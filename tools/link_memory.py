"""Die Erinnerungen dieser Sitzung in den Arbeitsbaum hängen (einmal je Maschine).

Claude Code legt seine Erinnerungen unter dem Nutzerprofil ab:
``~/.claude/projects/<Pfadkürzel>/memory``. Dieses Werkzeug macht aus dem Ort
eine **Verknüpfung** auf ``.claude/memory`` im Arbeitsbaum, damit Claude Code
und Codex dieselben Dateien lesen und schreiben.

**Git trägt die Erinnerungen nicht.** ``.claude/memory/`` steht in
``.gitignore``: Das Repository wird zu jedem Release öffentlich, und die
Erinnerungen nennen Zugangswege, Schlüsselablagen, Kundennamen und
Verkaufszahlen (Entscheidung Robert). Bis dahin waren sie versioniert; der
Pull, der sie aus dem Index nahm, löscht sie auf jeder anderen Maschine aus dem
Arbeitsbaum. ``--wiederherstellen`` holt dort den letzten versionierten Stand
zurück, ohne eine vorhandene Datei zu überschreiben; der Sitzungsstart ruft es
auf, sobald ``MEMORY.md`` fehlt.

Was schon im Nutzerprofil liegt, wird vorher in den Arbeitsbaum übernommen;
nichts geht verloren. Läuft das Werkzeug zweimal, sagt es das und tut nichts.

    python tools/link_memory.py                   # einrichten
    python tools/link_memory.py --pruefen         # nur sagen, wie es steht
    python tools/link_memory.py --wiederherstellen

Auf Windows entsteht eine Verzeichnisverknüpfung (Junction) — die braucht keine
erhöhten Rechte, anders als eine symbolische Verknüpfung. Auf Linux und macOS
ein Symlink.
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

#: Die Wurzel des Arbeitsbaums, zu dem dieses Werkzeug gehört.
ROOT = Path(__file__).resolve().parent.parent

#: Der Ort der Erinnerungen, so wie Git ihn nennt.
GIT_PATH = ".claude/memory"

#: Wo die Erinnerungen im Arbeitsbaum liegen.
IN_REPO = ROOT / GIT_PATH


def restore_from_history(root: Path) -> list[str]:
    """Holt fehlende Erinnerungen aus dem letzten versionierten Stand zurück.

    Der Stand steht im Elternteil des Commits, der ``MEMORY.md`` aus dem Index
    genommen hat. Zurück kommt jede Datei, **die hier fehlt**; eine vorhandene
    bleibt, wie sie ist — sie kann auf dieser Maschine weitergeschrieben sein.
    Ohne diesen Commit in der Historie gibt es nichts zurückzuholen.
    """
    found = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--diff-filter=D", "--", f"{GIT_PATH}/MEMORY.md"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    removal = found.stdout.strip()
    if found.returncode != 0 or not removal:
        return []
    archive = subprocess.run(
        ["git", "archive", "--format=tar", f"{removal}^", "--", GIT_PATH],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if archive.returncode != 0:
        return []
    restored: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as bundle:
        for member in bundle.getmembers():
            name = member.name
            if not member.isfile() or not name.startswith(GIT_PATH + "/") or ".." in name:
                continue
            target = root / name
            content = bundle.extractfile(member)
            if target.exists() or content is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.read())
            restored.append(name.removeprefix(GIT_PATH + "/"))
    return restored


def harness_dir(project: Path) -> Path:
    """Wohin Claude Code die Erinnerungen dieses Projekts legt.

    Das Kürzel entsteht aus dem absoluten Pfad, indem Trenner, Doppelpunkt
    **und Leerzeichen** zu Bindestrichen werden — ``C:\\Users\\rober\\Documents\\Solidon``
    wird zu ``C--Users-rober-Documents-Solidon``, ``F:\\3D Druck`` zu ``F--3D-Druck``.
    Abgelesen und nicht erraten: Der Ordner existiert auf jeder Maschine, auf der
    schon einmal eine Sitzung lief.

    Das Leerzeichen fehlte hier zuerst, und der Fehler war der unangenehme: Das
    Werkzeug rechnete ``F--3D Druck`` aus, fand dort nichts, legte den Ordner an,
    verknüpfte ihn und meldete „Eingerichtet". Übernommen wurde nichts — die
    achtundzwanzig Dateien lagen nebenan. Darum hält ``main`` jetzt an, wenn der
    berechnete Ort nicht existiert, statt einen leeren zweiten anzulegen.
    """
    slug = str(project).replace(":", "-").replace("\\", "-").replace("/", "-")
    slug = slug.replace(" ", "-")
    return Path.home() / ".claude" / "projects" / slug / "memory"


def linked(path: Path) -> bool:
    """Ob dieser Pfad schon eine Verknüpfung ist (Junction oder Symlink)."""
    if path.is_symlink():
        return True
    if os.name != "nt" or not path.exists():
        return False
    # Eine Junction ist kein Symlink im Sinne von `is_symlink`; sie trägt aber
    # das Reparse-Point-Bit. Gefragt wird mit ``lstat`` und nicht mit ``stat``:
    # ``stat`` folgt der Verknüpfung und liefert die Attribute des **Ziels**,
    # und das ist ein gewöhnliches Verzeichnis ohne dieses Bit. Einmal
    # hineingetappt: Das Werkzeug meldete „noch nicht verknüpft" über einer
    # Verknüpfung, die es selbst angelegt hatte.
    return bool(path.lstat().st_file_attributes & 0x400)


def link(target: Path, source: Path) -> None:
    """Legt die Verknüpfung an — Junction auf Windows, Symlink sonst."""
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(source)],
            check=True,
            capture_output=True,
        )
    else:
        target.symlink_to(source, target_is_directory=True)


def _kept(entry: Path, im_repo: Path) -> bool:
    """Liegt die lokale Datei unverändert an ihrem tatsächlich gewählten Ort?"""
    return im_repo.is_file() and im_repo.read_bytes() == entry.read_bytes()


def _keep_local(entry: Path, destination: Path) -> Path:
    """Sichert die Fassung in einer freien Datei, ohne ältere Sicherungen zu ersetzen."""
    contents = entry.read_bytes()
    candidate = destination
    number = 1
    while True:
        if candidate.exists():
            if candidate.is_file() and candidate.read_bytes() == contents:
                return candidate
            suffix = "" if number == 1 else f"-{number}"
            candidate = destination.with_name(
                f"{destination.stem}.dieser-maschine{suffix}{destination.suffix}"
            )
            number += 1
            continue
        candidate.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Die Namenswahl und ihre Reservierung müssen zusammenfallen,
            # sonst könnte eine zweite Sitzung denselben freien Namen nehmen.
            with candidate.open("xb"):
                pass
        except FileExistsError:
            continue
        shutil.copy2(entry, candidate)
        return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pruefen", action="store_true", help="nur berichten, nichts ändern")
    parser.add_argument(
        "--wiederherstellen",
        action="store_true",
        help="fehlende Erinnerungen aus dem letzten versionierten Stand zurückholen",
    )
    args = parser.parse_args(argv)

    if args.wiederherstellen:
        restored = restore_from_history(ROOT)
        if restored:
            print(f"Erinnerungen aus der Git-Historie zurückgeholt: {len(restored)} Dateien.")
        else:
            print("Nichts zurückzuholen: Jede versionierte Erinnerung liegt schon hier.")
        return 0

    project = ROOT
    target = harness_dir(project)
    print(f"Erinnerungen im Arbeitsbaum: {IN_REPO}")
    print(f"Ort der Sitzung:             {target}")

    if linked(target):
        print("Steht schon: der Ort ist eine Verknüpfung, nichts zu tun.")
        return 0
    if args.pruefen:
        print("Noch nicht verknüpft — `python tools/link_memory.py` richtet es ein.")
        return 1

    if not target.exists():
        # Nicht anlegen, sondern anhalten: Ein Ort, den es nicht gibt, heißt
        # entweder „hier lief noch nie eine Sitzung" oder „das Kürzel stimmt
        # nicht". Im zweiten Fall stünde die Verknüpfung neben den Erinnerungen
        # statt über ihnen, und niemand merkte es.
        print("Diesen Ort gibt es nicht — das Kürzel passt vermutlich nicht.")
        known = sorted(q.name for q in target.parent.parent.iterdir() if q.is_dir())
        if known:
            print("Unter ~/.claude/projects liegen: " + ", ".join(known))
        print("Den richtigen Ordner ablesen und harness_dir danach richten.")
        return 1

    IN_REPO.mkdir(parents=True, exist_ok=True)
    if target.is_dir():
        # Was diese Maschine allein gelernt hat, kommt zuerst ins Repository —
        # **alles**, und zwar bevor hier irgendetwas gelöscht wird. Bis zum
        # 05.09.2026 wurden nur die Markdown-Dateien der obersten Ebene
        # übernommen, und davon nur die, deren Name im Repository fehlte; eine
        # abweichende Fassung bekam allein ``MEMORY.md`` beiseite gelegt.
        # Danach fiel das ganze Verzeichnis: Eine lokal ergänzte ``topic.md``
        # verschwand ersatzlos, sobald im Repository eine andere ``topic.md``
        # lag, Unterordner und Nicht-Markdown-Dateien gleich mit
        # (Gesamtreview, R19). Jetzt gilt: gleich → nichts zu tun, neu →
        # übernommen, abweichend → daneben gelegt; und gelöscht wird erst,
        # wenn jede Datei nachweislich einen Ort hat.
        adopted: list[str] = []
        aside_names: list[str] = []
        kept: dict[Path, Path] = {}
        for entry in sorted(target.rglob("*")):
            if not entry.is_file():
                continue
            relative = entry.relative_to(target)
            im_repo = IN_REPO / relative
            existed = im_repo.exists()
            saved = _keep_local(entry, im_repo)
            kept[entry] = saved
            if saved != im_repo:
                aside_names.append(saved.relative_to(IN_REPO).as_posix())
            elif not existed:
                adopted.append(relative.as_posix())
        if adopted:
            print("Aus dem Nutzerprofil übernommen: " + ", ".join(adopted))
        if aside_names:
            # Zusammenführen ist Handarbeit — eine abweichende Fassung liegt
            # daneben statt überschrieben zu werden.
            print(
                "Abweichend, die Fassung dieser Maschine liegt daneben: " + ", ".join(aside_names)
            )
            print("Zeilen von Hand übernehmen und die Datei danach löschen.")
        unsaved = [
            entry.relative_to(target).as_posix()
            for entry in sorted(target.rglob("*"))
            if entry.is_file() and (entry not in kept or not _kept(entry, kept[entry]))
        ]
        if unsaved:
            print("Nicht gesichert, deshalb bleibt das Nutzerprofil stehen: " + ", ".join(unsaved))
            return 2
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    link(target, IN_REPO)
    print("Eingerichtet. Ab jetzt liest und schreibt jede Sitzung dieses Projekts")
    print("dieselben Dateien; sie bleiben auf dieser Maschine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
