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
from app.core.export.slicer_keys import SlicerFlavour
from app.core.export.writer import (
    arrangement_holds,
    check_adhesion_clearance,
    check_adhesion_on_bed,
    check_before_export,
    check_filament_changes,
    export_bytes,
    plan_export,
    plates_by_material,
    safe_name,
    write_assembly,
    write_plan,
)
from app.core.geom.mesh import MeshData, as_mesh_data, read_mesh
from app.core.geom.prepare import check_build_volume
from app.core.geom.transform import apply, place_on_bed, translation
from app.core.ingest import threemf as threemf_reader
from app.core.ingest.loader import normalise, read_model
from app.core.knowledge import print_settings, profiles
from app.core.slice import advise
from app.core.types import (
    Finding,
    MaterialSlot,
    Profile,
    Scene,
    SceneObject,
    SettingAdvice,
    Source,
    SourceOrigin,
)
from app.core.units import MAX_FACET_SAG

MESHES = Path(__file__).parent / "data" / "meshes"


def body(name: str = "cube_clean.stl"):
    """Auf dem Bett, wohin ein Teil kurz vor dem Export gehört.

    ``mend=False``: Der Export prüft, was ein Defekt auslöst — ein Import, der
    ihn vorher behebt, nähme den Prüflingen ihren Gegenstand."""
    return place_on_bed(
        normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm", mend=False).mesh
    )


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
        normalise(
            read_mesh((MESHES / "broken_open.stl").read_bytes(), ".stl"), "mm", mend=False
        ).mesh
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


# --- die zwei Fragen, die kein Körper allein beantwortet (§29, RM-140) ----------


def _tube_scene(profile: Profile, inner: float, outer: float) -> tuple[Scene, SceneObject]:
    """Ein Rohr als Szene — das kleinste Teil, an dem eine Wand entsteht."""
    from app.core.perceive.features import detect

    mesh = MeshData.of(
        trimesh.creation.annulus(r_min=inner / 2.0, r_max=outer / 2.0, height=20.0, sections=96)
    )
    entry = SceneObject(id="obj_1", name="Rohr", mesh=mesh, features=detect(mesh))
    return Scene(objects={"obj_1": entry}, profile=profile), entry


def test_a_wall_too_thin_to_print_is_named_before_the_file_exists(profile: Profile) -> None:
    """§29 zählt „keine Dünnstellen unter der Mindestwandstärke" auf.

    Die Zeile stand seit je im Bauplan und in keiner Prüfung: Eine Wand steht
    nicht in einem Körper, sondern zwischen einer Bohrung und dem Mantel um
    sie herum — und die Prüfung sah nur die Auswahl. Mit der Szene sieht sie
    das Verhältnis.
    """
    scene, entry = _tube_scene(profile, inner=19.0, outer=20.0)

    findings = check_before_export([entry], profile, {}, scene=scene)

    assert "perceive.thin_wall" in {finding.code for finding in findings}


def test_without_the_scene_the_export_makes_nothing_up(profile: Profile) -> None:
    """Die Gegenprobe, und sie ist zugleich die Zusage aus Regel 21.

    Ein Aufrufer ohne Szene — die Kommandozeile hatte lange keine — bekommt
    den Bericht, den er belegen kann. Geraten wird nichts.
    """
    _scene, entry = _tube_scene(profile, inner=19.0, outer=20.0)

    findings = check_before_export([entry], profile, {})

    assert "perceive.thin_wall" not in {finding.code for finding in findings}


def test_a_violated_fit_is_named_before_the_file_exists(profile: Profile) -> None:
    """Die zweite Zeile aus §29: „keine verletzten Passungen".

    Gemessen an einer Bohrung, die kleiner ist als ihr Stift — das Teil lässt
    sich fügen, sobald man es mit einem Hammer meint.
    """
    from tests.test_digest_and_fits import clearance_fit, pin_and_hole

    scene = pin_and_hole(4.9, 5.0, profile)
    scene.fits.append(clearance_fit())

    findings = check_before_export(list(scene.objects.values()), profile, {}, scene=scene)

    assert [finding.code for finding in findings if finding.code.startswith("fit.")], (
        "eine Passung, die nicht aufgeht, gehört vor die Datei und nicht dahinter"
    )


def test_a_fit_is_reported_for_either_partner_but_not_an_unrelated_body(profile: Profile) -> None:
    """Eine Beziehung betrifft auch den einzeln exportierten Stift.

    Gefragt wird trotzdem an der **ganzen** Szene: Die zweite Hälfte einer
    Passung mag außen vor bleiben, aufgelöst werden muss sie dennoch — sonst
    käme „Merkmal verloren" zurück, und das ist eine andere Aussage.
    """
    from tests.test_digest_and_fits import clearance_fit, pin_and_hole

    scene = pin_and_hole(4.9, 5.0, profile)
    scene.fits.append(clearance_fit())
    ohne = [entry for key, entry in scene.objects.items() if key != "obj_1"]

    findings = check_before_export(ohne, profile, {}, scene=scene)

    codes = [finding.code for finding in findings if finding.code.startswith("fit.")]
    assert "fit.violated" in codes
    unrelated = replace(scene.objects["obj_2"], id="obj_3", features={})
    scene.objects[unrelated.id] = unrelated
    findings = check_before_export([unrelated], profile, {}, scene=scene)
    assert not [finding.code for finding in findings if finding.code.startswith("fit.")]


def test_a_report_that_was_already_taken_is_not_taken_twice(
    tmp_path: Path, profile: Profile
) -> None:
    """``checked`` schreibt mit dem Bericht, den der Kunde gesehen hat (RM-140).

    Die Prüfung ist der teure Teil des Exports; zweimal zu prüfen hieße, den
    Kunden zweimal warten zu lassen — und ein zweites Ergebnis wäre auch ein
    zweiter Zustand. Gemessen wird an einer Zusage, die kein zweiter Lauf
    erzeugen würde.
    """
    fremd = [
        Finding(code="export.not_watertight", severity="warning", message="aus dem ersten Lauf")
    ]
    plan = plan_export([scene_object()], project_name="Dose", profile=profile, checked=fremd)

    assert [finding.message for finding in plan.findings] == ["aus dem ersten Lauf"]
    assert write_plan(plan, tmp_path)


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
    # In Metern, seit dem 05.09.2026 (CORE-33): der Leser skaliert bewusst nicht
    # zurück, die Einheit fragt die Eingangsstufe.
    assert back.volume == pytest.approx(original.volume * 1e-9, rel=1e-6)
    assert back.bounds.size == pytest.approx((0.010, 0.040, 0.020), abs=1e-9)


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

    Der Abstand ist gemessen und nicht gewählt — siehe ``SLICER_PLATE_GAP``. Hier
    steht die Gegenprobe: Zwei gleiche Teile auf zwei Platten liegen um genau
    eine Bettbreite plus ein Fünftel auseinander.
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
    assert offsets == [pytest.approx(width * (1.0 + threemf.SLICER_PLATE_GAP))]


def test_plates_go_into_the_grid_of_the_slicer(tmp_path: Path, profile: Profile) -> None:
    """Vier Platten sind beim Slicer ein Quadrat, fünf brauchen drei Spalten.

    **Roberts Bild aus dem ElegooSlicer** (11.09.2026: „so ganz passt die
    ausrichtung an den platten von den druckern bei den slicern nicht"): Die
    Buchstaben der Platten 3 und 4 lagen rechts neben allem, Platte 03 und 04
    standen leer **unter** 01 und 02. Solidon reihte die Platten auf, der
    Slicer legt sie ins Raster — ``ceil(sqrt(n))`` Spalten, die Zeilen nach
    unten, ein Fünftel Luft (``PartPlate.cpp``; gemessen am installierten
    Slicer, siehe ``SLICER_PLATE_GAP``).

    Gemessen wird an der Matrix in der Datei: Platte 3 von 4 steht bei
    (0, −Tiefe·1,2), Platte 4 rechts daneben; bei fünf Platten liegt die
    dritte noch in der ersten Zeile.
    """
    width, depth, _height = profile.printer.build_volume
    pitch = 1.0 + threemf.SLICER_PLATE_GAP

    def offsets_of(count: int) -> list[tuple[float, float]]:
        objects = []
        for plate in range(count):
            entry = scene_object(f"obj_{plate + 1}", f"Teil {plate + 1}")
            entry.plate = plate
            objects.append(entry)
        written, _findings = write_assembly(
            objects, tmp_path, project_name=f"raster{count}", profile=profile
        )
        model = zipfile.ZipFile(BytesIO(written.read_bytes())).read(threemf.MODEL_PATH)
        found = {}
        for item in re.findall(
            r"<item objectid=\"(\d+)\"(?: transform=\"([^\"]+)\")?", model.decode()
        ):
            values = item[1].split() if item[1] else ["0"] * 12
            found[int(item[0]) - 2] = (float(values[9]), float(values[10]))
        return [found[index] for index in range(count)]

    four = offsets_of(4)
    assert four[0] == (0.0, 0.0)
    assert four[1] == pytest.approx((width * pitch, 0.0)), "die zweite rechts daneben"
    assert four[2] == pytest.approx((0.0, -depth * pitch)), "die dritte darunter, nicht rechts"
    assert four[3] == pytest.approx((width * pitch, -depth * pitch))

    five = offsets_of(5)
    assert five[2] == pytest.approx((2 * width * pitch, 0.0)), "fünf Platten: drei Spalten"
    assert five[3] == pytest.approx((0.0, -depth * pitch))

    # Und die Plattenblöcke zählen durch, wie der Slicer zählt.
    beilage = zipfile.ZipFile(BytesIO((tmp_path / "raster5.3mf").read_bytes())).read(
        threemf.SETTINGS_PATH
    )
    assert re.findall(r'plater_id" value="(\d+)"', beilage.decode()) == ["1", "2", "3", "4", "5"]


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


def test_only_painted_faces_count_as_a_tool_in_use() -> None:
    """Die Gegenprobe nach dem Slicen fragt nach den **Flächen**, nicht nach
    der Slotliste.

    Ein Körper darf einen Slot deklarieren, den keines seiner Dreiecke trägt —
    eine alte Spulenwahl, eine gelöschte Bemalung. Zählte ``tools_in_use`` die
    Deklaration mit, meldete ``handover.spools_left_out`` bei jedem solchen
    Druck eine verlorene Spule, obwohl nichts fehlt; und ein Fehlalarm, den
    der Kunde dreimal gesehen hat, nimmt dem echten Befund die Wirkung.
    """
    red = MaterialSlot(index=0, name="Rot")
    white = MaterialSlot(index=1, name="Weiß")
    box = trimesh.creation.box()
    faces = len(box.faces)

    declared_only = threemf.AssemblyPart(
        mesh=MeshData.of(box, slots=(0,) * faces), name="A", slots=(red, white)
    )
    assert threemf.tools_in_use([declared_only]) == (0,), (
        "Weiß steht in der Liste, aber auf keinem Dreieck"
    )

    painted = threemf.AssemblyPart(
        mesh=MeshData.of(box, slots=tuple(0 if i < faces // 2 else 1 for i in range(faces))),
        name="B",
        slots=(red, white),
    )
    assert threemf.tools_in_use([painted]) == (0, 1), "bemalt: beide Werkzeuge"

    # Und die Nummern sind die des Auftrags, nicht die der Platte — dieselbe
    # Unterscheidung wie bei ``merge_slots`` eine Zeile darüber.
    second = threemf.AssemblyPart(
        mesh=MeshData.of(box, slots=(1,) * faces), name="C", slots=(white,)
    )
    whole = [painted, second]
    assert threemf.tools_in_use([second], across=whole) == (1,), (
        "Weiß bleibt Werkzeug 2, auch wenn es auf dieser Platte allein liegt"
    )
    assert threemf.tools_in_use([second]) == (0,), (
        "ohne den Auftrag ist die Platte der Auftrag — dann ist Weiß das erste Werkzeug"
    )


def test_a_lettering_split_into_letters_keeps_its_one_filament(
    tmp_path: Path, profile: Profile
) -> None:
    """Zerlegt ist ein Schriftzug auf Slot 7 im Slicer immer noch **ein** Filament.

    **Roberts Bild aus dem ElegooSlicer** (11.09.2026: „Filamente auch
    nicht"): zwei Filamente, „PLAOrange" und ein „Slot 0", und alle
    Buchstaben auf dem zweiten — orange lag daneben, unbenutzt. Die Zerlegung
    hatte die Slots je Dreieck verloren, die Teile trugen nur noch die
    Beschreibung (``material_slots``), und der Export ergänzte für die nun
    unbemalten Dreiecke den neutralen Platzhalter.

    Hier steht die ganze Kette: bemalen, zerlegen, als Baugruppe schreiben —
    und in der Datei ein Material, jedes Teil an Extruder 1.
    """
    from app.core.geom.attributes import with_slot
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    left = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right.apply_translation((50.0, 0.0, 0.0))
    orange = MaterialSlot(index=7, name="PLAOrange", colour=(0.7, 0.4, 0.05), material_type="PLA")
    lettering = SceneObject(
        id="obj_1",
        name="Schrift",
        mesh=with_slot(MeshData.of(trimesh.util.concatenate([left, right])), 7),
        material_slots=(orange,),
    )
    spec = REGISTRY.get("split_bodies")
    pieces = spec.fn(
        OpContext(
            scene=Scene(objects={lettering.id: lettering}),
            inputs=[lettering],
            params=spec.params(count=2),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    ).outputs

    written, _findings = write_assembly(
        list(pieces), tmp_path, project_name="schrift", profile=profile
    )
    archive = zipfile.ZipFile(BytesIO(written.read_bytes()))
    model = archive.read(threemf.MODEL_PATH).decode("utf-8")
    assert re.findall(r'<base name="([^"]*)"', model) == ["PLAOrange"], (
        "ein Filament — kein Platzhalter „Slot 0“ daneben"
    )
    settings = archive.read(threemf.SETTINGS_PATH).decode("utf-8")
    assert re.findall(r'key="extruder" value="(\d+)"', settings) == ["1", "1"], (
        "und beide Buchstaben liegen auf ihm"
    )


def test_every_object_names_its_tool_even_without_a_spool() -> None:
    """Creality Print 7.2 rechnet auf der Konsole kein Objekt ohne Werkzeug.

    RM-164: Ohne ``extruder`` in ``model_settings.config`` blieb die
    Werkzeugfolge leer, und jede 3MF endete mit −100 und „The print is
    empty" — Solidons Übergabe genauso wie eine nackte aus trimesh; dieselbe
    Datei mit ``extruder = 1`` am Objekt schneidet (29.09.2026, Sonde
    ``output/review/rm164-2026-09-29/varianten.py``). Ein Teil ohne Spule
    druckt mit dem neutralen Platz, den :func:`threemf.tools_in_use` für die
    Gegenprobe zählt — also steht genau dieses Werkzeug in der Datei, auch
    neben bemalten Teilen.
    """
    red = MaterialSlot(index=0, name="Rot")
    white = MaterialSlot(index=1, name="Weiß")
    box = trimesh.creation.box()
    faces = len(box.faces)

    def extruders(parts: list[threemf.AssemblyPart]) -> list[int]:
        archive = zipfile.ZipFile(BytesIO(threemf.write_assembly(parts)))
        settings = archive.read(threemf.SETTINGS_PATH).decode("utf-8")
        return [int(value) for value in re.findall(r'key="extruder" value="(\d+)"', settings)]

    plain = threemf.AssemblyPart(mesh=MeshData.of(box), name="Würfel")
    assert extruders([plain]) == [1], "ein Teil ohne Spule steht an Werkzeug 1"

    painted = threemf.AssemblyPart(
        mesh=MeshData.of(box, slots=tuple(0 if i < faces // 2 else 1 for i in range(faces))),
        name="Bemalt",
        slots=(red, white),
    )
    parts = [painted, plain]
    assert extruders(parts) == [1, 3], "der neutrale Platz ist das dritte Filament"
    assert threemf.tools_in_use(parts) == (0, 1, 2), (
        "und genau dieses Werkzeug erwartet die Gegenprobe"
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
        threemf.AssemblyPart(
            mesh=MeshData(trimesh.creation.box(), slots=(1,) * 12), name="A", slots=(red,)
        ),
        threemf.AssemblyPart(
            mesh=MeshData(trimesh.creation.box(), slots=(1,) * 6 + (2,) * 6),
            name="B",
            slots=(white, red_again),
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
    white = MaterialSlot(index=0, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
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
    name: str,
    size: tuple[float, float, float],
    at: tuple[float, float],
    slot: str = "",
    material: str | None = None,
) -> SceneObject:
    """Ein Quader an einer Stelle der Platte, mit optionaler Spule und Material.

    ``slot`` ist die zugewiesene Spule, ``material`` das ausdrücklich am Teil
    gesetzte Material — zwei verschiedene Dinge, und die Plattenverteilung
    braucht beide (siehe ``plates_by_material``).
    """
    raw = trimesh.creation.box(size)
    raw.apply_translation((at[0], at[1], size[2] / 2.0))
    return SceneObject(
        id=name,
        name=name,
        mesh=MeshData.of(raw),
        material=material,
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


def test_a_rim_beyond_the_bed_edge_is_said() -> None:
    """Die Körper liegen auf dem Bett, ihr Rand nicht (27.09.2026): Am
    Minigolf-Auftrag für den Centauri Carbon 2 fuhr der Auto-Brim am Neptune 4
    210 Züge neben das Bett, PrusaSlicers Skirt am SV06 24. Der Skirt zählt
    dabei mit seiner Breite — am Bettrand liegt er ganz außen."""
    profile = profiles.make_profile()
    half = profile.printer.build_volume[0] / 2.0
    settings = print_settings.resolve(profile)
    brim = print_settings.with_path(settings, "adhesion.kind", "brim")
    brim = print_settings.with_path(brim, "adhesion.brim_width", 5.0)
    skirt = print_settings.with_path(settings, "adhesion.kind", "skirt")
    skirt = print_settings.with_path(skirt, "adhesion.skirt_distance", 2.0)
    skirt = print_settings.with_path(skirt, "adhesion.skirt_loops", 1)
    edge = _boxed("Rand", (10.0, 10.0, 5.0), (half - 7.0, 0.0)).mesh
    middle = _boxed("Mitte", (10.0, 10.0, 5.0), (0.0, 0.0)).mesh
    beside = _boxed("Daneben", (10.0, 10.0, 5.0), (half + 20.0, 0.0)).mesh

    [found] = check_adhesion_on_bed([edge, middle], brim, profile, ["Rand", "Mitte"])

    assert found.code == "arrange.adhesion_off_bed" and found.object_id == "Rand"
    assert found.suggestions, "Regel 17: Anordnen"
    assert [f.code for f in check_adhesion_on_bed([edge], skirt, profile)] == [
        "arrange.adhesion_off_bed"
    ], "2 mm Abstand und eine Bahn über 2 mm Luft"
    assert check_adhesion_on_bed([middle], brim, profile) == []
    assert check_adhesion_on_bed([beside], brim, profile) == [], "das sagt die Bauraumprüfung"
    none = print_settings.with_path(settings, "adhesion.kind", "none")
    assert check_adhesion_on_bed([edge], none, profile) == []


def test_a_part_too_tall_for_the_printer_is_named_as_such() -> None:
    """PrusaSlicer sagt „outside of the print volume", gleich ob ein Teil
    daneben liegt oder zu hoch ist. Am Minigolf-Auftrag auf dem MINI war es
    ein Teil von 200 mm bei 180 mm Bauhöhe, und „Anordnen" half dort nicht."""
    profile = profiles.make_profile("prusa-mini", "pla")
    setup = handover.SlicerSetup(executable=Path("prusa-slicer-console.exe"), flavour="prusa")

    tall = handover._outside_the_volume(setup, profile, "outside of the print volume", 200.0)
    flat = handover._outside_the_volume(setup, profile, "outside of the print volume", 20.0)

    assert tall.values["height_mm"] == 200.0 and tall.values["limit_mm"] == 180.0
    assert tall.suggestions[0].id == "split_model"
    assert "limit_mm" not in flat.values
    assert flat.suggestions[0].id == "arrange_on_bed"


def test_the_support_structure_needs_its_own_room_beside_the_part() -> None:
    """Nicht nur der Brim steht über — die Stütze auch (Robert, 09.09.2026).

    Sie steht unter dem Überhang und damit überwiegend in der Aufsicht des
    Körpers, an einer senkrechten Wand aber ``xy_gap`` außerhalb. Zwischen zwei
    Nachbarn zählt dieser Rand zweimal, genau wie der Brim. Gemessen ohne
    Haftung, damit allein die Stütze die Aussage trägt: 2 mm ``xy_gap`` je
    Seite brauchen 4 mm, und 3 mm Luft sind zu wenig.

    **Und ohne Stützstil bleibt der Rand aus.** Wo keine Struktur entsteht,
    verschenkte ein Rand für sie Bettfläche.
    """
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "adhesion.kind", "none")
    settings = print_settings.with_path(settings, "support.xy_gap", 2.0)
    meshes = [
        (_boxed("links", (10.0, 10.0, 5.0), (0.0, 0.0)).mesh),
        (_boxed("rechts", (10.0, 10.0, 5.0), (13.0, 0.0)).mesh),
    ]

    ohne = print_settings.with_path(settings, "support.style", "none")
    assert check_adhesion_clearance(meshes, ohne) == [], "ohne Stützen kein Rand"

    mit = print_settings.with_path(settings, "support.style", "grid")
    assert [entry.code for entry in check_adhesion_clearance(meshes, mit)] == [
        "arrange.adhesion_too_close"
    ]
    weit = [
        meshes[0],
        (_boxed("weit", (10.0, 10.0, 5.0), (16.0, 0.0)).mesh),
    ]
    assert check_adhesion_clearance(weit, mit) == [], "5 mm Luft reichen für 2 + 2"


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


def test_a_material_set_on_the_part_gets_its_own_plate() -> None:
    """Eine TPU-Dichtung gehört nicht auf die Platte des PETG-Gehäuses.

    ``SceneObject.material`` ist kein Beiwerk: ``for_object`` rechnet damit
    Spiel, Schrumpf und Elefantenfuß, und ``types.py`` nennt genau diesen Fall
    („Eine TPU-Dichtung im PETG-Gehäuse schrumpft anders"). Die
    Plattenverteilung sah es bis zum 03.09.2026 trotzdem nicht: Sie gruppierte
    allein nach dem Spulennamen, und ohne zugewiesene Spule trugen alle Teile
    denselben leeren Schlüssel. Gehäuse und Dichtung kamen auf eine Platte,
    ``check_filament_changes`` schwieg, und so ging es an den Slicer.
    """
    objects = [
        _boxed("gehaeuse", (10.0, 10.0, 10.0), (0.0, 0.0)),
        _boxed("dichtung", (10.0, 10.0, 10.0), (30.0, 0.0), material="tpu-95a"),
    ]

    plates = plates_by_material(objects)

    assert plates["gehaeuse"] != plates["dichtung"], (
        "zwei Materialien sind zwei Filamente, auch ohne zugewiesene Spule"
    )
    assert plates["gehaeuse"] == 0, "die Reihenfolge folgt dem ersten Auftreten"


def test_two_spools_of_the_same_material_stay_apart() -> None:
    """Und die Gegenrichtung, an der der einfache Fix gescheitert wäre.

    „Material schlägt Spule" ist die Rangfolge aus ``for_object``, und für die
    **Rechnung** ist sie richtig. Für die **Platte** ist sie falsch: Grau und
    Weiß sind zwei Spulen, auch wenn beide PETG sind — zwei Filamente, zwei
    Platten. Gemessen an vier Lagen war das der einzige Fall, in dem sich die
    naheliegende Fassung und die gewählte unterscheiden, und er entscheidet.
    """
    objects = [
        _boxed("links", (10.0, 10.0, 10.0), (0.0, 0.0), slot="grau", material="petg"),
        _boxed("rechts", (10.0, 10.0, 10.0), (30.0, 0.0), slot="weiss", material="petg"),
    ]

    assert plates_by_material(objects)["links"] != plates_by_material(objects)["rechts"]


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


def test_cura_input_stays_centred_before_the_engine_moves_it(
    tmp_path: Path, profile: Profile
) -> None:
    """CuraEngine verschiebt das STL selbst vom Bettzentrum zum Maschinenursprung."""
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


def test_every_family_gets_the_parts_in_bed_coordinates(tmp_path: Path, profile: Profile) -> None:
    """Nur die Projektleser benötigen schon verschobene Eingabepunkte."""
    width, depth, _height = profile.printer.build_volume
    for flavour in ("cura", "prusa", "orca"):
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
            assert centre[1] == pytest.approx(0.0, abs=0.01), flavour
        else:
            text = (
                zipfile.ZipFile(BytesIO(written.read_bytes()))
                .read(threemf.MODEL_PATH)
                .decode("utf-8")
            )
            assert f'transform="1 0 0 0 1 0 0 0 1 {width / 2.0:g} {depth / 2.0:g} 0"' in text, (
                flavour
            )


def _asks_only_a_flavour(function: object) -> bool:
    """Ist das eine Funktion, die genau eine Slicer-Familie beantwortet?

    Erkannt an der Signatur und nicht am Namen: **ein** Parameter, und der
    heißt ``flavour``. Das trifft die sieben, die es gab, und jedes weitere,
    das jemand daneben schreibt — und es trifft nicht ``flavour_of`` (nimmt
    einen Dateinamen) oder ``values_for`` (nimmt drei Dinge).
    """
    import inspect

    if not inspect.isfunction(function):
        return False
    parameters = list(inspect.signature(function).parameters)
    return parameters == ["flavour"]


def test_every_flavour_answers_every_property() -> None:
    """Jede Familie hat zu jeder Eigenschaft eine Antwort — und sie steht hier.

    Die Prädikate in ``slicer_keys`` sind der eine Ort, an dem einer
    Slicer-Familie eine Eigenschaft zugeordnet wird. Diese Tabelle ist ihr
    Gegenstück im Test: Sie schreibt den Bestand fest, damit ein Prädikat sich
    nicht unbemerkt umdreht, und sie ist die Liste, die jemand ausfüllen muss,
    der eine vierte Familie einführt.

    Der Bestand ist ausdrücklich **kein** Muster: Sechs der elf Zeilen
    trennen die Orca-Familie von den anderen beiden, eine gilt für alle, eine stellt Cura allein
    (``has_key_definitions``), und wer daraus „Orca kann alles" liest, hat die
    Ursache verwechselt. Sie kann es, weil sie ihre
    Profile als Dateien führt, die Solidon lesen kann; Cura führt seine
    Einstellungen ausschließlich auf der Kommandozeile, und PrusaSlicer legt
    keine Profile ab, die eine Auswahl trügen.

    Gegenprobe gefahren: Jedes der Prädikate einmal auf ``True`` festgenagelt,
    jedes Mal wird diese Tabelle rot.
    """
    # ``other`` ist seit dem 22.09.2026 die vierte Familie: ein Programm, dem
    # Solidon nur die Datei ins Fenster gibt (RM-071). Es antwortet auf jede
    # Eigenschaft mit „nein" — bis auf die Bettkoordinaten, die eine Aussage
    # über einen G-Code sind, den es nie schreibt.
    expected: dict[str, dict[SlicerFlavour, bool]] = {
        # Seit dem 05.09.2026 jede: Der Drucker misst von der Ecke, gleich
        # welcher Slicer die Datei schreibt (CORE-17, siehe das Prädikat).
        "wants_bed_coordinates": {"prusa": True, "orca": True, "cura": True, "other": True},
        "needs_bed_translation": {"prusa": True, "orca": True, "cura": False, "other": False},
        "has_user_profile_tree": {"prusa": False, "orca": True, "cura": False, "other": False},
        "has_filament_profiles": {"prusa": False, "orca": True, "cura": False, "other": False},
        "reads_settings_from_project_file": {
            "prusa": False,
            "orca": True,
            "cura": False,
            "other": False,
        },
        "names_its_own_output": {"prusa": False, "orca": True, "cura": False, "other": False},
        "has_readable_profiles": {"prusa": True, "orca": True, "cura": True, "other": False},
        "reads_assembly_file": {"prusa": True, "orca": True, "cura": False, "other": False},
        "takes_a_machine_profile": {"prusa": False, "orca": True, "cura": False, "other": False},
        # **Die einzige Zeile, in der Cura allein steht**, und sie fehlte hier,
        # bis die Vollständigkeitsprüfung darunter sie ans Licht holte: Nur
        # neben CuraEngine liegt eine Datei, die jeden gültigen Schlüssel nennt
        # (``fdmprinter.def.json``). Sie ist dort die einzige Gegenprobe, die
        # es gibt, denn CuraEngine schreibt seine wirksame Konfiguration nicht
        # in den G-Code — Prusa und Orca tun es und prüfen sich damit selbst.
        "has_key_definitions": {"prusa": False, "orca": False, "cura": True, "other": False},
        # Die Maschine aus einer Druckerdefinition der Installation (Stufe D,
        # 27.09.2026): Nur CuraEngine bekommt sie so; die Orca-Familie lädt
        # ein Profil, PrusaSlicer bekommt sie in Solidons ``.ini``.
        "machine_from_definition": {"prusa": False, "orca": False, "cura": True, "other": False},
        # Je Teil ein Netz mit eigenen Werten auf der Kommandozeile (Stufe D):
        # So reist die Stützsperre zu CuraEngine als ``anti_overhang_mesh``.
        "takes_mesh_settings": {"prusa": False, "orca": False, "cura": True, "other": False},
        # Mehrere Platten in einer Projektdatei — die Orca-Familie speichert
        # ihre Projekte so; PrusaSlicer und Cura kennen eine Platte je Datei.
        "knows_plates": {"prusa": False, "orca": True, "cura": False, "other": False},
        # Die Stützsperre als eigenes Teil (Orca-Beilage) statt als Bereich im
        # Netz (Prusa-Beilage) — jede Familie liest nur ihre Schreibweise und
        # druckte die andere als Kunststoff (26.09.2026). Cura bekommt ein STL.
        "helpers_as_parts": {"prusa": False, "orca": True, "cura": False, "other": False},
        # Das Tempo nach dem Volumenstrom des Filaments deckeln PrusaSlicer und
        # die Orca-Familie selbst; ein Tempodeckel als Vorschlag ändert dort
        # nichts am Druck (Gesamtprüfung, 27.09.2026). Cura liest den Wert nicht.
        "caps_volumetric_speed": {"prusa": True, "orca": True, "cura": False, "other": False},
    }
    flavours = set(get_args(SlicerFlavour))
    assert len(flavours) >= 4, f"zu wenige Familien gefunden: {flavours}"

    for name, answers in expected.items():
        assert set(answers) == flavours, f"{name}: Tabelle und Literal weichen ab"
        predicate = getattr(slicer_keys, name)
        for flavour, wanted in answers.items():
            assert predicate(flavour) is wanted, f"{name}({flavour})"

    # **Und die Tabelle muss vollständig sein, nicht nur richtig.** Sie ist
    # bis zum 03.09.2026 über ``expected`` gelaufen und hat damit nur geprüft,
    # was jemand eingetragen hatte. Ein achtes Prädikat kam an diesem Tag dazu
    # (``takes_a_machine_profile``, aus dem Fall „Cura bekam eine Warnung über
    # ein Maschinenprofil, das es nie lädt") — und wäre stillschweigend
    # ungeprüft geblieben, weil die Schleife es nie zu Gesicht bekommt.
    #
    # Der Docstring nennt diese Tabelle „die Liste, die jemand ausfüllen muss,
    # der eine vierte Familie einführt". Ein Versprechen, das nur gilt, wenn
    # jemand daran denkt, ist keines.
    found = {
        name
        for name in dir(slicer_keys)
        if not name.startswith("_")
        and callable(getattr(slicer_keys, name))
        and _asks_only_a_flavour(getattr(slicer_keys, name))
    }
    assert found == set(expected), (
        f"nicht in der Tabelle: {sorted(found - set(expected))}; "
        f"nicht als Prädikat gefunden: {sorted(set(expected) - found)}"
    )


@pytest.mark.parametrize("flavour", get_args(SlicerFlavour))
def test_the_print_file_is_checked_in_machine_coordinates(
    profile: Profile, flavour: SlicerFlavour
) -> None:
    """Alle Familien prüfen Bahnen ohne Bettkopf vom Ursprung bis zur vollen Größe."""
    width, depth, height = profile.printer.build_volume
    start = "G90\nM83\n;LAYER:0\nG0 X0 Y0 Z0\n"
    inside = start + f"G1 X{width} Y{depth} Z{height} E1\n"
    assert handover.off_the_bed(inside, profile, flavour) is None

    for axis, bound in zip("XYZ", (width, depth, height), strict=True):
        for outside in (-2.0, bound + 2.0):
            moving_axis = "Y" if axis == "X" else "X"
            text = start + f"G1 {moving_axis}1 {axis}{outside} E1\n"
            finding = handover.off_the_bed(text, profile, flavour)
            assert finding is not None, (flavour, axis, outside)
            assert finding.code == "gcode.off_the_bed"
            assert finding.source == "gcode"


def _solid(object_id: str = "obj_2", name: str = "Flansch") -> SceneObject:
    """Ein Körper, der seine Flächen kennt — als Attrappe, ohne OpenCASCADE.

    ``BRepBody`` ist ein Protokoll (§30), und ``kind_of`` prüft es zur
    Laufzeit. Drei Mitglieder reichen also, und der Test läuft auch dort, wo
    der zweite Kern nicht installiert ist.
    """

    class Attrappe:
        @property
        def shape(self) -> object:
            return object()

        @property
        def deflection(self) -> float:
            return MAX_FACET_SAG

        @property
        def solid_count(self) -> int:
            return 1

        def to_mesh(self, *, deflection: float | None = None) -> object:
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

    monkeypatch.setattr(writer, "_step_bytes", lambda body, name="", slots=None: b"ISO-10303-21;\n")
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


def test_the_export_says_why_the_machine_side_is_missing(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anschlusstest: Der Befund liegt nicht nur bereit, er kommt auch heraus.

    ``handover.machine_missing`` allein zu prüfen hieße zu prüfen, dass die
    Auskunft *gerechnet* werden **kann**. Der Fall vom 03.09.2026 war ein
    anderer: Die Begründung existierte längst als Protokollzeile und erreichte
    niemanden. Also wird hier der Weg gefahren, den die Anwendung geht — eine
    Baugruppe schreiben und nachsehen, was in den Befunden steht.
    """
    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "Bambu Lab A1 0.2 nozzle")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")
    settings = print_settings.resolve(profile, "standard")

    _written, findings = write_assembly(
        [scene_object("obj_1", "Deckel")],
        tmp_path,
        project_name="Gehäuse",
        profile=profile,
        settings=settings,
        setup=setup,
    )

    treffer = [finding for finding in findings if finding.code == "slicer.machine_mismatch"]
    assert treffer, [finding.code for finding in findings]
    assert "Bambu Lab A1 0.2 nozzle" in str(treffer[0].values["machine"])
    assert treffer[0].suggestions, "Regel 17"


def test_a_plain_export_hears_nothing_about_a_foreign_slicer(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne gewählten Slicer bleibt die Einstellung eines fremden Programms außen vor.

    ``write_assembly`` baut sich für die Filamentprüfung einen Platzhalter aus
    dem Familiennamen. Diesen nach seiner eingestellten Maschine zu fragen
    ergäbe einen Satz über einen Slicer, den der Kunde gerade nicht benutzt —
    er speichert eine 3MF und sonst nichts.
    """
    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "Bambu Lab A1 0.2 nozzle")
    settings = print_settings.resolve(profile, "standard")

    _written, findings = write_assembly(
        [scene_object("obj_1", "Deckel")],
        tmp_path,
        project_name="Gehäuse",
        profile=profile,
        settings=settings,
    )

    assert not [f for f in findings if f.code.startswith("slicer.machine_")]


def test_the_step_refusal_offers_the_way_out_it_names(profile: Profile) -> None:
    """Derselbe Fall, zwei Wege — und nur einer trug den Knopf.

    ``export.needs_solid`` erreicht den Kunden auf zwei Wegen: als Befund im
    Prüfbericht und als geworfener Fehler, wenn er ``teil.step`` tippt. Der
    Befund bietet seit dem 30.08.2026 *Als 3MF speichern* an; die Ausnahme bot
    nur *Abbrechen*. Gemessen am selben Tag:

        geworfen    ['cancel']
        als Befund  ['export_as_mesh', 'show_details']

    Formal genügte das Regel 17 — ein Vorschlag war da. Praktisch endete der
    häufigere der beiden Wege mit „geht nicht, brich ab", während die Handlung
    dazu im Fenster fertig lag: ``_export_as_mesh_after_error`` trägt den Fall
    im Namen und wurde nie gerufen.

    **Seit P4.0 sind es zwei Auswege, und der zum Körper steht vorn:** *In
    Flächen und Kanten umwandeln* macht aus dem Netz, was STEP tragen kann;
    *Als 3MF speichern* bleibt für den, der kein STEP braucht. Beide stehen vor
    dem Abbruch.
    """
    from app.core.errors import CANCEL, CONVERT_TO_EXACT, EXPORT_AS_MESH
    from app.core.export.writer import _needs_solid

    ausgaenge = [action.id for action in _needs_solid().suggestions]

    assert EXPORT_AS_MESH.id in ausgaenge, ausgaenge
    assert ausgaenge[:2] == [CONVERT_TO_EXACT.id, EXPORT_AS_MESH.id], ausgaenge
    assert ausgaenge.index(CANCEL.id) > 1, "die Auswege stehen vor dem Abbruch"


def test_a_name_the_customer_typed_reaches_the_disc_unchanged(
    tmp_path: Path, profile: Profile
) -> None:
    """Wer den Dateinamen selbst eingibt, hat entschieden.

    Der ``_ExportWorker`` reicht den Stem des im Speichern-Dialog gewählten
    Pfads als ``project_name`` durch, und der ging durch dieselbe Bereinigung
    wie ein erzeugter Name: „Gehäuse Deckel" wurde ``Gehaeuse_Deckel``, ein
    „Halter V2+" verlor sein Plus. Gemessen am 03.09.2026 über den Weg der
    Oberfläche — drei Exporte, dreimal ein anderer Name als der getippte
    (Entscheidung Robert: unverändert nehmen).

    Der **Objektname** im selben Dateinamen bleibt bereinigt: Er entsteht, statt
    getippt zu werden, und für ihn gilt die Konvention weiter.
    """
    plan = plan_export(
        [scene_object("obj_1", "Größe L")],
        project_name="Gehäuse Deckel V2+",
        profile=profile,
        scheme="{project}",
    )
    written = write_plan(plan, tmp_path)

    assert [path.stem for path in written] == ["Gehäuse Deckel V2+"], (
        "Umlaut, Leerzeichen und Plus stehen so da, wie sie getippt wurden"
    )

    beides = plan_export(
        [scene_object("obj_1", "Größe L")],
        project_name="Gehäuse Deckel",
        profile=profile,
        scheme="{project}_{object}",
    )
    assert [path.stem for path in write_plan(beides, tmp_path)] == ["Gehäuse Deckel_Groesse_L"], (
        "der getippte Teil bleibt, der erzeugte wird transliteriert"
    )


def test_a_typed_name_still_loses_what_no_disc_can_hold(tmp_path: Path, profile: Profile) -> None:
    """Erlaubt ist, was möglich ist — und Pfadtrenner sind es nicht.

    Die Gegenrichtung zum Test darüber: Ohne sie wäre „unverändert nehmen" die
    Erlaubnis, mit einem Doppelpunkt oder einem Schrägstrich ein Verzeichnis zu
    wechseln. Ein leerer Rest fällt auf den Rückfall zurück, sonst entstünde
    eine Datei, die nur ihre Endung ist.
    """
    plan = plan_export(
        [scene_object("obj_1", "Teil")],
        project_name="../ganz/woanders:x?",
        profile=profile,
        scheme="{project}",
    )
    written = write_plan(plan, tmp_path)

    assert len(written) == 1
    assert written[0].parent == tmp_path, "die Datei bleibt im gewählten Ordner"
    assert "/" not in written[0].stem and ":" not in written[0].stem

    leer = plan_export(
        [scene_object("obj_1", "Teil")],
        project_name=":::",
        profile=profile,
        scheme="{project}",
    )
    assert write_plan(leer, tmp_path)[0].stem == "projekt", "ein leerer Rest bekommt den Rückfall"


def _object_values(written: Path, member: str) -> dict[str, dict[str, str]]:
    """Die Objektwerte einer Baugruppe je Objektname — aus
    ``model_settings.config`` (Orca-Familie) oder ``Slic3r_PE_model.config``
    (PrusaSlicer)."""
    config = ET.fromstring(zipfile.ZipFile(written).read(member))
    values: dict[str, dict[str, str]] = {}
    for node in config.iter("object"):
        own = {meta.get("key", ""): meta.get("value", "") for meta in node.findall("metadata")}
        values[own.pop("name", node.get("id", ""))] = own
    return values


def _plate_value(written: Path, flavour: SlicerFlavour, key: str) -> object:
    """Ein Wert der Platte, wie die Baugruppe ihn trägt."""
    archive = zipfile.ZipFile(written)
    if flavour == "prusa":
        for line in archive.read("Metadata/Slic3r_PE.config").decode("utf-8").splitlines():
            name, _sep, value = line.removeprefix("; ").partition(" = ")
            if name == key:
                return value
        return None
    return json.loads(archive.read("Metadata/project_settings.config")).get(key)


def test_an_accepted_brim_goes_only_to_the_part_that_needs_it(
    tmp_path: Path, profile: Profile
) -> None:
    """*Vorschläge übernehmen* setzt „brim" als übernommenen Vorschlag
    (``advise.apply``), und seit Stufe E bekommt ihn nur das Teil, das ihn
    braucht (Konzept Herstellerprofil, Entscheidung G; RM-250). Die Platte
    behält die Grundlage, der schlanke Turm trägt den Brim als Objektwert, die
    breite Platte nichts. Vorher bekam jedes Teil einen Rand, auch das, das
    breit auf dem Bett steht — Material, das der Kunde wieder abschneidet.
    """
    schlank = MeshData.of(trimesh.creation.box(extents=(4.0, 4.0, 80.0)))
    breit = MeshData.of(trimesh.creation.box(extents=(60.0, 60.0, 10.0)))
    objects = [
        replace(scene_object("obj_1", "Turm"), mesh=schlank),
        replace(scene_object("obj_2", "Platte"), mesh=breit),
    ]
    settings = print_settings.resolve(profile, "standard")
    assert settings.adhesion.kind == "skirt", "die Vorbedingung des Tests"
    brim = SettingAdvice(
        path="adhesion.kind",
        value="brim",
        was="skirt",
        reason="Dieses Teil ist hoch und schmal.",
        severity="warning",
    )
    settings = advise.apply(settings, [brim])
    assert "adhesion.kind" in settings.accepted

    written, findings = write_assembly(
        objects, tmp_path, project_name="Gehäuse", profile=profile, settings=settings
    )

    treffer = [finding for finding in findings if finding.code == "export.part_setting"]
    assert [finding.object_id for finding in treffer] == ["obj_1"], "nur der Turm"
    assert _plate_value(written, "orca", "brim_type") == "no_brim", "die Platte bleibt"
    values = _object_values(written, "Metadata/model_settings.config")
    assert values["Turm"]["brim_type"] == "outer_only"
    assert "brim_type" not in values["Platte"]


def _two_blocks() -> list[SceneObject]:
    """Zwei Klötze, die keines Rats je Teil bedürfen: kein Überhang, breiter Fuß."""
    return [
        replace(
            scene_object("obj_1", "Klotz"),
            mesh=MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 10.0))),
        ),
        replace(
            scene_object("obj_2", "Platte"),
            mesh=MeshData.of(trimesh.creation.box(extents=(30.0, 30.0, 10.0))),
        ),
    ]


def test_an_accepted_suggestion_no_part_asks_for_goes_to_every_part(
    tmp_path: Path, profile: Profile
) -> None:
    """Ein übernommener Vorschlag verschwindet nie still (Durchsicht 0.5.1, B2).

    Fragt der Export den Rat je Teil und keines verlangt ihn — weil die
    Grundlage des Herstellers schon hält oder weil Dialog und Export an
    verschiedenen Netzen rechnen —, bekommt jedes Teil den übernommenen Wert
    als Objektwert, und der Bericht sagt es. Die Platte bleibt die Grundlage,
    damit Datei und Konsolenlauf dieselbe Platte tragen. Bis dahin stand der
    Wert nirgends in der Datei.
    """
    settings = print_settings.resolve(profile, "standard")
    assert settings.support.style == "none", "die Vorbedingung des Tests"
    settings = print_settings.with_accepted(settings, "support.style", "auto")

    written, findings = write_assembly(
        _two_blocks(), tmp_path, project_name="Klötze", profile=profile, settings=settings
    )

    assert _plate_value(written, "orca", "enable_support") in ("0", ["0"]), "die Platte bleibt"
    values = _object_values(written, "Metadata/model_settings.config")
    assert values["Klotz"]["enable_support"] == "1"
    assert values["Platte"]["enable_support"] == "1"
    said = [
        (entry.values["setting"], entry.values["value"])
        for entry in findings
        if entry.code == "export.part_setting_all"
    ]
    assert said == [("support.style", "auto")]
    assert not [entry for entry in findings if entry.code == "export.part_setting"]


def test_cura_keeps_an_accepted_suggestion_no_part_asks_for(
    tmp_path: Path, profile: Profile
) -> None:
    """Bei Cura trägt die Platte die Übernahme, und ein Netz, das sie nicht
    braucht, bekommt die Grundlage zurück. Braucht sie keines, nahm jedes sie
    zurück — der Vorschlag war weg (B2). Jetzt bleibt sie an allen."""
    settings = print_settings.with_accepted(
        print_settings.resolve(profile, "standard"), "support.style", "auto"
    )

    written, findings = write_assembly(
        _two_blocks(),
        tmp_path,
        project_name="Klötze",
        profile=profile,
        settings=settings,
        flavour="cura",
    )

    meshes = {mesh.path.name: dict(mesh.settings) for mesh in handover.cura_meshes(written)}
    assert [entry.get("support_enable") for entry in meshes.values()] == ["true", "true"], meshes
    assert "export.part_setting_all" in {entry.code for entry in findings}


def test_the_export_adds_no_brim_by_itself(tmp_path: Path, profile: Profile) -> None:
    """Ohne *Vorschläge übernehmen* bekommt kein Teil einen Brim (RM-250).

    Seit dem 03.09.2026 setzte der Export einem hohen, schmalen Teil einen
    Brim, auch wenn die Platte auf Skirt stand — mit Befund, aber ohne Klick.
    Roberts Regel vom 26.09.2026: Nur mit „Vorschläge übernehmen" wird auf das
    Modell zugeschnitten, sonst geht der Standard zum Slicer. Am Minigolf-Satz
    im ElegooSlicer lief deshalb ein anderer Rand als mit dem Profil des
    Herstellers allein (8,5 statt 11,7 m), bei gleicher Konfiguration.
    """
    schlank = MeshData.of(trimesh.creation.box(extents=(4.0, 4.0, 80.0)))
    breit = MeshData.of(trimesh.creation.box(extents=(60.0, 60.0, 10.0)))
    objects = [
        replace(scene_object("obj_1", "Turm"), mesh=schlank),
        replace(scene_object("obj_2", "Platte"), mesh=breit),
    ]
    settings = print_settings.resolve(profile, "standard")
    assert settings.adhesion.kind == "skirt", "die Vorbedingung des Tests"

    written, findings = write_assembly(
        objects, tmp_path, project_name="Gehäuse", profile=profile, settings=settings
    )

    assert not [finding for finding in findings if finding.code == "export.part_setting"]
    config = zipfile.ZipFile(written).read("Metadata/model_settings.config").decode("utf-8")
    assert "brim" not in config, "kein Brim je Teil in der Beilage"


def test_an_accepted_brim_for_a_part_is_said_out_loud(tmp_path: Path, profile: Profile) -> None:
    """Ist die Haftung übernommen, schreibt der Export den Brim je Teil — und
    sagt es.

    Gleich, welcher Wert übernommen ist: Die Platte bekommt die Grundlage, und
    der Brim steht an den Teilen, deren Geometrie ihn verlangt (Konzept
    Herstellerprofil, Entscheidung G; siehe
    :func:`test_an_accepted_brim_goes_only_to_the_part_that_needs_it`).

    **Der Grund lag dabei fertig da.** ``SettingAdvice`` trägt ihn mit, und
    sein Docstring sagt warum: „eine Zahl ohne Begründung ist im Zweifel
    schlechter als die Vorgabe, weil niemand sie nachprüfen kann." Gemessen am
    03.09.2026 kam aus ``for_part`` der fertige Satz „Dieses Teil ist hoch und
    schmal. Die Düse kann es beim Anfahren kippen." — und ``object_keys``
    machte daraus Slicer-Schlüssel und warf den Satz weg.

    Für den Kunden zählt es doppelt: Ein Brim kostet Material und muss
    abgeschnitten werden. Wer drei von fünfzehn Teilen mit Rand aus dem Drucker
    nimmt und seine Platte auf Skirt gestellt hat, sucht den Fehler bei sich.

    Einmal je Grund und nicht je Teil — dieselbe Zurückhaltung wie beim
    ungedeckelten Schnitt: Zwölf gleiche Sätze verdrängen elf andere.
    """
    schlank = MeshData.of(trimesh.creation.box(extents=(4.0, 4.0, 80.0)))
    breit = MeshData.of(trimesh.creation.box(extents=(60.0, 60.0, 10.0)))
    objects = [
        replace(scene_object("obj_1", "Turm"), mesh=schlank),
        replace(scene_object("obj_2", "Platte"), mesh=breit),
    ]
    settings = print_settings.resolve(profile, "standard")
    assert settings.adhesion.kind == "skirt", "die Vorbedingung des Tests"
    settings = print_settings.with_accepted(settings, "adhesion.kind", "skirt")

    _written, findings = write_assembly(
        objects, tmp_path, project_name="Gehäuse", profile=profile, settings=settings
    )

    treffer = [finding for finding in findings if finding.code == "export.part_setting"]
    assert treffer, [finding.code for finding in findings]
    assert [finding.object_id for finding in treffer] == ["obj_1"], "nur der Turm"
    assert "Brim" in str(treffer[0].message), treffer[0].message
    assert treffer[0].values["setting"] == "adhesion.kind"
    assert treffer[0].values["value"] == "brim"


@pytest.mark.parametrize("adhesion", ["skirt", "brim"])
def test_cura_says_when_part_settings_cannot_be_carried(
    tmp_path: Path, profile: Profile, adhesion: str
) -> None:
    """Curas STL trägt keinen Brim je Körper; der Export erklärt den unerfüllten Rat."""
    mesh = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 80.0)))
    body = replace(scene_object("obj_1", "Turm"), mesh=mesh)
    settings = print_settings.resolve(profile, "standard")
    settings = print_settings.with_accepted(settings, "adhesion.kind", adhesion)

    written, findings = write_assembly(
        [body], tmp_path, project_name="Turm", profile=profile, settings=settings, flavour="cura"
    )

    assert written.suffix == ".stl"
    assert read_mesh(written.read_bytes(), ".stl").volume == pytest.approx(mesh.volume)
    unavailable = [entry for entry in findings if entry.code == "export.part_setting_unavailable"]
    assert len(unavailable) == (1 if adhesion == "skirt" else 0)
    assert not [entry for entry in findings if entry.code == "export.part_setting"]
    if unavailable:
        assert unavailable[0].severity == "warning"
        assert unavailable[0].values["setting"] == "adhesion.kind"
        assert unavailable[0].values["value"] == "brim"
        assert unavailable[0].object_id == "obj_1"
        assert str(unavailable[0].values["reason"])


def _mushroom_and_block() -> list[SceneObject]:
    """Ein Pilz — Stiel 10 × 10 × 20, Hut 40 × 40 × 3, 15 mm frei auskragend,
    ohne Stützen nicht zu drucken — und daneben ein Klotz ohne Überhang."""
    stem = trimesh.creation.box(extents=(10.0, 10.0, 20.0))
    stem.apply_translation((0.0, 0.0, 10.0))
    cap = trimesh.creation.box(extents=(40.0, 40.0, 3.0))
    cap.apply_translation((0.0, 0.0, 21.5))
    block = trimesh.creation.box(extents=(30.0, 30.0, 10.0))
    block.apply_translation((0.0, 0.0, 5.0))
    return [
        replace(
            scene_object("obj_1", "Pilz"), mesh=MeshData.of(trimesh.boolean.union([stem, cap]))
        ),
        replace(scene_object("obj_2", "Klotz"), mesh=MeshData.of(block)),
    ]


@pytest.mark.parametrize(
    ("flavour", "member", "key"),
    [
        ("orca", "Metadata/model_settings.config", "enable_support"),
        ("prusa", "Metadata/Slic3r_PE_model.config", "support_material"),
    ],
)
def test_supports_go_only_to_the_part_whose_geometry_needs_them(
    tmp_path: Path, profile: Profile, flavour: SlicerFlavour, member: str, key: str
) -> None:
    """Ein übernommener Stützvorschlag gilt dem Körper, der ihn braucht
    (Konzept Herstellerprofil, Entscheidung G): Die Platte bleibt ohne
    Stützen, der Pilz bekommt sie als Objektwert, der Klotz nichts. Vorher
    stützte der Slicer die ganze Platte, und an jedem Teil ohne Überhang stand
    ein Satz Stützeinstellungen, der nur Zeit kostete, wo er griff."""
    settings = print_settings.resolve(profile, "standard")
    assert settings.support.style == "none", "die Vorbedingung des Tests"
    settings = print_settings.with_accepted(settings, "support.style", "auto")

    written, findings = write_assembly(
        _mushroom_and_block(),
        tmp_path,
        project_name="Pilze",
        profile=profile,
        settings=settings,
        flavour=flavour,
    )

    assert _plate_value(written, flavour, key) in ("0", ["0"]), "die Platte stützt nicht"
    values = _object_values(written, member)
    assert values["Pilz"][key] == "1"
    assert key not in values["Klotz"]
    if flavour == "prusa":
        # Prusas Grundlage stützt nur an Verstärkern (``support_material_auto =
        # 0``); ohne den zweiten Schalter am Teil blieb der Pilz ohne Stütze —
        # gemessen in der Abnahme von Stufe E, PrusaSlicer 2.9.6.
        assert values["Pilz"]["support_material_auto"] == "1"
    treffer = [finding for finding in findings if finding.code == "export.part_setting"]
    assert [(finding.object_id, finding.values["setting"]) for finding in treffer] == [
        ("obj_1", "support.style")
    ]


def test_cura_takes_supports_back_where_a_part_does_not_need_them(
    tmp_path: Path, profile: Profile
) -> None:
    """CuraEngine nimmt ob gestützt wird je Netz an (``support_enable``), die
    Stützart aber nur für die Platte (``support_structure``, Cura 5.13). Die
    Übernahme bleibt deshalb auf der Platte, und der Klotz bekommt sie je Netz
    zurückgenommen; der Pilz behält die Stützart der Platte, und der Befund
    nennt diese. Je Netz steht nur, was Cura dort liest."""
    settings = print_settings.with_accepted(
        print_settings.resolve(profile, "standard"), "support.style", "tree"
    )

    written, findings = write_assembly(
        _mushroom_and_block(),
        tmp_path,
        project_name="Pilze",
        profile=profile,
        settings=settings,
        flavour="cura",
    )

    meshes = {mesh.path.name: dict(mesh.settings) for mesh in handover.cura_meshes(written)}
    assert meshes == {
        "Pilze-part-1.stl": {"support_enable": "true"},
        "Pilze-part-2.stl": {"support_enable": "false"},
    }
    treffer = [finding for finding in findings if finding.code == "export.part_setting"]
    assert [(finding.object_id, finding.values["value"]) for finding in treffer] == [
        ("obj_1", "tree")
    ]


def test_the_scarf_seam_goes_to_the_round_part_only(tmp_path: Path, profile: Profile) -> None:
    """Die Schrägnaht gilt dem runden Teil (Entscheidung G): Das Rohr hat
    keine Ecke, in der die Naht verschwindet, der Klotz daneben vier. Die
    Platte bleibt ohne, das Rohr bekommt sie als Objektwert bei der
    Orca-Familie und PrusaSlicer, und bei Cura nimmt das Netz des Klotzes sie
    zurück."""
    tube = trimesh.creation.cylinder(radius=12.5, height=40.0, sections=128)
    tube.apply_translation((0.0, 0.0, 20.0))
    block = trimesh.creation.box(extents=(25.0, 25.0, 40.0))
    block.apply_translation((0.0, 0.0, 20.0))
    objects = [
        replace(scene_object("obj_1", "Rohr"), mesh=MeshData.of(tube)),
        replace(scene_object("obj_2", "Klotz"), mesh=MeshData.of(block)),
    ]
    settings = print_settings.with_accepted(
        print_settings.resolve(profile, "standard"), "shell.scarf_seam", True
    )

    def written(flavour: SlicerFlavour) -> tuple[Path, list[Finding]]:
        return write_assembly(
            objects,
            tmp_path / flavour,
            project_name="Rohre",
            profile=profile,
            settings=settings,
            flavour=flavour,
        )

    orca, findings = written("orca")
    assert _plate_value(orca, "orca", "seam_slope_type") == "none", "die Platte bleibt"
    values = _object_values(orca, "Metadata/model_settings.config")
    assert values["Rohr"]["seam_slope_type"] == "external"
    assert values["Rohr"]["seam_slope_min_length"] == "20"
    assert "seam_slope_type" not in values["Klotz"]
    said = [finding.object_id for finding in findings if finding.code == "export.part_setting"]
    assert said == ["obj_1"], "einmal, für das Rohr"

    prusa, _findings = written("prusa")
    parts = _object_values(prusa, "Metadata/Slic3r_PE_model.config")
    assert parts["Rohr"]["scarf_seam_placement"] == "contours"
    assert "scarf_seam_placement" not in parts["Klotz"]

    cura, _findings = written("cura")
    meshes = {mesh.path.name: dict(mesh.settings) for mesh in handover.cura_meshes(cura)}
    assert meshes["Rohre-part-1.stl"]["scarf_joint_seam_length"] == "20"
    assert meshes["Rohre-part-2.stl"]["scarf_joint_seam_length"] == "0"


def test_a_part_gets_what_its_second_spool_asks_for(tmp_path: Path, profile: Profile) -> None:
    """Der Rat je Teil fragt jede Spule des Teils, nicht nur Slot 0.

    Ein Deckel in PETG mit einem Griff aus TPU: Der Druckdialog fragt je Spule
    und schlägt für das weiche Filament die langsame Außenwand vor. Übernommen
    geht sie je Teil (Entscheidung G) — und der Export fragte bis dahin nur das
    Material von Slot 0. Der Griff bekam den Vorschlag nicht, den der Dialog
    für ihn gezeigt hatte, und das TPU lief mit dem Tempo des PETG.
    """
    from app.core.geom.attributes import used_slots

    griff_netz = MeshData.of(trimesh.creation.box(extents=(30.0, 30.0, 10.0)))
    griff_netz = replace(griff_netz, slots=(0, 1) * (griff_netz.triangle_count // 2))
    assert used_slots(griff_netz) == (0, 1), "die Vorbedingung des Tests"
    objects = [
        replace(
            scene_object("obj_1", "Griff"),
            mesh=griff_netz,
            material_slots=[
                MaterialSlot(0, "Grau", material_type="PETG"),
                MaterialSlot(1, "Weich", material_type="TPU"),
            ],
        ),
        replace(
            scene_object("obj_2", "Deckel"),
            mesh=MeshData.of(trimesh.creation.box(extents=(30.0, 30.0, 10.0))),
        ),
    ]
    settings = print_settings.resolve(profile, "standard")
    assert settings.speed.outer_wall > advise.FLEXIBLE_MAX_SPEED, "die Vorbedingung des Tests"
    assert "speed.outer_wall" not in advise.plate_paths(settings, profile), (
        "für PETG ist das Tempo kein Grund der ganzen Platte"
    )
    settings = print_settings.with_accepted(settings, "speed.outer_wall", advise.FLEXIBLE_MAX_SPEED)

    written, findings = write_assembly(
        objects, tmp_path, project_name="Deckel", profile=profile, settings=settings
    )

    values = _object_values(written, "Metadata/model_settings.config")
    assert float(values["Griff"]["outer_wall_speed"]) == pytest.approx(advise.FLEXIBLE_MAX_SPEED)
    assert "outer_wall_speed" not in values["Deckel"]
    treffer = [finding for finding in findings if finding.code == "export.part_setting"]
    assert [(finding.object_id, finding.values["setting"]) for finding in treffer] == [
        ("obj_1", "speed.outer_wall")
    ]


def test_a_plate_wide_reason_keeps_the_accepted_value_on_the_plate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verlangt das Material den Brim (ABS auf einem offenen Drucker), gilt er
    übernommen der ganzen Platte — auch wo zusätzlich ein Teil schlank ist.
    Bei PLA auf demselben Drucker geht er je Teil (``advise.plate_paths``).

    Die Grundlage ist hier eine mit Schürze, wie der Hersteller sie oft führt;
    Solidons eigene Tabelle legt für ABS schon selbst einen Brim, und dann
    gäbe es nichts zu trennen."""
    from types import SimpleNamespace

    from app.core.export import manufacturer

    def split(material: str) -> handover.PartSplit:
        chosen = profiles.make_profile("prusa-mk4s", material)
        skirted = print_settings.with_path(print_settings.resolve(chosen), "adhesion.kind", "skirt")
        monkeypatch.setattr(
            manufacturer,
            "base_settings",
            lambda *_args, **_kwargs: SimpleNamespace(settings=skirted),
        )
        accepted = print_settings.with_accepted(skirted, "adhesion.kind", "brim")
        return handover.split_for_parts(accepted, chosen, None, "orca")

    material = split("abs")
    assert material.per_part == frozenset()
    assert material.plate.adhesion.kind == "brim"

    geometry = split("pla")
    assert geometry.per_part == frozenset({"adhesion.kind"})
    assert geometry.plate.adhesion.kind == "skirt"
    assert geometry.base.adhesion.kind == "skirt"


def test_nothing_is_said_when_every_part_takes_the_plates_setting(
    tmp_path: Path, profile: Profile
) -> None:
    """Die Gegenprobe: Wo nichts abweicht, steht auch nichts."""
    breit = MeshData.of(trimesh.creation.box(extents=(60.0, 60.0, 10.0)))
    objects = [replace(scene_object("obj_1", "Platte"), mesh=breit)]

    _written, findings = write_assembly(
        objects,
        tmp_path,
        project_name="Gehäuse",
        profile=profile,
        settings=print_settings.resolve(profile, "standard"),
    )

    assert not [finding for finding in findings if finding.code == "export.part_setting"]


def test_an_empty_object_says_what_to_do_about_it(tmp_path: Path, profile: Profile) -> None:
    """Der schwerste Befund des Exports endete mit „hat keine Geometrie".

    ``export.empty`` ist ``error`` — das Stärkste, was der Prüfbericht sagen
    kann — und trug weder einen eigenen Ausweg noch einen in der Tabelle des
    Fensters. Damit ist es „geht nicht" an einem anderen Ort; Regel 17 gilt im
    Bericht so gut wie im Dialog.

    Gefunden am 03.09.2026 beim Durchzählen aller Fehlerbefunde: Von fünfzehn
    tragen sieben einen Knopf über ``panels.FINDING_ACTIONS``, acht gar nichts.
    Dieser hier liegt im Export und damit an der Stelle, an der er entsteht.

    **Zwei Auswege, beide verdrahtet und beide wahr.** Ein Objekt ohne
    Dreiecke ist entweder das falsche in der Auswahl — dann hilft eine andere
    Auswahl — oder das Ergebnis eines Schritts, der nichts übrig gelassen hat;
    dann steht im Verlauf, welcher. Ein dritter Knopf wäre geraten.

    Am Befund selbst und nicht in der Tabelle des Fensters: ``_actions_for``
    liest ``finding.suggestions`` zuerst und die Tabelle nur als Rückfall. Der
    Grund, warum es hier gehört, ist derselbe wie bei jeder Operation — wer den
    Befund erzeugt, weiß am besten, was hilft.
    """
    leer = MeshData.of(trimesh.Trimesh())
    objects = [replace(scene_object("obj_1", "Nichts"), mesh=leer)]

    _written, findings = write_assembly(objects, tmp_path, project_name="Gehäuse", profile=profile)

    treffer = [finding for finding in findings if finding.code == "export.empty"]
    assert treffer, [finding.code for finding in findings]
    wege = [action.id for action in treffer[0].suggestions]
    assert "change_selection" in wege, wege
    assert "show_history" in wege, wege
    assert treffer[0].object_id == "obj_1", "der Befund nennt das Objekt, um das es geht"


def test_numbering_never_lands_on_a_name_the_job_already_uses(profile: Profile) -> None:
    """Gesamtreview 05.09.2026, CORE-18: ``A``, ``A`` und ``A-1`` wurden
    ``A-1``, ``A-2``, ``A-1`` — die laufende Nummer wurde nie gegen die
    geplanten Namen geprüft, und das erste Teil verschwand unter dem dritten,
    während ``write_plan`` drei Pfade meldete."""
    objects = [
        scene_object("obj_1", "A"),
        scene_object("obj_2", "A"),
        scene_object("obj_3", "A-1"),
    ]

    plan = plan_export(objects, project_name="P", profile=profile, scheme="{object}")

    names = [entry.filename for entry in plan.entries]
    assert names == ["A-2.stl", "A-3.stl", "A-1.stl"], "was allein steht, behält seinen Namen"
    assert len({name.casefold() for name in names}) == 3


def test_numbering_treats_upper_and_lower_case_as_one_name(
    tmp_path: Path, profile: Profile
) -> None:
    """``A.stl`` und ``a.stl`` sind auf Windows und macOS dieselbe Datei:
    zwei gemeldete Pfade, einer auf der Platte, der erste Körper weg. Die
    Kollisionsregel faltet den Namen, auf jeder Plattform."""
    objects = [scene_object("obj_1", "A"), scene_object("obj_2", "a")]

    plan = plan_export(objects, project_name="P", profile=profile, scheme="{object}")
    names = [entry.filename for entry in plan.entries]
    assert len({name.casefold() for name in names}) == 2, names

    written = write_plan(plan, tmp_path)
    assert len(written) == 2
    assert len(list(tmp_path.glob("*.stl"))) == 2, "zwei Dateien auf der Platte"


def test_glb_keeps_every_region_when_slot_names_collide() -> None:
    """Gesamtreview 05.09.2026, CORE-19: Die Teilnetze wurden nach dem
    bereinigten Anzeigenamen abgelegt — zwei Slots namens „Farbe", oder
    ``A/B`` neben ``AB``, ersetzten einander: sechs statt zwölf Dreiecke,
    eine ganze Farbregion fehlte. Die Slotnummer ist die Identität."""
    plain = body()
    two_tone = MeshData(raw=plain.raw, slots=tuple(0 if index < 6 else 1 for index in range(12)))
    for names in (("Farbe", "Farbe"), ("A/B", "AB")):
        slots = [
            MaterialSlot(index=0, name=names[0], colour=(1.0, 0.0, 0.0)),
            MaterialSlot(index=1, name=names[1], colour=(0.0, 0.0, 1.0)),
        ]
        written = trimesh.load(
            BytesIO(export_bytes(two_tone, "glb", slots=slots, name="Schild")),
            file_type="glb",
        )
        assert sum(len(geometry.faces) for geometry in written.geometry.values()) == 12, names


def test_same_colour_but_another_material_stays_its_own_extruder() -> None:
    """Gesamtreview 05.09.2026, CORE-21: Zwei Teile, je ein Slot „Schwarz" in
    Schwarz — eines PLA, eines PETG. Zusammengelegt wurde über Name und
    Farbe: ein Materialeintrag, jedes Dreieck an Düse 0, das PETG-Profil weg.
    Gleicher Name und gleiche Farbe fallen nur zusammen, wenn auch Profil und
    Materialart gleich sind."""
    black = (0.0, 0.0, 0.0)
    pla = MaterialSlot(
        index=0, name="Schwarz", colour=black, material="PLA Basic", material_type="PLA"
    )
    petg = MaterialSlot(
        index=0, name="Schwarz", colour=black, material="PETG Basic", material_type="PETG"
    )
    parts = [
        threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box()), name="A", slots=(pla,)),
        threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box()), name="B", slots=(petg,)),
    ]

    merged = threemf.merge_slots(parts)
    assert [(slot.index, slot.material_type) for slot in merged] == [(0, "PLA"), (1, "PETG")]

    payload = threemf.write_assembly(parts)
    model = zipfile.ZipFile(BytesIO(payload)).read(threemf.MODEL_PATH).decode("utf-8")
    assert model.count("<base ") == 2, "zwei Materialien in der Baugruppe"
    assert 'p1="1"' in model, "und das zweite Teil zeigt auf das zweite"

    twin = MaterialSlot(
        index=0, name="Schwarz", colour=black, material="PLA Basic", material_type="PLA"
    )
    assert (
        len(
            threemf.merge_slots(
                [parts[0], threemf.AssemblyPart(mesh=parts[1].mesh, name="C", slots=(twin,))]
            )
        )
        == 1
    ), "dasselbe Filament bleibt eine Düse"


def test_glb_is_written_in_metres(tmp_path: Path) -> None:
    """Gesamtreview 05.09.2026, CORE-33: glTF 2.0 legt den Meter als Einheit
    fest (Abschnitt 3.4). Die Millimeter gingen unverändert hinaus — ein
    Quader 10 x 20 x 40 mm kam als 10 x 40 x 20 m an, und nur ein Betrachter
    mit automatischem Einpassen verbarg das."""
    original = MeshData.of(trimesh.creation.box(extents=(10.0, 20.0, 40.0)))
    written = trimesh.load(BytesIO(export_bytes(original, "glb")), file_type="glb")
    extents = written.bounds[1] - written.bounds[0]

    assert sorted(extents) == pytest.approx([0.01, 0.02, 0.04], abs=1e-9)


def test_prusa_gets_the_individual_brim_in_its_own_object_configuration(
    tmp_path: Path, profile: Profile
) -> None:
    """Die zugesagte Objektabweichung muss in Prusas gelesener Beilage stehen."""
    import xml.etree.ElementTree as ET

    tower = trimesh.creation.box(extents=(4.0, 4.0, 20.0))
    tower.apply_translation((0.0, 0.0, 10.0))
    objects = [scene_object(mesh=MeshData.of(tower))]
    settings = print_settings.resolve(profile)
    settings = print_settings.with_accepted(settings, "adhesion.kind", settings.adhesion.kind)
    path, findings = write_assembly(
        objects,
        tmp_path,
        project_name="Turm",
        profile=profile,
        settings=settings,
        flavour="prusa",
    )
    assert "export.part_setting" in {entry.code for entry in findings}
    with zipfile.ZipFile(path) as archive:
        config = ET.fromstring(archive.read("Metadata/Slic3r_PE_model.config"))
    obj = config.find("object")
    assert obj is not None and obj.get("id") == "2"
    assert obj.find("metadata[@type='object'][@key='brim_width']").get("value") == "5"
    assert obj.find("volume").get("lastid") == str(len(tower.faces) - 1)


def test_cura_export_reports_lost_second_material_values(tmp_path: Path, profile: Profile) -> None:
    """Auch der früh zurückkehrende STL-Weg benennt den verlorenen Materialwertsatz."""
    first = replace(
        scene_object("obj_1"), material_slots=(MaterialSlot(0, "PLA", material_type="PLA"),)
    )
    second = replace(
        scene_object("obj_2"), material_slots=(MaterialSlot(0, "PETG", material_type="PETG"),)
    )
    _, findings = write_assembly(
        [first, second],
        tmp_path,
        project_name="Materialien",
        profile=profile,
        settings=print_settings.resolve(profile),
        flavour="cura",
    )
    assert "slicer.overrides_unreachable" in {entry.code for entry in findings}


def test_legacy_body_material_gets_its_own_slot_without_changing_declared_slots() -> None:
    """Ein altes ABS-Körpermaterial darf nicht mit einem unbekannten PLA-Platz verschmelzen."""
    legacy = replace(scene_object(), material="abs")
    original = tuple(legacy.material_slots)
    slots = threemf.slots_for_object(legacy)
    assert len(slots) == 1
    assert slots[0].index == 0 and slots[0].material_type == "ABS"
    assert tuple(legacy.material_slots) == original
    assert threemf.slots_for_object(scene_object()) == ()

    declared = MaterialSlot(0, "Eigene Spule", material="Hersteller PLA", material_type="PLA")
    supplied = replace(legacy, material_slots=[declared])
    assert threemf.slots_for_object(supplied) == (declared,)
    assert threemf.slots_for_object(supplied)[0] is declared

    mesh = replace(legacy.mesh, slots=(0, 1) * (legacy.mesh.triangle_count // 2))
    completed = threemf.assembly_slots(threemf.AssemblyPart(mesh, slots=slots))
    assert [(slot.index, slot.material_type) for slot in completed] == [(0, "ABS"), (1, None)]


def test_legacy_body_material_reaches_assembly_and_single_file_export(
    tmp_path: Path,
) -> None:
    """PLA und altes ABS behalten getrennte Werkzeuge und die jeweils wirksame Temperatur."""
    profile = profiles.make_profile(material_id="pla")
    first = scene_object("obj_1")
    second = replace(scene_object("obj_2"), material="abs")
    target, _ = write_assembly(
        [first, second],
        tmp_path,
        project_name="Alte Materialangaben",
        profile=profile,
        settings=print_settings.resolve(profile),
        flavour="orca",
    )
    with zipfile.ZipFile(target) as archive:
        project = json.loads(archive.read(threemf.PROJECT_SETTINGS_PATH))
    assert project["filament_type"] == ["PLA", "ABS"]
    assert project["nozzle_temperature"] == ["210", "250"]

    plan = plan_export([second], profile=profile, export_format="3mf", project_name="ABS")
    assert plan.entries[0].slots[0].material_type == "ABS"


@pytest.mark.parametrize("flavour", ["prusa", "cura"])
def test_shared_slicer_reports_legacy_material_loss_and_keeps_the_first_material(
    tmp_path: Path, profile: Profile, flavour
) -> None:
    """Ein gemeinsam beschränkter Export rät nicht still das Material der Projektvorgabe."""
    from app.core.export import handover

    legacy = replace(scene_object("obj_1"), material="abs")
    ordinary = scene_object("obj_2")
    settings = print_settings.resolve(profile)
    slots = threemf.merge_slots(
        [
            threemf.AssemblyPart(entry.mesh, slots=threemf.slots_for_object(entry))
            for entry in (legacy, ordinary)
        ]
    )
    effective = handover.settings_for_handover(settings, profile, flavour, slots)
    assert effective.temperature.nozzle == 250
    _, findings = write_assembly(
        [legacy, ordinary],
        tmp_path,
        project_name="Alt und neu",
        profile=profile,
        settings=settings,
        flavour=flavour,
    )
    assert "slicer.overrides_unreachable" in {entry.code for entry in findings}


# --- die Vorgabe steht an einer Stelle (RM-141) -----------------------------------


def test_the_default_scheme_is_asked_and_not_recomputed(profile: Profile) -> None:
    """Das Fenster zeigt dasselbe Muster, nach dem der Kern benennt (§29, RM-141).

    Es schreibt es bei mehreren Dateien ins Namensfeld des Dateidialogs,
    damit der Kunde es ändern kann. Zwei Stellen, die es ausrechnen, wären
    zwei Antworten — und die des Dialogs wäre die sichtbare.
    """
    from app.core.export.writer import DEFAULT_SCHEME, PLATE_SCHEME, SINGLE_SCHEME, default_scheme

    one = scene_object()
    two = [scene_object(), scene_object("obj_2", "Deckel")]
    plates = [scene_object(), replace(scene_object("obj_2", "Deckel"), plate=1)]

    assert default_scheme([one]) == SINGLE_SCHEME
    assert default_scheme(two) == DEFAULT_SCHEME
    assert default_scheme(plates) == PLATE_SCHEME

    plan = plan_export(two, project_name="Projekt", profile=profile)
    assert [entry.filename for entry in plan.entries] == [
        "Projekt_Halterung_1von2.stl",
        "Projekt_Deckel_2von2.stl",
    ], "und der Plan benennt danach"


def test_a_chosen_scheme_decides_the_names(profile: Profile) -> None:
    """Ein selbst gewähltes Muster gilt, Feld für Feld (§29, RM-141).

    Der Kunde tippt es ins Namensfeld; was dort mit Klammern steht, ist ein
    Muster und kein Name. Hier steht, was daraus wird — auch die Reihenfolge,
    denn genau dafür stellt jemand ein Schema um.
    """
    two = [scene_object(), scene_object("obj_2", "Deckel")]

    plan = plan_export(
        two,
        project_name="Projekt",
        profile=profile,
        scheme="{index}_{object}",
    )

    assert [entry.filename for entry in plan.entries] == ["1_Halterung.stl", "2_Deckel.stl"]


def test_a_body_named_like_the_geometry_mark_still_exports() -> None:
    # Der Name reist unverändert ins XML. Vorher zählte die Marke doppelt,
    # und ein RuntimeError riss den Export-Arbeiter ohne einen Weg ab.
    part = threemf.AssemblyPart(
        mesh=MeshData.of(trimesh.creation.box((10, 10, 10))), name="[SOLIDON-MESH-2]"
    )
    with zipfile.ZipFile(BytesIO(threemf.write_assembly([part], "Test"))) as archive:
        model = archive.read("3D/3dmodel.model").decode("utf-8")
    assert 'name="[SOLIDON-MESH-2]"' in model
    assert "SOLIDON-MESH-" not in model.replace("[SOLIDON-MESH-2]", "")
    assert model.count("<vertex ") == 8


# --- Der Kundenweg STL → Operation → STL → Import (RM-166) --------------------


def _drilled_plate_after_an_stl_round(profile: Profile) -> MeshData:
    """Die Platte der Werkstattfilme: 100 x 55 x 8 mit zwei 6-mm-Bohrungen —
    einmal durch eine STL geschickt, damit sie in float32 ankommt wie beim
    Kunden."""
    from app.core.geom.prepare import drill

    plate = MeshData.of(trimesh.creation.box(extents=(100.0, 55.0, 8.0)))
    for x in (-28.0, 28.0):
        plate = drill(
            plate,
            position=(x, 0.0, 4.0),
            axis="z",
            diameter=6.0,
            depth=0.0,
            profile=profile,
            compensate=False,
        ).mesh
    return normalise(read_model(plate.to_stl(), ".stl"), "mm").mesh


def _run_registered(name: str, entry: SceneObject, profile: Profile, **params):
    """Derselbe registrierte Aufruf wie im Dialog."""
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext

    load_operations()
    spec = REGISTRY.get(name)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=1,
            progress=lambda *_: None,
            ask=lambda _, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


@pytest.mark.parametrize("source", ["plate_holes.stl", "gebohrte Platte"])
@pytest.mark.parametrize(
    "operation", ["resize_hole", "move_feature", "fillet_edges", "chamfer_edges"]
)
def test_a_mesh_op_result_on_an_stl_survives_the_weld(
    operation: str, source: str, profile: Profile
) -> None:
    """Was Solidon exportiert, muss der nächste Import — und jeder Slicer — als
    geschlossen lesen (RM-166).

    Gefunden am 13.09.2026 beim Prüfen der Werkstattfilme: Nach *Bohrung
    ändern*, *Merkmal verschieben* und *Fase anbringen* an einer **eingelesenen**
    STL war das Ergebnis per Index dicht, nach dem Verschweißen nicht mehr —
    Solidons eigener Import derselben Datei meldete „Das Modell ist nicht
    geschlossen". Zwei Ursachen: ``manifold3d`` ließ auf dem alten Bohrkreis
    Eckpunktpaare unter der Schweißtoleranz und Sliver stehen (jetzt räumt
    ``boolean._tidied`` auf), und der abziehende Keil der Fase stand mit seinen
    Flanken **in** der fast koplanaren Körperfläche und ließ Haut ohne Dicke
    zurück (jetzt ``BOOLEAN_OVERLAP`` in ``edges.rounding_tool``).

    Zwei Quellen, weil sie verschiedene Fehler zeigen: Am Korpus
    ``plate_holes.stl`` rissen die Bohrungsoperationen, an der gebohrten
    Platte der Filme zusätzlich die Fase über die Bohrungsränder. Der Weg ist
    der des Kunden — ``read_model`` + ``normalise``, Operation über das
    Register, ``to_stl()``, wieder ``read_model`` + ``normalise`` — und die
    Zusicherung ist die von ``repair()``: dicht, Volumen unverändert.
    """
    from app.core.perceive.features import detect

    if source == "plate_holes.stl":
        plate = normalise(read_model((MESHES / source).read_bytes(), ".stl"), "mm").mesh
    else:
        plate = _drilled_plate_after_an_stl_round(profile)
    assert plate.is_watertight
    entry = SceneObject("obj_1", "Platte", plate, features=detect(plate))
    hole = next(feature for feature in entry.features.values() if feature.kind == "hole")
    cx, cy, cz = hole.params["centre"]
    params = {
        "resize_hole": {"at_feature": hole.id, "diameter": 9.0, "compensate": False, "x": cx + 4.0},
        "move_feature": {"at_feature": hole.id, "x": cx + 6.0, "y": cy, "z": cz},
        "fillet_edges": {"radius": 3.0, "edges": "vertical"},
        "chamfer_edges": {"distance": 0.8, "edges": "top"},
    }[operation]

    result = _run_registered(operation, entry, profile, **params)
    made = result.outputs[0].mesh
    assert made.is_watertight, "per Index dicht ist die Voraussetzung, nicht der Befund"

    back = normalise(read_model(made.to_stl(), ".stl"), "mm")
    codes = {finding.code for finding in back.findings}
    assert back.mesh.is_watertight, f"nach der STL-Runde nicht mehr geschlossen — {sorted(codes)}"
    assert "ingest.not_watertight" not in codes and "ingest.degenerate_removed" not in codes, codes
    assert back.mesh.raw.volume == pytest.approx(made.raw.volume, abs=1e-3), (
        "das Verschweißen ändert das Volumen nicht"
    )
    if operation == "move_feature":
        assert made.raw.volume == pytest.approx(plate.raw.volume, abs=1e-3), (
            "ein verschobenes Loch nimmt nichts weg und legt nichts dazu"
        )
    else:
        assert made.raw.volume < plate.raw.volume, "die drei anderen tragen ab"


# --- Cura im Fenster: die Einstellungen als Profil (Durchsicht 0.5.0) --------------


def _cura_install(tmp_path: Path) -> Path:
    """Eine Cura-Installation mit dem, was ihr Profilleser prüft.

    ``fdmprinter.def.json`` trägt die Einstellungsversion und die Typen der
    Einstellungen, zwei allgemeine Qualitätsstufen daneben — gebaut nach Cura
    5.13 (``share/cura/resources``), nicht nach Solidons Vorstellung davon.
    """
    install = tmp_path / "UltiMaker Cura 5.13.0"
    resources = install / "share" / "cura" / "resources"
    (resources / "definitions").mkdir(parents=True)
    (resources / "definitions" / "fdmprinter.def.json").write_text(
        json.dumps({"version": 2, "name": "FDM Printer", "metadata": {"setting_version": 27}}),
        encoding="utf-8",
    )
    (resources / "quality").mkdir()
    for kind, height in (("draft", 0.2), ("normal", 0.1)):
        (resources / "quality" / f"{kind}.inst.cfg").write_text(
            f"[general]\ndefinition = fdmprinter\nname = {kind}\nversion = 4\n\n"
            f"[metadata]\nglobal_quality = True\nquality_type = {kind}\n"
            "setting_version = 27\ntype = quality\n\n"
            f"[values]\nlayer_height = {height}\n",
            encoding="utf-8",
        )
    # Ein Drucker ohne eigene Qualitäten, wie der Kobra 2 in Cura: Er nimmt
    # die allgemeinen Stufen von ``fdmprinter``.
    (resources / "definitions" / "werkstatt.def.json").write_text(
        json.dumps({"version": 2, "name": "Werkstatt", "inherits": "fdmprinter"}),
        encoding="utf-8",
    )
    engine = install / "CuraEngine.exe"
    engine.write_bytes(b"")
    return engine


def _cura_active(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str = "Werkstatt",
    definition: str = "werkstatt",
    *,
    variant: str = "empty_variant",
    material: str = "empty_material",
) -> None:
    """Curas Konfigurationsordner mit einem eingerichteten, aktiven Drucker.

    Wie Cura 5.13 ihn schreibt: ``cura.cfg`` nennt ihn, sein Stapel in
    ``machine_instances`` die Definition an letzter Stelle, der Stapel des
    ersten Fachs Düse (Stelle 5) und Spule (Stelle 4).
    """
    from app.core.export import slicer_profiles

    config = tmp_path / "config"
    root = config / "cura" / "5.13"
    (root / "machine_instances").mkdir(parents=True)
    (root / "extruders").mkdir()
    (root / "cura.cfg").write_text(
        f"[general]\nversion = 7\n\n[cura]\nactive_machine = {name}\n", encoding="utf-8"
    )
    (root / "machine_instances" / f"{name.replace(' ', '+')}.global.cfg").write_text(
        f"[general]\nversion = 5\nname = {name}\nid = {name}\n\n"
        "[metadata]\nsetting_version = 27\ntype = machine\n\n"
        f"[containers]\n0 = {name}_user\n1 = empty_quality_changes\n2 = empty_intent\n"
        f"3 = empty_quality\n4 = empty_material\n5 = empty_variant\n6 = {name}_settings\n"
        f"7 = {definition}\n",
        encoding="utf-8",
    )
    (root / "extruders" / f"{name.replace(' ', '+')}_0.extruder.cfg").write_text(
        f"[general]\nversion = 5\nname = Extruder 1\nid = {name}_0\n\n"
        f"[metadata]\ntype = extruder_train\nmachine = {name}\nposition = 0\n\n"
        "[containers]\n0 = empty_user_changes\n1 = empty_quality_changes\n"
        f"2 = empty_intent\n3 = empty_quality\n4 = {material}\n5 = {variant}\n"
        "6 = empty_definition_changes\n7 = fdmextruder\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(slicer_profiles, "config_home", lambda _platform: str(config))


def _cura_containers(target: Path) -> dict[str, dict[str, dict[str, str]]]:
    """Die Einträge so gelesen wie Curas ``CuraProfileReader``: INI ohne Interpolation."""
    import configparser

    found: dict[str, dict[str, dict[str, str]]] = {}
    with zipfile.ZipFile(target) as archive:
        for name in archive.namelist():
            parser = configparser.ConfigParser(interpolation=None)
            parser.read_string(archive.read(name).decode("utf-8"))
            found[name] = {section: dict(parser[section]) for section in parser.sections()}
    return found


def test_cura_opens_with_its_settings_as_an_importable_profile(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Im Slicer öffnen" gab Cura ein bloßes STL — die Einstellungen blieben zurück.

    Cura liest aus einer geöffneten Datei nur Geometrie; Einstellungen nimmt
    sein Fenster als Profil an. Seit der Durchsicht 0.5.0 liegt deshalb eine
    ``.curaprofile`` neben dem Modell, und der Befund sagt, wo sie in Cura
    hineingeht. Geprüft wie Curas eigener Leser: Container Version 4, die
    Einstellungsversion der Installation, eine Qualitätsstufe, die es gibt,
    und Wahrheitswerte als ``True`` — ``ast.literal_eval`` liest kein
    ``true``. Maschinenwerte und Abgeleitetes gehören nicht hinein: Das
    Fenster rechnet seine Formeln selbst.
    """
    engine = _cura_install(tmp_path)
    _cura_active(tmp_path, monkeypatch)
    setup = handover.SlicerSetup(engine, "cura")
    settings = print_settings.resolve(profile)
    settings = replace(settings, support=replace(settings.support, style="tree"))
    model = tmp_path / "halter.stl"
    model.write_bytes(b"solid halter\nendsolid halter\n")

    said = handover.cura_profile_beside(model, settings, profile, setup)

    assert said is not None and said.code == "handover.cura_profile"
    assert said.values["file"] == "halter.curaprofile"
    assert said.values["machine"] == "Werkstatt", "der Befund nennt den Drucker in Cura"
    containers = _cura_containers(model.with_suffix(".curaprofile"))
    assert list(containers) == ["solidon"], "eine einzelne Spule legt Cura selbst aufs erste Fach"
    entry = containers["solidon"]
    assert entry["general"]["version"] == "4"
    assert entry["metadata"]["setting_version"] == "27"
    assert entry["metadata"]["type"] == "quality_changes"
    assert entry["metadata"]["quality_type"] == "draft", "die Stufe mit der nächsten Schichthöhe"
    values = entry["values"]
    assert values["layer_height"] == "0.2"
    assert values["support_enable"] == "True"
    assert not [key for key in values if key.startswith("machine_")], "die Maschine bleibt Curas"
    assert "infill_line_distance" not in values, "Abgeleitetes rechnet das Fenster selbst"
    assert not [value for value in values.values() if value in {"true", "false"}]


def test_cura_gets_one_extruder_profile_per_spool(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei Spulen, zwei Fächer: je Spule ein Extruderprofil mit ``position``."""
    engine = _cura_install(tmp_path)
    _cura_active(tmp_path, monkeypatch)
    model = tmp_path / "zweifarbig.stl"
    model.write_bytes(b"solid z\nendsolid z\n")
    slots = (
        MaterialSlot(index=0, name="Rot", colour="#ff0000", material_type="PETG"),
        MaterialSlot(index=1, name="Weiß", colour="#ffffff", material_type="PLA"),
    )

    handover.cura_profile_beside(
        model,
        print_settings.resolve(profile),
        profile,
        handover.SlicerSetup(engine, "cura"),
        slots,
    )

    containers = _cura_containers(model.with_suffix(".curaprofile"))
    assert [entry["metadata"].get("position") for entry in containers.values()] == [None, "0", "1"]
    assert (
        containers["solidon_extruder_0"]["values"]["material_print_temperature"]
        != containers["solidon_extruder_1"]["values"]["material_print_temperature"]
    ), "PETG und PLA fahren verschiedene Temperaturen"


def test_the_profile_takes_a_quality_of_the_printer_active_in_cura(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mit den Stufen von ``fdmprinter`` lehnte Cura das Profil ab oder versteckte es.

    An Elegoos Druckern hieß es „Quality type 'draft' is not compatible", an
    Creality und Sovol war es importiert und unsichtbar (Prüfbericht Cura,
    B9). Die Stufe kommt jetzt vom Drucker, der in Cura aktiv ist, und zwar
    eine, die es für seine Düse und seine Spule gibt: „fein" liegt genau auf
    der Schichthöhe, ein Profil für 0,4 mm und PLA hat aber nur „standard".
    """
    engine = _cura_install(tmp_path)
    resources = engine.parent / "share" / "cura" / "resources"
    for name, body in (
        ("kaste_basis", {"inherits": "fdmprinter", "metadata": {"has_machine_quality": True}}),
        (
            "kaste_k1",
            {"inherits": "kaste_basis", "metadata": {"quality_definition": "kaste_basis"}},
        ),
    ):
        (resources / "definitions" / f"{name}.def.json").write_text(
            json.dumps({"version": 2, "name": name, **body}), encoding="utf-8"
        )
    quality = resources / "quality" / "kaste"
    quality.mkdir()
    for kind, height in (("fein", 0.2), ("standard", 0.24), ("draft", 0.32)):
        (quality / f"kaste_global_{kind}.inst.cfg").write_text(
            f"[general]\ndefinition = kaste_basis\nname = {kind}\nversion = 4\n\n"
            f"[metadata]\nglobal_quality = True\nquality_type = {kind}\n"
            "setting_version = 27\ntype = quality\n\n"
            f"[values]\nlayer_height = {height}\n",
            encoding="utf-8",
        )
    (quality / "kaste_0.4_pla_standard.inst.cfg").write_text(
        "[general]\ndefinition = kaste_basis\nname = Standard\nversion = 4\n\n"
        "[metadata]\nmaterial = generic_pla\nquality_type = standard\n"
        "setting_version = 27\ntype = quality\nvariant = 0.4mm Nozzle\n\n[values]\n",
        encoding="utf-8",
    )
    (resources / "variants" / "kaste").mkdir(parents=True)
    (resources / "variants" / "kaste" / "kaste_basis_0.4.inst.cfg").write_text(
        "[general]\ndefinition = kaste_basis\nname = 0.4mm Nozzle\nversion = 4\n\n"
        "[metadata]\nhardware_type = nozzle\ntype = variant\n",
        encoding="utf-8",
    )
    (resources / "materials").mkdir()
    (resources / "materials" / "generic_pla.xml.fdm_material").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<fdmmaterial xmlns="http://www.ultimaker.com/material" version="1.3">\n'
        "  <metadata><name><brand>Generic</brand><material>PLA</material>"
        "<color>Generic</color></name></metadata>\n"
        "</fdmmaterial>\n",
        encoding="utf-8",
    )
    _cura_active(
        tmp_path,
        monkeypatch,
        "Kaste K1",
        "kaste_k1",
        variant="kaste_basis_0.4",
        material="generic_pla_175_kaste_k1_0.4",
    )
    model = tmp_path / "halter.stl"
    model.write_bytes(b"solid halter\nendsolid halter\n")
    settings = print_settings.resolve(profile)
    assert settings.layers.layer_height == pytest.approx(0.2), "die Probe braucht 0,2 mm"

    said = handover.cura_profile_beside(
        model, settings, profile, handover.SlicerSetup(engine, "cura")
    )

    assert said is not None and said.code == "handover.cura_profile"
    assert said.values["machine"] == "Kaste K1"
    entry = _cura_containers(model.with_suffix(".curaprofile"))["solidon"]
    assert entry["general"]["definition"] == "kaste_basis", "so führt Cura die Qualitäten"
    assert entry["metadata"]["quality_type"] == "standard", "die Stufe für Düse und Spule"


def test_without_a_printer_in_cura_there_is_no_profile_but_a_way(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne eingerichteten Drucker gibt es keine Stufe, auf die das Profil passt.

    Vorher entstand die Datei trotzdem, mit ``draft`` von ``fdmprinter``, und
    ging beim Import still verloren (Prüfbericht Cura, B9). Jetzt sagt ein
    Befund, was zu tun ist, und es liegt keine Datei neben dem Modell.
    """
    from app.core.export import slicer_profiles

    engine = _cura_install(tmp_path)
    monkeypatch.setattr(slicer_profiles, "config_home", lambda _platform: str(tmp_path / "leer"))
    model = tmp_path / "halter.stl"
    model.write_bytes(b"solid halter\nendsolid halter\n")

    said = handover.cura_profile_beside(
        model, print_settings.resolve(profile), profile, handover.SlicerSetup(engine, "cura")
    )

    assert said is not None and said.code == "handover.cura_profile_unbound"
    assert said.severity == "warning"
    assert [action.id for action in said.suggestions] == ["choose_slicer"]
    assert not model.with_suffix(".curaprofile").exists()


def test_only_cura_gets_a_profile_beside_the_model(tmp_path: Path, profile: Profile) -> None:
    """Die anderen Familien tragen ihre Einstellungen in der Datei selbst."""
    model = tmp_path / "teil.3mf"
    model.write_bytes(b"")
    setup = handover.SlicerSetup(tmp_path / "orca-slicer.exe", "orca")

    assert (
        handover.cura_profile_beside(model, print_settings.resolve(profile), profile, setup) is None
    )
    assert not model.with_suffix(".curaprofile").exists()


@pytest.mark.parametrize(
    ("program", "stripped"),
    [("CrealityPrint.exe", True), ("orca-slicer.exe", False)],
)
def test_the_creality_window_gets_the_file_its_console_gets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: Profile, program: str, stripped: bool
) -> None:
    """Das Fenster bekam die volle Datei, die Konsole eine Kopie ohne Plattenblock.

    Creality Print 7.2 stürzt an diesem Block einer Mehrfilament-3MF ab, und
    Fenster und Konsole sind dasselbe Programm mit demselben 3MF-Leser. Seit
    der Durchsicht 0.5.0 öffnet auch das Fenster die Datei ohne den Block —
    an Ort und Stelle, mit dem Namen, den der Kunde im Austauschordner sieht.
    Namen und Werkzeuge der Körper bleiben; die anderen Slicer bekommen die
    Datei unverändert.
    """
    from app.core.export import slicer_keys

    executable = tmp_path / program
    executable.write_bytes(b"")
    flavour = slicer_keys.flavour_of(program)
    assert flavour == "orca"
    setup = handover.SlicerSetup(executable=executable, flavour=flavour)
    settings = print_settings.resolve(profile)
    parts = [
        threemf.AssemblyPart(
            MeshData.of(trimesh.creation.box((12.0, 12.0, 3.0))),
            name=name,
            slots=(MaterialSlot(index=0, name=name, colour=colour, material_type=kind),),
        )
        for name, colour, kind in (
            ("PLA Orange", (177 / 255, 99 / 255, 10 / 255), "PLA"),
            ("PETG Weiß", (1.0, 1.0, 1.0), "PETG"),
        )
    ]
    slots = threemf.merge_slots(parts)
    model = tmp_path / "Halter.3mf"
    model.write_bytes(
        threemf.write_assembly(
            parts,
            project_settings=handover.project_settings(settings, profile, setup, slots=slots),
        )
    )
    with zipfile.ZipFile(model) as container:
        before = ET.fromstring(container.read(threemf.SETTINGS_PATH))
    assert len(before.findall("plate")) == 1
    opened: list[list[str]] = []
    monkeypatch.setattr(
        handover.subprocess, "Popen", lambda command, **_options: opened.append(command)
    )

    handover.open_in_slicer(model, setup)

    assert len(opened) == 1 and opened[0][-1] == str(model.resolve())
    with zipfile.ZipFile(model) as container:
        after = ET.fromstring(container.read(threemf.SETTINGS_PATH))
    assert len(after.findall("plate")) == (0 if stripped else 1)
    assert [
        entry.find("metadata[@key='name']").get("value") for entry in after.findall("object")
    ] == ["PLA Orange", "PETG Weiß"]
    assert [
        entry.find("metadata[@key='extruder']").get("value") for entry in after.findall("object")
    ] == ["1", "2"]
    assert not list(tmp_path.glob("*.staging.3mf")), "die Zwischenkopie bleibt nicht liegen"


# --- RM-191: jede Rolle bekommt Solidons Werte (Durchsicht 0.5.0) ---------------


def test_prusa_gets_the_infill_speed_for_solid_infill_and_no_guessed_machine_limits(
    tmp_path: Path, profile: Profile
) -> None:
    """PrusaSlicer fuhr die volle Füllung mit seinen eingebauten 20 mm/s.

    Gemessen am Gewürzregal (RM-191): 48 532 s gegen 23 655 s bei Orca für
    dieselbe Platte; danach 31 387 s gegen 26 471 s, Material innerhalb von
    drei Prozent. Dazu schätzte Prusa mit seinen 1500 mm/s² statt mit den
    angeforderten 8000 (``machine_limits_usage``).
    """
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(tmp_path / "prusa-slicer-console.exe", "prusa")

    written = handover.write_config(settings, profile, setup, tmp_path).written

    assert written["solid_infill_speed"] == f"{settings.speed.infill:g}"
    assert written["gap_fill_speed"] == f"{settings.speed.inner_wall:g}"
    assert written["machine_limits_usage"] == "ignore"


def test_the_orca_family_gets_solidons_speed_and_width_for_every_role(profile: Profile) -> None:
    """Die Orca-Familie fuhr volle Füllung und Lücken mit dem Herstellerprofil.

    Beim Centauri Carbon 2 mit 250 mm/s, während Wände und dünne Füllung
    Solidons Werte bekamen — und Innenwand und Füllung mit 0,45 mm statt
    Solidons Bahnbreite (RM-191).
    """
    settings = print_settings.resolve(profile)

    process = handover.by_section(settings, "orca")["process"]

    assert process["internal_solid_infill_speed"] == f"{settings.speed.infill:g}"
    assert process["gap_infill_speed"] == f"{settings.speed.inner_wall:g}"
    width = f"{settings.layers.line_width:g}"
    for key in (
        "outer_wall_line_width",
        "inner_wall_line_width",
        "sparse_infill_line_width",
        "internal_solid_infill_line_width",
        "top_surface_line_width",
    ):
        assert process[key] == width, key


# --- Die Stützsperre reist nur mit, wenn der Vorschlag übernommen ist ------------


def tunnel_block() -> MeshData:
    """Ein Block 60 × 40 × 40 mit einem Tunnel 20 × 20 quer hindurch.

    Die Tunneldecke hängt über dem Tunnelboden, 20 mm weit — ein Kanal
    (``analysis.CHANNEL_WIDTH``).
    """
    block = trimesh.creation.box(extents=(60.0, 40.0, 40.0))
    block.apply_translation((0.0, 0.0, 20.0))
    tunnel = trimesh.creation.box(extents=(20.0, 50.0, 20.0))
    tunnel.apply_translation((0.0, 0.0, 18.0))
    return MeshData.of(trimesh.boolean.difference([block, tunnel]))


def _blocker_ranges(written: Path) -> list[tuple[str, int, int]]:
    config = ET.fromstring(zipfile.ZipFile(written).read("Metadata/Slic3r_PE_model.config"))
    return [
        (
            volume.find("metadata[@key='volume_type']").get("value", ""),  # type: ignore[union-attr]
            int(volume.get("firstid", "-1")),
            int(volume.get("lastid", "-1")),
        )
        for volume in config.iter("volume")
    ]


def _orca_parts(written: Path) -> list[tuple[str, str]]:
    """Die Teile, die ``model_settings.config`` je Objekt nennt: (Objekt, Art)."""
    config = ET.fromstring(zipfile.ZipFile(written).read("Metadata/model_settings.config"))
    return [
        (node.get("id", ""), part.get("subtype", ""))
        for node in config.iter("object")
        for part in node.iter("part")
    ]


def test_the_support_blocker_travels_only_after_the_advice(
    tmp_path: Path, profile: Profile
) -> None:
    """Ohne „Vorschläge übernehmen" gehen die Standardeinstellungen hinaus,
    und in denen ist nichts auf dieses Modell zugeschnitten (Robert,
    26.09.2026). Mit übernommenem Vorschlag bekommt die Orca-Familie die
    Sperre als eigenes Teil desselben Objekts — so, wie sie es selbst
    schreibt. Als Bereich hinter den Dreiecken des Körpers liest der
    ElegooSlicer die Orca-Beilage, übergeht die Bereichsart und druckte die
    Sperre als Kunststoff in den Kanal (22,8 g mehr an der Waschschüssel)."""
    entry = scene_object(mesh=tunnel_block())
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "grid")

    plain, _plain_findings = write_assembly(
        [entry], tmp_path / "ohne", project_name="t", profile=profile, settings=settings
    )
    assert _orca_parts(plain) == []
    assert [kind for kind, _first, _last in _blocker_ranges(plain)] == ["ModelPart"]

    taken = print_settings.with_path(settings, "support.block_channels", True)
    written, findings = write_assembly(
        [entry], tmp_path / "mit", project_name="t", profile=profile, settings=taken
    )
    kinds = _orca_parts(written)
    assert [kind for _object, kind in kinds] == ["normal_part", "support_blocker"]
    assert {owner for owner, _kind in kinds} == {"2"}, "beide Teile gehören zum einen Objekt"
    assert [kind for kind, _first, _last in _blocker_ranges(written)] == ["ModelPart"]
    assert "export.support_blocker" in {finding.code for finding in findings}
    model = zipfile.ZipFile(written).read("3D/3dmodel.model").decode("utf-8")
    assert "slic3rpe:Version3mf" not in model, "die Orca-Familie bleibt bei ihrer Beilage"

    # Und Solidon liest seine eigene Übergabe als den einen Körper zurück.
    read_back = threemf_reader.read_objects(written.read_bytes(), [])
    assert len(read_back) == 1
    assert read_back[0].mesh.triangle_count == as_mesh_data(entry.mesh).triangle_count


def test_prusaslicer_gets_the_blocker_as_a_range_of_the_mesh(
    tmp_path: Path, profile: Profile
) -> None:
    """PrusaSlicer liest die andere Schreibweise: einen Bereich hinter den
    Dreiecken des Körpers, den ``Slic3r_PE_model.config`` benennt. Als eigene
    Komponente druckte er die Sperre als Kunststoff (38,8 g mehr an der
    Waschschüssel) — jede Familie bekommt ihre (``helpers_as_parts``)."""
    entry = scene_object(mesh=tunnel_block())
    taken = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.block_channels",
        True,
    )
    written, _findings = write_assembly(
        [entry], tmp_path, project_name="t", profile=profile, settings=taken, flavour="prusa"
    )

    body, blocker = _blocker_ranges(written)
    triangles = as_mesh_data(entry.mesh).triangle_count
    assert body == ("ModelPart", 0, triangles - 1)
    assert blocker[0] == "SupportBlocker" and blocker[1] == triangles and blocker[2] > triangles
    assert _orca_parts(written) == []
    # Ohne diese Angabe übersprang PrusaSlicer die Bereichsarten ganz: 91,0 m
    # Stütze im Sperrkörper mit und ohne Sperre, mit ihr 6,5 m.
    model = zipfile.ZipFile(written).read("3D/3dmodel.model").decode("utf-8")
    assert '<metadata name="slic3rpe:Version3mf">1</metadata>' in model
    read_back = threemf_reader.read_objects(written.read_bytes(), [])
    assert [part.mesh.triangle_count for part in read_back] == [triangles]


@pytest.mark.parametrize("flavour", ["orca", "cura"])
def test_only_the_part_that_is_supported_gets_a_blocker(
    tmp_path: Path, profile: Profile, flavour: SlicerFlavour
) -> None:
    """Die Sperre folgt den Stützen (Entscheidung G): Übernommen sind Stützen
    und Sperre, aber nur der Tunnelblock mit dem auskragenden Arm braucht
    Stützen — also sperrt nur er seine Kanäle, und der Klotz daneben bekommt
    weder das eine noch das andere. Gesagt wird es einmal, im Befund der
    Sperre mit dem Namen des Teils, nicht noch einmal als „andere Einstellung
    je Teil"."""
    arm = trimesh.creation.box(extents=(30.0, 20.0, 4.0))
    arm.apply_translation((44.0, 0.0, 36.0))
    with_arm = trimesh.boolean.union([tunnel_block().raw, arm])
    block = trimesh.creation.box(extents=(30.0, 30.0, 10.0))
    block.apply_translation((0.0, 0.0, 5.0))
    objects = [
        replace(scene_object("obj_1", "Tunnel"), mesh=MeshData.of(with_arm)),
        replace(scene_object("obj_2", "Klotz"), mesh=MeshData.of(block)),
    ]
    settings = print_settings.resolve(profile, "standard")
    settings = print_settings.with_accepted(settings, "support.style", "auto")
    settings = print_settings.with_accepted(settings, "support.block_channels", True)

    written, findings = write_assembly(
        objects, tmp_path, project_name="t", profile=profile, settings=settings, flavour=flavour
    )

    blocked = [
        finding.object_id for finding in findings if finding.code == "export.support_blocker"
    ]
    assert blocked == ["obj_1"]
    said = [
        finding.values["setting"] for finding in findings if finding.code == "export.part_setting"
    ]
    assert said == ["support.style"], "die Sperre nennt sich selbst"
    if flavour == "orca":
        assert _orca_parts(written) == [("2", "normal_part"), ("2", "support_blocker")]
    else:
        meshes = [(mesh.path.name, dict(mesh.settings)) for mesh in handover.cura_meshes(written)]
        assert meshes == [
            ("t-part-1.stl", {"support_enable": "true"}),
            ("t-blocker-1.stl", {"anti_overhang_mesh": "true"}),
            ("t-part-2.stl", {"support_enable": "false"}),
        ]


def test_the_simplified_blocker_still_covers_the_whole_channel(profile: Profile) -> None:
    """Die Kanalscheiben werden vor dem Sperrkörper um
    ``writer.BLOCKER_SIMPLIFY`` vereinfacht — am Eiffelturm aus dem Korpus
    404 464 statt 177 454 Dreiecke, 12,6 statt 1,4 s. Der Zuschlag
    ``BLOCKER_MARGIN`` schiebt den Umriss danach nach außen; vom freien
    Kanalraum darf deshalb nichts außerhalb der Sperre liegen."""
    import manifold3d
    import numpy as np

    from app.core.export import writer
    from app.core.knowledge import profiles as profile_table
    from app.core.slice.analysis import channel_space, model_support, slice_body

    # Eine geschlossene runde Kammer Ø 20: Am Kreis ändert Vereinfachen den
    # Umriss, an einem quer liegenden Tunnel nicht — dessen Scheiben sind
    # Rechtecke, und dort wäre jede Toleranz grün (gegengeprüft mit 3 mm).
    block = trimesh.creation.box(extents=(40.0, 40.0, 40.0))
    block.apply_translation((0.0, 0.0, 20.0))
    chamber = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=96)
    chamber.apply_translation((0.0, 0.0, 18.0))
    entry = scene_object(mesh=MeshData.of(trimesh.boolean.difference([block, chamber])))
    mesh = as_mesh_data(entry.mesh)
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "grid")
    blocker, _found = writer._support_blocker(entry, mesh, settings, profile)
    assert blocker is not None

    wall, angle = profile_table.analysis_limits(profile, entry)
    result = slice_body(
        mesh,
        settings.layers.layer_height,
        first_layer_height=settings.layers.first_layer_height,
        overhang_angle=angle,
        bridge_from=wall,
        detail="support",
        support_volume=False,
    )
    exact = []
    for bottom, top, region in channel_space(result, model_support(result)):
        rings = [
            ring
            for part in getattr(region, "geoms", [region])
            for ring in (
                np.asarray(part.exterior.coords)[:-1],
                *(np.asarray(hole.coords)[:-1] for hole in part.interiors),
            )
        ]
        section = manifold3d.CrossSection(rings, manifold3d.FillRule.EvenOdd)
        exact.append(manifold3d.Manifold.extrude(section, top - bottom).translate((0, 0, bottom)))
    free = manifold3d.Manifold.batch_boolean(exact, manifold3d.OpType.Add)
    raw = blocker.raw
    shield = manifold3d.Manifold(
        manifold3d.Mesh(
            vert_properties=np.asarray(raw.vertices, dtype=np.float32),
            tri_verts=np.asarray(raw.faces, dtype=np.uint32),
        )
    )

    assert free.volume() > 0.0
    assert (free - shield).volume() < 1e-6 * free.volume(), "nichts vom Kanal liegt außerhalb"


def test_the_blocker_takes_the_reports_layers(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DRUCK-14: Hat der Prüfbericht das Netz geschnitten, schneidet die Sperre nicht.

    Seine Überhänge und Inseln sind dieselben wie bei ``detail="support"``;
    also ist auch die Sperre dieselbe. Am Eiffelturm aus dem Korpus kostete
    der zweite Schnitt vor dem Start des Slicers den größten Teil von 17 s.
    """
    from app.core.export import writer
    from app.core.knowledge import profiles as profile_table
    from app.core.slice import analysis
    from app.core.slice.findings import analysed

    block = trimesh.creation.box(extents=(40.0, 40.0, 40.0))
    block.apply_translation((0.0, 0.0, 20.0))
    tunnel = trimesh.creation.box(extents=(12.0, 50.0, 14.0))
    tunnel.apply_translation((0.0, 0.0, 16.0))
    entry = scene_object(mesh=MeshData.of(trimesh.boolean.difference([block, tunnel])))
    mesh = as_mesh_data(entry.mesh)
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "grid")
    fresh, _found = writer._support_blocker(entry, MeshData.of(mesh.raw.copy()), settings, profile)
    assert fresh is not None

    wall, angle = profile_table.analysis_limits(profile, entry)
    analysed(mesh, settings, angle, wall)

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("die Schichten des Prüfberichts genügen")

    monkeypatch.setattr(analysis, "slice_body", refuse)
    reused, _found = writer._support_blocker(entry, mesh, settings, profile)

    assert reused is not None
    assert reused.raw.volume == pytest.approx(fresh.raw.volume, rel=1e-9)
    assert reused.triangle_count == fresh.triangle_count


def test_the_blocker_cuts_with_the_threshold_that_goes_out(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Entscheidung L: Die Sperre schneidet mit der Stützschwelle der
    Einstellungen, die hinausgehen — auf einem Herstellerprozess dessen
    Schwelle, nicht die des Druckers in Solidons Tabelle (am Centauri 60°).
    Sonst sperrte sie nach einer Grenze, nach der der Slicer nicht stützt."""
    from app.core.export import writer
    from app.core.slice import analysis

    class SeenError(Exception):
        pass

    angles: list[float] = []

    def capture(*_args: object, **kwargs: float) -> None:
        angles.append(kwargs["overhang_angle"])
        raise SeenError

    block = trimesh.creation.box(extents=(30.0, 30.0, 30.0))
    block.apply_translation((0.0, 0.0, 15.0))
    entry = scene_object(mesh=MeshData.of(block))
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "grid")
    printed = print_settings.with_path(settings, "support.threshold_angle", 41.0)
    monkeypatch.setattr(analysis, "slice_body", capture)

    with pytest.raises(SeenError):
        writer._support_blocker(entry, as_mesh_data(entry.mesh), printed, profile)

    assert profile.overhang_limit_degrees == pytest.approx(60.0)
    assert angles == [pytest.approx(41.0)]


def test_the_blocker_stops_when_the_customer_cancels(tmp_path: Path, profile: Profile) -> None:
    """Die Sperre rechnet am Eiffelturm aus dem Korpus eine Viertelminute —
    Schnitt, Kanalfrage, Kanalraum — vor dem Start des Slicers. *Abbrechen*
    griff erst danach: ``write_assembly`` kannte keinen Abbruch. Jetzt erreicht
    er den Schnitt, und es entsteht keine Datei."""
    from app.core.errors import OperationCancelled

    class Stopped:
        is_cancelled = True

        def raise_if_cancelled(self) -> None:
            raise OperationCancelled

    entry = scene_object(mesh=tunnel_block())
    taken = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.block_channels",
        True,
    )

    with pytest.raises(OperationCancelled):
        write_assembly(
            [entry],
            tmp_path,
            project_name="t",
            profile=profile,
            settings=taken,
            cancelled=Stopped(),
        )
    assert not list(tmp_path.glob("*.3mf")), "keine halbe Übergabe"


def test_a_saved_file_carries_no_blocker(tmp_path: Path, profile: Profile) -> None:
    """Eine gespeicherte 3MF ist das Projekt des Kunden und keine Übergabe:
    Sie trägt keine Sperre, die ein anderes Programm als Material lesen
    könnte."""
    entry = scene_object(mesh=tunnel_block())
    taken = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.block_channels",
        True,
    )

    saved, _saved_findings = write_assembly(
        [entry],
        tmp_path / "datei",
        project_name="t",
        profile=profile,
        settings=taken,
        for_slicer=False,
    )
    assert [kind for kind, _first, _last in _blocker_ranges(saved)] == ["ModelPart"]


def test_cura_gets_every_part_and_the_blocker_as_meshes_of_their_own(
    tmp_path: Path, profile: Profile
) -> None:
    """Die Stützsperre reist zu CuraEngine als eigenes Netz (Prüfbericht Cura, B10).

    Bis zum 27.09.2026 bekam Cura alle Teile als ein STL, und die Sperre fiel
    weg — am Minigolf-Körper im Prüfbericht gemessen: mit der Sperre als
    eigenem Netz und ``anti_overhang_mesh`` 18 476 Stützbewegungen weniger,
    die Modellbahn gleich. Curas Fenster bekommt dieselben Netze als 3MF
    (:func:`test_curas_window_gets_the_blocker_and_the_values_of_each_part`),
    der Befund ist deshalb derselbe wie bei jedem Slicer.
    """
    entry = scene_object(mesh=tunnel_block())
    second = scene_object("obj_2", "Zweites")
    second = replace(second, mesh=apply(second.mesh, translation((60.0, 0.0, 0.0))))
    taken = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.block_channels",
        True,
    )

    stl, findings = write_assembly(
        [entry, second], tmp_path, project_name="t", profile=profile, settings=taken, flavour="cura"
    )

    assert stl.suffix == ".stl", "das Fenster bekommt weiter ein STL mit allen Teilen"
    meshes = handover.cura_meshes(stl)
    assert [mesh.path.name for mesh in meshes] == [
        "t-part-1.stl",
        "t-blocker-1.stl",
        "t-part-2.stl",
    ]
    assert [dict(mesh.settings) for mesh in meshes] == [{}, {"anti_overhang_mesh": "true"}, {}]
    part = read_mesh(meshes[0].path.read_bytes(), ".stl")
    assert part.volume == pytest.approx(as_mesh_data(entry.mesh).raw.volume, rel=1e-6)
    blocker = read_mesh(meshes[1].path.read_bytes(), ".stl")
    assert blocker.volume > 0.0
    [said] = [finding for finding in findings if finding.code == "export.support_blocker"]
    assert "Cura-Fenster" not in str(said.message), "das Fenster bekommt die Sperre selbst"


def _ledge_tunnel() -> MeshData:
    """Der Tunnelblock mit einem Kragarm oben, 30 mm frei: Er braucht Stützen,
    und die Tunneldecke trägt sich selbst — Stützen an und Kanal gesperrt."""
    ledge = trimesh.creation.box(extents=(30.0, 40.0, 3.0))
    ledge.apply_translation((44.0, 0.0, 38.5))
    return MeshData.of(trimesh.boolean.union([tunnel_block().raw, ledge]))


def test_curas_window_gets_the_blocker_and_the_values_of_each_part(
    tmp_path: Path, profile: Profile
) -> None:
    """Curas Fenster bekommt, was die Kommandozeile bekommt (RM-257): je Teil
    ein Objekt mit seinen Werten, die Sperre als Netz mit ``anti_overhang_mesh``
    — als 3MF in Curas Schreibweise statt des zusammengelegten STL, das weder
    Sperre noch Werte je Teil trug.

    Die Sperre steht als Komponente neben ihrem Körper in einem Objekt: Cura
    setzt ein freistehendes Objekt aufs Bett, ein Kind einer Gruppe wandert
    mit ihr. Verschoben um den halben Bauraum, denn Cura misst eine 3MF von
    der Bettecke und ordnet sie beim Laden nicht an.
    """
    taken = print_settings.with_accepted(
        print_settings.with_accepted(print_settings.resolve(profile), "support.style", "grid"),
        "support.block_channels",
        True,
    )
    objects = [
        scene_object("obj_1", "Tunnel", mesh=_ledge_tunnel()),
        replace(
            scene_object("obj_2", "Klotz"),
            mesh=apply(scene_object().mesh, translation((70.0, 0.0, 0.0))),
        ),
    ]

    console, _console_findings = write_assembly(
        objects,
        tmp_path / "konsole",
        project_name="t",
        profile=profile,
        settings=taken,
        flavour="cura",
    )
    window, findings = write_assembly(
        objects,
        tmp_path / "fenster",
        project_name="t",
        profile=profile,
        settings=taken,
        flavour="cura",
        for_window=True,
    )

    assert window.suffix == ".3mf"
    archive = zipfile.ZipFile(window)
    assert sorted(archive.namelist()) == ["3D/3dmodel.model", "[Content_Types].xml", "_rels/.rels"]
    model = ET.fromstring(archive.read("3D/3dmodel.model"))
    core = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
    objects_by_id = {node.get("id"): node for node in model.iter(f"{core}object")}

    def values(node: ET.Element) -> dict[str, str]:
        return {
            meta.get("name", ""): meta.text or ""
            for meta in node.iter(f"{core}metadata")
            if meta.get("name", "").startswith("cura:")
        }

    items = list(model.iter(f"{core}item"))
    width, depth, _height = profile.printer.build_volume
    assert {item.get("transform") for item in items} == {
        f"1 0 0 0 1 0 0 0 1 {width / 2:g} {depth / 2:g} 0"
    }
    tunnel, block = (objects_by_id[item.get("objectid")] for item in items)
    body, shield = (
        objects_by_id[component.get("objectid")] for component in tunnel.iter(f"{core}component")
    )
    assert values(body) == {"cura:support_enable": "True"}
    assert values(shield) == {"cura:anti_overhang_mesh": "True"}
    assert values(block) == {"cura:support_enable": "False"}
    assert [dict(mesh.settings) for mesh in handover.cura_meshes(console)] == [
        {"support_enable": "true"},
        {"anti_overhang_mesh": "true"},
        {"support_enable": "false"},
    ], "dieselben Werte wie in der Kommandozeile, dort in ihrer Schreibweise"
    assert "export.support_blocker" in {finding.code for finding in findings}


def test_curas_window_centres_the_job_on_the_bed_cura_has_active(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Curas Leser zieht beim Öffnen die halbe Bettgröße *seiner* aktiven
    Maschine ab (``ThreeMFReader._read``, Cura 5.13) und ordnet nicht an.

    Auf das Bett des Druckers in Solidon gerechnet, lag ein Auftrag an einer
    anderen Maschine um die halbe Differenz aus der Mitte: am Ender-3 V3 SE
    (220 mm) mit dem Centauri Carbon 2 (256 mm) um 18 mm nach hinten rechts
    (B5, Durchsicht 0.5.1) — ein Auftrag, der auf Curas Bett passte, konnte so
    über dessen Rand ragen.
    """
    from app.core.export import slicer_profiles

    monkeypatch.setattr(
        slicer_profiles,
        "cura_active_machine",
        lambda _executable: slicer_profiles.CuraActiveMachine(
            name="Ender-3 V3 SE",
            definition=Path("creality_ender3v3se.def.json"),
            bed=(220.0, 200.0),
        ),
    )
    assert profile.printer.build_volume[:2] != (220.0, 200.0), "sonst prüft der Test nichts"

    window, _findings = write_assembly(
        [scene_object("obj_1", "Klotz")],
        tmp_path,
        project_name="t",
        profile=profile,
        settings=print_settings.resolve(profile),
        flavour="cura",
        setup=handover.SlicerSetup(executable=Path("CuraEngine.exe"), flavour="cura"),
        for_window=True,
    )

    model = ET.fromstring(zipfile.ZipFile(window).read("3D/3dmodel.model"))
    core = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
    assert [item.get("transform") for item in model.iter(f"{core}item")] == [
        "1 0 0 0 1 0 0 0 1 110 100 0"
    ]


def test_cura_gets_parts_without_a_blocker_when_none_is_taken(
    tmp_path: Path, profile: Profile
) -> None:
    """Ohne übernommene Sperre: je Teil ein Netz, keines mit Werten."""
    stl, findings = write_assembly(
        [scene_object(mesh=tunnel_block())],
        tmp_path,
        project_name="t",
        profile=profile,
        settings=print_settings.resolve(profile),
        flavour="cura",
    )

    assert [(mesh.path.name, dict(mesh.settings)) for mesh in handover.cura_meshes(stl)] == [
        ("t-part-1.stl", {})
    ]
    assert "export.support_blocker" not in {finding.code for finding in findings}
