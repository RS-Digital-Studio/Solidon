"""Operationen für die Druckvorbereitung (Bauplan §25).

Bohren, Teilen, Anordnen und die Kollisionsprüfung. Die letzte ändert gar
keine Geometrie — sie meldet nur, und das ist eine völlig gute Sache für eine
Operation, wenn die Alternative eine Überraschung am Drucker ist.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from functools import lru_cache
from typing import Final, cast

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import (
    CANCEL,
    CHANGE_SELECTION,
    CORRECT_INPUT,
    GeometryError,
    InternalError,
    ValidationError,
)
from app.core.geom.boolean import (
    NOTHING_LEFT_DETAIL,
    NOTHING_LEFT_TITLE,
    BooleanKind,
    BooleanOutcome,
    boolean,
    without_effect,
)
from app.core.geom.hollow import VENT_DIAMETER, below_printable_wall, hollow
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.ops import as_transform
from app.core.geom.orient import orient_for_print, print_transform
from app.core.geom.pins import (
    PIN_COUNT,
    PIN_MAX,
    PinnedPair,
    add_pins,
    connector_glue_finding,
    feature_side,
    next_connector_index,
    plan_pins,
)
from app.core.geom.prepare import (
    BORE_SECTIONS,
    MAX_PLATES,
    Arrangement,
    BoreAnchor,
    arrange_on_bed,
    bore_diameter,
    check_build_volume,
    check_collisions,
    compensate_elephant_foot,
    countersink,
    drill,
    named_for,
    over_the_edge_along,
    plug,
    resize_bore,
    shell,
    split_at_plane,
)
from app.core.geom.section import AXIS_NORMALS, SectionPlane
from app.core.geom.transform import Axis, place_on_bed
from app.core.knowledge.profiles import for_object, material
from app.core.registry import AUTO_FROM_PROFILE_DOC, VARIABLE, op_params, param, register_op
from app.core.slice.orientation import DEFAULT_CANDIDATES, search
from app.core.types import (
    BaseParams,
    CancelToken,
    Feature,
    FeatureId,
    Finding,
    Mesh,
    OpContext,
    OpResult,
    Quality,
    SceneObject,
    Vec3,
)
from app.core.units import DEGREE_UNIT, EPS_DISPLAY, EPS_GEOM, format_length
from app.i18n import TranslatableText, _

_AXES = tuple(AXIS_NORMALS)

#: Erklärungen, die für jede Bohrung dieselben sind. Einmal geschrieben, damit
#: dieselbe Zahl nicht an drei Stellen unterschiedlich erklärt wird.
_WHERE_X = _(
    "Mitte der Bohrung im Koordinatensystem des Objekts. Eine angeklickte "
    "Fläche trägt die drei Werte selbst ein."
)
_WHERE_Y = _("Zweite Achse der Position — siehe Position X.")
_WHERE_Z = _("Dritte Achse der Position — siehe Position X.")
_ALONG = _(
    "Richtung, in die gebohrt wird. Z ist senkrecht von oben, X und Y bohren durch eine Seitenwand."
)

#: Was die Position bedeutet. „mouth" ist die Vorgabe, weil eine angeklickte
#: Fläche die Mündung ist und nicht die Mitte des Lochs dahinter; „centre" gibt
#: es, weil Dateien bis Formatversion 6 es so gemeint haben.
_ANCHORS = ("mouth", "centre")

#: Was ein Verbinder sein kann. Die ersten drei sind Querschnitte: dieselbe
#: Rechnung, ein anderes Vieleck. Rund ist die Vorgabe und der einfachste
#: Druck; die kantigen sichern gegen Verdrehen, der Schwalbenschwanz zusätzlich
#: gegen Auseinanderziehen quer zur Naht.
#:
#: Der Schnapper ist kein Querschnitt, sondern ein Mechanismus mit eigenem
#: Baustein (``snap_connector``) — er steht hier trotzdem in derselben Liste,
#: weil er für den Nutzer dieselbe Entscheidung ist: *womit* halten die Hälften
#: zusammen. Wo eine Naht ihm zu schmal ist, wird rund daraus, und der
#: Prüfbericht sagt es (``split.snap_too_small``).
CONNECTOR_SHAPES = ("round", "hex", "dovetail", "snap")

_CONNECTOR_DOC = _(
    "Womit die Hälften zusammenhalten. Rund druckt am saubersten und braucht "
    "zwei Stück gegen Verdrehen; Sechskant und Schwalbenschwanz halten schon "
    "einzeln, der Schwalbenschwanz auch gegen Auseinanderziehen. Der Schnapper "
    "rastet ein und hält ohne Kleber — er braucht eine Naht, die mindestens "
    "5,4 mm hergibt."
)


#: Was eine Hälfte von der anderen unterscheidet, sobald verstiftet wurde,
#: und das Zeichen davor.
_HALF_MARK = " · "
_PIN_NOTE = _("Stifte")
_BORE_NOTE = _("Löcher")

#: Dieselben zwei Zusätze als **ganzer** Name, mit dem Stamm als Wert. Der
#: Stamm gehört dem Nutzer und bleibt eine Zeichenkette; der Zusatz gehört der
#: Anwendung und wandert mit der Sprache. Vorher war der ganze Name eine feste
#: Zeichenkette in der Sprache, die beim Trennen eingestellt war.
#:
#: Das Trennzeichen steht hier ausgeschrieben und nicht als ``_HALF_MARK``:
#: Der Einsammler liest die Message-ID als **Literal** aus dem ``_()``-Aufruf,
#: und ein zusammengesetzter Ausdruck ist für ihn keine. Zwei Sprachdateien mit
#: einem Schlüssel, den niemand mehr füllt, wären der Preis dafür.
_HALF_IDS = frozenset({"{name} · Stifte", "{name} · Löcher"})


@lru_cache(maxsize=1)
def _own_notes() -> frozenset[str]:
    """Die beiden Zusätze in jeder ausgelieferten Sprache.

    Gebraucht, um den *eigenen* Zusatz von einem fremden Namensteil zu
    unterscheiden. Ein bloßes Abschneiden am letzten „ · " war zu grob:
    „Halter · Sonderanfertigung" verlor beim Teilen sein zweites Wort —
    stiller Verlust an einem Namen, den jemand selbst vergeben hat.

    Über alle Sprachen und nicht nur über die aktive, weil ein Teil auf
    Deutsch geteilt und danach auf Englisch weitergeteilt werden kann. Ohne
    das stapelten sich zwei Zusätze in zwei Sprachen.

    Gemerkt, und das ist keine vorbeugende Optimierung: Der Aufruf liest fünf
    Katalogdateien und kostet gemessen 9,6 ms — für den Vergleich von zwei
    Wörtern, einmal je Schnitt. Die Antwort hängt an den ausgelieferten
    Dateien und nicht an der eingestellten Sprache, kann also nicht veralten.
    """
    from app.i18n.catalog import available_languages, read_catalog

    notes = {str(_PIN_NOTE), str(_BORE_NOTE), _PIN_NOTE.msgid, _BORE_NOTE.msgid}
    for language in available_languages():
        catalog = read_catalog(language)
        for note in (_PIN_NOTE, _BORE_NOTE):
            translated = catalog.get(note.msgid)
            if translated:
                notes.add(translated)
    return frozenset(notes)


def half_names(
    base: TranslatableText | str, *, pinned: bool
) -> tuple[TranslatableText | str, TranslatableText | str]:
    """Wie die beiden Stücke heißen.

    „A" und „B" allein beantworten die Frage nicht, die man beim Zusammenbauen
    hat — und beim Export ist der Dateiname die einzige Auskunft darüber,
    welches der beiden Teile die Stifte trägt. Deshalb steht sie im Namen.

    Ein **eigener** Zusatz wird ersetzt, nicht ergänzt: Wer eine Hälfte noch
    einmal teilt, bekommt sonst „Halter A · Stifte A · Stifte". Der
    Buchstabenpfad bleibt dabei stehen — er zeigt, aus welchem Stück welches
    geworden ist. Ein fremder Namensteil hinter demselben Zeichen bleibt, wo
    er ist (:func:`_own_notes`).

    Der Rückgabetyp ist geteilt: Ohne Stifte ist der Name reiner Nutzertext und
    bleibt eine Zeichenkette; mit Stiften trägt er den Zusatz der Anwendung und
    ist übersetzbar. Wer ihn anzeigt, nimmt ``str(...)``; wer ihn in einen
    Dateinamen schreibt, ``source_text``.
    """
    # Ab hier wörtlich: Wie die Hälften heißen, entsteht beim Trennen, und was
    # dabei entsteht, gehört dem Nutzer — dieselbe Regel wie beim Namen einer
    # Kopie (:func:`app.core.scene.ops._copy_name`). Genommen wird die Fassung,
    # die er beim Trennen gesehen hat.
    if isinstance(base, TranslatableText) and base.msgid in _HALF_IDS:
        # Eine Hälfte, die dieselbe Anwendung benannt hat: Der Stamm steht
        # als Wert daneben und muss nicht aus dem Text zurückgelesen werden.
        stem = str((base.values or {}).get("name", ""))
    else:
        stem = str(base)
        head, mark, tail = stem.rpartition(_HALF_MARK)
        if mark and tail in _own_notes():
            stem = head
    if not pinned:
        return f"{stem} A", f"{stem} B"
    return (
        _("{name} · Stifte", name=f"{stem} A"),
        _("{name} · Löcher", name=f"{stem} B"),
    )


@op_params
class DrillParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=5.0,
        unit="mm",
        minimum=0.2,
        maximum=200.0,
        doc=_(
            "Nenndurchmesser der Bohrung. Für eine Schraube gibt es *Schraubenloch* "
            "in den Bausteinen — dort kommen die Maße aus der Normteiltabelle."
        ),
    )
    x: float = param(
        title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X, placement="advanced"
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z, placement="advanced"
    )
    axis: str = param(
        title=_("Achse"), default="z", choices=_AXES, doc=_ALONG, placement="advanced"
    )
    depth: float = param(
        title=_("Tiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        placement="advanced",
        doc=_("Null bohrt durch das ganze Teil."),
    )
    anchor: str = param(
        title=_("Bezugspunkt"),
        default="mouth",
        choices=_ANCHORS,
        placement="advanced",
        doc=_(
            "Was die Position bedeutet: die Mündung, an der die Bohrung anfängt, "
            "oder ihre Mitte. Bei einer durchgehenden Bohrung ändert es nichts."
        ),
    )
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=True,
        placement="advanced",
        doc=_("Vergrößert die Bohrung um den Wert aus dem Materialprofil."),
    )


@register_op(
    name="drill_hole",
    title=_("Bohrung setzen"),
    category="holes",
    params=DrillParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    touches_features=True,
    deterministic=False,
    shortcut="Ctrl+B",
    doc=_("Bohrt ein rundes Loch — auf Wunsch um die Materialtoleranz vergrößert."),
)
def drill_hole(ctx: OpContext) -> OpResult:
    params = cast(DrillParams, ctx.params)
    source = ctx.inputs[0]
    result = drill(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        depth=params.depth,
        anchor=cast(BoreAnchor, params.anchor),
        profile=ctx.profile,
        compensate=params.compensate,
        quality=ctx.quality,
        seed=ctx.seed,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh)],
        solver=result.solver,
        findings=result.findings,
    )


# --- Erkannte Merkmale versetzen (§25, Kundenumfrage vom 03.09.2026) ---------------
#
# **Eine Maschine mit mehreren Ausgängen, nicht mehrere Operationen.** Vier der
# neun Merkmalsarten beschreiben ihren eigenen Körper vollständig, und ``recess``
# sagt, ob er ein Hohlraum ist oder Materie:
#
#     hole     axis, centre, depth, diameter, through
#     pin      axis, centre, depth, diameter
#     cone     axis, centre, diameter, angle, recess
#     sphere   centre, diameter, recess
#
# Damit sind Verschieben, Ändern und Löschen dasselbe Paar aus Vereinen und
# Abziehen — an der alten Stelle das Gegenteil dessen, was das Merkmal ist, an
# der neuen das Merkmal selbst.
#
# Die drei übrigen Arten bleiben draußen, und zwar begründet: Eine ``face``
# gehört zur Oberfläche des Körpers (dafür gibt es ``push_face``), ein
# ``edge_loop`` ist ein Netzfehler und kein Körper, und ein ``fillet`` hängt an
# seiner Kante — versetzt man ihn allein, bleibt die Kante scharf und die
# Rundung liegt daneben.

#: Die Arten, deren Kennzahlen das Merkmal **genau** beschreiben.
#:
#: **Genau heißt: Der gebaute Körper ist das Merkmal und nicht mehr.** Bei einer
#: Bohrung stimmt das — ``centre``, ``axis``, ``depth`` und ``through`` spannen
#: den Zylinder auf, der genau das Loch ist. Bei einem Zapfen ebenso: ``depth``
#: ist seine Höhe über der Grundfläche.
#:
#: Bei ``cone`` und ``sphere`` stimmt es **nicht**, und das ist gemessen: Die
#: erkannte Mitte einer Kuppe liegt in der Fläche, auf der sie sitzt — der halbe
#: Grundkörper steckt im Material. Wer den ganzen abzieht, gräbt eine Mulde in
#: die Platte. An einer Kuppe Ø 12 auf einer 10 mm starken Platte kostete das
#: 445 mm³ von 24 449, und der Körper war danach wasserdicht und still falsch.
#:
#: Der Weg dorthin ist bekannt und gehört in einen eigenen Schritt: Die
#: Merkmalsflächen (``face_indices``) begrenzen die Kuppe genau, und ihr
#: Randring liegt auf der Grundfläche — gedeckelt ergibt er den Körper, der
#: wirklich das Merkmal ist. Bis dahin sagt die Operation, warum sie es nicht
#: tut, statt es falsch zu tun (Regel 21).
MOVABLE_KINDS: Final = ("hole", "pin", "cone", "sphere")

#: Die Arten, deren Kennzahlen den Körper genau beschreiben.
#:
#: Für sie baut :func:`_feature_solid` ihn daraus, und das ist auch der
#: einzige Weg, der eine **durchgehende** Bohrung trägt: Ihr Flächenausschnitt
#: hat zwei Randringe, und ein Deckel aus einem Fächer schließt nur einen.
PARAMETRIC_KINDS: Final = ("hole", "pin")

#: Wie viele Seiten ein gebauter Zylinder oder Kegel bekommt. Dieselbe Zahl wie
#: beim Bohren — ein Stopfen mit anderer Auflösung träfe die Bohrungswand in
#: einer fast zusammenfallenden Fläche, und das ist der eine Fall, den eine
#: Boolesche zuverlässig bricht (§39).
FEATURE_SECTIONS: Final = BORE_SECTIONS

#: Wieviel größer der Körper gebaut wird, der ein Merkmal ausfüllt oder
#: abträgt. Aus demselben Grund wie beim Stopfen: Fläche auf Fläche bricht.
FEATURE_OVERLAP: Final = 0.02


def _feature_is_a_cavity(feature: Feature) -> bool:
    """Ist dieses Merkmal ein Hohlraum oder Materie?

    ``hole`` ist immer ein Hohlraum, ``pin`` immer Materie. ``cone`` und
    ``sphere`` können beides sein, und die Erkennung sagt es in ``recess`` —
    eine angesenkte Bohrung ist ein Kegel nach innen, eine Kuppe einer nach
    außen.
    """
    if feature.kind == "hole":
        return True
    if feature.kind == "pin":
        return False
    return bool(feature.params.get("recess", False))


def _feature_solid(
    feature: Feature,
    centre: Vec3,
    scale: float = 1.0,
    axis: Vec3 | None = None,
) -> MeshData:
    """Der Körper, den dieses Merkmal einnimmt — an ``centre`` gesetzt.

    ``scale`` skaliert die Querschnittsmaße; ``1.0`` baut das Merkmal, wie es
    gemessen wurde. ``axis`` überschreibt seine Richtung; ``None`` nimmt die
    gemessene. Beide zusammen sind der Grund, warum Versetzen, Drehen und
    Ändern **eine** Maschine sind und nicht drei: Zwischen den zwei Booleschen
    steht jeweils nur ein anderer Wert.

    Der Körper wird um :data:`FEATURE_OVERLAP` größer gebaut als gemessen,
    damit keine Boolesche auf zusammenfallende Flächen trifft (§39) — beim
    Ausfüllen wie beim Abtragen.
    """
    diameter = float(feature.params.get("diameter", 0.0)) * scale + FEATURE_OVERLAP
    if diameter <= EPS_GEOM:
        raise ValidationError(
            field="at_feature",
            detail=_("Dieses Merkmal hat kein Maß, aus dem sich ein Körper bauen ließe."),
            values={"feature": feature.id},
            constraint="no_size",
        )

    if feature.kind == "sphere":
        body = trimesh.creation.icosphere(radius=diameter / 2.0)
        body.apply_translation(np.asarray(centre, dtype=float))
        return MeshData.of(body)

    wanted = axis if axis is not None else feature.params.get("axis", (0.0, 0.0, 1.0))
    given = np.asarray(wanted, dtype=float)
    length = float(np.linalg.norm(given))
    direction = given / length if length > EPS_GEOM else np.array([0.0, 0.0, 1.0])
    # **Ganz durch und nicht nur so tief wie gemessen.** Eine Bohrung, die als
    # 12 mm tief erkannt wurde, muss beim Ausfüllen auch die 12 mm treffen —
    # und eine, die durchgeht, den ganzen Körper. Die gemessene Tiefe ist die
    # Untergrenze, die Zugabe an beiden Enden deckt die Messungenauigkeit.
    depth = float(feature.params.get("depth", 0.0))
    height = max(depth, diameter) + 2.0 * FEATURE_OVERLAP

    if feature.kind == "cone":
        body = trimesh.creation.cone(
            radius=diameter / 2.0, height=height, sections=FEATURE_SECTIONS
        )
        # ``cone`` steht mit der Spitze oben auf z=0; für einen Hohlraum zeigt
        # sie ins Material, also entlang der Achse.
        body.apply_translation((0.0, 0.0, -height / 2.0))
    else:
        body = trimesh.creation.cylinder(
            radius=diameter / 2.0, height=height, sections=FEATURE_SECTIONS
        )

    turn = trimesh.geometry.align_vectors(  # type: ignore[no-untyped-call]
        [0.0, 0.0, 1.0], direction
    )
    body.apply_transform(turn)
    body.apply_translation(np.asarray(centre, dtype=float))
    return MeshData.of(body)


#: Wie flach ein Randring sein muss, damit ein Deckel aus einem Fächer trägt.
#:
#: Ein Fächer vom Schwerpunkt zu jeder Randkante ist genau dann eine Fläche,
#: wenn der Ring in einer Ebene liegt. Bei einer Kuppe auf einer Platte ist die
#: Spanne gemessen **null**; die Grenze fängt die Tesselierung einer schwach
#: gekrümmten Grundfläche mit und lehnt alles darüber ab, statt einen
#: verdrehten Deckel zu bauen.
#:
#: **Diese Zahl ist an einem einzigen Körper gemessen, und das ist ihr
#: schwächster Punkt.** Sie hält, weil die Grenze mit der Wurzel der
#: Randknotenzahl mitwächst — die abgelehnten Fälle liegen um Größenordnungen
#: darüber (15,2 gegen 0,51 an einer Senkung über einer Bohrung, gemessen am
#: 03.09.2026). Wer sie anfasst, messe an **mehr als einem** Körper: 3d-druck-7b
#: hat am selben Tag zwei Schranken aus je einem Messwert gesetzt, und beide
#: standen zu eng — 5 Grad aus einer Messung von 2,2, und der zweite Fall lag
#: bei 5,74. Eine Schranke aus einem Wert ist geraten, nicht gemessen; der Fall
#: steht ausgeschrieben in ``.claude/memory/schranke-aus-einem-messwert-ist-geraten.md``.
FLAT_RIM: Final = 0.05


def _feature_body(mesh: MeshData, feature: Feature) -> MeshData | None:
    """Der Körper, den dieses Merkmal wirklich einnimmt — aus seinen Flächen.

    **Warum nicht aus den Kennzahlen.** Für Bohrung und Zapfen beschreiben
    ``centre``, ``axis``, ``depth`` und ``diameter`` den Körper genau, und
    :func:`_feature_solid` baut ihn daraus. Für eine Kuppe oder einen Kegel tun
    sie das nicht: Die erkannte Mitte liegt **in** der Fläche, auf der sie
    sitzen, der halbe Grundkörper steckt im Material. Gemessen am 03.09.2026
    kostete das Versetzen einer Kuppe Ø 12 auf einer 10-mm-Platte 445 mm³ von
    24 449 — der Körper blieb wasserdicht und war still falsch.

    Die Merkmalsflächen sagen es genau: Sie begrenzen die Kuppe, ihr Randring
    liegt auf der Grundfläche, und mit einem Deckel darüber entsteht der
    Körper, der wirklich das Merkmal ist. Gemessen: 448,5 mm³ gegen 452,4 der
    analytischen Halbkugel — die Differenz ist die Tesselierung der Vorlage.

    ``None``, wenn der Bau nicht sicher ist: keine Flächen, mehr als ein
    Randring, oder ein Ring, der nicht in einer Ebene liegt. Dann ist ein
    Deckel aus einem Fächer keine Fläche, und ein verdrehter Deckel wäre
    schlimmer als eine Absage (Regel 21).

    **Warum ein zweiter Randring die Absage wert ist**, gemessen am 03.09.2026
    an einer 10 mm starken Platte mit durchgehender Bohrung Ø 6 und Senkung Ø 12:
    Die Kegelfläche der Senkung hat zwei Ringe — Ø 12 auf der Oberseite und
    Ø 6 dort, wo sie in die Bohrung übergeht. Mit einem Deckel je Ring entsteht
    ein sauberer Kegelstumpf von 196,65 mm³, wasserdicht und der analytischen
    Rechnung entsprechend. Er ist trotzdem das falsche Werkzeug: Beim Auffüllen
    an der alten Stelle wuchs der Körper um alle 196,65 mm³, obwohl nur 113,1
    davon Senkung waren — der Rest war die **Bohrung**, und ein Querschnitt bei
    z = 3,5 hatte danach kein Loch mehr. Wer die Senkung versetzt, hätte seine
    Bohrung verloren.

    Ein zweiter Ring heißt also: Dieses Merkmal geht in ein anderes über, und
    sein Hohlraum gehört nicht ihm allein. Bis Solidon die Nachbarschaft kennt,
    ist die Absage die richtige Antwort.
    """
    if not feature.face_indices:
        return None

    raw = mesh.raw
    chosen = np.asarray(feature.face_indices, dtype=np.int64)
    if chosen.size == 0 or int(chosen.max()) >= len(raw.faces):
        return None

    patch = trimesh.Trimesh(
        vertices=raw.vertices, faces=np.asarray(raw.faces)[chosen], process=False
    )
    patch.remove_unreferenced_vertices()
    patch.merge_vertices()

    # Eine Randkante gehört genau einem Dreieck des Ausschnitts. Alles andere
    # liegt innen und braucht keinen Deckel.
    edges = patch.edges_sorted
    single = trimesh.grouping.group_rows(  # type: ignore[no-untyped-call]
        edges, require_count=1
    )
    rim = edges[single]
    points = np.asarray(patch.vertices, dtype=float)

    if len(rim) == 0:
        # Ein Ausschnitt ohne Rand ist schon geschlossen — ein Hohlraum ganz im
        # Material. Er braucht keinen Deckel und ist der Körper selbst.
        closed = patch
    else:
        rings = trimesh.graph.connected_components(rim)
        if len(rings) != 1 or len(rim) < 3:
            return None
        ring = points[np.unique(rim)]
        hub = ring.mean(axis=0)
        # Flach in **irgendeiner** Richtung, nicht nur in Z: Eine Kuppe an einer
        # Seitenwand hat ihren Ring in der YZ-Ebene.
        spread = ring - hub
        if float(np.linalg.svd(spread, compute_uv=False)[-1]) > FLAT_RIM * len(ring) ** 0.5:
            return None
        index = len(points)
        cap = np.column_stack([rim[:, 0], rim[:, 1], np.full(len(rim), index, dtype=np.int64)])
        closed = trimesh.Trimesh(
            vertices=np.vstack([points, hub]),
            faces=np.vstack([np.asarray(patch.faces, dtype=np.int64), cap]),
            process=True,
        )
    trimesh.repair.fix_normals(closed)  # type: ignore[no-untyped-call]
    if not closed.is_watertight or closed.volume <= EPS_GEOM:
        return None
    return MeshData.of(closed)


def _feature_direction(feature: Feature, axis: Vec3 | None = None) -> Vec3:
    """Die Richtung dieses Merkmals als Einheitsvektor.

    ``axis`` überschreibt die gemessene; ohne beides gilt Z.
    """
    wanted = axis if axis is not None else feature.params.get("axis", (0.0, 0.0, 1.0))
    given = np.asarray(wanted, dtype=float)
    length = float(np.linalg.norm(given))
    unit = given / length if length > EPS_GEOM else np.array([0.0, 0.0, 1.0])
    return (float(unit[0]), float(unit[1]), float(unit[2]))


def _no_longer_through(
    mesh: MeshData,
    feature: Feature,
    centre: Vec3,
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
) -> bool:
    """Steht im Schlauch dieser Bohrung wieder Material?

    **Der Fall, den niemand ansagt.** Das Werkzeug eines Merkmals ist aus
    seinen gemessenen Kennzahlen gebaut und wandert mit: Eine Bohrung, die als
    durchgehend erkannt wurde, ist nach dem Versetzen genau so lang wie vorher.
    Wandert sie entlang ihrer eigenen Achse oder trifft sie an der neuen Stelle
    auf dickeres Material, geht sie nicht mehr durch. Gemessen am 03.09.2026 an
    einer 10 mm starken Platte, Bohrung Ø 16, um 5 mm in Z versetzt: Unten
    blieben 1,985 mm Material stehen, 398 mm³, und der Körper war wasserdicht
    und einteilig. Geometrisch richtig, für den Kunden eine Überraschung.

    Gemessen wird am **Ergebnis** und nicht an einer Rechnung über Hüllmaße:
    Ein Zylinder im Durchmesser der Bohrung, lang genug für das ganze Teil,
    gegen den fertigen Körper verschnitten. Bleibt dort Volumen, steht Material
    im Schlauch. Ein Vergleich von Hüllmaßen hätte an jedem nicht
    quaderförmigen Teil falschen Alarm gegeben.
    """
    diameter = float(feature.params.get("diameter", 0.0)) - FEATURE_OVERLAP
    if diameter <= EPS_GEOM:
        return False
    reach = float(np.linalg.norm(mesh.bounds.size)) * 2.0
    column = trimesh.creation.cylinder(
        radius=diameter / 2.0, height=reach, sections=FEATURE_SECTIONS
    )
    column.apply_transform(
        trimesh.geometry.align_vectors(  # type: ignore[no-untyped-call]
            np.array([0.0, 0.0, 1.0]), np.asarray(_feature_direction(feature), dtype=float)
        )
    )
    column.apply_translation(np.asarray(centre, dtype=float))
    left = boolean(
        "intersection",
        [MeshData.of(column), mesh],
        quality=quality,
        seed=seed,
        allow_empty=True,
        cancelled=cancelled,
    )
    # **Der leere Schnitt ist der gute Fall, und er darf nicht rechnen.** Geht
    # die Bohrung noch durch, bleibt vom Verschnitt nichts übrig — und ein Netz
    # ohne Dreiecke nach seinem Volumen zu fragen teilt in ``trimesh`` durch
    # null (``RuntimeWarning: invalid value encountered in divide``). Die Suite
    # macht daraus einen Fehler (``filterwarnings = ["error"]``), und gemessen
    # am 03.09.2026 riss genau daran der erste Lauf des Verdoppelns.
    remaining = left.mesh.raw
    if len(remaining.faces) == 0:
        return False
    return bool(remaining.volume > EPS_GEOM)


def _throughness_lost(
    mesh: MeshData,
    feature: Feature,
    centre: Vec3,
    op: str,
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
) -> list[Finding]:
    """Der Befund dazu — leer, wenn die Bohrung weiter durchgeht.

    Ein Hinweis und keine Ausnahme: Das Ergebnis ist richtig gerechnet, es ist
    nur nicht das, was der Kunde erwartet hat. Der Satz nennt deshalb, woran es
    liegt, und nicht nur, dass es so ist (§2.7).
    """
    if not feature.params.get("through"):
        return []
    if not _no_longer_through(
        mesh, feature, centre, quality=quality, seed=seed, cancelled=cancelled
    ):
        return []
    return [
        Finding(
            code=f"{op}.no_longer_through",
            severity="warning",
            message=_(
                "Diese Bohrung ging durch das Teil und tut es an der neuen Stelle "
                "nicht mehr — ihre Achse durchquert das Material dort nicht ganz."
            ),
            feature_ids=(feature.id,),
            location=centre,
        )
    ]


def _between_the_mouths(mesh: MeshData, feature: Feature, centre: Vec3) -> MeshData | None:
    """Ein Schnittkörper, der genau so weit reicht wie das Merkmal selbst.

    **Warum die konvexe Hülle dafür nicht genügt.** ``plug`` beschneidet seinen
    Stopfen an :func:`~app.core.geom.prepare.shell`, und für einen massiven
    Körper ist das richtig: Die Hülle *ist* er. Für ein U-Profil ist sie der
    volle Kasten — gemessen 72 000 gegen 27 000 mm³ —, und ein Überstand, der
    in die Nut ragt, liegt **innerhalb** der Hülle. Genau das hat Robert am
    03.09.2026 an einem Kundenteil gesehen: ein erhabener Kranz um die alte
    Stelle. Nachgebaut an einem U-Profil mit 5 mm Bodenwand und einer Bohrung
    Ø 7,98: **76,4 mm³** standen nach dem Versetzen im Nutraum, vorher null.

    Die Merkmalsfläche weiß es besser als jede Hülle: Sie **ist** die Wand des
    Hohlraums, ihre Ausdehnung entlang der Merkmalsachse ist seine Tiefe, und
    ihre Ränder liegen in den Mündungen. Der Schnittkörper ist deshalb ein
    Zylinder um die Achse, der genau von der einen Mündung zur anderen reicht —
    breit genug für jedes Werkzeug, das hier hineingeht, und in der Länge
    genau.

    ``None``, wenn das Merkmal keine Flächen führt. Dann bleibt es beim
    Hüllschnitt, der für massive Körper trägt.
    """
    if not feature.face_indices:
        return None
    raw = mesh.raw
    chosen = np.asarray(feature.face_indices, dtype=np.int64)
    if chosen.size == 0 or int(chosen.max()) >= len(raw.faces):
        return None

    points = np.asarray(raw.vertices, dtype=float)[np.unique(np.asarray(raw.faces)[chosen])]
    direction = np.asarray(_feature_direction(feature), dtype=float)
    measured = np.asarray([float(value) for value in feature.params["centre"]], dtype=float)
    along = (points - measured) @ direction
    reach = float(along.max() - along.min())
    if reach <= EPS_GEOM:
        return None

    # Breit genug für alles, was als Werkzeug hineingeht — geschnitten wird nur
    # in der Länge. Der Radius kommt aus der Ausdehnung der Fläche quer zur
    # Achse, damit auch eine Senkung hineinpasst, die weiter ist als ihr Loch.
    across = points - measured - np.outer(along, direction)
    radius = float(np.linalg.norm(across, axis=1).max()) + FEATURE_OVERLAP * 2.0

    cut = trimesh.creation.cylinder(radius=radius, height=reach, sections=FEATURE_SECTIONS)
    cut.apply_transform(
        trimesh.geometry.align_vectors(  # type: ignore[no-untyped-call]
            np.array([0.0, 0.0, 1.0]), direction
        )
    )
    middle = float(along.min() + along.max()) / 2.0
    cut.apply_translation(np.asarray(centre, dtype=float) + direction * middle)
    return MeshData.of(cut)


def _closed_at(
    mesh: MeshData,
    feature: Feature,
    centre: Vec3,
    cavity: bool,
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
) -> BooleanOutcome:
    """Das Merkmal an dieser Stelle schließen: gefüllt, wenn es ein Hohlraum
    ist, abgetragen, wenn es Material ist.

    **Ein Werkzeug, das beim Abtragen richtig ist, ist beim Auffüllen zu
    groß.** Der Körper eines Merkmals wird absichtlich etwas größer gebaut, als
    gemessen wurde (:data:`FEATURE_OVERLAP`), und eine durchgehende Bohrung
    bekommt mindestens ihren Durchmesser als Länge, damit sie das Material auf
    jeden Fall trifft — sonst stünde eine Boolesche vor zusammenfallenden
    Flächen (§39). Beim Ausschneiden macht dieser Überstand nichts. Beim
    Vereinen trägt er außen auf.

    **Gemessen am 03.09.2026**, gefunden von Robert am eigenen Kundenmodell
    („die Bohrung wird richtig verschoben, aber an der alten Stelle steht das
    Material dann oben und unten über") und nachgebaut an einer 10 mm starken
    Platte mit durchgehender Bohrung Ø 16: Nach dem Versetzen war das
    Teil **16,03 mm hoch statt 10**, der Stopfen stand oben und unten drei
    Millimeter über, und das Volumen wuchs von 21 995 auf 23 600 mm³. Der
    Körper blieb dabei wasserdicht.

    :func:`~app.core.geom.prepare.plug` löst dasselbe seit langem mit einer
    Zeile: erst mit der Hülle verschneiden, dann vereinen. Genau die fehlte
    hier, an vier Stellen — Versetzen, Entfernen, Drehen und Ändern schließen
    alle nach demselben Muster.

    Abgetragen wird ohne Schnitt: Ein Zapfen, der über die Hülle hinausragt,
    **ist** das Teil an dieser Stelle, und ein zu großes Messer schneidet nur
    Luft.
    """
    tool = _tool_for(mesh, feature, centre)
    if cavity:
        # **Erst an den Mündungen, sonst an der Hülle.** Die Merkmalsfläche
        # kennt die Tiefe des Hohlraums genau; die konvexe Hülle kennt nur den
        # Umriss des ganzen Teils und lässt einen Überstand stehen, der in eine
        # Nut oder einen Innenraum ragt (siehe :func:`_between_the_mouths`).
        limit = _between_the_mouths(mesh, feature, centre) or shell(mesh)
        tool = boolean(
            "intersection", [tool, limit], quality=quality, seed=seed, cancelled=cancelled
        ).mesh
    return boolean(
        "union" if cavity else "difference",
        [mesh, tool],
        quality=quality,
        seed=seed,
        cancelled=cancelled,
    )


def _tool_for(
    mesh: MeshData, feature: Feature, centre: Vec3, scale: float = 1.0, axis: Vec3 | None = None
) -> MeshData:
    """Der Werkzeugkörper dieses Merkmals, an ``centre`` gesetzt.

    Zwei Wege, und welcher gilt, entscheidet die Merkmalsart: Wo die
    Kennzahlen den Körper genau beschreiben (Bohrung, Zapfen), baut
    :func:`_feature_solid` ihn daraus — das trägt auch für eine durchgehende
    Bohrung, deren Ausschnitt **zwei** Randringe hat und die ein Deckel aus
    einem Fächer deshalb nicht schließt. Sonst kommt er aus den Flächen des
    Merkmals (:func:`_feature_body`) und wird verschoben, gedreht und
    skaliert wie er ist.

    Baut sich der Körper nicht sicher, endet der Aufruf mit einem Satz, der
    den **heutigen** Grund nennt und nicht den von gestern — siehe
    :data:`_NO_OWN_BODY`.
    """
    if feature.kind in PARAMETRIC_KINDS:
        return _feature_solid(feature, centre, scale=scale, axis=axis)

    built = _feature_body(mesh, feature)
    if built is None:
        raise ValidationError(
            field="at_feature",
            detail=_NO_OWN_BODY,
            values={"feature": feature.id, "kind": feature.kind},
            constraint="not_movable",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )

    measured = [float(value) for value in feature.params["centre"]]
    matrix = np.eye(4)
    if axis is not None:
        from_axis = np.asarray(feature.params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
        matrix = np.asarray(
            trimesh.geometry.align_vectors(  # type: ignore[no-untyped-call]
                from_axis, np.asarray(axis, dtype=np.float64)
            ),
            dtype=np.float64,
        )
    body = built.raw.copy()
    body.apply_translation(-np.asarray(measured, dtype=float))
    if scale != 1.0:
        body.apply_scale(scale)  # type: ignore[no-untyped-call]
    body.apply_transform(matrix)
    body.apply_translation(np.asarray(centre, dtype=float))
    return MeshData.of(body)


@op_params
class MoveFeatureParams(BaseParams):
    at_feature: str = param(
        title=_("Merkmal"),
        default="",
        kind="feature",
        required=True,
        placement="front",
        doc=_(
            "Das erkannte Merkmal, das versetzt wird. Ein Klick darauf im Objektbaum "
            "oder in der Ansicht wählt es aus."
        ),
    )
    x: float = param(
        title=_("X"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_("Die neue Mitte des Merkmals. Beim Anklicken steht hier seine heutige."),
    )
    y: float = param(
        title=_("Y"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_("Die neue Mitte des Merkmals. Beim Anklicken steht hier seine heutige."),
    )
    z: float = param(
        title=_("Z"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_("Die neue Mitte des Merkmals. Beim Anklicken steht hier seine heutige."),
    )


def _movable_feature(source: SceneObject, name: str, op: str) -> Feature:
    """Das gewählte Merkmal — oder ein Satz, warum es nicht geht (Regel 17).

    **Gefragt wird das Register, und zwar nach der aufrufenden Operation.**
    ``applies_to`` sagt je Operation, welche Merkmalsarten sie annimmt, und es
    stand bis zum 03.09.2026 nur im Menü und im Panel: Wer eine Operation über
    Chat oder Kommandozeile rief, kam daran vorbei. Gemessen an jenem Tag
    kostete das zwei stille Falschergebnisse — ``resize_feature`` änderte eine
    **Bohrung** am exakten Kern und an der Materialkompensation vorbei
    (46 997,6 auf 45 737,0 mm³), und ``rotate_feature`` kippte eine **Kuppel**,
    die keine Lage hat, und nahm dabei 112 von 24 448 mm³ mit. Beide Male blieb
    der Körper wasserdicht, und nichts wurde rot.

    Der Satz dazu kommt aus derselben Tabelle, aus der das Panel seine
    ausgegraute Zeile beschriftet — ``perceive.actions.reason_against``.
    """
    from app.core.perceive.actions import reason_against

    feature = source.features.get(name)
    if feature is None:
        raise ValidationError(
            field="at_feature",
            detail=_("Dieses Merkmal gibt es an diesem Objekt nicht."),
            values={"feature": name, "object": source.id},
            constraint="unknown_feature",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    against = reason_against(op, feature.kind)
    if against is None:
        return feature
    raise ValidationError(
        field="at_feature",
        detail=against,
        values={"feature": name, "kind": feature.kind, "op": op},
        constraint="not_movable",
        suggestions=(CHANGE_SELECTION, CANCEL),
    )


#: Wenn die Flächen eines beweglichen Merkmals es nicht als eigenen Körper
#: begrenzen.
#:
#: Hier stand bis zum 03.09.2026 eine zweite Ausgabe der Gründetabelle aus
#: ``perceive.actions`` — dieselben fünf Sätze, zweimal im Programm, und in
#: beiden dieselben zwei veraltet. Was den Kunden erreicht, kommt jetzt aus
#: einer Quelle; hier bleibt der eine Fall, den das Panel nicht kennt, weil er
#: nicht an der Merkmalsart hängt, sondern am Netz.
_NO_OWN_BODY: Final = _(
    "Dieses Merkmal geht in ein anderes über — eine Senkung über einer "
    "Bohrung etwa —, und sein Hohlraum gehört nicht ihm allein. Versetzt "
    "würde die Bohrung darunter mit zugehen. Wählen Sie das Merkmal in der "
    "Mitte, oder verschließen Sie die Bohrung und legen beides neu an."
)


@register_op(
    name="move_feature",
    title=_("Merkmal verschieben"),
    category="holes",
    params=MoveFeatureParams,
    consumes=1,
    produces=1,
    applies_to=list(MOVABLE_KINDS),
    touches_features=True,
    deterministic=False,
    doc=_(
        "Versetzt ein erkanntes Merkmal an eine andere Stelle: Bohrung, Zapfen, "
        "Senkung, Verjüngung, Kuppel oder Pfanne."
    ),
)
def move_feature(ctx: OpContext) -> OpResult:
    """Ein erkanntes Merkmal an eine andere Stelle — in einem Schritt.

    **Der Kunde hat es verlangt, und der Umweg war schlecht.** „Move existing
    holes and other recognised details/features" war bei 1 von 5 der einzige
    konkrete Punkt der Umfrage vom 03.09.2026. Möglich war es vorher nur über
    zwei Schritte: verschließen und an neuen Zahlen neu bohren. Das ergibt
    dieselbe Geometrie und ein **anderes** Merkmal — jede Passung, die auf die
    alte Kennung zeigte, verlor ihren Bezug (``fit.missing_feature``).

    **Innen ist es dasselbe Paar wie beim Löschen und beim Ändern**: An der
    alten Stelle das Gegenteil dessen, was das Merkmal ist, an der neuen das
    Merkmal selbst. Ein Hohlraum wird also gefüllt und neu ausgeschnitten, ein
    Zapfen abgetragen und neu angesetzt. Beide Wege gehen über die Boolesche
    Rückfallkette, und die benutzte Stufe steht im Ergebnis (§39).

    Die Kennung reist mit: Sie ist das Einzige, was den Unterschied zum Umweg
    von Hand ausmacht.
    """
    params = cast(MoveFeatureParams, ctx.params)
    source = ctx.inputs[0]
    feature = _movable_feature(source, params.at_feature, "move_feature")
    # **Erst in eine Liste, dann drei Werte einzeln.** Ein Generatorausdruck über
    # die Achsen hat für mypy keine feste Länge; ``Vec3`` verlangt genau drei.
    measured = [float(value) for value in feature.params["centre"]]
    centre: Vec3 = (measured[0], measured[1], measured[2])
    target: Vec3 = (params.x, params.y, params.z)

    if all(abs(a - b) <= EPS_GEOM for a, b in zip(centre, target, strict=True)):
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="move_feature.unchanged",
                    severity="info",
                    message=_("Das Merkmal liegt schon dort — nichts zu versetzen."),
                    feature_ids=(feature.id,),
                )
            ],
        )

    body = as_mesh_data(source.mesh)
    cavity = _feature_is_a_cavity(feature)
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle geschlossen …")))
    closed = _closed_at(
        body, feature, centre, cavity, quality=ctx.quality, seed=ctx.seed, cancelled=ctx.cancelled
    )
    ctx.progress(0.6, str(_("Das Merkmal wird an seiner neuen Stelle gesetzt …")))
    placed = boolean(
        "difference" if cavity else "union",
        [closed.mesh, _tool_for(as_mesh_data(source.mesh), feature, target)],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    moved = dataclasses.replace(
        feature,
        params={**feature.params, "centre": target},
        provenance="generated",
    )
    findings = [*closed.findings, *placed.findings]
    # Nur, wenn sie entlang ihrer eigenen Achse gewandert ist: Quer versetzt
    # bleibt eine durchgehende Bohrung durchgehend, und die Messung kostet eine
    # Boolesche, die dann nichts zu sagen hätte.
    travel = np.asarray(target, dtype=float) - np.asarray(centre, dtype=float)
    axial = float(np.dot(travel, np.asarray(_feature_direction(feature), dtype=float)))
    if abs(axial) > EPS_GEOM:
        findings += _throughness_lost(
            placed.mesh,
            feature,
            target,
            "move_feature",
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features={**source.features, feature.id: moved},
            )
        ],
        findings=findings,
        solver=placed.solver,
    )


def _free_feature_id(source: SceneObject, kind: str) -> FeatureId:
    """Eine Kennung, die es an diesem Körper noch nicht gibt.

    Dieselbe Form, die die Erkennung vergibt (``hole_1``, ``pin_2``), damit
    Kopie und Original im Objektbaum nebeneinander gleich aussehen. Gesucht
    wird die kleinste freie Zahl und nicht die nächste nach der höchsten: Wer
    eine Bohrung löscht und danach eine verdoppelt, bekommt die Lücke gefüllt
    statt eine Kennung, die auf eine Zählung verweist, die niemand sieht.
    """
    number = 1
    while f"{kind}_{number}" in source.features:
        number += 1
    return f"{kind}_{number}"


@op_params
class DuplicateFeatureParams(BaseParams):
    at_feature: str = param(
        title=_("Merkmal"),
        default="",
        kind="feature",
        required=True,
        placement="front",
        doc=_(
            "Das erkannte Merkmal, das ein zweites Mal entsteht. Ein Klick darauf im "
            "Objektbaum oder in der Ansicht wählt es aus."
        ),
    )
    x: float = param(
        title=_("X"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte der Kopie. Beim Anklicken steht hier die alte, um einen "
            "Durchmesser versetzt."
        ),
    )
    y: float = param(
        title=_("Y"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte der Kopie. Beim Anklicken steht hier die alte, um einen "
            "Durchmesser versetzt."
        ),
    )
    z: float = param(
        title=_("Z"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte der Kopie. Beim Anklicken steht hier die alte, um einen "
            "Durchmesser versetzt."
        ),
    )


@register_op(
    name="duplicate_feature",
    title=_("Merkmal verdoppeln"),
    category="holes",
    params=DuplicateFeatureParams,
    reversible=True,
    consumes=1,
    produces=1,
    applies_to=list(MOVABLE_KINDS),
    deterministic=False,
    doc=_(
        "Legt ein erkanntes Merkmal ein zweites Mal an: Bohrung, Zapfen, Senkung, "
        "Verjüngung, Kuppel oder Pfanne."
    ),
)
def duplicate_feature(ctx: OpContext) -> OpResult:
    """Ein erkanntes Merkmal ein zweites Mal — die halbe Bewegung des Versetzens.

    **Der weiteste Weg von allen war das** (gemessen 3d-druck-d4, 03.09.2026):
    Wer eine zweite Bohrung wie die erste wollte, rief *Bohrung setzen* und
    tippte Durchmesser, Tiefe, Achse und drei Koordinaten von Hand ab — obwohl
    Solidon alle vier Werte gemessen hat und im Merkmalspanel anzeigt. Vier
    abgeschriebene Zahlen sind vier Gelegenheiten für einen Tippfehler, und
    keine davon ist nötig.

    Innen ist es die zweite Hälfte von :func:`move_feature` ohne die erste: An
    der alten Stelle bleibt alles, an der neuen entsteht dasselbe Merkmal. Ein
    Hohlraum wird also geschnitten, ein Zapfen angesetzt.

    **Die Kopie bekommt eine eigene Kennung**, und das ist der Unterschied zum
    Versetzen: Dort reist die Kennung mit, weil es dasselbe Merkmal bleibt;
    hier gibt es hinterher zwei, und Passungen, die auf das Original zeigen,
    dürfen davon nichts merken.
    """
    params = cast(DuplicateFeatureParams, ctx.params)
    source = ctx.inputs[0]
    feature = _movable_feature(source, params.at_feature, "duplicate_feature")
    measured = [float(value) for value in feature.params["centre"]]
    centre: Vec3 = (measured[0], measured[1], measured[2])
    target: Vec3 = (params.x, params.y, params.z)

    if all(abs(a - b) <= EPS_GEOM for a, b in zip(centre, target, strict=True)):
        # Kein Fehler, sondern ein Hinweis: Die Boolesche liefe auf sich selbst
        # und ließe den Körper, wie er ist. Regel 19 — was zurücknehmbar ist,
        # bekommt keine Nachfrage, und was nichts tut, keine Ausnahme.
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="duplicate_feature.unchanged",
                    severity="info",
                    message=_(
                        "Ein zweites Merkmal an derselben Stelle ist dasselbe Merkmal — "
                        "nichts verdoppelt."
                    ),
                    feature_ids=(feature.id,),
                )
            ],
        )

    body = as_mesh_data(source.mesh)
    cavity = _feature_is_a_cavity(feature)
    ctx.progress(0.2, str(_("Das Merkmal wird an der neuen Stelle angelegt …")))
    change: BooleanKind = "difference" if cavity else "union"
    placed = boolean(
        change,
        [body, _tool_for(body, feature, target)],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    findings = [*placed.findings]
    # **Eine Kopie, die nichts geschnitten hat, ist die stille Variante des
    # Fehlers**, den Robert heute am Stopfen gefunden hat: Im Verlauf steht ein
    # Schritt, im Bild liegt dasselbe Teil. Wer eine Bohrung neben den Körper
    # verdoppelt, soll es lesen und nicht suchen.
    #
    # **Und diese Prüfung gehört hierher und ausdrücklich nicht zu den anderen
    # vier.** Sie vergleicht das Volumen davor und danach, und beim Verdoppeln
    # ist die Differenz genau das Merkmal. Versetzen, Drehen und Ändern führen
    # **zwei** Boolesche aus, die sich gegenseitig aufheben — ein gelungenes
    # Versetzen ändert das Volumen um nichts. Dort eingebaut würde derselbe
    # Aufruf bei **jedem** Erfolg anschlagen; gemessen am 03.09.2026 bleibt das
    # Volumen einer versetzten Bohrung auf die Stelle genau gleich.
    nothing = without_effect(source.mesh, placed.mesh, change, ctx.profile)
    if nothing is not None:
        findings.append(nothing)
    findings += _throughness_lost(
        placed.mesh,
        feature,
        target,
        "duplicate_feature",
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    copy = dataclasses.replace(
        feature,
        id=_free_feature_id(source, feature.kind),
        params={**feature.params, "centre": target},
        provenance="generated",
    )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features={**source.features, copy.id: copy},
            )
        ],
        findings=findings,
        solver=placed.solver,
    )


@op_params
class RemoveFeatureParams(BaseParams):
    at_feature: str = param(
        title=_("Merkmal"),
        default="",
        kind="feature",
        required=True,
        placement="front",
        doc=_("Das erkannte Merkmal, das entfernt wird."),
    )


@register_op(
    name="remove_feature",
    title=_("Merkmal entfernen"),
    category="holes",
    params=RemoveFeatureParams,
    consumes=1,
    produces=1,
    applies_to=list(MOVABLE_KINDS),
    touches_features=True,
    deterministic=False,
    doc=_(
        "Entfernt ein erkanntes Merkmal: Bohrung, Zapfen, Senkung, Verjüngung, Kuppel oder Pfanne."
    ),
)
def remove_feature(ctx: OpContext) -> OpResult:
    """Ein erkanntes Merkmal wegnehmen — die halbe Bewegung des Versetzens.

    „Ich will die auch löschen können, also jede Operation" (Robert,
    03.09.2026). Für ein erkanntes Merkmal ist das derselbe Motor wie
    :func:`move_feature`, nur mit einem Gang: An der alten Stelle steht das
    Gegenteil dessen, was das Merkmal ist, und danach nichts mehr. Eine
    Bohrung wird gefüllt, ein Zapfen abgetragen.

    **Die Kennung geht mit und bleibt nicht als Verweis stehen.** Ein Merkmal,
    das im Objekt weiterlebt, obwohl seine Geometrie fort ist, ist genau der
    Zustand, den ``fit.missing_feature`` später als Verletzung meldet — und
    dann sucht der Kunde an einem Teil, das in Ordnung ist. Ein Befund sagt es
    stattdessen sofort.
    """
    params = cast(RemoveFeatureParams, ctx.params)
    source = ctx.inputs[0]
    feature = _movable_feature(source, params.at_feature, "remove_feature")
    measured = [float(value) for value in feature.params["centre"]]
    centre: Vec3 = (measured[0], measured[1], measured[2])

    cavity = _feature_is_a_cavity(feature)
    ctx.progress(0.2, str(_("Das Merkmal wird geschlossen …")))
    closed = _closed_at(
        as_mesh_data(source.mesh),
        feature,
        centre,
        cavity,
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    remaining = {name: entry for name, entry in source.features.items() if name != feature.id}
    findings = [
        *closed.findings,
        Finding(
            code="remove_feature.gone",
            severity="info",
            message=_(
                "Das Merkmal ist entfernt. Spätere Schritte und Passungen, die auf es "
                "verweisen, finden es nicht mehr."
            ),
            feature_ids=(feature.id,),
            values={"feature": feature.id, "kind": feature.kind},
        ),
    ]
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=closed.mesh, features=remaining)],
        findings=findings,
        solver=closed.solver,
    )


@op_params
class RotateFeatureParams(BaseParams):
    at_feature: str = param(
        title=_("Merkmal"),
        default="",
        kind="feature",
        required=True,
        placement="front",
        doc=_("Das erkannte Merkmal, das gedreht wird."),
    )
    axis: Axis = param(
        title=_("Achse"),
        default="x",
        choices=("x", "y", "z"),
        placement="front",
        doc=_("Um welche Achse gedreht wird. Gedreht wird um die Mitte des Merkmals."),
    )
    angle: float = param(
        title=_("Winkel"),
        default=90.0,
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        placement="front",
        doc=_("Wie weit gedreht wird, in Grad."),
    )


@register_op(
    name="rotate_feature",
    title=_("Merkmal drehen"),
    category="holes",
    params=RotateFeatureParams,
    consumes=1,
    produces=1,
    # **Ohne die Kugel.** Sie hat keine Lage, die sich drehen ließe — gedreht
    # sähe sie aus wie vorher, und eine Handlung ohne Wirkung ist schlechter
    # als keine (Roberts „alles, was bei den jeweiligen sinnvoll ist").
    applies_to=["hole", "pin", "cone"],
    touches_features=True,
    deterministic=False,
    doc=_("Kippt ein erkanntes Merkmal um seine Mitte: Bohrung, Zapfen, Senkung oder Verjüngung."),
)
def rotate_feature(ctx: OpContext) -> OpResult:
    """Ein erkanntes Merkmal kippen — dieselbe Maschine, eine Matrix dazwischen.

    **Achse und Winkel, wie bei** :func:`rotate_object`. Das Register spricht
    diese Sprache schon, und wer einen Körper um Z gedreht hat, sucht für eine
    Bohrung nicht nach einer anderen Bedienung.

    **Gedreht wird um die Mitte des Merkmals**, nicht um den Ursprung: Eine
    Bohrung, die beim Kippen davonwandert, ist keine gekippte Bohrung, sondern
    zwei Änderungen, von denen der Kunde eine wollte.

    Eine Kugel bekommt diese Operation nicht: Sie hat keine Lage, die sich
    drehen ließe. Das steht in :data:`MOVABLE_KINDS` noch nicht getrennt, weil
    ``sphere`` dort ohnehin nicht steht — kommt sie dazu, gehört hier eine
    eigene Liste hin.
    """
    params = cast(RotateFeatureParams, ctx.params)
    source = ctx.inputs[0]
    feature = _movable_feature(source, params.at_feature, "rotate_feature")
    measured = [float(value) for value in feature.params["centre"]]
    centre: Vec3 = (measured[0], measured[1], measured[2])

    if abs(params.angle) <= EPS_DISPLAY:
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="rotate_feature.unchanged",
                    severity="info",
                    message=_("Ohne Winkel bleibt alles, wie es ist."),
                    feature_ids=(feature.id,),
                )
            ],
        )

    turned_axis = _turned(feature, params.axis, params.angle)
    cavity = _feature_is_a_cavity(feature)
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle geschlossen …")))
    closed = _closed_at(
        as_mesh_data(source.mesh),
        feature,
        centre,
        cavity,
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )
    ctx.progress(0.6, str(_("Das Merkmal wird gedreht gesetzt …")))
    placed = boolean(
        "difference" if cavity else "union",
        [closed.mesh, _tool_for(as_mesh_data(source.mesh), feature, centre, axis=turned_axis)],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    moved = dataclasses.replace(
        feature,
        params={**feature.params, "axis": turned_axis},
        provenance="generated",
    )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features={**source.features, feature.id: moved},
            )
        ],
        findings=[*closed.findings, *placed.findings],
        solver=placed.solver,
    )


def _turned(feature: Feature, axis: Axis, angle: float) -> Vec3:
    """Die Achse des Merkmals, um ``axis`` um ``angle`` Grad gedreht."""
    direction = np.asarray(feature.params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
    matrix = trimesh.transformations.rotation_matrix(  # type: ignore[no-untyped-call]
        math.radians(angle), AXIS_NORMALS[axis]
    )
    spun = np.asarray(matrix, dtype=float)[:3, :3] @ direction
    length = float(np.linalg.norm(spun)) or 1.0
    spun = spun / length
    return (float(spun[0]), float(spun[1]), float(spun[2]))


@op_params
class ResizeFeatureParams(BaseParams):
    at_feature: str = param(
        title=_("Merkmal"),
        default="",
        kind="feature",
        required=True,
        placement="front",
        doc=_("Das erkannte Merkmal, dessen Maß geändert wird."),
    )
    diameter: float = param(
        title=_("Durchmesser"),
        default=8.0,
        unit="mm",
        minimum=0.5,
        maximum=200.0,
        placement="front",
        doc=_("Der neue Durchmesser. Beim Anklicken steht hier sein gemessener."),
    )


@register_op(
    name="resize_feature",
    title=_("Merkmal ändern"),
    category="holes",
    params=ResizeFeatureParams,
    consumes=1,
    produces=1,
    # **Nicht ``hole``** — dafür gibt es ``resize_hole`` mit eigenem Weg durch
    # den exakten Kern und einer Materialkompensation, die für ein Loch gilt und
    # für einen Zapfen andersherum liefe. Die beiden überschneiden sich deshalb
    # nicht, und ``perceive.actions`` legt sie zu **einer** Zeile zusammen.
    applies_to=["pin", "cone", "sphere"],
    touches_features=True,
    deterministic=False,
    doc=_(
        "Ändert den Durchmesser eines erkannten Merkmals: Zapfen, Senkung, "
        "Verjüngung, Kuppel oder Pfanne."
    ),
)
def resize_feature(ctx: OpContext) -> OpResult:
    """Den Durchmesser eines erkannten Merkmals ändern — Zapfen, Kegel, Kugel.

    **Warum das nicht** :func:`resize_hole` **mit erweitertem ``applies_to``
    ist.** Die Bohrung hat einen eigenen Weg durch den exakten Kern
    (``edit.resize_bore``) und eine Materialkompensation, die für ein Loch
    gilt und für einen Zapfen genau andersherum liefe: Ein Loch wird beim
    Drucken enger, ein Zapfen dicker. Zwei Operationen, eine Zeile im Panel —
    ``perceive.actions`` legt sie zusammen, und der Kunde sieht *Größe ändern*
    und nicht zwei Einträge, von denen einer immer grau ist.

    Sonst ist es derselbe Motor: an der alten Stelle abtragen, mit dem neuen
    Maß wieder ansetzen.
    """
    params = cast(ResizeFeatureParams, ctx.params)
    source = ctx.inputs[0]
    feature = _movable_feature(source, params.at_feature, "resize_feature")
    measured = [float(value) for value in feature.params["centre"]]
    centre: Vec3 = (measured[0], measured[1], measured[2])
    previous = float(feature.params.get("diameter", 0.0))

    if abs(params.diameter - previous) <= EPS_GEOM:
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="resize_feature.unchanged",
                    severity="info",
                    message=_("Das Merkmal hat dieses Maß schon."),
                    feature_ids=(feature.id,),
                )
            ],
        )

    scale = params.diameter / previous if previous > EPS_GEOM else 1.0
    cavity = _feature_is_a_cavity(feature)
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle geschlossen …")))
    closed = _closed_at(
        as_mesh_data(source.mesh),
        feature,
        centre,
        cavity,
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )
    ctx.progress(0.6, str(_("Das Merkmal wird mit dem neuen Maß gesetzt …")))
    placed = boolean(
        "difference" if cavity else "union",
        [closed.mesh, _tool_for(as_mesh_data(source.mesh), feature, centre, scale=scale)],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    changed = dataclasses.replace(
        feature,
        params={**feature.params, "diameter": params.diameter},
        provenance="generated",
    )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features={**source.features, feature.id: changed},
            )
        ],
        findings=[*closed.findings, *placed.findings],
        solver=placed.solver,
    )


@op_params
class ResizeHoleParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=5.0,
        unit="mm",
        minimum=0.2,
        maximum=200.0,
        placement="front",
        doc=_(
            "Neuer fertiger Durchmesser der erkannten Bohrung. Beim Anklicken steht "
            "hier zuerst ihr gemessenes Maß."
        ),
    )
    at_feature: str = param(
        title=_("Bohrung"),
        default="",
        kind="feature",
        required=True,
        # Vorn, nicht hinter der Klappe: Ein Pflichtfeld ohne „— keines —"
        # steht vorausgewählt auf der ersten Bohrung, und zugeklappt wäre das
        # eine stille Wahl (Regel 21) — über das Menü geöffnet sah der Kunde
        # nur den Durchmesser.
        placement="front",
        doc=_(
            "Die erkannte Bohrung, deren Durchmesser geändert wird. Ein Klick auf "
            "die Bohrung trägt sie ein."
        ),
    )
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=False,
        placement="advanced",
        doc=_(
            "Vergrößert das gewählte Fertigmaß um den Wert aus dem Materialprofil. "
            "Aus bleibt das gemessene Maß unverändert."
        ),
    )


@register_op(
    name="resize_hole",
    title=_("Bohrung ändern"),
    category="holes",
    params=ResizeHoleParams,
    consumes=1,
    produces=1,
    applies_to=["hole"],
    touches_features=True,
    deterministic=False,
    doc=_("Ändert den Durchmesser einer erkannten Bohrung."),
)
def resize_hole(ctx: OpContext) -> OpResult:
    """Der gemeinsame Kundenweg für STL-Netze und exakte STEP-Körper."""
    params = cast(ResizeHoleParams, ctx.params)
    source = ctx.inputs[0]
    feature = _chosen_bore(source, params.at_feature)
    centre = _bore_vector(feature, "centre")
    axis = _bore_vector(feature, "axis")
    previous = _bore_number(feature, "diameter")
    depth = _bore_number(feature, "depth")
    cut = bore_diameter(params.diameter, ctx.profile, params.compensate)

    if source.kind == "brep":
        from app.core.brep import edit
        from app.core.brep.features import features_of
        from app.core.brep.kernel import Solid

        if not isinstance(source.mesh, Solid):
            raise InternalError(
                detail="a scene object marked as brep does not carry a Solid",
                values={"object": source.id},
            )
        if abs(cut - previous) <= EPS_GEOM:
            return OpResult(outputs=[source], findings=[_unchanged_bore(cut)])
        solid = edit.resize_bore(
            source.mesh,
            position=centre,
            direction=axis,
            previous_diameter=previous,
            diameter=cut,
            depth=depth,
        )
        if solid.volume <= EPS_GEOM or solid.face_count == 0:
            raise GeometryError(
                title=NOTHING_LEFT_TITLE,
                detail=NOTHING_LEFT_DETAIL,
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        findings: list[Finding] = []
        change: BooleanKind = "difference" if cut > previous else "union"
        nothing = without_effect(source.mesh, solid, change, ctx.profile)
        if nothing is not None:
            findings.append(nothing)
        findings.extend(over_the_edge_along(source.mesh, centre, axis, cut))
        findings.extend(_compensation_findings(params.diameter, cut, params.compensate))
        exact_features = _preserved_exact_features(
            source.features,
            features_of(solid),
            feature,
            cut,
            solid,
        )
        return OpResult(
            outputs=[
                dataclasses.replace(
                    source,
                    mesh=solid,
                    kind="brep",
                    features=exact_features,
                )
            ],
            findings=findings,
        )

    body = as_mesh_data(source.mesh)
    exact_depth = _mesh_bore_depth(body, feature, axis, depth)
    result = resize_bore(
        body,
        position=centre,
        direction=axis,
        previous_diameter=previous,
        diameter=params.diameter,
        depth=exact_depth,
        through=bool(feature.params.get("through", False)),
        profile=ctx.profile,
        compensate=params.compensate,
        quality=ctx.quality,
        seed=ctx.seed,
    )
    if result.solver is None:
        return OpResult(outputs=[source], findings=result.findings)
    resized_feature = _recognised_resized_feature(result.mesh, feature, result.diameter)
    carried = {
        name: entry
        for name, entry in source.features.items()
        if entry.provenance == "generated" and name != feature.id
    }
    # Findet sich die geänderte Bohrung nicht wieder, bleibt der Körper und
    # das Merkmal geht — mit einem Satz darüber. Ihn zu behalten wäre eine
    # Behauptung über etwas, das die Erkennung gerade nicht bestätigt.
    features = (
        {**carried, feature.id: resized_feature} if resized_feature is not None else dict(carried)
    )
    findings = list(result.findings)
    if resized_feature is None:
        findings.append(_bore_no_longer_a_feature(feature, result.diameter))
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features=features)],
        solver=result.solver,
        findings=findings,
    )


def _chosen_bore(source: SceneObject, name: str) -> Feature:
    """Die angeklickte Bohrung oder eine Korrekturmöglichkeit statt Raten."""
    feature = source.features.get(name)
    if feature is None:
        raise ValidationError(
            field="at_feature",
            detail=_("Dieses Merkmal gibt es an diesem Objekt nicht."),
            value=name,
            constraint="unknown_feature",
            values={"known": ", ".join(sorted(source.features))},
        )
    if feature.kind != "hole":
        raise ValidationError(
            field="at_feature",
            detail=_("Zum Ändern des Durchmessers muss eine Bohrung gewählt sein."),
            value=name,
            constraint="not_a_hole",
            values={"kind": feature.kind},
        )
    return feature


def _bore_vector(feature: Feature, name: str) -> tuple[float, float, float]:
    """Eine gespeicherte Dreierkoordinate mit einem verständlichen Fehler."""
    value = feature.params.get(name)
    if (
        not isinstance(value, tuple | list)
        or len(value) != 3
        or not all(isinstance(entry, int | float) for entry in value)
    ):
        raise ValidationError(
            field="at_feature",
            detail=_(
                "Diese erkannte Bohrung enthält keine verwendbaren Geometriedaten. "
                "Lassen Sie die Merkmale neu erkennen und wählen Sie sie danach erneut."
            ),
            value=feature.id,
            constraint="no_geometry",
        )
    return (float(value[0]), float(value[1]), float(value[2]))


def _bore_number(feature: Feature, name: str) -> float:
    """Ein positives Bohrungsmaß aus der Erkennung."""
    value = feature.params.get(name)
    if not isinstance(value, int | float) or float(value) <= EPS_GEOM:
        raise ValidationError(
            field="at_feature",
            detail=_(
                "Diese erkannte Bohrung enthält keine verwendbaren Geometriedaten. "
                "Lassen Sie die Merkmale neu erkennen und wählen Sie sie danach erneut."
            ),
            value=feature.id,
            constraint="no_geometry",
        )
    return float(value)


def _mesh_bore_depth(
    mesh: MeshData,
    feature: Feature,
    axis: tuple[float, float, float],
    fallback: float,
) -> float:
    """Liest die volle Zylinderlänge aus den gewählten Wanddreiecken.

    Die Merkmalswerte sind für Auswahl und Anzeige stabil quantisiert. Für
    das Werkzeug zählt dagegen jeder vorhandene Eckpunkt: Ein um wenige
    Zehntausendstel verkürzter Ring kann ein Sackloch bei der nächsten
    Erkennung fälschlich als durchgehend erscheinen lassen.
    """
    raw = mesh.raw
    valid = [index for index in feature.face_indices if 0 <= index < len(raw.faces)]
    length = math.sqrt(sum(value * value for value in axis))
    if not valid or length <= EPS_GEOM:
        return fallback
    unit = tuple(value / length for value in axis)
    vertices = raw.vertices[raw.faces[valid].reshape(-1)]
    along = vertices[:, 0] * unit[0] + vertices[:, 1] * unit[1] + vertices[:, 2] * unit[2]
    span = float(along.max() - along.min())
    return span if math.isfinite(span) and span > EPS_GEOM else fallback


def _unchanged_bore(diameter: float) -> Finding:
    """Die gemeinsame Auskunft für Netz und exakten Körper."""
    return Finding(
        code="bore.resize_unchanged",
        severity="info",
        message=_("Die Bohrung hat bereits diesen Durchmesser."),
        values={"diameter": format_length(diameter)},
    )


def _compensation_findings(nominal: float, cut: float, compensate: bool) -> list[Finding]:
    """Materialkompensation, wortgleich mit den anderen Bohrungswegen."""
    if not compensate or abs(cut - nominal) <= EPS_GEOM:
        return []
    return [
        Finding(
            code="bore.compensated",
            severity="info",
            message=_("Die Bohrung wurde um die Materialtoleranz vergrößert."),
            values={"nominal": format_length(nominal), "cut": format_length(cut)},
        )
    ]


def _expected_bore(feature: Feature, diameter: float) -> Feature:
    """Das alte Merkmal mit dem einen Maß, das diese Operation bewusst ändert."""
    return dataclasses.replace(
        feature,
        params={**feature.params, "diameter": diameter},
    )


def _recognised_resized_feature(
    mesh: MeshData, feature: Feature, diameter: float
) -> Feature | None:
    """Findet die eben erzeugte Wand und hängt den bestehenden Namen daran.

    Die allgemeine Zuordnung darf einen Sprung von Ø 3 auf Ø 30 nicht
    stillschweigend für dasselbe Merkmal halten. Hier ist er dagegen die
    ausdrückliche Operation. Darum wird genau für diesen Vergleich das neue
    Sollmaß eingesetzt, statt die globale Toleranz aufzuweichen.

    **Findet sie sich nicht wieder, ist das kein Programmfehler.** Hier stand
    ein ``InternalError`` mit „Erstellen Sie einen Fehlerbericht" — und er warf
    das fertig gerechnete Ergebnis mit weg, weil eine geworfene Ausnahme das
    ganze ``OpResult`` nimmt. Gemessen an ``spool-bearing-holder-p1stp.stl``
    aus dem Kundenbestand: Wer die 3,4-mm-Bohrung auf 0,2 mm verkleinert,
    bekommt genau die 11,75 mm³ Material zurück, die die Rechnung verlangt —
    und danach die Absage, weil ein Loch von 0,2 mm keines mehr ist, das die
    Erkennung findet. Die Auswertung hielt an, die richtige Geometrie war
    verworfen, und der Kunde las von einem unerwarteten Fehler.

    Der Rückgabewert ist deshalb ``None``, wenn die Zuordnung nicht greift.
    Der Aufrufer behält den Körper und meldet, dass das Merkmal fort ist —
    das ist die Wahrheit über die Lage und nicht über das Programm.
    """
    from app.core.perceive.features import detect
    from app.core.perceive.matching import match

    detected = detect(mesh)
    expected = _expected_bore(feature, diameter)
    matched = match(
        {feature.id: expected},
        detected,
        mesh.bounds.centre,
        mesh.bounds.diagonal,
    )
    found_id = matched.mapping.get(feature.id)
    if found_id is None:
        return None
    return dataclasses.replace(
        detected[found_id],
        id=feature.id,
        provenance="generated",
        created_by=None,
    )


def _bore_no_longer_a_feature(feature: Feature, diameter: float) -> Finding:
    """Die geänderte Bohrung ist da, aber nicht mehr als Merkmal auffindbar.

    Der Satz sagt beides — die Geometrie stimmt, der Bezug ist fort —, weil
    aus dem einen das andere folgt: Wer später auf diese Bohrung verweist,
    findet sie nicht mehr, und das ist die Auskunft, die er braucht.
    """
    return Finding(
        code="resize_hole.feature_lost",
        severity="warning",
        message=_(
            "Die Bohrung wurde geändert, lässt sich in dieser Größe aber nicht mehr "
            "als Merkmal wiederfinden. Die Geometrie stimmt; spätere Schritte, die "
            "auf sie verweisen, verlieren ihren Bezug."
        ),
        feature_ids=(feature.id,),
        values={"feature": feature.id, "diameter": format_length(diameter)},
    )


def _preserved_exact_features(
    previous: dict[str, Feature],
    detected: dict[str, Feature],
    feature: Feature,
    diameter: float,
    solid: Mesh,
) -> dict[str, Feature]:
    """Ordnet die exakte Topologie neu zu, mit dem gewählten Maß als Absicht."""
    from app.core.perceive.matching import apply_mapping, match

    expected = {**previous, feature.id: _expected_bore(feature, diameter)}
    bounds = solid.bounds
    matched = match(expected, detected, bounds.centre, bounds.diagonal)
    if feature.id not in matched.mapping:
        # **Englisch und ohne Rat an den Kunden**, anders als der Mesh-Weg
        # darüber. Hier ist die Absage berechtigt: Der exakte Kern führt
        # Flächen und Kanten und keine Dreiecke, und eine zylindrische Fläche
        # bleibt auffindbar, gleich wie klein sie wird. Gemessen an einem
        # exakten Quader mit Bohrung — 8,0 mm auf 0,2 mm verkleinert, das
        # Merkmal steht danach unverändert da, wo der Mesh-Weg seines verliert.
        # Tritt der Fall hier doch ein, ist etwas geschehen, das nicht
        # vorgesehen war, und dann gehört er in den Fehlerbericht.
        #
        # Der Satz stand übersetzt hier, und das war der Fehler: Von 26
        # ``InternalError`` im Programm trugen 25 englischen Detailtext und
        # genau dieser einen deutschen. Wer einen Programmfehler übersetzt,
        # hat einen Bedienfall als Programmfehler geschrieben — der Zwilling
        # im Mesh-Weg war genau das (Hinweis 3d-druck-a0).
        raise InternalError(
            detail="the resized exact bore could not be matched back to its feature",
            values={"feature": feature.id, "diameter": format_length(diameter)},
        )
    return apply_mapping(detected, matched)


def _both_halves_or_stop(first: MeshData, second: MeshData, position: float) -> None:
    """Hält an, wenn die Ebene den Körper gar nicht getroffen hat.

    Ohne das kam eine Hälfte mit null Dreiecken heraus, und der Stapel legte
    sie als Objekt an: ein Eintrag im Baum, den man ansehen, umbenennen und
    exportieren kann und der nichts ist. Der Fall ist häufiger als er klingt —
    der Dialog belegt ``position = 0`` vor, und ein Körper steht mit seiner
    Unterseite oft genau dort.
    """
    if first.triangle_count and second.triangle_count:
        return
    raise ValidationError(
        field="position",
        detail=_("Diese Ebene teilt das Objekt nicht."),
        value=position,
        constraint="no_split",
    )


@op_params
class CountersinkParams(BaseParams):
    diameter: float = param(
        title=_("Kopfdurchmesser"),
        default=8.4,
        unit="mm",
        minimum=0.5,
        maximum=100.0,
        doc=_(
            "Durchmesser des Schraubenkopfes, nicht der Bohrung darunter. Eine "
            "angeklickte Bohrung trägt den Kopf der passenden Schraube ein — "
            "nie ihr eigenes, gemessenes Maß."
        ),
    )
    angle: float = param(
        title=_("Winkel"),
        default=90.0,
        unit=DEGREE_UNIT,
        minimum=30.0,
        maximum=170.0,
        # Hinten, weil 90 Grad die Norm ist und nicht eine Wahl: Der eigene
        # doc-Satz sagt es. Damit hat die Senkung dieselbe Vorderseite wie
        # `drill_hole` und `plug_hole` — Durchmesser, Position, Achse — und war
        # vorher die einzige Operation mit sechs Werten und leerer Rückseite
        # (§2.4: vorn die zwei bis drei, die man tatsächlich ändert).
        placement="advanced",
        doc=_("Voller Kopfwinkel — 90 Grad bei metrischen Senkschrauben."),
    )
    x: float = param(
        title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X, placement="advanced"
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z, placement="advanced"
    )
    axis: str = param(
        title=_("Achse"), default="z", choices=_AXES, doc=_ALONG, placement="advanced"
    )
    anchor: str = param(
        title=_("Bezugspunkt"),
        default="mouth",
        choices=_ANCHORS,
        placement="advanced",
        doc=_(
            "Was die Position bedeutet: die Mündung der Bohrung, in der gesenkt "
            "wird, oder die Stelle selbst. Eine angeklickte Bohrung meldet ihre "
            "Mitte — dort gesenkt entsteht ein Hohlraum statt einer Fase."
        ),
    )


@register_op(
    name="countersink_hole",
    title=_("Senken"),
    category="holes",
    params=CountersinkParams,
    consumes=1,
    produces=1,
    # Auch auf eine **vorhandene** Senkung: Ein angeklickter Kegel bietet damit
    # „Senken" an, und das heißt dort „anders senken" — tiefer, weiter, anderer
    # Winkel. Ohne diesen Eintrag wäre der Kegel ein Merkmal, das man sehen und
    # anklicken kann und an dem das Kontextmenü leer bleibt (§2.6).
    applies_to=["hole", "cone"],
    doc=_("Senkt die Mündung einer Bohrung an, damit ein Schraubenkopf bündig sitzt."),
)
def countersink_hole(ctx: OpContext) -> OpResult:
    params = cast(CountersinkParams, ctx.params)
    source = ctx.inputs[0]
    result = countersink(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        angle=params.angle,
        anchor=cast(BoreAnchor, params.anchor),
        profile=ctx.profile,
        quality=ctx.quality,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh)],
        solver=result.solver,
        findings=result.findings,
    )


@op_params
class PlugParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=5.0,
        unit="mm",
        minimum=0.2,
        maximum=200.0,
        doc=_("Durchmesser der Bohrung, die zugemacht wird — etwas mehr schadet nicht."),
    )
    x: float = param(
        title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X, placement="advanced"
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z, placement="advanced"
    )
    axis: str = param(
        title=_("Achse"), default="z", choices=_AXES, doc=_ALONG, placement="advanced"
    )
    depth: float = param(
        title=_("Tiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        placement="advanced",
        doc=_("Null füllt durch das ganze Teil."),
    )
    anchor: str = param(
        title=_("Bezugspunkt"),
        default="mouth",
        choices=_ANCHORS,
        placement="advanced",
        doc=_(
            "Was die Position bedeutet: die Mündung, an der der Stopfen anfängt, "
            "oder seine Mitte. Bei einem durchgehenden Stopfen ändert es nichts."
        ),
    )
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=True,
        placement="advanced",
        doc=_(
            "Füllt so weit, wie *Bohrung setzen* mit derselben Einstellung schneidet — "
            "sonst bleibt rings um den Stopfen der Spalt stehen, um den die Bohrung "
            "aufgeweitet wurde."
        ),
    )


@register_op(
    name="plug_hole",
    title=_("Bohrung verschließen"),
    category="holes",
    params=PlugParams,
    consumes=1,
    produces=1,
    applies_to=["hole"],
    doc=_("Füllt eine Bohrung wieder auf — etwa wenn ein fremdes Teil eine zu viel hat."),
)
def plug_hole(ctx: OpContext) -> OpResult:
    params = cast(PlugParams, ctx.params)
    source = ctx.inputs[0]
    result = plug(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        depth=params.depth,
        anchor=cast(BoreAnchor, params.anchor),
        profile=ctx.profile,
        compensate=params.compensate,
        quality=ctx.quality,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features={})],
        solver=result.solver,
        findings=result.findings,
    )


@op_params
class HollowParams(BaseParams):
    wall: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        # **Die Zahl ist eine Rechengrenze, keine Toleranz mehr.** Hier stand
        # 0,4 mit dem Satz „zwei Extrusionsbreiten sind das Minimum" daneben —
        # und setzte ihn nicht um: Zwei Extrusionsbreiten sind am Centauri
        # 0,84 mm, an einer 0,6er Düse 1,2. Die Regel trägt jetzt
        # ``below_printable_wall`` gegen das Profil (§39, Regel 7); was hier
        # steht, ist nur noch, was der Kern überhaupt rechnen kann, und dieselbe
        # Zahl wie beim exakten Zwilling.
        minimum=0.2,
        maximum=50.0,
        doc=_("Was stehen bleibt. Zwei Extrusionsbreiten sind das Minimum."),
    )
    open_top: bool = param(
        title=_("Oben öffnen"),
        default=False,
        doc=_(
            "Nimmt die Decke über dem Hohlraum weg. Aus dem hohlen Körper wird "
            "eine Dose, und *Deckel erzeugen* findet die Öffnung, die es braucht."
        ),
    )
    vents: int = param(
        title=_("Entlüftungen"),
        default=1,
        minimum=0,
        maximum=6,
        doc=_(
            "Null heißt geschlossener Hohlraum — beim FDM-Druck drückt der die "
            "Decke hoch. Eine offene Dose braucht keine."
        ),
    )
    vent_diameter: float = param(
        title=_("Entlüftungsdurchmesser"),
        default=VENT_DIAMETER,
        unit="mm",
        minimum=1.0,
        maximum=20.0,
        placement="advanced",
        doc=_("Weite der Öffnungen. Groß genug, dass nicht verbrauchtes Material herauskommt."),
    )


@register_op(
    name="hollow_object",
    title=_("Aushöhlen"),
    category="prepare",
    params=HollowParams,
    consumes=1,
    produces=1,
    doc=_(
        "Höhlt ein Objekt aus und setzt Entlüftungen. Spart Material und Zeit; "
        "die Wandstärke stimmt im Rahmen des Rasters."
    ),
    caveat=_(
        "Nicht ohne Entlüftung, wenn im Slicer Stützen entstehen: Der Hohlraum füllt "
        "sich sonst mit Material, das niemand mehr herausbekommt. Und nicht bei "
        "Teilen, die Kräfte aufnehmen — eine dünne Hülle bricht anders als ein "
        "gefüllter Körper."
    ),
    shortcut="Ctrl+H",
)
def hollow_object(ctx: OpContext) -> OpResult:
    params = cast(HollowParams, ctx.params)
    source = ctx.inputs[0]
    result = hollow(
        as_mesh_data(source.mesh),
        params.wall,
        vents=params.vents,
        vent_diameter=params.vent_diameter,
        open_top=params.open_top,
        quality=ctx.quality,
        progress=ctx.progress,
        cancelled=ctx.cancelled,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features={})],
        # Aushöhlen fährt bis zu sechs Boolesche Schnitte und meldete keine
        # Stufe. Wer hinterher fragt, was die Wandstärke wert ist, liest sie
        # hier (§17.2).
        solver=result.solver,
        # Die Geometriefunktion kennt keine Kennungen — sie rechnet auf einem
        # Netz. Verorten kann die Operation, und sie muss es: zwei ausgehöhlte
        # Körper meldeten zweimal denselben Satz, und im Bericht standen zwei
        # Zeilen, die aussahen wie ein Fehler in der Anwendung.
        findings=[
            dataclasses.replace(entry, object_id=source.id)
            # **Die Druckbarkeit fragt das Profil, nicht das Schema.** Hier
            # stand ``minimum=0.4`` — richtig für eine 0,4er Düse und für jede
            # andere falsch: Am Centauri sind zwei Extrusionsbreiten 0,84 mm,
            # die Grenze ließ dort das Doppelte an zu dünner Wand durch.
            for entry in [*result.findings, below_printable_wall(params.wall, ctx.profile)]
            if entry is not None
        ],
    )


@op_params
class ElephantFootParams(BaseParams):
    height: float = param(
        title=_("Höhe"),
        default=0.6,
        unit="mm",
        minimum=0.1,
        maximum=5.0,
        doc=_("Über wie viel Höhe eingezogen wird — etwa die ersten drei Schichten."),
    )
    amount: float = param(
        title=_("Betrag"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        placement="advanced",
        doc=AUTO_FROM_PROFILE_DOC,
    )


@register_op(
    name="compensate_first_layer",
    title=_("Elefantenfuß ausgleichen"),
    category="prepare",
    params=ElephantFootParams,
    consumes=1,
    produces=1,
    doc=_(
        "Zieht die ersten Schichten um den Betrag ein, um den sie beim Drucken "
        "breitlaufen. Der Wert kommt aus dem Materialprofil."
    ),
)
def compensate_first_layer(ctx: OpContext) -> OpResult:
    params = cast(ElephantFootParams, ctx.params)
    source = ctx.inputs[0]
    if ctx.profile is None:
        raise InternalError(detail="the elephant foot compensation needs a profile")

    mesh, findings, solver = compensate_elephant_foot(
        as_mesh_data(source.mesh),
        # Das Auseinanderlaufen gehört zum Material, und dieser Körper ist
        # vielleicht nicht im Material des Projekts (§12) — eine TPU-Dichtung
        # läuft weiter als das PETG um sie herum.
        for_object(ctx.profile, source),
        height=params.height,
        amount=params.amount or None,
        quality=ctx.quality,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh)], findings=findings, solver=solver
    )


@op_params
class MaterialParams(BaseParams):
    material: str = param(
        title=_("Material"),
        kind="material",
        default="",
        doc=_("Welches Material dieses Teil ist. Leer heißt: das des Projekts."),
    )


@register_op(
    name="set_material",
    title=_("Material festlegen"),
    category="prepare",
    params=MaterialParams,
    consumes=1,
    produces=1,
    doc=_(
        "Gibt diesem Körper ein eigenes Material. Toleranzen, Schwund und "
        "Elefantenfuß werden dann damit gerechnet und nicht mit dem des Projekts."
    ),
)
def set_material(ctx: OpContext) -> OpResult:
    """§12: eine Szene, mehr als ein Material.

    Ein Gehäuse in PETG mit einer Dichtung in TPU ist ein Projekt und zwei
    Materialien. Ohne das würden Spiel, Schrumpf und erste Schicht der Dichtung
    aus dem Material des Gehäuses gerechnet — Zahlen, die nicht ungefähr sind,
    sondern falsch, und falsch in der Richtung, die einen Druck zu Ausschuss
    macht.

    Die Kennung wird hier geprüft statt als feste Liste angeboten: zu den
    bekannten Materialien gehören die eigenen Profile des Nutzers, und die
    erscheinen, nachdem dieses Modul importiert wurde.
    """
    params = cast(MaterialParams, ctx.params)
    source = ctx.inputs[0]
    chosen = params.material.strip()
    if chosen:
        material(chosen)  # wirft mit der Liste der bekannten, wenn es keines ist

    return OpResult(
        outputs=[dataclasses.replace(source, material=chosen or None)],
        findings=[
            Finding(
                code="prepare.material",
                severity="info",
                message=_("Dieser Körper wird in einem eigenen Material gerechnet."),
                # **Ohne `str()`.** Der Aufruf löste den Namen in der Sprache
                # von jetzt auf und schrieb ihn fest: Im englischen Fenster
                # stand hier weiter „Deckel", während der Körper daneben im
                # Objektbaum „Lid" hieß — zwei Namen für dasselbe Teil in einem
                # Blick. Ein übersetzbarer Text wandert mit; aufgelöst wird
                # erst beim Anzeigen und beim Speichern.
                values={"object": source.name, "material": chosen or "-"},
            )
        ]
        if chosen
        else [],
    )


@op_params
class TestPieceParams(BaseParams):
    size: float = param(
        title=_("Kantenlänge"),
        default=20.0,
        unit="mm",
        minimum=2.0,
        maximum=200.0,
        doc=_("Wie groß der Ausschnitt wird. Groß genug, dass die Passung Material hat."),
    )
    x: float = param(
        title=_("Position X"),
        default=0.0,
        unit="mm",
        doc=_("Mitte des Ausschnitts — die Stelle, um die es geht."),
        placement="advanced",
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z, placement="advanced"
    )
    on_bed: bool = param(
        title=_("Auf das Bett setzen"),
        default=True,
        doc=_("Legt das Prüfstück flach hin, damit es ohne Stützen druckt."),
    )


@register_op(
    name="test_piece",
    title=_("Prüfstück erzeugen"),
    category="prepare",
    params=TestPieceParams,
    consumes=1,
    produces=1,
    applies_to=["hole", "pin", "face"],
    doc=_(
        "Schneidet einen Würfel um eine Stelle heraus, um sie zu drucken und "
        "auszuprobieren — zwei Minuten statt zwei Stunden."
    ),
)
def test_piece(ctx: OpContext) -> OpResult:
    """§28.3, aus der Praxis: eine Passung prüft man am Ausschnitt, nicht am Teil.

    Der Ausschnitt ist eine Verschneidung mit einem Würfel — heraus kommt also
    die echte Geometrie mit den echten Toleranzen, keine nachgebaute Näherung
    davon. Ein Prüfstück, das anders druckt als das Teil, für das es steht,
    wäre schlechter als gar kein Test.
    """
    params = cast(TestPieceParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    window = trimesh.creation.box(extents=(params.size, params.size, params.size))
    window.apply_translation((params.x, params.y, params.z))
    # Ein Fenster über leerem Raum ist eine Antwort, keine gescheiterte
    # Operation: ohne ``allow_empty`` probierte die Kette drei weitere Stufen
    # und würfe dann — und der Nutzer läse etwas über den Voxel-Solver statt
    # über das Loch, auf das er gezielt hat.
    outcome = boolean(
        "intersection", [mesh, mesh.replacing(window)], quality=ctx.quality, allow_empty=True
    )

    piece = outcome.mesh
    if not piece.triangle_count or abs(piece.volume) <= EPS_GEOM:
        raise ValidationError(
            field="size",
            detail=_("An dieser Stelle ist kein Material — der Ausschnitt bleibt leer."),
            constraint="empty",
            values={"size_mm": round(params.size, 2)},
        )
    if params.on_bed:
        piece = place_on_bed(piece)

    share = abs(piece.volume) / max(abs(mesh.volume), EPS_GEOM)
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=piece,
                # Wie beim Deckel: kein Quellbezug, kein eingefrorenes Wort.
                name=_("Prüfstück"),
                features={},
            )
        ],
        solver=outcome.solver,
        findings=[
            *outcome.findings,
            Finding(
                code="prepare.test_piece",
                severity="info",
                message=_("Ein Ausschnitt zum Ausprobieren — die Maße sind die des Teils."),
                object_id=source.id,
                values={"share_percent": round(share * 100.0, 1), "size_mm": params.size},
            ),
        ],
    )


@op_params
class SplitPinnedParams(BaseParams):
    axis: str = param(
        title=_("Achse"),
        default="z",
        choices=_AXES,
        doc=_("Senkrecht zu welcher Achse geschnitten wird. Z legt einen waagerechten Schnitt."),
    )
    position: float = param(
        title=_("Position"),
        default=0.0,
        unit="mm",
        doc=_(
            "Wo die Schnittebene liegt, auf dieser Achse gemessen. Die Zahl bleibt "
            "änderbar: ein Doppelklick auf den Schritt verschiebt den Schnitt."
        ),
    )
    pins: int = param(
        title=_("Passstifte"),
        default=PIN_COUNT,
        minimum=0,
        maximum=6,
        doc=_("Null heißt: nur schneiden. Zwei halten die Hälften gegen Verdrehen."),
    )
    shape: str = param(
        title=_("Stiftform"),
        default="round",
        choices=CONNECTOR_SHAPES,
        placement="advanced",
        doc=_CONNECTOR_DOC,
    )
    glue_hint: bool = param(
        title=_("Kleben empfohlen"),
        default=False,
        placement="advanced",
        doc=_(
            "Automatisch teilen schaltet dies ein, wenn weder Schwalbenschwanz noch "
            "Schnapper zur Naht passen."
        ),
    )
    diameter: float = param(
        title=_("Stiftdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=PIN_MAX,
        placement="advanced",
        doc=_("Null heißt: aus der Schnittfläche ableiten."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=AUTO_FROM_PROFILE_DOC,
    )


@register_op(
    name="split_pinned",
    # Nicht mehr „Teilen und verstiften": Seit *An Ebene teilen* in dieser
    # Operation aufgegangen ist (Formatversion 11), ist es die eine Zeile für
    # beides — mit Stiften und ohne. Ein Titel, der die Stifte verspricht,
    # wäre für die Hälfte der Fälle falsch; das Feld *Passstifte* sagt,
    # welcher Fall gilt, und seine Null ist der ganze Unterschied.
    title=_("Teilen"),
    category="prepare",
    params=SplitPinnedParams,
    consumes=1,
    produces=2,
    doc=_(
        "Teilt ein Objekt an einer Ebene, auf Wunsch mit Passstiften in der "
        "Schnittfläche. Das Spiel kommt aus dem Materialprofil; null Stifte heißt: "
        "nur schneiden."
    ),
    caveat=_(
        "Nicht bei Teilen, deren Schnittfläche sichtbar bleibt: Die Naht liegt an "
        "einer Ebene und ist es danach auch. Wo sie stören würde, lieber die Lage "
        "ändern oder eine Stelle wählen, an der ohnehin eine Kante läuft."
    ),
)
def split_pinned(ctx: OpContext) -> OpResult:
    """§25: der Schnitt und die Stifte in einem Schritt, denn sie gehören
    zusammen.

    Eine Naht ohne Stifte ist eine Naht, die jemand von Hand ausrichten muss,
    während der Kleber greift; ein Stift ohne Naht ist nichts. Beides in einer
    Operation heißt außerdem: ein Undo nimmt das Ganze zurück.
    """
    params = cast(SplitPinnedParams, ctx.params)
    plane = SectionPlane(normal=AXIS_NORMALS[cast(Axis, params.axis)], position=params.position)
    return _cut_and_pin(
        ctx,
        plane,
        pins=params.pins,
        shape=params.shape,
        glue_hint=params.glue_hint,
        diameter=params.diameter,
        play=params.play,
    )


def _cut_and_pin(
    ctx: OpContext,
    plane: SectionPlane,
    *,
    pins: int,
    shape: str,
    glue_hint: bool,
    diameter: float,
    play: float,
) -> OpResult:
    """Der gemeinsame Teil von *Teilen* und *An Linie trennen*.

    Die beiden unterscheiden sich einzig darin, **woher die Ebene kommt** —
    aus einer Achse und einer Zahl oder aus zwei angeklickten Punkten. Alles
    danach ist dasselbe, und zweimal geschrieben wäre es beim ersten Nachbessern
    an einer Stelle anders.
    """
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)
    connector_start = next_connector_index(source.features)

    first, second, findings = split_at_plane(mesh, plane)
    _both_halves_or_stop(first, second, plane.position)

    # **Der Wunschdurchmesser geht in die Planung hinein**, nicht hinterher in
    # ihr Ergebnis. Bis zum 02.09.2026 stand hier ein ``dataclasses.replace``
    # auf dem fertigen Plan: Es tauschte das eine Feld und ließ Sitzpuffer,
    # Materialtiefe, Länge und Formwahl stehen, wie sie für den *abgeleiteten*
    # Durchmesser gerechnet waren. Ein 8-mm-Stift in einer 10 mm starken Platte
    # ließ damit 0,875 mm Wand stehen statt der geforderten 1,6 und band 4,5 mm
    # ein statt der nötigen 6,0 — ohne einen einzigen Befund.
    plan = (
        plan_pins(mesh, plane, count=pins, shape=shape, diameter=diameter or None) if pins else None
    )

    # **``ctx.profile`` ist nach §9 keine Option**, und die zweite Bedingung
    # hier war es doch: ``plan is not None and ctx.profile is not None``. Der
    # ``else``-Zweig dahinter konnte nie laufen — und er warf die Befunde des
    # Stiftplans weg, also genau die Sätze, die sagen, *warum* aus zwei
    # verlangten Stiften keiner wurde. Ein toter Zweig, der im Ernstfall das
    # Falsche getan hätte; mypy nennt ihn seit ``warn_unreachable`` beim Namen.
    #
    # Beide Hälften kommen aus diesem einen Körper, das Spiel ist also das
    # seines Materials.
    pair = (
        add_pins(
            first,
            second,
            plan,
            for_object(ctx.profile, source),
            start=connector_start,
            play=play or None,
            quality=ctx.quality,
            cancelled=ctx.cancelled,
        )
        if plan is not None
        else PinnedPair(first=first, second=second)
    )
    if glue_hint and plan is not None and plan.count and plan.shape == "round":
        pair.findings.append(connector_glue_finding())

    first_features, second_features = _features_after_split(source.features, plane)
    first_name, second_name = half_names(source.name, pinned=bool(pair.pin_features))
    return OpResult(
        solver=pair.solver,
        outputs=[
            dataclasses.replace(
                source,
                mesh=pair.first,
                name=first_name,
                features={**first_features, **pair.pin_features},
            ),
            dataclasses.replace(
                source,
                mesh=pair.second,
                name=second_name,
                features={**second_features, **pair.bore_features},
            ),
        ],
        findings=[*findings, *pair.findings, _halves_still_together(source)],
    )


def _features_after_split(
    features: dict[str, Feature], plane: SectionPlane
) -> tuple[dict[str, Feature], dict[str, Feature]]:
    """Nimmt bestehende Merkmale auf die geometrisch richtige Hälfte mit.

    Ein Merkmal genau auf dem neuen Schnitt wird selbst getrennt und kann
    deshalb nicht unverändert weitergelten. Ohne Mittelpunkt bleibt das alte
    Verhalten erhalten: Es reist mit der ersten Hälfte, statt geraten zu
    werden.
    """
    first: dict[str, Feature] = {}
    second: dict[str, Feature] = {}
    for feature_id, feature in features.items():
        side = feature_side(
            feature,
            plane,
            connector=feature_id.startswith(("pin_", "bore_")),
        )
        if side in (-1, None):
            first[feature_id] = feature
        elif side == 1:
            second[feature_id] = feature
    return first, second


def _halves_still_together(source: SceneObject) -> Finding:
    """Zwei Hälften an ihrem Platz sehen aus wie ein Körper.

    Das Teilen setzt beide Stücke dorthin, wo sie im ganzen Teil lagen —
    richtig so, denn erst damit passen sie noch zusammen, und die Passstifte
    sitzen aufeinander. Im Bild ist das Ergebnis aber von der Ausgangslage
    nicht zu unterscheiden: ein Schritt im Verlauf, zwei Zeilen im Baum, und
    davor ein Körper, der aussieht wie vorher (Fund 27, 27.08.2026).

    Der Nachbarbefund ``arrange.bodies_in_one_place`` greift hier **nicht**:
    Er sucht Körper, die sich in Hüllquader und Volumen gleichen, und zwei
    komplementäre Hälften tun genau das nicht. Deshalb sagt es die Operation
    selbst — sie ist die einzige Stelle, die weiß, dass die zwei Körper
    zusammengehören.

    Ein Hinweis und keine Warnung: Nichts ist schiefgegangen, und wer gleich
    exportiert, bekommt zwei richtige Dateien. Die Handlung daneben ist
    *Auf dem Bett anordnen* — dieselbe, die auch die Nachbarbefunde tragen.
    """
    return Finding(
        code="prepare.halves_in_place",
        severity="info",
        message=_(
            "Die zwei Hälften liegen noch aneinander — im Bild sieht das aus wie ein Teil. "
            "Zum Drucken nebeneinander legen."
        ),
        object_id=source.id,
    )


@op_params
class SplitLineParams(BaseParams):
    """Die Trennebene aus einer gezeichneten Linie.

    Was der Nutzer tut, ist zwei Punkte anklicken; was gespeichert wird, ist
    die Ebene, die daraus folgt. Beides ist dieselbe Angabe — nur ist die
    Ebene die, die sich hinterher noch verschieben lässt, und ein Punktpaar
    wäre eine Zahlenkolonne, an der niemand etwas nachbessert.
    """

    position: float = param(
        title=_("Lage"),
        default=0.0,
        unit="mm",
        doc=_(
            "Wie weit die Trennebene vom Nullpunkt entfernt liegt, in Trennrichtung "
            "gemessen. Die gezeichnete Linie trägt die Zahl ein; nachträglich "
            "verschiebt sie den Schnitt, ohne ihn zu drehen."
        ),
    )
    pins: int = param(
        title=_("Passstifte"),
        default=PIN_COUNT,
        minimum=0,
        maximum=6,
        doc=_(
            "Stifte auf der einen Hälfte, Bohrungen auf der anderen — sie halten die "
            "Teile beim Kleben in Deckung. Null heißt: nur trennen."
        ),
    )
    normal_x: float = param(
        title=_("Trennrichtung X"),
        default=0.0,
        placement="advanced",
        doc=_(
            "Richtung, in der die Ebene steht. Die gezeichnete Linie trägt sie ein — "
            "von Hand gesetzt ergeben die drei Zahlen zusammen einen Pfeil senkrecht "
            "zur Schnittfläche."
        ),
    )
    normal_y: float = param(
        title=_("Trennrichtung Y"),
        default=0.0,
        placement="advanced",
        doc=_("Zweite Achse der Trennrichtung — siehe Trennrichtung X."),
    )
    normal_z: float = param(
        title=_("Trennrichtung Z"),
        default=1.0,
        placement="advanced",
        doc=_("Dritte Achse der Trennrichtung — siehe Trennrichtung X."),
    )
    shape: str = param(
        title=_("Stiftform"),
        default="round",
        choices=CONNECTOR_SHAPES,
        placement="advanced",
        doc=_CONNECTOR_DOC,
    )
    diameter: float = param(
        title=_("Stiftdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=PIN_MAX,
        placement="advanced",
        doc=_("Null heißt: aus der Schnittfläche ableiten."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=AUTO_FROM_PROFILE_DOC,
    )


@register_op(
    name="split_line",
    title=_("An gezeichneter Linie trennen"),
    category="prepare",
    params=SplitLineParams,
    consumes=1,
    produces=2,
    icon="split",
    doc=_(
        "Trennt ein Objekt entlang einer im Bild gezeichneten Linie und setzt auf "
        "Wunsch Passstifte in die Schnittfläche."
    ),
    caveat=_(
        "Der Schnitt ist eine Ebene, keine Kurve: Die Linie legt fest, wo und wie "
        "schräg getrennt wird, und die Ebene läuft von dort gerade durch das Teil. "
        "Wer um eine Rundung herum trennen will, teilt zweimal."
    ),
)
def split_line(ctx: OpContext) -> OpResult:
    """§25: derselbe Schnitt wie *Teilen und verstiften*, nur mit einer Ebene,
    die nicht an einer Achse hängt.

    Zwei Punkte auf dem Körper und die Blickrichtung spannen sie auf — das ist
    die Rechnung, die das Fenster macht, bevor es hier ankommt. Hier steht nur
    noch die fertige Ebene, und das ist Absicht: Eine Operation, die von der
    Kamerastellung abhinge, wäre beim zweiten Auswerten eine andere (§11.2).
    """
    params = cast(SplitLineParams, ctx.params)
    normal = (params.normal_x, params.normal_y, params.normal_z)
    if _length(normal) <= EPS_GEOM:
        raise ValidationError(
            field="normal_z",
            detail=_("Ohne Trennrichtung gibt es keine Ebene."),
            value=0.0,
            constraint="no_normal",
        )
    return _cut_and_pin(
        ctx,
        SectionPlane(normal=normal, position=params.position),
        pins=params.pins,
        shape=params.shape,
        glue_hint=False,
        diameter=params.diameter,
        play=params.play,
    )


def _length(vector: tuple[float, float, float]) -> float:
    return float(sum(entry * entry for entry in vector) ** 0.5)


@op_params
class OrientParams(BaseParams):
    thorough: bool = param(
        title=_("Gründlich suchen"),
        default=True,
        doc=_(
            "Rechnet hunderte Lagen mit der Schichtanalyse durch. "
            "Aus heißt: schnelle Heuristik über die Flächen."
        ),
    )
    candidates: int = param(
        title=_("Kandidaten"),
        default=DEFAULT_CANDIDATES,
        minimum=8,
        maximum=2000,
        placement="advanced",
        doc=_(
            "Wie viele Lagen durchgerechnet werden. Mehr findet feinere "
            "Verbesserungen und dauert entsprechend länger."
        ),
        depends_on=("thorough", (True,)),
    )


@register_op(
    name="orient_for_print",
    title=_("Druckoptimal ausrichten"),
    category="transform",
    params=OrientParams,
    consumes=1,
    produces=1,
    deterministic=False,
    doc=_("Sucht die Lage mit dem geringsten Stützbedarf."),
)
def orient_for_print_op(ctx: OpContext) -> OpResult:
    """Gründlich heißt, die Schichtanalyse urteilt; sonst tut es die
    P2-Heuristik.
    """
    params = cast(OrientParams, ctx.params)
    mesh = as_mesh_data(ctx.inputs[0].mesh)

    if params.thorough:
        found = search(
            mesh,
            count=params.candidates,
            seed=ctx.seed,
            profile=ctx.profile,
            progress=ctx.progress,
            cancelled=ctx.cancelled,
        )
        return OpResult(
            outputs=[dataclasses.replace(ctx.inputs[0], mesh=found.mesh)],
            findings=found.findings,
            # Dieselbe Bewegung, die die Suche gefahren ist — aus derselben
            # Funktion, damit die zwei nicht auseinanderlaufen können.
            transform=as_transform(print_transform(mesh, found.best.direction)),
        )

    result = orient_for_print(mesh)
    return OpResult(
        outputs=[dataclasses.replace(ctx.inputs[0], mesh=result.mesh)],
        findings=result.findings,
        transform=as_transform(result.transform),
    )


@op_params
class ArrangeParams(BaseParams):
    spacing: float = param(
        title=_("Abstand"),
        default=5.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_(
            "Luft zwischen den Teilen. Genug, dass ein Elefantenfuß zwei Teile "
            "nicht am Rand zusammenwachsen lässt."
        ),
    )
    plates: int = param(
        title=_("Druckplatten"),
        default=1,
        minimum=1,
        maximum=MAX_PLATES,
        doc=_("Passt nicht alles auf eine Platte, wandert der Rest auf die nächste."),
    )
    by_material: bool = param(
        title=_("Nach Filament trennen"),
        default=False,
        doc=_(
            "Legt Teile aus verschiedenen Filamenten auf verschiedene Platten. "
            "Zwei Filamente auf einer Platte kosten je gemeinsamer Schicht "
            "einen Wechsel samt Spülgang."
        ),
    )


def _arranged_by_material(ctx: OpContext, params: ArrangeParams) -> Arrangement:
    """Erst nach Filament gruppieren, dann jede Gruppe für sich anordnen.

    Den Vorschlag rechnet :func:`app.core.export.writer.plates_by_material`
    schon lange — er war nur von nirgends aus erreichbar. Hier wird er zu einer
    Handlung, und zwar als Umschalter an der bestehenden Operation statt als
    zweite daneben: es ist dieselbe Handlung mit einer anderen Vorgabe, wer
    neben wem liegt.

    Jede Gruppe bekommt ihre eigenen Platten, hintereinander weg. Die Grenze
    aus ``plates`` gilt dabei für die ganze Szene, nicht je Gruppe — sonst
    hätte ein Projekt mit drei Filamenten unversehens dreimal so viele
    Platten, wie jemand eingestellt hat.
    """
    from app.core.export.writer import plates_by_material

    groups = plates_by_material(list(ctx.inputs))
    order: list[int] = []
    for entry in ctx.inputs:
        group = groups[entry.id]
        if group not in order:
            order.append(group)

    meshes: dict[str, MeshData] = {}
    assigned: dict[str, int] = {}
    findings: list[Finding] = []
    next_plate = 0

    for group in order:
        members = [entry for entry in ctx.inputs if groups[entry.id] == group]
        # Sind die Platten aufgebraucht, teilt sich diese Gruppe die letzte mit
        # der vorigen — dieselbe Regel, die `arrange_on_bed` innerhalb einer
        # Gruppe befolgt: die letzte Platte nimmt den Rest, und der Bericht
        # sagt, dass sie übervoll ist. Ein Teil, das still aus der Anordnung
        # fiele, wäre ein Teil, das nie gedruckt wird.
        start = min(next_plate, params.plates - 1)
        arranged = arrange_on_bed(
            [as_mesh_data(entry.mesh) for entry in members],
            ctx.profile,
            params.spacing,
            params.plates - start,
            # Mit Kennungen: Der Bauraum-Befund soll den Körper beim Namen
            # nennen, nicht beim laufenden Index (Roberts Foto, 30.08.2026).
            object_ids=[entry.id for entry in members],
        )
        findings.extend(arranged.findings)
        for entry, mesh, plate in zip(members, arranged.meshes, arranged.plates, strict=True):
            meshes[entry.id] = mesh
            assigned[entry.id] = start + plate
        next_plate = start + arranged.plate_count

    return Arrangement(
        meshes=[meshes[entry.id] for entry in ctx.inputs],
        plates=[assigned[entry.id] for entry in ctx.inputs],
        findings=findings,
    )


@register_op(
    name="arrange_bed",
    title=_("Auf dem Bett anordnen"),
    category="scene",
    params=ArrangeParams,
    consumes=0,
    produces=VARIABLE,
    whole_scene=True,
    doc=_("Legt alle Objekte nebeneinander auf das Druckbett."),
    shortcut="Ctrl+Shift+O",
)
def arrange_bed(ctx: OpContext) -> OpResult:
    params = cast(ArrangeParams, ctx.params)
    meshes = [as_mesh_data(entry.mesh) for entry in ctx.inputs]
    if params.by_material:
        result = _arranged_by_material(ctx, params)
    else:
        result = arrange_on_bed(
            meshes,
            ctx.profile,
            params.spacing,
            params.plates,
            object_ids=[entry.id for entry in ctx.inputs],
        )
    findings = list(result.findings)

    # Kollisionen werden je Platte geprüft: zwei Teile an derselben Stelle auf
    # verschiedenen Platten treffen sich nie.
    #
    # **Und mit Namen.** ``check_collisions`` kennt nur die Reihenfolge seiner
    # Liste und schreibt sie in den Befund; ohne ``named_for`` stand im Bericht
    # „Zwei Objekte überschneiden sich — 0 · 1". Hier war es doppelt irre, denn
    # die Liste ist je Platte gefiltert: die 1 der zweiten Platte ist nicht das
    # zweite Objekt der Szene. Die Einträge werden deshalb mitgefiltert und
    # zusammen weitergegeben. Die Zwillings-Op darunter macht es seit je so.
    for plate in range(result.plate_count):
        on_plate = [
            (mesh, entry)
            for mesh, entry, at in zip(result.meshes, ctx.inputs, result.plates, strict=True)
            if at == plate
        ]
        findings.extend(
            named_for(
                check_collisions([mesh for mesh, _entry in on_plate]),
                [entry for _mesh, entry in on_plate],
            )
        )

    # **Wenn nichts zu verschieben war, sagt die Operation es.** Sonst ist ein
    # zweiter Klick von einer kaputten Anwendung nicht zu unterscheiden: Der
    # Dialog geht auf, OK rechnet dasselbe Ergebnis, im Verlauf steht ein
    # Schritt, und das Bild bleibt, wie es war. Robert am 24.08.2026, nachdem
    # er es zum zweiten Mal geklickt hatte: „das an druckbett ausrichten
    # funktioniert nicht mehr" — es lag schon alles, wo es liegen sollte.
    #
    # Ein Befund und kein Fehler: Die Operation ist gelungen, das Ergebnis ist
    # nur dasselbe wie vorher. Regel 17 gilt für Ausnahmen; hier gibt es keine,
    # und ein Dialog wäre eine Bestätigung ohne Entscheidung (Regel 19).
    if not _has_moved(ctx.inputs, result):
        findings.append(
            Finding(
                code="arrange.already_arranged",
                severity="info",
                message=_("Die Teile liegen schon so — es war nichts zu verschieben."),
            )
        )

    return OpResult(
        outputs=[
            dataclasses.replace(entry, mesh=mesh, plate=plate)
            for entry, mesh, plate in zip(ctx.inputs, result.meshes, result.plates, strict=True)
        ],
        findings=findings,
    )


def _has_moved(entries: Sequence[SceneObject], result: Arrangement) -> bool:
    """Ob die Anordnung überhaupt einen Körper bewegt hat.

    Gegen ``EPS_DISPLAY`` und nicht gegen ``EPS_GEOM`` (§11.2, Regel 6): Die
    Frage ist nicht, ob zwei Netze rechnerisch gleich liegen, sondern ob jemand
    den Unterschied **sieht**. Ein Hundertstelmillimeter ist im Fenster
    dasselbe Bild, und eine Meldung „verschoben", die nichts zeigt, wäre
    genauso irre wie die Stille, gegen die sie steht.

    Die Platte zählt mit: Zwei Platten liegen in der Szene an derselben Stelle,
    weil jede einzeln gedruckt wird (§25). Ein Körper, der auf die nächste
    wandert, behält damit seine Koordinaten und ist trotzdem woanders.
    """
    for entry, mesh, plate in zip(entries, result.meshes, result.plates, strict=True):
        if plate != entry.plate:
            return True
        before = as_mesh_data(entry.mesh).bounds.minimum
        after = mesh.bounds.minimum
        if any(abs(a - b) > EPS_DISPLAY for a, b in zip(before, after, strict=True)):
            return True
    return False


@op_params
class CollisionParams(BaseParams):
    clearance: float = param(
        title=_("Mindestabstand"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        doc=_(
            "Ab wann zwei Teile als zu nah gelten. Null meldet nur echte "
            "Überschneidungen; ein Wert darüber meldet auch knappe Stellen."
        ),
    )


@register_op(
    name="check_collisions",
    # „Überschneidungen" statt „Kollisionen": Der Kunde denkt bei Kollision an
    # einen Zusammenstoß, gemeint ist, dass zwei Teile ineinanderstecken.
    title=_("Überschneidungen prüfen"),
    category="scene",
    params=CollisionParams,
    consumes=0,
    produces=VARIABLE,
    whole_scene=True,
    doc=_("Meldet Überschneidungen und was über den Bauraum hinaussteht."),
)
def check_collisions_op(ctx: OpContext) -> OpResult:
    params = cast(CollisionParams, ctx.params)
    meshes = [as_mesh_data(entry.mesh) for entry in ctx.inputs]
    findings = check_collisions(meshes, params.clearance)
    findings.extend(check_build_volume(meshes, ctx.profile))
    # Ändert nichts: die Objekte gehen unberührt hindurch, die Befunde sind das
    # Ergebnis.
    return OpResult(outputs=list(ctx.inputs), findings=named_for(findings, ctx.inputs))
