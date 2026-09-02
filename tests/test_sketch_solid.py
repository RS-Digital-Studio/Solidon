"""Aus einem Skizzenumriss ein Netz ziehen — gegen analytische Körper geprüft.

Das Gegenstück zu `app.core.brep.profiles.extrude`, für den Fall, dass kein
exakter Kern da ist oder der Körper ohnehin ein Netz ist. Geprüft wird gegen
Zahlen, die man ausrechnen kann, nicht gegen einen früheren Lauf: Volumen,
Hüllquader, Lage im Raum.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from app.core.geom.sketch_solid import ARC_STEPS, extrude_profile, outline_points
from app.core.sketch.planes import PlaneFrame
from app.core.sketch.profile import Profile, ProfileSegment

XY = PlaneFrame(
    origin=(0.0, 0.0, 0.0), x_axis=(1.0, 0.0, 0.0), y_axis=(0.0, 1.0, 0.0), normal=(0.0, 0.0, 1.0)
)
XZ = PlaneFrame(
    origin=(0.0, 0.0, 0.0), x_axis=(1.0, 0.0, 0.0), y_axis=(0.0, 0.0, 1.0), normal=(0.0, -1.0, 0.0)
)


def _rectangle(width: float, depth: float, at: tuple[float, float] = (0.0, 0.0)) -> Profile:
    x, y = at
    corners = [(x, y), (x + width, y), (x + width, y + depth), (x, y + depth)]
    return Profile(
        segments=tuple(
            ProfileSegment(kind="line", start=corners[index], end=corners[(index + 1) % 4])
            for index in range(4)
        ),
        circle=None,
        holes=(),
    )


def test_a_rectangle_becomes_exactly_its_box() -> None:
    """Der einfachste Fall, und der einzige, dessen Volumen exakt sein muss.

    Wo nichts gerundet wird, darf auch nichts abweichen: Ein Rechteck aus vier
    Strecken hat keine Sehne, die einen Kreis annähert.
    """
    solid = extrude_profile(_rectangle(10.0, 6.0), 4.0, XY)

    assert solid.volume == pytest.approx(240.0), "10 × 6 × 4"
    low, high = solid.bounds
    assert list(low) == pytest.approx([0.0, 0.0, 0.0])
    assert list(high) == pytest.approx([10.0, 6.0, 4.0])
    assert solid.is_watertight, "ein Werkzeug für eine Boolesche Operation muss dicht sein"


def test_a_circle_comes_close_enough_for_a_nozzle() -> None:
    """Ein Kreis wird zum Vieleck — die Frage ist nur, wie fein.

    Geprüft wird nicht die Zahl der Ecken, sondern was sie bedeutet: die
    Abweichung von der Kreisfläche. Bei zweiundsiebzig Ecken sind das gut
    0,1 Prozent, und die Düse eines FDM-Druckers ist 400 Mikrometer breit —
    der Fehler liegt drei Größenordnungen darunter.
    """
    profile = Profile(segments=(), circle=((0.0, 0.0), 5.0), holes=())
    solid = extrude_profile(profile, 3.0, XY)

    exact = math.pi * 25.0 * 3.0
    assert solid.volume == pytest.approx(exact, rel=0.002), (
        f"{ARC_STEPS} Ecken sollten den Kreis auf zwei Promille treffen"
    )
    assert solid.volume < exact, "ein einbeschriebenes Vieleck ist kleiner als sein Kreis"


def test_a_hole_in_the_outline_stays_a_hole() -> None:
    """Ein Loch im Umriss ist Material, das nicht entsteht.

    Ohne diese Zusage wäre die Tasche unter einem Ring ein voller Zylinder —
    und der Fehler fiele erst am fertigen Teil auf.
    """
    outer = _rectangle(20.0, 20.0)
    inner = _rectangle(5.0, 5.0, at=(7.0, 7.0))
    ring = Profile(segments=outer.segments, circle=None, holes=(inner,))

    solid = extrude_profile(ring, 2.0, XY)

    assert solid.volume == pytest.approx((400.0 - 25.0) * 2.0), "20×20 minus 5×5, zwei hoch"
    assert solid.is_watertight


def test_the_frame_decides_where_the_body_goes() -> None:
    """Auf einer Seitenwand gezeichnet wird nicht nach oben aufgezogen.

    Dieselbe Zusage, die der B-Rep-Weg über ``frame`` hält (§30.1) — auf XZ
    wächst der Körper nach −Y, und der Hüllquader sagt es.
    """
    solid = extrude_profile(_rectangle(10.0, 6.0), 4.0, XZ)

    low, high = solid.bounds
    assert list(low) == pytest.approx([0.0, -4.0, 0.0])
    assert list(high) == pytest.approx([10.0, 0.0, 6.0])
    assert solid.volume == pytest.approx(240.0), "gedreht ist dasselbe Volumen"


def test_a_negative_height_grows_the_other_way() -> None:
    """Die Tasche zieht nach unten, und zwar von der Ebene aus.

    Ohne das Vorzeichen läge das Werkzeug über dem Körper statt in ihm — die
    Differenz träfe nichts, und der Schritt liefe stumm durch.
    """
    solid = extrude_profile(_rectangle(4.0, 4.0), -3.0, XY)

    low, high = solid.bounds
    assert list(low) == pytest.approx([0.0, 0.0, -3.0])
    assert list(high) == pytest.approx([4.0, 4.0, 0.0])


def test_an_arc_follows_the_point_it_was_given() -> None:
    """Von Anfang zu Ende führen zwei Wege um den Kreis.

    Gemeint ist der, auf dem der Zwischenpunkt liegt. Ohne diese Unterscheidung
    schnitte ein Bogen gelegentlich das Gegenstück heraus — ein Fehler, der nur
    bei manchen Bögen auftritt und deshalb lange unentdeckt bliebe.
    """
    # Ein Halbkreis über der x-Achse: via liegt oben.
    upper = Profile(
        segments=(
            ProfileSegment(kind="arc", start=(-5.0, 0.0), end=(5.0, 0.0), via=(0.0, 5.0)),
            ProfileSegment(kind="line", start=(5.0, 0.0), end=(-5.0, 0.0)),
        ),
        circle=None,
        holes=(),
    )
    points = outline_points(upper)
    assert max(y for _, y in points) > 4.9, "der Bogen geht nach oben, wo via liegt"
    assert min(y for _, y in points) > -0.1, "und nicht nach unten"

    solid = extrude_profile(upper, 1.0, XY)
    assert solid.volume == pytest.approx(math.pi * 12.5, rel=0.01), "ein halber Kreis, 1 mm hoch"


def test_an_outline_without_area_says_so() -> None:
    """Drei Punkte auf einer Geraden schließen nichts ein.

    Ein leeres Werkzeug wäre eine Boolesche Operation ohne Wirkung — und die
    meldet erst die Stufe darüber, mit einem Satz über die falsche Sache.
    """
    flat = Profile(
        segments=(
            ProfileSegment(kind="line", start=(0.0, 0.0), end=(5.0, 0.0)),
            ProfileSegment(kind="line", start=(5.0, 0.0), end=(10.0, 0.0)),
        ),
        circle=None,
        holes=(),
    )
    with pytest.raises(ValueError, match="Fläche"):
        extrude_profile(flat, 2.0, XY)


# --- Und die Operation darüber: eine Tasche in einem Netz ----------------------
#
# **Bewusst hier und nicht in ``test_sketch_ops.py``.** Jene Datei überspringt
# sich vollständig, wenn OpenCASCADE fehlt (``pytestmark``) — und das ist genau
# die Lage, für die dieser Weg gebaut wurde. Ein Test, der dort läge, wäre auf
# jedem Rechner ohne B-Rep-Kern still übersprungen, also dort, wo er am meisten
# zusichert.


def _mesh_box(width: float, depth: float, height: float):
    """Ein Quader als Netz — der Körper, den ein Kunde einliest.

    **In X und Y um den Ursprung zentriert, in Z auf der Platte stehend.** Der
    erste Aufbau schob ihn ganz ins Positive, und dann traf die Tasche nur ein
    Viertel: ``shapes.rectangle`` legt seine Ecken auf ``±length/2``, sitzt
    also im Ursprung. Gemessen kamen 36 mm³ statt 144 — der Code hatte recht
    und der Prüfstand nicht.
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    box = trimesh.creation.box(extents=(width, depth, height))
    box.apply_translation((0.0, 0.0, height / 2.0))
    return MeshData.of(box)


def _pocket(entry, **params):
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    spec = REGISTRY.get("sketch_pocket")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}, parameters={}),
            inputs=[entry],
            params=spec.params(**params),
            profile=None,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_a_pocket_cuts_into_an_imported_mesh() -> None:
    """Der Kundenweg, der bis zum 30.08.2026 an einem Satz endete.

    „Der gewählte Körper besteht bereits aus festen Dreiecken" — und damit war
    Abtragen für jedes heruntergeladene Modell ausgeschlossen, also für den
    häufigsten aller Fälle. In Fusion geht es, und Robert hat genau danach
    gefragt.

    Geprüft wird das abgetragene **Volumen**, nicht die Zahl der Dreiecke: Was
    die Boolesche Rückfallkette an Netz liefert, hängt von ihrer Stufe ab, die
    entfernte Menge nicht.
    """
    from app.core.types import SceneObject

    body = SceneObject(id="obj_1", name="Teil", mesh=_mesh_box(40.0, 30.0, 10.0))
    assert body.mesh.volume == pytest.approx(12000.0)

    result = _pocket(body, shape="rectangle", length=6.0, width=6.0, depth=4.0)

    cut = result.outputs[0].mesh
    assert body.mesh.volume - cut.volume == pytest.approx(144.0, rel=0.01), "6 × 6 × 4"
    assert cut.is_watertight, "ein Teil mit einer Tasche bleibt druckbar"
    assert result.outputs[0].kind != "brep", "aus einem Netz wird kein exakter Körper"


def test_a_pocket_through_a_mesh_goes_all_the_way() -> None:
    """Durchgehend heißt durchgehend — auch am Netz.

    Ohne den Zuschlag an beiden Enden bliebe eine hauchdünne Haut stehen: Die
    Boolesche Differenz zweier Körper, die genau aneinander enden, ist an der
    Berührfläche nicht entschieden.
    """
    from app.core.types import SceneObject

    body = SceneObject(id="obj_1", name="Teil", mesh=_mesh_box(20.0, 20.0, 5.0))
    result = _pocket(body, shape="rectangle", length=4.0, width=4.0, depth=1.0, through=True)

    cut = result.outputs[0].mesh
    assert body.mesh.volume - cut.volume == pytest.approx(80.0, rel=0.02), "4 × 4 × 5 ganz durch"
    assert cut.is_watertight


def test_a_pocket_beside_the_mesh_says_so() -> None:
    """Eine Tasche, die den Körper verfehlt, läuft nicht stumm durch.

    Denselben Satz bekommt seit je, wer eine Magnettasche daneben setzt
    (``geom.boolean.without_effect``) — der Mesh-Weg erbt ihn, statt einen
    zweiten zu erfinden.
    """
    from app.core.types import SceneObject

    body = SceneObject(id="obj_1", name="Teil", mesh=_mesh_box(10.0, 10.0, 5.0))
    result = _pocket(body, shape="rectangle", length=2.0, width=2.0, depth=1.0, x=80.0, y=80.0)

    assert result.findings, "danebengesetzt, und niemand sagte etwas — das war der Fehler"
    assert any(
        "effect" in entry.code or "wirkung" in entry.code.lower() for entry in result.findings
    ), (
        f"der Befund sollte von der wirkungslosen Differenz sprechen: "
        f"{[entry.code for entry in result.findings]}"
    )


def test_the_pocket_reports_the_stage_of_the_union(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zwei Umrisse in einer Zeichnung: auch ihre Vereinigung meldet ihre Stufe.

    Der Mesh-Weg fährt die Rückfallkette **zweimal** — erst werden die
    Werkzeuge vereint, dann wird abgezogen —, und nur der zweite Lauf kam im
    Ergebnis an. Ein Werkzeug, das die Voxelstufe geglättet hat, schneidet eine
    gerundete Tasche, und der Verlauf behauptete dazu ``direct``; die Befunde
    der Vereinigung fielen mit weg (§17.2).
    """
    from app.core.geom import boolean as mesh_boolean
    from app.core.sketch.serialize import sketch_to_text
    from app.core.types import SceneObject, Sketch, SketchElement

    def square(size: float, at: tuple[float, float]) -> tuple[SketchElement, ...]:
        half = size / 2.0
        x, y = at
        corners = [
            (x - half, y - half),
            (x + half, y - half),
            (x + half, y + half),
            (x - half, y + half),
        ]
        return tuple(
            SketchElement(kind="line", points=(corners[index], corners[(index + 1) % 4]))
            for index in range(4)
        )

    chain = mesh_boolean.boolean

    def forced(kind: str, meshes: list, **options: Any):
        # Nur die Vereinigung der Werkzeuge wird auf die Voxelstufe gezwungen;
        # der Abzug danach läuft, wie er immer läuft.
        if kind == "union":
            options["stages"] = ("voxel",)
        return chain(kind, meshes, **options)

    monkeypatch.setattr(mesh_boolean, "boolean", forced)

    body = SceneObject(id="obj_1", name="Teil", mesh=_mesh_box(40.0, 30.0, 10.0))
    drawing = Sketch(
        plane="plane:xy", elements=square(8.0, (-10.0, 0.0)) + square(8.0, (10.0, 0.0))
    )
    result = _pocket(body, sketch=sketch_to_text(drawing), depth=4.0)

    assert result.solver is not None, "die Stufe der Vereinigung fiel ganz weg"
    assert result.solver.strategy == "voxel", (
        f"gemeldet wurde {result.solver.strategy} — die geglättete Vereinigung fehlt darin"
    )
    assert any(entry.code == "boolean.voxel" for entry in result.findings), (
        f"der Befund der Vereinigung fehlt: {[entry.code for entry in result.findings]}"
    )


def test_both_plane_tables_know_the_same_names() -> None:
    """Die Ebenennamen des exakten und des Netz-Wegs decken sich.

    ``sketch_pocket`` verlässt sich darauf: Kommt es bis zur Weiche und hat
    keinen Rahmen, dann baut es ihn aus dem Namen — und dass das gelingt, ist
    keine Annahme, sondern diese Zeile. Wer eine vierte Ebene in ``PLANES``
    einträgt und ``frame_for_plane`` vergisst, sieht es hier und nicht an einer
    Zusicherung im Kern.
    """
    from app.core.brep import profiles
    from app.core.sketch import planes as plane_table

    for name in sorted(profiles.PLANES):
        assert plane_table.frame_for_plane(name) is not None, (
            f"{name} steht in profiles.PLANES, aber frame_for_plane kennt es nicht"
        )


def test_the_mesh_path_works_without_the_optional_brep_kernel() -> None:
    """Ohne OpenCASCADE wird trotzdem geschnitten — der ganze Grund für dieses Modul.

    Der B-Rep-Kern ist eine **optionale** Abhängigkeitsgruppe
    (``brep = ["cadquery-ocp-novtk>=7.8"]`` in ``pyproject.toml``, §30). Wenn
    der Netz-Weg ihn heimlich doch bräuchte — über einen Import in
    ``sketch/ops.py``, über ``profiles.PLANES``, über irgendeine Hilfsfunktion
    dazwischen —, wäre er auf genau dem Rechner nutzlos, für den er gebaut
    wurde.

    Gemessen in einem eigenen Prozess, weil ``OCP`` in diesem hier längst
    geladen ist. Der erste Versuch sperrte über ``find_module`` und meldete den
    Kern als vorhanden: Python 3.12 hat die Methode abgeschafft, und eine
    Sperre, die niemand fragt, sperrt nichts.
    """
    import subprocess
    import sys
    from pathlib import Path

    script = """
import sys


class Sperre:
    def find_spec(self, name, path=None, target=None):
        if name == "OCP" or name.startswith("OCP."):
            raise ImportError(name + " fehlt auf diesem Rechner")
        return None


sys.meta_path.insert(0, Sperre())

import trimesh

from app.core.bootstrap import load_operations
from app.core.brep.kernel import available
from app.core.geom.mesh import MeshData
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Scene, SceneObject

assert not available(), "die Sperre hat nicht gegriffen — der Rest misst nichts"

load_operations()
box = trimesh.creation.box(extents=(40.0, 30.0, 10.0))
box.apply_translation((0.0, 0.0, 5.0))
entry = SceneObject(id="obj_1", name="Teil", mesh=MeshData.of(box))
spec = REGISTRY.get("sketch_pocket")
result = spec.fn(
    OpContext(
        scene=Scene(objects={entry.id: entry}, parameters={}),
        inputs=[entry],
        params=spec.params(shape="rectangle", length=6.0, width=6.0, depth=4.0),
        profile=None,
        quality="fine",
        seed=None,
        progress=lambda fraction, text: None,
        ask=lambda question, choices: choices[0],
        cancelled=NeverCancelled(),
    )
)
cut = entry.mesh.volume - result.outputs[0].mesh.volume
assert abs(cut - 144.0) < 2.0, cut
"""
    import app.core

    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
