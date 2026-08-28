"""Das private Support-Werkzeug hält Kundendaten lokal und spricht nur per Digest."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.activation import certificate, ed25519, key
from tools import licence_admin
from tools.licence_archive import ArchiveBusyError, archive_lock
from tools.make_licence_keys import make_key

LICENCE_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")


def _archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, str]:
    public = ed25519.public_key(LICENCE_SEED)
    monkeypatch.setattr(key, "PUBLIC_KEY", public)
    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="POOL-7000",
        holder="kundin@beispiel.de",
    )
    licence_text = make_key(LICENCE_SEED, licence)
    digest = certificate.licence_digest(licence)
    archive = tmp_path / "licences.jsonl"
    archive.write_text(
        json.dumps(
            {
                "format": 1,
                "digest": digest,
                "key": licence_text,
                "major": licence.major,
                "purchased_on": licence.purchased_on.isoformat(),
                "order": licence.order,
                "holder": licence.holder,
                "archived_at": "2026-08-28T12:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return archive, licence_text, digest


def test_archive_finds_the_same_licence_by_every_support_clue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, licence_text, digest = _archive(tmp_path, monkeypatch)

    records = licence_admin.load_archive(archive)

    assert licence_admin.find_licences("POOL-7000", records)[0].digest == digest
    assert licence_admin.find_licences("kundin@beispiel.de", records)[0].digest == digest
    assert licence_admin.find_licences(digest, records)[0].order == "POOL-7000"
    assert licence_admin.find_licences(licence_text, records)[0].holder == "kundin@beispiel.de"


def test_archive_rejects_a_changed_buyer_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, _licence_text, _digest = _archive(tmp_path, monkeypatch)
    record = json.loads(archive.read_text(encoding="utf-8"))
    record["order"] = "POOL-9999"
    archive.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(licence_admin.OperatorError) as raised:
        licence_admin.load_archive(archive)

    assert "Zeile 1" in str(raised.value)
    assert "Sicherung" in str(raised.value)


def test_unknown_digest_can_be_inspected_without_disclosing_an_archive() -> None:
    digest = "ab" * 32

    found = licence_admin.find_licences(digest, [])

    assert found == [licence_admin.SupportLicence(digest, "", None, None, "", "")]


def test_a_pool_key_can_be_linked_to_the_mor_transaction_locally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, _licence_text, digest = _archive(tmp_path, monkeypatch)

    licence_admin.assign_transaction(archive, digest, " txn-4711 ")

    records = licence_admin.load_archive(archive)
    assert records[0].transaction == "txn-4711"
    assert licence_admin.find_licences("txn-4711", records)[0].digest == digest


def test_the_same_transaction_never_identifies_two_licences(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, _licence_text, first_digest = _archive(tmp_path, monkeypatch)
    first = json.loads(archive.read_text(encoding="utf-8"))
    second_licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="POOL-7001",
        holder="",
    )
    second_text = make_key(LICENCE_SEED, second_licence)
    second_digest = certificate.licence_digest(second_licence)
    second = {
        "format": 1,
        "digest": second_digest,
        "key": second_text,
        "major": second_licence.major,
        "purchased_on": second_licence.purchased_on.isoformat(),
        "order": second_licence.order,
        "holder": second_licence.holder,
        "transaction": "",
        "archived_at": "2026-08-28T12:00:00+00:00",
    }
    archive.write_text(
        json.dumps(first) + "\n" + json.dumps(second) + "\n",
        encoding="utf-8",
    )
    licence_admin.assign_transaction(archive, first_digest, "txn-eindeutig")

    with pytest.raises(licence_admin.OperatorError) as raised:
        licence_admin.assign_transaction(archive, second_digest, "TXN-EINDEUTIG")

    assert "anderen Lizenz" in str(raised.value)


def test_archive_lock_refuses_a_second_writer(tmp_path: Path) -> None:
    archive = tmp_path / "licences.jsonl"

    with (
        archive_lock(archive),
        pytest.raises(ArchiveBusyError),
        archive_lock(archive, timeout=0.0),
    ):
        pytest.fail("die zweite Schreibstelle darf die Sperre nie betreten")


def test_a_key_from_an_older_major_is_found_in_the_loaded_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    public = ed25519.public_key(LICENCE_SEED)
    monkeypatch.setattr(key, "PUBLIC_KEY", public)
    old_major = max(0, key.current_major() - 1)
    licence = key.Licence(
        major=old_major,
        purchased_on=date(2026, 11, 1),
        order="ALT-7000",
        holder="alt@beispiel.de",
    )
    licence_text = make_key(LICENCE_SEED, licence)
    digest = certificate.licence_digest(licence)
    archive = tmp_path / "licences.jsonl"
    archive.write_text(
        json.dumps(
            {
                "format": 1,
                "digest": digest,
                "key": licence_text,
                "major": old_major,
                "purchased_on": licence.purchased_on.isoformat(),
                "order": licence.order,
                "holder": licence.holder,
                "transaction": "",
                "archived_at": "2026-08-28T12:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    records = licence_admin.load_archive(archive)

    assert licence_admin.find_licences(licence_text, records)[0].digest == digest


def test_operator_client_sends_only_digest_reason_and_two_token_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class Answer:
        status = 200

        def __enter__(self) -> Answer:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        @staticmethod
        def read() -> bytes:
            return b'{"ok":true,"licence":{"status":"blocked"}}'

    def open_request(request: object, timeout: int) -> Answer:
        seen["request"] = request
        seen["timeout"] = timeout
        return Answer()

    monkeypatch.setattr(licence_admin, "urlopen", open_request)
    token = "cd" * 32
    digest = "ab" * 32

    result = licence_admin.OperatorClient("https://solidon3d.de/api/operator.php", token).call(
        "block", digest, "refund"
    )

    request = seen["request"]
    assert json.loads(request.data) == {  # type: ignore[attr-defined]
        "action": "block",
        "digest": digest,
        "reason": "refund",
    }
    assert request.get_header("Authorization") == f"Bearer {token}"  # type: ignore[attr-defined]
    assert request.get_header("X-solidon-operator-token") == token  # type: ignore[attr-defined]
    assert seen["timeout"] == 10
    assert result["licence"]["status"] == "blocked"


def test_operator_client_never_sends_a_token_over_plain_remote_http() -> None:
    with pytest.raises(licence_admin.OperatorError) as raised:
        licence_admin.OperatorClient("http://solidon3d.de/api/operator.php", "cd" * 32)

    assert "HTTPS" in str(raised.value)


def test_a_late_server_answer_never_overwrites_the_new_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Antwort A bleibt bei A, wenn während des Ladens bereits B gewählt wurde."""
    first = licence_admin.SupportLicence("aa" * 32, "", None, None, "A", "")
    second = licence_admin.SupportLicence("bb" * 32, "", None, None, "B", "")
    messages: list[str] = []
    shown: list[object] = []
    retried: list[str] = []
    window = object.__new__(licence_admin.SupportWindow)
    window.busy = False
    window.current = first
    window.message = SimpleNamespace(set=lambda value: messages.append(str(value)))
    window.action_buttons = []
    window.tk = SimpleNamespace(TclError=RuntimeError)
    window.root = SimpleNamespace(after=lambda _delay, callback: callback())
    window.lookup = lambda: retried.append(window.current.digest)

    class ImmediateThread:
        def __init__(self, *, target: object, **_kwargs: object) -> None:
            self.target = target

        def start(self) -> None:
            self.target()  # type: ignore[operator]

    monkeypatch.setattr(licence_admin.threading, "Thread", ImmediateThread)

    def delayed_answer() -> dict[str, object]:
        window.current = second
        return {"ok": True, "licence": {"status": "active"}}

    licence_admin.SupportWindow._run(window, delayed_answer, shown.append, first.digest)

    assert not shown, "die Antwort der alten Auswahl wird nicht dargestellt"
    assert retried == [second.digest], "die neue Auswahl wird unmittelbar nachgeladen"
    assert any("Auswahl geändert" in entry for entry in messages)


def test_a_server_error_keeps_refresh_available_but_changes_locked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nach einem Netzfehler gibt es einen klaren Wiederholweg ohne Blindänderung."""
    licence = licence_admin.SupportLicence("aa" * 32, "", None, None, "A", "")

    class Control:
        def __init__(self) -> None:
            self.values: list[dict[str, object]] = []

        def configure(self, **values: object) -> None:
            self.values.append(values)

    action = Control()
    refresh = Control()
    badge = Control()
    messages: list[str] = []
    window = object.__new__(licence_admin.SupportWindow)
    window.busy = False
    window.current = licence
    window.server_loaded_digest = licence.digest
    window.action_buttons = [action]
    window.lookup_button = refresh
    window.status_badge = badge
    window.message = SimpleNamespace(set=lambda value: messages.append(str(value)))
    window.tk = SimpleNamespace(TclError=RuntimeError)
    window.root = SimpleNamespace(after=lambda _delay, callback: callback())

    class ImmediateThread:
        def __init__(self, *, target: object, **_kwargs: object) -> None:
            self.target = target

        def start(self) -> None:
            self.target()  # type: ignore[operator]

    monkeypatch.setattr(licence_admin.threading, "Thread", ImmediateThread)

    def unavailable() -> dict[str, object]:
        raise licence_admin.OperatorError("Server nicht erreichbar. Verbindung prüfen.")

    licence_admin.SupportWindow._run(window, unavailable, lambda _answer: None, licence.digest)

    assert action.values[-1]["state"] == "disabled"
    assert refresh.values[-1]["state"] == "normal"
    assert "nicht verfügbar" in str(badge.values[-1]["text"])
    assert "Verbindung prüfen" in messages[-1]
