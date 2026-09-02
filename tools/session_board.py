"""Wer arbeitet gerade woran — damit zwei Sitzungen nicht dasselbe anfassen.

An diesem Projekt laufen oft zwei bis vier Claude-Sitzungen. Sie können
einander schreiben, und das reicht für zwei; ab drei reicht es nicht mehr.

**Der Grund steht im Protokoll vom 22.08.2026.** Zwei Sitzungen haben ihre
Gebiete in zwei Nachrichten verabredet, und es hat getragen — aber zweimal
haben sich die Nachrichten *gekreuzt*: Beide hatten denselben Satz in
`CLAUDE.md` gefunden, beide wollten ihn ändern, und dass es nicht doppelt
passierte, lag daran, dass eine von beiden vorher fragte. Bei vier Sitzungen
kreuzen sich Nachrichten nicht gelegentlich, sondern ständig — und eine
Absprache, die nur gesagt wurde, kann niemand nachlesen, der später dazukommt.

Also steht sie hier. Eine Datei je Sitzung, kein gemeinsames Dokument: Zwei
Sitzungen, die gleichzeitig schreiben, können sich so nicht überschreiben.
Dieselbe Überlegung wie bei den Postfächern von Claude Code.

**Der Ort ist das gemeinsame Git-Verzeichnis** (``git rev-parse
--git-common-dir``). Es ist für jeden Arbeitsbaum derselbe und für jeden Klon
ein anderer — genau die Reichweite, die eine Absprache braucht.

**Eine tote Sitzung verschwindet von allein.** Der Eintrag trägt den Pfad des
Postfachs, das Claude Code für jede Sitzung anlegt; die benannte Pipe gibt es
nur, solange die Sitzung lebt. Am 22.08.2026 gemessen: Die Prüfung darauf
stimmte auf Anhieb mit ``/list-agents`` überein, während die Prozessnummer
allein fünf Fehltreffer lieferte.

Aufrufe::

    python tools/session_board.py claim --area "Oberfläche" --files "app/ui/**"
    python tools/session_board.py list
    python tools/session_board.py release

``list`` endet mit 0, wenn niemand sonst da ist, und mit 1, wenn jemand da ist
— damit ein Skript danach entscheiden kann.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Als Skript gestartet (``python tools/session_board.py``) liegt ``tools/``
# selbst im Suchpfad, das Paket darüber nicht — dasselbe Muster wie in
# ``make_changelog.py``.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.gate_lock import common_dir


def _board() -> Path:
    folder = common_dir() / "solidon-sitzungen"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _own_mailbox() -> str:
    """Das eigene Postfach — der Beleg, dass diese Sitzung lebt.

    Claude Code reicht es jedem Hook und jedem Bash-Befehl als
    ``CLAUDE_CODE_MESSAGING_SOCKET`` durch. Fehlt es, trägt der Eintrag keinen
    Lebensnachweis, und dann zählt nur noch das Alter.
    """
    return str(os.environ.get("CLAUDE_CODE_MESSAGING_SOCKET") or "")


def _own_name() -> str:
    """Wie diese Sitzung heißt — so, wie die anderen sie adressieren.

    Aus dem Register von Claude Code, über die eigene Prozessnummer. Steht dort
    nichts, bleibt der Name offen: Ein geratener Name wäre schlimmer als
    keiner, weil ihn niemand anschreiben kann.
    """
    pid = str(os.environ.get("CLAUDE_PID") or "")
    if not pid:
        return ""
    entry = Path.home() / ".claude" / "sessions" / f"{pid}.json"
    try:
        return str(json.loads(entry.read_text(encoding="utf-8")).get("name") or "")
    except (OSError, ValueError):
        return ""


#: Wie alt ein Eintrag ohne Postfach werden darf, bevor er als verlassen gilt.
#: Nur der Rückfall — normalerweise entscheidet das Postfach.
MAX_AGE_SECONDS = 12 * 60 * 60


def _alive(entry: dict[str, object]) -> bool:
    mailbox = str(entry.get("mailbox") or "")
    if mailbox:
        try:
            return Path(mailbox).exists()
        except OSError:
            return False
    return time.time() - float(entry.get("since") or 0.0) < MAX_AGE_SECONDS


def _entries() -> list[tuple[Path, dict[str, object]]]:
    found = []
    for path in sorted(_board().glob("*.json")):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue
        if not _alive(entry):
            # Aufräumen ist eine Nebenwirkung des Nachsehens, kein eigener
            # Befehl: Ein Aufräumbefehl, den man aufrufen muss, wird vergessen.
            path.unlink(missing_ok=True)
            continue
        found.append((path, entry))
    return found


def _key() -> str:
    """Der Dateiname des eigenen Eintrags — je Sitzung genau einer."""
    return _own_name() or str(os.environ.get("CLAUDE_PID") or "unbenannt")


def claim(area: str, files: str, note: str) -> int:
    """Trägt ein, woran diese Sitzung arbeitet."""
    name = _own_name()
    entry = {
        "name": name or "(ohne Namen — /list-agents fragen)",
        "area": area,
        "files": files,
        "note": note,
        "cwd": str(Path.cwd()),
        "mailbox": _own_mailbox(),
        "since": time.time(),
    }
    path = _board() / f"{_key()}.json"
    try:
        path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as problem:
        print(f"Nicht eingetragen ({problem}) — sag dein Gebiet den anderen direkt.")
        return 1
    print(f"Eingetragen als {entry['name']}: {area or '(kein Gebiet)'}")
    others = [e for p, e in _entries() if p != path]
    if others:
        print("Sag es auch denen, die schon da sind:")
        for other in others:
            print(f"  {other.get('name')} — {other.get('area') or '(kein Gebiet)'}")
    return 0


def show() -> int:
    """1 heißt: es ist noch jemand da."""
    mine = _board() / f"{_key()}.json"
    entries = _entries()
    others = [e for p, e in entries if p != mine]
    if not entries:
        print("Niemand hat ein Gebiet eingetragen.")
        return 0
    for path, entry in entries:
        wer = " (ich)" if path == mine else ""
        alter = (time.time() - float(entry.get("since") or 0.0)) / 60
        gebiet = entry.get("area") or "(kein Gebiet)"
        print(f"{entry.get('name')}{wer} — {gebiet}, seit {alter:.0f} min")
        if entry.get("files"):
            print(f"    Dateien: {entry.get('files')}")
        if entry.get("note"):
            print(f"    {entry.get('note')}")
    return 1 if others else 0


def release() -> int:
    path = _board() / f"{_key()}.json"
    if not path.exists():
        print("Es lag kein Eintrag.")
        return 0
    path.unlink(missing_ok=True)
    print("Gebiet freigegeben.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="task", required=True)

    taking = sub.add_parser("claim", help="eintragen, woran diese Sitzung arbeitet")
    taking.add_argument("--area", default="", help="das Gebiet in wenigen Worten")
    taking.add_argument("--files", default="", help="welche Pfade dazugehören")
    taking.add_argument("--note", default="", help="was die anderen sonst wissen müssen")

    sub.add_parser("list", help="wer arbeitet gerade woran")
    sub.add_parser("release", help="das eigene Gebiet wieder freigeben")

    args = parser.parse_args()
    if args.task == "claim":
        return claim(args.area, args.files, args.note)
    if args.task == "release":
        return release()
    return show()


if __name__ == "__main__":
    raise SystemExit(main())
