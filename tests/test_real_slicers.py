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
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
import trimesh

from app.core.export import appimage, cura_linux, handover, slicer_keys, slicer_profiles
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.types import Profile, SceneObject
from app.core.units import format_length
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


#: Curas Bahnarten des Modells (``;TYPE:``); Stütze ist alles, was mit
#: ``SUPPORT`` beginnt, samt Trennschicht. Rand und Turm zählen nicht.
_CURA_MODEL = frozenset({"WALL-OUTER", "WALL-INNER", "SKIN", "FILL"})

_CURA_WORD = re.compile(r"([XYZE])(-?\d*\.?\d+)")


@dataclass(frozen=True)
class _CuraGaps:
    """Abstand oben und unten zwischen Curas Stütze und dem Modell, in mm, und
    wie viele Bahnpunkte (je Millimeter einer) die oberste und die unterste
    Stützlage im Ring tragen."""

    top: float
    bottom: float
    top_points: int
    bottom_points: int


def _cura_support_gaps(text: str, layer: float, ring: tuple[float, float]) -> _CuraGaps:
    """Misst Curas Stützabstand oben und unten (RM-628) in einem Ring um die Mitte
    des Modells (``ring``: innerer und äußerer Abstand in mm, je Achse).

    Höhen im G-Code sind Oberkanten; jede Lage ist ``layer`` hoch. Oben: die
    Unterseite der ersten Modelllage über der höchsten Stützbahn minus diese —
    auch, wenn Cura die oberste Stütze als Bruchteillage tiefer legt. Unten: die
    Unterseite der tiefsten Stützlage minus die oberste Modellbahn darunter.
    Gezählt werden Bahnen mit Förderung, absolut (``M82``, ``G92 E``) wie relativ
    (``M83``)."""
    relative = False
    x = y = z = e = 0.0
    kind = ""
    moves: list[tuple[bool, float, float, float]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(";TYPE:"):
            kind = line[len(";TYPE:") :].strip()
            continue
        command = line.split(";", 1)[0].split()
        if not command:
            continue
        if command[0] in ("M82", "M83"):
            relative = command[0] == "M83"
            continue
        words = {key: float(value) for key, value in _CURA_WORD.findall(" ".join(command[1:]))}
        if command[0] == "G92":
            e = words.get("E", e)
            continue
        if command[0] not in ("G0", "G1"):
            continue
        start_x, start_y = x, y
        x, y, z = words.get("X", x), words.get("Y", y), words.get("Z", z)
        if "E" not in words:
            continue
        fed = words["E"] if relative else words["E"] - e
        e = e if relative else words["E"]
        support = kind.startswith("SUPPORT")
        if fed > 0.0 and command[0] == "G1" and (support or kind in _CURA_MODEL):
            # Je Millimeter Bahn ein Punkt: Füllbahnen enden am Rand, nicht im Ring.
            steps = max(1, math.ceil(math.hypot(x - start_x, y - start_y)))
            moves += [
                (
                    support,
                    start_x + (x - start_x) * t / steps,
                    start_y + (y - start_y) * t / steps,
                    z,
                )
                for t in range(1, steps + 1)
            ]
    model = [(px, py) for support, px, py, _pz in moves if not support]
    assert model, "keine Modellbahn im G-Code"
    centre_x = (min(px for px, _ in model) + max(px for px, _ in model)) / 2.0
    centre_y = (min(py for _, py in model) + max(py for _, py in model)) / 2.0
    inner, outer = ring
    inside = [
        (support, pz)
        for support, px, py, pz in moves
        if inner <= max(abs(px - centre_x), abs(py - centre_y)) <= outer
    ]
    held = [pz for support, pz in inside if support]
    walls = [pz for support, pz in inside if not support]
    assert held, "keine Stützbahn im Ring"
    highest, lowest = max(held), min(held)
    above = min(pz for pz in walls if pz > highest)
    below = max(pz for pz in walls if pz < lowest)
    return _CuraGaps(
        top=round(above - layer - highest, 4),
        bottom=round(lowest - layer - below, 4),
        top_points=sum(1 for pz in held if math.isclose(pz, highest, abs_tol=1e-3)),
        bottom_points=sum(1 for pz in held if math.isclose(pz, lowest, abs_tol=1e-3)),
    )


def test_the_cura_gap_measure_reads_fractions_resets_and_the_ring() -> None:
    """Die Messung selbst (RM-628), an einem kleinen G-Code nach Curas Art: Sockel
    bis 3,0 mm, Stütze ab 3,6 (unten 0,4 Luft), oberste Stützbahn als Bruchteillage
    bei 12,72 unter der Platte ab 13,0 (oben 0,28). Absolute Förderung mit
    ``G92 E0`` zwischen den Lagen; Stütze am Rand außerhalb des Rings, Rand und
    Fahrten ohne Förderung zählen nicht."""
    lines = ["M82", "G92 E0"]
    e = 0.0

    def lay(kind: str, z: float, xs: tuple[float, ...]) -> None:
        nonlocal e
        lines.append(f";TYPE:{kind}")
        for x in xs:
            lines.append(f"G0 X{x} Y-10 Z{z}")
            e += 0.1
            lines.append(f"G1 X{x} Y10 E{e:.5f}")

    walls = (-18.0, -10.0, 10.0, 18.0)
    for step in range(15):
        lay("WALL-OUTER", round(0.2 * (step + 1), 3), walls)
    lay("SKIRT", 3.6, (-30.0, 30.0))
    for step in range(46):
        lay("SUPPORT", round(3.6 + 0.2 * step, 3), (-10.0, 10.0, 17.5))
        lines.append("G92 E0")
        e = 0.0
    lay("SUPPORT-INTERFACE", 12.72, (-10.0, 10.0))
    lines.append("G0 X-10 Y-10 Z12.9")
    for step in range(10):
        lay("SKIN", round(13.2 + 0.2 * step, 3), walls)
    text = "\n".join(lines) + "\n"

    measured = _cura_support_gaps(text, 0.2, (7.0, 14.0))
    assert measured == _CuraGaps(top=0.28, bottom=0.4, top_points=40, bottom_points=40), measured
    relative = text.replace("M82", "M83").replace("G92 E0\n", "")
    assert _cura_support_gaps(relative, 0.2, (7.0, 14.0)).bottom == pytest.approx(0.4)


@pytest.mark.slicer("cura")
@pytest.mark.parametrize(
    ("style", "layer", "gap"),
    [("grid", 0.2, 0.28), ("tree", 0.2, 0.44), ("grid", 0.28, 0.3), ("tree", 0.12, 0.28)],
)
def test_curas_support_gap_arrives_as_solidon_says(
    style: str,
    layer: float,
    gap: float,
    installed_slicer: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cura druckt den Stützabstand, wie Solidon rät und anzeigt (RM-628).

    Eine Platte über einer Säule auf einem Sockel, PETG, Werte fern des
    Herstellers. CuraEngine rundet auf (``round_up_divide``): unter Gitter nur
    unten, oben gilt der Abstand genau mit einer Bruchteillage der Stütze; unter
    Bäumen oben und unten. Unter Gitter schreibt die Übergabe unten deshalb das
    Vielfache im Band von PETG selbst (``support_bottom_distance``): 0,28 bei
    0,2er Schichten druckt oben 0,28 und unten 0,2 statt 0,4, 0,30 bei 0,28er
    Schichten unten 0,28 statt 0,56. 0,44 unter Bäumen druckt 0,6 — zur nächsten
    Schicht gerundet wären es 0,4. Der Satz am Feld nennt den Wert, den Cura
    unten druckt.
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
    profile = profiles.make_profile(PROGRAMS["cura"], "petg")
    settings = print_settings.resolve(profile)
    for path, value in (
        ("layers.layer_height", layer),
        ("support.style", style),
        ("support.placement", "everywhere"),
        ("support.z_gap", gap),
        ("support.interface_layers", 2),
        ("support.bottom_interface_layers", 3),
    ):
        settings = print_settings.with_choice(settings, path, value)
    setup = _preselected(handover.detect(installed_slicer), profile)
    assert setup.flavour == "cura", setup
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
    # Vier Millimeter innerhalb des Plattenrands und drei außerhalb der Säule.
    measured = _cura_support_gaps(
        outcome.gcode_path.read_text(encoding="utf-8", errors="replace"), layer, (7.0, 14.0)
    )

    top, bottom = advise.printed_support_gaps(gap, layer, "cura", style, material=profile.material)
    assert measured.top_points >= 10 and measured.bottom_points >= 10, measured
    assert measured.top == pytest.approx(top, abs=0.02), measured
    assert measured.bottom == pytest.approx(bottom, abs=0.02), measured
    if style == "grid":
        assert bottom == pytest.approx(layer), "unten eine Schicht, im Band von PETG"
    said = slicer_keys.limitation("cura", "support.z_gap", settings, material=profile.material)
    assert said is not None and said.values == {"gap": format_length(bottom)}, said
