"""Befunde aus der Durchsicht von ``ingest/`` und ``export/`` (§17.1, §20, §29).

Jeder Test hier stand vor seinem Fix einmal rot. Sie liegen zusammen, weil sie
denselben Weg betreffen — was in eine Datei hineingeht und was wieder
herauskommt —, und getrennt von ``test_export.py``, damit die Reproduktion
neben dem Befund lesbar bleibt.
"""

from __future__ import annotations

import json
import re
import struct
import zipfile
from io import BytesIO

import pytest
import trimesh

from app.core.export import threemf
from app.core.export.writer import GLB_METRES_PER_MM, check_filament_changes, export_bytes
from app.core.geom.mesh import MeshData
from app.core.ingest import threemf as threemf_reader
from app.core.knowledge import print_settings, profiles
from app.core.types import MaterialSlot, PrintSettings, SceneObject

# --- GLB geht Y-oben hinaus ----------------------------------------------------


def _gltf_document(payload: bytes) -> dict[str, object]:
    """Der JSON-Teil einer GLB — der Kasten, in dem die Maße stehen."""
    _magic, _version, length = struct.unpack("<III", payload[:12])
    offset = 12
    while offset < length:
        size, kind = struct.unpack("<II", payload[offset : offset + 8])
        if kind == 0x4E4F534A:  # "JSON"
            return dict(json.loads(payload[offset + 8 : offset + 8 + size].decode("utf-8")))
        offset += 8 + size
    raise AssertionError("die GLB hat keinen JSON-Block")


def _extents_in(payload: bytes) -> tuple[float, float, float]:
    """Die Kantenmaße, wie ein fremder Betrachter sie aus der Datei liest.

    Über die Accessor-Grenzen, nicht über einen zweiten Leser: Genau diese
    Zahlen nimmt ein Betrachter, und sie sagen unabhängig von jeder Bibliothek,
    in welche Richtung das Teil steht.
    """
    document = _gltf_document(payload)
    accessors = [entry for entry in document["accessors"] if entry.get("type") == "VEC3"]  # type: ignore[union-attr]
    assert accessors, "die GLB nennt keine Punktgrenzen"
    lowest = [min(entry["min"][axis] for entry in accessors) for axis in range(3)]
    highest = [max(entry["max"][axis] for entry in accessors) for axis in range(3)]
    return (
        highest[0] - lowest[0],
        highest[1] - lowest[1],
        highest[2] - lowest[2],
    )


def _slab() -> MeshData:
    """Ein Quader, dessen drei Kanten sich nicht verwechseln lassen."""
    return MeshData.of(trimesh.creation.box(extents=(10.0, 20.0, 40.0)))


def _metres(*millimetres: float) -> tuple[float, ...]:
    """glTF kennt genau eine Einheit, und Solidon schreibt sie seit dem 05.09.2026
    auch (Gesamtreview, CORE-33): Was hier in Millimetern gebaut wird, steht in
    der Datei in Metern."""
    return tuple(value * GLB_METRES_PER_MM for value in millimetres)


def test_a_glb_stands_upright_for_the_viewer_that_receives_it() -> None:
    """Der glTF-2.0-Standard schreibt in Abschnitt 3.5 +Y oben vor, Solidon
    rechnet Z-oben.

    ``trimesh`` dreht beim Schreiben nichts und legt auch keine Knotenmatrix an
    — die Höhe stand damit auf der Z-Achse der Datei, und jeder konforme
    Betrachter (Windows-3D-Viewer, three.js, Blender) zeigte das Teil um 90°
    gekippt.
    """
    written = _extents_in(export_bytes(_slab(), "glb"))

    assert written == pytest.approx(_metres(10.0, 40.0, 20.0)), "die Höhe gehört auf die Y-Achse"


def test_the_slot_meshes_of_a_glb_turn_together() -> None:
    """Zweifarbig wird je Slot ein Teilnetz — und alle stehen gleich.

    Ein Netz, das die Drehung nicht mitmacht, steckte quer im anderen; sichtbar
    wäre es erst beim Empfänger.
    """
    plain = _slab()
    two_tone = MeshData(raw=plain.raw, slots=tuple(0 if index < 6 else 1 for index in range(12)))
    slots = [
        MaterialSlot(index=0, name="Grundkörper", colour=(1.0, 0.0, 0.0)),
        MaterialSlot(index=1, name="Schrift", colour=(0.0, 0.0, 1.0)),
    ]

    written = _extents_in(export_bytes(two_tone, "glb", slots=slots, name="Schild"))

    assert written == pytest.approx(_metres(10.0, 40.0, 20.0))


# --- die Extrudernummer des Auftrags -------------------------------------------


def _part(name: str, slots: tuple[MaterialSlot, ...], plate: int = 0) -> threemf.AssemblyPart:
    body = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    return threemf.AssemblyPart(mesh=body, name=name, slots=slots, plate=plate)


RED = MaterialSlot(index=0, name="Rot", colour=(1.0, 0.0, 0.0))
WHITE = MaterialSlot(index=1, name="Weiß", colour=(1.0, 1.0, 1.0))


def test_a_plate_without_the_first_job_colour_keeps_the_job_extruder() -> None:
    """§20: Die Extruderbelegung gehört dem Auftrag, nicht der Platte.

    ``merge_slots(across=…)`` rechnet die Nummer richtig; geschrieben wurde
    danach die *Position* in der gefilterten Liste. Lässt eine Platte die
    frühere Farbe des Auftrags weg, rutscht die spätere auf Extruder 0 — wer
    den Auftrag am Stück druckt, müsste mittendrin umstecken.
    """
    # Das einfarbige Teil führt seinen Slot als **objekteigene** Null — so
    # entsteht er in der Szene. Die Auftragsnummer vergibt erst ``merge_slots``.
    weiss_allein = MaterialSlot(index=0, name="Weiß", colour=(1.0, 1.0, 1.0))
    job = [_part("Zweifarbig", (RED, WHITE), plate=0), _part("Weiß", (weiss_allein,), plate=1)]

    payload = threemf.write_assembly([job[1]], "Auftrag", across=job)

    model = zipfile.ZipFile(BytesIO(payload)).read(threemf.MODEL_PATH).decode("utf-8")
    assert sorted(set(re.findall(r'p1="(\d+)"', model))) == ["1"], "Weiß ist Extruder 1"
    names = re.findall(r'<base name="([^"]*)"', model)
    assert len(names) == 2, "der freie Platz von Rot bleibt in der Liste stehen"
    assert names[1] == "Weiß"


def test_a_plate_with_the_whole_job_is_unchanged() -> None:
    """Die Gegenprobe: Ohne Lücke ändert sich nichts an der Datei."""
    job = [_part("Zweifarbig", (RED, WHITE))]

    payload = threemf.write_assembly(job, "Auftrag", across=job)

    model = zipfile.ZipFile(BytesIO(payload)).read(threemf.MODEL_PATH).decode("utf-8")
    assert re.findall(r'<base name="([^"]*)"', model) == ["Rot", "Weiß"]


def test_the_settings_of_a_plate_stand_at_their_extruder_position() -> None:
    """Dieselbe Lücke in der Beilage (§29).

    Die Orca-Familie liest Filamentwerte als Liste in Extruderreihenfolge.
    Stünde die Farbe der zweiten Spule dort an erster Stelle, widerspräche die
    Beilage der Geometrie derselben Datei.
    """
    from pathlib import Path

    from app.core.export import handover

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    written = handover.project_settings(settings, profile, setup, slots=[WHITE])

    colours = written.get("filament_colour")
    assert isinstance(colours, list)
    assert colours[1] == "#FFFFFF", "Weiß gehört an Position 1"


# --- ein Körper ohne Dreiecke ---------------------------------------------------


def _mesh_xml(body: trimesh.Trimesh) -> str:
    points = "".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in body.vertices)
    faces = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in body.faces)
    return f"<mesh><vertices>{points}</vertices><triangles>{faces}</triangles></mesh>"


def _assembly_with_an_empty_body() -> bytes:
    """Zwei Build-Items, das zweite ohne ein einziges Dreieck."""
    body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    root = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<model unit="millimeter" xmlns="{threemf.CORE_NAMESPACE}">'
        "<resources>"
        f'<object id="1" type="model" name="Voll">{_mesh_xml(body)}</object>'
        '<object id="2" type="model" name="Leer">'
        "<mesh><vertices/><triangles/></mesh></object>"
        "</resources>"
        '<build><item objectid="1"/><item objectid="2"/></build></model>'
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr(threemf.MODEL_PATH, root)
    return buffer.getvalue()


def test_a_body_without_triangles_is_not_counted_as_one() -> None:
    """§11: Der Stapel vergibt die Objekt-IDs, bevor es Geometrie gibt.

    Der Scan zählte jedes ``mesh``-Element, der Leser überspringt eines ohne
    Dreiecke — zwei versprochen, einer geliefert. Die Auswertung hielt daraufhin
    mit ``evaluate.object_count`` an, und aus einer Datei mit einem lesbaren
    Körper wurde ein Import, der gar nichts einlas.
    """
    payload = _assembly_with_an_empty_body()

    assert threemf_reader.count_objects(payload) == len(threemf_reader.read_objects(payload)) == 1


def test_the_triangle_count_still_covers_the_whole_file() -> None:
    """Der leere Körper ändert nichts an der Größengrenze (§32)."""
    payload = _assembly_with_an_empty_body()

    assert threemf_reader.scan_assembly(payload) == (1, 12)


# --- ein schwebendes Teil wechselt keine Spule ----------------------------------


def _object_at(name: str, height: float, slot: str) -> SceneObject:
    body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    body.apply_translation((0.0, 0.0, height + 5.0))
    return SceneObject(
        id=name,
        name=name,
        mesh=MeshData.of(body),
        material_slots=[MaterialSlot(index=0, name=slot)],
    )


def test_a_part_that_starts_higher_up_shares_no_layer_below_it() -> None:
    """§29: Ein Wechsel kostet nur, wo zwei Filamente wirklich übereinander
    liegen.

    Gezählt wurde allein gegen die Oberkante: Ein Teil, das erst bei 30 mm
    beginnt, galt damit schon in der ersten Schicht als vorhanden — die Meldung
    nannte Wechsel für Schichten, in denen es das zweite Filament noch gar
    nicht gibt.
    """
    settings: PrintSettings = print_settings.resolve(profiles.make_profile())
    unten = _object_at("unten", 0.0, "Rot")
    oben = _object_at("oben", 30.0, "Weiß")

    findings = check_filament_changes([unten, oben], settings, plate=0)

    assert findings == [], "die beiden stehen übereinander, nicht nebeneinander"
