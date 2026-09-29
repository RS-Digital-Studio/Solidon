# Zug im gewählten Loch zum Langloch: Stehen danach Maße im Bild, auch nach
# einer Kameradrehung? (Gegenprobe zum roten Fenstertest
# test_the_measures_stay_in_the_view_while_a_pulled_slot_waits.) Läuft in probe.py (exec).
import numpy as _np2

exec((HERE / "scenario_zeit.py").read_text(encoding="utf-8").split("# Körper wählen")[0])
_view = window.viewport
_seen = []
for _name in ("placementDragged", "placementDragStarted", "slotProposed", "slotDragged", "featureMoveProposed"):
    getattr(_view, _name).connect(lambda *args, _n=_name: _seen.append(_n))
_orig_dispatch = type(_view)._dispatch_pointer


def _traced(self, event):
    _orig_dispatch(self, event)
    if event.kind in ("press", "release"):
        held = {
            a: getattr(getattr(self, a), "pressing", None)
            for a in ("_placement_grip", "_gizmo", "_slot_handle")
            if getattr(self, a) is not None
        }
        _seen.append(f"{event.kind}->{held}")


type(_view)._dispatch_pointer = _traced


def _state(label):
    flow = window._quiet_placement
    fields = []
    if flow is not None:
        fields = [f.text() for f in (*flow._measures, *flow._centre_measures) if not f.isHidden()]
    log(
        f"{label}: gewählt={window.object_tree.selected_feature()} "
        f"fluss={None if flow is None else flow.spec_of().name} "
        f"begonnen={getattr(window._quiet_host, 'begun', None)} "
        f"bild={None if flow is None else flow._canvas.shown} "
        f"linien={None if flow is None else len(flow._canvas.lines)} "
        f"umriss={None if flow is None else len(flow._canvas.outline)} "
        f"langloch_wartet={_view.slot_drag_waits()} "
        f"knoepfe={_view._slot_handle is not None} "
        f"langlochmerkmal={getattr(_view.slot_handle_feature(), 'id', None)} "
        f"schritte={[op.op for op in window.session.project.document.ops]}"
    )
    log("   Maße:", fields)
    log("   Signale:", list(_seen))
    _seen.clear()


click(to_widget(_h0.params["centre"]))
idle(0.8)
_one(_h1)
idle(0.5)
_state("A hole_4 gewählt")
from app.ui.viewport import slot_feature_kinds as _sfk  # noqa: E402

_sel = _view._selected_feature
_feats = _view._features_of_selection()
log("   Ansicht: _selected_feature", repr(_sel), "Arten", sorted(_sfk()), "vorhanden", sorted(_feats)[:8])
_f = _feats.get(_sel) if _sel is not None else None
log("   Merkmal:", None if _f is None else (_f.kind, sorted(_f.params)))
log("   gesperrt:", _view._feature_gizmo_blocked, "knöpfe bleiben:", _view._knobs_stay, "gewollt:", _view._gizmo_wanted)
_axis = _np2.asarray(_h1.params["axis"], dtype=float)
_side = _np2.cross(_axis, (0.0, 0.0, 1.0) if abs(_axis[2]) < 0.9 else (1.0, 0.0, 0.0))
_side = _side / _np2.linalg.norm(_side)
_c = _np2.asarray(_h1.params["centre"], dtype=float)
_diag = _side + _np2.cross(_axis, _side)
_diag = _diag / _np2.linalg.norm(_diag)
start = to_widget(tuple(_c + 1.6 * _diag))
end = to_widget(tuple(_c + 7.0 * _diag))
left = Qt.MouseButton.LeftButton
send(QEvent.Type.MouseMove, start, Qt.MouseButton.NoButton)
pump(0.2)
send(QEvent.Type.MouseButtonPress, start, left, left)
for _k in range(1, 11):
    _p = QPointF(start.x() + (end.x() - start.x()) * _k / 10, start.y() + (end.y() - start.y()) * _k / 10)
    send(QEvent.Type.MouseMove, _p, left)
    pump(0.02)
send(QEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton, left)
idle(1.0)
_state("B nach dem Zug zum Langloch")
window.viewport.cameraMoved.emit()
pump(0.3)
idle(0.5)
_state("C nach cameraMoved")
