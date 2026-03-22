from django.urls import path

from .views import auth_me_view

urlpatterns = [
    path("auth/me/", auth_me_view, name="auth-me"),
]
