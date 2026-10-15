from django.db import migrations

POLICY_NAME = "tenant_isolation"
TENANT_PREDICATE = (
    "store_id = NULLIF(current_setting('app.store_id', true), '')::uuid "
    "OR current_setting('app.rls_bypass', true) = 'on'"
)


def enable_rls(*tables):
    forward = []
    backward = []
    for table in tables:
        forward.extend(
            [
                f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
                f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
                f"CREATE POLICY {POLICY_NAME} ON {table} AS PERMISSIVE FOR ALL "
                f"USING ({TENANT_PREDICATE}) WITH CHECK ({TENANT_PREDICATE})",
            ]
        )
        backward.extend(
            [
                f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}",
                f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY",
                f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY",
            ]
        )
    return migrations.RunSQL(sql=forward, reverse_sql=backward)
