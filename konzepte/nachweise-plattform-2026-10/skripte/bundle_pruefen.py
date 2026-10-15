"""Prüft jede Mach-O-Datei eines ditto-Zips einer .app: Signatur, Team, Flags,
Seitenhashes, Entitlements, minos, Architektur, Abhängigkeiten, CodeResources.

Aufruf: python -I bundle_pruefen.py <zip> <ausgabe-präfix>
Liest nur aus dem Zip, schreibt nichts aus und führt nichts aus.
"""

from __future__ import annotations

import base64
import collections
import hashlib
import json
import plistlib
import posixpath
import stat
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import macho  # noqa: E402

from asn1crypto import cms as acms  # noqa: E402


def cms_info(raw: bytes | None, cd_raw: bytes | None) -> dict:
    if not raw:
        return {"cms": "fehlt"}
    if len(raw) == 0:
        return {"cms": "leer"}
    try:
        ci = acms.ContentInfo.load(raw)
        sd = ci["content"]
        certs = []
        for c in sd["certificates"] or []:
            cert = c.chosen
            subj = cert.subject.native
            certs.append({"cn": subj.get("common_name"), "ou": subj.get("organizational_unit_name")})
        si = sd["signer_infos"][0]
        algo = si["digest_algorithm"]["algorithm"].native
        attrs = {a["type"].native: a for a in si["signed_attrs"]} if si["signed_attrs"] else {}
        md = attrs.get("message_digest")
        md_val = md["values"][0].native if md else None
        st = attrs.get("signing_time")
        st_val = str(st["values"][0].native) if st else None
        unsigned = [a["type"].dotted for a in si["unsigned_attrs"]] if si["unsigned_attrs"] else []
        digest_ok = None
        if md_val is not None and cd_raw is not None:
            digest_ok = hashlib.new(algo.replace("sha", "sha"), cd_raw).digest() == md_val
        return {
            "cms": "ja",
            "certs": certs,
            "digest": algo,
            "digest_matches_cd0": digest_ok,
            "signing_time": st_val,
            "timestamp_token": "1.2.840.113549.1.9.16.2.14" in unsigned,
        }
    except Exception as exc:  # noqa: BLE001
        if len(raw) < 16:
            return {"cms": f"leer ({len(raw)} Byte)"}
        return {"cms": f"Fehler {exc}"}


def main() -> None:
    src, prefix = sys.argv[1], sys.argv[2]
    zf = zipfile.ZipFile(src)
    files: dict[str, bytes | None] = {}
    links: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for info in zf.infolist():
        name = info.filename
        if name.startswith("__MACOSX/") or name.endswith("/"):
            continue
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            links[name] = zf.read(info).decode()
        else:
            files[name] = None
            sizes[name] = info.file_size

    app_root = next(n.split("/")[0] for n in files)  # Solidon3D.app

    def resolve(path: str, depth: int = 0) -> str | None:
        """Löst Symlinks innerhalb des Zips auf (auch in Zwischenverzeichnissen)."""
        if depth > 40:
            return None
        parts = path.split("/")
        cur = ""
        for i, p in enumerate(parts):
            cur = p if not cur else f"{cur}/{p}"
            if cur in links:
                target = links[cur]
                base = posixpath.dirname(cur)
                new = posixpath.normpath(posixpath.join(base, target))
                rest = "/".join(parts[i + 1 :])
                full = f"{new}/{rest}" if rest else new
                return resolve(full, depth + 1)
        return cur

    def exists(path: str) -> bool:
        r = resolve(path)
        if r is None:
            return False
        if r in files:
            return True
        return any(f.startswith(r + "/") for f in files)

    results = []
    with_sig_err = []
    for name in sorted(files):
        with zf.open(name) as fh:
            head = fh.read(8)
        if head[:4] not in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf", b"\xce\xfa\xed\xfe"):
            continue
        data = zf.read(name)
        rec: dict = {"path": name, "size": len(data), "slices": []}
        try:
            slices = macho.parse_macho(data)
        except Exception as exc:  # noqa: BLE001
            rec["error"] = str(exc)
            results.append(rec)
            continue
        for sl in slices:
            s: dict = {
                "arch": sl.arch,
                "filetype": sl.filetype,
                "minos": sl.minos,
                "sdk": sl.sdk,
                "min_cmd": sl.min_cmd or ("LC_BUILD_VERSION" if sl.minos else None),
                "build_platform": sl.build_platform,
                "dylibs": sl.dylibs,
                "rpaths": sl.rpaths,
                "id": sl.id_dylib,
            }
            sig = sl.signature
            if sig is None:
                s["signature"] = None
            elif sig.error:
                s["signature"] = {"error": sig.error}
            else:
                cds = []
                for cd in sig.cds:
                    ok, total, bad = macho.verify_pages(data, sl, cd)
                    cds.append(
                        {
                            "slot": hex(cd.slot),
                            "version": hex(cd.version),
                            "flags": hex(cd.flags),
                            "flag_names": cd.flag_names,
                            "hash": macho.HASH_TYPES[cd.hash_type][0],
                            "team": cd.team_id,
                            "ident": cd.identifier,
                            "pages_ok": ok,
                            "pages": total,
                            "bad_pages": bad[:10],
                            "code_limit": cd.code_limit,
                            "slice_size": sl.size,
                            "special": macho.verify_special(sig, cd),
                            "runtime_version": macho.ver(cd.runtime_version) if cd.runtime_version else None,
                            "exec_seg_flags": hex(cd.exec_seg_flags) if cd.exec_seg_flags is not None else None,
                            "cdhash": cd.cdhash(),
                            "n_special": cd.n_special,
                        }
                    )
                cd0 = sig.blobs.get(0)
                s["signature"] = {
                    "size": sig.size,
                    "blob_types": sorted(hex(t) for t in sig.blobs),
                    "cds": cds,
                    "entitlements_xml": sig.entitlements_xml.decode("utf-8", "replace") if sig.entitlements_xml else None,
                    "entitlements_der_b64": base64.b64encode(sig.entitlements_der).decode() if sig.entitlements_der else None,
                    "cms": cms_info(sig.cms, cd0),
                    "sig_ends_at_slice_end": sig.offset + sig.size <= sl.size,
                }
            # Abhängigkeiten auflösen
            missing = []
            exe_dir = posixpath.dirname(name)
            for kind, dep in sl.dylibs:
                if dep.startswith("/System/") or dep.startswith("/usr/lib/"):
                    continue
                cands = []
                if dep.startswith("@rpath/"):
                    tail = dep[len("@rpath/") :]
                    for rp in sl.rpaths:
                        rp2 = rp.replace("@loader_path", exe_dir).replace(
                            "@executable_path", f"{app_root}/Contents/MacOS"
                        )
                        cands.append(posixpath.normpath(posixpath.join(rp2, tail)))
                elif dep.startswith("@loader_path/"):
                    cands.append(posixpath.normpath(posixpath.join(exe_dir, dep[len("@loader_path/") :])))
                elif dep.startswith("@executable_path/"):
                    cands.append(
                        posixpath.normpath(posixpath.join(f"{app_root}/Contents/MacOS", dep[len("@executable_path/") :]))
                    )
                else:
                    cands.append(dep)
                found = [c for c in cands if exists(c)]
                if not found:
                    missing.append({"kind": kind, "dep": dep, "tried": cands})
            s["missing_deps"] = missing
            rec["slices"].append(s)
        results.append(rec)

    # CodeResources des Hauptbundles
    cr_path = f"{app_root}/Contents/_CodeSignature/CodeResources"
    cr_report: dict = {}
    if cr_path in files:
        cr = plistlib.loads(zf.read(cr_path))
        files2 = cr.get("files2", {})
        bad, ok, nested_ok, nested_bad, link_ok, link_bad, missing_in_zip = [], 0, 0, [], 0, [], []
        by_cdhash = {}
        for r in results:
            for s in r.get("slices", []):
                pass
        for rel, ent in files2.items():
            full = f"{app_root}/Contents/{rel}"
            if isinstance(ent, dict) and "symlink" in ent:
                if links.get(full) == ent["symlink"]:
                    link_ok += 1
                else:
                    link_bad.append((rel, ent["symlink"], links.get(full)))
                continue
            if isinstance(ent, dict) and "cdhash" in ent:
                # verschachtelter Code: cdhash gegen die Datei
                target = full
                if target not in files:
                    # Bundle (Framework) -> Hauptprogramm suchen
                    missing_in_zip.append(rel)
                    continue
                d = zf.read(target)
                try:
                    sls = macho.parse_macho(d)
                except Exception:  # noqa: BLE001
                    nested_bad.append((rel, "kein Mach-O"))
                    continue
                want = ent["cdhash"].hex()
                have = set()
                for sl in sls:
                    if sl.signature:
                        for cd in sl.signature.cds:
                            have.add(cd.cdhash())
                if want in have:
                    nested_ok += 1
                else:
                    nested_bad.append((rel, want, sorted(have)))
                continue
            h = ent.get("hash2") if isinstance(ent, dict) else None
            if h is None:
                continue
            if full not in files:
                missing_in_zip.append(rel)
                continue
            got = hashlib.sha256(zf.read(full)).digest()
            if got == h:
                ok += 1
            else:
                bad.append(rel)
        # Dateien, die gar nicht versiegelt sind
        sealed = {f"{app_root}/Contents/{k}" for k in files2}
        unsealed = []
        for f in list(files) + list(links):
            if f.startswith(f"{app_root}/Contents/_CodeSignature/") or f == f"{app_root}/Contents/Info.plist":
                continue
            if f == f"{app_root}/Contents/MacOS/Solidon3D":
                continue
            if f in sealed:
                continue
            # in einem verschachtelten Bundle versiegelt?
            if any(f.startswith(s.rsplit("/Versions/", 1)[0] + "/") for s in sealed if ".framework/" in s):
                continue
            unsealed.append(f)
        cr_report = {
            "files2": len(files2),
            "hash_ok": ok,
            "hash_bad": bad,
            "nested_ok": nested_ok,
            "nested_bad": nested_bad,
            "symlink_ok": link_ok,
            "symlink_bad": link_bad,
            "listed_but_missing": missing_in_zip,
            "unsealed_sample": unsealed[:50],
            "unsealed_count": len(unsealed),
            "rules2_keys": list(cr.get("rules2", {}).keys()),
        }
    # Info.plist
    info = plistlib.loads(zf.read(f"{app_root}/Contents/Info.plist"))
    main_exe = f"{app_root}/Contents/MacOS/{info.get('CFBundleExecutable')}"
    main_check = {}
    if main_exe in files:
        d = zf.read(main_exe)
        for sl in macho.parse_macho(d):
            for cd in sl.signature.cds:
                name_, size_ = macho.HASH_TYPES[cd.hash_type]
                ip = hashlib.new(name_, zf.read(f"{app_root}/Contents/Info.plist")).digest()[:size_]
                crh = hashlib.new(name_, zf.read(cr_path)).digest()[:size_] if cr_path in files else None
                main_check[f"{sl.arch}/{name_}"] = {
                    "info_plist_slot": "ok" if cd.special_hash(1) == ip else "FALSCH",
                    "coderesources_slot": "ok" if cd.special_hash(3) == crh else "FALSCH",
                }

    out = {
        "zip": src,
        "app_root": app_root,
        "n_files": len(files),
        "n_links": len(links),
        "info_plist": {k: (v if not isinstance(v, bytes) else v.hex()) for k, v in info.items()},
        "main_exe_special_slots": main_check,
        "coderesources": cr_report,
        "macho": results,
    }
    Path(prefix + ".json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(f"Mach-O: {len(results)}  Symlinks: {len(links)}  Dateien: {len(files)}")


if __name__ == "__main__":
    main()
