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

from dataclasses import dataclass, field

from app.core.errors import PROGRAMMING_ERRORS, GeometryError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.log import get_logger
from app.core.types import Finding, ObjectId, Quality, Scene, SceneObject, SolverInfo
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Volumen darunter sind Vernetzungsrauschen, keine Änderung (§11.2 dem
#: Sinne nach).
NOISE_VOLUME = 1e-3


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

    @property
    def changed(self) -> bool:
        return self.added_volume > NOISE_VOLUME or self.removed_volume > NOISE_VOLUME


@dataclass(slots=True)
class SceneDifference:
    """Die ganze Szene, Körper für Körper, plus was erschien und verschwand."""

    entries: dict[ObjectId, Difference] = field(default_factory=dict)
    created: tuple[ObjectId, ...] = ()
    deleted: tuple[ObjectId, ...] = ()

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


def compare(before: MeshData, after: MeshData, *, quality: Quality = "draft") -> Difference:
    """Ein Körper gegen seinen Nachfolger."""
    entry = Difference(object_id="")
    added = _cut(after, before, quality)
    removed = _cut(before, after, quality)

    if added is not None:
        entry.added, entry.added_volume = added[0], max(added[0].volume, 0.0)
        entry.solvers = (*entry.solvers, added[1])
    if removed is not None:
        entry.removed, entry.removed_volume = removed[0], max(removed[0].volume, 0.0)
        entry.solvers = (*entry.solvers, removed[1])

    if added is None or removed is None:
        entry.findings.append(
            Finding(
                code="difference.incomplete",
                severity="info",
                message=_("Die Differenz ließ sich nicht vollständig berechnen."),
            )
        )
    return entry


def compare_scenes(before: Scene, after: Scene, *, quality: Quality = "draft") -> SceneDifference:
    """Die Differenz einer ganzen Transaktion — die Einheit, in der §18.7
    misst."""
    result = SceneDifference()
    result.created = tuple(name for name in after.objects if name not in before.objects)
    result.deleted = tuple(name for name in before.objects if name not in after.objects)

    for object_id in result.created:
        difference = _whole_body(after.objects[object_id], object_id, added=True)
        if difference is not None:
            result.entries[object_id] = difference
    for object_id in result.deleted:
        difference = _whole_body(before.objects[object_id], object_id, added=False)
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
        if abs(first.volume - second.volume) < NOISE_VOLUME and _same_bounds(first, second):
            continue
        difference = compare(first, second, quality=quality)
        difference.object_id = object_id
        result.entries[object_id] = difference
    return result


def _whole_body(entry: SceneObject, object_id: str, *, added: bool) -> Difference | None:
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
    if volume < NOISE_VOLUME:
        return None
    return Difference(
        object_id=object_id,
        added=mesh if added else None,
        removed=None if added else mesh,
        added_volume=volume if added else 0.0,
        removed_volume=0.0 if added else volume,
    )


def _same_bounds(first: MeshData, second: MeshData) -> bool:
    """Billige Vorprüfung: gleiches Volumen und gleicher Quader heißt, dass
    sich auch nichts bewegt hat.

    Verglichen wird mit ``EPS_GEOM``: Beide Seiten sind Millimeter, also ist es
    dieselbe Frage, die §11.2 mit dieser Toleranz beantwortet. Hier stand die
    Zahl ``1e-6`` — derselbe Wert, nur ohne den Namen, und damit eine Stelle,
    die eine Änderung an ``EPS_GEOM`` nicht mitbekommen hätte.
    """
    return all(
        abs(a - b) < EPS_GEOM
        for a, b in zip(
            (*first.bounds.minimum, *first.bounds.maximum),
            (*second.bounds.minimum, *second.bounds.maximum),
            strict=True,
        )
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
    return outcome.mesh, outcome.solver
