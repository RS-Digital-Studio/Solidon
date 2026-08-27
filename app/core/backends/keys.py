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

from typing import Any

from app.branding import ENVIRONMENT_PREFIX
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
    return keyring


def available() -> bool:
    """Ob überhaupt ein Schlüsselbund erreichbar ist."""
    return _keyring() is not None


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
    (:func:`unusable`).

    **Der Wert wird beschnitten, bevor er hineingeht.** Ein an der
    Zwischenablage hängengebliebenes Leerzeichen ist der häufigste Grund für
    einen Schlüssel, der „nicht geht", und niemand sieht es ihm an.
    """
    key = key.strip()
    if unusable(key) is not None:
        _log.warning("refused a key for %s: it cannot be a key", account)
        return False
    keychain = _keyring()
    if keychain is None:
        return False
    try:
        keychain.set_password(SERVICE, account, key)
    except Exception as error:  # pragma: no cover - gesperrter Schlüsselbund
        # Derselbe Rahmen wie in `read`: ein gesperrter Schlüsselbund — etwa
        # ein Linux ohne laufenden Secret-Service — ist ein Nein, kein
        # Absturz. Die Ausnahme flog sonst aus dem Qt-Slot des
        # Einstellungsdialogs, der nur den Rückgabewert behandelt.
        _log.warning("keychain refused the key: %s", error)
        return False
    _log.info("key for %s stored in the keychain", account)
    # Ein neuer Schlüssel ist ein neuer Versuch: Was die Gegenseite vorhin
    # abgelehnt hat, war ein anderer Schlüssel. Der Import steht im Aufruf,
    # weil :mod:`app.core.backends.llm` diese Datei benutzt und nicht umgekehrt.
    from app.core.backends import llm

    llm.accept_again(account)
    return True


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
