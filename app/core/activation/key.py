"""Das Format des Lizenzschlüssels: lesen, prüfen, zerlegen.

Ein Schlüssel ist eine signierte Nutzlast, in Base32 geschrieben:

    SOLIDON3D-2-ABCDEFGH-IJKLMNOP-...

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

Seit dem 15.09.2026 trägt die Nutzlast außerdem die **Lizenzart** — privat
oder gewerblich. Sie ist keine Funktionsgrenze: beide Arten können dasselbe
(`konzept-lizenzarten-2026-09.md`, Entscheidung A). Sie steht im Schlüssel,
damit ein gewerblicher Arbeitsplatz belegen kann, dass er richtig lizenziert
ist, ohne eine Bestellmail zu suchen.

Dafür gibt es ein zweites Format, und das erste bleibt lesbar: Ein Schlüssel
aus Format 1 nennt keine Art und **ist** damit eine private Lizenz — das war
seine Bedeutung beim Ausstellen. Neu ausgegeben wird nur noch Format 2.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date, timedelta
from enum import IntEnum
from typing import ClassVar, Final

from app.core.activation import ed25519
from app.core.errors import BUY_LICENCE, CANCEL, CHECK_UPDATES, CORRECT_INPUT, Action, UserError
from app.i18n import TranslatableText, _

#: Was vor der Nutzlast steht. Wird beim Lesen verlangt, damit eine
#: hineingerutschte Zeichenkette anderer Herkunft sofort auffällt.
PREFIX: Final = "SOLIDON3D"

#: Version des Schlüsselformats, in der **ausgestellt** wird. Steht im Text
#: **und** signiert in der Nutzlast: nur der Text wäre umdeutbar, sobald es
#: eine zweite Version gibt — und seit dem 15.09.2026 gibt es sie. Beide
#: müssen übereinstimmen, sonst ist der Schlüssel nicht verwendbar.
FORMAT_VERSION: Final = 2

#: Welche Formate **gelesen** werden. Format 1 bleibt darunter, solange es
#: einen ausgegebenen Schlüssel geben kann: Ein Bestandsschlüssel muss in fünf
#: Jahren noch freischalten. Ältere Formate werden nie zusammengefasst
#: (Checkliste „Dateiformat ändern" in ``AGENTS.md``).
READABLE_VERSIONS: Final = (1, 2)

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


class LicenceKind(IntEnum):
    """Wofür eine Lizenz gekauft wurde — privat oder gewerblich.

    Ein **Byte** in der Nutzlast und nicht ein Bit im Hauptversionsbyte: 254
    freie Werte kosten nichts und nehmen einer späteren Bildungs-, Behörden-
    oder Mehrplatzlizenz den Formatwechsel ab.

    Was die Art **nicht** tut: Funktionen sperren. Beide Arten können dasselbe
    (Entscheidung A). Sie sagt auch nicht, ob jemand tatsächlich gewerblich
    arbeitet — das kann Solidon nicht prüfen und soll es nicht; wer mit einer
    privaten Lizenz gewerblich arbeitet, verstößt gegen den Vertrag und nicht
    gegen eine Programmsperre (Entscheidung J).
    """

    PRIVATE = 1
    COMMERCIAL = 2


#: Wie viele Rechner je Lizenzart **gleichzeitig** freigeschaltet sein dürfen.
#:
#: Das ist der eine Unterschied, den die gewerbliche Lizenz im Programm hat —
#: und er sperrt nichts, er gibt etwas dazu (Entscheidung Robert, 15.09.2026).
#: Im Betrieb steht Solidon auf dem Arbeitsplatz und auf dem Notebook, und wer
#: zwischen beiden wechselt, soll nicht jedes Mal deaktivieren.
#:
#: Der Aktivierungsdienst führt dieselbe Tabelle
#: (``ACTIVATION_DEVICE_LIMITS`` in ``website/api/activation_common.php``) und
#: entscheidet damit; hier steht sie, weil Handbuch, Dialog und Rechtstexte
#: dieselbe Zahl nennen müssen.
DEVICE_LIMITS: Final[dict[LicenceKind, int]] = {
    LicenceKind.PRIVATE: 1,
    LicenceKind.COMMERCIAL: 2,
}


def device_limit(kind: LicenceKind) -> int:
    """Wie viele Rechner diese Lizenzart gleichzeitig freischalten darf."""
    return DEVICE_LIMITS[kind]


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
    kind: LicenceKind = LicenceKind.PRIVATE
    """Privat oder gewerblich. Der Vorgabewert ist keine Bequemlichkeit,
    sondern die Bedeutung von Format 1: Ein Schlüssel ohne Artangabe **ist**
    eine private Lizenz. Wo die Art eine Entscheidung ist — beim Ausstellen —
    verlangt das Werkzeug sie ausdrücklich und rät nicht."""
    format_version: int = FORMAT_VERSION
    """In welchem Format dieser Schlüssel geschrieben ist.

    Das Feld ist nicht Zierde, sondern die Bedingung dafür, dass Format 1
    weiter gilt: :func:`certificate.licence_digest` hasht die Nutzlast aus
    :func:`encode`, und ein Bestandsschlüssel muss dabei **byteweise** seine
    ursprüngliche Nutzlast ergeben. Ohne das Feld wüsste ``encode`` nicht, in
    welchem Format es schreiben soll, und der Digest eines
    Format-1-Schlüssels wäre nach dem Lesen ein anderer als beim Server."""


def _normalise(text: str) -> tuple[int, str]:
    """Macht aus allem, was jemand einfügt, den reinen Nutzlast-Text.

    Zurück kommt die im **Kopf** genannte Formatversion und der Rumpf. Der
    Kopf ist unsigniert und damit keine Aussage, auf die man baut — geprüft
    wird er gegen die signierte Version in der Nutzlast (:func:`parse`). Hier
    entscheidet er nur, ob der Text überhaupt nach einem Solidon-Schlüssel
    aussieht.

    Zeilenumbrüche, Leerzeichen und Bindestriche fallen weg — ein Schlüssel,
    der über drei Zeilen einer E-Mail kam, soll sich einfügen lassen.

    Alles andere fällt **nicht** weg. Ein stillschweigend verschlucktes Zeichen
    verschiebt die Nutzlast um fünf Bit, und der Nutzer bekommt „die Signatur
    passt nicht" statt eines Hinweises auf die Stelle. Die drei klassischen
    Vertipper werden zurückgebogen, der Rest wird benannt.
    """
    upper = text.strip().upper()
    for version in READABLE_VERSIONS:
        head = f"{PREFIX}-{version}-"
        if upper.startswith(head):
            break
    else:
        raise LicenceKeyError(
            detail=_("Der Schlüssel beginnt nicht mit „SOLIDON3D-“ und einer Formatnummer."),
            values={"expected_prefix": f"{PREFIX}-{FORMAT_VERSION}-"},
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
    return version, "".join(body)


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

    Geschrieben wird in dem Format, das die Lizenz nennt — nicht im neuesten.
    Sonst bekäme ein gelesener Bestandsschlüssel beim Hashen eine andere
    Nutzlast, als er selbst trägt, und sein Digest passte nicht mehr zu dem,
    den der Aktivierungsserver berechnet. **Format 1 kennt keine Lizenzart**;
    eine gewerbliche Lizenz lässt sich darin nicht ausdrücken und wird
    abgelehnt statt stillschweigend als privat geschrieben.
    """
    if licence.format_version not in READABLE_VERSIONS:
        raise ValueError(f"unknown key format: {licence.format_version}")
    if licence.format_version == 1 and licence.kind is not LicenceKind.PRIVATE:
        raise ValueError("format 1 cannot express a licence kind")
    order = licence.order.encode("ascii")
    holder = licence.holder.encode("utf-8")
    if len(order) > 255 or len(holder) > 255:
        raise ValueError("order and holder are length-prefixed with a single byte")
    days = (licence.purchased_on - EPOCH).days
    if not 0 <= days <= 0xFFFF:
        raise ValueError(f"purchase date outside the two-byte range: {licence.purchased_on}")
    payload = bytearray([licence.format_version, licence.major, days >> 8, days & 0xFF])
    if licence.format_version >= 2:
        payload.append(int(licence.kind))
    for field in (order, holder):
        payload.append(len(field))
        payload.extend(field)
    return bytes(payload)


def _decode_payload(payload: bytes) -> Licence:
    """Zerlegt die Nutzlast. Jede Längenangabe wird geprüft, bevor sie
    verwendet wird — eine signierte Nutzlast ist echt, aber nicht
    notwendigerweise heil.

    Die Formatversion steht im ersten Byte und entscheidet, ob hinter dem
    Kaufdatum ein Byte für die Lizenzart liegt. Beides ist signiert; ein
    Angreifer kann also nicht Format 1 behaupten, um die Art zu verschlucken.
    """
    if not payload:
        raise LicenceKeyError(detail=_("Der Schlüssel ist zu kurz."))
    version = payload[0]
    if version not in READABLE_VERSIONS:
        raise LicenceKeyError(
            detail=_(
                "Der Schlüssel ist in einem Format geschrieben, das diese Version nicht kennt."
            ),
            suggestions=(CHECK_UPDATES, CANCEL),
        )
    #: Wo die Längenangabe der Bestellkennung steht: hinter dem Kaufdatum in
    #: Format 1, hinter der Lizenzart in Format 2.
    order_length_at = 4 if version == 1 else 5
    if len(payload) < order_length_at + 2:
        raise LicenceKeyError(detail=_("Der Schlüssel ist zu kurz."))
    kind = LicenceKind.PRIVATE
    if version >= 2:
        try:
            kind = LicenceKind(payload[4])
        except ValueError as problem:
            # Ein Schlüssel aus der Zukunft — eine Bildungs- oder
            # Mehrplatzlizenz, deren Bedingungen diese Version nicht kennt.
            # Sie zu raten wäre schlimmer als abzulehnen (Regel 21).
            raise LicenceKeyError(
                detail=_("Der Schlüssel gilt für eine Lizenzart, die diese Version nicht kennt."),
                values={"kind": payload[4]},
                suggestions=(CHECK_UPDATES, CANCEL),
            ) from problem
    order_start = order_length_at + 1
    order_end = order_start + payload[order_length_at]
    if len(payload) < order_end + 1:
        raise LicenceKeyError(detail=_("Der Schlüssel ist zu kurz."))
    holder_end = order_end + 1 + payload[order_end]
    if len(payload) != holder_end:
        raise LicenceKeyError(detail=_("Der Schlüssel ist zu kurz."))
    try:
        order = payload[order_start:order_end].decode("ascii")
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
        kind=kind,
        format_version=version,
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
    head_version, body = _normalise(text)
    raw = _decode(body)
    if len(raw) <= ed25519.SIGNATURE_BYTES:
        raise LicenceKeyError(detail=_("Der Schlüssel ist zu kurz."))
    payload = raw[: -ed25519.SIGNATURE_BYTES]
    signer = PUBLIC_KEY if public_key is None else public_key
    if not ed25519.verify(signer, payload, raw[-ed25519.SIGNATURE_BYTES :]):
        raise LicenceKeyError(
            detail=_("Die Signatur passt nicht — der Schlüssel wurde verändert oder abgetippt.")
        )
    licence = _decode_payload(payload)
    # Der Kopf ist unsigniert, die Nutzlast nicht. Wer den Kopf umschreibt,
    # ändert die Bedeutung des Schlüssels nicht — aber er bekommt auch keinen
    # halb gelesenen: Widersprechen sich beide, ist das kein Schlüssel.
    if licence.format_version != head_version:
        # Ohne Werte: „vorn 1, innen 2" hilft niemandem weiter, der einen
        # veränderten Schlüssel eingegeben hat, und jeder Befundwert braucht
        # eine Beschriftung in ``labels.py`` (``test_every_value_key_has_a_label``).
        raise LicenceKeyError(detail=_("Der Schlüssel nennt vorn ein anderes Format als innen."))
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
    benutzt; die Anwendung liest nur.

    Die Formatnummer im Kopf kommt aus der **Nutzlast** und nicht aus
    :data:`FORMAT_VERSION`: Sonst trüge ein neu geschriebener
    Bestandsschlüssel vorn eine 2 und innen eine 1, und :func:`parse` würde
    ihn zu Recht ablehnen.
    """
    if not payload or payload[0] not in READABLE_VERSIONS:
        raise ValueError("payload does not start with a readable format version")
    body = base64.b32encode(payload + signature).decode("ascii").rstrip("=")
    groups = [body[index : index + GROUP_SIZE] for index in range(0, len(body), GROUP_SIZE)]
    return "-".join([PREFIX, str(payload[0]), *groups])
