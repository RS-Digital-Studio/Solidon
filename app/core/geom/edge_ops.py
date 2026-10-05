"""Verrunden und Fasen — **eine** Handlung, zwei Rechenkerne (§25, §30).

Bis zum 10.09.2026 waren das zwei B-Rep-Operationen mit
``requires_kind="brep"``: Wer ein STL einlas, fand sie ausgegraut vor, mit
einem Satz im Tooltip, der erklärte, warum nicht. Das ist die Ordnung, die
Robert an diesem Tag aufgehoben hat — „alles soll immer bearbeitbar sein, egal
ob importiert Format egal und beim selbst zeichnen".

**Es bleibt trotzdem bei zwei Rechenwegen, und das ist keine Schwäche.** Der
exakte Kern kennt die Kante als Kurve und rundet sie als Kurve; das Netz kennt
sie als Zug von Segmenten und rundet sie mit einem Sehnenzug, dessen Feinheit
an :data:`~app.core.units.MAX_FACET_SAG` hängt. Gemessen am selben Quader mit
vier Verrundungen zu R = 3: 23845,49 mm³ exakt gegen 23839,05 am Netz, also
0,027 % Unterschied, und der steckt vollständig in den Kreisabschnitten unter
den Sehnen. **Bei der Fase gibt es gar keinen** — eine Fase ist eine Ebene,
und eine Ebene hat ein Netz exakt (gemessen: 23840,0000 gegen 23840,0000).

Was den Weg wählt, ist der Körper und nicht der Kunde. Ein Umschalter wie bei
den Zwillingspaaren (``MENU_TWINS``) wäre hier keiner: Ein Netz lässt sich
nicht exakt verrunden — der Rückweg zu einer Topologie existiert nicht (§30) —,
und ein exakter Körper hat keinen Grund für den gröberen Weg.

Die **Auswahl** der Kanten kennt den Unterschied ohnehin nicht: Ein Schlüssel
aus ``geom.edges.edge_key`` benennt dieselbe Kante in beiden Kernen, und die
Gruppen („alle senkrechten") rechnet ``geom.edges.wanted`` für beide.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast

from app.core.errors import (
    CANCEL,
    CORRECT_INPUT,
    MESH_AND_RETRY,
    SHOW_LOCATION,
    GeometryError,
    ValidationError,
)
from app.core.geom.boolean import BooleanOutcome, HasVolume
from app.core.geom.edges import (
    EDGE_CHOICES,
    ChamferShape,
    EdgeChoice,
    EdgeSides,
    MeshEdge,
    RadiusLaw,
    bead_edges,
    bevel_edges,
    chamfer_reaches,
    mesh_edge_sides,
    reference_first,
    round_edges,
)
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.registry import op_params, param, register_op
from app.core.types import (
    BaseParams,
    CancelToken,
    Finding,
    OpContext,
    OpResult,
    Profile,
    ProgressFn,
    SceneObject,
    Vec3,
)
from app.core.units import DEGREE_UNIT, EPS_GEOM, MAX_FACET_SAG, format_length
from app.i18n import _

#: Wie eine Fase bemaßt ist (P6.2): gleich breit, zwei Abstände, Abstand und Winkel.
CHAMFER_MODES: tuple[str, ...] = ("equal_distances", "two_distances", "distance_angle")

#: Wie der Radius einer Verrundung verläuft (P6.1): gleichbleibend oder mit Verlauf.
FILLET_MODES: tuple[str, ...] = ("constant_radius", "variable_radius")

#: Wie Zwischenstellen geschrieben werden — der Satz steht einmal, für den
#: ``doc``-Satz des Feldes und für jede Absage beim Lesen.
_STATIONS_HOW = _(
    "Weitere Radien entlang der Kante, je als „Stelle:Radius“ mit der Stelle in Prozent "
    "der Länge vom Anfang — etwa „50:4“ für 4 mm in der Mitte, mehrere durch "
    "Leerzeichen getrennt."
)

#: Dieselbe Auswahl bei Verrundung und Fase — deshalb steht der Satz einmal hier.
_CHOICE_DOC = _(
    "Welche Kanten gemeint sind — senkrechte, waagerechte, oben, unten, alle oder einzeln "
    "gewählte. Ein runder Rand gehört nur dazu, wenn er waagerecht liegt; eine Bohrung in "
    "einer Seitenwand wählen Sie einzeln."
)

#: Wie runde Ränder zu den Gruppen stehen (RM-279) — ein Satz für alle drei.
#: Er nennt den Namen, den die Beschriftung einer solchen Mündung zeigt: Sie
#: heißt „Senkrecht“ und gehört trotzdem zu keiner Gruppe (``edges.choose``).
_RINGS_DOC = _(
    "Ein runder Rand wie die Mündung einer Bohrung zählt nur zu waagerecht, oben oder "
    "unten, wenn er waagerecht liegt. In einer Seitenwand heißt er „Senkrecht“, gehört "
    "aber zu keiner Gruppe — wählen Sie ihn dann einzeln. Ohne Haken zählt jeder runde "
    "Rand als waagerecht, wie in Schritten aus älteren Versionen."
)

#: Und derselbe Satz zum Feld der einzeln gewählten Kanten.
_KEYS_DOC = _(
    "Die einzeln gewählten Kanten. Sie hängen an ihrer Lage am Körper, nicht an "
    "ihrer Nummer — ein Schritt davor darf etwas anderes ändern, ohne dass die "
    "Verrundung wandert."
)


def _rings_param() -> bool:
    """Das Feld „Runde Ränder nach ihrer Lage“ — gleich an allen drei Operationen."""
    return cast(
        bool,
        param(
            title=_("Runde Ränder nach ihrer Lage"),
            default=True,
            placement="advanced",
            doc=_RINGS_DOC,
            # „senkrecht“ nimmt an beiden Wegen dieselben Kanten.
            depends_on=("edges", ("horizontal", "top", "bottom")),
        ),
    )


def _chosen_edges(choice: str, value: str) -> tuple[str, ...]:
    """Die einzeln gewählten Kanten aus dem gespeicherten Wert (E4).

    Ein Text mit Leerzeichen dazwischen, wie ihn ``kind="edges"`` ablegt.
    Der Editor im Dialog setzt ihn zusammen; hier steht der eine Weg zurück,
    damit Verrundung und Fase ihn nicht zweimal verschieden lesen.

    **Und ``choice`` entscheidet, nicht der Inhalt.** Der Dialog graut das Feld
    aus, wenn eine Gruppe gewählt ist — er **löscht** es aber nicht, und das ist
    richtig so: Wer von „einzeln" auf „alle senkrechten" und zurück wechselt,
    soll seine Auswahl wiederfinden. Wer den Inhalt lesen würde statt der
    Auswahl, bekäme eine Gruppe, die stillschweigend zu drei Kanten wird.
    """
    if choice != "named":
        return ()
    return tuple(entry for entry in value.split() if entry)


@op_params
class FilletParams(BaseParams):
    radius: float = param(
        title=_("Radius"),
        default=2.0,
        unit="mm",
        minimum=0.01,
        maximum=100.0,
        doc=_(
            "Radius der Verrundung, bei einem Verlauf der Radius am Anfang der Kante. "
            "Größer als das dünnste angrenzende Material geht nicht — dann bleibt "
            "für die Rundung kein Platz."
        ),
    )
    # **P6.1 — Verrunden mit Verlauf.** Die Vorgabe bleibt der eine Radius;
    # jeder gespeicherte Schritt behält damit seine Bedeutung, und die drei
    # Felder darunter schweigen, solange der Verlauf gleichbleibend ist.
    mode: str = param(
        # **Nicht „Verlauf“**: Unter diesem Schlüssel steht in den Katalogen
        # der Verlauf der Schritte („History“) — derselbe deutsche Text wäre
        # englisch die falsche Sache.
        title=_("Radiusverlauf"),
        default="constant_radius",
        choices=FILLET_MODES,
        doc=_(
            "Ein Radius über die ganze Kante, oder ein Radius, der sich vom Anfang zum "
            "Ende und über Zwischenstellen ändert — etwa für einen Griff."
        ),
        placement="advanced",
    )
    end_radius: float = param(
        title=_("Radius am Ende"),
        default=4.0,
        unit="mm",
        minimum=0.01,
        maximum=100.0,
        doc=_(
            "Radius am Ende der Kante. Dazwischen ändert sich die Rundung gleichmäßig, "
            "mit Zwischenstellen als weicher Bogen durch alle Werte."
        ),
        depends_on=("mode", ("variable_radius",)),
        placement="advanced",
    )
    stations: str = param(
        title=_("Zwischenstellen"),
        default="",
        placement="advanced",
        doc=_STATIONS_HOW,
        depends_on=("mode", ("variable_radius",)),
    )
    reverse: bool = param(
        title=_("Anfang und Ende tauschen"),
        default=False,
        placement="advanced",
        doc=_(
            "Ohne Haken beginnt der Verlauf am linken Ende der Kante, bei gleicher Lage "
            "am vorderen, dann am unteren. Mit Haken beginnt er am anderen Ende."
        ),
        depends_on=("mode", ("variable_radius",)),
    )
    edges: str = param(
        title=_("Kanten"),
        default="vertical",
        choices=EDGE_CHOICES,
        doc=_CHOICE_DOC,
    )
    # **Aus nur für gespeicherte Schritte** (RM-279): Bis Format 36 zählte
    # jeder Ring als waagerecht, auch die Mündung einer Querbohrung, und die
    # Migration 36 → 37 schreibt ihnen den Haken aus, damit sie beim Öffnen
    # dieselben Kanten treffen.
    rings_by_plane: bool = _rings_param()
    edge_keys: str = param(
        title=_("Einzelne Kanten"),
        default="",
        kind="edges",
        placement="advanced",
        doc=_KEYS_DOC,
        depends_on=("edges", ("named",)),
    )


@register_op(
    name="fillet_edges",
    # 8: die Berührlinien werden an beiden Kernen geprüft, und eine Gruppe
    # lässt gefaltete Züge aus (22.09.2026).
    # 9: Radius mit Verlauf (P6.1, 23.09.2026).
    # 10: ein stehender Ring gehört zu keiner Gruppe nach Lage (RM-279).
    # 11: ein gebogener Zug am Netz wird durch seine Knoten gezogen (RM-279).
    # 12: an einer gemischten Ecke bleibt jede durchgereichte Ecke an ihrem
    # Weltort (RM-274).
    # 13: exakte Rundungsgruppen lassen einzeln nicht baubare Kanten gezielt aus (RM-284).
    # 14: Gruppen binden nur vollständig belegte native Kanten und erhalten alle Orte (RM-322).
    # 15: Gruppensuche je Kontur, Wand je Kontur, ein Befund für alle ausgelassenen Kanten,
    #     Bindung je native Kante, Engstellen in Kanten gezählt (RM-435, RM-412, RM-436).
    cache_version="15",
    title=_("Verrunden"),
    category="shaping",
    params=FilletParams,
    consumes=1,
    produces=1,
    doc=_(
        "Rundet die gewählten Kanten ab, mit einem Radius oder mit einem Verlauf vom "
        "Anfang zum Ende. Das geht an einem exakten Körper wie an einem Netz."
    ),
    # **Der zweite Teil des Vorbehalts ist gefallen** (22.09.2026). Er sagte,
    # das Netz nehme am 3-mm-Kasten noch 2 mm an, wo der exakte Körper
    # ablehnt — und das Netz nahm sie an, indem es die Wand still niedriger
    # schnitt. Seit beide Kerne dieselbe Frage stellen
    # (``edges.contact_band_limit``), lehnen beide ab, mit demselben Satz.
    caveat=_(
        "An einem Netz besteht die Rundung aus geraden Stücken statt aus einer "
        "Kurve. Sie weichen um weniger ab, als eine Düse auflöst; wer eine echte "
        "Kurve braucht, arbeitet an einem exakten Körper weiter."
    ),
)
def fillet_edges(ctx: OpContext) -> OpResult:
    params = cast(FilletParams, ctx.params)
    law = radius_law(params)
    return _worked(
        ctx,
        law.largest if law is not None else params.radius,
        cast(EdgeChoice, params.edges),
        _chosen_edges(params.edges, params.edge_keys),
        rounded=True,
        rings_by_plane=params.rings_by_plane,
        law=law,
    )


def radius_law(params: FilletParams) -> RadiusLaw | None:
    """Der Radiusverlauf aus den Parametern — ``None`` für den einen Radius (P6.1).

    Anfang und Ende kommen aus ``radius`` und ``end_radius``, dazwischen die
    Zwischenstellen aus ``stations``: ``Stelle:Radius``, die Stelle in Prozent
    der Kantenlänge, getrennt durch Leerzeichen oder Semikolon; Komma und
    Punkt gelten beide als Dezimalzeichen. Was sich so nicht lesen lässt, ist
    eine Absage mit dem Satz, wie es richtig heißt — nie eine stille Auswahl
    (Regel 21).
    """
    if params.mode != "variable_radius":
        return None
    spec = next(item for item in FilletParams.spec() if item.name == "radius")
    minimum = float(spec.minimum if spec.minimum is not None else 0.0)
    maximum = float(spec.maximum if spec.maximum is not None else math.inf)
    found: dict[float, float] = {}
    for entry in params.stations.replace(";", " ").split():
        place_text, colon, radius_text = entry.partition(":")
        try:
            place = float(place_text.replace(",", "."))
            radius = float(radius_text.replace(",", "."))
        except ValueError:
            place, radius = math.nan, math.nan
        if (
            not colon
            or not math.isfinite(place)
            or not math.isfinite(radius)
            or not 0.0 < place < 100.0
            or not minimum <= radius <= maximum
            or any(abs(place - known) <= EPS_GEOM * 100.0 for known in found)
        ):
            raise ValidationError(
                "stations",
                _(
                    "Die Zwischenstelle „{entry}“ lässt sich nicht lesen. Die Stelle liegt "
                    "zwischen 0 und 100 Prozent und kommt nur einmal vor, der Radius liegt "
                    "zwischen {low} und {high}. {how}",
                    entry=entry,
                    low=format_length(minimum),
                    high=format_length(maximum),
                    how=_STATIONS_HOW,
                ),
                value=params.stations,
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        found[place] = radius
    ordered = sorted(found)
    positions = (0.0, *(place / 100.0 for place in ordered), 1.0)
    radii = (float(params.radius), *(found[place] for place in ordered), float(params.end_radius))
    return RadiusLaw(positions, radii, reversed=bool(params.reverse))


@op_params
class ChamferParams(BaseParams):
    distance: float = param(
        title=_("Breite"),
        default=1.0,
        unit="mm",
        minimum=0.01,
        maximum=100.0,
        doc=_(
            "Wie weit die Fase die Kante zurücknimmt — auf beiden Flächen, oder bei zwei "
            "Abständen und bei Abstand und Winkel auf der Bezugsfläche."
        ),
    )
    # **P6.2 — Fasen mit zwei Abständen oder Abstand und Winkel.** Die
    # Vorgabe bleibt die gleiche Breite auf beiden Seiten; jede gespeicherte
    # Fase behält damit ihre Bedeutung.
    mode: str = param(
        title=_("Bemaßung"),
        default="equal_distances",
        choices=CHAMFER_MODES,
        doc=_(
            "Gleiche Breite auf beiden Flächen, zwei verschiedene Abstände oder ein "
            "Abstand mit dem Winkel der Fase zur Bezugsfläche."
        ),
        placement="advanced",
    )
    second_distance: float = param(
        title=_("Zweiter Abstand"),
        default=1.0,
        unit="mm",
        minimum=0.01,
        maximum=100.0,
        doc=_("Wie weit die Fase auf der zweiten Fläche zurücknimmt."),
        depends_on=("mode", ("two_distances",)),
        placement="advanced",
    )
    angle: float = param(
        title=_("Winkel"),
        default=45.0,
        unit=DEGREE_UNIT,
        minimum=1.0,
        maximum=89.0,
        doc=_(
            "Unter welchem Winkel die Fase zur Bezugsfläche steht. 45 Grad an einer "
            "rechtwinkligen Kante ist die gleiche Breite auf beiden Seiten."
        ),
        depends_on=("mode", ("distance_angle",)),
        placement="advanced",
    )
    flip_sides: bool = param(
        title=_("Seiten tauschen"),
        default=False,
        placement="advanced",
        doc=_(
            "Nimmt die andere Fläche als Bezugsfläche. Ohne Haken ist es die Fläche, die "
            "am weitesten nach oben zeigt, bei gleicher Höhe die hintere, dann die rechte."
        ),
        depends_on=("mode", ("two_distances", "distance_angle")),
    )
    edges: str = param(
        title=_("Kanten"),
        default="vertical",
        choices=EDGE_CHOICES,
        doc=_CHOICE_DOC,
    )
    # **Aus nur für gespeicherte Schritte** (RM-279): Bis Format 36 zählte
    # jeder Ring als waagerecht, auch die Mündung einer Querbohrung, und die
    # Migration 36 → 37 schreibt ihnen den Haken aus, damit sie beim Öffnen
    # dieselben Kanten treffen.
    rings_by_plane: bool = _rings_param()
    edge_keys: str = param(
        title=_("Einzelne Kanten"),
        default="",
        kind="edges",
        placement="advanced",
        doc=_KEYS_DOC,
        depends_on=("edges", ("named",)),
    )


@register_op(
    name="chamfer_edges",
    # 8: wie beim Verrunden (22.09.2026).
    # 9: zwei Abstände oder Abstand und Winkel (P6.2, 23.09.2026).
    # 10: der exakte Kern fragt die Flächen an einem Punkt auf der Kante statt
    # am Linienschwerpunkt — an Bögen und Kreisen (P6.2, 23.09.2026).
    # 11: ein stehender Ring gehört zu keiner Gruppe nach Lage (RM-279).
    # 12: ein gebogener Zug am Netz wird durch seine Knoten gezogen (RM-279).
    # 13: wie beim Verrunden (RM-274).
    # 14: dieselbe belegte Gruppenauswahl wie beim Verrunden (RM-322).
    # 15: Bindung je native Kante, Engstellen in Kanten gezählt, Absage mit Maß (RM-435, RM-436).
    cache_version="15",
    title=_("Fase anbringen"),
    category="shaping",
    params=ChamferParams,
    consumes=1,
    produces=1,
    doc=_(
        "Bricht die gewählten Kanten — gleich breit, mit zwei Abständen oder mit Abstand "
        "und Winkel, an einem exakten Körper wie an einem Netz."
    ),
    # Gemessen am 23.09.2026 am Quader 40 x 30 x 20, alle Kanten, 2 und 1 mm:
    # Netz 23 656,0 mm³ (ebene Ecke durch die drei Berührpunkte), exakter
    # Körper 23 655,0 (gewölbte Ecke) — bei Abstand und Winkel beide gleich.
    caveat=_(
        "Wo drei Fasen mit verschiedenen Abständen an einer Ecke zusammentreffen, "
        "schließt der exakte Körper die Ecke gewölbt und das Netz eben. Die Kanten "
        "selbst sind an beiden gleich."
    ),
)
def chamfer_edges(ctx: OpContext) -> OpResult:
    params = cast(ChamferParams, ctx.params)
    return _worked(
        ctx,
        params.distance,
        cast(EdgeChoice, params.edges),
        _chosen_edges(params.edges, params.edge_keys),
        rounded=False,
        rings_by_plane=params.rings_by_plane,
        shape=chamfer_shape(params),
    )


def chamfer_shape(params: ChamferParams) -> ChamferShape | None:
    """Die Form der Fase aus den Parametern — ``None`` für die gleiche Breite."""
    if params.mode == "two_distances":
        return ChamferShape(second=float(params.second_distance), flipped=bool(params.flip_sides))
    if params.mode == "distance_angle":
        return ChamferShape(angle=float(params.angle), flipped=bool(params.flip_sides))
    return None


@dataclass(frozen=True, slots=True)
class ChamferMark:
    """Wo eine Fase eine ihrer zwei Flächen zurücknimmt — für die Marke im Bild (P6.2).

    ``start`` liegt auf der Kante, ``end`` auf der Berührlinie der Fase in
    dieser Fläche; dazwischen liegen ``reach`` Millimeter in der Fläche.
    ``reference`` sagt, ob diese Fläche die Bezugsfläche ist — die, auf der
    die Breite gilt und zu der der Winkel steht. ``normal`` ist die Normale
    der Fläche an dieser Stelle, damit die Oberfläche sie auch in Worten
    nennen kann („oben", „rechts").
    """

    start: Vec3
    end: Vec3
    reach: float
    reference: bool
    normal: Vec3


def edge_sides(body: object, entry: object) -> EdgeSides | None:
    """Die zwei Flächen einer Kante an einem Punkt auf ihr — an beiden Kernen.

    ``entry`` ist die Kante, wie der Kern des Körpers sie beschreibt:
    ``brep.edit.EdgeInfo`` an einem exakten Körper, ``MeshEdge`` an einem
    Netz. ``None``, wo die Frage keine Antwort hat — eine entartete Kante,
    oder ein exakter Körper ohne OpenCASCADE.
    """
    if isinstance(entry, MeshEdge):
        return mesh_edge_sides(entry)
    try:
        from app.core.brep import edit
        from app.core.brep.kernel import Solid, available
    except ImportError:
        return None
    if not available() or not isinstance(body, Solid) or not isinstance(entry, edit.EdgeInfo):
        return None
    try:
        return edit.edge_sides(body, entry)
    except GeometryError:
        return None


def chamfer_marks(
    sides: EdgeSides,
    values: Mapping[str, object],
    parameter_values: Mapping[str, float] | None = None,
) -> tuple[ChamferMark, ChamferMark] | None:
    """Welche Fläche welche Rücknahme bekommt — die Bezugsfläche zuerst.

    ``values`` sind die Werte, die gerade im Merkmalfenster stehen, auch mit
    Ausdrücken (``=@breite``); sie werden mit ``parameter_values`` aufgelöst
    wie bei der Auswertung. Gerechnet wird mit denselben Zeilen wie beim Fasen
    (:func:`chamfer_shape`, :func:`~app.core.geom.edges.chamfer_reaches`) und
    denselben Normalen in derselben Folge — die Marke kann also nicht eine
    andere Fläche nennen als die Fase nimmt.

    ``None`` bei gleicher Breite (dort gibt es keine Bezugsfläche, die man
    sehen müsste) und bei Werten, aus denen keine Fase wird: ein ungültiger
    Ausdruck, ein Winkel, der die Gegenfläche verfehlt. Das sagt die Vorschau
    mit ihrem eigenen Satz; eine Marke dazu wäre eine zweite Meldung.
    """
    from app.core import expressions
    from app.core.errors import AppError

    try:
        resolved = expressions.resolve_params(dict(values), dict(parameter_values or {}))
        params = ChamferParams(
            **{
                name: resolved[name]
                for name in ("distance", "mode", "second_distance", "angle", "flip_sides")
                if name in resolved
            }
        )
        shape = chamfer_shape(params)
        if shape is None:
            return None
        one, two = chamfer_reaches(
            float(params.distance), shape, sides.one.normal, sides.two.normal
        )
    except AppError, TypeError, ValueError:
        return None
    reference_is_one = reference_first(sides.one.normal, sides.two.normal) != shape.flipped
    marks = [
        ChamferMark(
            start=sides.at,
            end=cast(
                Vec3,
                tuple(sides.at[axis] + reach * side.towards[axis] for axis in range(3)),
            ),
            reach=reach,
            reference=reference,
            normal=side.normal,
        )
        for side, reach, reference in (
            (sides.one, one, reference_is_one),
            (sides.two, two, not reference_is_one),
        )
    ]
    marks.sort(key=lambda mark: not mark.reference)
    return marks[0], marks[1]


@op_params
class BeadParams(BaseParams):
    radius: float = param(
        title=_("Radius"),
        default=1.5,
        unit="mm",
        minimum=0.01,
        maximum=100.0,
        doc=_("Wie dick die Leiste wird — der Radius des Rundstabs, der auf der Kante liegt."),
    )
    edges: str = param(
        title=_("Kanten"),
        default="vertical",
        choices=EDGE_CHOICES,
        doc=_CHOICE_DOC,
    )
    # **Aus nur für gespeicherte Schritte** (RM-279): Bis Format 36 zählte
    # jeder Ring als waagerecht, auch die Mündung einer Querbohrung, und die
    # Migration 36 → 37 schreibt ihnen den Haken aus, damit sie beim Öffnen
    # dieselben Kanten treffen.
    rings_by_plane: bool = _rings_param()
    edge_keys: str = param(
        title=_("Einzelne Kanten"),
        default="",
        kind="edges",
        placement="advanced",
        doc=_KEYS_DOC,
        depends_on=("edges", ("named",)),
    )


@register_op(
    name="bead_edges",
    result_kind="mesh",
    # 7: ein stehender Ring gehört zu keiner Gruppe nach Lage (RM-279).
    cache_version="7",
    title=_("Wulst anlegen"),
    category="shaping",
    params=BeadParams,
    consumes=1,
    produces=1,
    edges_on_mesh=True,
    doc=_(
        "Legt eine runde Leiste auf die gewählten Kanten — außen als Wulst, in "
        "einem Innenwinkel als Kehlnaht. Die glatte Hohlkehle macht dagegen "
        "*Verrunden* an derselben Kante."
    ),
    caveat=_(
        "Ein Wulst steht über den Körper hinaus und ändert damit sein Außenmaß. "
        "Wo es auf das Maß ankommt, gehört er nach innen oder gar nicht hin. "
        "Ein exakter Körper wird dabei zum Netz; seine Flächen und Kanten werden "
        "zu festen Dreiecken. Rückgängig stellt den exakten Körper wieder her."
    ),
)
def bead_edges_op(ctx: OpContext) -> OpResult:
    """Die Gegenrichtung zu Verrunden und Fase: Material kommt dazu.

    Der Wulst wird am tessellierten Körper vereinigt. Ein exakter Eingang
    kommt deshalb als Netz zurück; Einschränkung und Ergebnisbefund benennen
    den Verlust der exakten Geometrie.
    """
    params = cast(BeadParams, ctx.params)
    source = ctx.inputs[0]
    body = as_mesh_data(source.mesh)
    outcome = bead_edges(
        body,
        params.radius,
        cast(EdgeChoice, params.edges),
        _chosen_edges(params.edges, params.edge_keys),
        selected_edges=ctx.bound_edges.get("edge_keys"),
        rings_by_plane=params.rings_by_plane,
        quality=ctx.quality,
        cancelled=ctx.cancelled,
    )
    empty = _too_small_to_see(body, outcome.mesh, ctx.profile, kind="bead")
    conversion = []
    if source.kind == "brep":
        from app.core.brep.ops import converted_finding

        conversion.append(converted_finding(source, outcome.mesh))
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, kind="mesh", features={})],
        solver=outcome.solver,
        findings=[
            dataclasses.replace(entry, object_id=source.id)
            for entry in [*outcome.findings, *conversion, empty]
            if entry is not None
        ],
    )


def _worked(
    ctx: OpContext,
    size: float,
    choice: EdgeChoice,
    keys: tuple[str, ...],
    *,
    rounded: bool,
    rings_by_plane: bool = True,
    shape: ChamferShape | None = None,
    law: RadiusLaw | None = None,
) -> OpResult:
    """Der gemeinsame Rumpf beider Operationen — der Körper wählt den Kern.

    Gefragt wird ``kind`` und nicht der Typ des Netzes: Das ist dieselbe
    Auskunft, die das Register unter ``requires_kind`` prüft, und sie kostet
    keinen Import in den optionalen Kern.
    """
    source = ctx.inputs[0]
    # Die von der Auswertung gebundene Auswahl (``bound_edges``) geht vor:
    # Sie ist die bestätigte Antwort auf einen Schlüssel, der zwei Kanten traf,
    # und ein Schlüssel hier würde wieder zwei treffen. Ohne sie — direkter
    # Aufruf, Gruppenauswahl — gilt der Schlüsselweg wie bisher.
    bound = ctx.bound_edges.get("edge_keys")
    if source.kind == "brep":
        return _on_a_solid(
            source,
            size,
            choice,
            keys,
            selected_edges=bound,
            rings_by_plane=rings_by_plane,
            profile=ctx.profile,
            rounded=rounded,
            cancelled=ctx.cancelled,
            shape=shape,
            law=law,
            progress=ctx.progress,
        )

    body = as_mesh_data(source.mesh)
    if not rounded:
        outcome = bevel_edges(
            body,
            size,
            choice,
            keys,
            selected_edges=bound,
            rings_by_plane=rings_by_plane,
            quality=ctx.quality,
            cancelled=ctx.cancelled,
            narrowest=narrowest_face(ctx.profile),
            shape=shape,
        )
        return _edge_result(ctx, source, body, outcome, rounded=False)
    work = round_edges
    # **Abbrechbar, weil es dauern kann.** Gemessen an einer Lochplatte mit
    # 60 Bohrungen (7932 Dreiecke, 132 Kantenzüge): 2,7 s für die Fase über
    # alle Kanten, 6,9 s für die Verrundung. Ohne das Token liefe der Klick
    # auf *Abbrechen* ins Leere (§15.6).
    outcome = work(
        body,
        size,
        choice,
        keys,
        selected_edges=bound,
        rings_by_plane=rings_by_plane,
        quality=ctx.quality,
        cancelled=ctx.cancelled,
        narrowest=narrowest_face(ctx.profile),
        law=law,
    )
    return _edge_result(ctx, source, body, outcome, rounded=rounded)


def _edge_result(
    ctx: OpContext,
    source: SceneObject,
    body: MeshData,
    outcome: BooleanOutcome,
    *,
    rounded: bool,
) -> OpResult:
    """Das Ergebnis am Netz — gleich für Rundung und Fase."""
    empty = _too_small_to_see(
        body, outcome.mesh, ctx.profile, kind="fillet" if rounded else "chamfer"
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features={})],
        # Beide Handlungen fahren bis zu zwei Boolesche Schnitte; welche Stufe
        # sie gelöst hat, gehört in den Bericht und nicht ins Vergessen (§17.2).
        solver=outcome.solver,
        findings=[
            dataclasses.replace(entry, object_id=source.id)
            for entry in [*outcome.findings, empty]
            if entry is not None
        ],
    )


def _exact_group_skipped_finding(
    outline: tuple[tuple[Vec3, Vec3], ...], skipped: int, worked: int
) -> Finding:
    """Nennt die Kanten, die eine Gruppe am exakten Körper auslassen musste — alle mit Ort.

    **Ein Befund für alle**, mit dem Umriss jeder Kante (``outline``): Einer je
    Kante bündelte das Fenster ab zweien zu einer Zeile ohne Ort, und der Kunde
    musste raten, welche Kanten scharf blieben (RM-412). *Stelle zeigen*
    umrandet sie alle. Der Satz nennt den Weg, nicht die Bibliothek.
    """
    return Finding(
        code="edges.exact_group_skipped",
        severity="warning",
        message=_(
            "Einige Kanten dieser Auswahl sind nicht verrundet: Der exakte Kern konnte die "
            "Rundung dort nicht bilden. Die übrigen Kanten sind verrundet. Soll die Rundung "
            "auch dort sitzen, versuchen Sie einen kleineren Radius, verrunden Sie diese "
            "Kanten in einem eigenen Schritt, oder beenden Sie die Flächenbearbeitung."
        ),
        values={"skipped": skipped, "worked": worked},
        location=outline[0][0],
        outline=outline,
        # Am Netz rundet derselbe Schritt auch, was der exakte Kern nicht baut —
        # am Crimper eine 20-mm-Kante, deren Kontur durch einen tangential
        # auslaufenden Knick läuft (RM-435).
        suggestions=(SHOW_LOCATION, CORRECT_INPUT, MESH_AND_RETRY),
    )


def _thin_wall_finding(
    outline: tuple[tuple[Vec3, Vec3], ...], skipped: int, worked: int, size: float, wall: float
) -> Finding:
    """Nennt die Kanten einer Gruppe, deren Wand nicht dicker ist als der Radius.

    Die Gruppe lässt sie vor dem Bau aus, statt ganz abzusagen
    (``brep.edit.fillet_group``); darunter passt der Radius dort. Derselbe Bau
    wie ``edges.too_narrow``: Ort aller Kanten, Maß, Weg.
    """
    return Finding(
        code="edges.thin_wall",
        severity="warning",
        message=_(
            "Einige Kanten dieser Auswahl sind nicht verrundet: Die Wand neben ihnen ist nicht "
            "dicker als dieser Radius. Dort passt nur ein Radius unter {largest}. Die übrigen "
            "Kanten sind verrundet. Soll die Rundung auch dort sitzen, wählen Sie einen "
            "kleineren Radius.",
            largest=format_length(max(wall, 0.0)),
        ),
        values={
            "skipped": skipped,
            "worked": worked,
            "size_mm": round(size, 3),
            "largest_mm": round(max(wall, 0.0), 3),
        },
        location=outline[0][0],
        outline=outline,
        suggestions=(SHOW_LOCATION, CORRECT_INPUT),
    )


def _on_a_solid(
    source: SceneObject,
    size: float,
    choice: EdgeChoice,
    keys: tuple[str, ...],
    *,
    selected_edges: Sequence[int] | None = None,
    rings_by_plane: bool = True,
    profile: Profile | None,
    rounded: bool,
    cancelled: CancelToken,
    shape: ChamferShape | None = None,
    law: RadiusLaw | None = None,
    progress: ProgressFn | None = None,
) -> OpResult:
    """Der exakte Weg — träge geholt, weil OpenCASCADE optional ist (§36).

    Ein Rechner ohne den Kern hat auch keinen Körper der Art ``brep`` in der
    Szene; dieser Zweig wird dort nie betreten, und der Import darf deshalb
    nicht beim Laden des Registers stattfinden.
    """
    from itertools import pairwise

    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid

    narrow: list[Finding] = []
    # **Gefragt war die Gruppe, nicht die belegten Kanten**: Eine Absage erklärt
    # sich über alle Züge der Auswahl (``_why_it_does_not_fit``) und nennt das
    # größte passende Maß. Mit den belegten Kanten fragte sie nie (RM-435 M1).
    asked = selected_edges
    group_was_fitted = False
    if selected_edges is None and not keys and choice != "named":
        fitted = _group_that_fits(
            source,
            size,
            choice,
            rounded=rounded,
            narrowest=narrowest_face(profile),
            shape=shape,
            law=law,
            rings_by_plane=rings_by_plane,
            cancelled=cancelled,
        )
        selected_edges, narrow = fitted
        group_was_fitted = True

    def with_places(error: GeometryError) -> GeometryError:
        """Auch ein gescheiterter Gruppenbau behält alle ausgewählten Stellen."""
        if not group_was_fitted:
            return error
        outline = [segment for finding in narrow for segment in finding.outline]
        for edge in edit._edges_at(cast(Solid, source.mesh), selected_edges or ()):
            cancelled.raise_if_cancelled()
            outline.extend(pairwise(edit.edge_points(edge)))
        if outline:
            error.values.update(location=outline[0][0], outline=tuple(outline))
            error.object_id = source.id
            if SHOW_LOCATION not in error.suggestions:
                error.suggestions = (SHOW_LOCATION, *error.suggestions)
        return error

    exact_skipped: tuple[int, ...] = ()
    thin: tuple[int, ...] = ()
    thinnest = math.inf
    try:
        if rounded:
            if group_was_fitted and (law is None or law.constant):
                assert selected_edges is not None
                group = edit.fillet_group(
                    cast(Solid, source.mesh),
                    size,
                    selected_edges,
                    cancelled=cancelled,
                    progress=progress,
                )
                solid, exact_skipped, thin = group.solid, group.omitted, group.thin
                thinnest = group.thinnest
            else:
                solid = edit.fillet(
                    cast(Solid, source.mesh),
                    size,
                    choice,
                    keys,
                    selected_edges=selected_edges,
                    rings_by_plane=rings_by_plane,
                    cancelled=cancelled,
                    law=law,
                )
        else:
            solid = edit.chamfer(
                cast(Solid, source.mesh),
                size,
                choice,
                keys,
                selected_edges=selected_edges,
                rings_by_plane=rings_by_plane,
                shape=shape,
                cancelled=cancelled,
            )
    except GeometryError as refused:
        explained = _why_it_does_not_fit(
            source,
            size,
            choice,
            keys,
            asked,
            rounded,
            narrowest_face(profile),
            shape,
            law,
            rings_by_plane=rings_by_plane,
        )
        if explained is None:
            with_places(refused)
            raise
        raise with_places(explained) from refused
    if exact_skipped or thin:
        worked = max(0, len(selected_edges or ()) - len(exact_skipped) - len(thin))
        narrow = [
            dataclasses.replace(entry, values={**entry.values, "worked": worked})
            if "worked" in entry.values
            else entry
            for entry in narrow
        ]

        def outline_of(indices: Sequence[int]) -> tuple[tuple[Vec3, Vec3], ...]:
            return tuple(
                segment
                for edge in edit._edges_at(cast(Solid, source.mesh), indices)
                for segment in pairwise(edit.edge_points(edge))
            )

        if thin:
            narrow.append(_thin_wall_finding(outline_of(thin), len(thin), worked, size, thinnest))
        if exact_skipped:
            narrow.append(
                _exact_group_skipped_finding(outline_of(exact_skipped), len(exact_skipped), worked)
            )
    if narrow and cast(Solid, source.mesh).is_watertight and not solid.is_watertight:
        # **Eine verkleinerte Gruppe liefert keinen offenen Körper** (RM-279 (ii)).
        # Die Rundung prüft ``fillet_group`` selbst; diese Schranke bleibt für
        # die Fase, deren Gruppe in einem Bau entsteht.
        explained = _why_it_does_not_fit(
            source,
            size,
            choice,
            keys,
            asked,
            rounded,
            narrowest_face(profile),
            shape,
            law,
            rings_by_plane=rings_by_plane,
        )
        if explained is None:
            explained = GeometryError(
                detail=edit._too_large("fillet" if rounded else "chamfer"),
                suggestions=(CORRECT_INPUT, CANCEL),
                values={"size_mm": size, "edges": len(selected_edges or ())},
            )
        raise with_places(explained)
    empty = _too_small_to_see(source.mesh, solid, profile, kind="fillet" if rounded else "chamfer")
    # **Eine Rundung oder Fase legt keine Wendel an**: Trägt der Eingang kein
    # Gewinde, liest das Ergebnis keines (``known_threads=()``). Die Lesung
    # passte an ``pegboard-gs-100-v2.step`` nach „alle Kanten“ R 0,5 66 Achsen
    # an Rundungsränder an — über die Hälfte der Auswertung (RM-435).
    threaded = any(feature.kind == "thread" for feature in source.features.values())
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=solid,
                kind="brep",
                features=features_of(
                    solid, cancelled=cancelled, known_threads=None if threaded else ()
                ),
            )
        ],
        findings=[
            dataclasses.replace(entry, object_id=source.id)
            for entry in (*narrow, empty)
            if entry is not None
        ],
    )


def _group_that_fits(
    source: SceneObject,
    size: float,
    choice: EdgeChoice,
    *,
    rounded: bool,
    narrowest: float,
    shape: ChamferShape | None,
    law: RadiusLaw | None,
    rings_by_plane: bool,
    cancelled: CancelToken | None = None,
) -> tuple[tuple[int, ...], list[Finding]]:
    """Nur belegte und tragende Kanten; eine leere Gruppe sagt ausdrücklich ab.

    Dreiecksherkunft und der vollständige Kurvenverlauf belegen die native
    Kante. Fehlende Partner sind keine Aussage über Glattheit: Ein Knick
    innerhalb einer C0-Fläche hat ebenfalls keine eigene Topologiekante.
    Die Bandprüfung nimmt nur Kanten, die tatsächlich bearbeitet würden.
    """
    from itertools import pairwise

    from app.core.brep import edit
    from app.core.brep.kernel import Solid
    from app.core.geom.edges import contact_band_limits, edges_of, too_narrow_finding, wanted
    from app.core.units import weld_tolerance

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    solid = cast(Solid, source.mesh)
    mesh = as_mesh_data(solid)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    entries = edges_of(mesh)
    chosen = wanted(entries, choice, (), rings_by_plane=rings_by_plane)
    segments = edit.native_edges_of_segments(solid, mesh, chosen, cancelled=cancelled)
    bindings = [_bound_edges(claimed) for claimed in segments]
    bound = [entry for entry, binding in zip(chosen, bindings, strict=True) if binding]
    varying = law if law is not None and not law.constant else None
    try:
        limits = (
            contact_band_limits(
                entries,
                bound,
                size,
                rounded=rounded,
                tolerance=weld_tolerance(mesh.bounds.diagonal),
                narrowest=narrowest,
                shape=shape,
                law=varying,
            )
            if bound
            else {}
        )
    except GeometryError as refused:
        outline = tuple(segment for entry in chosen for segment in pairwise(entry.points))
        refused.values.update(location=outline[0][0], outline=outline)
        refused.object_id = source.id
        raise
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    # Eine native Kante kann auf mehrere Netzzüge verteilt sein. Trägt einer
    # das Maß nicht, darf kein anderer dieselbe ganze native Kante freigeben.
    narrow_indices = {
        index
        for entry, binding in zip(chosen, bindings, strict=True)
        if id(entry) in limits
        for index in binding
    }
    retained = segments
    if narrow_indices:
        available = [
            (position, entry)
            for position, entry in enumerate(chosen)
            if id(entry) not in limits and bindings[position]
        ]
        # Ein Zug kann mehr als eine native Kante tragen, eine native Kante auf
        # mehrere Züge verteilt sein. Ohne die Engstellen entscheidet die
        # Kurvenprüfung deshalb je Kante neu: Was ein schmaler Zug mit belegte,
        # ist jetzt unvollständig und fällt; die übrigen Kanten bleiben. Ein
        # indirekt verlorener Beleg ist keine gemessene Engstelle.
        rebound = edit.native_edges_of_segments(
            solid, mesh, [entry for _position, entry in available], cancelled=cancelled
        )
        by_position = dict(zip((position for position, _entry in available), rebound, strict=True))
        retained = tuple(
            by_position.get(position, (None,) * (len(entry.points) - 1))
            for position, entry in enumerate(chosen)
        )
    narrow: list[MeshEdge] = []
    unmapped: list[tuple[tuple[Vec3, Vec3], ...]] = []
    # Strecken eines tragenden Zugs auf einer Kante, die ein schmaler Zug
    # mitbelegt: Die Kante gibt es, sie ist nur anderswo zu schmal — das sagt
    # ``edges.too_narrow``, nicht „keine eigene Kante“.
    narrow_rest: list[tuple[Vec3, Vec3]] = []
    kept: dict[int, None] = {}
    for position, (entry, claimed) in enumerate(zip(chosen, retained, strict=True)):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if id(entry) in limits:
            narrow.append(entry)
            continue
        kept.update((index, None) for index in _bound_edges(claimed))
        first = segments[position]
        narrow_rest.extend(
            segment
            for before, after, segment in zip(first, claimed, pairwise(entry.points), strict=True)
            if after is None and before in narrow_indices
        )
        unmapped.extend(
            _unbound_pieces(
                entry,
                tuple(
                    after if after is not None or before not in narrow_indices else before
                    for before, after in zip(first, claimed, strict=True)
                ),
            )
        )
    if not kept:
        outline = tuple(segment for entry in chosen for segment in pairwise(entry.points))
        values = {"skipped": len(narrow_indices) + len(unmapped), "worked": 0, "size_mm": size}
        if not unmapped:
            from app.core.geom.edges import too_large_for_the_faces

            error = too_large_for_the_faces(
                size, min(limits.values()), rounded=rounded, varying=varying is not None
            )
        else:
            if narrow:
                largest = min(limits.values())
                values["largest_mm"] = largest
                detail = _(
                    "Keine Kante dieser Auswahl lässt sich mit diesem Maß bearbeiten. "
                    "Bei {narrow} Kanten sind die angrenzenden Flächen zu schmal; dort muss "
                    "das Maß unter {largest} liegen. An {unmapped} weiteren Stellen hat der "
                    "exakte Körper keine eigene Kante, etwa weil der Knick innerhalb einer "
                    "Fläche liegt. Verkleinern Sie das Maß, oder beenden Sie die "
                    "Flächenbearbeitung: Am Dreiecksmodell lassen sich diese Stellen bearbeiten.",
                    narrow=len(narrow_indices),
                    largest=format_length(max(largest, 0.0)),
                    unmapped=len(unmapped),
                )
            else:
                detail = _(
                    "An keiner der {count} ausgewählten Stellen hat der exakte Körper eine "
                    "eigene Kante, etwa weil der Knick innerhalb einer Fläche liegt. Der Körper "
                    "blieb unverändert. Am Dreiecksmodell lassen sich diese Stellen bearbeiten: "
                    "Beenden Sie dafür die Flächenbearbeitung.",
                    count=len(unmapped),
                )
            error = GeometryError(detail=detail)
        error.values.update(values)
        error.values.update(location=outline[0][0], outline=outline)
        error.object_id = source.id
        error.suggestions = (
            (SHOW_LOCATION, MESH_AND_RETRY, CORRECT_INPUT, CANCEL)
            if unmapped
            else (SHOW_LOCATION, CORRECT_INPUT, CANCEL)
        )
        raise error
    findings = []
    if narrow:
        outline = (
            *(segment for entry in narrow for segment in pairwise(entry.points)),
            *narrow_rest,
        )
        findings.append(
            dataclasses.replace(
                # Gezählt in nativen Kanten wie ``worked``: Am exakten Körper ist
                # die Kante die Einheit, die der Kunde wählt und sieht. Netzzüge
                # zählten an pb3041 zwei statt vierzehn (RM-436).
                too_narrow_finding(
                    len(narrow_indices),
                    min(limits.values()),
                    size,
                    worked=len(kept),
                    rounded=rounded,
                    varying=varying is not None,
                    place=outline[0][0],
                ),
                outline=outline,
            )
        )
    if unmapped:
        outline = tuple(segment for piece in unmapped for segment in piece)
        findings.append(
            Finding(
                code="edges.unmapped",
                severity="warning",
                message=_(
                    "An {skipped} Stellen hat der exakte Körper keine eigene Kante, etwa weil "
                    "der Knick innerhalb einer Fläche liegt. Diese Stellen blieben unverändert. "
                    "Am Dreiecksmodell lassen sie sich mitbearbeiten: Beenden Sie dafür die "
                    "Flächenbearbeitung.",
                    skipped=len(unmapped),
                ),
                values={"skipped": len(unmapped), "worked": len(kept)},
                location=outline[0][0],
                outline=outline,
                suggestions=(SHOW_LOCATION, MESH_AND_RETRY, CORRECT_INPUT),
            )
        )
    return tuple(kept), findings


def _bound_edges(claimed: Sequence[int | None]) -> tuple[int, ...]:
    """Die nativen Kanten, die die Strecken eines Zugs belegen — ohne Wiederholung."""
    return tuple(dict.fromkeys(index for index in claimed if index is not None))


def _unbound_pieces(
    entry: MeshEdge, claimed: Sequence[int | None]
) -> list[tuple[tuple[Vec3, Vec3], ...]]:
    """Die zusammenhängenden Stücke eines Zugs ohne native Kante — je Stück eine Stelle.

    Ein ganz unbelegter Zug ist ein Stück; ein teilweise belegter behält seine
    Kanten und meldet nur, was übrig bleibt (RM-435 M2).
    """
    from itertools import pairwise

    pieces: list[tuple[tuple[Vec3, Vec3], ...]] = []
    current: list[tuple[Vec3, Vec3]] = []
    for claim, segment in zip(claimed, pairwise(entry.points), strict=True):
        if claim is None:
            current.append(segment)
        elif current:
            pieces.append(tuple(current))
            current = []
    if current:
        pieces.append(tuple(current))
    return pieces


def _why_it_does_not_fit(
    source: SceneObject,
    size: float,
    choice: EdgeChoice,
    keys: tuple[str, ...],
    selected_edges: Sequence[int] | None,
    rounded: bool,
    narrowest: float,
    shape: ChamferShape | None = None,
    law: RadiusLaw | None = None,
    *,
    rings_by_plane: bool = True,
) -> GeometryError | None:
    """Warum der exakte Kern abgelehnt hat — mit demselben Satz wie am Netz, wo er passt.

    OpenCASCADE sagt nur, dass der Bau nicht gelang. Die häufigste Ursache ist
    dieselbe, die das Netz vorab prüft (``edges.contact_band_limit``): Die
    Berührlinien passen nicht auf die angrenzenden Flächen. Gefragt wird an
    der Tessellierung des Körpers, deren ebene Flächen exakt sind; findet sich
    dort der Grund, bekommt der Kunde das größte Maß, das passt — sonst bleibt
    die Absage des Kerns (Übertrag der Durchsicht v0.4.1, Punkt 3).
    """
    from app.core.geom.edges import contact_band_limit, edges_of, too_large_for_the_faces, wanted
    from app.core.units import weld_tolerance

    if selected_edges is not None:
        return None
    varying = law if law is not None and not law.constant else None
    mesh = as_mesh_data(source.mesh)
    entries = edges_of(mesh)
    try:
        chosen = wanted(entries, choice, keys, rings_by_plane=rings_by_plane)
    except GeometryError:
        return None
    try:
        largest = contact_band_limit(
            entries,
            chosen,
            size,
            rounded=rounded,
            tolerance=weld_tolerance(mesh.bounds.diagonal),
            narrowest=narrowest,
            shape=shape,
            law=varying,
        )
    except GeometryError as second:
        # Die zweite Breite passt schon allein nicht — derselbe Satz wie am Netz.
        return second
    if largest is None:
        return None
    return too_large_for_the_faces(size, largest, rounded=rounded, varying=varying is not None)


def narrowest_face(profile: Profile | None) -> float:
    """Die schmalste Fläche, die eine Berührlinie tragen muss — das kleinste Detail
    des Druckers, ohne Drucker die Sehnengrenze (``edges.contact_band_limit``)."""
    if profile is None:
        return MAX_FACET_SAG
    return max(MAX_FACET_SAG, float(profile.printer.smallest_detail))


__all__ = [
    "BeadParams",
    "ChamferParams",
    "FilletParams",
    "bead_edges_op",
    "chamfer_edges",
    "fillet_edges",
    "radius_law",
]


def _too_small_to_see(
    before: HasVolume,
    after: HasVolume,
    profile: Profile | None,
    *,
    kind: Literal["fillet", "chamfer", "bead"],
) -> Finding | None:
    """Hat die Bearbeitung etwas bewirkt, das im Druck ankommt?

    ``boolean.without_effect`` stellt dieselbe Frage und gibt die falsche
    Antwort: Seine beiden Sätze heißen „das Werkzeug liegt neben dem Körper"
    und „Position prüfen" — richtig für eine Tasche, die danebensitzt, und
    unbrauchbar hier. Ein Verrundungswerkzeug sitzt immer richtig, es sitzt
    an der Kante; wenn nichts geschieht, ist das Maß zu klein.

    **Gemessen wird am Drucker und nicht am Rechenepsilon.** Ein Radius von
    0,01 mm an einer 20 mm langen Kante trägt 0,002 mm³ ab — mehr als
    ``EPS_GEOM`` und weniger, als je eine Düse legt. Der Kunde sähe einen
    Schritt im Verlauf und ein unverändertes Teil (§2.7, Regel 17).
    """
    change = abs(after.volume - before.volume)
    threshold = profile.smallest_printable_volume if profile is not None else EPS_GEOM
    if change > threshold:
        return None
    return Finding(
        code="edges.without_effect",
        severity="warning",
        message=(
            _(
                "Der Wulst ist zu klein, um im Druck anzukommen. Wählen Sie einen "
                "größeren Radius, oder prüfen Sie, ob die gewählten Kanten noch da sind."
            )
            if kind == "bead"
            else _(
                "Die Verrundung ist zu klein, um im Druck anzukommen. Wählen Sie einen "
                "größeren Radius, oder prüfen Sie, ob die gewählten Kanten noch da sind."
            )
            if kind == "fillet"
            else _(
                "Die Fase ist zu klein, um im Druck anzukommen. Wählen Sie eine größere "
                "Breite, oder prüfen Sie, ob die gewählten Kanten noch da sind."
            )
        ),
        # ``removed_mm3`` sagt, wie knapp es war: eine glatte Null heißt, dass
        # gar nichts geschnitten wurde, ein Tausendstel heißt „zu klein".
        values={"volume_mm3": round(before.volume, 3), "removed_mm3": round(change, 6)},
        # Regel 17: Radius oder Breite, die der Satz nennt, stehen im Schritt.
        suggestions=(CORRECT_INPUT,),
    )
