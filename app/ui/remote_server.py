"""Der MCP-Server im Fenster (Konzept P15 §7 Etappe 9, D19).

Das Protokoll liegt in ``app.core.agent.remote`` und weiß nichts von Netz und
Fenster. Hier kommt beides dazu: ein Server auf ``127.0.0.1``, und eine Brücke,
die einen Aufruf im Qt-Hauptthread ausführt.

**Warum im Hauptthread.** Das Dokument gehört dem Fenster. Ein Aufruf, der
nebenher hineinschriebe, während der Nutzer eine Operation ausführt, hinterließe
einen Zustand, den weder Undo noch Prüfbericht erklären können. Der Server
nimmt entgegen, gibt weiter und wartet — die Wartezeit trägt der Ferngast, und
das ist die richtige Seite.

**Warum als eine Transaktion.** Ein Fernaufruf ist derselbe Vorgang wie ein
Menüklick und geht denselben Weg durch ``History.apply``. Was von außen kam,
steht als Herkunft daran (§26.4): wer hinterher wissen will, was er nicht
selbst getan hat, sieht es im Verlauf statt es zu erraten.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from PySide6.QtCore import QCoreApplication, QEvent, QObject

from app.core.agent import remote
from app.core.log import get_logger

_log = get_logger(__name__)

#: Wie lange ein Fernaufruf auf den Hauptthread warten darf. Großzügig, weil
#: eine Boolesche Operation auf einem großen Netz dauert — aber endlich, damit
#: ein hängendes Fenster nicht jeden Aufrufer mit sich zieht.
CALL_TIMEOUT = 300.0

#: Der Pfad, unter dem das Protokoll spricht. Alles andere antwortet mit 404 —
#: ein Server, der auf jeden Pfad antwortet, lädt zum Stöbern ein.
ENDPOINT = "/mcp"

#: Deckel für eine einzelne Anfrage. Eine Werkzeugliste ist ein paar Kilobyte;
#: alles darüber ist kein Aufruf, sondern ein Versuch.
MAX_BODY = 1 << 20


class _Call(QEvent):
    """Ein Aufruf auf dem Weg in den Hauptthread."""

    TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, name: str, arguments: dict[str, Any]) -> None:
        super().__init__(_Call.TYPE)
        self.name = name
        self.arguments = arguments
        self.done = threading.Event()
        self.answer = ""
        self.error: BaseException | None = None


class WindowBridge(QObject):
    """Führt Fernaufrufe dort aus, wo das Dokument lebt.

    Die Brücke ist ein ``QObject`` im Hauptthread. Der Server ruft
    ``call`` aus seinem eigenen Thread; der Aufruf reist als Ereignis
    hinüber und der Server wartet auf die Antwort. Ein Signal täte es auch,
    aber ein Ereignis trägt sein Ergebnis zurück, ohne dass beide Seiten einen
    gemeinsamen Zustand halten müssen.
    """

    def __init__(self, run: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._run = run

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        event = _Call(name, arguments)
        QCoreApplication.postEvent(self, event)
        if not event.done.wait(CALL_TIMEOUT):
            raise TimeoutError(name)
        if event.error is not None:
            raise event.error
        return event.answer

    def event(self, event: QEvent) -> bool:
        if event.type() != _Call.TYPE:
            handled: bool = super().event(event)
            return handled
        assert isinstance(event, _Call)
        try:
            event.answer = self._run(event.name, event.arguments)
        except BaseException as problem:  # der Aufrufer bekommt ihn, nicht der Server
            event.error = problem
        finally:
            event.done.set()
        return True


class _Handler(BaseHTTPRequestHandler):
    """JSON-RPC über POST. Keine Sitzung, kein Zustand, kein Verzeichnis."""

    protocol_version = "HTTP/1.1"
    bridge: remote.Bridge

    def do_POST(self) -> None:
        if not remote.allowed(self.client_address[0]):
            # Die zweite der drei Prüfungen. Die erste ist die Bindung; wer
            # trotzdem hier ankommt, kam über eine Weiterleitung.
            _log.warning("remote call refused from %s", self.client_address[0])
            self._send(403, b"")
            return
        origin = self.headers.get("Origin")
        if not remote.origin_allowed(origin):
            # Die dritte, und die einzige, die einen Browser aufhält: der sitzt
            # auf diesem Rechner und besteht die Adressprüfung.
            _log.warning("remote call refused, origin %s", origin)
            self._send(403, b"")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if self.path.rstrip("/") != ENDPOINT:
            self._drain(length)
            self._send(404, b"")
            return
        if length > MAX_BODY:
            self._drain(length)
            self._send(413, b"")
            return
        payload = self.rfile.read(length)
        self._send(200, remote.answer_bytes(payload, self.bridge))

    def _drain(self, length: int) -> None:
        """Den Rumpf einer abgelehnten Anfrage wegwerfen, statt ihn liegen zu
        lassen.

        Ungelesen bleibt er im Sockel stehen; der Client schreibt weiter, und
        die Gegenseite bricht ab, bevor er die Antwort gelesen hat — er sieht
        einen Verbindungsabbruch statt „zu groß" und weiß nicht, warum. Gelesen
        wird höchstens :data:`MAX_BODY`: wer mehr schickt, bekommt seine
        Antwort und danach eine geschlossene Leitung.
        """
        remaining = min(length, MAX_BODY)
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 64 * 1024))
            if not chunk:
                break
            remaining -= len(chunk)

    def _send(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if status >= 400:
            # Bei einer Ablehnung liegt der Rumpf der Anfrage ungelesen im
            # Sockel — bei 413 mit Absicht. Unter HTTP/1.1 hält die Leitung
            # danach offen, der Client schreibt weiter, und Windows bricht
            # die Verbindung ab, bevor er die Antwort gelesen hat: er sieht
            # einen Abbruch statt „zu groß" und weiß nicht, warum.
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Nicht auf die Konsole — ins Protokoll, wie alles andere auch."""
        _log.debug("mcp %s", format % args)


class RemoteServer:
    """Start und Stopp, mehr nicht.

    Der Server hält keinen Zustand über eine Anfrage hinaus. Ausschalten heißt
    deshalb wirklich aus: der Sockel wird geschlossen, und was danach kommt,
    findet niemanden.
    """

    def __init__(self, bridge: remote.Bridge, port: int = remote.DEFAULT_PORT) -> None:
        self._bridge = bridge
        self._port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._server is not None

    @property
    def port(self) -> int:
        return self._port

    def start(self) -> None:
        if self._server is not None:
            return
        handler = type("_Bound", (_Handler,), {"bridge": self._bridge})
        self._server = ThreadingHTTPServer((remote.HOST, self._port), handler)
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, name="mcp", daemon=True)
        self._thread.start()
        _log.info("mcp server listening on %s:%d", remote.HOST, self._port)

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._server = None
        self._thread = None
        _log.info("mcp server stopped")
