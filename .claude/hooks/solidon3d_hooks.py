"""Hooks für Claude Code und Codex in diesem Projekt.

Ein Skript, sechs Aufgaben — welche, sagt das erste Argument:

    sitzungsstart    SessionStart: sagt, in welchem Projekt wir sind. Die
                     globale Konfiguration beschreibt ein Avalonia-Projekt;
                     dieses hier ist Python. Prüft dabei, ob die Umgebung dem
                     festgeschriebenen Stand entspricht — mehrere Leute am
                     selben Repository heißt sonst mehrere Versionssätze.
    sitzungsende     SessionEnd: gibt das Gebiet dieser Sitzung auf dem
                     Sitzungsbrett frei, damit die nächste es nicht für
                     belegt hält.
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

import contextlib
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


def _nachbarhinweis() -> str:
    """Wer sonst gerade an diesem Projekt sitzt — falls jemand da ist.

    Beim Start zu wissen, dass man nicht allein ist, erspart die Runde, in der
    man es beim ersten Zusammenstoß erfährt. Ist niemand da, steht hier auch
    nichts: Ein Hinweis, der immer erscheint, wird nicht mehr gelesen.
    """
    andere = nachbarsitzungen()
    if not andere:
        return ""
    if is_codex():
        return (
            " ES ARBEITEN SCHON CLAUDE-CODE-SITZUNGEN HIER: "
            + ", ".join(andere)
            + ". Lies vor der ersten Änderung `python tools/session_board.py list`, "
            "meide ihre Gebiete und trag dein eigenes mit "
            '`python tools/session_board.py claim --area "…" --files "…"` ein. '
            "Codex kann diese Sitzungen nicht direkt anschreiben."
        )
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
    data = eingabe()
    start = _session_path(SESSION_START, data)
    if not start.exists():
        start.parent.mkdir(parents=True, exist_ok=True)
        start.write_text(str(time.time()), encoding="utf-8")
    if is_codex():
        workflow_note = (
            "Nach jedem Schritt laufen die betroffenen Tests; vor dem Commit das "
            "vollständige Tor mit `$pruefen` und der Regelcheck mit `$regelcheck`. "
            "Parallele Codex-Arbeit läuft in eigenen Aufgaben oder Worktrees. "
        )
    else:
        workflow_note = (
            "Nach jedem Schritt laufen die betroffenen Tests; vor dem Commit das "
            "vollständige Tor mit `/pruefen` und der Regelcheck mit `/regelcheck`. "
            "Hier arbeiten oft zwei bis vier Sitzungen gleichzeitig: `/list-agents` "
            "zeigt sie, `claude --worktree <name>` gibt jeder ihren eigenen Baum, und "
            "/pruefen nimmt ein Schloss, damit Messungen sich nicht verfälschen. "
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
        + _nachbarhinweis()
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
    # Gesammelt und **einmal** gemeldet: Zwei ``melden``-Aufrufe schreiben zwei
    # JSON-Objekte auf denselben Strom, und das ist keine Antwort mehr.
    hinweise = [text for text in (_ruff_hinweis(befehl), _commit_hinweis(befehl)) if text]
    if hinweise:
        melden("PostToolUse", "\n\n".join(hinweise))


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
    if (
        len(arguments) > 2
        and arguments[0].rsplit("/", 1)[-1] == "gate_lock.py"
        and arguments[1] == "run"
        and "--" in arguments
        and depth < 8
    ):
        return _test_invocation(arguments[arguments.index("--") + 1 :], depth + 1)
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
    if is_codex():
        return (
            "Es arbeiten Claude-Code-Sitzungen an diesem Projekt: "
            + ", ".join(andere)
            + ". Ein Commit ändert den gemeinsamen Stand. Prüfe deshalb "
            "`python tools/session_board.py list`; Codex kann diese Sitzungen nicht "
            "direkt anschreiben."
        )
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
            "Der Hook sieht nur den Zeitstempel, nicht den Urheber: stammt die Änderung "
            "aus einer parallel laufenden Sitzung, gehört sie nicht dir. Dann weder "
            "prüfen noch anfassen, sondern es beim Berichten erwähnen.",
        )


def sitzungsende() -> None:
    """SessionEnd: gibt das Gebiet dieser Sitzung auf dem Brett wieder frei.

    Ohne das bleibt der Eintrag liegen. Das Brett räumt zwar selbst auf — es
    prüft das Postfach der Sitzung —, aber erst, wenn das nächste Mal jemand
    nachsieht, und bei einer Codex-Sitzung ohne Postfach erst nach zwölf
    Stunden. Bis dahin liest die nächste Sitzung ein Gebiet als belegt, das
    niemand mehr hält, und weicht ihm aus.

    Wer das Gebiet noch braucht, trägt es in der nächsten Sitzung neu ein; ein
    Anspruch, der eine Sitzung überlebt, wäre eine Absprache, die niemand
    gekündigt hat.
    """
    data = eingabe()
    # Codex lässt höchstens drei Sekunden zu. Weder einen Git-Prozess noch
    # die Importkette des Torwerkzeugs starten; .git und commondir genügen.
    cwd = Path(data.get("cwd") or Path.cwd()).resolve()
    git_dir = next(
        (path / ".git" for path in (cwd, *cwd.parents) if (path / ".git").exists()), None
    )
    if git_dir is None:
        return
    if git_dir.is_file():
        pointer = git_dir.read_text(encoding="utf-8").strip()
        if not pointer.startswith("gitdir: "):
            return
        git_dir = (git_dir.parent / pointer.removeprefix("gitdir: ")).resolve()
    common = git_dir / "commondir"
    if common.exists():
        git_dir = (git_dir / common.read_text(encoding="utf-8").strip()).resolve()

    if is_codex():
        session_id = str(
            data.get("session_id")
            or os.environ.get("CODEX_THREAD_ID")
            or os.environ.get("CODEX_SESSION_ID")
            or ""
        )
        if not session_id:
            return
        key = f"codex-{session_id}"
    else:
        key = str(os.environ.get("CLAUDE_PID") or "")
        if not key:
            return
        entry = Path.home() / ".claude" / "sessions" / f"{key}.json"
        with contextlib.suppress(OSError, ValueError):
            key = str(json.loads(entry.read_text(encoding="utf-8")).get("name") or key)
    if Path(key).name != key or key in {".", ".."}:
        return
    (git_dir / "solidon-sitzungen" / f"{key}.json").unlink(missing_ok=True)


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
                    "reverten, immer vorwärts fixen — Reverts zerstören parallele "
                    "Arbeit. Nur nach ausdrücklicher Freigabe ausführen."
                ),
            }
        },
        sys.stdout,
    )


AUFGABEN = {
    "sitzungsstart": sitzungsstart,
    "sitzungsende": sitzungsende,
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
