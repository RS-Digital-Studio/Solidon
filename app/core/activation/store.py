"""Wo der Lizenzschlüssel liegt und wie der Testlauf gezählt wird (§38).

**Als Datei, nicht im Schlüsselbund** — anders als der API-Schlüssel des
Nutzers (``backends/keys.py``). Zwei Gründe, und beide wiegen mehr als das
Gefühl, ein Schlüsselbund sei immer sicherer: der Lizenzschlüssel ist nicht
geheim, er ist personalisiert — wer ihn hat, hat auch den Namen darin. Und ein
Schlüsselbund kann gesperrt sein. Dann fragt das Betriebssystem beim Start nach
einem Passwort, und ein Lizenzschlüssel ist der falsche Anlass für diese Frage.

Der Testlaufmarker ist **absichtlich nicht versteckt**. Wer ihn löscht, hat
wieder vierzehn Tage. Ihn zu verstecken bräuchte Streuung über Registry und
verborgene Dateien — also genau das Verhalten, das Solidon seinen Nutzern
nirgends zumutet. Die Frist ist eine Erinnerung; die Schwelle für den
dauerhaften Gebrauch ist die Signatur, und die hält.

Eine zurückgestellte Systemuhr verlängert trotzdem nichts: gespeichert wird
auch der höchste je gesehene Tag, und die Frist läuft nie rückwärts. Ein Tag
weit jenseits des ersten Starts wird dabei verworfen und nicht festgeschrieben
— sonst nähme ein einziger Start mit falsch gestellter Uhr den Testlauf
dauerhaft weg, auch nachdem die Uhr wieder stimmt.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from app.core.log import get_logger
from app.core.paths import ensure_dir, user_config_dir

_log = get_logger(__name__)

#: Wie lange der Testlauf dauert. Steht so auf der Website.
TRIAL_DAYS: Final = 14

#: Letzter Tag der öffentlichen Demo — oder ``None`` in der Verkaufsversion,
#: die stattdessen den Testlauf zählt.
#:
#: Ein Stichtag statt einer Frist ab dem ersten Start: die Demo endet für alle
#: am selben Tag, der Tag selbst gehört noch dazu. Der Testlaufmarker verliert
#: damit seine Bedeutung — wer ihn löscht, gewinnt keinen Tag, und wer die Uhr
#: zurückstellt, verschiebt nur sein eigenes Kalenderblatt.
#:
#: Er steht hier und nicht in ``branding.py``, weil dieses Paket seit V4c mit
#: Cython übersetzt ausgeliefert wird: der Stichtag reist in der Erweiterung
#: statt als lesbare Zeile daneben. Öffnen kann er ohnehin nichts, was ein
#: Schlüssel nicht öffnete — er kann nur sperren.
DEMO_UNTIL: Final[date | None] = date(2026, 10, 30)

#: Dateiname des Schlüssels im Einstellungsordner.
KEY_FILE: Final = "licence.key"

#: Dateiname des Testlaufmarkers.
TRIAL_FILE: Final = "trial.json"

#: Ab welchem Abstand zum ersten Start ein gespeicherter Tag keine verstrichene
#: Zeit mehr sein kann, sondern eine falsch gestellte Uhr. Ein Jahr ist
#: großzügig genug, dass ein Nutzer, der Solidon nach Monaten wieder öffnet,
#: den Rückwärtsschutz behält.
CLOCK_HORIZON_DAYS: Final = 365


def key_path() -> Path:
    return user_config_dir() / KEY_FILE


def trial_path() -> Path:
    return user_config_dir() / TRIAL_FILE


def read_key() -> str | None:
    """Der abgelegte Schlüsseltext, oder ``None``.

    ``ValueError`` fängt den ``UnicodeDecodeError`` einer beschädigten Datei
    mit ab. Ohne ihn schlägt eine unlesbare ``licence.key`` bis in jede
    Dokumentänderung durch — und bis in den Dialog, mit dem sie zu ersetzen
    wäre.
    """
    path = key_path()
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return text or None


def write_key(text: str) -> bool:
    """Legt den Schlüssel ab. Geprüft wird vorher, nicht hier.

    ``False`` heißt: das Profil ist nicht beschreibbar. Kein Abbruch — der
    Schlüssel gilt dann für diese Sitzung, und der Dialog sagt, dass er beim
    nächsten Start wieder gebraucht wird. Ein Absturz beim Eintragen des
    bezahlten Schlüssels wäre die falsche Richtung des Fehlers.
    """
    try:
        ensure_dir(user_config_dir())
        key_path().write_text(text.strip(), encoding="utf-8")
    except OSError as problem:
        _log.warning("licence key could not be written: %s", problem)
        return False
    _log.info("licence key stored")
    return True


def forget_key() -> bool:
    """Entfernt den Schlüssel — das eine, was ein Einstellungsdialog können
    muss, etwa vor dem Verkauf des Rechners.

    ``missing_ok``, weil „es lag keiner da" das Ziel erreicht und kein
    Fehlschlag ist. ``False`` bleibt dem Fall vorbehalten, dass die Datei da
    ist und sich nicht entfernen lässt.
    """
    try:
        key_path().unlink(missing_ok=True)
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


def days_left(today: date | None = None) -> int:
    """Wie viele Tage die schreibende Seite noch offensteht. Null heißt zu.

    Die eine Stelle, an der sich Demo und Verkaufsversion unterscheiden: mit
    einem Stichtag zählt der Kalender, ohne ihn die Frist ab dem ersten Start.
    Alles darüber — die vier Grenzstellen, die ausgegraute Oberfläche, der
    Freischaltdialog — sieht in beiden Fällen dieselbe Zahl.
    """
    if DEMO_UNTIL is None:
        return trial_days_left(today)
    # Der Stichtag selbst gehört noch dazu: am 30.10. bleibt ein Tag übrig,
    # am 31.10. keiner. Die freundliche Richtung, und die, die auf der Website
    # steht („bis zum 30.10.").
    return max(0, (DEMO_UNTIL - (today or date.today())).days + 1)


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
    # Ein Tag jenseits des Horizonts ist keine verstrichene Zeit, sondern eine
    # leere BIOS-Batterie. Er wird verworfen statt festgeschrieben — sonst
    # kostet ein einziger Start mit falscher Uhr den ganzen Testlauf, und zwar
    # dauerhaft, weil er unten als höchster gesehener Tag zurückkäme. Wer die
    # Uhr absichtlich verstellt, kommt damit nicht weiter als der, der
    # ``trial.json`` löscht — und das ist oben ausdrücklich zugestanden.
    if last_seen > first_run + timedelta(days=CLOCK_HORIZON_DAYS):
        _log.warning("trial marker holds an implausible date, ignoring it: %s", last_seen)
        last_seen = max(now, first_run)
    # Die Uhr darf vorgehen, aber nicht zurück: sonst verlängert ein
    # zurückgedrehtes Systemdatum die Frist beliebig.
    effective = max(now, last_seen)
    if effective != stored[1]:
        _write_trial(first_run, effective)
    used = (effective - first_run).days
    return max(0, TRIAL_DAYS - used)
