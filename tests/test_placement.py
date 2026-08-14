"""Was ein angeklicktes Merkmal über eine Operation sagt (§18.5, §25, §40).

Merkmale zu erkennen war P3 und Bausteine zu setzen war P5; verbunden wurden
die zwei nie. Das Merkmal war im Baum und in der Ansicht wählbar, und der
Dialog, der sich als Nächstes öffnete, wusste nichts davon — wer eine Bohrung
in der eben angeklickten Fläche wollte, las die Koordinaten von der
Analysekarte ab und tippte sie ein.

Diese Tests halten die Verbindung: welche Parameter ein Merkmal einträgt, und
— genauso wichtig — welche es in Ruhe lässt.
"""

from __future__ import annotations

import pytest

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from app.core.scene.placement import (
    dominant_axis,
    faces_up,
    top_face,
    values_for,
    values_for_object,
)
from app.core.types import Feature

load_operations()


def face(
    centre: tuple[float, float, float] = (10.0, 20.0, 30.0),
    normal: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> Feature:
    return Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"area": 400.0, "centre": centre, "normal": normal},
    )


def hole(
    centre: tuple[float, float, float] = (5.0, -5.0, 4.0),
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0),
    diameter: float = 5.2,
) -> Feature:
    return Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"diameter": diameter, "centre": centre, "axis": axis, "through": True},
    )


# --- Lage und Richtung ----------------------------------------------------------


def test_a_face_says_where_a_bore_goes() -> None:
    """Der Fall, für den es das gibt: eine Fläche anklicken, dort bohren."""
    values = values_for(REGISTRY.get("drill_hole"), face(centre=(12.0, -3.0, 8.0)))

    assert values["x"] == pytest.approx(12.0)
    assert values["y"] == pytest.approx(-3.0)
    assert values["z"] == pytest.approx(8.0)


def test_the_normal_of_a_face_becomes_the_axis() -> None:
    sideways = values_for(REGISTRY.get("drill_hole"), face(normal=(1.0, 0.0, 0.0)))

    assert sideways["axis"] == "x"


def test_a_face_at_an_angle_names_no_axis() -> None:
    """Ein gerundeter Wert, von dem niemandem etwas gesagt wurde, ist
    schlechter als keiner.
    """
    slanted = values_for(REGISTRY.get("drill_hole"), face(normal=(0.7, 0.0, 0.71)))

    assert "axis" not in slanted
    assert "x" in slanted, "where it is, is still known"


def test_lettering_takes_the_full_direction() -> None:
    """§25: eine Beschriftung folgt der Normalen, nicht der nächsten Achse."""
    values = values_for(REGISTRY.get("label_text"), face(normal=(0.0, 1.0, 0.0)))

    assert (values["nx"], values["ny"], values["nz"]) == (0.0, 1.0, 0.0)


def test_the_axis_of_a_bore_is_used_where_there_is_no_normal() -> None:
    values = values_for(REGISTRY.get("countersink_hole"), hole(axis=(0.0, 1.0, 0.0)))

    assert values["axis"] == "y"


# --- Was mit Absicht nicht eingetragen wird --------------------------------------


def test_the_diameter_is_never_guessed() -> None:
    """Eine Senkung nimmt den Kopf der Schraube, nicht die Bohrung, auf der
    sie sitzt.

    Eine dort eingetragene 5,2 ist eine falsche Zahl, die wie eine gemessene
    aussieht.
    """
    values = values_for(REGISTRY.get("countersink_hole"), hole(diameter=5.2))

    assert "diameter" not in values


def test_an_operation_that_names_features_gets_the_name() -> None:
    """Die Bausteinbibliothek setzt sich selbst an ein Merkmal; die Position
    ist ein Versatz.
    """
    values = values_for(REGISTRY.get("insert_heatset_m4"), hole())

    assert values == {"at_feature": "hole_1"}, "the name is the whole answer"


def test_the_lid_is_placed_at_the_face_it_was_clicked_on() -> None:
    values = values_for(REGISTRY.get("create_lid"), face())

    assert values == {"at_feature": "face_1"}


def test_an_operation_without_a_place_takes_nothing() -> None:
    assert values_for(REGISTRY.get("repair"), face()) == {}


# --- die zwei Helfer ------------------------------------------------------------


def test_the_dominant_axis_needs_to_be_dominant() -> None:
    assert dominant_axis((0.0, 0.0, -1.0)) == "z"
    assert dominant_axis((0.95, 0.1, 0.0)) == "x"
    assert dominant_axis((0.6, 0.6, 0.5)) is None
    assert dominant_axis((0.0, 0.0, 0.0)) is None


def test_only_a_face_looking_up_counts_as_an_opening() -> None:
    """Flach ist nicht genug — die Decke eines Hohlraums ist flach und zeigt
    nach unten.

    Als Höhe einer Öffnung gewählt baute sie einen Deckel ins Innere der Box,
    auf 26,9 von 30 Millimetern, und weiter unten fiel es niemandem auf: ein
    Schnitt unter dieser Ebene trifft ja die Wand.
    """
    assert faces_up(face(normal=(0.0, 0.0, 1.0)))
    assert not faces_up(face(normal=(0.0, 0.0, -1.0))), "a ceiling is flat too"
    assert not faces_up(face(normal=(1.0, 0.0, 0.0)))
    assert not faces_up(hole())


# --- Was seit P15 dazukam --------------------------------------------------------


def test_a_clicked_face_becomes_the_target_of_an_extrusion() -> None:
    """„Bis zur Fläche" — der doc-Satz versprach es, niemand löste es ein.

    `up_to` nimmt eine Kennung und keine Zahl: den Rahmen rechnet die
    Auswertung bei jedem Lauf aus der Fläche. Damit hält die Höhe auch dann,
    wenn der Körper darunter morgen anders hoch ist.
    """
    values = values_for(REGISTRY.get("sketch_extrude"), face())

    assert values["up_to"] == "face_1"


def test_a_hole_is_no_target_for_an_extrusion() -> None:
    """Bis zu einer Bohrung zu extrudieren hat keine Bedeutung.

    Sie ist ein Zylinder, keine Ebene — es gäbe keine Höhe, bei der die
    Extrusion „dort ankommt"."""
    values = values_for(REGISTRY.get("sketch_extrude"), hole())

    assert "up_to" not in values


def test_a_cylinder_gives_the_texture_the_diameter_it_wraps_around() -> None:
    """Und der Durchmesser kommt aus dem Zylinder, um den gewickelt wird.

    Der Parameter heißt `wrap_diameter` und nicht `diameter` — sonst erbte
    eine Senkung den der Bohrung, auf der sie sitzt. Der Test dafür stand
    schon da und fing genau diesen Fehler.
    """
    values = values_for(REGISTRY.get("apply_texture"), hole(diameter=20.0))

    assert values["wrap_diameter"] == 20.0


# --- ohne angeklicktes Merkmal ---------------------------------------------------


def test_a_body_without_a_picked_feature_offers_its_top_face() -> None:
    """Die Vorgabe war der Ursprung, und ob der im Material liegt, ist Zufall.

    Bei einer Platte um den Nullpunkt ging es gut. Bei einem Körper, der auf
    dem Bett angeordnet ist — und das ist jede Druckvorbereitung — lag der
    Ursprung fünfundsechzig Millimeter daneben: gemessen am Beispielprojekt,
    dessen Dose von x −120 bis −40 reicht. Die Bohrung trug nichts ab, und
    die Operation sagte es hinterher.
    """
    features = {
        "face_top": face(centre=(-82.0, -93.0, 40.0)),
        "face_bottom": face(centre=(-82.0, -93.0, 0.0), normal=(0.0, 0.0, -1.0)),
    }

    values = values_for_object(REGISTRY.get("drill_hole"), features)

    assert values["x"] == pytest.approx(-82.0)
    assert values["y"] == pytest.approx(-93.0)
    assert values["z"] == pytest.approx(40.0), "die obere Fläche, nicht die untere"


def test_the_highest_upward_face_wins() -> None:
    """Eine Bohrung kommt von oben — also die höchste, nicht die größte.

    Bei einem Deckel mit Kragen wäre die größte der Boden.
    """
    features = {
        "face_wide": Feature(
            id="face_wide",
            kind="face",
            provenance="detected",
            params={"area": 4000.0, "centre": (0.0, 0.0, 2.0), "normal": (0.0, 0.0, 1.0)},
        ),
        "face_high": Feature(
            id="face_high",
            kind="face",
            provenance="detected",
            params={"area": 100.0, "centre": (0.0, 0.0, 30.0), "normal": (0.0, 0.0, 1.0)},
        ),
    }

    assert top_face(features) is features["face_high"]


def test_a_body_without_an_upward_face_suggests_nothing() -> None:
    """Lieber keine Zahl als eine geratene — der Dialog behält seine Vorgabe."""
    features = {"face_side": face(normal=(1.0, 0.0, 0.0))}

    assert values_for_object(REGISTRY.get("drill_hole"), features) == {}


def test_the_body_never_claims_a_feature_was_picked() -> None:
    """``at_feature`` ist eine Behauptung über eine Absicht.

    Eine Position ist ein Vorschlag, den man im Feld sieht und ändern kann;
    eine eingetragene Merkmalskennung ist eine Bindung, die niemand gewählt
    hat — und die spätere Läufe an einer Fläche festmacht, auf die nie
    jemand gezeigt hat.
    """
    features = {"face_top": face(centre=(1.0, 2.0, 3.0))}

    for spec in REGISTRY.all():
        values = values_for_object(spec, features)
        assert "at_feature" not in values, spec.name
        assert "up_to" not in values, spec.name
