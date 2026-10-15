"""Fasst isa_scan-Ergebnisse zusammen. Aufruf: python -I isa_auswerten.py <isa.json>"""

import json
import re
import sys

MARKERS = re.compile(
    r"(X86_V4|AVX512|avx512|_SKX|SKYLAKEX|skylakex|COOPERLAKE|SAPPHIRERAPIDS|_ICL|_KNL|knl|AVX512F|avx3|AVX3|"
    r"_V4\b|zen4|ZEN4|cooperlake|sapphire|icelake|ICELAKE|_avx512|Avx512|SPR_|spr_|_x86_v4|vbmi|VBMI|vnni|VNNI|"
    r"bf16|BF16|fp16|FP16|AMX|amx)"
)
BAD = ["avx512", "evex", "sha", "fma4", "xop", "tbm", "sse4a", "gfni", "vaes256", "vpclmul256", "avxvnni",
       "rdpid", "clwb", "movdir", "serialize", "waitpkg", "amx", "rex2", "avxifma", "pconfig", "wbnoinvd",
       "enqcmd", "cldemote", "ptwrite"]


def main() -> None:
    res = json.load(open(sys.argv[1], encoding="utf-8"))
    rows = []
    tot_insn = tot_bytes = 0
    for r in res:
        for s in r.get("slices", []):
            tot_insn += s["insns"]
            tot_bytes += s["text_bytes"]
            c, f = s["counts"], s["funcs"]
            bad = {k: c[k] for k in BAD if c.get(k)}
            v3f = s["funcs_v3_any"]
            nf = max(s["n_funcs"], 1)
            rows.append((r["path"], r["size"], s, bad, v3f / nf))
    print(f"Dateien: {len(rows)}  Befehle: {tot_insn:,}  Code-Bytes: {tot_bytes:,}")
    print()
    print("== Dateien mit Befehlen, die Coffee Lake nicht kann ==")
    for path, size, s, bad, frac in sorted(rows, key=lambda x: -sum(x[3].values())):
        if not bad:
            continue
        names = set()
        for k in bad:
            names.update(s["func_names"].get(k, []))
        unmarked = sorted(n for n in names if not MARKERS.search(n))
        cpuid = s["counts"].get("cpuid", 0)
        print(f"- {path.replace('Solidon3D.app/Contents/', '')} ({size/1e6:.1f} MB)")
        print(f"    {bad}  Funktionen: { {k: s['funcs'].get(k) for k in bad} } von {s['n_funcs']}; cpuid={cpuid} xgetbv={s['counts'].get('xgetbv', 0)}")
        print(f"    Funktionen mit Kennung (V4/AVX512/SKX…): {len(names) - len(unmarked)}, ohne Kennung: {len(unmarked)}")
        for n in unmarked[:40]:
            print("       ohne Kennung:", n)
        if s["func_names"].get("cpuid"):
            print("    cpuid in:", s["func_names"]["cpuid"][:8])
    print()
    print("== Verbreitung AVX2/FMA/BMI (x86-64-v3) — größte Anteile an Funktionen ==")
    for path, size, s, bad, frac in sorted(rows, key=lambda x: -x[4])[:40]:
        c = s["counts"]
        if not (c.get("avx2") or c.get("fma") or c.get("bmi2") or c.get("bmi1")):
            continue
        print(
            f"  {frac*100:5.1f}% von {s['n_funcs']:6d} Fkt  avx2={c.get('avx2',0):6d} fma={c.get('fma',0):6d} "
            f"bmi1={c.get('bmi1',0):5d} bmi2={c.get('bmi2',0):5d} avx={c.get('avx',0):6d} cpuid={c.get('cpuid',0)}  "
            f"{path.replace('Solidon3D.app/Contents/', '')}"
        )
    print()
    print("== Große Bibliotheken (>1 MB) im Überblick ==")
    for path, size, s, bad, frac in sorted(rows, key=lambda x: -x[1]):
        if size < 1_000_000:
            continue
        c = s["counts"]
        print(
            f"  {size/1e6:6.1f} MB  insn={s['insns']:9,d} skip={s['skipped_bytes']:6d}  avx512={c.get('avx512',0):6d} "
            f"avx2={c.get('avx2',0):6d} fma={c.get('fma',0):6d} bmi2={c.get('bmi2',0):5d} v3-Fkt={frac*100:4.1f}%  "
            f"cpuid={c.get('cpuid',0)}  {path.replace('Solidon3D.app/Contents/', '')}"
        )


if __name__ == "__main__":
    main()
