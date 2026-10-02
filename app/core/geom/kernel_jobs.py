"""Die langen Aufrufe des Netzkerns als reine Rechnungen: Felder hinein, Felder heraus.

``manifold3d`` gibt den Interpreter während seiner Aufrufe nie her — nicht beim
Aufbau aus ``Mesh64``, nicht in ``simplify``, ``refine_to_length``,
``batch_boolean``, ``decompose`` oder ``to_mesh64``. Gemessen am 27.09.2026
(``konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/gil_kern.py``): Jeder
dieser Aufrufe hielt einen Taktfaden so lange an, wie er rechnete — am
Spielwürfel mit 250 488 Dreiecken
der Aufbau 110 ms, ``refine_to_length(0.05)`` 1,5 s, am Aufbau aus den 4 Mio.
Dreiecken danach 1,3 s. Ein Arbeiterfaden, der den Kern ruft, hält damit das
Fenster an, obwohl er ein Arbeiterfaden ist.

Jede Rechnung hier läuft deshalb an zwei Orten mit denselben Bytes: im Prozess
selbst, wenn sie klein ist oder der Hauptfaden fragt, und im Hilfsprozess
(:mod:`app.core.geom.kernel_process`), wenn sie groß ist. Das geht nur, wenn
sie nichts kennt außer ihren Feldern und Zahlen:

* Hinein gehen ein ``dict`` von Feldern und eines von Zahlen. Kein Feld wird
  verändert — im Prozess sind es die Felder der Szene (Regel 3).
* Heraus kommen eigene, zusammenhängende Felder und Zahlen, Wahrheitswerte
  oder Zeichenketten — nie ein Körper des Kerns, denn der reist nicht über
  eine Prozessgrenze.
* Grenzen und Toleranzen kommen als Zahl vom Aufrufer, nicht als Import: Was
  ein Test an ``mesh_ops`` umstellt, gilt damit auch im Hilfsprozess, und das
  Modul zieht außer ``numpy`` und ``manifold3d`` nichts nach, was den Start
  des Hilfsprozesses verlängert (``component_labels`` lädt trimesh erst, wenn
  es gefragt wird).
* ``check`` steht zwischen zwei Kernaufrufen. Im Prozess wirft es den Abbruch
  (``CancelToken.raise_if_cancelled``), im Hilfsprozess beendet es ihn, wenn
  sein Elternprozess nicht mehr lebt. Einen laufenden Kernaufruf hält keines
  von beiden an — das kann nur das Beenden des Hilfsprozesses.

Die Rechnungen sind aus ``mesh_ops``, ``boolean``, ``prepare_ops`` und
``measure`` hierher gezogen und rechnen Schritt für Schritt wie zuvor; die
Abdrücke vor und nach dem Umzug sind gleich
(``konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/referenz.py``).

Hier steht auch die Seite des Hilfsprozesses (:func:`serve`) samt dem
gemeinsamen Speicher, über den die Felder reisen: Der Hilfsprozess lädt dieses
Modul und sonst keines aus dem Kern.
"""

from __future__ import annotations

import errno
import math
import multiprocessing
import os
import pickle
import sys
import tempfile
import traceback
from collections.abc import Callable, Mapping
from contextlib import suppress
from multiprocessing import shared_memory
from pathlib import Path
from typing import Any, Final

import manifold3d
import numpy as np

#: Felder einer Rechnung, nach Namen.
Arrays = dict[str, np.ndarray]
#: Zahlen, Wahrheitswerte und Zeichenketten einer Rechnung — was ``pickle``
#: bitgleich über die Prozessgrenze trägt.
Values = dict[str, Any]
#: Was eine Rechnung zurückgibt.
Outcome = tuple[Arrays, Values]
#: Wird zwischen zwei Kernaufrufen gerufen und darf werfen.
Check = Callable[[], None]


def solid(vertices: np.ndarray, faces: np.ndarray, face_id: np.ndarray | None = None) -> Any:
    """Das Netz als Körper des Kerns — in doppelter Genauigkeit (Regel 6).

    ``Mesh64``, nicht ``Mesh``: Der einfache Eingang nimmt ``float32``. Die
    native Schnittstelle braucht schreibbare C-Puffer; ein vorheriges
    ``Mesh64``-Ergebnis kann schreibgeschützt sein, und ``np.require``
    kopiert dann. Ein Netz, das kein Volumen umschließt, gibt der Kern wortlos
    leer zurück — die Frage danach stellt der Aufrufer.
    """
    points = np.require(vertices, dtype=np.float64, requirements=("C", "W"))
    corners = np.require(faces, dtype=np.uint64, requirements=("C", "W"))
    if face_id is None:
        return manifold3d.Manifold(manifold3d.Mesh64(points, corners))
    return manifold3d.Manifold(
        manifold3d.Mesh64(vert_properties=points, tri_verts=corners, face_id=face_id)
    )


def mesh_arrays(body: Any) -> Arrays:
    """Eckpunkte und Dreiecke eines Körpers als eigene Felder.

    **Eigene Puffer, nicht der Speicher des Kerns** (Durchsicht 0.5.1): Die
    Ecken aus ``vert_properties`` sind nur lesbar, und die Schichtanalyse des
    Prüfberichts nimmt keinen solchen Puffer; ``fast_simplification`` nimmt nur
    eigene C-Puffer an.
    """
    built = body.to_mesh64()
    return {
        "vertices": np.array(built.vert_properties[:, :3], dtype=np.float64, order="C", copy=True),
        "faces": np.array(built.tri_verts, dtype=np.int64, order="C", copy=True),
    }


def without_slivers(body: Any, tolerance: float) -> Any | None:
    """Der vereinfachte Körper ohne die Schalen, die dünner sind als ``tolerance``.

    ``manifold3d.simplify`` lässt dort, wo es dünne Stellen zusammenzieht,
    kleine geschlossene Schalen stehen: an der Piratenschiff-Baugruppe
    (1 223 836 Dreiecke, ein Teil) bei 0,2 mm zwölf Stück aus vier bis
    vierzehn Dreiecken, im Mittel 0,003 bis 0,03 mm dick, manche verkehrt
    herum und alle an Kanten des Rumpfs anliegend (26.09.2026, RM-212).
    ``mesh_ops._as_mesh`` verschweißt ihre Ecken mit denen des Rumpfs, vier
    Kanten trugen danach vier Flächen, und die Boolesche Kette lehnte das
    grobe Netz der Vorschau ab — jede Zahl im Bohrdialog rechnete genau.

    Gemessen wird die mittlere Dicke einer Schale, doppeltes Volumen durch
    Oberfläche. Was dünner ist als die Toleranz, mit der der Kern gerade
    vereinfacht hat, hat unter dessen eigener Zusage keine Form mehr; das
    dünnste echte Teil an vier Kundenmodellen (Waschschüssel, Eiffelturm,
    Spiderman, Piratenschiff, je bei 0,05 und 0,2 mm) war über 1 mm dick.
    ``None``, wenn nichts übrig bliebe.
    """
    parts = body.decompose()
    if len(parts) < 2:
        return body
    kept = [part for part in parts if 2.0 * abs(part.volume()) > tolerance * part.surface_area()]
    if len(kept) == len(parts):
        return body
    if not kept:
        return None
    return manifold3d.Manifold.compose(kept)


def native_contact(body: Any, volume: float) -> bool:
    """Erkennt ausschließlich Volumenreste innerhalb der nativen Float64-Rechengrenze."""
    bounds = body.bounding_box()
    # Ein exakt flacher Hüllquader beweist Nullvolumen. Das native Integral
    # kann für solche Kontaktflächen trotzdem positive oder negative
    # Rundungsreste liefern; sie rechtfertigen keinen geometrischen Rückfall.
    if any(bounds[index + 3] <= bounds[index] for index in range(3)):
        return True
    # Gedrehte oder gekrümmte Nullhüllen besitzen einen räumlichen Hüllquader.
    # Die Fehlerfortpflanzung über Differenzen, Kreuz- und Skalarprodukt hat
    # die Form gamma(8) * Koordinatengröße * Oberfläche: Positionsunsicherheit
    # mal Fläche ergibt Volumenunsicherheit. Das Band folgt Float64, nicht
    # einer Drucktoleranz, EPS_GEOM oder einer absoluten Volumenschranke.
    relative_error = 8.0 * np.finfo(np.float64).eps
    roundoff = (
        relative_error
        / (1.0 - relative_error)
        * max(abs(value) for value in bounds)
        * body.surface_area()
    )
    return math.isfinite(roundoff) and abs(volume) <= roundoff


def longest_side(points: np.ndarray, corners: np.ndarray) -> float:
    """Die längste Dreiecksseite, Seite für Seite gemessen.

    Ohne die Kanten erst zu gruppieren — das wäre an acht Millionen Dreiecken
    ein Sortierlauf je Durchgang. Normen über eine Achse rechnen auf jeder
    Maschine gleich; an dieser Zahl hängt, ob ein weiterer Durchgang folgt.
    """
    longest = 0.0
    for first, second in ((0, 1), (1, 2), (2, 0)):
        sides = points[corners[:, second]] - points[corners[:, first]]
        longest = max(longest, float(np.linalg.norm(sides, axis=1).max(initial=0.0)))
    return longest


# --- die Rechnungen -----------------------------------------------------------------
#
# Jede nimmt ``(arrays, values, check)`` und gibt ``(arrays, values)`` zurück. Die
# Namen in :data:`JOBS` sind der einzige Weg in den Hilfsprozess; ausgeführt wird
# dort nichts, was nicht hier steht (Regel 11).


def display_simplify(arrays: Mapping[str, np.ndarray], values: Values, check: Check) -> Outcome:
    """Der erste Weg von ``mesh_ops.decimate_for_display``: der Kern nach Toleranz.

    Beginnt bei ``tolerance`` und wächst je Schritt um ``growth``, höchstens
    ``steps`` Schritte, bis höchstens ``target`` Dreiecke bleiben. Ein Schritt,
    der nichts einbringt, beendet die Suche; ``found`` ist falsch, wenn der Kern
    das Netz nicht nimmt, das Ziel nicht erreicht oder nichts gewinnt
    (weniger als ``triangles``, die Zahl des Eingangs).
    """
    body = solid(arrays["vertices"], arrays["faces"])
    if body.is_empty():
        return {}, {"found": False}
    target = int(values["target"])
    tolerance = float(values["tolerance"])
    best = None
    best_tolerance = tolerance
    for _step in range(int(values["steps"])):
        check()
        candidate = body.simplify(tolerance)
        if candidate.is_empty():
            break
        if best is not None and candidate.num_tri() >= best.num_tri():
            break
        best, best_tolerance = candidate, tolerance
        if candidate.num_tri() <= target:
            break
        tolerance *= float(values["growth"])
    if best is None or best.num_tri() > target or best.num_tri() >= int(values["triangles"]):
        return {}, {"found": False}
    best = without_slivers(best, best_tolerance)
    if best is None:
        return {}, {"found": False}
    return mesh_arrays(best), {"found": True}


def simplify_at_most(arrays: Mapping[str, np.ndarray], values: Values, check: Check) -> Outcome:
    """``simplify(tolerance)`` am ganzen Körper — nur, wenn höchstens ``most`` Dreiecke bleiben.

    ``empty`` sagt, dass der Kern das Netz nicht nimmt; ``found`` ist falsch,
    wenn das Ergebnis leer ist oder mehr als ``most`` Dreiecke behält.
    """
    body = solid(arrays["vertices"], arrays["faces"])
    if body.is_empty():
        return {}, {"found": False, "empty": True}
    check()
    flat = body.simplify(float(values["tolerance"]))
    if flat.is_empty() or flat.num_tri() > values["most"]:
        return {}, {"found": False, "empty": False}
    return mesh_arrays(flat), {"found": True, "empty": False}


def simplify_search(arrays: Mapping[str, np.ndarray], values: Values, check: Check) -> Outcome:
    """Die kleinste Abweichung bis ``limit``, mit der höchstens ``target`` Dreiecke bleiben.

    Eine Bisektion über ``simplify``, höchstens ``steps`` Schritte und nur, bis
    das Intervall unter ``limit * resolution`` geschrumpft ist
    (``mesh_ops._manifold_decimation``). ``found`` ist falsch, wenn schon
    ``limit`` das Ziel nicht trägt oder der Kern das Netz nicht nimmt.
    """
    body = solid(arrays["vertices"], arrays["faces"])
    if body.is_empty():
        return {}, {"found": False}
    target = int(values["target"])
    limit = float(values["limit"])
    check()
    best = body.simplify(limit)
    if best.is_empty() or best.num_tri() > target:
        return {}, {"found": False}
    low = 0.0
    high = limit
    for _step in range(int(values["steps"])):
        if high - low <= limit * float(values["resolution"]):
            break
        check()
        middle = (low + high) / 2.0
        candidate = body.simplify(middle)
        if not candidate.is_empty() and candidate.num_tri() <= target:
            high = middle
            best = candidate
        else:
            low = middle
    return mesh_arrays(best), {"found": True}


def refine_conforming(arrays: Mapping[str, np.ndarray], values: Values, check: Check) -> Outcome:
    """Konform teilen, bis keine Kante mehr über ``edge`` liegt (``mesh_ops._split_conforming``).

    ``refine_to_length`` teilt jede Kante in ``ceil(l / edge)`` Stücke, zieht
    im Inneren eines Dreiecks aber neue Kanten, und die können länger sein;
    weitere Durchgänge, höchstens ``passes``, teilen nur noch diese. Die
    Herkunft jedes Dreiecks reist als ``face_id`` durch den Kern und kommt als
    ``origin`` zurück. Wächst das Netz in einem Durchgang über ``most``
    Dreiecke, endet die Rechnung mit ``too_many``; ``empty`` sagt, dass der
    Kern das Netz nicht nimmt. ``slack`` ist die Rechentoleranz, um die eine
    Kante länger sein darf.
    """
    faces = np.asarray(arrays["faces"], dtype=np.uint64)
    body = solid(arrays["vertices"], faces, face_id=np.arange(len(faces), dtype=np.uint64))
    if body.is_empty():
        return {}, {"empty": True, "too_many": 0}
    edge = float(values["edge"])
    most = int(values["most"])
    passes = 0
    while True:
        check()
        body = body.refine_to_length(edge)
        built = body.to_mesh64()
        corners = np.asarray(built.tri_verts, dtype=np.int64)
        if len(corners) > most:
            return {}, {"empty": False, "too_many": len(corners)}
        points = np.array(built.vert_properties[:, :3], dtype=np.float64, order="C", copy=True)
        passes += 1
        if passes >= int(values["passes"]) or longest_side(points, corners) <= edge + float(
            values["slack"]
        ):
            break
    origin = np.asarray(built.face_id, dtype=np.int64)
    return {"vertices": points, "faces": corners, "origin": origin}, {"empty": False, "too_many": 0}


def refine_once(arrays: Mapping[str, np.ndarray], values: Values, check: Check) -> Outcome:
    """Ein Durchgang ``refine_to_length(edge)`` (``mesh_ops.refined``); ``empty`` wie oben."""
    body = solid(arrays["vertices"], arrays["faces"])
    if body.is_empty():
        return {}, {"empty": True}
    check()
    return mesh_arrays(body.refine_to_length(float(values["edge"]))), {"empty": False}


def simplify_and_refine(arrays: Mapping[str, np.ndarray], values: Values, check: Check) -> Outcome:
    """``simplify(deviation)``, dann ``refine_to_length(edge)`` (``mesh_ops.uniform``)."""
    body = solid(arrays["vertices"], arrays["faces"])
    if body.is_empty():
        return {}, {"empty": True}
    check()
    evened = body.simplify(float(values["deviation"])).refine_to_length(float(values["edge"]))
    return mesh_arrays(evened), {"empty": False}


def smooth_and_refine(arrays: Mapping[str, np.ndarray], values: Values, check: Check) -> Outcome:
    """Tangenten aus den Eckpunktnormalen, dann ``refine_to_length(edge)``.

    Die Rechnung von ``mesh_ops.subdivided``. Kanten steiler als ``angle`` Grad
    bekommen keine und bleiben scharf.
    """
    body = solid(arrays["vertices"], arrays["faces"])
    if body.is_empty():
        return {}, {"empty": True}
    smoothed = body.calculate_normals(0, float(values["angle"])).smooth_by_normals(0)
    check()
    return mesh_arrays(smoothed.refine_to_length(float(values["edge"]))), {"empty": False}


#: Die Booleschen Arten des Kerns.
_OPERATIONS: Final = {
    "union": "Add",
    "difference": "Subtract",
    "intersection": "Intersect",
}


def boolean(arrays: Mapping[str, np.ndarray], values: Values, check: Check) -> Outcome:
    """Eine Boolesche Operation über ``bodies`` Körper (``vertices0``/``faces0`` …).

    ``outcome`` ist ``"failed"`` (der Kern meldet einen Fehler oder ein
    negatives Volumen), ``"empty"`` (nichts oder nur Kontaktreste innerhalb der
    Float64-Rechengrenze, :func:`native_contact`) oder ``"mesh"``: Dann liegen
    die verbleibenden Schalen orientiert nebeneinander in ``vertices`` und
    ``faces`` — eine native Vereinigung würde negative Innenschalen als
    eigenständige Körper behandeln und füllen. Nimmt der Kern einen Eingang
    nicht, ist das ein ``ValueError`` wie bisher.
    """
    count = int(values["bodies"])
    manifolds = [
        solid(arrays[f"vertices{index}"], arrays[f"faces{index}"]) for index in range(count)
    ]
    if any(body.status() != manifold3d.Error.NoError for body in manifolds):
        raise ValueError("Manifold could not take over an input mesh")
    operation = getattr(manifold3d.OpType, _OPERATIONS[str(values["kind"])])
    check()
    result = manifold3d.Manifold.batch_boolean(manifolds, operation)
    if result.status() != manifold3d.Error.NoError:
        return {}, {"outcome": "failed"}
    volume = result.volume()
    if native_contact(result, volume):
        return {}, {"outcome": "empty"}
    if not math.isfinite(volume) or volume < 0.0:
        return {}, {"outcome": "failed"}
    parts = result.decompose()
    kept = [part for part in parts if not native_contact(part, part.volume())]
    if not kept:
        return {}, {"outcome": "empty"}
    if len(kept) == len(parts):
        kept = [result]
    vertices: list[np.ndarray] = []
    faces: list[np.ndarray] = []
    vertex_offset = 0
    for part in kept:
        built = part.to_mesh64()
        vertices.append(
            np.array(built.vert_properties[:, :3], dtype=np.float64, order="C", copy=True)
        )
        faces.append(np.asarray(built.tri_verts, dtype=np.int64) + vertex_offset)
        vertex_offset += len(vertices[-1])
    return {
        "vertices": np.concatenate(vertices) if len(vertices) > 1 else vertices[0],
        "faces": np.concatenate(faces) if len(faces) > 1 else faces[0],
    }, {"outcome": "mesh"}


def simplify_closed(arrays: Mapping[str, np.ndarray], values: Values, check: Check) -> Outcome:
    """``simplify(tolerance)`` an einem Körper, den der Kern ohne Fehler nimmt
    (``prepare_ops._without_scars``); ``found`` ist falsch, wenn er ihn nicht nimmt."""
    body = solid(arrays["vertices"], arrays["faces"])
    if body.status() != manifold3d.Error.NoError:
        return {}, {"found": False}
    check()
    built = body.simplify(float(values["tolerance"])).to_mesh64()
    return {
        "vertices": np.array(built.vert_properties[:, :3], dtype=np.float64, copy=True),
        "faces": np.array(built.tri_verts, dtype=np.int64, copy=True),
    }, {"found": True}


def min_gap(arrays: Mapping[str, np.ndarray], values: Values, check: Check) -> Outcome:
    """Kleinster Flächenabstand zweier Körper bis ``search`` (``measure.surface_gap``).

    ``gap`` ist ``None``, wenn der Kern einen der beiden nicht nimmt — eine
    fehlgeschlagene Übernahme ist keine Abstandsaussage.
    """
    first = solid(arrays["vertices0"], arrays["faces0"])
    second = solid(arrays["vertices1"], arrays["faces1"])
    if any(
        body.status() != manifold3d.Error.NoError or body.is_empty() for body in (first, second)
    ):
        return {}, {"gap": None}
    check()
    return {}, {"gap": float(first.min_gap(second, float(values["search"])))}


def component_labels(arrays: Mapping[str, np.ndarray], values: Values, check: Check) -> Outcome:
    """Die Zusammenhangsnummer jedes der ``count`` Knoten eines Graphen aus ``edges``.

    Die Frage von ``mesh.face_components``, gestellt wie
    ``trimesh.graph.connected_components`` mit ``engine="scipy"`` sie stellt
    (``connected_component_labels``). ``scipy.sparse.csgraph`` hält den GIL wie
    der Kern: an den 5,8 Mio. Dreiecken des verfeinerten Spielwürfels 0,22 bis
    0,26 s am Stück (RM-212,
    ``konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/buchhaltung.py``).
    trimesh wird erst hier geladen — der Hilfsprozess startet ohne es.
    """
    from trimesh import graph

    # trimesh trägt hier keine Typen; die Antwort ist ein Feld ganzer Zahlen.
    labelled: Any = graph.connected_component_labels
    labels = labelled(arrays["edges"], node_count=int(values["count"]))
    return {"labels": np.ascontiguousarray(labels)}, {}


#: Was der Hilfsprozess rechnen darf — nach Namen, und sonst nichts.
JOBS: Final[dict[str, Callable[[Mapping[str, np.ndarray], Values, Check], Outcome]]] = {
    "display_simplify": display_simplify,
    "simplify_at_most": simplify_at_most,
    "simplify_search": simplify_search,
    "refine_conforming": refine_conforming,
    "refine_once": refine_once,
    "simplify_and_refine": simplify_and_refine,
    "smooth_and_refine": smooth_and_refine,
    "boolean": boolean,
    "simplify_closed": simplify_closed,
    "min_gap": min_gap,
    "component_labels": component_labels,
}


# --- Felder im gemeinsamen Speicher -------------------------------------------------
#
# **Kopiert wird mit numpy, nicht mit pickle.** Gemessen an den 4 Mio. Dreiecken
# des verfeinerten Spielwürfels (147 MB, ``gil_kern.py``): ``pickle.dumps`` hielt
# den Interpreter 70 ms an, ``pickle.loads`` 37 ms — und das je Richtung, im
# Faden, der auf den Hilfsprozess wartet, also neben dem Fenster. ``np.copyto``
# in den gemeinsamen Speicher und die Kopie heraus geben ihn her: längster
# Stillstand 1 bis 9 ms an allen vier Modellen. Durch die Leitung gehen nur
# Namen, Formen und Zahlen.

#: Ein Feld im gemeinsamen Speicher: Name, ``dtype.str``, Form, Versatz.
Layout = list[tuple[str, str, tuple[int, ...], int]]

#: Worauf jedes Feld im Speicher ausgerichtet beginnt, in Bytes — eine
#: Cachezeile; ``numpy`` rechnet auf ausgerichteten Feldern ohne Umweg.
_ALIGNMENT: Final = 64

#: Womit Windows einen gemeinsamen Speicher ablehnt, für den der Speicher nicht
#: reicht: ``ERROR_NOT_ENOUGH_MEMORY``, ``ERROR_OUTOFMEMORY``,
#: ``ERROR_NO_SYSTEM_RESOURCES``, ``ERROR_COMMITMENT_LIMIT``. Gemessen an einem
#: Speicher über der Zusagegrenze: 1455 und 8 — als ``OSError``, nie als
#: ``MemoryError`` (Durchsicht RM-212, B2).
_WINDOWS_OUT_OF_MEMORY: Final = frozenset({8, 14, 1450, 1455})

#: Unter POSIX nur echter Speichermangel; ENOSPC kann allein den Transfer verhindern.
_POSIX_OUT_OF_MEMORY: Final = frozenset({errno.ENOMEM})


def short_of_memory(problem: OSError) -> bool:
    """Ob ein ``OSError`` um einen gemeinsamen Speicher heißt: Der Speicher reicht nicht."""
    return (
        getattr(problem, "winerror", None) in _WINDOWS_OUT_OF_MEMORY
        or problem.errno in _POSIX_OUT_OF_MEMORY
    )


def _opened(**arguments: Any) -> shared_memory.SharedMemory:
    """Ein gemeinsamer Speicher, angelegt oder geöffnet; Speichermangel als ``MemoryError``.

    Aus dem ``OSError`` des Betriebssystems wird der Fehler, den die Rechnungen
    kennen: ``mesh_ops.remesh``, ``uniform`` und ``subdivided`` sagen dem
    Kunden dann, dass der Speicher nicht reicht, und schlagen eine gröbere
    Einstellung vor — statt „unerwarteter Fehler“ mit ``WinError 1455``.
    """
    try:
        return shared_memory.SharedMemory(track=False, **arguments)
    except OSError as problem:
        if short_of_memory(problem):
            raise MemoryError(str(problem)) from problem
        raise


def pack(arrays: Mapping[str, np.ndarray]) -> tuple[shared_memory.SharedMemory | None, Layout]:
    """Legt ``arrays`` in einen neuen gemeinsamen Speicher; ``None`` ohne ein Byte.

    ``track=False``: Unter POSIX meldete sich jeder Speicher sonst bei einem
    eigenen Aufräumprozess an. Aufgeräumt wird hier selbst — wer einen
    Speicher anlegt, gibt ihn frei, und der Empfänger nimmt unter POSIX den
    Namen weg, sobald er ihn geöffnet hat. Reicht der Speicher nicht, kommt
    ``MemoryError`` (:func:`_opened`).
    """
    layout: Layout = []
    plain: list[np.ndarray] = []
    size = 0
    for name, array in arrays.items():
        field = np.asarray(array)
        size = -(-size // _ALIGNMENT) * _ALIGNMENT
        layout.append((name, field.dtype.str, tuple(field.shape), size))
        plain.append(field)
        size += field.nbytes
    if size == 0:
        return None, layout
    segment = _opened(create=True, size=size)
    try:
        for (_name, dtype, shape, offset), field in zip(layout, plain, strict=True):
            target = np.ndarray(shape, dtype=np.dtype(dtype), buffer=segment.buf, offset=offset)
            np.copyto(target, field, casting="no")
            del target
    except BaseException:
        segment.close()
        segment.unlink()
        raise
    return segment, layout


def views(segment: shared_memory.SharedMemory | None, layout: Layout) -> Arrays:
    """Die Felder aus ``layout`` als Sichten auf ``segment`` — ohne Kopie."""
    if segment is None:
        return {name: np.empty(shape, dtype=np.dtype(dtype)) for name, dtype, shape, _ in layout}
    return {
        name: np.ndarray(shape, dtype=np.dtype(dtype), buffer=segment.buf, offset=offset)
        for name, dtype, shape, offset in layout
    }


def copied(name: str | None, layout: Layout) -> Arrays:
    """Die Felder aus einem fremden Speicher als eigene Kopien; danach ist er zu.

    Unter POSIX nimmt der Empfänger den Namen weg (``unlink``): Die Sichten des
    Absenders bleiben gültig, und stirbt einer von beiden, bleibt kein Speicher
    liegen. Unter Windows endet ein Speicher mit seinem letzten offenen Griff.
    """
    if name is None:
        return views(None, layout)
    segment = _opened(name=name)
    try:
        arrays: Arrays = {}
        for field, dtype, shape, offset in layout:
            view = np.ndarray(shape, dtype=np.dtype(dtype), buffer=segment.buf, offset=offset)
            arrays[field] = np.array(view, copy=True)
            del view
        return arrays
    finally:
        segment.close()
        segment.unlink()


def _closed(segment: shared_memory.SharedMemory | None) -> None:
    """Schließt einen Speicher, auch wenn noch eine Sicht auf ihn zeigt.

    Eine Sicht, die eine Ausnahme in ihrem Rahmen festhält, ließe ``close``
    mit ``BufferError`` scheitern; dann gibt der Prozess den Speicher mit
    seinem Ende frei, statt an dieser Stelle zu sterben.
    """
    if segment is None:
        return
    try:
        segment.close()
    except BufferError:
        return


def _portable(problem: BaseException) -> bytes:
    """Eine Ausnahme so verpackt, dass der Elternprozess sie auspacken kann."""
    try:
        blob = pickle.dumps(problem)
        pickle.loads(blob)
    except Exception:
        return pickle.dumps(RuntimeError(f"{type(problem).__name__}: {problem}"))
    return blob


#: ``BELOW_NORMAL_PRIORITY_CLASS`` unter Windows.
_WINDOWS_BELOW_NORMAL: Final = 0x00004000

#: Um so viel rückt der Hilfsprozess unter POSIX nach hinten (``nice``).
_POSIX_NICENESS: Final = 5


def _yield_to_the_window() -> None:
    """Der Hilfsprozess rechnet eine Stufe unter der Anwendung.

    Der Kern rechnet parallel auf allen Kernen. Mit gleicher Priorität stand
    das Fenster auch dann, wenn der Kern den GIL gar nicht mehr hält: Während
    der Verfeinerung des Spielwürfels im Hilfsprozess wachte der Hauptfaden aus
    einem 10-ms-Schlaf 912 und 419 ms zu spät auf, kein anderer Faden rechnete
    (``fenster-nachher-wuerfel2.txt``, 27.09.2026, 28 freigegebene Kerne unter
    Last). Eine Stufe tiefer bekommt jeder Faden der Anwendung Vorrang.

    **Der Preis, gemessen**: Er weicht dann auch jedem fremden Programm. An der
    Senkplatte (genaue Vorschau *Bohrung ändern*, 311 296 Dreiecke) auf einem
    Rechner, den andere Programme zu 100 % auslasteten, brauchte er im Mittel
    von drei Runden 10 bis 30 % länger als mit normaler Priorität (Ø 7:
    13,3 statt 10,3 s, 28.09.2026,
    ``konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/senkplatte.py``) —
    auf freien Kernen weicht er niemandem. Gewählt ist das bedienbare Fenster:
    Um das ging es (RM-212), und die längere Rechnung zeigt Balken und
    *Abbrechen*. Gelingt das Zurückstellen nicht, rechnet er mit gleicher
    Priorität.
    """
    try:
        if hasattr(os, "nice"):
            os.nice(_POSIX_NICENESS)
            return
        import ctypes

        # Die Windows-Namen fehlen in den ctypes-Stubs anderer Plattformen.
        windows: Any = ctypes
        kernel32 = windows.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), _WINDOWS_BELOW_NORMAL)
    except OSError, AttributeError:
        return


def _without_a_temp_folder() -> None:
    """Räumt im Paket den Ordner weg, den PyInstaller jedem Prozess für matplotlib anlegt.

    Der Laufzeithaken ``pyi_rth_mplconfig`` legt beim Start jedes Prozesses
    des Pakets einen leeren Ordner im Temp-Verzeichnis an, setzt
    ``MPLCONFIGDIR`` darauf und räumt ihn erst in ``atexit`` weg. Ein
    Hilfsprozess endet aber oft hart (Abbrechen, ``shutdown``): Am gebauten
    ``Solidon3D.exe`` blieb je Start ein Ordner liegen (Durchsicht RM-212, B4:
    drei Starts, drei Ordner). Der Hilfsprozess lädt nie matplotlib; entfernt
    wird nur ein leerer Ordner direkt im Temp-Verzeichnis.
    """
    folder = os.environ.get("MPLCONFIGDIR")
    if not getattr(sys, "frozen", False) or not folder:
        return
    path = Path(folder)
    with suppress(OSError):
        if path.parent.resolve() == Path(tempfile.gettempdir()).resolve():
            path.rmdir()
            del os.environ["MPLCONFIGDIR"]


def _told(connection: Any, message: tuple[Any, ...]) -> bool:
    """Sendet ``message`` an den Elternprozess — ``False``, wenn er nicht mehr zuhört."""
    try:
        connection.send(message)
    except OSError:
        return False
    return True


def _refusal(problem: BaseException) -> tuple[Any, ...]:
    """Die Antwort, wenn der Hilfsprozess eine Rechnung nicht übernehmen oder übergeben kann."""
    return ("refused", _portable(problem), traceback.format_exc())


def serve(connection: Any) -> None:
    """Die Seite des Hilfsprozesses: Rechnungen annehmen, rechnen, zurückgeben.

    Das Gespräch, je Rechnung (``kernel_process._Helper``):

    1. ``("job", name, speicher, layout, zahlen)`` kommt an; der Hilfsprozess
       öffnet den Speicher und antwortet sofort ``("accepted",)`` — ein
       Hilfsprozess, der das nicht tut, gilt als hängend. Kann er ihn nicht
       öffnen, antwortet er ``("refused", ausnahme, stapel)``.
    2. Er rechnet und antwortet ``("done", speicher, layout, zahlen)``, bei
       einer Ausnahme der Rechnung ``("error", ausnahme, stapel)`` — und
       ``("refused", …)``, wenn für das Ergebnis kein Speicher anzulegen ist.
    3. Nach ``done`` wartet er auf ``("ack",)``: Unter Windows gibt es seinen
       Ergebnisspeicher nur, solange er ihn offen hält.

    Er endet, wenn die Leitung zu ist oder etwas anderes als eine Rechnung
    kommt — und zwischen zwei Kernaufrufen, wenn sein Elternprozess nicht mehr
    lebt (``check``). Ein Kernaufruf selbst ist nicht zu unterbrechen; das
    Beenden übernimmt der Elternprozess, unter Windows auch dessen Ende
    (``process.bind_helper``).

    **Nichts entweicht ihm** (Durchsicht RM-212, B2). Eine Ausnahme aus
    ``serve`` schriebe ``multiprocessing`` nach ``sys.stderr`` — im
    Fensterpaket unter Windows ``None``: Der ``AttributeError`` liefe bis in
    den Startcode von PyInstaller, und der zeigte einen Traceback in einem
    eigenen Fenster, neben der Meldung der Anwendung. Hört der Elternprozess
    nicht mehr zu, endet der Hilfsprozess still und auf dem gewöhnlichen Weg,
    damit ``atexit`` noch aufräumt.
    """
    try:
        _without_a_temp_folder()
        _serve(connection)
    except BaseException:
        if sys.stderr is not None:
            with suppress(Exception):
                traceback.print_exc()


def _serve(connection: Any) -> None:
    """Die Schleife von :func:`serve`, ohne ihren letzten Fang."""
    parent = multiprocessing.parent_process()

    def check() -> None:
        if parent is not None and not parent.is_alive():
            os._exit(0)

    _yield_to_the_window()
    if not _told(connection, ("ready", os.getpid())):
        return
    while True:
        try:
            message = connection.recv()
        except EOFError, OSError:
            return
        if not isinstance(message, tuple) or not message or message[0] != "job":
            return
        _kind, job, name, layout, values = message
        try:
            segment = _opened(name=name) if name else None
        except Exception as problem:
            if not _told(connection, _refusal(problem)):
                return
            continue
        if not _told(connection, ("accepted",)):
            _closed(segment)
            return
        failure: tuple[bytes, str] | None = None
        outcome: Outcome = ({}, {})
        arrays: Arrays = {}
        try:
            arrays = views(segment, layout)
            outcome = JOBS[job](arrays, values, check)
        except Exception as problem:
            failure = (_portable(problem), traceback.format_exc())
        finally:
            arrays = {}
        _closed(segment)
        if failure is not None:
            if not _told(connection, ("error", *failure)):
                return
            continue
        result, reported = outcome
        try:
            out, out_layout = pack(result)
        except Exception as problem:
            del result, outcome
            if not _told(connection, _refusal(problem)):
                return
            continue
        del result, outcome
        if not _told(
            connection, ("done", out.name if out is not None else None, out_layout, reported)
        ):
            if out is not None:
                with suppress(OSError):
                    out.unlink()
                _closed(out)
            return
        if out is None:
            continue
        try:
            connection.recv()
        except EOFError, OSError:
            # Unter POSIX kann der Elternprozess den Namen schon weggenommen
            # haben (``copied``), bevor er starb.
            with suppress(OSError):
                out.unlink()
            _closed(out)
            return
        _closed(out)
