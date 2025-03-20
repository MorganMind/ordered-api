from django.urls import path
from .views import invite_view
from common.auth_routes import create_protected_urls
urlpatterns = [
    path('invites/', invite_view.get_invites_view, name='get_invites'),
    path('invites/create/', invite_view.create_invite_view, name='create_invite'),
    path('public/invites/<str:invite_id>/details/', invite_view.get_invite_view, name='get_invite'),
    path('invites/<str:invite_id>/accept/', invite_view.accept_invite_view, name='accept_invite'),
    path('invites/<str:invite_id>/decline/', invite_view.decline_invite_view, name='decline_invite'),
    path('invites/<str:invite_id>/', invite_view.delete_invite_view, name='delete_invite'),
]

# Protect all routes
urlpatterns = create_protected_urls(
    urlpatterns,
    public_prefixes=[
        'public/invites/',
    ]
) 