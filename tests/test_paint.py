"""Flächen färben (Bauplan §20, Konzept Filamente).

Bis zum 26.08.2026 stand hier ein Pinsel mit Radius, und der schwere Teil war,
ihn an Kanten anzuhalten. Die Füllung braucht das nicht: Die Grenze der Fläche
kommt aus der Erkennung, und was sie färbt, sind genau deren Dreiecke. Der
größte Teil dieser Datei misst seitdem, dass sie **nur** die färbt — und dass
die Farbe, die ein Filament ohne eigene bekommt, nicht wie eine Auswahl
aussieht.
"""

from __future__ import annotations

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.attributes import counts, used_slots
from app.core.geom.mesh import MeshData
from app.core.geom.paint import fill_feature
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject


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


# --- Die Füllung: was sie färbt -------------------------------------------------


def test_filling_paints_the_face_and_nothing_else() -> None:
    """Der Punkt der ganzen Sache: Die Grenze kommt aus der Erkennung.

    Ein Pinsel mit Radius brauchte einen Kantenwinkel, damit die Farbe nicht um
    die Ecke lief; die Fläche weiß selbst, wo sie aufhört (``face_indices``).
    """
    filled = fill_feature(plate(), (0, 1), slot=1)

    assert counts(filled.mesh) == {0: 10, 1: 2}, "the top face, and nothing else"
    assert filled.painted == 2, "der Befund zählt den Strich, nicht den Bestand"


def test_filling_everything_is_a_matter_of_the_indices() -> None:
    """Kein Sonderfall, kein Winkel von 180 Grad: Wer alle Dreiecke nennt,
    färbt alle."""
    body = plate()

    filled = fill_feature(body, tuple(range(body.triangle_count)), slot=1)

    assert used_slots(filled.mesh) == (1,)


def test_filling_does_not_move_a_single_point() -> None:
    """§20: der Slot ist ein Attribut. Farbe ist keine Geometrie."""
    before = plate()

    filled = fill_feature(before, (0, 1), slot=2)

    assert filled.mesh.raw is before.raw
    assert filled.mesh.volume == before.volume


def test_a_second_fill_does_not_undo_the_first() -> None:
    once = fill_feature(plate(), (0, 1), slot=1)

    twice = fill_feature(once.mesh, (2, 3), slot=2)

    assert used_slots(twice.mesh) == (0, 1, 2), "zwei gefärbte Flächen und der Rest"


def test_indices_beyond_the_mesh_are_skipped_not_fatal() -> None:
    """Ein Merkmal einer früheren Auswertung kann mehr Dreiecke kennen, als das
    Netz nach einer Änderung noch hat — der Rest der Fläche ist trotzdem
    gemeint."""
    filled = fill_feature(plate(), (0, 1, 999), slot=1)

    assert filled.painted == 2


# --- Als Operation ---------------------------------------------------------------


def test_painting_runs_as_an_operation(profile: Profile) -> None:
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))

    result = run("paint_slot", entry, profile, slot=1, at_feature="face_1", name="Rot")

    output = result.outputs[0]
    assert used_slots(output.mesh) == (0, 1)
    assert [slot.name for slot in output.material_slots] == ["Rot"]
    assert [finding.code for finding in result.findings] == ["colour.painted"]


def test_painting_keeps_the_slicer_identity_with_the_colour(profile: Profile) -> None:
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))

    output = run(
        "paint_slot",
        entry,
        profile,
        slot=1,
        at_feature="face_1",
        name="Werkstattrolle",
        colour="#9AA0A6",
        material_type="PETG",
        slicer_profile="Elegoo PETG PRO @ECC2",
    ).outputs[0]

    slot = output.material_slots[0]
    assert slot.material_type == "PETG"
    assert slot.material == "Elegoo PETG PRO @ECC2"


def test_painting_rejects_a_slicer_profile_path(profile: Profile) -> None:
    """Auch die Flächenoperation speichert keinen rechnergebundenen Pfad."""
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))

    with pytest.raises(ValidationError) as raised:
        run(
            "paint_slot",
            entry,
            profile,
            slot=1,
            at_feature="face_1",
            slicer_profile="profiles/PETG.json",
        )

    assert raised.value.field == "slicer_profile"
    assert raised.value.suggestions


def test_painting_without_a_face_stops_with_advice(profile: Profile) -> None:
    """Der Punkt-Pinsel ist entfallen — ohne Fläche gibt es nichts zu färben,
    und das sagt die Operation, statt still nichts zu tun."""
    entry = SceneObject(id="obj_1", name="Deckel", mesh=plate())

    with pytest.raises(ValidationError) as raised:
        run("paint_slot", entry, profile, slot=1)

    assert raised.value.suggestions, "Regel 17: auch diese Ausnahme trägt Handlungen"


def test_the_slot_keeps_the_name_it_was_given(profile: Profile) -> None:
    """Eine zweite Füllung in denselben Slot darf ihn nicht umbenennen."""
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))
    first = run("paint_slot", entry, profile, slot=1, at_feature="face_1", name="Rot").outputs[0]

    second = run("paint_slot", first, profile, slot=1, at_feature="face_1").outputs[0]

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

    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))
    first = run("paint_slot", entry, profile, slot=1, at_feature="face_1").outputs[0]
    painted = run("paint_slot", first, profile, slot=2, at_feature="face_1").outputs[0]

    assert [slot.colour for slot in painted.material_slots] == [None, None], (
        "der Pinsel setzt keine Farbe — genau darum geht es hier"
    )
    colours = [slot_colour(slot.index) for slot in painted.material_slots]
    assert len(set(colours)) == len(colours), "zwei bemalte Slots bekommen dieselbe Farbe"
    assert all(colour in SLOT_COLOURS for colour in colours)
    assert slot_colour(0) is None, "Slot 0 ist das unbemalte Teil und behält seine Farbe"


def test_a_chosen_colour_wins_over_an_existing_slot() -> None:
    """Wer eine Fläche färbt, hat gerade ein Filament gewählt (§20).

    ``paint_slot`` legte den Slot mit ``setdefault`` an — damit gewann der
    **Bestand**: Färbte man eine zweite Fläche in denselben Slot, blieb dessen
    alter, oft leerer Eintrag stehen, und die eben gewählte Farbe verschwand.
    Am laufenden Fenster sah das so aus: Der Wähler zeigte Rot, und nach dem
    Abwählen war das Teil grau (Robert, 27.08.2026).

    ``assign_slot`` nebenan tat es die ganze Zeit richtig; seine Funktion wird
    jetzt geteilt statt verdoppelt.
    """
    from app.core.geom.colour_ops import merged_slots
    from app.core.types import MaterialSlot

    bestand = [MaterialSlot(index=1, name="", colour=None)]
    gewaehlt = [MaterialSlot(index=1, name="Rot", colour=(0.8, 0.13, 0.13))]

    ergebnis = merged_slots(bestand, gewaehlt)
    assert ergebnis[0].colour == (0.8, 0.13, 0.13), "die Wahl gewinnt, nicht der Bestand"
    assert ergebnis[0].name == "Rot"

    # Und ein Slot, den dieser Schritt nicht anfasst, bleibt unberührt.
    mit_zweitem = merged_slots(
        [MaterialSlot(index=2, name="Weiß", colour=(1.0, 1.0, 1.0)), *bestand], gewaehlt
    )
    weiss = next(s for s in mit_zweitem if s.index == 2)
    assert weiss.colour == (1.0, 1.0, 1.0), "fremde Filamente bleiben, wie sie waren"
