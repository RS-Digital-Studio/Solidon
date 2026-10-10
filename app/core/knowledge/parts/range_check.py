"""Der Bereichstest in der Anwendung (§24.3, §24.5 — Konzept E3).

§24.3 sagt: „Ein Baustein ohne diesen Test gilt als nicht vorhanden", und
§24.5 verlangt für eigene Bausteine denselben Test, mit Warnhinweis im
Katalog, wenn er nicht bestanden ist. Für die mitgelieferten Bausteine läuft
er in der Suite (``tests/test_parts.py``); ein Kunde hat keine Suite — sein
Rezept wird deshalb **beim Anlegen** geprüft, mit Fortschritt und Abbruch,
und das Ergebnis bleibt am Baustein.

Die Ecken sind dieselben wie im Test, und das ist der Punkt: eine Regel, ein
Ort. Das kartesische Produkt ist Absicht — erst die Kombination zweier Grenzen
ist oft die Stelle, an der eine Geometrie zusammenfällt.
"""

from __future__ import annotations

import gc
import itertools
import math
import threading
from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import Any, Final

from app.core.errors import OperationCancelled, ValidationError
from app.core.knowledge.parts.ops import PLAY_FIELD
from app.core.knowledge.parts.registry import FeatureRequirement, PartSpec, WallRequirement
from app.core.types import BaseParams, CancelToken, PartResult, Profile, ProgressFn
from app.core.units import EPS_DISPLAY, EPS_GEOM, PRINT_LIMIT
from app.i18n import _


def _corner_values(
    params: type[BaseParams], pinned: Collection[str] = ()
) -> list[tuple[str, list[Any]]]:
    """Die unterschiedlichen Randwerte je Feld, noch ohne ihr kartesisches Produkt.

    ``pinned`` stehen auf ihrer Vorgabe: der Spiegelschalter eines Bausteins
    (``PartSpec.mirrored_by``), dessen andere Stellung :func:`check` als
    Spiegelbild belegt.
    """
    lists: list[tuple[str, list[Any]]] = []
    for entry in params.spec():
        values: list[Any] = []
        if entry.name in pinned:
            values = [entry.default]
        elif entry.kind == "enum":
            values = list(entry.choices)
        elif entry.kind == "bool":
            values = [True, False]
        elif entry.kind in ("float", "int"):
            values = [entry.minimum, entry.maximum]
        values = list(dict.fromkeys(value for value in values if value is not None))
        if values:
            lists.append((entry.name, values))
    return lists


#: Vollständige Kombinationen je Lauf für einen **eigenen** Baustein des Kunden
#: (Rezept, eigene ``.py``): Er prüft auf seinem Rechner, im Dialog, und der
#: Dialog nennt vorher die geschätzte Dauer.
MAX_CORNERS: Final = 512

#: Dieselbe Grenze für die **mitgelieferte** Bibliothek (RM-578, Entscheidung
#: Robert, 08.10.2026: „wenn wir mehr liefern können, wollen wir das“). Ihr
#: Nachweis läuft einmal bei uns (``tools/check_part_ranges.py --jobs``), nie
#: beim Kunden; die Grenze richtet sich deshalb nach seiner Rechenzeit, nicht
#: nach einem Dialog. Gemessen am 08.10.2026 mit sechs Prozessen: Bausteine ohne
#: Gewinde kosten 0,02 bis 0,3 s je Ecke, 4096 Ecken also höchstens rund
#: zwanzig Minuten — so lange wie das druckbare Gewinde mit 248 Ecken bei 5 s je
#: Ecke. Ein Gewindebaustein bleibt durch seine Kosten von selbst darunter. Die
#: volle Prüfung ohne Stichprobe gilt unverändert (§24.3).
LIBRARY_MAX_CORNERS: Final = 4096


def corner_limit(source: str) -> int:
    """Die Eckengrenze für einen Baustein dieser Herkunft (``PartSpec.source``)."""
    return LIBRARY_MAX_CORNERS if source == "shipped" else MAX_CORNERS


def _collect_on_main_thread() -> None:
    """Kernzyklen sammeln, ohne im Arbeiter fremde GUI-Objekte zu finalisieren."""
    if threading.current_thread() is threading.main_thread():
        gc.collect()


@dataclass(frozen=True, slots=True)
class _Field:
    """Ein Feld des Bereichs: seine Randwerte, und wovon abhängt, ob sie zählen."""

    name: str
    values: list[Any]
    rest: Any
    """Der Wert in einer Ecke, in der das Feld nicht wirkt — seine Vorgabe."""
    wanted: tuple[str | bool, ...]
    """Bei welchen Werten seines Steuerfelds es wirkt (``ParamSpec.depends_on``)."""


def _matches(value: Any, wanted: tuple[str | bool, ...]) -> bool:
    """Ob ein Steuerwert das abhängige Feld wirksam macht — ``bool`` nie gleich ``int``."""
    return any(
        value is choice
        if isinstance(choice, bool)
        else (value == choice and not isinstance(value, bool))
        for choice in wanted
    )


def _forest(
    params: type[BaseParams], pinned: Collection[str] = ()
) -> tuple[list[_Field], dict[str, list[_Field]], list[str]]:
    """Die Felder als Wald: Wurzeln ohne Bedingung, darunter, was von ihnen abhängt.

    Ein Feld hängt an höchstens einem Steuerfeld (``depends_on``). Wo das
    Steuerfeld fehlt oder die Kette einen Kreis schließt — ein fehlerhaftes
    Schema, das die Registerprüfung meldet —, zählt das Feld wie ohne
    Bedingung: lieber eine Ecke zu viel als eine zu wenig.
    """
    entries = {entry.name: entry for entry in params.spec()}
    fields = {}
    for name, values in _corner_values(params, pinned):
        entry = entries[name]
        rest = entry.default if entry.default in values or entry.kind in ("float", "int") else None
        fields[name] = _Field(
            name=name,
            values=values,
            rest=values[0] if rest is None else rest,
            wanted=entry.depends_on[1] if entry.depends_on is not None else (),
        )
    parent = {
        name: entries[name].depends_on[0]  # type: ignore[index]
        for name in fields
        if entries[name].depends_on is not None and entries[name].depends_on[0] in fields  # type: ignore[index]
    }
    reached: set[str] = set()
    pending = [name for name in fields if name not in parent]
    while pending:
        name = pending.pop()
        reached.add(name)
        pending.extend(child for child, above in parent.items() if above == name)
    for name in [name for name in parent if name not in reached]:
        del parent[name]
    children: dict[str, list[_Field]] = {name: [] for name in fields}
    for name in fields:
        if name in parent:
            children[parent[name]].append(fields[name])
    roots = [name for name in fields if name not in parent]
    return [fields[name] for name in roots], children, list(fields)


def _count(field: _Field, children: dict[str, list[_Field]]) -> int:
    """Wie viele Ecken ein Feld samt allem, was an ihm hängt, beiträgt."""
    return sum(
        math.prod(
            _count(child, children) if _matches(value, child.wanted) else 1
            for child in children[field.name]
        )
        for value in field.values
    )


def _at_rest(field: _Field, children: dict[str, list[_Field]]) -> dict[str, Any]:
    """Ein Feld ohne Wirkung und alles, was an ihm hängt, auf seiner Vorgabe."""
    values = {field.name: field.rest}
    for child in children[field.name]:
        values.update(_at_rest(child, children))
    return values


def _expand(field: _Field, children: dict[str, list[_Field]]) -> list[dict[str, Any]]:
    """Die Ecken eines Feldes samt allem, was an ihm hängt."""
    expanded: list[dict[str, Any]] = []
    for value in field.values:
        below = [
            _expand(child, children)
            if _matches(value, child.wanted)
            else [_at_rest(child, children)]
            for child in children[field.name]
        ]
        for combination in itertools.product(*below):
            merged = {field.name: value}
            for part in combination:
                merged.update(part)
            expanded.append(merged)
    return expanded


def corner_count(params: type[BaseParams], pinned: Collection[str] = ()) -> int:
    """Zählt den ganzen Bereich, ohne eine einzige Kombination anzulegen."""
    roots, children, _order = _forest(params, pinned)
    return math.prod(_count(root, children) for root in roots)


def part_corner_count(spec: PartSpec) -> int:
    """Die Ecken eines Registerbausteins — sein Spiegelschalter zählt keine (:func:`check`)."""
    return corner_count(spec.params, _pinned(spec))


def _pinned(spec: PartSpec) -> tuple[str, ...]:
    """Die Felder, die der Bereichstest dieses Bausteins auf ihrer Vorgabe lässt."""
    return (spec.mirrored_by,) if spec.mirrored_by else ()


def require_range_size(count: int, limit: int = MAX_CORNERS) -> None:
    """Weist zu große Bereiche vor dem Rechnen ab; niemals nur teilweise prüfen."""
    if count > limit:
        raise ValidationError(
            field="exposed",
            constraint="maximum",
            values={"count": count, "limit": limit},
            detail=_(
                "Der Bereichstest umfasst {count} Kombinationen; höchstens {limit} "
                "sind möglich. Geben Sie weniger Maße frei.",
                count=count,
                limit=limit,
            ),
        )


def corners(
    params: type[BaseParams], limit: int = MAX_CORNERS, pinned: Collection[str] = ()
) -> list[dict[str, Any]]:
    """Der Parameterbereich als die Werte, die ein Baustein überstehen muss.

    Der kleinste und der größte Wert jeder Zahl, jede Wahl jedes Enums und
    beide Zustände jedes Schalters — als vollständiges kartesisches Produkt.
    Die Vorgabe ist keine Grenze; sie wird im Reproduzierbarkeitstest gefahren.

    Die vorherige zyklische Fassung prüfte jeden Einzelwert, aber nicht sein
    Zusammenspiel: 124 Zeilen sahen nach Abdeckung aus, obwohl die Bibliothek
    2.114 Grenzkombinationen hat. Gemessen am 31.08.2026 brauchen ihre reinen
    Builds 73,2 Sekunden. Das ist ein sichtbarer, abbrechbarer Arbeitslauf und
    kein Grund, die zugesagte Menge still zu verkürzen.

    **Ein Feld ohne Wirkung vervielfacht nichts.** Wo seine Bedingung
    (``ParamSpec.depends_on``) in einer Ecke nicht erfüllt ist, verwirft der
    Baustein seinen Wert (``oberflaeche.md``: „Ein Feld ohne Wirkung steht nicht
    da"); es steht dort auf seiner Vorgabe, statt dieselbe Ecke an seinen
    Grenzen noch einmal zu bauen. Bis zum 06.10.2026 tat es das: Der
    Nenndurchmesser eines eigenen Maßes verdoppelte jede Tabellengröße, und ein
    Schraubenloch mit 23 Normgrößen und eigenem Maß hätte 1536 Ecken gezählt,
    von denen 400 verschieden sind.
    """
    roots, children, order = _forest(params, pinned)
    require_range_size(math.prod(_count(root, children) for root in roots), limit)
    if not roots:
        return [{}]
    plan: list[dict[str, Any]] = []
    for combination in itertools.product(*(_expand(root, children) for root in roots)):
        merged: dict[str, Any] = {}
        for part in combination:
            merged.update(part)
        plan.append({name: merged[name] for name in order})
    return plan


DEFAULT_WALL_REQUIREMENT: Final = WallRequirement()


def _is_cancelled(token: CancelToken) -> bool:
    """Fragt erneut; der Zustand darf sich während einer Phase ändern."""
    return token.is_cancelled


@dataclass(frozen=True, slots=True)
class RangeFailure:
    """Eine Ecke, die nicht hielt — mit den Werten, bei denen es geschah."""

    values: dict[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class RangeExclusion:
    """Eine Ecke, die der Baustein selbst als nicht baubar erklärt hat."""

    values: dict[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class RangeReport:
    """Was der Bereichstest ergeben hat. Hängt am Baustein, nicht im Hash.

    Der Hash ist die Version des Rezepts (§24.4) — stünde der Bericht darin,
    machte das **Prüfen** aus dem Rezept ein anderes, und jedes Projekt
    meldete beim Öffnen eine Änderung, die keine ist.

    ``excluded`` sind die Ecken, die :attr:`PartSpec.feasible` vorher als
    nicht baubar erklärt hat und an denen der Baustein wie erklärt ablehnt.
    Sie zählen nicht als Fehler — ein erklärter Ausschluss ist Teil des
    Vertrags; ein **unerklärter** Abbruch bleibt einer.
    """

    checked: int = 0
    failures: tuple[RangeFailure, ...] = ()
    excluded: tuple[RangeExclusion, ...] = ()

    @property
    def passed(self) -> bool:
        return self.checked > 0 and not self.failures


@dataclass(slots=True)
class _Silent:
    @property
    def is_cancelled(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        return None


#: Zwei Flächen bilden eine Wand, wenn ihre Normalen höchstens rund 18 Grad
#: von der Gegenrichtung abweichen. Eine Fase oder Keilspitze ist damit kein
#: vermeintlich dünnes Wandstück; eine facettierte Rundung bleibt eines.
OPPOSING_NORMAL: Final = -0.95


def local_wall_thickness(mesh: Any, cancelled: CancelToken | None = None) -> float | None:
    """Die kleinste lokale Wand zwischen wirklich gegenläufigen Flächen.

    Von **jedem** Dreiecksmittelpunkt läuft ein Strahl nach innen bis zum
    ersten Austritt. Dessen Fläche muss gegenläufig sein: Nur dann ist der
    Abstand eine Wandstärke. So werden eine Fase, ein scharfer Keil und das
    Ende eines Zylinders nicht mit einer dünnen Wand verwechselt. Ist der
    nächste Austritt nicht gegenläufig, zählt dieser Strahl nicht — es wird
    nicht am selben Punkt nach einem zweiten, weiter entfernten Austritt
    gesucht.

    Gerechnet wird in ``geom.mesh.ray_hits_batch``: Möller-Trumbore gegen die
    Dreiecke, die ein räumlicher Index je Strahl vorauswählt (RM-050 — Ersatz
    für VTKs ``vtkStaticCellLocator``, plattformgleich wie jeder andere
    Strahl im Kern; RM-214 — ein Baum aus Hüllquadern, auch an Vollkörpern
    fast linear; die Auswahl ändert den Aufwand, den Treffer nur an fast
    streifenden Rändern, die auch der Vollvergleich nur gerundet kennt —
    Grenze und Kosten stehen an ``ray_hits_batch``). Es gibt keine
    Stichprobe: auch ein kleines Detail mit einem
    einzigen Dreieck wird vermessen. ``None`` bedeutet, dass der Körper keine
    zwei gegenläufigen Flächen trägt, oder dass der Lauf abgebrochen wurde;
    der Aufrufer unterscheidet beides am Token.
    """
    import numpy as np

    from app.core.geom.mesh import ray_hits_batch

    body = mesh.raw
    if not len(body.faces):
        return None
    vertices = np.asarray(body.vertices, dtype=np.float64)
    faces = np.asarray(body.faces, dtype=np.int64)
    centres = np.asarray(body.triangles_center, dtype=float)
    normals = np.asarray(body.face_normals, dtype=float)

    travel, hit_face = ray_hits_batch(
        vertices[faces],
        centres,
        -normals,
        edge_margin=EPS_GEOM,
        # Das Dreieck unter dem Startpunkt liegt exakt auf der Strahlachse
        # (der Strahl steht senkrecht auf ihm) und wäre sonst sein eigener
        # erster Treffer bei t≈0 — dieselbe Schwelle wie in
        # ``geom.measure.ray_distances``.
        minimum_travel=EPS_GEOM * 100.0,
        cancelled=cancelled,
    )
    if cancelled is not None and cancelled.is_cancelled:
        return None
    hit = hit_face >= 0
    if not np.any(hit):
        return None
    opposite = normals[hit_face[hit]]
    dotted = np.sum(normals[hit] * opposite, axis=1)
    opposing = np.zeros(len(hit), dtype=bool)
    opposing[hit] = dotted <= OPPOSING_NORMAL
    if not np.any(opposing):
        return None
    return float(travel[opposing].min())


def has_self_intersections(mesh: Any, cancelled: CancelToken | None = None) -> bool:
    """Ob nicht benachbarte Dreiecke einander schneiden.

    Ein wasserdichtes Netz kann aus zwei geschlossenen Hüllen bestehen, die
    durcheinanderlaufen, und zwei Bausteinflächen können an einer Ecke des
    Parameterbereichs deckungsgleich aufeinanderfallen. Topologieflags sehen
    beides nicht. Gerechnet wird in ``geom.intersections`` — dieselbe
    vollständige Rechnung, die auch die Netzfehlerkarte fragt, als Feld statt
    als Schleife über Dreieckspaare (RM-206: am Schraubenloch 1,5 s je Ecke
    zuvor).

    Ein Abbruch gibt ``False`` zurück; der Aufrufer unterscheidet ihn am Token.
    """
    from app.core.geom.intersections import intersects

    if cancelled is not None and cancelled.is_cancelled:
        return False
    body = mesh.raw
    try:
        return intersects(body.vertices, body.faces, cancelled)
    except OperationCancelled:
        return False


def printable_gap(mesh: Any, *, cancelled: CancelToken | None = None) -> float | None:
    """Kleinster Flächenabstand aller Komponenten, unabhängig von ihrer Reihenfolge."""
    from app.core.geom.measure import surface_gap
    from app.core.geom.mesh import MeshData

    pieces = mesh.raw.split(only_watertight=False)
    if len(pieces) < 2:
        return None
    closest = float(mesh.bounds.diagonal)
    for index, first in enumerate(pieces):
        for second in pieces[index + 1 :]:
            if cancelled is not None and cancelled.is_cancelled:
                return None
            measured = surface_gap(MeshData.of(first), MeshData.of(second), closest)
            if measured is None:
                return None
            closest = min(closest, measured)
            if closest <= EPS_GEOM:
                return 0.0
    return closest


def check(
    params: type[BaseParams],
    build: Any,
    profile: Profile,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
    joined_by_host: bool = False,
    bodies: int = 1,
    wall: WallRequirement = DEFAULT_WALL_REQUIREMENT,
    features: tuple[FeatureRequirement, ...] = (),
    feasible: Callable[[BaseParams], Any] | None = None,
    limit: int = MAX_CORNERS,
    mirrored_by: str | None = None,
    window: tuple[int, int] | None = None,
) -> RangeReport:
    """Fährt die Ecken und sagt je Ecke, was nicht hielt.

    ``mirrored_by`` ist ein Schalter, der den Baustein nur spiegelt
    (``PartSpec.mirrored_by``, RM-544): Die Prüfungen laufen mit ihm auf seiner
    Vorgabe, denn Wasserdichtheit, Wand, Selbstdurchdringung und Merkmale sind
    unter einer Spiegelung dieselben. **Dass er nur spiegelt, belegt jede Ecke
    selbst** (:func:`_mirror_problem`): Sie baut auch die andere Stellung, und
    deren Körper muss das Spiegelbild an y = 0 sein — dasselbe Volumen, jede Ecke
    auf der gespiegelten Fläche und umgekehrt, dieselben Merkmale. Eine erklärte
    Ausschlussecke muss in beiden Stellungen ausgeschlossen sein. Damit ist die
    andere Stellung an jeder Ecke voll geprüft, nicht an einer Stichprobe.

    ``window`` fährt nur die Ecken ``[von, bis)`` des Plans: Der Nachweis der
    Bibliothek teilt einen großen Baustein so auf mehrere Prozesse
    (``tools/check_part_ranges.py``) und zählt die Teile zusammen.

    ``feasible`` ist die erklärte Bedingung des Bausteins zwischen seinen
    Parametern (:attr:`PartSpec.feasible`): Nennt sie für eine Ecke einen
    Grund, muss der Bau dort mit ``ValidationError`` ablehnen — dann ist die
    Ecke ein erklärter Ausschluss. Baut er trotzdem, ist die Erklärung falsch
    und die Ecke ein Fehler; bricht er anders ab, ebenso.

    ``joined_by_host`` nimmt die Prüfung auf **eine** Komponente heraus — für
    Bausteine, deren Teile erst der Träger verbindet. Der Lochwand-Einhänger
    setzt ohne Rückplatte je Haken einen Zapfen; zwei Zapfen sind zwei Körper,
    und an dem Teil, an das sie kommen, sind sie einer. Ohne diesen Schalter
    trüge sein Katalogeintrag eine Warnung über einen Baustein, der im Einsatz
    tadellos ist (§24.5 verlangt, dass ein gebrochener Bericht dort steht).
    Die übrigen drei Prüfungen gelten unverändert: Ein Baustein darf auch
    mehrteilig weder undicht noch leer noch zu dünn sein.

    ``bodies`` ist der **andere** mehrteilige Fall (§24.3, Entscheidung Robert
    vom 25.08.2026): print-in-place — ein Scharnier, das schon beim Drucken
    beweglich ist. Hier hält kein Träger die Teile zusammen, sie sollen
    getrennt bleiben. Geprüft wird deshalb nicht *ob* der Baustein zerfällt,
    sondern **ob er in so viele Teile zerfällt, wie er erklärt hat**: Zwei
    statt zwei ist die Zusage, drei statt zwei ist ein Fehler wie jeder andere.
    Unerklärtes Zerfallen bleibt damit rot — die Prüfung wird nicht schwächer,
    sondern genauer.

    ``wall`` macht die Mindestwand zum Vertrag statt zur Namenssonderregel:
    Profilgrenze, benannter Geometrieparameter oder eine fachlich begründete
    Nichtanwendbarkeit. ``features`` nennt ebenso, welches Merkmal in welcher
    Parameterstellung vorkommen muss. Ohne diese Deklaration werden vorhandene
    Merkmale weiterhin auf ID, Herkunft und Maße geprüft.

    ``build`` ist, was aus Werten einen Körper macht — für ein Rezept die
    Auswertung, für eine ``.py`` ihre Funktion. Ein Fehlschlag bricht nicht ab:
    Der Kunde soll **alle** brechenden Ecken sehen, nicht je Lauf eine.

    Abbruch ist Abbruch (§15.6): Was bis dahin geprüft ist, kommt zurück,
    und ``checked`` sagt ehrlich, wie weit es kam — ein abgebrochener Lauf
    sieht nie wie ein bestandener aus, denn ``passed`` verlangt Fehlerfreiheit
    **über alle** Ecken, und die Zahl steht daneben.
    """
    from app.core.geom.mesh import as_mesh_data

    token = cancelled or _Silent()
    plan = corners(params, limit, (mirrored_by,) if mirrored_by else ())
    first = 0
    if window is not None:
        first = max(0, window[0])
        plan = plan[first : max(first, window[1])]
    failures: list[RangeFailure] = []
    excluded: list[RangeExclusion] = []
    checked = 0

    def announce(index: int, phase: int) -> None:
        if progress is None:
            return
        progress(
            (index * 4 + phase) / (len(plan) * 4),
            str(_("Bereichstest, Ecke {n} von {total}")).format(n=index + 1, total=len(plan)),
        )

    def add(values: dict[str, Any], reason: str) -> None:
        failures.append(RangeFailure(dict(values), reason[:200]))

    for index, values in enumerate(plan):
        if _is_cancelled(token):
            break
        announce(index, 0)
        # **Das Spiel kommt aus dem Profil, wie im Einsatz.** Ein Baustein
        # deklariert ``play`` und lässt es auf null; ``insert_part`` setzt dort
        # ``profile.material.clearance`` ein (``ops.py``, Regel 7). Der
        # Bereichstest tat das nicht und fuhr damit einen Zustand, den es nie
        # gibt: beim Bolzenscharnier ein Gelenk mit einer Hundertstel Spalt,
        # das beim Drucken verschweißt. Geprüft wurde eine Geometrie, die
        # niemand bekommt.
        entered = dict(values)
        if PLAY_FIELD in entered and not entered[PLAY_FIELD]:
            entered[PLAY_FIELD] = profile.material.clearance
        try:
            instance = params(**entered)
            declared = str(feasible(instance) or "") if feasible is not None else ""
            try:
                result: PartResult = build(instance)
            except ValidationError:
                if not declared:
                    raise
                excluded.append(RangeExclusion(dict(entered), declared[:200]))
                if mirrored_by and not _mirror_excluded(params, build, entered, mirrored_by):
                    add(entered, _mirror_failure(mirrored_by))
                checked += 1
                announce(index, 4)
                if checked % 16 == 0:
                    _collect_on_main_thread()
                continue
            if declared:
                add(
                    entered,
                    str(_("als nicht baubar erklärt, baut aber: {reason}")).format(reason=declared),
                )
            announce(index, 1)
            if _is_cancelled(token):
                break

            mesh = as_mesh_data(result.mesh)
            if mirrored_by:
                problem = _mirror_problem(params, build, entered, mirrored_by, result, mesh)
                if problem is not None:
                    add(entered, problem)
            if not mesh.is_watertight:
                add(entered, str(_("nicht geschlossen")))
            if mesh.volume <= 0.0:
                add(entered, str(_("kein Volumen")))
            if not joined_by_host and mesh.component_count != max(bodies, 1):
                # **Die erklärte Zahl, nicht die Eins.** Wer nichts deklariert,
                # bekommt ``bodies=1`` und damit genau die alte Prüfung; wer zwei
                # erklärt, muss zwei bauen — auch das ist eine Zusage, die brechen
                # kann, und ein Scharnier, das in drei Teile fällt, ist genauso
                # kaputt wie eine Rastnase, die in zwei fällt.
                add(
                    entered,
                    str(_("zerfällt in {found} Teile statt {declared}")).format(
                        found=mesh.component_count, declared=max(bodies, 1)
                    ),
                )

            minimum = wall.minimum(entered, profile)
            measured = local_wall_thickness(mesh, token) if minimum is not None else None
            if _is_cancelled(token):
                break
            if minimum is not None:
                if measured is None:
                    add(entered, str(_("Wandstärke nicht messbar")))
                elif measured < minimum - EPS_GEOM:
                    add(
                        entered,
                        str(
                            _(
                                "dünner als druckbar: {measured} mm < {minimum} mm",
                                measured=f"{measured:.3f}",
                                minimum=f"{minimum:.3f}",
                            )
                        ),
                    )
            announce(index, 2)
            if _is_cancelled(token):
                break

            if mesh.is_watertight and mesh.volume > 0.0 and has_self_intersections(mesh, token):
                add(entered, str(_("Selbstdurchdringung")))
            if _is_cancelled(token):
                break
            announce(index, 3)

            gap = printable_gap(mesh, cancelled=token) if bodies > 1 else None
            if _is_cancelled(token):
                break
            if bodies > 1 and gap is None and mesh.component_count > 1:
                add(
                    entered,
                    str(
                        _(
                            "Der Abstand zwischen den Teilkörpern ist nicht messbar. "
                            "Die Geometrie reparieren und erneut prüfen."
                        )
                    ),
                )
            if (
                gap is not None
                # **``EPS_DISPLAY`` und nicht ``EPS_GEOM``**: Das hier ist eine
                # Fertigungsfrage, kein Rechenvergleich. Der gemessene Spalt fällt
                # um Bruchteile kleiner aus als der eingestellte, weil ein
                # facettierter Zylinder seine Sehne zeigt und nicht den Bogen —
                # gemessen 0,2499 bei eingestellten 0,25, und mit dem
                # Rechenepsilon meldete die Prüfung ein Scharnier, das genau
                # richtig gebaut war. Ein Hundertstel Millimeter liegt unter jeder
                # Druckauflösung; was darunter liegt, ist kein Spalt und kein
                # Fehler.
                and (gap < profile.material.clearance - EPS_DISPLAY)
            ):
                # **Der Spalt ist bei einem print-in-place-Teil die ganze Sache.**
                # Zu eng verschweißt beim Drucken, und aus zwei Körpern wird einer
                # — der Bereichstest sähe davon nichts, weil er die Geometrie vor
                # dem Drucker prüft und nicht danach. Gemessen wird gegen das
                # kalibrierte Material und nie gegen eine Zahl im Code (Regel 7).
                add(
                    entered,
                    str(_("Spalt {gap} mm — der Drucker legt {least} mm")).format(
                        gap=round(gap, 2), least=round(profile.material.clearance, 2)
                    ),
                )

            generated_features = getattr(result, "features", {})
            names = tuple(generated_features)
            for name, feature in generated_features.items():
                if feature.id != name:
                    add(
                        entered,
                        str(_("Merkmal {name}: ID {found} statt {expected}")).format(
                            name=name, found=feature.id, expected=name
                        ),
                    )
                if feature.provenance != "generated":
                    add(
                        entered,
                        str(_("Merkmal {name}: Herkunft {found} statt generated")).format(
                            name=name, found=feature.provenance
                        ),
                    )
                if not feature.params:
                    add(entered, str(_("Merkmal {name}: ohne Maße")).format(name=name))
                if features and not any(
                    requirement.applies(entered)
                    and (name == requirement.name or name.startswith(f"{requirement.name}_"))
                    for requirement in features
                ):
                    add(entered, str(_("Merkmal {name}: nicht deklariert")).format(name=name))
            for requirement in features:
                if requirement.applies(entered) and not any(
                    name == requirement.name or name.startswith(f"{requirement.name}_")
                    for name in names
                ):
                    add(
                        entered,
                        str(_("Merkmal {name}: fehlt")).format(name=requirement.name),
                    )

        except OperationCancelled:
            break
        except Exception as problem:  # Jede Prüfphase gehört zur betroffenen Ecke.
            if _is_cancelled(token):
                break
            add(entered, str(problem))

        checked += 1
        announce(index, 4)
        # VTK-Wrapper und native Manifold-Netze bilden Referenzzyklen. Ohne
        # periodischen Lauf sammelte die vollständige Bibliothek vor dem
        # ersten Gewinde bereits über ein Gigabyte an und wurde durch Paging
        # zwanzigmal langsamer. Die Paar- und Grenzmenge bleibt unverändert.
        # Nur im Hauptthread erzwingen: Der globale Sammler könnte sonst
        # auch GUI-Objekte aus fremden Referenzzyklen im Arbeiter zerstören.
        if checked % 16 == 0:
            _collect_on_main_thread()
    if checked < len(plan):
        add(
            {},
            str(
                _(
                    "Bereichstest abgebrochen: {checked} von {total} Kombinationen geprüft. "
                    "Starten Sie die Prüfung erneut, um den Rest zu prüfen.",
                    checked=checked,
                    total=len(plan),
                )
            ),
        )
    if progress is not None and checked == len(plan):
        progress(1.0, str(_("Bereichstest abgeschlossen")))
    report = RangeReport(checked=checked, failures=tuple(failures), excluded=tuple(excluded))
    _collect_on_main_thread()
    return report


#: Wie genau ein gespiegelter Baustein sein Vorbild treffen muss: Volumen relativ,
#: Dreiecke für den schnellen Weg und Flächenabstand in Millimetern. Beide
#: Stellungen entstehen aus demselben Netz, einmal an y = 0 gespiegelt; meist
#: liegen die Ecken auf 10⁻¹³ mm übereinander. Die Vereinigung danach darf anders
#: triangulieren (G 1/2: eine Ecke mehr auf einer Kante) und an einer Naht einen
#: Splitter anders auflösen: Am Bolzen Ø 1000 lag eine Ecke 0,32 µm neben der
#: gespiegelten Fläche, bei 20-8 NPT 0,019 µm (RM-544, 10.10.2026). Ein falscher
#: Drehsinn weicht um die Gangtiefe ab; die Druckgrenze trennt beides, und was
#: darunter abweicht, prüft die andere Stellung selbst (:func:`_mirror_problem`).
_MIRROR_VOLUME: Final = 1e-6
_MIRROR_TRIANGLES: Final = 10.0 * EPS_GEOM
_MIRROR_SURFACE: Final = PRINT_LIMIT


def _mirror_failure(field: str) -> str:
    return str(_("{field} spiegelt den Baustein nicht nur", field=field))


def _mirrored(values: dict[str, Any], field: str) -> dict[str, Any]:
    """Dieselbe Ecke in der anderen Stellung des Spiegelschalters."""
    return {**values, field: not bool(values.get(field, False))}


def _mirror_excluded(
    params: type[BaseParams], build: Any, values: dict[str, Any], field: str
) -> bool:
    """Ob eine erklärte Ausschlussecke auch in der anderen Stellung ausgeschlossen ist."""
    try:
        build(params(**_mirrored(values, field)))
    except ValidationError:
        return True
    return False


def _same_triangles(one: Any, other: Any) -> bool:
    """Ob zwei Netze aus denselben Dreiecken bestehen — bis auf Reihenfolge und Rundung.

    Der schnelle Weg der Spiegelprüfung: Meist ist das gespiegelte Netz Dreieck für
    Dreieck das andere (gemessen auf 10⁻¹³ mm), und dann liegen die Flächen
    aufeinander, ohne eine Abstandsrechnung über Millionen Ecken.
    """
    import numpy as np

    if len(one.faces) != len(other.faces):
        return False

    def ordered(body: Any) -> Any:
        corners = np.asarray(body.vertices, dtype=np.float64)[np.asarray(body.faces)]
        keys = np.round(corners / _MIRROR_TRIANGLES)
        inner = np.lexsort((keys[:, :, 2], keys[:, :, 1], keys[:, :, 0]), axis=-1)
        corners = np.take_along_axis(corners, inner[:, :, None], axis=1).reshape(-1, 9)
        rows = np.round(corners / _MIRROR_TRIANGLES)
        return corners[np.lexsort(rows.T[::-1])]

    return bool(np.max(np.abs(ordered(one) - ordered(other)), initial=0.0) <= _MIRROR_TRIANGLES)


def _mirror_problem(
    params: type[BaseParams],
    build: Any,
    values: dict[str, Any],
    field: str,
    result: PartResult,
    mesh: Any,
) -> str | None:
    """Ob die andere Stellung des Spiegelschalters an dieser Ecke nur spiegelt — sonst der Grund.

    Gebaut wird die andere Stellung; ihr Körper muss das Spiegelbild an y = 0
    sein: dasselbe Volumen, jede ihrer Ecken auf der gespiegelten Fläche und
    jede gespiegelte Ecke auf ihrer — die Netze dürfen anders trianguliert sein,
    die Flächen höchstens um die Druckgrenze anders liegen —, und dieselben
    Merkmale. Dreieck für Dreieck gleich ist sie wasserdicht, wandstark und frei
    von Selbstdurchdringung genau dann, wenn die geprüfte Stellung es ist; anders
    trianguliert prüft sie Dichtheit, Körperzahl und Selbstdurchdringung selbst,
    die Wand weicht höchstens um die Druckgrenze ab.
    """
    import numpy as np

    from app.core.geom.mesh import as_mesh_data, on_surface

    try:
        other = build(params(**_mirrored(values, field)))
    except Exception as problem:  # Wie jede Ecke: der Grund gehört in den Bericht.
        return str(problem)
    turned = as_mesh_data(other.mesh)
    if abs(turned.volume - mesh.volume) > _MIRROR_VOLUME * abs(mesh.volume):
        return _mirror_failure(field)
    flipped = mesh.raw.copy()
    flipped.vertices = np.asarray(flipped.vertices, dtype=np.float64) * np.array([1.0, -1.0, 1.0])
    if not _same_triangles(flipped, turned.raw):
        # Anders trianguliert: Dann muss jede Ecke auf der anderen Fläche liegen.
        for body, points in (
            (flipped, np.asarray(turned.raw.vertices, dtype=np.float64)),
            (turned.raw, np.asarray(flipped.vertices, dtype=np.float64)),
        ):
            _closest, distance, _triangle = on_surface(body, points)
            if len(distance) and float(np.max(distance)) > _MIRROR_SURFACE:
                return _mirror_failure(field)
        # Unter der Druckgrenze dürfen die Flächen auseinanderliegen; ob die andere
        # Stellung dicht, ganz und ohne Selbstdurchdringung ist, folgt daraus nicht
        # mehr, also prüft sie es selbst.
        if (
            not turned.is_watertight
            or turned.component_count != mesh.component_count
            or has_self_intersections(turned)
        ):
            return _mirror_failure(field)
    plain_features = getattr(result, "features", {})
    other_features = getattr(other, "features", {})
    if {name: feature.kind for name, feature in plain_features.items()} != {
        name: feature.kind for name, feature in other_features.items()
    }:
        return _mirror_failure(field)
    return None


def check_part(
    spec: PartSpec,
    profile: Profile,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
    window: tuple[int, int] | None = None,
) -> RangeReport:
    """Prüft einen Registerbaustein ausschließlich nach seiner Deklaration.

    ``window`` wie bei :func:`check`: ein Ausschnitt der Ecken für den Nachweis.
    """
    return check(
        spec.params,
        spec.fn,
        profile,
        progress=progress,
        cancelled=cancelled,
        joined_by_host=spec.joined_by_host,
        bodies=spec.bodies,
        wall=spec.wall,
        features=spec.feature_requirements,
        feasible=spec.feasible,
        limit=corner_limit(spec.source),
        mirrored_by=spec.mirrored_by,
        window=window,
    )
