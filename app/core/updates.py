"""The update notice (Bauplan §37.2).

A notice, not an automatic update: the application asks a version file and
points at the download page. It never downloads anything, never runs anything,
and never replaces itself — a program that updates itself is a program that can
break itself while nobody is watching.

The check is off unless someone switches it on. It is one request to one
address, and asking is the only thing it does, but it is still a request that
leaves the machine — so it is a decision, not a default.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

from app.branding import APP_VERSION
from app.core.backends.llm import Transport
from app.core.log import get_logger

_log = get_logger(__name__)

#: Where the version file lives. One address, one JSON object.
VERSION_URL: Final = "https://formwerk.rsdigital.de/version.json"

#: How long the check may take. It happens at start; nobody waits for it.
TIMEOUT_SECONDS: Final = 4.0


@dataclass(frozen=True, slots=True)
class Release:
    """What the version file says."""

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
    """Ask once. Any problem means "no answer", never an error dialog.

    An update notice that interrupts the start because a server was down would
    be worse than no notice at all.
    """
    try:
        payload = (fetch or _get)(url, {}, {})
    except Exception as problem:  # a network fails in many ways, none of them ours
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
