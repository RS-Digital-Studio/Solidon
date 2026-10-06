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

from app.core.errors import UserError
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


def _removed_copy() -> History:
    """Die Platte, eine Kopie davon, verschoben und wieder entfernt — Schritte 4 bis 6."""
    history = _plate()
    history.apply(
        "Duplizieren",
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 2})],
    )
    copy = history.operations[-1].outputs[1]
    history.apply(
        "Bewegen", [OperationDraft(op="translate_object", inputs=(copy,), params={"dx": 90.0})]
    )
    history.apply("Entfernen", [OperationDraft(op="delete_object", inputs=(copy,))])
    return history


def test_a_step_whose_result_was_removed_says_so() -> None:
    """„Ergebnis entfernt" an jedem Schritt, dessen Körper später entfernt wurde.

    Anlass S-20261006-2a0261. Die Kopie entsteht, wird verschoben und entfernt: Duplizieren und
    Verschieben wirken nicht mehr, das Entfernen selbst schon, und die
    Bohrungen an der bleibenden Platte rechnen weiter.
    """
    from app.core.scene.history import discarded

    history = _removed_copy()
    ops = history.operations
    gone = discarded(history.document.ops)

    assert step_state(history.document, ops[3].id, gone) == "Ergebnis entfernt"
    assert step_state(history.document, ops[4].id, gone) == "Ergebnis entfernt"
    assert step_state(history.document, ops[5].id, gone) == "", "das Entfernen wirkt"
    assert step_state(history.document, ops[1].id, gone) == "", "die Platte bleibt"
    assert step_state(history.document, ops[3].id) == "", "ohne Auskunft keine Behauptung"


def test_the_removed_steps_stand_under_their_removal() -> None:
    """Was mit einem Objekt wegfällt, steht unter seiner Löschung (Entscheidung Robert, 06.10.2026).

    Duplizieren und Verschieben der Kopie gehören unter *Entfernen*. Steht ein
    Schritt in einer Transaktion mit einem, der weiter wirkt, bleibt die
    Transaktion an ihrer Stelle — sie zieht nur ganz um.
    """
    from app.core.scene.history import discarded
    from app.ui.panels import removal_groups

    history = _removed_copy()
    ops = history.operations
    removal = history.document.transactions[-1]
    assert removal_groups(history.document, discarded(history.document.ops)) == {
        removal.id: (ops[3].id, ops[4].id)
    }

    mixed = _plate()
    mixed.apply(
        "Kopie und Platte bewegen",
        [
            OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 2}),
            OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 5.0}),
        ],
    )
    copy = mixed.operations[3].outputs[1]
    mixed.apply("Entfernen", [OperationDraft(op="delete_object", inputs=(copy,))])
    gone = discarded(mixed.document.ops)
    assert removal_groups(mixed.document, gone) == {}
    assert step_state(mixed.document, mixed.operations[3].id, gone) == "Ergebnis entfernt", (
        "an ihrer Stelle sagt die Zeile, was gilt"
    )


def test_the_history_folds_removed_steps_under_their_removal(qt_app: Any) -> None:
    """Die Löschung ist ein Oberpunkt mit der Zahl als Wort, die Schritte zugeklappt darunter.

    Eingerückt, kursiv und mit dem entfernenden Schritt in der Kurzhilfe;
    aufgeklappt per Klick, und zwischen sie lässt sich nichts ablegen — sie
    stehen nicht an ihrer Stelle im Stapel.
    """
    from app.ui.panels import NESTED_ROLE, HistoryPanel

    history = _removed_copy()
    ops = history.operations
    panel = HistoryPanel()
    try:
        panel.show_document(history.document)
        head = _row_of(panel, ops[5].id)
        assert head.text().startswith("▸") and head.text().endswith("(mit 2 Schritten)")
        assert "Entfernt, was die 2 Schritte darunter ergeben." in head.toolTip()
        at = panel.list.row(head)
        for offset, step in enumerate((ops[3], ops[4]), start=1):
            row = _row_of(panel, step.id)
            assert panel.list.row(row) == at + offset, "unter der Löschung, in Stapelfolge"
            assert row.text().startswith("    ") and "(Ergebnis entfernt)" not in row.text()
            assert row.font().italic() and row.data(NESTED_ROLE)
            assert row.isHidden(), "zugeklappt, bis jemand aufklappt"
            assert (
                "Schritt 6 entfernt das Ergebnis wieder. Dieser Schritt bleibt im Verlauf, "
                "wirkt aber nicht mehr." in row.toolTip()
            )
        assert not panel.list.row_ops()[at + 1], "kein Ablageziel zwischen den Schritten"

        panel._toggle_group(head)
        assert head.text().startswith("▾")
        assert not _row_of(panel, ops[3].id).isHidden()
        assert "(Ergebnis entfernt)" not in _row_of(panel, ops[1].id).text(), "die Platte bleibt"
    finally:
        panel.deleteLater()


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


def test_history_slider_counts_transactions_and_supports_keyboard(qt_app):
    """Zwei Ops in einem Auftrag geben eine Raste; Pfeile wählen den Stand."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.panels import HistoryPanel

    history = _plate()
    history.apply(
        "Zwei Körper", [OperationDraft(op="create_box"), OperationDraft(op="create_sphere")]
    )
    panel = HistoryPanel()
    panel.show_document(history.document)
    chosen = []
    panel.previewRequested.connect(chosen.append)
    panel.compare.click()
    assert panel.timeline_slider.maximum() == 4
    assert panel.timeline_slider.minimum() == 1
    assert panel.timeline_slider.accessibleName()
    QTest.keyClick(panel.timeline_slider, Qt.Key.Key_Left)
    assert chosen == [4, 3]
    assert len(history.document.transactions) == 4
    assert len(history.document.ops) == 5
    panel.close()


def test_history_preview_reconstructs_each_transaction_without_mutating_document(qt_app):
    """Jede Raste liefert den echten früheren Hash, auch über eine Parameteränderung."""
    import copy

    from app.core.scene.evaluate import evaluate
    from app.core.types import Parameter
    from app.ui.session import Session
    from tests.ui_helpers import wait_until

    session = Session()
    session.add_parameter(Parameter(name="width", value=20.0, unit="mm"))
    session.wait_for_idle()
    session.history.apply("Quader", [OperationDraft(op="create_box", params={"width": "=@width"})])
    session.change_parameter("width", 35.0)
    session.wait_for_idle()
    session.history.apply("Zweiter Körper", [OperationDraft(op="create_sphere")])
    original = copy.deepcopy(session.project.document)
    for count in range(1, len(original.transactions) + 1):
        document = copy.deepcopy(original)
        history = History(document)
        while len(document.transactions) > count:
            history.undo()
        expected = evaluate(
            document, session.profile, quality=session.quality, detect_features=False
        )
        values, errors = [], []
        session.history_preview_async(
            count, values.append, explained=errors.append, progressed=lambda value: None
        )
        wait_until(qt_app, lambda values=values: bool(values))
        assert not errors
        actual = values[0][0]
        assert actual.object_hashes == expected.object_hashes
        assert session.project.document == original
        assert not session.history.undone
    session.release()


@pytest.mark.parametrize(
    "filename", ["weg2-halter-konstruieren.p3d", "skizze-mit-massen.p3d", "dose-mit-deckel.p3d"]
)
def test_history_preview_reaches_every_transaction_of_three_real_projects(qt_app, filename):
    """Die Transaktionsrasten funktionieren auch an drei gespeicherten Kundenwegen."""
    import copy

    from app.core.scene import evaluate
    from app.core.scene.project import ProjectSources, load
    from app.ui.session import Session
    from tests.ui_helpers import wait_until

    session = Session()
    session.project = load(Path("app/examples") / filename)
    session.history = History(session.project.document)
    saved = copy.deepcopy(session.project.document)
    assert len(saved.transactions) > 1
    for count in range(1, len(saved.transactions) + 1):
        document = copy.deepcopy(saved)
        history = History(document)
        while len(document.transactions) > count:
            history.undo()
        expected = evaluate(
            document,
            session.profile,
            quality=session.quality,
            sources=ProjectSources(session.project),
            ask=lambda question, choices: choices[0],
            detect_features=False,
        )
        assert expected.stopped_at is None
        values, errors = [], []
        session.history_preview_async(
            count, values.append, explained=errors.append, progressed=lambda value: None
        )
        wait_until(qt_app, lambda values=values: bool(values))
        assert not errors
        assert values[0][0].object_hashes == expected.object_hashes
        assert session.project.document == saved
    session.release()


@pytest.mark.parametrize("interruption", ["newer", "cancel", "project"])
def test_history_preview_discards_outdated_answers(qt_app, monkeypatch, interruption):
    """Schneller Wechsel, Abbruch und neues Projekt lassen keine alte Vorschau zurück."""
    import threading

    from app.ui import session as session_module
    from app.ui.session import Session
    from tests.ui_helpers import wait_until

    session = Session()
    session.history.apply("Quader", [OperationDraft(op="create_box")])
    session.history.apply("Kugel", [OperationDraft(op="create_sphere")])
    entered, release = threading.Event(), threading.Event()
    original = session_module.evaluate
    first = True

    def delayed(*args, **kwargs):
        nonlocal first
        if first:
            first = False
            entered.set()
            release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(session_module, "evaluate", delayed)
    old, new = [], []
    session.history_preview_async(
        1, old.append, explained=lambda text: None, progressed=lambda value: None
    )
    wait_until(qt_app, entered.is_set)
    if interruption == "newer":
        session.history_preview_async(
            2, new.append, explained=lambda text: None, progressed=lambda value: None
        )
    elif interruption == "cancel":
        session.cancel_preview()
    else:
        session.start_new()
    release.set()
    assert session.wait_for_idle(30000)
    session.release()
    qt_app.processEvents()
    assert not old
    if interruption == "newer":
        assert len(new) == 1
        assert len(new[0][0].scene.objects) == 2


def test_history_preview_restores_selection_and_explicitly_sets_insertion(qt_app):
    """Der Vergleich zeigt keinen Griff; Rückweg und Einfügemarke bleiben getrennt."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    window.session.history.apply("Quader", [OperationDraft(op="create_box")])
    window.session.history.apply("Kugel", [OperationDraft(op="create_sphere")])
    window.session.evaluate_async()
    assert window.session.wait_for_idle()
    window.object_tree.select_objects(("obj_1",))
    panel = window.history_panel
    transactions = tuple(window.session.history.transactions)
    panel.compare.click()
    assert window.session.wait_for_idle()
    assert window.viewport.highlighted_objects() == ()
    assert window.object_tree.selected_objects() == ("obj_1",)
    QTest.keyClick(panel.timeline_slider, Qt.Key.Key_Left)
    assert window.session.wait_for_idle()
    assert window.session.inserting is None
    panel.timeline_end.click()
    assert window.viewport.highlighted_objects() == ("obj_1",)
    assert tuple(window.session.history.transactions) == transactions
    panel.compare.click()
    QTest.keyClick(panel.timeline_slider, Qt.Key.Key_Left)
    assert window.session.wait_for_idle()
    panel.timeline_insert.click()
    assert window.session.wait_for_idle()
    assert window.session.inserting == 2
    assert not panel.compare.isChecked()
    assert tuple(window.session.history.transactions) == transactions
    window.session.stop_inserting()
    assert window.session.wait_for_idle()
    assert len(window.session.last_result.scene.objects) == 2


@pytest.mark.parametrize(
    "command", ["start_sculpt", "start_armature", "start_sketch", "operation", "undo"]
)
def test_history_comparison_keeps_camera_and_refuses_editing(qt_app, monkeypatch, command):
    """Stand 1 hat einen leeren Vorgänger: Er darf weder Bettzoom noch Bearbeitung auslösen."""
    from app.core.registry import REGISTRY
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.session.history.apply("Quader", [OperationDraft(op="create_box")])
        window.session.history.apply("Kugel", [OperationDraft(op="create_sphere")])
        window.session.evaluate_async()
        assert window.session.wait_for_idle()
        window.object_tree.select_objects(("obj_1",))
        fitted = []
        monkeypatch.setattr(window.viewport, "_fit_camera", lambda **kwargs: fitted.append(kwargs))
        panel = window.history_panel
        transactions = tuple(window.session.history.transactions)
        panel.compare.click()
        assert window.session.wait_for_idle()
        panel.timeline_slider.setValue(1)
        assert window.session.wait_for_idle()
        assert not fitted, "auch der leere Vorgänger hält den bisherigen Kamerarahmen"
        if command == "operation":
            window.launch_operation(REGISTRY.get("create_box"))
        elif command == "start_sketch":
            window.start_sketch("sketch_extrude")
        elif command == "undo":
            window.action_undo()
        else:
            getattr(window, command)()
        assert panel.compare.isChecked(), "der Befehl darf den Vergleich nicht still beenden"
        assert not window.sculpting() and not window.setting_armature()
        assert window._sketch_panel is None and window._op_dialog is None
        assert "Aktueller Stand" in window._announcement
        assert tuple(window.session.history.transactions) == transactions
        panel.timeline_end.click()
        assert window.session.wait_for_idle()
        assert not fitted, "der Rückweg hält ebenfalls den Kamerarahmen"
        assert len(window.session.last_result.scene.objects) == 2
    finally:
        monkeypatch.setattr(window, "_may_discard", lambda: True)
        window.close()
        window.release()


def test_history_comparison_does_not_replace_an_active_editor(qt_app, monkeypatch):
    """Schon die Wahl wird abgewiesen; kein Schließen-Signal stellt das Dokument darüber."""
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.session.history.apply("Quader", [OperationDraft(op="create_box")])
        window.session.evaluate_async()
        assert window.session.wait_for_idle()
        closed = []
        requested = []
        window.history_panel.previewClosed.connect(lambda: closed.append(True))
        window.history_panel.previewRequested.connect(requested.append)
        for editor in ("sculpting", "setting_armature", "sketch", "measure"):
            with monkeypatch.context() as patch:
                if editor in ("sculpting", "setting_armature"):
                    patch.setattr(window, editor, lambda: True)
                elif editor == "sketch":
                    patch.setattr(window, "_sketch_panel", object())
                else:
                    patch.setattr(
                        window, "_quiet_host", SimpleNamespace(begun=True, committing=False)
                    )
                window.history_panel.compare.click()
                assert not window.history_panel.compare.isChecked()
                assert window._announcement
                assert not closed and not requested
    finally:
        monkeypatch.setattr(window, "_may_discard", lambda: True)
        window.close()
        window.release()


def test_revision_lineage_keeps_titles_through_insert_move_undo_and_roundtrip(tmp_path):
    """Gleiche Operationen behalten ihre Namen anhand der gespeicherten Herkunft."""
    from app.core.knowledge import profiles
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import load
    from app.ui.panels import history_step_titles

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply("Rumpf", [OperationDraft(op="create_box")])
    history.apply("Kopf", [OperationDraft(op="create_sphere")])
    history.apply(
        "Kopf setzen",
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"z": 25.0})],
    )
    first = history.plan_insert(2, "Halter", [OperationDraft(op="create_box")])
    history.commit(first)
    assert history.document.transactions[-1].renumbered == first.renumbered
    assert history_step_titles(project.document)[first.new_id(2)] == "Kopf"
    assert history_step_titles(project.document)[first.new_id(3)] == "Kopf setzen"
    second = history.plan_move([first.subjects[0]], 1)
    history.commit(second)
    expected = ["Halter", "Rumpf", "Kopf", "Kopf setzen"]
    assert [
        history_step_titles(project.document)[step.id] for step in history.operations
    ] == expected
    assert all(step.id > 4 for step in history.operations), "Kennungen bleiben monoton"
    history.undo()
    assert history_step_titles(project.document)[first.new_id(2)] == "Kopf"
    history.redo()
    third = history.plan_insert(
        history.operations[-1].id, "Zweiter Halter", [OperationDraft(op="create_box")]
    )
    history.commit(third)
    expected.insert(-1, "Zweiter Halter")
    for _ in range(2):
        history.undo()
        history.redo()
    assert [
        history_step_titles(project.document)[step.id] for step in history.operations
    ] == expected
    saved = save(project, tmp_path / "lineage.p3d")
    reopened = load(saved)
    titles = history_step_titles(reopened.document)
    assert [titles[step.id] for step in History(reopened.document).operations] == expected
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    original = evaluate(project.document, profile, detect_features=False)
    restored = evaluate(reopened.document, profile, detect_features=False)
    assert original.complete and restored.complete
    assert original.object_hashes == restored.object_hashes


def test_sentences_about_steps_name_positions_after_an_early_insert():
    """RM-368 NM 3/4: Nach einem Einfügen vor Schritt 2 sprechen alle Sätze in Stellen.

    Gegenprobe vor dem Fix: Absage beim Verschieben, Nachfrage vor dem Löschen
    und Löschtitel nannten die Kennungen (7, 8 …) der umnummerierten Schritte,
    während der Verlauf 3 und 4 zeigte.
    """
    from app.core.scene.history import named_steps, step_position, step_titles

    history = History(new_project("centauri-carbon-2", "petg").document)
    history.apply("Rumpf", [OperationDraft(op="create_box")])
    history.apply("Kopf", [OperationDraft(op="create_sphere")])
    history.apply(
        "Kopf setzen",
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dz": 25.0})],
    )
    plan = history.plan_insert(2, "Halter", [OperationDraft(op="create_box")])
    history.commit(plan)
    head, placed = plan.new_id(2), plan.new_id(3)
    assert (head, placed) != (3, 4), "der Fall braucht abweichende Kennungen"
    order = history.document.ops
    assert step_position(order, head) == 3 and step_position(order, placed) == 4

    # **Nummer und Titel wie im Verlauf** (fenster.md, „Rückfragen“): Die
    # Zeile heißt „4  Kopf setzen“; „4 Verschieben“ war der Registertitel und
    # ließ den Kunden eine Zeile suchen, die es so nicht gibt (Fensterabnahme
    # RM-368, 04.10.2026).
    titles = step_titles(history.document)
    names, rest = named_steps([history.operation(placed)], order=order, titles=titles)
    assert [str(name) for name in names] == ["4 Kopf setzen"] and rest == 0

    with pytest.raises(UserError) as refused:
        history.plan_move([placed], head)
    detail = str(refused.value.detail)
    assert "Schritt 4" in detail and "Schritt 3" in detail, detail
    assert str(placed) not in detail.replace("Schritt 4", "").replace("Schritt 3", "")

    removed = history.remove_operations([placed])
    assert str(removed.title) == "Schritt löschen: 4 Kopf setzen"


def test_a_deleted_replanned_step_keeps_no_identifier_as_its_number(qt_app):
    """Ein gelöschter Schritt hat keine Stelle mehr — er zeigt keine Kennung als Nummer.

    Nach einem Einfügen vor Schritt 2 und dem Löschen von „Kopf“ standen dessen
    Zeilen als „9  Kopf“, „10  Kopf setzen“ im Verlauf, nicht durchgestrichen
    (Fensterabnahme RM-368, 04.10.2026).
    """
    from app.ui.panels import HistoryPanel

    history = History(new_project("centauri-carbon-2", "petg").document)
    history.apply("Rumpf", [OperationDraft(op="create_box")])
    history.apply("Kopf", [OperationDraft(op="create_sphere")])
    history.apply(
        "Kopf setzen",
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dz": 25.0})],
    )
    plan = history.plan_insert(2, "Halter", [OperationDraft(op="create_box")])
    history.commit(plan)
    head, placed = plan.new_id(2), plan.new_id(3)
    history.remove_operations([head, placed])
    panel = HistoryPanel()
    try:
        panel.show_document(history.document)
        texts = [panel.list.item(i).text() for i in range(panel.list.count())]
        gone = [text for text in texts if "Kopf" in text and "löschen" not in text]
        assert gone, texts
        for text in gone:
            assert not text.strip()[0].isdigit(), f"Kennung als Nummer: {text!r}"
            assert "gelöscht" in text, text
    finally:
        panel.deleteLater()


def test_revision_rows_show_positions_and_keep_stable_ids(qt_app):
    """Die zweite sichtbare Operation ist Position 2, auch wenn sie die Kennung 8 trägt."""
    from app.ui.panels import HistoryPanel

    history = _plate()
    plan = history.plan_insert(2, "Eigener Halter", [OperationDraft(op="create_sphere")])
    history.commit(plan)
    panel = HistoryPanel()
    try:
        panel.show_document(history.document)
        rows = [_row_of(panel, step.id) for step in history.operations]
        assert [row.text().strip().split("  ", 1)[0] for row in rows] == ["1", "2", "3", "4"]
        assert "Eigener Halter" in rows[1].text()
        assert "Position 3" in rows[2].toolTip()
        assert str(plan.new_id(2)) in rows[2].toolTip()
    finally:
        panel.deleteLater()


def test_inserted_history_uses_positions_in_report_status_and_dependency_tips(qt_app):
    """Kennung 5 ist nach Einfügen Position 3; Meldungen und Klickziele bleiben getrennt."""
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow
    from app.ui.panels import _origin_text
    from app.ui.session import Session

    session = Session()
    try:
        session.history.apply("Rumpf", [OperationDraft(op="create_box")])
        session.history.apply("Kopf", [OperationDraft(op="create_sphere")])
        plan = session.history.plan_insert(2, "Halter", [OperationDraft(op="create_box")])
        session.history.commit(plan)
        marker = plan.new_id(2)
        assert marker != 3
        session.start_inserting(marker)
        assert session.wait_for_idle()
        finding = next(
            item
            for item in session.last_result.scene.report.findings
            if item.code == "history.inserting"
        )
        assert "vor Schritt 3" in str(finding.message)
        assert finding.op_id == marker, "der Rückweg benutzt weiterhin die stabile Kennung"
        announced = []
        MainWindow._on_insertion_changed(
            SimpleNamespace(session=session, announce=announced.append), marker
        )
        assert announced == ["Neue Schritte kommen jetzt vor Schritt 3."]
        assert _origin_text(marker, session.project.document).startswith("aus Operation 3")
        assert (
            needs_tip(
                marker,
                [StepNeed(step=marker, on=plan.subjects[0], object_id="obj_1")],
                session.project.document,
            )
            == "Braucht Schritt 2."
        )
    finally:
        session.release()
