import os

from .test_settings import *  # noqa: F401,F403


# Replay the project's migrations on MySQL, as premerge does.
MIGRATION_MODULES = {}

# Use the premerge image's default SQL mode and make its test collation explicit.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "snowland_ci",
        "HOST": os.getenv("SNOWLAND_TEST_MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("SNOWLAND_TEST_MYSQL_PORT", "3306"),
        "USER": os.getenv("SNOWLAND_TEST_MYSQL_USER", "root"),
        "PASSWORD": os.getenv("SNOWLAND_TEST_MYSQL_PASSWORD", "test"),
        "OPTIONS": {"charset": "utf8mb4"},
        "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_0900_ai_ci"},
    },
}
