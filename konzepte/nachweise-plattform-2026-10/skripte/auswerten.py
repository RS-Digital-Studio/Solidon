"""Fasst das JSON aus bundle_pruefen.py zusammen. Aufruf: python -I auswerten.py <json>"""

import collections
import json
import sys


def vt(v):
    if not v:
        return (0,)
    return tuple(int(x) for x in v.split("."))


def main() -> None:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    info = d["info_plist"]
    print("== Info.plist ==")
    for k in sorted(info):
        print(f"  {k}: {info[k]!r}")
    print("== Hauptprogramm Spezialslots ==", d["main_exe_special_slots"])
    lsmin = info.get("LSMinimumSystemVersion")
    teams = collections.Counter()
    flags = collections.Counter()
    archs = collections.Counter()
    minos = collections.Counter()
    nosig, adhoc, linker, noruntime, badpages, badspecial, fremdteam = [], [], [], [], [], [], []
    ents = []
    cms = collections.Counter()
    missing = []
    over_min = []
    errors = []
    sdks = collections.Counter()
    hashes = collections.Counter()
    cdcount = collections.Counter()
    filetypes = collections.Counter()
    for r in d["macho"]:
        if "error" in r:
            errors.append((r["path"], r["error"]))
            continue
        archs[tuple(s["arch"] for s in r["slices"])] += 1
        for s in r["slices"]:
            filetypes[s["filetype"]] += 1
            minos[(s["min_cmd"], s["minos"])] += 1
            sdks[s["sdk"]] += 1
            if lsmin and s["minos"] and vt(s["minos"]) > vt(lsmin):
                over_min.append((r["path"], s["arch"], s["minos"]))
            if s["missing_deps"]:
                missing.append((r["path"], s["missing_deps"]))
            sig = s["signature"]
            if not sig:
                nosig.append(r["path"])
                continue
            if "error" in sig:
                errors.append((r["path"], sig["error"]))
                continue
            cdcount[len(sig["cds"])] += 1
            for cd in sig["cds"]:
                hashes[cd["hash"]] += 1
                teams[cd["team"]] += 1
                flags[tuple(cd["flag_names"])] += 1
                if "adhoc" in cd["flag_names"]:
                    adhoc.append(r["path"])
                if "linkerSigned" in cd["flag_names"]:
                    linker.append(r["path"])
                if "runtime" not in cd["flag_names"]:
                    noruntime.append(r["path"])
                if cd["bad_pages"] or cd["pages_ok"] != cd["pages"]:
                    badpages.append((r["path"], cd["hash"], cd["pages_ok"], cd["pages"], cd["bad_pages"]))
                if any(v != "ok" and v != "leer" for v in cd["special"].values()):
                    badspecial.append((r["path"], cd["special"]))
            if sig["entitlements_xml"] or sig["entitlements_der_b64"]:
                ents.append((r["path"], sig["entitlements_xml"], sig["entitlements_der_b64"]))
            c = sig["cms"]
            key = (c.get("cms"), tuple((x["cn"], x["ou"]) for x in c.get("certs", [])[:1]), c.get("digest_matches_cd0"), c.get("timestamp_token"))
            cms[key] += 1
    print("== Zahl ==", len(d["macho"]), "Mach-O")
    print("== Architekturen ==", dict(archs))
    print("== Dateitypen ==", dict(filetypes))
    print("== minos ==", sorted(minos.items(), key=lambda kv: vt(kv[0][1])))
    print("== SDK ==", sorted(sdks.items(), key=lambda kv: vt(kv[0])))
    print("== über LSMinimumSystemVersion", lsmin, "==", len(over_min))
    for x in over_min[:40]:
        print("   ", x)
    print("== Team-IDs (je CD) ==", dict(teams))
    print("== Flags (je CD) ==", dict(flags))
    print("== Hashes (je CD) ==", dict(hashes), "CDs je Datei", dict(cdcount))
    print("== CMS ==")
    for k, v in cms.items():
        print("   ", v, k)
    print("== ohne Signatur ==", len(nosig), nosig[:20])
    print("== ad hoc ==", len(set(adhoc)), sorted(set(adhoc))[:40])
    print("== linker-signed ==", len(set(linker)), sorted(set(linker))[:20])
    print("== ohne runtime ==", len(set(noruntime)), sorted(set(noruntime))[:20])
    print("== Seitenhash falsch ==", len(badpages))
    for x in badpages[:20]:
        print("   ", x)
    print("== Spezialslot falsch ==", len(badspecial), badspecial[:10])
    print("== Entitlements ==", len(ents))
    for p, x, der in ents:
        print("   ", p)
        print("      XML:", x)
        print("      DER:", der)
    print("== fehlende Abhängigkeiten ==", len(missing))
    for p, m in missing[:60]:
        for dep in m:
            print("   ", p, dep["kind"], dep["dep"])
    print("== Fehler ==", errors[:20])
    cr = d["coderesources"]
    print("== CodeResources ==")
    for k, v in cr.items():
        if isinstance(v, list):
            print(f"   {k}: {len(v)} {v[:15]}")
        else:
            print(f"   {k}: {v}")


if __name__ == "__main__":
    main()
