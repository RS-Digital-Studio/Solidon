"""Der ausdrücklich ausgelöste Netzweg der Geräteaktivierung.

Der Freischaltzustand selbst importiert dieses Modul nicht. Damit bleibt der
Programmstart vollständig lokal: Erst der Klick auf „Online aktivieren“ ruft
:func:`activate` auf. Der Offline-Weg erzeugt dieselbe Anforderung, überträgt
sie aber als Datei und kommt ohne diese Verbindung aus.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, Final
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from app.core.errors import ACTIVATE_OFFLINE, CANCEL, REPORT_ERROR, RETRY, Action, AppError
from app.core.http import (
    HttpBoundaryError,
    RejectRedirects,
    ResponseDeadlineError,
    ResponseTooLargeError,
    deadline_after,
    read_limited,
    response_url,
    same_origin,
    validate_http_url,
)
from app.core.json_boundary import loads as load_json
from app.i18n import TranslatableText, _

ACTIVATION_URL: Final = "https://solidon3d.de/api/activation.php"
DEACTIVATION_URL: Final = "https://solidon3d.de/api/deactivation.php"
TIMEOUT_SECONDS: Final = 15.0
MAX_RESPONSE_BYTES: Final = 65536
_SERVICE_OPENER = build_opener(RejectRedirects())


def _open_service(request: Request, *, timeout: float) -> object:
    """Öffnet genau den festen Aktivierungsendpunkt, ohne Weiterleitung."""
    return _SERVICE_OPENER.open(request, timeout=timeout)


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


def _response_body(
    response: object,
    *,
    deadline: float | None = None,
    require_timeout: bool = False,
) -> bytes:
    """Liest eine kleine JSON-Antwort; der Dienst liefert nie große Dateien."""
    try:
        return read_limited(
            response,  # type: ignore[arg-type]
            limit=MAX_RESPONSE_BYTES,
            deadline=deadline if deadline is not None else deadline_after(TIMEOUT_SECONDS),
            require_timeout=require_timeout,
        )
    except ResponseTooLargeError as problem:
        raise ActivationServiceError(
            detail=_("Der Aktivierungsdienst hat eine ungewöhnlich große Antwort gesendet.")
        ) from problem
    except (HttpBoundaryError, ResponseDeadlineError) as problem:
        raise ActivationServiceError(
            detail=_("Der Aktivierungsdienst hat die Anfrage abgelehnt.")
        ) from problem


def _post_to(url: str, payload: bytes) -> bytes:
    address = validate_http_url(
        url,
        allow_http=False,
        allow_query=False,
        allow_fragment=False,
    )
    deadline = deadline_after(TIMEOUT_SECONDS)
    request = Request(
        address,
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Solidon3D-Activation/1",
        },
        method="POST",
    )
    try:
        with _open_service(request, timeout=TIMEOUT_SECONDS) as response:  # type: ignore[attr-defined]
            final = validate_http_url(response_url(response, address), allow_http=False)
            if not same_origin(address, final):
                raise ActivationServiceError(
                    detail=_("Der Aktivierungsdienst hat die Anfrage abgelehnt.")
                )
            return _response_body(response, deadline=deadline, require_timeout=True)
    except HTTPError as problem:
        try:
            body = _response_body(problem, deadline=deadline, require_timeout=True)
            if body:
                return body
            raise ActivationServiceError(
                detail=_("Der Aktivierungsdienst hat die Anfrage abgelehnt.")
            ) from problem
        finally:
            problem.close()
    except (URLError, TimeoutError, OSError, ResponseDeadlineError) as problem:
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
        answer = load_json(text, max_bytes=MAX_RESPONSE_BYTES)
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
        answer = load_json(
            send(request_document.encode("utf-8")),
            max_bytes=MAX_RESPONSE_BYTES,
        )
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
