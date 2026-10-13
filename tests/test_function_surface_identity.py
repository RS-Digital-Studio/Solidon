"""Eine lebende Qt-Fläche bleibt dieselbe, auch bei kurzlebigen Pythonhüllen (FD55)."""

import gc
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget

from tools import function_bench, function_surface


def test_cpp_file_dialog_is_still_without_a_wrapper_held_by_the_test(qt_app, tmp_path):
    """Der statische Qt-Aufruf erzeugt den Dialog in C++, ohne dauerhafte Pythonreferenz."""
    host = QWidget()
    host._op_dialog = None
    host.show()
    flow = object.__new__(function_bench.FunctionFlow)
    flow.window = host
    flow.row = {"target": "finding.action:export_as_mesh"}
    flow.data = {"unmeasured": {}}
    step = flow.still_step("Dateidialog", lambda: function_surface.open_dialog(host), at_most_s=0.8)
    completed = []
    failures = []

    def close():
        dialog = QApplication.activeModalWidget()
        if dialog is not None:
            dialog.reject()

    def tick():
        try:
            gc.collect()
            if step.ready():
                completed.append(flow.restless)
                close()
                return
            timer.start(15)
        except Exception as error:
            failures.append(error)
            close()

    timer = QTimer(host)
    timer.setSingleShot(True)
    timer.timeout.connect(tick)
    watchdog = QTimer(host)
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(close)
    watchdog.start(3000)
    timer.start(150)
    try:
        selected = QFileDialog.getSaveFileName(
            host,
            "Prüfstand Dateidialog",
            str(tmp_path),
            "STEP (*.step)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
    finally:
        timer.stop()
        watchdog.stop()
        host.close()
    assert not failures
    assert selected == ("", "")
    assert completed == [None], flow.data["unmeasured"]


class Surface:
    """Unbewegte Rechtecke ohne Fenster; die Signatur liest dieselbe öffentliche Schnittstelle."""

    def __init__(self):
        self.size = 100

    def mapToGlobal(self, point):  # noqa: N802 - öffentliche Qt-Schnittstelle
        return QPoint(0, 0)

    def width(self):
        return self.size

    def height(self):
        return 80

    def findChildren(self, kind):  # noqa: N802 - öffentliche Qt-Schnittstelle
        return []


@pytest.mark.parametrize("change", ["geometry", "root", "moving"])
def test_real_geometry_and_surface_changes_still_restart_the_quiet_period(monkeypatch, change):
    """Ein ruhiger Vorgänger oder gleiche Rechtecke machen eine neue Fläche nicht sofort still."""
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(function_bench.time, "perf_counter", lambda: clock.now)
    root = Surface()
    flow = object.__new__(function_bench.FunctionFlow)
    flow.window = None
    flow.row = {"target": "finding.action:export_as_mesh"}
    flow.data = {"unmeasured": {}}
    step = flow.still_step("Fläche", lambda: root, at_most_s=0.8)
    assert not step.ready()
    clock.now = 0.2
    if change == "root":
        root = Surface()
    else:
        root.size += 1
    assert not step.ready()
    clock.now = 0.4
    assert not step.ready()
    if change == "moving":
        for moment in (0.45, 0.6, 0.75):
            clock.now = moment
            root.size += 1
            assert not step.ready()
        clock.now = 0.85
        assert step.ready()
        assert flow.restless and flow.data["unmeasured"]
    else:
        clock.now = 0.55
        assert step.ready()
        assert flow.restless is None and not flow.data["unmeasured"]
