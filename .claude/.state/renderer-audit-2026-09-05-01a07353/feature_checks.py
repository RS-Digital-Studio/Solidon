"""Merkmale mit echten Qt-Eingaben prüfen; Dokumentänderungen nur über die UI."""

from __future__ import annotations

import hashlib
import json
import math
import time
import traceback

import numpy as np
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QPushButton

from app.core.perceive.actions import actions_for
from app.ui.labels import LengthSpin, display_unit


def fingerprint(probe):
    """Geometrie und Merkmalsbezüge aller Körper unabhängig von der Ansicht lesen."""
    result = probe.session.last_result
    if result is None:
        return None
    digest = hashlib.sha256()
    bodies = []
    for oid, obj in sorted(result.scene.objects.items()):
        mesh = obj.mesh
        body = hashlib.sha256()
        for array in (mesh.raw.vertices, mesh.raw.faces):
            data = np.asarray(array)
            body.update(str((data.shape, data.dtype.str)).encode())
            body.update(data.tobytes())
        metadata = {
            "id": str(oid), "name": str(obj.name), "kind": obj.kind, "plate": obj.plate,
            "features": {
                str(fid): {"kind": feature.kind, "params": probe.plain(dict(feature.params)),
                           "face_count": len(feature.face_indices),
                           "face_hash": hashlib.sha256(np.asarray(feature.face_indices, dtype=np.int64).tobytes()).hexdigest()}
                for fid, feature in sorted(obj.features.items())
            },
        }
        body.update(json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode())
        value = body.hexdigest()
        digest.update(value.encode())
        bodies.append({"id": str(oid), "hash": value, "volume": float(mesh.volume),
                       "triangles": mesh.triangle_count, "watertight": mesh.is_watertight})
    return {"hash": digest.hexdigest(), "bodies": bodies}


def _item(probe, oid, fid=None):
    for item in probe.tree_items():
        if str(item.data(0, Qt.ItemDataRole.UserRole)) != str(oid):
            continue
        value = item.data(1, Qt.ItemDataRole.UserRole)
        if (fid is None and not value) or (fid is not None and str(value) == str(fid)):
            return item
    raise LookupError(f"Baumzeile fehlt: {oid} / {fid}")


def _choose(probe, oid, fid):
    for attempt in range(3):
        probe.select_item(_item(probe, oid, fid))
        selected = probe.window.feature_panel.feature_id
        bodies = probe.window.object_tree.selected_objects()
        if selected == fid and str(oid) in [str(body) for body in bodies]:
            break
        probe.log("Merkmalsauswahl wird nachgeklickt", object=oid, feature=fid,
                  selected=selected, bodies=bodies, attempt=attempt + 1)
        probe.settle(550)
    else:
        raise AssertionError(f"Baumklick wählte {selected}, erwartet {fid} an {oid}")
    if not probe.window.feature_dock.isVisible():
        probe.menu(probe.window.feature_dock.toggleViewAction())
    probe.settle(80)


def _quiet(probe):
    probe.wait("Merkmalsarbeiter beendet", lambda: not probe.session.busy and not probe.session._previews, 180)
    probe.wait("Viewport folgt Ergebnis", lambda: probe.window.viewport._result is probe.session.last_result, 30)


def _row(probe, title):
    for row in probe.window.feature_panel._built:
        buttons = row.findChildren(QPushButton)
        button = next((button for button in buttons if button.text() == str(title)), None)
        if button is not None:
            return row, button
    raise LookupError(f"Panelhandlung fehlt: {title}")


def _fields(row, action):
    """Feldzuordnung aus demselben Formular lesen, ohne Signale selbst auszulösen."""
    forms = row.findChildren(QFormLayout)
    editors = []
    for form in forms:
        for index in range(form.rowCount()):
            item = form.itemAt(index, QFormLayout.ItemRole.FieldRole)
            if item is not None and item.widget() is not None:
                editors.append(item.widget())
    if len(editors) != len(action.fields):
        raise AssertionError(f"{action.op}: {len(editors)} sichtbare Felder für {len(action.fields)} Parameter")
    return {field.name: editor for field, editor in zip(action.fields, editors)}


def _number(probe, editor, value):
    """Zahl tippen wie ein Kunde; weder setValue noch Änderungssignal verwenden."""
    if not isinstance(editor, QDoubleSpinBox):
        raise TypeError(f"Kein Zahlenfeld: {type(editor).__name__}")
    shown = float(value)
    unit_scale = 1.0
    if isinstance(editor, LengthSpin):
        # Die gerundete Anzeige darf niemals den Umrechnungsfaktor liefern:
        # -0,000013 mm erscheint als 0,00 und ergäbe sonst den Faktor null.
        unit = editor.suffix().strip()
        if unit not in ("mm", "in"):
            unit = display_unit()
        unit_scale = 25.4 if unit == "in" else 1.0
        shown /= unit_scale
    text = editor.locale().toString(shown, "f", editor.decimals())
    edit = editor.lineEdit()
    probe.click(editor)
    QTest.keyClick(edit, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(edit, text)
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    probe.settle(100)
    actual = float(editor.value_mm()) if isinstance(editor, LengthSpin) else float(editor.value())
    allowance = max(1e-5, 10 ** (-editor.decimals()) * unit_scale * 1.1)
    if not math.isclose(actual, value, rel_tol=0, abs_tol=allowance):
        raise AssertionError(f"Zahleneingabe {text}: gelesen {actual}, erwartet {value}")
    return actual


def _set_fields(probe, editors, values):
    actual = {}
    for name, value in values.items():
        editor = editors[name]
        if isinstance(editor, QCheckBox):
            if editor.isChecked() != bool(value):
                probe.click(editor)
            actual[name] = editor.isChecked()
        elif isinstance(editor, QComboBox):
            index = editor.findData(value)
            if index < 0:
                raise LookupError(f"Auswahl fehlt: {name}={value}")
            probe.click(editor)
            QTest.keyClick(editor, Qt.Key.Key_Home)
            for _ in range(index):
                QTest.keyClick(editor, Qt.Key.Key_Down)
            QTest.keyClick(editor, Qt.Key.Key_Return)
            probe.settle(60)
            actual[name] = editor.currentData()
        else:
            actual[name] = _number(probe, editor, float(value))
    return actual


def _history(probe, redo=False):
    """UI-Transaktion und das danach gemeldete Auswertungsergebnis getrennt prüfen."""
    count = len(probe.session.project.document.transactions)
    expected = count + (1 if redo else -1)
    errors_before = len(probe.errors)
    finished = []

    def received(result):
        finished.append(result)

    probe.session.sceneChanged.connect(received)
    try:
        probe.menu(probe.window.redo_action if redo else probe.window.undo_action)
        # History.undo/redo ändert die Transaktionsliste synchron im Klick.
        # Ein nicht zugestellter Klick darf keine dreiminütige Rechenwartezeit
        # auslösen. probe.menu bestätigt bereits das echte QAction-Signal.
        try:
            probe.wait("Menüklick ändert Verlauf", lambda:
                       len(probe.session.project.document.transactions) == expected, 3)
        except TimeoutError:
            probe.log("Verlaufsklick änderte keine Transaktion", redo=redo, before=count,
                      expected=expected, actual=len(probe.session.project.document.transactions),
                      busy=probe.session.busy, results_received=len(finished),
                      errors=probe.errors[errors_before:])
            raise
        probe.log("Verlaufsklick bestätigt", redo=redo, before=count, after=expected,
                  busy=probe.session.busy, results_received=len(finished))
        probe.wait("Verlaufsschritt ausgewertet", lambda: not probe.session.busy and
                   (bool(finished) or len(probe.errors) > errors_before), 180)
        if not finished:
            raise AssertionError("Verlaufsauswertung meldete einen Fehler: " +
                                 "; ".join(probe.errors[errors_before:]))
        _quiet(probe)
    finally:
        probe.session.sceneChanged.disconnect(received)


def _restore(probe, baseline, count, oid):
    """Nur eigene UI-Transaktionen zurücknehmen; die eingelesene Datei bleibt stehen."""
    if probe.session.busy:
        cancel = probe.window.veil.cancel
        if cancel.isVisible() and cancel.isEnabled():
            started = time.monotonic()
            probe.click(cancel)
            probe.wait("Lange Merkmalsänderung über sichtbaren Knopf abbrechen",
                       lambda: not probe.session.busy, 120)
            probe.log("Lange Merkmalsänderung nach Prüfzeit über Oberfläche abgebrochen",
                      status="probe_cancelled_after_timeout", seconds=time.monotonic() - started)
    if not probe.session.busy:
        try:
            probe.select_item(_item(probe, oid))
        except LookupError:
            pass
    _quiet(probe)
    current = len(probe.session.project.document.transactions)
    if current < count or current > count + 2:
        raise AssertionError(f"Unerwartete Verlaufslänge: {current}, Ausgang {count}")
    while len(probe.session.project.document.transactions) > count:
        _history(probe)
    restored = fingerprint(probe)
    if restored != baseline:
        probe.log("Ausgangszustand NICHT wiederhergestellt", expected=baseline, actual=restored)
        raise AssertionError("Merkmalsprüfung angehalten: Undo stellt Ausgangszustand nicht her")


def _perform(probe, oid, fid, action, values, label, number, *, all_alike=False):
    baseline = fingerprint(probe)
    original = probe.session.last_result.scene.objects[oid]
    feature_before = original.features[fid]
    count = len(probe.session.project.document.transactions)
    errors_before = len(probe.errors)
    start = time.monotonic()
    try:
        _choose(probe, oid, fid)
        row, button = _row(probe, action.title)
        editors = _fields(row, action)
        actual = _set_fields(probe, editors, values)
        if all_alike:
            check = next((box for box in row.findChildren(QCheckBox)
                          if box.text().startswith("Auf alle ")), None)
            if check is None:
                raise AssertionError("Checkbox für Sammelhandlung fehlt")
            probe.click(check)
        probe.log("Merkmalshandlung vorbereitet", object=oid, feature=fid, op=action.op,
                  variant=label, values=actual, all_alike=all_alike,
                  preview_pending=probe.window._feature_pending is not None,
                  document_unchanged=fingerprint(probe) == baseline)
        if fingerprint(probe) != baseline or len(probe.session.project.document.transactions) != count:
            raise AssertionError("Vorschau hat das Dokument bereits verändert")
        previous = probe.session.last_result
        probe.click(button)
        probe.wait("Merkmalshandlung ausgewertet", lambda: not probe.session.busy and
                   (probe.session.last_result is not previous or len(probe.errors) > errors_before), 180)
        _quiet(probe)
        result = probe.session.last_result
        after = fingerprint(probe)
        delta = len(probe.session.project.document.transactions) - count
        findings = [probe.plain(f) for f in result.scene.report.findings]
        changed_object = result.scene.objects.get(oid)
        feature_after = changed_object.features.get(fid) if changed_object else None
        measured = {"before": probe.plain(dict(feature_before.params)),
                    "after": probe.plain(dict(feature_after.params)) if feature_after else None}
        semantic = {}
        if result.stopped_at is None and changed_object is not None:
            if action.op in ("resize_feature", "resize_hole") and feature_after is not None:
                semantic["diameter_matches"] = math.isclose(
                    float(feature_after.params.get("diameter", math.nan)),
                    float(actual["diameter"]), rel_tol=0.02, abs_tol=0.12)
                if all_alike:
                    sibling_ids = [key for key, item in original.features.items() if item.kind == feature_before.kind]
                    semantic["all_sibling_diameters_match"] = all(
                        key in changed_object.features and math.isclose(
                            float(changed_object.features[key].params.get("diameter", math.nan)),
                            float(actual["diameter"]), rel_tol=0.02, abs_tol=0.12)
                        for key in sibling_ids)
            elif action.op == "move_feature" and feature_after is not None:
                centre = feature_after.params.get("centre", ())
                semantic["position_matches"] = len(centre) == 3 and all(
                    math.isclose(float(centre["xyz".index(key)]), float(value), rel_tol=0, abs_tol=0.15)
                    for key, value in actual.items() if key in "xyz")
            elif action.op == "remove_feature":
                semantic["original_id_removed"] = feature_after is None
            elif action.op == "duplicate_feature":
                new_ids = [str(key) for key, item in changed_object.features.items()
                           if key not in original.features and item.kind == feature_before.kind]
                semantic["original_kept"] = feature_after is not None
                semantic["copy_has_own_id"] = bool(new_ids)
                measured["new_ids"] = new_ids
            before_other = {body["id"]: body["hash"] for body in baseline["bodies"] if body["id"] != str(oid)}
            after_other = {body["id"]: body["hash"] for body in after["bodies"] if body["id"] != str(oid)}
            semantic["other_bodies_unchanged"] = before_other == after_other
        probe.log("Merkmalshandlung Ergebnis", object=oid, feature=fid, op=action.op,
                  variant=label, seconds=time.monotonic() - start, transaction_delta=delta,
                  changed=after != baseline, stopped_at=probe.plain(result.stopped_at),
                  errors=probe.errors[errors_before:], fingerprints={"before": baseline, "after": after},
                  findings=findings, measurements=measured, semantic_checks=semantic)
        probe.shot(f"30-feature-{number:02d}-{action.op}-{label}")
        if delta != 1:
            raise AssertionError(f"Eine Handlung erzeugte {delta} Transaktionen")
        _history(probe)
        undo = fingerprint(probe)
        probe.log("Merkmalshandlung Undo", op=action.op, variant=label, same=undo == baseline)
        if undo != baseline:
            raise AssertionError("Undo weicht vom Ausgangszustand ab")
        _history(probe, redo=True)
        redone = fingerprint(probe)
        probe.log("Merkmalshandlung Redo", op=action.op, variant=label, same=redone == after)
        if redone != after:
            raise AssertionError("Redo reproduziert das Ergebnis nicht")
        _history(probe)
        last = fingerprint(probe)
        probe.log("Merkmalshandlung zweites Undo", op=action.op, variant=label, same=last == baseline)
        if last != baseline:
            raise AssertionError("Zweites Undo weicht vom Ausgangszustand ab")
    except Exception:
        probe.log("Merkmalshandlung Prüffehler", object=oid, feature=fid, op=action.op,
                  variant=label, error=traceback.format_exc(), errors=probe.errors[errors_before:])
    finally:
        _restore(probe, baseline, count, oid)


def _positions(obj, feature, *, duplicate=False):
    centre = np.asarray(feature.params.get("centre", ()), dtype=float)
    if centre.shape != (3,) or not np.isfinite(centre).all():
        return None
    axis = np.asarray(feature.params.get("axis", (0, 0, 1)), dtype=float)
    if axis.shape != (3,) or not np.isfinite(axis).all():
        axis = np.array((0, 0, 1))
    low = np.asarray(obj.mesh.bounds.minimum)
    high = np.asarray(obj.mesh.bounds.maximum)
    diameter = float(feature.params.get("diameter", 1.0))
    candidates = []
    for index in range(3):
        if abs(axis[index]) > 0.8:
            continue
        for direction in (-1, 1):
            room = (high[index] - centre[index]) if direction > 0 else (centre[index] - low[index])
            candidates.append((room, index, direction))
    if not candidates:
        return None
    room, index, direction = max(candidates)
    distance = max(0.2, min(0.5, diameter * 0.1))
    if duplicate:
        distance = max(1.0, diameter * 1.25)
        if room < distance + diameter * 0.5:
            return None
    target = centre.copy()
    target[index] += distance * direction
    return {"xyz"[index]: float(target[index])}


def _viewport_click(probe, oid, fid, feature):
    """Sichtbare Geometriestelle projizieren und anschließend wirklich mit Qt klicken."""
    viewport = probe.window.viewport
    plotter = viewport.plotter
    if plotter is None:
        probe.log("Viewportklick ausgelassen", object=oid, feature=fid, reason="Kein nativer Plotter")
        return
    probe.select_item(_item(probe, oid))
    obj = probe.session.last_result.scene.objects[oid]
    centres = []
    centre = feature.params.get("centre")
    if centre is not None and len(centre) == 3:
        centres.append(centre)
    faces = list(feature.face_indices)
    if faces:
        chosen = np.linspace(0, len(faces) - 1, min(40, len(faces)), dtype=int)
        indices = np.array([faces[int(index)] for index in chosen], dtype=int)
        indices = indices[(indices >= 0) & (indices < len(obj.mesh.raw.faces))]
        centres.extend(obj.mesh.raw.vertices[obj.mesh.raw.faces[indices]].mean(axis=1))
    ratio = float(plotter.interactor.devicePixelRatioF()) or 1.0
    height = plotter.interactor.height()
    for point in centres:
        world = viewport.view_point_of(tuple(float(v) for v in point), oid)
        renderer = plotter.renderer
        renderer.SetWorldPoint(*world, 1.0)
        renderer.WorldToDisplay()
        display = renderer.GetDisplayPoint()
        qt_point = QPoint(round(display[0] / ratio), round(height - display[1] / ratio))
        if not plotter.interactor.rect().adjusted(8, 8, -8, -8).contains(qt_point):
            continue
        # Nur lesendes Picking wählt einen belastbaren sichtbaren Testpunkt.
        hit = viewport._aim_at(round(display[0]), round(display[1]))
        if hit is None or viewport._feature_at(hit) != fid:
            continue
        QTest.mouseMove(plotter.interactor, qt_point)
        QTest.mouseClick(plotter.interactor, Qt.MouseButton.LeftButton, pos=qt_point)
        probe.settle(200)
        selected = probe.window.feature_panel.feature_id
        probe.log("Echter Viewportklick", object=oid, feature=fid, selected=selected,
                  point=[qt_point.x(), qt_point.y()], passed=selected == fid)
        return
    probe.log("Viewportklick ausgelassen", object=oid, feature=fid,
              reason="Keine eindeutig sichtbare projizierte Merkmalsfläche in der aktuellen Kamera")


def _preview_abort(probe, oid, fid, action, values):
    baseline = fingerprint(probe)
    count = len(probe.session.project.document.transactions)
    try:
        _choose(probe, oid, fid)
        row, _button = _row(probe, action.title)
        _set_fields(probe, _fields(row, action), values)
        probe.settle(450)
        started = bool(probe.session._previews or probe.window._preview_shown)
        probe.select_item(_item(probe, oid))
        _quiet(probe)
        probe.log("Merkmalsvorschau durch Auswahlwechsel verworfen", object=oid, feature=fid,
                  started=started, document_unchanged=fingerprint(probe) == baseline,
                  transaction_unchanged=len(probe.session.project.document.transactions) == count,
                  pending=probe.window._feature_pending is not None,
                  shown=bool(probe.window._preview_shown))
        if fingerprint(probe) != baseline or probe.window._feature_pending is not None or probe.window._preview_shown:
            raise AssertionError("Auswahlwechsel ließ Vorschau oder Dokumentänderung zurück")
    except Exception:
        probe.log("Vorschau-Abbruch Prüffehler", error=traceback.format_exc())
    finally:
        _restore(probe, baseline, count, oid)


def run(probe):
    """Eine geometrisch geeignete Stelle je vorhandener Art über alle Körper prüfen."""
    import wait_driver
    wait_driver.install(probe)
    import menu_driver
    menu_driver.install(probe)
    _quiet(probe)
    all_features = {}
    for oid, obj in probe.session.last_result.scene.objects.items():
        for fid, feature in obj.features.items():
            all_features.setdefault(feature.kind, []).append((oid, fid, feature))
    completed = 0
    for kind, candidates in sorted(all_features.items()):
        def score(entry):
            oid, _fid, feature = entry
            obj = probe.session.last_result.scene.objects[oid]
            centre = feature.params.get("centre", ())
            return (bool(obj.mesh.is_watertight), len(centre) == 3,
                    bool(feature.face_indices), min(len(feature.face_indices), 5000))
        oid, fid, feature = max(candidates, key=score)
        obj = probe.session.last_result.scene.objects[oid]
        offered = actions_for(feature, obj.features)
        probe.log("Merkmalsart Prüfumfang", kind=kind, count=len(candidates), object=oid,
                  feature=fid, selection="Geschlossener Körper und belastbare Merkmalsfläche bevorzugt",
                  other_features=[{"object": o, "feature": f} for o, f, _ in candidates if (o, f) != (oid, fid)],
                  offers=[{"op": a.op, "title": str(a.title), "reason": str(a.reason),
                           "note": str(a.note), "fields": [f.name for f in a.fields]} for a in offered])
        try:
            _viewport_click(probe, oid, fid, feature)
        except Exception:
            probe.log("Viewportklick Prüffehler", kind=kind, object=oid, feature=fid, error=traceback.format_exc())
        active = [action for action in offered if action.op]
        if not active:
            _choose(probe, oid, fid)
            probe.log("Merkmalsart ohne Bearbeitung", kind=kind, feature=fid,
                      labels=[label.text() for label in probe.window.feature_panel.findChildren(QLabel)],
                      buttons=[button.text() for button in probe.window.feature_panel.findChildren(QPushButton)])
            continue
        for action in active:
            variants = []
            if action.op == "move_feature":
                values = _positions(obj, feature)
                if values:
                    _preview_abort(probe, oid, fid, action, values)
                    variants.append(("kleine-Strecke", values, False))
            elif action.op in ("resize_feature", "resize_hole"):
                diameter = float(feature.params.get("diameter", 0.0))
                change = max(0.1, min(0.5, diameter * 0.05))
                spec = next(field for field in action.fields if field.name == "diameter")
                for label, value in (("größer", diameter + change), ("kleiner", diameter - change)):
                    if (spec.minimum is None or value >= spec.minimum) and (spec.maximum is None or value <= spec.maximum):
                        variants.append((label, {"diameter": value}, False))
                    else:
                        probe.log("Merkmalsvariante ausgelassen", op=action.op, variant=label,
                                  reason="Änderungswert außerhalb der sichtbaren Feldgrenzen", value=value)
                siblings = [other for other in obj.features.values() if other.kind == kind]
                if 2 <= len(siblings) <= 8 and diameter + change <= (spec.maximum or math.inf):
                    variants.append(("alle-gleichartigen", {"diameter": diameter + change}, True))
                elif len(siblings) > 8:
                    probe.log("Sammelhandlung ausgelassen", kind=kind, count=len(siblings),
                              reason="Mehr als acht Teiloperationen; Audit begrenzt Sammeländerungen auf überschaubare Gruppen")
            elif action.op == "rotate_feature":
                axis = np.asarray(feature.params.get("axis", (0, 0, 1)), dtype=float)
                rotate_axis = "xyz"[int(np.argmin(np.abs(axis)))] if axis.shape == (3,) else "x"
                variants.append(("kleine-Neigung", {"axis": rotate_axis, "angle": 5.0}, False))
            elif action.op == "duplicate_feature":
                values = _positions(obj, feature, duplicate=True)
                if values:
                    variants.append(("daneben", values, False))
            elif action.op == "remove_feature":
                variants.append(("entfernen", {}, False))
            if not variants:
                probe.log("Merkmalshandlung ausgelassen", kind=kind, feature=fid, op=action.op,
                          reason="Kein sinnvoller Zielwert innerhalb der Körperhülle aus den gemessenen Daten")
            for label, values, all_alike in variants:
                completed += 1
                _perform(probe, oid, fid, action, values, label, completed, all_alike=all_alike)
    probe.log("Merkmalsbearbeitung abgeschlossen", kinds=len(all_features), actions=completed,
              baseline_restored=True)
