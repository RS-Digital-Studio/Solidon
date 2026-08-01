"""Profile des installierten Slicers finden und zuordnen (Bauplan §29).

Gegen einen nachgebauten Bestand im Temp-Ordner, nicht gegen ein installiertes
Programm: die Suite muss auf einem Bauserver dasselbe Ergebnis liefern wie auf
einem Rechner, auf dem drei Slicer liegen.

Der Aufbau ist der echte, samt der Eigenheiten, die das Bauen gekostet haben —
uneinheitliche Ordnertiefe, geerbte Verträglichkeit, selbst angelegte Profile
ohne ``type``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.export import slicer_profiles as sp
from app.core.types import PrinterProfile


def _write(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


@pytest.fixture
def bestand(tmp_path: Path) -> Path:
    """Ein Profilbestand, wie ihn ein Orca-Ableger ausliefert."""
    root = tmp_path / "resources" / "profiles"

    # Elegoo legt eine Ebene tiefer als Bambu — genau daran scheiterte die
    # Suche beim ersten Versuch.
    _write(
        root / "Elegoo" / "machine" / "ECC2" / "Centauri.json",
        {
            "type": "machine",
            "name": "Elegoo Centauri Carbon 2 0.4 nozzle",
            "instantiation": "true",
            "printer_model": "Elegoo Centauri Carbon 2",
            "nozzle_diameter": ["0.4"],
            "default_print_profile": "0.20mm Standard @CC2",
        },
    )
    _write(
        root / "Elegoo" / "machine" / "ECC2" / "Centauri06.json",
        {
            "type": "machine",
            "name": "Elegoo Centauri Carbon 2 0.6 nozzle",
            "instantiation": "true",
            "printer_model": "Elegoo Centauri Carbon 2",
            "nozzle_diameter": ["0.6"],
        },
    )
    _write(
        root / "Anderer" / "machine" / "Fremd.json",
        {
            "type": "machine",
            "name": "Ganz anderes Gerät 0.4 nozzle",
            "instantiation": "true",
            "printer_model": "Ganz anderes Gerät",
            "nozzle_diameter": ["0.4"],
        },
    )

    # Nur das Standardprofil trägt die Liste; die Geschwister erben sie.
    _write(
        root / "Elegoo" / "process" / "ECC2" / "standard.json",
        {
            "type": "process",
            "name": "0.20mm Standard @CC2",
            "instantiation": "true",
            "compatible_printers": ["Elegoo Centauri Carbon 2 0.4 nozzle"],
        },
    )
    _write(
        root / "Elegoo" / "process" / "ECC2" / "fein.json",
        {
            "type": "process",
            "name": "0.12mm Fein @CC2",
            "instantiation": "true",
            "inherits": "0.20mm Standard @CC2",
        },
    )
    _write(
        root / "Elegoo" / "process" / "ECC2" / "fremd.json",
        {
            "type": "process",
            "name": "0.20mm Standard @Fremd",
            "instantiation": "true",
            "compatible_printers": ["Ganz anderes Gerät 0.4 nozzle"],
        },
    )
    # Ein Zwischenstück der Erbkette — im Slicer selbst nicht wählbar.
    _write(
        root / "Elegoo" / "process" / "fdm_process_common.json",
        {"type": "process", "name": "fdm_process_common"},
    )
    # Filamente liegen daneben und gehen niemanden etwas an.
    _write(root / "Elegoo" / "filament" / "pla.json", {"type": "filament", "name": "PLA"})
    return root


@pytest.fixture
def slicer(bestand: Path) -> Path:
    """Die Programmdatei über dem Profilbestand."""
    executable = bestand.parent.parent / "orca-slicer.exe"
    executable.write_bytes(b"")
    return executable


# --- Finden ------------------------------------------------------------------------


def test_the_install_root_is_found_above_the_executable(slicer: Path, bestand: Path) -> None:
    assert sp.install_root(slicer) == bestand


def test_profiles_are_found_at_any_depth(slicer: Path) -> None:
    """Bambu legt die Profile direkt in ``machine/``, Elegoo eine Ebene tiefer.
    Eine feste Tiefe fände nur die eine Hälfte."""
    found = sp.find_profiles(slicer, "orca")

    names = {entry.name for entry in found}
    assert "Elegoo Centauri Carbon 2 0.4 nozzle" in names
    assert "0.12mm Fein @CC2" in names


def test_the_kind_comes_from_the_folder(slicer: Path) -> None:
    found = sp.find_profiles(slicer, "orca")

    assert {entry.kind for entry in found} == {"machine", "process"}
    assert all(entry.kind == "machine" for entry in sp.machines(found))


def test_filaments_and_intermediates_stay_out(slicer: Path) -> None:
    """Ein Zwischenstück der Erbkette ist im Slicer nicht wählbar und hier
    ebenso wenig; Filamente gehören in eine andere Auswahl."""
    names = {entry.name for entry in sp.find_profiles(slicer, "orca")}

    assert "fdm_process_common" not in names
    assert "PLA" not in names


def test_prusa_needs_no_profiles(slicer: Path) -> None:
    """§29: eine PrusaSlicer-ini läuft eigenständig — eine leere Liste ist
    hier die richtige Antwort, kein Mangel."""
    assert sp.find_profiles(slicer, "prusa") == []


def test_a_missing_install_root_is_no_crash(tmp_path: Path) -> None:
    assert sp.find_profiles(tmp_path / "nirgends.exe", "orca") == []


def test_broken_json_is_skipped_not_fatal(slicer: Path, bestand: Path) -> None:
    (bestand / "Elegoo" / "machine" / "kaputt.json").write_text("{ das ist keins", encoding="utf-8")

    found = sp.find_profiles(slicer, "orca")

    assert found, "der Rest muss trotzdem ankommen"


# --- Zuordnen ----------------------------------------------------------------------


def _printer(nozzle: float = 0.4) -> PrinterProfile:
    return PrinterProfile(
        id="x",
        title="Elegoo Centauri Carbon 2",
        build_volume=(256.0, 256.0, 256.0),
        nozzle_diameter=nozzle,
    )


def test_the_printer_finds_its_machine_profile(slicer: Path) -> None:
    machine, process = sp.match(sp.find_profiles(slicer, "orca"), _printer())

    assert machine is not None and machine.name == "Elegoo Centauri Carbon 2 0.4 nozzle"
    assert process is not None and process.name == "0.20mm Standard @CC2"


def test_the_nozzle_decides_between_variants(slicer: Path) -> None:
    """Dasselbe Gerät gibt es mit vier Düsen. Das falsche Profil zu nehmen
    hieße, mit der falschen Bahnbreite zu rechnen."""
    machine, _process = sp.match(sp.find_profiles(slicer, "orca"), _printer(nozzle=0.6))

    assert machine is not None and machine.nozzle == pytest.approx(0.6)


def test_an_unknown_printer_gets_no_guess(slicer: Path) -> None:
    """Eine falsche Vorauswahl wäre schlimmer als keine — sie sähe aus wie
    eine Entscheidung."""
    stranger = PrinterProfile(
        id="y", title="Gerät, das es hier nicht gibt", build_volume=(100.0, 100.0, 100.0)
    )

    assert sp.match(sp.find_profiles(slicer, "orca"), stranger) == (None, None)


def test_inherited_compatibility_counts(slicer: Path) -> None:
    """Nur ein Profil je Familie trägt die Verträglichkeitsliste, die
    Geschwister erben sie. Wer nur das eigene Feld liest, findet eines statt
    aller."""
    found = sp.find_profiles(slicer, "orca")
    machine, _process = sp.match(found, _printer())

    fitting = {entry.name for entry in sp.processes(found, machine)}

    assert fitting == {"0.20mm Standard @CC2", "0.12mm Fein @CC2"}
    assert "0.20mm Standard @Fremd" not in fitting


def test_an_inheritance_loop_does_not_hang(slicer: Path, bestand: Path) -> None:
    _write(
        bestand / "Elegoo" / "process" / "ECC2" / "kreis_a.json",
        {"type": "process", "name": "A", "instantiation": "true", "inherits": "B"},
    )
    _write(
        bestand / "Elegoo" / "process" / "ECC2" / "kreis_b.json",
        {"type": "process", "name": "B", "instantiation": "true", "inherits": "A"},
    )
    found = sp.find_profiles(slicer, "orca")
    known = {entry.name: entry for entry in found if entry.kind == "process"}

    assert sp.compatible_with(known["A"], known) == ()


# --- Eigene Profile ----------------------------------------------------------------


def test_own_profiles_are_read_and_marked(slicer: Path, bestand: Path) -> None:
    """Selbst angelegte Profile tragen kein ``type`` und kein
    ``instantiation`` — sie erben bloß. Genau die will man in der Liste haben.
    """
    _write(
        bestand / "Elegoo" / "process" / "ECC2" / "eigenes.json",
        {"name": "Meine Fassung", "from": "User", "inherits": "0.20mm Standard @CC2"},
    )
    found = sp.find_profiles(slicer, "orca")

    own = [entry for entry in found if entry.name == "Meine Fassung"]
    assert own, "ein eigenes Profil ohne type muss trotzdem erscheinen"
    assert own[0].from_user
    assert "(" in own[0].title("eigenes"), "und es muss als eigenes erkennbar sein"


def test_the_title_says_it_in_words_not_in_a_symbol(slicer: Path) -> None:
    """Regel 18 und §4.1: ein Zeichen als Kennzeichnung liest sich nicht vor
    und überlebt nicht jeden Zeichensatz."""
    found = sp.find_profiles(slicer, "orca")
    plain = next(entry for entry in found if not entry.from_user)

    assert plain.title("eigenes") == plain.name
