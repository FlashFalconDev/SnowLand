"""Isolated test database for development machines without local MySQL."""

import os

from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('SNOWLAND_SQLITE_PATH', ':memory:'),
    },
}

# Local browser QA runs on plain HTTP. Production settings remain Secure-only.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
