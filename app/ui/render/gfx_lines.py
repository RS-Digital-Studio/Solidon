"""Koplanare GFX-Linien mit Tiefenversatz und erhaltener Verdeckung (§18).

Der Versatz betrifft ausschließlich die Rastertiefe, weder Weltpunkte noch
Pickkoordinaten. Die Linien bleiben hinter davorliegenden Flächen verborgen.
"""

from __future__ import annotations

from typing import Any

import pygfx as gfx
from pygfx.renderers.wgpu import register_wgpu_render_function
from pygfx.renderers.wgpu.shaders.lineshader import LineShader


class DepthLineMaterial(gfx.LineMaterial):  # type: ignore[misc]
    """Verbundene Linie mit kleinem Tiefenversatz."""


class DepthLineSegmentMaterial(gfx.LineSegmentMaterial):  # type: ignore[misc]
    """Getrennte Linienpaare mit kleinem Tiefenversatz."""


@register_wgpu_render_function(gfx.Line, DepthLineMaterial)
@register_wgpu_render_function(gfx.Line, DepthLineSegmentMaterial)
class DepthLineShader(LineShader):  # type: ignore[misc]
    """Der pygfx-Linienshader mit einem rasterbezogenen Tiefenversatz."""

    def __init__(self, obj: Any) -> None:
        super().__init__(obj)
        if isinstance(obj.material, DepthLineSegmentMaterial):
            self["line_type"] = "segment"

    def get_code(self) -> str:
        code = str(super().get_code())
        output = "varyings.position = vec4<f32>(the_pos_n);"
        if output not in code:
            raise RuntimeError(
                "Der pygfx-Linienshader hat sich geändert. "
                "Die festgelegte Paketversion installieren."
            )
        # Ein Bildpunkt im Kameraraum löst auch den Tiefenunterschied über
        # die Breite einer Linie. Der Versatz passiert im Vertexshader, damit
        # die frühe Tiefenprüfung und verborgene Kanten erhalten bleiben.
        return code.replace(
            output,
            output
            + """
                let view_h = u_stdinfo.projection_transform_inv * the_pos_n;
                var view_point = view_h / view_h.w;
                let pixel_depth = 2.0 * the_pos_n.w /
                    (u_stdinfo.projection_transform[1][1] * u_stdinfo.physical_size.y);
                view_point.z += pixel_depth;
                let shifted = u_stdinfo.projection_transform * view_point;
                varyings.position.z = max(0.0, shifted.z / shifted.w) * the_pos_n.w;
            """,
            1,
        )
