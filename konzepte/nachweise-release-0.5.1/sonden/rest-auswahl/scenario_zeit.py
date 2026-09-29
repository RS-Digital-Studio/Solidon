# Bohrung zu Bohrung per Klick ins Bild: Zeit bis die Maße stehen, bis Ruhe, Bilder dazwischen.
# Läuft in probe.py (exec). Kein Ereignisfilter an Widgets — nur die Renderer-Bilder gezählt.
import statistics as _st
import time as _time

import numpy as _np

from app.core.scene import placement as _placement

_entry = next(iter(window.session.last_result.scene.objects.values()))
_oid = _entry.id
_holes = sorted(
    (f for f in _entry.features.values() if f.kind == "hole"),
    key=lambda f: f.id,
)
log("Bohrungen:", len(_holes), "Dreiecke:", len(_entry.mesh.raw.faces) if hasattr(_entry.mesh, "raw") else "?")
_pairs = []
for _i, _a in enumerate(_holes):
    _aa = _np.asarray(_a.params["axis"], dtype=float)
    _ca = _np.asarray(_a.params["centre"], dtype=float)
    for _b in _holes[_i + 1 :]:
        _cb = _np.asarray(_b.params["centre"], dtype=float)
        if abs(float(_np.asarray(_b.params["axis"], dtype=float) @ _aa)) > 0.99 and abs(float((_cb - _ca) @ _aa)) < 0.5:
            _d = float(_np.linalg.norm(_cb - _ca))
            if _d > 1.0:
                _pairs.append((_d, _a.id, _b.id, _a, _b))
_pairs.sort(key=lambda item: (item[0], item[1], item[2]))


def _feature_under(feature):
    view = window.viewport
    ratio = view.renderer.device_ratio()
    at = to_widget(feature.params["centre"])
    aim = view._aim_at(int(at.x() * ratio), int(at.y() * ratio))
    return None if aim is None else view._feature_at(aim)


_found = False
for _d, _n0, _n1, _h0, _h1 in _pairs[:12]:
    _a0 = _np.asarray(_h0.params["axis"], dtype=float)
    _c0 = _np.asarray(_h0.params["centre"], dtype=float)
    _c1 = _np.asarray(_h1.params["centre"], dtype=float)
    _mid = (_c0 + _c1) / 2.0
    _dist = max(60.0, 2.2 * _d)
    _up = (0.0, 0.0, 1.0) if abs(float(_a0[2])) < 0.9 else (0.0, 1.0, 0.0)
    for _axis in (_a0, -_a0):
        _eye = _mid + _axis * _dist
        window.viewport.set_camera_pose(tuple(map(float, _eye)), tuple(map(float, _mid)), _up)
        idle(0.4)
        if _feature_under(_h0) == _h0.id and _feature_under(_h1) == _h1.id:
            _found = True
            break
    if _found:
        break
log("gewählt:", _h0.id, _h0.params.get("diameter"), _h1.id, _h1.params.get("diameter"),
    "Abstand", round(_d, 2), "gefunden:", _found)

_frames: list[float] = []
_renderer = window.viewport.renderer
_orig_draw = type(_renderer)._draw


_shown_at: list[float] = []


def _counted_draw(self, *args, **kwargs):
    try:
        return _orig_draw(self, *args, **kwargs)
    finally:
        _frames.append(_time.perf_counter())
        # **Das erste Bild, zu dem die Maße stehen** — gemessen am Ende dieses
        # Bildes, nicht am Ende der Ereignisrunde der Sonde.
        if not _shown_at and _ready():
            _shown_at.append(_frames[-1])


type(_renderer)._draw = _counted_draw


def _ready() -> bool:
    flow = window._quiet_placement
    return (
        flow is not None
        and (flow._surface is not None or getattr(flow, "_measure_without_surface", False))
        and not flow._surface_busy
        and not flow._measure_box.isHidden()
    )


def _one(feature) -> tuple[float, float, int, str]:
    target = to_widget(feature.params["centre"])
    send(QEvent.Type.MouseMove, target, Qt.MouseButton.NoButton)
    pump(0.25)
    idle(0.3)
    _frames.clear()
    _shown_at.clear()
    left = Qt.MouseButton.LeftButton
    t0 = _time.perf_counter()
    send(QEvent.Type.MouseButtonPress, target, left, left)
    send(QEvent.Type.MouseButtonRelease, target, Qt.MouseButton.NoButton, left)
    measures = None
    while _time.perf_counter() - t0 < 20.0:
        application.processEvents()
        _time.sleep(0.0005)
        if _ready():
            measures = (_time.perf_counter() - t0) * 1000.0
            break
    end = _time.perf_counter() + 0.4
    while _time.perf_counter() < end:
        application.processEvents()
        _time.sleep(0.0005)
    after = [f for f in _frames if f >= t0]
    rest = (max(after) - t0) * 1000.0 if after else float("nan")
    # Die Maße stehen mit dem ersten Bild, das sie zeigt; ohne ein solches
    # Bild gilt die Runde der Sonde (``measures``).
    if _shown_at:
        measures = (_shown_at[0] - t0) * 1000.0
    return (measures if measures is not None else float("nan")), rest, len(after), str(
        window.object_tree.selected_feature()
    )


# Körper wählen, dann beide Bohrungen einmal kalt.
click(to_widget(_h0.params["centre"]))
idle(0.8)
for _label, _f in (("kalt0", _h0), ("kalt1", _h1)):
    _m, _r, _n, _sel = _one(_f)
    log(f"{_label} {_f.id}: Maße {_m:7.1f} ms, Ruhe {_r:7.1f} ms, Bilder {_n}, gewählt {_sel}")
    idle(0.6)
_ms, _rs, _ns = [], [], []
for _round in range(4):
    for _f in (_h0, _h1):
        _m, _r, _n, _sel = _one(_f)
        _ms.append(_m)
        _rs.append(_r)
        _ns.append(_n)
        log(f"KLICK {_f.id}: Maße {_m:7.1f} ms, Ruhe {_r:7.1f} ms, Bilder {_n}, gewählt {_sel}")
        idle(0.6)
_flow = window._quiet_placement
if _flow is not None:
    log(
        "Maßfelder:",
        [
            field.text()
            for field in (*_flow._measures, *_flow._centre_measures)
            if not field.isHidden()
        ],
    )
log(
    "ERGEBNIS Maße Median", round(_st.median(_ms), 1), "ms; Ruhe Median", round(_st.median(_rs), 1),
    "ms; Bilder Median", _st.median(_ns),
)
