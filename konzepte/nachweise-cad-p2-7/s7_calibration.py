"""S7: Gruppe Kalibrierung — Toleranzleiter, Wandstärkenleiter, Überhangfächer.

Drei eigenständige Prüfkörper aus Quadern, Zylindern und Keilen. Die
Toleranzleiter erklärt zwei Körper (zwei getrennte Leisten) und graviert
Strichcodes; der Überhangfächer setzt Rampen, deren Winkel die Funktion sind.
"""

from __future__ import annotations

import math

import _probe as pr

from app.core import bootstrap

bootstrap.load_operations()

from app.core.geom.boolean import BOOLEAN_OVERLAP  # noqa: E402
from app.core.knowledge.parts import shapes  # noqa: E402
from app.core.knowledge.parts.registry import PARTS  # noqa: E402
from app.core.knowledge.parts.testbodies import LABEL_DEPTH  # noqa: E402

FACET = pr.polygon_ratio(shapes.SEGMENTS)


def build_mesh(name: str, **values: object):  # type: ignore[no-untyped-def]
    spec = PARTS.get(name)
    params = spec.params(**values)
    return spec, spec.fn(params)


def same_bounds(label: str, mesh_info: dict, info: dict, tol: float = 1e-6) -> None:  # type: ignore[type-arg]
    pr.check(
        label,
        all(abs(a - b) < tol for a, b in zip(mesh_info["bounds"], info["bounds"], strict=True)),
        f"{mesh_info['bounds']} / {info['bounds']}",
    )


# --- fit_ladder ---------------------------------------------------------------------

pr.out("== fit_ladder (Ø 6, 4 Stufen, 0,1 + 0,05, Höhe 8) ==")
diameter, steps, first, step, height = 6.0, 4, 0.1, 0.05, 8.0
spec, produced = build_mesh(
    "fit_ladder", diameter=diameter, steps=steps, first=first, step=step, height=height
)
mi = pr.mesh_report("fit_ladder", produced.mesh)
largest = diameter + first + step * (steps - 1)
spacing = max(diameter * 2.2, largest * 1.5, steps * 1.4 + 2.8)
base_height = 3.0
width = spacing * steps + spacing
rail_depth = max(spacing, largest + 8.0)
rail_offset = (rail_depth + spacing * 0.2) / 2.0
pin_y, bore_y = -rail_offset, rail_offset
bodies = [pr.moved(pr.box(width, rail_depth, base_height), (0.0, y, 0.0)) for y in (pin_y, bore_y)]
cutters = []


def label_exact(count: int, position: tuple[float, float, float]):  # type: ignore[no-untyped-def]
    bars = []
    for index in range(count):
        bar = pr.box(0.8, 3.0, LABEL_DEPTH + BOOLEAN_OVERLAP)
        bars.append(
            pr.moved(bar, (position[0] + index * 1.4 - count * 0.7, position[1], position[2]))
        )
    return pr.union(*bars)


with pr.Timed("fit_ladder exakt (2 Leisten, 4 Zapfen, 4 Bohrungen, 8 Strichcodes)"):
    for index in range(steps):
        play = first + step * index
        x = -width / 2.0 + spacing * (index + 1)
        bodies.append(pr.moved(pr.cylinder(diameter, height), (x, pin_y, base_height)))
        cutters.append(
            pr.moved(
                pr.cylinder(diameter + play, base_height + 2.0 * BOOLEAN_OVERLAP),
                (x, bore_y, -BOOLEAN_OVERLAP),
            )
        )
        for y in (pin_y, bore_y):
            cutters.append(
                label_exact(index + 1, (x, y + largest / 2.0 + 2.0, base_height - LABEL_DEPTH))
            )
    body = pr.subtract(pr.union(*bodies), *cutters)
info = pr.expect_solid("fit_ladder exakt", body, solids=2)
pr.check(
    "fit_ladder: Netz erklärt ebenfalls zwei Körper", mi["components"] == 2, str(mi["components"])
)
for index in range(steps):
    x = -width / 2.0 + spacing * (index + 1)
    play = first + step * index
    pr.close(
        f"fit_ladder: Bohrung {index + 1} Ø = {diameter + play:.2f}",
        pr.hole_diameter(body, (x, bore_y), base_height / 2.0),
        diameter + play,
        1e-6,
    )
    pr.check(
        f"fit_ladder: Zapfen {index + 1} steht (Material bei z = base + h/2)",
        pr.inside(body, (x, pin_y, base_height + height / 2.0))
        and not pr.inside(body, (x + diameter / 2.0 + 0.01, pin_y, base_height + height / 2.0)),
    )
    pr.check(
        f"fit_ladder: Strichcode {index + 1} graviert ({index + 1} Striche)",
        not pr.inside(
            body,
            (x - (index + 1) * 0.7, pin_y + largest / 2.0 + 2.0, base_height - LABEL_DEPTH / 2.0),
        ),
    )
same_bounds("fit_ladder: Bounds Netz = exakt", mi, info)
pr.ratio(
    "fit_ladder: Netz/exakt (Zapfen und Bohrungen facettiert)", mi["volume"], info["volume"], 0.002
)
pr.step_roundtrip("fit_ladder", body)

# --- wall_ladder ----------------------------------------------------------------------

pr.out()
pr.out("== wall_ladder (0,42, 6 Stufen, Höhe 15, Länge 25) ==")
extrusion, steps, height, length = 0.42, 6, 15.0, 25.0
spec, produced = build_mesh(
    "wall_ladder", extrusion=extrusion, steps=steps, height=height, length=length
)
mi = pr.mesh_report("wall_ladder", produced.mesh)
gap = extrusion * 6.0
thicknesses = [extrusion * (i + 1) for i in range(steps)]
width = sum(thicknesses) + gap * (steps + 1)
bodies = [pr.box(width, length, 2.0)]
left = -width / 2.0 + gap
for t in thicknesses:
    bodies.append(pr.moved(pr.box(t, length, height), (left + t / 2.0, 0.0, 2.0)))
    left += t + gap
body = pr.union(*bodies)
info = pr.expect_solid("wall_ladder exakt", body)
pr.close(
    "wall_ladder: Volumen",
    info["volume"],
    width * length * 2.0 + sum(thicknesses) * length * height,
    1e-9,
)
pr.close("wall_ladder: Netz = exakt", mi["volume"], info["volume"], 1e-9)
same_bounds("wall_ladder: Bounds Netz = exakt", mi, info)
thin_x = -width / 2.0 + gap + extrusion / 2.0
pr.close(
    "wall_ladder: dünnste Wand genau eine Extrusionsbreite",
    pr.extent_along(body, (thin_x, 0.0, 10.0), (1.0, 0.0, 0.0))
    + pr.extent_along(body, (thin_x, 0.0, 10.0), (-1.0, 0.0, 0.0)),
    extrusion,
    1e-6,
)
pr.step_roundtrip("wall_ladder", body)

# --- overhang_fan ---------------------------------------------------------------------

pr.out()
pr.out("== overhang_fan (20° + 10° x 6, Breite 8, Länge 15) ==")
first, step, steps, width, length = 20.0, 10.0, 6, 8.0, 15.0
spec, produced = build_mesh(
    "overhang_fan", first=first, step=step, steps=steps, width=width, length=length
)
mi = pr.mesh_report("overhang_fan", produced.mesh)
total = width * steps
depth = 6.0
bodies = [pr.box(total, depth, 3.0)]
start = depth / 2.0 - 1.0
for index in range(steps):
    angle = math.radians(first + step * index)
    x = -total / 2.0 + width * (index + 0.5)
    reach, rise = length * math.sin(angle), length * math.cos(angle)
    # Rampe wie _ramp: Rechteck-Fuß bei y=0, Oberkante bei (reach, rise), Rückwand senkrecht.
    ramp = pr.prism([(0.0, 0.0), (reach, rise), (0.0, rise)], width, "plane:yz")
    bodies.append(pr.moved(ramp, (x - width / 2.0, start, 3.0 - BOOLEAN_OVERLAP)))
body = pr.union(*bodies)
info = pr.expect_solid("overhang_fan exakt", body)
ramps = sum(
    0.5 * length * math.sin(a) * length * math.cos(a) * width
    for a in (math.radians(first + step * i) for i in range(steps))
)
pr.close(
    "overhang_fan: Volumen = Sockel + Rampen (bis auf die Überlappung)",
    info["volume"],
    total * depth * 3.0 + ramps,
    0.5,
)
pr.close("overhang_fan: Netz = exakt", mi["volume"], info["volume"], 1e-6)
same_bounds("overhang_fan: Bounds Netz = exakt", mi, info)
# Der Winkel ist die Funktion: Die Unterseite der letzten Rampe (70°) liegt auf der
# Geraden durch den Fuß mit der Steigung des Winkels.
a = math.radians(first + step * (steps - 1))
x = -total / 2.0 + width * (steps - 0.5)
probe_y, probe_z = start + 0.5 * length * math.sin(a), 3.0 + 0.5 * length * math.cos(a)
pr.check(
    "overhang_fan: letzte Rampe hat ihre Unterseite auf der Winkelgeraden",
    pr.inside(body, (x, probe_y - 0.02, probe_z + 0.02))
    and not pr.inside(body, (x, probe_y + 0.02, probe_z - 0.02)),
)
pr.step_roundtrip("overhang_fan", body)

pr.finish("S7 Kalibrierung")
