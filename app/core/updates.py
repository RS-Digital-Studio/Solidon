"""Der Update-Hinweis (Bauplan §37.2).

Ein Hinweis, kein automatisches Update: die Anwendung fragt eine Versionsdatei
und zeigt auf die Download-Seite. Sie lädt nie etwas herunter, führt nie etwas
aus und ersetzt sich nie selbst — ein Programm, das sich selbst aktualisiert,
ist eines, das sich kaputtmachen kann, während niemand hinsieht.

Die Prüfung ist aus, bis jemand sie einschaltet. Es ist eine Anfrage an eine
Adresse, und Fragen ist alles, was sie tut — aber es bleibt eine Anfrage, die
den Rechner verlässt. Also ist sie eine Entscheidung, keine Vorgabe.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

from app.branding import APP_VERSION
from app.core.backends.llm import Transport
from app.core.log import get_logger

_log = get_logger(__name__)

#: Wo die Versionsdatei liegt. Eine Adresse, ein JSON-Objekt.
VERSION_URL: Final = "https://formwerk.rsdigital.de/version.json"

#: Wie lange die Prüfung dauern darf. Sie läuft beim Start; niemand wartet
#: auf sie.
TIMEOUT_SECONDS: Final = 4.0


@dataclass(frozen=True, slots=True)
class Release:
    """Was die Versionsdatei sagt."""

    version: str
    url: str = ""
    notes: str = ""

    def newer_than(self, current: str = APP_VERSION) -> bool:
        return _as_tuple(self.version) > _as_tuple(current)


def _as_tuple(version: str) -> tuple[int, ...]:
    parts = []
    for piece in version.split("."):
        digits = "".join(character for character in piece if character.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check(url: str = VERSION_URL, fetch: Transport | None = None) -> Release | None:
    """Fragt einmal. Jedes Problem heißt „keine Antwort", nie ein Fehlerdialog.

    Ein Update-Hinweis, der den Start unterbricht, weil ein Server nicht
    erreichbar war, wäre schlimmer als gar keiner.
    """
    try:
        payload = (fetch or _get)(url, {}, {})
    except Exception as problem:  # ein Netz scheitert auf viele Arten, keine davon ist unsere
        _log.info("update check did not answer: %s", problem)
        return None

    version = str(payload.get("version", "")).strip()
    if not version:
        return None
    return Release(
        version=version,
        url=str(payload.get("url", "")),
        notes=str(payload.get("notes", "")),
    )


def _get(url: str, headers: dict[str, str], _payload: dict[str, Any]) -> dict[str, Any]:
    import urllib.request

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:
        return dict(json.loads(answer.read().decode("utf-8")))
