# Generated migration for events app
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event_type', models.CharField(choices=[('booking.created', 'Booking Created'), ('booking.confirmed', 'Booking Confirmed'), ('booking.cancelled', 'Booking Cancelled'), ('booking.completed', 'Booking Completed'), ('booking.rescheduled', 'Booking Rescheduled'), ('job.assigned', 'Job Assigned'), ('job.started', 'Job Started'), ('job.completed', 'Job Completed'), ('job.cancelled', 'Job Cancelled'), ('technician.assigned', 'Technician Assigned'), ('technician.unassigned', 'Technician Unassigned'), ('technician.checked_in', 'Technician Checked In'), ('technician.checked_out', 'Technician Checked Out'), ('memory.created', 'Memory Created'), ('memory.updated', 'Memory Updated'), ('memory.deleted', 'Memory Deleted'), ('user.created', 'User Created'), ('user.updated', 'User Updated'), ('user.deactivated', 'User Deactivated'), ('user.reactivated', 'User Reactivated'), ('property.created', 'Property Created'), ('property.updated', 'Property Updated'), ('property.deleted', 'Property Deleted'), ('service.created', 'Service Created'), ('service.updated', 'Service Updated'), ('service.deleted', 'Service Deleted')], db_index=True, help_text='Type of event that occurred', max_length=50)),
                ('entity_type', models.CharField(choices=[('booking', 'Booking'), ('job', 'Job'), ('user', 'User'), ('property', 'Property'), ('service', 'Service'), ('memory', 'Memory'), ('technician', 'Technician')], db_index=True, help_text='Type of entity this event relates to', max_length=50)),
                ('entity_id', models.UUIDField(db_index=True, help_text='ID of the entity this event relates to')),
                ('payload', models.JSONField(default=dict, help_text='Event-specific data and context')),
                ('ip_address', models.GenericIPAddressField(blank=True, help_text='IP address of the request that triggered the event', null=True)),
                ('user_agent', models.TextField(blank=True, help_text='User agent of the request')),
                ('actor', models.ForeignKey(blank=True, help_text='User who performed the action', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events_created', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name='events', to='tenants.tenant')),
            ],
            options={
                'db_table': 'events',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['tenant', 'event_type', '-created_at'], name='events_tenant_event_created_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['tenant', 'entity_type', 'entity_id', '-created_at'], name='events_tenant_entity_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['tenant', 'actor', '-created_at'], name='events_tenant_actor_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['tenant', '-created_at'], name='events_tenant_created_idx'),
        ),
    ]
