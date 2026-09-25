import pickle, sys, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
S = r"C:\Users\rober\AppData\Local\Temp\claude\F--3D-Druck\5a618bfd-281d-49da-a2e6-53d607465f68\scratchpad"
run = sys.argv[1]
layers = pickle.load(open(S + f"\{run}\layers.pkl", "rb"))
colors = {"Support": "#e8590c", "Support interface": "#f59f00", "Outer wall": "#1c7ed6", "Inner wall": "#74c0fc", "Skirt": "#aaa", "Bottom surface": "#2f9e44", "Internal solid infill": "#8ce99a", "Brim": "#862e9c", "Gap infill": "#555", "Overhang wall": "#364fc7", "Bridge": "#c2255c", "Sparse infill": "#ddd"}
fig, axes = plt.subplots(1, 3, figsize=(30, 10))
for i, ax in enumerate(axes):
    L = layers[i]
    total = {k: float(np.hypot(v[:,2]-v[:,0], v[:,3]-v[:,1]).sum()) for k, v in L["seg"].items()}
    tr = L["travel"]; tl = np.hypot(tr[:,2]-tr[:,0], tr[:,3]-tr[:,1]) if len(tr) else np.zeros(0)
    print(f"Schicht {i+1} z={L['z']}: " + ", ".join(f"{k} {v:.0f} mm" for k, v in sorted(total.items(), key=lambda t: -t[1])))
    print(f"   Leerfahrten: {len(tl)}, davon > 2 mm: {(tl > 2).sum()}, Summe {tl.sum():.0f} mm")
    for k, v in L["seg"].items():
        for s in v: ax.plot([s[0], s[2]], [s[1], s[3]], color=colors.get(k, "k"), lw=0.5)
    ax.set_aspect("equal"); ax.set_title(f"Schicht {i+1} (z={L['z']})"); ax.set_xlim(0, 256); ax.set_ylim(0, 256)
from matplotlib.lines import Line2D
axes[0].legend([Line2D([0], [0], color=c, lw=3) for c in colors.values()], colors.keys(), loc="upper left", fontsize=8)
plt.tight_layout(); plt.savefig(S + f"\{run}\erste_schichten.png", dpi=55)
