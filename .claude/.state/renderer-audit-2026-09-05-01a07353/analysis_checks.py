"""Sichtet Analysekarte und Schichtdarstellung durch die sichtbaren Bedienelemente."""

import time

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView, QLabel, QStyle, QStyleOptionSlider


def choose(probe, combo, data):
    """Wählt per Tastatur am geschlossenen Feld ohne Dialogbestätigung."""
    index = combo.findData(data)
    if index < 0:
        raise ValueError(f"Listeneintrag fehlt: {data}")
    probe.click(combo)
    if combo.view().isVisible():
        popup = probe.app.activePopupWidget() or combo.view().window()
        QTest.keyClick(popup, Qt.Key.Key_Escape)
        probe.settle(100)
    for _ in range(combo.count() + 1):
        current = combo.currentIndex()
        if current == index:
            break
        QTest.keyClick(combo, Qt.Key.Key_Down if current < index else Qt.Key.Key_Up)
        probe.settle(60)
        if combo.currentIndex() == current:
            raise AssertionError(f"Pfeiltaste erreicht Analyseauswahl {data} nicht")
    QTest.keyClick(combo, Qt.Key.Key_Tab)
    probe.settle(150)
    if combo.currentData() != data:
        raise AssertionError(f"Popupwahl ergibt {combo.currentData()} statt {data}")


def run(probe):
    """Prüft Merkmalskarten aller Körper und weitere Karten am größten Körper."""
    import wait_driver
    wait_driver.install(probe)
    window = probe.window
    objects = list(probe.session.last_result.scene.objects.items())
    ordered = sorted(
        objects, key=lambda pair: pair[1].mesh.triangle_count, reverse=True
    )
    for position, (oid, obj) in enumerate(ordered):
        item = next(
            (
                i
                for i in probe.tree_items()
                if i.data(0, Qt.ItemDataRole.UserRole) == oid
                and not i.data(1, Qt.ItemDataRole.UserRole)
            ),
            None,
        )
        if item is None:
            probe.log(
                "Analysekarten: Körper im Baum nicht gefunden",
                status="failed",
                object=str(oid),
            )
            continue
        probe.select_item(item)
        if window.tools.active() != "analysis":
            probe.click(window.tools._buttons["analysis"])
        kinds = (
            ["features", "wall", "overhang", "defects", "curvature", "fits", "support"]
            if position == 0
            else ["features"]
        )
        for kind in kinds:
            try:
                choose(probe, window.analysis_bar.selector, kind)
                probe.wait(
                    "Analysekarte " + kind,
                    lambda: (
                        window._map_worker is None or not window._map_worker.isRunning()
                    ),
                    120,
                )
                probe.settle(300)
                note = window.analysis_bar.legend.note.text()
                probe.log(
                    "Analysekarte",
                    status="observed",
                    object=str(oid),
                    name=str(obj.name),
                    kind=kind,
                    note=note,
                    legend=window.analysis_bar.legend.entries,
                )
                if position == 0:
                    probe.shot("03-map-" + kind)
            except Exception as error:
                probe.log(
                    "Analysekarte",
                    status="failed",
                    object=str(oid),
                    kind=kind,
                    error=str(error),
                )
        if not window.analysis_bar.overlay.isChecked():
            probe.click(window.analysis_bar.overlay)
        probe.log(
            "Merkmalsbeschriftung",
            status="observed",
            object=str(oid),
            checked=window.analysis_bar.overlay.isChecked(),
        )
        choose(probe, window.analysis_bar.selector, None)
    if window.tools.active() == "analysis":
        probe.click(window.tools._buttons["analysis"])
    if ordered:
        probe.log("Schichtansicht zurückgestellt", reason="Wird nach Merkmalsänderungen, allgemeinen Bearbeitungen und Speicherung geprüft")
    probe.log(
        "Analyseumfang",
        status="observed",
        feature_maps_objects=len(ordered),
        other_maps_object=str(ordered[0][0]) if ordered else None,
        note="Alle sieben Karten am größten Körper, Merkmalskarte zusätzlich an jedem weiteren Körper.",
    )


def _layer_position(probe, slider, target):
    """Erste/letzte Schicht per Taste, Mitte über die echte Schieberrinne."""
    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    style = slider.style()
    handle = style.subControlRect(
        QStyle.ComplexControl.CC_Slider,
        option,
        QStyle.SubControl.SC_SliderHandle,
        slider,
    )
    groove = style.subControlRect(
        QStyle.ComplexControl.CC_Slider,
        option,
        QStyle.SubControl.SC_SliderGroove,
        slider,
    )
    # Ein Klick auf den Griff setzt den Fokus, ohne vorher eine andere Schicht zu wählen.
    QTest.mouseClick(slider, Qt.MouseButton.LeftButton, pos=handle.center())
    if target == slider.minimum():
        QTest.keyClick(slider, Qt.Key.Key_Home)
    elif target == slider.maximum():
        QTest.keyClick(slider, Qt.Key.Key_End)
    else:
        travel = max(1, groove.width() - handle.width())
        offset = QStyle.sliderPositionFromValue(
            slider.minimum(), slider.maximum(), target, travel
        )
        spot = QPoint(groove.x() + handle.width() // 2 + offset, groove.center().y())
        QTest.mouseMove(slider, spot)
        QTest.mouseClick(slider, Qt.MouseButton.LeftButton, pos=spot)
        # Ein Bildpunkt kann mehrere Schichten umfassen; wenige Pfeiltasten treffen exakt.
        difference = target - slider.value()
        if abs(difference) > max(
            20, (slider.maximum() - slider.minimum()) // travel + 3
        ):
            raise AssertionError(
                f"Schichtregler springt unerwartet: {slider.value()} statt Nähe {target}"
            )
        key = Qt.Key.Key_Right if difference > 0 else Qt.Key.Key_Left
        for _ in range(abs(difference)):
            QTest.keyClick(slider, key)
    probe.wait("Gewählte Schichtnummer", lambda: slider.value() == target, 10)


def check_layers(probe, oid, obj):
    """Schichten des größten Körpers ausschließlich über Werkzeug und Regler sichten."""
    window = probe.window
    bar = window.layer_bar
    started = time.monotonic()
    operation_count = len(probe.session.project.document.ops)
    result_before = probe.session.last_result
    triangles = obj.mesh.triangle_count
    # Große organische Netze dürfen mehrere Minuten im echten SliceWorker rechnen.
    timeout = min(1200, max(180, 180 + triangles / 5000))
    try:
        item = next(
            (
                item
                for item in probe.tree_items()
                if item.data(0, Qt.ItemDataRole.UserRole) == oid
                and not item.data(1, Qt.ItemDataRole.UserRole)
            ),
            None,
        )
        if item is None:
            raise AssertionError("Größter Körper steht nicht mehr im Objektbaum")
        probe.select_item(item)
        if window.tools.active() != "layers":
            probe.click(window.tools._buttons["layers"])
        probe.wait(
            "Schichtenwerkzeug sichtbar",
            lambda: window.tools.active() == "layers" and bar.isVisible(),
            10,
        )
        probe.log(
            "Schichtanalyse gestartet",
            status="observed",
            object=str(oid),
            name=str(obj.name),
            triangles=triangles,
            timeout_seconds=timeout,
            worker_running=window._slice_worker is not None
            and window._slice_worker.isRunning(),
            note=bar.note.text(),
            status_text=window.status_message.text(),
        )
        probe.wait(
            "Schichtanalyse des gewählten Körpers",
            lambda: (
                (window._slice_worker is None or not window._slice_worker.isRunning())
                and window._slice_pending is None
            ),
            timeout,
        )
        expected_key = (oid, triangles)
        if window._slice_key != expected_key or bar._result is None:
            raise AssertionError(
                f"Schichtanalyse liefert keinen Stand für {expected_key}; Schlüssel={window._slice_key}, Hinweis={bar.note.text()!r}"
            )
        layers = bar._result.layers
        if not layers:
            probe.log(
                "Schichtansicht ohne Schichten",
                status="observed",
                object=str(oid),
                seconds=time.monotonic() - started,
                note=bar.note.text(),
                readout=bar.readout.text(),
                slider_enabled=bar.slider.isEnabled(),
                slice_result=probe.plain(bar._result),
            )
            probe.shot("04-layers-empty")
            return
        if not bar.slider.isVisible() or not bar.slider.isEnabled():
            raise AssertionError(
                "Berechnete Schichten haben keinen sichtbaren bedienbaren Regler"
            )
        targets = (
            ("first", 0),
            ("middle", (len(layers) - 1) // 2),
            ("last", len(layers) - 1),
        )
        for label, target in targets:
            _layer_position(probe, bar.slider, target)
            expected_layer = layers[target]
            probe.wait(
                "Kontur der gewählten Schicht",
                lambda: window.viewport._layer is expected_layer,
                30,
            )
            probe.wait(
                "3D-Ansicht folgt der Schichthöhe",
                lambda: not window.viewport._layer_rebuild.isActive(),
                90,
            )
            probe.settle(300)
            readout = bar.readout.text()
            if f"{target + 1}/{len(layers)}" not in readout:
                raise AssertionError(
                    f"Schichtanzeige passt nicht zur Auswahl {target + 1}/{len(layers)}: {readout}"
                )
            probe.log(
                "Schichtansicht",
                status="observed",
                object=str(oid),
                position=label,
                index=bar.slider.value(),
                layer_count=len(layers),
                readout=readout,
                note=bar.note.text(),
                note_visible=bar.note.isVisible(),
                legend=[
                    widget.text()
                    for widget in bar.findChildren(QLabel)
                    if widget.isVisible() and widget not in (bar.readout, bar.note)
                ],
                viewport_layer_z=float(expected_layer.z),
                viewport_contour_actors=len(window.viewport._layer_actors),
                slice_worker_running=window._slice_worker is not None
                and window._slice_worker.isRunning(),
            )
            probe.shot("04-layers-" + label)
        unchanged = (
            probe.session.last_result is result_before
            and len(probe.session.project.document.ops) == operation_count
        )
        probe.log(
            "Schichtansicht abgeschlossen",
            status="observed" if unchanged else "failed",
            object=str(oid),
            seconds=time.monotonic() - started,
            layer_count=len(layers),
            document_unchanged=unchanged,
            note="Geometrische Schichtanalyse, keine G-Code-Werkzeugwege.",
        )
    except Exception as error:
        probe.log(
            "Schichtansicht",
            status="failed",
            object=str(oid),
            seconds=time.monotonic() - started,
            error=str(error),
            note=bar.note.text(),
            readout=bar.readout.text(),
            slice_pending=probe.plain(window._slice_pending),
            slice_worker_running=window._slice_worker is not None
            and window._slice_worker.isRunning(),
        )
        try:
            probe.shot("04-layers-failed")
        except Exception:
            pass
    finally:
        if window.tools.active() == "layers":
            probe.click(window.tools._buttons["layers"])
            probe.settle(200)
        probe.log(
            "Schichtwerkzeug geschlossen",
            status="observed",
            object=str(oid),
            tool=window.tools.active(),
            bar_visible=bar.isVisible(),
            viewport_layer_cleared=window.viewport._layer is None,
        )
        if window._slice_worker is not None and window._slice_worker.isRunning():
            # Dieser Worker bietet keinen öffentlichen Abbruchknopf. Nicht mit
            # parallelen Bearbeitungen fortfahren, während er nach dem Budget weiterläuft.
            raise TimeoutError(
                "Schichtanalyse rechnet nach ihrem Zeitbudget weiter; Dateiprüfung wird angehalten"
            )
