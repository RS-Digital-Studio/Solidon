"""Startet ein fertiges Kundenpaket einmal: Fenster, 3D-Ansicht, sauberes Ende.

Der Starttest jedes Releases auf jeder Plattform (Entscheidung Robert,
03.10.2026). 0.5.1 bestand Suite, Paketbau, Signatur und Notarisierung — und
beendete sich auf jedem Mac 20 bis 40 Sekunden nach dem Start, weil kein
Schritt das ausgelieferte Programm je gestartet hatte.

Das Werkzeug startet die Anwendung wie beim ersten Start eines Kunden, mit
leerem Nutzerprofil, und setzt ``SOLIDON3D_START_CHECK``
(:mod:`app.ui.start_check`). Die Anwendung steht dann
:data:`~app.ui.start_check.SECONDS` lang, schreibt ihren Zustand und schließt
sich selbst. Verlangt wird:

* sie endet von selbst und mit 0 — kein Absturz, kein Hänger;
* der Bericht ist da und stammt aus genau dieser Version;
* das Hauptfenster war sichtbar;
* die 3D-Ansicht hat ein Bild gezeichnet (nicht ohne Bildschirm);
* das Absturzprotokoll des Laufs trägt keinen Absturz (``log.fatal_records``);
* kein Hilfsprozess überlebt sie (nicht im Flatpak: eigener PID-Raum, der mit
  der Anwendung endet).

Aufrufe::

    python tools/check_frozen_start.py dist                       # PyInstaller-Ausgabe
    python tools/check_frozen_start.py --executable <Pfad>        # installiert, .app oder AppImage
    python tools/check_frozen_start.py --flatpak de.rsdigital.solidon3d
    python tools/check_frozen_start.py --source                   # aus dem Quellbaum

``--offscreen`` startet ohne Bildschirm und verlangt dann keine 3D-Ansicht.
Gebraucht wird es auf dem Intel-Mac-Runner: Dort stürzt der Symboldienst des
Systems (``iconservicesagent``) in Metal ab, und jedes Programm, das ein
Systemsymbol anfragt, wartet für immer (gemessen im Lauf 37150755506). Unter
Linux startet der Aufrufer einen X-Server (``xvfb-run``).

Nur Standardbibliothek und leichte Module der Anwendung ohne Qt und Geometrie:
Das Werkzeug läuft auch in Jobs, die keine Abhängigkeiten installieren.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.branding import APP_NAME, APP_VERSION  # noqa: E402
from app.core.log import fatal_records  # noqa: E402
from app.core.paths import PROFILE_VARIABLES  # noqa: E402
from app.ui.start_check import FORMAT, REPORT_VARIABLE, SECONDS  # noqa: E402
from tools.check_frozen_helper import application, image_of, is_the_application  # noqa: E402

#: Was das Paket unter Linux aus Slicer-AppImages entpacken muss: zstd für die
#: Orca-Familie, gzip für Cura (``app.core.export.squashfs``).
IMAGE_COMPRESSIONS = ("gzip", "zstd")

#: Bis das Fenster steht, höchstens, in Sekunden. Ein Runner startet ein frisch
#: installiertes Programm langsamer als ein Kundengerät: macOS prüft beim
#: ersten Start jede Datei des Bundles, Windows Defender jede DLL.
STARTUP_SECONDS = 180.0

#: Für das eigene Ende nach dem Bericht, höchstens, in Sekunden.
END_SECONDS = 60.0

#: Die ganze Frist eines Laufs.
TOTAL_SECONDS = STARTUP_SECONDS + SECONDS + END_SECONDS


def command_for(args: argparse.Namespace, report: Path) -> list[str]:
    """Wie die Anwendung gestartet wird — so, wie der Kunde sie hat."""
    if args.flatpak:
        command = ["flatpak", "run", f"--env={REPORT_VARIABLE}={report}"]
        if args.offscreen:
            command.append("--env=QT_QPA_PLATFORM=offscreen")
        return [*command, args.flatpak]
    if args.source:
        return [sys.executable, "-m", "app.ui.app"]
    if args.executable:
        path = Path(args.executable)
        if path.suffix == ".app":
            path = path / "Contents" / "MacOS" / APP_NAME
        return [str(path)]
    return [str(application(Path(args.dist), APP_NAME))]


def package_root(args: argparse.Namespace) -> Path | None:
    """Der Paketbaum, der beim Start unverändert bleiben muss — wo er beschreibbar ist.

    AppImage und Flatpak sind schreibgeschützte Abbilder, der Quellbaum ist
    kein Paket.
    """
    if args.flatpak or args.source:
        return None
    if args.executable:
        path = Path(args.executable)
        if path.suffix == ".AppImage":
            return None
        return path if path.suffix == ".app" else path.parent
    dist = Path(args.dist)
    return dist / f"{APP_NAME}.app" if sys.platform == "darwin" else dist / APP_NAME


def tree_state(root: Path | None) -> dict[str, tuple[int, int]]:
    """Jede Datei des Paketbaums mit Größe und Änderungszeit."""
    if root is None or not root.is_dir():
        return {}
    state = {}
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            info = path.stat()
            state[path.relative_to(root).as_posix()] = (info.st_size, info.st_mtime_ns)
    return state


def tree_changes(
    before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]
) -> list[str]:
    """Was die Anwendung in ihrem eigenen Baum angelegt, entfernt oder geändert hat."""
    return sorted(
        set(before) ^ set(after)
        | {name for name in before.keys() & after.keys() if before[name] != after[name]}
    )


def environment_for(args: argparse.Namespace, report: Path, profile: Path) -> dict[str, str]:
    """Umgebung eines ersten Starts: leeres Profil, Starttest verlangt."""
    env = dict(os.environ)
    env[REPORT_VARIABLE] = str(report)
    if args.offscreen:
        env["QT_QPA_PLATFORM"] = "offscreen"
    else:
        env.pop("QT_QPA_PLATFORM", None)
    # Das Flatpak nimmt sein Profil aus ~/.var/app; ein umgebogenes HOME
    # käme im Sandkasten nicht an. Auf dem Runner ist es ohnehin leer.
    if not args.flatpak:
        for name in PROFILE_VARIABLES:
            env[name] = str(profile)
    # Der Runner hat kein FUSE; das AppImage packt sich dann selbst aus.
    if args.executable and Path(args.executable).suffix == ".AppImage":
        env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    return env


def exit_text(code: int) -> str:
    """Ein Prozessende in Worten: Signal unter POSIX, NTSTATUS unter Windows."""
    if code < 0:
        try:
            return f"Signal {signal.Signals(-code).name}"
        except ValueError:
            return f"Signal {-code}"
    if code > 0xFFFF:
        return f"Code 0x{code & 0xFFFFFFFF:08X}"
    return f"Code {code}"


def judge(
    returncode: int | None,
    report: dict[str, Any] | None,
    *,
    offscreen: bool,
    crash_text: str,
    helpers_alive: list[int],
    tree_changed: list[str],
    linux: bool = False,
) -> list[str]:
    """Was am Lauf nicht stimmt — leer, wenn er bestanden ist."""
    problems: list[str] = []
    if returncode is None:
        problems.append(
            f"Die Anwendung endete nicht binnen {TOTAL_SECONDS:.0f} s: Sie hängt. "
            "Stapel mit sample (macOS) oder py-spy dump --native holen."
        )
    elif returncode != 0:
        problems.append(
            f"Die Anwendung endete mit {exit_text(returncode)}. "
            "Absturzbericht des Systems und Protokoll lesen."
        )
    if report is None:
        problems.append(
            f"Kein Bericht: Das Fenster stand keine {SECONDS:.0f} s. "
            "Ausgabe und Protokoll der Anwendung unten lesen."
        )
        return problems
    if report.get("format") != FORMAT:
        problems.append(f"Bericht in Fassung {report.get('format')!r}, erwartet {FORMAT}.")
    if report.get("version") != APP_VERSION:
        problems.append(
            f"Gestartet wurde {report.get('version')!r}, erwartet {APP_VERSION}: falsches Paket."
        )
    if not report.get("window", {}).get("visible"):
        problems.append("Das Hauptfenster war nicht sichtbar.")
    renderer = report.get("renderer", {})
    if not offscreen:
        if not renderer.get("present"):
            problems.append(
                "Die 3D-Ansicht fehlt: kein Grafikadapter. Vulkan, Metal oder "
                "Direct 3D 12 auf dem Prüfrechner einrichten (lavapipe, WARP)."
            )
        elif "error" in renderer:
            problems.append(f"Die 3D-Ansicht zeichnet nicht: {renderer['error']}")
        elif not renderer.get("brightest"):
            problems.append("Die 3D-Ansicht zeichnet ein schwarzes Bild.")
    # Was Solidon abgefangen und überlebt hat — eine COM-Ausnahme, ein
    # Treibereintrag — bleibt mit dem Vermerk des geordneten Endes in der
    # Datei und hält den Start nicht an; ein Absturz schon (``log.fatal_records``).
    fatal = fatal_records(crash_text).strip()
    if fatal:
        problems.append("Das Absturzprotokoll des Laufs trägt einen Absturz:\n" + fatal[:2000])
    if helpers_alive:
        problems.append(
            f"Hilfsprozesse leben nach dem Ende weiter: {helpers_alive}. "
            "kernel_process.shutdown am Ende der Anwendung prüfen."
        )
    if tree_changed:
        problems.append(
            "Die Anwendung hat in ihren eigenen Ordner geschrieben — nach einer "
            f"Signatur bräche das sie: {tree_changed[:10]}"
        )
    modules = [str(name).casefold() for name in report.get("input_modules", ())]
    if linux and not any("ibus" in name for name in modules):
        problems.append(
            "Das Paket bringt kein IBus-Eingabemodul mit (platforminputcontexts: "
            f"{modules}): Fcitx- und IBus-Nutzer tippen ins Leere (RM-062). "
            "Die Qt-Plugins im Paket prüfen."
        )
    compressions = [str(name) for name in report.get("image_compressions", ())]
    missing = [name for name in IMAGE_COMPRESSIONS if name not in compressions]
    if linux and missing:
        problems.append(
            f"Das Paket entpackt {', '.join(missing)} nicht (image_compressions: "
            f"{compressions}): Unter Linux fehlen dann die Drucker der Slicer-AppImages "
            "(RM-549, RM-599). CPythons _zstd und zlib im Paket prüfen."
        )
    return problems


def run(command: list[str], env: dict[str, str], output: Path) -> int | None:
    """Startet und wartet die ganze Frist; ``None`` heißt: hängt, abgeschossen."""
    with output.open("wb") as stream:
        process = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT)
        try:
            return process.wait(timeout=TOTAL_SECONDS)
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                    capture_output=True,
                    check=False,
                )
            process.kill()
            process.wait(timeout=30)
            return None


def survivors(report: dict[str, Any] | None, *, flatpak: bool) -> list[int]:
    """Hilfsprozesse aus dem Bericht, die nach dem Ende noch dieselbe Anwendung sind."""
    if report is None or flatpak:
        return []
    executable = Path(report.get("executable", ""))
    alive = []
    for pid in report.get("helpers", []):
        image = image_of(int(pid))
        if image is not None and is_the_application(image, executable):
            alive.append(int(pid))
    return alive


def read_text(path: str | None) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def check(args: argparse.Namespace) -> int:
    base = Path.home() if args.flatpak else None
    with tempfile.TemporaryDirectory(prefix="solidon-start-", dir=base) as folder:
        work = Path(folder)
        report_path = work / "start-check.json"
        profile = work / "profile"
        profile.mkdir()
        output = work / "output.txt"
        command = command_for(args, report_path)
        if not (args.flatpak or args.source or Path(command[0]).is_file()):
            print(f"::error::Die Anwendung fehlt: {command[0]}. Erst bauen oder installieren.")
            return 1
        root = package_root(args)
        before = tree_state(root)
        print(f"Starte: {' '.join(command)}", flush=True)
        began = time.monotonic()
        returncode = run(command, environment_for(args, report_path, profile), output)
        took = time.monotonic() - began
        changed = tree_changes(before, tree_state(root))
        report: dict[str, Any] | None = None
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
        crash_text = read_text(report.get("crash_file")) if report else ""
        alive = survivors(report, flatpak=bool(args.flatpak))
        problems = judge(
            returncode,
            report,
            offscreen=args.offscreen,
            crash_text=crash_text,
            helpers_alive=alive,
            tree_changed=changed,
            linux=sys.platform.startswith("linux"),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2) if report else "(kein Bericht)")
        print(
            f"Ende nach {took:.1f} s mit {exit_text(returncode) if returncode is not None else '—'}"
        )
        if problems:
            print("\n--- Ausgabe der Anwendung (Ende)")
            print(output.read_text(encoding="utf-8", errors="replace")[-6000:])
            if report:
                print("--- Protokoll (Ende)")
                print(read_text(report.get("log"))[-6000:])
            for problem in problems:
                print(f"::error::{problem}" if os.environ.get("GITHUB_ACTIONS") else problem)
            return 1
        print("Starttest bestanden.")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("dist", nargs="?", help="PyInstaller-Ausgabe mit der gebauten Anwendung")
    target.add_argument("--executable", help="installierte Anwendung, .app oder AppImage")
    target.add_argument("--flatpak", help="Kennung eines installierten Flatpaks")
    target.add_argument("--source", action="store_true", help="aus dem Quellbaum starten")
    parser.add_argument("--offscreen", action="store_true", help="ohne Bildschirm starten")
    return check(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
