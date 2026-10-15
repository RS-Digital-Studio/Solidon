"""Die Primärbetonung ist eine belegte Rolle der Grundschrift, keine beliebige fünfte Stufe."""

from copy import deepcopy

import pytest

from tests.bundled_fonts import SANS, bundled_font
from tools import function_capture
from tools.function_checks import validate_protocol
from tools.function_judges import CRITERION_JUDGES
from tools.function_samples import sample_context, sample_protocol


@pytest.fixture
def styled_app(qt_app):
    """Gebündelte Sans und Serif; Schrift und Thema gibt ``conftest.py`` zurück."""
    with bundled_font(qt_app, 9, (*SANS, "DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf")):
        yield qt_app


def _font_protocol(entry):
    protocol = sample_protocol()
    protocol["fonts"] = [entry]
    return protocol


@pytest.mark.parametrize("base", [9, 18])
def test_primary_font_is_captured_and_judged_with_its_real_role(styled_app, base):
    """Die tatsächliche Anwendungsschrift, Primärbetonung und Rückgabe laufen durch den Richter."""
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from app.ui.style import apply_style, make_primary

    qt_app = styled_app
    font = QFont(qt_app.font())
    font.setPointSize(base)
    qt_app.setFont(font)
    apply_style(qt_app, "dark")
    root = QWidget()
    button = QPushButton("Übernehmen", root)
    button.setAutoDefault(False)
    QVBoxLayout(root).addWidget(button)
    root.show()
    qt_app.processEvents()
    try:
        for primary in (True, False, True, False):
            make_primary(button, leading=primary)
            qt_app.processEvents()
            (entry,) = function_capture.font_entries(root)
            assert (
                CRITERION_JUDGES["G4"]({"fonts": [entry]}, sample_context()).verdict == "erfuellt"
            )
            assert entry["primary"] is primary
            assert entry["points"] == base
            assert entry["weight"] == (600 if primary else 400)
            assert entry["family"] == entry["base_family"]
            assert not validate_protocol(_font_protocol(entry))
    finally:
        root.close()


@pytest.mark.parametrize("wrong", ["not_primary", "size", "family", "weight", "stylesheet"])
def test_primary_evidence_does_not_hide_wrong_font_values(styled_app, wrong):
    """Gleiches Halbfett ohne Rolle sowie fremde Größe/Familie bleiben Funde."""
    from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from app.ui.style import apply_style, make_primary

    qt_app = styled_app
    font = QFont(qt_app.font())
    font.setPointSize(9)
    qt_app.setFont(font)
    apply_style(qt_app, "dark")
    root = QWidget()
    button = QPushButton("Übernehmen", root)
    button.setAutoDefault(False)
    QVBoxLayout(root).addWidget(button)
    make_primary(button)
    root.show()
    qt_app.processEvents()
    try:
        (entry,) = function_capture.font_entries(root)
        assert entry["primary"] is True
        if wrong == "not_primary":
            button.setDefault(False)
            qt_app.processEvents()
            (entry,) = function_capture.font_entries(root)
            assert entry["primary"] is False and entry["weight"] == 600
        else:
            font = QFont(button.font())
            if wrong == "size":
                font.setPointSize(13)
            elif wrong == "family":
                families = {
                    QFontInfo(QFont(family)).family() for family in QFontDatabase.families()
                }
                alternatives = sorted(families - {entry["base_family"]})
                assert alternatives, (
                    "Der Gegenfall braucht eine tatsächlich andere installierte Schrift"
                )
                font.setFamily(alternatives[0])
            elif wrong == "weight":
                button.setStyleSheet("font-weight: 700;")
            else:
                button.setStyleSheet("font-size: 13px;")
            button.setFont(font)
            qt_app.processEvents()
            (entry,) = function_capture.font_entries(root)
            if wrong == "size":
                assert entry["points"] == 13
            elif wrong == "family":
                assert entry["family"] != entry["base_family"]
            elif wrong == "weight":
                assert entry["weight"] == 700
            else:
                assert entry["stylesheet"] == "font-size: 13px;"
        assert CRITERION_JUDGES["G4"]({"fonts": [entry]}, sample_context()).verdict == "fund"
    finally:
        root.close()


@pytest.mark.parametrize("value", [None, 0, 1, "true", [], {}])
def test_primary_role_requires_a_real_boolean_in_the_protocol(value):
    """Insbesondere 1 ist trotz Pythons Gleichheit kein wahrer Rollenbeleg."""
    protocol = sample_protocol()
    protocol["fonts"][0]["primary"] = value
    problems = validate_protocol(protocol)
    assert "fonts[1]: primary hat nicht den Typ bool" in problems


@pytest.mark.parametrize("key", ["family", "base_family"])
@pytest.mark.parametrize("value", [None, 1, True, [], {}])
def test_recorded_font_families_require_text(key, value):
    """Optionale Familienangaben bleiben typgeprüfte Messwerte."""
    protocol = sample_protocol()
    protocol["fonts"][0][key] = value
    assert f"fonts[1]: {key} hat nicht den Typ str" in validate_protocol(protocol)


def test_old_protocols_without_role_and_family_stay_readable():
    """Fehlende neue Angaben sind erlaubt, erfinden aber keine Primärbetonung."""
    protocol = sample_protocol()
    for entry in protocol["fonts"]:
        for key in ("primary", "family", "base_family"):
            entry.pop(key, None)
    assert not validate_protocol(protocol)
    outcome = CRITERION_JUDGES["G4"](protocol, sample_context())
    assert outcome.verdict == "erfuellt"
    entry = deepcopy(protocol["fonts"][0])
    entry.update(points=9, weight=600, base_points=9, level="")
    assert CRITERION_JUDGES["G4"]({"fonts": [entry]}, sample_context()).verdict == "fund"


@pytest.mark.parametrize("missing", ["family", "base_family", "both"])
def test_primary_font_requires_both_family_measurements(missing):
    """Eine belegte Rolle ersetzt die noch fehlende Schriftmessung nicht."""
    entry = {
        "widget": "Hauptknopf",
        "level": "",
        "stylesheet": "",
        "points": 9,
        "weight": 600,
        "base_points": 9,
        "primary": True,
        "family": "Familie",
        "base_family": "Familie",
    }
    for key in ("family", "base_family") if missing == "both" else (missing,):
        entry.pop(key)
    assert not validate_protocol(_font_protocol(entry))
    assert CRITERION_JUDGES["G4"]({"fonts": [entry]}, sample_context()).verdict == "nicht_gelaufen"


@pytest.mark.parametrize("unproven", [False, 1, "true"])
def test_a_truthy_value_does_not_grant_primary_emphasis(unproven):
    """Auch ein direkter Richteraufruf erfindet aus einem ähnlichen Wert keine Rolle."""
    entry = {
        "widget": "Knopf",
        "level": "",
        "stylesheet": "",
        "points": 9,
        "weight": 600,
        "base_points": 9,
        "primary": unproven,
        "family": "Familie",
        "base_family": "Familie",
    }
    assert CRITERION_JUDGES["G4"]({"fonts": [entry]}, sample_context()).verdict == "fund"


def test_section_font_keeps_its_existing_type_scale():
    """Der Rollenanschluss verändert die vier vorhandenen Typografiestufen nicht."""
    from app.ui.style import type_scale

    points, weight = type_scale(9)["section"]
    entry = {
        "widget": "Abschnitt",
        "level": "section",
        "stylesheet": "",
        "points": points,
        "weight": weight,
        "base_points": 9,
        "primary": False,
        "family": "Familie",
        "base_family": "Familie",
    }
    assert CRITERION_JUDGES["G4"]({"fonts": [entry]}, sample_context()).verdict == "erfuellt"
