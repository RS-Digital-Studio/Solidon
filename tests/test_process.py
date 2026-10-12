"""Die gemeinsame Sicherheitsgrenze für externe Prozesse."""

from __future__ import annotations

import ast
import contextlib
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from app.core import process

#: Nur eine Hängergrenze, keine Zeitaussage: Wo ein Fall die Zeitgrenze von
#: ``run_limited`` nicht selbst prüft, darf sie ihn nie entscheiden. Ein frischer
#: Interpreter braucht ruhig 0,2 s bis zu seiner ersten Ausgabe, unter sechsfach
#: überbuchten Kernen bis 13 s (RM-635); feste 3 bis 5 s rissen im vollen Tor
#: neben anderen Sitzungen. Was ein Fall über Zeit sagt, misst er ab dem Zustand,
#: um den es geht (:func:`_clock_held_until`, Ereignisse, Prozesskennungen).
HANG_GUARD = 120.0

#: So lange schläft ein Kind, das nicht von selbst fertig werden soll: länger als
#: die Hängergrenze, und ein Fehler wird trotzdem nach Minuten rot.
SLEEP = 2 * HANG_GUARD

#: Wie schnell ein Lauf ab dem Ereignis reagiert — Ausgabegrenze, Elternende,
#: ``linger``, Abbruch. Gezählt ab dem Ereignis selbst, nie ab dem Start: Der
#: Interpreterstart des Kindes zählt nicht mit (RM-635). Der Prozesskern sieht
#: alle ``PROCESS_POLL_SECONDS`` (0,05 s) nach; das harte Beenden dauerte unter
#: Last bis 3,2 s. Ein Kern, der nur alle 20 s nachsieht, reißt die Frist.
REACTION = 10.0


def _stamp(path: Path) -> str:
    """Python-Zeilen, mit denen ein Kind die Zeit eines Ereignisses ablegt.

    ``time.monotonic`` ist auf allen drei Systemen eine Uhr für alle Prozesse.
    """
    return (
        "import time\n"
        "from pathlib import Path\n"
        f"Path({str(path) + '.tmp'!r}).write_text(repr(time.monotonic()))\n"
        f"__import__('os').replace({str(path) + '.tmp'!r}, {str(path)!r})\n"
    )


def _since(path: Path) -> float:
    """Sekunden seit dem Ereignis, das ein Kind in ``path`` abgelegt hat."""
    return time.monotonic() - float(path.read_text(encoding="utf-8"))


def _noting_pid(path: Path) -> str:
    """Python-Zeilen, mit denen ein Kind zuerst seine Kennung ablegt — ganz oder gar nicht."""
    return (
        "import os\n"
        "from pathlib import Path\n"
        f"Path({str(path) + '.tmp'!r}).write_text(str(os.getpid()))\n"
        f"os.replace({str(path) + '.tmp'!r}, {str(path)!r})\n"
    )


def _waiting_for(path: Path) -> str:
    """Python-Zeilen, die warten, bis ``path`` da ist (höchstens :data:`HANG_GUARD`)."""
    return (
        "import time\n"
        "from pathlib import Path\n"
        f"_until = time.monotonic() + {HANG_GUARD}\n"
        f"while not Path({str(path)!r}).exists() and time.monotonic() < _until:\n"
        "    time.sleep(0.01)\n"
    )


def _gone(pid: int, within: float = HANG_GUARD) -> bool:
    """Ob der Prozess ``pid`` innerhalb von ``within`` Sekunden nicht mehr läuft.

    Ein Zustand statt einer Marke nach fester Wartezeit: Ein überlebender
    Nachkomme schreibt unter Last seine Marke womöglich erst nach der Prüfung.
    """
    until = time.monotonic() + within
    if os.name == "nt":
        import ctypes

        # Die Windows-Namen fehlen in den ctypes-Stubs anderer Plattformen.
        windows: Any = ctypes
        kernel32 = windows.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
        kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION; ohne Griff gibt es ihn nicht mehr.
        handle = kernel32.OpenProcess(0x00100000 | 0x00001000, False, pid)
        if not handle:
            return True
        try:
            return kernel32.WaitForSingleObject(handle, int(within * 1000)) == 0
        finally:
            kernel32.CloseHandle(handle)
    while time.monotonic() < until:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        state = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False
        ).stdout.strip()
        if not state or state.startswith("Z"):
            return True
        time.sleep(0.05)
    return False


@contextlib.contextmanager
def _clock_held_until(ready: Callable[[], bool]) -> Iterator[None]:
    """``time.monotonic`` steht, bis ``ready()`` wahr ist, und läuft dann von dort weiter.

    So beginnt eine Zeitgrenze von ``run_limited`` mit dem Zustand, um den es im
    Fall geht, und nicht mit dem Interpreterstart des Kindes — unter Last fiel
    eine Grenze von 0,2 s sonst, bevor es den Zustand gab, und der Fall prüfte
    nichts. Nach :data:`HANG_GUARD` läuft die Uhr in jedem Fall.
    """
    real = time.monotonic
    begun = real()
    since: list[float] = []

    def clock() -> float:
        now = real()
        if not since:
            if not ready() and now - begun < HANG_GUARD:
                return begun
            since.append(now)
        return begun + (now - since[0])

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(time, "monotonic", clock)
        yield


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


def test_the_program_folder_travels_so_that_nvidia_smi_finds_its_library() -> None:
    """Ohne ``PROGRAMFILES`` antwortet ``nvidia-smi`` mit „Failed to initialize
    NVML“ (rc 255, gemessen an der RTX 4080), und jeder Windows-Rechner hätte für
    Solidon keine Grafikkarte (RM-564, Nachprüfung K, N6)."""
    answer = process.trusted_environment({"PROGRAMFILES": r"C:\Program Files"})

    assert answer == {"PROGRAMFILES": r"C:\Program Files"}


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
        timeout=HANG_GUARD,
        output_limit=4096,
    )

    lines = answer.stdout.decode("utf-8").strip().splitlines()
    assert Path(lines[0]).resolve() == tmp_path.resolve()
    assert lines[1] == "fehlt"


def test_limited_process_stops_at_the_combined_output_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    finished = tmp_path / "normal-finish"
    writing = tmp_path / "schreibt"
    script = _stamp(writing) + (
        "import os\n"
        f"os.write(1, b'x' * 700); os.write(2, b'y' * 700); time.sleep({SLEEP})\n"
        f"Path({str(finished)!r}).touch()\n"
    )
    children: list[subprocess.Popen[bytes]] = []
    real_popen = subprocess.Popen

    def record_child(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(process.subprocess, "Popen", record_child)

    # Gestoppt wird an der Grenze, während das Kind noch Minuten schliefe:
    # Ohne Reaktion käme die Zeitgrenze (TimeoutExpired), ohne Abbruch sein Ende.
    with pytest.raises(process.ProcessOutputLimitExceeded):
        process.run_limited(
            [sys.executable, "-c", script],
            cwd=tmp_path,
            timeout=HANG_GUARD,
            output_limit=1024,
        )

    assert _since(writing) < REACTION, "die Grenze griff erst lange nach der Ausgabe"
    assert children[0].poll() is not None, "das Kind muss bereits beendet sein"
    assert not finished.exists(), "normal fertig werden und erst dann melden wäre zu spät"


def test_exact_output_limit_is_still_accepted(tmp_path: Path) -> None:
    answer = process.run_limited(
        [sys.executable, "-c", "import os; os.write(1, b'x' * 1024)"],
        cwd=tmp_path,
        timeout=HANG_GUARD,
        output_limit=1024,
    )

    assert len(answer.stdout) == 1024


def _parent_of_a_sleeper(tmp_path: Path, *, flags: str = "", then: str = "") -> tuple[str, Path]:
    """Ein Elternprozess, der einen langen Schläfer startet und wartet, bis er läuft.

    Der Nachkomme legt zuerst seine Kennung ab und schliefe dann :data:`SLEEP` Sekunden;
    erst danach schriebe er seine Marke. Gibt Skript und Kennungsdatei zurück.
    """
    alive = tmp_path / "nachkomme-lebt"
    marker = tmp_path / "entkommener-nachkomme"
    child = (
        _noting_pid(alive) + f"import time\ntime.sleep({SLEEP})\nPath({str(marker)!r}).touch()\n"
    )
    parent = (
        "import subprocess, sys\n"
        f"subprocess.Popen([sys.executable, '-c', {child!r}]{flags})\n" + _waiting_for(alive) + then
    )
    return parent, alive


def _assert_the_sleeper_is_gone(alive: Path, why: str, since: Path | None = None) -> None:
    """Der Nachkomme lief und läuft nicht mehr; seine Marke kam nie. Mit ``since``
    ist er spätestens :data:`REACTION` nach diesem Ereignis weg."""
    assert _gone(int(alive.read_text())), why
    if since is not None:
        assert _since(since) < REACTION, f"{why} — erst lange nach dem Elternende"
    assert not (alive.parent / "entkommener-nachkomme").exists(), why


def test_timeout_stops_the_descendant_process_too(tmp_path: Path) -> None:
    parent, alive = _parent_of_a_sleeper(tmp_path, then=f"time.sleep({SLEEP})\n")

    # Die 0,2 s laufen ab dem lebenden Nachkommen, nicht ab dem Start des Elternprozesses.
    with _clock_held_until(alive.exists), pytest.raises(subprocess.TimeoutExpired):
        process.run_limited(
            [sys.executable, "-c", parent],
            cwd=tmp_path,
            timeout=0.2,
            output_limit=4096,
        )

    _assert_the_sleeper_is_gone(alive, "ein Nachkomme darf den abgebrochenen Lauf nicht überleben")


def test_a_successful_parent_must_not_leave_a_descendant_running(tmp_path: Path) -> None:
    ending = tmp_path / "elternende"
    parent, alive = _parent_of_a_sleeper(tmp_path, then=_stamp(ending))

    answer = process.run_limited(
        [sys.executable, "-c", parent],
        cwd=tmp_path,
        timeout=HANG_GUARD,
        output_limit=4096,
    )

    assert answer.returncode == 0
    _assert_the_sleeper_is_gone(
        alive, "auch ein erfolgreicher Lauf darf keine Kinder zurücklassen", ending
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows-Jobobjekt")
def test_a_windows_child_cannot_escape_into_a_detached_process_group(tmp_path: Path) -> None:
    """Das Jobobjekt schließt auch eine losgelöste Prozessgruppe.

    **Die Flaggen kommen aus dem Produktivweg und stehen hier nicht ein zweites
    Mal.** Ausgeschrieben waren es nur ``CREATE_NEW_PROCESS_GROUP`` und
    ``DETACHED_PROCESS`` — die Anwendung startet losgelöste Prozesse aber immer
    zusätzlich mit ``CREATE_NO_WINDOW`` (``detached_process_options`` hat
    ``no_window=True`` als Vorgabe). Ohne diese dritte Flagge öffnete der
    Testenkel am 10.09.2026 unter Windows Terminal ein sichtbares Fenster mit
    „Fehler 2147942632 (0x800700e8)"; der Test blieb dabei grün, denn das
    Fenster ist ein Nebeneffekt der Konsolenzuweisung und nicht der
    Prozessgruppe.

    Eine Testfassung, die dieselben Flaggen selbst zusammensetzt, kann vom
    echten Startweg abweichen — diese hier kann es nicht mehr.

    **Gemessen statt zugesehen (14.09.2026, RM-100):** Ein Fensterzähler über
    ``EnumWindows`` (zwanzig Abtastungen je Sekunde) um genau diese
    Enkelkette, gefahren aus einer von Windows Terminal 1.24 gehosteten
    Konsole auf Windows 11 26200, direkt und unter pytest — kein neues
    Fenster, weder mit noch ohne ``CREATE_NO_WINDOW``, und die Marke des
    Enkels blieb beide Male aus. Die Flagge bleibt trotzdem: Sie ist der
    Produktivweg, und der Befund vom 10.09. ist eine Beobachtung, die eine
    andere Terminal- oder Delegationslage getroffen haben kann.
    """
    flags = process.process_group_options(detached=True, no_window=True)["creationflags"]
    ending = tmp_path / "elternende"
    parent, alive = _parent_of_a_sleeper(
        tmp_path, flags=f", creationflags={flags}", then=_stamp(ending)
    )

    answer = process.run_limited(
        [sys.executable, "-c", parent],
        cwd=tmp_path,
        timeout=HANG_GUARD,
        output_limit=4096,
    )

    assert answer.returncode == 0
    _assert_the_sleeper_is_gone(
        alive, "das Jobobjekt muss auch losgelöste Gruppen schließen", ending
    )


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
        timeout=HANG_GUARD,
        output_limit=4096,
        on_line=seen.append,
    )

    assert answer.returncode == 0
    assert seen == ["größer", "halb", "fertig"]


class _BlockingCallback:
    """Ein Zeilenempfänger, der bei der ersten Zeile hängen bleibt, bis man ihn löst.

    ``entered`` sagt, dass er hängt, ``returned``, dass er zurückkam. Kehrt der
    Lauf zurück, während er noch hängt, hat der Lauf nicht auf ihn gewartet —
    eine Ordnung der Ereignisse statt einer Stoppuhr, die unter Last den
    Interpreterstart mitmaß.
    """

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.returned = threading.Event()

    def __call__(self, _line: str) -> None:
        self.entered_at = time.monotonic()
        self.entered.set()
        self.release.wait(HANG_GUARD)
        self.returned.set()


_SLEEPER = [sys.executable, "-c", f"print('bereit', flush=True); import time; time.sleep({SLEEP})"]


def test_a_blocking_stream_callback_cannot_disable_the_total_timeout(tmp_path: Path) -> None:
    callback = _BlockingCallback()

    # Die 0,2 s laufen ab dem hängenden Empfänger: Vorher gäbe es nichts zu umgehen.
    with _clock_held_until(callback.entered.is_set), pytest.raises(subprocess.TimeoutExpired):
        process.run_stream_limited(
            _SLEEPER, cwd=tmp_path, timeout=0.2, output_limit=4096, on_line=callback
        )

    assert callback.entered.is_set() and not callback.returned.is_set()
    callback.release.set()


def test_a_blocking_stream_callback_cannot_disable_cancellation(tmp_path: Path) -> None:
    callback = _BlockingCallback()

    with pytest.raises(process.ProcessCancelled):
        process.run_stream_limited(
            _SLEEPER,
            cwd=tmp_path,
            timeout=HANG_GUARD,
            output_limit=4096,
            on_line=callback,
            cancelled=callback.entered.is_set,
        )

    assert not callback.returned.is_set(), "der Abbruch wartete auf den Empfänger"
    assert time.monotonic() - callback.entered_at < REACTION, "der Abbruch griff spät"
    callback.release.set()


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
        timeout=HANG_GUARD,
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


class _SlowToDie:
    """Ein Prozess, der erst ``dying`` Sekunden nach dem harten Ende weg ist — wie ein
    Kind mit vielen rechnenden Fäden: ``TerminateProcess`` wirkt erst, wenn jeder Faden
    eine Zeitscheibe bekommt. Vorher endet er nicht von selbst."""

    pid = 4711

    def __init__(self, dying: float) -> None:
        self.dying = dying
        self.killed_at: float | None = None
        self.returncode: int | None = None

    def kill(self) -> None:
        self.killed_at = time.monotonic()

    def wait(self, timeout: float | None = None) -> int:
        if self.killed_at is not None:
            remaining = self.killed_at + self.dying - time.monotonic()
            if timeout is None or remaining <= timeout:
                time.sleep(max(0.0, remaining))
                self.returncode = -9
                return -9
        assert timeout is not None, "ohne Ende und ohne Frist wartete der Test ewig"
        time.sleep(timeout)
        raise subprocess.TimeoutExpired("kind", timeout)


@pytest.mark.parametrize("system", ["nt", "posix"])
def test_a_killed_process_that_takes_a_moment_to_die_is_waited_for(
    monkeypatch: pytest.MonkeyPatch, system: str
) -> None:
    """Der Abbau wartet auf das Ende des hart beendeten Prozesses (RM-635).

    Mit fester halber Sekunde danach warf er selbst ``TimeoutExpired`` — und der
    Lauf meldete einen Zeitablauf statt seines Grundes (Abbruch, Zeitgrenze,
    Ausgabegrenze). Ruhig brauchte ein Kind mit acht rechnenden Fäden im Median
    0,53 s vom Beenden bis zum Ende, unter Last bis 3,2 s.
    """
    monkeypatch.setattr(process.os, "name", system)
    monkeypatch.setattr(process, "_taskkill", lambda _pid, *, force: None)
    monkeypatch.setattr(process, "_kill_process_group", lambda _pid, *, force: None)
    child = _SlowToDie(dying=2 * process.PROCESS_STOP_SECONDS)

    process.terminate_process_tree(child)  # type: ignore[arg-type]

    assert child.killed_at is not None and child.returncode == -9


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


def test_a_process_that_stays_after_its_result_is_ended(tmp_path: Path) -> None:
    """Bambu Studio schreibt Druckdatei und ``result.json`` und endet manchmal
    nicht mehr (Gesamtprüfung, 27.09.2026). Sagt ``finished`` ja, wartet der
    Lauf nur noch ``linger`` Sekunden und beendet den Prozess — statt bis zum
    Zeitlimit, nach dem der Kunde eine Absage über einer fertigen Datei las."""
    result = tmp_path / "result.json"
    ended = tmp_path / "von-selbst-fertig"
    noted = tmp_path / "ergebnis-zeit"
    script = (
        _stamp(noted) + _noting_pid(result) + f"time.sleep({SLEEP})\nPath({str(ended)!r}).touch()\n"
    )

    # Ohne ``linger`` endete der Lauf erst an der Zeitgrenze, mit TimeoutExpired;
    # er kommt ohne zurück, lange bevor das Kind von selbst fertig würde.
    process.run_limited(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        timeout=HANG_GUARD,
        output_limit=4096,
        finished=result.exists,
        linger=0.3,
    )

    assert _since(noted) < 0.3 + REACTION, "erst lange nach dem Ergebnis beendet"
    assert _gone(int(result.read_text())), "beendet, nicht weiterlaufen gelassen"
    assert not ended.exists(), "beendet, nicht von selbst fertig geworden"


def test_a_process_that_ends_on_its_own_keeps_its_return_code(tmp_path: Path) -> None:
    """Wer von selbst endet, bleibt unberührt — auch mit ``finished``.

    ``linger`` ist hier die Hängergrenze: Sie beginnt mit dem Start, und ein
    Interpreter, der unter Last länger als sie bis zu seiner Zeile braucht, würde
    beendet statt abgewartet.
    """
    answer = process.run_limited(
        [sys.executable, "-c", "print('fertig')"],
        cwd=tmp_path,
        timeout=HANG_GUARD,
        output_limit=4096,
        finished=lambda: True,
        linger=HANG_GUARD,
    )

    assert answer.returncode == 0
    assert answer.stdout.decode("utf-8").strip() == "fertig"


#: Die Wurzel des Baums, aus dem Kinder ``app`` laden.
ROOT = Path(__file__).resolve().parents[1]


def _starts_a_program(module: str, name: str) -> bool:
    """Ob ``<module>.<name>(…)`` ein Programm startet — über ``subprocess`` und daran vorbei."""
    if module == "subprocess":
        return name in {"Popen", "run", "call", "check_call", "check_output"}
    if module == "asyncio":
        return name in {"create_subprocess_exec", "create_subprocess_shell"}
    if module == "os":
        return name in {"startfile", "system", "popen"} or name.startswith(
            ("spawn", "exec", "posix_spawn")
        )
    return False


#: Was eine Datei tragen muss, damit sie einen Start enthalten kann: den Namen
#: des Moduls oder der Startfunktion, auch hinter einem Alias. Eine Datei ohne
#: Treffer wird nicht geparst; das Parsen aller Dateien unter ``app/`` war fast
#: die ganze Laufzeit des Wächters.
_MAY_START = re.compile(
    r"subprocess|startfile|QProcess|\bspawn[lv]|posix_spawn|\bexec[lv]"
    r"|\b(?:system|popen)\s*\(|import[^\n]*\b(?:system|popen)\b"
)


def _is_shield(expression: ast.expr) -> bool:
    """``no_error_dialogs()`` oder ``process.no_error_dialogs()``."""
    if not isinstance(expression, ast.Call):
        return False
    function = expression.func
    name = function.attr if isinstance(function, ast.Attribute) else getattr(function, "id", "")
    return name == "no_error_dialogs"


def _scan(source: str) -> tuple[list[int], list[int]]:
    """Zeilen aller Programmstarts und der Starts außerhalb von ``no_error_dialogs``.

    Ein Start ist ``subprocess.Popen(…)`` und seine Geschwister, auch über
    ``import subprocess as …`` und ``from subprocess import …``, dazu die Wege
    an ``subprocess`` vorbei (``os.startfile``, ``os.system``, ``os.spawn*``,
    ``os.exec*``, ``asyncio.create_subprocess_*``). ``QProcess`` startet
    außerhalb jedes Blocks (``start`` läuft später als der Bau) und zählt
    deshalb immer als ungeschützt.
    """
    tree = ast.parse(source)
    modules: dict[str, str] = {}
    direct: set[str] = set()
    forbidden: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.partition(".")[0] in {"subprocess", "asyncio", "os"}:
                    modules[alias.asname or alias.name.partition(".")[0]] = alias.name.partition(
                        "."
                    )[0]
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if node.module and _starts_a_program(node.module, alias.name):
                    direct.add(alias.asname or alias.name)
                if alias.name == "QProcess":
                    forbidden.append(node.lineno)
        elif (isinstance(node, ast.Name) and node.id == "QProcess") or (
            isinstance(node, ast.Attribute) and node.attr == "QProcess"
        ):
            forbidden.append(node.lineno)

    def is_start(call: ast.Call) -> bool:
        function = call.func
        if isinstance(function, ast.Name):
            return function.id in direct
        return (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and _starts_a_program(modules.get(function.value.id, ""), function.attr)
        )

    shielded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.With) and any(_is_shield(item.context_expr) for item in node.items):
            for statement in node.body:
                shielded.update(id(inner) for inner in ast.walk(statement))
    starts = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and is_start(node)]
    return (
        sorted([node.lineno for node in starts] + forbidden),
        sorted([node.lineno for node in starts if id(node) not in shielded] + forbidden),
    )


def _unshielded_starts(source: str) -> tuple[list[int], list[int]]:
    """:func:`_scan` hinter dem Vorfilter :data:`_MAY_START`."""
    return _scan(source) if _MAY_START.search(source) else ([], [])


def test_every_program_start_of_the_application_opens_no_system_window() -> None:
    """Jeder Start über ``subprocess`` unter ``app/`` steht in ``no_error_dialogs`` (RM-788).

    Ohne den Block öffnet Windows für eine ``.exe``, die kein Programm ist, das
    Fenster „Nicht unterstützte 16-Bit-Anwendung“ im startenden Faden und
    wartet auf einen Klick. ``multiprocessing`` startet nur den eigenen
    Interpreter und zählt nicht.
    """
    starts: list[str] = []
    bare: list[str] = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        found, unshielded = _unshielded_starts(path.read_text(encoding="utf-8"))
        name = path.relative_to(ROOT).as_posix()
        starts += [f"{name}:{line}" for line in found]
        bare += [f"{name}:{line}" for line in unshielded]
    assert len(starts) >= 5, f"die Suche fand die Programmstarts nicht mehr: {starts}"
    assert not bare, f"Programmstart ohne no_error_dialogs: {bare}"


def test_the_start_guard_sees_a_start_outside_the_block() -> None:
    """Gegenprobe des Wächters: außerhalb des Blocks, im Kopf des Blocks und daneben."""
    source = (
        "import subprocess\n"
        "from app.core import process\n"
        "subprocess.Popen(['a'])\n"
        "with process.no_error_dialogs():\n"
        "    subprocess.Popen(['b'])\n"
        "with no_error_dialogs():\n"
        "    started = subprocess.run(['c'])\n"
        "with subprocess.Popen(['d']) as d, no_error_dialogs():\n"
        "    pass\n"
        "with open('e'):\n"
        "    subprocess.check_output(['e'])\n"
    )
    assert _unshielded_starts(source) == ([3, 5, 7, 8, 11], [3, 8, 11])


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "import subprocess as sp\nsp.Popen(['a'])\n"
            "with no_error_dialogs():\n    sp.run(['b'])\n",
            ([2, 4], [2]),
            id="import-subprocess-as",
        ),
        pytest.param(
            "from subprocess import Popen as P, PIPE\nP(['a'], stdout=PIPE)\n"
            "with no_error_dialogs():\n    P(['b'])\n",
            ([2, 4], [2]),
            id="from-subprocess-import",
        ),
        pytest.param(
            "import os\nos.startfile('a.exe')\nwith no_error_dialogs():\n    os.startfile('b')\n",
            ([2, 4], [2]),
            id="os-startfile",
        ),
        pytest.param(
            "import os as o\no.system('a')\no.spawnv(0, 'b', [])\no.execv('c', [])\n"
            "o.popen('d')\no.path.join('e')\n",
            ([2, 3, 4, 5], [2, 3, 4, 5]),
            id="os-system-spawn-exec-popen",
        ),
        pytest.param(
            "from os import startfile\nstartfile('a')\n",
            ([2], [2]),
            id="from-os-import",
        ),
        pytest.param(
            "import asyncio\nasyncio.create_subprocess_exec('a')\n",
            ([2], [2]),
            id="asyncio",
        ),
        pytest.param(
            "from PySide6.QtCore import QProcess\nwith no_error_dialogs():\n"
            "    QProcess.startDetached('a')\n",
            ([1, 3], [1, 3]),
            id="qprocess",
        ),
        pytest.param(
            "import os\nos.makedirs('a')\nrun(['b'])\n",
            ([], []),
            id="nothing-that-starts",
        ),
    ],
)
def test_the_start_guard_sees_every_way_to_start_a_program(
    source: str, expected: tuple[list[int], list[int]]
) -> None:
    """Gegenprobe je Form (N3): Alias, Direktimport und die Wege an ``subprocess`` vorbei.

    Jede Form geht durch denselben Vorfilter wie der Wächter; was er wegließe,
    fände der Fall hier nicht. ``QProcess`` gilt auch im Block als ungeschützt.
    """
    assert _unshielded_starts(source) == expected


@pytest.mark.skipif(os.name != "nt", reason="Fehlermodus eines Fadens gibt es nur unter Windows")
def test_the_error_mode_holds_only_inside_the_block() -> None:
    """Der Modus gilt im Block und ist danach wieder, wie er war — verschachtelt und
    nach einer Ausnahme, wie sie ein gescheiterter Start wirft."""
    import ctypes

    windows: Any = ctypes
    kernel32 = windows.WinDLL("kernel32", use_last_error=True)
    kernel32.GetThreadErrorMode.restype = ctypes.c_uint32
    before = kernel32.GetThreadErrorMode()
    with process.no_error_dialogs():
        inside = kernel32.GetThreadErrorMode()
        with process.no_error_dialogs():
            nested = kernel32.GetThreadErrorMode()
        assert kernel32.GetThreadErrorMode() == inside, "der innere Block nahm den äußeren mit"
    assert inside & 0x0001 and nested & 0x0001, "SEM_FAILCRITICALERRORS fehlt im Block"
    assert kernel32.GetThreadErrorMode() == before
    with pytest.raises(OSError, match="Start"), process.no_error_dialogs():
        raise OSError("Start gescheitert")
    assert kernel32.GetThreadErrorMode() == before, "nach der Ausnahme blieb der Modus stehen"


@pytest.mark.skipif(
    os.name != "nt", reason="das Fenster für 16-Bit-Anwendungen gibt es nur unter Windows"
)
@pytest.mark.parametrize("start", ["run_limited", "run_stream_limited"])
def test_a_file_that_is_no_program_fails_at_once_instead_of_waiting_for_a_click(
    tmp_path: Path, start: str
) -> None:
    """Eine ``.exe``, die kein Programm ist, endet sofort im ``OSError`` (RM-788).

    Das Kind startet im Standardfehlermodus (``CREATE_DEFAULT_ERROR_MODE``), wie
    die Anwendung aus Explorer und Startmenü — aus Git Bash erbte die Suite
    ``SEM_FAILCRITICALERRORS`` und sähe den Fehler nie. Ohne
    ``no_error_dialogs`` wartete ``CreateProcess`` dort auf einen Klick in
    „Nicht unterstützte 16-Bit-Anwendung“; die Frist zählt ab dem Aufruf, nicht
    ab dem Interpreterstart.
    """
    fake = tmp_path / "elegoo-slicer.exe"
    fake.write_text("kein programm", encoding="utf-8")
    called = tmp_path / "aufgerufen"
    extra = ", output_limit=4096, on_line=print" if start == "run_stream_limited" else ""
    # Die Umgebung einmal vor der Marke: Ihr erster Aufruf lädt ``discover``,
    # und das gehört nicht in die Frist ab dem Aufruf.
    script = (
        "from app.core import process\n"
        + "process.trusted_environment()\n"
        + _stamp(called)
        + "try:\n"
        + f"    process.{start}([{str(fake)!r}], cwd=Path({str(tmp_path)!r}), "
        + f"timeout={HANG_GUARD}{extra})\n"
        + "except OSError as problem:\n"
        + "    print('OSError', problem.winerror, flush=True)\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", script],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_DEFAULT_ERROR_MODE", 0),
    )
    try:
        until = time.monotonic() + HANG_GUARD
        while not called.exists() and child.poll() is None and time.monotonic() < until:
            time.sleep(0.01)
        try:
            output, errors = child.communicate(timeout=REACTION)
        except subprocess.TimeoutExpired:
            if not called.exists():
                pytest.fail(f"Das Kind kam in {HANG_GUARD:.0f} s nicht bis zum Aufruf.")
            pytest.fail(
                f"Der Start einer .exe, die kein Programm ist, kam {REACTION:.0f} s nach dem "
                "Aufruf nicht zurück: CreateProcess wartet im Fenster „Nicht unterstützte "
                "16-Bit-Anwendung“ auf einen Klick — der Start lief nicht in "
                "process.no_error_dialogs (RM-788)."
            )
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()
    assert child.returncode == 0, output + errors
    # 216 für einen Text oder einen MZ-Kopf ohne Programm, 193 für eine leere
    # Datei oder eine DLL; ein verrutschter Pfad (2) erreichte den 16-Bit-Weg nie.
    assert output.split()[:2] in (["OSError", "216"], ["OSError", "193"]), output + errors


def test_the_comfyui_setup_starts_behind_the_shared_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Einrichtung von ComfyUI startet wie jedes externe Werkzeug (§32, RM-789).

    Ihr Python bekam die ganze Umgebung von Solidon — gesetzte API-Schlüssel und
    Python-Suchpfade eingeschlossen — und den Arbeitsordner des Aufrufers. Was
    der Download von Hugging Face liest (``HF_*``: Spiegel, Cache, Zugang),
    reist weiter mit; es gehört zu genau diesem Programm.
    """
    import json

    from app.core.backends import comfy_setup

    monkeypatch.setenv("ANTHROPIC_API_KEY", "geheim")
    monkeypatch.setenv("PYTHONPATH", "fremd")
    monkeypatch.setenv("HF_ENDPOINT", "https://spiegel.example")
    output = comfy_setup._run(
        [
            sys.executable,
            "-c",
            "import json, os; print(json.dumps([sorted(os.environ), os.getcwd()]))",
        ],
        "Umgebung",
        comfy_setup._silent,
    )

    names, folder = json.loads(output.splitlines()[-1])
    assert "ANTHROPIC_API_KEY" not in names, "ein fremder Schlüssel reiste mit"
    assert "PYTHONPATH" not in names, "Solidons Suchpfad reiste mit"
    assert "HF_ENDPOINT" in names, "der Spiegel von Hugging Face fehlt dem Download"
    assert Path(folder).resolve() == process.trusted_cwd()


def test_a_cancelled_comfyui_step_ends_its_whole_tree(tmp_path: Path) -> None:
    """Abbrechen beendet auch, was der Schritt gestartet hat (§32, RM-789).

    ``process.kill()`` traf nur das direkte Kind; ein Enkel lief weiter. Der
    Abbruch greift, sobald der Enkel läuft.
    """
    from app.core.backends import comfy_setup

    parent, alive = _parent_of_a_sleeper(tmp_path, then=f"time.sleep({SLEEP})\n")

    with pytest.raises(comfy_setup.Cancelled):
        comfy_setup._run(
            [sys.executable, "-c", parent],
            "Ein Schritt mit Enkel",
            comfy_setup._silent,
            alive.exists,
        )

    _assert_the_sleeper_is_gone(alive, "der Enkel überlebte den Abbruch der Einrichtung")
