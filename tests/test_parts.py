"""Die Bausteinbibliothek (Bauplan §24).

§24.3 setzt die Latte: jeder Baustein wird über seinen gesamten
Parameterbereich gerechnet — wasserdicht, Mindestwandstärke, keine
Selbstdurchdringung an den Grenzen, Merkmale richtig benannt. **Ein Baustein
ohne diesen Test gilt als nicht vorhanden.** Also ist der Bereichstest über das
Register parametrisiert: ein neuer Baustein ist abgedeckt, sobald er deklariert
ist, und ein Baustein, der an seinen eigenen Grenzen scheitert, scheitert hier.
"""

from __future__ import annotations

import dataclasses
import itertools
from pathlib import Path
from typing import Any
from unittest import mock

import numpy as np
import pytest

from app.core.geom.boolean import boolean
from app.core.knowledge import standards
from app.core.knowledge.parts import LIBRARY_VERSION, PARTS, changed_since, missing_parts, shapes
from app.core.knowledge.parts import ops as part_ops
from app.core.knowledge.parts.range_check import corners as core_corners
from app.core.knowledge.parts.registry import PartRegistry, PartSpec, register_part
from app.core.registry import REGISTRY, op_params, param
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import BaseParams, PartResult, Profile, Source

MESHES = Path(__file__).parent / "data" / "meshes"


def ids(spec: PartSpec) -> str:
    return spec.name


def corners(spec: PartSpec) -> list[dict[str, Any]]:
    """Die Ecken des Parameterbereichs — seit dem 25.08.2026 aus dem Kern.

    Die Fassung mit der ganzen Geschichte (warum kein kartesisches Produkt,
    was der 24er-Schnitt gekostet hat) steht in
    :func:`app.core.knowledge.parts.range_check.corners` — dort läuft sie
    beim Kunden, wenn er ein Rezept anlegt (§24.5), hier läuft sie in der
    Suite. Eine Regel, ein Ort; die Kopie, die hier stand, wäre beim
    nächsten Nachbessern auseinandergelaufen.
    """
    return core_corners(spec.params)


# --- die Bibliothek ---------------------------------------------------------------


def test_the_library_has_the_first_set_from_the_plan() -> None:
    """§24.1 nennt dreizehn Bausteine für die erste Auslieferung, dazu sieben.

    Die Kalibrierkörper aus §28.3 sind auch Bausteine, gehören aber nicht zu
    diesem Satz — sie sind Werkzeuge für den Drucker, nicht für das Modell, und
    sie haben ihre eigene Gruppe im Katalog.

    **Sechs stehen nicht in der Erstbestückung**, und alle sechs sind eine Ansage
    und kein Versehen. Wer die Zahl hier ändert, ändert die Bibliothek, und das soll
    auffallen.

    ``snap_connector`` ist am 14.08.2026 dazugekommen, weil das Trennwerkzeug
    einen Verbinder brauchte, der einrastet. Die ``snap_fit`` des Plans ist etwas
    anderes — ein Arm, den man an eine Wand setzt; dieser hier ist ein Paar aus
    Arm und Tasche, bemaßt aus dem Durchmesser, den eine Naht hergibt.

    ``profile_tongue`` kam am 20.08.2026 dazu, und der Anlass lag nicht an einem
    Werkzeug, sondern in der Tabelle: Die Aluprofil-Nutmaße stehen seit der
    Erstbestückung in ``standards.toml``, weil §24.2 sie verlangt, und gelesen
    hat sie kein Baustein. Nachschlagen konnte man sie, verbauen nicht. Die zwei
    Maße, die eine Feder darüber hinaus braucht — Stegdicke und Kammertiefe —
    sind mit ihr in die Tabelle gekommen; sie ist seither auf Version 2.

    ``cable_clip`` kam am 24.08.2026 dazu, und der Anlass war eine Zählung. Die
    Gruppe „Kabel und Schläuche" hatte **einen** Eintrag, und der ist ein Loch
    (die Durchführung), kein Halter — während Kabelmanagement die
    meistgenannte Kategorie der Modellportale ist. Dieselbe Sorte Lücke wie bei
    ``profile_tongue``: Die Schlauchmaße standen seit der Erstbestückung in
    ``standards.toml``, und gelesen hat sie genau ein Baustein.

    ``pegboard_hook`` kam am 25.08.2026 dazu, und der Anlass war eine
    Kundenanfrage: an ein heruntergeladenes Modell IKEA-SKÅDIS-Haken hängen,
    ohne es nachzukonstruieren. Mit ihm kam eine neue Tabellenart — Lochwände
    sind keine Normteile, ihre Maße veröffentlicht niemand, und **gegeben sind
    sie trotzdem**: Wer einen Einhänger baut, hat sie nicht zu wählen, sondern
    zu treffen.

    ``gusset`` kam am 25.08.2026 dazu, aus derselben Durchsicht wie der
    Kabelclip: Die Versteifungsrippe hält **eine** Wand, und die Ecke zwischen
    zweien blieb offen — ein Eckwinkel steht auf jeder Liste häufig gedruckter
    Funktionsteile, und die Gruppe „Struktur" hatte zwei Einträge.

    ``foot`` kam am 25.08.2026 dazu, aus derselben Liste: Was auf dem Tisch
    steht, steht sonst auf seiner Druckkante. Er kann beides — ein gedruckter
    Fuß und die Tasche für einen gekauften aus Gummi —, und das ist kein
    Doppelbaustein, sondern dieselbe Form zweimal gelesen (``subtractive_on``,
    wie beim Passstift).

    ``hinge_eye`` kam am 25.08.2026 dazu und ist der letzte der Liste. Das
    Filmscharnier **biegt**, dieses hier **dreht** — zwei Augen und ein
    Passstift ergeben ein Gelenk, das hält. Ein Scharnier, das schon beim
    Drucken beweglich ist, wäre etwas anderes und ist keiner: Es bestünde aus
    zwei Teilen, und ein Baustein muss einer sein. Die Frage dahinter steht im
    Register.
    """
    building = [spec for spec in PARTS.all() if spec.group != "calibration"]

    assert len(building) == 20
    assert len([spec for spec in PARTS.all() if spec.group == "calibration"]) == 3


def test_every_part_is_completely_declared() -> None:
    for spec in PARTS.all():
        assert str(spec.title).strip(), f"{spec.name} has no title"
        assert str(spec.doc).strip(), f"{spec.name} has no documentation"
        assert spec.features, f"{spec.name} names no provenance features"
        assert spec.changes, f"{spec.name} has no change log (§24.4)"


def test_a_part_without_features_is_refused() -> None:
    """§24.1: Provenienz-Merkmale sind der Sinn eines Bausteins, keine
    Nettigkeit.
    """
    from app.core.errors import InternalError

    registry = PartRegistry()

    @op_params
    class Params(BaseParams):
        size: float = param(title="x", default=1.0)

    with pytest.raises(InternalError):

        @register_part(
            name="nameless", title="x", group="fasteners", params=Params, registry=registry
        )
        def nameless(raw: BaseParams) -> PartResult:  # pragma: no cover - läuft nie
            raise AssertionError


# --- Der Bereichstest, den §24.3 verlangt -----------------------------------------


@pytest.mark.parametrize("spec", PARTS.all(), ids=ids)
def test_a_part_holds_over_its_whole_range(spec: PartSpec, profile: Profile) -> None:
    minimum_wall = profile.minimum_wall_thickness

    for values in corners(spec):
        result = spec.fn(spec.params(**values))
        mesh = result.mesh

        assert mesh.is_watertight, f"{spec.name} {values} is not watertight"
        assert mesh.volume > 0.0, f"{spec.name} {values} has no volume"
        assert mesh.component_count == 1, f"{spec.name} {values} falls apart"
        assert min(mesh.bounds.size) > minimum_wall / 4.0, (
            f"{spec.name} {values} is thinner than a printer can make"
        )


@pytest.mark.parametrize("spec", PARTS.all(), ids=ids)
def test_a_part_names_the_features_it_promised(spec: PartSpec) -> None:
    """§24.1: was die Deklaration verspricht, muss aus der Funktion
    herauskommen.
    """
    result = spec.fn(spec.params())

    assert result.features, f"{spec.name} returned no features"
    for name, feature in result.features.items():
        assert feature.id == name
        assert feature.provenance == "generated"
        assert feature.params, f"{spec.name}.{name} carries no dimensions"


@pytest.mark.parametrize("spec", PARTS.all(), ids=ids)
def test_a_part_is_reproducible(spec: PartSpec) -> None:
    """Leitprinzip 4: dieselben Parameter geben dieselbe Geometrie."""
    first = spec.fn(spec.params())
    second = spec.fn(spec.params())

    assert first.mesh.volume == pytest.approx(second.mesh.volume, rel=1e-9)
    assert first.mesh.triangle_count == second.mesh.triangle_count


def by_direction(subtractive: bool) -> list[tuple[PartSpec, BaseParams]]:
    """Je Baustein und Richtung ein Paar aus Bauplan und Werten.

    **Drei Bausteine fielen durch beide Netze.** Passstift, Standfuß und
    Schnappverbinder entscheiden die Richtung über einen Parameter; sie sind
    weder ``spec.subtractive`` (das gilt nur für die fest abtragenden) noch
    ``not cuts(spec, None)`` (ohne Werte zählt ein umschaltbarer als
    abtragend). Der subtraktive Test kannte sie damit nicht und der additive
    auch nicht — gemessen am 25.08.2026 prüfte niemand, ob die Fußtasche
    überhaupt ins Material reicht.

    **Der Fehler, der dort tatsächlich saß, wäre auch damit nicht aufgefallen:**
    Der Sitz der Tasche war um zwei Fasen zu eng für den Fuß, für den sie
    gedacht ist, und ins Material reichte sie trotzdem. Ein geschlossenes Netz
    ist keine geprüfte Zusage; dafür steht
    :func:`test_the_pocket_takes_the_foot_it_is_meant_for` daneben. Das Loch
    hier zu schließen ist trotzdem richtig — ein Loch **zwischen** zwei Listen
    ist schlechter als eines in einer: Beide sahen vollständig aus, und was
    dazwischen durchfiel, tauchte in keiner Fehlliste auf.

    Die Richtung kommt deshalb aus derselben Quelle wie für die Operation
    selbst (``cuts_by_parameter``) und nicht aus einer Eigenschaft, die sie nur
    halb beschreibt.
    """
    pairs: list[tuple[PartSpec, BaseParams]] = []
    for spec in PARTS.all():
        choice = part_ops.cuts_by_parameter(spec.params)
        if choice is None:
            if spec.subtractive is subtractive:
                pairs.append((spec, spec.params()))
            continue
        name, cutting = choice
        entry = next(item for item in spec.params.spec() if item.name == name)
        for value in entry.choices or ():
            if (value in cutting) is subtractive:
                pairs.append((spec, spec.params(**{name: value})))
    return pairs


def direction_ids(pair: tuple[PartSpec, BaseParams]) -> str:
    spec, values = pair
    choice = part_ops.cuts_by_parameter(spec.params)
    if choice is None:
        return spec.name
    return f"{spec.name}[{getattr(values, choice[0])}]"


SUBTRACTIVE = by_direction(subtractive=True)


@pytest.mark.parametrize("pair", SUBTRACTIVE, ids=direction_ids)
def test_a_subtractive_part_reaches_into_the_material(
    pair: tuple[PartSpec, BaseParams],
) -> None:
    """§24.1: der Ursprung ist die Mündung, das Werkzeug geht nach unten.

    Wer eine Fläche anklickt, bekommt ihre Höhe in die Position eingetragen.
    Ein Werkzeug, das von dort nach *oben* wächst, steht in der Luft und trägt
    nichts ab — genau das taten Magnettasche, Schlüsselloch und
    Kabeldurchführung, bis die Bibliothek auf Version 2 ging.

    Gemessen wird an der Wirkung, nicht an den Koordinaten: der Baustein sitzt
    auf der Oberseite einer Platte, und danach hat sie weniger Volumen.
    """
    spec, values = pair
    plate = shapes.box(60.0, 60.0, 20.0)
    tool = shapes.moved(spec.fn(values).mesh, (0.0, 0.0, 20.0))
    cut = boolean("difference", [plate, tool])

    assert cut.mesh.volume < plate.volume - 1.0, (
        f"{direction_ids(pair)} trägt an der angeklickten Fläche nichts ab"
    )


# --- was die drei Neuen versprechen -------------------------------------------------
#
# Sie hatten keinen Test ihrer Zusage, und deshalb kamen drei Fehler durch, die
# jede Kennzahl bestanden: Die Fußtasche war zu eng für ihren Fuß, ihr Merkmal
# meldete einen anderen Durchmesser als das Loch, und die Fase des Fußes saß am
# falschen Ende. Volumen, Wasserdichtheit, Komponentenzahl und Hüllquader waren
# bei allen dreien in Ordnung.


def _section_diameter(mesh: Any, height: float) -> float:
    """Der größte Durchmesser eines Querschnitts auf dieser Höhe.

    Über einen Schnitt und nicht über die Eckpunkte: Ein extrudierter oder
    gedrehter Körper hat zwischen seinen Enden keine.
    """
    cut = mesh.raw.section(plane_origin=[0.0, 0.0, height], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None, f"nothing to measure at z={height}"
    points = np.asarray(cut.vertices, dtype=float)
    return 2.0 * float(np.hypot(points[:, 0], points[:, 1]).max())


@pytest.mark.parametrize(("height", "diameter"), [(5.0, 10.0), (30.0, 10.0), (3.0, 25.0)])
def test_the_foot_tapers_towards_the_table_and_not_towards_the_part(
    height: float, diameter: float
) -> None:
    """Die Verjüngung gehört ans Standende, sonst steht der Fuß auf seiner Kante.

    Ein Zylinder mit scharfer Kante bekommt beim Drucken einen Elefantenfuß:
    Die erste Schicht quetscht breiter als die zweite und steht als Grat vor.
    Ein Kegelstumpf, der zum Tisch hin schmaler wird, hat den Grat dort, wo
    ohnehin Luft ist.

    **Die erste Fassung setzte ihn ans Anbau-Ende** — genau umgekehrt zu dem
    Absatz, den ihr eigener Docstring schon so enthielt. Keine Kennzahl
    bemerkte es: Volumen, Wasserdichtheit und Hüllquader sind bei beiden Lagen
    identisch. Gemessen wird deshalb an zwei Querschnitten, und die Richtung
    steht zwischen ihnen.
    """
    spec = PARTS.get("foot")
    built = spec.fn(spec.params(kind="foot", diameter=diameter, height=height)).mesh

    at_part = _section_diameter(built, 0.15)
    at_table = _section_diameter(built, height - 0.15)
    assert at_table < at_part - 0.1, (
        f"h={height} d={diameter}: {at_part:.2f} mm at the part and {at_table:.2f} mm "
        "at the table — the foot stands on its sharp edge"
    )


@pytest.mark.parametrize(("height", "diameter"), [(5.0, 10.0), (30.0, 10.0), (3.0, 25.0)])
def test_the_pocket_takes_the_foot_it_is_meant_for(height: float, diameter: float) -> None:
    """Eine Tasche für einen Ø-10-Gummifuß muss zehn Millimeter weit sein.

    **Sie war es nicht.** Der Schaft wurde mit dem *schmalen* Kegeldurchmesser
    gebaut, also um zwei Fasen zu eng: Ein Ø-10-Fuß fand ein Loch von 9,05 mm
    vor, und an der Bereichsecke (Höhe 30, Ø 10) maß der Sitz noch einen
    einzigen Millimeter. Eine Einführschräge weitet die Mündung, sie verengt
    nicht den Sitz.

    Gemessen wird an der Stelle, an der der Fuß sitzt — am tiefen Ende, nicht
    an der Mündung, wo die Schräge das Ergebnis freundlich aussehen lässt.
    """
    spec = PARTS.get("foot")
    values = spec.params(kind="pocket", diameter=diameter, height=height, play=0.25)
    built = spec.fn(values).mesh

    seat = _section_diameter(built, -height + 0.15)
    assert seat >= diameter, f"h={height}: the seat measures {seat:.2f} mm for a {diameter} mm foot"

    mouth = _section_diameter(built, -0.15)
    assert mouth >= seat, "the lead-in chamfer narrows the mouth instead of widening it"
    assert mouth < seat + 4.0, (
        f"h={height}: the mouth flares to {mouth:.2f} mm over a {seat:.2f} mm seat — "
        "a lead-in chamfer is a bevel, not a funnel"
    )


def test_the_pocket_names_the_hole_it_actually_cuts() -> None:
    """Was das Merkmal meldet, muss das Loch auch messen.

    Ein Merkmal ist eine Zusage an den nächsten Schritt: Wer daran ausrichtet,
    rechnet mit der Zahl, die dort steht. ``foot_1`` nannte den vollen
    Durchmesser, während das Loch zwei Fasen enger war — eine Passung, die auf
    dem Papier stimmte und im Druck geklemmt hätte.
    """
    spec = PARTS.get("foot")
    values = spec.params(kind="pocket", diameter=10.0, height=5.0, play=0.25)
    built = spec.fn(values)
    named = built.features["foot_1"].params["diameter"]

    assert _section_diameter(built.mesh, -5.0 + 0.15) == pytest.approx(named, abs=0.15), (
        f"the feature promises {named:.2f} mm, the hole is something else"
    )


def test_the_hinge_eye_names_the_axis_its_bore_actually_runs_on() -> None:
    """Die Drehachse liegt quer, nicht senkrecht.

    ``lying()`` legt den Zylinder um, damit die Achse parallel zur Fläche
    läuft — das ist der Sinn eines Scharniers. Das Merkmal sagte trotzdem
    ``(0, 0, 1)``, weil das die Vorgabe von :func:`bore` ist und niemand sie
    überschrieb. Ein Passstift, an ``eye_1`` ausgerichtet, stünde damit
    senkrecht aus dem Auge heraus statt hindurch.

    Geprüft wird beides gegeneinander: die genannte Achse und die, auf der das
    Loch wirklich liegt. Eine Angabe, die nur mit sich selbst übereinstimmt,
    ist keine.
    """
    spec = PARTS.get("hinge_eye")
    values = spec.params(pin=4.0, width=10.0, reach=8.0)
    built = spec.fn(values)
    named = tuple(built.features["eye_1"].params["axis"])

    assert named == pytest.approx((1.0, 0.0, 0.0)), f"eye_1 claims the axis is {named}"

    # Und das Loch liegt wirklich dort: Quer zur genannten Achse geschnitten
    # zeigt sich der Ring um die Bohrung — als zwei getrennte Konturen.
    across = built.mesh.raw.section(
        plane_origin=[0.0, values.reach, 0.0], plane_normal=[1.0, 0.0, 0.0]
    )
    assert across is not None, "nothing crosses the eye at all"
    assert len(across.entities) >= 2, (
        "a cut across the named axis shows one contour — the bore does not run there"
    )


def test_the_hinge_eye_lets_the_pin_through_that_it_asks_for() -> None:
    """Ein Auge für einen 4er Bolzen muss einen 4er Bolzen durchlassen.

    Die Zusage steht im Parameter: ``pin`` ist der Durchmesser des Bolzens, der
    hindurchgeht. Das Loch muss ihn samt Spiel aufnehmen, und es muss **durch**
    gehen — ein Sackloch hielte das Gegenstück nur auf einer Seite.
    """
    spec = PARTS.get("hinge_eye")
    for pin in (2.0, 4.0, 8.0):
        values = spec.params(pin=pin, width=10.0, reach=8.0, play=0.2)
        built = spec.fn(values)
        assert built.features["eye_1"].params["diameter"] >= pin, (
            f"pin={pin}: the bore is narrower than the pin it names"
        )
        assert built.features["eye_1"].params.get("through") is True, (
            f"pin={pin}: the bore does not go through, so no pin can pass"
        )
        assert built.mesh.is_watertight and built.mesh.component_count == 1, (
            f"pin={pin}: the eye falls apart"
        )


def test_the_gusset_fills_the_corner_it_is_put_into() -> None:
    """Ein Eckwinkel, der die Ecke nicht berührt, hält nichts.

    Die Zusage ist eine Diagonale zwischen zwei Wänden: Der Körper muss an
    beiden anliegen und dazwischen Material haben. Ein Dreieck, das die Ecke
    verfehlt, sieht im Hüllquader genauso aus.
    """
    spec = PARTS.get("gusset")
    for wall in (0.8, 2.0, 5.0):
        built = spec.fn(spec.params(wall=wall)).mesh
        low = built.bounds.minimum

        assert built.is_watertight and built.component_count == 1, f"wall={wall}: falls apart"
        # Beide Schenkel beginnen an der Ecke, nicht daneben.
        assert abs(float(low[1])) < 0.05, f"wall={wall}: the gusset does not touch the wall"
        assert abs(float(low[2])) < 0.05, f"wall={wall}: the gusset does not touch the floor"

        # Und es ist eine Rampe, kein Quader: weiter unten als oben.
        high = float(built.bounds.maximum[2])
        near = built.raw.section(plane_origin=[0.0, 0.0, high * 0.1], plane_normal=[0.0, 0.0, 1.0])
        far = built.raw.section(plane_origin=[0.0, 0.0, high * 0.9], plane_normal=[0.0, 0.0, 1.0])
        assert near is not None, f"wall={wall}: nothing at the base"
        reach_near = float(np.asarray(near.vertices, dtype=float)[:, 1].max())
        reach_far = (
            float(np.asarray(far.vertices, dtype=float)[:, 1].max()) if far is not None else 0.0
        )
        assert reach_far < reach_near, (
            f"wall={wall}: the gusset reaches {reach_far:.1f} mm out at the top and "
            f"{reach_near:.1f} mm at the base — that is a block, not a brace"
        )


# --- die Normteiltabelle -----------------------------------------------------------


def test_the_table_answers_the_question_from_the_plan() -> None:
    """§24.2: „Loch für eine M4-Einpressbuchse" muss ein Nachschlagen sein."""
    assert standards.insert("M4").hole == pytest.approx(5.6)
    assert standards.screw("M4").clearance == pytest.approx(4.5)
    assert standards.nut("M4").width == pytest.approx(7.0)


def test_every_screw_has_the_holes_that_belong_to_it() -> None:
    for size in standards.screw_sizes():
        entry = standards.screw(size)
        assert entry.tap < entry.nominal < entry.clearance < entry.countersink
        assert entry.pitch > 0.0


def test_every_table_can_be_looked_up_by_its_kind() -> None:
    """§24.2 verlangt jede Tabelle als Nachschlagewert, und der Weg dorthin
    geht über ``standards.TABLES``.

    Die Zuordnung Art → Tabelle lag in ``agent/session.py``, mit einem
    ``getattr`` daneben — eine neunte Tabelle hätte also zwei Dateien
    gebraucht, und die zweite vergisst man still. Sie steht jetzt neben den
    Tabellen, und dieser Test hält beides zusammen: Jedes Feld von ``Tables``
    ist über eine Art erreichbar, und jede Art zeigt auf ein Feld, das es
    gibt.
    """
    import dataclasses

    tables = standards.load()
    fields = {
        field.name
        for field in dataclasses.fields(tables)
        if isinstance(getattr(tables, field.name), dict)
    }

    assert set(standards.TABLES.values()) == fields, (
        "Tabelle ohne Art oder Art ohne Tabelle — "
        f"benannt {sorted(standards.TABLES.values())}, vorhanden {sorted(fields)}"
    )
    for kind in standards.TABLES:
        found = standards.table(kind)
        assert found, f"{kind} liefert keine Tabelle"
    assert standards.table("kein-normteil") is None


def test_an_unknown_size_says_what_is_known() -> None:
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as raised:
        standards.screw("M42")
    assert "M4" in str(raised.value.values["known"])


# --- Die Operationen, die aus den Bausteinen entstehen ----------------------------


def test_every_part_became_an_operation() -> None:
    """§10, Leitprinzip 3: einmal deklariert, und jede Oberfläche folgt."""
    for spec in PARTS.all():
        assert REGISTRY.has(part_ops.op_name(spec.name)), spec.name


def test_a_part_operation_carries_its_own_parameters_and_a_place() -> None:
    spec = REGISTRY.get("insert_screw_hole")
    names = {entry.name for entry in spec.params.spec()}

    assert {"size", "depth", "countersink"} <= names, "the part's own parameters"
    assert {"x", "y", "z", "axis", "angle"} <= names, "and where it goes"
    assert spec.category == "parts"


def project_with_plate() -> Project:
    made = new_project("centauri-carbon-2", "petg")
    made.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    made.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    History(made.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    return made


def test_a_subtractive_part_removes_material(profile: Profile) -> None:
    project = project_with_plate()
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]

    History(project.document).apply(
        "Buchse",
        [
            OperationDraft(
                op="insert_heatset_m4",
                inputs=("obj_1",),
                params={"size": "M3", "x": 0.0, "y": 0.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=sources)

    assert result.complete, [f.message for f in result.scene.report.findings]
    after = result.scene.objects["obj_1"]
    assert after.mesh.volume < before.mesh.volume, "a pressed-in insert needs a hole"


def _plate_and(name: str, params: dict[str, Any], profile: Profile) -> tuple[Any, Any]:
    """Die Platte vorher und nachher, mit einem Baustein dazwischen."""
    project = project_with_plate()
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]
    History(project.document).apply(
        name, [OperationDraft(op=name, inputs=("obj_1",), params=params)]
    )
    result = evaluate(project.document, profile, sources=sources)
    assert result.complete, [f.message for f in result.scene.report.findings]
    return before, result.scene.objects["obj_1"]


@pytest.mark.parametrize(
    ("name", "params"),
    [
        ("insert_dowel", {"diameter": 8.0, "length": 6.0, "shape": "hex"}),
        ("insert_snap_connector", {}),
    ],
)
def test_a_bore_removes_material_and_a_pin_adds_it(
    name: str, params: dict[str, Any], profile: Profile
) -> None:
    """Beide Bausteine sind ein **Paar**, und welche Hälfte gemeint ist,
    entscheidet der Parameter *Art* — nicht der Baustein.

    Gefunden beim Nachbau einer Sechskantverbindung: die Passbohrung rechnete
    ihr Spiel dazu, gab ein ``bore``-Merkmal zurück und setzte **+411,7 mm³**
    auf, also einen etwas dickeren Zapfen als der Zapfen. Beim
    Schnappverbinder war die „Tasche mit der Rastkante" +108,5 mm³, obwohl ihr
    Docstring seit je sagt: „was hier fehlt, bleibt im Bauteil stehen".
    """
    top = {"x": 0.0, "y": 0.0, "z": 8.0}

    before, gebohrt = _plate_and(name, {**params, **top, "kind": "bore"}, profile)
    _, gestiftet = _plate_and(name, {**params, **top, "kind": "pin"}, profile)

    assert gebohrt.mesh.volume < before.mesh.volume, "eine Bohrung nimmt weg"
    assert gestiftet.mesh.volume > before.mesh.volume, "ein Stift setzt auf"
    assert gebohrt.mesh.is_watertight and gestiftet.mesh.is_watertight
    assert gebohrt.mesh.component_count == 1, "die Bohrung zerlegt den Körper nicht"


def test_the_direction_is_declared_at_the_parameter() -> None:
    """§24: die Angabe steht dort, wo die Wahl getroffen wird — wie
    ``depends_on``.

    Drei Stellen lesen sie, und ohne eine Quelle hätte jede ihre eigene
    Version: die Operation (welche Boolesche Op), der Registereintrag (ob ein
    Flächenklick den Baustein anbietet) und die Vorschau (welche Farbe).
    """
    for name in ("dowel", "snap_connector"):
        spec = PARTS.get(name)
        assert part_ops.cuts_by_parameter(spec.params) == ("kind", ("bore",)), name
        assert part_ops.cuts(spec, spec.params(kind="bore")) is True, name
        assert part_ops.cuts(spec, spec.params(kind="pin")) is False, name
        # Ohne Werte gilt „kann abtragen": ``applies_to`` ist eine Reihenfolge
        # und keine Sperre, und beide Hälften werden auf eine Fläche gesetzt.
        assert part_ops.cuts(spec, None) is True, name
        assert "face" in REGISTRY.get(part_ops.op_name(name)).applies_to, name


def test_a_part_without_the_declaration_keeps_its_own_direction() -> None:
    """Die Gegenprobe — sonst hätte der neue Weg den alten überschrieben."""
    for name, subtractive in (("magnet_pocket", True), ("rib", False), ("heatset_m4", True)):
        spec = PARTS.get(name)
        assert part_ops.cuts_by_parameter(spec.params) is None, name
        assert part_ops.cuts(spec, spec.params()) is subtractive, name


def test_a_changed_bore_is_announced_to_old_projects() -> None:
    """§24.4: ein Baustein, dessen Maße sich ändern, wird beim Öffnen gemeldet.

    Hier ändert sich mehr als ein Maß — aus einem Buckel wird ein Loch. Wer die
    Bohrung bisher benutzt hat, muss das erfahren.

    Der Schnapper steht auf 4, weil Version 3 nur halb stimmte: Sie schob die
    Tasche unter ihre Mündung und nahm die Rastkante mit ans falsche Ende.
    """
    for name in ("dowel", "snap_connector"):
        spec = PARTS.get(name)
        letzte = spec.changes[-1]
        assert spec.version == letzte.version, name
        assert letzte.effect, name

    # **Und die Zusicherung, die keine feste Zahl braucht.** Vorher standen
    # hier zwei — „dowel" auf 2, „snap_connector" auf 4 —, und beide waren
    # der Stand vom Tag des Schreibens. Der erste Eintrag, der alle achtzehn
    # Bausteine zugleich betraf, machte sie falsch, obwohl an der Sache nichts
    # falsch war. Was gilt, ist die Übereinstimmung, nicht die Ziffer.
    for spec in PARTS.all():
        assert spec.changes, spec.name
        assert spec.version == spec.changes[-1].version, spec.name
        assert spec.changes[-1].effect or spec.changes[-1].version == "1", spec.name
        assert changed_since({name: "1"}) == (name,) or name in changed_since({name: "1"})


def test_an_additive_part_adds_material(profile: Profile) -> None:
    project = project_with_plate()
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]

    History(project.document).apply(
        "Rippe",
        [
            OperationDraft(
                op="insert_rib",
                inputs=("obj_1",),
                params={"length": 20.0, "height": 6.0, "wall": 3.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=sources)

    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume > before.mesh.volume


def test_the_features_of_a_part_reach_the_scene(profile: Profile) -> None:
    """§24.1, §21.1: eine Bohrung aus der Bibliothek ist von Anfang an
    benannt.
    """
    project = project_with_plate()
    History(project.document).apply(
        "Magnet",
        [
            OperationDraft(
                op="insert_magnet_pocket",
                inputs=("obj_1",),
                params={"size": "8x3", "x": 10.0, "y": 0.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    features = result.scene.objects["obj_1"].features
    assert "magnet_pocket_pocket_1" in features
    pocket = features["magnet_pocket_pocket_1"]
    assert pocket.provenance == "generated"
    assert pocket.params["centre"][0] == pytest.approx(10.0, abs=0.01)


def test_the_play_comes_from_the_material_profile(profile: Profile) -> None:
    """AGENTS.md Regel 7: nie eine feste Zahl in der Datei."""
    project = project_with_plate()
    History(project.document).apply(
        "Passbohrung",
        [
            OperationDraft(
                op="insert_dowel",
                inputs=("obj_1",),
                params={"kind": "bore", "diameter": 4.0, "length": 6.0, "z": 4.0, "play": 0.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    bore = result.scene.objects["obj_1"].features["dowel_bore_1"]
    assert bore.params["diameter"] == pytest.approx(4.0 + profile.material.clearance, abs=0.01)


@pytest.mark.parametrize(
    "name",
    [part_ops.op_name(spec.name) for spec in PARTS.all()],
    ids=lambda name: str(name),
)
def test_every_part_operation_runs_on_a_body(name: str, profile: Profile) -> None:
    """Ein Lauf je Operation — eine Deklaration, die nie jemand aufgerufen
    hat, ist nicht fertig.
    """
    project = project_with_plate()
    History(project.document).apply(
        name, [OperationDraft(op=name, inputs=("obj_1",), params={"z": 4.0})]
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    assert result.scene.objects["obj_1"].mesh.volume > 0.0


def test_a_part_that_misses_the_body_says_so(profile: Profile) -> None:
    """Der Fall, der einen Satz Deckel gekostet hat (Regel 17, §2.7).

    Eine Magnettasche neben dem Körper schnitt nichts und meldete nichts: keine
    Ausnahme, kein Befund, kein Hinweis. Im Verlauf stand ein Schritt, im
    Viewport lag dasselbe Teil, und gesucht wurde der Fehler in der Geometrie
    statt in der Position. Gemessen wurde es an einer Platte 60 × 60 × 20:
    0,0 mm³ abgetragen, null Befunde.
    """
    project = project_with_plate()
    History(project.document).apply(
        "Daneben",
        [
            OperationDraft(
                op="insert_magnet_pocket",
                inputs=("obj_1",),
                params={"size": "6x3", "x": 200.0, "y": 0.0, "z": 4.0},
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, "die Operation ist gelaufen — sie hat nur nichts bewirkt"
    codes = {finding.code for finding in result.scene.report.findings}
    assert "boolean.without_effect" in codes


def test_a_part_that_hits_the_body_stays_quiet(profile: Profile) -> None:
    """Und der Normalfall meldet nichts — sonst stünde die Warnung unter jedem
    Baustein und wäre nach dem dritten Mal unsichtbar.

    Die Tasche sitzt auf z = 0, der Mitte der Platte. Auf ihrer Oberkante
    (z = 4) träfe sie nichts, und das ist kein Zufall dieses Tests, sondern ein
    eigener Fund: die Magnettasche und das Schlüsselloch werden **über** ihrem
    Anker gebaut, das Schraubenloch darunter. Wer eine Fläche anklickt, trifft
    also je nach Baustein oder nicht — das gehört zusammengeführt und steht
    unter A2 im Konzept.
    """
    project = project_with_plate()
    History(project.document).apply(
        "Getroffen",
        [
            OperationDraft(
                op="insert_magnet_pocket",
                inputs=("obj_1",),
                params={"size": "6x3", "x": 0.0, "y": 0.0, "z": 0.0},
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    codes = {finding.code for finding in result.scene.report.findings}
    assert "boolean.without_effect" not in codes


# --- versioning (§24.4) -------------------------------------------------------------


def test_the_library_has_a_version() -> None:
    assert LIBRARY_VERSION


def test_a_changed_part_is_named(profile: Profile) -> None:
    used = {"screw_hole": "0", "rib": PARTS.get("rib").version}

    assert changed_since(used) == ("screw_hole",)


def test_a_part_that_is_gone_is_named() -> None:
    """§24.5: ein eigener Baustein von einer anderen Maschine fehlt, er wird
    nicht still übersprungen.
    """
    assert missing_parts({"eigenbau": "1", "rib": "1"}) == ("eigenbau",)


def test_the_change_log_says_what_moved() -> None:
    for spec in PARTS.all():
        for change in spec.changes:
            assert change.date and change.reason


@pytest.mark.parametrize("pair", by_direction(subtractive=False), ids=direction_ids)
def test_an_added_part_grows_together_with_the_body(
    pair: tuple[PartSpec, BaseParams], profile: Profile
) -> None:
    """Ein aufgesetzter Baustein muss **ein** Körper mit seinem Träger werden.

    Die Rastnase wurde es nicht: sie sitzt mit 6 × 1 mm auf der Fläche auf, und
    zwei Volumen, die sich nur in einer Fläche berühren, sind das eine, woran
    eine boolesche Operation zuverlässig scheitert (§39). Heraus kam ein
    wasserdichtes Netz aus zwei Komponenten — beim nächsten Bohren waren es
    drei. Die breiteren Bausteine fielen nie auf, weil manifold sie verschmolz.

    **Aus dem Register statt aus einer Liste**, seit dem 25.08.2026. Hier
    standen fünf Namen von Hand, und die letzten beiden Bausteine — Kabelclip
    und Lochwand-Einhänger — waren nicht darunter; niemand hatte es vergessen,
    es fällt nur schlicht nicht auf. Eine Liste, die man beim Anlegen eines
    Bausteins mitpflegen muss, ist beim übernächsten unvollständig.

    Und seit demselben Tag **je Richtung**: Wer die Liste aus
    ``not cuts(spec, None)`` zog, ließ die drei umschaltbaren Bausteine
    draußen, weil sie ohne Werte als abtragend zählen (siehe
    :func:`by_direction`).
    """
    spec, values = pair
    name = part_ops.op_name(spec.name)
    choice = part_ops.cuts_by_parameter(spec.params)
    params: dict[str, Any] = {"at_feature": "face_top"}
    if choice is not None:
        params[choice[0]] = getattr(values, choice[0])

    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    History(project.document).apply(
        name, [OperationDraft(op=name, inputs=("obj_1",), params=params)]
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    body = result.scene.objects["obj_1"].mesh
    assert body.component_count == 1, direction_ids(pair)
    assert body.is_watertight, direction_ids(pair)


def test_the_part_keeps_the_size_it_promises(profile: Profile) -> None:
    """Eingesenkt wird um den Überlappungswert, nicht um einen Millimeter.

    Die Nase steht 3 mm hoch über der Fläche; was im Körper verschwindet, ist
    ein Hundertstel und liegt unter dem, was die Anzeige unterscheidet.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    History(project.document).apply(
        "Nase",
        [
            OperationDraft(
                op="insert_latch",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "height": 3.0},
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    top = result.scene.objects["obj_1"].mesh.bounds.maximum[2]
    assert top == pytest.approx(13.0, abs=0.02), "10 mm Quader plus 3 mm Nase"


def test_a_part_on_a_side_wall_grows_into_that_wall(profile: Profile) -> None:
    """Die angeklickte Fläche bestimmt die Richtung, nicht nur den Ort.

    ``_anchor`` las von einem Merkmal ausschließlich ``centre``. Die Richtung
    kam aus dem Feld *Achse*, und dessen Vorgabe ist Z — also stand jeder
    Baustein senkrecht, gleich welche Fläche man angeklickt hatte. Für den
    Kunden war das der häufigste Handgriff überhaupt: Man zeigt auf eine Wand,
    und was man bekommt, steckt in der Decke.

    **Gemessen wird über zwei Höhen, und das ist keine Umständlichkeit.** Bei
    3 mm Höhe stimmt die Zahl auch im falschen Zustand: Die Nase ist 6 mm
    breit, eine senkrecht stehende reicht also 3 mm nach -X — dieselbe Zahl,
    aus der Breite statt aus der Höhe. Ein Test, der nur diesen einen Wert
    prüft, ist grün und beweist nichts. Erst wenn der Ausschlag mit der Höhe
    **mitwächst**, misst er die Richtung.
    """
    for height, expected in ((3.0, -23.0), (8.0, -28.0)):
        project = new_project("centauri-carbon-2", "petg")
        History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
        History(project.document).apply(
            "Nase",
            [
                OperationDraft(
                    op="insert_latch",
                    inputs=("obj_1",),
                    # face_5 schaut nach -X; der Quader steht dort bei x = -20.
                    params={"at_feature": "face_5", "height": height},
                )
            ],
        )

        result = evaluate(project.document, profile, sources=ProjectSources(project))

        assert result.complete, [f.message for f in result.scene.report.findings]
        bounds = result.scene.objects["obj_1"].mesh.bounds
        assert bounds.minimum[0] == pytest.approx(expected, abs=0.02), f"height {height}"
        assert bounds.maximum[2] == pytest.approx(10.0, abs=0.02), "und nichts nach oben"


def test_a_bore_in_a_side_wall_runs_through_that_wall(profile: Profile) -> None:
    """Dasselbe an dem Baustein, für den es am meisten zählt.

    Ein Schraubenloch bringt seine Bohrung als benanntes Merkmal mit, und
    deren Achse ist die Zahl, an der sich „durch die Wand" von „durch den
    Deckel" unterscheiden lässt. Der Betrag des Skalarprodukts mit der
    Flächennormalen ist 1, wenn beide dieselbe Gerade meinen — die Richtung
    entlang dieser Geraden ist Sache der Bohrung, nicht des Tests.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    wall = before.scene.objects["obj_1"].features["face_5"]
    History(project.document).apply(
        "Loch",
        [
            OperationDraft(
                op="insert_screw_hole", inputs=("obj_1",), params={"at_feature": "face_5"}
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    normal = np.asarray(wall.params["normal"], dtype=float)
    bores = [
        np.asarray(entry.params["axis"], dtype=float)
        for entry in result.scene.objects["obj_1"].features.values()
        if entry.kind == "hole" and entry.params.get("axis") is not None
    ]
    assert bores, "the part brings a named bore"
    assert all(abs(float(axis @ normal)) == pytest.approx(1.0, abs=1e-3) for axis in bores), (
        f"bore axes {bores} against wall normal {normal}"
    )


def test_every_play_field_defaults_to_the_profile() -> None:
    """Regel 7: `_part_values` füllt das Spiel nur bei **null** aus dem
    Materialprofil — jede andere Vorgabe ist eine feste Zahl, die die
    Kalibrierung (§28.3) nie erreicht. `nut_trap` (0,2) und `printed_thread`
    (0,15) waren genau das: ein TPU-Projekt baute die Mutternfalle mit
    PLA-Spiel."""
    from app.core.knowledge.parts import PARTS

    checked = 0
    for spec in PARTS.all():
        play = next((entry for entry in spec.params.fields() if entry.name == "play"), None)
        if play is None:
            continue
        checked += 1
        assert play.default == 0.0, (
            f"{spec.name}: Vorgabe {play.default} statt Verweis ins Materialprofil"
        )
    assert checked >= 7, "die Prüfung muss die Bausteine mit Spiel wirklich sehen"


@pytest.mark.parametrize("size", list(standards.profile_sizes()))
@pytest.mark.parametrize("play", [0.0, 0.15, 0.3, 1.0])
def test_the_tongue_leaves_air_in_the_slot_it_is_made_for(size: str, play: float) -> None:
    """Eine Passung wird an der **Differenz** gemessen, nicht daran, dass beide
    Hälften für sich stimmen.

    Geprüft wird gegen die Nut, wie die Tabelle sie beschreibt: in der Breite
    gegen den Kerndurchmesser, in der Tiefe gegen Steg plus Kammer. In beiden
    Richtungen muss genau das Spiel übrig bleiben.

    Die Tiefe ist der Fall, an dem es schiefging: Der Hals rechnete
    ``lip + play`` und der Kopf ``depth - play``, und damit kürzte sich das
    Spiel weg — die Feder war exakt so hoch wie die Nut tief und stieß mit null
    Luft auf dem Nutgrund auf. Ein gedruckter Kopf klemmt so, bevor er am Steg
    trägt, und gerade das soll er.
    """
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("profile_tongue")
    entry = standards.profile_slot(size)

    body = spec.fn(spec.params(size=size, play=play, length=20.0)).mesh
    width, _, height = (float(value) for value in body.bounds.size)

    assert entry.core - width == pytest.approx(play, abs=1e-6), (
        f"{size}: Kopf {width:.2f} in einer Kammer von {entry.core:.2f} — "
        f"{entry.core - width:.2f} Luft statt {play:.2f}"
    )
    assert entry.lip + entry.depth - height == pytest.approx(play, abs=1e-6), (
        f"{size}: Feder {height:.2f} hoch in einer Nut von "
        f"{entry.lip + entry.depth:.2f} — {entry.lip + entry.depth - height:.2f} "
        f"Luft über dem Nutgrund statt {play:.2f}"
    )


@pytest.mark.parametrize("size", list(standards.profile_sizes()))
def test_the_tongue_reaches_behind_the_lip(size: str) -> None:
    """Der Kopf muss hinter dem Steg sitzen, sonst hält die Feder nichts.

    Gemessen am Querschnitt und nicht am Hüllquader: In Steghöhe darf die Feder
    nur den Hals breit sein, darunter den Kopf. Ein Riegel, der über die ganze
    Höhe Kopfbreite hat, hätte denselben Hüllquader und ließe sich nicht
    einschieben.
    """
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("profile_tongue")
    entry = standards.profile_slot(size)
    body = spec.fn(spec.params(size=size, play=0.15, length=20.0)).mesh

    # Ein dünner Schnitt mitten durch den Steg und einer mitten durch die Kammer
    plate = shapes.box(60.0, 60.0, 0.2)
    through_lip = boolean("intersection", [body, shapes.moved(plate, (0.0, 0.0, entry.lip / 2.0))])
    in_chamber = boolean(
        "intersection",
        [body, shapes.moved(plate, (0.0, 0.0, entry.lip + entry.depth / 2.0))],
    )

    neck = float(through_lip.mesh.bounds.size[0])
    head = float(in_chamber.mesh.bounds.size[0])

    assert neck == pytest.approx(entry.slot - 0.15, abs=0.01), (
        f"{size}: im Steg {neck:.2f} breit, die Öffnung ist {entry.slot:.2f}"
    )
    assert head > neck + 1.0, (
        f"{size}: der Kopf ({head:.2f}) ist nicht breiter als der Hals ({neck:.2f}) — "
        "die Feder greift nicht hinter den Steg"
    )


def test_the_tongue_takes_every_dimension_from_the_table() -> None:
    """§24.2, und die Regel dahinter: Normteilmaße stehen nie im Baustein.

    Gemessen, indem die Tabelle verstellt wird — vier Maße, vier Wirkungen.
    Eine Zahl, die der Baustein selbst mitbringt, fällt hier auf, weil sie sich
    nicht mitbewegt.
    """
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("profile_tongue")
    before = spec.fn(spec.params(size="2020", play=0.0, length=20.0)).mesh.bounds.size
    entry = standards.profile_slot("2020")
    wider = dataclasses.replace(entry, slot=entry.slot + 1.0, core=entry.core + 2.0)
    deeper = dataclasses.replace(entry, lip=entry.lip + 1.0, depth=entry.depth + 3.0)

    with mock.patch.object(standards, "profile_slot", return_value=wider):
        grown = spec.fn(spec.params(size="2020", play=0.0, length=20.0)).mesh.bounds.size
    with mock.patch.object(standards, "profile_slot", return_value=deeper):
        taller = spec.fn(spec.params(size="2020", play=0.0, length=20.0)).mesh.bounds.size

    assert float(grown[0]) - float(before[0]) == pytest.approx(2.0, abs=1e-6), "core wirkt nicht"
    assert float(taller[2]) - float(before[2]) == pytest.approx(4.0, abs=1e-6), (
        "lip oder depth wirkt nicht"
    )


def test_the_lead_in_narrows_the_ends_and_leaves_a_middle_that_bears() -> None:
    """Die Einführschräge nimmt Material an den Enden, nicht die ganze Feder.

    Gekappt auf ein Drittel der Länge, und das ist eine Entscheidung über die
    Konstruktion und nicht eine über die Robustheit: Ein Kopf ohne
    volle-Breite-Mitte greift kaum noch hinter den Steg. Gemessen wird deshalb
    am Querschnitt in der Mitte, nicht am Volumen — das fiele auch, wenn die
    Schräge die Mitte auffräße.
    """
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("profile_tongue")
    entry = standards.profile_slot("2020")

    straight = spec.fn(spec.params(size="2020", lead_in=0.0, length=20.0)).mesh
    tapered = spec.fn(spec.params(size="2020", lead_in=4.0, length=20.0)).mesh

    assert tapered.volume < straight.volume, "die Schräge nimmt nichts weg"
    assert tapered.bounds.size[1] == pytest.approx(20.0, abs=1e-6), "die Länge hat sich geändert"

    # Die kürzeste Feder mit der größten Schräge — dort greift die Kappung
    plate = shapes.box(60.0, 0.2, 60.0)
    extreme = spec.fn(spec.params(size="2020", lead_in=6.0, length=6.0, play=0.0)).mesh
    middle = boolean("intersection", [extreme, plate])

    assert float(middle.mesh.bounds.size[0]) == pytest.approx(entry.core, abs=0.01), (
        f"in der Mitte nur {float(middle.mesh.bounds.size[0]):.2f} statt {entry.core:.2f} breit — "
        "die Schräge hat den tragenden Teil aufgefressen"
    )


@pytest.mark.parametrize("length", [6.0, 6.6, 12.0])
def test_a_tapered_bar_holds_at_every_taper_not_just_at_the_corners(length: float) -> None:
    """Die entartete Fläche liegt **mitten** im Bereich, nicht an seinem Ende.

    Genau auf ``taper == length / 2`` fällt die Schulter auf null, und damit
    fallen an jedem Ende zwei Ecken des Umrisses aufeinander. Vor der Abfrage in
    ``shapes.tapered_bar`` kam dort ein Körper aus fünf Teilen heraus, der nicht
    wasserdicht war — bei Schräge 2, 4 und 6 derselben Länge ging es gut.

    Deshalb fährt dieser Test in Zehntelschritten und nicht über Ecken: Der
    Bereichstest aus §24.3 nimmt Minimum, Maximum und Vorgabe jedes Parameters,
    und diese Stelle ist keines der drei. Ein Eckenraster hätte sie nie
    gefunden, und gefunden hat sie erst die Gegenprobe.
    """
    for step in range(int(length * 10) + 1):
        taper = step / 10.0
        body = shapes.tapered_bar(10.6, 6.0, length, 4.3, taper)

        assert body.is_watertight, f"Länge {length}, Schräge {taper} ist nicht wasserdicht"
        assert body.component_count == 1, (
            f"Länge {length}, Schräge {taper} fällt in {body.component_count} Teile"
        )
        assert body.volume > 0.0, f"Länge {length}, Schräge {taper} hat kein Volumen"


def test_insert_profile_tongue_grows_a_tongue_on_a_real_body(profile: Profile) -> None:
    """Der Weg des Nutzers: nicht die Bausteinfunktion, sondern die Operation.

    Zwischen beiden liegt einiges — ``_part_values`` füllt das Spiel aus dem
    Materialprofil, ``_anchor`` setzt die Feder an ein Merkmal, und die
    Vereinigung mit dem Körper läuft über die Boolesche Rückfallkette. Ein
    Baustein, der für sich rechnet und im Fenster nichts tut, ist die Sorte
    Fehler, die drei Bausteine schon einmal hatten (§24.1, MOUTH_AT_ORIGIN).
    """
    project = project_with_plate()
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]

    History(project.document).apply(
        "Nutfeder",
        [
            OperationDraft(
                op="insert_profile_tongue",
                inputs=("obj_1",),
                params={"size": "2020", "length": 20.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=sources)
    after = result.scene.objects["obj_1"]

    assert result.complete, "die Auswertung hält an: " + " | ".join(
        f"{f.code}: {f.message}" for f in result.scene.report.findings
    )
    assert "boolean.without_effect" not in {f.code for f in result.scene.report.findings}, (
        "die Feder sitzt neben der Platte statt auf ihr"
    )
    assert after.mesh.volume > before.mesh.volume, "die Feder hat nichts angebaut"
    assert after.mesh.is_watertight, "der Körper ist danach nicht mehr geschlossen"

    grown = float(after.mesh.bounds.maximum[2] - before.mesh.bounds.maximum[2])
    entry = standards.profile_slot("2020")
    # Steg plus Kammer, abzüglich des Spiels aus dem Materialprofil — dieselbe
    # Rechnung wie im Baustein, hier aber über die Operation gemessen.
    expected = entry.lip + entry.depth - profile.material.clearance
    assert grown == pytest.approx(expected, abs=0.05), (
        f"die Feder steht {grown:.2f} mm über der Platte, erwartet {expected:.2f}"
    )


def test_a_part_can_carry_a_caveat() -> None:
    """Ein Baustein darf sagen, wann er die falsche Wahl ist (§25.4).

    **Bis zum 23.08.2026 konnte er das nicht**, und deshalb trug keiner der
    zwanzig einen ``caveat`` — nicht aus Nachlässigkeit, sondern weil
    ``register_part`` das Feld nicht kannte. Zwölf Operationen außerhalb der
    Bibliothek hatten längst einen; die Bausteine fielen durch eine Lücke in der
    Schnittstelle, und die sah man nur, wenn man einen setzen wollte.

    Geprüft wird die ganze Kette, nicht das Feld: ``register_part`` nimmt ihn,
    ``PartSpec`` hält ihn, und ``_register_one`` reicht ihn an die Operation
    weiter — dort liest ihn die Oberfläche. Ein Test auf ``PartSpec.caveat``
    allein wäre grün geblieben, während die Weitergabe fehlt.
    """
    from app.core.bootstrap import load_operations
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    load_operations()
    tragen = [spec for spec in PARTS.all() if spec.caveat]
    assert tragen, "kein Baustein trägt einen caveat — dann prüft dieser Test nichts"

    for spec in tragen:
        eintrag = next(
            (op for op in REGISTRY.all() if op.category == "parts" and spec.name in op.name),
            None,
        )
        assert eintrag is not None, f"{spec.name} steht nicht als Operation im Register"
        assert str(eintrag.caveat) == str(spec.caveat), (
            f"{spec.name}: der caveat kommt am Register nicht an — "
            "_register_one reicht ihn nicht weiter"
        )


def test_parts_that_need_a_bore_are_offered_at_one() -> None:
    """Wer eine Bohrung anklickt, bekommt die drei angeboten, die hineingehören.

    Vor dem 23.08.2026 speiste nur ``subtractive`` das Kontextmenü, und zwar
    ausschließlich an Flächen: An einer Bohrung standen vier Einträge, das
    Gewinde stand nirgends. Der Unterschied zwischen „bringt sein Loch mit" und
    „braucht eines" war nicht ausgedrückt.
    """
    from app.core.bootstrap import load_operations

    load_operations()

    an_bohrung = {spec.name for spec in REGISTRY.for_feature("hole")}
    for name in ("printed_thread", "nut_trap", "heatset_m4"):
        spec = PARTS.get(name)
        assert spec.at_hole, f"{name} gehört in eine Bohrung und sagt es nicht"
        assert part_ops.op_name(name) in an_bohrung, (
            f"{name} ist als at_hole markiert, steht aber nicht im Kontextmenü "
            "einer Bohrung — _applies_to reicht es nicht weiter"
        )

    for spec in PARTS.all():
        if spec.at_hole:
            continue
        assert part_ops.op_name(spec.name) not in an_bohrung, (
            f"{spec.name} steht an einer Bohrung, ohne dafür gedacht zu sein: "
            "wirken ist nicht dasselbe wie sinnvoll sein"
        )


def test_every_group_has_a_title_and_every_title_a_tile() -> None:
    """Die Anschlussprüfung, die beim Umbau der Bohrungs-Bausteine fehlte.

    **Zwei Richtungen, und beide waren am 24.08.2026 ungeprüft.** Der Katalog
    zeichnet seine Kacheln nach ``spec.group`` und beschriftet die Abschnitte
    aus ``GROUPS``. Wer eine Gruppe verschiebt, muss beides anfassen — und
    keine Zusicherung hielt die zwei zusammen:

    * **Eine Gruppe ohne Titel** liest der Kunde als englischen Schlüssel.
      ``GROUPS.get(gruppe, gruppe)`` fällt auf den Schlüssel zurück, und dann
      steht „inserts" über den Kacheln statt „Einlegeteile" — eine feste
      Zeichenkette in der Oberfläche, die nie durch ``tr()`` gelaufen ist
      (Regel 20).
    * **Ein Titel ohne Kachel** ist ein leerer Abschnitt. Genau das entsteht,
      wenn ein Baustein die Gruppe wechselt und ihr Titel stehen bleibt — und
      es fällt nur auf, wenn jemand den Katalog aufmacht.

    Der Anlass: `heatset_m4` stand allein in `inserts`, und beim Auflösen
    dieser Gruppe wanderten Baustein **und** Titel — zwei Änderungen in zwei
    Dateien, deren Zusammenhang niemand geprüft hätte. Beim nächsten Mal prüft
    ihn dieser Test.

    Nicht geprüft wird, wie **viele** Kacheln eine Gruppe braucht: Ob eine
    Einzelgruppe zusammengelegt wird, ist eine Entscheidung über die Oberfläche
    und keine über die Konsistenz — sie gehört nicht in einen Test.
    """
    from app.core.knowledge.parts import GROUPS

    benutzt = {spec.group for spec in PARTS.all()}
    assert benutzt, "ohne Bausteine prüft dieser Test nichts"
    assert GROUPS, "und ohne Gruppentitel auch nicht"

    ohne_titel = sorted(benutzt - set(GROUPS))
    assert not ohne_titel, (
        f"Gruppen ohne Titel in GROUPS: {ohne_titel} — der Katalog zeigt dann den Schlüssel"
    )

    ohne_kachel = sorted(set(GROUPS) - benutzt)
    assert not ohne_kachel, (
        f"Gruppentitel ohne einen einzigen Baustein: {ohne_kachel} — ein leerer Abschnitt"
    )


# --- Der Kabelclip (insert_cable_clip) ------------------------------------------


@pytest.mark.parametrize("size", ["cable-5", "cable-7", "ptfe-4x2", "ptfe-6x3"])
def test_the_clip_lets_the_cable_lie_but_not_drop_in(size: str) -> None:
    """Die Zusage des Clips ist ein Widerspruch, und beide Hälften sind messbar:
    Das Kabel **liegt im Bügel**, und es **kommt nicht senkrecht hinein**.

    Genau daran hängt, ob ein Clip hält. Ist die Öffnung so weit wie das Kabel,
    fällt es wieder heraus; ist der Innenraum zu eng, drückt der Bügel es platt.

    Gefragt wird über die Boolesche Operation, und ihre **Ausnahme ist die
    Antwort**: Eine leere Schnittmenge meldet ``boolean`` als
    ``BooleanFailedError`` („Es bleibt kein Körper übrig"), und das ist hier
    genau das gesuchte Ergebnis.

    **Warum die Probe neunzig Prozent misst und nicht hundert.** Der Sitz ist
    so groß wie das Kabel, also berühren sich beide in einer Fläche — und
    darauf ist keine Boolesche Operation zu bauen (§39). Gemessen, wie weit die
    Zahl davon abhängt: Bei 98 % kamen für vier Größen 8,6 · 10,4 · 9,3 ·
    9,4 mm³ heraus, **absolut konstant statt proportional**, und die Kette
    meldete dabei „jittered". Das ist kein Eindringen, das ist das Werkzeug,
    das sich selbst misst. Bei neunzig Prozent ist die Antwort eindeutig, und
    die Zusage — der Sitz ist für das Kabel gebaut — prüft sie immer noch.
    """
    from app.core.errors import BooleanFailedError
    from app.core.geom.boolean import boolean
    from app.core.geom.mesh import MeshData
    from app.core.knowledge import standards
    from app.core.knowledge.parts import PARTS, shapes

    spec = PARTS.get("cable_clip")
    values = spec.params(size=size)
    built = spec.fn(values)
    entry = standards.tube(size)

    # Wo das Kabel liegt, sagt der Baustein selbst: ``seat_1`` ist die Auflage,
    # und das Kabel liegt mit seinem Radius darüber. Nicht aus der Formel des
    # Bausteins gerechnet — die prüft sich sonst selbst.
    axis = built.features["seat_1"].params["centre"][2] + entry.outer / 2.0

    def cable(height: float, share: float) -> MeshData:
        upright = shapes.cylinder(entry.outer * share, values.width * 4.0)
        centred = shapes.moved(upright, (0.0, 0.0, -values.width * 2.0))
        lying = shapes.turned(centred, 90.0, (1.0, 0.0, 0.0))
        return shapes.moved(lying, (0.0, 0.0, height))

    with pytest.raises(BooleanFailedError):
        boolean("intersection", [built.mesh, cable(axis, 0.90)])

    # Und der Weg von oben ist versperrt: ein Kabel, das über der Öffnung steht
    # und heruntergedrückt würde, trifft auf Material. Hier ist der Schnitt
    # groß und die Antwort eindeutig.
    blocked = boolean("intersection", [built.mesh, cable(axis + entry.outer, 1.0)]).mesh
    assert blocked.volume > 0.0, (
        f"{size}: the opening is as wide as the cable — nothing holds it in"
    )


def test_the_clip_keeps_its_grip_over_the_whole_range() -> None:
    """Die Verengung wird gekappt, nicht abgelehnt (§24.3, Bereichstest).

    Bei ``grip`` = 5 und einem 4-mm-Schlauch wäre die Öffnung rechnerisch minus
    sechs Millimeter breit. Der Baustein baut trotzdem — was herauskommt, ist
    ein geschlossener Ring, unbrauchbar und wasserdicht. Das ist die richtige
    Antwort auf eine Grenze, die das Feld selbst nennt: Ein Bereichstest, der an
    seiner eigenen Ecke in eine Ausnahme läuft, prüft nichts.
    """
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("cable_clip")
    for grip in (0.0, 2.5, 5.0):
        built = spec.fn(spec.params(size="ptfe-4x2", grip=grip))
        assert built.mesh.is_watertight, f"grip={grip} is not watertight"
        assert built.mesh.component_count == 1, f"grip={grip} falls apart"


def test_an_attachment_stands_in_the_face_menu_and_a_test_body_does_not() -> None:
    """``at_face`` wirkt bis ins Register — die Regression von sechs aus achtzehn.

    Am 24.08.2026 fehlten Wandhalter, Nutfeder, Rippe, Rastnase,
    Schnappverbindung und Filmscharnier in jedem Kontextmenü einer Fläche,
    weil die Fläche aus „trägt Material ab" geraten wurde. Der Fix (074e5d0)
    kam ohne Wache; wer die Ableitung anfasst, konnte die sechs wieder
    verlieren, ohne dass ein Lauf rot wird.

    Geprüft wird über das Register, nicht über die Menüs: ``applies_to`` ist
    die eine Quelle, aus der Kontextmenü und Palette lesen. Und die Gegenseite
    gehört dazu — ein Prüfkörper steht für sich, und an einer Fläche hätte er
    nichts verloren.
    """
    for spec in PARTS.all():
        expected = spec.at_face
        got = "face" in REGISTRY.get(part_ops.op_name(spec.name)).applies_to
        assert got == expected, (
            f"{spec.name}: at_face={expected}, aber das Register bietet die Fläche "
            f"{'nicht ' if expected else ''}an"
        )
    # Und die Erklärung ist keine leere Menge auf einer Seite: Es gibt beide.
    assert any(spec.at_face for spec in PARTS.all())
    assert any(not spec.at_face for spec in PARTS.all()), (
        "ohne einen Prüfkörper prüft die Gegenseite nichts"
    )


# --- Der Lochwand-Einhänger (insert_pegboard_hook) ------------------------------


@pytest.mark.parametrize("count", [1, 2, 4])
def test_the_hook_goes_through_the_slot_and_catches_behind_it(count: int) -> None:
    """Zwei Zusagen, und ein Einhänger, der eine davon bricht, hängt nicht.

    **Er muss hinein**: Zapfen und Nase zusammen sind der Weg durch den Schlitz,
    und der ist bei SKÅDIS fünfzehn Millimeter hoch und fünf breit. Passt der
    Haken nicht hindurch, liegt das Teil daneben statt zu hängen.

    **Und er muss hinter die Platte greifen**: Die Nase sitzt jenseits der
    Plattendicke, sonst rutscht das Teil beim ersten Anstoßen heraus.

    Gemessen wird an der Geometrie, die herauskommt, und an den benannten
    Merkmalen — **nicht an der Formel des Bausteins**. Dieser Docstring
    versprach das schon, während die Prüfung darunter
    ``slot_width + 2 * slot_width`` nachrechnete, also die Randformel der
    Rückplatte rückwärts. Als der Rand ein eigenes Maß bekam, wurde der Test
    rot, obwohl der Baustein besser geworden war — er hatte die Aktualität der
    Formel geprüft und nie ihre Richtigkeit
    (``.claude/memory/sollwert-aus-dem-pruefling.md``).
    """
    from app.core.knowledge import standards
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("pegboard_hook")
    values = spec.params(count=count)
    built = spec.fn(values)
    board = standards.board(values.system)

    kanten = built.mesh.bounds
    tief = float(kanten.size[2])

    # Der Haken ragt hinter die Rückplatte, und zwar über die Plattendicke
    # hinaus — sonst greift die Nase ins Leere.
    assert tief > values.plate + board.thickness, (
        f"count={count}: the hook is {tief:.1f} mm deep, which does not reach past "
        f"the {board.thickness} mm board behind the {values.plate} mm plate"
    )

    # Und die Haken sitzen im Raster: zwischen zwei benachbarten liegt genau
    # eine Rasterweite, sonst passen sie in keine zwei Schlitze. Die Merkmale
    # sagen, wo sie stehen — die Rückplatte darum herum ist eine andere Frage.
    zapfen = sorted(
        f.params["centre"][0] for name, f in built.features.items() if name.startswith("hook_")
    )
    assert len(zapfen) == count, f"count={count}: {len(zapfen)} hooks named"
    for links, rechts in itertools.pairwise(zapfen):
        assert rechts - links == pytest.approx(board.pitch, abs=0.01), (
            f"count={count}: neighbouring hooks sit {rechts - links:.2f} mm apart, "
            f"the grid says {board.pitch}"
        )

    # Die Rückplatte trägt jeden Zapfen, und zwar mit Rand ringsum: Ein Zapfen
    # an der Plattenkante hätte kein Material, das ihn hält.
    breit = float(kanten.size[0])
    assert breit > (zapfen[-1] - zapfen[0]) + board.slot_width, (
        f"count={count}: the plate is {breit:.1f} mm wide and does not reach around the outer hooks"
    )


def test_the_hook_fits_the_slot_it_is_made_for() -> None:
    """Was hinter der Rückplatte steckt, muss durch den Schlitz passen.

    Gemessen wird am gebauten Netz und gegen die Tabelle: Alle Punkte jenseits
    der Rückplatte gehören zu dem Teil, das in die Lochwand greift, und ihre
    Spanne in Breite und Höhe ist der Weg durch den Schlitz. Ist sie größer als
    das Loch, kommt der Haken nicht hinein — dann liegt das Teil daneben statt
    zu hängen.

    **Ohne Boolesche Operation, und das ist kein Umweg.** Der erste Versuch
    stellte eine Platte mit Schlitz daneben und fragte nach der Schnittmenge.
    Sie ist nie leer: Die Rückplatte des Hakens liegt an der Lochwand an, und
    zwar flächig — das ist keine Klemmung, sondern der Zweck. Wer hier eine
    Boolesche Operation befragt, misst die Berührung und nicht die Passung.
    """
    from app.core.knowledge import standards
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("pegboard_hook")
    values = spec.params(count=1, play=0.2)
    built = spec.fn(values)
    board = standards.board(values.system)

    punkte = built.mesh.raw.vertices
    dahinter = punkte[punkte[:, 2] > values.plate + 0.1]
    assert len(dahinter), "nothing reaches behind the plate at all"

    breit = float(dahinter[:, 0].max() - dahinter[:, 0].min())
    hoch = float(dahinter[:, 1].max() - dahinter[:, 1].min())

    assert breit <= board.slot_width, (
        f"the part behind the plate is {breit:.2f} mm wide, the slot is {board.slot_width}"
    )
    assert hoch <= board.slot_height, (
        f"the part behind the plate is {hoch:.2f} mm tall, the slot is {board.slot_height}"
    )
    # Und es soll den Schlitz auch ausnutzen: Ein Haken, der nur halb so hoch
    # ist wie das Loch, hält beim ersten Anstoßen nicht.
    assert hoch > board.slot_height / 2.0, (
        f"the hook only uses {hoch:.2f} mm of the {board.slot_height} mm slot"
    )
