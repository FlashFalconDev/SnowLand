"""Rehearse Django migrations on a fresh disposable MySQL database."""

import argparse
import os
from pathlib import Path
import re
import secrets
import sys
from unittest.mock import patch


def database_config(env):
    host = env.get("SNOWLAND_DRILL_HOST", "127.0.0.1")
    if host in ("localhost", "127.0.0.1"):
        host = "127.0.0.1"  # Use TCP explicitly and skip hostname resolution.
    elif host != "mysql" or env.get("GITHUB_ACTIONS") != "true":
        raise ValueError("只允許本機 loopback 或 GitHub Actions 的 mysql service")

    name = env.get("SNOWLAND_DRILL_DB", "snowland_migration_drill")
    words = set(name.lower().split("_"))
    if (
        not re.fullmatch(r"[a-zA-Z0-9_]{1,64}", name)
        or not words & {"test", "drill", "throwaway"}
        or words & {"prod", "production"}
    ):
        raise ValueError("資料庫名稱須包含以底線分隔的 test、drill 或 throwaway")

    port = env.get("SNOWLAND_DRILL_PORT", "33306")
    if not re.fullmatch(r"[0-9]{1,5}", port) or not 1 <= int(port) <= 65535:
        raise ValueError("MySQL port 須介於 1 至 65535")
    return {
        "ENGINE": "django.db.backends.mysql",
        "HOST": host,
        "PORT": port,
        "NAME": name,
        "USER": env.get("SNOWLAND_DRILL_USER", ""),
        "PASSWORD": env.get("SNOWLAND_DRILL_PASSWORD", ""),
        "OPTIONS": {"charset": "utf8mb4", "connect_timeout": 5},
    }


def resolve_plan(graph, app, steps):
    leaves = graph.leaf_nodes(app)
    if len(leaves) != 1:
        raise ValueError(f"{app} 須有一個 migration leaf，現在有 {len(leaves)} 個")
    target = leaves[0]
    current = target
    selected = set()
    for _ in range(steps):
        if current is None:
            raise ValueError(f"{app} 沒有足夠的 migration 可回退 {steps} 步")
        selected.add(current)
        parents = [node.key for node in graph.node_map[current].parents if node.key[0] == app]
        if len(parents) > 1:
            raise ValueError(f"{current[1]} 有多個同 app 的前序 migration，無法選定回退點")
        current = parents[0] if parents else None
    return target, current, selected


def configure_django(config):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "snowland"))
    import django
    from django.conf import settings
    import requests

    local_key = secrets.token_urlsafe(32)
    # SnowLand imports its base settings before applying test overrides.
    # Keep dotenv and instance metadata out of the rehearsal.
    with (
        patch.dict(os.environ, {"DJANGO_SECRET_KEY": local_key}),
        patch("dotenv.load_dotenv"),
        patch("dotenv.dotenv_values", return_value={}),
        patch("requests.put", side_effect=requests.ConnectionError),
    ):
        from snowland import test_settings

    options = {name: getattr(test_settings, name) for name in dir(test_settings) if name.isupper()}
    options.update(
        DATABASES={"default": config},
        MIGRATION_MODULES={},  # Restore real migrations disabled for SQLite tests.
        DEBUG=False,
        EMAIL_BACKEND="django.core.mail.backends.dummy.EmailBackend",
    )
    settings.configure(**options)
    django.setup()


def require_empty_database(connection):
    if connection.introspection.table_names(include_views=True):
        raise ValueError("資料庫已有資料表或 view，請使用新建的拋棄式空庫")


def run_drill(config, app, steps):
    configure_django(config)
    from django.core.management import call_command
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.recorder import MigrationRecorder

    try:
        require_empty_database(connection)
        target, previous, selected = resolve_plan(MigrationLoader(connection).graph, app, steps)
        recorder = MigrationRecorder(connection)
        rollback_to = previous[1] if previous else "zero"
        print(f"MySQL {connection.mysql_server_info} / {app}：{target[1]} → {rollback_to} → {target[1]}", flush=True)
        for stage, destination in (("套用", target[1]), ("回退", rollback_to), ("重新套用", target[1])):
            call_command("migrate", app, destination, interactive=False, verbosity=0)
            applied = set(recorder.applied_migrations())
            if stage == "回退":
                verified = not (selected & applied) and (previous is None or previous in applied)
            else:
                verified = selected <= applied
            if not verified:
                raise ValueError(f"{stage}後的 django_migrations 狀態不符")
            print(f"{stage}通過：{app}.{destination}", flush=True)
    finally:
        connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, help="Django app label")
    parser.add_argument("--steps", type=int, default=1, help="從最新 migration 回退的步數")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.app) or args.steps < 1:
        parser.error("請提供有效的 app label，且 --steps 至少為 1")

    password = ""
    try:
        config = database_config(os.environ)
        print(f"演練目標：{config['HOST']}:{config['PORT']}/{config['NAME']}（{args.app}）", flush=True)
        if args.dry_run:
            print(f"Dry run：套用最新 migration → 回退 {args.steps} 步 → 重新套用。未連線。")
            return 0
        password = config["PASSWORD"]
        if not config["USER"] or not password:
            raise ValueError("請由環境變數提供演練專用的 MySQL 使用者和密碼")
        run_drill(config, args.app, args.steps)
    except Exception as error:
        message = str(error)
        if password:
            message = message.replace(password, "[已遮蔽]")
        print(f"演練失敗（{type(error).__name__}）：{message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
