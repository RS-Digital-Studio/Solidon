"""Das Format des Lizenzschlüssels: lesen, prüfen, zerlegen.

Ein Schlüssel ist eine signierte Nutzlast, in Base32 geschrieben:

    SOLIDON3D-1-ABCDEFGH-IJKLMNOP-...

Base32 (RFC 4648) statt Base64, weil sein Alphabet keine verwechselbaren
Zeichen enthält — kein 0 gegen O, kein 1 gegen l. Ein Schlüssel wird
normalerweise kopiert; wer ihn doch abtippt oder durchtelefoniert, soll daran
nicht scheitern. Der Preis ist Länge, und die ist bei einem personalisierten
Offline-Schlüssel unvermeidlich: 64 Bytes Signatur sind 64 Bytes Signatur.

Was in der Nutzlast steht, steht dort mit Absicht knapp. Die Käuferkennung
trägt sie, damit ein Schlüssel den Namen seines Käufers nennen kann — das wird
seltener weitergegeben als eine anonyme Zeichenkette. Mehr als das braucht
niemand zu wissen, und was nicht darin steht, kann auch nicht verloren gehen.

Gezeigt wird der Name im Freischaltdialog und im Über-Dialog, dort als
„Lizenziert für …" (Konzept §2 I H2).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date, timedelta
from typing import ClassVar, Final

from app.core.activation import ed25519
from app.core.errors import BUY_LICENCE, CORRECT_INPUT, Action, UserError
from app.i18n import TranslatableText, _

#: Was vor der Nutzlast steht. Wird beim Lesen verlangt, damit eine
#: hineingerutschte Zeichenkette anderer Herkunft sofort auffällt.
PREFIX: Final = "SOLIDON3D"

#: Version des Schlüsselformats. Steht im Text **und** signiert in der
#: Nutzlast: nur der Text wäre umdeutbar, sobald es eine Version 2 gibt.
FORMAT_VERSION: Final = 1

#: Ab wann Kaufdaten gezählt werden. Zwei Bytes reichen damit für 179 Jahre.
EPOCH: Final = date(2026, 1, 1)

#: Wie viele Base32-Zeichen zwischen zwei Bindestrichen stehen.
GROUP_SIZE: Final = 8

#: Das Alphabet von Base32 nach RFC 4648.
ALPHABET: Final = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")

#: Was beim Lesen wegfällt: die Gruppentrenner und der Weißraum, den ein
#: Schlüssel aus einer E-Mail mitbringt.
SEPARATORS: Final = frozenset("- \t\r\n")

#: Die drei Verwechslungen, gegen die Base32 überhaupt gewählt wurde. Wer
#: abtippt, schreibt sie — also werden sie zurückgebogen statt abgelehnt.
CONFUSABLE: Final = {"0": "O", "1": "I", "8": "B"}

#: Der öffentliche Schlüssel, gegen den geprüft wird.
#:
#: Der echte, für Hauptversion 1 — erzeugt mit ``tools/make_licence_keys.py``.
#: Der private Teil liegt im Passwortmanager und auf Papier an einem zweiten
#: Ort (§8) und verlässt beide nie; gebraucht wird er nur zum Ausstellen von
#: Schlüsseln, nie beim Bauen. Dieser öffentliche Teil darf überall stehen.
#:
#: Wer hier je wieder einen Platzhalter braucht (neue Hauptversion, neues
#: Paar): ``b"\xff" * 32`` ist der sichere — alle Bits gesetzt heißt
#: y >= 2^255 - 19, kein Punkt auf der Kurve, ``decompress`` gibt ``None``
#: und die Prüfung lehnt jeden Schlüssel ab. Zweiunddreißig **Null**bytes
#: wären das Gegenteil: ein Punkt der Ordnung 4, gegen den sich zu jeder
#: Nutzlast in Millisekunden eine Signatur schmieden lässt. Dagegen steht
#: seit ``ed25519.has_small_order`` zusätzlich die Prüfung selbst.
PUBLIC_KEY: Final = bytes.fromhex(
    "c1a6c906ff05f935ae99e71ea3bea79919021077fbd763a9f31475b56e6d714d"
)


class LicenceKeyError(UserError):
    """Der eingegebene Schlüssel ist nicht verwendbar — mit Grund.

    Warum eigene Gründe und nicht ein schlichtes „ungültig": „Dieser Schlüssel
    gilt für eine andere Hauptversion" ist eine Auskunft, mit der jemand etwas
    anfangen kann. „Ungültig" ist eine Sackgasse (§2.7).
    """

    default_title: ClassVar[TranslatableText] = _("Dieser Lizenzschlüssel ist nicht verwendbar.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (CORRECT_INPUT, BUY_LICENCE)


@dataclass(frozen=True, slots=True)
class Licence:
    """Was ein gültiger Schlüssel aussagt."""

    major: int
    """Hauptversion, für die er gilt — alle Punktversionen darunter sind
    eingeschlossen (das ist das Versprechen „alle 1.x-Updates inklusive")."""
    purchased_on: date
    order: str
    """Bestellkennung des Zahlungsanbieters. Macht einen Schlüssel im
    Support-Fall zuordenbar; gezeigt wird sie im Freischaltdialog."""
    holder: str
    """Auf wen er lautet."""


def _normalise(text: str) -> str:
    """Macht aus allem, was jemand einfügt, den reinen Nutzlast-Text.

    Zeilenumbrüche, Leerzeichen und Bindestriche fallen weg — ein Schlüssel,
    der über drei Zeilen einer E-Mail kam, soll sich einfügen lassen.

    Alles andere fällt **nicht** weg. Ein stillschweigend verschlucktes Zeichen
    verschiebt die Nutzlast um fünf Bit, und der Nutzer bekommt „die Signatur
    passt nicht" statt eines Hinweises auf die Stelle. Die drei klassischen
    Vertipper werden zurückgebogen, der Rest wird benannt.
    """
    upper = text.strip().upper()
    head = f"{PREFIX}-{FORMAT_VERSION}-"
    if not upper.startswith(head):
        raise LicenceKeyError(
            detail=_("Der Schlüssel beginnt nicht mit „SOLIDON3D-1-“."),
            values={"expected_prefix": head},
        )
    body = []
    for character in upper[len(head) :]:
        if character in SEPARATORS:
            continue
        corrected = CONFUSABLE.get(character, character)
        if corrected not in ALPHABET:
            raise LicenceKeyError(
                detail=_("Der Schlüssel enthält ein Zeichen, das im Schlüsselalphabet fehlt."),
                values={"character": character},
            )
        body.append(corrected)
    return "".join(body)


def _decode(body: str) -> bytes:
    padded = body + "=" * (-len(body) % 8)
    try:
        return base64.b32decode(padded)
    except Exception as problem:
        raise LicenceKeyError(
            detail=_("Der Schlüssel ist unvollständig oder enthält fremde Zeichen.")
        ) from problem


def encode(licence: Licence) -> bytes:
    """Die Nutzlast als Bytes — genau das, was signiert wird.

    Steht hier und nicht im Erzeugungswerkzeug, damit beide Seiten dasselbe
    Layout benutzen. Zwei Umsetzungen wären der Weg zu einer Signatur, die nur
    eine Seite versteht.
    """
    order = licence.order.encode("ascii")
    holder = licence.holder.encode("utf-8")
    if len(order) > 255 or len(holder) > 255:
        raise ValueError("order and holder are length-prefixed with a single byte")
    days = (licence.purchased_on - EPOCH).days
    if not 0 <= days <= 0xFFFF:
        raise ValueError(f"purchase date outside the two-byte range: {licence.purchased_on}")
    payload = bytearray([FORMAT_VERSION, licence.major, days >> 8, days & 0xFF])
    for field in (order, holder):
        payload.append(len(field))
        payload.extend(field)
    return bytes(payload)


def _decode_payload(payload: bytes) -> Licence:
    """Zerlegt die Nutzlast. Jede Längenangabe wird geprüft, bevor sie
    verwendet wird — eine signierte Nutzlast ist echt, aber nicht
    notwendigerweise heil."""
    if len(payload) < 6:
        raise LicenceKeyError(detail=_("Der Schlüssel ist zu kurz."))
    if payload[0] != FORMAT_VERSION:
        raise LicenceKeyError(
            detail=_(
                "Der Schlüssel ist in einem Format geschrieben, das diese Version nicht kennt."
            )
        )
    order_end = 5 + payload[4]
    if len(payload) < order_end + 1:
        raise LicenceKeyError(detail=_("Der Schlüssel ist zu kurz."))
    holder_end = order_end + 1 + payload[order_end]
    if len(payload) != holder_end:
        raise LicenceKeyError(detail=_("Der Schlüssel ist zu kurz."))
    try:
        order = payload[5:order_end].decode("ascii")
        holder = payload[order_end + 1 : holder_end].decode("utf-8")
    except UnicodeDecodeError as problem:
        raise LicenceKeyError(
            detail=_("Der Schlüssel enthält Zeichen, die dort nicht stehen können.")
        ) from problem
    return Licence(
        major=payload[1],
        purchased_on=EPOCH + timedelta(days=(payload[2] << 8) | payload[3]),
        order=order,
        holder=holder,
    )


def parse(text: str, public_key: bytes | None = None, major: int | None = None) -> Licence:
    """Liest, prüft und zerlegt einen Schlüssel — oder erklärt, warum nicht.

    ``major`` ist die Hauptversion, die gelten muss; ohne Angabe wird die der
    laufenden Anwendung genommen. Die Reihenfolge der Prüfungen ist Absicht:
    **erst die Signatur, dann der Inhalt.** Was nicht signiert ist, ist keine
    Aussage, über deren Bedeutung sich zu streiten lohnt.

    ``public_key`` und ``major`` sind ``None`` und nicht mit dem Modulwert
    vorbelegt: ein Vorgabewert wird beim Import gebunden, und dann wäre der
    Schlüssel eingefroren, mit dem geprüft wird. Genau daran ist die erste
    Version dieser Funktion in der Suite aufgefallen.
    """
    raw = _decode(_normalise(text))
    if len(raw) <= ed25519.SIGNATURE_BYTES:
        raise LicenceKeyError(detail=_("Der Schlüssel ist zu kurz."))
    payload = raw[: -ed25519.SIGNATURE_BYTES]
    signer = PUBLIC_KEY if public_key is None else public_key
    if not ed25519.verify(signer, payload, raw[-ed25519.SIGNATURE_BYTES :]):
        raise LicenceKeyError(
            detail=_("Die Signatur passt nicht — der Schlüssel wurde verändert oder abgetippt.")
        )
    licence = _decode_payload(payload)
    expected = current_major() if major is None else major
    if licence.major != expected:
        raise LicenceKeyError(
            detail=_("Dieser Schlüssel gilt für eine andere Hauptversion von Solidon."),
            values={"key_major": licence.major, "app_major": expected},
        )
    return licence


def current_major() -> int:
    """Die Hauptversion der laufenden Anwendung."""
    from app.branding import APP_VERSION

    return int(APP_VERSION.split(".")[0])


def format_key(payload: bytes, signature: bytes) -> str:
    """Schreibt Nutzlast und Signatur als Schlüsseltext. Vom Erzeugungswerkzeug
    benutzt; die Anwendung liest nur."""
    body = base64.b32encode(payload + signature).decode("ascii").rstrip("=")
    groups = [body[index : index + GROUP_SIZE] for index in range(0, len(body), GROUP_SIZE)]
    return "-".join([PREFIX, str(FORMAT_VERSION), *groups])
