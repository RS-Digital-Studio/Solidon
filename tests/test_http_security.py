"""Missbrauchsproben für die gemeinsame HTTP- und Protokollgrenze."""

from __future__ import annotations

import io
import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core import discover, support, updates
from app.core.backends import llm
from app.core.http import (
    RejectRedirects,
    ResponseDeadlineError,
    ResponseTooLargeError,
    apply_header_deadline,
    deadline_after,
    read_limited,
    validate_download_redirect,
    validate_http_url,
)
from app.core.json_boundary import StrictJsonError
from app.core.log import _OpFormatter, redact
from tools import check_activation, licence_admin, upload_website


class _Clock:
    """Eine monotone Uhr, die nur der Antwortstrom weiterschaltet."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _Body:
    """Ein begrenzbarer Antwortstrom für Byte- und Fristproben."""

    def __init__(self, body: bytes, *, clock: _Clock | None = None, step: float = 0.0) -> None:
        self.body = body
        self.headers: dict[str, str] = {}
        self.clock = clock
        self.step = step
        self.timeouts: list[float] = []

    def read(self, size: int = -1) -> bytes:
        if self.clock is not None:
            self.clock.now += self.step
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk

    def set_read_timeout(self, seconds: float) -> None:
        self.timeouts.append(seconds)


_HANG_SECONDS = 30.0
"""Ab wann ein Stillstand in diesen Tests als Hänger gilt.

Ein reiner Hängerschutz, keine Messung. Er begrenzt das Warten auf einen
angehaltenen Sendefaden, die Stille eines Gegenübers vor einem späten Byte und
jedes Zeitlimit je Lesegriff, das nicht selbst geprüft wird. ``join`` kehrt
zurück, sobald der Faden endet, und ein Sender, den der Test beim Abbruch
anhält, wartet seine Stille nie aus. Die Grenze kostet also nur Zeit, wenn
wirklich etwas hängt. Ein Läufer, der einen Faden einige Sekunden nicht
rechnen lässt (in der CI gemessen: 1,96 s), reißt sie nicht.
"""


def test_limited_reader_accepts_the_boundary_and_rejects_one_more_byte() -> None:
    clock = _Clock()
    assert (
        read_limited(
            _Body(b"1234"),
            limit=4,
            deadline=deadline_after(1.0, timer=clock),
            timer=clock,
        )
        == b"1234"
    )

    with pytest.raises(ResponseTooLargeError) as raised:
        read_limited(
            _Body(b"12345"),
            limit=4,
            deadline=deadline_after(1.0, timer=clock),
            timer=clock,
        )
    assert raised.value.received == 5


def test_a_trickling_response_cannot_restart_the_total_deadline() -> None:
    clock = _Clock()
    body = _Body(b"abc", clock=clock, step=0.6)

    with pytest.raises(ResponseDeadlineError):
        read_limited(
            body,
            limit=10,
            deadline=deadline_after(1.0, timer=clock),
            timer=clock,
        )

    assert body.timeouts[0] == pytest.approx(1.0)
    assert body.timeouts[1] == pytest.approx(0.4)


@pytest.mark.parametrize(
    "url",
    (
        "https://name:kennwort@example.org/antwort",
        "https://example.org/antwort#zugang",
        "https://example.org/ant wort",
        "https://example.org\\@evil.invalid/antwort",
    ),
)
def test_http_urls_reject_ambiguous_or_secret_authority_data(url: str) -> None:
    with pytest.raises(ValueError):
        validate_http_url(url, allow_http=False)


def test_a_public_download_cannot_redirect_into_a_private_network_or_downgrade() -> None:
    with pytest.raises(ValueError):
        validate_download_redirect(
            "https://example.org/teil.stl",
            "http://example.org/teil.stl",
        )
    with pytest.raises(ValueError):
        validate_download_redirect(
            "https://example.org/teil.stl",
            "https://127.0.0.1/teil.stl",
        )


def test_service_openers_reject_redirects_before_credentials_can_travel() -> None:
    """Gefragt wird die Fabrik, weil der Öffner je Aufruf entsteht.

    Bis zum 10.09.2026 stand hier ein modulweit geteiltes ``_OPERATOR_OPENER``.
    Seit die Gesamtfrist auch über Statuszeile und Kopfzeilen gilt, gehört der
    Öffner dem einzelnen Aufruf — die Frist steckt in seiner Antwortklasse, und
    ein geteilter trüge nach dem ersten Aufruf für immer dessen Frist.
    """
    opener = discover.opener_for("https://example.org/api")
    assert any(isinstance(handler, RejectRedirects) for handler in opener.handlers)
    assert any(
        isinstance(handler, RejectRedirects)
        for handler in licence_admin._operator_opener().handlers
    )


def test_the_central_formatter_redacts_credentials_urls_and_log_injection() -> None:
    record = logging.LogRecord(
        "app.test",
        logging.WARNING,
        __file__,
        1,
        (
            "Authorization: Bearer topsecret "
            "https://alice:kennwort@example.org/a?token=abc#fragment\n"
            "X-API-Key=zweites-geheimnis"
        ),
        (),
        None,
    )
    rendered = _OpFormatter("%(message)s").format(record)

    for secret in ("topsecret", "alice", "kennwort", "abc", "fragment", "zweites-geheimnis"):
        assert secret not in rendered
    assert "https://example.org/a" in rendered
    assert "\\n" in rendered
    assert "\n" not in rendered


def test_a_traceback_keeps_its_lines_in_the_log() -> None:
    """Der Stapel wird angehängt, nicht redigiert (§33.2).

    ``redact`` ersetzt jeden Zeilenumbruch durch ``\\n`` und kappt bei tausend
    Zeichen. Über den **ganzen** Eintrag gelegt, machte es aus einem Traceback
    eine einzige, abgeschnittene Zeile — und genau die liest, wer einen
    Fehlerbericht bekommt. Die Meldung bleibt redigiert; sie ist die Stelle,
    an der ein fremder Text hineinkommt, ein Stapel ist es nicht.
    """
    import sys

    try:
        raise ValueError("etwas ging schief")
    except ValueError:
        info = sys.exc_info()

    record = logging.LogRecord("app.test", logging.ERROR, __file__, 1, "Angehalten", (), info)
    rendered = _OpFormatter("%(message)s").format(record)

    assert rendered.count("\n") >= 2, f"der Stapel kam einzeilig an: {rendered!r}"
    assert "Traceback (most recent call last)" in rendered
    assert rendered.rstrip().endswith("ValueError: etwas ging schief"), (
        f"der Stapel wurde gekappt: {rendered!r}"
    )


def test_redaction_has_a_hard_character_limit_for_foreign_content() -> None:
    assert len(redact("x" * 10_000, limit=120)) == 120


def test_llm_rejects_userinfo_before_opening_any_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = False

    def opener(_url: str) -> Any:
        nonlocal opened
        opened = True
        raise AssertionError

    monkeypatch.setattr(llm, "opener_for", opener)
    with pytest.raises(llm.BackendUnavailable):
        llm.post_json("https://name:secret@example.org/chat", {}, {})
    assert not opened


def test_llm_rejects_an_oversized_success_body(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _Body(b"x" * (llm.MAX_RESPONSE_BYTES + 1))
    answer = SimpleNamespace(
        open=lambda request, timeout: _ContextBody(body, request.full_url),
    )
    monkeypatch.setattr(llm, "opener_for", lambda _url: answer)

    with pytest.raises(llm.BackendUnavailable):
        llm.post_json("https://example.org/chat", {}, {})


class _LocalAnswer(_Body):
    """Ein Antwortstrom mit Statuszeile, wie ihn ``http.client`` zurückgibt."""

    def __init__(self, body: bytes, status: int = 200) -> None:
        super().__init__(body)
        self.status = status
        self.closed = False

    def __enter__(self) -> _LocalAnswer:
        return self

    def __exit__(self, *_args: object) -> None:
        self.closed = True


class _LocalConnection:
    """Ein ``http.client``-Ersatz für den abbrechbaren lokalen Weg."""

    def __init__(self, answer: _LocalAnswer) -> None:
        self.answer = answer
        self.sock: Any = None
        self.connected = False
        self.closed = False

    def connect(self) -> None:
        self.connected = True

    def request(self, *_args: object, **_options: object) -> None:
        assert self.connected

    def getresponse(self) -> _LocalAnswer:
        return self.answer

    def close(self) -> None:
        self.closed = True


class _NeverCancelled:
    """Ein Abbruchmarker, der nie zuschlägt — geprüft wird die Byte-Grenze."""

    @property
    def is_cancelled(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        return None


def test_the_cancelable_local_transport_rejects_an_oversized_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Auch der abbrechbare Weg zum lokalen Modell liest begrenzt.**

    Er las mit ``response.read()`` ohne Grenze und ohne Frist, während der Weg
    daneben (``post_json``) beides seit §37.2 einhält. Hinter ``127.0.0.1:11434``
    muss kein Ollama liegen — was dort antwortet, füllte sonst den
    Arbeitsspeicher, und ein Abbruch half nicht, weil das Lesen selbst nie
    zurückkam.
    """
    connection = _LocalConnection(_LocalAnswer(b"x" * (llm.MAX_RESPONSE_BYTES + 1)))
    monkeypatch.setattr(llm, "_local_connection", lambda *_a, **_o: connection)

    with pytest.raises(llm.BackendUnavailable) as raised:
        llm.post_json_local_cancelable("http://127.0.0.1:11434/api/chat", {}, {}, _NeverCancelled())
    assert isinstance(raised.value.__cause__, ResponseTooLargeError)
    assert connection.closed and connection.answer.closed


def test_the_cancelable_local_transport_redacts_a_foreign_error_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Text einer fremden Fehlerantwort wird redigiert und gedeckelt.

    Er stand ungefiltert in der Meldung und damit im Protokoll (§33.2) — ein
    Proxy, der einen Schlüssel zurückspiegelt, hätte ihn dort hinterlassen.
    """
    antwort = _LocalAnswer(
        b"Authorization: Bearer topsecret\n" + b"y" * 10_000,
        status=500,
    )
    connection = _LocalConnection(antwort)
    monkeypatch.setattr(llm, "_local_connection", lambda *_a, **_o: connection)

    with pytest.raises(llm.BackendUnavailable) as raised:
        llm.post_json_local_cancelable("http://127.0.0.1:11434/api/chat", {}, {}, _NeverCancelled())

    detail = str(raised.value.detail)
    assert "topsecret" not in detail
    assert len(detail) <= 500
    assert connection.closed and antwort.closed


class _ContextBody(_Body):
    """Ein Antwortstrom mit Kontextmanager und endgültiger URL."""

    def __init__(self, body: _Body, url: str) -> None:
        super().__init__(body.body)
        self.url = url

    def __enter__(self) -> _ContextBody:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_operator_endpoint_rejects_userinfo_query_and_fragment() -> None:
    token = "ab" * 32
    for endpoint in (
        "https://name:secret@solidon3d.de/api/operator.php",
        "https://solidon3d.de/api/operator.php?token=secret",
        "https://solidon3d.de/api/operator.php#secret",
    ):
        with pytest.raises(licence_admin.OperatorError):
            licence_admin.OperatorClient(endpoint, token)


def test_website_public_addresses_reject_embedded_credentials() -> None:
    with pytest.raises(ValueError):
        upload_website.public_url("name:secret@solidon3d.de/httpdocs", "index.html")


def test_health_check_does_not_echo_credentials_from_an_invalid_url() -> None:
    ok, message = check_activation.check(
        "https://name:secret@solidon3d.de/api/activation-health.php"
    )
    assert not ok
    assert "secret" not in message


@pytest.mark.parametrize(
    "raw",
    [
        b'{"ok":true,"protocol":NaN}',
        (b"[" * 65) + b"0" + (b"]" * 65),
    ],
)
def test_health_check_refuses_unsafe_json(
    monkeypatch: pytest.MonkeyPatch,
    raw: bytes,
) -> None:
    answer = _ContextBody(_Body(raw), check_activation.DEFAULT_URL)
    # Wie beim Support: gepatcht wird die Öffner-Funktion, seit der Öffner dem
    # einzelnen Aufruf gehört und seine Gesamtfrist mitbringt.
    monkeypatch.setattr(check_activation, "_open_health", lambda request, timeout: answer)

    ready, message = check_activation.check(check_activation.DEFAULT_URL)

    assert not ready
    assert "JSON" in message


def test_support_and_update_requests_reject_userinfo_before_opening() -> None:
    with pytest.raises(ValueError):
        support._post(
            "https://name:secret@example.org/support",
            "application/octet-stream",
            b"x",
        )
    with pytest.raises(ValueError):
        updates._get(
            "https://name:secret@solidon3d.de/version.json",
            {},
            {},
        )


def test_support_refuses_non_finite_json_from_the_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer = _ContextBody(_Body(b'{"ok":true,"value":NaN}'), "https://example.org/support")
    # Gepatcht wird die Öffner-**Funktion**, nicht mehr ein modulweit geteiltes
    # Öffner-Objekt: Seit die Sendung ihre Gesamtfrist auch über die Kopfzeilen
    # legt, muss der Öffner dem Aufruf gehören (`http.apply_header_deadline`).
    # Zwischenzeitlich zeigte dieser Test, was ein verfehlter Testzugang
    # kostet — der Aufruf ging an das echte example.org und kam mit 405 zurück.
    monkeypatch.setattr(support, "_open_support", lambda request, timeout: answer)

    with pytest.raises(ValueError):
        support._post("https://example.org/support", "application/octet-stream", b"x")


def test_website_content_comparison_rejects_a_body_larger_than_announced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    local = tmp_path / "index.html"
    local.write_bytes(b"a")
    answer = _ContextBody(_Body(b"ab"), "https://solidon3d.de/index.html")
    monkeypatch.setattr(upload_website, "LOCAL_ROOT", tmp_path)
    monkeypatch.setattr(upload_website, "_open_public", lambda request, timeout: answer)

    assert upload_website.differs("solidon3d.de/httpdocs", local, 1)


@pytest.mark.parametrize(
    "problem_factory",
    [
        lambda: urllib.error.URLError("nicht erreichbar"),
        lambda: urllib.error.HTTPError(
            "https://solidon3d.de/index.html", 403, "Forbidden", {}, None
        ),
    ],
)
def test_website_content_comparison_fails_closed_on_transport_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    problem_factory: Callable[[], BaseException],
) -> None:
    local = tmp_path / "index.html"
    local.write_bytes(b"a")
    # HTTPError besitzt einen Antwortstrom. Erst im Test erzeugen, damit
    # schon eine abgebrochene Sammlung keinen ungeschlossenen Strom hält.
    problem = problem_factory()
    monkeypatch.setattr(upload_website, "LOCAL_ROOT", tmp_path)
    monkeypatch.setattr(
        upload_website,
        "_open_public",
        lambda request, timeout: (_ for _ in ()).throw(problem),
    )

    assert upload_website.differs("solidon3d.de/httpdocs", local, 1)
    if isinstance(problem, urllib.error.HTTPError):
        assert problem.closed


def test_website_upload_refuses_an_ip_before_sending_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = False

    def ftp_tls(*_args: object, **_kwargs: object) -> object:
        nonlocal opened
        opened = True
        raise AssertionError("vor der Hostnamenprüfung darf keine FTPS-Sitzung entstehen")

    monkeypatch.setattr(upload_website.ftplib, "FTP_TLS", ftp_tls)

    with pytest.raises(SystemExit, match="Hostname"):
        upload_website.connect(
            {"host": "192.0.2.1", "port": 21, "user": "name", "password": "geheim"}
        )

    assert not opened


class _VersionFtp:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.timeout = 30.0

    def transfercmd(self, command: str) -> Any:
        assert command.endswith("/version.json")
        return _VersionData(self.body)

    def voidresp(self) -> str:
        return "226 Transfer complete"


class _VersionData:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def settimeout(self, _seconds: float) -> None:
        return

    def recv(self, size: int) -> bytes:
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk

    def close(self) -> None:
        return


def _valid_remote_version() -> dict[str, object]:
    return {
        "version": "1.2.3",
        "signature": "0" * 128,
        "packages": {
            "windows": {
                "file": "Solidon3D-Setup-1.2.3.exe",
                "url": "https://solidon3d.de/api/count.php?f=Solidon3D-Setup-1.2.3.exe",
                "size": 123,
                "sha256": "0" * 64,
            }
        },
    }


@pytest.mark.parametrize(
    "raw",
    [
        b'{"version":NaN}',
        (b"[" * 65) + b"0" + (b"]" * 65),
    ],
)
def test_remote_version_refuses_unsafe_json(raw: bytes) -> None:
    with pytest.raises(StrictJsonError):
        upload_website.remote_version(_VersionFtp(raw), "httpdocs")  # type: ignore[arg-type]


def test_remote_version_stops_at_its_transfer_limit() -> None:
    body = b"x" * (upload_website.MAX_REMOTE_VERSION_BYTES + 1)

    with pytest.raises(ResponseTooLargeError):
        upload_website.remote_version(_VersionFtp(body), "httpdocs")  # type: ignore[arg-type]


def test_remote_version_stops_at_its_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Datenkanal endet an der Gesamtfrist, nicht am Zeitlimit seines Sockets.

    Drei Bytes kommen vor der Frist. Danach schweigt der Datenkanal
    :data:`_HANG_SECONDS` lang, länger als die Frist (der Socket hier hat gar
    kein eigenes Zeitlimit, ``retrbinary`` hatte früher dreißig Sekunden je
    Lesegriff), und schickt erst dann ein spätes Byte. Endet der Lesegriff an
    der Frist, hält der Test den Sender an, bevor es geht. Behält der
    Datensocket sein eigenes Zeitlimit, wartet der Lesegriff auf das späte
    Byte, und erst die Prüfung danach bricht ab.

    Beobachtet wird die Marke, nicht die Uhr: Eine Grenze von einer Sekunde ab
    Fadenstart war zugleich zu eng für einen überlasteten Läufer und zu weit
    für den Fehler, der nach 0,3 s abbrach. Sonst wird der Test nur rot, wenn
    der Leser so lange nicht zurückkommt; die Meldung nennt beide Ursachen.
    """
    receiving, sending = socket.socketpair()
    stop = threading.Event()
    late_sent = threading.Event()

    class SlowFtp:
        timeout = 30.0

        def transfercmd(self, command: str) -> socket.socket:
            assert command.endswith("/version.json")
            return receiving

        def voidresp(self) -> str:
            raise AssertionError("nach abgelaufener Gesamtfrist darf voidresp nicht folgen")

    def trickle() -> None:
        try:
            for _part in range(3):
                sending.sendall(b"x")
                if stop.wait(0.015):
                    return
            if stop.wait(_HANG_SECONDS):
                return
            late_sent.set()
            sending.sendall(b"x")
        except OSError:
            pass
        finally:
            sending.close()

    monkeypatch.setattr(upload_website, "PUBLIC_TIMEOUT_SECONDS", 0.08)
    thread = threading.Thread(target=trickle, daemon=True)
    thread.start()
    try:
        with pytest.raises(ResponseDeadlineError):
            upload_website.remote_version(SlowFtp(), "httpdocs")  # type: ignore[arg-type]
    finally:
        stop.set()
        late = late_sent.is_set()
        thread.join(_HANG_SECONDS)
    assert not thread.is_alive()
    assert not late, (
        "Das Zeitlimit des Datensockets hat die Gesamtfrist verlängert"
        f" (oder der Leser stand {_HANG_SECONDS:.0f} s lang)"
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"unexpected": True}),
        lambda payload: payload.update({"version": 123}),
        lambda payload: payload.update({"packages": []}),
        lambda payload: payload.pop("signature"),
        lambda payload: payload["packages"].update({"plan9": {}}),
        lambda payload: payload["packages"]["windows"].update({"command": "calc"}),
        lambda payload: payload["packages"]["windows"].pop("sha256"),
        lambda payload: payload["packages"]["windows"].update({"size": True}),
        lambda payload: payload["packages"]["windows"].update(
            {"url": "https://name:secret@solidon3d.de/Paket.exe"}
        ),
    ],
)
def test_remote_version_refuses_every_malformed_manifest_before_package_use(
    mutate: Any,
) -> None:
    payload = _valid_remote_version()
    mutate(payload)

    with pytest.raises(StrictJsonError):
        upload_website.remote_version(
            _VersionFtp(json.dumps(payload).encode("utf-8")),  # type: ignore[arg-type]
            "httpdocs",
        )


def test_remote_version_accepts_the_closed_package_schema() -> None:
    payload = _valid_remote_version()

    assert (
        upload_website.remote_version(  # type: ignore[arg-type]
            _VersionFtp(json.dumps(payload).encode("utf-8")),
            "httpdocs",
        )
        == payload
    )


class _MalformedVersionFtp(_VersionFtp):
    def mlsd(self, _path: str, facts: list[str] | None = None) -> object:
        raise AssertionError("bei ungültigem Manifest darf die Löschliste nicht gelesen werden")


def test_cleanup_stops_before_reading_packages_from_a_malformed_manifest() -> None:
    payload = _valid_remote_version()
    payload["packages"]["windows"]["size"] = "123"
    session = _MalformedVersionFtp(json.dumps(payload).encode("utf-8"))

    stale, reason = upload_website.stale_packages(session, "httpdocs")  # type: ignore[arg-type]

    assert stale == []
    assert "ungültiges Schema" in reason


def test_http_error_body_is_bounded_before_an_llm_detail_is_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = urllib.error.HTTPError(
        "https://example.org/chat",
        401,
        "Unauthorized",
        {},
        io.BytesIO(b'{"error":"Bearer topsecret"}' + b"x" * llm.MAX_ERROR_BYTES),
    )
    monkeypatch.setattr(
        llm,
        "opener_for",
        lambda _url: SimpleNamespace(open=lambda request, timeout: (_ for _ in ()).throw(error)),
    )

    with pytest.raises(llm.BackendUnavailable) as raised:
        llm.post_json("https://example.org/chat", {"Authorization": "Bearer key"}, {})

    assert "topsecret" not in str(raised.value.detail)


def test_the_upload_tool_accepts_the_version_file_we_publish() -> None:
    """Was ``make_download.py`` schreibt, muss ``upload_website`` annehmen.

    **Der Fall, aus dem dieser Test entstand** (Auslieferung 0.3.1): Der
    Download-Kasten schreibt seit einer Weile ein Feld ``changes_total``, und
    ``_VERSION_FIELDS`` kannte es nicht. Die Prüfung ist mit Absicht
    geschlossen — ein unbekanntes Feld lässt sie scheitern —, also wies sie
    jede aktuelle ``version.json`` ab. Gelöscht wurde dadurch nichts, das ist
    die sichere Richtung; aber ``--alte-pakete`` war blind, und alte Pakete
    blieben auf dem Server liegen.

    Aufgefallen ist es nur, weil ``--nachpruefen`` eine Minute vorher fünf
    Pakete aus derselben Datei gelesen hatte. Die Meldung selbst
    („nennt kein einziges Paket oder hat ein ungültiges Schema") liest sich wie
    eine kaputte Datei und nicht wie ein veraltetes Werkzeug.

    Geprüft wird gegen die **eingecheckte** Datei und nicht Feldliste gegen
    Feldliste: Zwei Listen zu vergleichen hieße anzunehmen, dass eine von
    beiden stimmt.
    """
    published = Path(upload_website.__file__).resolve().parent.parent / "website" / "version.json"
    payload = json.loads(published.read_text(encoding="utf-8"))
    assert payload.get("packages"), (
        "die veröffentlichte version.json führt kein Paket — make_download.py hat sie geleert?"
    )

    upload_website._validate_remote_version(payload)


def test_the_read_timeout_caps_a_single_read_below_the_total_deadline() -> None:
    """CORE-28: Ohne eigene Grenze war der Socket-Timeout die Restzeit bis zur
    Gesamtfrist — eine großzügige Frist für ein großes Paket hätte auch einen
    Stillstand so lange stehen lassen. ``read_timeout`` deckelt jede
    Leseoperation für sich."""
    from app.core.http import iter_limited

    clock = _Clock()
    body = _Body(b"abcdef", clock=clock, step=0.0)

    received = b"".join(
        iter_limited(
            body,
            limit=10,
            deadline=deadline_after(1000.0, timer=clock),
            timer=clock,
            chunk_size=3,
            read_timeout=60.0,
        )
    )

    assert received == b"abcdef"
    assert body.timeouts and all(seconds == pytest.approx(60.0) for seconds in body.timeouts)


class _Lockstep:
    """Ein Gegenüber, das je Lesegriff des Lesers ein Byte schickt, und erst ab der Frist.

    Ein Sender nach eigener Uhr zählt Fadenzeiten mit. Steht nur der Leser,
    sammeln sich die Bytes, und ein einziger Lesegriff holt danach eine ganze
    Zeile: rot, obwohl die Frist gilt. Tröpfelt der Sender schon, bevor die
    Frist entsteht, zählen Bytes mit, die vor ihr lagen. Hier geht das nächste
    Byte erst, wenn der Leser wieder an seinem Socket liest, frühestens
    ``pace`` Sekunden danach und erst nach :meth:`open`.

    Wie viele Bytes bis zum Abbruch gehen, hängt damit nur daran, wie viele
    Lesegriffe die Frist zulässt. Ein Stillstand, gleich welches Fadens, senkt
    die Zahl und hebt sie nie. ``_socket_deadline`` prüft die Frist **vor** dem
    Lesegriff, den es umhüllt; nach dem Abbruch fragt also niemand mehr nach.
    :attr:`sent` wächst vor dem Senden und ist deshalb eine obere Schranke
    dessen, was der Leser haben kann. :meth:`clock` zählt die Lesegriffe
    selbst, als Uhr für eine Frist, die gar nicht an der Wanduhr hängt.
    """

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        reader: socket.socket,
        writer: socket.socket,
        *,
        pace: float = 0.02,
    ) -> None:
        self.pace = pace
        self._writer = writer
        self._reads = 0
        self._opened = threading.Event()
        self._demand = threading.Event()
        self._stop = threading.Event()
        self.sent: list[int] = []
        original = socket.SocketIO.readinto

        def asking(stream: socket.SocketIO, buffer: Any) -> int | None:
            if vars(stream).get("_sock") is reader:
                self._reads += 1
                self._demand.set()
            return original(stream, buffer)

        monkeypatch.setattr(socket.SocketIO, "readinto", asking)

    def clock(self) -> float:
        """Die Zahl der bisherigen Lesegriffe am Leser, als ``timer`` einer Frist."""
        return float(self._reads)

    def open(self) -> None:
        """Ab hier wird gesendet; ein Lesegriff von vorher gilt nicht."""
        self._demand.clear()
        self._opened.set()

    def trickle(self, payload: bytes) -> None:
        """Schickt ``payload`` byteweise im Gleichschritt mit dem Leser (im Sendefaden)."""
        if not self._opened.wait(_HANG_SECONDS):
            return
        for value in payload:
            while not self._demand.wait(0.05):
                if self._stop.is_set():
                    return
            self._demand.clear()
            if self._stop.wait(self.pace):
                return
            self.sent.append(value)
            self._writer.sendall(bytes([value]))

    def halt(self) -> int:
        """Hält den Sender an und nennt, wie viele Bytes er bis dahin freigegeben hat."""
        self._stop.set()
        self._opened.set()
        return len(self.sent)


@pytest.mark.parametrize("delay_writer_start", [False, True])
def test_a_trickling_real_http_response_stops_at_the_deadline_not_at_the_block(
    monkeypatch: pytest.MonkeyPatch, delay_writer_start: bool
) -> None:
    """Gesamtreview 05.09.2026, CORE-06: ``HTTPResponse.read(n)`` füllt seinen
    Block aus vielen Socket-Lesezugriffen, und der Socket-Timeout beginnt bei
    jedem neu. Ein Gegenüber, das alle 10 ms ein Byte schickt, hielt eine
    Gesamtfrist von 150 ms so bis zum letzten angekündigten Byte offen. Ein
    prozesslokales Socketpaar, kein Netz.

    Ein Byte liegt bereit; die übrigen 79 kommen im Gleichschritt mit dem Leser
    (:class:`_Lockstep`), je Lesegriff eines und erst ab der Frist. Die Frist
    läuft auf einer Uhr, die Lesegriffe zählt, und lässt zwanzig davon zu: Eine
    Wandzeitfrist von 0,4 s war rot, sobald der Leser direkt nach ihrem Beginn
    so lange stand, denn dann kam vor ihr nichts an, gleich wie gelesen wurde.
    Die Gegenprobe verzögert ``Thread.start`` absichtlich um 250 ms; diese
    Testvorbereitung darf nicht als verstrichene Netzwerkzeit gelten. Mit der
    Zähluhr und dem Tor in :meth:`_Lockstep.open` gilt das durch die Bauart,
    der zweite Fall wiederholt den Lauf also nur mit verzögertem Senderstart.
    Gemessen wird, ob der Leser **vor der Frist etwas liefert**: Ein einzelner
    Lesezugriff gibt bereits gelesene Stücke zurück, der gefüllte Block
    dagegen wartet auf den ganzen angekündigten Körper, und die Frist bricht
    ihn ab, bevor er etwas liefert.
    Der Sender taugt nicht als Maß — auf Windows nimmt der Kern Sendungen an
    ein geschlossenes Gegenüber still an —, und auch nicht, was der Abbruch
    verschluckt: Das zuletzt gelesene Stück wird in beiden Fassungen nicht mehr
    geliefert.
    """
    import http.client

    from app.core.http import iter_limited

    left, right = socket.socketpair()
    lockstep = _Lockstep(monkeypatch, left, right, pace=0.0)
    total = 80
    reads_allowed = 20
    writer_ready = threading.Event()

    def trickle() -> None:
        try:
            writer_ready.set()
            lockstep.trickle(b"x" * (total - 1))
        except OSError:
            pass
        finally:
            right.close()

    writer = threading.Thread(target=trickle, daemon=True)
    right.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 80\r\n\r\nx")
    start_requested = time.monotonic()
    if delay_writer_start:
        original_start = threading.Thread.start

        def delayed_start(thread: threading.Thread) -> None:
            original_start(thread)
            if thread is writer:
                time.sleep(0.25)

        monkeypatch.setattr(threading.Thread, "start", delayed_start)
    writer.start()
    start_delay = time.monotonic() - start_requested
    if delay_writer_start:
        assert start_delay >= 0.25, "die Gegenprobe muss die Thread-Einrichtung verschieben"
    assert writer_ready.wait(_HANG_SECONDS), "der Schreiber muss vor der Lesefrist bereit sein"

    response = http.client.HTTPResponse(left, method="GET")
    received = bytearray()
    try:
        response.begin()
        deadline = deadline_after(reads_allowed, timer=lockstep.clock)
        lockstep.open()
        with pytest.raises(ResponseDeadlineError):
            for chunk in iter_limited(response, limit=100, deadline=deadline, timer=lockstep.clock):
                received.extend(chunk)
    finally:
        lockstep.halt()
        response.close()
        left.close()
        right.close()
        writer.join(_HANG_SECONDS)
    assert not writer.is_alive()

    assert received, "vor der Frist kam nichts an — der Leser wartete auf den ganzen Block"
    assert len(received) < total, "und die Frist galt, nicht der angekündigte Block"


@pytest.mark.parametrize("part", ["extension", "trailer"])
def test_chunk_metadata_cannot_restart_the_network_deadline(
    monkeypatch: pytest.MonkeyPatch, part: str
) -> None:
    """Auch gültige HTTP-Metadaten dürfen die absolute Frist nicht umgehen.

    Gezählt, nicht gemessen: Auf einem überlasteten Intel-Mac-Läufer riss eine
    Wandzeitgrenze (1,96 s statt 1 s), obwohl ``_socket_deadline`` jeden
    Lesegriff begrenzt. Ob dort beide Fäden standen oder nur der Leser, zeigt
    die Zahl nicht; der Gleichschritt (:class:`_Lockstep`) trägt beide Fälle.
    Die langsame Zeile kommt erst ab der Frist und je Lesegriff ein Byte.
    Verlängerte die Metadatenzeile die Frist, käme der Abbruch erst nach ihrem
    Zeilenende.
    """
    import http.client

    left, right = socket.socketpair()
    lockstep = _Lockstep(monkeypatch, left, right)
    prefix = b"" if part == "extension" else b"1\r\nx\r\n0\r\n"
    slow = (
        b"1;extension=abcdefghijklmnopqrst\r\nx\r\n0\r\n\r\n"
        if part == "extension"
        else b"X-Trailer: abcdefghijklmnopqrst\r\n\r\n"
    )

    def send() -> None:
        try:
            right.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + prefix)
            lockstep.trickle(slow)
        except OSError:
            pass
        finally:
            right.close()

    writer = threading.Thread(target=send, daemon=True)
    writer.start()
    response = http.client.HTTPResponse(left)
    try:
        response.begin()
        deadline = deadline_after(0.08)
        lockstep.open()
        with pytest.raises(ResponseDeadlineError):
            read_limited(response, limit=100, deadline=deadline)
    finally:
        released = lockstep.halt()
        response.close()
        left.close()
        writer.join(_HANG_SECONDS)
    assert not writer.is_alive()
    line_end = slow.index(b"\r\n") + 2
    assert released < line_end, "Metadaten haben die Gesamtfrist bis zum Zeilenende verlängert"


def _loopback_pair() -> tuple[socket.socket, socket.socket]:
    """Ein verbundenes TCP-Paar über die Loopback-Schnittstelle.

    ``socket.socketpair()`` wäre kürzer, liefert auf Linux und macOS aber ein
    Paar aus AF_UNIX — und ``http.client.connect`` setzt auf der Verbindung, die
    es bekommt, ``TCP_NODELAY``. Ein Unix-Socket weist das ab, Linux mit
    ``Errno 95`` und macOS mit ``Errno 102``, und der Test scheiterte an seiner
    eigenen Nachstellung statt an der Frist, die er messen will.

    Auf dieser Maschine konnte das nie auffallen: Python kennt unter Windows
    kein AF_UNIX und bildet ``socketpair`` selbst über TCP nach. Der Fall, den
    der Test meint, ist ohnehin TCP — also stellt er ihn auch so her.
    """
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        near = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        near.connect(listener.getsockname())
        far, _peer = listener.accept()
    finally:
        listener.close()
    return near, far


def _connecting_to(sock: socket.socket) -> Callable[..., socket.socket]:
    """Ein ``socket.create_connection``, das ``sock`` liefert, samt Zeitlimit des Aufrufers.

    Wie das echte: ``http.client`` reicht das Zeitlimit des Öffners nur hier
    durch, und nur hier kommt es an den Socket. Eine Attrappe, die es
    verwirft, ließe den Socket ohne Zeitlimit warten, und ein Test über das
    Zeitlimit prüfte etwas, das es gar nicht gab.
    """

    def connect(_address: object, timeout: float, *_rest: object) -> socket.socket:
        sock.settimeout(timeout)
        return sock

    return connect


@pytest.mark.parametrize("part", ["status", "headers"])
def test_initial_http_lines_share_the_absolute_deadline(
    monkeypatch: pytest.MonkeyPatch, part: str
) -> None:
    """Die Frist beginnt vor dem ersten Antwortbyte, nicht erst am Inhalt.

    Gezählt, nicht gemessen, wie bei den Chunk-Metadaten: Das Gegenüber
    schickt die langsame Zeile im Gleichschritt mit dem Leser
    (:class:`_Lockstep`) und beginnt erst nach der Anfrage, also nach der
    Frist. Hielte die Frist erst nach dem Kopfblock, käme der Abbruch erst nach
    dem Zeilenende; hielte sie gar nicht, scheitert schon ``pytest.raises``.
    """
    from app.core import http

    left, right = _loopback_pair()
    lockstep = _Lockstep(monkeypatch, left, right)
    monkeypatch.setattr(http, "resolve_public_addresses", lambda *_args, **_kwargs: ("8.8.8.8",))
    monkeypatch.setattr(http, "verify_public_peer", lambda *_args: None)
    monkeypatch.setattr(socket, "create_connection", _connecting_to(left))
    payload = (
        b"HTTP/1.1 200 Long Reason Phrase\r\nContent-Length: 0\r\n\r\n"
        if part == "status"
        else b"X-Header: abcdefghijklmnopqrst\r\nContent-Length: 0\r\n\r\n"
    )

    def send() -> None:
        try:
            right.recv(4096)
            if part == "headers":
                right.sendall(b"HTTP/1.1 200 OK\r\n")
            lockstep.trickle(payload)
        except OSError:
            pass
        finally:
            right.close()

    writer = threading.Thread(target=send, daemon=True)
    writer.start()
    try:
        lockstep.open()
        with pytest.raises(ResponseDeadlineError):
            http.open_public_url("http://example.org/model", deadline=deadline_after(0.08))
    finally:
        released = lockstep.halt()
        left.close()
        writer.join(_HANG_SECONDS)
    assert not writer.is_alive()
    line_end = payload.index(b"\r\n") + 2
    assert released < line_end, (
        "die langsame Antwortzeile hat die Gesamtfrist bis zu ihrem Ende verlängert"
    )


@pytest.mark.parametrize("with_deadline", [True, False])
def test_an_opener_puts_its_headers_under_the_same_deadline(
    monkeypatch: pytest.MonkeyPatch, with_deadline: bool
) -> None:
    """Was ``open_public_url`` seit je hält, gilt jetzt auch für die übrigen Wege.

    ``OpenerDirector.open(request, timeout=…)`` begrenzt die einzelne
    Leseoperation, nicht die Gesamtdauer. Ein Gegenüber, das seine Kopfzeilen
    byteweise mit Pausen unterhalb des Zeitlimits schickt, hält die Verbindung
    beliebig lange offen — und die Frist, die der Aufrufer daneben gebildet
    hat, greift erst am Rumpf.

    Gezählt, nicht gemessen: Die Kopfzeile kommt im Gleichschritt mit dem
    Leser (:class:`_Lockstep`) und erst nach der Anfrage, also nach der Frist.
    Hielte die Frist erst nach dem Kopfblock, käme der Abbruch erst nach dem
    Zeilenende.

    **Der zweite Parameterwert ist die Gegenprobe.** Ohne
    ``apply_header_deadline`` läuft derselbe Aufruf nicht etwa in ein späteres
    Zeitlimit, er **gelingt**: Jedes Byte der Kopfzeilen kam einzeln und
    frühestens 20 ms nach dem vorigen (``pace`` von :class:`_Lockstep`),
    zusammen ein Vielfaches der Frist des ersten Zweigs. Das Zeitlimit
    (:data:`_HANG_SECONDS`) steht dabei wirklich am Socket
    (:func:`_connecting_to`). Im ersten Zweig entscheidet die Frist, im zweiten
    ist es nur Hängerschutz. Dass es die Frist auch dann nicht verlängert, wenn
    das Gegenüber ganz schweigt, prüft
    :func:`test_a_silent_peer_cannot_hold_the_headers_until_the_read_timeout`.
    """
    left, right = _loopback_pair()
    lockstep = _Lockstep(monkeypatch, left, right)
    monkeypatch.setattr(socket, "create_connection", _connecting_to(left))
    payload = b"X-Header: abcdefghijklmnopqrst\r\nContent-Length: 0\r\n\r\n"

    def send() -> None:
        try:
            right.recv(4096)
            right.sendall(b"HTTP/1.1 200 OK\r\n")
            lockstep.trickle(payload)
        except OSError:
            pass
        finally:
            right.close()

    writer = threading.Thread(target=send, daemon=True)
    writer.start()
    opener = urllib.request.build_opener(RejectRedirects())
    if with_deadline:
        apply_header_deadline(opener, deadline_after(0.08))
    request = urllib.request.Request("http://example.org/version.json")
    try:
        lockstep.open()
        if with_deadline:
            with pytest.raises(ResponseDeadlineError):
                opener.open(request, timeout=_HANG_SECONDS)
        else:
            with opener.open(request, timeout=_HANG_SECONDS) as answer:
                assert answer.status == 200
    finally:
        released = lockstep.halt()
        left.close()
        writer.join(_HANG_SECONDS)
    assert not writer.is_alive()
    if with_deadline:
        line_end = payload.index(b"\r\n") + 2
        assert released < line_end, "die Kopfzeile hat die Gesamtfrist bis zu ihrem Ende verlängert"
    else:
        assert released == len(payload), "ohne Frist kam die Antwort erst nach der letzten Zeile"


def test_a_silent_peer_cannot_hold_the_headers_until_the_read_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Jeder Lesegriff unter der Kopfzeilenfrist wartet höchstens die Restfrist.

    Die Frist vor dem Lesegriff zu prüfen genügt nicht: Ein Lesegriff, der bei
    offener Frist beginnt, wartet sonst so lange, wie der Socket es erlaubt.
    Am Öffner ist das sein Zeitlimit je Leseoperation, im Betrieb dreißig
    Sekunden, und ein Gegenüber, das nach der Anfrage schweigt, hielte die
    Kopfzeilen so weit über die Frist hinaus offen. Deshalb setzt
    ``_socket_deadline`` vor jedem Netzgriff die Restfrist am Socket.

    Beobachtet wird eine Marke, nicht die Uhr: Das Gegenüber schweigt
    :data:`_HANG_SECONDS` lang, länger als die Frist und halb so lang wie das
    Zeitlimit am Socket, und schickt erst dann ein spätes Byte. Endet der
    Lesegriff an der Frist, hält der Test den Sender an, bevor es geht. Erbt
    er das Zeitlimit, wartet er auf das späte Byte, und erst die Prüfung vor
    dem nächsten Lesegriff bricht ab. Sonst wird der Test nur rot, wenn der
    Leser so lange nicht zurückkommt; die Meldung nennt beide Ursachen.
    """
    left, right = _loopback_pair()
    stop = threading.Event()
    late_sent = threading.Event()
    monkeypatch.setattr(socket, "create_connection", _connecting_to(left))

    def send() -> None:
        try:
            right.recv(4096)
            if stop.wait(_HANG_SECONDS):
                return
            late_sent.set()
            right.sendall(b"H")
        except OSError:
            pass
        finally:
            right.close()

    writer = threading.Thread(target=send, daemon=True)
    writer.start()
    opener = urllib.request.build_opener(RejectRedirects())
    apply_header_deadline(opener, deadline_after(0.08))
    request = urllib.request.Request("http://example.org/version.json")
    try:
        with pytest.raises(ResponseDeadlineError):
            opener.open(request, timeout=2 * _HANG_SECONDS)
    finally:
        stop.set()
        late = late_sent.is_set()
        left.close()
        writer.join(_HANG_SECONDS)
    assert not writer.is_alive()
    assert not late, (
        "der Lesegriff wartete über die Frist hinaus auf das Zeitlimit des Sockets"
        f" (oder der Leser stand {_HANG_SECONDS:.0f} s lang)"
    )


@pytest.mark.parametrize(
    "raw, useful",
    [
        (b'{"ok":false,"code":"service_unavailable","error":"private-secret"}', True),
        (b'{"ok":false,"code":"private-secret"}', False),
        (b'{"ok":false,"code":"service_unavailable","x":NaN}', False),
        (b'{"ok":false,"code":"service_unavailable","x":"' + b"x" * 4096 + b'"}', False),
    ],
)
def test_health_error_body_is_bounded_and_only_known_codes_are_shown(
    monkeypatch: pytest.MonkeyPatch, raw: bytes, useful: bool
) -> None:
    stream = io.BytesIO(raw)
    error = urllib.error.HTTPError(check_activation.DEFAULT_URL, 503, "Error", {}, stream)
    monkeypatch.setattr(error, "set_read_timeout", lambda seconds: None, raising=False)

    def fail(request: object, *, timeout: float) -> None:
        raise error

    monkeypatch.setattr(check_activation, "_open_health", fail)
    ready, message = check_activation.check(check_activation.DEFAULT_URL)
    assert not ready
    assert "HTTP 503" in message
    assert ("PHP-Fehlerprotokoll" in message) is useful
    assert "private-secret" not in message
    assert stream.closed


def test_health_error_body_timeout_keeps_status_and_closes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = io.BytesIO(b"unfinished")
    error = urllib.error.HTTPError(check_activation.DEFAULT_URL, 503, "Error", {}, stream)
    monkeypatch.setattr(error, "set_read_timeout", lambda seconds: None, raising=False)

    def expire(size: int) -> bytes:
        raise TimeoutError("private-secret")

    def fail(request: object, *, timeout: float) -> None:
        raise error

    monkeypatch.setattr(error, "read1", expire)
    monkeypatch.setattr(check_activation, "_open_health", fail)
    assert check_activation.check(check_activation.DEFAULT_URL) == (
        False,
        "Aktivierungsdienst antwortet mit HTTP 503."
        " Zuerst die privaten Dateirechte prüfen: appdata 0700, activation.seed, "
        "activation.sqlite und operator.token 0600 (SITE CHMOD über FTPS)."
        " Das private Serverprotokoll prüfen.",
    )
    assert stream.closed


@pytest.mark.parametrize("status", [500, 503])
def test_health_http_status_always_suggests_a_private_operator_check(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    error = urllib.error.HTTPError(
        check_activation.DEFAULT_URL, status, "private-secret", {}, io.BytesIO(b"not json")
    )
    monkeypatch.setattr(error, "set_read_timeout", lambda seconds: None, raising=False)

    def fail(request: object, *, timeout: float) -> None:
        raise error

    monkeypatch.setattr(check_activation, "_open_health", fail)
    ready, message = check_activation.check(check_activation.DEFAULT_URL)
    assert not ready
    assert "Serverprotokoll prüfen" in message
    assert "private-secret" not in message
    if status == 503:
        assert "0700" in message and "0600" in message
        assert "activation.seed" in message and "activation.sqlite" in message
