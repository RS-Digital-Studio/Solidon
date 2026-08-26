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

import http.client
import json
from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("PySide6")

from app.core.agent import remote
from app.ui.remote_server import ENDPOINT, MAX_BODY, RemoteServer


class _Bridge:
    """Führt aus, was ankommt — und merkt es sich."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return "fertig"


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


def test_a_broken_body_still_gets_an_answer(server: tuple[RemoteServer, _Bridge]) -> None:
    """Kein Absturz auf kaputte Eingabe — das Protokoll antwortet mit Fehler."""
    running, _bridge = server

    status, body = post(running.port, b"{kein json")

    assert status == 200
    assert "error" in json.loads(body)


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


def test_it_is_off_until_someone_turns_it_on() -> None:
    """Die vierte Auflage: standardmäßig aus.

    Eine offene Schnittstelle, die niemand eingeschaltet hat, ist eine offene
    Tür — der Server läuft erst nach ``start``.
    """
    running = RemoteServer(_Bridge())

    assert not running.running
