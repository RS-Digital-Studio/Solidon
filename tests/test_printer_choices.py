"""Die Druckerlisten nennen Drucker, keine Düsen.

Die Slicer führen jede Düse als eigenes Profil („Bambu Lab A1 0.4 nozzle“);
Erststart, Einstellungen und Druckdialog zeigen je Modell eine Zeile, und die
Düse wählt der Druckdialog (Entscheidung Robert). Eine dort gewählte Düse
überlebt das erneute Speichern des Druckers aus dem Slicer.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

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


def test_every_printer_list_offers_the_printers_of_the_chosen_slicer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Erst der Slicer, dann seine Drucker — in Erststart, Einstellungen und
    Druckdialog dieselbe Liste (Entscheidung Robert, 06.10.2026).

    Der Druckdialog bot nur Solidons Tabelle und die gespeicherten Drucker an:
    Wer im Erststart den Kobra S1 Max gewählt hatte, fand dort den Kobra S1
    nicht, obwohl Anycubic Slicer Next ihn führt. Angeboten wird, was der
    Slicer nennt, dazu die eigenen, der allgemeine und die Resin-Drucker; ein
    Tabellendrucker, den der Slicer nicht nennt, steht nicht da. Eine am
    gespeicherten Drucker gesetzte Düse bleibt.
    """
    original_profiles_dir = profiles.user_profiles_dir

    def restore_profile_cache() -> None:
        profiles.user_profiles_dir = original_profiles_dir
        profiles.reload()

    request.addfinalizer(restore_profile_cache)
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    profiles.reload()
    s1, s1_max = (
        _variant(0.4, title=f"Anycubic {model} 0.4 nozzle", vendor="Anycubic", identifier=key)
        for model, key in (("Kobra S1", "slicer-kobra-s1"), ("Kobra S1 Max", "slicer-s1-max"))
    )
    discovered = {s1.id: s1, s1_max.id: s1_max}
    profiles.save_printer(replace(s1_max, nozzle_diameter=0.6, extrusion_width=0.63))
    workshop = profiles.save_printer(
        replace(profiles.printer(profiles.DEFAULT_PRINTER), id="user-werkstatt", title="Werkstatt")
    )
    resin = {name for name, entry in profiles.printer_profiles().items() if entry.is_resin}
    assert resin, "die Tabelle führt Resin-Drucker"

    offered = first_run.printers_on_offer(
        (*discovered, *profiles.user_printer_profiles()), discovered
    )

    assert {s1.id, s1_max.id, workshop.id, profiles.DEFAULT_PRINTER} | resin == set(offered)
    assert "centauri-carbon-2" in profiles.printer_profiles(), "Gegenprobe: in der Tabelle"
    assert offered[s1.id] == s1
    assert offered[s1_max.id].nozzle_diameter == pytest.approx(0.6), "die gesetzte Düse bleibt"
    assert first_run.known_printers(discovered)[s1_max.id] == offered[s1_max.id]


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
