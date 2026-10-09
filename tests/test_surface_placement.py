"""Präzise Platzierung auf Originalflächen, einschließlich Aussparungen und freier Richtung."""

import math

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.geom.transform import apply, rotation
from app.core.registry import REGISTRY
from app.core.scene import placement
from app.core.types import Feature
from tests.helpers import exact_kernel


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("consumer", ["primitive", "centred", "part"])
def test_a_saved_surface_placement_keeps_its_edge_distances(
    profile, kind, quality, consumer, tmp_path
):
    """Eine geänderte Trägerbreite bewegt den Ansatz, seine zwei Randabstände bleiben."""
    from app.core.geom.mesh import MeshCodec, as_mesh_data
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import load, new_project, save
    from app.core.types import Parameter
    from tests.helpers import inside

    if kind == "brep":
        exact_kernel()
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    cache_directory = tmp_path / "cache"
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=cache_directory))
    create = "create_box" if kind == "mesh" else "create_brep_box"
    history.apply(
        "Träger",
        [OperationDraft(op=create, params={"width": 40.0, "depth": 30.0, "height": 10.0})],
    )
    prefix = evaluate(project.document, profile, quality=quality, cache=cache)
    assert prefix.complete
    source = prefix.scene.objects["obj_1"]
    mesh = as_mesh_data(source.mesh)
    surface = placement.prepare_surface(mesh, _top(mesh), source.features)
    hit = placement.at_point(surface, (-12.0, -6.0, 10.0))
    assert sorted(edge.distance for edge in hit.edges) == pytest.approx([8.0, 9.0])
    name = create if consumer != "part" else "insert_magnet_pocket"
    values = placement.bound_surface_values(REGISTRY.get(name), source, hit)
    project.document.parameters["edge_distance"] = Parameter("edge_distance", hit.edges[0].distance)
    values["surface_distance_1"] = "=@edge_distance"
    if consumer != "part":
        values.update(width=4.0, depth=6.0, height=8.0)
        if consumer == "centred":
            values["surface_seat"] = "centred"
    history.apply(
        "Auf die Fläche",
        [OperationDraft(op=name, inputs=() if consumer != "part" else (source.id,), params=values)],
    )
    before = evaluate(project.document, profile, quality=quality, cache=cache)
    assert before.complete, before.scene.report.findings
    history.change_params(
        project.document.ops[0].id, {"width": 60.0, "depth": 50.0, "height": 12.0}
    )
    changed = evaluate(project.document, profile, quality=quality, cache=cache)
    assert changed.complete, changed.scene.report.findings
    made = changed.scene.objects["obj_2" if consumer != "part" else "obj_1"]
    if consumer != "part":
        low = (-2.0, -3.0, 12.0) if consumer == "centred" else (-24.0, -19.0, 12.0)
        high = (2.0, 3.0, 20.0) if consumer == "centred" else (-20.0, -13.0, 20.0)
        assert made.mesh.bounds.minimum == pytest.approx(low)
        assert made.mesh.bounds.maximum == pytest.approx(high)
    else:
        body = as_mesh_data(made.mesh)
        assert inside(body, [(-22.0, -16.0, 11.0), (-12.0, -6.0, 11.0)]).tolist() == [False, True]
    assert made.mesh.is_watertight
    hits = cache.statistics.hits
    cached = evaluate(project.document, profile, quality=quality, cache=cache)
    assert cached.complete and cache.statistics.hits > hits
    history.undo()
    undone = evaluate(project.document, profile, quality=quality, cache=cache)
    assert undone.complete
    original = before.scene.objects[made.id]
    assert undone.scene.objects[made.id].mesh.volume == pytest.approx(
        original.mesh.volume, abs=1e-6
    )
    history.redo()
    redone = evaluate(project.document, profile, quality=quality, cache=cache)
    assert redone.complete
    assert redone.scene.objects[made.id].mesh.bounds.minimum == pytest.approx(
        made.mesh.bounds.minimum
    )
    saved = save(project, tmp_path / "surface.p3d")
    loaded = load(saved)
    assert loaded.document.ops[-1].params["surface_distance_1"] == "=@edge_distance"
    reopened = evaluate(
        loaded.document,
        profile,
        quality=quality,
        cache=ResultCache(disk=DiskCache(codec=MeshCodec(), directory=cache_directory)),
    )
    assert reopened.complete
    assert reopened.scene.objects[made.id].mesh.volume == pytest.approx(made.mesh.volume, abs=1e-6)
    assert reopened.scene.objects[made.id].mesh.bounds.minimum == pytest.approx(
        made.mesh.bounds.minimum
    )


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_surface_binding_without_detected_features_keeps_the_carrier_and_its_frame(profile, kind):
    """Auch eine unbenannte Fläche liefert den Träger und lebt in dessen gespeicherter Lage."""
    from dataclasses import replace

    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.transform import moved_object
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cancel import NeverCancelled
    from app.core.scene.project import new_project

    if kind == "brep":
        exact_kernel()
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    create = "create_box" if kind == "mesh" else "create_brep_box"
    History(project.document).apply(
        "Träger", [OperationDraft(op=create, params={"width": 40.0, "depth": 30.0, "height": 10.0})]
    )
    result = evaluate(project.document, profile)
    source = replace(result.scene.objects["obj_1"], features={})
    mesh = as_mesh_data(source.mesh)
    prepared = placement.prepare_surface(mesh, _top(mesh), source.features)
    hit = placement.at_point(prepared, (-12.0, -6.0, 10.0))
    spec = REGISTRY.get(create)
    values = placement.bound_surface_values(spec, source, hit)
    assert not values["surface_target"]
    matrix = np.array(
        ((0.0, -1.0, 0.0, 7.0), (1.0, 0.0, 0.0, 11.0), (0.0, 0.0, 1.0, 4.0), (0.0, 0.0, 0.0, 1.0))
    )
    moved = moved_object(source, matrix, cancelled=NeverCancelled())
    binding = placement.bind_surface(
        spec,
        values,
        {moved.id: moved},
        {moved.id: "moved"},
        ask=lambda *_: pytest.fail("Eindeutiger Bezug fragt nicht"),
        announce=None,
        cancelled=NeverCancelled(),
    )
    assert binding.source_id == moved.id
    assert binding.prepared is not None and binding.placed is not None
    assert binding.placed.point == pytest.approx((13.0, -1.0, 14.0))
    assert [edge.distance for edge in binding.placed.edges] == pytest.approx(
        [edge.distance for edge in hit.edges]
    )
    assert values["x"] == pytest.approx(-12.0), "Die gespeicherten Parameter bleiben unverändert."
    assert not binding.answers


def _top(mesh):
    return int(np.argmax(np.asarray(mesh.raw.face_normals)[:, 2]))


def _carrier_with_a_bore(profile, carrier):
    """Ein Projekt mit einer Bohrung, wie der Kunde sie hatte.

    Aus dem Korpus (glatt oder gesenkt) oder ein exakter Quader in den Maßen
    seines STEP-Teils mit *Schraubenloch mit Senkung* M6, mit oder ohne
    Senkkopf. Zurück kommen Projekt, Verlauf, Quellen, Träger und Bohrung.
    """
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source
    from tests.helpers import MESHES

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    if carrier.endswith(".stl"):
        project.document.sources["src_1"] = Source(
            id="src_1", kind="import", path=f"sources/{carrier}", sha256=""
        )
        project.sources["src_1"] = (MESHES / carrier).read_bytes()
        history.apply(
            "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
        )
    else:
        exact_kernel()
        history.apply(
            "Träger",
            [
                OperationDraft(
                    op="create_brep_box", params={"width": 34.13, "depth": 40.74, "height": 14.15}
                )
            ],
        )
        box = evaluate(project.document, profile).scene.objects["obj_1"]
        top = next(
            identifier
            for identifier, feature in box.features.items()
            if feature.kind == "face" and feature.params["normal"][2] > 0.9
        )
        history.apply(
            "Schraubenloch",
            [
                OperationDraft(
                    op="insert_screw_hole",
                    inputs=("obj_1",),
                    params={
                        "at_feature": top,
                        "size": "M6",
                        "countersink": carrier.endswith("countersunk"),
                    },
                )
            ],
        )
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources)
    assert before.complete, before.scene.report.findings
    source = before.scene.objects["obj_1"]
    bore = next(
        feature
        for _identifier, feature in sorted(source.features.items())
        if feature.kind == "hole"
    )
    return project, history, sources, source, bore


def _seated_in_the_bore(history, source, bore, name, **chosen):
    """Den Baustein so in die Bohrung setzen, wie die Platzierung es im Fenster tut.

    ``PlacementFlow._begin_on_a_face`` sitzt über ``seat_of`` in der Mündung,
    ``_set_values`` legt Lage und Flächenbezug in den Schritt; ``chosen``
    überschreibt danach, was der Kunde im Dialog ändert.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene import OperationDraft

    seated = placement.seat_of(as_mesh_data(source.mesh), bore, source.features)
    assert seated is not None, "die Bohrung hat eine Mündungsfläche"
    prepared, mouth = seated
    hit = placement.at_point(prepared, mouth)
    spec = REGISTRY.get(name)
    values = dict(placement.values_for(spec, bore, source.id))
    values.update(placement.surface_values(spec, hit, feature=bore, source=source))
    values.update(placement.bound_surface_values(spec, source, hit))
    assert values["surface_anchor"], "die Platzierung speichert den Flächenbezug"
    values.update(chosen)
    history.apply(spec.title, [OperationDraft(op=name, inputs=(source.id,), params=values)])
    return values


@pytest.mark.parametrize(
    "carrier",
    ["plate_holes.stl", "plate_countersunk.stl", "screw_hole", "screw_hole_countersunk"],
)
def test_a_part_seated_in_the_chosen_bore_is_built_there(profile, carrier):
    """Ein Baustein, den die Platzierung selbst in die gewählte Bohrung setzt, wird gebaut.

    Kundenmeldung zu 0.5.2: Bohrung angeklickt, *Druckbares Gewinde* aus dem
    Katalog, und jeder Versuch endete mit „Dieser Punkt liegt außerhalb der
    gewählten Fläche“ — an einer STEP-Bohrung, an einem *Schraubenloch mit
    Senkung* aus dem Katalog, an einem Netz. Die Platzierung setzt den
    Baustein über ``seat_of`` in die Mündung; deren Fläche hat die eigene
    Öffnung gefüllt, und der gespeicherte Punkt ist die Mitte der Bohrung.
    Beim Rechnen bereitete ``bind_surface`` dieselbe Fläche **mit** Öffnung
    vor, und die Mitte lag in der Luft.

    Der Weg wird gegangen wie im Fenster, für jeden Baustein, der in
    Bohrungen gehört, und an beiden Kernen mit und ohne Senkung. Er muss
    rechnen, und was er erzeugt, sitzt auf der Achse der Bohrung.
    """
    from app.core.knowledge.parts.ops import part_of
    from app.core.scene import evaluate

    load_operations()
    names = [
        spec.name
        for spec in REGISTRY.all()
        if spec.consumes and (part := part_of(spec.name)) is not None and part.at_hole
    ]
    assert len(names) >= 4, names
    for name in names:
        project, history, sources, source, bore = _carrier_with_a_bore(profile, carrier)
        suggested = "size" in placement.values_for(REGISTRY.get(name), bore, source.id)
        _seated_in_the_bore(history, source, bore, name)

        after = evaluate(project.document, profile, sources=sources)

        assert after.complete, (
            name,
            [
                (finding.code, str(finding.message))
                for finding in after.scene.report.findings
                if finding.severity == "error"
            ],
        )
        step = project.document.ops[-1].id
        made = [
            feature
            for entry in after.scene.objects.values()
            for feature in entry.features.values()
            if feature.created_by == step
            and feature.params.get("centre") is not None
            and feature.params.get("axis") is not None
        ]
        assert made, f"{name} meldet kein rundes Merkmal"
        codes = [finding.code for finding in after.scene.report.findings]
        if suggested:
            assert "parts.bore_too_wide" not in codes, (name, "die vorgeschlagene Größe passt")
        if name in {"insert_printed_thread", "insert_heatset_m4"}:
            # Beide bleiben im Radius ihrer Bohrung oder knapp darüber, und jede
            # Bohrung liegt mindestens 5 mm vom Rand: Über die Öffnung, in der
            # sie sitzen, reichen sie nicht „über den Rand der Fläche“.
            assert "part.over_the_edge" not in codes, name
        axis = np.asarray(bore.params["axis"], dtype=float)
        axis /= np.linalg.norm(axis)
        for feature in made:
            offset = np.asarray(feature.params["centre"], dtype=float) - bore.params["centre"]
            across = offset - np.dot(offset, axis) * axis
            assert np.linalg.norm(across) == pytest.approx(0.0, abs=1e-6), (name, feature.id)


@pytest.mark.parametrize(
    ("carrier", "size", "named"),
    # Im Schraubenloch M6 (Ø 6,6) passt keine Tabellengröße; der Satz nennt das eigene Maß.
    [("plate_holes.stl", "M4", "M6"), ("screw_hole", "M6", "eigenem Maß")],
)
def test_a_thread_in_a_wider_bore_names_the_bore_not_the_body(profile, carrier, size, named):
    """Ein Gewinde, das in seiner Bohrung nichts abträgt, sagt, dass sie zu weit ist.

    Der zweite Teil der Kundenmeldung zu 0.5.2: *Schraubenloch mit Senkung*
    M6 bohrt Ø 6,6, ein *Druckbares Gewinde* M6 reicht nur bis 6 mm plus
    Spiel. Gemeldet wurde „das Werkzeug liegt neben dem Körper“ — es lag in
    der Bohrung, und der Kunde suchte an der falschen Stelle. Der Befund nennt
    die Bohrung, den Satz über passende Gewinde und *Größe ändern*.
    """
    from app.core.scene import evaluate

    load_operations()
    project, history, sources, source, bore = _carrier_with_a_bore(profile, carrier)
    _seated_in_the_bore(history, source, bore, "insert_printed_thread", size=size)

    after = evaluate(project.document, profile, sources=sources)

    assert after.complete, after.scene.report.findings
    codes = {finding.code: finding for finding in after.scene.report.findings}
    assert "boolean.without_effect" not in codes, "nicht „neben dem Körper“"
    assert "parts.bore_too_wide" in codes, sorted(codes)
    finding = codes["parts.bore_too_wide"]
    assert finding.values["field"] == "size"
    assert [action.id for action in finding.suggestions] == ["change_step"]
    assert named in str(finding.message), str(finding.message)


def test_a_saved_point_in_a_bore_but_off_its_axis_stays_refused():
    """Gefüllt wird nur die Öffnung, deren Achse durch den gespeicherten Punkt geht.

    Gegenstück zu ``test_a_part_seated_in_the_chosen_bore_is_built_there``:
    Ein Bezug, der einen Millimeter neben der Mitte in derselben Bohrung landet
    (Ø 5,2), hat keine Mündung gemeint — er bleibt eine Absage mit Vorschlag,
    statt dass der Baustein still über der Luft sitzt.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import detect
    from app.core.scene.cancel import NeverCancelled
    from tests.helpers import MESHES

    load_operations()
    mesh = MeshData.of(trimesh.load_mesh(MESHES / "plate_holes.stl"))
    features = detect(mesh)
    bore = next(feature for _name, feature in sorted(features.items()) if feature.kind == "hole")
    source = _plate_object(mesh, features)
    seated = placement.seat_of(as_mesh_data(source.mesh), bore, features)
    assert seated is not None
    prepared, mouth = seated
    hit = placement.at_point(prepared, mouth)
    spec = REGISTRY.get("insert_printed_thread")
    values = placement.bound_surface_values(spec, source, hit)

    def bound(shift: float) -> placement.SurfaceBinding:
        moved = dict(values, surface_distance_1=float(values["surface_distance_1"]) + shift)
        return placement.bind_surface(
            spec,
            moved,
            {source.id: source},
            {source.id: "plate"},
            ask=lambda *_: pytest.fail("Eindeutiger Bezug fragt nicht"),
            announce=None,
            cancelled=NeverCancelled(),
        )

    centred = bound(0.0).placed
    assert centred is not None and centred.point == pytest.approx(mouth)
    with pytest.raises(ValidationError, match="außerhalb"):
        bound(1.0)


def _plate_object(mesh, features):
    from app.core.types import SceneObject

    return SceneObject(id="obj_1", name="Platte", mesh=mesh, features=features)


@pytest.mark.parametrize("painted", [False, True])
def test_native_surface_snapshot_keeps_exact_normals_and_owns_its_caches(profile, painted):
    """Die Arbeiterkopie (``Solid.detached``) hält Topologie, Dreiecke und Merker getrennt."""
    from dataclasses import replace

    from app.core.brep.kernel import Solid
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cancel import NeverCancelled
    from app.core.scene.project import new_project

    exact_kernel()
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Träger",
        [OperationDraft(op="create_brep_cylinder", params={"diameter": 20.0, "height": 20.0})],
    )
    source = evaluate(project.document, profile).scene.objects["obj_1"]
    body = source.mesh
    assert isinstance(body, Solid)
    if painted:
        body = body.with_triangle_slots(
            tuple(int(index) % 2 for index in body.raw.face_attributes["solidon_brep_face"])
        )
        source = replace(source, mesh=body)
    snapshot = replace(source, mesh=body.detached())
    assert isinstance(snapshot.mesh, Solid)
    assert snapshot.mesh._cache is not body._cache
    assert snapshot.mesh.raw._cache is not body.raw._cache
    assert not snapshot.mesh.shape.IsPartner(body.shape)
    assert np.array_equal(snapshot.mesh.raw.vertices, body.raw.vertices)
    assert np.array_equal(snapshot.mesh.raw.faces, body.raw.faces)
    assert snapshot.mesh.slot_indices == body.slot_indices
    keys = set(body._cache)
    original_normals = np.asarray(body.raw.face_normals).copy()
    feature = next(entry for entry in source.features.values() if entry.kind == "pin")
    point = placement.surface_at_feature(
        snapshot, feature, point=(6.0, 8.0, 10.0), cancelled=NeverCancelled()
    )
    assert point.point == pytest.approx((6.0, 8.0, 10.0), abs=1e-6)
    assert point.normal == pytest.approx((0.6, 0.8, 0.0), abs=1e-6)
    assert set(body._cache) == keys
    assert np.array_equal(body.raw.face_normals, original_normals)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("shape", ["cylinder", "sphere"])
def test_curved_surface_binding_keeps_its_point_after_scaling_and_turning(profile, kind, shape):
    """Ein gemeinsamer Maßstab darf den gespeicherten Radius nicht zweimal anwenden."""
    from app.core.geom.transform import (
        composed,
        moved_object,
        moved_points,
        scaling,
        translation,
        turned,
    )
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cancel import NeverCancelled
    from app.core.scene.project import new_project

    if kind == "brep":
        exact_kernel()
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    creator = f"create_{'brep_' if kind == 'brep' else ''}{shape}"
    params = {"diameter": 20.0, **({"height": 20.0} if shape == "cylinder" else {})}
    History(project.document).apply("Träger", [OperationDraft(op=creator, params=params)])
    source = evaluate(project.document, profile).scene.objects["obj_1"]
    feature = max(
        (f for f in source.features.values() if f.kind != "face"), key=lambda f: len(f.face_indices)
    )
    point = (6.0, 8.0, 10.0)
    if kind == "mesh" and shape == "sphere":
        index = max(
            feature.face_indices,
            key=lambda i: float(source.mesh.raw.face_normals[i] @ (0.6, 0.8, 0.0)),
        )
        point = tuple(source.mesh.raw.triangles[index].mean(axis=0))
    hit = placement.surface_at_feature(source, feature, point=point)
    spec = REGISTRY.get("create_box")
    values = placement.bound_surface_values(spec, source, hit)
    matrix = composed(translation((7.0, 11.0, 4.0)), rotation("y", 17.0), scaling((2.0, 2.0, 2.0)))
    moved = moved_object(source, matrix, cancelled=NeverCancelled())
    result = placement.bind_surface(
        spec,
        values,
        {moved.id: moved},
        {moved.id: "scaled"},
        ask=lambda *_: pytest.fail("Eindeutiger Bezug fragt nicht"),
        announce=None,
        cancelled=NeverCancelled(),
    )
    assert result.placed is not None
    expected = moved_points(np.asarray([hit.point]), matrix)[0]
    normal = turned(np.asarray(hit.normal), matrix) / 2.0
    assert result.placed.point == pytest.approx(expected, abs=1e-6)
    assert result.placed.normal == pytest.approx(normal, abs=1e-6)


def _unrecognised_bound_box():
    """Analytischer Quader, dessen Fläche absichtlich keinen Merkmalsnamen trägt."""
    from app.core.types import IDENTITY_FRAME, SceneObject

    load_operations()
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 10.0)))
    source = SceneObject(id="obj_1", name="Träger", mesh=mesh, frame=IDENTITY_FRAME)
    hit = placement.at_point(placement.prepare_surface(mesh, _top(mesh), {}), (-12.0, -6.0, 5.0))
    spec = REGISTRY.get("create_box")
    return source, spec, placement.bound_surface_values(spec, source, hit)


def _a_top_that_is_flat_only_from_its_middle():
    """Oberseite aus drei Feldern, die nur von der Mitte aus eine Ebene bilden.

    Die Höhen der vier Eckreihen liegen 0,8 µm auseinander, unter der
    Ebenengrenze ``EPS_GEOM`` (1 µm) von der Mitte, darüber von einem Ende aus
    — wie die Gleitkommaspuren einer eingelesenen STL. Vom mittleren Feld B
    gewachsen umfasst die Fläche A, B und C, von A aus nur A und B, von C aus
    nur B und C. Die Dreiecke von A und C stehen vor denen von B. Nur die
    Oberseite: Gefragt wird die Fläche, nicht der Körper darunter.
    """
    lift = 0.8e-6
    xs = (0.0, 10.0, 20.0, 30.0)
    heights = (lift, 0.0, 0.0, lift)
    vertices = [(x, y, h) for x, h in zip(xs, heights, strict=True) for y in (0.0, 10.0)]

    def at(column, row):
        return column * 2 + row

    faces = []
    for column in (0, 2, 1):  # A, C, dann B
        a, b = at(column, 0), at(column + 1, 0)
        c, d = at(column + 1, 1), at(column, 1)
        faces += [(a, b, c), (a, c, d)]
    mesh = trimesh.Trimesh(np.asarray(vertices), np.asarray(faces), process=False)
    return MeshData.of(mesh)


def test_surface_binding_finds_the_face_it_was_saved_on_and_does_not_ask():
    """Die Bindung wächst die Fläche vom gespeicherten Punkt aus, wie das Setzen.

    Am echten Fenster (Fensterabnahme 04.10.2026, RM-396) fragte ein an die
    Schrägfläche des *Wedge-Lock* angesetzter Quader schon bei der ersten
    Auswertung „Mehrere Kanten passen zum gespeicherten Bezug“ — und jede Wahl
    endete mit „Diese Bezüge fehlen oder liegen zu parallel“. Gesetzt war von
    dem Dreieck unter dem Punkt aus; gebunden wurde vom ersten Dreieck der
    Liste aus, dessen Fläche den Punkt enthielt, aber nicht die ganze war.
    """
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import IDENTITY_FRAME, SceneObject

    load_operations()
    mesh = _a_top_that_is_flat_only_from_its_middle()
    source = SceneObject(id="obj_1", name="Träger", mesh=mesh, frame=IDENTITY_FRAME)
    middle = 5  # das zweite Dreieck von B
    prepared = placement.prepare_surface(mesh, middle, {})
    assert len(prepared.face_indices) == 6, "die mittlere Fläche umfasst alle drei Felder"
    hit = placement.at_point(prepared, (15.0, 4.0, 0.0))
    spec = REGISTRY.get("create_box")
    values = placement.bound_surface_values(spec, source, hit)
    binding = placement.bind_surface(
        spec,
        values,
        {source.id: source},
        {source.id: "same"},
        ask=lambda *_: pytest.fail("Am unveränderten Träger ist der Bezug eindeutig"),
        announce=None,
        cancelled=NeverCancelled(),
    )
    assert binding.placed is not None
    assert binding.placed.point == pytest.approx(hit.point)
    assert [edge.distance for edge in binding.placed.edges] == pytest.approx(
        [edge.distance for edge in hit.edges]
    )
    assert not binding.answers


def test_a_reference_on_one_of_two_collinear_edges_binds_without_asking():
    """Zwei Kantenstücke auf einer Geraden sind zwei Kanten, keine Wahl.

    Am *Wedge-Lock* (Fensterabnahme 04.10.2026, RM-403) lag der zweite Bezug
    eines Schraublochs auf einem von zwei kurzen Randstücken derselben Geraden
    links und rechts der Aussparung. Die Bindung prüfte nur den Abstand quer zur
    Kante und fragte beim ersten Auswerten „Mehrere Kanten passen zum
    gespeicherten Bezug“ — gespeichert war aber genau eines.
    """
    from shapely.geometry import Polygon

    from app.core.scene.cancel import NeverCancelled
    from app.core.types import IDENTITY_FRAME, SceneObject

    load_operations()
    notched = Polygon([(0, 0), (10, 0), (10, 10), (20, 10), (20, 0), (30, 0), (30, 20), (0, 20)])
    mesh = MeshData.of(trimesh.creation.extrude_polygon(notched, 5.0))
    source = SceneObject(id="obj_1", name="Träger", mesh=mesh, frame=IDENTITY_FRAME)
    prepared = placement.prepare_surface(mesh, _top(mesh), {})
    hit = placement.at_point(prepared, (25.0, 2.0, 5.0))
    front = [
        edge for edge in prepared.edges if abs(edge.start[1]) < 1e-9 and abs(edge.end[1]) < 1e-9
    ]
    assert len(front) == 2, "links und rechts der Aussparung je ein Stück der Vorderkante"
    assert any(abs(edge.inward[1] - 1.0) < 1e-9 for edge in hit.edges), (
        "ein Bezug ist die Vorderkante"
    )
    spec = REGISTRY.get("create_box")
    values = placement.bound_surface_values(spec, source, hit)
    binding = placement.bind_surface(
        spec,
        values,
        {source.id: source},
        {source.id: "same"},
        ask=lambda *_: pytest.fail("Gespeichert ist genau ein Stück der Vorderkante"),
        announce=None,
        cancelled=NeverCancelled(),
    )
    assert binding.placed is not None
    assert binding.placed.point == pytest.approx(hit.point)
    assert not binding.answers


def test_the_second_reference_is_the_side_across_not_a_facet_of_the_rounded_corner():
    """An einer Platte mit gerundeten Ecken stehen die Maße links und unten.

    Am echten Fenster (Fensterabnahme 04.10.2026, RM-403) standen beim
    Magnet am Tray und beim Schraubloch am Wedge-Lock beide Felder an
    derselben Kante: Die nächste unabhängige Kante war ein Facettenstück der
    Rundung, „Außenkante 4“ oder „Außenkante 56“, nicht die Seite quer dazu.
    """
    from shapely.geometry import box

    rounded = box(5.0, 5.0, 35.0, 25.0).buffer(5.0, quad_segs=8)
    plate = trimesh.creation.extrude_polygon(rounded, 5.0)
    mesh = MeshData.of(plate)
    top = _top(mesh)
    prepared = placement.prepare_surface(mesh, top, {})
    hit = placement.at_point(prepared, (1.0, 12.0, 5.0))
    inward = [np.round(np.asarray(edge.inward), 6).tolist() for edge in hit.edges]
    assert inward[0] == pytest.approx([1.0, 0.0, 0.0]), "erst die nahe linke Kante"
    assert inward[1] == pytest.approx([0.0, 1.0, 0.0]), f"dann die Unterkante, nicht {inward[1]}"
    assert hit.edges[1].distance == pytest.approx(12.0)


def test_surface_binding_saves_an_explicit_new_face_and_asks_only_once():
    """Zwei neue parallele Flächen verlangen eine Wahl; der gewählte Träger bleibt gespeichert."""
    from dataclasses import replace

    from app.core.scene.cancel import NeverCancelled

    source, spec, values = _unrecognised_bound_box()
    first, second = source.mesh.raw.copy(), source.mesh.raw.copy()
    first.vertices[:, 2] += 2.0
    second.vertices[:, 2] += 22.0
    changed = replace(source, mesh=MeshData.of(trimesh.util.concatenate((first, second))))
    asked, announced = [], []

    def choose(question, choices):
        asked.append((question, choices))
        return choices[-1]

    result = placement.bind_surface(
        spec,
        values,
        {source.id: changed},
        {source.id: "two"},
        ask=choose,
        announce=announced.append,
        cancelled=NeverCancelled(),
    )
    assert len(asked) == 1 and announced[0] and announced[-1] == ()
    assert result.answers and result.placed is not None
    repeated = placement.bind_surface(
        spec,
        {**values, **result.answers},
        {source.id: changed},
        {source.id: "two"},
        ask=lambda *_: pytest.fail("Die ausdrückliche Wahl gilt weiter"),
        announce=None,
        cancelled=NeverCancelled(),
    )
    assert repeated.placed is not None
    assert repeated.placed.point == pytest.approx(result.placed.point)
    assert not repeated.answers


@pytest.mark.parametrize("fault", ["normal", "edge", "inward", "frame", "radius", "version"])
def test_surface_binding_rejects_invalid_saved_geometry_with_a_suggestion(fault):
    """Beschädigte Projektdaten erzeugen weder NaN-Geometrie noch eine stille Ersatzwahl."""
    import json

    from app.core.scene.cancel import NeverCancelled

    source, spec, values = _unrecognised_bound_box()
    record = json.loads(values["surface_anchor"])
    if fault == "normal":
        record["normal"] = [0.0, 0.0, 0.0]
    elif fault == "edge":
        record["edges"][0]["end"] = record["edges"][0]["start"]
    elif fault == "inward":
        record["edges"][0]["inward"] = [0.0, 0.0, 0.0]
    elif fault == "frame":
        record["frame"][0] = record["frame"][1]
    elif fault == "radius":
        record["radius"] = float("nan")
    else:
        record["version"] = True
    values["surface_anchor"] = json.dumps(record)
    with pytest.raises(ValidationError) as failed:
        placement.bind_surface(
            spec,
            values,
            {source.id: source},
            {source.id: "old"},
            ask=lambda *_: pytest.fail("Ungültige Beschreibung fragt nicht"),
            announce=None,
            cancelled=NeverCancelled(),
        )
    assert failed.value.suggestions


def test_surface_binding_cancelled_during_reselection_publishes_nothing():
    """Abbruch bei der Frage räumt die Markierung auf und ändert keine Parameter."""
    from copy import deepcopy
    from dataclasses import replace

    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source, spec, values = _unrecognised_bound_box()
    first, second = source.mesh.raw.copy(), source.mesh.raw.copy()
    first.vertices[:, 2] += 2.0
    second.vertices[:, 2] += 22.0
    changed = replace(source, mesh=MeshData.of(trimesh.util.concatenate((first, second))))
    token, announced = CancelSignal(), []
    before = deepcopy(values)

    def cancel(_question, choices):
        token.cancel()
        return choices[0]

    with pytest.raises(OperationCancelled):
        placement.bind_surface(
            spec,
            values,
            {source.id: changed},
            {source.id: "two"},
            ask=cancel,
            announce=announced.append,
            cancelled=token,
        )
    assert announced[0] and announced[-1] == ()
    assert values == before


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("shape", ["cylinder", "sphere"])
def test_surface_binding_follows_a_curved_carrier(profile, kind, quality, shape):
    """Ein veränderter Radius trägt den Ansatz weiter auf der echten gekrümmten Haut."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import new_project

    if kind == "brep":
        exact_kernel()
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    creator = f"create_{'brep_' if kind == 'brep' else ''}{shape}"
    values = {"diameter": 20.0}
    if shape == "cylinder":
        values["height"] = 20.0
    history.apply("Runder Träger", [OperationDraft(op=creator, params=values)])
    before = evaluate(project.document, profile, quality=quality)
    assert before.complete
    source = before.scene.objects["obj_1"]
    feature = max(
        (entry for entry in source.features.values() if entry.kind != "face"),
        key=lambda entry: len(entry.face_indices),
    )
    hit = placement.surface_at_feature(source, feature, point=(10.0, 0.0, 10.0))
    assert not hit.planar
    box_name = "create_brep_box" if kind == "brep" else "create_box"
    assert placement.seats_on(REGISTRY.get(box_name), feature)
    bound = placement.bound_surface_values(REGISTRY.get(box_name), source, hit)
    bound.update(width=4.0, depth=4.0, height=4.0)
    history.apply("Aufsetzen", [OperationDraft(op=box_name, params=bound)])
    history.change_params(project.document.ops[0].id, {"diameter": 40.0})
    after = evaluate(project.document, profile, quality=quality)
    assert after.complete, after.scene.report.findings
    made = as_mesh_data(after.scene.objects["obj_2"].mesh)
    centre = np.asarray(made.raw.center_mass)
    carrier_centre = np.array((0.0, 0.0, 20.0 if shape == "sphere" else 10.0))
    expected = (
        carrier_centre
        + 2.0 * (np.asarray(hit.point) - (0.0, 0.0, 10.0))
        + 2.0 * np.asarray(hit.normal)
    )
    assert centre == pytest.approx(expected, abs=1e-6)
    if kind == "brep":
        assert float(np.linalg.norm(centre - carrier_centre)) == pytest.approx(22.0, abs=1e-6)
    assert made.is_watertight
    assert made.volume == pytest.approx(64.0, abs=1e-6)


@pytest.mark.parametrize("cache_kind", ["missing", "malformed", "read_only"])
def test_original_face_adjacency_survives_an_unavailable_private_cache(cache_kind):
    """Die exakten Originalkanten brauchen keine bestimmte private Cacheform."""
    from types import SimpleNamespace

    vertices = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)])
    raw = SimpleNamespace(faces=np.array([(0, 1, 2), (3, 4, 5)]))
    if cache_kind != "missing":
        raw._cache = SimpleNamespace(
            verify=lambda: None, cache=None if cache_kind == "malformed" else {}
        )
    assert placement._welded_adjacency(raw, vertices).tolist() == [[0, 1]]


def test_original_face_adjacency_cache_follows_mesh_changes():
    """Ein Treffer wird wiederverwendet, ein neuer echter Spalt nicht überbrückt."""
    raw = trimesh.Trimesh(
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
        faces=[(0, 1, 2), (3, 4, 5)],
        process=False,
    )
    first = placement._welded_adjacency(raw, raw.vertices)
    assert first.tolist() == [[0, 1]]
    assert placement._welded_adjacency(raw, raw.vertices) is first
    raw.vertices[3, 0] += 0.001
    assert placement._welded_adjacency(raw, raw.vertices).tolist() == []


@pytest.mark.parametrize("welded", [True, False])
def test_the_welded_adjacency_reads_the_body_numbering_and_answers_as_before(welded, monkeypatch):
    """Über die Punktnummer des Körpers dieselben Paare wie über die Koordinaten (RM-232).

    Bis zum 25.09.2026 sortierte die Nachbarschaft die Ecken als Zeilen
    (``np.unique(…, axis=0)``) — dieselbe Auskunft, die ``vertex_rank`` im
    Cache des Netzes schon hält. Geschweißt beantwortet die Kantenzählung
    die Frage ohne eigene Kantensuche; ungeschweißt (jedes STL-Dreieck mit
    eigenen Ecken) trägt die Punktnummer die Orte. Verglichen wird gegen die
    alte Rechnung, als Menge — die Reihenfolge der Paare sagt nichts.
    """
    from pathlib import Path

    from app.core.geom.mesh import unique_edges
    from app.core.perceive.features import vertex_rank

    raw = trimesh.load_mesh(
        Path(__file__).parent / "data" / "meshes" / "plate_countersunk.stl", process=welded
    )
    vertices = np.asarray(raw.vertices, dtype=np.float64)
    _, inverse = np.unique(vertices, axis=0, return_inverse=True)
    assert np.array_equal(vertex_rank(raw), inverse.reshape(-1)), "dieselbe Nummerierung"
    faces = inverse.reshape(-1)[np.asarray(raw.faces, dtype=np.int64)]
    _, edge_ids = unique_edges(
        faces[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), return_inverse=True
    )
    edge_ids = np.asarray(edge_ids, dtype=np.int64).reshape(-1)
    order = np.argsort(edge_ids, kind="stable")
    before = (order[np.bincount(edge_ids)[edge_ids[order]] == 2] // 3).reshape(-1, 2)
    if welded:
        monkeypatch.setattr(
            placement, "unique_edges", lambda *_a, **_k: pytest.fail("eigene Kantensuche")
        )

    pairs = placement._welded_adjacency(raw, vertices)

    assert len(before) and len(pairs) == len(before)
    assert set(map(tuple, pairs.tolist())) == set(map(tuple, before.tolist()))
    assert (pairs[:, 0] < pairs[:, 1]).all(), "das kleinere Dreieck zuerst"


@pytest.mark.parametrize("slotted", [False, True])
def test_blind_feature_from_below_finds_its_actual_mouth(slotted):
    """Die kanonisch positive Achse verlegt die Mündung nicht auf den Sacklochboden."""
    edit = exact_kernel()
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import detect

    body = edit.box(40.0, 30.0, 10.0)
    values = {
        "position": (0.0, 0.0, 2.0),
        "direction": (0.0, 0.0, -1.0),
        "diameter": 6.0,
        "depth": 4.0,
    }
    body = (
        edit.slot_bore(body, **values, length=16.0, angle_deg=0.0, overlap=0.0)
        if slotted
        else edit.cut_bore(body, **values)
    )
    mesh = as_mesh_data(body)
    found = detect(mesh)
    feature = next(f for f in found.values() if f.kind == ("slot" if slotted else "hole"))
    seat = placement.seat_of(mesh, feature, found)
    assert seat is not None
    prepared, mouth = seat
    assert mouth[2] == pytest.approx(0.0, abs=0.01)
    assert sorted(
        edge.distance for edge in placement.at_point(prepared, mouth).edges
    ) == pytest.approx([15.0, 20.0])


def test_slot_mouth_preview_keeps_its_full_width_and_length(profile):
    """Die Mündung eines langen Langlochs behält beide Enden und die volle Breite."""
    from app.core.units import MAX_FACET_SAG

    load_operations()
    tool = placement.prepare_tool(
        REGISTRY.get("drill_hole"),
        {
            "diameter": 5.0,
            "slotted": True,
            "slot_length": 20.0,
            "slot_angle": 0.0,
            "compensate": False,
        },
        profile,
    )
    outline = np.asarray(placement.mouth_outline(tool))
    assert outline.shape[0] >= 4
    assert np.ptp(outline, axis=0) == pytest.approx([20.0, 5.0], abs=2.0 * MAX_FACET_SAG)


@pytest.mark.parametrize("angle", [0.0, 90.0])
@pytest.mark.parametrize("compensate", [False, True])
@pytest.mark.parametrize(
    "op,width", [("resize_hole", 8.0), ("slot_hole", 8.0), ("slot_hole", None)]
)
def test_existing_slot_preview_keeps_direction_travel_and_requested_width(
    profile, angle, compensate, op, width
):
    """Breitenänderung erhält den Weg; ein Langlochauftrag zeigt seine Zielbreite."""
    from app.core.types import SceneObject
    from app.core.units import MAX_FACET_SAG

    load_operations()
    feature = Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        params={
            "diameter": 6.0,
            "length": 20.0,
            "travel": 14.0,
            "depth": 8.0,
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "direction": (math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0.0),
        },
    )
    source = SceneObject(
        id="obj_1",
        name="Langlochplatte",
        mesh=MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0))),
        features={feature.id: feature},
    )
    values = {"at_feature": feature.id, "diameter": width, "compensate": compensate}
    if op == "slot_hole":
        values.update(slot_length=24.0, slot_angle=angle)
    tool = placement.prepare_tool(REGISTRY.get(op), values, profile, source=source)
    outline = np.asarray(placement.mouth_outline(tool))
    cut = (
        6.0
        if width is None
        else width + (profile.material.hole_compensation if compensate else 0.0)
    )
    length = 14.0 + cut if op == "resize_hole" else 24.0
    expected = (length, cut) if angle < 45.0 else (cut, length)
    assert np.ptp(outline, axis=0) == pytest.approx(expected, abs=2.0 * MAX_FACET_SAG)


@pytest.mark.parametrize("width", [None, 8.0])
def test_a_slot_pulled_back_to_its_width_previews_the_round_bore(profile, width):
    """Länge = Breite zeigt die runde Bohrung, zu der das Langloch zurückgeht.

    Ohne diese Vorschau blieb *Übernehmen* nach dem Einrasten grau: Das
    Werkzeug fragte ``slot_travel``, das eine Länge unter der Mindestlänge
    ablehnt, und ohne Werkzeug gibt die Platzierung den Knopf nicht frei
    (Prüfstand am Scraper-Modell, 24.09.2026). Langloch Ø 6 auf 20 mm; die
    Mündung ist danach ein Kreis der gewünschten Breite.
    """
    from app.core.types import SceneObject
    from app.core.units import MAX_FACET_SAG

    load_operations()
    feature = Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        params={
            "diameter": 6.0,
            "length": 20.0,
            "travel": 14.0,
            "depth": 8.0,
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "direction": (1.0, 0.0, 0.0),
        },
    )
    source = SceneObject(
        id="obj_1",
        name="Langlochplatte",
        mesh=MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0))),
        features={feature.id: feature},
    )
    cut = 6.0 if width is None else width
    values = {
        "at_feature": feature.id,
        "diameter": width,
        "compensate": False,
        "slot_length": cut,
        "slot_angle": 0.0,
    }
    tool = placement.prepare_tool(REGISTRY.get("slot_hole"), values, profile, source=source)
    outline = np.asarray(placement.mouth_outline(tool))
    assert np.ptp(outline, axis=0) == pytest.approx((cut, cut), abs=2.0 * MAX_FACET_SAG)


def test_two_real_edges_replace_the_triangulation_diagonal():
    """Eine Deckfläche hat vier Randkanten; die innere Diagonale taugt nicht als Bezug."""
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    hit = placement.at_point(prepared, (13.123456789, 8.0, 4.0))
    assert hit.planar
    assert len(prepared.edges) == 4
    assert len(hit.edges) == 2
    assert sorted(edge.distance for edge in hit.edges) == pytest.approx([6.876543211, 7.0])
    assert hit.point[0] == 13.123456789
    moved = placement.point_with_distances(prepared, hit, (2.0, 3.0))
    assert [edge.distance for edge in moved.edges] == pytest.approx([2.0, 3.0])
    assert moved.point[2] == pytest.approx(4.0)


def test_rotated_plate_keeps_its_real_plane_and_distances():
    """Abstände bleiben Millimeter in der Flächenebene, ohne Weltachsenrundung."""
    raw = trimesh.creation.box((40.0, 30.0, 8.0))
    face = _top(MeshData.of(raw))
    matrix = np.asarray(rotation("y", 37.0))
    raw.apply_transform(matrix)
    mesh = MeshData.of(raw)
    point = trimesh.transform_points([[13.0, 8.0, 4.0]], matrix)[0]
    prepared = placement.prepare_surface(mesh, face)
    hit = placement.at_point(prepared, tuple(point))
    assert hit.normal == pytest.approx(matrix[:3, 2])
    assert sorted(edge.distance for edge in hit.edges) == pytest.approx([7.0, 7.0])
    load_operations()
    values = placement.surface_values(REGISTRY.get("drill_hole"), hit)
    assert [values[key] for key in ("nx", "ny", "nz")] == pytest.approx(matrix[:3, 2])
    assert "axis" not in values
    assert values["anchor"] == "mouth"


def test_a_small_hole_is_not_filled_by_the_placement_patch():
    """Die Patchfläche bewahrt innere Konturen und bietet echte Bohrungsmittelpunkte."""
    from app.core.perceive.features import detect
    from tests.test_prepare import plate

    mesh = plate()
    face = _top(mesh)
    features = detect(mesh)
    hole = next(item for item in features.values() if item.kind == "hole")
    prepared = placement.prepare_surface(mesh, face, features)
    triangles = np.asarray(mesh.raw.triangles)[list(prepared.face_indices)]
    point = tuple(triangles[0].mean(axis=0))
    hit = placement.at_point(prepared, point)
    assert hole.id in {reference.feature_id for reference in hit.centres}
    # Ein konkreter innerer Ring des Korpus muss bei Punktversatz frei bleiben.
    assert len(prepared.area.interiors) > 0
    opening = np.asarray(prepared.area.interiors[0].coords).mean(axis=0)
    from app.core.sketch.planes import to_world

    with pytest.raises(ValidationError):
        placement.at_point(prepared, to_world(prepared.frame, tuple(opening)))


def test_curved_triangles_offer_no_invented_planar_dimensions():
    mesh = MeshData.of(trimesh.creation.icosphere(subdivisions=1, radius=20.0))
    prepared = placement.prepare_surface(mesh, 0)
    hit = placement.at_point(prepared, tuple(mesh.raw.triangles[0].mean(axis=0)))
    assert not hit.planar
    assert not hit.edges


def test_original_ray_hits_the_mesh_and_respects_clipping():
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    hit = placement.original_surface_hit(mesh, (0.0, 0.0, 20.0), (0.0, 0.0, -1.0))
    assert hit is not None and hit[1] == pytest.approx((0.0, 0.0, 4.0))
    assert hit[0] in placement.prepare_surface(mesh, _top(mesh)).face_indices
    clipped = placement.original_surface_hit(
        mesh,
        (0.0, 0.0, 20.0),
        (0.0, 0.0, -1.0),
        clip_origin=(0.0, 0.0, 0.0),
        clip_normal=(0.0, 0.0, -1.0),
    )
    assert clipped is not None and clipped[1] == pytest.approx((0.0, 0.0, -4.0))


def test_all_section_planes_filter_original_hits_without_inventing_caps():
    from app.core.geom.section import SectionPlane

    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    sections = (SectionPlane.along("z", 1.0), SectionPlane.along("z", -1.0).flipped())
    assert (
        placement.original_surface_hit(
            mesh, (0.0, 0.0, 20.0), (0.0, 0.0, -1.0), clip_planes=sections
        )
        is None
    )
    side = placement.original_surface_hit(
        mesh, (50.0, 0.0, 0.0), (-1.0, 0.0, 0.0), clip_planes=sections
    )
    assert side is not None and side[1] == pytest.approx((20.0, 0.0, 0.0))


def test_original_ray_preserves_face_ids_across_blocks_and_can_be_cancelled(monkeypatch):
    from app.core.errors import OperationCancelled

    mesh = MeshData.of(trimesh.creation.box(extents=(40.0, 30.0, 8.0)))
    expected = placement.original_surface_hit(mesh, (13.0, 8.0, 20.0), (0.0, 0.0, -1.0))
    monkeypatch.setattr(placement, "PICK_TRIANGLE_BLOCK", 3)
    checks = []
    actual = placement.original_surface_hit(
        mesh,
        (13.0, 8.0, 20.0),
        (0.0, 0.0, -1.0),
        check_cancelled=lambda: checks.append(True),
    )
    assert actual is not None and expected is not None
    assert actual[0] == expected[0]
    assert actual[1] == pytest.approx(expected[1])
    assert len(checks) >= 4

    def stop():
        raise OperationCancelled()

    with pytest.raises(OperationCancelled):
        placement.original_surface_hit(
            mesh,
            (13.0, 8.0, 20.0),
            (0.0, 0.0, -1.0),
            check_cancelled=stop,
        )


def test_editing_distances_cannot_put_the_point_into_a_cutout():
    from shapely.geometry import Polygon

    outline = Polygon(
        [(-20, -15), (20, -15), (20, 15), (-20, 15)], holes=[[(-2, -2), (2, -2), (2, 2), (-2, 2)]]
    )
    mesh = MeshData.of(trimesh.creation.extrude_polygon(outline, 8.0))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    hit = placement.at_point(prepared, (18.0, 13.0, 8.0))
    # Ziel: genau die Mitte der Aussparung, aus denselben beiden Außenkanten.
    distances = tuple(
        float(np.dot(np.asarray((0.0, 0.0, 8.0)) - edge.start, edge.inward)) for edge in hit.edges
    )
    with pytest.raises(ValidationError, match="außerhalb"):
        placement.point_with_distances(prepared, hit, distances)
    assert hit.point == (18.0, 13.0, 8.0)


def test_repeated_point_moves_reuse_the_prepared_geometry(monkeypatch):
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    monkeypatch.setattr(placement, "_patch_faces", lambda *_: pytest.fail("topology recomputed"))
    for x in (-7.123456789, 0.0, 13.123456789):
        hit = placement.at_point(prepared, (x, 5.0, 4.0))
        assert hit.point == (x, 5.0, 4.0)


@pytest.mark.parametrize("normal", [(0.0, 0.0, -1.0), (0.3, -0.7, 0.6), (0.0, 0.0, 0.0)])
def test_text_preview_and_real_body_share_geometry_and_orientation(normal, profile):
    """Vorschau und Operation bauen denselben Körper — **mit allen Parametern**.

    Der Test stand hier schon, und er lief mit den Vorgaben: kein Schnitt, kein
    anderer Zeichensatz. Genau darum blieb unsichtbar, dass ``placement`` den
    Schnitt gar nicht durchreichte — die Vorschau zeigte den normalen, während
    die Operation den fetten baute (Fett ist rund anderthalbmal so breit).
    Seitdem stehen beide in ``values``, und ein vergessener Parameter fällt hier
    auf statt im Fenster.
    """
    from app.core.sketch.planes import frame_of
    from tests.helpers import run_operation as run

    load_operations()
    spec = REGISTRY.get("create_label")
    values = {
        "text": "L7",
        "size": 8.0,
        "depth": 0.7,
        "angle": 37.0,
        "font": "Liberation Serif",
        "style": "bold_italic",
    }
    tool = placement.prepare_tool(spec, values, profile).mesh
    point = (3.123456789, -2.1, 8.0)
    frame = frame_of(normal if np.linalg.norm(normal) else (0.0, 0.0, 1.0), point)
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    matrix[:3, 3] = point
    expected = apply(tool, matrix)
    actual = (
        run(
            "create_label",
            None,
            profile,
            **values,
            x=point[0],
            y=point[1],
            z=point[2],
            nx=normal[0],
            ny=normal[1],
            nz=normal[2],
        )
        .outputs[0]
        .mesh
    )
    assert actual.volume == pytest.approx(expected.volume)
    assert np.asarray(actual.raw.vertices) == pytest.approx(expected.raw.vertices, abs=1e-12)

    # **Und der Schnitt macht wirklich einen Unterschied.** Ohne diese Zeile
    # wäre der Test auch dann grün, wenn beide Seiten denselben falschen
    # nähmen — zwei gleich fehlerhafte Wege sehen aus wie Übereinstimmung.
    plain = placement.prepare_tool(spec, {**values, "style": "regular"}, profile).mesh
    assert plain.volume < 0.9 * tool.volume, (plain.volume, tool.volume)


def _placed_like_the_cut(tool, normal, position):
    """Das Vorschauwerkzeug in den Rahmen der Fläche gelegt, wie die Operation es tut.

    Seit RM-274 wandert das Werkzeug in die Welt, statt dass der Körper in den
    Rahmen der Bohrung wandert; die Boolesche bekommt es also in Weltlage. Die
    Richtung wird wie in ``prepare.drill`` über ``math.hypot`` normiert.
    """
    from app.core.geom.transform import moved
    from app.core.sketch.planes import frame_of

    length = math.hypot(*normal)
    frame = frame_of(tuple(value / length for value in normal), position)
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    matrix[:3, 3] = position
    placed = tool.raw.copy()
    moved(placed, matrix)
    return np.asarray(placed.vertices)


def test_drill_preview_and_actual_cut_share_the_same_local_tool(profile, monkeypatch):
    import app.core.geom.prepare as module

    load_operations()
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    values = {"diameter": 4.0, "depth": 3.0, "compensate": False}
    preview = placement.prepare_tool(REGISTRY.get("drill_hole"), values, profile).mesh
    captured = []
    original = module.boolean

    def record(kind, meshes, **kwargs):
        captured.append(meshes[1])
        return original(kind, meshes, **kwargs)

    monkeypatch.setattr(module, "boolean", record)
    module.drill(
        mesh, position=(0.0, 0.0, 4.0), axis="z", normal=(0.3, 0.4, 0.5), profile=profile, **values
    )
    # Die schräge Mündungsebene geht nur durch die Stelle, nicht durch die
    # Oberseite: Kein Ende liegt in einer Fläche, das Werkzeug bleibt das der Vorschau.
    assert captured[0].raw.vertices == pytest.approx(
        _placed_like_the_cut(preview, (0.3, 0.4, 0.5), (0.0, 0.0, 4.0)), abs=1e-12
    )


def test_only_real_placement_operations_accept_surface_values():
    load_operations()
    assert placement.supports_surface_placement(REGISTRY.get("drill_hole"))
    assert placement.supports_surface_placement(REGISTRY.get("insert_screw_hole"))
    assert not placement.supports_surface_placement(REGISTRY.get("translate_object"))


@pytest.mark.parametrize("with_feature", [False, True])
def test_circle_facets_never_become_two_linear_measurement_references(with_feature):
    from app.core.geom.boolean import boolean

    plate = MeshData.of(trimesh.creation.box((20.0, 20.0, 4.0)))
    cutter = MeshData.of(trimesh.creation.cylinder(radius=0.25, height=10.0, sections=48))
    mesh = boolean("difference", [plate, cutter]).mesh
    feature = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "depth": 4.0, "diameter": 0.5},
    )
    prepared = placement.prepare_surface(
        mesh, _top(mesh), {feature.id: feature} if with_feature else {}
    )
    assert len(prepared.edges) == 4
    hit = placement.at_point(prepared, (0.3, 0.3, 2.0))
    assert len(hit.edges) == 2
    assert all(abs(edge.distance) > 9.0 for edge in hit.edges)
    if with_feature:
        assert hit.centres[0].point == pytest.approx((0.0, 0.0, 2.0))
    else:
        assert not hit.centres


def test_small_straight_cutout_edges_are_preserved():
    from shapely.geometry import Polygon

    outline = Polygon(
        [(-10, -10), (10, -10), (10, 10), (-10, 10)],
        holes=[[(-0.1, -0.1), (0.1, -0.1), (0.1, 0.1), (-0.1, 0.1)]],
    )
    mesh = MeshData.of(trimesh.creation.extrude_polygon(outline, 2.0))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    assert len(prepared.edges) == 8
    assert min(
        np.linalg.norm(np.asarray(edge.start) - edge.end) for edge in prepared.edges
    ) == pytest.approx(0.2)


def test_reference_choice_keeps_the_point_and_survives_crossing_the_plate():
    """Eine ausdrücklich gewählte ferne Kante bleibt beim Zug dieselbe."""
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    original = placement.at_point(prepared, (15.0, 10.0, 4.0))
    opposite = next(edge for edge in prepared.edges if np.allclose(edge.inward, (1, 0, 0)))
    index = next(i for i, edge in enumerate(original.edges) if abs(edge.inward[0]) > 0.9)
    chosen = placement.with_reference(prepared, original, index, opposite.id)
    assert chosen.point == original.point
    assert chosen.edges[index].distance == pytest.approx(35.0)
    moved = placement.at_point(prepared, (-15.0, -10.0, 4.0), references=chosen.edges)
    assert [edge.id for edge in moved.edges] == [edge.id for edge in chosen.edges]
    assert moved.edges[index].distance == pytest.approx(5.0)
    with pytest.raises(ValidationError):
        placement.with_reference(prepared, original, index, "missing_edge")


def test_held_references_skip_the_ranking_of_every_edge(monkeypatch):
    """Mit festgehaltenen Bezügen wird keine Kante gerankt und keine kopiert.

    Das Loslassen des Platzierungsgriffs ruft ``at_point`` mit den Bezügen
    der Stelle im Qt-Hauptthread; die Rangfolge über alle Randkanten wurde
    dort bis zum 22.09.2026 gebildet und verworfen — 85 ms an einer Platte
    mit 2 452 Randkanten (RM-200). Ohne Bezüge bleibt die Wahl, wie sie war:
    die zwei nächsten unabhängigen Kanten, und nur sie tragen einen Abstand.
    """
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    original = placement.at_point(prepared, (15.0, 10.0, 4.0))
    assert sorted(edge.distance for edge in original.edges) == pytest.approx([5.0, 5.0])

    checks = []
    real = placement._independent

    def counted(frame, edges):
        checks.append(len(edges))
        return real(frame, edges)

    monkeypatch.setattr(placement, "_independent", counted)
    moved = placement.at_point(prepared, (-15.0, -10.0, 4.0), references=original.edges)
    # Geprüft wird nur noch das Paar selbst (``_checked_references``).
    assert checks == [2], "festgehaltene Bezüge brauchen keine Rangfolge"
    assert [edge.id for edge in moved.edges] == [edge.id for edge in original.edges]
    assert sorted(edge.distance for edge in moved.edges) == pytest.approx([25.0, 35.0])

    again = placement.at_point(prepared, (15.0, 10.0, 4.0))
    assert again == original


def test_a_clean_face_is_united_from_its_rim_and_matches_the_general_union(monkeypatch):
    """Die Fläche eines sauberen Netzes entsteht ohne ``union_all`` — und gleich.

    Bis zum 22.09.2026 ging jedes Dreieck der gewählten Fläche als eigenes
    Polygon durch ``union_all``: 17 bis 28 s an der Oberseite der fünfmal
    unterteilten ``plate_holes.stl``, bevor Griff und Maße erschienen
    (RM-200). Der Rand eines sauberen Netzes kommt mit Zählen aus.
    Verglichen wird mit der allgemeinen Vereinigung, Punkt für Punkt nach
    Normalisierung.
    """
    from pathlib import Path

    import shapely

    corpus = Path(__file__).parent / "data/meshes/plate_holes.stl"
    mesh = MeshData.of(trimesh.load(corpus, force="mesh"))
    face = _top(mesh)
    indices, _planar = placement._patch_faces(mesh, face)
    frame = placement.prepare_surface(mesh, face).frame
    relative = np.asarray(mesh.raw.triangles)[list(indices)] - frame.origin
    xy = np.stack((relative @ frame.x_axis, relative @ frame.y_axis), axis=-1)
    reference = shapely.union_all([shapely.Polygon(corners) for corners in xy])

    def refused(*_args, **_kwargs):
        raise AssertionError("union_all an einem sauberen Netz")

    monkeypatch.setattr(shapely, "union_all", refused)
    fast = placement.prepare_surface(mesh, face)
    assert len(fast.area.interiors) == 4
    assert shapely.normalize(fast.area).equals_exact(shapely.normalize(reference), 0.0)


def test_overlapping_or_t_junction_triangles_fall_back_to_the_general_union():
    """Was keine saubere Überdeckung ist, vereinigt weiter ``union_all``.

    Zwei überlappende Dreiecke und eine T-Kreuzung — eine Kante, an der
    auf der anderen Seite zwei kürzere liegen: Der Rand setzt geteilte
    Ecken voraus, und sein Ergebnis wird deshalb geprüft, nicht geglaubt.
    """
    import shapely

    overlapping = np.array(
        [[[0.0, 0.0], [4.0, 0.0], [0.0, 4.0]], [[1.0, 1.0], [5.0, 1.0], [1.0, 5.0]]]
    )
    t_junction = np.array(
        [
            [[0.0, 0.0], [4.0, 0.0], [0.0, 4.0]],
            [[4.0, 0.0], [2.0, 2.0], [4.0, 4.0]],
            [[2.0, 2.0], [0.0, 4.0], [4.0, 4.0]],
        ]
    )
    for triangles in (overlapping, t_junction):
        general = shapely.union_all([shapely.Polygon(corners) for corners in triangles])
        area = placement._patch_area(triangles)
        assert area.is_valid and area.geom_type == "Polygon"
        assert shapely.normalize(area).equals_exact(shapely.normalize(general), 1e-12)
    assert placement._boundary_area(overlapping) is None
    assert placement._boundary_area(t_junction) is None


@pytest.mark.parametrize("angle, accepted", [(15.0, True), (5.0, False)])
@pytest.mark.parametrize("size", [1.0, 1000.0])
@pytest.mark.parametrize("tilt", [0.0, 37.0])
def test_reference_condition_is_independent_of_size_and_world_rotation(angle, accepted, size, tilt):
    """Die Bediengrenze betrifft das Bezugspaar, weder Größe noch Weltachsen."""
    from dataclasses import replace

    raw = trimesh.creation.box((size, size, size))
    face = _top(MeshData.of(raw))
    matrix = np.asarray(rotation("y", tilt))
    raw.apply_transform(matrix)
    prepared = placement.prepare_surface(MeshData.of(raw), face)
    frame = prepared.frame
    one = np.asarray(frame.x_axis)
    two = math.cos(math.radians(angle)) * one + math.sin(math.radians(angle)) * np.asarray(
        frame.y_axis
    )
    origin = np.asarray(frame.origin)
    edges = tuple(
        placement.EdgeReference(
            str(index), tuple(origin), tuple(origin + np.cross(frame.normal, normal)), tuple(normal)
        )
        for index, normal in enumerate((one, two))
    )
    prepared = replace(prepared, edges=edges)
    point = tuple(trimesh.transform_points([[0.0, 0.0, size / 2]], matrix)[0])
    surface = placement.at_point(prepared, point)
    assert (len(surface.edges) == 2) is accepted
    if not accepted:
        with pytest.raises(ValidationError):
            placement.with_reference(prepared, surface, 1, edges[1].id)


def test_inner_reference_is_explicit_and_automatic_references_prefer_the_outer_boundary():
    """Der winzige echte Innenausschnitt bleibt wählbar, die Außenmaße sind die Vorgabe."""
    from shapely.geometry import Polygon

    outline = Polygon(
        [(-10, -10), (10, -10), (10, 10), (-10, 10)],
        holes=[[(0, 0), (0.2, 0), (0.2, 0.2), (0, 0.2)]],
    )
    mesh = MeshData.of(trimesh.creation.extrude_polygon(outline, 2.0))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    surface = placement.at_point(prepared, (0.4, 0.4, 2.0))
    assert all(edge.kind == "outer" for edge in surface.edges)
    inner = next(
        edge
        for edge in prepared.edges
        if edge.kind == "inner" and abs(np.dot(edge.inward, surface.edges[1].inward)) < 0.1
    )
    chosen = placement.with_reference(prepared, surface, 0, inner.id)
    assert chosen.edges[0].id == inner.id
    assert chosen.point == surface.point


@pytest.mark.parametrize("native", [False, True])
def test_real_slot_offers_its_measured_centre_and_axis(native):
    """Beide Körperarten liefern die Langlochachse aus der tatsächlichen Richtung."""
    edit = exact_kernel()
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import detect

    body = edit.slot_bore(
        edit.box(40.0, 30.0, 8.0),
        position=(0.0, 0.0, 4.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=12.0,
        length=16.0,
        angle_deg=30.0,
        overlap=0.0,
    )
    mesh = as_mesh_data(body)
    features = features_of(body) if native else detect(mesh)
    slot = next(feature for feature in features.values() if feature.kind == "slot")
    prepared = placement.prepare_surface(mesh, _top(mesh), features)
    centre = next(point for identifier, point in prepared.centres if identifier == slot.id)
    axis = next(edge for edge in prepared.edges if edge.id == f"axis_{slot.id}")
    assert centre == pytest.approx((0.0, 0.0, 8.0), abs=0.01)
    direction = np.asarray(axis.end) - axis.start
    assert np.linalg.norm(direction) == pytest.approx(16.0, abs=0.01)
    assert abs(
        direction @ np.asarray((math.cos(math.radians(30)), math.sin(math.radians(30)), 0))
    ) == pytest.approx(16.0, abs=0.01)
    nearby = placement.reference_candidates(prepared, centre, 0.1)
    assert (slot.id, "centre") in nearby
    assert (axis.id, "axis") in nearby
    assert (slot.id, "centre") in placement.reference_candidates(
        prepared, (0.0, 0.0, 0.0), 0.1, ray=((0.0, 0.0, 20.0), (0.0, 0.0, -1.0))
    )
    assert not placement.reference_candidates(
        prepared, (0.0, 0.0, 12.0), 0.1, ray=((0.0, 0.0, 20.0), (0.0, 0.0, -1.0))
    )
    assert not placement.reference_candidates(
        prepared, (0.0, 0.0, 0.0), 0.1, ray=((0.0, 0.0, -20.0), (0.0, 0.0, 1.0))
    )


def test_stale_reference_geometry_is_rejected_even_when_the_number_is_reused():
    """Eine neue edge_0 ist kein Nachweis für die alte reale Kante."""
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    surface = placement.at_point(prepared, (15.0, 10.0, 4.0))
    shifted = mesh.raw.copy()
    shifted.apply_translation((1.0, 0.0, 0.0))
    other = MeshData.of(shifted)
    updated = placement.prepare_surface(other, _top(other))
    with pytest.raises(ValidationError):
        placement.at_point(updated, (15.0, 10.0, 4.0), references=surface.edges)


def test_reference_extension_is_not_claimed_as_a_wall_distance():
    """Außerhalb der endlichen Kante ist nur die gestrichelte Verlängerung ein Bezug."""
    edge = placement.EdgeReference("edge", (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert placement.reference_extension(edge, (1.0, 3.0, 0.0)) is None
    assert placement.reference_extension(edge, (5.0, 3.0, 0.0)) == (
        (2.0, 0.0, 0.0),
        (5.0, 0.0, 0.0),
    )


def test_seated_slot_preserves_other_openings_and_their_real_references():
    """Nur die eigene Öffnung wird zum Platzieren gefüllt; fremde Ausschnitte bleiben frei."""
    edit = exact_kernel()
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data

    body = edit.box(50.0, 30.0, 8.0)
    for x in (-12.0, 12.0):
        body = edit.slot_bore(
            body,
            position=(x, 0.0, 4.0),
            direction=(0.0, 0.0, 1.0),
            diameter=4.0,
            depth=12.0,
            length=8.0,
            angle_deg=0.0,
            overlap=0.0,
        )
    features = features_of(body)
    slots = sorted(
        (feature for feature in features.values() if feature.kind == "slot"),
        key=lambda feature: feature.params["centre"][0],
    )
    prepared, mouth = placement.seat_of(as_mesh_data(body), slots[0], features)
    surface = placement.at_point(prepared, mouth)
    assert f"axis_{slots[0].id}" not in {edge.id for edge in prepared.edges}
    assert f"axis_{slots[1].id}" in {edge.id for edge in prepared.edges}
    assert len(surface.centres) == 1
    with pytest.raises(ValidationError):
        placement.at_point(prepared, surface.centres[0].point)


def test_a_pin_on_the_underside_uses_its_material_base(profile):
    from app.core.geom.boolean import boolean
    from app.core.geom.prepare_ops import feature_placement_geometry
    from app.core.types import SceneObject

    load_operations()
    plate = trimesh.creation.box((20.0, 20.0, 4.0))
    pin = trimesh.creation.cylinder(radius=2.0, height=6.0, sections=48)
    pin.apply_translation((0.0, 0.0, -4.0))
    mesh = boolean("union", [MeshData.of(plate), MeshData.of(pin)]).mesh
    feature = Feature(
        id="pin_1",
        kind="pin",
        provenance="generated",
        params={"centre": (0.0, 0.0, -4.5), "axis": (0.0, 0.0, 1.0), "diameter": 4.0, "depth": 5.0},
    )
    source = SceneObject(id="obj_1", name="Zapfenplatte", mesh=mesh, features={feature.id: feature})
    geometry = feature_placement_geometry(source, feature, "move_feature")
    assert geometry.frame.normal == pytest.approx((0.0, 0.0, -1.0))
    assert geometry.frame.origin == pytest.approx((0.0, 0.0, -2.0))
    assert geometry.mesh.bounds.maximum[2] == pytest.approx(5.02)


@pytest.mark.parametrize("operation", ["move_feature", "duplicate_feature"])
def test_existing_feature_tool_matches_free_placement_and_preserves_ids(
    operation, profile, monkeypatch
):
    import app.core.geom.prepare_ops as module
    from app.core.geom.boolean import boolean
    from app.core.types import SceneObject
    from tests.helpers import run_operation as run

    load_operations()
    mesh = boolean(
        "difference",
        [
            MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0))),
            MeshData.of(trimesh.creation.cylinder(radius=1.5, height=12.0, sections=48)),
        ],
    ).mesh
    feature = Feature(
        id="hole_9",
        kind="hole",
        provenance="generated",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 3.0,
            "depth": 8.0,
            "through": True,
        },
    )
    source = SceneObject(id="obj_1", name="Platte", mesh=mesh, features={feature.id: feature})
    spec = REGISTRY.get(operation)
    target = MeshData.of(trimesh.creation.box((20.0, 20.0, 8.0)))
    prepared = placement.prepare_surface(target, _top(target))
    hit = placement.at_point(prepared, (7.0, 6.0, 4.0))
    values = placement.surface_values(spec, hit, feature=feature, source=source)
    tool = placement.prepare_tool(spec, values, profile, source=source, feature=feature).mesh
    captured = []
    original = module.boolean

    def record(kind, meshes, **kwargs):
        if kind == "difference":
            captured.append(meshes[1])
        return original(kind, meshes, **kwargs)

    monkeypatch.setattr(module, "boolean", record)
    result = run(operation, source, profile, **values).outputs[0]
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((hit.frame.x_axis, hit.frame.y_axis, hit.normal))
    matrix[:3, 3] = hit.point
    expected = apply(tool, matrix)
    assert captured[0].raw.vertices == pytest.approx(expected.raw.vertices, abs=1e-12)
    assert "hole_9" in result.features
    if operation == "duplicate_feature":
        assert "hole_10" in result.features
        assert result.features["hole_9"].params["centre"] == feature.params["centre"]
    else:
        assert result.features["hole_9"].params["centre"] == pytest.approx((7.0, 6.0, 0.0))


@pytest.mark.parametrize("operation", ["move_feature", "duplicate_feature"])
@pytest.mark.parametrize("chosen", [0, 1, 2])
def test_surface_placement_carries_the_complete_bore_chain(operation, chosen, profile):
    from app.core.geom.prepare_ops import feature_placement_geometry
    from app.core.perceive.features import detect
    from app.core.perceive.relations import cavity_chains
    from app.core.types import SceneObject
    from tests.helpers import run_operation as run

    load_operations()
    outline = [
        [30.0, 0.0],
        [30.0, 10.0],
        [5.5, 10.0],
        [5.5, 8.5],
        [3.0, 6.0],
        [3.0, 0.0],
        [30.0, 0.0],
    ]
    mesh = MeshData.of(trimesh.creation.revolve(outline, sections=64))
    features = detect(mesh)
    chain = next(iter(cavity_chains(features, mesh)))
    assert len(chain) == 3
    feature = chain[chosen]
    source = SceneObject(id="obj_1", name="Senkbohrung", mesh=mesh, features=features)
    spec = REGISTRY.get(operation)
    geometry = feature_placement_geometry(source, feature, operation)
    assert geometry.frame.normal == pytest.approx((0.0, 0.0, 1.0))
    assert geometry.frame.origin[2] == pytest.approx(10.0)
    prepared = placement.prepare_surface(mesh, _top(mesh), features)
    hit = placement.at_point(prepared, (15.0, 0.0, 10.0))
    values = placement.surface_values(spec, hit, feature=feature, source=source)
    result = run(operation, source, profile, **values).outputs[0]
    assert result.mesh.raw.is_watertight
    assert all(identifier in result.features for identifier in features)
    if operation == "move_feature":
        assert result.mesh.volume == pytest.approx(mesh.volume, abs=0.02)
        assert [result.features[item.id].params["centre"][0] for item in chain] == pytest.approx(
            [15.0] * 3
        )
    else:
        assert len(result.features) == len(features) + 3
        assert mesh.volume - result.mesh.volume == pytest.approx(
            math.pi * (54.0 + 56.0 * 2.5 / 3.0 + 45.375), rel=0.01
        )
        assert all(
            result.features[item.id].params["centre"] == item.params["centre"] for item in chain
        )


def test_a_chain_moved_by_hand_leaves_no_scars_in_the_face(profile):
    """Versetzen per Klick räumt die Kappen des Stopfens ab wie der Zahlenweg.

    Der Zahlenweg tut es seit dem 23.09.2026 (``_without_scars``); am Klickweg
    fehlte es (Durchsicht 0.5.1): An dieser Senkbohrung wuchs der Körper je Zug
    um 260 Dreiecke, 768 → 1028 → 1288 nach zwei Zügen, 130 davon in der
    Oberseite — und mit ihnen jeder spätere Schritt.
    """
    from app.core.perceive.features import detect
    from app.core.perceive.relations import cavity_chains
    from app.core.types import SceneObject
    from tests.helpers import run_operation as run

    load_operations()
    outline = [
        [30.0, 0.0],
        [30.0, 10.0],
        [5.5, 10.0],
        [5.5, 8.5],
        [3.0, 6.0],
        [3.0, 0.0],
        [30.0, 0.0],
    ]
    mesh = MeshData.of(trimesh.creation.revolve(outline, sections=64))
    current = SceneObject(id="obj_1", name="Senkbohrung", mesh=mesh, features=detect(mesh))
    spec = REGISTRY.get("move_feature")
    for x in (15.0, -15.0):
        body = current.mesh
        bore = next(
            item
            for item in next(iter(cavity_chains(current.features, body)))
            if item.kind == "hole"
        )
        prepared = placement.prepare_surface(body, _top(body), current.features)
        hit = placement.at_point(prepared, (x, 0.0, 10.0))
        values = placement.surface_values(spec, hit, feature=bore, source=current)
        moved = run("move_feature", current, profile, **values).outputs[0].mesh
        current = SceneObject(id="obj_1", name="Senkbohrung", mesh=moved, features=detect(moved))
    assert current.mesh.raw.is_watertight
    assert current.mesh.volume == pytest.approx(mesh.volume, abs=0.02)
    assert len(current.mesh.raw.faces) == len(mesh.raw.faces)


def test_a_free_direction_drills_the_rotated_plate_to_the_given_depth():
    from app.core.geom.prepare import drill
    from tests.test_prepare import profiles

    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    matrix = np.asarray(rotation("y", 37.0))
    moved = apply(mesh, rotation("y", 37.0))
    mouth = tuple(trimesh.transform_points([[0.0, 0.0, 4.0]], matrix)[0])
    result = drill(
        moved,
        position=mouth,
        axis="z",
        normal=tuple(matrix[:3, 2]),
        diameter=4.0,
        depth=3.0,
        compensate=False,
        profile=profiles.make_profile("centauri-carbon-2", "petg"),
    )
    removed = moved.volume - result.mesh.volume
    assert removed == pytest.approx(math.pi * 4.0 * 3.0, rel=0.03)


@pytest.mark.parametrize("route", ["x", "y", "z", "normal"])
@pytest.mark.parametrize("side", [-1.0, 1.0])
@pytest.mark.parametrize("anchor", ["mouth", "centre"])
@pytest.mark.parametrize("widened", [False, True])
def test_blind_drill_keeps_the_exact_bottom_and_anchor(route, side, anchor, widened, profile):
    """Die eingegebene Tiefe begrenzt das echte Loch, einschließlich seiner Blindböden."""
    from app.core.geom.mesh import ray_hit_distances
    from app.core.geom.prepare import BORE_SECTIONS, drill
    from app.core.sketch.planes import frame_of
    from tests.helpers import cube_mesh

    outward = (
        np.asarray((0.3, 0.4, math.sqrt(0.75)))
        if route == "normal"
        else np.eye(3)[{"x": 0, "y": 1, "z": 2}[route]]
    )
    outward *= side
    frame = frame_of(tuple(outward), (0.0, 0.0, 0.0))
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    original = cube_mesh().raw.copy()
    original.apply_transform(matrix)
    mesh = MeshData.of(original)
    depth = 2.0
    mouth = 10.0 if anchor == "mouth" else depth / 2.0
    position = tuple(outward * (10.0 if anchor == "mouth" else 0.0))
    result = drill(
        mesh,
        position=position,
        axis="z" if route == "normal" else route,
        normal=tuple(outward) if route == "normal" else (0.0, 0.0, 0.0),
        diameter=2.0,
        depth=depth,
        anchor=anchor,
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
        compensate=False,
        profile=profile,
    )
    local = result.mesh.raw.copy()
    local.apply_transform(np.linalg.inv(matrix))
    vertices = np.asarray(local.vertices)
    internal = vertices[np.linalg.norm(vertices[:, :2], axis=1) < 2.1]
    assert len(internal)
    assert float(internal[:, 2].min()) == pytest.approx(mouth - depth, abs=1e-8)
    assert float(internal[:, 2].max()) == pytest.approx(mouth, abs=1e-8)
    # Die 48-seitige Netzfläche ist analytisch bekannt; ihre Kreisabweichung
    # darf keine zusätzliche Bohrtiefe in einer großzügigen Volumentoleranz verstecken.
    area_factor = BORE_SECTIONS * math.sin(math.tau / BORE_SECTIONS) / 2.0
    volume_factor = (0.75 + 4.0 * 0.25 + (1.0 + 2.0 + 4.0) / 3.0) if widened else depth
    # Die native Rundflächenübergabe weicht im Volumen um wenige 1e-7 mm³ ab;
    # das unabhängig geprüfte Bodenmaß behält seine engere Längenschranke.
    assert mesh.volume - result.mesh.volume == pytest.approx(area_factor * volume_factor, abs=1e-6)
    assert result.mesh.is_watertight
    assert result.solver.strategy == "direct"
    if anchor == "mouth":
        hits = ray_hit_distances(
            local.triangles, np.asarray((0.0, 0.0, 11.0)), np.asarray((0.0, 0.0, -1.0))
        )
        assert float(hits.min()) == pytest.approx(11.0 - (mouth - depth), abs=1e-8)


def test_the_mouth_overlap_stays_above_the_surface_and_leaves_the_floor(profile):
    """Die Zugabe an der Mündung schneidet Luft: Boden exakt, Mündung darüber.

    Ohne sie endete das Werkzeug im Achsenweg genau auf der angeklickten
    Fläche — zwei zusammenfallende Flächen, der Fall, für den
    :data:`BOOLEAN_OVERLAP` in der Rückfallkette da ist (Review 06.09.2026).
    """
    import numpy as np

    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.geom.prepare import drill_tool

    for values in ({}, {"widening_diameter": 8.0, "widening_depth": 1.0}):
        exact = drill_tool(diameter=4.0, depth=5.0, profile=profile, compensate=False, **values)
        padded = drill_tool(
            diameter=4.0,
            depth=5.0,
            profile=profile,
            compensate=False,
            mouth_overlap=BOOLEAN_OVERLAP,
            **values,
        )
        assert padded.bounds.minimum[2] == pytest.approx(-5.0, abs=1e-9)
        assert padded.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP, abs=1e-9)
        assert exact.bounds.maximum[2] == pytest.approx(0.0, abs=1e-9)
        # Unter der Fläche sind beide Werkzeuge dasselbe; die Zugabe ist eine
        # Scheibe mit dem Querschnitt der Mündung (bei der Senkung der weite).
        radius = values.get("widening_diameter", 4.0) / 2.0
        assert np.isclose(
            padded.volume - exact.volume, np.pi * radius**2 * BOOLEAN_OVERLAP, rtol=0.03
        )


@pytest.mark.parametrize("widened", [False, True])
def test_the_shared_drill_tool_has_no_hidden_end_allowance(widened, profile):
    """Auch nicht gerundete Eingabetiefen bleiben im Werkzeugkörper exakt erhalten."""
    from app.core.geom.prepare import drill_tool

    depth = 2.123456789
    tool = drill_tool(
        diameter=2.0,
        depth=depth,
        profile=profile,
        compensate=False,
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
    )
    assert tool.bounds.minimum[2] == pytest.approx(-depth, abs=1e-12)
    assert tool.bounds.maximum[2] == pytest.approx(0.0, abs=1e-12)
    assert tool.is_watertight


@pytest.mark.parametrize("widened", [False, True])
def test_an_entered_mouth_inside_material_keeps_its_exact_start(widened, profile):
    """Eine manuell im Material gesetzte Mündung ist kein belegter Außenanschluss."""
    from app.core.geom.prepare import drill
    from tests.helpers import cube_mesh

    result = drill(
        cube_mesh(),
        position=(0.0, 0.0, 5.0),
        axis="z",
        normal=(0.0, 0.0, 1.0),
        diameter=2.0,
        depth=2.0,
        anchor="mouth",
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
        compensate=False,
        profile=profile,
    )
    vertices = np.asarray(result.mesh.raw.vertices)
    internal = vertices[np.linalg.norm(vertices[:, :2], axis=1) < 2.1]
    assert float(internal[:, 2].min()) == pytest.approx(3.0, abs=1e-8)
    assert float(internal[:, 2].max()) == pytest.approx(5.0, abs=1e-8)


@pytest.mark.parametrize("normal", [(0.0, 0.0, 0.0), (0.0, 0.0, -1.0)])
@pytest.mark.parametrize("anchor", ["mouth", "centre"])
@pytest.mark.parametrize("widened", [False, True])
def test_through_drilling_stays_open_after_removing_blind_allowances(
    normal, anchor, widened, profile
):
    """Die ausdrücklich überlange Durchgangsgeometrie lässt auf keiner Seite einen Boden."""
    from app.core.geom.mesh import ray_hit_distances
    from app.core.geom.prepare import drill
    from tests.helpers import cube_mesh

    mesh = cube_mesh()
    result = drill(
        mesh,
        position=(0.0, 0.0, -10.0),
        axis="z",
        normal=normal,
        anchor=anchor,
        diameter=2.0,
        depth=0.0,
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
        compensate=False,
        profile=profile,
    )
    for side in (-1.0, 1.0):
        hits = ray_hit_distances(
            result.mesh.raw.triangles,
            np.asarray((0.0, 0.0, side * 11.0)),
            np.asarray((0.0, 0.0, -side)),
        )
        assert not len(hits)
    assert result.mesh.is_watertight
    assert result.solver.strategy == "direct"


@pytest.mark.parametrize("gap", [-1e-3, 1e-3, -1e-9, 1e-9])
@pytest.mark.parametrize("widened", [False, True])
def test_a_real_offset_from_the_drill_mouth_survives_roundoff_cleanup(gap, widened, profile):
    """Ein Abstand über der Schweißtoleranz bleibt ein echter Abstand, einer darunter nicht.

    **Die Grenze ist seit RM-274 die Schweißtoleranz** (``units.weld_tolerance``,
    am Würfel 20 mm 3,5·10⁻⁵ mm) und nicht mehr der Float64-Rechenfehler. Das
    Werkzeug liegt in der Welt, und dort trifft es eine schräge Fläche nicht
    genau; eine Mündung, die näher als zwei Orte, die das Verschweißen für einen
    hält, an der Fläche liegt, liegt in ihr und reicht in die Luft davor. Mit
    der alten Grenze behielt eine eingelesene float32-Fläche eine Haut über der
    Bohrung (``tests/test_cut_in_world.py``). Ein Tausendstel Millimeter bleibt
    ein echter Abstand: darüber eine Haut, darunter Luft.
    """
    from app.core.geom.mesh import ray_hit_distances
    from app.core.geom.prepare import drill
    from app.core.sketch.planes import frame_of
    from tests.helpers import cube_mesh

    outward = np.asarray((0.3, 0.4, math.sqrt(0.75)))
    frame = frame_of(tuple(outward), (0.0, 0.0, 0.0))
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    raw = cube_mesh().raw.copy()
    # apply_translation überspringt solche kleinen Verschiebungen als Identität;
    # hier muss der analytisch vorgegebene Abstand wirklich im Eingang stehen.
    raw.vertices = np.asarray(raw.vertices) + np.asarray((0.0, 0.0, gap))
    raw.apply_transform(matrix)
    result = drill(
        MeshData.of(raw),
        position=tuple(outward * 10.0),
        axis="z",
        normal=tuple(outward),
        diameter=2.0,
        depth=2.0,
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
        compensate=False,
        profile=profile,
    )
    local = result.mesh.raw.copy()
    local.apply_transform(np.linalg.inv(matrix))
    assert local.bounds[1, 2] == pytest.approx(10.0 + gap, abs=5e-14)
    hits = ray_hit_distances(
        local.triangles, np.asarray((0.0, 0.0, 11.0)), np.asarray((0.0, 0.0, -1.0))
    )
    # Eine echte Haut über der Mündung bleibt; unter der Schweißtoleranz ist sie keine.
    expected = 1.0 - gap if gap > 1e-6 else 3.0
    assert float(hits.min()) == pytest.approx(expected, abs=5e-14)
    assert result.mesh.is_watertight


@pytest.mark.parametrize("widened", [False, True])
def test_a_coplanar_drill_mouth_keeps_its_bottom_after_welding(widened, profile, monkeypatch):
    """Die echte zweite Stufe darf die maßhaltige koplanare Mündung ebenfalls schneiden."""
    from importlib import import_module

    from app.core.geom.mesh import ray_hit_distances
    from app.core.geom.prepare import drill
    from tests.helpers import cube_mesh

    module = import_module("app.core.geom.boolean")
    original = module._run_stage

    def skip_direct(kind, meshes, stage, seed, cancelled=None):
        return None if stage == "direct" else original(kind, meshes, stage, seed, cancelled)

    monkeypatch.setattr(module, "_run_stage", skip_direct)
    result = drill(
        cube_mesh(),
        position=(0.0, 0.0, 10.0),
        axis="z",
        normal=(0.0, 0.0, 1.0),
        diameter=2.0,
        depth=2.0,
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
        compensate=False,
        profile=profile,
    )
    hits = ray_hit_distances(
        result.mesh.raw.triangles,
        np.asarray((0.0, 0.0, 11.0)),
        np.asarray((0.0, 0.0, -1.0)),
    )
    assert result.solver.strategy == "welded"
    assert result.solver.attempted == ("direct", "welded")
    assert result.mesh.is_watertight
    assert float(hits.min()) == pytest.approx(3.0, abs=1e-8)


@pytest.mark.parametrize("depth", [0.0, 10.0])
def test_a_surface_drill_builds_one_connected_three_stage_cavity(depth, profile):
    """Bohrung, Übergang und Aufweitung bilden dieselbe erkennbare zusammenhängende Form."""
    from app.core.perceive.features import detect
    from app.core.perceive.relations import cavity_chains
    from app.core.types import SceneObject
    from tests.helpers import run_operation as run

    load_operations()
    raw = trimesh.creation.box((40.0, 30.0, 10.0))
    raw.apply_translation((0.0, 0.0, 5.0))
    source = SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(raw))
    result = run(
        "drill_hole",
        source,
        profile,
        diameter=6.0,
        depth=depth,
        widening_diameter=11.0,
        widening_depth=1.5,
        transition_angle=90.0,
        z=10.0,
        nz=1.0,
        compensate=False,
    ).outputs[0]
    chain = next(iter(cavity_chains(detect(result.mesh), result.mesh)))
    assert sorted(item.kind for item in chain) == ["cone", "hole", "hole"]
    assert result.mesh.raw.is_watertight
    assert source.mesh.volume - result.mesh.volume == pytest.approx(
        math.pi * (54.0 + 55.75 * 2.5 / 3.0 + 45.375), rel=0.005
    )


@pytest.mark.parametrize("sides", [8, 12, 16])
def test_regular_polygon_edges_need_round_provenance_before_being_hidden(sides):
    """Ein echtes regelmäßiges Vieleck verliert seine Bezugskanten nicht an einen Kreisfit."""
    mesh = MeshData.of(trimesh.creation.cylinder(radius=10.0, height=8.0, sections=sides))
    face = _top(mesh)
    plane = Feature(
        id="face_top",
        kind="face",
        provenance="generated",
        face_indices=[face],
        params={"normal": (0.0, 0.0, 1.0)},
    )
    prepared = placement.prepare_surface(mesh, face, {plane.id: plane})
    assert len(prepared.edges) == sides


def test_drill_preview_and_actual_operation_use_the_objects_material(profile, monkeypatch):
    """Die Körperwahl gilt für den sichtbaren Werkzeugkörper und den tatsächlichen Abtrag."""
    import app.core.geom.prepare as module
    from app.core.types import SceneObject
    from tests.helpers import run_operation as run

    load_operations()
    source = SceneObject(
        id="obj_1",
        name="PLA-Platte",
        material="pla",
        mesh=MeshData.of(trimesh.creation.box((30.0, 20.0, 10.0))),
    )
    values = {
        "diameter": 4.0,
        "depth": 8.0,
        "widening_diameter": 8.0,
        "widening_depth": 1.0,
        "transition_angle": 90.0,
    }
    preview = placement.prepare_tool(
        REGISTRY.get("drill_hole"), values, profile, source=source
    ).mesh
    captured = []
    original = module.boolean

    def record(kind, meshes, **kwargs):
        captured.append(meshes[1])
        return original(kind, meshes, **kwargs)

    monkeypatch.setattr(module, "boolean", record)
    run("drill_hole", source, profile, **values, z=5.0, nx=0.3, ny=0.4, nz=0.5)
    assert captured[0].raw.vertices == pytest.approx(
        _placed_like_the_cut(preview, (0.3, 0.4, 0.5), (0.0, 0.0, 5.0)), abs=1e-12
    )
    from app.core.knowledge.profiles import for_object

    assert np.ptp(preview.raw.vertices[:, 0]) == pytest.approx(
        module.bore_diameter(8.0, for_object(profile, source), True)
    )


@pytest.mark.parametrize(
    "values",
    [
        {"widening_diameter": 3.0},
        {"widening_diameter": float("nan")},
        {"widening_diameter": 8.0, "widening_depth": 3.0},
        {"widening_diameter": 8.0, "transition_angle": 0.0},
    ],
)
def test_invalid_widening_has_an_actionable_error(values, profile):
    from app.core.errors import ValidationError
    from app.core.geom.prepare import drill_tool

    with pytest.raises(ValidationError) as caught:
        drill_tool(diameter=4.0, depth=4.0, profile=profile, compensate=False, **values)
    assert caught.value.suggestions


def test_widening_starts_at_the_clicked_step_not_the_highest_face(profile):
    """Ein höherer Nachbar verschiebt die Aufweitung nicht aus der gewählten Fläche."""
    from app.core.geom.boolean import boolean
    from app.core.geom.prepare import drill

    low = trimesh.creation.box((40.0, 30.0, 8.0))
    low.apply_translation((0.0, 0.0, 4.0))
    high = trimesh.creation.box((10.0, 30.0, 20.0))
    high.apply_translation((-15.0, 0.0, 10.0))
    mesh = boolean("union", [MeshData.of(low), MeshData.of(high)]).mesh
    actual = drill(
        mesh,
        position=(8.0, 0.0, 8.0),
        axis="z",
        normal=(0.0, 0.0, 1.0),
        diameter=4.0,
        depth=0.0,
        widening_diameter=8.0,
        widening_depth=1.0,
        transition_angle=180.0,
        profile=profile,
        compensate=False,
    ).mesh
    assert mesh.volume - actual.volume == pytest.approx(math.pi * (4.0 * 7.0 + 16.0), rel=0.005)


def test_centre_offsets_are_editable_in_the_actual_rotated_plane():
    """Mittelpunktmaße gehören zur Flächenebene und dürfen nicht in die Öffnung führen."""
    from app.core.geom.boolean import boolean

    raw = boolean(
        "difference",
        [
            MeshData.of(trimesh.creation.box((20.0, 20.0, 4.0))),
            MeshData.of(trimesh.creation.cylinder(radius=2.0, height=10.0, sections=48)),
        ],
    ).mesh
    matrix = np.asarray(rotation("y", 37.0))
    mesh = apply(raw, matrix)
    centre = Feature(
        id="hole_1",
        kind="hole",
        provenance="generated",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": tuple(matrix[:3, 2]),
            "depth": 4.0,
            "diameter": 4.0,
        },
    )
    prepared = placement.prepare_surface(mesh, _top(raw), {centre.id: centre})
    point = tuple(trimesh.transform_points([[6.0, 5.0, 2.0]], matrix)[0])
    surface = placement.at_point(prepared, point)
    result = placement.point_with_centre(prepared, surface, centre.id, (3.123456789, 4.0))
    reference = next(item for item in result.centres if item.feature_id == centre.id)
    assert reference.offset == pytest.approx((3.123456789, 4.0), abs=1e-12)
    assert reference.distance == pytest.approx(math.hypot(3.123456789, 4.0))
    crossed = placement.point_with_centre(prepared, result, centre.id, (-4.0, -5.0))
    assert [edge.id for edge in crossed.edges] == [edge.id for edge in surface.edges]
    with pytest.raises(ValidationError, match="außerhalb"):
        placement.point_with_centre(prepared, result, centre.id, (0.0, 0.0))
    with pytest.raises(ValidationError, match="außerhalb"):
        placement.point_with_centre(prepared, result, centre.id, (100.0, 100.0))


def test_through_drill_preview_uses_the_target_size(profile):
    from app.core.types import SceneObject

    load_operations()
    source = SceneObject(
        id="obj_1", name="Würfel", mesh=MeshData.of(trimesh.creation.box((20.0, 20.0, 20.0)))
    )
    tool = placement.prepare_tool(
        REGISTRY.get("drill_hole"), {"diameter": 4.0}, profile, source=source
    ).mesh
    assert 20.0 <= float(np.ptp(tool.raw.vertices[:, 2])) < 35.0


def test_a_nonuniform_bore_rim_does_not_shift_its_placement_anchor():
    """Zusätzliche Teilungen an einer Kreisstelle verschieben weder Mündung noch Bohrungsachse."""
    from shapely.geometry import Polygon

    from app.core.geom.prepare_ops import feature_placement_geometry
    from app.core.types import SceneObject

    angles = np.concatenate(
        (
            np.linspace(0.0, math.pi / 2.0, 33, endpoint=False),
            np.linspace(math.pi / 2.0, 2.0 * math.pi, 16, endpoint=False),
        )
    )
    points = np.column_stack((2.0 * np.cos(angles), 2.0 * np.sin(angles)))
    polygon = Polygon([(-20, -15), (20, -15), (20, 15), (-20, 15)], holes=[points])
    raw = trimesh.creation.extrude_polygon(polygon, 8.0)
    faces = np.flatnonzero(
        (np.linalg.norm(raw.triangles_center[:, :2], axis=1) < 3.0)
        & (np.abs(raw.face_normals[:, 2]) < 0.5)
    )
    feature = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 4.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 4.0,
            "depth": 8.0,
            "through": True,
        },
        face_indices=tuple(int(index) for index in faces),
    )
    source = SceneObject(
        id="obj_1", name="Platte", mesh=MeshData.of(raw), features={feature.id: feature}
    )
    load_operations()
    geometry = feature_placement_geometry(source, feature, "move_feature")
    assert geometry.frame.origin == pytest.approx((0.0, 0.0, 8.0), abs=1e-12)
    assert geometry.selected_offset == pytest.approx((0.0, 0.0, -4.0), abs=1e-12)


def test_prepared_feature_tool_keeps_geometry_out_of_point_updates(profile, monkeypatch):
    """Der Worker baut den Merkmalskörper; Punktänderungen verwenden nur den Versatz."""
    import app.core.geom.prepare_ops as module
    from app.core.geom.boolean import boolean
    from app.core.types import SceneObject

    load_operations()
    mesh = boolean(
        "difference",
        [
            MeshData.of(trimesh.creation.box((20.0, 20.0, 8.0))),
            MeshData.of(trimesh.creation.cylinder(radius=1.5, height=10.0, sections=48)),
        ],
    ).mesh
    feature = Feature(
        id="hole_1",
        kind="hole",
        provenance="generated",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 3.0,
            "depth": 8.0,
            "through": True,
        },
    )
    source = SceneObject(id="obj_1", name="Platte", mesh=mesh, features={feature.id: feature})
    spec = REGISTRY.get("move_feature")
    tool = placement.prepare_tool(spec, {}, profile, source=source, feature=feature)
    monkeypatch.setattr(
        module,
        "feature_placement_geometry",
        lambda *_: pytest.fail("geometry rebuilt in point update"),
    )
    prepared = placement.prepare_surface(mesh, _top(mesh))
    for point in ((6.0, 4.0, 4.0), (7.123456789, 3.0, 4.0)):
        surface = placement.at_point(prepared, point)
        values = placement.surface_values(
            spec, surface, feature=feature, source=source, prepared_tool=tool
        )
        assert (values["x"], values["y"], values["z"]) == pytest.approx((*point[:2], 0.0))


@pytest.mark.parametrize(
    ("operation", "values"),
    [
        ("create_box", {"width": 12.0, "depth": 8.0, "height": 5.0}),
        ("create_box", {"width": 12.0, "depth": 8.0, "height": 5.0, "anchor": "corner"}),
        ("create_cylinder", {"diameter": 10.0, "height": 7.0, "segments": 32}),
        ("create_cone", {"bottom_diameter": 12.0, "top_diameter": 6.0, "height": 9.0}),
        ("create_sphere", {"diameter": 10.0, "segments": 24}),
        ("create_torus", {"outer_diameter": 20.0, "tube_diameter": 4.0, "segments": 32}),
    ],
)
def test_primitive_surface_route_places_the_actual_tool_without_rounding(
    operation, values, profile
):
    """Jeder Grundkörper nutzt vom Originaltreffer bis zur echten Op denselben Rahmen."""
    from tests.helpers import primitive_operation

    load_operations()
    raw = trimesh.creation.box((40.0, 30.0, 8.0))
    original_face = _top(MeshData.of(raw))
    turn = np.asarray(rotation("y", 127.0))
    raw.apply_transform(turn)
    point = trimesh.transform_points([[4.123456789, 3.0, 4.0]], turn)[0]
    prepared = placement.prepare_surface(MeshData.of(raw), original_face)
    hit = placement.at_point(prepared, tuple(point))
    spec = REGISTRY.get(operation)
    assert placement.supports_surface_placement(spec)
    tool = placement.prepare_tool(spec, values, profile)
    placed_values = placement.surface_values(spec, hit, prepared_tool=tool)
    assert [placed_values[key] for key in ("x", "y", "z")] == pytest.approx(point, abs=1e-12)
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((hit.frame.x_axis, hit.frame.y_axis, hit.normal))
    matrix[:3, 3] = point
    shown = apply(tool.mesh, matrix)
    actual = primitive_operation(operation, {**values, **placed_values}, profile).outputs[0].mesh
    assert actual.raw.vertices == pytest.approx(shown.raw.vertices, abs=1e-12)
    assert np.array_equal(actual.raw.faces, shown.raw.faces)


def test_primitive_preview_validates_dimensions_before_building(profile, monkeypatch):
    """Ungültige Maße erreichen auch über den Vorschauweg keine Geometriefunktion."""
    import app.core.geom.primitive_ops as module
    from app.core.errors import ValidationError

    load_operations()
    monkeypatch.setattr(module, "primitive_local_tool", lambda *_: pytest.fail("unvalidated build"))
    with pytest.raises(ValidationError):
        placement.prepare_tool(REGISTRY.get("create_cone"), {"height": -1.0}, profile)


def test_internal_shoulders_never_replace_the_outer_cavity_mouth():
    """Eine breitere Innenstufe ist keine Ansatzfläche der vollständigen Bohrkette."""
    from app.core.geom.prepare_ops import feature_placement_geometry
    from app.core.perceive.features import detect
    from app.core.perceive.relations import cavity_chains
    from app.core.types import SceneObject

    outline = [
        [12.0, 0.0],
        [12.0, 12.0],
        [3.0, 12.0],
        [3.0, 9.0],
        [5.0, 9.0],
        [5.0, 6.0],
        [7.0, 6.0],
        [7.0, 3.0],
        [2.0, 3.0],
        [2.0, 0.0],
        [12.0, 0.0],
    ]
    mesh = MeshData.of(trimesh.creation.revolve(outline, sections=48))
    features = detect(mesh)
    chain = next(iter(cavity_chains(features, mesh)))
    assert len(chain) == 4
    source = SceneObject(id="obj_1", name="Innenstufen", mesh=mesh, features=features)
    geometry = feature_placement_geometry(source, chain[0], "move_feature")
    assert geometry.frame.origin == pytest.approx((0.0, 0.0, 12.0), abs=1e-10)
    assert geometry.frame.normal == pytest.approx((0.0, 0.0, 1.0))
    assert geometry.mesh.is_watertight
    assert geometry.mesh.bounds.maximum[2] == pytest.approx(0.0, abs=1e-10)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_chain_whose_mouth_lies_in_a_curved_face_can_be_placed_by_hand(
    kernel: str, profile
) -> None:
    """Eine Kette mit gekrümmter Mündung lässt sich ins Bild klicken — und die
    alte Stelle füllt der Stopfen, nicht das Werkzeug.

    ``feature_placement_geometry`` fragte nur ``_paired_cavity_body``, und das
    findet an einer gekrümmten Mündung keine Ebene: Wer die Senkbohrung einer
    Platte mit gewölbter Unterseite — oder die Senkungen in der Hohlkehle des
    Gartenschlauchhalters — an eine neue Stelle klicken wollte, las „Dieses
    Merkmal geht in einen anderen Hohlraum über …“, obwohl *Merkmal
    versetzen* mit eingetippten Zahlen dieselbe Kette versetzt (Durchsicht
    0.5.1). Jetzt nimmt der Geist dasselbe Werkzeug wie die Operation.

    **Dieses Werkzeug reicht über die gekrümmte Mündung hinaus**, und
    ``_place_oriented_feature`` füllte die alte Stelle mit dem Geist: Mit ihm
    stand dort ein Stumpf unter der Fläche, 8,3 mm³ (gemessen an dieser
    Platte, 16 mm entlang X). Gefüllt wird jetzt mit dem Stopfen der Kette
    (``flush``), wie beim Versetzen mit Zahlen.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.prepare_ops import feature_placement_geometry
    from app.core.units import MAX_FACET_SAG
    from tests.helpers import BOTH_ENDS, cavity_under, narrowest_hole, widened_bore
    from tests.helpers import run_operation as run

    load_operations()
    outline = BOTH_ENDS["Zylindersenkung und Fase"]
    source = widened_bore(kernel, outline, bottom="Zylinder R 40")
    bore = narrowest_hole(source)
    geometry = feature_placement_geometry(source, bore, "move_feature")
    assert geometry.mesh.is_watertight
    assert len(geometry.related) == 3
    assert not geometry.flush
    # Der ganze Hohlraum reist mit: Senkung, Bohrung und Fase, 651 mm³ nach
    # dem Profil, dazu der Überstand hinter der gekrümmten Mündung.
    assert abs(float(geometry.mesh.volume)) > 640.0

    mesh = as_mesh_data(source.mesh)
    before = abs(float(mesh.volume))
    normals = np.asarray(mesh.raw.face_normals)
    centres = np.asarray(mesh.raw.triangles_center)
    # Geklickt wird auf die Oberseite, an der der Rahmen sitzt, 16 mm weiter
    # entlang X — dort ist die Unterseite dieselbe.
    top = np.flatnonzero((normals[:, 2] > 0.999) & (np.abs(centres[:, 2] - 12.0) < 0.01))
    placed = {}
    for operation in ("move_feature", "duplicate_feature"):
        spec = REGISTRY.get(operation)
        prepared = placement.prepare_surface(mesh, int(top[0]), source.features)
        hit = placement.at_point(prepared, (8.0, 0.0, 12.0))
        values = placement.surface_values(spec, hit, feature=bore, source=source)
        placed[operation] = as_mesh_data(run(operation, source, profile, **values).outputs[0].mesh)
    moved = placed["move_feature"]
    assert moved.is_watertight
    assert abs(float(moved.volume)) - before == pytest.approx(0.0, abs=0.5)
    assert float(moved.bounds.minimum[2]) > -MAX_FACET_SAG
    removed = before - abs(float(placed["duplicate_feature"].volume))
    assert removed == pytest.approx(cavity_under("Zylinder R 40", outline), rel=0.01)


def test_the_welded_adjacency_is_built_once_per_mesh_and_not_once_per_click():
    """Die Nachbarschaft hängt am Netz, nicht an der angeklickten Fläche.

    ``_patch_faces`` sucht die zusammenhängenden koplanaren Dreiecke, und der
    teure Teil davon — Punkte exakt verschweißen, Kanten bilden, Besitzer
    zählen — kennt die Fläche gar nicht. Er lief trotzdem bei jedem Aufruf,
    also bei jeder Mausbewegung über das Modell: gemessen an
    ``Filamenthalter-Solidon3D.p3d`` (2 428 Dreiecke) 4,4 ms im Median und
    52 ms im schlechtesten Fall (Befund Robert, 09.09.2026).

    Gezählt wird die Identität des Ergebnisses und nicht die Zeit: Eine
    Zeitschranke wäre auf einer schnellen Maschine grün und sagte nichts
    darüber, ob zweimal gerechnet wurde.
    """
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    raw = mesh.raw
    vertices = np.asarray(raw.vertices, dtype=np.float64)

    erste = placement._welded_adjacency(raw, vertices)
    zweite = placement._welded_adjacency(raw, vertices)
    assert len(erste), "ohne Nachbarschaft prüft der Test nichts"
    assert zweite is erste, "die zweite Frage rechnete erneut"

    # Über den echten Weg: zwei Klicks auf verschiedene Flächen desselben
    # Netzes teilen dieselbe Auskunft.
    placement.prepare_surface(mesh, _top(mesh))
    unten = int(np.argmin(np.asarray(raw.face_normals)[:, 2]))
    placement.prepare_surface(mesh, unten)
    assert placement._welded_adjacency(raw, vertices) is erste

    # **Und sie verfällt mit dem Netz.** Das ist der Grund, warum der Cache
    # im Netz selbst liegt und nicht in einem Wörterbuch daneben: Ein
    # verschobener Punkt macht jede Kantenzuordnung ungültig.
    raw.vertices[0][0] += 1.0
    danach = placement._welded_adjacency(raw, np.asarray(raw.vertices, dtype=np.float64))
    assert danach is not erste, "die alte Nachbarschaft überlebte eine Netzänderung"


def test_a_depth_that_goes_outwards_gets_no_depth_stage():
    """Zwölf Operationen führen ein ``depth`` — bei dreien geht es nach außen.

    Die Tiefenstufe der Flächenplatzierung zieht die Maus nach unten ins
    Material. Wer den Namen des Feldes für die Auskunft hält, zieht damit auch
    an der vorstehenden Nase von ``insert_latch`` und an einer erhabenen
    Beschriftung — Werte, die nichts abtragen. Gefragt wird deshalb nach der
    Richtung, aus derselben Quelle wie die Boolesche Operation und die
    Vorschaufarbe.
    """
    from app.core.knowledge.parts.ops import depth_field

    load_operations()

    for name in ("drill_hole", "plug_hole", "sketch_pocket", "insert_screw_hole"):
        spec = REGISTRY.get(name)
        assert depth_field(name, spec.params) == "depth", f"{name} bohrt ins Material"

    # Die Nase steht vor: kein Zug nach unten. Ihre Aussparung trägt ab — seit
    # dem 22.09.2026 sagt der Umschalter das (``subtractive_on``); vorher wurde
    # auch die Aussparung aufgesetzt.
    latch = REGISTRY.get("insert_latch")
    nose, pocket = latch.params(negative=False), latch.params(negative=True)
    assert depth_field("insert_latch", latch.params, nose) is None
    assert depth_field("insert_latch", latch.params, pocket) == "depth"

    # Und wo ein Umschalter die Richtung führt, entscheidet sein Wert.
    for name, values in (
        ("label_text", {"text": "A"}),
        ("apply_texture", {}),
    ):
        spec = REGISTRY.get(name)
        raised = spec.params(**values, mode="raised")
        engraved = spec.params(**values, mode="engraved")
        assert depth_field(name, spec.params, raised) is None, f"{name} erhaben trägt nichts ab"
        assert depth_field(name, spec.params, engraved) == "depth", f"{name} vertieft schon"
        # Ohne Werte bleibt es ein Angebot: Der Umschalter *kann* abtragen.
        assert depth_field(name, spec.params) == "depth"


def _plate_with(**values):
    """Platte 60 x 40 x 10 mit einem Loch bei (10, 5) — rund oder lang."""
    from app.core.geom.prepare import drill
    from app.core.knowledge import profiles
    from app.core.perceive.features import detect

    load_operations()
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    plate = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    mesh = drill(
        plate,
        profile=profile,
        position=(10.0, 5.0, 5.0),
        axis="z",
        diameter=6.0,
        compensate=False,
        **values,
    ).mesh
    return mesh, detect(mesh)


@pytest.mark.parametrize(
    ("beschreibung", "werte"),
    [("rund", {}), ("lang", {"slot_length": 20.0, "slot_angle": 30.0})],
)
def test_a_feature_that_is_already_there_knows_its_distances(beschreibung, werte):
    """Wo ein Merkmal sitzt, misst sich am Rand des Teils (Robert, 10.09.2026).

    ``prepare_surface`` beantwortet „wohin darf ich setzen" und verlangt einen
    Klick auf Material; die Mitte eines bestehenden Lochs liegt in dessen
    eigener Aussparung, und ``at_point`` lehnt sie ab. ``seat_of`` füllt sie —
    für die Frage nach den **Außenmaßen** ist das Loch ohne Belang.

    Gemessen an einer Platte 60 x 40 mit dem Loch bei (10, 5): 15 mm zur oberen
    und 20 mm zur rechten Kante, für das runde wie für das lange.
    """
    mesh, found = _plate_with(**werte)
    feature = next(entry for entry in found.values() if entry.kind in ("hole", "slot"))

    seat = placement.seat_of(mesh, feature, found)

    assert seat is not None, f"{beschreibung}: die Trägerfläche wurde nicht gefunden"
    prepared, mouth = seat
    assert mouth == pytest.approx((10.0, 5.0, 5.0)), "die Mündung liegt auf der Oberseite"
    spot = placement.at_point(prepared, mouth)
    assert sorted(edge.distance for edge in spot.edges) == pytest.approx([15.0, 20.0])


def test_an_unusable_surface_candidate_does_not_hide_a_valid_mouth(monkeypatch):
    """Eine nicht vorbereitbare Fläche verdrängt keine spätere gültige Fläche derselben Mündung."""
    from dataclasses import replace

    mesh, found = _plate_with()
    feature = next(entry for entry in found.values() if entry.kind == "hole")
    top = next(
        entry
        for entry in found.values()
        if entry.kind == "face" and entry.params["normal"][2] > 0.99
    )
    unusable = replace(top, id="unusable_face", face_indices=(-1,))
    candidates = {unusable.id: unusable, **found}
    original = placement.prepare_surface
    inspected = []

    def prepare(mesh, index, features):
        inspected.append(index)
        if index == -1:
            raise ValidationError("face", "Diese Fläche ist nicht zusammenhängend.")
        return original(mesh, index, features)

    monkeypatch.setattr(placement, "prepare_surface", prepare)

    seat = placement.seat_of(mesh, feature, candidates)

    assert -1 in inspected
    assert seat is not None
    prepared, mouth = seat
    assert mouth == pytest.approx((10.0, 5.0, 5.0))
    assert sorted(
        edge.distance for edge in placement.at_point(prepared, mouth).edges
    ) == pytest.approx([15.0, 20.0])


def test_the_flanks_of_a_slot_are_not_its_distance_to_the_edge():
    """Die eigene Öffnung ist keine Bezugskante — die Gegenprobe zur Füllung.

    Ein Langloch hat zwei **gerade** Flanken, und vom Merkmal aus sind sie die
    nächsten Kanten überhaupt: Ohne die Filterung kamen minus 3,00 und minus
    3,30 zurück, also seine eigene halbe Breite. Eine runde Bohrung zeigt den
    Fall nicht — ihr Rand ist ein Kreis und trägt keine geraden Bezugskanten.
    """
    mesh, found = _plate_with(slot_length=20.0, slot_angle=30.0)
    slot = next(entry for entry in found.values() if entry.kind == "slot")

    prepared, mouth = placement.seat_of(mesh, slot, found)

    assert all(edge.distance > 0.0 for edge in placement.at_point(prepared, mouth).edges), (
        "keine Kante der eigenen Aussparung"
    )
    assert not prepared.area.interiors, "die Öffnung ist gefüllt"


@pytest.mark.parametrize(
    ("kind", "mouth", "distances", "operation"),
    [
        # Sackloch Ø 9 von unten: Wand von z = -3,4 bis 2,0, Fase 0,6 bis z = -4.
        # Kanten der Unterseite: links x = -30 (15 mm), vorn/hinten y = ±20 (20 mm).
        ("hole", (-15.0, 0.0, -4.0), [15.0, 20.0], "resize_hole"),
        # Langloch 6 x 18 durch, Fasen 0,8 oben und unten: Wand von z = -3,2 bis
        # 3,2. Kanten der Oberseite: rechts x = 30 (18 mm), vorn/hinten 20 mm.
        ("slot", (12.0, 0.0, 4.0), [18.0, 20.0], "slot_hole"),
    ],
)
def test_a_chamfered_mouth_still_finds_its_carrier_face(kind, mouth, distances, operation):
    """Eine Fase an der Mündung legt die gemessene Wand unter die Fläche (Robert, 24.09.2026).

    Die Erkennung misst die zylindrische Wand; eine Fase oder Rundung an der
    Mündung gehört nicht dazu, und die Mündung liegt damit unter der Ebene
    der Trägerfläche. Gemessen an echten Modellen: Magnettasche des Schabers
    0,19 mm, Langloch des Wedge-Lock 0,76 mm — beide Male keine Fläche, keine
    Maße im Bild, und der Platzierungsfluss fiel aufs Zielen mit dem Zeiger
    zurück. Die Fläche hinter der Fase ist die Trägerfläche, sofern ihre
    Öffnung die Achse umschließt; die Mitte des Merkmals bleibt, wo sie ist.

    Die Gegenprobe steckt im Sackloch: Über seinem Boden liegt die Oberseite
    nur 2 mm entfernt, näher als ein Radius, und sie hat dort keine Öffnung.
    Sie darf nicht die Trägerfläche sein.
    """
    from pathlib import Path

    from app.core.perceive.features import detect

    load_operations()
    mesh = MeshData.of(
        trimesh.load_mesh(
            Path(__file__).parent / "data" / "meshes" / "plate_chamfered_mouths.stl",
            process=True,
        )
    )
    found = detect(mesh)
    feature = next(entry for entry in found.values() if entry.kind == kind)

    seat = placement.seat_of(mesh, feature, found)

    assert seat is not None, "die Fläche hinter der Fase trägt das Merkmal"
    prepared, seated = seat
    assert seated == pytest.approx(mouth, abs=1e-6)
    spot = placement.at_point(prepared, seated)
    assert sorted(edge.distance for edge in spot.edges) == pytest.approx(distances, abs=1e-6)
    values = placement.surface_values(REGISTRY.get(operation), spot, feature=feature, mouth=seated)
    assert (values["x"], values["y"], values["z"]) == pytest.approx(
        feature.params["centre"], abs=1e-6
    ), "die Mitte bleibt auf ihrer Höhe, die Fase verschiebt sie nicht"


@pytest.mark.parametrize("shift", [-0.0035, 0.0035])
def test_a_mouth_measured_a_few_microns_off_its_face_still_seats(shift):
    """Eine eingepasste Wand endet nicht auf den Mikrometer in ihrer Fläche.

    Am Wedge-Lock lag die gemessene Mündung eines gekürzten Langlochs 3,5 µm
    über ihrer Fläche; für ``EPS_GEOM`` eine andere Ebene, und das Langloch
    hatte nach dem Übernehmen keine Maße mehr. Nachgestellt an der Lochplatte
    des Korpus, deren Bohrung Ø 5,2 von z = -4 bis 4 durch die Platte geht:
    die Mitte um dieselben 3,5 µm entlang der Achse versetzt, in beide
    Richtungen. Der Sitz bleibt die Oberseite, und die Mitte bleibt die
    gemessene.
    """
    from dataclasses import replace
    from pathlib import Path

    from app.core.perceive.features import detect

    load_operations()
    mesh = MeshData.of(
        trimesh.load_mesh(Path(__file__).parent / "data" / "meshes" / "plate_holes.stl")
    )
    found = detect(mesh)
    hole = min(
        (entry for entry in found.values() if entry.kind == "hole"),
        key=lambda entry: entry.id,
    )
    x, y, z = hole.params["centre"]
    measured = replace(hole, params={**hole.params, "centre": (x, y, z + shift)})

    seat = placement.seat_of(mesh, measured, {**found, measured.id: measured})

    assert seat is not None, "ein Messrest von Mikrometern ist keine andere Fläche"
    prepared, mouth = seat
    assert mouth == pytest.approx((x, y, 4.0), abs=1e-9)
    spot = placement.at_point(prepared, mouth)
    values = placement.surface_values(
        REGISTRY.get("resize_hole"), spot, feature=measured, mouth=mouth
    )
    assert (values["x"], values["y"], values["z"]) == pytest.approx((x, y, z + shift), abs=1e-9)


def test_moving_along_the_face_keeps_the_height_of_a_slightly_tilted_hole():
    """Die Mitte behält ihre Höhe, auch wenn die gemessene Achse um Rauschen schief steht.

    Am Schaber stand die Achse der Magnettasche 1,5 µrad schief. Gemessen
    wurde der Abstand zur Mitte am **verschobenen** Punkt, und der wuchs mit
    dem Versatz: 43 mm weiter lag die Mitte 2,9 µm höher. Beim nächsten
    Tastendruck im Feld X hielt ``move_to`` das für eine getippte Tiefe, und
    die Maßgruppe verschwand mitten im Tippen (25.09.2026). Gemessen wird
    seither an der eigenen Mündung, und die Höhe bleibt auf die letzte Stelle.
    """
    from dataclasses import replace
    from pathlib import Path

    from app.core.perceive.features import detect

    load_operations()
    mesh = MeshData.of(
        trimesh.load_mesh(Path(__file__).parent / "data" / "meshes" / "plate_holes.stl")
    )
    found = detect(mesh)
    hole = min(
        (entry for entry in found.values() if entry.kind == "hole"),
        key=lambda entry: entry.id,
    )
    tilted = replace(hole, params={**hole.params, "axis": (-6.2e-8, -1.5e-6, 1.0)})
    prepared, mouth = placement.seat_of(mesh, tilted, {**found, tilted.id: tilted})
    z = hole.params["centre"][2]
    spec = REGISTRY.get("resize_hole")

    heights = []
    for shift in (0.0, 5.0, 10.0):
        spot = placement.at_point(prepared, (mouth[0] + shift, mouth[1], mouth[2]))
        values = placement.surface_values(spec, spot, feature=tilted, mouth=mouth)
        heights.append(values["z"])

    assert heights == pytest.approx([z, z, z], abs=1e-12), "kein Wandern der Mitte mit dem Versatz"


def _chamfered_plate():
    """Die Platte mit den gefasten Mündungen, ihre Merkmale und die zwei Löcher."""
    from pathlib import Path

    from app.core.perceive.features import detect

    load_operations()
    mesh = MeshData.of(
        trimesh.load_mesh(
            Path(__file__).parent / "data" / "meshes" / "plate_chamfered_mouths.stl",
            process=True,
        )
    )
    found = detect(mesh)
    blind = next(entry for entry in found.values() if entry.kind == "hole")
    slot = next(entry for entry in found.values() if entry.kind == "slot")
    return mesh, found, blind, slot


def _clicked(mesh, found, height, point):
    """Die Fläche auf der Höhe ``height``, frisch vorbereitet wie nach einem Klick."""
    face = next(
        entry
        for entry in found.values()
        if entry.kind == "face"
        and entry.face_indices
        and abs(abs(float(entry.params["normal"][2])) - 1.0) < 1e-6
        and abs(float(entry.params["centre"][2]) - height) < 1e-6
    )
    prepared = placement.prepare_surface(mesh, face.face_indices[0], found)
    return prepared, placement.at_point(prepared, point)


def test_a_foreign_parallel_face_within_a_radius_is_not_the_own_mouth():
    """Die Fasenkorrektur gilt der eigenen Fläche, nicht jeder parallelen daneben (G5).

    Das Sackloch Ø 9 der Korpusplatte kommt von unten: Wand von z = -3,4 bis
    2,0, darüber noch 2 mm Material bis zur Oberseite — näher als ein Radius.
    Wer das Loch mit einem Klick auf die Oberseite versetzt, meint eine
    Bohrung von **dort**. Bis zum 25.09.2026 hielt ``surface_values`` die
    Oberseite für die eigene, gefaste Mündung, weil sie im Fenster bis zu
    einem Radius hinter der gemessenen lag, und behielt die Höhe der Mitte:
    Das Werkzeug saß danach 2 mm unter der Oberseite, ein Hohlraum im
    Material statt einer Bohrung. Die Oberseite hat über dem Loch keine
    Öffnung; sie ist nicht seine Mündung.
    """
    mesh, found, blind, _slot = _chamfered_plate()
    prepared, spot = _clicked(mesh, found, 4.0, (-15.0, 0.0, 4.0))

    assert placement.mouth_on(prepared, blind, found) is None, "über dem Loch ist Material"
    values = placement.surface_values(REGISTRY.get("resize_hole"), spot, feature=blind)
    half = float(blind.params["depth"]) / 2.0
    assert values["z"] == pytest.approx(4.0 - half, abs=1e-6), (
        "die Mündung der versetzten Bohrung liegt auf der geklickten Fläche"
    )


@pytest.mark.parametrize(("height", "towards"), [(4.0, 1.0), (-4.0, -1.0)])
def test_the_own_chamfered_face_found_by_a_click_keeps_the_centre(height, towards):
    """Frisch geklickt, nicht aus dem Sitz — und trotzdem die eigene Mündung (G5).

    Nach einem Klick auf eine andere Fläche und zurück ist die Fläche des
    Langlochs frisch vorbereitet, mit ihrer Öffnung, und nicht die gefüllte
    aus ``seat_of``. ``mouth_on`` erkennt sie an der Öffnung um die Achse —
    oben wie unten, beide Enden sind 0,8 mm gefast —, und die Mitte bleibt
    auf halber Höhe der Platte, statt um die Fase in die Achse zu rücken.
    """
    mesh, found, _blind, slot = _chamfered_plate()
    x, y, z = slot.params["centre"]
    prepared, spot = _clicked(mesh, found, height, (float(x), float(y) + 12.0, height))

    mouth = placement.mouth_on(prepared, slot, found)

    assert mouth == pytest.approx((x, y, height), abs=1e-6), "die Öffnung umschließt die Achse"
    values = placement.surface_values(REGISTRY.get("slot_hole"), spot, feature=slot, mouth=mouth)
    assert values["z"] == pytest.approx(z, abs=1e-6), "die Fase verschiebt die Mitte nicht"
    assert towards * (height - values["z"]) > float(slot.params["depth"]) / 2.0


def test_a_feature_without_an_axis_gets_no_distances():
    """Wo keine Trägerfläche ist, wird keine erfunden (Regel 21).

    Eine Verrundung hängt an ihrer Kante und mündet nirgends; ohne Achse und
    Tiefe gibt es keine Ebene, gegen die sich messen ließe. Die ehrliche
    Antwort ist ``None`` — der Aufrufer zeigt dann keine Maße statt falscher.
    """
    mesh, found = _plate_with()
    ohne_achse = Feature(
        id="fillet_1",
        kind="fillet",
        provenance="detected",
        params={"radius": 2.0, "centre": (10.0, 5.0, 5.0)},
    )

    assert placement.seat_of(mesh, ohne_achse, found) is None


def _bore_history(profile, kind, **values):
    """Eine echte Bohrung oder ein Langloch mit ursprünglichem Schritt."""
    if kind == "brep":
        exact_kernel()
    from app.core.scene import History, OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import FeatureRef

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Körper",
        [
            OperationDraft(
                op="create_brep_box" if kind == "brep" else "create_box",
                params={"width": 40.0, "depth": 30.0, "height": 20.0},
            )
        ],
    )
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    assert before.complete
    owner, body = next(iter(before.scene.objects.items()))
    history.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_brep_hole" if kind == "brep" else "drill_hole",
                inputs=(owner,),
                params={
                    "diameter": 6.0,
                    "depth": 8.0,
                    "z": body.mesh.bounds.maximum[2],
                    "anchor": "mouth",
                    "compensate": False,
                    **values,
                },
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    step = project.document.ops[-1]
    feature_kind = "slot" if values.get("slotted") else "hole"
    holes = [
        f
        for f in result.scene.objects[owner].features.values()
        if f.kind == feature_kind and f.created_by == step.id
    ]
    assert holes, "das echte Merkmal muss seine Herkunft tragen"
    return project, history, result, step, FeatureRef(owner, holes[0].id)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize(
    "widening",
    [
        {},
        {"widening_diameter": 10.0, "widening_depth": 2.0, "transition_angle": 180.0},
        {"widening_diameter": 10.0, "widening_depth": 2.0, "transition_angle": 90.0},
    ],
)
def test_bore_step_uses_the_real_origin_of_every_coupled_section(profile, kind, widening):
    """Grundbohrung und Aufweitung bearbeiten denselben gespeicherten Bohrungsschritt."""
    from app.core.types import FeatureRef

    project, _history, result, step, selected = _bore_history(profile, kind, **widening)
    body = result.scene.objects[selected.object_id]
    sections = [f for f in body.features.values() if f.kind in {"hole", "cone"}]
    assert len(sections) >= (2 if widening else 1)
    for section in sections:
        found = placement.bore_step_of(
            project.document,
            result.scene.objects,
            FeatureRef(body.id, section.id),
            completed=result.completed,
        )
        assert found is step
        assert found.params["depth"] == 8.0
        assert found.params["diameter"] == 6.0


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_bore_step_keeps_original_values_after_transform_and_replays_depth(profile, kind):
    """Die Schrittwerte bleiben ursprünglich; die Folgeauswertung trägt Tiefe und Undo weiter."""
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources
    from app.core.units import MAX_FACET_SAG

    project, history, result, step, selected = _bore_history(profile, kind)
    history.apply(
        "Bewegen und vergrößern",
        [
            OperationDraft(
                op="translate_object", inputs=(selected.object_id,), params={"dx": 25.0}
            ),
            OperationDraft(op="scale_object", inputs=(selected.object_id,), params={"factor": 2.0}),
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    feature = result.scene.objects[selected.object_id].features[selected.feature_id]
    assert feature.created_by == step.id
    assert feature.params["diameter"] == pytest.approx(12.0, abs=4 * MAX_FACET_SAG)
    assert feature.params["depth"] == pytest.approx(16.0)
    found = placement.bore_step_of(
        project.document, result.scene.objects, selected, completed=result.completed
    )
    assert found is step and found.params["diameter"] == 6.0
    assert found.params["depth"] == 8.0
    history.change_params(step.id, {**step.params, "depth": 6.0})
    changed = evaluate(project.document, profile, sources=ProjectSources(project))
    assert changed.complete
    hole = changed.scene.objects[selected.object_id].features[selected.feature_id]
    assert hole.params["depth"] == pytest.approx(12.0)
    history.undo()
    restored = evaluate(project.document, profile, sources=ProjectSources(project))
    assert restored.scene.objects[selected.object_id].features[selected.feature_id].params[
        "depth"
    ] == pytest.approx(16.0)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("following", ["duplicate_object", "pattern", "resize_hole"])
def test_bore_step_declines_copies_and_a_later_bore_replacement(profile, kind, following):
    """Eine einzige Auswahl darf weder ihre Kopien noch ein überholtes Ausgangsmaß ändern."""
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources
    from app.core.types import FeatureRef

    project, history, result, _step, selected = _bore_history(profile, kind)
    values = {"count": 2}
    if following == "pattern":
        values["spacing"] = 55.0
    elif following == "resize_hole":
        values = {"at_feature": selected.feature_id, "diameter": 8.0, "compensate": False}
    history.apply(
        "Danach", [OperationDraft(op=following, inputs=(selected.object_id,), params=values)]
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    holes = [
        (body.id, feature)
        for body in result.scene.objects.values()
        for feature in body.features.values()
        if feature.kind == "hole"
    ]
    assert len(holes) == (1 if following == "resize_hole" else 2)
    for owner, feature in holes:
        assert (
            placement.bore_step_of(
                project.document,
                result.scene.objects,
                FeatureRef(owner, feature.id),
                completed=result.completed,
            )
            is None
        )


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_bore_step_keeps_zero_for_a_through_hole_and_requires_a_completed_maker(profile, kind):
    """Durchgang bleibt ein Schrittwert; ein nicht gerechneter Erzeuger wird nicht angeboten."""
    project, _history, result, step, selected = _bore_history(profile, kind, depth=0.0)
    feature = result.scene.objects[selected.object_id].features[selected.feature_id]
    assert feature.params["depth"] == pytest.approx(20.0)
    found = placement.bore_step_of(
        project.document, result.scene.objects, selected, completed=result.completed
    )
    assert found is step and found.params["depth"] == 0.0
    assert (
        placement.bore_step_of(
            project.document,
            result.scene.objects,
            selected,
            completed=tuple(n for n in result.completed if n != step.id),
        )
        is None
    )


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_bore_step_declines_an_imported_hole_even_with_another_drill_in_the_document(profile, kind):
    """STL- und STEP-Erkennung haben keinen Bohrungserzeuger; Namen ersetzen keinen Beleg."""
    from app.core.brep.step import write
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources
    from app.core.types import FeatureRef, Source

    project, history, result, _step, selected = _bore_history(profile, kind)
    body = result.scene.objects[selected.object_id].mesh
    suffix = "step" if kind == "brep" else "stl"
    project.document.sources["imported"] = Source(
        id="imported", kind="import", path=f"sources/bore.{suffix}", sha256=""
    )
    project.sources["imported"] = (
        write(body) if kind == "brep" else as_mesh_data(body).raw.export(file_type="stl")
    )
    history.apply(
        "Import",
        [
            OperationDraft(
                op="load_step" if kind == "brep" else "load",
                params={"source": "imported", **({} if kind == "brep" else {"unit": "mm"})},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    body = result.scene.objects[project.document.ops[-1].outputs[0]]
    hole = next(f for f in body.features.values() if f.kind == "hole")
    assert hole.created_by is None
    assert (
        placement.bore_step_of(
            project.document,
            result.scene.objects,
            FeatureRef(body.id, hole.id),
            completed=result.completed,
        )
        is None
    )


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_bore_step_follows_the_bore_under_a_later_countersink(profile, kind):
    """Eine nachträgliche Senkung hat keinen eigenen Tiefenwert der Grundbohrung."""
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources
    from app.core.types import FeatureRef

    project, history, _result, step, selected = _bore_history(profile, kind)
    history.apply(
        "Senken",
        [
            OperationDraft(
                op="countersink_hole",
                inputs=(selected.object_id,),
                params={"diameter": 10.0, "angle": 90.0, "z": 20.0, "anchor": "mouth"},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    body = result.scene.objects[selected.object_id]
    sections = [f for f in body.features.values() if f.kind in {"hole", "cone"}]
    assert {f.kind for f in sections} == {"hole", "cone"}
    for feature in sections:
        found = placement.bore_step_of(
            project.document,
            result.scene.objects,
            FeatureRef(body.id, feature.id),
            completed=result.completed,
        )
        assert found is step
        assert found.params["depth"] == 8.0


@pytest.mark.parametrize("changed_before_copy", [False, True])
@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_bore_step_checks_the_copies_actual_history_not_the_later_original(
    profile, changed_before_copy, kind
):
    """Die einzig lebende Kopie stammt vom damaligen Stand, nicht vom später geänderten Original."""
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources
    from app.core.types import FeatureRef

    project, history, _result, step, selected = _bore_history(profile, kind)
    change = OperationDraft(
        op="resize_hole",
        inputs=(selected.object_id,),
        params={"at_feature": selected.feature_id, "diameter": 8.0, "compensate": False},
    )
    if changed_before_copy:
        history.apply("Original vorher ändern", [change])
    history.apply(
        "Kopieren",
        [OperationDraft(op="duplicate_object", inputs=(selected.object_id,), params={"count": 2})],
    )
    copied = project.document.ops[-1].outputs[-1]
    if not changed_before_copy:
        history.apply("Nur das Original ändern", [change])
    history.apply(
        "Original entfernen", [OperationDraft(op="delete_object", inputs=(selected.object_id,))]
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete and set(result.scene.objects) == {copied}
    hole = next(f for f in result.scene.objects[copied].features.values() if f.kind == "hole")
    found = placement.bore_step_of(
        project.document,
        result.scene.objects,
        FeatureRef(copied, hole.id),
        completed=result.completed,
    )
    assert found is (None if changed_before_copy else step)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_bore_originators_do_not_relabel_existing_holes_when_another_is_drilled(profile, kind):
    """Neue native Kennungen sind keine Erzeugerkennung; beide echten Bohrungen bleiben getrennt."""
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources
    from app.core.types import FeatureRef

    project, history, _result, first, selected = _bore_history(profile, kind)
    history.apply(
        "Weitere Bohrung",
        [
            OperationDraft(
                op=first.op, inputs=(selected.object_id,), params={**first.params, "x": -10.0}
            )
        ],
    )
    second = project.document.ops[-1]
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    holes = sorted(
        (f for f in result.scene.objects[selected.object_id].features.values() if f.kind == "hole"),
        key=lambda f: f.params["centre"][0],
    )
    assert len(holes) == 2
    assert [f.created_by for f in holes] == [second.id, first.id]
    # Die zweite Formänderung liegt hinter der ersten: Ohne deren fachlichen
    # Anschluss wird der alte Tiefeneditor nicht als aktuelle Maßanzeige benutzt.
    assert (
        placement.bore_step_of(
            project.document,
            result.scene.objects,
            FeatureRef(selected.object_id, holes[1].id),
            completed=result.completed,
        )
        is None
    )
    assert (
        placement.bore_step_of(
            project.document,
            result.scene.objects,
            FeatureRef(selected.object_id, holes[0].id),
            completed=result.completed,
        )
        is second
    )


def test_bore_originators_leave_ambiguous_native_candidates_unclaimed(profile, monkeypatch):
    """Auch frische native Flächen mit gleichen Namen sind bei Mehrdeutigkeit kein Erzeugerbeleg."""
    from importlib import import_module

    from app.core.perceive.matching import MatchResult
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources

    project, history, _result, first, selected = _bore_history(profile, "brep")
    module = import_module("app.core.scene.evaluate")
    original = module.match

    def contested(old, new, centre, diagonal, *, check_cancelled=None):
        holes = tuple(name for name, feature in new.items() if feature.kind == "hole")
        if len(holes) > 1:
            old_hole = next(name for name, feature in old.items() if feature.kind == "hole")
            return MatchResult(ambiguous={old_hole: holes}, fresh=holes)
        return original(old, new, centre, diagonal, check_cancelled=check_cancelled)

    monkeypatch.setattr(module, "match", contested)
    # Erzwungen wird die Mehrdeutigkeit, die übrig bleibt: Die Lage der
    # Oberfläche entschiede die erfundene sonst gleich wieder — am exakten
    # Körper fragt die Auswertung sie ebenso (``matching.settled_twins``).
    monkeypatch.setattr(module, "settled_twins", lambda result, *_, **__: result)
    history.apply(
        "Weitere Bohrung",
        [
            OperationDraft(
                op=first.op, inputs=(selected.object_id,), params={**first.params, "x": -10.0}
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    holes = [
        f for f in result.scene.objects[selected.object_id].features.values() if f.kind == "hole"
    ]
    assert len(holes) == 2
    assert all(f.created_by is None for f in holes)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("depth", [0.0, 8.0])
def test_bore_action_edits_original_values_and_preserves_hidden_params(profile, kind, depth):
    """Die Tiefenhandlung bearbeitet trotz Skalierung den vollständigen ursprünglichen Auftrag."""
    from app.core.perceive.actions import bore_action
    from app.core.registry import REGISTRY
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources

    project, history, _result, step, selected = _bore_history(profile, kind, depth=depth)
    saved = dict(step.params)
    history.apply(
        "Vergrößern",
        [OperationDraft(op="scale_object", inputs=(selected.object_id,), params={"factor": 2.0})],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    original = placement.bore_step_of(
        project.document, result.scene.objects, selected, completed=result.completed
    )
    assert original is step
    action = bore_action(original, REGISTRY.get(original.op))
    fields = {field.name: field for field in action.fields}
    assert action.step == step.id
    assert action.op == step.op
    assert "ursprünglichen Schritt" in str(action.title)
    assert "ursprünglichen Schrittwerte" in str(action.note)
    assert list(fields)[:2] == ["diameter", "depth"]
    assert fields["diameter"].value == pytest.approx(6.0)
    assert fields["depth"].value == pytest.approx(depth)
    assert fields["depth"].minimum == pytest.approx(0.0)
    assert fields["slotted"].kind == "bool"
    # Die Richtung des Langlochs steht seit RM-513 hinten — im Dialog wie hier.
    assert "slot_angle" not in fields
    assert not {"x", "y", "z", "nx", "anchor", "compensate"} & fields.keys()
    proposed = {**dict(action.fixed), **{name: field.value for name, field in fields.items()}}
    assert all(proposed[name] == value for name, value in saved.items())
    assert step.params == saved
    proposed["depth"] = 6.0
    history.change_params(step.id, proposed)
    changed = evaluate(project.document, profile, sources=ProjectSources(project))
    assert changed.complete
    hole = changed.scene.objects[selected.object_id].features[selected.feature_id]
    assert hole.params["depth"] == pytest.approx(12.0)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_bore_action_preserves_expressions_in_the_original_step(profile, kind):
    """Ein benanntes Tiefenmaß bleibt Ausdruck, auch wenn die Bohrung anderswo gemessen wird."""
    from app.core.perceive.actions import bore_action
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources
    from app.core.types import Parameter

    project, history, _result, step, selected = _bore_history(profile, kind)
    project.document.parameters["bore_depth"] = Parameter("bore_depth", 4.0)
    history.change_params(step.id, {**step.params, "depth": "@bore_depth * 2"})
    current = project.document.ops[-1]
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    assert result.scene.objects[selected.object_id].features[selected.feature_id].params[
        "depth"
    ] == pytest.approx(8.0)
    action = bore_action(current, REGISTRY.get(current.op))
    assert (
        next(field.value for field in action.fields if field.name == "depth") == "@bore_depth * 2"
    )
    assert current.params["depth"] == "@bore_depth * 2"


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize(
    "values, mouth, outward",
    [
        ({"z": 20.0, "depth": 8.0}, (0.0, 0.0, 20.0), (0.0, 0.0, 1.0)),
        ({"z": 0.0, "depth": 8.0}, (0.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
        ({"z": 16.0, "depth": 8.0, "anchor": "centre"}, (0.0, 0.0, 20.0), (0.0, 0.0, 1.0)),
        ({"z": 0.0, "depth": 0.0}, (0.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
        ({"z": 10.0, "depth": 0.0}, (0.0, 0.0, 20.0), (0.0, 0.0, 1.0)),
        ({"z": 35.0, "depth": 0.0}, (0.0, 0.0, 20.0), (0.0, 0.0, 1.0)),
    ],
)
def test_original_bore_seat_uses_the_historical_body_and_anchor(
    profile, kind, values, mouth, outward
):
    """Die wirkliche Bohrung erhält ihre ursprüngliche Fläche ohne erneuten Modellklick."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources

    project, history, _result, step, selected = _bore_history(profile, kind, **values)
    saved = dict(step.params)
    history.undo()
    prefix = evaluate(project.document, profile, sources=ProjectSources(project))
    assert prefix.complete
    body = prefix.scene.objects[selected.object_id]
    assert not any(feature.kind == "hole" for feature in body.features.values())
    seat = placement.seat_for_bore_step(
        as_mesh_data(body.mesh), REGISTRY.get(step.op), step.params, body.features
    )
    assert seat is not None
    prepared, point = seat
    assert point == pytest.approx(mouth)
    assert prepared.frame.normal == pytest.approx(outward)
    assert prepared.planar
    assert sorted(
        edge.distance for edge in placement.at_point(prepared, point).edges
    ) == pytest.approx([15.0, 20.0])
    assert step.params == saved


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_original_bore_seat_follows_a_rotated_prefix_face(profile, kind):
    """Die ursprüngliche freie Bohrrichtung trifft die gedrehte Fläche desselben Eingangs."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources

    project, history, _result, step, selected = _bore_history(profile, kind)
    history.undo()
    history.apply(
        "Kippen",
        [
            OperationDraft(
                op="rotate_object",
                inputs=(selected.object_id,),
                params={"axis": "x", "angle": 30.0, "about": "origin", "keep_on_bed": False},
            )
        ],
    )
    prefix = evaluate(project.document, profile, sources=ProjectSources(project))
    assert prefix.complete
    body = prefix.scene.objects[selected.object_id]
    outward = (0.0, -0.5, math.sqrt(3.0) / 2.0)
    mouth = (0.0, -10.0, 10.0 * math.sqrt(3.0))
    params = {**step.params, **dict(zip(("x", "y", "z"), mouth, strict=True))}
    params.update(zip(("nx", "ny", "nz"), outward, strict=True))
    history.apply("Bohrung", [OperationDraft(op=step.op, inputs=(body.id,), params=params)])
    drilled = evaluate(project.document, profile, sources=ProjectSources(project))
    assert drilled.complete
    assert any(f.kind == "hole" for f in drilled.scene.objects[body.id].features.values())
    seat = placement.seat_for_bore_step(
        as_mesh_data(body.mesh), REGISTRY.get(step.op), params, body.features
    )
    assert seat is not None
    prepared, point = seat
    assert point == pytest.approx(mouth)
    assert prepared.frame.normal == pytest.approx(outward)
    assert sorted(
        edge.distance for edge in placement.at_point(prepared, point).edges
    ) == pytest.approx([15.0, 20.0])


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_original_bore_seat_declines_no_hit_and_separate_material_columns(profile, kind):
    """Ein leerer Achsstrahl oder zwei getrennte Eintrittsflächen erzeugen keinen geratenen Sitz."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources

    project, history, _result, step, selected = _bore_history(profile, kind)
    history.undo()
    prefix = evaluate(project.document, profile, sources=ProjectSources(project))
    body = prefix.scene.objects[selected.object_id]
    mesh = as_mesh_data(body.mesh)
    spec = REGISTRY.get(step.op)
    assert (
        placement.seat_for_bore_step(mesh, spec, {**step.params, "x": 100.0}, body.features) is None
    )
    assert (
        placement.seat_for_bore_step(mesh, spec, {**step.params, "z": 25.0}, body.features) is None
    )
    other = mesh.raw.copy()
    other.apply_translation((0.0, 0.0, 40.0))
    disconnected = MeshData.of(trimesh.util.concatenate([mesh.raw, other]))
    assert (
        placement.seat_for_bore_step(disconnected, spec, {**step.params, "depth": 0.0}, {}) is None
    )


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("depth", [0.0, 8.0])
@pytest.mark.parametrize("shape", ["round", "widened", "slotted"])
def test_bore_twins_share_surface_values_tool_and_actual_cut(profile, kind, depth, shape):
    """Beide Bohrwege nehmen dieselbe Fläche und denselben Werkzeugumriss bis zum echten Schnitt."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources

    project, history, _result, step, selected = _bore_history(profile, kind)
    history.undo()
    prefix = evaluate(project.document, profile, sources=ProjectSources(project))
    assert prefix.complete
    body = prefix.scene.objects[selected.object_id]
    mesh = as_mesh_data(body.mesh)
    spec = REGISTRY.get(step.op)
    assert placement.supports_surface_placement(spec)
    seat = placement.seat_for_bore_step(mesh, spec, step.params, body.features)
    assert seat is not None
    prepared, mouth = seat
    hit = placement.at_point(prepared, mouth)
    values = {**step.params, "depth": depth, "anchor": "centre"}
    if shape == "widened":
        values.update(widening_diameter=10.0, widening_depth=2.0, transition_angle=90.0)
    elif shape == "slotted":
        values.update(slotted=True, slot_length=12.0, slot_angle=30.0)
    placed = placement.surface_values(spec, hit, source=body)
    assert placed["anchor"] == "mouth"
    assert [placed[name] for name in ("x", "y", "z")] == pytest.approx((0.0, 0.0, 20.0))
    assert [placed[name] for name in ("nx", "ny", "nz")] == pytest.approx((0.0, 0.0, 1.0))
    values.update(placed)
    tool = placement.prepare_tool(spec, values, profile, source=body)
    assert tool.mesh.is_watertight
    assert tool.mesh.bounds.maximum[2] == pytest.approx(0.0)
    tool_depth = depth or body.mesh.bounds.diagonal
    assert tool.mesh.bounds.minimum[2] == pytest.approx(-tool_depth)
    assert placement.mouth_outline(tool)
    other = REGISTRY.get("drill_hole" if kind == "brep" else "drill_brep_hole")
    twin_tool = placement.prepare_tool(other, values, profile, source=body)
    assert twin_tool.mesh.raw.vertices == pytest.approx(tool.mesh.raw.vertices, abs=1e-12)
    assert np.array_equal(twin_tool.mesh.raw.faces, tool.mesh.raw.faces)
    history.apply(
        "Bohrung auf Fläche", [OperationDraft(op=spec.name, inputs=(body.id,), params=values)]
    )
    changed = evaluate(project.document, profile, sources=ProjectSources(project))
    assert changed.complete
    changed_body = changed.scene.objects[body.id]
    assert changed_body.mesh.is_watertight
    drilled_depth = depth or 20.0
    expected = math.pi * 9.0 * drilled_depth
    if shape == "widened":
        expected += math.pi * (32.0 + 44.0 / 3.0)
    elif shape == "slotted":
        expected += 36.0 * drilled_depth
    assert body.mesh.volume - changed_body.mesh.volume == pytest.approx(expected, rel=0.015)


def test_a_prepared_face_is_remembered_per_mesh_triangle_and_feature_names():
    """Dieselbe Fläche wird am selben Netz einmal vorbereitet (RM-232).

    ``seat_of`` fragt für jede Bohrung auf einer Fläche deren erstes Dreieck,
    und an der dichten Platte kostete die Oberseite jedes Mal 105 ms. Die
    Antwort gehört zu Netz, Dreieck und den Namen der Merkmale — ihre
    Mittenbezüge tragen die Namen.
    """
    mesh, found = _plate_with()
    face = _top(mesh)

    first = placement.prepare_surface(mesh, face, found)

    assert placement.prepare_surface(mesh, face, found) is first, "dieselbe Frage, dieselbe Antwort"
    renamed = {f"renamed_{name}": entry for name, entry in found.items()}
    assert placement.prepare_surface(mesh, face, renamed) is not first, "andere Namen, neue Antwort"
    other = MeshData.of(mesh.raw.copy())
    assert placement.prepare_surface(other, face, found) is not first, "anderes Netz, neue Antwort"


def test_swapped_feature_names_do_not_read_a_remembered_face():
    """Dieselben Namen an vertauschten Bohrungen sind eine neue Frage.

    Der Merker von ``prepare_surface`` hing an Netz, Dreieck und den **Namen**
    der Merkmale. Dasselbe Netz kann aber nach einer neu beantworteten
    Zuordnung dieselben Namen an vertauschten Merkmalen tragen — das Netz
    kommt dann unverändert aus dem Ergebniscache. Die gemerkte Fläche nannte
    danach die eigene Mitte einer Bohrung als die der anderen, und ``seat_of``
    nahm die falsche heraus: Im Bild stand der Abstand zur eigenen Mitte, null,
    und der zur Nachbarbohrung fehlte (dieselbe Zusage wie
    ``_others``, Robert, 10.09.2026).
    """
    from dataclasses import replace

    from app.core.geom.prepare import drill
    from app.core.knowledge import profiles
    from app.core.perceive.features import detect

    load_operations()
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    mesh = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    for position in ((10.0, 5.0, 5.0), (-15.0, -5.0, 5.0)):
        mesh = drill(
            mesh, profile=profile, position=position, axis="z", diameter=6.0, compensate=False
        ).mesh
    found = detect(mesh)
    first, second = sorted(
        (entry for entry in found.values() if entry.kind == "hole"), key=lambda entry: entry.id
    )
    swapped = {
        **found,
        first.id: replace(second, id=first.id),
        second.id: replace(first, id=second.id),
    }

    before, _mouth = placement.seat_of(mesh, found[first.id], found)
    after, mouth = placement.seat_of(mesh, swapped[first.id], swapped)

    def at_the_mouth(feature: Feature) -> tuple[float, float]:
        centre = feature.params["centre"]
        return (float(centre[0]), float(centre[1]))

    (other_before,) = before.centres
    assert other_before[0] == second.id
    assert other_before[1][:2] == pytest.approx(at_the_mouth(second))
    assert mouth[:2] == pytest.approx(at_the_mouth(second)), "die Bohrung heißt jetzt anders"
    (other_after,) = after.centres
    assert other_after[0] == second.id
    assert other_after[1][:2] == pytest.approx(at_the_mouth(first)), (
        "die andere Bohrung, nicht die eigene Mitte"
    )


def _preview_matrix(
    operation,
    normal,
    *,
    monkeypatch,
    feature_axis=None,
    slotted=False,
    angle_degrees=0.0,
    measured_frame=False,
    tool_axis=None,
    source=None,
    axis="z",
    surface_point=(3.0, -4.0, 5.0),
    tool_context=None,
    tool_ready=True,
    tool_busy=False,
    capture_projection=None,
    request_flow=None,
    captured_items=None,
    deepening=False,
):
    """Die Matrix am echten Zuweisungspunkt in ``PlacementFlow.redraw`` erheben."""
    from types import MethodType, SimpleNamespace

    from PySide6.QtCore import QRect

    from app.core.sketch.planes import frame_of
    from app.ui import placement_flow
    from app.ui.placement_flow import PlacementFlow
    from tests.ui_helpers import PlacementItem

    feature = None if feature_axis is None else SimpleNamespace(params={"axis": feature_axis})
    surface = SimpleNamespace(normal=normal, frame=frame_of(normal, (0.0, 0.0, 0.0)))
    surface.point = surface_point
    surface.edges = ()
    surface.centres = ()

    class Widget:
        def adjustSize(self):  # noqa: N802 - Qt-Protokollname des Testdoppels
            pass

        def hide(self):
            pass

        def height(self):
            return 1

        def isVisibleTo(self, _parent):  # noqa: N802 - Qt-Protokollname des Testdoppels
            return False

        def move(self, *_args):
            pass

        def raise_(self):
            pass

        def setMaximumWidth(self, _width):  # noqa: N802 - Qt-Protokollname des Testdoppels
            pass

        def setVisible(self, _visible):  # noqa: N802 - Qt-Protokollname des Testdoppels
            pass

        def setText(self, _text):  # noqa: N802 - Qt-Protokollname des Testdoppels
            pass

        def show(self):
            pass

        def sizeHint(self):  # noqa: N802 - Qt-Protokollname des Testdoppels
            return SimpleNamespace(height=lambda: 1)

        def width(self):
            return 1

    class RendererStub:
        def __init__(self):
            self.items = []

        def add_surface(self, *_args, **_kwargs):
            item = CapturedMatrix()
            self.items.append(item)
            if captured_items is not None:
                captured_items.append(item)
            return item

        def world_to_display(self, point):
            if capture_projection is not None:
                capture_projection.append(tuple(float(value) for value in point))
                raise MatrixWasSetError
            return float(point[0]), float(point[1]), float(point[2])

    class ViewportStub:
        def __init__(self, renderer):
            self.renderer = renderer
            self._diff_palette = "blue_orange"
            self._object_colour = "blue"

        def rect(self):
            return QRect(0, 0, 640, 480)

        def slot_drag_waits(self):
            return False

        def view_point_of(self, point, _object_id):
            return point

        def grip_placement(self, *_args, **_kwargs):
            pass

        def _device_ratio(self):
            return 1.0

        def gizmo_reach(self):
            return None

    class CapturedMatrix(PlacementItem):
        def set_matrix(self, matrix):
            super().set_matrix(matrix)
            if capture_projection is None:
                raise MatrixWasSetError

    class MatrixWasSetError(Exception):
        pass

    renderer = RendererStub()
    tool = CapturedMatrix() if tool_ready and request_flow is None else None
    context = tool_context if tool_ready else None
    if request_flow is None:
        flow = SimpleNamespace(
            active=True,
            _disposed=False,
            _redraw_held=False,
            viewport=ViewportStub(renderer),
            window=SimpleNamespace(),
            session=SimpleNamespace(result_current=True),
            spec_of=lambda: SimpleNamespace(name=operation),
            dialog=SimpleNamespace(
                values=lambda: {
                    "slotted": slotted,
                    "slot_angle": angle_degrees,
                    "measured_frame": measured_frame,
                    "axis": axis,
                }
            ),
            _source_feature=lambda: (source, feature),
            _bar=Widget(),
            _surface=surface,
            _display_ready=lambda: True,
            _change_op=None,
            _showing_input=False,
            _tool_context=context if context is not None else (object() if tool_ready else None),
            _tool_axis=getattr(context, "outward_axis", None) or tool_axis,
            _tool_angle=getattr(context, "angle", None)
            if getattr(context, "angle", None) is not None
            else angle_degrees,
            _tool_busy=tool_busy,
            _tool=tool,
            _addition=None,
            _accept=SimpleNamespace(setEnabled=lambda _enabled: None),
            _canvas=SimpleNamespace(hide=lambda: None),
            _measures=[],
            _reference_boxes=[Widget(), Widget(), Widget()],
            _centre=Widget(),
            _centre_id="",
            _centre_measures=[],
            _depth_measure=Widget(),
            _deepening=deepening,
            _measure_group=None,
            _distance_valid=True,
            _show_bar=lambda: None,
            _refresh_measure_actions=lambda: None,
            _size_measure_fields=lambda _room: None,
            _reference_titles=lambda _at=None: {},
            _seat_is_coming=lambda: False,
            _object_id="object",
            _frozen=False,
            _seated_at_feature=False,
            _field_slots={},
            _rest=Widget(),
        )
    else:
        flow = request_flow
        flow.active = True
        flow._disposed = False
        flow._redraw_held = False
        flow.viewport = ViewportStub(renderer)
        flow.window = SimpleNamespace()
        flow.session.result_current = True
        flow._bar = Widget()
        flow._surface = surface
        flow._display_ready = lambda: True
        flow._change_op = None
        flow._showing_input = False
        flow._tool = None
        flow._addition = None
        flow._accept = SimpleNamespace(setEnabled=lambda _enabled: None)
        flow._canvas = SimpleNamespace(hide=lambda: None)
        flow._measures = []
        flow._reference_boxes = [Widget(), Widget(), Widget()]
        flow._centre = Widget()
        flow._centre_id = ""
        flow._centre_measures = []
        flow._depth_measure = Widget()
        flow._deepening = deepening
        flow._measure_group = None
        flow._distance_valid = True
        flow._show_bar = lambda: None
        flow._refresh_measure_actions = lambda: None
        flow._size_measure_fields = lambda _room: None
        flow._reference_titles = lambda _at=None: {}
        flow._seat_is_coming = lambda: False
        flow._object_id = "object"
        flow._frozen = False
        flow._seated_at_feature = False
        flow._field_slots = {}
        flow._rest = Widget()
        flow._tool_legend = Widget()
        flow._depth_name = lambda: "depth"
        flow._depth_now = lambda _name: 1.0
        flow._material_below = lambda: 2.0
    flow._tool_axes = MethodType(PlacementFlow._tool_axes, flow)
    monkeypatch.setattr(placement_flow, "QApplication", SimpleNamespace(focusWidget=lambda: None))
    if capture_projection is None:
        monkeypatch.setattr(placement_flow.placement, "mouth_outline", lambda _tool: ())

    if request_flow is None:
        with pytest.raises(MatrixWasSetError):
            PlacementFlow.redraw(flow, draw=False)
    else:
        flow.redraw = lambda: PlacementFlow.redraw(flow, draw=False)
        compute, done = flow._placement_callbacks[0]
        with pytest.raises(MatrixWasSetError):
            done(compute())
    if tool is not None:
        return tool.matrix
    if captured_items:
        return captured_items[0].matrix
    return None


def _requested_tool_for_preview(
    operation, values, source, profile, monkeypatch, *, worker_reply="ready"
):
    """Einen echten Werkzeugauftrag bis zum Rückruf der Vorschau ausführen."""
    from types import SimpleNamespace

    from app.core.registry import REGISTRY
    from app.ui import placement_flow
    from app.ui.placement_flow import PlacementFlow
    from tests.ui_helpers import PlacementItem

    entered = dict(values)
    requests = []
    callbacks = []

    class RendererStub:
        def add_surface(self, *_args, **_kwargs):
            return PlacementItem()

    def placement_async(compute, done, _failed, _refused=None):
        requests.append(None)
        if worker_reply == "pending":
            callbacks.append((compute, done))
        elif worker_reply == "refused":
            done(None)
        else:
            done(compute())

    dialog = SimpleNamespace(
        values=lambda: dict(entered), take_placement=lambda changed: entered.update(changed)
    )
    flow = SimpleNamespace(
        active=True,
        _disposed=False,
        _tool_busy=False,
        _tool_again=False,
        _tool_context=None,
        _tool_axis=None,
        _tool_angle=None,
        _tool_key="",
        _epoch=1,
        spec_of=lambda: REGISTRY.get(operation),
        _source_feature=lambda: (source, source.features.get(entered.get("at_feature", ""))),
        dialog=dialog,
        session=SimpleNamespace(
            profile=profile,
            project=SimpleNamespace(document=SimpleNamespace(parameters={})),
            placement_async=placement_async,
        ),
        viewport=SimpleNamespace(
            renderer=RendererStub(), _diff_palette="blue_orange", _object_colour="blue"
        ),
        _remove_tools=lambda: None,
        _set_values=lambda: None,
        _tool=None,
        _addition=None,
        _refused_note=None,
        _note=SimpleNamespace(text=lambda: "", setText=lambda _text: None),
        _accept_pending=False,
        redraw=lambda: None,
    )
    flow._placement_requests = requests
    flow._placement_callbacks = callbacks
    monkeypatch.setattr(placement_flow, "isValid", lambda _flow: True)
    PlacementFlow._request_tool(flow)
    assert (flow._tool_context is not None) is (worker_reply == "ready")
    return flow


@pytest.mark.parametrize("operation", ["slot_hole", "resize_hole"])
@pytest.mark.parametrize(
    ("tilt_degrees", "deepening", "expected_visible"),
    [
        (1.0, False, False),
        (2.0, False, False),
        (90.0, False, True),
        (1.0, True, True),
    ],
    ids=["1-grad", "2-grad", "parallel", "depth"],
)
def test_requested_slot_angle_and_mouth_plane_reach_redraw(
    operation, tilt_degrees, deepening, expected_visible, profile, monkeypatch
):
    """Werkzeugrückruf, Umriss und Sichtbarkeit laufen im selben Vorschaufluss."""
    from types import SimpleNamespace

    from app.core.geom.prepare import slot_angle_from_measured_frame, slot_frame
    from app.core.geom.prepare_ops import slot_angle_of
    from app.ui.placement_flow import _mouth_outline_on_surface

    axis = (
        math.sin(math.radians(tilt_degrees)),
        0.0,
        math.cos(math.radians(tilt_degrees)),
    )
    feature_frame = slot_frame(axis, (0.0, 0.0, 0.0))
    feature_angle = 27.0
    direction = tuple(
        math.cos(math.radians(feature_angle)) * feature_frame.x_axis[index]
        + math.sin(math.radians(feature_angle)) * feature_frame.y_axis[index]
        for index in range(3)
    )
    feature = SimpleNamespace(
        id="slot_1",
        kind="slot",
        params={
            "axis": axis,
            "direction": direction,
            "centre": (0.0, 0.0, 0.0),
            "diameter": 6.0,
            "depth": 8.0,
            "length": 20.0,
            "travel": 14.0,
        },
    )
    source = SimpleNamespace(
        kind="mesh",
        material=None,
        material_slots=(),
        mesh=MeshData.of(trimesh.creation.box((30.0, 30.0, 8.0))),
        features={feature.id: feature},
    )
    spec = REGISTRY.get(operation)
    values = {
        entry.name: entry.default for entry in spec.params.spec() if entry.default is not None
    }
    values["at_feature"] = feature.id
    if operation == "slot_hole":
        values.update(slot_length=20.0, slot_angle=33.0, measured_frame=True)
        expected_angle = slot_angle_from_measured_frame(axis, 33.0)
    else:
        values["diameter"] = 6.0
        expected_angle = slot_angle_of(feature, axis)

    flow = _requested_tool_for_preview(
        operation, values, source, profile, monkeypatch, worker_reply="pending"
    )
    assert flow._tool_context is None
    assert flow._tool_busy

    surface_normal = (0.0, 0.0, -1.0)
    surface_point = (12.0, 0.0, 0.0)
    projected: list[tuple[float, float, float]] = []
    captured_items = []
    matrix = _preview_matrix(
        operation,
        surface_normal,
        feature_axis=axis,
        measured_frame=operation == "slot_hole",
        angle_degrees=33.0 if operation == "slot_hole" else feature_angle,
        source=source,
        surface_point=surface_point,
        capture_projection=projected,
        request_flow=flow,
        captured_items=captured_items,
        deepening=deepening,
        monkeypatch=monkeypatch,
    )
    assert flow._tool_context is not None
    assert not flow._tool_busy
    assert flow._tool_context.angle == pytest.approx(expected_angle)
    assert flow._tool_angle == pytest.approx(expected_angle)
    assert captured_items
    assert all(item.visible is expected_visible for item in captured_items)
    basis = matrix[:3, :3]
    preview_direction = basis @ np.asarray(
        (math.cos(math.radians(expected_angle)), math.sin(math.radians(expected_angle)), 0.0)
    )
    expected_direction = np.asarray(feature_frame.x_axis) * math.cos(
        math.radians(expected_angle)
    ) + np.asarray(feature_frame.y_axis) * math.sin(math.radians(expected_angle))

    assert preview_direction == pytest.approx(expected_direction, abs=1e-12)

    if expected_visible:
        assert projected == [surface_point]
        assert flow._canvas.outline == []
    else:
        outline = np.asarray(placement.mouth_outline(flow._tool_context), dtype=np.float64)
        local_offsets = outline @ basis[:, :2].T
        axis_normal = float(np.dot(basis[:, 2], surface_normal))
        expected_points = (
            np.asarray(surface_point)
            + local_offsets
            - np.outer((local_offsets @ np.asarray(surface_normal)) / axis_normal, basis[:, 2])
        )
        plane_distances = (expected_points - np.asarray(surface_point)) @ np.asarray(surface_normal)
        assert np.max(np.abs(plane_distances)) == pytest.approx(0.0, abs=1e-10)
        assert projected == [pytest.approx(tuple(expected_points[0]), abs=1e-10)]
        surface_outline = _mouth_outline_on_surface(
            tuple((float(coordinate[0]), float(coordinate[1])) for coordinate in outline),
            surface_point,
            surface_normal,
            tuple(float(value) for value in basis[:, 0]),
            tuple(float(value) for value in basis[:, 1]),
            tuple(float(value) for value in basis[:, 2]),
        )
        assert np.asarray(surface_outline) == pytest.approx(expected_points, abs=1e-10)


def test_parallel_tool_axis_has_no_finite_mouth_outline_on_surface():
    """Eine achsparallele Ebene besitzt keinen endlichen Umriss entlang der Werkzeugachse."""
    from app.ui.placement_flow import _mouth_outline_on_surface

    assert (
        _mouth_outline_on_surface(
            ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0)),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 1.0, 0.0),
        )
        == ()
    )


@pytest.mark.parametrize("operation", ["slot_hole", "resize_hole"])
def test_slot_redraw_projects_the_real_prepared_mouth_outline(operation, profile, monkeypatch):
    """Der vollständige Umrisspfad verarbeitet Float-Koordinaten als Vektoren."""
    from app.core.geom.prepare import drill_tool, slot_frame
    from app.core.scene import placement
    from app.core.scene.placement import PlacementTool

    angle = 23.0
    tool = PlacementTool(
        drill_tool(
            diameter=5.0,
            depth=8.0,
            profile=profile,
            compensate=False,
            slot_length=20.0,
            slot_angle=angle,
        ),
        angle=angle,
    )
    outline = placement.mouth_outline(tool)
    assert len(outline) >= 3

    point = (3.0, -4.0, 5.0)
    projected: list[tuple[float, float, float]] = []
    _preview_matrix(
        operation,
        (0.0, 0.0, 1.0),
        feature_axis=(0.0, 0.0, 1.0),
        angle_degrees=angle,
        surface_point=point,
        tool_context=tool,
        capture_projection=projected,
        monkeypatch=monkeypatch,
    )

    frame = slot_frame((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    u, v = outline[0]
    expected = np.asarray(point) + np.asarray(frame.x_axis) * u + np.asarray(frame.y_axis) * v
    assert projected == [pytest.approx(tuple(expected))]


@pytest.mark.parametrize("worker_reply", ["pending", "refused"])
def test_measured_frame_redraw_waits_for_a_resolved_tool_axis(worker_reply, profile, monkeypatch):
    """Wartende und abgelehnte Arbeiter lassen die Flächenmaße weiterzeichnen."""
    from types import SimpleNamespace

    values = {
        entry.name: entry.default
        for entry in REGISTRY.get("drill_hole").params.spec()
        if entry.default is not None
    }
    values.update(
        x=3.0,
        y=0.0,
        z=0.0,
        axis="x",
        nx=0.0,
        ny=0.0,
        nz=0.0,
        slotted=True,
        slot_length=20.0,
        measured_frame=True,
    )
    source = SimpleNamespace(
        kind="mesh",
        material=None,
        material_slots=(),
        mesh=MeshData.of(trimesh.creation.box()),
        features={},
    )
    flow = _requested_tool_for_preview(
        "drill_hole",
        values,
        source,
        profile,
        monkeypatch,
        worker_reply=worker_reply,
    )
    assert flow._tool_context is None
    assert flow._tool_axis is None
    assert flow._tool_busy is (worker_reply == "pending")
    if worker_reply == "refused":
        assert flow._refused_note is not None

    surface_point = (3.0, -4.0, 5.0)
    projected: list[tuple[float, float, float]] = []
    _preview_matrix(
        "drill_hole",
        (-1.0, 0.0, 0.0),
        slotted=True,
        measured_frame=True,
        axis="x",
        surface_point=surface_point,
        tool_ready=False,
        tool_busy=flow._tool_busy,
        capture_projection=projected,
        monkeypatch=monkeypatch,
    )
    assert projected == [surface_point]


def test_turning_off_slot_keeps_a_migrated_drill_axis(profile, monkeypatch):
    """Eine runde Altbohrung bleibt in der Richtung des gespeicherten Kerns."""
    from types import SimpleNamespace

    axis = (math.sin(math.radians(10.0)), 0.0, math.cos(math.radians(10.0)))
    source = SimpleNamespace(
        kind="mesh",
        material=None,
        material_slots=(),
        mesh=MeshData.of(trimesh.creation.box((30.0, 30.0, 8.0))),
        features={},
    )
    spec = REGISTRY.get("drill_hole")
    values = {
        entry.name: entry.default for entry in spec.params.spec() if entry.default is not None
    }
    values.update(
        x=0.0,
        y=0.0,
        z=0.0,
        axis="z",
        nx=axis[0],
        ny=axis[1],
        nz=axis[2],
        slotted=False,
        measured_frame=True,
    )
    flow = _requested_tool_for_preview("drill_hole", values, source, profile, monkeypatch)
    assert flow._tool_axis == pytest.approx(axis)

    matrix = _preview_matrix(
        "drill_hole",
        (0.0, 0.0, 1.0),
        measured_frame=True,
        tool_axis=flow._tool_axis,
        source=source,
        tool_context=flow._tool_context,
        monkeypatch=monkeypatch,
    )
    assert matrix[:3, 2] == pytest.approx(axis)


def test_legacy_zero_axis_uses_core_direction_and_refreshes_after_moving(profile, monkeypatch):
    """Position, Achswahl und Kernpfad bestimmen den Vorschauwinkel gemeinsam."""
    from types import MethodType, SimpleNamespace

    from app.core.geom.mesh import MeshData
    from app.core.scene.placement import PlacementTool
    from app.ui.placement_flow import PlacementFlow

    body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    cutter = trimesh.creation.box(extents=(9.0, 6.0, 6.0))
    cutter.apply_translation((-1.5, 0.0, 0.0))
    pocket = MeshData.of(trimesh.boolean.difference([body, cutter], engine="manifold"))
    source = SimpleNamespace(
        kind="mesh",
        material=None,
        material_slots=(),
        mesh=MeshData.of(body),
        features={},
    )
    spec = REGISTRY.get("drill_hole")
    values = {
        entry.name: entry.default for entry in spec.params.spec() if entry.default is not None
    }
    values.update(
        x=3.0,
        y=0.0,
        z=0.0,
        axis="x",
        nx=0.0,
        ny=0.0,
        nz=0.0,
        slotted=True,
        slot_length=20.0,
        slot_angle=0.0,
        measured_frame=True,
    )
    flow = _requested_tool_for_preview("drill_hole", values, source, profile, monkeypatch)

    assert flow._tool_context.position_dependent_axis
    assert flow._tool_axis == pytest.approx((1.0, 0.0, 0.0))
    first = _preview_matrix(
        "drill_hole",
        (-1.0, 0.0, 0.0),
        slotted=True,
        measured_frame=True,
        axis="x",
        source=source,
        surface_point=(3.0, 0.0, 0.0),
        tool_context=flow._tool_context,
        monkeypatch=monkeypatch,
    )
    assert first[:3, 2] == pytest.approx((1.0, 0.0, 0.0))
    assert flow._tool_key and "3.0" in flow._tool_key and "x" in flow._tool_key

    dialog_values = flow.dialog.values()
    dialog_values.update(x=-3.0, y=0.0, z=0.0)
    flow.dialog.take_placement(dialog_values)
    surface = SimpleNamespace(point=(-3.0, 0.0, 0.0), normal=(-1.0, 0.0, 0.0))
    flow._surface = surface
    flow._own_mouth = None
    flow._updating = False
    flow._measure_group = None
    flow._measure_without_surface = False
    flow._change_op = None
    flow._position_edited = True
    flow._set_values = MethodType(PlacementFlow._set_values, flow)
    flow._request_tool = MethodType(PlacementFlow._request_tool, flow)
    monkeypatch.setattr(
        placement,
        "surface_values",
        lambda *_args, **_kwargs: {"x": -3.0, "y": 0.0, "z": 0.0},
    )

    assert PlacementFlow._set_values(flow)
    assert len(flow._placement_requests) == 2
    assert flow._tool_axis == pytest.approx((-1.0, 0.0, 0.0))
    second = _preview_matrix(
        "drill_hole",
        (-1.0, 0.0, 0.0),
        slotted=True,
        measured_frame=True,
        axis="x",
        source=source,
        surface_point=(-3.0, 0.0, 0.0),
        tool_context=flow._tool_context,
        monkeypatch=monkeypatch,
    )
    assert second[:3, 2] == pytest.approx((-1.0, 0.0, 0.0))

    mesh_source = SimpleNamespace(
        kind="mesh",
        material=None,
        material_slots=(),
        mesh=pocket,
        features={},
    )
    mesh_flow = _requested_tool_for_preview("drill_hole", values, mesh_source, profile, monkeypatch)
    assert mesh_flow._tool_context.position_dependent_axis
    assert mesh_flow._tool_axis == pytest.approx((-1.0, 0.0, 0.0))
    assert isinstance(mesh_flow._tool_context, PlacementTool)


def test_brep_legacy_zero_axis_matches_the_core_and_refreshes_after_moving(profile, monkeypatch):
    """Die echte BRep-Bohrung und ihre Vorschau teilen die Hüllmittenrichtung."""
    from types import MethodType, SimpleNamespace

    exact_kernel()

    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from app.core.brep.kernel import Solid
    from app.core.brep.ops import _bore_span
    from app.core.geom.prepare_ops import DrillParams
    from app.core.scene.placement import PlacementTool
    from app.ui.placement_flow import PlacementFlow

    body = Solid(BRepPrimAPI_MakeBox(gp_Pnt(-5.0, -5.0, -5.0), 10.0, 10.0, 10.0).Shape())
    source = SimpleNamespace(kind="brep", material=None, material_slots=(), mesh=body, features={})
    spec = REGISTRY.get("drill_hole")
    values = {
        entry.name: entry.default for entry in spec.params.spec() if entry.default is not None
    }
    values.update(
        x=3.0,
        y=0.0,
        z=0.0,
        axis="x",
        nx=0.0,
        ny=0.0,
        nz=0.0,
        slotted=True,
        slot_length=20.0,
        slot_angle=0.0,
        measured_frame=True,
    )
    flow = _requested_tool_for_preview("drill_hole", values, source, profile, monkeypatch)
    assert flow._tool_context.position_dependent_axis
    assert isinstance(flow._tool_context, PlacementTool)

    def core_axis(x: float) -> tuple[float, float, float]:
        params = DrillParams(
            x=x,
            y=0.0,
            z=0.0,
            axis="x",
            nx=0.0,
            ny=0.0,
            nz=0.0,
            slotted=True,
            slot_length=20.0,
            slot_angle=0.0,
        )
        frame, _height, _mouth = _bore_span(body, params, 0.0, slotted=True)
        return frame.normal

    assert flow._tool_axis == pytest.approx(core_axis(3.0))
    assert flow._tool_axis == pytest.approx((1.0, 0.0, 0.0))

    dialog_values = flow.dialog.values()
    dialog_values.update(x=-3.0, y=0.0, z=0.0)
    flow.dialog.take_placement(dialog_values)
    flow._surface = SimpleNamespace(point=(-3.0, 0.0, 0.0), normal=(-1.0, 0.0, 0.0))
    flow._own_mouth = None
    flow._updating = False
    flow._measure_group = None
    flow._measure_without_surface = False
    flow._change_op = None
    flow._position_edited = True
    flow._set_values = MethodType(PlacementFlow._set_values, flow)
    flow._request_tool = MethodType(PlacementFlow._request_tool, flow)
    monkeypatch.setattr(
        placement,
        "surface_values",
        lambda *_args, **_kwargs: {"x": -3.0, "y": 0.0, "z": 0.0},
    )

    assert PlacementFlow._set_values(flow)
    assert len(flow._placement_requests) == 2
    assert flow._tool_axis == pytest.approx(core_axis(-3.0))
    assert flow._tool_axis == pytest.approx((-1.0, 0.0, 0.0))


@pytest.mark.parametrize("operation", ["slot_hole", "resize_hole"])
@pytest.mark.parametrize(
    ("surface_normal", "feature_axis"),
    [
        ((0.0, 0.0, 1.0), (0.0, 0.0, 1.0)),
        ((0.0, 0.0, -1.0), (0.0, 0.0, 1.0)),
        ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ((0.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        ((0.0, -1.0, 0.0), (0.0, 1.0, 0.0)),
        (
            (0.0, 0.0, 1.0),
            (math.sin(math.radians(1.0)), 0.0, math.cos(math.radians(1.0))),
        ),
        (
            (0.0, 0.0, -1.0),
            (math.sin(math.radians(1.0)), 0.0, math.cos(math.radians(1.0))),
        ),
    ],
    ids=[
        "positive-z",
        "negative-z",
        "positive-x",
        "negative-x",
        "positive-y",
        "negative-y",
        "positive-face-one-degree-tilt",
        "negative-face-one-degree-tilt",
    ],
)
@pytest.mark.parametrize("angle_degrees", [0.0, 45.0, 90.0], ids=["0", "45", "90"])
def test_existing_slot_preview_uses_the_positive_feature_axis_for_every_angle(
    operation, surface_normal, feature_axis, angle_degrees, monkeypatch
):
    """Der Vorschaurichtung liegt derselbe Achsenrahmen wie dem Schnitt zugrunde."""
    from app.core.geom.prepare import slot_frame
    from app.core.units import positive_axis

    # Gegenüberliegende Mündungen und eine um 1° geneigte Achse dürfen weder
    # spiegeln noch die Tiefe skalieren.
    matrix = _preview_matrix(
        operation,
        surface_normal,
        feature_axis=feature_axis,
        angle_degrees=angle_degrees,
        monkeypatch=monkeypatch,
    )
    basis = matrix[:3, :3]
    frame = slot_frame(positive_axis(feature_axis), (0.0, 0.0, 0.0))
    expected_basis = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    angle = math.radians(angle_degrees)
    direction = basis @ np.asarray((math.cos(angle), math.sin(angle), 0.0))
    expected_direction = expected_basis @ np.asarray((math.cos(angle), math.sin(angle), 0.0))
    if float(np.dot(frame.normal, surface_normal)) < 0.0:
        local_direction = np.asarray((math.cos(angle), math.sin(angle)))
        correction = np.eye(3)
        correction[:2, :2] = 2.0 * np.outer(local_direction, local_direction) - np.eye(2)
        correction[2, 2] = -1.0
        expected_basis = expected_basis @ correction

    assert basis == pytest.approx(expected_basis, abs=1e-12)
    assert direction == pytest.approx(expected_direction, abs=1e-12)
    assert basis.T @ basis == pytest.approx(np.eye(3), abs=1e-12)
    assert np.linalg.det(basis) == pytest.approx(1.0, abs=1e-12)
    assert matrix[:3, 3] == pytest.approx((3.0, -4.0, 5.0))
    if feature_axis == (0.0, 0.0, 1.0) and angle_degrees == 45.0:
        assert direction == pytest.approx((math.sqrt(0.5), math.sqrt(0.5), 0.0))


def test_a_slotted_drill_preview_keeps_the_surface_normal_as_its_cut_axis(monkeypatch):
    """Beim Setzen bestimmt die Flächennormale weiter Achse und Langlochwinkel."""
    from app.core.geom.prepare import slot_frame

    normal = np.asarray((0.0, 0.0, -1.0))
    matrix = _preview_matrix("drill_hole", tuple(normal), slotted=True, monkeypatch=monkeypatch)
    basis = matrix[:3, :3]
    frame = slot_frame(tuple(normal), (0.0, 0.0, 0.0))
    expected_basis = np.column_stack((frame.x_axis, frame.y_axis, normal))
    angle = math.radians(45.0)
    direction = basis @ np.asarray((math.cos(angle), math.sin(angle), 0.0))
    expected_direction = expected_basis @ np.asarray((math.cos(angle), math.sin(angle), 0.0))

    assert basis == pytest.approx(expected_basis, abs=1e-12)
    assert direction == pytest.approx(expected_direction, abs=1e-12)


@pytest.mark.parametrize(
    ("tool_axis", "axis", "surface_normal", "surface_point", "expected_axis"),
    [
        ((0.0, 0.0, 2.0), "z", (0.0, 0.0, 1.0), (3.0, -4.0, 5.0), (0.0, 0.0, 1.0)),
    ],
    ids=["normalize"],
)
def test_a_legacy_drill_preview_normalizes_or_uses_its_selected_axis(
    tool_axis, axis, surface_normal, surface_point, expected_axis, monkeypatch
):
    """Die vorbereitete alte Achse bleibt endlich und maßstabsgetreu."""
    from types import SimpleNamespace

    body = SimpleNamespace(mesh=SimpleNamespace(bounds=SimpleNamespace(centre=(0.0, 0.0, 0.0))))
    matrix = _preview_matrix(
        "drill_hole",
        surface_normal,
        slotted=True,
        measured_frame=True,
        tool_axis=tool_axis,
        source=body,
        axis=axis,
        surface_point=surface_point,
        monkeypatch=monkeypatch,
    )
    basis = matrix[:3, :3]

    assert basis[:, 2] == pytest.approx(expected_axis, abs=1e-12)
    assert basis.T @ basis == pytest.approx(np.eye(3), abs=1e-12)
    assert np.linalg.det(basis) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize(
    ("feature_axis", "surface_normal", "surface_point"),
    [
        ((0.0, 0.0, 1.0), (0.0, 0.0, 1.0), (5.0, 5.0, 10.0)),
        ((0.0, 0.0, 1.0), (0.0, 0.0, -1.0), (5.0, 5.0, 0.0)),
        ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (10.0, 5.0, 5.0)),
        ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 5.0, 5.0)),
        ((0.0, 1.0, 0.0), (0.0, 1.0, 0.0), (5.0, 10.0, 5.0)),
        ((0.0, 1.0, 0.0), (0.0, -1.0, 0.0), (5.0, 0.0, 5.0)),
        (
            (math.sin(math.radians(1.0)), 0.0, math.cos(math.radians(1.0))),
            (0.0, 0.0, 1.0),
            (5.0, 5.0, 10.0),
        ),
        (
            (math.sin(math.radians(1.0)), 0.0, math.cos(math.radians(1.0))),
            (0.0, 0.0, -1.0),
            (5.0, 5.0, 0.0),
        ),
    ],
    ids=[
        "z-top",
        "z-bottom",
        "x-right",
        "x-left",
        "y-back",
        "y-front",
        "tilted-top",
        "tilted-bottom",
    ],
)
@pytest.mark.parametrize("angle_degrees", [0.0, 45.0, 90.0], ids=["0", "45", "90"])
def test_the_prepared_slot_tool_enters_from_both_mouths_with_a_right_handed_frame(
    feature_axis, surface_normal, surface_point, angle_degrees, profile, monkeypatch
):
    """Die echte Werkzeugform behält Winkel und Tiefe an beiden Mündungen."""
    from types import SimpleNamespace

    from app.core.geom.mesh import MeshData
    from app.core.geom.prepare import slot_frame
    from app.core.registry import REGISTRY
    from app.core.scene import placement
    from app.core.units import positive_axis

    axis = positive_axis(feature_axis)
    angle = math.radians(angle_degrees)
    frame = slot_frame(axis, (5.0, 5.0, 5.0))
    direction = tuple(
        math.cos(angle) * frame.x_axis[index] + math.sin(angle) * frame.y_axis[index]
        for index in range(3)
    )
    feature = SimpleNamespace(
        id="slot_1",
        kind="slot",
        params={
            "axis": axis,
            "direction": direction,
            "centre": (5.0, 5.0, 5.0),
            "diameter": 6.0,
            "depth": 8.0,
            "length": 20.0,
            "travel": 14.0,
        },
    )
    raw_body = trimesh.creation.box((10.0, 10.0, 10.0))
    raw_body.apply_translation((5.0, 5.0, 5.0))
    source = SimpleNamespace(
        material=None,
        material_slots=(),
        mesh=MeshData.of(raw_body),
        features={feature.id: feature},
    )
    prepared = placement.prepare_tool(
        REGISTRY.get("slot_hole"),
        {
            "at_feature": feature.id,
            "slot_length": 20.0,
            "slot_angle": angle_degrees,
            "measured_frame": False,
        },
        profile,
        source=source,
        feature=feature,
    )
    original_outline = placement.mouth_outline
    matrix = _preview_matrix(
        "slot_hole",
        surface_normal,
        feature_axis=axis,
        angle_degrees=angle_degrees,
        source=source,
        surface_point=surface_point,
        tool_context=prepared,
        monkeypatch=monkeypatch,
    )
    basis = matrix[:3, :3]
    moved = prepared.mesh.raw.copy()
    moved.apply_transform(matrix)
    depth_coordinates = (np.asarray(moved.vertices) - np.asarray(surface_point)) @ np.asarray(axis)
    side = 1.0 if float(np.dot(axis, surface_normal)) >= 0.0 else -1.0

    assert basis.T @ basis == pytest.approx(np.eye(3), abs=1e-12)
    assert np.linalg.det(basis) == pytest.approx(1.0, abs=1e-12)
    assert depth_coordinates.min() == pytest.approx(min(0.0, -side * 8.0), abs=1e-9)
    assert depth_coordinates.max() == pytest.approx(max(0.0, -side * 8.0), abs=1e-9)
    assert moved.volume > 0.0

    from app.core.units import MAX_FACET_SAG

    outline = np.asarray(original_outline(prepared), dtype=np.float64)
    segments = np.roll(outline, -1, axis=0) - outline
    longest = segments[np.argmax(np.sum(segments * segments, axis=1))]
    outline_length = float(np.linalg.norm(longest))
    local_direction = longest / outline_length
    world_direction = basis[:, :2] @ local_direction
    expected_direction = np.asarray(frame.x_axis) * math.cos(angle) + np.asarray(
        frame.y_axis
    ) * math.sin(angle)
    difference = math.degrees(
        math.acos(min(1.0, abs(float(np.dot(world_direction, expected_direction)))))
    )
    angle_limit = math.degrees(math.atan2(2.0 * MAX_FACET_SAG, outline_length))
    assert difference <= angle_limit


def test_legacy_slot_angle_uses_the_measured_axis_in_placement_tool(profile):
    """Die Vorschau hält bei Altprojekten dieselbe Weltrichtung wie der Schnitt."""
    from types import SimpleNamespace

    from app.core.geom.mesh import MeshData
    from app.core.registry import REGISTRY
    from app.core.sketch.planes import frame_of

    axis = (0.001, 0.0, 1.0)
    previous = frame_of(axis, (0.0, 0.0, 0.0))
    feature = SimpleNamespace(
        id="slot_1",
        kind="slot",
        params={
            "axis": axis,
            "direction": previous.x_axis,
            "centre": (0.0, 0.0, 0.0),
            "diameter": 6.0,
            "depth": 8.0,
            "length": 20.0,
            "travel": 14.0,
        },
    )
    source = SimpleNamespace(
        material=None,
        material_slots=(),
        mesh=MeshData.of(trimesh.creation.box((30.0, 30.0, 8.0))),
        features={feature.id: feature},
    )

    tool = placement.prepare_tool(
        REGISTRY.get("slot_hole"),
        {
            "at_feature": feature.id,
            "slot_length": 20.0,
            "slot_angle": 0.0,
            "measured_frame": True,
        },
        profile,
        source=source,
    )
    spans = np.ptp(np.asarray(placement.mouth_outline(tool)), axis=0)

    assert spans[1] > spans[0] * 2.0, "das alte +Y liegt heute entlang der zweiten Rahmenachse"


def test_migrated_drill_preview_keeps_parameter_bound_axis_through_request(profile, monkeypatch):
    """Die echte Vorschauanfrage hält Winkel und Achse des migrierten Schnitts."""
    import copy
    from pathlib import Path
    from types import SimpleNamespace

    from tests.helpers import exact_kernel

    exact_kernel()

    from app.core.scene.evaluate import evaluate
    from app.core.scene.migrations import migrate
    from app.core.scene.project import project_data
    from app.core.scene.serialise import document_from_data
    from app.core.sketch.planes import frame_of
    from app.core.units import MAX_FACET_SAG
    from app.ui import placement_flow
    from app.ui.placement_flow import PlacementFlow

    data = project_data(Path(__file__).parent / "data/projects/slot_angle_frame_v38.p3d")
    for step in data["ops"]:
        if step["op"] not in {"drill_hole", "drill_brep_hole"} or not step["params"].get("slotted"):
            continue
        for name in ("slot_angle", "nx", "ny", "nz"):
            parameter = f"{name}_{step['id']}"
            data.setdefault("parameters", {})[parameter] = {
                "value": step["params"][name],
                "unit": "°" if name == "slot_angle" else "",
            }
            step["params"][name] = f"=@{parameter}"

    document = document_from_data(migrate(copy.deepcopy(data)))
    result = evaluate(document, profile, quality="fine")
    assert result.complete, result.findings

    checked = set()
    monkeypatch.setattr(placement_flow, "isValid", lambda _flow: True)
    for step in document.ops:
        if step.op not in {"drill_hole", "drill_brep_hole"} or not step.params.get("slotted"):
            continue
        assert step.params["measured_frame"]
        source, feature = next(
            (owner, feature)
            for owner in result.scene.objects.values()
            for feature in owner.features.values()
            if feature.kind == "slot" and feature.created_by == step.id
        )
        prepared = []
        refresh_requests = []
        dialog_values = dict(step.params)

        def placement_async(compute, done, *_callbacks, prepared=prepared):
            tool = compute()
            prepared.append(tool)
            done(tool)

        flow = SimpleNamespace(
            active=True,
            _disposed=False,
            _tool_busy=False,
            _tool_again=False,
            _tool_key=None,
            _tool_context=None,
            _tool_axis=None,
            _tool_angle=None,
            _epoch=1,
            spec_of=lambda step=step: REGISTRY.get(step.op),
            _request_tool=lambda requests=refresh_requests, values=dialog_values: requests.append(
                dict(values)
            ),
            _source_feature=lambda source=source: (source, None),
            dialog=SimpleNamespace(
                values=lambda values=dialog_values: dict(values),
                take_placement=lambda update, values=dialog_values: values.update(update),
            ),
            session=SimpleNamespace(
                profile=profile,
                project=SimpleNamespace(document=document),
                placement_async=placement_async,
            ),
            viewport=SimpleNamespace(renderer=None),
            _accept_pending=False,
            _measure_group=None,
            _change_op=step,
            _surface=None,
            _own_mouth=None,
            _updating=False,
            redraw=lambda: None,
        )

        PlacementFlow._request_tool(flow)
        assert len(prepared) == 1
        prepared_tool = prepared[0]
        assert flow._tool_axis is not None
        original_axis = flow._tool_axis
        flow._tool_context = prepared_tool

        surface_normal = np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
        surface = SimpleNamespace(
            point=(0.0, 0.0, 0.0),
            normal=tuple(surface_normal),
            frame=frame_of(tuple(surface_normal), (0.0, 0.0, 0.0)),
        )
        flow._surface = surface
        assert PlacementFlow._set_values(flow)
        assert len(prepared) == 1, "eine Positionsänderung darf kein Werkzeug erneut anfordern"
        assert flow._tool_axis == original_axis
        assert all(dialog_values[name] == step.params[name] for name in ("nx", "ny", "nz")), (
            "die gebundenen Richtungswerte bleiben beim Verschieben erhalten"
        )

        axes = PlacementFlow._tool_axes(flow, surface)
        outline = np.asarray(placement.mouth_outline(prepared_tool), dtype=np.float64)
        segments = np.roll(outline, -1, axis=0) - outline
        longest = segments[np.argmax(np.sum(segments * segments, axis=1))]
        major_axis = np.r_[longest, 0.0]
        preview_direction = np.column_stack(axes) @ major_axis
        actual_direction = np.asarray(feature.params["direction"], dtype=np.float64)
        preview_angle = math.degrees(math.atan2(preview_direction[1], preview_direction[0])) % 180.0
        actual_angle = math.degrees(math.atan2(actual_direction[1], actual_direction[0])) % 180.0
        difference = abs((preview_angle - actual_angle + 90.0) % 180.0 - 90.0)
        # Die sichtbare Kontur wird mit MAX_FACET_SAG vereinfacht. Wenn beide
        # Endpunkte des langen Umrisses jeweils um höchstens diesen Betrag
        # wandern, bleibt seine Winkelabweichung durch die Konturvereinfachung
        # innerhalb des daraus folgenden Winkels.
        outline_length = float(np.linalg.norm(longest))
        outline_angle_limit = math.degrees(math.atan2(2.0 * MAX_FACET_SAG, outline_length))

        assert difference <= outline_angle_limit, (
            f"{step.op}, {source.kind}: {difference:.6f}° > "
            f"{outline_angle_limit:.6f}° aus MAX_FACET_SAG"
        )
        checked.add((step.op, source.kind))

        dialog_values.update(nx=1.0, ny=0.0, nz=0.0)
        PlacementFlow._request_tool(flow)
        assert len(prepared) == 2
        assert flow._tool_axis == (1.0, 0.0, 0.0)
        flow._tool_context = prepared[-1]
        axes = PlacementFlow._tool_axes(flow, surface)
        assert axes[2] == pytest.approx((1.0, 0.0, 0.0))
        assert PlacementFlow._set_values(flow)
        # Eine Fläche mit anderer Normale ist eine neue Lage: Die Bohrung folgt
        # ihr wie jede neue, und der Altrahmen fällt (RM-332, N6). Hier blieb
        # (1, 0, 0) stehen, und die Bohrung lief quer zur angeklickten Fläche.
        assert (dialog_values["nx"], dialog_values["ny"], dialog_values["nz"]) == pytest.approx(
            (0.0, 0.0, 1.0)
        )
        assert dialog_values["measured_frame"] is False
        assert len(refresh_requests) == 1
        assert refresh_requests[0]["measured_frame"] is False

    assert checked == {("drill_hole", "mesh"), ("drill_hole", "brep")}


@pytest.mark.parametrize(
    ("stored", "placed", "same"),
    [
        ({"nx": 0.0, "ny": 0.0, "nz": 1.0}, {"nx": 0.0, "ny": 0.0, "nz": 1.0}, True),
        ({"nx": 0.0005, "ny": 0.0, "nz": 1.0}, {"nx": 0.0, "ny": 0.0, "nz": 1.0}, True),
        ({"nx": 0.0, "ny": 0.0, "nz": 1.0}, {"nx": 1.0, "ny": 0.0, "nz": 0.0}, False),
        ({"nx": "=@kipp", "ny": 0.0, "nz": 1.0}, {"nx": 1.0, "ny": 0.0, "nz": 0.0}, True),
        (
            {"nx": 0.001, "ny": 0.0, "nz": 2.0},
            {"nx": 0.0005, "ny": 0.0, "nz": 1.0},
            True,
        ),
        ({"nx": 0.0, "ny": 0.0, "nz": 2.0}, {"nx": 0.0, "ny": 0.0, "nz": -1.0}, False),
    ],
)
def test_an_old_slot_direction_only_stays_on_the_same_face(
    stored: dict[str, object], placed: dict[str, object], same: bool
) -> None:
    """Eine migrierte Langlochbohrung behielt beim Umsetzen auf eine andere
    Fläche die alte Bohrrichtung (RM-332, N6). Die alte Richtung bleibt nur auf
    einer Fläche mit derselben Normalen; ein Ausdruck ist eine Bindung und
    bleibt."""
    from app.ui.placement_flow import _same_direction

    assert _same_direction(stored, placed, ("nx", "ny", "nz")) is same


@pytest.mark.parametrize(
    "fields",
    [("nx", "ny", "nz"), ("surface_nx", "surface_ny", "surface_nz")],
    ids=["operation", "recipe"],
)
@pytest.mark.parametrize(("bound_axis", "axis_name"), [(0, "x"), (1, "y"), (2, "z")])
def test_a_bound_normal_component_survives_replacing_the_surface(fields, bound_axis, axis_name):
    """Ein gebundener Achsenwert bleibt auch hinter einer abweichenden Komponente erhalten."""
    from app.ui.placement_flow import _same_direction

    old = dict(zip(fields, (0.0005, 0.0, 1.0), strict=True))
    old[fields[bound_axis]] = f"=@tilt_{axis_name}"
    new_surface = dict(zip(fields, (1.0, 0.0, 0.0), strict=True))

    assert _same_direction(old, new_surface, fields)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_measured_slot_preview_rebuilds_on_a_new_face_and_undo_restores_the_cut(profile, kind):
    """Ein Flächenwechsel zeigt den neuen Schnitt; Undo stellt den alten Schritt her."""
    from types import SimpleNamespace

    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources
    from app.core.sketch.planes import frame_of
    from app.core.units import MAX_FACET_SAG
    from app.ui import placement_flow
    from app.ui.placement_flow import PlacementFlow

    project, history, original, step, selected = _bore_history(
        profile,
        kind,
        slotted=True,
        slot_length=16.0,
        slot_angle=0.0,
        nx=0.0005,
        ny=0.0,
        nz=1.0,
        measured_frame=True,
    )
    original_params = dict(step.params)
    original_body = original.scene.objects[selected.object_id]
    original_feature = original_body.features[selected.feature_id]
    dialog_values = dict(original_params)
    prepared = []

    class RendererStub:
        def add_surface(self, *_args, **_kwargs):
            return object()

    def placement_async(compute, done, _failed, _refused=None):
        tool = compute()
        prepared.append(tool)
        done(tool)

    flow = SimpleNamespace(
        active=True,
        _disposed=False,
        _tool_busy=False,
        _tool_again=False,
        _tool_context=None,
        _tool_axis=None,
        _tool_angle=None,
        _tool_key="",
        _epoch=1,
        _surface=None,
        _own_mouth=None,
        _updating=False,
        _measure_group=None,
        _change_op=step,
        _showing_input=False,
        _accept_pending=False,
        _refused_note=None,
        _tool=None,
        _addition=None,
        spec_of=lambda: REGISTRY.get(step.op),
        _source_feature=lambda: (original_body, original_feature),
        dialog=SimpleNamespace(
            values=lambda: dict(dialog_values),
            take_placement=lambda values: dialog_values.update(values),
        ),
        session=SimpleNamespace(
            profile=profile,
            project=SimpleNamespace(document=project.document),
            placement_async=placement_async,
        ),
        viewport=SimpleNamespace(
            renderer=RendererStub(), _diff_palette="blue_orange", _object_colour="blue"
        ),
        _remove_tools=lambda: None,
        _tool_legend=SimpleNamespace(setText=lambda _text: None, show=lambda: None),
        redraw=lambda: None,
    )
    flow._set_values = lambda: PlacementFlow._set_values(flow)
    flow._request_tool = lambda: PlacementFlow._request_tool(flow)

    PlacementFlow._request_tool(flow)
    assert len(prepared) == 1
    old_tool = flow._tool_context
    assert old_tool is prepared[0]

    new_normal = (1.0, 0.0, 0.0)
    surface = SimpleNamespace(
        point=(20.0, 0.0, 10.0),
        normal=new_normal,
        frame=frame_of(new_normal, (20.0, 0.0, 10.0)),
    )
    flow._surface = surface
    assert PlacementFlow._set_values(flow)

    assert len(prepared) == 2, "der neue Flächenrahmen braucht ein neu vorbereitetes Werkzeug"
    assert flow._tool_context is prepared[-1] and flow._tool_context is not old_tool
    assert dialog_values["measured_frame"] is False
    assert (dialog_values["nx"], dialog_values["ny"], dialog_values["nz"]) == pytest.approx(
        new_normal
    )
    assert project.document.ops[-1].params == original_params, (
        "die Vorschau ändert den Schritt nicht"
    )

    axes = PlacementFlow._tool_axes(flow, surface)
    outline = np.asarray(
        placement_flow.placement.mouth_outline(flow._tool_context), dtype=np.float64
    )
    segments = np.roll(outline, -1, axis=0) - outline
    longest = segments[np.argmax(np.sum(segments * segments, axis=1))]
    preview_direction = np.column_stack(axes) @ np.r_[longest, 0.0]
    preview_direction /= np.linalg.norm(preview_direction)

    history.change_params(step.id, {**original_params, **dialog_values})
    changed = evaluate(project.document, profile, sources=ProjectSources(project))
    assert changed.complete, changed.findings
    changed_feature = next(
        feature
        for body in changed.scene.objects.values()
        for feature in body.features.values()
        if feature.created_by == step.id and feature.kind == "slot"
    )
    actual_direction = np.asarray(changed_feature.params["direction"], dtype=np.float64)
    actual_direction /= np.linalg.norm(actual_direction)
    difference = math.degrees(
        math.acos(min(1.0, abs(float(np.dot(preview_direction, actual_direction)))))
    )
    outline_length = float(np.linalg.norm(longest))
    allowed_difference = math.degrees(math.atan2(2.0 * MAX_FACET_SAG, outline_length))
    assert difference <= allowed_difference

    history.undo()
    restored = project.document.ops[-1]
    assert restored.id == step.id
    assert restored.params == original_params
    replayed = evaluate(project.document, profile, sources=ProjectSources(project))
    assert replayed.complete, replayed.findings
    restored_feature = next(
        feature
        for body in replayed.scene.objects.values()
        for feature in body.features.values()
        if feature.created_by == step.id and feature.kind == "slot"
    )
    assert restored_feature.params["direction"] == pytest.approx(
        original_feature.params["direction"]
    )


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_resolved_zero_axis_stays_bound_on_the_same_face(profile, kind):
    """Die aufgelöste Achse unterscheidet eine Positionsgeste vom Flächenwechsel."""
    from types import SimpleNamespace

    from app.core.scene import placement
    from app.core.sketch.planes import frame_of
    from app.ui.placement_flow import PlacementFlow

    _project, _history, result, step, _selected = _bore_history(
        profile,
        kind,
        axis="z",
        slotted=True,
        slot_length=16.0,
        slot_angle=0.0,
        nx=0.0,
        ny=0.0,
        nz=0.0,
        measured_frame=True,
    )
    source = next(iter(result.scene.objects.values()))
    values = dict(step.params)
    context = placement.prepare_tool(REGISTRY.get(step.op), values, profile, source=source)
    assert context.outward_axis == pytest.approx((0.0, 0.0, 1.0))
    assert context.position_dependent_axis

    def surface(point, normal):
        return placement.SurfacePlacement(
            point=point,
            normal=normal,
            frame=frame_of(normal, point),
            planar=True,
            face_indices=(),
            edges=(),
            centres=(),
        )

    refreshes = []
    flow = SimpleNamespace(
        _measure_group=None,
        _surface=surface((4.0, 0.0, 20.0), (0.0, 0.0, 1.0)),
        _tool_context=context,
        _own_mouth=None,
        _updating=False,
        spec_of=lambda: REGISTRY.get(step.op),
        _source_feature=lambda: (source, None),
        dialog=SimpleNamespace(
            values=lambda: dict(values),
            take_placement=lambda placed: values.update(placed),
        ),
        _request_tool=lambda: refreshes.append(dict(values)),
    )
    flow._set_values = lambda: PlacementFlow._set_values(flow)

    assert PlacementFlow._set_values(flow)
    assert values["measured_frame"] is True
    assert (values["nx"], values["ny"], values["nz"]) == (0.0, 0.0, 0.0)
    assert values["x"] == pytest.approx(4.0)
    assert len(refreshes) == 1, "die ortsabhängige Achse wird an der neuen Stelle neu bestimmt"
    assert refreshes[0]["measured_frame"] is True
    assert (refreshes[0]["nx"], refreshes[0]["ny"], refreshes[0]["nz"]) == (0.0, 0.0, 0.0)

    flow._surface = surface((20.0, 0.0, 10.0), (1.0, 0.0, 0.0))
    assert PlacementFlow._set_values(flow)
    assert values["measured_frame"] is False
    assert (values["nx"], values["ny"], values["nz"]) == pytest.approx((1.0, 0.0, 0.0))
    assert len(refreshes) == 2, "ein wirklicher Flächenwechsel bereitet das Werkzeug neu vor"
