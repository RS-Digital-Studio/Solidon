"""Die Linux-Grenze: höchstens glibc 2.35, keine ``libstdc++``/``libgcc_s`` im Bau.

Die ELF-Dateien hier entstehen im Test: ein Kopf, ein Ladesegment, ein
``PT_DYNAMIC`` mit ``DT_NEEDED``, ``DT_STRTAB`` und ``DT_VERNEED`` — genau das,
was der dynamische Lader liest und ``tools/check_glibc_floor.py`` auswertet.
Gegen den echten Baum des Pakets 0.6.0 (Ubuntu 24.04) meldete das Werkzeug
30 Befunde in 486 ELF-Dateien, darunter ``libpython3.14.so.1.0`` mit
``GLIBC_2.38 (libm.so.6)`` — dieselbe Zahl wie die Forensik vom 12.10.2026.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from tools import check_glibc_floor as tool

_BASE = 0x400000


def _elf(
    needed: list[str],
    versions: dict[str, list[str]],
    *,
    dynamic: bool = True,
) -> bytes:
    """Eine kleine ELF64-Datei mit den angegebenen Bibliotheken und Fassungen."""
    strings = b"\0"
    offsets: dict[str, int] = {}
    for name in [*needed, *versions, *(v for vs in versions.values() for v in vs)]:
        if name not in offsets:
            offsets[name] = len(strings)
            strings += name.encode() + b"\0"

    verneed = b""
    libraries = list(versions.items())
    for index, (library, names) in enumerate(libraries):
        aux = b""
        for position, name in enumerate(names):
            following = 16 if position < len(names) - 1 else 0
            aux += struct.pack("<IHHII", 0, 0, position + 2, offsets[name], following)
        following = 16 + len(aux) if index < len(libraries) - 1 else 0
        verneed += struct.pack("<HHIII", 1, len(names), offsets[library], 16, following) + aux

    header_size, phentsize = 64, 56
    phnum = 2 if dynamic else 1
    strtab_at = header_size + phnum * phentsize
    verneed_at = strtab_at + len(strings)
    dynamic_at = verneed_at + len(verneed)
    entries = [(1, offsets[name]) for name in needed]
    entries += [(5, _BASE + strtab_at), (10, len(strings))]
    if versions:
        entries += [(0x6FFFFFFE, _BASE + verneed_at), (0x6FFFFFFF, len(libraries))]
    entries.append((0, 0))
    table = b"".join(struct.pack("<qQ", tag, value) for tag, value in entries)
    total = dynamic_at + len(table)

    ident = b"\x7fELF" + bytes([2, 1, 1]) + bytes(9)
    head = ident + struct.pack(
        "<HHIQQQIHHHHHH", 3, 62, 1, 0, header_size, 0, 0, header_size, phentsize, phnum, 0, 0, 0
    )
    load = struct.pack("<IIQQQQQQ", 1, 5, 0, _BASE, _BASE, total, total, 0x1000)
    program = load
    if dynamic:
        program += struct.pack(
            "<IIQQQQQQ", 2, 6, dynamic_at, _BASE + dynamic_at, 0, len(table), len(table), 8
        )
    return head + program + strings + verneed + table


def test_the_reader_finds_libraries_and_the_highest_glibc(tmp_path: Path) -> None:
    library = tmp_path / "libpython3.14.so.1.0"
    library.write_bytes(
        _elf(
            ["libm.so.6", "libc.so.6"],
            {"libm.so.6": ["GLIBC_2.2.5", "GLIBC_2.38"], "libc.so.6": ["GLIBC_2.34"]},
        )
    )

    needs = tool.read_elf(library)

    assert needs is not None
    assert needs.needed == ["libm.so.6", "libc.so.6"]
    assert ("libm.so.6", "GLIBC_2.38") in needs.versions
    assert needs.highest_glibc() == ((2, 38), "GLIBC_2.38 (libm.so.6)")


def test_other_version_names_and_static_files_ask_for_no_glibc(tmp_path: Path) -> None:
    """``GLIBCXX_``, ``GLIBC_PRIVATE`` und statisch gebundene Dateien zählen nicht."""
    cxx = tmp_path / "libQt6Core.so.6"
    cxx.write_bytes(
        _elf(
            ["libstdc++.so.6"],
            {"libstdc++.so.6": ["GLIBCXX_3.4.30"], "libc.so.6": ["GLIBC_PRIVATE"]},
        )
    )
    static = tmp_path / "runtime"
    static.write_bytes(_elf([], {}, dynamic=False))
    text = tmp_path / "notes.txt"
    text.write_text("keine ELF-Datei", encoding="utf-8")

    cxx_needs = tool.read_elf(cxx)
    assert cxx_needs is not None and cxx_needs.highest_glibc() is None
    static_needs = tool.read_elf(static)
    assert static_needs is not None and static_needs.highest_glibc() is None
    assert tool.read_elf(text) is None


def test_the_tree_check_holds_the_oldest_glibc_and_the_host_libraries(tmp_path: Path) -> None:
    root = tmp_path / "Solidon3D"
    (root / "_internal").mkdir(parents=True)
    fine = root / "_internal" / "libfine.so"
    fine.write_bytes(_elf(["libc.so.6"], {"libc.so.6": ["GLIBC_2.34", "GLIBC_2.35"]}))

    assert tool.check_tree(root) == ([], 1)

    (root / "_internal" / "libpython3.14.so.1.0").write_bytes(
        _elf(["libm.so.6"], {"libm.so.6": ["GLIBC_2.38"]})
    )
    (root / "_internal" / "libstdc++.so.6").write_bytes(
        _elf(["libc.so.6"], {"libc.so.6": ["GLIBC_2.34"]})
    )
    (root / "_internal" / "libgcc_s.so.1").write_bytes(b"\x7fELF" + bytes([2, 1]) + bytes(58))

    problems, _count = tool.check_tree(root)
    joined = "\n".join(problems)
    assert "libpython3.14.so.1.0: verlangt GLIBC_2.38 (libm.so.6)" in joined
    assert "libstdc++.so.6: bringt der Rechner mit" in joined
    assert "libgcc_s.so.1: bringt der Rechner mit" in joined
    assert "libfine.so" not in joined

    assert tool.check_tree(root, (2, 38))[0] == [p for p in problems if "Rechner" in p]


def test_the_tree_check_holds_the_cxx_runtime_of_the_oldest_system(tmp_path: Path) -> None:
    """libstdc++ und libgcc_s kommen vom Rechner — also höchstens das, was 22.04 trägt.

    Ubuntu 22.04: ``GLIBCXX_3.4.30``, ``CXXABI_1.3.13``, ``GCC_12.0.0`` (GCC 12,
    an den Paketen ``libstdc++6`` und ``libgcc-s1`` gemessen). Der Baum von
    0.6.0 verlangte höchstens 3.4.29 (libpyside6) und 1.3.13 (QtCore).
    """
    root = tmp_path / "tree"
    root.mkdir()
    (root / "libQt6Core.so.6").write_bytes(
        _elf(
            ["libstdc++.so.6", "libgcc_s.so.1"],
            {
                "libstdc++.so.6": ["GLIBCXX_3.4.30", "CXXABI_1.3.13"],
                "libgcc_s.so.1": ["GCC_12.0.0"],
            },
        )
    )
    assert tool.check_tree(root) == ([], 1)

    for name, library, version in (
        ("libnewcxx.so", "libstdc++.so.6", "GLIBCXX_3.4.31"),
        ("libnewabi.so", "libstdc++.so.6", "CXXABI_1.3.14"),
        ("libnewgcc.so", "libgcc_s.so.1", "GCC_13.0.0"),
    ):
        (root / name).write_bytes(_elf([library], {library: [version]}))
    problems, count = tool.check_tree(root)
    assert count == 4
    assert sorted(problems) == [
        "libnewabi.so: verlangt CXXABI_1.3.14 (libstdc++.so.6)",
        "libnewcxx.so: verlangt GLIBCXX_3.4.31 (libstdc++.so.6)",
        "libnewgcc.so: verlangt GCC_13.0.0 (libgcc_s.so.1)",
    ]
    assert tool.OLDEST_RUNTIME == {"GLIBCXX": (3, 4, 30), "CXXABI": (1, 3, 13), "GCC": (12, 0, 0)}


def test_host_libraries_are_matched_by_soname_and_by_their_full_file_name() -> None:
    assert tool.is_host_library("libstdc++.so.6")
    assert tool.is_host_library("libstdc++.so.6.0.30")
    assert tool.is_host_library("libgcc_s.so.1")
    assert not tool.is_host_library("libstdc++-hash.so.6")
    assert not tool.is_host_library("libgcc_s_seh-1.dll")


def test_the_command_fails_on_a_finding_and_on_an_empty_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    assert tool.main([str(root)]) == 1, "ohne ELF-Datei prüfte das Werkzeug ins Leere"

    (root / "libok.so").write_bytes(_elf(["libc.so.6"], {"libc.so.6": ["GLIBC_2.35"]}))
    assert tool.main([str(root)]) == 0
    (root / "libnew.so").write_bytes(_elf(["libc.so.6"], {"libc.so.6": ["GLIBC_2.36"]}))
    assert tool.main([str(root)]) == 1
    assert tool.main([str(root), "--oldest", "2.36"]) == 0
    assert "libnew.so: verlangt GLIBC_2.36" in capsys.readouterr().out
    assert tool.main([str(tmp_path / "missing")]) == 2


def test_the_oldest_glibc_is_the_one_of_the_linux_build_server() -> None:
    """Die Grenze und der Bauserver gehören zusammen: Ubuntu 22.04 trägt glibc 2.35."""
    assert tool.OLDEST_GLIBC == (2, 35)
