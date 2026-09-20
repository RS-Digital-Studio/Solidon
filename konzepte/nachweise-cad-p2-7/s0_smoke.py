"""S0: Rauchtest der Sondenbibliothek — jede Form einmal, jedes Maß gegen Analytik."""

from __future__ import annotations

import math

import _probe as pr

pr.out("Formen über die vorhandene API:")
b = pr.expect_solid("box 10x20x30", pr.box(10, 20, 30))
pr.close("box Volumen", b["volume"], 6000.0)
c = pr.expect_solid("cylinder d8 h5", pr.cylinder(8, 5))
pr.close("cylinder Volumen", c["volume"], math.pi * 16 * 5, 1e-6)
h = pr.expect_solid("hexagon sw7 h3", pr.hexagon(7, 3))
pr.close("hexagon Volumen", h["volume"], (math.sqrt(3) / 2) * 49 * 3, 1e-6)
s = pr.expect_solid("slot w4 l12 h2", pr.slot(4, 12, 2))
pr.close("slot Volumen", s["volume"], (math.pi * 4 + 8 * 4) * 2, 1e-6)
pr.check("slot trägt zwei Zylinderflächen", s["types"].get("cylinder") == 2, str(s["types"]))
w = pr.expect_solid("wedge w6 d1 h3 tip0", pr.wedge(6, 1, 3, 0.0))
pr.close("wedge Volumen", w["volume"], 6 * 0.5 * 1 * 3, 1e-6)
wb = pr.bounds(pr.wedge(6, 1, 3, 0.0))
pr.check(
    "wedge liegt in X zentriert, Y in +, Z in +",
    abs(wb[0] + 3) < 1e-9 and abs(wb[3] - 3) < 1e-9 and wb[1] >= -1e-9 and wb[2] >= -1e-9,
    str(wb),
)
k = pr.expect_solid("cone 6->10 h2", pr.cone(6, 10, 2))
pr.close("cone Volumen", k["volume"], math.pi * 2 / 3 * (9 + 15 + 25), 1e-6)
pr.check("cone trägt eine Kegelfläche", k["types"].get("cone") == 1, str(k["types"]))
t = pr.expect_solid("tapered_bar", pr.tapered_bar(8, 5, 20, 3, 2))
r = pr.expect_solid("rounded_prism 40x30x10 r8", pr.rounded_prism(40, 30, 10, 8))
pr.close("rounded_prism Volumen", r["volume"], (40 * 30 - (4 - math.pi) * 64) * 10, 1e-6)
pr.check("rounded_prism vier Zylinderflächen", r["types"].get("cylinder") == 4, str(r["types"]))
u = pr.expect_solid(
    "union box+cyl", pr.union(pr.box(10, 10, 10), pr.moved(pr.cylinder(4, 20), (0, 0, -5)))
)
d = pr.expect_solid(
    "subtract box-cyl", pr.subtract(pr.box(10, 10, 10), pr.moved(pr.cylinder(4, 20), (0, 0, -5)))
)
pr.close("subtract Volumen", d["volume"], 1000 - math.pi * 4 * 10, 1e-6)
tr = pr.turned(pr.cylinder(4, 10), 90.0, (0, 1, 0))
tb = pr.bounds(tr)
pr.check(
    "turned: Zylinderachse liegt jetzt in X",
    abs(tb[3] - tb[0] - 10) < 1e-6 and abs(tb[5] - tb[2] - 4) < 1e-6,
    str(tb),
)
pr.check("inside: Mitte des Quaders", pr.inside(pr.box(10, 10, 10), (0, 0, 5)))
pr.check("inside: neben dem Quader", not pr.inside(pr.box(10, 10, 10), (6, 0, 5)))
pr.close("radial_extent Zylinder d8", pr.radial_extent(pr.cylinder(8, 5), 2.5), 4.0, 1e-6)
pr.step_roundtrip("rounded_prism", pr.rounded_prism(40, 30, 10, 8))
pr.finish("S0 Rauchtest")
