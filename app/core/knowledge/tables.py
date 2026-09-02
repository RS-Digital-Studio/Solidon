"""Eine TOML-Tabelle lesen, die auch von Hand geschrieben sein kann.

Drei Leser in diesem Paket taten dasselbe mit je eigenem Titel: Profile,
Druckeinstellungen und Kalibrierung lesen die mitgelieferte Datei **und** die
des Nutzers, und die zweite ist handgeschrieben. Eine fehlende Klammer darin
war jeweils ein Startabbruch mit rohem Stapelabzug — `printer_profiles()`
läuft beim Fensteraufbau —, bis jeder Leser für sich den Fehler in einen Satz
mit Dateinamen übersetzte (Regel 17, §33.1). Dreimal derselbe Rumpf; hier
steht er einmal, der Titel bleibt beim Aufrufer, weil nur er weiß, was für eine
Datei das war.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from app.core.errors import ValidationError
from app.i18n import TranslatableText


def read_table(path: Path, *, title: TranslatableText) -> dict[str, Any]:
    """Liest ``path`` als TOML; ein Syntaxfehler wird ein Satz mit Dateinamen.

    ``title`` nennt die Datei so, wie der Nutzer sie kennt („Diese Profildatei
    lässt sich nicht lesen."); der Grund kommt vom Parser und steht im Detail.
    """
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except tomllib.TOMLDecodeError as problem:
        raise ValidationError(
            title=title,
            field="file",
            detail=str(problem),
            constraint="toml",
            values={"file": str(path)},
        ) from problem
