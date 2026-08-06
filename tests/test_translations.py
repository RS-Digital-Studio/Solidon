"""Jeder Oberflächentext ist übersetzbar, und die Kataloge sind
vollständig (§4.1, §37.2).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import app
from app.i18n import SOURCE_LANGUAGE, SUPPORTED_LANGUAGES, TranslatableText, set_language
from app.i18n.catalog import install_language, read_catalog
from app.i18n.extract import message_ids

PACKAGE_DIR = Path(app.__file__).parent
UI_DIR = PACKAGE_DIR / "ui"

#: Qt-Aufrufe, die einen Text vor den Nutzer bringen.
DISPLAY_CALLS = frozenset(
    {
        "setText",
        "setWindowTitle",
        "setToolTip",
        "setStatusTip",
        "setPlaceholderText",
        "addTab",
        "addItem",
        "addItems",
        "setSuffix",
        "setPrefix",
    }
)

#: Statische Meldungsfenster-Aufrufe. Nur an QMessageBox gezählt —
#: ``log.warning`` ist kein Dialog.
BOX_CALLS = frozenset({"information", "question", "warning", "critical"})

#: Widgets, die ihre Beschriftung als erstes Argument nehmen.
LABELLED_WIDGETS = frozenset(
    {"QLabel", "QPushButton", "QAction", "QGroupBox", "QCheckBox", "QToolBar", "QListWidgetItem"}
)


@pytest.mark.parametrize(
    "language", [entry for entry in SUPPORTED_LANGUAGES if entry != SOURCE_LANGUAGE]
)
def test_every_text_is_translated(language: str) -> None:
    catalog = read_catalog(language)
    ids = message_ids()

    missing = sorted(key for key in ids if not catalog.get(key))
    assert not missing, f"{language}: no translation for\n" + "\n".join(missing)

    orphaned = sorted(key for key in catalog if key not in ids)
    assert not orphaned, f"{language}: no longer used\n" + "\n".join(orphaned)


def test_the_catalog_actually_switches_the_language() -> None:
    install_language("en")
    text = TranslatableText("Abbrechen")
    assert text.translate("en") == "Cancel"
    assert text.translate("de") == "Abbrechen"

    set_language("en")
    try:
        assert str(text) == "Cancel"
    finally:
        set_language(SOURCE_LANGUAGE)


def test_qt_standard_buttons_speak_the_application_language(qt_app: object) -> None:
    """Qt beschriftet OK/Abbrechen/Schließen selbst — ohne geladenen
    qtbase-Katalog stand dort „Cancel", mitten im deutschen Programm.

    Geprüft am echten Artefakt: einer QDialogButtonBox, nicht am Katalog.
    """
    from PySide6.QtWidgets import QDialogButtonBox

    from app.ui.app import install_qt_translations

    translator = install_qt_translations(qt_app, "de")  # type: ignore[arg-type]
    assert translator is not None, "PySide6 liefert qtbase_de.qm mit — Laden darf nicht scheitern"
    try:
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
        assert cancel is not None
        assert cancel.text().replace("&", "") == "Abbrechen"
    finally:
        qt_app.removeTranslator(translator)  # type: ignore[attr-defined]


#: Ein Dateifilter für Qt: eine Beschriftung, dann die Endungen in Klammern.
FILE_FILTER = re.compile(r"^(?P<label>[^(]*)\(\s*\*\.")

#: Eine Beschriftung, die keine ist: ein Formatname wie „STL" oder „3MF".
#: Großbuchstaben, Ziffern, Punkt und Bindestrich — sonst nichts. So etwas
#: heißt in jeder Sprache gleich und braucht keine Übersetzung.
FORMAT_NAME = re.compile(r"^[A-Z0-9.\- ]*$")


class _Literals(ast.NodeVisitor):
    """Sammelt Zeichenketten, die **nicht** durch ``tr()`` oder ``_()`` gehen."""

    def __init__(self) -> None:
        self.depth = 0
        self.free: list[ast.Constant] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = ""
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        translated = name in {"tr", "_", "translate", "TranslatableText"}
        self.depth += int(translated)
        self.generic_visit(node)
        self.depth -= int(translated)

    def visit_Constant(self, node: ast.Constant) -> None:
        if not self.depth and isinstance(node.value, str):
            self.free.append(node)


@pytest.mark.parametrize("path", sorted(UI_DIR.rglob("*.py")), ids=lambda path: path.name)
def test_no_hard_wired_file_filter(path: Path) -> None:
    """AGENTS.md Regel 20 gilt auch für Dateifilter — und für Konstanten.

    ``test_no_hard_wired_text_in_the_surface`` sieht nur Argumente von
    Anzeige-Aufrufen. ``MODEL_FILTER = "Modelle (*.stl …)"`` stand daneben, auf
    Modulebene, und erschien deshalb auch in der englischen Oberfläche deutsch.
    Ein Filter ist ein Text wie jeder andere: alles vor der Klammer liest ein
    Mensch.

    Ein reiner Formatname („STL (*.stl)") bleibt draußen — er heißt überall so.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    visitor = _Literals()
    visitor.visit(tree)

    offenders = []
    for node in visitor.free:
        match = FILE_FILTER.match(node.value)
        if match is None:
            continue
        label = match.group("label").strip()
        if FORMAT_NAME.match(label):
            continue
        offenders.append(f"{path.name}:{node.lineno} {node.value!r}")

    assert not offenders, "file filter that never reaches tr():\n" + "\n".join(offenders)


def test_the_filter_check_would_catch_a_violation() -> None:
    """Ein Wächter für die Prüfung darüber: ein grüner Lauf soll etwas heißen."""
    assert FILE_FILTER.match("Modelle (*.stl *.3mf)")
    assert not FORMAT_NAME.match("Modelle")
    assert FORMAT_NAME.match("STL"), "ein Formatname bleibt draußen"
    assert FORMAT_NAME.match("3MF")
    assert FILE_FILTER.match("Bilder (*.png)")
    assert not FILE_FILTER.match("Ein Satz ohne Endung."), "kein Filter, kein Fund"


def surface_files() -> list[Path]:
    return sorted(UI_DIR.rglob("*.py"))


@pytest.mark.parametrize("path", surface_files(), ids=lambda path: path.name)
def test_no_hard_wired_text_in_the_surface(path: Path) -> None:
    """AGENTS.md rule 20: everything the user reads goes through tr()."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = ""
        owner = ""
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
            if isinstance(node.func.value, ast.Name):
                owner = node.func.value.id
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        is_box = name in BOX_CALLS and owner == "QMessageBox"
        if not is_box and name not in DISPLAY_CALLS and name not in LABELLED_WIDGETS:
            continue
        for argument in node.args:
            if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
                continue
            # Stilvorlagen und leere Zeichenketten sind keine Texte, die jemand liest.
            if argument.value.strip() and not argument.value.startswith(("#", "font", "QFrame")):
                offenders.append(f"{path.name}:{argument.lineno} {argument.value!r}")

    assert not offenders, "text that never reaches tr():\n" + "\n".join(offenders)
