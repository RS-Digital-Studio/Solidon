"""Das Vorschauband zeigt die Legende nur, wo sich Volumen ändert (FD-116).

*Objekt umbenennen* und *Material setzen* zeigten unter dem Band
„Hinzugefügt · Entfernt“, obwohl nichts hinzukam oder wegfiel. Die Legende
erklärt die Farben der Differenz; sie steht, sobald eine Differenz im Bild ist,
die Volumen hinzufügt oder wegnimmt — vorher gibt es keine Farben zu erklären.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from app.core.geom.difference import Difference, SceneDifference
from app.ui.viewport import Viewport

NOTE = "Vorschau — noch nicht übernommen"
HINT = "Leertaste halten: vorher"


@pytest.fixture
def view(qt_app: QApplication) -> Iterator[Viewport]:
    shown = Viewport()
    shown.resize(1280, 800)
    shown.show()
    try:
        yield shown
    finally:
        shown.mark_preview("")
        shown.release()
        shown.close()
        shown.deleteLater()
        qt_app.processEvents()


def _legend_shown(view: Viewport) -> bool:
    QApplication.processEvents()
    assert view.banner.isVisible()
    return view.banner.legend.isVisibleTo(view.banner)


def test_a_preview_without_a_change_of_volume_shows_no_legend(view: Viewport) -> None:
    """Umbenennen: Die Differenz ist da und ändert nichts."""
    view.show_difference(SceneDifference(entries={"obj_1": Difference(object_id="obj_1")}))
    view.mark_preview(NOTE, HINT)
    assert not _legend_shown(view), "„Hinzugefügt · Entfernt“ ohne Volumenänderung"


def test_the_legend_follows_the_difference_on_screen(view: Viewport) -> None:
    view.mark_preview(NOTE, HINT)
    assert not _legend_shown(view), "ohne Differenz gibt es keine Farben zu erklären"

    grown = Difference(object_id="obj_1", added_volume=500.0)
    view.show_difference(SceneDifference(entries={"obj_1": grown}))
    assert _legend_shown(view), "mit Volumen steht die Legende"

    view.show_difference(SceneDifference(entries={"obj_1": Difference(object_id="obj_1")}))
    assert not _legend_shown(view)

    view.show_difference(SceneDifference(created=("obj_2",)))
    assert _legend_shown(view), "ein neuer Körper ist eine Änderung"

    view.show_difference(None)
    assert not _legend_shown(view), "die Differenz ist weg"
