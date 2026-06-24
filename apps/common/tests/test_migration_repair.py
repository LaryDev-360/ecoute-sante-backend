from django.test import TestCase

from apps.common.migration_repair import repair_migration_state, schema_is_ready


class MigrationRepairTests(TestCase):
    def test_fresh_database_is_ready_after_migrate(self):
        self.assertTrue(schema_is_ready())

    def test_repair_on_ready_schema_is_noop(self):
        self.assertEqual(repair_migration_state(), "schema_ok")
