"""Vergleicht die Payload (gzip-cpio) eines pkg mit dem signierten App-Zip:
Dateiliste, Inhalt (sha256), Symlinks, Rechte, AppleDouble-Einträge.

Aufruf: python -I pkg_vergleich.py <Payload> <app.zip>
"""

import gzip
import hashlib
import stat
import sys
import zipfile


def read_cpio(path):
    entries = {}
    with gzip.open(path, "rb") as fh:
        while True:
            magic = fh.read(6)
            if magic == b"070707":
                hdr = fh.read(70)
                # odc: dev ino mode uid gid nlink rdev mtime namesize filesize (oktal)
                f = [hdr[0:6], hdr[6:12], hdr[12:18], hdr[18:24], hdr[24:30], hdr[30:36], hdr[36:42], hdr[42:53], hdr[53:59], hdr[59:70]]
                mode = int(f[2], 8)
                namesize = int(f[8], 8)
                filesize = int(f[9], 8)
                name = fh.read(namesize)[:-1].decode("utf-8", "replace")
                data = fh.read(filesize)
            elif magic in (b"070701", b"070702"):
                hdr = fh.read(104)
                vals = [int(hdr[i : i + 8], 16) for i in range(0, 104, 8)]
                mode, filesize, namesize = vals[1], vals[6], vals[11]
                name = fh.read(namesize)[:-1].decode("utf-8", "replace")
                pad = (4 - (110 + namesize) % 4) % 4
                fh.read(pad)
                data = fh.read(filesize)
                fh.read((4 - filesize % 4) % 4)
            else:
                raise ValueError(f"unbekannter cpio-Magic {magic!r}")
            if name == "TRAILER!!!":
                break
            entries[name] = (mode, data)
    return entries


def main() -> None:
    cp = read_cpio(sys.argv[1])
    zf = zipfile.ZipFile(sys.argv[2])
    z = {}
    for info in zf.infolist():
        n = info.filename
        if n.endswith("/"):
            n = n[:-1]
        z[n] = info
    # cpio-Namen beginnen mit "./"
    cpn = {k[2:] if k.startswith("./") else k: v for k, v in cp.items()}
    cpn.pop(".", None)
    cpn.pop("", None)
    only_cpio = sorted(set(cpn) - set(z))
    only_zip = sorted(n for n in set(z) - set(cpn) if not n.startswith("__MACOSX"))
    print("cpio-Einträge:", len(cpn), "Zip-Einträge (ohne __MACOSX):", sum(1 for n in z if not n.startswith("__MACOSX")))
    print("nur in cpio:", len(only_cpio), only_cpio[:20])
    print("nur im Zip:", len(only_zip), only_zip[:20])
    diff_content, diff_link, diff_mode, same = [], [], [], 0
    for n, (mode, data) in cpn.items():
        info = z.get(n)
        if info is None:
            continue
        zmode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            if zf.read(info) != data:
                diff_link.append(n)
            else:
                same += 1
            continue
        if stat.S_ISDIR(mode):
            continue
        if hashlib.sha256(zf.read(info)).digest() != hashlib.sha256(data).digest():
            diff_content.append(n)
        else:
            same += 1
        if (mode & 0o7777) != (zmode & 0o7777):
            diff_mode.append((n, oct(mode & 0o7777), oct(zmode & 0o7777)))
    print("gleich:", same)
    print("Inhalt verschieden:", len(diff_content), diff_content[:20])
    print("Symlink verschieden:", len(diff_link), diff_link[:20])
    print("Rechte verschieden:", len(diff_mode), diff_mode[:20])
    ad = [n for n in cpn if "/._" in n or n.startswith("._")]
    print("AppleDouble in cpio:", ad[:10])


if __name__ == "__main__":
    main()
