"""Sucht in allen Mach-O eines App-Zips nach Eigenschaften, die die Hardened
Runtime anders behandelt: Textrelokationen (Rebase in nicht beschreibbare
Segmente, LC_DYSYMTAB-Relokationen), W+X-Segmente, Header-Flags.

Aufruf: python -I textrelocs.py <app.zip>
"""

import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import macho  # noqa: E402

LC_DYSYMTAB = 0xB
LC_DYLD_INFO = 0x22
LC_DYLD_INFO_ONLY = 0x80000022
LC_DYLD_CHAINED_FIXUPS = 0x80000034
LC_SEGMENT_SPLIT_INFO = 0x1E
HDR_FLAGS = {0x20000: "ALLOW_STACK_EXECUTION", 0x200000: "PIE", 0x1000000: "NO_HEAP_EXECUTION",
             0x800000: "HAS_TLV"}


def uleb(b, i):
    v = s = 0
    while True:
        x = b[i]
        i += 1
        v |= (x & 0x7F) << s
        s += 7
        if not x & 0x80:
            return v, i


def rebase_segments(blob, nseg):
    """Liefert die Segmentindizes, in die Rebase-Opcodes schreiben."""
    segs = set()
    i = 0
    seg = None
    while i < len(blob):
        op = blob[i] & 0xF0
        imm = blob[i] & 0x0F
        i += 1
        if op == 0x00:  # DONE
            break
        elif op == 0x10:  # SET_TYPE_IMM
            pass
        elif op == 0x20:  # SET_SEGMENT_AND_OFFSET_ULEB
            seg = imm
            _, i = uleb(blob, i)
        elif op == 0x30:  # ADD_ADDR_ULEB
            _, i = uleb(blob, i)
        elif op == 0x40:  # ADD_ADDR_IMM_SCALED
            pass
        elif op == 0x50:  # DO_REBASE_IMM_TIMES
            segs.add(seg)
        elif op == 0x60:  # DO_REBASE_ULEB_TIMES
            _, i = uleb(blob, i)
            segs.add(seg)
        elif op == 0x70:  # DO_REBASE_ADD_ADDR_ULEB
            _, i = uleb(blob, i)
            segs.add(seg)
        elif op == 0x80:  # DO_REBASE_ULEB_TIMES_SKIPPING_ULEB
            _, i = uleb(blob, i)
            _, i = uleb(blob, i)
            segs.add(seg)
        else:
            segs.add(("unbekannt", op))
            break
    return segs


def main() -> None:
    zf = zipfile.ZipFile(sys.argv[1])
    n_files = 0
    findings = []
    fixups = {"chained": 0, "dyld_info": 0, "keine": 0}
    for info in zf.infolist():
        if info.filename.startswith("__MACOSX/") or info.filename.endswith("/"):
            continue
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            continue
        with zf.open(info) as fh:
            if fh.read(4) not in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
                continue
        data = zf.read(info)
        n_files += 1
        for sl in macho.parse_macho(data):
            base = sl.offset
            flags = sl.flags
            fl = [n for b, n in HDR_FLAGS.items() if flags & b and n not in ("PIE", "NO_HEAP_EXECUTION", "HAS_TLV")]
            wx = [s[0] for s in sl.segments if (s[5] & 2) and (s[5] & 4)]
            pos = base + 32
            nlocrel = nextrel = 0
            reb_bad = set()
            kind = "keine"
            for _ in range(sl.ncmds):
                cmd, size = struct.unpack("<II", data[pos : pos + 8])
                if cmd == LC_DYSYMTAB:
                    vals = struct.unpack("<18I", data[pos + 8 : pos + 80])
                    nextrel, nlocrel = vals[15], vals[17]
                elif cmd in (LC_DYLD_INFO, LC_DYLD_INFO_ONLY):
                    kind = "dyld_info"
                    rebase_off, rebase_size = struct.unpack("<II", data[pos + 8 : pos + 16])
                    blob = data[base + rebase_off : base + rebase_off + rebase_size]
                    for sg in rebase_segments(blob, len(sl.segments)):
                        if isinstance(sg, int) and sg < len(sl.segments):
                            segprot = sl.segments[sg][5]
                            if not segprot & 2:
                                reb_bad.add(sl.segments[sg][0])
                        elif sg is not None:
                            reb_bad.add(str(sg))
                elif cmd == LC_DYLD_CHAINED_FIXUPS:
                    kind = "chained"
                pos += size
            fixups[kind] += 1
            if fl or wx or nlocrel or nextrel or reb_bad:
                findings.append((info.filename, sl.arch, fl, wx, nlocrel, nextrel, sorted(map(str, reb_bad))))
    print("Mach-O:", n_files, "Fixup-Art:", fixups)
    print("Auffällig (Header-Flags, W+X-Segment, LC_DYSYMTAB-Relokationen, Rebase in r-x):", len(findings))
    for f in findings:
        print("  ", f)


if __name__ == "__main__":
    main()
