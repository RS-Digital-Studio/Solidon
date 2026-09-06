"""Erfasst die mittlere Windows-CPU-Last rund um ein tatsächlich gemessenes Zeitfenster."""
import ctypes
import os
import time


def cpu_snapshot():
    values = [ctypes.c_ulonglong() for _ in range(3)]
    if not ctypes.windll.kernel32.GetSystemTimes(*(ctypes.byref(v) for v in values)):
        raise ctypes.WinError()
    return time.perf_counter(), time.process_time(), tuple(v.value for v in values)


def cpu_context(before):
    after = cpu_snapshot()
    wall = after[0] - before[0]
    idle, kernel, user = (last-first for first, last in zip(before[2], after[2]))
    total = kernel + user
    system = 100.0 * (total-idle) / total if total else None
    process = 100.0 * (after[1]-before[1]) / (wall * (os.cpu_count() or 1)) if wall else None
    return {"sample_seconds": wall, "logical_cpus": os.cpu_count(),
            "system_cpu_percent": system, "process_cpu_percent": process,
            "background_cpu_estimate_percent": max(0.0, system-process) if system is not None and process is not None else None,
            "scope": "Mittel über das Messfenster; keine Aussage über einzelne Kerne oder GPU-Fremdlast"}
