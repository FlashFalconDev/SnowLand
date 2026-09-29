import re
import time

from django.conf import settings


_TOKEN_USED_TOO_EARLY = re.compile(r"Token used too early,\s*(\d+)\s*<\s*(\d+)")
_MAX_RETRY_WAIT_SECONDS = 5


def verify_google_oauth2_token(credential):
    """Verify a Google token, retrying once for a tiny server clock lead."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    request = google_requests.Request()

    def verify():
        return id_token.verify_oauth2_token(
            credential,
            request,
            settings.GOOGLE_OAUTH_CLIENT_ID,
            clock_skew_in_seconds=settings.GOOGLE_OAUTH_CLOCK_SKEW_SECONDS,
        )

    try:
        return verify()
    except ValueError as exc:
        match = _TOKEN_USED_TOO_EARLY.search(str(exc))
        if not match:
            raise

        wait_seconds = int(match.group(2)) - int(match.group(1)) + 1
        if wait_seconds <= 0 or wait_seconds > _MAX_RETRY_WAIT_SECONDS:
            raise

        time.sleep(wait_seconds)
        return verify()
