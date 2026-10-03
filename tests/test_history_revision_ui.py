"""Der Verlauf als Bedienort des Umbaus (RM-188 P7.1 bis P7.3).

Die reinen Helfer des Verlaufsfelds laufen ohne Fenster im Entwicklungstor;
Sitzung und Feld brauchen ``qt_app`` und laufen damit beim Release
(``tests/conftest.py`` vergibt den Marker ``windowed``). Der Kern des Umbaus —
Planen, isoliert Rechnen, Übernehmen — steht in ``test_revision.py`` und
``test_history.py``; hier steht, ob die Oberfläche ihn erreicht.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.scene import History, OperationDraft
from app.core.scene.history import StepNeed
from app.core.scene.project import new_project, save
from app.ui.panels import drop_before, needs_tip, replanned_steps, step_state
from tests.helpers import stop_evaluation

#: Die beiden Bohrungen der kleinen Platte, aus ihren Entwürfen.
LEFT_X = -20.0
RIGHT_X = 20.0


def _plate(project: Any = None) -> History:
    """Quader 80 × 40 × 10 mit zwei Bohrungen Ø 5 — Schritte 1, 2 und 3."""
    history = History((project or new_project("centauri-carbon-2", "petg")).document)
    history.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 40.0, "height": 10.0})],
    )
    for seed, x in ((1, LEFT_X), (2, RIGHT_X)):
        history.apply("Bohrung", [_drill(x, seed)])
    return history


def _drill(x: float, seed: int) -> OperationDraft:
    return OperationDraft(
        op="drill_hole",
        inputs=("obj_1",),
        params={"diameter": 5.0, "x": x, "y": 0.0, "z": 10.0, "depth": 10.0},
        seed=seed,
    )


# --- Helfer ohne Fenster --------------------------------------------------------


def test_the_old_rows_of_a_move_are_replanned_not_deleted() -> None:
    """Nach dem Verschieben stehen die alten Kennungen neu gefasst, nicht gelöscht (P7.2).

    Das Verlaufsfeld blendet sie aus, statt sie durchzustreichen — dasselbe
    Teil steht unter neuer Kennung beim Umbau. Nach Strg+Z gibt es nichts
    Neugefasstes mehr.
    """
    history = _plate()
    old = history.operations
    history.commit(history.plan_move([old[2].id], old[1].id))
    new = history.operations

    assert replanned_steps(history.document) == {old[1].id, old[2].id}
    assert not replanned_steps(history.document) & {entry.id for entry in new}, (
        "die neuen Kennungen sind die, die rechnen"
    )
    history.undo()
    assert replanned_steps(history.document) == frozenset()


def test_the_state_of_a_step_is_a_word_off_or_resting() -> None:
    """Aus, ruht oder nichts — als Wort an der Zeile, nie nur als Farbe (Regel 18)."""
    history = _plate()
    ops = history.operations
    assert step_state(history.document, ops[1].id) == ""
    history.commit(history.plan_suppress([ops[1].id]))
    assert step_state(history.document, ops[1].id) == "aus"
    assert step_state(history.document, ops[2].id) == "", "die andere Bohrung rechnet weiter"
    assert step_state(history.document, 999) == "", "einen unbekannten Schritt gibt es nicht"


def test_the_dependency_tip_names_both_directions() -> None:
    """Was ein Schritt braucht und wer ihn braucht — Körper und Merkmal zählen gleich (P7.2)."""
    needs = (
        StepNeed(step=2, on=1, object_id="obj_1"),
        StepNeed(step=3, on=1, object_id="obj_1"),
        StepNeed(step=4, on=2, object_id="obj_1", feature_id="hole_1"),
    )
    assert needs_tip(1, needs) == "Schritt 2, 3 braucht diesen."
    assert needs_tip(2, needs) == "Braucht Schritt 1.\nSchritt 4 braucht diesen."
    assert needs_tip(4, needs) == "Braucht Schritt 2."
    assert needs_tip(5, needs) == "", "ohne Abhängigkeit keine Zeile"


def test_a_drop_lands_before_the_next_step_below() -> None:
    """Protokollzeilen, Zurückgenommenes und die Einfügemarke tragen keinen Schritt."""
    rows: list[tuple[int, ...]] = [(1,), (), (2, 3), (), (4,)]
    assert drop_before(rows, 0) == 1
    assert drop_before(rows, 1) == 2, "eine Zeile ohne Schritt zählt nicht"
    assert drop_before(rows, 3) == 4
    assert drop_before(rows, 5) is None, "unter der letzten Zeile heißt: ans Ende"
    assert drop_before(rows, -1) == 1


def test_an_import_at_the_marker_does_not_land_on_a_kept_model(monkeypatch: Any) -> None:
    """Review N4 (Sonde p18): ein weiteres Modell an der Einfügemarke.

    Vor dem Ladeschritt eines Blocks eingefügt, dessen Stelle schon
    feststand, suchte der zweite Block an der Szene vor der Marke. Dort stand
    der erste noch nicht, und beide lagen deckungsgleich. Die Sitzung plant
    jetzt im Arbeiter mit der Stelle am Endstand. Geprüft ohne Fenster: Der
    Plan, den die Sitzung dem Arbeiter übergibt, läuft hier so, wie der
    Arbeiter ihn fährt.
    """
    import copy
    from pathlib import Path

    from app.core.scene import evaluate
    from app.core.scene.history import RevisionPlan
    from app.core.scene.project import ProjectSources
    from app.core.scene.revision import commit, dependencies, revise
    from app.ui.session import Session

    meshes = Path(__file__).parent / "data" / "meshes"
    session = Session()
    for name in ("cube_clean.stl", "block_with_rounded_edge.stl"):
        assert session.import_model(meshes / name, unit="mm")
        stop_evaluation(session)

    def run(document: Any) -> Any:
        return evaluate(
            document,
            session.evaluation_profile,
            cache=session.cache,
            sources=ProjectSources(session.project, base_dir=session.base_dir),
        )

    session.history.record_answers(run(session.project.document).answers)
    kept = session.project.document.ops[1]
    assert kept.params.get("spot_x") is not None, "die Stelle des ersten Blocks steht fest"
    assert session.start_inserting(kept.id)
    stop_evaluation(session)

    handed: list[Any] = []
    monkeypatch.setattr(
        session, "_start_revision", lambda planned, _baseline: handed.append(planned) or True
    )
    assert session.import_model(meshes / "block_with_rounded_edge.stl", unit="mm")
    [planned] = handed

    history = History(copy.deepcopy(session.project.document))
    baseline = run(history.document)
    context = dependencies(history.document, baseline)
    plan = planned if isinstance(planned, RevisionPlan) else planned(history, context, run)
    commit(session.history, revise(history, plan, evaluate=run, baseline=baseline))
    result = run(session.project.document)

    assert result.complete
    boxes = [
        (entry.plate, entry.mesh.bounds.minimum, entry.mesh.bounds.maximum)
        for entry in result.scene.objects.values()
    ]
    assert len(boxes) == 3
    overlapping = [
        (a, b)
        for index, a in enumerate(boxes)
        for b in boxes[index + 1 :]
        if a[0] == b[0]
        and all(a[1][axis] < b[2][axis] and b[1][axis] < a[2][axis] for axis in (0, 1))
    ]
    assert not overlapping, "der eingefügte Block liegt nicht auf dem festgehaltenen"


# --- Feld und Sitzung (Release) ---------------------------------------------------


def _row_of(panel: Any, op_id: int) -> Any:
    from PySide6.QtCore import Qt

    for row in range(panel.list.count()):
        item = panel.list.item(row)
        if item.data(Qt.ItemDataRole.UserRole) == op_id:
            return item
    raise AssertionError(f"keine Zeile für Schritt {op_id}")


def _choose(panel: Any, op_id: int) -> None:
    item = _row_of(panel, op_id)
    panel.list.clearSelection()
    panel.list.setCurrentItem(item)
    item.setSelected(True)


def test_the_keyboard_reaches_every_revision_of_the_history(qt_app: Any) -> None:
    """Leertaste, Alt+Pfeil und Einfügen tun, was Kontextmenü und Maus tun (P7).

    Geprüft an den Signalen des Felds: Was die Sitzung daraus macht, prüfen
    die Sitzungstests darunter. Ein ausgeschalteter Schritt steht mit „(aus)"
    an seiner Zeile, und die Leertaste schaltet ihn wieder ein.
    """
    from app.ui.panels import HistoryPanel

    history = _plate()
    ops = history.operations
    history.commit(history.plan_suppress([ops[2].id]))
    panel = HistoryPanel()
    seen: dict[str, list[Any]] = {
        "insert": [],
        "move": [],
        "suppress": [],
        "reactivate": [],
        "note": [],
    }
    panel.insertRequested.connect(seen["insert"].append)
    panel.moveRequested.connect(lambda steps, before: seen["move"].append((steps, before)))
    panel.suppressRequested.connect(seen["suppress"].append)
    panel.reactivateRequested.connect(seen["reactivate"].append)
    panel.noteRequested.connect(seen["note"].append)
    try:
        panel.show_document(history.document)
        assert "(aus)" in _row_of(panel, ops[2].id).text()
        assert "(aus)" not in _row_of(panel, ops[1].id).text()

        _choose(panel, ops[2].id)
        panel.toggle_action.trigger()
        assert seen["reactivate"] == [(ops[2].id,)]

        _choose(panel, ops[1].id)
        panel.toggle_action.trigger()
        assert seen["suppress"] == [(ops[1].id,)]

        panel.insert_action.trigger()
        assert seen["insert"] == [ops[1].id]

        panel.down_action.trigger()
        assert seen["move"] == [((ops[1].id,), None)], "eine Stelle tiefer ist hier: ans Ende"

        # Mit einer Auskunft über die Stellen: eine ungültige sagt ihren Grund
        # und bewegt nichts.
        panel.list.places = lambda _steps: {ops[0].id: "Kein Körper davor.", None: None}
        panel.up_action.trigger()
        assert seen["move"] == [((ops[1].id,), None)]
        assert seen["note"] == ["Kein Körper davor."]
    finally:
        panel.deleteLater()


def test_the_insertion_marker_stands_before_its_step(qt_app: Any) -> None:
    """Die Einfügemarke ist eine eigene Zeile vor ihrem Schritt, ohne Schritt darin (P7.1)."""
    from app.ui.panels import MARKER_ROLE, HistoryPanel

    history = _plate()
    ops = history.operations
    panel = HistoryPanel()
    panel.revision_context = lambda: (ops[2].id, ())
    try:
        panel.show_document(history.document)
        rows = [panel.list.item(row) for row in range(panel.list.count())]
        marker = next(index for index, item in enumerate(rows) if item.data(MARKER_ROLE))
        assert "Neue Schritte kommen hierhin" in rows[marker].text()
        assert panel.list.row(_row_of(panel, ops[2].id)) == marker + 1
        assert panel.stop_insert_action.isEnabled()
    finally:
        panel.deleteLater()


def _session_on_plate(tmp_path: Path) -> Any:
    from app.ui.session import Session

    project = new_project("centauri-carbon-2", "petg")
    _plate(project)
    path = save(project, tmp_path / "platte.p3d")
    session = Session()
    session.open_project(path)
    assert session.wait_for_idle(60_000)
    return session


def test_the_session_switches_a_step_off_in_the_worker_and_undo_restores_it(
    qt_app: Any, tmp_path: Path
) -> None:
    """Ausschalten über die Sitzung: gerechnet im Arbeiter, übernommen als eine Transaktion."""
    session = _session_on_plate(tmp_path)
    done: list[Any] = []
    failed: list[Any] = []
    session.revisionDone.connect(done.append)
    session.failed.connect(failed.append)
    second = session.project.document.ops[2].id

    assert session.revise_history("suppress", [second])
    assert session.wait_for_idle(60_000)
    assert not failed, failed
    assert [revision.plan.kind for revision in done] == ["suppress"]
    entry = next(entry for entry in session.project.document.ops if entry.id == second)
    assert entry.suppressed is not None and entry.suppressed.chosen
    assert session.last_result is not None and session.last_result.complete

    session.undo()
    assert session.wait_for_idle(60_000)
    assert all(entry.suppressed is None for entry in session.project.document.ops)


def test_the_session_inserts_at_the_marker_and_the_marker_moves_along(
    qt_app: Any, tmp_path: Path
) -> None:
    """Einfügen vor Schritt 3: Die Oberfläche zeigt den Stand davor, die Marke rückt mit (P7.1)."""
    session = _session_on_plate(tmp_path)
    failed: list[Any] = []
    session.failed.connect(failed.append)
    box, first, second = (entry.id for entry in session.project.document.ops)

    assert session.start_inserting(second)
    assert session.wait_for_idle(60_000)
    assert [entry.id for entry in session.displayed_document().ops] == [box, first]

    assert session.apply("Bohrung", [_drill(0.0, 3)])
    assert session.wait_for_idle(60_000)
    assert not failed, failed
    ops = session.project.document.ops
    assert [entry.params.get("x") for entry in ops[1:]] == [LEFT_X, 0.0, RIGHT_X]
    assert session.inserting == ops[3].id, "die Marke steht vor dem neu gefassten Schritt"

    session.stop_inserting()
    assert session.wait_for_idle(60_000)
    assert session.inserting is None
    assert session.last_result is not None and session.last_result.complete
    session.undo()
    assert session.wait_for_idle(60_000)
    assert [entry.params.get("x") for entry in session.project.document.ops[1:]] == [
        LEFT_X,
        RIGHT_X,
    ]


@pytest.mark.parametrize("ending", ["cancelled", "failed", "taken"])
def test_an_import_at_the_marker_takes_its_source_along_when_it_does_not_land(
    monkeypatch: Any, ending: str
) -> None:
    """RM-303: Ein abgebrochener Import an der Einfügemarke ließ seine Datei zurück.

    An der Marke rechnet ein Arbeiter den Import erst; die Quelle steht da
    schon im Dokument. Brach der Kunde ab oder scheiterte der Umbau, blieb sie
    dort und reiste mit dem nächsten Speichern in die Projektdatei. Kommt der
    Import an, meldet die Sitzung seinen Körper — derselbe Satz wie am Ende
    des Stapels, damit das Fenster seine Platte zeigt.
    """
    import copy
    from types import SimpleNamespace

    from app.core.errors import InternalError
    from app.core.scene import evaluate
    from app.core.scene.history import RevisionPlan
    from app.core.scene.project import ProjectSources
    from app.core.scene.revision import dependencies, revise
    from app.ui.session import Session

    meshes = Path(__file__).parent / "data" / "meshes"
    session = Session()
    for name in ("cube_clean.stl", "block_with_rounded_edge.stl"):
        assert session.import_model(meshes / name, unit="mm")
        stop_evaluation(session)
    assert session.start_inserting(session.project.document.ops[1].id)
    stop_evaluation(session)
    before = set(session.project.document.sources)
    placed: list[str] = []
    session.modelPlaced.connect(placed.append)

    # Der Arbeiter läuft hier nicht; sein Ausgang wird so zugestellt, wie er
    # ihn meldet. Sonst entschiede die Uhr, ob ein Abbruch vor dem Ende ankommt.
    worker = SimpleNamespace(_project_generation=session._project_generation)
    handed: list[Any] = []

    def held(planned: Any, _baseline: Any) -> bool:
        handed.append(planned)
        session._revision = worker
        return True

    monkeypatch.setattr(session, "_start_revision", held)
    assert session.import_model(meshes / "block_with_rounded_edge.stl", unit="mm")
    [planned] = handed
    added = set(session.project.document.sources) - before
    assert len(added) == 1, "die Quelle steht schon im Dokument, solange der Arbeiter rechnet"
    assert not placed, "gemeldet wird erst, was im Stapel steht"

    if ending == "cancelled":
        session._on_revision_cancelled(finished=worker)
    elif ending == "failed":
        session._on_revision_failed(InternalError(detail="test"), finished=worker)
    else:

        def run(document: Any) -> Any:
            return evaluate(
                document,
                session.evaluation_profile,
                cache=session.cache,
                sources=ProjectSources(session.project, base_dir=session.base_dir),
            )

        history = History(copy.deepcopy(session.project.document))
        baseline = run(history.document)
        context = dependencies(history.document, baseline)
        plan = planned if isinstance(planned, RevisionPlan) else planned(history, context, run)
        session._on_revised(revise(history, plan, evaluate=run, baseline=baseline), worker)
    session._revision = None

    sources = set(session.project.document.sources)
    if ending == "taken":
        assert added <= sources
        body = next(
            entry.outputs[0]
            for entry in session.project.document.ops
            if entry.params.get("source") in added
        )
        assert placed == [body]
    else:
        assert not added & sources, "die Datei reiste sonst mit dem nächsten Speichern mit"
        assert not added & set(session.project.sources)
        assert not placed
