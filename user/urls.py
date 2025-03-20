from django.urls import path
from .views.user_view import (
    get_or_create_user_data_view, 
    complete_onboarding_view, 
    update_user_view,
)
from .views.analytics_view import get_user_analytics_view
from common.auth_routes import create_protected_urls
from .views import user_settings_view

# Define your URL patterns
urlpatterns = [
    path("user/data/", get_or_create_user_data_view, name="get_or_create_user_data"),
    path("user/data/update/", update_user_view, name="update_user_data"),
    path("user/complete-onboarding/", complete_onboarding_view, name="complete_onboarding"),
    path("user/analytics/", get_user_analytics_view, name="get_user_analytics"),
    path('settings/', user_settings_view.get_user_settings, name='get_user_settings'),
    path('settings/update/', user_settings_view.update_user_settings, name='update_user_settings'),
]

# Wrap them with auth protection
urlpatterns = create_protected_urls(
    urlpatterns
) 