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
