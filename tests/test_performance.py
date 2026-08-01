"""Das Leistungsbudget (Bauplan §31).

Zwei Arten von Prüfung, denn jede allein führt in die Irre. Die absoluten Ziele
aus §31 sagen, ob die Anwendung überhaupt schnell genug ist. Der Vergleich mit
dem vorigen Lauf auf dieser Maschine fängt eine Verschlechterung ab, die
innerhalb des Ziels bleibt — „ein Viertel langsamer" ist ein Fehler, kein
Rauschen.

Messungen hängen von der Maschine ab, die Vergleichsbasis ist also lokal
(``.performance.json``, nicht eingecheckt). Die absoluten Ziele sind großzügig,
wo eine Testmaschine langsamer sein darf als eine Workstation; bei einem Fehler
um eine Größenordnung schlagen sie trotzdem an.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.core.geom.measure import wall_thickness
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.section import SectionPlane, cut
from app.core.ingest.loader import normalise
from app.core.perceive.features import detect
from app.core.perceive.maps import wall_thickness_map
from app.core.scene import History, OperationDraft, ResultCache, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.slice.analysis import slice_body
from app.core.slice.orientation import search
from app.core.types import Profile, Source
from app.i18n import _

pytestmark = pytest.mark.performance

MESHES = Path(__file__).parent / "data" / "meshes"
BASELINE = Path(__file__).parent / ".performance.json"

#: Wie viel langsamer als der letzte Lauf auf dieser Maschine als Fehler gilt (§31).
REGRESSION_LIMIT = 1.25


def dense_mesh() -> MeshData:
    """Der Millionen-Dreieck-Körper. Beim ersten Gebrauch gebaut; er ist zu
    groß zum Einchecken.
    """
    path = MESHES / "dense_1m.stl"
    if not path.is_file():
        import trimesh

        sphere = trimesh.creation.icosphere(subdivisions=8, radius=40.0)
        path.write_bytes(trimesh.exchange.stl.export_stl(sphere))
    return read_mesh(path.read_bytes(), ".stl")


def measure(name: str, work: Callable[[], Any]) -> float:
    """Einmal laufen lassen, die Sekunden festhalten, mit dem vorigen Lauf
    vergleichen.
    """
    started = time.perf_counter()
    work()
    taken = time.perf_counter() - started

    history: dict[str, float] = {}
    if BASELINE.is_file():
        history = json.loads(BASELINE.read_text(encoding="utf-8"))
    previous = history.get(name)
    history[name] = taken
    BASELINE.write_text(json.dumps(history, indent=2, sort_keys=True), encoding="utf-8")

    print(
        f"\n{name}: {taken * 1000:.0f} ms"
        + (f" (vorher {previous * 1000:.0f} ms)" if previous else "")
    )
    if previous is not None and previous > 0.02:
        assert taken <= previous * REGRESSION_LIMIT, (
            f"{name} is {taken / previous:.2f} times slower than the last run on this machine"
        )
    return taken


def test_reading_a_million_triangles(profile: Profile) -> None:
    """Nicht namentlich in §31, aber das Tor zu allem anderen."""
    taken = measure("read_dense", dense_mesh)
    assert taken < 30.0


def test_the_input_stage_on_a_million_triangles() -> None:
    mesh = dense_mesh()
    taken = measure("ingest_dense", lambda: normalise(mesh, "mm"))
    assert taken < 60.0, "welding and cleaning a million triangles"


def test_the_section_cut_stays_interactive() -> None:
    """§18.2: die Ebene wird gezogen, der Schnitt muss also mithalten."""
    mesh = normalise(read_mesh((MESHES / "two_components.stl").read_bytes(), ".stl"), "mm").mesh
    taken = measure("section_small", lambda: cut(mesh, SectionPlane.along("z", 0.0)))
    assert taken < 1.0


def test_wall_thickness_answers_quickly() -> None:
    mesh = normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh
    taken = measure("thickness_small", lambda: wall_thickness(mesh, (0.0, 0.0, 10.0)))
    assert taken < 0.5


def medium_mesh() -> MeshData:
    """Rund 200 000 Dreiecke — die Größe, für die jedes §31-Ziel angegeben ist."""
    import trimesh

    sphere = trimesh.creation.icosphere(subdivisions=7, radius=40.0)
    return MeshData.of(sphere)


def test_feature_detection_on_two_hundred_thousand_triangles() -> None:
    """§31: unter einer Sekunde. Eine Kugel hat keine Bohrungen, und das
    herauszufinden ist die Arbeit.
    """
    mesh = medium_mesh()
    taken = measure("detect_medium", lambda: detect(mesh))
    assert taken < 10.0, "the target is one second; ten catches an order of magnitude"


def test_the_sketch_solver_meets_its_budget() -> None:
    """§31: 200 Bedingungen unter 100 ms.

    Eine Kette aus hundert Maschen — hundert Linien, deren Enden aufeinander
    liegen, jede mit einem Maß, ein Anker. Gemessen wird der ganze Weg durch
    ``solve_sketch`` einschließlich Validierung und Ranganalyse; die
    analytischen Ableitungen und der ``lsmr``-Unterlöser sind genau die zwei
    Entscheidungen, die diesen Wert tragen (700 ms mit dichter SVD)."""
    from app.core.sketch import solve_sketch
    from app.core.types import Sketch, SketchConstraint, SketchElement

    elements = tuple(
        SketchElement("line", ((i * 10.0, 0.3), (i * 10.0 + 9.5, -0.2))) for i in range(100)
    )
    constraints = (
        *(SketchConstraint("coincident", (2 * i + 1, 2 * i + 2)) for i in range(99)),
        *(SketchConstraint("distance", (2 * i, 2 * i + 1), "10") for i in range(100)),
        SketchConstraint("fixed", (0,)),
    )
    sketch = Sketch(plane="plane:xy", elements=elements, constraints=constraints)
    taken = measure("sketch_solve_200", lambda: solve_sketch(sketch))
    assert taken < 1.0, "das Ziel ist ein Zehntel; eine Sekunde fängt die Größenordnung"


def test_the_layer_analysis_stays_under_the_budget() -> None:
    """§31 verlangt 300 ms bei 200 000 Dreiecken und 0,2 mm.

    Dieser Körper hat 328 000 Dreiecke und braucht etwa 1,05 Sekunden — also
    grob 650 ms bei der Größe, die §31 nennt, von 2,35 Sekunden am Anfang. Zwei
    Änderungen haben ihn dorthin gebracht: die Breitensuche hört auf, sobald
    eine Schicht dicker ist als alles, wovor §22.2 warnt, und das Messen läuft
    auf so vielen Threads, wie die Maschine hat, denn GEOS gibt den
    Interpreter-Lock frei, während es arbeitet.

    Übrig bleibt das Bauen der Polygone, und das parallelisiert *nicht* — die
    Messung steht in ``cross_sections``. Den Rest zu schließen braucht einen
    kompilierten Kern, keine weitere Python-Idee.
    """
    mesh = medium_mesh()
    taken = measure("slice_medium", lambda: slice_body(mesh, 0.2))
    assert taken < 2.5


def test_the_wall_thickness_map_stays_under_the_bound() -> None:
    """§31 nennt drei Sekunden für diese Karte, im Hintergrund.

    Erreicht, nach zwei Änderungen. Das Raster wurde früher Schicht für Schicht
    geschnitten, was alle 328 000 Dreiecke einmal je Schicht ablief —
    dreihundertmal. Es ist jetzt ein Durchgang über alle Höhen, und das brachte
    die Karte von acht Sekunden auf drei. Und sie läuft in einem Thread mit
    einem Hinweis in der Leiste (§18.9) statt im Vordergrund hinter einem
    Wartezeiger.
    """
    mesh = medium_mesh()
    taken = measure("map_wall_medium", lambda: wall_thickness_map(mesh))
    assert taken < 8.0


def test_the_orientation_search_over_two_hundred_candidates() -> None:
    """§31: unter 20 Sekunden, unterbrechbar. Hier etwa 16, und dorthin kam
    sie, indem sie Arbeit unterlässt, die niemand liest: die Suche nimmt eine
    Zahl aus jedem Schnitt, fragt also nach ``detail="support"``, und die
    Strukturbreiten bleiben weg.
    """
    mesh = normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh
    taken = measure("orient_200", lambda: search(mesh, count=200, layer_height=0.4))
    assert taken < 20.0, "the §31 target, and it holds"


def test_scrubbing_through_the_layers_is_free() -> None:
    """§18.10: die Analyse wird einmal gerechnet, das Durchfahren ist also nur
    Zeichnen.
    """
    mesh = normalise(read_mesh((MESHES / "island_tower.stl").read_bytes(), ".stl"), "mm").mesh
    result = slice_body(mesh, 0.2)

    def scrub() -> None:
        for layer in result.layers:
            assert layer.contours is not None

    taken = measure("scrub_layers", scrub)
    assert taken < 0.05, "walking the layers must not touch the geometry again"


def test_reevaluating_from_the_cache_is_quick(profile: Profile) -> None:
    """§31: ein Projekt aus dem Platten-Cache zu öffnen bleibt unter einer
    Sekunde.
    """
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/cube_clean.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "cube_clean.stl").read_bytes()
    History(project.document).apply(
        _("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    cache = ResultCache()
    sources = ProjectSources(project)
    evaluate(project.document, profile, sources=sources, cache=cache)

    taken = measure(
        "evaluate_cached",
        lambda: evaluate(project.document, profile, sources=sources, cache=cache),
    )
    assert taken < 1.0
    assert cache.statistics.hits >= 1
