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
#: Befehle, die eine Datei geschrieben haben können, ohne dass Write oder Edit
#: es gesehen hätte — ein Skript über die Shell, ein `sed -i`, eine Umleitung.
SCHREIBT_DATEI = re.compile(
    r"write_text|writelines|\bsed\s+-i|>\s*\S+\.py|\btee\b|ruff\s+format(?!\s+--check)"
)


def nachbarsitzungen() -> list[str]:
    """Die anderen Claude-Sitzungen, die gerade an diesem Projekt arbeiten.

    Gelesen aus ``~/.claude/sessions/*.json``, wo jede Sitzung sich einträgt.
    **Erkannt wird eine lebende Sitzung an ihrem Postfach**, nicht an ihrer
    Prozessnummer: Am 22.08.2026 lieferte die Nummer allein fünf Fehltreffer —
    beendete Sitzungen, deren Nummer inzwischen jemand anders trug. Das
    Postfach ist eine benannte Pipe und existiert nur, solange sie jemand hält;
    die Prüfung darauf stimmte auf Anhieb mit ``ListAgents`` überein.

    Der Eintrag ist interner Zustand von Claude Code und nirgends zugesagt —
    ältere Fassungen tragen gar kein Postfach ein. Deshalb ist ein leeres
    Ergebnis hier nie eine Aussage, sondern nur „nichts gefunden": Wer wissen
    will, wer wirklich da ist, fragt ``/list-agents``.
    """
    eigen = str(os.environ.get("CLAUDE_PID") or "")
    register = Path.home() / ".claude" / "sessions"
    gefunden: list[str] = []
    try:
        dateien = list(register.glob("*.json"))
    except OSError:
        return []
    for datei in dateien:
        try:
            eintrag = json.loads(datei.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(eintrag, dict) or datei.stem == eigen:
            continue
        postfach = eintrag.get("messagingSocketPath")
        if not isinstance(postfach, str) or not postfach:
            continue
        try:
            if Path(str(eintrag.get("cwd") or "")).resolve() != WURZEL:
                continue
            if not Path(postfach).exists():
                continue
        except OSError:
            continue
        gefunden.append(str(eintrag.get("name") or datei.stem))
    return sorted(gefunden)


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
    """Ruft ruff aus der virtuellen Umgebung.

    **Jeder Aufruf hier braucht ``--force-exclude``.** Ruff wendet
    ``extend-exclude`` aus ``pyproject.toml`` nur auf Pfade an, die es selbst
    findet — ein *explizit genannter* Pfad wird geprüft, und dieser Hook nennt
    immer explizit. Ohne das Flag prüfte er damit genau die zwei Bäume, die das
    Projekt ausdrücklich ausnimmt: ``.claude/.state/`` und ``3D Drucker/``.

    Das war zweimal falsch. Gemeldet wurden Verstöße in den Messskripten
    vergangener Durchsichten, die niemanden mehr angehen — eine Fehlermeldung
    nach jedem Werkzeugaufruf, die auf nichts zeigt, und das Tor war die ganze
    Zeit grün (``ruff check .`` gibt Exit 0). Schwerer wiegt die andere Hälfte:
    ``format`` prüft nicht, es **schreibt**. Unter ``3D Drucker/`` liegen 22
    Skripte für Roberts physische Druckteile, und der Hook hat sie bei jedem
    Schreiben umformatiert — gegen die Begründung, die in ``pyproject.toml``
    daneben steht: „Ein Messskript, das umgeschrieben wurde, belegt seine Zahl
    nicht mehr."
    """
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


def _nachbarhinweis() -> str:
    """Wer sonst gerade an diesem Projekt sitzt — falls jemand da ist.

    Beim Start zu wissen, dass man nicht allein ist, erspart die Runde, in der
    man es beim ersten Zusammenstoß erfährt. Ist niemand da, steht hier auch
    nichts: Ein Hinweis, der immer erscheint, wird nicht mehr gelesen.
    """
    andere = nachbarsitzungen()
    if not andere:
        return ""
    return (
        " ES ARBEITEN SCHON ANDERE SITZUNGEN HIER: "
        + ", ".join(andere)
        + ". Bevor du die erste Datei anfasst, tu drei Dinge: (1) "
        "`python tools/session_board.py list` — dort steht, wer welches Gebiet hält. "
        "(2) Schreib jeder von ihnen über SendMessage, wofür du gekommen bist, und "
        "einige dich auf ein Gebiet, das ihres nicht berührt; wer zuerst da war, "
        "behält seines. (3) Trag deins ein: "
        '`python tools/session_board.py claim --area "…" --files "…"`. '
        "Das kostet zwei Minuten und erspart den Fall vom 22.08.2026, in dem sich "
        "zwei Nachrichten kreuzten und beide Sitzungen dieselbe Datei ändern wollten."
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
        "/pruefen nimmt ein Schloss, damit Messungen sich nicht verfälschen."
        + _nachbarhinweis()
        + umgebungshinweis(),
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

    ruff("format", "--force-exclude", str(datei))
    schluss, ausgabe = ruff("check", "--quiet", "--force-exclude", str(datei))
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
    if "pytest" in befehl:
        try:
            MARKE.parent.mkdir(parents=True, exist_ok=True)
            MARKE.write_text(str(time.time()), encoding="utf-8")
        except OSError:
            pass
    # Gesammelt und **einmal** gemeldet: Zwei ``melden``-Aufrufe schreiben zwei
    # JSON-Objekte auf denselben Strom, und das ist keine Antwort mehr.
    hinweise = [text for text in (_ruff_hinweis(befehl), _commit_hinweis(befehl)) if text]
    if hinweise:
        melden("PostToolUse", "\n\n".join(hinweise))


def _ruff_hinweis(befehl: str) -> str:
    """Was ruff zu den Dateien sagt, die dieser Shell-Befehl geschrieben haben
    könnte.

    **Die Lücke, die dieser Hinweis schließt, und sie ist heute zugeschnappt.**
    :func:`nach_aenderung` prüft jede geänderte Python-Datei — aber nur, wenn
    das Modell Write oder Edit benutzt hat. Eine Änderung über die Shell sieht
    der Matcher ``Write|Edit`` nicht, und am 24.08.2026 kam so eine Zeile von
    102 Zeichen ins Tor: Geprüft wurde ruff **mit Pfadangabe** auf die eine
    Datei, die man im Kopf hatte, die zweite fiel einer Nachbarsitzung auf.
    Zwei Sitzungen an einem Tag, dieselbe Falle — und gefangen hat sie beide
    Male nicht Umsicht, sondern Zufall.

    **Geprüft, nicht formatiert**, und das ist der Unterschied zum Hook nach
    Write und Edit. Der kennt die eine Datei, die gerade geschrieben wurde, und
    darf sie formatieren. Hier ist nur bekannt, dass *irgendetwas* geschrieben
    wurde; formatiert würde also jede geänderte Datei im Baum — im geteilten
    Arbeitsbaum wäre das ein Eingriff in die Arbeit von drei anderen Sitzungen.

    Gefragt wird gegen **HEAD** und nicht gegen den Index: Im geteilten Baum
    steht im Index der Zwischenstand fremder Sitzungen (`.claude/rules/tests.md`).
    Und weil auch fremde Dateien in der Liste stehen, nennt der Hinweis den
    Dateinamen — wer ihn liest, sieht selbst, ob er ihm gehört.
    """
    if not SCHREIBT_DATEI.search(befehl):
        return ""
    dateien: list[str] = []
    for argumente in (
        ("diff", "--name-only", "HEAD", "--", "*.py"),
        ("ls-files", "--others", "--exclude-standard", "--", "*.py"),
    ):
        try:
            lauf = subprocess.run(
                ["git", *argumente], capture_output=True, text=True, timeout=15, cwd=WURZEL
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        dateien += [zeile.strip() for zeile in lauf.stdout.splitlines() if zeile.strip()]
    if not dateien:
        return ""

    hinweise: list[str] = []
    for aufgabe in (
        ("check", "--quiet", "--force-exclude"),
        ("format", "--check", "--quiet", "--force-exclude"),
    ):
        schluss, ausgabe = ruff(*aufgabe, *dateien)
        if schluss != 0 and ausgabe.strip():
            hinweise.append(f"ruff {aufgabe[0]} meldet:\n" + ausgabe.strip()[:1200])
    return "\n\n".join(hinweise)


#: Wie frisch ``HEAD`` sein muss, damit der Commit als eben gelaufen gilt.
#: Großzügig gegen eine langsame Maschine, kurz genug, dass der Commit von
#: vorhin nicht mitzählt.
COMMIT_FRISCH_SEKUNDEN = 60


def _gerade_committet() -> bool:
    """Hat der Befehl wirklich einen Commit hinterlassen?

    Der Hook erkennt einen Commit am Befehlstext, und das reicht nicht: Am
    22.08.2026 scheiterte ein ``git commit`` an der fehlenden Git-Identität,
    und der Hinweis erschien trotzdem. Ein Hinweis, der bei Fehlschlägen
    anschlägt, wird nach dem dritten Mal überlesen — und dann fehlt er in dem
    Augenblick, für den er gebaut ist.

    Gefragt wird deshalb **Git und nicht die Werkzeugantwort**: Ein
    gescheiterter Commit lässt ``HEAD`` stehen, wo es war. Das ist eine
    Tatsache über die Welt und hängt an keinem Feldnamen, den eine spätere
    Fassung umbenennen könnte.

    Die Grenze der Auskunft: Committet eine **andere** Sitzung im selben
    Arbeitsbaum in derselben Minute, sieht dieser Hook ihren Commit für seinen
    an. Der Hinweis ist dann überflüssig, nicht falsch — die anderen zu
    unterrichten schadet auch dann nicht.
    """
    try:
        lauf = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=WURZEL,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    try:
        return time.time() - float(lauf.stdout.strip()) < COMMIT_FRISCH_SEKUNDEN
    except ValueError:
        return False


def _commit_hinweis(befehl: str) -> str:
    """Nach einem Commit daran erinnern, es den anderen Sitzungen zu sagen.

    **Gibt den Text zurück, statt ihn zu melden**, seit :func:`testlauf` zwei
    Hinweise haben kann (der andere ist :func:`_ruff_hinweis`): Zwei
    ``melden``-Aufrufe schreiben zwei JSON-Objekte auf denselben Strom, und das
    ist keine Antwort mehr.

    **Der Hinweis geht an die eigene Sitzung, nicht an die anderen**, und das
    ist keine Sparsamkeit, sondern eine Grenze: Ein Hook hat den Schlüssel
    seiner eigenen Sitzung (``CLAUDE_CODE_MESSAGING_TOKEN``), und ein fremdes
    Postfach verlangt unter Windows genau dessen Schlüssel. Von hier aus lässt
    sich also niemand anderes erreichen — das Senden bleibt eine Entscheidung
    des Modells, und das ist die richtige Stelle dafür.

    Was der Hook beiträgt, ist der **Auslöser**. Am 22.08.2026 hat eine
    Nachbarsitzung dreimal nachgefragt, ob der Commit endlich liege; ein Satz
    im richtigen Augenblick hätte alle drei erspart. Ein Commit ist der eine
    Vorgang, der den gemeinsamen Stand ändert — deshalb hängt der Hinweis
    daran und nicht an jeder Änderung.
    """
    if not re.search(r"\bgit\b[^|;&]*\bcommit\b", befehl):
        return ""
    if not _gerade_committet():
        return ""
    andere = nachbarsitzungen()
    if not andere:
        return ""
    return (
        "Es arbeiten weitere Sitzungen an diesem Projekt: "
        + ", ".join(andere)
        + ". Ein Commit ändert den gemeinsamen Stand — sag ihnen kurz, was gelandet ist "
        "und was das für ihre Dateien heißt. Welches Gebiet wer hält, steht in "
        "`python tools/session_board.py list`; die verbindliche Liste der Sitzungen gibt "
        "`/list-agents`, denn "
        "dieser Hinweis liest internen Zustand und kann jemanden übersehen."
    )


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
