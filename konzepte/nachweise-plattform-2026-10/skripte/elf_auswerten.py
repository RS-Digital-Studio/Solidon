"""Fasst elf_pruefen.py zusammen. Aufruf: python -I elf_auswerten.py <json>"""

import collections
import json
import re
import sys

# Was auf einer frischen Desktop-Installation (Ubuntu 22.04/24.04 GNOME,
# Fedora Workstation) ohne Zutun vorhanden ist — konservativ.
SYSTEM = {
    "libc.so.6", "libm.so.6", "libdl.so.2", "libpthread.so.0", "librt.so.1", "libutil.so.1",
    "ld-linux-x86-64.so.2", "libresolv.so.2", "libnsl.so.1", "libcrypt.so.1", "libanl.so.1",
    "libgcc_s.so.1", "libstdc++.so.6", "libz.so.1",
    "libGL.so.1", "libEGL.so.1", "libGLX.so.0", "libOpenGL.so.0", "libGLdispatch.so.0", "libgbm.so.1", "libdrm.so.2",
    "libX11.so.6", "libX11-xcb.so.1", "libxcb.so.1", "libXext.so.6", "libXrender.so.1", "libXau.so.6", "libXdmcp.so.6",
    "libXi.so.6", "libXfixes.so.3", "libXcursor.so.1", "libXrandr.so.2", "libXinerama.so.1",
    "libfontconfig.so.1", "libfreetype.so.6", "libexpat.so.1", "libpng16.so.16", "libharfbuzz.so.0", "libbz2.so.1.0",
    "libdbus-1.so.3", "libglib-2.0.so.0", "libgobject-2.0.so.0", "libgio-2.0.so.0", "libgthread-2.0.so.0", "libgmodule-2.0.so.0",
    "libxkbcommon.so.0", "libxkbcommon-x11.so.0", "libwayland-client.so.0", "libwayland-cursor.so.0", "libwayland-egl.so.1",
    "libxcb-shm.so.0", "libxcb-render.so.0", "libxcb-randr.so.0", "libxcb-xfixes.so.0", "libxcb-sync.so.1", "libxcb-xkb.so.1",
    "libxcb-shape.so.0", "libxcb-xinput.so.0", "libxcb-glx.so.0", "libxcb-dri3.so.0", "libxcb-present.so.0", "libxcb-dri2.so.0",
    "libxcb-xinerama.so.0",
    "libvulkan.so.1", "libuuid.so.1", "libblkid.so.1", "libmount.so.1", "libselinux.so.1", "libpcre2-8.so.0", "libffi.so.8",
    "libsystemd.so.0", "libcap.so.2", "liblzma.so.5", "libzstd.so.1", "liblz4.so.1", "libgcrypt.so.20", "libgpg-error.so.0",
    "libssl.so.3", "libcrypto.so.3", "libudev.so.1", "libbrotlidec.so.1", "libbrotlicommon.so.1", "libgraphite2.so.3",
    "libasound.so.2", "libpulse.so.0", "libicuuc.so.74", "libicui18n.so.74",
}
# Gibt es auf frischer Ubuntu-Desktop-Installation oft NICHT (Qt-xcb-Plugin).
QT_XCB_EXTRA = {
    "libxcb-cursor.so.0", "libxcb-icccm.so.4", "libxcb-image.so.0", "libxcb-keysyms.so.1", "libxcb-render-util.so.0",
    "libxcb-util.so.1",
}

KNOWN = {
    "GLIBC": {"Ubuntu 22.04": (2, 35), "Ubuntu 24.04": (2, 39), "Debian 12": (2, 36), "Fedora 40": (2, 39), "RHEL 9": (2, 34)},
    "GLIBCXX": {"Ubuntu 22.04": (3, 4, 30), "Ubuntu 24.04": (3, 4, 33), "Debian 12": (3, 4, 30), "Fedora 40": (3, 4, 33), "RHEL 9": (3, 4, 29)},
}


def vt(v):
    m = re.match(r"^([A-Z]+)_(\d+(?:\.\d+)*)$", v)
    if not m:
        return None, None
    return m.group(1), tuple(int(x) for x in m.group(2).split("."))


def main() -> None:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    provided = set(d["provided"])
    elfs = d["elf"]
    print("ELF-Dateien:", len(elfs))
    maxv = {}
    maxv_file = {}
    per_lib_req = collections.defaultdict(lambda: collections.defaultdict(set))
    for e in elfs:
        for lib, vs in e.get("verneed", {}).items():
            for v in vs:
                fam, t = vt(v)
                if fam is None:
                    continue
                per_lib_req[lib][fam].add(t)
                if fam not in maxv or t > maxv[fam]:
                    maxv[fam] = t
                    maxv_file[fam] = (e["path"], lib, v)
    print("== Höchste benötigte Symbolversion je Familie (über alle Dateien) ==")
    for fam in sorted(maxv):
        print(f"  {fam}_{'.'.join(map(str, maxv[fam]))}  <- {maxv_file[fam][0]} (aus {maxv_file[fam][1]})")
    # Rangfolge GLIBC je Datei
    glibc = []
    for e in elfs:
        best = None
        for lib, vs in e.get("verneed", {}).items():
            for v in vs:
                fam, t = vt(v)
                if fam == "GLIBC" and (best is None or t > best):
                    best = t
        if best:
            glibc.append((best, e["path"]))
    glibc.sort(reverse=True)
    print("== Die 15 Dateien mit dem höchsten GLIBC-Bedarf ==")
    for t, p in glibc[:15]:
        print(f"  GLIBC_{'.'.join(map(str, t))}  {p}")
    for fam in ("GLIBC", "GLIBCXX"):
        if fam in maxv:
            for distro, have in KNOWN[fam].items():
                print(f"  {fam}: {distro} hat {'.'.join(map(str, have))} -> {'ok' if maxv[fam] <= have else 'ZU NEU'}")
    # libstdc++ mitgeliefert?
    bundled_cxx = [e["path"] for e in elfs if (e.get("soname") or "").startswith("libstdc++")]
    print("libstdc++ im Paket:", bundled_cxx)
    bundled_gcc = [e["path"] for e in elfs if (e.get("soname") or "").startswith("libgcc_s")]
    print("libgcc_s im Paket:", bundled_gcc)
    # fehlende NEEDED
    missing = collections.Counter()
    users = collections.defaultdict(list)
    for e in elfs:
        for n in e.get("needed", []):
            if n not in provided:
                missing[n] += 1
                users[n].append(e["path"])
    print("== NEEDED, die nicht im Paket liegen ==")
    for n, c in sorted(missing.items()):
        cls = "System" if n in SYSTEM else ("Qt-xcb-Zusatz (oft NICHT installiert)" if n in QT_XCB_EXTRA else "UNKLAR")
        print(f"  {n:32s} {c:4d}x  [{cls}]  z.B. {users[n][0]}")
    # ISA
    isa = collections.Counter()
    isa_files = collections.defaultdict(list)
    for e in elfs:
        p = e.get("props", {})
        key = tuple(p.get("isa_needed", [])) or ("-",)
        isa[key] += 1
        isa_files[key].append(e["path"])
    print("== GNU_PROPERTY_X86_ISA_1_NEEDED ==")
    for k, v in isa.items():
        print(f"  {k}: {v}  z.B. {isa_files[k][:5]}")
    feat = collections.Counter(e.get("props", {}).get("feature_1_and", "-") for e in elfs)
    print("  FEATURE_1_AND (IBT/SHSTK):", dict(feat))
    # Plugins
    print("== Qt-Plugins ==")
    for e in sorted(elfs, key=lambda x: x["path"]):
        if "/plugins/" in e["path"] and any(k in e["path"] for k in ("platforms/", "xcbglintegrations", "wayland", "platformthemes", "platforminputcontexts", "egldeviceintegrations")):
            print("  ", e["path"].split("/plugins/")[1], "NEEDED:", [n for n in e["needed"] if not n.startswith("libQt6") and n not in ("libc.so.6", "libm.so.6", "libstdc++.so.6", "libgcc_s.so.1")])
    print("== Interpreter ==", collections.Counter(e.get("interp") for e in elfs))
    print("== Fehler ==", [e["path"] for e in elfs if "error" in e][:10])


if __name__ == "__main__":
    main()
