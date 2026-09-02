"""Materialslots: sie durch Operationen tragen und nach 3MF hinausbringen
(§20, §29).

Das Abnahmekriterium von P9 ist kurz und hart: „die Slot-Zuweisung überlebt
Boolesche Operationen einschließlich der Voxelstufe". Beide Hälften werden
geprüft — die leichte, in der der Kern die Dreiecke durchreicht, und die, in
der das Netz vollständig ersetzt wurde und jedes Dreieck fragen muss, woher es
kam.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

import numpy as np
import pytest
import trimesh

from app.core.export import threemf
from app.core.export.writer import export_bytes, plan_export
from app.core.geom.attributes import counts, transfer, used_slots, with_slot
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.geom.mesh_ops import decimate
from app.core.ingest import threemf as threemf_reader
from app.core.types import MaterialSlot, Profile, SceneObject

NAMESPACE = {"c": threemf.CORE_NAMESPACE}


def cube(size: float = 20.0, offset: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> MeshData:
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_translation(offset)
    return MeshData.of(body)


def pin(radius: float = 3.0, height: float = 40.0) -> MeshData:
    return MeshData.of(trimesh.creation.cylinder(radius=radius, height=height))


def area_share(mesh: MeshData, slot: int) -> float:
    """Welcher Anteil der Oberfläche in einem Slot sitzt — das ehrliche Maß.

    Dreieckszahlen lügen nach einem Voxellauf: die Treppe erzeugt viele kleine
    Flächen, wo das Original wenige große hatte.
    """
    areas = mesh.raw.area_faces
    chosen = [area for area, entry in zip(areas, mesh.slots, strict=True) if entry == slot]
    return float(sum(chosen) / areas.sum())


def test_with_slot_paints_every_triangle() -> None:
    painted = with_slot(cube(), 2)

    assert len(painted.slots) == painted.triangle_count
    assert counts(painted) == {2: painted.triangle_count}
    assert used_slots(painted) == (2,)


def test_a_body_without_slots_counts_as_one_material() -> None:
    assert counts(cube()) == {0: 12}
    assert used_slots(cube()) == (0,)


def test_slots_survive_a_direct_difference() -> None:
    result = boolean("difference", [with_slot(cube(), 1), pin()])

    assert result.solver.strategy == "direct"
    assert used_slots(result.mesh) == (0, 1), "the bore wall is new, the outside is not"
    outside = 6 * 400 - 2 * 9 * 3.14159
    assert area_share(result.mesh, 1) == pytest.approx(
        outside / (outside + 2 * 3.14159 * 3 * 20), abs=0.01
    ), "exactly the cube surface minus the two mouths of the bore"


def test_slots_survive_the_voxel_stage() -> None:
    """§20, der Fall, der die Arbeit kostet: die Vernetzung wurde weggeworfen."""
    result = boolean("difference", [with_slot(cube(), 1), pin()], stages=("voxel",))

    assert result.solver.strategy == "voxel"
    assert used_slots(result.mesh) == (0, 1)
    assert area_share(result.mesh, 1) == pytest.approx(0.82, abs=0.08), (
        "the outside of the cube keeps its colour, the bore does not get it"
    )


def test_slots_survive_the_decimation() -> None:
    """Die Dezimierung wirft Dreiecke weg — nicht die Farbe darauf.

    §20 nennt die Booleschen Operationen, weil dort die Arbeit sitzt. Der Satz
    dahinter gilt weiter: Eine Zuweisung, die eine Operation still verliert, ist
    eine, die der Nutzer neu machen darf. Gemessen an einer Kugel, deren obere
    Hälfte Slot 1 trägt: 20 480 Dreiecke gingen hinein, 5 000 kamen heraus, und
    alle 20 480 Slots waren fort.

    Die Grenze zwischen den Farben verläuft nach dem Zusammenlegen nicht mehr
    exakt am Äquator — ein Dreieck, das beide Hälften überspannt, hat keine
    richtige Antwort. Deshalb der Flächenanteil und nicht die Dreieckszahl.
    """
    body = trimesh.creation.icosphere(subdivisions=5)
    upper = tuple(int(centre[2] > 0.0) for centre in body.triangles_center)
    two_tone = MeshData(raw=body, slots=upper)

    reduced = decimate(two_tone, 5_000)

    assert len(reduced.slots) == reduced.triangle_count, "jedes Dreieck trägt einen Slot"
    assert used_slots(reduced) == (0, 1), "beide Farben sind noch da"
    assert area_share(reduced, 1) == pytest.approx(0.5, abs=0.02), "der Äquator liegt, wo er lag"


def test_slots_survive_the_decimation_of_an_unwelded_body() -> None:
    """Derselbe Satz, aber über den Weg, der beim Verschweißen entlangführt.

    Seit `decimate` ein unverschweißtes Netz zuerst verschweißt, gibt es zwei
    Wege durch die Funktion, und der Test darüber fährt nur den einen: Seine
    Kugel kommt aus `trimesh` und ist verschweißt. Ein Netz aus einer Datei ist
    es nie — und §20 gilt auf beiden Wegen.

    Die Stelle, an der es hätte brechen können, ist `replacing`: Sie lässt eine
    Zuweisung fallen, deren Länge nicht mehr passt. Das Verschweißen ändert die
    Punkte und nicht die Dreiecke, also passt sie — aber das ist eine Zusage
    über `merge_vertices`, und Zusagen über fremde Funktionen gehören geprüft.
    """
    ball = trimesh.creation.icosphere(subdivisions=5)
    # Eine Dreieckssuppe, wie sie aus einer STL kommt: kein Punkt geteilt.
    loose = trimesh.Trimesh(
        vertices=ball.vertices[ball.faces].reshape(-1, 3),
        faces=np.arange(len(ball.faces) * 3).reshape(-1, 3),
        process=False,
    )
    upper = tuple(int(centre[2] > 0.0) for centre in loose.triangles_center)
    two_tone = MeshData(raw=loose, slots=upper)
    # Gefragt wird die Speicherform und nicht das Teil: Die Komponentenzählung
    # sagt seit dem 27.08.2026 richtig **1** — eine Kugel ist ein Teil, gleich
    # wie sie abgelegt ist. Was dieser Test braucht, ist die Zusicherung, dass
    # keine Kante zwei Dreiecke verbindet; daran zieht die Dezimierung.
    assert len(loose.face_adjacency) == 0, "die Suppe ist keine Suppe"

    reduced = decimate(two_tone, 5_000)

    assert reduced.is_watertight, "beim Dezimieren aufgerissen"
    assert len(reduced.slots) == reduced.triangle_count, "jedes Dreieck trägt einen Slot"
    assert used_slots(reduced) == (0, 1), "beide Farben sind noch da"
    assert area_share(reduced, 1) == pytest.approx(0.5, abs=0.02), "der Äquator liegt, wo er lag"


def test_the_decimation_invents_no_slots() -> None:
    """Ein Körper mit einem Material bleibt einer — auch nach der Dezimierung.

    Das ist nicht nur Kosmetik: Ohne Slots läuft die Übertragung gar nicht erst
    an, und damit auch keine Anfrage an den ``rtree``-Index. Der Viewport
    dezimiert jedes große Modell für die Anzeige, und die allermeisten sind
    einfarbig.
    """
    reduced = decimate(MeshData.of(trimesh.creation.icosphere(subdivisions=5)), 5_000)

    assert not reduced.slots


def test_the_cutter_does_not_paint_the_body_it_cuts() -> None:
    """Ein Loch durch ein rotes Teil hat graue Wände, nicht die Farbe des
    Bohrers.
    """
    result = boolean("difference", [with_slot(cube(), 1), with_slot(pin(), 7)])

    assert 7 not in used_slots(result.mesh)


def test_a_named_cut_slot_lands_on_the_new_faces() -> None:
    result = boolean("difference", [with_slot(cube(), 1), pin()], cut_slot=3)

    assert used_slots(result.mesh) == (1, 3)


def test_without_slots_nothing_is_invented() -> None:
    result = boolean("difference", [cube(), pin()])

    assert not result.mesh.slots, "one material in, one material out"


def test_transfer_keeps_a_union_of_two_colours_apart() -> None:
    left = with_slot(cube(), 1)
    right = with_slot(cube(offset=(20.0, 0.0, 0.0)), 2)

    result = boolean("union", [left, right])

    assert used_slots(result.mesh) == (1, 2)
    assert area_share(result.mesh, 1) == pytest.approx(0.5, abs=0.05)


def test_the_assignment_is_reproducible() -> None:
    """Gleiche Eingabe, gleiche Zuweisung — nichts hier darf zufällig
    sein (§11.3).
    """
    first = boolean("difference", [with_slot(cube(), 1), pin()], stages=("voxel",))
    second = boolean("difference", [with_slot(cube(), 1), pin()], stages=("voxel",))

    assert first.mesh.slots == second.mesh.slots


def test_transfer_takes_the_surfaces_it_is_given() -> None:
    """Die Regel aus §20 lebt in ``transfer``; wer als Quelle zählt, wird
    außerhalb entschieden.
    """
    result = boolean("difference", [with_slot(cube(), 1), with_slot(pin(), 7)])
    including_the_tool = transfer(result.mesh, [with_slot(cube(), 1), with_slot(pin(), 7)])

    assert used_slots(including_the_tool) == (1, 7), "asked for the tool, gets the tool"
    assert used_slots(result.mesh) == (0, 1), "the operation does not ask for it"


def model_of(data: bytes) -> ET.Element:
    with zipfile.ZipFile(BytesIO(data)) as container:
        return ET.fromstring(container.read(threemf.MODEL_PATH))


def test_3mf_is_a_readable_container() -> None:
    data = threemf.write(cube())

    with zipfile.ZipFile(BytesIO(data)) as container:
        assert container.testzip() is None
        assert set(container.namelist()) == {
            "[Content_Types].xml",
            "_rels/.rels",
            threemf.MODEL_PATH,
        }


def test_3mf_carries_one_colour_group_per_slot() -> None:
    body = boolean("union", [with_slot(cube(), 1), with_slot(cube(offset=(20, 0, 0)), 2)]).mesh
    slots = [
        MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0)),
        MaterialSlot(index=2, name="Schwarz", colour=(0.0, 0.0, 0.0)),
    ]

    model = model_of(threemf.write(body, slots, "Zweifarbig"))

    materials = model.findall(".//c:basematerials/c:base", NAMESPACE)
    assert [entry.get("name") for entry in materials] == ["Rot", "Schwarz"]
    assert [entry.get("displaycolor") for entry in materials] == ["#FF0000", "#000000"]

    triangles = model.findall(".//c:triangle", NAMESPACE)
    assert len(triangles) == body.triangle_count
    assert {entry.get("p1") for entry in triangles} == {"0", "1"}, "both groups are used"


def test_3mf_only_declares_the_slots_the_body_uses() -> None:
    """Ein Objekt darf fünf Filamente kennen; die Datei nennt nur die, die auf
    ihm sind.
    """
    slots = [MaterialSlot(index=index, name=f"Farbe {index}") for index in range(5)]

    model = model_of(threemf.write(with_slot(cube(), 3), slots))

    materials = model.findall(".//c:basematerials/c:base", NAMESPACE)
    assert [entry.get("name") for entry in materials] == ["Farbe 3"]
    assert {entry.get("p1") for entry in model.findall(".//c:triangle", NAMESPACE)} == {"0"}


def test_3mf_gives_a_slot_without_a_colour_a_neutral_grey() -> None:
    model = model_of(threemf.write(with_slot(cube(), 1), [MaterialSlot(index=1, name="Sonder")]))

    base = model.find(".//c:basematerials/c:base", NAMESPACE)
    assert base is not None and base.get("displaycolor") == "#B8B8B8"


def test_3mf_keeps_the_geometry_and_the_unit() -> None:
    model = model_of(threemf.write(cube(), name="Würfel"))

    assert model.get("unit") == "millimeter", "millimetres are the unit of §11.1"
    assert len(model.findall(".//c:vertex", NAMESPACE)) == 8
    assert len(model.findall(".//c:triangle", NAMESPACE)) == 12
    assert model.find(".//c:build/c:item", NAMESPACE) is not None


def test_3mf_written_here_can_be_read_here_again() -> None:
    """§20, Import: eine aus Solidon exportierte Datei darf ihre Farben nicht
    verlieren.
    """
    body = boolean("union", [with_slot(cube(), 1), with_slot(cube(offset=(20, 0, 0)), 2)]).mesh
    slots = [
        MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0)),
        MaterialSlot(index=2, name="Schwarz", colour=(0.0, 0.0, 0.0)),
    ]

    groups = threemf_reader.read(threemf.write(body, slots), body.triangle_count)

    assert groups is not None
    assert [entry.name for entry in groups.materials] == ["Rot", "Schwarz"]
    assert groups.materials[0].colour == pytest.approx((1.0, 0.0, 0.0))
    assert len(groups.slots) == body.triangle_count
    assert set(groups.slots) == {0, 1}, "3MF numbers groups by position, not by our slot number"


def test_reading_a_3mf_without_groups_says_so() -> None:
    assert threemf_reader.read(threemf.write(cube()), 12) is None, "one material is not a group"
    assert threemf_reader.read(threemf.write(with_slot(cube(), 4)), 12) is None
    assert threemf_reader.read(b"not a container", 12) is None


def test_a_3mf_with_a_different_triangle_count_is_not_guessed_at() -> None:
    """Mehrere Körper werden auf dem Weg hinein aneinandergehängt — dann ist
    die Reihenfolge unbekannt.
    """
    assert threemf_reader.read(threemf.write(with_slot(cube(), 1)), 999) is None


def test_loading_a_3mf_brings_its_colours_into_the_scene(profile: Profile) -> None:
    """Die ganze Importseite von §20: Datei auf der Platte, farbiges Objekt in
    der Szene.
    """
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source
    from app.i18n import _

    body = boolean("union", [with_slot(cube(), 1), with_slot(cube(offset=(20, 0, 0)), 2)]).mesh
    payload = threemf.write(
        body,
        [
            MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0)),
            MaterialSlot(index=2, name="Schwarz", colour=(0.0, 0.0, 0.0)),
        ],
        "Zweifarbig",
    )

    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    document = project.document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/zweifarbig.3mf", sha256=""
    )
    History(document).apply(
        _("Laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm", "weld": False})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    entry = result.scene.objects["obj_1"]
    assert [slot.name for slot in entry.material_slots] == ["Rot", "Schwarz"]
    assert set(entry.mesh.slots) == {0, 1}


def test_export_writes_3mf_with_the_slots_of_the_object(profile: Profile) -> None:
    """The whole way through: scene object, plan, bytes."""
    entry = SceneObject(
        id="obj-1",
        name="Zweifarbig",
        mesh=with_slot(cube(), 1),
        material_slots=[MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0))],
    )

    plan = plan_export([entry], project_name="Test", profile=profile, export_format="3mf")
    data = export_bytes(plan.entries[0].mesh, "3mf", list(plan.entries[0].slots))

    assert plan.entries[0].filename == "Test_Zweifarbig.3mf"
    base = model_of(data).find(".//c:basematerials/c:base", NAMESPACE)
    assert base is not None and base.get("displaycolor") == "#FF0000"


# --- Der Vorfilter, mit dem die Übertragung bezahlbar wurde ----------------------


def _without_the_shortcut(
    result: MeshData, sources: list[MeshData], *, cut_slot: int = 0
) -> tuple[int, ...]:
    """Die Übertragung, wie sie vor dem Vorfilter lief: jedes Dreieck gegen
    jede Quelle."""
    import numpy as np

    from app.core.geom.attributes import NEAR_LIMIT, _nearest

    centres = np.asarray(result.raw.triangles_center, dtype=float)
    slots = np.full(len(centres), cut_slot, dtype=np.int32)
    distance = np.full(len(centres), np.inf)
    for mesh in sources:
        if not mesh.slots:
            continue
        found, offset = _nearest(mesh, centres)
        closer = offset < distance
        slots[closer] = found[closer]
        distance[closer] = offset[closer]
    limit = max(result.bounds.diagonal, 1.0) * NEAR_LIMIT
    slots[distance > limit] = cut_slot
    return tuple(int(entry) for entry in slots)


def test_the_shortcut_changes_nothing_about_the_result() -> None:
    """Der Vorfilter ist derselbe Wert auf kürzerem Weg, keine Näherung.

    Ein Dreieck, das zu keiner Quelle mit eigener Farbe nah genug liegt,
    bekommt am Ende den Schnittslot — ob eine Quelle, die ohnehin nur den
    Schnittslot trägt, näher liegt, ändert daran nichts. Für die Dose aus dem
    Beispielprojekt hieß das: sechseinhalb der siebeneinhalb Sekunden einer
    Auswertung gingen darauf, für vierzigtausend Dreiecke den Abstand zu einer
    sechshundert Dreiecke großen Beschriftung zu suchen.
    """
    body = with_slot(cube(20.0), 0)
    label = with_slot(cube(4.0, offset=(0.0, 0.0, 10.0)), 1)
    merged = boolean("union", [body, label]).mesh

    expected = _without_the_shortcut(merged, [body, label])
    actual = transfer(merged, [body, label])

    assert tuple(actual.slots) == expected


@pytest.mark.parametrize(
    ("offset", "size"),
    [
        ((0.0, 0.0, 10.0), 4.0),
        ((0.0, 0.0, 8.0), 6.0),
        ((0.0, 0.0, 0.0), 30.0),
        ((6.0, 6.0, 6.0), 12.0),
    ],
    ids=["aufgesetzt", "eingesenkt", "umschliessend", "ueberlappend"],
)
def test_the_shortcut_holds_where_the_bodies_meet(
    offset: tuple[float, float, float], size: float
) -> None:
    """Auch dort, wo beide Quellen demselben Dreieck nah sind.

    Eine Quelle, die nur den Schnittslot trägt, darf nicht übersprungen
    werden: an der Naht entscheidet, welche näher liegt, und dort trägt der
    farblose Körper seine Fläche zu Recht. Der Vorfilter lässt deshalb die
    Suche über *alle* Quellen laufen — er wählt nur die Dreiecke aus, für die
    sie etwas ändern kann.
    """
    body = with_slot(cube(20.0), 0)
    label = with_slot(cube(size, offset=offset), 1)
    merged = boolean("union", [body, label]).mesh

    expected = _without_the_shortcut(merged, [body, label])
    actual = transfer(merged, [body, label])

    assert tuple(actual.slots) == expected


def test_on_surface_matches_the_exact_answer_without_any_index() -> None:
    """Die Näherungssuche ist exakt — verglichen mit der indexfreien Referenz.

    ``on_surface`` fragt seit dem 24.08.2026 einen eigenen Baum über den
    Dreiecksschwerpunkten statt ``trimesh.proximity`` mit seinem
    ``rtree``-Index: ``rtree`` griff auf dieser Maschine in fremde Seiten, und
    ein Kunde verlor beim Ändern eines Maßes die Anwendung — ohne eine Zeile
    im Protokoll. Der Ersatz ist ein Vorfilter mit Schranke, kein
    Näherungsverfahren; genau das prüft dieser Vergleich, und zwar gegen
    ``closest_point_naive``, das jedes Dreieck ansieht und keinerlei Index
    kennt.

    Der Zylinder steht mit in der Reihe, weil er der unbequeme Fall ist: hohe
    Seitendreiecke machen die Schwerpunkt-Ecke-Spanne groß und die
    Kandidatenmengen weit — wer hier besteht, rät nicht.
    """
    from trimesh.proximity import closest_point_naive

    from app.core.geom.mesh import on_surface

    rng = np.random.default_rng(11)
    bodies = (
        trimesh.creation.box((20.0, 20.0, 20.0)),
        trimesh.creation.icosphere(subdivisions=3, radius=15.0),
        trimesh.creation.cylinder(radius=8.0, height=40.0, sections=32),
    )
    for body in bodies:
        # nah, fern und auf der Oberfläche — die drei Lagen, die es gibt
        points = np.vstack(
            [
                rng.uniform(-30.0, 30.0, size=(60, 3)),
                rng.uniform(200.0, 400.0, size=(20, 3)),
                body.triangles.mean(axis=1)[:40],
            ]
        )
        closest, distance, triangle = on_surface(body, points)
        _spot, exact, _tri = closest_point_naive(body, points)
        assert np.allclose(distance, exact, atol=1e-9), "distances must match the naive truth"
        assert np.allclose(np.linalg.norm(points - closest, axis=1), distance, atol=1e-9), (
            "the returned spot must be as far away as the returned distance says"
        )
        # Der dritte Rückgabewert wird **benutzt**, nicht nur angesehen: Der
        # nächste Ort muss auf genau dem genannten Dreieck liegen — eine
        # endliche Norm war für jeden Index wahr und prüfte nichts.
        on_named = trimesh.triangles.closest_point(
            triangles=body.triangles[triangle], points=points
        )
        assert np.allclose(np.linalg.norm(points - on_named, axis=1), distance, atol=1e-9), (
            "the named triangle must carry the closest spot"
        )
        assert triangle.dtype == np.int64


def test_one_large_triangle_does_not_widen_every_surface_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine einzelne große Fläche darf nicht jede kleine Fläche zum Kandidaten machen.

    Die exakte Suche schrank früher alle Dreiecke mit der **größten**
    Schwerpunkt-Ecke-Spanne des ganzen Netzes ein. Im Dosenbeispiel hatten
    ein Prozent der Flächen eine große Spanne; dadurch wurden für 849 Punkte
    32,36 Millionen Dreieckspaare exakt nachgerechnet. Kleine und große
    Dreiecke getrennt einzuschränken ändert die Antwort nicht, nur die Menge
    der Kandidaten. Die Paarzahl prüft diese Struktur ohne eine wackelige
    Zeitgrenze.
    """
    from app.core.geom.mesh import on_surface

    steps = 64
    axis = np.linspace(-10.0, 10.0, steps + 1)
    grid_x, grid_y = np.meshgrid(axis, axis, indexing="xy")
    vertices = np.column_stack((grid_x.ravel(), grid_y.ravel(), np.zeros(grid_x.size)))
    row = np.arange(steps)[:, None] * (steps + 1)
    column = np.arange(steps)[None, :]
    bottom_left = (row + column).ravel()
    bottom_right = bottom_left + 1
    top_left = bottom_left + steps + 1
    top_right = top_left + 1
    faces = np.vstack(
        (
            np.column_stack((bottom_left, bottom_right, top_right)),
            np.column_stack((bottom_left, top_right, top_left)),
        )
    )
    grid = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    broad = trimesh.Trimesh(
        vertices=np.asarray(((-200.0, -200.0, -10.0), (200.0, -200.0, -10.0), (0.0, 200.0, -10.0))),
        faces=np.asarray(((0, 1, 2),)),
        process=False,
    )
    body = trimesh.util.concatenate((grid, broad))
    points = np.column_stack(
        (
            np.linspace(-9.75, 9.75, 64),
            np.linspace(9.25, -9.25, 64),
            np.full(64, 0.05),
        )
    )

    examined = 0
    exact = trimesh.triangles.closest_point

    def counted(triangles: np.ndarray, queries: np.ndarray) -> np.ndarray:
        nonlocal examined
        examined += len(triangles)
        return exact(triangles, queries)

    monkeypatch.setattr(trimesh.triangles, "closest_point", counted)
    closest, distance, triangle = on_surface(body, points)

    assert examined < 50_000, f"{examined} Dreieckspaare sind kein räumlicher Vorfilter"
    assert np.allclose(distance, 0.05, atol=1e-12)
    assert np.allclose(closest[:, 2], 0.0, atol=1e-12)
    assert np.all(triangle < len(grid.faces)), "die nahe Rasterfläche muss gewinnen"


def test_the_geometry_paths_never_load_rtree() -> None:
    """Die Zusage hinter dem Umbau vom 24.08.2026: ``rtree`` rechnet nie mehr
    mit.

    Nicht „der Baum kann es", sondern „die Anwendung tut es" — deshalb ein
    eigener Prozess, und deshalb alle **vier** Wege, die je durch den Index
    liefen: die Näherungssuche (``on_surface``), der gedeckelte Schnitt durch
    eine Platte mit Loch (``slice_plane`` läuft durch ``enclosure_tree``, und
    genau dieser dritte Nutzer flog erst mit dieser Probe auf), das Einlesen
    einer Zeichnung — und der Strahlweg der Stiftplanung, die Ersetzung, die
    zuvor als einzige in keiner Probe stand.

    **Geprüft wird der Code, nicht die Umgebung.** ``import trimesh`` zieht
    ein installiertes ``rtree`` über seine eigenen abgesicherten Importe
    herein — ein Rechner, dessen ``.venv`` das Paket noch trägt, wäre mit
    einem ``sys.modules``-Blick rot, ohne dass ein Fehler vorliegt. Die Probe
    macht ``rtree`` deshalb **unbenutzbar**, wo es importierbar ist, und
    verlangt, dass der Patch wirklich unsere Fassung eingesetzt hat; die
    ``sys.modules``-Frage bleibt nur dort, wo das Paket fehlt. Dass es auf
    unseren Ständen fehlt, erzwingt daneben die Sperrliste
    (``banned_packages`` in ``licences.toml`` — Stabilität, nicht Lizenz).
    """
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    probe = (
        "import sys\n"
        "try:\n"
        "    import rtree.index as _rtree_index\n"
        "except Exception:\n"
        "    _rtree_index = None\n"
        "if _rtree_index is not None:\n"
        "    class _Boom:\n"
        "        def __init__(self, *args, **kwargs):\n"
        "            raise AssertionError('rtree wurde benutzt')\n"
        "    _rtree_index.Index = _Boom\n"
        "from pathlib import Path\n"
        "import numpy as np, trimesh\n"
        "import trimesh.path.polygons as _polygons\n"
        "from app.core.geom import enclosure\n"
        "from app.core.geom.mesh import MeshData, on_surface\n"
        "from app.core.geom.pins import plan_pins\n"
        "from app.core.geom.section import cut, SectionPlane\n"
        "from app.core.ingest.outline import extrude\n"
        "closest, distance, triangle = on_surface(\n"
        "    trimesh.creation.box((20.0, 20.0, 20.0)), np.array([[100.0, 0.0, 0.0]])\n"
        ")\n"
        "assert abs(float(distance[0]) - 90.0) < 1e-9\n"
        "plate = trimesh.creation.box((60.0, 40.0, 10.0))\n"
        "hole = trimesh.creation.cylinder(radius=6.0, height=30.0)\n"
        "body = trimesh.boolean.difference([plate, hole], engine='manifold')\n"
        "sliced = cut(MeshData.of(body), SectionPlane(normal=(0.0, 0.0, 1.0), position=0.0))\n"
        "assert _polygons.enclosure_tree is enclosure.enclosure_tree, "
        "'der Schnitt installiert den Patch nicht'\n"
        "assert sliced.capped and sliced.mesh.raw.is_watertight\n"
        "wall = trimesh.creation.box((60.0, 40.0, 10.0))\n"
        "plan = plan_pins(MeshData.of(wall), SectionPlane(normal=(1.0, 0.0, 0.0), position=0.0))\n"
        "assert plan.count >= 1, plan.count\n"
        "drawing = Path('app/examples/weg2-halter-konstruieren.svg').read_bytes()\n"
        "outline = extrude(drawing, '.svg', height=3.0)\n"
        "assert outline.contours == 197, outline.contours\n"
        "if _rtree_index is None:\n"
        "    assert 'rtree' not in sys.modules, 'rtree wurde geladen'\n"
        "print('ohne rtree')\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(root),
    )
    assert done.returncode == 0, done.stderr
    assert "ohne rtree" in done.stdout
