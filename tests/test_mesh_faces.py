"""Die **Flächen** eines Netzes bearbeiten — versetzen und anstellen.

Derselbe Auftrag wie bei den Kanten (`test_mesh_edges.py`): Ein importiertes
Modell soll dieselben Werkzeuge annehmen wie ein selbst gezeichnetes
(Entscheidung Robert, 10.09.2026). Und ein zweiter Befund desselben Tages
steckt hier drin — *Fläche versetzen* nahm eine **Richtung** entgegen und
bewegte jede Fläche, die dorthin zeigte.
"""

from __future__ import annotations

import math
import pathlib
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import GeometryError, OperationCancelled
from app.core.geom import faces
from app.core.geom.boolean import boolean
from app.core.geom.faces import (
    SAME_PLANE_ENOUGH,
    _upright_faces,
    draft_vertical,
    push_face,
)
from app.core.geom.mesh import MeshData
from app.core.perceive.features import _one_body, detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Feature, OpContext, OpResult, Profile, Scene, SceneObject
from app.core.units import EPS_GEOM

CORPUS = pathlib.Path(__file__).parent / "data" / "meshes"
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


def flat_plate() -> MeshData:
    """Eine flache Platte 8 × 5 × 0,5 — der Körper aus Roberts Befund.

    Die beiden schmalen Wände messen 2,5 mm², und genau damit fallen sie
    durch jede Schwelle der Merkmalserkennung: ``MIN_FACE_AREA`` liegt bei
    4,0, und fünf Prozent der Gesamtoberfläche sind 4,65.
    """
    body = trimesh.creation.box(extents=(8.0, 5.0, 0.5))
    body.apply_translation((0.0, 0.0, 0.25))
    return MeshData(body)


def test_the_draft_reaches_every_wall_not_just_the_recognised_ones() -> None:
    """Alle vier Wände stehen an, auch die, die kein Merkmal geworden ist.

    **Der Befund Robert, 18.09.2026:** „ganzes Modell gewählt nur 2 seiten
    verändern sich". Gemessen an ``plate_cm.stl`` — einem Quader —, lieferte
    die Erkennung vier Flächen statt sechs: Die beiden schmalsten fehlten,
    und die Formschräge stellte an, was sie fand.

    Das war keine Fehlfunktion der Erkennung. Sie beantwortet die Frage
    „was kann der Kunde anklicken", und eine Fläche von 2,5 mm² an einem
    Teil von 93 mm² Oberfläche ist darauf eine vertretbare Antwort. Für
    diese Operation ist es die falsche Frage: Hier zählt jede ebene Wand.
    """
    plate = flat_plate()
    recognised = [
        entry
        for entry in detect(plate).values()
        if entry.kind == "face" and abs(entry.params["normal"][2]) <= 0.1
    ]
    assert len(recognised) == 2, "die Voraussetzung des Befunds: zwei Wände sind kein Merkmal"

    shaped = draft_vertical(plate, DRAFT).mesh.raw

    slope = math.tan(math.radians(DRAFT))
    highest = shaped.vertices[shaped.vertices[:, 2] > 0.5 - 1e-6]
    assert float(highest[:, 0].max()) == pytest.approx(4.0 - slope * 0.5, abs=1e-6), (
        "auch die schmale Wand wandert"
    )
    assert float(highest[:, 1].max()) == pytest.approx(2.5 - slope * 0.5, abs=1e-6)
    assert shaped.bounds[0][0] == pytest.approx(-4.0, abs=1e-6), "unten bleibt jedes Maß"
    assert shaped.bounds[0][1] == pytest.approx(-2.5, abs=1e-6)


def _inner_rings(body: MeshData, height: float) -> list[Any]:
    """Die inneren Konturen eines waagerechten Schnitts — der Rand einer Bohrung.

    Das Maß einer einzelnen Kontur hängt daran, wie man es nimmt (mittlerer
    Durchmesser, größte Sehne, Hüllspanne); ihre **Zahl** hängt an nichts. Der
    Außenumriss fällt über seine Ausdehnung heraus.
    """
    section = body.raw.section(plane_origin=(0.0, 0.0, height), plane_normal=(0.0, 0.0, 1.0))
    assert section is not None, f"bei z = {height} schneidet nichts"
    rings = []
    for entity in section.entities:
        points = section.vertices[entity.points][:, :2]
        span = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))
        if span < 50.0:
            rings.append(entity)
    return rings


def test_the_facets_of_a_bore_do_not_become_walls() -> None:
    """Die Grenze, ohne die die Ergänzung die Operation bricht.

    Ein facettierter Bohrungsmantel besteht aus lauter ebenen senkrechten
    Streifen, die kein Merkmal beansprucht. An ``plate_countersunk.stl`` sind
    das **48** freie Gruppen zu vier erkannten Wänden, und jede bekäme einen
    Keil.

    **Was dabei kaputtgeht, sagt keine Kennzahl.** Der Körper bleibt
    geschlossen, die Kette bleibt auf Stufe ``welded``, und das Volumen geht
    von 18635,703 auf 18622,288 mm³ — dreizehn Kubikmillimeter. Zerlegt wird
    die **Bohrung**: Ihr Rand bei z = 1 mm kommt statt als eine Kontur als 22
    zurück, acht davon ohne Ausdehnung. Der Test misst deshalb den Rand und
    nicht das Volumen.

    (Der frühere Wortlaut sagte, die Rückfallkette falle bis zur Voxelstufe
    durch. Das stimmte, bevor die Ergänzung Nullnormalen und gewölbte Gruppen
    aussortierte; heute rechnet sie durch — die schlechtere Lage, weil man dem
    Ergebnis nichts ansieht.)

    **Der Zylindertest darunter fängt das nicht**, und das ist der Grund für
    diesen hier: Dort ist der Mantel *ein* erkanntes Merkmal, es bleibt also
    gar keine Gruppe frei, und die Grenze kommt nie zum Zug (gemessen über
    eine Mutationsprobe am 18.09.2026).
    """
    plate = MeshData.of(trimesh.load_mesh(str(CORPUS / "plate_countersunk.stl")))
    walls = _upright_faces(plate)
    assert len(walls) == 4, f"nur die vier Außenwände, gefunden: {len(walls)}"

    shaped = draft_vertical(plate, DRAFT).mesh

    assert shaped.raw.is_watertight
    assert shaped.raw.volume < plate.raw.volume, "und angestellt ist er auch"
    assert len(_inner_rings(shaped, 1.0)) == 1, "und die Bohrung ist eine Kontur geblieben"


def test_a_degenerate_triangle_is_no_upright_wall() -> None:
    """Ein Dreieck ohne Fläche hat keine Richtung — und ist keine Wand.

    Ein entartetes Dreieck trägt in ``trimesh`` die Normale ``[0, 0, 0]``, und
    deren Z-Anteil ist null: Ohne Prüfung gilt es als senkrecht, der Keil
    darüber hat die Dicke null, und die Rückfallkette fällt durch alle vier
    Stufen. Gemessen an ``degenerate.stl``: 8 Wände statt 6, davon zwei mit
    Nullnormale, und statt 7190,772 mm³ kam ``BooleanFailedError``.

    Der Merkmalsweg daneben hat die Prüfung seit je (:func:`face_normal`
    wirft bei Länge null); der ergänzte Weg hatte sie nicht.

    **Und der Fall ist keiner am Rand:** ``ingest.loader`` behält entartete
    Dreiecke ausdrücklich, wenn ihr Entfernen ein geschlossenes Netz aufrisse
    — der dort festgehaltene Messfall ist eine erzeugte Datei mit 221 138
    Dreiecken und zwölf entarteten. Also genau das, was Solidon selbst baut.
    """
    body = MeshData.of(trimesh.load_mesh(str(CORPUS / "degenerate.stl")))
    walls = _upright_faces(body)

    assert len(walls) == 6, "die Voraussetzung: sechs senkrechte Wände"
    for triangles, normal in walls:
        direction = np.asarray(normal, dtype=float)
        # **``isfinite`` und nicht nur die Länge.** Die Ebenheitsprüfung
        # daneben verwirft einen Nullvektor ohnehin (sein Skalarprodukt ist
        # null, und der Abstand zu eins reißt ``SAME_PLANE_ENOUGH``) — die eine Gestalt,
        # die sie durchlässt, ist ``0/0``: ``nan > 0,02`` ist falsch. Ohne
        # diese Zeile bewacht der Test seine Nachbarin statt seiner Sperre
        # (gemessen 18.09.2026).
        assert np.isfinite(direction).all(), f"eine Wand ohne Zahl ({len(triangles)} Dreiecke)"
        length = float(np.linalg.norm(direction))
        assert length > EPS_GEOM, f"eine Wand ohne Richtung ({len(triangles)} Dreiecke)"

    shaped = draft_vertical(body, DRAFT).mesh
    assert shaped.raw.is_watertight
    # Die Zahl aus dem Docstring, gemessen und nicht nur genannt. Ohne die
    # Ergänzung sind es drei Wände und 7385,755 mm³ — eine Zusicherung auf
    # ``> 0.0`` hätte beide Zustände durchgelassen.
    assert shaped.raw.volume == pytest.approx(7190.772, abs=0.001)


def test_the_limit_counts_what_it_guesses_not_what_it_knows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Grenze gilt der Ergänzung, nicht der Summe.

    Ein Teil mit vielen **erkannten** senkrechten Flächen bekam sonst keine
    einzige Ergänzung: Gemessen an einem Kundenmodell (Kumiko-Organizer,
    25 erkannte Wände und 12 ebene Kandidaten mit 0,0 Grad Abweichung) wurde
    alles verworfen — also genau bei den Teilen nichts behoben, an denen
    Roberts Befund entsteht.

    Der Docstring der Konstante beschreibt seit je die Ergänzung („über die
    Merkmalserkennung hinaus"); der Code begrenzte die Summe.

    **Die Grenze wird für diesen Test gesenkt, und das ist der Prüfling
    selbst.** Der Unterschied zwischen beiden Zählungen zeigt sich nur an
    einer Grenze, die **zwischen** Summe und Ergänzung liegt, und die hat im
    Korpus keine Datei von sich aus: Wo viel zu ergänzen ist, reißt die
    Ergänzung allein schon zwölf (``generated_figure.stl`` 94,
    ``plate_countersunk.stl`` 48, ``plate_chamfer_and_taper.stl`` 28), und wo
    viel erkannt ist, gibt es nichts zu ergänzen (``oversized.stl``: zehn
    erkannte, null frei). An ``plate_cm.stl`` — dem Stück aus Roberts Befund —
    sind es zwei erkannte und zwei ergänzte; bei einer Grenze von drei reißt
    die Summe, die Ergänzung nicht (alle Zahlen gemessen 18.09.2026).
    """
    plate = MeshData.of(trimesh.load_mesh(str(CORPUS / "plate_cm.stl")))
    recognised = [
        entry
        for entry in detect(plate).values()
        if entry.kind == "face" and abs(entry.params["normal"][2]) <= 0.1
    ]
    assert len(recognised) == 2, "die Voraussetzung dieses Korpusstücks"

    monkeypatch.setattr(faces, "MOST_WALLS_TO_GUESS", len(recognised) + 1)
    walls = _upright_faces(plate)

    assert len(walls) > len(recognised), (
        "die ebenen Kandidaten kommen dazu, obwohl zwei Wände schon erkannt sind"
    )
    assert len(walls) == 4, "und es sind alle vier senkrechten Wände des Quaders"


def test_a_guessed_wall_is_flat_all_over_and_not_only_at_its_first_triangle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Und eine geratene Wand ist überall eben, nicht nur am ersten Dreieck.

    ``trimesh.facets`` gruppiert über einen Krümmungsradius, nicht über einen
    Winkel: Eine gewölbte Fläche kommt als **eine** Gruppe zurück, und deren
    erstes Dreieck steht zufällig senkrecht oder nicht. An
    ``generated_figure.stl`` sind zwei solche Gruppen — 180 Grad Spanne, also
    Dreiecke, die in die Gegenrichtung zeigen. Ein Keil darüber ist kein Keil.

    **Die Grenze wird dafür angehoben, und das ist Absicht.** Sie fängt die
    Gruppen dieser Datei heute vorher ab (94 Kandidaten gegen zwölf), und
    damit stünde die Ebenheitsprüfung ohne Wächter da — der Docstring der
    Funktion nennt genau das: „Dass das heute nicht aufschlägt, liegt an der
    Erkennung und an der Grenze — beides Zufall, keine Zusage." Gemessen mit
    angehobener Grenze: 94 Wände mit null Abweichung gegen 96 mit 2,0.
    """
    body = MeshData.of(trimesh.load_mesh(str(CORPUS / "generated_figure.stl")))
    welded = _one_body(body).raw
    monkeypatch.setattr(faces, "MOST_WALLS_TO_GUESS", 10_000)

    walls = _upright_faces(body)

    assert len(walls) > 12, "die Voraussetzung: diese Datei hat viele Kandidaten"
    for triangles, normal in walls:
        spread = float(
            np.abs(welded.face_normals[np.asarray(triangles, dtype=int)] @ normal - 1.0).max()
        )
        assert spread <= SAME_PLANE_ENOUGH, (
            f"eine Wand aus {len(triangles)} Dreiecken mit {spread:.4f} Abweichung"
        )


def test_a_cylinder_is_not_mistaken_for_a_stack_of_walls() -> None:
    """Und die Ergänzung nimmt keinen Mantel mit.

    Die Gegenprobe zum Test darüber: Ein fein facettierter Zylinder besteht
    aus lauter senkrechten koplanaren Streifen. Jeden davon als eigene Wand
    anzustellen hieße, aus einem Mantel dreihundert Keile zu bauen — der
    exakte Kern stellt nur ebene Flächen an, und das Netz hält sich daran.
    """
    body = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=180)
    body.apply_translation((0.0, 0.0, 10.0))

    with pytest.raises(GeometryError) as problem:
        draft_vertical(MeshData(body), DRAFT)

    assert "senkrechten" in str(problem.value.detail)


def test_an_open_mesh_is_turned_away_before_the_chain_wrecks_it() -> None:
    """Ein offenes Netz wird angehalten, nicht angestellt.

    Die Keile gehen als Differenz in die Rückfallkette, und die braucht
    geschlossene Körper. An ``broken_open.stl`` fielen alle drei Kernstufen
    durch, die Voxelstufe rechnete 3,7 Sekunden und gab von 4000 mm³ noch
    101 zurück — kein angestellter Körper, sondern ein anderer.
    """
    body = trimesh.load_mesh(str(CORPUS / "broken_open.stl"))

    with pytest.raises(GeometryError) as problem:
        draft_vertical(MeshData(body), DRAFT)

    assert "nicht geschlossen" in str(problem.value.detail)
    assert problem.value.suggestions, "Regel 17: nie ohne Handlungsvorschlag"


def test_a_mesh_only_the_weld_closes_still_goes_through() -> None:
    """Und die Gegenprobe: per Index offen ist nicht dasselbe wie offen.

    Eine STL schreibt jedes Dreieck mit eigenen Ecken und ist deshalb nie
    dicht, bevor jemand sie verschweißt — dafür gibt es Stufe 2 der Kette.
    ``plate_countersunk.stl`` ist roh offen und trug die Formschräge immer
    schon; eine Sperre am rohen Netz hätte den Normalfall getroffen.
    """
    body = MeshData(trimesh.load_mesh(str(CORPUS / "plate_countersunk.stl")))
    assert not body.raw.is_watertight, "die Voraussetzung: roh ist es offen"

    shaped = draft_vertical(body, DRAFT).mesh

    assert shaped.raw.is_watertight
    assert shaped.raw.volume < body.raw.volume, "und es ist wirklich angestellt worden"


def test_a_loose_speck_the_wedge_eats_is_named() -> None:
    """Was der Keil ganz abträgt, steht im Bericht.

    Die neutrale Ebene gilt dem ganzen Körper: ``two_components.stl`` trägt
    neben einem Würfel von 20 mm ein loses Stück von 0,2 mm, zehn Millimeter
    über der Unterkante. Bei drei Grad sind das 0,52 mm Abtrag auf 0,2 mm
    Material — richtig gerechnet, und trotzdem nichts, was jemand
    stillschweigend hinnehmen will.
    """
    body = MeshData(trimesh.load_mesh(str(CORPUS / "two_components.stl")))
    assert body.component_count == 2, "die Voraussetzung: zwei Teile"

    outcome = draft_vertical(body, DRAFT)

    assert outcome.mesh.component_count == 1
    spoken = [entry for entry in outcome.findings if entry.code == "draft.parts_consumed"]
    assert spoken, "ein Teil ist verschwunden, und niemand hat es gesagt"
    assert spoken[0].values["before"] == 2 and spoken[0].values["after"] == 1


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("bottom", [-30.0, -10.0, 0.0, 8.0])
def test_drafting_keeps_the_actual_bottom_at_every_height(kind: str, bottom: float) -> None:
    """Ein verschobener Quader behält dieselben Maße und denselben analytischen Abtrag."""
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data

    exact = edit.moved(edit.box(WIDTH, DEPTH, HEIGHT), (0.0, 0.0, bottom))
    mesh = exact if kind == "brep" else as_mesh_data(exact)
    features = features_of(exact) if kind == "brep" else detect(mesh)
    source = SceneObject(id="obj_1", name="Quader", kind=kind, mesh=mesh, features=features)

    result = run("draft_faces", source, angle=DRAFT)

    changed = as_mesh_data(result.outputs[0].mesh)
    assert changed.is_watertight
    assert changed.volume == pytest.approx(drafted_volume(DRAFT), abs=1e-6)
    assert changed.bounds.minimum == pytest.approx((-WIDTH / 2, -DEPTH / 2, bottom), abs=1e-6)
    assert changed.bounds.maximum == pytest.approx(
        (WIDTH / 2, DEPTH / 2, bottom + HEIGHT), abs=1e-6
    )
    if kind == "mesh":
        assert result.solver.strategy == "direct"
    assert source.mesh.volume == pytest.approx(WIDTH * DEPTH * HEIGHT, abs=1e-6)


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


def run(
    op: str,
    entry: SceneObject,
    profile: Profile | None = None,
    *,
    cancelled: Any = None,
    **params: Any,
) -> OpResult:
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
            cancelled=cancelled if cancelled is not None else NeverCancelled(),
        )
    )


def test_the_draft_can_be_stopped_between_its_walls() -> None:
    """Die Formschräge baut je Wand einen Keil — und fragt dazwischen (§15.6).

    Dieselbe Lücke wie bei den Kantenoperationen (`test_mesh_edges.py`): Das
    Token stand im ``OpContext`` und kam nirgends an. Der Quader hat vier
    senkrechte Wände, also gibt es ein „dazwischen"; ein Token, das erst beim
    zweiten Fragen anhält, unterscheidet das von einer Frage am Eingang.
    """
    token = StopsAfterTheFirstWall()

    with pytest.raises(OperationCancelled):
        run("draft_faces", imported(block()), angle=DRAFT, cancelled=token)

    assert token.asked == 2, "gefragt wird je Wand, nicht einmal am Eingang"


class StopsAfterTheFirstWall:
    """Ein Abbruchtoken, das beim zweiten Fragen anhält."""

    def __init__(self) -> None:
        self.asked = 0

    @property
    def is_cancelled(self) -> bool:
        return self.asked >= 2

    def raise_if_cancelled(self) -> None:
        self.asked += 1
        if self.asked >= 2:
            raise OperationCancelled


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


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("distance", [-100000.0, 100000.0])
def test_pushing_rejects_a_distance_many_times_larger_than_the_body(
    kind: str, distance: float
) -> None:
    """Ein fehlendes Dezimalzeichen darf keinen hundert Meter langen Körper erzeugen."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.errors import ValidationError
    from app.core.geom.mesh import as_mesh_data

    exact = edit.box(WIDTH, DEPTH, HEIGHT)
    body = exact if kind == "brep" else as_mesh_data(exact)
    features = features_of(exact) if kind == "brep" else detect(body)
    top = next(
        entry
        for entry in features.values()
        if entry.kind == "face" and entry.params["normal"][2] > 0.9
    )
    source = SceneObject(id="obj_1", name="Klotz", kind=kind, mesh=body, features=features)

    with pytest.raises(ValidationError) as caught:
        run("push_face", source, face=top.id, distance=distance)

    assert caught.value.field == "distance"
    assert caught.value.constraint == "maximum"
    assert "Länge" in str(caught.value.detail)
    assert body.volume == pytest.approx(WIDTH * DEPTH * HEIGHT, abs=1e-6)


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
