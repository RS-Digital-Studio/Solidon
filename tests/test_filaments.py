"""Der Filamentkatalog (Konzept Filamente, 26.08.2026).

Beliebig viele benannte Filamente mit Farbe, projektübergreifend im Profil —
die Vorwahl, aus der der Filamentwähler anbietet. Die Grenze je Objekt bleibt
``MAX_SLOTS``; der Katalog kennt keine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.core.knowledge import filaments


@pytest.fixture
def own_catalogue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Ein eigener Einstellungsordner je Test — wie beim Testlaufmarker."""
    monkeypatch.setattr(filaments, "user_config_dir", lambda: tmp_path)
    return tmp_path


def test_a_fresh_catalogue_is_empty(own_catalogue: Path) -> None:
    assert filaments.catalogue() == ()


def test_remember_and_read_back(own_catalogue: Path) -> None:
    filaments.remember(
        "PETG Rot",
        "#d02020",
        material_type="PETG",
        slicer_profile="Elegoo PETG PRO @ECC2",
    )
    filaments.remember("PLA Weiß", "#f0f0f0")

    names = [entry.name for entry in filaments.catalogue()]
    assert names == ["PETG Rot", "PLA Weiß"], "sortiert nach Name, nicht nach Anlage"
    assert filaments.catalogue()[0].colour == "#d02020"
    assert filaments.catalogue()[0].material_type == "PETG"
    assert filaments.catalogue()[0].slicer_profile == "Elegoo PETG PRO @ECC2"


def test_an_old_catalogue_without_type_and_profile_still_opens(own_catalogue: Path) -> None:
    """Die zwei neuen Angaben sind rückwärtskompatible Ergänzungen."""
    filaments.catalogue_path().write_text(
        '[{"name": "PLA Weiß", "colour": "#f0f0f0"}]', encoding="utf-8"
    )

    assert filaments.catalogue() == (
        filaments.CatalogueFilament(name="PLA Weiß", colour="#f0f0f0"),
    )


def test_synchronising_the_slicer_keeps_the_rest_of_the_rack(own_catalogue: Path) -> None:
    filaments.remember("ASA Schwarz", "#202020", material_type="ASA")

    filaments.synchronise(
        [
            filaments.CatalogueFilament(
                name="Elegoo PETG PRO @ECC2",
                colour="#9AA0A6",
                material_type="PETG",
                slicer_profile="Elegoo PETG PRO @ECC2",
            )
        ]
    )

    entries = {entry.name: entry for entry in filaments.catalogue()}
    assert set(entries) == {"ASA Schwarz", "Elegoo PETG PRO @ECC2"}
    assert entries["Elegoo PETG PRO @ECC2"].material_type == "PETG"


def test_the_same_name_changes_the_colour_instead_of_doubling(own_catalogue: Path) -> None:
    """Ein Filament ist sein Name — wer „PETG Rot" neu anlegt, meint dasselbe
    Filament mit anderer Farbe, nicht ein zweites."""
    filaments.remember("PETG Rot", "#d02020")
    filaments.remember("PETG Rot", "#a01010")

    entries = filaments.catalogue()
    assert len(entries) == 1
    assert entries[0].colour == "#a01010"


def test_forget_removes_and_says_whether_it_did(own_catalogue: Path) -> None:
    filaments.remember("PETG Rot", "#d02020")

    assert filaments.forget("PETG Rot") is True
    assert filaments.forget("PETG Rot") is False, "weg heißt weg — kein zweites Mal"
    assert filaments.catalogue() == ()


def test_a_broken_file_means_an_empty_catalogue_not_a_crash(own_catalogue: Path) -> None:
    """Die freundliche Richtung: Eine kaputte Datei kostet die Vorwahl, nie
    den Start der Anwendung."""
    filaments.catalogue_path().write_text("{kaputt", encoding="utf-8")

    assert filaments.catalogue() == ()

    filaments.remember("PETG Rot", "#d02020")
    assert [entry.name for entry in filaments.catalogue()] == ["PETG Rot"]


def test_an_empty_name_stops_with_advice(own_catalogue: Path) -> None:
    with pytest.raises(ValidationError) as raised:
        filaments.remember("   ", "#d02020")
    assert raised.value.suggestions, "Regel 17: auch diese Ausnahme trägt Handlungen"


def test_a_colour_that_is_no_colour_stops_with_advice(own_catalogue: Path) -> None:
    """„#RRGGBB" ist der Vertrag — der 3MF-Export und die Ansicht lesen ihn."""
    for wrong in ("rot", "#12345", "#gg0000", ""):
        with pytest.raises(ValidationError):
            filaments.remember("PETG Rot", wrong)
    assert filaments.catalogue() == (), "abgelehnt heißt: nichts geschrieben"


def test_the_catalogue_survives_a_new_reading(own_catalogue: Path) -> None:
    """Persistenz ist der Zweck: Der Katalog ist die Vorwahl über Projekte
    hinweg, nicht ein Sitzungszustand."""
    filaments.remember("ASA Schwarz", "#202020")

    assert [entry.name for entry in filaments.catalogue()] == ["ASA Schwarz"]
    scratch = list(own_catalogue.glob("*.tmp"))
    assert scratch == [], "atomar geschrieben — kein halber Katalog bleibt liegen"
