"""Jedes Ganzzahlfeld der Oberfläche schreibt Dreiergruppen (FD-184, Zwilling von FD-124).

Der Operationsdialog zeigt „1 051 736“; Druckeinstellungen, Merkmalfenster,
Zeichnen, Teilen, Pinsel, Filamentlager und erste Einrichtung zeigten ihre
Anzahlen ohne Gruppen und lasen „2.103.472“ als Kommazahl. Ein Ganzzahlfeld
entsteht über ``app.ui.grouped_spin``.

Der Wächter hat zwei Teile. Der Quelltext darf kein ``QSpinBox`` bauen, gleich
in welcher Form, und jedes ``setDecimals`` mit einer anderen Zahl als einer
festen positiven nennt seinen Ort in :data:`COMPUTED_PLACES`. Dort steht, wie
der **wirksame** Wert an diesem Ort ermittelt wird. Geprüft wird dann der
Wert, den das Feld wirklich bekommt, nicht die Schreibweise: Die
Druckeinstellungen hatten ``setDecimals(field.decimals)``, und dreizehn
Zeilen mit null Stellen standen ohne Gruppen da (Review F2a, R2).

**Eine Kennung ist keine Menge** (R5): Dreiecksnummer, Startwert und Port
stehen ohne Gruppen, damit man sie abschreiben kann. Was eine Kennung ist,
sagt das Schema (``param(identifier=True)``) oder die Bauart
(``IdentifierSpin``, ``IdentifierIntSpin``), nie der Name eines Feldes.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import get_args

import pytest
from PySide6.QtCore import QLocale, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from app.core.units import LengthUnit, decimals_for
from app.i18n.catalog import available_languages
from app.ui.fine_length_spin import finer
from app.ui.grouped_spin import (
    GroupedIntSpin,
    GroupedNumberSpin,
    GroupedSpin,
    IdentifierIntSpin,
    IdentifierSpin,
)

UI = Path(__file__).resolve().parent.parent / "app" / "ui"

#: Das geschützte Leerzeichen zwischen den Gruppen.
GAP = " "

UNITS: tuple[LengthUnit, ...] = get_args(LengthUnit)


def _print_setting_places() -> list[int]:
    """Die Stellen jedes Druckfeldes, das nicht als Ganzzahlfeld entsteht."""
    from app.core.knowledge.print_fields import FIELDS
    from app.ui.print_settings_dialog import _make_setting_editor

    host = QWidget()
    try:
        editors = [
            _make_setting_editor(field, host, lambda *_args: None)
            for field in FIELDS
            if field.kind in ("int", "float")
        ]
        return [
            editor.decimals()  # type: ignore[attr-defined]
            for editor in editors
            if not isinstance(editor, GroupedNumberSpin)
        ]
    finally:
        host.deleteLater()


def _operation_places() -> list[int]:
    """Die Stellen jedes Kommazahlfeldes jeder Operation, in jeder Einheit."""
    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.op_dialog import _decimals_for

    bootstrap.load_operations()
    entries = [
        entry for spec in REGISTRY.all() for entry in spec.params.spec() if entry.kind == "float"
    ]
    return [_decimals_for(entry, unit) for entry in entries for unit in (None, *UNITS)]


def _parameter_places(least: int) -> Callable[[], list[int]]:
    """Die Stellen eines Parameterfeldes für jede Bedeutung, in jeder Anzeigeeinheit."""

    def places() -> list[int]:
        from app.ui import parameter_dialog
        from app.ui.labels import display_unit, set_display_unit
        from app.ui.parameter_dialog import number_places

        codes = (parameter_dialog.LENGTH_CODE, "", "deg", "%", "count")
        found: list[int] = []
        shown = display_unit()
        for unit in UNITS:
            set_display_unit(unit)
            found += [number_places(code, least) for code in codes]
        set_display_unit(shown)
        return found

    return places


#: (Datei, Ausdruck in ``setDecimals``) → die wirksamen Stellen über alles,
#: was diesen Ort erreicht. Keine darf null sein: Ein Feld ohne Nachkomma
#: entsteht über ``grouped_spin``.
COMPUTED_PLACES: dict[tuple[str, str], Callable[[], Iterable[int]]] = {
    ("labels.py", "decimals_for(self._unit)"): lambda: [decimals_for(unit) for unit in UNITS],
    ("fine_length_spin.py", "finer(decimals_for(self._unit))"): lambda: [
        finer(decimals_for(unit)) for unit in UNITS
    ],
    ("op_dialog.py", "_decimals_for(entry, self._shown)"): _operation_places,
    ("parameter_dialog.py", "number_places(code, 3)"): _parameter_places(3),
    ("recipe_dialog.py", "number_places(chosen, 2)"): _parameter_places(2),
    ("recipe_dialog.py", "number_places(self._given_code, 2)"): _parameter_places(2),
    ("print_settings_dialog.py", "field.decimals"): _print_setting_places,
}


def _called(node: ast.Call) -> str:
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")


def _assigned(tree: ast.AST) -> dict[int, str]:
    """Aufruf → Name, dem er unmittelbar zugewiesen wird, auch mit Annotation."""
    targets: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target: ast.expr = node.targets[0]
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target = node.target
        else:
            continue
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        targets[id(node.value)] = name
    return targets


def _fixed_places(node: ast.expr) -> bool:
    """Eine feste, positive Stellenzahl — die einzige, die der Quelltext selbst belegt."""
    return isinstance(node, ast.Constant) and type(node.value) is int and node.value > 0


def _findings(source: str, name: str) -> tuple[list[tuple[str, str, int]], list[tuple[str, str]]]:
    """Ganzzahlfelder an ``grouped_spin`` vorbei und berechnete Stellenzahlen einer Datei."""
    tree = ast.parse(source)
    assigned = _assigned(tree)
    bare: list[tuple[str, str, int]] = []
    computed: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
            getattr(base, "id", getattr(base, "attr", "")) == "QSpinBox" for base in node.bases
        ):
            bare.append((name, f"class {node.name}", node.lineno))
        if not isinstance(node, ast.Call):
            continue
        if _called(node) == "QSpinBox":
            bare.append((name, assigned.get(id(node), ""), node.lineno))
        if _called(node) == "setDecimals" and node.args and not _fixed_places(node.args[0]):
            computed.append((name, ast.unparse(node.args[0])))
    return bare, computed


def _scan() -> tuple[list[tuple[str, str, int]], list[tuple[str, str]]]:
    bare: list[tuple[str, str, int]] = []
    computed: list[tuple[str, str]] = []
    for path in sorted(UI.rglob("*.py")):
        if path.name == "grouped_spin.py":
            continue
        found = _findings(path.read_text(encoding="utf-8"), path.relative_to(UI).as_posix())
        bare += found[0]
        computed += found[1]
    return bare, computed


def test_no_integer_field_is_built_without_groups() -> None:
    bare, _computed = _scan()
    wrong = [f"{name}:{line} {target or 'ohne Namen'}" for name, target, line in bare]
    assert not wrong, (
        "Ganzzahlfeld an grouped_spin vorbei — GroupedSpin, GroupedNumberSpin oder "
        "GroupedIntSpin nehmen, für eine Kennung IdentifierSpin oder IdentifierIntSpin:\n"
        + "\n".join(wrong)
    )


def test_every_whole_operation_field_is_grouped_unless_it_is_an_identifier(
    qt_app: QApplication,
) -> None:
    """Jede ganze Zahl jeder Operation: Menge in Gruppen, Kennung ohne (R5).

    ``detect_region.seed_face`` stand als „1 234 567“ da, eine Dreiecksnummer,
    die man abschreibt wie einen Startwert.
    """
    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.op_dialog import ValueField

    bootstrap.load_operations()
    entries = [
        (spec.name, entry)
        for spec in REGISTRY.all()
        for entry in spec.params.spec()
        if entry.kind == "int" and not entry.internal
    ]
    identifiers = {f"{name}.{entry.name}" for name, entry in entries if entry.identifier}
    assert "detect_region.seed_face" in identifiers, identifiers
    assert len(identifiers) < len(entries) // 4, "fast alles Kennungen — dann prüft das nichts"
    wrong: list[str] = []
    for name, entry in entries:
        field = ValueField(entry)
        try:
            kind = IdentifierSpin if entry.identifier else GroupedSpin
            if type(field.spin) is not kind:
                wrong.append(f"{name}.{entry.name}: {type(field.spin).__name__}")
        finally:
            field.deleteLater()
    assert not wrong, "\n".join(wrong)


def test_no_schema_marks_anything_but_a_whole_number_as_identifier() -> None:
    from app.core import bootstrap
    from app.core.registry import REGISTRY

    bootstrap.load_operations()
    marked = [
        f"{spec.name}.{entry.name} ({entry.kind})"
        for spec in REGISTRY.all()
        for entry in spec.params.spec()
        if entry.identifier and entry.kind != "int"
    ]
    assert not marked, marked


@pytest.mark.parametrize("kind", [IdentifierSpin, IdentifierIntSpin])
def test_an_identifier_is_written_without_groups_and_read_with_them(
    qt_app: QApplication, kind: type
) -> None:
    field = kind()
    try:
        field.setRange(0, 5_000_000)
        field.setValue(1_234_567)
        assert field.lineEdit().text() == "1234567"
        field.lineEdit().setText(f"2{GAP}103{GAP}472")
        field.interpretText()
        assert field.value() == 2_103_472
        assert field.lineEdit().text() == "2103472"
    finally:
        field.deleteLater()


def test_seed_and_port_stand_without_groups_in_their_dialogs(qt_app: QApplication) -> None:
    """Startwert und Port so, wie man sie abschreibt — im Dialog, nicht nur in der Bauart.

    Die Bauart prüft der Fall davor; hier steht fest, dass *Modell erzeugen* und
    die Einstellungen sie nehmen. Als ``GroupedIntSpin`` stünden dort
    „1 234 567“ und „8 765“ (Review 2 F2a/D, D4 zu R5).
    """
    from app.ui.generate_dialog import GenerateDialog
    from app.ui.settings import UiSettings
    from app.ui.settings_dialog import SettingsDialog
    from tests.scripted_backend import ScriptedMeshBackend

    generate = GenerateDialog(backend=ScriptedMeshBackend())
    settings = SettingsDialog(UiSettings(remote_port=8765))
    try:
        generate.seed.setValue(1_234_567)
        assert generate.seed.lineEdit().text() == "1234567"
        assert settings.remote_port.lineEdit().text() == "8765"
    finally:
        generate.release()
        generate.deleteLater()
        settings.deleteLater()


def test_every_computed_number_of_places_is_known() -> None:
    _bare, computed = _scan()
    unknown = sorted(
        f"{name}: setDecimals({source})" for name, source in set(computed) - set(COMPUTED_PLACES)
    )
    assert not unknown, (
        "Stellenzahl ohne Nachweis — ein Feld ohne Nachkomma entsteht über grouped_spin; "
        "sonst den Ort mit seinen wirksamen Werten in COMPUTED_PLACES eintragen:\n"
        + "\n".join(unknown)
    )
    stale = sorted(f"{name}: {source}" for name, source in set(COMPUTED_PLACES) - set(computed))
    assert not stale, f"Eintrag trifft keinen Aufruf mehr — austragen: {stale}"


@pytest.mark.parametrize("place", list(COMPUTED_PLACES), ids=lambda place: f"{place[0]}:{place[1]}")
def test_no_computed_number_of_places_is_zero(qt_app: QApplication, place: tuple[str, str]) -> None:
    """Der wirksame Wert an jedem Ort, über alles, was ihn erreicht."""
    places = list(COMPUTED_PLACES[place]())
    assert places, f"{place}: nichts erreicht diesen Ort — dann prüft das nichts"
    assert min(places) >= 1, f"{place}: ein Feld mit {min(places)} Stellen ohne Dreiergruppen"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("self.count: QSpinBox = QSpinBox(self)\n", ("count", "")),
        ("self.count = GroupedIntSpin(self) if wide else QSpinBox(self)\n", ("", "")),
        ("class Count(QSpinBox):\n    pass\n", ("class Count", "")),
        (
            "editor = BoundedSpin(parent)\neditor.setDecimals(int(field.step < 1))\n",
            (None, "int(field.step < 1)"),
        ),
        ("box.setDecimals(0)\n", (None, "0")),
    ],
    ids=["annotiert", "bedingt", "abgeleitet", "berechnet", "null"],
)
def test_the_guard_finds_every_form(source: str, expected: tuple[str | None, str]) -> None:
    """Gegenprobe an gebautem Quelltext: jede Form, in der ein Feld ohne Gruppen entstand."""
    bare, computed = _findings(source, "probe.py")
    target, places = expected
    if target is not None:
        assert [found[1] for found in bare] == [target]
    if places:
        assert computed == [("probe.py", places)]
    assert not _findings("box.setDecimals(2)\nfield = GroupedIntSpin(self)\n", "probe.py")[1]


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
    """Jede Druckzeile ohne Nachkomma baut ein ``GroupedSpin`` — Anzahl wie Maß."""
    from app.core.knowledge.print_fields import FIELDS
    from app.ui.print_settings_dialog import _make_setting_editor

    whole = [
        field
        for field in FIELDS
        if field.kind == "int" or (field.kind == "float" and field.decimals == 0)
    ]
    paths = {field.path for field in whole}
    assert {"speed.acceleration", "speed.travel", "temperature.nozzle"} <= paths, paths
    host = QWidget()
    try:
        for field in whole:
            editor = _make_setting_editor(field, host, lambda *_args: None)
            assert isinstance(editor, GroupedSpin), field.path
    finally:
        host.deleteLater()


def _type(editor: QWidget, text: str) -> None:
    """Tippt ``text`` über den ganzen alten Inhalt und bestätigt mit der Eingabetaste."""
    line = editor.lineEdit()  # type: ignore[attr-defined]
    editor.setFocus(Qt.FocusReason.TabFocusReason)
    line.selectAll()
    QTest.keyClicks(line, text)
    QTest.keyClick(line, Qt.Key.Key_Return)


@pytest.mark.parametrize("language", available_languages())
def test_a_whole_print_setting_reads_a_thousand_in_every_language(
    qt_app: QApplication, language: str
) -> None:
    """*Leerfahrt* nahm „1.000“ als 1 mm/s, *Beschleunigung* stand ohne Gruppen (R2)."""
    from app.core.knowledge.print_fields import FIELDS
    from app.ui.print_settings_dialog import _make_setting_editor

    before = QLocale()
    QLocale.setDefault(QLocale(language))
    host = QWidget()
    try:
        fields = {field.path: field for field in FIELDS}
        travel = _make_setting_editor(fields["speed.travel"], host, lambda *_args: None)
        acceleration = _make_setting_editor(fields["speed.acceleration"], host, lambda *_args: None)
        host.show()
        acceleration.setValue(10_000)  # type: ignore[attr-defined]
        assert acceleration.lineEdit().text() == f"10{GAP}000 mm/s²"  # type: ignore[attr-defined]
        for editor, typed, expected in (
            (travel, "1.000", 1000.0),
            (travel, "1,000", 1000.0),
            (travel, f"1{GAP}000", 1000.0),
            (acceleration, "12.000", 12_000.0),
            (acceleration, "2,500", 2500.0),
        ):
            editor.setValue(300)  # type: ignore[attr-defined]
            _type(editor, typed)
            assert editor.value() == expected, (language, typed, editor.value())  # type: ignore[attr-defined]
    finally:
        host.deleteLater()
        QLocale.setDefault(before)
