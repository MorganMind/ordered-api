from functools import wraps
from django.http import JsonResponse, HttpResponse
import jwt
import json
import os
from common.supabase.supabase_client import get_authenticated_client, set_current_user
from common.logger.logger_service import get_logger
from google.auth.transport import requests
from google.oauth2 import id_token
import base64
from google.auth import jwt as google_jwt
from hmac import HMAC, compare_digest
from hashlib import sha256
import time

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
            print("cock",token)
            print("balls",os.getenv('SUPABASE_JWT_SECRET'))
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

def cloud_task_handler(func):
    """
    Decorator for handling Cloud Tasks requests.
    Verifies OIDC token and handles errors.
    """
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        try:
            # Get the Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                logger.error("Missing or invalid Authorization header")
                return HttpResponse(status=401)

            # Extract the token
            token = auth_header.split('Bearer ')[1]

            # Verify the token
            try:
                # audience should match your Cloud Run service URL
                audience = request.build_absolute_uri('/')
                id_info = id_token.verify_oauth2_token(
                    token,
                    requests.Request(),
                    audience=audience,
                    clock_skew_in_seconds=300
                )

                # Verify issuer
                if id_info['iss'] not in ['https://accounts.google.com', 'accounts.google.com']:
                    raise ValueError('Wrong issuer.')

                # Parse the payload
                payload = json.loads(request.body.decode('utf-8')) if request.body else {}

                # Execute the task with await
                return await func(request, payload, *args, **kwargs)

            except ValueError as e:
                logger.error(f"Invalid token: {str(e)}")
                return HttpResponse(status=401)

        except Exception as e:
            logger.error(f"Task execution failed: {str(e)}")
            # Return 500 to trigger retry
            return HttpResponse(status=500)

    return wrapper

def pubsub_handler(func):
    """
    Decorator for handling Pub/Sub push messages.
    - Verifies the request is from Pub/Sub using JWT
    - Handles error responses
    - Parses and decodes the message payload
    """
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        try:
            # Verify the request has the required Pub/Sub authentication token
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                logger.error("Missing or invalid Authorization header")
                return HttpResponse(status=401)

            # Extract and verify the JWT token
            token = auth_header.split('Bearer ')[1]
            try:
                # Add debug logging
                logger.debug(f"Verifying Pub/Sub token for URL: {request.build_absolute_uri()}")
                
                # Use id_token.verify_oauth2_token instead of google_jwt.verify_token
                audience = request.build_absolute_uri()
                try:
                    id_info = id_token.verify_oauth2_token(
                        token,
                        requests.Request(),
                        audience=audience,
                        clock_skew_in_seconds=300
                    )
                    
                    # Verify issuer
                    if id_info['iss'] not in ['https://accounts.google.com', 'accounts.google.com']:
                        raise ValueError('Wrong issuer.')
                        
                except Exception as jwt_error:
                    logger.error(f"JWT verification failed: {type(jwt_error).__name__}: {str(jwt_error)}")
                    raise
                    
            except Exception as e:
                logger.error(f"Invalid Pub/Sub token. Error type: {type(e).__name__}")
                logger.error(f"Error details: {str(e)}")
                return HttpResponse(status=401)

            # Parse the message body
            try:
                body = json.loads(request.body)
                if 'message' not in body:
                    logger.error("Invalid Pub/Sub message format")
                    return HttpResponse(status=400)

                # Extract and decode the message data
                message = body['message']
                if 'data' in message:
                    try:
                        decoded_data = base64.b64decode(message['data']).decode('utf-8')
                        message['data'] = json.loads(decoded_data)
                    except Exception as e:
                        logger.error(f"Failed to decode message data: {str(e)}")
                        return HttpResponse(status=400)

                # Add parsed message to the request object for the handler
                request.pubsub_message = message
                request.pubsub_data = message.get('data')
                request.pubsub_attributes = message.get('attributes', {})

                # Call the handler with await
                return await func(request, *args, **kwargs)

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in request body: {str(e)}")
                return HttpResponse(status=400)

        except Exception as e:
            logger.error(f"Pub/Sub message handling failed: {str(e)}")
            # Return 500 to trigger Pub/Sub retry
            return HttpResponse(status=500)

    return wrapper