"""Wo der eigene Schlüssel des Nutzers liegt (Bauplan §27).

Im System-Schlüsselbund, und sonst nirgends: nicht in der Projektdatei, nicht
in den Einstellungen, nicht in einer Punktdatei neben den Modellen. Eine
Projektdatei wird als Fehlerbericht herumgereicht (§37.2), und ein Schlüssel,
der mitgereist wäre, wäre weg.

``keyring`` ist optional. Ohne es lässt sich der Schlüssel weiterhin über die
Umgebung übergeben — nützlich auf einem Bauserver — und die Oberfläche sagt,
welches von beiden sie gefunden hat, statt einen Schlüsselbund vorzutäuschen.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Any, Final

from app.branding import ENVIRONMENT_PREFIX
from app.core.keyring_backend import find_backend_once
from app.core.log import get_logger
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Unter welchem Namen der Schlüssel im Schlüsselbund abgelegt ist.
SERVICE = "solidon-llm"

#: Rückfall für Rechner ohne Schlüsselbund, etwa einen Bauserver.
ENVIRONMENT_VARIABLE = f"{ENVIRONMENT_PREFIX}_LLM_KEY"


def _keyring() -> Any | None:
    try:
        import keyring
    except Exception:  # pragma: no cover - hängt an der Installation
        return None
    try:
        find_backend_once(keyring)
    except Exception as error:
        # Das eingestellte Backend ist hier nicht nutzbar: derselbe Fall wie
        # ein gesperrter Schlüsselbund in `read` — kein Schlüssel von dort,
        # kein Absturz.
        _log.warning("keychain unreachable: %s", error)
        return None
    return keyring


def read(account: str) -> str | None:
    """Der Schlüssel eines Backends, aus dem Schlüsselbund oder der Umgebung."""
    import os

    keychain = _keyring()
    if keychain is not None:
        try:
            stored = keychain.get_password(SERVICE, account)
        except Exception as error:  # pragma: no cover - gesperrter oder fehlender Schlüsselbund
            _log.warning("keychain unreachable: %s", error)
            stored = None
        if stored:
            return str(stored)

    value = os.environ.get(f"{ENVIRONMENT_VARIABLE}_{account.upper()}") or os.environ.get(
        ENVIRONMENT_VARIABLE
    )
    return value or None


def unusable(key: str) -> TranslatableText | None:
    """Was an diesem Schlüssel nicht geht — ``None``, wenn nichts.

    **Ein Schlüssel wird ein HTTP-Header, und ein Header verträgt nicht
    alles.** Am 24.08.2026 hat ein Kunde die Fehlermeldung eines
    fehlgeschlagenen Zuges samt der Knopfbeschriftung darunter markiert und in
    dieses Feld eingefügt. Sie wurde ungeprüft gespeichert und flog beim
    nächsten Zug als ``ValueError`` aus ``http.client.putheader`` — als
    „Im Programm ist ein unerwarteter Fehler aufgetreten", mit der Bitte um
    einen Fehlerbericht, für einen Tippfehler (Regel 17).

    Geprüft wird deshalb dort, wo der Wert hereinkommt, und nicht dort, wo er
    explodiert.
    """
    if not key.strip():
        return _("Das Feld ist leer. Tragen Sie den Schlüssel Ihres Anbieters ein.")
    if key.strip() != key.strip().splitlines()[0]:
        return _(
            "Der Schlüssel geht über mehrere Zeilen. Wahrscheinlich ist mehr "
            "hineingeraten als der Schlüssel selbst — fügen Sie nur die eine "
            "Zeile ein, die Ihr Anbieter Ihnen genannt hat."
        )
    try:
        # **Latin-1 und nicht ASCII**, denn das ist die Grenze, an der es
        # wirklich bricht: ``http.client`` kodiert Kopfzeilen so, und was
        # darin liegt, geht durch. Ein Umlaut wirft also nichts — ein
        # Gedankenstrich oder ein typografisches Anführungszeichen schon, und
        # genau die bringt ein kopierter Text mit.
        key.strip().encode("latin-1")
    except UnicodeEncodeError:
        return _(
            "Der Schlüssel enthält Zeichen, die kein Anbieter vergibt — etwa "
            "Gedankenstriche oder typografische Anführungszeichen aus einem "
            "kopierten Text. Fügen Sie nur die Zeichenfolge ein, die Ihr "
            "Anbieter Ihnen genannt hat."
        )
    return None


def store(account: str, key: str) -> bool:
    """Legt einen Schlüssel in den Schlüsselbund. False, wenn es keinen gibt,
    in den er passte — oder wenn der Schlüssel keiner sein kann
    (:func:`unusable`). Warum, sagt :func:`store_refusal`.
    """
    return store_refusal(account, key) is None


def _no_keychain() -> TranslatableText:
    """Auf diesem Rechner gibt es keinen Schlüsselbund — der Weg über die Umgebung."""
    return _(
        "Auf diesem Rechner gibt es keinen Schlüsselbund. Tragen Sie den Schlüssel "
        "in die Umgebungsvariable {variable} ein und starten Sie das Programm neu.",
        variable=ENVIRONMENT_VARIABLE,
    )


def _keychain_unreachable() -> TranslatableText:
    """Es gibt einen Schlüsselbund, aber er nimmt nichts an — gesperrt oder nicht erreichbar."""
    return _(
        "Der Schlüsselbund ist gesperrt oder nicht erreichbar. Entsperren Sie ihn und "
        "speichern Sie erneut, oder tragen Sie den Schlüssel in die Umgebungsvariable "
        "{variable} ein und starten Sie das Programm neu.",
        variable=ENVIRONMENT_VARIABLE,
    )


def _keyring_installed() -> bool:
    """Ob ``keyring`` überhaupt da ist — ohne den Schlüsselbund zu fragen."""
    from importlib.util import find_spec

    try:
        return find_spec("keyring") is not None
    except ValueError:  # schon geladen, aber ohne Modulbeschreibung
        return True


def store_refusal(account: str, key: str) -> TranslatableText | None:
    """Legt einen Schlüssel in den Schlüsselbund — ``None``, wenn er drin ist,
    sonst der tatsächliche Grund mit dem Weg, der bleibt (Regel 17).

    Drei Gründe, drei Sätze: Der Schlüssel kann keiner sein (:func:`unusable`);
    es gibt keinen Schlüsselbund (``keyring`` fehlt, oder es fand kein Backend
    — ``NoKeyringError``); es gibt einen, aber er ist gesperrt oder nicht
    erreichbar. Bis dahin hieß jeder Fehlschlag „Auf diesem Rechner gibt es
    keinen Schlüsselbund", auch über einem gesperrten, und die Variable
    stand nirgends.

    **Der Wert wird beschnitten, bevor er hineingeht.** Ein an der
    Zwischenablage hängengebliebenes Leerzeichen ist der häufigste Grund für
    einen Schlüssel, der „nicht geht", und niemand sieht es ihm an.
    """
    key = key.strip()
    refusal = unusable(key)
    if refusal is not None:
        _log.warning("refused a key for %s: it cannot be a key", account)
        return refusal
    keychain = _keyring()
    if keychain is None:
        # Ist ``keyring`` da, scheiterte seine Backend-Suche (:func:`_keyring`
        # hat es protokolliert): Das eingestellte Backend geht hier nicht.
        return _keychain_unreachable() if _keyring_installed() else _no_keychain()
    try:
        keychain.set_password(SERVICE, account, key)
    except Exception as error:  # pragma: no cover - gesperrter Schlüsselbund
        # Derselbe Rahmen wie in `read`: ein gesperrter Schlüsselbund — etwa
        # ein Linux ohne laufenden Secret-Service — ist ein Nein, kein
        # Absturz. Die Ausnahme flog sonst aus dem Qt-Slot des
        # Einstellungsdialogs, der nur den Rückgabewert behandelt.
        _log.warning("keychain refused the key: %s", error)
        # Beim Namen gefragt: Wer ``keyring`` hier ersetzt, hat dessen
        # Fehlerklassen nicht, und ohne Backend wirft es genau diese.
        if any(kind.__name__ == "NoKeyringError" for kind in type(error).__mro__):
            return _no_keychain()
        return _keychain_unreachable()
    _log.info("key for %s stored in the keychain", account)
    # Ein neuer Schlüssel ist ein neuer Versuch: Was die Gegenseite vorhin
    # abgelehnt hat, war ein anderer Schlüssel. Der Import steht im Aufruf,
    # weil :mod:`app.core.backends.llm` diese Datei benutzt und nicht umgekehrt.
    from app.core.backends import llm

    llm.accept_again(account)
    return None


def forget(account: str) -> bool:
    """Entfernt einen Schlüssel wieder — das eine, was ein
    Einstellungsdialog können muss.
    """
    keychain = _keyring()
    if keychain is None:
        return False
    try:
        keychain.delete_password(SERVICE, account)
    except Exception:  # pragma: no cover - nichts gespeichert
        return False
    return True


def source(account: str) -> str:
    """Woher der Schlüssel kam, für den Einstellungsdialog: Schlüsselbund,
    Umgebung, keiner.
    """
    import os

    keychain = _keyring()
    if keychain is not None:
        try:
            if keychain.get_password(SERVICE, account):
                return "keychain"
        except Exception:  # pragma: no cover - gesperrter Schlüsselbund
            pass
    if os.environ.get(f"{ENVIRONMENT_VARIABLE}_{account.upper()}") or os.environ.get(
        ENVIRONMENT_VARIABLE
    ):
        return "environment"
    return "none"


# --- ein als ungültig abgelehnter Schlüssel --------------------------------------

#: Wie lange ein Schlüssel übergangen wird, den der Anbieter als ungültig
#: abgelehnt hat (401).
#:
#: Ohne Merker scheiterte bei jedem Start der erste Chatzug am selben Schlüssel
#: (S-20261010-e5014c, dreimal an einem Abend). Ohne Ablauf aber wäre die
#: Sperre endgültig, und ob ein 401 heilt, entscheidet der Anbieter: ein
#: wieder freigeschalteter Schlüssel, eine Störung der Anmeldung, eine
#: Zwischenstelle, die 401 schickt. Ein Tag hält den Chat für die Sitzungen
#: eines Abends frei vom selben Fehler und gibt dem Schlüssel am nächsten Tag
#: von selbst eine neue Chance (Entscheidung Koordinator, Review agentlog M2).
#: Früher geht es über „Noch einmal versuchen“ oder einen anderen Schlüssel.
REFUSAL_HOLDS_SECONDS: Final = 24 * 3600.0

#: Wo der Merker liegt — im Nutzerordner (§38), getrennt von den gemerkten
#: Programmen, deren Schreiben protokolliert wird und die Programmsuche leert.
REFUSALS_FILE: Final = "refused_keys.json"


def _refusals_path() -> Path:
    from app.core.paths import user_config_dir

    return user_config_dir() / REFUSALS_FILE


def _load_refusals() -> dict[str, Any]:
    path = _refusals_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError) as problem:
        _log.warning("could not read %s, ignoring it: %s", REFUSALS_FILE, problem)
        return {}
    return data if isinstance(data, dict) else {}


def _store_refusals(data: dict[str, Any]) -> None:
    from app.core.paths import ensure_dir

    path = _refusals_path()
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


#: Konten, deren Merker diese Sitzung geschrieben hat — für ``llm.accept_again``
#: ohne Namen, das sonst bei jedem Aufruf die Datei läse.
_marked: set[str] = set()


def marked_here() -> frozenset[str]:
    """Welche Konten diese Sitzung als abgelehnt gemerkt hat."""
    return frozenset(_marked)


def _salt_of(data: dict[str, Any]) -> str:
    """Das Salz der Datei — oder leer, wenn es keines oder ein beschädigtes ist."""
    salt = data.get("salt")
    if not isinstance(salt, str) or len(salt) != 32:
        return ""
    try:
        bytes.fromhex(salt)
    except ValueError:
        return ""
    return salt


def _fingerprint(key: str, salt: str) -> str:
    """HMAC-SHA256 mit einem Salz je Installation — wiedererkennbar, nicht der
    Schlüssel selbst.

    Was das Salz leistet und was nicht: Es macht vorberechnete Tabellen
    nutzlos, denn jeder Rechner hat ein anderes. Es steht aber in derselben
    Datei wie der Abdruck — wer die Datei hat, kann einen **kurzen** Schlüssel
    durchprobieren. Ein Anthropic-Schlüssel (rund 90 Zufallszeichen) ist so
    nicht zu finden. Die Datei bleibt im Nutzerordner, reist mit keinem
    Projekt und keinem Fehlerbericht und wird nicht protokolliert.
    """
    return hmac.new(bytes.fromhex(salt), key.encode("utf-8"), hashlib.sha256).hexdigest()


def mark_refused(account: str, key: str, now: float | None = None) -> None:
    """Merken, dass der Anbieter genau diesen Schlüssel abgelehnt hat.

    **Buchhaltung, kein Vorgang:** Ein Schreibfehler am Merker wird
    protokolliert und verschluckt — sonst machte ein schreibgeschützter
    Nutzerordner aus dem 401 einen Programmfehler statt eines Satzes mit Ausweg.
    """
    data = _load_refusals()
    salt = _salt_of(data) or secrets.token_hex(16)
    data["salt"] = salt
    data[account] = {
        "mark": _fingerprint(key, salt),
        "at": time.time() if now is None else now,
    }
    try:
        _store_refusals(data)
    except OSError as problem:
        _log.warning("could not remember the refused %s key: %s", account, problem)
        return
    _marked.add(account)
    _log.info("%s key marked as refused", account)


def refused(account: str, key: str, now: float | None = None) -> bool:
    """Ob genau dieser Schlüssel als ungültig gemerkt ist und die Frist noch läuft."""
    data = _load_refusals()
    entry = data.get(account)
    salt = _salt_of(data)
    if not isinstance(entry, dict) or not salt:
        return False
    # Die Datei liegt im Nutzerordner und kann von Hand beschädigt sein. Ein
    # kaputter Eintrag zählt als nicht gesperrt — er darf ``available`` nie
    # werfen lassen: ``compare_digest`` lehnt Nicht-ASCII mit ``TypeError`` ab,
    # ``float`` eine riesige Ganzzahl mit ``OverflowError``.
    mark = entry.get("mark")
    if not isinstance(mark, str) or not _is_fingerprint(mark):
        return False
    at = entry.get("at")
    if not isinstance(at, int | float) or isinstance(at, bool):
        return False
    try:
        elapsed = (time.time() if now is None else now) - float(at)
    except OverflowError:
        return False
    if not 0.0 <= elapsed < REFUSAL_HOLDS_SECONDS:
        return False
    return hmac.compare_digest(mark, _fingerprint(key, salt))


def _is_fingerprint(mark: str) -> bool:
    """Ob ``mark`` aussieht wie ein Abdruck aus :func:`_fingerprint` (64 Hexziffern)."""
    return len(mark) == 64 and all(sign in "0123456789abcdef" for sign in mark)


def clear_refusal(account: str) -> None:
    """Den Merker aufheben — beim Eintragen eines Schlüssels und über „Noch
    einmal versuchen“. Ein Schreibfehler bleibt Buchhaltung (:func:`mark_refused`)."""
    _marked.discard(account)
    data = _load_refusals()
    if account not in data:
        return
    del data[account]
    try:
        _store_refusals(data)
    except OSError as problem:
        _log.warning("could not clear the refused %s key: %s", account, problem)
