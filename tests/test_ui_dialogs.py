"""Aus dem Operationsschema erzeugte Dialoge: Werte, Auswahl und gestufte Tiefe (§2.5)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
)

from app.core.registry import REGISTRY
from app.ui.main_window import MainWindow
from app.ui.op_dialog import OperationDialog
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


def test_a_dialog_is_generated_from_the_parameter_schema(qt_app: QApplication) -> None:
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    values = dialog.values()

    assert set(values) == {entry.name for entry in REGISTRY.get("load").params.spec()}
    assert values["unit"] == "auto"
    assert values["weld"] is True


@pytest.mark.parametrize("finish", ["accept", "reject"])
def test_operation_waits_for_the_saved_spool_and_window_keeps_a_cancelled_dialogs_write(
    window: MainWindow,
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    finish: str,
) -> None:
    """Anwenden wartet auf die neue Spule; Abbrechen verliert keinen bestätigten Lagerauftrag."""
    from time import monotonic

    from PySide6.QtCore import QCoreApplication
    from PySide6.QtTest import QTest

    from app.core.knowledge import filaments
    from app.ui.filament_picker import NEW_FILAMENT, FilamentField, NewFilamentDialog

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    original = filaments.save
    entered, released = threading.Event(), threading.Event()

    def save(entry):
        entered.set()
        assert released.wait(5)
        return original(entry)

    def confirm(dialog):
        dialog.name.setText("Neue Spule")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(filaments, "save", save)
    monkeypatch.setattr(NewFilamentDialog, "exec", confirm)
    dialog = OperationDialog(REGISTRY.get("assign_slot"), ["obj_1"], window, values={"slot": 0})
    field = dialog.findChild(FilamentField)
    assert field is not None
    writer = field._writes
    dialog.show()
    try:
        field._make_one(field.findData(NEW_FILAMENT))
        assert entered.wait(2)
        assert not dialog._accept_button.isEnabled()
        assert "gespeichert" in dialog._accept_button.toolTip()
        dialog.accept()
        assert not dialog.isHidden()
        if finish == "reject":
            dialog.reject()
            dialog.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not window.wait_for_workers(0)
        assert writer.parent() is window
    finally:
        released.set()
        deadline = monotonic() + 5
        while not writer.wait_for_workers(0) and monotonic() < deadline:
            QTest.qWait(10)
    assert writer.wait_for_workers(0)
    assert [entry.name for entry in filaments.catalogue()] == ["Neue Spule"]
    if finish == "accept":
        assert dialog._accept_button.isEnabled()
        assert dialog.values()["name"] == "Neue Spule"
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
        dialog.deleteLater()


def test_choosing_a_profileless_filament_clears_old_slicer_metadata(
    qt_app: QApplication,
) -> None:
    """Ein Filamentwechsel darf keine unsichtbare Herstellerwahl behalten.

    Eine lokale Spule hat bewusst kein Slicer-Profil. Wird sie in einem
    geöffneten Farbschritt gewählt, muss deshalb der alte Profilname
    verschwinden; sonst fährt die neue Spule mit den Druckwerten der alten.
    """
    dialog = OperationDialog(
        REGISTRY.get("assign_slot"),
        ["obj_1"],
        values={
            "slot": 1,
            "name": "PETG Grau",
            "colour": "#808080",
            "material_type": "PETG",
            "slicer_profile": "Elegoo PETG PRO @ECC2",
        },
    )
    try:
        dialog._fill_filament_fields("PLA Weiß", "#ffffff", "PLA", "")

        values = dialog.values()
        assert values["name"] == "PLA Weiß"
        assert values["material_type"] == "PLA"
        assert values["slicer_profile"] == "", "die leere Auswahl löscht den alten Wert"
    finally:
        dialog.deleteLater()


def test_a_feature_parameter_offers_the_features(qt_app: QApplication) -> None:
    """§18.5: „face_2" tippt niemand, der es nicht vorher abgelesen hat.

    Der Parameter war ein leeres Textfeld, und sein eigener doc-Satz versprach,
    er werde „beim Anklicken im Fenster eingetragen" — abzulesen war die
    Kennung nur im Objektbaum, wo die Namen bei Standardbreite abgeschnitten
    sind.
    """
    from PySide6.QtWidgets import QComboBox

    spec = REGISTRY.get("create_lid")
    features = {"face_2": "face_2 · 3915 mm²", "hole_1": "hole_1 · Ø5,19 mm"}
    dialog = OperationDialog(spec, ["obj_1"], features=features)
    try:
        editor = dialog._editors["at_feature"]
        assert isinstance(editor, QComboBox), "eine Liste, kein Textfeld"

        labels = [editor.itemText(index) for index in range(editor.count())]
        assert "face_2 · 3915 mm²" in labels, "die Beschriftung, nicht die Kennung"
        assert editor.itemData(0) == "", "ohne Merkmal geht es auch — der Parameter ist optional"
        assert dialog.values()["at_feature"] == "", "und die Vorgabe bleibt leer"

        editor.setCurrentIndex(labels.index("hole_1 · Ø5,19 mm"))
        assert dialog.values()["at_feature"] == "hole_1", "die Kennung reist mit, nicht der Text"
    finally:
        dialog.deleteLater()


def test_an_unknown_feature_is_shown_not_replaced(qt_app: QApplication) -> None:
    """Ein gespeicherter Wert, den die Liste nicht kennt, bleibt stehen.

    Wer eine Operation aus dem Verlauf öffnet, deren Merkmal seit einer
    Umbenennung nicht mehr da ist, soll sehen, was dasteht — nicht
    stillschweigend ein anderes bekommen.
    """
    from PySide6.QtWidgets import QComboBox

    spec = REGISTRY.get("create_lid")
    dialog = OperationDialog(
        spec, ["obj_1"], values={"at_feature": "face_9"}, features={"face_2": "face_2 · 100 mm²"}
    )
    try:
        editor = dialog._editors["at_feature"]
        assert isinstance(editor, QComboBox)
        assert dialog.values()["at_feature"] == "face_9"
    finally:
        dialog.deleteLater()


def test_clicking_a_feature_fills_the_field(qt_app: QApplication) -> None:
    """Der ``doc``-Satz versprach es seit je: „wird beim Anklicken im Fenster
    eingetragen".

    Einzulösen war das nicht, solange der Dialog das Fenster sperrte — es gab
    kein Anklicken, während er offen war. Jetzt ist der kürzeste Weg zu einer
    Fläche wieder der, auf sie zu zeigen.
    """
    spec = REGISTRY.get("create_lid")
    dialog = OperationDialog(spec, ["obj_1"], features={"face_2": "face_2 · 3915 mm²"})
    try:
        assert dialog.take_feature("face_2", "face_2 · 3915 mm²")
        assert dialog.values()["at_feature"] == "face_2"

        # Ein Merkmal, das die Liste nicht kennt, kommt trotzdem an: erkannt
        # wird nach jeder Operation neu, der Dialog steht seit vorher offen.
        assert dialog.take_feature("hole_7", "hole_7 · Ø3,20 mm")
        assert dialog.values()["at_feature"] == "hole_7"
    finally:
        dialog.deleteLater()


def test_a_dialog_without_a_feature_field_takes_nothing(qt_app: QApplication) -> None:
    """Der Aufrufer weiß sonst nicht, ob sein Klick angekommen ist."""
    dialog = OperationDialog(REGISTRY.get("drill_hole"), ["obj_1"])
    try:
        assert not dialog.take_feature("face_2", "face_2 · 100 mm²")
    finally:
        dialog.deleteLater()


def test_clicking_a_spot_fills_the_position(qt_app: QApplication) -> None:
    """§18.5: zeigen statt tippen — und §11 bleibt gewahrt.

    *Bohrung setzen* öffnete mit X, Y und Z auf 0,00, und der Ursprung liegt
    bei einer geladenen Platte an einer Ecke. Wer dort bohrte, kratzte einen
    Span von der Kante ab. Was der Klick einträgt, steht danach lesbar da: die
    Zahl ist die Wahrheit, das Zeigen nur die bequeme Eingabe.
    """
    dialog = OperationDialog(REGISTRY.get("drill_hole"), ["obj_1"])
    try:
        assert dialog.take_point((12.5, -7.25, 4.0))

        values = dialog.values()
        assert values["x"] == pytest.approx(12.5)
        assert values["y"] == pytest.approx(-7.25)
        assert values["z"] == pytest.approx(4.0)
    finally:
        dialog.deleteLater()


def test_a_dialog_without_a_position_takes_no_point(qt_app: QApplication) -> None:
    """Nicht jede Operation hat eine Stelle, an der sie arbeitet."""
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    try:
        assert not dialog.take_point((1.0, 2.0, 3.0))
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize(
    ("shown", "requested", "expected"),
    [(False, 240, 380), (False, 520, 520), (True, 380, 380), (True, 520, 520)],
)
def test_the_dialog_keeps_out_of_the_middle_of_the_view(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    shown: bool,
    requested: int,
    expected: int,
) -> None:
    """Bei vorhandenem Platz steht der Dialog rechts und vollständig im Anker.

    Die Breiten sind Vorgaben dieser Geometrieprobe. Vor dem Anzeigen zählt
    die Mindestbreite, danach die gewählte Fensterbreite; die Schriftmetrik
    des Offscreen-Treibers sagt nichts über einen Kundendialog aus.
    """
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QWidget

    anchor = QWidget()
    room = qt_app.primaryScreen().availableGeometry().adjusted(16, 32, -16, -32)
    anchor.setGeometry(room)
    anchor.show()
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    try:
        if shown:
            dialog.setFixedWidth(requested)
            dialog.show()
            QApplication.processEvents()
        else:
            monkeypatch.setattr(dialog, "sizeHint", lambda: QSize(requested, 400))
        dialog.place_beside(anchor)
        middle = anchor.mapToGlobal(anchor.rect().center()).x()

        if expected + 24 < anchor.width() / 2:
            assert dialog.x() > middle, "der Dialog lässt bei genügend Platz die Mitte frei"
        assert dialog.y() >= anchor.mapToGlobal(anchor.rect().topLeft()).y()
        right_edge = anchor.mapToGlobal(anchor.rect().topRight()).x()
        assert dialog.x() + expected <= right_edge, "auch die Mindestbreite bleibt im Anker"
    finally:
        dialog.deleteLater()
        anchor.deleteLater()


def test_a_narrow_view_leaves_the_dialog_where_it_was(qt_app: QApplication) -> None:
    """Passt er nicht daneben, bleibt er, wo Qt ihn hingesetzt hat.

    Ein Dialog halb außerhalb des Bildschirms wäre schlimmer als einer in der
    Mitte.
    """
    from PySide6.QtWidgets import QWidget

    anchor = QWidget()
    anchor.resize(120, 400)
    anchor.show()
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    try:
        before = dialog.pos()
        dialog.place_beside(anchor)

        assert dialog.pos() == before
    finally:
        dialog.deleteLater()
        anchor.deleteLater()


def test_advanced_parameters_sit_behind_the_fold(qt_app: QApplication) -> None:
    """§2.4: die Vorderseite hält, was Leute wirklich ändern.

    Und der hintere Teil ist wirklich weg, nicht nur grau: eine ankreuzbare
    Gruppe graut ihre Felder aus und lässt sie stehen — die gestufte Tiefe war
    damit gedacht und nicht gebaut.
    """
    dialog = OperationDialog(REGISTRY.get("load"), [])

    assert hasattr(dialog, "advanced"), "load hat hintere Parameter, also gibt es die Klappe"
    assert not dialog.advanced.isChecked(), "sie beginnt zugeklappt"

    hidden = [
        editor
        for name, editor in dialog._editors.items()
        if next(entry.placement for entry in dialog.spec.params.spec() if entry.name == name)
        == "advanced"
    ]
    assert hidden, "diese Operation hat welche"
    assert all(not editor.isVisibleTo(dialog) for editor in hidden), "zugeklappt heißt unsichtbar"


def test_an_open_advanced_section_never_overlaps_the_action_buttons(
    qt_app: QApplication,
) -> None:
    """Der aufgeklappte Gewinde-Dialog bleibt vollständig bedienbar."""
    dialog = OperationDialog(REGISTRY.get("insert_printed_thread"), [])
    try:
        dialog.show()
        QApplication.processEvents()
        dialog.advanced.setChecked(True)
        QApplication.processEvents()

        box = dialog.findChild(QDialogButtonBox)
        assert box is not None
        from app.ui.op_dialog import inactive_dependency

        schema = dialog.spec.params.spec()
        values = dialog.values()
        advanced = [
            dialog._editors[entry.name]
            for entry in schema
            if entry.placement == "advanced"
            and not entry.internal
            and inactive_dependency(entry, schema, values) is None
            and entry.name not in {"surface_distance_1", "surface_distance_2"}
        ]
        assert advanced and all(editor.isVisibleTo(dialog) for editor in advanced)
        for entry in schema:
            if entry.internal:
                assert not dialog._editors[entry.name].isVisibleTo(dialog)
        viewport = dialog._scroll.viewport()
        viewport_bottom = viewport.mapToGlobal(viewport.rect().bottomLeft()).y()
        footer_top = box.mapToGlobal(box.rect().topLeft()).y()
        assert viewport_bottom < footer_top, "auch scrollende Felder bleiben oberhalb der Knöpfe"
        assert dialog.rect().contains(box.mapTo(dialog, box.rect().bottomRight()))
    finally:
        dialog.close()


def test_two_ways_are_two_buttons_not_a_list(qt_app: QApplication) -> None:
    """Die Frage vor der Vollerkennung antwortet mit einem Klick (Durchsicht 0.5.1).

    Vorher stand eine Liste mit zwei Zeilen da und darunter ein Knopf, dessen
    Beschriftung mit der Zeile wechselte: Wer mit Erkennung laden wollte, wählte
    erst die Zeile und klickte dann den Knopf.
    """
    from PySide6.QtWidgets import QPushButton

    from app.ui.dialogs import AskDialog

    dialog = AskDialog(
        "„Drache“ hat 2,3 Millionen Dreiecke …",
        ["Sofort laden", "Mit Merkmalserkennung laden"],
        as_buttons=True,
    )
    answers = [
        button
        for button in dialog.findChildren(QPushButton)
        if button.text() in ("Sofort laden", "Mit Merkmalserkennung laden")
        and not button.isHidden()
    ]
    assert len(answers) == 2, "je Antwort ein sichtbarer Knopf"
    assert dialog.list.isHidden(), "keine Liste daneben"
    assert answers[0].isDefault(), "Enter nimmt die erste Antwort"
    answers[1].click()
    assert dialog.result() == AskDialog.DialogCode.Accepted
    assert dialog.chosen() == "Mit Merkmalserkennung laden"
    dialog.deleteLater()


def test_only_short_actions_without_candidates_become_buttons() -> None:
    """Kandidaten im Bild, lange Namen oder viele Antworten bleiben eine Liste."""
    from app.ui.main_window import _answers_as_buttons
    from app.ui.session import AskRequest

    assert _answers_as_buttons(AskRequest("?", ["Sofort laden", "Mit Merkmalserkennung laden"]))
    assert not _answers_as_buttons(
        AskRequest("?", ["hole_1", "hole_2"], candidates=(("obj_1", "hole_1"),))
    )
    assert not _answers_as_buttons(AskRequest("?", ["a", "b", "c", "d"]))
    assert not _answers_as_buttons(
        AskRequest("?", ["eine sehr lange Modelldatei im Archiv, Teil 1.stl", "b"])
    )
    assert not _answers_as_buttons(AskRequest("?", ["nur eine"]))


def test_undoing_a_changed_step_says_the_change_not_the_step() -> None:
    """Strg+Z nach *Offen lassen* sagte „Modell einfügen zurückgenommen.“ (Durchsicht 0.5.1).

    Zurückgenommen war nur die Änderung am Ladeschritt; das Modell stand weiter
    da. Ein eigener Schritt und ein gelöschter behalten den alten Satz.
    """
    from app.core.types import DocumentChange, DocumentState, Operation, Transaction
    from app.ui.main_window import _history_feedback

    step = Operation(id=1, op="load", inputs=(), outputs=("obj_1",), params={})
    edited = Transaction(
        id="t2",
        title="Modell einfügen",
        ops=(),
        changes=DocumentChange(
            before=DocumentState(edited_ops={1: step}), after=DocumentState(edited_ops={1: step})
        ),
    )
    assert _history_feedback(edited, undone=True) == "Änderung an „Modell einfügen“ zurückgenommen."
    assert (
        _history_feedback(edited, undone=False)
        == "Änderung an „Modell einfügen“ wieder angewendet."
    )
    own = Transaction(id="t1", title="Bohrung", ops=(2,))
    assert _history_feedback(own, undone=True) == "Bohrung zurückgenommen."
    assert _history_feedback(own, undone=False) == "Bohrung wieder angewendet."
    removed = Transaction(
        id="t3",
        title="Schritte löschen",
        ops=(),
        changes=DocumentChange(
            before=DocumentState(edited_ops={1: step}), after=DocumentState(edited_ops={1: None})
        ),
    )
    assert _history_feedback(removed, undone=True) == "Schritte löschen zurückgenommen."
    assert _history_feedback(removed, undone=False) == "Schritte löschen wieder angewendet."


@pytest.mark.parametrize(
    ("path", "name"),
    [
        (r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe", "ElegooSlicer"),
        (r"C:\Program Files\UltiMaker Cura 5.13.0\CuraEngine.exe", "UltiMaker Cura 5.13.0"),
        ("/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer", "PrusaSlicer"),
        ("/usr/bin/prusa-slicer", "prusa-slicer"),
    ],
)
def test_a_slicer_is_named_as_on_its_box(path: str, name: str) -> None:
    """Druckdialog und Erstinbetriebnahme nennen einen Slicer gleich (KUNDE-02).

    Der Erststart zeigte `elegoo-slicer`, `CuraEngine` — Dateinamen, während der
    Druckdialog „ElegooSlicer“ und „UltiMaker Cura 5.13.0“ schrieb.
    """
    from pathlib import PurePosixPath, PureWindowsPath

    from app.ui.labels import slicer_title

    pure = PureWindowsPath(path) if "\\" in path else PurePosixPath(path)
    assert slicer_title(pure) == name  # type: ignore[arg-type]


def test_the_first_run_names_slicers_like_the_print_dialog() -> None:
    """Keine zweite Namensregel im Erststart: alle drei Stellen fragen ``slicer_title``."""
    import inspect

    from app.ui import first_run

    source = inspect.getsource(first_run)
    assert ".stem, " not in source, "ein Slicer wird wieder mit seinem Dateinamen eingetragen"
    assert source.count("slicer_title(") >= 3


# --- Eine Form für alle Dialoge (RM-518) ------------------------------------------

_UI = Path(__file__).resolve().parents[1] / "app" / "ui"

#: Wo ein Rahmen bleibt, mit Grund — er gliedert dort keinen Dialog in Abschnitte.
_FRAMES_WITH_A_REASON: dict[str, str] = {
    "filament_usage.py": "eine Karte je Filamentzeile, kein Abschnitt eines Formulars",
}

#: Noch nicht umgestellt — jede Datei hier ist ein offener Teil von RM-518 und
#: verlässt die Liste mit ihrer Umstellung (Erstlauf: RM-515, eigener Baustein:
#: RM-517).
_FRAMES_STILL_TO_GO: dict[str, str] = {
    "first_run.py": "RM-515 stellt den Erstlauf um",
    "recipe_dialog.py": "RM-517 stellt den eigenen Baustein um",
}

#: Dialoge mit mehreren Formularen, die noch nicht ausrichten — wie oben ein
#: offener Teil von RM-518, keine Ausnahme mit Bestand.
_FORMS_STILL_TO_ALIGN: dict[tuple[str, str], str] = {
    ("first_run.py", "FirstRunDialog"): "RM-515 stellt den Erstlauf um",
    ("recipe_dialog.py", "RecipeDialog"): "RM-517 stellt den eigenen Baustein um",
    ("counterpart_dialog.py", "CounterpartDialog"): "noch nicht umgestellt (RM-518)",
    ("organizer_dialog.py", "OrganizerDialog"): "noch nicht umgestellt (RM-518)",
}


def _calls(tree: object, name: str) -> int:
    """Wie oft ``name(...)`` im Baum gerufen wird, als Name oder Attribut."""
    import ast

    return sum(
        1
        for node in ast.walk(tree)  # type: ignore[arg-type]
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == name)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == name)
        )
    )


def test_no_dialog_frames_its_sections() -> None:
    """Abschnitte sind flache Überschriften, kein gerahmter ``QGroupBox`` (RM-518, C18).

    Einstellungen, Erstlauf und *Eigener Baustein* rahmten ihre Abschnitte, die
    übrigen Dialoge klappten flach — zwei Formen, zwei Rhythmen. Gelesen wird
    der Quelltext; die Listen nennen jede Ausnahme mit Grund und werden kürzer,
    nie länger.
    """
    import ast

    framed = sorted(
        path.name
        for path in _UI.rglob("*.py")
        if _calls(ast.parse(path.read_text(encoding="utf-8")), "QGroupBox")
    )
    allowed = set(_FRAMES_WITH_A_REASON) | set(_FRAMES_STILL_TO_GO)
    assert set(framed) <= allowed, f"gerahmte Abschnitte: {sorted(set(framed) - allowed)}"
    done = sorted(set(_FRAMES_STILL_TO_GO) - set(framed))
    assert not done, f"umgestellt — aus der Übergangsliste nehmen: {done}"


def test_a_dialog_with_several_forms_aligns_them() -> None:
    """Wer zwei Formulare hat, gibt ihnen eine Beschriftungskante (RM-518).

    Erzeugen und der Parameterdialog richteten ihre Formulare nicht aus, und
    die Felder begannen in jedem an einer anderen Stelle. Ausgerichtet wird
    über ``panels.align_forms`` oder, mit Rückseite, über
    ``dialogs.align_to_the_front``.
    """
    import ast

    loose: list[str] = []
    for path in sorted(_UI.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {base.id for base in node.bases if isinstance(base, ast.Name)}
            if "QDialog" not in bases or _calls(node, "QFormLayout") < 2:
                continue
            aligned = any(
                _calls(node, name)
                for name in ("align_forms", "align_to_the_front", "_align_to_the_front")
            )
            if not aligned and (path.name, node.name) not in _FORMS_STILL_TO_ALIGN:
                loose.append(f"{path.name}:{node.name}")
    assert not loose, f"Formulare ohne gemeinsame Kante: {loose}"


def test_align_to_the_front_lets_the_back_wrap(qt_app: QApplication) -> None:
    """Die Vorderseite setzt die Spalte; hinten bricht eine längere Beschriftung um (C21)."""
    from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

    from app.ui.dialogs import align_to_the_front

    holder = QWidget()
    try:
        front, back = QFormLayout(), QFormLayout()
        outer = QVBoxLayout(holder)
        outer.addLayout(front)
        outer.addLayout(back)
        front.addRow("Breite", QLineEdit(holder))
        front.addRow("Höhe", QLineEdit(holder))
        back.addRow("Eine sehr lange Beschriftung hinter der Klappe", QLineEdit(holder))
        align_to_the_front(front, back)

        def label(form: QFormLayout, row: int) -> QLabel:
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            assert item is not None and isinstance(item.widget(), QLabel)
            return item.widget()

        long_label = label(back, 0)
        assert long_label.wordWrap(), "hinten bricht die lange Beschriftung um"
        widest = max(label(front, row).sizeHint().width() for row in range(2))
        assert all(label(front, row).minimumWidth() == widest for row in range(2))
        # Umgebrochen wird zwischen Wörtern: so schmal wie die Spalte, außer
        # ein einzelnes Wort ist breiter — abgeschnitten wird nichts.
        assert long_label.maximumWidth() == max(widest, long_label.minimumSizeHint().width())
        assert long_label.fontMetrics().horizontalAdvance(long_label.text()) > (
            long_label.maximumWidth()
        ), "der Satz selbst ist breiter als die Spalte"
    finally:
        holder.deleteLater()
