"""Rückmeldungen und Fehlerberichte zum Support senden (Bauplan §37.2).

Das ist die Ergänzung zu :mod:`app.core.report`, nicht dessen Ersatz. Der
Bericht bleibt ein Ordner, der auf dem Rechner liegt; hier kommt der Weg dazu,
ihn ohne Umweg über den Dateimanager an ``support@solidon3d.de`` zu schicken.

**Die Linie zur verbotenen Telemetrie bleibt scharf.** Von allein geht nichts.
Es gibt keine Zeile, die aus einem Fehler heraus sendet, keinen Zeitgeber und
keine Hintergrundmeldung — gesendet wird, was jemand geschrieben und mit einem
Knopf abgeschickt hat, und vorher sieht er, was mitgeht. Telemetrie ist das
Sammeln ohne Zutun; ein Bericht ist eine Nachricht, die jemand schreibt.

Gesendet wird an eine Adresse dieser Domain, die die Post annimmt und
weiterreicht (``website/api/support.php``). Der Umweg ist kein Selbstzweck: Ein
Programm, das selbst zu einem Postausgang spricht, trägt dessen Zugangsdaten in
sich, und was in einer ausgelieferten Datei steht, ist kein Geheimnis mehr.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from app.branding import APP_NAME, APP_VERSION, SUPPORT_ADDRESS
from app.core.errors import CANCEL, CORRECT_INPUT, Action, AppError, UserError
from app.core.log import get_logger
from app.core.report import environment
from app.i18n import _, tr

_log = get_logger(__name__)

#: Wohin die Nachricht geht. Eine Adresse auf derselben Domain wie die
#: Produktseite; sie nimmt an und reicht an :data:`SUPPORT_ADDRESS` weiter.
SUPPORT_URL: Final = "https://solidon3d.de/api/support.php"

#: Wie lange der Versand dauern darf. Großzügiger als der Update-Hinweis: dort
#: wartet niemand, hier steht jemand vor dem Fenster und hat etwas geschrieben,
#: das er nicht noch einmal tippen möchte.
TIMEOUT_SECONDS: Final = 30.0

#: Wie groß die ganze Sendung werden darf. Ein Bildschirmfoto wiegt wenig, ein
#: Projekt mit eingebetteten Netzen viel — die Grenze steht hier und nicht erst
#: beim Server, damit die Absage vor dem Hochladen kommt und einen Vorschlag
#: trägt.
MAX_TOTAL_BYTES: Final = 12 * 1024 * 1024

#: Wie lang die Nachricht selbst werden darf. Wer mehr zu sagen hat, hängt es
#: an.
MAX_MESSAGE_LENGTH: Final = 20_000

#: Wie viel von der Antwort gelesen wird. Sie trägt zwei Felder — ``ok`` und
#: eine Referenz —, also ist die Grenze hier ein Deckel gegen einen bösen
#: Server und keine Platzrechnung.
#:
#: **Der Name ist seit dem 27.08.2026 ein anderer.** Er lautete wie die
#: Antwortgrenze in :mod:`app.core.updates`, und die deckelt die
#: Versionsdatei — an jenem Tag auf einen abgeleiteten Wert umgestellt, weil
#: sie beim Kunden riss. Damit standen zwei verschiedene Zahlen unter einem
#: Namen, und am Namen sah man es nicht. Gemeldet vom Zwillingsscan einer
#: Nachbarsitzung.
MAX_REPLY_BYTES: Final = 64 * 1024

#: Die Arten einer Sendung. Sie stehen im Betreff und sortieren den Posteingang
#: — mehr tun sie nicht, und deshalb sind es fünf und nicht zwölf.
#:
#: Zwei davon wählt niemand selbst. :data:`KIND_CRASH` setzt der Fehlerdialog,
#: :data:`KIND_SURVEY` der Bogen aus :mod:`app.core.feedback`; beide stehen
#: deshalb nicht in der Auswahlliste des Dialogs. Der Bogen bekam eine eigene
#: Art, weil er sonst den Stapel der Verbesserungsvorschläge füllte: Er kommt
#: unaufgefordert und in Serie, und wer beides mischt, kann keines von beidem
#: mehr durchsehen.
KIND_IDEA: Final = "idea"
KIND_BUG: Final = "bug"
KIND_QUESTION: Final = "question"
KIND_CRASH: Final = "crash"
KIND_SURVEY: Final = "survey"

#: Wie eine Art in der Oberfläche heißt. Der Schlüssel reist, der Text wird
#: gezeigt (Regel 20).
KIND_NAMES: Final[dict[str, Any]] = {
    KIND_IDEA: _("Verbesserungsvorschlag"),
    KIND_BUG: _("Fehler"),
    KIND_QUESTION: _("Frage"),
    KIND_CRASH: _("Programmfehler"),
    KIND_SURVEY: _("Fragebogen"),
}

#: Wenn der Versand nicht ging: den Bericht ablegen und selbst schicken. Beides
#: sind Wege, die ohne Netz auskommen — Regel 17 verlangt einen Ausweg, und ein
#: Ausweg, der dieselbe Leitung braucht wie der gescheiterte Versuch, ist
#: keiner.
SAVE_REPORT: Final = Action("save_report", _("Bericht ablegen"))
SEND_BY_MAIL: Final = Action("send_by_mail", _("Selbst per E-Mail senden"), primary=True)
RETRY_SEND: Final = Action("retry_send", _("Noch einmal senden"), primary=True)

#: Was als Rückadresse durchgeht. Keine Vollprüfung — die gibt es nicht —,
#: sondern die Absage an das, was offensichtlich keine ist.
_ADDRESS = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")

#: Steuerzeichen haben in einem Kopffeld nichts zu suchen: ein Zeilenumbruch in
#: der Rückadresse ist der klassische Weg, einer Mail fremde Empfänger
#: unterzuschieben. Der Server prüft es noch einmal; hier steht es, weil eine
#: Prüfung an einer Stelle keine ist.
_CONTROL = re.compile(r"[\r\n\t\x00-\x1f\x7f]")


class SendFailed(AppError):
    """Die Sendung ist nicht angekommen — Netz, Server oder Antwort.

    Kein Bedienfehler: Der Nutzer hat alles richtig gemacht, und die Sache
    liegt an einer Leitung. Also nennt der Fehler die zwei Wege, die ohne
    diese Leitung auskommen.
    """

    default_title = _("Die Rückmeldung ließ sich nicht senden.")
    default_suggestions = (RETRY_SEND, SAVE_REPORT, SEND_BY_MAIL, CANCEL)


@dataclass(frozen=True, slots=True)
class Attachment:
    """Eine Datei, die mitgeht — mit dem Satz, der sagt, was sie enthält."""

    name: str
    data: bytes
    description: str = ""

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass(slots=True)
class Ticket:
    """Eine Sendung, bevor sie irgendwohin geht.

    Sie ist vollständig lesbar, bevor sie abgeschickt wird: :meth:`as_text`
    ist genau das, was ankommt, und die Anhänge stehen mit Namen und Größe
    daneben. Was jemand nicht gesehen hat, sendet er nicht (§37.2).
    """

    kind: str = KIND_IDEA
    message: str = ""
    contact: str = ""
    detail: str = ""
    """Was das Programm dazu weiß — Fehlertext und Stapelabzug, wo es einen
    gibt. Der Nutzer schreibt hier nichts hinein."""
    attachments: list[Attachment] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        """Wie schwer die Sendung ist. Der Text zählt mit, auch wenn er
        gegenüber einem Projektcontainer nicht ins Gewicht fällt."""
        return len(self.as_text().encode("utf-8")) + sum(entry.size for entry in self.attachments)

    @property
    def kind_name(self) -> str:
        """Die Art als Wort — für Betreff und Vorschau."""
        return str(KIND_NAMES.get(self.kind, KIND_NAMES[KIND_IDEA]))

    @property
    def subject(self) -> str:
        """Was im Posteingang steht: Art, Version, erste Zeile."""
        first = self.message.strip().splitlines()[0] if self.message.strip() else ""
        head = f"{APP_NAME} {APP_VERSION} — {self.kind_name}"
        return f"{head}: {first[:80]}" if first else head

    def as_text(self) -> str:
        """Die Sendung als lesbarer Text — genau das, was ankommt."""
        lines = [
            self.subject,
            datetime.now(UTC).isoformat(timespec="seconds"),
            "",
            self.message.strip(),
        ]
        if self.contact:
            lines.extend(["", f"{tr('Rückantwort an')}: {self.contact}"])
        if self.detail:
            lines.extend(["", "--- detail ---", self.detail.strip()])

        lines.extend(["", "--- system ---"])
        lines.extend(f"{name}: {value}" for name, value in environment().items())
        if self.attachments:
            lines.extend(["", "--- anhänge ---"])
            lines.extend(
                f"{entry.name} ({entry.size // 1024} KB)"
                + (f" — {entry.description}" if entry.description else "")
                for entry in self.attachments
            )
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Receipt:
    """Was zurückkam: die Vorgangsnummer, wenn der Server eine vergibt.

    Sie ist keine Zusage — sie ist das, was in einer Rückfrage zitiert wird,
    damit niemand „die Mail von gestern" suchen muss.
    """

    reference: str = ""


#: Der Versandweg als Funktion, damit er sich austauschen lässt: Ein Test, der
#: eine Adresse im Netz braucht, prüft das Netz und nicht diesen Code.
Sender = Callable[[str, str, bytes], dict[str, Any]]


def check(ticket: Ticket) -> None:
    """Was vor dem Senden feststeht. Wirft mit einem Vorschlag, nie stumm.

    Absichtlich getrennt von :func:`send`: Der Dialog kann damit den
    Senden-Knopf sperren, ohne eine Leitung zu bemühen.
    """
    # Inhalt braucht die Sendung, und der darf auch vom Programm kommen: Nach
    # einem Absturz ist der Stapelabzug der Bericht. Wer dann nichts zu
    # schreiben weiß, soll ihn trotzdem abschicken können — sonst ist der
    # gesperrte Knopf die Sackgasse hinter dem Programmfehler.
    if not ticket.message.strip() and not ticket.detail.strip():
        raise UserError(
            _("Die Rückmeldung ist noch leer."),
            _("Schreiben Sie in einem Satz, was passiert ist oder was besser sein sollte."),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    if len(ticket.message) > MAX_MESSAGE_LENGTH:
        raise UserError(
            _("Die Rückmeldung ist zu lang."),
            _("Kürzen Sie den Text, oder hängen Sie ihn als Datei an."),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={"size": len(ticket.message), "limit": MAX_MESSAGE_LENGTH},
        )
    if ticket.contact and not _ADDRESS.match(ticket.contact.strip()):
        raise UserError(
            _("Diese Rückadresse sieht nicht aus wie eine E-Mail-Adresse."),
            _("Tragen Sie eine gültige Adresse ein, oder lassen Sie das Feld leer."),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    if ticket.total_bytes > MAX_TOTAL_BYTES:
        raise UserError(
            _("Die Anhänge sind zusammen zu groß."),
            _("Nehmen Sie die Sitzung heraus — sie ist der schwerste Anhang."),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={
                "megabytes": round(ticket.total_bytes / (1024 * 1024), 1),
                "limit": MAX_TOTAL_BYTES // (1024 * 1024),
            },
        )


def _failure_for(problem: Exception) -> SendFailed:
    """Übersetzt einen gescheiterten Versand in eine Absage mit dem Vorschlag,
    der zum Fall passt (Regel 17).

    Die Frage, die den Vorschlag trägt, ist: **hat die Gegenstelle geantwortet
    oder nicht?** Ein HTTP-Status heißt geantwortet — dann ist „nicht
    erreichbar" falsch, denn erreichbar war der Server, und bei der Ratengrenze
    ist „sofort noch einmal" sogar schädlich, weil ein zweiter Versuch die
    Sperre verlängert. Ohne Status hat niemand geantwortet (Netz, DNS,
    Zeitlimit), und dafür ist „nicht erreichbar" der richtige Satz.

    Gelesen wird der Status über ``code`` — das trägt ``urllib.error.HTTPError``,
    ein Verbindungsfehler nicht. So bleibt der Versandweg austauschbar: geprüft
    wird eine Eigenschaft der Ausnahme, nicht ihr Typ.
    """
    reason = str(problem)[:200]
    code = getattr(problem, "code", None)
    if code == 429:
        # Ratengrenze, oft die des gemeinsamen Anschlusses (NAT): warten, nicht
        # drängeln. Kein sofortiger Wiederholungsknopf — der Weg über die eigene
        # Mail umgeht die Grenze ganz und steht deshalb vorn.
        return SendFailed(
            detail=_(
                "Die Gegenstelle nimmt gerade zu viele Anfragen an. "
                "Bitte versuchen Sie es später noch einmal."
            ),
            suggestions=(SEND_BY_MAIL, SAVE_REPORT, CANCEL),
            values={"reason": reason, "status": code},
        )
    if isinstance(code, int) and 500 <= code < 600:
        # Der Server hat ein Problem, nicht die Leitung. Ein späterer Versuch
        # kann gelingen, also bleibt der Wiederholungsweg (Vorgabe) — nur der
        # Satz sagt jetzt, dass es am Dienst liegt.
        return SendFailed(
            detail=_(
                "Der Dienst hat gerade ein Problem. Bitte versuchen Sie es später noch einmal."
            ),
            values={"reason": reason, "status": code},
        )
    if isinstance(code, int):
        # Eine andere Absage der Gegenstelle (etwa 403): sie hat geantwortet,
        # die Sendung aber nicht angenommen. Ein sofortiger zweiter Versuch
        # ändert daran nichts, also steht er nicht vorn.
        return SendFailed(
            detail=_("Die Gegenstelle hat die Sendung abgelehnt."),
            suggestions=(SEND_BY_MAIL, SAVE_REPORT, CANCEL),
            values={"reason": reason, "status": code},
        )
    # Kein Status: die Gegenstelle hat nicht geantwortet — Netz, DNS, Zeitlimit.
    return SendFailed(
        detail=_("Die Gegenstelle war nicht erreichbar."),
        values={"reason": reason},
    )


def send(ticket: Ticket, url: str = SUPPORT_URL, sender: Sender | None = None) -> Receipt:
    """Schickt die Sendung ab und gibt zurück, was der Server dazu sagt.

    Aufgerufen wird das aus genau einem Knopf. Es gibt keinen zweiten Aufrufer,
    und wenn je einer dazukommt, ist die Frage zuerst, ob er ein Knopf ist.
    """
    check(ticket)

    content_type, body = _package(ticket)
    _log.info(
        "sending support ticket: kind=%s bytes=%s attachments=%s",
        ticket.kind,
        len(body),
        len(ticket.attachments),
    )
    try:
        answer = (sender or _post)(url, content_type, body)
    except AppError:
        raise
    except Exception as problem:  # ein Netz oder ein Server scheitert auf viele Arten
        _log.warning("support ticket did not go out: %s", problem)
        # Der Grund steht in ``values`` und nicht im Satz: Ein ``{reason}`` im
        # Text eines Kernfehlers bleibt stehen, wie es dasteht — der Kern
        # formatiert nichts, das erst die Anzeige auflöst.
        raise _failure_for(problem) from problem

    if not answer.get("ok"):
        refusal = str(answer.get("error") or "").strip()[:200]
        raise SendFailed(
            detail=_("Die Gegenstelle hat die Sendung abgelehnt."),
            values={"reason": refusal} if refusal else {},
        )

    reference = str(answer.get("reference") or "").strip()[:64]
    _log.info("support ticket accepted as %s", reference or "-")
    return Receipt(reference=reference)


def mail_link(ticket: Ticket) -> str:
    """Der Weg ohne diesen Server: eine vorbereitete Mail im Mailprogramm.

    Anhänge kann ein ``mailto`` nicht tragen — deshalb steht im Text, wo der
    abgelegte Ordner liegt, und der Nutzer zieht die Dateien selbst hinein.
    """
    from urllib.parse import quote

    subject = quote(ticket.subject, safe="")
    body = quote(ticket.as_text(), safe="")
    return f"mailto:{SUPPORT_ADDRESS}?subject={subject}&body={body}"


def _package(ticket: Ticket) -> tuple[str, bytes]:
    """Baut die Sendung als ``multipart/form-data``.

    Von Hand, ohne Zusatzbibliothek: Es ist ein Kopf, ein Trenner und ein Ende
    (Regel 22 — jede Abhängigkeit kostet einen Eintrag in der Lizenzliste, und
    diese hier verdient keinen).
    """
    fields = {
        "kind": ticket.kind,
        "subject": _header_safe(ticket.subject),
        "contact": _header_safe(ticket.contact),
        "message": ticket.as_text(),
        "app_version": APP_VERSION,
        "environment": json.dumps(environment(), ensure_ascii=False),
    }

    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            + value.encode("utf-8")
        )
    for index, entry in enumerate(ticket.attachments):
        head = (
            f'Content-Disposition: form-data; name="file{index}"; '
            f'filename="{_file_safe(entry.name)}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        )
        parts.append(head.encode() + entry.data)

    boundary = _boundary(parts)
    body = b"".join(f"--{boundary}\r\n".encode() + part + b"\r\n" for part in parts)
    body += f"--{boundary}--\r\n".encode()
    return f"multipart/form-data; boundary={boundary}", body


def _boundary(parts: list[bytes]) -> str:
    """Ein Trenner, der im Inhalt nicht vorkommt — aus dem Inhalt gebildet.

    Nicht gewürfelt: Ein Zufallstrenner müsste einen Startwert führen (Regel
    9), und die Frage stellt sich gar nicht erst, wenn der Trenner aus dem
    hervorgeht, was er trennt. Kollisionsfrei ist er nicht per Definition,
    aber prüfbar — und geprüft wird.
    """
    digest = hashlib.sha256(b"".join(parts)).hexdigest()[:32]
    candidate = f"----solidon{digest}"
    while any(candidate.encode() in part for part in parts):  # pragma: no cover - sha256
        digest = hashlib.sha256(digest.encode()).hexdigest()[:32]
        candidate = f"----solidon{digest}"
    return candidate


def _header_safe(value: str) -> str:
    """Was in eine Kopfzeile geht, trägt keine Steuerzeichen."""
    return _CONTROL.sub(" ", value).strip()[:200]


def _file_safe(name: str) -> str:
    """Ein Dateiname ohne Pfad und ohne Anführungszeichen."""
    plain = _CONTROL.sub("", name).replace("\\", "/").rsplit("/", 1)[-1].replace('"', "")
    return plain[:120] or "anhang.bin"


def _post(url: str, content_type: str, body: bytes) -> dict[str, Any]:
    """Der Vorgabeweg: ein POST, Formular hinein, JSON heraus."""
    import urllib.request

    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": content_type,
            "User-Agent": f"{APP_NAME}/{APP_VERSION}",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:
        raw = answer.read(MAX_REPLY_BYTES + 1)
    if len(raw) > MAX_REPLY_BYTES:
        raise ValueError("answer is too large")
    try:
        return dict(json.loads(raw.decode("utf-8")))
    except ValueError as problem:
        raise ValueError(f"answer was not JSON: {raw[:200]!r}") from problem
