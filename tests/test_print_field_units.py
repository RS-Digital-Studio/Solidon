"""Die Druckfelder zählen Grenzen, Schritt und Vorgabe in derselben Einheit (FD-197).

*Fluss bei Brücken* trug seine Grenzen als Anteil (0,5 bis 1,5) in einem Feld,
das Prozent zeigt. Der Dialog setzte sie unverändert als Spanne des Felds, Qt
rundete sie auf 1 bis 2 %, und die Vorgabe 100 % stand als „2 %“ da. Wer 90
tippte, wurde abgewiesen; wer 1 tippte, schickte 0,01 — ein Prozent
Brückenfluss — an den Slicer. So stand es in 0.6.0.

Die Wächter hier prüfen jede Zeile der Tabelle, nicht nur die eine: Vorgabe
und jeder Wert aus den mitgelieferten Profilen liegen in Anzeigeeinheit im
Bereich, Grenzen und Schritt lassen sich mit den Nachkommastellen des Felds
zeigen, und ein umgerechnetes Feld ist ein Prozentfeld. Dazu der Formatschritt
52 → 53, der einen aus 0.6.0 gespeicherten Fehlwert zurücknimmt, und der Weg
bis in die Konfigurationsdatei des Slicers.
"""

from __future__ import annotations

import json
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest
import trimesh

from app.core.export.writer import write_assembly
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.knowledge.print_fields import FIELDS, Field, field_of
from app.core.scene import migrations
from app.core.scene.migrations import FORMAT_VERSION, migrate
from app.core.scene.project import load, project_data
from app.core.types import PrintSettings, Profile, SceneObject

NUMBER_FIELDS = tuple(field for field in FIELDS if field.kind in ("float", "int"))

#: Die Beispieldatei, geschrieben vom Stand vor dem Formatschritt: Im Druckdialog
#: von 0.6.0 (welle5 ``364367294``) 1 getippt — angezeigt „1 %“, gespeichert 0,01
#: als eigene Wahl —, dazu vier Wände als eigene Wahl, die bleiben muss.
OLD_FILE = Path(__file__).parent / "data" / "projects" / "bridge_flow_v52.p3d"


def _shown(field: Field, value: float) -> float:
    return float(value) * field.factor


def _within(field: Field, value: float) -> bool:
    shown = _shown(field, value)
    return field.minimum - 1e-9 <= shown <= field.maximum + 1e-9


def _plate_value(written: Path, flavour: str, key: str) -> object:
    """Ein Wert der Platte, so wie die Datei für den Slicer ihn trägt."""
    with zipfile.ZipFile(written) as archive:
        if flavour == "prusa":
            for line in archive.read("Metadata/Slic3r_PE.config").decode("utf-8").splitlines():
                name, _sep, value = line.removeprefix("; ").partition(" = ")
                if name == key:
                    return value
            return None
        return json.loads(archive.read("Metadata/project_settings.config")).get(key)


def _written(tmp_path: Path, profile: Profile, settings: PrintSettings, flavour: str) -> Path:
    cube = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    cube.apply_translation((0.0, 0.0, 10.0))
    folder = tmp_path / flavour
    folder.mkdir()
    written, _findings = write_assembly(
        [SceneObject(id="obj_1", name="Wuerfel", mesh=MeshData.of(cube))],
        folder,
        project_name="Bruecke",
        profile=profile,
        settings=settings,
        flavour=flavour,  # type: ignore[arg-type]
        for_slicer=False,
    )
    return written


# --- Das Feld ------------------------------------------------------------------


def test_the_bridge_flow_field_counts_in_percent() -> None:
    """50 bis 200 % in Fünferschritten, die Vorgabe der Programme steht als 100 %.
    Oben reicht es über die 180 % der Creality Hi (HueForge, Review 1 F1)."""
    field = field_of("shell.bridge_flow")
    assert field is not None
    assert (field.unit, field.factor, field.decimals) == ("%", 100.0, 0)
    assert (field.minimum, field.maximum, field.step) == (50.0, 200.0, 5.0)
    assert _shown(field, PrintSettings().shell.bridge_flow) == pytest.approx(100.0)


@pytest.mark.parametrize("field", NUMBER_FIELDS, ids=lambda field: field.path)
def test_every_number_field_holds_its_default_in_its_own_unit(field: Field) -> None:
    """Grenzen, Schritt und Vorgabe stehen in Anzeigeeinheit, und das Feld kann sie zeigen.

    Eine Grenze, die bei den Nachkommastellen des Felds nicht darstellbar ist,
    rundet Qt still weg (0,5 bei null Stellen wurde 1); ein Schritt darunter
    bewegt den Pfeil nicht oder um eine Stelle, die niemand sieht.
    """
    decimals = 0 if field.kind == "int" else field.decimals
    least = 10.0**-decimals
    for bound in (field.minimum, field.maximum):
        assert round(bound, decimals) == pytest.approx(bound, abs=least / 100.0), (
            f"{field.path}: Grenze {bound} bei {decimals} Stellen"
        )
    assert field.minimum < field.maximum
    if field.kind == "float":
        assert field.step >= least - 1e-12, f"{field.path}: Schritt {field.step} unter {least}"
        assert field.step <= field.maximum - field.minimum
    value = print_settings.read_path(PrintSettings(), field.path)
    if value is not None:
        assert _within(field, value), (
            f"{field.path}: Vorgabe {value} zeigt {_shown(field, value)} {field.unit}, "
            f"Bereich {field.minimum}…{field.maximum}"
        )


def test_a_converted_field_is_a_percent_field() -> None:
    """Umgerechnet wird nur Anteil in Prozent; ein Prozentfeld ohne Umrechnung
    zeigte eine 0,15 als „0 %“."""
    for field in FIELDS:
        assert field.factor in (1.0, 100.0), field.path
        assert (field.factor == 100.0) == (field.unit == "%"), field.path
        if field.factor == 100.0:
            assert field.kind == "float", field.path


def test_every_shipped_profile_lands_inside_the_fields_it_fills() -> None:
    """Jeder Wert, den ein mitgelieferter Filamentdrucker mit jedem Material und
    jeder Stufe einträgt, liegt im Bereich seines Felds — sonst klemmt der Dialog
    ihn beim Zeigen, und die Zahl im Feld ist nicht die, die zum Slicer geht.

    Harzdrucker zeigen die Reiter nicht (``_reduce_for_resin``)."""
    outside: dict[tuple[str, float], str] = {}
    printers = [key for key, printer in profiles.printer_profiles().items() if not printer.is_resin]
    materials = list(profiles.material_profiles())
    qualities = list(print_settings.quality_presets())
    # Gezählt, nicht nur gelaufen: Über eine leere Menge ist ein Verbot immer
    # grün (Review 1 F6). Gemessen 16 Filamentdrucker, 7 Materialien, 4 Stufen.
    assert len(printers) >= 10 and len(materials) >= 5 and len(qualities) >= 4
    checked = 0
    for printer in printers:
        for material in materials:
            profile = profiles.make_profile(printer, material)
            for quality in qualities:
                settings = print_settings.resolve(profile, quality)  # type: ignore[arg-type]
                for field in NUMBER_FIELDS:
                    value = print_settings.read_path(settings, field.path)
                    if value is None:
                        continue
                    checked += 1
                    if not _within(field, value):
                        outside.setdefault(
                            (field.path, _shown(field, value)), f"{printer}/{material}/{quality}"
                        )
    assert checked >= len(printers) * len(materials) * len(qualities) * (len(NUMBER_FIELDS) - 2)
    assert not outside, outside


# --- Der Weg zum Slicer ----------------------------------------------------------


@pytest.mark.parametrize(
    ("printer", "flavour", "key"),
    [
        ("centauri-carbon-2", "orca", "bridge_flow"),
        ("prusa-mini", "prusa", "bridge_flow_ratio"),
    ],
)
def test_ninety_percent_reaches_the_slicer_as_a_ratio(
    tmp_path: Path, printer: str, flavour: str, key: str
) -> None:
    """Was das Feld als 90 % zeigt, steht in der Datei des Slicers als 0,9 — die
    Orca-Familie (Orca, Bambu, Elegoo, Creality, Anycubic) liest ``bridge_flow``,
    die Prusa-Familie ``bridge_flow_ratio`` als Anteil."""
    field = field_of("shell.bridge_flow")
    assert field is not None
    profile = profiles.make_profile(printer, "pla")
    chosen = print_settings.with_choice(
        print_settings.resolve(profile), "shell.bridge_flow", 90.0 / field.factor
    )

    written = _written(tmp_path, profile, chosen, flavour)

    assert float(str(_plate_value(written, flavour, key))) == pytest.approx(0.9)


# --- Der Formatschritt 52 → 53 ---------------------------------------------------


def test_a_bridge_flow_from_the_percent_slip_falls_back_to_the_profile() -> None:
    """Die Datei aus 0.6.0 trägt 0,01 als eigene Wahl. Nach dem Öffnen gilt der
    Wert des Herstellerprofils, die vier Wände bleiben die eigene Wahl."""
    stored = project_data(OLD_FILE)
    assert stored["format_version"] == 52
    assert stored["print_settings"]["shell"]["bridge_flow"] == pytest.approx(0.01)
    assert "shell.bridge_flow" in stored["print_settings"]["chosen"]

    document = load(OLD_FILE).document
    settings = document.print_settings
    assert settings is not None
    assert document.format_version == FORMAT_VERSION
    assert settings.chosen == {"shell.wall_count"}
    assert settings.shell.wall_count == 4
    assert "shell.bridge_flow" not in settings.explicit
    assert settings.shell.bridge_flow == pytest.approx(PrintSettings().shell.bridge_flow)


@pytest.mark.parametrize(
    ("printer", "flavour", "key"),
    [
        ("centauri-carbon-2", "orca", "bridge_flow"),
        ("prusa-mini", "prusa", "bridge_flow_ratio"),
    ],
)
def test_the_old_file_hands_over_the_profile_bridge_flow(
    tmp_path: Path, printer: str, flavour: str, key: str
) -> None:
    """Die alte Datei rechnet richtig: In der Datei des Slicers steht der Wert der
    Grundlage. Die Grundlage trägt hier 85 %, damit sie sich vom zurückgesetzten
    Wert der Datei (1,0) unterscheidet (Review 1 F3) — wie der Standardprozess
    des K1 Max mit 0,9."""
    settings = load(OLD_FILE).document.print_settings
    assert settings is not None
    profile = profiles.make_profile(printer, "pla")
    base = print_settings.with_path(print_settings.resolve(profile), "shell.bridge_flow", 0.85)
    effective = print_settings.on_base(settings, base)
    assert effective.shell.wall_count == 4, "die eigene Wahl der Datei gilt weiter"

    written = _written(tmp_path, profile, effective, flavour)

    assert float(str(_plate_value(written, flavour, key))) == pytest.approx(0.85)


def _v52(shell: dict[str, object], **stored: object) -> dict[str, object]:
    return {
        "format_version": 52,
        "scene": {"printer": "centauri-carbon-2", "material": "pla"},
        "ops": [],
        "transactions": [],
        "print_settings": {"shell": shell, **stored},
    }


@pytest.mark.parametrize("slip", [0.01, 0.02])
def test_the_step_drops_the_slip_as_choice_and_as_plate_choice(slip: float) -> None:
    """Das alte Feld konnte nur 1 oder 2 % schreiben — als eigene Wahl oder, unter
    einem übernommenen Vorschlag je Teil, als Wahl der Platte."""
    chosen = migrate(
        _v52(
            {"bridge_flow": slip, "wall_count": 4},
            chosen=["shell.bridge_flow", "shell.wall_count"],
            accepted=[],
        )
    )["print_settings"]
    assert chosen["chosen"] == ["shell.wall_count"]
    assert chosen["shell"]["bridge_flow"] == pytest.approx(1.0)
    assert chosen["shell"]["wall_count"] == 4

    told: list[dict[str, object]] = []
    plate = migrate(
        _v52(
            {"bridge_flow": 0.9},
            chosen=[],
            accepted=["shell.bridge_flow"],
            plate_choices={"shell.bridge_flow": slip, "adhesion.kind": "none"},
        ),
        notes=told,
    )["print_settings"]
    assert plate["accepted"] == ["shell.bridge_flow"]
    assert plate["shell"]["bridge_flow"] == pytest.approx(0.9)
    assert plate["plate_choices"] == {"adhesion.kind": "none"}
    # Auch nur als Wahl der Platte sagt es der Prüfbericht (Nachprüfung R2-1).
    assert told == [{"code": "project.bridge_flow_reset", "percent": round(slip * 100)}]


def test_the_step_keeps_every_real_bridge_flow() -> None:
    """Ein Wert, den das alte Feld nicht schreiben konnte, bleibt — auch der
    übernommene Vorschlag 0,9 und eine Datei ohne Druckeinstellungen."""
    base = _v52(
        {"bridge_flow": 0.85},
        chosen=["shell.bridge_flow"],
        accepted=[],
        plate_choices={"shell.bridge_flow": 0.95},
    )
    kept = migrate(deepcopy(base))["print_settings"]
    assert kept["chosen"] == ["shell.bridge_flow"]
    assert kept["shell"]["bridge_flow"] == pytest.approx(0.85)
    assert kept["plate_choices"] == {"shell.bridge_flow": 0.95}

    bare = {"format_version": 52, "scene": {}, "ops": [], "transactions": []}
    assert migrate(deepcopy(bare))["format_version"] == FORMAT_VERSION
    damaged = _v52({"bridge_flow": "viel"}, chosen="shell.bridge_flow")
    assert migrate(deepcopy(damaged))["print_settings"]["shell"]["bridge_flow"] == "viel"


# --- Der Kunde erfährt es (Review 1 F2, Regel 21) ---------------------------------


def test_opening_the_old_file_says_what_was_taken_back() -> None:
    """Die alte Datei bringt beim Öffnen einen Hinweis mit: der Wert von damals,
    was jetzt gilt, und der Weg zum Feld. Gespeichert wird er nicht."""
    project = load(OLD_FILE)

    (notice,) = project.notices
    assert (notice.code, notice.severity) == ("project.bridge_flow_reset", "info")
    assert "1 %" in str(notice.message) and "0.6.0" in str(notice.message)
    assert notice.values.get("field") == "shell.bridge_flow"
    assert [action.id for action in notice.suggestions] == ["open_print_settings"]
    assert "project.bridge_flow_reset" not in {entry.code for entry in project.report.findings}


@pytest.mark.parametrize("slip", [0.01, 0.02])
def test_the_step_notes_each_slip_once(slip: float) -> None:
    told: list[dict[str, object]] = []
    migrated = migrate(
        _v52(
            {"bridge_flow": slip},
            chosen=["shell.bridge_flow"],
            accepted=[],
            plate_choices={"shell.bridge_flow": slip},
        ),
        notes=told,
    )
    assert told == [{"code": "project.bridge_flow_reset", "percent": round(slip * 100)}]
    assert migrations.NOTES_KEY not in migrated
    (finding,) = migrations.notes_as_findings(told)
    assert f"{round(slip * 100)} %" in str(finding.message)


def test_a_file_cannot_bring_its_own_notes() -> None:
    """Hinweise schreibt nur die Kette; ein Schlüssel aus der Datei sagt nichts."""
    told: list[dict[str, object]] = []
    planted = {
        **_v52({"bridge_flow": 0.9}, chosen=[], accepted=[]),
        migrations.NOTES_KEY: [{"code": "project.bridge_flow_reset", "percent": 99}],
    }
    assert migrations.NOTES_KEY not in migrate(planted, notes=told)
    assert told == []
    real = {"format_version": 52, "scene": {}, "ops": [], "transactions": []}
    assert migrate(deepcopy(real), notes=told) and told == []


# --- Folge der gehobenen Grenzen: Bahnbreite gegen die Düse ----------------------


@pytest.mark.parametrize("path", ["layers.line_width", "layers.first_layer_line_width"])
def test_a_line_far_wider_than_the_nozzle_is_warned(path: str) -> None:
    """Die Feldgrenze reicht für die Granulatdüsen bis 10 mm und wies den
    Tippfehler 4 statt 0,4 mm an der 0,4er Düse nicht mehr ab (Nachprüfung
    NP-3). Wie bei der Schichthöhe sagt der Rat es gegen die Düse — mit dem
    Breitesten, was ein Herstellerprofil an dieser Düse legt, als Vorschlag."""
    from app.core.slice import advise

    profile = profiles.make_profile("generic-220", "pla")
    nozzle = profile.printer.nozzle_diameter
    assert nozzle == pytest.approx(0.4)
    base = print_settings.resolve(profile)
    typo = print_settings.with_choice(base, path, 4.0)

    offered = {entry.path: entry for entry in advise.advise(typo, profile)}

    assert path in offered
    assert offered[path].severity == "warning"
    assert offered[path].value == pytest.approx(advise.WIDE_LINE_SHARE * nozzle)
    widest = print_settings.with_choice(base, path, advise.WIDE_LINE_SHARE * nozzle)
    assert path not in {entry.path for entry in advise.advise(widest, profile)}
