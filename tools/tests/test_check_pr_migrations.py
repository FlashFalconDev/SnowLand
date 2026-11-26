from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from tools.check_pr_migrations import check


class CheckPRMigrationsTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.git("init", "-q", "--initial-branch=main")
        self.git("config", "core.autocrlf", "false")
        self.root = self.migration("0001_initial")
        self.commit("base")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def commit(self, message):
        self.git("add", "--all")
        self.git(
            "-c", "user.name=Migration Tests", "-c", "user.email=migrations@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-qm", message,
        )

    def migration(self, name, parent=None, *, dependencies=None, operation=None, app="booking"):
        path = f"snowland/{app}/migrations/{name}.py"
        file = self.repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        if dependencies is None:
            dependencies = repr([(app, parent)] if parent else [])
        operations = "[]" if operation is None else f"[{operation}]"
        file.write_text(
            f"class Migration(migrations.Migration):\n"
            f"    dependencies = {dependencies}\n"
            f"    operations = {operations}\n",
            encoding="utf-8",
        )
        return path

    def check(self, body="", base="main"):
        output = StringIO()
        with redirect_stdout(output):
            status = check(base, body, self.repo)
        return status, output.getvalue()

    def body(self, *paths):
        return "Migration：有\n" + "\n".join(f"- `{path}` — Tier 1" for path in paths)

    def test_excludes_init_and_uncommitted_files(self):
        self.git("checkout", "-qb", "candidate")
        (self.repo / self.root).with_name("__init__.py").touch()
        self.commit("add package marker")
        self.migration("0002_uncommitted", "0001_initial")
        status, output = self.check()
        self.assertEqual(status, 0)
        self.assertIn("無新 migration", output)

    def test_rejects_modifying_or_deleting_existing_file(self):
        self.git("checkout", "-qb", "candidate")
        self.migration("0001_initial", operation="migrations.CreateModel()")
        self.commit("edit")
        status, output = self.check()
        self.assertEqual(status, 1)
        self.assertIn(self.root, output)
        (self.repo / self.root).unlink()
        self.commit("delete")
        status, output = self.check()
        self.assertEqual(status, 1)
        self.assertIn(self.root, output)

    def test_uses_selected_base_and_merge_base(self):
        self.git("checkout", "-qb", "bot")
        self.migration("0002_already_in_bot", "0001_initial")
        self.commit("bot migration")
        self.git("checkout", "-qb", "candidate")
        added = self.migration("0003_candidate", "0002_already_in_bot")
        self.commit("candidate migration")
        self.git("checkout", "bot")
        self.migration("0003_after_branching", "0002_already_in_bot")
        self.commit("bot moved")
        self.git("checkout", "candidate")
        self.assertEqual(self.check(self.body(added), base="bot")[0], 0)
        self.assertEqual(self.check(self.body(added), base="main")[0], 1)

    def test_rejects_missing_wrong_or_hidden_pr_entries(self):
        self.git("checkout", "-qb", "candidate")
        added = self.migration("0002_new", "0001_initial")
        self.commit("add migration")
        for body in ("", f"Migration：有\n<!-- - `{added}` -->", self.body(added) + "\nMigration：無"):
            with self.subTest(body=body):
                self.assertEqual(self.check(body)[0], 1)
        self.assertEqual(self.check(self.body(added))[0], 0)

    def test_rejects_duplicate_number_even_on_linear_graph(self):
        self.git("checkout", "-qb", "candidate")
        added = self.migration("0001_duplicate", "0001_initial")
        self.commit("duplicate")
        status, output = self.check(self.body(added))
        self.assertEqual(status, 1)
        self.assertIn("編號 0001 重複", output)

    def test_rejects_fork_and_accepts_merge(self):
        self.git("checkout", "-qb", "candidate")
        left = self.migration("0002_left", "0001_initial")
        right = self.migration("0003_right", "0001_initial")
        self.commit("fork")
        status, output = self.check(self.body(left, right))
        self.assertEqual(status, 1)
        self.assertIn("目前有 2 個", output)
        merge = self.migration(
            "0004_merge", dependencies="[('booking', '0002_left'), ('booking', '0003_right')]",
        )
        self.commit("merge migration")
        self.assertEqual(self.check(self.body(left, right, merge))[0], 0)

    def test_warns_on_dynamic_dependencies_and_tier_is_advisory(self):
        self.git("checkout", "-qb", "candidate")
        added = self.migration("0002_dynamic", dependencies="build_edges()", operation="migrations.RunPython()")
        self.commit("dynamic")
        status, output = self.check(self.body(added))
        self.assertEqual(status, 0)
        self.assertIn("leaf 待人工核對", output)
        self.assertIn("Tier 3", output)

    def test_warns_on_tier_two_without_failing(self):
        self.git("checkout", "-qb", "candidate")
        added = self.migration("0002_index", "0001_initial", operation="migrations.AddIndex()")
        self.commit("index")
        status, output = self.check(self.body(added))
        self.assertEqual(status, 0)
        self.assertIn("Tier 2", output)
