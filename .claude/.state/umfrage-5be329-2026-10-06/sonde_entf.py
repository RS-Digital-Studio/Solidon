"""Sonde: Entf im Reiter Auswahl und bei angehaltener Kette."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path


def main() -> None:
    tree, project, out_path = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    out = open(out_path, "w", encoding="utf-8", buffering=1)

    def say(text: str) -> None:
        out.write(text + "\n")

    home = Path(tempfile.mkdtemp(prefix="sonde_entf2_"))
    os.environ["APPDATA"] = str(home / "roaming")
    os.environ["LOCALAPPDATA"] = str(home / "local")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, tree)
    import faulthandler

    faulthandler.enable(all_threads=True)
    faulthandler.dump_traceback_later(400, exit=True)
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QPushButton

    import app.ui.main_window as mw

    say(f"gemessen wird {Path(mw.__file__).resolve()}")
    from app.core.bootstrap import load_operations
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    qt = QApplication.instance() or QApplication([])
    load_operations()
    window = MainWindow(Session(), UiSettings())
    window.resize(1600, 900)
    window.show()
    window.open_path(project)
    end = time.monotonic() + 180
    while window.session.last_result is None and time.monotonic() < end:
        window.session.wait_for_idle()
        QTest.qWait(50)
    QTest.qWait(1500)

    def ops() -> list[str]:
        return [f"{e.id}:{e.op}" for e in window.session.project.document.ops]

    def settle() -> None:
        window.session.wait_for_idle()
        QTest.qWait(800)
        window.session.wait_for_idle()
        QTest.qWait(200)

    def child_ids() -> list[tuple[str, str]]:
        t = window.object_tree.tree
        for i in range(t.topLevelItemCount()):
            it = t.topLevelItem(i)
            if it.data(0, Qt.ItemDataRole.UserRole) == "obj_3":
                return [
                    (it.child(j).text(0), it.child(j).data(1, Qt.ItemDataRole.UserRole))
                    for j in range(it.childCount())
                ]
        return []

    def wait_children() -> None:
        end = time.monotonic() + 60
        while time.monotonic() < end and not child_ids():
            QTest.qWait(200)

    def press(target, label: str, undo: bool = True) -> None:
        before = ops()
        window.announce("")
        target.setFocus(Qt.FocusReason.MouseFocusReason)
        qt.processEvents()
        twin = window.feature_instead_of("delete_object")
        obj = window._selected_feature_object()
        say(
            f"  vor [{label}]: {window.object_tree.selected()}/{window.object_tree.selected_feature()} "
            f"Merkmal im Ergebnis={getattr(obj, 'kind', None)} Zwilling={getattr(twin, 'name', None)}"
        )
        focus = QApplication.focusWidget()
        QTest.keyClick(focus or target, Qt.Key.Key_Delete)
        settle()
        after = ops()
        say(
            f"[{label}] Fokus={type(focus).__name__ if focus else None} "
            f"neu={after[len(before):] if len(after) > len(before) else '-'} "
            f"Status={window.status_message.text()!r}"
        )
        if undo and len(after) != len(before):
            window.undo_action.trigger()
            settle()
            wait_children()

    end = time.monotonic() + 240
    while window.session.busy and time.monotonic() < end:
        window.session.wait_for_idle()
        QTest.qWait(100)
    say(f"Erstauswertung fertig nach Warten, busy={window.session.busy}")
    last, still_since = None, time.monotonic()
    end = time.monotonic() + 120
    while time.monotonic() < end:
        now = child_ids()
        if now != last:
            last, still_since = now, time.monotonic()
        elif time.monotonic() - still_since > 4:
            break
        QTest.qWait(250)
    say(f"Stiftzeilen ruhig: {last}")
    hole = next(fid for text, fid in child_ids() if fid and fid.startswith("hole"))
    # 1) Merkmal gewählt, Fokus auf einem Knopf im Reiter Auswahl
    from app.ui import panels as P
    t = window.object_tree.tree
    tops = [t.topLevelItem(i) for i in range(t.topLevelItemCount())]
    say(f"Kopfzeilen: {[(x.text(0), x.data(0, Qt.ItemDataRole.UserRole)) for x in tops]}")
    for x in tops:
        if x.data(0, Qt.ItemDataRole.UserRole) == "obj_3":
            hit = P._feature_item(x, hole)
            say(f"  _feature_item -> {hit.text(0) if hit else None}")
    seen = []
    window.object_tree.featureSelected.connect(lambda f: seen.append(("featureSelected", f)))
    window.object_tree.selectionChanged.connect(lambda o: seen.append(("selectionChanged", o)))
    window.object_tree.select_feature("obj_3", hole)
    say(f"  direkt danach: {window.object_tree.selected()}/{window.object_tree.selected_feature()} Signale={seen}")
    t0 = time.monotonic()
    last_line = None
    while time.monotonic() - t0 < 6:
        res = window.session.last_result
        line = (
            window.object_tree.selected(), window.object_tree.selected_feature(),
            window.session.busy, id(res), [fid for _t, fid in child_ids()],
        )
        if line != last_line:
            say(f"  t={time.monotonic() - t0:5.2f} Auswahl={line[0]}/{line[1]} busy={line[2]} Ergebnis={line[3] % 100000} Zeilen={line[4]}")
            last_line = line
        QTest.qWait(50)
    say(f"  Signale insgesamt={seen}")
    import app.core.scene.history as H
    say(f"  Schritte={ops()}")
    settle()
    buttons = [
        w
        for w in window.feature_dock.findChildren(QPushButton)
        if w.isVisible() and w.isEnabled() and w.focusPolicy() != Qt.FocusPolicy.NoFocus
    ]
    say(f"Knöpfe im Reiter: {[b.text() for b in buttons][:6]}")
    if buttons:
        press(buttons[0], f"Merkmal {hole}, Knopf im Reiter")
    # 2) Fokus in einem Zahlenfeld im Reiter: Entf gehört dem Feld
    window.object_tree.select_feature("obj_3", hole)
    settle()
    from PySide6.QtWidgets import QLineEdit
    spins = [w for w in window.feature_dock.findChildren(QLineEdit) if w.isVisibleTo(window.feature_dock) and not w.isReadOnly()]
    say(f"Zahlenfelder im Reiter: {len(spins)}")
    if spins:
        spin = spins[0]
        spin.setFocus()
        qt.processEvents()
        spin.setText("Bohrung")
        spin.setCursorPosition(0)
        text_before = spin.text()
        press(spin, "Merkmal, Zahlenfeld im Reiter")
        say(f"  Feldtext vorher={text_before!r} nachher={spin.text()!r}")
    # 3) Kette angehalten: Verrundung auf 3 mm
    fillet = next(e for e in window.session.project.document.ops if e.op == "fillet_edges")
    window.session.change_params(fillet.id, {**fillet.params, "radius": 3.0})
    settle()
    say(f"Halt: {window.session.halted_step()} Aktion an? {window._op_actions['delete_object'].isEnabled()}")
    window.object_tree.select_object("obj_3")
    settle()
    press(window.object_tree, "Halt, Körper, Baum", undo=False)
    press(window.viewport, "Halt, Körper, Ansicht", undo=False)
    window.object_tree.select_object(None)
    settle()
    press(window.object_tree, "Halt, ohne Auswahl, Baum", undo=False)
    say("fertig")
    out.close()
    os._exit(0)


if __name__ == "__main__":
    main()
