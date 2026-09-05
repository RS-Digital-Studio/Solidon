"""Welcher Renderer die Ansicht zeichnet — und ob er hier kann (§18).

Zwei Renderer stehen hinter dem Vertrag aus :mod:`app.ui.render.api`, und
beide werden gemessen (Entscheidung Robert, 05.09.2026). Solange die Messung
läuft, wählt die Umgebungsvariable ``SOLIDON_RENDERER``: ``vtk`` (Vorgabe)
oder ``gfx``. Eine Einstellung in der Oberfläche gibt es absichtlich nicht —
ein Kunde soll nie vor der Frage stehen, welche Grafikbibliothek er möchte;
die Entscheidung fällt einmal, hier im Code.

Alles, was einen Renderer baut, geht über :func:`make_renderer` — der
Viewport, seine Bildaufnahme und die Ansichten für den Agenten —, damit ein
Wechsel an genau einer Stelle stattfindet.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any, Literal

from app.ui.render.api import Renderer

_log = logging.getLogger(__name__)

#: Die Umgebungsvariable, die den Renderer wählt.
RENDERER_VARIABLE = "SOLIDON_RENDERER"

Backend = Literal["vtk", "gfx"]

#: Was die Variable alles heißen darf, je Renderer.
_NAMES: dict[str, Backend] = {
    "vtk": "vtk",
    "gfx": "gfx",
    "pygfx": "gfx",
    "wgpu": "gfx",
}


def backend(environ: Mapping[str, str] | None = None) -> Backend:
    """Der gewählte Renderer — ``vtk``, solange niemand etwas anderes sagt.

    Ein unbekannter Wert fällt auf VTK zurück und sagt es im Protokoll: Ein
    Tippfehler soll die Ansicht nicht kosten, aber auch nicht still bleiben.
    """
    source = os.environ if environ is None else environ
    raw = source.get(RENDERER_VARIABLE, "").strip().lower()
    if not raw:
        return "vtk"
    chosen = _NAMES.get(raw)
    if chosen is None:
        _log.warning("%s=%r ist kein Renderer; es bleibt bei VTK", RENDERER_VARIABLE, raw)
        return "vtk"
    return chosen


def available(kind: Backend) -> bool:
    """Ob dieser Renderer auf dieser Maschine zeichnen kann.

    VTK braucht seine OpenGL-Fabrik und das Qt-Widget; pygfx braucht einen
    wgpu-Adapter, also einen Grafiktreiber mit Vulkan, Metal oder DX12. Die
    Frage wird **vor** dem Aufbau gestellt, nicht in einem except-Zweig — ein
    Renderer ohne Kontext stirbt nicht höflich, sondern mit dem Prozess.
    """
    if kind == "gfx":
        try:
            import wgpu

            adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
        except Exception as problem:  # pragma: no cover - hängt an der Maschine
            _log.info("pygfx steht nicht zur Verfügung: %s", problem)
            return False
        return adapter is not None
    try:
        import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
        from vtkmodules.qt.QVTKRenderWindowInteractor import (  # noqa: F401
            QVTKRenderWindowInteractor,
        )
    except Exception:  # pragma: no cover - hängt an der Maschine
        return False
    return True


def make_renderer(
    parent: Any = None,
    *,
    offscreen: bool = False,
    size: tuple[int, int] = (640, 480),
    kind: Backend | None = None,
) -> Renderer:
    """Ein Renderer nach Wahl — mit Qt-Widget unter ``parent`` oder ohne Fenster."""
    chosen = backend() if kind is None else kind
    if chosen == "gfx":
        from app.ui.render.gfx_renderer import GfxRenderer

        return GfxRenderer(parent, offscreen=offscreen, size=size)
    from app.ui.render.vtk_renderer import VtkRenderer

    return VtkRenderer(parent, offscreen=offscreen, size=size)
