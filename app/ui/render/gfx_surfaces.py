"""Koplanare Flächenmarkierungen mit erhaltener Verdeckung (§18).

Nur die Rastertiefe rückt zur Kamera. Beleuchtung, Weltpunkte und die
ursprünglichen Dreiecke für das genaue Picking bleiben unverändert.
"""

from __future__ import annotations

from typing import Any, Final

import pygfx as gfx
from pygfx.renderers.wgpu import register_wgpu_render_function
from pygfx.renderers.wgpu.shaders.meshshader import MeshShader

#: Ein Achtel Gerätebildpunkt überwindet Rundungsunterschiede koplanarer
#: Dreiecke, ohne den Tiefenabstand einer ganzen sichtbaren Linie zu benötigen.
SURFACE_DEPTH_OFFSET_PIXELS: Final = 0.125


class CoplanarMeshBasicMaterial(gfx.MeshBasicMaterial):  # type: ignore[misc]
    """Unbeleuchtete Flächenmarkierung mit kleinem Rastertiefenversatz."""


class CoplanarMeshPhongMaterial(gfx.MeshPhongMaterial):  # type: ignore[misc]
    """Beleuchtete Flächenmarkierung mit kleinem Rastertiefenversatz."""


@register_wgpu_render_function(gfx.Mesh, CoplanarMeshBasicMaterial)
@register_wgpu_render_function(gfx.Mesh, CoplanarMeshPhongMaterial)
class CoplanarMeshShader(MeshShader):  # type: ignore[misc]
    """Der pygfx-Meshshader mit vorgezogener Rastertiefe und regulärem Tiefentest."""

    def __init__(self, obj: Any) -> None:
        super().__init__(obj)
        if isinstance(obj.material, CoplanarMeshPhongMaterial):
            self["lighting"] = "phong"

    def get_code(self) -> str:
        code = str(super().get_code())
        output = "varyings.position = vec4<f32>(ndc_pos.xyz, ndc_pos.w);"
        if output not in code:
            raise RuntimeError(
                "Der pygfx-Meshshader hat sich geändert. Die festgelegte Paketversion installieren."
            )
        # Wie bei DepthLineShader bleibt die frühe Tiefenprüfung möglich.
        # Nur position.z ändert sich, niemals world_pos oder die Rasterlage xy.
        return code.replace(
            output,
            output
            + f"""
                let view_h = u_stdinfo.projection_transform_inv * ndc_pos;
                var view_point = view_h / view_h.w;
                let pixel_depth = 2.0 * ndc_pos.w /
                    (u_stdinfo.projection_transform[1][1] * u_stdinfo.physical_size.y);
                view_point.z += pixel_depth * {SURFACE_DEPTH_OFFSET_PIXELS};
                let shifted = u_stdinfo.projection_transform * view_point;
                varyings.position.z = max(0.0, shifted.z / shifted.w) * ndc_pos.w;
            """,
            1,
        )
