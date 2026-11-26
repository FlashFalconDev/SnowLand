"""Check committed PR migration changes without Django or a database."""

import argparse
import ast
from collections import defaultdict
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


MIGRATION_PATH = re.compile(r"snowland/[^/]+/migrations/(?!__init__\.py$)[^/]+\.py")
TIER_3 = {
    "DeleteModel", "RemoveField", "RenameField", "RenameModel", "RunPython", "RunSQL",
}
TIER_2 = {
    "AddConstraint", "AddIndex", "AlterField", "AlterIndexTogether",
    "AlterUniqueTogether", "ForeignKey", "OneToOneField",
}


def git(*args, cwd):
    return subprocess.check_output(["git", *args], cwd=cwd, stderr=subprocess.PIPE)


def migration_names(tree):
    """Read explicit dependency edges without executing migration code."""
    migration = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Migration"
    )
    dependencies = []
    for assignment in migration.body:
        if isinstance(assignment, ast.Assign):
            targets = assignment.targets
        elif isinstance(assignment, ast.AnnAssign):
            targets = [assignment.target]
        else:
            continue
        fields = {node.id for node in targets if isinstance(node, ast.Name)}
        if "replaces" in fields:
            raise ValueError("含 replaces")
        for field in fields & {"dependencies", "run_before"}:
            if not isinstance(assignment.value, (ast.List, ast.Tuple)):
                raise ValueError(f"{field} 不是明列的清單")
            for entry in assignment.value.elts:
                if (
                    isinstance(entry, ast.Call)
                    and isinstance(entry.func, ast.Attribute)
                    and entry.func.attr == "swappable_dependency"
                    and field == "dependencies"
                ):
                    # Common cross-app edge with a settings-dependent target.
                    continue
                pair = ast.literal_eval(entry)
                if not isinstance(pair, (tuple, list)) or len(pair) != 2 or not all(
                    isinstance(value, str) for value in pair
                ):
                    raise ValueError(f"{field} 有未知格式")
                dependencies.append((field, *pair))
    return dependencies


def tier_hint(tree):
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                calls.add(node.func.id)
    for operations, tier in ((TIER_3, 3), (TIER_2, 2)):
        matched = sorted(calls & operations)
        if matched:
            return f"可能為 Tier {tier}（{', '.join(matched)}），須在部署計畫取得小陌同意"
    return "確認是否符合 Tier 1，需核對實際 DDL 與舊版相容性"


def check_graph(paths, new_paths, app, cwd):
    errors = []
    warnings = []
    hints = {}
    numbered = defaultdict(list)
    by_name = {PurePosixPath(path).stem: path for path in paths}
    leaves = set(by_name)
    for name, path in by_name.items():
        number = re.match(r"^([0-9]+)(?:_|$)", name)
        if number:
            numbered[int(number[1])].append(path)
        try:
            tree = ast.parse(git("show", f"HEAD:{path}", cwd=cwd), filename=path)
            if path in new_paths:
                hints[path] = tier_hint(tree)
            for field, dependency_app, dependency_name in migration_names(tree):
                if dependency_app == app:
                    if dependency_name not in by_name:
                        raise ValueError(f"{field} 指向未知的 {dependency_name}")
                    leaves.discard(dependency_name if field == "dependencies" else name)
        except (SyntaxError, ValueError, StopIteration) as error:
            warnings.append(f"{path} 的相依性無法解析（{error or '找不到 Migration 類別'}）")
    for number, duplicates in sorted(numbered.items()):
        if len(duplicates) > 1 and new_paths.intersection(duplicates):
            errors.append(f"{app} 的 migration 編號 {number:04d} 重複：{', '.join(duplicates)}")
    if warnings:
        warnings.append(f"{app} 的 migration leaf 待人工核對")
    elif len(leaves) != 1:
        errors.append(f"{app} 必須有一個 migration leaf，目前有 {len(leaves)} 個：{', '.join(sorted(leaves))}")
    return errors, warnings, hints


def check(base, body, cwd):
    base_commit = git("rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}", cwd=cwd)
    merge_base = git("merge-base", base_commit.decode().strip(), "HEAD", cwd=cwd).decode().strip()
    entries = git(
        "diff", "--name-status", "-z", "--no-renames", merge_base, "HEAD", "--", "snowland/", cwd=cwd,
    ).decode("utf-8").split("\0")
    changes = [
        (status, path) for status, path in zip(entries[::2], entries[1::2])
        if MIGRATION_PATH.fullmatch(path)
    ]
    added = {path for status, path in changes if status == "A"}
    existing = [path for status, path in changes if status != "A"]
    errors = [f"既有 migration 被修改或刪除：{path}" for path in existing]
    warnings = []
    hints = {}
    if added:
        body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
        declarations = re.findall(r"^Migration：[ \t]*([有無])[ \t\r]*$", body, flags=re.MULTILINE)
        if declarations != ["有"]:
            errors.append("PR 說明須有一行 Migration：有")
        listed = set(re.findall(r"^[ \t]*-[ \t]+`([^`\r\n]+)`", body, flags=re.MULTILINE))
        for path in sorted(added - listed):
            errors.append(f"PR 說明缺少 migration 路徑：{path}")
        tracked = git("ls-tree", "-r", "-z", "--name-only", "HEAD", "--", "snowland/", cwd=cwd)
        migrations = [
            path for path in tracked.decode("utf-8").split("\0") if MIGRATION_PATH.fullmatch(path)
        ]
        for app in sorted({path.split("/")[1] for path in added}):
            paths = [path for path in migrations if path.split("/")[1] == app]
            graph_errors, graph_warnings, graph_hints = check_graph(paths, added, app, cwd)
            errors.extend(graph_errors)
            warnings.extend(graph_warnings)
            hints.update(graph_hints)

    print(f"Migration 摘要（base {base}，merge base {merge_base[:8]}）")
    print(f"新增 {len(added)} 支，修改或刪除既有 migration {len(existing)} 支。")
    for path in sorted(added):
        print(f"- {path}：{hints.get(path, '分級待人工確認')}")
    for warning in warnings:
        print(f"警告：{warning}")
    for error in errors:
        print(f"失敗：{error}")
    if not errors:
        print("通過。" if added else "通過：無新 migration。")
    return int(bool(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--pr-body-file", type=Path)
    args = parser.parse_args()
    try:
        body = (
            args.pr_body_file.read_text(encoding="utf-8-sig")
            if args.pr_body_file else os.getenv("PR_BODY", "")
        )
        return check(args.base, body, cwd=Path(__file__).resolve().parents[1])
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            error = error.stderr.decode("utf-8", errors="replace").strip() or str(error)
        print(f"Migration 檢查無法完成：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
