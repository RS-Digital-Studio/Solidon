"""Ein vorhandenes Gewinde ersetzen — mit tragender Wand und Gegengewinde (RM-184, Audit §9).

*Merkmal ändern* setzt ein Gewinde mit neuem Durchmesser und neuer Steigung,
in beiden Kernen. Zwei Dinge fehlten dem Weg, wie das Audit ihn verlangt:

* **Die tragende Wand bleibt.** Ein Innengewinde, das größer wird, frisst die
  Wand um sich; ein Außengewinde, das kleiner wird, den Kern über einer
  Bohrung. Bricht das neue Gewinde durch, sagt die Operation ab; bleibt
  weniger Wand, als das Material legen kann, sagt sie es.
* **Das Gegenstück geht mit.** Steht das Gewinde in einer Gewindepassung, ist
  der zweite Schritt am anderen Teil Teil derselben Transaktion — mit dem
  Durchmesser, den die Passung verlangt, und derselben Steigung. Ein Strg+Z
  nimmt beide zurück.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.counterpart import (
    apply_thread_counterpart,
    attach_thread_fit,
    coupled_thread_drafts,
)
from app.core.errors import ValidationError
from app.core.scene import ResultCache, evaluate
from app.core.scene.fits import active_fits, check, target
from app.core.scene.history import History, OperationDraft
from app.core.scene.project import load, new_project, save
from app.core.types import Document, Feature, Fit, Profile, Scene
from tests.helpers import run_operation as run
from tests.helpers import studded_thread_plate, tapped_thread_plate


@pytest.fixture(autouse=True)
def _operations() -> None:
    load_operations()


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_an_inner_thread_that_would_break_through_is_refused(kind: str, profile: Profile) -> None:
    """Platte 40 × 40: Ein Innengewinde Ø 41 schnitte durch die Seitenwände."""
    plate = tapped_thread_plate(kind)
    with pytest.raises(ValidationError) as problem:
        run("resize_feature", plate, profile, at_feature="thread_1", diameter=41.0, pitch=2.0)
    assert problem.value.constraint == "thread_wall"
    assert problem.value.suggestions, "Regel 17"
    # Der Satz nennt den größten Durchmesser, der die Mindestwand lässt:
    # 40 / 2 = 20 mm bis zur Seitenwand, abzüglich der Mindestwand, verdoppelt.
    largest = 2.0 * (20.0 - profile.minimum_wall_thickness)
    assert problem.value.values["largest"] == pytest.approx(largest, abs=0.05)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_an_inner_thread_that_thins_the_wall_says_so(kind: str, profile: Profile) -> None:
    """Ø 39,2 lässt 0,4 mm Wand — weniger als der Drucker legt; Ø 30 lässt 5 mm."""
    plate = tapped_thread_plate(kind)
    thin = run("resize_feature", plate, profile, at_feature="thread_1", diameter=39.2, pitch=2.0)
    finding = next(item for item in thin.findings if item.code == "thread.thin_wall")
    assert finding.values["wall_mm"] == pytest.approx(0.4, abs=0.05)
    assert finding.severity == "warning"
    roomy = run("resize_feature", plate, profile, at_feature="thread_1", diameter=30.0, pitch=2.0)
    assert not any(item.code == "thread.thin_wall" for item in roomy.findings)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_an_outer_thread_on_a_solid_stud_has_no_wall_to_lose(kind: str, profile: Profile) -> None:
    stud = studded_thread_plate(kind)
    result = run("resize_feature", stud, profile, at_feature="thread_1", diameter=4.0, pitch=0.7)
    assert not any(item.code == "thread.thin_wall" for item in result.findings)


def test_an_outer_thread_over_a_bore_keeps_its_core(profile: Profile) -> None:
    """Ein hohler Bolzen: Ø 3 durch Platte und Gewinde. Der Kern über der Bohrung ist die Wand.

    M4 × 0,7 hat seinen Kern bei 2 − 0,7 · RIDGE_SHARE = 1,615 mm Radius, über
    der Bohrung (1,5 mm) bleiben 0,115 mm; Ø 3,4 × 0,6 reicht mit 1,37 mm in sie
    hinein.
    """
    from app.core.geom.boolean import boolean
    from app.core.knowledge.parts import shapes

    stud = studded_thread_plate("mesh")
    bore = shapes.moved(shapes.cylinder(3.0, 30.0), (0.0, 0.0, -5.0))
    hollow = dataclasses.replace(
        stud, mesh=boolean("difference", [stud.mesh, bore], quality="fine").mesh
    )
    thin = run("resize_feature", hollow, profile, at_feature="thread_1", diameter=4.0, pitch=0.7)
    finding = next(item for item in thin.findings if item.code == "thread.thin_wall")
    core = 2.0 - 0.7 * shapes.RIDGE_SHARE
    assert finding.values["wall_mm"] == pytest.approx(core - 1.5, abs=0.05)
    with pytest.raises(ValidationError) as problem:
        run("resize_feature", hollow, profile, at_feature="thread_1", diameter=3.4, pitch=0.6)
    assert problem.value.constraint == "thread_wall"


def _with_a_paired_thread(document: Document, scene_of: Callable[[], Scene]) -> Feature:
    """Zwei Platten, ein M6-Innengewinde in der ersten, das Gegengewinde an der zweiten.

    ``scene_of`` wertet aus — am Dokument, über die Sitzung oder die Datei —,
    denn die Kennung des Gegengewindes entsteht erst dabei (``counterpart``).
    """
    History(document).apply(
        "Zwei Platten",
        [
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 10.0}),
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 10.0}),
        ],
    )
    History(document).apply(
        "Die zweite daneben",
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": 60.0})],
    )
    History(document).apply(
        "Gewinde in der ersten Platte",
        [
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"size": "M6", "length": 8.0, "internal": True, "z": 10.0},
            )
        ],
    )
    feature = next(
        item
        for item in scene_of().objects["obj_1"].features.values()
        if item.kind == "thread" and item.provenance == "generated"
    )
    applied = apply_thread_counterpart(
        document, feature, "obj_1", "obj_2", {"x": 60.0, "y": 0.0, "z": 10.0}
    )
    attach_thread_fit(document, applied, feature, scene_of())
    assert len(active_fits(document)) == 1, "die Gewindepassung steht"
    return feature


def _paired(profile: Profile) -> tuple[Document, ResultCache, Feature, Fit]:
    document = new_project("centauri-carbon-2", "petg").document
    cache = ResultCache()
    feature = _with_a_paired_thread(
        document, lambda: evaluate(document, profile, cache=cache).scene
    )
    return document, cache, feature, active_fits(document)[0]


def test_changing_a_paired_thread_changes_its_counterpart_in_the_same_step(
    profile: Profile,
) -> None:
    document, cache, feature, fit = _paired(profile)
    before = evaluate(document, profile, cache=cache)
    wanted, _names = target(before.scene, fit, profile)
    partner = fit.b if fit.a.object_id == "obj_1" else fit.a

    own = OperationDraft(
        op="resize_feature",
        inputs=("obj_1",),
        params={"at_feature": feature.id, "diameter": 8.0, "pitch": 1.25},
    )
    coupled = coupled_thread_drafts(document, before.scene, profile, "obj_1", dict(own.params))
    assert len(coupled) == 1
    assert coupled[0].op == "resize_feature"
    assert coupled[0].inputs == (partner.object_id,)
    assert coupled[0].params["at_feature"] == partner.feature_id
    assert coupled[0].params["pitch"] == pytest.approx(1.25)
    assert coupled[0].params["diameter"] == pytest.approx(8.0 - wanted), "außen um das Spiel enger"

    # Gegenprobe: Ohne den gekoppelten Schritt meldet die Prüfung die Passung —
    # sonst prüfte die Zusicherung unten nichts.
    alone = copy.deepcopy(document)
    History(alone).apply("Nur ein Gewinde", [own])
    lonely = evaluate(alone, profile)
    assert lonely.scene.fits, "die Passung steht in der Szene"
    assert any(
        item.code in {"fit.violated", "fit.pitch_mismatch"}
        for item in check(lonely.scene, profile, document=alone)
    )

    steps = len(document.ops)
    History(document).apply("Gewinde ersetzen", [own, *coupled])
    assert len(document.ops) == steps + 2, "zwei Schritte"
    after = evaluate(document, profile, cache=cache)
    assert after.stopped_at is None
    inner = after.scene.objects["obj_1"].features[feature.id]
    outer = after.scene.objects[partner.object_id].features[partner.feature_id]
    assert inner.params["diameter"] == pytest.approx(8.0)
    assert outer.params["diameter"] == pytest.approx(8.0 - wanted)
    assert inner.params["pitch"] == pytest.approx(outer.params["pitch"])
    violated = [
        item
        for item in check(after.scene, profile, document=document)
        if item.code in {"fit.violated", "fit.pitch_mismatch", "fit.missing_feature"}
    ]
    assert not violated, violated

    History(document).undo()
    assert len(document.ops) == steps, "ein Strg+Z nimmt beide Schritte"


def test_every_way_through_the_window_carries_the_counterpart_in_preview_and_step() -> None:
    """Merkmalfenster, Dialog, Palette und Karte enden alle in ``Session.apply`` und
    ``Session.preview_async`` — dort, nicht an jedem Einstieg, wird gekoppelt.

    Ohne Fenster: Die Sitzung ist der Anschluss (``tests.md``, „Anschluss“).
    """
    from app.ui.session import Session

    session = Session()
    document = session.project.document
    feature = _with_a_paired_thread(document, lambda: session.evaluate_now().scene)
    session.evaluate_now()

    own = OperationDraft(
        op="resize_feature",
        inputs=("obj_1",),
        params={"at_feature": feature.id, "diameter": 8.0, "pitch": 1.25},
    )
    planned = session.with_coupled_threads([own])
    assert [draft.inputs for draft in planned] == [("obj_1",), ("obj_2",)]

    transactions, steps = len(document.transactions), len(document.ops)
    assert session.apply("Merkmal ändern", [own])
    assert len(document.transactions) == transactions + 1, "eine Transaktion"
    assert len(document.ops) == steps + 2, "beide Gewinde"
    assert session.history.undo()
    assert len(document.ops) == steps, "ein Strg+Z nimmt beide"


def test_the_command_line_carries_the_counterpart_too(tmp_path: Path, profile: Profile) -> None:
    """``solidon3d run resize_feature`` schreibt beide Gewinde in einen Schritt der Datei."""
    from app.cli.main import main

    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    feature = _with_a_paired_thread(document, lambda: evaluate(document, profile).scene)
    path = save(project, tmp_path / "gewinde.p3d")
    steps = len(document.ops)

    code = main(
        [
            "run",
            "resize_feature",
            str(path),
            "--on",
            "obj_1",
            "--at-feature",
            feature.id,
            "--diameter",
            "8",
            "--pitch",
            "1.25",
        ]
    )

    assert code == 0
    written = load(path).document
    assert len(written.ops) == steps + 2, "beide Gewinde"
    assert [entry.inputs for entry in written.ops[-2:]] == [("obj_1",), ("obj_2",)]
    assert len(written.transactions[-1].ops) == 2, "ein Schritt im Verlauf"


def test_the_agent_carries_the_counterpart_in_its_proposal(profile: Profile) -> None:
    """Ein Werkzeugaufruf des Agenten, zwei Entwürfe im Vorschlag — eine Transaktion."""
    from app.core.agent.session import AgentSession
    from app.core.backends.llm import Reply, ToolCall
    from tests.scripted_backend import ScriptedBackend

    document, _cache, feature, _fit = _paired(profile)
    backend = ScriptedBackend(
        answers=[
            Reply(
                tool_calls=(
                    ToolCall(
                        id="1",
                        name="resize_feature",
                        arguments={
                            "objects": ["obj_1"],
                            "at_feature": feature.id,
                            "diameter": 8.0,
                            "pitch": 1.25,
                        },
                    ),
                )
            ),
            Reply(text="Beide Gewinde sind jetzt M8."),
        ]
    )
    agent = AgentSession(backend=backend, document=document, profile=profile)

    proposal = agent.propose("Mach das Gewinde M8")

    assert [(draft.op, draft.inputs) for draft in proposal.drafts] == [
        ("resize_feature", ("obj_1",)),
        ("resize_feature", ("obj_2",)),
    ]


def test_a_thread_without_a_fit_has_no_counterpart_to_carry(profile: Profile) -> None:
    plate = tapped_thread_plate("mesh")
    document = new_project("centauri-carbon-2", "petg").document
    drafts = coupled_thread_drafts(
        document,
        Scene(objects={plate.id: plate}),
        profile,
        plate.id,
        {"at_feature": "thread_1", "diameter": 8.0, "pitch": 1.25},
    )
    assert drafts == ()
