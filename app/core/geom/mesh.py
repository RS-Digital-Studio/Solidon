"""Die Mesh-Hülle um den Geometriekern (Bauplan §9, §7).

Der Rest des Kerns spricht mit dem ``Mesh``-Protokoll, nie direkt mit
``trimesh`` oder ``manifold3d``. Das hält den Kern austauschbar und macht den
B-Rep-Kern (§30) zu einer Ergänzung statt einem Umbau.

Eine ``MeshData`` gilt als unveränderlich: jede Operation gibt eine neue
zurück — das ist non-destruktives Bearbeiten, eine Ebene tiefer.
"""

from __future__ import annotations

import io
import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # das 3MF-Modul braucht MeshData, der Import geht also nur in eine Richtung
    from app.core.export.threemf import Part

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import CANCEL, CHOOSE, PROGRAMMING_ERRORS, GeometryError, ValidationError
from app.core.log import get_logger
from app.core.types import BoundingBox, Mesh
from app.core.units import EPS_GEOM, weld_digits, weld_tolerance
from app.i18n import _

_log = get_logger(__name__)

#: Endungen, die die Eingangsstufe lesen kann (§25, „Import").
READABLE_SUFFIXES: tuple[str, ...] = (".stl", ".3mf", ".obj", ".ply", ".off", ".glb", ".gltf")


@dataclass(frozen=True, slots=True)
class MeshData:
    """Ein Körper: Eckpunkte, Dreiecke und ein Materialslot je Dreieck (§20)."""

    raw: trimesh.Trimesh
    slots: tuple[int, ...] = field(default_factory=tuple)

    # --- Protokoll --------------------------------------------------------------

    @property
    def vertex_count(self) -> int:
        return len(self.raw.vertices)

    @property
    def triangle_count(self) -> int:
        return len(self.raw.faces)

    @property
    def bounds(self) -> BoundingBox:
        if self.triangle_count == 0:
            return BoundingBox((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        low, high = self.raw.bounds
        return BoundingBox(
            (float(low[0]), float(low[1]), float(low[2])),
            (float(high[0]), float(high[1]), float(high[2])),
        )

    @property
    def volume(self) -> float:
        # **Ein leeres Netz hat Volumen null und wirft nicht.** ``bounds``
        # darüber fängt den Fall seit je ab, ``volume`` und ``area`` taten es
        # nicht — dieselbe Klasse, zwei Haltungen. trimesh rechnet dort nicht
        # null, sondern wirft ``ValueError: Triangles must be (n, 3, 3)!``,
        # und das kam beim Vergleich zweier gleicher Zustände heraus, sobald
        # die Boolesche Kette ein leeres Ergebnis durchlassen durfte.
        if self.triangle_count == 0:
            return 0.0
        return float(self.raw.volume)

    @property
    def area(self) -> float:
        if self.triangle_count == 0:
            return 0.0
        return float(self.raw.area)

    @property
    def is_watertight(self) -> bool:
        return bool(self.raw.is_watertight)

    @property
    def component_count(self) -> int:
        return len(face_components(self.raw))

    @property
    def slot_indices(self) -> tuple[int, ...]:
        return self.slots

    # --- Aufbau -----------------------------------------------------------------

    @classmethod
    def of(cls, mesh: trimesh.Trimesh, slots: tuple[int, ...] = ()) -> MeshData:
        return cls(raw=mesh, slots=slots)

    def replacing(self, mesh: trimesh.Trimesh) -> MeshData:
        """Eine neue Hülle um einen geänderten Körper; die Slots bleiben, wo
        sie passen."""
        slots = self.slots if len(self.slots) == len(mesh.faces) else ()
        return MeshData(raw=mesh, slots=slots)

    # --- Serialisierung ---------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Verlustfreie Form für den Platten-Cache.

        STL würde Slots und die Darstellungsfarben importierter OBJ-, PLY-
        oder GLTF-Dateien verlieren. Eine Textur wird dabei auf eine Farbe je
        Dreieck abgetastet: Das reicht für die Ansicht, ohne Bilddateien oder
        Druckmaterial vorzutäuschen.
        """
        from app.core.geom.texture import face_colours

        colours = face_colours(self.raw)
        stored_colours = (
            np.clip(np.rint(colours * 255.0), 0.0, 255.0).astype(np.uint8)
            if colours is not None
            else np.empty((0, 3), dtype=np.uint8)
        )
        buffer = io.BytesIO()
        np.savez_compressed(
            buffer,
            vertices=np.asarray(self.raw.vertices, dtype=np.float64),
            faces=np.asarray(self.raw.faces, dtype=np.int64),
            slots=np.asarray(self.slots, dtype=np.int32),
            face_colours=stored_colours,
        )
        return buffer.getvalue()

    @classmethod
    def from_bytes(cls, payload: bytes) -> MeshData:
        with np.load(io.BytesIO(payload)) as data:
            mesh = trimesh.Trimesh(vertices=data["vertices"], faces=data["faces"], process=False)
            slots = tuple(int(entry) for entry in data["slots"])
            colours = data["face_colours"] if "face_colours" in data.files else ()
            if len(colours) == len(mesh.faces):
                alpha = np.full((len(colours), 1), 255, dtype=np.uint8)
                mesh.visual = trimesh.visual.ColorVisuals(
                    mesh=mesh,
                    face_colors=np.column_stack((colours, alpha)),
                )
        return cls(raw=mesh, slots=slots)

    def to_stl(self) -> bytes:
        """Binäres STL, für den Export und die Übergabe an einen Slicer (§29)."""
        result: bytes = trimesh.exchange.stl.export_stl(self.raw)
        return result


def as_mesh_data(mesh: Mesh) -> MeshData:
    """Das konkrete Netz hinter dem Protokoll.

    Operationen deklarieren ``Mesh``, denn das ist der Vertrag (§9) — aber die
    Dreiecksarbeit braucht den Kern. Hier wird ein Körper der falschen Sorte
    mit klarer Meldung abgewiesen (§30).
    """
    if isinstance(mesh, MeshData):
        return mesh
    # §30: der Weg von B-Rep zu Mesh steht jederzeit offen — eine Mesh-Op auf
    # einem exakten Körper funktioniert also: auf seiner Tessellation, und das
    # Objekt kommt danach als Mesh markiert heraus, denn das ist es jetzt.
    converted = getattr(mesh, "to_mesh", None)
    if callable(converted):
        result = converted()
        if isinstance(result, MeshData):
            return result
    raise GeometryError(
        _("Diese Operation arbeitet nur auf Netzen."),
        detail=_("Das Objekt liegt in einer anderen Darstellung vor."),
        # Auch hier nicht die Vorgabe: Netzreparatur macht aus einem exakten
        # Körper kein Netz, und Stellen nennt dieser Fehler keine. Was hilft,
        # ist eine andere Auswahl — der Körper, an dem die Operation arbeiten
        # kann.
        suggestions=(CHOOSE, CANCEL),
    )


def fully_stitched(mesh: trimesh.Trimesh) -> bool:
    """Hat schon jede Kante ihren Partner? Dann ist am Ort nichts mehr zu holen.

    Drei Kanten je Dreieck, jede von zwei Dreiecken geteilt — ein geschlossenes,
    zusammengeführtes Netz hat also ``3F/2`` Nachbarschaften. Wer die erreicht,
    kann durch Zusammenlegen keine Verbindung dazugewinnen.

    Die Frage kostet nichts: ``face_adjacency`` braucht ohnehin jeder, der hier
    vorbeikommt, und ``trimesh`` legt sie am Körper ab. Das ist der Unterschied
    zu einer Abkürzung, die selbst rechnet, was sie abkürzen soll.

    **Wozu sie da ist**, steht in einer Zahl: Das Zusammenlegen der Ecken einer
    Kugel mit 327 680 Dreiecken kostet kalt rund 160 ms und findet nichts. Ohne
    diese Zeile lag die Merkmalserkennung dort bei 733 ms gegen 571 vorher —
    achtundzwanzig Prozent für eine Antwort, die schon dastand.
    """
    return len(mesh.faces) > 0 and 2 * len(mesh.face_adjacency) >= 3 * len(mesh.faces)


def face_components(mesh: trimesh.Trimesh) -> list[np.ndarray]:
    """Zusammenhängende Komponenten als Dreiecksindizes.

    Mit Absicht über die Flächen-Nachbarschaft statt ``Trimesh.split``: das
    Splitten baut Teilnetze und versucht, sie zu reparieren — das ist
    langsamer und zugleich eine Entscheidung, die die Eingangsstufe noch gar
    nicht getroffen hat (§17.1 Schritt 5).

    **Gefragt wird nach dem Teil, nicht nach der Speicherform.** Eine STL kennt
    keine gemeinsamen Ecken; ungeschweißt geladen hat ein solches Netz gar
    keine Flächen-Nachbarschaft, und dann ist jedes Dreieck seine eigene
    Komponente. Gemessen: 796 statt 1 an ``plate_holes.stl``, 12 statt 1 am
    Würfel. Der Prüfbericht schrieb daraufhin „Das Modell besteht aus mehreren
    Teilen" mit 796 daneben, an einem Teil, das aus einem Stück ist.

    Gezählt wird deshalb über die **Vereinigung** beider Lesarten: benachbart
    ist, was eine Kante teilt — nach den gespeicherten Eckennummern *oder* nach
    dem Ort. Das ist der Teil, der nicht selbstverständlich ist, und er hat
    einen gemessenen Anlass: Über den Ort **allein** zerfiel ein
    verrundeter Blend-Körper mit Radius 12 in fünf Stücke. Dort liegen zwei
    Ecken 88 Nanometer auseinander; sie auf denselben Ort zu legen macht aus
    einem Dreieck ein entartetes, das keine Kante mehr teilt — und wenn es eine
    Brücke war, reißt der Graph an einer Stelle, an der nichts fehlt.

    Zusammenführen darf Verbindungen **hinzufügen** und nie welche wegnehmen.
    Die Vereinigung sichert genau das zu, und die Gegenprobe steht daneben:
    Zwei Würfel mit fünf Millimetern Abstand bleiben zwei.

    Das Netz des Aufrufers wird dabei nicht angefasst — umnummeriert wird eine
    Kopie der Flächentabelle, die Dreiecke behalten ihren Platz, und die
    Rückgabe zeigt auf dieselben Dreiecke wie vorher. Die Toleranz ist dieselbe
    wie bei ``repair.merge_vertices`` und ``perceive.features``:
    ``trimesh.scale`` ist die Diagonale des Hüllquaders, also derselbe Wert wie
    ``MeshData.bounds.diagonal`` (nachgemessen, auf die letzte Stelle gleich).
    """
    count = len(mesh.faces)
    if count == 0:
        return []
    return list(
        trimesh.graph.connected_components(
            _adjacency_by_place(mesh), nodes=np.arange(count), engine="scipy"
        )
    )


def _adjacency_by_place(mesh: trimesh.Trimesh) -> np.ndarray:
    """Nachbarschaften nach gespeicherten Nummern **und** nach Ort.

    Die zweite Hälfte ist die, die eine ungeschweißte Datei überhaupt erst
    zusammenhängen lässt; die erste die, ohne die ein zusammengelegter Ort eine
    bestehende Verbindung kosten könnte. Beide zusammen sind die Frage, die
    gemeint ist — der Grund steht bei :func:`face_components`.
    """
    stored = np.asarray(mesh.face_adjacency, dtype=np.int64).reshape(-1, 2)
    if fully_stitched(mesh):
        return stored
    digits = weld_digits(weld_tolerance(float(mesh.scale)))
    _, place = trimesh.grouping.unique_rows(np.asarray(mesh.vertices, dtype=float), digits=digits)
    faces = np.asarray(place, dtype=np.int64)[np.asarray(mesh.faces, dtype=np.int64)]
    welded = np.asarray(trimesh.graph.face_adjacency(faces=faces), dtype=np.int64).reshape(-1, 2)
    return np.vstack([stored, welded])


def on_surface(
    body: trimesh.Trimesh, points: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Für jeden Punkt der nächste Ort auf der Oberfläche, sein Abstand und
    sein Dreieck.

    **Ohne ``rtree``, seit dem 24.08.2026 — und das ist der ganze Zweck dieser
    Funktion.** Der Weg über ``trimesh.proximity`` führte durch dessen Index,
    und ``rtree`` greift auf dieser Maschine in fremde Seiten: Ein Kunde, der
    im Beispiel von Weg 2 die Breite auf 90 stellte, verlor die Anwendung —
    ohne eine Zeile im Protokoll, denn ein nativer Abriss schreibt keine.
    Die Milderungen davor (ein Wiederholversuch an einer Kopie, zwei
    Größenordnungen weniger Anfragen über den Vorfilter in
    ``geom.attributes``) machten den Fehlgriff selten, nicht unmöglich; und
    ein geladenes ``rtree`` beschädigte sogar Unbeteiligtes — das Zahlenlesen
    in ``export/threemf.py`` scheiterte sechsmal öfter, solange es im Prozess
    war.

    Der Ersatz fragt ``cKDTree``-Bäume über den **Dreiecksschwerpunkten**
    (scipy, längst Abhängigkeit) und rechnet exakt nach: Erst der nächste
    Schwerpunkt als Schranke ``u``, dann alle Dreiecke, deren Schwerpunkt
    näher als ``u`` plus ihre Schwerpunkt-Ecke-Spanne liegen kann — jedes
    andere kann die Schranke nicht mehr unterbieten. Auf den Kandidaten
    entscheidet die exakte Rechnung von ``trimesh.triangles``. Das ist
    **kein** Näherungsverfahren: gemessen gegen ``ProximityQuery`` sind die
    Abstände identisch.

    Die Spanne gilt **je Größenband**, nicht einmal als größter Wert des ganzen
    Netzes. Eine einzige große Fläche machte sonst aus dem Baum wieder die
    vollständige Suche: Im Dosenbeispiel wurden 32,36 Millionen Paare exakt
    nachgerechnet, obwohl 99 Prozent der Dreiecke klein sind. Zweierpotenzen
    teilen die Bänder ohne willkürliche Millimetergrenze; dieselbe Datei fragt
    damit noch 224 432 Paare und liefert dieselben Slotwerte.

    Der Baum entsteht je Aufruf und wird nicht am Netz zwischengespeichert —
    der von ``trimesh`` gecachte ``rtree``-Index war genau die Stelle, unter
    der der beschädigte Speicher lag.
    """
    from scipy.spatial import cKDTree
    from trimesh.triangles import closest_point as closest_on

    queries = np.asarray(points, dtype=float).reshape(-1, 3)
    triangles = np.asarray(body.triangles, dtype=float)
    centroids = triangles.mean(axis=1)
    span = np.linalg.norm(triangles - centroids[:, None, :], axis=2).max(axis=1)
    tree = cKDTree(centroids)

    # Die Schranke: exakter Abstand zum Dreieck mit dem nächsten Schwerpunkt.
    _, nearest = tree.query(queries)
    nearest = np.atleast_1d(nearest)
    bound_spot = closest_on(triangles[nearest], queries)
    bound = np.linalg.norm(queries - bound_spot, axis=1)

    # Alle Dreiecke, die sie noch unterbieten könnten. Pro Größenband genügt
    # dessen größte Spanne als Radius; ein großes Dreieck weitet damit nur die
    # Suche unter anderen großen Dreiecken. ``frexp`` liefert Zweierpotenzen
    # ohne eine zweite, in Millimetern festgeschriebene Wahrheit.
    exponents = np.frexp(span)[1]
    parts: list[list[np.ndarray]] = [[] for _ in range(len(queries))]
    for exponent in np.unique(exponents):
        indices = np.flatnonzero(exponents == exponent)
        band_tree = tree if len(indices) == len(triangles) else cKDTree(centroids[indices])
        found = band_tree.query_ball_point(queries, bound + float(span[indices].max()))
        for row, local in enumerate(found):
            if len(local):
                parts[row].append(indices[np.asarray(local, dtype=np.int64)])

    # Der bisherige einzelne Baum gab seine Kandidaten nach Dreiecksnummer
    # geordnet zurück. Die Bandreihenfolge darf an einer exakt geteilten Kante
    # nicht plötzlich den anderen Materialslot gewinnen lassen, deshalb wird
    # dieselbe stabile Reihenfolge ausdrücklich wiederhergestellt.
    grouped = [np.sort(np.concatenate(entries)) for entries in parts]
    counts = np.fromiter((len(group) for group in grouped), dtype=np.int64, count=len(grouped))

    # In Portionen mit begrenzter Paarzahl: Liegen die Punkte weit weg vom
    # Netz, deckt jede Kugel fast alle Schwerpunkte — bei tausend Punkten
    # gegen ein dichtes Netz wären das Milliarden Paare auf einmal im
    # Speicher. Die Grenze kostet im Normalfall nichts, denn dort bleibt es
    # bei einer einzigen Portion.
    budget = 2_000_000
    closest = np.empty_like(queries)
    distance = np.empty(len(queries), dtype=float)
    triangle = np.empty(len(queries), dtype=np.int64)
    lower = 0
    while lower < len(queries):
        upper, pairs = lower, 0
        while upper < len(queries) and (pairs == 0 or pairs + counts[upper] <= budget):
            pairs += int(counts[upper])
            upper += 1
        rows = np.arange(lower, upper)
        owners = np.repeat(rows - lower, counts[rows])
        candidates = np.concatenate([grouped[row] for row in rows]).astype(np.int64)
        spots = closest_on(triangles[candidates], queries[rows][owners])
        gaps = np.linalg.norm(queries[rows][owners] - spots, axis=1)
        order = np.lexsort((gaps, owners))
        best = order[np.searchsorted(owners[order], np.arange(len(rows)), side="left")]
        closest[rows] = spots[best]
        distance[rows] = gaps[best]
        triangle[rows] = candidates[best]
        lower = upper
    return closest, distance, triangle


#: Ab wann eine Möller-Trumbore-Determinante als „Strahl parallel zum
#: Dreieck" gilt. Keine Millimeter (dafür gäbe es ``EPS_GEOM``), sondern das
#: Spatprodukt aus Richtung und zwei Kanten — gemessen wird ein Dreieck mit
#: 1e-6 mm Kantenlänge damit noch getroffen.
RAY_PARALLEL_EPS: Final = 1e-12


def ray_hit_distances(
    triangles: np.ndarray, origin: np.ndarray, direction: np.ndarray
) -> np.ndarray:
    """Alle Strahlparameter, zu denen ein Strahl die gegebenen Dreiecke trifft.

    Möller-Trumbore, vektorisiert über die Dreiecke, exakt und ohne Index —
    die Alternative wäre ``body.ray.intersects_location``, und die baut sich
    ihren Suchbaum über ``rtree`` (warum das Paket den Prozess nicht mehr
    betreten darf, steht an :func:`on_surface`). Für die Anfragen dieses
    Hauses — ein paar Strahlen gegen einen Körper, wie bei der Materialtiefe
    der Stifte — ist die volle Rechnung billiger als jeder Baum, den man
    vorher bauen müsste.

    Zurück kommen die **positiven** Strahlparameter ``t``, unsortiert —
    gemessen von ``origin`` entlang ``direction``, **das normiert erwartet
    wird** (dieselbe Zusage wie bei :func:`ray_span_in_hull`): Mit einer
    Richtung der Länge zwei wäre jeder „Abstand" halb so groß wie der echte.
    Wer den ersten Austritt will, nimmt das Minimum.

    **Ein Treffer auf einer geteilten Kante oder Ecke zählt mehrfach** — je
    einmal pro angrenzendem Dreieck, gemessen: die Diagonale einer Deckfläche
    gibt zwei gleiche Werte, eine Ecke fünf. Für ein Minimum ist das egal;
    für Innen/Außen über die **Parität** der Durchdringungen taugt diese
    Funktion deshalb nicht.
    """
    triangles = np.asarray(triangles, dtype=float)
    origin = np.asarray(origin, dtype=float).reshape(3)
    direction = np.asarray(direction, dtype=float).reshape(3)
    edge_one = triangles[:, 1] - triangles[:, 0]
    edge_two = triangles[:, 2] - triangles[:, 0]
    across = np.cross(direction, edge_two)
    determinant = np.einsum("ij,ij->i", edge_one, across)
    parallel = np.abs(determinant) < RAY_PARALLEL_EPS
    # Division erst nach dem Ausblenden der parallelen — sonst rechnet numpy
    # mit inf weiter und meldet Warnungen über Fälle, die keiner nimmt.
    safe = np.where(parallel, 1.0, determinant)
    to_origin = origin - triangles[:, 0]
    u = np.einsum("ij,ij->i", to_origin, across) / safe
    q = np.cross(to_origin, edge_one)
    v = np.dot(q, direction) / safe
    t = np.einsum("ij,ij->i", edge_two, q) / safe
    inside = ~parallel & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1.0 + 1e-9) & (t > 0.0)
    return np.asarray(t[inside], dtype=float)


def distance_to_triangles(triangles: np.ndarray, point: np.ndarray) -> float:
    """Der kürzeste Abstand von einem Punkt zu einer gegebenen Menge Dreiecke.

    Die Frage hinter „welches Merkmal liegt unter diesem Klick?" (§18.5): Die
    Dreiecke sind die eines erkannten Merkmals, der Punkt ist die Stelle, auf
    die gezeigt wurde. Gerechnet wird gegen den nächsten **Ort auf dem
    Dreieck** und nicht gegen den nächsten Eckpunkt — der Unterschied ist kein
    Feinschliff: Die Deckfläche der Platte aus dem Korpus besteht aus zwei
    großen Dreiecken, und ein Klick in ihre Mitte liegt vierzig Millimeter von
    jedem ihrer Eckpunkte entfernt.

    **Ohne den Näherungsindex**, anders als :func:`on_surface`: Hier steht die
    Dreiecksmenge schon fest, es ist also nichts zu suchen, sondern nur zu
    rechnen — reine Arithmetik über ein Array. Damit bleibt der Weg an
    ``rtree`` vorbei, und was dort oben über Zugriffsverletzungen steht, gilt
    hier nicht.

    Eine leere Menge hat keinen Abstand und bekommt unendlich — der Aufrufer
    vergleicht gegen eine Reichweite, und „unendlich" fällt dort heraus, ohne
    dass er einen Sonderfall braucht.
    """
    gaps = distances_to_triangles(triangles, point)
    return float(gaps.min()) if len(gaps) else float("inf")


def distances_to_triangles(triangles: np.ndarray, point: np.ndarray) -> np.ndarray:
    """Dasselbe je Dreieck statt als Minimum — ein Abstand für jedes.

    Der Pinsel braucht beides (:mod:`app.core.geom.paint`): das nächste Dreieck
    als Startpunkt seines Laufes und die einzelnen Abstände als Grenze seines
    Umfangs. Beides aus derselben Rechnung, und die steht **hier**, weil
    ``trimesh.triangles`` keine Signaturen trägt und diese Datei die typisierte
    Engführung dafür ist — dasselbe Muster wie :func:`concatenated`.
    """
    if not len(triangles):
        return np.empty(0, dtype=float)
    query = np.repeat(np.asarray(point, dtype=float).reshape(1, 3), len(triangles), axis=0)
    nearest = trimesh.triangles.closest_point(np.asarray(triangles, dtype=float), query)
    return np.asarray(np.linalg.norm(np.asarray(nearest, dtype=float) - query, axis=1), dtype=float)


#: Wie viele Eckpunkte höchstens in die konvexe Hülle eingehen
#: (:func:`hull_planes`). Dieselbe Zahl und derselbe Grund wie beim
#: Schattenumriss der Ansicht: Bei einer feinen Kugel liegt **jeder** Punkt auf
#: der Hülle, und die exakte Rechnung kostet dann mehr als sie wert ist.
#: Gemessen an ``dense_1m.stl`` (655 362 Eckpunkte): **5084 ms** exakt gegen
#: **20 ms** über die Stichprobe. An der Korpusplatte liefern beide dasselbe —
#: zwölf Flächen, Volumen 32 000 mm³.
HULL_SAMPLE_LIMIT = 4096


def hull_planes(mesh: Mesh) -> np.ndarray | None:
    """Die konvexe Hülle eines Netzes als Halbräume, ``n·x + d <= 0`` innen.

    Nicht als Netz, sondern als Ebenengleichungen: Die Frage dahinter ist „läuft
    dieser Sichtstrahl **durch** den Körper hindurch?" (:func:`ray_span_in_hull`),
    und die beantwortet ein Halbraumschnitt in einer Handvoll Rechenschritten,
    während ein Strahl gegen ein Hüllnetz wieder jedes Dreieck anfassen müsste.

    **Die Stichprobe ist der Kostendeckel**, und sie unterschätzt die Hülle
    leicht: Jeder ``n``-te Eckpunkt, dazu die äußersten in allen sechs
    Achsenrichtungen, damit ein gescannter Halter seine Ecken behält. Für die
    Frage, ob ein Klick durch eine Öffnung geht, ist das genau genug — die
    Öffnung ist millimeterweit, die Abweichung liegt im Bereich der Punktdichte.

    ``None`` heißt „keine räumliche Hülle": ein ebener oder entarteter Körper —
    oder einer ohne Eckpunkte, denn das ``Mesh``-Protokoll (§9) sagt nichts über
    ein ``raw`` zu; ein B-Rep-Körper hat keines. Der Aufrufer hat dann keinen
    Innenraum zu prüfen und braucht dafür keinen Sonderfall.
    """
    from scipy.spatial import ConvexHull, QhullError

    raw = getattr(mesh, "raw", None)
    if raw is None:
        return None
    points = np.asarray(raw.vertices, dtype=float)
    if len(points) < 4:
        return None
    if len(points) > HULL_SAMPLE_LIMIT:
        step = len(points) // HULL_SAMPLE_LIMIT + 1
        extremes = np.concatenate(
            [points[points[:, axis].argmin()][None] for axis in range(3)]
            + [points[points[:, axis].argmax()][None] for axis in range(3)]
        )
        points = np.concatenate([points[::step], extremes])
    try:
        return np.asarray(ConvexHull(points).equations, dtype=float)
    except QhullError as problem:
        # Flach, entartet oder alle Punkte auf einer Linie — kein Innenraum.
        _log.info("convex hull unavailable: %s", problem)
        return None


def ray_span_in_hull(
    planes: np.ndarray, origin: np.ndarray, direction: np.ndarray
) -> tuple[float, float] | None:
    """Von wo bis wo ein Strahl innerhalb dieser Halbräume läuft.

    Der Schnitt eines Strahls mit einem konvexen Körper, gerechnet wie das
    Kappen an Schichten: Jede Ebene schiebt entweder den Eintritt nach hinten
    oder den Austritt nach vorn, und bleibt am Ende ein Stück übrig, geht der
    Strahl hindurch. Zurück kommen die beiden Strahlparameter in Millimetern,
    gemessen von ``origin`` entlang ``direction`` (das normiert erwartet wird),
    oder nichts.

    Der Eintritt kann ``-inf`` sein — dann liegt der Ursprung selbst innen. Wer
    nur nach vorn sehen will, klemmt auf null; hier bleibt es stehen, weil die
    Aussage „von hier bis dort" nichts über die Blickrichtung des Aufrufers
    voraussetzen soll.
    """
    if planes is None or not len(planes):
        return None
    normals = np.asarray(planes, dtype=float)[:, :3]
    offsets = np.asarray(planes, dtype=float)[:, 3]
    along = normals @ np.asarray(direction, dtype=float)
    gap = normals @ np.asarray(origin, dtype=float) + offsets

    # Parallel zu einer Ebene und außerhalb von ihr: der Strahl kommt nie hinein.
    parallel = np.abs(along) <= EPS_GEOM
    if bool(np.any(parallel & (gap > EPS_GEOM))):
        return None

    crossing = ~parallel
    if not bool(np.any(crossing)):
        return None
    steps = -gap[crossing] / along[crossing]
    leaving = along[crossing] > 0.0
    enter = float(steps[~leaving].max()) if bool(np.any(~leaving)) else -math.inf
    leave = float(steps[leaving].min()) if bool(np.any(leaving)) else math.inf
    return (enter, leave) if enter < leave else None


def read_mesh(payload: bytes, suffix: str) -> MeshData:
    """Parst eine Datei, die schon im Speicher liegt. Noch keine
    Aufbereitung — die ist §17.1."""
    normalised = suffix.lower()
    if normalised not in READABLE_SUFFIXES:
        raise ValidationError(
            field="file",
            detail=_("Dieses Dateiformat kann nicht gelesen werden."),
            constraint="unsupported_format",
            values={"suffix": suffix, "known": list(READABLE_SUFFIXES)},
        )
    if normalised == ".gltf":
        _check_embedded_gltf(payload)
    if normalised == ".3mf":
        # Nicht über trimesh: es löst eine Komponente, die in eine externe
        # Objektdatei zeigt, zur ganzen Datei auf statt zu dem Objekt, das sie
        # benennt, und gibt jeden Körper einmal je Komponente zurück. Hier
        # statt oben importiert, weil das 3MF-Modul MeshData braucht.
        from app.core.export import threemf

        parts = threemf.read_objects(payload)
        if parts:
            return _joined(parts)

    try:
        # ``load_mesh`` statt ``load(force="mesh")``: trimesh 5 führt ``load``
        # nur noch als Rückwärtskompatibilität und nennt es im Docstring
        # veraltet. Der Nachfolger sagt schon im Rückgabetyp, dass ein
        # ``Trimesh`` herauskommt — mehrere Körper in einer Datei verschweißt
        # er wie zuvor ``force="mesh"``, gemessen an einer GLB mit zwei
        # Quadern: beide Wege 24 Dreiecke.
        loaded = trimesh.load_mesh(
            io.BytesIO(payload), file_type=normalised.lstrip("."), process=False
        )
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # trimesh wirft eine breite Palette an Parserfehlern
        raise ValidationError(
            field="file",
            detail=_("Die Datei ließ sich nicht lesen; sie ist vermutlich beschädigt."),
            constraint="unreadable",
            values={"suffix": suffix},
        ) from problem

    # Eine Datei, an der der Parser scheitert, ohne zu werfen, kommt als leerer
    # Körper heraus — das ist der Fall, den die Zeile abfängt.
    if not len(loaded.faces):
        raise ValidationError(
            field="file",
            detail=_("Die Datei enthält keine Dreiecksgeometrie."),
            constraint="no_geometry",
            values={"suffix": suffix},
        )
    return MeshData.of(loaded)


def _check_embedded_gltf(payload: bytes) -> None:
    """Lehnt eine allein nicht lesbare GLTF mit einem Ausweg ab.

    Der Speicherleser hat keinen Ordner, aus dem er ``.bin``- oder Bilddateien
    holen könnte. Lokale Dateien macht :func:`read_local_payload` vorher
    eigenständig; ein Download muss bereits eigenständig sein oder als GLB
    vorliegen. Ohne diese Prüfung endet trimesh an einer gewöhnlichen GLTF mit
    einem rohen ``TypeError`` statt einer Meldung für den Nutzer.
    """
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as problem:
        raise ValidationError(
            field="file",
            detail=_("Die GLTF-Datei enthält kein lesbares JSON."),
            constraint="unreadable",
        ) from problem
    if not isinstance(document, dict):
        raise ValidationError(
            field="file",
            detail=_("Die GLTF-Datei enthält kein gültiges Modelldokument."),
            constraint="unreadable",
        )
    for section in ("buffers", "images"):
        entries = document.get(section, [])
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            raise ValidationError(
                field="file",
                detail=_("Die GLTF-Datei enthält kein gültiges Modelldokument."),
                constraint="unreadable",
                values={"section": section},
            )
        external = [
            entry["uri"]
            for entry in entries
            if isinstance(entry.get("uri"), str)
            and entry["uri"]
            and not entry["uri"].lower().startswith("data:")
        ]
        if external:
            raise ValidationError(
                field="file",
                detail=_(
                    "Diese GLTF braucht Begleitdateien. Öffne sie lokal zusammen mit "
                    "diesen Dateien oder exportiere das Modell als GLB."
                ),
                constraint="missing_file",
                values={"dependencies": external},
            )


def concatenated(parts: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Verschweißt mehrere Netze zu einem.

    trimesh annotiert ``concatenate`` mit dem gemeinsamen Obertyp ``Geometry``,
    weil auch Punktwolken hineinpassen; aus lauter ``Trimesh`` entsteht aber
    immer ein ``Trimesh``. Die eine Engführung lebt hier, nicht an jeder
    Aufrufstelle.
    """
    merged = trimesh.util.concatenate(parts)
    assert isinstance(merged, trimesh.Trimesh)
    return merged


def _joined(parts: list[Part]) -> MeshData:
    """Die Körper einer 3MF als der eine Körper, den diese Funktion verspricht.

    Wer sie getrennt will, fragt :func:`app.core.export.threemf.read_objects`;
    hier werden sie verschweißt, denn das ist, was ein einzelner Rückgabewert
    sein kann. Die Slots reisen nur aus einer Datei mit einem Körper mit:
    jedes Teil nummeriert seine Slots ab null, und diese Nummerierungen ohne
    gemeinsame Palette zu mischen setzte das falsche Filament auf die Hälfte
    der Dreiecke (§20).
    """
    if len(parts) == 1:
        return parts[0].mesh
    return MeshData.of(concatenated([part.mesh.raw for part in parts]))


class MeshCodec:
    """Codec für den Platten-Cache (§38). Registriert, sobald der Kern da ist."""

    suffix = ".npz"

    def stores(self, mesh: Mesh) -> bool:
        """Nur Netze. Ein exakter Körper (§30) wird neu gerechnet statt gelegt.

        Die Frage gibt es, damit der Aufrufer den Normalfall nicht am
        geworfenen ``TypeError`` erkennen muss — der bedeutet dort auch einen
        Programmfehler, und beide sahen gleich aus.
        """
        return isinstance(mesh, MeshData)

    def dumps(self, mesh: Mesh) -> bytes:
        # Bleibt: Wer ohne zu fragen ablegt, hat einen Programmfehler, und der
        # soll auffallen. ``stores`` ist die Frage, das hier die Zusicherung.
        if not isinstance(mesh, MeshData):
            raise TypeError("the disk cache can only store MeshData")
        return mesh.to_bytes()

    def loads(self, data: bytes) -> Mesh:
        return MeshData.from_bytes(data)
