"""Signierte Geräteanforderung und signiertes Aktivierungszertifikat.

Beide Richtungen benutzen ein kleines JSON-Dokument, dessen ``payload`` als
unveränderte Bytes signiert wird. Damit müssen Python-Anwendung, PHP-Dienst
und Offline-Weg keine zwei vermeintlich gleichen JSON-Serialisierungen
nachbauen. Der Kaufcode und der öffentliche Geräteteil dürfen offen reisen;
der private Geräteteil verlässt den System-Schlüsselbund nie.

Ein Zertifikat trägt kein Ablaufdatum. Nach der einmaligen Aktivierung bleibt
Solidon ohne Netz, Konto und regelmäßige Rückfrage verwendbar.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any, ClassVar, Final

from app.core.activation import device, ed25519, key, store
from app.core.errors import (
    ACTIVATE_OFFLINE,
    ACTIVATE_ONLINE,
    CANCEL,
    CORRECT_INPUT,
    Action,
    UserError,
)
from app.core.json_boundary import loads as load_json
from app.core.log import get_logger
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

DOCUMENT_FORMAT: Final = 1
REQUEST_KIND: Final = "activation-request"
CERTIFICATE_KIND: Final = "activation-certificate"
DEACTIVATION_KIND: Final = "deactivation-request"

#: Öffentlicher Schlüssel des Aktivierungsdienstes. Der private Startwert
#: liegt ausschließlich in der Serverkonfiguration und ist ausdrücklich ein
#: anderes Paar als der Aussteller der Kaufcodes.
#:
#: Das Paar wurde am 28.08.2026 mit ``tools/setup_activation_server.py``
#: erzeugt. Der private Startwert liegt außerhalb des Arbeitsbaums und wird
#: vor dem Verkaufsbau als Servergeheimnis außerhalb von ``httpdocs``
#: eingerichtet. Dieser öffentliche Teil ist gegen ihn geprüft.
ACTIVATION_PUBLIC_KEY: Final = bytes.fromhex(
    "52e0682ff6d864d4c07809c2ec48728f435fd4b2e1f18dbd5a60561f524887c6"
)


#: Wie groß eine Aktivierungsdatei höchstens sein darf.
#:
#: Sie trägt einen Gerätenamen (höchstens 80 Zeichen), zwei Base64-Felder von
#: je unter hundert Byte und den Kaufcode — zusammen deutlich unter einem
#: Kilobyte. Sechzehn sind reichlich Luft und immer noch eine Grenze: Die
#: Datei kommt vom Dienst oder von einem USB-Stick, also von jemand anderem
#: (§32), und wird deshalb wie jedes fremde JSON gelesen — mit Deckel für
#: Bytes, Tiefe und Knotenzahl und **ohne** doppelte Schlüssel. Zwei
#: Auslegungen derselben signierten Nachricht wären keine Grundlage für eine
#: Entscheidung.
MAX_DOCUMENT_BYTES: Final = 16 * 1024


class ActivationDocumentError(UserError):
    """Eine Aktivierungsdatei ist unvollständig, fremd oder verändert."""

    default_title: ClassVar[TranslatableText] = _("Die Aktivierungsdatei ist nicht verwendbar.")
    default_suggestions: ClassVar[tuple[Action, ...]] = (
        CORRECT_INPUT,
        ACTIVATE_ONLINE,
        ACTIVATE_OFFLINE,
        CANCEL,
    )


@dataclass(frozen=True, slots=True)
class ActivationRequest:
    """Eine vom Gerät bestätigte Bitte um genau eine Aktivierung."""

    licence: key.Licence
    licence_text: str
    licence_digest: str
    device_public: bytes
    device_name: str
    request_id: str


@dataclass(frozen=True, slots=True)
class ActivationCertificate:
    """Die signierte Freigabe einer Lizenz für genau ein Gerätepaar."""

    licence_digest: str
    device_public: bytes
    device_name: str
    activation_id: str
    issued_on: date


@dataclass(frozen=True, slots=True)
class DeactivationRequest:
    """Vom aktuell aktivierten Gerät signierte Freigabe seines Serverplatzes."""

    licence: key.Licence
    licence_digest: str
    device_public: bytes
    activation_id: str


def encode_text(data: bytes) -> str:
    """URL-sicheres Base64 ohne bedeutungslose Auffüllzeichen."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def decode_text(text: object) -> bytes:
    """Liest die Transportkodierung oder wirft einen erklärten Dateifehler."""
    if not isinstance(text, str):
        raise ActivationDocumentError(detail=_("Ein Datenfeld der Aktivierungsdatei fehlt."))
    try:
        return base64.b64decode(
            text + "=" * (-len(text) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, TypeError) as problem:
        raise ActivationDocumentError(
            detail=_("Ein Datenfeld der Aktivierungsdatei ist unvollständig.")
        ) from problem


def _canonical(values: dict[str, object]) -> bytes:
    return json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def signed_document(kind: str, payload: bytes, signature: bytes) -> str:
    """Die gemeinsame Hülle für Online- und Dateiweg."""
    return json.dumps(
        {
            "format": DOCUMENT_FORMAT,
            "kind": kind,
            "payload": encode_text(payload),
            "signature": encode_text(signature),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _document(text: str, expected_kind: str) -> tuple[dict[str, Any], bytes, bytes]:
    try:
        document = load_json(text, max_bytes=MAX_DOCUMENT_BYTES)
    except (TypeError, ValueError) as problem:
        raise ActivationDocumentError(
            detail=_("Die Datei enthält kein vollständiges Aktivierungsdokument.")
        ) from problem
    if not isinstance(document, dict):
        raise ActivationDocumentError(detail=_("Die Aktivierungsdatei hat den falschen Aufbau."))
    if document.get("format") != DOCUMENT_FORMAT or document.get("kind") != expected_kind:
        raise ActivationDocumentError(
            detail=_("Die Aktivierungsdatei gehört zu einem anderen Format oder Schritt.")
        )
    payload = decode_text(document.get("payload"))
    signature = decode_text(document.get("signature"))
    return document, payload, signature


def _payload_values(payload: bytes) -> dict[str, Any]:
    try:
        values = load_json(payload, max_bytes=MAX_DOCUMENT_BYTES)
    except ValueError as problem:
        raise ActivationDocumentError(
            detail=_("Die signierten Aktivierungsdaten sind unvollständig.")
        ) from problem
    if not isinstance(values, dict):
        raise ActivationDocumentError(
            detail=_("Die signierten Aktivierungsdaten haben den falschen Aufbau.")
        )
    return values


def licence_digest(licence: key.Licence) -> str:
    """Stabile Kennung der signierten Kauf-Aussage, ohne Kundendaten im Klartext."""
    return hashlib.sha256(key.encode(licence)).hexdigest()


def create_request(licence_text: str, device_name: str) -> str:
    """Erzeugt die Datei/Netznachricht nach einem ausdrücklichen Nutzerklick."""
    licence = key.parse(licence_text)
    name = " ".join(device_name.split()).strip()
    if not name or len(name) > 80:
        raise ActivationDocumentError(
            detail=_("Der Gerätename muss zwischen 1 und 80 Zeichen lang sein.")
        )
    digest = licence_digest(licence)
    public = device.ensure_public_key()
    request_id = hashlib.sha256(public + digest.encode("ascii")).hexdigest()[:32]
    payload = _canonical(
        {
            "device_name": name,
            "device_public": encode_text(public),
            "format": DOCUMENT_FORMAT,
            "kind": REQUEST_KIND,
            "licence_digest": digest,
            "request_id": request_id,
        }
    )
    signer, signature = device.sign(payload)
    if signer != public:  # pragma: no cover - nur bei kaputtem Schlüsselbund während des Klicks
        raise ActivationDocumentError(
            detail=_("Die Geräteidentität hat sich während der Aktivierung geändert.")
        )
    document = json.loads(signed_document(REQUEST_KIND, payload, signature))
    document["licence"] = licence_text.strip()
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def create_deactivation(
    licence_text: str,
    installed: ActivationCertificate | None = None,
) -> str:
    """Baut die ausdrückliche, vom aktivierten Gerät bestätigte Abmeldung."""
    licence = key.parse(licence_text)
    certificate = installed or load_for(licence)
    if certificate is None:
        raise ActivationDocumentError(
            detail=_("Dieser Rechner besitzt kein gültiges Geräte-Zertifikat.")
        )
    payload = _canonical(
        {
            "activation_id": certificate.activation_id,
            "device_public": encode_text(certificate.device_public),
            "format": DOCUMENT_FORMAT,
            "kind": DEACTIVATION_KIND,
            "licence_digest": certificate.licence_digest,
        }
    )
    signer, signature = device.sign(payload)
    if signer != certificate.device_public:
        raise ActivationDocumentError(
            detail=_("Geräte-Zertifikat und Geräteidentität gehören nicht zusammen.")
        )
    document = json.loads(signed_document(DEACTIVATION_KIND, payload, signature))
    document["licence"] = licence_text.strip()
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_deactivation(
    text: str,
    *,
    licence_public_key: bytes | None = None,
) -> DeactivationRequest:
    """Prüft den Abmeldenachweis; der PHP-Dienst bildet dieselben Regeln nach."""
    document, payload, signature = _document(text, DEACTIVATION_KIND)
    licence_text = document.get("licence")
    if not isinstance(licence_text, str):
        raise ActivationDocumentError(detail=_("Der Lizenzschlüssel fehlt in der Abmeldung."))
    licence = key.parse(licence_text, public_key=licence_public_key)
    values = _payload_values(payload)
    try:
        public = decode_text(values["device_public"])
        digest = str(values["licence_digest"])
        activation_id = str(values["activation_id"])
    except KeyError as problem:
        raise ActivationDocumentError(
            detail=_("In der Geräteabmeldung fehlt eine signierte Angabe.")
        ) from problem
    if values.get("format") != DOCUMENT_FORMAT or values.get("kind") != DEACTIVATION_KIND:
        raise ActivationDocumentError(detail=_("Die Geräteabmeldung hat das falsche Format."))
    if digest != licence_digest(licence) or not ed25519.verify(public, payload, signature):
        raise ActivationDocumentError(
            detail=_("Lizenzschlüssel und Geräteabmeldung gehören nicht zusammen.")
        )
    if len(activation_id) != 32 or any(
        character not in "0123456789abcdef" for character in activation_id
    ):
        raise ActivationDocumentError(detail=_("Die Aktivierungskennung ist unvollständig."))
    return DeactivationRequest(licence, digest, public, activation_id)


def parse_request(
    text: str,
    *,
    licence_public_key: bytes | None = None,
) -> ActivationRequest:
    """Prüft eine Anforderung; dieselben Regeln bildet der PHP-Dienst nach."""
    document, payload, signature = _document(text, REQUEST_KIND)
    licence_text = document.get("licence")
    if not isinstance(licence_text, str):
        raise ActivationDocumentError(detail=_("Der Lizenzschlüssel fehlt in der Anforderung."))
    licence = key.parse(licence_text, public_key=licence_public_key)
    values = _payload_values(payload)
    try:
        public = decode_text(values["device_public"])
        name = str(values["device_name"])
        digest = str(values["licence_digest"])
        request_id = str(values["request_id"])
    except KeyError as problem:
        raise ActivationDocumentError(
            detail=_("In der Aktivierungsanforderung fehlt eine Geräteangabe.")
        ) from problem
    if values.get("format") != DOCUMENT_FORMAT or values.get("kind") != REQUEST_KIND:
        raise ActivationDocumentError(
            detail=_("Die Aktivierungsanforderung gehört zu einem anderen Format.")
        )
    if digest != licence_digest(licence):
        raise ActivationDocumentError(
            detail=_("Lizenzschlüssel und Aktivierungsanforderung gehören nicht zusammen.")
        )
    expected_id = hashlib.sha256(public + digest.encode("ascii")).hexdigest()[:32]
    if request_id != expected_id or not ed25519.verify(public, payload, signature):
        raise ActivationDocumentError(
            detail=_("Die Geräte-Signatur der Aktivierungsanforderung passt nicht.")
        )
    if not name.strip() or len(name) > 80:
        raise ActivationDocumentError(detail=_("Der Gerätename ist unvollständig."))
    return ActivationRequest(licence, licence_text, digest, public, name, request_id)


def certificate_payload(
    request: ActivationRequest,
    *,
    activation_id: str,
    issued_on: date,
) -> bytes:
    """Die kanonische Zertifikatsnutzlast für Dienst und Integrationstest."""
    return _canonical(
        {
            "activation_id": activation_id,
            "device_name": request.device_name,
            "device_public": encode_text(request.device_public),
            "format": DOCUMENT_FORMAT,
            "issued_on": issued_on.isoformat(),
            "kind": CERTIFICATE_KIND,
            "licence_digest": request.licence_digest,
        }
    )


def parse_certificate(
    text: str,
    licence: key.Licence,
    device_public: bytes,
    *,
    activation_public_key: bytes | None = None,
) -> ActivationCertificate:
    """Prüft Unterschrift, Kaufcodebindung und Gerät — jeder Fehler sperrt."""
    _document_values, payload, signature = _document(text, CERTIFICATE_KIND)
    signer = ACTIVATION_PUBLIC_KEY if activation_public_key is None else activation_public_key
    if not ed25519.verify(signer, payload, signature):
        raise ActivationDocumentError(detail=_("Die Signatur des Geräte-Zertifikats passt nicht."))
    values = _payload_values(payload)
    try:
        public = decode_text(values["device_public"])
        digest = str(values["licence_digest"])
        name = str(values["device_name"])
        activation_id = str(values["activation_id"])
        issued_on = date.fromisoformat(str(values["issued_on"]))
    except (KeyError, ValueError) as problem:
        raise ActivationDocumentError(
            detail=_("Im Geräte-Zertifikat fehlt eine signierte Angabe.")
        ) from problem
    if values.get("format") != DOCUMENT_FORMAT or values.get("kind") != CERTIFICATE_KIND:
        raise ActivationDocumentError(detail=_("Das Geräte-Zertifikat hat das falsche Format."))
    if digest != licence_digest(licence):
        raise ActivationDocumentError(
            detail=_("Das Geräte-Zertifikat gehört zu einem anderen Lizenzschlüssel.")
        )
    if public != device_public:
        raise ActivationDocumentError(
            detail=_("Das Geräte-Zertifikat gehört zu einem anderen Rechner.")
        )
    if len(activation_id) != 32 or any(
        character not in "0123456789abcdef" for character in activation_id
    ):
        raise ActivationDocumentError(detail=_("Die Aktivierungskennung ist unvollständig."))
    return ActivationCertificate(digest, public, name, activation_id, issued_on)


def load_for(licence: key.Licence) -> ActivationCertificate | None:
    """Liest das lokale Zertifikat; jedes Problem bleibt ein gesperrter Zustand."""
    text = store.read_certificate()
    public = device.public_key()
    if text is None or public is None:
        return None
    try:
        return parse_certificate(text, licence, public)
    except ActivationDocumentError as problem:
        _log.warning("stored activation certificate rejected: %s", problem.detail)
        return None


def install(text: str, licence_text: str | None = None) -> ActivationCertificate:
    """Prüft eine Antwort vollständig, bevor sie lokal abgelegt wird."""
    stored = licence_text or store.read_key()
    if stored is None:
        raise ActivationDocumentError(
            detail=_("Tragen Sie zuerst den Lizenzschlüssel aus der Bestellmail ein.")
        )
    licence = key.parse(stored)
    public = device.public_key()
    if public is None:
        raise ActivationDocumentError(
            detail=_("Auf diesem Rechner wurde noch keine Aktivierungsanforderung erzeugt.")
        )
    certificate = parse_certificate(text, licence, public)
    if not store.write_certificate(text):
        raise ActivationDocumentError(
            detail=_("Das geprüfte Geräte-Zertifikat ließ sich nicht im Profil ablegen.")
        )
    return certificate
