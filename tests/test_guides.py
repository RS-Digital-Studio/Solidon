"""Die Bildanleitungen und die Gliederung des Handbuchs (Konzept Handbuch §4, §5).

Geprüft wird, was eine Anleitung brauchbar macht, bevor es ein Bild gibt:
kurze Schritte, Ziele aus dem gemeinsamen Wortschatz, Abbildungen, die der
Katalog kennt, und eine Gliederung, in der keine Seite fehlt und keine
doppelt steht. Die Bilder selbst entstehen beim Release; ob sie zur Version
passen, prüft ein Test mit Marker ``rendered``.
"""

from __future__ import annotations

import json
from typing import get_args

import pytest

from app.branding import APP_VERSION
from app.core import figures, guides, manual, tour
from app.core.bootstrap import load_operations
from app.i18n import tr
from app.i18n.catalog import available_languages

load_operations()


@pytest.mark.parametrize("guide", guides.GUIDES, ids=lambda guide: guide.key)
def test_every_guide_is_complete(guide: guides.Guide) -> None:
    assert str(guide.title).strip(), guide.key
    assert str(guide.summary).strip(), guide.key
    assert guide.steps, f"{guide.key}: eine Anleitung ohne Schritt"
    for number, one in enumerate(guide.steps, 1):
        assert str(one.text).strip(), f"{guide.key} Schritt {number}: ohne Satz"
        assert one.marks, f"{guide.key} Schritt {number}: ein Bild, das auf nichts zeigt"


def test_guide_keys_are_unique_and_differ_from_every_page() -> None:
    keys = [guide.key for guide in guides.GUIDES]
    assert len(keys) == len(set(keys))
    written = {page.key for page in manual.INTRODUCTION}
    assert not written & set(keys), "eine Anleitung heißt wie eine geschriebene Seite"


@pytest.mark.parametrize("guide", guides.GUIDES, ids=lambda guide: guide.key)
def test_every_step_is_short(guide: guides.Guide) -> None:
    """Ein Schritt ist ein Satz unter einem Bild, gezählt an der deutschen Quelle."""
    for number, one in enumerate(guide.steps, 1):
        words = len(str(one.text).split())
        assert words <= guides.MAX_STEP_WORDS, f"{guide.key} Schritt {number}: {words} Wörter"
        for mark in one.marks:
            label = len(str(mark.label).split())
            assert label <= guides.MAX_LABEL_WORDS, f"{guide.key}: {mark.label}"


@pytest.mark.parametrize("guide", guides.GUIDES, ids=lambda guide: guide.key)
def test_every_mark_names_a_target_of_the_vocabulary(guide: guides.Guide) -> None:
    for number, one in enumerate(guide.steps, 1):
        for mark in one.marks:
            assert guides.is_target(mark.target), f"{guide.key} Schritt {number}: {mark.target}"


@pytest.mark.parametrize("guide", guides.GUIDES, ids=lambda guide: guide.key)
def test_a_legend_labels_every_mark(guide: guides.Guide) -> None:
    """Halb beschriftet hieße: Eine Nummer im Bild, zu der unten nichts steht."""
    for number, one in enumerate(guide.steps, 1):
        if one.is_legend:
            unlabelled = [mark.target for mark in one.marks if not str(mark.label)]
            assert not unlabelled, f"{guide.key} Schritt {number}: {unlabelled}"


def test_the_vocabulary_accepts_named_kinds_and_nothing_else() -> None:
    assert guides.is_target("report")
    assert guides.is_target("command:file.open")
    assert guides.is_target("operation:drill_hole")
    assert guides.is_target("field:diameter")
    assert not guides.is_target("reports")
    assert not guides.is_target("command:")
    assert not guides.is_target("widget:report")
    assert not guides.is_target("field:Durchmesser")


def test_the_tour_points_at_targets_of_the_same_vocabulary() -> None:
    """Tour und Anleitung zeigen auf dieselben Bereiche und fragen dieselbe Auflösung."""
    assert set(get_args(tour.TourTarget)) <= guides.TARGETS


def test_every_step_has_its_figure_in_the_catalogue() -> None:
    """Der Alt-Text nennt Anleitung, Schritt und Satz — vorgelesen weiß man, wo man steht."""
    for guide in guides.GUIDES:
        for number, (key, one) in enumerate(
            zip(guide.figure_keys(), guide.steps, strict=True), start=1
        ):
            figure = figures.find(key)
            assert figure is not None, key
            assert figure.kind == "shot", key
            alt = str(figure.alt)
            assert str(guide.title) in alt and str(number) in alt, alt
            assert alt.endswith(str(one.text)), alt


def test_the_outline_holds_every_written_page_and_guide_exactly_once() -> None:
    placed = [key for _part, keys in manual.OUTLINE for key in keys]
    expected = [
        *(page.key for page in manual.INTRODUCTION),
        manual.SPACEMOUSE_ACCESS,
        *(guide.key for guide in guides.GUIDES),
    ]
    assert sorted(placed) == sorted(expected)


def test_the_outline_names_every_part_once_in_the_order_of_the_titles() -> None:
    assert [part for part, _keys in manual.OUTLINE] == list(manual.PART_TITLES)
    assert set(manual.PART_TITLES) == set(get_args(manual.Part))


def test_the_pages_follow_the_outline_and_the_generated_ones_close_the_reference() -> None:
    order = list(manual.PART_TITLES)
    pages = manual.pages()
    positions = [order.index(page.part) for page in pages]
    assert positions == sorted(positions), "die Teile stehen nicht in ihrer Reihenfolge"
    generated = [page for page in pages if page.generated]
    assert generated == list(pages[-len(generated) :])
    assert {page.part for page in generated} == {"reference"}


def test_a_guide_page_shows_each_step_with_its_number_and_its_picture() -> None:
    guide = guides.Guide(
        key="probe",
        title="Probe",
        summary="Zwei Schritte.",
        part="tasks",
        steps=(guides.step("Erst das.", "report"), guides.step("Dann das.", "history")),
    )
    page = manual.guide_page(guide)
    body = str(page.body)

    assert page.part == "tasks"
    assert body.index("**1.** Erst das.") < body.index("![](figure:guide-probe-1)")
    assert body.index("![](figure:guide-probe-1)") < body.index("**2.** Dann das.")
    assert page.figures() == ("guide-probe-1", "guide-probe-2")


def test_a_legend_lists_what_its_numbers_stand_for() -> None:
    guide = guides.Guide(
        key="probe",
        title="Probe",
        summary="Eine Legende.",
        part="start",
        steps=(guides.legend("Die Bereiche.", ("tree", "Links."), ("report", "Rechts.")),),
    )
    body = str(manual.guide_page(guide).body)

    assert body.startswith("Die Bereiche."), "ein einzelner Schritt trägt keine Nummer"
    assert body.endswith("1. Links.\n2. Rechts.")


def test_the_text_output_keeps_the_steps_and_drops_their_pictures() -> None:
    """Das Schrittbild wiederholt den Satz; im reinen Text stünde er sonst zweimal.

    Gezählt wird die Zeile des Schritts mit ihrer Nummer, nicht der Satz allein:
    „Klicken Sie auf *Bohrung setzen*." steht als eigener Schritt und zugleich
    im Satz des Schritts davor.
    """
    for guide in guides.GUIDES:
        page = manual.find(guide.key)
        assert page is not None, guide.key
        text = manual.without_figures(page.text())
        assert "figure:" not in text
        assert f"*{tr('Abbildung')}:" not in text, guide.key
        numbered = len(guide.steps) > 1
        for number, one in enumerate(guide.steps, 1):
            line = f"**{number}.** {one.text}" if numbered else str(one.text)
            assert text.count(line) == 1, line


def test_every_name_of_the_vocabulary_has_its_resolution_in_the_interface() -> None:
    """Ein Name im Kern, den die Oberfläche nicht kennt, scheiterte erst beim Release."""
    from app.ui import guide_targets

    assert guides.TARGETS == guide_targets.RESOLVED


def test_every_guide_has_its_story_and_no_story_is_left_over() -> None:
    """Die Geschichte geht den Weg der Anleitung; ohne sie entsteht kein Bild."""
    from tools import make_guides

    assert set(make_guides.STORIES) == {guide.key for guide in guides.GUIDES}


def test_the_fingerprint_follows_what_the_pictures_show() -> None:
    """Ein neuer Schritt oder ein anderes Ziel verlangt neue Bilder; ein Tippfehler im
    Satz eines anderen Schritts ändert den Abdruck auch — der Satz steht im Alt-Text."""
    base = guides.Guide("probe", "Probe", "Kurz.", "tasks", (guides.step("Eins.", "report"),))
    other_target = guides.Guide("probe", "Probe", "Kurz.", "tasks", (guides.step("Eins.", "tree"),))
    more = guides.Guide(
        "probe",
        "Probe",
        "Kurz.",
        "tasks",
        (guides.step("Eins.", "report"), guides.step("Zwei.", "tree")),
    )
    assert guides.fingerprint(base) == guides.fingerprint(base)
    assert guides.fingerprint(base) != guides.fingerprint(other_target)
    assert guides.fingerprint(base) != guides.fingerprint(more)


@pytest.mark.rendered
@pytest.mark.parametrize("language", available_languages())
def test_the_guide_pictures_belong_to_this_version(language: str) -> None:
    """Die Bilder entstehen beim Release (Konzept Handbuch §6); zwischen zwei
    Releases ist dieser Test rot, und das ist ein Zustand, kein Fund."""
    stamp_path = figures.IMAGE_ROOT / language / "guides.json"
    assert stamp_path.is_file(), f"{stamp_path} fehlt — tools/make_guides.py lief nicht"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))["guides"]
    for guide in guides.GUIDES:
        entry = stamp.get(guide.key)
        assert entry is not None, f"{language}: {guide.key} nie aufgenommen"
        assert entry["version"] == APP_VERSION, f"{language}: {guide.key} von {entry['version']}"
        assert entry["fingerprint"] == guides.fingerprint(guide), (
            f"{language}: {guide.key} wurde seit der Aufnahme geändert"
        )
        for key in guide.figure_keys():
            figure = figures.find(key)
            assert figure is not None and figure.available(language), f"{language}: {key}"


def test_the_fixed_targets_resolve_on_a_real_window(qt_app: object) -> None:
    """Jeder feste Name findet sein Widget am Fenster, wie die Anwendung es baut.

    Die Namen, die einen Zustand brauchen — ein offener Dialog, ein gewählter
    Befund, ein Schritt im Verlauf —, prüft erst die Aufnahme beim Release;
    hier geht es um die, die immer da sind.
    """
    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    stateful = {"dialog", "dialog.accept", "report.action", "history.last"}
    window = MainWindow(Session(), UiSettings())
    try:
        for name in sorted(guide_targets.RESOLVED - stateful):
            assert guide_targets.widget_for(window, name) is not None, name
        with pytest.raises(guide_targets.MissingTargetError):
            guide_targets.widget_for(window, "dialog")
        with pytest.raises(guide_targets.MissingTargetError):
            guide_targets.area_for(window, "history.last")
    finally:
        window.close()
        window.deleteLater()
