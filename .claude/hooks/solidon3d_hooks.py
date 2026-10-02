"""Hooks für Claude Code und Codex in diesem Projekt.

Ein Skript, fünf Aufgaben — welche, sagt das erste Argument:

    sitzungsstart    SessionStart: meldet nur, was die Unterlagen nicht wissen
                     können — eine Umgebung, die vom festgeschriebenen Stand
                     abweicht (drei Maschinen am selben Repository heißen
                     sonst mehrere Versionssätze), und Erinnerungen, die ein
                     Pull aus dem Arbeitsbaum genommen hat. Räumt alte
                     Sitzungsmarken weg.
    nach-aenderung   PostToolUse (Write|Edit): formatiert die geänderte
                     Python-Datei und meldet Lint-Befunde sowie Verstöße gegen
                     die harten Regeln, die sich rein syntaktisch erkennen
                     lassen. Einer neuen Erinnerungsdatei nennt es die
                     nächstliegenden vorhandenen Themen.
    testlauf         PostToolUse (Bash): merkt sich je Sitzung den letzten
                     erkannten Testaufruf; Erfolg und Abdeckung prüft der Agent.
    abschluss        Stop: erinnert daran, wenn seit der letzten Änderung an
                     app/, tests/ oder tools/ kein Testaufruf erfasst ist.
    vor-bash         PreToolUse (Bash, PowerShell): fragt nach, bevor ein
                     Befehl Arbeit verwirft (Regel „niemals reverten") oder
                     ein Werkzeug startet, das Geld kostet oder etwas
                     veröffentlicht — in jeder Schreibweise des Aufrufs.
                     Codex blockiert den ersten Versuch, weil es die
                     Entscheidung „ask" noch nicht unterstützt.

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
#
# Vor `vor-bash` und `testlauf` steht in `.claude/settings.json` ein
# `case`-Vorfilter: Python startet nur, wenn die Nutzlast ein Wort trägt, auf
# das VERWIRFT, RUECKFRAGE_WERKZEUGE, SCHREIBT_DATEI oder `_test_command`
# reagieren können. Wer einen
# Auslöser ergänzt, zieht die Muster dort nach;
# `tests/test_solidon3d_hooks.py` prüft die Obermenge.
QT_IMPORT = re.compile(r"^\s*(?:from|import)\s+(?:PySide6|PyQt\d|shiboken\d?)\b", re.MULTILINE)
EVAL_AUFRUF = re.compile(r"(?<![\w.])(?:eval|exec)\s*\(")
PRINT_AUFRUF = re.compile(r"(?<![\w.])print\s*\(")
#: Ein Git-Aufruf samt Vorab-Optionen — `git -C <pfad> …` ist in einem Baum mit
#: mehreren Worktrees die übliche Form, und ohne diesen Teil ging sie durch.
_GIT = r"git(?:\s+(?:-[Cc]\s+(?:\"[^\"]*\"|'[^']*'|\S+)|--?[\w-]+(?:=\S+)?))*\s+"
VERWIRFT = re.compile(
    _GIT + r"(?:checkout\s+(?:-f\b|--force\b|--(?:\s|$)|\.(?:\s|$)|HEAD\b|\S+\s+--\s)"
    r"|switch\s+(?:\S+\s+)*(?:-f|--force|--discard-changes)\b"
    r"|restore\b"
    r"|reset\s+(?:\S+\s+)*--hard\b"
    r"|clean\s+(?:\S+\s+)*(?:-[a-zA-Z]*f[a-zA-Z]*|--force)\b"
    r"|push\s+(?:.*\s)?(?:--force(?!-with-lease)\b|-f\b|\+\S)"
    r"|stash\s+(?:drop|clear)\b"
    r"|branch\s+(?:\S+\s+)*-D\b"
    r"|rebase\b"
    r"|pull\s+(?:.*\s)?--rebase\b"
    r"|worktree\s+remove\s+(?:\S+\s+)*(?:-f|--force)\b"
    r"|filter-(?:branch|repo)\b)"
)
CODEX_APPROVAL_MARKER = re.compile(
    r"SOLIDON3D_REVERT_FREIGEGEBEN\s*(?:=|:)\s*['\"]?ja\b", re.IGNORECASE
)
CODEX_ARGUMENT = "--codex"
#: Werkzeuge, die Geld kosten oder etwas veröffentlichen. Dieselbe Liste steht
#: als `ask` in `.claude/settings.json`; jene Regeln sind Präfixregeln und
#: treffen nur eine Schreibweise, hier wird am Werkzeugnamen gefragt.
#: `tests/test_solidon3d_hooks.py` hält beide Listen gleich.
RUECKFRAGE_WERKZEUGE = (
    "run_agent_suite",
    "upload_website",
    "deploy_activation_server",
    "check_support",
    "sign_release",
    "make_licence_keys",
)
CODEX_WERKZEUG_MARKER = re.compile(
    r"SOLIDON3D_WERKZEUG_FREIGEGEBEN\s*(?:=|:)\s*['\"]?ja\b", re.IGNORECASE
)
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


def erinnerungshinweis() -> str:
    """Holt die Erinnerungen zurück, wenn ein Pull sie aus dem Arbeitsbaum nahm.

    `.claude/memory/` steht in `.gitignore`; der Commit, der die Dateien aus
    dem Index nahm, löscht sie beim Pull auf jeder anderen Maschine.
    `tools/link_memory.py --wiederherstellen` holt den letzten versionierten
    Stand zurück, ohne eine vorhandene Datei zu überschreiben.
    """
    if (WURZEL / ".claude" / "memory" / "MEMORY.md").exists():
        return ""
    try:
        lauf = subprocess.run(
            [sys.executable, str(WURZEL / "tools" / "link_memory.py"), "--wiederherstellen"],
            cwd=WURZEL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return (
            " Die Erinnerungen fehlen. `python tools/link_memory.py --wiederherstellen` "
            "holt den letzten versionierten Stand zurück."
        )
    zeilen = lauf.stdout.strip().splitlines()
    return " " + zeilen[-1] if zeilen else ""


#: Wie alt eine Sitzungsmarke werden darf, bevor der Start sie wegräumt.
MARKEN_TAGE = 14


def marken_aufraeumen() -> None:
    """Löscht Sitzungsmarken, die älter als zwei Wochen sind.

    Jede Sitzung legt eigene Marken an (`_session_path`); ohne Aufräumen wächst
    `.claude/.state/` um bis zu drei Dateien je Sitzung.
    """
    grenze = time.time() - MARKEN_TAGE * 86400
    for vorlage in (SESSION_START, MARKE, ERINNERT):
        for datei in vorlage.parent.glob(f"{vorlage.name}-*"):
            try:
                if datei.stat().st_mtime < grenze:
                    datei.unlink()
            except OSError:
                continue


def sitzungsstart() -> None:
    """Meldet nur, was CLAUDE.md und AGENTS.md nicht wissen können.

    Sprache, Kerntrennung, Tor und die harten Regeln laden über die Unterlagen
    in jede Sitzung; sie hier ein zweites Mal zu sagen, kostete Kontext und
    veraltete neben dem Original.
    """
    data = eingabe()
    start = _session_path(SESSION_START, data)
    if not start.exists():
        start.parent.mkdir(parents=True, exist_ok=True)
        start.write_text(str(time.time()), encoding="utf-8")
    marken_aufraeumen()
    hinweis = (umgebungshinweis() + erinnerungshinweis()).strip()
    if hinweis:
        melden("SessionStart", hinweis)


def _tool_paths(data: dict) -> list[Path]:
    """Die Pfade, die ein Claude- oder Codex-Werkzeug geschrieben hat, absolut."""
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

    paths: list[Path] = []
    for raw_path in dict.fromkeys(raw_paths):
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path(data.get("cwd") or WURZEL) / path
        paths.append(path)
    return paths


def _changed_files(data: dict) -> list[Path]:
    """Die geänderten Python-Dateien dieses Arbeitsbaums."""
    files: list[Path] = []
    for path in _tool_paths(data):
        try:
            path.resolve().relative_to(WURZEL)
        except (OSError, ValueError):
            continue
        if path.suffix == ".py" and path.exists():
            files.append(path)
    return files


#: Wörter, die in fast jeder Beschreibung stehen und kein Thema kennzeichnen.
_FUELLWOERTER = frozenset(
    {
        "nicht", "einen", "einer", "eines", "wird", "werden", "sind", "auch",
        "nach", "über", "oder", "sich", "dass", "beim", "eine", "diese", "wenn",
        "noch", "hier", "immer", "kein", "keine", "erst", "dann", "schon",
        "statt", "ohne", "zwei",
    }
)  # fmt: skip


def _stichwoerter(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zäöüß]{4,}", text.lower()) if w not in _FUELLWOERTER}


def _thema(path: Path, zeichen: int = 1500) -> str:
    """Name und Beschreibung einer Erinnerung, dazu der Anfang ihres Texts."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:zeichen]
    except OSError:
        return ""
    beschreibung = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    return f"{path.stem.replace('-', ' ')} {beschreibung.group(1) if beschreibung else ''}"


def themenhinweis(data: dict) -> str:
    """Eine neue Erinnerungsdatei bekommt die nächstliegenden Themen genannt.

    Erinnerungen sind Themendateien: Eine neue Erkenntnis gehört zuerst in das
    Thema, das sie schon hat. Neu heißt hier: im Verzeichnis und noch nicht in
    `MEMORY.md` — beim Ergänzen einer vorhandenen Datei schweigt der Hook.
    """
    ordner = (WURZEL / ".claude" / "memory").resolve()
    try:
        index = (ordner / "MEMORY.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    hinweise: list[str] = []
    for path in _tool_paths(data):
        try:
            path = path.resolve()
        except OSError:
            continue
        if (
            path.parent != ordner
            or path.suffix != ".md"
            or path.name == "MEMORY.md"
            or not path.exists()
            or f"]({path.name})" in index
        ):
            continue
        eigene = _stichwoerter(_thema(path, zeichen=3000))
        rangliste = sorted(
            (
                (len(eigene & _stichwoerter(_thema(other))), other.name)
                for other in ordner.glob("*.md")
                if other.name not in ("MEMORY.md", path.name)
            ),
            reverse=True,
        )
        naechste = [f"`{name}`" for treffer, name in rangliste[:3] if treffer > 0]
        hinweise.append(
            f"Neue Erinnerungsdatei `{path.name}`. Erinnerungen sind Themendateien: "
            "Gehört das zu einem vorhandenen Thema, dort als Abschnitt ergänzen und "
            "diese Datei wieder löschen. "
            + (
                f"Nächstliegend: {', '.join(naechste)}. "
                if naechste
                else "Kein Thema teilt Stichwörter — den Index trotzdem prüfen. "
            )
            + "Nur ein wirklich neues Thema bekommt eine eigene Datei und eine Zeile "
            "in `MEMORY.md`."
        )
    return "\n\n".join(hinweise)


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
    thema = themenhinweis(daten)
    if thema:
        hinweise.append(thema)
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
            "betroffenen Kerntests: .venv\\Scripts\\python.exe tools/affected_tests.py --run "
            f"— und vor dem Commit {'$pruefen' if is_codex() else '/pruefen'} für "
            "das Entwicklungstor aus Kernsammlung, Ruff, Format und mypy. "
            "Fensterdateien und Leistungsprüfungen bleiben bis zum Release zurückgestellt. "
            "Der Hook sieht nur den Zeitstempel, nicht den Urheber.",
        )


#: Ein Python-Interpreter als erstes Wort: `python`, `python3.14`, `py`,
#: `python.exe` unter jedem Pfad — oder eine Variable, die ihn trägt
#: (`"$SUITE_PYTHON"`, `$env:SUITE_PYTHON`).
_INTERPRETER = re.compile(r"(?:pythonw?[\d.]*|py)(?:\.exe)?", re.IGNORECASE)
_HUELLEN = {"bash", "bash.exe", "sh", "zsh", "pwsh", "pwsh.exe", "powershell", "powershell.exe"}


def _werkzeug_im_wort(wort: str) -> str | None:
    """`…/tools/upload_website.py`, `upload_website.py` oder `tools.upload_website`."""
    wort = wort.replace("\\", "/").casefold()
    for name in RUECKFRAGE_WERKZEUGE:
        if wort.rsplit("/", 1)[-1] == f"{name}.py" or wort in (f"tools.{name}", f"tools/{name}"):
            return name
    return None


class _ShellWord(str):
    """Behält bei einem zerlegten Wort, ob es tatsächlich ein Shelltrenner war."""

    punctuation = False
    quoted = False


def rueckfrage_werkzeug(command: str, *, depth: int = 0) -> str | None:
    """Welches Geld- oder Veröffentlichungswerkzeug der Befehl startet — sonst ``None``.

    Entscheidend ist das gestartete Skript, nicht der Pfad des Interpreters:
    relativ, absolut, über `"$SUITE_PYTHON"`, als `-m tools.x`, direkt als
    `./tools/x.py`, in PowerShell-Form oder in einer `bash -c`-Hülle. Wer die
    Datei nur liest, prüft oder nennt (`cat`, `ruff check`, `git log --`),
    startet sie nicht und wird nicht gefragt.
    """
    if depth > 8:
        return None
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|\n,()")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        lexer.escape = "`"
        lexer.wordchars += ","
        command_head = True
        cmdlet = False
        array_depth = 0
        tokens: list[_ShellWord] = []
        while True:
            # shlex kann ein Zeichen des nächsten Worts schon gelesen haben.
            start = lexer.instream.tell() - len(lexer._pushback_chars)
            value = lexer.get_token()
            end = lexer.instream.tell() - len(lexer._pushback_chars)
            if value is None:
                break
            raw = command[start:end].strip(" \t\r")
            while raw.startswith("#") and "\n" in raw:
                raw = raw.split("\n", 1)[1].lstrip(" \t\r")
            # Im c-Zustand kann shlex den nachfolgenden Kommentar mitlesen.
            punctuation = bool(value) and set(value) <= set(";&|\n,()") and raw.startswith(value)
            # Auch ");" wird getrennt: Das Array schließt vor dem nächsten Befehl.
            for text in value if punctuation else (value,):
                if punctuation and cmdlet and text == "(":
                    array_depth += 1
                elif punctuation and cmdlet and text == ")" and array_depth:
                    array_depth -= 1
                elif punctuation and text == "\n" and array_depth:
                    continue
                word = _ShellWord(text)
                word.punctuation = punctuation
                word.quoted = raw.startswith(("'", '"', "`"))
                tokens.append(word)
                if punctuation and text in ";&|\n" and not array_depth:
                    command_head = True
                    cmdlet = False
                    lexer.wordchars += "," if "," not in lexer.wordchars else ""
                elif command_head and not punctuation:
                    if text == "env" or re.match(r"(?:\$env:)?[A-Za-z_][A-Za-z_0-9]*=", text):
                        continue
                    command_head = False
                    cmdlet = text.casefold() in {"start-process", "start"}
                    if cmdlet:
                        lexer.wordchars = lexer.wordchars.replace(",", "")
    except ValueError:
        # Nicht zerlegbar: lieber einmal zu oft fragen als ein Werkzeug laufen lassen.
        return next((name for name in RUECKFRAGE_WERKZEUGE if name in command), None)
    statement: list[str] = []
    for token in [*tokens, ";"]:
        if getattr(token, "punctuation", True) and token and set(token) <= set(";&|\n"):
            found = _werkzeug_aufruf(statement, depth)
            if found:
                return found
            statement = []
        else:
            statement.append(token)
    return None


def _start_process_values(arguments: list[str], index: int) -> tuple[list[str], int] | None:
    """Liest einen literalen Cmdletwert, eine Kommaliste oder ein gewöhnliches Array."""
    values: list[str] = []
    if index >= len(arguments):
        return None
    if (
        arguments[index] == "@"
        and index + 1 < len(arguments)
        and arguments[index + 1] == "("
        and getattr(arguments[index + 1], "punctuation", True)
    ):
        index += 1
    if arguments[index] == "(" and getattr(arguments[index], "punctuation", True):
        index += 1
        while index < len(arguments) and not (
            arguments[index] == ")" and getattr(arguments[index], "punctuation", True)
        ):
            if arguments[index] != "," or not getattr(arguments[index], "punctuation", True):
                values.append(arguments[index])
            index += 1
        if index == len(arguments):
            return None
        return values, index + 1
    values.append(arguments[index])
    index += 1
    while (
        index < len(arguments)
        and arguments[index] == ","
        and getattr(arguments[index], "punctuation", True)
    ):
        if index + 1 == len(arguments):
            return None
        values.append(arguments[index + 1])
        index += 2
    return values, index


def _windows_arguments(argument_line: str) -> list[str]:
    """Zerlegt ausschließlich native Argumente nach Microsofts C-Startregeln."""
    arguments: list[str] = []
    word: list[str] = []
    quoted = False
    started = False
    index = 0
    while index < len(argument_line):
        char = argument_line[index]
        if char in " \t" and not quoted:
            if started:
                arguments.append("".join(word))
                word = []
                started = False
            index += 1
            continue
        started = True
        if char == "\\":
            end = index
            while end < len(argument_line) and argument_line[end] == "\\":
                end += 1
            count = end - index
            if end == len(argument_line) or argument_line[end] != '"':
                word.append("\\" * count)
                index = end
                continue
            word.append("\\" * (count // 2))
            if count % 2:
                word.append('"')
                index = end + 1
                continue
            index = end
            char = '"'
        if char == '"':
            if quoted and index + 1 < len(argument_line) and argument_line[index + 1] == '"':
                word.append('"')
                index += 2
            else:
                quoted = not quoted
                index += 1
        else:
            word.append(char)
            index += 1
    if started:
        arguments.append("".join(word))
    return arguments


def _start_process_invocation(arguments: list[str], depth: int) -> str | None:
    """Bindet benannte Werte zuerst; nur freie Werte belegen Programm und ArgumentList."""
    if depth >= 8:
        return None
    program: str | None = None
    values: list[str] | None = None
    positional: list[list[str]] = []
    switches = {
        "-loaduserprofile",
        "-nonewwindow",
        "-passthru",
        "-wait",
        "-usenewenvironment",
        "-whatif",
        "-confirm",
        "-verbose",
        "-debug",
    }
    index = 0
    while index < len(arguments):
        option = arguments[index].casefold()
        named = option.startswith("-") and not getattr(arguments[index], "quoted", False)
        if named:
            option, separator, bound_value = arguments[index].partition(":")
            option = option.casefold()
        if named and option.split(":", 1)[0] in switches:
            index += 1
            continue
        if named and separator and bound_value:
            # Nur der erste Doppelpunkt bindet; der Wert bleibt ein Literal.
            bound_word = _ShellWord(bound_value)
            bound_word.quoted = True
            arguments = [*arguments[: index + 1], bound_word, *arguments[index + 1 :]]
        parsed = _start_process_values(arguments, index + 1 if named else index)
        if parsed is None:
            return None
        value, index = parsed
        if named:
            if option in {"-filepath", "-pspath", "-path"}:
                if len(value) != 1:
                    return None
                program = value[0]
            elif option in {"-argumentlist", "-args"}:
                values = value
            # Andere benannte Parameter bleiben Werte ihres Parameters.
        else:
            positional.append(value)
    if program is None and positional:
        first = positional.pop(0)
        if len(first) != 1:
            return None
        program = first[0]
    if values is None and positional:
        values = positional.pop(0)
    if not program or positional:
        return None
    # Start-Process verbindet Arraywerte mit Leerzeichen. Deren Argumente
    # bleiben Daten: Ein Semikolon darin startet keinen zweiten Shellbefehl.
    native_arguments = _windows_arguments(" ".join(values or []))
    return _werkzeug_aufruf([program, *native_arguments], depth + 1)


def _werkzeug_aufruf(tokens: list[str], depth: int) -> str | None:
    while tokens and re.match(r"(?:\$env:)?[A-Za-z_][A-Za-z_0-9]*=", tokens[0]):
        tokens = tokens[1:]
    if tokens and tokens[0] == "env":
        return _werkzeug_aufruf(tokens[1:], depth)
    if not tokens:
        return None
    runner = tokens[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    arguments = tokens[1:]
    if runner in _HUELLEN:
        for index, argument in enumerate(arguments):
            if argument.lower() in {"-c", "-lc", "-command"} and index + 1 < len(arguments):
                return rueckfrage_werkzeug(arguments[index + 1], depth=depth + 1)
        return _werkzeug_im_wort(arguments[0]) if arguments else None
    if runner in {"start-process", "start"}:
        return _start_process_invocation(arguments, depth)
    direct = _werkzeug_im_wort(tokens[0])
    if direct:
        return direct
    if not (tokens[0].startswith("$") or _INTERPRETER.fullmatch(runner)):
        return None
    while arguments:
        if arguments[0] in {"-u", "-B", "-I", "-S", "-E", "-O", "-OO", "-s", "-q"} or (
            re.fullmatch(r"-3(?:\.\d+)*", arguments[0])
        ):
            arguments = arguments[1:]
        elif arguments[0] in {"-X", "-W"} and len(arguments) > 1:
            arguments = arguments[2:]
        elif arguments[0].startswith(("-X", "-W")) and len(arguments[0]) > 2:
            arguments = arguments[1:]
        else:
            break
    if not arguments:
        return None
    if arguments[0] == "-m":
        return _werkzeug_im_wort(arguments[1]) if len(arguments) > 1 else None
    if arguments[0].startswith("-"):
        return None
    return _werkzeug_im_wort(arguments[0])


def _entscheidung(entscheidung: str, grund: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": entscheidung,
                "permissionDecisionReason": grund,
            }
        },
        sys.stdout,
    )


def vor_bash() -> None:
    """Fragt vor verwerfenden Git-Befehlen und vor Geld- und Veröffentlichungswerkzeugen.

    Codex unterstützt die Entscheidung „ask" nicht und blockiert deshalb, bis
    Roberts Freigabe als Marker im Befehl steht.
    """
    daten = eingabe()
    befehl = (daten.get("tool_input") or {}).get("command") or ""
    if VERWIRFT.search(befehl):
        if not is_codex():
            _entscheidung(
                "ask",
                "Dieser Befehl verwirft Arbeit. In diesem Projekt gilt: niemals "
                "reverten, immer vorwärts fixen. Nur nach ausdrücklicher "
                "Freigabe ausführen.",
            )
        elif not CODEX_APPROVAL_MARKER.search(befehl):
            _entscheidung(
                "deny",
                "Dieser Befehl verwirft Arbeit. Frage Robert ausdrücklich. "
                "Nach seiner Freigabe darf derselbe Befehl mit dem Marker "
                "SOLIDON3D_REVERT_FREIGEGEBEN=ja erneut ausgeführt werden.",
            )
        return
    werkzeug = rueckfrage_werkzeug(befehl)
    if werkzeug is None:
        return
    if not is_codex():
        _entscheidung(
            "ask",
            f"tools/{werkzeug}.py kostet Geld oder veröffentlicht etwas. "
            "Nur ausführen, wenn Robert es ausdrücklich beauftragt hat.",
        )
    elif not CODEX_WERKZEUG_MARKER.search(befehl):
        _entscheidung(
            "deny",
            f"tools/{werkzeug}.py kostet Geld oder veröffentlicht etwas. Frage "
            "Robert ausdrücklich. Nach seiner Freigabe darf derselbe Befehl mit "
            "dem Marker SOLIDON3D_WERKZEUG_FREIGEGEBEN=ja erneut ausgeführt werden.",
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
