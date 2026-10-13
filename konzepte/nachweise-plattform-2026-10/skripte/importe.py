"""Importierte Symbole aus Systembibliotheken je Mach-O (über lief, nur Lesen).

Vergleicht die Importe der Dateien mit minos >= 26 gegen alle übrigen und
listet Symbole, die nur die 26er-Dateien ziehen.
Aufruf: python -I importe.py <app.zip> <bundle.json>
"""

import collections
import json
import sys
import zipfile

import lief

lief.logging.disable()


def imports_of(data: bytes):
    fat = lief.MachO.parse(list(data))
    out = collections.defaultdict(set)
    if fat is None:
        return out
    for b in fat:
        for sym in b.imported_symbols:
            lib = None
            try:
                if sym.has_binding_info:
                    bi = sym.binding_info
                    if bi.has_library:
                        lib = bi.library.name
            except Exception:  # noqa: BLE001
                lib = None
            out[lib or "?"].add(sym.name)
    return out


def main() -> None:
    zf = zipfile.ZipFile(sys.argv[1])
    d = json.load(open(sys.argv[2], encoding="utf-8"))
    new_syms = collections.defaultdict(set)
    old_syms = collections.defaultdict(set)
    per_file = {}
    for r in d["macho"]:
        s = r["slices"][0]
        minos = tuple(int(x) for x in (s["minos"] or "0.0.0").split("."))
        if minos < (14, 4, 0) and "PySide6" not in r["path"] and "shiboken6" not in r["path"]:
            continue
        imps = imports_of(zf.read(r["path"]))
        per_file[r["path"]] = {k: sorted(v) for k, v in imps.items()}
        target = new_syms if minos >= (26, 0, 0) else old_syms
        for lib, names in imps.items():
            if lib.startswith("/usr/lib") or lib.startswith("/System") or lib == "?":
                target[lib].update(names)
    print("Systemsymbole, die nur Dateien mit minos >= 26 importieren (nicht die 14.4-Qt-Bibliotheken):")
    for lib in sorted(new_syms):
        only = sorted(new_syms[lib] - old_syms.get(lib, set()))
        if only:
            print(f"  {lib}: {len(only)}")
            for n in only:
                print("     ", n)
    json.dump(per_file, open(sys.argv[2].replace(".json", "-importe.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
