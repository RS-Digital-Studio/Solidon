"""Hilfsprozess-Seite von ``elternende.py``: blockierte Rechnung wie im Lebenszyklustest.

Lädt oben nur, was der Test-Helfer auch lädt; die Varianten unterscheiden
sich ausschließlich in der Priorität während der Rechnung.
"""

from __future__ import annotations

import ctypes
import json
import os
import threading
from pathlib import Path
from typing import Any

from app.core.geom import kernel_jobs

BLOCK_SECONDS = 300.0
JOB = "probe_blocked"


def _mark(path: Path, values: dict[str, Any]) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(values), encoding="utf-8")
    pending.replace(path)


def _blocked(_arrays: Any, values: Any, _check: Any) -> tuple[dict, dict]:
    _mark(Path(values["entered"]), {"pid": os.getpid(), "parent": os.getppid()})
    threading.Event().wait(BLOCK_SECONDS)
    return {}, {}


def serve_blocked(connection: Any) -> None:
    kernel_jobs.JOBS[JOB] = _blocked
    kernel_jobs.serve(connection)


def serve_blocked_normal(connection: Any) -> None:
    """Wie oben, aber der Helfer bleibt während der Rechnung in normaler Klasse."""
    kernel_jobs._yield_to_the_window = lambda: None
    kernel_jobs.JOBS[JOB] = _blocked
    kernel_jobs.serve(connection)


def publish(helper: Any, receiver_pid: int, path: Path) -> None:
    """Dupliziert Helfer- und Elterngriff mit vollen Rechten in den Prüfer."""
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    k.OpenProcess.restype = ctypes.c_void_p
    k.DuplicateHandle.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint32,
    )
    k.CloseHandle.argtypes = (ctypes.c_void_p,)
    receiver = k.OpenProcess(0x40, False, receiver_pid)
    if not receiver:
        raise OSError(ctypes.get_last_error(), "OpenProcess")  # type: ignore[attr-defined]
    made = []
    try:
        for handle in (helper.sentinel, k.GetCurrentProcess()):
            dup = ctypes.c_void_p()
            if not k.DuplicateHandle(
                k.GetCurrentProcess(), handle, receiver, ctypes.byref(dup), 0, False, 2
            ):
                raise OSError(ctypes.get_last_error(), "DuplicateHandle")  # type: ignore[attr-defined]
            made.append(int(dup.value))
    finally:
        k.CloseHandle(receiver)
    _mark(
        path,
        {"handle": made[0], "pid": helper.pid, "parent_handle": made[1], "parent_pid": os.getpid()},
    )
