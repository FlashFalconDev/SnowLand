from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import migration_rollback_drill as drill


class DrillTests(unittest.TestCase):
    def test_defaults_and_localhost_are_pinned_to_loopback(self):
        default = drill.database_config({})
        self.assertEqual(default["HOST"], "127.0.0.1")
        self.assertEqual(default["NAME"], "snowland_migration_drill")
        self.assertEqual(default["PORT"], "33306")
        self.assertEqual(drill.database_config({"SNOWLAND_DRILL_HOST": "localhost"}), default)

    def test_rejects_remote_hosts_and_non_ci_mysql_alias(self):
        for host in ("db.example.invalid", "127.0.0.2", "localhost.", "::1", "127.0.0.1:3306", "mysql", ""):
            with self.subTest(host=host), self.assertRaises(ValueError):
                drill.database_config({"SNOWLAND_DRILL_HOST": host})
        env = {"SNOWLAND_DRILL_HOST": "mysql", "GITHUB_ACTIONS": "true"}
        self.assertEqual(drill.database_config(env)["HOST"], "mysql")
        env["SNOWLAND_DRILL_HOST"] = "other-service"
        with self.assertRaises(ValueError):
            drill.database_config(env)

    def test_rejects_real_looking_names_and_invalid_ports(self):
        for name in ("snowland", "contest", "prod_db_test", "test;drop", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                drill.database_config({"SNOWLAND_DRILL_DB": name})
        for port in ("0", "65536", "not-a-port", ""):
            with self.subTest(port=port), self.assertRaises(ValueError):
                drill.database_config({"SNOWLAND_DRILL_PORT": port})

    def test_dry_run_checks_guard_without_running_django(self):
        with patch.object(drill, "run_drill") as run, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(drill.main(["--app", "booking", "--dry-run"]), 0)
            with patch.dict(os.environ, {"SNOWLAND_DRILL_HOST": "db.example.invalid"}, clear=True):
                self.assertEqual(drill.main(["--app", "booking", "--dry-run"]), 1)
            run.assert_not_called()

    def test_existing_tables_prevent_migration(self):
        connection = Mock()
        connection.introspection.table_names.return_value = ["django_migrations"]
        with self.assertRaises(ValueError):
            drill.require_empty_database(connection)
        connection.introspection.table_names.assert_called_once_with(include_views=True)

    def test_two_steps_follow_same_app_parents(self):
        root, middle, latest = [("booking", f"{i:04d}_migration") for i in range(1, 4)]
        graph = Mock()
        graph.leaf_nodes.return_value = [latest]
        graph.node_map = {
            latest: SimpleNamespace(parents=[SimpleNamespace(key=middle), SimpleNamespace(key=("auth", "0001"))]),
            middle: SimpleNamespace(parents=[SimpleNamespace(key=root)]),
            root: SimpleNamespace(parents=[]),
        }
        self.assertEqual(drill.resolve_plan(graph, "booking", 2), (latest, root, {middle, latest}))
        self.assertEqual(drill.resolve_plan(graph, "booking", 3), (latest, None, {root, middle, latest}))
        with self.assertRaises(ValueError):
            drill.resolve_plan(graph, "booking", 4)
        graph.node_map[latest].parents.append(SimpleNamespace(key=root))
        with self.assertRaises(ValueError):
            drill.resolve_plan(graph, "booking", 1)
