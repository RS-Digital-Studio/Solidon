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
from dataclasses import replace
from pathlib import Path

import pytest
import trimesh

from app.core.export import handover, slicer_profiles
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

    Dieselbe Wahl wie ``tools/matrix_unit.prepared`` (Stufe C): Die
    Orca-Familie und PrusaSlicer bekommen das Herstellerprofil ihres
    Bestands, Cura seine Druckerdefinition über die Übergabe selbst. Ohne
    diese Wahl lehnt die Orca-Familie den Prozess ab („process not compatible
    with printer“, Rückgabe -17).
    """
    if setup.flavour not in ("orca", "prusa"):
        return setup
    executable = setup.executable
    machine, process = slicer_profiles.match(
        list(slicer_profiles.find_profiles(executable, setup.flavour, ("machine", "process"))),
        profile.printer,
    )
    assert machine is not None, f"kein Herstellerprofil für {profile.printer.id} bei {executable}"
    roots = slicer_profiles.profile_roots(setup.flavour, executable)
    filament = slicer_profiles.match_filament(
        list(slicer_profiles.find_profiles(executable, setup.flavour, ("filament",))),
        machine,
        "PLA",
        roots,
    )
    return replace(
        setup,
        machine_profile=machine.name,
        base_process=process.name if process else "",
        base_filament=slicer_profiles.identity(filament) if filament else "",
    )


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


def _commands(path: Path) -> list[str]:
    """Was der Drucker aus einer Druckdatei ausführt: jede Zeile ohne Kommentar."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = (line.split(";", 1)[0].strip() for line in text.splitlines())
    return [line for line in lines if line]


@pytest.mark.slicer("prusaslicer")
def test_prusaslicer_estimates_a_printer_without_its_bundle_with_the_requested_acceleration(
    installed_slicer: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne Drucker seines Bündels schätzt PrusaSlicer, was die Datei fordert (RM-191).

    Den Centauri Carbon 2 führt kein Prusa-Bündel; die Übergabe schreibt
    Solidons Satz samt Maschine. Bis 0.5.3 schätzte PrusaSlicer dann mit
    seinen eingebauten 1500 mm/s², gleich was die Datei mit ``M204 S``
    verlangte. Der Kontrollfall ist derselbe Würfel mit den Schätzwerten von
    0.5.3 (``machine_limits_usage = ignore``, kein Dialekt): Die Druckbefehle
    bleiben dieselben, nur die Schätzung sinkt (PrusaSlicer 2.9.6 unter
    Windows, 09.10.2026: 891 gegen 1008 s). Grenzen gehen keine in die
    Druckdatei, die Firmware behält ihre, und die Beschleunigung steht als
    ``M204 S`` darin, das Marlin und Klipper lesen — ``M204 P`` ohne ``T``
    übergeht Klipper.
    """
    from app.ui.print_settings_dialog import _PlateJob, _prepare_plate

    set_test_license(monkeypatch, active=True)
    raw = trimesh.creation.box((20.0, 20.0, 20.0))
    raw.apply_translation((0.0, 0.0, 10.0))
    cube = SceneObject("wuerfel", "Würfel", MeshData.of(raw))
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    setup = handover.detect(installed_slicer)

    def sliced(name: str) -> handover.SliceOutcome:
        folder = tmp_path / name
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
        return handover.slice_model(
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

    requested = sliced("angefordert")
    # Ohne Ersatz, falls es die Funktion nicht gibt: Dann schätzen beide Läufe
    # gleich, und der Vergleich unten wird rot.
    monkeypatch.setattr(
        handover,
        "_prusa_time_estimate",
        lambda _written: {"machine_limits_usage": "ignore"},
        raising=False,
    )
    built_in = sliced("eingebaut")

    commands = _commands(requested.gcode_path)
    assert f"M204 S{settings.speed.acceleration:g}" in commands
    limits = ("M201", "M203", "M205", "M204 P", "M204 T")
    assert not [line for line in commands if line.startswith(limits)]
    assert commands == _commands(built_in.gcode_path), "derselbe Druck"
    assert requested.metrics.print_seconds is not None
    assert built_in.metrics.print_seconds is not None
    assert requested.metrics.print_seconds < built_in.metrics.print_seconds


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
