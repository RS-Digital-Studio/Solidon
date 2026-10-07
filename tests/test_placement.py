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
from app.core.types import Feature, MeasureSource, MeasureStatus, Profile, measure_status
from app.i18n.catalog import available_languages

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
    values = values_for(REGISTRY.get("resize_hole"), hole(diameter=6.00004))

    assert values == {"at_feature": "hole_1", "diameter": pytest.approx(6.00004)}


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
    assert "face" not in values
    assert values["z"] == pytest.approx(4.0)


def test_texture_remembers_the_face_without_losing_rectangular_placement() -> None:
    values = values_for(REGISTRY.get("apply_texture"), face())
    assert values["face"] == "face_1"
    assert [values[name] for name in ("x", "y", "z")] == pytest.approx([10, 20, 30])
    assert [values[name] for name in ("nx", "ny", "nz")] == pytest.approx([0, 0, 1])
    assert "coverage" not in values
    inferred = values_for_object(REGISTRY.get("apply_texture"), {"face_1": face()})
    assert "face" not in inferred
    assert "coverage" not in inferred
    assert inferred["z"] == pytest.approx(30)


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
        for entry in spec.params.spec():
            if entry.kind in {"feature", "features"}:
                assert entry.name not in values, f"{spec.name}: {entry.name}"
        assert "up_to" not in values, spec.name


# --- Erzeuger: nur eine gezeigte Fläche trägt ihn (RM-390) ----------------------


def test_a_creator_takes_no_place_from_a_body_nobody_pointed_at() -> None:
    """Ein neuer Körper entstand auf dem zuletzt gewählten (RM-390).

    Zylinder Ø 40 × 20 anlegen, anklicken, *Quader anlegen* — Position Z stand
    auf 20, und der Quader saß auf dem Zylinder, ohne dass jemand eine Fläche
    gezeigt hatte. In fünf von zwölf Nachbauten entstand so ein Körper an einer
    Stelle, die der Kunde nicht gewählt hatte. Gefragt wird nach ``consumes``,
    also für jeden Erzeuger und nicht nur für den Quader.
    """
    features = {"face_top": face(centre=(0.0, 0.0, 20.0))}
    creators = [spec for spec in REGISTRY.all() if spec.consumes == 0]
    positioned = [
        spec.name
        for spec in creators
        if {"x", "y", "z"} <= {entry.name for entry in spec.params.spec()}
    ]
    assert "create_box" in positioned, "ohne einen Erzeuger mit Position prüft das nichts"

    placed = {
        spec.name: values for spec in creators if (values := values_for_object(spec, features))
    }

    assert placed == {}
    # Gegenprobe: Wer einen Körper bearbeitet, bekommt weiter dessen Oberseite.
    assert values_for_object(REGISTRY.get("drill_hole"), features)["z"] == pytest.approx(20.0)


def _lowest_and_base(
    mesh: object, centre: tuple[float, ...], normal: tuple[float, ...]
) -> tuple[float, float]:
    """Tiefster Punkt über dem Bett und Abstand der Grundfläche zur Flächenebene."""
    import numpy as np

    vertices = np.asarray(mesh.raw.vertices)  # type: ignore[attr-defined]
    along = (vertices - np.asarray(centre)) @ np.asarray(normal)
    return float(vertices[:, 2].min()), float(along.min())


@pytest.mark.parametrize(
    "normal",
    [(1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.6, 0.0, -0.8)],
    ids=["right", "front", "slanted_down"],
)
def test_a_creator_on_a_chosen_side_face_stands_on_it_above_the_bed(
    profile: Profile, normal: tuple[float, float, float]
) -> None:
    """Der Fehlerfall aus RM-390: Seitenfläche gewählt, Quader halb unter dem Bett.

    Der Quader übernahm die Richtung der Fläche und ihre Mitte — gedreht auf
    die Seite, mit z = −4,5. Er gehört **auf** die Fläche: Grundfläche in ihrer
    Ebene, und so weit in ihr nach oben gerückt, dass nichts unter dem Bett
    liegt. Für jeden Grundkörper in beiden Kernen, gemessen am Körper, den die
    Operation tatsächlich baut.
    """
    from app.core.registry import PRIMITIVE_TWINS
    from app.core.scene.placement import seat_on_face
    from app.core.units import EPS_DISPLAY
    from tests.helpers import primitive_operation

    centre = (20.0, 0.0, 5.0)
    side = face(centre=centre, normal=normal)
    for mesh_name, brep_name in PRIMITIVE_TWINS:
        seated = seat_on_face(REGISTRY.get(brep_name), side, {}, profile)
        assert seated is not None, brep_name
        assert seat_on_face(REGISTRY.get(mesh_name), side, {}, profile) == seated, (
            "beide Kerne stehen gleich"
        )
        assert (seated["nx"], seated["ny"], seated["nz"]) == pytest.approx(normal)
        body = primitive_operation(mesh_name, dict(seated), profile).outputs[0].mesh
        lowest, base = _lowest_and_base(body, centre, normal)
        assert lowest == pytest.approx(0.0, abs=EPS_DISPLAY), f"{mesh_name}: auf dem Bett"
        assert base == pytest.approx(0.0, abs=EPS_DISPLAY), f"{mesh_name}: auf der Fläche"


def test_lettering_on_a_side_face_rises_like_a_primitive(profile: Profile) -> None:
    """Die freistehende Beschriftung ist auch ein Erzeuger mit Position und Richtung."""
    from app.core.scene.placement import seat_on_face
    from app.core.units import EPS_DISPLAY
    from tests.helpers import primitive_operation

    centre, normal = (20.0, 0.0, 2.0), (1.0, 0.0, 0.0)
    entered = {"text": "SOLIDON", "size": 20.0}
    seated = seat_on_face(REGISTRY.get("create_label"), face(centre, normal), entered, profile)

    assert seated is not None
    body = primitive_operation("create_label", {**entered, **seated}, profile).outputs[0].mesh
    lowest, base = _lowest_and_base(body, centre, normal)
    assert lowest == pytest.approx(0.0, abs=EPS_DISPLAY)
    assert base == pytest.approx(0.0, abs=EPS_DISPLAY)


def test_a_creator_on_a_top_face_sits_at_its_centre(profile: Profile) -> None:
    """Gegenprobe: Auf einer Oberseite gibt es nichts zu heben."""
    from app.core.scene.placement import seat_on_face

    seated = seat_on_face(REGISTRY.get("create_box"), face(centre=(1.0, 2.0, 20.0)), {}, profile)

    assert seated == pytest.approx({"x": 1.0, "y": 2.0, "z": 20.0, "nx": 0.0, "ny": 0.0, "nz": 1.0})


def test_a_creator_that_would_reach_under_the_bed_takes_no_seat(profile: Profile) -> None:
    """Unter einer Unterseite auf dem Bett ist kein Platz, und in ihrer Ebene steigt nichts.

    Dann sitzt er nicht dort — :func:`seat_on_face` sagt es mit ``None``, und
    der Dialog sagt es dem Kunden. Gegenprobe: Unter einer Decke in 50 mm Höhe
    hängt ein 10 mm hoher Quader frei.
    """
    from app.core.scene.placement import seat_on_face

    spec = REGISTRY.get("create_box")
    down = (0.0, 0.0, -1.0)

    assert seat_on_face(spec, face(centre=(0.0, 0.0, 0.0), normal=down), {}, profile) is None
    hanging = seat_on_face(spec, face(centre=(0.0, 0.0, 50.0), normal=down), {}, profile)
    assert hanging is not None
    assert hanging["z"] == pytest.approx(50.0)


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

    Seit dem 06.10.2026 bekommt eine solche Bohrung ein **eigenes Maß**, und
    das ist nicht geraten: Die Bohrung ist sein Kernloch, das Nennmaß liegt
    zwei Gangtiefen der Regelsteigung darüber. Bleibt nur die Bohrung unter
    dem kleinsten Gewinde ohne Größe — die Richtung steht auch dort fest.
    """
    from app.core.knowledge.parts.fasteners import CUSTOM_SIZE

    wide = values_for(REGISTRY.get("insert_printed_thread"), hole(diameter=70.0))
    assert wide.get("internal") is True, (
        "eine Ø 70-Bohrung bekommt ein Innengewinde — die Schemavorgabe steht auf "
        "Außengewinde und setzte einen Bolzen in das Loch"
    )
    # Über M64 (Nennmaß 64) passt keine Tabellengröße mehr; Ø 70 nimmt die 6 der M64.
    assert wide["size"] == CUSTOM_SIZE
    assert wide["diameter"] == pytest.approx(70.0 + 2.0 * 0.55 * 6.0)
    assert wide["pitch"] == 0.0, "die Steigung bleibt automatisch und trifft die Regelsteigung"

    narrow = values_for(REGISTRY.get("insert_printed_thread"), hole(diameter=1.0))
    assert narrow.get("internal") is True and "size" not in narrow, (
        "unter dem kleinsten Gewinde gibt es keine Größe, aber die Richtung"
    )


def test_a_bore_that_fits_nothing_keeps_the_default() -> None:
    """Wo keine Größe passt, wird nicht geraten (Regel 21).

    Beide Schranken sind fachlich und keine gegriffene Toleranz: Unter dem
    Kernlochdurchmesser greift ein Gewinde nicht ins Material, über dem Nennmaß
    liegt die Bohrungswand außerhalb. Eine Einpressbuchse oder Mutter, deren
    Tabelle an der Bohrung endet, bekommt **keinen** Vorschlag statt eines
    falschen; ein geratener sieht im Dialog genauso aus wie ein gemessener.

    Das Gewinde hat seit dem 06.10.2026 ein eigenes Maß und damit für jede
    Bohrung eines, die zwischen zwei Größen (Ø 6,5) wie die weite (Ø 40) —
    gerechnet aus der Bohrung, nicht geraten.
    """
    from app.core.knowledge.parts.fasteners import CUSTOM_SIZE

    between = values_for(REGISTRY.get("insert_printed_thread"), hole(diameter=6.5))
    assert between["size"] == CUSTOM_SIZE
    assert between["diameter"] == pytest.approx(6.5 + 2.0 * 0.55 * 1.0)

    # Die Buchse endet an der Tabelle (CNC Kitchen M10, Loch 12,0) — welches Loch eine
    # andere braucht, sagt ihr Datenblatt. Die Mutternfalle hat bei 40 mm die M39
    # (40 ist ihr feines Durchgangsloch nach ISO 273) und über dem größten Gewinde
    # (Durchgangsloch über 1093,75) keine Größe.
    for name, diameter in (("insert_heatset_m4", 40.0), ("insert_nut_trap", 1200.0)):
        values = values_for(REGISTRY.get(name), hole(diameter=diameter))
        assert "size" not in values, f"{name} rät an einer {diameter}-mm-Bohrung eine Größe"
        assert values["at_feature"] == "hole_1", "die Zuordnung bleibt davon unberührt"
    assert values_for(REGISTRY.get("insert_nut_trap"), hole(diameter=40.0))["size"] == "M39"
    # 38 mm liegt zwischen Kernloch (37,5) und Nennmaß der M42 und lässt dem Gang
    # mehr als die halbe Tiefe; über M64 ein eigenes Maß.
    thread = values_for(REGISTRY.get("insert_printed_thread"), hole(diameter=38.0))
    assert thread["size"] == "M42" and thread["at_feature"] == "hole_1"
    thread = values_for(REGISTRY.get("insert_printed_thread"), hole(diameter=80.0))
    assert thread["size"] == CUSTOM_SIZE and thread["at_feature"] == "hole_1"


def test_the_sentence_over_a_bore_names_the_size_the_dialog_chose() -> None:
    """Satz und Vorauswahl sprechen von derselben Größe.

    Über *Druckbares Gewinde* stand an einer 5,20-mm-Bohrung „Passt vermutlich
    zu M5 (Durchgangsloch fein).“, gewählt war M6 (Handbuchbild *Ein Gewinde in
    eine Bohrung*, 4): Der allgemeine Satz sprach von einem Durchgangsloch. Die
    Einpressbuchse zeigte denselben Satz über der Vorauswahl M4. Geprüft über
    jeden Baustein mit eigenem Satz und eine Reihe von Durchmessern: Nennt der
    Satz eine Normgröße, ist es die vorgewählte.
    """
    import re

    from app.core.knowledge import standards
    from app.core.knowledge.parts.fasteners import CUSTOM_SIZE
    from app.core.knowledge.parts.ops import part_of
    from app.core.scene.placement import advises_on_bores, bore_advice
    from app.core.units import format_length

    sizes = set(standards.screw_sizes()) | set(standards.insert_sizes())
    specs = [
        spec
        for spec in REGISTRY.all()
        if advises_on_bores(spec)
        and (part := part_of(spec.name)) is not None
        and part.at_hole_advice is not None
    ]
    names = {spec.name for spec in specs}
    assert {"insert_printed_thread", "insert_heatset_m4", "insert_nut_trap"} <= names, names
    for diameter in (2.6, 3.4, 4.3, 5.19, 5.5, 6.5, 8.4, 10.0):
        bore = hole(diameter=diameter)
        for spec in specs:
            chosen = values_for(spec, bore).get("size")
            said, choices = bore_advice(diameter, ask=False, feature=bore, spec=spec)
            assert said.startswith("Bohrungsmaß: "), said
            assert not choices, "ein Satz über dem Dialog fragt nicht"
            named = [
                word
                for word in re.findall(r"M\d+(?:[.,]\d+)?(?:S|x\d+x\d+)?", said)
                if word in sizes
            ]
            if chosen == CUSTOM_SIZE:
                # Das eigene Maß nennt der Satz mit dem vorgewählten Durchmesser.
                built = format_length(values_for(spec, bore)["diameter"])
                assert "eigenem Maß" in said and str(built).replace(".", ",") in said, (
                    spec.name,
                    diameter,
                    said,
                )
            elif chosen is not None:
                assert named and named[0] == chosen, (spec.name, diameter, chosen, said)

    gewinde = REGISTRY.get("insert_printed_thread")
    said, _choices = bore_advice(5.19, ask=False, feature=hole(diameter=5.19), spec=gewinde)
    assert "Innengewinde M6" in said and "Durchgangsloch" not in said, said
    said, _choices = bore_advice(6.5, ask=False, feature=hole(diameter=6.5), spec=gewinde)
    assert "Innengewinde mit eigenem Maß Ø 7,60 mm, Steigung 1,00 mm" in said, said
    said, _choices = bore_advice(1.0, ask=False, feature=hole(diameter=1.0), spec=gewinde)
    assert "Kernloch des kleinsten mit Ø 1,60 mm" in said, said

    # Gegenprobe: Die Senkung behält den Satz über die Schraube, die hindurchgeht.
    said, _choices = bore_advice(
        5.19, ask=False, feature=hole(diameter=5.19), spec=REGISTRY.get("countersink_hole")
    )
    assert "Durchgangsloch" in said and "M5" in said, said


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
        if any(entry.kind in {"feature", "features"} for entry in spec.params.spec())
    ]
    assert with_field, "ohne Operationen mit Merkmalsfeld prüft dieser Test nichts"

    empty = []
    for spec in with_field:
        # Ein Feld, das nur Flächen annimmt (``feature_kinds``, die Öffnungen
        # des Aushöhlens, P6.3), bekommt eine Fläche angeklickt — eine Bohrung
        # trägt sich dort mit Absicht nicht ein.
        faces_only = any(
            entry.feature_kinds and clicked.kind not in entry.feature_kinds
            for entry in spec.params.spec()
            if entry.kind in {"feature", "features"}
        )
        selected = face() if spec.applies_to == ("face",) or faces_only else clicked
        values = values_for(spec, selected)
        fields = [entry for entry in spec.params.spec() if entry.kind in {"feature", "features"}]
        if not any(
            values.get(entry.name) == ((selected.id,) if entry.kind == "features" else selected.id)
            for entry in fields
        ):
            empty.append(f"{spec.name} ({', '.join(entry.name for entry in fields)})")

    assert not empty, "diese Operationen lassen den Nutzer die Kennung tippen:\n" + "\n".join(empty)


@pytest.mark.parametrize(
    "name",
    ("heatset_m4", "nut_trap", "printed_thread", "printed_screw", "fit_ladder"),
)
@pytest.mark.parametrize("source", ("native", "facets", "fit", "parameter", None))
def test_part_bore_advice_qualifies_every_non_native_measure(
    name: str, source: MeasureSource | None
) -> None:
    """Alle fünf Bausteinsätze unterscheiden Herkunft und Einschätzung."""
    from dataclasses import replace

    from app.core.knowledge.parts.ops import part_of
    from app.core.scene.placement import bore_advice
    from app.i18n import get_language, set_language

    previous = get_language()
    set_language("de")
    try:
        spec = REGISTRY.get(f"insert_{name}")
        part = part_of(spec.name)
        assert part is not None and part.at_hole_advice is not None
        bore = replace(
            hole(diameter=5.19), measure_sources={} if source is None else {"diameter": source}
        )
        before = values_for(spec, bore)
        body = part.at_hole_advice(5.19)
        assert body is not None
        status = measure_status(bore, "diameter")
        assert status.source == source and status.available
        assert status.state == (
            "unknown" if source is None else "estimated" if source == "fit" else "exact"
        )
        said, choices = bore_advice(5.19, ask=False, feature=bore, status=status, spec=spec)
        expected = str(body)
        if source != "native":
            expected = f"Einschätzung anhand dieses Maßes: {expected}"
        assert said.endswith(expected), said
        assert ("Einschätzung anhand dieses Maßes:" in said) is (source != "native")
        assert not choices
        assert values_for(spec, bore) == before, "Der Hinweis ändert keine Vorauswahl."
    finally:
        set_language(previous)


@pytest.mark.parametrize(
    ("name", "diameter"),
    # Ein Gewinde sagt nur noch unter dem kleinsten Kernloch ab; Ø 6,5 bekommt ein eigenes Maß.
    (("printed_thread", 1.0), ("heatset_m4", 40.0), ("nut_trap", 1200.0)),
)
def test_part_bore_advice_qualifies_negative_measurement_answers(
    name: str, diameter: float
) -> None:
    """Auch eine abgelehnte Normgröße ist bei einem Netzmaß eine Einschätzung."""
    from app.core.knowledge.parts.ops import part_of
    from app.core.scene.placement import bore_advice
    from app.i18n import get_language, set_language

    previous = get_language()
    set_language("de")
    try:
        spec = REGISTRY.get(f"insert_{name}")
        part = part_of(spec.name)
        assert part is not None and part.at_hole_advice is not None
        body = part.at_hole_advice(diameter)
        assert body is not None and str(body).startswith("Kein")
        said, choices = bore_advice(
            diameter,
            ask=False,
            feature=hole(diameter=diameter),
            status=MeasureStatus("estimated", source="fit", available=True),
            spec=spec,
        )
        assert said.endswith(f"Einschätzung anhand dieses Maßes: {body}"), said
        assert not choices
    finally:
        set_language(previous)


def test_part_bore_advice_keeps_the_single_argument_user_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein eigener Baustein bekommt weiter nur den ungerundeten Durchmesser."""
    from dataclasses import replace

    from app.core.knowledge.parts import ops as part_ops
    from app.core.scene.placement import bore_advice
    from app.i18n import get_language, set_language

    calls: list[float] = []

    def own_advice(diameter: float) -> str:
        calls.append(diameter)
        return f"Eigener Hinweis für {diameter} mm."

    spec = REGISTRY.get("insert_printed_thread")
    part = part_ops.part_of(spec.name)
    assert part is not None
    monkeypatch.setattr(part_ops, "part_of", lambda _name: replace(part, at_hole_advice=own_advice))
    previous = get_language()
    set_language("de")
    try:
        said, choices = bore_advice(
            5.1873,
            ask=False,
            status=MeasureStatus("estimated", source="fit", available=True),
            spec=spec,
        )
        assert calls == [5.1873]
        assert said.endswith("Einschätzung anhand dieses Maßes: Eigener Hinweis für 5.1873 mm.")
        assert not choices
    finally:
        set_language(previous)


def test_part_bore_advice_skips_an_unavailable_measure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne verfügbares Maß wird kein Baustein nach einer passenden Größe gefragt."""
    from app.core.knowledge.parts import ops as part_ops
    from app.core.scene.placement import bore_advice

    def unexpected(_name: str) -> None:
        pytest.fail("Ein nicht verfügbares Maß erreicht keinen Bausteinrückruf.")

    monkeypatch.setattr(part_ops, "part_of", unexpected)
    said, choices = bore_advice(
        5.19,
        ask=False,
        status=MeasureStatus("unknown", available=False),
        spec=REGISTRY.get("insert_printed_thread"),
    )
    assert said and not choices
    assert "Einschätzung anhand dieses Maßes:" not in said


def test_part_bore_advice_none_keeps_the_general_size_answer() -> None:
    """Ohne eigenen Bausteinsatz gilt weiter der allgemeine Hinweis zur Bohrung."""
    from app.core.knowledge.parts.ops import part_of
    from app.core.scene.placement import bore_advice

    spec = REGISTRY.get("insert_printed_screw")
    part = part_of(spec.name)
    assert part is not None and part.at_hole_advice is not None
    # 7,5 mm ist kein Durchgangsloch der Tabelle: Zwischen dem groben der M6 (7,0)
    # und dem feinen der M8 (8,4) gibt es keine Schraube, die gedruckte schweigt.
    # 40 mm taugt dafür nicht mehr: Seit der zweiten Wahl ist es das feine Loch der M39.
    assert part.at_hole_advice(7.5) is None
    status = MeasureStatus("estimated", source="fit", available=True)
    plain = bore_advice(7.5, ask=False, status=status)
    assert bore_advice(7.5, ask=False, status=status, spec=spec) == plain


@pytest.mark.parametrize("language", available_languages())
def test_part_bore_advice_translates_the_complete_assessment_frame(language: str) -> None:
    """Maßherkunft und Bausteinsatz werden zusammen in der gewählten Sprache gezeigt."""
    from app.core.knowledge.parts.ops import part_of
    from app.core.scene.placement import bore_advice
    from app.i18n import get_language, set_language, tr
    from app.i18n.catalog import install_language

    previous = get_language()
    install_language(language)
    set_language(language)
    try:
        spec = REGISTRY.get("insert_printed_thread")
        part = part_of(spec.name)
        assert part is not None and part.at_hole_advice is not None
        body = part.at_hole_advice(5.19)
        assert body is not None
        said, choices = bore_advice(
            5.19,
            ask=False,
            status=MeasureStatus("estimated", source="fit", available=True),
            spec=spec,
        )
        expected = tr("Einschätzung anhand dieses Maßes: {advice}", advice=body)
        assert said.endswith(expected), said
        assert not choices
        if language == "fr":
            assert expected.startswith("Estimation à partir de cette cote : ")
        elif language != "de":
            assert not expected.startswith("Einschätzung anhand dieses Maßes:")
    finally:
        set_language(previous)


@pytest.mark.parametrize("unit", ["mm", "in"])
def test_the_bore_sentence_names_its_diameter_in_the_display_unit(unit: str) -> None:
    """In Zoll steht kein „mm“ im Satz über der Bohrung (RM-516).

    Das „mm“ stand fest in den Sätzen, und das Merkmalfenster schrieb in Zoll
    „Bohrungsmaß: 5,20 mm“ neben lauter Zollmaßen. Die Zahl trägt jetzt ihre
    Einheit selbst — gemessen wie vorgegeben.
    """
    from app.core.scene.placement import bore_advice
    from app.i18n import display_unit, set_display_unit

    previous = display_unit()
    set_display_unit(unit)
    try:
        measured, _choices = bore_advice(5.2, ask=False, feature=hole(diameter=5.2))
        native, _choices = bore_advice(5.5, ask=False)
        blind, _choices = bore_advice(7.5, ask=True)
    finally:
        set_display_unit(previous)
    for said in (measured, native, blind):
        assert ("mm" in said.split()) is (unit == "mm"), said
        assert (" in" in said) is (unit == "in"), said


@pytest.mark.parametrize(
    ("diameter", "expected"),
    [(22.0, "M24"), (22.3, "M24"), (22.4, "custom_size"), (23.9, "M27")],
)
def test_a_bore_just_under_the_nominal_size_takes_a_thread_that_grips(
    diameter: float, expected: str
) -> None:
    """Eine Bohrung knapp unter dem Nennmaß ist kein Kernloch dieser Größe (Review RM-532, K-N6).

    Ø 23,9 bekam die M24: Ihr gedruckter Bolzen reicht mit dem Spiel bis r 11,9 und
    griff in die Bohrung mit r 11,95 gar nicht. Eine Tabellengröße muss dem Gang
    die halbe Tiefe lassen (``units.THREAD_MIN_GRIP_SHARE``, M24: bis
    24 − 0,55 · 3 = Ø 22,35); darüber nimmt die Bohrung das eigene Maß mit voller
    Gangtiefe, Ø 22,4 → 22,4 + 1,1 · 3 = Ø 25,7. Ø 23,9 liegt über dem Gangfuß der
    M27 (27 − 1,1 · 3 = 23,7) und ist ihre Bohrung (Review P2, M1).
    """
    from app.core.knowledge.parts.fasteners import size_for_thread

    chosen = size_for_thread(diameter)
    assert chosen["size"] == expected, chosen
    if expected == "custom_size":
        assert chosen["diameter"] > diameter + 0.5 * 2.0 * 0.55 * 1.0, chosen
    if diameter == 22.4:
        assert chosen["diameter"] == pytest.approx(25.7)
