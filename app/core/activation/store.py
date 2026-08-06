"""Wo der Lizenzschlüssel liegt und wie der Testlauf gezählt wird (§38).

**Als Datei, nicht im Schlüsselbund** — anders als der API-Schlüssel des
Nutzers (``backends/keys.py``). Zwei Gründe, und beide wiegen mehr als das
Gefühl, ein Schlüsselbund sei immer sicherer: der Lizenzschlüssel ist nicht
geheim, er ist personalisiert — wer ihn hat, hat auch den Namen darin. Und ein
Schlüsselbund kann gesperrt sein. Dann fragt das Betriebssystem beim Start nach
einem Passwort, und ein Lizenzschlüssel ist der falsche Anlass für diese Frage.

Der Testlaufmarker ist **absichtlich nicht versteckt**. Wer ihn löscht, hat
wieder vierzehn Tage. Ihn zu verstecken bräuchte Streuung über Registry und
verborgene Dateien — also genau das Verhalten, das Formwerk seinen Nutzern
nirgends zumutet. Die Frist ist eine Erinnerung; die Schwelle für den
dauerhaften Gebrauch ist die Signatur, und die hält.

Eine zurückgestellte Systemuhr verlängert trotzdem nichts: gespeichert wird
auch der höchste je gesehene Tag, und die Frist läuft nie rückwärts.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Final

from app.core.log import get_logger
from app.core.paths import ensure_dir, user_config_dir

_log = get_logger(__name__)

#: Wie lange der Testlauf dauert. Steht so auf der Website.
TRIAL_DAYS: Final = 14

#: Dateiname des Schlüssels im Einstellungsordner.
KEY_FILE: Final = "licence.key"

#: Dateiname des Testlaufmarkers.
TRIAL_FILE: Final = "trial.json"


def key_path() -> Path:
    return user_config_dir() / KEY_FILE


def trial_path() -> Path:
    return user_config_dir() / TRIAL_FILE


def read_key() -> str | None:
    """Der abgelegte Schlüsseltext, oder ``None``."""
    path = key_path()
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def write_key(text: str) -> None:
    """Legt den Schlüssel ab. Geprüft wird vorher, nicht hier."""
    ensure_dir(user_config_dir())
    key_path().write_text(text.strip(), encoding="utf-8")
    _log.info("licence key stored")


def forget_key() -> bool:
    """Entfernt den Schlüssel — das eine, was ein Einstellungsdialog können
    muss, etwa vor dem Verkauf des Rechners."""
    try:
        key_path().unlink()
    except OSError:
        return False
    return True


def _read_trial() -> tuple[date, date] | None:
    try:
        data = json.loads(trial_path().read_text(encoding="utf-8"))
        return date.fromisoformat(data["first_run"]), date.fromisoformat(data["last_seen"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write_trial(first_run: date, last_seen: date) -> None:
    try:
        ensure_dir(user_config_dir())
        trial_path().write_text(
            json.dumps({"first_run": first_run.isoformat(), "last_seen": last_seen.isoformat()}),
            encoding="utf-8",
        )
    except OSError as problem:
        # Ein schreibgeschütztes Profil heißt: der Testlauf beginnt bei jedem
        # Start neu. Das ist die freundliche Richtung des Fehlers, und ein
        # Abbruch wäre die falsche.
        _log.warning("trial marker could not be written: %s", problem)


def trial_days_left(today: date | None = None) -> int:
    """Wie viele Tage der Testlauf noch hat. Null heißt abgelaufen.

    Der erste Aufruf legt den Marker an — der Testlauf beginnt also beim ersten
    Start, nicht bei der Installation.
    """
    now = today or date.today()
    stored = _read_trial()
    if stored is None:
        _write_trial(now, now)
        return TRIAL_DAYS
    first_run, last_seen = stored
    # Die Uhr darf vorgehen, aber nicht zurück: sonst verlängert ein
    # zurückgedrehtes Systemdatum die Frist beliebig.
    effective = max(now, last_seen)
    if effective > last_seen:
        _write_trial(first_run, effective)
    used = (effective - first_run).days
    return max(0, TRIAL_DAYS - used)
