"""Die erste Schicht zweier Druckdateien nebeneinander, mit eigenen Titeln.

Aufruf: python erste_schicht.py <links.gcode> <titel> <rechts.gcode> <titel> <bild.png>
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
left, left_title, right, right_title, target = sys.argv[1:6]
sys.argv = [sys.argv[0], r"F:\3D Druck.minigolf", left, tempfile.mkdtemp()]
sys.path.insert(0, r"F:\3D Druck.minigolf")
import lauf  # noqa: E402  (liest seine Argumente beim Import)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

BED = (256.0, 256.0)
COLOURS = {"model": "#1c7ed6", "support": "#e8590c", "rim": "#862e9c", "other": "#aaaaaa"}
NAMES = {"model": "Modell", "support": "Stütze", "rim": "Rand (Brim/Skirt)", "other": "Sonstiges"}

fig, axes = plt.subplots(1, 2, figsize=(16, 8))
for ax, path, title in ((axes[0], left, left_title), (axes[1], right, right_title)):
    segments = lauf.first_layer_segments(Path(path))
    for kind, lines in segments.items():
        for x0, y0, x1, y1 in lines:
            ax.plot([x0, x1], [y0, y1], color=COLOURS[kind], lw=0.6)
    lengths = {
        kind: sum(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 for x0, y0, x1, y1 in lines) / 1000.0
        for kind, lines in segments.items()
    }
    summary = ", ".join(f"{NAMES[k]} {v:.1f} m" for k, v in lengths.items() if v > 0.0)
    ax.set_aspect("equal")
    ax.set_xlim(0, BED[0])
    ax.set_ylim(0, BED[1])
    ax.set_title(f"{title}\nSchicht 1: {summary}")
fig.legend(
    handles=[Line2D([0], [0], color=COLOURS[k], lw=3, label=NAMES[k]) for k in ("model", "support", "rim")],
    loc="lower center",
    ncol=3,
)
plt.tight_layout(rect=(0, 0.05, 1, 0.97))
plt.savefig(target, dpi=70)
plt.close(fig)
print(target)
