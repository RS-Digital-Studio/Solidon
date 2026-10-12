"""Kleiner, eigenständiger Mach-O-Leser: Kopf, Ladebefehle, Code-Signatur.

Liest Bytes, führt nichts aus. Wird von den Auswerteskripten importiert.
"""

from __future__ import annotations

import hashlib
import plistlib
import struct
from dataclasses import dataclass, field

CPU_NAMES = {
    (0x01000007, 3): "x86_64",
    (0x01000007, 8): "x86_64h",
    (0x0100000C, 0): "arm64",
    (0x0100000C, 1): "arm64v8",
    (0x0100000C, 2): "arm64e",
    (7, 3): "i386",
}

LC_SEGMENT_64 = 0x19
LC_LOAD_DYLIB = 0xC
LC_ID_DYLIB = 0xD
LC_LOAD_WEAK_DYLIB = 0x80000018
LC_REEXPORT_DYLIB = 0x8000001F
LC_LAZY_LOAD_DYLIB = 0x20
LC_LOAD_UPWARD_DYLIB = 0x80000023
LC_RPATH = 0x8000001C
LC_CODE_SIGNATURE = 0x1D
LC_BUILD_VERSION = 0x32
LC_VERSION_MIN_MACOSX = 0x24
LC_DYLD_CHAINED_FIXUPS = 0x80000034
LC_ENCRYPTION_INFO_64 = 0x2C

DYLIB_CMDS = {
    LC_LOAD_DYLIB: "load",
    LC_LOAD_WEAK_DYLIB: "weak",
    LC_REEXPORT_DYLIB: "reexport",
    LC_LAZY_LOAD_DYLIB: "lazy",
    LC_LOAD_UPWARD_DYLIB: "upward",
}

CSMAGIC_EMBEDDED_SIGNATURE = 0xFADE0CC0
CSMAGIC_CODEDIRECTORY = 0xFADE0C02
CSMAGIC_REQUIREMENTS = 0xFADE0C01
CSMAGIC_EMBEDDED_ENTITLEMENTS = 0xFADE7171
CSMAGIC_EMBEDDED_DER_ENTITLEMENTS = 0xFADE7172
CSMAGIC_BLOBWRAPPER = 0xFADE0B01

HASH_TYPES = {1: ("sha1", 20), 2: ("sha256", 32), 3: ("sha256", 20), 4: ("sha384", 48)}

CD_FLAGS = {
    0x1: "host",
    0x2: "adhoc",
    0x4: "forceHard",
    0x8: "forceKill",
    0x10: "forceExpiration",
    0x20: "restrict",
    0x40: "enforcement",
    0x80: "libraryValidation",
    0x10000: "runtime",
    0x20000: "linkerSigned",
}


def ver(v: int) -> str:
    return f"{v >> 16}.{(v >> 8) & 0xFF}.{v & 0xFF}"


@dataclass
class CodeDirectory:
    slot: int
    version: int
    flags: int
    hash_type: int
    hash_size: int
    page_size: int
    code_limit: int
    n_code: int
    n_special: int
    identifier: str
    team_id: str | None
    platform: int
    exec_seg_flags: int | None
    runtime_version: int | None
    raw: bytes
    hash_offset: int

    @property
    def flag_names(self) -> list[str]:
        return [n for b, n in CD_FLAGS.items() if self.flags & b]

    def cdhash(self) -> str:
        name, size = HASH_TYPES[self.hash_type]
        return hashlib.new(name, self.raw).hexdigest()[: size * 2 if size < 32 else 40]

    def special_hash(self, slot: int) -> bytes | None:
        """Hash des Spezialslots -slot (slot positiv, 1..n_special)."""
        if slot > self.n_special:
            return None
        off = self.hash_offset - slot * self.hash_size
        return self.raw[off : off + self.hash_size]

    def code_hashes(self) -> list[bytes]:
        return [
            self.raw[self.hash_offset + i * self.hash_size : self.hash_offset + (i + 1) * self.hash_size]
            for i in range(self.n_code)
        ]


@dataclass
class Signature:
    offset: int
    size: int
    blobs: dict[int, bytes] = field(default_factory=dict)
    cds: list[CodeDirectory] = field(default_factory=list)
    entitlements_xml: bytes | None = None
    entitlements_der: bytes | None = None
    requirements: bytes | None = None
    cms: bytes | None = None
    error: str | None = None


@dataclass
class Section:
    segname: str
    sectname: str
    addr: int
    size: int
    offset: int
    flags: int


@dataclass
class Slice:
    arch: str
    offset: int
    size: int
    filetype: int
    flags: int
    dylibs: list[tuple[str, str]] = field(default_factory=list)
    rpaths: list[str] = field(default_factory=list)
    id_dylib: str | None = None
    minos: str | None = None
    sdk: str | None = None
    build_platform: int | None = None
    min_cmd: str | None = None
    sections: list[Section] = field(default_factory=list)
    segments: list[tuple[str, int, int, int, int, int]] = field(default_factory=list)
    signature: Signature | None = None
    sig_cmd: tuple[int, int] | None = None
    hdr_end: int = 0
    ncmds: int = 0


def parse_signature(data: bytes, base: int, off: int, size: int) -> Signature:
    sig = Signature(offset=off, size=size)
    blob = data[base + off : base + off + size]
    if len(blob) < 12:
        sig.error = "Signaturbereich außerhalb der Datei"
        return sig
    magic, length, count = struct.unpack(">III", blob[:12])
    if magic != CSMAGIC_EMBEDDED_SIGNATURE:
        sig.error = f"SuperBlob-Magic {magic:#x}"
        return sig
    for i in range(count):
        typ, boff = struct.unpack(">II", blob[12 + 8 * i : 20 + 8 * i])
        bmagic, blen = struct.unpack(">II", blob[boff : boff + 8])
        raw = blob[boff : boff + blen]
        sig.blobs[typ] = raw
        if bmagic == CSMAGIC_CODEDIRECTORY:
            sig.cds.append(parse_cd(typ, raw))
        elif bmagic == CSMAGIC_EMBEDDED_ENTITLEMENTS:
            sig.entitlements_xml = raw[8:]
        elif bmagic == CSMAGIC_EMBEDDED_DER_ENTITLEMENTS:
            sig.entitlements_der = raw[8:]
        elif bmagic == CSMAGIC_REQUIREMENTS:
            sig.requirements = raw
        elif bmagic == CSMAGIC_BLOBWRAPPER:
            sig.cms = raw[8:]
    return sig


def parse_cd(slot: int, raw: bytes) -> CodeDirectory:
    (
        _magic,
        _length,
        version,
        flags,
        hash_offset,
        ident_offset,
        n_special,
        n_code,
        code_limit,
        hash_size,
        hash_type,
        platform,
        page_size,
        _spare2,
    ) = struct.unpack(">IIIIIIIIIBBBBI", raw[:44])
    team = None
    exec_seg_flags = None
    runtime = None
    pos = 44
    if version >= 0x20100:
        pos += 4  # scatterOffset
    if version >= 0x20200:
        (team_off,) = struct.unpack(">I", raw[pos : pos + 4])
        pos += 4
        if team_off:
            team = raw[team_off : raw.index(b"\0", team_off)].decode()
    if version >= 0x20300:
        _spare3, code_limit64 = struct.unpack(">IQ", raw[pos : pos + 12])
        pos += 12
        if code_limit64:
            code_limit = code_limit64
    if version >= 0x20400:
        _base, _limit, exec_seg_flags = struct.unpack(">QQQ", raw[pos : pos + 24])
        pos += 24
    if version >= 0x20500:
        runtime, _pre = struct.unpack(">II", raw[pos : pos + 8])
        pos += 8
    ident = raw[ident_offset : raw.index(b"\0", ident_offset)].decode("utf-8", "replace")
    return CodeDirectory(
        slot=slot,
        version=version,
        flags=flags,
        hash_type=hash_type,
        hash_size=hash_size,
        page_size=(1 << page_size) if page_size else 0,
        code_limit=code_limit,
        n_code=n_code,
        n_special=n_special,
        identifier=ident,
        team_id=team,
        platform=platform,
        exec_seg_flags=exec_seg_flags,
        runtime_version=runtime,
        raw=raw,
        hash_offset=hash_offset,
    )


def parse_slice(data: bytes, base: int, size: int) -> Slice:
    magic = data[base : base + 4]
    if magic != b"\xcf\xfa\xed\xfe":
        raise ValueError(f"nicht unterstützter Slice-Magic {magic.hex()}")
    cputype, cpusub, filetype, ncmds, sizeofcmds, flags, _res = struct.unpack("<iIIIIII", data[base + 4 : base + 32])
    arch = CPU_NAMES.get((cputype & 0xFFFFFFFF, cpusub & 0xFFFFFF), f"cpu{cputype:#x}/{cpusub:#x}")
    sl = Slice(arch=arch, offset=base, size=size, filetype=filetype, flags=flags, ncmds=ncmds)
    pos = base + 32
    sl.hdr_end = pos + sizeofcmds
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack("<II", data[pos : pos + 8])
        body = data[pos : pos + cmdsize]
        if cmd in DYLIB_CMDS or cmd == LC_ID_DYLIB:
            (name_off,) = struct.unpack("<I", body[8:12])
            name = body[name_off:].split(b"\0", 1)[0].decode("utf-8", "replace")
            if cmd == LC_ID_DYLIB:
                sl.id_dylib = name
            else:
                sl.dylibs.append((DYLIB_CMDS[cmd], name))
        elif cmd == LC_RPATH:
            (name_off,) = struct.unpack("<I", body[8:12])
            sl.rpaths.append(body[name_off:].split(b"\0", 1)[0].decode("utf-8", "replace"))
        elif cmd == LC_CODE_SIGNATURE:
            dataoff, datasize = struct.unpack("<II", body[8:16])
            sl.sig_cmd = (dataoff, datasize)
            sl.signature = parse_signature(data, base, dataoff, datasize)
        elif cmd == LC_BUILD_VERSION:
            platform, minos, sdk, _ntools = struct.unpack("<IIII", body[8:24])
            sl.build_platform = platform
            sl.minos = ver(minos)
            sl.sdk = ver(sdk)
        elif cmd == LC_VERSION_MIN_MACOSX:
            v, s = struct.unpack("<II", body[8:16])
            sl.min_cmd = "LC_VERSION_MIN_MACOSX"
            sl.minos = ver(v)
            sl.sdk = ver(s)
        elif cmd == LC_SEGMENT_64:
            segname = body[8:24].split(b"\0", 1)[0].decode()
            vmaddr, vmsize, fileoff, filesize, maxprot, initprot, nsects, _fl = struct.unpack(
                "<QQQQiiII", body[24:72]
            )
            sl.segments.append((segname, vmaddr, vmsize, fileoff, filesize, initprot))
            for k in range(nsects):
                s = body[72 + 80 * k : 152 + 80 * k]
                sectname = s[0:16].split(b"\0", 1)[0].decode()
                sseg = s[16:32].split(b"\0", 1)[0].decode()
                addr, ssize, soff, _align, _reloff, _nreloc, sflags = struct.unpack("<QQIIIII", s[32:68])
                sl.sections.append(Section(sseg, sectname, addr, ssize, soff, sflags))
        pos += cmdsize
    return sl


def parse_macho(data: bytes) -> list[Slice]:
    magic = data[:4]
    if magic in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
        (n,) = struct.unpack(">I", data[4:8])
        if n > 30:
            raise ValueError("vermutlich Java-Class, kein Fat-Mach-O")
        slices = []
        is64 = magic == b"\xca\xfe\xba\xbf"
        for i in range(n):
            if is64:
                ct, cs, off, size, _al, _r = struct.unpack(">iiQQII", data[8 + 32 * i : 40 + 32 * i])
            else:
                ct, cs, off, size, _al = struct.unpack(">iiIII", data[8 + 20 * i : 28 + 20 * i])
            slices.append(parse_slice(data, off, size))
        return slices
    if magic == b"\xcf\xfa\xed\xfe":
        return [parse_slice(data, 0, len(data))]
    raise ValueError(f"kein unterstütztes Mach-O: {magic.hex()}")


def verify_pages(data: bytes, sl: Slice, cd: CodeDirectory) -> tuple[int, int, list[int]]:
    """Prüft die Seitenhashes einer CD gegen den Slice. Liefert (ok, gesamt, falsche Seiten)."""
    name, size = HASH_TYPES[cd.hash_type]
    hashes = cd.code_hashes()
    bad = []
    for i, h in enumerate(hashes):
        start = sl.offset + i * cd.page_size
        end = min(start + cd.page_size, sl.offset + cd.code_limit)
        got = hashlib.new(name, data[start:end]).digest()[:size]
        if got != h:
            bad.append(i)
    return len(hashes) - len(bad), len(hashes), bad


def verify_special(sig: Signature, cd: CodeDirectory) -> dict[str, str]:
    """Prüft die Spezialslots gegen die Blobs der Signatur (Requirements, Entitlements)."""
    name, size = HASH_TYPES[cd.hash_type]
    out = {}
    for slot, typ in ((2, 2), (5, 5), (7, 7)):
        expected = cd.special_hash(slot)
        if expected is None:
            continue
        blob = sig.blobs.get(typ)
        if blob is None:
            out[f"-{slot}"] = "leer" if expected == b"\0" * len(expected) else "Blob fehlt, Hash gesetzt"
            continue
        got = hashlib.new(name, blob).digest()[:size]
        out[f"-{slot}"] = "ok" if got == expected else "FALSCH"
    return out


def entitlements_dict(xml: bytes | None):
    if not xml:
        return None
    try:
        return plistlib.loads(xml)
    except Exception as exc:  # noqa: BLE001 — nur Bericht
        return {"_fehler": str(exc)}
