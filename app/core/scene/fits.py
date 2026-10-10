"""Passungen zwischen Merkmalen (Bauplan §14).

Objekte sind sonst unabhängig, und ein Fehler zeigt sich erst beim
Zusammenbau — wenn der Stift nicht ins Loch geht und der Druck schon gemacht
ist. Eine Passung bindet zwei Merkmale aneinander und wird bei jeder
Auswertung geprüft.

Die Toleranz ist ein Verweis ins Materialprofil, nie eine Zahl in der
Datei (§12, AGENTS.md Regel 7). Genau das lässt die Kalibrierung (§28.3)
Projekte erreichen, die vor ihr gebaut wurden.
"""

from __future__ import annotations

import math
from collections.abc import Collection
from dataclasses import dataclass, replace
from typing import cast

import numpy as np

from app.core.errors import (
    PROGRAMMING_ERRORS,
    SHOW_FEATURE,
    SHOW_HISTORY,
    AppError,
    InternalError,
    OperationCancelled,
)
from app.core.expressions import resolve as resolve_parameters
from app.core.expressions import resolve_value
from app.core.knowledge.profiles import for_object, resolve_tolerance, thread_share
from app.core.log import get_logger
from app.core.perceive.features import EPS_ANGLE
from app.core.scene.cancel import NeverCancelled
from app.core.types import (
    AUTO_TOLERANCE_PREFIX,
    BaseParams,
    CancelToken,
    Document,
    Feature,
    FeatureRef,
    Finding,
    Fit,
    FitKind,
    Operation,
    Profile,
    Scene,
    SceneObject,
    Severity,
    kind_of,
    vec3_or_none,
)
from app.core.units import EPS_DISPLAY, EPS_GEOM, format_length
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Wie weit das tatsächliche Spiel vom Profilwert abweichen darf, bevor es ein
#: Befund wird.
#:
#: §14 hält diese Prüfauflösung getrennt vom Materialprofil. Native
#: analytische Maße kommen aus der Topologie, Netzmaße aus einer Einpassung.
#: Der Bereich ist keine pauschale Genauigkeitszusage für fremde Netze:
#: deren tatsächliches Radialband wird zusätzlich geprüft. Eine mögliche
#: Überdeckung der Spielpassung verschwindet auch innerhalb dieses Bereichs nicht.
FIT_TOLERANCE = EPS_DISPLAY * 5


def resolve(scene: Scene, reference: FeatureRef) -> Feature | None:
    """Das Merkmal, auf das eine Passung zeigt — oder None, wenn es fort ist."""
    entry = scene.objects.get(reference.object_id)
    if entry is None:
        return None
    return entry.features.get(reference.feature_id)


def diameter_of(feature: Feature) -> float | None:
    return _positive(feature, "diameter")


def _positive(feature: Feature, name: str) -> float | None:
    """Ein wirklich gemessenes positives Maß; bool und nichtendliche Werte zählen nicht."""
    value = feature.params.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value > EPS_GEOM else None


def _role(feature: Feature) -> str | None:
    """Die belegte Innen-/Außenrolle, nie aus der größeren Zahl geraten."""
    if feature.kind in {"hole", "pin"}:
        return "inner" if feature.kind == "hole" else "outer"
    if feature.kind == "thread" and isinstance(feature.params.get("internal"), bool):
        return "inner" if feature.params["internal"] else "outer"
    role = feature.params.get("fit_role")
    if feature.kind == "face" and isinstance(role, str) and role in {"inner", "outer"}:
        return role
    return None


def pair_problem(kind: FitKind, first: Feature, second: Feature) -> TranslatableText | None:
    """Gemeinsame Eignungsprüfung für gespeicherte Beziehungen und ihre Anlegeoberfläche."""
    problem = _pair_problem(kind, first, second)
    return problem[1] if problem is not None else None


def _pair_problem(
    kind: FitKind, first: Feature, second: Feature
) -> tuple[str, TranslatableText] | None:
    """Code und Vorschlag kommen aus derselben Prüfung, auch nach späteren Maßänderungen."""
    if kind == "flush":
        if first.kind != "face" or second.kind != "face":
            return "fit.not_measurable", _("Für eine bündige Passung zwei ebene Flächen wählen.")
        for feature in (first, second):
            centre = vec3_or_none(feature.params.get("centre"))
            normal = vec3_or_none(feature.params.get("normal"))
            if (
                centre is None
                or normal is None
                or not all(math.isfinite(v) for v in (*centre, *normal))
                or not math.isfinite(math.hypot(*normal))
                or math.hypot(*normal) <= EPS_GEOM
            ):
                return "fit.not_measurable", _(
                    "Diese Fläche hat keine gemessene Ebene. Eine andere ebene Fläche wählen."
                )
        return None
    if kind == "thread":
        if first.kind != "thread" or second.kind != "thread":
            return "fit.not_measurable", _(
                "Für eine Gewindepassung ein Innen- und ein Außengewinde wählen."
            )
        if _positive(first, "pitch") is None or _positive(second, "pitch") is None:
            return "fit.not_measurable", _(
                "Die Gewindesteigung fehlt. Zwei Gewinde mit gemessener Steigung wählen."
            )
    if {_role(first), _role(second)} != {"inner", "outer"}:
        return "fit.not_measurable", _(
            "Eine Öffnung und ihr Gegenstück wählen, etwa Bohrung und Zapfen."
        )
    if diameter_of(first) is None or diameter_of(second) is None:
        return "fit.not_measurable", _(
            "Ein Durchmesser fehlt. Zwei Merkmale mit gemessenem Durchmesser wählen."
        )
    if kind == "thread":
        first_pitch, second_pitch = _positive(first, "pitch"), _positive(second, "pitch")
        assert first_pitch is not None and second_pitch is not None
        # **Zwei gemessene Steigungen sind auf ihre Unsicherheit gleich, nicht
        # auf ``EPS_GEOM``** (B5, P2.5). Der exakte Leser nennt seine
        # Wendelabweichung, der Netzweg sucht im Raster von 0,01, ein Erzeuger
        # weiß es genau: 0,99 am Netz gegen 1,0000 am exakten Körper ist
        # dieselbe Steigung, 1,25 gegen 1,0 nicht.
        if abs(first_pitch - second_pitch) > (
            _pitch_uncertainty(first) + _pitch_uncertainty(second) + EPS_GEOM
        ):
            return "fit.pitch_mismatch", _(
                "Die Gewindesteigungen unterscheiden sich. Beide Gewinde auf dieselbe "
                "Steigung ändern."
            )
        first_hand = first.params.get("handedness")
        second_hand = second.params.get("handedness")
        if first_hand not in ("right", "left") or second_hand not in ("right", "left"):
            return "fit.not_measurable", _(
                "Die Drehrichtung eines Gewindes ist nicht bekannt. Zwei Gewinde mit "
                "bekannter gleicher Drehrichtung wählen."
            )
        if first_hand != second_hand:
            return "fit.handedness_mismatch", _(
                "Ein Rechtsgewinde und ein Linksgewinde greifen nicht ineinander. "
                "Ein Gegenstück mit derselben Drehrichtung wählen oder die Spiegelung zurücknehmen."
            )
    return None


def _pitch_uncertainty(feature: Feature) -> float:
    """Wie genau die Steigung dieses Gewindes bekannt ist — je nach Herkunft.

    Ein gemessenes Gewinde — am exakten Kern oder am Netz an den Kanten
    (P2.5) — trägt seine Wendelabweichung (``uncertainty``); das Spektrum des
    Netzwegs kennt sie nicht und sucht die Steigung im Raster
    ``helix.PITCH_STEP`` — eine Rasterstufe ist seine Unsicherheit; ein
    erzeugtes Gewinde (``parameter``) ist so genau wie seine Zahl.
    """
    stated = feature.params.get("uncertainty")
    if isinstance(stated, int | float) and math.isfinite(stated) and stated >= 0.0:
        return float(stated)
    if feature.measure_sources.get("pitch") == "fit":
        from app.core.perceive.helix import PITCH_STEP

        return float(PITCH_STEP)
    return 0.0


def pair_kinds(first: Feature, second: Feature) -> tuple[FitKind, ...]:
    """Die sinnvollen neuen Prüfbeziehungen; historische radiale Gewindepaare bleiben lesbar."""
    candidates: tuple[FitKind, ...]
    if first.kind == "thread" or second.kind == "thread":
        candidates = ("thread",)
    elif _role(first) is not None or _role(second) is not None:
        candidates = ("clearance", "press")
    else:
        candidates = ("flush",)
    return tuple(kind for kind in candidates if pair_problem(kind, first, second) is None)


def target(
    scene: Scene, fit: Fit, profile: Profile, *, as_stated: bool = False
) -> tuple[float, tuple[str, ...]]:
    """Sollmaß und tatsächlich verwendete Materialtitel für die sichtbare Anlegeauskunft.

    ``as_stated`` gilt der Gewindepassung: das Sollmaß, wenn beide Gewinde so
    gebaut werden, wie sie dastehen (:func:`_thread_wanted`).
    """
    if fit.kind == "flush":
        return 0.0, ()
    first, second = resolve(scene, fit.a), resolve(scene, fit.b)
    if first is None or second is None or pair_problem(fit.kind, first, second) is not None:
        raise ValueError("fit_not_measurable")
    hole, pin = _sort_by_kind(first, second)
    hole_ref, pin_ref = (fit.a, fit.b) if hole is first else (fit.b, fit.a)
    wanted, _ = _wanted(scene, fit, hole_ref, pin_ref, profile, as_stated=as_stated)
    # Ein Bolzen ohne eigenes Spiel trägt zum Gewinde nichts bei, sein Material
    # also auch nicht.
    pin_counts = fit.kind != "thread" or (not as_stated and _positive(pin, "nominal") is not None)
    references = (hole_ref, pin_ref) if pin_counts else (hole_ref,)
    names = tuple(
        dict.fromkeys(_profile_of(scene, ref, profile).material.title for ref in references)
    )
    return wanted, names


def _condition_value(fit: Fit, document: Document | None) -> float:
    """Die Bedingung liest die aktuelle Operation, nie einen kopierten Altwert."""
    if fit.when_positive is None:
        return 1.0
    if document is None:
        raise ValueError("document_missing")
    operation_id, parameter = fit.when_positive
    operation = next((entry for entry in document.ops if entry.id == operation_id), None)
    if operation is None:
        raise ValueError("operation_missing")
    from app.core.registry import REGISTRY

    fields = {entry.name: entry for entry in REGISTRY.get(operation.op).params.fields()}
    if parameter not in fields:
        raise ValueError("parameter_missing")
    value = operation.params.get(parameter, fields[parameter].default)
    value = resolve_value(value, resolve_parameters(document.parameters))
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("condition_not_numeric")
    return float(value)


def paused_fits(document: Document) -> frozenset[str]:
    """Die Passungen, die mit einem ausgeschalteten Schritt ruhen (P7.3).

    Zwei Wege, und beide stehen im Dokument, keiner wird geraten: die Namen,
    die ein ausgeschalteter Schritt ausdrücklich mitnimmt
    (``Suppression.fits`` — sein Merkmal oder sein Körper entsteht in ihm),
    und eine bedingte Passung, deren Schritt ausgeschaltet ist — ohne ihn gibt
    es den Stift nicht, den ``when_positive`` ein- und ausschaltet. Eine
    ruhende Passung bleibt im Dokument und prüft wieder, sobald ihr Schritt
    eingeschaltet ist.
    """
    resting = {entry.id for entry in document.ops if entry.suppressed is not None}
    if not resting:
        return frozenset()
    names = {
        name
        for entry in document.ops
        if entry.suppressed is not None
        for name in entry.suppressed.fits
    }
    names.update(
        fit.name
        for fit in document.fits
        if fit.when_positive is not None and fit.when_positive[0] in resting
    )
    return frozenset(names)


def active_fits(document: Document) -> list[Fit]:
    """Nur eine gültige nichtpositive Bedingung deaktiviert eine Passung —
    und ein ausgeschalteter Schritt, mit dem sie ruht (:func:`paused_fits`)."""
    active: list[Fit] = []
    paused = paused_fits(document)
    for fit in document.fits:
        if fit.name in paused:
            continue
        try:
            if _condition_value(fit, document) <= 0.0:
                continue
        except AppError, ValueError, TypeError, KeyError:
            # Ungültig bleibt sichtbar; check liefert den zugehörigen Befund.
            pass
        active.append(fit)
    return active


#: Schritte, die eine Passung **herstellen**, ohne sie einzutragen — Deckel,
#: Verbinder, Einsätze, Gewinde. Jeder legt zwei Flächen mit einem gerechneten
#: Spiel aufeinander, aus dem Materialprofil oder der Normteiltabelle; für den
#: Druck heißt das dasselbe wie eine eingetragene Passung: Die Außenwand muss
#: auf Maß, und schnell darf sie dabei nicht sein. Welche Flächen es sind,
#: steht nirgends; für den Ratgeber zählen sie als Schiebesitz
#: (:func:`fit_kinds_for`).
FITTING_OPS: frozenset[str] = frozenset(
    {
        "create_lid",
        "screw_lid",
        "create_container",
        "split_pinned",
        "split_line",
        "insert_snap_fit",
        "insert_dowel",
        "insert_magnet_pocket",
        "insert_heatset_m4",
        "insert_nut_trap",
        "insert_printed_thread",
        "thread_exact",
    }
)


def numbered_name(fits: Collection[Fit], key: str) -> str:
    """Der erste Name ``key_1``, ``key_2`` …, den noch keine dieser Passungen trägt.

    Zwei Passungen mit gleichem Namen wären eine: Der Bericht nennt eine
    Passung beim Namen, und die Karte der Passungen baut ``{name: fit}`` —
    die zweite Verbindung fiele still aus der Prüfung. Wer zwei Stifte setzt,
    hat zwei Paare. Gegenstücke und das Agentenwerkzeug ``add_fit`` benennen
    hierüber; der Deckel zählt nach dem Namen der Objekte
    (``lid_flow.unique_name``).
    """
    used = {entry.name for entry in fits}
    number = 1
    while f"{key}_{number}" in used:
        number += 1
    return f"{key}_{number}"


def _producing(document: Document, object_ids: Collection[str]) -> tuple[set[str], set[int]]:
    """Die Körper und eingeschalteten Schritte, aus denen diese Körper entstanden sind.

    Rückwärts durch den Stapel, **je Körperkennung**: Gibt ein Schritt einen
    gesuchten Körper aus, den er auch als Eingang hat, hat er ihn an Ort und
    Stelle bearbeitet — weiter geht es mit dieser Kennung und mit dem, was der
    Schritt in ihn aufnimmt (Eingänge, die er nicht wieder ausgibt, etwa beim
    Vereinigen). Entsteht der Körper im Schritt neu (Teilen, Deckel,
    Duplikat), zählen alle Eingänge. *Anordnen* und *Ausrichten* führen alle
    Körper als Ein- und Ausgang; über alle Eingänge bekam jeder Körper die
    Herkunft seiner Nachbarn (Review RM-589, N1). Ausgeschaltete Schritte
    zählen nicht.
    """
    wanted = set(object_ids)
    relevant_operations: set[int] = set()
    for operation in reversed(document.ops):
        if operation.suppressed is not None:
            continue
        made = wanted.intersection(operation.outputs)
        if not made:
            continue
        relevant_operations.add(operation.id)
        if made.issubset(operation.inputs):
            wanted.update(set(operation.inputs).difference(operation.outputs))
        else:
            wanted.update(operation.inputs)
    return wanted, relevant_operations


#: Schritte, die ein Loch um die Lochkorrektur des Materials weiten, wenn ihr
#: Haken *Materialtoleranz berücksichtigen* steht (``compensate``). Gefragt
#: wird am Merkmal des fertigen Körpers: Ein gestopftes Loch ist fort, und ein
#: ohne Haken nachgebohrtes nennt seinen letzten Schritt.
COMPENSATING_HOLE_OPS: frozenset[str] = frozenset(
    {"drill_hole", "drill_brep_hole", "resize_hole", "slot_hole", "field_cut"}
)

#: Passungsschritte außerhalb der Bausteine, die das Spiel aus dem Material in
#: die Innenmerkmale legen, die sie selbst erzeugen: das Innengewinde der
#: Kappe (*Drehdeckel erzeugen*, *Behälter mit Deckel*), die Bohrungen der
#: Verbinder (*An Ebene teilen*, *An gezeichneter Linie teilen*), die
#: Scharnierbohrung eines Deckels. Kragen und Hals tragen ihr Spiel außen und
#: sind kein Innenmerkmal; *Schraube erstellen* fehlt deshalb.
PLAY_HOLE_OPS: frozenset[str] = frozenset(
    {"create_lid", "screw_lid", "split_pinned", "split_line", "create_container"}
)

#: *Gegenform einlassen* legt Taschen mit Spiel in den Einsatz, das erste
#: Ergebnis; ein Achsmerkmal tragen sie nicht (:func:`_pocket_closes`).
COUNTER_FORM_OP = "cut_counter_form"

#: Der Schritt, der die ersten Schichten um den Elefantenfuß des Materials
#: einzieht.
FOOT_OP = "compensate_first_layer"

#: Schritte, deren neue Körper reine Kopien ihres Eingangs sind; das
#: eingezogene Band einer Kopie liegt, wo es beim Original liegt. *Stift für
#: Bohrung* und *Behältereinsatz erzeugen* geben ihren Eingang ebenfalls
#: unverändert zurück, bauen daneben aber etwas Neues.
COPY_OPS: frozenset[str] = frozenset({"duplicate_object", "pattern"})

#: Was das Modell eines Körpers schon selbst ausgleicht (RM-589): ``"holes"``
#: — seine Löcher tragen Spiel oder Lochkorrektur aus dem Materialprofil —,
#: ``"foot"`` — seine ersten Schichten sind um den Elefantenfuß eingezogen.
MODEL_ALLOWANCES: tuple[str, ...] = ("holes", "foot")


def allowances_for(document: Document, body: SceneObject) -> tuple[str, ...]:
    """Welche Ausgleiche dieser Körper schon im Modell trägt (RM-589).

    Die Herkunft je Körper wie bei :func:`fit_kinds_for`. Löcher zählen am
    fertigen Körper: an einem Innenmerkmal — Bohrung, Innengewinde, Langloch —,
    das der Slicer in einer Schicht als geschlossene Kontur sieht
    (:func:`_closes_in_a_layer`; eine waagerechte Bohrung weitet sein
    Lochausgleich nicht) und das ein Schritt mit Spiel oder Lochkorrektur aus
    dem Material gemacht hat: mit Haken aus :data:`COMPENSATING_HOLE_OPS`, aus
    :data:`PLAY_HOLE_OPS` oder ein Baustein mit Spiel innen
    (:func:`_part_with_play_inside`). Dazu die Taschen von *Gegenform
    einlassen* (:func:`_pocket_closes`). Eine nur eingetragene Passung ändert
    die Geometrie nicht und zählt nicht. Der Fuß zählt, wo das eingezogene
    Band am Bett liegt (:func:`_foot_on_the_bed`). Der Druckrat stellt dann den
    gleichen Ausgleich des Slicers auf null.
    """
    lineage, relevant = _producing(document, {body.id})
    active = {operation.id: operation for operation in document.ops if operation.suppressed is None}
    steps = [active[identifier] for identifier in sorted(relevant) if identifier in active]
    found: set[str] = set()
    if _foot_on_the_bed(document, body):
        found.add("foot")
    for operation in steps:
        if operation.op == COUNTER_FORM_OP and _pocket_closes(operation, body, lineage):
            found.add("holes")
    # Wer ein erzeugtes Merkmal ohne vermerkten Erzeuger gebaut hat: der
    # Schritt, mit dem der Körper ohne Eingang entstand (*Behälter mit
    # Deckel*, *… erstellen*). Ein erkanntes Langloch ohne Erzeuger stammt aus
    # einem Lochfeld der Herkunft — das Feld benennt nur seine runden Löcher.
    origins = tuple(operation for operation in steps if not operation.inputs)
    fields = tuple(operation for operation in steps if operation.op == "field_cut")
    for feature in body.features.values():
        if feature.kind not in ("hole", "thread", "slot"):
            continue
        if feature.created_by is not None:
            creators: tuple[Operation, ...] = (
                (active[feature.created_by],) if feature.created_by in active else ()
            )
        elif feature.provenance == "generated":
            creators = origins
        else:
            creators = fields if feature.kind == "slot" else ()
        # Erst der billige Blick auf den Erzeuger, dann die Mündungen am Netz.
        if any(_puts_allowance_into(creator) for creator in creators) and _closes_in_a_layer(
            feature, body
        ):
            found.add("holes")
            break
    return tuple(entry for entry in MODEL_ALLOWANCES if entry in found)


def _closes_in_a_layer(feature: Feature, body: SceneObject | None = None) -> bool:
    """Sieht der Slicer dieses Innenmerkmal in einer Schicht als geschlossene Kontur?

    Nur eine solche weitet sein Lochausgleich (OrcaSlicer
    ``_shrink_contour_holes``: die Löcher jedes Schichtumrisses). Hat der
    Mantel eines Lochs oder Langlochs am Körper zwei Ränder, entscheiden deren
    Höhen (:func:`_closes_between_mouths`) — auch bei einer senkrecht
    gebohrten, schrägen Mündung in einer gekippten Platte. Sonst gilt die
    Annahme, dass die Enden quer zur Achse stehen. Ist es um ``θ`` gegen die
    Senkrechte geneigt,
    schneidet eine Schicht die Wand um ein Loch der Länge ``L`` als Streifen
    der Breite ``L/sin θ`` und das Loch vom Durchmesser ``d`` als Ellipse der
    Länge ``d/cos θ``; geschlossen ist die Kontur, solange die Ellipse in den
    Streifen passt: ``L·cos θ > d·sin θ``. Dann bekäme jede geschlossene
    Schicht den Ausgleich ein zweites Mal. Senkrecht zählt jede Länge,
    waagerecht keine; die Grenze folgt aus den Maßen, nicht aus einem Winkel
    (am Schnitt belegt: ``test_a_tilted_hole_counts_while_a_layer_closes_around_it``).
    Ein Langloch nimmt seine größere Weite. Die Achse ist die des fertigen
    Körpers, nach Drehen und Ausrichten.
    """
    if feature.kind == "thread":
        if feature.params.get("internal") is not True:
            return False
        length, across = _positive(feature, "length"), diameter_of(feature)
    elif feature.kind == "hole":
        length, across = _positive(feature, "depth"), diameter_of(feature)
    elif feature.kind == "slot":
        width, extent = diameter_of(feature), _positive(feature, "length")
        length = _positive(feature, "depth")
        across = max(width, extent) if width is not None and extent is not None else None
    else:
        return False
    axis = vec3_or_none(feature.params.get("axis"))
    if axis is None or length is None or across is None:
        return False
    norm = math.hypot(*axis)
    if not math.isfinite(norm) or norm <= EPS_GEOM:
        return False
    if body is not None and feature.kind in ("hole", "slot"):
        between = _closes_between_mouths(body, feature)
        if between is not None:
            return between
    upright = abs(axis[2]) / norm
    tilt = math.hypot(axis[0], axis[1]) / norm
    return length * upright > across * tilt


def _closes_between_mouths(body: SceneObject, feature: Feature) -> bool | None:
    """Liegt das Loch in einer waagerechten Schicht ganz zwischen seinen Mündungen?

    Die Mündungen sind die zwei Randringe des Lochmantels in der verschweißten
    Topologie (dieselben wie bei *Bohrung ändern*, am exakten Körper an seinem
    Netz-Zwilling), schräg oder quer zur Achse, flach oder nicht. Eine Schicht
    auf Höhe ``h`` schneidet den Mantel als geschlossene Kurve, wenn sie keinen
    der beiden Ringe trifft und zwischen ihnen liegt: über jedem Punkt des
    unteren Rings und unter jedem des oberen. Geschlossen ist die Kontur also,
    wenn der tiefste Punkt des oberen Rings über dem höchsten des unteren
    liegt. Für Enden quer zur Achse ist das ``L·cos θ > d·sin θ``; eine
    senkrecht in eine gekippte Platte gebohrte Mündung liegt schräg, und eine
    Bohrung, deren Boden die untere Plattenfläche gerade noch anschneidet, hat
    einen geknickten Ring — beide misst der Ring selbst. Ein Sackloch rechnet
    seinen Boden wie eine Mündung und zählt so eher zu wenig. ``None``, wo der
    Mantel nicht genau zwei Ränder hat.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.prepare_ops import _welded
    from app.core.perceive.relations import boundary_rings

    if not feature.face_indices:
        return None
    mesh = as_mesh_data(body.mesh)
    if int(max(feature.face_indices)) >= len(mesh.raw.faces):
        return None
    welded = _welded(mesh)
    rings = boundary_rings(welded, feature)
    if rings is None or len(rings) != 2:
        return None
    heights = np.asarray(welded.vertices, dtype=np.float64)[:, 2]
    spans = [heights[sorted({vertex for edge in ring for vertex in edge})] for ring in rings]
    lower, upper = sorted(spans, key=lambda span: float(span.mean()))
    return float(upper.min()) - float(lower.max()) > EPS_GEOM


def _pocket_closes(operation: Operation, body: SceneObject, lineage: Collection[str]) -> bool:
    """Liegen die Taschen von *Gegenform einlassen* in diesem Körper senkrecht?

    Der Einsatz ist das erste Ergebnis. Die Tasche läuft vom tiefsten Punkt
    des Teils durch die Oberseite des Einsatzes; geschlossen ist ihr Umriss in
    der Schicht nur, wenn sie senkrecht entnommen wird — seitlich entnommen
    reicht sie in jeder Schicht bis an die Außenwand. Die Taschen tragen kein
    Achsmerkmal; ihre Richtung ist die Entnahmerichtung im Raum des Schritts,
    gedreht um das, was der Rahmen des Körpers seither sagt. Gerechnet wird
    damit, dass der Einsatz beim Einlassen aufrecht stand, wie die Richtung Z
    es vorsieht; wurde er vorher gekippt, zählt er nicht.
    """
    if not operation.outputs or operation.outputs[0] not in lineage:
        return False
    if _step_values(operation).get("axis") != "z":
        return False
    up = _frame_up(body)
    return up is not None and abs(up) >= math.cos(math.radians(EPS_ANGLE))


def _frame_up(body: SceneObject) -> float | None:
    """Wie weit die Z-Achse des Rahmens nach oben zeigt, als Kosinus mit
    Vorzeichen — ``None`` ohne bekannten Rahmen."""
    if body.frame is None:
        return None
    column = tuple(float(body.frame[row][2]) for row in range(3))
    norm = math.hypot(*column)
    if not math.isfinite(norm) or norm <= EPS_GEOM:
        return None
    return column[2] / norm


def _foot_on_the_bed(document: Document, body: SceneObject) -> bool:
    """Liegt das Band, das *Elefantenfuß ausgleichen* eingezogen hat, am Bett?

    Der Schritt zieht ein, was beim Einziehen unten lag. Gezählt wird er nur
    auf der eigenen Linie des Körpers — Schritte, die ihn an Ort und Stelle
    bearbeiten, mit dem, was sie in ihn aufnehmen (*Vereinigen*), und reine
    Kopien (:data:`COPY_OPS`). Baut ein Schritt den Körper aus einem anderen
    neu (die Hälften eines Teilens, der Deckel), liegt das Band nicht unten
    oder fehlt ganz. Dazu muss die Z-Achse des Rahmens nach oben zeigen, mit
    Vorzeichen: Gekippt liegt das Band an einer Seite, gewendet oben. Und am
    fertigen Körper muss das Band unten noch eingezogen sein
    (:func:`_band_drawn_in`): *Abschneiden* oder *Abziehen* nehmen es an Ort
    und Stelle weg, und wer vor dem Einziehen kippt und danach zurückdreht,
    hat es an einer Seite oder oben, obwohl der Rahmen wieder aufrecht steht.
    Im Zweifel behält der Slicer seinen Ausgleich: Doppelt eingezogen wird die
    erste Schicht etwas schmaler, ohne Einzug druckt sie den Wulst
    (Schlussprüfung RM-589, S1; Kontrolle, K1).
    """
    up = _frame_up(body)
    if up is None or up < math.cos(math.radians(EPS_ANGLE)):
        return False
    wanted = {body.id}
    for operation in reversed(document.ops):
        if operation.suppressed is not None:
            continue
        made = wanted.intersection(operation.outputs)
        if not made:
            continue
        in_place = made.intersection(operation.inputs)
        if in_place and operation.op == FOOT_OP:
            return _band_drawn_in(document, body, operation)
        if in_place:
            wanted.update(set(operation.inputs).difference(operation.outputs))
        if made.difference(in_place) and operation.op in COPY_OPS:
            wanted.update(operation.inputs)
    return False


def _band_drawn_in(document: Document, body: SceneObject, operation: Operation) -> bool:
    """Ist der Körper am Bett noch so eingezogen, wie dieser Fußschritt es tat?

    Zwei Schnitte am fertigen Körper: in der Mitte des Bands (Unterseite plus
    halbe Höhe ``h`` des Schritts) und eine halbe Höhe über dem Band. Der
    untere muss im oberen liegen, rundum um den halben Betrag ``a`` eingezogen
    — derselbe Schnitt, mit dem der Schritt das Band baut
    (``geom.prepare.compensate_elephant_foot``). Der Betrag kommt aus dem
    Schritt oder, ohne eigenen, aus dem Material des Körpers oder Projekts.
    Nennt das Dokument keines, rechnete der Schritt mit dem Material des
    Profils, das hier fehlt; dann genügt ein Einzug um ``EPS_DISPLAY`` — ein
    fehlendes Band unterscheidet auch das. Ein Körper, der über dem Band
    breiter wird, besteht die Probe auch ohne Band; dort entscheiden Linie und
    Rahmen.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.knowledge.profiles import material
    from app.core.slice.analysis import cross_section

    values = _step_values(operation)
    height, given = values.get("height"), values.get("amount")
    if not isinstance(height, (int, float)) or not height > EPS_GEOM:
        return False
    amount = float(given) if isinstance(given, (int, float)) else 0.0
    named = body.material or document.material
    if not amount > EPS_GEOM and named:
        try:
            amount = material(named).elephant_foot
        except AppError:
            return False
    elif not amount > EPS_GEOM:
        amount = 2.0 * EPS_DISPLAY
    if not amount > EPS_GEOM:
        return False
    mesh = as_mesh_data(body.mesh)
    bottom = float(mesh.bounds.minimum[2])
    band = cross_section(mesh, bottom + height / 2.0)
    above = cross_section(mesh, bottom + 1.5 * height)
    if band is None or above is None or band.is_empty or above.is_empty:
        return False
    # Was übersteht, darf nur Rundungsrest der Schnitte sein — ein Streifen von
    # EPS_GEOM Breite entlang des Umrisses; ein fehlendes Band steht um a/2 über.
    outside = band.difference(above.buffer(-amount / 2.0))
    return bool(outside.area <= EPS_GEOM * band.length)


def _puts_allowance_into(operation: Operation) -> bool:
    """Legt dieser Schritt Spiel oder Lochkorrektur des Materials in seine Innenmerkmale?"""
    if operation.op in COMPENSATING_HOLE_OPS:
        from app.core.geom.field_ops import COMPENSATED_SHAPES

        values = _step_values(operation)
        return values.get("compensate") is True and (
            operation.op != "field_cut" or values.get("shape") in COMPENSATED_SHAPES
        )
    return operation.op in PLAY_HOLE_OPS or _part_with_play_inside(operation)


def _step_values(operation: Operation) -> dict[str, object]:
    """Die Parameter eines Schritts samt Vorgaben; ohne Registereintrag (der
    exakte Kern fehlt) nur, was im Schritt steht."""
    from app.core.registry import REGISTRY

    schema = REGISTRY.get(operation.op).params.fields() if REGISTRY.has(operation.op) else ()
    return {entry.name: entry.default for entry in schema} | dict(operation.params)


def _part_with_play_inside(operation: Operation) -> bool:
    """Legt dieser Bausteinschritt sein Spiel in eine Innenkontur?

    Abtragend (``parts.ops.cuts``, dieselbe Auskunft wie Operation und
    Vorschau) mit Spiel oder Übermaß aus dem Material, oder aufgesetzt mit
    einer Bohrung, die das Spiel trägt (``PartSpec.play_inside``). Gezählt
    wird nur an einem Innenmerkmal des Bausteins (:func:`allowances_for`).
    """
    from types import SimpleNamespace

    from app.core.knowledge.parts import ops as part_ops

    spec = part_ops.part_of(operation.op)
    if spec is None:
        return False
    fields = {entry.name for entry in spec.params.spec()}
    if not fields & {part_ops.PLAY_FIELD, part_ops.GRIP_FIELD}:
        return False
    values = cast(BaseParams, SimpleNamespace(**_step_values(operation)))
    return spec.play_inside or part_ops.cuts(spec, values)


def fit_kinds_for(document: Document, object_ids: Collection[str]) -> tuple[str, ...]:
    """Welche Passungen diese Körper tragen — eingetragene und gebaute.

    Die Körper und alles, woraus sie entstanden sind (:func:`_producing`, je
    Körperkennung — nach *Anordnen* trägt kein Körper die Passung seines
    Nachbarn). Eine eingetragene aktive Passung zählt mit ihrer Art
    (:func:`active_fits`). Ein passender, eingeschalteter Schritt ohne gebundene
    Passung zählt als Schiebesitz (:data:`FITTING_OPS`), etwa eine ältere
    Mutternfalle mit Spiel aus der Normteiltabelle. Ausgeschaltete Schritte
    zählen nicht.

    Zurück kommen die **Arten**, nicht bloß ein Ja: Eine bündige Passung
    verlangt eine Einstellung mehr als ein Schiebesitz. Der Druckdialog fragt
    für die Körper der Platte, der Export je Teil (Entscheidung G).
    """
    wanted, relevant_operations = _producing(document, object_ids)
    kinds: list[str] = [
        entry.kind
        for entry in active_fits(document)
        if entry.a.object_id in wanted or entry.b.object_id in wanted
    ]
    bound_operations = {
        entry.when_positive[0] for entry in document.fits if entry.when_positive is not None
    }
    if any(
        entry.op in FITTING_OPS
        and entry.id in relevant_operations
        and entry.id not in bound_operations
        for entry in document.ops
    ):
        kinds.append("clearance")
    return tuple(dict.fromkeys(kinds))


def check(
    scene: Scene,
    profile: Profile,
    *,
    document: Document | None = None,
    cancelled: CancelToken | None = None,
) -> list[Finding]:
    """Prüft jede Passung der Szene. Verletzungen sind nie still (§14)."""
    if document is None and any(fit.when_positive is not None for fit in scene.fits):
        raise InternalError(detail="Bedingte Passungen brauchen ihr Dokument für die Prüfung.")
    token = cancelled if cancelled is not None else NeverCancelled()
    token.raise_if_cancelled()
    findings: list[Finding] = []
    for fit in scene.fits:
        token.raise_if_cancelled()
        try:
            if _condition_value(fit, document) <= 0.0:
                continue
        except (AppError, ValueError, TypeError, KeyError) as problem:
            findings.append(
                Finding(
                    code="fit.invalid_condition",
                    severity="error",
                    message=_(
                        "Die Bedingung dieser Passung lässt sich nicht auswerten. Den "
                        "zugehörigen Schritt und seinen Parameter prüfen."
                    ),
                    object_id=fit.a.object_id,
                    values={"fit": fit.name, "reason": str(problem)},
                    # Regel 17, derselbe Weg wie ``fit.missing_feature``: Eine
                    # Passung gehört keinem Schritt, und im Verlauf steht der,
                    # dessen Parameter der Satz meint.
                    suggestions=(SHOW_HISTORY,),
                )
            )
            continue
        findings.extend(_check_one(scene, fit, profile, token))
    token.raise_if_cancelled()
    return findings


def _check_one(scene: Scene, fit: Fit, profile: Profile, cancelled: CancelToken) -> list[Finding]:
    return [*_check_pair(scene, fit, profile, cancelled), *_standard_size_notes(scene, fit)]


def _standard_size_notes(scene: Scene, fit: Fit) -> list[Finding]:
    """Was die Wahl des Gegenstücks über ein gemessenes Gewinde sagt — im Bericht.

    Ein gemessenes Ø 6,0 x 1,03 bekommt als Gegenstück ein M6 x 1, und der
    Satz dazu (``counterpart.thread_size_note``) stand nur in der Statuszeile:
    Wer sie verpasste, erfuhr nicht, dass die Normgröße statt des gemessenen
    Maßes gebaut wurde (Review RM-532 Runde 2, K-N4). Hier gehört er zur
    Passung, solange sie besteht — an der gemessenen Hälfte, wenn die andere
    ein Bibliotheksgewinde ist (es trägt sein Nennmaß, ``nominal``).
    """
    if fit.kind != "thread":
        return []
    from app.core.counterpart import thread_size_note

    notes: list[Finding] = []
    for reference, partner in ((fit.a, fit.b), (fit.b, fit.a)):
        measured, made = resolve(scene, reference), resolve(scene, partner)
        if (
            measured is None
            or made is None
            or measured.kind != "thread"
            or made.kind != "thread"
            or measured.provenance == "generated"
            or _positive(made, "nominal") is None
            or _pair_problem(fit.kind, measured, made) is not None
        ):
            continue
        try:
            note = thread_size_note(measured)
        except AppError:
            continue
        if note is not None:
            notes.append(
                replace(note, object_id=reference.object_id, feature_ids=(reference.feature_id,))
            )
    return notes


def _check_pair(scene: Scene, fit: Fit, profile: Profile, cancelled: CancelToken) -> list[Finding]:
    first = resolve(scene, fit.a)
    second = resolve(scene, fit.b)
    if first is None or second is None:
        # **Der Satz nennt den Grund und einen Weg.** Er nannte keinen von
        # beiden, und der häufigste Fall ist einer, in den ein Kunde ohne
        # Warnung hineinläuft: Er öffnet „Dose mit Deckel", schreibt seinen
        # Namen darauf — und der Prüfbericht meldet einen Fehler. Eine
        # Boolesche Operation baut den Körper neu, die Merkmale werden neu
        # erkannt, und die vom Deckel *benannten* (`lid_cavity`) sind dabei
        # nicht mehr. Wer das nicht weiß, sucht den Fehler in seiner
        # Beschriftung.
        #
        # **Und er nennt keine Ursache, die er nicht kennt** (RM-189). Seit die
        # erzeugten Merkmale solche Schritte überstehen, trifft der Fall vor
        # allem erkannte: *Glätten* oder starkes *Dreiecke verringern* nimmt
        # einer Bohrung die Zylinderform. Der Satz „benannte Merkmale überstehen
        # das nicht" war dort falsch; welcher Schritt es war, sagt der Befund
        # am Schritt selbst (``perceive.referenced_lost``), und der Verlauf
        # führt dorthin.
        return [
            Finding(
                code="fit.missing_feature",
                severity="error",
                message=_(
                    "Ein Merkmal dieser Passung gibt es nicht mehr, oder es ist nach einem "
                    "späteren Schritt nicht mehr erkennbar."
                ),
                values={"fit": fit.name, "a": str(fit.a), "b": str(fit.b)},
                # Ein Merkmal, das es nicht mehr gibt, lässt sich nicht
                # ansteuern — der Körper aber schon. Das ist die zweite Stufe
                # der Zusage aus §18.4, und ohne diese Zeile war es keine.
                object_id=fit.a.object_id,
            )
        ]

    problem = _pair_problem(fit.kind, first, second)
    if problem is not None:
        code, message = problem
        values = {"fit": fit.name, "a": str(fit.a), "b": str(fit.b)}
        if code == "fit.pitch_mismatch":
            values.update(
                first_pitch=format_length(float(first.params["pitch"])),
                second_pitch=format_length(float(second.params["pitch"])),
            )
        findings = [
            Finding(
                code=code,
                severity="warning",
                message=message,
                values=values,
                object_id=fit.a.object_id,
                feature_ids=(fit.a.feature_id,),
                # Regel 17: Die zwei Merkmale passen ihrer Art nach nicht
                # zueinander; das Merkmal zeigt, woran es liegt.
                suggestions=(SHOW_FEATURE,),
            )
        ]
        if fit.kind == "flush":
            findings.extend(_geometry_findings(scene, fit, first, second, fit.a, fit.b, cancelled))
        return findings

    if fit.kind == "flush":
        return [
            *_check_flush(fit, first, second),
            *_geometry_findings(scene, fit, first, second, fit.a, fit.b, cancelled),
        ]

    hole, pin = _sort_by_kind(first, second)
    hole_diameter = diameter_of(hole)
    pin_diameter = diameter_of(pin)
    if hole_diameter is None or pin_diameter is None:
        return [
            Finding(
                code="fit.not_measurable",
                severity="warning",
                message=_("Diese Passung lässt sich nicht messen — es fehlt ein Durchmesser."),
                values={"fit": fit.name},
                object_id=fit.a.object_id,
                feature_ids=(fit.a.feature_id,),
                # Regel 17: Das Merkmal zeigt, welches Maß fehlt.
                suggestions=(SHOW_FEATURE,),
            )
        ]

    # Aus welchem der zwei Verweise das Loch kam: _sort_by_kind kann sie
    # getauscht haben, und „hole_1" ist nur im eigenen Objekt eindeutig.
    hole_ref, pin_ref = (fit.a, fit.b) if hole is first else (fit.b, fit.a)
    wanted, materials = _wanted(scene, fit, hole_ref, pin_ref, profile)
    actual = hole_diameter - pin_diameter
    geometry = _geometry_findings(scene, fit, hole, pin, hole_ref, pin_ref, cancelled)
    if abs(actual - wanted) <= FIT_TOLERANCE:
        if fit.kind in {"clearance", "press"}:
            uncertainty = _mesh_clearance(fit, hole, pin, hole_ref, wanted)
            if uncertainty is not None:
                return [uncertainty, *geometry]
        return geometry

    return [
        Finding(
            code="fit.violated",
            severity="warning",
            message=_message_for(actual, wanted),
            values={
                "fit": fit.name,
                "actual": format_length(actual),
                "expected": format_length(wanted),
                **({"materials": materials} if materials else {}),
            },
            # **Wohin der Klick führt.** Genannt wird das Loch und nicht der
            # Zapfen: Bei einer Schiebepassung ist die Öffnung die Stelle, an
            # der man nachsieht. Aus dem Merkmal rechnet `maps.location_of`
            # den Punkt, zu dem die Kamera fliegt.
            object_id=hole_ref.object_id,
            feature_ids=(hole_ref.feature_id,),
            # Regel 17: Geändert wird das Maß des Merkmals, nicht die Passung.
            suggestions=(SHOW_FEATURE,),
        ),
        *geometry,
    ]


def _axis_span(feature: Feature) -> tuple[np.ndarray, np.ndarray, float] | None:
    """Gemessene Achse mit Mittelpunkt und axialer Ausdehnung, ohne Ersatz aus dem Körpermaß."""
    centre = vec3_or_none(feature.params.get("centre"))
    axis = vec3_or_none(feature.params.get("axis"))
    length = _positive(feature, "depth") or _positive(feature, "length")
    if centre is None or axis is None or length is None:
        return None
    size = math.hypot(*axis)
    if not all(math.isfinite(value) for value in (*centre, *axis, size)) or size <= EPS_GEOM:
        return None
    return np.asarray(centre), np.asarray(axis) / size, length


def _shared_pose(first: SceneObject, second: SceneObject, hole: Feature, pin: Feature) -> bool:
    """Nur dieselbe koaxiale Einbaulage mit belegter axialer Überlappung ist prüfbar."""
    if first.id == second.id or first.plate != second.plate:
        return False
    left, right = _axis_span(hole), _axis_span(pin)
    if left is None or right is None:
        return False
    centre, axis, length = left
    other_centre, other_axis, other_length = right
    offset = other_centre - centre
    along = float(offset @ axis)
    # Die seitliche Abweichung an beiden Enden wird in mm geprüft. Eine
    # Winkelschwelle allein könnte bei einem langen Zapfen einen Versatz erlauben.
    endpoints = (offset - other_axis * other_length / 2, offset + other_axis * other_length / 2)
    if any(float(np.linalg.norm(point - (point @ axis) * axis)) > EPS_GEOM for point in endpoints):
        return False
    projected = other_length * abs(float(axis @ other_axis))
    overlap = min(length / 2, along + projected / 2) - max(-length / 2, along - projected / 2)
    return overlap > EPS_GEOM


@dataclass(frozen=True)
class GeometryProbe:
    """Was die Körperprobe einer Passung gemessen hat — Zahlen ohne Urteil.

    ``source`` sagt, woran gemessen wurde: ``native`` an zwei exakten Körpern,
    ``mesh`` an zwei Netzen, ``mixed`` am Netzzwilling eines exakten Körpers
    neben einem Netz — dann ist die Zahl eine Näherung.
    """

    source: str
    overlap_mm3: float

    @property
    def intersects(self) -> bool:
        return self.overlap_mm3 > 0.0


def _pose_proven(
    scene: Scene,
    fit: Fit,
    first_feature: Feature,
    second_feature: Feature,
    first_ref: FeatureRef,
    second_ref: FeatureRef,
) -> bool:
    """Ob die Lage der zwei Körper zueinander die Einbaulage der Passung ist.

    Zwei Teile nebeneinander auf dem Bett, ein Deckel auf einer anderen Platte,
    zwei Flächen desselben Körpers: Dort ist die Einbaulage nicht modelliert,
    und eine Probe der Körper sagte nichts über die Passung. Bündige Flächen
    brauchen keine radiale Lage — zwei verschiedene Körper auf derselben
    Platte genügen; ein radiales Paar muss koaxial mit überlappender
    Einstecktiefe stehen (`_shared_pose`).
    """
    first, second = scene.objects[first_ref.object_id], scene.objects[second_ref.object_id]
    if fit.kind == "flush":
        return first.id != second.id and first.plate == second.plate
    return _shared_pose(first, second, first_feature, second_feature)


def _probe(first: SceneObject, second: SceneObject, cancelled: CancelToken) -> GeometryProbe:
    """Die starre Verschneidung zweier Körper in ihrer aktuellen Lage."""
    from app.core.geom.measure import body_overlap

    kinds = (kind_of(first.mesh), kind_of(second.mesh))
    source = "native" if kinds == ("brep", "brep") else "mesh" if kinds[0] == kinds[1] else "mixed"
    cancelled.raise_if_cancelled()
    volume = body_overlap(first.mesh, second.mesh, cancelled=cancelled)
    cancelled.raise_if_cancelled()
    return GeometryProbe(source=source, overlap_mm3=volume)


def overlap(
    scene: Scene, fit: Fit, *, cancelled: CancelToken | None = None
) -> GeometryProbe | None:
    """Die Körperprobe einer Passung als Zahl — die eigene Auskunft für die
    Passungskarte und jeden, der das gemessene Volumen braucht, ohne den
    Prüfbericht zu lesen.

    ``None`` heißt: Ein Merkmal fehlt, das Paar ist nicht messbar oder die
    Einbaulage ist nicht belegt (`_pose_proven`) — dann gibt es keine Zahl,
    und der Prüfbericht trägt dazu auch keinen Befund. Ein Fehler des Kerns
    wird hier nicht verschluckt: Im Bericht heißt er `fit.geometry_failed`,
    hier ist er die Ausnahme selbst.
    """
    first, second = resolve(scene, fit.a), resolve(scene, fit.b)
    if first is None or second is None:
        return None
    first_ref, second_ref = fit.a, fit.b
    if fit.kind != "flush":
        try:
            hole, _pin = _sort_by_kind(first, second)
        except ValueError:
            return None
        if hole is not first:
            first, second = second, first
            first_ref, second_ref = second_ref, first_ref
    if not _pose_proven(scene, fit, first, second, first_ref, second_ref):
        return None
    token = cancelled if cancelled is not None else NeverCancelled()
    return _probe(scene.objects[first_ref.object_id], scene.objects[second_ref.object_id], token)


def _geometry_findings(
    scene: Scene,
    fit: Fit,
    first_feature: Feature,
    second_feature: Feature,
    first_ref: FeatureRef,
    second_ref: FeatureRef,
    cancelled: CancelToken,
) -> list[Finding]:
    """Die Körperprobe in belegter Einbaulage — und ohne belegte Lage nichts.

    Bis zum 21.09.2026 stand hier für jede Passung ein Befund: eine Warnung
    „Einbaulage nicht belegt" an zwei Teilen, die zum Drucken nebeneinander
    liegen — nicht behebbar, denn *Anordnen* zieht sie gerade auseinander —,
    und ein Hinweis „überschneiden sich nicht" an jeder gelungenen Passung.
    Damit begrüßten „Dose mit Deckel" und „Passung nach Materialwechsel" mit
    einer Warnung, und ein Teil mit einer Passung war nie „druckbereit"
    (Regel: eine Warnung, die im Normalfall kommt, ist keine Warnung mehr).

    Jetzt entsteht ein Befund nur, wenn die Probe etwas zu sagen hat:

    * Überschneidung zweier gleichartiger Körper — `fit.collision`, Warnung.
    * Gemischte Zwillinge — `fit.geometry_approximate`: Warnung bei
      Überschneidung, sonst Hinweis, denn die Zahl ist eine Netznäherung.
    * Presspassung — `fit.press_unverified`, Hinweis: Übermaß ist dort
      vorgesehen, und eine starre Probe belegt weder Montage noch Verformung.
    * Kernfehler — `fit.geometry_failed`, Warnung.

    Eine leere Verschneidung ist kein Befund; die Zahl dazu gibt `overlap`.
    """
    if not _pose_proven(scene, fit, first_feature, second_feature, first_ref, second_ref):
        return []
    first, second = scene.objects[first_ref.object_id], scene.objects[second_ref.object_id]
    values: dict[str, float | str | TranslatableText] = {
        "fit": fit.name,
        "a": first.id,
        "b": second.id,
    }
    severity: Severity = "warning"
    flush = fit.kind == "flush"
    try:
        probe = _probe(first, second, cancelled)
    except OperationCancelled:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # Native Kerne haben eigene Fehlerklassen.
        cancelled.raise_if_cancelled()
        _log.warning("fit geometry probe failed: %s", problem)
        code = "fit.geometry_failed"
        values["reason"] = str(problem)
        message = _(
            "Die Körper dieser Passung konnten geometrisch nicht geprüft werden. "
            "Geschlossene gültige Körper verwenden oder die Geometrie erneut prüfen."
        )
    else:
        values["geometry_source"] = probe.source
        values["overlap_mm3"] = probe.overlap_mm3
        values["intersects"] = probe.intersects
        mixed = probe.source == "mixed"
        if fit.kind == "press":
            code = "fit.press_unverified"
            severity = "info"
            message = (
                _(
                    "Bei einer Presspassung ist Übermaß vorgesehen. Diese starre Körperprobe "
                    "bestätigt weder die Montage noch die Verformung; "
                    "auch Boden und Schulter prüfen."
                )
                if probe.intersects
                else _(
                    "Bei einer Presspassung ist Übermaß vorgesehen, doch in dieser Einbaulage "
                    "überschneiden sich die Körper nicht. Die tatsächlichen Konturen und die "
                    "Einstecktiefe prüfen."
                )
            )
        elif mixed:
            code = "fit.geometry_approximate"
            if not probe.intersects:
                severity = "info"
            if flush:
                message = (
                    _(
                        "Die Netznäherung zeigt eine Überschneidung in der aktuellen Lage. "
                        "Die exakten Körper und die Auflösung der Näherung prüfen."
                    )
                    if probe.intersects
                    else _(
                        "Die Netznäherung zeigt in der aktuellen Lage keine Überschneidung. "
                        "Ein Flächenkontakt und der Montageweg sind damit nicht nachgewiesen; "
                        "die exakten Körper separat prüfen."
                    )
                )
            else:
                message = (
                    _(
                        "Die Netznäherung zeigt eine Überschneidung in dieser Einbaulage. "
                        "Die exakten Körper und die Auflösung der Näherung prüfen."
                    )
                    if probe.intersects
                    else _(
                        "Die Netznäherung zeigt in dieser Einbaulage keine Überschneidung. "
                        "Die exakten Körper und den Montageweg separat prüfen."
                    )
                )
        elif probe.intersects:
            code = "fit.collision"
            message = (
                _(
                    "Die Körper überschneiden sich in der aktuellen Lage. "
                    "Die gesamten Körper und ihre Platzierung prüfen."
                )
                if flush
                else _(
                    "Die Körper überschneiden sich in dieser Einbaulage. Einstecktiefe, "
                    "Boden, Schulter und die tatsächlichen Konturen prüfen."
                )
            )
        else:
            return []
    return [
        Finding(
            code=code,
            severity=severity,
            message=message,
            values=values,
            object_id=first_ref.object_id,
            feature_ids=(first_ref.feature_id,),
        )
    ]


def _mesh_clearance(
    fit: Fit, hole: Feature, pin: Feature, hole_ref: FeatureRef, wanted: float
) -> Finding | None:
    """Kreismaß und tatsächliches radiales Netzband nicht als dieselbe Messung behandeln.

    Die Differenz der äußeren Bandgrenzen ist eine konservative Auskunft.
    Sie beweist weder eine konkrete Kollision noch die passende Winkelstellung
    zweier Polygone. Ein nicht belegtes Spiel bleibt deshalb ausdrücklich offen.
    """
    if not any(
        "radial_min" in feature.params or "radial_max" in feature.params for feature in (hole, pin)
    ):
        return None
    bands = []
    for feature in (hole, pin):
        if not any(key in feature.params for key in ("radial_min", "radial_max")):
            diameter = diameter_of(feature)
            assert diameter is not None
            bands.append((diameter / 2.0, diameter / 2.0))
            continue
        low, high = _positive(feature, "radial_min"), _positive(feature, "radial_max")
        if low is None or high is None or low > high:
            return Finding(
                code="fit.not_measurable",
                severity="warning",
                message=_(
                    "Die Netzmaße dieser Passung sind nicht vollständig bestimmt. "
                    "Die Merkmale erneut erkennen oder eine genauer aufgelöste Datei verwenden."
                ),
                values={"fit": fit.name},
                object_id=hole_ref.object_id,
                feature_ids=(hole_ref.feature_id,),
                # Regel 17: Das Merkmal zeigt, welches Maß fehlt.
                suggestions=(SHOW_FEATURE,),
            )
        bands.append((low, high))
    minimum = 2.0 * (bands[0][0] - bands[1][1])
    maximum = 2.0 * (bands[0][1] - bands[1][0])
    within = minimum >= wanted - FIT_TOLERANCE and maximum <= wanted + FIT_TOLERANCE
    possible_interference = fit.kind == "clearance" and minimum < -EPS_GEOM
    if within and not possible_interference:
        return None
    return Finding(
        code="fit.mesh_uncertain",
        severity="warning",
        message=_(
            "Die geschätzten Kreismaße passen, die Netzflächen belegen das Spiel aber nicht. In "
            "Einbaulage prüfen oder eine feinere Datei verwenden."
        ),
        values={
            "fit": fit.name,
            "clearance_min_mm": minimum,
            "clearance_max_mm": maximum,
            "expected": format_length(wanted),
        },
        object_id=hole_ref.object_id,
        feature_ids=(hole_ref.feature_id,),
        # Regel 17: Das Merkmal zeigt die Maße, an denen die Unsicherheit hängt.
        suggestions=(SHOW_FEATURE,),
    )


def _wanted(
    scene: Scene,
    fit: Fit,
    hole: FeatureRef,
    pin: FeatureRef,
    profile: Profile,
    *,
    as_stated: bool = False,
) -> tuple[float, str]:
    """Das Spiel, das diese Passung haben soll, in den Materialien, aus denen
    sie besteht (§12).

    Ein benannter Verweis (``auto:petg``) bleibt, was er sagt — dieses
    Material hat jemand mit Absicht hingeschrieben. Das nackte ``auto:``
    heißt „worin das eben gedruckt wird", und das ist nicht unbedingt eines:
    eine TPU-Dichtung im PETG-Gehäuse hat zwei Antworten.

    Wo sie sich unterscheiden, gewinnt der größere Wert — eine Regel für beide
    Arten statt zwei. Ein Spiel ist positiv, der größere Wert also der
    weitere Spalt: es geht zusammen. Ein Pressmaß ist negativ, der größere
    Wert also das *kleinere* Übermaß: es sprengt das Teil nicht, in das
    gepresst wird. Beide Male fällt die Wahl auf die Seite, deren Scheitern
    ein brauchbares Teil übrig lässt — eine Verbindung, die locker sitzt,
    kann man kleben; ein Gehäuse, das beim Zusammenbau gerissen ist, ist
    Ausschuss.

    Ein Gewinde ist die Summe seiner zwei Hälften (:func:`_thread_wanted`).
    """
    if fit.kind == "thread" and isinstance(fit.tolerance, str):
        return _thread_wanted(scene, fit.tolerance, hole, pin, profile, as_stated=as_stated)
    if not isinstance(fit.tolerance, str) or fit.tolerance != AUTO_TOLERANCE_PREFIX:
        return resolve_tolerance(fit.tolerance, fit.kind, profile), ""

    both = [_profile_of(scene, hole, profile), _profile_of(scene, pin, profile)]
    chosen = max(resolve_tolerance(fit.tolerance, fit.kind, entry) for entry in both)

    names = {entry.material.id for entry in both}
    return chosen, ", ".join(sorted(names)) if len(names) > 1 else ""


def _thread_wanted(
    scene: Scene,
    tolerance: str,
    hole: FeatureRef,
    pin: FeatureRef,
    profile: Profile,
    *,
    as_stated: bool,
) -> tuple[float, str]:
    """Das Spiel einer Gewindepassung: was jede Hälfte in ihrem Material trägt.

    Verglichen wird gebaut gegen gebaut — ein eingelesenes Gewinde nennt sein
    gemessenes Maß, ein gedrucktes sein gebautes. Ein gedrucktes Gewinde aus
    der Bibliothek (es nennt sein Nennmaß, ``nominal``) ist um das Spiel
    seines Materials daneben gebaut; ein Gewinde ohne Nennmaß trägt als Loch
    die Lochkorrektur, als Bolzen nichts (``profiles.thread_share``). Ein
    gedrucktes Paar soll also zweimal das Spiel haben, ein gedruckter Bolzen
    in einer eingelesenen Mutter Spiel plus Lochkorrektur.

    ``as_stated`` fragt, was die Passung verlangt, wenn beide Hälften so
    gebaut werden, wie sie dastehen — so setzt *Merkmal ändern* ein Gewinde,
    und so rechnet die Kopplung das Gegengewinde (``counterpart``).
    """
    shares: list[tuple[str, float]] = []
    for reference, inner in ((hole, True), (pin, False)):
        feature = resolve(scene, reference)
        printed = (
            not as_stated and feature is not None and _positive(feature, "nominal") is not None
        )
        own = _profile_of(scene, reference, profile)
        share = thread_share(tolerance, own, inner=inner, printed=printed)
        if share > 0.0:
            shares.append((own.material.id, share))
    names = {name for name, _share in shares}
    explicit = tolerance != AUTO_TOLERANCE_PREFIX
    return (
        sum(share for _name, share in shares),
        ", ".join(sorted(names)) if len(names) > 1 and not explicit else "",
    )


def _profile_of(scene: Scene, reference: FeatureRef, profile: Profile) -> Profile:
    """Das Profil des Körpers, auf den ein Passungsverweis zeigt."""
    return for_object(profile, scene.objects.get(reference.object_id))


def _check_flush(fit: Fit, first: Feature, second: Feature) -> list[Finding]:
    """Zwei Flächen, die in einer Ebene sitzen sollen (§14).

    Gemessen als Abstand des Mittelpunkts der zweiten Fläche von der Ebene der
    ersten. Das ist die Zahl, für die jemand ein Haarlineal über den
    Zusammenbau legen würde, und sie entscheidet, ob ein Deckel übersteht.

    Ein Flächenpaar, das nicht parallel steht, ist ein anderer Fehler und
    bekommt das gesagt: zwei Ebenen im Winkel haben keinen Abstand, der sich
    zu melden lohnt.
    """
    if first.kind != "face" or second.kind != "face":
        return [
            Finding(
                code="fit.not_measurable",
                severity="warning",
                message=_("Eine bündige Passung braucht zwei Flächen."),
                values={"fit": fit.name, "a": first.kind, "b": second.kind},
                object_id=fit.a.object_id,
                feature_ids=(fit.a.feature_id,),
                # Regel 17: Das Merkmal zeigt, welches Maß fehlt.
                suggestions=(SHOW_FEATURE,),
            )
        ]

    normal = vec3_or_none(first.params.get("normal"))
    other = vec3_or_none(second.params.get("normal"))
    centre = vec3_or_none(first.params.get("centre"))
    against = vec3_or_none(second.params.get("centre"))
    if normal is None or other is None or centre is None or against is None:
        return [
            Finding(
                code="fit.not_measurable",
                severity="warning",
                message=_("Diese Passung lässt sich nicht messen — es fehlt eine Fläche."),
                values={"fit": fit.name},
                object_id=fit.a.object_id,
                feature_ids=(fit.a.feature_id,),
                # Regel 17: Das Merkmal zeigt, welches Maß fehlt.
                suggestions=(SHOW_FEATURE,),
            )
        ]

    normal_size, other_size = math.hypot(*normal), math.hypot(*other)
    normal = (normal[0] / normal_size, normal[1] / normal_size, normal[2] / normal_size)
    other = (other[0] / other_size, other[1] / other_size, other[2] / other_size)
    signed = sum(a * b for a, b in zip(normal, other, strict=True))
    # Bündig verlangt dieselbe Ebene, keinen acht Grad breiten Winkelbereich —
    # aber eine **Winkel**toleranz, keine Längentoleranz: ``EPS_GEOM`` auf dem
    # Abstand zweier Einheitsvektoren wären 0,00006 Grad, und schon der
    # Float32-Umlauf einer STL streut die Normalen einer ebenen Fläche um das
    # Zehnfache (gemessen 06.09.2026: 5,7e-6 an einer 10-mm-Platte bei 180 mm).
    # Parallel ist, was der Erkenner selbst als eine Ebene führt (§21):
    # ``EPS_ANGLE`` in Grad, dieselbe Schwelle wie beim Zusammenfassen der
    # Dreiecke zu einer Fläche.
    angle = math.degrees(math.acos(min(1.0, abs(signed))))
    if angle > EPS_ANGLE:
        return [
            Finding(
                code="fit.violated",
                severity="warning",
                message=_("Die beiden Flächen stehen nicht parallel — bündig können sie nicht."),
                values={"fit": fit.name, "alignment": abs(signed)},
                object_id=fit.a.object_id,
                feature_ids=(fit.a.feature_id,),
                # Regel 17: Geändert wird das Maß des Merkmals, nicht die Passung.
                suggestions=(SHOW_FEATURE,),
            )
        ]

    offset = abs(sum((b - a) * n for a, b, n in zip(centre, against, normal, strict=True)))
    if offset <= FIT_TOLERANCE:
        return []
    return [
        Finding(
            code="fit.violated",
            severity="warning",
            message=_("Die beiden Flächen sitzen nicht bündig."),
            values={"fit": fit.name, "actual": format_length(offset), "expected": "0 mm"},
            # Die erste Fläche ist die Bezugsebene, gegen die gemessen
            # wird — und damit die Stelle, an der man nachsieht.
            object_id=fit.a.object_id,
            feature_ids=(fit.a.feature_id,),
            # Regel 17: Geändert wird das Maß des Merkmals, nicht die Passung.
            suggestions=(SHOW_FEATURE,),
        )
    ]


def _sort_by_kind(first: Feature, second: Feature) -> tuple[Feature, Feature]:
    """Das Loch zuerst, der Stift danach — egal, wie herum sie geschrieben
    wurden."""
    if _role(first) == "inner":
        return first, second
    if _role(second) == "inner":
        return second, first
    raise ValueError("fit_inner_role_missing")


def _message_for(actual: float, wanted: float) -> TranslatableText:
    """Die Meldung zu einer Passung, die nicht sitzt wie gewollt.

    Der Marker steht hier an den Zeichenketten und **nicht** um den Aufruf
    herum. Das ist kein Geschmack: Der Sammler nimmt nur Konstanten, die
    unmittelbar in ``_()`` stehen (``app/i18n/extract.py``). Als
    ``_(_message_for(...))`` geschrieben, sah der Aufruf übersetzt aus, war
    es aber nie — beide Sätze standen in keinem Katalog, und im spanischen
    Handbuchbild stand ein deutscher Befund zwischen sieben spanischen.
    """
    if actual < wanted:
        return _("Die Passung sitzt enger als vorgesehen.")
    return _("Die Passung sitzt loser als vorgesehen.")
