"""Inventar eines ditto-Zips: Dateien, Symlinks, AppleDouble, Mach-O-Kandidaten.

Liest nur, führt nichts aus. Aufruf: python -I zipinventar.py <zip> <ausgabe.json>
"""

import json
import stat
import sys
import zipfile

MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce": "macho32-be",
    b"\xce\xfa\xed\xfe": "macho32",
    b"\xfe\xed\xfa\xcf": "macho64-be",
    b"\xcf\xfa\xed\xfe": "macho64",
    b"\xca\xfe\xba\xbe": "fat",
    b"\xca\xfe\xba\xbf": "fat64",
}


def main() -> None:
    src, out = sys.argv[1], sys.argv[2]
    zf = zipfile.ZipFile(src)
    entries = []
    counts = {"file": 0, "dir": 0, "symlink": 0, "appledouble": 0, "macho": 0}
    for info in zf.infolist():
        mode = info.external_attr >> 16
        name = info.filename
        rec = {"name": name, "size": info.file_size, "mode": oct(mode)}
        if name.startswith("__MACOSX/"):
            rec["kind"] = "appledouble"
            counts["appledouble"] += 1
        elif stat.S_ISLNK(mode):
            rec["kind"] = "symlink"
            rec["target"] = zf.read(info).decode("utf-8", "replace")
            counts["symlink"] += 1
        elif name.endswith("/"):
            rec["kind"] = "dir"
            counts["dir"] += 1
        else:
            rec["kind"] = "file"
            counts["file"] += 1
            with zf.open(info) as fh:
                head = fh.read(4)
            magic = MACHO_MAGICS.get(head)
            if magic:
                rec["macho"] = magic
                counts["macho"] += 1
            # Für fat-Magic: Java-Class-Dateien teilen sie; Prüfung später.
            rec["exec"] = bool(mode & 0o111)
        entries.append(rec)
    json.dump({"counts": counts, "entries": entries}, open(out, "w", encoding="utf-8"), indent=1)
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
