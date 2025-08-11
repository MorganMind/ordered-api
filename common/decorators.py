from functools import wraps
from django.http import JsonResponse
import jwt
import json
import os
from common.supabase.supabase_client import get_authenticated_client, set_current_user
from common.logger.logger_service import get_logger

logger = get_logger()

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
                # Decode and verify the JWT token
                decoded = jwt.decode(
                    token,
                    os.getenv('SUPABASE_JWT_SECRET'),
                    algorithms=["HS256"],
                    options={
                        "verify_iat": False,
                        "verify_aud": False,
                        "verify_signature": True
                    }
                )
                print(decoded)
                # Add user info to request
                request.user_id = decoded.get('sub')
                request.user_role = decoded.get('role')
                request.user_email = decoded.get('email')
                request.supabase = get_authenticated_client(token)
                
                user_metadata = decoded.get('user_metadata', {})
                analytics_id = user_metadata.get('analytics_id')
               
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
            except jwt.InvalidTokenError as e:
                return JsonResponse({'error': f'Invalid token: {str(e)}'}, status=401)
            
        return wrapped_view
    return decorator
