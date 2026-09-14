"""Zählt die Fenster, die während eines Befehls aufgehen — statt zuzusehen.

Der Anlass ist RM-100: Am 02.09.2026 ließ die Suite auf einem Rechner mit
Windows Terminal als Standardhost ein Fenster mit „Fehler 2147942632
(0x800700e8)" aufgehen, und der Test dazu blieb grün — das Fenster war ein
Nebeneffekt der Konsolenzuweisung, nicht des Prozessbaums, den er prüft.
„Ob ein Fenster aufgeht, sieht nur, wer zusieht" stimmt nicht: Windows führt
seine sichtbaren Hauptfenster, und wer sie vor dem Befehl und während des
Befehls abfragt, sieht jedes, das dazukommt — auch eines, das nach einer
Sekunde wieder weg ist.

Aufruf:

    python tools/count_new_windows.py -- python -m pytest tests/test_process.py -q

Gemeldet werden Klasse, Titel und Prozesskennung jedes Fensters, das während
des Befehls neu sichtbar wurde, und getrennt die Konsolenfenster darunter
(``ConsoleWindowClass`` für conhost, ``CASCADIA_HOSTING_WINDOW_CLASS`` für
Windows Terminal). Exit 0 heißt: kein neues Konsolenfenster. Nur Windows —
anderswo gibt es die Frage nicht in dieser Form, und das Werkzeug sagt es.

Die Messung gilt nur für die Lage, in der sie läuft: Der Standardhost der
Konsole (``HKCU\\Console\\%%Startup``), die Fassung von Windows Terminal und
ob der Befehl aus einer Konsole oder ohne eine gestartet wird, gehören zum
Ergebnis. Der Kopf der Ausgabe nennt sie.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time

#: Die Fensterklassen der beiden Konsolenhosts unter Windows.
CONSOLE_CLASSES: frozenset[str] = frozenset({"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"})

#: Wie oft je Sekunde die Fensterliste abgefragt wird. Ein Fenster, das kürzer
#: als eine Abtastung lebt, ist auch für ein Auge nicht da.
SAMPLES_PER_SECOND = 20

#: Wie lange nach dem Ende des Befehls noch mitgezählt wird — ein losgelöster
#: Nachkomme kann sein Fenster erst nach dem Elternprozess öffnen.
TAIL_SECONDS = 2.0


def visible_windows() -> dict[int, tuple[str, str, int]]:
    """Alle sichtbaren Hauptfenster: Handle → (Klasse, Titel, Prozesskennung)."""
    import ctypes
    import ctypes.wintypes as wintypes

    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    found: dict[int, tuple[str, str, int]] = {}

    def collect(handle: int, _: int) -> bool:
        if user32.IsWindowVisible(handle):
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(handle, class_name, 256)
            title = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(handle, title, 512)
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
            found[int(handle)] = (class_name.value, title.value, int(owner.value))
        return True

    user32.EnumWindows(callback_type(collect), 0)
    return found


def console_host() -> str:
    """Der eingestellte Standardhost der Konsole, oder „Windows entscheidet"."""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Console\%%Startup") as key:
            terminal, _ = winreg.QueryValueEx(key, "DelegationTerminal")
    except OSError:
        return "Windows entscheidet (keine Delegation eingetragen)"
    return str(terminal)


def own_console_class() -> str:
    """Die Fensterklasse der eigenen Konsole — oder „keine"."""
    import ctypes

    handle = ctypes.windll.kernel32.GetConsoleWindow()
    if not handle:
        return "keine"
    class_name = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(handle, class_name, 256)
    return class_name.value


def watch(command: list[str]) -> tuple[int, dict[int, tuple[str, str, int]]]:
    """Führt den Befehl aus und sammelt jedes Fenster, das währenddessen neu sichtbar wird."""
    before = visible_windows()
    new: dict[int, tuple[str, str, int]] = {}
    stop = threading.Event()

    def sample() -> None:
        while not stop.is_set():
            for handle, entry in visible_windows().items():
                if handle not in before and handle not in new:
                    new[handle] = entry
            time.sleep(1.0 / SAMPLES_PER_SECOND)

    watcher = threading.Thread(target=sample, daemon=True)
    watcher.start()
    try:
        returncode = subprocess.call(command)
        time.sleep(TAIL_SECONDS)
    finally:
        stop.set()
        watcher.join()
    return returncode, new


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zählt die Fenster, die während eines Befehls aufgehen — statt zuzusehen."
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="der Befehl, nach „--“")
    options = parser.parse_args(argv)
    command = [part for part in options.command if part != "--"]
    if not command:
        parser.error("kein Befehl angegeben")
    if sys.platform != "win32":
        print("Nur unter Windows: Dort hat ein Konsolenprozess ein Fenster, das aufgehen kann.")
        return 2

    # Vor dem Befehl hinaus, sonst steht die Kopfzeile in einer umgeleiteten
    # Ausgabe hinter dem, was der Befehl schreibt.
    print(f"Standardhost: {console_host()} · eigene Konsole: {own_console_class()}", flush=True)
    returncode, new = watch(command)
    consoles = {handle: entry for handle, entry in new.items() if entry[0] in CONSOLE_CLASSES}
    print(f"Befehl beendet mit {returncode}; neue sichtbare Fenster: {len(new)}")
    for class_name, title, owner in new.values():
        print(f"    {class_name:36} {owner:>7}  {title!r}")
    print(f"davon Konsolenfenster: {len(consoles)}")
    return 1 if consoles else 0


if __name__ == "__main__":
    raise SystemExit(main())
