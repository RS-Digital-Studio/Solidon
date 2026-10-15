"""Das Vorschauband bemisst wieder eingeblendete Inhalte mit (FD52)."""

from collections.abc import Iterator

import pytest
from PySide6.QtGui import QFont, QFontInfo, QFontMetrics
from PySide6.QtWidgets import QApplication

from app.core.geom.difference import Difference, SceneDifference
from app.i18n import get_language, set_language, tr
from app.i18n.catalog import install_language
from app.ui.style import apply_style
from app.ui.theme import apply_theme
from app.ui.viewport import Viewport
from tests.bundled_fonts import bundled_font


@pytest.fixture(params=[9, 13], ids=["9pt", "13pt"])
def preview_view(qt_app: QApplication, request: pytest.FixtureRequest) -> Iterator[Viewport]:
    """Inhaltsschrift und Thema wie im Betrieb, mit echter gebündelter Schrift.

    Schrift und Thema gibt ``conftest.py`` zurück, die Sprache diese Fixture.
    """
    previous_language = get_language()
    point_size = request.param
    with bundled_font(qt_app, point_size):
        apply_theme(qt_app, "dark")
        apply_style(qt_app, "dark")
        view = Viewport()
        view.resize(1920, 1080)
        view.show()
        qt_app.processEvents()
        try:
            assert (view.width(), view.height()) == (1920, 1080)
            actual_font = QFontInfo(view.banner.note.font())
            assert actual_font.family() == "DejaVu Sans"
            assert actual_font.pointSize() == point_size
            metrics = view.banner.note.fontMetrics()
            assert metrics.horizontalAdvance("WWW") > metrics.horizontalAdvance("iii")
            if point_size > 9:
                standard = QFontMetrics(QFont("DejaVu Sans", 9))
                wide = standard.horizontalAdvance("Vorschau")
                assert metrics.horizontalAdvance("Vorschau") > wide
                assert metrics.height() > standard.height()
            yield view
        finally:
            view.mark_preview("")
            view.release()
            view.close()
            view.deleteLater()
            qt_app.processEvents()
            set_language(previous_language)


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "it", "pt"])
@pytest.mark.parametrize("long_note", [False, True], ids=["kurz", "gegenstuecke"])
def test_preview_after_refusal_fits_the_restored_legend(
    qt_app: QApplication, preview_view: Viewport, language: str, long_note: bool
) -> None:
    """Eine Absage darf die nächste Legende nicht aus der Größenberechnung nehmen."""
    install_language(language)
    set_language(language)
    view = preview_view
    view.mark_preview(
        tr("Keine Vorschau: {reason}").format(reason=tr("Ohne Text gibt es nichts anzulegen.")),
        changes=False,
    )
    qt_app.processEvents()
    assert not view.banner.legend.isVisible()
    view.mark_preview("")
    qt_app.processEvents()
    assert not view.banner.isVisible()

    note = tr("Vorschau — noch nicht übernommen")
    if language != "de":
        assert note != "Vorschau — noch nicht übernommen", "Der Sprachkatalog wirkt nicht"
    if long_note:
        note += "\n" + " · ".join(
            (
                tr("Passstift und Passbohrung"),
                tr("Quader"),
                "40,00 × 30,00 × 20,00 mm → 47,99 × 30,00 × 20,00 mm",
                tr("Druckbefunde noch nicht geprüft"),
            )
        )
    # Die Legende steht nur über einer Differenz, die Volumen ändert (FD-116).
    grown = Difference(object_id="obj_1", added_volume=500.0)
    view.show_difference(SceneDifference(entries={"obj_1": grown}))
    view.mark_preview(note, tr("Leertaste halten: vorher"))
    banner = view.banner
    assert banner.isVisible() and banner.legend.isVisible()
    assert banner.width() >= banner.sizeHint().width(), (
        f"{language}: Band {banner.size()} unterschreitet den Bedarf {banner.sizeHint()}"
    )
    qt_app.processEvents()
    assert banner.width() >= banner.sizeHint().width()
    assert banner.legend.width() >= banner.legend.minimumSizeHint().width()
    assert banner.hint.width() >= banner.hint.minimumSizeHint().width()
    assert banner.note.height() >= banner.note.heightForWidth(banner.note.width())
    assert view.rect().contains(banner.geometry())
