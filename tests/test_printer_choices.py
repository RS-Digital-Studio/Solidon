"""Die Druckerlisten nennen Drucker, keine Düsen.

Die Slicer führen jede Düse als eigenes Profil („Bambu Lab A1 0.4 nozzle“);
Erststart, Einstellungen und Druckdialog zeigen je Modell eine Zeile, und die
Düse wählt der Druckdialog (Entscheidung Robert). Eine dort gewählte Düse
überlebt das erneute Speichern des Druckers aus dem Slicer.
"""

from __future__ import annotations

from dataclasses import replace

from app.core.knowledge import profiles
from app.core.types import PrinterProfile
from app.ui import first_run
from app.ui.labels import printer_title


def _variant(
    nozzle: float, *, title: str = "", vendor: str = "BBL", identifier: str = ""
) -> PrinterProfile:
    return PrinterProfile(
        id=identifier or f"slicer-a1-{nozzle:g}",
        title=title or f"Bambu Lab A1 {nozzle:g} nozzle",
        build_volume=(256.0, 256.0, 256.0),
        nozzle_diameter=nozzle,
        extrusion_width=round(nozzle * 1.05, 3),
        vendor=vendor,
    )


def test_a_slicer_variant_is_named_without_its_nozzle() -> None:
    """Der Name nennt das Gerät; eine andere Ausführung (HF) bleibt darin, ein
    selbst benannter Drucker heißt, wie der Kunde ihn nannte."""
    assert printer_title(_variant(0.6)) == "Bambu Lab A1"
    assert (
        printer_title(_variant(0.4, title="Original Prusa MK4S HF0.4 nozzle"))
        == "Original Prusa MK4S HF"
    )
    assert printer_title(_variant(0.6, vendor="", title="Werkstatt 0.6 nozzle")) == (
        "Werkstatt 0.6 nozzle"
    )
    builtin = profiles.printer("centauri-carbon-2")
    assert printer_title(builtin) == builtin.title


def test_the_listed_variant_is_the_chosen_one_then_the_usual_nozzle() -> None:
    """Eine Wahl behält ihre Düse; sonst steht die 0,4er für das Modell, und
    fehlt sie, die nächstliegende — bei gleichem Abstand die größere."""
    variants = [(entry.id, entry) for entry in map(_variant, (0.2, 0.6, 0.4, 0.8))]

    assert first_run._listed_variant(variants, keep=())[0] == "slicer-a1-0.4"
    assert first_run._listed_variant(variants, keep={"slicer-a1-0.6"})[0] == "slicer-a1-0.6"
    assert first_run._listed_variant(variants, keep={"elsewhere"})[0] == "slicer-a1-0.4"
    without_usual = [pair for pair in variants if pair[0] != "slicer-a1-0.4"]
    assert first_run._listed_variant(without_usual, keep=())[0] == "slicer-a1-0.6"


def test_a_saved_nozzle_survives_a_fresh_read_from_the_slicer() -> None:
    """Der Druckdialog legt eine andere Düse unter derselben Kennung ab; ein
    frisch gelesenes Slicerprofil behält sie, alles andere kommt neu."""
    found = replace(_variant(0.4), printable_area=((0.0, 0.0), (256.0, 0.0), (0.0, 256.0)))
    saved = replace(_variant(0.4), nozzle_diameter=0.6, extrusion_width=0.63, nozzles=2)

    kept = first_run.with_saved_nozzle(found, saved)

    assert (kept.nozzle_diameter, kept.extrusion_width, kept.nozzles) == (0.6, 0.63, 2)
    assert kept.printable_area == found.printable_area
    assert first_run.with_saved_nozzle(found, None) is found


def test_variants_of_one_printer_become_one_choice(qt_app) -> None:
    """Eine Zeile je Modell, mit der Düse im Hinweis; eine Wahl steht für ihr
    Modell, ein selbst angelegter Drucker bleibt für sich."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QComboBox

    entries = {
        entry.id: entry
        for entry in (
            _variant(0.2),
            _variant(0.4),
            _variant(0.6),
            _variant(
                0.4,
                title="Original Prusa MK4S HF0.4 nozzle",
                vendor="PrusaResearch",
                identifier="slicer-mk4s-hf",
            ),
            _variant(0.6, title="Werkstatt 0.6 nozzle", vendor="", identifier="user-1"),
            _variant(0.4, title="Werkstatt 0.4 nozzle", vendor="", identifier="user-2"),
        )
    }

    def rows(box: QComboBox) -> list[tuple[str, str]]:
        return [
            (box.itemText(index), str(box.itemData(index)))
            for index in range(box.count())
            if box.itemData(index) != first_run._GROUP_HEADER
        ]

    box = QComboBox()
    chosen = QComboBox()
    try:
        first_run.add_printer_choices(box, entries)
        first_run.add_printer_choices(chosen, entries, keep={"slicer-a1-0.6"})

        assert rows(box) == [
            ("Bambu Lab A1", "slicer-a1-0.4"),
            ("Original Prusa MK4S HF", "slicer-mk4s-hf"),
            ("Werkstatt 0.4 nozzle", "user-2"),
            ("Werkstatt 0.6 nozzle", "user-1"),
        ]
        assert ("Bambu Lab A1", "slicer-a1-0.6") in rows(chosen)
        tip = str(box.itemData(box.findData("slicer-a1-0.4"), Qt.ItemDataRole.ToolTipRole))
        assert tip.startswith("Bambu Lab A1, Düse ") and "Druckeinstellungen" in tip
    finally:
        box.deleteLater()
        chosen.deleteLater()
