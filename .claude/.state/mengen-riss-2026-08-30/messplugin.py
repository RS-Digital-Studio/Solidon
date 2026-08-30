"""Misst nach jedem Test, was mit der Sammelmenge wächst.

Zeilenweise geschrieben (``buffering=1``): Der Lauf, um den es geht, stürzt ab,
und ein Werkzeug, das erst am Sitzungsende ausgibt, misst genau den Fall nicht,
für den es gebaut ist.

Die erste Fassung gab für Handles ``-1`` und für den Arbeitssatz ``0`` zurück,
über zweiundsechzig Zeilen konstant — und eine konstante Zahl ist ein Zeiger
auf das Werkzeug, nicht auf die Sache. Ohne ``argtypes``/``restype`` schneidet
ctypes das Prozess-Handle auf 32 Bit ab; der Aufruf gelingt scheinbar und
liefert nichts. Beide Funktionen sind jetzt an einem Fall mit bekanntem
Ausgang geprüft (136 Handles, 15 MB in einem nackten Python).
"""

import ctypes
import gc
import os
from ctypes import wintypes

import pytest

_ZIEL = open(os.environ["KUER_PROTOKOLL"], "w", buffering=1, encoding="utf-8")
_ZAEHLER = {"n": 0}

_K32 = ctypes.WinDLL("kernel32", use_last_error=True)
_K32.GetCurrentProcess.restype = wintypes.HANDLE
_K32.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
_K32.GetProcessHandleCount.restype = wintypes.BOOL

_PSAPI = ctypes.WinDLL("psapi", use_last_error=True)


class _Counters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


_PSAPI.GetProcessMemoryInfo.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(_Counters),
    wintypes.DWORD,
]


def _handles() -> int:
    count = wintypes.DWORD(0)
    ok = _K32.GetProcessHandleCount(_K32.GetCurrentProcess(), ctypes.byref(count))
    return int(count.value) if ok else -1


def _memory() -> tuple[int, int]:
    counters = _Counters()
    counters.cb = ctypes.sizeof(_Counters)
    ok = _PSAPI.GetProcessMemoryInfo(_K32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
    if not ok:
        return -1, -1
    return int(counters.WorkingSetSize), int(counters.PagefileUsage)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    _ZAEHLER["n"] += 1
    oben = tot = leash = -1
    try:
        from PySide6.QtWidgets import QApplication
        from shiboken6 import isValid

        application = QApplication.instance()
        if application is not None:
            widgets = list(application.topLevelWidgets())
            oben = len(widgets)
            tot = sum(1 for widget in widgets if not isValid(widget))
        from app.ui import leash as _leash

        leash = len(getattr(_leash, "_alive", ()))
    except Exception as problem:  # noqa: BLE001
        print(f"# nicht lesbar: {problem}", file=_ZIEL)

    working, pagefile = _memory()
    _ZIEL.write(
        f"{_ZAEHLER['n']}\t{item.name}\toben={oben}\ttot={tot}\tleash={leash}\t"
        f"handles={_handles()}\tarbeitssatz={working}\tauslagerung={pagefile}\t"
        f"gc={len(gc.get_objects())}\n"
    )
