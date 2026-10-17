"""Nach einem Absturz des Grundlagenarbeiters gilt Solidons Tabelle, und „vorläufig“ geht (RA-14).

Die Zahlenzeile nennt Material und Druckdauer „vorläufig“, solange die Werte des
gewählten Slicerprofils gelesen werden (FD-89). Stürzte der Arbeiter ab, merkte
sich das Fenster nur, dass er nicht mehr läuft; die Zahl blieb für immer
vorläufig, und die Kurzhilfe sagte weiter, es werde gelesen. Jetzt gilt nach dem
Absturz die Tabelle als Grundlage — der Sollwert ist
``manufacturer.base_settings`` ohne Profil —, und die Zeile sagt nichts mehr
Vorläufiges.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from app.core.export import manufacturer
from app.core.scene import OperationDraft
from app.ui import main_window as main_window_module
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import wait_until


@pytest.fixture
def window(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[MainWindow]:
    def crash(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("Profilbestand nicht lesbar")

    monkeypatch.setattr(main_window_module, "_chosen_with_stock", crash)
    built = MainWindow(Session(), UiSettings())
    built.resize(1600, 1000)
    built.show()
    built._show_start_screen(False)
    yield built
    assert built.session.wait_for_idle(60_000)
    built.release()
    built.deleteLater()
    qt_app.processEvents()


def test_after_a_crash_the_table_is_the_foundation(
    qt_app: QApplication, window: MainWindow
) -> None:
    assert window.session.apply("Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(60_000)
    wait_until(
        qt_app,
        lambda: window._foundation_pending is None and window._foundation_worker is None,
    )
    for _round in range(10):
        qt_app.processEvents()

    settings = window.effective_print_settings()
    quality = settings.quality
    cached = window._foundation_cache
    assert cached is not None, "nach dem Absturz gilt eine Grundlage"
    assert cached[0] == window._foundation_key(quality)
    assert cached[1] == manufacturer.base_settings(window.session.profile, quality, None), (
        "die Tabelle, ohne Slicerprofil"
    )
    window._update_facts()
    summary, delta = window.facts.state()
    assert summary, "die Zeile zeigt eine Zahl"
    assert delta != "vorläufig", delta
    assert "Vorläufig" not in window.facts.toolTip(), window.facts.toolTip()
