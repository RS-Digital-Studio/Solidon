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
    opener = discover.opener_for("https://example.org/api")
    assert any(isinstance(handler, RejectRedirects) for handler in opener.handlers)
    assert any(
        isinstance(handler, RejectRedirects) for handler in licence_admin._OPERATOR_OPENER.handlers
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


class _LocalConnection:
    """Ein ``http.client``-Ersatz für den abbrechbaren lokalen Weg."""

    def __init__(self, answer: _LocalAnswer) -> None:
        self.answer = answer
        self.sock: Any = None

    def request(self, *_args: object, **_options: object) -> None:
        return None

    def getresponse(self) -> _LocalAnswer:
        return self.answer

    def close(self) -> None:
        return None


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
    monkeypatch.setattr(llm.http.client, "HTTPConnection", lambda *_a, **_o: connection)

    with pytest.raises(llm.BackendUnavailable):
        llm.post_json_local_cancelable("http://127.0.0.1:11434/api/chat", {}, {}, _NeverCancelled())


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
    monkeypatch.setattr(llm.http.client, "HTTPConnection", lambda *_a, **_o: connection)

    with pytest.raises(llm.BackendUnavailable) as raised:
        llm.post_json_local_cancelable("http://127.0.0.1:11434/api/chat", {}, {}, _NeverCancelled())

    detail = str(raised.value.detail)
    assert "topsecret" not in detail
    assert len(detail) <= 500


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
    monkeypatch.setattr(
        check_activation,
        "_HEALTH_OPENER",
        SimpleNamespace(open=lambda request, timeout: answer),
    )

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
    monkeypatch.setattr(
        support,
        "_SUPPORT_OPENER",
        SimpleNamespace(open=lambda request, timeout: answer),
    )

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
    "problem",
    [
        urllib.error.URLError("nicht erreichbar"),
        urllib.error.HTTPError("https://solidon3d.de/index.html", 403, "Forbidden", {}, None),
    ],
)
def test_website_content_comparison_fails_closed_on_transport_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    problem: BaseException,
) -> None:
    local = tmp_path / "index.html"
    local.write_bytes(b"a")
    monkeypatch.setattr(upload_website, "LOCAL_ROOT", tmp_path)
    monkeypatch.setattr(
        upload_website,
        "_open_public",
        lambda request, timeout: (_ for _ in ()).throw(problem),
    )

    assert upload_website.differs("solidon3d.de/httpdocs", local, 1)


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
    receiving, sending = socket.socketpair()
    finished = threading.Event()

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
                time.sleep(0.015)
            # Der letzte Block kommt noch vor der Gesamtfrist. Danach bleibt
            # der Datenkanal länger still als die Frist, aber deutlich kürzer
            # als der normale 30-s-Sockettimeout. Genau dort lief retrbinary
            # zuvor bis zum alten Einzeltimeout weiter.
            time.sleep(0.25)
            sending.sendall(b"x")
        except OSError:
            pass
        finally:
            sending.close()
            finished.set()

    monkeypatch.setattr(upload_website, "PUBLIC_TIMEOUT_SECONDS", 0.08)
    thread = threading.Thread(target=trickle, daemon=True)
    started = time.monotonic()
    thread.start()

    with pytest.raises(ResponseDeadlineError):
        upload_website.remote_version(SlowFtp(), "httpdocs")  # type: ignore[arg-type]

    elapsed = time.monotonic() - started
    assert elapsed < 0.24, "Der alte 30-s-Datentimeout darf die Gesamtfrist nicht verlängern"
    thread.join(timeout=1)
    assert finished.is_set()


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
    if not payload.get("packages"):
        pytest.skip("version.json führt noch keine Pakete — vor dem ersten Release ist das richtig")

    upload_website._validate_remote_version(payload)
