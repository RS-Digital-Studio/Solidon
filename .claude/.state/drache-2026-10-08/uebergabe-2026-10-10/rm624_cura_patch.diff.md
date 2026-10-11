# rm624_cura_patch.diff

Abgelegt als Markdown, damit die Akte keine CI auslöst.

```diff
diff --git a/tests/test_real_slicers.py b/tests/test_real_slicers.py
index 153cf03bf..f47b192bc 100644
--- a/tests/test_real_slicers.py
+++ b/tests/test_real_slicers.py
@@ -16,12 +16,11 @@ Apple Silicon und Intel-Mac, sobald eine Änderung die Übergabe berührt
 
 from __future__ import annotations
 
-import math
 import re
 import subprocess
 import time
 from collections.abc import Callable
-from dataclasses import dataclass, replace
+from dataclasses import replace
 from pathlib import Path
 
 import pytest
@@ -32,6 +31,7 @@ from app.core.geom.mesh import MeshData
 from app.core.knowledge import print_settings, profiles
 from app.core.types import Profile, SceneObject
 from app.core.units import format_length
+from tests.gcode_contact import support_contact
 from tests.helpers import set_test_license
 
 #: Je Programm ein Drucker, den sein Hersteller selbst führt — so läuft der
@@ -294,160 +294,201 @@ def test_curas_printers_are_read_from_its_appimage_without_starting_it(
         )
 
 
-#: Curas Bahnarten des Modells (``;TYPE:``); Stütze ist alles, was mit
-#: ``SUPPORT`` beginnt, samt Trennschicht. Rand und Turm zählen nicht.
-_CURA_MODEL = frozenset({"WALL-OUTER", "WALL-INNER", "SKIN", "FILL"})
-
-_CURA_WORD = re.compile(r"([XYZE])(-?\d*\.?\d+)")
-
-
-@dataclass(frozen=True)
-class _CuraGaps:
-    """Abstand oben und unten zwischen Curas Stütze und dem Modell, in mm, und
-    wie viele Bahnpunkte (je Millimeter einer) die oberste und die unterste
-    Stützlage im Ring tragen."""
-
-    top: float
-    bottom: float
-    top_points: int
-    bottom_points: int
-
-
-def _cura_support_gaps(text: str, layer: float, ring: tuple[float, float]) -> _CuraGaps:
-    """Misst Curas Stützabstand oben und unten (RM-628) in einem Ring um die Mitte
-    des Modells (``ring``: innerer und äußerer Abstand in mm, je Achse).
-
-    Höhen im G-Code sind Oberkanten; jede Lage ist ``layer`` hoch. Oben: die
-    Unterseite der ersten Modelllage über der höchsten Stützbahn minus diese —
-    auch, wenn Cura die oberste Stütze als Bruchteillage tiefer legt. Unten: die
-    Unterseite der tiefsten Stützlage minus die oberste Modellbahn darunter.
-    Gezählt werden Bahnen mit Förderung, absolut (``M82``, ``G92 E``) wie relativ
-    (``M83``)."""
-    relative = False
-    x = y = z = e = 0.0
-    kind = ""
-    moves: list[tuple[bool, float, float, float]] = []
-    for raw in text.splitlines():
-        line = raw.strip()
-        if line.startswith(";TYPE:"):
-            kind = line[len(";TYPE:") :].strip()
-            continue
-        command = line.split(";", 1)[0].split()
-        if not command:
-            continue
-        if command[0] in ("M82", "M83"):
-            relative = command[0] == "M83"
-            continue
-        words = {key: float(value) for key, value in _CURA_WORD.findall(" ".join(command[1:]))}
-        if command[0] == "G92":
-            e = words.get("E", e)
-            continue
-        if command[0] not in ("G0", "G1"):
-            continue
-        start_x, start_y = x, y
-        x, y, z = words.get("X", x), words.get("Y", y), words.get("Z", z)
-        if "E" not in words:
-            continue
-        fed = words["E"] if relative else words["E"] - e
-        e = e if relative else words["E"]
-        support = kind.startswith("SUPPORT")
-        if fed > 0.0 and command[0] == "G1" and (support or kind in _CURA_MODEL):
-            # Je Millimeter Bahn ein Punkt: Füllbahnen enden am Rand, nicht im Ring.
-            steps = max(1, math.ceil(math.hypot(x - start_x, y - start_y)))
-            moves += [
-                (
-                    support,
-                    start_x + (x - start_x) * t / steps,
-                    start_y + (y - start_y) * t / steps,
-                    z,
-                )
-                for t in range(1, steps + 1)
-            ]
-    model = [(px, py) for support, px, py, _pz in moves if not support]
-    assert model, "keine Modellbahn im G-Code"
-    centre_x = (min(px for px, _ in model) + max(px for px, _ in model)) / 2.0
-    centre_y = (min(py for _, py in model) + max(py for _, py in model)) / 2.0
-    inner, outer = ring
-    inside = [
-        (support, pz)
-        for support, px, py, pz in moves
-        if inner <= max(abs(px - centre_x), abs(py - centre_y)) <= outer
-    ]
-    held = [pz for support, pz in inside if support]
-    walls = [pz for support, pz in inside if not support]
-    assert held, "keine Stützbahn im Ring"
-    highest, lowest = max(held), min(held)
-    above = min(pz for pz in walls if pz > highest)
-    below = max(pz for pz in walls if pz < lowest)
-    return _CuraGaps(
-        top=round(above - layer - highest, 4),
-        bottom=round(lowest - layer - below, 4),
-        top_points=sum(1 for pz in held if math.isclose(pz, highest, abs_tol=1e-3)),
-        bottom_points=sum(1 for pz in held if math.isclose(pz, lowest, abs_tol=1e-3)),
+def _contact_gcode(relative: bool, resets: bool) -> str:
+    """Eine Platte über einer Säule als G-Code: Modell auf jeder Ebene in einer
+    eigenen Zelle (Säule), Trennschicht auf 0,6 mm und das Dach auf 1,0 mm über
+    derselben Zelle. Relativ, absolut oder absolut mit ``G92 E0`` je Ebene."""
+    lines = ["M83" if relative else "M82"]
+    e = 0.0
+
+    def move(x: float, y: float, z: float) -> str:
+        nonlocal e
+        e += 0.05
+        return f"G1 X{x} Y{y} Z{z} E{0.05 if relative else round(e, 5)}"
+
+    for level, kinds in (
+        (0.2, ("Outer wall",)),
+        (0.4, ("Outer wall",)),
+        (0.6, ("Outer wall", "Support interface")),
+        (0.8, ("Outer wall",)),
+        (1.0, ("Outer wall", "Top surface")),
+    ):
+        if resets and not relative:
+            lines.append("G92 E0")
+            e = 0.0
+        for kind in kinds:
+            lines.append(f";TYPE:{kind}")
+            if kind == "Outer wall":
+                lines += ["G0 X50 Y50", move(51.0, 50.0, level)]
+            else:
+                lines += ["G0 X10 Y10", move(11.0, 10.0, level), move(11.0, 11.0, level)]
+    return "\n".join(lines) + "\n"
+
+
+@pytest.mark.parametrize(("relative", "resets"), [(True, False), (False, False), (False, True)])
+def test_the_contact_measure_counts_extrusion_as_the_printer_does(
+    relative: bool, resets: bool
+) -> None:
+    """Dieselbe Bahn misst gleich, relativ, absolut und mit ``G92 E0`` (RM-624).
+
+    Die historischen Messleser kannten ``G92`` nicht: Nach dem Rücksetzen galt
+    jede Bahn als Leerfahrt, und unter absoluten Werten fehlten Kontakte.
+    """
+    measured = support_contact(_contact_gcode(relative, resets))
+
+    assert measured.top_cells > 0, "die Messung findet den Kontakt"
+    assert measured.top_gap == pytest.approx(0.2)
+    assert measured.top_interface_layers == pytest.approx(1.0)
+
+
+def _wall(levels: tuple[float, ...]) -> list[str]:
+    """Eine Wand in einer eigenen Zelle, je Ebene ein Strich: Sie gibt dem Modell
+    seine Schichthöhe von 0,2 mm."""
+    lines = [";TYPE:Outer wall"]
+    for level in levels:
+        lines += [f"G0 X50 Y50 Z{level}", "G1 X51 Y50 E0.05"]
+    return lines
+
+
+def test_the_contact_measure_follows_arcs() -> None:
+    """Ein Bogen zählt entlang seiner Bahn und führt die Position nach (RM-624).
+
+    Bambu Studio und PrusaSlicer biegen Wände und Bäume in ``G2``/``G3`` —
+    zehntausende Bögen je Baumdruck. Das Dach hier ist ein ``G3`` um (11; 11,5):
+    Es überspannt die Trennschicht bei (11; 7), seine Sehne nicht. Danach geht es
+    gerade weiter; vom Punkt vor dem Bogen aus liefe diese Bahn über die Falle bei
+    (13; 11), eine Trennschicht eine Ebene tiefer, die 0,4 statt 0,2 mm mäße.
+    Übergangene Bögen und Bögen als Sehne treffen die Falle, eine nicht
+    nachgeführte Position zählt zwei Zellen.
+    """
+    text = "\n".join(
+        [
+            "M83",
+            *_wall((0.2, 0.4, 0.6, 0.8, 1.0)),
+            ";TYPE:Support interface",
+            "G0 X10.5 Y6.5 Z0.6",
+            "G1 X11.5 Y7.5 E0.05",
+            "G0 X12.5 Y10.5 Z0.4",
+            "G1 X13.5 Y11.5 E0.05",
+            ";TYPE:Top surface",
+            "G0 X6 Y11.5 Z1.0",
+            "G3 X16 Y11.5 I5 J0 E0.8",
+            "G1 X17 Y11.5 E0.05",
+        ]
     )
 
+    measured = support_contact(text + "\n")
 
-def test_the_cura_gap_measure_reads_fractions_resets_and_the_ring() -> None:
-    """Die Messung selbst (RM-628), an einem kleinen G-Code nach Curas Art: Sockel
-    bis 3,0 mm, Stütze ab 3,6 (unten 0,4 Luft), oberste Stützbahn als Bruchteillage
-    bei 12,72 unter der Platte ab 13,0 (oben 0,28). Absolute Förderung mit
-    ``G92 E0`` zwischen den Lagen; Stütze am Rand außerhalb des Rings, Rand und
-    Fahrten ohne Förderung zählen nicht."""
-    lines = ["M82", "G92 E0"]
-    e = 0.0
+    assert measured.top_cells == 1, measured
+    assert measured.top_gap == pytest.approx(0.2), measured
 
-    def lay(kind: str, z: float, xs: tuple[float, ...]) -> None:
-        nonlocal e
-        lines.append(f";TYPE:{kind}")
-        for x in xs:
-            lines.append(f"G0 X{x} Y-10 Z{z}")
-            e += 0.1
-            lines.append(f"G1 X{x} Y10 E{e:.5f}")
-
-    walls = (-18.0, -10.0, 10.0, 18.0)
-    for step in range(15):
-        lay("WALL-OUTER", round(0.2 * (step + 1), 3), walls)
-    lay("SKIRT", 3.6, (-30.0, 30.0))
-    for step in range(46):
-        lay("SUPPORT", round(3.6 + 0.2 * step, 3), (-10.0, 10.0, 17.5))
-        lines.append("G92 E0")
-        e = 0.0
-    lay("SUPPORT-INTERFACE", 12.72, (-10.0, 10.0))
-    lines.append("G0 X-10 Y-10 Z12.9")
-    for step in range(10):
-        lay("SKIN", round(13.2 + 0.2 * step, 3), walls)
-    text = "\n".join(lines) + "\n"
-
-    measured = _cura_support_gaps(text, 0.2, (7.0, 14.0))
-    assert measured == _CuraGaps(top=0.28, bottom=0.4, top_points=40, bottom_points=40), measured
-    relative = text.replace("M82", "M83").replace("G92 E0\n", "")
-    assert _cura_support_gaps(relative, 0.2, (7.0, 14.0)).bottom == pytest.approx(0.4)
 
+@pytest.mark.parametrize("marked", [True, False], ids=["bahnhoehe", "ohne-bahnhoehe"])
+def test_the_contact_measure_takes_the_support_height_from_its_own_stack(marked: bool) -> None:
+    """Die Unterseite misst mit der Höhe der eigenen Stützbahn (RM-624).
 
-@pytest.mark.slicer("cura")
+    Auf einem Sockel bis 0,6 mm steht Stütze ab 1,16 mm, 0,28 mm hoch: 0,28 mm
+    Luft. Daneben eine Säule auf dem Bett mit Ebenen alle 0,28 mm — aus allen
+    Stützebenen zusammen gerechnet wäre die Stützlage auf 1,16 mm nur 0,04 mm
+    hoch, und die Unterseite mäße 0,52. Dazu eine Zelle, in der Wand und Stütze
+    nebeneinander stehen und ihre Ebenen sich abwechseln: kein Kontakt. Mit
+    ``;HEIGHT:`` wie die Orca-Familie und PrusaSlicer, ohne wie CuraEngine.
+    """
+    height = [";HEIGHT:0.28"] if marked else []
+    lines = ["M83", *_wall((0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6))]
+    for level in (0.2, 0.4, 0.6):
+        lines += [";TYPE:Top surface", f"G0 X10.5 Y10.5 Z{level}", "G1 X11.5 Y11.5 E0.05"]
+    for kind, level in (
+        ("Support interface", 1.16),
+        ("Support interface", 1.44),
+        ("Support", 1.72),
+    ):
+        lines += [f";TYPE:{kind}", *height, f"G0 X10.5 Y10.5 Z{level}", "G1 X11.5 Y11.5 E0.05"]
+    for level in (0.28, 0.56, 0.84, 1.12, 1.4):
+        lines += [";TYPE:Support", *height, f"G0 X30.5 Y30.5 Z{level}", "G1 X31.5 Y31.5 E0.05"]
+    for level in (0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6):
+        lines += [";TYPE:Inner wall", f"G0 X20.5 Y20.5 Z{level}", "G1 X21.5 Y21.5 E0.05"]
+    for level in (0.28, 0.56, 0.84, 1.12, 1.4):
+        lines += [";TYPE:Support", *height, f"G0 X20.5 Y20.5 Z{level}", "G1 X21.5 Y21.5 E0.05"]
+
+    measured = support_contact("\n".join(lines) + "\n")
+
+    assert measured.bottom_cells == 1, measured
+    assert measured.bottom_gap == pytest.approx(0.28), measured
+    assert measured.bottom_interface_layers == pytest.approx(2.0), measured
+
+
+def test_the_contact_measure_keeps_to_the_inside_of_the_model() -> None:
+    """``inset`` nimmt nur das Innere der Aufsicht, und ein Rand gehört nicht dazu (RM-624).
+
+    Ein Dach von 10 × 10 mm über zwei Trennschichtflecken, einer am Rand, einer
+    in der Mitte; vier Millimeter Abstand lassen nur die Mitte. Darunter ein
+    Rand, wie PrusaSlicer ihn schreibt (``;TYPE:Skirt/Brim``): Als Modell
+    gezählt, verbreiterte er die Aufsicht, und der Fleck am Rand zählte mit.
+    """
+    lines = ["M83", *_wall((0.2, 0.4, 0.6, 0.8, 1.0)), ";TYPE:Skirt/Brim"]
+    for row in range(7, 24, 2):
+        lines += [f"G0 X6.5 Y{row} Z0.2", f"G1 X23.5 Y{row} E0.5"]
+    lines += [";TYPE:Support interface"]
+    for x in (10.5, 14.5):
+        lines += [f"G0 X{x} Y14.5 Z0.6", f"G1 X{x + 1} Y15.5 E0.05"]
+    lines += [";TYPE:Top surface"]
+    for row in range(11, 20, 2):
+        lines += [f"G0 X10.5 Y{row} Z1.0", f"G1 X19.5 Y{row} E0.5"]
+
+    everywhere = support_contact("\n".join(lines) + "\n")
+    inside = support_contact("\n".join(lines) + "\n", inset=4.0)
+
+    assert everywhere.top_cells == 2, everywhere
+    assert inside.top_cells == 1, inside
+
+
+#: Was RM-622 an den Programmen gemessen hat und Solidons Tabellen behaupten
+#: (``advise.rounds_to_whole_layers``, ``slicer_keys.IGNORED_UNDER_TREES_BY_PROGRAM``).
+_CONTACT_PROGRAMS = (
+    "elegooslicer",
+    "orcaslicer",
+    "bambustudio",
+    "crealityprint",
+    "anycubicslicernext",
+    "prusaslicer",
+    "cura",
+)
+
+
+@pytest.mark.parametrize("style", ["grid", "tree"])
 @pytest.mark.parametrize(
-    ("style", "layer", "gap"),
-    [("grid", 0.2, 0.28), ("tree", 0.2, 0.44), ("grid", 0.28, 0.3), ("tree", 0.12, 0.28)],
+    ("program", "printer"),
+    [
+        pytest.param(program, PROGRAMS[program], marks=pytest.mark.slicer(program), id=program)
+        for program in _CONTACT_PROGRAMS
+    ],
 )
-def test_curas_support_gap_arrives_as_solidon_says(
+def test_the_support_contact_arrives_as_solidon_says(
+    program: str,
+    printer: str,
     style: str,
-    layer: float,
-    gap: float,
     installed_slicer: Path,
     tmp_path: Path,
     monkeypatch: pytest.MonkeyPatch,
 ) -> None:
-    """Cura druckt den Stützabstand, wie Solidon rät und anzeigt (RM-628).
-
-    Eine Platte über einer Säule auf einem Sockel, PETG, Werte fern des
-    Herstellers. CuraEngine rundet auf (``round_up_divide``): unter Gitter nur
-    unten, oben gilt der Abstand genau mit einer Bruchteillage der Stütze; unter
-    Bäumen oben und unten. Unter Gitter schreibt die Übergabe unten deshalb das
-    Vielfache im Band von PETG selbst (``support_bottom_distance``): 0,28 bei
-    0,2er Schichten druckt oben 0,28 und unten 0,2 statt 0,4, 0,30 bei 0,28er
-    Schichten unten 0,28 statt 0,56. 0,44 unter Bäumen druckt 0,6 — zur nächsten
-    Schicht gerundet wären es 0,4. Der Satz am Feld nennt den Wert, den Cura
-    unten druckt.
+    """Abstand und untere Trennschicht kommen an, wie Solidons Tabellen sagen (RM-624).
+
+    Eine Platte über einer Säule auf einem Sockel, PETG bei 0,2-mm-Schichten.
+    Unter Gitter gilt der Abstand (eigene Stützebenen), oben wie unten, mit
+    unteren Trennschichten. Unter organischen Bäumen rundet das Programm auf die
+    Schichten des Modells (RM-622), und Bambu Studio, Creality Print, Anycubic
+    Slicer Next und PrusaSlicer drucken dort keine untere Trennschicht. Ändert
+    ein neuer Slicerstand eine dieser Eigenschaften, wird der Test rot, und die
+    Tabelle zieht nach.
+
+    Kein Wert ist der des Herstellers — sonst bliebe ein verlorener Wert grün:
+    Die gewählten Prozesse führen 0,2 mm Abstand (Anycubic 0,1) und zwei untere
+    Trennschichten (PrusaSlicer 0, Anycubic „wie oben“). Unter Gitter 0,28 mm.
+    Unter Bäumen 0,44 mm, 2,2 Schichten: Ob ein Programm rundet oder abschneidet,
+    es druckt 0,4. Cura rundet auf, unter Gitter nur unten, und dort schreibt
+    die Übergabe das Vielfache im Band selbst (RM-628): Gitter oben 0,28 und
+    unten 0,2, Baum 0,6; der Feldsatz nennt den gedruckten Wert.
     """
     from app.core.slice import advise
     from app.ui.print_settings_dialog import _PlateJob, _prepare_plate
@@ -459,19 +500,21 @@ def test_curas_support_gap_arrives_as_solidon_says(
         part.apply_translation((0.0, 0.0, z))
         parts.append(part)
     body = SceneObject("stufe", "Stufe", MeshData.of(trimesh.boolean.union(parts)))
-    profile = profiles.make_profile(PROGRAMS["cura"], "petg")
+    profile = profiles.make_profile(printer, "petg")
     settings = print_settings.resolve(profile)
+    layer = 0.2
+    gap = 0.44 if style == "tree" else 0.28
+    bottom_layers = 3
     for path, value in (
         ("layers.layer_height", layer),
         ("support.style", style),
         ("support.placement", "everywhere"),
         ("support.z_gap", gap),
         ("support.interface_layers", 2),
-        ("support.bottom_interface_layers", 3),
+        ("support.bottom_interface_layers", bottom_layers),
     ):
         settings = print_settings.with_choice(settings, path, value)
     setup = _preselected(handover.detect(installed_slicer), profile)
-    assert setup.flavour == "cura", setup
     folder = tmp_path / "platte"
     folder.mkdir()
     job = _PlateJob(
@@ -498,16 +541,37 @@ def test_curas_support_gap_arrives_as_solidon_says(
         model_meshes=run.meshes,
         expected_tools=run.used_tools,
     )
-    # Vier Millimeter innerhalb des Plattenrands und drei außerhalb der Säule.
-    measured = _cura_support_gaps(
-        outcome.gcode_path.read_text(encoding="utf-8", errors="replace"), layer, (7.0, 14.0)
+    # Vier Millimeter vom Rand: Dort teilen sich Sockelwand und die Stütze
+    # daneben, die auf dem Bett steht, eine Rasterzelle.
+    measured = support_contact(
+        outcome.gcode_path.read_text(encoding="utf-8", errors="replace"), inset=4.0
     )
 
-    top, bottom = advise.printed_support_gaps(gap, layer, "cura", style, material=profile.material)
-    assert measured.top_points >= 10 and measured.bottom_points >= 10, measured
-    assert measured.top == pytest.approx(top, abs=0.02), measured
-    assert measured.bottom == pytest.approx(bottom, abs=0.02), measured
-    if style == "grid":
-        assert bottom == pytest.approx(layer), "unten eine Schicht, im Band von PETG"
-    said = slicer_keys.limitation("cura", "support.z_gap", settings, material=profile.material)
-    assert said is not None and said.values == {"gap": format_length(bottom)}, said
+    organic = handover.organic_styles(setup, profile)
+    # Was gedruckt ankommt, oben und unten (RM-628): organisch zur nächsten
+    # Schicht, Cura auf, unter Curas Gitter unten das Vielfache der Übergabe.
+    top, bottom = advise.printed_support_gaps(
+        gap, layer, setup.flavour, style, organic, profile.material
+    )
+    # Ohne Zellen sagt ein Median nichts, und eine Zusicherung über eine leere
+    # Menge bliebe grün (hier 57 bis 201 Zellen je Seite).
+    assert measured.top_cells > 20, f"kaum Kontakt unter der Platte: {measured}"
+    assert measured.bottom_cells > 20, f"kaum Stütze auf dem Sockel: {measured}"
+    assert measured.top_gap == pytest.approx(top, abs=0.02), measured
+    assert measured.bottom_gap == pytest.approx(bottom, abs=0.02), measured
+    if setup.flavour == "cura":
+        said = slicer_keys.limitation(
+            "cura", "support.z_gap", settings, material=profile.material
+        )
+        shown = top if style == "tree" else bottom
+        assert said is not None and said.values == {"gap": format_length(shown)}, said
+    skipped = handover.ignored_under_trees(style, organic, slicer_keys.program_of(setup.executable))
+    if "support.bottom_interface_layers" in skipped:
+        layers = 0
+    elif style == "grid" and setup.flavour == "orca":
+        # Unter Gitter legt die Orca-Familie die Kontaktlage dazu (``SupportCommon.cpp``,
+        # ``slicer_keys``). Genau gezählt: Mit ihrem Standard 2 druckte sie auch drei.
+        layers = bottom_layers + 1
+    else:
+        layers = bottom_layers
+    assert measured.bottom_interface_layers == layers, f"untere Trennschicht: {measured}"
```
