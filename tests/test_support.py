"""Rückmeldungen senden (Bauplan §37.2, §33.3).

Zwei Dinge werden hier festgehalten, und das zweite ist das wichtigere: dass
eine Sendung ankommt, wenn jemand sie abschickt — und dass ohne diesen Knopf
nichts hinausgeht.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest

from app.core import report as report_module
from app.core import support
from app.core.errors import AppError, UserError
from app.core.support import Attachment, Ticket
from tests.php_probe import php_executable

# --- derselbe begrenzte Protokollausschnitt für Vorschau, Versand und Ordner -----------


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"", ""),
        ("Größe geprüft\r\nLetzte Zeile\r\n".encode(), "Größe geprüft\nLetzte Zeile"),
        ("Größe geprüft\nLetzte Zeile".encode(), "Größe geprüft\nLetzte Zeile"),
        (b"erste\n\nletzte\n", "erste\n\nletzte"),
        (b"kaputt: \xff\r\nlesbar\r\n", "kaputt: \ufffd\nlesbar"),
    ],
)
def test_log_tail_preserves_text_and_normalises_line_endings(tmp_path, payload, expected):
    """Umlaute, Leerzeilen und beschädigte Bytes behalten denselben Textvertrag."""
    source = tmp_path / "solidon.log"
    source.write_bytes(payload)
    assert report_module.log_tail(source).decode("utf-8") == expected


def test_log_tail_uses_the_default_path_and_accepts_a_missing_file(tmp_path, monkeypatch):
    source = tmp_path / "solidon.log"
    monkeypatch.setattr(report_module, "log_path", lambda: source)
    assert report_module.log_tail() == b""
    source.write_bytes(b"letzte Zeile\n")
    assert report_module.log_tail() == b"letzte Zeile"


@pytest.mark.parametrize("oversized_line", [False, True])
def test_log_tail_bounds_the_bytes_actually_read(tmp_path, monkeypatch, oversized_line):
    """Die Zusage gilt den gelesenen Bytes, nicht einer zufällig schnellen SSD."""
    source = tmp_path / "solidon.log"
    if oversized_line:
        tail = "Erste vollständige Zeile\r\nLetzte vollständige Zeile\r\n"
        payload = ("ä" * report_module.LOG_TAIL_MAX_BYTES + "\r\n" + tail).encode()
    else:
        lines = [f"Teil {index}: Größe geprüft" for index in range(20_000)]
        payload = ("\r\n".join(lines) + "\r\n").encode()
        tail = "\n".join(lines[-report_module.LOG_LINES :])
    source.write_bytes(payload)
    sizes = []
    original_open = Path.open

    class MeasuredReader:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.wrapped.__exit__(*args)

        def seek(self, *args):
            return self.wrapped.seek(*args)

        def read(self, size=-1):
            assert 0 < size <= report_module.LOG_TAIL_CHUNK_BYTES
            data = self.wrapped.read(size)
            sizes.append(len(data))
            return data

    def measured_open(path, *args, **kwargs):
        wrapped = original_open(path, *args, **kwargs)
        return MeasuredReader(wrapped) if path == source and args == ("rb",) else wrapped

    monkeypatch.setattr(Path, "open", measured_open)
    result = report_module.log_tail(source).decode("utf-8")
    assert 0 < sum(sizes) <= report_module.LOG_TAIL_MAX_BYTES
    assert sum(sizes) < len(payload)
    if oversized_line:
        assert sum(sizes) == report_module.LOG_TAIL_MAX_BYTES
        assert "gekürzt" in result.splitlines()[0]
        assert result.splitlines()[1:] == tail.splitlines()
        assert "\ufffd" not in result
    else:
        assert result == tail
        assert sum(sizes) < len(tail.encode()) + 2 * report_module.LOG_TAIL_CHUNK_BYTES


def test_log_tail_marks_a_single_oversized_damaged_line(tmp_path):
    """Eine unvollständige Riesenzeile wird nicht als vollständiger Befund ausgegeben."""
    source = tmp_path / "solidon.log"
    source.write_bytes(b"\xff" * (report_module.LOG_TAIL_MAX_BYTES + 1))
    result = report_module.log_tail(source).decode("utf-8")
    assert len(result.splitlines()) == 1
    assert "gekürzt" in result
    assert "\ufffd" not in result


def test_log_tail_discards_the_partial_first_line_without_losing_recent_lines(tmp_path):
    """Auch beim Abbruch nach genügend Zeilen ist der erste Blockanfang keine Zeile."""
    source = tmp_path / "solidon.log"
    lines = [f"Prüfung {index}: vollständig" for index in range(report_module.LOG_LINES)]
    source.write_bytes(("ä" * report_module.LOG_TAIL_MAX_BYTES + "\n" + "\n".join(lines)).encode())
    assert report_module.log_tail(source).decode("utf-8") == "\n".join(lines)


def test_the_saved_log_uses_the_same_tail_bytes(tmp_path, monkeypatch):
    """Der Ordnerweg darf weder das ganze Protokoll noch einen anderen Ausschnitt lesen."""
    payload = "Ein begrenzter Ausschnitt mit Umlauten: äöü".encode()
    monkeypatch.setattr(report_module, "log_tail", lambda: payload)
    report_module._copy_log(tmp_path)
    assert (tmp_path / "protokoll.txt").read_bytes() == payload


# --- was in der Sendung steht ---------------------------------------------------------


def test_a_ticket_carries_the_versions() -> None:
    """Ohne Version und Plattform beginnt jede Antwort mit drei Rückfragen."""
    text = Ticket(message="Der Deckel sitzt schief.").as_text()

    assert "Der Deckel sitzt schief." in text
    assert "Solidon" in text
    assert "python:" in text


def test_the_subject_says_what_kind_it_is() -> None:
    ticket = Ticket(kind=support.KIND_BUG, message="Die Differenz frisst das Modell.")

    assert str(support.KIND_NAMES[support.KIND_BUG]) in ticket.subject
    assert "Die Differenz frisst das Modell." in ticket.subject


def test_attachments_are_named_in_the_text() -> None:
    """Was mitgeht, steht im Text — wer es nicht liest, hat es trotzdem gesehen."""
    ticket = Ticket(
        message="x",
        attachments=[Attachment("bildschirmfoto.png", b"\x89PNG" + b"0" * 2048)],
    )

    assert "bildschirmfoto.png" in ticket.as_text()
    assert ticket.total_bytes > 2048


# --- was vorher geprüft wird ----------------------------------------------------------


def test_an_empty_message_is_refused_with_a_way_out() -> None:
    with pytest.raises(UserError) as caught:
        support.check(Ticket(message="   "))

    assert caught.value.suggestions, "Regel 17: eine Ausnahme ohne Vorschlag ist unfertig"


def test_a_crash_goes_out_even_without_a_written_word() -> None:
    """Nach einem Absturz ist der Stapelabzug der Bericht.

    Wer dann nichts zu schreiben weiß, soll ihn trotzdem abschicken können —
    ein gesperrter Knopf wäre die Sackgasse hinter dem Programmfehler.
    """
    support.check(
        Ticket(kind=support.KIND_CRASH, message="", detail="Traceback …\nValueError: kaputt")
    )


def test_a_broken_return_address_is_refused() -> None:
    with pytest.raises(UserError):
        support.check(Ticket(message="x", contact="kein-at-zeichen"))

    support.check(Ticket(message="x", contact="jemand@example.org"))


def test_an_oversized_load_is_refused_before_it_goes_up() -> None:
    """Die Absage kommt vor dem Hochladen und nennt den Anhang, der schwer ist."""
    big = Attachment("sitzung.p3d", b"0" * (support.MAX_TOTAL_BYTES + 1))

    with pytest.raises(UserError) as caught:
        support.check(Ticket(message="x", attachments=[big]))

    assert "megabytes" in caught.value.values


# --- der Versand ----------------------------------------------------------------------


def test_a_ticket_goes_out_as_one_form() -> None:
    seen: dict[str, Any] = {}

    def sender(url: str, content_type: str, body: bytes) -> dict[str, Any]:
        seen.update(url=url, content_type=content_type, body=body)
        return {"ok": True, "reference": "S-2026-0042"}

    receipt = support.send(
        Ticket(message="Bitte ein Fasenwerkzeug.", contact="jemand@example.org"),
        "https://example.invalid/support",
        sender,
    )

    assert receipt.reference == "S-2026-0042"
    assert seen["content_type"].startswith("multipart/form-data; boundary=")
    body = bytes(seen["body"])
    assert b'name="message"' in body
    assert b"Bitte ein Fasenwerkzeug." in body
    assert b"jemand@example.org" in body


def test_the_attachment_travels_in_the_same_form() -> None:
    seen: dict[str, Any] = {}

    def sender(url: str, content_type: str, body: bytes) -> dict[str, Any]:
        seen["body"] = body
        return {"ok": True}

    support.send(
        Ticket(message="x", attachments=[Attachment("bildschirmfoto.png", b"\x89PNGrest")]),
        "https://example.invalid/support",
        sender,
    )

    assert b'filename="bildschirmfoto.png"' in seen["body"]
    assert b"\x89PNGrest" in seen["body"]


def test_the_boundary_never_appears_inside_the_body() -> None:
    """Ein Trenner, der im Inhalt vorkommt, zerlegt die Sendung falsch."""
    seen: dict[str, Any] = {}

    def sender(url: str, content_type: str, body: bytes) -> dict[str, Any]:
        seen.update(content_type=content_type, body=body)
        return {"ok": True}

    support.send(
        Ticket(message="----solidon und noch etwas", attachments=[Attachment("a.bin", b"--")]),
        "https://example.invalid/support",
        sender,
    )

    boundary = seen["content_type"].split("boundary=")[1]
    # Sechs Felder, ein Anhang, ein Schluss. Der Punkt ist nicht die Zahl,
    # sondern dass die Nachricht „----solidon" enthält und den Trenner
    # trotzdem nicht trifft — sonst zerfiele die Sendung an der falschen Stelle.
    assert seen["body"].count(f"--{boundary}".encode()) == 8
    assert boundary.encode() not in b"----solidon und noch etwas"


def test_a_refusal_names_a_way_that_needs_no_network() -> None:
    """Regel 17: der Ausweg darf nicht dieselbe Leitung brauchen wie der
    Versuch, der gerade scheiterte."""

    def sender(url: str, content_type: str, body: bytes) -> dict[str, Any]:
        raise OSError("Netz weg")

    with pytest.raises(support.SendFailed) as caught:
        support.send(Ticket(message="x"), "https://example.invalid/support", sender)

    offered = {action.id for action in caught.value.suggestions}
    assert {"save_report", "send_by_mail"} <= offered
    assert "Netz weg" in str(caught.value.values.get("reason"))


def test_a_server_that_says_no_is_not_a_success() -> None:
    def sender(url: str, content_type: str, body: bytes) -> dict[str, Any]:
        return {"ok": False, "error": "zu groß"}

    with pytest.raises(support.SendFailed) as caught:
        support.send(Ticket(message="x"), "https://example.invalid/support", sender)

    assert "zu groß" in str(caught.value.values.get("reason"))


def test_the_rate_limit_does_not_invite_an_immediate_retry() -> None:
    """429 heißt: die (oft am NAT geteilte) Ratengrenze ist erreicht.

    Ein sofortiger zweiter Versuch verlängert die Sperre — also darf kein „Noch
    einmal senden" vorn stehen, und der Fall trägt seinen Status, damit sich das
    Muster später auch messen lässt (Gesamtreview: jede Absage kam als „nicht
    erreichbar" an).
    """

    def sender(url: str, content_type: str, body: bytes) -> dict[str, Any]:
        raise HTTPError(url, 429, "Too Many Requests", {}, None)  # type: ignore[arg-type]

    with pytest.raises(support.SendFailed) as caught:
        support.send(Ticket(message="x"), "https://example.invalid/support", sender)

    offered = {action.id for action in caught.value.suggestions}
    assert "retry_send" not in offered, "429: kein Knopf, der sofort noch einmal sendet"
    assert {"send_by_mail", "save_report"} <= offered, "die Wege ohne diese Leitung bleiben"
    assert caught.value.values.get("status") == 429


def test_a_server_error_is_not_reported_as_unreachable() -> None:
    """5xx heißt: der Server hat geantwortet, nur mit einem Problem. „Nicht
    erreichbar" wäre falsch — erreichbar war er."""

    def sender(url: str, content_type: str, body: bytes) -> dict[str, Any]:
        raise HTTPError(url, 503, "Service Unavailable", {}, None)  # type: ignore[arg-type]

    with pytest.raises(support.SendFailed) as caught:
        support.send(Ticket(message="x"), "https://example.invalid/support", sender)

    assert caught.value.values.get("status") == 503
    assert "erreichbar" not in str(caught.value.detail), "der Server war erreichbar"


def test_a_refused_request_is_not_reported_as_unreachable() -> None:
    """Auch 403 ist eine Antwort, keine tote Leitung: die Gegenstelle hat die
    Sendung abgelehnt, nicht geschwiegen — und ein Wiederholen ändert daran
    nichts."""

    def sender(url: str, content_type: str, body: bytes) -> dict[str, Any]:
        raise HTTPError(url, 403, "Forbidden", {}, None)  # type: ignore[arg-type]

    with pytest.raises(support.SendFailed) as caught:
        support.send(Ticket(message="x"), "https://example.invalid/support", sender)

    offered = {action.id for action in caught.value.suggestions}
    assert "retry_send" not in offered, "403 ändert sich durch Wiederholen nicht"
    assert caught.value.values.get("status") == 403
    assert "erreichbar" not in str(caught.value.detail)


def test_a_genuine_connection_failure_still_says_unreachable() -> None:
    """Ohne HTTP-Status hat die Gegenstelle nicht geantwortet — Netz, DNS,
    Zeitlimit. Das ist der Fall, für den „nicht erreichbar" richtig ist und der
    Wiederholungsknopf sinnvoll (die Regressionsprobe zum Fund oben)."""

    def sender(url: str, content_type: str, body: bytes) -> dict[str, Any]:
        raise OSError("Name or service not known")

    with pytest.raises(support.SendFailed) as caught:
        support.send(Ticket(message="x"), "https://example.invalid/support", sender)

    offered = {action.id for action in caught.value.suggestions}
    assert "status" not in caught.value.values
    assert "erreichbar" in str(caught.value.detail)
    assert "retry_send" in offered


def test_a_header_field_carries_no_line_breaks() -> None:
    """Ein Zeilenumbruch in der Rückadresse ist der Weg, einer Mail fremde
    Empfänger unterzuschieben."""
    _type, body = support._package(
        Ticket(message="x", contact="jemand@example.org\r\nBcc: fremd@example.net")
    )

    # Der Text „Bcc:" darf stehen bleiben — gefährlich ist nicht das Wort,
    # sondern der Umbruch davor, der die zweite Zeile zu einer Kopfzeile macht.
    field = body.split(b'name="contact"\r\n\r\n')[1].split(b"\r\n--")[0]
    assert b"\r" not in field and b"\n" not in field
    assert field.startswith(b"jemand@example.org")


def test_the_mail_link_needs_no_server() -> None:
    link = support.mail_link(Ticket(message="Hallo"))

    assert link.startswith("mailto:support@solidon3d.de?")
    assert "subject=" in link and "body=" in link


def test_mail_link_keeps_unicode_and_reserved_characters() -> None:
    """Native Mailprogramme erhalten genau einmal kodierte Felder."""
    from urllib.parse import parse_qs, urlsplit

    ticket = Ticket(message="Größe: 100% & Frage?\n12,5 mm + 2; %3A bleibt so.")
    fields = parse_qs(urlsplit(support.mail_link(ticket)).query)

    assert fields["subject"] == [ticket.subject]
    assert fields["body"][0].splitlines()[2:] == ticket.as_text().splitlines()[2:]


# --- die Grenze zur Telemetrie --------------------------------------------------------


def test_nothing_leaves_without_being_sent() -> None:
    """§37.2: Es gibt genau einen Weg hinaus, und der heißt :func:`send`.

    Der Test liest die Quelle, weil sich das anders nicht festhalten lässt:
    Ein Zeitgeber, ein Fehlerpfad oder ein Startaufruf, der selbst sendet,
    wäre Telemetrie — gleich wie freundlich er begründet ist.
    """
    import inspect

    from app.ui import support_dialog

    callers = [
        line.strip()
        for line in inspect.getsource(support_dialog).splitlines()
        if "support.send(" in line
    ]

    assert len(callers) == 1, f"nur der Knopf sendet, gefunden: {callers}"


def test_the_report_folder_still_sends_nothing() -> None:
    """Der abgelegte Bericht bleibt, was er war: ein Ordner (§33.2)."""
    import inspect

    from app.core import report

    source = inspect.getsource(report)

    assert "urlopen" not in source
    assert "post" not in source


def test_every_failure_carries_a_suggestion() -> None:
    """Regel 17, für die Ausnahme dieses Moduls."""
    assert issubclass(support.SendFailed, AppError)
    assert support.SendFailed().suggestions


# --- die Gegenstelle -------------------------------------------------------------------

ENDPOINT = Path(__file__).parent.parent / "website" / "api" / "support.php"


def test_the_endpoint_reads_every_field_the_client_sends() -> None:
    """Client und Gegenstelle kennen dieselben Feldnamen.

    Der Modulkopf von ``support.php`` sagt es so: „Feldnamen und Antwortformat
    stehen dort fest; wer hier etwas umbenennt, benennt es dort mit um." Nur
    stand dahinter nichts, was es prüft — und ein umbenanntes Feld fällt nicht
    auf, es kommt einfach leer an.

    Geprüft wird die Richtung, die weh tut: Was der Server liest, muss der
    Client schicken. Umgekehrt ist harmlos — ``environment`` reist mit und
    wird drüben nicht gelesen, weil dieselben Angaben schon im Text stehen.
    """
    import inspect

    source = inspect.getsource(support._package)
    endpoint = ENDPOINT.read_text(encoding="utf-8")
    read_by_server = set(re.findall(r"\$_POST\['([a-z_]+)'\]", endpoint))
    sent_by_client = set(re.findall(r'^\s*"([a-z_]+)":', source, re.MULTILINE))

    missing = read_by_server - sent_by_client
    assert not missing, (
        f"Die Gegenstelle liest Felder, die niemand schickt: {sorted(missing)}. "
        "Sie kommen leer an, und niemand merkt es."
    )


def test_the_endpoint_is_valid_php() -> None:
    """Die Datei wird nie hier ausgeführt — also prüft sie hier auch niemand.

    Sie liegt im Repository, geht per FTPS auf den Server und läuft erst dort.
    Ein Tippfehler fällt damit frühestens dem ersten Nutzer auf, der etwas
    schickt, und der bekommt eine leere Antwort statt einer Fehlermeldung.
    """
    php = php_executable()
    done = subprocess.run([php, "-l", str(ENDPOINT)], capture_output=True, text=True, timeout=30)

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"


def test_the_subject_never_exceeds_a_mime_word() -> None:
    """RFC 2047 erlaubt 75 Zeichen je Wort, der Betreff darf 200 tragen.

    Als ein einziges Wort kodiert wurden daraus über 270. Die meisten Zusteller
    nehmen das hin, manche stutzen die Kopfzeile — und dann steht im
    Posteingang kein Betreff.

    Geprüft wird an der echten Funktion, nicht an einem Nachbau: Das Skript
    daneben schneidet sie aus ``support.php`` heraus und lässt sie laufen.
    """
    php = php_executable()

    # Ohne ``php.ini`` sucht PHP seine Erweiterungen unter dem eingebauten
    # Standardpfad — bei einer entpackten Installation liegen sie neben der
    # ausführbaren Datei. Gibt es dort ein ``ext``, wird es gesagt; sonst hat
    # dieses PHP eine ini und weiß es selbst.
    # **Startmeldungen nach stderr.** Gemessen wird die Ausgabe des Skripts,
    # nicht die Meinung der php.ini über ihre Erweiterungen: Auf dem
    # Intel-Mac-Runner zeigt sie auf ein mbstring, das dort nicht liegt, und
    # die Ladewarnung landete mitten in stdout — der Test meldete dann einen
    # Fehler, der über den Betreff nichts aussagte.
    options = ["-d", "display_errors=stderr", "-d", "extension=mbstring"]
    extensions = Path(php).parent / "ext"
    if extensions.is_dir():
        options[:0] = ["-d", f"extension_dir={extensions}"]
    done = subprocess.run(
        [
            php,
            *options,
            str(Path(__file__).parent / "data" / "check_subject.php"),
            str(ENDPOINT),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert done.returncode == 0 and done.stdout == "ok", f"{done.stdout}\n{done.stderr}"


def test_two_reports_in_the_same_second_get_two_folders(tmp_path: Path) -> None:
    """Gesamtreview 05.09.2026, CORE-27: Der Sekundenstempel allein war der
    Ordnername, und ein vorhandener Ordner wurde erneut geöffnet — der zweite
    Bericht überschrieb den ersten in ``bericht.txt``, und die Anhänge des
    ersten lagen weiter daneben."""
    from app.core import report as report_module

    first = report_module.write(report_module.ErrorReport(summary="erster"), directory=tmp_path)
    second = report_module.write(report_module.ErrorReport(summary="zweiter"), directory=tmp_path)

    assert first != second
    assert (first / "bericht.txt").read_text(encoding="utf-8") != (
        second / "bericht.txt"
    ).read_text(encoding="utf-8")
    assert "erster" in (first / "bericht.txt").read_text(encoding="utf-8")


def test_an_exception_report_keeps_the_cause_without_source_or_local_values() -> None:
    """Automatische Diagnose sammelt den Stapel, keine Variablen oder Quellzeilen."""
    private_local = "DIESE_LOKALE_VARIABLE_REIST_NICHT_MIT"
    try:
        try:
            raise ValueError("Authorization: Bearer verborgen")
        except ValueError as cause:
            raise RuntimeError("https://person:passwort@example.org/a?token=geheim") from cause
    except RuntimeError as problem:
        report = report_module.exception_report(problem, context="CLI")

    assert private_local not in report.traceback
    assert "raise RuntimeError" not in report.traceback
    assert "raise ValueError" not in report.traceback
    assert "test_an_exception_report_keeps_the_cause" in report.traceback
    assert "ValueError" in report.traceback and "RuntimeError" in report.traceback
    for secret in ("verborgen", "person", "passwort", "geheim"):
        assert secret not in report.traceback + report.detail
    assert not report.include_project and not report.digest


def _crash_child(
    tmp_path: Path, body: str, *, installed: bool = True
) -> subprocess.CompletedProcess[str]:
    """Ein echter kopfloser Prozess mit vollständig getrenntem Nutzerprofil."""
    import os
    import sys
    import textwrap

    environment = dict(os.environ)
    for key in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME"):
        environment[key] = str(tmp_path)
    environment["PYTHONUTF8"] = "1"
    setup = """
import os
import sys
from pathlib import Path
from app.core.log import install_crash_logging
if os.name == "nt":
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
"""
    if installed:
        setup += """
capture = install_crash_logging()
assert capture is not None
print(capture, flush=True)
"""
    return subprocess.run(
        [sys.executable, "-c", setup + textwrap.dedent(body)],
        cwd=Path(__file__).resolve().parent.parent,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


@pytest.mark.parametrize("threaded", [False, True])
def test_unhandled_exceptions_reach_the_local_report_from_a_real_process(
    tmp_path: Path, threaded: bool
) -> None:
    """Hauptfaden und normale Python-Fäden teilen denselben redigierten Bericht."""
    body = """
def fail():
    private_local = "LOKALE_GEOMETRIE_BLEIBT_PRIVAT"
    raise RuntimeError("Authorization: Bearer verborgen")
"""
    body += (
        "import threading\nworker = threading.Thread(target=fail)\nworker.start()\nworker.join()\n"
        if threaded
        else "fail()\n"
    )
    done = _crash_child(tmp_path, body)
    assert done.returncode == (0 if threaded else 1), done.stderr
    raw = Path(done.stdout.splitlines()[0]).read_text(encoding="utf-8")
    assert "RuntimeError" in raw and "fail" in raw
    assert "verborgen" not in raw + done.stderr
    reports = list(tmp_path.rglob("bericht.txt"))
    assert len(reports) == 1
    written = reports[0].read_text(encoding="utf-8")
    assert "RuntimeError" in written and "fail" in written
    assert "verborgen" not in written and "LOKALE_GEOMETRIE_BLEIBT_PRIVAT" not in written
    assert not list(reports[0].parent.glob("*.p3d"))


def test_a_broken_report_writer_does_not_replace_the_original_exception(tmp_path: Path) -> None:
    done = _crash_child(
        tmp_path,
        """
from app.core import report
def refuse(*args, **kwargs):
    raise OSError("Berichtsordner schreibgeschützt")
report.write = refuse
raise RuntimeError("ursprünglicher Fehler")
""",
    )
    assert done.returncode == 1
    raw = Path(done.stdout.splitlines()[0]).read_text(encoding="utf-8")
    assert "RuntimeError: ursprünglicher Fehler" in raw
    assert "ursprünglicher Fehler" in done.stderr
    assert "Berichtsordner schreibgeschützt" in done.stderr


def test_a_native_crash_still_writes_after_logging_has_shut_down(tmp_path: Path) -> None:
    """Der eigene Deskriptor überlebt den normalen Logger und den Python-Abbau."""
    done = _crash_child(
        tmp_path,
        """
import atexit
import faulthandler
import logging
def crash_at_shutdown():
    logging.shutdown()
    faulthandler._sigsegv()
atexit.register(crash_at_shutdown)
""",
    )
    assert done.returncode != 0
    raw = Path(done.stdout.splitlines()[0]).read_text(encoding="utf-8", errors="replace")
    assert "crash_at_shutdown" in raw
    assert "Fatal Python error" in raw or "Windows fatal exception" in raw


def test_repeated_installation_uses_one_file_and_leaves_clean_runs_empty(tmp_path: Path) -> None:
    done = _crash_child(
        tmp_path,
        """
assert install_crash_logging() == capture
assert "PySide6" not in sys.modules
""",
    )
    assert done.returncode == 0, done.stderr
    target = Path(done.stdout.splitlines()[0])
    assert target.read_bytes() == b""
    assert list(target.parent.glob("crash-*.log")) == [target]


def test_diagnostic_versions_never_import_a_native_package(tmp_path: Path) -> None:
    done = _crash_child(
        tmp_path,
        """
from app.core import report
import importlib.abc
class RefuseNative(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in report.REPORTED_PACKAGES:
            raise AssertionError('Die Diagnose darf kein natives Paket importieren')
sys.meta_path.insert(0, RefuseNative())
versions = report.environment()
assert versions['python'] and versions['app']
assert all(name not in sys.modules for name in report.REPORTED_PACKAGES)
""",
    )
    assert done.returncode == 0, done.stderr
    assert Path(done.stdout.splitlines()[0]).read_bytes() == b""


def test_crash_attachments_are_redacted_bounded_and_frozen(tmp_path: Path) -> None:
    recent = tmp_path / "crash-20260920T120000-0.4.4-123-0000000000000001.log"
    empty = tmp_path / "crash-20260920T130000-0.4.4-123-0000000000000002.log"
    ignored = tmp_path / "crash-mein-eigener-text.log"
    empty.write_bytes(b"")
    ignored.write_text("nicht automatisch anhängen", encoding="utf-8")
    recent.write_text(
        ("alter Eintrag\n" * 100_000) + "RuntimeError: Authorization: Bearer geheim\n",
        encoding="utf-8",
    )
    frozen = report_module.diagnostic_attachments(normal=b"normal", directory=tmp_path)
    attached = dict(frozen)
    raw = attached["absturzprotokoll.txt"]
    assert len(raw) <= report_module.LOG_TAIL_MAX_BYTES
    assert b"RuntimeError" in raw and b"geheim" not in raw
    assert "gekürzt" in raw.decode("utf-8")
    assert empty.name.encode() not in raw and ignored.read_bytes() not in raw
    recent.write_text("geänderter Stand", encoding="utf-8")
    assert dict(frozen)["absturzprotokoll.txt"] == raw
    assert attached["protokoll.txt"] == b"normal"


def test_a_partial_crash_line_cannot_lose_the_secret_prefix(tmp_path: Path) -> None:
    recent = tmp_path / "crash-20260920T120000-0.4.4-123-0000000000000001.log"
    recent.write_text(
        "Authorization: Bearer " + "zugangsdaten" * 150_000 + "\nletzter vollständiger Eintrag\n",
        encoding="utf-8",
    )
    text = report_module.crash_tail(tmp_path).decode("utf-8")
    assert "zugangsdaten" not in text
    assert "letzter vollständiger Eintrag" in text and "gekürzt" in text


def test_crash_retention_keeps_live_files_and_bounds_only_automatic_reports(tmp_path: Path) -> None:
    """Ein zweiter Prozess darf weder den offenen Deskriptor noch bewusste Berichte löschen."""
    done = _crash_child(
        tmp_path,
        """
from app.core import log, report
for number in range(8):
    old = capture.parent / f'crash-2000010{number + 1}T120000-0.4.4-123-{number:016x}.log'
    old.write_text(f'alter Absturz {number}', encoding='utf-8')
    automatic = old.with_suffix('') / 'bericht-20000101-120000'
    automatic.mkdir(parents=True)
    (automatic / 'bericht.txt').write_text('automatisch', encoding='utf-8')
empty = capture.parent / 'crash-20000101T010000-0.4.4-123-0000000000000020.log'
empty.write_bytes(b'')
manual = capture.parent / 'meine-diagnose.txt'
manual.write_text('behalten', encoding='utf-8')
import subprocess
probe = subprocess.run(
    [sys.executable, '-c',
     'from app.core.log import install_crash_logging; install_crash_logging()'],
    check=True,
)
assert capture.exists() and capture.read_bytes() == b''
old = [path for path in log.crash_paths(capture.parent) if path.name.startswith('crash-2000')]
assert len(old) == 5
assert not empty.exists()
assert manual.read_text(encoding='utf-8') == 'behalten'
for number in range(8):
    try:
        raise RuntimeError(f'Fehler {number}')
    except RuntimeError as problem:
        sys.excepthook(type(problem), problem, problem.__traceback__)
folders = list(capture.with_suffix('').glob('bericht-*'))
assert len(folders) == 5
assert 'Fehler 7' in capture.read_text(encoding='utf-8')
""",
    )
    assert done.returncode == 0, done.stderr


def test_a_broken_exception_message_is_still_reported(tmp_path: Path) -> None:
    done = _crash_child(
        tmp_path,
        """
class UnreadableError(Exception):
    def __str__(self):
        raise ValueError('nicht darstellbar')
raise UnreadableError()
""",
    )
    assert done.returncode == 1
    assert "UnreadableError" in Path(done.stdout.splitlines()[0]).read_text(encoding="utf-8")
    assert "Error in sys.excepthook" not in done.stderr


def test_system_exit_in_a_thread_is_not_recorded_as_a_crash(tmp_path: Path) -> None:
    done = _crash_child(
        tmp_path,
        """
import threading
worker = threading.Thread(target=lambda: sys.exit(2))
worker.start()
worker.join()
""",
    )
    assert done.returncode == 0, done.stderr
    assert Path(done.stdout.splitlines()[0]).read_bytes() == b""


@pytest.mark.parametrize("failure", ["open", "enable", "after_enable"])
def test_failed_crash_setup_removes_only_its_own_new_files(tmp_path: Path, failure: str) -> None:
    done = _crash_child(
        tmp_path,
        f"""
from app.core import log
from app.core.paths import user_log_dir
folder = user_log_dir()
folder.mkdir(parents=True)
unrelated = folder / 'meine-datei.lock'
unrelated.write_text('behalten', encoding='utf-8')
original_open = os.open
original_enable = log.faulthandler.enable
def refused_open(path, *args, **kwargs):
    if str(path).endswith('.log'):
        raise OSError('schreibgeschützt')
    return original_open(path, *args, **kwargs)
def refused_enable(*args, **kwargs):
    if {failure!r} == 'after_enable':
        original_enable(*args, **kwargs)
    raise RuntimeError('Handler nicht verfügbar')
if {failure!r} == 'open':
    log.os.open = refused_open
else:
    log.faulthandler.enable = refused_enable
assert install_crash_logging() is None
if {failure!r} != 'open':
    assert not log.faulthandler.is_enabled()
assert list(folder.iterdir()) == [unrelated]
raise ValueError('ursprünglicher Fehler')
""",
        installed=False,
    )
    assert done.returncode == 1
    assert "ursprünglicher Fehler" in done.stderr
    assert "Error in sys.excepthook" not in done.stderr


def test_nested_exception_groups_have_one_shared_construction_budget() -> None:
    from app.core import log

    visited: list[bool] = []

    class CountedError(Exception):
        def __str__(self) -> str:
            visited.append(True)
            return "begrenzter Fehlertext"

    error = ExceptionGroup(
        "viele Fehler",
        [ExceptionGroup("ein Zweig", [CountedError() for _ in range(20)]) for _ in range(20)],
    )
    text = log.exception_text(error)
    assert 0 < len(visited) <= 100
    assert "ExceptionGroup" in text and "CountedError" in text
    assert "…" in text
    assert len(text) <= 2 * 1024 * 1024
