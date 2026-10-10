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
from app.core.slice.analysis import slice_body
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


#: Die 36-mm-Brücke der G-Code-Gegenprüfung (N1): ein Steg auf zwei Pfeilern.
BRIDGE = Path(__file__).parent / "data" / "meshes" / "bridge_two_end_supports.ply"


def _advised_gcode(
    installed_slicer: Path,
    tmp_path: Path,
    body: trimesh.Trimesh,
    printer: str,
    material: str = "pla",
    *,
    vendor: bool = True,
    declined: frozenset[str] = frozenset(),
    without: frozenset[str] = frozenset(),
) -> tuple[str, list[str]]:
    """Den Rat übernehmen wie *Vorschläge übernehmen* und die Platte schneiden.

    Gibt die Druckdatei und die übernommenen Pfade zurück. ``vendor=False``
    schneidet mit Solidons eigenem Satz (kein Herstellerprofil), ``declined``
    sind abgelehnte Vorschläge (RM-587), ``without`` Pfade, die für den
    Vergleich nicht übernommen werden."""
    from app.core.slice import advise
    from app.ui.print_settings_dialog import _PlateJob, _prepare_plate

    body.apply_translation((0.0, 0.0, -body.bounds[0][2]))
    mesh = MeshData.of(body)
    entry = SceneObject("koerper", "Körper", mesh)
    profile = profiles.make_profile(printer, material)
    settings = print_settings.resolve(profile)
    result = slice_body(
        mesh,
        settings.layers.layer_height,
        first_layer_height=settings.layers.first_layer_height,
        overhang_angle=profile.overhang_limit_degrees,
        bridge_from=profile.minimum_wall_thickness,
        support_volume=False,
    )
    setup = handover.detect(installed_slicer)
    if vendor:
        setup = _preselected(setup, profile)
    entries = [
        item
        for item in advise.advise(
            settings, profile, result, bounds=mesh.bounds, flavour=setup.flavour, declined=declined
        )
        if item.path not in declined
    ]
    settings = advise.apply(settings, [item for item in entries if item.path not in without])
    folder = tmp_path / "platte"
    folder.mkdir(parents=True)
    job = _PlateJob(
        objects=(entry,),
        plates=(0,),
        folder=folder,
        name="koerper",
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
    text = outcome.gcode_path.read_text(encoding="utf-8", errors="replace")
    return text, [item.path for item in entries]


def _config(text: str, key: str) -> str:
    """Ein Wert aus dem Konfigurationsblock der Druckdatei."""
    found = re.search(rf"^; {re.escape(key)} = (.*)$", text, re.MULTILINE)
    assert found is not None, f"{key} fehlt im Konfigurationsblock"
    return found.group(1).strip()


def _support_moves(text: str) -> int:
    """Wie viele Druckbewegungen in Stützbahnen liegen (alle Familien)."""
    count = 0
    inside = False
    for line in text.splitlines():
        if line.startswith((";TYPE:", "; TYPE:")):
            inside = "upport" in line
        elif inside and _EXTRUSION.match(line):
            count += 1
    return count


#: Die Pfade aus RM-587. Sie gehen je Teil und stehen deshalb nicht im
#: Konfigurationsblock, der die Platte zeigt; gemessen wird ihre Wirkung.
RM587_PATHS = frozenset(
    {
        "support.bridges",
        "shell.thick_bridges",
        "shell.bridge_flow",
        "shell.overhang_walls",
        "shell.overhang_reverse",
    }
)


def _bridge_lines(text: str) -> tuple[float, float]:
    """Länge und Förderung der äußeren Brückenbahnen (Prusa ``Bridge infill``,
    Orca-Familie ``Bridge``), in mm."""
    length = feed = 0.0
    inside = False
    x = y = 0.0
    for line in text.splitlines():
        if line.startswith((";TYPE:", "; TYPE:")):
            inside = line.split(":", 1)[1].strip() in ("Bridge", "Bridge infill")
            continue
        if not line.startswith(("G1 ", "G0 ")):
            continue
        words = {word[0]: word[1:] for word in line.split(";")[0].split()[1:]}
        nx = float(words["X"]) if "X" in words else x
        ny = float(words["Y"]) if "Y" in words else y
        if inside and "E" in words and float(words["E"]) > 0.0:
            length += ((nx - x) ** 2 + (ny - y) ** 2) ** 0.5
            feed += float(words["E"])
        x, y = nx, ny
    return length, feed


@pytest.mark.slicer("prusaslicer")
def test_prusaslicer_supports_a_long_bridge_and_thickens_a_free_one(
    installed_slicer: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N1 der G-Code-Gegenprüfung: Mit Solidons eigenem Satz blieb die 36-mm-Brücke
    in PrusaSlicer trotz Stützen frei (``dont_support_bridges = 1``, 0 mm Stütze).
    Jetzt stützt sie. Lehnt der Kunde die Stützen ab, legt das Teil seine Brücke
    dick und mit 90 % Fluss — als Objektwert, gemessen gegen denselben Lauf ohne
    die Übernahme (RM-587)."""
    set_test_license(monkeypatch, active=True)
    raw = trimesh.load(BRIDGE, force="mesh")

    held, _taken = _advised_gcode(
        installed_slicer, tmp_path / "gestuetzt", raw.copy(), "generic-220", vendor=False
    )
    assert _config(held, "dont_support_bridges") == "0"
    assert _support_moves(held) > 50, "Stütze unter der Brücke"

    free, taken = _advised_gcode(
        installed_slicer,
        tmp_path / "frei",
        raw.copy(),
        "prusa-mk4s",
        declined=frozenset({"support.style"}),
    )
    plain, _taken = _advised_gcode(
        installed_slicer,
        tmp_path / "ohne",
        raw.copy(),
        "prusa-mk4s",
        declined=frozenset({"support.style"}),
        without=RM587_PATHS,
    )
    assert {"shell.thick_bridges", "shell.bridge_flow"} <= set(taken)
    length, feed = _bridge_lines(free)
    plain_length, plain_feed = _bridge_lines(plain)
    assert length > 0.0 and plain_length > 0.0
    assert feed / length > 1.15 * plain_feed / plain_length, "dicke Brücke fördert mehr je mm"


@pytest.mark.parametrize(
    "program",
    [
        pytest.param(program, marks=pytest.mark.slicer(program), id=program)
        for program in ("orcaslicer", "elegooslicer")
    ],
)
def test_the_orca_family_takes_bridges_rims_and_alternating_walls(
    program: str, installed_slicer: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-587 in der Orca-Familie, je gegen denselben Lauf ohne die Übernahme: Die
    freie 36-mm-Brücke wird dick, ein 3-mm-Rand ohne Stütze verliert seine lose
    Brückenbahn an Zusatzwände, und ein ABS-Trichter mit 50 Grad dreht seine
    Außenwand in jeder zweiten Schicht."""
    set_test_license(monkeypatch, active=True)
    printer = PROGRAMS[program]
    declined = frozenset({"support.style"})

    def both(name: str, body: trimesh.Trimesh, material: str = "pla") -> tuple[str, str, list[str]]:
        advised, taken = _advised_gcode(
            installed_slicer, tmp_path / name, body.copy(), printer, material, declined=declined
        )
        plain, _taken = _advised_gcode(
            installed_slicer,
            tmp_path / f"{name}-ohne",
            body.copy(),
            printer,
            material,
            declined=declined,
            without=RM587_PATHS,
        )
        return advised, plain, taken

    bridge, plain, taken = both("bruecke", trimesh.load(BRIDGE, force="mesh"))
    assert "shell.thick_bridges" in taken
    length, feed = _bridge_lines(bridge)
    plain_length, plain_feed = _bridge_lines(plain)
    assert feed / length > 1.15 * plain_feed / plain_length, "dicke Brücke fördert mehr je mm"

    post = trimesh.creation.box((20.0, 20.0, 20.0))
    post.apply_translation((0.0, 0.0, 10.0))
    slab = trimesh.creation.box((26.0, 20.0, 3.0))
    slab.apply_translation((0.0, 0.0, 21.5))
    rim, plain, taken = both("rand", trimesh.boolean.union([post, slab]))
    assert "shell.overhang_walls" in taken
    assert _bridge_lines(rim)[0] < 0.5 * _bridge_lines(plain)[0], "Zusatzwände statt Brücke"

    funnel, plain, taken = both("trichter", _funnel(50.0), "abs")
    assert "shell.overhang_reverse" in taken
    turns = _outer_wall_turns(funnel)
    assert len(turns) > 40 and len(set(turns)) == 2, "die Außenwand wechselt die Richtung"
    assert len(set(_outer_wall_turns(plain))) == 1, "ohne die Übernahme in einer Richtung"


def _two_pillar_bridge(x: float) -> trimesh.Trimesh:
    """Zwei Säulen 6 × 20 × 12 mm, darüber ein Deck von 3 mm, 36 mm frei gespannt."""
    parts = []
    for extents, centre in (
        ((6.0, 20.0, 12.0), (x - 21.0, 0.0, 6.0)),
        ((6.0, 20.0, 12.0), (x + 21.0, 0.0, 6.0)),
        ((48.0, 20.0, 3.0), (x, 0.0, 13.5)),
    ):
        box = trimesh.creation.box(extents=extents)
        box.apply_translation(centre)
        parts.append(box)
    return trimesh.boolean.union(parts, engine="manifold")


#: Wo ein Körper in der Druckdatei beginnt: der Name in der Orca-Familie (bei
#: Anycubic Slicer Next in Anführungszeichen), die Nummer bei PrusaSlicer
#: (``M486``), die Kennung in Ladefolge bei Bambu Studio.
_ORCA_OBJECT = re.compile(r'^; printing object "?(\w+)')
_PRUSA_NAME = re.compile(r"^M486 A(\w+)")
_PRUSA_OBJECT = re.compile(r"^M486 S(-?\d+)")
_BAMBU_IDS = re.compile(r"^; model label id: ([\d,]+)")
_BAMBU_OBJECT = re.compile(r"^; start printing object, unique label id: (\d+)")


def _bridge_lines_per_object(text: str, names: tuple[str, ...]) -> dict[str, tuple[float, float]]:
    """Länge und Förderung der äußeren Brückenbahnen je Körper, in mm.

    Bambu Studio nennt keine Namen, sondern Kennungen in der Ladefolge der Körper;
    die erste gehört dem ersten Körper der Platte."""
    found = {name: [0.0, 0.0] for name in names}
    numbers: dict[str, str] = {}
    label: str | None = None
    pending: str | None = None
    inside = False
    x = y = 0.0
    for line in text.splitlines():
        if line.startswith((";TYPE:", "; TYPE:", "; FEATURE:")):
            inside = line.split(":", 1)[1].strip() in ("Bridge", "Bridge infill")
            continue
        orca = _ORCA_OBJECT.match(line)
        prusa = _PRUSA_OBJECT.match(line)
        prusa_name = _PRUSA_NAME.match(line)
        bambu_ids = _BAMBU_IDS.match(line)
        bambu = _BAMBU_OBJECT.match(line)
        if orca:
            label = orca.group(1) if orca.group(1) in found else None
        elif line.startswith("; stop printing object"):
            label = None
        elif bambu_ids:
            numbers = dict(zip(bambu_ids.group(1).split(","), names, strict=False))
        elif bambu:
            label = numbers.get(bambu.group(1))
        elif prusa_name and pending is not None:
            numbers[pending] = prusa_name.group(1)
        elif prusa:
            pending = prusa.group(1)
            label = numbers.get(pending)
        if not line.startswith(("G1 ", "G0 ")):
            continue
        words = {word[0]: word[1:] for word in line.split(";")[0].split()[1:]}
        nx = float(words["X"]) if "X" in words else x
        ny = float(words["Y"]) if "Y" in words else y
        if inside and label is not None and "E" in words and float(words["E"]) > 0.0:
            found[label][0] += ((nx - x) ** 2 + (ny - y) ** 2) ** 0.5
            found[label][1] += float(words["E"])
        x, y = nx, ny
    return {name: (length, feed) for name, (length, feed) in found.items()}


@pytest.mark.parametrize(
    "program",
    [
        pytest.param(program, marks=pytest.mark.slicer(program), id=program)
        for program in (
            "prusaslicer",
            "orcaslicer",
            "elegooslicer",
            "crealityprint",
            "anycubicslicernext",
            "bambustudio",
        )
    ],
)
def test_the_bridge_flow_of_one_part_stays_with_that_part(
    program: str, installed_slicer: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Brückenwerte gehören dem Teil mit der Brücke (RM-587, Entscheidung Robert):
    Zwei gleiche Brücken auf einer Platte, nur die linke verlangt 70 % Fluss. Das
    Programm liest ihn als Objektwert und legt nur ihre Brücke dünner; die rechte
    behält den Fluss der Platte. Gemessen in acht Programmen mit allen fünf Werten
    (``konzepte/begruendungen/regel-druckrat.md``); Cura und SuperSlicer nehmen
    keinen und fehlen hier."""
    from app.core.export import writer
    from app.core.types import PrintSettings, SettingAdvice
    from app.ui.print_settings_dialog import _PlateJob, _prepare_plate
    from tests.helpers import object_values

    set_test_license(monkeypatch, active=True)
    profile = profiles.make_profile(PROGRAMS[program], "pla")
    settings = print_settings.with_choice(print_settings.resolve(profile), "support.style", "none")
    settings = print_settings.with_accepted(settings, "shell.bridge_flow", 0.7)
    setup = _preselected(handover.detect(installed_slicer), profile)

    def asks(
        entry: SceneObject, _mesh: object, base: PrintSettings, *_args: object, **_kwargs: object
    ) -> list[SettingAdvice]:
        if entry.id != "links":
            return []
        was = print_settings.read_path(base, "shell.bridge_flow")
        return [SettingAdvice("shell.bridge_flow", 0.7, was, "Probe")]

    monkeypatch.setattr(writer, "part_advice", asks)
    objects = tuple(
        SceneObject(name, name, MeshData.of(_two_pillar_bridge(x)))
        for name, x in (("links", -34.0), ("rechts", 34.0))
    )
    folder = tmp_path / "platte"
    folder.mkdir()
    job = _PlateJob(
        objects=objects,
        plates=(0,),
        folder=folder,
        name="bruecken",
        setup=setup,
        settings=settings,
        profile=profile,
        slot_profiles={},
    )
    run = _prepare_plate(job, 0)
    member, key = (
        ("Metadata/Slic3r_PE_model.config", "bridge_flow_ratio")
        if setup.flavour == "prusa"
        else ("Metadata/model_settings.config", "bridge_flow")
    )
    written = object_values(run.model, member)
    assert float(written["links"][key]) == pytest.approx(0.7)
    assert key not in written["rechts"], "das rechte Teil bekommt keinen Brückenfluss"
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
    text = outcome.gcode_path.read_text(encoding="utf-8", errors="replace")
    lines = _bridge_lines_per_object(text, ("links", "rechts"))
    (left, left_feed), (right, right_feed) = lines["links"], lines["rechts"]
    assert left > 0.0 and right > 0.0, f"{program}: Brückenbahnen je Körper {lines}"
    assert left_feed / left < 0.85 * right_feed / right, (
        f"{program}: links {left_feed / left:.4f}, rechts {right_feed / right:.4f} mm je mm"
    )


def _funnel(angle: float, bottom: float = 6.0, height: float = 20.0) -> trimesh.Trimesh:
    """Ein umgedrehter Kegelstumpf, Wand ``angle`` Grad gegen die Senkrechte."""
    import math

    import numpy as np

    top = bottom + height * math.tan(math.radians(angle))
    sides = 128
    turn = np.linspace(0.0, 2.0 * np.pi, sides, endpoint=False)
    lower = np.c_[bottom * np.cos(turn), bottom * np.sin(turn), np.zeros(sides)]
    upper = np.c_[top * np.cos(turn), top * np.sin(turn), np.full(sides, height)]
    vertices = np.vstack([lower, upper, [[0.0, 0.0, 0.0], [0.0, 0.0, height]]])
    faces = []
    for index in range(sides):
        following = (index + 1) % sides
        faces += [
            [index, following, sides + following],
            [index, sides + following, sides + index],
            [2 * sides, following, index],
            [2 * sides + 1, sides + index, sides + following],
        ]
    raw = trimesh.Trimesh(vertices, faces)
    raw.fix_normals()
    return raw


def _outer_wall_turns(text: str) -> list[bool]:
    """Je Schicht der Drehsinn der Außenwand (Vorzeichen der umfahrenen Fläche)."""
    turns: list[bool] = []
    area = 0.0
    inside = False
    x = y = 0.0
    for line in text.splitlines():
        if line.startswith(";LAYER_CHANGE"):
            if area:
                turns.append(area > 0.0)
            area = 0.0
        elif line.startswith(";TYPE:"):
            inside = line[6:].strip() == "Outer wall"
        elif line.startswith(("G1 ", "G0 ")):
            words = {word[0]: word[1:] for word in line.split(";")[0].split()[1:]}
            nx = float(words["X"]) if "X" in words else x
            ny = float(words["Y"]) if "Y" in words else y
            if inside and "E" in words and float(words["E"]) > 0.0:
                area += x * ny - nx * y
            x, y = nx, ny
    return turns


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
