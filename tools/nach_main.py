"""Der Weg nach ``main``: prüfen, was wirklich committet wird, und erst dann liefern.

**Das Problem, das dieses Werkzeug löst.** Am 22.08.2026 arbeiteten vier
Sitzungen in einem Arbeitsbaum. Jeder Torlauf las die ungestagten Dateien aller
vier; committet wurde davon je ein Ausschnitt. **Kein einziger Lauf prüfte
damit, was in ``main`` landete** — und dreimal an einem Abend meldete ein Lauf
etwas, das an einem fremden Zwischenstand lag. Der gefährlichere Fall ist der
umgekehrte: Ein fremder Zwischenstand kann einen Lauf auch **grün** machen.

**Die Lösung ist ein eigener Arbeitsbaum je Sitzung** (``claude --worktree``).
Dort steht ``HEAD`` plus die eigenen Änderungen und sonst nichts. Zwei Bäume
können denselben Branch nicht auschecken — Git verweigert es, und die Sperre
ist keine Formalität: Zwei Bäume auf ``main`` teilten sich Index und HEAD, also
genau das, was wir loswerden wollen. Jede Sitzung braucht deshalb einen eigenen
Branch, und dieses Werkzeug bringt ihn nach ``main``.

Der Ablauf, und jeder Schritt hat einen Grund:

1. **Den eigenen Stand committen** — geprüft wird, was committet ist, nicht was
   im Baum liegt.
2. **``origin/main`` holen und einweben.** Ohne diesen Schritt prüft das Tor
   einen Stand, den es so nie geben wird: die eigene Arbeit ohne die der
   anderen. Bei einem Konflikt hält das Werkzeug an — Konflikte löst ein
   Mensch oder die Sitzung, nicht ein Skript.
3. **Das Tor fahren**, unter dem Schloss. Erst hier steht fest, dass der Stand
   trägt, den ``main`` bekommen wird.
4. **Nur bei grün nach ``main``**, und zwar als Vorspulen. Geht das nicht, ist
   ``main`` inzwischen weitergewandert; dann wird ab Schritt 2 wiederholt.

**Was es nie tut:** mit ``--force`` schieben, auf ``main`` committen, einen
roten Lauf durchwinken oder eine Konfliktauflösung erfinden.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

#: Der Branch, auf dem am Ende alles zusammenläuft.
HAUPT = "main"

#: Das Tor. Genau der Lauf, den `/pruefen` fährt — hier über das Schloss, damit
#: vier Sitzungen sich nicht gegenseitig die Messung verderben.
TOR = [
    "bash",
    ".claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh",
]


def git(*args: str, pruefen: bool = True) -> subprocess.CompletedProcess[str]:
    """Ein Git-Aufruf, dessen Ausgabe lesbar bleibt."""
    fertig = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if pruefen and fertig.returncode != 0:
        print(f"  git {' '.join(args)} scheiterte:")
        print("  " + (fertig.stderr or fertig.stdout).strip().replace("\n", "\n  "))
    return fertig


def zweig() -> str:
    """Auf welchem Branch dieser Arbeitsbaum steht."""
    return git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def sauber() -> bool:
    """Ist alles committet? Ungestagtes würde nicht mitgeprüft und nicht mitreisen."""
    return not git("status", "--porcelain").stdout.strip()


def tor_laeuft_durch(wer: str) -> bool:
    """Das vollständige Tor unter dem Schloss — Suite, Leistung, ruff, format, mypy.

    Der Exit-Code kommt von den Läufen selbst und nicht von einer Zählzeile:
    Wer die Zusammenfassung liest statt ``returncode``, misst einen Filter.
    """
    schritte: list[tuple[str, list[str]]] = [
        ("Suite", TOR),
        ("Leistung", [sys.executable, "-m", "pytest", "-q", "-m", "performance"]),
        ("ruff", [sys.executable, "-m", "ruff", "check", "."]),
        ("format", [sys.executable, "-m", "ruff", "format", "--check", "."]),
        ("mypy", [sys.executable, "-m", "mypy"]),
    ]
    # Der Arbeitsbaum hat keine eigene `.venv` — sie gehört dem Hauptbaum. Ohne
    # diesen Durchgriff sucht das Tor-Skript sie relativ und findet nichts;
    # jede Fensterdatei meldete dann Exit 127, was wie der bekannte Absturz
    # beim Abbau aussieht und keiner ist.
    umgebung = {**os.environ, "SUITE_PYTHON": sys.executable}
    for name, befehl in schritte:
        print(f"  {name} …", end="", flush=True)
        fertig = subprocess.run(
            [
                sys.executable,
                "tools/gate_lock.py",
                "run",
                "--who",
                wer,
                "--wait",
                "3000",
                "--",
                *befehl,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=umgebung,
        )
        if fertig.returncode != 0:
            print(f" rot (Exit {fertig.returncode})")
            schluss = (fertig.stdout or "").strip().splitlines()[-12:]
            for zeile in schluss:
                print(f"    {zeile}")
            return False
        print(" grün")
    return True


def liefere(wer: str, nur_pruefen: bool) -> int:
    """Der ganze Weg, mit Halt bei jedem Grund zum Halten."""
    eigener = zweig()
    if eigener == HAUPT:
        print(f"Dieser Baum steht auf {HAUPT}. Der Weg führt von einem eigenen Branch dorthin —")
        print("lege einen an (`git switch -c <name>`) oder arbeite in einem eigenen Arbeitsbaum.")
        return 2
    if not sauber():
        print("Es liegt Ungestagtes im Baum. Was nicht committet ist, wird nicht geprüft")
        print("und reist nicht mit — committe es oder lege es beiseite.")
        return 2

    print(f"Branch: {eigener}")
    print(f"1. {HAUPT} holen und einweben")
    git("fetch", "origin", HAUPT, pruefen=False)
    verschmolzen = git("merge", f"origin/{HAUPT}", "--no-edit", pruefen=False)
    if verschmolzen.returncode != 0:
        print("  Der Zusammenschluss hat Konflikte. Die löst kein Skript:")
        print("  `git status` zeigt die Dateien, danach `git merge --continue`.")
        return 3
    print("  " + (verschmolzen.stdout.strip().splitlines() or ["nichts Neues"])[0])

    print("2. das Tor")
    if not tor_laeuft_durch(wer):
        print(f"\nRot — nichts geht nach {HAUPT}. Der Branch {eigener} behält deine Arbeit.")
        return 1

    if nur_pruefen:
        print(f"\nGrün. (--nur-pruefen: nichts nach {HAUPT} geschoben.)")
        return 0

    print(f"3. nach {HAUPT}")
    # Vorspulen und nichts anderes: Ein echter Zusammenschluss hier hieße, dass
    # `main` einen Stand bekommt, den das Tor nie gesehen hat.
    if git("switch", HAUPT).returncode != 0:
        return 4
    git("merge", "--ff-only", eigener)
    geschoben = git("push", "origin", HAUPT, pruefen=False)
    git("switch", eigener)
    if geschoben.returncode != 0:
        print(f"  {HAUPT} ist weitergewandert. Noch einmal von vorn — dann passt es.")
        return 5
    print(f"  {eigener} steht in {HAUPT} und ist draußen.")
    return 0


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--who", default="unbenannt", help="Name der Sitzung fürs Schloss")
    zerleger.add_argument(
        "--nur-pruefen",
        action="store_true",
        help="Das Tor fahren, aber nichts nach main schieben",
    )
    gewaehlt = zerleger.parse_args()
    if not Path(".git").exists() and not Path(".git").is_file():
        print("Kein Git-Arbeitsbaum hier.")
        return 2
    return liefere(gewaehlt.who, gewaehlt.nur_pruefen)


if __name__ == "__main__":
    sys.exit(main())
