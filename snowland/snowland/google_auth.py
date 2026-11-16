import re
import time

from google.auth.transport.requests import Request
from google.oauth2 import id_token


_TOKEN_USED_TOO_EARLY = re.compile(r'^Token used too early,\s*(\d+)\s*<\s*(\d+)\.')
_MAX_RETRY_WAIT_SECONDS = 5


def verify_google_oauth2_token(credential, audience):
    """Retry once after a short clock difference, keeping standard Google validation."""
    request = Request()
    try:
        return id_token.verify_oauth2_token(credential, request, audience)
    except ValueError as error:
        match = _TOKEN_USED_TOO_EARLY.match(str(error))
        if not match:
            raise
        wait_seconds = int(match[2]) - int(match[1]) + 1
        if not 0 < wait_seconds <= _MAX_RETRY_WAIT_SECONDS:
            raise

    time.sleep(wait_seconds)
    return id_token.verify_oauth2_token(credential, request, audience)
