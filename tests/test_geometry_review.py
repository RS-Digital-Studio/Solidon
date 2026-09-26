"""Die Fehlerbilder aus der Gesamtdurchsicht des Geometriekerns (25.08.2026).

Jedes gefundene Fehlerbild wird eine Testdatei und kein Sonderfall im Code
(`AGENTS.md`, Arbeitsweise). Diese hier hält neunzehn davon fest — sie liegen
über `app/core/geom/` verteilt und haben nur eines gemeinsam: Sie waren
**still**. Kein Absturz, keine Ausnahme, kein Befund; nur ein Ergebnis, das
etwas anderes war als das versprochene, und ein Nutzer, der es entweder im
Slicer bemerkt oder am gedruckten Teil.

Darum prüft fast jeder Test hier **Kennzahlen** gegen erwartete Werte statt
„läuft durch": Alle diese Fälle liefen durch.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import OperationCancelled
from app.core.geom import boolean as boolean_module
from app.core.geom import hollow as hollow_module
from app.core.geom import label_ops as label_module
from app.core.geom import lattice as lattice_module
from app.core.geom import lid as lid_module
from app.core.geom import pins as pins_module
from app.core.geom import prepare as prepare_module
from app.core.geom import texture_ops as texture_module
from app.core.geom.hollow import erosion_steps, hollow
from app.core.geom.lattice import _cavity_mesh
from app.core.geom.measure import ray_distances
from app.core.geom.mesh import MeshData, ray_hits, ray_hits_batch
from app.core.geom.orient import orient_for_print, print_transform
from app.core.geom.prepare import countersink, drill, open_sides, plug
from app.core.geom.primitive_ops import top_face_of
from app.core.geom.repair import fill_holes, open_edge_count, repair
from app.core.knowledge.parts.shapes import box as shape_box
from app.core.knowledge.parts.shapes import cylinder as shape_cylinder
from app.core.perceive.features import detect
from app.core.perceive.matching import moved_features
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.scene.placement import values_for
from app.core.slice.analysis import cross_section
from app.core.types import Feature, OpContext, Profile, Scene, SceneObject
from app.core.units import EPS_GEOM

load_operations()


# --- Werkzeuge ------------------------------------------------------------------


def cube(size: float = 40.0, standing: bool = False) -> MeshData:
    body = trimesh.creation.box(extents=(size, size, size))
    if standing:
        body.apply_translation((0.0, 0.0, size / 2.0))
    return MeshData.of(body)


def plate(width: float = 60.0, depth: float = 40.0, height: float = 10.0) -> MeshData:
    body = trimesh.creation.box(extents=(width, depth, height))
    body.apply_translation((0.0, 0.0, height / 2.0))
    return MeshData.of(body)


def run(op: str, entry: SceneObject, profile: Profile | None = None, **params: Any) -> Any:
    """Eine Operation so fahren, wie die Auswertung sie fährt."""
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def holes_in(mesh: MeshData, z: float) -> int:
    """Wie viele Löcher der Querschnitt auf dieser Höhe hat."""
    shape = cross_section(mesh, z)
    if shape is None:
        return 0
    return sum(len(part.interiors) for part in getattr(shape, "geoms", [shape]))


class CancelAfter:
    """Ein Abbruch, der nach ``count`` Abfragen zuschlägt.

    So misst der Test, ob die Operation überhaupt **fragt** — ein Token, das
    von Anfang an gesetzt ist, würde auch bei der einen Abfrage greifen, die es
    schon immer gab (der zwischen den Operationen).
    """

    def __init__(self, count: int) -> None:
        self.count = count
        self.asked = 0

    @property
    def is_cancelled(self) -> bool:
        return self.asked >= self.count

    def raise_if_cancelled(self) -> None:
        self.asked += 1
        if self.asked > self.count:
            raise OperationCancelled


# --- C-1: Senken senkt in die falsche Richtung ----------------------------------

#: Der Kegel eines 90-Grad-Senkkopfs Ø 8,4: πr²h/3 mit h = r, als 48-Eck
#: gerechnet also etwas weniger als die 77,6 der exakten Kreisform.
SINK_VOLUME = 76.81


@pytest.mark.parametrize(
    ("axis", "position"),
    [
        ("z", (0.0, 0.0, 20.0)),
        ("z", (0.0, 0.0, -20.0)),
        ("x", (20.0, 0.0, 0.0)),
        ("x", (-20.0, 0.0, 0.0)),
        ("y", (0.0, 20.0, 0.0)),
        ("y", (0.0, -20.0, 0.0)),
    ],
    ids=["z+", "z-", "x+", "x-", "y+", "y-"],
)
def test_a_countersink_cuts_into_the_body_from_every_face(
    axis: str, position: tuple[float, float, float], profile: Profile
) -> None:
    """An allen sechs Flächen dasselbe Volumen — vorher an dreien fast nichts.

    Die Richtung stand je Achse fest: entlang Z und X in die eine, entlang Y in
    die andere. An drei Flächen lag der Kegel damit außen und trug nur die
    Überlappung ab: 0,55 statt 76,8 mm³. Kein Befund, keine Ausnahme.
    """
    body = cube()

    result = countersink(body, position=position, axis=axis, diameter=8.4, profile=profile)

    removed = body.volume - result.mesh.volume
    assert removed == pytest.approx(SINK_VOLUME, abs=0.05), f"{axis} bei {position}"
    assert [finding.code for finding in result.findings] == []


def test_a_countersink_beside_the_body_says_so(profile: Profile) -> None:
    """Nichts abgetragen ist eine Auskunft (§2.7, Regel 17)."""
    result = countersink(
        cube(), position=(200.0, 0.0, 0.0), axis="z", diameter=8.4, profile=profile
    )

    assert "boolean.without_effect" in [finding.code for finding in result.findings]


def test_a_countersink_in_solid_material_says_so(profile: Profile) -> None:
    """Mitten im Material gibt es keine Mündung, nur einen Hohlraum."""
    result = countersink(cube(), position=(0.0, 0.0, 0.0), axis="z", diameter=8.4, profile=profile)

    assert "bore.sink_buried" in [finding.code for finding in result.findings]


def test_the_open_side_is_read_from_the_body_not_from_the_box() -> None:
    """Die Grundlage von C-1: wo ist Luft, wo Material."""
    body = cube()

    assert open_sides(body, "z", (0.0, 0.0, 20.0)) == (1.0,), "über der Oberseite ist Luft"
    assert open_sides(body, "z", (0.0, 0.0, -20.0)) == (-1.0,)
    assert open_sides(body, "z", (0.0, 0.0, 0.0)) == (), "mitten im Material ist beides zu"


# --- C-2: die Senkung landete in der Mitte der Bohrung --------------------------


def test_a_countersink_on_a_clicked_bore_sits_at_its_mouth(profile: Profile) -> None:
    """Die echte Vorbelegung aus ``placement.values_for``, Ende zu Ende.

    Ein angeklicktes Loch meldet seine **Mitte** — bei einer durchgehenden
    Bohrung in einer 12 mm dicken Platte also z = 0, sechs Millimeter unter der
    Oberfläche. Der Kegel lag dort ganz in der Bohrung und trug 0,0 mm³ ab; im
    Bild änderte sich nichts.
    """
    bored = drill(
        plate(40.0, 40.0, 12.0),
        position=(0.0, 0.0, 12.0),
        axis="z",
        diameter=5.2,
        profile=profile,
    ).mesh
    hole = next(entry for entry in detect(bored).values() if entry.kind == "hole")
    values = values_for(REGISTRY.get("countersink_hole"), hole)
    assert values["z"] == pytest.approx(6.0, abs=0.2), "die Vorbelegung ist die Mitte der Bohrung"

    result = countersink(
        bored,
        position=(values["x"], values["y"], values["z"]),
        axis=values["axis"],
        diameter=8.4,
        profile=profile,
    )

    removed = bored.volume - result.mesh.volume
    # Der Kegel minus dem, was die Bohrung schon weggenommen hatte — auf die
    # Mitte gesetzt lag er ganz in ihr und trug nichts ab.
    assert removed > 20.0, f"nur {removed:.2f} mm³ — der Kegel steckt in der Bohrung"
    assert holes_in(result.mesh, 11.5) == 1, "oben ist die Senkung offen"
    near_the_top = cross_section(result.mesh, 11.5)
    opening = next(iter(getattr(near_the_top, "geoms", [near_the_top]))).interiors[0]
    left, _bottom, right, _top = opening.bounds
    assert right - left > 7.0, "kurz unter der Fläche ist die Öffnung schon fast Kopfbreite"


def test_a_countersink_typed_onto_the_surface_stays_where_it_was(profile: Profile) -> None:
    """``anchor='centre'`` nimmt die Position wörtlich — sonst wäre das
    Verschieben eine stille Reparatur."""
    body = plate(40.0, 40.0, 12.0)

    at_mouth = countersink(body, position=(0.0, 0.0, 12.0), axis="z", diameter=8.4, profile=profile)
    verbatim = countersink(
        body, position=(0.0, 0.0, 12.0), axis="z", diameter=8.4, anchor="centre", profile=profile
    )

    assert at_mouth.mesh.volume == pytest.approx(verbatim.mesh.volume, abs=0.01)


# --- C-3/C-4: der Pinsel maß gegen Dreiecks-Schwerpunkte ------------------------
#
# **Der Gegenstand ist ausgebaut.** Vier Tests standen hier — zwei am
# Radius-Pinsel (``brush``), zwei an ``paint_slot`` mit Punkt und Radius.
# Seit dem Filament-Umbau färbt die Operation eine erkannte Fläche
# vollständig (``fill_feature``, Parameter ``slot`` und ``at_feature``);
# einen Radius gibt es nicht mehr, und ``brush`` auch nicht — die Datei
# brach deshalb schon beim Einsammeln ab und nahm die übrigen
# Durchsichtsbefunde mit.
#
# Die zwei Zusagen, die den Ausbau überlebt haben, stehen in
# ``tests/test_paint.py`` in der Form der neuen Operation: „nichts gefärbt
# ist kein Erfolg" (``test_a_feature_without_triangles_says_so``,
# ``test_an_unknown_feature_stops_with_advice``) und „die Zahl im Befund
# ist der Strich" (``test_filling_a_feature_paints_exactly_its_triangles``).
# Was hier stand, war der Weg dorthin und ist mit ihm gegangen.


# --- C-5: Ausrichten drehte, ohne die Drehung zu melden -------------------------


def test_orienting_for_print_reports_its_movement(profile: Profile) -> None:
    """Ohne ``transform`` muss die Zuordnung raten, und bei 90 Grad rät sie
    falsch: Merkmalskennungen wechseln, Passungen zeigen ins Leere (§21.2)."""
    body = trimesh.creation.box(extents=(10.0, 40.0, 60.0))
    body.apply_translation((0.0, 0.0, 30.0))
    entry = SceneObject(id="obj_1", name="Steher", mesh=MeshData.of(body))

    result = run("orient_for_print", entry, profile, thorough=False)

    assert result.transform is not None, "eine bewegende Operation meldet ihre Bewegung"
    matrix = np.asarray(result.transform, dtype=float)
    moved = np.asarray(entry.mesh.raw.copy().apply_transform(matrix).bounds, dtype=float)
    assert moved == pytest.approx(np.asarray(result.outputs[0].mesh.raw.bounds), abs=1e-6), (
        "die gemeldete Matrix muss die sein, die wirklich gefahren wurde"
    )


def test_the_reported_movement_matches_the_heuristic() -> None:
    """Dieselbe Matrix aus beiden Wegen — sonst laufen sie auseinander."""
    body = MeshData.of(trimesh.creation.box(extents=(10.0, 40.0, 60.0)))

    result = orient_for_print(body)

    assert result.transform == pytest.approx(print_transform(body, result.chosen.direction))


# --- C-6: die Entlüftung ging auch durch die Decke ------------------------------


def test_a_vent_goes_through_the_floor_and_not_through_the_ceiling() -> None:
    """Der Docstring sagte „nach unten durch den Boden", der Bohrer war so lang
    wie der ganze Körper plus vier Millimeter und lag mittig darüber: Aus einer
    Dose wurde ein Rohr."""
    result = hollow(cube(standing=True), 2.0, vents=1)

    assert holes_in(result.mesh, 1.0) == 1, "unten die Entlüftung"
    assert holes_in(result.mesh, 39.0) == 0, "oben nichts — die Decke bleibt zu"
    assert cross_section(result.mesh, 39.0).area == pytest.approx(1600.0, abs=0.5)


def test_the_vent_still_reaches_the_cavity() -> None:
    """Die Gegenprobe zum Test darüber: zu kurz wäre genauso falsch."""
    result = hollow(cube(standing=True), 2.0, vents=1)

    assert holes_in(result.mesh, 2.5) == 1, "die Entlüftung stößt in den Hohlraum durch"


# --- C-7: der Bericht widersprach sich ------------------------------------------


def half_open() -> MeshData:
    """Ein Würfel ohne Decke (zu groß zum Füllen) und mit einem fehlenden
    Bodendreieck (klein genug)."""
    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).subdivide().subdivide()
    normals = np.asarray(body.face_normals)
    keep = np.ones(len(body.faces), dtype=bool)
    keep[normals[:, 2] > 0.9] = False
    keep[int(np.flatnonzero(normals[:, 2] < -0.9)[0])] = False
    body.update_faces(keep)
    return MeshData.of(body)


def test_filling_holes_reports_filling_and_not_watertightness() -> None:
    """``fill_holes`` meldete „ist jetzt dicht" und hieß „hat gefüllt".

    Der Unterschied bleibt, auch wenn der Ringfüller seit dem 22.09.2026 beide
    Löcher dieses Körpers schließt: Gemessen wird an den offenen Kanten, nicht
    an der Dichtheit. Ein Körper, dessen Ringe sich nicht verketten lassen,
    wird gefüllt und bleibt offen — dafür steht der Rückgabewert.
    """
    mesh = half_open()
    before = open_edge_count(mesh)

    filled, changed = fill_holes(mesh)

    assert changed is True, "gefüllt wurde"
    assert open_edge_count(filled) < before
    assert open_edge_count(filled) == 0, "und hier reichte es bis zum geschlossenen Körper"


def test_repair_names_the_success_and_the_wide_hole(profile: Profile) -> None:
    """Eine Reparatur nennt Erfolg und Preis, ohne den Nutzer zurückzuschicken.

    Der Prüfling beginnt mit neunzehn offenen Kanten in zwei Ringen. Bis zum
    22.09.2026 schloss der Füller drei davon und ließ sechzehn stehen, und aus
    „Offene Stellen wurden geschlossen" allein wurde eine falsche
    Vollzugsmeldung; noch schlimmer war der Folgesatz „Kanten verfeinern
    schließt es" — diese Operation weist ein offenes Netz zurück und empfiehlt
    wieder Reparieren.

    Der Ringfüller schließt jetzt beide. Der Bericht sagt damit zweierlei: wie
    viele Löcher geschlossen wurden, und dass eine der Öffnungen groß genug
    war, um sie anzusehen — dort ist eine Fläche entstanden, die im Modell
    nicht war.
    """
    entry = SceneObject(id="obj_1", name="Halb offen", mesh=half_open())
    before = open_edge_count(entry.mesh)

    result = run(
        "repair", entry, profile, weld=False, degenerate=False, normals=False, fill_holes=True
    )

    codes = [finding.code for finding in result.findings]
    assert "repair.wide_hole_filled" in codes, "die große Öffnung steht als Warnung da"
    assert "repair.nothing_to_do" not in codes, "ein Widerspruch in derselben Liste"
    assert "repair.holes_filled" in codes
    filled = next(finding for finding in result.findings if finding.code == "repair.holes_filled")
    wide = next(finding for finding in result.findings if finding.code == "repair.wide_hole_filled")
    after = open_edge_count(result.outputs[0].mesh)
    # Gezählt werden Stellen, nicht Randkanten: zwei Ringe, zwei Löcher. Die
    # Kanten bleiben in den Werten für den Tooltip.
    assert filled.values == {"holes": 2, "before": before, "after": after}
    assert str(filled.message) == "2 Löcher wurden geschlossen."
    assert before > 0 and after == 0, "der Prüfling kommt geschlossen heraus"
    assert "repair.still_open" not in codes
    assert wide.severity == "warning" and wide.values["walls"] >= 1
    assert "Kanten verfeinern" not in str(wide.message)


def test_a_complete_hole_repair_counts_every_open_edge(profile: Profile) -> None:
    """Ein vollständiger Erfolg ist derselbe Bericht mit einem Rest von null."""
    body = cube().replacing(cube().raw.submesh([range(1, 12)], append=True))
    entry = SceneObject(id="obj_1", name="Ein Loch", mesh=body)
    before = open_edge_count(body)

    result = run(
        "repair", entry, profile, weld=False, degenerate=False, normals=False, fill_holes=True
    )

    filled = next(finding for finding in result.findings if finding.code == "repair.holes_filled")
    assert filled.values == {"holes": 1, "before": before, "after": 0}
    assert str(filled.message) == "Ein Loch wurde geschlossen."
    assert result.outputs[0].mesh.is_watertight
    assert "repair.still_open" not in [finding.code for finding in result.findings]


def test_a_healthy_mesh_still_says_nothing_to_do(profile: Profile) -> None:
    """Die Gegenprobe: der Satz darf nicht verschwinden."""
    entry = SceneObject(id="obj_1", name="Würfel", mesh=cube())

    result = run("repair", entry, profile)

    assert [finding.code for finding in result.findings] == ["repair.nothing_to_do"]


def test_repair_leaves_a_sound_mesh_unchanged(profile: Profile) -> None:
    """``changed`` heißt „hat sich geändert" — an einem gesunden Netz nichts."""
    result = repair(cube())

    assert result.changed is False
    assert result.mesh.volume == pytest.approx(cube().volume)


# --- C-8: aushöhlen mit Entlüftung, dann füllen war eine Sackgasse -------------


def test_a_vented_cavity_is_still_a_cavity() -> None:
    """Die Entlüftung verschweißt Innen- und Außenschale zu einer.

    ``_cavity_mesh`` zählte Schalen und fand eine — der Vorschlag lautete
    „Erst aushöhlen, dann füllen", also genau das, was der Nutzer gerade getan
    hatte.
    """
    sealed = hollow(cube(standing=True), 3.0, vents=0).mesh
    vented = hollow(cube(standing=True), 3.0, vents=1).mesh
    assert len(vented.raw.split(only_watertight=False)) == 1, "eine einzige Schale"

    # Seit RM-041 gibt ``_cavity_mesh`` dazu die Bohrungen, über die geschätzt
    # wurde — hier keine: Beide Körper tragen ihre Schnittgeometrie noch.
    (vented_cavity, over), (sealed_cavity, _none) = _cavity_mesh(vented), _cavity_mesh(sealed)
    assert vented_cavity is not None and sealed_cavity is not None
    assert over == ()
    assert np.asarray(vented_cavity.bounds.minimum) == pytest.approx(
        np.asarray(sealed_cavity.bounds.minimum), abs=0.6
    )
    assert np.asarray(vented_cavity.bounds.maximum) == pytest.approx(
        np.asarray(sealed_cavity.bounds.maximum), abs=0.6
    )


def test_a_vented_body_can_be_filled_with_a_lattice(profile: Profile) -> None:
    """Der Weg, an dem es hing: aushöhlen (Vorgabe: eine Entlüftung), füllen."""
    hollowed = hollow(cube(standing=True), 3.0, vents=1).mesh
    entry = SceneObject(id="obj_1", name="Dose", mesh=hollowed)

    result = run("lattice_fill", entry, profile, structure="cubic", cell=8.0, wall=1.2)

    assert [finding.code for finding in result.findings] == ["lattice.filled"]
    assert result.outputs[0].mesh.volume > hollowed.volume, "die Füllung trägt Material bei"


def test_a_solid_body_still_has_no_cavity() -> None:
    """Die Gegenprobe: der Vollkörper darf nicht plötzlich einen bekommen."""
    assert _cavity_mesh(cube()) == (None, ())


# --- C-9: eine Bewegung verlor zwei Felder --------------------------------------


def test_moving_a_feature_keeps_what_the_move_does_not_touch() -> None:
    """``created_by`` ist der Eintrag „diesen Schritt ändern" (§21.2), und
    ``recognised=False`` hält ein Bausteinmerkmal davon ab, an einer Erkennung
    gemessen zu werden, die es nie findet. Beides fiel bei jedem Verschieben weg.
    """
    feature = Feature(
        id="pin_1",
        kind="pin",
        provenance="generated",
        params={"centre": (1.0, 2.0, 3.0), "axis": (0.0, 0.0, 1.0), "diameter": 4.0},
        face_indices=(7, 8),
        recognised=False,
        created_by=12,
    )
    turn = (
        (0.0, -1.0, 0.0, 0.0),
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 5.0),
        (0.0, 0.0, 0.0, 1.0),
    )

    moved = moved_features({"pin_1": feature}, turn)["pin_1"]

    assert moved.created_by == 12
    assert moved.recognised is False
    assert moved.face_indices == (7, 8)
    assert moved.params["diameter"] == 4.0, "ein Durchmesser bewegt sich nicht"
    assert moved.params["centre"] == pytest.approx((-2.0, 1.0, 8.0))


# --- C-10: die stehende Wand und was der Befund darüber sagte ------------------


def test_the_hollow_finding_names_what_was_eroded() -> None:
    """Der Befund nannte den Sollwert. Bei 0,8 mm Wand erodiert das Raster
    dreimal 0,3, also 0,9 — und im Bericht stand 0,8."""
    result = hollow(cube(standing=True), 0.8, vents=0)

    done = next(entry for entry in result.findings if entry.code == "hollow.done")
    steps, pitch = erosion_steps(0.8)
    assert done.values["wall_mm"] == 0.8
    assert done.values["eroded_mm"] == pytest.approx(steps * pitch)
    assert done.values["eroded_mm"] != done.values["wall_mm"], "sonst prüft dieser Test nichts"
    assert done.values["tolerance_mm"] == pytest.approx(pitch / 2.0)


def test_a_wall_the_grid_cannot_hold_says_so() -> None:
    """Unter ``MIN_PITCH`` kommt das Raster nicht — dann ist das Versprechen
    ±1/6 nicht zu halten, und das gehört gesagt statt gerundet."""
    thin = hollow(cube(standing=True), 0.5, vents=0)
    fair = hollow(cube(standing=True), 2.0, vents=0)

    assert "hollow.coarse_grid" in [entry.code for entry in thin.findings]
    assert "hollow.coarse_grid" not in [entry.code for entry in fair.findings]


def test_the_erosion_stays_within_what_the_finding_promises() -> None:
    """Gemessen am Querschnitt: die wirklich stehende Wand liegt im gemeldeten
    Band."""
    for wall in (0.5, 0.8, 2.0):
        result = hollow(cube(standing=True), wall, vents=0)
        shape = cross_section(result.mesh, 20.0)
        ring = next(iter(getattr(shape, "geoms", [shape]))).interiors[0]
        left, _bottom, right, _top = ring.bounds
        standing = (40.0 - (right - left)) / 2.0

        done = next(entry for entry in result.findings if entry.code == "hollow.done")
        eroded = done.values["eroded_mm"]
        tolerance = done.values["tolerance_mm"]
        # Die gemeldeten Werte sind auf ein Tausendstel gerundet; genau darum
        # geht dieser Vergleich mit demselben Schritt.
        assert abs(standing - eroded) <= tolerance + 0.001, f"{wall}: {standing} vs {eroded}"


# --- C-11: der Stopfen saß mittig auf der Mündung ------------------------------


def test_a_plug_at_the_mouth_fills_the_depth_that_was_asked_for(profile: Profile) -> None:
    """Sechs Millimeter Tiefe, an der Mündung eingetippt: der Stopfen füllte
    drei und ragte drei heraus."""
    body = plate(40.0, 40.0, 12.0)
    bored = drill(
        body, position=(0.0, 0.0, 12.0), axis="z", diameter=6.0, depth=0.0, profile=profile
    ).mesh

    plugged = plug(
        bored, position=(0.0, 0.0, 12.0), axis="z", diameter=6.0, depth=6.0, profile=profile
    )

    assert plugged.mesh.bounds.maximum[2] == pytest.approx(12.0, abs=0.05), (
        "nichts steht über die Oberfläche hinaus"
    )
    added = plugged.mesh.volume - bored.volume
    # Gerechnet wird mit dem **gefüllten** Maß, nicht mit dem eingetippten:
    # Seit dem 26.08.2026 weitet der Stopfen wie die Bohrung um die
    # Materialtoleranz auf, sonst bliebe rings um ihn der Spalt stehen. Der
    # Nennradius stand hier fest, und damit hätte dieser Test die alte Lücke
    # festgeschrieben — geprüft ist die **Tiefe**, und die sagt der Name.
    radius = plugged.diameter / 2.0
    assert added == pytest.approx(math.pi * radius**2 * 6.0, rel=0.05), "sechs Millimeter voll"


def test_a_plug_by_its_centre_fills_only_half_of_it(profile: Profile) -> None:
    """Das Fehlerbild selbst, als Test: auf die Mündung zentriert füllt der
    Stopfen die Hälfte.

    Zu sehen ist es nicht daran, dass er heraussteht — er wird auf die
    Außenseite des Teils beschnitten (:func:`app.core.geom.prepare.shell`).
    Zu sehen ist es am Volumen, und genau deshalb fiel es niemandem auf.
    """
    bored = drill(
        plate(40.0, 40.0, 12.0),
        position=(0.0, 0.0, 12.0),
        axis="z",
        diameter=6.0,
        profile=profile,
    ).mesh

    centred = plug(
        bored,
        position=(0.0, 0.0, 12.0),
        axis="z",
        diameter=6.0,
        depth=6.0,
        anchor="centre",
        profile=profile,
    )

    radius = centred.diameter / 2.0
    assert centred.mesh.volume - bored.volume == pytest.approx(
        math.pi * radius**2 * 3.0, rel=0.06
    ), "die halbe Tiefe — das war die Vorgabe, bis anchor dazukam"


# --- C-12: ein Kragen, den es nicht gab -----------------------------------------


def tin() -> MeshData:
    return hollow(cube(standing=True), 3.0, vents=0, open_top=True).mesh


def test_a_lid_without_a_collar_has_no_collar_feature(profile: Profile) -> None:
    """Eine Passung misst sonst Geometrie, die es nicht gibt — und meldet sie
    als in Ordnung, denn die Zahlen im Merkmal stimmen ja."""
    entry = SceneObject(id="obj_1", name="Dose", mesh=tin())

    flat = run("create_lid", entry, profile, thickness=2.4, collar=0.0)
    with_collar = run("create_lid", entry, profile, thickness=2.4, collar=4.0)

    assert "lid_collar" not in flat.outputs[1].features
    assert "lid_collar" in with_collar.outputs[1].features


# --- C-13/C-14: die Stufe und die Qualität -------------------------------------


def test_hollowing_reports_the_fallback_stage(profile: Profile) -> None:
    """Bis zu sechs Boolesche Schnitte, und keiner meldete seine Stufe."""
    entry = SceneObject(id="obj_1", name="Klotz", mesh=cube(standing=True))

    result = run("hollow_object", entry, profile, wall=2.0, vents=1)

    assert result.solver is not None
    assert result.solver.strategy in boolean_module.FULL_CHAIN


def test_the_lid_reports_the_fallback_stage(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Dose", mesh=tin())

    result = run("create_lid", entry, profile, thickness=2.4, collar=4.0)

    # Nicht nur „irgendeine Stufe“: eine der Kette, und die zuletzt versuchte.
    assert result.solver is not None
    assert result.solver.strategy in boolean_module.FULL_CHAIN
    assert result.solver.attempted[-1] == result.solver.strategy


def test_the_screw_lid_reports_the_fallback_stage(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Dose", mesh=tin())

    result = run("screw_lid", entry, profile, height=8.0, pitch=2.0, wall=2.0, thickness=3.0)

    # Nicht nur „irgendeine Stufe“: eine der Kette, und die zuletzt versuchte.
    assert result.solver is not None
    assert result.solver.strategy in boolean_module.FULL_CHAIN
    assert result.solver.attempted[-1] == result.solver.strategy


def test_the_elephant_foot_reports_the_fallback_stage(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Klotz", mesh=cube(standing=True))

    result = run("compensate_first_layer", entry, profile, height=0.6, amount=0.2)

    # Nicht nur „irgendeine Stufe“: eine der Kette, und die zuletzt versuchte.
    assert result.solver is not None
    assert result.solver.strategy in boolean_module.FULL_CHAIN
    assert result.solver.attempted[-1] == result.solver.strategy


def test_splitting_with_pins_reports_the_fallback_stage(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Klotz", mesh=cube(standing=True))

    result = run("split_pinned", entry, profile, axis="z", position=20.0, pins=2)

    # Nicht nur „irgendeine Stufe“: eine der Kette, und die zuletzt versuchte.
    assert result.solver is not None
    assert result.solver.strategy in boolean_module.FULL_CHAIN
    assert result.solver.attempted[-1] == result.solver.strategy


@pytest.mark.parametrize(
    ("module", "op", "params"),
    [
        (hollow_module, "hollow_object", {"wall": 2.0, "vents": 0}),
        (lid_module, "create_lid", {"thickness": 2.4, "collar": 4.0}),
        (lid_module, "screw_lid", {"pitch": 3.0, "height": 8.0}),
        (pins_module, "split_pinned", {"axis": "z", "position": 20.0, "pins": 2}),
        (prepare_module, "compensate_first_layer", {"height": 0.6, "amount": 0.2}),
        (lattice_module, "lattice_fill", {"structure": "cubic", "cell": 8.0, "wall": 1.2}),
    ],
    ids=["hollow", "lid", "screw_lid", "pins", "elephant_foot", "lattice"],
)
def test_the_quality_setting_reaches_the_boolean_chain(
    module: Any, op: str, params: dict[str, Any], profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Checkliste Punkt 5: beide Qualitätsstufen bedienen.

    Diese fünf verdrahteten ``quality="fine"`` fest oder ließen die Vorgabe
    stehen — in Entwurfsqualität lief die volle Kette weiter, und §31 verlor
    genau dort seine Wirkung, wo eine Op teuer ist.
    """
    seen: list[str] = []
    # ``lattice`` importiert die Kette erst im Aufruf; dort muss die Quelle
    # ausgetauscht werden, sonst greift der Ersatz an einem Namen, den niemand
    # liest — und der Test wäre grün, ohne etwas zu messen.
    target = module if hasattr(module, "boolean") else boolean_module
    original = target.boolean

    def recording(kind: str, meshes: list[Any], **kwargs: Any) -> Any:
        seen.append(str(kwargs.get("quality", "fine")))
        return original(kind, meshes, **kwargs)

    monkeypatch.setattr(target, "boolean", recording)
    source = tin() if op in {"create_lid", "screw_lid", "lattice_fill"} else cube(standing=True)
    if op == "lattice_fill":
        source = hollow(cube(standing=True), 3.0, vents=0).mesh
    entry = SceneObject(id="obj_1", name="Teil", mesh=source)

    spec = REGISTRY.get(op)
    spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="draft",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )

    assert seen, "diese Operation ruft die Kette gar nicht — dann prüft der Test nichts"
    assert set(seen) == {"draft"}, f"{op} reicht die Qualität nicht durch: {seen}"


@pytest.mark.parametrize(
    ("module", "op", "params"),
    [
        (hollow_module, "hollow_object", {"wall": 2.0, "vents": 1}),
        (lattice_module, "lattice_fill", {"structure": "cubic", "cell": 8.0, "wall": 1.2}),
        (pins_module, "split_pinned", {"axis": "z", "position": 20.0, "pins": 2}),
        (lid_module, "create_lid", {"thickness": 2.4, "collar": 4.0}),
        (lid_module, "screw_lid", {"pitch": 3.0, "height": 8.0}),
        (label_module, "label_text", {"text": "I", "size": 6.0, "depth": 0.6, "z": 40.0}),
        (
            texture_module,
            "apply_texture",
            {"pattern": "rib", "width": 4.0, "height": 4.0, "pitch": 2.0, "z": 40.0},
        ),
    ],
    ids=["hollow", "lattice", "pins", "lid", "screw_lid", "label", "texture"],
)
def test_the_cancel_token_reaches_the_boolean_chain(
    module: Any, op: str, params: dict[str, Any], profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§15.6: der Abbruch reicht bis in die Rückfallkette.

    ``test_an_expensive_operation_can_be_stopped`` prüft nur, dass **gefragt**
    wird — und das taten die ``_step``-Aufrufe schon. Zwischen zweien von ihnen
    liegen aber bis zu vier boolesche Stufen samt Voxelisierung, und ``hollow``
    reichte ``cancelled`` an keinen seiner ``boolean``-Aufrufe weiter: dort stand
    der Abbrechen-Knopf minutenlang still. Gemessen wird am Token selbst, nicht
    an einer Wirkung — der Wert muss ankommen.
    """
    seen: list[Any] = []
    target = module if hasattr(module, "boolean") else boolean_module
    original = target.boolean

    def recording(kind: str, meshes: list[Any], **kwargs: Any) -> Any:
        seen.append(kwargs.get("cancelled"))
        return original(kind, meshes, **kwargs)

    monkeypatch.setattr(target, "boolean", recording)
    if op in {"create_lid", "screw_lid"}:
        source = tin()
    elif op == "lattice_fill":
        source = hollow(cube(standing=True), 3.0, vents=0).mesh
    else:
        source = cube(standing=True)
    entry = SceneObject(id="obj_1", name="Teil", mesh=source)
    token = NeverCancelled()

    spec = REGISTRY.get(op)
    spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="draft",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=token,
        )
    )

    assert seen, "diese Operation ruft die Kette gar nicht — dann prüft der Test nichts"
    assert all(entry is token for entry in seen), f"{op} reicht den Abbruch nicht durch: {seen}"


# --- C-15: teure Operationen ohne Abbruch ---------------------------------------


@pytest.mark.parametrize(
    ("op", "params", "source"),
    [
        ("hollow_object", {"wall": 2.0, "vents": 1}, "cube"),
        ("lattice_fill", {"structure": "cubic", "cell": 8.0, "wall": 1.2}, "hollow"),
    ],
    ids=["hollow", "lattice"],
)
def test_an_expensive_operation_can_be_stopped(
    op: str, params: dict[str, Any], source: str, profile: Profile
) -> None:
    """§15.6: was rechnet, fragt. ``blend_union`` rechnete 9,2 Sekunden, in
    denen der Abbrechen-Knopf nichts tat."""
    mesh = cube(standing=True) if source == "cube" else hollow(cube(standing=True), 3.0).mesh
    entry = SceneObject(id="obj_1", name="Teil", mesh=mesh)
    token = CancelAfter(1)
    spec = REGISTRY.get(op)

    with pytest.raises(OperationCancelled):
        spec.fn(
            OpContext(
                scene=Scene(objects={entry.id: entry}),
                inputs=[entry],
                params=spec.params(**params),
                profile=profile,
                quality="draft",
                seed=None,
                progress=lambda fraction, text: None,
                ask=lambda question, choices: choices[0],
                cancelled=token,
            )
        )
    assert token.asked > 1, "gefragt wird mehr als einmal"


def test_blending_asks_for_progress_and_can_be_stopped(profile: Profile) -> None:
    """Das Abstandsfeld ist die Zeit, nicht das Drumherum."""
    first = SceneObject(id="obj_1", name="A", mesh=cube(20.0))
    second = SceneObject(
        id="obj_2", name="B", mesh=MeshData.of(trimesh.creation.icosphere(radius=12.0))
    )
    steps: list[float] = []
    spec = REGISTRY.get("blend_union")

    def context(token: Any) -> OpContext:
        return OpContext(
            scene=Scene(objects={"obj_1": first, "obj_2": second}),
            inputs=[first, second],
            params=spec.params(radius=3.0, grid=2.0),
            profile=profile,
            quality="draft",
            seed=None,
            progress=lambda fraction, text: steps.append(fraction),
            ask=lambda question, choices: choices[0],
            cancelled=token,
        )

    spec.fn(context(NeverCancelled()))
    assert steps, "kein Fortschritt gemeldet"
    assert max(steps) <= 1.0 and min(steps) >= 0.0

    with pytest.raises(OperationCancelled):
        spec.fn(context(CancelAfter(1)))


# --- C-16: die Deckfläche der Grundformen --------------------------------------


def test_the_top_face_of_a_cylinder_is_a_circle_not_a_square() -> None:
    """Ø 20 sind 314 mm², nicht 400 — der Hüllquader ist kein Maß."""
    area, centre = top_face_of(shape_cylinder(20.0, 20.0))

    assert area == pytest.approx(math.pi * 100.0, rel=0.01)
    assert centre == pytest.approx((0.0, 0.0, 20.0), abs=1e-6)


def test_the_top_face_of_a_box_is_exact() -> None:
    area, centre = top_face_of(shape_box(40.0, 30.0, 10.0))

    assert area == pytest.approx(1200.0)
    assert centre == pytest.approx((0.0, 0.0, 10.0), abs=1e-6)


def test_a_sphere_has_no_flat_top(profile: Profile) -> None:
    """Ein Merkmal, das man anklicken und gegen das man eine Passung prüfen
    kann — mit einer Zahl, die es nicht gibt."""
    result = run("create_sphere", SceneObject(id="", name="", mesh=cube()), profile, diameter=20.0)

    assert result.outputs[0].features == {}


def test_a_cylinder_created_as_an_operation_reports_its_circle(profile: Profile) -> None:
    """Nicht nur die Hilfsfunktion — der Weg, den die Anwendung geht."""
    result = run(
        "create_cylinder",
        SceneObject(id="", name="", mesh=cube()),
        profile,
        diameter=20.0,
        height=20.0,
    )

    assert result.outputs[0].features["face_top"].params["area"] == pytest.approx(
        math.pi * 100.0, rel=0.01
    )


# --- C-19: zwei Epsilons für dieselbe Rechnung ---------------------------------


def test_a_sliver_triangle_is_still_hit_by_a_ray() -> None:
    """``EPS_GEOM`` sind Millimeter, die Determinante ist ein Spatprodukt.

    Sie wächst mit dem **Quadrat** der Kantenlänge: Ein Dreieck von zwei
    Zehntausendstel Millimeter — wie sie in heruntergeladenen Netzen zu
    Hunderten liegen — hat eine Determinante von 4e-8 und fiel damit unter
    1e-6 durch, obwohl der Strahl mitten hindurchgeht. ``ray_hit_distances``
    in ``mesh.py`` vergleicht mit ``RAY_PARALLEL_EPS``; hier stand dieselbe
    Rechnung mit einer Längenschranke, und ``wall_thickness`` maß daran vorbei.
    """
    edge = 2e-4
    sliver = trimesh.Trimesh(
        vertices=np.array([[0.0, 0.0, 0.0], [edge, 0.0, 0.0], [0.0, edge, 0.0]]),
        faces=np.array([[0, 1, 2]]),
        process=False,
    )
    assert edge * edge < 1e-6, "sonst prüft dieser Test die alte Schranke gar nicht"

    hits = ray_distances(
        MeshData.of(sliver), np.array([edge / 5, edge / 5, -1.0]), np.array([0.0, 0.0, 1.0])
    )

    assert len(hits) == 1, "der Strahl geht mitten hindurch"


# --- RM-050: der Bereichstest verzichtet auf VTK -------------------------------


def test_ray_hits_batch_answers_like_one_ray_hits_call_per_ray() -> None:
    """Viele Strahlen zugleich, dieselbe Antwort wie ``ray_hits`` einzeln je Strahl.

    :func:`ray_hits_batch` ersetzt VTKs ``vtkStaticCellLocator`` in der
    Wandstärkenmessung der Bereichsprüfung (``knowledge.parts.range_check.
    local_wall_thickness``, RM-050) — dieselbe Möller-Trumbore-Rechnung wie
    :func:`ray_hits`, nur über zwei Achsen zugleich und blockweise über die
    Dreiecke, damit der Speicher begrenzt bleibt.
    """
    rng = np.random.default_rng(23092026)
    sphere = trimesh.creation.icosphere(subdivisions=1)
    triangles = np.asarray(sphere.triangles, dtype=float)
    centres = np.asarray(sphere.triangles_center, dtype=float)
    normals = np.asarray(sphere.face_normals, dtype=float)
    origins = centres + rng.normal(scale=0.01, size=centres.shape)
    directions = -normals

    travel, hit_face = ray_hits_batch(
        triangles, origins, directions, edge_margin=EPS_GEOM, minimum_travel=EPS_GEOM * 100.0
    )

    assert travel.shape == (len(origins),)
    assert hit_face.shape == (len(origins),)
    for index in range(len(origins)):
        single_travel, single_faces = ray_hits(
            triangles,
            origins[index],
            directions[index],
            edge_margin=EPS_GEOM,
            minimum_travel=EPS_GEOM * 100.0,
        )
        if len(single_travel):
            best = int(np.argmin(single_travel))
            assert travel[index] == pytest.approx(float(single_travel[best]), abs=1e-9)
            assert int(hit_face[index]) == int(single_faces[best])
        else:
            assert travel[index] == float("inf")
            assert int(hit_face[index]) == -1


def _nearest_by_single_rays(
    triangles: np.ndarray, origins: np.ndarray, directions: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Die unabhängige Sollantwort: je Strahl ``ray_hits`` über alle Dreiecke.

    Gleiche Abstände entscheidet die kleinste Dreiecksnummer — ``ray_hits``
    liefert aufsteigende Nummern, ``np.argmin`` nimmt davon die erste.
    """
    travel = np.full(len(origins), np.inf)
    face = np.full(len(origins), -1, dtype=np.int64)
    for index, (origin, direction) in enumerate(zip(origins, directions, strict=True)):
        hits, faces = ray_hits(
            triangles, origin, direction, edge_margin=EPS_GEOM, minimum_travel=EPS_GEOM * 100.0
        )
        if len(hits):
            best = int(np.argmin(hits))
            travel[index] = hits[best]
            face[index] = faces[best]
    return travel, face


def test_the_spatial_preselection_of_ray_hits_batch_changes_no_bit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Vorauswahl der Dreiecke ändert weder Abstand noch Dreieck, nur den Aufwand.

    Ohne sie war die Wandstärke quadratisch: An der runden Dichtschnur mit
    45 000 Dreiecken (``test_seal_geometry``) rechnete sie zwei Milliarden
    Paare und über sechs Minuten. Geprüft wird bitgleich gegen einen Strahl
    je Aufruf an einer dünnen Kugelschale — innen und außen je 5120 Dreiecke,
    1 mm Wand —, mit Strahlen von der Wand nach innen, frei im Raum in alle
    Richtungen (auch an allem vorbei), auf Ecken der Außenhaut (gleiche
    Abstände an mehreren Dreiecken), mit ungleich langen Richtungen und einer
    ohne Richtung. Und der Aufwand wird gezählt: Rechnete die Vorauswahl
    alle Paare, wäre der Vergleich darüber keiner.
    """
    from app.core.geom import mesh as mesh_module

    rng = np.random.default_rng(24092026)
    outer = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
    inner = trimesh.creation.icosphere(subdivisions=4, radius=9.0)
    inner.invert()
    triangles = np.concatenate(
        (np.asarray(outer.triangles, dtype=float), np.asarray(inner.triangles, dtype=float))
    )
    wall = slice(0, len(outer.faces), 5)
    inward = (
        np.asarray(outer.triangles_center, dtype=float)[wall],
        -np.asarray(outer.face_normals, dtype=float)[wall],
    )
    free_origins = rng.random((120, 3)) * 30.0 - 15.0
    free_directions = rng.random((120, 3)) * 2.0 - 1.0
    corners = np.asarray(outer.vertices, dtype=float)[:40]
    origins = np.concatenate((inward[0], free_origins, np.zeros((40, 3)), [[0.0, 0.0, 0.0]]))
    directions = np.concatenate((inward[1], free_directions, corners, [[0.0, 0.0, 0.0]]))
    directions[::7] *= 3.0
    directions[1::7] *= 0.25

    evaluated = []
    parameters = mesh_module._ray_triangle_parameters

    def counted(*arguments: Any) -> tuple[np.ndarray, np.ndarray]:
        t, inside = parameters(*arguments)
        evaluated.append(t.size)
        return t, inside

    monkeypatch.setattr(mesh_module, "_ray_triangle_parameters", counted)
    travel, hit_face = ray_hits_batch(
        triangles, origins, directions, edge_margin=EPS_GEOM, minimum_travel=EPS_GEOM * 100.0
    )
    monkeypatch.setattr(mesh_module, "_ray_triangle_parameters", parameters)

    assert len(triangles) * len(origins) > mesh_module.RAY_CULL_PAIRS
    assert sum(evaluated) < len(triangles) * len(origins) / 2
    expected_travel, expected_face = _nearest_by_single_rays(triangles, origins, directions)
    assert np.isinf(expected_travel).any() and np.isfinite(expected_travel).any()
    assert np.array_equal(travel, expected_travel)
    assert np.array_equal(hit_face, expected_face)


def test_the_ray_preselection_leaves_non_finite_input_to_the_full_comparison() -> None:
    """Ein Ursprung, eine Richtung oder ein Dreieck mit NaN: dieselbe Antwort, keine Warnung.

    Die Vorauswahl rechnet Zellnummern aus Koordinaten; ein NaN darin wäre eine
    ``invalid value``-Warnung beim Umwandeln, wo der Vollvergleich still „kein
    Treffer" sagt. Solche Strahlen und Szenen gehen deshalb unverändert dorthin.
    """
    from app.core.geom import mesh as mesh_module

    sphere = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
    triangles = np.asarray(sphere.triangles, dtype=float)
    origins = np.asarray(sphere.triangles_center, dtype=float)[::20].copy()
    directions = -np.asarray(sphere.face_normals, dtype=float)[::20].copy()
    origins[3] = np.nan
    directions[5] = (np.nan, 0.0, 1.0)
    assert len(triangles) * len(origins) > mesh_module.RAY_CULL_PAIRS

    for scene in (triangles, np.concatenate((triangles, np.full((1, 3, 3), np.nan)))):
        travel, hit_face = ray_hits_batch(
            scene, origins, directions, edge_margin=EPS_GEOM, minimum_travel=EPS_GEOM * 100.0
        )
        expected_travel, expected_face = _nearest_by_single_rays(scene, origins, directions)
        assert np.array_equal(travel, expected_travel)
        assert np.array_equal(hit_face, expected_face)
        assert hit_face[3] == hit_face[5] == -1 and (hit_face >= 0).sum() > 200


def _inward_rays(subdivisions: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Eine volle Kugel, von jedem Dreieck einwärts: jeder Treffer liegt jenseits der Mitte."""
    sphere = trimesh.creation.icosphere(subdivisions=subdivisions, radius=10.0)
    return (
        np.asarray(sphere.triangles, dtype=float),
        np.asarray(sphere.triangles_center, dtype=float),
        -np.asarray(sphere.face_normals, dtype=float),
    )


def test_the_ray_index_answers_a_solid_body_with_few_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Vollkörper, von jedem Dreieck einwärts: dieselben Bits, ein Bruchteil der Paare.

    Hier war die frühere Vorauswahl nach Reichweite am schwächsten — der
    Treffer liegt auf der anderen Seite, jede Strahlgruppe berührte die halbe
    Kugel, und sie rechnete teurer als der Vollvergleich (RM-214: eine Kugel
    mit 12 800 Dreiecken 34 s). Der Index lässt jeden Strahl nur die Blätter
    rechnen, deren Quader er durchquert: an der Wand, von der er ausgeht, und
    an der, die er trifft.
    """
    from app.core.geom import mesh as mesh_module

    triangles, origins, directions = _inward_rays(4)
    assert len(triangles) * len(origins) > mesh_module.RAY_CULL_PAIRS
    evaluated = []
    parameters = mesh_module._ray_triangle_parameters

    def counted(*arguments: Any) -> tuple[np.ndarray, np.ndarray]:
        t, inside = parameters(*arguments)
        evaluated.append(t.size)
        return t, inside

    monkeypatch.setattr(mesh_module, "_ray_triangle_parameters", counted)
    travel, hit_face = ray_hits_batch(
        triangles, origins, directions, edge_margin=EPS_GEOM, minimum_travel=EPS_GEOM * 100.0
    )
    monkeypatch.setattr(mesh_module, "_ray_triangle_parameters", parameters)

    assert sum(evaluated) < len(triangles) * len(origins) / 20
    expected_travel, expected_face = _nearest_by_single_rays(triangles, origins, directions)
    assert np.isfinite(expected_travel).all()
    assert np.array_equal(travel, expected_travel) and np.array_equal(hit_face, expected_face)


def test_the_ray_index_splits_a_group_that_would_hold_too_many_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Über ``RAY_INDEX_PAIRS`` teilt sich die Gruppe, bis sie passt — dieselbe Antwort."""
    from app.core.geom import mesh as mesh_module

    triangles, origins, directions = _inward_rays(3)
    monkeypatch.setattr(mesh_module, "RAY_INDEX_PAIRS", 40)
    split = []
    candidates = mesh_module._index_candidates

    def counted(*arguments: Any) -> tuple[np.ndarray, np.ndarray] | None:
        found = candidates(*arguments)
        split.append(found is None)
        return found

    monkeypatch.setattr(mesh_module, "_index_candidates", counted)
    travel, hit_face = ray_hits_batch(
        triangles, origins, directions, edge_margin=EPS_GEOM, minimum_travel=EPS_GEOM * 100.0
    )
    assert any(split), "die Gruppe wurde nie geteilt — dann prüft dieser Test nichts"
    expected_travel, expected_face = _nearest_by_single_rays(triangles, origins, directions)
    assert np.array_equal(travel, expected_travel) and np.array_equal(hit_face, expected_face)


def test_a_cancelled_ray_index_stops_inside_its_descent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Abbruch endet in der laufenden Strahlgruppe, mit dem Teilstand und ohne Fehler.

    Gefragt wird je Gruppe und je Ebene des Baums: Die Bereichsprüfung muss
    mitten in ihrer ersten Ecke anhalten können
    (``test_range_check_cancels_inside_local_geometry_and_keeps_progress_monotonic``).
    """
    from app.core.geom import mesh as mesh_module

    triangles, origins, directions = _inward_rays(3)
    monkeypatch.setattr(mesh_module, "RAY_INDEX_RAYS", 64)
    asked = []

    class Token:
        @property
        def is_cancelled(self) -> bool:
            asked.append(True)
            return len(asked) > 25

        def raise_if_cancelled(self) -> None:
            raise AssertionError("der Index fragt, er wirft nicht")

    travel, hit_face = ray_hits_batch(
        triangles, origins, directions, edge_margin=EPS_GEOM, cancelled=Token()
    )
    assert travel.shape == hit_face.shape == (len(origins),)
    assert len(asked) == 26, "nach dem ersten Ja wurde weiter gefragt oder gerechnet"
    assert (hit_face < 0).any() and (hit_face >= 0).any()


def test_a_ray_along_a_box_wall_touches_the_box() -> None:
    """Liegt der Ursprung auf einer Quaderwand und läuft der Strahl in ihr, zählt er.

    Der Scheibentest rechnet dort ``0 · ∞`` — ``NaN``, und ein ``NaN`` im
    Maximum hätte den Quader still verworfen. Die Auswahl muss im Zweifel
    rechnen lassen, nie weglassen.
    """
    from app.core.geom import mesh as mesh_module

    low = np.zeros((4, 3))
    high = np.ones((4, 3))
    origins = np.array(
        [[0.5, 1.0, 0.5], [0.0, 0.5, 0.5], [0.5, 0.5, 1.0], [0.5, 2.0, 0.5]], dtype=float
    )
    directions = np.array(
        [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]], dtype=float
    )
    with np.errstate(divide="ignore"):
        inverse = 1.0 / directions
    touched = mesh_module._crossing(origins, inverse, low, high)
    assert touched.tolist() == [True, True, True, False]


def test_hits_behind_the_origin_are_never_preselected_away() -> None:
    """Ein negatives ``minimum_travel`` lässt Treffer hinter dem Ursprung zu — voll gerechnet.

    Die Vorauswahl sucht nur vorwärts. Der Prüfer fand dazu den Gegenfall:
    Vollvergleich ``(-3,0, Dreieck 0)``, Vorauswahl ``(20,0, Dreieck 1)``.
    """
    triangles, origins, directions = _inward_rays(3)
    travel, hit_face = ray_hits_batch(
        triangles, origins, directions, edge_margin=EPS_GEOM, minimum_travel=-5.0
    )
    expected_travel = np.full(len(origins), np.inf)
    expected_face = np.full(len(origins), -1, dtype=np.int64)
    for index, (origin, direction) in enumerate(zip(origins, directions, strict=True)):
        hits, faces = ray_hits(
            triangles, origin, direction, edge_margin=EPS_GEOM, minimum_travel=-5.0
        )
        if len(hits):
            best = int(np.argmin(hits))
            expected_travel[index], expected_face[index] = hits[best], faces[best]
    assert (expected_travel < 0).any(), "die Probe hat keinen Treffer hinter dem Ursprung"
    assert np.array_equal(travel, expected_travel) and np.array_equal(hit_face, expected_face)


def _triangle(*corners: tuple[float, float, float]) -> np.ndarray:
    return np.asarray(corners, dtype=float)


def test_each_safeguard_of_the_ray_preselection_decides_a_constructed_case() -> None:
    """Drei Fälle, deren Sollwert aus der Konstruktion kommt, nicht aus dem Prüfling.

    Der Zufallsvergleich darüber ist für eine Auswahl zu gutmütig; hier steht
    je Frage ein Strahl, an dem eine falsche Auswahl sichtbar würde:

    * **Das nächste, nicht das erste.** Eine große schräge Wand ``B`` ragt in
      jeden Quader längs des Strahls und wird erst in ``2R`` getroffen; das
      kleine Dreieck ``A`` liegt in ``1,5R`` davor. Wer den ersten gefundenen
      Treffer nähme, meldete ``B``.
    * **Derselbe Aufbau näher:** ``A3`` in ``0,6R``, ``B`` in ``0,7R``.
    * **Randzugabe.** Der Strahl geht ein halbes Millionstel neben der Kante
      von ``C`` vorbei — innerhalb von ``edge_margin``, also ein Treffer, aber
      außerhalb des ungewachsenen Hüllquaders von ``C``.

    ``R`` ist eine feste Länge, ein Zweiunddreißigstel der Szenendiagonale,
    die zwei Ankerdreiecke festlegen. Eine Kugel daneben mit Strahlen von
    ihrer Wand bringt die Paare über ``RAY_CULL_PAIRS``.
    """
    from app.core.geom import mesh as mesh_module

    reach = 100.0 * math.sqrt(3.0) / 32.0
    wall_x = 2.0 * reach
    filler = trimesh.creation.icosphere(subdivisions=4, radius=5.0)
    filler.apply_translation((-35.0, -35.0, -35.0))
    shift = 0.5e-6
    special = [
        _triangle((-50.0, -50.0, -50.0), (-49.9, -50.0, -50.0), (-50.0, -49.9, -50.0)),
        _triangle((50.0, 50.0, 50.0), (49.9, 50.0, 50.0), (50.0, 49.9, 50.0)),
        # B: die Ebene x = wall_x + y/2, von jedem Suchquader um y = 0 berührt.
        _triangle((wall_x - 20.0, -40.0, -40.0), (wall_x + 20.0, 40.0, -40.0), (wall_x, 0.0, 40.0)),
        # A: klein, quer zum ersten Strahl bei x = 1,5R.
        _triangle((1.5 * reach, -1.0, -1.0), (1.5 * reach, 1.0, -1.0), (1.5 * reach, 0.0, 1.0)),
        # A3: klein, quer zum zweiten Strahl, 0,6R hinter dessen Ursprung.
        _triangle(
            (wall_x - 0.1 * reach, -1.0, 19.0),
            (wall_x - 0.1 * reach, 1.0, 19.0),
            (wall_x - 0.1 * reach, 0.0, 21.0),
        ),
        # C: um ``shift`` neben dem dritten Strahl, in z = 3.
        _triangle((30.0 + shift, 30.0, 3.0), (31.0 + shift, 30.0, 3.0), (30.0 + shift, 31.0, 3.0)),
    ]
    triangles = np.concatenate((np.stack(special), np.asarray(filler.triangles, dtype=float)))
    face_a, face_a3, face_c = 3, 4, 5
    wall = slice(0, len(filler.faces), 25)
    origins = np.concatenate(
        (
            [[0.0, 0.0, 0.0], [wall_x - 0.7 * reach, 0.0, 20.0], [30.0, 30.5, 0.0]],
            np.asarray(filler.triangles_center, dtype=float)[wall],
        )
    )
    directions = np.concatenate(
        (
            [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            -np.asarray(filler.face_normals, dtype=float)[wall],
        )
    )
    assert len(triangles) * len(origins) > mesh_module.RAY_CULL_PAIRS

    travel, hit_face = ray_hits_batch(
        triangles, origins, directions, edge_margin=EPS_GEOM, minimum_travel=EPS_GEOM * 100.0
    )

    assert hit_face[:3].tolist() == [face_a, face_a3, face_c]
    assert travel[:3] == pytest.approx([1.5 * reach, 0.6 * reach, 3.0])
    expected_travel, expected_face = _nearest_by_single_rays(triangles, origins, directions)
    assert np.array_equal(travel, expected_travel)
    assert np.array_equal(hit_face, expected_face)


# --- C-22: der tote Zweig verwarf die Befunde des Stiftplans -------------------


def test_splitting_says_why_there_are_no_pins(profile: Profile) -> None:
    """Verlangt wurden Stifte, geliefert zwei glatte Hälften — mit einem Wort.

    ``plan_pins`` sagt, warum aus zwei verlangten Stiften keiner wurde. Die
    Befunde gingen im ``else``-Zweig von ``_cut_and_pin`` verloren, der nach
    dem Vertrag von §9 nie laufen konnte (``ctx.profile`` ist keine Option).
    Der Zweig ist weg; dieser Test hält fest, dass die Sätze ankommen.
    """
    small = trimesh.creation.box(extents=(6.0, 6.0, 6.0))
    small.apply_translation((0.0, 0.0, 3.0))
    entry = SceneObject(id="obj_1", name="Klötzchen", mesh=MeshData.of(small))

    result = run("split_pinned", entry, profile, axis="z", position=3.0, pins=2)

    assert "split.face_too_small" in [finding.code for finding in result.findings]
    assert len(result.outputs) == 2, "getrennt wurde trotzdem"


def test_splitting_a_body_that_can_hold_pins_really_sets_them(profile: Profile) -> None:
    """Die Gegenprobe: passt es, entstehen Stifte und kein Hinweis."""
    entry = SceneObject(id="obj_1", name="Klotz", mesh=cube(standing=True))

    result = run("split_pinned", entry, profile, axis="z", position=20.0, pins=2)

    assert not [finding for finding in result.findings if finding.code.startswith("split.")], (
        "kein Hinweis, wo alles passt"
    )
    assert result.outputs[0].features, "die Hälfte mit den Stiften trägt Merkmale"


def test_a_feature_survives_being_moved_through_the_registry() -> None:
    """Zur Sicherheit über ``replace``: ein Feld, das später dazukommt, reist
    von selbst mit."""
    feature = Feature(id="f", kind="face", provenance="detected", params={"area": 5.0})

    moved = moved_features({"f": feature}, np.eye(4).tolist())["f"]

    assert moved == replace(feature, params=dict(feature.params))


def _ring_and_ell() -> list[tuple[str, MeshData]]:
    """Ein Ring und ein L — zwei Körper, deren Hohlraum die Mitte seines Hüllquaders nicht hat."""
    import trimesh as _trimesh

    from app.core.geom.boolean import boolean

    ring = _trimesh.creation.torus(
        major_radius=30.0, minor_radius=10.0, major_sections=64, minor_sections=32
    )
    ring.apply_translation((0.0, 0.0, 10.0))
    first = _trimesh.creation.box(extents=(60.0, 20.0, 20.0))
    first.apply_translation((0.0, -20.0, 10.0))
    second = _trimesh.creation.box(extents=(20.0, 60.0, 20.0))
    second.apply_translation((-20.0, 0.0, 10.0))
    ell = boolean("union", [MeshData.of(first), MeshData.of(second)]).mesh
    return [("Ring", MeshData.of(ring)), ("L", ell)]


@pytest.mark.parametrize("vents", [1, 2])
@pytest.mark.parametrize("index", [0, 1], ids=["ring", "ell"])
def test_every_vent_opens_the_cavity_it_is_counted_for(vents: int, index: int) -> None:
    """Eine gesetzte Entlüftung öffnet den Hohlraum — auch an einem Ring und einem L.

    Die Stellen lagen auf einer Linie durch die Mitte des Hüllquaders, und dort
    ist bei einem Ring das Loch in der Mitte, bei einem L der freie Winkel. Der
    Bohrer traf Luft, der Bericht zählte ihn trotzdem als Entlüftung, und der
    Hohlraum blieb geschlossen (gemessen 22.09.2026: Ring mit einer und zwei
    Entlüftungen, L mit einer — zwei Schalen, kein ``hollow.no_vent``). Beim
    FDM-Druck drückt ein geschlossener Hohlraum die Decke hoch, beim Harzdruck
    bleibt das Harz darin.
    """
    name, body = _ring_and_ell()[index]

    result = hollow(body, 2.0, vents=vents)

    shells = len(result.mesh.raw.split(only_watertight=False))
    assert shells == 1, f"{name}: der Hohlraum ist noch geschlossen ({shells} Schalen)"
    assert len(result.vents) == vents
    assert "hollow.no_vent" not in {finding.code for finding in result.findings}
