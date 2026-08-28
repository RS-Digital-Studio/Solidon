"""PHP-Dienst und Python-Anwendung sprechen wirklich dasselbe Protokoll."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
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

    assert setup_activation_server(["--database", str(database)]) == 0

    with contextlib.closing(sqlite3.connect(database)) as connection:
        objects = {
            name
            for (name,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
            )
        }
    assert {"licences", "activations", "activation_attempts", "one_active_device"} <= objects


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
    executable = shutil.which("php")
    if executable is None:
        pytest.skip("PHP fehlt; der Server-Integrationstest braucht PHP 7.4+")
    command = [executable]
    modules = subprocess.run(
        [executable, "-m"], capture_output=True, text=True, check=False
    ).stdout.lower()
    if "sodium" not in modules or "pdo_sqlite" not in modules:
        extension = Path(executable).parent / "ext"
        sodium = extension / ("php_sodium.dll" if os.name == "nt" else "sodium.so")
        sqlite = extension / ("php_pdo_sqlite.dll" if os.name == "nt" else "pdo_sqlite.so")
        if not sodium.is_file() or not sqlite.is_file():
            pytest.skip("PHP ist ohne sodium oder PDO_SQLITE installiert")
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
        return problem.code, problem.read().decode("utf-8")


def _get(url: str) -> tuple[int, str]:
    try:
        with urlopen(url, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as problem:
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

        again_status, again_answer = _post(url, request_text)
        assert again_status == 200, again_answer
        again = certificate.parse_certificate(
            again_answer,
            licence,
            device.ensure_public_key(),
            activation_public_key=activation_public,
        )
        assert again.activation_id == first.activation_id, "Wiederholen belegt keinen zweiten Platz"

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
