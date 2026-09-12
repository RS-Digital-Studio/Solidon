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
from typing import Literal, cast

from app.core.geom.boolean import HasVolume
from app.core.geom.edges import (
    EDGE_CHOICES,
    EdgeChoice,
    bead_edges,
    bevel_edges,
    round_edges,
)
from app.core.geom.mesh import as_mesh_data
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Finding, OpContext, OpResult, Profile, SceneObject
from app.core.units import EPS_GEOM
from app.i18n import _

#: Dieselbe Auswahl bei Verrundung und Fase — deshalb steht der Satz einmal hier.
_CHOICE_DOC = _(
    "Welche Kanten gemeint sind — senkrechte, waagerechte, oben, unten, alle oder einzeln gewählte."
)

#: Und derselbe Satz zum Feld der einzeln gewählten Kanten.
_KEYS_DOC = _(
    "Die einzeln gewählten Kanten. Sie hängen an ihrer Lage am Körper, nicht an "
    "ihrer Nummer — ein Schritt davor darf etwas anderes ändern, ohne dass die "
    "Verrundung wandert."
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
            "Radius der Verrundung. Größer als das dünnste angrenzende Material "
            "geht nicht — dann hat der Kern keinen Platz mehr."
        ),
    )
    edges: str = param(
        title=_("Kanten"),
        default="vertical",
        choices=EDGE_CHOICES,
        doc=_CHOICE_DOC,
    )
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
    cache_version="5",
    title=_("Verrunden"),
    category="shaping",
    params=FilletParams,
    consumes=1,
    produces=1,
    doc=_("Rundet die gewählten Kanten ab — an einem exakten Körper wie an einem Netz."),
    caveat=_(
        "An einem Netz besteht die Rundung aus geraden Stücken statt aus einer "
        "Kurve. Sie weichen um weniger ab, als eine Düse auflöst; wer eine echte "
        "Kurve braucht, arbeitet an einem exakten Körper weiter."
    ),
)
def fillet_edges(ctx: OpContext) -> OpResult:
    params = cast(FilletParams, ctx.params)
    return _worked(
        ctx,
        params.radius,
        cast(EdgeChoice, params.edges),
        _chosen_edges(params.edges, params.edge_keys),
        rounded=True,
    )


@op_params
class ChamferParams(BaseParams):
    distance: float = param(
        title=_("Breite"),
        default=1.0,
        unit="mm",
        minimum=0.01,
        maximum=100.0,
        doc=_("Wie weit die Fase die Kante zurücknimmt, auf jeder der beiden Flächen."),
    )
    edges: str = param(
        title=_("Kanten"),
        default="vertical",
        choices=EDGE_CHOICES,
        doc=_CHOICE_DOC,
    )
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
    cache_version="5",
    title=_("Fase anbringen"),
    category="shaping",
    params=ChamferParams,
    consumes=1,
    produces=1,
    doc=_("Bricht die gewählten Kanten unter 45 Grad — an einem exakten Körper wie an einem Netz."),
)
def chamfer_edges(ctx: OpContext) -> OpResult:
    params = cast(ChamferParams, ctx.params)
    return _worked(
        ctx,
        params.distance,
        cast(EdgeChoice, params.edges),
        _chosen_edges(params.edges, params.edge_keys),
        rounded=False,
    )


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
    cache_version="5",
    title=_("Wulst anlegen"),
    category="shaping",
    params=BeadParams,
    consumes=1,
    produces=1,
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
) -> OpResult:
    """Der gemeinsame Rumpf beider Operationen — der Körper wählt den Kern.

    Gefragt wird ``kind`` und nicht der Typ des Netzes: Das ist dieselbe
    Auskunft, die das Register unter ``requires_kind`` prüft, und sie kostet
    keinen Import in den optionalen Kern.
    """
    source = ctx.inputs[0]
    if source.kind == "brep":
        return _on_a_solid(source, size, choice, keys, profile=ctx.profile, rounded=rounded)

    body = as_mesh_data(source.mesh)
    work = round_edges if rounded else bevel_edges
    outcome = work(body, size, choice, keys)
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


def _on_a_solid(
    source: SceneObject,
    size: float,
    choice: EdgeChoice,
    keys: tuple[str, ...],
    *,
    profile: Profile | None,
    rounded: bool,
) -> OpResult:
    """Der exakte Weg — träge geholt, weil OpenCASCADE optional ist (§36).

    Ein Rechner ohne den Kern hat auch keinen Körper der Art ``brep`` in der
    Szene; dieser Zweig wird dort nie betreten, und der Import darf deshalb
    nicht beim Laden des Registers stattfinden.
    """
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid

    work = edit.fillet if rounded else edit.chamfer
    solid = work(cast(Solid, source.mesh), size, choice, keys)
    empty = _too_small_to_see(source.mesh, solid, profile, kind="fillet" if rounded else "chamfer")
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=solid, kind="brep", features=features_of(solid))],
        findings=[dataclasses.replace(empty, object_id=source.id)] if empty is not None else [],
    )


__all__ = [
    "BeadParams",
    "ChamferParams",
    "FilletParams",
    "bead_edges_op",
    "chamfer_edges",
    "fillet_edges",
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
    )
