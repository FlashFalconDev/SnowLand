from .settings import *  # noqa: F401,F403


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Several legacy project migrations contain MySQL-only raw SQL. Unit tests use
# SQLite and sync the current model state for local apps instead.
MIGRATION_MODULES = {
    "Client": None,
    "Coach": None,
    "Control": None,
    "Coursekit": None,
    "Courses": None,
    "Resorts": None,
    "booking": None,
    "chatbooking": None,
}
