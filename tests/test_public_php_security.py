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
from urllib.request import Request, urlopen

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
    "operator.php",
    "count.php",
    "stats.php",
)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextlib.contextmanager
def _php_server(
    tmp_path: Path,
    extra_environment: dict[str, str] | None = None,
    *,
    prepend: Path | None = None,
) -> Iterator[str]:
    php = php_executable("PHP fehlt; der Endpunkttest braucht PHP 7.4+")
    port = _free_port()
    environment = os.environ.copy()
    environment["SOLIDON_STATS_DIR"] = str(tmp_path / "stats")
    environment["SOLIDON_ACTIVATION_RATE_FILE"] = str(tmp_path / "activation-rate.json")
    environment["SOLIDON_SUPPORT_RATE_FILE"] = str(tmp_path / "support-rate.json")
    if extra_environment:
        environment.update(extra_environment)
    command = [php]
    if prepend is not None:
        command.extend(["-d", f"auto_prepend_file={prepend}"])
    command.extend(["-S", f"127.0.0.1:{port}", "-t", "website"])
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


def test_activation_common_is_not_a_public_blank_endpoint(tmp_path: Path) -> None:
    with _php_server(tmp_path) as base:
        status, _headers, _body = _request(f"{base}/activation_common.php")

    assert status == 404


@pytest.mark.parametrize(
    ("endpoint", "method", "allow"),
    [
        ("support.php", "GET", "POST"),
        ("activation.php", "GET", "POST"),
        ("deactivation.php", "GET", "POST"),
        ("activation-health.php", "POST", "GET"),
        ("operator.php", "GET", "POST"),
        ("count.php", "PUT", "GET, POST"),
        ("stats.php", "PUT", "GET, POST"),
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

    seed = bytes(range(32))
    seed_file = tmp_path / "activation.seed"
    seed_file.write_text(seed.hex(), encoding="ascii")
    seed_file.chmod(0o600)
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
        "SOLIDON_ACTIVATION_SEED_FILE": str(seed_file),
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
        "}\n"
        "if (!function_exists('sodium_crypto_sign_seed_keypair')) {\n"
        "  define('SODIUM_CRYPTO_SIGN_SEEDBYTES', 32);\n"
        "  function sodium_crypto_sign_seed_keypair(string $seed): string { return $seed; }\n"
        "  function sodium_crypto_sign_publickey(string $pair): string "
        "{ return hash('sha256', $pair, true); }\n"
        "}\n",
        encoding="utf-8",
    )
    # **Den erwarteten Schlüssel rechnet PHP, nicht Python.** Hier stand
    # ``hashlib.sha256(seed)`` — das ist der Ersatz aus dem Prepend darüber,
    # und der greift nur, wo sodium *fehlt*. Mit echtem sodium (in der
    # Linux-CI, und lokal sobald die Erweiterung geladen ist) rechnet der
    # Server Ed25519, der Vergleich in ``activation_seed`` scheitert mit 503,
    # und die Ratenbegrenzung kommt nie an die Reihe: Der rohe Hash blieb in
    # der Datei liegen, und dieser Test war rot, ohne dass am Endpunkt etwas
    # falsch war. Dasselbe Prepend, derselbe Rechenweg — dann ist es egal,
    # welche Antwort die Umgebung gibt.
    # ``auto_prepend_file`` gilt für Skripte, nicht für ``-r`` — deshalb das
    # ``require`` im Code selbst.
    environment["SOLIDON_ACTIVATION_TEST_PUBLIC_KEY"] = subprocess.run(
        [
            php,
            "-r",
            "require $argv[2]; echo bin2hex(sodium_crypto_sign_publickey("
            "sodium_crypto_sign_seed_keypair(hex2bin($argv[1]))));",
            seed.hex(),
            str(prepend),
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout.strip()
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

    with _php_server(tmp_path) as base:
        status, _headers, _body = _request(
            f"{base}/count.php", method="POST", data=body, headers=headers
        )

    assert status == 429
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


def test_private_rate_secrets_reject_symlinked_files(tmp_path: Path) -> None:
    """Support-Schlüssel und Tageswert folgen keinem fremden Dateiverweis."""
    support_target = tmp_path / "support-secret-target"
    support_target.write_text("unverändert", encoding="utf-8")
    count_target = tmp_path / "count-secret-target"
    count_target.write_text("unverändert", encoding="utf-8")
    stats_dir = tmp_path / "stats"
    stats_dir.mkdir(mode=0o700)
    try:
        (tmp_path / "support-rate.json.key").symlink_to(support_target)
        (stats_dir / "salt.json").symlink_to(count_target)
    except OSError:
        pytest.skip("dieser Prüfstand darf keine Datei-Symlinks anlegen")

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

    assert support_status == 503
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
