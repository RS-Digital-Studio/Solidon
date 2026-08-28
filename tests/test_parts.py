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
from app.core.knowledge import profiles, standards
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
    """§24.1 nennt dreizehn Bausteine für die erste Auslieferung, dazu elf.

    Die Kalibrierkörper aus §28.3 sind auch Bausteine, gehören aber nicht zu
    diesem Satz — sie sind Werkzeuge für den Drucker, nicht für das Modell, und
    sie haben ihre eigene Gruppe im Katalog.

    **Elf stehen nicht in der Erstbestückung**, und alle elf sind eine Ansage
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

    ``hinge_eye`` kam am 25.08.2026 dazu. Das Filmscharnier **biegt**, dieses
    hier **dreht** — zwei Augen und ein Passstift ergeben ein Gelenk, das hält.

    ``barrel_hinge`` kam am 27.08.2026 dazu und ist das Scharnier, das das Auge
    damals nicht sein durfte: eines, das schon beim Drucken beweglich ist. Es
    besteht aus zwei Teilen, und bis dahin musste ein Baustein einer sein —
    nicht laut Bauplan, sondern laut Test. §24.3 trägt die Ausnahme seit dem
    25.08.2026 als **Deklaration** (Entscheidung Robert): Wer mehrere Körper
    baut, sagt wie viele, und dann prüft der Bereichstest die gebaute Zahl
    gegen die erklärte. Unerklärtes Zerfallen bleibt rot. Er ist der erste
    Nutzer von ``bodies`` und damit der Beleg, dass die Deklaration trägt.

    Die gedruckte Schraube und Mutter kamen am 28.08.2026 aus einer
    Supportmeldung hinzu. Sie benutzen dieselbe Normtabelle und dasselbe
    Materialspiel wie das druckbare Gewinde, damit ein Behältergewinde, sein
    Deckel und eine lösbare Schraubverbindung nicht drei unvereinbare Maße
    bekommen.

    ``bearing_seat`` kam am 28.08.2026 dazu. Lagermaße standen schon in der
    Normteiltabelle, waren aber im Katalog nicht benutzbar. Der Lagersitz macht
    daraus eine einfache Auswahl: Lagernummer wählen und entscheiden, ob das
    Lager wechselbar oder fest eingepresst sein soll.
    """
    building = [spec for spec in PARTS.all() if spec.group != "calibration"]

    assert len(building) == 24
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
        if not spec.joined_by_host:
            # Die **erklärte** Zahl, nicht die Eins (§24.3, Entscheidung Robert
            # vom 25.08.2026). Wer nichts deklariert, hat ``bodies=1`` und
            # damit genau die alte Prüfung; wer zwei erklärt, muss zwei bauen.
            # Unerklärtes Zerfallen bleibt rot — das ist der Unterschied
            # zwischen einer Deklaration und einer Ausnahme im Test.
            assert mesh.component_count == spec.bodies, (
                f"{spec.name} {values}: {mesh.component_count} Teile statt {spec.bodies}"
            )
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
        # **Ein Schalter hat keine ``choices`` und trotzdem zwei Stellungen.**
        # ``printed_thread`` entscheidet über ``internal: bool``, und die erste
        # Fassung dieser Funktion las nur ``entry.choices`` — für einen
        # bool-Parameter ist das ``None``, und der Baustein fiel damit erneut
        # durch beide Netze, obwohl die Funktion genau dagegen geschrieben war.
        values = entry.choices or ((False, True) if entry.kind == "bool" else ())
        for value in values:
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


def test_the_gusset_names_the_middle_of_its_face_and_not_its_edge() -> None:
    """``gusset_1`` ist eine Fläche, und eine Fläche hat eine Mitte.

    Der Keil steht mit seiner Unterseite auf der Wand: in x über die Dicke
    zentriert, in y von 0 bis zum Schenkel (``shapes.wedge``). Genannt wurde als
    Mitte ``(0, 0, 0)`` — das ist die Vorderkante dieser Fläche und nicht ihr
    Mittelpunkt. Wer daran ausrichtet, setzt einen halben Schenkel daneben, bei
    der Vorgabe also 6 mm; §24.1 macht ein Merkmal aber zur Zusage an den
    nächsten Schritt.

    Geprüft wird gegen die Geometrie und nicht gegen die Formel: Der genannte
    Punkt muss auf der Auflagefläche liegen, und zwar in ihrem Inneren. Die alte
    Angabe lag auf ihrem Rand — ein Unterschied, den kein Volumen und kein
    Hüllquader zeigt.
    """
    from shapely.geometry import Point

    from app.core.slice.analysis import cross_section

    spec = PARTS.get("gusset")
    legs = 12.0
    built = spec.fn(spec.params(legs=legs, thickness=3.0))
    centre = built.features["gusset_1"].params["centre"]
    normal = built.features["gusset_1"].params["normal"]

    assert normal == (0.0, 0.0, -1.0), "die Auflagefläche schaut nach unten"
    assert centre[2] == pytest.approx(0.0), "sie liegt auf z = 0"

    # Ein Haar über der Fläche, weil ein Schnitt genau auf ihr entartet.
    footprint = cross_section(built.mesh, 0.01)
    assert footprint is not None and not footprint.is_empty, "nothing to stand on"

    assert footprint.contains(Point(centre[0], centre[1])), (
        f"gusset_1 nennt {centre[:2]}, und dort ist die Fläche nicht — "
        f"ihr Umriss reicht von y={footprint.bounds[1]:.2f} bis y={footprint.bounds[3]:.2f}"
    )
    assert centre[1] == pytest.approx(legs / 2.0)


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

    **Gemessen wird das Loch, nicht das Merkmal.** Bis zum 26.08.2026 stand
    hier nur, was ``eye_1`` verspricht — ein Wert, den derselbe Baustein selbst
    hineinschreibt. Ein Subtraktionszylinder, der statt ``pin + play`` nur
    ``pin`` nimmt, hätte diese Prüfung bestanden und den Bolzen klemmen
    lassen: Das Merkmal wäre unverändert richtig geblieben. Quer zur Drehachse
    geschnitten zeigen sich zwei Konturen; der kleinere Zug ist die Bohrung,
    und ihre Weite ist die Antwort (dieselbe Art Messung wie beim Fuß, nur um
    die liegende Achse gedreht).
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

        across = built.mesh.raw.section(plane_origin=[0.0, 0.0, 0.0], plane_normal=[1.0, 0.0, 0.0])
        assert across is not None, f"pin={pin}: nothing crosses the eye at all"
        contours = [np.asarray(entry, dtype=float) for entry in across.discrete]
        assert len(contours) == 2, (
            f"pin={pin}: a cut across the axis shows {len(contours)} contours, "
            "so there is no ring to measure"
        )
        bore = min(contours, key=lambda entry: float(np.ptp(entry[:, 1])))
        assert float(np.ptp(bore[:, 1])) == pytest.approx(pin + values.play, abs=0.05), (
            f"pin={pin}: the hole measures {float(np.ptp(bore[:, 1])):.2f} mm, "
            f"a {pin} mm pin with {values.play} mm play needs {pin + values.play:.2f}"
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


def test_the_keyhole_slot_runs_the_way_the_part_falls() -> None:
    """Ein Schlüsselloch mit waagerechtem Schlitz hält nicht.

    Die Schraube muss sich beim Absinken im schmalen Teil **verklemmen**. Liegt
    der Schlitz quer, wandert sie darin seitlich hin und her und hält das Teil
    nur, solange niemand dagegenstößt.

    **Der Baustein lag drei Wochen lang quer, und sein Docstring sagte das
    Gegenteil**: „Der Schlitz läuft in -Y." Der Versatz in Y stand auch
    richtig da — nur baut ``shapes.slot`` seine Länge immer in **X**, und ein
    Verschieben ist kein Drehen. Gemessen an ``keyhole(drop=8)`` waren es
    15,58 mm in X gegen 7,60 in Y, und 15,58 ist ``head + 0,6 + drop``, also
    der Schlitz selbst.

    Geprüft wird die Länge gegen die Breite, nicht der Quelltext: Ein Docstring
    hat hier schon einmal etwas anderes behauptet als der Code darunter.
    """
    spec = PARTS.get("keyhole")
    for drop in (4.0, 8.0, 16.0):
        built = spec.fn(spec.params(drop=drop)).mesh
        along = float(built.bounds.size[1])
        across = float(built.bounds.size[0])
        assert along > across, (
            f"drop={drop}: the keyhole measures {across:.2f} mm across and {along:.2f} mm "
            "along the direction it falls — the slot lies crosswise"
        )
        # Und der Schlitz wächst mit ``drop``: Er *ist* der Weg der Schraube.
        assert along == pytest.approx(across + drop, abs=0.2), (
            f"drop={drop}: the slot is {along:.2f} mm long, expected about "
            f"{across + drop:.2f} — the drop does not end up in the slot"
        )


def test_the_keyhole_puts_the_screw_above_the_hole_it_went_through() -> None:
    """Wo die Schraube endet, entscheidet, ob das Teil hängt.

    Der Kopf geht durch das runde Ende, dann sinkt das Teil — und die Schraube
    steht danach **relativ höher**, weil sich das Teil an ihr vorbei nach unten
    bewegt hat. Sitzt es umgekehrt, fällt das Teil beim Loslassen herunter.

    Im eigenen System des Bausteins heißt „oben" **-Y**: die Konvention von
    ``axis="y"``, dem auch ``PartSpec.keeps_up`` folgt. Geprüft wird an den
    benannten Merkmalen, denn genau die liest, wer das Gegenstück ausrichtet.
    """
    spec = PARTS.get("keyhole")
    built = spec.fn(spec.params(drop=8.0))

    mouth = built.features["pocket_1"].params["centre"]
    seat = built.features["bore_1"].params["centre"]
    assert float(seat[1]) < float(mouth[1]) - 1.0, (
        f"the screw ends at y={float(seat[1]):.1f} and the head goes in at "
        f"y={float(mouth[1]):.1f} — the part would drop off when let go"
    )
    # Der Kopf braucht mehr Platz als der Schaft, sonst kommt er nicht hinein.
    assert (
        built.features["pocket_1"].params["diameter"]
        > (built.features["bore_1"].params["diameter"])
    ), "the head opening is no wider than the shaft slot"


@pytest.mark.parametrize("kind", ["keyhole", "pegboard_hook"])
def test_a_part_that_knows_up_hangs_the_right_way_on_every_wall(kind: str) -> None:
    """``keeps_up`` gilt beiden gleich — und beinahe hätte es sie gegeneinander
    ausgespielt.

    Die Aufrichtung entstand für den Lochwand-Einhänger, und der baute sein
    Oben nach **+Y**. So kam es in die Funktion. Das Schlüsselloch baut seit je
    nach -Y und hatte damit recht: ``axis="y"`` dreht das eigene +Y nach
    Welt-unten, seit es diesen Weg gibt. Für einen Nachmittag richtete die
    Bibliothek deshalb die Bauweise **eines** Bausteins zur Regel für alle auf,
    und das Schlüsselloch hing verkehrt herum — Schraubensitz unten,
    Kopfdurchlass oben.

    Dieser Test prüft beide über dieselbe Frage: Was oben liegen soll, muss
    nach dem Setzen an eine senkrechte Wand **oben** liegen.
    """
    spec = PARTS.get(kind)
    assert spec.keeps_up, f"{kind} does not declare that it knows up"

    profile = profiles.make_profile("centauri-carbon-2", "petg")

    for face in ("face_4", "face_6"):
        # Je Fläche ein frisches Projekt: Zwei Bausteine nacheinander in
        # denselben Körper wären ein anderer Test.
        project = new_project("centauri-carbon-2", "petg")
        History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
        History(project.document).apply(
            kind,
            [
                OperationDraft(
                    op=part_ops.op_name(kind), inputs=("obj_1",), params={"at_feature": face}
                )
            ],
        )
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        assert result.complete, (
            f"{kind} at {face}: {[f.message for f in result.scene.report.findings]}"
        )

        placed = result.scene.objects["obj_1"].features
        # Was im eigenen System bei -Y liegt, muss in der Welt oben liegen.
        own = spec.fn(spec.params())
        upper = min(own.features, key=lambda name: float(own.features[name].params["centre"][1]))
        lower = max(own.features, key=lambda name: float(own.features[name].params["centre"][1]))
        if upper == lower:
            continue
        top = next(f for name, f in placed.items() if name.endswith(upper))
        bottom = next(f for name, f in placed.items() if name.endswith(lower))
        assert float(top.params["centre"][2]) > float(bottom.params["centre"][2]), (
            f"{kind} at {face}: '{upper}' should sit above '{lower}' and sits below"
        )


def test_every_change_log_climbs() -> None:
    """Eine Version, die nicht steigt, warnt niemanden.

    ``PartSpec.version`` wird aus dem **letzten** Eintrag des Verlaufs gelesen,
    nicht aus dem höchsten — das ist richtig so, denn der letzte Eintrag ist
    der Stand. Es setzt aber voraus, dass die Einträge aufsteigen, und das
    prüfte nichts.

    **Zweimal an einem Tag ging es schief, beide Male beim Beheben von etwas
    anderem.** Die Rippe stand auf 4; ein neuer Eintrag mit „2" senkte sie auf
    2, und ``changed_since`` meldete einem Projekt mit Stand 4 nichts mehr —
    die Maßänderung an dünnen Wänden wäre still durchgerechnet worden. Das
    Schlüsselloch stand auf 4 und bekam einen Eintrag mit „4": gleicher Stand,
    also keine Meldung, obwohl sich die Richtung seines Schlitzes gedreht
    hatte. Beide Bausteine sahen dabei völlig gesund aus, ihre Verläufe waren
    vollständig, jeder Eintrag hatte Datum, Grund und Wirkung.

    Und beide Fehler entstanden aus derselben Bequemlichkeit: einen neuen
    Eintrag zu schreiben, ohne den vorletzten zu lesen.

    **Ein dritter kam dazu, den niemand geschrieben hatte.** Der
    Schnappverbinder stand auf 4 und bekam ``FACE_GIVES_DIRECTION`` angehängt —
    einen Eintrag, den sechs Bausteine teilen und der die Version 4 trägt. Für
    die fünf anderen war das ein Schritt nach oben, für ihn keiner. Ein
    geteilter Eintrag trägt **eine** Zahl, und die passt nur, wenn alle, die
    ihn führen, vom selben Stand kommen. Geprüft wird das hier nicht eigens:
    Wo es nicht passt, steigt die Kette nicht, und das steht schon in der
    Bedingung darüber.
    """
    for spec in PARTS.all():
        versions = [change.version for change in spec.changes]
        assert versions, spec.name
        numbers = [int(version) for version in versions]
        for older, newer in itertools.pairwise(numbers):
            assert newer > older, (
                f"{spec.name}: the change log goes {' -> '.join(versions)} — "
                f"version {newer} does not climb past {older}, so a project saved "
                f"at {older} is never told the part moved"
            )
        assert spec.version == versions[-1], (
            f"{spec.name}: reports version {spec.version} but its log ends at {versions[-1]}"
        )


def test_the_nut_trap_takes_the_nut_it_is_named_after() -> None:
    """Eine M5-Falle muss eine M5-Mutter aufnehmen — ganz, nicht fast.

    **Sie tat es nicht, und zwar bei der verbreitetsten Größe.** Die
    Mutternhöhen der Tabelle waren die der zurückgezogenen DIN 934, und die
    weicht von ISO 4032 in genau drei Größen ab: M5 stand auf 4,00 statt 4,70,
    M6 auf 5,00 statt 5,20, M8 auf 6,50 statt 6,80. Für M2 bis M4 sind beide
    Normen gleich — deshalb fiel es an keiner Stelle auf, an der jemand
    nachgemessen hätte.

    Geprüft wird gegen die Norm und nicht gegen die Tabelle: Wer die Erwartung
    aus derselben Quelle nimmt wie den Prüfling, prüft nur, ob sich etwas
    geändert hat (``.claude/memory/sollwert-aus-dem-pruefling.md``).
    """
    #: Höhe m max nach ISO 4032, abgeschrieben aus der Norm und nicht aus
    #: ``standards.toml`` — sonst prüfte sich die Tabelle selbst.
    iso_4032 = {"M2": 1.6, "M2.5": 2.0, "M3": 2.4, "M4": 3.2, "M5": 4.7, "M6": 5.2, "M8": 6.8}

    spec = PARTS.get("nut_trap")
    for size, height in iso_4032.items():
        if size not in standards.nut_sizes():
            continue
        assert standards.nut(size).height >= height - 0.01, (
            f"{size}: the table says the nut is {standards.nut(size).height} mm tall, "
            f"ISO 4032 says {height} — a real nut does not fit the pocket"
        )
        built = spec.fn(spec.params(size=size)).mesh
        deep = float(built.bounds.size[2])
        assert deep >= height, f"{size}: the trap is {deep:.2f} mm deep for a {height} mm nut"


@pytest.mark.parametrize("play", [0.0, 0.2, 0.35])
def test_the_magnet_lip_is_narrower_than_the_magnet(play: float) -> None:
    """Eine Haltelippe, die nichts festhält, ist ein Wort im Dialog.

    **Sie hielt in keiner Einstellung.** Der Kegel stand neben dem
    Taschenzylinder und wurde mit ihm vereinigt — und ein Volumen, das man
    einem anderen hinzufügt, kann es nur weiter machen, nie enger. Das Werkzeug
    war über die ganze Höhe zylindrisch, die Lippe verschwand darin. Dazu
    verengte sie um feste 0,2 mm gegenüber der bereits um das Profilspiel
    aufgeweiteten Tasche, also um weniger als nichts: Bei den 0,20 bis 0,35 mm
    der Materialprofile wäre die Öffnung selbst dann weiter als der Magnet
    gewesen, wenn die Boolesche Operation mitgespielt hätte. Zwei Fehler
    übereinander, und beide zeigten dieselbe harmlose Zahl.

    Gemessen wird an der **engsten** Stelle, und die liegt an der Mündung: Ein
    Querschnitt durch die Mitte des Kegels zeigt den Mittelwert und damit ein
    freundlicheres Bild, als das Teil verdient — die erste Fassung dieser
    Messung tat genau das und meldete „hält nicht" für einen Stand, der hielt.
    """
    from app.core.knowledge import standards

    spec = PARTS.get("magnet_pocket")
    entry = standards.magnet("6x3")
    built = spec.fn(spec.params(size="6x3", play=play, press_lip=True)).mesh

    cut = built.raw.section(plane_origin=[0.0, 0.0, -0.02], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None, "nothing at the mouth of the pocket"
    points = np.asarray(cut.vertices, dtype=float)
    mouth = 2.0 * float(np.hypot(points[:, 0], points[:, 1]).max())

    assert mouth < entry.diameter, (
        f"play={play}: the mouth is {mouth:.2f} mm wide for a {entry.diameter} mm magnet — "
        "the lip holds nothing"
    )
    # Und sie sperrt nicht: Der Magnet muss sich hineindrücken lassen.
    assert mouth > entry.diameter - 0.4, (
        f"play={play}: the mouth is {mouth:.2f} mm — that is a press the customer "
        "cannot push through"
    )


@pytest.mark.parametrize("grip", [0.05, 0.1, 0.3])
def test_the_magnet_lip_grips_by_the_amount_it_is_given(grip: float) -> None:
    """Das Übermaß der Haltelippe ist ein Wert, keine Zahl im Code.

    Es stand als feste 0,1 daneben, mit der Begründung, ein Übermaß sei keine
    Toleranz aus dem Profil. Genau das ist es aber: Das Materialprofil führt
    ``press`` (PLA und PETG -0,05, ABS und ASA -0,06, TPU -0,10), der Wert wird
    kalibriert (§28.3), und eine Zahl daneben untergräbt die Kalibrierung —
    dieselbe Tasche liest ihr Spiel längst aus dem Profil (Regel 7).

    Gemessen wird an der **engsten** Stelle, also an der Mündung: Der Kegel
    zeigt in seiner Mitte den Mittelwert und damit ein freundlicheres Bild, als
    das Teil verdient. Und gegen den Magneten, nicht gegen die Tasche — die ist
    um das Profilspiel weiter, und ein Übermaß dagegen wäre keines.
    """
    from app.core.knowledge import standards

    spec = PARTS.get("magnet_pocket")
    entry = standards.magnet("6x3")
    built = spec.fn(spec.params(size="6x3", play=0.25, press_lip=True, grip=grip)).mesh

    # Ein Tausendstel unter der Fläche und nicht zwei Hundertstel: Der Kegel
    # wird über 0,4 mm eng, ein Schnitt 0,02 tiefer liegt fünf Prozent seiner
    # Spanne daneben — bei 0,3 mm Übermaß sind das 0,03 mm, also mehr als die
    # Zusage selbst. Der Test darüber misst gröber, weil er nur „enger als der
    # Magnet" fragt; hier steht eine Zahl.
    cut = built.raw.section(plane_origin=[0.0, 0.0, -0.001], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None, "nothing at the mouth of the pocket"
    points = np.asarray(cut.vertices, dtype=float)
    mouth = 2.0 * float(np.hypot(points[:, 0], points[:, 1]).max())

    assert mouth == pytest.approx(entry.diameter - grip, abs=0.02), (
        f"grip={grip}: the mouth is {mouth:.2f} mm for a {entry.diameter} mm magnet — "
        "the lip does not grip by the amount it was given"
    )


def test_the_magnet_lip_falls_back_when_no_profile_reaches_the_part() -> None:
    """Null im Feld heißt „aus dem Profil" — und ohne Profil nicht „keine Lippe".

    ``PartSpec.fn`` bekommt kein Profil; eingefüllt wird der Wert erst vom
    Bausteinaufruf, so wie beim Spiel. Wo das nicht geschieht, muss die Lippe
    trotzdem halten: Null als Übermaß wäre eine Mündung so weit wie der Magnet,
    also der Zustand, den Version 5 gerade behoben hat.
    """
    from app.core.knowledge import standards
    from app.core.knowledge.parts.mounting import MAGNET_LIP_GRIP

    spec = PARTS.get("magnet_pocket")
    entry = standards.magnet("6x3")
    built = spec.fn(spec.params(size="6x3", play=0.25, press_lip=True)).mesh

    cut = built.raw.section(plane_origin=[0.0, 0.0, -0.001], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None
    points = np.asarray(cut.vertices, dtype=float)
    mouth = 2.0 * float(np.hypot(points[:, 0], points[:, 1]).max())

    assert mouth == pytest.approx(entry.diameter - MAGNET_LIP_GRIP, abs=0.02)


def test_a_part_that_needs_a_face_says_so_instead_of_guessing(profile: Profile) -> None:
    """Regel 21: nie stillschweigend raten — auch nicht über die Stelle.

    **Gefunden über die Oberfläche, nicht hier.** Im Bausteinkatalog wählt man
    einen *Baustein*, keine Fläche; „An Merkmal" steht dann auf „— keines —".
    Bestätigt man so, lief die Operation durch und setzte den Baustein in den
    Nullpunkt des Objekts: halb im Körper, halb unter dem Druckbett. Am
    Lochwand-Einhänger gemessen — 717 mm³ statt 2358, dazu vier Befunde, von
    denen keiner sagte, was fehlt.

    Kein Test hat das gesehen, und der Grund ist derselbe wie immer: **Jeder
    Test setzte ``at_feature``, weil jeder Test wusste, dass es gebraucht
    wird.** Der Kunde weiß es nicht.

    Was **nicht** verlangt wird, ist ein Merkmal um jeden Preis: Wer die
    Position von Hand einträgt, hat gewählt. Die ausgelieferten Beispiele tun
    genau das (siehe :func:`~app.core.knowledge.parts.ops._placed_by_hand`),
    und eine Prüfung nur auf das Merkmal hielt sieben von ihnen an.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])

    for spec in PARTS.all():
        if not (spec.at_face or spec.at_hole):
            continue
        step = new_project("centauri-carbon-2", "petg")
        History(step.document).apply("Quader", [OperationDraft(op="create_box", params={})])
        History(step.document).apply(
            spec.name,
            [OperationDraft(op=part_ops.op_name(spec.name), inputs=("obj_1",), params={})],
        )
        result = evaluate(step.document, profile, sources=ProjectSources(step))

        assert not result.complete, (
            f"{spec.name} was placed without a face and without a position — "
            "it sits in the origin and nobody was asked"
        )
        messages = [str(finding.message) for finding in result.scene.report.findings]
        assert any("Position" in text or "Fläche" in text for text in messages), (
            f"{spec.name} stopped, but the report does not say what is missing: {messages}"
        )


def test_a_part_placed_by_hand_needs_no_feature(profile: Profile) -> None:
    """Wer die Position einträgt, hat gewählt — und wird nicht gefragt.

    Die Gegenprobe zur Prüfung darüber, und sie ist die wichtigere: Ohne sie
    wäre die Regel „ein Baustein braucht ein Merkmal", und das ist falsch. Die
    Mutternfalle des Beispielgehäuses steht auf (-25, -15, 4) mit leerem
    ``at_feature``, seit Monaten, und sie soll dort stehen bleiben.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    History(project.document).apply(
        "Rippe",
        [
            OperationDraft(
                op=part_ops.op_name("rib"), inputs=("obj_1",), params={"x": 5.0, "z": 2.0}
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, (
        "a part positioned by hand was refused: "
        f"{[str(f.message) for f in result.scene.report.findings]}"
    )


@pytest.mark.parametrize("spec", [s for s in PARTS.all() if s.joined_by_host], ids=lambda s: s.name)
def test_a_part_held_by_its_host_becomes_one_with_it(spec: PartSpec, profile: Profile) -> None:
    """Wer den Träger zum Zusammenhalten braucht, wird dort geprüft.

    Der Bereichstest verlangt sonst ``component_count == 1`` vom Baustein
    allein. Für einen Lochwand-Einhänger ohne Rückplatte stimmt das nicht: Zwei
    Haken sind zwei Zapfen, und verbunden werden sie von dem Teil, an das sie
    kommen — genau dafür sind sie da.

    **Die Zusage wandert damit, sie verschwindet nicht.** Was der Baustein
    allein nicht leisten muss, muss er am Träger leisten, und zwar in der
    Stellung, die am schwächsten ist: ohne Platte, mit mehreren Haken, am
    weitesten auseinander. Ein Test, der die Prüfung nur ausnimmt, hätte hier
    nichts mehr gesagt.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 200.0, "depth": 120.0, "height": 20.0})],
    )
    History(project.document).apply(
        spec.name,
        [
            OperationDraft(
                op=part_ops.op_name(spec.name),
                inputs=("obj_1",),
                params={"at_feature": "face_top", "count": 3, "steps": 2, "plate": 0.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    body = result.scene.objects["obj_1"].mesh
    assert body.component_count == 1, (
        f"{spec.name}: three hooks on a plate two grid steps apart do not become one body with it"
    )
    assert body.is_watertight, f"{spec.name}: the result is not printable"


def test_the_library_version_covers_every_part() -> None:
    """Die Bibliotheksversion muss den höchsten Baustein abdecken.

    ``changed_since_library`` fragt: Was hat sich seit dem Stand geändert, mit
    dem dieses Projekt gespeichert wurde? Verglichen wird gegen
    ``LIBRARY_VERSION`` — und wenn die hinter einem Baustein zurückbleibt,
    meldet die Prüfung eine Änderung und nennt dazu zwei gleiche Zahlen:
    „parts: rib, saved: 4, now: 4". Ein Befund, den niemand einordnen kann.

    **Am 25.08.2026 war es genau so.** Sieben Bausteine wanderten an einem Tag
    auf 5 und einer auf 6, die Bibliothek blieb auf 4. Jede einzelne Erhöhung
    war richtig und dokumentiert; mitzuziehen war nur diese eine Zahl, und sie
    steht in einer anderen Datei als die Änderungsverläufe.

    Der Test schließt die Lücke, die drei ähnliche Lücken heute schon hatten:
    eine Zahl, die von Hand mitwandern muss, wandert irgendwann nicht mit.
    """
    highest = max(int(spec.version) for spec in PARTS.all())
    assert int(LIBRARY_VERSION) >= highest, (
        f"the library says {LIBRARY_VERSION}, but a part is already at {highest} — "
        "changed_since_library would report a change and name two equal numbers"
    )


def test_the_range_check_knows_which_parts_their_host_holds_together(
    profile: Profile,
) -> None:
    """Das Feld muss dort wirken, wo der Kunde die Folge sieht.

    ``joined_by_host`` stand einen Tag lang nur in einem Test. Der Bereichstest
    des **Kerns** kannte es nicht, und der ist der, dessen Bericht am
    Katalogeintrag hängt (§24.5): Ein Kunde hätte über dem Lochwand-Einhänger
    „zerfällt in Teile" gelesen — über einem Baustein, der im Einsatz tadellos
    ist.

    Das ist der Fall aus ``.claude/memory/eine-kette-endet-am-letzten-glied.md``
    in Reinform: Ein Feld einzuführen ist nicht dasselbe, wie es zu lesen. Ich
    hatte beim Einbauen sogar den richtigen Satz geschrieben — „statt eine
    Ausnahme in den Test zu schreiben" — und dann genau das getan.
    """
    from app.core.knowledge.parts.range_check import check

    spec = PARTS.get("pegboard_hook")
    assert spec.joined_by_host, "der Einhänger deklariert es nicht mehr"

    strict = check(spec.params, spec.fn, profile)
    assert not strict.passed, (
        "ohne den Schalter müsste der Einhänger an einer Ecke zerfallen — "
        "sonst prüft dieser Test nichts"
    )
    assert any("zerfällt" in failure.reason for failure in strict.failures), (
        f"unerwarteter Grund: {[f.reason for f in strict.failures]}"
    )

    lenient = check(spec.params, spec.fn, profile, joined_by_host=True)
    assert lenient.passed, (
        f"mit dem Schalter darf nichts übrig bleiben: {[f.reason for f in lenient.failures]}"
    )
    assert lenient.checked == strict.checked, "es wurden verschieden viele Ecken gefahren"


@pytest.mark.parametrize(
    ("width", "steps", "loose"),
    [(20.0, 1, True), (60.0, 1, False), (60.0, 2, True), (200.0, 2, False)],
)
def test_a_part_beside_the_object_says_so(
    width: float, steps: int, loose: bool, profile: Profile
) -> None:
    """Was neben dem Teil hängt, wird gemeldet — auf Fehlerstufe.

    **Robert hat es an seinem Würfel gesehen.** Zwei Haken im Vierzigerraster
    stehen ±22,5 mm von der Mitte; auf einem 20 mm breiten Würfel berühren sie
    ihn nicht. Heraus kamen drei lose Stücke, wasserdicht und mit plausiblem
    Volumen, und der Prüfbericht führte „3 Teile" als **Angabe**: null Fehler,
    null Warnungen, zwei Hinweise. Wer nicht weiß, dass dort eine Eins stehen
    müsste, druckt sie.

    Seit die Rückplatte die Ausnahme ist, ist das der Preis dafür — und
    Roberts Entscheidung dazu war eindeutig: melden, und die Platte empfehlen.

    Gemessen wird am **Ergebnis**, nicht an der Breite der Zielfläche. Eine
    Fläche ist schnell nachgerechnet, trifft aber nicht jeden Fall: eine
    schmale Fläche auf einem breiten Teil, ein Loch dazwischen, eine Rundung —
    da stimmt die Rechnung und der Körper zerfällt trotzdem. Die vier Fälle
    hier decken beide Richtungen ab, damit die Prüfung nicht bloß immer
    „Fehler" sagt.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": width, "depth": width, "height": 20.0})],
    )
    History(project.document).apply(
        "Einhänger",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "count": 2, "steps": steps},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, [str(f.message) for f in result.scene.report.findings]

    errors = [f for f in result.scene.report.findings if f.severity == "error"]
    hanging = [f for f in errors if f.code == "parts.hanging_loose"]
    body = result.scene.objects["obj_1"].mesh

    if loose:
        assert hanging, (
            f"width={width} steps={steps}: {body.component_count} Teile und kein Fehler — "
            "der Kunde druckt lose Stücke"
        )
        assert "Rückplatte" in str(hanging[0].message), (
            "der Befund empfiehlt die Rückplatte nicht (Regel 17)"
        )
    else:
        assert not hanging, (
            f"width={width} steps={steps}: Fehlalarm bei {body.component_count} Teilen"
        )
        assert body.component_count == 1, "der Träger hält den Baustein doch nicht"


def test_the_advice_for_a_loose_part_names_fields_that_part_has(profile: Profile) -> None:
    """Regel 17: ein Vorschlag, der trägt — und nicht einer, der ins Leere zeigt.

    ``parts.hanging_loose`` gilt für **jeden** anbauenden Baustein, und der
    Satz nannte trotzdem die Felder des Lochwand-Einhängers: „Geben Sie eine
    Rückplatte an … oder verringern Sie die Rasterschritte." Eine Rippe hat
    weder eine Rückplatte noch Rasterschritte, ein Scharnierauge und ein
    Kabelclip auch nicht — wer den Satz befolgen wollte, suchte zwei Felder,
    die es in seinem Dialog nicht gibt.

    Gefragt wird das Parameterschema des Bausteins, nicht sein Name: Der
    Zusatz erscheint dort, wo er einzulösen ist.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 20.0, "height": 20.0})],
    )
    History(project.document).apply(
        "Rippe",
        [OperationDraft(op="insert_rib", inputs=("obj_1",), params={"x": 100.0})],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    hanging = [f for f in result.scene.report.findings if f.code == "parts.hanging_loose"]
    assert hanging, "eine Rippe 100 mm neben dem Würfel hängt in der Luft und niemand sagt es"

    message = str(hanging[0].message)
    assert "Rückplatte" not in message and "Rasterschritte" not in message, (
        f"die Rippe hat weder das eine noch das andere Feld: {message}"
    )
    assert "Merkmal" in message or "Position" in message, (
        f"und ohne einen Weg nach vorn endet der Befund mit „fehlgeschlagen“: {message}"
    )


# --- die Normteiltabelle -----------------------------------------------------------


def test_the_table_answers_the_question_from_the_plan() -> None:
    """§24.2: „Loch für eine M4-Einpressbuchse" muss ein Nachschlagen sein."""
    assert standards.insert("M4").hole == pytest.approx(5.6)
    assert standards.screw("M4").clearance == pytest.approx(4.5)
    assert standards.nut("M4").width == pytest.approx(7.0)


def test_every_screw_size_has_a_matching_standard_washer() -> None:
    """Eine angebotene Schraube darf nicht erst beim Scheibensitz aus der Tabelle fallen."""
    assert set(standards.washer_sizes()) == set(standards.screw_sizes())


def test_heatset_entries_name_the_real_product_variant() -> None:
    """Eine Gewindegröße allein unterscheidet lange und kurze Buchsen nicht."""
    regular = standards.insert("M4")
    short = standards.insert("M4S")

    assert regular.thread == short.thread == "M4"
    assert regular.length == pytest.approx(8.1)
    assert short.length == pytest.approx(4.0)
    assert regular.outer == short.outer == pytest.approx(6.3, abs=0.01)


def test_every_heatset_insert_is_wider_than_its_installation_hole() -> None:
    """`outer == hole` war zweimal dieselbe Bohrung, kein Buchsenmaß."""
    for size in standards.insert_sizes():
        entry = standards.insert(size)
        assert entry.outer > entry.hole
        assert entry.thread in standards.screw_sizes()


def test_the_bearing_table_covers_small_and_common_housings() -> None:
    """Der Lagersitz soll nicht nur die eine Skateboardgröße anbieten."""
    assert {"623", "624", "625", "626", "608", "6800", "6000", "6001"} <= set(
        standards.bearing_sizes()
    )


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


def test_agent_and_table_offer_the_same_standard_kinds() -> None:
    """Eine neue Tabellenart erreicht Agent und Oberfläche ohne zweite Liste."""
    from app.core.agent.tools import STANDARD_KINDS

    assert tuple(standards.TABLES) == STANDARD_KINDS
    assert "board" in STANDARD_KINDS, "Lochwandmaße sind hinterlegt und müssen lesbar sein"


def test_every_typed_standard_table_offers_its_sizes() -> None:
    """Scheiben und Lager sind keine Tabellen zweiter Klasse."""
    assert standards.washer_sizes() == tuple(standards.load().washers)
    assert standards.bearing_sizes() == tuple(standards.load().bearings)


def test_duplicate_standard_sizes_are_rejected(tmp_path: Path) -> None:
    """Ein Tippfehler darf keinen älteren Datensatz still überschreiben."""
    table = tmp_path / "standards.toml"
    table.write_text(
        """
version = "test"

[[magnets]]
size = "8x3"
diameter = 8.0
height = 3.0

[[magnets]]
size = "8x3"
diameter = 9.0
height = 3.0
""".strip(),
        encoding="utf-8",
    )

    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as raised:
        standards.load(table)
    assert raised.value.values["size"] == "8x3"


def test_impossible_standard_dimensions_are_rejected(tmp_path: Path) -> None:
    """Innendurchmesser, Außenmaß und Verweise werden beim Laden geprüft."""
    table = tmp_path / "standards.toml"
    table.write_text(
        """
version = "test"

[[bearings]]
size = "verkehrt"
inner = 12.0
outer = 10.0
width = 4.0
""".strip(),
        encoding="utf-8",
    )

    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as raised:
        standards.load(table)
    assert raised.value.values["size"] == "verkehrt"


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
def test_an_added_part_has_the_component_count_it_declares(
    pair: tuple[PartSpec, BaseParams], profile: Profile
) -> None:
    """Ein aufgesetzter Baustein verbindet sich — außer als lösbares Gegenstück.

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
    expected = 2 if spec.separate_from_host else 1
    assert body.component_count == expected, direction_ids(pair)
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


def _plate_with_a_through_bore() -> Project:
    """Eine 10 mm dicke Platte mit einer durchgehenden Bohrung Ø 6.

    Gebohrt wird ohne Materialzugabe, damit die gemessenen Durchmesser unten
    nicht vom Profil abhängen: Die Bohrung misst 6,00 mm, und alles darüber
    kommt vom Baustein.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Platte",
        [OperationDraft(op="create_box", params={"width": 40.0, "depth": 40.0, "height": 10.0})],
    )
    History(project.document).apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 6.0, "depth": 0.0, "compensate": False},
            )
        ],
    )
    return project


def _widest_bore(mesh: Any, height: float) -> float:
    """Der weiteste Durchmesser des mittigen Lochs auf dieser Höhe.

    Gemessen wird nur, was innerhalb von 15 mm um die Achse liegt — die
    Außenkontur der Platte steht bei 20 mm und würde jede Zahl überdecken.
    """
    cut = mesh.raw.section(plane_origin=[0.0, 0.0, height], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None, f"z={height}: der Schnitt trifft die Platte nicht"
    points = np.asarray(cut.vertices, dtype=float)
    radii = np.hypot(points[:, 0], points[:, 1])
    inner = radii[radii < 15.0]
    assert inner.size, f"z={height}: auf dieser Höhe ist gar kein Loch"
    return 2.0 * float(inner.max())


def test_a_tool_in_a_bore_starts_at_its_mouth(profile: Profile) -> None:
    """Ein Gewinde in einer Bohrung schneidet die **ganze** Bohrung.

    ``_anchor`` gab für ein Bohrungsmerkmal ``centre`` zurück — die *Mitte* des
    Zylinders. Ein abtragender Baustein liegt aber unter seiner Mündung
    (§24.1), also fing das Werkzeug in halber Materialstärke an: Auf einer
    10 mm dicken Platte trug ein Innengewinde mit 12 mm Länge unten zwischen
    z = 0 und z = 5 ab und ließ die obere Hälfte glatt — gemessen 6,25 mm
    Gewindeaußenmaß bei z = 1 und 3 gegen glatte 6,00 mm bei z = 7 und 9.
    Sieben von zwölf Millimetern Werkzeug hingen unter der Platte in der Luft.

    Über eine **Fläche** gesetzt war derselbe Handgriff immer richtig, und
    genau deshalb ist es niemandem aufgefallen: Der Weg, den jeder Test ging,
    war der heile. Der zweite Fall unten hält ihn fest — er darf sich nicht
    ändern.
    """
    for feature, threaded in (("hole_1", "die Bohrung"), ("face_top", "die Fläche")):
        project = _plate_with_a_through_bore()
        History(project.document).apply(
            "Gewinde",
            [
                OperationDraft(
                    op="insert_printed_thread",
                    inputs=("obj_1",),
                    params={
                        "at_feature": feature,
                        "internal": True,
                        "size": "M6",
                        "length": 12.0,
                    },
                )
            ],
        )
        result = evaluate(project.document, profile, sources=ProjectSources(project))

        assert result.complete, [str(f.message) for f in result.scene.report.findings]
        mesh = result.scene.objects["obj_1"].mesh
        smooth = [
            height for height in (1.0, 3.0, 5.0, 7.0, 9.0) if _widest_bore(mesh, height) < 6.1
        ]
        assert not smooth, (
            f"an {feature} gesetzt ({threaded}) blieb die Bohrung auf z={smooth} glatt — "
            "dort greift keine Schraube"
        )


def test_a_container_thread_and_a_lid_thread_are_a_matching_pair(profile: Profile) -> None:
    """Der Behälter bekommt außen, sein Deckel innen dieselbe Gewindegröße."""
    container = new_project("centauri-carbon-2", "petg")
    History(container.document).apply(
        "Behälter",
        [OperationDraft(op="create_box", params={"width": 30.0, "depth": 30.0, "height": 10.0})],
    )
    History(container.document).apply(
        "Außengewinde",
        [
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "size": "M6", "length": 12.0},
            )
        ],
    )
    container_result = evaluate(
        container.document,
        profile,
        sources=ProjectSources(container),
    )

    lid = _plate_with_a_through_bore()
    History(lid.document).apply(
        "Innengewinde",
        [
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"at_feature": "hole_1", "size": "M6", "length": 12.0, "internal": True},
            )
        ],
    )
    lid_result = evaluate(lid.document, profile, sources=ProjectSources(lid))

    assert container_result.complete and lid_result.complete
    outer = next(
        feature
        for feature in container_result.scene.objects["obj_1"].features.values()
        if feature.kind == "thread"
    )
    inner = next(
        feature
        for feature in lid_result.scene.objects["obj_1"].features.values()
        if feature.kind == "thread"
    )
    assert not outer.params["internal"] and inner.params["internal"]
    assert outer.params["diameter"] == inner.params["diameter"] == 6.0
    assert outer.params["pitch"] == inner.params["pitch"]


@pytest.mark.parametrize("countersunk", [False, True])
def test_a_printed_screw_sits_in_its_bore_and_keeps_its_head_outside(
    profile: Profile, countersunk: bool
) -> None:
    """Das Gegenstück sitzt an der Bohrungsmündung, nicht in ihrer Mitte.

    Es bleibt absichtlich ein eigener Körper: Eine echte Schraube soll sich
    lösen lassen, auch wenn ihr Kopf in einer Senkung ohne Materialkontakt
    liegt. Die Operation darf daraus keinen Fehler über ein loses Anbauteil
    machen.
    """
    project = _plate_with_a_through_bore()
    History(project.document).apply(
        "Schraube",
        [
            OperationDraft(
                op="insert_printed_screw",
                inputs=("obj_1",),
                params={
                    "at_feature": "hole_1",
                    "size": "M6",
                    "length": 12.0,
                    "countersunk": countersunk,
                },
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    entry = result.scene.objects["obj_1"]
    assert entry.mesh.bounds.maximum[2] > 10.0, "der Kopf liegt über der Platte"
    assert entry.mesh.bounds.minimum[2] < 0.0, "der Schaft reicht durch die Bohrung"
    assert entry.mesh.component_count == 2, "Schraube und Werkstück bleiben lösbar"
    from app.core.units import EPS_GEOM

    components = list(entry.mesh.raw.split(only_watertight=False))
    screw = max(components, key=lambda mesh: float(mesh.bounds[1][2]))
    points = np.asarray(screw.vertices, dtype=float)
    radii = np.hypot(points[:, 0], points[:, 1])
    inside_plate = (points[:, 2] > EPS_GEOM) & (points[:, 2] < 10.0 - EPS_GEOM)
    outside_bore = radii > 3.0 + EPS_GEOM
    assert not np.any(inside_plate & outside_bore), (
        "eine lösbare Schraube darf nicht in das Werkstück hineinragen"
    )
    threads = [feature for feature in entry.features.values() if feature.kind == "thread"]
    assert any(not feature.params["internal"] for feature in threads)
    assert not any(
        finding.code == "parts.hanging_loose" for finding in result.scene.report.findings
    )


def test_a_separate_printed_screw_keeps_existing_material_slots(profile: Profile) -> None:
    """Ein nachträglich eingesetztes Teil entfärbt das Werkstück nicht.

    Die Schraube bleibt geometrisch getrennt und hängt deshalb ohne Boolesche
    Operation am vorhandenen Netz. Genau dieser kürzere Weg ließ bislang die
    Slotliste fallen, sobald die Zahl der Dreiecke wuchs.
    """
    project = _plate_with_a_through_bore()
    History(project.document).apply(
        "Filament",
        [
            OperationDraft(
                op="assign_slot",
                inputs=("obj_1",),
                params={"slot": 2, "name": "PETG Rot", "colour": "#C53D38"},
            )
        ],
    )
    History(project.document).apply(
        "Schraube",
        [
            OperationDraft(
                op="insert_printed_screw",
                inputs=("obj_1",),
                params={"at_feature": "hole_1", "size": "M6", "length": 12.0},
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    mesh = result.scene.objects["obj_1"].mesh
    assert len(mesh.slots) == mesh.triangle_count
    assert 2 in mesh.slots, "das zugewiesene Filament des Werkstücks bleibt erhalten"
    assert 0 in mesh.slots, "das neue, noch nicht zugewiesene Teil bleibt als Standard erkennbar"


def test_printed_nut_has_the_matching_internal_thread() -> None:
    """Schraube und Mutter sind ein Paar, nicht zwei ähnlich benannte Körper."""
    screw = PARTS.get("printed_screw").fn(PARTS.get("printed_screw").params(size="M5", length=12.0))
    nut = PARTS.get("printed_nut").fn(PARTS.get("printed_nut").params(size="M5"))

    external = next(feature for feature in screw.features.values() if feature.kind == "thread")
    internal = next(feature for feature in nut.features.values() if feature.kind == "thread")
    assert external.params["diameter"] == internal.params["diameter"] == 5.0
    assert external.params["pitch"] == internal.params["pitch"]
    assert not external.params["internal"] and internal.params["internal"]


def test_a_part_that_reaches_upwards_keeps_the_middle_of_the_bore(profile: Profile) -> None:
    """Die Gegenprobe, und ohne sie wäre die Regel oben falsch.

    Nicht jeder Baustein an einer Bohrung liegt unter seinem Ursprung: Die
    Mutternfalle baut ihre Tasche **nach oben**, weil die Mutter im Material
    sitzt und nicht an der Oberfläche. An die Mündung gesetzt stünde sie
    vollständig über der Platte und trüge nichts ab — aus einem halben Fehler
    wäre ein ganzer geworden.

    Gemessen wird an der Tasche selbst: Auf halber Höhe muss sie da sein, und
    dicht unter der Oberfläche darf sie es nicht.
    """
    project = _plate_with_a_through_bore()
    History(project.document).apply(
        "Mutternfalle",
        [
            OperationDraft(
                op="insert_nut_trap",
                inputs=("obj_1",),
                params={"at_feature": "hole_1", "size": "M3", "slide": 12.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    mesh = result.scene.objects["obj_1"].mesh
    assert _widest_bore(mesh, 5.5) > 6.5, "die Tasche liegt nicht mehr im Material"
    assert _widest_bore(mesh, 9.5) < 6.5, "die Tasche ist an die Oberfläche gewandert"


def test_a_nut_trap_on_a_top_face_sinks_into_the_material(profile: Profile) -> None:
    """Die Mutternfalle an einer Fläche baut ihre Tasche ins Material (§24.1).

    Sie ist der einzige abtragende Baustein, der nach oben baut — die Mutter
    sitzt im Material, nicht an der Oberfläche. An eine Bohrung gesetzt bleibt
    sie deshalb in deren Mitte (:func:`test_a_part_that_reaches_upwards_keeps_
    the_middle_of_the_bore`); an eine **Deckfläche** gesetzt stand sie vorher
    vollständig über der Platte und trug nichts ab — ``boolean.without_effect``,
    unverändertes Volumen. Jetzt wird sie entgegen der Normalen ins Material
    gebaut, die Öffnung an der Fläche.

    Gemessen wird an drei Dingen: der Befund darf nicht mehr kommen, das
    Volumen muss sinken, und dicht unter der Deckfläche muss der Sechskant
    stehen — ohne über die Fläche hinauszuwachsen.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    plate_volume = before.scene.objects["obj_1"].mesh.raw.volume

    History(project.document).apply(
        "Mutternfalle",
        [
            OperationDraft(
                op="insert_nut_trap",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "size": "M6", "slide": 0.0, "screw_hole": False},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    codes = [f.code for f in result.scene.report.findings]
    assert "boolean.without_effect" not in codes, "die Tasche liegt neben dem Körper statt darin"
    mesh = result.scene.objects["obj_1"].mesh
    assert mesh.raw.volume < plate_volume - 1.0, "die Mutternfalle hat nichts abgetragen"
    # Die Deckfläche liegt bei z = 10; die Tasche sitzt darunter, ihre Öffnung an ihr.
    assert _widest_bore(mesh, 9.5) > 6.5, "dicht unter der Fläche fehlt die Tasche"
    assert mesh.bounds.maximum[2] == pytest.approx(10.0, abs=0.02), (
        "die Tasche wächst über die Fläche hinaus statt ins Material"
    )


def test_head_room_cuts_below_the_mouth_not_above_it(profile: Profile) -> None:
    """Die Kopffreiheit trägt Material ab, und zwar unter der Fläche (§24.1).

    ``head_room`` baute seinen Zylinder bei z = 0 nach +Z — über die Mündung,
    in die Luft über der Fläche. Der Baustein ist abtragend und liegt unter
    seiner Mündung; nach oben gebaut trug der Zylinder nichts ab, und der
    versenkte Kopf stand vor. Jetzt liegt die zylindrische Aussparung in
    Kopfbreite unter der Deckfläche, die Senkung um denselben Betrag tiefer.

    Gemessen wird auf halber Kopffreiheit (1,5 mm unter der Fläche), wo der
    alte Stand nichts abtrug: dort steht jetzt der Kopfdurchmesser, und die
    Gegenprobe ohne Kopffreiheit zeigt an derselben Stelle nur die schmale
    Senkung.
    """

    def bore_at(head_room: float, height: float) -> float:
        project = new_project("centauri-carbon-2", "petg")
        History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
        History(project.document).apply(
            "Loch",
            [
                OperationDraft(
                    op="insert_screw_hole",
                    inputs=("obj_1",),
                    params={
                        "at_feature": "face_top",
                        "size": "M4",
                        "depth": 10.0,
                        "countersink": True,
                        "head_room": head_room,
                    },
                )
            ],
        )
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        assert result.complete, [str(f.message) for f in result.scene.report.findings]
        mesh = result.scene.objects["obj_1"].mesh
        assert mesh.bounds.maximum[2] == pytest.approx(10.0, abs=0.02), (
            "die Kopffreiheit steht über der Fläche vor statt sie zu versenken"
        )
        return _widest_bore(mesh, height)

    countersink = float(standards.screw("M4").countersink)
    with_room = bore_at(3.0, 8.5)
    without_room = bore_at(0.0, 8.5)
    assert with_room >= countersink - 0.1, (
        f"die Kopffreiheit misst {with_room:.2f} mm, der Kopf braucht {countersink:.2f} mm"
    )
    assert without_room < with_room - 1.0, (
        f"ohne Kopffreiheit ist das Loch dort {without_room:.2f} mm — die Aussparung "
        "trägt nichts Neues ab"
    )


def test_a_round_screw_head_gets_its_own_diameter() -> None:
    """„Senkung aus“ meint einen Zylinderkopf, nicht einen breiten Senkkopf."""
    spec = PARTS.get("screw_hole")
    built = spec.fn(
        spec.params(
            size="M4",
            depth=10.0,
            countersink=False,
            head_room=3.0,
        )
    )

    diameter = built.mesh.bounds.size[0]
    screw = standards.screw("M4")
    assert diameter == pytest.approx(screw.head, abs=0.1)
    assert diameter < screw.countersink - 0.5, "die runde Aussparung nimmt das Senkkopfmaß"


def test_the_screw_head_choice_only_promises_the_supported_round_head() -> None:
    """Der Dialog darf einen Linsenkopf nicht mit dem Zylinderkopfmaß gleichsetzen."""
    countersink = next(
        entry for entry in PARTS.get("screw_hole").params.spec() if entry.name == "countersink"
    )

    assert "Zylinderkopf" in str(countersink.doc)
    assert "Linsenkopf" not in str(countersink.doc)


def test_a_screw_hole_can_recess_its_standard_washer() -> None:
    """Die Tabellenmaße der Scheibe müssen als passende Tasche nutzbar sein."""
    spec = PARTS.get("screw_hole")
    washer = standards.washer("M4")
    built = spec.fn(
        spec.params(
            size="M4",
            depth=10.0,
            countersink=False,
            head_room=0.0,
            washer=True,
            play=0.2,
        )
    )

    recess = built.features["washer_1"]
    assert recess.params["diameter"] == pytest.approx(washer.outer + 0.2)
    assert recess.params["depth"] == pytest.approx(washer.thickness)
    assert built.mesh.bounds.size[0] == pytest.approx(washer.outer + 0.2, abs=0.02)


def test_a_recessed_washer_follows_the_screw_head_depth() -> None:
    """Kopftiefe senkt die Scheibenauflage mit ab, statt unter ihr leer zu enden."""
    spec = PARTS.get("screw_hole")
    washer = standards.washer("M4")
    head_depth = 3.0
    built = spec.fn(
        spec.params(
            size="M4",
            depth=10.0,
            countersink=False,
            head_room=head_depth,
            washer=True,
            play=0.2,
        )
    )

    recess = built.features["washer_1"]
    assert recess.params["centre"][2] == pytest.approx(-head_depth - washer.thickness / 2.0)
    assert recess.params["depth"] == pytest.approx(washer.thickness)


def test_short_and_regular_heatset_inserts_cut_their_named_depth() -> None:
    """Im Feld wählt man die gekaufte Länge; dieselbe muss im Modell ankommen."""
    spec = PARTS.get("heatset_m4")
    regular = spec.fn(spec.params(size="M4", extra_depth=0.0))
    short = spec.fn(spec.params(size="M4S", extra_depth=0.0))

    assert regular.mesh.bounds.size[2] == pytest.approx(8.1, abs=0.02)
    assert short.mesh.bounds.size[2] == pytest.approx(4.0, abs=0.02)


def test_a_bearing_seat_uses_the_bearing_and_material_fit() -> None:
    """Außenmaß und Breite kommen aus der Tabelle, die Passung aus dem Profil."""
    spec = PARTS.get("bearing_seat")
    bearing = standards.bearing("608")
    removable = spec.fn(
        spec.params(size="608", removable=True, play=0.25, grip=0.05, extra_depth=0.0)
    )
    pressed = spec.fn(
        spec.params(size="608", removable=False, play=0.25, grip=0.05, extra_depth=0.0)
    )

    assert removable.mesh.bounds.size[0] == pytest.approx(bearing.outer + 0.25, abs=0.02)
    assert pressed.mesh.bounds.size[0] == pytest.approx(bearing.outer - 0.05, abs=0.02)
    assert removable.mesh.bounds.size[2] == pytest.approx(bearing.width, abs=0.02)
    seat = removable.features["seat_1"]
    assert seat.params["diameter"] == pytest.approx(bearing.outer + 0.25)
    assert seat.params["depth"] == pytest.approx(bearing.width)


def test_a_bearing_seat_only_offers_the_fit_value_that_has_an_effect() -> None:
    """Niemand soll einen sichtbaren Passungswert eintragen, den der Sitz ignoriert."""
    fields = {entry.name: entry for entry in PARTS.get("bearing_seat").params.spec()}

    assert fields["play"].depends_on == ("removable", (True,))
    assert fields["grip"].depends_on == ("removable", (False,))


def test_a_custom_magnet_size_reaches_the_pocket() -> None:
    """Ein gemessener Magnet darf benutzt werden, ohne eine Normbezeichnung zu kennen."""
    spec = PARTS.get("magnet_pocket")
    built = spec.fn(
        spec.params(
            size="6x3",
            diameter=9.0,
            height=4.0,
            play=0.2,
            press_lip=False,
            cover=0.0,
        )
    )

    pocket = built.features["pocket_1"]
    assert pocket.params["diameter"] == pytest.approx(9.2)
    assert pocket.params["depth"] == pytest.approx(4.0)
    assert built.mesh.bounds.size[2] == pytest.approx(4.0, abs=0.02)


def test_a_shallow_custom_magnet_keeps_its_depth_with_a_lip() -> None:
    """Eine Haltelippe darf aus einer flachen Sondergröße keine tiefere Tasche machen."""
    spec = PARTS.get("magnet_pocket")
    built = spec.fn(
        spec.params(
            size="6x3",
            diameter=6.0,
            height=0.2,
            play=0.0,
            press_lip=True,
            grip=0.1,
            cover=0.0,
        )
    )

    assert built.features["pocket_1"].params["depth"] == pytest.approx(0.2)
    assert built.mesh.bounds.size[2] == pytest.approx(0.2, abs=0.02)


def test_a_custom_magnet_too_narrow_for_its_lip_gets_a_clear_error() -> None:
    """Ein unmögliches Übermaß darf keine negative Öffnung an die Geometrie reichen."""
    from app.core.errors import ValidationError

    spec = PARTS.get("magnet_pocket")
    with pytest.raises(ValidationError) as caught:
        spec.fn(
            spec.params(
                size="6x3",
                diameter=0.1,
                height=1.0,
                press_lip=True,
                grip=0.1,
                cover=0.0,
            )
        )

    assert caught.value.field == "diameter"
    assert caught.value.suggestions, "Regel 17: die Korrektur braucht eine Handlung"


def test_a_custom_cable_diameter_reaches_gland_and_clip() -> None:
    """Ein gemessenes Kabelmaß gilt in beiden Kabelbausteinen gleich."""
    gland = PARTS.get("cable_gland")
    gland_built = gland.fn(
        gland.params(
            size="cable-5",
            diameter=9.0,
            play=0.2,
            strain_relief=False,
        )
    )
    assert gland_built.features["bore_1"].params["diameter"] == pytest.approx(9.2)

    clip = PARTS.get("cable_clip")
    clip_values = clip.params(size="cable-5", diameter=9.0, play=0.2, width=8.0)
    clip_built = clip.fn(clip_values)
    assert clip_built.features["seat_1"].params["area"] == pytest.approx(9.2 * 8.0)


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
    assert checked >= 8, "die Prüfung muss die Bausteine mit Spiel wirklich sehen"


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

    # **Eine bestellte Rückplatte trägt jeden Zapfen, mit Rand ringsum.** Ein
    # Zapfen an der Plattenkante hätte kein Material, das ihn hält.
    #
    # Ohne Platte gibt es nichts zu umschließen — seit dem 25.08.2026 ist sie
    # die Ausnahme statt die Vorgabe, und die Haken hängen dann an dem Teil, an
    # das sie kommen. Der Baustein misst dort genau so breit wie seine Zapfen,
    # und das ist richtig; geprüft wird der Zusammenhalt am Träger
    # (``test_a_part_held_by_its_host_becomes_one_with_it``).
    ordered = spec.fn(spec.params(count=count, plate=2.0)).mesh
    breit = float(ordered.bounds.size[0])
    assert breit > (zapfen[-1] - zapfen[0]) + board.slot_width, (
        f"count={count}: the plate is {breit:.1f} mm wide and does not reach around the outer hooks"
    )


def fits_the_slot(points: np.ndarray, board: Any, shift: float) -> bool:
    """Passt dieser Punkthaufen durch den Schlitz, wenn er um ``shift`` steigt?

    **Gegen die Öffnung, nicht gegen ihren Hüllquader.** Ein Schlitz hat runde
    Enden; ein Rechteck, das in 5 mal 15 passt, passt deshalb noch lange nicht
    in das Loch (der Docstring des Bausteins rechnet es vor). Geprüft wird
    darum gegen die Stadionform: innerhalb des geraden Stücks zählt nur die
    Breite, an den Enden der Abstand zum Mittelpunkt des Halbkreises.

    ``shift`` ist die Höhe, in der das Teil gerade hängt. Dass die Frage über
    **alle** Höhen gestellt werden muss, ist der Kern der Sache: Ein Einhänger
    ohne Rastzunge passt bei einer davon hindurch, und genau dort nimmt ihn
    jemand versehentlich ab.
    """
    radius = board.slot_width / 2.0
    straight = board.slot_height / 2.0 - radius
    x = points[:, 0]
    y = points[:, 1] + shift
    inside = (np.abs(x) <= radius + 1e-9) & (
        (np.abs(y) <= straight + 1e-9) | (x**2 + (np.abs(y) - straight) ** 2 <= radius**2 + 1e-9)
    )
    return bool(inside.all())


def slot_heights(points: np.ndarray, board: Any) -> list[float]:
    """Bei welchen Höhen der Punkthaufen durch den Schlitz ginge."""
    return [
        float(shift)
        for shift in np.arange(-board.slot_height, board.slot_height, 0.05)
        if fits_the_slot(points, board, float(shift))
    ]


def behind_the_board(built: Any, board: Any) -> np.ndarray:
    """Die Punkte jenseits der Plattenrückseite — was hinter der Wand liegt.

    Die Lochwand liegt zwischen der angeklickten Fläche und ihrer eigenen
    Dicke; eine bestellte Rückplatte steckt **im** Teil und damit unter null.
    Gezählt wird deshalb ab der Plattendicke und nicht ab der Rückplatte.
    """
    points = np.asarray(built.mesh.raw.vertices, dtype=float)
    return points[points[:, 2] > board.thickness + 0.05]


def through_the_board(built: Any, board: Any) -> np.ndarray:
    """Der Querschnitt im Brett — was durch den Schlitz muss.

    Als Schnitt und nicht über die Eckpunkte: Zapfen und Zunge sind Prismen
    durch das ganze Brett, die haben zwischen ihren Enden keine.
    """
    cut = built.mesh.raw.section(
        plane_origin=[0.0, 0.0, board.thickness / 2.0], plane_normal=[0.0, 0.0, 1.0]
    )
    assert cut is not None, "nothing goes through the board at all"
    return np.asarray(cut.vertices, dtype=float)


def spring_gap(mesh: Any, height: float) -> float:
    """Der größte freie Abstand in Y auf dieser Höhe — der Weg der Zunge.

    Am Schnitt gemessen und nicht an einer Formel: Wo Zunge und Zapfen zwei
    getrennte Umrisse sind, ist der größte Sprung zwischen zwei Umrisskanten
    genau der Spalt, in den die Zunge ausweichen kann.
    """
    cut = mesh.raw.section(plane_origin=[0.0, 0.0, height], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None, f"nothing to measure at z={height}"
    values = np.unique(np.round(np.asarray(cut.vertices, dtype=float)[:, 1], 4))
    return float(np.diff(values).max()) if len(values) > 1 else 0.0


def loose_at(mesh: Any, height: float) -> bool:
    """Ob die Zunge auf dieser Höhe frei ist — zwei Umrisse statt einem."""
    cut = mesh.raw.section(plane_origin=[0.0, 0.0, height], plane_normal=[0.0, 0.0, 1.0])
    return cut is not None and len(cut.discrete) > 1


def solid_fraction(mesh: Any, centre: Any, size: float = 0.4) -> float:
    """Wie viel eines kleinen Würfels um diesen Punkt im Material liegt.

    Ein Merkmal ist ein Anhaltspunkt an der Oberfläche. Liegt sein Mittelpunkt
    mitten im Körper, findet die Zuordnung dort nichts, worauf sie zeigen
    könnte — und keine Kennzahl merkt es. Ein halber Würfel heißt: auf einer
    Fläche. Ein ganzer heißt: im Material.
    """
    probe = shapes.moved(
        shapes.box(size, size, size),
        (float(centre[0]), float(centre[1]), float(centre[2]) - size / 2.0),
    )
    # ``allow_empty``, weil leer hier eine Antwort ist: Ein Würfel in der Luft
    # schneidet nichts, und genau danach wird für die Richtung gefragt. Ohne
    # das Wort hält die Rückfallkette den leeren Schnitt für ihr eigenes
    # Versagen und wirft.
    schnitt = boolean("intersection", [mesh, probe], allow_empty=True).mesh
    return float(schnitt.volume / size**3)


def shoulder_step(built: Any, board: Any) -> float:
    """Um wie viel die Rastschulter über den Querschnitt im Brett hinaussteht.

    Das ist der Federweg, den die Zunge beim Einführen zurücklegen muss, und
    zugleich das Maß, mit dem sie hinter der Platte sperrt — gemessen am Netz
    und nicht an der Formel, die ihn ausrechnet.
    """
    return float(
        through_the_board(built, board)[:, 1].min() - behind_the_board(built, board)[:, 1].min()
    )


def test_the_hook_fits_the_slot_it_is_made_for() -> None:
    """Was durch den Schlitz muss, muss durch den Schlitz passen.

    Gemessen wird am gebauten Netz und gegen die Tabelle: Alle Punkte, die im
    Brett liegen, gehören zu dem Teil, das durch das Loch geht, und sie müssen
    bei irgendeiner Höhe hineinpassen. Tun sie es nicht, liegt das Teil daneben
    statt zu hängen.

    **Die Grenze verläuft seit der Rastzunge an der Plattenrückseite, nicht an
    der Rückplatte.** Vorher maß dieser Test alles jenseits der Rückplatte —
    also Zapfen, Nase und Zunge zusammen — gegen die Schlitzhöhe. Was hinter
    der Wand liegt, *soll* aber höher sein als der Schlitz: Genau das ist die
    Verriegelung. Durch das Loch geht nur, was im Loch steckt.

    **Ohne Boolesche Operation, und das ist kein Umweg.** Der erste Versuch
    stellte eine Platte mit Schlitz daneben und fragte nach der Schnittmenge.
    Sie ist nie leer: Die Rückplatte des Hakens liegt an der Lochwand an, und
    zwar flächig — das ist keine Klemmung, sondern der Zweck. Wer hier eine
    Boolesche Operation befragt, misst die Berührung und nicht die Passung.
    """
    spec = PARTS.get("pegboard_hook")
    values = spec.params(count=1, play=0.2)
    built = spec.fn(values)
    board = standards.board(values.system)

    im_schlitz = through_the_board(built, board)
    assert len(im_schlitz), "nothing reaches into the board at all"
    assert slot_heights(im_schlitz, board), (
        f"the hook is {np.ptp(im_schlitz[:, 0]):.2f} by {np.ptp(im_schlitz[:, 1]):.2f} mm and "
        f"goes into no {board.slot_width} by {board.slot_height} slot at any height"
    )

    # Und er soll den Schlitz auch ausnutzen: Ein Haken, der nur halb so hoch
    # ist wie das Loch, hält beim ersten Anstoßen nicht.
    hoch = float(im_schlitz[:, 1].max() - im_schlitz[:, 1].min())
    assert hoch > board.slot_height / 2.0, (
        f"the hook only uses {hoch:.2f} mm of the {board.slot_height} mm slot"
    )

    # **Und das Spiel ist wirklich abgezogen.** ``fits_the_slot`` fragt „passt
    # es hinein" — und das täte ein Zapfen in voller Schlitzbreite auch, auf
    # den Hundertstel genau. Ein Baustein, der ``play`` vergisst, käme damit
    # durch und klemmte beim Kunden in einer Wand, deren Schlitze nie exakt
    # fünf Millimeter breit sind. Also gegen die Zahl und nicht gegen die
    # Grenze.
    breit = float(np.ptp(im_schlitz[:, 0]))
    assert breit == pytest.approx(board.slot_width - values.play, abs=0.05), (
        f"the shank is {breit:.2f} mm wide in a {board.slot_width} mm slot — "
        f"with {values.play} mm play it should be {board.slot_width - values.play:.2f}"
    )


@pytest.mark.parametrize("latch", [True, False])
def test_the_latch_leaves_no_height_at_which_the_hook_comes_off(latch: bool) -> None:
    """Die Zusage der Rastzunge, in einem Satz: **es gibt keine solche Höhe.**

    Ein Einhänger löst sich, indem man ihn anhebt, bis die Nase frei ist, und
    dann herauszieht. Beides zusammen ist eine einzige Frage an die Geometrie:
    Gibt es eine Höhe, bei der alles hinter der Platte durch den Schlitz
    zurückpasst? Ohne Zunge gibt es sie — sonst ließe sich das Teil gar nicht
    erst einhängen. Mit Zunge darf es sie nicht geben, in **keiner** Höhe.

    Gemessen wird an der Richtung und nicht nur an der Berührung
    (``.claude/rules/bausteine.md``): Die Rastschulter muss am **oberen** Ende
    sitzen, dort, wo der Haken beim Anheben hinwandert. Eine gleich große
    Schulter am unteren Ende sperrte nichts — sie wanderte beim Anheben in den
    Schlitz hinein.
    """
    spec = PARTS.get("pegboard_hook")
    values = spec.params(count=1, latch=latch)
    built = spec.fn(values)
    board = standards.board(values.system)

    dahinter = behind_the_board(built, board)
    assert len(dahinter), "nothing reaches behind the board at all"
    passend = slot_heights(dahinter, board)

    if not latch:
        assert passend, (
            "without the latch the hook must come out again — otherwise it could "
            "never have gone in, and this test would prove nothing"
        )
        return

    assert not passend, (
        f"the latched hook slips back through the slot at {len(passend)} heights, "
        f"first at {passend[:1]}"
    )

    # Die Richtung: Die Sperre sitzt oben. Der höchste Punkt hinter der Platte
    # liegt über dem, was im Brett steckt — die Schulter steht also dorthin
    # hinaus, wo der Haken beim Anheben hinwill.
    im_schlitz = through_the_board(built, board)
    assert float(dahinter[:, 1].min()) < float(im_schlitz[:, 1].min()) - 0.3, (
        f"the shoulder sits at y={dahinter[:, 1].min():.2f} and the shank reaches to "
        f"{im_schlitz[:, 1].min():.2f} — it does not stand out at the top end"
    )
    # Und unten steht sie nicht über: Dort greift die Nase, und mehr braucht
    # es nicht.
    assert float(dahinter[:, 1].max()) == pytest.approx(
        float(spec.fn(spec.params(count=1, latch=False)).mesh.bounds.maximum[1]), abs=0.01
    ), "the latch changed the lower end of the hook, where the nose already holds"


def test_the_latched_hook_still_goes_into_the_slot() -> None:
    """Eine Verriegelung, die das Einhängen verhindert, ist keine.

    Der Querschnitt im Brett — Zapfen und Zunge nebeneinander — muss durch das
    Loch gehen, und zwar bei einer Höhe, bei der auch die Nase hindurchkommt.
    Die Zunge selbst federt dabei ein; **hier** wird gemessen, dass sie das
    ohne die Schulter überhaupt tun könnte: Was im Brett liegt, ist die
    eingefederte Gestalt.
    """
    spec = PARTS.get("pegboard_hook")
    for play in (0.0, 0.2, 1.5):
        values = spec.params(count=1, play=play)
        built = spec.fn(values)
        board = standards.board(values.system)
        im_schlitz = through_the_board(built, board)
        assert slot_heights(im_schlitz, board), (
            f"play={play}: shank and tongue together measure "
            f"{np.ptp(im_schlitz[:, 0]):.2f} by {np.ptp(im_schlitz[:, 1]):.2f} mm and fit "
            f"no {board.slot_width} by {board.slot_height} slot"
        )


def test_the_tongue_has_room_to_spring() -> None:
    """Eine Zunge ohne Spalt ist ein Vorsprung, kein Federarm.

    Sie muss um ihre Rastschulter ausweichen können, sonst kommt der Haken
    nicht durch den Schlitz. Gemessen am Schnitt durch den Arm: der freie
    Abstand zwischen Zunge und Zapfen gegen den Überstand der Schulter, den der
    Hüllquader verrät.
    """
    spec = PARTS.get("pegboard_hook")
    board = standards.board("skadis")

    for play, plate, lip in ((0.0, 0.0, 0.0), (1.5, 0.0, 6.0), (0.0, 10.0, 0.0)):
        values = spec.params(count=1, play=play, plate=plate, lip=lip)
        built = spec.fn(values)
        step = shoulder_step(built, board)
        gap = spring_gap(built.mesh, board.thickness / 2.0)
        assert gap >= step > 0.2, (
            f"play={play} plate={plate} lip={lip}: the shoulder stands {step:.2f} mm proud "
            f"and the tongue has {gap:.2f} mm to give way"
        )


def test_the_tongue_stays_under_the_strain_a_printed_arm_survives() -> None:
    """Der Federweg kommt aus dem Arm, in dem er entsteht — nachgerechnet.

    Für einen Rechteckquerschnitt ist die Randdehnung an der Wurzel
    ``ε = 3·t·δ/(2·L²)``. Alle drei Größen stehen am gebauten Körper: die
    Armstärke als Dicke der Zunge, der Federweg als Überstand der Schulter, die
    freie Länge als der Bereich, in dem Zunge und Zapfen zwei getrennte Umrisse
    sind. Was herauskommt, muss unter ``LATCH_STRAIN`` bleiben — sonst bricht
    der Arm beim ersten Einrasten, und der Baustein verspricht etwas, das er
    nicht hält.

    **Nicht mit der Formel des Bausteins gerechnet.** Die Erwartung kommt aus
    der Biegemechanik und die Messwerte aus dem Netz; wer den Sollwert aus dem
    Prüfling zöge, prüfte die Aktualität der Formel und nicht ihre Richtigkeit.
    """
    from app.core.knowledge.parts.mounting import LATCH_STRAIN

    spec = PARTS.get("pegboard_hook")
    board = standards.board("skadis")
    values = spec.params(count=1)
    built = spec.fn(values)

    step = shoulder_step(built, board)
    schulter = float(behind_the_board(built, board)[:, 2].min())
    hoehen = np.arange(0.05, schulter, 0.05)
    frei = [float(z) for z in hoehen if loose_at(built.mesh, float(z))]
    assert frei, "the tongue is fused to the shank over its whole length"
    length = schulter - frei[0]

    cut = built.mesh.raw.section(
        plane_origin=[0.0, 0.0, frei[len(frei) // 2]], plane_normal=[0.0, 0.0, 1.0]
    )
    umriss = min(cut.discrete, key=lambda ring: np.asarray(ring)[:, 1].min())
    thickness = float(np.ptp(np.asarray(umriss)[:, 1]))

    strain = 3.0 * thickness * step / (2.0 * length**2)
    assert strain <= LATCH_STRAIN, (
        f"the tongue is {thickness:.2f} mm thick, {length:.2f} mm long and has to give "
        f"way {step:.2f} mm — that is {strain * 100:.1f} % strain at the root"
    )
    # Und nicht beliebig weich: Ein Arm, der zehnmal so lang ist wie nötig,
    # federt nicht mehr zurück. Ein Zehntel der zulässigen Dehnung wäre einer.
    assert strain > LATCH_STRAIN / 10.0, (
        f"only {strain * 100:.2f} % strain — this arm is a flag, not a spring"
    )


@pytest.mark.parametrize("values", corners(PARTS.get("pegboard_hook")), ids=str)
def test_the_latched_hook_holds_over_the_whole_range(values: dict[str, Any]) -> None:
    """§24.3 für die Zunge: jede Ecke des Bereichs, Zunge eingeschaltet.

    Der Bereichstest der Datei fährt die Ecken zyklisch, und ein Schalter
    bekommt dabei abwechselnd beide Stellungen — die Ecke mit dem größten Spiel
    und der tiefsten Nase liefe also ohne Zunge. Hier wird sie eingeschaltet
    erzwungen: Was an den Rändern bricht, bricht nicht in der Mitte.
    """
    spec = PARTS.get("pegboard_hook")
    board = standards.board("skadis")
    werte = spec.params(**{**values, "latch": True})
    built = spec.fn(werte)
    mesh = built.mesh

    assert mesh.is_watertight, f"{values} is not watertight"
    assert mesh.volume > 0.0, f"{values} has no volume"
    # Ein Haken je Zapfen, und die Zunge gehört zu ihrem: mehr Teile hieße,
    # sie hängt an nichts. Mit Rückplatte sind es keine zwei mehr — die Platte
    # verbindet, wozu sonst der Träger da ist.
    erwartet = 1 if werte.plate > 0.0 else werte.count
    assert mesh.component_count == erwartet, (
        f"{values} falls into {mesh.component_count} pieces, expected {erwartet}"
    )
    assert sorted(built.features) == sorted(
        [f"hook_{i + 1}" for i in range(werte.count)]
        + [f"latch_{i + 1}" for i in range(werte.count)]
    ), f"{values} names {sorted(built.features)}"

    dahinter = behind_the_board(built, board)
    assert not slot_heights(dahinter, board), f"{values}: the latched hook slips back out"


def test_without_the_latch_the_hook_is_the_shape_it_was() -> None:
    """Abgeschaltet muss die alte Form herauskommen, aufs Zehntel.

    §24.4 lebt davon, dass ein alter Stand erreichbar bleibt: Wer die Meldung
    beim Öffnen liest und lieber weiterrechnet wie bisher, schaltet die Zunge
    ab. Die Maße stehen hier aus der Tabelle und der Aufteilung des Docstrings
    — halbe Schlitzhöhe Zapfen, ein Viertel Nase, ein Viertel Weg —, nicht aus
    dem Baustein.
    """
    spec = PARTS.get("pegboard_hook")
    board = standards.board("skadis")
    values = spec.params(count=1, latch=False)
    built = spec.fn(values)

    lip = board.thickness * (2.0 / 3.0)
    hoch = board.slot_height * 3.0 / 4.0
    size = built.mesh.bounds.size
    assert float(size[0]) == pytest.approx(board.slot_width, abs=0.01)
    # Die runden Enden eines Langlochs sind ein Vieleck; dessen äußerster Punkt
    # liegt ein Hundertstel innerhalb der Rundung.
    assert float(size[1]) == pytest.approx(hoch, abs=0.02)
    assert float(size[2]) == pytest.approx(board.thickness + lip, abs=0.02)
    assert sorted(built.features) == ["hook_1"], "a hook without a latch names no latch"


def test_the_hook_names_its_features_on_faces_that_exist() -> None:
    """Ein Merkmal mitten im Material ist kein Anhaltspunkt.

    ``hook_1`` lag auf der Höhe der Plattenrückseite und damit **im** Zapfen:
    gemessen zu 99 % innen, mit der Fläche eines Rechtecks, das der Haken gar
    nicht hat. Derselbe Fehler wie beim Plattenmerkmal, das aus demselben Grund
    verschwunden ist — und keine Kennzahl des Bereichstests bemerkt ihn.

    Gemessen wird mit einem kleinen Würfel um den Mittelpunkt: halb im
    Material heißt „auf einer Fläche", ganz im Material heißt „daneben
    gegriffen". Dazu die Richtung — einen halben Millimeter in Richtung der
    Normalen muss Luft sein.
    """
    spec = PARTS.get("pegboard_hook")
    built = spec.fn(spec.params(count=1))
    mesh = built.mesh

    for name, feature in built.features.items():
        centre = np.asarray(feature.params["centre"], dtype=float)
        normal = np.asarray(feature.params["normal"], dtype=float)
        anteil = solid_fraction(mesh, centre)
        assert 0.2 < anteil < 0.8, (
            f"{name} sits {anteil * 100:.0f} % inside the body — that is not a face"
        )
        draussen = solid_fraction(mesh, centre + 0.5 * normal, size=0.2)
        assert draussen < 0.2, f"{name} points into the material, not out of it"


def test_a_board_without_room_for_a_tongue_says_so() -> None:
    """Regel 21: wo es nicht geht, wird es gesagt — nicht halb gebaut.

    Die Tabelle führt heute eine einzige Lochwand, und in deren Schlitz ist
    reichlich Platz. Eine Zeile mehr ist eine Datenänderung, keine
    Codeänderung: Sie käme ohne Test durch und ergäbe eine Zunge, die keinen
    Federweg hat. Der Baustein hält dann an und nennt den Ausweg — die Zunge
    abzuschalten —, statt einen Vorsprung zu bauen, der sich nicht eindrücken
    lässt.
    """
    from app.core.errors import ValidationError

    spec = PARTS.get("pegboard_hook")
    eng = standards.Board(size="eng", slot_width=4.0, slot_height=6.0, pitch=20.0, thickness=3.0)

    with mock.patch.object(standards, "board", return_value=eng):
        with pytest.raises(ValidationError) as gefangen:
            spec.fn(spec.params(count=1))
        # Ohne Zunge geht dieselbe Lochwand durch — sonst wäre die Meldung ein
        # Rat ins Leere.
        assert spec.fn(spec.params(count=1, latch=False)).mesh.is_watertight

    assert gefangen.value.suggestions, "Regel 17: eine Ausnahme ohne Handlungsvorschlag"


def test_the_two_changed_parts_report_themselves_to_old_projects() -> None:
    """§24.4: wer die Maße ändert, sagt es den Projekten, die sie benutzt haben.

    Beide Änderungen des 25.08.2026 verschieben Maße — der Einhänger um seine
    Zunge, das Schlüsselloch um das Kopfspiel, das es wieder addiert statt
    ersetzt. Ein Projekt, das mit Bibliotheksstand 6 gerechnet wurde, muss
    beide genannt bekommen.
    """
    from app.core.knowledge.parts.registry import changed_since_library

    gemeldet = changed_since_library("6", ["pegboard_hook", "keyhole", "wall_mount"])
    assert set(gemeldet) == {"pegboard_hook", "keyhole"}, gemeldet

    # **Und zwar jede der beiden Änderungen einzeln.** Gegen 6 gefragt genügt
    # dem Einhänger sein älterer Eintrag; die Zunge wäre dabei stumm geblieben,
    # und die Gegenprobe hat genau das gezeigt: Der Test blieb grün, als ihr
    # Eintrag entwertet wurde. Gefragt wird deshalb gegen den Stand unmittelbar
    # davor — dort spricht nur noch der jüngste Eintrag. Der Stand kommt aus der
    # Version des Einhängers selbst, nicht aus ``LIBRARY_VERSION``: sobald ein
    # späterer Baustein die Bibliothek weiterschiebt (die Kopffreiheit auf 9),
    # ist der Zungen-Eintrag nicht mehr der jüngste der Bibliothek, wohl aber
    # der des Einhängers.
    vorher = str(int(PARTS.get("pegboard_hook").version) - 1)
    assert changed_since_library(vorher, ["pegboard_hook"]) == ("pegboard_hook",), (
        f"a project computed at library {vorher} is never told the hook grew a latch"
    )


def test_additional_size_fields_do_not_claim_that_old_geometry_changed() -> None:
    """Neue optionale Eingaben sind kein Maßwechsel für bestehende Projekte."""
    from app.core.knowledge.parts.registry import changed_since_library

    unchanged = ["cable_clip", "cable_gland", "magnet_pocket"]
    assert changed_since_library("11", unchanged) == ()
    assert changed_since_library("11", ["screw_hole"]) == ("screw_hole",)


@pytest.mark.parametrize("size", ["M3", "M4", "M6"])
def test_the_keyhole_head_falls_through_with_a_profile(size: str, profile: Profile) -> None:
    """Der Kopf soll hindurchfallen — auch mit unkalibriertem Material.

    **Er tat es nicht.** Version 6 schrieb ``params.play or HEAD_CLEARANCE``,
    und ``ops.insert`` füllt das Spiel bei *jedem* Profil aus dem Material ein,
    nicht erst bei einem kalibrierten. Damit ersetzte ein Spiel von 0,25 mm das
    Durchgangsmaß von 0,6: Ein M4-Kopf von 7,00 mm fand eine Öffnung von
    7,25 mm vor, und gedruckt geht er da nicht mehr durch.

    Gemessen wird auf dem Weg, den die Anwendung geht — mit den Werten, die
    ``insert_part`` dem Baustein reicht —, und nicht mit einer eigenen
    Nachbildung davon.
    """
    spec = PARTS.get("keyhole")
    werte = part_ops._part_values(spec, spec.params(size=size), profile)
    built = spec.fn(spec.params(**werte))
    screw = standards.screw(size)

    from app.core.knowledge.parts.mounting import HEAD_CLEARANCE

    weite = float(built.features["pocket_1"].params["diameter"])
    assert weite >= screw.head + HEAD_CLEARANCE, (
        f"{size}: the head is {screw.head} mm and the opening {weite} mm — printed it "
        "no longer goes through"
    )
    assert weite == pytest.approx(screw.head + HEAD_CLEARANCE + profile.material.clearance)


def test_a_part_may_declare_how_many_bodies_it_prints_as(profile: Profile) -> None:
    """Print-in-place: mehrere Körper, aber nur so viele wie erklärt (§24.3).

    Ein Scharnier, das schon beim Drucken beweglich ist, besteht aus zwei
    Teilen. Der Bereichstest verlangte `component_count == 1` — und die
    Einteiligkeit steht nicht im Bauplan: §24.3 nennt wasserdicht,
    Mindestwandstärke, keine Selbstdurchdringung, benannte Merkmale. Der Test
    hatte sie hinzugefügt, aus gutem Anlass (die Rastnase zerfiel, weil sie
    die Fläche nur berührte). Gemeint war „zerfällt nicht **versehentlich**".

    Entschieden am 25.08.2026 (Robert): Deklaration statt stiller Ausnahme.
    Der Unterschied ist der ganze Punkt — die Prüfung wird nicht schwächer,
    sondern genauer: Zwei statt zwei ist die Zusage, drei statt zwei fällt.
    """
    from types import SimpleNamespace

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.knowledge.parts.range_check import check
    from app.core.registry import op_params, param
    from app.core.types import BaseParams

    @op_params
    class TwoPartParams(BaseParams):
        size: float = param(title="Maß", default=10.0, unit="mm", minimum=8.0, maximum=12.0)

    def two_bodies(values: BaseParams) -> Any:
        """Zwei getrennte Würfel — ein Gelenk im Kleinen."""
        left = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
        right = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
        right.apply_translation((10.0, 0.0, 0.0))
        return SimpleNamespace(mesh=MeshData.of(trimesh.util.concatenate([left, right])))

    declared = check(TwoPartParams, two_bodies, profile, bodies=2)
    assert declared.passed, [entry.reason for entry in declared.failures]

    # Die Gegenprobe, und sie ist der Punkt: Ohne Deklaration ist derselbe
    # Baustein ein Fehler — unerklärtes Zerfallen bleibt rot.
    undeclared = check(TwoPartParams, two_bodies, profile)
    assert not undeclared.passed
    assert "2 Teile statt 1" in undeclared.failures[0].reason


def test_a_printed_joint_needs_a_gap_the_printer_can_hold(profile: Profile) -> None:
    """Bei einem print-in-place-Teil ist der Spalt die ganze Sache.

    Zu eng verschweißt beim Drucken, und aus zwei Körpern wird einer — davon
    sähe der Bereichstest nichts, weil er die Geometrie **vor** dem Drucker
    prüft. Gemessen wird deshalb der engste Abstand zwischen den Teilen, gegen
    das kalibrierte Material und nie gegen eine Zahl im Code (Regel 7).

    Die Toleranz ist `EPS_DISPLAY` und nicht `EPS_GEOM`: eine Fertigungsfrage,
    kein Rechenvergleich. Ein facettierter Zylinder zeigt seine Sehne und nicht
    den Bogen, der gemessene Spalt fällt also um Bruchteile kleiner aus —
    0,2499 bei eingestellten 0,25. Mit dem Rechenepsilon meldete die Prüfung
    ein Scharnier, das genau richtig gebaut war.
    """
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts.range_check import check
    from app.core.registry import op_params, param
    from app.core.types import BaseParams

    hinge = PARTS.get("barrel_hinge")

    # So, wie der Kunde es bekommt: `play` bleibt null, der Bereichstest setzt
    # den Profilwert ein — wie `insert_part` es tut.
    assert check(hinge.params, hinge.fn, profile, bodies=hinge.bodies).passed

    @op_params
    class TooTight(BaseParams):
        pin: float = param(title="Bolzen", default=4.0, unit="mm", minimum=3.0, maximum=5.0)

    def built_too_tight(values: BaseParams) -> Any:
        """Dasselbe Scharnier, aber mit einem Spiel, das nicht aus dem Profil kommt."""
        return hinge.fn(hinge.params(pin=values.pin, play=0.05))

    tight = check(TooTight, built_too_tight, profile, bodies=2)
    assert not tight.passed, "ein Spalt von 0,05 mm verschweißt beim Drucken"
    assert "0.05" in tight.failures[0].reason


#: Was ein Messschieber an einer echten SKÅDIS-Platte hergibt.
#:
#: Erste Messung am 27.08.2026 (Alexander Schneider): Schlitzbreite 4,9 bis
#: 5,1 mm, Schlitzhöhe 14,9 bis 15,1 mm. Die **Nennmaße** der Tabelle sind
#: damit bestätigt — neu ist die Toleranz, die keine Zeichnung hergibt.
#:
#: Hier steht die **untere** Grenze, denn nur sie kann klemmen. Wer die Zahl
#: ändert, hat gemessen; wer sie ohne Messung ändert, verschiebt eine Zusage
#: ins Blaue.
NARROWEST_MEASURED_SLOT = 4.9
NARROWEST_MEASURED_SLOT_HEIGHT = 14.9


@pytest.mark.parametrize("material", ["pla", "petg", "abs", "tpu-95a"])
def test_the_hook_still_fits_the_narrowest_slot_that_was_measured(material: str) -> None:
    """Ein Teil, das in neun von zehn Platten passt, ist kaputt.

    Die Tabelle führt Nennmaße: 5,0 × 15,0. Eine echte Platte hält sie nicht
    auf den Hundertstel — gemessen wurden 4,9 bis 5,1 und 14,9 bis 15,1. Für
    den Einhänger zählt allein das **untere** Ende: Ein Zapfen, der genau
    5,0 misst, geht in einen 4,9er Schlitz nicht hinein.

    Getragen wird das vom Spiel aus dem Materialprofil (Regel 7), und dieser
    Test hält fest, dass es dafür reicht — in **jedem** Material, nicht nur in
    dem, mit dem gerade jemand gedruckt hat. Am knappsten wird es bei PLA, das
    das kleinste Spiel führt: dort bleiben 0,10 mm.

    Ohne diese Zusage wäre die Toleranz eine Notiz in einer Tabelle, die
    niemand nachrechnet — und die erste Platte, die 0,05 mm enger ausfällt,
    fiele beim Kunden auf statt hier.
    """
    from app.core.knowledge import standards
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.profiles import material_profiles

    board = standards.board("skadis")
    spiel = material_profiles()[material].clearance

    # Dieselbe Rechnung wie im Baustein; ``play`` kommt bei null aus dem
    # Profil (``parts/ops.py``, ``PLAY_FIELD``).
    zapfen = board.slot_width - spiel
    nutzbar = board.slot_height - spiel

    assert zapfen <= NARROWEST_MEASURED_SLOT, (
        f"{material}: Zapfen {zapfen:.2f} mm passt nicht in den engsten "
        f"gemessenen Schlitz ({NARROWEST_MEASURED_SLOT} mm)"
    )
    assert nutzbar <= NARROWEST_MEASURED_SLOT_HEIGHT, (
        f"{material}: {nutzbar:.2f} mm Weg passt nicht in die engste "
        f"gemessene Schlitzhöhe ({NARROWEST_MEASURED_SLOT_HEIGHT} mm)"
    )

    # Und die Gegenprobe zur Zusage selbst: Der Baustein baut wirklich mit
    # diesem Maß, statt dass hier eine Formel neben ihm herrechnet.
    #
    # **Ein einzelner Haken, und nur seine Breite.** Zwei Haken stehen im
    # Rasterabstand, ihr Hüllquader misst 44,75 mm — das ist 40 plus eine
    # Zapfenbreite und sagt nichts über die Passung. Und gemessen wird X:
    # In der Höhe ragt die federnde Rastzunge absichtlich über den Zapfen
    # hinaus, sie liegt *vor* der Platte. Was durch den Schlitz muss, prüft
    # der Test darüber (``goes_through_the_slot_and_catches_behind_it``).
    spec = PARTS.get("pegboard_hook")
    gebaut = spec.fn(spec.params(count=1, play=spiel))
    breite = gebaut.mesh.bounds.size[0]
    assert breite <= NARROWEST_MEASURED_SLOT + 1e-6, (
        f"{material}: gebauter Zapfen ist {breite:.2f} mm breit und passt nicht "
        f"in den engsten gemessenen Schlitz ({NARROWEST_MEASURED_SLOT} mm)"
    )
