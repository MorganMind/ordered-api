import json
from functools import lru_cache, wraps

from django.http import JsonResponse
import jwt
import os
import ssl
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError

from common.supabase.supabase_client import get_authenticated_client, set_current_user
from common.logger.logger_service import get_logger

logger = get_logger()


def _jwks_ssl_verify_disabled() -> bool:
    """Local dev escape hatch if JWKS HTTPS still fails (e.g. corporate proxy)."""
    return os.getenv("SUPABASE_JWKS_INSECURE_SSL", "").lower() in ("1", "true", "yes")


def _jwks_ssl_context(*, insecure: bool) -> ssl.SSLContext:
    """
    urllib HTTPS to Supabase JWKS. macOS / some Python builds lack a usable default CA store;
    certifi fixes [SSL: CERTIFICATE_VERIFY_FAILED] for public Supabase URLs.
    """
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return ctx


@lru_cache(maxsize=8)
def _py_jwk_client(jwks_url: str, insecure: bool) -> PyJWKClient:
    """Cached JWKS client for Supabase asymmetric (RS256/ES256) JWTs."""
    return PyJWKClient(
        jwks_url, ssl_context=_jwks_ssl_context(insecure=insecure)
    )


def _decode_supabase_jwt(token: str) -> dict:
    """
    Verify Supabase access tokens.

    - HS256: legacy JWT secret (SUPABASE_JWT_SECRET)
    - RS256 / ES256: JWKS at {SUPABASE_URL}/auth/v1/.well-known/jwks.json

    PyJWT raises "The specified alg value is not allowed" if `algorithms=` omits the token's alg;
    Supabase often issues RS256 now, while older code only passed HS256.
    """
    header = jwt.get_unverified_header(token)
    alg = header.get("alg") or "HS256"

    if alg == "HS256":
        secret = os.getenv("SUPABASE_JWT_SECRET")
        if not secret:
            raise jwt.InvalidTokenError(
                "SUPABASE_JWT_SECRET is not set (required for HS256 tokens)"
            )
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={
                "verify_iat": False,
                "verify_aud": False,
                "verify_signature": True,
            },
        )

    if alg in ("RS256", "ES256"):
        base = (os.getenv("SUPABASE_URL") or "").rstrip("/")
        if not base:
            raise jwt.InvalidTokenError(
                "SUPABASE_URL is not set (required for RS256/ES256 tokens)"
            )
        jwks_url = f"{base}/auth/v1/.well-known/jwks.json"
        insecure = _jwks_ssl_verify_disabled()
        signing_key = _py_jwk_client(jwks_url, insecure).get_signing_key_from_jwt(
            token
        )
        # Match previous relaxed checks; signature is verified via JWKS.
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            issuer=f"{base}/auth/v1",
            options={
                "verify_signature": True,
                "verify_aud": False,
                "verify_iat": False,
                "verify_iss": True,
            },
        )

    raise jwt.InvalidTokenError(f"Unsupported JWT algorithm: {alg}")

def auth_required(allow_anonymous=False):
    """
    Decorator to validate Supabase JWT tokens.
    
    Args:
        allow_anonymous (bool): If True, allows requests without auth tokens
    """
    def decorator(view_func):
        @wraps(view_func)
        async def wrapped_view(request, *args, **kwargs):
            auth_header = request.headers.get('Authorization')
            
            # For public routes (allow_anonymous=True), proceed without auth
            if allow_anonymous and not auth_header:
                return await view_func(request, *args, **kwargs)
            
            if not auth_header or not auth_header.startswith('Bearer '):
                return JsonResponse({'error': 'No valid authorization header'}, status=401)
            
            token = auth_header.split(' ')[1]
            
            try:
                decoded = _decode_supabase_jwt(token)
                print(decoded)
                request.jwt_claims = decoded
                # Add user info to request
                request.user_id = decoded.get("sub")
                # JWT top-level "role" is Supabase session scope (authenticated / anon), not app RBAC.
                request.supabase_jwt_role = decoded.get("role")
                request.user_email = decoded.get("email")
                request.supabase = get_authenticated_client(token)

                user_metadata = decoded.get("user_metadata") or {}
                app_metadata = decoded.get("app_metadata") or {}
                # App RBAC: prefer app_metadata (operator/admin set in Supabase dashboard/SQL)
                # over user_metadata (often "client" from consumer signup).
                request.user_role = app_metadata.get("role") or user_metadata.get("role")
                analytics_id = user_metadata.get("analytics_id")

                set_current_user({
                    "id": request.user_id,
                    "email": request.user_email,
                    "role": request.user_role,
                    "analytics_id": analytics_id,
                    "avatar_url": user_metadata.get("avatar_url") if user_metadata.get("avatar_url") else None,
                    "full_name": user_metadata.get("full_name") if user_metadata.get("full_name") else None
                })

                return await view_func(request, *args, **kwargs)
                
            except jwt.ExpiredSignatureError:
                return JsonResponse({'error': 'Token has expired'}, status=401)
            except (jwt.InvalidTokenError, PyJWKClientError) as e:
                return JsonResponse({'error': f'Invalid token: {str(e)}'}, status=401)
            
        return wrapped_view
    return decorator


def cloud_task_handler(view_func):
    """
    Wrap Cloud Tasks (or local) POST handlers: parse JSON body and pass ``payload`` dict.

    Production can add OIDC / queue verification here; for now only JSON parsing is enforced.
    """

    @wraps(view_func)
    async def wrapper(request, *args, **kwargs):
        if request.method != "POST":
            return JsonResponse({"error": "Method not allowed"}, status=405)
        try:
            raw = request.body.decode() if request.body else "{}"
            payload = json.loads(raw) if raw.strip() else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        return await view_func(request, payload, *args, **kwargs)

    return wrapper
