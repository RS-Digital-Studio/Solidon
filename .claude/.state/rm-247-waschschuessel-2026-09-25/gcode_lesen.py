"""G-Code der Orca-Familie in Segmente je Schicht und Typ zerlegen (für Auswertungen)."""
import re, sys, pickle, numpy as np
def read(path):
    layers = []  # (z, {type: [(x0,y0,x1,y1,e)]}, travels)
    z = 0.0; typ = None; x = y = 0.0; cur = None; absolute_e = False
    num = re.compile(r"([XYZEF])(-?[\d.]+)")
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith(";Z:"):
                z = float(line[3:]); cur = {"z": z, "seg": {}, "travel": []}; layers.append(cur); continue
            if line.startswith(";TYPE:"):
                typ = line[6:].strip(); continue
            if line.startswith("G1") or line.startswith("G0"):
                vals = dict((k, float(v)) for k, v in num.findall(line.split(";")[0]))
                nx, ny = vals.get("X", x), vals.get("Y", y)
                if cur is not None and ("X" in vals or "Y" in vals):
                    e = vals.get("E", 0.0)
                    if e > 0 and typ:
                        cur["seg"].setdefault(typ, []).append((x, y, nx, ny, e))
                    elif e <= 0:
                        cur["travel"].append((x, y, nx, ny))
                x, y = nx, ny
    for L in layers:
        L["seg"] = {k: np.array(v) for k, v in L["seg"].items()}
        L["travel"] = np.array(L["travel"]) if L["travel"] else np.zeros((0, 4))
    return layers
if __name__ == "__main__":
    layers = read(sys.argv[1])
    pickle.dump(layers, open(sys.argv[2], "wb"))
    print(len(layers), "Schichten")
