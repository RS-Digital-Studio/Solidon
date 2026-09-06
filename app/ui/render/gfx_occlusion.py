"""Umgebungsverdeckung für GFX, vor durchscheinenden Flächen und Marken (§18).

Der Bildschirmdurchgang liest ausschließlich Farbe und Tiefe auf der GPU.
Radius und Abstandsschwelle gelten in Millimetern im Kameraraum; der
Sichtstrahl entsteht aus der inversen Projektionsmatrix beider Kameraarten.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import wgpu
from pygfx.renderers.wgpu import EffectPass

_VIEW_POSITION_WGSL = """
    fn view_position_at_depth(pixel: vec2<i32>, depth: f32,
                              dimensions: vec2<i32>) -> vec3<f32> {
        let uv = (vec2<f32>(pixel) + vec2<f32>(0.5)) / vec2<f32>(dimensions);
        let clip = vec4<f32>(2.0 * uv.x - 1.0, 1.0 - 2.0 * uv.y, depth, 1.0);
        let world = u_effect.projection_inverse * clip;
        return world.xyz / world.w;
    }

    fn view_position(pixel: vec2<i32>, dimensions: vec2<i32>) -> vec3<f32> {
        return view_position_at_depth(pixel, textureLoad(depthTex, pixel, 0), dimensions);
    }
"""


class _OcclusionResolvePass(EffectPass):  # type: ignore[misc]
    """Nur Verdeckung glätten; die ursprüngliche Farbe und Alpha erhalten."""

    USES_DEPTH = True
    uniform_type: ClassVar[dict[str, str]] = {
        **EffectPass.uniform_type,
        "projection_inverse": "4x4xf4",
        "radius": "f4",
        "bias": "f4",
    }
    load_op = wgpu.LoadOp.load
    blend_state: ClassVar[dict[str, dict[str, str]]] = {
        "color": {"operation": "add", "src_factor": "zero", "dst_factor": "src"},
        "alpha": {"operation": "add", "src_factor": "zero", "dst_factor": "one"},
    }
    wgsl = (
        _VIEW_POSITION_WGSL
        + """
        @fragment
        fn fs_main(varyings: Varyings) -> @location(0) vec4<f32> {
            let pixel = vec2<i32>(varyings.position.xy);
            let dimensions = vec2<i32>(textureDimensions(depthTex));
            let depth = textureLoad(depthTex, pixel, 0);
            if (depth >= 1.0) {
                return vec4<f32>(1.0);
            }
            let centre = view_position_at_depth(pixel, depth, dimensions);
            let factor = textureLoad(colorTex, pixel, 0);
            let normal = normalize(factor.gba * 2.0 - 1.0);
            let plane_scale = max(max(u_effect.bias * 2.0, u_effect.radius * 0.01), 1e-6);
            var total = 0.0;
            var weights = 0.0;
            for (var y = -2; y <= 2; y += 1) {
                for (var x = -2; x <= 2; x += 1) {
                    let sample_pixel = pixel + vec2<i32>(x, y);
                    if (any(sample_pixel < vec2<i32>(0)) || any(sample_pixel >= dimensions)) {
                        continue;
                    }
                    let sample_depth = textureLoad(depthTex, sample_pixel, 0);
                    if (sample_depth >= 1.0) {
                        continue;
                    }
                    let neighbour = textureLoad(colorTex, sample_pixel, 0);
                    let sample_normal = normalize(neighbour.gba * 2.0 - 1.0);
                    let delta = view_position_at_depth(sample_pixel, sample_depth, dimensions)
                        - centre;
                    let plane_distance = dot(normal, delta) / plane_scale;
                    let alignment = max(dot(normal, sample_normal), 0.0);
                    let weight = exp2(-f32(x * x + y * y) * 0.5
                        - plane_distance * plane_distance) * pow(alignment, 16.0);
                    total += neighbour.r * weight;
                    weights += weight;
                }
            }
            let visibility = select(factor.r, total / max(weights, 1e-8), weights > 1e-8);
            return vec4<f32>(vec3<f32>(visibility), 1.0);
        }
        """
    )


class AmbientOcclusionPass(EffectPass):  # type: ignore[misc]
    """Deterministische Tiefenabtastung, ohne Zufallsrauschen oder Rücklesen."""

    USES_DEPTH = True
    uniform_type: ClassVar[dict[str, str]] = {
        **EffectPass.uniform_type,
        "projection_inverse": "4x4xf4",
        "radius": "f4",
        "bias": "f4",
    }
    wgsl = (
        _VIEW_POSITION_WGSL
        + """
        @fragment
        fn fs_main(varyings: Varyings) -> @location(0) vec4<f32> {
            let pixel = vec2<i32>(varyings.position.xy);
            let dimensions = vec2<i32>(textureDimensions(depthTex));
            let depth = textureLoad(depthTex, pixel, 0);
            if (depth >= 1.0 || u_effect.radius <= 0.0) {
                return vec4<f32>(1.0, 0.5, 0.5, 1.0);
            }
            let last = dimensions - vec2<i32>(1);
            let centre = view_position_at_depth(pixel, depth, dimensions);
            let left = view_position(
                clamp(pixel + vec2<i32>(-1, 0), vec2<i32>(0), last), dimensions);
            let right = view_position(
                clamp(pixel + vec2<i32>(1, 0), vec2<i32>(0), last), dimensions);
            let up = view_position(clamp(pixel + vec2<i32>(0, -1), vec2<i32>(0), last), dimensions);
            let down = view_position(
                clamp(pixel + vec2<i32>(0, 1), vec2<i32>(0), last), dimensions);
            // Die nähere Nachbarfläche trägt die Normale, nicht die Silhouette dahinter.
            let horizontal = select(right - centre, centre - left,
                abs(centre.z - left.z) < abs(right.z - centre.z));
            let vertical = select(centre - down, up - centre,
                abs(up.z - centre.z) < abs(centre.z - down.z));
            let cross_normal = cross(horizontal, vertical);
            if (dot(cross_normal, cross_normal) < 1e-20) {
                return vec4<f32>(1.0, 0.5, 0.5, 1.0);
            }
            var normal = normalize(cross_normal);
            normal = select(normal, -normal, normal.z < 0.0);
            let pixel_size = max(length(horizontal.xy), length(vertical.xy));
            let screen_radius = u_effect.radius / max(pixel_size, 1e-8);
            // Ein festes 4x4-Muster verteilt Winkel und Radien zwischen Nachbarpixeln.
            // Es hängt nie von der Bildzeit ab: keine wandernden Körner bei ruhender Kamera.
            let phase = f32((pixel.x & 1) * 8 + (pixel.y & 1) * 4
                + (pixel.x & 2) + (pixel.y & 2) / 2) / 16.0;
            var obscured = 0.0;
            for (var direction = 0; direction < 8; direction += 1) {
                let angle = (f32(direction) + phase) * 0.78539816339;
                let axis = vec2<f32>(cos(angle), sin(angle));
                var horizon = 0.0;
                for (var step = 0; step < 4; step += 1) {
                    let fraction = (f32(step) + 0.25 + phase * 0.5) * 0.25;
                    let displacement = vec2<i32>(round(axis * screen_radius * fraction));
                    let sample_pixel = pixel + displacement;
                    if (any(sample_pixel < vec2<i32>(0)) || any(sample_pixel >= dimensions)) {
                        continue;
                    }
                    let sample_depth = textureLoad(depthTex, sample_pixel, 0);
                    if (sample_depth >= 1.0) {
                        continue;
                    }
                    let delta = view_position_at_depth(sample_pixel, sample_depth, dimensions)
                        - centre;
                    let distance = length(delta);
                    if (distance <= u_effect.bias || distance >= u_effect.radius
                        || distance < 1e-8) {
                        continue;
                    }
                    let elevation = max(dot(normal, delta) - u_effect.bias, 0.0) / distance;
                    let attenuation = 1.0 - distance / u_effect.radius;
                    horizon = max(horizon, elevation * attenuation * attenuation);
                }
                obscured += horizon;
            }
            let visibility = clamp(1.0 - obscured * 0.22, 0.35, 1.0);
            // Im zweiten Durchgang führen Normale und Tiefe die Glättung des Faktors.
            return vec4<f32>(visibility, normal * 0.5 + 0.5);
        }
    """
    )

    def __init__(self) -> None:
        super().__init__()
        self._resolve = _OcclusionResolvePass()

    def apply(self, renderer: Any, camera: Any, radius: float, bias: float) -> None:
        """Den Effekt vor Überlagerungen in denselben Farbpuffer zurückschreiben.

        Der begrenzte Texturzugriff bleibt hier; pygfx' öffentliche EffectPass-
        API übernimmt Shader, Bindungen und GPU-Ressourcen. Es wird kein Bild
        zur CPU kopiert, und weder Tiefen- noch Pickpuffer werden verändert.
        """
        blender = renderer._blender
        read = wgpu.TextureUsage.TEXTURE_BINDING
        write = wgpu.TextureUsage.RENDER_ATTACHMENT
        depth = blender.get_texture_view("depth", read)
        if depth is None:
            return
        colour = blender.get_texture_view("color", read)
        temporary = blender.get_texture_view("altcolor", write, create_if_not_exist=True)
        self._uniform_data["projection_inverse"] = np.asarray(camera.projection_matrix_inverse).T
        self._uniform_data["radius"] = max(float(radius), 0.0)
        self._uniform_data["bias"] = max(float(bias), 0.0)
        for name in ("projection_inverse", "radius", "bias"):
            self._resolve._uniform_data[name] = self._uniform_data[name]
        encoder = renderer._device.create_command_encoder()
        self.render(encoder, colour, depth, temporary)
        self._resolve.render(
            encoder,
            blender.get_texture_view("altcolor", read),
            depth,
            blender.get_texture_view("color", write),
        )
        renderer._device.queue.submit([encoder.finish()])
