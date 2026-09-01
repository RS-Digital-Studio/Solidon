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

import gc
import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from statistics import median
from types import SimpleNamespace
from typing import Any

import pytest

from app.core import deferred
from app.core.export.threemf import AssemblyPart, read_objects, write_assembly
from app.core.geom.autosplit import find_plane
from app.core.geom.measure import wall_thickness
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.section import SectionPlane, cut
from app.core.ingest.loader import normalise
from app.core.perceive.features import detect
from app.core.perceive.maps import wall_thickness_map
from app.core.scene import History, OperationDraft, ResultCache, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.scene.project import load as load_project
from app.core.slice import analysis as slice_analysis
from app.core.slice.analysis import slice_body
from app.core.slice.orientation import search
from app.core.types import Profile, Source
from app.i18n import _

pytestmark = pytest.mark.performance

MESHES = Path(__file__).parent / "data" / "meshes"
EXAMPLES = Path(__file__).parent.parent / "app" / "examples"
BASELINE = Path(__file__).parent / ".performance.json"

#: Wie viel langsamer als der letzte Lauf auf dieser Maschine als Fehler gilt (§31).
REGRESSION_LIMIT = 1.25

#: Wie oft eine Überschreitung hintereinander auftreten muss, bis sie ein
#: Fehler ist (§31).
#:
#: Eine einzelne Überschreitung sagt nichts. Gemessen am 22.08.2026 auf dieser
#: Maschine, zwei aufeinanderfolgende saubere Läufe unter dem Schloss, dieselbe
#: Software: `blend_union` 1335 → 1745 ms (+31 %), `remesh_uniform` +21 %,
#: `subdivide_surface` +17 %, `boolean_medium` +14 %, `orient_200` +12 %. Die
#: Streuung der Maschine reicht damit über die Schwelle hinaus, und eine
#: Schwelle unter der Streuung ist kein Wächter, sondern ein Würfel.
#:
#: Die drei möglichen Antworten waren: die Schwelle hochsetzen — dann fängt sie
#: nichts mehr; die Meldung zum Hinweis machen — dann sieht sie niemand; oder
#: zweimal verlangen. Die dritte steht nicht nur besser da, sie steht schon im
#: Bauplan: §31 sagt „Wer eine Verschlechterung meldet, misst vorher ein
#: zweites Mal auf einer ruhigen Maschine." Das ist genau diese Regel, nur
#: bisher von Hand ausgeführt. Ein Ausschlag ist Last, zwei sind eine Richtung
#: — und der zweite Lauf kostet nichts, weil er ohnehin kommt.
REGRESSION_STRIKES = 2
MIN_RUNS = 3
"""Ab wie vielen Läufen überhaupt verglichen wird.

**Zwei Läufe bewusst blind sind ehrlicher als zwei Läufe falsch rot.** Ein
Median aus einem oder zwei Werten ist keiner: Steht ein Ausreißer darin — und
der migrierte alte Bestwert *ist* einer, er war das Minimum über alle Läufe —,
zieht er die Marke nach unten und meldet zwei Überschreitungen, bevor das
Fenster ihn überstimmen kann. Gemessen am 30.08.2026 an ``boolean_medium``:

    Lauf 1   Marke 451 ms (nur der alte Bestwert)   gemessen 849 → Strike 1
    Lauf 2   Marke 650 ms (451 und 849)             gemessen 838 → Strike 2, rot
    Lauf 3   Marke 838 ms (451, 838, 849)           ab hier trägt sie

Ab dem dritten Wert steht der Ausreißer außen und bestimmt den Median nicht
mehr — das ist genau die Eigenschaft, wegen der hier ein Median steht."""

WINDOW = 5
"""Über wie viele Läufe die Marke gebildet wird.

Fünf: genug, damit ein einzelner günstiger Lauf sie nicht bestimmt, und wenig
genug, dass sie einer echten Änderung in wenigen Läufen folgt. Bei einer
Verlangsamung um mehr als ein Viertel schlägt der Vergleich zu, bevor der
Median nachgezogen ist — die Reihenfolge ist wichtig und nicht zufällig."""


#: Unter welchem Schlüssel die Marken aus der Zeit vor der Trennung nach
#: Aufrufkontext stehen.
#:
#: Sie bleiben in der Datei, weil die dritte Spalte von §31 aus ihr gefüllt
#: wird — verglichen wird gegen sie nicht mehr. Zu welchem Kontext sie gehören,
#: weiß niemand, und genau das war der Fehler.
UNKNOWN_CONTEXT = "unknown"

#: Der Aufrufkontext dieses Prozesses. ``_invocation`` setzt ihn, sobald der
#: erste Leistungstest anläuft.
_context: str | None = None


def _invocation_key(session: pytest.Session) -> str:
    """Welche Testdateien in diesem Prozess laufen — der Aufrufkontext aus §31.

    Verglichen wird gegen den besten Wert **je Kontext**, und der Kontext ist
    die Gesellschaft. Dieselbe Rechnung braucht allein 114 ms und hinter
    ``test_slice.py`` 162, weil der Sammler den Haufen des Vorgängers während
    der Messung einholt (der Absatz in ``measure`` rechnet es vor). Ein
    Bestwert über alle Läufe hinweg ist damit der Wert des saubersten Laufs,
    und jeder andere Lauf misst dagegen zu langsam — das ist die Ursache hinter
    „Die Regressionsschwelle schlägt an, ohne dass etwas langsamer wurde".

    Gezählt wird die **Menge** der Dateien, nicht ihre Reihenfolge und nicht,
    wie viele Messungen daraus ausgewählt sind. Für die Reihenfolge braucht es
    nichts: Ohne ordnungsmischendes Plugin läuft eine Datei von oben nach
    unten. Für die Auswahl war die Vermutung naheliegend und ist gemessen
    widerlegt — ``app_start`` liegt bei einer ausgewählten Messung auf 2516 ms
    und bei dreiundzwanzig auf 2571, ``slice_knurl`` bei zwei auf 5442 und bei
    dreiundzwanzig auf 5327. Das ist Rauschen und kein Kontext. Ein Schlüssel,
    der die Auswahl mitnimmt, hätte jede neue Messung in dieser Datei alle
    Marken des vollen Laufs verworfen — für eine Unterscheidung, die es nicht
    gibt.
    """
    files = sorted({item.nodeid.split("::")[0] for item in session.items})
    strangers = [name for name in files if not name.endswith("test_performance.py")]
    if not strangers:
        return "alone"
    stamp = hashlib.sha256("|".join(files).encode("utf-8")).hexdigest()[:6]
    return f"with {len(strangers)} more ({stamp})"


@pytest.fixture(autouse=True)
def _invocation(request: pytest.FixtureRequest) -> None:
    """Hält den Aufrufkontext fest, bevor die erste Messung läuft."""
    global _context
    if _context is None:
        _context = _invocation_key(request.session)


def _runs_of(entry: dict[str, Any]) -> list[float]:
    """Die Läufe eines Eintrags — auch aus der Zeit, als nur einer gemerkt wurde.

    ``best`` war bis zum 30.08.2026 das Minimum über alle Läufe. Es zieht als
    einzelner Lauf ein statt wegzufallen: Eine Marke, die bei null anfängt,
    ist bis zum Fenster voll blind, und blind ist schlechter als ungenau.
    """
    stored = entry.get("runs")
    if isinstance(stored, list) and stored:
        return [float(one) for one in stored][-WINDOW:]
    if "best" in entry:
        return [float(entry["best"])]
    return []


def _read_marks() -> dict[str, dict[str, dict[str, Any]]]:
    """Die Marken dieser Maschine, nach Aufrufkontext geordnet.

    Je Kontext die letzten Läufe und ein Zähler:
    ``{"runs": [Sekunden, …], "strikes": n}``.

    **Drei** ältere Fassungen werden mitgelesen — eine flache Zahl je Name aus
    der Zeit vor der Trennung nach Kontext (sie wandert unter
    ``UNKNOWN_CONTEXT``), eine Zahl je Kontext aus der Zeit vor dem Zähler,
    und ``{"best": …}`` aus der Zeit vor dem Median (30.08.2026). Ein
    Bestwert zieht als **einzelner** Lauf ein: Die Marke fällt damit nicht
    weg, und der Vergleich greift ab dem nächsten Lauf statt erst in fünf.

    Verglichen wird gegen ``UNKNOWN_CONTEXT`` nie wieder, denn zu welchem
    Kontext er gehört, weiß niemand; er bleibt lesbar für die dritte Spalte
    von §31.
    """
    if not BASELINE.is_file():
        return {}
    raw = json.loads(BASELINE.read_text(encoding="utf-8"))
    marks: dict[str, dict[str, dict[str, Any]]] = {}
    for name, value in raw.items():
        if not isinstance(value, dict):
            marks[name] = {UNKNOWN_CONTEXT: {"runs": [float(value)], "strikes": 0}}
            continue
        marks[name] = {
            context: (
                {
                    "runs": _runs_of(entry),
                    # **Der Zähler beginnt von vorn, wenn die Marke wechselt.**
                    # Er zählte Überschreitungen gegen das alte Minimum; gegen
                    # den Median sagt dieselbe Zahl nichts. Ihn mitzunehmen
                    # hieße, einen Test beim ersten Lauf nach dem Umbau rot zu
                    # melden, ohne dass je gegen die neue Marke gemessen wurde.
                    "strikes": int(entry.get("strikes", 0)) if "runs" in entry else 0,
                }
                if isinstance(entry, dict)
                else {"runs": [float(entry)], "strikes": 0}
            )
            for context, entry in value.items()
        }
    return marks


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
    """Einmal laufen lassen, die Sekunden festhalten, mit dem **Median der
    letzten Läufe** desselben Aufrufkontexts auf dieser Maschine vergleichen.

    Je Aufrufkontext gemerkt (§31, ``_invocation_key``) — sonst gilt der Wert
    des saubersten Laufs für alle, und jeder Lauf in Gesellschaft misst
    dagegen zu langsam. An dieser Datei gemessen: `sketch_solve_200` braucht
    allein 114 ms und hinter `test_slice.py` 162 — dieselbe Rechnung, dasselbe
    Ergebnis, achtunddreißig Prozent Unterschied.

    **Der Median über die letzten** :data:`WINDOW` **Läufe, nicht das Minimum
    über alle.** Das Minimum stand hier bis zum 30.08.2026 mit einem guten
    Argument: Eine Messung ist nach oben beliebig verrauschbar — eine Datei
    mit Leistungstests unmittelbar davor genügt schon — und nach unten nicht.
    Das stimmt für **Fremdlast** und nicht für den **Maschinenzustand**: Ein
    Rechner mit hohem Takt und ohne Hintergrunddienst ist schneller, und
    dieser Zustand ist nicht wiederherstellbar. Ein Minimum kann nur sinken,
    nie steigen; ein einziger günstiger Lauf nagelt es für immer fest.

    Gemessen, als es so weit war: Fünf Marken meldeten zwölf bis vierzehn
    Überschreitungen in Folge. Eine Messreihe gegen den Stand vor dem
    verzögerten Geometrieimport zeigte, dass **keine** davon langsamer
    geworden war — `subdivide_surface` braucht dort 1893 ms und hier 1863,
    `boolean_medium` dort 854 und hier 834. Reproduzierbar waren die alten
    Bestwerte auf keinem der beiden Stände. Der Test meldete also über zwei
    Wochen eine Regression, die es nicht gab, und das ist schlimmer als eine
    verpasste: Wer einen Wächter zweimal umsonst prüft, sieht beim dritten Mal
    nicht mehr hin.

    Ein Median verschiebt sich mit dem Maschinenzustand und nicht mit einem
    einzelnen Ausreißer — Fremdlast fängt er weiterhin, denn sie hebt die
    Mehrzahl der Läufe. Und er verdeckt keine echte Verlangsamung: Wer eine
    Rechnung um mehr als ein Viertel teurer macht, reißt die Schwelle sofort,
    und :data:`REGRESSION_STRIKES` schlägt zu, bevor der Median nachgezogen
    ist.

    Die Kehrseite bleibt gewollt: Wer ein Verfahren bewusst durch ein teureres
    ersetzt, bekommt einen roten Test, bis er die Marke verwirft. Genau dann
    soll jemand hinsehen — und die Marke fällt mit einer Begründung im Commit,
    nicht stillschweigend beim nächsten Lauf.

    **Vor der Uhr wird aufgeräumt**, und das ist der Grund, warum der Absatz
    oben von achtunddreißig Prozent sprechen konnte. Nachgemessen am
    20.08.2026, je drei frische Prozesse mit den fünf großen Messungen davor:
    ohne `collect` braucht der Löser 142, 139 und 151 ms, mit `collect` 126,
    122 und 121 — und ein Aufwärmlauf davor ändert *nichts* (146, 149, 144).
    Es sind also keine trägen Importe und keine erste kalte Runde, sondern der
    **Müll der vorigen Tests**, den der Sammler während der Messung einholt:
    Der Haufen ist nach einer Million Dreiecken gewachsen, die nächste
    Generation-2-Sammlung läuft über alles, und sie fällt dem zur Last, der
    gerade gemessen wird.

    Aufgeräumt wird **vor** und nicht während: Was die gemessene Arbeit selbst
    erzeugt, sammelt der Sammler weiter mitten in ihr ein und kostet sie auch
    weiter Zeit — eine Prozedur, die Müll in Massen produziert, soll das
    bezahlen. Weg ist nur die Rechnung des Vorgängers. Damit misst dieselbe
    Rechnung dasselbe, egal was vor ihr lief, und genau darauf ruht der
    Vergleich mit der Marke.
    """
    # Kein `gc.disable()`: Das würde die Kosten der gemessenen Arbeit selbst
    # verstecken und wäre Schönrechnen. Hier fällt nur weg, was ihr nicht
    # gehört.
    gc.collect()
    started = time.perf_counter()
    work()
    taken = time.perf_counter() - started

    context = _context or "alone"
    marks = _read_marks()
    per_context = marks.setdefault(name, {})
    entry = per_context.get(context)
    # Ältere Marken trugen nur ``best``; sie ziehen als einzelner Lauf ein,
    # damit eine gewachsene Baseline nicht wegfällt und der Vergleich nicht
    # erst nach fünf Läufen wieder greift.
    runs: list[float] = _runs_of(entry) if entry is not None else []
    previous: float | None = median(runs) if len(runs) >= MIN_RUNS else None
    strikes = entry["strikes"] if entry is not None else 0

    over = previous is not None and previous > 0.02 and taken > previous * REGRESSION_LIMIT
    strikes = strikes + 1 if over else 0
    per_context[context] = {
        "runs": [*runs, taken][-WINDOW:],
        "strikes": strikes,
    }
    BASELINE.write_text(json.dumps(marks, indent=2, sort_keys=True), encoding="utf-8")

    print(
        f"\n{name} [{context}]: {taken * 1000:.0f} ms"
        + (f" (Marke dieses Kontexts {previous * 1000:.0f} ms)" if previous else "")
        + (
            f" — {strikes}. Überschreitung"
            + (", beim nächsten Lauf rot" if strikes < REGRESSION_STRIKES else "")
            if over
            else ""
        )
    )
    assert strikes < REGRESSION_STRIKES, (
        f"{name} is slower than the mark of this context ({context}) on this machine, "
        f"{REGRESSION_STRIKES} runs in a row — this time {taken * 1000:.0f} ms "
        f"against {(previous or 0.0) * 1000:.0f} ms"
    )
    return taken


def test_reading_a_million_triangles(profile: Profile) -> None:
    """Nicht namentlich in §31, aber das Tor zu allem anderen.

    Der verzögerte Geometrieimport vom 29.08.2026 fiel zunächst in diese
    Marke: solo enthielt sie rund 500 ms ``trimesh``-Import, im Volllauf
    hatte ihn längst ein Vorgänger bezahlt — dieselbe Marke maß je nach
    Sammelumfang zwei verschiedene Dinge (gemessen 1072 ms allein gegen
    427–443 im Volllauf, Register 30.08.2026). Der Import steht deshalb vor
    der Uhr und trägt seine eigene Marke: ``deferred_geometry`` hält fest,
    was der verzögerte Import kostet — die Verschiebung aus dem Kundenstart
    bleibt damit messbar festgehalten, nur nicht mehr im Lesen versteckt —,
    und ``read_dense`` misst in jedem Kontext dasselbe: das Lesen.
    """
    measure("deferred_geometry", lambda: deferred.trimesh.__version__)
    taken = measure("read_dense", dense_mesh)
    assert taken < 30.0


def test_the_input_stage_on_a_million_triangles() -> None:
    mesh = dense_mesh()
    taken = measure("ingest_dense", lambda: normalise(mesh, "mm"))
    assert taken < 60.0, "welding and cleaning a million triangles"


def large_assembly() -> bytes:
    """25 Teile mit zusammen gut 500 000 Dreiecken, als eine 3MF-Baugruppe.

    Die Bauart der Kundendatei aus dem Register („Eine Kunden-3MF hängt vier
    Minuten im Hash", 30.08.2026): nicht ein dichter Körper, sondern viele
    mittlere in einer Datei — jedes Teil wird einzeln gelesen, über seine
    Platzierungsmatrix verschoben und normalisiert, und trimeshs Cache hasht
    dabei je Teil. ``ingest_dense`` sieht diesen Weg nicht: ein Körper, eine
    Kopie, ein Hash. Die Kundendatei selbst bleibt draußen — fremde Lizenz,
    und der Korpus trägt keine 10-MB-Fremdmodelle.
    """
    parts = []
    for n in range(25):
        body = deferred.trimesh.creation.icosphere(subdivisions=5, radius=8.0)
        body.apply_translation((n % 5 * 20.0, n // 5 * 20.0, 8.0))
        parts.append(AssemblyPart(mesh=MeshData.of(body), name=f"part_{n + 1}"))
    return write_assembly(parts)


def test_the_input_stage_on_a_large_assembly() -> None:
    """Der Einleseweg einer Kunden-3MF mit vielen Teilen bleibt im Budget.

    Gemessen wird ab dem fertigen Dateipuffer: Erzeugen und Schreiben der
    Baugruppe liegen **vor** der Uhr, wie bei ``read_dense`` der
    trimesh-Import — sonst misst die Marke solo den Aufbau mit und im
    Volllauf nicht (Register 30.08.2026). Das Budget ist eine absolute
    Zusage mit viel Luft (gemessen 1,8 s am 30.08.2026, mit xxhash);
    eine Regression fängt der Median dieser Maschine.
    """
    payload = large_assembly()
    taken = measure(
        "ingest_assembly",
        lambda: [normalise(part.mesh, "mm") for part in read_objects(payload)],
    )
    assert taken < 30.0, "reading and normalising 25 parts from one 3MF"


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
    """Der bestehende härtere Korpus mit 327 680 Dreiecken."""
    import trimesh

    return MeshData.of(trimesh.creation.icosphere(subdivisions=7, radius=40.0))


def slice_target_mesh() -> MeshData:
    """Exakt 200 000 Dreiecke — die ausdrücklich genannte §31-Größe.

    Feature-Erkennung und Wandkarte behalten den gewachsenen 327-680er-Korpus:
    Das vereinfachte Netz hat eine andere Merkmalstopologie und wäre dort ein
    anderer Test. Nur die Schichtzeile beantwortet zusätzlich die genaue
    Zielgröße, statt von einem um 64 Prozent größeren Körper abzuleiten.
    """
    import trimesh

    sphere = trimesh.creation.icosphere(subdivisions=7, radius=40.0)
    result = MeshData.of(sphere.simplify_quadric_decimation(face_count=200_000))
    assert result.triangle_count == 200_000, "the §31 fixture does not have its named size"
    assert result.is_watertight, "decimation opened the §31 fixture"
    return result


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
    analytischen Ableitungen, der ``lsmr``-Unterlöser und seine begrenzten
    inneren Schritte sind die Entscheidungen, die diesen Wert tragen (700 ms
    mit dichter SVD, 105 ms mit unbeschränktem LSMR, 48–50 ms jetzt)."""
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

    Der weiterhin geschlossene Körper hat jetzt wirklich exakt 200 000
    Dreiecke und liegt nach der ganzen Kette bei 288–299 ms (Median 292 ms).
    Der größere alte Körper mit 327 680 Dreiecken liegt bei 331–355 ms. Am
    Anfang waren es 2,35 Sekunden, über den NumPy-/GEOS-Rückfallweg 1,05.
    Der native Kern schneidet und gruppiert die Ebenensegmente und verkettet
    die Ringe; bekannte Konturen werden nicht zurückübersetzt, eindeutig
    schmale Überhangbänder nicht ein zweites Mal als Brücke vermessen. Zehn
    Threads tragen die vollständige Analyse, sechzehn die Stützsuche.
    """
    mesh = slice_target_mesh()
    taken = measure("slice_medium", lambda: slice_body(mesh, 0.2))
    assert taken < 2.5


def knurled_plate() -> MeshData:
    """Eine Platte mit feinem Rändel aus der Textur-Op — wenige Dreiecke,
    aber tausende getrennte Konturen je Schicht in der Texturzone.
    """
    import trimesh

    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, PrinterProfile, Scene, SceneObject

    load_operations()
    spec = REGISTRY.get("apply_texture")
    plate = SceneObject(
        id="obj_1",
        name="Platte",
        mesh=MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 6.0))),
    )
    result = spec.fn(
        OpContext(
            scene=Scene(objects={"obj_1": plate}, parameters={}),
            inputs=[plate],
            params=spec.params(
                pattern="knurl_diamond", width=56.0, height=36.0, pitch=1.2, depth=0.5, z=3.0
            ),
            profile=Profile(
                printer=PrinterProfile(id="test", title="Test", build_volume=(220.0, 220.0, 250.0)),
                material=None,
            ),
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    return result.outputs[0].mesh


def test_the_layer_analysis_survives_a_knurled_surface() -> None:
    """Viele Konturen sind der eigentliche Härtefall, nicht viele Dreiecke.

    Die Rändel-Platte hat 46 000 Dreiecke — ein Bruchteil des §31-Körpers —
    und stand trotzdem bei 37 Sekunden: die Verschachtelungsanalyse in
    ``_polygon_from`` stellte je Schicht n² einzelne contains-Fragen, bei
    2 898 Ringen also 8,4 Millionen. Über den räumlichen Index sind es vier
    Sekunden; die Schranke hier fängt die Größenordnung, die 25-%-Schwelle
    des Vergleichslaufs den Rest.
    """
    mesh = knurled_plate()
    taken = measure("slice_knurl", lambda: slice_body(mesh, 0.2))
    assert taken < 12.0


def test_the_wall_thickness_map_stays_under_the_bound() -> None:
    """§31 nennt drei Sekunden für diese Karte, im Hintergrund.

    Erreicht, nach zwei Änderungen. Das Raster wurde früher Schicht für Schicht
    geschnitten, was alle 328 000 Dreiecke einmal je Schicht ablief —
    dreihundertmal. Es ist jetzt ein Durchgang über alle Höhen. Die Abtastung
    verwendet außerdem ihre großen Fließkomma- und Ganzzahlfelder wieder,
    statt sie in 175 Schritten neu anzulegen. Beides brachte die Karte von acht
    Sekunden über 3,10 auf 1,43–1,48 Sekunden. Sie läuft weiterhin in einem
    Thread mit einem Hinweis in der Leiste (§18.9) statt im Vordergrund hinter
    einem Wartezeiger.
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


def test_support_aware_auto_split_stays_within_the_orientation_budget(
    profile: Profile,
) -> None:
    """T2: drei Nähte mal drei Grundflächen auf exakt 200 000 Dreiecken.

    §31 nennt für die verwandte, größere Orientierungssuche zwanzig Sekunden.
    Auto Split darf mit seiner begrenzten Vorauswahl nicht darüber liegen;
    die lokale Marke fängt zusätzlich jede Verschlechterung über ein Viertel.
    Erzeugung und Streckung liegen vor der Uhr, gemessen wird nur die Suche.
    """
    mesh = slice_target_mesh()
    raw = mesh.raw.copy()
    raw.apply_scale((4.0, 1.0, 1.0))  # type: ignore[no-untyped-call]
    oversized = MeshData.of(raw)
    assert oversized.triangle_count == 200_000

    taken = measure(_autosplit_support_mark(), lambda: find_plane(oversized, profile))

    assert taken < 20.0, "die T2-Suche bleibt unter dem §31-Budget der Orientierung"


def _autosplit_support_mark() -> str:
    """Trennt die lokale Marke nach tatsächlich verfügbarem Schnittkern."""
    backend = (
        "native"
        if slice_analysis._chain is not None and hasattr(slice_analysis._chain, "plane_segments")
        else "fallback"
    )
    return f"autosplit_support_200k_{backend}"


@pytest.mark.parametrize(
    ("chain", "expected"),
    [
        pytest.param(
            SimpleNamespace(plane_segments=object()),
            "autosplit_support_200k_native",
            id="native",
        ),
        pytest.param(object(), "autosplit_support_200k_fallback", id="without-plane-segments"),
        pytest.param(None, "autosplit_support_200k_fallback", id="fallback"),
    ],
)
def test_auto_split_performance_marks_distinguish_the_slice_backend(
    monkeypatch: pytest.MonkeyPatch, chain: object | None, expected: str
) -> None:
    """Beide gleichwertigen Wege dürfen nie gegeneinander regressionsprüfen."""
    monkeypatch.setattr(slice_analysis, "_chain", chain)

    assert _autosplit_support_mark() == expected


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


def test_the_multicolour_example_opens_without_a_surface_search_explosion(
    profile: Profile,
) -> None:
    """Das echte Dosenprojekt: Boolesche Schritte und zwei Filamentflächen.

    Am 29.08.2026 brauchte seine Kernauswertung 14,11 Sekunden. Nicht die acht
    Booleschen Operationen waren teuer, sondern die anschließende exakte
    Slot-Übertragung: Eine einzelne große Fläche weitete die Suche auf 32,36
    Millionen Dreieckspaare. Nach Größenbändern sind es 224 432 und 1,53
    Sekunden bei identischen Slotwerten. Der Strukturtest in ``test_slots``
    zählt die Paare; dieser hier hält den Kundenweg als Ganzes fest.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    project = load_project(EXAMPLES / "dose-mit-deckel.p3d")
    outcome: list[Any] = []
    taken = measure(
        "open_multicolour_example",
        lambda: outcome.append(
            evaluate(
                project.document,
                profile,
                sources=ProjectSources(project),
                cache=ResultCache(),
            )
        ),
    )

    assert taken < 10.0, "ein kleines Kundenbeispiel darf keine zweistellige Wartezeit haben"
    assert outcome[0].complete
    assert len(outcome[0].scene.objects) == 2


# --- Organische Modellierung (P16.2) ----------------------------------------
#
# Die Messungen, die über den Entwurf aus
# `konzepte/konzept-organische-modellierung-2026-08.md` entscheiden. Sie prüfen die
# **Verfahren**, nicht die Operationen — die gibt es noch nicht, und genau
# darum stehen sie hier: P16.2 darf das Vorhaben stoppen, bevor P16.5 beginnt.
# Sobald `sculpt_strokes` existiert, wird hier auf die Op umgestellt; die
# Zielwerte bleiben.


def brush_field(points: Any, centres: Any, radius: float) -> Any:
    """Die Summe aller Pinselgewichte je Vertex — Entscheidung C.

    Ein KD-Baum, dann je Strich eine Kugelabfrage. Der Aufbau ist der ganze
    Trick: Ein eigener Durchgang über alle Vertices je Strich kostet das
    Produkt aus Strichzahl und Vertexzahl, dieser hier die Summe der
    tatsächlich getroffenen Punkte.
    """
    import numpy as np
    from scipy.spatial import cKDTree

    tree = cKDTree(points)
    weights = np.zeros(len(points))
    for centre in centres:
        near = tree.query_ball_point(centre, radius)
        if not near:
            continue
        near = np.asarray(near, dtype=np.int64)
        away = np.linalg.norm(points[near] - centre, axis=1)
        weights[near] += np.exp(-((away / radius) ** 2))
    return weights


def sculpting_ground() -> tuple[Any, Any, Any, float]:
    """Ein Netz in Sculpting-Auflösung, seine Normalen und tausend Strichmitten."""
    import numpy as np

    points = np.asarray(medium_mesh().raw.vertices, dtype=float)
    normals = np.asarray(medium_mesh().raw.vertex_normals, dtype=float)
    radius = float(np.ptp(points, axis=0).max()) * 0.05
    generator = np.random.default_rng(7)
    centres = points[generator.integers(0, len(points), 1000)]
    return points, normals, centres, radius


def test_a_brush_stroke_stays_inside_a_frame() -> None:
    """§31 (neu): ein Strich unter 50 ms, damit der Pinsel der Hand folgt.

    Gemessen wird der Vorschauweg: der KD-Baum steht seit dem Öffnen der
    Sitzung, und ein Strich schreibt nur die getroffenen Vertices. Die
    naheliegende Vollkopie des Vertex-Arrays kostet das Vierzigfache und ist
    der Fehler, den dieser Test verhindert.
    """
    import numpy as np
    from scipy.spatial import cKDTree

    points, normals, centres, radius = sculpting_ground()
    tree = cKDTree(points)
    buffer = points.copy()

    def one_stroke() -> None:
        near = np.asarray(tree.query_ball_point(centres[0], radius), dtype=np.int64)
        away = np.linalg.norm(buffer[near] - centres[0], axis=1)
        buffer[near] += normals[near] * np.exp(-((away / radius) ** 2))[:, None]

    taken = measure("sculpt_stroke_preview", one_stroke)
    assert taken < 0.05


def test_replaying_a_thousand_strokes_stays_under_two_seconds() -> None:
    """§31 (neu): eine Strichliste neu auszuwerten bleibt im Budget einer
    Parameteränderung.
    """
    points, _normals, centres, radius = sculpting_ground()
    taken = measure("sculpt_replay_1000", lambda: brush_field(points, centres, radius))
    assert taken < 2.0


def test_the_real_stroke_evaluation_meets_the_same_budget() -> None:
    """Dasselbe Budget, aber an der Operation statt am Gewichtsfeld.

    Der Test darüber misst den Kern des Verfahrens und hat in P16.2 den
    Entwurf entschieden. Seit P16.5 gibt es die Auswertung wirklich, und ab
    jetzt gilt die Zahl für sie: mit Normalen, Nachbarschaft, Etappen und dem
    neu gebauten Netz am Ende. Ein Budget, das nur den Kern kennt, deckt nicht
    ab, was der Nutzer wartet.
    """
    import numpy as np

    from app.core.geom.mesh import MeshData
    from app.core.geom.sculpt import apply_strokes
    from app.core.types import Stroke

    mesh = medium_mesh()
    points = np.asarray(mesh.raw.vertices, dtype=float)
    normals = np.asarray(mesh.raw.vertex_normals, dtype=float)
    radius = float(np.ptp(points, axis=0).max()) * 0.05
    generator = np.random.default_rng(7)
    picked = generator.integers(0, len(points), 1000)
    strokes = [
        Stroke(
            point=tuple(points[index]),
            normal=tuple(normals[index]),
            radius=radius,
            strength=0.2,
        )
        for index in picked
    ]

    taken = measure("sculpt_apply_1000", lambda: apply_strokes(MeshData.of(mesh.raw), strokes))
    assert taken < 2.0


def test_gathering_strokes_beats_replaying_them_one_by_one() -> None:
    """Entscheidung C, als Test statt als Behauptung.

    Der ganze Entwurf hängt daran, dass alle Striche in **einem** Durchgang
    billiger sind als jeder für sich.

    Zwei Abstände, nicht einer — das war beim ersten Schreiben dieses Tests
    verwechselt. Über den vollen Weg mit ``warp_batch`` und neu gebautem
    Manifold liegt rund das Sechzigfache dazwischen (§2.5 des Konzepts); hier
    wird nur das Gewichtsfeld gemessen, ohne Manifold, und da sind es rund
    neun. Die Schwelle steht deshalb beim Fünffachen: eng genug, dass eine
    kaputte Annahme auffällt, weit genug, dass eine langsame Maschine nicht
    als Fehler gilt.
    """
    import numpy as np

    points, _normals, centres, radius = sculpting_ground()
    few = centres[:50]

    started = time.perf_counter()
    brush_field(points, few, radius)
    gathered = time.perf_counter() - started

    started = time.perf_counter()
    for centre in few:
        away = np.linalg.norm(points - centre, axis=1)
        np.exp(-((away / radius) ** 2))
    apart = time.perf_counter() - started

    print(f"\ngathered {gathered * 1000:.0f} ms vs. one by one {apart * 1000:.0f} ms")
    assert gathered * 5 < apart


def test_subdivision_stays_under_three_seconds() -> None:
    """§31 (neu): Subdivision auf einem Netz in Arbeitsgröße.

    Gemessen wird die Operation, die ausgeliefert wird, nicht das Verfahren,
    das beim Messen naheliegend schien. In P16.2 stand hier
    ``smooth_out(52.5).refine(2)`` auf einem selbst gebauten Manifold; P16.3
    hat beide Hälften davon ersetzt — ``smooth_by_normals`` statt
    ``smooth_out``, weil Ersteres CAD-Netze zerlegt, und die Zielkantenlänge
    statt eines Teilungsfaktors. Der Weg hin und zurück ins Netz samt
    Verschweißen gehört mit in die Zeit; ihn wegzulassen hieße, ein Budget für
    etwas einzuhalten, das so niemand aufruft.
    """
    import numpy as np

    from app.core.geom.mesh_ops import subdivided

    pytest.importorskip("manifold3d")
    mesh = medium_mesh()
    # Halbe vorhandene Kantenlänge: Das vervierfacht die Dreiecke und ist damit
    # dieselbe Arbeit, die das alte ``refine(2)`` gemessen hat. Die vorhandene
    # Länge als Ziel zu nehmen wäre die bequeme Messung — sie würde kaum etwas
    # teilen und ein Budget bestätigen, das niemand strapaziert hat.
    edge = float(np.median(np.asarray(mesh.raw.edges_unique_length, dtype=float))) / 2.0

    taken = measure("subdivide_surface", lambda: subdivided(mesh, edge, 52.5))
    assert taken < 3.0


def test_evening_out_a_mesh_stays_under_three_seconds() -> None:
    """§31 (neu): dasselbe Budget fürs gleichmäßige Vernetzen.

    Es steht vor dem Sculpting und wird deshalb genauso oft aufgerufen wie das
    Unterteilen — ein Budget, das nur eine der beiden Vorstufen kennt, deckt
    den Weg nicht ab.
    """
    import numpy as np

    from app.core.geom.mesh_ops import uniform

    pytest.importorskip("manifold3d")
    mesh = medium_mesh()
    # Halbe vorhandene Kantenlänge: Das vervierfacht die Dreiecke und ist damit
    # dieselbe Arbeit, die das alte ``refine(2)`` gemessen hat. Die vorhandene
    # Länge als Ziel zu nehmen wäre die bequeme Messung — sie würde kaum etwas
    # teilen und ein Budget bestätigen, das niemand strapaziert hat.
    edge = float(np.median(np.asarray(mesh.raw.edges_unique_length, dtype=float))) / 2.0

    taken = measure("remesh_uniform", lambda: uniform(mesh, edge, 0.0))
    assert taken < 3.0


def test_blending_two_bodies_stays_under_three_seconds() -> None:
    """§31 (neu): das weiche Verschmelzen auf einem Raster in Arbeitsgröße.

    Nicht am §31-Prüfnetz gemessen, sondern an zwei gekreuzten Rohren: Die
    Kosten dieser Operation hängen an der Zahl der **Rasterpunkte**, nicht an
    der Zahl der Dreiecke. Eine Kugel mit 200 000 Dreiecken auf einem groben
    Raster wäre die bequeme Messung; zwei Körper, die einander wirklich
    durchdringen, sind der Fall, für den es die Operation gibt.

    Die Zahl hängt an ``workers=-1`` in der Abstandsabfrage: mit einem Kern
    sind es 9,6 Sekunden statt 1,5, bei identischem Ergebnis. Fällt der Wert
    einmal weg, schlägt dieser Test an und nicht erst der Nutzer.
    """
    import numpy as np
    import trimesh

    from app.core.geom.blend import blend_bodies
    from app.core.geom.mesh import MeshData

    first = trimesh.creation.cylinder(radius=10.0, height=60.0, sections=48)
    second = trimesh.creation.cylinder(radius=10.0, height=60.0, sections=48)
    second.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0]))

    taken = measure(
        "blend_union",
        lambda: blend_bodies(MeshData.of(first), MeshData.of(second), 6.0, 1.0),
    )
    assert taken < 3.0


# --- Die vier Zeilen aus §31, die nie eine Messmarke hatten ------------------
#
# §31 nennt elf Ziele. Sieben hatten eine Marke in `.performance.json`, vier
# nicht — und es sind die vier, die der Nutzer spürt: die Boolesche Operation,
# die Parameteränderung, der Anwendungsstart und die Navigation bei einer
# Million Dreiecken. Eine Zeile ohne Marke ist eine Absicht, die aussieht wie
# ein Zustand; sie stehen deshalb hier zusammen und nicht bei ihren Nachbarn.
#
# Die Navigation in der Ansicht ist die interessante, und sie bekommt **keine**
# Marke unter ihrem eigenen Namen: „flüssig" ist eine Bildrate, ohne GL kein Bild,
# und die Python-Kosten einer Kamerabewegung wären für immer grün — ein
# Messwert, der die Abwesenheit der Sache misst und nicht die Sache. Gemessen
# wird stattdessen der Schritt, der eine Million Dreiecke überhaupt navigierbar
# macht: die Dezimierung für die Anzeige.


def test_a_boolean_operation_on_two_hundred_thousand_triangles() -> None:
    """§31: unter 2 s — die Zeile hatte keine Marke.

    ``blend_union`` mit 1,18 s stand in der dritten Spalte daneben und hat sie
    nie belegt: Das ist ``blend`` auf einem Raster, eine andere Rechnung mit
    anderen Kosten. Hier läuft die nackte Boolesche über die Rückfallkette, an
    der Größe, für die §31 seine Ziele angibt.

    Zwei Kugeln mit Radius 40, deren Mitten 30 mm auseinander liegen — sie
    durchdringen sich wirklich. Zwei Körper, die sich nur berühren, wären die
    bequeme Messung: Die erste Stufe der Kette hätte fast nichts zu tun.
    """
    from app.core.geom.boolean import BooleanOutcome, boolean

    first = medium_mesh()
    moved = medium_mesh().raw.copy()
    moved.apply_translation((30.0, 0.0, 0.0))
    second = MeshData.of(moved)

    outcome: list[BooleanOutcome] = []

    def cut_them() -> None:
        outcome.append(boolean("difference", [first, second]))

    taken = measure("boolean_medium", cut_them)

    assert outcome[0].mesh.triangle_count > 0, (
        "an empty result means a failed chain, and measuring a failure says nothing"
    )
    assert taken < 20.0, "the target is two seconds; twenty catches an order of magnitude"


#: Auf wie viele Dreiecke die Anzeige eine Million herunterrechnet.
#:
#: Die Zahl ist die Prüfgröße aus §31 — dieselbe, für die dort die Boolesche
#: Operation und die Feature-Erkennung ihre Ziele nennen. Die Ansicht führt sie
#: als ``DISPLAY_DECIMATION_TARGET`` ein zweites Mal; von dort wird sie hier
#: **nicht** geholt, denn der Import zöge Qt in einen Lauf, der ohne Fenster
#: auskommt, und die Datei stünde danach in der Fenstergruppe der geteilten
#: Suite. Dass die Zahl an zwei Stellen steht, ist ein Fund und kein Entwurf:
#: Die Schwelle beschreibt Arbeit, die der Kern tut.
DISPLAY_TRIANGLES = 200_000


def test_building_the_display_version_of_a_million_triangles() -> None:
    """Was hinter der Zeile „…-Navigation, flüssig bei 1 Mio. Dreiecken" messbar ist.

    Die Ansicht heißt hier absichtlich nicht mit ihrem Klassennamen, und §31s
    Zeile steht deshalb verkürzt da: ``suite-getrennt.sh`` sucht die
    Fensterdateien **im Text**, und ein einziges Vorkommen in einem Docstring
    sortiert diese Datei zu ihnen — in einen eigenen Prozess, der dann nichts
    zu sammeln hat. Das Skript zählt das seit dem 22.08.2026 nicht mehr als
    Fehllauf (es tat es einen Tag lang, wegen genau dieser zwei Wörter), aber
    ein Prozess für nichts bleibt ein Prozess für nichts.

    Die Ansicht zeichnet nie eine Million: Ab 500 000 Dreiecken (§31) baut er
    eine vereinfachte Fassung und zeigt die. *Deshalb* ist eine Million
    navigierbar — und diese eine Rechnung steht zwischen „Körper geladen" und
    „navigierbar". Wird sie langsamer, wartet der Nutzer, bevor er überhaupt
    ziehen kann; das ist spürbar, und es ist regressionsfähig.

    Was hier **nicht** gemessen wird, ist die Bildrate beim Ziehen. Die braucht
    Bilder auf echter Grafik, und die hat das Tor nicht — das Register führt
    dazu „VTK stirbt in der CI, und die Fenstertests laufen dort nicht mehr".
    Diese Marke tritt nicht an ihre Stelle, sie steht daneben.
    """
    from app.core.geom.mesh_ops import decimate

    mesh = dense_mesh()
    taken = measure("display_decimate_1m", lambda: decimate(mesh, DISPLAY_TRIANGLES))
    assert taken < 30.0, "no target in §31 yet; this bound only catches a runaway"


def test_a_parameter_change_reaches_the_screen_in_time(profile: Profile) -> None:
    """§31: Parameteränderung → sichtbares Ergebnis unter 2 s, nur betroffene Zweige.

    Der Aufbau ist die Zusage selbst: ein teurer Zweig, der den Parameter nicht
    kennt (eine Million Dreiecke, geladen und geschweißt — allein über drei
    Sekunden), und ein zweiter, der an ihm hängt (ein Quader, dessen Breite ein
    Ausdruck ist, und eine Bohrung darin). Gemessen wird die **zweite**
    Auswertung, nachdem der Parameter sich geändert hat.

    Damit prüft die Zahl beide Hälften der Zeile auf einmal: Bleibt sie unter
    zwei Sekunden, ist der teure Zweig aus dem Cache gekommen. Landet sie in
    der Größenordnung der ersten Auswertung, ist „nur betroffene Zweige" nicht
    eingelöst — und das wäre ein Fund und keine Marke.
    """
    from app.core.types import Parameter

    project = new_project("centauri-carbon-2", "petg")
    dense_mesh()  # legt die Datei an, falls sie fehlt
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/dense_1m.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "dense_1m.stl").read_bytes()
    project.document.parameters["breite"] = Parameter(name="breite", value=40.0, unit="mm")

    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    history.apply(
        _("Quader"),
        [
            OperationDraft(
                op="create_box", params={"width": "=@breite", "depth": 30.0, "height": 10.0}
            )
        ],
    )

    cache = ResultCache()
    sources = ProjectSources(project)
    first = evaluate(project.document, profile, sources=sources, cache=cache)
    box_id = next(
        object_id
        for object_id, body in first.scene.objects.items()
        if body.mesh.triangle_count < 1000
    )
    history.apply(
        _("Bohren"), [OperationDraft(op="drill_hole", inputs=(box_id,), params={"diameter": 6.0})]
    )
    evaluate(project.document, profile, sources=sources, cache=cache)

    project.document.parameters["breite"] = Parameter(name="breite", value=52.0, unit="mm")
    before = cache.statistics.hits
    taken = measure(
        "param_change",
        lambda: evaluate(project.document, profile, sources=sources, cache=cache),
    )

    assert cache.statistics.hits > before, "the untouched branch has to come from the cache"
    assert taken < 20.0, "the target is two seconds; twenty catches an order of magnitude"


#: Der Treiber für den Startversuch. Er tut, was ``main()`` bis zum bedienbaren
#: Fenster tut, und hört dort auf.
STARTUP_DRIVER = '''"""Startet Solidon bis zum bedienbaren Fenster und hoert dann auf."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.bootstrap import load_operations, load_user_parts
from app.ui.app import build_application

load_operations()
load_user_parts()
application, window = build_application([])
window.show()
'''


def test_the_application_is_usable_quickly(tmp_path: Path) -> None:
    """§31: Anwendungsstart bis bedienbar unter 3 s — die Zeile hatte keine Marke.

    Gemessen wird ein **eigener Prozess**, und das ist die Entscheidung, die
    diese Marke trägt. Zwei Gründe. Erstens gehört der Prozessstart dazu: Vor
    dem Umbau vom 29.08.2026 zog der Registerimport allein trimesh, scipy und
    networkx nach; im laufenden Testprozess wären sie längst da und die Marke
    eine Zehntelsekunde und eine Lüge. Jetzt hält
    ``test_loading_the_registry_defers_geometry_libraries`` diese Ursache
    einzeln fest, der eigene Prozess weiter ihre Kundenwirkung. Zweitens
    entsteht im Messprozess selbst kein Fenster; die Datei bleibt damit aus
    der Fenstergruppe der geteilten Suite heraus.

    Bis wohin gemessen wird: Register und eigener Bausteinordner geladen,
    Anwendung und Fenster gebaut, Fenster gezeigt — das ist „bedienbar". Nicht
    dabei ist, was ``main()`` davor tut (Ladebildschirm, Freischaltung, eine
    Datei von der Befehlszeile). Der Ladebildschirm gehört bewusst nicht dazu:
    Er verdeckt die Wartezeit, er verkürzt sie nicht.

    Diese Zahl hat eine kalte und eine warme Fassung, und der Unterschied ist
    kein Rauschen: Die ersten zwei Messungen am 22.08.2026 lasen 13 764 und
    12 936 ms, jede weitere an diesem Tag 2500 bis 3000 — fünffach, und dann
    nie wieder. Der Betriebssystem-Cache holt die Dateien der Anwendung beim
    ersten Mal von der Platte und behält sie danach. Nach dem verzögerten
    Geometrieimport misst die warme Fassung am 29.08.2026 1482 ms; eine neue
    kalte Zahl braucht einen geleerten Plattencache und gehört nicht in diesen
    Testlauf.

    Die Marke behält den kleinsten Wert und ist damit die **warme** Zahl. Sie
    ist die richtige für den Vergleich — eine Suite, die mehrmals am Tag läuft,
    startet nie kalt — und sie ist nicht die, die der Nutzer nach dem
    Hochfahren erlebt. Wer die kalte wissen will, muss sie einzeln messen und
    dazwischen den Cache leeren; in dieser Suite steht sie nicht.

    Die Nutzerverzeichnisse sind über Umgebungsvariablen umgebogen (§38), und
    die erbt der Unterprozess — er schreibt nichts in Roberts Profil.
    """
    import subprocess
    import sys

    driver = tmp_path / "until_usable.py"
    driver.write_text(STARTUP_DRIVER, encoding="utf-8")

    root = Path(__file__).parent.parent
    finished: list[subprocess.CompletedProcess[str]] = []

    def start() -> None:
        finished.append(
            subprocess.run(
                [sys.executable, str(driver)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
        )

    taken = measure("app_start", start)

    assert finished[0].returncode == 0, (
        f"the application did not come up: {finished[0].stderr[-2000:]}"
    )
    assert taken < 30.0, "the target is three seconds; thirty catches an order of magnitude"


def test_a_second_step_on_an_unwelded_model_stays_quick(profile: Profile) -> None:
    """Die Regression, die 102 Sekunden gekostet hat — als Marke.

    **Der Bestand konnte sie prinzipiell nicht fangen.**
    ``test_reevaluating_from_the_cache_is_quick`` lädt ``cube_clean.stl`` mit
    **einer** Operation, und bei einem Schritt ist ``old`` leer: ``match`` kehrt
    sofort zurück, ohne je eine Kostenmatrix zu bauen. Gemessen wird die
    Zuordnung erst ab dem **zweiten** Schritt, und teuer wird sie nur bei vielen
    Merkmalen — also braucht dieser Test beides.

    Der Aufbau ist deshalb der des erzeugten Stapels aus ``generate.py``:
    ungeschweißt laden (``weld: False``, dort mit guter Begründung), dann auf
    Maß bringen. Genau zwischen diesen zwei Zuständen lag die Explosion — eine
    STL speichert jedes Dreieck mit eigenen Ecken, die Erkennung hielt jede
    dieser Kanten für eine offene Stelle, und aus 3 372 Dreiecken wurde eine
    Kostenmatrix mit 11,4 Millionen Einträgen.

    Die Schranke fängt die Größenordnung: gemessen 102,3 s vorher und 0,2 s
    nachher. Was innerhalb der Größenordnung schleicht, fängt die
    25-%-Schwelle von ``measure``.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/generated_figure.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "generated_figure.stl").read_bytes()
    history = History(project.document)
    history.apply(
        _("Laden"),
        [
            OperationDraft(
                op="load",
                params={
                    "source": "src_1",
                    "unit": "mm",
                    "weld": False,
                    "remove_degenerate": False,
                    "unify_normals": False,
                },
            )
        ],
    )
    body = project.document.ops[-1].outputs[0]
    history.apply(
        _("Auf Maß"),
        [OperationDraft(op="fit_to_size", inputs=(body,), params={"largest": 100.0})],
    )

    sources = ProjectSources(project)
    outcome: list[Any] = []
    taken = measure(
        "evaluate_unwelded_two_steps",
        lambda: outcome.append(evaluate(project.document, profile, sources=sources)),
    )

    result = outcome[0]
    assert result.complete, "eine abgebrochene Auswertung misst nicht, was sie soll"
    # **Ohne diese Zusicherung misst der Test nichts.** Liefe die Erkennung gar
    # nicht — Dreiecksgrenze, Merkmalsgrenze, ein Fehler —, wäre er der
    # schnellste Test der Suite und völlig blind.
    loops = [
        feature
        for entry in result.scene.objects.values()
        for feature in entry.features.values()
        if feature.kind == "edge_loop"
    ]
    assert loops, "ohne erkannte Merkmale hat die Zuordnung nichts zu tun"
    assert len(loops) < 100, (
        f"{len(loops)} offene Stellen — das ist die Speicherform der Datei, nicht das Modell"
    )
    assert taken < 5.0, "the target is well under a second; five catches the old 102 s"


def test_matching_eight_hundred_features_stays_responsive() -> None:
    """Die Kostenmatrix bleibt auch beim nächsten Merkmalsausreißer bedienbar.

    Das reale Fehlerbild hatte 3 372 Merkmale und brauchte 101 Sekunden. Die
    Erkennung begrenzt diesen Ausreißer inzwischen, doch die quadratische
    Zuordnung bleibt das Sicherheitsnetz für neue Merkmalsarten. 800 Merkmale
    bilden 640 000 Paare: vor der Vektorisierung 6,4 Sekunden auf dieser
    Maschine, danach deutlich unter einer Sekunde.
    """
    from app.core.perceive.matching import match
    from app.core.types import Feature

    old: dict[str, Feature] = {}
    new: dict[str, Feature] = {}
    for index in range(800):
        centre = (float(index % 40) * 2.0, float(index // 40) * 2.0, 0.0)
        params = {
            "centre": centre,
            "axis": (0.0, 0.0, 1.0),
            "diameter": 5.0 + (index % 3) * 0.01,
        }
        old_id = f"old_{index}"
        new_id = f"new_{index}"
        old[old_id] = Feature(id=old_id, kind="hole", provenance="detected", params=params)
        new[new_id] = Feature(id=new_id, kind="hole", provenance="detected", params=params)

    result: list[Any] = []
    taken = measure(
        "match_800",
        lambda: result.append(match(old, new, (40.0, 20.0, 0.0), 100.0)),
    )

    assert len(result[0].mapping) == 800, "a fast wrong assignment proves nothing"
    assert taken < 3.0, "the previous Python loops took 6.4 seconds here"
