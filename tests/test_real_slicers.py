"""Solidons Übergabe gegen echte, installierte Slicer — nicht gegen eine Attrappe.

Die übrige Suite ersetzt den Slicerlauf (``handover._run_slicer``) und fragt
die Maschine nicht (``_machine_stays_out_of_it`` in ``conftest.py``). Was sie
damit nicht sieht: ob das Programm unter Linux als AppImage oder Flatpak und
auf dem Mac als Bündel überhaupt anläuft, die geschriebenen Profile annimmt
und eine Druckdatei mit Druckbefehlen zurückgibt, die Solidon wieder liest.

Jeder Fall trägt ``@pytest.mark.slicer(<programm>)``; ``installed_slicer``
sucht das Programm wie die Anwendung. Ohne das Programm überspringt sich der
Fall, in ``.github/workflows/slicer-auswahl.yml`` ist er dann rot
(``SOLIDON_REQUIRE_SLICERS``). Der Workflow fährt diese Datei auf Linux,
Apple Silicon und Intel-Mac, sobald eine Änderung die Übergabe berührt
(``tools/ci_selection.py``); Windows deckt der lokale Lauf.
"""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
import trimesh

from app.core.export import appimage, cura_linux, handover, slicer_profiles
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.types import Profile, SceneObject
from tests.helpers import set_test_license

#: Je Programm ein Drucker, den sein Hersteller selbst führt — so läuft der
#: Fall den Weg, den ein Kunde mit diesem Slicer am ehesten geht.
PROGRAMS = {
    "orcaslicer": "creality-k1-max",
    "prusaslicer": "prusa-mk4s",
    "cura": "creality-ender3-v3-se",
    "bambustudio": "bambu-a1",
    "elegooslicer": "elegoo-neptune-4",
    "crealityprint": "creality-k1-max",
    "anycubicslicernext": "anycubic-kobra-2",
}

#: Eine Druckbewegung mit Vorschub: ``G1`` mit positivem ``E``-Wert, auch ``E.03``.
_EXTRUSION = re.compile(r"^G1 [^;\n]*\bE\.?\d", re.MULTILINE)


def _preselected(setup: handover.SlicerSetup, profile: Profile) -> handover.SlicerSetup:
    """Maschine, Prozess und Filament des Herstellers, wie der Druckdialog sie vorwählt.

    Die Vorwahl selbst (:func:`handover.standard_choice`), die auch Export und
    Hauptfenster ohne gemerkte Maschine nehmen (RM-623) — so läuft sie hier
    auf Linux und beiden Macs am echten Bestand. Dieselbe Wahl wie
    ``tools/matrix_unit.prepared`` (Stufe C): Die Orca-Familie und
    PrusaSlicer bekommen das Herstellerprofil ihres Bestands, Cura seine
    Druckerdefinition über die Übergabe selbst. Ohne diese Wahl lehnt die
    Orca-Familie den Prozess ab („process not compatible with printer“,
    Rückgabe -17).
    """
    if setup.flavour not in ("orca", "prusa"):
        return setup
    chosen = handover.standard_choice(setup, profile)
    assert chosen is not None, (
        f"kein Herstellerprofil für {profile.printer.id} bei {setup.executable}"
    )
    assert handover.machine_for(chosen, profile) == chosen.machine_profile, (
        f"{chosen.machine_profile} gehört nicht zu {profile.printer.id}"
    )
    return chosen


@pytest.mark.parametrize(
    ("program", "printer"),
    [
        pytest.param(program, printer, marks=pytest.mark.slicer(program), id=program)
        for program, printer in PROGRAMS.items()
    ],
)
def test_a_cube_comes_back_as_a_print_file_with_measured_figures(
    program: str,
    printer: str,
    installed_slicer: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein 20-mm-Würfel geht durch den echten Slicer und kommt gemessen zurück.

    Platte und Aufruf wie im Druckdialog (``_prepare_plate`` und der Aufruf aus
    ``_SliceWorker``, dasselbe Paar wie ``tools/matrix_unit.py``), nicht als
    nachgebaute STL-Übergabe.
    """
    from app.ui.print_settings_dialog import _PlateJob, _prepare_plate

    set_test_license(monkeypatch, active=True)
    raw = trimesh.creation.box((20.0, 20.0, 20.0))
    raw.apply_translation((0.0, 0.0, 10.0))
    cube = SceneObject("wuerfel", "Würfel", MeshData.of(raw))
    profile = profiles.make_profile(printer, "pla")
    settings = print_settings.resolve(profile)
    setup = _preselected(handover.detect(installed_slicer), profile)
    folder = tmp_path / "platte"
    folder.mkdir()
    job = _PlateJob(
        objects=(cube,),
        plates=(0,),
        folder=folder,
        name="wuerfel",
        setup=setup,
        settings=settings,
        profile=profile,
        slot_profiles={},
    )
    run = _prepare_plate(job, 0)

    outcome = handover.slice_model(
        [run.model],
        settings,
        profile,
        setup,
        output_dir=folder,
        timeout=600,
        keep_arrangement=run.keep_arrangement,
        slots=run.slots,
        model_height=run.model_height,
        model_meshes=run.meshes,
        expected_tools=run.used_tools,
    )

    text = outcome.gcode_path.read_text(encoding="utf-8", errors="replace")
    assert len(_EXTRUSION.findall(text)) > 100, f"kaum Druckbewegungen von {installed_slicer}"
    metrics = outcome.metrics
    assert metrics.source == "gcode"
    # Zwanzig Millimeter in Schichten von höchstens 0,4 mm sind mindestens 50.
    assert metrics.layer_count is not None and metrics.layer_count >= 50, metrics
    assert metrics.print_seconds is not None and metrics.print_seconds > 60, metrics
    assert metrics.filament_mm is not None and metrics.filament_mm > 100, metrics


@pytest.mark.parametrize(
    "program",
    [pytest.param(program, marks=pytest.mark.slicer(program), id=program) for program in PROGRAMS],
)
def test_every_installed_slicer_stays_on_offer(program: str, installed_slicer: Path) -> None:
    """„alle slicer bei linux und mac sollen dazu gehören“ (Robert, 08.10.2026).

    Die Slicerlisten zeigen nur noch, was ``tools.is_supported_slicer`` annimmt
    (RM-601). Hier gegen das Programm, wie die Suche es auf diesem Rechner
    findet: als AppImage, Flatpak oder Paket unter Linux, als Bündel auf dem
    Mac. Ein Unterstrich im AppImage-Namen hatte Bambu Studio dort aus der
    Familie geworfen.
    """
    from app.core import tools

    assert tools.is_supported_slicer(installed_slicer), installed_slicer
    assert handover.detect(installed_slicer).flavour != "other", installed_slicer


@pytest.mark.slicer("elegooslicer")
def test_an_adopted_twin_and_its_built_in_printer_share_the_machine(
    installed_slicer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eingebauter Centauri Carbon 2 im Projekt, derselbe aus dem Slicer übernommen (RM-600).

    Am echten Bestand: Die Übergabe nimmt die 0,4er Maschine des Herstellers,
    obwohl ein übernommener Drucker ihren Namen trägt.
    """
    machine = "Elegoo Centauri Carbon 2 0.4 nozzle"
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: machine)
    built_in = profiles.make_profile("centauri-carbon-2", "pla")
    profiles.save_printer(
        replace(built_in.printer, id="slicer-orca-twin", title=machine), slicer="elegooslicer"
    )
    setup = handover.detect(installed_slicer)

    assert handover.machine_for(setup, built_in) == machine
    assert handover.machine_missing(setup, built_in) == []


@pytest.mark.slicer("anycubicslicernext")
def test_a_related_device_never_hands_its_machine_to_the_smaller_printer(
    installed_slicer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Steht der Slicer auf dem Kobra 2 Max, bekommt ein Kobra-2-Projekt dessen Maschine nicht.

    Bis zum 08.10.2026 meinte „Anycubic Kobra 2" auch den Kobra 2 Max: Startcode
    und Bauraum des größeren gingen in die Datei des kleineren (RM-600, Review).
    """
    monkeypatch.setattr(
        slicer_profiles, "chosen_machine", lambda *_args: "Anycubic Kobra 2 Max 0.4 nozzle"
    )
    kobra = profiles.make_profile("anycubic-kobra-2", "pla")
    setup = handover.detect(installed_slicer)

    assert handover.machine_for(setup, kobra) == ""
    assert [finding.code for finding in handover.machine_missing(setup, kobra)] == [
        "slicer.machine_mismatch"
    ]


#: Die Orca-Familie, deren Linux-Fassung ein AppImage ist (RM-549).
ORCA_APPIMAGES = ("orcaslicer", "bambustudio", "elegooslicer", "crealityprint")


@pytest.mark.parametrize(
    "program",
    [
        pytest.param(program, marks=pytest.mark.slicer(program), id=program)
        for program in ORCA_APPIMAGES
    ],
)
def test_a_slicer_never_opened_offers_the_printers_of_its_maker(
    program: str,
    installed_slicer: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_testsuite_property: Callable[[str, object], None],
) -> None:
    """Frisch installiert, nie geöffnet: keine eigene Konfiguration, kein ``system/``.

    Trotzdem stehen die Drucker des Herstellers zur Wahl und die Maschine des
    Druckers aus :data:`PROGRAMS`. Unter Linux kommen sie aus dem Abbild des
    AppImage, das dafür nicht startet (Regel 11); bis RM-549 sah Solidon dort
    keinen Herstellerdrucker, bis der Slicer einmal gelaufen war. Wie lange die
    erste Kopie dort dauert, steht im Bericht des Laufs (``record_testsuite_property``;
    ``record_property`` verträgt der ``xunit2``-Bericht des Workflows nicht).
    """
    empty = tmp_path / "konfiguration"
    empty.mkdir()
    monkeypatch.setattr(slicer_profiles, "config_base", lambda _executable: str(empty))

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Zum Lesen der Profile startet kein Programm")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    found = slicer_profiles.discover_printers(installed_slicer, "orca")
    machine, _process = slicer_profiles.match(
        slicer_profiles.find_profiles(installed_slicer, "orca"),
        profiles.make_profile(PROGRAMS[program], "pla").printer,
    )

    assert len(found) >= 10, [printer.title for printer in found]
    assert machine is not None, PROGRAMS[program]
    if cura_linux.is_appimage(installed_slicer):
        root = slicer_profiles.install_root(installed_slicer)
        assert root is not None and root.is_relative_to(appimage.PROFILE_COPIES.root()), root
        started = time.perf_counter()
        count = appimage.copy_profiles(installed_slicer, tmp_path / "kopie")
        seconds = round(time.perf_counter() - started, 2)
        record_testsuite_property(f"{program}_profile", count)
        record_testsuite_property(f"{program}_kopie_sekunden", seconds)
        record_testsuite_property(f"{program}_drucker", len(found))


@pytest.mark.slicer("cura")
def test_curas_printers_are_read_from_its_appimage_without_starting_it(
    installed_slicer: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_testsuite_property: Callable[[str, object], None],
) -> None:
    """RM-599: Unter Linux liest Solidon Curas Drucker aus dem Abbild, mit leerem
    Cache und ohne einen Prozess zu starten; ob CuraEngine samt Lader darin
    vollständig ist, beantwortet dasselbe Lesen. Andernorts (Mac-Bündel) liegt der
    Bestand neben dem Programm, und der Fall prüft nur, dass er gelesen wird."""
    monkeypatch.setattr(cura_linux.PRINTER_COPIES, "root", lambda: tmp_path / "cache")
    monkeypatch.setattr(cura_linux.PRINTER_COPIES, "_kept", {})
    monkeypatch.setattr(cura_linux.PRINTER_COPIES, "_failed", {})

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Zum Lesen der Drucker startet kein Programm")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    started = time.perf_counter()
    root = slicer_profiles.install_root(installed_slicer)
    seconds = round(time.perf_counter() - started, 2)

    assert root is not None, installed_slicer
    assert (slicer_profiles.cura_resources(root) / "definitions" / "fdmprinter.def.json").is_file()
    if cura_linux.is_appimage(installed_slicer):
        assert root.is_relative_to(tmp_path / "cache"), root
        assert not cura_linux.engine_missing(installed_slicer)
        record_testsuite_property("cura_kopie_sekunden", seconds)
        record_testsuite_property(
            "cura_dateien", sum(1 for path in root.rglob("*") if path.is_file())
        )
