"""S4: ``threaded_rod`` über die Länge — wo der Gang stillschweigend fehlt.

Aufgefallen beim Bau des kurzen Referenzkörpers: ``threaded_rod(6, 1, 2.5)``
kam als nackter Kern zurück — 11 Flächen, Volumen exakt das des Kerns, kein
Fehler, keine Meldung. Die Länge liegt über der Untergrenze (zwei Steigungen),
der Gang wird gebaut und zugeschnitten (S4 misst beides gültig), und die
Vereinigung mit dem Kern verliert ihn. ``_is_sound_rod`` fragt geschlossen
und einteilig — beides erfüllt der Kern allein.

Gemessen wird hier, **wann** das passiert: über ein Raster aus Durchmesser,
Steigung und Länge, mit dem Gangvolumen je Umlauf als Kennzahl. Ein Bolzen
ohne Gang meldet 0; ein beschädigter (M10 x 1,5, Länge 4) weniger als den
Kern. Jede halbzahlige Umlaufzahl des Rasters (Länge/Steigung + 2 = x,5)
verliert den Gang, aber nicht nur die: M8 x 1,25 mit Länge 8 (8,4 Umläufe)
auch. Die Sonde ändert nichts am Produkt — sie belegt den Befund B3.
"""

from __future__ import annotations

import math

import _iso  # noqa: F401
import _probe as pr

from app.core.brep import profiles

DEPTH_SHARE = 0.6134  # profiles._THREAD_DEPTH_SHARE

GRID = (
    (6.0, 1.0, (2.2, 2.5, 2.75, 3.0, 3.5, 4.0, 4.5, 6.5, 8.0, 10.5, 12.0)),
    (8.0, 1.25, (5.0, 5.625, 6.25, 8.0, 10.0)),
    (10.0, 1.5, (3.5, 4.0, 4.5, 6.0, 6.75, 8.0, 12.0)),
)

pr.out("== Gangvolumen je Umlauf über Länge/Steigung ==")
pr.out("  Umläufe = Länge/Steigung + 2 (so baut threaded_rod seine Helix)")
lost: list[str] = []
broken: list[str] = []
half_turns: list[str] = []
per_turn: dict[tuple[float, float], list[float]] = {}
for major, pitch, lengths in GRID:
    core_radius = major / 2.0 - DEPTH_SHARE * pitch
    for length in lengths:
        turns = length / pitch + 2.0
        with pr.Timed(f"threaded_rod M{major:g}x{pitch:g} L={length:g}"):
            rod = profiles.threaded_rod(major, pitch, length)
        core = math.pi * core_radius**2 * length
        ridge = rod.volume - core
        share = ridge / (length / pitch)
        label = f"M{major:g}x{pitch:g} L={length:<5g} Umläufe {turns:5.2f}"
        pr.out(
            f"  {label}: Flächen {rod.face_count:2}  Gang {ridge:9.4f} mm³ "
            f"({share:8.4f} je Umlauf)  dicht={rod.is_closed}"
        )
        if abs(turns - round(turns)) > 0.49:
            half_turns.append(label)
        # Ein Hundertstel Kubikmillimeter trennt „kein Gang" von „Gang":
        # der kleinste Gang im Raster hat 7 mm³.
        if ridge < -0.01:
            broken.append(label)
        elif ridge < 0.01:
            lost.append(label)
        else:
            per_turn.setdefault((major, pitch), []).append(share)

pr.out()
pr.out("== Befund ==")
for key, shares in per_turn.items():
    pr.close(
        f"M{key[0]:g}x{key[1]:g}: das Gangvolumen je Umlauf ist eine Konstante des Profils",
        max(shares) - min(shares),
        0.0,
        0.05,
    )
pr.check(
    "B3: threaded_rod liefert an mehreren Längen den Kern ohne Gang — ohne Fehler",
    bool(lost),
    "; ".join(lost),
)
pr.check(
    "B3: und liefert mindestens einmal einen Körper unter dem Kernvolumen",
    bool(broken),
    "; ".join(broken),
)
pr.check(
    "B3: jede halbzahlige Umlaufzahl des Rasters verliert den Gang",
    bool(half_turns) and all(entry in lost for entry in half_turns),
    f"{len(half_turns)} halbzahlige, verloren: {sum(entry in lost for entry in half_turns)}",
)
odd = [entry for entry in lost if entry not in half_turns]
pr.check(
    "B3: halbzahlig ist hinreichend, nicht notwendig — auch andere Längen verlieren ihn",
    bool(odd),
    "; ".join(odd),
)
pr.out(
    f"  Verloren oder beschädigt: {len(lost) + len(broken)} von "
    f"{sum(len(lengths) for _, _, lengths in GRID)} Rasterpunkten. "
    "Kein Fall meldet einen Fehler — die Absage bliebe dem Nutzer verborgen."
)


def stages(major: float, pitch: float, length: float) -> tuple[float, float, float, float]:
    """Die drei Stufen von ``threaded_rod`` einzeln: Sweep, Zuschnitt, Vereinigung.

    Nachgebaut mit denselben Aufrufen wie das Produkt (Helix auf dem
    Kernzylinder, Fünfpunktprofil mit Sockel, MakePipeShell, Zuschnitt mit
    dem Zylinder, ``_joined_rod``) — damit die Stufe benannt werden kann, an
    der der Gang verloren geht.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.BRepLib import BRepLib
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.Geom import Geom_CylindricalSurface
    from OCP.Geom2d import Geom2d_Line
    from OCP.gp import gp_Ax2d, gp_Ax3, gp_Dir2d, gp_Pnt, gp_Pnt2d

    from app.core.brep.kernel import Solid

    depth = DEPTH_SHARE * pitch
    core_radius = major / 2.0 - depth
    turns = length / pitch + 2.0
    surface = Geom_CylindricalSurface(gp_Ax3(), core_radius)
    line = Geom2d_Line(gp_Ax2d(gp_Pnt2d(0.0, -pitch), gp_Dir2d(2.0 * math.pi, pitch)))
    helix = BRepBuilderAPI_MakeEdge(line, surface, 0.0, math.hypot(math.tau, pitch) * turns).Edge()
    BRepLib.BuildCurves3d_s(helix)
    half, foot, seat = pitch * 0.375, core_radius - 0.1, core_radius - max(0.1, depth)
    corners = (
        (seat, -pitch - half),
        (foot, -pitch - half),
        (core_radius + depth, -pitch),
        (foot, -pitch + half),
        (seat, -pitch + half),
    )
    outline = BRepBuilderAPI_MakeWire()
    for index in range(len(corners)):
        start, end = corners[index - 1], corners[index]
        outline.Add(
            BRepBuilderAPI_MakeEdge(
                gp_Pnt(start[0], 0.0, start[1]), gp_Pnt(end[0], 0.0, end[1])
            ).Edge()
        )
    pipe = BRepOffsetAPI_MakePipeShell(BRepBuilderAPI_MakeWire(helix).Wire())
    pipe.SetMode(True)
    pipe.Add(outline.Wire())
    pipe.Build()
    pipe.MakeSolid()
    ridge = Solid(pipe.Shape())
    slab = Solid(BRepPrimAPI_MakeCylinder(major / 2.0 + 1.0, length).Shape())
    trimmed = profiles._fuzzy_boolean("intersection", ridge, slab)
    core = Solid(BRepPrimAPI_MakeCylinder(core_radius, length).Shape())
    joined = profiles._joined_rod(core, trimmed, major, pitch)
    pr.out(
        f"  M{major:g}x{pitch:g} L={length:g}: Sweep {ridge.volume:.3f} mm³ "
        f"(geschlossen={ridge.is_closed}), Zuschnitt {trimmed.volume:.3f} mm³ "
        f"(sound={profiles._is_sound_rod(trimmed)}), Kern {core.volume:.3f}, "
        f"Vereinigung {joined.volume:.3f} mm³ ({profiles._rod_state(joined)})"
    )
    return ridge.volume, trimmed.volume, core.volume, joined.volume


pr.out()
pr.out("== Die Stufe, an der der Gang verloren geht ==")
sweep, trimmed, core, joined = stages(6.0, 1.0, 2.5)
pr.check("M6x1 L=2,5: der Sweep hat Volumen", sweep > 1.0)
pr.check("M6x1 L=2,5: der Zuschnitt hat Volumen", trimmed > 1.0)
pr.close("M6x1 L=2,5: die Vereinigung ist der Kern allein", joined, core, 1e-6)
sweep, trimmed, core, joined = stages(10.0, 1.5, 4.0)
pr.check("M10x1,5 L=4: der Zuschnitt hat Volumen", trimmed > 1.0)
pr.check(
    "M10x1,5 L=4: die Vereinigung liegt unter dem Kern — und wird trotzdem geliefert",
    joined < core - 1.0,
    f"{joined:.3f} < {core:.3f}",
)
pr.finish("S4 threaded_rod über die Länge")
