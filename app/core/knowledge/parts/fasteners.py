"""Bausteine für Schrauben (Bauplan §24.1, Gruppe „Verbindungen").

Vier der dreizehn: das Schraubenloch mit seiner Senkung, die Bohrung für die
Einpressbuchse, die Mutternfalle von der Seite oder von unten, und ein
druckbares Gewinde.

Jedes Maß kommt aus der Normteiltabelle (§24.2) — „Loch für eine
M4-Einpressbuchse" ist ein Nachschlagen, keine Vermutung. Was der Baustein
darauflegt, ist die Materialtoleranz aus dem Profil, und er sagt das in seiner
Dokumentation, statt es in einer Zahl zu verstecken.
"""

from __future__ import annotations

from typing import Any, cast

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, result, thread, union
from app.core.knowledge.parts.registry import PartChange, register_part
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult
from app.i18n import _

_SCREWS = standards.screw_sizes()
_NUTS = standards.nut_sizes()
_INSERTS = standards.insert_sizes()

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Erstbestückung der Bibliothek (§24.1)."
)

#: Version 3 betrifft zwei Bausteine mit derselben Ursache: ihr Spiel stand
#: als feste Zahl in der Vorgabe (0,2 bzw. 0,15 mm), und der Zweig, der es
#: aus dem kalibrierten Materialprofil füllt, greift nur bei null — die
#: Kalibrierung nach §28.3 erreichte beide nie (Regel 7).
PLAY_FROM_PROFILE = PartChange(
    version="3",
    date="2026-08-16",
    reason="Das Spiel kommt aus dem kalibrierten Materialprofil, nie als Zahl "
    "im Baustein (Regel 7, §28.3).",
    effect="Die Vorgabe ist null und heißt: Profilwert. Mutternfalle und "
    "Gewinde fallen damit je nach Material enger oder weiter aus als mit den "
    "alten Festwerten 0,2 und 0,15 mm; wer genau die will, trägt sie ein.",
)


# --- screw hole -------------------------------------------------------------------


@op_params
class ScrewHoleParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M3",
        choices=_SCREWS,
        doc=_("Gewindegröße der Schraube. Alle Maße kommen aus der Normteiltabelle."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=10.0,
        unit="mm",
        minimum=1.0,
        maximum=200.0,
        doc=_("Wie tief gebohrt wird. Mehr als die Wandstärke ergibt ein Durchgangsloch."),
    )
    countersink: bool = param(
        title=_("Senkung"),
        default=True,
        doc=_("90-Grad-Senkung für einen Senkkopf. Aus für Zylinderkopf und Linsenkopf."),
    )
    head_room: float = param(
        title=_("Kopffreiheit"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        placement="advanced",
        doc=_("Zylindrische Aussparung über der Senkung, für einen versenkten Kopf."),
    )


@register_part(
    name="screw_hole",
    title=_("Schraubenloch mit Senkung"),
    group="fasteners",
    params=ScrewHoleParams,
    subtractive=True,
    features=["bore", "countersink"],
    doc=_(
        "Durchgangsloch zum Verschrauben mit einer metrischen Schraube, auf Wunsch "
        "mit 90-Grad-Senkung "
        "und Kopffreiheit. Maße aus der Normteiltabelle."
    ),
    changes=[FIRST_RELEASE],
)
def screw_hole(raw: BaseParams) -> PartResult:
    params = cast(ScrewHoleParams, raw)
    screw = standards.screw(params.size)

    shaft = shapes.cylinder(screw.clearance, params.depth + shapes.OVERLAP)
    shaft = shapes.moved(shaft, (0.0, 0.0, -params.depth))
    parts = [shaft]
    features = [
        bore(
            "bore_1",
            screw.clearance,
            (0.0, 0.0, -params.depth / 2.0),
            depth=params.depth,
            through=True,
        )
    ]

    if params.countersink:
        # Eine 90-Grad-Senkung ist so tief, wie der Kopf breit ist, halbiert.
        depth = (screw.countersink - screw.clearance) / 2.0
        sink = shapes.cone(screw.clearance, screw.countersink, depth)
        parts.append(shapes.moved(sink, (0.0, 0.0, -depth)))
        features.append(
            bore("countersink_1", screw.countersink, (0.0, 0.0, -depth / 2.0), depth=depth)
        )

    if params.head_room > 0.0:
        room = shapes.cylinder(screw.countersink, params.head_room + shapes.OVERLAP)
        parts.append(room)

    return result(union(*parts), *features)


# --- heat-set insert ---------------------------------------------------------------


@op_params
class HeatsetParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M3",
        choices=_INSERTS,
        doc=_("Gewinde der Buchse. Der Bohrungsdurchmesser dazu kommt aus der Normteiltabelle."),
    )
    lead_in: bool = param(
        title=_("Einführfase"),
        default=True,
        doc=_("Fase am Rand, damit die Buchse beim Einpressen gerade läuft."),
    )
    extra_depth: float = param(
        title=_("Zusatztiefe"),
        default=0.5,
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        placement="advanced",
        doc=_("Platz unter der Buchse für verdrängtes Material."),
    )


def size_for_insert(diameter: float) -> dict[str, Any]:
    """Die kleinste Buchse, die eine Bohrung dieses Durchmessers **aufweitet**.

    Die Buchse ersetzt die Bohrung, sie sitzt nicht auf ihr. Eine Größe, deren
    Bohrung kleiner ist als die vorhandene, schneidet vollständig innerhalb und
    trägt nichts ab — genau das geschah bis zum 23.08.2026 mit der Vorgabe M3
    (4,00 mm) an einer Ø 5,19-Bohrung.
    """
    for size in standards.insert_sizes():
        if standards.insert(size).hole >= diameter:
            return {"size": size}
    return {}


def size_for_nut_trap(diameter: float) -> dict[str, Any]:
    """Die kleinste Mutter, deren Durchgangsloch die Bohrung noch aufnimmt.

    Dasselbe Verhältnis wie bei der Buchse: Das Schraubenloch der Falle tritt
    an die Stelle der vorhandenen Bohrung. Ein kleineres verschwände darin, und
    die Mutter säße in einem Loch, das weiter ist als ihr eigenes.
    """
    for size in standards.screw_sizes():
        if standards.screw(size).clearance >= diameter:
            return {"size": size}
    return {}


def size_for_thread(diameter: float) -> dict[str, Any]:
    """Das größte Gewinde, das in eine Bohrung dieses Durchmessers geschnitten
    werden kann — und zwar als **Innengewinde**.

    Zwei Schranken, beide fachlich und keine geratene Toleranz: Unterhalb des
    Kernlochdurchmessers greift das Werkzeug nicht ins Material, oberhalb des
    Nennmaßes liegt die Bohrungswand außerhalb des Gewindes. Eine
    Ø 6,5-Bohrung bekommt deshalb **keinen** Vorschlag statt eines falschen —
    für M6 ist sie zu weit, für M8 zu eng.

    Und ``internal``: Wer eine Bohrung anklickt und „Gewinde" wählt, meint
    Gänge in der Wand. Die Schemavorgabe steht auf Außengewinde, und das ist
    für einen freistehenden Bolzen richtig — in einem Loch setzte sie einen
    zweiten Bolzen hinein.
    """
    fitting = [
        size
        for size in standards.screw_sizes()
        if standards.screw(size).tap <= diameter <= standards.screw(size).nominal
    ]
    return {"size": fitting[-1], "internal": True} if fitting else {}


@register_part(
    name="heatset_m4",
    title=_("Heat-Set-Einpressbuchse"),
    group="inserts",
    params=HeatsetParams,
    subtractive=True,
    at_hole=True,
    at_hole_values=size_for_insert,
    features=["bore", "chamfer"],
    doc=_(
        "Bohrung für eine Heat-Set-Einpressbuchse mit Einführfase. Der Durchmesser "
        "ist bewusst knapp: das Material soll beim Einpressen verdrängt werden."
    ),
    caveat=_(
        "Nicht ohne Lötkolben: Die Buchse wird warm eingepresst, und der Durchmesser "
        "ist dafür knapp gehalten. Kalt hineingedrückt sprengt sie die Wand — dann "
        "ist ein Schraubenloch die bessere Wahl."
    ),
    changes=[FIRST_RELEASE],
)
def heatset_insert(raw: BaseParams) -> PartResult:
    params = cast(HeatsetParams, raw)
    entry = standards.insert(params.size)
    depth = entry.length + params.extra_depth

    shaft = shapes.cylinder(entry.hole, depth + shapes.OVERLAP)
    shaft = shapes.moved(shaft, (0.0, 0.0, -depth))
    parts = [shaft]
    features = [
        bore("bore_1", entry.hole, (0.0, 0.0, -depth / 2.0), depth=depth),
    ]

    if params.lead_in:
        chamfer = (entry.outer - entry.hole) / 2.0 + 0.3
        lead = shapes.cone(entry.hole, entry.hole + 2.0 * chamfer, chamfer)
        parts.append(shapes.moved(lead, (0.0, 0.0, -chamfer)))
        features.append(
            bore("chamfer_1", entry.hole + 2.0 * chamfer, (0.0, 0.0, -chamfer / 2.0), depth=chamfer)
        )

    return result(union(*parts), *features)


# --- nut trap -----------------------------------------------------------------------


@op_params
class NutTrapParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M3",
        choices=_NUTS,
        doc=_("Gewinde der Mutter. Schlüsselweite und Höhe kommen aus der Normteiltabelle."),
    )
    direction: str = param(
        title=_("Richtung"),
        default="side",
        choices=("side", "bottom"),
        doc=_("Von der Seite eingeschoben oder von unten eingelegt."),
    )
    slide: float = param(
        title=_("Einschubweg"),
        default=12.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_("Wie weit der Schlitz nach außen reicht. Null heißt: nur die Tasche."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=_("Null heißt: Wert aus dem kalibrierten Materialprofil."),
    )
    screw_hole: bool = param(
        title=_("Schraubenloch mitschneiden"),
        default=True,
        doc=_("Schneidet zusätzlich das Durchgangsloch für die Schraube durch das Teil."),
    )


@register_part(
    name="nut_trap",
    title=_("Mutternfalle"),
    group="fasteners",
    params=NutTrapParams,
    subtractive=True,
    at_hole=True,
    at_hole_values=size_for_nut_trap,
    features=["pocket", "bore"],
    doc=_(
        "Tasche für eine Sechskantmutter, seitlich eingeschoben oder von unten "
        "eingelegt, auf Wunsch mit durchgehendem Schraubenloch."
    ),
    changes=[FIRST_RELEASE, PLAY_FROM_PROFILE],
)
def nut_trap(raw: BaseParams) -> PartResult:
    params = cast(NutTrapParams, raw)
    entry = standards.nut(params.size)
    width = entry.width + params.play
    height = entry.height + params.play / 2.0

    pocket = shapes.hexagon(width, height)
    parts = [pocket]
    features = [
        bore("pocket_1", width, (0.0, 0.0, height / 2.0), depth=height),
    ]

    if params.slide > 0.0:
        # Der Schlitz, durch den die Mutter eingeschoben wird, entlang +Y zeigend.
        channel = shapes.box(width, params.slide, height)
        parts.append(shapes.moved(channel, (0.0, params.slide / 2.0, 0.0)))

    if params.screw_hole:
        screw = standards.screw(params.size)
        length = height + 20.0
        shaft = shapes.cylinder(screw.clearance, length)
        parts.append(shapes.moved(shaft, (0.0, 0.0, -10.0)))
        features.append(
            bore("bore_1", screw.clearance, (0.0, 0.0, height / 2.0), depth=length, through=True)
        )

    body = union(*parts)
    if params.direction == "bottom":
        # Gedreht, sodass die Öffnung nach unten schaut — von unten eingelegt
        # statt von der Seite eingeschoben.
        body = shapes.turned(body, 90.0, (1.0, 0.0, 0.0))
    return result(body, *features)


# --- thread --------------------------------------------------------------------------


@op_params
class ThreadParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M6",
        choices=_SCREWS,
        doc=_(
            "Nenndurchmesser und Steigung. Das Profil ist druckbar abgeflacht, "
            "kein ISO-Profil — das löst ein Drucker ohnehin nicht auf."
        ),
    )
    length: float = param(
        title=_("Länge"),
        default=12.0,
        unit="mm",
        minimum=2.0,
        maximum=200.0,
        doc=_("Länge des Gewindes, nicht des Bolzens."),
    )
    internal: bool = param(
        title=_("Innengewinde"),
        default=False,
        doc=_("Innengewinde wird abgezogen, Außengewinde wird angesetzt."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=_("Null heißt: Wert aus dem kalibrierten Materialprofil."),
    )


@register_part(
    name="printed_thread",
    title=_("Gewinde"),
    group="fasteners",
    params=ThreadParams,
    subtractive=False,
    at_hole=True,
    at_hole_values=size_for_thread,
    features=["thread"],
    doc=_(
        "Druckbares Gewinde als Wendel mit abgeflachtem Kamm — kein ISO-Profil, "
        "weil ein Drucker es ohnehin nicht auflöst."
    ),
    caveat=_(
        "Nicht, wo eine Metallschraube greifen soll: Der Kamm ist abgeflacht, damit "
        "ein Drucker ihn überhaupt auflöst — ein genormtes Gegenstück fasst darin "
        "nicht sauber. Für tragende Verschraubungen ist eine Einpressbuchse richtig."
    ),
    changes=[FIRST_RELEASE, PLAY_FROM_PROFILE],
)
def printed_thread(raw: BaseParams) -> PartResult:
    """Ein Gewinde, und sein Gegenstück so gemessen, dass die zwei wirklich
    greifen.

    Beide werden von denselben zwei Zahlen beschrieben — Außendurchmesser und
    Steigung — und von entgegengesetzten Enden des Gangs her gebaut:

    * außen liegt der Kern zwei Gangtiefen unter dem Außendurchmesser, und die
      Helix reicht bis zu ihm hinaus;
    * innen beginnt das *Werkzeug* bei genau diesem Kerndurchmesser, und die
      Helix reicht bis zum Außendurchmesser. Vom Kern geschnitten statt vom
      Außendurchmesser — das ist der Unterschied zwischen einer Mutter und
      einem glatten Loch: eine Bohrung auf Außendurchmesser lässt nichts
      stehen, woran der Gang einer Schraube halten könnte, und die Schraube
      fällt glatt hindurch. An M6 gemessen: eine Schraube mit 5,85 außen
      reicht bis r = 2,925, und ein auf 6,15 gebohrtes Loch beginnt bei
      r = 3,075 — hundertfünfzig Mikrometer Luft.
    """
    params = cast(ThreadParams, raw)
    screw = standards.screw(params.size)
    depth = screw.pitch * shapes.RIDGE_SHARE
    if params.internal:
        # Das Werkzeug: Kern plus Spiel, und die Nut reicht von dort hinaus.
        diameter = screw.nominal - 2.0 * depth + params.play
        core = shapes.cylinder(diameter, params.length)
    else:
        diameter = screw.nominal - params.play
        core = shapes.cylinder(diameter - 2.0 * depth, params.length)

    ridge = shapes.thread_body(diameter, screw.pitch, params.length, internal=params.internal)
    body = union(core, ridge)
    # Die Helix endet ein Stück über der Nennlänge; sie wird zurückgeschnitten,
    # damit das Teil genau so lang ist, wie es sagt.
    limit = shapes.cylinder(diameter * 2.0 + 4.0, params.length)
    body = _intersect(body, limit)

    return result(
        body,
        thread(
            "thread_1",
            screw.nominal,
            screw.pitch,
            (0.0, 0.0, params.length / 2.0),
            internal=params.internal,
        ),
    )


def _intersect(first: MeshData, second: MeshData) -> MeshData:
    return boolean("intersection", [first, second], quality="fine").mesh
