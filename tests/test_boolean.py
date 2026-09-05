"""Die Boolesche Rückfallkette (Bauplan §17.2, §35).

Jede Stufe wird einmal erzwungen, damit keine von ihnen still verrottet: die
Kette lohnt nur, wenn Stufe 4 an dem Tag noch funktioniert, an dem Stufe 1
aufgibt.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import BooleanFailedError, GeometryError
from app.core.geom.attributes import used_slots, with_slot
from app.core.geom.boolean import DRAFT_CHAIN, FULL_CHAIN, boolean, shared_volume
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.knowledge import profiles
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import MaterialSlot, OpContext, OpResult, Scene, SceneObject

MESHES = Path(__file__).parent / "data" / "meshes"


def solid(name: str = "cube_clean.stl") -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def box(size: float, offset: tuple[float, float, float]) -> MeshData:
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_translation(offset)
    return MeshData.of(body)


def run_op(
    op: str,
    first: MeshData,
    second: MeshData,
    *,
    first_slots: tuple[MaterialSlot, ...] = (),
    second_slots: tuple[MaterialSlot, ...] = (),
) -> OpResult:
    """Eine boolesche Operation über das Register fahren — mit Profil, damit
    ``without_effect`` an der Düse misst und nicht am Rechenepsilon."""
    load_operations()
    spec = REGISTRY.get(op)
    a = SceneObject(id="obj_1", name="A", mesh=first, material_slots=list(first_slots))
    b = SceneObject(id="obj_2", name="B", mesh=second, material_slots=list(second_slots))
    return spec.fn(
        OpContext(
            scene=Scene(objects={"obj_1": a, "obj_2": b}, parameters={}),
            inputs=[a, b],
            params=spec.params(),
            profile=profiles.make_profile(),
            quality="fine",
            seed=0,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_union_of_two_overlapping_cubes() -> None:
    result = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.solver.strategy == "direct"
    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(12000.0, rel=1e-6), "8000 + 8000 - 4000 overlap"
    assert not result.findings, "the plain case has nothing to report"


def test_difference_removes_the_overlap() -> None:
    result = boolean("difference", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.mesh.volume == pytest.approx(4000.0, rel=1e-6)
    assert result.solver.strategy == "direct"


def test_intersection_keeps_only_the_overlap() -> None:
    result = boolean("intersection", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.mesh.volume == pytest.approx(4000.0, rel=1e-6)


def test_union_keeps_the_filament_descriptions_of_both_bodies() -> None:
    """Die Flächen trugen beide Slotnummern, aber der zweite Name und seine
    Farbe verschwanden am Operationsrand — die Ansicht und der 3MF-Export
    konnten die korrekt übertragene Nummer dadurch nicht mehr erklären.
    """
    white = MaterialSlot(index=0, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    black = MaterialSlot(index=1, name="PLA Schwarz", colour=(0.05, 0.05, 0.05))

    result = run_op(
        "union_objects",
        with_slot(solid(), 0),
        with_slot(box(20.0, (10.0, 0.0, 0.0)), 1),
        first_slots=(white,),
        second_slots=(black,),
    )

    output = result.outputs[0]
    assert used_slots(output.mesh) == (0, 1), "die Geometrie trägt beide Filamente"
    assert output.material_slots == [white, black], "Name und Farbe erklären beide Nummern"


def test_the_stage_that_worked_is_recorded() -> None:
    """§17.2: die erfolgreiche Stufe wird in die Operation geschrieben."""
    result = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.solver.attempted == ("direct",)
    assert result.solver.seed is None


@pytest.mark.parametrize("stage", ["welded", "jittered", "voxel"])
def test_every_stage_can_carry_the_operation_alone(stage: str) -> None:
    """§35: jede Stufe einmal erzwungen — eine Kette, die niemand übt, ist
    eine Kette, die verrottet.
    """
    result = boolean(
        "union",
        [solid(), box(20.0, (10.0, 0.0, 0.0))],
        seed=20260728,
        stages=(stage,),  # type: ignore[arg-type]
    )

    assert result.solver.strategy == stage
    assert result.mesh.triangle_count > 0
    # Jitter bewegt Eckpunkte, Voxel runden auf ein Raster — beide tauschen
    # Genauigkeit gegen eine Antwort, und genau dafür sind die späteren Stufen
    # da (§17.2).
    tolerance = {"welded": 1e-6, "jittered": 1e-3, "voxel": 0.05}[stage]
    assert result.mesh.volume == pytest.approx(12000.0, rel=tolerance)


def test_the_voxel_stage_says_that_it_rounded() -> None:
    """§17.3: Stufe 4 kostet Genauigkeit und wird nie stillschweigend benutzt."""
    result = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], stages=("voxel",))

    codes = {finding.code for finding in result.findings}
    assert "boolean.voxel" in codes
    assert any(finding.severity == "warning" for finding in result.findings)


def test_the_jitter_stage_carries_its_seed() -> None:
    """§11.3: ohne gespeicherten Startwert wäre das Ergebnis nicht
    reproduzierbar.
    """
    first = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], seed=42, stages=("jittered",))
    second = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], seed=42, stages=("jittered",))

    assert first.solver.seed == 42
    assert first.mesh.volume == pytest.approx(second.mesh.volume, rel=1e-12)


def test_draft_quality_stops_after_the_second_stage() -> None:
    """§31: das Iterieren bleibt schnell, der Entwurf gibt also keine Zeit für
    Voxel aus.
    """
    assert DRAFT_CHAIN == ("direct", "welded")
    assert FULL_CHAIN[:2] == DRAFT_CHAIN
    assert "voxel" in FULL_CHAIN and "voxel" not in DRAFT_CHAIN


def test_an_impossible_operation_ends_with_a_finding_and_a_way_forward() -> None:
    """§17.2 Stufe 5: aufgeben ist erlaubt, still aufgeben nicht."""
    with pytest.raises(BooleanFailedError) as caught:
        boolean(
            "intersection",
            [solid(), box(2.0, (500.0, 0.0, 0.0))],
            stages=("direct", "welded"),
        )

    assert caught.value.attempted == ("direct", "welded")
    assert caught.value.suggestions, "an error without a way forward is unfinished"


def test_at_least_two_bodies_are_needed() -> None:
    with pytest.raises(ValueError):
        boolean("union", [solid()])


# --- as operations --------------------------------------------------------------


def two_body_document(document, profile):
    """Zwei überlappende Würfel in einem Dokument, bereit für eine Boolesche
    Operation.
    """
    from app.core.registry import REGISTRY
    from app.core.scene import History, OperationDraft
    from app.core.scene.project import new_project
    from app.core.types import Source
    from app.i18n import _

    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    for index, name in enumerate(("cube_clean.stl", "cube_clean.stl"), start=1):
        document.sources[f"src_{index}"] = Source(
            id=f"src_{index}", kind="import", path=f"sources/{index}_{name}", sha256=""
        )
        project.sources[f"src_{index}"] = (MESHES / name).read_bytes()

    history = History(document)
    history.apply(
        _("Laden"),
        [
            OperationDraft(op="load", params={"source": "src_1", "unit": "mm"}),
            OperationDraft(op="load", params={"source": "src_2", "unit": "mm"}),
        ],
    )
    history.apply(
        _("Verschieben"),
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": 10.0})],
    )
    assert REGISTRY.has("union_objects")
    return project, history


def test_a_boolean_operation_records_its_stage(document, profile) -> None:
    """§17.2: die Stufe, die die Operation getragen hat, wird in den Stapel
    geschrieben.
    """
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.project import ProjectSources
    from app.i18n import _

    project, history = two_body_document(document, profile)
    history.apply(
        _("Vereinigen"),
        [OperationDraft(op="union_objects", inputs=("obj_1", "obj_2"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    # Zwei Körper hinein, einer heraus — und der eine ist der **erste**: Das
    # Vereinigen setzt fort, was der Nutzer zuerst angeklickt hat, mit seiner
    # Kennung, seinem Namen und seinem Material (``keeps_inputs=1``). Der
    # zweite ist verbraucht.
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(12000.0, rel=1e-6)
    assert "obj_2" not in result.scene.objects, "der zweite Körper ist aufgegangen"

    union_op = history.operations[-1]
    assert union_op.seed is not None, "a randomised operation carries a seed (§11.3)"
    assert result.solvers[union_op.id].strategy == "direct"

    history.record_solvers(result.solvers)
    assert history.operation(union_op.id).solver is not None
    assert history.operation(union_op.id).solver.strategy == "direct"


def test_subtracting_and_intersecting_run_as_operations(document, profile) -> None:
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.project import ProjectSources
    from app.i18n import _

    project, history = two_body_document(document, profile)
    history.apply(
        _("Abziehen"),
        [OperationDraft(op="subtract_objects", inputs=("obj_1", "obj_2"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(4000.0, rel=1e-6)
    assert "obj_2" not in result.scene.objects, "both inputs were consumed"


def test_intersect_objects_runs_as_an_operation(document, profile) -> None:
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.project import ProjectSources
    from app.i18n import _

    project, history = two_body_document(document, profile)
    history.apply(
        _("Schnittmenge"),
        [OperationDraft(op="intersect_objects", inputs=("obj_1", "obj_2"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))
    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(4000.0, rel=1e-6)


# --- Eine boolesche Op, die nichts bewirkt, sagt das (§2.7, operationen.md) ------


def test_subtracting_a_body_that_does_not_touch_says_so() -> None:
    """„Wer Boolesches rechnet, fragt danach — ohne Ausnahme." Ein Abzugskörper
    weit neben dem Teil trägt nichts ab, und das stand nirgends: ein Schritt im
    Verlauf, dasselbe Teil im Bild."""
    result = run_op("subtract_objects", solid(), box(20.0, (100.0, 0.0, 0.0)))

    assert result.outputs[0].mesh.volume == pytest.approx(8000.0, rel=1e-6)
    assert "boolean.without_effect" in [finding.code for finding in result.findings]


def test_a_union_that_adds_nothing_says_so() -> None:
    """Ein Körper, der ganz im anderen steckt, fügt der Vereinigung nichts
    hinzu — dieselbe Auskunft, andersherum."""
    result = run_op("union_objects", solid(), box(4.0, (0.0, 0.0, 0.0)))

    assert result.outputs[0].mesh.volume == pytest.approx(8000.0, rel=1e-6)
    assert "boolean.without_effect" in [finding.code for finding in result.findings]


def test_an_intersection_of_two_separate_bodies_says_it_is_empty() -> None:
    """Zwei Körper, die sich nicht treffen, haben keine Schnittmenge. Statt die
    ganze Rückfallkette bis zur Voxelstufe zu fahren und dann „das Werkzeug
    deckt ihn vollständig ab" zu melden, hält die Operation sofort an und nennt
    den zutreffenden Grund."""
    with pytest.raises(GeometryError) as problem:
        run_op("intersect_objects", solid(), box(20.0, (100.0, 0.0, 0.0)))

    assert problem.value.suggestions, "Regel 17: der Fehler nennt einen Weg"
    said = f"{problem.value.title} {problem.value.detail}"
    assert "gemeinsam" in said.lower(), "der zutreffende Grund, nicht der der Vereinigung"
    assert "deckt" not in said, "nicht die alte, falsche Begründung aus der Rückfallkette"


# --- Ein falscher Aufruf ist keine Antwort (§33.1) -------------------------------


def test_a_wrong_call_into_the_kernel_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Lektion der konvexen Zerlegung, dort festgehalten, wo es geht.

    Handler um einen Kern fangen breit, denn ein Kern scheitert auf Kernarten,
    und das ist eine Antwort. Ein TypeError ist keine: er heißt, dass der
    Aufruf falsch ist, und ihn zu verschlucken macht aus einem Fehler ein leeres
    Ergebnis. Die Zerlegung aus §22.3 tat genau das, zwei Phasen lang, hinter
    einer grünen Suite.
    """

    def wrong(*_args: object, **_kwargs: object) -> None:
        raise TypeError("intersection(): incompatible function arguments")

    monkeypatch.setattr(trimesh.boolean, "intersection", wrong)

    with pytest.raises(TypeError):
        shared_volume(solid().raw, solid().raw)


def test_the_fallback_chain_does_not_swallow_a_wrong_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dieselbe Regel eine Ebene höher — dort, wo sie am meisten verdeckt.

    ``shared_volume`` ließ Programmfehler durch, die Rückfallkette nicht: Sie
    fing jede Ausnahme, notierte „Stufe gescheitert" ins Protokoll und probierte
    die nächste. Ein falscher Aufruf sah damit aus wie vier Kerne, die nacheinander
    aufgeben — und der Nutzer las am Ende, seine Geometrie sei schuld.

    Die Stufen rufen mit eigenen Argumenten (``voxelized(pitch=...)``,
    ``matrix_to_marching_cubes(matrix=..., pitch=...)``), also gilt hier genau
    die Vorsichtsmaßnahme, die ``errors.PROGRAMMING_ERRORS`` beschreibt.
    """

    def wrong(*_args: object, **_kwargs: object) -> None:
        raise TypeError("union(): incompatible function arguments")

    monkeypatch.setattr(trimesh.boolean, "union", wrong)

    with pytest.raises(TypeError):
        boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))])


def test_a_kernel_that_gives_up_is_still_an_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die andere Hälfte der Regel: wofür der Handler wirklich da ist, bleibt
    gefangen.
    """

    def gave_up(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("manifold: could not solve")

    monkeypatch.setattr(trimesh.boolean, "intersection", gave_up)

    assert shared_volume(solid().raw, solid().raw) == 0.0


def test_an_emptied_body_says_so_instead_of_blaming_the_solver() -> None:
    """Kein Rückfall hilft gegen Maße.

    Eine Bohrung mit 200 mm Durchmesser in einer 80er Platte frisst sie ganz.
    Vier Stufen liefen durch, und der Nutzer las am Ende „Auch die letzte
    Rückfallstufe hat kein brauchbares Ergebnis geliefert" — die Sprache des
    Rechenkerns für etwas, das aus den Maßen folgt, und ohne den
    Handlungsvorschlag, den Regel 17 verlangt.
    """
    plate = MeshData.of(trimesh.creation.box(extents=(80.0, 50.0, 8.0)))
    tool = MeshData.of(trimesh.creation.box(extents=(300.0, 300.0, 300.0)))

    with pytest.raises(BooleanFailedError) as caught:
        boolean("difference", [plate, tool])

    detail = str(caught.value.detail)
    assert "bleibt nichts übrig" in detail, "der Satz sagt, was zu sehen wäre"
    assert "Rückfallstufe" not in detail, "und nicht, woran der Kern gescheitert ist"
    assert any(action.id == "correct_input" for action in caught.value.suggestions), (
        "die Handlung ist nachrechnen, nicht reparieren"
    )
    # **Und der Titel dazu.** Er blieb der Vorgabetitel der Klasse — „Die
    # boolesche Operation ist auf allen Stufen gescheitert." — und stand damit
    # über einem Detailsatz, der das Gegenteil sagt. Der Dialog zeichnet den
    # Titel groß und das Detail klein: Wer hinsieht, liest zuerst, der Kern sei
    # gescheitert, und sucht einen Netzfehler statt einer falschen Zahl.
    title = str(caught.value.title)
    assert "gescheitert" not in title, f"der Titel widerspricht seinem eigenen Detail: {title!r}"
    assert "kein Körper" in title, title


def test_a_cancelled_chain_stops_before_the_first_stage() -> None:
    """§15.6: Vier Kernversuche plus Voxelisierung an einem großen Netz waren
    als Ganzes unabbrechbar — das Token wird jetzt zwischen den Stufen
    gefragt, und der Abbruch ist eine ``OperationCancelled``, kein Befund."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], cancelled=signal)


def test_a_boolean_keeps_the_feature_names_where_they_were(document, profile) -> None:
    """Ein Bohrungsname zeigt nach dem Abziehen auf dieselbe Bohrung wie davor.

    **Das war der teuerste Teil des Kennungsfehlers, und er ist kein
    Anzeigefehler.** Die Merkmale des Vorgängers hängen an seiner
    Eingangskennung; bekam der Ausgang eine frische, griff die Zuordnung ins
    Leere und vergab die Namen neu — nach Lage sortiert. Eine Senkung oder ein
    Gewinde, das an ``hole_1`` hängt, sitzt danach am falschen Loch, und
    gemeldet wird nichts (§21.2).

    **Der Aufbau muss die Sortierung kippen lassen, sonst prüft er nichts.**
    Der erste Anlauf verschob das Werkzeug so, dass die Reihenfolge gleich
    blieb — der Test war grün, auch ohne die Deklaration. Hier wandert das
    Werkzeug von der einen Seite des gebohrten Lochs auf die andere: Ohne
    ``keeps_inputs`` trägt danach ein anderes Loch den Namen ``hole_1``.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft, evaluate
    from app.i18n import _

    load_operations()
    history = History(document)
    history.apply(
        _("Platte"),
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 80.0, "height": 10.0})],
    )
    history.apply(
        _("Loch"),
        [
            OperationDraft(
                op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "x": 0.0, "y": 0.0}
            )
        ],
    )
    history.apply(_("Werkzeug"), [OperationDraft(op="create_cylinder", params={"diameter": 5.0})])
    tool = document.ops[-1].outputs[0]
    history.apply(
        _("Setzen"),
        [
            OperationDraft(
                op="translate_object",
                inputs=(tool,),
                params={"dx": -25.0, "dy": -25.0, "dz": -5.0},
            )
        ],
    )
    history.apply(
        _("Abziehen"), [OperationDraft(op="subtract_objects", inputs=("obj_1", tool), params={})]
    )

    def holes() -> dict[str, tuple[float, float]]:
        found: dict[str, tuple[float, float]] = {}
        for entry in evaluate(document, profile).scene.objects.values():
            for name, feature in entry.features.items():
                centre = feature.params.get("centre") if feature.kind == "hole" else None
                if centre:
                    found[name] = (round(float(centre[0]), 1), round(float(centre[1]), 1))
        return found

    before = holes()
    assert len(before) == 2, f"der Aufbau braucht zwei Bohrungen, hat aber {before}"
    drilled = next(name for name, place in before.items() if place == (0.0, 0.0))

    # Das Werkzeug wandert auf die andere Seite — die Sortierung kippt.
    moved = next(entry for entry in history.operations if entry.op == "translate_object")
    history.change_params(moved.id, {"dx": 25.0, "dy": 25.0, "dz": -5.0})
    after = holes()

    assert after[drilled] == (0.0, 0.0), (
        f"{drilled} zeigt jetzt auf eine andere Bohrung: {before} -> {after}"
    )


@pytest.mark.parametrize("overlap", [0.05, 0.01, 0.001, 0.0])
def test_coplanar_faces_survive_every_overlap(overlap: float) -> None:
    """Die Zugabe schützt vor einem Bruch, den dieser Kern nicht mehr hat.

    ``BOOLEAN_OVERLAP`` stand an drei Stellen mit zwei Werten — zuletzt sogar
    zweimal unter demselben Namen (``geom/boolean.py`` 0,05,
    ``geom/prepare.py`` 0,01), beide importiert. Damit hing es am Importpfad,
    welche Zugabe eine Operation bekam.

    Die Messung hat die Frage verschoben: nicht „welcher Wert ist richtig",
    sondern „wirkt der Wert überhaupt". Drei koplanare Lagen, jede mit vier
    Zugaben bis hinunter zu **null** — alle über Stufe 1, alle wasserdicht,
    alle mit exaktem Volumen. ``manifold3d`` ist feste Abhängigkeit und rechnet
    zusammenfallende Flächen robust.

    Der Test hält diese Aussage fest, damit die eine Zahl nicht wieder zu
    zweien wird: Wer sie ändert, ändert nichts an der Rechnung — und wer sie
    verdoppelt, hat keinen Grund dafür.
    """
    plate = MeshData.of(trimesh.creation.box(extents=[40, 30, 10]))

    through = trimesh.creation.box(extents=[10, 10, 10 + overlap])
    through.apply_translation([0, 0, overlap / 2])
    on_top = trimesh.creation.box(extents=[8, 8, 4 + overlap])
    on_top.apply_translation([0, 0, 5 + (4 - overlap) / 2])
    at_the_side = trimesh.creation.box(extents=[10 + overlap, 8, 4])
    at_the_side.apply_translation([20 - (10 - overlap) / 2, 0, 0])

    for kind, tool, expected in (
        ("difference", through, 11000.0),
        ("union", on_top, 12256.0),
        ("difference", at_the_side, 11680.0),
    ):
        outcome = boolean(kind, [plate, MeshData.of(tool)], quality="fine")
        assert outcome.solver.strategy == "direct", (
            f"{kind} mit {overlap} mm Zugabe fiel auf {outcome.solver.strategy} zurück"
        )
        assert outcome.mesh.is_watertight, f"{kind} mit {overlap} mm ließ ein offenes Netz"
        assert outcome.mesh.volume == pytest.approx(expected, abs=0.5), (
            f"{kind} mit {overlap} mm: {outcome.mesh.volume:.1f} statt {expected}"
        )


def test_the_overlap_is_one_number_for_the_whole_core() -> None:
    """Wer die Zugabe braucht, importiert sie — er schreibt sie nicht ab.

    Drei Stellen trugen sie einmal, und zwei davon unter demselben Namen mit
    verschiedenen Zahlen. Am Namen sah man den Unterschied nicht; am Ergebnis
    auch nicht, denn die Zugabe liegt außerhalb des Materials. Genau deshalb
    wäre es unbemerkt geblieben.
    """
    import ast
    from pathlib import Path as _Path

    core = _Path(__file__).resolve().parent.parent / "app" / "core"
    defined: list[str] = []
    for path in sorted(core.rglob("*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            names = [t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)]
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            if any(name in ("BOOLEAN_OVERLAP", "OVERLAP") for name in names):
                defined.append(path.name)
    assert defined == ["boolean.py"], f"die Zugabe steht an {len(defined)} Stellen: {defined}"


def test_an_empty_result_in_draft_quality_points_at_the_stages_left() -> None:
    """„Nichts übrig" ist keine Aussage über die Maße, solange Stufen offen sind.

    Der Test darüber gilt der **vollen** Kette, und dort stimmt der Satz. Im
    Fenster läuft die kurze (:data:`DRAFT_CHAIN`, §31), und dieselbe Handlung
    an demselben Körper endete dort mit „Prüfen Sie Maß und Lage" — ohne einen
    Weg weiter und mit einer Ursache, die es nicht war.

    Gemessen am Mast des Piratenschiffs (``obj_1_Cylinder.stl``, Ø 5 auf
    115 mm, 04.09.2026): ``resize_feature`` liefert über *direkt* und
    *verschweißt* nichts, und die dritte Stufe löst es (Befund
    ``boolean.jittered``). In feiner Qualität bekam der Kunde sein Ergebnis, in
    Entwurfsqualität eine Absage — dieselbe Datei, derselbe Klick.
    """
    plate = MeshData.of(trimesh.creation.box(extents=(80.0, 50.0, 8.0)))
    tool = MeshData.of(trimesh.creation.box(extents=(300.0, 300.0, 300.0)))

    with pytest.raises(BooleanFailedError) as caught:
        boolean("difference", [plate, tool], quality="draft")

    detail = str(caught.value.detail)
    assert "Rechenstufen" in detail, f"der Satz nennt die offenen Stufen nicht: {detail!r}"
    assert "Maß und Lage" not in detail, (
        f"er behauptet weiter eine Ursache, die nicht feststeht: {detail!r}"
    )
    assert any(action.id == "use_voxel_stage" for action in caught.value.suggestions), (
        "der Weg zur vollständigen Kette fehlt — genau die Handlung, die hier hilft"
    )
    # Und der Titel kommt aus derselben Entscheidung wie die Handlung: Die
    # Ausnahme wählt ihn danach, ob die Voxelstufe dran war. Zwei Stellen für
    # dieselbe Frage liefen auseinander, sobald jemand eine davon ändert.
    assert "Vorschau" in str(caught.value.title), str(caught.value.title)


def test_the_voxel_stage_refuses_a_grid_it_cannot_afford(caplog: pytest.LogCaptureFixture) -> None:
    """Gesamtreview 05.09.2026, G-13: Die Rasterweite folgt der größten
    Einzeldiagonale, die Ausdehnung dem gemeinsamen Hüllquader. Zwei
    1-mm-Würfel, einer um (1000, 1000, 1000) verschoben, forderten bei 0,05 mm
    Rasterweite 20025³ Zellen an — acht Terabyte, ohne Budget vor
    ``np.zeros``. Die Stufe gibt jetzt auf, bevor sie allokiert."""
    from app.core.geom import boolean as boolean_module

    near = box(1.0, (0.0, 0.0, 0.0))
    far = box(1.0, (1000.0, 1000.0, 1000.0))

    with caplog.at_level("WARNING"):
        assert boolean_module._voxel("union", [near, far]) is None
    assert any("budget" in record.message for record in caplog.records)


def test_the_voxel_grid_of_a_difference_spans_only_the_body_that_shrinks() -> None:
    """Eine Differenz macht den ersten Körper nur kleiner: Das Werkzeug daneben
    braucht keine Zellen. Der ferne Würfel wird damit rechenbar, statt das
    Raster über tausend Millimeter Leere zu spannen."""
    from app.core.geom import boolean as boolean_module

    near = box(10.0, (0.0, 0.0, 0.0))
    far = box(1.0, (1000.0, 1000.0, 1000.0))

    result = boolean_module._voxel("difference", [near, far])

    assert result is not None
    assert result.volume == pytest.approx(near.volume, rel=0.05), "das ferne Werkzeug trifft nichts"
