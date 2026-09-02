"""Gerätebindung: Anforderung, Zertifikat und die harte Verkaufsgrenze.

Die Tests benutzen zwei voneinander getrennte Schlüsselpaare: Das erste
stellt Kaufcodes aus, das zweite Geräte-Zertifikate. Genau diese Trennung muss
auch der Dienst halten — ein Einbruch dort darf nie neue Kaufcodes erlauben.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.core import activation, licence_service
from app.core.activation import certificate, device, ed25519, key, store
from app.core.errors import DeviceActivationRequired, DeviceDeactivationPending
from app.core.licence_service import ActivationServiceError, activate, deactivate
from tools.make_licence_keys import make_key

LICENCE_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
ACTIVATION_SEED = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")


class _MemoryKeyring:
    """Ein Schlüsselbund ohne Maschine — nur für diesen Testprozess."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self.values.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        self.values[(service, account)] = value

    def delete_password(self, service: str, account: str) -> None:
        self.values.pop((service, account), None)


@pytest.fixture
def activation_place(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[_MemoryKeyring, str]:
    config = tmp_path / "config"
    data = tmp_path / "data"
    config.mkdir()
    data.mkdir()
    keyring = _MemoryKeyring()
    monkeypatch.setattr(store, "user_config_dir", lambda: config)
    monkeypatch.setattr(store, "user_data_dir", lambda: data)
    monkeypatch.setattr(device, "_load_keyring", lambda: keyring)
    monkeypatch.setattr(key, "PUBLIC_KEY", ed25519.public_key(LICENCE_SEED))
    monkeypatch.setattr(certificate, "ACTIVATION_PUBLIC_KEY", ed25519.public_key(ACTIVATION_SEED))
    monkeypatch.setattr(store, "DEMO_UNTIL", None)
    monkeypatch.setattr(store, "TRIAL_FROM", None)
    activation.forget_cache()
    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="A-1234",
        holder="kundin@beispiel.de",
    )
    text = make_key(LICENCE_SEED, licence)
    yield keyring, text
    activation.forget_cache()


def _issue(request: certificate.ActivationRequest) -> str:
    payload = certificate.certificate_payload(
        request,
        activation_id="0123456789abcdef0123456789abcdef",
        issued_on=date(2026, 11, 1),
    )
    return certificate.signed_document(
        certificate.CERTIFICATE_KIND,
        payload,
        ed25519.sign(ACTIVATION_SEED, payload),
    )


def test_the_two_shipped_public_keys_are_valid_and_separate() -> None:
    point = ed25519.decompress(certificate.ACTIVATION_PUBLIC_KEY)

    assert point is not None, "der Aktivierungsdienst trägt keinen Platzhalter mehr"
    assert not ed25519.has_small_order(point)
    assert certificate.ACTIVATION_PUBLIC_KEY != key.PUBLIC_KEY


def test_the_device_request_proves_possession_of_the_local_key(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    keyring, licence_text = activation_place

    document = certificate.create_request(licence_text, "Werkstatt-PC")
    request = certificate.parse_request(
        document, licence_public_key=ed25519.public_key(LICENCE_SEED)
    )

    assert request.device_name == "Werkstatt-PC"
    assert request.licence.order == "A-1234"
    assert ed25519.decompress(request.device_public) is not None
    assert keyring.values, "der private Geräteteil liegt im System-Schlüsselbund"
    assert licence_text not in "".join(keyring.values.values()), (
        "der Kaufcode ist kein Geheimnis des Geräteschlüsselbunds"
    )


def test_changing_a_signed_request_is_rejected(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    _keyring, licence_text = activation_place
    document = json.loads(certificate.create_request(licence_text, "Werkstatt-PC"))
    payload = bytearray(certificate.decode_text(document["payload"]))
    payload[-2] ^= 1
    document["payload"] = certificate.encode_text(bytes(payload))

    with pytest.raises(certificate.ActivationDocumentError):
        certificate.parse_request(
            json.dumps(document), licence_public_key=ed25519.public_key(LICENCE_SEED)
        )


def test_a_purchase_key_alone_does_not_open_the_sale_version(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    _keyring, licence_text = activation_place

    state = activation.remember(licence_text)

    assert state.licence is not None
    assert state.needs_activation
    assert not state.unlocked
    with pytest.raises(DeviceActivationRequired):
        activation.require(activation.CHANGE)


def test_the_activation_cutoff_is_exact(
    activation_place: tuple[_MemoryKeyring, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bis 31.10. bleibt Bestand lokal; ab 01.11. beginnt die Gerätebindung."""
    _keyring, _licence_text = activation_place
    legacy = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 10, 31),
        order="A-ALT",
        holder="bestand@beispiel.de",
    )
    legacy_text = make_key(LICENCE_SEED, legacy)

    state = activation.remember(legacy_text)

    assert state.unlocked
    assert state.licensed
    assert not state.needs_activation
    assert state.certificate is None


def test_a_signed_certificate_opens_only_its_device(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    _keyring, licence_text = activation_place
    activation.remember(licence_text)
    request = certificate.parse_request(
        certificate.create_request(licence_text, "Werkstatt-PC"),
        licence_public_key=ed25519.public_key(LICENCE_SEED),
    )

    installed = activation.install_certificate(_issue(request))

    assert installed.device_name == "Werkstatt-PC"
    assert activation.state().unlocked
    assert activation.state().certificate is not None
    activation.require(activation.EXPORT)


def test_an_active_licence_cannot_be_replaced_through_the_core(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    _keyring, licence_text = activation_place
    activation.remember(licence_text)
    request = certificate.parse_request(
        certificate.create_request(licence_text, "Werkstatt-PC"),
        licence_public_key=ed25519.public_key(LICENCE_SEED),
    )
    activation.install_certificate(_issue(request))
    other = make_key(
        LICENCE_SEED,
        key.Licence(
            major=key.current_major(),
            purchased_on=date(2026, 11, 2),
            order="A-5678",
            holder="andere-kundin@beispiel.de",
        ),
    )

    with pytest.raises(activation.ActiveLicenceCannotBeReplaced):
        activation.remember(other)

    assert store.read_key() == licence_text
    assert activation.state().unlocked


def test_a_temporary_keyring_error_never_deletes_the_certificate(
    activation_place: tuple[_MemoryKeyring, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein gesperrter Schlüsselbund macht lokal zu, aber nichts dauerhaft kaputt."""
    keyring, licence_text = activation_place
    activation.remember(licence_text)
    request = certificate.parse_request(
        certificate.create_request(licence_text, "Werkstatt-PC"),
        licence_public_key=ed25519.public_key(LICENCE_SEED),
    )
    installed = _issue(request)
    activation.install_certificate(installed)

    def unavailable() -> _MemoryKeyring:
        raise RuntimeError("der Schlüsselbund ist vorübergehend gesperrt")

    monkeypatch.setattr(device, "_load_keyring", unavailable)
    activation.forget_cache()

    state = activation.remember(licence_text)

    assert state.certificate is None, "ohne privaten Geräteteil bleibt die Schreibseite sicher zu"
    assert store.read_certificate() == installed, (
        "eine vorübergehende Störung löscht keine Freigabe"
    )

    monkeypatch.setattr(device, "_load_keyring", lambda: keyring)
    activation.forget_cache()
    assert activation.state().unlocked, "nach dem Entsperren gilt die vorhandene Freigabe wieder"


def test_a_copied_certificate_does_not_open_another_device(
    activation_place: tuple[_MemoryKeyring, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _keyring, licence_text = activation_place
    activation.remember(licence_text)
    request = certificate.parse_request(
        certificate.create_request(licence_text, "Erster PC"),
        licence_public_key=ed25519.public_key(LICENCE_SEED),
    )
    copied = _issue(request)
    assert activation.install_certificate(copied)

    other_keyring = _MemoryKeyring()
    monkeypatch.setattr(device, "_load_keyring", lambda: other_keyring)
    device.ensure_public_key()
    store.write_certificate(copied)
    activation.forget_cache()

    state = activation.state()
    assert state.licence is not None
    assert state.certificate is None
    assert state.needs_activation
    assert not state.unlocked


def test_tampering_with_the_certificate_never_unlocks(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    _keyring, licence_text = activation_place
    activation.remember(licence_text)
    request = certificate.parse_request(
        certificate.create_request(licence_text, "Werkstatt-PC"),
        licence_public_key=ed25519.public_key(LICENCE_SEED),
    )
    document = json.loads(_issue(request))
    signature = bytearray(certificate.decode_text(document["signature"]))
    signature[0] ^= 1
    document["signature"] = certificate.encode_text(bytes(signature))
    store.write_certificate(json.dumps(document))
    activation.forget_cache()

    state = activation.state()
    assert state.certificate is None
    assert not state.unlocked


def test_removing_the_purchase_key_removes_its_certificate(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    _keyring, licence_text = activation_place
    activation.remember(licence_text)
    request = certificate.parse_request(
        certificate.create_request(licence_text, "Werkstatt-PC"),
        licence_public_key=ed25519.public_key(LICENCE_SEED),
    )
    activation.install_certificate(_issue(request))

    assert activation.forget_key()
    assert store.read_key() is None
    assert store.read_certificate() is None
    assert not activation.state().unlocked


def test_an_unconfirmed_deactivation_stays_locked_and_can_be_repeated(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    """Eine verlorene Serverantwort darf lokal nie einen zweiten Platz öffnen."""
    _keyring, licence_text = activation_place
    activation.remember(licence_text)
    request = certificate.parse_request(
        certificate.create_request(licence_text, "Werkstatt-PC"),
        licence_public_key=ed25519.public_key(LICENCE_SEED),
    )
    activation.install_certificate(_issue(request))

    deactivation = activation.prepare_deactivation()
    assert store.read_pending_deactivation() == deactivation
    assert activation.remove_certificate()
    activation.forget_cache()

    state = activation.state()
    assert state.deactivation_pending
    assert not state.needs_activation
    assert not state.unlocked
    assert activation.prepare_deactivation() == deactivation, (
        "erneut wird derselbe Auftrag gesendet"
    )
    with pytest.raises(DeviceDeactivationPending):
        activation.create_activation_request("Zweiter Rechner")
    with pytest.raises(DeviceDeactivationPending):
        activation.require(activation.CHANGE)


def test_a_pending_deactivation_is_written_atomically(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    _keyring, _licence_text = activation_place

    assert store.write_pending_deactivation("signierter Auftrag")
    assert store.read_pending_deactivation() == "signierter Auftrag"
    assert not store.pending_deactivation_path().with_suffix(".tmp").exists()
    assert store.forget_pending_deactivation()
    assert store.read_pending_deactivation() is None


def test_the_online_client_accepts_a_certificate_but_explains_a_server_error(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    _keyring, licence_text = activation_place
    request = certificate.parse_request(
        certificate.create_request(licence_text, "Werkstatt-PC"),
        licence_public_key=ed25519.public_key(LICENCE_SEED),
    )
    answer = _issue(request).encode("utf-8")

    assert activate("{}", sender=lambda _payload: answer) == answer.decode("utf-8")

    refused = json.dumps(
        {"ok": False, "code": "device_limit", "error": "Schon auf einem Gerät aktiv."}
    ).encode()
    with pytest.raises(ActivationServiceError) as raised:
        activate("{}", sender=lambda _payload: refused)
    assert raised.value.values["code"] == "device_limit"
    assert "Schon auf einem Gerät aktiv" not in str(raised.value.detail), (
        "unübersetzte Serverprosa darf nicht direkt in der Oberfläche landen"
    )
    assert raised.value.suggestions

    limited = json.dumps(
        {"ok": False, "code": "rate_limit", "error": "Technischer Servertext."}
    ).encode()
    with pytest.raises(ActivationServiceError) as rate:
        activate("{}", sender=lambda _payload: limited)
    assert "morgen" in str(rate.value.detail)
    assert {action.id for action in rate.value.suggestions} == {"report_error", "cancel"}


def test_the_online_client_accepts_only_a_confirmed_deactivation() -> None:
    deactivate("{}", sender=lambda _payload: b'{"ok":true}')

    refused = json.dumps(
        {"ok": False, "code": "not_found", "error": "Gerät nicht gefunden."}
    ).encode()
    with pytest.raises(ActivationServiceError) as raised:
        deactivate("{}", sender=lambda _payload: refused)
    assert raised.value.values["code"] == "not_found"
    assert raised.value.suggestions


@pytest.mark.parametrize(
    "answer",
    [
        b'{"ok":true,"value":NaN}',
        (b"[" * 65) + b"0" + (b"]" * 65),
    ],
)
def test_the_online_client_refuses_unsafe_json(answer: bytes) -> None:
    with pytest.raises(ActivationServiceError):
        activate("{}", sender=lambda _payload: answer)


def test_the_online_client_rejects_an_unbounded_server_answer() -> None:
    class _LargeAnswer:
        def read(self, _amount: int) -> bytes:
            return b"x" * (licence_service.MAX_RESPONSE_BYTES + 1)

    with pytest.raises(ActivationServiceError):
        licence_service._response_body(_LargeAnswer())


def test_the_deactivation_request_parses_back_to_the_device_that_signed_it(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    """``parse_deactivation`` ist der Spiegel der PHP-Regeln — und lief nie.

    Der Kern erzeugt die Abmeldung, der Dienst prüft sie in PHP; die
    Python-Fassung des Prüfers steht daneben, damit beide dieselben Regeln
    tragen. Bis hierher rief sie niemand, auch kein Test: Eine Regel, die nur
    in PHP geprüft wird, kann in Python stillschweigend abweichen. Der
    Rundweg hält die beiden Hälften an einem Ort zusammen.
    """
    _keyring, licence_text = activation_place
    activation.remember(licence_text)
    request = certificate.parse_request(
        certificate.create_request(licence_text, "Werkstatt-PC"),
        licence_public_key=ed25519.public_key(LICENCE_SEED),
    )
    activation.install_certificate(_issue(request))

    parsed = certificate.parse_deactivation(
        activation.prepare_deactivation(),
        licence_public_key=ed25519.public_key(LICENCE_SEED),
    )

    assert parsed.activation_id == "0123456789abcdef0123456789abcdef"
    assert parsed.licence.order == "A-1234"
    assert parsed.device_public == request.device_public
    assert parsed.licence_digest == certificate.licence_digest(parsed.licence)


def test_changing_a_signed_deactivation_is_rejected(
    activation_place: tuple[_MemoryKeyring, str],
) -> None:
    """Ein verändertes Byte in der Abmeldung passt nicht mehr zur Gerätesignatur."""
    _keyring, licence_text = activation_place
    activation.remember(licence_text)
    request = certificate.parse_request(
        certificate.create_request(licence_text, "Werkstatt-PC"),
        licence_public_key=ed25519.public_key(LICENCE_SEED),
    )
    activation.install_certificate(_issue(request))
    text = activation.prepare_deactivation()

    document = json.loads(text)
    payload = bytearray(certificate.decode_text(document["payload"]))
    payload[-2] ^= 1
    document["payload"] = certificate.encode_text(bytes(payload))

    with pytest.raises(certificate.ActivationDocumentError):
        certificate.parse_deactivation(
            json.dumps(document), licence_public_key=ed25519.public_key(LICENCE_SEED)
        )
