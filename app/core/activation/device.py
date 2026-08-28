"""Die Geräteidentität im Schlüsselbund des Betriebssystems.

Der private Teil wird beim ersten ausdrücklichen Aktivierungsversuch zufällig
erzeugt und ausschließlich über ``keyring`` abgelegt. Es gibt absichtlich
keinen Rückfall auf eine Datei oder eine Umgebungsvariable: Beides ließe sich
zusammen mit dem Geräte-Zertifikat kopieren und machte aus der Bindung nur
eine zweite Datei.

Der Programmstart erzeugt nichts und öffnet auch keinen Schlüsselbund. Erst
eine Aktivierungsanforderung ruft :func:`ensure_public_key` oder :func:`sign`
auf. Eine bereits aktivierte Installation liest den privaten Teil lokal; sie
fragt niemals den Aktivierungsdienst.
"""

from __future__ import annotations

import secrets
from typing import ClassVar, Protocol

from app.core.activation import ed25519
from app.core.errors import CANCEL, REPORT_ERROR, RETRY, Action, UserError
from app.i18n import TranslatableText, _

SERVICE = "de.rsdigital.solidon3d.activation"
ACCOUNT = "device-seed-v1"


class _Keyring(Protocol):
    def get_password(self, service: str, account: str) -> str | None: ...

    def set_password(self, service: str, account: str, password: str) -> None: ...

    def delete_password(self, service: str, account: str) -> None: ...


class DeviceIdentityError(UserError):
    """Der sichere Ablageort der Geräteidentität ist nicht verwendbar."""

    default_title: ClassVar[TranslatableText] = _(
        "Die Geräteidentität ließ sich nicht sicher ablegen."
    )
    default_suggestions: ClassVar[tuple[Action, ...]] = (
        RETRY,
        REPORT_ERROR,
        CANCEL,
    )


def _load_keyring() -> _Keyring:
    """Lädt den System-Schlüsselbund erst, wenn er wirklich gebraucht wird."""
    try:
        import keyring
    except ImportError as problem:
        raise DeviceIdentityError(
            detail=_(
                "Der Zugang zum Schlüsselbund des Betriebssystems fehlt. "
                "Installieren Sie Solidon vollständig neu oder wenden Sie sich an den Support."
            )
        ) from problem
    return keyring


def _read_seed(*, strict: bool) -> bytes | None:
    try:
        text = _load_keyring().get_password(SERVICE, ACCOUNT)
    except DeviceIdentityError:
        if strict:
            raise
        return None
    except Exception as problem:
        if strict:
            raise DeviceIdentityError(
                detail=_(
                    "Der Schlüsselbund des Betriebssystems ist gesperrt oder nicht erreichbar."
                )
            ) from problem
        return None
    if text is None:
        return None
    try:
        seed = bytes.fromhex(text)
    except ValueError as problem:
        if strict:
            raise DeviceIdentityError(
                detail=_(
                    "Die gespeicherte Geräteidentität ist beschädigt. "
                    "Der Support kann die bisherige Aktivierung zurücksetzen."
                )
            ) from problem
        return None
    if len(seed) != ed25519.POINT_BYTES:
        if strict:
            raise DeviceIdentityError(
                detail=_(
                    "Die gespeicherte Geräteidentität ist unvollständig. "
                    "Der Support kann die bisherige Aktivierung zurücksetzen."
                )
            )
        return None
    return seed


def _ensure_seed() -> bytes:
    seed = _read_seed(strict=True)
    if seed is not None:
        return seed
    seed = secrets.token_bytes(ed25519.POINT_BYTES)
    try:
        keyring = _load_keyring()
        keyring.set_password(SERVICE, ACCOUNT, seed.hex())
        if keyring.get_password(SERVICE, ACCOUNT) != seed.hex():
            raise RuntimeError("der Schlüsselbund hat den Geräteteil nicht zurückgegeben")
    except DeviceIdentityError:
        raise
    except Exception as problem:
        raise DeviceIdentityError(
            detail=_(
                "Der Schlüsselbund des Betriebssystems hat die Geräteidentität "
                "nicht dauerhaft angenommen."
            )
        ) from problem
    return seed


def public_key() -> bytes | None:
    """Der vorhandene öffentliche Geräteteil, ohne etwas anzulegen."""
    seed = _read_seed(strict=False)
    return ed25519.public_key(seed) if seed is not None else None


def ensure_public_key() -> bytes:
    """Der öffentliche Geräteteil; legt die Identität nötigenfalls an."""
    return ed25519.public_key(_ensure_seed())


def sign(message: bytes) -> tuple[bytes, bytes]:
    """Signiert mit dem lokalen Geräteteil und gibt öffentlich + Signatur zurück."""
    seed = _ensure_seed()
    return ed25519.public_key(seed), ed25519.sign(seed, message)
