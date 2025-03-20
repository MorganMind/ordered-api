from django.urls import path
from .views import task_view

urlpatterns = [
    path('create/handle-ingest-source', task_view.handle_ingest_source, name='handle-ingest-source'),
    path('create/handle-delete-source', task_view.handle_delete_source, name='handle-delete-source'),
]
