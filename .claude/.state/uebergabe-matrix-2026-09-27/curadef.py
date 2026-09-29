import json, sys, pathlib
R = pathlib.Path(r"C:\Program Files\UltiMaker Cura 5.13.0\share\cura\resources")
D = R / "definitions"
E = R / "extruders"

def flatten(settings, out):
    for k, v in settings.items():
        if not isinstance(v, dict):
            continue
        out.setdefault(k, {}).update({kk: vv for kk, vv in v.items() if kk != "children"})
        if "children" in v:
            flatten(v["children"], out)

def chain(name, folder=D):
    p = folder / f"{name}.def.json"
    if not p.exists():
        p = D / f"{name}.def.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    levels = []
    if "inherits" in doc:
        levels = chain(doc["inherits"], folder)
    own = {}
    flatten(doc.get("settings", {}), own)
    for k, v in doc.get("overrides", {}).items():
        own.setdefault(k, {}).update(v)
    levels.append((name, own, doc.get("metadata", {})))
    return levels

def resolved(name, keys, folder=D):
    levels = chain(name, folder)
    res = {}
    for k in keys:
        trail = []
        for lvl, own, _ in levels:
            if k in own:
                d = own[k]
                bits = []
                if "default_value" in d: bits.append(f"dv={d['default_value']!r}")
                if "value" in d: bits.append(f"value={d['value']!r}")
                if "enabled" in d and lvl != "fdmprinter": bits.append(f"enabled={d['enabled']!r}")
                if "maximum_value" in d and lvl != "fdmprinter": bits.append(f"max={d['maximum_value']!r}")
                if bits: trail.append(f"{lvl}: " + ", ".join(bits))
        res[k] = trail
    return res, levels

if __name__ == "__main__":
    name = sys.argv[1]
    keys = sys.argv[2].split(",")
    res, levels = resolved(name, keys)
    print("chain:", " -> ".join(l[0] for l in levels))
    md = {}
    for _, _, m in levels: md.update(m)
    for mk in ("quality_definition","preferred_quality_type","preferred_material","preferred_variant_name","has_variants","has_materials","machine_extruder_trains","exclude_materials"):
        if mk in md: 
            v = md[mk]
            if isinstance(v, list): v = f"list[{len(v)}]"
            print(f"  meta {mk} = {v}")
    for k, t in res.items():
        print(f"{k}:")
        for x in t: print("    ", x)
