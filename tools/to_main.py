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

Die Bezeichner sind englisch wie überall unter ``tools/`` (AGENTS.md) — sie
waren es bis zum 25.08.2026 nicht, und in derselben Runde ist aufgefallen, dass
das Werkzeug bei **jedem** Aufruf an einem davon starb: Der Schalter hieß
``--nur-check``, gelesen wurde ``chosen.check_only``. Ein deutscher Schaltername
ist also nicht nur ein Regelverstoß, sondern hier eine zweite Schreibweise
desselben Wortes.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

#: Der Branch, auf dem am Ende alles zusammenläuft.
MAIN = "main"

#: Das Tor. Genau der Lauf, den `/pruefen` fährt — hier über das Schloss, damit
#: vier Sitzungen sich nicht gegenseitig die Messung verderben.
GATE = [
    "bash",
    ".claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh",
]


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Ein Git-Aufruf, dessen Ausgabe lesbar bleibt."""
    done = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if check and done.returncode != 0:
        print(f"  git {' '.join(args)} scheiterte:")
        print("  " + (done.stderr or done.stdout).strip().replace("\n", "\n  "))
    return done


def branch() -> str:
    """Auf welchem Branch dieser Arbeitsbaum steht."""
    return git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def is_clean() -> bool:
    """Ist alles committet? Ungestagtes würde nicht mitgeprüft und nicht mitreisen."""
    return not git("status", "--porcelain").stdout.strip()


def gate_passes(who: str) -> bool:
    """Das vollständige Tor unter dem Schloss — Suite, Leistung, ruff, format, mypy.

    Der Exit-Code kommt von den Läufen selbst und nicht von einer Zählzeile:
    Wer die Zusammenfassung liest statt ``returncode``, misst einen Filter.
    """
    steps: list[tuple[str, list[str]]] = [
        ("Suite", GATE),
        ("Leistung", [sys.executable, "-m", "pytest", "-q", "-m", "performance"]),
        ("ruff", [sys.executable, "-m", "ruff", "check", "."]),
        ("format", [sys.executable, "-m", "ruff", "format", "--check", "."]),
        ("mypy", [sys.executable, "-m", "mypy"]),
    ]
    # Der Arbeitsbaum hat keine eigene `.venv` — sie gehört dem Hauptbaum. Ohne
    # diesen Durchgriff sucht das Tor-Skript sie relativ und findet nichts;
    # jede Fensterdatei meldete dann Exit 127, was wie der bekannte Absturz
    # beim Abbau aussieht und keiner ist.
    environment = {**os.environ, "SUITE_PYTHON": sys.executable}
    for name, command in steps:
        print(f"  {name} …", end="", flush=True)
        done = subprocess.run(
            [
                sys.executable,
                "tools/gate_lock.py",
                "run",
                "--who",
                who,
                "--wait",
                "3000",
                "--",
                *command,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        if done.returncode != 0:
            print(f" rot (Exit {done.returncode})")
            tail = (done.stdout or "").strip().splitlines()[-12:]
            for line in tail:
                print(f"    {line}")
            return False
        print(" grün")
    return True


def deliver(who: str, check_only: bool) -> int:
    """Der ganze Weg, mit Halt bei jedem Grund zum Halten."""
    own_branch = branch()
    if own_branch == MAIN:
        print(f"Dieser Baum steht auf {MAIN}. Der Weg führt von einem eigenen Branch dorthin —")
        print("lege einen an (`git switch -c <name>`) oder arbeite in einem eigenen Arbeitsbaum.")
        return 2
    if not is_clean():
        print("Es liegt Ungestagtes im Baum. Was nicht committet ist, wird nicht geprüft")
        print("und reist nicht mit — committe es oder lege es beiseite.")
        return 2

    print(f"Branch: {own_branch}")
    print(f"1. {MAIN} holen und einweben")
    git("fetch", "origin", MAIN, check=False)
    merged = git("merge", f"origin/{MAIN}", "--no-edit", check=False)
    if merged.returncode != 0:
        print("  Der Zusammenschluss hat Konflikte. Die löst kein Skript:")
        print("  `git status` zeigt die Dateien, danach `git merge --continue`.")
        return 3
    print("  " + (merged.stdout.strip().splitlines() or ["nichts Neues"])[0])

    print("2. das Tor")
    if not gate_passes(who):
        print(f"\nRot — nichts geht nach {MAIN}. Der Branch {own_branch} behält deine Arbeit.")
        return 1

    if check_only:
        print(f"\nGrün. (--check-only: nichts nach {MAIN} geschoben.)")
        return 0

    print(f"3. nach {MAIN}")
    # Vorspulen und nichts anderes: Ein echter Zusammenschluss hier hieße, dass
    # `main` einen Stand bekommt, den das Tor nie gesehen hat.
    if git("switch", MAIN).returncode != 0:
        return 4
    # Der Rückgabewert zählt, und danach wird nachgemessen: Trägt das
    # lokale ``main`` einen eigenen, noch nicht veröffentlichten Commit,
    # scheitert das Vorspulen — und der Push danach kann trotzdem gelingen.
    # Draußen war dann dieses ungeprüfte ``main``, während hier „steht in
    # main und ist draußen" über den geprüften Branch stand (Gesamtreview
    # 05.09.2026, R20). Veröffentlicht wird nur, was genau der geprüfte
    # Commit ist.
    forwarded = git("merge", "--ff-only", own_branch)
    same_commit = (
        git("rev-parse", MAIN).stdout.strip() == git("rev-parse", own_branch).stdout.strip()
    )
    if forwarded.returncode != 0 or not same_commit:
        git("switch", own_branch)
        print(
            f"  {MAIN} lässt sich nicht vorspulen — es trägt einen Stand, den das Tor nie "
            f"gesehen hat. Nichts geht hinaus. Erst {MAIN} holen, {own_branch} darauf "
            "setzen, dann noch einmal."
        )
        return 6
    pushed = git("push", "origin", MAIN, check=False)
    git("switch", own_branch)
    if pushed.returncode != 0:
        print(f"  {MAIN} ist weitergewandert. Noch einmal von vorn — dann passt es.")
        return 5
    print(f"  {own_branch} steht in {MAIN} und ist draußen.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--who", default="unbenannt", help="Name der Sitzung fürs Schloss")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Das Tor fahren, aber nichts nach main schieben",
    )
    chosen = parser.parse_args()
    if not Path(".git").exists() and not Path(".git").is_file():
        print("Kein Git-Arbeitsbaum hier.")
        return 2
    return deliver(chosen.who, chosen.check_only)


if __name__ == "__main__":
    sys.exit(main())
