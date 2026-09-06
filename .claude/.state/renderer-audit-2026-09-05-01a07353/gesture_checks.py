"""Freien Körperzug mit echten Qt-Eingaben im nativen Prüfstand beobachten.

Aufruf: ``gesture_checks.run(probe)`` nach Import/Ansichtsaufbau, vor weiteren
Körperzügen. Das Modul startet selbst weder Qt noch einen Renderer. Die einzige
Dokumentänderung entsteht durch Loslassen; der sichtbare Undo-Menüweg nimmt sie
zurück. Keine Produktionsmethode zur Auswahl oder Vorschau wird aufgerufen.
"""

from __future__ import annotations

import hashlib
import json
import traceback

import feature_checks
import numpy as np
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core.scene.serialise import document_to_data


def _document(probe):
    """Auch Parameter und vorhandene Operationswerte im gehaltenen Zug schützen."""
    data = document_to_data(probe.session.project.document)
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _quiet(probe):
    feature_checks._quiet(probe)
    probe.wait(
        "Körperzug: tatsächlich gezeigte Szene bereit",
        lambda: probe.window.viewport._scene_worker is None,
        60,
    )


def _item_state(item):
    if item is None:
        return None
    # vtkActor2D trägt keinen UserMatrix-Transform; sein Labelanker steht im
    # Datenpuffer. GFX-Labels besitzen dagegen denselben Träger wie ihre Punkte.
    matrix_supported = not hasattr(item, "actor") or hasattr(item.actor, "GetUserMatrix")
    return {
        "identity": id(item),
        "visible": bool(item.visible()),
        "matrix": np.asarray(item.matrix(), dtype=float).copy() if matrix_supported else None,
        "position": np.asarray(item.position(), dtype=float).copy(),
    }


def _points(item):
    """Die tatsächlich an den Renderer übergebenen Punktpuffer nur lesen."""
    if item is None:
        return None
    if hasattr(item, "anchors"):
        return np.asarray(item.anchors, dtype=float).copy()
    if hasattr(item, "data"):
        from vtkmodules.util.numpy_support import vtk_to_numpy

        return np.asarray(vtk_to_numpy(item.data.GetPoints().GetData()), dtype=float).copy()
    for child in getattr(item, "objects", ()):
        geometry = getattr(child, "geometry", None)
        positions = getattr(geometry, "positions", None)
        if positions is not None:
            return np.asarray(positions.data, dtype=float).copy()
    raise TypeError(f"Punktpuffer nicht lesbar: {type(item).__name__}")


def _snapshot(view):
    """Darstellungszustand kopieren, damit spätere Pufferupdates ihn nicht ändern."""
    return {
        "bodies": {str(oid): _item_state(actor) for oid, actor in view._actors.items()},
        "originals": [
            (list(point), str(text), int(priority))
            for point, text, priority in view._feature_label_data
        ],
        "owners": [str(oid) for oid in view._feature_label_owners],
        "anchors": np.asarray(view._feature_label_points, dtype=float).copy(),
        "markers": _points(view._feature_marker_item),
        "texts": _points(view._feature_text_item),
        "leaders": _points(view._feature_leader_item),
        "text_names": list((view._feature_label_content or ((), (), ()))[1]),
        "marker_item": _item_state(view._feature_marker_item),
        "text_item": _item_state(view._feature_text_item),
        "leader_item": _item_state(view._feature_leader_item),
        "patch": _item_state(view._feature_patch),
        "selected_body": str(view._selected),
        "selected_feature": view.selected_feature,
        "drag_active": view._body_drag_from is not None,
        "drag_offset": tuple(view._body_drag_offset),
        "camera": view.renderer.camera_pose(),
    }


def _same_points(first, second):
    return (
        first is not None
        and second is not None
        and np.shape(first) == np.shape(second)
        and bool(np.allclose(first, second, rtol=2e-7, atol=2e-5))
    )


def _overlay_checks(held, oid):
    """Anker aus Originalen und Körpertransform unabhängig neu ausrechnen."""
    originals = np.asarray([entry[0] for entry in held["originals"]], dtype=float).reshape(-1, 3)
    expected = originals.copy()
    for index, owner in enumerate(held["owners"]):
        body = held["bodies"][owner]
        expected[index] = (body["matrix"] @ np.append(originals[index], 1.0))[:3] + body["position"]
    checks = {
        "anchor_transform": _same_points(held["anchors"], expected),
        "marker_buffer_transform": _same_points(held["markers"], expected),
        "marker_visible": bool(held["marker_item"] and held["marker_item"]["visible"]),
        "text_visible": bool(held["text_item"] and held["text_item"]["visible"]),
        "leader_visible": bool(held["leader_item"] and held["leader_item"]["visible"]),
        "body_selection_kept": held["selected_feature"] is None
        and held["selected_body"] == str(oid),
    }
    for name in ("marker_item", "text_item", "leader_item"):
        item = held[name]
        checks[name + "_has_no_second_transform"] = bool(
            item
            and (item["matrix"] is None or _same_points(item["matrix"], np.eye(4)))
            and _same_points(item["position"], np.zeros(3))
        )
    # Ausgeblendete Originale können denselben Text wie ein sichtbares tragen.
    # Deshalb von den wirklich gezeigten Zeilen ausgehen: Name UND Linienanfang
    # ordnen jede einmalig ihrem transformierten Original zu. Der Text allein
    # ist keine Kennung und macht ausgelassene Anker nicht zu sichtbaren Labels.
    sources_by_text = {}
    for index, (_point, text, _priority) in enumerate(held["originals"]):
        sources_by_text.setdefault(text, []).append(index)
    leaders, texts = held["leaders"], held["texts"]
    checks["text_leader_endpoints"] = bool(
        texts is not None
        and len(texts)
        and leaders is not None
        and len(leaders) == 2 * len(texts)
        and _same_points(leaders[1::2], texts)
    )
    matched_sources = set()
    displayed_links = []
    for row, text in enumerate(held["text_names"]):
        source = next(
            (
                index
                for index in sources_by_text.get(text, ())
                if index not in matched_sources
                and leaders is not None
                and 2 * row < len(leaders)
                and _same_points(leaders[2 * row], expected[index])
            ),
            None,
        )
        displayed_links.append(source is not None)
        if source is not None:
            matched_sources.add(source)
    checks["displayed_anchor_to_text"] = (
        bool(displayed_links)
        and all(displayed_links)
        and any(held["owners"][index] == str(oid) for index in matched_sources)
    )
    return checks


def _automatic_labels(probe, enabled):
    """Über Analyseknopf und dessen echtes Kontrollkästchen schalten."""
    button = probe.window.tools._buttons["analysis"]
    if not button.isChecked():
        probe.click(button)
    probe.wait(
        "Körperzug: Merkmalsanzeige erreichbar", lambda: probe.window.analysis_bar.isVisible(), 10
    )
    checkbox = probe.window.analysis_bar.overlay
    if checkbox.isChecked() != enabled:
        probe.click(checkbox)
    if button.isChecked():
        probe.click(button)
    probe.settle(180)


def _target(probe, proposals, oid):
    """Kurzen Zug über zwei unabhängig bestätigte Originaloberflächen finden."""
    view = probe.window.viewport
    widget = view.renderer.widget
    ratio = float(widget.devicePixelRatioF())
    attempts = []
    rays_left = 32
    for proposal in proposals:
        if proposal["expected_cpu"].get("object") != str(oid):
            continue
        start = QPoint(*(round(value / ratio) for value in proposal["pixel"]))
        access = probe.canvas_access(widget, start)
        if not access["allowed"]:
            attempts.append({"start": [start.x(), start.y()], "access": access})
            continue
        initial = probe.independent_surface(
            view, round(start.x() * ratio), round(start.y() * ratio)
        )
        if initial.get("object") != str(oid) or not initial.get("interior"):
            continue
        for dx, dy in (
            (24, 0),
            (-24, 0),
            (0, 24),
            (0, -24),
            (18, 18),
            (-18, 18),
            (18, -18),
            (-18, -18),
        ):
            end = start + QPoint(dx, dy)
            access_end = probe.canvas_access(widget, end)
            if not access_end["allowed"]:
                continue
            if rays_left <= 0:
                return None, attempts
            rays_left -= 1
            final = probe.independent_surface(view, round(end.x() * ratio), round(end.y() * ratio))
            row = {
                "start": [start.x(), start.y()],
                "end": [end.x(), end.y()],
                "start_cpu": initial,
                "end_cpu": final,
                "start_access": access,
                "end_access": access_end,
                "dpr": ratio,
            }
            if final.get("object") == str(oid) and final.get("interior"):
                travel = np.asarray(final["point"]) - np.asarray(initial["point"])
                row["expected_xy_displacement"] = travel[:2]
                if np.max(np.abs(travel[:2])) > max(0.1, float(view._grid_step) * 0.6):
                    return (start, end, row), attempts
            attempts.append(row)
    return None, attempts


def run(probe):
    """Eine echte Vorschaugeste mit Rücknahme prüfen; Auslassungen sind nie grün."""
    view, session = probe.window.viewport, probe.session
    record = {
        "status": "skipped",
        "passed": None,
        "scope": "free_body_drag",
        "native_input": "QTest.mousePress/mouseMove/mouseRelease",
        "screenshot_requires_visual_review": True,
        "coverage_limit": (
            "Freier Körperzug: Merkmalswahl/deren Patch fallen beim Beginn weg. "
            "Automatische Labels folgen; gezielte Merkmals-Gizmo-Vorschau ist hier nicht geprüft."
        ),
    }
    result = session.last_result
    if result is None or view.renderer is None:
        record["reason"] = "Keine aufgebaute Szene"
        probe.log("Freier Körperzug mit Merkmalen", **record)
        return record
    if (
        probe.window.tools.active() is not None
        or view._gizmo is not None
        or view._sketch_frame is not None
        or view._sculpting
        or view._section is not None
        or view._layer is not None
    ):
        record["reason"] = "Aktives Werkzeug kann die freie Körpergeste übernehmen"
        probe.log("Freier Körperzug mit Merkmalen", **record)
        return record
    if session.history._open_bundle is not None:
        record["reason"] = "Offenes Zugbündel: Undo wäre kein isolierter Rückweg"
        probe.log("Freier Körperzug mit Merkmalen", **record)
        return record
    overlay_before = bool(view._feature_overlay)
    overlay_changed = False
    token = None
    pressed = False
    before_count = None
    baseline_hash = None
    events = []
    start = end = None
    try:
        _quiet(probe)
        result = session.last_result
        visible = [
            (oid, obj)
            for oid, obj in result.scene.objects.items()
            if oid in view._actors and obj.features
        ]
        features = [
            (oid, fid, feature)
            for oid, obj in visible
            for fid, feature in obj.features.items()
            if feature.face_indices
        ]
        features.sort(
            key=lambda row: (row[2].kind not in ("hole", "pin"), -len(row[2].face_indices))
        )
        if not visible:
            record["reason"] = "Kein sichtbarer Körper mit erkannten Merkmalen"
            return record
        if not overlay_before:
            _automatic_labels(probe, True)
            overlay_changed = True
        if features:
            # Das Panel zuerst öffnen: Seine Breite verändert die Projektion.
            feature_checks._choose(probe, features[0][0], features[0][1])
        else:
            probe.select_item(feature_checks._item(probe, visible[0][0]))
        proposals, search, _body_count = probe.targeted_surface_points(view, set())
        record["surface_search"] = search
        proposals.sort(key=lambda row: -row.get("projected_area_pixels", 0))
        chosen = next(
            (
                (oid, fid)
                for proposal in proposals
                for oid, fid, _feature in features
                if str(oid) == proposal["expected_cpu"].get("object")
            ),
            None,
        )
        if chosen is None:
            first = next(
                (
                    p
                    for p in proposals
                    if p["expected_cpu"].get("object") in {str(oid) for oid, _obj in visible}
                ),
                None,
            )
            if first is None:
                record["reason"] = "Kein unabhängig bestätigter Körperpunkt für den Ausweichweg"
                return record
            oid = next(oid for oid, _obj in visible if str(oid) == first["expected_cpu"]["object"])
            fid = None
            probe.select_item(feature_checks._item(probe, oid))
            record["coverage_limit"] += " Schon vor dem Zug war nur Körperwahl erreichbar."
        else:
            oid, fid = chosen
            feature_checks._choose(probe, oid, fid)
        probe.settle(200)
        record.update(
            object=str(oid),
            feature=fid,
            feature_kind=result.scene.objects[oid].features[fid].kind if fid else None,
        )
        target, rejected = _target(probe, proposals, oid)
        record["rejected_paths"] = rejected
        if target is None:
            record["reason"] = (
                "Kein unverdeckter Zug über die Klickschwelle mit ausreichend Bettbewegung"
            )
            return record
        start, end, record["gesture"] = target
        widget = view.renderer.widget
        QTest.mouseMove(widget, start, delay=30)
        probe.settle(200)
        before = _snapshot(view)
        if before["selected_feature"] != fid or before["selected_body"] != str(oid):
            raise AssertionError("Auswahl vor dem Drücken entspricht nicht dem Baumklick")
        before_count = len(session.project.document.transactions)
        before_ops = {str(op.id) for op in session.project.document.ops}
        errors_before = len(probe.errors)
        baseline_hash = feature_checks.fingerprint(probe)["hash"]
        before_document = _document(probe)
        original_body = result.scene.objects[oid].mesh.raw
        probe.shot("gesture-body-before")

        def observed(event):
            events.append(
                {
                    "kind": event.kind,
                    "x": event.x,
                    "y": event.y,
                    "button": event.button,
                    "buttons": sorted(event.buttons),
                    "transactions": len(session.project.document.transactions),
                }
            )

        token = view.renderer.add_pointer_listener(observed)
        QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=start, delay=30)
        pressed = True
        QTest.mouseMove(widget, end, delay=100)
        probe.settle(160)
        held = _snapshot(view)
        held_hash = feature_checks.fingerprint(probe)["hash"]
        # Ab Beginn gehört die Geste dem ganzen Körper. Das Hauptfenster muss
        # dazu auch die Baum-Merkmalswahl räumen; sonst würde Loslassen trotz
        # Körpervorschau die Operation move_feature auslösen.
        checks = _overlay_checks(held, oid)
        checks["selection_stepped_to_body"] = (
            held["selected_feature"] is None and probe.window.object_tree.selected_feature() is None
        )
        checks["selected_patch_cleared"] = held["patch"] is None
        delta = held["bodies"][str(oid)]["position"] - before["bodies"][str(oid)]["position"]
        original_hit = np.asarray(record["gesture"]["start_cpu"]["point"])
        screen_before = np.asarray(view.renderer.world_to_display(tuple(original_hit)))
        screen_held = np.asarray(view.renderer.world_to_display(tuple(original_hit + delta)))
        record["body_displacement_device_pixels"] = float(
            np.linalg.norm((screen_held - screen_before)[:2])
        )
        checks.update(
            document_unchanged_while_held=_document(probe) == before_document,
            geometry_unchanged_while_held=held_hash == baseline_hash,
            transactions_unchanged_while_held=len(session.project.document.transactions)
            == before_count,
            active_body_preview=held["drag_active"],
            camera_unchanged=before["camera"] == held["camera"],
            body_visibly_displaced=record["body_displacement_device_pixels"]
            > 4.0 * widget.devicePixelRatioF(),
            native_held_move=any(e["kind"] == "move" and "left" in e["buttons"] for e in events),
            press_delivered=any(e["kind"] == "press" and e["button"] == "left" for e in events),
        )
        probe.shot("gesture-body-held-preview")
        # Noch während des Haltens protokollieren: spätere Auswertung und Undo
        # dürfen einen misslungenen Vorschauanschluss nicht verdecken.
        record.update(
            before=before,
            held=held,
            held_checks=dict(checks),
            events_while_held=list(events),
            document_before=before_document,
            geometry_before=baseline_hash,
            screenshots=["gesture-body-before.png", "gesture-body-held-preview.png"],
        )
        probe.log(
            "Freier Körperzug: gehaltene Vorschau",
            **{
                **record,
                "status": "observed",
                "passed": all(checks.values()),
                "stage": "held_only",
            },
        )
        QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=end, delay=30)
        pressed = False
        probe.wait(
            "Körperzug: Loslassen schreibt eine Transaktion",
            lambda: (
                len(session.project.document.transactions) != before_count
                or len(probe.errors) > errors_before
            ),
            4,
        )
        _quiet(probe)
        added = [op for op in session.project.document.ops if str(op.id) not in before_ops]
        checks["release_delivered"] = any(
            e["kind"] == "release" and e["button"] == "left" for e in events
        )
        checks["one_translation_transaction"] = (
            len(session.project.document.transactions) == before_count + 1
            and len(added) == 1
            and str(added[0].op) == "translate_object"
        )
        record["released_operations"] = [
            {"id": str(op.id), "op": str(op.op), "params": probe.plain(op.params)} for op in added
        ]
        checks["geometry_changed_after_release"] = (
            feature_checks.fingerprint(probe)["hash"] != baseline_hash
        )
        # Eine andere Geometrie allein wäre kein Beleg für die versprochene
        # Körpertranslation. Sämtliche Ecken müssen demselben Versatz folgen.
        moved = session.last_result.scene.objects.get(oid)
        if checks["one_translation_transaction"] and moved is not None:
            displacement = np.asarray(
                [added[0].params[key] for key in ("dx", "dy", "dz")], dtype=float
            )
            checks["all_vertices_follow_translation"] = np.array_equal(
                original_body.faces, moved.mesh.raw.faces
            ) and _same_points(original_body.vertices + displacement, moved.mesh.raw.vertices)
        else:
            checks["all_vertices_follow_translation"] = False
        checks["no_new_application_error"] = len(probe.errors) == errors_before
        record["checks"] = dict(checks)
        probe.shot("gesture-body-after-release")
        record["screenshots"].append("gesture-body-after-release.png")
        record["status"] = (
            "passed"
            if all(checks.values()) and fid is not None
            else "partial"
            if all(checks.values())
            else "failed"
        )
        record["passed"] = None if record["status"] == "partial" else record["status"] == "passed"
    except Exception:
        record.update(status="failed", passed=False, error=traceback.format_exc())
    finally:
        if pressed:
            QTest.mouseRelease(
                view.renderer.widget, Qt.MouseButton.LeftButton, pos=end or start, delay=30
            )
        if token is not None:
            view.renderer.remove_pointer_listener(token)
        record["events"] = events
        if before_count is not None:
            try:
                _quiet(probe)
                count = len(session.project.document.transactions)
                if count == before_count + 1:
                    feature_checks._history(probe)
                    _quiet(probe)
                elif count != before_count:
                    raise AssertionError(
                        f"Unerwarteter Verlauf: {count}; erwartet {before_count}/{before_count + 1}"
                    )
                restored = (
                    len(session.project.document.transactions) == before_count
                    and feature_checks.fingerprint(probe)["hash"] == baseline_hash
                )
                record["undo_restored_original_geometry"] = restored
                if not restored:
                    record.update(status="failed", passed=False)
                probe.shot("gesture-body-after-undo")
            except Exception:
                record.update(status="failed", passed=False, restore_error=traceback.format_exc())
        if overlay_changed:
            try:
                _automatic_labels(probe, overlay_before)
            except Exception:
                record.update(
                    status="failed", passed=False, overlay_restore_error=traceback.format_exc()
                )
        probe.log("Freier Körperzug mit Merkmalen", **record)
    return record
