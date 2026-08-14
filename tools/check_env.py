"""Prüft, ob die Umgebung dem festgeschriebenen Stand entspricht — und stellt ihn her.

Warum es das Werkzeug gibt: `constraints.txt` schreibt fest, *in welcher*
Fassung ein Paket installiert wird. Nur half das nichts, solange niemand
nachsah. Wer `pip install -e ".[dev,geom,ui,agent,brep]"` ohne das `-c` tippt,
bekommt andere Fassungen als die, gegen die die Suite grün ist — am 06.08.2026
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
import tomllib
from pathlib import Path
from typing import Final

WURZEL: Final = Path(__file__).resolve().parent.parent
CONSTRAINTS: Final = WURZEL / "constraints.txt"
PYPROJECT: Final = WURZEL / "pyproject.toml"

#: Die Gruppen, die ein Arbeitsplatz braucht — dieselben wie in CLAUDE.md.
EXTRAS: Final = "dev,geom,ui,agent,brep"

_ZEILE = re.compile(r"^([A-Za-z0-9._-]+)==([^\s;#]+)")


def normal(name: str) -> str:
    """Paketnamen nach PEP 503 vergleichbar machen (`svg.path` = `svg-path`)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def venv_python() -> Path | None:
    """Der Interpreter der Projektumgebung, falls es sie gibt."""
    for kandidat in (
        WURZEL / ".venv" / "Scripts" / "python.exe",
        WURZEL / ".venv" / "bin" / "python",
    ):
        if kandidat.exists():
            return kandidat
    return None


def festgeschrieben() -> dict[str, tuple[str, str]]:
    """`constraints.txt` als Zuordnung normalisierter Name → (Name, Fassung)."""
    satz: dict[str, tuple[str, str]] = {}
    for zeile in CONSTRAINTS.read_text(encoding="utf-8").splitlines():
        treffer = _ZEILE.match(zeile.strip())
        if treffer:
            name, fassung = treffer.group(1), treffer.group(2)
            satz[normal(name)] = (name, fassung)
    return satz


def installiert(python: Path) -> dict[str, str] | None:
    """Was in dieser Umgebung liegt — oder ``None``, wenn sie nicht antwortet."""
    quelle = (
        "import json,importlib.metadata as m;"
        "print(json.dumps({d.metadata['Name']: d.version for d in m.distributions()"
        " if d.metadata['Name']}))"
    )
    try:
        lauf = subprocess.run(
            [str(python), "-c", quelle],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=WURZEL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if lauf.returncode != 0:
        return None
    try:
        roh: dict[str, str] = json.loads(lauf.stdout)
    except json.JSONDecodeError:
        return None
    return {normal(name): fassung for name, fassung in roh.items()}


def verlangte_fassung() -> tuple[int, int]:
    """Die Untergrenze aus ``requires-python`` als Zahlenpaar."""
    with PYPROJECT.open("rb") as handle:
        daten = tomllib.load(handle)
    roh = str(daten["project"]["requires-python"]).strip()
    haupt, neben = roh.removeprefix(">=").strip().split(".")[:2]
    return int(haupt), int(neben)


def interpreter_fassung(python: Path) -> tuple[int, int] | None:
    try:
        lauf = subprocess.run(
            [str(python), "-c", "import sys;print(f'{sys.version_info[0]} {sys.version_info[1]}')"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if lauf.returncode != 0:
        return None
    try:
        haupt, neben = lauf.stdout.split()
    except ValueError:
        return None
    return int(haupt), int(neben)


def aufbaubefehl(mit_venv: bool) -> str:
    """Der Befehl, der die Umgebung herstellt — plattformgerecht geschrieben."""
    python = ".venv\\Scripts\\python.exe" if sys.platform == "win32" else ".venv/bin/python"
    anlegen = (
        ""
        if mit_venv
        else f"{'python' if sys.platform == 'win32' else 'python3'} -m venv .venv && "
    )
    return f'{anlegen}{python} -m pip install -c constraints.txt -e ".[{EXTRAS}]"'


def abweichungen(satz: dict[str, tuple[str, str]], vorhanden: dict[str, str]) -> list[str]:
    """Pakete, die in einer anderen Fassung liegen als festgeschrieben.

    Ein Paket, das **fehlt**, steht hier absichtlich nicht: `constraints.txt`
    sagt, *in welcher* Fassung installiert wird, nicht *dass* installiert wird.
    Der Windows-Eintrag hat auf Linux nichts zu suchen, und ein nicht
    installiertes Extra ist eine Entscheidung, kein Fehler.
    """
    return [
        f"{name} {vorhanden[schluessel]} statt {fassung}"
        for schluessel, (name, fassung) in sorted(satz.items())
        if schluessel in vorhanden and vorhanden[schluessel] != fassung
    ]


def pruefen() -> tuple[list[str], list[str]]:
    """Befunde und Handlungsvorschläge — leer heißt: die Umgebung stimmt."""
    befunde: list[str] = []
    vorschlaege: list[str] = []

    python = venv_python()
    if python is None:
        return (
            ["Die Projektumgebung `.venv` fehlt."],
            [aufbaubefehl(mit_venv=False)],
        )

    verlangt = verlangte_fassung()
    laeuft = interpreter_fassung(python)
    if laeuft is None:
        return (
            ["Die Projektumgebung `.venv` antwortet nicht."],
            [f"Umgebung neu aufbauen: {aufbaubefehl(mit_venv=False)}"],
        )
    if laeuft < verlangt:
        befunde.append(
            f"Die Umgebung fährt Python {laeuft[0]}.{laeuft[1]}, "
            f"das Projekt verlangt {verlangt[0]}.{verlangt[1]} oder neuer."
        )
        vorschlaege.append("Umgebung mit einem neueren Python neu aufbauen (siehe CLAUDE.md).")

    satz = festgeschrieben()
    vorhanden = installiert(python)
    if vorhanden is None:
        befunde.append("Die installierten Fassungen ließen sich nicht auslesen.")
        vorschlaege.append(aufbaubefehl(mit_venv=True))
        return befunde, vorschlaege

    abweichend = abweichungen(satz, vorhanden)
    if abweichend:
        befunde.append(
            f"{len(abweichend)} Paket(e) weichen von `constraints.txt` ab: "
            + ", ".join(abweichend[:6])
            + (" …" if len(abweichend) > 6 else "")
        )
        vorschlaege.append(aufbaubefehl(mit_venv=True))

    return befunde, vorschlaege


def herstellen() -> int:
    """Installiert gegen `constraints.txt`. Braucht Netz und dauert."""
    python = venv_python()
    if python is None:
        print("Die Umgebung fehlt. Sie wird zuerst angelegt:", flush=True)
        lauf = subprocess.run([sys.executable, "-m", "venv", str(WURZEL / ".venv")], cwd=WURZEL)
        if lauf.returncode != 0:
            print("Das Anlegen ist fehlgeschlagen — bitte von Hand:", aufbaubefehl(mit_venv=False))
            return lauf.returncode
        python = venv_python()
    assert python is not None

    befehl = [
        str(python),
        "-m",
        "pip",
        "install",
        "-c",
        str(CONSTRAINTS),
        "-e",
        f".[{EXTRAS}]",
    ]
    print("Stelle die Umgebung her:", " ".join(befehl), flush=True)
    return subprocess.run(befehl, cwd=WURZEL).returncode


def main() -> int:
    zerleger = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    zerleger.add_argument(
        "--install",
        action="store_true",
        help="die Umgebung herstellen statt nur prüfen (braucht Netz)",
    )
    zerleger.add_argument(
        "--quiet",
        action="store_true",
        help="nichts ausgeben, nur den Exit-Code setzen",
    )
    argumente = zerleger.parse_args()

    if argumente.install:
        return herstellen()

    befunde, vorschlaege = pruefen()
    if not befunde:
        if not argumente.quiet:
            print("Die Umgebung entspricht `constraints.txt`.")
        return 0

    if not argumente.quiet:
        for satz in befunde:
            print(satz)
        print()
        for satz in vorschlaege:
            print("  " + satz)
        print("\nOder in einem Schritt:  python tools/check_env.py --install")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
