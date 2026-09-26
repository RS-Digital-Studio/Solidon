"""Was eine Änderung hinzugefügt und was sie entfernt hat (Bauplan §18.7).

Die Differenzansicht heißt die wichtigste Ansicht der Anwendung (§19.1), und
sie verdient das, indem sie eine Frage beantwortet: was genau täte dieser
Vorschlag mit meinem Modell? Nicht „etwas hat sich geändert" — so viel Material
hier ist fort, so viel dort ist neu.

Beide Hälften sind Boolesche Operationen, kommen also beide aus der
Rückfallkette (§17.2) und können beide ehrlich scheitern. Eine Differenz, die
sich nicht rechnen ließ, sagt das, statt eine leere Ansicht zu zeigen, die wie
„nichts hat sich geändert" aussieht.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import cast

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import PROGRAMMING_ERRORS, GeometryError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data, face_components, signed_volume
from app.core.log import get_logger
from app.core.types import (
    Finding,
    ObjectId,
    Profile,
    Quality,
    Scene,
    SceneObject,
    SolverInfo,
)
from app.i18n import _

_log = get_logger(__name__)

#: Volumen darunter sind Vernetzungsrauschen, keine Änderung (§11.2 dem
#: Sinne nach) — **die Antwort für einen Aufrufer ohne Drucker**.
#:
#: **Wer ein Profil kennt, misst an der Düse** (Regel 7, RM-097).
#: ``Profile.smallest_printable_volume`` ist ein Stück Extrusionsbahn von
#: einer Bahnbreite Länge: am Centauri 0,035 mm³, an einer 0,8er Düse 0,28 —
#: das Fünfunddreißigfache dieser Zahl. Dieselbe Grenze und dieselbe
#: Begründung wie bei :func:`boolean.without_effect`: Eine Änderung, die
#: kleiner ist als das, was der Drucker überhaupt hinterlässt, hat niemand je
#: zu sehen bekommen, und eine Meldung darüber bringt niemanden weiter.
#:
#: Das Rauschen bleibt daneben stehen, weil es eine andere Frage beantwortet:
#: Es ist die Untergrenze der Rechnung und nicht die des Drucks. Wer keinen
#: Drucker kennt, soll keinen erfinden.
NOISE_VOLUME = 1e-3

#: Ab welchem Anteil der gemeinsamen Hülle die Änderungsbox den Vergleich
#: **nicht** mehr verkleinert. Ein Beschnitt kostet zwei Boolesche Schnitte
#: mit einem Quader; er lohnt, wenn das Ergebnis deutlich kleiner ist als der
#: ganze Körper — bei einer Hälfte nicht mehr. Eine Rechengrenze.
CHANGED_REGION_SHARE = 0.5

#: Wie weit die Änderungsbox über die geänderten Dreiecke hinausreicht, als
#: Anteil ihrer eigenen Diagonale. Zwei fast deckungsgleiche Häute sind der
#: schlimmste Fall eines Booleschen Kerns (``wartezeit.md``); eine Boxwand,
#: die genau auf einer Deckfläche des Körpers liegt, wäre genau das. Fünf
#: Prozent schieben sie ins Freie, ohne den Beschnitt spürbar zu vergrößern.
CHANGED_REGION_MARGIN = 0.05


@dataclass(slots=True)
class Difference:
    """Das hinzugekommene und das entfernte Volumen eines Körpers."""

    object_id: ObjectId
    added: MeshData | None = None
    removed: MeshData | None = None
    added_volume: float = 0.0
    removed_volume: float = 0.0
    solvers: tuple[SolverInfo, ...] = ()
    findings: list[Finding] = field(default_factory=list)
    #: Ab welchem Volumen diese Differenz eine Änderung ist. Kommt vom Drucker,
    #: wo einer bekannt ist; sonst bleibt es beim Vernetzungsrauschen (siehe
    #: :data:`NOISE_VOLUME`).
    noise_volume: float = NOISE_VOLUME
    retriangulated: MeshData | None = None
    """Der Körper danach, wenn seine Dreiecke sich ändern und sein Volumen
    nicht — *Dreiecke verringern*, *Angleichen*, *Unterteilen*, *Glätten*
    unterhalb dessen, was der Drucker hinterlässt (RM-169).

    Die Ansicht misst Volumen, und diese Operationen haben keines: Bis zum
    14.09.2026 blieb ihre Vorschau leer, und das Band sagte „am Volumen ändert
    sich nichts" — wahr, und für den, der die Dreiecke sehen wollte, keine
    Antwort. Die Ansicht legt den Körper danach mit seinen Kanten über den
    davor."""
    recoloured: SceneObject | None = None
    """Der Körper danach, wenn nur seine Farben sich ändern — *Filament
    zuweisen*, *auf eine Fläche*, *entfernen*, *Textur umrechnen* (RM-169).

    Die Geometrie ist dieselbe, ``compare`` fände nichts; die Ansicht zeichnet
    den Körper mit den neuen Slotfarben über den alten."""
    result: SceneObject | None = None
    """Der vollständige Nachherkörper bei einer Geometrieänderung.

    Er bleibt auch bei unvollständigem Volumenvergleich verfügbar. Die
    Differenzfarben erklären den Abtrag, dieser Körper zeigt das Ergebnis.
    """

    @property
    def changed(self) -> bool:
        return self.added_volume > self.noise_volume or self.removed_volume > self.noise_volume


@dataclass(slots=True)
class SceneDifference:
    """Die ganze Szene, Körper für Körper, plus was erschien und verschwand."""

    entries: dict[ObjectId, Difference] = field(default_factory=dict)
    created: tuple[ObjectId, ...] = ()
    deleted: tuple[ObjectId, ...] = ()
    #: Befunde der vorgeschauten Schritte; ältere Befunde gehören zum Dokument.
    findings: tuple[Finding, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.created or self.deleted) or any(
            entry.changed for entry in self.entries.values()
        )

    @property
    def added_volume(self) -> float:
        return sum(entry.added_volume for entry in self.entries.values())

    @property
    def removed_volume(self) -> float:
        return sum(entry.removed_volume for entry in self.entries.values())

    @property
    def reshaped(self) -> bool:
        """Ob ein Körper neue Dreiecke bei gleichem Volumen bekommt."""
        return any(entry.retriangulated is not None for entry in self.entries.values())

    @property
    def recoloured(self) -> bool:
        """Ob ein Körper nur andere Farben bekommt."""
        return any(entry.recoloured is not None for entry in self.entries.values())


def compare(
    before: MeshData,
    after: MeshData,
    *,
    quality: Quality = "draft",
    profile: Profile | None = None,
) -> Difference:
    """Ein Körper gegen seinen Nachfolger.

    ``profile`` entscheidet, ab wann die Differenz eine **Änderung** ist: das
    kleinste Volumen, das dieser Drucker überhaupt hinterlässt (Regel 7,
    RM-097). Ohne Profil bleibt es beim Vernetzungsrauschen — ein Aufrufer,
    der keinen Drucker kennt, soll keinen erfinden.
    """
    entry = Difference(object_id="", noise_volume=_noise(profile))
    before, after = _clipped_to_the_change(before, after, quality)
    first, second, common = _comparison_parts(before, after)
    balance = _volume_balance(first, second, common)
    noise = entry.noise_volume
    # Zuerst die Seite, auf der die Bilanz Material erwartet; die andere steht
    # danach oft ohne Schnitt fest (:func:`_empty_by_balance`).
    if balance is not None and balance > 0.0:
        added = _cut_parts(second, first, common, quality)
        removed = _empty_by_balance(added, balance, noise, added=False)
        if removed is None:
            removed = _cut_parts(first, second, common, quality)
    else:
        removed = _cut_parts(first, second, common, quality)
        added = _empty_by_balance(removed, balance, noise, added=True)
        if added is None:
            added = _cut_parts(second, first, common, quality)
            if removed is None:
                removed = _empty_by_balance(added, balance, noise, added=False)

    if added is not None:
        entry.added, entry.added_volume = added[0], max(added[0].volume, 0.0)
        entry.solvers = (*entry.solvers, *added[1])
    if removed is not None:
        entry.removed, entry.removed_volume = removed[0], max(removed[0].volume, 0.0)
        entry.solvers = (*entry.solvers, *removed[1])

    if added is None or removed is None:
        entry.findings.append(
            Finding(
                code="difference.incomplete",
                severity="info",
                message=_("Die Differenz ließ sich nicht vollständig berechnen."),
            )
        )
    return entry


def _clipped_to_the_change(
    before: MeshData, after: MeshData, quality: Quality
) -> tuple[MeshData, MeshData]:
    """Beide Körper auf den Quader beschnitten, in dem sie sich unterscheiden.

    Die Differenz zweier Körper liegt dort, wo ihre Häute verschieden sind:
    Ein Dreieck, das beide Netze mit derselben Orientierung tragen, hat auf
    derselben Seite Material und ist kein Rand von ``A - B`` oder ``B - A``.
    Jede Komponente der Differenz ist deshalb von geänderten Dreiecken
    begrenzt und liegt in deren Hülle. Bis zum 22.09.2026 schnitt der
    Vergleich trotzdem die ganzen Körper gegeneinander — an einer Platte mit
    204 000 Dreiecken, an der sich ein Bohrdurchmesser um einen Millimeter
    änderte, zweimal 183 ms Kern für eine Differenz aus 1 148 Dreiecken;
    beschnitten auf die Änderungsbox kosten beide Schnitte zusammen 25 ms
    (:func:`_changed_region`).

    Beschnitten wird über dieselbe Kette wie jede Boolesche Operation, mit
    einem Quader, der um :data:`CHANGED_REGION_MARGIN` über die geänderten
    Dreiecke hinausreicht. Reicht die Box über :data:`CHANGED_REGION_SHARE`
    der gemeinsamen Hülle, bleibt es beim ganzen Körper; scheitert ein
    Schnitt, ebenso — der Vergleich verliert dann Zeit, nie eine Antwort.
    """
    region = _changed_region(before, after)
    if region is None:
        return before, after
    low, high = region
    whole_low = np.minimum(before.raw.bounds[0], after.raw.bounds[0])
    whole_high = np.maximum(before.raw.bounds[1], after.raw.bounds[1])
    whole = float(np.prod(np.maximum(whole_high - whole_low, 0.0)))
    if whole <= 0.0 or float(np.prod(high - low)) > whole * CHANGED_REGION_SHARE:
        return before, after
    box = MeshData.of(
        cast(
            trimesh.Trimesh,
            trimesh.creation.box(extents=high - low, transform=_translation((low + high) / 2.0)),
        )
    )
    try:
        clipped_before = boolean("intersection", [before, box], quality=quality, allow_empty=True)
        clipped_after = boolean("intersection", [after, box], quality=quality, allow_empty=True)
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # Kerne scheitern auf kerneigene Arten
        _log.info("difference falls back to the whole bodies: %s", problem)
        return before, after
    return clipped_before.mesh, clipped_after.mesh


def _translation(offset: np.ndarray) -> np.ndarray:
    """Eine 4x4-Verschiebung — ohne den Umweg über ``geom.transform``, das
    diese Datei nicht kennt."""
    matrix = np.eye(4)
    matrix[:3, 3] = offset
    return matrix


#: Wie viele Ecken ein Körper haben darf, damit drei Eckennummern in eine
#: ``int64``-Dreiecksnummer passen (``n³ < 2⁶³``). Darüber gibt es keine
#: Änderungsbox, und der Vergleich läuft am ganzen Körper.
_CODED_VERTEX_LIMIT = 2_000_000


def _changed_region(before: MeshData, after: MeshData) -> tuple[np.ndarray, np.ndarray] | None:
    """Der Quader um die Dreiecke, die nicht beide Körper gleich tragen.

    Die Ecken des zweiten Körpers werden auf die des ersten abgebildet
    (Suchbaum, Abstand im Rundungsrauschen), jedes Dreieck bekommt eine
    Nummer aus seinen drei Ecken in kanonischer Drehung — die Orientierung
    bleibt, ein umgedrehtes Dreieck ist ein anderes —, und was nur eine
    Seite trägt, spannt die Box. ``None``, wenn nichts oder alles gleich ist.
    """
    from scipy.spatial import cKDTree

    first_vertices = np.asarray(before.raw.vertices, dtype=np.float64)
    second_vertices = np.asarray(after.raw.vertices, dtype=np.float64)
    if not len(first_vertices) or not len(second_vertices):
        return None
    if max(len(first_vertices), len(second_vertices)) > _CODED_VERTEX_LIMIT:
        return None
    roundoff = (
        8
        * np.finfo(np.float64).eps
        * max(
            float(np.max(np.abs(first_vertices))),
            float(np.max(np.abs(second_vertices))),
            np.finfo(np.float64).tiny,
        )
    )
    distances, nearest = cKDTree(first_vertices).query(second_vertices)
    mapped = np.where(distances <= roundoff, nearest, -1).astype(np.int64)
    first_faces = np.asarray(before.raw.faces, dtype=np.int64)
    second_faces = mapped[np.asarray(after.raw.faces, dtype=np.int64)]
    placeable = (second_faces >= 0).all(axis=1)
    count = len(first_vertices)
    first_codes = _triangle_codes(first_faces, count)
    second_codes = _triangle_codes(second_faces[placeable], count)
    # Ein Dreieck steht je Körper einmal; kommt seine Nummer in der
    # Vereinigung zweimal vor, tragen es beide. Ein ``unique`` über die
    # Vereinigung statt zweimal ``isin`` — 30 statt 80 ms an 400 000 Nummern.
    _codes, inverse, counts = np.unique(
        np.concatenate((first_codes, second_codes)), return_inverse=True, return_counts=True
    )
    shared = counts[inverse.reshape(-1)] > 1
    only_first = ~shared[: len(first_codes)]
    only_second = np.ones(len(second_faces), dtype=bool)
    only_second[np.flatnonzero(placeable)[shared[len(first_codes) :]]] = False
    if not only_first.any() and not only_second.any():
        return None
    corners = [
        np.asarray(before.raw.triangles, dtype=np.float64)[only_first].reshape(-1, 3),
        np.asarray(after.raw.triangles, dtype=np.float64)[only_second].reshape(-1, 3),
    ]
    changed = np.concatenate([part for part in corners if len(part)])
    low, high = changed.min(axis=0), changed.max(axis=0)
    span = high - low
    margin = max(
        math.hypot(float(span[0]), float(span[1]), float(span[2])) * CHANGED_REGION_MARGIN,
        roundoff,
    )
    return low - margin, high + margin


def _triangle_codes(faces: np.ndarray, count: int) -> np.ndarray:
    """Eine Zahl je Dreieck aus seinen Eckennummern — in kanonischer Drehung,
    also mit der kleinsten Nummer vorn und der Umlaufrichtung erhalten."""
    if not len(faces):
        return np.zeros(0, dtype=np.int64)
    start = np.argmin(faces, axis=1)
    rows = np.arange(len(faces))
    a = faces[rows, start]
    b = faces[rows, (start + 1) % 3]
    c = faces[rows, (start + 2) % 3]
    return np.asarray((a * count + b) * count + c, dtype=np.int64)


def _comparison_parts(
    before: MeshData, after: MeshData
) -> tuple[list[MeshData], list[MeshData], list[MeshData]]:
    """Unveränderte positive Schalen aus beiden Operanden herausnehmen.

    Der gemeinsame Anteil C wird aus beiden Operanden ausgeklammert.
    C verschwindet deshalb aus der ersten Rechnung, bleibt aber als Maske
    erhalten. Negative Innenschalen bleiben mit ihrem vollständigen Körper
    zusammen; sie sind keine separat zu vereinigenden Materialstücke.
    """
    groups = [face_components(mesh.raw) for mesh in (before, after)]
    if all(len(group) <= 1 for group in groups):
        return [before], [after], []
    parts = [
        [
            MeshData.of(cast(trimesh.Trimesh, mesh.raw.submesh([faces], append=True, repair=False)))
            for faces in group
        ]
        for mesh, group in zip((before, after), groups, strict=True)
    ]
    # Ein Vergleichsteil ohne Fläche — lauter entartete Dreiecke — hat das
    # Volumen null, und trimesh teilt für den Schwerpunkt dadurch: ``invalid
    # value`` aus numpy, kein Befund (Review, 21.09.2026). Ein solches Teil
    # ist kein Materialstück, und die Antwort darunter bleibt dieselbe.
    with np.errstate(divide="ignore", invalid="ignore"):
        degenerate = any(
            part.triangle_count == 0
            or not part.is_watertight
            or not part.raw.is_winding_consistent
            or part.volume <= 0.0
            for side in parts
            for part in side
        )
    if degenerate:
        return [before], [after], []
    first, second = parts
    candidates: dict[int, list[int]] = {}
    for index, part in enumerate(second):
        candidates.setdefault(part.triangle_count, []).append(index)
    common: list[MeshData] = []
    changed: list[MeshData] = []
    for part in first:
        for index in candidates.get(part.triangle_count, []):
            other = second[index]
            # Nur Float64-Rechenrauschen ist gleich, kein Fertigungsspiel.
            roundoff = (
                8
                * np.finfo(np.float64).eps
                * max(
                    float(np.max(np.abs(part.raw.vertices))),
                    float(np.max(np.abs(other.raw.vertices))),
                    np.finfo(np.float64).tiny,
                )
            )
            if not np.allclose(part.raw.bounds, other.raw.bounds, rtol=0, atol=roundoff):
                continue
            if _same_component(part, other, roundoff):
                common.append(part)
                candidates[part.triangle_count].remove(index)
                break
        else:
            changed.append(part)
    if not common:
        return [before], [after], []
    remaining = {index for indices in candidates.values() for index in indices}
    return changed, [part for index, part in enumerate(second) if index in remaining], common


def _same_component(first: MeshData, second: MeshData, roundoff: float) -> bool:
    """Eindeutige Eckenzuordnung und dieselben Dreiecke trotz neuer Indizes prüfen."""
    from scipy.spatial import cKDTree

    if first.vertex_count != second.vertex_count:
        return False
    distances, indices = cKDTree(first.raw.vertices).query(second.raw.vertices)
    if np.any(distances > roundoff) or len(np.unique(indices)) != len(indices):
        return False
    left = np.sort(np.asarray(first.raw.faces), axis=1)
    right = np.sort(indices[np.asarray(second.raw.faces)], axis=1)
    return bool(np.array_equal(left[np.lexsort(left.T[::-1])], right[np.lexsort(right.T[::-1])]))


def _cut_parts(
    keep: list[MeshData], subtract: list[MeshData], common: list[MeshData], quality: Quality
) -> tuple[MeshData, tuple[SolverInfo, ...]] | None:
    """Nur geändertes Material vergleichen und gemeinsame Überdeckungen abziehen."""
    if not keep:
        return MeshData.of(trimesh.Trimesh()), ()
    solvers: list[SolverInfo] = []
    try:
        operands = []
        for parts in (keep, subtract):
            if not parts:
                continue
            if len(parts) == 1:
                operands.append(parts[0])
            else:
                outcome = boolean("union", parts, quality=quality)
                operands.append(outcome.mesh)
                solvers.append(outcome.solver)
        mesh = operands[0]
        if len(operands) == 2:
            cut = _cut(operands[0], operands[1], quality)
            if cut is None:
                return None
            mesh, solver = cut
            solvers.append(solver)
        for mask in common:
            if not mesh.triangle_count:
                break
            if np.any(mesh.raw.bounds[1] <= mask.raw.bounds[0]) or np.any(
                mask.raw.bounds[1] <= mesh.raw.bounds[0]
            ):
                continue
            cut = _cut(mesh, mask, quality)
            if cut is None:
                return None
            mesh, solver = cut
            solvers.append(solver)
        return mesh, tuple(solvers)
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:
        _log.warning("component difference could not be computed: %s", problem)
        return None


def _volume_balance(
    first: list[MeshData], second: list[MeshData], common: list[MeshData]
) -> float | None:
    """|danach| - |davor| — oder ``None``, wo die Volumina der Netze keine
    Volumina der Körper sind.

    Für zwei Körper A und B gilt |A - B| - |B - A| = |A| - |B|: Hat einer der
    zwei Schnitte gerechnet, steht der andere als Zahl fest. Das Volumen eines
    Netzes ist aber nur dann das seines Körpers, wenn sich keine Schalen
    überdecken — eine zweite, ineinandersteckende zählte doppelt. Gerechnet
    wird deshalb nur an je einem zusammenhängenden Stück ohne gemeinsamen
    Anteil; alles andere schneidet beide Seiten wie bisher.
    """
    if common or len(first) != 1 or len(second) != 1:
        return None
    before, after = first[0], second[0]
    if len(face_components(before.raw)) != 1 or len(face_components(after.raw)) != 1:
        return None
    return float(signed_volume(after.raw)) - float(signed_volume(before.raw))


def _empty_by_balance(
    known: tuple[MeshData, tuple[SolverInfo, ...]] | None,
    balance: float | None,
    noise: float,
    *,
    added: bool,
) -> tuple[MeshData, tuple[SolverInfo, ...]] | None:
    """Die andere Seite des Vergleichs als leer, wenn die Bilanz es belegt.

    ``known`` ist der gerechnete Schnitt der Gegenseite, ``added`` sagt,
    welche Seite hier gefragt ist. Aus der Bilanz folgt ihr Volumen; liegt es
    nicht über ``noise`` — der Grenze, ab der der Vergleich überhaupt eine
    Änderung meldet —, ist sie leer, ein leeres Netz ohne Löser. Sonst
    ``None``, und es wird geschnitten.

    **Der Schnitt, den das spart, ist der schwierigste von beiden.** Liegt ein
    Körper ganz im anderen und decken sich ihre ebenen Flächen mit
    verschiedenen Dreiecken, liefert der Kern für den inneren minus den
    äußeren Splitter: an der Senkplatte (311 296 Dreiecke, Bohrung Ø 5,2 auf
    Ø 6 und 6,5) solche mit negativem Volumen, die beide Stufen der
    Entwurfskette ablehnten — die Vorschau hieß unvollständig —, bei Ø 7 ein
    Kontaktrest aus 1 980 Dreiecken, gezeigt als hinzugekommenes Material
    (26.09.2026, RM-212).
    """
    if known is None or balance is None:
        return None
    other = max(float(known[0].volume), 0.0)
    derived = other + balance if added else other - balance
    if derived > noise:
        return None
    return MeshData.of(trimesh.Trimesh()), ()


def _noise(profile: Profile | None) -> float:
    """Die Grenze zwischen „hat sich etwas geändert" und „Rauschen"."""
    return profile.smallest_printable_volume if profile is not None else NOISE_VOLUME


def compare_scenes(before: Scene, after: Scene, *, quality: Quality = "draft") -> SceneDifference:
    """Die Differenz einer ganzen Transaktion — die Einheit, in der §18.7
    misst.

    Den Drucker bringt die Szene mit; gefragt wird die **nachher**, denn um
    deren Zustand geht es. Eine Szene ohne Profil gibt es (Tests, ein frisch
    geöffnetes Dokument), und dann misst die Differenz am Rauschen.
    """
    profile = after.profile if after.profile is not None else before.profile
    result = SceneDifference()
    result.created = tuple(name for name in after.objects if name not in before.objects)
    result.deleted = tuple(name for name in before.objects if name not in after.objects)

    for object_id in result.created:
        difference = _whole_body(after.objects[object_id], object_id, added=True, profile=profile)
        if difference is not None:
            result.entries[object_id] = difference
    for object_id in result.deleted:
        difference = _whole_body(before.objects[object_id], object_id, added=False, profile=profile)
        if difference is not None:
            result.entries[object_id] = difference

    for object_id, entry in after.objects.items():
        earlier = before.objects.get(object_id)
        if earlier is None:
            continue
        # **Auch ein exakter Körper zeigt, was sich geändert hat.** Hier stand
        # ein stilles ``continue`` für alles, was kein ``MeshData`` ist — ein
        # STEP-Import also, und jeder Körper aus dem exakten Kern. Kein
        # Absturz und keine Meldung: Die Differenzansicht blieb nach einer
        # Änderung daran einfach leer, obwohl §18.7 sie verspricht. Derselbe
        # Zwilling wie beim Absturz der Analysekarten (27.08.2026), nur still
        # — und still ist schwerer zu finden. Der Weg von B-Rep zu Mesh steht
        # jederzeit offen (§30); verglichen wird auf der Tessellation.
        try:
            first, second = as_mesh_data(earlier.mesh), as_mesh_data(entry.mesh)
        except GeometryError:
            # Ein Körper, der keiner der beiden Kerne ist, hat keine Dreiecke
            # zum Vergleichen. Die Differenz ist eine Auskunft und keine
            # Zusage — sie fehlt dann, statt den Zug abzubrechen.
            continue
        if _same_geometry(first, second):
            # **Dieselben Dreiecke, andere Farben — auch das ist eine Vorschau.**
            # Die vier Filament-Operationen ändern keinen Eckpunkt; hier stand
            # ``continue``, und im Bild blieb die alte Farbe, bis übernommen war.
            if not _same_colouring(earlier, entry):
                result.entries[object_id] = Difference(
                    object_id=object_id, recoloured=entry, noise_volume=_noise(profile)
                )
            continue
        difference = compare(first, second, quality=quality, profile=profile)
        difference.object_id = object_id
        difference.result = entry
        # Neue Dreiecke, gleiches Volumen: Die Zahl sagt „nichts", das Netz
        # sagt etwas — und darum geht es bei diesen Operationen. **Aber nur,
        # wenn die Zahl gerechnet wurde.** Scheitert ``_cut`` in beiden
        # Richtungen, sind beide Volumina null, ``changed`` ist falsch, und der
        # Eintrag behauptete „neue Dreiecke, gleiches Volumen", wo über das
        # Volumen nichts bekannt ist — und ``reshaped`` unterdrückte dazu die
        # Warnung der Operation im Band (Review 14.09.2026). Eine
        # unvollständige Differenz bleibt, was sie ist: unvollständig.
        incomplete = any(finding.code == "difference.incomplete" for finding in difference.findings)
        if not difference.changed and not incomplete:
            difference.retriangulated = second
        result.entries[object_id] = difference
    return result


def _same_colouring(earlier: SceneObject, entry: SceneObject) -> bool:
    """Ob zwei Körper dieselben Farben tragen — Slot je Dreieck und die
    Slotliste mit ihren Farben. Beides muss gleich sein; eine umgefärbte
    Liste bei gleicher Zuordnung ist genauso eine Änderung wie umgekehrt."""
    return tuple(getattr(earlier.mesh, "slots", ())) == tuple(
        getattr(entry.mesh, "slots", ())
    ) and list(earlier.material_slots) == list(entry.material_slots)


def _whole_body(
    entry: SceneObject,
    object_id: str,
    *,
    added: bool,
    profile: Profile | None = None,
) -> Difference | None:
    """Ein Körper, der ganz erschienen oder ganz verschwunden ist.

    **Die Differenz eines neuen Körpers ist er selbst.** Hier stand nichts —
    ein Objekt ohne Vorgänger wurde übersprungen, und damit blieb die
    Differenzansicht bei jeder **erzeugenden** Operation leer: Skizze
    extrudieren, Quader anlegen, Zylinder erzeugen. Wer eine Höhe eintippt,
    sah nichts, bis er anwendete, und das trifft genau den Anfang von Weg 2
    (§2.2, neu konstruieren).

    Gefunden über die Live-Vorschau des Operationsdialogs (§18.7): Sie rechnet
    seit je richtig, und die Ansicht zeichnet ``entries`` — nur stand der neue
    Körper allein in ``created``, ohne Geometrie daneben. Zwei Listen für eine
    Sache, und die gezeichnete war die leere (27.08.2026, Roberts Frage nach
    dem Hochziehen in der Seitenansicht).

    Die Zahl hing mit daran: ``added_volume`` meldete null, während
    achttausend Kubikmillimeter entstanden. Eine Differenz, die ihr eigenes
    Ergebnis nicht mitzählt, ist als Auskunft falsch und nicht bloß als Bild
    leer.

    ``created`` und ``deleted`` bleiben, wie sie waren: Sie sagen, **dass** es
    einen Körper mehr oder weniger gibt, und das ist eine andere Auskunft als
    seine Geometrie — der Chat schreibt sie in Worte, die Ansicht zeichnet sie
    nicht.
    """
    try:
        mesh = as_mesh_data(entry.mesh)
    except GeometryError:
        # Dieselbe Haltung wie beim Vergleich zweier Körper: Was keine
        # Dreiecke hat, fehlt in der Ansicht, statt den Zug abzubrechen.
        return None
    volume = max(mesh.volume, 0.0)
    noise = _noise(profile)
    if volume < noise:
        return None
    return Difference(
        object_id=object_id,
        added=mesh if added else None,
        removed=None if added else mesh,
        added_volume=volume if added else 0.0,
        removed_volume=0.0 if added else volume,
        noise_volume=noise,
    )


def _same_geometry(first: MeshData, second: MeshData) -> bool:
    """Nur identische Netzarrays sparen die geometrische Differenzrechnung.

    Das ist eine Identitätsprüfung, kein geometrischer Toleranzvergleich.
    Gleiche Kennzahlen allein übersehen etwa ein verschobenes Loch.
    """
    return first.raw is second.raw or (
        np.array_equal(first.raw.vertices, second.raw.vertices)
        and np.array_equal(first.raw.faces, second.raw.faces)
    )


def _cut(
    keep: MeshData, subtract: MeshData, quality: Quality
) -> tuple[MeshData, SolverInfo] | None:
    try:
        # **``allow_empty``, weil hier nichts übrig zu bleiben braucht.** Ein
        # Vergleich fragt „was kam dazu, was fiel weg" — und die Antwort ist oft
        # „nichts". Ohne dieses Wort wirft die Kette dann ``BooleanFailedError``
        # mit dem Titel „Es bleibt kein Körper übrig", ``_cut`` gibt ``None``
        # zurück, und der Vergleich meldet, er habe nicht rechnen können. Das
        # stimmte nie: Er hat gerechnet, und das Ergebnis war leer.
        #
        # Im Protokoll des ersten Kunden mit 0.1.3 stand das zwölfmal, mit einem
        # Befund im Prüfbericht daneben — für zwei Zustände, zwischen denen sich
        # schlicht nichts geändert hatte.
        outcome = boolean("difference", [keep, subtract], quality=quality, allow_empty=True)
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # Kerne scheitern auf kerneigene Arten
        _log.warning("difference could not be computed: %s", problem)
        return None
    return _without_contact_shells(outcome.mesh), outcome.solver


def _without_contact_shells(mesh: MeshData) -> MeshData:
    """Reine Float64-Kontaktreste vor weiteren Maskenschnitten entfernen.

    Auch eine Nullhülle kann durch Rundung ein kleines orientiertes Integral
    tragen. Wie im nativen Booleschen Kern gilt gamma(8) mal Koordinatengröße
    mal Oberfläche; negative Innenschalen mit echtem Volumen bleiben erhalten.
    """
    groups = face_components(mesh.raw)
    if len(groups) <= 1:
        return mesh
    kept = []
    relative_error = 8 * np.finfo(np.float64).eps
    for faces in groups:
        part = cast(trimesh.Trimesh, mesh.raw.submesh([faces], append=True, repair=False))
        roundoff = (
            relative_error
            / (1 - relative_error)
            * float(np.max(np.abs(part.vertices)))
            * float(part.area)
        )
        if abs(signed_volume(part)) > roundoff:
            kept.append(faces)
    if len(kept) == len(groups):
        return mesh
    return mesh.replacing(
        cast(trimesh.Trimesh, mesh.raw.submesh([np.concatenate(kept)], append=True, repair=False))
        if kept
        else trimesh.Trimesh()
    )
