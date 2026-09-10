"""Die **Flächen** eines Netzes bearbeiten — versetzen und anstellen.

Derselbe Auftrag wie bei den Kanten (`test_mesh_edges.py`): Ein importiertes
Modell soll dieselben Werkzeuge annehmen wie ein selbst gezeichnetes
(Entscheidung Robert, 10.09.2026). Und ein zweiter Befund desselben Tages
steckt hier drin — *Fläche versetzen* nahm eine **Richtung** entgegen und
bewegte jede Fläche, die dorthin zeigte.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import GeometryError
from app.core.geom.boolean import boolean
from app.core.geom.faces import draft_vertical, push_face
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Feature, OpContext, OpResult, Profile, Scene, SceneObject

WIDTH, DEPTH, HEIGHT = 40.0, 30.0, 20.0
STEP = 10.0
DRAFT = 3.0


def block() -> MeshData:
    """Ein Quader, der auf der Platte steht — die neutrale Ebene ist z = 0."""
    body = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    body.apply_translation((0.0, 0.0, HEIGHT / 2.0))
    return MeshData(body)


def stairs() -> MeshData:
    """Zwei Stufen: links 10 mm hoch, rechts 20 — der Fall, der den Befund trug."""
    low = trimesh.creation.box(extents=(20.0, DEPTH, STEP))
    low.apply_translation((-10.0, 0.0, STEP / 2.0))
    high = trimesh.creation.box(extents=(20.0, DEPTH, HEIGHT))
    high.apply_translation((10.0, 0.0, HEIGHT / 2.0))
    return boolean("union", [MeshData(low), MeshData(high)], quality="fine").mesh


def face_looking_up(mesh: MeshData, below: float = 1e9) -> Feature:
    """Die nach oben zeigende Fläche unterhalb einer Höhe."""
    return next(
        entry
        for entry in detect(mesh).values()
        if entry.kind == "face"
        and abs(entry.params["normal"][2] - 1.0) < 1e-6
        and entry.params["centre"][2] < below
    )


def drafted_volume(angle_deg: float) -> float:
    """Was von einem Quader übrig bleibt, wenn alle vier Wände anstehen.

    Analytisch und nicht aus dem Prüfling: Die Grundfläche schrumpft mit der
    Höhe um ``2·tan(α)·z`` je Richtung, und das Integral darüber ist
    ``W·D·H − tan(α)·H²·(W+D) + 4/3·tan(α)²·H³``.
    """
    slope = math.tan(math.radians(angle_deg))
    return (
        WIDTH * DEPTH * HEIGHT
        - slope * HEIGHT**2 * (WIDTH + DEPTH)
        + 4.0 / 3.0 * slope**2 * HEIGHT**3
    )


def test_pushing_a_face_out_adds_exactly_the_prism() -> None:
    """Nach außen: Der Körper wächst um Fläche mal Weg, und nur dort."""
    body = block()
    top = face_looking_up(body)

    outcome = push_face(body, top, 5.0)
    grown = outcome.mesh.raw

    assert grown.is_watertight and grown.body_count == 1
    assert grown.volume == pytest.approx(WIDTH * DEPTH * (HEIGHT + 5.0), abs=1e-6)
    assert outcome.solver.strategy == "direct"


def test_pushing_a_face_in_takes_exactly_the_prism_away() -> None:
    """Nach innen: dasselbe Werkzeug, umgekehrtes Vorzeichen.

    **Der Fall, der beim ersten Anlauf nichts tat.** Das Prisma entstand mit
    ``abs(distance)`` und lag damit auch bei negativem Weg außerhalb des
    Körpers; die Differenz traf nichts, und zurück kam ein wasserdichter,
    einteiliger Quader mit 24000 mm³ statt 18000 — ein Schritt im Verlauf und
    kein Unterschied im Bild.
    """
    body = block()
    top = face_looking_up(body)

    shrunk = push_face(body, top, -5.0).mesh.raw

    assert shrunk.is_watertight and shrunk.body_count == 1
    assert shrunk.volume == pytest.approx(WIDTH * DEPTH * (HEIGHT - 5.0), abs=1e-6)
    assert shrunk.bounds[1][2] == pytest.approx(HEIGHT - 5.0, abs=1e-6)


def test_only_the_chosen_step_moves_and_not_every_face_facing_up() -> None:
    """Der Befund vom 10.09.2026, als Zusicherung.

    „fläche versetzen ergibt doch keinen sinn oder wo ist das sinnvoll?" —
    gemessen an dieser Treppe: Die alte Fassung nahm eine *Richtung* und
    bewegte beide Stufen, 24000,0 mm³ statt 21000,0. Der Kunde klickt eine
    Fläche an, und genau die ist gemeint.

    Die Treppe ist dafür der kleinste Körper, der es überhaupt zeigen kann:
    Ein Quader hat nur **eine** nach oben zeigende Fläche, und daran sind die
    zwei Fassungen nicht zu unterscheiden.
    """
    body = stairs()
    before = body.raw.volume
    upward = [
        entry
        for entry in detect(body).values()
        if entry.kind == "face" and abs(entry.params["normal"][2] - 1.0) < 1e-6
    ]
    assert len(upward) == 2, "sonst prüft der Test nicht, was er behauptet"

    lifted = push_face(body, face_looking_up(body, below=15.0), 5.0).mesh.raw

    assert lifted.volume == pytest.approx(before + 20.0 * DEPTH * 5.0, abs=1e-6)
    assert lifted.volume == pytest.approx(21000.0, abs=1e-6)
    assert lifted.bounds[1][2] == pytest.approx(HEIGHT, abs=1e-6), "die hohe Stufe bleibt"


def test_a_curved_face_is_turned_away_with_a_sentence() -> None:
    """„Entlang ihrer Normalen" braucht eine Normale, und ein Mantel hat viele.

    Kein Fehler im Programm, sondern eine Handlung, die dort nicht definiert
    ist — also ein Satz mit Weg nach vorn (Regel 17).

    **Das Merkmal ist hier von Hand gebaut, und das ist kein Kunstgriff.** Die
    Erkennung gibt einem Zylindermantel gar kein ``face`` — sie nennt ihn
    ``pin`` —, also käme dieser Fall über den Mausklick nie herein. Über Chat
    und Kommandozeile schon: Dort benennt jemand die Dreiecke, und dieselbe
    Lücke hat ``applies_to`` am 03.09.2026 schon einmal offengelassen.
    """
    cylinder = MeshData(trimesh.creation.cylinder(radius=10.0, height=20.0, sections=32))
    flat = next(entry for entry in detect(cylinder).values() if entry.kind == "face")
    mantle_triangles = tuple(
        index
        for index, normal in enumerate(cylinder.raw.face_normals)
        if abs(float(normal[2])) < 0.5
    )
    assert mantle_triangles, "sonst prüft der Test eine leere Menge"
    mantle = Feature(
        id="face_9",
        kind="face",
        provenance=flat.provenance,
        params={"normal": (1.0, 0.0, 0.0), "centre": (10.0, 0.0, 0.0), "area": 1.0},
        face_indices=mantle_triangles,
    )

    with pytest.raises(GeometryError) as problem:
        push_face(cylinder, mantle, 2.0)

    assert "gewölbt" in str(problem.value.detail)
    assert problem.value.suggestions, "Regel 17: nie ohne Handlungsvorschlag"


def test_the_draft_keeps_the_standing_face_and_narrows_the_top() -> None:
    """Die Formschräge, gegen die analytische Zahl — und in der ersten Stufe.

    **Zwei Fehler steckten im Keil**, und beide sahen nach „geht halt nicht"
    aus: Er kam mit **negativem** Volumen heraus (−419,262 statt 419,262),
    weil der Versatz ins Material zeigt und die Umlaufrichtung damit kippt;
    und an der neutralen Kante liegen Boden und Deckel aufeinander, was
    Dreiecke ohne Fläche hinterlässt. Für ``manifold3d`` war beides kein
    „positive closed volume": Die Kette fiel bis zur Voxelstufe durch, brauchte
    4,8 Sekunden und lag 0,13 % daneben.
    """
    outcome = draft_vertical(block(), DRAFT)
    shaped = outcome.mesh.raw
    slope = math.tan(math.radians(DRAFT))

    assert outcome.solver.strategy == "direct", "ein sauberer Keil braucht keinen Rückfall"
    assert shaped.is_watertight and shaped.body_count == 1
    assert shaped.volume == pytest.approx(drafted_volume(DRAFT), abs=1e-6)
    assert shaped.bounds[0][0] == pytest.approx(-WIDTH / 2.0, abs=1e-6), "die Standfläche bleibt"
    assert shaped.bounds[1][0] == pytest.approx(WIDTH / 2.0, abs=1e-6)
    highest = shaped.vertices[shaped.vertices[:, 2] > HEIGHT - 1e-6]
    assert float(highest[:, 0].max()) == pytest.approx(WIDTH / 2.0 - slope * HEIGHT, abs=1e-6), (
        "und oben ist er um tan(α)·H schmaler"
    )


def test_both_kernels_draft_to_the_same_body() -> None:
    """Dieselbe Handlung, zwei Kerne — und hier ist der Unterschied null.

    Eine Formschräge schiebt ebene Flächen gegeneinander; daran hat ein Netz
    nichts zu runden. Anders als bei der Verrundung (`test_mesh_edges.py`)
    bleibt deshalb kein Sehnenzug übrig.
    """
    brep = pytest.importorskip("app.core.brep.profiles")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")
    from app.core.brep.edit import box

    exact = brep.draft_vertical(box(WIDTH, DEPTH, HEIGHT), DRAFT)
    meshed = draft_vertical(block(), DRAFT).mesh.raw

    assert exact.volume == pytest.approx(drafted_volume(DRAFT), abs=1e-6)
    assert meshed.volume == pytest.approx(exact.volume, abs=1e-6)


def test_both_kernels_push_the_same_single_face() -> None:
    """Und beim Versetzen trifft der exakte Kern jetzt auch **eine** Fläche.

    Die Auswahl über den Ort steht dort neben der über die Richtung: Die
    Richtung bleibt der Vorfilter, die Stelle entscheidet
    (``profiles._nearest_face``). Ohne sie gibt derselbe Aufruf 24000,0 —
    beide Stufen.
    """
    brep = pytest.importorskip("app.core.brep.profiles")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")
    from app.core.brep.edit import boolean as exact_boolean
    from app.core.brep.edit import box, moved

    exact = exact_boolean(
        "union", [box(20.0, DEPTH, STEP), moved(box(20.0, DEPTH, HEIGHT), (20.0, 0.0, 0.0))]
    )

    everything = brep.push_faces(exact, (0.0, 0.0, 1.0), 5.0)
    just_one = brep.push_faces(exact, (0.0, 0.0, 1.0), 5.0, centre=(10.0, 15.0, STEP))

    assert everything.volume == pytest.approx(24000.0, abs=1e-6), "die alte Fassung, zum Vergleich"
    assert just_one.volume == pytest.approx(21000.0, abs=1e-6)
    assert just_one.volume == pytest.approx(
        push_face(stairs(), face_looking_up(stairs(), below=15.0), 5.0).mesh.raw.volume, abs=1e-6
    ), "und beide Kerne kommen auf dieselbe Zahl"


# --- Als Operation, wie der Kunde sie fährt -----------------------------------


def run(op: str, entry: SceneObject, profile: Profile | None = None, **params: Any) -> OpResult:
    """Eine Operation so fahren, wie die Auswertung sie fährt."""
    load_operations()
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def imported(mesh: MeshData) -> SceneObject:
    """Ein Körper, wie er aus einer STL-Datei kommt — mit erkannten Merkmalen."""
    return SceneObject(id="obj_1", name="Import", mesh=mesh, features=detect(mesh))


def test_the_menu_entries_work_on_an_imported_mesh() -> None:
    """Der Punkt der Übung: Beide Zeilen sind an einem STL nicht mehr ausgegraut."""
    body = stairs()
    entry = imported(body)
    chosen = face_looking_up(body, below=15.0)

    pushed = run("push_face", entry, face=chosen.id, distance=5.0)
    drafted = run("draft_faces", imported(block()), angle=DRAFT)

    assert pushed.outputs[0].kind == "mesh", "aus einem Netz wird kein exakter Körper (§30)"
    assert pushed.outputs[0].mesh.volume == pytest.approx(21000.0, abs=1e-6)
    assert pushed.solver is not None and pushed.solver.strategy == "direct"
    assert drafted.outputs[0].mesh.volume == pytest.approx(drafted_volume(DRAFT), abs=1e-6)


def test_pushing_without_a_chosen_face_says_what_is_missing() -> None:
    """Am Netz gibt es den Richtungsweg nicht — und der Satz sagt, was fehlt.

    Die Richtungsfelder tragen nur gespeicherte Schritte von exakten Körpern
    (§16). Ein Netz kann keinen solchen Schritt haben, denn die Operation
    verlangte bis heute einen exakten Körper; hier wäre die Richtung also kein
    Erbe, sondern der Fehler selbst.
    """
    with pytest.raises(GeometryError) as problem:
        run("push_face", imported(block()), distance=5.0, nz=1.0)

    assert "keine Fläche gewählt" in str(problem.value.detail)
    assert problem.value.suggestions


def test_a_face_that_is_gone_is_a_sentence_and_not_a_wrong_body() -> None:
    """Ein Merkmalsverweis altert (§21.2) — und sagt es, statt zu raten."""
    body = block()
    top = face_looking_up(body)
    stale = Feature(
        id=top.id,
        kind="face",
        provenance=top.provenance,
        params=top.params,
        face_indices=(9999,),
    )

    with pytest.raises(GeometryError) as problem:
        push_face(body, stale, 2.0)

    assert "nicht mehr" in str(problem.value.detail)
    assert problem.value.suggestions


def test_the_exact_body_still_takes_the_exact_way() -> None:
    """Und der exakte Körper bleibt exakt — dieselbe Menüzeile, anderer Kern."""
    pytest.importorskip("app.core.brep.profiles")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")
    from app.core.brep.edit import box
    from app.core.brep.features import features_of

    solid = box(WIDTH, DEPTH, HEIGHT)
    entry = SceneObject(
        id="obj_1", name="Block", mesh=solid, kind="brep", features=features_of(solid)
    )

    result = run("draft_faces", entry, angle=DRAFT)

    assert result.outputs[0].kind == "brep"
    assert result.outputs[0].mesh.volume == pytest.approx(drafted_volume(DRAFT), abs=1e-6)


def test_the_profile_decides_whether_a_move_is_worth_a_step(profile: Profile) -> None:
    """Ein Weg unter der Auflösung des Druckers verändert nichts Sichtbares.

    Anders als beim Verrunden gibt es hier keinen eigenen Befund: Der Weg ist
    ein Maß, das der Kunde selbst gesetzt hat, und ein Prisma von 0,01 mm Höhe
    entsteht auch wirklich. Was der Test festhält, ist deshalb nur, dass es
    *rechnet* statt anzuhalten — und dass die Grenze bei genau null liegt.
    """
    body = block()
    top = face_looking_up(body)

    tiny = push_face(body, top, 0.01).mesh.raw
    assert tiny.volume == pytest.approx(WIDTH * DEPTH * (HEIGHT + 0.01), abs=1e-6)

    with pytest.raises(Exception) as problem:
        push_face(body, top, 0.0)
    assert "null" in str(getattr(problem.value, "detail", problem.value))
