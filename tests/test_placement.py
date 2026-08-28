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

    Bis zum 25.08.2026 hieß die Zusage „gar kein Wert" — seither ist sie
    stärker: 5,2 mm ist das Durchgangsloch von M5, also kommt der Senkkopf
    von M5 ins Feld (10,0 mm, ISO-10642-Spalte der Normteiltabelle, hier
    abgeschrieben statt nachgeschlagen). Das gemessene Maß selbst wäre
    weiterhin eine falsche Zahl, die wie eine richtige aussieht.
    """
    values = values_for(REGISTRY.get("countersink_hole"), hole(diameter=5.2))

    assert values["diameter"] == pytest.approx(10.0)
    assert values["diameter"] != pytest.approx(5.2)


def test_resizing_a_bore_starts_with_its_measured_diameter() -> None:
    """Hier ist das gemessene Maß kein geratenes Kopfmaß, sondern genau der
    Wert, den die Operation ändert.

    Ohne ihn öffnete *Bohrung ändern* an einer erkannten Ø-5,19-Bohrung mit
    der Schemavorgabe 5,00. Ein unverändertes Bestätigen hätte das Teil also
    verändert — das Gegenteil eines einfachen, sicheren Kundenwegs.
    """
    values = values_for(REGISTRY.get("resize_hole"), hole(diameter=5.1901))

    assert values == {"at_feature": "hole_1", "diameter": pytest.approx(5.1901)}


def test_an_operation_that_names_features_gets_the_name() -> None:
    """Die Bausteinbibliothek setzt sich selbst an ein Merkmal; die Position
    ist ein Versatz.

    **Keine Koordinaten**, und das ist der Punkt dieses Tests: Wer sich an ein
    Merkmal hängt, bekommt dessen Kennung und rechnet den Rest selbst. Seit dem
    23.08.2026 kommt eine Größe dazu, wo der Baustein eine aus dem gemessenen
    Durchmesser herleiten kann — geprüft wird sie in
    ``test_a_bore_proposes_the_size_that_fits_it``.
    """
    values = values_for(REGISTRY.get("insert_heatset_m4"), hole())

    assert values["at_feature"] == "hole_1", "the name is the whole answer"
    assert not {"x", "y", "z", "axis"} & set(values), "keine Koordinaten neben der Kennung"


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


# --- Größe aus der Bohrung ------------------------------------------------------


def test_a_bore_proposes_the_size_that_fits_it() -> None:
    """Was in eine Bohrung gesetzt wird, richtet sich nach ihrem Durchmesser.

    **Gemeldet von 3d-druck-b8 am 23.08.2026, mit Zahlen:** An einer
    Ø 5,19-Bohrung schlug die Einpressbuchse **M3** vor. Deren Bohrung misst
    4,00 mm, liegt also vollständig innerhalb der vorhandenen — der Schnitt
    trug **nichts** ab. Gemessen: ±0 mm³. Der Kunde klickte, füllte den Dialog
    aus, bestätigte, bekam einen Schritt im Verlauf und eine unveränderte
    Geometrie. Ein Fehler, den niemand bei der Anwendung sucht.

    Die Regeln stehen bei den Bausteinen und nicht hier, weil sie **fachlich
    verschieden** sind: Eine Buchse braucht die kleinste Größe, die die Bohrung
    *aufweitet*; ein Gewinde die größte, die noch *hineinpasst*. Eine
    gemeinsame Formel wäre in einem der beiden Fälle falsch.
    """
    bore = hole(diameter=5.19)

    insert = values_for(REGISTRY.get("insert_heatset_m4"), bore)
    assert insert["size"] == "M4", (
        f"die Einpressbuchse schlägt {insert.get('size')} vor — deren Bohrung ist kleiner "
        "als die vorhandene und trägt nichts ab"
    )
    assert values_for(REGISTRY.get("insert_nut_trap"), bore)["size"] == "M5"

    thread = values_for(REGISTRY.get("insert_printed_thread"), bore)
    assert thread["size"] == "M6", "M6 hat das Kernloch, das zu 5,19 mm passt"
    assert thread["internal"] is True, (
        "wer eine Bohrung anklickt und Gewinde wählt, meint Gänge in der Wand — "
        "die Schemavorgabe steht auf Außengewinde und setzte einen Bolzen hinein"
    )


def test_a_bore_that_fits_no_thread_still_means_inside() -> None:
    """Kein Größenvorschlag ist kein Grund, die Richtung zu vergessen.

    **Gemeldet von Robert am 24.08.2026:** Bohrung gesetzt, „Gewinde" gewählt,
    und das Gewinde saß außen. Der Test darüber deckt den Fall ab, in dem eine
    Normgröße passt — dort kommt ``internal`` mit. Fehlt sie, gab
    ``size_for_thread`` ein leeres Wörterbuch zurück, und mit dem Vorschlag
    verschwand auch die Richtung: Die Schemavorgabe steht auf Außengewinde,
    also wuchs ein Bolzen aus dem Loch heraus.

    Die zwei Aussagen sind **verschieden sicher**, und genau das war der
    Fehler. Die Größe ist ein Vorschlag, der fehlschlagen darf — oberhalb von
    M8 gibt es keine Normgröße mehr, und eine geratene wäre schlechter als
    keine. Die Richtung ist keine Schätzung, sondern steht im angeklickten
    Merkmal: Es ist eine Bohrung. Sie mit dem Vorschlag zusammen wegzuwerfen
    hieß, das Sichere am Unsicheren scheitern zu lassen.

    Gemessen an M8, der größten Normgröße: Jede Bohrung darüber traf es, dazu
    Ø 6,5 zwischen M6 und M8 — zehn von 22 geprüften Durchmessern.
    """
    wide = values_for(REGISTRY.get("insert_printed_thread"), hole(diameter=10.0))

    assert wide.get("internal") is True, (
        "eine Ø 10-Bohrung bekommt keine Normgröße vorgeschlagen — die Richtung "
        "steht trotzdem fest, sonst setzt „Gewinde“ einen Bolzen in das Loch"
    )
    assert "size" not in wide, (
        "für Ø 10 gibt es keine passende Normgröße; eine geratene sähe aus wie eine gemessene"
    )


def test_a_bore_that_fits_nothing_keeps_the_default() -> None:
    """Wo keine Größe passt, wird nicht geraten (Regel 21).

    Beide Schranken sind fachlich und keine gegriffene Toleranz: Unter dem
    Kernlochdurchmesser greift ein Gewinde nicht ins Material, über dem Nennmaß
    liegt die Bohrungswand außerhalb. Eine Ø 6,5-Bohrung ist für M6 zu weit und
    für M8 zu eng — sie bekommt **keinen** Vorschlag statt eines falschen.

    Ein geratener Vorschlag sieht im Dialog genauso aus wie ein gemessener.
    """
    assert "size" not in values_for(REGISTRY.get("insert_printed_thread"), hole(diameter=6.5))

    huge = hole(diameter=40.0)
    for name in ("insert_heatset_m4", "insert_nut_trap", "insert_printed_thread"):
        values = values_for(REGISTRY.get(name), huge)
        assert "size" not in values, f"{name} rät an einer 40-mm-Bohrung eine Größe"
        assert values["at_feature"] == "hole_1", "die Zuordnung bleibt davon unberührt"


def test_a_part_that_brings_its_own_bore_takes_no_size_from_one() -> None:
    """Die Gegenprobe — sonst hätte der neue Weg den alten überschrieben.

    Der Docstring von ``values_for`` sagt seit je, dass die Größe eines
    Merkmals nicht in die Vorgaben gehört: „eine Senkung nimmt den Durchmesser
    des Schraubenkopfs, nicht den der Bohrung, auf der sie sitzt". Für alles,
    was **auf** einer Bohrung sitzt oder seine eigene mitbringt, gilt das
    unverändert.
    """
    bore = hole(diameter=5.19)
    for name in ("insert_screw_hole", "insert_dowel", "insert_cable_gland"):
        if not REGISTRY.has(name):
            continue
        assert "size" not in values_for(REGISTRY.get(name), bore), (
            f"{name} bringt seine Bohrung mit und darf keine Größe von einer erben"
        )

    countersink = values_for(REGISTRY.get("countersink_hole"), bore)
    assert countersink["diameter"] == pytest.approx(10.0), (
        "die Senkung nimmt den Kopf der passenden Schraube (M5), nicht das Loch"
    )
    assert countersink["diameter"] != pytest.approx(5.19)


def test_every_operation_with_a_feature_field_gets_it_filled_in() -> None:
    """Gefragt wird nach der **Art** des Feldes, nicht nach seinem Namen.

    Bis zum 23.08.2026 stand in :func:`values_for` ``if FEATURE_FIELD in
    names`` — also „heißt hier ein Feld *at_feature*?". *An Merkmal
    ausrichten* nennt ihres ``feature`` und fiel damit durch: Wer eine Fläche
    anklickte, bekam bei einundzwanzig Operationen eine Vorbelegung und bei
    dieser ein leeres Textfeld, in das er ``hole_1`` selbst tippen sollte
    (gefunden von 3d-druck-33).

    **Es war die zweite von zwei Stellen, die dieselbe Sache verschieden
    fragten.** ``scene/orphans.py`` geht nach ``kind == "feature"``; hier ging
    es nach dem Namen, und eine Operation fiel durch beide Raster. Der Test
    prüft deshalb nicht den einen Fall, sondern **jede** Operation mit einem
    Merkmalsfeld — ein Test auf ``align_to_feature`` allein hielte genau den
    Namen fest, der das Problem war.
    """
    load_operations()
    clicked = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"diameter": 5.2, "centre": (10.0, 5.0, 0.0), "axis": (0.0, 0.0, 1.0)},
        face_indices=(),
    )

    with_field = [
        spec
        for spec in REGISTRY.all()
        if any(entry.kind == "feature" for entry in spec.params.spec())
    ]
    assert with_field, "ohne Operationen mit Merkmalsfeld prüft dieser Test nichts"

    empty = []
    for spec in with_field:
        values = values_for(spec, clicked)
        fields = [entry.name for entry in spec.params.spec() if entry.kind == "feature"]
        if not any(values.get(name) == "hole_1" for name in fields):
            empty.append(f"{spec.name} ({', '.join(fields)})")

    assert not empty, "diese Operationen lassen den Nutzer die Kennung tippen:\n" + "\n".join(empty)
