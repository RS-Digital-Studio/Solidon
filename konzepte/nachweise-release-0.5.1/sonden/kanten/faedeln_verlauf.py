"""Ersetzt ``_swept_tool`` durch die Fassung mit Radiusverlauf (einmaliges Umbauskript)."""

import io
import sys
from pathlib import Path

TREE = sys.argv[1]
path = TREE + "/app/core/geom/edges.py"
new = Path(__file__).with_name("swept_tool.txt").read_text(encoding="utf-8")
text = io.open(path, encoding="utf-8", newline="").read()
start = text.index("def _swept_tool(")
end = text.index("def _tube(sections: list[np.ndarray]) -> MeshData | None:")
text = text[:start] + new + text[end:]
old = """        if law is not None:
            tool = _varying_tool(entry, law, quality=quality, cancelled=cancelled)
"""
assert text.count(old) == 1
text = text.replace(
    old,
    """        if law is not None:
            tool = _swept_tool(
                entry,
                law.largest,
                True,
                subtracted=entry.convex,
                min_steps=0,
                flank_overlap=BOOLEAN_OVERLAP if entry.convex else 0.0,
                law=law,
            ) or _varying_tool(entry, law, quality=quality, cancelled=cancelled)
""",
)
io.open(path, "w", encoding="utf-8", newline="").write(text)
print("ok")
