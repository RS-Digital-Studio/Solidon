"""Prüft alle ELF-Dateien eines entpackten Linux-Pakets: NEEDED, SONAME,
RPATH/RUNPATH, benötigte Symbolversionen (GLIBC_, GLIBCXX_, CXXABI_, GCC_),
GNU_PROPERTY_X86_ISA_1_NEEDED, fehlende Bibliotheken.

Aufruf: python -I elf_pruefen.py <wurzel> <ausgabe.json>
Liest nur, führt nichts aus.
"""

from __future__ import annotations

import collections
import json
import os
import re
import struct
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile
from elftools.elf.dynamic import DynamicSection
from elftools.elf.gnuversions import GNUVerNeedSection

ISA_NEEDED = 0xC0008002
ISA_USED = 0xC0010002
FEATURE_1_AND = 0xC0000002
ISA_BITS = {1: "baseline", 2: "x86-64-v2", 4: "x86-64-v3", 8: "x86-64-v4"}


def vkey(v: str):
    m = re.match(r"([A-Z_]+?)_?(\d+(?:\.\d+)*)$", v)
    if not m:
        return (v, ())
    return (m.group(1), tuple(int(x) for x in m.group(2).split(".")))


def gnu_properties(elf: ELFFile):
    out = {}
    for sec in elf.iter_sections():
        if sec.name != ".note.gnu.property":
            continue
        data = sec.data()
        i = 0
        while i + 12 <= len(data):
            namesz, descsz, ntype = struct.unpack("<III", data[i : i + 12])
            name = data[i + 12 : i + 12 + namesz]
            desc_off = i + 12 + ((namesz + 3) & ~3)
            desc = data[desc_off : desc_off + descsz]
            if ntype == 5 and name.startswith(b"GNU"):
                j = 0
                while j + 8 <= len(desc):
                    pr_type, pr_datasz = struct.unpack("<II", desc[j : j + 8])
                    val = desc[j + 8 : j + 8 + pr_datasz]
                    if pr_datasz == 4:
                        (v,) = struct.unpack("<I", val)
                        if pr_type == ISA_NEEDED:
                            out["isa_needed"] = [n for b, n in ISA_BITS.items() if v & b]
                        elif pr_type == ISA_USED:
                            out["isa_used"] = [n for b, n in ISA_BITS.items() if v & b]
                        elif pr_type == FEATURE_1_AND:
                            out["feature_1_and"] = hex(v)
                    j += 8 + ((pr_datasz + 7) & ~7)
            i = desc_off + ((descsz + 3) & ~3)
    return out


def main() -> None:
    root = Path(sys.argv[1])
    results = []
    provided = set()
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            p = Path(dirpath) / fn
            provided.add(fn)
            if p.is_symlink():
                continue
            try:
                with open(p, "rb") as fh:
                    if fh.read(4) != b"\x7fELF":
                        continue
            except OSError:
                continue
            rec = {"path": str(p.relative_to(root)).replace("\\", "/"), "size": p.stat().st_size}
            try:
                with open(p, "rb") as fh:
                    elf = ELFFile(fh)
                    rec["machine"] = elf["e_machine"]
                    rec["type"] = elf["e_type"]
                    needed, soname, rpath, runpath = [], None, None, None
                    interp = None
                    for seg in elf.iter_segments():
                        if seg["p_type"] == "PT_INTERP":
                            interp = seg.get_interp_name()
                    for sec in elf.iter_sections():
                        if isinstance(sec, DynamicSection):
                            for tag in sec.iter_tags():
                                if tag.entry.d_tag == "DT_NEEDED":
                                    needed.append(tag.needed)
                                elif tag.entry.d_tag == "DT_SONAME":
                                    soname = tag.soname
                                elif tag.entry.d_tag == "DT_RPATH":
                                    rpath = tag.rpath
                                elif tag.entry.d_tag == "DT_RUNPATH":
                                    runpath = tag.runpath
                    vers = collections.defaultdict(set)
                    for sec in elf.iter_sections():
                        if isinstance(sec, GNUVerNeedSection):
                            for verneed, auxs in sec.iter_versions():
                                for aux in auxs:
                                    vers[verneed.name].add(aux.name)
                    rec.update(
                        needed=needed,
                        soname=soname,
                        rpath=rpath,
                        runpath=runpath,
                        interp=interp,
                        verneed={k: sorted(v) for k, v in vers.items()},
                        props=gnu_properties(elf),
                    )
                    if soname:
                        provided.add(soname)
            except Exception as exc:  # noqa: BLE001
                rec["error"] = str(exc)
            results.append(rec)
    Path(sys.argv[2]).write_text(json.dumps({"provided": sorted(provided), "elf": results}, indent=1), encoding="utf-8")
    print("ELF:", len(results))


if __name__ == "__main__":
    main()
