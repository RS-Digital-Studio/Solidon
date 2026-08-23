"""Prüft, ob die Umgebung dem festgeschriebenen Stand entspricht — und stellt ihn her.

Warum es das Werkzeug gibt: `constraints.txt` schreibt fest, *in welcher*
Version ein Paket installiert wird. Nur half das nichts, solange niemand
nachsah. Wer `pip install -e ".[dev,geom,ui,agent,brep]"` ohne das `-c` tippt,
bekommt andere Versionen als die, gegen die die Suite grün ist — am 06.08.2026
zog ein frischer Klon numpy 2.5, und sechzehn Tests fielen um, ohne dass eine
Zeile Code sich geändert hatte. Bei mehreren Leuten am selben Repository ist
das kein Einzelfall, sondern der Normalfall.

Das Werkzeug beantwortet zwei Fragen und braucht dafür kein Netz:

    python tools/check_env.py              # stimmt die Umgebung? Exit 0 oder 1
    python tools/check_env.py --install    # sie stimmen machen (braucht Netz)

Es läuft **auch ohne die virtuelle Umgebung** und nur mit der
Standardbibliothek — sonst könnte es im frischen Klon nicht sagen, dass die
Umgebung fehlt. Genau deshalb ruft der Sitzungsstart-Hook es auf.

Was es nicht prüft: die externen Programme (OpenSCAD, Slicer, Ollama). Die
werden nach §36 nur aufgerufen, nie mitgeliefert, und ihre Abwesenheit ist
kein Fehler, sondern ein abgeschalteter Weg.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
CONSTRAINTS: Final = ROOT / "constraints.txt"
PYPROJECT: Final = ROOT / "pyproject.toml"

#: Die Gruppen, die ein Arbeitsplatz braucht — dieselben wie in CLAUDE.md.
EXTRAS: Final = "dev,geom,ui,agent,brep"

#: Ab wann die Versionspflege fällig ist. Der wöchentliche CI-Lauf „Neueste
#: Versionen" meldet gebrochene Versionen; er sagt aber niemandem, dass es
#: etwas Neues *gäbe*. Nach einem Vierteljahr ohne Nachziehen ist der Satz
#: alt genug, dass ein Sprung wehtut — deshalb die Erinnerung.
DAYS_UNTIL_MAINTENANCE: Final = 90

_LINE = re.compile(r"^([A-Za-z0-9._-]+)==([^\s;#]+)")
#: Eine Obergrenze in `pyproject.toml`, etwa `trimesh>=4.4,<5`.
_LIMIT = re.compile(r"^\s*[\"']?([A-Za-z0-9._-]+)[^\"']*?<=?\s*([0-9][0-9.]*)")


def normal(name: str) -> str:
    """Paketnamen nach PEP 503 vergleichbar machen (`svg.path` = `svg-path`)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def venv_python() -> Path | None:
    """Der Interpreter der Projektumgebung, falls es sie gibt."""
    for candidate in (
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ):
        if candidate.exists():
            return candidate
    return None


def pinned() -> dict[str, tuple[str, str]]:
    """`constraints.txt` als Zuordnung normalisierter Name → (Name, Version)."""
    result: dict[str, tuple[str, str]] = {}
    for line in CONSTRAINTS.read_text(encoding="utf-8").splitlines():
        match = _LINE.match(line.strip())
        if match:
            name, version = match.group(1), match.group(2)
            result[normal(name)] = (name, version)
    return result


def installed(python: Path) -> dict[str, str] | None:
    """Was in dieser Umgebung liegt — oder ``None``, wenn sie nicht antwortet."""
    source = (
        "import json,importlib.metadata as m;"
        "print(json.dumps({d.metadata['Name']: d.version for d in m.distributions()"
        " if d.metadata['Name']}))"
    )
    try:
        result = subprocess.run(
            [str(python), "-c", source],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ROOT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        raw: dict[str, str] = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return {normal(name): version for name, version in raw.items()}


def required_version() -> tuple[int, int]:
    """Die Untergrenze aus ``requires-python`` als Zahlenpaar."""
    with PYPROJECT.open("rb") as handle:
        data = tomllib.load(handle)
    raw = str(data["project"]["requires-python"]).strip()
    major, minor = raw.removeprefix(">=").strip().split(".")[:2]
    return int(major), int(minor)


def interpreter_version(python: Path) -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            [str(python), "-c", "import sys;print(f'{sys.version_info[0]} {sys.version_info[1]}')"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        major, minor = result.stdout.split()
    except ValueError:
        return None
    return int(major), int(minor)


def venv_name() -> str:
    """Der Interpreteraufruf, wie man ihn hier tippt."""
    return ".venv\\Scripts\\python.exe" if sys.platform == "win32" else ".venv/bin/python"


def setup_command(with_venv: bool) -> str:
    """Der Befehl, der die Umgebung herstellt — plattformgerecht geschrieben."""
    python = venv_name()
    create = (
        ""
        if with_venv
        else f"{'python' if sys.platform == 'win32' else 'python3'} -m venv .venv && "
    )
    return f'{create}{python} -m pip install -c constraints.txt -e ".[{EXTRAS}]"'


def version_tuple(version: str) -> tuple[int, ...]:
    """Eine Version als Zahlenfolge, so weit sie sich lesen lässt.

    Absichtlich kein vollständiger PEP-440-Vergleich: Gebraucht wird nur die
    Frage, ob eine angebotene Version unter einer Obergrenze bleibt, und die
    Obergrenzen dieses Projekts sind schlichte Zahlen (`<5`).
    """
    parts: list[int] = []
    for piece in version.split("."):
        if piece.isdigit():
            parts.append(int(piece))
            continue
        # „0rc1" zählt als 0, „post0" gar nicht — was hinter der ersten
        # Nicht-Ziffer steht, ist Vorab- oder Nachlaufkennung, keine Stelle.
        leading = ""
        for char in piece:
            if not char.isdigit():
                break
            leading += char
        if leading:
            parts.append(int(leading))
        break
    return tuple(parts)


def upper_bounds() -> dict[str, str]:
    """Pakete aus `pyproject.toml`, die eine Version ausdrücklich ausschließen.

    `trimesh>=4.4,<5` ist keine Nachlässigkeit, sondern eine Entscheidung: Der
    Major-Sprung wird als eigene Migration gemacht, weil der erste frische
    CI-Lauf mit trimesh 5.0.0 rot war. Wer nach Neuem sucht, muss solche
    Grenzen kennen — sonst schlägt er etwas vor, das absichtlich nicht kommt.
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    limits: dict[str, str] = {}
    for line in text.splitlines():
        if "<" not in line or line.lstrip().startswith("#"):
            continue
        match = _LIMIT.match(line)
        if match:
            limits[normal(match.group(1))] = match.group(2)
    return limits


def age_in_days() -> int | None:
    """Wie lange `constraints.txt` unverändert ist — nach Git, sonst nach Datei.

    Der Git-Zeitstempel ist der richtige: Die Änderungszeit im Dateisystem
    sagt nach einem frischen Klon nur, wann geklont wurde.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", CONSTRAINTS.name],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=ROOT,
        )
        if result.returncode == 0 and result.stdout.strip():
            committed = int(result.stdout.strip())
            return int((time.time() - committed) / 86400)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    try:
        return int((time.time() - CONSTRAINTS.stat().st_mtime) / 86400)
    except OSError:
        return None


def newer_versions(python: Path) -> tuple[list[str], list[str]] | None:
    """Was der Index neuer anbietet — getrennt in erlaubt und ausgeschlossen.

    Braucht Netz. ``None`` heißt: pip hat nicht geantwortet.
    """
    try:
        result = subprocess.run(
            [str(python), "-m", "pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=ROOT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        entries = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    pinned_set = pinned()
    limits = upper_bounds()
    possible: list[str] = []
    locked: list[str] = []
    for entry in entries:
        key = normal(str(entry.get("name", "")))
        if key not in pinned_set:
            continue  # nicht festgeschrieben, also auch nicht unsere Sorge
        new = str(entry.get("latest_version", ""))
        old = str(entry.get("version", ""))
        name = pinned_set[key][0]
        limit = limits.get(key)
        if limit and version_tuple(new) >= version_tuple(limit):
            locked.append(f"{name} {old} → {new} (ausgeschlossen durch <{limit})")
        else:
            possible.append(f"{name} {old} → {new}")
    return sorted(possible), sorted(locked)


def freeze(python: Path) -> int:
    """Schreibt `constraints.txt` aus dem Ist — und behält den Kopf.

    `pip freeze > constraints.txt` wäre der naheliegende Weg und würde die
    neunzehn Zeilen Erklärung darüber löschen, also genau das, was die Datei
    verständlich macht.
    """
    try:
        result = subprocess.run(
            [str(python), "-m", "pip", "freeze", "--exclude-editable"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=ROOT,
        )
    except (OSError, subprocess.SubprocessError):
        print("`pip freeze` ließ sich nicht ausführen.")
        return 1
    if result.returncode != 0:
        print("`pip freeze` ist fehlgeschlagen:", result.stderr.strip()[:200])
        return 1

    old = CONSTRAINTS.read_text(encoding="utf-8").splitlines()
    head = [line for line in old if line.startswith("#") or not line.strip()]
    while head and not head[-1].strip():
        head.pop()
    new = sorted(
        (line for line in result.stdout.splitlines() if _LINE.match(line.strip())),
        key=lambda line: normal(str(_LINE.match(line.strip()).group(1))),  # type: ignore[union-attr]
    )
    CONSTRAINTS.write_text("\n".join([*head, "", *new]) + "\n", encoding="utf-8")
    print(f"`constraints.txt` neu geschrieben: {len(new)} Pakete, Kopf erhalten.")
    print("Jetzt die Suite fahren — grün heißt, der Satz taugt.")
    return 0


def mismatches(pinned_set: dict[str, tuple[str, str]], present: dict[str, str]) -> list[str]:
    """Pakete, die in einer anderen Version liegen als festgeschrieben.

    Ein Paket, das **fehlt**, steht hier absichtlich nicht: `constraints.txt`
    sagt, *in welcher* Version installiert wird, nicht *dass* installiert wird.
    Der Windows-Eintrag hat auf Linux nichts zu suchen, und ein nicht
    installiertes Extra ist eine Entscheidung, kein Fehler.
    """
    return [
        f"{name} {present[key]} statt {version}"
        for key, (name, version) in sorted(pinned_set.items())
        if key in present and present[key] != version
    ]


HOOKS_DIR: Final = ROOT / ".githooks"


def hooks_are_wired() -> bool | None:
    """Ob Git die Hooks dieses Projekts überhaupt ansieht.

    ``None``, wenn die Frage sich nicht stellt — kein Git-Repository, oder
    ``.githooks/`` gibt es nicht.

    **Warum das eine Prüfung wert ist.** ``CLAUDE.md`` sagt zu: *„Jeder Commit
    geht sofort hinaus, ``.githooks/post-commit`` pusht ihn"* — begründet damit,
    dass auf drei Maschinen gearbeitet wird und ein liegengebliebener Commit auf
    den anderen zweien nicht existiert. Am 23.08.2026 zeigte sich, dass Git
    diesen Hook nie angesehen hat: ``core.hooksPath`` war auf keiner Ebene
    gesetzt, und ohne ihn sucht Git in ``.git/hooks/``, wo nichts liegt.

    **Gemerkt hat es niemand, weil das Ergebnis stimmte** — es hat immer jemand
    von Hand gepusht. Aufgefallen ist es erst, als zwei Commits vor einem
    CI-Start liegenblieben und die CI beinahe den Stand *vor* zwei
    Fehlerbehebungen gebaut hätte.

    **Eine Automatik, die in Wahrheit Handarbeit ist, ist gefährlicher als gar
    keine:** Man verlässt sich auf sie, und sie trägt nicht. Deshalb wird hier
    nicht der Hook geprüft, sondern **dass er gerufen wird**.
    """
    if not (ROOT / ".git").exists() or not HOOKS_DIR.is_dir():
        return None
    try:
        antwort = subprocess.run(
            ["git", "-C", str(ROOT), "config", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    gesetzt = antwort.stdout.strip()
    if not gesetzt:
        return False
    return (ROOT / gesetzt).resolve() == HOOKS_DIR.resolve()


def check() -> tuple[list[str], list[str]]:
    """Befunde und Handlungsvorschläge — leer heißt: die Umgebung stimmt."""
    findings: list[str] = []
    suggestions: list[str] = []

    python = venv_python()
    if python is None:
        return (
            ["Die Projektumgebung `.venv` fehlt."],
            [setup_command(with_venv=False)],
        )

    required = required_version()
    running = interpreter_version(python)
    if running is None:
        return (
            ["Die Projektumgebung `.venv` antwortet nicht."],
            [f"Umgebung neu aufbauen: {setup_command(with_venv=False)}"],
        )
    if running < required:
        findings.append(
            f"Die Umgebung fährt Python {running[0]}.{running[1]}, "
            f"das Projekt verlangt {required[0]}.{required[1]} oder neuer."
        )
        suggestions.append("Umgebung mit einem neueren Python neu aufbauen (siehe CLAUDE.md).")

    pinned_set = pinned()
    present = installed(python)
    if present is None:
        findings.append("Die installierten Versionen ließen sich nicht auslesen.")
        suggestions.append(setup_command(with_venv=True))
        return findings, suggestions

    mismatched = mismatches(pinned_set, present)
    if mismatched:
        findings.append(
            f"{len(mismatched)} Paket(e) weichen von `constraints.txt` ab: "
            + ", ".join(mismatched[:6])
            + (" …" if len(mismatched) > 6 else "")
        )
        suggestions.append(setup_command(with_venv=True))

    days = age_in_days()
    if days is not None and days >= DAYS_UNTIL_MAINTENANCE:
        findings.append(
            f"Der festgeschriebene Satz ist seit {days} Tagen unverändert. "
            "Festgenagelt heißt nicht aktuell — je länger er steht, desto "
            "größer der Sprung, wenn er doch einmal muss."
        )
        suggestions.append("Was es Neues gibt: python tools/check_env.py --outdated")

    if hooks_are_wired() is False:
        findings.append(
            "Git sieht `.githooks/` nicht an: `core.hooksPath` ist nicht gesetzt. "
            "Der post-commit-Hook, der jeden Commit sofort hinausschickt, läuft "
            "damit nicht — und das fällt nicht auf, solange jemand von Hand pusht."
        )
        suggestions.append("Einmalig einrichten: git config core.hooksPath .githooks")

    return findings, suggestions


def install() -> int:
    """Installiert gegen `constraints.txt`. Braucht Netz und dauert."""
    python = venv_python()
    if python is None:
        print("Die Umgebung fehlt. Sie wird zuerst angelegt:", flush=True)
        result = subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], cwd=ROOT)
        if result.returncode != 0:
            print(
                "Das Anlegen ist fehlgeschlagen — bitte von Hand:",
                setup_command(with_venv=False),
            )
            return result.returncode
        python = venv_python()
    assert python is not None

    command = [
        str(python),
        "-m",
        "pip",
        "install",
        "-c",
        str(CONSTRAINTS),
        "-e",
        f".[{EXTRAS}]",
    ]
    print("Stelle die Umgebung her:", " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT).returncode


def show_newer(python: Path) -> int:
    """Berichtet, was aktueller wäre — und was absichtlich nicht kommt."""
    outcome = newer_versions(python)
    if outcome is None:
        print("pip hat nicht geantwortet — kein Netz, oder die Umgebung ist unvollständig.")
        return 1

    possible, locked = outcome
    days = age_in_days()
    if days is not None:
        print(f"Der festgeschriebene Satz ist seit {days} Tagen unverändert.\n")

    if not possible and not locked:
        print("Alles festgeschriebene ist auf dem neuesten Stand.")
        return 0

    if possible:
        print(f"Neuer verfügbar ({len(possible)}):")
        for line in possible:
            print("  " + line)
    if locked:
        print(f"\nDurch eine Grenze in `pyproject.toml` ausgeschlossen ({len(locked)}):")
        for line in locked:
            print("  " + line)
        print("  Eine Grenze fällt nicht nebenbei — sie ist eine eigene Migration.")

    if possible:
        print(
            "\nSo wird daraus ein neuer Stand:\n"
            f"  1. {venv_name()} -m pip install -U --upgrade-strategy eager "
            f'-e ".[{EXTRAS}]"\n'
            "     (ohne `eager` lässt pip alles stehen, was die Untergrenzen\n"
            "     schon erfüllt — und das sind sie fast alle)\n"
            "  2. Die Suite fahren — rot heißt: die Version bleibt, wo sie war\n"
            "  3. python tools/check_env.py --freeze\n"
            "  4. `constraints.txt` committen, mit dem Grund im Text"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="die Umgebung herstellen statt nur prüfen (braucht Netz)",
    )
    parser.add_argument(
        "--outdated",
        action="store_true",
        help="zeigen, was der Index neuer anbietet und was eine Grenze ausschließt (braucht Netz)",
    )
    parser.add_argument(
        "--freeze",
        action="store_true",
        help="`constraints.txt` aus dem Ist neu schreiben, Kopf behalten — erst nach grüner Suite",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="nichts ausgeben, nur den Exit-Code setzen",
    )
    args = parser.parse_args()

    if args.install:
        return install()

    if args.outdated or args.freeze:
        python = venv_python()
        if python is None:
            print("Ohne `.venv` geht das nicht:", setup_command(with_venv=False))
            return 1
        if args.freeze:
            return freeze(python)
        return show_newer(python)

    findings, suggestions = check()
    if not findings:
        if not args.quiet:
            print("Die Umgebung entspricht `constraints.txt`.")
        return 0

    if not args.quiet:
        for finding in findings:
            print(finding)
        print()
        for suggestion in suggestions:
            print("  " + suggestion)
        print("\nOder in einem Schritt:  python tools/check_env.py --install")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
