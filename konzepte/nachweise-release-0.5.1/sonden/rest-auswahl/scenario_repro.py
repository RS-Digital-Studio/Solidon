# Zweiter Klick auf die gewählte Bohrung (Griffmitte), danach Klicks auf die
# Nachbarbohrung: Wechselt die Auswahl? Läuft in probe.py (exec).
exec((HERE / "scenario_zeit.py").read_text(encoding="utf-8").split("# Körper wählen")[0])

_view = window.viewport
_signals = []
for _name in (
    "placementDragged",
    "placementDragStarted",
    "featureMoveProposed",
    "featureMoved",
    "slotProposed",
    "slotDragged",
    "transformDragged",
    "previewDragged",
):
    _sig = getattr(_view, _name, None)
    if _sig is not None:
        _sig.connect(lambda *args, _n=_name: _signals.append(_n))

_consumer = []
for _attr in ("_placement_grip", "_preview_gizmo", "_gizmo", "_scale_handle", "_slot_handle"):
    pass

_orig_dispatch = type(_view)._dispatch_pointer


def _traced_dispatch(self, event):
    if event.kind in ("press", "release"):
        before = {
            a: (getattr(self, a) is not None and getattr(getattr(self, a), "pressing", None))
            for a in ("_placement_grip", "_preview_gizmo", "_gizmo", "_scale_handle", "_slot_handle")
        }
        _consumer.append(f"{event.kind}:{ {k: v for k, v in before.items() if v is not False} }")
    _orig_dispatch(self, event)
    if event.kind in ("press", "release"):
        after = {
            a: getattr(getattr(self, a), "pressing", None)
            for a in ("_placement_grip", "_preview_gizmo", "_gizmo", "_scale_handle", "_slot_handle")
            if getattr(self, a) is not None
        }
        _consumer.append(f"  nach {event.kind}: {after} drag={self._drag_kind}")


type(_view)._dispatch_pointer = _traced_dispatch


def _state(label):
    flow = window._quiet_placement
    fields = []
    if flow is not None:
        fields = [f.text() for f in (*flow._measures, *flow._centre_measures) if not f.isHidden()]
    log(
        f"{label}: gewählt={window.object_tree.selected_feature()} "
        f"fluss={'ja' if flow is not None else 'nein'} "
        f"sitzt={getattr(flow, '_seated_at_feature', None)} "
        f"frozen={getattr(flow, '_frozen', None)} "
        f"surface={'ja' if getattr(flow, '_surface', None) is not None else 'nein'} "
        f"move_target={_view._move_target!r} shift={_view._grip_shift} "
        f"slot_waiting={_view._slot_waiting is not None} borrowed={_view._slot_borrowed} "
        f"schritte={len(window.session.project.document.ops)}"
    )
    log("   Maße:", fields)
    log("   Signale:", list(_signals))
    for line in _consumer:
        log("   ", line)
    _signals.clear()
    _consumer.clear()


def _step(label, feature):
    _one(feature)
    idle(0.5)
    _state(f"{label} ({feature.id})")


click(to_widget(_h0.params["centre"]))
idle(0.8)
_state("Körper")
_step("1 Klick", _h0)
_step("2 Klick", _h1)
_step("3 zweiter Klick auf gewählte", _h1)
_step("4 Klick Nachbar", _h0)
_step("5 Klick", _h1)
_step("6 Klick", _h0)
