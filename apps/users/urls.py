from django.urls import path

from .views import UserMeAvatarUploadView, UserMeView

urlpatterns = [
    path("users/me/", UserMeView.as_view(), name="users-me"),
    path("users/me/avatar/", UserMeAvatarUploadView.as_view(), name="users-me-avatar"),
]
