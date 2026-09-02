"""Export und die Prüfung, die davor läuft (Bauplan §29, §16.3)."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from typing import get_args
from xml.etree import ElementTree as ET

import pytest
import trimesh

from app.core.errors import FileWriteError, NeedsSolidError, ValidationError
from app.core.export import handover, slicer_keys, threemf
from app.core.export.handover import with_slot_profiles
from app.core.export.slicer_keys import SlicerFlavour, wants_bed_coordinates
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
from app.core.geom.prepare import check_build_volume
from app.core.geom.transform import apply, place_on_bed, translation
from app.core.ingest import threemf as threemf_reader
from app.core.ingest.loader import normalise, read_model
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


def test_two_parts_that_would_share_a_name_are_numbered(profile: Profile) -> None:
    """H2: zwei Objekte, die auf denselben Dateinamen fallen, überschrieben
    sich — eine Datei, zwei Erfolgsmeldungen, das erste Teil weg. Ein Schema
    ohne unterscheidendes Feld (hier ``{object}`` bei zwei gleichnamigen Körpern)
    bekommt jetzt eine laufende Nummer, statt sich zu überschreiben.
    """
    objects = [scene_object("obj_1", "Halterung"), scene_object("obj_2", "Halterung")]

    plan = plan_export(objects, project_name="P", profile=profile, scheme="{object}")

    names = [entry.filename for entry in plan.entries]
    assert names == ["Halterung-1.stl", "Halterung-2.stl"]
    assert len(set(names)) == 2, "keine zwei Dateien mit demselben Namen"


def test_a_typo_in_the_scheme_names_the_placeholders(profile: Profile) -> None:
    """``--scheme "{name}"`` endete in einem rohen ``KeyError``.

    Das Schema ist eine Eingabe des Nutzers — in der Kommandozeile getippt, im
    Dialog eingetragen —, und der Platzhalter heißt ``{object}``. Ein
    Stapelabzug sagt ihm das nicht; er sagt ihm nicht einmal, dass er selbst
    etwas ändern kann (§2.7, Regel 17).
    """
    with pytest.raises(ValidationError) as falsch:
        plan_export(
            [scene_object()],
            project_name="Projekt",
            profile=profile,
            scheme="{name}_{index}",
        )

    assert falsch.value.field == "scheme"
    assert falsch.value.values["requested"] == "{name}"
    known = str(falsch.value.values["known"])
    for platzhalter in ("{project}", "{object}", "{index}", "{count}", "{plate}"):
        assert platzhalter in known, platzhalter
    assert falsch.value.suggestions


def test_a_scheme_with_a_stray_brace_says_so(profile: Profile) -> None:
    """Der zweite Weg, dasselbe falsch zu tippen — und er wirft eine andere
    Ausnahme, die genauso roh durchflog."""
    with pytest.raises(ValidationError) as kaputt:
        plan_export([scene_object()], project_name="Projekt", profile=profile, scheme="{project")

    assert kaputt.value.constraint == "broken_scheme"
    assert kaputt.value.suggestions


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

    assert "arrange.below_bed" in {finding.code for finding in findings}


def test_a_part_below_the_bed_is_not_called_too_big(profile: Profile) -> None:
    """Der häufigste Fall von Weg 1 bekam den irreführendsten Satz.

    Ein heruntergeladenes Teil ist meist um den Ursprung zentriert und liegt
    darum zur Hälfte unter der Platte — ein 8 mm hohes Teil auf einem
    256-mm-Drucker. „Steht über den Bauraum hinaus" schickt den Nutzer zum
    Skalieren, obwohl ein Aufsetzen genügt.

    **Und die Kennung sagt es mit.** Sie tat es nicht, und der Prüfbericht
    hängt seine Handlungen an ihr auf: Damit bekam der verrutschte Körper
    *Modell teilen* und *Auf den Bauraum verkleinern* angeboten — zwei
    Handlungen, die hier nichts ausrichten (``FINDING_ACTIONS``).
    """
    sunk = normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh
    findings = check_before_export([scene_object(mesh=sunk)], profile, {})

    said = str(next(f.message for f in findings if f.code == "arrange.below_bed"))
    assert "unter dem Druckbett" in said
    assert "hinaus" not in said, "das ist der Satz für zu groß"
    assert "arrange.out_of_build_volume" not in {f.code for f in findings}, (
        "the too-big code belongs to the case that really is too big"
    )


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
    """Ein Würfel 400 mm neben dem Bett wird gemeldet — und zwar als **Lage**.

    Er ist 20 mm groß und passt zehnmal auf das Bett; was hilft, ist ein Klick
    auf *Auf dem Bett anordnen*. „Steht über den Bauraum hinaus" hieße „zu
    groß" und bot *Modell teilen* und *Verkleinern* an (``_fits_at_all``).
    """
    far = apply(body(), translation((400.0, 0.0, 0.0)))
    findings = check_before_export([scene_object(mesh=far)], profile, {})

    assert "arrange.off_the_plate" in {finding.code for finding in findings}
    assert "arrange.out_of_build_volume" not in {finding.code for finding in findings}


def test_before_writing_a_misplaced_part_is_a_warning(profile: Profile) -> None:
    """Derselbe Körper, zwei Anlässe, zwei Schweregrade — und das ist Absicht.

    Im Editor ist eine falsche Lage ein Hinweis: ein Klick auf *Auf dem Bett
    anordnen* behebt sie, und stünde dort eine Warnung, warnte fast jede
    geladene Datei (`_severity_for`). Vor dem **Schreiben** fällt genau diese
    Voraussetzung weg — der Klick ist nicht passiert, und was jetzt entsteht,
    ist eine Datei. Gemessen: CuraEngine prüft den Bauraum nicht und schreibt
    eine Druckdatei, die neben der Platte druckt.

    Gesperrt wird trotzdem nichts (§29) — der Befund steht nur nicht mehr
    zwischen zwei Dutzend Hinweisen.
    """
    verschoben = apply(body(), translation((400.0, 0.0, 0.0)))
    im_editor = check_build_volume([verschoben], profile)
    vor_dem_schreiben = check_before_export([scene_object(mesh=verschoben)], profile, {})

    assert [finding.severity for finding in im_editor] == ["info"], "im Editor behebt ein Klick es"
    schwer = [
        finding.severity for finding in vor_dem_schreiben if finding.code == "arrange.off_the_plate"
    ]
    assert schwer == ["warning"], vor_dem_schreiben


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


def test_two_same_named_parts_write_two_files(tmp_path: Path, profile: Profile) -> None:
    """Die Kollisionsauflösung schreibt wirklich zwei Dateien — nicht eine, über
    die zweimal Erfolg gemeldet wird."""
    objects = [scene_object("obj_1", "Halterung"), scene_object("obj_2", "Halterung")]
    plan = plan_export(objects, project_name="P", profile=profile, scheme="{object}")

    written = write_plan(plan, tmp_path)

    assert len(written) == 2
    assert len(set(written)) == 2, "zwei verschiedene Pfade"
    assert len(list(tmp_path.glob("*.stl"))) == 2, "zwei Dateien auf der Platte"


@pytest.mark.parametrize("export_format", ["stl", "3mf", "obj", "ply", "glb"])
def test_every_format_writes_something_readable(export_format: str, profile: Profile) -> None:
    data = export_bytes(body(), export_format)  # type: ignore[arg-type]

    assert data, f"{export_format} produced no bytes"
    if export_format in ("stl", "obj", "ply", "3mf", "glb"):
        suffix = f".{export_format}"
        assert read_model(data, suffix).triangle_count == 12


def test_glb_keeps_the_measurements_it_was_given() -> None:
    """§29: Ein GLB ist zum Zeigen da — und was es zeigt, muss stimmen.

    Der glTF-2.0-Standard verlangt in seinem Abschnitt 3.5 ein Y-oben-Format,
    Solidon rechnet Z-oben, und der
    Schreiber dreht deshalb (``writer._glb_bytes``). Der Leser dreht
    **bewusst nicht** zurück — die Begründung steht in ``read_mesh`` —, also
    kommt die Höhe auf der Y-Achse wieder herein. Der Körper selbst bleibt
    derselbe: gleiche Dreiecke, gleiches Volumen, dieselben drei Kantenmaße.

    Gemessen an einem Quader statt am Würfel des Korpus: Bei drei gleichen
    Kanten ist jede Drehung unsichtbar, und der Test bliebe grün, gleich wie
    oft jemand dreht.
    """
    original = MeshData.of(trimesh.creation.box(extents=(10.0, 20.0, 40.0)))
    back = read_mesh(export_bytes(original, "glb"), ".glb")

    assert back.triangle_count == original.triangle_count
    assert back.volume == pytest.approx(original.volume, rel=1e-6)
    assert back.bounds.size == pytest.approx((10.0, 40.0, 20.0), abs=1e-6)


def test_glb_carries_the_slot_colours() -> None:
    """§20: Ein zweifarbiges Teil, das grau ankommt, zeigt nicht, wofür man
    es verschickt hat."""
    plain = body()
    two_tone = MeshData(raw=plain.raw, slots=tuple(0 if index < 6 else 1 for index in range(12)))
    slots = [
        MaterialSlot(index=0, name="Grundkörper", colour=(1.0, 0.0, 0.0)),
        MaterialSlot(index=1, name="Schrift", colour=(0.0, 0.0, 1.0)),
    ]

    written = trimesh.load_mesh(
        BytesIO(export_bytes(two_tone, "glb", slots=slots, name="Schild")),
        file_type="glb",
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
    assert threemf_reader.count_objects(written.read_bytes()) == 2


def test_the_assembly_carries_the_object_names(tmp_path: Path, profile: Profile) -> None:
    objects = [scene_object("obj_1", "Deckel"), scene_object("obj_2", "Boden")]

    written, _findings = write_assembly(objects, tmp_path, project_name="x", profile=profile)

    assert [part.name for part in threemf_reader.read_objects(written.read_bytes())] == [
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

    assert threemf_reader.count_objects(written.read_bytes()) == 1


def test_without_a_named_plate_every_plate_goes_in(tmp_path: Path, profile: Profile) -> None:
    """Und ohne Einschränkung kommen alle hinein — mit ihrer Platte dazu.

    Die Orca-Familie legt ihre Platten in einem Koordinatenraum nebeneinander.
    Ohne den Versatz stünde die zweite auf der ersten: Beide fangen am selben
    Bettursprung an, und am modularen Besteckkorb überlagerten sich zwei
    Platten um neunundzwanzig Millimeter.

    Der Abstand ist gemessen und nicht gewählt — siehe ``PLATE_STRIDE``. Hier
    steht die Gegenprobe: Zwei gleiche Teile auf zwei Platten liegen um genau
    eine Bettbreite plus ein Achtel auseinander.
    """
    erste = scene_object("obj_1", "Vorne")
    zweite = scene_object("obj_2", "Naechste")
    zweite.plate = 1

    written, _findings = write_assembly(
        [erste, zweite], tmp_path, project_name="x", profile=profile
    )

    payload = written.read_bytes()
    assert threemf_reader.count_objects(payload) == 2, "beide Teile in einer Datei"

    beilage = zipfile.ZipFile(BytesIO(payload)).read(threemf.SETTINGS_PATH).decode("utf-8")
    assert beilage.count("<plate>") == 2, "und beide Platten benannt"

    # Die erste Platte steht, wo sie steht, und bekommt gar keine Matrix — eine
    # Verschiebung um null wäre eine Angabe ohne Aussage. Verschoben ist nur,
    # was auf die zweite gehört.
    model = zipfile.ZipFile(BytesIO(payload)).read(threemf.MODEL_PATH).decode("utf-8")
    offsets = [float(entry.split()[9]) for entry in re.findall(r'transform="([^"]+)"', model)]
    width = profile.printer.build_volume[0]
    assert offsets == [pytest.approx(width * threemf.PLATE_STRIDE)]


def test_an_empty_plate_says_so(tmp_path: Path, profile: Profile) -> None:
    with pytest.raises(ValidationError):
        write_assembly([scene_object()], tmp_path, project_name="x", profile=profile, plate=7)


def test_the_assembly_reports_before_writing(tmp_path: Path, profile: Profile) -> None:
    """§29: die Prüfung vor dem Export berichtet, sie blockiert nicht."""
    objects = [scene_object("obj_1", "Teil", mesh=body("broken_open.stl"))]

    written, findings = write_assembly(objects, tmp_path, project_name="x", profile=profile)

    assert written.is_file(), "geschrieben wird trotzdem"
    assert findings, "aber der Befund steht dabei"


@pytest.mark.parametrize("flavour", ["orca", "cura"])
def test_an_assembly_that_cannot_be_written_names_the_way_out(
    tmp_path: Path, profile: Profile, flavour: str
) -> None:
    """Ein ``OSError`` ist kein Programmfehler, sondern ein Ziel, das nicht
    geht (§2.7).

    ``write_plan`` wandelt ihn seit je; die Baugruppe daneben tat es nicht —
    dieselbe Handlung, zwei Antworten. In der Kommandozeile endete sie in
    einem Stapelabzug, im Fenster stiller und schlimmer: Der Export-Arbeiter
    fängt ``AppError``, ein ``OSError`` riss den Thread ab, und danach geschah
    gar nichts mehr.

    Beide Wege, denn es sind zwei Schreibstellen: die Orca-Familie bekommt
    eine 3MF, CuraEngine ein STL.
    """
    versperrt = tmp_path / "platte"
    versperrt.write_bytes(b"eine Datei, kein Ordner")

    with pytest.raises(FileWriteError) as gescheitert:
        write_assembly(
            [scene_object()],
            versperrt,
            project_name="Projekt",
            profile=profile,
            flavour=flavour,  # type: ignore[arg-type]
        )

    assert gescheitert.value.suggestions, "Regel 17"
    assert gescheitert.value.detail, "der Grund des Betriebssystems steht dabei"


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


def test_a_prusa_assembly_carries_its_settings(tmp_path: Path, profile: Profile) -> None:
    """Eine exportierte 3MF soll man drucken können, nicht erst einrichten.

    Für die Orca-Familie war das längst so; für PrusaSlicer trug dieselbe
    Datei nur Geometrie, und beim Öffnen galt das Profil, das gerade
    eingestellt war. Er liest seine Einstellungen aus einer eigenen Beilage —
    gemessen: ohne ``--load`` geslict kamen Solidons Werte an.
    """
    settings = print_settings.resolve(profile)
    target, _findings = write_assembly(
        [scene_object()],
        tmp_path,
        project_name="Halter",
        profile=profile,
        settings=settings,
        flavour="prusa",
    )

    with zipfile.ZipFile(target) as container:
        config = container.read(threemf.PRUSA_CONFIG_PATH).decode("utf-8")
    lines = config.splitlines()
    assert lines[0] == threemf.PRUSA_CONFIG_HEADER, (
        "die erste Zeile überspringt PrusaSlicer — ohne Kopf fehlt der erste Wert"
    )
    written = {
        line.split("=", 1)[0].removeprefix(";").strip(): line.split("=", 1)[1].strip()
        for line in lines[1:]
        if "=" in line
    }
    assert written["perimeters"] == str(settings.shell.wall_count)
    assert written["first_layer_temperature"] == str(settings.temperature.nozzle_first_layer)


def test_a_filament_keeps_its_extruder_across_the_plates_of_one_job() -> None:
    """Vier Spulen sind nicht vier Farben desselben Materials — und eine Farbe
    ist nicht auf jeder Platte ein anderer Extruder.

    ``merge_slots`` nummeriert nach dem ersten Auftreten, und der Export ruft
    es **je Platte**. Damit lag dieselbe Farbe in einem Auftrag an
    verschiedenen Düsen: Platte 1 nur Rot (Extruder 0), Platte 2 Weiß und Rot
    (Rot dann Extruder 1). Wer den Auftrag am Stück druckt, müsste mittendrin
    umstecken — und merkt es an der zweiten Platte.

    Die Zuordnung gehört deshalb dem **Auftrag**: Wer alle Platten kennt,
    nummeriert einmal für alle. ``across`` nimmt die Teile des ganzen Auftrags
    und gibt die gemeinsame Belegung; ohne Angabe bleibt es beim alten
    Verhalten je Platte, denn eine einzelne exportierte Platte *ist* der
    Auftrag.
    """
    red = MaterialSlot(index=1, name="Rot")
    white = MaterialSlot(index=1, name="Weiß")
    red_again = MaterialSlot(index=2, name="Rot")

    first = [threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box()), name="A", slots=(red,))]
    second = [
        threemf.AssemblyPart(
            mesh=MeshData.of(trimesh.creation.box()), name="B", slots=(white, red_again)
        )
    ]

    whole_job = [*first, *second]
    plate_one = threemf.merge_slots(first, across=whole_job)
    plate_two = threemf.merge_slots(second, across=whole_job)

    def extruder_of(name: str, slots: list[MaterialSlot]) -> int:
        return next(slot.index for slot in slots if str(slot.name) == name)

    assert extruder_of("Rot", plate_one) == extruder_of("Rot", plate_two), (
        "dieselbe Farbe, derselbe Extruder — sonst wird mitten im Auftrag umgesteckt"
    )
    assert extruder_of("Rot", plate_one) != extruder_of("Weiß", plate_two), (
        "und zwei Farben teilen sich keine Düse"
    )


def test_the_exported_plates_of_one_job_agree_on_the_extruders(
    profile: Profile, tmp_path: Path
) -> None:
    """Der Anschluss: Die Zusage wird im **Export** eingelöst, nicht in
    ``merge_slots``.

    Der Test daneben prüft die Zählung; dieser prüft, dass der Weg dorthin sie
    auch benutzt. Ohne das könnte ``across`` richtig rechnen und der Export es
    trotzdem nie mitgeben — genau die Sorte Lücke, die die Testart „Anschluss"
    meint: nicht „die Funktion kann es", sondern „die Anwendung tut es".
    """
    red = MaterialSlot(index=1, name="Rot")
    white = MaterialSlot(index=1, name="Weiß")
    red_again = MaterialSlot(index=2, name="Rot")
    objects = [
        SceneObject(
            id="obj_1",
            name="A",
            mesh=MeshData.of(trimesh.creation.box((10, 10, 10))),
            material_slots=[red],
            plate=0,
        ),
        SceneObject(
            id="obj_2",
            name="B",
            mesh=MeshData.of(trimesh.creation.box((10, 10, 10))),
            material_slots=[white, red_again],
            plate=1,
        ),
    ]

    def extruders(plate: int) -> dict[str, int]:
        target, _findings = write_assembly(
            objects,
            tmp_path / f"platte{plate}",
            project_name="auftrag",
            profile=profile,
            plate=plate,
        )
        with zipfile.ZipFile(target) as container:
            root = ET.fromstring(container.read(threemf.MODEL_PATH))
        found: dict[str, int] = {}
        for index, node in enumerate(root.iter()):
            label = node.get("name")
            if label and node.tag.endswith("base"):
                found[label] = index
        return found

    first, second = extruders(0), extruders(1)

    assert "Rot" in first and "Rot" in second, "beide Platten führen die Farbe"
    order_first = sorted(first, key=lambda name: first[name])
    order_second = sorted(second, key=lambda name: second[name])
    assert order_first.index("Rot") == order_second.index("Rot"), (
        "dieselbe Farbe steht in beiden Dateien an derselben Extruderstelle"
    )


def test_the_chosen_filament_profile_follows_the_colour_not_the_position() -> None:
    """Die zweite Hälfte der Extruderfrage — und die teurere.

    ``slot_profiles`` und ``slot_overrides`` sind **positionsbasiert**: Der
    Kunde wählt im Dialog „Position 0 druckt mit PETG-Rot", und
    ``with_slot_profiles`` heftet den Namen an den Slot an dieser Stelle. Das
    ist richtig — solange die Stelle für den ganzen Auftrag dieselbe bedeutet.

    Solange jede Platte für sich nummerierte, tat sie das nicht: Auf Platte 2
    stand an Position 0 Weiß statt Rot, und der Kunde bekam sein
    Rot-Profil auf das weiße Filament gedruckt. Das ist schlimmer als eine
    vertauschte Düse — die Temperatur stimmt dann nicht mehr.

    Der Auftrag als Zählung (``across``) behebt es, ohne dass die
    Positionslogik angefasst werden muss: Wenn die Reihenfolge über alle
    Platten gleich ist, meint Position 0 überall dasselbe Filament.
    """
    red = MaterialSlot(index=1, name="Rot")
    white = MaterialSlot(index=1, name="Weiß")
    red_again = MaterialSlot(index=2, name="Rot")
    job = [
        threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box()), name="A", slots=(red,)),
        threemf.AssemblyPart(
            mesh=MeshData.of(trimesh.creation.box()), name="B", slots=(white, red_again)
        ),
    ]
    chosen = ["PETG-Rot", "PLA-Weiss"]

    def profile_of(colour: str, plate: list[threemf.AssemblyPart]) -> str | None:
        slots = with_slot_profiles(threemf.merge_slots(plate, across=job), chosen)
        return next(slot.material for slot in slots if str(slot.name) == colour)

    assert profile_of("Rot", [job[0]]) == profile_of("Rot", [job[1]]) == "PETG-Rot", (
        "dasselbe Filament bekommt auf jeder Platte dasselbe Profil"
    )
    assert profile_of("Weiß", [job[1]]) == "PLA-Weiss"
    assert profile_of("Weiß", [replace(job[1], slots=(white,))]) == "PLA-Weiss", (
        "auch eine Platte mit nur dem späteren Auftragsslot behält dessen Profil"
    )


def test_an_exported_3mf_carries_each_filaments_temperature(
    profile: Profile, tmp_path: Path
) -> None:
    """Der Anschluss vom Projektwert bis in die exportierte Kundendatei.

    ``write_config`` konnte bereits je Extruder schreiben. Der direkte
    3MF-Export ging aber an diesem Weg vorbei und legte nur den gemeinsamen
    PETG-Satz in ``project_settings.config`` ab. Eine PLA-Schrift kam dadurch
    mit der richtigen Farbe und der falschen Temperatur im Slicer an.
    """
    from app.core.types import SlotOverride

    black = MaterialSlot(index=0, name="PETG Schwarz", colour=(0.05, 0.05, 0.05))
    white = MaterialSlot(index=0, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    objects = [
        SceneObject(id="body", name="Gehäuse", mesh=body(), material_slots=[black]),
        SceneObject(id="label", name="Schrift", mesh=body(), material_slots=[white]),
    ]
    settings = print_settings.resolve(profile)
    pla_temperature = replace(settings.temperature, nozzle=210, nozzle_first_layer=215)
    settings = replace(
        settings,
        slot_overrides=(
            SlotOverride(
                name=white.name,
                colour=white.colour,
                temperature=pla_temperature,
            ),
        ),
    )

    written, _findings = write_assembly(
        objects,
        tmp_path,
        project_name="Schild",
        profile=profile,
        settings=settings,
        flavour="orca",
    )

    with zipfile.ZipFile(written) as archive:
        embedded = json.loads(archive.read(threemf.PROJECT_SETTINGS_PATH))
    assert embedded["nozzle_temperature"] == [
        str(settings.temperature.nozzle),
        "210",
    ]
    assert embedded["nozzle_temperature_initial_layer"] == [
        str(settings.temperature.nozzle_first_layer),
        "215",
    ]
    imported = threemf_reader.read_objects(written.read_bytes())
    assert [[str(slot.name) for slot in part.slots] for part in imported] == [
        ["PETG Schwarz"],
        ["PLA Weiß"],
    ], "der Import liest dieselben benannten Filamente zurück"
    for part, expected in zip(imported, (black, white), strict=True):
        assert part.slots[0].colour == pytest.approx(expected.colour, abs=1 / 255), (
            "auch die sichtbaren Spulenfarben überstehen den Reimport"
        )


def test_a_direct_3mf_export_uses_each_chosen_filament_profile(
    profile: Profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Profilwahl aus dem Druckdialog gilt auch beim normalen Export.

    Der Slicerlauf heftete die Namen bereits an die Slots; der direkte Export
    ging an diesem Schritt vorbei und nahm für beide Spulen das eine
    Basisprofil. Eine PLA-Schrift erbte dadurch die PETG-Temperatur, solange
    der Kunde nicht zusätzlich dieselbe Temperatur von Hand übersteuerte.
    """
    from app.core.export import slicer_profiles

    petg_path = tmp_path / "Haus PETG.json"
    petg_path.write_text(
        json.dumps(
            {
                "name": "Haus PETG",
                "nozzle_temperature": ["240"],
                "filament_max_volumetric_speed": ["5"],
            }
        ),
        encoding="utf-8",
    )
    pla_path = tmp_path / "Haus PLA.json"
    pla_path.write_text(
        json.dumps(
            {
                "name": "Haus PLA",
                "nozzle_temperature": ["210"],
                "filament_max_volumetric_speed": ["21"],
            }
        ),
        encoding="utf-8",
    )
    available = [
        slicer_profiles.SlicerProfile(path=petg_path, name="Haus PETG", kind="filament"),
        slicer_profiles.SlicerProfile(path=pla_path, name="Haus PLA", kind="filament"),
    ]
    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *_args, **_kwargs: available)

    black = MaterialSlot(index=0, name="PETG Schwarz", colour=(0.05, 0.05, 0.05))
    white = MaterialSlot(index=1, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    objects = [
        SceneObject(id="body", name="Gehäuse", mesh=body(), material_slots=[black]),
        SceneObject(id="label", name="Schrift", mesh=body(), material_slots=[white]),
    ]
    settings = replace(
        print_settings.resolve(profile),
        slot_profiles=("Haus PETG", "Haus PLA"),
    )
    setup = handover.SlicerSetup(
        executable=tmp_path / "orca.exe",
        flavour="orca",
        base_filament="Haus PETG",
    )

    written, _findings = write_assembly(
        objects,
        tmp_path,
        project_name="Schild mit Profilen",
        profile=profile,
        settings=settings,
        flavour="orca",
        setup=setup,
    )

    with zipfile.ZipFile(written) as archive:
        embedded = json.loads(archive.read(threemf.PROJECT_SETTINGS_PATH))
    assert embedded["nozzle_temperature"] == ["240", "210"]
    assert embedded["filament_max_volumetric_speed"] == ["5", "21"]


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


def test_two_filaments_on_separate_plates_cost_no_changes() -> None:
    """Getrennte Platten werden nacheinander gedruckt, nie schichtweise.

    Der Export einer mehrplattigen 3MF übergibt ``plate=None``. Bis hier jede
    Farbe trotzdem gemeinsam gezählt wurde, meldete die fertige
    CC2-Werkzeugbox 230 Filamentwechsel, obwohl jede Platte genau eine Farbe
    trägt.
    """
    settings = print_settings.resolve(profiles.make_profile())
    objects = [
        replace(
            _boxed("weiss", (10.0, 10.0, 23.0), (0.0, 0.0), slot="weiß"),
            plate=0,
        ),
        replace(
            _boxed("schwarz", (10.0, 10.0, 27.0), (0.0, 0.0), slot="schwarz"),
            plate=1,
        ),
    ]

    assert check_filament_changes(objects, settings) == []


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


def at(x: float, y: float, size: float = 20.0, z: float = 0.0) -> MeshData:
    """Ein Würfel mit seiner Mitte auf (x, y), auf der Platte stehend.

    ``z`` hebt oder senkt ihn — die Unterkante liegt dann dort statt auf null.
    """
    cube = trimesh.creation.box((size, size, size))
    cube.apply_translation((x, y, size / 2.0 + z))
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


def test_a_part_sunk_into_the_bed_is_no_arrangement(profile: Profile) -> None:
    """Geprüft wurde nur nach oben — und die Anordnung wird beim Slicer
    **durchgesetzt** (``--arrange 0``).

    Ein Teil bei z = -15 steckt zur Hälfte im Druckbett. Der Slicer ordnet
    nicht an, weil Solidon sagt, die Anordnung halte; er schneidet ab, was
    unter null liegt, und druckt einen halben Körper. Die Grenze ist dieselbe
    wie in ``check_build_volume``: unter dem Bett ist unter dem Bett.
    """
    assert not arrangement_holds([at(0.0, 0.0, z=-15.0)], profile)
    assert not arrangement_holds([at(-30.0, 0.0), at(30.0, 0.0, z=-15.0)], profile)


def test_a_floating_part_is_no_arrangement(profile: Profile) -> None:
    """Und die andere Richtung: Ein Teil bei z = 50 hängt in der Luft.

    Mit übernommener Anordnung druckt der Slicer es dort — fünfzig Millimeter
    Stützmaterial oder ein Klumpen auf der Platte. Wird stattdessen ihm das
    Anordnen überlassen, setzt er es ab, und genau dafür gibt es diese
    Prüfung.

    Die Grenze ist die von ``prepare._floats``: ein Hundertstelmillimeter ist
    Rundung, darüber ist ein Spalt.
    """
    assert not arrangement_holds([at(0.0, 0.0, z=50.0)], profile)
    assert arrangement_holds([at(0.0, 0.0, z=0.005)], profile), "Rundung ist kein Schweben"


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


def test_every_flavour_answers_every_property() -> None:
    """Jede Familie hat zu jeder Eigenschaft eine Antwort — und sie steht hier.

    Die Prädikate in ``slicer_keys`` sind der eine Ort, an dem einer
    Slicer-Familie eine Eigenschaft zugeordnet wird. Diese Tabelle ist ihr
    Gegenstück im Test: Sie schreibt den Bestand fest, damit ein Prädikat sich
    nicht unbemerkt umdreht, und sie ist die Liste, die jemand ausfüllen muss,
    der eine vierte Familie einführt.

    Der Bestand ist ausdrücklich **kein** Muster: Sechs der sieben Zeilen
    trennen die Orca-Familie von den anderen beiden, und wer daraus „Orca kann
    alles" liest, hat die Ursache verwechselt. Sie kann es, weil sie ihre
    Profile als Dateien führt, die Solidon lesen kann; Cura führt seine
    Einstellungen ausschließlich auf der Kommandozeile, und PrusaSlicer legt
    keine Profile ab, die eine Auswahl trügen.

    Gegenprobe gefahren: Jedes der sieben Prädikate einmal auf ``True``
    festgenagelt, jedes Mal wird diese Tabelle rot.
    """
    expected: dict[str, dict[SlicerFlavour, bool]] = {
        "wants_bed_coordinates": {"prusa": False, "orca": True, "cura": False},
        "has_user_profile_tree": {"prusa": False, "orca": True, "cura": False},
        "has_filament_profiles": {"prusa": False, "orca": True, "cura": False},
        "reads_settings_from_project_file": {"prusa": False, "orca": True, "cura": False},
        "names_its_own_output": {"prusa": False, "orca": True, "cura": False},
        "has_readable_profiles": {"prusa": False, "orca": True, "cura": True},
        "reads_assembly_file": {"prusa": True, "orca": True, "cura": False},
    }
    flavours = set(get_args(SlicerFlavour))
    assert len(flavours) >= 3, f"zu wenige Familien gefunden: {flavours}"

    for name, answers in expected.items():
        assert set(answers) == flavours, f"{name}: Tabelle und Literal weichen ab"
        predicate = getattr(slicer_keys, name)
        for flavour, wanted in answers.items():
            assert predicate(flavour) is wanted, f"{name}({flavour})"


def test_the_bed_box_asks_the_same_source_as_the_handover(profile: Profile) -> None:
    """Wo das Bett liegt, wird an einer Stelle entschieden, nicht an zweien.

    Der Test darüber prüft, *dass* nur die Orca-Familie von der Ecke misst.
    Dieser hier prüft, dass beide Stellen, die das wissen müssen, dieselbe
    Quelle fragen: ``wants_bed_coordinates``. ``bed_box`` verglich lange
    selbst gegen ``"orca"`` — dieselbe Frage, zweimal formuliert, und der
    Docstring beschrieb sie beide Male mit denselben Worten.

    Auseinander laufen sie erst bei einer vierten Familie, und dann teuer:
    Der Bettkasten, gegen den ``off_the_bed`` prüft, stünde in der einen
    Welt, die geschriebene Datei in der anderen. Ein Druck, der um den
    halben Bauraum danebenliegt, käme dann durch eine Prüfung, die genau
    das verhindern soll.

    **Was dieser Test leistet und was nicht — gemessen, nicht angenommen.**
    Die erwartete Gegenprobe „Quelle mutieren, Test wird rot" schlägt fehl,
    und zwar zu Recht: Lesen beide Stellen dieselbe Quelle, können sie nicht
    mehr auseinanderlaufen, und die Zusicherung ist nach dem Fix eine
    Tautologie. Drei Lagen gefahren:

    ===========================================  ======
    Quelle unverändert, ``bed_box`` fragt sie    grün
    Quelle sagt auch ``cura``, ``bed_box``       grün
    fragt sie
    Quelle sagt auch ``cura``, ``bed_box``       **rot**
    vergleicht den Namen
    ===========================================  ======

    Er ist damit kein Verhaltenstest, sondern ein **Regressionswächter**: Er
    wird genau dann rot, wenn jemand den Namensvergleich zurückholt, während
    die Quelle etwas anderes sagt. Das ist die Zusage, die hier gebraucht
    wird — den Fall „nur die Orca-Familie misst von der Ecke" prüft der Test
    darüber, und zwar am geschriebenen Ergebnis.
    """
    flavours = get_args(SlicerFlavour)
    assert len(flavours) >= 3, f"zu wenige Familien gefunden: {flavours}"

    for flavour in flavours:
        box = handover.bed_box(profile, flavour)
        from_the_corner = box.minimum == (0.0, 0.0, 0.0)
        assert from_the_corner == wants_bed_coordinates(flavour), flavour


def _solid(object_id: str = "obj_2", name: str = "Flansch") -> SceneObject:
    """Ein Körper, der seine Flächen kennt — als Attrappe, ohne OpenCASCADE.

    ``BRepBody`` ist ein Protokoll (§30), und ``kind_of`` prüft es zur
    Laufzeit. Zwei Methoden reichen also, und der Test läuft auch dort, wo der
    zweite Kern nicht installiert ist.
    """

    class Attrappe:
        @property
        def shape(self) -> object:
            return object()

        def to_mesh(self) -> object:
            return body()

    return SceneObject(id=object_id, name=name, mesh=Attrappe())  # type: ignore[arg-type]


def test_a_mesh_exported_as_step_is_told_before_the_file_is_written(
    profile: Profile,
) -> None:
    """**Der Plan war ohne einen Befund, und der Fehler kam beim Schreiben.**

    Wer ``teil.step`` tippte, wählte Format, Ordner und Namen — und erfuhr erst
    danach, dass ein Netz keine Flächen hat. Die Auskunft war die ganze Zeit
    verfügbar: Der Körper weiß, ob er exakt ist, und das Format weiß, ob es das
    braucht.

    Das Fenster bietet STEP inzwischen nur an, wenn ein exakter Körper dabei
    ist; die Kommandozeile hat keinen Dialog, der etwas ausgraut, und zeigt die
    Befunde des Plans **vor** dem Schreiben.
    """
    plan = plan_export(
        [scene_object()], project_name="Projekt", profile=profile, export_format="step"
    )

    codes = {finding.code for finding in plan.findings}
    assert "export.needs_solid" in codes
    finding = next(entry for entry in plan.findings if entry.code == "export.needs_solid")
    assert finding.severity == "error"
    assert finding.object_id == "obj_1", "welcher Körper es ist"
    gesagt = str(finding.message)
    assert "bearbeitbare Flächen und Kanten" in gesagt
    assert "festen Dreiecken" in gesagt
    assert "B-Rep" not in gesagt and "exakter Körper" not in gesagt
    assert "STL" in gesagt and "3MF" in gesagt, "Regel 17: was jetzt geht"


def test_a_solid_exported_as_step_is_not_complained_about(profile: Profile) -> None:
    """Die Prüfung darf das Format nicht abschaffen, nur erklären."""
    plan = plan_export([_solid()], project_name="Projekt", profile=profile, export_format="step")

    assert "export.needs_solid" not in {finding.code for finding in plan.findings}


def test_a_mixed_selection_names_the_body_that_cannot_go(profile: Profile) -> None:
    """**Der Fall, der auch im Fenster bleibt.** STEP wird angeboten, sobald
    *ein* exakter Körper dabei ist — die Netze daneben scheitern einzeln, und
    dann will der Nutzer wissen, welche.
    """
    plan = plan_export(
        [scene_object(), _solid()],
        project_name="Projekt",
        profile=profile,
        export_format="step",
    )

    betroffen = [f.object_id for f in plan.findings if f.code == "export.needs_solid"]
    assert betroffen == ["obj_1"], "nur das Netz, nicht der exakte Körper"


def test_a_mixed_step_export_writes_the_solids_and_leaves_the_meshes(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Zusage der Prüfung wird eingelöst, statt beim ersten Netz
    abzubrechen.

    ``check_before_export`` sagt es je Objekt, „weil der Export die exakten
    Körper schreibt und die Netze auslässt" — geschrieben wurde stattdessen
    bis zum ersten Netz, und dann flog der Fehler. Was schon auf der Platte
    lag, blieb liegen: ein halber Export mit einer Fehlermeldung darüber.

    Der zweite Kern ist hier nicht installiert, also schreibt eine Attrappe
    die Bytes; geprüft wird der Ablauf, nicht der Inhalt einer STEP-Datei.
    """
    from app.core.export import writer

    monkeypatch.setattr(writer, "_step_bytes", lambda body, name="": b"ISO-10303-21;\n")
    plan = plan_export(
        [scene_object(), _solid(), scene_object("obj_3", "Winkel")],
        project_name="Projekt",
        profile=profile,
        export_format="step",
    )

    written = write_plan(plan, tmp_path, "step")

    assert [entry.name for entry in written] == ["Projekt_Flansch_2von3.step"]
    assert {
        finding.object_id for finding in plan.findings if finding.code == "export.needs_solid"
    } == {
        "obj_1",
        "obj_3",
    }, "und der Bericht nennt die beiden, die nicht gehen"


def test_step_for_meshes_alone_still_refuses(tmp_path: Path, profile: Profile) -> None:
    """Die Grenze der Nachsicht: Bleibt nichts übrig, wird nichts geschrieben
    — und das wird gesagt.

    Ein Aufruf, der leise null Dateien schreibt und Erfolg meldet, ist
    schlimmer als der Fehler davor.
    """
    plan = plan_export(
        [scene_object()], project_name="Projekt", profile=profile, export_format="step"
    )

    with pytest.raises(NeedsSolidError) as caught:
        write_plan(plan, tmp_path, "step")

    text = f"{caught.value.title} {caught.value.detail}"
    assert "bearbeitbare Flächen und Kanten" in text
    assert "festen Dreiecken" in text
    assert "B-Rep" not in text and "exakter Körper" not in text
    assert caught.value.suggestions, "Regel 17"
    assert not list(tmp_path.iterdir()), "und keine halbe Bescherung im Ordner"


@pytest.mark.parametrize("export_format", ["stl", "3mf", "obj", "ply"])
def test_the_mesh_formats_say_nothing_about_solids(profile: Profile, export_format: str) -> None:
    """Ein Netz als STL ist der Normalfall und kein Befund."""
    plan = plan_export(
        [scene_object()],
        project_name="Projekt",
        profile=profile,
        export_format=export_format,  # type: ignore[arg-type]
    )

    assert "export.needs_solid" not in {finding.code for finding in plan.findings}


def test_a_part_in_bed_coordinates_is_offered_the_arranging(profile: Profile) -> None:
    """Der häufigste Fall von Weg 1, und er bekam drei Handlungen, die nicht
    helfen.

    Eine 3MF aus Bambu Studio, Orca oder Elegoo führt **Bettkoordinaten**.
    Gemessen an einer heruntergeladenen Ente: die drei Körper liegen bei x 83
    bis 216 und y 43 bis 113, auf einem Bett um den Ursprung also rechts
    draußen. Der größte ist 132 mm breit und passt dreimal aufs Bett.

    Angeboten wurden über die Kennung ``arrange.out_of_build_volume`` genau die
    drei Handlungen, die hier nichts ausrichten — teilen, verkleinern, anderen
    Drucker wählen (``FINDING_ACTIONS``). Was hilft, ist das Anordnen, und das
    hängt an ``arrange.off_the_plate``.
    """
    from app.ui import panels

    ente = apply(body(), translation((150.0, 78.0, 0.0)))
    findings = check_before_export([scene_object(mesh=ente)], profile, {})

    codes = {finding.code for finding in findings}
    assert "arrange.off_the_plate" in codes, codes
    handlungen = {
        action.id
        for finding in findings
        if finding.code == "arrange.off_the_plate"
        for action in panels.actions_for(finding)
    }
    assert "arrange_on_bed" in handlungen
    assert not handlungen & {"split_model", "scale_to_fit", "choose_printer"}, (
        "keine Handlung, die an der Größe ansetzt — die Größe stimmt"
    )
