"""Die echte Ebenenabsage einer Skizzenoperation, für Kern- und Fensterprüfung (FD-182).

Eigenes kleines Modul, weil zwei Testdateien sie brauchen: der Kernfall
(`test_plane_refusal_field.py`) und der Dialogfall
(`test_refusal_field_ways_window.py`). Aus einer Testdatei geholt, zöge sie
deren Abhängigkeiten in die Auswahl der anderen (`tests.md`).
"""

from __future__ import annotations

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.sketch.serialize import sketch_to_text
from app.core.types import OpContext, Scene, Sketch, SketchElement

#: Drei Punkte auf einer Geraden: eine Ebene, die sich nicht lesen lässt.
UNREADABLE_PLANE = "through:0,0,20;10,0,20;20,0,20"


def square_on(plane: str) -> str:
    """Ein Quadrat von zehn Millimetern als Skizzentext auf ``plane``."""
    return sketch_to_text(
        Sketch(
            plane=plane,
            elements=(
                SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
                SketchElement(kind="line", points=((10.0, 0.0), (10.0, 10.0))),
                SketchElement(kind="line", points=((10.0, 10.0), (0.0, 10.0))),
                SketchElement(kind="line", points=((0.0, 10.0), (0.0, 0.0))),
            ),
            constraints=(),
        )
    )


def sketch_plane_refusal(plane: str) -> ValidationError:
    """Was *Skizze extrudieren* auf ``plane`` absagt — ein Quadrat, vier Millimeter hoch."""
    load_operations()
    sketch = square_on(plane)
    spec = REGISTRY.get("sketch_extrude")
    try:
        spec.fn(
            OpContext(
                scene=Scene(objects={}, parameters={}),
                inputs=[],
                params=spec.params(sketch=sketch, height=4.0),
                profile=None,
                quality="fine",
                seed=None,
                progress=lambda fraction, text: None,
                ask=lambda question, choices: choices[0],
                cancelled=NeverCancelled(),
            )
        )
    except ValidationError as refusal:
        return refusal
    raise AssertionError(f"Voraussetzung: {plane!r} wird abgesagt")
