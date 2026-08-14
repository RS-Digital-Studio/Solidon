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
import time
import tomllib
from pathlib import Path
from typing import Final

WURZEL: Final = Path(__file__).resolve().parent.parent
CONSTRAINTS: Final = WURZEL / "constraints.txt"
PYPROJECT: Final = WURZEL / "pyproject.toml"

#: Die Gruppen, die ein Arbeitsplatz braucht — dieselben wie in CLAUDE.md.
EXTRAS: Final = "dev,geom,ui,agent,brep"

#: Ab wann die Fassungspflege fällig ist. Der wöchentliche CI-Lauf „Neueste
#: Fassungen" meldet gebrochene Fassungen; er sagt aber niemandem, dass es
#: etwas Neues *gäbe*. Nach einem Vierteljahr ohne Nachziehen ist der Satz
#: alt genug, dass ein Sprung wehtut — deshalb die Erinnerung.
TAGE_BIS_ZUR_PFLEGE: Final = 90

_ZEILE = re.compile(r"^([A-Za-z0-9._-]+)==([^\s;#]+)")
#: Eine Obergrenze in `pyproject.toml`, etwa `trimesh>=4.4,<5`.
_GRENZE = re.compile(r"^\s*[\"']?([A-Za-z0-9._-]+)[^\"']*?<=?\s*([0-9][0-9.]*)")


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


def venv_name() -> str:
    """Der Interpreteraufruf, wie man ihn hier tippt."""
    return ".venv\\Scripts\\python.exe" if sys.platform == "win32" else ".venv/bin/python"


def aufbaubefehl(mit_venv: bool) -> str:
    """Der Befehl, der die Umgebung herstellt — plattformgerecht geschrieben."""
    python = venv_name()
    anlegen = (
        ""
        if mit_venv
        else f"{'python' if sys.platform == 'win32' else 'python3'} -m venv .venv && "
    )
    return f'{anlegen}{python} -m pip install -c constraints.txt -e ".[{EXTRAS}]"'


def zahlenfolge(fassung: str) -> tuple[int, ...]:
    """Eine Fassung als Zahlenfolge, so weit sie sich lesen lässt.

    Absichtlich kein vollständiger PEP-440-Vergleich: Gebraucht wird nur die
    Frage, ob eine angebotene Fassung unter einer Obergrenze bleibt, und die
    Obergrenzen dieses Projekts sind schlichte Zahlen (`<5`).
    """
    teile: list[int] = []
    for stueck in fassung.split("."):
        if stueck.isdigit():
            teile.append(int(stueck))
            continue
        # „0rc1" zählt als 0, „post0" gar nicht — was hinter der ersten
        # Nicht-Ziffer steht, ist Vorab- oder Nachlaufkennung, keine Stelle.
        fuehrend = ""
        for zeichen in stueck:
            if not zeichen.isdigit():
                break
            fuehrend += zeichen
        if fuehrend:
            teile.append(int(fuehrend))
        break
    return tuple(teile)


def obergrenzen() -> dict[str, str]:
    """Pakete aus `pyproject.toml`, die eine Fassung ausdrücklich ausschließen.

    `trimesh>=4.4,<5` ist keine Nachlässigkeit, sondern eine Entscheidung: Der
    Major-Sprung wird als eigene Migration gemacht, weil der erste frische
    CI-Lauf mit trimesh 5.0.0 rot war. Wer nach Neuem sucht, muss solche
    Grenzen kennen — sonst schlägt er etwas vor, das absichtlich nicht kommt.
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    grenzen: dict[str, str] = {}
    for zeile in text.splitlines():
        if "<" not in zeile or zeile.lstrip().startswith("#"):
            continue
        treffer = _GRENZE.match(zeile)
        if treffer:
            grenzen[normal(treffer.group(1))] = treffer.group(2)
    return grenzen


def alter_in_tagen() -> int | None:
    """Wie lange `constraints.txt` unverändert ist — nach Git, sonst nach Datei.

    Der Git-Zeitstempel ist der richtige: Die Änderungszeit im Dateisystem
    sagt nach einem frischen Klon nur, wann geklont wurde.
    """
    try:
        lauf = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", CONSTRAINTS.name],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=WURZEL,
        )
        if lauf.returncode == 0 and lauf.stdout.strip():
            gesetzt = int(lauf.stdout.strip())
            return int((time.time() - gesetzt) / 86400)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    try:
        return int((time.time() - CONSTRAINTS.stat().st_mtime) / 86400)
    except OSError:
        return None


def neuere_fassungen(python: Path) -> tuple[list[str], list[str]] | None:
    """Was der Index neuer anbietet — getrennt in erlaubt und ausgeschlossen.

    Braucht Netz. ``None`` heißt: pip hat nicht geantwortet.
    """
    try:
        lauf = subprocess.run(
            [str(python), "-m", "pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=WURZEL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if lauf.returncode != 0:
        return None
    try:
        eintraege = json.loads(lauf.stdout)
    except json.JSONDecodeError:
        return None

    satz = festgeschrieben()
    grenzen = obergrenzen()
    moeglich: list[str] = []
    gesperrt: list[str] = []
    for eintrag in eintraege:
        schluessel = normal(str(eintrag.get("name", "")))
        if schluessel not in satz:
            continue  # nicht festgeschrieben, also auch nicht unsere Sorge
        neu = str(eintrag.get("latest_version", ""))
        alt = str(eintrag.get("version", ""))
        name = satz[schluessel][0]
        grenze = grenzen.get(schluessel)
        if grenze and zahlenfolge(neu) >= zahlenfolge(grenze):
            gesperrt.append(f"{name} {alt} → {neu} (ausgeschlossen durch <{grenze})")
        else:
            moeglich.append(f"{name} {alt} → {neu}")
    return sorted(moeglich), sorted(gesperrt)


def einfrieren(python: Path) -> int:
    """Schreibt `constraints.txt` aus dem Ist — und behält den Kopf.

    `pip freeze > constraints.txt` wäre der naheliegende Weg und würde die
    neunzehn Zeilen Erklärung darüber löschen, also genau das, was die Datei
    verständlich macht.
    """
    try:
        lauf = subprocess.run(
            [str(python), "-m", "pip", "freeze", "--exclude-editable"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=WURZEL,
        )
    except (OSError, subprocess.SubprocessError):
        print("`pip freeze` ließ sich nicht ausführen.")
        return 1
    if lauf.returncode != 0:
        print("`pip freeze` ist fehlgeschlagen:", lauf.stderr.strip()[:200])
        return 1

    alt = CONSTRAINTS.read_text(encoding="utf-8").splitlines()
    kopf = [zeile for zeile in alt if zeile.startswith("#") or not zeile.strip()]
    while kopf and not kopf[-1].strip():
        kopf.pop()
    neu = sorted(
        (zeile for zeile in lauf.stdout.splitlines() if _ZEILE.match(zeile.strip())),
        key=lambda zeile: normal(str(_ZEILE.match(zeile.strip()).group(1))),  # type: ignore[union-attr]
    )
    CONSTRAINTS.write_text("\n".join([*kopf, "", *neu]) + "\n", encoding="utf-8")
    print(f"`constraints.txt` neu geschrieben: {len(neu)} Pakete, Kopf erhalten.")
    print("Jetzt die Suite fahren — grün heißt, der Satz taugt.")
    return 0


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

    tage = alter_in_tagen()
    if tage is not None and tage >= TAGE_BIS_ZUR_PFLEGE:
        befunde.append(
            f"Der festgeschriebene Satz ist seit {tage} Tagen unverändert. "
            "Festgenagelt heißt nicht aktuell — je länger er steht, desto "
            "größer der Sprung, wenn er doch einmal muss."
        )
        vorschlaege.append("Was es Neues gibt: python tools/check_env.py --outdated")

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


def zeige_neueres(python: Path) -> int:
    """Berichtet, was aktueller wäre — und was absichtlich nicht kommt."""
    ergebnis = neuere_fassungen(python)
    if ergebnis is None:
        print("pip hat nicht geantwortet — kein Netz, oder die Umgebung ist unvollständig.")
        return 1

    moeglich, gesperrt = ergebnis
    tage = alter_in_tagen()
    if tage is not None:
        print(f"Der festgeschriebene Satz ist seit {tage} Tagen unverändert.\n")

    if not moeglich and not gesperrt:
        print("Alles festgeschriebene ist auf dem neuesten Stand.")
        return 0

    if moeglich:
        print(f"Neuer verfügbar ({len(moeglich)}):")
        for zeile in moeglich:
            print("  " + zeile)
    if gesperrt:
        print(f"\nDurch eine Grenze in `pyproject.toml` ausgeschlossen ({len(gesperrt)}):")
        for zeile in gesperrt:
            print("  " + zeile)
        print("  Eine Grenze fällt nicht nebenbei — sie ist eine eigene Migration.")

    if moeglich:
        print(
            "\nSo wird daraus ein neuer Stand:\n"
            f'  1. {venv_name()} -m pip install -U -e ".[{EXTRAS}]"\n'
            "  2. Die Suite fahren — rot heißt: die Fassung bleibt, wo sie war\n"
            "  3. python tools/check_env.py --freeze\n"
            "  4. `constraints.txt` committen, mit dem Grund im Text"
        )
    return 0


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
        "--outdated",
        action="store_true",
        help="zeigen, was der Index neuer anbietet und was eine Grenze ausschließt (braucht Netz)",
    )
    zerleger.add_argument(
        "--freeze",
        action="store_true",
        help="`constraints.txt` aus dem Ist neu schreiben, Kopf behalten — erst nach grüner Suite",
    )
    zerleger.add_argument(
        "--quiet",
        action="store_true",
        help="nichts ausgeben, nur den Exit-Code setzen",
    )
    argumente = zerleger.parse_args()

    if argumente.install:
        return herstellen()

    if argumente.outdated or argumente.freeze:
        python = venv_python()
        if python is None:
            print("Ohne `.venv` geht das nicht:", aufbaubefehl(mit_venv=False))
            return 1
        if argumente.freeze:
            return einfrieren(python)
        return zeige_neueres(python)

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
