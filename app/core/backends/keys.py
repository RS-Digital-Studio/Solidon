"""Wo der eigene Schlüssel des Nutzers liegt (Bauplan §27).

Im System-Schlüsselbund, und sonst nirgends: nicht in der Projektdatei, nicht
in den Einstellungen, nicht in einer Punktdatei neben den Modellen. Eine
Projektdatei wird als Fehlerbericht herumgereicht (§33.3), und ein Schlüssel,
der mitgereist wäre, wäre weg.

``keyring`` ist optional. Ohne es lässt sich der Schlüssel weiterhin über die
Umgebung übergeben — nützlich auf einem Bauserver — und die Oberfläche sagt,
welches von beiden sie gefunden hat, statt einen Schlüsselbund vorzutäuschen.
"""

from __future__ import annotations

from typing import Any

from app.branding import ENVIRONMENT_PREFIX
from app.core.log import get_logger

_log = get_logger(__name__)

#: Unter welchem Namen der Schlüssel im Schlüsselbund abgelegt ist.
SERVICE = "formwerk-llm"

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


def store(account: str, key: str) -> bool:
    """Legt einen Schlüssel in den Schlüsselbund. False, wenn es keinen gibt,
    in den er passte.
    """
    keychain = _keyring()
    if keychain is None:
        return False
    keychain.set_password(SERVICE, account, key)
    _log.info("key for %s stored in the keychain", account)
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
    except Exception:  # pragma: no cover - nothing stored
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
        except Exception:  # pragma: no cover - locked keychain
            pass
    if os.environ.get(f"{ENVIRONMENT_VARIABLE}_{account.upper()}") or os.environ.get(
        ENVIRONMENT_VARIABLE
    ):
        return "environment"
    return "none"
