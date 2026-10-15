"""Prüft die verschachtelten Framework-Bundles: cdhash im äußeren Siegel gegen
das Framework-Binary, inneres CodeResources gegen die Dateien, Info.plist-Slot,
und welche Dateien im Bundle von keinem Siegel erfasst sind.

Aufruf: python -I frameworks_pruefen.py <zip>
"""

import hashlib
import plistlib
import posixpath
import stat
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import macho  # noqa: E402


def main() -> None:
    zf = zipfile.ZipFile(sys.argv[1])
    files, links = set(), {}
    for info in zf.infolist():
        n = info.filename
        if n.startswith("__MACOSX/") or n.endswith("/"):
            continue
        if stat.S_ISLNK(info.external_attr >> 16):
            links[n] = zf.read(info).decode()
        else:
            files.add(n)
    root = "Solidon3D.app/Contents"

    def resolve(path, depth=0):
        parts = path.split("/")
        cur = ""
        for i, p in enumerate(parts):
            cur = p if not cur else f"{cur}/{p}"
            if cur in links:
                new = posixpath.normpath(posixpath.join(posixpath.dirname(cur), links[cur]))
                rest = "/".join(parts[i + 1 :])
                return resolve(f"{new}/{rest}" if rest else new, depth + 1)
        return cur

    outer = plistlib.loads(zf.read(f"{root}/_CodeSignature/CodeResources"))
    files2 = outer["files2"]
    sealed_outer = set()
    nested_roots = []
    for rel, ent in files2.items():
        sealed_outer.add(f"{root}/{rel}")
        if isinstance(ent, dict) and "cdhash" in ent and f"{root}/{rel}" not in files:
            nested_roots.append((rel, ent))
    print("Verschachtelte Bundles im äußeren Siegel:", len(nested_roots))
    sealed_inner = set()
    for rel, ent in nested_roots:
        fw = f"{root}/{rel}"
        name = posixpath.basename(fw).rsplit(".", 1)[0]
        binpath = resolve(f"{fw}/Versions/Current/{name}")
        if binpath not in files:
            binpath = resolve(f"{fw}/{name}")
        verdict = []
        if binpath not in files:
            print("  FEHLT Binary:", rel)
            continue
        data = zf.read(binpath)
        sl = macho.parse_macho(data)[0]
        cds = sl.signature.cds
        have = {cd.cdhash() for cd in cds}
        verdict.append("cdhash ok" if ent["cdhash"].hex() in have else f"cdhash FALSCH {ent['cdhash'].hex()} vs {have}")
        req = ent.get("requirement", "")
        verdict.append(f"req={req[:90]}")
        vdir = posixpath.dirname(binpath)
        inner_cr = f"{vdir}/_CodeSignature/CodeResources"
        sealed_inner.update({binpath, inner_cr})
        if inner_cr in files:
            icr = plistlib.loads(zf.read(inner_cr))
            ok = bad = 0
            for irel, ient in icr.get("files2", {}).items():
                p = f"{vdir}/{irel}"
                sealed_inner.add(p)
                if isinstance(ient, dict) and "hash2" in ient:
                    if p in files and hashlib.sha256(zf.read(p)).digest() == ient["hash2"]:
                        ok += 1
                    else:
                        bad += 1
            cd = cds[0]
            hn, hs = macho.HASH_TYPES[cd.hash_type]
            crslot = "ok" if cd.special_hash(3) == hashlib.new(hn, zf.read(inner_cr)).digest()[:hs] else "FALSCH"
            ip = f"{vdir}/Resources/Info.plist"
            ipslot = "ok" if ip in files and cd.special_hash(1) == hashlib.new(hn, zf.read(ip)).digest()[:hs] else "FALSCH/fehlt"
            verdict.append(f"inner files2 ok={ok} bad={bad} CR-slot={crslot} Info.plist-slot={ipslot}")
        else:
            verdict.append("kein inneres CodeResources")
        print(" ", rel, "|", "; ".join(verdict))
    # Was ist nirgends versiegelt?
    loose = []
    for f in sorted(files | set(links)):
        if f in sealed_outer or f in sealed_inner:
            continue
        if f.startswith(f"{root}/_CodeSignature/") or f in (f"{root}/Info.plist", f"{root}/MacOS/Solidon3D"):
            continue
        loose.append(f)
    print("Nicht versiegelt (weder außen noch in einem Framework):", len(loose))
    for f in loose:
        kind = "link->" + links[f] if f in links else "datei"
        print("   ", f, kind)


if __name__ == "__main__":
    main()
