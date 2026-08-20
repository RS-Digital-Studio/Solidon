"""Rückmeldungen senden (Bauplan §37.2, §33.3).

Zwei Dinge werden hier festgehalten, und das zweite ist das wichtigere: dass
eine Sendung ankommt, wenn jemand sie abschickt — und dass ohne diesen Knopf
nichts hinausgeht.
"""

from __future__ import annotations

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
