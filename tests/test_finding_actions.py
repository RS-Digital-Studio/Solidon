"""Ein Knopf am Befund tut, was er sagt — am Weg des Kunden geprüft.

Die Durchsicht 0.5.1 gab rund dreißig Warnungen eine Handlung (Regel 17,
RM-215), die meisten *Eingabe korrigieren*. Der Knopf öffnet den Schritt des
Befunds (``MainWindow._correct_after_error`` über ``edit_operation``) — und tut
nichts, wenn der Befund keine Schrittkennung trägt. Die Operationen setzen sie
nicht selbst; die Auswertung trägt sie an jedem Befund eines Schritts nach
(``evaluate``: „Ein Befund, der seine Kennung selbst mitbringt, behält sie").
Dieser Test hält beides fest: dass Kennung und Körper ankommen, und dass der
Bericht eine Handlung, die sie braucht, ohne sie gar nicht erst anbietet.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from app.core.errors import CORRECT_INPUT, SHOW_SUPPORT_NEED
from app.core.geom import mesh_ops
from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY, Registry
from app.core.scene import ResultCache, evaluate
from app.core.types import (
    Document,
    Finding,
    OpContext,
    Operation,
    OpResult,
    Profile,
    SceneObject,
)

MESHES = Path(__file__).parent / "data" / "meshes"


def _cube() -> object:
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


def _plate() -> object:
    return normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh


def _evaluated(profile: Profile, mesh: object, op: str, params: dict[str, object]):
    """Ein Körper aus einem Erzeuger, dann genau der Schritt, dessen Befund gefragt ist."""

    def make(ctx: OpContext) -> OpResult:
        return OpResult(outputs=[SceneObject(id="", name="Teil", mesh=mesh)])

    registry = Registry()
    registry.register(dataclasses.replace(REGISTRY.get("create_box"), fn=make, cache_version="t"))
    registry.register(REGISTRY.get(op))
    document = Document(
        format_version=1,
        app_version="0.0.1",
        ops=[
            Operation(id=1, op="create_box", outputs=["obj_1"], params={}),
            Operation(id=2, op=op, inputs=["obj_1"], outputs=["obj_1"], params=params),
        ],
    )
    return evaluate(document, profile, registry=registry, cache=ResultCache())


def _only(result, code: str) -> Finding:
    found = [entry for entry in result.scene.report.findings if entry.code == code]
    assert found, [entry.code for entry in result.scene.report.findings]
    return found[0]


def test_every_finding_of_a_step_carries_its_step_and_body(profile: Profile) -> None:
    """Die Zusage, auf der jeder Knopf *Eingabe korrigieren* steht.

    Eine Operation gibt Befunde ohne Kennung zurück — sie kennt ihren Schritt
    nicht. Kommt der Befund ohne sie im Bericht an, öffnet der Knopf nichts.
    """
    mesh = _cube()

    def warns(ctx: OpContext) -> OpResult:
        return OpResult(
            outputs=[dataclasses.replace(ctx.inputs[0], id="")],
            findings=[
                Finding(
                    code="probe.warns",
                    severity="warning",
                    message="—",
                    suggestions=(CORRECT_INPUT, SHOW_SUPPORT_NEED),
                )
            ],
        )

    registry = Registry()
    registry.register(
        dataclasses.replace(
            REGISTRY.get("create_box"),
            fn=lambda ctx: OpResult(outputs=[SceneObject(id="", name="Teil", mesh=mesh)]),
            cache_version="t",
        )
    )
    registry.register(
        dataclasses.replace(REGISTRY.get("translate_object"), fn=warns, cache_version="t")
    )
    document = Document(
        format_version=1,
        app_version="0.0.1",
        ops=[
            Operation(id=1, op="create_box", outputs=["obj_1"], params={}),
            Operation(id=2, op="translate_object", inputs=["obj_1"], outputs=["obj_1"], params={}),
        ],
    )
    result = evaluate(document, profile, registry=registry, cache=ResultCache())

    probe = _only(result, "probe.warns")
    assert probe.op_id == 2, "ohne Schrittkennung öffnet *Eingabe korrigieren* nichts"
    assert probe.object_id == "obj_1", "ohne Körper fiele *Stützbedarf zeigen* auf die Auswahl"


@pytest.mark.parametrize(
    ("mesh", "op", "params", "code"),
    [
        # Die Bohrung über die Kante (Stellvertreter der Bohrungswarnungen).
        (
            _cube,
            "drill_hole",
            {"diameter": 6.0, "axis": "z", "x": 15.0, "y": 0.0, "z": 30.0},
            "bore.over_the_edge",
        ),
        # Aushöhlen mit einer Wand, die keinen Hohlraum lässt.
        (_cube, "hollow_object", {"wall": 14.0}, "hollow.too_thin"),
    ],
)
def test_a_warning_with_correct_input_opens_its_own_step(
    profile: Profile, mesh, op: str, params: dict[str, object], code: str
) -> None:
    """Am echten Schritt: Befund, Handlung und Kennung kommen zusammen an."""
    result = _evaluated(profile, mesh(), op, params)

    finding = _only(result, code)
    assert CORRECT_INPUT in finding.suggestions, finding.suggestions
    assert finding.op_id == 2


def test_a_dense_remesh_opens_the_edge_length(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Satz nennt die Kantenlänge, und der Schritt geht mit dem Cursor dort auf."""
    monkeypatch.setattr(mesh_ops, "DENSE_FACTOR", 2)
    result = _evaluated(profile, _plate(), "remesh_mesh", {"edge": 5.0})

    finding = _only(result, "mesh.remesh_dense")
    assert finding.op_id == 2
    assert finding.values["field"] == "edge"


def test_the_report_offers_no_step_action_without_a_step() -> None:
    """Dieselbe Schranke wie im Fehlerdialog (``dialogs.NEEDS_OP``).

    Ein Befund ohne Schritt — aus der Übergabe an den Slicer, aus der
    Druckanalyse — bekommt *Eingabe korrigieren* nicht angeboten, und ein
    Befund ohne Körper nicht *Stützbedarf zeigen*: Beides wäre ein Knopf,
    der nichts tut oder am falschen Körper.
    """
    from app.ui.panels import actions_for_document

    loose = Finding(
        code="probe.loose",
        severity="warning",
        message="—",
        suggestions=(CORRECT_INPUT, SHOW_SUPPORT_NEED),
    )
    anchored = dataclasses.replace(loose, op_id=2, object_id="obj_1")

    assert [action.id for action in actions_for_document(loose, None)] == []
    assert [action.id for action in actions_for_document(anchored, None)] == [
        CORRECT_INPUT.id,
        SHOW_SUPPORT_NEED.id,
    ]


def test_a_smoothing_that_cost_too_much_offers_the_refinement_before_it() -> None:
    """„Erst neu vernetzen, dann glätten." ist seit der Durchsicht 0.5.1 ein Knopf.

    ``mesh.smooth_shrank`` steht an einem Schritt, der durchlief; das Verfeinern
    gehört **davor**, wie die Reparatur vor einen gerundeten Schritt. Angeboten
    nur mit der durchgespielten Länge und nur an einem Schritt, der im Verlauf
    steht und vorhandene Netze liest.
    """
    from app.core.errors import REMESH_AND_RETRY
    from app.ui.panels import actions_for_document

    document = Document(
        format_version=1,
        app_version="0.0.1",
        ops=[
            Operation(id=1, op="create_box", outputs=["obj_1"], params={}),
            Operation(
                id=2,
                op="smooth_mesh",
                inputs=["obj_1"],
                outputs=["obj_1"],
                params={"iterations": 5},
            ),
        ],
    )
    shrank = Finding(
        code="mesh.smooth_shrank",
        severity="warning",
        message="—",
        op_id=2,
        object_id="obj_1",
        values={"remesh_to_mm": 10.0},
        suggestions=(REMESH_AND_RETRY,),
    )

    def offered(finding: Finding) -> list[str]:
        return [action.id for action in actions_for_document(finding, document)]

    assert REMESH_AND_RETRY.id in offered(shrank)
    assert REMESH_AND_RETRY.id not in offered(dataclasses.replace(shrank, values={}))
    assert REMESH_AND_RETRY.id not in offered(dataclasses.replace(shrank, op_id=9))


def test_every_finding_with_correct_input_comes_from_an_operation() -> None:
    """*Eingabe korrigieren* nur an Befunden, die eine Operation zurückgibt.

    Befunde aus der Slicer-Übergabe, der Druckanalyse oder dem Einlesen
    entstehen außerhalb eines Schritts; die Auswertung kann ihnen keine
    Kennung nachtragen. Dort wäre der Knopf wirkungslos — der Bericht blendet
    ihn zwar aus (Test darüber), aber dann bliebe der Befund ohne Weg.
    """
    import app.core

    outside = ("slice/", "export/", "agent/")
    wrong: list[str] = []
    root = Path(app.core.__file__).parent
    for path in root.rglob("*.py"):
        name = path.relative_to(root).as_posix()
        if not name.startswith(outside):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Finding"
            ):
                continue
            for keyword in node.keywords:
                if keyword.arg == "suggestions" and "CORRECT_INPUT" in ast.unparse(keyword.value):
                    wrong.append(f"{name}:{node.lineno}")
    assert not wrong, "Eingabe korrigieren ohne Schritt: " + ", ".join(wrong)


def test_the_stages_tried_read_as_words() -> None:
    """„Versuchte Rechenwege: ['direct', 'welded']" stand im Fehlerdialog (KUNDE-10)."""
    from app.ui.labels import value_text

    shown = value_text("attempted", ["direct", "welded"])
    assert "[" not in shown and "direct" not in shown, shown
    assert shown == "direkt gerechnet, mit zusammengeführten Punkten gerechnet"


def _split_document() -> Document:
    """Laden, dann *Teilen*: ``obj_1`` ist verbraucht, ``obj_2`` und ``obj_3`` stehen."""
    return Document(
        format_version=1,
        app_version="0.0.1",
        ops=[
            Operation(id=1, op="load", outputs=["obj_1"], params={"source": "src_1"}),
            Operation(id=2, op="repair", inputs=["obj_1"], outputs=["obj_1"], params={}),
            Operation(
                id=3,
                op="split_pinned",
                inputs=["obj_1"],
                outputs=["obj_2", "obj_3"],
                params={"axis": "z", "position": 10.0},
            ),
        ],
    )


def test_a_consumed_body_offers_nothing_that_needs_it() -> None:
    """RM-268: Nach *Modell teilen* stand am Laptopständer „Das Modell besteht aus
    21 Teilen …“ am verbrauchten ``obj_1`` — mit *Überschneidungen auflösen* und
    *In Einzelteile zerlegen*; ein Klick legte eine Reparatur an einem Körper an,
    den es nicht mehr gibt
    (``konzepte/nachweise-release-0.5.1/sonden/rest-kunde/s268_laptop.txt``).

    Weggelassen wird jede Handlung, die den Körper des Befunds braucht
    (``panels.NEEDS_LIVE_BODY``); was ohne ihn gilt — den Schritt ändern, die
    ganze Szene anordnen —, bleibt. Am lebenden Körper steht alles da.
    """
    from types import SimpleNamespace

    from app.core import errors
    from app.ui.panels import NEEDS_LIVE_BODY, actions_for_document

    document = _split_document()
    needing = tuple(
        action
        for action in vars(errors).values()
        if isinstance(action, errors.Action) and action.id in NEEDS_LIVE_BODY
    )
    assert {action.id for action in needing} == NEEDS_LIVE_BODY, "jede Kennung ist eine Handlung"
    keeping = (errors.ARRANGE_ON_BED, errors.CORRECT_INPUT, errors.LEAVE_OPEN)
    finding = Finding(
        code="ingest.multiple_components",
        severity="info",
        message="—",
        op_id=1,
        object_id="obj_1",
        values={"components": 21, "feature_ids": ("f1",)},
        location=(0.0, 0.0, 0.0),
        suggestions=(*needing, *keeping),
    )
    mesh = SimpleNamespace(kind="mesh")
    gone = {"obj_2": mesh, "obj_3": mesh}
    alive = {"obj_1": mesh}

    def offered(entry: Finding, live: dict[str, object]) -> set[str]:
        return {
            action.id
            for action in actions_for_document(entry, document, live_objects=live)  # type: ignore[arg-type]
        }

    assert offered(finding, gone) == {action.id for action in keeping}
    for action in (errors.RESOLVE_INTERSECTIONS, errors.SPLIT_BODIES, errors.GIVE_THICKNESS):
        assert action.id in offered(finding, alive), action.id

    # *Überschneidungen auflösen* an einem Reparaturschritt ändert diesen Schritt
    # (``MainWindow._resolve_intersections_after_error``) — das gilt ohne Körper.
    at_repair = dataclasses.replace(
        finding, op_id=2, suggestions=(errors.RESOLVE_INTERSECTIONS, errors.SPLIT_BODIES)
    )
    assert offered(at_repair, gone) == {errors.RESOLVE_INTERSECTIONS.id}


def test_every_handler_that_reads_the_body_of_a_finding_is_listed() -> None:
    """Die eine Quelle bleibt vollständig: Liest ein Handler am Fenster den
    Körper des Befunds (``_object_of``, ``_entry_of``, ``error.object_id``), steht
    seine Kennung in ``NEEDS_LIVE_BODY`` — oder hier mit Grund daneben."""
    import app.ui.main_window as main_window
    from app.ui.panels import NEEDS_LIVE_BODY

    # Eigene Schranke oder bewusst ohne lebenden Körper:
    reasoned = {
        # ``repair_is_available`` fragt Körper und Schritt selbst (``live_objects``).
        "repair_and_retry",
        # Die Wahl steht am Ladeschritt; ein verbrauchter Körper behält sie
        # (``panels._recognition_reopenable``, Review 24.09.2026).
        "recognize_fully",
        # Setzt das Verfeinern vor den Schritt, solange er im Verlauf steht —
        # das gilt ohne den Körper; ohne Schritt nimmt es ``actions_for_document``
        # schon heraus (``repair_is_available`` mit dem Schritt des Befunds).
        "remesh_and_retry",
    }
    tree = ast.parse(Path(main_window.__file__).read_text(encoding="utf-8"))
    window = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
    )
    methods = {node.name: node for node in window.body if isinstance(node, ast.FunctionDef)}
    table = next(
        node
        for node in ast.walk(methods["error_handlers"])
        if isinstance(node, ast.Dict) and len(node.keys) > 20
    )

    def reads_the_body(node: ast.AST) -> bool:
        for inner in ast.walk(node):
            if isinstance(inner, ast.Attribute) and inner.attr in {"_object_of", "_entry_of"}:
                return True
            if (
                isinstance(inner, ast.Attribute)
                and inner.attr == "object_id"
                and isinstance(inner.value, ast.Name)
                and inner.value.id == "error"
            ):
                return True
        return False

    missing = []
    for key, value in zip(table.keys, table.values, strict=True):
        if key is None:
            continue  # ``**{...}`` der Schreibfehler: Wiederholen, anderer Ort
        assert isinstance(key, ast.Constant)
        body: ast.AST = value
        if isinstance(value, ast.Attribute) and value.attr in methods:
            body = methods[value.attr]
        if reads_the_body(body) and key.value not in NEEDS_LIVE_BODY | reasoned:
            missing.append(key.value)
    assert not missing, missing


def _run(op: str, entry: SceneObject, profile: Profile, **params: object) -> OpResult:
    """Eine Operation so fahren, wie die Auswertung sie fährt — ohne Stapel."""
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import Scene

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


def _change_step(finding: Finding) -> list[str]:
    """Die Beschriftungen der Handlung, die den Schritt des Befunds öffnet."""
    from app.ui.panels import actions_for_document

    return [
        str(action.label)
        for action in actions_for_document(finding, None)
        if action.id == "change_step"
    ]


@pytest.mark.parametrize(
    ("op", "params", "code", "label", "field"),
    [
        # Weg 3: der Generatorwürfel auf 100 mm, und der kürzeste Weg zum
        # gemeinten Maß ist der Schritt selbst (RM-374).
        ("fit_to_size", {"largest": 50.0}, "transform.fitted", "Größe ändern", "largest"),
        # Die Vorgabe des Dialogs übernommen: Der Körper steht, wo er stand.
        ("translate_object", {}, "transform.without_effect", "Diesen Schritt ändern", None),
        # Ob die Wand trägt, entscheidet der Kunde am Befund (RM-441).
        ("hollow_object", {"wall": 3.0}, "hollow.done", "Diesen Schritt ändern", "wall"),
    ],
)
def test_a_finding_about_what_a_step_did_opens_that_step(
    profile: Profile, op: str, params: dict[str, object], code: str, label: str, field: str | None
) -> None:
    """RM-374: Ein Befund, der einen änderbaren Schritt meint, trägt den Knopf,
    der genau diesen Schritt zum Ändern öffnet — mit dem Cursor im Feld, um
    das es geht (``values["field"]``, wie bei *Eingabe korrigieren*)."""
    from app.ui.dialogs import NEEDS_OP

    result = _evaluated(profile, _cube(), op, params)

    finding = _only(result, code)
    assert finding.op_id == 2, "ohne Schritt öffnet der Knopf nichts"
    assert _change_step(finding) == [label]
    assert finding.values.get("field") == field
    assert "change_step" in NEEDS_OP, "ohne Schrittkennung wird der Knopf nicht angeboten"
    loose = dataclasses.replace(finding, op_id=None)
    assert _change_step(loose) == [], "ohne Schritt kein Knopf"


def test_a_filled_lattice_offers_its_cell_size(profile: Profile) -> None:
    """Der dritte Befund derselben Art: „Der Hohlraum trägt jetzt eine
    Gitterstruktur.“ — der Wert, nach dem man danach fragt, ist die Zellgröße."""
    import trimesh

    from app.core.geom.hollow import hollow
    from app.core.geom.mesh import MeshData

    body = trimesh.creation.box(extents=(40.0, 40.0, 40.0))
    body.apply_translation((0.0, 0.0, 20.0))
    hollowed = hollow(MeshData.of(body), 3.0, vents=1).mesh
    entry = SceneObject(id="obj_1", name="Dose", mesh=hollowed)

    result = _run("lattice_fill", entry, profile, structure="cubic", cell=8.0, wall=1.2)

    filled = next(finding for finding in result.findings if finding.code == "lattice.filled")
    attached = dataclasses.replace(filled, op_id=2, object_id="obj_1")
    assert _change_step(attached) == ["Zellgröße ändern"]
    assert filled.values.get("field") == "cell"
