"""Deterministische Geometriekandidaten, begrenzte echte Schichtanalysen (§28.2)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from shapely.geometry import Point
from shapely.geometry import Polygon as ShapelyPolygon

from app.core.deferred import trimesh
from app.core.errors import (
    OPEN_PRINT_SETTINGS,
    SHOW_SUPPORT_NEED,
)
from app.core.geom.mesh import MeshData
from app.core.geom.mesh_ops import decimate_for_display
from app.core.geom.orient import (
    AXES,
    MAX_FACE_CANDIDATES,
    NoFittingOrientationError,
    Orientation,
    evaluate_directions,
    extreme_points,
    fitting_transform,
    print_transform,
    ranked_orientations,
    rotation_to_down,
    turned_extents,
)
from app.core.geom.orient import candidates as face_candidates
from app.core.geom.transform import apply, moved_points, place_on_bed, translation
from app.core.log import get_logger
from app.core.slice.analysis import cross_sections, slice_body
from app.core.types import CancelToken, Finding, Profile, ProgressFn, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Schichthöhe für die Suche. Gröber als beim Druck: die Rangfolge bewegt
#: sich darunter kaum, und genau das hält hunderte Kandidaten
#: bezahlbar (§31).
SEARCH_LAYER_HEIGHT = 1.0

#: Vorgabeanzahl der versuchten Richtungen.
DEFAULT_CANDIDATES = 200

#: Mehr Dreiecke sieht die Suche nicht. Standfläche und Stützraum ändern sich
#: durch eine Dezimierung kaum, die Schichtanalyse kostet aber linear: Der
#: Filamenthalter kam mit 260 988 Dreiecken aus dem Aushöhlen, und jeder
#: Kandidat brauchte rund fünf Sekunden — 200 Kandidaten wären eine halbe
#: Stunde beim Öffnen gewesen (06.09.2026).
SEARCH_TRIANGLES = 20_000

#: So viele Lagen aus der Vorauswahl werden wirklich geschnitten. Die
#: Heuristik (Standfläche gegen Überhang, ``geom.orient``) sortiert vor —
#: „meistens entscheidet die unterste Schicht" (Robert, 06.09.2026) —, und
#: die Schichtanalyse beurteilt nur noch, was vorn liegt. Dazu kommen die
#: sechs Achsen (:data:`app.core.geom.orient.AXES`), gleich wo sie in der
#: Vorauswahl stehen; geschnitten wird also höchstens
#: ``FINALISTS + len(AXES)`` plus die Ausgangslage.
FINALISTS = 8

#: So viele Lagen mit dem kleinsten **geschätzten** Stützraum werden
#: zusätzlich geschnitten (:attr:`app.core.geom.orient.Orientation.support`).
#: Die Heuristik ordnet nach Fläche; wie hoch ein Überhang hängt, weiß sie
#: nicht — an Roberts Getränkehalter stand die beste Lage von Schirm, Mast
#: und Halter dort auf Rang 182, 51 und 25, nach der Schätzung auf 10, 2
#: und 5 (RM-190, 23.09.2026). Spiegelgleiche Lagen mit derselben Schätzung
#: zählen einmal: Sie ergäben denselben Schnitt.
SUPPORT_FINALISTS = 8


#: Stützvolumen innerhalb dieses Anteils voneinander zählen als gleich gut,
#: und dann entscheidet die Grundfläche. Ohne die Toleranz suchte das
#: Vernetzungsrauschen die Orientierung aus.
SUPPORT_TIE = 0.05


@dataclass(frozen=True, slots=True)
class Candidate:
    """Eine Richtung, beurteilt danach, was sie zu drucken kostete."""

    direction: Vec3
    support_volume: float
    """Der gestützte **Raum** in mm³, nicht das Stützmaterial darin.

    Gemeint ist das Volumen unter den Überhängen bis zum nächsten Material
    oder zur Platte (:func:`app.core.slice.analysis._support_volume`). Eine
    gedruckte Stütze füllt diesen Raum nur zu ihrer Dichte —
    :func:`app.core.slice.estimate.support_material` rechnet sie hinein, und
    erst dort steht, was der Drucker wirklich verbraucht.

    Die Zahl ist absolut belastbar und nicht nur relativ: An einem Pilz (Hut
    40 auf 40 über einem Stiel 10 auf 10, 20 mm hoch) beträgt der Sollwert von Hand
    30 000 mm³, gemessen wurden 29 986,7 — die Differenz ist die halbe
    Schichthöhe an der Unterkante, die unten benannt ist. Ein Quader meldet
    null, weil er keine Überhänge hat, und derselbe Umriss massiv gefüllt
    ebenfalls: Das ist die Definition und nicht ihre Verletzung."""
    first_layer_area: float
    height: float
    stable: bool = True
    """Die Schwerpunktprojektion liegt in der Hülle der tatsächlichen Auflage."""
    footing: float | None = None
    """Der Teil der Aufstandsfläche, der eine Linie tragen kann, in mm² — die
    Auflage um eine halbe Linienbreite nach innen versetzt. ``None`` heißt:
    ohne Linienbreite beurteilt, dann zählt :attr:`first_layer_area`.

    **Eine Kante ist keine Auflage, auch eine lange nicht** (RM-190,
    23.09.2026). Roberts Getränkehalter stand um 48 Grad gekippt auf drei
    Kanten, zusammen 36,5 mm² und damit über der kleinsten Aufstandsfläche —
    aber jede schmaler als eine Linie, versetzt blieb nichts. Ein Slicer
    druckt dort keine erste Schicht, und die Lage steht nicht."""


def stands(candidate: Candidate, floor: float) -> bool:
    """Kann diese Lage überhaupt stehen? (§22.2, §28.2)

    ``floor`` ist die kleinste Aufstandsfläche, die der Drucker halten kann —
    :attr:`app.core.types.Profile.smallest_first_layer`. Null heißt: nicht
    gefragt, dann steht jede Lage. Gemessen wird sie an dem, was eine Linie
    tragen kann (:attr:`Candidate.footing`), wo das beurteilt ist.
    """
    return candidate.stable and _footing_of(candidate) >= floor


def _footing_of(candidate: Candidate) -> float:
    """Die Aufstandsfläche, an der das Stehen gemessen wird."""
    return candidate.first_layer_area if candidate.footing is None else candidate.footing


def best_of(candidates: Sequence[Candidate], floor: float = 0.0) -> Candidate:
    """Die beste Lage aus einem ganzen Feld (§22.2).

    Weniger Stützen gewinnt; erst bei Gleichstand entscheidet die Grundfläche.
    Mit Absicht lexikografisch statt als gewichtete Summe: eine große
    Aufstandsfläche darf sich nie an echtem Stützmaterial vorbeikaufen.

    **Und umgekehrt genauso.** Der Satz darüber nennt eine Richtung, und die
    andere fehlte: Ein paar Kubikmillimeter Stützmaterial dürfen keine Lage
    kaufen, die nicht stehen kann. Gemessen an einer Verbinderstange von
    157 mm — die Suche wählte eine diagonale Lage mit 0,6 mm³ Stütze und
    **0,1 mm²** erster Schicht gegen die liegende mit 11,1 mm³ und 1424 mm².
    Der Vergleich war richtig, die Zahl auch; nur ist 0,1 mm² kein Stand,
    sondern eine Ecke. Wer stehen kann, gewinnt gegen jeden, der es nicht kann
    — und **erst danach** wird gerechnet. Steht keine Lage (eine Kugel steht
    auf keiner), fällt das Kriterium für alle gleich aus.

    **Entschieden wird über das Feld, nicht paarweise.** Vorher lief ein
    Vergleich ``better(kandidat, bester)`` durch die Schleife, und der ist
    nicht transitiv: A schlägt B, B schlägt C, C schlägt A. Die
    Fünf-Prozent-Toleranz ist der Grund — zwischen A und B liegen vier
    Prozent, zwischen A und C neun, und je nachdem, in welcher Reihenfolge die
    Kandidaten kommen, gewinnt ein anderer. Damit hing die empfohlene Lage an
    der Abtastung statt am Körper. Gesucht wird deshalb erst das Minimum des
    Stützvolumens, dann unter allen, die innerhalb von :data:`SUPPORT_TIE`
    davon liegen, die größte Grundfläche.
    """
    field = [candidate for candidate in candidates if stands(candidate, floor)] or list(candidates)
    least = min(candidate.support_volume for candidate in field)
    reference = max(least, EPS_GEOM)
    tied = [
        candidate
        for candidate in field
        if candidate.support_volume - least <= reference * SUPPORT_TIE
    ]
    return max(tied, key=lambda candidate: candidate.first_layer_area)


@dataclass(slots=True)
class SearchResult:
    """Der Gewinner, das Feld, gegen das er gewann, und was dem Nutzer zu
    sagen ist.
    """

    mesh: MeshData
    best: Candidate
    tried: int
    baseline: Candidate | None
    """Wie der Körper vorher stand — damit der Gewinn belegt und nicht behauptet wird."""
    findings: list[Finding]
    transform: np.ndarray = field(default_factory=lambda: np.eye(4))

    @property
    def improvement(self) -> float:
        """Wie viel Stützvolumen gegenüber der Ausgangslage gespart wird, in mm³."""
        if self.baseline is None:
            return 0.0
        return max(0.0, self.baseline.support_volume - self.best.support_volume)


def _least_support(scored: Sequence[Orientation], skip: Vec3) -> list[Vec3]:
    """Die Lagen mit dem kleinsten geschätzten Stützraum, je Gleichstand eine.

    Gleich heißt hier bitgleich in Schätzung, Standfläche, Überhang und Höhe —
    alle vier sind exakt summiert, also tragen spiegelgleiche Lagen eines
    symmetrischen Teils dieselben Zahlen und ergäben denselben Schnitt. Das
    Schirmdach des Getränkehalters hat acht solche Lagen um seine Achse.
    """
    chosen: list[Vec3] = []
    seen: set[tuple[float, float, float, float]] = set()
    for entry in sorted(scored, key=lambda item: (item.support, item.direction)):
        if entry.direction == skip:
            continue
        key = (entry.support, entry.footprint, entry.overhang, entry.height)
        if key in seen:
            continue
        seen.add(key)
        chosen.append(entry.direction)
        if len(chosen) == SUPPORT_FINALISTS:
            break
    return chosen


def _unique_directions(directions: list[Vec3]) -> list[Vec3]:
    """Entfernt Lagen, die dieselbe Schichtanalyse erneut auslösen würden.

    Die sechs Achsen stehen fest in den Flächenkandidaten und kommen bei
    achsparallelen Körpern noch einmal als große Flächennormalen vor. Auch die
    Ausgangslage ``-Z`` gehört dazu. Dieselbe Lage zweimal zu schneiden ändert
    die Rangfolge nicht; bei zweihundert Kandidaten kostet es aber messbar Zeit.
    """
    found: list[Vec3] = []
    for direction in directions:
        if any(math.dist(direction, previous) <= EPS_GEOM for previous in found):
            continue
        found.append(direction)
    return found


def judge(
    mesh: MeshData,
    direction: Vec3,
    layer_height: float,
    footing_height: float | None = None,
    *,
    overhang_angle: float | None = None,
    footing_mesh: MeshData | None = None,
    line_width: float | None = None,
) -> Candidate:
    """Dreht den Körper, bis ``direction`` nach unten zeigt, dann schneiden und
    zählen.

    ``line_width`` ist die Linienbreite des Druckers; mit ihr wird gemessen,
    wie viel der Auflage eine Linie tragen kann (:attr:`Candidate.footing`).

    ``footing_height`` ist die Höhe, in der die Aufstandsfläche gemessen wird
    — die halbe Schichthöhe des **Druckers**, nicht die der Suche. Ohne sie
    hängt :func:`stands` an der Suchauflösung: Eine Kugel mit R = 20 steht bei
    1,0 mm auf 54 mm² und bei 0,2 mm auf 4,6 mm², und die Antwort auf „kann
    das stehen" fällt einmal so und einmal anders aus.

    **Und die Aufstandsfläche wird am Original gemessen, nicht am
    Ersatznetz.** ``mesh`` ist in der Suche das auf 20 000 Dreiecke
    ausgedünnte Netz (:func:`search_proxy`); das reicht, um Stützräume zu
    ordnen, aber ein schmaler flacher Rand überlebt die Ausdünnung nicht als
    Ebene. Gemessen am Gitterbecher vom 20.09.2026 (94 990 Dreiecke, Rand
    2 mm breit): am Ersatznetz stand er mit dem Rand nach unten auf 5 mm²,
    am Original auf 594. Die Suche verwarf damit genau die Lage, die ohne
    Stützen druckt, und stellte ihn auf die Schräge. Wer ein ``footing_mesh``
    mitgibt, bekommt Aufstandsfläche und Stand von dort.

    **Ohne das Original zu kopieren.** Eine Drehung und ein Schnitt je Lage
    hieß zuerst: das ganze Netz drehen, aufs Bett setzen, den Schwerpunkt
    des gedrehten Netzes rechnen — 754 ms je Lage an 1,3 Millionen Dreiecken,
    davon 587 ms für einen Schwerpunkt, der sich mitdreht wie jeder andere
    Punkt (21.09.2026). Jetzt kennt das Original seinen Schwerpunkt einmal,
    die Drehung trifft nur ihn und die äußersten Ecken, und geschnitten werden
    allein die Dreiecke, die die Aufstandsebene kreuzen (:func:`_contact`).
    """
    turn = rotation_to_down(direction)
    turned = place_on_bed(apply(mesh, turn))
    # §28.2: die Suche liest eine Zahl daraus. Strukturbreiten an einem
    # Körper zu messen, der gleich wieder gedreht wird, ist Arbeit, die
    # niemand ansieht.
    result = slice_body(
        turned,
        layer_height,
        detail="support",
        footing_height=footing_height,
        overhang_angle=overhang_angle,
    )
    standing = mesh if footing_mesh is None else footing_mesh
    # Die Fläche allein trägt nicht: Bei einem Ausleger kann sein Schwerpunkt
    # neben einer großen Auflage liegen. Getrennte Füße tragen gemeinsam über
    # ihre konvexe Hülle; das Loch zwischen ihnen ist kein Grund zum Ablehnen.
    contact, centre = _contact(standing, turn, footing_height or layer_height / 2.0)
    stable = (
        contact is not None
        and bool(np.isfinite(centre).all())
        and bool(contact.convex_hull.buffer(EPS_GEOM).covers(Point(centre)))
    )
    first_layer_area = result.first_layer_area
    if footing_mesh is not None:
        first_layer_area = 0.0 if contact is None or contact.is_empty else float(contact.area)
    footing = None
    if line_width is not None:
        # Gehrung statt Rundung: Ein Rückversatz braucht dann keinen Kreisbogen
        # und damit keine Winkelfunktion der Plattform (RM-187).
        footing = (
            0.0
            if contact is None or contact.is_empty
            else float(contact.buffer(-line_width / 2.0, join_style="mitre").area)
        )
    return Candidate(
        direction=direction,
        support_volume=result.support_volume,
        first_layer_area=first_layer_area,
        height=turned.bounds.size[2],
        stable=stable,
        footing=footing,
    )


def _contact(
    mesh: MeshData, turn: np.ndarray, footing_height: float
) -> tuple[ShapelyPolygon | None, np.ndarray]:
    """Die Aufstandsfläche des gedrehten Körpers und sein Schwerpunkt in XY —
    ohne das Netz zu drehen.

    Auf dem Bett steht der Körper, sobald seine tiefste gedrehte Ecke auf null
    liegt; die kommt aus den äußersten Ecken (``orient.extreme_points``). Die
    Aufstandsebene liegt ``footing_height`` darüber, höchstens auf halber
    Höhe. Welche Dreiecke sie kreuzen, sagt die gedrehte Höhe ihrer Ecken;
    nur diese werden bewegt und geschnitten — mit derselben Matrix und
    denselben Rechenschritten wie das ganze Netz, also mit demselben Schnitt.

    Der Schwerpunkt ist der des Originals, einmal gerechnet und von
    ``trimesh`` am Netz gehalten, und wird wie eine Ecke mitgedreht.
    """
    body = mesh.raw
    low, high = turned_extents(extreme_points(mesh), turn)
    matrix = translation((0.0, 0.0, -low[2])) @ turn
    height = min(footing_height, (high[2] - low[2]) / 2.0)
    vertices = np.asarray(body.vertices, dtype=float)
    faces = np.asarray(body.faces, dtype=np.int64)
    # Die Auswahl darf grob sein — BLAS statt elementweise —, solange sie
    # jedes Dreieck behält, das der Ebenenschnitt mit seiner eigenen Toleranz
    # noch ansieht; die Bewegung danach ist die exakte.
    lifted = vertices @ np.asarray(matrix[2, :3], dtype=float) + float(matrix[2, 3])
    corners = lifted[faces]
    crossing = (corners.min(axis=1) <= height + 2.0 * EPS_GEOM) & (
        corners.max(axis=1) >= height - 2.0 * EPS_GEOM
    )
    centre = moved_points(np.asarray(body.center_mass, dtype=float)[None, :], matrix)[0, :2]
    if not crossing.any():
        return None, centre
    used, local = np.unique(faces[crossing], return_inverse=True)
    band = trimesh.Trimesh(
        vertices=moved_points(vertices[used], matrix),
        faces=local.reshape(-1, 3),
        process=False,
    )
    return cross_sections(MeshData.of(band), np.asarray([height], dtype=float))[0], centre


def search_proxy(mesh: MeshData) -> MeshData:
    """Das Netz, an dem die Suche urteilt: höchstens ``SEARCH_TRIANGLES`` Dreiecke.

    Große ebene Flächen bleiben bei der Dezimierung ebene Flächen, und mehr
    braucht die Standfläche nicht; der Stützraum unter Überhängen ist ein
    Volumen, das auf ein Prozent genau reicht, um Lagen zu ordnen.
    """
    if mesh.triangle_count <= SEARCH_TRIANGLES:
        return mesh
    return decimate_for_display(mesh, SEARCH_TRIANGLES)


def settled(baseline: Candidate, floor: float, footprint: float, best_footprint: float) -> bool:
    """Ob die Ausgangslage schon stützfrei auf der größten Standfläche steht.

    Dann ist nichts zu suchen. ``footprint`` ist die Standfläche der
    Ausgangslage aus der Vorauswahl, ``best_footprint`` die größte, die eine
    Richtung dort erreicht; innerhalb von ``SUPPORT_TIE`` gilt beides als
    gleich — dieselbe Toleranz, mit der :func:`best_of` Gleichstände entscheidet.
    """
    if baseline.support_volume > EPS_GEOM:
        return False
    if floor > 0.0 and not stands(baseline, floor):
        return False
    return footprint >= best_footprint * (1.0 - SUPPORT_TIE)


def best_face_candidate(
    mesh: MeshData,
    *,
    count: int,
    profile: Profile,
    layer_height: float = SEARCH_LAYER_HEIGHT,
    cancelled: CancelToken | None = None,
) -> Candidate:
    """Die beste der grob vorausgewählten Grundflächen, echt geschnitten.

    ``geom.orient`` ordnet Flächen schnell nach Auflage, Überhangfläche und
    Höhe. Das ist nur die Vorauswahl. Zwischen ihren besten Richtungen gilt
    anschließend dieselbe Entscheidung wie in der großen Orientierungssuche:
    Eine Lage muss stehen können, dann gewinnt das echte interne
    Stützvolumen, bei höchstens fünf Prozent Abstand die Grundfläche.
    """
    coarse = ranked_orientations(mesh, limit=count, cancelled=cancelled, printer=profile.printer)[
        : max(1, count)
    ]
    if not coarse:
        raise NoFittingOrientationError()
    footing = profile.printer.layer_height / 2.0
    field: list[Candidate] = []
    for orientation in coarse:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        field.append(
            judge(
                mesh,
                orientation.direction,
                layer_height,
                footing,
                overhang_angle=profile.overhang_limit_degrees,
                line_width=profile.printer.extrusion_width,
            )
        )
        if cancelled is not None:
            cancelled.raise_if_cancelled()
    return best_of(field, profile.smallest_first_layer)


def search(
    mesh: MeshData,
    *,
    count: int = DEFAULT_CANDIDATES,
    seed: int | None = None,
    layer_height: float = SEARCH_LAYER_HEIGHT,
    profile: Profile | None = None,
    overhang_angle: float | None = None,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
    margin: float = 0.0,
) -> SearchResult:
    """Wählt unter zulässigen Geometrielagen nach echtem Stützvolumen.

    ``count`` begrenzt die Hüllnormalen, ergänzt durch Achsen und große
    Körperflächen. ``seed`` bleibt für gespeicherte Aufrufer kompatibel; die
    Geometrieauswahl ist ohne Zufallsrichtungen vollständig deterministisch.
    Unmögliche Lagen werden vor jeder Schichtanalyse ausgeschieden. Ein
    fehlender Ausgangswert heißt ``baseline=None``, nicht null Stützbedarf.
    """
    floor = profile.smallest_first_layer if profile is not None else 0.0
    footing = profile.printer.layer_height / 2.0 if profile is not None else None
    # Mit Profil wird gemessen, was eine Linie tragen kann (``Candidate.footing``);
    # als Schlüsselwort nur dann, wie ``footing_mesh`` darunter.
    line_width: dict[str, float] = (
        {"line_width": profile.printer.extrusion_width} if profile is not None else {}
    )
    if overhang_angle is None and profile is not None:
        overhang_angle = profile.overhang_limit_degrees
    baseline_direction: Vec3 = (0.0, 0.0, -1.0)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    proxy = search_proxy(mesh)
    # Stützräume am Ersatznetz, der Stand am Original (siehe :func:`judge`).
    # Als Schlüsselwort nur, wenn es ein Original gibt: Wer ``judge`` in einem
    # Test durch eine Attrappe ersetzt, muss den Fall ohne Ersatznetz nicht
    # kennen.
    footing_on: dict[str, Any] = {} if proxy is mesh else {"footing_mesh": mesh}
    footing_on.update(line_width)

    def matrix_for(direction: Vec3) -> np.ndarray | None:
        if profile is None:
            return print_transform(mesh, direction)
        return fitting_transform(mesh, direction, profile.printer, margin=margin)

    matrices: dict[Vec3, np.ndarray] = {}
    baseline_matrix = matrix_for(baseline_direction)
    baseline = None
    field: list[Candidate] = []
    if baseline_matrix is not None:
        matrices[baseline_direction] = baseline_matrix
        baseline = judge(
            proxy,
            baseline_direction,
            layer_height,
            footing,
            overhang_angle=overhang_angle,
            **footing_on,
        )
        field.append(baseline)
    if cancelled is not None:
        cancelled.raise_if_cancelled()

    directions = _unique_directions([baseline_direction, *face_candidates(mesh, hull_limit=count)])
    # **Die Vorauswahl sieht Achsen und tragende Flächen am Original.** Die
    # Kandidatenliste beginnt mit der Ausgangslage, den sechs Achsen und den
    # größten ebenen Flächen des Körpers — und die Ausdünnung, an der die
    # Stützräume gemessen werden, macht genau aus einer solchen Fläche eine
    # Landschaft: Der Rand des Gitterbechers (20.09.2026) hatte am Ersatznetz
    # null Standfläche und kam nie unter die Finalisten; die Suche stellte
    # ihn auf die Schräge. Die wenigen vorderen Richtungen kosten am Original
    # nichts, was zählt; die Hüllnormalen dahinter bleiben am Ersatznetz.
    trusted = 0 if proxy is mesh else min(len(directions), 1 + 6 + MAX_FACE_CANDIDATES)
    on_original: list[Vec3] = []
    on_proxy: list[Vec3] = []
    for index, direction in enumerate(directions):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if progress is not None:
            progress(0.5 * (index + 1) / len(directions), str(_("Ausrichtung suchen")))
        matrix = matrices.get(direction)
        if matrix is None:
            matrix = matrix_for(direction)
        if matrix is None:
            continue
        matrices[direction] = matrix
        (on_original if index < trusted else on_proxy).append(direction)
    # Gestapelt statt einzeln: die Projektionen aller Lagen in einem Zug je
    # Netz (``orient.evaluate_directions``), so weit die Speichergrenze reicht.
    scored: list[Orientation] = [
        *evaluate_directions(mesh, on_original, cancelled),
        *evaluate_directions(proxy, on_proxy, cancelled),
    ]
    if not scored:
        raise NoFittingOrientationError()
    ranked = sorted(
        scored,
        key=lambda entry: (
            -entry.score,
            -entry.footprint,
            entry.overhang,
            entry.height,
            entry.direction,
        ),
    )
    initial = next((entry for entry in scored if entry.direction == baseline_direction), None)
    complete = (
        baseline is not None
        and initial is not None
        and settled(baseline, floor, initial.footprint, max(entry.footprint for entry in scored))
    )
    if not complete:
        finalists = [entry for entry in ranked if entry.direction != baseline_direction][:FINALISTS]
        # **Und die Achsen immer.** Die Heuristik ordnet nach Standfläche und
        # nach unten zeigender Fläche, und an einem Gitter zeigt in jeder Lage
        # die Hälfte nach unten: Der Gitterbecher (20.09.2026) hatte liegend
        # 14 848 mm² „Überhang" und 4931 Standfläche, stehend 6587 und 594 —
        # die Heuristik setzte jede liegende Lage vor die stehende, und die
        # Schichtanalyse sah die Lage, die ohne Stützen druckt, gar nicht.
        # Eine Achse ist die Lage, die jemand beim Konstruieren gewählt hat;
        # sie bekommt einen Schnitt, keine Schätzung.
        sliced = _unique_directions(
            [
                *(entry.direction for entry in finalists),
                *_least_support(scored, baseline_direction),
                *(direction for direction in AXES if direction in matrices),
            ]
        )
        sliced = [direction for direction in sliced if direction != baseline_direction]
        for index, direction in enumerate(sliced, start=1):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            if progress is not None:
                progress(0.5 + 0.5 * index / max(len(sliced), 1), str(_("Ausrichtung suchen")))
            field.append(
                judge(
                    proxy,
                    direction,
                    layer_height,
                    footing,
                    overhang_angle=overhang_angle,
                    **footing_on,
                )
            )
            if cancelled is not None:
                cancelled.raise_if_cancelled()
    best = best_of(field, floor)
    matrix = matrices[best.direction]
    turned = apply(mesh, matrix)
    # Nie negativ, wie :attr:`SearchResult.improvement`: Kippt die
    # Ausgangslage, gewinnt eine stehende Lage auch mit mehr Stützen, und
    # „minus vier Kubikzentimeter gespart" wäre keine Auskunft, sondern ein
    # Rätsel. Gespart ist dann nichts — und das steht da.
    saved = (
        max(0.0, baseline.support_volume - best.support_volume) if baseline is not None else None
    )
    findings = [
        Finding(
            code="orient.searched",
            severity="info",
            message=_("Ausrichtung über die Schichtanalyse gesucht."),
            values={
                "candidates": len(directions),
                "valid": len(scored),
                "sliced": len(field),
                "support": round(best.support_volume / 1000.0, 2),
                **({"saved": round(saved / 1000.0, 2)} if saved is not None else {}),
            },
            source="internal",
        )
    ]
    if floor > 0.0 and _footing_of(best) < floor:
        findings.append(
            Finding(
                code="orient.no_footing",
                severity="warning",
                message=_(
                    "Keine geprüfte Lage steht auf genug Fläche — dieses Teil braucht einen Brim."
                ),
                # Dieselbe Zahl, an der entschieden wurde: die Auflage, die eine
                # Linie trägt. Sonst stünde neben „nicht genug" eine größere Zahl
                # als die geforderte.
                values={
                    "first_layer_mm2": round(_footing_of(best), 3),
                    "needed_mm2": round(floor, 3),
                },
                source="internal",
                # Regel 17: Den Brim, den der Satz nennt, setzen die Druckeinstellungen.
                suggestions=(OPEN_PRINT_SETTINGS,),
            )
        )
    if not best.stable:
        findings.append(
            Finding(
                code="orient.unstable",
                severity="warning",
                message=_(
                    "Der Schwerpunkt liegt außerhalb der Auflage. "
                    "Prüfen Sie Stützen oder eine größere Plattenhaftung."
                ),
                source="internal",
                # Regel 17: Die Stützkarte zeigt, was über der Auflage hängt.
                suggestions=(SHOW_SUPPORT_NEED,),
            )
        )
    if progress is not None:
        progress(1.0, str(_("Ausrichtung suchen")))
    _log.info("orientation search: %d valid candidates, %d sliced", len(scored), len(field))
    return SearchResult(
        mesh=turned,
        best=best,
        tried=len(field),
        baseline=baseline,
        findings=findings,
        transform=matrix,
    )
