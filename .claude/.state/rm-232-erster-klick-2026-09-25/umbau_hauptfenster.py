"""Einmalig: RM-232 — die Kernauskünfte eines großen Körpers im Arbeiter."""

from __future__ import annotations

from pathlib import Path

path = Path("app/ui/main_window.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str) -> None:
    global text
    assert text.count(old) == 1, (text.count(old), old[:100])
    text = text.replace(old, new)


swap(
    '''class _MapWorker(Worker):
    """Eine Analysekarte, abseits des Oberflächen-Threads (§18.9).
''',
    '''#: Ab wie vielen Dreiecken das Merkmalfenster seine Kernauskünfte im Arbeiter
#: rechnen lässt (RM-232). Darunter kosten sie beim ersten Klick unter 50 ms —
#: am Wabenhalter mit 7 956 Dreiecken 45 ms samt kalter Körpermerker —, und ein
#: Zwischenzustand flackerte nur; an der dichten Platte mit 204 000 Dreiecken
#: waren es 130 ms im Hauptfaden, und jede weitere Bohrung kostete beim ersten
#: Klick noch 60.
ANSWERS_IN_WORKER_FROM: Final = 20_000


class _FeatureAnswersWorker(Worker):
    """Die Kernauskünfte des Merkmalfensters abseits des Hauptfadens (RM-232).

    Gerechnet wird an der Arbeiterkopie des Netzes und unter ihrem Schloss
    (``placement_flow.for_a_worker``, ``on_the_copy``): Die trägen trimesh-
    Merker sind nicht threadsicher, und dieselbe Kopie nimmt danach der
    Platzierungsfluss — was hier warm wird, bleibt es dort.
    """

    done = Signal(object)

    def __init__(self, compute: Callable[[], Any]) -> None:
        super().__init__()
        self._compute = compute

    def work(self) -> None:
        self.done.emit(self._compute())


class _MapWorker(Worker):
    """Eine Analysekarte, abseits des Oberflächen-Threads (§18.9).
''',
)
swap(
    '''        self._map_worker: Any = None
        self._map_request: _MapRequest | None = None
''',
    '''        self._map_worker: Any = None
        self._answers_worker: _FeatureAnswersWorker | None = None
        """Rechnet gerade die Kernauskünfte eines großen Körpers (RM-232)."""
        self._map_request: _MapRequest | None = None
''',
)
swap(
    '''    def _show_feature_fields(
        self, feature_id: str, entry: Any, result: EvaluationResult | None
    ) -> None:
        """Merkmalsmaße und belegte Originalwerte für Panel und Maßgruppe vorbereiten.

        Zwei Wege enden hier: die einzeln angeklickte Zeile und die Bohrung
        mit ihrer Senkung, die als **zwei** Merkmale gemeldet wird und
        trotzdem eine Wahl ist (:meth:`_on_features_selected`). Zweimal
        dieselben fünf Zeilen zu schreiben hieße, dass die eine Stelle beim
        nächsten Nachbessern die andere vergisst.
        """
''',
    '''    def _show_feature_fields(
        self,
        feature_id: str,
        entry: Any,
        result: EvaluationResult | None,
        *,
        allow_worker: bool = True,
    ) -> None:
        """Merkmalsmaße und belegte Originalwerte für Panel und Maßgruppe vorbereiten.

        Zwei Wege enden hier: die einzeln angeklickte Zeile und die Bohrung
        mit ihrer Senkung, die als **zwei** Merkmale gemeldet wird und
        trotzdem eine Wahl ist (:meth:`_on_features_selected`). Zweimal
        dieselben fünf Zeilen zu schreiben hieße, dass die eine Stelle beim
        nächsten Nachbessern die andere vergisst.

        **An einem großen Körper antwortet der Kern im Arbeiter** (RM-232,
        :meth:`_answer_in_worker`): Kennt das Fenster die Handlungen des
        Merkmals noch nicht, zeigt es Name und Maß, und der ganze Aufbau
        läuft noch einmal, sobald die Antwort da ist — ``allow_worker=False``,
        damit es dabei bleibt.
        """
''',
)
swap(
    '''            self.feature_dock.reveal()
            self._start_feature_preview()
            return
        self.feature_panel.show_feature(
            feature_id,
            feature,
            features=entry.features,
            mesh=as_mesh_data(entry.mesh),
''',
    '''            self.feature_dock.reveal()
            self._start_feature_preview()
            return
        mesh = as_mesh_data(entry.mesh)
        if (
            allow_worker
            and mesh.triangle_count >= ANSWERS_IN_WORKER_FROM
            and self.feature_panel.known_answers(feature_id, feature, entry.features, mesh) is None
        ):
            self._answer_in_worker(feature_id, entry, result)
            return
        self.feature_panel.show_feature(
            feature_id,
            feature,
            features=entry.features,
            mesh=mesh,
''',
)
swap(
    '''    def _close_the_other_way(self) -> None:''',
    '''    def _answer_in_worker(
        self, feature_id: str, entry: Any, result: EvaluationResult | None
    ) -> None:
        """Die Kernauskünfte eines großen Körpers im Arbeiter holen (RM-232).

        Hohlraumkette, Handlungen und gleichartige Geschwister kosteten an der
        dichten Platte beim ersten Klick 130 ms im Hauptfaden. Bis sie da sind,
        stehen Name und Maß im Fenster (``FeaturePanel.show_pending``); eine
        Zeile, die etwas anbietet, gibt es in dieser Zeit nicht. Ein neuer
        Klick löst den laufenden Arbeiter ab.
        """
        from app.ui.panels import feature_answers
        from app.ui.placement_flow import for_a_worker, on_the_copy

        feature = entry.features[feature_id]
        features = entry.features
        self.feature_panel.show_pending(feature_id, feature)
        self.feature_dock.reveal()
        copy = for_a_worker(entry.mesh)
        compute = on_the_copy(copy, lambda: feature_answers(feature_id, feature, features, copy))
        worker = _FeatureAnswersWorker(compute)
        request = (entry.id, feature_id, result)
        worker.done.connect(
            weak_slot(self, MainWindow._answers_arrived, request, worker, forward=True)
        )
        worker.crashed.connect(weak_slot(self, MainWindow._answers_failed, worker, forward=True))
        worker.finished.connect(weak_slot(self, MainWindow._answers_worker_done, worker))
        if self._answers_worker is not None:
            self._retire(self._answers_worker)
        self._answers_worker = worker
        self._leash.start(worker)

    def _answers_arrived(
        self,
        request: tuple[str, str, EvaluationResult | None],
        worker: _FeatureAnswersWorker,
        answers: Any,
    ) -> None:
        """Die Antwort merken — und aufbauen, wenn noch dieses Merkmal gewählt ist.

        Gemerkt wird auch die Antwort eines abgelösten Arbeiters, solange die
        Auswertung dieselbe ist: Sie gilt weiter für ihr Merkmal, und der
        nächste Klick darauf braucht sie. Aufgebaut wird nur, was noch
        gewählt ist.
        """
        object_id, feature_id, result = request
        if result is None or result is not self.session.last_result:
            return
        entry = result.scene.objects.get(object_id)
        feature = entry.features.get(feature_id) if entry is not None else None
        if feature is None:
            return
        self.feature_panel.remember_answers(
            feature_id, feature, entry.features, as_mesh_data(entry.mesh), answers
        )
        if worker is not self._answers_worker:
            return
        if (
            self.object_tree.selected() != object_id
            or self.object_tree.selected_feature() != feature_id
        ):
            return
        self._show_feature_fields(feature_id, entry, result, allow_worker=False)

    def _answers_failed(self, worker: _FeatureAnswersWorker, detail: str) -> None:
        """Ein Programmfehler im Arbeiter ist einer — mit Fehlerbericht, ohne Wartezustand."""
        if worker is not self._answers_worker:
            return
        self.feature_panel.clear()
        self._on_error(InternalError(detail=detail))

    def _answers_worker_done(self, worker: _FeatureAnswersWorker) -> None:
        """Den eigenen Arbeiter loslassen, erst wenn Qt mit ihm durch ist."""
        if self._answers_worker is worker:
            self._answers_worker = None
        self._hold_until_done(worker)

    def _close_the_other_way(self) -> None:''',
)
swap(
    '''        workers = (
            self._map_worker,
            self._slice_worker,
''',
    '''        workers = (
            self._map_worker,
            self._answers_worker,
            self._slice_worker,
''',
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
