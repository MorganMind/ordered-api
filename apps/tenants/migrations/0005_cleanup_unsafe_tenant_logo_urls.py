from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from django.db import migrations


def _is_unsafe_logo_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    )


def clear_unsafe_logo_urls(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    for tenant in Tenant.objects.exclude(logo_url__isnull=True).exclude(logo_url="").iterator():
        if _is_unsafe_logo_url(tenant.logo_url):
            tenant.logo_url = None
            tenant.save(update_fields=["logo_url"])


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0004_tenant_logo_url"),
    ]

    operations = [
        migrations.RunPython(clear_unsafe_logo_urls, migrations.RunPython.noop),
    ]
