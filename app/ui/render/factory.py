"""Wo der Renderer der 3D-Ansicht gebaut wird — und ob er hier kann (§18).

Gezeichnet wird mit pygfx über wgpu (Vulkan, DX12, Metal; in einer virtuellen
Maschine WARP beziehungsweise lavapipe). Entscheidung Robert, 06.09.2026,
nach der Modellabnahme mit beiden Renderern; der VTK-Renderer ist ausgebaut,
``vtk`` bleibt als kopflose Geometriebibliothek der Bereichsprüfung
(``app/core/knowledge/parts/range_check.py``).

Alles, was einen Renderer baut, geht über :func:`make_renderer` — der
Viewport, seine Bildaufnahme und die Ansichten für den Agenten —, damit ein
Wechsel an genau einer Stelle stattfindet. Ob die Maschine überhaupt einen
wgpu-Adapter hat, fragt :func:`available` **vor** dem Aufbau: Ein Renderer
ohne Adapter stirbt nicht höflich, sondern mit dem Prozess.
"""

from __future__ import annotations

import logging
from typing import Any

from app.ui.render.api import Renderer

_log = logging.getLogger(__name__)


def available() -> bool:
    """Ob pygfx auf dieser Maschine zeichnen kann: ein wgpu-Adapter ist da."""
    try:
        import wgpu

        adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
    except Exception as problem:  # pragma: no cover - hängt an der Maschine
        _log.info("pygfx steht nicht zur Verfügung: %s", problem)
        return False
    return adapter is not None


def make_renderer(
    parent: Any = None,
    *,
    offscreen: bool = False,
    size: tuple[int, int] = (640, 480),
) -> Renderer:
    """Der Renderer — mit Qt-Widget unter ``parent`` oder ohne Fenster."""
    from app.ui.render.gfx_renderer import GfxRenderer

    return GfxRenderer(parent, offscreen=offscreen, size=size)
