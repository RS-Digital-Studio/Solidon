"""P2.8 — die Kernwahl-Haken sind gefallen (Konzept §10.1, Entscheidung 4 vom 17.09.2026).

Neue Grundkörper entstehen exakt, wo der exakte Kern da ist; gespeicherte
Schritte behalten ihren Kern; eine Bearbeitung fragt die Körperart ihres
Eingangs statt eines Hakens im Dialog; und der Wechsel in den anderen Kern
steht am Schritt im Verlauf.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.registry import (
    MENU_TWINS,
    PRIMITIVE_TWINS,
    REGISTRY,
    kernel_switch_label,
    kernel_twin_of,
    shown_of_twins,
)
from app.core.registry import registry as registry_module
from app.core.scene import ResultCache, evaluate
from app.core.scene.history import History, OperationDraft
from app.core.scene.placement import _creation_tool
from app.core.scene.project import new_project
from app.core.types import Profile
from tests.helpers import exact_kernel
from tests.helpers import run_operation as run


@pytest.fixture(autouse=True)
def _operations() -> None:
    load_operations()


def _kernel() -> None:
    exact_kernel()


def test_new_primitives_are_exact_where_the_kernel_is_present() -> None:
    """Sichtbar ist der exakte Erzeuger, versteckt der Netz-Zwilling — für alle sechs."""
    _kernel()
    for mesh, brep in PRIMITIVE_TWINS:
        assert MENU_TWINS[mesh] == brep, f"{mesh} ist nicht mehr der versteckte Zwilling"
        assert brep not in MENU_TWINS, f"{brep} steht versteckt statt sichtbar"
        shown = shown_of_twins([REGISTRY.get(mesh), REGISTRY.get(brep)])
        assert [spec.name for spec in shown] == [brep]
    # Bearbeitungen behalten ihre Richtung: der exakte Zwilling ist versteckt,
    # denn der sichtbare fragt die Körperart selbst.
    assert MENU_TWINS["drill_brep_hole"] == "drill_hole"
    assert MENU_TWINS["shell_exact"] == "hollow_object"


def test_without_the_kernel_the_mesh_creators_stay_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein erklärter verfügbarer Weg, kein stilles Scheitern (Konzept §10.1)."""
    monkeypatch.setattr(registry_module, "exact_kernel_present", lambda: False)
    # Die Antwort ist gemerkt (``functools.cache``) — für die Probe ohne Kern
    # einmal vergessen, und danach wieder, damit der nächste Test die echte sieht.
    registry_module.menu_twins.cache_clear()
    try:
        twins = registry_module.menu_twins()
        for mesh, brep in PRIMITIVE_TWINS:
            assert twins[brep] == mesh
            assert mesh not in twins
        assert twins["drill_brep_hole"] == "drill_hole"
    finally:
        registry_module.menu_twins.cache_clear()


def test_the_twin_is_found_in_both_directions_and_the_label_names_the_gain() -> None:
    _kernel()
    assert kernel_twin_of("create_box") == "create_brep_box"
    assert kernel_twin_of("create_brep_box") == "create_box"
    assert kernel_twin_of("drill_hole") == "drill_brep_hole"
    assert kernel_twin_of("fillet_edges") is None
    assert kernel_switch_label("fillet_edges") is None
    to_exact = str(kernel_switch_label("create_box"))
    to_mesh = str(kernel_switch_label("create_brep_box"))
    assert "Flächen und Kanten" in to_exact
    assert "Dreiecksmodell" in to_mesh
    # Bohren entscheidet der Körper selbst — kein Satz am Schritt.
    assert kernel_switch_label("drill_brep_hole") is None
    assert kernel_switch_label("hollow_object") is None
    for label in (to_exact, to_mesh):
        assert "B-Rep" not in label and "exakt" not in label.lower(), label


def _evaluated(profile: Profile, *drafts: OperationDraft) -> Any:
    document = new_project("centauri-carbon-2", "petg").document
    History(document).apply("Schritte", list(drafts))
    result = evaluate(document, profile, cache=ResultCache())
    assert result.stopped_at is None, result.stopped_at
    return result


def test_saved_steps_keep_their_kernel(profile: Profile) -> None:
    """Alte Projekte rechnen unverändert: ``create_box`` bleibt ein Netz."""
    _kernel()
    result = _evaluated(
        profile,
        OperationDraft(op="create_box", params={"width": 20.0, "depth": 16.0, "height": 10.0}),
        OperationDraft(op="create_brep_box", params={"width": 20.0, "depth": 16.0, "height": 10.0}),
    )
    assert result.scene.objects["obj_1"].kind == "mesh"
    assert result.scene.objects["obj_2"].kind == "brep"


def test_drilling_an_exact_body_stays_exact_without_a_toggle(profile: Profile) -> None:
    """*Bohrung setzen* — die eine sichtbare Operation — fragt die Körperart selbst."""
    _kernel()
    box = run("create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0).outputs[0]
    # Ohne Materialtoleranz, damit die Analytik das Nennmaß trifft.
    drilled = run(
        "drill_hole", box, profile, x=0.0, y=0.0, z=20.0, diameter=6.0, depth=10.0, compensate=False
    ).outputs[0]
    assert drilled.kind == "brep"
    assert any(feature.kind == "hole" for feature in drilled.features.values())
    assert float(drilled.mesh.volume) == pytest.approx(24000.0 - math.pi * 9.0 * 10.0, rel=1e-6)
    plate = run("create_box", None, profile, width=40.0, depth=30.0, height=20.0).outputs[0]
    meshed = run("drill_hole", plate, profile, x=0.0, y=0.0, z=20.0, diameter=6.0, depth=10.0)
    assert meshed.outputs[0].kind == "mesh"


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"open_top": True, "vents": 0}, "brep"),
        ({"open_top": True, "vents": 2}, "brep"),
        ({"open_top": False, "vents": 0}, "mesh"),
        ({"open_top": True, "vents": 0, "open_at": "face_1"}, "mesh"),
    ],
)
def test_hollowing_follows_the_table(
    profile: Profile, params: dict[str, Any], expected: str
) -> None:
    """Konzept §10.1: Oberseite offen bleibt exakt, sonst der Netzweg.

    Eine Entlüftung zählt bei offener Oberseite nicht — die offene Dose braucht
    keine, und das Feld steht dann nicht da (Durchsicht 0.5.3, Fund 2).
    """
    _kernel()
    result = _evaluated(
        profile,
        OperationDraft(op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 20.0}),
        OperationDraft(op="hollow_object", inputs=("obj_1",), params={"wall": 2.0, **params}),
    )
    body = result.scene.objects["obj_1"]
    assert body.kind == expected
    assert float(body.mesh.volume) < 24000.0
    codes = {finding.code for finding in result.scene.report.findings}
    assert ("evaluate.exact_became_mesh" in codes) == (expected == "mesh")


def test_a_saved_conversion_after_an_open_hollowing_lets_the_history_compute_on(
    profile: Profile,
) -> None:
    """Ein Verlauf aus 0.5.2: exakt aushöhlen, oben offen, dann umwandeln — und weiter.

    In 0.5.2 zählte die verborgene Vorgabe *Entlüftungen* 1 auch bei *Oben
    öffnen* und machte den exakten Körper zum Netz; wer seine Flächen
    zurückwollte, ließ *In Flächen und Kanten umwandeln* folgen. Seit das
    Aushöhlen exakt bleibt (Durchsicht 0.5.3, Fund 2), kommt dort ein exakter
    Körper an, und die Absage „hat bereits echte Flächen und Kanten“ hielt den
    ganzen Verlauf an. Jetzt geht er unverändert weiter, mit einem Hinweis, und
    der Schritt danach rechnet an ihm.

    Sollwerte aus der Konstruktion: Quader 40 × 30 × 20, Wand 2, oben offen —
    Hohlraum 36 × 26 × 18; die Bohrung Ø 6 von der Oberkante durch die ganze
    Höhe trifft nur den Boden der Dicke 2.
    """
    _kernel()
    result = _evaluated(
        profile,
        OperationDraft(op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 20.0}),
        OperationDraft(
            op="hollow_object",
            inputs=("obj_1",),
            params={"wall": 2.0, "open_top": True, "vents": 1},
        ),
        OperationDraft(op="mesh_to_exact", inputs=("obj_1",), params={}),
        OperationDraft(
            op="drill_hole",
            inputs=("obj_1",),
            params={
                "x": 0.0,
                "y": 0.0,
                "z": 20.0,
                "diameter": 6.0,
                "depth": 20.0,
                "compensate": False,
            },
        ),
    )
    body = result.scene.objects["obj_1"]
    assert body.kind == "brep"
    hollowed = 24000.0 - 36.0 * 26.0 * 18.0
    assert float(body.mesh.volume) == pytest.approx(hollowed - math.pi * 9.0 * 2.0, rel=1e-6)
    notes = [
        finding for finding in result.scene.report.findings if finding.code == "brep.already_exact"
    ]
    assert [note.severity for note in notes] == ["info"], "der Schritt sagt, dass er nichts tat"


def test_the_exact_primitives_stand_where_their_mesh_twins_stand(profile: Profile) -> None:
    """Gleicher Ort, gleiche Hülle, gleiches Volumen bis auf die Facettierung."""
    _kernel()
    cases = {
        "cone": {"bottom_diameter": 20.0, "top_diameter": 10.0, "height": 12.0},
        "sphere": {"diameter": 10.0},
        "torus": {"outer_diameter": 40.0, "tube_diameter": 8.0},
    }
    analytic = {
        "cone": 700.0 * math.pi,
        "sphere": 500.0 * math.pi / 3.0,
        "torus": 2.0 * math.pi**2 * 16.0 * 16.0,
    }
    for name, params in cases.items():
        exact = run(f"create_brep_{name}", None, profile, **params).outputs[0]
        mesh = run(f"create_{name}", None, profile, **params, segments=96).outputs[0]
        assert exact.kind == "brep" and mesh.kind == "mesh"
        assert float(exact.mesh.volume) == pytest.approx(analytic[name], rel=1e-6)
        assert float(mesh.mesh.volume) == pytest.approx(analytic[name], rel=2e-2)
        low, high = exact.mesh.bounds.minimum, exact.mesh.bounds.maximum
        assert low[2] == pytest.approx(0.0, abs=1e-6), f"{name} steht nicht auf dem Bett"
        assert high[2] == pytest.approx(mesh.mesh.bounds.maximum[2], abs=0.05)
    with pytest.raises(ValidationError) as caught:
        run("create_brep_torus", None, profile, outer_diameter=10.0, tube_diameter=6.0)
    assert caught.value.constraint == "crosses_axis"
    with pytest.raises(ValidationError):
        run("create_brep_cone", None, profile, bottom_diameter=0.0, top_diameter=0.0, height=5.0)


#: Drei Ringe aus dem Nachbau (RM-398) und ein Rohr über die Wandstärke:
#: Rankenclip 21,7/16,7 mal 14, Klemmschelle 22,9/16,9 mal 30, Kragen des
#: Kartuschendeckels 34,3/31,1 mal 6,4 — je Außen-, Innendurchmesser und Höhe.
TUBES = [
    pytest.param(
        {"outer_diameter": 21.7, "inner_given": True, "inner_diameter": 16.7, "height": 14.0},
        16.7,
        id="rankenclip",
    ),
    pytest.param(
        {"outer_diameter": 22.9, "inner_given": True, "inner_diameter": 16.9, "height": 30.0},
        16.9,
        id="klemmschelle",
    ),
    pytest.param(
        {"outer_diameter": 34.3, "inner_given": True, "inner_diameter": 31.1, "height": 6.4},
        31.1,
        id="kartuschendeckel",
    ),
    pytest.param({"outer_diameter": 20.0, "wall": 2.0, "height": 20.0}, 16.0, id="wand"),
]


@pytest.mark.parametrize(("values", "inner"), TUBES)
def test_a_tube_has_its_analytic_shape_in_both_kernels(
    profile: Profile, values: dict[str, Any], inner: float
) -> None:
    """Ein Rohr ist ein Ring mit durchgehender Öffnung — an beiden Kernen mit den
    eingetragenen Maßen, auf dem Bett stehend, und die Öffnung ist eine Bohrung.

    Exakt trifft das Volumen die Analytik; das Netz ist um genau die zwei
    einbeschriebenen Vielecke kleiner, nicht um irgendetwas daneben.
    """
    from app.core.perceive.features import detect

    _kernel()
    outer, height = float(values["outer_diameter"]), float(values["height"])
    segments = 96
    exact = run("create_brep_tube", None, profile, **values)
    mesh = run("create_tube", None, profile, **values, segments=segments)
    solid, net = exact.outputs[0], mesh.outputs[0]
    assert solid.kind == "brep" and net.kind == "mesh"
    assert not exact.findings and not mesh.findings

    ring = math.pi / 4.0 * (outer**2 - inner**2) * height
    assert float(solid.mesh.volume) == pytest.approx(ring, rel=1e-9)
    assert solid.mesh.is_closed and solid.mesh.solid_count == 1
    low, high = solid.mesh.bounds.minimum, solid.mesh.bounds.maximum
    assert tuple(low) == pytest.approx((-outer / 2.0, -outer / 2.0, 0.0), abs=1e-6)
    assert tuple(high) == pytest.approx((outer / 2.0, outer / 2.0, height), abs=1e-6)
    bores = [f for f in solid.features.values() if f.kind == "hole"]
    assert len(bores) == 1
    assert bores[0].params["diameter"] == pytest.approx(inner, abs=1e-6)
    assert bores[0].params["through"] is True

    polygon = segments / 2.0 * math.sin(2.0 * math.pi / segments)
    assert float(net.mesh.volume) == pytest.approx(
        polygon * ((outer / 2.0) ** 2 - (inner / 2.0) ** 2) * height, rel=1e-9
    )
    assert net.mesh.is_watertight and net.mesh.component_count == 1
    assert float(net.mesh.bounds.maximum[0]) == pytest.approx(outer / 2.0, abs=1e-9)
    assert float(net.mesh.bounds.minimum[2]) == pytest.approx(0.0, abs=1e-9)
    assert float(net.mesh.bounds.maximum[2]) == pytest.approx(height, abs=1e-9)
    found = [f for f in detect(net.mesh).values() if f.kind == "hole"]
    assert len(found) == 1
    assert found[0].params["diameter"] == pytest.approx(inner, abs=0.05)


def test_a_tube_without_an_opening_is_refused_in_both_kernels(profile: Profile) -> None:
    """Keine Öffnung, kein Rohr — beide Kerne sagen es am Feld, das schuld ist."""
    _kernel()
    for name in ("create_tube", "create_brep_tube"):
        with pytest.raises(ValidationError) as inner:
            run(
                name,
                None,
                profile,
                outer_diameter=20.0,
                inner_given=True,
                inner_diameter=20.0,
                height=5.0,
            )
        assert inner.value.field == "inner_diameter"
        with pytest.raises(ValidationError) as wall:
            run(name, None, profile, outer_diameter=20.0, wall=10.0, height=5.0)
        assert wall.value.field == "wall"


def test_a_tube_thinner_than_the_printer_lays_says_so_in_both_kernels(profile: Profile) -> None:
    """Die Wand nach dem Materialprofil: dieselbe Frage wie beim Aushöhlen (§39)."""
    _kernel()
    thin = profile.minimum_wall_thickness / 2.0
    for name in ("create_tube", "create_brep_tube"):
        result = run(name, None, profile, outer_diameter=20.0, wall=thin, height=5.0)
        codes = {finding.code for finding in result.findings}
        assert codes & {"hollow.wall_below_nozzle", "hollow.wall_below_minimum"}, name
        given = run(
            name,
            None,
            profile,
            outer_diameter=20.0,
            inner_given=True,
            inner_diameter=20.0 - 2.0 * thin,
            height=5.0,
        )
        assert {finding.code for finding in given.findings} == codes, name


def test_the_exact_tube_stands_where_its_mesh_twin_stands(profile: Profile) -> None:
    """Lage, Richtung und Drehung wirken an beiden Zwillingen gleich (P2.8)."""
    _kernel()
    placed = {
        "outer_diameter": 30.0,
        "wall": 3.0,
        "height": 12.0,
        "x": 5.0,
        "y": -3.0,
        "z": 2.0,
        "nx": 1.0,
        "ny": 0.0,
        "nz": 0.0,
        "angle": 30.0,
    }
    exact = run("create_brep_tube", None, profile, **placed).outputs[0]
    mesh = run("create_tube", None, profile, **placed, segments=96).outputs[0]
    # Liegend entlang +X: die Länge in X, der Durchmesser in Y und Z.
    assert exact.mesh.bounds.minimum[0] == pytest.approx(5.0, abs=1e-6)
    assert exact.mesh.bounds.maximum[0] == pytest.approx(17.0, abs=1e-6)
    for axis in range(3):
        assert exact.mesh.bounds.minimum[axis] == pytest.approx(
            mesh.mesh.bounds.minimum[axis], abs=0.02
        )
        assert exact.mesh.bounds.maximum[axis] == pytest.approx(
            mesh.mesh.bounds.maximum[axis], abs=0.02
        )


def test_the_exact_box_knows_the_corner_anchor(profile: Profile) -> None:
    _kernel()
    centred = run("create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0).outputs[0]
    cornered = run(
        "create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0, anchor="corner"
    ).outputs[0]
    assert centred.mesh.bounds.minimum[0] == pytest.approx(-20.0)
    assert cornered.mesh.bounds.minimum[0] == pytest.approx(0.0)
    assert cornered.mesh.bounds.minimum[1] == pytest.approx(0.0)
    assert float(cornered.mesh.volume) == pytest.approx(24000.0)


def test_a_cone_with_equal_radii_is_a_cylinder_not_a_refusal(profile: Profile) -> None:
    """Zwei gleiche Radien sind für OpenCASCADE ein Fehler, für den Kunden ein Zylinder.

    Die Vorgaben 20 und 10 liegen einen Tastendruck davon entfernt, und der
    Netz-Zwilling baut ihn, ohne zu fragen (Review, 21.09.2026).
    """
    _kernel()
    body = run(
        "create_brep_cone", None, profile, bottom_diameter=12.0, top_diameter=12.0, height=10.0
    ).outputs[0]
    assert body.kind == "brep"
    assert float(body.mesh.volume) == pytest.approx(math.pi * 36.0 * 10.0, rel=1e-6)


def test_the_exact_box_turns_around_its_anchor_like_the_mesh_twin(profile: Profile) -> None:
    """Bezugspunkt und Drehung wirken an beiden Zwillingen gleich — gemessen an der Hülle."""
    _kernel()
    placed = {"width": 40.0, "depth": 30.0, "height": 20.0, "anchor": "corner", "angle": 90.0}
    exact = run("create_brep_box", None, profile, **placed).outputs[0]
    mesh = run("create_box", None, profile, **placed).outputs[0]
    assert exact.kind == "brep" and mesh.kind == "mesh"
    for axis in range(3):
        assert exact.mesh.bounds.minimum[axis] == pytest.approx(
            mesh.mesh.bounds.minimum[axis], abs=1e-6
        )
        assert exact.mesh.bounds.maximum[axis] == pytest.approx(
            mesh.mesh.bounds.maximum[axis], abs=1e-6
        )


def test_the_surface_placement_previews_the_exact_primitives_too(profile: Profile) -> None:
    """Die Vorschau am Körper ist ein Netz — auch für den exakten Erzeuger im Menü."""
    _kernel()
    for mesh_name, brep_name in PRIMITIVE_TWINS:
        spec = REGISTRY.get(brep_name)
        values = {
            item.name: item.default for item in spec.params.spec() if item.default is not None
        }
        tool = _creation_tool(spec, values, profile)
        assert tool.mesh is not None, f"{brep_name} hat keine Vorschau am Körper"
        twin = _creation_tool(REGISTRY.get(mesh_name), values, profile)
        assert twin.mesh is not None
        assert float(tool.mesh.volume) == pytest.approx(float(twin.mesh.volume))


def test_the_history_offers_the_switch_only_at_primitives(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bohren und Aushöhlen entscheidet der Körper; ein Wechsel am Schritt liefe ins Leere.

    Und in den exakten Kern nur, wenn er da ist — sonst kein Eintrag statt
    einer Absage nach dem Klick (Regel 19).
    """
    _kernel()
    for name in ("drill_hole", "drill_brep_hole", "hollow_object", "shell_exact"):
        assert kernel_switch_label(name) is None, name
    for mesh, brep in PRIMITIVE_TWINS:
        assert kernel_switch_label(mesh) is not None
        assert kernel_switch_label(brep) is not None
    monkeypatch.setattr(registry_module, "exact_kernel_present", lambda: False)
    for mesh, brep in PRIMITIVE_TWINS:
        towards_exact = brep if kernel_twin_of(mesh) == brep else mesh
        assert kernel_switch_label(kernel_twin_of(towards_exact) or "") is None


def test_the_register_does_not_load_the_exact_kernel_on_import() -> None:
    """``MENU_TWINS`` fragt den Kern erst beim ersten Zugriff — 334 Module und 0,43 s
    bei jedem Import des Registers waren der Preis der eifrigen Antwort."""
    import subprocess
    import sys

    probe = (
        "import sys; import app.core.registry.registry as r; "
        "assert 'OCP' not in sys.modules, 'OCP beim Import geladen'; "
        "assert 'MENU_TWINS' not in vars(r); "
        "r.MENU_TWINS; print('ok')"
    )
    done = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=False, timeout=120
    )
    assert done.returncode == 0, done.stderr
    assert registry_module.MENU_TWINS is registry_module.menu_twins()
    assert set(registry_module.exact_names()) >= {brep for _mesh, brep in PRIMITIVE_TWINS}
    assert {"drill_brep_hole", "shell_exact"} <= set(registry_module.exact_names())


def test_a_step_still_switches_to_its_twin_in_the_history() -> None:
    """``History.change_kernel`` bleibt — jetzt vom Verlauf aus, ohne Haken."""
    _kernel()
    document = new_project("centauri-carbon-2", "petg").document
    history = History(document)
    history.apply(
        "Kegel",
        [
            OperationDraft(
                op="create_cone",
                params={
                    "bottom_diameter": 20.0,
                    "top_diameter": 10.0,
                    "height": 12.0,
                    "segments": 48,
                },
            )
        ],
    )
    op_id = document.ops[-1].id
    twin = kernel_twin_of("create_cone")
    assert twin == "create_brep_cone"
    allowed = {item.name for item in REGISTRY.get(twin).params.spec()}
    changed = history.change_kernel(
        op_id,
        twin,
        {key: value for key, value in document.ops[-1].params.items() if key in allowed},
    )
    assert changed.op == "create_brep_cone"
    assert "segments" not in changed.params


def test_a_step_below_an_exact_only_step_refuses_the_way_back_to_the_mesh() -> None:
    """Die zweite Sperre ist die Hürde des Kerns: mit der Zahl der Schritte, die anhielten."""
    _kernel()
    document = new_project("centauri-carbon-2", "petg").document
    history = History(document)
    history.apply("Quader", [OperationDraft(op="create_brep_box", params={})])
    box_step = document.ops[-1].id
    history.apply(
        "Exakt aushöhlen",
        [OperationDraft(op="shell_exact", inputs=("obj_1",), params={"wall": 2.0})],
    )
    with pytest.raises(ValidationError) as caught:
        history.change_kernel(box_step, "create_box", {})
    assert caught.value.constraint == "needs_exact"
    assert caught.value.values["count"] == 1
    assert caught.value.suggestions
    # Ohne den Schritt darüber geht der Weg zurück.
    history.undo()
    changed = history.change_kernel(box_step, "create_box", {})
    assert changed.op == "create_box"
