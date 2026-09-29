"""Privater Speicher eines frischen Prozesses nach einzelnen Importen (Herkunft der 761 MB)."""

import ctypes
import os
import sys
from ctypes import wintypes


class Counters(ctypes.Structure):
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
        ("PrivateUsage", ctypes.c_size_t),
    ]


def mine() -> str:
    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.K32GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
    kernel32.K32GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
    return f"Arbeitssatz {counters.WorkingSetSize / 2**20:6.0f} MB, privat {counters.PrivateUsage / 2**20:6.0f} MB"


print(f"OPENBLAS_NUM_THREADS={os.environ.get('OPENBLAS_NUM_THREADS')} cpu={os.cpu_count()}")
print("leer        ", mine())
import numpy

print("numpy       ", mine())
import manifold3d  # noqa: E402,F401

print("manifold3d  ", mine())
import scipy.sparse.csgraph  # noqa: E402,F401

print("csgraph     ", mine())
try:
    from threadpoolctl import threadpool_info

    for info in threadpool_info():
        print("  ", info.get("internal_api"), info.get("num_threads"), info.get("version"))
except ImportError:
    print("  threadpoolctl fehlt")
numpy.show_config() if "--config" in sys.argv else None
