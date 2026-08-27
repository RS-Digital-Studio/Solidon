"""Analysekarten (Bauplan §18.4).

Sieben Arten, denselben Körper anzusehen: wie dick er ist, wo er überhängt, wo
das Netz kaputt ist, wie er sich krümmt, was die Erkennung aus ihm gemacht
hat, an welchen Passungen er beteiligt ist, und wo Stützen wachsen werden.

Die Karten werden hier gerechnet, nicht im Viewport. Die Oberfläche braucht
nur die Zahlen, den Bereich und die Einheit — sie malt sie mit der Rampe aus
§19.1 und zeichnet die Legende. Das hält die Karten ohne Fenster testbar, und
es hält ``core`` frei von Qt.

Jede Zahl trägt ``source="internal"`` (§22.5). Eine Stützschätzung aus der
Schichtanalyse ist kein gemessener Wert aus G-Code, und die Legende sagt das.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final, Literal

import numpy as np
import trimesh
from shapely.geometry import Point
from shapely.geometry import Polygon as ShapelyPolygon

from app.core.errors import CANCEL, Action, UserError
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.rules import OVERHANG_LIMIT_DEGREES
from app.core.log import get_logger
from app.core.perceive.features import CURVATURE_LIMIT, pair_radii
from app.core.slice.analysis import cross_sections, slice_body
from app.core.types import (
    CancelToken,
    Feature,
    FeatureId,
    Finding,
    Fit,
    MetricSource,
    ObjectId,
    Profile,
    Scene,
    SceneObject,
    SliceResult,
    Vec3,
)
from app.core.units import DEGREE_UNIT
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

MapKind = Literal["wall", "overhang", "defects", "curvature", "features", "fits", "support"]

#: Darüber wird eine Karte abgelehnt statt minutenlang gerechnet (§31). Die
#: Karten schießen einen Strahl je Dreieck, und diese Kosten wachsen mit dem
#: Quadrat des Netzes.
MAP_LIMIT_TRIANGLES = 120_000

#: Nach so vielen Dreiecken wird gefragt, ob abgebrochen werden soll. Bei
#: 512 liegt der Abstand zwischen zwei Fragen unter einer Millisekunde — fein
#: genug, dass ein Kartenwechsel sofort wirkt, grob genug, dass die Frage
#: selbst nicht ins Gewicht fällt.
CANCEL_EVERY = 512

#: Wie weit über der Mindestwandstärke die Skala der Wandstärkenkarte endet.
#: Fünf mal zwei Extrusionsbreiten sind das Zehnfache einer Bahn — darüber
#: lautet die Antwort ohnehin „dick genug", und jede Farbstufe, die dort
#: verbraucht wird, fehlt unten, wo die Entscheidung fällt.
WALL_SCALE_FACTOR = 5.0

#: Flächenkategorien der Defektkarte, in der Reihenfolge ihrer Werte.
#:
#: Übersetzbar, und das war es sechs Texte lang nicht: Die Stufen standen als
#: feste deutsche Zeichenketten hier und liefen an ``tr()`` vorbei bis in die
#: Legende (Regel 20). Aufgelöst wird erst beim Bauen der Karte
#: (:func:`_named`) — beim Import steht die Sprache noch nicht fest.
DEFECT_LEVELS: Final = (_("in Ordnung"), _("offene Kante"), _("Non-Manifold"))

#: Flächenkategorien der Passungskarte, ebenso übersetzbar.
FIT_LEVELS: Final = (_("unbeteiligt"), _("Teil einer Passung"), _("Passung verletzt"))


def _named(levels: tuple[TranslatableText, ...]) -> tuple[str, ...]:
    """Die Stufen einer Karte in der eingestellten Sprache.

    Aufgelöst im Kern und nicht in der Legende, weil ``categories`` neben
    Stufennamen auch Provenienz-IDs trägt (``hole_3``) — die Legende bekommt
    Zeichenketten, und was übersetzt gehört, ist hier schon übersetzt.
    Dieselbe Stelle, an der :func:`feature_map` seit je ``str(_("ohne
    Merkmal"))`` schreibt.
    """
    return tuple(str(level) for level in levels)


@dataclass(frozen=True, slots=True)
class AnalysisMap:
    """Eine Karte über die Dreiecke eines Körpers.

    ``values`` hält eine Zahl je Dreieck. ``nan`` heißt „kann ich nicht sagen" —
    ein Strahl, der den Körper verlassen hat, ohne etwas zu treffen, ist keine
    Dicke von null.
    """

    kind: MapKind
    title: TranslatableText | str
    values: tuple[float, ...]
    unit: str
    low: float
    high: float
    highlighted: tuple[int, ...] = ()
    """Dreiecke, auf die die Karte hinweisen will: zu dünn, zu steil, gebrochen."""
    threshold: float | None = None
    """Ab wo hervorgehoben wird, in der Einheit der Karte."""
    categories: tuple[str, ...] = ()
    """Für Karten, deren Werte Stufen sind und keine Messwerte."""
    source: MetricSource = "internal"
    note: TranslatableText | str | None = None
    """Eine Zeile für die Legende, wenn die Zahl einen Vorbehalt braucht (§22.5)."""
    resolution: float | None = None
    """Rasterweite in mm, wo die Karte abgetastet statt genau gemessen wurde."""
    unknown_note: TranslatableText | str | None = None
    """Warum diese Karte an manchen Stellen nichts sagen kann — in drei Worten.

    Die Fußzeile zählte sie („17 mal nicht bestimmbar") und ließ die Zahl
    unerklärt stehen. Für jede Karte heißt es etwas anderes, also sagt es jede
    selbst; kurz genug, damit es in dieselbe Zeile passt."""

    @property
    def known(self) -> tuple[float, ...]:
        return tuple(value for value in self.values if not math.isnan(value))

    @property
    def unknown_count(self) -> int:
        return sum(1 for value in self.values if math.isnan(value))


class MapTooLarge(UserError):
    """Der Körper hat mehr Dreiecke, als eine Karte abzulaufen bereit ist (§31).

    Ein ``UserError``, keine nackte ``Exception``: als solche fiel die Klasse
    durch die Regel-17-Prüfung in ``tests/test_errors.py`` — kein Vorschlag,
    kein Warum, und die Oberfläche konnte nur „zu groß" sagen. Die Antwort
    steht seit je in der Eingangsstufe: Dezimieren hilft.
    """

    default_title = _("Für eine Analysekarte ist dieses Modell zu groß.")
    default_suggestions = (
        Action(id="decimate_mesh", label=_("Dreiecke verringern."), primary=True),
        CANCEL,
    )

    def __init__(self, triangles: int = 0) -> None:
        super().__init__(
            detail=_("Die Karte läuft jedes Dreieck ab, und ihr Budget ist begrenzt (§31)."),
            values={"triangles": triangles, "limit": MAP_LIMIT_TRIANGLES},
        )
        self.triangles = triangles


TITLES: dict[MapKind, TranslatableText] = {
    "wall": _("Wandstärke"),
    "overhang": _("Überhang"),
    "defects": _("Netzfehler"),
    "curvature": _("Krümmung"),
    # „Merkmale" und nicht „Feature-Zuordnung": Die Begriffszuordnung aus
    # Bauplan §4.2 sagt Merkmal → feature, und die sechs Nachbarn heißen
    # Wandstärke, Überhang, Netzfehler, Krümmung, Passungen, Stützbedarf. Ein
    # halb englischer Name in dieser Reihe war der einzige.
    "features": _("Merkmale"),
    "fits": _("Passungen"),
    "support": _("Stützbedarf"),
}


def build(
    kind: MapKind,
    entry: SceneObject,
    *,
    profile: Profile | None = None,
    scene: Scene | None = None,
    cancelled: CancelToken | None = None,
) -> AnalysisMap:
    """Der eine Einstiegspunkt, den die Oberfläche benutzt; der Rest ist die
    Karte selbst.

    ``cancelled`` bricht ab, wo es sich lohnt: am Eingang und in der teuersten
    Schleife. Die Zusage steht in §18.4 — die Karten laufen im Hintergrund und
    sind abbrechbar —, und eingelöst hat sie niemand: Wer bei 51 000 Dreiecken
    (3,4 s gemessen) die Karte wechselte, wartete auf die erste, bevor die
    zweite überhaupt anfing.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    mesh = _mesh_of(entry)
    if mesh.triangle_count > MAP_LIMIT_TRIANGLES:
        raise MapTooLarge(mesh.triangle_count)

    if kind == "wall":
        return wall_thickness_map(mesh, profile.minimum_wall_thickness if profile else None)
    if kind == "overhang":
        return overhang_map(mesh)
    if kind == "defects":
        return defect_map(mesh)
    if kind == "curvature":
        return curvature_map(mesh, entry.features)
    if kind == "features":
        return feature_map(mesh, entry.features)
    if kind == "fits":
        return fit_map(mesh, entry, scene)
    return support_map(mesh, profile.printer.layer_height if profile else 0.2, cancelled)


def _mesh_of(entry: SceneObject) -> MeshData:
    """Die Dreiecke des Körpers — auch wenn er exakt ist.

    Hier stand ``raise TypeError("analysis maps need the trimesh backed
    mesh")``, mit dem Kommentar „heute nur ein Kern" daneben. Der Satz war
    richtig, als er geschrieben wurde, und ist mit dem B-Rep-Kern still falsch
    geworden: Ein STEP-Import ist ein exakter Körper, und wer an ihm eine
    Analysekarte wählte, bekam einen **Programmfehler** samt Fehlerbericht —
    für eine gewöhnliche Handlung (Robert, 27.08.2026, Absturzbericht
    S-20260826-594f0f).

    Der Weg von B-Rep zu Mesh steht jederzeit offen (§30): Die Karten rechnen
    auf der Tessellation, wie jede Mesh-Operation an einem exakten Körper.
    ``as_mesh_data`` weist einen Körper, der wirklich keiner der beiden Kerne
    ist, mit einer lesbaren Meldung ab — nicht mit einem ``TypeError``.
    """
    return as_mesh_data(entry.mesh)


# --- Das Voxelfeld, auf dem beide Abstandskarten leben --------------------------


@dataclass(frozen=True, slots=True)
class SolidField:
    """Der Körper als gefülltes Raster, plus der Abstand nach außen je Voxel.

    Beide Abstandskarten brauchen dieselben zwei Fragen beantwortet — „ist hier
    Material" und „wie weit ist es bis zur Oberfläche" — und beide Antworten
    sind auf einem Raster weit billiger als mit einem Strahl je Dreieck: ein
    Strahl je Dreieck wächst mit dem Quadrat des Netzes, das hier wächst mit
    dem Volumen und schert sich nicht darum, wie fein das Netz ist.

    Das Raster kommt aus denselben Querschnitten, die die Schichtanalyse
    benutzt (§22.1), nicht aus einer Netzunterteilung — eine Platte aus zwölf
    großen Dreiecken bräuchte Minuten zum Unterteilen und braucht
    Millisekunden zum Schneiden.

    Der Preis ist die Auflösung: alles, was aus diesem Feld gelesen wird, ist
    auf ``pitch`` quantisiert, und die Legende sagt das, statt etwas anderes
    vorzugeben.
    """

    filled: Any
    origin: Any
    """Weltposition des Voxels (0, 0, 0)."""
    pitch: float


#: Feiner als so viele Schritte entlang der Diagonale wird das Raster nie. Ein
#: feineres Gitter kauft Genauigkeit, die niemand drucken kann, und kostet
#: Speicher, den niemand ausgeben will.
MAX_GRID_STEPS = 300


def solid_field(mesh: MeshData, pitch: float | None = None) -> SolidField:
    """Rastert den Körper: welche Zellen Material halten und welche nicht."""
    import shapely

    step = pitch if pitch is not None else default_pitch(mesh)
    low = np.asarray(mesh.bounds.minimum, dtype=float) - step
    high = np.asarray(mesh.bounds.maximum, dtype=float) + step
    # Ringsum eine leere Zelle, damit ein Lauf, der den Körper verlässt, immer
    # auf etwas Leerem landet, statt vom Raster zu fallen.
    axes = [np.arange(low[axis], high[axis] + step, step) for axis in range(3)]
    filled = np.zeros(tuple(len(axis) for axis in axes), dtype=bool)

    grid_x, grid_y = np.meshgrid(axes[0], axes[1], indexing="ij")
    flat_x, flat_y = grid_x.ravel(), grid_y.ravel()
    # Jede Höhe in einem Durchgang. Schicht für Schicht zu schneiden lief alle
    # Dreiecke einmal je Schicht ab — dreihundert Schichten eines Körpers mit
    # dreihunderttausend Dreiecken sind die Stelle, an der die Wandkarte die
    # meiste Zeit verbrachte.
    for index, shape in enumerate(cross_sections(mesh, axes[2])):
        if shape is None or shape.is_empty:
            continue
        inside = shapely.contains_xy(shape, flat_x, flat_y)
        filled[:, :, index] = inside.reshape(grid_x.shape)

    return SolidField(
        filled=filled,
        origin=np.array([axis[0] for axis in axes], dtype=float),
        pitch=step,
    )


def default_pitch(mesh: MeshData, extrusion_width: float = 0.42) -> float:
    """Eine halbe Extrusionsbreite, aber nie mehr Schritte, als das Raster
    zulässt.
    """
    diagonal = float(mesh.bounds.diagonal)
    return max(extrusion_width / 2.0, diagonal / MAX_GRID_STEPS)


def _indices(field: SolidField, points: Any) -> Any:
    """Weltpunkte als Rasterindizes, auf das Raster beschnitten."""
    raw = (np.asarray(points, dtype=float) - field.origin) / field.pitch
    indices = np.rint(raw).astype(int)
    upper = np.asarray(field.filled.shape) - 1
    return np.clip(indices, 0, upper)


# --- Wandstärke -----------------------------------------------------------------


def wall_thickness_map(
    mesh: MeshData, minimum: float | None = None, pitch: float | None = None
) -> AnalysisMap:
    """Die Dicke unter jedem Dreieck: einwärts entlang der Normalen bis zur
    gegenüberliegenden Wand.

    Dieselbe Frage, die das Messwerkzeug mit einem einzelnen Strahl beantwortet
    (§18.3) — eine Stelle anzuklicken und auf die Karte zu sehen gibt also
    dieselbe Zahl, bis auf das Raster, auf dem die Karte abgetastet ist. Wo der
    Lauf gar kein Material findet, ist der Wert ``nan``: eine offene Fläche hat
    keine Dicke, und null wäre eine Lüge.
    """
    body = mesh.raw
    if not len(body.faces):
        return AnalysisMap(
            kind="wall", title=TITLES["wall"], values=(), unit="mm", low=0.0, high=0.0
        )

    field = solid_field(mesh, pitch)
    thickness = _inward_thickness(body, field)

    highlighted: tuple[int, ...] = ()
    if minimum is not None:
        highlighted = tuple(
            int(index)
            for index, value in enumerate(thickness)
            if not math.isnan(value) and value < minimum
        )
    known = [value for value in thickness if not math.isnan(value)]
    top = max(known) if known else 0.0
    # **Die Skala wird gedeckelt.** An einer Stirnfläche misst der Strahl quer
    # durch das ganze Teil: bei einem Brett von 8 mm Dicke und 80 mm Länge
    # spannte die Legende über 80 mm, und der Bereich, um den es beim Drucken
    # geht — unter zwei Extrusionsbreiten —, fiel in eine einzige Farbstufe.
    # Die Karte konnte ihre eigene Frage nicht beantworten. Alles über dem
    # Deckel ist ohnehin dieselbe Aussage: dick genug.
    capped = min(top, minimum * WALL_SCALE_FACTOR) if minimum else top
    return AnalysisMap(
        kind="wall",
        title=TITLES["wall"],
        values=tuple(thickness),
        unit="mm",
        low=min(known) if known else 0.0,
        high=capped if capped > 0.0 else top,
        highlighted=highlighted,
        threshold=minimum,
        note=_(
            "Untergrenze sind zwei Extrusionsbreiten. Die Skala endet weit darüber; "
            "alles Dickere trägt dieselbe Farbe."
        )
        if minimum is not None and capped < top
        else _("Untergrenze sind zwei Extrusionsbreiten.")
        if minimum is not None
        else _("Auf einem Raster abgetastet."),
        resolution=field.pitch,
        unknown_note=_("kein Material gegenüber"),
    )


def _inward_thickness(body: trimesh.Trimesh, field: SolidField) -> list[float]:
    """Läuft von jedem Dreieck einwärts, bis das Material ausgeht."""
    centres = np.asarray(body.triangles_center, dtype=float)
    normals = np.asarray(body.face_normals, dtype=float)

    # Nichts kann dicker sein, als der Körper lang ist.
    steps = int(float(body.scale) / field.pitch) + 2
    reached = np.zeros(len(centres), dtype=float)
    inside = np.ones(len(centres), dtype=bool)

    for step in range(steps):
        points = centres - normals * (field.pitch * (step + 0.5))
        indices = _indices(field, points)
        here = field.filled[indices[:, 0], indices[:, 1], indices[:, 2]]
        # Hat ein Lauf das Material einmal verlassen, hört er auf zu zählen: was
        # jenseits der gegenüberliegenden Wand liegt, gehört zur nächsten Wand,
        # nicht zu dieser.
        inside &= here
        if not inside.any():
            break
        reached += inside

    values = reached * field.pitch
    return [float(value) if value > 0.0 else float("nan") for value in values]


# --- Überhang -------------------------------------------------------------------


def overhang_map(mesh: MeshData, limit: float = OVERHANG_LIMIT_DEGREES) -> AnalysisMap:
    """Winkel gegen die Baurichtung, null bei einer senkrechten Wand (§18.4).

    Eine Wand parallel zu Z ist 0°, eine Decke, die gerade nach unten schaut,
    90°. Nach oben schauende Dreiecke sind gar keine Überhänge — sie bleiben
    also bei null, statt negativ zu werden.
    """
    body = mesh.raw
    if not len(body.faces):
        return AnalysisMap(
            kind="overhang",
            title=TITLES["overhang"],
            values=(),
            unit=DEGREE_UNIT,
            low=0.0,
            high=0.0,
            threshold=limit,
        )

    downward = -np.asarray(body.face_normals, dtype=float)[:, 2]
    angles = np.degrees(np.arcsin(np.clip(downward, -1.0, 1.0)))
    angles = np.maximum(angles, 0.0)
    return AnalysisMap(
        kind="overhang",
        title=TITLES["overhang"],
        values=tuple(float(value) for value in angles),
        unit=DEGREE_UNIT,
        low=0.0,
        high=90.0,
        highlighted=tuple(int(index) for index in np.nonzero(angles > limit)[0]),
        threshold=limit,
        note=_("Über 45 Grad braucht die Fläche in aller Regel eine Stütze."),
    )


# --- Netzdefekte ----------------------------------------------------------------


def defect_map(mesh: MeshData) -> AnalysisMap:
    """Offene Kanten und nicht-mannigfaltige Kanten, je Dreieck (§18.4)."""
    body = mesh.raw
    values = np.zeros(len(body.faces), dtype=float)
    if len(body.faces):
        edges = np.asarray(body.edges_sorted)
        groups = trimesh.grouping.group_rows(edges, require_count=None)
        for group in groups:
            count = len(group)
            if count == 2:
                continue
            level = 1.0 if count == 1 else 2.0
            for edge in np.atleast_1d(np.asarray(group)):
                face = int(edge) // 3
                values[face] = max(values[face], level)

    return AnalysisMap(
        kind="defects",
        title=TITLES["defects"],
        values=tuple(float(value) for value in values),
        unit="",
        low=0.0,
        high=2.0,
        highlighted=tuple(int(index) for index in np.nonzero(values > 0.0)[0]),
        threshold=1.0,
        categories=_named(DEFECT_LEVELS),
    )


# --- Krümmung -------------------------------------------------------------------


def curvature_map(mesh: MeshData, features: dict[FeatureId, Feature] | None = None) -> AnalysisMap:
    """Der Radius, mit dem ein Dreieck gekrümmt ist — in Millimetern.

    **Vorher stand hier der schärfste Winkel zu einem Nachbarn, und das misst
    das Netz statt den Körper.** Der Docstring sagte es selbst: „Kanten stechen
    hervor, Verrundungen bleiben glatt." Genau das ist der Zweck einer
    Verrundung — je feiner sie vernetzt ist, desto kleiner der Winkel je
    Facette, obwohl der Radius derselbe bleibt. Eine Karte, deren Aussage an
    der Vernetzungsdichte hängt, beantwortet die Frage nicht, die §18.4 an sie
    stellt: *wie* rund, nicht *dass*.

    Gerechnet wird über :func:`app.core.perceive.features.pair_radii` — dieselbe
    Zahl, mit der die Erkennung ihre Flecken trennt. Was die Karte zeigt, ist
    damit genau das, wonach die Erkennung geht, und die Spalte *Nutzen* in
    §18.4 („Feature-Erkennung prüfen") stimmt wörtlich.

    **Drei Fälle, und zwei davon haben keinen Radius.** Eine ebene Fläche ist
    nicht unendlich rund, sie ist gar nicht rund — sie bekommt ``nan``, das in
    dieser Karte „kann ich nicht sagen" heißt. Eine **Kante** bekommt null und
    wird hervorgehoben: Die Formel gäbe dort 0,2 mm, eine Zahl, die nach einer
    sehr feinen Verrundung aussieht und keine ist.
    """
    body = mesh.raw
    values = np.full(len(body.faces), np.nan, dtype=float)
    pairs = np.asarray(body.face_adjacency)
    if not len(pairs):
        return _curvature_result(values, set(), _radii_from_features(values, features))

    degrees = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    radii = pair_radii(body)

    sharp: set[int] = set()
    for (first, second), radius, angle in zip(pairs, radii, degrees, strict=True):
        if angle >= CURVATURE_LIMIT:
            # **Eine Kante geht nicht in den Wert ein, sie wird markiert.** Sie
            # sagt nichts darüber, wie die Fläche gekrümmt ist, auf der das
            # Dreieck liegt — sie sagt, dass daneben eine andere anfängt. Der
            # kleinste Radius über *alle* Nachbarn, wie es die alte Karte mit
            # dem schärfsten Winkel tat, überschreibt jede Rundung: An einem
            # Zylinder grenzt **jedes** Manteldreieck an den Deckel, und die
            # ganze Wand käme als scharfe Kante heraus.
            sharp.update((int(first), int(second)))
            continue
        if not np.isfinite(radius):
            continue
        for index in (int(first), int(second)):
            # Unter den **glatten** Nachbarn gewinnt der kleinste: Wo eine
            # Fläche in zwei Richtungen verschieden gekrümmt ist, ist die
            # engere die, nach der gefragt wird.
            current = values[index]
            values[index] = float(radius) if math.isnan(current) else min(current, float(radius))

    exact = _radii_from_features(values, features)
    return _curvature_result(values, sharp, exact)


#: Woraus sich der Krümmungsradius eines Merkmals ablesen lässt, und mit
#: welchem Faktor. **Kein Kegel:** Sein Radius ändert sich über die Höhe, ein
#: einzelner Wert wäre dort für fast jedes Dreieck der falsche.
_FEATURE_RADIUS: Final[dict[str, tuple[str, float]]] = {
    "sphere": ("diameter", 0.5),
    "hole": ("diameter", 0.5),
    "pin": ("diameter", 0.5),
    "fillet": ("radius", 1.0),
    "torus": ("tube_diameter", 0.5),
}
"""

Der Torus stand hier bis zum 23.08.2026 als ``("minor_radius", 1.0)`` — **den
Schlüssel gibt es nicht**, das Merkmal führt ``tube_diameter``. Der Eintrag lief
ins ``continue`` und tat nichts.

Aufgefallen ist es niemandem, weil die Schätzung den Torus ohnehin auf 0,4 %
trifft: Er hat eine ausgezeichnete Hauptkrümmungsrichtung, und seine Vernetzung
folgt ihr. **Ein Eintrag, der nichts bewirkt, sieht dort genauso aus wie einer,
der wirkt** — gefunden hat es 3d-druck-64 beim Nachmessen, nicht ein Test.
``tests/test_maps.py`` prüft die Tabelle jetzt gegen die Merkmale des Korpus.
"""


def _radii_from_features(values: np.ndarray, features: dict[FeatureId, Feature] | None) -> set[int]:
    """Setzt den **gemessenen** Radius ein, wo die Erkennung einen kennt.

    **Die Erkennung hat recht, und das ist kein Zufall.** ``fit_sphere`` und
    Verwandte rechnen einen Ausgleich über *alle* Punkte des Merkmals; die
    Karte schätzt aus je einer einzelnen Nachbarschaft zweier Dreiecke. Eine
    einzelne Nachbarschaft kann schräg zur Hauptkrümmung liegen, eine
    Ausgleichsfläche nicht.

    **Bei einer Kugel liegt jede schräg**, und genau dort brach die Schätzung
    weg. Gemessen am 23.08.2026, Karte gegen Erkennung an den Dreiecken des
    Merkmals:

    ===================== ======== ============ ======= ========
    Korpus                Art      Erkennung    Karte   Abstand
    ===================== ======== ============ ======= ========
    sphere_socket.stl     sphere   7,969        7,211   -9,5 %
    post_with_fillet.stl  pin      6,000        5,996   -0,1 %
    post_with_fillet.stl  torus    2,994        2,992   -0,1 %
    block_with_rounded    fillet   2,999        2,998   -0,0 %
    torus_ring.stl        torus    4,957        4,937   -0,4 %
    ===================== ======== ============ ======= ========

    Zylinder, Verrundung und Torus haben eine ausgezeichnete
    Hauptkrümmungsrichtung, und ihre Vernetzung folgt ihr — es gibt
    Nachbarschaften, die quer liegen und exakt ``r`` liefern. Eine Kugel hat
    keine solche Richtung, und eine Icosphere ist obendrein **selbstähnlich
    verzerrt**: Die Dreiecke an den zwölf Ikosaeder-Ecken sind in jeder
    Auflösung anders geformt als die in der Flächenmitte. Deshalb verschwindet
    der Fehler auch bei 64-facher Verfeinerung nicht — er ist keine
    Diskretisierung, sondern ein Formfaktor der Vernetzung.

    Weder Median noch Perzentil helfen: gemessen liegt der Median am Torus bei
    +100,8 %, und bei p20 ist die Kugel immer noch -9,9 %.

    Gibt zurück, welche Dreiecke ihren Wert von der Erkennung haben — die Karte
    weist beide Herkünfte aus (§22.5).
    """
    if not features:
        return set()
    exact: set[int] = set()
    for feature in features.values():
        entry = _FEATURE_RADIUS.get(feature.kind)
        if entry is None:
            continue
        name, factor = entry
        measured = feature.params.get(name)
        if measured is None:
            continue
        radius = float(measured) * factor
        if radius <= 0.0:
            continue
        for index in feature.face_indices or ():
            if 0 <= int(index) < len(values):
                values[int(index)] = radius
                exact.add(int(index))
    return exact


def _curvature_result(values: np.ndarray, sharp: set[int], exact: set[int]) -> AnalysisMap:
    known = values[~np.isnan(values)]
    note = _(
        "Der Radius, mit dem eine Fläche gekrümmt ist. Hervorgehoben sind "
        "scharfe Kanten; ebene Flächen haben keinen Radius."
    )
    if exact:
        # **Zwei Herkünfte in einer Karte werden ausgewiesen** (§22.5), und zwar
        # in Worten — nicht über einen Farbton, den niemand ohne Legende deuten
        # kann (Regel 18).
        #
        # **Ohne Platzhalter**, obwohl eine Zahl hier gut stünde: Einen Text aus
        # dem Kern formatiert niemand nach, und ein ``{count}`` erschiene dem
        # Kunden mit geschweiften Klammern. ``tests/test_errors.py`` sucht im
        # ganzen Kern danach.
        note = _(
            "Der Radius, mit dem eine Fläche gekrümmt ist. Hervorgehoben sind "
            "scharfe Kanten; ebene Flächen haben keinen Radius. Wo ein Merkmal "
            "erkannt wurde, steht sein gemessenes Maß — sonst eine Schätzung aus "
            "den Nachbarflächen."
        )
    return AnalysisMap(
        kind="curvature",
        title=TITLES["curvature"],
        values=tuple(float(value) for value in values),
        unit="mm",
        low=float(known.min()) if len(known) else 0.0,
        high=float(known.max()) if len(known) else 0.0,
        highlighted=tuple(sorted(sharp)),
        note=note,
    )


# --- Was die Erkennung gesehen hat ----------------------------------------------


def feature_map(mesh: MeshData, features: dict[FeatureId, Feature]) -> AnalysisMap:
    """Jedes Merkmal auf einer eigenen Stufe — „verstehen, was die KI
    sieht" (§18.4).
    """
    body = mesh.raw
    values = np.zeros(len(body.faces), dtype=float)
    names: list[str] = [str(_("ohne Merkmal"))]

    for level, (feature_id, feature) in enumerate(sorted(features.items()), start=1):
        names.append(feature_id)
        for index in feature.face_indices:
            if 0 <= index < len(values):
                values[index] = float(level)

    return AnalysisMap(
        kind="features",
        title=TITLES["features"],
        values=tuple(float(value) for value in values),
        unit="",
        low=0.0,
        high=float(len(names) - 1),
        categories=tuple(names),
    )


# --- Passungen (§14) ------------------------------------------------------------


def fit_map(mesh: MeshData, entry: SceneObject, scene: Scene | None) -> AnalysisMap:
    """Welche Dreiecke an einer Passung teilnehmen, und welche davon verletzt
    sind.
    """
    body = mesh.raw
    values = np.zeros(len(body.faces), dtype=float)
    if scene is not None:
        violated = _violated_features(scene, entry.id)
        for fit in scene.fits:
            for reference in (fit.a, fit.b):
                if reference.object_id != entry.id:
                    continue
                feature = entry.features.get(reference.feature_id)
                if feature is None:
                    continue
                level = 2.0 if reference.feature_id in violated else 1.0
                for index in feature.face_indices:
                    if 0 <= index < len(values):
                        values[index] = max(values[index], level)

    return AnalysisMap(
        kind="fits",
        title=TITLES["fits"],
        values=tuple(float(value) for value in values),
        unit="",
        low=0.0,
        high=2.0,
        highlighted=tuple(int(index) for index in np.nonzero(values >= 2.0)[0]),
        threshold=2.0,
        categories=_named(FIT_LEVELS),
    )


def _violated_features(scene: Scene, object_id: ObjectId) -> set[FeatureId]:
    """Merkmale, die ein Passungsbefund benennt — der Prüfbericht ist die
    eine Quelle (§14).
    """
    names: set[FeatureId] = set()
    for finding in scene.report.findings:
        if not finding.code.startswith("fit."):
            continue
        if finding.object_id not in (None, object_id):
            continue
        names.update(finding.feature_ids)
    return names


def fits_of(scene: Scene, object_id: ObjectId) -> tuple[Fit, ...]:
    """Passungen, an denen ein Objekt teilnimmt — benutzt von Legende und
    Steckbrief.
    """
    return tuple(fit for fit in scene.fits if object_id in (fit.a.object_id, fit.b.object_id))


# --- Stützen (§22) --------------------------------------------------------------


def support_map(
    mesh: MeshData, layer_height: float = 0.2, cancelled: CancelToken | None = None
) -> AnalysisMap:
    """Wie hoch die Stützsäule unter jedem Dreieck wüchse.

    Das *Urteil* — braucht diese Stelle überhaupt Stützen — kommt aus der
    Schichtanalyse (§22): ein Dreieck zählt nur, wenn seine Mitte in den
    ungestützten Bereich einer Schicht fällt. Die *Höhe* ist der Abfall
    darunter. Beides sind Schätzungen dieser Anwendung, nie aus G-Code gemessene
    Zahlen (§22.5).
    """
    body = mesh.raw
    if not len(body.faces):
        return AnalysisMap(
            kind="support", title=TITLES["support"], values=(), unit="mm", low=0.0, high=0.0
        )

    result = slice_body(mesh, layer_height)
    regions = _overhang_regions(result)
    centres = np.asarray(body.triangles_center, dtype=float)
    field = solid_field(mesh)
    drops = _drop_below(mesh, field, centres)

    values = np.zeros(len(centres), dtype=float)
    marked: list[int] = []
    for index, centre in enumerate(centres):
        if cancelled is not None and index % CANCEL_EVERY == 0:
            # Die teuerste Schleife der sieben Karten: je Dreieck ein Punkt in
            # shapely. Nicht bei jedem Durchgang gefragt — der Abbruch ist eine
            # Sache von Millisekunden, das Prüfen einer von Nanosekunden, und
            # eine Million Abfragen kosten mehr als sie einbringen.
            cancelled.raise_if_cancelled()
        region = _region_at(regions, float(centre[2]), layer_height)
        if region is None or not _inside(region, float(centre[0]), float(centre[1])):
            continue
        values[index] = drops[index]
        marked.append(index)

    return AnalysisMap(
        kind="support",
        title=TITLES["support"],
        values=tuple(float(value) for value in values),
        unit="mm",
        low=0.0,
        high=float(values.max()) if len(values) else 0.0,
        highlighted=tuple(marked),
        note=_("Geschätzt aus der Schichtanalyse, nicht aus G-Code gemessen."),
        resolution=field.pitch,
    )


def _overhang_regions(result: SliceResult) -> list[tuple[float, list[Any]]]:
    """Schichthöhe und ihre ungestützten Konturen, als shapely-Formen."""
    regions: list[tuple[float, list[Any]]] = []
    for layer in result.layers:
        shapes = [
            ShapelyPolygon(polygon.outline, polygon.holes)
            for polygon in layer.overhangs
            if len(polygon.outline) >= 4
        ]
        if shapes:
            regions.append((layer.z, shapes))
    return regions


def _region_at(
    regions: list[tuple[float, list[Any]]], z: float, layer_height: float
) -> list[Any] | None:
    for height, shapes in regions:
        if abs(height - z) <= layer_height:
            return shapes
    return None


def _inside(shapes: list[Any], x: float, y: float) -> bool:
    point = Point(x, y)
    return any(shape.intersects(point) for shape in shapes)


def _drop_below(mesh: MeshData, field: SolidField, centres: Any) -> Any:
    """Wie weit es senkrecht nach unten bis zum nächsten Material geht — oder
    bis zur Druckplatte.

    Vom selben Raster abgelesen, das die Dickenkarte benutzt: in jeder Säule
    ist das höchste gefüllte Voxel unter dem Dreieck die Stelle, an der eine
    Stützsäule aufsetzte.
    """
    filled = field.filled
    height = filled.shape[2]
    ladder = np.arange(height).reshape(1, 1, height)
    # Höchstes gefülltes Voxel auf oder unter jeder Ebene, je Säule; -1, wo es
    # keines gibt.
    below = np.maximum.accumulate(np.where(filled, ladder, -1), axis=2)

    indices = _indices(field, centres)
    rows, columns, layers = indices[:, 0], indices[:, 1], indices[:, 2]
    # Zwei Voxel tiefer, damit das Dreieck nicht die Wand findet, auf der es sitzt.
    start = np.maximum(layers - 2, 0)
    landing = below[rows, columns, start]

    plate = float(mesh.bounds.minimum[2])
    to_plate = centres[:, 2] - plate
    to_surface = (layers - landing) * field.pitch
    return np.maximum(np.where(landing >= 0, to_surface, to_plate), 0.0)


# --- Wohin die Kamera fliegt ----------------------------------------------------


def focus_point(entry: SceneObject, analysis: AnalysisMap) -> Vec3 | None:
    """Die Mitte dessen, was die Karte hervorhebt — wohin die Kamera schauen
    soll (§18.4).
    """
    if not analysis.highlighted:
        return None
    mesh = _mesh_of(entry)
    centres = np.asarray(mesh.raw.triangles_center, dtype=float)
    picked = centres[list(analysis.highlighted)]
    middle = picked.mean(axis=0)
    return (float(middle[0]), float(middle[1]), float(middle[2]))


def location_of(entry: SceneObject, finding: Finding) -> Vec3 | None:
    """Wo ein Befund sitzt: an seinem eigenen Ort, oder in der Mitte seiner
    Merkmale.
    """
    if finding.location is not None:
        return finding.location
    mesh = _mesh_of(entry)
    centres = np.asarray(mesh.raw.triangles_center, dtype=float)
    named = [entry.features[key] for key in finding.feature_ids if key in entry.features]
    indices = [
        index for feature in named for index in feature.face_indices if 0 <= index < len(centres)
    ]
    if not indices:
        return None
    middle = centres[indices].mean(axis=0)
    return (float(middle[0]), float(middle[1]), float(middle[2]))


def map_for(finding: Finding) -> MapKind | None:
    """Welche Karte einen Befund erklärt — der kürzeste Weg von der Warnung
    zur Stelle (§18.4).
    """
    code = finding.code
    if code.startswith("fit."):
        return "fits"
    if code.startswith("perceive."):
        return "features"
    if code.startswith(("repair.", "ingest.", "mesh.")):
        return "defects"
    if "overhang" in code or code.startswith("orient."):
        return "overhang"
    if "wall" in code or "thin" in code:
        return "wall"
    if "support" in code:
        return "support"
    return None
