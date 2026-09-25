"""Übergabe-3MF mit geänderten Werten neu schreiben, schneiden, auswerten.

python variante.py <name> key=value ...   (value als JSON, sonst Text; Listen bleiben Listen)
"""
import json, sys, zipfile, subprocess, pickle, os, re, numpy as np
S = r"C:\Users\rober\AppData\Local\Temp\claude\F--3D-Druck\5a618bfd-281d-49da-a2e6-53d607465f68\scratchpad"
sys.path.insert(0, S)
from gcode_lesen import read
name = sys.argv[1]
over = {}
for arg in sys.argv[2:]:
    k, v = arg.split("=", 1)
    over[k] = v
src = zipfile.ZipFile(S + r"\uebergabe.3mf")
cfg = json.loads(src.read("Metadata/project_settings.config"))
if over.pop("__elegoo", None):
    cfg.update(json.load(open(S + r"\elegoo_ref.json", encoding="utf-8")))
for k, v in over.items():
    cfg[k] = [v] if isinstance(cfg.get(k), list) else v
out_dir = os.path.join(S, name); os.makedirs(out_dir, exist_ok=True)
target = os.path.join(out_dir, "in.3mf")
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as dst:
    for item in src.infolist():
        data = src.read(item.filename)
        if item.filename == "Metadata/project_settings.config":
            data = json.dumps(cfg, indent=1).encode()
        dst.writestr(item, data)
r = subprocess.run([r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe", "--arrange", "0", "--slice", "0", "--outputdir", out_dir, target], capture_output=True, text=True)
print(name, "Slicer-Exit", r.returncode)
g = os.path.join(out_dir, "plate_1.gcode")
text = open(g, encoding="utf-8", errors="replace").read()
def head(key):
    m = re.search(r"^; " + re.escape(key) + r" = (.*)$", text, re.M); return m.group(1) if m else "?"
layers = read(g); pickle.dump(layers, open(os.path.join(out_dir, "layers.pkl"), "wb"))
def length(L, keys):
    return sum(float(np.hypot(v[:, 2] - v[:, 0], v[:, 3] - v[:, 1]).sum()) for k, v in L["seg"].items() if k in keys)
sup = ("Support", "Support interface", "Support transition")
tot_sup = sum(length(L, sup) for L in layers)
print(f"  Zeit {head('estimated printing time (normal mode)')}, Filament {head('filament used [g]')} g, Stützbahn gesamt {tot_sup/1000:.0f} m")
for i in range(3):
    L = layers[i]; tr = L["travel"]; tl = np.hypot(tr[:, 2] - tr[:, 0], tr[:, 3] - tr[:, 1]) if len(tr) else np.zeros(0)
    print(f"  Schicht {i+1}: Stütze {length(L, sup):.0f} mm, Modell {length(L, set(L['seg']) - set(sup) - {'Skirt', 'Brim'}):.0f} mm, Leerfahrten {len(tl)} (>2 mm: {(tl>2).sum()})")
# Stütze in der Kugelkammer: Kugel um die Kammer (aus dem Schnittbild ~ x 196, y 195, z 53, r 22)
pts = []
for L in layers:
    for k in sup:
        v = L["seg"].get(k)
        if v is not None:
            mid = np.column_stack([(v[:, 0] + v[:, 2]) / 2, (v[:, 1] + v[:, 3]) / 2, np.full(len(v), L["z"])])
            pts.append(np.column_stack([mid, np.hypot(v[:, 2] - v[:, 0], v[:, 3] - v[:, 1])]))
P = np.vstack(pts) if pts else np.zeros((0, 4))
cham = json.load(open(S + r"\kammer.json")) if os.path.exists(S + r"\kammer.json") else None
if cham:
    d = np.linalg.norm(P[:, :3] - np.array(cham["c"]), axis=1)
    print(f"  Stütze in der Kammer: {P[d < cham['r'] - 1, 3].sum():.0f} mm Bahn")
