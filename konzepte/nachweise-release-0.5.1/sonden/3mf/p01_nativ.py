"""Sonde p01 (RM-258): native Stapel des Hauptfadens in den Lücken des Qt-Takts.

Wie ``sonden/fenster/p04g_cpu.py`` (echte Ereignisschleife ``exec()``, Drache
von der Startfläche, *Sofort laden*, Qt-Takt 5 ms, Python-Faden daneben,
CPU-Zeit des Hauptfadens über ``GetThreadTimes``). Dazu: Steht der Qt-Takt
länger als ``SONDE_SCHWELLE`` Sekunden (Vorgabe 0,3), holt ein Beobachterfaden
mit ``py-spy dump --native`` die Stapel aller Fäden, höchstens alle 0,25 s.
Ausgabe ``out/p01_<tag>.txt``, die Stapel unter ``out/p01_<tag>_dumps/``.
Baum aus ``SONDE_TREE``, Kennung aus ``SONDE_TAG``; ``SONDE_OHNE_DUMP=1``
misst nur (für den Vergleich vorher/nachher ohne die Pausen von py-spy).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("SONDE_FRIST", "600")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

tag = os.environ.get("SONDE_TAG", "x")
log = common.Log(f"p01_{tag}.txt")
log("app aus", common.app.__file__)
DUMP = not os.environ.get("SONDE_OHNE_DUMP")
LIMIT = float(os.environ.get("SONDE_SCHWELLE", "0.3"))
PYSPY = r"F:\3D Druck\.venv\Scripts\py-spy.exe"
dumps = common.OUT_DIR / f"p01_{tag}_dumps"
dumps.mkdir(exist_ok=True)
if os.environ.get("SONDE_FEIN"):
    import ctypes as _ctypes

    _ctypes.windll.winmm.timeBeginPeriod(1)
if os.environ.get("SONDE_SWITCH"):
    sys.setswitchinterval(float(os.environ["SONDE_SWITCH"]))
if os.environ.get("SONDE_CHUNK"):
    import app.core.ingest.threemf as _threemf

    _threemf.XML_CHUNK = int(os.environ["SONDE_CHUNK"])
if os.environ.get("SONDE_BLOCK"):
    import app.core.ingest.threemf as _threemf

    _threemf.NUMBER_BLOCK = int(os.environ["SONDE_BLOCK"])
import collections  # noqa: E402

import app.ui.app_events as _app_events  # noqa: E402

filter_calls = collections.Counter()
painted = collections.Counter()
if os.environ.get("SONDE_ZAEHLEN"):
    _original_filter = _app_events.ApplicationEvents.eventFilter

    def _counting_filter(self, watched, event):  # noqa: N802
        second = int(time.monotonic() - origin_box[0])
        filter_calls[(second, event.type().name)] += 1
        if 16 <= second <= 17:
            key = (event.type().name, type(watched).__name__, watched.objectName())
            if event.type().name == "Paint" and type(watched).__name__ in ("MainWindow", "OverlayHost", "ObjectTree", "LoadingVeil", "QStatusBar", "ToolStrip"):
                rect = event.region().boundingRect()
                key = key + (f"{rect.x()},{rect.y()} {rect.width()}x{rect.height()}",)
            painted[key] += 1
        return _original_filter(self, watched, event)

    _app_events.ApplicationEvents.eventFilter = _counting_filter
origin_box = [time.monotonic()]
application, window = common.build()
if os.environ.get("SONDE_OHNE_ZEITGEBER"):
    # Gegenprobe: Arbeiter ohne 1 ms Zeitgeberauflösung.
    import contextlib as _contextlib

    import app.ui.leash as _leash

    _leash._prompt_handover = _contextlib.nullcontext
    log("ohne Zeitgeberauflösung")
if os.environ.get("SONDE_SWITCH_NACH"):
    # Nach dem Aufbau, damit es den Wert von ``configure_gil_switching`` ersetzt.
    sys.setswitchinterval(float(os.environ["SONDE_SWITCH_NACH"]))
if os.environ.get("SONDE_OHNE_FILTER"):
    for _watcher in application.findChildren(_app_events.ApplicationEvents):
        application.removeEventFilter(_watcher)
        log("Anwendungsfilter abgemeldet")
from PySide6.QtCore import QTimer  # noqa: E402

from app.ui.dialogs import AskDialog  # noqa: E402


def handler(dialog) -> bool:
    log("Wachhund sieht", type(dialog).__name__, "bei", round(time.monotonic() - origin_box[0], 2))
    if isinstance(dialog, AskDialog):
        dialog.list.setCurrentRow(0)
        dialog._accept.click()
        return True
    return False


dog = common.Watchdog(application, window, log, handler)
window.start()
MODEL = Path(sys.argv[1] if len(sys.argv) > 1 else r"F:\3D Dateien\Mausoleum Dragon.3mf")
origin = time.monotonic()
origin_wall = time.time()
origin_box[0] = origin
last = [origin]
gaps: list[tuple[float, float]] = []
side: list[tuple[float, float]] = []


import mmap  # noqa: E402
import struct  # noqa: E402

_shared_path = common.OUT_DIR / f"p01_{tag}.takt"
_shared_path.write_bytes(bytes(8))
_shared_file = _shared_path.open("r+b")
shared_tick = mmap.mmap(_shared_file.fileno(), 8)


def tick() -> None:
    now = time.monotonic()
    struct.pack_into("d", shared_tick, 0, now)
    if now - last[0] > 0.1:
        gaps.append((round(last[0] - origin, 2), round(now - last[0], 2)))
    last[0] = now


def side_ticker() -> None:
    previous = time.monotonic()
    while True:
        time.sleep(0.005)
        now = time.monotonic()
        if now - previous > 0.25:
            side.append((round(previous - origin, 2), round(now - previous, 2)))
        previous = now


threading.Thread(target=side_ticker, daemon=True).start()

import ctypes  # noqa: E402
from ctypes import wintypes  # noqa: E402

_kernel = ctypes.windll.kernel32
_kernel.OpenThread.restype = wintypes.HANDLE
_main_handle = _kernel.OpenThread(0x0040 | 0x0800, False, threading.main_thread().native_id)
cpu_samples: list[tuple[float, float, float]] = []


def _cpu_of_main() -> tuple[float, float]:
    created, ended, kernel, user = (wintypes.FILETIME() for _ in range(4))
    _kernel.GetThreadTimes(
        _main_handle,
        ctypes.byref(created),
        ctypes.byref(ended),
        ctypes.byref(kernel),
        ctypes.byref(user),
    )

    def seconds(value: wintypes.FILETIME) -> float:
        return ((value.dwHighDateTime << 32) | value.dwLowDateTime) / 1e7

    return seconds(user), seconds(kernel)


def cpu_sampler() -> None:
    while True:
        user, kernel = _cpu_of_main()
        cpu_samples.append((time.monotonic() - origin, user, kernel))
        time.sleep(0.1)


threading.Thread(target=cpu_sampler, daemon=True).start()
dump_log: list[str] = []


def dumper() -> None:
    count = 0
    while True:
        time.sleep(0.05)
        stalled = time.monotonic() - last[0]
        if stalled < LIMIT or count >= 60 or time.monotonic() - origin < float(os.environ.get("SONDE_DUMP_AB", "0")):
            continue
        count += 1
        at = time.monotonic() - origin
        target = dumps / f"{count:02d}_{at:06.2f}s_steht{stalled:.2f}.txt"
        result = subprocess.run(
            [PYSPY, "dump", "--native", "--pid", str(os.getpid())],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        target.write_text(
            f"exit {result.returncode}\n{result.stdout}\n--- stderr\n{result.stderr}", "utf-8"
        )
        dump_log.append(f"{target.name} exit {result.returncode} dauerte {time.monotonic() - origin - at:.2f} s")
        time.sleep(float(os.environ.get("SONDE_DUMP_PAUSE", "0.2")))


if DUMP:
    threading.Thread(target=dumper, daemon=True).start()
py_stacks: list[str] = []


def py_stacker() -> None:
    """Steht der Takt, die Python-Stapel aller Fäden festhalten (ohne py-spy)."""
    import traceback

    after = float(os.environ.get("SONDE_DUMP_AB", "0"))
    seen_gap_start = None
    while True:
        time.sleep(0.02)
        stalled = time.monotonic() - last[0]
        if time.monotonic() - origin < after or stalled < LIMIT:
            continue
        if seen_gap_start == last[0]:
            continue
        seen_gap_start = last[0]
        lines = [f"--- {time.monotonic() - origin:.2f} s, steht {stalled:.2f} s"]
        names = {thread.ident: thread.name for thread in threading.enumerate()}
        for ident, frame in sys._current_frames().items():
            if ident == threading.get_ident():
                continue
            stack = traceback.extract_stack(frame)[-6:]
            lines.append(f"  [{names.get(ident, ident)}] " + " <- ".join(
                f"{Path(entry.filename).name}:{entry.lineno} {entry.name}" for entry in reversed(stack)))
        py_stacks.append(chr(10).join(lines))


if os.environ.get("SONDE_PYSTAPEL"):
    threading.Thread(target=py_stacker, daemon=True).start()
recorder = None
if os.environ.get("SONDE_WAECHTER"):
    subprocess.Popen(
        [
            sys.executable, str(Path(__file__).resolve().parent / "p05_waechter.py"), str(os.getpid()),
            str(_shared_path), str(dumps), os.environ.get("SONDE_SCHWELLE", "0.1"),
            os.environ.get("SONDE_DUMP_AB", "0"), repr(origin),
        ]
    )
if os.environ.get("SONDE_RECORD"):
    # Fortlaufend abtasten, mit Zeitstempeln (chrometrace), ohne den Prozess
    # anzuhalten; py-spy schreibt, sobald dieser Prozess endet.
    recorder = subprocess.Popen(
        [
            PYSPY, "record", "--native", "--idle", "--threads",
            "--rate", os.environ.get("SONDE_RATE", "200"), "--format", "chrometrace",
            "-o", str(common.OUT_DIR / f"p01_{tag}.trace.json"), "--pid", str(os.getpid()),
        ],
        stdout=subprocess.DEVNULL,
        stderr=open(common.OUT_DIR / f"p01_{tag}.pyspy.txt", "w", encoding="utf-8"),
    )
    log("py-spy record gestartet; Ursprung monotonic", origin, "wall", time.time())
grab_rounds: list[tuple[float, float, float]] = []


def grabber() -> None:
    """Alle 200 ms zwanzig Griffe nach dem GIL (``time.sleep(0)``): was kostet einer?"""
    while True:
        time.sleep(0.2)
        took = []
        for _ in range(20):
            before = time.perf_counter()
            time.sleep(0)
            took.append(time.perf_counter() - before)
        grab_rounds.append((time.monotonic() - origin, sum(took) / len(took), max(took)))


if os.environ.get("SONDE_GRIFFE"):
    threading.Thread(target=grabber, daemon=True).start()
beat = QTimer()
beat.setInterval(int(os.environ.get("SONDE_TAKT_MS", "5")))
beat.timeout.connect(tick)
beat.start()
state = {"seen_busy": False}


def check() -> None:
    busy = window.session.busy
    state["seen_busy"] |= busy
    if state["seen_busy"] and not busy and time.monotonic() - origin > 2:
        application.quit()


watch = QTimer()
watch.setInterval(100)
watch.timeout.connect(check)
watch.start()
QTimer.singleShot(0, lambda: window.open_path(MODEL))
log("Umschaltintervall", sys.getswitchinterval())
entries = collections.Counter()
if os.environ.get("SONDE_EINSTIEGE"):
    _module_frame = sys._getframe()

    def _profile(frame, event, _arg):
        # Jeder Einstieg aus Qt in Python ist mindestens ein Griff nach dem GIL.
        if event == "call" and frame.f_back is _module_frame:
            code = frame.f_code
            entries[(int(time.monotonic() - origin), f"{Path(code.co_filename).name}:{code.co_qualname}")] += 1

    sys.setprofile(_profile)
application.exec()
sys.setprofile(None)
struct.pack_into("d", shared_tick, 0, -1.0)
log("fertig nach", round(time.monotonic() - origin, 1))
log("Lücken Qt-Takt über 100 ms (Beginn, Dauer):", gaps)
log("Lücken Python-Faden über 250 ms:", side)
for start, length in gaps:
    inside = [entry for entry in cpu_samples if start <= entry[0] <= start + length]
    if len(inside) >= 2:
        span = inside[-1][0] - inside[0][0]
        user = inside[-1][1] - inside[0][1]
        kernel = inside[-1][2] - inside[0][2]
        log(
            f"  Lücke {start} s, {length} s: Hauptfaden rechnete {user:.2f} s Nutzer"
            f" + {kernel:.2f} s System in {span:.2f} s"
        )
for line in dump_log:
    log("  dump", line)
for block in py_stacks:
    log(block)
if grab_rounds:
    busy_rounds = [entry for entry in grab_rounds if 8 <= entry[0] <= 30]
    means = sorted(entry[1] for entry in busy_rounds)
    tops = sorted(entry[2] for entry in busy_rounds)
    if means:
        log(
            f"Griffe nach dem GIL 8–30 s: {len(means)} Runden zu 20; mittlerer Griff Median"
            f" {means[len(means) // 2] * 1000:.2f} ms, längster Griff Median {tops[len(tops) // 2] * 1000:.2f} ms,"
            f" 95 % {tops[int(len(tops) * 0.95)] * 1000:.2f} ms"
        )
if entries:
    per_second = collections.Counter()
    for (second, _name), count in entries.items():
        per_second[second] += count
    log("Einstiege aus Qt in Python je Sekunde:", sorted(per_second.items()))
    for second in sorted(per_second):
        top = sorted(((count, name) for (sec, name), count in entries.items() if sec == second), reverse=True)[:8]
        log(f"  s{second}:", top)
if filter_calls:
    per_second = collections.Counter()
    for (second, _kind), count in filter_calls.items():
        per_second[second] += count
    log("Aufrufe des Anwendungsfilters je Sekunde:", sorted(per_second.items()))
    kinds = collections.Counter()
    for (_second, kind), count in filter_calls.items():
        kinds[kind] += count
    log("  nach Art:", kinds.most_common(15))
    log("Ereignisse 16–17 s nach Art, Klasse, Name:")
    for key, count in painted.most_common(60):
        log("   ", count, key)
log("ERGEBNIS", "längste", max((d for _a, d in gaps), default=0), "über 100 ms", len(gaps), "über 200 ms", sum(1 for _a, d in gaps if d > 0.2))
# Die Arbeiter (Schichtanalyse, Vorschaubild) abwarten wie closeEvent → release;
# os._exit mitten in ihrer Rechnung riss in der Durchsicht zweimal.
try:
    window.session.release()
except Exception as error:  # noqa: BLE001
    log("release:", error)
os._exit(0)
