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
from collections.abc import Iterator
from pathlib import Path
from typing import Any, get_args

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QMenu, QToolButton

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


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("feature:resize_hole", True),
        ("feature:part.move", True),
        ("feature:Resize", False),
        ("edge:fillet_edges", True),
        ("edge:fillet_edges.variable_radius", True),
        ("edge:fillet_edges.a.b", False),
        ("feature.field:resize_hole.diameter", True),
        ("feature.field:part.move.x", True),
        ("feature.field:diameter", False),
        ("measure.field:diameter", True),
        ("measure.field:hole.diameter", False),
        ("menu:menubar.datei.speichern_unter", True),
        ("menu:history.edit", True),
        ("menu:Speichern", False),
        ("menu:menubar..datei", False),
        ("finding:arrange.below_bed", True),
        ("finding:op.drill_hole.ValidationError", True),
        ("finding:op drill", False),
        ("finding.action:place_on_bed", True),
        ("finding.action:Place", False),
        ("print:layers.layer_height", True),
        ("print:Layers", False),
        ("setting:language", True),
        ("handle:move.x", True),
        ("handle:bar.section", True),
        ("tree.row:obj_1", True),
        ("tree.row:obj_1.op5.pin_1", True),
        ("tree.row:obj_1:hole_2", False),
        ("history.row:3", True),
        ("history.row:0", False),
        ("history.row:three", False),
        ("view:obj_2.hole_1", True),
        ("dialog:print_settings_dialog", True),
        ("dialog:2nd_dialog", False),
        ("dialog:PrintSettingsDialog", False),
        ("start.recent:1", True),
        ("start.recent:0", False),
        ("history:edit", True),
        ("operation:part.move", False),
        ("feature.apply", True),
        ("feature.in_view", True),
        ("feature.every", True),
        ("measure.reference", True),
        ("search", True),
        ("toolbar.search", True),
        ("progress.cancel", True),
        ("preview.banner", True),
        ("selection.rebuild", True),
        ("feature", False),
        ("feature:", False),
    ],
)
def test_every_kind_has_its_own_pattern(name: str, valid: bool) -> None:
    """Je Art ein Muster: Ein Befundcode trägt Großbuchstaben, eine Verlaufszeile
    eine Zahl ab 1, eine Kantenvariante höchstens einen Punkt."""
    assert guides.is_target(name) is valid, name


def test_every_kind_has_a_pattern_and_every_pattern_a_kind() -> None:
    assert set(guides._PATTERNS) == set(guides.TARGET_KINDS)
    assert len(guides.TARGET_KINDS) == len(set(guides.TARGET_KINDS))


@pytest.mark.parametrize(
    ("msgid", "context", "expected"),
    [
        ("Speichern unter …", None, "menubar.speichern_unter"),
        ("Öffnen …", None, "menubar.oeffnen"),
        ("Rückgängig", None, "menubar.rueckgaengig"),
        ("Größe & Maße", None, "menubar.groesse_masse"),
        ("{app} unterstützen …", None, "menubar.app_unterstuetzen"),
        ("Massiv mit Kanten", None, "menubar.massiv_mit_kanten"),
        ("Rechts", "Kamera", "menubar.kamera.rechts"),
        ("Ändern", "Menü", "menubar.menue.aendern"),
    ],
)
def test_a_menubar_name_comes_from_the_source_text(
    msgid: str, context: str | None, expected: str
) -> None:
    name = guides.menubar_name(msgid, context)
    assert name == expected
    assert guides.is_target(f"menu:{name}")


def test_a_menubar_name_needs_letters() -> None:
    with pytest.raises(ValueError, match="kein Name"):
        guides.menubar_name("…")


def test_a_part_offers_its_three_actions_under_their_fixed_keys() -> None:
    """Maße und Verschieben tragen dieselbe Operation, Entfernen keine (B9):
    unterschieden werden sie über ``FeatureAction.key``."""
    from types import SimpleNamespace

    from app.core.perceive.actions import PART_ACTION_KEYS, part_actions
    from app.core.registry import REGISTRY

    spec = REGISTRY.get("insert_screw_hole")
    actions = part_actions(SimpleNamespace(id=4, params={}), spec)
    assert [action.key for action in actions] == list(PART_ACTION_KEYS)
    assert [guides.action_target(action) for action in actions] == [
        f"feature:{key}" for key in PART_ACTION_KEYS
    ]
    moving = actions[1]
    assert guides.action_field_target(moving, "x") == "feature.field:part.move.x"
    assert all(guides.is_target(guides.action_target(action)) for action in actions)


def test_a_texture_offers_its_two_actions_under_their_fixed_keys() -> None:
    from types import SimpleNamespace

    from app.core.perceive.actions import TEXTURE_ACTION_KEYS, texture_actions
    from app.core.registry import REGISTRY

    spec = REGISTRY.get("apply_texture")
    actions = texture_actions(SimpleNamespace(id=2, params={}), spec)
    assert tuple(action.key for action in actions) == TEXTURE_ACTION_KEYS


def test_an_action_without_its_own_key_is_named_after_its_operation() -> None:
    from app.core.perceive.actions import FeatureAction

    plain = FeatureAction(title="Bohrung ändern", op="resize_hole")
    assert guides.action_key(plain) == "resize_hole"
    assert guides.action_target(plain) == "feature:resize_hole"
    assert guides.action_field_target(plain, "diameter") == "feature.field:resize_hole.diameter"
    blocked = FeatureAction(title="Merkmal drehen", op=None, key="rotate_feature", reason="nein")
    assert guides.action_target(blocked) == "feature:rotate_feature"
    nameless = FeatureAction(title="Etwas", op=None, reason="nein")
    assert guides.action_target(nameless) == ""
    assert guides.action_field_target(nameless, "x") == ""


def test_an_edge_row_is_an_edge_target_and_a_variant_carries_its_mode() -> None:
    from app.core.perceive.actions import EDGE_OPERATIONS, EDGE_VARIANT_KEYS, edge_actions
    from app.core.registry import REGISTRY

    assert EDGE_VARIANT_KEYS == ("fillet_edges.variable_radius",)
    actions = edge_actions("1 2 3 4 5 6")
    expected = [name for name, _measure in EDGE_OPERATIONS if REGISTRY.has(name)] + [
        key for key in EDGE_VARIANT_KEYS if REGISTRY.has(key.partition(".")[0])
    ]
    assert [action.key for action in actions] == expected
    for action in actions:
        target = guides.action_target(action)
        assert target == f"edge:{action.key}"
        assert guides.is_target(target), target


def test_every_action_of_a_feature_has_a_key_even_when_it_is_refused() -> None:
    """Eine gesperrte Zeile trägt die Operation, für die sie steht — sonst hätte
    sie kein Ziel, und ihr Grund ließe sich am Fenster nicht ablesen."""
    from app.core.perceive.actions import actions_for
    from app.core.types import Feature

    hole = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"diameter": 5.0, "depth": 4.0, "axis": (0.0, 0.0, 1.0), "center": (0, 0, 0)},
        face_indices=(0, 1, 2, 3),
    )
    actions = actions_for(hole)
    assert actions
    for action in actions:
        assert guides.action_key(action), action.title
        assert guides.is_target(guides.action_target(action)), action


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
    assert "part" not in guides.Guide.__dataclass_fields__
    parts = {key: part for part, keys in manual.OUTLINE for key in keys}
    assert all(manual.guide_page(guide).part == parts[guide.key] for guide in guides.GUIDES)


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
        key="two-colours",
        title="Probe",
        summary="Zwei Schritte.",
        steps=(guides.step("Erst das.", "report"), guides.step("Dann das.", "history")),
    )
    page = manual.guide_page(guide)
    body = str(page.body)

    assert page.part == "tasks"
    assert body.index("**1.** Erst das.") < body.index("![](figure:guide-two-colours-1)")
    assert body.index("![](figure:guide-two-colours-1)") < body.index("**2.** Dann das.")
    assert page.figures() == ("guide-two-colours-1", "guide-two-colours-2")


def test_a_legend_lists_what_its_numbers_stand_for() -> None:
    guide = guides.Guide(
        key="window-overview",
        title="Probe",
        summary="Eine Legende.",
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
        assert "*" + tr("Abbildung: {description}", description="") not in text, guide.key
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


@pytest.mark.parametrize("language", available_languages())
def test_spool_names_follow_the_active_catalog(language: str) -> None:
    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from tools import make_guides

    install_language(language)
    set_language(language)
    try:
        expected = (f"PLA {tr('Weiß').lower()}", f"PLA {tr('Rot').lower()}")
        assert make_guides._spool_names() == expected
    finally:
        set_language(SOURCE_LANGUAGE)


def test_the_fingerprint_follows_what_the_pictures_show() -> None:
    """Ein neuer Schritt oder ein anderes Ziel verlangt neue Bilder; ein Tippfehler im
    Satz eines anderen Schritts ändert den Abdruck auch — der Satz steht im Alt-Text."""
    base = guides.Guide("probe", "Probe", "Kurz.", (guides.step("Eins.", "report"),))
    other_target = guides.Guide("probe", "Probe", "Kurz.", (guides.step("Eins.", "tree"),))
    more = guides.Guide(
        "probe",
        "Probe",
        "Kurz.",
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
    outline = dict(manual.OUTLINE)
    guide_by_key = {guide.key: guide for guide in guides.GUIDES}
    for film in films:
        assert [guide.key for guide in film.chapters] == [
            key for key in outline[film.name] if key in guide_by_key
        ]
    shown = [guide.key for film in films for guide in film.chapters]
    assert shown == [
        key for _part, keys in manual.OUTLINE[:2] for key in keys if key in guide_by_key
    ]
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


def test_a_film_picture_is_cut_at_least_as_large_as_its_place_in_the_film() -> None:
    """Der 2K-Film verkleinert seine Bilder höchstens, er rechnet nie hoch.

    Robert, 04.10.2026: „wenn wir kleinere Bilder benötigen, davon
    herunterskalieren". Ein Ausschnitt um ein kleines Ziel ist deshalb so groß
    wie die Fläche im Film (abzüglich des Rands, den ``annotate`` anlegt),
    enthält das Ziel und bleibt im Fenster; ist das Fenster kleiner, bleibt
    es beim ganzen Fenster.
    """
    from PySide6.QtCore import QRect

    from tools import make_guide_video
    from tools.make_guides import BORDER, film_cut

    # Die Flächen im Raster mal 2560 / 1920: 1800 x 740 und 1180 x 940.
    assert make_guide_video.picture_size(False) == (2400, 987)
    assert make_guide_video.picture_size(True) == (1573, 1253)
    window = QRect(0, 0, 2560, 1369)
    for legend in (False, True):
        width, height = make_guide_video.picture_size(legend)
        for focus in (QRect(10, 10, 40, 30), QRect(1200, 600, 80, 40), QRect(2500, 1330, 50, 30)):
            cut = film_cut(focus, window, (width, height))
            assert cut.contains(focus)
            assert window.contains(cut)
            assert (cut.width(), cut.height()) == (
                min(width - 2 * BORDER, window.width()),
                min(height - 2 * BORDER, window.height()),
            )
    small = QRect(0, 0, 900, 600)
    assert film_cut(QRect(100, 100, 50, 50), small, (2400, 987)) == small
    # Ein Gezeigtes, das höher ist als das breite Filmformat im Fenster (der
    # offene Dialog in „Gehäuse mit Deckel“, Schritt 10): Der Ausschnitt fasst
    # es ganz, und der Film verkleinert ihn.
    tall = QRect(305, 62, 2070, 1216)
    cut = film_cut(tall, window, make_guide_video.picture_size(False))
    assert cut.contains(tall) and window.contains(cut)


def test_the_film_draws_a_picture_in_its_own_pixels_and_never_enlarges_it(qt_app) -> None:
    """Ein kleineres Bild steht 1:1 im Film, ein größeres wird auf die Fläche verkleinert."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage

    from tools import make_guide_video

    draw = make_guide_video._Painter()
    area = make_guide_video.STEP_PICTURE
    width, height = make_guide_video.picture_size(False)
    for size, expected in (((400, 300), (400, 300)), ((4000, 1000), (width, round(width / 4)))):
        picture = QImage(*size, QImage.Format.Format_RGB32)
        picture.fill(QColor("#ff0000"))
        image, painter = draw.canvas()
        try:
            draw.picture(painter, picture, area)
        finally:
            painter.end()
        assert (image.width(), image.height()) == (make_guide_video.WIDTH, make_guide_video.HEIGHT)
        red = [
            (x, y)
            for y in range(0, image.height(), 2)
            for x in range(0, image.width(), 2)
            if image.pixelColor(x, y) == QColor("#ff0000")
        ]
        columns = max(x for x, _ in red) - min(x for x, _ in red) + 2
        rows = max(y for _, y in red) - min(y for _, y in red) + 2
        assert abs(columns - expected[0]) <= 2 and abs(rows - expected[1]) <= 2, (
            size,
            columns,
            rows,
        )
        assert QRectF(
            area.left() * make_guide_video.SCALE,
            area.top() * make_guide_video.SCALE,
            width,
            height,
        ).contains(QRectF(min(x for x, _ in red), min(y for _, y in red), columns - 2, rows - 2))


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
    hier geht es um die, die immer da sind. Die Ziele im Druckdialog gehören
    zu den ersten: Er läuft modal über ``exec()`` und ist am frischen Fenster
    nicht offen (am 28.09.2026 war der Test deshalb im Release-Probelauf rot).
    """
    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    printing = set(guide_targets._PRINT)
    stateful = {
        "dialog",
        "dialog.accept",
        "dialog.naming",
        "dialog.more",
        "parameters.first",
        "report.action",
        "history.last",
        # Das Merkmalfenster und die Maßgruppe stehen erst an einer Auswahl
        "feature.apply",
        "feature.in_view",
        "feature.every",
        "measure.reference",
        *printing,
    }
    window = MainWindow(Session(), UiSettings())
    try:
        for name in sorted(guide_targets.RESOLVED - stateful):
            assert guide_targets.widget_for(window, name) is not None, name
        for name in ("tool:transform", "transform:rotate"):
            assert guide_targets.widget_for(window, name) is not None, name
        for name in (
            "dialog",
            "dialog.naming",
            "dialog.more",
            "parameters.first",
            *printing,
        ):
            with pytest.raises(guide_targets.MissingTargetError):
                guide_targets.widget_for(window, name)
        with pytest.raises(guide_targets.MissingTargetError):
            guide_targets.area_for(window, "history.last")
    finally:
        window.close()
        window.deleteLater()


@pytest.mark.parametrize("away", [False, True])
def test_step_number_never_covers_text_even_in_a_full_dialog(away):
    """Ein völlig belegter Dialog zwingt die Nummer in den freien Bildrand."""
    from PySide6.QtCore import QRectF

    from tools.make_guides import BADGE, BORDER, _badge_centre

    text = QRectF(BORDER, BORDER, 500, 320)
    bounds = QRectF(0, 0, 500 + 2 * BORDER, 320 + 2 * BORDER)
    frame = QRectF(220, 160, 80, 28)
    taken = []
    for _ in range(8):
        point = _badge_centre(frame, [], bounds, taken, away=away, protected=[text])
        disc = QRectF(
            point.x() - BADGE - 3, point.y() - BADGE - 3, 2 * (BADGE + 3), 2 * (BADGE + 3)
        )
        assert bounds.contains(disc)
        assert not text.intersects(disc)
        assert all(
            abs(point.x() - old.x()) > 2 * BADGE + 4 or abs(point.y() - old.y()) > 2 * BADGE + 4
            for old in taken
        )
        taken.append(point)


def test_capture_protects_visible_dialog_text_and_item_views(qt_app):
    """Die Aufnahme übernimmt auch Text aus einem offenen Auswahldialog."""
    from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QVBoxLayout, QWidget

    from tools.make_guides import _text_areas

    window = QWidget()
    window.resize(600, 400)
    dialog = QDialog(window)
    layout = QVBoxLayout(dialog)
    label = QLabel("Text vor der Auswahl", dialog)
    listing = QListWidget(dialog)
    listing.addItem("Baustein mit einer langen Beschreibung")
    layout.addWidget(label)
    layout.addWidget(listing)
    window.show()
    dialog.show()
    qt_app.processEvents()
    try:
        from PySide6.QtCore import QPoint, QRect

        areas = _text_areas(window)
        origin = window.mapToGlobal(QPoint())
        assert QRect(label.mapToGlobal(QPoint()) - origin, label.size()) in areas
        assert QRect(listing.mapToGlobal(QPoint()) - origin, listing.size()) in areas
        dialog.hide()
        assert not _text_areas(window)
    finally:
        dialog.close()
        window.close()


def test_a_title_from_the_register_names_its_menu_line_by_its_source() -> None:
    """Ein übersetzbarer Titel gibt Quelle und Kontext, ein schlichter steht für sich."""
    from app.i18n import _

    assert guides.menubar_name_of(_("Rechts", context="Kamera")) == "menubar.kamera.rechts"
    assert guides.menubar_name_of(_("Öffnen …")) == "menubar.oeffnen"
    assert guides.menubar_name_of("Mein Haken") == "menubar.mein_haken"


# --- Wortschatz des Funktionsdurchgangs (RM-737) ------------------------------

#: Die Arten, die der Funktionsdurchgang dazugebracht hat; die alten neun prüfen
#: die Bildanleitungen beim Release.
NEW_KINDS = frozenset(guides.TARGET_KINDS) - {
    "command",
    "operation",
    "field",
    "part",
    "tool",
    "transform",
    "section",
    "sketch",
    "history",
}


def test_every_kind_of_the_vocabulary_has_its_resolution_in_the_interface() -> None:
    """Eine Art im Kern, die die Oberfläche nicht kennt, scheiterte erst am Prüfstand."""
    from app.ui import guide_targets

    assert frozenset(guides.TARGET_KINDS) == guide_targets.RESOLVED_KINDS


@pytest.mark.parametrize(
    ("class_name", "expected"),
    [
        ("PrintSettingsDialog", "print_settings_dialog"),
        ("SettingsDialog", "settings_dialog"),
        ("LLMKeyDialog", "llm_key_dialog"),
        ("MainWindow", "main_window"),
        ("PartCatalog", "part_catalog"),
    ],
)
def test_a_dialog_is_named_after_its_class(class_name: str, expected: str) -> None:
    assert guides.dialog_name(class_name) == expected
    assert guides.is_target(f"dialog:{expected}")


#: Die Auflöser, die mit dem Funktionsdurchgang entstanden sind. Sie greifen
#: auf kein privates Attribut zu: Was sie brauchen, trägt die Oberfläche als
#: Kennzeichen oder unter einem öffentlichen Namen (Abnahme D0-W).
NEW_RESOLVERS = (
    "marked_widgets",
    "_marked",
    "_rebuild_button",
    "_search_field",
    "_toolbar_search",
    "_progress_cancel",
    "_preview_banner",
    "_obstacles",
    "_Obstacle",
    "_reveal",
    "_tab_of_a_page_behind",
    "menu_entries",
    "menubar_entries",
    "_menu_name",
    "_bar",
    "_dialog_of_class",
    "_object_and_feature",
    "_spot",
    "_row",
    "_item_rect",
    "_item_area",
    "point_of_world",
    "_shows_the_view",
    "point_for",
    "_grip_point",
    "widget_under",
    "zone_of",
    "search_hits",
    "_hit_row",
    "next_click",
    "_obstacle_click",
    "_widget_click",
    "_scroll_needed",
    "_row_click",
    "_visible_row_click",
    "_expander_click",
    "_tile_click",
    "_command_click",
    "_actions_below",
    "_in_the_bar",
    "_chain_click",
    "_open_menus",
    "_menu_action_named",
    "_menubar_chain",
    "_menu_click",
)


def private_reads(source: str, names: tuple[str, ...]) -> list[str]:
    """Jeder Zugriff ``x._name`` in den genannten Funktionen und Klassen."""
    import ast

    tree = ast.parse(source)
    found: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.ClassDef) or node.name not in names:
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Attribute)
                and inner.attr.startswith("_")
                and not inner.attr.startswith("__")
            ):
                found.append(f"{node.name}: {ast.unparse(inner)}")
    return found


def test_the_new_resolvers_read_no_private_attribute() -> None:
    import inspect

    from app.ui import guide_targets

    source = inspect.getsource(guide_targets)
    defined = {name for name in NEW_RESOLVERS if hasattr(guide_targets, name)}
    assert defined == set(NEW_RESOLVERS), sorted(set(NEW_RESOLVERS) - defined)
    assert private_reads(source, NEW_RESOLVERS) == []


def test_a_private_read_in_a_resolver_turns_the_guard_red() -> None:
    """Gegenprobe: ``window.feature_panel._apply`` wäre ein Zugriff am Kennzeichen vorbei."""
    source = "def next_click(window, name):\n    return window.feature_panel._apply\n"
    assert private_reads(source, ("next_click",)) == ["next_click: window.feature_panel._apply"]


@pytest.fixture
def prepared_window(qt_app: Any) -> Iterator[Any]:
    """Ein Fenster mit einem Quader samt Bohrung, unter das Bett geschoben.

    Die Attrappe des Renderers gibt der Ansicht eine Projektion; offscreen gibt
    es sonst keine, und die Maßgruppe im Bild bliebe aus.
    """
    from app.core.scene.history import OperationDraft
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from tests.render_fakes import RecordingRenderer

    window = MainWindow(Session(), UiSettings())
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.resize(1400, 900)
    window.show()
    window._show_start_screen(False)
    assert window.session.apply(
        "Quader mit Bohrung",
        [
            OperationDraft(op="create_box"),
            OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 12.0}),
            OperationDraft(
                op="translate_object", inputs=("obj_1",), params={"dx": 0.0, "dy": 0.0, "dz": -15.0}
            ),
        ],
    )
    assert window.session.wait_for_idle(60_000)
    window.report.show_result(window.session.last_result, window.session.project.document)
    _settle(qt_app)
    try:
        yield window
    finally:
        for menu in [*window.findChildren(QMenu), *qt_app.topLevelWidgets()]:
            if isinstance(menu, QMenu) and menu.isVisible():
                menu.hide()
        window.hide()
        window.release()
        window.viewport.renderer = None


def _settle(qt_app: Any, rounds: int = 20) -> None:
    for _ in range(rounds):
        qt_app.processEvents()


def _follow(qt_app: Any, window: Any, name: str) -> str:
    """Den Weg zu ``name`` gehen wie der Kunde: Reiter, Klappe, Aufklappen per Klick
    auf das Rechteck aus ``next_click``, bis das Ziel dasteht."""
    from PySide6.QtTest import QTest

    from app.ui import guide_targets

    for _step in range(6):
        step = guide_targets.next_click(window, name)
        if step.why not in {"reiter", "klappe", "aufklappen"}:
            return str(step.why)
        centre = step.rect.center()
        under = guide_targets.widget_under(centre)
        assert under is not None, (name, step)
        QTest.mouseClick(under, Qt.MouseButton.LeftButton, pos=under.mapFromGlobal(centre))
        _settle(qt_app)
    raise AssertionError(f"{name}: kein Ziel nach sechs Klicks")


def _popup(qt_app: Any, menu: Any) -> None:
    menu.popup(QPoint(40, 40))
    _settle(qt_app, 5)
    assert menu.isVisible()


def test_every_menu_line_carries_a_unique_name_from_its_source(qt_app: Any) -> None:
    """Jede Zeile und jedes Menü der Leiste trägt einen gültigen, eindeutigen Namen;
    eine Zeile in zwei Menüs ist **eine** Aktion mit einem Namen."""
    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        entries = guide_targets.menubar_entries(window)
        assert len(entries) > 60
        by_action: dict[int, str] = {}
        for name, _menus, action in entries:
            assert name.startswith("menubar."), (name, action.text())
            assert guides.is_target(f"menu:{name}"), name
            by_action[id(action)] = name
        names = list(by_action.values())
        assert len(names) == len(set(names)), sorted(
            name for name in names if names.count(name) > 1
        )
        menus = {
            menu.objectName()
            for menu in window.findChildren(QMenu)
            if menu.objectName().startswith("menubar.")
        }
        assert len(menus) >= 8
        assert not menus & set(names)
        assert not [key for key in window.window_commands() if key.startswith("menu.")]
    finally:
        window.deleteLater()


def test_the_command_keys_do_not_follow_the_position_of_a_line(qt_app: Any) -> None:
    """Eine neue Zeile oben im Menü ändert keine Kennung darunter (Prüfbericht S1)."""
    from PySide6.QtGui import QAction

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        before = {
            key: title
            for key, (title, _keys, _slot) in window.window_commands().items()
            if key.startswith("menubar.")
        }
        file_menu = next(
            menu for menu in window.findChildren(QMenu) if menu.objectName() == "menubar.datei"
        )
        probe = QAction("Probe", window)
        probe.setObjectName("menubar.probe")
        file_menu.insertAction(file_menu.actions()[0], probe)
        after = {
            key: title
            for key, (title, _keys, _slot) in window.window_commands().items()
            if key.startswith("menubar.")
        }
        assert set(after) == set(before) | {"menubar.probe"}
        assert {key: after[key] for key in before} == before
    finally:
        window.deleteLater()


def test_every_context_action_carries_a_name(
    prepared_window: Any, qt_app: Any, monkeypatch
) -> None:
    """Baum, Verlauf, Prüfbericht und Parameterleiste: Jede Zeile eines Kontextmenüs
    trägt einen ``objectName``, unter dem ``menu:`` sie findet."""
    window = prepared_window

    def names(menu: Any) -> list[str]:
        found: list[str] = []
        for action in menu.actions():
            if action.isSeparator():
                continue
            found.append(action.objectName())
            if action.menu() is not None:
                found.extend(names(action.menu()))
        return found

    window.object_tree.select_object("obj_1")
    _settle(qt_app)
    on_body = names(window.object_tree.context_menu())
    window.object_tree.select_feature("obj_1", "hole_1")
    _settle(qt_app)
    on_feature = names(window.object_tree.context_menu())
    listing = window.history_panel.list
    on_step = names(window.history_panel.context_menu(listing.item(listing.count() - 1)))
    monkeypatch.setattr(window.parameters, "parameter_at", lambda _position: "breite")
    on_parameter = names(window.parameters.context_menu(QPoint(0, 0)))
    shown: list[list[str]] = []

    class ShownMenu(QMenu):
        """Hält fest, was das Menü zeigen würde, statt modal zu warten."""

        def exec(self, *_args: Any) -> None:  # type: ignore[override]
            shown.append(names(self))

    from app.ui import panels

    monkeypatch.setattr(panels, "QMenu", ShownMenu)
    window.right.setCurrentIndex(1)
    _settle(qt_app)
    report = window.report.list
    row = next(
        number
        for number in range(report.count())
        if getattr(report.item(number).data(Qt.ItemDataRole.UserRole), "code", "")
        == "arrange.below_bed"
    )
    window.report._on_menu(report.visualItemRect(report.item(row)).center())

    assert "tree.visibility" in on_body and "delete_object" in on_body
    assert "tree.step" in on_feature
    assert {"history.edit", "history.switch", "history.delete"} <= set(on_step)
    assert on_parameter == ["parameters.edit"]
    assert shown and "report.place_on_bed" in shown[0]
    for found in (on_body, on_feature, on_step, on_parameter, *shown):
        assert all(found), found
        assert all(guides.is_target(f"menu:{name}") for name in found), found


def test_every_new_kind_resolves_on_a_prepared_window(prepared_window: Any, qt_app: Any) -> None:
    """Jede Art aus dem Wortschatz des Funktionsdurchgangs findet ihr Ziel am Fenster."""
    from app.core.perceive.actions import edge_actions
    from app.ui import guide_targets
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.settings_dialog import SettingsDialog

    window = prepared_window
    seen: set[str] = set()

    def widget(name: str) -> Any:
        found = guide_targets.widget_for(window, name)
        assert found is not None, name
        seen.add(name.partition(":")[0])
        return found

    def click(name: str) -> Any:
        found = guide_targets.next_click(window, name)
        seen.add(name.partition(":")[0])
        return found

    # Baum, Verlauf, Prüfbericht
    assert click("tree.row:obj_1").why == "ziel"
    assert click("tree.row:obj_1.hole_1").why in {"aufklappen", "ziel"}
    # Drei Schritte in einer Transaktion: Schritt 1 steht in der zugeklappten
    # Gruppe, der Klick auf ihre Zeile klappt sie auf.
    from PySide6.QtTest import QTest

    step = click("history.row:1")
    assert step.why == "aufklappen"
    surface = window.history_panel.list.viewport()
    QTest.mouseClick(
        surface, Qt.MouseButton.LeftButton, pos=surface.mapFromGlobal(step.rect.center())
    )
    _settle(qt_app)
    assert click("history.row:1").why == "ziel"
    with pytest.raises(guide_targets.MissingTargetError):
        guide_targets.next_click(window, "history.row:99")
    assert _follow(qt_app, window, "finding:arrange.below_bed") == "ziel"
    seen.add("finding")
    report = window.report.list
    for number in range(report.count()):
        if getattr(report.item(number).data(Qt.ItemDataRole.UserRole), "code", "") == (
            "arrange.below_bed"
        ):
            report.setCurrentRow(number)
    _settle(qt_app)
    assert widget("finding.action:place_on_bed").isVisible()

    # Merkmalfenster und Maßgruppe an der Bohrung
    window.object_tree.select_object("obj_1")
    window.object_tree.select_feature("obj_1", "hole_1")
    _settle(qt_app, 40)
    assert widget("feature:resize_hole") is not None
    assert widget("feature.field:resize_hole.diameter") is not None
    assert widget("measure.field:diameter").isVisible()
    assert widget("measure.reference") is not None
    for name in ("feature.apply", "feature.in_view", "feature.every"):
        assert guide_targets.widget_for(window, name) is not None, name

    # Kante
    key = "1 2 3 4 5 6"
    window.feature_panel.show_edge(key, "Kante")
    _settle(qt_app)
    for action in edge_actions(key):
        assert widget(guides.action_target(action)) is not None
    if not edge_actions(key):
        seen.add("edge")

    # Menüleiste, und der Name der Anleitungen für das Verlaufsmenü
    assert click("menu:menubar.speichern_unter").why == "menue"
    listing = window.history_panel.list
    history_menu = window.history_panel.context_menu(listing.item(listing.count() - 1))
    _popup(qt_app, history_menu)
    assert click("history:edit") == guide_targets.Click(
        guide_targets.next_click(window, "menu:history.edit").rect,
        Qt.MouseButton.LeftButton,
        "ziel",
        "history:edit",
    )
    history_menu.hide()

    # Leisten, Suche, Fortschritt, Vorschauband, Nachbauen
    window.tools.toggle("section")
    _settle(qt_app)
    assert widget("handle:bar.section").isVisible()
    window.tools.toggle("section")
    for name in (
        "search",
        "toolbar.search",
        "progress.cancel",
        "preview.banner",
        "selection.rebuild",
    ):
        assert guide_targets.widget_for(window, name) is not None, name

    # Druckdialog und Einstellungen, offen neben dem Fenster
    printing = PrintSettingsDialog(window.session, window.settings, window)
    printing.show()
    _settle(qt_app)
    settings = SettingsDialog(window.settings, window)
    settings.show()
    _settle(qt_app)
    try:
        assert widget("print:layers.layer_height") is not None
        assert click("print:layers.layer_height").why in {"ziel", "reiter", "klappe", "rollen"}
        assert widget("setting:language") is not None
        assert widget("dialog:settings_dialog") is settings
        assert widget("dialog:print_settings_dialog") is printing
    finally:
        settings.close()
        printing.close()

    # Stelle im Bild und Griffe brauchen Projektion und Pick; sie prüfen die
    # zwei Fälle darunter an der Attrappe und der native Fall am echten Bild.
    # „Zuletzt geöffnet“ steht auf dem Startbildschirm: eigener Fall darunter.
    seen.update({"view", "start.recent"})
    assert seen >= NEW_KINDS, sorted(NEW_KINDS - seen)


def test_every_widget_has_its_zone(prepared_window: Any, qt_app: Any) -> None:
    """Wo ein Bedienelement steht, in den Zonen des Kriteriums E4."""
    from app.ui import guide_targets
    from app.ui.settings_dialog import SettingsDialog

    window = prepared_window
    host = window.overlay
    assert guide_targets.zone_of(window, window.viewport) == "ansicht"
    assert guide_targets.zone_of(window, window.statusBar()) == "statusleiste"
    assert guide_targets.zone_of(window, window.toolbar) == "kopf"
    assert guide_targets.zone_of(window, window.menuBar()) == "menue"
    if host.right is not None:
        assert guide_targets.zone_of(window, host.right) == "karte_rechts"
    if host.left is not None:
        assert guide_targets.zone_of(window, host.left) == "karte_links"
    menu = QMenu(window)
    assert guide_targets.zone_of(window, menu) == "menue"
    dialog = SettingsDialog(window.settings, window)
    try:
        assert guide_targets.zone_of(window, dialog.language) == "dialog"
    finally:
        dialog.deleteLater()
        menu.deleteLater()


def test_next_click_names_each_step_in_order_and_reveals_nothing(
    prepared_window: Any, qt_app: Any
) -> None:
    """Reiter, Klappe, Menütitel, Untermenü, Aufklappen und Rollen — und nach
    jeder Frage steht das Fenster wie vorher: ``next_click`` deckt nicht auf."""
    from app.ui import guide_targets

    window = prepared_window
    tabs = window.right

    def state() -> tuple[Any, ...]:
        tree = window.object_tree.tree
        return (
            tabs.currentIndex(),
            tuple(
                heading.isChecked()
                for heading in window.findChildren(QToolButton, "sectionHeading")
            ),
            tuple(tree.topLevelItem(row).isExpanded() for row in range(tree.topLevelItemCount())),
            tuple(menu.isVisible() for menu in window.findChildren(QMenu)),
            window.selection_operations.hits.verticalScrollBar().value(),
        )

    def ask(name: str) -> Any:
        before = state()
        found = guide_targets.next_click(window, name)
        assert state() == before, f"{name}: next_click hat aufgedeckt"
        return found

    # Reiter: Die Suche steht auf der Seite *Auswahl*.
    tabs.setCurrentIndex(1)
    _settle(qt_app)
    step = ask("search")
    assert step.why == "reiter"
    bar = tabs.tabBar()
    assert step.rect == QRect(bar.mapToGlobal(bar.tabRect(0).topLeft()), bar.tabRect(0).size())
    tabs.setCurrentIndex(0)
    _settle(qt_app)
    assert ask("search").why == "ziel"

    # Klappe: der Abschnitt *Objekte* links, zugeklappt
    tree = window.object_tree.tree
    heading = next(
        candidate
        for candidate in window.findChildren(QToolButton, "sectionHeading")
        if candidate.parentWidget() is window.object_tree.parentWidget()
    )
    heading.setChecked(False)
    _settle(qt_app)
    step = ask("tree.row:obj_1")
    assert step.why == "klappe"
    assert step.rect == QRect(heading.mapToGlobal(QPoint(0, 0)), heading.size())
    heading.setChecked(True)
    _settle(qt_app)

    # Aufklappen: eine Merkmalszeile unter einem zugeklappten Körper
    body = tree.topLevelItem(0)
    body.setExpanded(False)
    _settle(qt_app)
    assert ask("tree.row:obj_1.hole_1").why == "aufklappen"
    body.setExpanded(True)
    _settle(qt_app)
    assert ask("tree.row:obj_1.hole_1").why == "ziel"

    # Menütitel, Untermenü, Zeile
    assert ask("menu:menubar.vorne").why == "menue"
    view_menu = next(
        menu for menu in window.findChildren(QMenu) if menu.objectName() == "menubar.ansicht"
    )
    _popup(qt_app, view_menu)
    assert ask("menu:menubar.vorne").why == "untermenue"
    camera = next(
        menu for menu in window.findChildren(QMenu) if menu.objectName() == "menubar.kamera"
    )
    _popup(qt_app, camera)
    assert ask("menu:menubar.vorne").why == "ziel"
    camera.hide()
    view_menu.hide()

    # Rollen: der letzte Treffer einer langen Trefferliste
    window.selection_operations.search.setText("e")
    _settle(qt_app)
    hits = guide_targets.search_hits(window)
    assert len(hits) > 20
    step = ask(hits[-1])
    assert (step.why, step.direction, step.button) == ("rollen", 1, Qt.MouseButton.NoButton)
    assert ask(hits[0]).why == "ziel"
    window.selection_operations.search.setText("")


def test_an_operation_without_a_menu_line_resolves_over_its_button(
    prepared_window: Any, qt_app: Any, monkeypatch
) -> None:
    """Erst der Knopf, dann die Menüzeile (RM-737, B3) — vorher scheiterte eine
    Operation ohne Menüzeile, bevor nach ihrem Knopf gefragt war."""
    from app.ui import guide_targets

    window = prepared_window
    window.right.setCurrentIndex(0)
    window.object_tree.select_object("obj_1")
    _settle(qt_app)
    shown = [
        name
        for name in ("hollow_object", "orient_for_print", "split_pinned", "delete_object")
        if (button := window.selection_operations.button_for(name)) is not None
        and button.isVisible()
    ]
    assert shown, "an einem gewählten Körper steht keiner der Knöpfe"
    name = shown[0]
    monkeypatch.delitem(window._op_actions, name, raising=False)
    button = window.selection_operations.button_for(name)
    assert guide_targets.area_for(window, f"operation:{name}") == QRect(
        button.mapToGlobal(QPoint(0, 0)), button.size()
    )
    assert guide_targets.next_click(window, f"operation:{name}").why == "ziel"


def test_point_for_takes_a_facing_triangle_the_pick_confirms(
    prepared_window: Any, monkeypatch
) -> None:
    """Eine Stelle auf den Dreiecken des Merkmals, die der Pick bestätigt — nie die Achse.

    Die Attrappe projiziert x und y; der Pick ist hier nachgestellt und nimmt
    nur Dreiecke der Bohrung an. Ob ein Klick am echten Fenster das Merkmal
    wählt, prüft der native Fall darunter.
    """
    import numpy as np

    from app.core.geom.mesh import as_mesh_data
    from app.ui import guide_targets

    window = prepared_window
    viewport = window.viewport
    entry = window.session.last_result.scene.objects["obj_1"]
    hole = entry.features["hole_1"]
    raw = as_mesh_data(entry.mesh).raw
    wanted = {int(face) for face in hole.face_indices}
    centres = {index: viewport.display_of(tuple(raw.triangles_center[index])) for index in wanted}

    def picked(x: int, y: int) -> Any:
        for index, spot in centres.items():
            if spot is not None and abs(spot[0] - x) <= 1 and abs(spot[1] - y) <= 1:
                return ("obj_1", (0.0, 0.0, 0.0), index, None)
        return None

    monkeypatch.setattr(viewport, "placement_hit", picked)
    monkeypatch.setattr(guide_targets, "_shows_the_view", lambda _window, _point: True)
    point = guide_targets.point_for(window, "obj_1", "hole_1")
    facing = [
        index
        for index in wanted
        if float(raw.face_normals[index] @ np.asarray(viewport.view_direction())) < 0.0
    ]
    expected = {
        (
            viewport.mapToGlobal(QPoint(round(centres[index][0]), round(centres[index][1]))).x(),
            viewport.mapToGlobal(QPoint(round(centres[index][0]), round(centres[index][1]))).y(),
        )
        for index in facing
    }
    assert (point.x(), point.y()) in expected
    monkeypatch.setattr(viewport, "placement_hit", lambda _x, _y: None)
    with pytest.raises(guide_targets.MissingTargetError, match="keine zugewandte Stelle"):
        guide_targets.point_for(window, "obj_1", "hole_1")


def test_a_grip_is_found_by_the_name_the_renderer_gives_it(
    prepared_window: Any, monkeypatch
) -> None:
    """``handle:move.x`` ist die Stelle, an der der Pick den Pfeil der x-Achse meldet."""
    from types import SimpleNamespace

    from app.ui import guide_targets

    window = prepared_window
    viewport = window.viewport
    renderer = viewport.renderer
    monkeypatch.setattr(viewport, "gizmo_reach", lambda: ((0.0, 0.0, 0.0), 20.0))
    tip = viewport.display_of((8.0, 0.0, 0.0))
    arrow = SimpleNamespace(name="gizmo:arrow:0")
    monkeypatch.setattr(
        renderer,
        "pick_item",
        lambda x, y: arrow if abs(x - tip[0]) <= 6 and abs(y - tip[1]) <= 3 else None,
    )
    monkeypatch.setattr(guide_targets, "_shows_the_view", lambda _window, _point: True)
    found = guide_targets.next_click(window, "handle:move.x")
    centre = found.rect.center()
    local = viewport.mapFromGlobal(centre)
    assert abs(local.x() - tip[0]) <= 6 and abs(local.y() - tip[1]) <= 3
    with pytest.raises(guide_targets.MissingTargetError):
        guide_targets.next_click(window, "handle:rotate.z")


def test_widget_under_finds_the_child_and_an_open_menu_first(qt_app: Any) -> None:
    """Die Probe vor jedem Klick, offscreen belegt: das Kind an der Stelle, und ein
    offenes Menü darüber geht vor."""
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from app.ui import guide_targets

    host = QWidget()
    host.resize(300, 200)
    layout = QVBoxLayout(host)
    first = QPushButton("Eins", host)
    second = QPushButton("Zwei", host)
    layout.addWidget(first)
    layout.addWidget(second)
    host.show()
    _settle(qt_app, 5)
    try:
        point = second.mapToGlobal(second.rect().center())
        assert guide_targets.widget_under(point) is second
        menu = QMenu(host)
        menu.addAction("Probe")
        menu.popup(point)
        _settle(qt_app, 5)
        under = guide_targets.widget_under(menu.mapToGlobal(menu.rect().center()))
        assert under is menu or (under is not None and menu.isAncestorOf(under))
        menu.hide()
    finally:
        host.close()
        host.deleteLater()


@pytest.mark.usefixtures("require_graphics_adapter")
def test_a_click_at_point_for_chooses_the_feature(native_window_platform: str) -> None:
    """Am echten Fenster: Klicks an der Stelle aus ``point_for`` wählen erst den
    Körper, dann die Fläche — die Stelle trifft, was sie verspricht. Danach findet
    ``handle:move.*`` die Pfeile des Bewegungsgriffs im echten Bild."""
    import os
    import subprocess
    import sys

    script = r"""
import app.ui
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.core.bootstrap import load_operations
load_operations()
application = QApplication([])
assert application.platformName() not in ('offscreen', 'minimal')
from app.core.scene.history import OperationDraft
from app.ui import guide_targets
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
window = MainWindow(Session(), UiSettings())
window.resize(1400, 900)
window.show()
assert QTest.qWaitForWindowExposed(window)
window._show_start_screen(False)
assert window.session.apply('Quader', [OperationDraft(op='create_box')])
assert window.session.wait_for_idle(60000)
for _ in range(60):
    application.processEvents()
    QTest.qWait(20)
assert window.viewport.renderer is not None
window.viewport.reset_camera()
for _ in range(30):
    application.processEvents()
    QTest.qWait(20)
assert window.object_tree.selected_feature() != 'face_top'
clicks = 0
for click in range(2):
    if window.object_tree.selected_feature() == 'face_top':
        break
    clicks += 1
    point = guide_targets.point_for(window, 'obj_1', 'face_top')
    under = guide_targets.widget_under(point)
    QTest.mouseClick(under, Qt.MouseButton.LeftButton, pos=under.mapFromGlobal(point))
    for _ in range(30):
        application.processEvents()
        QTest.qWait(20)
assert window.object_tree.selected_feature() == 'face_top', window.object_tree.selected_feature()
window.object_tree.select_object('obj_1')
window.tools.toggle('transform')
for _ in range(30):
    application.processEvents()
    QTest.qWait(20)
for role in ('move.x', 'move.y', 'move.z'):
    step = guide_targets.next_click(window, f'handle:{role}')
    assert step.why == 'ziel', (role, step)
window.release()
print(f'point_for chose the feature after {clicks} clicks', flush=True)
import os
os._exit(0)
"""
    done = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": native_window_platform},
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "point_for chose the feature" in done.stdout, done.stdout


def test_the_recent_projects_and_the_dialog_fields_resolve(qt_app: Any, tmp_path: Path) -> None:
    """„Zuletzt geöffnet“ auf dem Startbildschirm (``start.recent:<n>`` ab 1) und die
    Felder des offenen Operationsdialogs (``field:<parameter>``) über ihr Kennzeichen."""
    from app.core.registry import REGISTRY
    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    window.resize(1200, 800)
    window.show()
    try:
        first, second = tmp_path / "eins.p3d", tmp_path / "zwei.p3d"
        window.start_screen.show_recent([first, second])
        _settle(qt_app)
        step = guide_targets.next_click(window, "start.recent:2")
        listing = window.start_screen.recent_list
        place = listing.visualItemRect(listing.item(1))
        assert step.why == "ziel"
        assert step.rect == QRect(listing.viewport().mapToGlobal(place.topLeft()), place.size())
        with pytest.raises(guide_targets.MissingTargetError):
            guide_targets.next_click(window, "start.recent:3")

        window._show_start_screen(False)
        window.run_operation(REGISTRY.get("create_box"))
        _settle(qt_app)
        editor = guide_targets.widget_for(window, "field:width")
        assert editor.property(guides.TARGET_PROPERTY) == "field:width"
        assert editor.window().isVisible()
        assert guide_targets.next_click(window, "field:width").why in {"ziel", "rollen"}
    finally:
        if window._op_dialog is not None:
            window._op_dialog.reject()
        window.hide()
        window.release()


def test_a_menu_hidden_from_the_bar_has_no_way(qt_app: Any) -> None:
    """Auf dem Startbildschirm stehen die Arbeitsmenüs nicht in der Leiste: kein
    Rechteck am Ursprung der Leiste, sondern ``MissingTargetError`` (Review M1)."""
    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    window.resize(1200, 800)
    window.show()
    _settle(qt_app)
    try:
        assert window.start_screen.isVisible()
        for name in ("menu:menubar.vorne", "menu:menubar.einpassen", "menu:menubar.ansicht"):
            with pytest.raises(guide_targets.MissingTargetError, match="nicht in der Leiste"):
                guide_targets.next_click(window, name)
        assert guide_targets.next_click(window, "menu:menubar.oeffnen").why == "menue"
    finally:
        window.hide()
        window.release()


def test_a_window_command_goes_over_its_button_in_the_card(
    prepared_window: Any, qt_app: Any
) -> None:
    """Ein Fensterbefehl mit Knopf in der Karte: erst der Knopf, dann das Menü (Review M4)."""
    from app.ui import guide_targets

    window = prepared_window
    window.right.setCurrentIndex(0)
    window.object_tree.select_object("obj_1")
    _settle(qt_app)
    button = window.selection_operations.button_for("edit.auto_split")
    assert button is not None and button.isVisible(), "Automatisch teilen steht nicht da"
    expected = QRect(button.mapToGlobal(QPoint(0, 0)), button.size())
    step = guide_targets.next_click(window, "command:edit.auto_split")
    assert (step.why, step.rect) == ("ziel", expected)
    assert guide_targets.area_for(window, "command:edit.auto_split") == expected


def test_an_operation_that_does_not_apply_here_says_so(prepared_window: Any, qt_app: Any) -> None:
    """Ohne Knopf und ohne Menüzeile nennt die Meldung den Grund, nicht ein
    geschlossenes Kontextmenü (Review L4)."""
    from app.ui import guide_targets

    window = prepared_window
    window.right.setCurrentIndex(0)
    window.object_tree.select_object(None)
    _settle(qt_app)
    button = window.selection_operations.button_for("hollow_object")
    assert button is None or not button.isVisible()
    with pytest.raises(guide_targets.MissingTargetError, match="gilt an dieser Auswahl nicht"):
        guide_targets.next_click(window, "operation:hollow_object")


def test_a_closed_submenu_of_an_open_context_menu_is_a_step(
    prepared_window: Any, qt_app: Any
) -> None:
    """*Verschieben vor* im offenen Verlaufsmenü: erst das Untermenü, dann die Zeile
    (Review L5)."""
    from app.core.scene.history import OperationDraft
    from app.ui import guide_targets

    window = prepared_window
    assert window.session.apply("Zweiter Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(60_000)
    _settle(qt_app)
    listing = window.history_panel.list
    menu = window.history_panel.context_menu(listing.item(listing.count() - 1))
    further = next(
        action for action in menu.actions() if action.objectName() == "history.move_before"
    )
    entry = further.menu().actions()[0].objectName()
    assert entry.startswith("history.move_before.")
    _popup(qt_app, menu)
    try:
        step = guide_targets.next_click(window, f"menu:{entry}")
        place = menu.actionGeometry(further)
        assert (step.why, step.rect) == (
            "untermenue",
            QRect(menu.mapToGlobal(place.topLeft()), place.size()),
        )
    finally:
        menu.hide()


def test_a_command_of_a_tool_keeps_its_own_name(prepared_window: Any) -> None:
    """``command:tool.section`` antwortet unter seinem eigenen Namen (Review L10)."""
    from app.ui import guide_targets

    step = guide_targets.next_click(prepared_window, "command:tool.section")
    assert step.target == "command:tool.section"
