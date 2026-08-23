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
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from app.core.geom.boolean import boolean
from app.core.knowledge import standards
from app.core.knowledge.parts import LIBRARY_VERSION, PARTS, changed_since, missing_parts, shapes
from app.core.knowledge.parts import ops as part_ops
from app.core.knowledge.parts.registry import PartRegistry, PartSpec, register_part
from app.core.registry import REGISTRY, op_params, param
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import BaseParams, PartResult, Profile, Source

MESHES = Path(__file__).parent / "data" / "meshes"


def ids(spec: PartSpec) -> str:
    return spec.name


def corners(spec: PartSpec) -> list[dict[str, Any]]:
    """Der Parameterbereich als die Werte, die ein Baustein überstehen muss.

    Kein Durchlauf über alles — die Ecken sind, wo ein Baustein bricht: der
    kleinste und der größte Wert jeder Zahl, jede Wahl jedes Enums, beide
    Zustände jedes Schalters. **Jeder davon kommt mindestens einmal vor**, und
    genau darum geht es hier.

    **Was das Produkt mit einer Obergrenze anrichtet.** Hier stand ein
    kartesisches Produkt, nach jedem Parameter auf die ersten
    vierundzwanzig Einträge gekürzt. Vom vierten Parameter an gewinnt dieser
    Schnitt: Die ersten vierundzwanzig von zweiundsiebzig tragen alle den
    ersten Wert der früheren Parameter, und mit jedem weiteren verengt es sich.
    Gezählt am 21.08.2026 hatten **siebzehn von achtzehn** Bausteinen Ecken,
    die nie gefahren wurden — bei nut_trap, screw_hole,
    printed_thread und keyhole alle Normgrößen außer einer. Die
    Mutternfalle ist der meistbenutzte Baustein der Bibliothek, und geprüft
    war eine Größe von sechs.

    Nachgemessen wurde auch, was das gekostet hat: Die neunundfünfzig
    fehlenden Kombinationen einmal von Hand gefahren, keine davon fehlerhaft.
    Der Fund war eine Lücke in der Prüfung, kein Schaden am Modell — und ein
    Baustein, der morgen geändert wird, hätte sie gefunden.

    Statt des Produkts deshalb: so viele Kombinationen wie die längste
    Werteliste, jede Liste zyklisch durchgezählt. Damit kommt jeder Wert jedes
    Parameters vor, und der Lauf wird **kürzer** statt länger. Was diese Form
    nicht prüft, ist das Zusammenspiel zweier Extreme; dafür wäre das Produkt
    nötig, und das ist bei zwölf Parametern kein Test mehr, sondern ein
    Nachmittag.
    """
    entries = spec.params.spec()
    lists: dict[str, list[Any]] = {}
    for entry in entries:
        values: list[Any] = []
        if entry.kind == "enum":
            values = list(entry.choices)
        elif entry.kind == "bool":
            values = [True, False]
        elif entry.kind in ("float", "int"):
            values = [entry.minimum, entry.maximum, entry.default]
            values = [value for value in values if value is not None]
        if values:
            lists[entry.name] = values
    if not lists:
        return [{}]
    longest = max(len(values) for values in lists.values())
    return [
        {name: values[index % len(values)] for name, values in lists.items()}
        for index in range(longest)
    ]


# --- die Bibliothek ---------------------------------------------------------------


def test_the_library_has_the_first_set_from_the_plan() -> None:
    """§24.1 nennt dreizehn Bausteine für die erste Auslieferung, dazu einen.

    Die Kalibrierkörper aus §28.3 sind auch Bausteine, gehören aber nicht zu
    diesem Satz — sie sind Werkzeuge für den Drucker, nicht für das Modell, und
    sie haben ihre eigene Gruppe im Katalog.

    **Zwei stehen nicht in der Erstbestückung**, und beide sind eine Ansage und
    kein Versehen. Wer die Zahl hier ändert, ändert die Bibliothek, und das soll
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
    """
    building = [spec for spec in PARTS.all() if spec.group != "calibration"]

    assert len(building) == 15
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


SUBTRACTIVE = [spec for spec in PARTS.all() if spec.subtractive]


@pytest.mark.parametrize("spec", SUBTRACTIVE, ids=ids)
def test_a_subtractive_part_reaches_into_the_material(spec: PartSpec) -> None:
    """§24.1: der Ursprung ist die Mündung, das Werkzeug geht nach unten.

    Wer eine Fläche anklickt, bekommt ihre Höhe in die Position eingetragen.
    Ein Werkzeug, das von dort nach *oben* wächst, steht in der Luft und trägt
    nichts ab — genau das taten Magnettasche, Schlüsselloch und
    Kabeldurchführung, bis die Bibliothek auf Version 2 ging.

    Gemessen wird an der Wirkung, nicht an den Koordinaten: der Baustein sitzt
    auf der Oberseite einer Platte, und danach hat sie weniger Volumen.
    """
    plate = shapes.box(60.0, 60.0, 20.0)
    tool = shapes.moved(spec.fn(spec.params()).mesh, (0.0, 0.0, 20.0))
    cut = boolean("difference", [plate, tool])

    assert cut.mesh.volume < plate.volume - 1.0, (
        f"{spec.name} trägt an der angeklickten Fläche nichts ab"
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
    for name, seit in (("dowel", "2"), ("snap_connector", "4")):
        spec = PARTS.get(name)
        assert spec.version == seit, name
        letzte = spec.changes[-1]
        assert letzte.version == seit and letzte.effect, name
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
    [
        "insert_screw_hole",
        "insert_nut_trap",
        "insert_printed_thread",
        "insert_snap_fit",
        "insert_latch",
        "insert_living_hinge",
        "insert_keyhole",
        "insert_wall_mount",
        "insert_cable_gland",
        "insert_snap_connector",
    ],
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


@pytest.mark.parametrize(
    "name",
    ["insert_latch", "insert_rib", "insert_snap_fit", "insert_wall_mount", "insert_overhang_fan"],
)
def test_an_added_part_grows_together_with_the_body(name: str, profile: Profile) -> None:
    """Ein aufgesetzter Baustein muss **ein** Körper mit seinem Träger werden.

    Die Rastnase wurde es nicht: sie sitzt mit 6 × 1 mm auf der Fläche auf, und
    zwei Volumen, die sich nur in einer Fläche berühren, sind das eine, woran
    eine boolesche Operation zuverlässig scheitert (§39). Heraus kam ein
    wasserdichtes Netz aus zwei Komponenten — beim nächsten Bohren waren es
    drei. Die breiteren Bausteine fielen nie auf, weil manifold sie verschmolz.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    History(project.document).apply(
        name,
        [OperationDraft(op=name, inputs=("obj_1",), params={"at_feature": "face_top"})],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    body = result.scene.objects["obj_1"].mesh
    assert body.component_count == 1, name
    assert body.is_watertight, name


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
