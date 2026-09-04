"""Der Server, der die MCP-Schnittstelle ins Netz bringt (Konzept P15 §7).

``tests/test_remote.py`` prüft das Protokoll — ``app/core/agent/remote.py``,
das von Netz und Fenster nichts weiß. Der Server daneben war ungeprüft, und
das ist die falsche Hälfte zum Weglassen: er ist die, die einen Sockel
aufmacht. Die Auflagen aus dem Konzept sind Aussagen über ihn, nicht über den
Parser.

Geprüft wird am laufenden Server mit echten Anfragen. Ein Test, der den
Handler direkt aufruft, ginge an dem vorbei, was hier zählt: dass die
Bindung hält und ein anderer Pfad nichts hergibt.
"""

from __future__ import annotations

import contextlib
import http.client
import io
import json
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import suppress
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from app.core.agent import remote
from app.ui import remote_server
from app.ui.remote_server import ENDPOINT, MAX_BODY, RemoteServer, WindowBridge


class _Bridge:
    """Führt aus, was ankommt — und merkt es sich."""

    def __init__(self, answer: str = "fertig") -> None:
        self.answer = answer
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return self.answer


class _BlockingBridge(_Bridge):
    """Hält Aufrufe fest, damit die gleichzeitig belegten Worker messbar sind."""

    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()
        self._condition = threading.Condition()

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        with self._condition:
            self.calls.append((name, arguments))
            self._condition.notify_all()
        if not self.release.wait(5.0):
            raise TimeoutError(name)
        return self.answer

    def wait_for_calls(self, count: int) -> None:
        limit = time.monotonic() + 5.0
        with self._condition:
            while len(self.calls) < count:
                remaining = limit - time.monotonic()
                if remaining <= 0 or not self._condition.wait(remaining):
                    raise AssertionError(f"nur {len(self.calls)} von {count} Aufrufen angekommen")


@pytest.fixture
def server() -> Iterator[tuple[RemoteServer, _Bridge]]:
    """Ein Server auf einem freien Port. Port 0 heißt: such dir einen."""
    bridge = _Bridge()
    running = RemoteServer(bridge, port=0)
    running.start()
    try:
        yield running, bridge
    finally:
        running.stop()


def post(port: int, payload: object, path: str = ENDPOINT) -> tuple[int, bytes]:
    """Eine echte Anfrage. Gibt Status und Rumpf zurück, auch bei Fehlern.

    Über ``http.client`` und nicht über ``urllib``: das wirft bei 4xx eine
    Ausnahme, und ihr Aufräumen hinterlässt unter Python 3.14 eine Warnung aus
    einem Destruktor, die mit dem Server nichts zu tun hat. Hier ist ein
    Statuscode eine Antwort und kein Fehler — genau das soll geprüft werden.
    """
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request("POST", path, body=body, headers={"Content-Type": "application/json"})
        answer = connection.getresponse()
        return int(answer.status), answer.read()
    finally:
        connection.close()


def post_with_headers(
    port: int,
    headers: list[tuple[str, str]],
    body: bytes = b"",
    *,
    shutdown_write: bool = False,
    timeout: float = 2.0,
) -> tuple[int, bytes]:
    """POST mit absichtlich ungültigen oder doppelten Kopfzeilen."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.putrequest("POST", ENDPOINT)
        connection.putheader("Content-Type", "application/json")
        for name, value in headers:
            connection.putheader(name, value)
        connection.endheaders(body)
        if shutdown_write:
            assert connection.sock is not None
            # Der Server lehnt eine solche Anfrage ab, ohne ihren Rumpf zu
            # lesen, und schließt — mitunter, bevor diese Zeile läuft. Linux
            # meldet das ``shutdown`` auf der schon getrennten Verbindung
            # dann mit ENOTCONN (CI, 02.09.2026, einmal von etwa zehn Läufen),
            # Windows schweigt. Die Antwort liegt in dem Fall bereits im
            # Puffer; ``getresponse`` liest sie wie sonst auch.
            with contextlib.suppress(OSError):
                connection.sock.shutdown(socket.SHUT_WR)
        answer = connection.getresponse()
        return int(answer.status), answer.read()
    finally:
        connection.close()


def test_it_binds_to_the_loopback_and_nowhere_else(
    server: tuple[RemoteServer, _Bridge],
) -> None:
    """Die erste der beiden Prüfungen aus dem Konzept ist die Bindung.

    Eine Schnittstelle, die auf allen Adressen lauscht, steht im Netz, sobald
    jemand den Rechner ins WLAN hängt — und niemand hat etwas eingeschaltet.
    """
    running, _bridge = server

    assert remote.HOST == "127.0.0.1"
    assert running.running
    assert running.port > 0


def test_a_call_comes_through_and_reaches_the_bridge(
    server: tuple[RemoteServer, _Bridge],
) -> None:
    running, bridge = server

    status, body = post(
        running.port,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "place_on_bed", "arguments": {}},
        },
    )

    assert status == 200
    assert json.loads(body)["id"] == 1
    assert bridge.calls and bridge.calls[0][0] == "place_on_bed"


def test_any_other_path_gets_nothing(server: tuple[RemoteServer, _Bridge]) -> None:
    """Ein Server, der auf jeden Pfad antwortet, lädt zum Stöbern ein."""
    running, bridge = server

    status, _body = post(running.port, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, "/")

    assert status == 404
    assert bridge.calls == [], "und gerechnet wurde dabei nichts"


def test_an_oversized_body_is_refused_before_it_is_read(
    server: tuple[RemoteServer, _Bridge],
) -> None:
    """Eine Werkzeugliste ist ein paar Kilobyte; alles darüber ist ein Versuch."""
    running, bridge = server

    status, _body = post(running.port, b"x" * (MAX_BODY + 1024))

    assert status == 413
    assert bridge.calls == []


@pytest.mark.parametrize("length", ["-1", "+1", "1.0", "keine-zahl", "9" * 100])
def test_an_invalid_content_length_is_rejected_without_reading(
    server: tuple[RemoteServer, _Bridge], length: str
) -> None:
    """Eine ungültige Länge darf nie zu ``read(-1)`` oder einem Abbruch führen."""
    running, bridge = server

    status, _body = post_with_headers(
        running.port,
        [("Content-Length", length)],
        shutdown_write=True,
    )

    assert status == 400
    assert bridge.calls == []


def test_a_missing_content_length_is_rejected(server: tuple[RemoteServer, _Bridge]) -> None:
    running, bridge = server

    status, _body = post_with_headers(running.port, [], shutdown_write=True)

    assert status == 411
    assert bridge.calls == []


def test_duplicate_content_lengths_are_rejected(server: tuple[RemoteServer, _Bridge]) -> None:
    running, bridge = server

    status, _body = post_with_headers(
        running.port,
        [("Content-Length", "2"), ("Content-Length", "2")],
        b"{}",
    )

    assert status == 400
    assert bridge.calls == []


def test_an_oversized_declaration_is_rejected_without_waiting_for_its_body(
    server: tuple[RemoteServer, _Bridge],
) -> None:
    """Ein Header allein darf keinen Worker beim angeblichen Megabyte festhalten."""
    running, bridge = server
    started = time.monotonic()

    status, _body = post_with_headers(
        running.port,
        [("Content-Length", str(MAX_BODY + 1))],
        timeout=1.0,
    )

    assert status == 413
    assert time.monotonic() - started < 0.75
    assert bridge.calls == []


def test_a_truncated_body_never_reaches_the_bridge(
    server: tuple[RemoteServer, _Bridge],
) -> None:
    running, bridge = server

    status, _body = post_with_headers(
        running.port,
        [("Content-Length", "20")],
        b"{}",
        shutdown_write=True,
    )

    assert status == 400
    assert bridge.calls == []


def test_chunked_requests_are_rejected(server: tuple[RemoteServer, _Bridge]) -> None:
    running, bridge = server

    status, _body = post_with_headers(
        running.port,
        [("Transfer-Encoding", "chunked")],
        b"2\r\n{}\r\n0\r\n\r\n",
        shutdown_write=True,
    )

    assert status == 400
    assert bridge.calls == []


def test_too_many_headers_are_rejected(server: tuple[RemoteServer, _Bridge]) -> None:
    running, bridge = server
    limit = getattr(remote_server, "MAX_HEADERS", 32)

    status, _body = post_with_headers(
        running.port,
        [("Content-Length", "0"), *((f"X-Fill-{index}", "x") for index in range(limit))],
    )

    assert status == 431
    assert bridge.calls == []


def test_an_oversized_header_is_rejected(server: tuple[RemoteServer, _Bridge]) -> None:
    running, bridge = server
    limit = getattr(remote_server, "MAX_HEADER_BYTES", 32 * 1024)

    status, _body = post_with_headers(
        running.port,
        [("Content-Length", "0"), ("X-Fill", "x" * limit)],
    )

    assert status == 431
    assert bridge.calls == []


def test_header_reader_stops_at_the_application_limit() -> None:
    """Die stdlib bekommt nie erst eine vollständige übergroße Kopfzeile."""
    stream = io.BytesIO(b"X-Fill: " + b"x" * remote_server.MAX_HEADER_BYTES + b"\r\n")
    limited = remote_server._LimitedHeaderReader(stream)

    with pytest.raises(remote_server._HeaderLimitError):
        limited.readline(64 * 1024 + 1)

    assert stream.tell() == remote_server.MAX_HEADER_BYTES + 1


def test_a_partial_body_releases_its_worker_after_the_read_timeout(
    server: tuple[RemoteServer, _Bridge], monkeypatch: pytest.MonkeyPatch
) -> None:
    running, bridge = server
    monkeypatch.setattr(remote_server, "REQUEST_TIMEOUT", 0.1)
    started = time.monotonic()

    status, _body = post_with_headers(
        running.port,
        [("Content-Length", "20")],
        b"{",
        timeout=1.0,
    )

    assert status == 408
    assert time.monotonic() - started < 0.75
    assert bridge.calls == []


def test_only_a_bounded_number_of_requests_runs_at_once() -> None:
    """Weitere Verbindungen bekommen 503, statt je einen neuen Thread."""
    bridge = _BlockingBridge()
    running = RemoteServer(bridge, port=0)
    running.start()
    workers = getattr(remote_server, "MAX_WORKERS", 2)
    results: list[tuple[int, bytes]] = []
    threads = [
        threading.Thread(
            target=lambda: results.append(
                post(
                    running.port,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": "place_on_bed", "arguments": {}},
                    },
                )
            )
        )
        for _index in range(workers)
    ]
    try:
        for thread in threads:
            thread.start()
        bridge.wait_for_calls(workers)

        status, _body = post(
            running.port,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )

        assert status == 503
        assert len(bridge.calls) == workers
    finally:
        bridge.release.set()
        for thread in threads:
            thread.join(timeout=5.0)
        running.stop()


def test_busy_rejection_never_waits_for_request_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine stille Überlastverbindung darf den Annahmethread nicht besetzen."""
    bridge = _BlockingBridge()
    running = RemoteServer(bridge, port=0)
    running.start()
    workers = remote_server.MAX_WORKERS
    results: list[tuple[int, bytes]] = []
    threads = [
        threading.Thread(
            target=lambda: results.append(
                post(
                    running.port,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": "place_on_bed", "arguments": {}},
                    },
                )
            )
        )
        for _index in range(workers)
    ]
    silent: socket.socket | None = None
    try:
        for thread in threads:
            thread.start()
        bridge.wait_for_calls(workers)
        # Der alte Weg wartet an dieser Stelle eine volle Sekunde in ``recv``.
        monkeypatch.setattr(remote_server, "BUSY_REJECT_TIMEOUT", 1.0, raising=False)
        silent = socket.create_connection(("127.0.0.1", running.port), timeout=2.0)
        time.sleep(0.05)

        started = time.monotonic()
        status, _body = post(
            running.port,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )

        assert status == 503
        assert time.monotonic() - started < 0.4
    finally:
        if silent is not None:
            silent.close()
        bridge.release.set()
        for thread in threads:
            thread.join(timeout=5.0)
        running.stop()


def test_an_oversized_response_is_replaced_before_serialisation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limit = getattr(remote_server, "MAX_RESPONSE_BODY", MAX_BODY)
    oversized = "x" * (limit + 1)
    original_dumps = remote.json.dumps

    def guarded_dumps(payload: Any, *args: Any, **kwargs: Any) -> str:
        pending = [payload]
        while pending:
            value = pending.pop()
            if isinstance(value, str):
                assert len(value) <= limit, "übergroßer Werkzeugtext erreichte json.dumps"
            elif isinstance(value, dict):
                pending.extend(value.keys())
                pending.extend(value.values())
            elif isinstance(value, list | tuple):
                pending.extend(value)
        return original_dumps(payload, *args, **kwargs)

    monkeypatch.setattr(remote.json, "dumps", guarded_dumps)
    running = RemoteServer(_Bridge(oversized), port=0)
    running.start()
    try:
        status, body = post(
            running.port,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "place_on_bed", "arguments": {}},
            },
        )
    finally:
        running.stop()

    assert status == 500
    assert len(body) <= limit
    problem = json.loads(body)["error"]
    assert problem["code"] == remote.INTERNAL_ERROR
    assert "Grenzen Sie die Anfrage ein" in problem["message"]


def test_a_broken_body_still_gets_an_answer(server: tuple[RemoteServer, _Bridge]) -> None:
    """Kein Absturz auf kaputte Eingabe — das Protokoll antwortet mit Fehler."""
    running, _bridge = server

    status, body = post(running.port, b"{kein json")

    assert status == 200
    assert "error" in json.loads(body)


def test_unsafe_json_is_translated_to_a_parse_error(
    server: tuple[RemoteServer, _Bridge],
) -> None:
    running, bridge = server

    status, body = post(
        running.port,
        b'{"jsonrpc":"2.0","id":NaN,"method":"tools/list"}',
    )

    assert status == 200
    assert json.loads(body)["error"]["code"] == remote.PARSE_ERROR
    assert not bridge.calls


def test_a_refused_operation_never_reaches_the_bridge(
    server: tuple[RemoteServer, _Bridge],
) -> None:
    """Eine Operation, die fremden Quelltext ausführt, ist gesperrt.

    Die Sperre sitzt im Protokoll — hier wird geprüft, dass sie über die
    Leitung auch wirkt und nicht nur im Modultest.
    """
    running, bridge = server

    status, body = post(
        running.port,
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "create_from_scad", "arguments": {"source": "cube(10);"}},
        },
    )

    assert status == 200
    assert bridge.calls == [], "abgewiesen wird, bevor irgendetwas ausgeführt ist"
    assert "error" in json.loads(body) or "isError" in body.decode("utf-8")


def test_stopping_really_stops(server: tuple[RemoteServer, _Bridge]) -> None:
    """Ausschalten heißt aus: der Sockel ist zu, und was danach kommt, findet
    niemanden."""
    running, _bridge = server
    port = running.port
    running.stop()

    assert not running.running
    with pytest.raises(OSError):
        post(port, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})


def test_stopping_aborts_a_partial_request() -> None:
    """Ausschalten lässt keinen Slowloris-Worker bis zum Timeout zurück."""
    running = RemoteServer(_Bridge(), port=0)
    running.start()
    connection = socket.create_connection(("127.0.0.1", running.port), timeout=2.0)
    connection.settimeout(1.0)
    connection.sendall(
        (
            f"POST {ENDPOINT} HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            f"Content-Length: {MAX_BODY}\r\n"
            "Content-Type: application/json\r\n\r\n"
        ).encode("ascii")
        + b"{"
    )
    time.sleep(0.05)
    started = time.monotonic()
    try:
        running.stop()

        assert time.monotonic() - started < 1.0
        try:
            remaining = connection.recv(1)
        except (ConnectionError, OSError):
            remaining = b""
        assert remaining == b""
    finally:
        connection.close()


def test_cancelling_the_window_bridge_discards_a_queued_call(qt_app: Any) -> None:
    """Ein gestoppter Server arbeitet seinen alten Qt-Aufruf nicht später ab."""
    called: list[tuple[str, dict[str, Any]]] = []
    errors: list[BaseException] = []
    bridge = WindowBridge(lambda name, arguments: called.append((name, arguments)) or "fertig")

    def invoke() -> None:
        try:
            bridge.call("place_on_bed", {})
        except BaseException as problem:
            errors.append(problem)

    worker = threading.Thread(target=invoke)
    worker.start()
    limit = time.monotonic() + 1.0
    while not bridge.has_pending_calls and time.monotonic() < limit:
        time.sleep(0.005)

    bridge.cancel_pending()
    worker.join(timeout=1.0)
    QCoreApplication.sendPostedEvents(bridge)

    assert not worker.is_alive()
    assert errors and isinstance(errors[0], TimeoutError)
    assert called == []


def test_stopping_the_server_cancels_its_window_bridge(qt_app: Any) -> None:
    called: list[tuple[str, dict[str, Any]]] = []
    bridge = WindowBridge(lambda name, arguments: called.append((name, arguments)) or "fertig")
    running = RemoteServer(bridge, port=0)
    running.start()

    def send() -> None:
        with suppress(OSError):
            post(
                running.port,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "place_on_bed", "arguments": {}},
                },
            )

    client = threading.Thread(target=send)
    client.start()
    limit = time.monotonic() + 1.0
    while not bridge.has_pending_calls and time.monotonic() < limit:
        time.sleep(0.005)
    assert bridge.has_pending_calls

    running.stop()
    client.join(timeout=1.0)
    QCoreApplication.sendPostedEvents(bridge)

    assert not client.is_alive()
    assert not bridge.has_pending_calls
    assert called == []


def test_it_is_off_until_someone_turns_it_on() -> None:
    """Die vierte Auflage: standardmäßig aus.

    Eine offene Schnittstelle, die niemand eingeschaltet hat, ist eine offene
    Tür — der Server läuft erst nach ``start``.
    """
    running = RemoteServer(_Bridge())

    assert not running.running


def _raw_post(port: int, headers: list[str], body: bytes = b"{}") -> int:
    """POST über einen rohen Socket, mit genau den angegebenen Kopfzeilen.

    ``post_with_headers`` setzt ``Content-Type`` immer selbst; um zu prüfen,
    was **ohne** ihn geschieht, braucht es einen Weg daneben. Gibt den
    Statuscode zurück.
    """
    connection = socket.create_connection(("127.0.0.1", port), timeout=5.0)
    try:
        head = f"POST {ENDPOINT} HTTP/1.1\r\n" + "".join(f"{one}\r\n" for one in headers)
        head += f"Content-Length: {len(body)}\r\n\r\n"
        connection.sendall(head.encode("ascii") + body)
        answer = b""
        while b"\r\n" not in answer:
            piece = connection.recv(256)
            if not piece:
                break
            answer += piece
        return int(answer.split(b" ")[1]) if b" " in answer else 0
    finally:
        connection.close()


def test_a_simple_browser_post_never_reaches_the_handler() -> None:
    """Ein POST mit ``text/plain`` ist für CORS eine *einfache* Anfrage.

    Der Browser schickt sie ohne Preflight ab und verbirgt nur die **Antwort**
    — ausgeführt wäre der Aufruf trotzdem, und bei einer Schnittstelle, die
    Operationen am offenen Dokument auslöst, ist das der Unterschied zwischen
    Mitlesen und Mitschreiben. Mit dem Zwang auf ``application/json`` braucht
    dieselbe Anfrage einen Preflight, auf den dieser Server nicht antwortet:
    Sie fällt geschlossen aus (Sicherheitsdurchsicht 04.09.2026).
    """
    running = RemoteServer(_Bridge(), port=0)
    running.start()
    try:
        eigen = f"Host: 127.0.0.1:{running.port}"

        assert _raw_post(running.port, [eigen, "Content-Type: text/plain;charset=UTF-8"]) == 415
        assert _raw_post(running.port, [eigen, "Content-Type: text/plain"]) == 415
        assert _raw_post(running.port, [eigen]) == 415, "gar keiner ist auch keiner"

        # Der echte Weg bleibt offen — ein MCP-Client schickt JSON.
        assert _raw_post(running.port, [eigen, "Content-Type: application/json"]) == 200
        assert (
            _raw_post(running.port, [eigen, "Content-Type: application/json; charset=utf-8"]) == 200
        ), "der Parameter dahinter gehört dazu"
    finally:
        running.stop()


def test_a_rebound_domain_does_not_pass_as_this_machine() -> None:
    """Die ``Host``-Kopfzeile muss diesen Server benennen.

    Bei einem DNS-Rebinding zeigt eine Angreiferdomäne auf 127.0.0.1. Der
    Ursprung fängt das schon, weil die Seite ihren eigenen Namen mitschickt —
    aber das ist eine glückliche Überdeckung und keine zweite Verteidigung:
    Wer ``origin_allowed`` je weitete, nähme sie mit.

    Der Port darf dabei fehlen, und das ist Absicht: ``Host: 127.0.0.1`` ohne
    Port ist eine gültige Kopfzeile, und ein Bestandstest schickt sie.
    """
    running = RemoteServer(_Bridge(), port=0)
    running.start()
    try:
        json_kopf = "Content-Type: application/json"

        assert _raw_post(running.port, ["Host: angreifer.example", json_kopf]) == 403
        assert (
            _raw_post(running.port, [f"Host: angreifer.example:{running.port}", json_kopf]) == 403
        )
        assert _raw_post(running.port, ["Host: 127.0.0.1.angreifer.example", json_kopf]) == 403, (
            "der Name endet woanders"
        )
        assert _raw_post(running.port, [f"Host: 127.0.0.1:{running.port + 1}", json_kopf]) == 403, (
            "ein genannter Port muss stimmen"
        )

        assert _raw_post(running.port, ["Host: 127.0.0.1", json_kopf]) == 200, "ohne Port gültig"
        assert _raw_post(running.port, [f"Host: localhost:{running.port}", json_kopf]) == 200
        assert _raw_post(running.port, [f"Host: [::1]:{running.port}", json_kopf]) == 200
    finally:
        running.stop()
