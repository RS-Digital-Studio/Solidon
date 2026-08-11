"""Ein Modell aus dem Netz holen (Bauplan §16.3, §17.1, §32).

Gefahren wird gegen einen eigenen Server im selben Prozess — kein Test dieser
Suite greift ins echte Netz, sonst hinge ein grüner Lauf an einer fremden
Maschine und einer Leitung.
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.errors import ExternalToolError, ValidationError
from app.core.ingest.fetch import ALLOWED_SUFFIXES, check_url, fetch_model

MESHES = Path(__file__).parent / "data" / "meshes"


class _Handler(http.server.BaseHTTPRequestHandler):
    """Antwortet je nach Pfad — jede Zeile davon ist ein Fall aus dem Modul."""

    def do_GET(self) -> None:
        payload = (MESHES / "cube_clean.stl").read_bytes()
        if self.path.startswith("/seite"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body>Modellseite</body></html>")
            return
        if self.path.startswith("/ohne-endung"):
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/benannt"):
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="halterung.stl"')
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/fehlt"):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "model/stl")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object) -> None:
        """Der Testlauf ist kein Zugriffsprotokoll."""


@pytest.fixture
def server() -> Iterator[str]:
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def test_a_model_arrives_with_its_provenance(server: str) -> None:
    """§16.3: Woher eine Datei kam, gehört zu ihr — nicht in ein Gedächtnis."""
    fetched = fetch_model(f"{server}/wuerfel.stl")

    assert fetched.name == "wuerfel.stl"
    assert fetched.payload.startswith(b"solid") or len(fetched.payload) > 80
    assert fetched.url.endswith("/wuerfel.stl")
    assert fetched.retrieved  # ISO-Zeitpunkt, nicht leer


def test_the_server_may_name_the_file(server: str) -> None:
    """Content-Disposition schlägt den Pfad — dort steht der Name, den der
    Anbieter meint."""
    assert fetch_model(f"{server}/benannt?id=17").name == "halterung.stl"


def test_progress_is_reported(server: str) -> None:
    seen: list[float] = []
    fetch_model(f"{server}/wuerfel.stl", progress=lambda share, _text: seen.append(share))

    assert seen, "ohne Fortschritt steht die Statusleiste still"
    assert max(seen) == pytest.approx(1.0)


def test_a_web_page_is_not_a_model(server: str) -> None:
    """Der Normalfall beim Kopieren aus dem Browser — und er bekommt eine
    Meldung, die weiterhilft (Regel 17)."""
    with pytest.raises(ValidationError) as raised:
        fetch_model(f"{server}/seite.stl")

    assert raised.value.values["constraint"] == "web_page"
    assert raised.value.suggestions, "ein Fehler endet nie mit „fehlgeschlagen\u201c"


def test_an_unknown_format_is_refused_before_anything_is_read(server: str) -> None:
    with pytest.raises(ValidationError) as raised:
        fetch_model(f"{server}/ohne-endung")

    assert raised.value.values["constraint"] == "unknown_format"


def test_a_missing_file_says_what_the_server_said(server: str) -> None:
    with pytest.raises(ExternalToolError) as raised:
        fetch_model(f"{server}/fehlt.stl")

    assert raised.value.values["status"] == 404


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/Windows/win.ini",
        "ftp://example.invalid/teil.stl",
        "javascript:alert(1)",
        "http://",
    ],
)
def test_only_http_gets_through(url: str) -> None:
    """§32: Eine Adresse aus der Zwischenablage ist kein Ort, an dem man das
    Dateisystem öffnet."""
    with pytest.raises(ValidationError):
        check_url(url)


def test_the_readable_formats_are_the_same_ones_the_drop_area_takes() -> None:
    """Zwei Listen, die auseinanderlaufen, sind eine Frage der Zeit."""
    from app.core.geom.mesh import READABLE_SUFFIXES

    assert set(READABLE_SUFFIXES) <= set(ALLOWED_SUFFIXES)
    assert ".step" in ALLOWED_SUFFIXES
