"""Die Bausteinbibliothek (Bauplan §24).

§24.3 setzt die Latte: jeder Baustein wird über seinen gesamten
Parameterbereich gerechnet — wasserdicht, Mindestwandstärke, keine
Selbstdurchdringung an den Grenzen, Merkmale richtig benannt. **Ein Baustein
ohne diesen Test gilt als nicht vorhanden.** Also ist der Bereichstest über das
Register parametrisiert: ein neuer Baustein ist abgedeckt, sobald er deklariert
ist, und ein Baustein, der an seinen eigenen Grenzen scheitert, scheitert hier.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.knowledge import standards
from app.core.knowledge.parts import LIBRARY_VERSION, PARTS, changed_since, missing_parts
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
    Zustände jedes Schalters.
    """
    entries = spec.params.spec()
    combinations: list[dict[str, Any]] = [{}]
    for entry in entries:
        values: list[Any] = []
        if entry.kind == "enum":
            values = list(entry.choices)
        elif entry.kind == "bool":
            values = [True, False]
        elif entry.kind in ("float", "int"):
            values = [entry.minimum, entry.maximum, entry.default]
            values = [value for value in values if value is not None]
        if not values:
            continue
        combinations = [{**base, entry.name: value} for base in combinations for value in values]
        # Endlich halten: die Ecken jedes Parameters, nicht jedes Produkt.
        if len(combinations) > 24:
            combinations = combinations[:24]
    return combinations


# --- the library ------------------------------------------------------------------


def test_the_library_has_the_first_set_from_the_plan() -> None:
    """§24.1 nennt dreizehn Bausteine für die erste Auslieferung.

    Die Kalibrierkörper aus §28.3 sind auch Bausteine, gehören aber nicht zu
    diesem Satz — sie sind Werkzeuge für den Drucker, nicht für das Modell, und
    sie haben ihre eigene Gruppe im Katalog.
    """
    building = [spec for spec in PARTS.all() if spec.group != "calibration"]

    assert len(building) == 13
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


# --- the standard table ------------------------------------------------------------


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
