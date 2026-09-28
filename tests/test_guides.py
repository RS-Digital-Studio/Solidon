"""Die Bildanleitungen und die Gliederung des Handbuchs (Konzept Handbuch §4, §5).

Geprüft wird, was eine Anleitung brauchbar macht, bevor es ein Bild gibt:
kurze Schritte, Ziele aus dem gemeinsamen Wortschatz, Abbildungen, die der
Katalog kennt, und eine Gliederung, in der keine Seite fehlt und keine
doppelt steht. Die Bilder selbst entstehen beim Release; ob sie zur Version
passen, prüft ein Test mit Marker ``rendered``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import get_args

import pytest

from app.branding import APP_VERSION
from app.core import figures, guides, manual, tour
from app.core.bootstrap import load_operations
from app.i18n import SOURCE_LANGUAGE, source_text, tr
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
    written |= {manual.WHERE_TO_START, manual.SPACEMOUSE_ACCESS}
    assert not written & set(keys), "eine Anleitung heißt wie eine geschriebene Seite"


def test_every_marked_operation_is_taught_by_its_guide() -> None:
    """Wer eine Operation im Bild zeigt, lehrt sie — F1 in ihrem Dialog führt hierher.

    Vergisst eine neue Anleitung ``teaches``, schlüge F1 im Dialog ihrer
    Operation die Referenz auf, obwohl es eine Anleitung dafür gibt.
    """
    for guide in guides.GUIDES:
        marked = {
            mark.target.partition(":")[2]
            for one in guide.steps
            for mark in one.marks
            if mark.target.startswith("operation:")
        }
        assert marked <= set(guide.teaches), f"{guide.key}: {sorted(marked - set(guide.teaches))}"


def test_every_taught_operation_exists_and_has_one_guide() -> None:
    """Eine Operation, die zwei Anleitungen lehren, hätte für F1 zwei Antworten."""
    from app.core.registry import REGISTRY

    taught = [name for guide in guides.GUIDES for name in guide.teaches]
    assert len(taught) == len(set(taught)), f"doppelt gelehrt: {sorted(taught)}"
    unknown = [name for name in taught if not REGISTRY.has(name)]
    assert not unknown, f"nicht im Register: {unknown}"


@pytest.mark.parametrize("language", available_languages())
def test_a_link_in_a_step_names_the_page_it_leads_to(language: str) -> None:
    """„Gedruckt wird wie in [Ein Modell prüfen und drucken]": Der Verweis heißt
    in jeder Sprache wie die Seite, die er aufschlägt, sonst sucht der Kunde in
    der Seitenliste einen Titel, den es nicht gibt."""
    from app.core import markup
    from app.i18n import set_language
    from app.i18n.catalog import install_language

    install_language(language)
    set_language(language)
    try:
        titles = {page.key: str(page.title) for page in manual.pages()}
        wrong = [
            f"{guide.key} Schritt {number}: {label!r} statt {titles.get(target)!r}"
            for guide in guides.GUIDES
            for number, one in enumerate(guide.steps, 1)
            for label, target in markup.MANUAL_LINK.findall(str(one.text))
            if label != titles.get(target)
        ]
    finally:
        set_language(SOURCE_LANGUAGE)
    assert not wrong, f"{language}:\n" + "\n".join(wrong)


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
    assert guides.is_target("part:screw_hole")
    assert not guides.is_target("reports")
    assert not guides.is_target("command:")
    assert not guides.is_target("widget:report")
    assert not guides.is_target("field:Durchmesser")


def test_every_named_operation_and_part_exists() -> None:
    """Ein umbenannter Baustein fiele sonst erst bei der Aufnahme zum Release auf."""
    from app.core.knowledge.parts import PARTS
    from app.core.registry import REGISTRY

    parts = {spec.name for spec in PARTS.all()}
    for guide in guides.GUIDES:
        for number, one in enumerate(guide.steps, 1):
            for mark in one.marks:
                kind, _separator, name = mark.target.partition(":")
                where = f"{guide.key} Schritt {number}: {mark.target}"
                if kind == "operation":
                    assert REGISTRY.has(name), where
                if kind == "part":
                    assert name in parts, where


@pytest.mark.parametrize("language", available_languages())
def test_a_menu_path_in_a_step_is_the_one_the_menu_shows(language: str) -> None:
    """Der Weg im Satz ist der Weg im Menü, in jeder Sprache (Konzept Handbuch §6).

    Die Aufnahme beim Release prüft den Weg am Fenster; dieser Test prüft
    vorher den Satz dazu — auch den übersetzten, den kein Bild prüft.
    """
    from app.core.registry import REGISTRY
    from app.core.registry.surfaces import menu_path
    from app.i18n import set_language
    from app.i18n.catalog import install_language

    install_language(language)
    set_language(language)
    for guide in guides.GUIDES:
        for number, one in enumerate(guide.steps, 1):
            text = str(one.text)
            if "→" not in text:
                continue
            named = [
                mark.target.partition(":")[2]
                for mark in one.marks
                if mark.target.startswith("operation:")
            ]
            assert named, f"{guide.key} Schritt {number}: ein Menüweg ohne Operation"
            for name in named:
                path = menu_path(REGISTRY.get(name))
                assert path in text, f"{language}, {guide.key} Schritt {number}: {path!r}"


@pytest.mark.parametrize(
    "language", [language for language in available_languages() if language != SOURCE_LANGUAGE]
)
def test_a_name_in_a_step_is_the_one_the_interface_shows(language: str) -> None:
    """Ein hervorgehobener Name heißt in jeder Sprache wie der Text, den er meint.

    Knopf, Feld, Baustein, Anleitungstitel: *Oben öffnen* muss im Satz so
    übersetzt sein wie am Kästchen im Dialog, sonst sucht der Kunde einen
    Knopf, den es nicht gibt. Ein Name ohne Katalogeintrag ist kein Text der
    Oberfläche. Ob ein Menüweg dort steht, wo er hinzeigt, prüft der Test
    davor.
    """
    import re

    from app.i18n import set_language
    from app.i18n.catalog import install_language, read_catalog

    catalog = read_catalog(language)
    emphasis = re.compile(r"\*([^*]+)\*")
    install_language(language)
    set_language(language)
    for guide in guides.GUIDES:
        for number, one in enumerate(guide.steps, 1):
            where = f"{language}, {guide.key} Schritt {number}"
            said = emphasis.findall(str(one.text))
            for name in emphasis.findall(source_text(one.text)):
                parts = [part.strip() for part in name.split("→")]
                unknown = [part for part in parts if part not in catalog]
                assert not unknown, f"{where}: {unknown} ist kein Text der Oberfläche"
                meant = " → ".join(catalog[part] for part in parts)
                assert meant in said, f"{where}: *{meant}* fehlt, es steht {said}"


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
        manual.WHERE_TO_START,
        *(page.key for page in manual.INTRODUCTION),
        manual.SPACEMOUSE_ACCESS,
        *(guide.key for guide in guides.GUIDES),
    ]
    assert sorted(placed) == sorted(expected)


def test_the_manual_begins_where_to_start() -> None:
    """Die erste Seite ist „Wo fange ich an?" — dorthin zeigen Startbildschirm und F1."""
    first = manual.pages()[0]
    assert first.key == manual.WHERE_TO_START
    assert first.part == "start"


@pytest.mark.parametrize("language", available_languages())
def test_where_to_start_leads_to_every_guide_by_its_title(language: str) -> None:
    """Jede Anleitung steht auf der ersten Seite, verlinkt und in jeder Sprache
    unter dem Titel, unter dem sie in der Seitenliste steht (Konzept Handbuch
    §11: jede Aufgabe in höchstens zwei Klicks vom Startbildschirm)."""
    from app.core import markup
    from app.i18n import set_language
    from app.i18n.catalog import install_language

    install_language(language)
    set_language(language)
    try:
        page = manual.find(manual.WHERE_TO_START)
        assert page is not None
        links = {target: label for label, target in markup.MANUAL_LINK.findall(page.text())}
        expected = {guide.key: str(guide.title) for guide in guides.GUIDES}
    finally:
        set_language(SOURCE_LANGUAGE)
    assert links == expected, f"{language}: {links}"


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


def test_every_guide_is_named_at_the_end_of_a_page_that_explains_its_topic() -> None:
    """Wer eine Erklärseite liest, findet dort den Weg in Bildern (``Guide.topics``)."""
    written = {page.key for page in manual.INTRODUCTION}
    for guide in guides.GUIDES:
        assert guide.topics, f"{guide.key}: keine Erklärseite verweist auf die Anleitung"
        unknown = sorted(set(guide.topics) - written)
        assert not unknown, f"{guide.key}: {unknown} ist keine Erklärseite"
        for key in guide.topics:
            page = manual.find(key)
            assert page is not None, key
            assert f"](manual:{guide.key})" in str(page.body), f"{key} nennt {guide.key} nicht"


def test_the_films_follow_where_to_start_and_hold_every_guide_once() -> None:
    """Zwei Filme wie die zwei Listen auf „Wo fange ich an?“ (HB-12)."""
    from tools import make_guide_video

    films = make_guide_video.films([])
    assert [film.name for film in films] == ["start", "tasks"]
    for film in films:
        assert [guide.part for guide in film.chapters] == [film.name] * len(film.chapters)
    shown = [guide.key for film in films for guide in film.chapters]
    assert shown == [guide.key for guide in guides.GUIDES if guide.part in ("start", "tasks")]
    assert sorted(shown) == sorted(guide.key for guide in guides.GUIDES)
    single = make_guide_video.films(["drill-a-hole"])
    assert [(film.name, len(film.chapters)) for film in single] == [("drill-a-hole", 1)]


def test_a_film_stops_at_pictures_that_no_longer_fit_their_guide(tmp_path: Path) -> None:
    """Ein Film, der einen anderen Schritt zeigt, als er einblendet, entsteht nicht."""
    from tools import make_guide_video

    drill = next(guide for guide in guides.GUIDES if guide.key == "drill-a-hole")
    with pytest.raises(SystemExit, match="make_guides"):
        make_guide_video.check_pictures(tmp_path, (drill,))

    def stamp(version: str, fingerprint: str) -> None:
        entry = {"version": version, "fingerprint": fingerprint}
        (tmp_path / "guides.json").write_text(
            json.dumps({"guides": {drill.key: entry}}), encoding="utf-8"
        )

    stamp(APP_VERSION, guides.fingerprint(drill))
    make_guide_video.check_pictures(tmp_path, (drill,))
    stamp(APP_VERSION, "0" * 16)
    with pytest.raises(SystemExit, match="drill-a-hole: seit der Aufnahme geändert"):
        make_guide_video.check_pictures(tmp_path, (drill,))
    stamp("0.0.1", guides.fingerprint(drill))
    with pytest.raises(SystemExit, match=re.escape("drill-a-hole: aufgenommen mit 0.0.1")):
        make_guide_video.check_pictures(tmp_path, (drill,))


def test_a_caption_colours_the_names_and_keeps_a_link_as_its_text() -> None:
    """Im Film ist nichts anklickbar; der Name, den der Kunde sucht, steht in der
    Farbe der Markierung, der Titel eines Verweises kursiv, und nichts aus dem
    Satz wird zu HTML."""
    from tools import make_guide_video

    text = "Klicken Sie auf *Verrunden* wie in [Das erste eigene Teil](manual:first-part) <b>"
    shown = make_guide_video.caption_html(text, "#f0a54a")
    assert '<span style="color:#f0a54a; font-weight:600">Verrunden</span>' in shown
    assert "<i>Das erste eigene Teil</i>" in shown
    assert "manual:" not in shown
    assert "*" not in shown
    assert "&lt;b&gt;" in shown


def test_the_chapters_follow_what_youtube_takes() -> None:
    """Ab drei Kapiteln, das erste bei 0:00 — sonst keine Marken."""
    from tools import make_guide_video

    events = [
        {"start": 0.0, "chapter": ""},
        {"start": 7.27, "chapter": "Eins"},
        {"start": 65.5, "chapter": "Zwei"},
        {"start": 130.0, "chapter": "Drei"},
    ]
    assert make_guide_video.chapter_marks(events) == "0:00 Eins\n1:05 Zwei\n2:10 Drei\n"
    assert make_guide_video.chapter_marks(events[:3]) == ""


def test_a_picture_stands_as_long_as_its_words_need_within_bounds() -> None:
    from tools import make_guide_video

    low, high = make_guide_video.STEP_SECONDS
    assert make_guide_video.reading_seconds(0, (low, high)) == low
    assert make_guide_video.reading_seconds(200, (low, high)) == high
    assert make_guide_video.reading_seconds(12, (low, high)) < make_guide_video.reading_seconds(
        18, (low, high)
    )


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

    stateful = {
        "dialog",
        "dialog.accept",
        "dialog.naming",
        "parameters.first",
        "sketch.plane",
        "report.action",
        "history.last",
    }
    window = MainWindow(Session(), UiSettings())
    try:
        for name in sorted(guide_targets.RESOLVED - stateful):
            assert guide_targets.widget_for(window, name) is not None, name
        for name in ("tool:transform", "transform:rotate"):
            assert guide_targets.widget_for(window, name) is not None, name
        for name in ("dialog", "dialog.naming", "parameters.first", "sketch.plane"):
            with pytest.raises(guide_targets.MissingTargetError):
                guide_targets.widget_for(window, name)
        with pytest.raises(guide_targets.MissingTargetError):
            guide_targets.area_for(window, "history.last")
    finally:
        window.close()
        window.deleteLater()
