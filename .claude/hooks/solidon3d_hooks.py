"""Hooks für Claude Code in diesem Projekt.

Ein Skript, fünf Aufgaben — welche, sagt das erste Argument:

    sitzungsstart    SessionStart: sagt, in welchem Projekt wir sind. Die
                     globale Konfiguration beschreibt ein Avalonia-Projekt;
                     dieses hier ist Python. Prüft dabei, ob die Umgebung dem
                     festgeschriebenen Stand entspricht — mehrere Leute am
                     selben Repository heißt sonst mehrere Versionssätze.
    nach-aenderung   PostToolUse (Write|Edit): formatiert die geänderte
                     Python-Datei und meldet Lint-Befunde sowie Verstöße gegen
                     die harten Regeln, die sich rein syntaktisch erkennen
                     lassen.
    testlauf         PostToolUse (Bash): merkt sich, wann die Suite zuletzt
                     lief.
    abschluss        Stop: erinnert daran, wenn seit der letzten Änderung an
                     app/ oder tests/ keine Suite gelaufen ist.
    vor-bash         PreToolUse (Bash): fragt nach, bevor ein Befehl Arbeit
                     verwirft (Regel „niemals reverten").

Grundsatz: Ein Hook stört nie die Arbeit. Jeder Fehler endet still mit 0 —
lieber ein ausgefallener Hinweis als eine blockierte Sitzung.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent.parent
VENV_PYTHON = WURZEL / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():  # Linux und macOS, falls das Projekt dort läuft
    VENV_PYTHON = WURZEL / ".venv" / "bin" / "python"
MARKE = WURZEL / ".claude" / ".state" / "letzter-testlauf"
ERINNERT = WURZEL / ".claude" / ".state" / "letzte-erinnerung"

# Regeln, die sich am Text einer Datei erkennen lassen. Alles andere prüfen die
# Tests — ein Hook, der raten muss, meldet lieber nichts.
QT_IMPORT = re.compile(r"^\s*(?:from|import)\s+(?:PySide6|PyQt\d|shiboken\d?)\b", re.MULTILINE)
EVAL_AUFRUF = re.compile(r"(?<![\w.])(?:eval|exec)\s*\(")
PRINT_AUFRUF = re.compile(r"(?<![\w.])print\s*\(")
VERWIRFT = re.compile(
    r"git\s+(?:checkout\s+(?:--|\.|HEAD)|restore\b|reset\s+--hard\b|clean\s+-[a-z]*f)"
    r"|git\s+push\s+.*--force(?!-with-lease)"
)


def eingabe() -> dict:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Umlaute überleben auch cp1252

    try:
        return json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return {}


def melden(ereignis: str, text: str) -> None:
    """Gibt Claude einen Hinweis mit, ohne die Handlung anzuhalten."""
    json.dump(
        {"hookSpecificOutput": {"hookEventName": ereignis, "additionalContext": text}},
        sys.stdout,
    )


def ruff(*argumente: str) -> tuple[int, str]:
    if not VENV_PYTHON.exists():
        return 0, ""
    try:
        lauf = subprocess.run(
            [str(VENV_PYTHON), "-m", "ruff", *argumente],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=WURZEL,
        )
    except (OSError, subprocess.SubprocessError):
        return 0, ""
    return lauf.returncode, (lauf.stdout or "") + (lauf.stderr or "")


def umgebungshinweis() -> str:
    """Meldet, wenn die Umgebung nicht dem festgeschriebenen Stand entspricht.

    Der Grund steht in `constraints.txt`: Wer das `-c` beim Installieren
    vergisst, bekommt andere Versionen als die, gegen die die Suite grün ist.
    Am 06.08.2026 zog ein frischer Klon numpy 2.5, und sechzehn Tests fielen
    um, ohne dass eine Zeile Code sich geändert hatte. Arbeiten mehrere am
    selben Repository, ist das kein Einzelfall.

    Der Hinweis kostet zwei kurze Unterprozesse und kein Netz. Schlägt er
    fehl, bleibt er still — ein Hook hält die Arbeit nie auf.
    """
    try:
        if str(WURZEL) not in sys.path:
            sys.path.insert(0, str(WURZEL))
        from tools.check_env import pruefen

        befunde, vorschlaege = pruefen()
    except Exception:  # ein Hinweis darf nie die Sitzung kosten
        return ""
    if not befunde:
        return ""
    schritte = " ".join(vorschlaege)
    return (
        " ACHTUNG, die Umgebung weicht ab: "
        + " ".join(befunde)
        + f" Herstellen mit: {schritte} — oder in einem Schritt: "
        "python tools/check_env.py --install. Bis dahin sagt ein roter Lauf "
        "nichts über den Code."
    )


def sitzungsstart() -> None:
    eingabe()
    melden(
        "SessionStart",
        "Projekt Solidon: Python mit PySide6, kein Avalonia und kein MVVM — "
        "die Stack-Angaben der globalen Konfiguration gelten hier nicht. "
        "Bezeichner, Dateinamen und Modulnamen auf Englisch; Docstrings, Kommentare, "
        "Doku, Commits und Gespräch auf Deutsch mit echten Umlauten. "
        "Der Kern (app/core) bleibt ohne Qt. "
        "Nach jedem Schritt läuft die Suite — /pruefen. Vor dem Commit /regelcheck. "
        "Die 22 harten Regeln stehen in AGENTS.md, das Sollverhalten im Bauplan. "
        "Hier arbeiten oft zwei bis vier Sitzungen gleichzeitig: `/list-agents` "
        "zeigt sie, `claude --worktree <name>` gibt jeder ihren eigenen Baum, und "
        "/pruefen nimmt ein Schloss, damit Messungen sich nicht verfälschen." + umgebungshinweis(),
    )


def nach_aenderung() -> None:
    daten = eingabe()
    roh = (daten.get("tool_input") or {}).get("file_path")
    if not roh:
        return
    datei = Path(roh)
    if datei.suffix != ".py" or not datei.exists():
        return
    try:
        relativ = datei.resolve().relative_to(WURZEL)
    except ValueError:
        return  # außerhalb des Projekts, geht diesen Hook nichts an

    hinweise: list[str] = []

    ruff("format", str(datei))
    schluss, ausgabe = ruff("check", "--quiet", str(datei))
    if schluss != 0 and ausgabe.strip():
        hinweise.append("ruff check meldet:\n" + ausgabe.strip()[:1500])

    try:
        text = datei.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""

    im_kern = relativ.parts[:2] == ("app", "core")
    if im_kern and QT_IMPORT.search(text):
        hinweise.append(
            "Regel 1: Qt unterhalb von ui/. In app/core darf kein PySide6 importiert "
            "werden — test_core_isolation.py fällt darüber. Kommunikation nach außen "
            "läuft über den OpContext."
        )
    if im_kern and PRINT_AUFRUF.search(text):
        hinweise.append(
            "Der Kern gibt nichts aus. Fortschritt über ctx.progress, Rückfragen über "
            "ctx.ask, alles andere ins Protokoll."
        )
    if relativ.parts[:1] == ("app",) and EVAL_AUFRUF.search(text):
        hinweise.append(
            "Regel 10: kein eval/exec. Parameterausdrücke laufen über den eigenen "
            "Auswerter mit beschränkter Grammatik (§32)."
        )

    if hinweise:
        melden("PostToolUse", "\n\n".join(hinweise))


def testlauf() -> None:
    daten = eingabe()
    befehl = (daten.get("tool_input") or {}).get("command") or ""
    if "pytest" not in befehl:
        return
    try:
        MARKE.parent.mkdir(parents=True, exist_ok=True)
        MARKE.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def abschluss() -> None:
    eingabe()  # stdin leeren, damit der Aufrufer nicht blockiert
    try:
        zuletzt = float(MARKE.read_text(encoding="utf-8")) if MARKE.exists() else 0.0
    except (OSError, ValueError):
        zuletzt = 0.0

    juenger: list[str] = []
    for gebiet in ("app", "tests"):
        for datei in (WURZEL / gebiet).rglob("*.py"):
            if "__pycache__" in datei.parts:
                continue
            try:
                if datei.stat().st_mtime > zuletzt:
                    juenger.append(str(datei.relative_to(WURZEL)))
            except OSError:
                continue
            if len(juenger) > 3:
                break
        if len(juenger) > 3:
            break

    if juenger:
        # Zweimal derselbe Hinweis ist keiner mehr: er wird überlesen und kostet
        # nur Kontext. Also nur melden, wenn sich etwas geändert hat — bei
        # fremder Arbeit im Baum feuert der Hook sonst bei jedem Zug erneut.
        stand = "|".join(sorted(juenger))
        try:
            if ERINNERT.exists() and ERINNERT.read_text(encoding="utf-8") == stand:
                return
            ERINNERT.parent.mkdir(parents=True, exist_ok=True)
            ERINNERT.write_text(stand, encoding="utf-8")
        except OSError:
            pass

        gezeigt = ", ".join(juenger[:3]) + (" und weitere" if len(juenger) > 3 else "")
        melden(
            "Stop",
            f"Seit der letzten Änderung ({gezeigt}) lief die Suite nicht. "
            "Die Arbeitsweise dieses Projekts verlangt sie nach jedem Schritt: "
            ".venv\\Scripts\\python.exe -m pytest -q — oder /pruefen für alle vier Läufe. "
            "Der Hook sieht nur den Zeitstempel, nicht den Urheber: stammt die Änderung "
            "aus einer parallel laufenden Sitzung, gehört sie nicht dir. Dann weder "
            "prüfen noch anfassen, sondern es beim Berichten erwähnen.",
        )


def vor_bash() -> None:
    daten = eingabe()
    befehl = (daten.get("tool_input") or {}).get("command") or ""
    if not VERWIRFT.search(befehl):
        return
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    "Dieser Befehl verwirft Arbeit. In diesem Projekt gilt: niemals "
                    "reverten, immer vorwärts fixen — Reverts zerstören parallele "
                    "Arbeit. Nur nach ausdrücklicher Freigabe ausführen."
                ),
            }
        },
        sys.stdout,
    )


AUFGABEN = {
    "sitzungsstart": sitzungsstart,
    "nach-aenderung": nach_aenderung,
    "testlauf": testlauf,
    "abschluss": abschluss,
    "vor-bash": vor_bash,
}


def main() -> int:
    if os.environ.get("SOLIDON3D_HOOKS") == "aus":
        return 0
    aufgabe = AUFGABEN.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if aufgabe is None:
        return 0
    try:
        aufgabe()
    except Exception:
        # Ein Hook hält die Sitzung nie auf, auch nicht mit einem eigenen Fehler.
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
