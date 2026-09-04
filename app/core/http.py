"""Gemeinsame Sicherheitsgrenze für kleine HTTP-Transporte.

Das Modul öffnet selbst keine Verbindung. Es prüft Adressen, verhindert auf
Wunsch Weiterleitungen und liest Antwortströme mit einer Byte- und einer
echten Gesamtzeitgrenze. Dadurch bleibt die Entscheidung, welcher Endpunkt
für welchen Zweck zulässig ist, beim jeweiligen Fachmodul.
"""

from __future__ import annotations

import http.client
import ipaddress
import queue
import socket
import ssl
import threading
from collections.abc import Callable, Iterator
from time import monotonic
from typing import IO, Any, Final, Protocol, cast
from urllib.parse import SplitResult, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request

READ_CHUNK_BYTES: Final = 64 * 1024
_DNS_SLOTS: Final = threading.BoundedSemaphore(4)


class HttpBoundaryError(ValueError):
    """Eine Antwort oder Adresse verletzt den lokalen HTTP-Vertrag."""


class UnsafeUrlError(HttpBoundaryError):
    """Eine Adresse ist für den vorgesehenen Netzweg nicht sicher."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ResponseTooLargeError(HttpBoundaryError):
    """Eine Antwort überschreitet ihre feste Byte-Grenze."""

    def __init__(self, received: int, limit: int) -> None:
        super().__init__(f"response exceeds {limit} bytes")
        self.received = received
        self.limit = limit


class ResponseDeadlineError(TimeoutError):
    """Die monotone Gesamtfrist einer Antwort ist abgelaufen."""


class ResponseTimeoutUnavailableError(HttpBoundaryError):
    """Der produktive Antwortstrom lässt sich nicht zeitlich begrenzen."""


class InvalidResponseBodyError(HttpBoundaryError):
    """Der Antwortstrom liefert keine Bytes."""


class ReadableResponse(Protocol):
    """Die für das begrenzte Lesen benötigte Antwortoberfläche."""

    headers: Any

    def read(self, size: int = -1) -> bytes: ...


Timer = Callable[[], float]


class RejectRedirects(HTTPRedirectHandler):
    """Verhindert, dass urllib eine Anfrage an eine neue Origin weiterreicht."""

    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        return None


def deadline_after(seconds: float, *, timer: Timer = monotonic) -> float:
    """Die monotone Endzeit für einen Verbindungs- und Lesevorgang."""
    if seconds <= 0:
        raise ValueError("seconds must be positive")
    return timer() + seconds


def validate_http_url(
    url: str,
    *,
    allow_http: bool,
    allow_query: bool = True,
    allow_fragment: bool = False,
) -> str:
    """Prüft eine HTTP-Adresse einschließlich ihrer Autoritätsdaten.

    Benutzername und Kennwort sind auch dann verboten, wenn der jeweilige
    Server sie unterstützen würde: Solche Werte landen zu leicht in
    Fehlermeldungen, Verlauf oder Herkunftsangaben.
    """
    value = url.strip()
    if not value or any(ord(character) <= 32 or ord(character) == 127 for character in value):
        raise UnsafeUrlError("control")
    if "\\" in value:
        raise UnsafeUrlError("backslash")
    try:
        parts = urlsplit(value)
        _port = parts.port
    except ValueError as problem:
        raise UnsafeUrlError("authority") from problem
    schemes = {"https", "http"} if allow_http else {"https"}
    if parts.scheme.lower() not in schemes:
        raise UnsafeUrlError("scheme")
    if not parts.hostname:
        raise UnsafeUrlError("host")
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrlError("userinfo")
    if not allow_query and parts.query:
        raise UnsafeUrlError("query")
    if not allow_fragment and parts.fragment:
        raise UnsafeUrlError("fragment")
    return value


def same_origin(first: str, second: str) -> bool:
    """Ob zwei geprüfte Adressen dasselbe Schema, denselben Host und Port haben."""
    try:
        left = _origin(urlsplit(first))
        right = _origin(urlsplit(second))
    except ValueError:
        return False
    return left == right


def redirect_left_origin(answer: Any, address: str, *, allow_http: bool) -> bool:
    """Hat die Antwort den Ursprung verlassen, aus dem sie kommen sollte? (§32)

    Eine Weiterleitung darf die Adresse verfeinern, aber nicht den Host
    wechseln: Sonst geht ein Kaufcode oder ein Prüfbericht an einen Server, den
    niemand geprüft hat. Die Frage ist überall dieselbe — die Antwort darauf
    nicht, und deshalb wirft diese Funktion nicht selbst: Der Sprachbackend
    meldet ``BackendUnavailable``, der Aktivierungsdienst
    ``ActivationServiceError``, Update und Support ein nacktes ``ValueError``.
    Jeder Aufrufer behält seinen Fehler und bekommt nur die Prüfung geliehen.

    Bis zum 04.09.2026 stand sie siebenmal ausgeschrieben — in ``backends.llm``
    dreimal, in ``updates`` zweimal, dazu ``support`` und ``licence_service``.
    Sieben Stellen sind sechs Gelegenheiten, eine zu vergessen, wenn die Regel
    einmal schärfer wird.
    """
    final = validate_http_url(response_url(answer, address), allow_http=allow_http)
    return not same_origin(address, final)


def is_private_destination(url: str) -> bool:
    """Ob eine Adresse ausdrücklich auf einen lokalen oder privaten Host zeigt.

    Die Funktion löst keine DNS-Namen auf. Sie verhindert die eindeutigen
    Eskalationen durch lokale Namen und Adressliterale, ohne einen CDN-Namen
    durch eine zweite, rennanfällige DNS-Abfrage vorwegzunehmen.
    """
    host = (urlsplit(url).hostname or "").rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def resolve_public_addresses(
    url: str,
    *,
    deadline: float,
    timer: Timer = monotonic,
) -> tuple[str, ...]:
    """Löst einen Netzhost innerhalb der Gesamtfrist ausschließlich öffentlich auf."""
    parts = urlsplit(url)
    host = parts.hostname
    if host is None:
        raise UnsafeUrlError("host")
    port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    remaining = deadline - timer()
    if remaining <= 0 or not _DNS_SLOTS.acquire(timeout=max(0.0, remaining)):
        raise ResponseDeadlineError("DNS deadline exceeded")

    answers: queue.Queue[tuple[list[tuple[Any, ...]] | None, BaseException | None]] = queue.Queue(
        maxsize=1
    )

    def resolve() -> None:
        try:
            result = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            answers.put_nowait((result, None))
        except BaseException as problem:
            answers.put_nowait((None, problem))
        finally:
            _DNS_SLOTS.release()

    threading.Thread(target=resolve, daemon=True, name="http-dns").start()
    remaining = deadline - timer()
    if remaining <= 0:
        raise ResponseDeadlineError("DNS deadline exceeded")
    try:
        resolved, problem = answers.get(timeout=remaining)
    except queue.Empty as problem:
        raise ResponseDeadlineError("DNS deadline exceeded") from problem
    if problem is not None:
        raise OSError("DNS-Auflösung fehlgeschlagen") from problem
    assert resolved is not None
    addresses: list[str] = []
    for answer in resolved:
        address = str(answer[4][0]).split("%", 1)[0]
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError as problem:
            raise UnsafeUrlError("dns_address") from problem
        if not parsed.is_global:
            raise UnsafeUrlError("private_destination")
        normalized = str(parsed)
        if normalized not in addresses:
            addresses.append(normalized)
    if not addresses:
        raise UnsafeUrlError("dns_empty")
    return tuple(addresses)


def verify_public_peer(peer: object, expected: str) -> None:
    """Bindet die erreichte Gegenstelle an die zuvor geprüfte DNS-Antwort."""
    try:
        address = ipaddress.ip_address(str(peer).split("%", 1)[0])
        pinned = ipaddress.ip_address(expected)
    except ValueError as problem:
        raise UnsafeUrlError("peer_address") from problem
    if not address.is_global or address != pinned:
        raise UnsafeUrlError("peer_mismatch")


class _PinnedResponse:
    """Hält Antwort, Verbindung und den bereits geprüften Socket zusammen."""

    def __init__(
        self,
        response: http.client.HTTPResponse,
        connection: http.client.HTTPConnection,
        sock: socket.socket,
        url: str,
    ) -> None:
        self._response = response
        self._connection = connection
        self._sock = sock
        self.url = url
        self.headers = response.headers
        self.status = response.status
        self.reason = response.reason

    def read(self, size: int = -1) -> bytes:
        return self._response.read(size)

    def set_read_timeout(self, seconds: float) -> None:
        candidates = [self._sock]
        for path in (("fp", "raw", "_sock"), ("fp", "_sock")):
            candidate: Any = self._response
            try:
                for attribute in path:
                    candidate = getattr(candidate, attribute)
            except AttributeError:
                continue
            candidates.append(candidate)
        for candidate in candidates:
            try:
                candidate.settimeout(seconds)
            except OSError:
                continue
            return
        # Ein HTTP/1.0-Server darf den Netzsocket nach den Kopfzeilen
        # schließen, während der Dateipuffer die vollständige Antwort hält.
        # Dann kann der folgende Lesezugriff nicht mehr im Netz blockieren.
        if self._response.length == 0 or self._response.isclosed():
            return
        raise OSError("Die Restzeit ließ sich nicht am Antwortsocket setzen")

    def geturl(self) -> str:
        return self.url

    def isclosed(self) -> bool:
        return self._response.isclosed()

    def close(self) -> None:
        self._response.close()
        self._connection.close()

    def __enter__(self) -> _PinnedResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def open_public_url(
    url: str,
    *,
    deadline: float,
    headers: dict[str, str] | None = None,
    timer: Timer = monotonic,
) -> _PinnedResponse:
    """Öffnet eine öffentliche URL an genau einer zuvor geprüften IP-Adresse."""
    checked = validate_http_url(url, allow_http=True, allow_fragment=False)
    parts = urlsplit(checked)
    hostname = parts.hostname
    if hostname is None:
        raise UnsafeUrlError("hostname")
    addresses = resolve_public_addresses(checked, deadline=deadline, timer=timer)
    port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    last_problem: OSError | None = None
    for address in addresses:
        remaining = deadline - timer()
        if remaining <= 0:
            raise ResponseDeadlineError("connection deadline exceeded")
        connection: http.client.HTTPConnection
        if parts.scheme.lower() == "https":
            connection = http.client.HTTPSConnection(
                hostname,
                port,
                timeout=remaining,
                context=ssl.create_default_context(),
            )
        else:
            connection = http.client.HTTPConnection(hostname, port, timeout=remaining)

        def pinned_connection(
            target: tuple[str, int],
            timeout: float | None = None,
            source_address: tuple[str, int] | None = None,
            *,
            pinned_address: str = address,
        ) -> socket.socket:
            return socket.create_connection((pinned_address, target[1]), timeout, source_address)

        connection.__dict__["_create_connection"] = pinned_connection
        try:
            connection.connect()
            sock = connection.sock
            if sock is None:
                raise OSError("Verbindung besitzt keinen Socket")
            verify_public_peer(sock.getpeername()[0], address)
            target = urlunsplit(("", "", parts.path or "/", parts.query, ""))
            connection.request("GET", target, headers=headers or {})
            response = connection.getresponse()
            wrapped = _PinnedResponse(response, connection, sock, checked)
            if response.status >= 400 or response.status in {301, 302, 303, 307, 308}:
                from urllib.error import HTTPError

                raise HTTPError(
                    checked,
                    response.status,
                    str(response.reason),
                    response.headers,
                    cast(IO[bytes], wrapped),
                )
            return wrapped
        except UnsafeUrlError:
            connection.close()
            raise
        except OSError as problem:
            connection.close()
            last_problem = problem
    if last_problem is not None:
        raise last_problem
    raise UnsafeUrlError("dns_empty")


def validate_download_redirect(initial: str, final: str) -> str:
    """Prüft den erreichten Ort eines Downloads mit erlaubtem CDN-Wechsel.

    Ein Wechsel zu einem anderen öffentlichen HTTPS-Host ist für
    Download-CDNs zulässig. HTTPS darf nicht auf Klartext herabgestuft werden,
    und eine öffentliche Adresse darf nicht in ein lokales Netz umleiten.
    """
    checked = validate_http_url(final, allow_http=True, allow_fragment=False)
    initial_parts = urlsplit(initial)
    final_parts = urlsplit(checked)
    if initial_parts.scheme.lower() == "https" and final_parts.scheme.lower() != "https":
        raise UnsafeUrlError("downgrade")
    if not is_private_destination(initial) and is_private_destination(checked):
        raise UnsafeUrlError("private_redirect")
    return checked


def response_url(response: object, fallback: str) -> str:
    """Die endgültige URL einer urllib-Antwort oder der geprüfte Ausgangswert."""
    getter = getattr(response, "geturl", None)
    value = getter() if callable(getter) else getattr(response, "url", fallback)
    return str(value or fallback)


def iter_limited(
    response: ReadableResponse,
    *,
    limit: int,
    deadline: float,
    timer: Timer = monotonic,
    require_timeout: bool = True,
    chunk_size: int = READ_CHUNK_BYTES,
) -> Iterator[bytes]:
    """Liest bis EOF mit Byte-Grenze und monotoner Gesamtfrist.

    Bei produktiven urllib-Antworten wird vor jedem Lesen die noch übrige
    Gesamtzeit am Socket gesetzt. Injizierte Testtransporte können denselben
    Vertrag über 'set_read_timeout(seconds)' anbieten; fehlt er und
    'require_timeout' ist wahr, wird vor dem ersten Lesen abgebrochen.
    """
    if limit < 0 or chunk_size <= 0:
        raise ValueError("limit and chunk_size must be valid")
    announced = _content_length(response)
    if announced is not None and announced > limit:
        raise ResponseTooLargeError(announced, limit)

    received = 0
    while True:
        remaining = deadline - timer()
        if remaining <= 0:
            raise ResponseDeadlineError("response deadline exceeded")
        controlled = _set_read_timeout(response, remaining)
        if require_timeout and not controlled:
            if _response_finished(response):
                return
            raise ResponseTimeoutUnavailableError("response socket timeout is unavailable")
        try:
            chunk = response.read(min(chunk_size, limit + 1 - received))
        except TimeoutError as problem:
            raise ResponseDeadlineError("response deadline exceeded") from problem
        if timer() > deadline:
            raise ResponseDeadlineError("response deadline exceeded")
        if not isinstance(chunk, bytes):
            raise InvalidResponseBodyError("response stream did not return bytes")
        if not chunk:
            return
        received += len(chunk)
        if received > limit:
            raise ResponseTooLargeError(received, limit)
        yield chunk


def read_limited(
    response: ReadableResponse,
    *,
    limit: int,
    deadline: float,
    timer: Timer = monotonic,
    require_timeout: bool = True,
) -> bytes:
    """Liest eine vollständige, zeit- und bytebegrenzte Antwort."""
    return b"".join(
        iter_limited(
            response,
            limit=limit,
            deadline=deadline,
            timer=timer,
            require_timeout=require_timeout,
        )
    )


def _origin(parts: SplitResult) -> tuple[str, str, int | None]:
    """Die normalisierte Origin einer zerlegten Adresse."""
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").rstrip(".").lower()
    port = parts.port
    if port is None:
        port = 443 if scheme == "https" else 80 if scheme == "http" else None
    return scheme, host, port


def _content_length(response: ReadableResponse) -> int | None:
    """Eine glaubhafte angekündigte Größe, sonst 'None'."""
    headers = getattr(response, "headers", None)
    raw = headers.get("Content-Length") if headers is not None else None
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _set_read_timeout(response: ReadableResponse, seconds: float) -> bool:
    """Setzt die Restzeit am Testvertrag oder an einem urllib-Socket."""
    declared = getattr(response, "set_read_timeout", None)
    if callable(declared):
        declared(seconds)
        return True

    for path in (
        ("fp", "fp", "raw", "_sock"),
        ("fp", "raw", "_sock"),
        ("fp", "_sock"),
        ("raw", "_sock"),
        ("_sock",),
    ):
        candidate: Any = response
        try:
            for attribute in path:
                candidate = getattr(candidate, attribute)
        except AttributeError:
            continue
        setter = getattr(candidate, "settimeout", None)
        if not callable(setter):
            continue
        try:
            setter(seconds)
        except OSError:
            # Bei kleinen, vollständig gepufferten Antworten kann der Server
            # den Socket schon nach den Kopfzeilen geschlossen haben. Dann
            # blockiert der folgende Lesezugriff nicht mehr.
            return bool(getattr(candidate, "_closed", False))
        return True
    return False


def _response_finished(response: ReadableResponse) -> bool:
    """Ob urllib den Strom nach vollständig gelesenem Inhalt geschlossen hat."""
    checker = getattr(response, "isclosed", None)
    if callable(checker):
        return bool(checker())
    return bool(getattr(response, "closed", False))
