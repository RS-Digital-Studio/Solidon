# Was _on_features_selected vergleicht, und wer select_feature_refs / _redraw_features ruft.
import traceback as _traceback

import app.ui.main_window as _mw
import app.ui.viewport as _vp

_seen = []
_original_show = _mw.MainWindow._show_chosen_features
_original_refs = _vp.Viewport.select_feature_refs
_original_redraw = _vp.Viewport._redraw_features


def _show(self, chosen):
    shown = tuple((str(o), str(f)) for o, f in chosen)
    _seen.append(("vergleich", shown, self.viewport.highlighted_feature_refs()))
    return _original_show(self, chosen)


def _refs(self, refs):
    _seen.append(("select_feature_refs", tuple(refs), self._selected_feature_refs))
    return _original_refs(self, refs)


def _redraw(self, *args, **kwargs):
    stack = " <- ".join(f.name for f in _traceback.extract_stack(limit=6)[:-1][::-1])
    _seen.append(("_redraw_features", stack, None))
    return _original_redraw(self, *args, **kwargs)


_mw.MainWindow._show_chosen_features = _show
_vp.Viewport.select_feature_refs = _refs
_vp.Viewport._redraw_features = _redraw
_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
for _round in range(2):
    for _hole in _holes:
        idle(0.4)
        _seen.clear()
        window.object_tree.select_feature(_object_id, _hole)
        idle(0.4)
        if _round == 1:
            log(f"--- {_hole}")
            for _entry_ in _seen:
                log("  ", _entry_)
