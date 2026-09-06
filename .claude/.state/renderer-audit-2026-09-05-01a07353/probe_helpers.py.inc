def plain(value):
    if dataclasses.is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [plain(v) for v in value]
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)

def write():
    payload = json.dumps(results, ensure_ascii=False, indent=2)
    temporary = OUT / ("result-" + str(os.getpid()) + ".tmp")
    for attempt in range(20):
        try:
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(OUT / "result.json")
            return
        except OSError:
            if attempt == 19:
                raise
            time.sleep(0.05)

def log(label, **values):
    row = {"time": time.strftime("%H:%M:%S"), "label": label, **plain(values)}
    results["checks"].append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    write()

def pump_events():
    """Pumpt Qt einschließlich der ohne echte Ereignisschleife offenen Löschaufträge."""
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def settle(ms=150):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        pump_events()
        time.sleep(0.01)

def wait(label, condition, seconds=120):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        pump_events()
        if condition():
            settle(100)
            return
        time.sleep(0.02)
    modal = app.activeModalWidget()
    popup = app.activePopupWidget()
    log("Wartebedingung nicht erfüllt", status="probe_timeout", waiting_for=label, busy=session.busy, transactions=len(session.project.document.transactions) if session.project else None, undo_enabled=window.undo_action.isEnabled(), redo_enabled=window.redo_action.isEnabled(), modal=modal.windowTitle() if modal else None, popup=popup.windowTitle() if popup else None)
    raise TimeoutError(label)

def click(widget):
    for parent in window.findChildren(QScrollArea):
        if parent.isAncestorOf(widget):
            parent.ensureWidgetVisible(widget)
    settle(40)
    QTest.mouseMove(widget, widget.rect().center())
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=widget.rect().center())
    settle(80)

def guard():
    global pending_file, pending_filter, guard_active, last_heartbeat
    if guard_active:
        return
    if time.monotonic() - last_heartbeat > 15:
        last_heartbeat = time.monotonic()
        print("STATUS", time.strftime("%H:%M:%S"), "busy=", session.busy, "result=", session.last_result is not None, "text=", window.status_message.text(), flush=True)
    modal = app.activeModalWidget()
    if modal is None:
        return
    guard_active = True
    try:
        if isinstance(modal, QFileDialog) and pending_file is not None:
            destination = pending_file
            modal.setDirectory(str(destination.parent))
            if pending_filter is not None:
                matching = next((f for f in modal.nameFilters() if pending_filter.lower() in f.lower()), None)
                if matching:
                    modal.selectNameFilter(matching)
                pending_filter = None
            modal.selectFile(str(destination))
            edit = modal.findChild(QLineEdit, "fileNameEdit")
            if edit is not None:
                edit.setText(str(destination))
            settle(300)
            boxes = modal.findChildren(QDialogButtonBox)
            button = next((b for box in boxes for b in box.buttons() if box.buttonRole(b) == QDialogButtonBox.ButtonRole.AcceptRole), None)
            results["dialogs"].append({"type": "file", "title": modal.windowTitle(), "path": str(destination)})
            if button is not None:
                print("DATEIDIALOG", button.text(), button.isEnabled(), modal.selectedFiles(), flush=True)
                modal.screen().grabWindow(int(modal.winId())).save(str(OUT / "00-file-dialog.png"))
                if button.isEnabled():
                    pending_file = None
                    QTest.mouseClick(button, Qt.MouseButton.LeftButton, pos=button.rect().center())
            write()
        elif modal.__class__.__name__ == "AskDialog":
            labels = [v.text() for v in modal.findChildren(QLabel)]
            choices = [modal.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(modal.list.count())]
            preferred = next((i for i, c in enumerate(choices) if str(c).lower() == "mm"), 0)
            item = modal.list.item(preferred)
            QTest.mouseClick(modal.list.viewport(), Qt.MouseButton.LeftButton, pos=modal.list.visualItemRect(item).center())
            results["dialogs"].append({"type": "question", "labels": labels, "choices": choices, "chosen": choices[preferred]})
            QTest.mouseClick(modal._accept, Qt.MouseButton.LeftButton, pos=modal._accept.rect().center())
            write()
        elif isinstance(modal, QMessageBox):
            description = modal.text() + " " + modal.informativeText()
            buttons = modal.buttons()
            texts = [b.text() for b in buttons]
            results["dialogs"].append({"type": "message", "text": description, "buttons": texts})
            print("DIALOG", description, texts, flush=True)
            preferred = next((b for b in buttons if any(t in b.text().lower() for t in ("millimeter", "verwerfen", "schließen", "weiter", "ok"))), None)
            if preferred is None:
                preferred = next((b for b in buttons if modal.buttonRole(b) in (QMessageBox.ButtonRole.AcceptRole, QMessageBox.ButtonRole.YesRole)), None)
            if preferred is not None:
                QTest.mouseClick(preferred, Qt.MouseButton.LeftButton, pos=preferred.rect().center())
            write()
        elif modal.__class__.__name__ not in ("OperationDialog",):
            token = (modal.__class__.__name__, modal.windowTitle())
            if token not in handled_dialogs:
                handled_dialogs.add(token)
                labels = [v.text() for v in modal.findChildren(QLabel)]
                buttons = [b for b in modal.findChildren(QAbstractButton) if b.isVisible()]
                results["dialogs"].append({"type": token[0], "title": token[1], "labels": labels, "buttons": [b.text() for b in buttons]})
                print("UNBEKANNTER DIALOG", token, labels, [b.text() for b in buttons], flush=True)
                write()
    except Exception:
        print(traceback.format_exc(), flush=True)
    finally:
        try:
            pump_events()
        finally:
            guard_active = False

def scene_data():
    result = session.last_result
    if result is None:
        return None
    objects = []
    for oid, obj in result.scene.objects.items():
        mesh = obj.mesh
        features = {str(fid): {"kind": f.kind, "params": plain(f.params), "face_count": len(f.face_indices)} for fid, f in obj.features.items()}
        objects.append({"id": str(oid), "name": str(obj.name), "kind": obj.kind, "plate": obj.plate, "triangles": mesh.triangle_count, "bounds": [plain(mesh.bounds.minimum), plain(mesh.bounds.maximum)], "volume": float(mesh.volume), "watertight": bool(mesh.is_watertight), "components": mesh.component_count, "features": features})
    return {"objects": objects, "stopped_at": plain(result.stopped_at), "findings": plain(result.scene.report.findings)}

def tree_items():
    iterator = QTreeWidgetItemIterator(window.object_tree.tree)
    items = []
    while iterator.value():
        items.append(iterator.value())
        iterator += 1
    return items

def select_item(item):
    tree = window.object_tree.tree
    parent = item.parent()
    while parent:
        parent.setExpanded(True)
        parent = parent.parent()
    expected = item.data(1, Qt.ItemDataRole.UserRole)
    for attempt in range(3):
        tree.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
        settle(550 if attempt else 150)
        rectangle = tree.visualItemRect(item).intersected(tree.viewport().rect())
        if rectangle.height() < 8 or tree.itemAt(rectangle.center()) is not item:
            continue
        QTest.mouseMove(tree.viewport(), rectangle.center())
        QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rectangle.center())
        settle(250)
        if item.isSelected() and (not expected or window.feature_panel.feature_id == expected):
            return
        log("Auswahl benötigt Wiederholung", attempt=attempt+1, expected=str(expected), selected=window.feature_panel.feature_id, rect=[rectangle.x(), rectangle.y(), rectangle.width(), rectangle.height()], viewport=[tree.viewport().width(), tree.viewport().height()])
    raise RuntimeError("Baumklick erreicht Auswahl nicht: " + str(expected or item.text(0)))
