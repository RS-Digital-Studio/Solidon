"""Was für ein Netz gilt, gilt auch für einen exakten Körper (§30).

**Der Anlass ist ein Absturzbericht vom 27.08.2026** (S-20260826-594f0f). Ein
Kunde lud eine STEP-Datei und wählte eine Analysekarte; ``maps._mesh_of``
verlangte hart ein ``MeshData`` und warf einen ``TypeError``. Für eine
gewöhnliche Handlung bekam er einen Programmfehler samt Fehlerbericht.

Der Typprüfer sieht so etwas nicht: Die Funktion war als ``-> MeshData``
deklariert und hielt sich daran — sie warf eben, statt umzuwandeln. Was fehlt,
ist eine Zusicherung zur **Laufzeit**, und zwar über das ganze Register.

``OperationSpec.requires_kind`` ist die Zusage, die hier geprüft wird: ``"brep"``
heißt „nur exakt", **leer heißt beides**. Jede Operation mit leerem
``requires_kind`` verspricht damit, einen exakten Körper zu verkraften.

**Die Aussage ist der Unterschied, nicht der Erfolg.** Eine Operation, die an
beidem scheitert, sagt nichts über B-Rep — ihr fehlen nur brauchbare Vorgaben
oder die passende Geometrie. Rot wird dieser Test erst, wenn dieselbe Operation
mit derselben Eingabe am exakten Körper scheitert **und** am Netz durchläuft.

Gemessen am 27.08.2026: 67 Operationen sagen zu, beides zu können; keine
einzige verhielt sich unterschiedlich.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge.profiles import make_profile
from app.core.registry import REGISTRY, OperationSpec
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, OpResult, Scene, SceneObject

#: Werte, mit denen eine Operation etwas zu tun bekommt. Ohne sie lehnen die
#: Bausteine ab, bevor sie den Körper überhaupt ansehen („Für diesen Baustein
#: fehlt die Stelle") — und dann prüft der Durchlauf nichts.
PLACEMENT: dict[str, Any] = {"x": 5.0, "y": 5.0, "z": 10.0, "wall": 1.6, "slot": 1}

#: Pflichtfelder ohne Vorgabe, je Name ein brauchbarer Wert.
REQUIRED: dict[str, Any] = {"source": "", "text": "AB", "name": "Neu"}


def _exact_body() -> Any:
    """Ein hohler exakter Körper — Box minus Box, damit auch Deckel und
    Gitterfüllung etwas vorfinden."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from app.core.brep.kernel import Solid

    outer = BRepPrimAPI_MakeBox(20.0, 20.0, 10.0).Shape()
    inner = BRepPrimAPI_MakeBox(gp_Pnt(2.0, 2.0, 2.0), 16.0, 16.0, 10.0).Shape()
    return Solid(shape=BRepAlgoAPI_Cut(outer, inner).Shape())


def _second_body() -> Any:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from app.core.brep.kernel import Solid

    return Solid(shape=BRepPrimAPI_MakeBox(gp_Pnt(10.0, 0.0, 0.0), 20.0, 20.0, 10.0).Shape())


def _params_for(spec: OperationSpec) -> Any:
    # Nicht jede Operation trägt ein Dataclass-Schema — ``delete_object``
    # etwa nimmt schlicht keine Werte entgegen.
    if not dataclasses.is_dataclass(spec.params):
        return spec.params()
    names = {field.name for field in dataclasses.fields(spec.params)}
    built = spec.params(**{key: value for key, value in REQUIRED.items() if key in names})
    changes = {
        field.name: PLACEMENT[field.name]
        for field in dataclasses.fields(built)
        if field.name in PLACEMENT
    }
    return dataclasses.replace(built, **changes) if changes else built


def _run(spec: OperationSpec, first: Any, second: Any, features: dict[str, Any]) -> str:
    """Der Name der Ausnahme, oder ``"ok"``. Kein Ergebnis wird bewertet —
    geprüft wird, **ob** es eines gibt."""
    one = SceneObject(id="obj_1", name="Probe", mesh=first, features=features)
    two = SceneObject(id="obj_2", name="Zweit", mesh=second, features=features)
    context = OpContext(
        scene=Scene(objects={"obj_1": one, "obj_2": two}),
        inputs=[one] if spec.consumes == 1 else [one, two],
        params=_params_for(spec),
        profile=make_profile("centauri-carbon-2", "pla"),
        quality="draft",
        seed=1234,
        progress=lambda *args, **kwargs: None,
        ask=lambda *args, **kwargs: None,
        cancelled=NeverCancelled(),
    )
    try:
        spec.fn(context)
    except Exception as problem:
        return type(problem).__name__
    return "ok"


def _candidates() -> list[OperationSpec]:
    load_operations()
    return sorted(
        (
            spec
            for spec in REGISTRY.all()
            if getattr(spec, "requires_kind", "") != "brep"
            and not getattr(spec, "whole_scene", False)
            and spec.consumes >= 1
        ),
        key=lambda spec: spec.name,
    )


@pytest.mark.slow
def test_no_operation_fails_on_an_exact_body_while_the_mesh_gets_through() -> None:
    """Der Durchlauf über das ganze Register."""
    from app.core.brep.kernel import available

    if not available():
        pytest.skip("OpenCASCADE is an optional dependency")

    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data

    solid, second = _exact_body(), _second_body()
    mesh, second_mesh = as_mesh_data(solid), as_mesh_data(second)
    features = dict(features_of(solid))

    candidates = _candidates()
    assert len(candidates) > 50, f"nur {len(candidates)} Operationen — greift der Filter?"

    divergent = []
    for spec in candidates:
        try:
            exact = _run(spec, solid, second, features)
            tessellated = _run(spec, mesh, second_mesh, features)
        except Exception as problem:  # der Aufbau selbst, nicht die Operation
            pytest.fail(f"{spec.name}: der Durchlauf ließ sich nicht bauen — {problem}")
        if exact != "ok" and tessellated == "ok":
            divergent.append(f"{spec.name}: exakt {exact}, vernetzt ok")

    assert not divergent, (
        "Diese Operationen sagen über `requires_kind` zu, beide Bauarten zu "
        "können, scheitern aber am exakten Körper:\n  " + "\n  ".join(divergent)
    )


def test_the_sweep_would_notice_an_operation_that_reaches_past_as_mesh_data() -> None:
    """Die Kontrollprobe — ein Wächter, den man nie hat fallen sehen, ist eine
    Behauptung.

    Nachgestellt wird genau der Griff, an dem der Kunde scheiterte: ``slots``
    ist einer von vier Namen, die es nur am ``MeshData`` gibt, und ein direkter
    Zugriff darauf fällt am exakten Körper hin.
    """
    from app.core.brep.kernel import available

    if not available():
        pytest.skip("OpenCASCADE is an optional dependency")

    from app.core.geom.mesh import as_mesh_data

    solid = _exact_body()

    def reaching_past(context: OpContext) -> OpResult:
        _ = context.inputs[0].mesh.slots  # type: ignore[attr-defined]
        return OpResult(outputs=[])

    def going_through(context: OpContext) -> OpResult:
        _ = as_mesh_data(context.inputs[0].mesh).slots
        return OpResult(outputs=[])

    broken = dataclasses.replace(_candidates()[0], name="probe", fn=reaching_past)
    sound = dataclasses.replace(_candidates()[0], name="probe", fn=going_through)

    assert _run(broken, solid, solid, {}) == "AttributeError", (
        "die Probe müsste am exakten Körper hinfallen — sonst prüft der Durchlauf darüber nichts"
    )
    assert _run(broken, as_mesh_data(solid), as_mesh_data(solid), {}) == "ok"
    assert _run(sound, solid, solid, {}) == "ok", "über as_mesh_data geht derselbe Griff"
