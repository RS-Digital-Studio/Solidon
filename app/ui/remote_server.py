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

import json
import socket
import threading
import time
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

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

#: Höchstens so viele Antworten rechnen gleichzeitig. ``ThreadingHTTPServer``
#: startet sonst für jede Verbindung einen neuen Thread; ein lokaler Prozess
#: könnte mit offenen Rümpfen oder langsamen Aufrufen beliebig viele erzeugen.
MAX_WORKERS = 4

#: Auch Kopf und Antwort sind begrenzt. Der Rumpfdeckel allein schützt weder
#: vor vielen großen Kopfzeilen noch vor einem Werkzeug, das sehr viel Text
#: zurückgibt.
MAX_HEADERS = 32
MAX_HEADER_BYTES = 32 * 1024
MAX_RESPONSE_BODY = 2 << 20

#: Ein unvollständiger Rumpf hält einen Worker nur endlich fest. Das ist kein
#: Zeitlimit für die Operation selbst; die läuft hinter der Brücke und hat mit
#: :data:`CALL_TIMEOUT` ihren eigenen, großzügigeren Deckel.
REQUEST_TIMEOUT = 5.0

#: Überlastantworten laufen außerhalb des Annahmethreads, aber ebenfalls nur
#: in einer festen Zahl. Ein kurzer, gedeckelter Nachlauf vermeidet auf Windows
#: den RST, durch den der Client sonst nicht einmal die 503-Antwort sieht.
MAX_BUSY_WORKERS = 2
BUSY_REJECT_TIMEOUT = 0.25
BUSY_DRAIN_LIMIT = 64 * 1024

#: Nach einer bereits gesendeten 413-Antwort dürfen unmittelbar anliegende
#: Bytes kurz verworfen werden. Das ermöglicht auf Windows eine saubere
#: HTTP-Antwort, ohne auf einen angekündigten langsamen Rumpf zu warten.
OVERSIZE_DRAIN_TIMEOUT = 0.25
OVERSIZE_DRAIN_LIMIT = MAX_BODY + 64 * 1024

_RESPONSE_TOO_LARGE = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": None,
        "error": {
            "code": remote.INTERNAL_ERROR,
            "message": (
                "Die MCP-Antwort überschreitet die sichere Größengrenze. "
                "Grenzen Sie die Anfrage ein und versuchen Sie es erneut."
            ),
        },
    },
    ensure_ascii=False,
).encode("utf-8")

type _SocketRequest = socket.socket | tuple[bytes, socket.socket]


class _HeaderLimitError(Exception):
    """Die rohen Kopfzeilen überschreiten eine Anwendungsgrenze."""


class _LimitedHeaderReader:
    """Begrenzt die stdlib schon während des Kopfzeilenlesens.

    ``BaseHTTPRequestHandler`` deckelt selbst erst bei 100 Zeilen und 64 KiB
    je Zeile. Der nachträgliche Blick auf ``self.headers`` ist für unsere
    kleinere Grenze zu spät: Dann wurden die Bytes bereits vollständig
    eingelesen und geparst. Dieser schmale Leser bleibt nur für
    ``parse_request`` eingesetzt; der Nachrichtenrumpf läuft danach wieder
    direkt über den ursprünglichen gepufferten Strom.
    """

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._bytes = 0
        self._lines = 0

    def readline(self, size: int = -1) -> bytes:
        remaining = MAX_HEADER_BYTES - self._bytes
        wanted = remaining + 1
        if size >= 0:
            wanted = min(wanted, size)
        line: bytes = self._stream.readline(wanted)
        self._bytes += len(line)
        if self._bytes > MAX_HEADER_BYTES:
            raise _HeaderLimitError
        if line not in (b"", b"\n", b"\r\n"):
            self._lines += 1
            if self._lines > MAX_HEADERS:
                raise _HeaderLimitError
        return line


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
        self.cancelled = threading.Event()


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
        self._pending: dict[int, _Call] = {}
        self._pending_lock = threading.Lock()
        self._accepting = True

    @property
    def has_pending_calls(self) -> bool:
        """Ob ein Serverworker gerade auf diese Brücke wartet."""
        with self._pending_lock:
            return bool(self._pending)

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        event = _Call(name, arguments)
        with self._pending_lock:
            if not self._accepting:
                raise TimeoutError(name)
            self._pending[id(event)] = event
        try:
            QCoreApplication.postEvent(self, event)
            if not event.done.wait(CALL_TIMEOUT):
                # Liegt das Ereignis noch in der Qt-Warteschlange, darf es nach
                # dem Timeout nicht verspätet am Dokument arbeiten. Eine
                # bereits laufende Operation lässt sich hier nicht sicher
                # unterbrechen; sie beendet den Hauptthreadweg regulär.
                event.cancelled.set()
                raise TimeoutError(name)
            if event.error is not None:
                raise event.error
            return event.answer
        finally:
            with self._pending_lock:
                self._pending.pop(id(event), None)

    def cancel_pending(self) -> None:
        """Wartende Worker lösen und noch eingereihte Qt-Aufrufe verwerfen."""
        with self._pending_lock:
            self._accepting = False
            pending = tuple(self._pending.values())
        for event in pending:
            event.cancelled.set()
            event.error = TimeoutError(event.name)
            event.done.set()

    def start_accepting(self) -> None:
        """Nach einem erneuten Serverstart wieder Brückenaufrufe annehmen."""
        with self._pending_lock:
            self._accepting = True

    def event(self, event: QEvent) -> bool:
        if event.type() != _Call.TYPE:
            handled: bool = super().event(event)
            return handled
        assert isinstance(event, _Call)
        if event.cancelled.is_set():
            event.done.set()
            return True
        try:
            event.answer = self._run(event.name, event.arguments)
        except BaseException as problem:  # der Aufrufer bekommt ihn, nicht der Server
            event.error = problem
        finally:
            event.done.set()
        return True


def _host_allowed(host: str | None, port: int) -> bool:
    """Ob die ``Host``-Kopfzeile diesen Server benennt.

    Geprüft wird der **Name**, und der Port nur, wenn er dabeisteht. Genau der
    Name ist die Aussage: Bei einem DNS-Rebinding — einer Angreiferdomäne, die
    auf 127.0.0.1 zeigt — steht dort ``angreifer.example`` und nicht der
    eigene Rechner.

    **Der Port darf fehlen, und das ist keine Nachlässigkeit.** Ein
    Bestandstest hat es gefangen: Er schickt ``Host: 127.0.0.1`` ohne Port,
    und das ist eine gültige Kopfzeile. Den Port zu verlangen hätte einen
    legitimen Client abgewiesen, ohne die Aussage über den Namen zu
    verbessern.

    Eine fehlende Kopfzeile fällt durch — HTTP/1.1 verlangt sie.
    """
    if not host:
        return False
    parts = urlsplit(f"//{host.strip().lower()}")
    try:
        named = parts.port
    except ValueError:
        # Ein Port, der keine Zahl ist. ``urlsplit`` wirft erst beim Zugriff.
        return False
    if (parts.hostname or "") not in remote.LOOPBACK_HOSTS:
        return False
    return named in (None, port)


def _json_request(content_type: str | None) -> bool:
    """Ob die Anfrage sich als JSON ausgibt.

    Geprüft wird nur der Medientyp; Parameter wie ``charset=utf-8`` gehören
    dazu und werden abgeschnitten. MCP-Clients schicken ``application/json``
    von sich aus — für sie ändert sich nichts. Was die Zeile abweist, ist die
    *einfache* Anfrage eines Browsers, die ohne Preflight abgeht.
    """
    if not content_type:
        return False
    return content_type.split(";")[0].strip().lower() == "application/json"


class _Handler(BaseHTTPRequestHandler):
    """JSON-RPC über POST. Keine Sitzung, kein Zustand, kein Verzeichnis."""

    protocol_version = "HTTP/1.1"
    bridge: remote.Bridge

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(REQUEST_TIMEOUT)

    def parse_request(self) -> bool:
        original = self.rfile
        self.rfile = _LimitedHeaderReader(original)  # type: ignore[assignment]
        try:
            parsed = super().parse_request()
        except _HeaderLimitError:
            self._send(431, b"")
            return False
        finally:
            self.rfile = original
        if not parsed:
            return False
        size = sum(len(name) + len(value) + 4 for name, value in self.headers.items())
        if len(self.headers) > MAX_HEADERS or size > MAX_HEADER_BYTES:
            self._send(431, b"")
            return False
        return True

    def do_POST(self) -> None:
        if not remote.allowed(self.client_address[0]):
            # Die zweite der drei Prüfungen. Die erste ist die Bindung; wer
            # trotzdem hier ankommt, kam über eine Weiterleitung.
            _log.warning("remote call refused from %s", self.client_address[0])
            self._send(403, b"")
            return
        # ``server_port`` und nicht ``server_address[1]``: Die Adresse ist am
        # ``BaseServer`` als Vereinigung mit ``str`` und ``Buffer`` typisiert
        # und damit nicht indexierbar. ``HTTPServer`` setzt den Port in
        # ``server_bind`` als ``int``, und das ist genau die Frage hier.
        server = self.server
        assert isinstance(server, _BoundedHTTPServer)
        port = server.server_port
        origin = self.headers.get("Origin")
        if not remote.origin_allowed(origin, port):
            # Die dritte, und die einzige, die einen Browser aufhält: der sitzt
            # auf diesem Rechner und besteht die Adressprüfung.
            _log.warning("remote call refused, origin %s", origin)
            self._send(403, b"")
            return
        if not _host_allowed(self.headers.get("Host"), port):
            # Die vierte, und sie ist bewusst redundant. Ein DNS-Rebinding —
            # eine Angreiferdomäne, die auf 127.0.0.1 zeigt — scheitert schon
            # an der Ursprungsprüfung, weil die Seite ihren eigenen Namen im
            # ``Origin`` mitschickt. Das ist aber eine glückliche Überdeckung
            # und keine zweite Verteidigung: Wer ``origin_allowed`` je
            # weitete, nähme sie mit. Der ``Host`` steht deshalb eigenständig.
            _log.warning("remote call refused, host %s", self.headers.get("Host"))
            self._send(403, b"")
            return
        if not _json_request(self.headers.get("Content-Type")):
            # Und die fünfte, die vor dem Browser wirkt statt nach ihm: Ein
            # ``Content-Type: application/json`` macht aus einer
            # Fremdursprungsanfrage eine, die erst einen Preflight braucht.
            # Auf ``OPTIONS`` antwortet dieser Server nicht, also fällt sie
            # geschlossen aus — der Aufruf erreicht den Handler nie. Ohne
            # diese Zeile war ein POST mit ``text/plain`` eine *einfache*
            # Anfrage: Der Browser schickt sie ohne Rückfrage ab und verbirgt
            # nur die Antwort. Verborgen ist dann die Antwort, ausgeführt der
            # Aufruf.
            _log.warning("remote call refused, content type %s", self.headers.get("Content-Type"))
            self._send(415, b"")
            return
        length, length_error = self._content_length()
        if length_error is not None:
            self._send(length_error, b"")
            return
        assert length is not None
        if self.path.rstrip("/") != ENDPOINT:
            self._send(404, b"")
            return
        if length > MAX_BODY:
            self._send(413, b"")
            self._discard_oversized_body(length)
            return
        try:
            payload = self.rfile.read(length)
        except (TimeoutError, OSError):
            self._send(408, b"")
            return
        if len(payload) != length:
            self._send(400, b"")
            return
        try:
            answer = remote.answer_bytes(payload, self.bridge, max_bytes=MAX_RESPONSE_BODY)
        except remote.ResponseTooLargeError:
            self._send(500, _RESPONSE_TOO_LARGE)
            return
        self._send(200, answer)

    def _content_length(self) -> tuple[int | None, int | None]:
        """Eine einzige kanonische, nichtnegative Rumpflänge lesen.

        ``int`` allein ist hier keine Prüfung: ``-1`` wird zu ``read(-1)`` und
        liest bis zum Leitungsende; ``+1`` wird still akzeptiert; kaputter Text
        wirft aus dem Handler und liefert gar keine Antwort. Mehrere Längen
        sind wegen Request-Smuggling immer ungültig, auch wenn sie gleich
        aussehen. Chunked Transfer wird vom Standardserver nicht dekodiert und
        deshalb ebenfalls geschlossen abgewiesen.
        """
        if self.headers.get("Transfer-Encoding") is not None:
            return None, 400
        values = self.headers.get_all("Content-Length", failobj=[]) or []
        if not values:
            return None, 411
        if len(values) != 1:
            return None, 400
        raw = values[0].strip()
        if not raw or len(raw) > len(str(MAX_BODY)) or not raw.isascii() or not raw.isdigit():
            return None, 400
        return int(raw), None

    def _discard_oversized_body(self, length: int) -> None:
        """Nach der Ablehnung kurz anliegende Bytes ohne Verarbeitung lesen.

        Die Größenentscheidung und die 413-Antwort fallen vorher. Dieser
        begrenzte Nachlauf verhindert lediglich einen Windows-RST, wenn ein
        gutartiger Client den knapp zu großen Rumpf bereits vollständig
        sendet. Ein langsamer oder beliebig großer Rumpf wird weder abgewartet
        noch vollständig eingelesen.
        """
        remaining = min(length, OVERSIZE_DRAIN_LIMIT)
        deadline = time.monotonic() + OVERSIZE_DRAIN_TIMEOUT
        try:
            while remaining:
                timeout = deadline - time.monotonic()
                if timeout <= 0:
                    return
                self.connection.settimeout(timeout)
                chunk = self.rfile.read1(min(8192, remaining))
                if not chunk:
                    return
                remaining -= len(chunk)
        except (TimeoutError, OSError):
            return

    def _send(self, status: int, body: bytes) -> None:
        if len(body) > MAX_RESPONSE_BODY:
            status = 500
            body = _RESPONSE_TOO_LARGE
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            # Eine Verbindung trägt genau eine Anfrage. Damit kann kein Client
            # einen der wenigen Worker nach der Antwort durch untätiges
            # Keep-Alive festhalten, und ein abgewiesener Rumpf wird nie als
            # Anfang der nächsten Anfrage fehlgedeutet.
            self.send_header("Connection", "close")
            self.close_connection = True
            self.end_headers()
            if body:
                self.wfile.write(body)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            # Der Client oder ``stop`` hat die Leitung abgebrochen. Die
            # Antwort wird nicht erneut versucht und hält keinen Worker fest.
            pass

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
        self._server: _BoundedHTTPServer | None = None
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
        if isinstance(self._bridge, WindowBridge):
            self._bridge.start_accepting()
        handler = type("_Bound", (_Handler,), {"bridge": self._bridge})
        self._server = _BoundedHTTPServer((remote.HOST, self._port), handler)
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, name="mcp", daemon=True)
        self._thread.start()
        _log.info("mcp server listening on %s:%d", remote.HOST, self._port)

    def stop(self) -> None:
        if self._server is None:
            return
        server = self._server
        server.begin_shutdown()
        if isinstance(self._bridge, WindowBridge):
            self._bridge.cancel_pending()
        server.shutdown()
        server.abort_active()
        server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._server = None
        self._thread = None
        _log.info("mcp server stopped")


class _BoundedHTTPServer(ThreadingHTTPServer):
    """Standardserver mit festem Arbeiterbudget und abbrechbaren Sockeln."""

    daemon_threads = True
    block_on_close = False
    request_queue_size = MAX_WORKERS

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler]) -> None:
        self._workers = threading.BoundedSemaphore(MAX_WORKERS)
        self._busy_workers = threading.BoundedSemaphore(MAX_BUSY_WORKERS)
        self._active: set[socket.socket] = set()
        self._busy_active: set[socket.socket] = set()
        self._active_lock = threading.Lock()
        self._stopping = threading.Event()
        super().__init__(address, handler)

    def process_request(self, request: _SocketRequest, client_address: Any) -> None:
        assert isinstance(request, socket.socket)
        if self._stopping.is_set():
            self.shutdown_request(request)
            return
        if not self._workers.acquire(blocking=False):
            self._start_busy_rejection(request)
            return
        with self._active_lock:
            self._active.add(request)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._finished(request)
            self.shutdown_request(request)
            raise

    def process_request_thread(self, request: _SocketRequest, client_address: Any) -> None:
        assert isinstance(request, socket.socket)
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._finished(request)

    def _finished(self, request: socket.socket) -> None:
        with self._active_lock:
            if request not in self._active:
                return
            self._active.remove(request)
        self._workers.release()

    def begin_shutdown(self) -> None:
        """Vor dem Serverstopp keine neue Anfrage mehr zu einem Worker geben."""
        self._stopping.set()

    def _start_busy_rejection(self, request: socket.socket) -> None:
        """Übergibt eine Ablehnung an einen der fest begrenzten Nebenworker."""
        if not self._busy_workers.acquire(blocking=False):
            self.shutdown_request(request)
            return
        with self._active_lock:
            self._busy_active.add(request)
        busy_thread = threading.Thread(
            target=self._reject_busy,
            args=(request,),
            name="mcp-busy",
            daemon=True,
        )
        try:
            busy_thread.start()
        except BaseException:
            with self._active_lock:
                self._busy_active.discard(request)
            self._busy_workers.release()
            self.shutdown_request(request)
            raise

    def _reject_busy(self, request: socket.socket) -> None:
        """Liest kurz und gedeckelt nach, ohne den Annahmethread zu berühren."""
        deadline = time.monotonic() + BUSY_REJECT_TIMEOUT
        received = bytearray()
        expected = 0
        try:
            while len(received) < BUSY_DRAIN_LIMIT:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                request.settimeout(remaining)
                chunk = request.recv(min(4096, BUSY_DRAIN_LIMIT - len(received)))
                if not chunk:
                    break
                received.extend(chunk)
                marker = received.find(b"\r\n\r\n")
                if marker < 0:
                    continue
                if expected == 0:
                    expected = self._busy_request_size(received, marker)
                if len(received) >= expected:
                    break
            request.sendall(
                b"HTTP/1.1 503 Service Unavailable\r\n"
                b"Content-Length: 0\r\nConnection: close\r\n\r\n"
            )
        except OSError:
            pass
        finally:
            with self._active_lock:
                self._busy_active.discard(request)
            self.shutdown_request(request)
            self._busy_workers.release()

    @staticmethod
    def _busy_request_size(received: bytearray, marker: int) -> int:
        """Gesamtgröße einer kanonischen kleinen Anfrage, sonst nur Kopf."""
        header_end = marker + 4
        for line in received[:marker].split(b"\r\n")[1:]:
            name, separator, value = line.partition(b":")
            value = value.strip()
            if (
                separator
                and name.strip().lower() == b"content-length"
                and value.isdigit()
                and len(value) <= len(str(BUSY_DRAIN_LIMIT))
            ):
                length = int(value)
                if length <= BUSY_DRAIN_LIMIT - header_end:
                    return header_end + length
        return header_end

    def abort_active(self) -> None:
        """Alle gerade lesenden oder schreibenden Leitungen abbrechen."""
        with self._active_lock:
            active = tuple(self._active | self._busy_active)
        for request in active:
            with suppress(OSError):
                request.shutdown(socket.SHUT_RDWR)
            with suppress(OSError):
                request.close()
