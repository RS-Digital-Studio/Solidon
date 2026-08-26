"""Der Filamentwähler (Konzept „Filamente statt nummerierter Slots").

Was hier geprüft wird, ist die Frage, an der das alte Zahlenfeld gescheitert
ist: *Welche Farbe hat Slot 1?* Der Wähler muss sie beantworten, ohne dass
jemand erst malt — und er muss die Slotnummer liefern, mit der der Kern
weiterrechnet.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.knowledge import filaments
from app.core.types import MaterialSlot
from app.ui.filament_picker import NEW_FILAMENT, FilamentField, hex_of


def test_a_colour_from_the_document_becomes_a_hex_value() -> None:
    """Das Dokument führt Anteile, die Oberfläche zeigt Hexwerte."""
    assert hex_of((1.0, 0.0, 0.0)) == "#ff0000"
    assert hex_of((0.0, 0.5, 1.0)) == "#0080ff"
    assert hex_of(None) == "", "keine Farbe ist keine Farbe, nicht Schwarz"


def test_the_picker_answers_what_colour_slot_one_has(qt_app: QApplication) -> None:
    """Der Anlass des ganzen Umbaus.

    Neben dem alten Zahlenfeld stand nichts: Wer wissen wollte, was Slot 1
    ist, malte einmal und sah nach. Jetzt trägt der Eintrag Namen und Farbe.
    """
    field = FilamentField(
        1,
        slots=[
            MaterialSlot(index=0, name="Unbemalt"),
            MaterialSlot(index=1, name="PETG Rot", colour=(0.8, 0.1, 0.1)),
        ],
    )

    assert field.currentData() == 1, "der übergebene Slot steht gewählt da"
    assert "PETG Rot" in field.currentText(), "der Name des Filaments fehlt"
    assert not field.itemIcon(field.currentIndex()).isNull(), "kein Farbfeld am Eintrag"


def test_the_value_stays_the_slot_number(qt_app: QApplication) -> None:
    """Der Kern rechnet mit der Nummer — der Wähler ist Bedienung, kein
    Formatwechsel."""
    field = FilamentField(2, slots=[MaterialSlot(index=2, name="PLA Schwarz")])

    assert isinstance(field.currentData(), int)
    assert field.currentData() == 2


def test_slot_zero_is_not_called_a_filament(qt_app: QApplication) -> None:
    """Slot 0 ist die Abwesenheit eines Filaments, keine Spule.

    „Filament 0" hätte behauptet, dort läge eines — und der Kunde hätte
    gesucht, welches.
    """
    field = FilamentField(0)

    position = field.findData(0)
    assert position >= 0
    assert "0 —" not in field.itemText(position), "die nackte Null sagt nichts"
    assert "Ohne" in field.itemText(position)


def test_the_catalogue_is_offered_and_carries_name_and_colour(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Die Vorwahl ist der Punkt: einmal angelegt, in jedem Projekt zur Wahl.

    Und sie meldet Namen und Farbe weiter, damit der Dialog seine Felder
    füllen kann — sonst hätte der Kunde die Spule gewählt und müsste ihren
    Namen daneben trotzdem abtippen.
    """
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    filaments.remember("PETG Rot", "#cc2222")

    field = FilamentField(0)
    position = next(row for row in range(field.count()) if "PETG Rot" in field.itemText(row))

    seen: list[tuple[str, str]] = []
    field.filamentChosen.connect(lambda name, colour: seen.append((name, colour)))
    field.setCurrentIndex(position)
    field._chosen(position)

    assert seen == [("PETG Rot", "#cc2222")], "Name und Farbe müssen weitergehen"
    assert field.currentData() == 1, "die erste freie Nummer, nicht die Null"


def test_a_catalogue_filament_does_not_take_slot_zero(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Null bleibt frei: Sie ist das unbemalte Teil.

    Vergäbe der Wähler sie an das erste Filament der Vorwahl, hieße „Ohne
    Filament" plötzlich „PETG Rot" — und jedes Teil ohne Zuweisung wäre rot.
    """
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    filaments.remember("PLA Weiß", "#eeeeee")

    field = FilamentField(0)

    numbers = [field.itemData(row) for row in range(field.count())]
    assert numbers.count(0) == 1, "die Null steht genau einmal in der Liste"
    white = next(row for row in range(field.count()) if "PLA Weiß" in field.itemText(row))
    assert field.itemData(white) != 0


def test_every_free_number_stays_reachable(qt_app: QApplication) -> None:
    """Keine Sackgasse (§2.1): Wer genau Slot 5 meint, bekommt ihn.

    Der Wähler ist eine Hilfe und keine Bevormundung — die acht Nummern des
    3MF-Farbwechsels bleiben alle erreichbar.
    """
    field = FilamentField(0, slots=[MaterialSlot(index=1, name="PETG Rot")])

    offered = {field.itemData(row) for row in range(field.count())}
    assert set(range(8)) <= offered, "eine Nummer fehlt in der Liste"


def test_a_cancelled_new_filament_leaves_a_usable_value(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """„Neues Filament …" ist kein Wert, den eine Operation kennt.

    Bliebe die Auswahl nach einem Abbruch darauf stehen, ginge NEW_FILAMENT
    als Slotnummer in die Transaktion — eine Zahl, die es im Schema nicht
    gibt.
    """
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    from app.ui import filament_picker

    class Cancelled:
        def __init__(self, *_args: object, **_kwargs: object) -> None: ...

        def exec(self) -> int:
            return 0  # QDialog.DialogCode.Rejected

    monkeypatch.setattr(filament_picker, "NewFilamentDialog", Cancelled)

    field = FilamentField(0)
    position = field.findData(NEW_FILAMENT)
    field.setCurrentIndex(position)
    field._chosen(position)

    assert field.currentData() != NEW_FILAMENT, "der Abbruch lässt keinen Unwert stehen"
    assert isinstance(field.currentData(), int)
