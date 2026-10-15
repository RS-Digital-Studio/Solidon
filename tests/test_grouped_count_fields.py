"""Jedes Ganzzahlfeld der Oberfläche schreibt Dreiergruppen (FD-184, Zwilling von FD-124).

Der Operationsdialog zeigt „1 051 736“; Druckeinstellungen, Merkmalfenster,
Zeichnen, Teilen, Pinsel, Filamentlager und erste Einrichtung zeigten ihre
Anzahlen ohne Gruppen und lasen „2.103.472“ als Kommazahl. Der Wächter liest
den Quelltext: Ein Ganzzahlfeld entsteht über ``app.ui.grouped_spin``, nicht als
nacktes ``QSpinBox`` und nicht über ``setDecimals(0)``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.grouped_spin import GroupedIntSpin, GroupedNumberSpin, GroupedSpin

UI = Path(__file__).resolve().parent.parent / "app" / "ui"

#: Das geschützte Leerzeichen zwischen den Gruppen.
GAP = " "

#: (Datei, Attribut) → warum dieses Ganzzahlfeld keine Gruppen trägt.
UNGROUPED: dict[tuple[str, str], str] = {
    ("generate_dialog.py", "seed"): (
        "Ein Startwert ist eine Kennung zum Abschreiben, auch in die Kommandozeile; "
        "Leerzeichen darin wären dort ein Fehler."
    ),
    ("settings_dialog.py", "remote_port"): "Eine Portnummer ist eine Kennung, keine Anzahl.",
}


def _is_zero(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant) and node.value == 0 and not isinstance(node.value, bool):
        return True
    if isinstance(node, ast.IfExp):
        return _is_zero(node.body) or _is_zero(node.orelse)
    return False


def _target_of(statement: ast.AST) -> str:
    """Das Attribut, dem ein ``QSpinBox(...)`` zugewiesen wird — sonst leer."""
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
        if isinstance(target, ast.Attribute):
            return target.attr
        if isinstance(target, ast.Name):
            return target.id
    return ""


def _ungrouped_fields() -> list[tuple[str, str, int]]:
    """Jedes Ganzzahlfeld an ``grouped_spin`` vorbei: (Datei, Ziel, Zeile)."""
    found: list[tuple[str, str, int]] = []
    for path in sorted(UI.rglob("*.py")):
        if path.name == "grouped_spin.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        name = path.relative_to(UI).as_posix()
        for statement in ast.walk(tree):
            if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call):
                func = statement.value.func
                called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if called == "QSpinBox":
                    found.append((name, _target_of(statement), statement.lineno))
            if (
                isinstance(statement, ast.Call)
                and isinstance(statement.func, ast.Attribute)
                and statement.func.attr == "setDecimals"
                and statement.args
                and _is_zero(statement.args[0])
            ):
                found.append((name, "setDecimals(0)", statement.lineno))
    return found


def test_no_integer_field_is_built_without_groups() -> None:
    found = _ungrouped_fields()
    wrong = [
        f"{name}:{line} {target}" for name, target, line in found if (name, target) not in UNGROUPED
    ]
    assert not wrong, (
        "Ganzzahlfeld ohne Dreiergruppen — GroupedSpin, GroupedNumberSpin oder "
        "GroupedIntSpin aus app.ui.grouped_spin nehmen:\n" + "\n".join(wrong)
    )
    seen = {(name, target) for name, target, _line in found}
    stale = sorted(f"{name} {target}" for name, target in UNGROUPED if (name, target) not in seen)
    assert not stale, f"Ausnahme trifft kein Feld mehr — austragen: {stale}"


def test_the_guard_finds_a_bare_integer_field() -> None:
    """Gegenprobe: dieselbe Prüfung an einem gebauten Quelltext."""
    tree = ast.parse("self.count = QSpinBox(self)\nbox.setDecimals(0 if whole else 2)\n")
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert any(getattr(call.func, "attr", "") == "setDecimals" for call in calls)
    assigned = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)]
    assert _target_of(assigned[0]) == "count"
    assert _is_zero(calls[-1].args[0]) if calls[-1].args else True


@pytest.mark.parametrize("typed", ["2103472", "2 103 472", f"2{GAP}103{GAP}472", "2.103.472"])
def test_a_spin_box_count_reads_every_writing(qt_app: QApplication, typed: str) -> None:
    field = GroupedIntSpin()
    try:
        field.setRange(0, 5_000_000)
        field.setValue(1_000)
        assert field.text() == f"1{GAP}000"
        field.lineEdit().setText(typed)
        field.interpretText()
        assert field.value() == 2_103_472
        assert isinstance(field.value(), int)
        assert field.text() == f"2{GAP}103{GAP}472"
    finally:
        field.deleteLater()


def test_a_small_count_shows_no_gap(qt_app: QApplication) -> None:
    field = GroupedIntSpin()
    try:
        field.setRange(3, 64)
        field.setValue(12)
        assert field.text() == "12"
    finally:
        field.deleteLater()


@pytest.mark.parametrize("kind", [GroupedNumberSpin, GroupedSpin])
def test_a_number_count_is_whole_and_grouped(qt_app: QApplication, kind: type) -> None:
    field = kind()
    try:
        assert field.decimals() == 0
        field.setRange(0, 5_000_000)
        field.setValue(1_051_736)
        assert field.lineEdit().text() == f"1{GAP}051{GAP}736"
        field.lineEdit().setText("2.103.472")
        field.interpretText()
        assert field.value() == 2_103_472
    finally:
        field.deleteLater()


def test_every_whole_print_setting_is_grouped(qt_app: QApplication) -> None:
    """Jede Ganzzahlzeile der Druckeinstellungen baut ein ``GroupedSpin``."""
    from PySide6.QtWidgets import QWidget

    from app.core.knowledge.print_fields import FIELDS
    from app.ui.print_settings_dialog import _make_setting_editor

    whole = [field for field in FIELDS if field.kind == "int"]
    assert whole, "keine Ganzzahlzeile — dann prüft das nichts"
    host = QWidget()
    try:
        for field in whole:
            editor = _make_setting_editor(field, host, lambda *_args: None)
            assert isinstance(editor, GroupedSpin), field.path
    finally:
        host.deleteLater()
