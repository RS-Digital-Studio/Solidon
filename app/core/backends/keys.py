"""Where the user's own key lives (Bauplan §27).

The system keychain, and nowhere else: not in the project file, not in the
settings, not in a dotfile next to the models. A project file is handed around
as a bug report (§33.3), and a key that travelled with it would be gone.

``keyring`` is optional. Without it the key can still be handed over through the
environment — useful on a build server — and the surface says which of the two
it found rather than pretending there is a keychain.
"""

from __future__ import annotations

from typing import Any

from app.branding import ENVIRONMENT_PREFIX
from app.core.log import get_logger

_log = get_logger(__name__)

#: Name the key is filed under in the keychain.
SERVICE = "formwerk-llm"

#: Fallback for machines without a keychain, e.g. a build server.
ENVIRONMENT_VARIABLE = f"{ENVIRONMENT_PREFIX}_LLM_KEY"


def _keyring() -> Any | None:
    try:
        import keyring
    except Exception:  # pragma: no cover - depends on the installation
        return None
    return keyring


def available() -> bool:
    """Whether a keychain can be reached at all."""
    return _keyring() is not None


def read(account: str) -> str | None:
    """The key for one backend, from the keychain or the environment."""
    import os

    keychain = _keyring()
    if keychain is not None:
        try:
            stored = keychain.get_password(SERVICE, account)
        except Exception as error:  # pragma: no cover - locked or missing keychain
            _log.warning("keychain unreachable: %s", error)
            stored = None
        if stored:
            return str(stored)

    value = os.environ.get(f"{ENVIRONMENT_VARIABLE}_{account.upper()}") or os.environ.get(
        ENVIRONMENT_VARIABLE
    )
    return value or None


def store(account: str, key: str) -> bool:
    """Put a key into the keychain. False when there is none to put it in."""
    keychain = _keyring()
    if keychain is None:
        return False
    keychain.set_password(SERVICE, account, key)
    _log.info("key for %s stored in the keychain", account)
    return True


def forget(account: str) -> bool:
    """Remove a key again — the one thing a settings dialog must be able to do."""
    keychain = _keyring()
    if keychain is None:
        return False
    try:
        keychain.delete_password(SERVICE, account)
    except Exception:  # pragma: no cover - nothing stored
        return False
    return True


def source(account: str) -> str:
    """Where the key came from, for the settings dialog: keychain, environment, none."""
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
