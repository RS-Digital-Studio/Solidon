"""Jeder Oberflächentext ist übersetzbar, und die Kataloge sind
vollständig (§4.1, §37.2).
"""

from __future__ import annotations

import ast
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
