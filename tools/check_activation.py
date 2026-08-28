"""Prüft die öffentliche Bereitschaft des Aktivierungsdienstes.

Das Werkzeug sendet weder Kaufcode noch Gerätekennung. Es liest ausschließlich
den passiven Bereitschaftsendpunkt und eignet sich damit für die Handprobe vor
einem Upload oder nach einer Serverwartung.
"""

from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_URL = "https://solidon3d.de/api/activation-health.php"
TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 4096


def check(url: str) -> tuple[bool, str]:
    """Liest den Status und gibt Erfolg plus einen kurzen deutschen Befund zurück."""
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "Solidon3D-Health/1"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as problem:
        return False, f"Aktivierungsdienst antwortet mit HTTP {problem.code}."
    except (URLError, TimeoutError, OSError) as problem:
        return False, f"Aktivierungsdienst ist nicht erreichbar: {problem}"
    if len(body) > MAX_RESPONSE_BYTES:
        return False, "Aktivierungsdienst sendet eine ungewöhnlich große Antwort."
    try:
        answer = json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError):
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
