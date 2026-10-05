"""Misst den Start des veröffentlichten Mac-Pakets wie ein Doppelklick.

Werkzeug auf Zeit für eine Kundenmeldung zu 0.5.2: „ohne codesign --sign -
startet es nicht“. Gestartet wird über LaunchServices (``open``), nicht über
die Binärdatei, damit Gatekeepers Prüfung beim ersten Start mitläuft. Je
Start werden die Zeitpunkte gemessen, an denen der Prozess erscheint, Python
läuft (Absturzprotokoll angelegt), das Fenster steht (``started`` im
Protokoll) und der Starttest berichtet.

Aufruf: ``python .claude/.state/mac-start-2026-10-05/mac_start.py <arch> <vorher-prüfen: ja|nein>``
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

APP = Path("/Applications/Solidon3D.app")
HOME = Path.home()
OUT = Path("diag-out").resolve()
LOGS = HOME / "Library" / "Logs" / "Solidon3D"
USER_DIRS = (
    LOGS,
    HOME / "Library" / "Application Support" / "Solidon3D",
    HOME / "Library" / "Caches" / "Solidon3D",
    HOME / "Library" / "Preferences" / "Solidon3D",
)


def run(command: list[str], label: str, timeout: float = 900) -> str:
    started = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    took = time.monotonic() - started
    text = f"$ {' '.join(command)}\n(Exit {result.returncode}, {took:.1f} s)\n{result.stdout}{result.stderr}"
    (OUT / f"{label}.txt").write_text(text, encoding="utf-8")
    print(text[:3000], flush=True)
    return result.stdout + result.stderr


def pids() -> list[str]:
    return subprocess.run(["pgrep", "-x", "Solidon3D"], capture_output=True, text=True).stdout.split()


def measure(label: str, offscreen: bool, limit: float = 420.0) -> dict[str, object]:
    for path in USER_DIRS:
        shutil.rmtree(path, ignore_errors=True)
    report = OUT / f"report-{label}.json"
    report.unlink(missing_ok=True)
    env = {"SOLIDON3D_START_CHECK": str(report)}
    if offscreen:
        env["QT_QPA_PLATFORM"] = "offscreen"
    for key, value in env.items():
        subprocess.run(["launchctl", "setenv", key, value], check=True)
    since = time.strftime("%Y-%m-%d %H:%M:%S")
    command = ["open"]
    for key, value in env.items():
        command += ["--env", f"{key}={value}"]
    command.append(str(APP))
    wall = time.time()
    start = time.monotonic()
    opened = subprocess.run(command, capture_output=True, text=True)
    marks: dict[str, float] = {"open_returned": round(time.monotonic() - start, 1)}
    if opened.returncode:
        marks["open_exit"] = opened.returncode
        print(opened.stderr, flush=True)
    while time.monotonic() - start < limit:
        now = round(time.monotonic() - start, 1)
        alive = pids()
        if alive and "process" not in marks:
            marks["process"] = now
        if "python" not in marks and LOGS.is_dir() and any(LOGS.glob("crash-*")):
            marks["python"] = now
        log = LOGS / "app.log"
        if "window" not in marks and log.is_file():
            if " started" in log.read_text(encoding="utf-8", errors="replace"):
                marks["window"] = now
        if "report" not in marks and report.is_file():
            marks["report"] = now
        if "process" in marks and not alive:
            marks["ended"] = now
            break
        time.sleep(0.25)
    alive = pids()
    if alive:
        marks["still_running_after"] = limit
        run(["sample", alive[0], "5"], f"sample-{label}", timeout=60)
        subprocess.run(["pkill", "-9", "-x", "Solidon3D"])
        time.sleep(2)
    for key in env:
        subprocess.run(["launchctl", "unsetenv", key])
    folder = OUT / f"logs-{label}"
    if LOGS.is_dir():
        shutil.copytree(LOGS, folder, dirs_exist_ok=True)
    reports = HOME / "Library" / "Logs" / "DiagnosticReports"
    if reports.is_dir():
        for item in reports.glob("*Solidon*"):
            if item.stat().st_mtime > wall - 5:
                shutil.copy2(item, OUT / f"{label}-{item.name}")
    run(
        [
            "log", "show", "--style", "compact", "--start", since, "--predicate",
            'process == "syspolicyd" OR process == "XprotectService" OR process == "amfid" '
            'OR process == "taskgated" OR process == "Solidon3D" '
            'OR (process == "kernel" AND eventMessage CONTAINS[c] "Solidon")',
        ],
        f"systemlog-{label}",
        timeout=300,
    )
    print(f"== {label}: {json.dumps(marks)}", flush=True)
    return marks


def main() -> int:
    arch, assess_first = sys.argv[1], sys.argv[2] == "ja"
    OUT.mkdir(exist_ok=True)
    offscreen = arch == "x86_64"
    package = f"Solidon3D-0.5.2-macos-{arch}.pkg"
    run(["sw_vers"], "system")
    run(["sysctl", "hw.ncpu", "hw.memsize", "machdep.cpu.brand_string"], "hardware")
    run(["curl", "-fsSL", "-o", package, f"https://solidon3d.de/dl/{package}"], "download")
    run(["shasum", "-a", "256", package], "sha256")
    stamp = f"{int(time.time()):x}"
    run(["xattr", "-w", "com.apple.quarantine", f"0083;{stamp};Safari;", package], "quarantine")
    run(["sudo", "installer", "-pkg", package, "-target", "/"], "installer")
    run(["bash", "-c", f"xattr -lr '{APP}' | grep -c quarantine"], "quarantine-installed")
    run(["du", "-sh", str(APP)], "size")
    run(["bash", "-c", f"find '{APP}' -type f | wc -l; find '{APP}' -type f -print0 | xargs -0 file | grep -c Mach-O"], "files")
    run(["codesign", "-dvvv", "--entitlements", "-", str(APP)], "codesign-before")
    results: dict[str, object] = {"arch": arch, "assess_first": assess_first}
    if assess_first:
        run(["spctl", "--assess", "--type", "execute", "-vv", str(APP)], "spctl-first")
    results["first"] = measure("first", offscreen)
    results["second"] = measure("second", offscreen)
    run(["spctl", "--assess", "--type", "execute", "-vv", str(APP)], "spctl-after")
    run(["sudo", "codesign", "--force", "--deep", "--sign", "-", str(APP)], "codesign-adhoc")
    run(["codesign", "-dvvv", str(APP)], "codesign-after")
    results["adhoc"] = measure("adhoc", offscreen)
    (OUT / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"```\n{json.dumps(results, indent=2)}\n```\n")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
