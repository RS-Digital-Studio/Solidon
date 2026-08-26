"""Der Pinsel (Bauplan §20, „Bemalen").

Das ganze Feature ist ein Satz — einen Slot auf die Flächen um einen Punkt
legen — und ein schwerer Teil: an Kanten anhalten. Ohne das läuft die Farbe um
die Ecke auf die Rückseite des Teils, und das aufzuräumen kostet mehr, als das
Malen gespart hat. Also misst der größte Teil dieser Datei genau das.
"""

from __future__ import annotations

import pytest
import trimesh
from PySide6.QtWidgets import QApplication

from app.core.geom.attributes import counts, used_slots
from app.core.geom.mesh import MeshData
from app.core.geom.paint import EDGE_ANGLE, brush
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject
from app.ui.paint_bar import PaintBar


def plate() -> MeshData:
    body = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    body.apply_translation((0.0, 0.0, 5.0))
    return MeshData.of(body)


def ball(subdivisions: int = 3) -> MeshData:
    return MeshData.of(trimesh.creation.icosphere(subdivisions=subdivisions, radius=20.0))


def run(op: str, entry: SceneObject, profile: Profile, **params: object):
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


# --- die Kante ------------------------------------------------------------------


def test_the_brush_stops_at_an_edge_however_wide_it_is() -> None:
    """Der Punkt der ganzen Sache: ein Radius allein malt um die Ecke."""
    painted = brush(plate(), (0.0, 0.0, 10.0), radius=1000.0, slot=1)

    assert counts(painted.mesh) == {0: 10, 1: 2}, "the top face, and nothing else"
    assert painted.painted == 2, "der Befund zählt den Strich, nicht den Bestand"


def test_a_wide_enough_angle_paints_over_everything() -> None:
    painted = brush(plate(), (0.0, 0.0, 10.0), radius=1000.0, slot=1, edge_angle=180.0)

    assert used_slots(painted.mesh) == (1,)


def test_on_a_smooth_surface_the_radius_is_what_decides() -> None:
    """Eine Kugel hat keine Kanten — der Pinsel ist also wieder ein Kreis, wie
    erwartet.
    """
    sphere = ball()

    small = brush(sphere, (0.0, 0.0, 20.0), radius=5.0, slot=1).painted
    large = brush(sphere, (0.0, 0.0, 20.0), radius=12.0, slot=1).painted

    assert 0 < small < large < sphere.triangle_count


def test_painting_does_not_move_a_single_point() -> None:
    """§20: der Slot ist ein Attribut. Farbe ist keine Geometrie."""
    before = plate()

    painted = brush(before, (0.0, 0.0, 10.0), radius=20.0, slot=2)

    assert painted.mesh.raw is before.raw
    assert painted.mesh.volume == before.volume


def test_a_second_stroke_does_not_undo_the_first() -> None:
    once = brush(plate(), (0.0, 0.0, 10.0), radius=1000.0, slot=1)

    twice = brush(once.mesh, (0.0, 0.0, 0.0), radius=1000.0, slot=2)

    assert used_slots(twice.mesh) == (0, 1, 2), "top, bottom and the sides in between"


# --- Als Operation ---------------------------------------------------------------


def test_painting_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Deckel", mesh=plate())

    result = run("paint_slot", entry, profile, slot=1, radius=1000.0, z=10.0, name="Rot")

    output = result.outputs[0]
    assert used_slots(output.mesh) == (0, 1)
    assert [slot.name for slot in output.material_slots] == ["Rot"]
    assert [finding.code for finding in result.findings] == ["colour.painted"]


def test_a_stroke_that_hits_nothing_says_so(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Deckel", mesh=plate())

    result = run("paint_slot", entry, profile, slot=1, radius=0.5, x=500.0, y=500.0, z=500.0)

    assert result.outputs[0] is entry, "nothing changed, so nothing is replaced"
    assert [finding.code for finding in result.findings] == ["colour.nothing_painted"]


def test_the_slot_keeps_the_name_it_was_given(profile: Profile) -> None:
    """Ein zweiter Strich in denselben Slot darf ihn nicht umbenennen."""
    entry = SceneObject(id="obj_1", name="Deckel", mesh=plate())
    first = run("paint_slot", entry, profile, slot=1, radius=1000.0, z=10.0, name="Rot").outputs[0]

    second = run("paint_slot", first, profile, slot=1, radius=1000.0, z=0.0).outputs[0]

    assert [slot.name for slot in second.material_slots] == ["Rot"]


def test_no_fallback_colour_can_be_mistaken_for_the_selection() -> None:
    """Roberts Befund vom 26.08.2026, als Zusage: Die erste Bemalung, die je
    ein Kunde sah, war ein Orange mit Kontrast 1,09 zur Auswahlfarbe — bemalt
    und ausgewählt waren dasselbe Bild.

    Die Leiter ist seitdem grau (Konzept Filamente); echte Farben kommen vom
    Kunden. Geprüft werden die drei Abstände, an denen die alte Palette
    scheiterte: zur Auswahl, zur Körperfarbe, und der Stufen untereinander —
    zwei farblose Filamente, die gleich aussehen, zeigen ihr Teil erst im
    Slicer zweifarbig.
    """
    from itertools import combinations

    from app.ui.theme import SLOT_COLOURS, contrast_ratio
    from app.ui.viewport import OBJECT_COLOUR

    def spread(colour: str) -> int:
        """Wie bunt eine Farbe ist: der Abstand ihres größten und kleinsten
        Kanals. Null ist reines Grau, die Auswahlfarbe liegt bei 166."""
        channels = [int(colour[index : index + 2], 16) for index in (1, 3, 5)]
        return max(channels) - min(channels)

    for colour in SLOT_COLOURS:
        # Nicht über die Helligkeit gemessen, sondern über die Buntheit: Ein
        # Grau und ein sattes Orange gleicher Helligkeit sind klar zu
        # unterscheiden — der alte Fehler war gleicher Ton UND gleiche
        # Helligkeit. Die Leiter bleibt unbunt, die Auswahl ist es nie.
        assert spread(colour) <= 24, (
            f"{colour} ist keine Graustufe mehr — bunt gehört dem Kunden und der Auswahl"
        )
        assert contrast_ratio(colour, OBJECT_COLOUR) >= 1.25, (
            f"{colour} liegt zu nah an der Körperfarbe — Färben wäre unsichtbar"
        )
    for first, second in combinations(SLOT_COLOURS, 2):
        assert contrast_ratio(first, second) >= 1.1, (
            f"{first} und {second} sind im Bild nicht zu unterscheiden"
        )


# --- die Merkmal-Füllung (Konzept Filamente, 26.08.2026) --------------------------


def _with_top_face(entry: SceneObject, indices: tuple[int, ...]) -> SceneObject:
    """Das Objekt mit einem erkannten Flächenmerkmal über ``indices``."""
    import dataclasses

    from app.core.types import Feature

    face = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"area": 1600.0},
        face_indices=indices,
    )
    return dataclasses.replace(entry, features={"face_1": face})


def test_filling_a_feature_paints_exactly_its_triangles(profile: Profile) -> None:
    """Der Kern des Umbaus: Rechtsklick auf „Oberseite" färbt die Oberseite.

    Kein Radius, kein Klickpunkt — die Dreiecke kommen aus dem Merkmal
    (``face_indices``), und damit wandert die Färbung mit, wenn ein früherer
    Schritt die Maße ändert. Ein gespeicherter Punkt läge dann daneben.
    """
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1, 4))

    result = run("paint_slot", entry, profile, slot=2, at_feature="face_1", name="Weiß")

    slots = result.outputs[0].mesh.slots
    assert slots is not None
    painted = {index for index, slot in enumerate(slots) if slot == 2}
    assert painted == {0, 1, 4}, "genau die Dreiecke des Merkmals, keines mehr, keines weniger"
    assert [finding.code for finding in result.findings] == ["colour.painted"]
    assert [slot.name for slot in result.outputs[0].material_slots] == ["Weiß"]


def test_an_unknown_feature_stops_with_advice(profile: Profile) -> None:
    """Ein Merkmal, das es am Körper nicht gibt, ist ein Halt mit Vorschlag —
    nicht ein stilles Nichtstun und nicht ein Rückfall auf irgendeinen Punkt."""
    from app.core.errors import ValidationError

    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))

    with pytest.raises(ValidationError) as raised:
        run("paint_slot", entry, profile, slot=1, at_feature="face_99")

    assert raised.value.suggestions, "Regel 17: auch diese Ausnahme trägt Handlungen"
    assert raised.value.values.get("feature") == "face_99"


def test_a_feature_without_triangles_says_so(profile: Profile) -> None:
    """Eine offene Kantenschleife hat keine eigenen Dreiecke — gefärbt wird
    nichts, und das steht als Befund da statt als stiller Erfolg."""
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), ())

    result = run("paint_slot", entry, profile, slot=1, at_feature="face_1")

    assert result.outputs[0] is entry, "nothing changed, so nothing is replaced"
    assert [finding.code for finding in result.findings] == ["colour.nothing_painted"]


# --- die Leiste -----------------------------------------------------------------


def test_the_bar_is_off_until_somebody_switches_it_on(qt_app: QApplication) -> None:
    """Ein Modell zu bemalen, das jemand drehen wollte, ist kein Fehler, den
    ein Undo deckt.
    """
    bar = PaintBar()

    assert not bar.painting


def test_the_bar_reports_being_switched(qt_app: QApplication) -> None:
    bar = PaintBar()
    seen: list[bool] = []
    bar.paintingToggled.connect(seen.append)

    bar.active.setChecked(True)

    assert seen == [True]
    assert bar.painting


def test_the_bar_hands_over_what_a_stroke_is_made_of(qt_app: QApplication) -> None:
    bar = PaintBar()
    bar.slot.setValue(3)
    bar.radius.setValue(7.5)

    assert bar.values() == {"slot": 3, "radius": 7.5, "edge_angle": pytest.approx(EDGE_ANGLE)}


def test_stopping_switches_it_off(qt_app: QApplication) -> None:
    bar = PaintBar()
    bar.active.setChecked(True)

    bar.stop()

    assert not bar.painting


def test_two_painted_slots_do_not_look_the_same(profile: Profile) -> None:
    """Bemalen war im Bild folgenlos.

    Der Pinsel legt einen Slot ohne Farbe an (``colour=None``) — dieselbe Lücke
    hat die Schrift und „Slot zuweisen" mit leerem Feld. Die Ansicht nahm für
    einen Slot ohne Farbe die Körperfarbe, und damit standen in der Farbtabelle
    zwei gleiche Einträge: Wer zweifarbig bemalte, sah das Ergebnis zum ersten
    Mal im Slicer. Genau das, was der Docstring von ``_slot_colours`` als
    behoben beschreibt — behoben war es nur für Slots, die schon eine Farbe
    hatten.

    Geprüft wird die Tabelle und nicht das Bild: Offscreen gibt es keinen
    Plotter, und die Aussage steckt in den Farben, nicht im Rendern.
    """
    from app.ui.theme import SLOT_COLOURS, slot_colour

    entry = SceneObject(id="obj_1", name="Deckel", mesh=plate())
    first = run("paint_slot", entry, profile, slot=1, radius=1000.0, z=10.0).outputs[0]
    painted = run("paint_slot", first, profile, slot=2, radius=8.0, x=20.0, z=5.0).outputs[0]

    assert [slot.colour for slot in painted.material_slots] == [None, None], (
        "der Pinsel setzt keine Farbe — genau darum geht es hier"
    )
    colours = [slot_colour(slot.index) for slot in painted.material_slots]
    assert len(set(colours)) == len(colours), "zwei bemalte Slots bekommen dieselbe Farbe"
    assert all(colour in SLOT_COLOURS for colour in colours)
    assert slot_colour(0) is None, "Slot 0 ist das unbemalte Teil und behält seine Farbe"


def test_the_bar_shows_the_colour_and_the_name_not_just_a_number(qt_app: QApplication) -> None:
    """„Slot 1" sagt nicht, was auf dem Teil landet.

    Die Leiste hatte ein Zahlenfeld und sonst nichts: Welche Farbe dabei
    herauskommt, erfuhr man, indem man malte. Jetzt steht das Farbfeld daneben
    und der Name dahinter — Farbe **und** Wort, denn allein die Farbe wäre
    keine Auskunft (Regel 18).
    """
    from app.core.types import MaterialSlot

    bar = PaintBar()
    bar.slot.setValue(1)

    assert bar.swatch.pixmap().isNull() is False, "kein Farbfeld neben der Nummer"
    assert bar.slot_name.text() == "neu", "ein Slot, den es nicht gibt, sagt das"

    bar.set_slots([MaterialSlot(index=1, name="Rot")])
    assert bar.slot_name.text() == "Rot", "die Leiste nennt den Slot nicht, wie er heißt"

    bar.slot.setValue(0)
    assert bar.swatch.pixmap().isNull(), "Slot 0 behauptet eine Farbe, die er nicht hat"
    assert bar.slot_name.text(), "und sagt trotzdem, was er ist"
