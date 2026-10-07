"""Sperrt eine eben umbenannte Meldedatei ihren Leser? (zu ``elternende.py``)

Der Lebenszyklustest und seine Sonde veröffentlichen Meldungen wie
``tests/test_kernel_process_lifecycle._write_mark``: schreiben nach
``*.pending``, dann ``Path.replace`` auf den eigentlichen Namen. Der Prüfer
wartet, bis der Name da ist, und liest ihn. Im ersten Sondenlauf scheiterte
dieses Lesen einmal mit ``PermissionError``.

Hier schreibt ein zweiter Prozess ``count`` Meldungen auf diesem Weg; der Leser
öffnet jeden Namen, sobald ``is_file()`` ihn sieht, zuerst über ``CreateFileW``
mit derselben Freigabe wie Pythons ``open`` (Lesen und Schreiben, ohne Löschen)
und zählt den Windows-Fehlercode, dann liest er wie der Test und zählt
``PermissionError``. Nach einer Ablehnung versucht er denselben Namen erneut.

Aufruf (Windows): python elternende_umbenennen.py [count]
Ausgabe: eine Zeile mit Uhrzeit, Zählern und gelesener Zahl.
"""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

WRITER = """
import json, sys, time
from pathlib import Path
folder = Path(sys.argv[1])
for i in range(int(sys.argv[2])):
    path = folder / f"mark{i}.json"
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps({"i": i}), encoding="utf-8")
    pending.replace(path)
    time.sleep(0.002)
"""

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
kernel32.CreateFileW.restype = ctypes.c_void_p
kernel32.CreateFileW.argtypes = (
    ctypes.c_wchar_p,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_void_p,
)
kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)

#: Freigabe wie Pythons ``open`` unter Windows: Lesen und Schreiben, kein Löschen.
SHARE_READ_WRITE = 0x3


def open_error(path: Path) -> int:
    """0, wenn sich der Name zum Lesen öffnen lässt, sonst der Windows-Fehlercode."""
    handle = kernel32.CreateFileW(str(path), 0x80000000, SHARE_READ_WRITE, None, 3, 0x80, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        return ctypes.get_last_error()  # type: ignore[attr-defined]
    kernel32.CloseHandle(handle)
    return 0


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    folder = Path(tempfile.mkdtemp(prefix="umbenennen-"))
    writer = subprocess.Popen([sys.executable, "-c", WRITER, str(folder), str(count)])
    seen: Counter[str] = Counter()
    i = 0
    deadline = time.monotonic() + 300
    while i < count and time.monotonic() < deadline:
        path = folder / f"mark{i}.json"
        if not path.is_file():
            continue
        error = open_error(path)
        if error:
            seen[f"CreateFileW Fehler {error}"] += 1
            continue
        try:
            assert json.loads(path.read_text(encoding="utf-8")) == {"i": i}
        except PermissionError:
            seen["read_text PermissionError"] += 1
            continue
        seen["gelesen"] += 1
        i += 1
    writer.wait()
    print(time.strftime("%Y-%m-%d %H:%M:%S"), dict(seen), f"{i} von {count}", flush=True)


if __name__ == "__main__":
    main()
