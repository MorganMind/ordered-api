from functools import partial
from .decorators import auth_required

def public_route(view_func):
    return auth_required(allow_anonymous=True)(view_func)

def private_route(view_func):
    return auth_required(allow_anonymous=False)(view_func)

def create_protected_urls(urlpatterns, public_prefixes=None):
    """
    Wraps URL patterns with appropriate auth decorators based on their paths.
    
    Args:
        urlpatterns: List of URL patterns
        public_prefixes: List of URL prefixes that should be public
    """
    public_prefixes = public_prefixes or [
        'public/',
        'auth/',
    ]
    
    protected_patterns = []
    for pattern in urlpatterns:
        # Get the raw pattern string from the path
        raw_path = pattern.pattern._route
       
        if any(raw_path.startswith(prefix) for prefix in public_prefixes):
            pattern.callback = public_route(pattern.callback)
        else:
            pattern.callback = private_route(pattern.callback)
        protected_patterns.append(pattern)
    
    return protected_patterns 