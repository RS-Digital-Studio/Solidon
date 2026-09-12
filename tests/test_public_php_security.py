"""Missbrauchsgrenzen der öffentlichen PHP-Endpunkte."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

import pytest

from tests.php_probe import php_executable, php_extension

ROOT = Path(__file__).parent.parent
API = ROOT / "website" / "api"
CLEANUP = API / "cleanup_private_state.php"
ENDPOINTS = (
    "support.php",
    "activation.php",
    "deactivation.php",
    "activation-health.php",
    "activation_common.php",
    "day_zone.php",
    "operator.php",
    "count.php",
    "stats.php",
)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _php_command(
    php: str,
    port: int,
    *,
    prepend: Path | None = None,
    error_log: Path | None = None,
    ini: dict[str, str] | None = None,
    docroot: Path | None = None,
) -> list[str]:
    """Die Befehlszeile des Prüfservers.

    **Post verlässt ihn nie.** ``support.php`` ruft ``mail()``, und ein Rechner
    mit eingerichtetem Sendmail oder SMTP hätte jede gültige Testrückmeldung
    an die echte Supportadresse geschickt (Gesamtreview 05.09.2026, R34). Der
    Transport zeigt deshalb auf ein Programm, das es nicht gibt, und auf einen
    Port, an dem niemand lauscht; der Endpunkt antwortet dann 502, und die
    Tests rechnen damit.
    """
    command = [
        php,
        "-d",
        "sendmail_path=/nonexistent/solidon-keine-post",
        "-d",
        "SMTP=127.0.0.1",
        "-d",
        "smtp_port=1",
    ]
    if prepend is not None:
        command.extend(["-d", f"auto_prepend_file={prepend}"])
    if error_log is not None:
        # Ohne eigene Datei schreibt PHP nach stderr, und das geht hier nach
        # DEVNULL — ein Test, der eine Meldung erwartet, sähe nie eine.
        command.extend(["-d", "log_errors=1", "-d", f"error_log={error_log}"])
    for key, value in (ini or {}).items():
        command.extend(["-d", f"{key}={value}"])
    command.extend(["-S", f"127.0.0.1:{port}", "-t", str(docroot or "website")])
    return command


def _temporary_docroot(tmp_path: Path) -> Path:
    """Ein eigener Dokumentenstamm für Tests, die Dateien daneben anlegen.

    Bis zum 05.09.2026 schrieben drei Tests Pakete nach ``website/dl`` und
    einer räumte ``website/api/.stats`` bedingungslos weg — auch, wenn dort
    ein Bestand lag, den der Test nie angelegt hatte (Gesamtreview, R33). Die
    Endpunkte finden ``../dl`` und den Dokumentenstamm relativ zu sich, also
    reicht eine Kopie von ``api/``.
    """
    docroot = tmp_path / "website"
    shutil.copytree(API, docroot / "api")
    (docroot / "dl").mkdir()
    return docroot


@contextlib.contextmanager
def _php_server(
    tmp_path: Path,
    extra_environment: dict[str, str] | None = None,
    *,
    prepend: Path | None = None,
    error_log: Path | None = None,
    ini: dict[str, str] | None = None,
    docroot: Path | None = None,
) -> Iterator[str]:
    php = php_executable("PHP fehlt; der Endpunkttest braucht PHP 7.4+")
    port = _free_port()
    environment = os.environ.copy()
    environment["SOLIDON_STATS_DIR"] = str(tmp_path / "stats")
    environment["SOLIDON_ACTIVATION_RATE_FILE"] = str(tmp_path / "activation-rate.json")
    environment["SOLIDON_SUPPORT_RATE_FILE"] = str(tmp_path / "support-rate.json")
    if extra_environment:
        environment.update(extra_environment)
    command = _php_command(
        php, port, prepend=prepend, error_log=error_log, ini=ini, docroot=docroot
    )
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}/api"
    try:
        for _attempt in range(50):
            try:
                _request(f"{base}/activation_common.php")
                break
            except URLError:
                time.sleep(0.05)
        else:
            pytest.fail("der lokale PHP-Prüfserver ist nicht gestartet")
        yield base
    finally:
        process.terminate()
        process.wait(timeout=5)


def _request(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Message, str]:
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, response.headers, response.read().decode("utf-8")
    except HTTPError as problem:
        with problem:
            return problem.code, problem.headers, problem.read().decode("utf-8")


def _chmod_private(path: Path) -> None:
    if os.name != "nt":
        path.chmod(0o600 if path.is_file() else 0o700)


def _prepare_cleanup_state(tmp_path: Path, ages: dict[str, int] | None = None) -> dict[str, Path]:
    now = int(time.time())
    stats = tmp_path / "stats"
    stats.mkdir(mode=0o700)
    _chmod_private(tmp_path)
    _chmod_private(stats)
    paths = {
        "count": stats / "rate.json",
        "activation": tmp_path / "activation-rate.json",
        "login": stats / "anmeldeversuche.json",
        "support": tmp_path / "support-rate.json",
        "salt": stats / "salt.json",
    }
    contents = {
        "count": {"global": [now - 1]},
        "activation": {"issue:global": [now - 1]},
        "login": {"global": [now - 1]},
        "support": {"global": [now - 1]},
        "salt": {"day": datetime.now(UTC).strftime("%Y-%m-%d"), "salt": "ab" * 16},
    }
    for name, path in paths.items():
        path.write_text(json.dumps(contents[name]), encoding="ascii")
        _chmod_private(path)
        age = (ages or {}).get(name, 5)
        os.utime(path, (now - age, now - age))
    return paths


def _utc_month(offset: int) -> str:
    now = datetime.now(UTC)
    index = now.year * 12 + now.month - 1 + offset
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _write_month(path: Path, month: str, *, timestamp_month: str | None = None) -> bytes:
    row = {
        "t": f"{timestamp_month or month}-15T12:00:00+00:00",
        "k": "p",
        "v": "/datenschutz",
        "r": "example.org",
        "u": "a1b2c3d4",
    }
    data = (json.dumps(row, separators=(",", ":")) + "\n").encode()
    path.write_bytes(data)
    _chmod_private(path)
    return data


def _run_cleanup(tmp_path: Path, paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    php = php_executable()
    return subprocess.run(
        [
            php,
            str(CLEANUP),
            "--stats-dir",
            str(tmp_path / "stats"),
            "--activation-rate",
            str(paths["activation"]),
            "--support-rate",
            str(paths["support"]),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _php_function(source: str, name: str) -> str:
    start = source.index(f"function {name}")
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Funktion nicht abgeschlossen: {name}")


def _fault_stream_php() -> str:
    return (
        "class FaultStream { public $context; public static $data = 'alt'; "
        "public static $position = 0; public static $mode = 'write'; "
        "public static $stage = 0; "
        "function stream_open($path, $mode, $options, &$openedPath) { "
        "self::$position = 0; return true; } "
        "function stream_set_option($option, $arg1, $arg2) { return true; } "
        "function stream_seek($offset, $whence) { "
        "$base = $whence === SEEK_SET ? 0 : "
        "($whence === SEEK_CUR ? self::$position : strlen(self::$data)); "
        "$next = $base + $offset; if ($next < 0) { return false; } "
        "self::$position = $next; return true; } "
        "function stream_tell() { return self::$position; } "
        "function stream_read($length) { $part = substr(self::$data, self::$position, $length); "
        "self::$position += strlen($part); return $part; } "
        "function stream_eof() { return self::$position >= strlen(self::$data); } "
        "function stream_truncate($size) { "
        "if (self::$mode === 'dead' && self::$stage >= 2) { return false; } "
        "self::$data = substr(self::$data, 0, $size); "
        "if (self::$position > $size) { self::$position = $size; } return true; } "
        "private function put($data) { $end = self::$position + strlen($data); "
        "self::$data = substr(self::$data, 0, self::$position) . $data . "
        "substr(self::$data, $end); "
        "self::$position = $end; return strlen($data); } "
        "function stream_write($data) { "
        "if ((self::$mode === 'write' || self::$mode === 'dead') && self::$stage === 0) { "
        "$this->put(substr($data, 0, 1)); self::$stage = 2; return 0; } "
        "if (self::$mode === 'dead') { return 0; } return $this->put($data); } "
        "function stream_flush() { if (self::$mode === 'flush' && self::$stage === 0) { "
        "self::$stage = 1; return false; } return true; } "
        "function stream_stat() { return ['size' => strlen(self::$data)]; } }\n"
        "stream_wrapper_register('faultstream', FaultStream::class);\n"
    )


@pytest.mark.parametrize("name", ENDPOINTS)
def test_every_public_endpoint_is_valid_php(name: str) -> None:
    php = php_executable()
    result = subprocess.run(
        [php, "-l", str(API / name)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_private_writers_require_php_81_and_plesk_uses_the_php_task_contract() -> None:
    for name in [
        "support.php",
        "activation_common.php",
        "count.php",
        "stats.php",
        "cleanup_private_state.php",
    ]:
        source = (API / name).read_text(encoding="utf-8")
        assert "PHP_VERSION_ID < 80100" in source
        assert "function_exists('fsync')" not in source
    readme = (ROOT / "website" / "README.md").read_text(encoding="utf-8")
    for contract in [
        "Run a PHP script",
        "with arguments",
        "Domain-Systemnutzer",
        "mindestens 8.1",
        "Run Now",
        "Exitcode 0",
        "chroot-sichtbar",
        "unmittelbar vorherigen",
        "UTC-Kalendermonats",
        "höchstens 62 Kalendertage",
        "stille Langzeitaggregate werden nicht gebildet",
    ]:
        assert contract in readme


def test_private_cleanup_is_valid_php_and_cannot_run_over_http(tmp_path: Path) -> None:
    php = php_executable()
    lint = subprocess.run([php, "-l", str(CLEANUP)], capture_output=True, text=True, timeout=30)
    assert lint.returncode == 0, lint.stdout + lint.stderr

    with _php_server(tmp_path) as base:
        status, _headers, _body = _request(f"{base}/cleanup_private_state.php")

    assert status == 404


def test_private_cleanup_requires_all_absolute_cli_paths(tmp_path: Path) -> None:
    php = php_executable()

    result = subprocess.run(
        [php, str(CLEANUP), "--stats-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 64
    assert "fehlt" in result.stderr


def test_private_cleanup_honours_every_age_boundary(tmp_path: Path) -> None:
    paths = _prepare_cleanup_state(
        tmp_path,
        {"count": 70, "activation": 5, "login": 910, "support": 5, "salt": 86410},
    )
    activation_before = paths["activation"].read_bytes()
    support_before = paths["support"].read_bytes()
    rate_key = tmp_path / "activation-rate.json.key"
    rate_key.write_text("cd" * 32, encoding="ascii")
    _chmod_private(rate_key)
    os.utime(rate_key, (0, 0))

    first = _run_cleanup(tmp_path, paths)

    assert first.returncode == 0, first.stderr
    assert json.loads(paths["count"].read_text(encoding="ascii")) == {}
    assert json.loads(paths["login"].read_text(encoding="ascii")) == {}
    assert paths["activation"].read_bytes() == activation_before
    assert paths["support"].read_bytes() == support_before
    assert not paths["salt"].exists()

    old = int(time.time()) - 3700
    os.utime(paths["activation"], (old, old))
    os.utime(paths["support"], (old, old))
    second = _run_cleanup(tmp_path, paths)

    assert second.returncode == 0, second.stderr
    assert json.loads(paths["activation"].read_text(encoding="ascii")) == {}
    assert json.loads(paths["support"].read_text(encoding="ascii")) == {}
    assert rate_key.read_text(encoding="ascii") == "cd" * 32


def test_private_cleanup_removes_legacy_sha_keys_while_holding_the_state_lock(
    tmp_path: Path,
) -> None:
    paths = _prepare_cleanup_state(tmp_path)
    now = int(time.time())
    legacy = "ab" * 32
    states = {
        "count": {legacy: [now - 1], "global": [now - 1]},
        "activation": {f"issue:{legacy}": [now - 1], "issue:global": [now - 1]},
        "login": {f"ip:{legacy}": [now - 1], "global": [now - 1]},
        "support": {legacy: [now - 1], "global": [now - 1]},
    }
    for name, state in states.items():
        paths[name].write_text(json.dumps(state), encoding="ascii")
        _chmod_private(paths[name])

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 0, result.stderr
    for name in states:
        state = json.loads(paths[name].read_text(encoding="ascii"))
        assert list(state) in (["global"], ["issue:global"])
        assert legacy not in "\n".join(state)


@pytest.mark.parametrize("name", ["activation", "login"])
def test_private_cleanup_rejects_corrupt_rate_json_without_partial_cleanup(
    tmp_path: Path, name: str
) -> None:
    paths = _prepare_cleanup_state(tmp_path, {"count": 70})
    count_before = paths["count"].read_bytes()
    paths[name].write_text("null", encoding="ascii")
    _chmod_private(paths[name])

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 65
    assert paths["count"].read_bytes() == count_before
    assert paths[name].read_text(encoding="ascii") == "null"


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_private_cleanup_rejects_linked_state_without_partial_cleanup(
    tmp_path: Path, link_kind: str
) -> None:
    paths = _prepare_cleanup_state(tmp_path, {"count": 70})
    count_before = paths["count"].read_bytes()
    support = paths["support"]
    support.unlink()
    target = tmp_path / "linked-support-state.json"
    target.write_text(json.dumps({"global": [int(time.time()) - 1]}), encoding="ascii")
    _chmod_private(target)
    try:
        if link_kind == "symlink":
            support.symlink_to(target)
        else:
            os.link(target, support)
    except OSError:
        pytest.skip(f"dieser Prüfstand erlaubt keinen {link_kind}")

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 65
    assert paths["count"].read_bytes() == count_before
    assert json.loads(target.read_text(encoding="ascii"))["global"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX-Dateirechte gibt es unter Windows nicht")
def test_private_cleanup_rejects_group_readable_state(tmp_path: Path) -> None:
    paths = _prepare_cleanup_state(tmp_path)
    paths["support"].chmod(0o640)

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 65


def test_private_cleanup_fails_fast_at_a_parallel_writer(tmp_path: Path) -> None:
    php = php_executable()
    paths = _prepare_cleanup_state(tmp_path, {"count": 70})
    count_before = paths["count"].read_bytes()
    locker = subprocess.Popen(
        [
            php,
            "-r",
            '$f=fopen($argv[1], "r+b"); flock($f, LOCK_EX); '
            'fwrite(STDOUT, "gesperrt\\n"); fflush(STDOUT); sleep(30);',
            str(paths["support"]),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert locker.stdout is not None
        assert locker.stdout.readline().strip() == "gesperrt"
        result = _run_cleanup(tmp_path, paths)
    finally:
        locker.terminate()
        locker.wait(timeout=5)
        if locker.stdout is not None:
            locker.stdout.close()
        if locker.stderr is not None:
            locker.stderr.close()

    assert result.returncode == 75
    assert paths["count"].read_bytes() == count_before


def test_private_cleanup_keeps_only_current_and_previous_utc_month(tmp_path: Path) -> None:
    paths = _prepare_cleanup_state(tmp_path)
    current = tmp_path / "stats" / f"{_utc_month(0)}.jsonl"
    previous = tmp_path / "stats" / f"{_utc_month(-1)}.jsonl"
    old = tmp_path / "stats" / f"{_utc_month(-2)}.jsonl"
    current_data = _write_month(current, _utc_month(0))
    previous_data = _write_month(previous, _utc_month(-1))
    _write_month(old, _utc_month(-2))
    old_mtime = int(time.time()) - 400 * 86400
    os.utime(current, (old_mtime, old_mtime))
    os.utime(previous, (old_mtime, old_mtime))

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 0, result.stderr
    assert current.read_bytes() == current_data
    assert previous.read_bytes() == previous_data
    assert not old.exists()


@pytest.mark.parametrize("agent", ["Solidon/0.4.0", "Mozilla/5.0"])
@pytest.mark.parametrize("legacy_mark", [False, True])
def test_private_cleanup_accepts_update_rows_from_the_live_writer(
    tmp_path: Path, agent: str, legacy_mark: bool
) -> None:
    """Der echte Zähler darf die zeitgesteuerte Löschung nicht lahmlegen."""
    paths = _prepare_cleanup_state(tmp_path, {"activation": 1000, "support": 3700})
    old = tmp_path / "stats" / f"{_utc_month(-2)}.jsonl"
    _write_month(old, _utc_month(-2))
    with _php_server(tmp_path) as base:
        status, _headers, _body = _request(f"{base}/count.php?u=1", headers={"User-Agent": agent})
    assert status == 200
    current = tmp_path / "stats" / f"{_utc_month(0)}.jsonl"
    if legacy_mark:
        row = json.loads(current.read_bytes())
        row.update(u="a1b2c3d4", r="example.org")
        current.write_text(json.dumps(row) + "\n", encoding="ascii")
    before = current.read_bytes()
    assert json.loads(before)["k"] == "u"

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 0, result.stderr
    assert current.read_bytes() == before
    assert not old.exists()
    assert json.loads(paths["activation"].read_text(encoding="ascii")) == {}
    assert json.loads(paths["support"].read_text(encoding="ascii")) == {}


@pytest.mark.parametrize("version", ["0.4.0.1.2", "beliebig", "0.4.0\n", "1" * 17])
def test_private_cleanup_rejects_invalid_update_versions_without_partial_deletion(
    tmp_path: Path, version: str
) -> None:
    paths = _prepare_cleanup_state(tmp_path, {"activation": 1000})
    old = tmp_path / "stats" / f"{_utc_month(-2)}.jsonl"
    old_data = _write_month(old, _utc_month(-2))
    current = tmp_path / "stats" / f"{_utc_month(0)}.jsonl"
    row = json.loads(_write_month(current, _utc_month(0)))
    row.update(k="u", v=version, r="")
    current.write_text(json.dumps(row) + "\n", encoding="ascii")
    before = paths["activation"].read_bytes()

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 65
    assert old.read_bytes() == old_data
    assert paths["activation"].read_bytes() == before


def test_private_cleanup_utc_month_window_handles_the_year_boundary() -> None:
    php = php_executable()
    source = CLEANUP.read_text(encoding="utf-8")
    function = _php_function(source, "cleanup_month_window")
    code = function + "\necho json_encode(cleanup_month_window(gmmktime(12, 0, 0, 1, 15, 2027)));"

    result = subprocess.run([php, "-r", code], capture_output=True, text=True, timeout=30)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["2027-01", "2026-12"]


def test_private_cleanup_accepts_more_than_16384_rows_near_the_16_mib_limit(
    tmp_path: Path,
) -> None:
    paths = _prepare_cleanup_state(tmp_path)
    current = tmp_path / "stats" / f"{_utc_month(0)}.jsonl"
    row = _write_month(current, _utc_month(0))
    copies = (16 * 1024 * 1024 - 1) // len(row)
    assert copies > 16384
    data = row * copies
    current.write_bytes(data)
    _chmod_private(current)
    before = hashlib.sha256(data).digest()
    old = tmp_path / "stats" / f"{_utc_month(-2)}.jsonl"
    _write_month(old, _utc_month(-2))

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 0, result.stderr
    assert current.stat().st_size == len(data)
    assert hashlib.sha256(current.read_bytes()).digest() == before
    assert not old.exists()


def test_private_cleanup_rejects_a_future_utc_month_without_deleting_old_data(
    tmp_path: Path,
) -> None:
    paths = _prepare_cleanup_state(tmp_path)
    old = tmp_path / "stats" / f"{_utc_month(-2)}.jsonl"
    old_data = _write_month(old, _utc_month(-2))
    future = tmp_path / "stats" / f"{_utc_month(1)}.jsonl"
    future_data = _write_month(future, _utc_month(1))

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 65
    assert old.read_bytes() == old_data
    assert future.read_bytes() == future_data


@pytest.mark.parametrize("problem", ["json", "month"])
def test_private_cleanup_validates_every_month_before_deleting_any(
    tmp_path: Path, problem: str
) -> None:
    paths = _prepare_cleanup_state(tmp_path, {"count": 70})
    count_before = paths["count"].read_bytes()
    first = tmp_path / "stats" / f"{_utc_month(-3)}.jsonl"
    broken = tmp_path / "stats" / f"{_utc_month(-2)}.jsonl"
    first_data = _write_month(first, _utc_month(-3))
    if problem == "json":
        broken.write_text("kein json\n", encoding="ascii")
        _chmod_private(broken)
    else:
        _write_month(broken, _utc_month(-2), timestamp_month=_utc_month(-1))
    broken_before = broken.read_bytes()

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 65
    assert first.read_bytes() == first_data
    assert broken.read_bytes() == broken_before
    assert paths["count"].read_bytes() == count_before


def test_private_cleanup_restores_earlier_month_if_a_later_clear_fails() -> None:
    php = php_executable()
    source = CLEANUP.read_text(encoding="utf-8")
    function = _php_function(source, "cleanup_remove_old_months")
    code = (
        "class CleanupFailure extends RuntimeException {}\n"
        "$states = ['a' => 'eins', 'b' => 'zwei']; $unlinked = [];\n"
        "function cleanup_write_locked(array $locked, string $data): void { "
        "global $states; $path = $locked['target']['path']; "
        "if ($path === 'b' && $data === '') { throw new CleanupFailure('Schreibfehler'); } "
        "$states[$path] = $data; }\n"
        "function cleanup_unlink_empty_locked(array &$locked): void { "
        "global $states, $unlinked; $path = $locked['target']['path']; "
        "$unlinked[] = $path; unset($states[$path]); }\n" + function + "\n$months = ["
        "['target' => ['path' => 'a'], 'original' => 'eins'], "
        "['target' => ['path' => 'b'], 'original' => 'zwei']]; "
        "try { cleanup_remove_old_months($months); exit(2); } "
        "catch (CleanupFailure $problem) { "
        "exit($states === ['a' => 'eins', 'b' => 'zwei'] && $unlinked === [] ? 0 : 3); } "
        "catch (Throwable $problem) { fwrite(STDERR, get_class($problem)); exit(4); }"
    )

    result = subprocess.run([php, "-r", code], capture_output=True, text=True, timeout=30)

    assert result.returncode == 0, result.stdout + result.stderr


def test_private_cleanup_rejects_non_calendar_jsonl_without_partial_cleanup(
    tmp_path: Path,
) -> None:
    paths = _prepare_cleanup_state(tmp_path)
    old = tmp_path / "stats" / f"{_utc_month(-2)}.jsonl"
    old_data = _write_month(old, _utc_month(-2))
    unexpected = tmp_path / "stats" / "reichweite.jsonl"
    unexpected.write_bytes(old_data)
    _chmod_private(unexpected)

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 65
    assert old.read_bytes() == old_data
    assert unexpected.read_bytes() == old_data


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_private_cleanup_rejects_linked_month_files(tmp_path: Path, link_kind: str) -> None:
    paths = _prepare_cleanup_state(tmp_path)
    target = tmp_path / "protected-month.jsonl"
    target_data = _write_month(target, _utc_month(-2))
    linked = tmp_path / "stats" / f"{_utc_month(-2)}.jsonl"
    try:
        if link_kind == "symlink":
            linked.symlink_to(target)
        else:
            os.link(target, linked)
    except OSError:
        pytest.skip(f"dieser Prüfstand erlaubt keinen {link_kind}")

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 65
    assert target.read_bytes() == target_data


@pytest.mark.skipif(os.name == "nt", reason="POSIX-Dateirechte gibt es unter Windows nicht")
def test_private_cleanup_rejects_group_readable_month_file(tmp_path: Path) -> None:
    paths = _prepare_cleanup_state(tmp_path)
    old = tmp_path / "stats" / f"{_utc_month(-2)}.jsonl"
    old_data = _write_month(old, _utc_month(-2))
    old.chmod(0o640)

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 65
    assert old.read_bytes() == old_data


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_private_cleanup_rejects_linked_quota_lock(tmp_path: Path, link_kind: str) -> None:
    paths = _prepare_cleanup_state(tmp_path)
    target = tmp_path / "protected-quota.lock"
    target.write_bytes(b"")
    _chmod_private(target)
    quota = tmp_path / "stats" / "quota.lock"
    try:
        if link_kind == "symlink":
            quota.symlink_to(target)
        else:
            os.link(target, quota)
    except OSError:
        pytest.skip(f"dieser Prüfstand erlaubt keinen {link_kind}")

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 65
    assert target.read_bytes() == b""


@pytest.mark.skipif(os.name == "nt", reason="POSIX-Dateirechte gibt es unter Windows nicht")
def test_private_cleanup_rejects_group_readable_quota_lock(tmp_path: Path) -> None:
    paths = _prepare_cleanup_state(tmp_path)
    quota = tmp_path / "stats" / "quota.lock"
    quota.write_bytes(b"")
    quota.chmod(0o640)

    result = _run_cleanup(tmp_path, paths)

    assert result.returncode == 65


def test_private_cleanup_respects_the_live_count_quota_lock(tmp_path: Path) -> None:
    php = php_executable()
    paths = _prepare_cleanup_state(tmp_path)
    old = tmp_path / "stats" / f"{_utc_month(-2)}.jsonl"
    old_data = _write_month(old, _utc_month(-2))
    quota = tmp_path / "stats" / "quota.lock"
    quota.write_bytes(b"")
    _chmod_private(quota)
    locker = subprocess.Popen(
        [
            php,
            "-r",
            '$f=fopen($argv[1], "r+b"); flock($f, LOCK_EX); '
            'fwrite(STDOUT, "gesperrt\\n"); fflush(STDOUT); sleep(30);',
            str(quota),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert locker.stdout is not None
        assert locker.stdout.readline().strip() == "gesperrt"
        result = _run_cleanup(tmp_path, paths)
    finally:
        locker.terminate()
        locker.wait(timeout=5)
        if locker.stdout is not None:
            locker.stdout.close()
        if locker.stderr is not None:
            locker.stderr.close()

    assert result.returncode == 75
    assert old.read_bytes() == old_data


@pytest.mark.parametrize(
    ("source_name", "function_name"),
    [
        ("support.php", "support_open_rate_state"),
        ("activation_common.php", "activation_open_rate_state"),
        ("count.php", "count_open_private_state"),
        ("stats.php", "stats_open_rate_state"),
    ],
)
@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_every_rate_writer_rejects_linked_state_files(
    tmp_path: Path, source_name: str, function_name: str, link_kind: str
) -> None:
    php = php_executable()
    target = tmp_path / f"{function_name}-target.json"
    target.write_text("{}", encoding="ascii")
    _chmod_private(target)
    linked = tmp_path / f"{function_name}-linked.json"
    try:
        if link_kind == "symlink":
            linked.symlink_to(target)
        else:
            os.link(target, linked)
    except OSError:
        pytest.skip(f"dieser Prüfstand erlaubt keinen {link_kind}")
    source = (API / source_name).read_text(encoding="utf-8")
    function = _php_function(source, function_name)
    dependency = (
        _php_function(source, "count_stream_is_named_private") + "\n"
        if source_name == "count.php"
        else ""
    )
    prelude = (
        "class ExpectedRejection extends RuntimeException {}\n"
        "class ActivationFailure extends ExpectedRejection { "
        "function __construct(string $message, int $status = 500, string $codeName = '') "
        "{ parent::__construct($message); } }\n"
        "function answer(bool $ok, string $error = '', string $reference = '', "
        "int $status = 200): void { throw new ExpectedRejection($error); }\n"
    )
    expects_exception = source_name in {"support.php", "activation_common.php"}
    success = (
        "if (is_resource($stream)) { flock($stream, LOCK_UN); fclose($stream); } exit(3);"
        if expects_exception
        else "exit($stream === null ? 0 : 3);"
    )
    expected_catch = (
        "catch (ExpectedRejection $problem) { exit(0); }"
        if expects_exception
        else "catch (ExpectedRejection $problem) { exit(4); }"
    )
    code = (
        prelude
        + dependency
        + function
        + (
            f"\ntry {{ $stream = {function_name}($argv[1]); {success} }} "
            f"{expected_catch} catch (Throwable $problem) {{ "
            "fwrite(STDERR, get_class($problem) . ': ' . $problem->getMessage()); exit(5); }"
        )
    )

    result = subprocess.run(
        [php, "-r", code, str(linked)], capture_output=True, text=True, timeout=30
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert target.read_text(encoding="ascii") == "{}"


@pytest.mark.skipif(os.name == "nt", reason="POSIX-Dateirechte gibt es unter Windows nicht")
@pytest.mark.parametrize(
    ("source_name", "function_name"),
    [
        ("support.php", "support_open_rate_state"),
        ("activation_common.php", "activation_open_rate_state"),
        ("count.php", "count_open_private_state"),
        ("stats.php", "stats_open_rate_state"),
    ],
)
def test_every_rate_writer_rejects_group_readable_state(
    tmp_path: Path, source_name: str, function_name: str
) -> None:
    php = php_executable()
    state = tmp_path / f"{function_name}.json"
    state.write_text("{}", encoding="ascii")
    state.chmod(0o640)
    source = (API / source_name).read_text(encoding="utf-8")
    function = _php_function(source, function_name)
    dependency = (
        _php_function(source, "count_stream_is_named_private") + "\n"
        if source_name == "count.php"
        else ""
    )
    prelude = (
        "class ExpectedRejection extends RuntimeException {}\n"
        "class ActivationFailure extends ExpectedRejection { "
        "function __construct(string $message, int $status = 500, string $codeName = '') "
        "{ parent::__construct($message); } }\n"
        "function answer(bool $ok, string $error = '', string $reference = '', "
        "int $status = 200): void { throw new ExpectedRejection($error); }\n"
    )
    expects_exception = source_name in {"support.php", "activation_common.php"}
    success = (
        "if (is_resource($stream)) { flock($stream, LOCK_UN); fclose($stream); } exit(3);"
        if expects_exception
        else "exit($stream === null ? 0 : 3);"
    )
    expected_catch = (
        "catch (ExpectedRejection $problem) { exit(0); }"
        if expects_exception
        else "catch (ExpectedRejection $problem) { exit(4); }"
    )
    code = (
        prelude
        + dependency
        + function
        + (
            f"\ntry {{ $stream = {function_name}($argv[1]); {success} }} "
            f"{expected_catch} catch (Throwable $problem) {{ "
            "fwrite(STDERR, get_class($problem) . ': ' . $problem->getMessage()); exit(5); }"
        )
    )

    result = subprocess.run(
        [php, "-r", code, str(state)], capture_output=True, text=True, timeout=30
    )

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("source_name", "function_name"),
    [
        ("support.php", "support_replace_stream"),
        ("activation_common.php", "activation_replace_stream"),
        ("count.php", "count_replace_stream"),
        ("stats.php", "stats_replace_stream"),
        ("cleanup_private_state.php", "cleanup_replace_stream"),
    ],
)
def test_every_private_state_writer_restores_after_write_and_flush_failures(
    source_name: str, function_name: str
) -> None:
    php = php_executable()
    source = (API / source_name).read_text(encoding="utf-8")
    prefix = function_name.removesuffix("_replace_stream")
    code = (
        _fault_stream_php()
        + f"function {prefix}_flush_and_sync($stream): bool {{ return fflush($stream); }}\n"
        + _php_function(source, f"{prefix}_write_all")
        + "\n"
        + _php_function(source, f"{prefix}_restore_stream")
        + "\n"
        + _php_function(source, function_name)
        + "\nforeach (['write', 'flush'] as $mode) { "
        "FaultStream::$data = 'alt'; FaultStream::$mode = $mode; FaultStream::$stage = 0; "
        "$stream = fopen('faultstream://state', 'w+'); "
        "stream_set_read_buffer($stream, 0); stream_set_write_buffer($stream, 0); "
        + f"$ok = {function_name}($stream, 'neu'); "
        "if ($ok || FaultStream::$data !== 'alt') { "
        "fwrite(STDERR, $mode . ':' . bin2hex(FaultStream::$data)); exit(2); } fclose($stream); } "
        "FaultStream::$data = 'alt'; FaultStream::$mode = 'dead'; FaultStream::$stage = 0; "
        "$stream = fopen('faultstream://state', 'w+'); "
        "stream_set_read_buffer($stream, 0); stream_set_write_buffer($stream, 0); "
        + f"$ok = {function_name}($stream, 'neu'); "
        "exit(!$ok && FaultStream::$data !== 'alt' ? 0 : 3);"
    )

    result = subprocess.run([php, "-r", code], capture_output=True, text=True, timeout=30)

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("source_name", "function_name"),
    [
        ("support.php", "support_replace_stream"),
        ("activation_common.php", "activation_replace_stream"),
        ("count.php", "count_replace_stream"),
        ("stats.php", "stats_replace_stream"),
        ("cleanup_private_state.php", "cleanup_replace_stream"),
    ],
)
def test_every_private_state_writer_persists_with_real_fsync(
    tmp_path: Path, source_name: str, function_name: str
) -> None:
    php = php_executable()
    source = (API / source_name).read_text(encoding="utf-8")
    prefix = function_name.removesuffix("_replace_stream")
    state = tmp_path / f"{prefix}.json"
    state.write_text("alt", encoding="ascii")
    code = (
        _php_function(source, f"{prefix}_write_all")
        + "\n"
        + _php_function(source, f"{prefix}_flush_and_sync")
        + "\n"
        + _php_function(source, f"{prefix}_restore_stream")
        + "\n"
        + _php_function(source, function_name)
        + f"\n$stream = fopen($argv[1], 'r+b'); $ok = {function_name}($stream, 'neu'); "
        "fclose($stream); exit($ok ? 0 : 2);"
    )

    result = subprocess.run(
        [php, "-r", code, str(state)], capture_output=True, text=True, timeout=30
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert state.read_text(encoding="ascii") == "neu"


def test_count_append_restores_recoverable_failures_and_blocks_irreparable_ones() -> None:
    php = php_executable()
    source = (API / "count.php").read_text(encoding="utf-8")
    code = (
        _fault_stream_php()
        + "function count_stream_is_named_private($path, $stream): bool { return true; }\n"
        "function count_flush_and_sync($stream): bool { return fflush($stream); }\n"
        + _php_function(source, "count_rollback_append")
        + "\n"
        + _php_function(source, "count_append_stream")
        + "\nforeach (['write', 'flush'] as $mode) { "
        "FaultStream::$data = 'alt'; FaultStream::$mode = $mode; FaultStream::$stage = 0; "
        "$stream = fopen('faultstream://state', 'w+'); "
        "stream_set_read_buffer($stream, 0); stream_set_write_buffer($stream, 0); "
        "$ok = count_append_stream('/privat/monat.jsonl', $stream, 'neu'); "
        "if ($ok || FaultStream::$data !== 'alt') { "
        "fwrite(STDERR, $mode . ':' . bin2hex(FaultStream::$data)); exit(2); } fclose($stream); } "
        "FaultStream::$data = 'alt'; FaultStream::$mode = 'dead'; FaultStream::$stage = 0; "
        "$stream = fopen('faultstream://state', 'w+'); "
        "stream_set_read_buffer($stream, 0); stream_set_write_buffer($stream, 0); "
        "$ok = count_append_stream('/privat/monat.jsonl', $stream, 'neu'); "
        "exit(!$ok && FaultStream::$data !== 'alt' ? 0 : 3);"
    )

    result = subprocess.run([php, "-r", code], capture_output=True, text=True, timeout=30)

    assert result.returncode == 0, result.stdout + result.stderr


def test_count_rate_window_survives_utc_midnight_without_the_day_salt() -> None:
    php = php_executable()
    source = (API / "count.php").read_text(encoding="utf-8")
    function = _php_function(source, "count_rate_client_keys")
    code = (
        "const COUNT_RATE_RETENTION_SECONDS = 60;\n"
        + function
        + "\n$_SERVER['REMOTE_ADDR'] = '198.51.100.7'; "
        "$secret = str_repeat('ab', 32); "
        "$before = gmmktime(23, 59, 59, 1, 1, 2027); "
        "$after = $before + 2; "
        "echo json_encode([count_rate_client_keys($secret, $before), "
        "count_rate_client_keys($secret, $after)]);"
    )

    result = subprocess.run([php, "-r", code], capture_output=True, text=True, timeout=30)
    windows = json.loads(result.stdout)

    assert result.returncode == 0, result.stderr
    assert windows[0][0] != windows[1][0]
    assert set(windows[0]) & set(windows[1])
    assert "rate.key" in source
    assert "count_consume_rate($dir, $rateSecret" in source


@pytest.mark.parametrize("endpoint", ["activation_common.php", "day_zone.php"])
def test_shared_php_helpers_are_not_public_blank_endpoints(tmp_path: Path, endpoint: str) -> None:
    with _php_server(tmp_path) as base:
        status, headers, _body = _request(f"{base}/{endpoint}")

    assert status == 404
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize(
    ("endpoint", "method", "allow"),
    [
        ("support.php", "GET", "POST"),
        ("activation.php", "GET", "POST"),
        ("deactivation.php", "GET", "POST"),
        ("activation-health.php", "POST", "GET"),
        ("operator.php", "GET", "POST"),
        ("count.php", "PUT", "GET, HEAD, POST"),
        ("stats.php", "PUT", "GET, HEAD, POST"),
    ],
)
def test_methods_are_bound_before_configuration_is_disclosed(
    tmp_path: Path, endpoint: str, method: str, allow: str
) -> None:
    with _php_server(tmp_path) as base:
        status, headers, _body = _request(f"{base}/{endpoint}", method=method, data=b"")

    assert status == 405
    assert headers["Allow"] == allow


@pytest.mark.parametrize(
    ("endpoint", "content_type"),
    [
        ("support.php", "application/json"),
        ("activation.php", "text/plain"),
        ("deactivation.php", "text/plain"),
        ("operator.php", "text/plain"),
        ("count.php", "application/json"),
        ("stats.php", "application/json"),
    ],
)
def test_post_content_types_are_fail_closed(
    tmp_path: Path, endpoint: str, content_type: str
) -> None:
    if endpoint in {"activation.php", "deactivation.php"}:
        # Beide prüfen sodium vor dem Medientyp und antworten ohne es 503 —
        # die Frage nach 415 lässt sich dann nicht stellen (`php_probe`).
        php_extension("sodium")
    with _php_server(tmp_path) as base:
        headers = {"Content-Type": content_type}
        if endpoint in {"count.php", "stats.php"}:
            headers["Origin"] = "https://solidon3d.de"
        status, _headers, _body = _request(
            f"{base}/{endpoint}",
            method="POST",
            data=b"{}",
            headers=headers,
        )

    assert status == 415


@pytest.mark.parametrize(
    "endpoint",
    [
        "support.php",
        "activation.php",
        "deactivation.php",
        "operator.php",
        "count.php",
        "stats.php",
    ],
)
def test_cross_site_browser_posts_are_rejected(tmp_path: Path, endpoint: str) -> None:
    content_type = (
        "multipart/form-data; boundary=x"
        if endpoint == "support.php"
        else (
            "application/x-www-form-urlencoded"
            if endpoint in {"count.php", "stats.php"}
            else "application/json"
        )
    )
    with _php_server(tmp_path) as base:
        status, _headers, _body = _request(
            f"{base}/{endpoint}",
            method="POST",
            data=b"x",
            headers={"Content-Type": content_type, "Origin": "https://angreifer.example"},
        )

    assert status == 403


def test_security_headers_cover_json_html_and_redirect_responses(tmp_path: Path) -> None:
    with _php_server(tmp_path) as base:
        responses = [
            _request(f"{base}/activation-health.php"),
            _request(f"{base}/stats.php"),
            _request(f"{base}/count.php"),
        ]

    for _status, headers, _body in responses:
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Referrer-Policy"] == "no-referrer"
        assert headers["X-Frame-Options"] == "DENY"
        assert "default-src" in headers["Content-Security-Policy"]


def test_counter_rate_limit_caps_disk_growth(tmp_path: Path) -> None:
    body = urlencode({"p": "/test"}).encode("ascii")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://solidon3d.de",
    }
    with _php_server(tmp_path) as base:
        statuses = [
            _request(f"{base}/count.php", method="POST", data=body, headers=headers)[0]
            for _attempt in range(61)
        ]

    assert statuses[:60] == [204] * 60
    assert statuses[60] == 429
    rows = list((tmp_path / "stats").glob("*.jsonl"))
    assert len(rows) == 1
    assert len(rows[0].read_text(encoding="utf-8").splitlines()) == 60
    if os.name != "nt":
        assert rows[0].stat().st_mode & 0o077 == 0
        assert (tmp_path / "stats" / "quota.lock").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("state_name", ["quota", "month"])
@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_counter_rejects_linked_quota_and_month_files(
    tmp_path: Path, state_name: str, link_kind: str
) -> None:
    stats = tmp_path / "stats"
    stats.mkdir(mode=0o700)
    _chmod_private(stats)
    protected = tmp_path / f"protected-{state_name}.txt"
    protected.write_text("unverändert", encoding="utf-8")
    _chmod_private(protected)
    linked = (
        stats / "quota.lock"
        if state_name == "quota"
        else stats / f"{datetime.now(UTC):%Y-%m}.jsonl"
    )
    try:
        if link_kind == "symlink":
            linked.symlink_to(protected)
        else:
            os.link(protected, linked)
    except OSError:
        pytest.skip(f"dieser Prüfstand erlaubt keinen {link_kind}")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://solidon3d.de",
    }

    with _php_server(tmp_path) as base:
        status = _request(
            f"{base}/count.php",
            method="POST",
            data=urlencode({"p": "/test"}).encode("ascii"),
            headers=headers,
        )[0]

    assert status == 429
    assert protected.read_text(encoding="utf-8") == "unverändert"


@pytest.mark.skipif(os.name == "nt", reason="POSIX-Dateirechte gibt es unter Windows nicht")
@pytest.mark.parametrize("state_name", ["quota", "month"])
def test_counter_rejects_group_readable_quota_and_month_files(
    tmp_path: Path, state_name: str
) -> None:
    stats = tmp_path / "stats"
    stats.mkdir(mode=0o700)
    state = (
        stats / "quota.lock"
        if state_name == "quota"
        else stats / f"{datetime.now(UTC):%Y-%m}.jsonl"
    )
    state.write_text("", encoding="ascii")
    state.chmod(0o640)

    with _php_server(tmp_path) as base:
        status = _request(
            f"{base}/count.php",
            method="POST",
            data=urlencode({"p": "/test"}).encode("ascii"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://solidon3d.de",
            },
        )[0]

    assert status == 429


def test_activation_rate_key_never_depends_on_the_signing_seed(tmp_path: Path) -> None:
    php_extension("sodium")
    database = tmp_path / "activation.sqlite"
    seed = tmp_path / "activation.seed"
    environment = {
        "SOLIDON_ACTIVATION_DB": str(database),
        "SOLIDON_ACTIVATION_SEED_FILE": str(seed),
    }
    headers = {"Content-Type": "application/json"}
    rate_key = tmp_path / "activation-rate.json.key"
    with _php_server(tmp_path, environment) as base:
        status, _headers, answer = _request(
            f"{base}/activation.php", method="POST", data=b"{}", headers=headers
        )
        assert status == 400, answer
        secret = rate_key.read_bytes()
        assert re.fullmatch(rb"[0-9a-f]{64}", secret)
        assert not seed.exists() and not database.exists()
        seed.write_text("absichtlich-kein-Signaturschlüssel", encoding="utf-8")
        _chmod_private(seed)
        status, _headers, answer = _request(
            f"{base}/activation.php", method="POST", data=b"{}", headers=headers
        )
        assert status == 400, answer
        assert rate_key.read_bytes() == secret
        assert seed.read_text(encoding="utf-8") == "absichtlich-kein-Signaturschlüssel"
        rate_key.write_text("beschädigt", encoding="utf-8")
        status, _headers, answer = _request(
            f"{base}/activation.php", method="POST", data=b"{}", headers=headers
        )
        assert status == 503, answer
        assert rate_key.read_text(encoding="utf-8") == "beschädigt"


@pytest.mark.parametrize("endpoint", ["activation", "support"])
def test_one_client_cannot_fill_the_global_request_budget(tmp_path: Path, endpoint: str) -> None:
    """Abgewiesene IP-Anfragen zählen nicht weiter gegen alle anderen Nutzer."""
    from app.core.activation.ed25519 import public_key

    php_extension("sodium")
    seed = bytes(range(32))
    seed_file = tmp_path / "activation.seed"
    seed_file.write_text(seed.hex(), encoding="ascii")
    _chmod_private(seed_file)
    prepend = tmp_path / "client-address.php"
    prepend.write_text(
        "<?php $_SERVER['REMOTE_ADDR'] = $_SERVER['HTTP_X_TEST_ADDRESS'] ?? '192.0.2.1';",
        encoding="ascii",
    )
    environment = {
        "SOLIDON_ACTIVATION_SEED_FILE": str(seed_file),
        "SOLIDON_ACTIVATION_DB": str(tmp_path / "activation.sqlite"),
        "SOLIDON_ACTIVATION_TEST_PUBLIC_KEY": public_key(seed).hex(),
    }
    budget = 30 if endpoint == "activation" else 12
    payload = (
        b"{}"
        if endpoint == "activation"
        else b'--test\r\nContent-Disposition: form-data; name="message"\r\n\r\n'
        b"Lokaler Test\r\n--test--\r\n"
    )
    content_type = (
        "application/json" if endpoint == "activation" else "multipart/form-data; boundary=test"
    )
    accepted_status = 400 if endpoint == "activation" else 502
    global_key = "issue:global" if endpoint == "activation" else "global"
    headers = {"Content-Type": content_type, "X-Test-Address": "192.0.2.1"}
    with _php_server(tmp_path, environment, prepend=prepend) as base:
        for _attempt in range(budget):
            status, _headers, answer = _request(
                f"{base}/{endpoint}.php", method="POST", data=payload, headers=headers
            )
            assert status == accepted_status, answer
        state_path = tmp_path / f"{endpoint}-rate.json"
        before = state_path.read_bytes()
        assert len(json.loads(before)[global_key]) == budget
        for _attempt in range(10):
            status, _headers, answer = _request(
                f"{base}/{endpoint}.php", method="POST", data=payload, headers=headers
            )
            assert status == 429, answer
        assert state_path.read_bytes() == before
        headers["X-Test-Address"] = "192.0.2.2"
        status, _headers, answer = _request(
            f"{base}/{endpoint}.php", method="POST", data=payload, headers=headers
        )
        assert status == accepted_status, answer
        assert len(json.loads(state_path.read_bytes())[global_key]) == budget + 1


def test_rate_limit_states_use_keyed_rotating_identifiers_and_purge_old_data(
    tmp_path: Path,
) -> None:
    """Kein Missbrauchszähler lässt eine offline erratbare IP-Kennung liegen."""
    # activation.php bereinigt seinen Zähler erst hinter der sodium-Prüfung;
    # ohne die Erweiterung bliebe der rohe Hash liegen, und der Test wäre rot
    # über die Umgebung statt über den Endpunkt (`php_probe`).
    php = php_extension("sodium")

    now = int(time.time())
    raw_ip_hash = hashlib.sha256(b"127.0.0.1").hexdigest()
    old = now - 7200
    future = now + 7200
    stats_dir = tmp_path / "stats"
    stats_dir.mkdir(mode=0o700)
    (stats_dir / "rate.json").write_text(
        json.dumps({raw_ip_hash: [now, future], "global": [old, future]}),
        encoding="utf-8",
    )
    (stats_dir / "anmeldeversuche.json").write_text(
        json.dumps({f"ip:{raw_ip_hash}": [now, future], "global": [old, future]}),
        encoding="utf-8",
    )
    support_rate = tmp_path / "support-rate.json"
    support_rate.write_text(
        json.dumps({raw_ip_hash: [now, future], "global": [old, future]}),
        encoding="utf-8",
    )
    activation_rate = tmp_path / "activation-rate.json"
    activation_rate.write_text(
        json.dumps({f"issue:{raw_ip_hash}": [now, future], "issue:global": [old, future]}),
        encoding="utf-8",
    )
    for path in [
        stats_dir / "rate.json",
        stats_dir / "anmeldeversuche.json",
        support_rate,
        activation_rate,
    ]:
        _chmod_private(path)

    access_dir = tmp_path / "access"
    access_dir.mkdir(mode=0o700)
    password_hash = subprocess.run(
        [php, "-r", "echo password_hash('richtig', PASSWORD_DEFAULT);"],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout
    access_file = access_dir / "stats-access.php"
    access_file.write_text(
        "<?php return ['hash' => " + repr(password_hash) + "];\n", encoding="utf-8"
    )
    access_file.chmod(0o600)
    environment = {
        "SOLIDON_STATS_ACCESS_FILE": str(access_file),
    }
    prepend = tmp_path / "php-test-extensions.php"
    prepend.write_text(
        "<?php\n"
        "if (!function_exists('mb_strlen')) {\n"
        "  function mb_strlen(string $value, ?string $encoding = null): int "
        "{ return strlen($value); }\n"
        "  function mb_substr(string $value, int $offset, ?int $length = null): string "
        "{ return substr($value, $offset, $length); }\n"
        "}\n",
        encoding="utf-8",
    )
    form_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://solidon3d.de",
    }
    boundary = "solidon-rate-test"
    support_body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="message"\r\n\r\n'
        "Pruefung\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="kind"\r\n\r\n'
        "idea\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    with _php_server(tmp_path, environment, prepend=prepend) as base:
        assert (
            _request(
                f"{base}/count.php",
                method="POST",
                data=urlencode({"p": "/schutz"}).encode("ascii"),
                headers=form_headers,
            )[0]
            == 204
        )
        support_status = _request(
            f"{base}/support.php",
            method="POST",
            data=support_body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )[0]
        assert support_status in {200, 502}
        assert _request(
            f"{base}/activation.php",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )[0] in {400, 503}
        assert (
            _request(
                f"{base}/stats.php",
                method="POST",
                data=urlencode({"password": "falsch"}).encode("ascii"),
                headers=form_headers,
            )[0]
            == 403
        )

    states = [
        (stats_dir / "rate.json", "ip:", 60),
        (support_rate, "ip:", 3600),
        (activation_rate, "issue:ip:", 900),
        (stats_dir / "anmeldeversuche.json", "ip:v2:", 900),
    ]
    checked_at = int(time.time())
    for path, prefix, retention in states:
        state = json.loads(path.read_text(encoding="utf-8"))
        assert raw_ip_hash not in "\n".join(state)
        assert any(key.startswith(prefix) for key in state)
        for stamps in state.values():
            assert all(checked_at - retention < stamp <= checked_at for stamp in stamps)

    support_secret = (tmp_path / "support-rate.json.key").read_text(encoding="ascii")
    assert re.fullmatch(r"[0-9a-f]{64}", support_secret)
    if os.name != "nt":
        assert (tmp_path / "support-rate.json.key").stat().st_mode & 0o077 == 0


def test_rate_limit_sources_define_exact_retention_and_windowed_hmacs() -> None:
    """Der Quellvertrag benennt Fristen und leitet Kennzeichen je Zeitfenster ab."""
    sources = {
        "support": (API / "support.php").read_text(encoding="utf-8"),
        "activation": (API / "activation_common.php").read_text(encoding="utf-8"),
        "count": (API / "count.php").read_text(encoding="utf-8"),
        "stats": (API / "stats.php").read_text(encoding="utf-8"),
    }

    assert "const SUPPORT_RATE_RETENTION_SECONDS = 3600;" in sources["support"]
    assert "const ACTIVATION_RATE_RETENTION_SECONDS = 900;" in sources["activation"]
    assert "const COUNT_RATE_RETENTION_SECONDS = 60;" in sources["count"]
    assert "const STATS_RATE_RETENTION_SECONDS = 900;" in sources["stats"]
    for source in sources.values():
        assert "hash_hmac('sha256'" in source
        assert "intdiv($now," in source
        assert "$stamp <= $now" in source
        assert "hash('sha256', (string) ($_SERVER['REMOTE_ADDR']" not in source
        assert "$raw === false || !is_array(" in source


def test_corrupt_rate_limit_states_fail_closed(tmp_path: Path) -> None:
    """Ein beschädigter Zähler wird nicht als leere Freigabe behandelt."""
    stats_dir = tmp_path / "stats"
    stats_dir.mkdir(mode=0o700)
    count_rate = stats_dir / "rate.json"
    support_rate = tmp_path / "support-rate.json"
    activation_rate = tmp_path / "activation-rate.json"
    stats_rate = stats_dir / "anmeldeversuche.json"
    count_rate.write_text("null", encoding="ascii")
    support_rate.write_text("null", encoding="ascii")
    activation_rate.write_text("null", encoding="ascii")
    stats_rate.write_text("null", encoding="ascii")
    for path in [count_rate, support_rate, activation_rate, stats_rate]:
        _chmod_private(path)
    access_dir = tmp_path / "access"
    access_dir.mkdir(mode=0o700)
    _chmod_private(access_dir)
    php = php_executable()
    password_hash = subprocess.run(
        [php, "-r", "echo password_hash('richtig', PASSWORD_DEFAULT);"],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout
    access_file = access_dir / "stats-access.php"
    access_file.write_text(
        "<?php return ['hash' => " + repr(password_hash) + "];\n", encoding="utf-8"
    )
    _chmod_private(access_file)
    prepend = tmp_path / "php-test-mbstring.php"
    prepend.write_text(
        "<?php\n"
        "if (!function_exists('mb_strlen')) {\n"
        "  function mb_strlen(string $value, ?string $encoding = null): int "
        "{ return strlen($value); }\n"
        "  function mb_substr(string $value, int $offset, ?int $length = null): string "
        "{ return substr($value, $offset, $length); }\n"
        "}\n",
        encoding="utf-8",
    )
    boundary = "solidon-corrupt-rate-test"
    support_body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="message"\r\n\r\n'
        "Pruefung\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="kind"\r\n\r\n'
        "idea\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    with _php_server(
        tmp_path,
        {"SOLIDON_STATS_ACCESS_FILE": str(access_file)},
        prepend=prepend,
    ) as base:
        count_status = _request(
            f"{base}/count.php",
            method="POST",
            data=urlencode({"p": "/schutz"}).encode("ascii"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://solidon3d.de",
            },
        )[0]
        support_status = _request(
            f"{base}/support.php",
            method="POST",
            data=support_body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )[0]
        activation_status = _request(
            f"{base}/activation.php",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )[0]
        stats_status = _request(
            f"{base}/stats.php",
            method="POST",
            data=urlencode({"password": "falsch"}).encode("ascii"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://solidon3d.de",
            },
        )[0]

    assert count_status == 429
    assert support_status == 503
    assert activation_status == 503
    # Auch die Anmeldung: Ein Zähler, der sich nicht lesen lässt, ist kein
    # Sperrzustand, sondern ein Speicherfehler — ``stats_unavailable`` sagt
    # seit a19293d5 ehrlich 503, wo vorher „Zu viele Versuche" stand, obwohl
    # niemand es versucht hatte. Fail-closed bleibt es: hinein kommt keiner.
    assert stats_status == 503
    assert count_rate.read_text(encoding="ascii") == "null"
    assert support_rate.read_text(encoding="ascii") == "null"


@pytest.mark.parametrize("quota", ["month", "total"])
def test_counter_storage_quotas_fail_closed_without_growth(tmp_path: Path, quota: str) -> None:
    docroot = _temporary_docroot(tmp_path)
    metadata = b'{"version":"0.4.0"}'
    (docroot / "version.json").write_bytes(metadata)
    package = "Solidon3D-Setup-0.0.0-test.exe"
    (docroot / "dl" / package).write_bytes(b"kein echtes Paket")
    directory = tmp_path / "stats"
    directory.mkdir(mode=0o700)
    current = directory / f"{datetime.now(UTC):%Y-%m}.jsonl"
    if quota == "month":
        current.write_bytes(b"")
        with current.open("r+b") as stream:
            stream.truncate(16 * 1024 * 1024)
        watched = [current]
    else:
        watched = []
        for month in ("2020-01", "2020-02", "2020-03", "2020-04"):
            path = directory / f"{month}.jsonl"
            path.write_bytes(b"")
            with path.open("r+b") as stream:
                stream.truncate(16 * 1024 * 1024)
            watched.append(path)
    before = {path: path.stat().st_size for path in watched}
    body = urlencode({"p": "/quota"}).encode("ascii")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://solidon3d.de",
    }

    log = tmp_path / "quota.log"
    with _php_server(tmp_path, error_log=log, docroot=docroot) as base:
        status, _headers, _body = _request(
            f"{base}/count.php", method="POST", data=body, headers=headers
        )
        update_status, _headers, update_body = _request(f"{base}/count.php?u=1")
        assert (update_status, update_body.encode()) == (200, metadata)
        download_status, target = _without_redirects(f"{base}/count.php?f={package}", "GET")
        assert (download_status, target) == (302, f"/dl/{package}")

    assert status == 204, "Volle Ablage ist keine Überschreitung des Besucherlimits"
    assert f"Solidon count storage quota: {quota}" in log.read_text(encoding="utf-8")
    assert {path: path.stat().st_size for path in watched} == before


def test_secret_and_state_paths_are_forbidden_below_the_document_root() -> None:
    common = (API / "activation_common.php").read_text(encoding="utf-8")
    support = (API / "support.php").read_text(encoding="utf-8")
    count = (API / "count.php").read_text(encoding="utf-8")
    stats = (API / "stats.php").read_text(encoding="utf-8")

    assert "activation_path_is_public" in common
    assert "activation_require_private_file" in common
    assert "SOLIDON_STATS_ACCESS_FILE" in stats
    assert "dirname(__DIR__, 2) . '/appdata/stats-access.php'" in stats
    assert "SOLIDON_SUPPORT_RATE_FILE" in support
    assert "sys_get_temp_dir" not in support
    assert "0700" in common
    assert "0700" in count


def test_php_inputs_have_explicit_byte_and_json_depth_limits() -> None:
    support = (API / "support.php").read_text(encoding="utf-8")
    activation = (API / "activation_common.php").read_text(encoding="utf-8")
    count = (API / "count.php").read_text(encoding="utf-8")
    operator = (API / "operator.php").read_text(encoding="utf-8")

    assert "support_request_bytes" in support
    assert "activation_read_json_body" in activation
    assert "count_request_bytes" in count
    assert "operator_request_body" in operator
    assert "JSON_THROW_ON_ERROR" in activation
    assert "activation_has_exact_keys" in activation


def test_stats_reads_months_as_a_bounded_stream() -> None:
    source = (API / "stats.php").read_text(encoding="utf-8")

    assert "STATS_MAX_MONTH_BYTES" in source
    assert "STATS_MAX_ROWS" in source
    assert "STATS_MAX_LINE_BYTES" in source
    assert "const STATS_MAX_ROWS = 16384;" in source
    assert "if ($size > STATS_MAX_MONTH_BYTES)" in source
    assert "$complete = false;" in source
    assert "fgetc($stream)" in source
    assert "Unvollständige Auswertung" in source
    assert "fgets($stream" in source
    assert "foreach (file($path" not in source


def test_activation_document_rejects_unknown_json_fields() -> None:
    php = php_executable()
    common = (API / "activation_common.php").as_posix().replace("'", "\\'")
    code = (
        f"require '{common}';"
        "$document = ['format' => 1, 'kind' => 'activation-request', "
        "'licence' => 'x', 'payload' => 'x', 'signature' => 'x', 'extra' => true];"
        "try { activation_document(json_encode($document), 'activation-request'); exit(2); }"
        "catch (ActivationFailure $problem) { exit(0); }"
    )
    result = subprocess.run([php, "-r", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_stats_access_generator_writes_only_a_private_ignored_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools import make_stats_access as generator

    target = tmp_path / "appdata" / "stats-access.php"
    monkeypatch.setattr(generator, "ROOT", tmp_path)
    monkeypatch.setattr(generator, "WEB_ROOT", tmp_path / "website")
    monkeypatch.setattr(generator, "TARGET", target)
    monkeypatch.setattr(generator, "find_php", lambda: "php")
    monkeypatch.setattr(generator, "ask_password", lambda: "sicheres-passwort")
    monkeypatch.setattr(
        generator,
        "run_php",
        lambda _php, _code, _password, checked=None: (
            "ja"
            if checked is not None
            else "$2y$12$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXY123456"
        ),
    )

    assert generator.main() == 0
    assert target.is_file()
    assert target.parent == tmp_path / "appdata"
    assert "website" not in target.parts
    if os.name == "posix":
        assert target.stat().st_mode & 0o777 == 0o600
        assert target.parent.stat().st_mode & 0o777 == 0o700

    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    source = (ROOT / "tools" / "make_stats_access.py").read_text(encoding="utf-8")
    assert "/appdata/" in ignore
    assert "tools/upload_website.py website/api/.stats-zugang.php" not in source


def test_stats_access_generator_rejects_a_webroot_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools import make_stats_access as generator

    web_root = tmp_path / "website"
    monkeypatch.setattr(generator, "WEB_ROOT", web_root)
    monkeypatch.setattr(generator, "TARGET", web_root / "api" / "secret.php")

    with pytest.raises(SystemExit, match="nicht im Dokumentenstamm"):
        generator.prepare_target()

    assert not web_root.exists()


def test_stats_access_generator_preserves_old_access_on_failed_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools import make_stats_access as generator

    target = tmp_path / "appdata" / "stats-access.php"
    target.parent.mkdir()
    target.write_text("alter-zugang", encoding="utf-8")
    monkeypatch.setattr(generator, "ROOT", tmp_path)
    monkeypatch.setattr(generator, "WEB_ROOT", tmp_path / "website")
    monkeypatch.setattr(generator, "TARGET", target)
    monkeypatch.setattr(generator, "find_php", lambda: "php")
    monkeypatch.setattr(generator, "ask_password", lambda: "sicheres-passwort")
    monkeypatch.setattr("builtins.input", lambda _prompt: "ja")
    monkeypatch.setattr(
        generator,
        "run_php",
        lambda _php, _code, _password, checked=None: (
            "nein"
            if checked is not None
            else "$2y$12$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXY123456"
        ),
    )

    with pytest.raises(SystemExit, match="bisherige Datei bleibt unverändert"):
        generator.main()

    assert target.read_text(encoding="utf-8") == "alter-zugang"


def test_private_php_state_rejects_symlinked_storage_paths(tmp_path: Path) -> None:
    target = tmp_path / "symlink-target"
    target.mkdir()
    link = tmp_path / "state-link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("dieser Prüfstand darf keine Verzeichnis-Symlinks anlegen")

    environment = {
        "SOLIDON_ACTIVATION_RATE_FILE": str(link / "activation-rate.json"),
    }
    with _php_server(tmp_path, environment) as base:
        activation_status, _headers, _body = _request(
            f"{base}/activation.php",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )

    assert activation_status == 503
    assert list(target.iterdir()) == []


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_private_rate_secrets_reject_symlinked_files(tmp_path: Path, link_kind: str) -> None:
    """Ratenstartwerte und Tageswert folgen keinem fremden Dateiverweis."""
    php_extension("sodium")
    activation_target = tmp_path / "activation-secret-target"
    activation_target.write_text("unverändert", encoding="utf-8")
    support_target = tmp_path / "support-secret-target"
    support_target.write_text("unverändert", encoding="utf-8")
    count_target = tmp_path / "count-secret-target"
    count_target.write_text("unverändert", encoding="utf-8")
    stats_dir = tmp_path / "stats"
    stats_dir.mkdir(mode=0o700)
    try:
        for link, target in (
            (tmp_path / "activation-rate.json.key", activation_target),
            (tmp_path / "support-rate.json.key", support_target),
            (stats_dir / "salt.json", count_target),
        ):
            if link_kind == "symlink":
                link.symlink_to(target)
            else:
                os.link(target, link)
    except OSError:
        pytest.skip("dieser Prüfstand darf keine Dateiverweise anlegen")

    prepend = tmp_path / "php-test-mbstring.php"
    prepend.write_text(
        "<?php\n"
        "if (!function_exists('mb_strlen')) {\n"
        "  function mb_strlen(string $value, ?string $encoding = null): int "
        "{ return strlen($value); }\n"
        "  function mb_substr(string $value, int $offset, ?int $length = null): string "
        "{ return substr($value, $offset, $length); }\n"
        "}\n",
        encoding="utf-8",
    )
    boundary = "solidon-secret-test"
    support_body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="message"\r\n\r\n'
        "Pruefung\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="kind"\r\n\r\n'
        "idea\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    with _php_server(tmp_path, prepend=prepend) as base:
        activation_status = _request(
            f"{base}/activation.php",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )[0]
        support_status = _request(
            f"{base}/support.php",
            method="POST",
            data=support_body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )[0]
        count_status = _request(
            f"{base}/count.php",
            method="POST",
            data=urlencode({"p": "/schutz"}).encode("ascii"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://solidon3d.de",
            },
        )[0]

    assert activation_status == support_status == 503
    assert activation_target.read_text(encoding="utf-8") == "unverändert"
    assert count_status == 204
    assert support_target.read_text(encoding="utf-8") == "unverändert"
    assert count_target.read_text(encoding="utf-8") == "unverändert"
    assert list(stats_dir.glob("*.jsonl")) == []


def test_missing_php_is_red_in_the_linux_ci_and_a_skip_elsewhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne PHP überspringen sich 88 Testfälle — und in der CI sah das niemand.

    ``build.yml`` richtete PHP nie ein; der Ubuntu-Runner brachte es zufällig
    mit. Hätte das Runner-Bild es weggelassen, wäre der Lauf grün geblieben
    und kein Endpunkt mehr geprüft worden. Unter ``CI`` auf Linux ist
    fehlendes PHP deshalb ein Fehler; Windows und macOS richten dort keines
    ein und überspringen weiter, wie ein Entwicklerrechner ohne PHP.
    """
    import sys

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setenv("CI", "true")

    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(pytest.fail.Exception, match="PHP fehlt in der CI"):
        php_executable()

    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(pytest.skip.Exception):
        php_executable()

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("CI")
    with pytest.raises(pytest.skip.Exception):
        php_executable()


def _without_redirects(url: str, method: str) -> tuple[int, str]:
    """Fragt eine Adresse, ohne der Weiterleitung zu folgen — sonst antwortet
    am Ende die Zieldatei mit 200, und die Weiterleitung selbst bliebe
    ungeprüft."""

    class _Bleibt(HTTPRedirectHandler):
        def redirect_request(self, *_arguments: object) -> None:
            return None

    request = Request(url, method=method)
    try:
        with build_opener(_Bleibt).open(request, timeout=5) as response:
            return response.status, response.headers.get("Location", "")
    except HTTPError as problem:
        with problem:
            return problem.code, problem.headers.get("Location", "")


def _stats_test_access(tmp_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Privater Prüfzugang mit echtem PHP-Token, ohne Produktivzugang."""
    php = php_executable()
    source = (API / "stats.php").read_text(encoding="utf-8")
    code = (
        "const COOKIE_DAYS = 30;\n"
        + _php_function(source, "signing_key")
        + "\n"
        + _php_function(source, "make_token")
        + "\n$hash = password_hash('nur-lokaler-Test', PASSWORD_DEFAULT);"
        "echo json_encode([$hash, make_token($hash)]);"
    )
    result = subprocess.run([php, "-r", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    password_hash, token = json.loads(result.stdout)
    access = tmp_path / "private-access"
    access.mkdir(mode=0o700)
    path = access / "stats-access.php"
    path.write_text("<?php return ['hash' => " + repr(password_hash) + "];", encoding="ascii")
    _chmod_private(path)
    return {"SOLIDON_STATS_ACCESS_FILE": str(path)}, {"Cookie": f"solidon_stats={token}"}


@pytest.mark.parametrize(
    ("filename", "variable", "valid"),
    [
        ("stats.php", "month", "2026-09"),
        ("support.php", "kindValue", "idea"),
        ("count.php", "agent", "Solidon/0.4.0"),
    ],
)
def test_php_text_patterns_reject_a_final_newline(filename: str, variable: str, valid: str) -> None:
    """PCREs Dollaranker darf hinter dem erlaubten Feld keinen Zeilenrest dulden."""
    source = (API / filename).read_text(encoding="utf-8")
    match = re.search(r"preg_match\('([^']+)', \$" + variable + r"\b", source)
    assert match
    code = (
        'echo json_encode([preg_match($argv[1], $argv[2]), preg_match($argv[1], $argv[2]."\\n")]);'
    )
    result = subprocess.run(
        [php_executable(), "-r", code, match[1], valid],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [1, 0]


def test_update_version_chart_keeps_even_small_counts_visible(tmp_path: Path) -> None:
    stats = tmp_path / "stats"
    stats.mkdir(mode=0o700)
    month = stats / f"{_utc_month(0)}.jsonl"
    row = json.loads(_write_month(month, _utc_month(0)))
    row.update(k="u", v="0.4.0", r="", u="")
    line = json.dumps(row) + "\n"
    row["v"] = "0.3.4"
    month.write_text(line * 1000 + json.dumps(row) + "\n", encoding="ascii")
    environment, headers = _stats_test_access(tmp_path)
    with _php_server(tmp_path, environment) as base:
        status, _headers, page = _request(f"{base}/stats.php", headers=headers)
    assert status == 200 and "</html>" in page
    updates = page.split("<h2>Update-Prüfungen</h2>")[1].split("<h2>Downloads</h2>")[0]
    bars = re.findall(r'<span class="balken" style="width:\s*(\d+)%">', updates)
    assert bars == ["100", "1"], "Beide positiven Werte brauchen einen sichtbaren Balken"


def test_stats_renders_a_numeric_download_filename_completely(tmp_path: Path) -> None:
    docroot = _temporary_docroot(tmp_path)
    (docroot / "dl" / "2026").write_bytes(b"kein echtes Paket")
    stats = tmp_path / "stats"
    stats.mkdir(mode=0o700)
    _write_month(stats / f"{_utc_month(0)}.jsonl", _utc_month(0))
    environment, headers = _stats_test_access(tmp_path)
    with _php_server(tmp_path, environment, docroot=docroot) as base:
        status, _headers, page = _request(f"{base}/stats.php", headers=headers)
    assert status == 200
    assert '<a href="/dl/2026">2026</a>' in page
    assert "</html>" in page, "Ein 200 mit abgebrochenem Rumpf ist keine erfolgreiche Statistik"


def test_update_counting_keeps_no_visitor_identifier_or_referrer(tmp_path: Path) -> None:
    docroot = _temporary_docroot(tmp_path)
    metadata = b'{"version":"0.4.0"}'
    (docroot / "version.json").write_bytes(metadata)
    environment, stats_headers = _stats_test_access(tmp_path)
    month = tmp_path / "stats" / f"{_utc_month(0)}.jsonl"
    with _php_server(tmp_path, environment, docroot=docroot) as base:
        for _attempt in range(2):
            status, headers, body = _request(
                f"{base}/count.php?u=1",
                headers={"User-Agent": "Solidon/0.4.0", "Referer": "https://example.org/private"},
            )
            assert (status, body.encode()) == (200, metadata)
            assert headers["Content-Type"].startswith("application/json")
        rows = [json.loads(line) for line in month.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 2
        assert all(row["u"] == row["r"] == "" for row in rows)
        assert not (tmp_path / "stats" / "salt.json").exists()
        status, _headers, page = _request(
            f"{base}/count.php",
            method="POST",
            data=b"p=%2Ftest",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://solidon3d.de",
            },
        )
        assert status == 204
        rows = [json.loads(line) for line in month.read_text(encoding="utf-8").splitlines()]
        assert rows[-1]["k"] == "p" and len(rows[-1]["u"]) == 8
        assert (tmp_path / "stats" / "salt.json").exists()
        status, _headers, page = _request(f"{base}/stats.php", headers=stats_headers)
        assert status == 200 and "</html>" in page
        updates = page.split("<h2>Update-Prüfungen</h2>")[1].split("<h2>Downloads</h2>")[0]
        assert '<th class="n">Prüfungen</th>' in updates
        assert "Installationen" not in updates
        assert "Installationen (Tag mal Kennzeichen)" not in page
        assert re.search(r"0\.4\.0</td>\s*<td class=\"n\">2</td>", updates)


def test_a_head_request_is_served_and_never_counted(tmp_path: Path) -> None:
    """HEAD holt Kopfzeilen und keinen Byte — also ist es kein Download.

    RFC 9110 verlangt HEAD, wo es GET gibt; ein 405 darauf bricht jeden
    Verfügbarkeitswächter und jedes Prüfwerkzeug. Gezählt werden darf es
    trotzdem nicht: Am 02.09.2026 schrieb eine Release-Nachprüfung mit HEAD
    auf jedes Paket in vierzig Sekunden 38 Downloads in die Statistik — die
    Hälfte des Tageswertes, den der Betreiber liest. Die Weiterleitung bekommt
    sie weiterhin, denn genau die prüft sie.
    """
    # **Der Test legt sein Paket selbst an.** `website/dl/` steht in
    # `.gitignore` — auf dieser Maschine liegen die Pakete früherer Fassungen
    # darin, auf einem frischen Klon und in der CI ist der Ordner leer, und
    # `min()` über ein leeres Glob warf dort (`ValueError`, Tag-Lauf 4,
    # 03.09.2026). `count.php` verlangt eine wirklich vorhandene Datei
    # (`is_file`), also gehört sie zum Testaufbau und nicht zum Fundus.
    docroot = _temporary_docroot(tmp_path)
    downloads = docroot / "dl"
    package = "Solidon3D-Setup-0.0.0-test.exe"
    real = ROOT / "website" / "dl" / package
    existed_before = real.exists()
    month = tmp_path / "stats" / f"{_utc_month(0)}.jsonl"

    try:
        (downloads / package).write_bytes(b"kein echtes Paket")
        assert real.exists() == existed_before, (
            "der Test legt sein Paket im eigenen Dokumentenstamm an, nicht im echten (R33)"
        )
        with _php_server(tmp_path, docroot=docroot) as base:
            head_status, head_target = _without_redirects(f"{base}/count.php?f={package}", "HEAD")
            assert head_status == 302, "ein HEAD auf einen Paketverweis wird bedient"
            assert head_target.endswith(package)
            assert not month.exists(), "und dabei nichts gezählt"

            get_status, get_target = _without_redirects(f"{base}/count.php?f={package}", "GET")
            assert (get_status, get_target) == (302, head_target), "derselbe Weg für beide"
    finally:
        (downloads / package).unlink(missing_ok=True)

    counted = [
        json.loads(line) for line in month.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert [(entry["k"], entry["v"]) for entry in counted] == [("d", package)], (
        "genau der eine GET steht in der Datei, nicht der HEAD davor"
    )


def test_head_reaches_the_statistics_page_like_a_get(tmp_path: Path) -> None:
    """Dieselbe Entscheidung an der Seite selbst: Ein Wächter darf fragen, ob
    sie noch steht, und bekommt dieselbe Antwort wie ein GET — nur ohne Rumpf."""
    php = php_executable("PHP fehlt; der Endpunkttest braucht PHP 7.4+")
    access_dir = tmp_path / "access"
    access_dir.mkdir()
    _chmod_private(access_dir)
    stored = subprocess.run(
        [php, "-r", "echo password_hash('richtig', PASSWORD_DEFAULT);"],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout
    access_file = access_dir / "stats-access.php"
    access_file.write_text("<?php return ['hash' => " + repr(stored) + "];\n", encoding="utf-8")
    _chmod_private(access_file)

    with _php_server(tmp_path, {"SOLIDON_STATS_ACCESS_FILE": str(access_file)}) as base:
        head_status, _head_headers, head_body = _request(f"{base}/stats.php", method="HEAD")
        get_status, get_headers, get_body = _request(f"{base}/stats.php", method="GET")

    assert head_status == get_status == 401, "ohne Anmeldung dieselbe Antwort wie bei GET"
    assert get_headers["Content-Type"].startswith("text/html")
    assert head_body == "", "ein HEAD trägt keinen Rumpf"
    assert "<form" in get_body, "der GET dagegen zeigt die Anmeldung"


def test_a_counter_that_stops_counting_says_so(tmp_path: Path) -> None:
    """Ein Zähler, der nicht mehr zählt, darf nicht schweigen.

    In der Nacht auf den 03.09.2026 hat ein Wartungseingriff die Monatsdatei
    per FTPS ersetzt. Sie kam mit 0644 zurück statt mit den 0600, die
    ``count_stream_is_named_private`` verlangt — und danach nahm ``count.php``
    jede Anfrage an, antwortete mit 302 und schrieb zwei Stunden lang keine
    Zeile. Von außen war das nicht von „niemand war da" zu unterscheiden;
    gefunden wurde es erst, weil jemand die Dateigröße vor und nach einem
    Abruf verglich.

    Die Prüfung selbst bleibt — sie hält eine untergeschobene Datei ab. Aber
    sie schreibt jetzt ins Fehlerprotokoll, und der Betreiber findet in
    Minuten, was ihn sonst Stunden kostet.

    **Ausgelöst wird der Zweig hier über einen Mehrfachverweis, nicht über die
    Rechte.** ``count_stream_is_named_private`` verlangt beides —
    ``nlink === 1`` und, nur auf POSIX, ``mode & 0077 === 0``. Der echte Fall
    waren die Rechte; ein Test darauf übersprünge sich auf Windows und liefe
    auf der Maschine, an der er geschrieben wird, nie. Ein harter Verweis
    trifft denselben Zweig und läuft überall.
    """
    stats = tmp_path / "stats"
    stats.mkdir()
    _chmod_private(stats)
    _chmod_private(tmp_path)
    month = stats / f"{_utc_month(0)}.jsonl"
    month.write_text("", encoding="utf-8")
    _chmod_private(month)
    os.link(month, stats / "zweiter-name.jsonl")
    assert month.stat().st_nlink == 2, "die Voraussetzung des Tests, nicht seine Annahme"

    protokoll = tmp_path / "php-fehler.log"
    docroot = _temporary_docroot(tmp_path)
    downloads = docroot / "dl"
    package = "Solidon3D-Setup-0.0.0-stumm.exe"
    (downloads / package).write_bytes(b"kein echtes Paket")
    try:
        with _php_server(
            tmp_path, {"SOLIDON_STATS_DIR": str(stats)}, error_log=protokoll, docroot=docroot
        ) as base:
            status, _ziel = _without_redirects(f"{base}/count.php?f={package}", "GET")
    finally:
        (downloads / package).unlink(missing_ok=True)

    assert status == 302, "die Weiterleitung bekommt der Besucher trotzdem"
    assert month.read_text(encoding="utf-8") == "", "aber in eine solche Datei wird nicht gezählt"
    gemeldet = protokoll.read_text(encoding="utf-8", errors="replace") if protokoll.exists() else ""
    assert "ist nicht privat" in gemeldet, (
        "und der Ausfall steht im Fehlerprotokoll, statt still zu bleiben: " + gemeldet[-400:]
    )


def test_a_counter_pointed_into_the_document_root_says_so(tmp_path: Path) -> None:
    """Ein verworfener Ablageort ist derselbe stille Ausfall, eine Ebene höher.

    Der Test daneben prüft die Datei, dieser den Ordner. Beide Male nimmt
    ``count.php`` jede Anfrage an, antwortet mit 302 und schreibt nichts —
    von außen nicht von „niemand war da" zu unterscheiden.

    Der Anlass ist gemessen und kein gedachter Fall: Am Abend des 02.09.2026
    lagen in ``website/api/.stats`` auf dem Server vier echte Zählzeilen aus
    sieben Minuten, entstanden unter einer älteren Fassung. Der heutige Code
    lehnt einen solchen Ort ab — er liegt im Dokumentenstamm —, und dass er
    ihn ablehnt, ist richtig: Dort läge pseudonyme Nutzung im öffentlichen
    Baum, geschützt nur durch eine Serverregel, die niemand zugesichert hat.
    Nur schweigen darf die Ablehnung nicht, sonst zählt der Server nach einer
    verstellten Umgebungsvariablen ruhig weiter nichts.

    Geprüft wird deshalb beides: dass im Dokumentenstamm kein Zählordner
    entsteht, und dass der Ausfall im Fehlerprotokoll steht.
    """
    docroot = _temporary_docroot(tmp_path)
    verzeichnis = docroot / "api" / ".stats"
    protokoll = tmp_path / "php-fehler.log"
    downloads = docroot / "dl"
    package = "Solidon3D-Setup-0.0.0-stamm.exe"
    (downloads / package).write_bytes(b"kein echtes Paket")
    try:
        with _php_server(
            tmp_path, {"SOLIDON_STATS_DIR": str(verzeichnis)}, error_log=protokoll, docroot=docroot
        ) as base:
            status, _ziel = _without_redirects(f"{base}/count.php?f={package}", "GET")
        # Vor dem Aufräumen abgelesen — sonst prüft die Zusicherung das finally.
        entstanden = verzeichnis.exists()
    finally:
        (downloads / package).unlink(missing_ok=True)
        shutil.rmtree(verzeichnis, ignore_errors=True)

    assert status == 302, "die Weiterleitung bekommt der Besucher trotzdem"
    assert not entstanden, f"und im Dokumentenstamm entsteht kein Zählordner: {verzeichnis}"
    gemeldet = protokoll.read_text(encoding="utf-8", errors="replace") if protokoll.exists() else ""
    assert "kein brauchbarer Ablageort" in gemeldet, (
        "und der verworfene Ordner steht im Fehlerprotokoll: " + gemeldet[-400:]
    )


# --- die Weiterleitung alter Downloads ---------------------------------------------


def _redirect_target(base: str, name: str) -> tuple[int, str]:
    """Wohin `veraltet.php` einen angefragten Paketnamen schickt.

    Ohne eigenen Aufruf ginge ``urlopen`` der Weiterleitung nach und meldete
    das Ziel als Inhalt — geprüft werden soll aber der ``Location``-Kopf, denn
    genau der ist die Zusage.
    """
    # ``base`` zeigt auf ``/api``; die Weiterleitung liegt daneben. Ein
    # ``..`` im Pfad hilft nicht — der eingebaute PHP-Server löst ihn gegen
    # das Dateisystem auf und lieferte dabei ein echtes Paket aus.
    # **Der Weiterleitung wird nicht gefolgt**, und das ist der ganze Punkt:
    # ``_request`` benutzt ``urlopen``, das eine 302 von sich aus verfolgt —
    # der Lauf landete damit auf dem **echten** Server und lud ein 195-MB-Paket
    # herunter, dessen erste Bytes dann als UTF-8 gelesen wurden. Geprüft wird
    # der ``Location``-Kopf, nicht das, was dahinter liegt.
    root = base.rsplit("/api", 1)[0]

    class _Stay(HTTPRedirectHandler):
        def redirect_request(self, *_args: object, **_kwargs: object) -> None:
            return None

    try:
        with build_opener(_Stay).open(f"{root}/dl/veraltet.php?datei={name}", timeout=5) as answer:
            return answer.status, answer.headers.get("Location", "")
    except HTTPError as problem:
        with problem:
            return problem.code, problem.headers.get("Location", "")


def test_an_old_download_link_leads_to_the_current_one(tmp_path: Path) -> None:
    """Ein Link auf ein altes Paket führt zur aktuellen Fassung derselben Plattform.

    Beim Veröffentlichen werden die vorherigen Pakete vom Server geräumt, und
    damit stirbt jeder Link, der je verschickt wurde. Am 03.09.2026 hat das
    einen Interessenten getroffen: Support-Mail vom Vortag mit einem Link auf
    `Solidon3D-Setup-0.2.2.exe`, einen Tag später eine 404 — und ein toter
    Download liest sich wie ein verschwundenes Produkt.

    **Auf dieselbe Plattform**, nicht pauschal auf die Startseite: Wer eine
    `.pkg` angefragt hat, sitzt an einem Mac und ist mit einer `.exe` nicht
    bedient.
    """
    rules = (ROOT / "website" / ".htaccess").read_text(encoding="utf-8")
    rule = next(line for line in rules.splitlines() if "RewriteRule ^dl/" in line)
    assert "QSA" not in rule, (
        "Eine queryseitige datei darf die Plattform aus dem Pfad nicht ersetzen"
    )
    manifest = json.loads((ROOT / "website" / "version.json").read_text(encoding="utf-8"))
    with _php_server(tmp_path) as base:
        for name, platform in (
            ("Solidon3D-Setup-0.2.2.exe", "windows"),
            ("Solidon3D-0.2.2-x86_64.flatpak", "linux"),
            ("Solidon3D-0.1.1-macos-arm64.pkg", "macos-arm64"),
            ("Solidon3D-0.1.1-macos-x86_64.pkg", "macos-x86_64"),
        ):
            status, target = _redirect_target(base, name)
            assert status == 302, f"{name}: {status}"
            assert target == manifest["packages"][platform]["url"], f"{name}: {target}"


def test_the_download_redirect_never_leaves_our_own_site(tmp_path: Path) -> None:
    """Jede Weiterleitung endet auf unserer eigenen Seite — ohne Ausnahme.

    Eine Weiterleitung ist ein Werkzeug, mit dem sich Vertrauen ausleihen
    lässt: Wer eine offene baut, verschickt fremde Adressen unter unserem
    Namen. Geprüft werden deshalb beide Enden — ein Name, der nach
    Pfadwechsel aussieht, und einer mit angehängter Endung, wie ihn ein
    Downloader anlegt.

    Was sich keiner ausgelieferten Datei zuordnen lässt, geht zur
    Downloadauswahl: tar.gz und zip standen früher im Angebot und werden nicht
    mehr ausgeliefert.
    """
    with _php_server(tmp_path) as base:
        for name in (
            "Solidon3D-0.1.1-linux-x86_64.tar.gz",
            "Solidon3D-..%2F..%2Fetc%2Fpasswd",
            "Solidon3D-Setup-0.2.2.exe.evil",
            "Solidon3D-https:%2F%2Ffremde.example%2Fx.exe",
        ):
            status, target = _redirect_target(base, name)
            assert status == 302, f"{name}: {status}"
            assert target == "https://solidon3d.de/#download", f"{name}: {target}"


def test_every_delivered_kind_finds_its_current_file(tmp_path: Path) -> None:
    """Ein alter Link führt zur Nachfolgerin **derselben** Plattform.

    Hier stand einmal, das AppImage werde „seit 0.2.0 nicht mehr gebaut", und
    der Test darüber schrieb genau das fest: Ein alter AppImage-Link musste
    auf der Downloadauswahl landen. Beides war überholt, seit die Datei zurück
    im Angebot ist — und die Zusicherung hielt den falschen Zustand fest,
    statt ihn zu melden. Gemessen am 04.09.2026 gegen den laufenden Server:
    Windows, Flatpak und beide Macs fanden ihre neue Datei, das AppImage
    landete auf der Auswahl.

    Geprüft wird jede Art, die ``make_download.DELIVERED`` ausliefert, und
    zwar gegen die Fassung, die ``version.json`` **hier** nennt: Der
    PHP-Prüfstand serviert ``website/``, dieselbe Datei liest der Auffangpfad.
    """
    import json

    from tools.make_download import DELIVERED

    manifest = json.loads((ROOT / "website" / "version.json").read_text(encoding="utf-8"))
    fassung = str(manifest["version"])
    alt = "0.2.2"
    assert alt != fassung, "der alte Name muss ein anderer sein als der aktuelle"

    namen = {
        ".exe": "Solidon3D-Setup-{}.exe",
        ".appimage": "Solidon3D-{}-x86_64.AppImage",
        ".flatpak": "Solidon3D-{}-x86_64.flatpak",
        ".pkg": None,  # zwei Architekturen, unten einzeln
    }
    fälle = [
        (muster.format(alt), muster.format(fassung))
        for endung, muster in namen.items()
        if muster is not None
    ]
    fälle += [
        (f"Solidon3D-{alt}-macos-arm64.pkg", f"Solidon3D-{fassung}-macos-arm64.pkg"),
        (f"Solidon3D-{alt}-macos-x86_64.pkg", f"Solidon3D-{fassung}-macos-x86_64.pkg"),
    ]
    assert len(fälle) == len(DELIVERED), (
        f"{len(DELIVERED)} ausgelieferte Arten, aber {len(fälle)} Fälle — "
        "eine neue Art gehört auch hierher"
    )

    # Nur das AppImage prüft im PHP-Weg zusätzlich, ob die versprochene Datei
    # wirklich im Downloadordner liegt. Dieser Ordner ist absichtlich
    # ignoriert: Auf der Release-Maschine liegen dort alte Pakete, in einem
    # frischen Klon und in der CI nicht. Der Prüfstand legt deshalb genau das
    # aktuelle AppImage selbst an und räumt nur seinen eigenen Platzhalter
    # wieder weg.
    appimage = ROOT / "website" / "dl" / f"Solidon3D-{fassung}-x86_64.AppImage"
    existed = appimage.is_file()
    if not existed:
        appimage.write_bytes(b"kein echtes Paket")
    try:
        with _php_server(tmp_path) as base:
            for angefragt, erwartet in fälle:
                status, target = _redirect_target(base, angefragt)
                assert status == 302, f"{angefragt}: {status}"
                assert target == f"https://solidon3d.de/dl/{erwartet}", f"{angefragt}: {target}"
    finally:
        if not existed:
            appimage.unlink(missing_ok=True)


def test_a_numeric_referrer_host_can_neither_be_stored_nor_break_the_report() -> None:
    """Ein rein numerischer Referrer-Host legte die Statistik still lahm.

    ``count.php`` schrieb ihn, weil die Zeichenprüfung Ziffern erlaubt;
    ``stats.php`` trägt den Wert dann als **Array-Schlüssel**, und PHP wandelt
    einen kanonischen Dezimaltext still in einen ``int``. Unter
    ``declare(strict_types=1)`` warf ``e()`` damit mitten im Rendern einen
    ``TypeError``: Die Seite brach ab der Herkunftstabelle ab, mit Status 200
    und ohne Fehlermeldung, und der Wartungslauf räumte die Zeile nicht weg
    (Sicherheitsdurchsicht 04.09.2026).

    **Geprüft wird der Quelltext, nicht das Verhalten** — diese Datei hat für
    die öffentlichen Endpunkte keinen HTTP-Aufbau, und ``stats.php`` lässt
    sich nicht einbinden, ohne loszulaufen. Die Zusicherung ist damit
    schwächer als ein Lauf, aber keine leere: Sie wird rot, wenn jemand den
    Lookahead entfernt oder die Signatur zurückdreht.
    """
    counter = (API / "count.php").read_text(encoding="utf-8")
    stats = (API / "stats.php").read_text(encoding="utf-8")

    # Die Schreibseite: mindestens ein Buchstabe muss im Hostnamen stehen.
    assert "'/^(?=.*[a-z])[a-z0-9.-]{1,80}$/D'" in counter, (
        "der Hostname braucht einen Buchstaben, sonst ist er als Schlüssel eine Zahl"
    )

    # Die Leseseite als Gegenprobe: ``e()`` nimmt auch eine Ganzzahl an.
    assert "function e(string|int $text): string" in stats, (
        "sechs Aufrufstellen übergeben einen Array-Schlüssel, der ein int sein kann"
    )
    assert "htmlspecialchars((string) $text" in stats, "und maskiert wird weiterhin"


def test_an_attachment_that_php_rejected_is_not_sent_as_a_success(tmp_path: Path) -> None:
    """Gesamtreview 05.09.2026, B-13: Ein Anhang über ``upload_max_filesize``
    kommt mit ``UPLOAD_ERR_INI_SIZE`` und null Bytes an; ein ``continue`` ließ
    ihn still weg, und die Rückmeldung ging ohne ihn als Erfolg hinaus. Die
    Grenze steht hier bewusst bei einem Kilobyte, damit kein Test Megabytes
    schickt; gesendet wird nichts, weil die Antwort vor dem Versand fällt."""
    prepend = tmp_path / "php-test-extensions.php"
    prepend.write_text(
        "<?php\n"
        "if (!function_exists('mb_strlen')) {\n"
        "  function mb_strlen(string $value, ?string $encoding = null): int "
        "{ return strlen($value); }\n"
        "  function mb_substr(string $value, int $offset, ?int $length = null): string "
        "{ return substr($value, $offset, $length); }\n"
        "}\n",
        encoding="utf-8",
    )
    boundary = "solidon-attachment-test"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="message"\r\n\r\n'
        "Pruefung\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="kind"\r\n\r\n'
        "idea\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="anhang"; filename="gross.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n" + "x" * 4096 + "\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    with _php_server(tmp_path, prepend=prepend, ini={"upload_max_filesize": "1K"}) as base:
        status, _headers, text = _request(
            f"{base}/support.php",
            method="POST",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )

    assert status == 413, text
    assert json.loads(text)["ok"] is False


def test_the_test_server_never_lets_a_mail_out() -> None:
    """R34: Der Rate-Limit-Test schickt eine gültige Rückmeldung durch den
    echten Endpunkt, und der ruft ``mail()``. Mit einem eingerichteten
    Transport wäre sie beim Support angekommen. Der Prüfserver zeigt deshalb
    auf einen Transport, den es nicht gibt."""
    command = _php_command("php", 1234)

    flags = " ".join(command)
    assert "sendmail_path=/nonexistent/" in flags
    assert "SMTP=127.0.0.1" in flags and "smtp_port=1" in flags
    assert command[-2:] == ["-t", "website"]
    assert _php_command("php", 1, docroot=Path("anderswo"))[-1] == "anderswo"


@pytest.mark.parametrize("lost_temporary", [False, True])
def test_a_lost_upload_is_rejected_before_the_support_mail(
    tmp_path: Path,
    lost_temporary: bool,
) -> None:
    """Auch nach erfolgreicher PHP-Annahme muss der wirkliche Anhang lesbar bleiben."""
    # support.php misst Nachrichten- und Feldlängen mit mb_strlen; ohne mbstring
    # antwortet PHP mit einem Fatal statt mit 400, und der Test fragte gar nicht
    # nach dem Anhang. Wie bei sodium: lokal überspringen und sagen, was fehlt —
    # in der CI, die die Erweiterung einrichtet, bleibt es ein roter Test.
    php_extension("mbstring")
    prepend = tmp_path / "upload-lost.php"
    mutation = (
        "unlink($_FILES['anhang']['tmp_name']);"
        if lost_temporary
        else "$_FILES['anhang']['tmp_name'] = '';"
    )
    prepend.write_text("<?php\n" + mutation, encoding="utf-8")
    boundary = "solidon-lost-upload"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="message"\r\n\r\n'
        "Prüfung\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="kind"\r\n\r\n'
        "idea\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="anhang"; filename="test.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        "vollständiger Inhalt\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    with _php_server(tmp_path, prepend=prepend) as base:
        status, _headers, text = _request(
            f"{base}/support.php",
            method="POST",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
    assert status == 400, text
    assert json.loads(text)["ok"] is False


def _day_zone_line() -> str:
    """Die eine Zeile aus day_zone.php, die count.php und stats.php teilen."""
    source = (API / "day_zone.php").read_text(encoding="utf-8")
    return next(line for line in source.splitlines() if line.startswith("const DAY_ZONE"))


def test_visitor_identity_rotates_at_the_displayed_day_boundary(tmp_path: Path) -> None:
    """UTC-Mitternacht innerhalb desselben Anzeigetages zählt keinen zweiten Besucher."""
    php = php_executable()
    counter = (API / "count.php").read_text(encoding="utf-8")
    stats = (API / "stats.php").read_text(encoding="utf-8")
    zone = next(line for line in stats.splitlines() if line.startswith("const DISPLAY_ZONE"))
    # Seit dem 06.09.2026 zeigt DISPLAY_ZONE auf DAY_ZONE aus day_zone.php; die Probe
    # braucht beide Zeilen, sonst kennt sie den Namen nicht.
    day_zone = _day_zone_line()
    moments = [
        "2026-09-04T23:59:00Z",
        "2026-09-05T00:01:00Z",
        "2026-09-05T21:59:00Z",
        "2026-09-05T22:01:00Z",
        "2026-01-05T22:59:00Z",
        "2026-01-05T23:01:00Z",
    ]
    probe = tmp_path / "days.php"
    probe.write_text(
        "<?php\n"
        + day_zone
        + "\n"
        + zone
        + "\n"
        + _php_function(counter, "count_day")
        + "\n"
        + "$answer = []; foreach (json_decode($argv[1]) as $text) { "
        + "$at = new DateTimeImmutable($text); $answer[] = [count_day($at), "
        + "$at->setTimezone(new DateTimeZone(DISPLAY_ZONE))->format('Y-m-d')]; } "
        + "echo json_encode($answer);",
        encoding="utf-8",
    )
    result = subprocess.run(
        [php, str(probe), json.dumps(moments)], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
    days = json.loads(result.stdout)
    assert all(counter == shown for counter, shown in days)
    assert days[0][0] == days[1][0] == days[2][0]
    assert days[2][0] != days[3][0]
    assert days[4][0] != days[5][0]


def test_the_month_comparison_carries_its_completeness(tmp_path: Path) -> None:
    """Gesamtreview 05.09.2026, R30: ``entries()`` kennt seine Grenze von
    16.384 Zeilen und sagt sie über ``$complete``; ``month_totals()`` warf das
    weg, und ein zu großer Monat stand im Vergleich als vollständige Summe."""
    php = php_executable()
    source = (API / "stats.php").read_text(encoding="utf-8")
    constants = (
        _day_zone_line()
        + "\n"
        + "\n".join(
            line
            for line in source.splitlines()
            if line.startswith(("const STATS_MAX_", "const DISPLAY_ZONE"))
        )
    )
    probe = tmp_path / "probe.php"
    probe.write_text(
        "<?php\ndeclare(strict_types=1);\n"
        + constants
        + "\n"
        + _php_function(source, "entries")
        + "\n"
        + _php_function(source, "visitors_per_day")
        + "\n"
        + _php_function(source, "month_totals")
        + "\necho json_encode(month_totals($argv[1], '2026-08'));\n",
        encoding="utf-8",
    )
    row = {"t": "2026-08-15T12:00:00+00:00", "k": "p", "v": "/", "r": "", "u": "12345678"}
    (tmp_path / "2026-08.jsonl").write_text((json.dumps(row) + "\n") * 16385, encoding="utf-8")

    result = subprocess.run(
        [php, str(probe), str(tmp_path)], capture_output=True, text=True, timeout=60
    )

    assert result.returncode == 0, result.stdout + result.stderr
    totals = json.loads(result.stdout)
    assert totals["pages"] == 16384, "bis zur Grenze gezählt"
    assert totals["complete"] is False, "und die Grenze reist mit"


@pytest.mark.parametrize(
    "case, expected",
    [
        ("missing", "private_file_missing"),
        ("relative", "path_not_absolute"),
        ("invalid", "seed_invalid"),
    ],
)
def test_activation_configuration_has_private_diagnostics(
    tmp_path: Path, case: str, expected: str
) -> None:
    from tools import check_activation

    secret = "private-fixture-do-not-print"
    path = tmp_path / "private-signature.seed"
    if case == "invalid":
        path.write_text(secret, encoding="ascii")
        _chmod_private(path)
    log = tmp_path / "private-errors.log"
    _chmod_private(tmp_path)
    with _php_server(
        tmp_path,
        {"SOLIDON_ACTIVATION_SEED_FILE": "relative.seed" if case == "relative" else str(path)},
        error_log=log,
    ) as base:
        status, _headers, body = _request(f"{base}/activation-health.php")
        ready, message = check_activation.check(f"{base}/activation-health.php")
        assert not ready
        assert "PHP-Fehlerprotokoll" in message
    assert status == 503
    assert json.loads(body)["code"] == "service_unavailable"
    assert expected not in body
    diagnostic = log.read_text(encoding="utf-8") if log.exists() else ""
    assert expected in diagnostic
    assert secret not in diagnostic + body
    assert str(path) not in diagnostic + body


@pytest.mark.parametrize(
    "case, expected",
    [
        ("missing", "access_file_missing"),
        ("empty", "access_hash_missing"),
        ("invalid", "access_hash_invalid"),
    ],
)
def test_stats_configuration_has_private_diagnostics(
    tmp_path: Path, case: str, expected: str
) -> None:
    secret = "private-fixture-do-not-print"
    path = tmp_path / "private-access.php"
    if case != "missing":
        value = secret if case == "invalid" else ""
        path.write_text("<?php return ['hash' => '" + value + "'];", encoding="ascii")
        _chmod_private(path)
    log = tmp_path / "private-errors.log"
    _chmod_private(tmp_path)
    with _php_server(tmp_path, {"SOLIDON_STATS_ACCESS_FILE": str(path)}, error_log=log) as base:
        status, _headers, body = _request(f"{base}/stats.php")
    assert status == 503
    assert body == "Diese Seite ist vorübergehend nicht verfügbar.\n"
    diagnostic = log.read_text(encoding="utf-8") if log.exists() else ""
    assert expected in diagnostic
    assert secret not in diagnostic + body
    assert str(path) not in diagnostic + body


@pytest.mark.parametrize("scope", ["client", "global"])
def test_activation_burst_limits_have_distinct_codes(tmp_path: Path, scope: str) -> None:
    state_file = tmp_path / "activation-rate.json"
    _chmod_private(tmp_path)
    if scope == "global":
        state_file.write_text(json.dumps({"issue:global": [int(time.time())] * 3000}))
        _chmod_private(state_file)
    headers = {"Content-Type": "application/json"}
    with _php_server(tmp_path) as base:
        if scope == "client":
            for _attempt in range(30):
                status, _, _ = _request(
                    f"{base}/activation.php", method="POST", data=b"{}", headers=headers
                )
                assert status == 400
        before = state_file.read_bytes()
        status, _, body = _request(
            f"{base}/activation.php", method="POST", data=b"{}", headers=headers
        )
    assert status == 429
    assert json.loads(body)["code"] == f"rate_limit_{scope}"
    assert state_file.read_bytes() == before
