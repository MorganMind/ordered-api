from django.urls import path
from .views.tag_view import (
    create_tag_view,
    create_tagging_view,
    remove_tagging_view,
    get_user_tags_view,
    get_taggings_for_item_view,
    get_item_ids_for_tags_view
)
from common.auth_routes import create_protected_urls

# Define URL patterns
urlpatterns = [
    path("tags/create/", create_tag_view, name="create_tag"),
    path("tags/tagging/create/", create_tagging_view, name="create_tagging"),
    path("tags/tagging/remove/", remove_tagging_view, name="remove_tagging"),
    path("tags/", get_user_tags_view, name="get_user_tags"),
    path("tags/taggings/<str:taggable_type>/<str:taggable_id>/", get_taggings_for_item_view, name="get_taggings_for_item"),
    path("tags/items/", get_item_ids_for_tags_view, name="get_item_ids_for_tags"),
]

# Protect all routes
urlpatterns = create_protected_urls(urlpatterns) 