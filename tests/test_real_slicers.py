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

import math
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
import trimesh

from app.core.export import appimage, cura_linux, handover, slicer_keys, slicer_profiles
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.types import Profile, SceneObject
from tests.gcode_contact import support_contact
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


#: Die Orca-Familie: Wandzahl der Bäume und Hybrid je Objekt gehen dort ans
#: Programm (RM-584).
ORCA_FAMILY = ("orcaslicer", "bambustudio", "elegooslicer", "crealityprint", "anycubicslicernext")


def _tower_with_island() -> SceneObject:
    """Ein Turm von 40 mm mit einer Insel auf 35 mm daneben, die ein Baum vom Bett
    trägt. Die Wandzahl ist gesetzt, nicht vorgeschlagen; ob das Programm sie
    liest, zeigt auch ein kurzer Baum, und der hohe kostete am ElegooSlicer
    vier Minuten je Lauf."""
    tower = trimesh.creation.box(extents=(10.0, 10.0, 40.0))
    tower.apply_translation((0.0, 0.0, 20.0))
    island = trimesh.creation.box(extents=(6.0, 6.0, 4.0))
    island.apply_translation((20.0, 0.0, 37.0))
    return SceneObject("turm", "Turm", MeshData.of(trimesh.util.concatenate([tower, island])))


def _moves(gcode: Path) -> list[str]:
    """Die Bewegungen einer Druckdatei, ohne Kopf, Zeiten und Konfigurationsblock."""
    return [
        line
        for line in gcode.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith(("G0 ", "G1 ", "G2 ", "G3 "))
    ]


#: Wo die Kegel unter der Platte hängen, 11 mm auseinander.
_CONES: tuple[tuple[float, float], ...] = (
    (-11.0, -11.0),
    (-11.0, 0.0),
    (-11.0, 11.0),
    (11.0, -11.0),
    (11.0, 0.0),
    (11.0, 11.0),
)


def _bearded_plate() -> SceneObject:
    """Eine Platte auf einer Säule, darunter sechs Kegel, die mit der Spitze nach
    unten als Inseln unter ``analysis.TIP_ROOF_AREA`` beginnen — die Bartstacheln
    des Drachen im Kleinen (RM-704). Stifte gleichen Querschnitts zeigen es nicht:
    Unter ihnen legte ElegooSlicer auch mit 0,8 mm Spitze eine Trennschicht."""
    column = trimesh.creation.box(extents=(8.0, 8.0, 20.0))
    column.apply_translation((0.0, 0.0, 10.0))
    plate = trimesh.creation.box(extents=(30.0, 30.0, 3.0))
    plate.apply_translation((0.0, 0.0, 21.5))
    upside_down = trimesh.transformations.rotation_matrix(math.pi, (1.0, 0.0, 0.0))
    cones = []
    for x, y in _CONES:
        cone = trimesh.creation.cone(radius=1.0, height=4.0, sections=24)
        cone.apply_transform(upside_down)
        cone.apply_translation((x, y, 20.0))
        cones.append(cone)
    body = trimesh.util.concatenate([column, plate, *cones])
    return SceneObject("bart", "Bart", MeshData.of(body))


def _sliced_tower(
    printer: str,
    program: Path,
    folder: Path,
    chosen: dict[str, object],
    accepted: dict[str, object] | None = None,
    body: SceneObject | None = None,
) -> tuple[list[str], Path]:
    """Den Turm (oder ``body``) durch das echte Programm, wie der Druckdialog ihn
    schickt: Bewegungen der Druckdatei und die geschriebene Platte."""
    moves, model, _gcode = _sliced(printer, program, folder, chosen, accepted, body)
    return moves, model


def _sliced(
    printer: str,
    program: Path,
    folder: Path,
    chosen: dict[str, object],
    accepted: dict[str, object] | None = None,
    body: SceneObject | None = None,
) -> tuple[list[str], Path, Path]:
    """:func:`_sliced_tower` samt Druckdatei."""
    from app.ui.print_settings_dialog import _PlateJob, _prepare_plate

    profile = profiles.make_profile(printer, "pla")
    settings = print_settings.resolve(profile)
    for path, value in chosen.items():
        settings = print_settings.with_choice(settings, path, value)
    for path, value in (accepted or {}).items():
        settings = print_settings.with_accepted(settings, path, value)
    setup = _preselected(handover.detect(program), profile)
    folder.mkdir(parents=True)
    job = _PlateJob(
        objects=(body or _tower_with_island(),),
        plates=(0,),
        folder=folder,
        name="turm",
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
        timeout=900,
        keep_arrangement=run.keep_arrangement,
        slots=run.slots,
        model_height=run.model_height,
        model_meshes=run.meshes,
        expected_tools=run.used_tools,
    )
    return _moves(outcome.gcode_path), run.model, outcome.gcode_path


#: Die Art einer Bahn: ``;TYPE:`` in der Orca-Familie, ``; FEATURE:`` bei Bambu Studio.
_KIND = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$")
#: Lage einer Bewegung.
_AXIS = re.compile(r"\b([XYZ])(-?\d*\.?\d+)")


def _support_below(gcode: Path, below: float) -> dict[str, list[tuple[float, float, float]]]:
    """Die Druckbewegungen der Stütze (``support``) und ihrer Trennschicht
    (``interface``) unter der Höhe ``below``, je Endpunkt ``(x, y, z)`` — unter den
    Kegeln, nicht unter der Platte —, dazu die des Modells darüber (``model``)."""
    found: dict[str, list[tuple[float, float, float]]] = {
        "support": [],
        "interface": [],
        "model": [],
    }
    kind = ""
    x = y = z = 0.0
    for line in gcode.read_text(encoding="utf-8", errors="replace").splitlines():
        named = _KIND.match(line)
        if named:
            kind = named.group(1).lower()
            continue
        if not line.startswith(("G0 ", "G1 ")):
            continue
        values = dict(_AXIS.findall(line.split(";", 1)[0]))
        x = float(values.get("X", x))
        y = float(values.get("Y", y))
        z = float(values.get("Z", z))
        if not _EXTRUSION.match(line):
            continue
        if z >= below:
            if kind and not kind.startswith(("support", "skirt", "brim", "custom", "prime")):
                found["model"].append((x, y, z))
        elif kind.startswith("support"):
            found["interface" if "interface" in kind else "support"].append((x, y, z))
    return found


def _cones_without(found: dict[str, list[tuple[float, float, float]]], reach: float) -> list:
    """Die Kegel aus :data:`_CONES`, unter denen keine Trennschicht näher als
    ``reach`` mm liegt. Die Mitte des Körpers auf dem Bett ist die Mitte der
    Platte, aus den Modellbahnen darüber."""
    xs = [point[0] for point in found["model"]]
    ys = [point[1] for point in found["model"]]
    middle = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
    return [
        (x, y)
        for x, y in _CONES
        if not any(
            math.hypot(px - middle[0] - x, py - middle[1] - y) <= reach
            for px, py, _pz in found["interface"]
        )
    ]


@pytest.mark.parametrize(
    "program",
    [
        pytest.param(program, marks=pytest.mark.slicer(program), id=program)
        for program in ORCA_FAMILY
    ],
)
def test_a_roof_tip_puts_an_interface_under_every_cone(
    program: str,
    installed_slicer: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Eine Baumspitze über ``analysis.TIP_ROOF_AREA`` Querschnitt erzwingt in der
    Orca-Familie die Trennschicht an jeder Spitze (``force_tip_to_roof``, RM-704):
    Unter sechs Kegelspitzen mit 0,4 mm Luft steht mit ``ROOF_TIP_DIAMETER`` unter
    jedem Kegel eine Trennschicht, mit der Spitze von 0,8 mm keine. Solidon schreibt die
    Wahl in jedem Programm; Bambu Studio meldet sie als übergangen
    (``slicer.setting_ignored``), Creality Print liest sie und baut andere Äste;
    beide drucken dieselbe Trennschicht, und dort kommt kein Rat
    (``slicer_keys.NOT_TAKEN_BY_PROGRAM``)."""
    from app.core.slice import advise

    set_test_license(monkeypatch, active=True)
    printer = PROGRAMS[program]

    def cut(tip: float, folder: str) -> dict[str, list[tuple[float, float, float]]]:
        gcode = _sliced(
            printer,
            installed_slicer,
            tmp_path / folder,
            {
                "support.style": "tree",
                "support.z_gap": 0.4,
                "support.interface_layers": 2,
                "support.tip_diameter": tip,
            },
            body=_bearded_plate(),
        )[2]
        # Die Kegel beginnen auf 16 mm, die Platte auf 20 mm.
        return _support_below(gcode, below=19.0)

    roof, plain = cut(advise.ROOF_TIP_DIAMETER, "spitze"), cut(0.8, "vorgabe")
    assert plain["support"] and roof["support"], f"{program} stützt die Kegel nicht"
    if slicer_keys.takes("orca", "support.tip_diameter", program=program):
        assert not _cones_without(roof, reach=2.0), (program, _cones_without(roof, reach=2.0))
        assert not plain["interface"], program
    else:
        # Verglichen ohne Reihenfolge: Bambu legt gleiche Bahnen je Lauf anders an.
        assert sorted(roof["interface"]) == sorted(plain["interface"]), program
        if program == "bambustudio":
            # Bambu meldet den Schlüssel selbst als übergangen. Gleiche Stützbahnen
            # lassen sich nicht zusichern: Bambu legt die Platte von Lauf zu Lauf an
            # 19 und 19 Punkten anders an, auch zweimal mit 0,8 mm.
            assert "tree_support_tip_diameter" in caplog.text, program


@pytest.mark.parametrize(
    ("program", "printer"),
    [
        pytest.param(program, PROGRAMS[program], marks=pytest.mark.slicer(program), id=program)
        for program in ORCA_FAMILY
    ]
    # Elegoos Prozess für den Centauri Carbon 2 füllt seine Bäume.
    + [
        pytest.param(
            "elegooslicer",
            "centauri-carbon-2",
            marks=pytest.mark.slicer("elegooslicer"),
            id="elegooslicer-cc2",
        )
    ],
)
def test_tree_walls_change_the_print_only_where_the_program_reads_them(
    program: str,
    printer: str,
    installed_slicer: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zwei Wände für hohe Bäume (RM-584) ändern die Druckdatei unter Hybrid. Unter
    gefüllten organischen Bäumen liest ElegooSlicer die Wandzahl nicht — derselbe
    G-Code mit einer und zwei Wänden am Centauri Carbon 2 —, unter hohlen
    (``handover.hollow_trees``, Neptune 4) schon. Was jedes Programm davon tut,
    steht in ``slicer_keys.IGNORED_UNDER_TREES_BY_PROGRAM``. Der Fall hält die
    Tabelle gegen das Programm; Bambu Studio und Creality Print lesen die
    Wandzahl auch unter ihren Bäumen und fehlen dort."""
    set_test_license(monkeypatch, active=True)
    profile = profiles.make_profile(printer, "pla")
    setup = _preselected(handover.detect(installed_slicer), profile)
    organic = handover.organic_styles(setup, profile)
    for style in ("hybrid", "tree"):
        moves = {
            walls: _sliced_tower(
                printer,
                installed_slicer,
                tmp_path / f"{style}-{walls}",
                {
                    "support.style": style,
                    "support.placement": "build_plate",
                    "support.tree_walls": walls,
                },
            )[0]
            for walls in (1, 2)
        }
        assert len(moves[1]) > 1000, f"{program} druckt den Turm nicht"
        ignored = "support.tree_walls" in handover.ignored_under_trees(
            style, organic, program, hollow=handover.hollow_trees(setup)
        )
        assert (moves[1] == moves[2]) is ignored, (
            f"{program}, {style}: Wände {'überlesen' if moves[1] == moves[2] else 'gedruckt'}, "
            f"die Tabelle sagt {'überlesen' if ignored else 'gedruckt'}"
        )


@pytest.mark.slicer("elegooslicer")
def test_hollow_trees_round_the_gap_like_organic_ones(
    installed_slicer: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hohle Bäume (``handover.hollow_trees``, Neptune 4) lesen ihre Wandzahl, liegen
    aber wie organische auf den Schichten des Modells (RM-584, Nachprüfung):
    0,28 mm Abstand oben bei 0,2 mm Schicht druckt wie 0,2 mm, 0,4 mm anders.
    Der Rat rechnet dort in ganzen Schichten (``organic_styles``)."""
    set_test_license(monkeypatch, active=True)
    printer = PROGRAMS["elegooslicer"]
    profile = profiles.make_profile(printer, "pla")
    setup = _preselected(handover.detect(installed_slicer), profile)
    assert handover.hollow_trees(setup), "der Prozess des Neptune 4 druckt Bäume hohl"
    assert "tree" in handover.organic_styles(setup, profile)
    moves = {
        gap: _sliced_tower(
            printer,
            installed_slicer,
            tmp_path / str(gap),
            {"support.style": "tree", "support.placement": "build_plate", "support.z_gap": gap},
        )[0]
        for gap in (0.2, 0.28, 0.4)
    }
    assert moves[0.28] == moves[0.2], "0,28 mm rundet auf eine Schicht"
    assert moves[0.4] != moves[0.2], "zwei Schichten Abstand drucken anders"


@pytest.mark.parametrize(
    "program",
    [
        pytest.param(program, marks=pytest.mark.slicer(program), id=program)
        for program in ORCA_FAMILY
    ],
)
def test_hybrid_for_one_part_reaches_the_program_as_tree_hybrid(
    program: str, installed_slicer: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verlangt ein Teil Hybrid, bekommt es ``tree_hybrid`` als Objektwert (RM-584),
    und das Programm druckt es anders als denselben Turm mit Baum je Objekt — sonst
    hätte es den Stil der Platte genommen."""
    from app.core.export import writer
    from app.core.types import SettingAdvice
    from tests.helpers import object_values

    set_test_license(monkeypatch, active=True)
    moves: dict[str, list[str]] = {}
    for style in ("tree", "hybrid"):
        # Der Rat des Teils ist hier gesetzt, nicht gerechnet: Gefragt ist die
        # Übergabe je Objekt, nicht die Deckenform des Turms.
        own = [SettingAdvice("support.style", style, "none", "Probe")]
        monkeypatch.setattr(writer, "part_advice", lambda *_args, own=own, **_kwargs: own)
        moves[style], model = _sliced_tower(
            PROGRAMS[program],
            installed_slicer,
            tmp_path / style,
            {"support.placement": "build_plate"},
            accepted={"support.style": style},
        )
        written = object_values(model, "Metadata/model_settings.config")["Turm"]
        assert written.get("support_type") == "tree(auto)", written
        assert (written.get("support_style") == "tree_hybrid") is (style == "hybrid"), written
    assert moves["tree"] != moves["hybrid"], f"{program} druckt Hybrid je Objekt wie den Baum"


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


def _contact_gcode(relative: bool, resets: bool) -> str:
    """Eine Platte über einer Säule als G-Code: Modell auf jeder Ebene in einer
    eigenen Zelle (Säule), Trennschicht auf 0,6 mm und das Dach auf 1,0 mm über
    derselben Zelle. Relativ, absolut oder absolut mit ``G92 E0`` je Ebene."""
    lines = ["M83" if relative else "M82"]
    e = 0.0

    def move(x: float, y: float, z: float) -> str:
        nonlocal e
        e += 0.05
        return f"G1 X{x} Y{y} Z{z} E{0.05 if relative else round(e, 5)}"

    for level, kinds in (
        (0.2, ("Outer wall",)),
        (0.4, ("Outer wall",)),
        (0.6, ("Outer wall", "Support interface")),
        (0.8, ("Outer wall",)),
        (1.0, ("Outer wall", "Top surface")),
    ):
        if resets and not relative:
            lines.append("G92 E0")
            e = 0.0
        for kind in kinds:
            lines.append(f";TYPE:{kind}")
            if kind == "Outer wall":
                lines += ["G0 X50 Y50", move(51.0, 50.0, level)]
            else:
                lines += ["G0 X10 Y10", move(11.0, 10.0, level), move(11.0, 11.0, level)]
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize(("relative", "resets"), [(True, False), (False, False), (False, True)])
def test_the_contact_measure_counts_extrusion_as_the_printer_does(
    relative: bool, resets: bool
) -> None:
    """Dieselbe Bahn misst gleich, relativ, absolut und mit ``G92 E0`` (RM-624).

    Die historischen Messleser kannten ``G92`` nicht: Nach dem Rücksetzen galt
    jede Bahn als Leerfahrt, und unter absoluten Werten fehlten Kontakte.
    """
    measured = support_contact(_contact_gcode(relative, resets))

    assert measured.top_cells > 0, "die Messung findet den Kontakt"
    assert measured.top_gap == pytest.approx(0.2)
    assert measured.top_interface_layers == pytest.approx(1.0)


def _wall(levels: tuple[float, ...]) -> list[str]:
    """Eine Wand in einer eigenen Zelle, je Ebene ein Strich: Sie gibt dem Modell
    seine Schichthöhe von 0,2 mm."""
    lines = [";TYPE:Outer wall"]
    for level in levels:
        lines += [f"G0 X50 Y50 Z{level}", "G1 X51 Y50 E0.05"]
    return lines


def test_the_contact_measure_follows_arcs() -> None:
    """Ein Bogen zählt entlang seiner Bahn und führt die Position nach (RM-624).

    Bambu Studio und PrusaSlicer biegen Wände und Bäume in ``G2``/``G3`` —
    zehntausende Bögen je Baumdruck. Das Dach hier ist ein ``G3`` um (11; 11,5):
    Es überspannt die Trennschicht bei (11; 7), seine Sehne nicht. Danach geht es
    gerade weiter; vom Punkt vor dem Bogen aus liefe diese Bahn über die Falle bei
    (13; 11), eine Trennschicht eine Ebene tiefer, die 0,4 statt 0,2 mm mäße.
    Übergangene Bögen und Bögen als Sehne treffen die Falle, eine nicht
    nachgeführte Position zählt zwei Zellen.
    """
    text = "\n".join(
        [
            "M83",
            *_wall((0.2, 0.4, 0.6, 0.8, 1.0)),
            ";TYPE:Support interface",
            "G0 X10.5 Y6.5 Z0.6",
            "G1 X11.5 Y7.5 E0.05",
            "G0 X12.5 Y10.5 Z0.4",
            "G1 X13.5 Y11.5 E0.05",
            ";TYPE:Top surface",
            "G0 X6 Y11.5 Z1.0",
            "G3 X16 Y11.5 I5 J0 E0.8",
            "G1 X17 Y11.5 E0.05",
        ]
    )

    measured = support_contact(text + "\n")

    assert measured.top_cells == 1, measured
    assert measured.top_gap == pytest.approx(0.2), measured


@pytest.mark.parametrize("marked", [True, False], ids=["bahnhoehe", "ohne-bahnhoehe"])
def test_the_contact_measure_takes_the_support_height_from_its_own_stack(marked: bool) -> None:
    """Die Unterseite misst mit der Höhe der eigenen Stützbahn (RM-624).

    Auf einem Sockel bis 0,6 mm steht Stütze mit 0,28 mm Luft. Mit ``;HEIGHT:``
    wie die Orca-Familie und PrusaSlicer hat die unterste Stützlage ihre eigene
    Höhe, wie in den echten G-Codes unter Gitter: 0,2 mm auf 1,08, darüber
    0,28. Der Schritt im Stapel mäße dort 0,2 mm Luft — die Angabe muss gelesen
    werden. Ohne Angabe wie CuraEngine ist der Stapel gleichförmig (1,16, 1,44,
    1,72), und der Schritt gilt. Daneben eine Säule auf dem Bett mit Ebenen
    alle 0,28 mm: Aus allen Stützebenen zusammen gerechnet läge unter der
    untersten Lage eine fremde auf 1,12 bzw. 0,84 mm, und die Unterseite mäße
    0,52 bzw. 0,24. Dazu eine Zelle, in der Wand und Trennschicht nebeneinander
    stehen und ihre Ebenen sich abwechseln: weder oben noch unten Kontakt.
    """
    height = [";HEIGHT:0.28"] if marked else []
    lines = ["M83", *_wall((0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6))]
    for level in (0.2, 0.4, 0.6):
        lines += [";TYPE:Top surface", f"G0 X10.5 Y10.5 Z{level}", "G1 X11.5 Y11.5 E0.05"]
    stack = (
        (
            ("Support interface", 1.08, 0.2),
            ("Support interface", 1.36, 0.28),
            ("Support", 1.64, 0.28),
        )
        if marked
        else (
            ("Support interface", 1.16, None),
            ("Support interface", 1.44, None),
            ("Support", 1.72, None),
        )
    )
    for kind, level, own in stack:
        tall = [] if own is None else [f";HEIGHT:{own}"]
        lines += [f";TYPE:{kind}", *tall, f"G0 X10.5 Y10.5 Z{level}", "G1 X11.5 Y11.5 E0.05"]
    for level in (0.28, 0.56, 0.84, 1.12, 1.4):
        lines += [";TYPE:Support", *height, f"G0 X30.5 Y30.5 Z{level}", "G1 X31.5 Y31.5 E0.05"]
    for level in (0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6):
        lines += [";TYPE:Inner wall", f"G0 X20.5 Y20.5 Z{level}", "G1 X21.5 Y21.5 E0.05"]
    for level in (0.28, 0.56, 0.84, 1.12, 1.4):
        lines += [
            ";TYPE:Support interface",
            *height,
            f"G0 X20.5 Y20.5 Z{level}",
            "G1 X21.5 Y21.5 E0.05",
        ]

    measured = support_contact("\n".join(lines) + "\n")

    assert measured.bottom_cells == 1, measured
    assert measured.bottom_gap == pytest.approx(0.28), measured
    assert measured.bottom_interface_layers == pytest.approx(2.0), measured
    assert measured.top_cells == 0, measured


def test_the_contact_measure_keeps_to_the_inside_of_the_model() -> None:
    """``inset`` nimmt nur das Innere der Aufsicht, und ein Rand gehört nicht dazu (RM-624).

    Ein Dach von 10 × 10 mm über zwei Trennschichtflecken, einer am Rand, einer
    in der Mitte; vier Millimeter Abstand lassen nur die Mitte. Außen um das
    Dach liegt ein Rand, wie PrusaSlicer ihn schreibt (``;TYPE:Skirt/Brim``),
    nicht unter den Flecken: Als Modell gezählt, verbreiterte er die Aufsicht,
    und der Fleck am Rand zählte mit.
    """
    lines = ["M83", *_wall((0.2, 0.4, 0.6, 0.8, 1.0)), ";TYPE:Skirt/Brim"]
    for row in (7, 9, 21, 23):
        lines += [f"G0 X6.5 Y{row} Z0.2", f"G1 X23.5 Y{row} E0.5"]
    for column in (6.5, 8.5, 20.5, 22.5):
        lines += [f"G0 X{column} Y7 Z0.2", f"G1 X{column} Y23 E0.5"]
    lines += [";TYPE:Support interface"]
    for x in (10.5, 14.5):
        lines += [f"G0 X{x} Y14.5 Z0.6", f"G1 X{x + 1} Y15.5 E0.05"]
    lines += [";TYPE:Top surface"]
    for row in range(11, 20, 2):
        lines += [f"G0 X10.5 Y{row} Z1.0", f"G1 X19.5 Y{row} E0.5"]

    everywhere = support_contact("\n".join(lines) + "\n")
    inside = support_contact("\n".join(lines) + "\n", inset=4.0)

    assert everywhere.top_cells == 2, everywhere
    assert inside.top_cells == 1, inside


#: Was RM-622 an den Programmen gemessen hat und Solidons Tabellen behaupten
#: (``advise.rounds_to_whole_layers``, ``slicer_keys.IGNORED_UNDER_TREES_BY_PROGRAM``).
_CONTACT_PROGRAMS = (
    "elegooslicer",
    "orcaslicer",
    "bambustudio",
    "crealityprint",
    "anycubicslicernext",
    "prusaslicer",
)


@pytest.mark.parametrize("style", ["grid", "tree"])
@pytest.mark.parametrize(
    ("program", "printer"),
    [
        pytest.param(program, PROGRAMS[program], marks=pytest.mark.slicer(program), id=program)
        for program in _CONTACT_PROGRAMS
    ],
)
def test_the_support_contact_arrives_as_solidon_says(
    program: str,
    printer: str,
    style: str,
    installed_slicer: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Abstand und untere Trennschicht kommen an, wie Solidons Tabellen sagen (RM-624).

    Eine Platte über einer Säule auf einem Sockel, PETG bei 0,2-mm-Schichten.
    Unter Gitter gilt der Abstand (eigene Stützebenen), oben wie unten, mit
    unteren Trennschichten. Unter organischen Bäumen rundet das Programm auf die
    Schichten des Modells (RM-622), und Bambu Studio, Creality Print, Anycubic
    Slicer Next und PrusaSlicer drucken dort keine untere Trennschicht. Ändert
    ein neuer Slicerstand eine dieser Eigenschaften, wird der Test rot, und die
    Tabelle zieht nach.

    Kein Wert ist der des Herstellers — sonst bliebe ein verlorener Wert grün:
    Die gewählten Prozesse führen 0,2 mm Abstand (Anycubic 0,1) und zwei untere
    Trennschichten (PrusaSlicer 0, Anycubic „wie oben“). Unter Gitter 0,28 mm.
    Unter Bäumen 0,44 mm, 2,2 Schichten: Ob ein Programm rundet oder abschneidet,
    es druckt 0,4. Cura steht nicht in der Liste: Es rundet auf (unter Gitter
    unten 0,40, unter Bäumen 0,60), während ``rounds_to_whole_layers`` ganze
    Schichten zur nächsten annimmt. Das richtet RM-628, und Cura kommt mit ihm
    hierher.
    """
    from app.core.slice import advise
    from app.ui.print_settings_dialog import _PlateJob, _prepare_plate

    set_test_license(monkeypatch, active=True)
    parts = []
    for side, height, z in ((36.0, 3.0, 1.5), (8.0, 10.2, 8.0), (36.0, 2.0, 14.0)):
        part = trimesh.creation.box((side, side, height))
        part.apply_translation((0.0, 0.0, z))
        parts.append(part)
    body = SceneObject("stufe", "Stufe", MeshData.of(trimesh.boolean.union(parts)))
    profile = profiles.make_profile(printer, "petg")
    settings = print_settings.resolve(profile)
    layer = 0.2
    gap = 0.44 if style == "tree" else 0.28
    bottom_layers = 3
    for path, value in (
        ("layers.layer_height", layer),
        ("support.style", style),
        ("support.placement", "everywhere"),
        ("support.z_gap", gap),
        ("support.interface_layers", 2),
        ("support.bottom_interface_layers", bottom_layers),
    ):
        settings = print_settings.with_choice(settings, path, value)
    setup = _preselected(handover.detect(installed_slicer), profile)
    folder = tmp_path / "platte"
    folder.mkdir()
    job = _PlateJob(
        objects=(body,),
        plates=(0,),
        folder=folder,
        name="stufe",
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
    # Vier Millimeter vom Rand: Dort teilen sich Sockelwand und die Stütze
    # daneben, die auf dem Bett steht, eine Rasterzelle.
    measured = support_contact(
        outcome.gcode_path.read_text(encoding="utf-8", errors="replace"), inset=4.0
    )

    organic = handover.organic_styles(setup, profile)
    # In ganzen Schichten: 0,44 mm werden gerundet wie abgeschnitten 0,4.
    rounds = advise.rounds_to_whole_layers(setup.flavour, style=style, organic=organic)
    printed = round(gap / layer) * layer if rounds else gap
    # Ohne Zellen sagt ein Median nichts, und eine Zusicherung über eine leere
    # Menge bliebe grün (hier 57 bis 201 Zellen je Seite).
    assert measured.top_cells > 20, f"kaum Kontakt unter der Platte: {measured}"
    assert measured.bottom_cells > 20, f"kaum Stütze auf dem Sockel: {measured}"
    assert measured.top_gap == pytest.approx(printed, abs=0.02), measured
    assert measured.bottom_gap == pytest.approx(printed, abs=0.02), measured
    skipped = handover.ignored_under_trees(style, organic, slicer_keys.program_of(setup.executable))
    if "support.bottom_interface_layers" in skipped:
        layers = 0
    elif style == "grid" and setup.flavour == "orca":
        # Unter Gitter legt die Orca-Familie die Kontaktlage dazu (``SupportCommon.cpp``,
        # ``slicer_keys``). Genau gezählt: Mit ihrem Standard 2 druckte sie auch drei.
        layers = bottom_layers + 1
    else:
        layers = bottom_layers
    assert measured.bottom_interface_layers == layers, f"untere Trennschicht: {measured}"


# --- Kein doppelter Ausgleich (RM-589) -------------------------------------------

#: Die Außenwand in den drei Schreibweisen: Orca-Familie, PrusaSlicer, Cura.
_OUTER_WALL = frozenset({"outer wall", "external perimeter", "wall-outer"})
_WORD = re.compile(r"([GXYZE])(-?\d*\.?\d+)")
#: Wo ein Objekt beginnt: Orca-Familie mit Namen oder Kennung (Bambu Studio),
#: PrusaSlicer über ``M486``, CuraEngine je Netz.
_OBJECT = re.compile(
    r"^(?:; printing object (.+?)(?: id:\d+ copy \d+)?$"
    r"|; start printing object, unique label id: (\d+)"
    r"|M486 S(\d+)|;MESH:(.+))"
)


def _outer_walls(gcode: str) -> dict[tuple[str, float], list[tuple[float, float]]]:
    """Die Punkte der Außenwand je Objekt und Schichthöhe — Endpunkte jeder Bahn mit Vorschub.

    Ein Bogen (``G2``/``G3``) endet wie eine Gerade auf seiner Bahn; für den
    mittleren Abstand zur Lochmitte genügen die Endpunkte. Die Bahnart steht
    als ``;TYPE:``, bei Bambu Studio als ``; FEATURE:``.
    """
    walls: dict[tuple[str, float], list[tuple[float, float]]] = {}
    x = y = z = e = 0.0
    relative = False
    kind = owner = ""
    for raw in gcode.splitlines():
        line = raw.strip()
        found = _OBJECT.match(line)
        if found:
            owner = next(group for group in found.groups() if group)
            continue
        if line.startswith((";TYPE:", "; FEATURE:")):
            kind = line.split(":", 1)[1].strip().lower()
            continue
        code = line.split(";", 1)[0].strip()
        if not code:
            continue
        head = code.split()[0]
        if head in ("M82", "M83"):
            relative = head == "M83"
            continue
        words = {key: float(value) for key, value in _WORD.findall(code)}
        if head == "G92":
            e = words.get("E", e)
            continue
        if head not in ("G0", "G1", "G2", "G3"):
            continue
        end = (words.get("X", x), words.get("Y", y), words.get("Z", z))
        fed = False
        if "E" in words:
            fed = words["E"] > 1e-6 if relative else words["E"] > e + 1e-6
            e = e if relative else words["E"]
        if fed and head != "G0" and kind in _OUTER_WALL:
            walls.setdefault((owner, round(end[2], 3)), []).extend([(x, y), (end[0], end[1])])
        x, y, z = end
    return walls


def _plate_figures(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Breite der äußeren Bahn und Durchmesser der Lochbahn einer Bohrplatte."""
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    centre = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
    hole = [
        math.hypot(px - centre[0], py - centre[1])
        for px, py in points
        if math.hypot(px - centre[0], py - centre[1]) < 6.0
    ]
    return max(xs) - min(xs), 2.0 * sum(hole) / len(hole)


@pytest.mark.parametrize(
    ("program", "printer"),
    [
        pytest.param(program, printer, marks=pytest.mark.slicer(program), id=program)
        for program, printer in PROGRAMS.items()
    ],
)
def test_a_part_that_compensates_itself_is_not_compensated_again(
    program: str,
    printer: str,
    installed_slicer: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zwei gleiche Bohrplatten, eine trägt ihren Ausgleich schon im Modell (RM-589).

    Platte A ist mit Materialzugabe gebohrt (Ø 6 + 0,2 mm PETG) und um den
    Elefantenfuß eingezogen, Platte B gleich weit gebohrt, aber ohne beides.
    Die Platte des Slicers weitet Löcher um 0,1 mm und zieht die erste Schicht
    um 0,15 mm ein, je Seite (eigene Wahl). Übernommen stellt der Rat bei A
    beides auf null, als Objektwert — gemessen im G-Code: Das Loch von A ist
    0,2 mm enger als das von B, und die erste Schicht von A ist gegenüber der
    zweiten um 0,3 mm weniger eingezogen als bei B.
    """
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.fits import allowances_for
    from app.core.slice import advise
    from app.core.types import Document
    from app.ui.print_settings_dialog import _PlateJob, _prepare_plate

    set_test_license(monkeypatch, active=True)
    profile = profiles.make_profile(printer, "petg")
    document = Document(format_version=1, app_version="0.0.1", printer=printer, material="petg")
    history = History(document)
    for x, name in ((-30.0, "A"), (30.0, "B")):
        history.apply(
            name,
            [
                OperationDraft(
                    op="create_box",
                    params={"width": 40.0, "depth": 40.0, "height": 8.0, "x": x, "name": name},
                )
            ],
        )
    nominal = 6.0 + profile.material.hole_compensation
    history.apply(
        "Bohrung A",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 6.0, "x": -30.0, "y": 0.0, "z": 4.0, "axis": "z"},
            )
        ],
    )
    history.apply(
        "Bohrung B",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_2",),
                params={
                    "diameter": nominal,
                    "x": 30.0,
                    "y": 0.0,
                    "z": 4.0,
                    "axis": "z",
                    "compensate": False,
                },
            )
        ],
    )
    history.apply(
        "Fuß A", [OperationDraft(op="compensate_first_layer", inputs=("obj_1",), params={})]
    )
    scene = evaluate(document, profile).scene
    assert allowances_for(document, scene.objects["obj_1"]) == ("holes", "foot")
    assert allowances_for(document, scene.objects["obj_2"]) == ()

    setup = _preselected(handover.detect(installed_slicer), profile)
    from app.core.export import manufacturer

    settings = manufacturer.effective(
        None, manufacturer.base_settings(profile, print_settings.resolve(profile).quality, setup)
    )
    settings = print_settings.with_choice(settings, "shell.hole_offset", 0.1)
    settings = print_settings.with_choice(settings, "layers.elephant_foot", 0.15)
    offered = [
        entry
        for entry in advise.advise(
            settings, profile, allowances=allowances_for(document, scene.objects["obj_1"])
        )
        if entry.path in {"shell.hole_offset", "layers.elephant_foot"}
        and slicer_keys_takes(setup, entry.path)
    ]
    settings = advise.apply(settings, offered)
    folder = tmp_path / "platte"
    folder.mkdir()
    job = _PlateJob(
        objects=tuple(scene.objects.values()),
        plates=(0,),
        folder=folder,
        name="ausgleich",
        setup=setup,
        settings=settings,
        profile=profile,
        slot_profiles={},
        scene=scene,
        document=document,
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

    walls = _outer_walls(outcome.gcode_path.read_text(encoding="utf-8", errors="replace"))
    owners = sorted({owner for owner, _height in walls})
    assert len(owners) == 2, owners
    heights = sorted({height for _owner, height in walls})
    first, second, middle = heights[0], heights[1], heights[len(heights) // 2]
    # A ist im Modell ab der zweiten Schicht um den Fuß des Materials schmaler.
    plates = sorted(
        (tuple(walls[owner, height] for height in (first, second, middle)) for owner in owners),
        key=lambda layers: _plate_figures(layers[1])[0],
    )
    (a_first, a_second, a_middle), (b_first, b_second, b_middle) = plates
    takes_holes = slicer_keys_takes(setup, "shell.hole_offset")
    takes_foot = slicer_keys_takes(setup, "layers.elephant_foot")
    hole_a = _plate_figures(a_middle)[1]
    hole_b = _plate_figures(b_middle)[1]
    if takes_holes:
        assert hole_b - hole_a == pytest.approx(0.2, abs=0.04), (hole_a, hole_b)
    pulled_a = _plate_figures(a_second)[0] - _plate_figures(a_first)[0]
    pulled_b = _plate_figures(b_second)[0] - _plate_figures(b_first)[0]
    if takes_foot:
        assert pulled_b - pulled_a == pytest.approx(0.3, abs=0.04), (pulled_a, pulled_b)
    assert takes_holes or takes_foot, program


def slicer_keys_takes(setup: handover.SlicerSetup, path: str) -> bool:
    """Nimmt das Programm dieses Aufbaus den Pfad an (``slicer_keys.takes``)?"""
    from app.core.export import slicer_keys

    return slicer_keys.takes(setup.flavour, path, program=slicer_keys.program_of(setup.executable))
