"""Export und die Prüfung, die davor läuft (Bauplan §29, §16.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.core.export import threemf
from app.core.export.writer import (
    check_before_export,
    export_bytes,
    plan_export,
    safe_name,
    write_assembly,
    write_plan,
)
from app.core.geom.mesh import read_mesh
from app.core.geom.transform import apply, place_on_bed, translation
from app.core.ingest.loader import normalise
from app.core.types import Profile, SceneObject, Source, SourceOrigin

MESHES = Path(__file__).parent / "data" / "meshes"


def body(name: str = "cube_clean.stl"):
    """Auf dem Bett, wohin ein Teil kurz vor dem Export gehört."""
    return place_on_bed(normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh)


def scene_object(object_id: str = "obj_1", name: str = "Halterung", mesh=None) -> SceneObject:
    return SceneObject(id=object_id, name=name, mesh=mesh or body())


# --- naming ---------------------------------------------------------------------


def test_names_stay_recognisable_while_becoming_safe() -> None:
    """§29: file-system-safe without becoming unreadable."""
    assert safe_name("Gehäuse oben") == "Gehaeuse_oben"
    assert safe_name("Halter/2") == "Halter2"
    assert safe_name("Größe: 20mm") == "Groesse_20mm"
    assert safe_name("") == "teil"


def test_a_single_part_gets_a_plain_name(profile: Profile) -> None:
    plan = plan_export([scene_object()], project_name="Projekt", profile=profile)

    assert [entry.filename for entry in plan.entries] == ["Projekt_Halterung.stl"]


def test_several_parts_are_numbered(profile: Profile) -> None:
    """§29: bei drei Teilen auf einer Platte will man sehen, welches welches
    ist.
    """
    objects = [
        scene_object("obj_1", "Deckel"),
        scene_object("obj_2", "Boden"),
        scene_object("obj_3", "Ring"),
    ]
    plan = plan_export(objects, project_name="Dose", profile=profile)

    assert [entry.filename for entry in plan.entries] == [
        "Dose_Deckel_1von3.stl",
        "Dose_Boden_2von3.stl",
        "Dose_Ring_3von3.stl",
    ]


def test_the_scheme_can_be_changed(profile: Profile) -> None:
    plan = plan_export(
        [scene_object()], project_name="P", profile=profile, scheme="{object}-{index}"
    )
    assert plan.entries[0].filename == "Halterung-1.stl"


def test_exporting_nothing_is_a_user_error(profile: Profile) -> None:
    with pytest.raises(ValidationError) as caught:
        plan_export([], project_name="P", profile=profile)
    assert caught.value.suggestions


# --- the check ------------------------------------------------------------------


def test_a_clean_part_has_nothing_to_report(profile: Profile) -> None:
    assert check_before_export([scene_object()], profile, {}) == []


def test_a_part_below_the_bed_is_reported(profile: Profile) -> None:
    """Der Bauraum beginnt bei Z = 0; ein halber Würfel darunter ist es wert,
    gesagt zu werden.
    """
    sunk = normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh
    findings = check_before_export([scene_object(mesh=sunk)], profile, {})

    assert "arrange.out_of_build_volume" in {finding.code for finding in findings}


def test_an_open_part_is_reported_but_not_blocked(profile: Profile) -> None:
    """§29: wer trotzdem exportieren will, kann das — er weiß dann nur, was er
    tut.
    """
    open_body = place_on_bed(
        normalise(read_mesh((MESHES / "broken_open.stl").read_bytes(), ".stl"), "mm").mesh
    )
    plan = plan_export([scene_object(mesh=open_body)], project_name="P", profile=profile)

    codes = {finding.code for finding in plan.findings}
    assert "export.not_watertight" in codes
    assert not plan.blocked
    assert plan.entries, "the file would still be written"


def test_a_part_outside_the_build_volume_is_reported(profile: Profile) -> None:
    far = apply(body(), translation((400.0, 0.0, 0.0)))
    findings = check_before_export([scene_object(mesh=far)], profile, {})

    assert "arrange.out_of_build_volume" in {finding.code for finding in findings}


def test_the_licence_of_a_source_is_mentioned_once(profile: Profile) -> None:
    """§16.3: once, factual, without a lecture."""
    sources = {
        "src_1": Source(
            id="src_1",
            kind="import",
            path="sources/a.stl",
            sha256="",
            origin=SourceOrigin(title="Halterung", licence="CC BY-NC 4.0"),
        )
    }
    findings = check_before_export([scene_object()], profile, sources)
    licence_findings = [f for f in findings if f.code == "export.source_licence"]

    assert len(licence_findings) == 1
    assert licence_findings[0].severity == "info"
    assert "CC BY-NC 4.0" in str(licence_findings[0].values["sources"])


# --- writing --------------------------------------------------------------------


def test_writing_produces_readable_files(tmp_path: Path, profile: Profile) -> None:
    plan = plan_export(
        [scene_object("obj_1", "Deckel"), scene_object("obj_2", "Boden")],
        project_name="Dose",
        profile=profile,
    )
    written = write_plan(plan, tmp_path)

    assert len(written) == 2
    for path in written:
        assert path.is_file()
        reread = read_mesh(path.read_bytes(), ".stl")
        assert reread.triangle_count == 12


@pytest.mark.parametrize("export_format", ["stl", "3mf", "obj", "ply"])
def test_every_format_writes_something_readable(export_format: str, profile: Profile) -> None:
    data = export_bytes(body(), export_format)  # type: ignore[arg-type]

    assert data, f"{export_format} produced no bytes"
    if export_format in ("stl", "obj", "ply", "3mf"):
        suffix = f".{export_format}"
        assert read_mesh(data, suffix).triangle_count == 12


def test_a_name_keeps_its_alphabet() -> None:
    """§29: sicher, nicht von allem befreit, was nicht englisch ist.

    Der Export zwang früher den ganzen Namen durch ASCII: ein
    heruntergeladenes ``埃菲尔铁塔18cm`` kam als ``18cm`` heraus und ein
    ``Соединитель`` als ``teil``.
    """
    assert safe_name("埃菲尔铁塔18cm") == "埃菲尔铁塔18cm"
    assert safe_name("Соединитель") == "Соединитель"
    assert safe_name("Boîtier") == "Boîtier", "a French accent is not a hazard either"


def test_what_is_actually_unsafe_still_goes() -> None:
    """Der Teil, der immer richtig war: Trenner und reservierte Satzzeichen."""
    assert safe_name(r"a/b\c") == "abc"
    assert safe_name('Teil: "gross" <1>') == "Teil_gross_1"
    assert safe_name("*?|") == "teil", "and nothing left over is still the fallback"


# --- Baugruppe: alles einer Platte in eine Datei (§20, §29) -------------------------


def test_an_assembly_is_one_file_for_every_object(tmp_path: Path, profile: Profile) -> None:
    """Der Unterschied zu ``write_plan`` ist nicht das Format, sondern die Zahl
    der Dateien: der Slicer bekommt einen Druckauftrag statt einer Handvoll
    Teile, über deren Zusammengehörigkeit er selbst entscheiden müsste."""
    objects = [scene_object("obj_1", "Deckel"), scene_object("obj_2", "Boden")]

    written, _findings = write_assembly(objects, tmp_path, project_name="Gehäuse", profile=profile)

    assert written.suffix == ".3mf"
    assert len(list(tmp_path.glob("*.3mf"))) == 1
    assert threemf.count_objects(written.read_bytes()) == 2


def test_the_assembly_carries_the_object_names(tmp_path: Path, profile: Profile) -> None:
    objects = [scene_object("obj_1", "Deckel"), scene_object("obj_2", "Boden")]

    written, _findings = write_assembly(objects, tmp_path, project_name="x", profile=profile)

    assert [part.name for part in threemf.read_objects(written.read_bytes())] == [
        "Deckel",
        "Boden",
    ]


def test_only_the_named_plate_goes_into_the_file(tmp_path: Path, profile: Profile) -> None:
    """Mehr Teile, als auf eine Platte passen, ist normal (§25) — aber eine
    Druckdatei ist eine Platte."""
    erste = scene_object("obj_1", "Vorne")
    zweite = scene_object("obj_2", "Naechste")
    zweite.plate = 1
    objects = [erste, zweite]

    written, _findings = write_assembly(
        objects, tmp_path, project_name="x", profile=profile, plate=0
    )

    assert threemf.count_objects(written.read_bytes()) == 1


def test_an_empty_plate_says_so(tmp_path: Path, profile: Profile) -> None:
    with pytest.raises(ValidationError):
        write_assembly([scene_object()], tmp_path, project_name="x", profile=profile, plate=7)


def test_the_assembly_reports_before_writing(tmp_path: Path, profile: Profile) -> None:
    """§29: die Prüfung vor dem Export berichtet, sie blockiert nicht."""
    objects = [scene_object("obj_1", "Teil", mesh=body("broken_open.stl"))]

    written, findings = write_assembly(objects, tmp_path, project_name="x", profile=profile)

    assert written.is_file(), "geschrieben wird trotzdem"
    assert findings, "aber der Befund steht dabei"
