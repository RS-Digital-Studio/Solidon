"""Allgemeine Bearbeitungen auf dem sichtbaren Klickweg einzeln prüfen.

``run(probe)`` erwartet das laufende Modul ui_probe mit app, window, session,
OUT, pending_file, errors sowie menu, click, wait, settle, log, shot,
scene_data und tree_items. Es startet weder eine Anwendung noch einen Timer.
Die Datei benutzt ausschließlich die bereits von ui_probe geladene Quelle.
"""

from __future__ import annotations

# Ein Prüfpunkt darf scheitern; sein Traceback wird vollständig gespeichert.
# ruff: noqa: BLE001
import hashlib
import json
import math
import time
import traceback

import numpy as np
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
)
from shiboken6 import isValid


def fingerprint(probe):
    """Geometrie und Merkmale lesen; keine Auswertung oder Änderung auslösen."""
    digest = hashlib.sha256()
    for identifier, obj in sorted(
        probe.session.last_result.scene.objects.items(), key=lambda pair: str(pair[0])
    ):
        digest.update(str(identifier).encode())
        digest.update(str(obj.name).encode())
        digest.update(str(obj.kind).encode())
        # MeshData.raw und Solid.raw liefern beide das bereits angezeigte Netz.
        for values in (obj.mesh.raw.vertices, obj.mesh.raw.faces):
            array = np.asarray(values)
            digest.update(str(array.shape).encode())
            digest.update(array.tobytes())
        digest.update(
            json.dumps(
                probe.plain(obj.features), sort_keys=True, ensure_ascii=False
            ).encode()
        )
    return digest.hexdigest()


def select_objects(probe, identifiers):
    """Objektzeilen im Baum mit normalen und zusätzlichen Mausklicks wählen."""
    wanted = {str(value) for value in identifiers}
    rows = {
        str(item.data(0, Qt.ItemDataRole.UserRole)): item
        for item in probe.tree_items()
        if item.data(0, Qt.ItemDataRole.UserRole) is not None
        and not item.data(1, Qt.ItemDataRole.UserRole)
    }
    tree = probe.window.object_tree.tree
    for number, identifier in enumerate(sorted(wanted)):
        item = rows[identifier]
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        reached = False
        for attempt in range(3):
            tree.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
            probe.settle(550)
            rectangle = tree.visualItemRect(item).intersected(tree.viewport().rect())
            if not rectangle.isValid() or not tree.viewport().rect().contains(
                rectangle.center()
            ):
                continue
            if tree.itemAt(rectangle.center()) is not item:
                continue
            if number > 0 and item.isSelected():
                reached = True
                break
            QTest.mouseMove(tree.viewport(), rectangle.center())
            QTest.mouseClick(
                tree.viewport(),
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier
                if number == 0
                else Qt.KeyboardModifier.ControlModifier,
                rectangle.center(),
            )
            probe.settle(250)
            if item.isSelected():
                reached = True
                break
            probe.log(
                "Allgemeine Objektauswahl benötigt Wiederholung",
                attempt=attempt + 1,
                object_id=identifier,
            )
        if not reached:
            raise AssertionError(f"Baumklick erreicht Körper {identifier} nicht")
    probe.settle(150)
    actual = {str(value) for value in probe.window.object_tree.selected_objects()}
    if actual != wanted:
        raise AssertionError(f"Objektauswahl über Baum: {actual}, erwartet {wanted}")


def set_field(probe, dialog, name, value):
    """Den benannten sichtbaren Editor wie am Bildschirm bedienen."""
    editor = dialog._editors[name]
    if not editor.isVisible():
        advanced = getattr(dialog, "advanced", None)
        if advanced is not None and not advanced.isChecked():
            probe.click(advanced)
    if not editor.isVisible() or not editor.isEnabled():
        raise AssertionError(f"Feld {name} ist nicht sichtbar und bedienbar")
    if isinstance(editor, QCheckBox):
        if editor.isChecked() != bool(value):
            probe.click(editor)
        return
    if isinstance(editor, QComboBox):
        target = editor.findData(value)
        if target < 0:
            raise AssertionError(f"Auswahl {value!r} fehlt in {name}")
        # Am geschlossenen Feld per Tastatur wählen. Enter würde den
        # Standardknopf des ganzen Dialogs auslösen; Tab verlässt nur das Feld.
        QTest.mouseClick(editor, Qt.MouseButton.LeftButton, pos=QPoint(editor.width()-10, editor.height()//2))
        probe.settle(100)
        if editor.view().isVisible():
            popup = probe.app.activePopupWidget() or editor.view().window()
            QTest.keyClick(popup, Qt.Key.Key_Escape)
            probe.settle(100)
        if not isValid(dialog) or not isValid(editor):
            raise AssertionError(f"Dialog beim Schließen der Auswahlliste {name} verschwunden")
        if editor.view().isVisible():
            raise AssertionError(f"Auswahlliste {name} ist noch geöffnet")
        for _ in range(editor.count() + 1):
            current = editor.currentIndex()
            if current == target:
                break
            QTest.keyClick(editor, Qt.Key.Key_Down if current < target else Qt.Key.Key_Up)
            probe.settle(60)
            if editor.currentIndex() == current:
                raise AssertionError(f"Pfeiltaste erreicht Auswahl {name} nicht")
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        probe.settle(60)
        if editor.currentData() != value:
            raise AssertionError(
                f"Auswahl {name}: {editor.currentData()!r} statt {value!r}"
            )
        return
    spin = (
        editor
        if isinstance(editor, (QSpinBox, QDoubleSpinBox))
        else getattr(editor, "spin", None)
    )
    if spin is not None:
        text = (
            spin.locale().toString(float(value), "f", spin.decimals())
            if isinstance(spin, QDoubleSpinBox)
            else str(int(value))
        )
        text = text.replace(spin.locale().groupSeparator(), "")
        line = spin.lineEdit()
        probe.click(line)
        QTest.keyClick(line, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(line, text)
        QTest.keyClick(line, Qt.Key.Key_Tab)
        probe.settle(70)
        tolerance = (
            10 ** (-spin.decimals()) if isinstance(spin, QDoubleSpinBox) else 0.0
        )
        if abs(float(spin.value()) - float(value)) > tolerance + 1e-10:
            raise AssertionError(f"Feld {name}: {spin.value()} statt {value}")
        return
    if isinstance(editor, QLineEdit):
        probe.click(editor)
        QTest.keyClick(editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(editor, str(value))
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        return
    raise TypeError(f"Unbekannter sichtbarer Editor {name}: {type(editor).__name__}")


def _close_operation(probe):
    """Einen noch offenen Operationsdialog mit Abbrechen schließen."""
    dialog = probe.window._op_dialog
    if dialog is None or not isValid(dialog):
        return
    boxes = dialog.findChildren(QDialogButtonBox)
    cancel = next(
        (
            box.button(QDialogButtonBox.StandardButton.Cancel)
            for box in boxes
            if box.button(QDialogButtonBox.StandardButton.Cancel)
        ),
        None,
    )
    if cancel is None:
        raise RuntimeError("Der Operationsdialog bietet keinen Abbrechen-Knopf")
    probe.click(cancel)
    probe.wait(
        "Operationsdialog geschlossen", lambda: probe.window._op_dialog is None, 5
    )


def _wait_evaluation(probe, previous, error_count, label, seconds=150):
    probe.wait(
        label,
        lambda: (
            not probe.session.busy
            and (
                probe.session.last_result is not previous
                or len(probe.errors) > error_count
            )
        ),
        seconds,
    )
    probe.wait(
        "Viewport übernimmt Ergebnis",
        lambda: probe.window.viewport._result is probe.session.last_result,
        20,
    )


def _history_step(probe, action, expected, label):
    previous = probe.session.last_result
    error_count = len(probe.errors)
    probe.menu(action)
    _wait_evaluation(probe, previous, error_count, label)
    actual = fingerprint(probe)
    if actual != expected:
        raise AssertionError(f"{label}: Szene-Fingerprint {actual} statt {expected}")


def _verify_effect(probe, name, values, before, object_id, object_count):
    """Bekannte Auswirkungen unabhängig von der Operation an den Netzdaten prüfen."""
    objects = probe.session.last_result.scene.objects
    if name == "duplicate_object":
        if len(objects) != object_count + int(values["count"]) - 1:
            raise AssertionError(
                "Duplizieren liefert nicht die gewählte zusätzliche Körperzahl"
            )
        return
    if name == "split_pinned":
        outputs = probe.session.project.document.ops[-1].outputs
        if len(outputs) != 2 or len(objects) != object_count + 1:
            raise AssertionError(
                "Teilen liefert nicht zwei Hälften anstelle des ausgewählten Körpers"
            )
        halves = [objects[identifier].mesh for identifier in outputs]
        if any(half.triangle_count <= 0 for half in halves):
            raise AssertionError("Eine bestätigte Schnitthälfte besitzt keine Dreiecke")
        combined = np.asarray(
            [
                np.minimum(halves[0].raw.bounds[0], halves[1].raw.bounds[0]),
                np.maximum(halves[0].raw.bounds[1], halves[1].raw.bounds[1]),
            ]
        )
        np.testing.assert_allclose(combined, before["bounds"], atol=1e-5, rtol=1e-7)
        axis = "xyz".index(values["axis"])
        low, high = sorted(halves, key=lambda half: float(half.raw.bounds[0, axis]))
        position = float(values["position"])
        if (
            low.raw.bounds[1, axis] > position + 1e-5
            or high.raw.bounds[0, axis] < position - 1e-5
        ):
            raise AssertionError(
                "Die Schnitthälften liegen nicht auf ihren jeweiligen Seiten der gewählten Ebene"
            )
        volumes = [float(half.raw.volume) for half in halves]
        if before["watertight"]:
            if any(volume <= 0 for volume in volumes) or not all(
                half.is_watertight for half in halves
            ):
                raise AssertionError(
                    "Geschlossener Eingang ergibt keine zwei geschlossenen Hälften mit positivem Volumen"
                )
            np.testing.assert_allclose(
                sum(volumes), before["volume"], atol=1e-3, rtol=1e-5
            )
        probe.log(
            "Schnitt geometrisch geprüft",
            operation=name,
            original_volume=before["volume"],
            half_volumes=volumes,
            volume_sum_checked=before["watertight"],
            original_objects=object_count,
            resulting_objects=len(objects),
            axis=values["axis"],
            position=position,
        )
        return
    current = objects[object_id].mesh
    bounds = np.asarray(current.raw.bounds)
    size = bounds[1] - bounds[0]
    old_bounds = np.asarray(before["bounds"])
    old_size = old_bounds[1] - old_bounds[0]
    if name == "translate_object":
        expected = old_bounds + np.asarray([values[key] for key in ("dx", "dy", "dz")])
        np.testing.assert_allclose(bounds, expected, atol=1e-6, rtol=1e-9)
    elif name == "scale_object":
        np.testing.assert_allclose(
            size, old_size * values["factor"], atol=1e-6, rtol=1e-9
        )
    elif name == "fit_to_size":
        np.testing.assert_allclose(max(size), values["largest"], atol=1e-5, rtol=1e-7)
    elif name == "mirror_object":
        np.testing.assert_allclose(size, old_size, atol=1e-6, rtol=1e-9)
    elif name == "decimate_mesh":
        if current.triangle_count >= before["triangles"]:
            explained = [finding for finding in probe.session.last_result.scene.report.findings
                         if finding.code == "mesh.not_simplified" and finding.object_id == object_id]
            if not explained:
                raise AssertionError("Gewählte Verringerung hat die Dreieckszahl nicht gesenkt")
            probe.log("Vereinfachungsgrenze sichtbar erklärt", operation=name, status="limited",
                      before=before["triangles"], after=current.triangle_count,
                      findings=probe.plain(explained))
    elif name == "remesh_mesh":
        np.testing.assert_allclose(bounds, old_bounds, atol=1e-6, rtol=1e-9)
        if current.triangle_count <= before["triangles"]:
            raise AssertionError(
                "Gewählte Kantenverfeinerung hat keine Dreiecke hinzugefügt"
            )
    elif name == "hollow_object":
        current_volume = float(current.raw.volume)
        if current_volume <= 0 or current_volume >= before["volume"] - 1e-6:
            raise AssertionError(
                "Aushöhlen hat kein positives, gegenüber dem Eingang verkleinertes Materialvolumen geliefert"
            )
        if not current.is_watertight:
            raise AssertionError("Aushöhlen hat die geschlossene Hülle nicht erhalten")
        probe.log(
            "Hohlkörper geometrisch geprüft",
            operation=name,
            wall=values["wall"],
            vents=values["vents"],
            original_volume=before["volume"],
            hollow_volume=current_volume,
            removed_volume=before["volume"] - current_volume,
            watertight=True,
        )
    elif name == "drill_hole":
        if not float(current.raw.volume) < before["volume"] - 1e-6:
            raise AssertionError("Bestätigte Bohrung entfernt kein messbares Volumen")
    if name in ("translate_object", "rotate_object", "mirror_object"):
        np.testing.assert_allclose(
            float(current.raw.volume), before["volume"], atol=1e-5, rtol=1e-7
        )


def operation(probe, name, values, object_id, number):
    """Eine Menüoperation anwenden, rücknehmen, wiederholen und rücknehmen."""
    probe.wait("Ruhe vor Bearbeitung", lambda: not probe.session.busy, 150)
    select_objects(probe, [object_id])
    baseline = fingerprint(probe)
    source = probe.session.last_result.scene.objects[object_id].mesh
    before = {
        "bounds": np.asarray(source.raw.bounds).tolist(),
        "volume": float(source.raw.volume),
        "triangles": source.triangle_count,
        "watertight": bool(source.is_watertight),
    }
    object_count = len(probe.session.last_result.scene.objects)
    count = len(probe.session.project.document.ops)
    action = probe.window._op_actions.get(name)
    if action is None or not action.isEnabled():
        probe.log(
            "Allgemeine Bearbeitung ausgelassen",
            operation=name,
            reason="Kein aktivierter Menüeintrag für diesen ausgewählten Körper",
            tooltip=action.toolTip() if action else None,
        )
        return True
    started = time.monotonic()
    applied = False
    try:
        probe.menu(action)
        probe.wait(
            "Operationsdialog geöffnet", lambda: probe.window._op_dialog is not None, 5
        )
        dialog = probe.window._op_dialog
        if dialog.spec.name != name:
            raise AssertionError(f"Menü öffnet {dialog.spec.name} statt {name}")
        for key, value in values.items():
            set_field(probe, dialog, key, value)
        # Die Vorschau darf rechnen; dokumentiert wird der tatsächlich sichtbare Dialog.
        probe.shot(f"general-{number:02d}-{name}-dialog", dialog)
        entered = dialog.values()
        previous = probe.session.last_result
        error_count = len(probe.errors)
        probe.click(dialog._accept_button)
        applied = len(probe.session.project.document.ops) > count
        _wait_evaluation(probe, previous, error_count, f"Auswertung {name}")
        applied = len(probe.session.project.document.ops) > count
        if not applied:
            raise AssertionError(
                "Bestätigung hat keinen Verlaufsschritt angelegt: "
                + "; ".join(probe.errors[error_count:])
            )
        if probe.session.last_result.stopped_at is not None:
            raise AssertionError(
                f"Auswertung stoppt bei {probe.session.last_result.stopped_at}"
            )
        after = fingerprint(probe)
        scene = probe.scene_data()
        probe.shot(f"general-{number:02d}-{name}-result")
        _verify_effect(probe, name, entered, before, object_id, object_count)
        _history_step(probe, probe.window.undo_action, baseline, name + " Rückgängig")
        _history_step(probe, probe.window.redo_action, after, name + " Wiederholen")
        _history_step(
            probe, probe.window.undo_action, baseline, name + " zweites Rückgängig"
        )
        applied = False
        probe.log(
            "Allgemeine Bearbeitung geprüft",
            operation=name,
            entered=entered,
            seconds=time.monotonic() - started,
            geometry_changed=after != baseline,
            fingerprint_before=baseline,
            fingerprint_after=after,
            undo_redo_undo=True,
            scene=scene,
        )
        return True
    except Exception as error:
        probe.log(
            "Allgemeine Bearbeitung auffällig",
            operation=name,
            requested=values,
            seconds=time.monotonic() - started,
            error=str(error),
            traceback=traceback.format_exc(),
            scene=probe.scene_data(),
        )
        try:
            _close_operation(probe)
            if probe.session.busy:
                cancel = probe.window.veil.cancel
                if cancel.isVisible() and cancel.isEnabled():
                    cancel_started = time.monotonic()
                    probe.shot(f"general-{number:02d}-{name}-timeout-cancel")
                    probe.click(cancel)
                    probe.wait("Lange Bearbeitung über sichtbaren Knopf abbrechen",
                               lambda: not probe.session.busy, 120)
                    probe.log("Lange Bearbeitung nach Prüfzeit über Oberfläche abgebrochen",
                              operation=name, seconds=time.monotonic() - cancel_started,
                              status="probe_cancelled_after_timeout")
            probe.wait(
                "Rechnung vor Wiederherstellung endet",
                lambda: not probe.session.busy,
                180,
            )
            # Ausschließlich die durch diesen Durchgang hinzugekommenen Schritte zurücknehmen.
            remaining = len(probe.session.project.document.ops) - count
            for _ in range(max(0, remaining)):
                previous = probe.session.last_result
                error_count = len(probe.errors)
                probe.menu(probe.window.undo_action)
                _wait_evaluation(
                    probe, previous, error_count, "Baseline wiederherstellen"
                )
            restored = (
                fingerprint(probe) == baseline
                and len(probe.session.project.document.ops) == count
            )
            probe.log(
                "Baseline nach Auffälligkeit",
                operation=name,
                restored=restored,
                had_applied=applied,
            )
            return restored
        except Exception:
            probe.log(
                "Baseline nicht wiederhergestellt",
                operation=name,
                traceback=traceback.format_exc(),
            )
            return False


def _persistence_move(probe, original):
    """Eine kleine sichtbare Änderung als dauerhaft gespeicherten Prüffall anlegen."""
    objects = probe.session.last_result.scene.objects
    object_id = max(objects, key=lambda key: objects[key].mesh.triangle_count)
    source = objects[object_id].mesh
    before = {
        "bounds": np.asarray(source.raw.bounds).tolist(),
        "volume": float(source.raw.volume),
        "triangles": source.triangle_count,
        "watertight": bool(source.is_watertight),
    }
    select_objects(probe, [object_id])
    action = probe.window._op_actions["translate_object"]
    if not action.isEnabled():
        raise AssertionError("Verschieben ist für den Persistenzprüffall nicht bedienbar")
    probe.menu(action)
    probe.wait(
        "Verschiebedialog für Persistenz geöffnet", lambda: probe.window._op_dialog is not None, 5
    )
    dialog = probe.window._op_dialog
    if dialog.spec.name != "translate_object":
        raise AssertionError("Der Persistenzprüffall öffnete den falschen Dialog")
    for key, value in {"dx": 1.25, "dy": -0.75, "dz": 0.5}.items():
        set_field(probe, dialog, key, value)
    if not isValid(dialog) or len(probe.session.project.document.ops) != original["operations"]:
        raise AssertionError("Feldeingabe bestätigte den Persistenzdialog vorzeitig")
    entered = dialog.values()
    probe.shot("general-persistence-edit-dialog", dialog)
    previous, errors = probe.session.last_result, len(probe.errors)
    probe.click(dialog._accept_button)
    _wait_evaluation(probe, previous, errors, "Verschiebung für Persistenz berechnet", 240)
    document = probe.session.project.document
    if (
        len(document.ops) != original["operations"] + 1
        or len(document.transactions) != original["transactions"] + 1
    ):
        raise AssertionError("Persistenzänderung ergibt nicht genau eine Operation und Transaktion")
    if probe.session.last_result.stopped_at is not None:
        raise AssertionError("Persistenzänderung wurde nicht vollständig ausgewertet")
    _verify_effect(probe, "translate_object", entered, before, object_id, len(objects))
    changed = fingerprint(probe)
    if changed == original["fingerprint"]:
        raise AssertionError("Verschieben änderte die gespeicherte Geometrie nicht")
    probe.shot("general-persistence-edit-result")
    probe.log(
        "Persistenzänderung über Dialog angewendet",
        operation="translate_object",
        object_id=str(object_id),
        entered=entered,
        geometry_changed=True,
        fingerprint_before=original["fingerprint"],
        fingerprint_after=changed,
        operations_before=original["operations"],
        operations_after=len(document.ops),
        transactions_before=original["transactions"],
        transactions_after=len(document.transactions),
        scene=probe.scene_data(),
    )
    return changed


def persistence(probe):
    """Geändertes Projekt speichern, exportieren, neu öffnen und per Undo zurückkehren."""
    original = {
        "fingerprint": fingerprint(probe),
        "operations": len(probe.session.project.document.ops),
        "transactions": len(probe.session.project.document.transactions),
    }
    reopened = False
    target = probe.OUT / "bearbeitung-geprueft.p3d"
    try:
        baseline = _persistence_move(probe, original)
        from stl_export_checks import capture as capture_stl, verify as verify_stl

        stl_expected = capture_stl(probe)
        object_ids = list(probe.session.last_result.scene.objects)
        saved_operations = len(probe.session.project.document.ops)
        saved_transactions = len(probe.session.project.document.transactions)
        probe.log(
            "Export-Ausgangsszene",
            fingerprint=baseline,
            operations=saved_operations,
            transactions=saved_transactions,
            scene=probe.scene_data(),
        )
        probe.pending_file = target
        action = probe.window.save_action
        # Bei einer Wiederholungsprüfung hat das Projekt bereits einen Pfad;
        # der echte Menüeintrag Speichern unter hält den Dateidialog erreichbar.
        if probe.session.path is not None:
            containers = [probe.window.menuBar()]
            action = None
            while containers and action is None:
                for candidate in containers.pop().actions():
                    if candidate.text().replace("&", "").startswith("Speichern unter"):
                        action = candidate
                        break
                    if candidate.menu() is not None:
                        containers.append(candidate.menu())
            if action is None:
                raise AssertionError("Speichern unter ist im echten Menü nicht erreichbar")
        probe.menu(action)
        probe.wait(
            "Geändertes Projekt geschrieben",
            lambda: target.is_file() and target.stat().st_size > 0 and probe.session.path == target,
            90,
        )
        if fingerprint(probe) != baseline:
            raise AssertionError("Speichern änderte den Szenenzustand")
        probe.log(
            "Projekt über Speicherdialog geschrieben",
            path=str(target),
            bytes=target.stat().st_size,
            fingerprint=baseline,
            saved_edit=True,
            operations=saved_operations,
            transactions=saved_transactions,
        )
        for extension in ("3mf", "stl"):
            try:
                select_objects(probe, object_ids)
                folder = probe.OUT / f"export-{extension}"
                folder.mkdir(exist_ok=True)
                before = {
                    path: (path.stat().st_mtime_ns, path.stat().st_size)
                    for path in folder.iterdir()
                    if path.is_file()
                }
                probe.pending_file = folder / f"vollstaendige-szene.{extension}"
                probe.pending_filter = f"{extension.upper()} (*.{extension})"
                probe.menu(probe.window.export_action)
                probe.wait(
                    "Export beendet",
                    lambda: (
                        probe.window._export_worker is None
                        and probe.window.export_action.isEnabled()
                    ),
                    300,
                )
                files = [
                    path
                    for path in folder.iterdir()
                    if path.is_file()
                    and before.get(path) != (path.stat().st_mtime_ns, path.stat().st_size)
                ]
                if not files or any(path.stat().st_size == 0 for path in files):
                    raise AssertionError(
                        "Der Export hat keine neuen, nichtleeren Dateien geschrieben"
                    )
                if fingerprint(probe) != baseline:
                    raise AssertionError("Export hat den Szenenzustand verändert")
                probe.log(
                    "Export über Dateidialog geprüft",
                    format=extension,
                    selected_objects=len(object_ids),
                    files=[{"path": str(path), "bytes": path.stat().st_size} for path in files],
                    scene_unchanged=True,
                    fingerprint=baseline,
                    saved_edit=True,
                )
                if extension == "stl":
                    verify_stl(probe, stl_expected, files)
            except Exception:
                probe.log("Export auffällig", format=extension, traceback=traceback.format_exc())
            finally:
                probe.pending_file = None
                probe.pending_filter = None
        previous, errors = probe.session.last_result, len(probe.errors)
        probe.pending_file = target
        probe.menu(probe.window.open_action)
        # open_project leert den Sitzungscache und wertet das gespeicherte
        # Dokument neu aus; ein großer Import darf hier erneut lange brauchen.
        _wait_evaluation(probe, previous, errors, "Geändertes Projekt wieder öffnen", 600)
        after = fingerprint(probe)
        operation_count_equal = len(probe.session.project.document.ops) == saved_operations
        transaction_count_equal = (
            len(probe.session.project.document.transactions) == saved_transactions
        )
        preserved = (
            after == baseline
            and operation_count_equal
            and transaction_count_equal
            and probe.session.last_result.stopped_at is None
        )
        probe.shot("general-project-reopened")
        probe.log(
            "Projekt über Öffnendialog wieder geöffnet",
            path=str(target),
            exact_scene_equal=after == baseline,
            fingerprint_before=baseline,
            fingerprint_after=after,
            saved_edit_preserved=preserved,
            operation_count_equal=operation_count_equal,
            transaction_count_equal=transaction_count_equal,
            scene=probe.scene_data(),
        )
        if not preserved:
            raise AssertionError(
                "Gespeicherte Änderung oder ihr Verlauf weicht nach Wiederöffnen ab"
            )
        reopened = True
        _history_step(
            probe,
            probe.window.undo_action,
            original["fingerprint"],
            "Gespeicherte Änderung nach Wiederöffnen rückgängig",
        )
        _history_step(
            probe,
            probe.window.redo_action,
            baseline,
            "Gespeicherte Änderung nach Wiederöffnen wiederholen",
        )
        _history_step(
            probe,
            probe.window.undo_action,
            original["fingerprint"],
            "Gespeicherte Änderung erneut rückgängig",
        )
        if (
            len(probe.session.project.document.ops) != original["operations"]
            or len(probe.session.project.document.transactions) != original["transactions"]
        ):
            raise AssertionError(
                "Undo nach Wiederöffnen stellt den ursprünglichen Verlauf nicht her"
            )
        probe.log(
            "Persistenzänderung nach Wiederöffnen zurückgenommen",
            restored=True,
            undo_redo_undo=True,
            fingerprint_expected=original["fingerprint"],
            fingerprint_actual=fingerprint(probe),
            operations=len(probe.session.project.document.ops),
            transactions=len(probe.session.project.document.transactions),
        )
    except Exception:
        probe.log(
            "Persistenzprüfung auffällig", reopened=reopened, traceback=traceback.format_exc()
        )
    finally:
        probe.pending_file = None
        probe.pending_filter = None
        _close_operation(probe)
        probe.wait("Rechnung vor Persistenz-Rückkehr beendet", lambda: not probe.session.busy, 600)
        if probe.session.last_result is None:
            probe.log(
                "Persistenz-Baseline auffällig",
                restored=False,
                reason="Kein auswertbares Ergebnis nach Wiederöffnen",
            )
            raise RuntimeError("Persistenzprüfung ohne wiederhergestellte Ausgangsszene")
        while len(probe.session.project.document.ops) > original["operations"]:
            previous, errors = probe.session.last_result, len(probe.errors)
            count = len(probe.session.project.document.ops)
            probe.menu(probe.window.undo_action)
            _wait_evaluation(probe, previous, errors, "Persistenz-Baseline wiederherstellen", 600)
            if len(probe.session.project.document.ops) >= count:
                raise RuntimeError("Rückgängig entfernt die Persistenzänderung nicht")
        restored = (
            fingerprint(probe) == original["fingerprint"]
            and len(probe.session.project.document.ops) == original["operations"]
            and len(probe.session.project.document.transactions) == original["transactions"]
        )
        probe.log(
            "Persistenz-Ausgangsszene wiederhergestellt"
            if restored
            else "Persistenz-Baseline auffällig",
            restored=restored,
            fingerprint=fingerprint(probe),
        )
        if not restored:
            raise RuntimeError("Weitere Prüfungen benötigen die unveränderte Ausgangsszene")



def run(probe):
    """Passende Operationen auf unverändertem Ausgangsstand einzeln prüfen."""
    from app.core.scene.evaluate import FEATURE_LIMIT_TRIANGLES

    objects = probe.session.last_result.scene.objects
    if not objects:
        probe.log(
            "Allgemeine Bearbeitung ausgelassen", reason="Import lieferte keinen Körper"
        )
        return
    object_id, obj = max(objects.items(), key=lambda pair: pair[1].mesh.triangle_count)
    bounds = np.asarray((obj.mesh.bounds.minimum, obj.mesh.bounds.maximum))
    size = bounds[1] - bounds[0]
    faces = obj.mesh.triangle_count
    probe.log(
        "Allgemeiner Bearbeitungsumfang",
        object_id=str(object_id),
        object_name=obj.name,
        kind=obj.kind,
        triangles=faces,
        other_objects=len(objects) - 1,
        reason="Der dreiecksreichste Körper wird bearbeitet; vollständige Szene wird gespeichert und exportiert",
    )
    checks = [
        ("translate_object", {"dx": 2.5, "dy": -1.25, "dz": 0.75}),
        ("rotate_object", {"axis": "z", "angle": 17.0}),
        ("scale_object", {"factor": 1.05}),
        ("mirror_object", {"axis": "x"}),
        ("duplicate_object", {"count": 2}),
        (
            "fit_to_size",
            {"largest": min(1000.0, max(0.1, round(float(max(size)) * 0.95, 2)))},
        ),
        ("repair", {"fill_holes": True}),
    ]
    if obj.kind == "mesh" and faces > 500:
        checks.append(("decimate_mesh", {"triangles": max(500, int(faces * 0.8))}))
    else:
        probe.log(
            "Allgemeine Bearbeitung ausgelassen",
            operation="decimate_mesh",
            reason=f"Körperart {obj.kind}, {faces} Dreiecke: keine sinnvolle Netzreduktion",
        )
    if obj.kind == "mesh" and 0 < faces <= FEATURE_LIMIT_TRIANGLES:
        vertices = np.asarray(obj.mesh.raw.vertices)
        triangles = np.asarray(obj.mesh.raw.faces)
        longest = max(
            float(
                np.linalg.norm(
                    vertices[triangles[:, a]] - vertices[triangles[:, b]], axis=1
                ).max()
            )
            for a, b in ((0, 1), (1, 2), (2, 0))
        )
        edge = min(50.0, max(0.05, round(longest * 0.9, 2)))
        if longest / edge <= 2.0:
            checks.append(("remesh_mesh", {"edge": edge}))
        else:
            probe.log(
                "Allgemeine Bearbeitung ausgelassen",
                operation="remesh_mesh",
                reason=f"Längste Kante {longest:.3f} mm würde bei maximal 50 mm mehrfache flächendeckende Unterteilung erzwingen",
            )
        checks.append(("smooth_mesh", {"iterations": 1}))
    else:
        for name in ("remesh_mesh", "smooth_mesh"):
            probe.log(
                "Allgemeine Bearbeitung ausgelassen",
                operation=name,
                reason=f"Körperart {obj.kind}, {faces} Dreiecke; zusätzliche Topologieänderungen werden innerhalb des aktuellen Merkmalsbudgets von {FEATURE_LIMIT_TRIANGLES} Dreiecken geprüft",
            )
    features = list(obj.features.values())
    planar = [
        feature
        for feature in features
        if feature.kind == "face" and feature.params.get("normal")
    ]
    if obj.kind == "brep" and planar:
        chosen = max(planar, key=lambda feature: float(feature.params.get("area", 0)))
        normal = chosen.params["normal"]
        checks.append(
            (
                "push_face",
                {
                    "distance": 0.5,
                    "nx": float(normal[0]),
                    "ny": float(normal[1]),
                    "nz": float(normal[2]),
                },
            )
        )
    else:
        probe.log(
            "Allgemeine Bearbeitung ausgelassen",
            operation="push_face",
            reason="Fläche versetzen benötigt einen exakten Körper mit erkannter ebener Fläche",
        )
    if obj.mesh.is_watertight and faces <= FEATURE_LIMIT_TRIANGLES and planar:
        chosen = max(planar, key=lambda feature: float(feature.params.get("area", 0)))
        normal = np.asarray(chosen.params["normal"])
        axis = int(np.argmax(np.abs(normal)))
        if abs(float(normal[axis])) >= 0.999:
            centre = chosen.params["centre"]
            diameter = min(
                2.0,
                max(
                    0.4, round(math.sqrt(float(chosen.params.get("area", 1))) * 0.05, 2)
                ),
            )
            checks.append(
                (
                    "drill_hole",
                    {
                        "diameter": diameter,
                        "x": float(centre[0]),
                        "y": float(centre[1]),
                        "z": float(centre[2]),
                        "axis": "xyz"[axis],
                        "compensate": False,
                    },
                )
            )
        else:
            probe.log(
                "Allgemeine Bearbeitung ausgelassen",
                operation="drill_hole",
                reason="Größte erkannte Fläche liegt nicht achsenparallel; der Bohrdialog bietet nur X, Y oder Z",
            )
    else:
        probe.log(
            "Allgemeine Bearbeitung ausgelassen",
            operation="drill_hole",
            reason=f"Keine passende ebene Fläche oder offenes/großes Netz: {faces} Dreiecke, geschlossen={bool(obj.mesh.is_watertight)}, Ebenen={len(planar)}",
        )
    probe.log(
        "Allgemeine Bearbeitung ausgelassen",
        operation="lose Körper trennen",
        reason="Der geprüfte Operationskatalog bietet keine eigene Handlung zum Trennen loser Zusammenhangskomponenten; Baugruppen werden beim Import getrennt",
    )
    # Ein reiner Ebenenschnitt ist bei jeder ausgedehnten Form ein erreichbarer
    # Bearbeitungsweg. Offene Eingänge prüfen Hüllmaß und Seitenlage, aber kein
    # physikalisch nicht definiertes Volumen.
    longest_axis = int(np.argmax(size))
    if float(size[longest_axis]) > 0.02:
        position = round(
            float((bounds[0, longest_axis] + bounds[1, longest_axis]) / 2.0), 2
        )
        if bounds[0, longest_axis] < position < bounds[1, longest_axis]:
            checks.append(
                (
                    "split_pinned",
                    {"axis": "xyz"[longest_axis], "position": position, "pins": 0},
                )
            )
        else:
            probe.log(
                "Allgemeine Bearbeitung ausgelassen",
                operation="split_pinned",
                reason="Die mittige Schnittebene fällt bei der sichtbaren Eingabegenauigkeit auf den Körperrand",
            )
    else:
        probe.log(
            "Allgemeine Bearbeitung ausgelassen",
            operation="split_pinned",
            reason=f"Größte Ausdehnung {max(size):.6f} mm bietet keinen im Dialog getrennt eingebbaren Innenpunkt",
        )

    # 2V/A ist eine vorsichtige globale Dickenabschätzung, keine lokale
    # Wandmessung. Zusammen mit dem kleinsten Hüllmaß schließt sie dünne
    # Schalen aus; ob ein Hohlraum entsteht, prüft das echte Ergebnis.
    minimum_wall = float(probe.session.profile.minimum_wall_thickness)
    area = float(obj.mesh.area)
    volume = float(obj.mesh.volume)
    estimated_thickness = (
        min(float(min(size)), 2.0 * volume / area) if area > 0 and volume > 0 else 0.0
    )
    wall = (
        math.ceil(max(minimum_wall, min(2.4, estimated_thickness / 6.0)) * 100.0)
        / 100.0
    )
    if obj.mesh.is_watertight and estimated_thickness >= 4.0 * wall:
        checks.append(
            (
                "hollow_object",
                {
                    "wall": wall,
                    "open_top": False,
                    "vents": 1,
                    "vent_diameter": max(1.0, round(min(2.0, wall * 1.5), 2)),
                },
            )
        )
        probe.log(
            "Aushöhlen geometrisch vorbereitet",
            minimum_dimension=float(min(size)),
            estimated_thickness=estimated_thickness,
            profile_minimum_wall=minimum_wall,
            chosen_wall=wall,
            heuristic="Minimum aus kleinstem Hüllmaß und 2V/A; tatsächlichen Materialverlust am Ergebnis prüfen",
        )
    else:
        probe.log(
            "Allgemeine Bearbeitung ausgelassen",
            operation="hollow_object",
            reason=f"Geschlossen={bool(obj.mesh.is_watertight)}, Dickenabschätzung {estimated_thickness:.3f} mm reicht nicht für vier gewählte Wandstärken à {wall:.2f} mm; Profilminimum {minimum_wall:.3f} mm",
        )
    safe = True
    for number, (name, values) in enumerate(checks, 1):
        if not safe:
            probe.log(
                "Allgemeine Bearbeitung ausgelassen",
                operation=name,
                reason="Ausgangsszene nach vorherigem Fehler nicht wiederhergestellt",
            )
            continue
        safe = operation(probe, name, values, object_id, number)
    if safe:
        persistence(probe)
    else:
        probe.log(
            "Speichern und Export ausgelassen",
            reason="Ausgangsszene nach vorherigem Fehler nicht wiederhergestellt",
        )
