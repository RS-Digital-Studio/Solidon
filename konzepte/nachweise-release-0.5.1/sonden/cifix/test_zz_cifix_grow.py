from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from app.ui.print_settings_dialog import SCREEN_MARGIN, PrintSettingsDialog
from app.ui.session import Session
from app.ui.settings import UiSettings


def test_alte_zusicherung_am_vollen_bildschirm(qt_app, tmp_path: Path, monkeypatch):
    session = Session()
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.wait_for_slicers()
    dialog._slicer_path = tmp_path / "orca-slicer.exe"
    dialog.slicer_box.setVisible(True)
    dialog.resize(dialog.sizeHint())
    dialog.show()
    qt_app.processEvents()
    before = dialog.height()
    real = dialog.screen().availableGeometry()
    print("\nechter Bildschirm", real.height(), "vorher", before)
    tight = QRect(real.x(), real.y(), real.width(), before + SCREEN_MARGIN)
    monkeypatch.setattr(dialog, "screen", lambda: SimpleNamespace(availableGeometry=lambda: QRect(tight)))
    dialog._open_slicer_section()
    qt_app.processEvents()
    print("nachher", dialog.height(), "Wunsch", dialog.sizeHint().height())
    with pytest.raises(AssertionError):
        assert dialog.height() > before
    dialog.close()
    session.release()
