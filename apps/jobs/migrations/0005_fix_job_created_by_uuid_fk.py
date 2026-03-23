"""
Repair schema drift: ``created_by_id`` / ``client_id`` were integer FKs to
``auth_user`` while ``AUTH_USER_MODEL`` is ``users.User`` (UUID PK).

PostgreSQL only; SQLite and other backends no-op (ORM already matches models).
"""

from django.db import migrations


def _drop_fk_to_auth_user(cursor, table: str, column: str) -> None:
    cursor.execute(
        """
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_schema = kcu.constraint_schema
         AND tc.constraint_name = kcu.constraint_name
        WHERE tc.table_schema = 'public'
          AND tc.table_name = %s
          AND tc.constraint_type = 'FOREIGN KEY'
          AND kcu.column_name = %s
        """,
        [table, column],
    )
    for (name,) in cursor.fetchall():
        cursor.execute(
            'ALTER TABLE "%s" DROP CONSTRAINT IF EXISTS "%s";' % (table, name)
        )


def fix_uuid_fks(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor != "postgresql":
        return

    with conn.cursor() as cursor:
        _drop_fk_to_auth_user(cursor, "jobs", "created_by_id")
        # Integer auth_user FKs cannot map to users_user UUIDs; null out then cast.
        cursor.execute(
            """
            ALTER TABLE jobs
            ALTER COLUMN created_by_id TYPE uuid
            USING (NULL::uuid);
            """
        )
        cursor.execute(
            """
            ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_created_by_id_fkey;
            ALTER TABLE jobs ADD CONSTRAINT jobs_created_by_id_fkey
                FOREIGN KEY (created_by_id)
                REFERENCES users_user (id)
                ON DELETE SET NULL;
            """
        )

        _drop_fk_to_auth_user(cursor, "service_requests", "client_id")
        cursor.execute(
            """
            ALTER TABLE service_requests
            ALTER COLUMN client_id TYPE uuid
            USING (NULL::uuid);
            """
        )
        cursor.execute(
            """
            ALTER TABLE service_requests DROP CONSTRAINT IF EXISTS service_requests_client_id_fkey;
            ALTER TABLE service_requests ADD CONSTRAINT service_requests_client_id_fkey
                FOREIGN KEY (client_id)
                REFERENCES users_user (id)
                ON DELETE SET NULL;
            """
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0004_booking_domain"),
        ("service_requests", "0003_alter_servicerequest_address_normalized_and_more"),
    ]

    operations = [
        migrations.RunPython(fix_uuid_fks, noop_reverse),
    ]
