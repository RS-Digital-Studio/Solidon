"""Die Suche nach einer Druckorientierung (Bauplan §22.3, §28.2).

Dafür gibt es den Analyse-Schneider eigentlich. Extern zu schneiden hieß, drei
bis fünf Kandidaten beurteilen zu können; intern zu schneiden heißt hunderte —
und das Urteil ist echtes Stützvolumen statt einer Faustregel über
Flächennormalen.

Die Abtastung ist über einen gespeicherten Startwert randomisiert (§11.3): eine
rein regelmäßige Abtastung bevorzugte systematisch symmetrische Körper, und
ohne den Startwert suchte dieselbe Datei nicht zweimal gleich.

Die Suche ist unterbrechbar. Zweihundert Kandidaten brauchen Sekunden, keine
Millisekunden, und §2.8 sagt, dass nichts das Fenster blockieren darf.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.core.geom.mesh import MeshData
from app.core.geom.mesh_ops import decimate
from app.core.geom.orient import candidates as face_candidates
from app.core.geom.orient import evaluate_direction, ranked_orientations, rotation_to_down
from app.core.geom.transform import apply, place_on_bed
from app.core.log import get_logger
from app.core.slice.analysis import slice_body
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
#: die Schichtanalyse beurteilt nur noch, was vorn liegt.
FINALISTS = 8


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


def stands(candidate: Candidate, floor: float) -> bool:
    """Kann diese Lage überhaupt stehen? (§22.2)

    ``floor`` ist die kleinste Aufstandsfläche, die der Drucker halten kann —
    :attr:`app.core.types.Profile.smallest_first_layer`. Null heißt: nicht
    gefragt, dann steht jede Lage.
    """
    return candidate.first_layer_area >= floor


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
    baseline: Candidate
    """Wie der Körper vorher stand — damit der Gewinn belegt und nicht behauptet wird."""
    findings: list[Finding]

    @property
    def improvement(self) -> float:
        """Wie viel Stützvolumen gegenüber der Ausgangslage gespart wird, in mm³."""
        return max(0.0, self.baseline.support_volume - self.best.support_volume)


def sample_directions(count: int, seed: int | None = None) -> list[Vec3]:
    """Gleichmäßig über die Kugel verteilte Richtungen, gedreht um einen
    gesetzten Versatz.
    """
    generator = np.random.default_rng(seed or 0)
    offset = float(generator.random())
    golden = math.pi * (3.0 - math.sqrt(5.0))

    found: list[Vec3] = []
    for index in range(max(1, count)):
        z = 1.0 - 2.0 * (index + offset) / max(count, 1)
        z = float(np.clip(z, -1.0, 1.0))
        radius = math.sqrt(max(0.0, 1.0 - z * z))
        angle = golden * index
        found.append((radius * math.cos(angle), radius * math.sin(angle), z))
    return found


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
) -> Candidate:
    """Dreht den Körper, bis ``direction`` nach unten zeigt, dann schneiden und
    zählen.

    ``footing_height`` ist die Höhe, in der die Aufstandsfläche gemessen wird
    — die halbe Schichthöhe des **Druckers**, nicht die der Suche. Ohne sie
    hängt :func:`stands` an der Suchauflösung: Eine Kugel mit R = 20 steht bei
    1,0 mm auf 54 mm² und bei 0,2 mm auf 4,6 mm², und die Antwort auf „kann
    das stehen" fällt einmal so und einmal anders aus.
    """
    turned = place_on_bed(apply(mesh, rotation_to_down(direction)))
    # §28.2: die Suche liest eine Zahl daraus. Strukturbreiten an einem
    # Körper zu messen, der gleich wieder gedreht wird, ist Arbeit, die
    # niemand ansieht.
    result = slice_body(turned, layer_height, detail="support", footing_height=footing_height)
    return Candidate(
        direction=direction,
        support_volume=result.support_volume,
        first_layer_area=result.first_layer_area,
        height=turned.bounds.size[2],
    )


def search_proxy(mesh: MeshData) -> MeshData:
    """Das Netz, an dem die Suche urteilt: höchstens ``SEARCH_TRIANGLES`` Dreiecke.

    Große ebene Flächen bleiben bei der Dezimierung ebene Flächen, und mehr
    braucht die Standfläche nicht; der Stützraum unter Überhängen ist ein
    Volumen, das auf ein Prozent genau reicht, um Lagen zu ordnen.
    """
    if mesh.triangle_count <= SEARCH_TRIANGLES:
        return mesh
    return decimate(mesh, SEARCH_TRIANGLES)


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
    coarse = ranked_orientations(mesh, limit=count, cancelled=cancelled)[: max(1, count)]
    footing = profile.printer.layer_height / 2.0
    field: list[Candidate] = []
    for orientation in coarse:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        field.append(judge(mesh, orientation.direction, layer_height, footing))
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
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> SearchResult:
    """Probiert viele Orientierungen und behält die, die am wenigsten Stützen
    braucht — unter denen, die stehen können.

    Ohne ``profile`` wird nach dem Stand nicht gefragt: ein Aufrufer, der
    keinen Drucker kennt, soll keinen erfinden (Regel 7).
    """
    floor = profile.smallest_first_layer if profile is not None else 0.0
    footing = profile.printer.layer_height / 2.0 if profile is not None else None
    baseline_direction: Vec3 = (0.0, 0.0, -1.0)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    # Beurteilt wird ein verkleinertes Netz; gedreht wird am Ende das echte.
    proxy = search_proxy(mesh)
    baseline = judge(proxy, baseline_direction, layer_height, footing)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    field = [baseline]
    # Die Flächennormalen kommen mit: die beste Orientierung hat meist eine
    # ebene Fläche auf der Platte, und eine gleichmäßige Abtastung der Kugel
    # trifft eine exakte Achse nur zufällig.
    directions = _unique_directions(
        [baseline_direction, *face_candidates(proxy), *sample_directions(count, seed)]
    )[1:]
    considered = 1 + len(directions)
    # Stufe eins: Standfläche gegen Überhang aus den Flächennormalen, für jede
    # Richtung, ohne eine einzige Schicht zu schneiden.
    scored = [evaluate_direction(proxy, baseline_direction)]
    for index, direction in enumerate(directions, start=1):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if progress is not None:
            progress(0.5 * index / max(len(directions), 1), str(_("Ausrichtung suchen")))
        scored.append(evaluate_direction(proxy, direction))
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
    # **Steht die Ausgangslage schon ohne Stützen und auf der größten
    # Standfläche, gibt es nichts zu suchen.** Ein offener Kasten meldete in
    # jeder der 200 Lagen null Stützraum, und die Suche verglich trotzdem eine
    # halbe Stunde lang Nullen miteinander. Die Standfläche gehört in die
    # Bedingung: Eine dünne Platte steht auch hochkant stützfrei, und die
    # Suche soll sie hinlegen.
    if not settled(baseline, floor, scored[0].footprint, ranked[0].footprint):
        # Stufe zwei: nur die Finalisten bekommen die Schichtanalyse.
        finalists = [entry for entry in ranked if entry.direction != baseline_direction][:FINALISTS]
        for index, entry in enumerate(finalists, start=1):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            if progress is not None:
                fraction = 0.5 + 0.5 * index / max(len(finalists), 1)
                progress(fraction, str(_("Ausrichtung suchen")))
            field.append(judge(proxy, entry.direction, layer_height, footing))

    # Erst wenn alle vermessen sind, wird entschieden: Die
    # Fünf-Prozent-Toleranz macht den paarweisen Vergleich nicht transitiv,
    # und dann hängt der Sieger an der Reihenfolge (:func:`best_of`).
    tried = len(field)
    best = best_of(field, floor)

    turned = place_on_bed(apply(mesh, rotation_to_down(best.direction)))
    findings = [
        Finding(
            code="orient.searched",
            severity="info",
            message=_("Ausrichtung über die Schichtanalyse gesucht."),
            values={
                "candidates": considered,
                "sliced": tried,
                "support": round(best.support_volume / 1000.0, 2),
                "saved": round((baseline.support_volume - best.support_volume) / 1000.0, 2),
            },
            source="internal",
        )
    ]
    if floor > 0.0 and not stands(best, floor):
        # Keine geprüfte Lage trägt. Eine Kugel ist der ehrliche Fall dafür,
        # und das Teil braucht dann eine Haftschicht — das zu sagen ist besser,
        # als stillschweigend eine Ecke zu wählen (§2.7).
        findings.append(
            Finding(
                code="orient.no_footing",
                severity="warning",
                message=_(
                    "Keine geprüfte Lage steht auf genug Fläche — dieses Teil braucht einen Brim."
                ),
                values={
                    "first_layer_mm2": round(best.first_layer_area, 3),
                    "needed_mm2": round(floor, 3),
                },
                source="internal",
            )
        )
    _log.info(
        "orientation search: %d candidates, support %.1f mm3 (was %.1f)",
        tried,
        best.support_volume,
        baseline.support_volume,
    )
    return SearchResult(mesh=turned, best=best, tried=tried, baseline=baseline, findings=findings)
