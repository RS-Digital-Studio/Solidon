"""Die Bildanleitungen und die Gliederung des Handbuchs (Konzept Handbuch §4, §5).

Geprüft wird, was eine Anleitung brauchbar macht, bevor es ein Bild gibt:
kurze Schritte, Ziele aus dem gemeinsamen Wortschatz, Abbildungen, die der
Katalog kennt, und eine Gliederung, in der keine Seite fehlt und keine
doppelt steht. Die Bilder selbst entstehen beim Release; ob sie zur Version
passen, prüft ein Test mit Marker ``rendered``.
"""

from __future__ import annotations

from typing import get_args

import pytest

from app.core import figures, guides, manual, tour
from app.core.bootstrap import load_operations

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
    """Das Schrittbild wiederholt den Satz; im reinen Text stünde er sonst zweimal."""
    for guide in guides.GUIDES:
        page = manual.find(guide.key)
        assert page is not None, guide.key
        text = manual.without_figures(page.text())
        assert "figure:" not in text
        for one in guide.steps:
            assert text.count(str(one.text)) == 1, one.text
