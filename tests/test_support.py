"""Rückmeldungen senden (Bauplan §37.2, §33.3).

Zwei Dinge werden hier festgehalten, und das zweite ist das wichtigere: dass
eine Sendung ankommt, wenn jemand sie abschickt — und dass ohne diesen Knopf
nichts hinausgeht.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from app.core import support
from app.core.errors import AppError, UserError
from app.core.support import Attachment, Ticket

# --- was in der Sendung steht ---------------------------------------------------------


def test_a_ticket_carries_the_versions() -> None:
    """Ohne Fassung und Plattform beginnt jede Antwort mit drei Rückfragen."""
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


@pytest.mark.skipif(shutil.which("php") is None, reason="ohne PHP nicht prüfbar")
def test_the_endpoint_is_valid_php() -> None:
    """Die Datei wird nie hier ausgeführt — also prüft sie hier auch niemand.

    Sie liegt im Repository, geht per FTPS auf den Server und läuft erst dort.
    Ein Tippfehler fällt damit frühestens dem ersten Nutzer auf, der etwas
    schickt, und der bekommt eine leere Antwort statt einer Fehlermeldung.
    """
    php = shutil.which("php")
    assert php is not None  # für mypy — skipif hat es schon geprüft
    done = subprocess.run([php, "-l", str(ENDPOINT)], capture_output=True, text=True, timeout=30)

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"


@pytest.mark.skipif(shutil.which("php") is None, reason="ohne PHP nicht prüfbar")
def test_the_subject_never_exceeds_a_mime_word() -> None:
    """RFC 2047 erlaubt 75 Zeichen je Wort, der Betreff darf 200 tragen.

    Als ein einziges Wort kodiert wurden daraus über 270. Die meisten Zusteller
    nehmen das hin, manche stutzen die Kopfzeile — und dann steht im
    Posteingang kein Betreff.

    Geprüft wird an der echten Funktion, nicht an einem Nachbau: Das Skript
    daneben schneidet sie aus ``support.php`` heraus und lässt sie laufen.
    """
    php = shutil.which("php")
    assert php is not None  # skipif hat es geprüft, mypy weiß das nicht

    # Ohne ``php.ini`` sucht PHP seine Erweiterungen unter dem eingebauten
    # Standardpfad — bei einer entpackten Installation liegen sie neben der
    # ausführbaren Datei. Gibt es dort ein ``ext``, wird es gesagt; sonst hat
    # dieses PHP eine ini und weiß es selbst.
    options = ["-d", "extension=mbstring"]
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

    assert done.stdout == "ok", f"{done.stdout}\n{done.stderr}"
