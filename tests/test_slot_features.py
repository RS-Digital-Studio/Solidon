"""Langlöcher als Merkmal (§21.1).

Ein Langloch ist keine Grundform: Die Einpassung findet darin zwei
Zylinderausschnitte und nennt sie Verrundungen. Was sie zu einem Loch macht,
ist die Nachbarschaft — und genau die wird hier gemessen, an beiden Enden:
dass ein Langloch eines wird, und dass etwas, das nur so aussieht, keines
wird.

**Nicht ``test_slots.py``**, und der Name ist eine Warnung: Dort geht es um
**Material**slots (§20), und im Deutschen heißt beides „Slot". Das
Filament-Konzept führt den Fall ausdrücklich als Falschtreffer; am 10.09.2026
ist er trotzdem einmal zugeschnappt.
"""

from __future__ import annotations

import dataclasses
import math

import pytest
import trimesh
from shapely.geometry import Polygon

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.prepare import drill, shortest_slot
from app.core.perceive.digest import _feature_line
from app.core.perceive.features import _fitted, _one_body, detect
from app.core.perceive.slots import find_slots
from app.core.registry import REGISTRY
from app.core.types import Feature, OpContext, Profile, Scene, SceneObject


def plate() -> MeshData:
    """60 x 40 x 10 mm, wasserdicht."""
    return MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))


def slotted(profile: Profile, **values: float | str) -> MeshData:
    """Eine Platte mit einem gebohrten Langloch."""
    settings: dict[str, object] = {
        "position": (0.0, 0.0, 5.0),
        "axis": "z",
        "diameter": 5.0,
        "compensate": False,
        "slot_length": 20.0,
    }
    settings.update(values)
    return drill(plate(), profile=profile, **settings).mesh  # type: ignore[arg-type]


def only_slot(mesh: MeshData) -> Feature:
    """Das eine erkannte Langloch — und die Zusicherung, dass es eines ist."""
    found = [entry for entry in detect(mesh).values() if entry.kind == "slot"]
    assert len(found) == 1, f"genau ein Langloch erwartet, gefunden: {len(found)}"
    return found[0]


# --- Was ein Langloch ist ---------------------------------------------------------


def test_a_slot_is_one_feature_and_not_two_fillets(profile: Profile) -> None:
    """Der Anlass: Im Objektbaum standen zwei Hohlkehlen, wo eine Öffnung ist.

    Gemessen an einer Platte mit einem Langloch Ø 5 auf 20 mm — vor dieser
    Erkennung ``fillet_1`` und ``fillet_2``, sonst nichts. Wer darauf klickte,
    fand die Handlungen einer Verrundung: keine.
    """
    mesh = slotted(profile)
    found = detect(mesh)

    assert [entry.kind for entry in found.values()].count("slot") == 1
    assert not [entry for entry in found.values() if entry.kind == "fillet"], (
        "die zwei Bögen sind im Langloch aufgegangen"
    )
    assert not [entry for entry in found.values() if entry.kind == "hole"]


def test_a_slot_carries_the_measures_it_was_cut_with(profile: Profile) -> None:
    slot = only_slot(slotted(profile, diameter=5.0, slot_length=20.0))

    assert float(slot.params["diameter"]) == pytest.approx(5.0, abs=0.01)
    assert float(slot.params["length"]) == pytest.approx(20.0, abs=0.01)
    assert float(slot.params["travel"]) == pytest.approx(15.0, abs=0.01)
    assert float(slot.params["depth"]) == pytest.approx(10.0, abs=0.01)
    assert slot.params["through"]
    assert slot.params["axis"] == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)
    assert slot.params["centre"] == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)


def test_a_blind_slot_says_it_does_not_go_through(profile: Profile) -> None:
    slot = only_slot(slotted(profile, depth=4.0))

    assert not slot.params["through"]
    assert float(slot.params["depth"]) == pytest.approx(4.0, abs=0.01)
    # Die Mitte liegt auf halber Tiefe unter der Oberseite, nicht in der Mitte
    # der Platte — sonst zeigte ein Klick darauf ins Material daneben.
    assert float(slot.params["centre"][2]) == pytest.approx(3.0, abs=0.01)


@pytest.mark.parametrize("angle", [0.0, 30.0, 90.0, -45.0])
def test_a_slot_knows_which_way_it_lies(angle: float, profile: Profile) -> None:
    """Die Richtung ist der Grund, aus dem es Langlöcher gibt.

    Ohne sie wüsste weder der Kunde noch der Agent, wohin sich das Teil
    verschieben lässt. Gemessen gegen den Winkel, mit dem gebohrt wurde —
    und ohne Vorzeichen: Ein Langloch hat keine Vorder- und keine Rückseite.
    """
    slot = only_slot(slotted(profile, slot_angle=angle))

    along = slot.params["direction"]
    wanted = (math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0.0)
    parallel = abs(sum(a * b for a, b in zip(along, wanted, strict=True)))
    assert parallel == pytest.approx(1.0, abs=1e-6)


def test_a_slot_cut_by_two_booleans_is_found_as_well(profile: Profile) -> None:
    """Der eigentliche Kundenfall: ein **eingelesenes** Modell.

    Wer eine Datei aus dem Netz öffnet, hat kein Solidon-Langloch, sondern ein
    Netz, in das jemand anders eine Nut geschnitten hat. Diese hier entsteht
    aus einem Quader und zwei Zylindern und nie aus ``drill`` — sonst prüfte
    der Test seinen eigenen Erzeuger.
    """
    del profile
    body = MeshData.of(trimesh.creation.box(extents=(80.0, 40.0, 20.0)))
    middle = trimesh.creation.box(extents=(22.0, 8.0, 8.0))
    middle.apply_translation((0.0, 0.0, 8.0))
    tool = MeshData.of(middle)
    for x in (-11.0, 11.0):
        cap = trimesh.creation.cylinder(radius=4.0, height=8.0, sections=64)
        cap.apply_translation((x, 0.0, 8.0))
        tool = boolean("union", [tool, MeshData.of(cap)]).mesh
    cut = boolean("difference", [body, tool]).mesh

    slot = only_slot(cut)

    assert float(slot.params["diameter"]) == pytest.approx(8.0, abs=0.05)
    assert float(slot.params["length"]) == pytest.approx(30.0, abs=0.05)
    assert not slot.params["through"], "die Nut ist 5 mm tief, die Platte 20 mm dick"


# --- Und was keines ist -----------------------------------------------------------


def pocket_with_rounded_corners(length: float, width: float, radius: float) -> MeshData:
    """Eine rechteckige Tasche mit vier verrundeten Ecken.

    Die härteste Gegenprobe, die es gibt: vier Innenverrundungen mit gleichem
    Radius und paralleler Achse, über die geraden Wände verbunden. Zwei
    benachbarte davon plus die Wand dazwischen sehen einem Langloch zum
    Verwechseln ähnlich — und sind keines, weil der Mantel weiterläuft.
    """
    block = trimesh.creation.box(extents=(length + 30.0, width + 30.0, 20.0))
    outline = (
        Polygon(
            [
                (-length / 2, -width / 2),
                (length / 2, -width / 2),
                (length / 2, width / 2),
                (-length / 2, width / 2),
            ]
        )
        .buffer(-radius)
        .buffer(radius, quad_segs=16)
    )
    tool = trimesh.creation.extrude_polygon(outline, height=8.0)
    tool.apply_translation((0.0, 0.0, 4.0))
    return boolean("difference", [MeshData.of(block), MeshData.of(tool)]).mesh


@pytest.mark.parametrize(("length", "width"), [(40.0, 24.0), (30.0, 30.0)])
def test_a_pocket_with_rounded_corners_is_not_a_slot(length: float, width: float) -> None:
    mesh = pocket_with_rounded_corners(length, width, 6.0)
    body = _one_body(mesh)
    rounded = [entry for entry in _fitted(body).fillets if entry[0].inward]

    assert len(rounded) == 4, (
        "die Vorbedingung: vier Innenverrundungen, sonst prüft die Gegenprobe nichts"
    )
    assert find_slots(body, _fitted(body).fillets) == []
    assert not [entry for entry in detect(mesh).values() if entry.kind == "slot"]


def test_two_separate_bores_are_not_a_slot(profile: Profile) -> None:
    """Zwei Löcher nebeneinander bleiben zwei Löcher."""
    first = drill(
        plate(),
        position=(-6.0, 0.0, 5.0),
        axis="z",
        diameter=5.0,
        profile=profile,
        compensate=False,
    )
    both = drill(
        first.mesh,
        position=(6.0, 0.0, 5.0),
        axis="z",
        diameter=5.0,
        profile=profile,
        compensate=False,
    )
    found = detect(both.mesh)

    assert [entry.kind for entry in found.values()].count("hole") == 2
    assert not [entry for entry in found.values() if entry.kind == "slot"]


# --- Wie der Kunde es sieht -------------------------------------------------------


def test_the_object_tree_names_a_slot_and_shows_both_measures(profile: Profile) -> None:
    """Ein Merkmal ohne Namen steht als englische Kennung im Baum (Regel 20)."""
    from app.i18n import set_language
    from app.ui import labels

    set_language("de")
    slot = only_slot(slotted(profile))

    assert "Langloch" in labels.feature_name(slot.id, slot)
    measure = labels.feature_measure(slot)
    assert "5,0" in measure and "20,0" in measure, (
        f"Breite und Länge stehen beide da, gelesen wurde {measure!r}"
    )


def test_the_digest_tells_the_agent_where_a_slot_points(profile: Profile) -> None:
    """Der Agent sieht nur diesen Text (§26.1)."""
    from app.i18n import set_language

    set_language("de")
    slot = only_slot(slotted(profile, slot_angle=90.0))

    line = _feature_line(slot.id, slot)
    assert "Langloch" in line
    assert "+Y" in line, f"die Richtung steht darin, gelesen wurde {line!r}"


# --- Und was sich daran noch tun lässt ---------------------------------------------


def run_op(op: str, entry: SceneObject, profile: Profile, **params: object) -> SceneObject:
    """Eine Operation fahren und danach neu erkennen, wie die Auswertung es tut."""
    from app.core.scene.cancel import NeverCancelled

    load_operations()
    spec = REGISTRY.get(op)
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, options: options[0],
            cancelled=NeverCancelled(),
        )
    )
    out = result.outputs[0]
    run_op.findings = list(result.findings)  # type: ignore[attr-defined]
    return dataclasses.replace(out, features=detect(as_mesh_data(out.mesh)))


def a_slotted_plate(profile: Profile) -> SceneObject:
    mesh = slotted(profile)
    return SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))


def test_pulling_an_existing_slot_keeps_its_direction(profile: Profile) -> None:
    """Ohne diese Vorgabe stellte ein Zug an der Länge das Loch quer.

    Das Feld *Richtung* steht auf null, und null heißt an einer **Bohrung**
    „die erste Achse der Fläche". An einem Langloch, das schon irgendwo liegt,
    hieße es „dreh es dorthin" — und aus einem Zug an der Länge würde ein
    Kreuz.
    """
    entry = a_slotted_plate(profile)
    slot = next(name for name, f in entry.features.items() if f.kind == "slot")
    before = entry.features[slot].params["direction"]

    longer = run_op("slot_hole", entry, profile, at_feature=slot, slot_length=28.0)

    after = only_slot(as_mesh_data(longer.mesh))
    assert float(after.params["length"]) == pytest.approx(28.0, abs=0.05)
    parallel = abs(sum(a * b for a, b in zip(before, after.params["direction"], strict=True)))
    assert parallel == pytest.approx(1.0, abs=1e-6), "dieselbe Richtung wie vorher"


def test_pulling_a_slot_across_itself_says_what_it_makes(profile: Profile) -> None:
    """Ein Kreuz ist richtig gerechnet und meistens nicht gemeint."""
    entry = a_slotted_plate(profile)
    slot = next(name for name, f in entry.features.items() if f.kind == "slot")

    run_op("slot_hole", entry, profile, at_feature=slot, slot_length=24.0, slot_angle=90.0)

    codes = {finding.code for finding in run_op.findings}  # type: ignore[attr-defined]
    assert "slot_hole.crosses" in codes
    assert "slot_hole.feature_renamed" not in codes, (
        "aus einem Langloch wird kein Langloch — es wird länger"
    )


def test_a_slot_offers_the_one_operation_that_fits_it() -> None:
    """Ein Merkmal ohne Handlung ist eine Sackgasse (§2.6).

    Gemessen am Weg: An einem erkannten Langloch standen fünf ausgegraute
    Zeilen und **null** Knöpfe — die Operation gab es im Register längst, die
    Oberfläche bot sie nur nicht an.

    **Seit dem 10.09.2026 steht sie eine Karte höher**, als Zeile mit Feldern
    im Merkmalsfenster (``perceive.actions.ACTION_ORDER``): Der Knopf allein
    ließ den Kunden die Maße sehen und keines davon ändern (Robert: „langloch
    merkmale hat noch in der auswahl keine einstellungen"). Was dort als Feld
    steht, bekommt in der Auswahlkarte darunter **keinen zweiten Knopf** —
    dieselbe Regel, an der schon *Bohrung ändern* hängt. Der Test prüft
    deshalb beide Seiten: dass die Zeile mit ihren zwei Maßen dasteht, und dass
    die Karte darunter schweigt.
    """
    from app.core.perceive.actions import actions_for
    from app.ui.selection_operations import quick_names

    load_operations()
    slot = Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        params={
            "diameter": 5.0,
            "length": 20.0,
            "travel": 15.0,
            "axis": (0.0, 0.0, 1.0),
            "direction": (1.0, 0.0, 0.0),
            "centre": (0.0, 0.0, 0.0),
            "depth": 10.0,
            "through": True,
        },
    )

    assert "slot_hole" in {spec.name for spec in REGISTRY.for_feature("slot")}
    zeile = next(action for action in actions_for(slot) if action.op == "slot_hole")
    # Länge, Richtung — **und die Stelle**: Seit dem 10.09.2026 führt
    # ``slot_hole`` seine Mitte selbst, damit es dieselbe Flächenplatzierung
    # bekommt wie *Bohrung setzen* (Robert: „einfach wie wenn ich eine bohrung
    # setze"). Die drei Felder tragen den gemessenen Ort.
    assert {field.name for field in zeile.fields} == {
        "slot_length",
        "slot_angle",
        "x",
        "y",
        "z",
    }
    werte = {field.name: field.value for field in zeile.fields}
    assert (werte["x"], werte["y"], werte["z"]) == pytest.approx((0.0, 0.0, 0.0)), (
        "die Stelle steht auf der gemessenen Mitte, nicht auf dem Ursprung von irgendwo"
    )
    assert quick_names(1, "slot") == (), "was als Feld dasteht, wird kein zweiter Knopf"


def test_a_slot_says_why_the_generic_actions_do_not_fit() -> None:
    """Was nicht gilt, steht trotzdem in der Liste — mit einem Grund (Regel 17)."""
    from app.core.perceive.actions import NOT_APPLICABLE, actions_for

    load_operations()
    slot = Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        params={
            "diameter": 5.0,
            "length": 20.0,
            "travel": 15.0,
            "axis": (0.0, 0.0, 1.0),
            "direction": (1.0, 0.0, 0.0),
            "centre": (0.0, 0.0, 0.0),
            "depth": 10.0,
            "through": True,
        },
    )

    assert "slot" in NOT_APPLICABLE
    reasons = {str(action.reason) for action in actions_for(slot) if action.op is None}
    assert reasons, "die generischen Zeilen stehen da"
    assert all("Langloch" in reason for reason in reasons)


# --- Der Durchgang wird geschnitten, nicht abgetastet ------------------------------


def slot_in_a_plate(width: float, length: float) -> MeshData:
    """80 x 40 x 10 mit einem durchgehenden Langloch, gebaut aus Booleschen.

    Nicht über ``drill``: Dieser Abschnitt prüft, was die Erkennung an einem
    fremden Netz liest, und ein Werkzeug, das seinen eigenen Erzeuger misst,
    prüft die Absicht statt der Sache.
    """
    body = MeshData.of(trimesh.creation.box(extents=(80.0, 40.0, 10.0)))
    travel = length - width
    tool = MeshData.of(trimesh.creation.box(extents=(travel, width, 20.0)))
    for x in (-travel / 2.0, travel / 2.0):
        cap = trimesh.creation.cylinder(radius=width / 2.0, height=20.0, sections=64)
        cap.apply_translation((x, 0.0, 0.0))
        tool = boolean("union", [tool, MeshData.of(cap)]).mesh
    return boolean("difference", [body, tool]).mesh


def with_a_bridge(mesh: MeshData, thickness: float, at: float, width: float) -> MeshData:
    """Ein schmaler Steg quer über das Loch, im oberen Drittel."""
    bridge = trimesh.creation.box(extents=(thickness, width + 2.0, 3.0))
    bridge.apply_translation((at, 0.0, 3.5))
    return boolean("union", [mesh, MeshData.of(bridge)]).mesh


@pytest.mark.parametrize(("thickness", "at"), [(0.42, 7.7), (0.5, 3.0), (1.0, 3.125), (1.3, 3.125)])
def test_a_bridge_across_a_slot_takes_its_through(thickness: float, at: float) -> None:
    """Wer hindurchsieht, sieht hindurch — und wer nicht, nicht.

    **Der Fall, der die Abtastung abgelöst hat.** ``_reaches_through`` prüfte
    die Mittellinie in Schritten von einem halben Radius und begründete das
    mit „schmaler als jedes Stück Material, das ein Drucker legen kann". Bei
    Ø 5 sind das 1,25 mm; eine Extrusionsbahn ist 0,42 mm breit. Gemessen kamen
    Brücken von 0,5 und 1,0 mm als „Durchgang" zurück, eine von 1,3 mm nicht —
    es entschied, ob der Steg zufällig auf einen Abtastpunkt fiel.

    Die vier Fälle hier liegen absichtlich **zwischen** den alten Punkten
    (0 · ±1,25 · ±2,5 · ±3,75 …).
    """
    open_slot = slot_in_a_plate(5.0, 40.0)
    assert only_slot(open_slot).params["through"], "die Vorbedingung: offen ist offen"

    blocked = with_a_bridge(open_slot, thickness, at, 5.0)

    assert not only_slot(blocked).params["through"]


def test_a_slot_without_a_bridge_still_goes_through() -> None:
    """Die Gegenprobe zur Gegenprobe: Der strengere Test darf nicht alles zumachen."""
    assert only_slot(slot_in_a_plate(8.0, 30.0)).params["through"]


# --- Was der Agent liest ----------------------------------------------------------


@pytest.mark.parametrize("angle", [15.0, 30.0, 45.0, -45.0])
def test_the_digest_does_not_round_a_slanted_slot_onto_an_axis(
    angle: float, profile: Profile
) -> None:
    """Eine Rundung, die als Tatsache dasteht, ist eine stille Wahl (Regel 21).

    ``_axis_name`` nimmt die größte Komponente. Für die **Achse** einer Bohrung
    ist das richtig; die **Richtung** eines Langlochs ist ein stetiger Wert, und
    gemessen sagten 0, 15, 30, 44, 45 und minus 45 Grad alle sechs „+X".
    """
    from app.i18n import set_language

    set_language("de")
    slot = only_slot(slotted(profile, slot_angle=angle))

    line = _feature_line(slot.id, slot)
    assert "+X" not in line and "+Y" not in line, (
        f"eine schräge Richtung bekommt keinen Achsennamen — gelesen wurde {line!r}"
    )


@pytest.mark.parametrize(("angle", "wanted"), [(0.0, "+X"), (90.0, "+Y"), (0.3, "+X")])
def test_the_digest_names_the_axis_where_it_really_is_one(
    angle: float, wanted: str, profile: Profile
) -> None:
    """Und die andere Richtung: Wo eine Achse ist, steht ihr Name.

    0,3 Grad ist die Rundung, mit der eine gemessene Richtung aus dem Netz
    kommt — dort einen Vektor zu drucken wäre genauso falsch wie umgekehrt.
    """
    from app.i18n import set_language

    set_language("de")
    slot = only_slot(slotted(profile, slot_angle=angle))

    assert wanted in _feature_line(slot.id, slot)


def test_a_slot_is_not_called_a_sleeve() -> None:
    """Ein Langloch hat keine gleichmäßige Wand — also nennt niemand eine.

    ``is_a_cavity`` führt ``slot`` bewusst nicht: Sein größter Leser
    (``relations.sleeve_at``) rechnet den halben Unterschied zweier Durchmesser
    und meldete damit an einem Zapfen Ø 20 mit einem Langloch Ø 8 auf 14 mm
    **6 mm** Wand, wo die dünnste Stelle 3 mm misst. Die Begründung steht an
    der Funktion; dieser Test hält fest, dass die Auskunft schweigt statt zu
    raten.
    """
    from app.core.perceive.relations import sleeve_at

    pin = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=96)
    tool = MeshData.of(trimesh.creation.box(extents=(6.0, 8.0, 40.0)))
    for x in (-3.0, 3.0):
        cap = trimesh.creation.cylinder(radius=4.0, height=40.0, sections=64)
        cap.apply_translation((x, 0.0, 0.0))
        tool = boolean("union", [tool, MeshData.of(cap)]).mesh
    body = boolean("difference", [MeshData.of(pin), tool]).mesh
    found = detect(body)
    slot = next(entry for entry in found.values() if entry.kind == "slot")

    assert sleeve_at(slot, found) is None


def test_the_slot_defaults_make_a_slot_and_not_an_error(profile: Profile) -> None:
    """Ein Feld, das mit einer Absage begrüßt, ist keine Vorgabe (Regel 17).

    Die Vorgabe der Länge stand auf 5,0 — dem Durchmesser einer gewöhnlichen
    Bohrung —, und ein Langloch muss länger sein als seiner. Wer den Dialog
    öffnete und übernahm, legte damit einen Schritt an, der bei **jeder**
    Auswertung anhält, auch bei jedem späteren Öffnen des Projekts (gefahren
    am 10.09.2026 an Roberts `weg1-halterung-anpassen.p3d`, Protokoll:
    „evaluation stopped at op 5").

    Gefahren wird hier der Weg ohne Merkmalsvorbelegung — Kommandozeile, Chat,
    Palette: nur ``at_feature``, alles andere aus dem Schema.
    """
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate(), features={})
    gebohrt = run_op(
        "drill_hole", entry, profile, x=0.0, y=0.0, z=5.0, axis="z", diameter=5.0, depth=0.0
    )
    bore = next(name for name, f in gebohrt.features.items() if f.kind == "hole")

    longer = run_op("slot_hole", gebohrt, profile, at_feature=bore)

    assert any(feature.kind == "slot" for feature in longer.features.values()), (
        "aus der Vorgabe entsteht ein Langloch und keine Absage"
    )


def test_a_slot_moves_and_closes_the_place_it_came_from(profile: Profile) -> None:
    """Wer versetzt, schließt die alte Stelle — sonst stehen zwei Löcher da.

    *Zum Langloch ziehen* führt seit dem 10.09.2026 seine eigene Mitte, damit es
    dieselbe Flächenplatzierung bekommt wie *Bohrung setzen* (Robert: „einfach
    wie wenn ich eine bohrung setze"). Gemessen ohne das Schließen: `hole_1`
    und `slot_1` im selben Körper, die alte Bohrung unverändert offen.

    Drei Nullen heißen dabei „lass es, wo es ist" — der Weg über Chat und
    Kommandozeile nennt keine Stelle, und der Ursprung wäre dort die falsche
    Antwort.
    """
    mesh = drill(
        plate(),
        profile=profile,
        position=(10.0, 5.0, 5.0),
        axis="z",
        diameter=6.0,
        compensate=False,
    ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    bore = next(name for name, feature in entry.features.items() if feature.kind == "hole")

    versetzt = run_op(
        "slot_hole", entry, profile, at_feature=bore, slot_length=20.0, x=-10.0, y=-8.0, z=0.0
    )

    arten = [feature.kind for feature in versetzt.features.values()]
    assert arten.count("slot") == 1, "genau ein Langloch"
    assert "hole" not in arten, "und die alte Bohrung ist zu"
    slot = next(feature for feature in versetzt.features.values() if feature.kind == "slot")
    assert slot.params["centre"] == pytest.approx((-10.0, -8.0, 0.0), abs=0.05)

    # Und ohne Stelle bleibt es, wo es war.
    geblieben = run_op("slot_hole", entry, profile, at_feature=bore, slot_length=20.0)
    stehend = next(feature for feature in geblieben.features.values() if feature.kind == "slot")
    assert stehend.params["centre"] == pytest.approx((10.0, 5.0, 0.0), abs=0.05)


@pytest.mark.parametrize("diameter", [2.0, 5.0, 12.0, 20.0, 40.0])
def test_a_length_the_recognition_cannot_hold_is_refused(diameter: float, profile: Profile) -> None:
    """Was hinterher kein Merkmal mehr wäre, wird vorher abgelehnt (Regel 17).

    **Der Anlass ist gemessen** (11.09.2026, Ø 2 bis Ø 40 in beiden
    Qualitätsstufen). Direkt über der alten Grenze — „länger als der
    Durchmesser" — liegt ein Streifen, in dem die Erkennung das Ergebnis nicht
    mehr als Langloch liest: erst als **Bohrung**, weil ein Zylinder auf den
    Mantel noch passt, und darüber als **gar nichts**, weil weder Zylinder noch
    Bogenpaar greifen. Ø 12 mit der Länge 12,5 ergab null Merkmale: kein
    Eintrag im Objektbaum, keine Maße im Bild, nichts zum Anklicken (Robert:
    „es gibt noch Fälle, wo das Langloch keine Maße im Viewport hat, nicht
    wählbar ist, im Objektbaum verschwindet").

    Der Griff im Bild rastet an :func:`prepare.shortest_slot`; über den Dialog,
    den Chat und die Kommandozeile kommt aber jede Zahl herein. Also fragt die
    Operation, und zwar gegen den **gemessenen** Durchmesser — gegen ihn misst
    auch die Erkennung.
    """
    entry = SceneObject(
        id="obj_1",
        name="Platte",
        mesh=MeshData.of(trimesh.creation.box(extents=(160.0, 120.0, 12.0))),
        features={},
    )
    drilled = run_op(
        "drill_hole", entry, profile, x=0.0, y=0.0, z=6.0, axis="z", diameter=diameter, depth=0.0
    )
    bore = next(feature for feature in drilled.features.values() if feature.kind == "hole")
    measured = float(bore.params["diameter"])
    shortest = shortest_slot(measured)

    # Eine Länge aus dem Streifen: über dem Durchmesser, unter der Grenze.
    with pytest.raises(ValidationError) as refused:
        run_op(
            "slot_hole",
            drilled,
            profile,
            at_feature=bore.id,
            slot_length=(measured + shortest) / 2.0,
        )
    assert refused.value.field == "slot_length"
    assert "shortest" in refused.value.values, (
        "die Absage nennt die Länge, die geht — sonst ist sie keine Handlungsanweisung"
    )

    # Und die Grenze selbst trägt: dort steht hinterher ein Langloch.
    pulled = run_op("slot_hole", drilled, profile, at_feature=bore.id, slot_length=shortest)
    arten = [feature.kind for feature in pulled.features.values()]
    assert arten.count("slot") == 1, f"Ø {diameter}: gefunden {arten}"


@pytest.mark.parametrize(
    ("kind", "values"),
    [
        ("über den Rand", {"slot_length": 20.0, "x": 38.0, "y": 0.0, "z": 5.0}),
        ("quer über sich selbst", {"slot_length": 26.0, "slot_angle": 90.0}),
    ],
)
def test_a_slot_that_is_no_longer_one_says_so(
    kind: str, values: dict[str, float], profile: Profile
) -> None:
    """Ein Merkmal, das verschwindet, verschwindet nicht schweigend (Regel 17).

    Zwei Wege führen dahin, und beide sind gemessen (11.09.2026): Wer über den
    Rand des Körpers zieht, bekommt einen offenen Schlitz und danach eine bis
    drei Verrundungen; wer quer über das eigene Langloch zieht, ein Kreuz und
    vier. Beides ist gültige Geometrie — der Schnitt stimmt, das Teil ist
    brauchbar —, und beides ist kein Langloch mehr. Im Objektbaum standen
    danach Verrundungen, die Auswahl zeigte ins Leere, und gesagt wurde nichts
    (Robert: „auf einem langloch 2 werden und nicht mehr wählbar").

    Der Befund sagt beides und nennt den Rückweg über Strg+Z.
    """
    mesh = drill(
        plate(),
        profile=profile,
        position=(0.0, 0.0, 5.0),
        axis="z",
        diameter=6.0,
        compensate=False,
    ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    bore = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    started = (
        run_op("slot_hole", entry, profile, at_feature=bore, slot_length=20.0)
        if "sich selbst" in kind
        else entry
    )
    chosen = (
        next(name for name, feature in started.features.items() if feature.kind == "slot")
        if started is not entry
        else bore
    )

    pulled = run_op("slot_hole", started, profile, at_feature=chosen, **values)

    codes = [entry.code for entry in run_op.findings]  # type: ignore[attr-defined]
    assert "slot_hole.feature_lost" in codes, f"{kind}: gesagt wird es, gefunden: {codes}"
    lost = next(
        entry
        for entry in run_op.findings  # type: ignore[attr-defined]
        if entry.code == "slot_hole.feature_lost"
    )
    assert lost.severity == "warning"
    assert not any(feature.kind == "slot" for feature in pulled.features.values()), (
        f"{kind}: und ein Langloch ist wirklich keines mehr"
    )


def test_the_same_word_comes_from_the_exact_kernel(profile: Profile) -> None:
    """„Zwischen den beiden soll es keinen unterschied geben" (Robert, 10.09.2026).

    Der exakte Zweig erkennt seine Merkmale über die Topologie
    (``brep.features.features_of``) und lief deshalb an der Prüfung des
    Netz-Zweigs vorbei: dieselbe Geste, dasselbe Ergebnis, kein Wort dazu.
    """
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
    from app.core.brep import edit
    from app.core.brep.features import features_of

    solid = edit.cut_bore(
        edit.box(90.0, 60.0, 10.0),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=10.0,
    )
    entry = SceneObject(
        id="obj_1", name="Platte", mesh=solid, kind="brep", features=features_of(solid)
    )
    bore = next(name for name, feature in entry.features.items() if feature.kind == "hole")

    run_op("slot_hole", entry, profile, at_feature=bore, slot_length=20.0, x=38.0, y=0.0, z=5.0)

    codes = [found.code for found in run_op.findings]  # type: ignore[attr-defined]
    assert "slot_hole.feature_lost" in codes, codes
