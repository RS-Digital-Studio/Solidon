"""(ii) am exakten Kern: nach einer Absage bauen, was sich bauen lässt (einmaliges Umbauskript)."""

import io
import sys
from pathlib import Path

TREE = sys.argv[1]
path = TREE + "/app/core/geom/edge_ops.py"
text = io.open(path, encoding="utf-8", newline="").read()
parts = Path(__file__).with_name("faedeln_ii_bau.txt").read_text(encoding="utf-8").split("=====\n")


def swap(old: str, new: str) -> None:
    global text
    found = text.count(old)
    assert found == 1, (old[:70], found)
    text = text.replace(old, new)


for index in range(0, len(parts) - 1, 2):
    swap(parts[index], parts[index + 1])
io.open(path, "w", encoding="utf-8", newline="").write(text)
print("ok")
