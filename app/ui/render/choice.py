"""Welcher Renderer die Ansicht zeichnet — und ob er hier kann (§18).

Zwei Renderer stehen hinter dem Vertrag aus :mod:`app.ui.render.api`, und
beide sind gemessen (Entscheidung Robert, 05.09.2026: „bau beides und mess“).
Gezeichnet wird mit pygfx über wgpu — ``gfx`` ist die Vorgabe (Entscheidung
Robert, 06.09.2026, nach der Modellabnahme mit beiden). VTK bleibt der zweite
Renderer hinter demselben Vertrag; die Umgebungsvariable ``SOLIDON_RENDERER``
wählt ihn mit ``vtk``. Eine Einstellung in der Oberfläche gibt es absichtlich
nicht — ein Kunde soll nie vor der Frage stehen, welche Grafikbibliothek er
möchte; die Entscheidung fällt einmal, hier im Code.

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


#: Der Renderer, der ohne Umgebungsvariable zeichnet.
DEFAULT_BACKEND: Backend = "gfx"


def backend(environ: Mapping[str, str] | None = None) -> Backend:
    """Der gewählte Renderer — ``gfx``, solange niemand etwas anderes sagt.

    Ein unbekannter Wert fällt auf die Vorgabe zurück und sagt es im
    Protokoll: Ein Tippfehler soll die Ansicht nicht kosten, aber auch nicht
    still bleiben.
    """
    source = os.environ if environ is None else environ
    raw = source.get(RENDERER_VARIABLE, "").strip().lower()
    if not raw:
        return DEFAULT_BACKEND
    chosen = _NAMES.get(raw)
    if chosen is None:
        _log.warning(
            "%s=%r ist kein Renderer; es bleibt bei %s",
            RENDERER_VARIABLE,
            raw,
            DEFAULT_BACKEND.upper(),
        )
        return DEFAULT_BACKEND
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


def effective_backend(environ: Mapping[str, str] | None = None) -> Backend | None:
    """Der Renderer, der auf dieser Maschine wirklich zeichnet.

    Die Wahl, sofern die Maschine sie kann — sonst der andere, und das steht
    im Protokoll. ``None`` heißt: keiner von beiden, und dann bleibt die
    Ansicht leer (der Viewport sagt dem Nutzer, was fehlt). Ein Kunde ohne
    wgpu-Adapter bekommt so weiterhin eine 3D-Ansicht, nur über VTK.
    """
    chosen = backend(environ)
    if available(chosen):
        return chosen
    other: Backend = "vtk" if chosen == "gfx" else "gfx"
    if available(other):
        _log.warning("%s kann hier nicht zeichnen; es zeichnet %s", chosen, other)
        return other
    return None


def make_renderer(
    parent: Any = None,
    *,
    offscreen: bool = False,
    size: tuple[int, int] = (640, 480),
    kind: Backend | None = None,
) -> Renderer:
    """Ein Renderer nach Wahl — mit Qt-Widget unter ``parent`` oder ohne Fenster.

    Ohne ``kind`` zeichnet, was :func:`effective_backend` nennt: die Wahl,
    oder der andere, wenn die Maschine die Wahl nicht kann.
    """
    chosen = (effective_backend() or backend()) if kind is None else kind
    if chosen == "gfx":
        from app.ui.render.gfx_renderer import GfxRenderer

        return GfxRenderer(parent, offscreen=offscreen, size=size)
    from app.ui.render.vtk_renderer import VtkRenderer

    return VtkRenderer(parent, offscreen=offscreen, size=size)
