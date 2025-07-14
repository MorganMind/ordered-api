from django.urls import path
from transcription.views.transcription_view import transcribe_stream_view
from common.auth_routes import create_protected_urls

# Define your URL patterns as normal
urlpatterns = [
    path("transcribe/", transcribe_stream_view, name="transcribe_stream"),
]

# Wrap them with auth protection
urlpatterns = create_protected_urls(
    urlpatterns
)