"""PHP-Dienst und Python-Anwendung sprechen wirklich dasselbe Protokoll."""

from __future__ import annotations

import contextlib
import json
import os
import socket
import sqlite3
import subprocess
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

from app.core.activation import certificate, device, ed25519, key
from tests.php_probe import missing_php, php_executable
from tools.make_licence_keys import make_key
from tools.setup_activation_server import main as setup_activation_server

LICENCE_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
ACTIVATION_SEED = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")


def test_setup_refuses_every_target_inside_the_repository() -> None:
    """Auch ein Ziel unter website wird vor dem Schreiben gestoppt."""
    target = Path(__file__).parent.parent / "website" / "niemals-activation.seed"

    with pytest.raises(SystemExit):
        setup_activation_server(["--private", str(target)])

    assert not target.exists()


def test_setup_prepares_the_complete_database(tmp_path: Path) -> None:
    database = tmp_path / "server" / "activation.sqlite"
    operator_token = tmp_path / "server" / "operator.token"

    assert (
        setup_activation_server(
            ["--database", str(database), "--operator-token", str(operator_token)]
        )
        == 0
    )

    with contextlib.closing(sqlite3.connect(database)) as connection:
        objects = {
            name
            for (name,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
            )
        }
    assert {
        "licences",
        "activations",
        "activation_attempts",
        "operator_events",
        "one_active_device",
    } <= objects
    assert len(bytes.fromhex(operator_token.read_text(encoding="ascii").strip())) == 32


class _MemoryKeyring:
    def __init__(self) -> None:
        self.value: str | None = None

    def get_password(self, _service: str, _account: str) -> str | None:
        return self.value

    def set_password(self, _service: str, _account: str, value: str) -> None:
        self.value = value

    def delete_password(self, _service: str, _account: str) -> None:
        self.value = None


def _php_command(port: int) -> list[str]:
    executable = php_executable("PHP fehlt; der Server-Integrationstest braucht PHP 7.4+")
    command = [executable]
    modules = subprocess.run(
        [executable, "-m"], capture_output=True, text=True, check=False
    ).stdout.lower()
    if "sodium" not in modules or "pdo_sqlite" not in modules:
        extension = Path(executable).parent / "ext"
        sodium = extension / ("php_sodium.dll" if os.name == "nt" else "sodium.so")
        sqlite = extension / ("php_pdo_sqlite.dll" if os.name == "nt" else "pdo_sqlite.so")
        if not sodium.is_file() or not sqlite.is_file():
            missing_php("PHP ist ohne sodium oder PDO_SQLITE installiert")
        command += [
            "-d",
            f"extension_dir={extension}",
            "-d",
            f"extension={sodium.name}",
            "-d",
            f"extension={sqlite.name}",
        ]
    return [*command, "-S", f"127.0.0.1:{port}", "-t", "website"]


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _post(url: str, text: str) -> tuple[int, str]:
    request = Request(
        url,
        data=text.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as problem:
        with problem:
            return problem.code, problem.read().decode("utf-8")


def _operator_post(url: str, token: str, payload: dict[str, str]) -> tuple[int, str]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as problem:
        with problem:
            return problem.code, problem.read().decode("utf-8")


def _get(url: str) -> tuple[int, str]:
    try:
        with urlopen(url, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as problem:
        with problem:
            return problem.code, problem.read().decode("utf-8")


def test_php_issues_one_idempotent_device_certificate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    licence_public = ed25519.public_key(LICENCE_SEED)
    activation_public = ed25519.public_key(ACTIVATION_SEED)
    monkeypatch.setattr(key, "PUBLIC_KEY", licence_public)
    monkeypatch.setattr(certificate, "ACTIVATION_PUBLIC_KEY", activation_public)
    first_keyring = _MemoryKeyring()
    monkeypatch.setattr(device, "_load_keyring", lambda: first_keyring)
    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="A-1234",
        holder="kundin@beispiel.de",
    )
    licence_text = make_key(LICENCE_SEED, licence)
    request_text = certificate.create_request(licence_text, "Ä" * 80)

    seed_file = tmp_path / "activation.seed"
    seed_file.write_text(ACTIVATION_SEED.hex(), encoding="ascii")
    seed_file.chmod(0o600)
    database = tmp_path / "activation.sqlite"
    port = _free_port()
    environment = os.environ.copy()
    environment.update(
        {
            "SOLIDON_ACTIVATION_SEED_FILE": str(seed_file),
            "SOLIDON_ACTIVATION_DB": str(database),
            "SOLIDON_ACTIVATION_TEST_PUBLIC_KEY": activation_public.hex(),
            "SOLIDON_ACTIVATION_TEST_LICENCE_PUBLIC_KEY": licence_public.hex(),
            "SOLIDON_ACTIVATION_MAJOR": str(key.current_major()),
        }
    )
    process = subprocess.Popen(
        _php_command(port),
        cwd=Path(__file__).parent.parent,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/api/activation.php"
    try:
        for _attempt in range(50):
            try:
                status, answer = _post(url, request_text)
                break
            except URLError:
                time.sleep(0.05)
        else:
            pytest.fail("der lokale PHP-Aktivierungsdienst ist nicht gestartet")

        health_status, health_answer = _get(f"http://127.0.0.1:{port}/api/activation-health.php")
        assert health_status == 200, health_answer
        assert json.loads(health_answer) == {"ok": True, "protocol": 1}

        malformed = json.loads(request_text)
        malformed["signature"] = ""
        malformed_status, malformed_answer = _post(url, json.dumps(malformed))
        assert malformed_status == 400, malformed_answer
        assert json.loads(malformed_answer)["code"] == "invalid_request"

        assert status == 200, answer
        first = certificate.parse_certificate(
            answer, licence, device.ensure_public_key(), activation_public_key=activation_public
        )
        assert first.device_name == "Ä" * 80, "80 Unicode-Zeichen sind nicht 160 Bytes"

        with contextlib.closing(sqlite3.connect(database)) as stored:
            stored.execute(
                "INSERT INTO activation_attempts(licence_digest, day, attempts) "
                "VALUES('veraltet', '2000-01-01', 3)"
            )
            stored.commit()

        again_status, again_answer = _post(url, request_text)
        assert again_status == 200, again_answer
        again = certificate.parse_certificate(
            again_answer,
            licence,
            device.ensure_public_key(),
            activation_public_key=activation_public,
        )
        assert again.activation_id == first.activation_id, "Wiederholen belegt keinen zweiten Platz"
        with contextlib.closing(sqlite3.connect(database)) as stored:
            assert stored.execute(
                "SELECT COUNT(*) FROM activation_attempts WHERE day < date('now')"
            ).fetchone() == (0,), "ein Tageslimit ist kein unbegrenztes Nutzungsprotokoll"

        second_keyring = _MemoryKeyring()
        monkeypatch.setattr(device, "_load_keyring", lambda: second_keyring)
        other_request = certificate.create_request(licence_text, "Laptop")
        refused_status, refused_answer = _post(url, other_request)
        assert refused_status == 409
        assert json.loads(refused_answer)["code"] == "device_limit"

        forged_payload = json.dumps(
            {
                "activation_id": first.activation_id,
                "device_public": certificate.encode_text(device.ensure_public_key()),
                "format": certificate.DOCUMENT_FORMAT,
                "kind": certificate.DEACTIVATION_KIND,
                "licence_digest": certificate.licence_digest(licence),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        _public, forged_signature = device.sign(forged_payload)
        forged_document = json.loads(
            certificate.signed_document(
                certificate.DEACTIVATION_KIND,
                forged_payload,
                forged_signature,
            )
        )
        forged_document["licence"] = licence_text
        forged_status, forged_answer = _post(
            f"http://127.0.0.1:{port}/api/deactivation.php",
            json.dumps(forged_document),
        )
        assert forged_status == 404
        assert json.loads(forged_answer)["code"] == "activation_not_found"
        still_refused, _still_answer = _post(url, other_request)
        assert still_refused == 409, "ein fremdes Gerät darf den belegten Platz nicht freigeben"

        monkeypatch.setattr(device, "_load_keyring", lambda: first_keyring)
        deactivation = certificate.create_deactivation(licence_text, first)
        deactivation_status, deactivation_answer = _post(
            f"http://127.0.0.1:{port}/api/deactivation.php", deactivation
        )
        assert deactivation_status == 200, deactivation_answer
        assert json.loads(deactivation_answer) == {"ok": True}
        repeated_status, repeated_answer = _post(
            f"http://127.0.0.1:{port}/api/deactivation.php", deactivation
        )
        assert repeated_status == 200, "eine verlorene Antwort lässt sich sicher wiederholen"
        assert json.loads(repeated_answer) == {"ok": True}

        monkeypatch.setattr(device, "_load_keyring", lambda: second_keyring)
        second_status, second_answer = _post(url, other_request)
        assert second_status == 200, second_answer
        second = certificate.parse_certificate(
            second_answer,
            licence,
            device.ensure_public_key(),
            activation_public_key=activation_public,
        )
        assert second.activation_id != first.activation_id

        limited_status, limited_answer = _post(url, other_request)
        assert limited_status == 429, limited_answer
        assert json.loads(limited_answer)["code"] == "rate_limit"
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_health_check_never_creates_a_missing_database(tmp_path: Path) -> None:
    """Die öffentliche Bereitschaftsprobe verändert keinen Serverzustand."""
    seed_file = tmp_path / "activation.seed"
    seed_file.write_text(ACTIVATION_SEED.hex(), encoding="ascii")
    seed_file.chmod(0o600)
    database = tmp_path / "missing.sqlite"
    port = _free_port()
    environment = os.environ.copy()
    environment.update(
        {
            "SOLIDON_ACTIVATION_SEED_FILE": str(seed_file),
            "SOLIDON_ACTIVATION_DB": str(database),
            "SOLIDON_ACTIVATION_TEST_PUBLIC_KEY": ed25519.public_key(ACTIVATION_SEED).hex(),
        }
    )
    process = subprocess.Popen(
        _php_command(port),
        cwd=Path(__file__).parent.parent,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        url = f"http://127.0.0.1:{port}/api/activation-health.php"
        for _attempt in range(50):
            try:
                status, answer = _get(url)
                break
            except URLError:
                time.sleep(0.05)
        else:
            pytest.fail("der lokale PHP-Aktivierungsdienst ist nicht gestartet")

        assert status == 503, answer
        assert json.loads(answer)["code"] == "service_unavailable"
        assert not database.exists()
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_private_operator_path_manages_one_licence_and_records_every_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Support sieht und ändert nur nach einem 256-Bit-Nachweis."""
    licence_public = ed25519.public_key(LICENCE_SEED)
    activation_public = ed25519.public_key(ACTIVATION_SEED)
    monkeypatch.setattr(key, "PUBLIC_KEY", licence_public)
    monkeypatch.setattr(certificate, "ACTIVATION_PUBLIC_KEY", activation_public)
    first_keyring = _MemoryKeyring()
    monkeypatch.setattr(device, "_load_keyring", lambda: first_keyring)
    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="A-4711",
        holder="supportfall@beispiel.de",
    )
    licence_text = make_key(LICENCE_SEED, licence)
    digest = certificate.licence_digest(licence)
    activation_request = certificate.create_request(licence_text, "Werkstatt")

    seed_file = tmp_path / "activation.seed"
    seed_file.write_text(ACTIVATION_SEED.hex(), encoding="ascii")
    seed_file.chmod(0o600)
    database = tmp_path / "activation.sqlite"
    token_file = tmp_path / "operator.token"
    token = "ab" * 32
    token_file.write_text(token + "\n", encoding="ascii")
    token_file.chmod(0o600)
    port = _free_port()
    environment = os.environ.copy()
    environment.update(
        {
            "SOLIDON_ACTIVATION_SEED_FILE": str(seed_file),
            "SOLIDON_ACTIVATION_DB": str(database),
            "SOLIDON_ACTIVATION_OPERATOR_TOKEN_FILE": str(token_file),
            "SOLIDON_ACTIVATION_TEST_PUBLIC_KEY": activation_public.hex(),
            "SOLIDON_ACTIVATION_TEST_LICENCE_PUBLIC_KEY": licence_public.hex(),
            "SOLIDON_ACTIVATION_MAJOR": str(key.current_major()),
        }
    )
    process = subprocess.Popen(
        _php_command(port),
        cwd=Path(__file__).parent.parent,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    activation_url = f"http://127.0.0.1:{port}/api/activation.php"
    operator_url = f"http://127.0.0.1:{port}/api/operator.php"
    try:
        for _attempt in range(50):
            try:
                activation_status, activation_answer = _post(activation_url, activation_request)
                break
            except URLError:
                time.sleep(0.05)
        else:
            pytest.fail("der lokale PHP-Aktivierungsdienst ist nicht gestartet")
        assert activation_status == 200, activation_answer

        refused, refused_answer = _operator_post(
            operator_url,
            "00" * 32,
            {"action": "lookup", "digest": digest},
        )
        assert refused == 403
        assert json.loads(refused_answer)["code"] == "operator_forbidden"

        looked_up, lookup_answer = _operator_post(
            operator_url, token, {"action": "lookup", "digest": digest}
        )
        assert looked_up == 200, lookup_answer
        first_state = json.loads(lookup_answer)
        assert first_state["licence"]["status"] == "active"
        assert first_state["activations"][0]["device_name"] == "Werkstatt"
        assert first_state["activations"][0]["active"] is True
        assert first_state["attempts"][0]["attempts"] == 1

        bad_reason, _bad_answer = _operator_post(
            operator_url,
            token,
            {"action": "block", "digest": digest, "reason": "freier Text"},
        )
        assert bad_reason == 400

        blocked, blocked_answer = _operator_post(
            operator_url,
            token,
            {"action": "block", "digest": digest, "reason": "refund"},
        )
        assert blocked == 200, blocked_answer
        assert json.loads(blocked_answer)["licence"]["status"] == "blocked"
        blocked_activation, blocked_activation_answer = _post(activation_url, activation_request)
        assert blocked_activation == 403, blocked_activation_answer
        assert json.loads(blocked_activation_answer)["code"] == "licence_blocked"

        for action in ("unblock", "release", "reset_attempts"):
            status, answer = _operator_post(
                operator_url,
                token,
                {"action": action, "digest": digest, "reason": "correction"},
            )
            assert status == 200, answer

        final_status, final_answer = _operator_post(
            operator_url, token, {"action": "lookup", "digest": digest}
        )
        assert final_status == 200, final_answer
        final_state = json.loads(final_answer)
        assert final_state["licence"]["status"] == "active"
        assert final_state["activations"][0]["active"] is False
        assert final_state["attempts"] == []
        assert [entry["action"] for entry in final_state["events"]] == [
            "reset_attempts",
            "release",
            "unblock",
            "block",
        ]
        assert all("supportfall" not in json.dumps(entry) for entry in final_state["events"])
    finally:
        process.terminate()
        process.wait(timeout=5)
