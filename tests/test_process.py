"""Die gemeinsame Sicherheitsgrenze für externe Prozesse."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from app.core import process


def test_trusted_environment_drops_secrets_and_loader_changes() -> None:
    source = {
        "PATH": "Programme",
        "TEMP": "Zwischenablage",
        "LANG": "de_DE.UTF-8",
        "OPENAI_API_KEY": "geheim",
        "HTTPS_PROXY": "http://name:passwort@example.invalid",
        "PYTHONPATH": "fremder-code",
        "LD_PRELOAD": "fremde-bibliothek",
    }

    answer = process.trusted_environment(source)

    assert answer == {
        "PATH": "Programme",
        "TEMP": "Zwischenablage",
        "LANG": "de_DE.UTF-8",
    }


def test_bounded_environment_drops_gui_session_capabilities() -> None:
    source = {
        "PATH": "Programme",
        "DISPLAY": ":0",
        "WAYLAND_DISPLAY": "wayland-0",
        "XAUTHORITY": "cookie",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=sitzung",
        "XDG_RUNTIME_DIR": "/run/user/1000",
    }

    assert process.trusted_environment(source) == {"PATH": "Programme"}
    assert process.trusted_environment(source, graphical=True) == source


def test_limited_process_gets_explicit_cwd_without_application_secrets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SOLIDON_PROCESS_SECRET", "nicht-weitergeben")
    script = (
        "import os; "
        "from pathlib import Path; "
        "print(Path.cwd()); "
        "print(os.environ.get('SOLIDON_PROCESS_SECRET', 'fehlt'))"
    )

    answer = process.run_limited(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        timeout=5.0,
        output_limit=4096,
    )

    lines = answer.stdout.decode("utf-8").strip().splitlines()
    assert Path(lines[0]).resolve() == tmp_path.resolve()
    assert lines[1] == "fehlt"


def test_limited_process_stops_at_the_combined_output_limit(tmp_path: Path) -> None:
    script = "import os, time; os.write(1, b'x' * 700); os.write(2, b'y' * 700); time.sleep(5)"
    begun = time.monotonic()

    with pytest.raises(process.ProcessOutputLimitExceeded):
        process.run_limited(
            [sys.executable, "-c", script],
            cwd=tmp_path,
            timeout=4.0,
            output_limit=1024,
        )

    assert time.monotonic() - begun < 3.0


def test_exact_output_limit_is_still_accepted(tmp_path: Path) -> None:
    answer = process.run_limited(
        [sys.executable, "-c", "import os; os.write(1, b'x' * 1024)"],
        cwd=tmp_path,
        timeout=5.0,
        output_limit=1024,
    )

    assert len(answer.stdout) == 1024


def test_timeout_stops_the_descendant_process_too(tmp_path: Path) -> None:
    marker = tmp_path / "descendant-finished"
    child = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).touch()"
    parent = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
        "time.sleep(30)"
    )

    with pytest.raises(subprocess.TimeoutExpired):
        process.run_limited(
            [sys.executable, "-c", parent],
            cwd=tmp_path,
            timeout=0.2,
            output_limit=4096,
        )

    time.sleep(1.3)
    assert not marker.exists(), "ein Nachkomme darf den abgebrochenen Lauf nicht überleben"


def test_a_successful_parent_must_not_leave_a_descendant_running(tmp_path: Path) -> None:
    marker = tmp_path / "entkommener-nachkomme"
    child = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).touch()"
    parent = f"import subprocess, sys; subprocess.Popen([sys.executable, '-c', {child!r}])"

    answer = process.run_limited(
        [sys.executable, "-c", parent],
        cwd=tmp_path,
        timeout=5.0,
        output_limit=4096,
    )

    assert answer.returncode == 0
    time.sleep(1.3)
    assert not marker.exists(), "auch ein erfolgreicher Lauf darf keine Kinder zurücklassen"


@pytest.mark.skipif(os.name != "nt", reason="Windows-Jobobjekt")
def test_a_windows_child_cannot_escape_into_a_detached_process_group(tmp_path: Path) -> None:
    marker = tmp_path / "entkommener-windows-nachkomme"
    child = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).touch()"
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    parent = (
        "import subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}], creationflags={flags})"
    )

    answer = process.run_limited(
        [sys.executable, "-c", parent],
        cwd=tmp_path,
        timeout=5.0,
        output_limit=4096,
    )

    assert answer.returncode == 0
    time.sleep(1.3)
    assert not marker.exists(), "das Jobobjekt muss auch losgelöste Gruppen schließen"


def test_streaming_process_keeps_utf8_and_carriage_return_lines(tmp_path: Path) -> None:
    script = (
        "import os; "
        "os.write(1, 'größer\\rhalb\\n'.encode('utf-8')); "
        "os.write(2, 'fertig\\n'.encode('utf-8'))"
    )
    seen: list[str] = []

    answer = process.run_stream_limited(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        timeout=5.0,
        output_limit=4096,
        on_line=seen.append,
    )

    assert answer.returncode == 0
    assert seen == ["größer", "halb", "fertig"]


def test_a_blocking_stream_callback_cannot_disable_the_total_timeout(tmp_path: Path) -> None:
    release = threading.Event()
    begun = time.monotonic()

    with pytest.raises(subprocess.TimeoutExpired):
        process.run_stream_limited(
            [sys.executable, "-c", "print('bereit', flush=True); import time; time.sleep(30)"],
            cwd=tmp_path,
            timeout=0.2,
            output_limit=4096,
            on_line=lambda _line: release.wait(30),
        )

    release.set()
    assert time.monotonic() - begun < 3.0


def test_a_blocking_stream_callback_cannot_disable_cancellation(tmp_path: Path) -> None:
    release = threading.Event()
    begun = time.monotonic()

    with pytest.raises(process.ProcessCancelled):
        process.run_stream_limited(
            [sys.executable, "-c", "print('bereit', flush=True); import time; time.sleep(30)"],
            cwd=tmp_path,
            timeout=10.0,
            output_limit=4096,
            on_line=lambda _line: release.wait(30),
            cancelled=lambda: time.monotonic() - begun >= 0.2,
        )

    release.set()
    assert time.monotonic() - begun < 3.0


def test_limited_process_enforces_the_memory_budget(tmp_path: Path) -> None:
    script = "chunks = []\nwhile True:\n    chunks.append(bytearray(2 * 1024 * 1024))"

    answer = process.run_limited(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        timeout=10.0,
        output_limit=4096,
        memory_limit=64 * 1024 * 1024,
    )

    assert answer.returncode != 0


def test_detached_options_are_closed_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SOLIDON_PROCESS_SECRET", "nicht-weitergeben")
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=sitzung")

    options = process.detached_process_options(cwd=tmp_path)

    assert options["cwd"] == tmp_path
    assert options["stdin"] is subprocess.DEVNULL
    assert options["stdout"] is subprocess.DEVNULL
    assert options["stderr"] is subprocess.DEVNULL
    assert options["close_fds"] is True
    assert "SOLIDON_PROCESS_SECRET" not in options["env"]
    assert "DBUS_SESSION_BUS_ADDRESS" not in options["env"]
    if os.name == "nt":
        assert options["creationflags"] & subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        assert options["start_new_session"] is True


def test_detached_graphical_process_gets_the_session_only_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=sitzung")

    options = process.detached_process_options(graphical=True)

    assert options["env"]["DBUS_SESSION_BUS_ADDRESS"] == "unix:path=sitzung"


def test_windows_process_group_options_cover_group_detach_and_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(process.sys, "platform", "win32")
    monkeypatch.setattr(process.subprocess, "CREATE_NEW_PROCESS_GROUP", 1, raising=False)
    monkeypatch.setattr(process.subprocess, "DETACHED_PROCESS", 2, raising=False)
    monkeypatch.setattr(process.subprocess, "CREATE_NO_WINDOW", 4, raising=False)

    options = process.process_group_options(detached=True, no_window=True)

    assert options == {"close_fds": True, "creationflags": 7}

    suspended = process.process_group_options(suspended=True)
    assert suspended["creationflags"] & process._WINDOWS_CREATE_SUSPENDED


def test_posix_process_group_options_start_a_new_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(process.sys, "platform", "linux")

    options = process.process_group_options(detached=True, no_window=True)

    assert options == {"close_fds": True, "start_new_session": True}
