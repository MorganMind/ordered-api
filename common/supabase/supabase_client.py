from supabase import create_client, create_async_client, ClientOptions
import os
from contextvars import ContextVar
from typing import Optional
from user.models.user_context import UserContext

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Separate context variables for regular and admin clients
current_client: ContextVar[Optional[object]] = ContextVar('current_client', default=None)
admin_client: ContextVar[Optional[object]] = ContextVar('admin_client', default=None)
current_user: ContextVar[Optional[UserContext]] = ContextVar('current_user', default=None)

def get_authenticated_client(access_token=None):
    """
    Get regular client that respects RLS policies
    """
    client = current_client.get()
    if client is not None:
        return client
    
    client_options = ClientOptions(
        postgrest_client_timeout=180,
    )

    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=client_options)
    if access_token:
        client.auth.set_session(access_token, "")
    
    current_client.set(client)
    return client

def get_admin_client():
    """
    Get admin client that bypasses RLS policies - use with caution!
    """
    client = admin_client.get()
    if client is not None:
        return client

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    admin_client.set(client)
    return client

def set_current_user(user: UserContext):
    """Set the user data in the current context"""
    current_user.set(user)

def get_current_user() -> UserContext:
    """Get the user data from the current context"""
    user = current_user.get()
    if user is None:
        raise ValueError("No authenticated user found in current context")
    return user