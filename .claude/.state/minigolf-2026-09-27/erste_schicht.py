"""Die ersten Schichten einer Druckdatei als Bild: Bahnen je Art, Leerfahrten gezählt.

Aufruf: python erste_schicht.py <plate.gcode> <bild.png> [schichten=2] [x0 x1 y0 y1]
Liest die Orca-Familie (``;TYPE:``/``; FEATURE:``, ``;LAYER_CHANGE``, ``;Z:``).
"""
# ruff: noqa: E501

import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

NUMBER = re.compile(r"([XYZEF])(-?(?:\d+\.?\d*|\.\d+))")
COLOURS = {
    "Outer wall": "#1c7ed6",
    "Inner wall": "#74c0fc",
    "Overhang wall": "#364fc7",
    "Bottom surface": "#2f9e44",
    "Internal solid infill": "#8ce99a",
    "Top surface": "#e03131",
    "Gap infill": "#000000",
    "Sparse infill": "#bbbbbb",
    "Brim": "#862e9c",
    "Skirt": "#aaaaaa",
    "Support": "#e8590c",
    "Support interface": "#f59f00",
    "Bridge": "#c2255c",
    "Internal Bridge": "#c2255c",
    "Custom": "#ff00ff",
}


def read(path: Path, wanted: int) -> list[dict]:
    layers: list[dict] = []
    kind = "?"
    x = y = 0.0
    absolute = True
    last_e = 0.0
    current: dict | None = None
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(";"):
                if line.startswith((";TYPE:", "; FEATURE:")):
                    kind = line.split(":", 1)[1].strip()
                elif line.startswith(";LAYER_CHANGE"):
                    if len(layers) == wanted:
                        break
                    current = {"z": None, "seg": {}, "travel": [], "width": {}}
                    layers.append(current)
                elif line.startswith(";Z:") and current is not None and current["z"] is None:
                    current["z"] = float(line[3:])
                elif line.startswith(";WIDTH:") and current is not None:
                    current["last_width"] = float(line[7:])
                continue
            if line.startswith("M83"):
                absolute = False
                continue
            if line.startswith("M82"):
                absolute = True
                continue
            if line.startswith("G92"):
                found = dict(NUMBER.findall(line.split(";")[0]))
                if "E" in found:
                    last_e = float(found["E"])
                continue
            if not line.startswith(("G1 ", "G0 ", "G2", "G3")):
                continue
            values = dict(NUMBER.findall(line.split(";")[0]))
            nx, ny = float(values.get("X", x)), float(values.get("Y", y))
            pushed = 0.0
            if "E" in values:
                e = float(values["E"])
                pushed = (e - last_e) if absolute else e
                if absolute:
                    last_e = e
            if current is not None and (nx != x or ny != y):
                if pushed > 0:
                    current["seg"].setdefault(kind, []).append((x, y, nx, ny))
                    current["width"].setdefault(kind, []).append(current.get("last_width", 0.0))
                else:
                    current["travel"].append((x, y, nx, ny))
            x, y = nx, ny
    return layers


def main() -> int:
    gcode = Path(sys.argv[1])
    image = Path(sys.argv[2])
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    window = [float(v) for v in sys.argv[4:8]] if len(sys.argv) >= 8 else None
    layers = read(gcode, count)
    fig, axes = plt.subplots(1, count, figsize=(16 * count, 16))
    axes = np.atleast_1d(axes)
    for number, (ax, layer) in enumerate(zip(axes, layers)):
        total = {k: float(np.hypot(*(np.asarray(v)[:, 2:] - np.asarray(v)[:, :2]).T).sum()) for k, v in layer["seg"].items()}
        travel = np.asarray(layer["travel"]) if layer["travel"] else np.zeros((0, 4))
        lengths = np.hypot(travel[:, 2] - travel[:, 0], travel[:, 3] - travel[:, 1]) if len(travel) else np.zeros(0)
        print(f"Schicht {number + 1} z={layer['z']}: " + ", ".join(f"{k} {v:.0f} mm" for k, v in sorted(total.items(), key=lambda t: -t[1])))
        print(f"   Leerfahrten {len(lengths)}, davon > 2 mm: {(lengths > 2).sum()}")
        for kind, segments in layer["seg"].items():
            seg = np.asarray(segments)
            widths = np.asarray(layer["width"][kind])
            short = np.hypot(seg[:, 2] - seg[:, 0], seg[:, 3] - seg[:, 1])
            print(f"   {kind:24s} Segmente {len(seg):6d}, kürzer als 1 mm: {(short < 1).sum():6d}, Breite {widths.min():.3f}..{widths.max():.3f}")
            for s, w in zip(seg, widths):
                ax.plot([s[0], s[2]], [s[1], s[3]], color=COLOURS.get(kind, "#ff0000"), lw=max(0.4, w * 4))
        ax.set_aspect("equal")
        ax.set_title(f"Schicht {number + 1} (z={layer['z']})")
        if window:
            ax.set_xlim(window[0], window[1])
            ax.set_ylim(window[2], window[3])
        else:
            ax.set_xlim(0, 256)
            ax.set_ylim(0, 256)
    plt.tight_layout()
    plt.savefig(image, dpi=40 if not window else 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
