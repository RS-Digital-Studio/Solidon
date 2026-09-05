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
    """Schlüssel, Suchpfade und Loader-Eingriffe bleiben hier.

    **Der Proxy reist seit dem 02.09.2026 mit, seine Zugangsdaten nicht.** Ohne
    ihn erreicht im Firmennetz weder ``pip`` noch ``winget`` seinen Server, und
    die Nachinstallation endet an einem Zeitlimit ohne Grund. Die Zusage dieses
    Moduls gilt den *Zugangsdaten*, und die hält: ``name:passwort`` wird aus der
    Adresse geschnitten, bevor sie einen Unterprozess erreicht.
    """
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
        "HTTPS_PROXY": "http://example.invalid",
    }
    assert "passwort" not in str(answer)


def test_the_way_out_of_a_company_network_travels_without_its_credentials() -> None:
    """Proxy, Zertifikatssatz und Paketquelle reisen mit — ohne Zugangsdaten.

    ``pip`` und ``winget`` laufen als Unterprozess mit genau dieser Umgebung.
    Fehlten die Namen, lief die Nachinstallation (§36) in einem Firmennetz in
    ein Zeitlimit, und die Meldung nannte den Grund nicht.

    Zugangsdaten in einer Adresse sind der Fall, für den der Schnitt da ist:
    Ein Unterprozess trägt seine Umgebung in die Prozessliste, in seinen
    Absturzbericht und in sein eigenes Protokoll.
    """
    source = {
        "HTTP_PROXY": "http://name:passwort@proxy.example.invalid:8080",
        "https_proxy": "http://name:passwort@proxy.example.invalid:8080",
        "NO_PROXY": "localhost,127.0.0.1",
        "SSL_CERT_FILE": "/etc/ssl/firma.pem",
        "REQUESTS_CA_BUNDLE": "/etc/ssl/firma.pem",
        "PIP_INDEX_URL": "https://leser:geheim@pakete.example.invalid/simple",
    }

    answer = process.trusted_environment(source)

    assert answer == {
        "HTTP_PROXY": "http://proxy.example.invalid:8080",
        "https_proxy": "http://proxy.example.invalid:8080",
        "NO_PROXY": "localhost,127.0.0.1",
        "SSL_CERT_FILE": "/etc/ssl/firma.pem",
        "REQUESTS_CA_BUNDLE": "/etc/ssl/firma.pem",
        "PIP_INDEX_URL": "https://pakete.example.invalid/simple",
    }
    for secret in ("passwort", "geheim"):
        assert secret not in str(answer)


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


def test_the_sandbox_bridge_travels_out_of_the_own_flatpak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Im eigenen Flatpak reisen Busadresse und Laufzeitverzeichnis mit.

    ``discover.on_host`` legt dort vor jeden Start ein ``flatpak-spawn --host``,
    und das spricht über den Sitzungsbus mit dem Flatpak-Dienst. Beide Namen
    standen nur in den grafischen Befugnissen — die bekommt ein begrenzter Lauf
    nicht, und genau begrenzte Läufe starten Slicer, Suchläufe und
    Nachinstallation. Im Linux-Paket kam damit keiner von ihnen heraus.

    Der Displayserver bleibt trotzdem draußen: Die Brücke ist keine Oberfläche.
    """
    from app.core import discover

    source = {
        "PATH": "Programme",
        "DISPLAY": ":0",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=sitzung",
        "XDG_RUNTIME_DIR": "/run/user/1000",
    }
    monkeypatch.setattr(discover, "in_flatpak", lambda: True)

    assert process.trusted_environment(source) == {
        "PATH": "Programme",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=sitzung",
        "XDG_RUNTIME_DIR": "/run/user/1000",
    }


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


def test_no_child_gets_a_memory_limit_from_us(tmp_path: Path) -> None:
    """Ein Kind darf so viel Speicher nehmen, wie der Rechner hergibt.

    **Die Grenze ist am 03.09.2026 überall gefallen** (Entscheidung Robert).
    Bis 0.2.2 gab es keine; die am 02.09. eingebaute deckelte jeden fremden
    Prozess auf vier GiB und war auf dem Mac tödlich — ``RLIMIT_AS`` lehnt der
    Darwin-Kern ab, und das Kind startete gar nicht. Der Slicer gehört dem
    Nutzer; wie viel Speicher er nimmt, entscheidet nicht Solidon.

    Geprüft wird die Zusage und nicht ihre Abwesenheit: 96 MiB in einem Zug,
    was unter jeder früheren Grenze gelegen hätte, kommen sauber zurück.
    """
    script = "import sys; block = bytearray(96 * 1024 * 1024); sys.exit(0 if block else 1)"

    answer = process.run_limited(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        timeout=30.0,
        output_limit=4096,
    )

    assert answer.returncode == 0, "der Kindprozess wurde an einer Speichergrenze angehalten"


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


def test_no_start_option_prepares_a_memory_limit() -> None:
    """Kein Startweg legt mehr eine Speichergrenze an — auf keiner Plattform.

    Der Wächter zur Entscheidung vom 03.09.2026: ``preexec_fn`` war der Griff,
    mit dem die Grenze gesetzt wurde, und genau er ließ auf dem Mac kein Kind
    mehr starten. Wer sie wieder einbaut, macht diesen Test rot und liest den
    Grund im Register.
    """
    for options in (
        process.process_group_options(no_window=True, suspended=True),
        process.process_group_options(detached=True, no_window=True),
    ):
        assert "preexec_fn" not in options, options
    assert not hasattr(process, "_memory_options"), "die Speichergrenze ist wieder da"
    assert not hasattr(process, "DEFAULT_MEMORY_LIMIT"), "die Speichergrenze ist wieder da"


def test_a_group_that_outlives_its_parent_is_killed_after_the_grace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gesamtreview 05.09.2026, CORE-23: Auf POSIX kehrte
    ``terminate_process_tree`` zurück, sobald der Elternprozess weg war —
    ein Nachkomme, der SIGTERM abfängt, lebte danach unbegrenzt weiter."""
    alive = iter([True, True, False])
    killed: list[tuple[int, bool]] = []
    monkeypatch.setattr(process, "_group_alive", lambda _pid: next(alive, False))
    monkeypatch.setattr(
        process, "_kill_process_group", lambda pid, *, force: killed.append((pid, force))
    )
    monkeypatch.setattr(process.time, "sleep", lambda _seconds: None)
    clock = iter([0.0, 0.0, 10.0])
    monkeypatch.setattr(process.time, "monotonic", lambda: next(clock, 10.0))

    process._finish_process_group(4711, 1.0)

    assert killed == [(4711, True)], "wer die Schonfrist übersteht, bekommt SIGKILL"


def test_the_posix_teardown_waits_for_the_group_after_the_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Elternprozess ist nach dem höflichen Signal sofort weg — die
    Gruppe wird danach trotzdem abgewartet und nicht vergessen."""
    monkeypatch.setattr(process.os, "name", "posix")
    finished: list[int] = []
    monkeypatch.setattr(process, "_kill_process_group", lambda _pid, *, force: None)
    monkeypatch.setattr(process, "_finish_process_group", lambda pid, _grace: finished.append(pid))

    class Parent:
        pid = 4711

        def wait(self, timeout: float | None = None) -> int:
            return 0

    process.terminate_process_tree(Parent(), grace_seconds=0.5)  # type: ignore[arg-type]

    assert finished == [4711]
