"""Prüft einen Linux-Bau auf das älteste System, auf dem er starten muss.

    python tools/check_glibc_floor.py dist/Solidon3D
    python tools/check_glibc_floor.py squashfs-root --oldest 2.35

**Warum.** Jede ELF-Datei verlangt die glibc-Fassungen, gegen die sie gebaut
wurde (``GLIBC_2.38`` in ``.gnu.version_r``). Das Paket 0.6.0 entstand auf
Ubuntu 24.04 und verlangte damit glibc 2.38: ``libpython3.14.so.1.0`` brauchte
``fmod@GLIBC_2.38``, und auf Ubuntu 22.04, Debian 12 und Mint 21 scheiterte
schon das Laden von Python. Seitdem entsteht der Linux-Bau auf dem ältesten
unterstützten System, und dieses Werkzeug hält die Grenze an jeder Datei.

**Und zwei Bibliotheken reisen nicht mit:** ``libstdc++.so.6`` und
``libgcc_s.so.1``. Der Bauserver ist das älteste System; jedes Zielsystem hat
dieselbe oder eine neuere Fassung. Eine mitgereiste ältere lädt der Starter
vor der des Rechners (``LD_LIBRARY_PATH``), und der Grafiktreiber des
Rechners (Mesa, LLVM), der eine neuere ``GLIBCXX``-Fassung verlangt, lädt
dann nicht — keine 3D-Ansicht oder ein Absturz. Weil beide vom Rechner
kommen, darf keine Datei mehr ``GLIBCXX_``/``CXXABI_``/``GCC_`` verlangen
als das älteste System trägt (``OLDEST_RUNTIME``).

Gelesen wird wie der dynamische Lader: über die Programmköpfe, ``PT_DYNAMIC``
und die Adressen der Ladesegmente — auch eine Datei ohne Abschnittstabelle
verrät so ihre Anforderungen. Nur Standardbibliothek; ``pyelftools`` steht
nicht in den Abhängigkeiten.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

#: Die älteste glibc, auf der AppImage und Archiv starten müssen: Ubuntu 22.04
#: LTS (2.35), dazu Debian 12 (2.36) und Linux Mint 21. Der Bauserver ist
#: genau dieses System (``build.yml``, Paketjob).
OLDEST_GLIBC: Final = (2, 35)

#: Was der Rechner selbst mitbringt und nie im Bau liegen darf — Gründe oben.
#: Gilt für den Soname und jede Datei, die ihn trägt (``libstdc++.so.6.0.30``).
HOST_LIBRARIES: Final = ("libstdc++.so.6", "libgcc_s.so.1")

#: Weil ``HOST_LIBRARIES`` vom Rechner kommen, darf keine Datei des Baums mehr
#: von ihnen verlangen als das älteste System bietet: Ubuntu 22.04 trägt
#: libstdc++ und libgcc_s aus GCC 12 (``libstdc++6``/``libgcc-s1``
#: 12.3.0-1ubuntu1~22.04.3, an den Paketen gemessen).
OLDEST_RUNTIME: Final = {
    "GLIBCXX": (3, 4, 30),
    "CXXABI": (1, 3, 13),
    "GCC": (12, 0, 0),
}

_ELF_MAGIC: Final = b"\x7fELF"
_PT_LOAD: Final = 1
_PT_DYNAMIC: Final = 2
_DT_NULL: Final = 0
_DT_NEEDED: Final = 1
_DT_STRTAB: Final = 5
_DT_SONAME: Final = 14
_DT_VERNEED: Final = 0x6FFFFFFE
_DT_VERNEEDNUM: Final = 0x6FFFFFFF
_VERSION: Final = re.compile(r"([A-Z]+)_(\d+(?:\.\d+)*)$")


@dataclass
class ElfNeeds:
    """Was eine ELF-Datei vom Lader verlangt."""

    needed: list[str] = field(default_factory=list)
    #: ``(bibliothek, fassung)``, etwa ``("libm.so.6", "GLIBC_2.38")``.
    versions: list[tuple[str, str]] = field(default_factory=list)

    def highest(self, family: str) -> tuple[tuple[int, ...], str] | None:
        """Die höchste verlangte Fassung einer Familie (``GLIBC``, ``GLIBCXX`` …).

        ``GLIBC_PRIVATE`` und andere Namen ohne Nummer zählen nicht.
        """
        found = []
        for library, version in self.versions:
            match = _VERSION.match(version)
            if match and match.group(1) == family:
                number = tuple(int(part) for part in match.group(2).split("."))
                found.append((number, f"{version} ({library})"))
        return max(found) if found else None

    def highest_glibc(self) -> tuple[tuple[int, ...], str] | None:
        """Die höchste verlangte ``GLIBC_``-Fassung samt Bibliothek, oder ``None``."""
        return self.highest("GLIBC")


def read_elf(path: Path) -> ElfNeeds | None:
    """Liest Bibliotheken und Fassungen einer ELF-Datei; ``None``, wenn es keine ist.

    Eine statisch gebundene Datei (ohne ``PT_DYNAMIC``, wie der Laufzeitkern
    des AppImage) verlangt nichts. Andere Formate als 64 Bit Little Endian
    (x86_64) baut Solidon nicht; sie halten mit einer Meldung an.
    """
    with path.open("rb") as handle:
        if handle.read(4) != _ELF_MAGIC:
            return None
        data = handle.read()
    data = _ELF_MAGIC + data
    if data[4] != 2 or data[5] != 1:
        raise ValueError(f"{path}: nur ELF64 Little Endian wird gelesen")
    (phoff,) = struct.unpack_from("<Q", data, 0x20)
    phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
    loads: list[tuple[int, int, int]] = []
    dynamic: tuple[int, int] | None = None
    for index in range(phnum):
        kind, _flags, offset, vaddr, _paddr, filesz = struct.unpack_from(
            "<IIQQQQ", data, phoff + index * phentsize
        )
        if kind == _PT_LOAD:
            loads.append((vaddr, offset, filesz))
        elif kind == _PT_DYNAMIC:
            dynamic = (offset, filesz)
    if dynamic is None:
        return ElfNeeds()

    def at(address: int) -> int:
        for vaddr, offset, filesz in loads:
            if vaddr <= address < vaddr + filesz:
                return address - vaddr + offset
        raise ValueError(f"{path}: Adresse {address:#x} liegt in keinem Ladesegment")

    entries: dict[int, list[int]] = {}
    start, size = dynamic
    for position in range(start, start + size, 16):
        tag, value = struct.unpack_from("<qQ", data, position)
        if tag == _DT_NULL:
            break
        entries.setdefault(tag, []).append(value)
    if _DT_STRTAB not in entries:
        return ElfNeeds()
    strings = at(entries[_DT_STRTAB][0])

    def text(offset: int) -> str:
        end = data.index(b"\0", strings + offset)
        return data[strings + offset : end].decode("utf-8", "replace")

    needs = ElfNeeds(needed=[text(value) for value in entries.get(_DT_NEEDED, [])])
    if _DT_VERNEED in entries:
        position = at(entries[_DT_VERNEED][0])
        for _ in range(entries.get(_DT_VERNEEDNUM, [0])[0]):
            _version, count, file_name, aux, following = struct.unpack_from(
                "<HHIII", data, position
            )
            library = text(file_name)
            entry = position + aux
            for _ in range(count):
                _hash, _flags, _other, name, after = struct.unpack_from("<IHHII", data, entry)
                needs.versions.append((library, text(name)))
                entry += after
            if not following:
                break
            position += following
    return needs


def is_host_library(name: str) -> bool:
    """Trägt die Datei den Namen einer Bibliothek, die der Rechner mitbringt?"""
    return any(name == soname or name.startswith(soname + ".") for soname in HOST_LIBRARIES)


def check_tree(root: Path, oldest: tuple[int, ...] = OLDEST_GLIBC) -> tuple[list[str], int]:
    """Alle Befunde eines Baums und die Zahl gelesener ELF-Dateien.

    Symlinks zählen nicht — ihr Ziel liegt ohnehin im Baum, und ein Link nach
    außen wäre ein eigener Fehler, den die Paketierer schon abweisen.
    """
    problems: list[str] = []
    count = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if is_host_library(path.name):
            problems.append(f"{relative}: bringt der Rechner mit und darf nicht mitreisen")
        needs = read_elf(path)
        if needs is None:
            continue
        count += 1
        limits = {"GLIBC": oldest, **OLDEST_RUNTIME}
        for family, limit in limits.items():
            highest = needs.highest(family)
            if highest is not None and highest[0] > limit:
                problems.append(f"{relative}: verlangt {highest[1]}")
    return problems, count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, help="der gebaute Baum (dist/Solidon3D, squashfs-root)")
    parser.add_argument(
        "--oldest",
        default=".".join(str(part) for part in OLDEST_GLIBC),
        help="älteste glibc, auf der der Bau starten muss (Vorgabe: %(default)s)",
    )
    arguments = parser.parse_args(argv)
    oldest = tuple(int(part) for part in arguments.oldest.split("."))
    if not arguments.root.is_dir():
        print(f"{arguments.root} ist kein Verzeichnis — erst bauen.")
        return 2
    problems, count = check_tree(arguments.root, oldest)
    for problem in problems:
        print(f"Linux-Grenze verletzt: {problem}")
    if count == 0:
        print(f"In {arguments.root} liegt keine ELF-Datei — falscher Ordner?")
        return 1
    if problems:
        print(
            f"{len(problems)} Befunde in {count} ELF-Dateien: Der Bau startete nicht auf "
            f"glibc {arguments.oldest} oder bräche den Grafiktreiber des Rechners. Auf dem "
            "ältesten unterstützten System bauen und die Bibliotheken des Rechners auslassen "
            "(make_linux_packages.trim_linux_binaries)."
        )
        return 1
    print(f"{count} ELF-Dateien, keine verlangt mehr als glibc {arguments.oldest}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
