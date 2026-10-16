"""Zusatzwerkzeuge des Agenten nennen ihren Ort im Fenster (FD-129).

Die Operationswerkzeuge sagen „Ort: …“ über ``menu_path``; ``add_parameter``,
``set_parameter``, ``add_fit`` und die übrigen Werkzeuge außerhalb des
Registers sagten nichts. Der Agent konnte nicht nennen, wo der Kunde einen
Parameter selbst anlegt, und Prüfpunkt 17 hielt den Punkt für nicht
zutreffend. ``EXTRA_TOOL_PLACES`` nennt den Ort mit denselben Katalogtexten
wie das Menü; ob es die Stellen gibt, prüft der Fensterteil an der gebauten
Menüleiste.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.core.agent import tools
from app.core.agent.tools import (
    EXTRA_TOOL_PLACES,
    EXTRA_TOOLS,
    extra_tool_place,
    extra_tool_rows,
    extra_tools,
)
from app.core.guides import dialog_name
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow

#: Werkzeuge ohne Zwilling im Fenster: die Rückfrage und die lesenden.
WITHOUT_A_PLACE = frozenset(
    {tools.ASK_USER, tools.READ_REPORT, tools.READ_DIGEST, tools.READ_STANDARD, tools.READ_ANALYSIS}
)

UI = Path(__file__).resolve().parent.parent / "app" / "ui"


def test_every_extra_tool_has_a_place_or_is_only_for_the_agent() -> None:
    assert set(EXTRA_TOOL_PLACES) | WITHOUT_A_PLACE == set(EXTRA_TOOLS)
    assert not set(EXTRA_TOOL_PLACES) & WITHOUT_A_PLACE


def test_the_description_names_the_place_like_an_operation_does() -> None:
    described = {entry["name"]: entry["description"] for entry in extra_tools()}
    compact = {entry["name"]: entry["description"] for entry in extra_tools(compact=True)}

    assert described[tools.ADD_PARAMETER].endswith("Ort: Bearbeiten → Parameter anlegen ….")
    assert described[tools.ADD_FIT].endswith(
        "Ort: Handlungen rechts (bei zwei gewählten Merkmalen) → Passung anlegen."
    )
    assert "Ort:" not in described[tools.ASK_USER]
    assert all("Ort:" not in text for text in compact.values()), "kompakt ohne Ort"


def test_the_checker_gets_place_path_and_rows() -> None:
    """Die Daten für Prüfpunkt 17 (``tools/function_points.py``, Paket F8)."""
    assert extra_tool_place(tools.ADD_PARAMETER) == ("menue", "Bearbeiten → Parameter anlegen …")
    assert extra_tool_place(tools.SET_PARAMETER) == (
        "leiste",
        "Parameter links → Wert in der Zeile",
    )
    assert extra_tool_place(tools.ASK_USER) is None
    assert extra_tool_rows(tools.ADD_PARAMETER) == (
        "Bearbeiten/Parameter anlegen …",
        "dialog:parameter_dialog",
    )
    assert extra_tool_rows(tools.FIND_PART) == ("Datei/Bausteinkatalog …", "dialog:part_catalog")
    assert extra_tool_rows(tools.ADD_FIT) == ()
    assert dialog_name("ParameterDialog") == "parameter_dialog"
    assert dialog_name("PartCatalog") == "part_catalog"


def test_the_named_places_outside_the_menu_bar_exist() -> None:
    """Kontexteintrag, Knopf und Dialogklassen stehen in der Oberfläche."""
    panels = (UI / "panels.py").read_text(encoding="utf-8")
    assert 'setObjectName("parameters.edit")' in panels
    assert 'tr("Passung anlegen")' in panels
    # Seit F2b ein eigenes Modul (Codestruktur, Regel 6), nicht mehr ``dialogs.py``.
    assert "class ParameterDialog(" in (UI / "parameter_dialog.py").read_text(encoding="utf-8")
    assert "class PartCatalog(" in (UI / "catalog.py").read_text(encoding="utf-8")


def test_every_menu_place_is_a_row_of_the_built_menu_bar(window: MainWindow) -> None:
    """Derselbe Text wie im Menü heißt: dieselbe Zeile in der gebauten Leiste."""
    from app.ui.guide_targets import menubar_entries

    built = {"/".join((*menus, action.text())) for _name, menus, action in menubar_entries(window)}
    wanted = {
        row
        for name, entry in EXTRA_TOOL_PLACES.items()
        if entry.place == "menue"
        for row in extra_tool_rows(name)[:1]
    }
    assert wanted, "kein Werkzeug im Menü — dann prüft der Test nichts"
    assert wanted <= built, f"nicht in der Leiste: {sorted(wanted - built)}"
