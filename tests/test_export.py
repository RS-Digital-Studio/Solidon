"""Export und die Prüfung, die davor läuft (Bauplan §29, §16.3)."""

from __future__ import annotations

import zipfile
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.export import threemf
from app.core.export.writer import (
    arrangement_holds,
    check_adhesion_clearance,
    check_before_export,
    check_filament_changes,
    export_bytes,
    plan_export,
    plates_by_material,
    safe_name,
    write_assembly,
    write_plan,
)
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.transform import apply, place_on_bed, translation
from app.core.ingest.loader import normalise
from app.core.knowledge import print_settings, profiles
from app.core.types import MaterialSlot, Profile, SceneObject, Source, SourceOrigin

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


# --- die Prüfung ----------------------------------------------------------------


def test_a_clean_part_has_nothing_to_report(profile: Profile) -> None:
    assert check_before_export([scene_object()], profile, {}) == []


def test_a_part_below_the_bed_is_reported(profile: Profile) -> None:
    """Der Bauraum beginnt bei Z = 0; ein halber Würfel darunter ist es wert,
    gesagt zu werden.
    """
    sunk = normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh
    findings = check_before_export([scene_object(mesh=sunk)], profile, {})

    assert "arrange.out_of_build_volume" in {finding.code for finding in findings}


def test_a_part_below_the_bed_is_not_called_too_big(profile: Profile) -> None:
    """Der häufigste Fall von Weg 1 bekam den irreführendsten Satz.

    Ein heruntergeladenes Teil ist meist um den Ursprung zentriert und liegt
    darum zur Hälfte unter der Platte — ein 8 mm hohes Teil auf einem
    256-mm-Drucker. „Steht über den Bauraum hinaus" schickt den Nutzer zum
    Skalieren, obwohl ein Aufsetzen genügt.
    """
    sunk = normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh
    findings = check_before_export([scene_object(mesh=sunk)], profile, {})

    said = str(next(f.message for f in findings if f.code == "arrange.out_of_build_volume"))
    assert "unter der Druckplatte" in said
    assert "hinaus" not in said, "das ist der Satz für zu groß"


def test_a_part_that_really_is_too_big_still_says_so(profile: Profile) -> None:
    """Die Unterscheidung darf den echten Fall nicht verschlucken."""
    huge = read_mesh((MESHES / "oversized.stl").read_bytes(), ".stl")
    findings = check_before_export([scene_object(mesh=place_on_bed(huge))], profile, {})

    said = str(next(f.message for f in findings if f.code == "arrange.out_of_build_volume"))
    assert "hinaus" in said


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


@pytest.mark.parametrize("export_format", ["stl", "3mf", "obj", "ply", "glb"])
def test_every_format_writes_something_readable(export_format: str, profile: Profile) -> None:
    data = export_bytes(body(), export_format)  # type: ignore[arg-type]

    assert data, f"{export_format} produced no bytes"
    if export_format in ("stl", "obj", "ply", "3mf", "glb"):
        suffix = f".{export_format}"
        assert read_mesh(data, suffix).triangle_count == 12


def test_glb_keeps_the_measurements_it_was_given() -> None:
    """§29: Ein GLB ist zum Zeigen da — und was es zeigt, muss stimmen.

    glTF ist ein Y-oben-Format und Solidon rechnet Z-oben. Wer das beim
    Schreiben oder Lesen einmal zu oft dreht, verschickt ein liegendes Teil.
    """
    original = body()
    back = read_mesh(export_bytes(original, "glb"), ".glb")

    assert back.triangle_count == original.triangle_count
    assert back.volume == pytest.approx(original.volume, rel=1e-6)
    assert back.bounds.size == pytest.approx(original.bounds.size, abs=1e-6)


def test_glb_carries_the_slot_colours() -> None:
    """§20: Ein zweifarbiges Teil, das grau ankommt, zeigt nicht, wofür man
    es verschickt hat."""
    plain = body()
    two_tone = MeshData(raw=plain.raw, slots=tuple(0 if index < 6 else 1 for index in range(12)))
    slots = [
        MaterialSlot(index=0, name="Grundkörper", colour=(1.0, 0.0, 0.0)),
        MaterialSlot(index=1, name="Schrift", colour=(0.0, 0.0, 1.0)),
    ]

    written = trimesh.load(
        BytesIO(export_bytes(two_tone, "glb", slots=slots, name="Schild")),
        file_type="glb",
        force="mesh",
    )
    seen = {tuple(colour[:3]) for colour in written.visual.face_colors}

    assert (255, 0, 0, 255)[:3] in seen
    assert (0, 0, 255, 255)[:3] in seen


def test_a_single_colour_stays_undecided() -> None:
    """Ein Teil ohne Materialslots bekommt keine erfundene Farbe."""
    data = export_bytes(body(), "glb", slots=[MaterialSlot(index=0, name="PLA")])

    assert read_mesh(data, ".glb").triangle_count == 12


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


# --- Einstellungen je Teil (§29, Stufe 4) -------------------------------------------


def test_the_assembly_carries_the_part_names_where_the_slicer_reads_them() -> None:
    """Der Standard hat ein ``name``-Attribut am Objekt, und Solidon schreibt
    es auch — aber die Orca-Familie schreibt es selbst nie und liest die Namen
    aus ``model_settings.config``. Ohne diese Beilage kam eine Baugruppe als
    „Object 1, Object 2" an, obwohl die Namen in der Datei standen.
    """
    parts = [
        threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box((10, 10, 10))), name="Behälter"),
        threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box((5, 5, 5))), name="Deckel"),
    ]

    payload = threemf.write_assembly(parts, "Gewürzset")

    with zipfile.ZipFile(BytesIO(payload)) as container:
        config = container.read(threemf.SETTINGS_PATH).decode("utf-8")
    assert 'key="name" value="Behälter"' in config
    assert 'key="name" value="Deckel"' in config


def test_only_the_part_that_needs_it_gets_the_setting() -> None:
    """Eine Platte hat einen Satz Werte, aber nicht jedes Teil darauf braucht
    dasselbe — ohne diesen Ort gäbe es nur „alle" oder „keiner"."""
    parts = [
        threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box((10, 10, 10))), name="gross"),
        threemf.AssemblyPart(
            mesh=MeshData.of(trimesh.creation.box((5, 5, 5))),
            name="klein",
            settings={"brim_type": "outer_only", "brim_width": "3"},
        ),
    ]

    payload = threemf.write_assembly(parts, "")

    with zipfile.ZipFile(BytesIO(payload)) as container:
        root = ET.fromstring(container.read(threemf.SETTINGS_PATH))
    by_name = {
        node.find("metadata[@key='name']").get("value"): {  # type: ignore[union-attr]
            entry.get("key"): entry.get("value") for entry in node.findall("metadata")
        }
        for node in root.findall("object")
    }
    assert by_name["klein"]["brim_type"] == "outer_only"
    assert "brim_type" not in by_name["gross"]


def _boxed(
    name: str, size: tuple[float, float, float], at: tuple[float, float], slot: str = ""
) -> SceneObject:
    """Ein Quader an einer Stelle der Platte, mit optionalem Materialnamen."""
    raw = trimesh.creation.box(size)
    raw.apply_translation((at[0], at[1], size[2] / 2.0))
    return SceneObject(
        id=name,
        name=name,
        mesh=MeshData.of(raw),
        material_slots=[MaterialSlot(index=0, name=slot)] if slot else [],
    )


def test_two_parts_may_be_apart_and_their_brims_still_collide() -> None:
    """Die Körper haben Luft, der Druck scheitert trotzdem.

    Genau das passierte beim Gewürzset: die Deckelplatte sah in der Rechnung
    frei aus, weil der Brim nicht mitzählte — und zwischen zwei Nachbarn zählt
    er zweimal.
    """
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "adhesion.kind", "brim")
    settings = print_settings.with_path(settings, "adhesion.brim_width", 3.0)
    meshes = [
        (_boxed("links", (10.0, 10.0, 5.0), (0.0, 0.0)).mesh),
        (_boxed("rechts", (10.0, 10.0, 5.0), (14.0, 0.0)).mesh),
    ]

    findings = check_adhesion_clearance(meshes, settings)

    assert [entry.code for entry in findings] == ["arrange.adhesion_too_close"]
    weit = [
        meshes[0],
        (_boxed("weit", (10.0, 10.0, 5.0), (30.0, 0.0)).mesh),
    ]
    assert check_adhesion_clearance(weit, settings) == []


def test_parts_on_different_plates_never_crowd_each_other() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "adhesion.kind", "brim")
    meshes = [
        (_boxed("a", (10.0, 10.0, 5.0), (0.0, 0.0)).mesh),
        (_boxed("b", (10.0, 10.0, 5.0), (11.0, 0.0)).mesh),
    ]

    assert check_adhesion_clearance(meshes, settings, plates=[0, 1]) == []


def test_two_filaments_on_one_plate_are_counted_not_forbidden() -> None:
    """Ein Wechsel ist ein Spülgang je gemeinsamer Schicht. Beim Gewürzset
    waren das hundertzehn — der Behälter 68 mm hoch, der Deckel 22."""
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "layers.layer_height", 0.2)
    objects = [
        _boxed("behaelter", (10.0, 10.0, 68.0), (0.0, 0.0), slot="transluzent"),
        _boxed("deckel", (10.0, 10.0, 22.0), (30.0, 0.0), slot="grau"),
    ]

    findings = check_filament_changes(objects, settings)

    assert [entry.code for entry in findings] == ["arrange.filament_changes"]
    assert findings[0].severity == "info", "eine Rechnung, kein Verbot"
    assert findings[0].values["layers"] == 110
    assert findings[0].values["changes"] == 220


def test_one_filament_costs_no_changes() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    objects = [
        _boxed("a", (10.0, 10.0, 60.0), (0.0, 0.0), slot="grau"),
        _boxed("b", (10.0, 10.0, 20.0), (30.0, 0.0), slot="grau"),
    ]

    assert check_filament_changes(objects, settings) == []


def test_a_plate_is_suggested_per_filament() -> None:
    """Ein Filament je Platte: zwei kosten je gemeinsamer Schicht einen
    Spülgang, und die Rechnung steht in check_filament_changes."""
    objects = [
        _boxed("behaelter", (10.0, 10.0, 68.0), (0.0, 0.0), slot="transluzent"),
        _boxed("basis", (10.0, 10.0, 22.0), (30.0, 0.0), slot="grau"),
        _boxed("scheibe", (10.0, 10.0, 5.0), (60.0, 0.0), slot="grau"),
        _boxed("zweiter", (10.0, 10.0, 68.0), (90.0, 0.0), slot="transluzent"),
    ]

    plates = plates_by_material(objects)

    assert plates["behaelter"] == plates["zweiter"]
    assert plates["basis"] == plates["scheibe"]
    assert plates["behaelter"] != plates["basis"]
    # Reihenfolge nach erstem Auftreten — eine Vorgabe, die zwischen zwei
    # Aufrufen springt, ist keine.
    assert plates["behaelter"] == 0


def test_parts_without_a_named_filament_stay_together() -> None:
    objects = [
        _boxed("a", (10.0, 10.0, 10.0), (0.0, 0.0)),
        _boxed("b", (10.0, 10.0, 10.0), (30.0, 0.0)),
    ]

    assert set(plates_by_material(objects).values()) == {0}


# --- die Anordnung geht nur mit, wenn sie eine ist (§29) ------------------------


def at(x: float, y: float, size: float = 20.0) -> MeshData:
    """Ein Würfel mit seiner Mitte auf (x, y), auf der Platte stehend."""
    cube = trimesh.creation.box((size, size, size))
    cube.apply_translation((x, y, size / 2.0))
    return MeshData.of(cube)


def test_two_parts_side_by_side_are_an_arrangement(profile: Profile) -> None:
    assert arrangement_holds([at(-30.0, 0.0), at(30.0, 0.0)], profile)


def test_parts_on_top_of_each_other_are_not(profile: Profile) -> None:
    """Der Grund für die ganze Prüfung: ohne sie ginge ``--arrange 0`` auch
    dann mit, wenn zwei Teile am selben Platz stehen — und der Slicer druckte
    sie übereinander, statt sie zu retten."""
    assert not arrangement_holds([at(0.0, 0.0), at(5.0, 0.0)], profile)


def test_a_part_outside_the_bed_is_not(profile: Profile) -> None:
    """Der Bauraum des Testprofils ist 256 mm; ein Würfel bei x = 200 ragt
    über die Kante."""
    assert not arrangement_holds([at(200.0, 0.0)], profile)


def test_nothing_at_all_is_no_arrangement(profile: Profile) -> None:
    assert not arrangement_holds([], profile)


def test_the_handover_places_the_parts_the_export_does_not(
    tmp_path: Path, profile: Profile
) -> None:
    """Zwei Zwecke, zwei Dateien: was zum Slicer geht, trägt die Platzierung;
    was der Nutzer exportiert, bleibt im Koordinatensystem des Dokuments —
    sonst läge eine zurückgelesene Platte um den halben Bauraum verschoben im
    nächsten Dokument.
    """
    objects = [scene_object(), scene_object("obj_2", "Zweites")]

    plain, _findings = write_assembly(objects, tmp_path, project_name="export", profile=profile)
    placed, _more = write_assembly(
        objects, tmp_path, project_name="uebergabe", profile=profile, place_on_bed=True
    )

    assert "transform" not in plain.read_bytes().decode("utf-8", errors="replace")
    text = zipfile.ZipFile(BytesIO(placed.read_bytes())).read(threemf.MODEL_PATH).decode("utf-8")
    assert 'transform="1 0 0 0 1 0 0 0 1 128 128 0"' in text


def test_the_handover_to_cura_is_stl_because_curaengine_reads_no_3mf(
    tmp_path: Path, profile: Profile
) -> None:
    """CuraEngine liest kein 3MF — die 3MF-Seite sitzt in Curas Oberfläche.

    Der Slicen-Knopf schrieb trotzdem immer eine 3MF-Baugruppe und reichte sie
    weiter: jeder Lauf endete in „Der Slicer hat keine Druckdatei
    geschrieben", ohne dass irgendwo stand, warum. Derselbe Körper als STL
    läuft durch.
    """
    written, _findings = write_assembly(
        [scene_object()], tmp_path, project_name="uebergabe", profile=profile, flavour="cura"
    )

    assert written.suffix == ".stl"
    assert read_mesh(written.read_bytes(), ".stl").volume > 0.0


def test_the_cura_handover_carries_every_part_of_the_plate(
    tmp_path: Path, profile: Profile
) -> None:
    """Ein Druckauftrag bleibt einer, auch wenn das Format keine Baugruppe kennt."""
    first = scene_object()
    second = scene_object("obj_2", "Zweites")
    second = replace(second, mesh=apply(second.mesh, translation((60.0, 0.0, 0.0))))

    written, _findings = write_assembly(
        [first, second], tmp_path, project_name="uebergabe", profile=profile, flavour="cura"
    )

    joined = read_mesh(written.read_bytes(), ".stl")
    assert joined.volume == pytest.approx(first.mesh.volume + second.mesh.volume, rel=1e-6)
    assert joined.bounds.size[0] > first.mesh.bounds.size[0], "beide Teile, nicht eines"


def test_the_cura_handover_keeps_the_coordinates_of_the_document(
    tmp_path: Path, profile: Profile
) -> None:
    """Ein STL trägt keine Platzierungsmatrix — es hat nur seine Punkte.

    Umso wichtiger ist, dass sie unverschoben bleiben: ``CuraEngine`` bekommt
    ``machine_center_is_zero``, rechnet also dieselbe Welt wie Solidon.
    """
    written, _findings = write_assembly(
        [scene_object()],
        tmp_path,
        project_name="uebergabe",
        profile=profile,
        flavour="cura",
        place_on_bed=True,
    )

    before = scene_object().mesh.bounds.centre
    centre = read_mesh(written.read_bytes(), ".stl").bounds.centre
    assert centre[0] == pytest.approx(before[0], abs=0.01)
    assert centre[1] == pytest.approx(before[1], abs=0.01)


def test_only_the_orca_family_wants_bed_coordinates(tmp_path: Path, profile: Profile) -> None:
    """Wer um den Ursprung rechnet, darf die Teile nicht ans Bett schieben.

    Solidon rechnet zentriert, und für Cura wie für PrusaSlicer schreibt die
    Übergabe genau das: ``machine_center_is_zero`` beim einen, eine Bettform
    von ``-128`` bis ``128`` beim anderen. Die Verschiebung um den halben
    Bauraum kam trotzdem — gemessen im G-Code lag ein Würfel, den das Dokument
    bei −10 … 10 hat, bei 110,9 … 137,8. PrusaSlicer lehnte ihn gleich ganz ab
    („All objects are outside of the print volume"), Cura druckte ihn
    schweigend woanders. Nur die Orca-Familie misst von der Ecke.
    """
    for flavour in ("cura", "prusa"):
        written, _findings = write_assembly(
            [scene_object()],
            tmp_path / flavour,
            project_name="uebergabe",
            profile=profile,
            flavour=flavour,  # type: ignore[arg-type]
            place_on_bed=True,
        )
        if flavour == "cura":
            centre = read_mesh(written.read_bytes(), ".stl").bounds.centre
            assert centre[0] == pytest.approx(0.0, abs=0.01), flavour
        else:
            text = zipfile.ZipFile(BytesIO(written.read_bytes())).read(threemf.MODEL_PATH)
            assert b"transform" not in text, flavour

    orca, _findings = write_assembly(
        [scene_object()],
        tmp_path / "orca",
        project_name="uebergabe",
        profile=profile,
        flavour="orca",
        place_on_bed=True,
    )
    text = zipfile.ZipFile(BytesIO(orca.read_bytes())).read(threemf.MODEL_PATH).decode("utf-8")
    assert 'transform="1 0 0 0 1 0 0 0 1 128 128 0"' in text
