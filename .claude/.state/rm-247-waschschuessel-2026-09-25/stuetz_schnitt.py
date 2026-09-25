"""Stützbahnen in Scheiben zusammen mit dem Modellschnitt zeichnen."""
import pickle, sys, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
S = r"C:\Users\rober\AppData\Local\Temp\claude\F--3D-Druck\5a618bfd-281d-49da-a2e6-53d607465f68\scratchpad"
run = sys.argv[1]
layers = pickle.load(open(S + "\\" + run + "\layers.pkl", "rb"))
m = trimesh.load(S + r"\out\bowl_washing_bowl_v1.stl"); m.apply_translation([128, 128, 0])
pts = []
for L in layers:
    for k in ("Support", "Support interface"):
        v = L["seg"].get(k)
        if v is None: continue
        # Punkte entlang der Bahnen alle 1 mm
        for x0, y0, x1, y1, _ in v:
            n = max(1, int(np.hypot(x1 - x0, y1 - y0)))
            t = np.linspace(0, 1, n + 1)
            pts.append(np.column_stack([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, np.full(n + 1, L["z"])]))
P = np.vstack(pts)
print("Stützpunkte", len(P))
# Scheiben: y = const (Normale Y) und x = const
cuts = [("y", 128), ("y", 95), ("x", 128), ("x", 200)]
fig, axes = plt.subplots(2, 2, figsize=(22, 13))
for ax, (axis, val) in zip(axes.flat, cuts):
    i = 1 if axis == "y" else 0; j = 0 if axis == "y" else 1
    normal = [0, 0, 0]; normal[i] = 1; origin = [0, 0, 0]; origin[i] = val
    sec = m.section(plane_origin=origin, plane_normal=normal)
    if sec is not None:
        for e in sec.entities:
            q = sec.vertices[e.points]; ax.fill(q[:, j], q[:, 2], color="#5b8fd9", alpha=.35, lw=0); ax.plot(q[:, j], q[:, 2], color="#1c4f9c", lw=.7)
    sel = np.abs(P[:, i] - val) < 0.7
    ax.scatter(P[sel, j], P[sel, 2], s=1.2, color="#e8590c")
    ax.set_aspect("equal"); ax.set_title(f"Scheibe {axis} = {val} mm: Modell blau, Stütze orange"); ax.grid(alpha=.3)
plt.tight_layout(); plt.savefig(S + "\\" + run + "\stuetz_schnitt.png", dpi=60)
