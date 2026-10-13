"""Befehlssatz-Analyse der x86_64-Mach-O eines App-Zips mit capstone.

Je Datei: alle ausführbaren Abschnitte linear disassemblieren, Befehle nach
Erweiterung zählen (AVX-512/EVEX, AVX2, FMA, BMI1/2, F16C, AVX, SHA, GFNI,
VAES/VPCLMULQDQ-256, RTM, …) und Funktionen zuordnen (LC_FUNCTION_STARTS,
Namen aus der Symboltabelle). CPUID/XGETBV werden mitgezählt.

Aufruf: python -I isa_scan.py <app.zip> <ausgabe.json> [prozesse]
Liest nur, führt nichts aus.
"""

from __future__ import annotations

import bisect
import collections
import json
import re
import struct
import sys
import zipfile
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capstone  # noqa: E402
from capstone import x86_const as X  # noqa: E402

import macho  # noqa: E402

LC_SYMTAB = 0x2
LC_FUNCTION_STARTS = 0x26

PREFIXES = {0x26, 0x2E, 0x36, 0x3E, 0x64, 0x65, 0x66, 0x67, 0xF0, 0xF2, 0xF3}

GROUP_NAMES = {
    X.X86_GRP_AVX512: "avx512",
    X.X86_GRP_AVX2: "avx2",
    X.X86_GRP_FMA: "fma",
    X.X86_GRP_FMA4: "fma4",
    X.X86_GRP_BMI: "bmi1",
    X.X86_GRP_BMI2: "bmi2",
    X.X86_GRP_F16C: "f16c",
    X.X86_GRP_AVX: "avx",
    X.X86_GRP_SHA: "sha",
    X.X86_GRP_RTM: "rtm",
    X.X86_GRP_XOP: "xop",
    X.X86_GRP_TBM: "tbm",
    X.X86_GRP_ADX: "adx",
    X.X86_GRP_AES: "aes",
    X.X86_GRP_PCLMUL: "pclmul",
    X.X86_GRP_SSE4A: "sse4a",
}

# Erweiterungen, die ein Coffee-Lake-Kern (i7/i9-9xxxH) nicht hat.
NOT_COFFEE_LAKE = {"avx512", "evex", "sha", "fma4", "xop", "tbm", "sse4a", "gfni", "vaes256", "vpclmul256",
                   "avxvnni", "rdpid", "clwb", "movdir", "serialize", "waitpkg", "amx", "rex2", "avxifma",
                   "pconfig", "wbnoinvd", "enqcmd", "cldemote", "ptwrite"}

EXTRA_MNEMONICS = {
    "rdpid": "rdpid",
    "clwb": "clwb",
    "movdiri": "movdir",
    "movdir64b": "movdir",
    "serialize": "serialize",
    "tpause": "waitpkg",
    "umwait": "waitpkg",
    "umonitor": "waitpkg",
    "pconfig": "pconfig",
    "wbnoinvd": "wbnoinvd",
    "enqcmd": "enqcmd",
    "enqcmds": "enqcmd",
    "cldemote": "cldemote",
    "ptwrite": "ptwrite",
    "xbegin": "rtm",
    "xend": "rtm",
    "xabort": "rtm",
    "xtest": "rtm",
    "cpuid": "cpuid",
    "xgetbv": "xgetbv",
    "sha1rnds4": "sha",
    "sha1nexte": "sha",
    "sha1msg1": "sha",
    "sha1msg2": "sha",
    "sha256rnds2": "sha",
    "sha256msg1": "sha",
    "sha256msg2": "sha",
    "gf2p8affineqb": "gfni",
    "gf2p8affineinvqb": "gfni",
    "gf2p8mulb": "gfni",
    "vgf2p8affineqb": "gfni",
    "vgf2p8affineinvqb": "gfni",
    "vgf2p8mulb": "gfni",
    "vpdpbusd": "avxvnni",
    "vpdpbusds": "avxvnni",
    "vpdpwssd": "avxvnni",
    "vpdpwssds": "avxvnni",
    "vpmadd52luq": "avxifma",
    "vpmadd52huq": "avxifma",
    "ldtilecfg": "amx",
    "tileloadd": "amx",
    "tdpbssd": "amx",
}

REG_NORM = [
    (re.compile(r"\bzmm\d+\b"), "zmm"),
    (re.compile(r"\bymm\d+\b"), "ymm"),
    (re.compile(r"\bxmm\d+\b"), "xmm"),
    (re.compile(r"\bk\d\b"), "k"),
    (re.compile(r"\b(?:byte|word|dword|qword|xmmword|ymmword|zmmword|tbyte)? ?ptr \[[^\]]*\]"), "m"),
    (re.compile(r"\[[^\]]*\]"), "m"),
    (re.compile(r"\b(?:r[a-z0-9]+|e[a-z]{2}|[a-d][lhx]|[sd]il?|[sb]pl?)\b"), "r"),
    (re.compile(r"\b0x[0-9a-f]+\b|\b\d+\b"), "i"),
]


def norm(op: str) -> str:
    for rx, rep in REG_NORM:
        op = rx.sub(rep, op)
    return op


def symbols_and_starts(data: bytes, sl: macho.Slice):
    base = sl.offset
    _, _, _, ncmds, _, _, _ = struct.unpack("<iIIIIII", data[base + 4 : base + 32])
    pos = base + 32
    text_vmaddr = None
    for seg in sl.segments:
        if seg[0] == "__TEXT":
            text_vmaddr = seg[1]
    starts, syms = [], {}
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack("<II", data[pos : pos + 8])
        if cmd == LC_FUNCTION_STARTS and text_vmaddr is not None:
            off, size = struct.unpack("<II", data[pos + 8 : pos + 16])
            blob = data[base + off : base + off + size]
            addr = text_vmaddr
            i = 0
            while i < len(blob):
                val = 0
                shift = 0
                while True:
                    b = blob[i]
                    i += 1
                    val |= (b & 0x7F) << shift
                    shift += 7
                    if not b & 0x80:
                        break
                if val == 0:
                    break
                addr += val
                starts.append(addr)
        elif cmd == LC_SYMTAB:
            symoff, nsyms, stroff, strsize = struct.unpack("<IIII", data[pos + 8 : pos + 24])
            strtab = data[base + stroff : base + stroff + strsize]
            for k in range(nsyms):
                e = data[base + symoff + 16 * k : base + symoff + 16 * (k + 1)]
                strx, ntype, nsect, _desc, value = struct.unpack("<IBBHQ", e)
                if ntype & 0xE0:
                    continue  # stab
                if (ntype & 0x0E) != 0x0E:
                    continue  # nicht N_SECT
                end = strtab.find(b"\0", strx)
                syms[value] = strtab[strx:end].decode("utf-8", "replace")
        pos += cmdsize
    if not starts:
        starts = sorted(syms)
    return sorted(set(starts)), syms


def scan_file(args):
    zpath, name = args
    zf = zipfile.ZipFile(zpath)
    data = zf.read(name)
    try:
        slices = macho.parse_macho(data)
    except Exception as exc:  # noqa: BLE001
        return {"path": name, "error": str(exc)}
    out = {"path": name, "size": len(data), "slices": []}
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.skipdata = True
    mdd = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    mdd.detail = True
    cache: dict[tuple, frozenset] = {}
    for sl in slices:
        if not sl.arch.startswith("x86_64"):
            continue
        starts, syms = symbols_and_starts(data, sl)
        counts = collections.Counter()
        funcs = collections.defaultdict(set)  # klasse -> Funktionsindizes
        func_any_simd = set()
        total = 0
        text_bytes = 0
        skipped = 0
        exec_secs = []
        for sec in sl.sections:
            seg_prot = next((s[5] for s in sl.segments if s[0] == sec.segname), 0)
            if not (seg_prot & 4):
                continue
            if not (sec.flags & 0x80000000 or sec.flags & 0x400):
                continue
            if sec.sectname in ("__stubs", "__stub_helper", "__auth_stubs"):
                continue
            exec_secs.append(f"{sec.segname},{sec.sectname}")
            code = data[sl.offset + sec.offset : sl.offset + sec.offset + sec.size]
            text_bytes += len(code)
            base = sec.addr
            for addr, size, mn, op in md.disasm_lite(code, base):
                total += 1
                if mn == ".byte":
                    skipped += size
                    continue
                i = addr - base
                j = i
                while j < i + size and code[j] in PREFIXES:
                    j += 1
                b0 = code[j] if j < i + size else 0
                classes = set()
                if b0 == 0x62:
                    classes.add("evex")
                    classes.add("avx512")
                elif b0 in (0xC4, 0xC5) or (b0 == 0x8F and j + 1 < i + size and (code[j + 1] >> 3) & 7):
                    key = (mn, norm(op))
                    groups = cache.get(key)
                    if groups is None:
                        ins = next(mdd.disasm(code[i : i + size], addr, 1), None)
                        groups = frozenset(GROUP_NAMES[g] for g in (ins.groups if ins else []) if g in GROUP_NAMES)
                        cache[key] = groups
                    classes |= groups
                    if mn.startswith(("vaes", "vpclmul")) and "ymm" in op:
                        classes.add("vaes256" if mn.startswith("vaes") else "vpclmul256")
                    if not classes:
                        classes.add("vex_other")
                elif b0 == 0xD5:
                    classes.add("rex2")
                extra = EXTRA_MNEMONICS.get(mn)
                if extra:
                    classes.add(extra)
                if not classes:
                    continue
                fi = bisect.bisect_right(starts, addr) - 1
                for c in classes:
                    counts[c] += 1
                    funcs[c].add(fi)
                if classes & {"avx2", "fma", "avx512", "bmi1", "bmi2", "f16c"}:
                    func_any_simd.add(fi)

        def name_of(fi):
            if fi < 0 or fi >= len(starts):
                return "?"
            return syms.get(starts[fi], f"sub_{starts[fi]:x}")

        res = {
            "arch": sl.arch,
            "exec_sections": exec_secs,
            "text_bytes": text_bytes,
            "insns": total,
            "skipped_bytes": skipped,
            "n_funcs": len(starts),
            "counts": dict(counts),
            "funcs": {c: len(v) for c, v in funcs.items()},
            "funcs_v3_any": len(func_any_simd),
            "func_names": {
                c: sorted({name_of(fi) for fi in v})[:3000]
                for c, v in funcs.items()
                if c in NOT_COFFEE_LAKE or c in ("cpuid", "xgetbv", "rtm")
            },
        }
        out["slices"].append(res)
    return out


def main() -> None:
    zpath, outp = sys.argv[1], sys.argv[2]
    procs = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    zf = zipfile.ZipFile(zpath)
    names = []
    for info in zf.infolist():
        if info.filename.startswith("__MACOSX/") or info.filename.endswith("/"):
            continue
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            continue
        with zf.open(info) as fh:
            head = fh.read(4)
        if head in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
            names.append((info.file_size, info.filename))
    names.sort(reverse=True)
    jobs = [(zpath, n) for _, n in names]
    results = []
    with Pool(procs) as pool:
        for k, r in enumerate(pool.imap_unordered(scan_file, jobs), 1):
            results.append(r)
            if k % 25 == 0:
                print(f"{k}/{len(jobs)}", flush=True)
    Path(outp).write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("fertig", len(results))


if __name__ == "__main__":
    main()
