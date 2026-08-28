"""Der ausdrücklich ausgelöste Netzweg der Geräteaktivierung.

Der Freischaltzustand selbst importiert dieses Modul nicht. Damit bleibt der
Programmstart vollständig lokal: Erst der Klick auf „Online aktivieren“ ruft
:func:`activate` auf. Der Offline-Weg erzeugt dieselbe Anforderung, überträgt
sie aber als Datei und kommt ohne diese Verbindung aus.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import ClassVar, Final
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.errors import ACTIVATE_OFFLINE, CANCEL, REPORT_ERROR, RETRY, Action, AppError
from app.i18n import TranslatableText, _

ACTIVATION_URL: Final = "https://solidon3d.de/api/activation.php"
DEACTIVATION_URL: Final = "https://solidon3d.de/api/deactivation.php"
TIMEOUT_SECONDS: Final = 15.0
MAX_RESPONSE_BYTES: Final = 65536


class ActivationServiceError(AppError):
    """Der Online-Weg hat keine verwendbare Aktivierungsantwort geliefert."""

    default_title: ClassVar[TranslatableText] = _(
        "Die Verbindung zum Aktivierungsdienst ist nicht durchgelaufen."
    )
    default_suggestions: ClassVar[tuple[Action, ...]] = (
        RETRY,
        ACTIVATE_OFFLINE,
        REPORT_ERROR,
        CANCEL,
    )


def _response_body(response: object) -> bytes:
    """Liest eine kleine JSON-Antwort; der Dienst liefert nie große Dateien."""
    body = response.read(MAX_RESPONSE_BYTES + 1)  # type: ignore[attr-defined]
    if len(body) > MAX_RESPONSE_BYTES:
        raise ActivationServiceError(
            detail=_("Der Aktivierungsdienst hat eine ungewöhnlich große Antwort gesendet.")
        )
    return bytes(body)


def _post_to(url: str, payload: bytes) -> bytes:
    request = Request(
        url,
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Solidon3D-Activation/1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return _response_body(response)
    except HTTPError as problem:
        body = _response_body(problem)
        if body:
            return body
        raise ActivationServiceError(
            detail=_("Der Aktivierungsdienst hat die Anfrage abgelehnt.")
        ) from problem
    except (URLError, TimeoutError, OSError) as problem:
        raise ActivationServiceError(
            detail=_(
                "Der Aktivierungsdienst war nicht erreichbar. Prüfen Sie die Verbindung, "
                "versuchen Sie es erneut oder verwenden Sie die Offline-Aktivierung."
            )
        ) from problem


def _post(payload: bytes) -> bytes:
    return _post_to(ACTIVATION_URL, payload)


def _post_deactivation(payload: bytes) -> bytes:
    return _post_to(DEACTIVATION_URL, payload)


def _error_from(answer: dict[str, object]) -> ActivationServiceError:
    """Übersetzt stabile Serverkennungen; Serverprosa gelangt nie ungeprüft in die UI."""
    code = str(answer.get("code", ""))
    if code == "device_limit":
        detail = _(
            "Der Lizenzschlüssel ist bereits auf einem anderen Rechner aktiviert. "
            "Deaktivieren Sie ihn dort oder wenden Sie sich bei einem Geräteverlust "
            "an den Support."
        )
    elif code == "wrong_major":
        detail = _("Der Lizenzschlüssel gilt für eine andere Hauptversion von Solidon.")
    elif code == "licence_blocked":
        detail = _(
            "Dieser Lizenzschlüssel wurde gesperrt. Wenden Sie sich mit Ihrer "
            "Bestellnummer an den Support."
        )
    elif code == "service_unavailable":
        detail = _(
            "Der Aktivierungsdienst ist vorübergehend nicht verfügbar. Versuchen Sie "
            "es später erneut oder wenden Sie sich an den Support."
        )
    elif code == "rate_limit":
        detail = _(
            "Für diesen Lizenzschlüssel gab es heute zu viele Aktivierungsversuche. "
            "Versuchen Sie es morgen erneut oder wenden Sie sich an den Support."
        )
    elif code == "activation_not_found":
        detail = _(
            "Der Geräteplatz wurde beim Aktivierungsdienst nicht gefunden. "
            "Wenden Sie sich mit Ihrer Bestellnummer an den Support."
        )
    else:
        detail = _(
            "Der Aktivierungsdienst hat die signierte Anfrage abgelehnt. Prüfen Sie "
            "den Lizenzschlüssel oder wenden Sie sich an den Support."
        )
    suggestions: tuple[Action, ...]
    if code == "rate_limit":
        suggestions = (REPORT_ERROR, CANCEL)
    elif code in {
        "activation_not_found",
        "device_limit",
        "licence_blocked",
        "service_unavailable",
        "wrong_major",
    }:
        suggestions = (RETRY, REPORT_ERROR, CANCEL)
    else:
        suggestions = ()
    return ActivationServiceError(
        detail=detail,
        suggestions=suggestions,
        values={"code": code},
    )


def activate(
    request_document: str,
    *,
    sender: Callable[[bytes], bytes] | None = None,
) -> str:
    """Sendet eine bereits signierte Anforderung und gibt das Zertifikat zurück."""
    send = sender or _post
    try:
        raw = send(request_document.encode("utf-8"))
        text = raw.decode("utf-8")
        answer = json.loads(text)
    except ActivationServiceError:
        raise
    except (UnicodeError, ValueError, TypeError) as problem:
        raise ActivationServiceError(
            detail=_("Der Aktivierungsdienst hat keine lesbare Antwort gesendet.")
        ) from problem
    if isinstance(answer, dict) and answer.get("ok") is False:
        raise _error_from(answer)
    if not isinstance(answer, dict) or answer.get("kind") != "activation-certificate":
        raise ActivationServiceError(
            detail=_("Der Aktivierungsdienst hat kein Geräte-Zertifikat gesendet.")
        )
    return text


def deactivate(
    request_document: str,
    *,
    sender: Callable[[bytes], bytes] | None = None,
) -> None:
    """Gibt den Geräteplatz nach einem ausdrücklichen Nutzerklick frei."""
    send = sender or _post_deactivation
    try:
        answer = json.loads(send(request_document.encode("utf-8")).decode("utf-8"))
    except (UnicodeError, ValueError, TypeError) as problem:
        raise ActivationServiceError(
            detail=_("Der Aktivierungsdienst hat keine lesbare Abmeldebestätigung gesendet.")
        ) from problem
    if not isinstance(answer, dict) or answer.get("ok") is not True:
        if isinstance(answer, dict):
            raise _error_from(answer)
        raise ActivationServiceError(
            detail=_("Dieser Rechner ließ sich beim Aktivierungsdienst nicht abmelden.")
        )
