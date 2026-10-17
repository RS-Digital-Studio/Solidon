"""Der graue *Übernehmen* der Flächenkarte nennt seinen Weg (FD-99-Rest).

Am Schlusslauf (nativ, 1920 und 125 %) stand am grauen *Übernehmen* von
*Fläche versetzen* mit Weg 0 mm als Kurzhilfe und zugängliche Beschreibung nur
„Fläche versetzen“. Ursache: Das Merkmalfenster stellt die Handlung scharf,
solange seine Karte noch verborgen ist, und fragte das erste offene Feld am
Fenster — das Feld war dort nicht sichtbar, der Satz blieb leer, und danach
fragte niemand mehr. Geprüft am Hauptfenster wie im Schlusslauf, mit einem
Klick auf die Fläche im Baum, in jeder Sprache.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.core.scene.project import save
from app.i18n import get_language, set_language, tr
from app.i18n.catalog import available_languages, install_language
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tools import function_scenes


def _rounds(qt_app: QApplication, count: int = 60) -> None:
    for _ in range(count):
        qt_app.processEvents()
        time.sleep(0.005)


@pytest.mark.parametrize("language", available_languages())
def test_the_grey_apply_of_a_face_names_its_field(
    qt_app: QApplication, tmp_path: Path, language: str
) -> None:
    spoken = get_language()
    install_language(language)
    set_language(language)
    path = tmp_path / "flaeche.p3d"
    save(function_scenes.build_scene("merkmal.face.exakt"), path)
    window = MainWindow(Session(), UiSettings())
    try:
        window.resize(1920, 1009)
        window.show()
        window._show_start_screen(False)
        window.open_path(path)
        assert window.session.wait_for_idle(60_000)
        _rounds(qt_app)
        window.object_tree.select_feature("obj_1", "face_6")
        assert window.session.wait_for_idle(60_000)
        _rounds(qt_app, 120)
        panel = window.feature_panel
        entry = panel._runs[panel._armed or ""]
        button = panel._apply
        assert entry.op == "push_face" and not button.isEnabled(), (
            "Voraussetzung: *Fläche versetzen* scharf, Übernehmen grau",
            entry.op,
            button.isEnabled(),
        )
        row = next(row for row in panel._shown_rows.values() if row.key == panel._armed)
        field = row.widgets["distance"].accessibleName().rsplit(" — ", 1)[-1]
        wanted = tr("Erst „{field}“ ändern, dann übernehmen.", field=field)
        assert button.toolTip() == wanted, (button.toolTip(), wanted)
        assert button.accessibleDescription() == wanted, button.accessibleDescription()
    finally:
        window.wait_for_workers()
        window.hide()
        window.deleteLater()
        qt_app.processEvents()
        install_language(spoken)
        set_language(spoken)
