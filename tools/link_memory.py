"""Die Erinnerungen dieser Sitzung ins Repository hängen (einmal je Maschine).

Claude Code legt seine Erinnerungen unter dem Nutzerprofil ab:
``~/.claude/projects/<Pfadkürzel>/memory``. Das ist ein Ort je Maschine — und
an Solidon wird auf drei gearbeitet. Was auf der einen gelernt wurde, kannte
die andere nicht: die Git-Identität, der geteilte Index, die Pipeline, die den
Exit-Code frisst. Jede Maschine hat dieselben Fallen einzeln gefunden.

Dieses Werkzeug macht aus dem Ort eine **Verknüpfung** auf ``.claude/memory``
im Arbeitsbaum. Damit trägt Git die Erinnerungen, und jede Maschine liest und
schreibt dieselben Dateien — ohne Kopierschritt, ohne zweite Wahrheit.

Was schon im Nutzerprofil liegt, wird vorher ins Repository übernommen; nichts
geht verloren. Läuft das Werkzeug zweimal, sagt es das und tut nichts.

    python tools/link_memory.py            # einrichten
    python tools/link_memory.py --pruefen  # nur sagen, wie es steht

Auf Windows entsteht eine Verzeichnisverknüpfung (Junction) — die braucht keine
erhöhten Rechte, anders als eine symbolische Verknüpfung. Auf Linux und macOS
ein Symlink.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

#: Wo die Erinnerungen im Arbeitsbaum liegen.
IN_REPO = Path(__file__).resolve().parent.parent / ".claude" / "memory"


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pruefen", action="store_true", help="nur berichten, nichts ändern")
    args = parser.parse_args(argv)

    project = Path(__file__).resolve().parent.parent
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
        # Was diese Maschine allein gelernt hat, kommt zuerst ins Repository.
        adopted = []
        for entry in sorted(target.glob("*.md")):
            im_repo = IN_REPO / entry.name
            if not im_repo.exists():
                shutil.copy2(entry, im_repo)
                adopted.append(entry.name)
        if adopted:
            print("Aus dem Nutzerprofil übernommen: " + ", ".join(adopted))
        # MEMORY.md ist das Verzeichnis und kann auf beiden Seiten Zeilen haben,
        # die die andere nicht kennt. Zusammenführen ist Handarbeit, also wird
        # eine abweichende Fassung daneben gelegt statt überschrieben.
        local = target / "MEMORY.md"
        shared = IN_REPO / "MEMORY.md"
        if local.is_file() and shared.is_file() and local.read_bytes() != shared.read_bytes():
            aside = IN_REPO / "MEMORY.dieser-maschine.md"
            shutil.copy2(local, aside)
            print(f"MEMORY.md wich ab — die Fassung dieser Maschine liegt als {aside.name}.")
            print("Zeilen von Hand übernehmen und die Datei danach löschen.")
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    link(target, IN_REPO)
    print("Eingerichtet. Ab jetzt liest und schreibt jede Sitzung dieses Projekts")
    print("dieselben Dateien, und Git trägt sie auf die anderen Maschinen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
