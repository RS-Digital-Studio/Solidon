"""Hooks für Claude Code und Codex in diesem Projekt.

Ein Skript, fünf Aufgaben — welche, sagt das erste Argument:

    sitzungsstart    SessionStart: sagt, in welchem Projekt wir sind. Die
                     globale Konfiguration beschreibt ein Avalonia-Projekt;
                     dieses hier ist Python. Prüft dabei, ob die Umgebung dem
                     festgeschriebenen Stand entspricht — drei Maschinen am
                     selben Repository heißen sonst mehrere Versionssätze.
    nach-aenderung   PostToolUse (Write|Edit): formatiert die geänderte
                     Python-Datei und meldet Lint-Befunde sowie Verstöße gegen
                     die harten Regeln, die sich rein syntaktisch erkennen
                     lassen.
    testlauf         PostToolUse (Bash): merkt sich je Sitzung den letzten
                     erkannten Testaufruf; Erfolg und Abdeckung prüft der Agent.
    abschluss        Stop: erinnert daran, wenn seit der letzten Änderung an
                     app/, tests/ oder tools/ kein Testaufruf erfasst ist.
    vor-bash         PreToolUse (Bash): fragt nach, bevor ein Befehl Arbeit
                     verwirft (Regel „niemals reverten"). Codex blockiert den
                     ersten Versuch, weil es die Entscheidung „ask" noch
                     nicht unterstützt.

Codex-Aufrufe tragen zusätzlich das zweite Argument ``--codex``. Die
Kennzeichnung kommt aus der jeweiligen Hook-Konfiguration und hängt damit
nicht von internen, nicht zugesagten Umgebungsvariablen ab.

Grundsatz: Ein Hook stört nie die Arbeit. Jeder Fehler endet still mit 0 —
lieber ein ausgefallener Hinweis als eine blockierte Sitzung.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
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
SESSION_START = WURZEL / ".claude" / ".state" / "sitzungsstart"

# Regeln, die sich am Text einer Datei erkennen lassen. Alles andere prüfen die
# Tests — ein Hook, der raten muss, meldet lieber nichts.
QT_IMPORT = re.compile(r"^\s*(?:from|import)\s+(?:PySide6|PyQt\d|shiboken\d?)\b", re.MULTILINE)
EVAL_AUFRUF = re.compile(r"(?<![\w.])(?:eval|exec)\s*\(")
PRINT_AUFRUF = re.compile(r"(?<![\w.])print\s*\(")
VERWIRFT = re.compile(
    r"git\s+(?:checkout\s+(?:--|\.|HEAD)|restore\b|reset\s+--hard\b|clean\s+-[a-z]*f)"
    r"|git\s+push\s+.*--force(?!-with-lease)"
)
CODEX_APPROVAL_MARKER = re.compile(
    r"SOLIDON3D_REVERT_FREIGEGEBEN\s*(?:=|:)\s*['\"]?ja\b", re.IGNORECASE
)
CODEX_ARGUMENT = "--codex"
#: Befehle, die eine Datei geschrieben haben können, ohne dass Write oder Edit
#: es gesehen hätte — ein Skript über die Shell, ein `sed -i`, eine Umleitung.
SCHREIBT_DATEI = re.compile(
    r"write_text|writelines|\bsed\s+-i|>\s*\S+\.py|\btee\b|ruff\s+format(?!\s+--check)"
)


def is_codex() -> bool:
    """Läuft der Hook in einer Codex-Sitzung?"""
    return CODEX_ARGUMENT in sys.argv[2:]


def eingabe() -> dict:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    try:
        data = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, UnicodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _session_path(path: Path, data: dict) -> Path:
    """Teststand und Erinnerung einer Sitzung bleiben unabhängig von anderen."""
    session_id = str(data.get("session_id") or "")
    if not session_id:
        return path
    key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:24]
    return path.with_name(f"{path.name}-{key}")


def melden(ereignis: str, text: str) -> None:
    """Gibt dem Agenten einen Hinweis mit, ohne die Handlung anzuhalten."""
    if ereignis == "Stop":
        # Stop kennt keinen additionalContext. Eine Warnung zeigt den Befund,
        # ohne aus einem unvollständigen Zeitstempelvergleich Arbeit auszulösen.
        json.dump({"systemMessage": text}, sys.stdout)
        return
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

    Der Prüfer läuft ohne Netz in einem begrenzten Unterprozess. Wird er nicht
    rechtzeitig fertig, bleibt der Projekthinweis samt manuellem Prüfweg erhalten.
    """
    try:
        lauf = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json; from tools.check_env import check; print(json.dumps(check()))",
            ],
            cwd=WURZEL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=True,
        )
        befunde, vorschlaege = json.loads(lauf.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return (
            " Die Umgebungsprüfung konnte beim Start nicht abgeschlossen werden. "
            "Prüfe sie mit `python tools/check_env.py`."
        )
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
    data = eingabe()
    start = _session_path(SESSION_START, data)
    if not start.exists():
        start.parent.mkdir(parents=True, exist_ok=True)
        start.write_text(str(time.time()), encoding="utf-8")
    if is_codex():
        workflow_note = (
            "Nach jedem Schritt laufen die betroffenen Tests; vor dem Commit das "
            "vollständige Tor mit `$pruefen` und der Regelcheck mit `$regelcheck`. "
        )
    else:
        workflow_note = (
            "Nach jedem Schritt laufen die betroffenen Tests; vor dem Commit das "
            "vollständige Tor mit `/pruefen` und der Regelcheck mit `/regelcheck`. "
        )
    melden(
        "SessionStart",
        "Projekt Solidon: Python mit PySide6, kein Avalonia und kein MVVM — "
        "die Stack-Angaben der globalen Konfiguration gelten hier nicht. "
        "Bezeichner, Dateinamen und Modulnamen auf Englisch; Docstrings, Kommentare, "
        "Doku, Commits und Gespräch auf Deutsch mit echten Umlauten. "
        "Der Kern (app/core) bleibt ohne Qt. "
        + workflow_note
        + "Die 22 harten Regeln stehen in AGENTS.md, das Sollverhalten im Bauplan."
        + umgebungshinweis(),
    )


def _changed_files(data: dict) -> list[Path]:
    """Liest geänderte Pfade aus Claude- oder Codex-Werkzeugeingaben."""
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return []
    raw_paths: list[str] = []
    file_path = tool_input.get("file_path")
    if isinstance(file_path, str) and file_path:
        raw_paths.append(file_path)

    patch = tool_input.get("command")
    if isinstance(patch, str):
        raw_paths.extend(
            match.group(1).strip()
            for match in re.finditer(
                r"^\*\*\* (?:(?:Add|Update) File|Move to): (.+)$", patch, re.MULTILINE
            )
        )

    files: list[Path] = []
    for raw_path in dict.fromkeys(raw_paths):
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path(data.get("cwd") or WURZEL) / path
        try:
            path.resolve().relative_to(WURZEL)
        except (OSError, ValueError):
            continue
        if path.suffix == ".py" and path.exists():
            files.append(path)
    return files


def _check_changed_file(path: Path) -> list[str]:
    """Formatiert und prüft genau eine vom Werkzeug geänderte Python-Datei."""
    relative = path.resolve().relative_to(WURZEL)
    notes: list[str] = []

    ruff("format", "--force-exclude", str(path))
    schluss, ausgabe = ruff("check", "--quiet", "--force-exclude", str(path))
    if schluss != 0 and ausgabe.strip():
        notes.append("ruff check meldet:\n" + ausgabe.strip()[:1500])

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""

    im_kern = relative.parts[:2] == ("app", "core")
    if im_kern and QT_IMPORT.search(text):
        notes.append(
            "Regel 1: Qt unterhalb von ui/. In app/core darf kein PySide6 importiert "
            "werden — test_core_isolation.py fällt darüber. Kommunikation nach außen "
            "läuft über den OpContext."
        )
    if im_kern and PRINT_AUFRUF.search(text):
        notes.append(
            "Der Kern gibt nichts aus. Fortschritt über ctx.progress, Rückfragen über "
            "ctx.ask, alles andere ins Protokoll."
        )
    if relative.parts[:1] == ("app",) and EVAL_AUFRUF.search(text):
        notes.append(
            "Regel 10: kein eval/exec. Parameterausdrücke laufen über den eigenen "
            "Auswerter mit beschränkter Grammatik (§32)."
        )

    return notes


def nach_aenderung() -> None:
    daten = eingabe()
    if daten.get("tool_name") == "apply_patch":
        # PostToolUse sieht in Codex auch Fehlversuche. Nur die Erfolgsausgabe
        # des Patchwerkzeugs erlaubt dem Hook, bestehende Dateien zu formatieren.
        response = daten.get("tool_response")
        if not isinstance(response, str) or not response.startswith("Success."):
            return
    hinweise = [note for path in _changed_files(daten) for note in _check_changed_file(path)]
    if hinweise:
        melden("PostToolUse", "\n\n".join(hinweise))


def testlauf() -> None:
    daten = eingabe()
    befehl = (daten.get("tool_input") or {}).get("command") or ""
    if _test_command(befehl) and not _tool_failed(daten):
        try:
            marker = _session_path(MARKE, daten)
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(str(time.time()), encoding="utf-8")
        except OSError:
            pass
    hinweis = _ruff_hinweis(befehl)
    if hinweis:
        melden("PostToolUse", hinweis)


def _test_command(command: str, *, depth: int = 0) -> bool:
    """Erkennt Testaufrufe, keine Erwähnungen, Hilfetexte oder Sammlungen.

    Die Marke belegt nur einen Aufruf. Codex liefert für Shellwerkzeuge nicht
    durchgehend einen strukturierten Exit-Code; grün muss der Agent selbst lesen.
    """
    if depth > 8:
        return False
    try:
        lexer = shlex.shlex(command.replace("\\", "/"), posix=True, punctuation_chars=";&|\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return False
    statement: list[str] = []
    for token in [*tokens, ";"]:
        if token and set(token) <= set(";&|\n"):
            if _test_invocation(statement, depth):
                return True
            statement = []
        else:
            statement.append(token)
    return False


def _test_invocation(tokens: list[str], depth: int) -> bool:
    """Entpackt ausschließlich die im Prüfablauf verwendeten Aufrufhüllen."""
    while tokens and re.match(r"(?:\$env:)?[A-Za-z_][A-Za-z_0-9]*=", tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return False
    runner = tokens[0].rsplit("/", 1)[-1].lower()
    arguments = tokens[1:]
    if runner in {
        "bash",
        "bash.exe",
        "sh",
        "zsh",
        "pwsh",
        "pwsh.exe",
        "powershell",
        "powershell.exe",
    }:
        for index, argument in enumerate(arguments):
            if argument.lower() in {"-c", "-lc", "-command"} and index + 1 < len(arguments):
                return _test_command(arguments[index + 1], depth=depth + 1)
        return bool(arguments and arguments[0].rsplit("/", 1)[-1] == "suite-getrennt.sh")
    if runner == "suite-getrennt.sh":
        return True
    if any(token in {"--help", "-h", "--collect-only", "--co"} for token in arguments):
        return False
    if runner in {"pytest", "pytest.exe", "py.test"}:
        return True
    if runner not in {"$suite_python", "${suite_python}", "$env:suite_python"} and not re.fullmatch(
        r"(?:python[\d.]*|py)(?:\.exe)?", runner
    ):
        return False
    while arguments:
        if arguments[0] in {"-u", "-B", "-I", "-S"} or re.fullmatch(r"-3(?:\.\d+)*", arguments[0]):
            arguments = arguments[1:]
        elif arguments[0] in {"-X", "-W"} and len(arguments) > 1:
            arguments = arguments[2:]
        else:
            break
    if arguments[:2] == ["-m", "pytest"]:
        return True
    if arguments and arguments[0].rsplit("/", 1)[-1] == "affected_tests.py":
        return "--run" in arguments[1:]
    return False


def _tool_failed(data: dict) -> bool:
    """Explizite Fehler dürfen keinen Testaufruf quittieren."""
    response = data.get("tool_response")
    if isinstance(response, dict):
        return bool(
            response.get("isError")
            or response.get("interrupted")
            or response.get("exit_code") not in (None, 0)
            or response.get("exitCode") not in (None, 0)
        )
    if isinstance(response, str):
        return bool(re.search(r"(?:Process exited with code|Exit code:)\s*[1-9]\d*", response))
    return False


def _ruff_hinweis(befehl: str) -> str:
    """Was ruff zu den Dateien sagt, die dieser Shell-Befehl geschrieben haben
    könnte.

    **Die Lücke, die dieser Hinweis schließt, und sie ist heute zugeschnappt.**
    :func:`nach_aenderung` prüft jede geänderte Python-Datei — aber nur, wenn
    das Modell Write oder Edit benutzt hat. Eine Änderung über die Shell sieht
    der Matcher ``Write|Edit`` nicht, und am 24.08.2026 kam so eine Zeile von
    102 Zeichen ins Tor: Geprüft wurde ruff **mit Pfadangabe** auf die eine
    Datei, die man im Kopf hatte, die zweite fiel erst später auf.

    **Geprüft, nicht formatiert**, und das ist der Unterschied zum Hook nach
    Write und Edit. Der kennt die eine Datei, die gerade geschrieben wurde, und
    darf sie formatieren. Hier ist nur bekannt, dass *irgendetwas* geschrieben
    wurde; formatiert würde also jede geänderte Datei im Baum, auch eine, die
    mit dem Befehl nichts zu tun hat.

    Gefragt wird gegen **HEAD** und nicht gegen den Index: Was vorgemerkt ist,
    ist deshalb noch nicht geprüft. Der Hinweis nennt den Dateinamen, damit
    beim Lesen klar ist, worum es geht.
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


def abschluss() -> None:
    data = eingabe()
    marker = _session_path(MARKE, data)
    remembered = _session_path(ERINNERT, data)
    started = _session_path(SESSION_START, data)
    try:
        zuletzt = max(
            (
                float(path.read_text(encoding="utf-8"))
                for path in (marker, started)
                if path.exists()
            ),
            default=0.0,
        )
    except (OSError, ValueError):
        zuletzt = 0.0

    juenger: list[str] = []
    stamps: list[str] = []
    for gebiet in ("app", "tests", "tools"):
        for datei in (WURZEL / gebiet).rglob("*.py"):
            if "__pycache__" in datei.parts:
                continue
            try:
                stat = datei.stat()
                if stat.st_mtime > zuletzt:
                    juenger.append(str(datei.relative_to(WURZEL)))
                    stamps.append(f"{juenger[-1]}:{stat.st_mtime_ns}")
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
        stand = "|".join(sorted(stamps))
        try:
            if remembered.exists() and remembered.read_text(encoding="utf-8") == stand:
                return
            remembered.parent.mkdir(parents=True, exist_ok=True)
            remembered.write_text(stand, encoding="utf-8")
        except OSError:
            pass

        gezeigt = ", ".join(juenger[:3]) + (" und weitere" if len(juenger) > 3 else "")
        melden(
            "Stop",
            f"Seit der letzten Änderung ({gezeigt}) wurde für diese Sitzung kein "
            "Testaufruf erfasst. Die Marke prüft weder Erfolg noch Testabdeckung. "
            "Die Arbeitsweise dieses Projekts verlangt nach jedem Schritt die "
            "betroffenen: .venv\\Scripts\\python.exe tools/affected_tests.py --run "
            f"— und vor dem Commit {'$pruefen' if is_codex() else '/pruefen'} für "
            "das vollständige Tor. (`pytest -q` am Stück kommt seit dem 16.08.2026 "
            "nicht mehr durch: rund zwanzig Minuten, dann ein Speicherabriss.) "
            "Der Hook sieht nur den Zeitstempel, nicht den Urheber.",
        )


def vor_bash() -> None:
    daten = eingabe()
    befehl = (daten.get("tool_input") or {}).get("command") or ""
    if not VERWIRFT.search(befehl):
        return
    if is_codex():
        if CODEX_APPROVAL_MARKER.search(befehl):
            return
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "Dieser Befehl verwirft Arbeit. Frage Robert ausdrücklich. "
                        "Nach seiner Freigabe darf derselbe Befehl mit dem Marker "
                        "SOLIDON3D_REVERT_FREIGEGEBEN=ja erneut ausgeführt werden."
                    ),
                }
            },
            sys.stdout,
        )
        return
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    "Dieser Befehl verwirft Arbeit. In diesem Projekt gilt: niemals "
                    "reverten, immer vorwärts fixen. Nur nach ausdrücklicher "
                    "Freigabe ausführen."
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
