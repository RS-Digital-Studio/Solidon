"""Eine 3MF als die Baugruppe lesen, die sie ist (§17.1, §29, §40).

Ein Slicer hält seine Objekte in getrennten Dateien unter ``3D/Objects/`` und
verweist aus dem Build darauf. Zwei Dinge gingen damit schief, bevor es diesen
Leser gab, und beide werden hier festgehalten: eine Komponente wurde zur ganzen
Datei aufgelöst, in die sie zeigt, statt zu dem einen Objekt, das sie benennt —
und die Teile wurden auf dem Weg hinein zu einem einzigen Körper verschweißt.

Die Container werden im Test gebaut statt als Fixtures gehalten, damit die
Struktur, auf die es ankommt, in der Datei sichtbar ist, die sie prüft.
"""

from __future__ import annotations

import re
import zipfile
from io import BytesIO

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.export import threemf
from app.core.geom.mesh import MeshData

CORE = threemf.CORE_NAMESPACE
PRODUCTION = threemf.PRODUCTION_NAMESPACE


def mesh_xml(body: trimesh.Trimesh) -> str:
    points = "".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in body.vertices)
    faces = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in body.faces)
    return f"<mesh><vertices>{points}</vertices><triangles>{faces}</triangles></mesh>"


def objects_file(bodies: dict[str, trimesh.Trimesh]) -> str:
    entries = "".join(
        f'<object id="{identifier}" type="model">{mesh_xml(body)}</object>'
        for identifier, body in bodies.items()
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<model unit="millimeter" xmlns="{CORE}" xmlns:p="{PRODUCTION}">'
        f"<resources>{entries}</resources><build/></model>"
    )


def production_container(
    bodies: dict[str, trimesh.Trimesh],
    *,
    one_file: bool = True,
    names: dict[str, str] | None = None,
    transforms: dict[str, str] | None = None,
    missing: str | None = None,
) -> bytes:
    """Eine 3MF, wie ein Slicer sie schreibt: Geometrie außen, Komponenten
    innen.

    ``one_file`` legt jedes Objekt in ein einziges externes Modell — der Fall,
    der früher vervielfachte, weil eine Komponente zur Datei aufgelöst wurde
    statt zu dem Objekt, das sie benennt.
    """
    if one_file:
        externals = {"3D/Objects/parts.model": objects_file(bodies)}
        where = dict.fromkeys(bodies, "3D/Objects/parts.model")
    else:
        externals = {
            f"3D/Objects/part_{identifier}.model": objects_file({identifier: body})
            for identifier, body in bodies.items()
        }
        where = {identifier: f"3D/Objects/part_{identifier}.model" for identifier in bodies}

    wrappers = "".join(
        f'<object id="1{identifier}" type="model"><components>'
        f'<component objectid="{"999" if missing == identifier else identifier}"'
        f' p:path="/{where[identifier]}"/>'
        f"</components></object>"
        for identifier in bodies
    )
    items = "".join(
        f'<item objectid="1{identifier}"'
        + (
            f' transform="{(transforms or {})[identifier]}"'
            if identifier in (transforms or {})
            else ""
        )
        + "/>"
        for identifier in bodies
    )
    root = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<model unit="millimeter" xmlns="{CORE}" xmlns:p="{PRODUCTION}">'
        f"<resources>{wrappers}</resources><build>{items}</build></model>"
    )

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr(threemf.MODEL_PATH, root)
        for path, text in externals.items():
            container.writestr(path, text)
        if names:
            parts = "".join(
                f'<object id="1{identifier}"><metadata key="name" value="{title}"/>'
                f'<part id="{identifier}"><metadata key="name" value="{title}"/></part>'
                f"</object>"
                for identifier, title in names.items()
            )
            container.writestr(
                threemf.SETTINGS_PATH, f'<?xml version="1.0"?><config>{parts}</config>'
            )
    return buffer.getvalue()


def cube(size: float, at: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> trimesh.Trimesh:
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_translation(at)
    return body


# --- die Vervielfältigung -------------------------------------------------------


def test_three_objects_in_one_file_come_back_three_times_not_nine() -> None:
    """Der Fehler: jede Komponente löste sich zur ganzen Datei auf, in die sie
    zeigt.

    Am Korpus vor der Behebung gemessen — eine Düse aus zwei Körpern und
    290 120 Dreiecken kam als vier Körper und 580 240 an, mit doppeltem
    Volumen.
    """
    payload = production_container(
        {"1": cube(10.0), "2": cube(20.0, (40.0, 0.0, 0.0)), "3": cube(30.0, (0.0, 40.0, 0.0))}
    )

    parts = threemf.read_objects(payload)

    assert len(parts) == 3
    volumes = sorted(round(part.mesh.volume) for part in parts)
    assert volumes == [1000, 8000, 27000], "each body once, at its own size"


def test_one_file_per_object_reads_the_same_way() -> None:
    """Das andere Layout, das ein Slicer schreibt. Dieselbe Antwort, oder der
    Leser rät.
    """
    bodies = {"1": cube(10.0), "2": cube(20.0, (40.0, 0.0, 0.0))}

    single = threemf.read_objects(production_container(bodies, one_file=True))
    split = threemf.read_objects(production_container(bodies, one_file=False))

    assert [round(part.mesh.volume) for part in single] == [
        round(part.mesh.volume) for part in split
    ]


def test_the_count_matches_what_is_read() -> None:
    """Der Stapel fragt nach der Anzahl, bevor es die Geometrie gibt (§11)."""
    payload = production_container({"1": cube(10.0), "2": cube(20.0), "3": cube(30.0)})

    assert threemf.count_objects(payload) == len(threemf.read_objects(payload)) == 3


# --- die Transformationen -------------------------------------------------------


def test_a_body_arrives_where_the_build_put_it() -> None:
    """Ohne die Transformation sitzen die Teile einer Baugruppe alle im
    Ursprung.
    """
    payload = production_container(
        {"1": cube(10.0)}, transforms={"1": "1 0 0 0 1 0 0 0 1 100 50 25"}
    )

    parts = threemf.read_objects(payload)

    assert len(parts) == 1
    centre = parts[0].mesh.bounds.centre
    assert centre[0] == pytest.approx(100.0)
    assert centre[1] == pytest.approx(50.0)
    assert centre[2] == pytest.approx(25.0)


def test_a_rotation_in_the_transform_is_applied() -> None:
    """Eine 3MF-Matrix ist spaltenweise; zeilenweise gelesen kommt eine
    Drehung gespiegelt heraus.
    """
    plate = trimesh.creation.box(extents=(30.0, 10.0, 4.0))
    # Neunzig Grad um Z: die lange Seite muss entlang Y landen.
    payload = production_container({"1": plate}, transforms={"1": "0 1 0 -1 0 0 0 0 1 0 0 0"})

    size = threemf.read_objects(payload)[0].mesh.bounds.size

    assert size[0] == pytest.approx(10.0)
    assert size[1] == pytest.approx(30.0)


# --- die Namen ------------------------------------------------------------------


def test_the_parts_are_called_what_the_slicer_called_them() -> None:
    """Der Standard lässt ``name`` leer; der Slicer schreibt ihn neben das
    Modell.
    """
    payload = production_container(
        {"1": cube(10.0), "2": cube(20.0)},
        names={"1": "Wasserfall_1_Koerper.stl", "2": "Wasserfall_2_Deckel.stl"},
    )

    parts = threemf.read_objects(payload)

    assert [part.name for part in parts] == ["Wasserfall_1_Koerper", "Wasserfall_2_Deckel"]


def test_bodies_with_the_same_name_are_told_apart() -> None:
    payload = production_container(
        {"1": cube(10.0), "2": cube(20.0)}, names={"1": "Halter", "2": "Halter"}
    )

    assert [part.name for part in threemf.read_objects(payload)] == ["Halter 1", "Halter 2"]


def test_a_file_without_names_still_names_its_bodies() -> None:
    parts = threemf.read_objects(production_container({"1": cube(10.0)}))

    assert parts[0].name, "an object without a name is not an object without a name"


# --- Was keine lesbare Baugruppe ist --------------------------------------------


def test_something_that_is_not_a_3mf_is_not_read() -> None:
    assert threemf.read_objects(b"not a container") == []
    assert threemf.count_objects(b"not a container") == 0


def zip_with_method(name: str, data: bytes, method: int) -> bytes:
    """Ein Archiv, dessen Eintrag ein Packverfahren nennt, das Python nicht
    auspackt — Deflate64 (9) oder AES (99).

    Geschrieben wird ungepackt; getauscht wird nur die Nummer des Verfahrens,
    im lokalen Kopf und im Verzeichnis. Ein solches Archiv von Hand zu bauen
    ist der einzige Weg: ``zipfile`` **schreibt** diese Verfahren ebenso wenig,
    wie es sie liest.
    """
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as container:
        container.writestr(name, data)
    raw = bytearray(buffer.getvalue())
    zahl = method.to_bytes(2, "little")
    lokal = raw.find(bytes([80, 75, 3, 4]))
    verzeichnis = raw.find(bytes([80, 75, 1, 2]))
    raw[lokal + 8 : lokal + 10] = zahl
    raw[verzeichnis + 10 : verzeichnis + 12] = zahl
    return bytes(raw)


@pytest.mark.parametrize("method", [9, 99])
def test_a_3mf_in_a_packing_we_cannot_open_is_an_answer(method: int) -> None:
    """§32: „nicht auspackbar" ist eine Auskunft, kein Stapelabzug.

    Deflate64 und AES stehen im Verzeichnis wie jedes andere Verfahren — die
    Namensliste kommt, und erst beim Lesen wirft ``zipfile`` ein rohes
    ``NotImplementedError``. Das flog durch jeden Leser hindurch bis in die
    Oberfläche: Ablegen tat sichtbar nichts, und die Quelle blieb als Waise im
    Dokument zurück.

    Die Datei ist dabei nicht kaputt — sie ist anders gepackt, und das ist ein
    anderer Satz und ein anderer Ausweg (Regel 17).
    """
    payload = zip_with_method(threemf.MODEL_PATH, b"<model/>", method)

    for lesen in (threemf.read_objects, threemf.count_objects):
        with pytest.raises(ValidationError) as caught:
            lesen(payload)
        assert caught.value.constraint == "unsupported_compression", lesen.__name__
        assert caught.value.suggestions, "Regel 17"

    with pytest.raises(ValidationError):
        threemf.read(payload, 12)


def test_a_component_pointing_at_nothing_drops_that_body_only() -> None:
    """Ein kaputter Verweis kostet nicht die anderen drei Teile."""
    parts = threemf.read_objects(
        production_container({"1": cube(10.0), "2": cube(20.0)}, missing="2")
    )

    assert len(parts) == 1
    assert round(parts[0].mesh.volume) == 1000


def test_our_own_single_body_export_reads_back_as_one_part() -> None:
    """§29, runde Reise: was dieses Modul schreibt, liest es auch."""
    body = MeshData.of(cube(10.0))

    parts = threemf.read_objects(threemf.write(body, name="Klotz"))

    assert len(parts) == 1
    assert parts[0].mesh.volume == pytest.approx(1000.0)


# --- Schreiben: mehrere Körper als eine Baugruppe (§20, §29) ------------------------


def _part(size: tuple[float, float, float], name: str, *slots: threemf.MaterialSlot):
    body = MeshData.of(trimesh.creation.box(size))
    return threemf.AssemblyPart(mesh=body, name=name, slots=slots)


def test_an_assembly_keeps_every_part() -> None:
    """Eine Datei je Teil und eine Datei mit allen Teilen sind nicht dasselbe:
    der Slicer ordnet nur im zweiten Fall als Ganzes an."""
    payload = threemf.write_assembly(
        [_part((10, 10, 10), "Deckel"), _part((20, 5, 5), "Boden")], "Gehäuse"
    )

    parts = threemf.read_objects(payload)

    assert [entry.name for entry in parts] == ["Deckel", "Boden"]
    assert threemf.count_objects(payload) == 2


def test_the_same_colour_becomes_the_same_extruder() -> None:
    """§20: ein Slot ist ein Filament, kein Objektmerkmal. Ohne Zusammenlegung
    fragte der Slicer nach drei Filamenten für einen einfarbigen Druck."""
    rot = threemf.MaterialSlot(index=0, name="Rot", colour=(1.0, 0.0, 0.0))
    blau = threemf.MaterialSlot(index=1, name="Blau", colour=(0.0, 0.0, 1.0))

    merged = threemf.merge_slots([_part((10, 10, 10), "A", rot, blau), _part((5, 5, 5), "B", rot)])

    assert [entry.name for entry in merged] == ["Rot", "Blau"]
    assert [entry.index for entry in merged] == [0, 1], "der Index ist die Extrudernummer"


def test_a_parts_own_slot_numbers_do_not_leak() -> None:
    """Teil zwei zählt seine Slots ab null wie Teil eins. Ohne Übersetzung in
    die gemeinsame Liste trüge es die Farben von Teil eins."""
    nur_blau = threemf.MaterialSlot(index=0, name="Blau", colour=(0.0, 0.0, 1.0))
    rot = threemf.MaterialSlot(index=0, name="Rot", colour=(1.0, 0.0, 0.0))

    payload = threemf.write_assembly(
        [_part((10, 10, 10), "A", rot), _part((5, 5, 5), "B", nur_blau)]
    )

    text = zipfile.ZipFile(BytesIO(payload)).read(threemf.MODEL_PATH).decode("utf-8")
    assert text.count("<base ") == 2, "zwei Farben, nicht eine und nicht drei"
    assert "Rot" in text and "Blau" in text


def test_a_two_colour_assembly_comes_back_in_its_colours() -> None:
    """§20, die runde Reise: schreiben, lesen, dieselben Slots.

    Jedes Teil hier ist einfarbig, und die Farben sind zwei — die gemeinsame
    Materialliste *ist* die Extruderbelegung. Zurückgelesen war trotzdem jedes
    Teil ohne Farbe: ``_groups_of`` hielt „ein Slot" für „keine Gruppe", auch
    wenn der Slot nicht der erste war. Eine Datei, die dieses Modul selbst
    geschrieben hatte, verlor damit genau das, wofür es geschrieben wurde.
    """
    rot = threemf.MaterialSlot(index=0, name="Rot", colour=(1.0, 0.0, 0.0))
    blau = threemf.MaterialSlot(index=0, name="Blau", colour=(0.0, 0.0, 1.0))

    payload = threemf.write_assembly(
        [_part((10, 10, 10), "Platte", rot), _part((5, 5, 5), "Schrift", blau)]
    )
    zurueck = threemf.read_objects(payload)

    assert [entry.name for entry in zurueck] == ["Platte", "Schrift"]
    assert [slot.name for slot in zurueck[0].slots] == ["Rot"]
    assert [slot.name for slot in zurueck[1].slots] == ["Blau"]
    assert zurueck[0].slots[0].colour == pytest.approx((1.0, 0.0, 0.0), abs=1.0 / 255.0)
    assert zurueck[1].slots[0].colour == pytest.approx((0.0, 0.0, 1.0), abs=1.0 / 255.0)
    for entry in zurueck:
        assert set(entry.mesh.slots) == {0}, "je Teil ein Slot, und jedes Dreieck darauf"


def test_a_body_in_two_colours_keeps_both_of_them() -> None:
    """Der Fall, der schon ging, und er muss weiter gehen: zwei Slots in einem
    Netz, in der Reihenfolge der Dreiecke."""
    rot = threemf.MaterialSlot(index=0, name="Rot", colour=(1.0, 0.0, 0.0))
    blau = threemf.MaterialSlot(index=1, name="Blau", colour=(0.0, 0.0, 1.0))
    body = trimesh.creation.box((10, 10, 10))
    zweifarbig = MeshData(raw=body, slots=(0,) * 6 + (1,) * 6)

    payload = threemf.write_assembly(
        [threemf.AssemblyPart(mesh=zweifarbig, name="Schild", slots=(rot, blau))]
    )
    zurueck = threemf.read_objects(payload)

    assert [slot.name for slot in zurueck[0].slots] == ["Rot", "Blau"]
    assert zurueck[0].mesh.slots == (0,) * 6 + (1,) * 6


def coloured_container(
    faces: list[str], bases: str, *, on_object: str = 'pid="1" pindex="0"'
) -> bytes:
    """Eine 3MF von Hand: eine Materialgruppe und ein Tetraeder, dessen
    Dreiecke tragen, was der Test ihnen mitgibt.
    """
    points = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 0.0, 10.0))
    corners = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))
    vertices = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in points)
    triangles = "".join(
        f'<triangle v1="{a}" v2="{b}" v3="{c}" {extra}/>'
        for (a, b, c), extra in zip(corners, faces, strict=True)
    )
    root = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<model unit="millimeter" xmlns="{CORE}">'
        f'<resources><basematerials id="1">{bases}</basematerials>'
        f'<object id="2" type="model" {on_object}><mesh>'
        f"<vertices>{vertices}</vertices><triangles>{triangles}</triangles>"
        f"</mesh></object></resources>"
        f'<build><item objectid="2"/></build></model>'
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr(threemf.MODEL_PATH, root)
    return buffer.getvalue()


def test_a_triangle_that_points_past_the_material_list_still_gets_a_slot() -> None:
    """Jeder vergebene Slot hat einen Eintrag.

    Die Liste wurde beim Lesen um alles gekürzt, was über sie hinauszeigte —
    das Netz behielt seine drei Slotnummern, die Materialliste hatte zwei
    Einträge, und Slot 2 zeigte ins Leere. Ein Netz, das auf eine Farbe zeigt,
    die es nicht gibt, ist schlimmer als eine graue Ersatzfarbe mit Namen.
    """
    payload = coloured_container(
        ['pid="1" p1="0"', 'pid="1" p1="1"', 'pid="1" p1="7"', 'pid="1" p1="0"'],
        '<base name="Rot" displaycolor="#FF0000"/><base name="Blau" displaycolor="#0000FF"/>',
    )

    parts = threemf.read_objects(payload)

    assert len(parts[0].slots) == len(set(parts[0].mesh.slots)), "je benutztem Slot ein Eintrag"
    assert [slot.index for slot in parts[0].slots] == [0, 1, 2]
    assert [slot.name for slot in parts[0].slots] == ["Rot", "Blau", "Slot 7"]
    assert max(parts[0].mesh.slots) < len(parts[0].slots)


def test_a_body_that_names_no_material_gets_none() -> None:
    """Regel 21: Was die Datei nicht sagt, wird nicht angenommen.

    Ein Objekt ohne ``pid``, dessen Dreiecke ebenfalls schweigen, gehört zu
    keinem Material — auch wenn die Datei daneben zwei führt. Ihm das erste
    zuzuschreiben wäre geraten, und geraten wird hier nicht.
    """
    payload = coloured_container(
        ["", "", "", ""],
        '<base name="Rot" displaycolor="#FF0000"/><base name="Blau" displaycolor="#0000FF"/>',
        on_object="",
    )

    parts = threemf.read_objects(payload)

    assert parts[0].slots == (), "keine Farbe ist keine Farbe"
    assert parts[0].mesh.slots == ()


def test_a_second_material_group_is_read_as_itself() -> None:
    """Zwei ``basematerials``-Gruppen sind zwei Gruppen.

    Gelesen wurde nur die erste, und was auf die zweite zeigte, fiel still auf
    deren ersten Eintrag: Ein Körper aus zwei Gruppen kam einfarbig zurück.
    """
    points = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 0.0, 10.0))
    corners = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))
    vertices = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in points)
    zuordnung = ('pid="1" p1="0"', 'pid="1" p1="0"', 'pid="3" p1="0"', 'pid="3" p1="0"')
    triangles = "".join(
        f'<triangle v1="{a}" v2="{b}" v3="{c}" {extra}/>'
        for (a, b, c), extra in zip(corners, zuordnung, strict=True)
    )
    root = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<model unit="millimeter" xmlns="{CORE}"><resources>'
        f'<basematerials id="1"><base name="Rot" displaycolor="#FF0000"/></basematerials>'
        f'<basematerials id="3"><base name="Blau" displaycolor="#0000FF"/></basematerials>'
        f'<object id="2" type="model" pid="1" pindex="0"><mesh>'
        f"<vertices>{vertices}</vertices><triangles>{triangles}</triangles>"
        f"</mesh></object></resources>"
        f'<build><item objectid="2"/></build></model>'
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr(threemf.MODEL_PATH, root)

    parts = threemf.read_objects(buffer.getvalue())

    assert [slot.name for slot in parts[0].slots] == ["Rot", "Blau"]
    assert parts[0].mesh.slots == (0, 0, 1, 1)


def test_an_assembly_without_parts_is_refused() -> None:
    with pytest.raises(ValueError):
        threemf.write_assembly([])


def test_a_single_part_assembly_is_just_an_assembly_of_one() -> None:
    """Kein Sonderweg: derselbe Code, ein Eintrag."""
    payload = threemf.write_assembly([_part((10, 10, 10), "Allein")])

    assert threemf.count_objects(payload) == 1


# --- die Platte reist mit (§29) -------------------------------------------------


def test_without_a_bed_the_parts_stay_where_the_model_has_them() -> None:
    """Ohne Bauraumangabe wird nichts platziert — der Slicer ordnet dann an."""
    payload = threemf.write_assembly([_part((10, 10, 10), "A"), _part((10, 10, 10), "B")])

    text = zipfile.ZipFile(BytesIO(payload)).read(threemf.MODEL_PATH).decode("utf-8")
    assert "transform" not in text


def test_with_a_bed_every_part_carries_its_place() -> None:
    """Solidon rechnet um den Nullpunkt, ein Slicer misst von der Ecke.

    Ohne die Umrechnung liegt die ganze Szene außerhalb des Betts, und der
    Slicer ordnet notgedrungen selbst an — womit alles verloren ist, was
    ``arrange_bed`` errechnet hat. Gemessen an zwei Läufen derselben Szene, die
    denselben G-Code ergaben.
    """
    payload = threemf.write_assembly(
        [_part((10, 10, 10), "A"), _part((10, 10, 10), "B")], "Platte", bed=(256.0, 256.0)
    )

    text = zipfile.ZipFile(BytesIO(payload)).read(threemf.MODEL_PATH).decode("utf-8")
    assert text.count('transform="1 0 0 0 1 0 0 0 1 128 128 0"') == 2


def test_the_geometry_itself_stays_untouched() -> None:
    """Verschoben wird über die Matrix, nicht über die Punkte.

    Der Unterschied ist nicht kosmetisch: die Ecken in der Datei bleiben die
    des Dokuments, und wer die Datei als Modell liest, bekommt das Modell. Erst
    wer sie als Platte liest, bekommt die Platte — deshalb steht die
    Verschiebung beim gelesenen Körper, nicht bei den Punkten im XML.
    """
    payload = threemf.write_assembly([_part((10, 10, 10), "A")], bed=(256.0, 256.0))
    text = zipfile.ZipFile(BytesIO(payload)).read(threemf.MODEL_PATH).decode("utf-8")

    coordinates = [float(value) for value in re.findall(r'x="(-?[0-9.]+)"', text)]
    assert max(coordinates) <= 5.0, "die Punkte selbst bleiben, wo das Dokument sie hat"
    assert threemf.read_objects(payload)[0].mesh.bounds.centre[0] == pytest.approx(128.0)


# --- wenn die Zahlen beschädigt zurückkommen ----------------------------------------


def test_damaged_numbers_are_read_a_second_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dieselbe Wunde wie bei ``mesh.on_surface``, an der zweiten Stelle.

    Dieselbe Datei dreißigmal im selben Prozess gelesen, und sporadisch kommt
    ``OverflowError``, ``SystemError`` oder ein ``ValueError`` über eine
    Zeichenkette, die eine gültige Zahl ist. Eingegrenzt: nicht der XML-Leser
    (lxml verhält sich gleich), nicht die Art der Umwandlung — das geladene
    ``rtree``. Ein zweiter Anlauf trägt.
    """
    payload = threemf.write_assembly([_part((10, 10, 10), "A")], bed=(256.0, 256.0))
    echt = threemf._read_numbers
    versuche: list[int] = []

    def erst_beschädigt(vertices: object, triangles: object) -> object:
        versuche.append(1)
        if len(versuche) == 1:
            raise OverflowError("int too big to convert")
        return echt(vertices, triangles)

    monkeypatch.setattr(threemf, "_read_numbers", erst_beschädigt)
    parts = threemf.read_objects(payload)

    assert len(versuche) == 2, "einmal beschädigt, einmal wiederholt"
    assert len(parts) == 1, "und der Körper ist trotzdem da"
    assert parts[0].mesh.triangle_count == 12


def test_numbers_damaged_twice_are_not_silently_dropped(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Wiederholen heißt nicht verschlucken.

    Ein Körper, der zweimal beschädigt zurückkommt, fällt aus der Baugruppe —
    das ist richtig. Wortlos zu verschwinden ist es nicht: siebzehn Teile
    kamen als sechzehn zurück, und keine Zeile sagte warum.
    """
    payload = threemf.write_assembly([_part((10, 10, 10), "A")], bed=(256.0, 256.0))

    def immer_beschädigt(vertices: object, triangles: object) -> object:
        raise ValueError("invalid literal for int() with base 10: '98968'")

    monkeypatch.setattr(threemf, "_read_numbers", immer_beschädigt)
    with caplog.at_level("INFO"):
        parts = threemf.read_objects(payload)

    assert parts == [], "der Körper fällt aus"
    assert any(
        "unreadable" in entry.message or "damaged" in entry.message for entry in caplog.records
    ), "und er sagt es"
