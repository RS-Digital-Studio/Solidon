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
VERSION_URL: Final = "https://formwerk.rs-digital.org/version.json"

#: Wie lange die Prüfung dauern darf. Sie läuft beim Start; niemand wartet
#: auf sie.
TIMEOUT_SECONDS: Final = 4.0

#: Wie viel von der Antwort überhaupt gelesen wird.
#:
#: Das Zeitlimit deckelt die einzelne Socket-Operation, nicht die Menge: eine
#: Gegenstelle, die zügig und endlos liefert, füllte sonst beim Start den
#: Arbeitsspeicher. Die Datei trägt drei kurze Felder; alles darüber ist keine
#: Versionsdatei mehr.
MAX_ANSWER_BYTES: Final = 64 * 1024

#: Wie lang die einzelnen Felder werden dürfen. Sie landen in der Statusleiste,
#: und was dort steht, kommt von einem Server — nicht aus diesem Programm.
MAX_FIELD_LENGTH: Final = 200


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

    version = _field(payload.get("version"))
    if not version:
        return None
    url = _field(payload.get("url"))
    return Release(
        version=version,
        # Angezeigt wird nur, was auch anklickbar wäre. Ein „url", das keine
        # ist, war entweder nie eine oder soll etwas anderes sein als eine
        # Adresse — beides gehört nicht in die Statusleiste.
        url=url if url.startswith("https://") else "",
        notes=_field(payload.get("notes")),
    )


def _field(value: object) -> str:
    """Ein Feld aus der Antwort, gestutzt auf das, was hineinpasst."""
    return str(value if value is not None else "").strip()[:MAX_FIELD_LENGTH]


def _get(url: str, headers: dict[str, str], _payload: dict[str, Any]) -> dict[str, Any]:
    import urllib.request

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:
        # Ein Byte mehr als erlaubt wird noch gelesen, damit „zu lang" von
        # „gerade noch" unterscheidbar bleibt.
        raw = answer.read(MAX_ANSWER_BYTES + 1)
    if len(raw) > MAX_ANSWER_BYTES:
        raise ValueError("version file is too large")
    return dict(json.loads(raw.decode("utf-8")))
