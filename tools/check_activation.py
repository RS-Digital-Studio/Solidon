"""Prüft die öffentliche Bereitschaft des Aktivierungsdienstes.

Das Werkzeug sendet weder Kaufcode noch Gerätekennung. Es liest ausschließlich
den passiven Bereitschaftsendpunkt und eignet sich damit für die Handprobe vor
einem Upload oder nach einer Serverwartung.
"""

from __future__ import annotations

import argparse
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from app.core.http import (
    HttpBoundaryError,
    RejectRedirects,
    ResponseDeadlineError,
    ResponseTooLargeError,
    deadline_after,
    is_private_destination,
    read_limited,
    response_url,
    same_origin,
    validate_http_url,
)
from app.core.json_boundary import StrictJsonError
from app.core.json_boundary import loads as load_json
from app.core.log import redact_external

DEFAULT_URL = "https://solidon3d.de/api/activation-health.php"
TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 4096
_HEALTH_OPENER = build_opener(RejectRedirects())


def _checked_url(url: str) -> str:
    """HTTPS nach außen, HTTP ausschließlich zu einem ausdrücklich lokalen Ziel."""
    checked = validate_http_url(
        url,
        allow_http=True,
        allow_query=False,
        allow_fragment=False,
    )
    if urlsplit(checked).scheme == "http" and not is_private_destination(checked):
        raise ValueError("remote health endpoint requires HTTPS")
    return checked


def check(url: str) -> tuple[bool, str]:
    """Liest den Status und gibt Erfolg plus einen kurzen deutschen Befund zurück."""
    try:
        address = _checked_url(url)
    except ValueError:
        return False, "Bereitschaftsendpunkt ist keine sichere Adresse."
    deadline = deadline_after(TIMEOUT_SECONDS)
    request = Request(
        address,
        headers={"Accept": "application/json", "User-Agent": "Solidon3D-Health/1"},
        method="GET",
    )
    try:
        with _HEALTH_OPENER.open(request, timeout=TIMEOUT_SECONDS) as response:
            final = _checked_url(response_url(response, address))
            if not same_origin(address, final):
                return False, "Aktivierungsdienst hat unerwartet weitergeleitet."
            body = read_limited(
                response,
                limit=MAX_RESPONSE_BYTES,
                deadline=deadline,
            )
    except HTTPError as problem:
        problem.close()
        return False, f"Aktivierungsdienst antwortet mit HTTP {problem.code}."
    except ResponseTooLargeError:
        return False, "Aktivierungsdienst sendet eine ungewöhnlich große Antwort."
    except HttpBoundaryError:
        return False, "Aktivierungsdienst sendet keine sicher lesbare Antwort."
    except (URLError, TimeoutError, OSError, ResponseDeadlineError) as problem:
        return (
            False,
            f"Aktivierungsdienst ist nicht erreichbar: {redact_external(problem, limit=160)}",
        )
    try:
        answer = load_json(body, max_bytes=MAX_RESPONSE_BYTES)
    except StrictJsonError:
        return False, "Aktivierungsdienst sendet kein lesbares JSON."
    if answer != {"ok": True, "protocol": 1}:
        return False, "Aktivierungsdienst meldet sich, ist aber nicht einsatzbereit."
    return True, "Aktivierungsdienst ist bereit (Protokoll 1)."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="Bereitschaftsendpunkt")
    arguments = parser.parse_args(argv)
    ready, message = check(arguments.url)
    print(message)
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
