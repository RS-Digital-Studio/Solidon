"""Misst, ob Rückrufe und die wgpu-Adapterfrage unter Hardened Runtime laufen.

Werkzeug auf Zeit für RM-104: Auf Intel-Macs startet das mit Developer ID und
Hardened Runtime (ohne Entitlements) signierte Paket nicht, ad hoc signiert
schon. Verdacht: Unter Hardened Runtime verweigert macOS beschreib- und
ausführbaren Speicher, den cffi- und ctypes-Rückrufe auf x86_64 brauchen,
auf arm64 nicht (dort Trampolinseiten). wgpu fragt den Adapter über
cffi-Rückrufe; der Starttest auf dem Intel-Runner baut offscreen keine
Ansicht und hat das nie berührt.

Gefahren wird ein eigenständiges Python (python-build-standalone über uv,
verschiebbar) in Varianten der Signatur; je Prüfung ein eigener Prozess, damit
ein Abbruch durch den Kern die übrigen nicht mitnimmt. Jede Prüfung meldet,
unter welcher Signatur das laufende Abbild tatsächlich steht.

Aufruf als Treiber: python3 hardened_probe.py treiber
Als Prüfling (vom Treiber): <python> hardened_probe.py <cffi|ctypes|wgpu>
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = "3.14.8"
PACKAGES = ["cffi==2.1.1", "wgpu==0.32.0"]
VARIANTS: dict[str, list[str] | None] = {
    "wie-geliefert": None,
    "runtime": [],
    "runtime-dlv": ["disable-library-validation"],
    "runtime-dlv-mem": ["disable-library-validation", "allow-unsigned-executable-memory"],
    "runtime-dlv-jit": ["disable-library-validation", "allow-jit"],
}
TESTS = ("cffi", "ctypes", "wgpu")


def own_image() -> dict[str, str]:
    """Pfad und Signaturangaben des Abbilds, das gerade läuft."""
    path = subprocess.run(
        ["ps", "-o", "comm=", "-p", str(os.getpid())], capture_output=True, text=True
    ).stdout.strip()
    sign = subprocess.run(
        ["codesign", "-dvvv", "--entitlements", "-", path], capture_output=True, text=True
    )
    flags = [line for line in (sign.stdout + sign.stderr).splitlines() if "flags=" in line or "cs." in line]
    return {"image": path, "signature": " | ".join(flags)}


def probe(test: str) -> int:
    result: dict[str, object] = {"test": test, "machine": platform.machine(), **own_image()}
    try:
        if test == "cffi":
            import cffi

            ffi = cffi.FFI()
            callback = ffi.callback("int(int)", lambda value: value + 1)
            result["value"] = f"cffi {cffi.__version__}, Rückruf {callback!r}"
        elif test == "ctypes":
            import ctypes

            function = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)(lambda value: value + 1)
            result["value"] = function(41)
        else:
            import wgpu

            adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
            result["value"] = None if adapter is None else dict(adapter.info)
        result["ok"] = True
    except BaseException as problem:  # gemessen wird gerade der Fehler
        result["ok"] = False
        result["error"] = f"{type(problem).__name__}: {problem}"
    print(json.dumps(result, default=str), flush=True)
    return 0


def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, **kwargs)  # type: ignore[call-overload]


def driver() -> int:
    out = Path("diag-out/hardened").resolve()
    out.mkdir(parents=True, exist_ok=True)
    log: list[str] = []

    def note(text: str) -> None:
        log.append(text)
        print(text, flush=True)

    note(run(["sw_vers"]).stdout)
    note(run(["sysctl", "-n", "machdep.cpu.brand_string"]).stdout)
    run([sys.executable, "-m", "pip", "install", "-q", "uv"])
    installed = run([sys.executable, "-m", "uv", "python", "install", VERSION])
    note(installed.stdout + installed.stderr)
    # Nur ein von uv verwaltetes Python (python-build-standalone): Das
    # Framework-Python von python.org springt in sein eigenes, mit
    # Entitlements signiertes Python.app, und dann misst man dessen Signatur.
    managed = Path(run([sys.executable, "-m", "uv", "python", "dir"]).stdout.strip())
    candidates = sorted(managed.glob(f"cpython-{VERSION}-macos-*/bin/python3.14"))
    if not candidates:
        raise SystemExit(f"kein verwaltetes Python {VERSION} unter {managed}")
    real = candidates[0].resolve()
    prefix = real.parent.parent
    note(f"Interpreter {real}, Präfix {prefix}")
    note(run(["otool", "-L", str(real)]).stdout)
    base = Path("/tmp/hr-base")
    shutil.rmtree(base, ignore_errors=True)
    shutil.copytree(prefix, base, symlinks=True)
    for marker in base.glob("lib/python*/EXTERNALLY-MANAGED"):
        marker.unlink()
    python = base / "bin" / real.name
    note(run([str(python), "-m", "ensurepip"]).stderr[-500:])
    pip = run([str(python), "-m", "pip", "install", *PACKAGES])
    note(pip.stdout[-1500:] + pip.stderr[-1500:])

    summary: dict[str, dict[str, object]] = {}
    for name, entitlements in VARIANTS.items():
        folder = Path(f"/tmp/hr-{name}")
        shutil.rmtree(folder, ignore_errors=True)
        shutil.copytree(base, folder, symlinks=True)
        executable = folder / "bin" / real.name
        if entitlements is not None:
            plist = Path(f"/tmp/hr-{name}.plist")
            keys = "".join(f"<key>com.apple.security.cs.{key}</key><true/>" for key in entitlements)
            plist.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                f'<plist version="1.0"><dict>{keys}</dict></plist>\n',
                encoding="utf-8",
            )
            signed = run(
                ["codesign", "--force", "--options", "runtime", "--entitlements", str(plist),
                 "--sign", "-", str(executable)]
            )
            note(f"{name}: codesign Exit {signed.returncode} {signed.stderr.strip()}")
        results: dict[str, object] = {}
        for test in TESTS:
            try:
                done = run([str(executable), __file__, test], timeout=180)
            except subprocess.TimeoutExpired:
                results[test] = {"ok": False, "error": "Zeitüberschreitung nach 180 s"}
                continue
            lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
            entry: dict[str, object] = json.loads(lines[-1]) if lines else {}
            entry["exit"] = done.returncode
            if not lines:
                entry["stderr"] = done.stderr[-1500:]
            results[test] = entry
            note(f"{name} {test}: {json.dumps(entry, default=str)[:600]}")
        summary[name] = results

    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (out / "log.txt").write_text("\n".join(log), encoding="utf-8")
    table = ["| Variante | " + " | ".join(TESTS) + " |", "|---|" + "---|" * len(TESTS)]
    for name, results in summary.items():
        cells = []
        for test in TESTS:
            entry = results.get(test, {})
            cells.append(
                "ok" if isinstance(entry, dict) and entry.get("ok")
                else str(entry.get("error") or f"Exit {entry.get('exit')}")[:80]
                if isinstance(entry, dict) else "?"
            )
        table.append(f"| {name} | " + " | ".join(cells) + " |")
    step = os.environ.get("GITHUB_STEP_SUMMARY")
    if step:
        with open(step, "a", encoding="utf-8") as handle:
            handle.write(f"## {platform.machine()}\n\n" + "\n".join(table) + "\n")
    print("\n".join(table))
    return 0


if __name__ == "__main__":
    raise SystemExit(driver() if sys.argv[1] == "treiber" else probe(sys.argv[1]))
