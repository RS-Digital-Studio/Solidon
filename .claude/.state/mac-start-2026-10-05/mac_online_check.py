"""Hält das Developer-ID-Paket an Apples Online-Prüfungen fest? (RM-104)

Werkzeug auf Zeit für die Kundenmeldung „startet nur ad hoc signiert“ auf zwei
Intel-Macs mit macOS 26. Ein Developer-ID-signiertes Programm trägt ein
Zertifikat, dessen Widerruf macOS online prüfen kann (OCSP), ein ad hoc
signiertes nicht. Verwirft eine Firewall oder ein Proxy diese Anfragen stumm,
wartet jede Prüfung bis zur Zeitgrenze.

Nachgestellt wird das mit ``/etc/hosts`` auf eine TEST-NET-Adresse und einer
pf-Regel, die alles dorthin stumm verwirft. Je Variante wird gemessen, wann
der Prozess erscheint, wann Python läuft (Absturzdatei angelegt), wann das
Protokoll beginnt, wann die Profile geladen sind (nach dem Ladebildschirm)
und wann die Anwendung ``started`` meldet. Dazu das Systemprotokoll von
trustd, amfid, syspolicyd und XprotectService.

Aufruf: ``python3 mac_online_check.py <arch> <reihenfolge>`` mit der
Reihenfolge als Komma-Liste aus ``gesperrt``, ``offen``, ``adhoc-gesperrt``.
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
SINK = "192.0.2.1"
HOSTS = (
    "ocsp.apple.com",
    "ocsp2.apple.com",
    "valid.apple.com",
    "crl.apple.com",
    "certs.apple.com",
    "api.apple-cloudkit.com",
    "ocsp.digicert.com",
    "timestamp.apple.com",
)
MARKER = "# solidon-sperre"


def run(command: list[str], label: str, timeout: float = 600) -> str:
    started = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        text = f"$ {' '.join(command)}\n(Exit {result.returncode}, {time.monotonic() - started:.1f} s)\n{result.stdout}{result.stderr}"
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired as expired:
        text = f"$ {' '.join(command)}\n(Zeitgrenze {timeout} s)\n{expired.stdout or ''}{expired.stderr or ''}"
        output = ""
    (OUT / f"{label}.txt").write_text(text, encoding="utf-8")
    print(text[:2500], flush=True)
    return output


def pids() -> list[str]:
    return subprocess.run(["pgrep", "-x", "Solidon3D"], capture_output=True, text=True).stdout.split()


def flush_dns() -> None:
    subprocess.run(["sudo", "dscacheutil", "-flushcache"])
    subprocess.run(["sudo", "killall", "-HUP", "mDNSResponder"])


def block(on: bool) -> None:
    hosts = Path("/etc/hosts").read_text(encoding="utf-8").splitlines()
    kept = [line for line in hosts if MARKER not in line]
    if on:
        kept += [f"{SINK} {host} {MARKER}" for host in HOSTS]
    scratch = OUT / "hosts.neu"
    scratch.write_text("\n".join(kept) + "\n", encoding="utf-8")
    subprocess.run(["sudo", "cp", str(scratch), "/etc/hosts"], check=True)
    rules = OUT / "pf.regeln"
    rules.write_text(f"block drop out quick inet from any to {SINK}\n" if on else "", encoding="utf-8")
    subprocess.run(["sudo", "pfctl", "-a", "com.apple/solidon", "-f", str(rules)])
    if on:
        subprocess.run(["sudo", "pfctl", "-E"])
    flush_dns()
    # Ob die Sperre greift: curl muss an der Zeitgrenze scheitern, nicht sofort.
    run(["curl", "-sS", "-m", "8", "-o", "/dev/null", "-w", "%{http_code}", "http://ocsp.apple.com/"],
        f"sperre-{'an' if on else 'aus'}-probe", timeout=30)


def measure(label: str, limit: float = 300.0) -> dict[str, object]:
    for path in USER_DIRS:
        shutil.rmtree(path, ignore_errors=True)
    since = time.strftime("%Y-%m-%d %H:%M:%S")
    wall = time.time()
    start = time.monotonic()
    opened = subprocess.run(
        ["open", "--stdout", str(OUT / f"{label}-stdout.txt"), "--stderr", str(OUT / f"{label}-stderr.txt"),
         "-a", str(APP)],
        capture_output=True, text=True, timeout=600,
    )
    marks: dict[str, object] = {"open_returned": round(time.monotonic() - start, 1)}
    if opened.returncode:
        marks["open_exit"] = opened.returncode
    sampled = False
    while time.monotonic() - start < limit:
        now = round(time.monotonic() - start, 1)
        alive = pids()
        if alive and "process" not in marks:
            marks["process"] = now
        if "python" not in marks and LOGS.is_dir() and any(LOGS.glob("crash-*.log")):
            marks["python"] = now
        log = LOGS / "app.log"
        text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        if text and "log" not in marks:
            marks["log"] = now
        if "material profiles" in text and "profiles" not in marks:
            marks["profiles"] = now
        if " started" in text and "started" not in marks:
            marks["started"] = now
            break
        if "profiles" in marks and now - float(marks["profiles"]) > 20:
            break  # Intel hängt danach am Symboldienst des Runners (RM-104)
        if alive and not sampled and now > 45 and "python" not in marks:
            run(["sample", alive[0], "3"], f"{label}-sample-45s", timeout=60)
            sampled = True
        time.sleep(0.25)
    alive = pids()
    if alive:
        run(["sample", alive[0], "3"], f"{label}-sample-ende", timeout=60)
        subprocess.run(["pkill", "-9", "-x", "Solidon3D"])
        time.sleep(3)
    marks["seconds_total"] = round(time.monotonic() - start, 1)
    if LOGS.is_dir():
        shutil.copytree(LOGS, OUT / f"{label}-logs", dirs_exist_ok=True)
    reports = HOME / "Library" / "Logs" / "DiagnosticReports"
    if reports.is_dir():
        for item in reports.glob("*Solidon*"):
            if item.stat().st_mtime > wall - 5:
                shutil.copy2(item, OUT / f"{label}-{item.name}")
    run(
        ["log", "show", "--style", "compact", "--info", "--start", since, "--predicate",
         'process == "trustd" OR process == "amfid" OR process == "syspolicyd" '
         'OR process == "XprotectService" OR process == "Solidon3D" '
         'OR (process == "kernel" AND (eventMessage CONTAINS[c] "Solidon" OR eventMessage CONTAINS "AMFI"))'],
        f"{label}-systemlog", timeout=300,
    )
    print(f"== {label}: {json.dumps(marks)}", flush=True)
    return marks


def main() -> int:
    arch, order = sys.argv[1], sys.argv[2].split(",")
    OUT.mkdir(exist_ok=True)
    package = f"Solidon3D-0.5.3-macos-{arch}.pkg"
    run(["sw_vers"], "system")
    run(["csrutil", "status"], "sip")
    run(["curl", "-fsSL", "-o", package, f"https://solidon3d.de/dl/{package}"], "download")
    stamp = f"{int(time.time()):x}"
    run(["xattr", "-w", "com.apple.quarantine", f"0083;{stamp};Safari;", package], "quarantine")
    run(["sudo", "installer", "-pkg", package, "-target", "/"], "installer")
    run(["codesign", "-dvv", str(APP)], "codesign-vorher")
    results: dict[str, object] = {"arch": arch, "order": order}
    for variant in order:
        adhoc = variant.startswith("adhoc")
        if adhoc and "adhoc_signed" not in results:
            block(False)
            run(["sudo", "codesign", "--force", "--deep", "--sign", "-", str(APP)], "codesign-adhoc")
            results["adhoc_signed"] = True
        block(variant.endswith("gesperrt"))
        results[variant] = measure(variant)
    block(False)
    (OUT / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"```\n{json.dumps(results, indent=2)}\n```\n")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
