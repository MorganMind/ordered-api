from django.urls import path
from .views.file_view import generate_file_upload_url_view, generate_image_upload_url_view
from common.auth_routes import create_protected_urls

urlpatterns = [
    path("files/upload-url/", generate_file_upload_url_view, name="generate_file_upload_url"),
    path("files/images/upload-url/", generate_image_upload_url_view, name="generate_image_upload_url"),
]

# Wrap them with auth protection
urlpatterns = create_protected_urls(urlpatterns) 