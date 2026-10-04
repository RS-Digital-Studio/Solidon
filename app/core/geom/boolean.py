"""Boolesche Operationen mit der Rückfallkette (Bauplan §17.2).

| Stufe | Was sie tut                                     | Vermerk     |
|-------|-------------------------------------------------|-------------|
| 1     | direkt durch den Kern                           | ``direct``  |
| 2     | verschweißen, aufräumen, erneut                 | ``welded``  |
| 3     | die Eingangsgeometrie minimal stören            | ``jittered``|
| 4     | auf Voxeln rechnen, das Ergebnis neu vernetzen  | ``voxel``   |
| 5     | aufgeben, mit Befund und Weg nach vorn          | —           |

Die Stufe, die es geschafft hat, wird in die Operation geschrieben — so
rechnet dieselbe Datei gleich nach (§11.3), und der Bericht kann sagen, was
die Zahlen wert sind. Stufe 4 kostet Genauigkeit und läuft nie
stillschweigend.

In Entwurfsqualität endet die Kette nach Stufe 2 — das Iterieren bleibt
schnell (§31).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Protocol, cast

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import (
    CANCEL,
    CHANGE_SELECTION,
    CORRECT_INPUT,
    PROGRAMMING_ERRORS,
    SHOW_LOCATION,
    SHOW_LOCATIONS,
    BooleanFailedError,
    GeometryError,
)
from app.core.geom import kernel_process
from app.core.geom.attributes import (
    DEFAULT_CUT_SLOT,
    carry_refined_units,
    in_source_layout,
    transfer,
)
from app.core.geom.mesh import (
    MeshData,
    enclosed_volume,
    face_components,
    signed_volume,
    without_faces,
)
from app.core.geom.repair import (
    CROSSING_PARTS_MAX,
    merge_vertices,
    nested_part_families,
    parts_that_cross,
    remove_degenerate_faces,
    resolve_self_intersections,
    self_crossing_shells,
)
from app.core.log import get_logger
from app.core.types import (
    BRepBody,
    CancelToken,
    Finding,
    ObjectId,
    Profile,
    Quality,
    SolverInfo,
    SolverStage,
    Vec3,
)
from app.core.units import EPS_GEOM, is_close, weld_digits, weld_tolerance
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

BooleanKind = Literal["union", "difference", "intersection"]


class HasVolume(Protocol):
    """Was :func:`without_effect` von einem Körper braucht — und mehr nicht.

    ``MeshData`` und der exakte ``Solid`` haben nichts gemeinsam außer diesem
    Wert, und für die Frage „hat sich etwas geändert" genügt er beiden.
    """

    @property
    def volume(self) -> float: ...


#: Die volle Kette, und die verkürzte für Entwurfsqualität (§31).
FULL_CHAIN: tuple[SolverStage, ...] = ("direct", "welded", "jittered", "voxel")
DRAFT_CHAIN: tuple[SolverStage, ...] = ("direct", "welded")

#: Wie weit Stufe 3 die Eckpunkte bewegt — die Standardabweichung je
#: Koordinate, als Anteil der Modelldiagonale: genug, um ein Zusammenfallen zu
#: brechen, weit unter allem, was ein Drucker auflösen könnte.
JITTER_AMPLITUDE = 1e-4

#: Kantenlänge des Voxelrasters in Stufe 4, relativ zur Modelldiagonale.
VOXEL_PITCH_RELATIVE = 0.004
#: So viele Zellen darf das Raster der Voxelstufe haben — 50 Millionen sind
#: 50 MB als Bool-Feld und ein Marching-Cubes-Lauf von Sekunden; darüber
#: gibt die Stufe auf, statt den Speicher zu reißen (G-13, siehe ``_voxel``).
MAX_VOXEL_CELLS: Final = 50_000_000

#: Wie weit ein abziehendes Werkzeug über die Fläche hinausreichen soll, die es
#: durchschneidet.
#:
#: Zusammenfallende Flächen sind der klassische Weg, eine Boolesche Operation
#: zu brechen (§39) — also reicht das Werkzeug ein Stück darüber hinaus, weit
#: unter dem, was ein Drucker auflöst.
#:
#: **Die Zahl stand an drei Stellen mit zwei Werten**, zuletzt sogar zweimal
#: unter diesem Namen: 0,05 hier, 0,01 in ``geom/prepare.py``, 0,01 als
#: ``OVERLAP`` in ``knowledge/parts/shapes.py``. Damit hing es am Importpfad,
#: welche Zugabe eine Operation bekam.
#:
#: **Gemessen am 27.08.2026, und die Messung hat die Frage verschoben.** Nicht
#: „welcher Wert ist richtig", sondern „wirkt der Wert überhaupt":
#:
#: * Neun koplanare Lagen — Tasche bis zur Unterseite, Aufsatz auf der
#:   Oberseite, Tasche an der Seitenwand, je mit 0,05, 0,01 und **0,0** —
#:   liefen alle über Stufe 1 (``direct``), alle wasserdicht, alle mit exaktem
#:   Volumen. Kein einziger Rückfall.
#: * Eine Gravur von 0,2 mm trug bei 0,05, 0,01, 0,001 und 0,0 dieselben
#:   2,6221 mm³ ab. Die Zugabe liegt außerhalb des Materials: Das Werkzeug wird
#:   um sie länger **und** um sie angehoben.
#:
#: ``manifold3d`` ist feste Abhängigkeit (``constraints.txt``) und rechnet
#: koplanare Flächen robust — der Bruch, gegen den diese Zahl einmal gebaut
#: wurde, gehört zu einem Kern, den es hier nicht mehr gibt. Sie bleibt
#: trotzdem: Die Rückfallkette hat Stufen unterhalb von ``manifold3d``, und
#: eine Zugabe, die nachweislich nichts kostet, ist billiger als die Frage, ob
#: eine davon sie doch braucht.
#:
#: **„Robust" gilt für exakt koplanare float64-Geometrie** (gemessen
#: 13.09.2026, RM-166). Kommt der Körper aus einer STL, liegt seine Fläche in
#: float32, und ein Werkzeug, dessen Flanke exakt in dieser Fläche steht, ist
#: nur *fast* koplanar: Die Differenz ließ an den Bohrungsrändern einer
#: gefasten Platte Haut ohne Dicke stehen — per Index dicht, nach der nächsten
#: STL-Runde nicht mehr. ``edges.rounding_tool`` rückt die Flanken abziehender
#: Keile deshalb um diese Zugabe in die Luft; ``EPS_GEOM`` war dafür zu wenig.
#:
#: **Der kleinere Wert gewinnt, weil er gebunden ist.** In
#: ``knowledge/parts/ops.py`` ist dieselbe Zahl die Schwelle, an der ein
#: Baustein als „baut nach oben" statt „trägt ab" gilt — sie muss den
#: Einsinkbetrag knapp überdecken, den derselbe Wert erzeugt. 0,05 hätte diese
#: Entscheidung verschoben; 0,01 ist dort seit je in Gebrauch und anderswo
#: nachweislich gleichwertig.
BOOLEAN_OVERLAP = 0.01


@dataclass(slots=True)
class BooleanOutcome:
    """Das Ergebnis, plus wie es erreicht wurde."""

    mesh: MeshData
    solver: SolverInfo
    findings: list[Finding] = field(default_factory=list)


def boolean(
    kind: BooleanKind,
    meshes: list[MeshData],
    *,
    quality: Quality = "fine",
    seed: int | None = None,
    stages: tuple[SolverStage, ...] | None = None,
    cut_slot: int = DEFAULT_CUT_SLOT,
    allow_empty: bool = False,
    cancelled: CancelToken | None = None,
    merge_face_contacts: bool = False,
    object_ids: Sequence[ObjectId | None] | None = None,
) -> BooleanOutcome:
    """Führt eine Boolesche Operation aus und fällt Stufe um Stufe zurück, bis
    eine hält.

    ``cut_slot`` ist, was eine frisch geschnittene Fläche bekommt (§20): per
    Vorgabe der Slot des Körpers, der geschnitten wird — ein Loch durch ein
    zweifarbiges Teil streicht seine Wand so nicht in der Farbe, die das
    Werkzeug zufällig hatte.

    ``allow_empty`` sagt: Nichts ist eine Antwort. Bei einer Differenz, die
    jemand wollte, heißt ein leeres Ergebnis, dass der Kern aufgegeben hat und
    die nächste Stufe dran ist — dafür ist die Kette da. Bei einer
    Verschneidung kann es heißen, dass die zwei Körper sich schlicht nicht
    treffen — und drei weitere Stufen laufen zu lassen, um dasselbe noch
    einmal zu hören, macht aus einer Tatsache eine Ausnahme, die der Aufrufer
    auseinandernehmen muss.

    Lassen sich Teile eines Eingangs nicht vereinigen, rechnet die Kette mit
    den Teilen, wie sie sind, und sagt es (``boolean.parts_not_united``) — wie
    vor RM-253. **Angehalten wird nur, wo ein Werkzeug eine Schale trifft, die
    sich belegt selbst kreuzt** (RM-382, Entscheidung Robert: „Das Beste für
    Kunden, damit sie bearbeiten können."): Dort rechnet der Kern an
    unveränderten, einander durchdringenden Teilen nichts Verlässliches — am
    Laptop-Ständer blieb in einer versetzten Bohrung Material stehen (RM-253).
    Eine Bohrung abseits dieser Schale rechnet dagegen wie an jedem Körper;
    seit ``eab5f4f47`` hielt sie an jeder Stelle an, auch wo sie nichts traf.

    ``object_ids`` bindet jeden Eingang an das Szenenobjekt, aus dem er stammt.
    Interne Werkzeuge tragen ``None`` und gehen unverändert an den Solver, denn
    ihre Teile dürfen sich konstruktionsbedingt überschneiden. Szenenkörper mit
    Kennung werden vorab geprüft, auch als Werkzeug einer Differenz; ein Halt
    nennt den Körper mit der kaputten Schale.
    """
    if len(meshes) < 2:
        raise ValueError("a boolean operation needs at least two bodies")
    if object_ids is not None and len(object_ids) != len(meshes):
        raise ValueError("object_ids must match meshes")

    chain = stages if stages is not None else FULL_CHAIN
    given = meshes
    meshes, united, stuck = _parts_united_first(
        kind,
        meshes,
        cancelled,
        merge_face_contacts=merge_face_contacts,
        object_ids=object_ids,
    )
    for index, joined in stuck:
        if not joined.crossing:
            continue
        others = [mesh for number, mesh in enumerate(meshes) if number != index]
        met = _meets_the_shells(others, meshes[index], joined.crossing, cancelled)
        if met is None:
            continue
        # Gebunden an den Körper mit der kaputten Schale; ohne Kennung gibt es
        # keine Karte, die *Stellen zeigen* öffnen könnte. Der Ort ist der, an
        # dem das Werkzeug die Schale trifft. Ist das Werkzeug ein Szenenkörper,
        # wählt man andere Objekte, sonst eine andere Stelle im Schritt.
        owner = object_ids[index] if object_ids is not None else None
        internal = object_ids is None or all(
            object_ids[number] is None for number in range(len(meshes)) if number != index
        )
        raise GeometryError(
            detail=CROSSING_SHELL_IN_THE_WAY,
            suggestions=(
                *((SHOW_LOCATIONS,) if owner is not None else ()),
                CORRECT_INPUT if internal else CHANGE_SELECTION,
                CANCEL,
            ),
            object_id=owner,
            values={"location": met},
        )
    attempted: list[SolverStage] = []
    emptied = False
    """Ob eine Stufe sauber gerechnet hat und dabei nichts übrig blieb.

    Das ist kein Scheitern des Verfahrens, sondern eine Aussage über die
    Eingabe: eine Bohrung mit 200 mm Durchmesser in einer 80er Platte frisst
    sie ganz. Ohne diese Unterscheidung liefen alle vier Stufen durch und der
    Nutzer las am Ende „Auch die letzte Rückfallstufe hat kein brauchbares
    Ergebnis geliefert" — die Sprache des Rechenkerns für etwas, das aus den
    Maßen folgt.
    """

    for stage in chain:
        # **Nach der Güte gefragt wird erst hinter den verlustfreien Stufen**
        # (RM-494): Beide Ketten beginnen mit :data:`DRAFT_CHAIN`. Hält eine
        # davon, rechnet der Entwurf dasselbe wie die feine Rechnung, und die
        # Auswertung weiß, dass der Export nicht nachrechnen muss.
        if stages is None and stage not in DRAFT_CHAIN and quality != "fine":
            break
        # Zwischen den Stufen, nicht mittendrin: eine Stufe ist ein nativer
        # Aufruf und kooperativ nicht zu unterbrechen — aber vier Versuche
        # plus Voxelisierung an einem großen Netz waren als Ganzes
        # unabbrechbar, und §15.6 verlangt „jederzeit abbrechbar".
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        attempted.append(stage)
        try:
            result = _run_stage(kind, meshes, stage, seed, cancelled)
        except kernel_process.NOT_A_KERNEL_FAILURE:
            # Abgebrochen, oder der Hilfsprozess des Kerns ist gestorben — kein
            # Kern, der aufgegeben hat. Die nächste Stufe bekäme dieselbe Last
            # im nächsten Hilfsprozess und zuletzt die Voxelstufe im Prozess
            # der Anwendung (Durchsicht RM-212, B3).
            raise
        except PROGRAMMING_ERRORS:
            # Die Stufen rufen mit eigenen Argumenten — ``voxelized(pitch=...)``,
            # ``matrix_to_marching_cubes(matrix=..., pitch=...)``. Fiele ein
            # falscher Aufruf in den Handler darunter, sähe er aus wie vier
            # Kerne, die nacheinander aufgeben, und der Nutzer läse am Ende, es
            # liege an seiner Geometrie.
            raise
        except Exception as problem:  # Kerne scheitern auf kerneigene Arten
            _log.warning("boolean stage %s failed: %s", stage, problem)
            continue
        if result is None or not _plausible(result, allow_empty):
            if result is not None and result.triangle_count == 0:
                emptied = True
            _log.warning("boolean stage %s produced nothing usable", stage)
            continue
        # **Was der Schnitt nicht berührt hat, behält die Darstellung seines
        # Eingangs** (RM-261): Eckenfolge und Eckenreihenfolge. Sonst liest die
        # Erkennung nach der ersten Booleschen jeden Fleck mit verschobenen
        # letzten Stellen — und kippt an Schwellen fern vom Schritt.
        result = in_source_layout(result, given)
        # Der Ursprung je Dreieck vor *Kanten verfeinern* hängt an den
        # Dreiecken, die der Schnitt nicht berührt hat (R1) — gesucht an den
        # Eingängen, wie sie hereinkamen, vor jeder Vereinigung ihrer Teile.
        carry_refined_units(result, given)
        return BooleanOutcome(
            # Nichts hat keine Flächen zum Färben, und die Übertragung suchte
            # die nächste Oberfläche eines Körpers, der keine hat.
            mesh=result
            if result.triangle_count == 0
            else _keep_slots(result, meshes, kind, stage, cut_slot),
            solver=SolverInfo(
                strategy=stage,
                attempted=tuple(attempted),
                seed=seed if stage == "jittered" else None,
            ),
            findings=[*united, *_findings_for(stage, kind, meshes, result)],
        )

    if emptied and "voxel" not in attempted:
        # **„Nichts übrig" ist keine Aussage über die Maße, solange die Kette
        # noch Stufen hätte.** Genau das stand hier — „Kein Rückfall hilft
        # gegen Maße" —, und es ist widerlegt: Am Mast des Piratenschiffs
        # (``obj_1_Cylinder.stl``, Ø 5 auf 115 mm) liefern *direkt* und
        # *verschweißt* für ``resize_feature`` nichts, und **die dritte Stufe
        # löst es** (Befund ``boolean.jittered``, gemessen 04.09.2026).
        #
        # Im Fenster läuft die kurze Kette (:data:`DRAFT_CHAIN`), beim Export
        # die volle (§17.2, §31). Derselbe Kunde bekam damit für dieselbe
        # Handlung am selben Körper einmal ein Ergebnis und einmal „Prüfen Sie
        # Maß und Lage" — und Maß und Lage waren in Ordnung.
        #
        # Der Rat gehört deshalb dem, was noch offen ist. Titel und
        # Vorschläge setzt hier **niemand**: Die Ausnahme wählt sie selbst
        # danach, ob die Voxelstufe dran war (``errors.BooleanFailedError``),
        # und eine zweite Entscheidung derselben Frage liefe auseinander.
        raise BooleanFailedError(
            detail=_(
                "In der schnellen Vorschau blieb von dem Körper nichts übrig. "
                "Von {stages} Rechenstufen sind {tried} gelaufen — ob es an den "
                "Maßen liegt oder an der schnellen Rechnung, sagt erst die "
                "vollständige.",
                stages=len(FULL_CHAIN),
                tried=len(attempted),
            ),
            attempted=tuple(attempted),
            seed=seed,
        )
    if emptied:
        # Hier ist die Kette wirklich zu Ende, und dann sagt „nichts übrig"
        # etwas über die Maße. Die Handlung dazu ist eine andere als beim
        # Kernversagen: nicht reparieren, sondern nachrechnen.
        raise BooleanFailedError(
            # **Eigener Titel, denn hier ist nichts gescheitert.** Der Vorgabetitel
            # der Klasse heißt „Die boolesche Operation ist auf allen Stufen
            # gescheitert." — und stand damit über einem Detailsatz, der das
            # Gegenteil sagt: Die Rechnung ist sauber durchgelaufen, das Ergebnis
            # ist leer, weil das Werkzeug den Körper deckt. Wer nur den Titel
            # liest, sucht einen Netzfehler; die Antwort liegt bei den Maßen, und
            # genau dorthin schicken die Vorschläge.
            title=NOTHING_LEFT_TITLE,
            detail=NOTHING_LEFT_DETAIL,
            suggestions=(CORRECT_INPUT, CANCEL),
            attempted=tuple(attempted),
            seed=seed,
        )
    raise BooleanFailedError(
        detail=_(
            "Häufig ist das Modell an einer Stelle offen — dann hilft Reparieren. Gröber "
            "gerechnet gelingt es meist, mit gerundeten Maßen."
        ),
        attempted=tuple(attempted),
        seed=seed,
    )


#: Wo :func:`_united_parts` seine Antwort im Cache des Netzes ablegt.
_UNITED_KEY: Final = "solidon_parts_united"
_UNITED_FACE_CONTACT_KEY: Final = "solidon_parts_united_with_face_contacts"

#: Der Halt, wenn ein Werkzeug eine Schale trifft, die sich selbst kreuzt
#: (RM-382). Grund und Ausweg in einem Satz; *Reparieren* steht nicht dabei,
#: denn die Reparatur löst eine Eigenkreuzung nicht auf (``repair.self_crossing``)
#: — der Knopf endete am selben Halt.
CROSSING_SHELL_IN_THE_WAY: Final = _(
    "Der Schritt trifft ein Teil, dessen Oberfläche sich selbst kreuzt. Dort lässt er sich "
    "nicht verlässlich rechnen. Setzen Sie ihn an eine andere Stelle oder reparieren Sie das "
    "Teil in einem Netzprogramm."
)


@dataclass(frozen=True, slots=True)
class _Joined:
    """Was die Vorvereinigung an einem Eingang gefunden hat."""

    body: MeshData | None
    """Der Eingang mit vereinigten Teilen — ``None``, wenn es nicht ging."""
    place: Vec3
    """Wo sich Teile treffen oder berühren."""
    crossing: tuple[np.ndarray, ...] = ()
    """Ging es nicht, die Schalen, die sich belegt selbst kreuzen — je Schale ihre Dreiecke."""


def _parts_united_first(
    kind: BooleanKind,
    meshes: list[MeshData],
    cancelled: CancelToken | None,
    *,
    merge_face_contacts: bool = False,
    object_ids: Sequence[ObjectId | None] | None = None,
) -> tuple[list[MeshData], list[Finding], list[tuple[int, _Joined]]]:
    """Teile eines Eingangs vorab vereinigen — und es sagen.

    **An Schalen, die einander durchdringen, rechnet der Kern nichts
    Verlässliches** (RM-221). Beim Schließen einer alten Höhlung gilt das
    zusätzlich für flächige Berührung (RM-319). Am Piratenschiff
    (``obj_11_Cylinder_B.stl``)
    verschmolz *Fläche versetzen* +1 mm die zwei Zylinder still — Teile 2 → 1,
    +10,01 statt +19,63 mm³, kein Befund. An zwei ineinandergeschobenen
    Würfeln blieb dieselbe Vereinigung zweiteilig, und eine Bohrung machte aus
    zwei Teilen drei oder vier (gemessen 25.09.2026). Gedruckt werden solche
    Teile ohnehin als eines: Der Slicer vereinigt sie. Die Kette vereinigt sie
    deshalb vorher auf demselben Weg wie *Überschneidungen auflösen*
    (:func:`~app.core.geom.repair.resolve_self_intersections`: jede Schale ein
    Operand, nachgeprüft) — danach ist das Volumen das des Drucks, der
    gemeinsame Raum zählt einmal.

    Gilt nur, wo die Vorfrage es belegt
    (:func:`~app.core.geom.repair.parts_that_cross`); wenn ``merge_face_contacts``
    gesetzt ist, zählt außerdem positive koplanare Flächenberührung. Kanten-
    und Eckkontakt allein reichen nicht. Sagt die Vorfrage nichts, bleibt der
    Eingang, wie er war. Die Antwort liegt je Vorprüfmodus getrennt im Cache
    des Netzes. Ein Befund je Operation, auch wenn mehrere Eingänge es
    brauchten.

    **Ein Teil ganz im Material eines anderen steckt ebenso darin** (Durchsicht
    0.5.1, BOHRUNG-02): Es schneidet keine Wand, und die Vorfrage sah es nicht.
    Eine Bohrung durch einen Würfel mit einem zweiten ganz innen ließ
    8 154 statt 7 434 mm³ stehen — das innere Teil zählte weiter doppelt.
    Vereinigt wird es wie gedruckt (:func:`_nested_united`).

    **Was sich nicht vereinigen lässt, geht unverändert weiter und wird
    gesagt** (``boolean.parts_not_united``); zurück kommt es außerdem als
    dritter Wert, damit :func:`boolean` fragen kann, ob ein Werkzeug eine
    Schale trifft, die sich selbst kreuzt (RM-382). Am Laptop-Ständer
    (21 Teile, eines kreuzt sich 1 121-mal selbst) lehnt das Auflösen ab.

    **Gefragt wird jeder Szenenkörper** — der Körper, an dem gearbeitet wird,
    bei der Vereinigung jeder Eingang, und mit ``object_ids`` auch ein
    Szenenkörper als Werkzeug einer Differenz oder Schnittmenge: Er bringt
    seine Teile so ungeprüft in den Kern wie der Körper selbst (Review RM-253,
    Fund 5). Interne Werkzeuge (``None``) baut Solidon selbst: Das Gitter von
    *Gitter füllen* besteht aus Streben, die sich an jedem Knoten
    überschneiden, und über ihm stand sonst ein Satz über Teile, die der Kunde
    nie hatte.
    """
    prepared: list[MeshData] = []
    place: Vec3 | None = None
    stuck: list[tuple[int, _Joined]] = []
    for index, mesh in enumerate(meshes):
        scene_body = object_ids[index] is not None if object_ids is not None else None
        if index and (scene_body is False or (scene_body is None and kind != "union")):
            prepared.append(mesh)
            continue
        united = _united_parts(mesh, cancelled, merge_face_contacts=merge_face_contacts)
        if united is None:
            prepared.append(mesh)
            continue
        if united.body is None:
            prepared.append(mesh)
            stuck.append((index, united))
            continue
        prepared.append(united.body)
        place = united.place if place is None else place
    findings: list[Finding] = []
    if place is not None:
        findings.append(
            Finding(
                code="boolean.parts_united",
                severity="info",
                message=_("Teile des Modells wurden vor diesem Schritt zu einem Körper vereinigt."),
                location=place,
                # Der Ort, an dem die Teile verbunden wurden, reist mit (Regel 17).
                suggestions=(SHOW_LOCATION,),
            )
        )
    if stuck:
        index, first = stuck[0]
        crossing = any(joined.crossing for _number, joined in stuck)
        findings.append(
            Finding(
                code="boolean.parts_not_united",
                severity="warning",
                message=(
                    _(
                        "Teile des Modells stecken ineinander und ließen sich nicht vereinigen, "
                        "weil sich eine Oberfläche selbst kreuzt. Wo der Schritt durch beide "
                        "Teile geht, kann Material stehen bleiben."
                    )
                    if crossing
                    else _(
                        "Teile des Modells ließen sich vor diesem Schritt nicht vereinigen. "
                        "Der Schritt kann Material stehen lassen."
                    )
                ),
                object_id=object_ids[index] if object_ids is not None else None,
                location=first.place,
                # *Stellen zeigen* öffnet die Netzfehlerkarte, und die färbt die
                # Eigenkreuzung; die Stelle des Kontakts fliegt *Stelle zeigen* an.
                suggestions=(SHOW_LOCATIONS, SHOW_LOCATION) if crossing else (SHOW_LOCATION,),
            )
        )
    return (prepared if place is not None else meshes), findings, stuck


def _united_parts(
    mesh: MeshData, cancelled: CancelToken | None, *, merge_face_contacts: bool = False
) -> _Joined | None:
    """Der Eingang mit vereinigten Teilen und ein Ort des Kontakts — oder ``None``.

    Treffen oder berühren sich Teile, lassen sich aber nicht vereinigen, kommt
    statt des Körpers ``None`` mit dem Ort zurück und, wo es der Grund ist, mit
    den Schalen, die sich selbst kreuzen (:func:`_parts_united_first` sagt es
    dann). Einmal je Netz: Die Antwort liegt im Cache des Netzes und verfällt
    mit seiner Geometrie. Die Vorschau fragt denselben Körper bei jeder
    getippten Zahl, und ein Körper aus einem Stück kostet nur die gemerkte
    Teilezahl.
    """
    if mesh.triangle_count == 0 or mesh.component_count < 2:
        return None
    cache = getattr(mesh.raw, "_cache", None)
    cache_key = _UNITED_FACE_CONTACT_KEY if merge_face_contacts else _UNITED_KEY
    if cache is not None and cache_key in cache:
        return cast("_Joined | None", cache[cache_key])
    answer: _Joined | None = None
    place = parts_that_cross(
        mesh.raw,
        cancelled=cancelled,
        max_pairs=None,
        include_face_contacts=merge_face_contacts,
        require_complete=True,
    )
    if place is not None:
        resolved, done = resolve_self_intersections(mesh, cancelled)
        answer = (
            _Joined(resolved, place)
            if done
            else _Joined(None, place, tuple(self_crossing_shells(mesh)))
        )
    elif mesh.component_count <= CROSSING_PARTS_MAX:
        nested = _nested_united(mesh, cancelled)
        answer = _Joined(*nested) if nested is not None else None
    if cache is not None:
        cache[cache_key] = answer
    return answer


def _meets_the_shells(
    tools: Sequence[MeshData],
    body: MeshData,
    shells: Sequence[np.ndarray],
    cancelled: CancelToken | None,
) -> Vec3 | None:
    """Wo eines der Werkzeuge eine der Schalen trifft — ``None``, wenn keines (RM-382).

    Treffen heißt: Eine Werkzeugfläche schneidet eine Schalenfläche oder liegt
    flächig auf ihr (:func:`~app.core.geom.intersections.crossing_pairs` mit
    Flächenkontakt), gesucht über zwei Hüllquaderbäume — oder das Werkzeug
    liegt ganz in der Schale; das sagt ein Strahl von einer Ecke je
    Werkzeugteil, und wo der Strahl nichts entscheidet, gilt es als getroffen.
    Eine Schale, die ganz im Werkzeug liegt, trifft es nicht: Ihre Dreiecke
    fallen dort als Ganzes heraus oder bleiben als Ganzes stehen. Der Ort ist
    die Mitte des ersten getroffenen Paars, sonst die Ecke des Werkzeugs.
    """
    from app.core.geom.box_pairs import BoxTree, box_pairs_between
    from app.core.geom.intersections import crossing_pairs
    from app.core.perceive.features import _point_inside_shell, _triangle_bounds

    corners = np.asarray(body.raw.triangles, dtype=np.float64)
    chosen = np.concatenate(shells)
    own = corners[chosen]
    own_faces = np.asarray(body.raw.faces, dtype=np.int64)[chosen]
    shell_tree = BoxTree(np.arange(len(chosen)), own.min(axis=1), own.max(axis=1))
    # Fremde Eckennummern dürfen nie wie eigene aussehen: Gleiche Nummern sind
    # für die Schnittprüfung eine doppelte Fläche, kein Kontakt.
    offset = len(body.raw.vertices)
    walls = [(corners[faces], _triangle_bounds(corners[faces])) for faces in shells]
    for tool in tools:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        triangles = np.asarray(tool.raw.triangles, dtype=np.float64)
        if not len(triangles):
            continue
        faces = np.asarray(tool.raw.faces, dtype=np.int64) + offset
        tool_tree = BoxTree(np.arange(len(triangles)), triangles.min(axis=1), triangles.max(axis=1))
        for first, second in box_pairs_between(tool_tree, shell_tree, cancelled):
            hit = np.flatnonzero(
                crossing_pairs(triangles[first], own[second], faces[first], own_faces[second])
            )
            if len(hit):
                index = int(hit[0])
                middle = (
                    triangles[first[index]].mean(axis=0) + own[second[index]].mean(axis=0)
                ) / 2.0
                return (float(middle[0]), float(middle[1]), float(middle[2]))
        for piece in face_components(tool.raw):
            point = triangles[int(piece[0]), 0]
            for wall, bounds in walls:
                if _point_inside_shell(point, wall, bounds) is not False:
                    return (float(point[0]), float(point[1]), float(point[2]))
    return None


def _nested_united(mesh: MeshData, cancelled: CancelToken | None) -> tuple[MeshData, Vec3] | None:
    """Der Eingang ohne die Teile, die ganz im Material eines anderen liegen —
    wie gedruckt, wo sie ohnehin voll sind — und ihr Ort; ``None`` ohne solche.

    Ob sie wirklich ganz drin liegen, sagt nicht der eine Strahl der Vorfrage
    (:func:`~app.core.geom.repair.nested_part_families`), sondern die
    Vereinigung selbst: Bleibt ihr Volumen das des Rests, ist die Familie im
    Material, und der Rest ist das Ergebnis — mit seinen eigenen Dreiecken,
    Slots und Farben. Ragt eine hinaus, gilt die Vereinigung; scheitert sie,
    bleibt der Eingang.
    """
    families = nested_part_families(mesh.raw)
    if not families:
        return None
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    inner = np.zeros(len(mesh.raw.faces), dtype=bool)
    for family in families:
        inner[family] = True
    slots = np.asarray(mesh.slots, dtype=np.int64) if len(mesh.slots) == len(inner) else None

    def part(keep: np.ndarray) -> MeshData:
        body = without_faces(mesh.raw, keep)
        return MeshData.of(body, tuple(slots[keep].tolist()) if slots is not None else ())

    rest = part(~inner)
    pieces = []
    for family in families:
        keep = np.zeros(len(inner), dtype=bool)
        keep[family] = True
        pieces.append(part(keep))
    corners = np.asarray(mesh.raw.triangles, dtype=np.float64)[families[0]].reshape(-1, 3)
    centre = (corners.min(axis=0) + corners.max(axis=0)) / 2.0
    place: Vec3 = (float(centre[0]), float(centre[1]), float(centre[2]))
    try:
        united = boolean("union", [rest, *pieces], stages=("direct",), cancelled=cancelled).mesh
    except PROGRAMMING_ERRORS:
        raise
    except BooleanFailedError:
        return None
    before = signed_volume(rest.raw)
    after = signed_volume(united.raw)
    if abs(after - before) <= _NESTED_SAME * max(abs(before), 1.0):
        return rest, place
    return united, place


#: Wie genau das Volumen der Vereinigung das des Rests treffen muss, damit die
#: eingeschlossenen Teile als ganz im Material gelten (:func:`_nested_united`) —
#: ein Anteil, weit über der Rechengenauigkeit des Kerns und weit unter dem
#: kleinsten Teil, das hinausragen könnte.
_NESTED_SAME: Final = 1e-7


def _keep_slots(
    result: MeshData,
    sources: list[MeshData],
    kind: BooleanKind,
    stage: SolverStage,
    cut_slot: int,
) -> MeshData:
    """§20: die Slot-Zuweisung überlebt die Operation.

    Die Zuordnung folgt der nächsten erhaltenen Eingangsfläche. Eine gleiche
    Dreieckszahl ist kein Beleg für gleiche Flächen oder ihre Reihenfolge.

    Nur die Körper, die noch *im* Ergebnis sind, geben ihre Farbe weiter. Bei
    einer Differenz ist das Werkzeug fort, und die Bohrungswand, die es
    hinterließ, ist eine neue Oberfläche, kein Stück des Bohrers — sonst käme
    ein Loch durch ein rotes Teil in der Farbe heraus, die das Werkzeug
    zufällig hatte.
    """
    # Gleiche Dreieckszahl beweist keine Flächenidentität: Schon eine
    # halbierte Box hat wieder zwölf Dreiecke in anderer Reihenfolge.
    tolerance = None
    if stage == "voxel":
        # Die Treppe des Rasters ist überall einen halben Voxel tief; enger
        # gemessen verlöre der Körper seine Farbe an die eigene Vernetzung
        # statt an die Operation.
        diagonal = max(mesh.bounds.diagonal for mesh in sources)
        tolerance = max(diagonal * VOXEL_PITCH_RELATIVE, 0.05) * 1.5
    carriers = sources[:1] if kind == "difference" else sources
    return transfer(result, carriers, cut_slot=cut_slot, tolerance=tolerance)


def _run_stage(
    kind: BooleanKind,
    meshes: list[MeshData],
    stage: SolverStage,
    seed: int | None,
    cancelled: CancelToken | None = None,
) -> MeshData | None:
    if stage == "direct":
        return _kernel(kind, [mesh.raw for mesh in meshes], meshes[0], cancelled)
    if stage == "welded":
        cleaned = [_welded_input(mesh) for mesh in meshes]
        return _kernel(kind, [mesh.raw for mesh in cleaned], meshes[0], cancelled)
    if stage == "jittered":
        disturbed = [_jitter(mesh, seed, index) for index, mesh in enumerate(meshes)]
        return _kernel(kind, [mesh.raw for mesh in disturbed], meshes[0], cancelled)
    return _voxel(kind, meshes)


def _welded_input(mesh: MeshData) -> MeshData:
    """Stufe 2 an einem Eingang: verschweißt und entnadelt — ohne ein dichtes
    Netz dabei aufzureißen.

    Dieselbe Zusicherung wie beim Import (``ingest.degenerate_kept``) und in
    ``repair()``: In einem geschlossenen Netz ist jedes Dreieck an zwei Kanten
    der einzige Nachbar; wer eines streicht, reißt genau dort ein Loch — auch
    wenn es keine Fläche hat. Die Stufe hatte diese Zusicherung nicht, und der
    Fall kam mit RM-166 (14.09.2026): Ein Fasenwerkzeug aus zwölf Keilstücken
    um einen Bohrkreis, deren Flanken um ``BOOLEAN_OVERLAP`` überstehen, trägt
    an den Stoßstellen Nadeln — roh dicht, nach dem Entnadeln nicht mehr, und
    ``_kernel`` wies das Werkzeug als „nicht positiv geschlossen" ab. An einer
    nur verschweißten Platte mit dünnen Knoten (``plate_countersunk.stl``) war
    das die Stufe, die trug, und die Kette lief bis in die Voxel.
    """
    welded, _removed = merge_vertices(mesh)
    if mesh.is_watertight and not welded.is_watertight:
        welded = mesh
    cleaned, _dropped = remove_degenerate_faces(welded)
    if welded.is_watertight and not cleaned.is_watertight:
        return welded
    return cleaned


def _kernel(
    kind: BooleanKind,
    bodies: list[trimesh.Trimesh],
    like: MeshData,
    cancelled: CancelToken | None = None,
) -> MeshData | None:
    """Rechnet in Float64 und verwirft belegte Kontaktreste auch neben echten Volumenkörpern.

    Die Rechnung selbst ist ``kernel_jobs.boolean`` — an großen Körpern im
    Hilfsprozess (``kernel_process``): Aufbau und Verknüpfung halten den
    Interpreter sonst an, am Spiderman (885 570 Dreiecke) 636 ms für den
    Aufbau und 225 ms für eine Bohrung (``gil_kern.py``, 27.09.2026).
    Kontaktreste innerhalb der Float64-Rechengrenze entscheidet
    ``kernel_jobs.native_contact``.
    """
    if not all(
        body.is_watertight and body.is_winding_consistent and signed_volume(body) > 0.0
        for body in bodies
    ):
        raise ValueError("Not all meshes are positive closed volumes")
    arrays: dict[str, np.ndarray] = {}
    for index, body in enumerate(bodies):
        arrays[f"vertices{index}"] = np.asarray(body.vertices)
        arrays[f"faces{index}"] = np.asarray(body.faces)
    arrays_out, reported = kernel_process.run(
        "boolean",
        arrays,
        {"bodies": len(bodies), "kind": kind},
        weight=sum(len(body.faces) for body in bodies),
        cancelled=cancelled,
    )
    if reported["outcome"] == "failed":
        return None
    if reported["outcome"] == "empty":
        return like.replacing(trimesh.Trimesh())
    # Die Schalen bleiben orientiert nebeneinander: Eine native Vereinigung
    # würde negative Innenschalen als eigenständige Körper behandeln und füllen.
    built = trimesh.Trimesh(
        # Die Ausgabe besitzt ihre Puffer: Nachfolgende Netzoperationen
        # dürfen nicht am schreibgeschützten Speicher des Kerns hängen.
        vertices=arrays_out["vertices"],
        faces=arrays_out["faces"],
        process=False,
    )
    return like.replacing(_tidied(built))


def _tidied(body: trimesh.Trimesh) -> trimesh.Trimesh:
    """Die Kernausgabe so verschweißt, wie jeder Slicer sie verschweißen wird.

    ``manifold3d`` liefert ein Netz, das **per Index** dicht ist — und an
    Nähten zwischen fast koplanaren Flächen Eckpunktpaare unter der
    Schweißtoleranz und Sliver-Dreiecke stehen lässt. Gemessen am 13.09.2026
    (RM-166): Nach *Bohrung ändern* und *Merkmal verschieben* an einer
    eingelesenen STL blieben auf dem alten Bohrkreis zehn solcher Paare und
    25 Sliver. Per Index dicht, in Solidon dicht — und nach der ersten
    STL-Runde in float32 nicht mehr: Solidons eigener Import derselben Datei
    meldete „Das Modell ist nicht geschlossen", und jeder Slicer verschweißt
    genauso.

    Verschweißt wird mit derselben Toleranz wie beim Import
    (``weld_tolerance`` der Diagonale); Dreiecke, die dabei einen Eckpunkt
    doppelt bekommen, fallen weg, unreferenzierte Ecken danach. **Übernommen
    wird das nur, wenn es die Zusicherung von ``repair()`` hält**: Das Netz
    bleibt dicht und das Volumen ändert sich nicht. Nahe Punkte können zu zwei
    getrennten Schalen gehören, und sie zusammenzulegen dürfte deren Kanten
    nicht aufreißen — dann bleibt die rohe Ausgabe. Was hier **nicht**
    passiert: Nadeln mit drei verschiedenen Ecken streichen — das reißt
    Löcher, und ``manifold.simplify`` vernetzt ebene Flächen neu und ließ
    gemessen 25 mm² Haut stehen.

    **„Unverändert" heißt ``EPS_GEOM`` absolut** — dieselbe Schwelle wie
    ``repair.unify_normals``. Die weitere Schranke „Oberfläche mal Toleranz"
    war hergeleitet und trotzdem falsch: Sie ist eine Obergrenze dessen, was
    ein Weld bewegen *kann*, keine Zusicherung dessen, was er bewegen *darf*.
    Gemessen am 14.09.2026: Sie ließ eine dünne Verschneidung von 0,004 mm³
    auf 0,0009 verschweißen und verschob Fasenvolumina an gemischten Ecken um
    2,5·10⁻⁵ — acht Tests, die mit ``EPS_GEOM`` grün sind. Ein Weld, der mehr
    als Rechenrauschen bewegt, hat eine dünne Stelle getroffen, und dann
    bleibt die rohe Ausgabe.
    """
    if len(body.faces) == 0 or not body.is_watertight:
        return body
    candidate = body.copy()
    extents = candidate.extents
    # ``math.hypot`` statt ``np.linalg.norm`` (BLAS): Aus der Diagonale wird
    # die Schweißtoleranz, und die soll auf jeder Maschine dieselbe sein.
    diagonal = math.hypot(float(extents[0]), float(extents[1]), float(extents[2]))
    tolerance = weld_tolerance(diagonal)
    candidate.merge_vertices(digits_vertex=weld_digits(tolerance))
    corners = candidate.faces
    distinct = (
        (corners[:, 0] != corners[:, 1])
        & (corners[:, 1] != corners[:, 2])
        & (corners[:, 0] != corners[:, 2])
    )
    if not np.all(distinct):
        candidate.update_faces(distinct)
    candidate.remove_unreferenced_vertices()
    if len(candidate.vertices) == len(body.vertices) and len(candidate.faces) == len(body.faces):
        return body
    # Das Volumen erst hier, und nur dann (RM-208): Meist verschweißt nichts,
    # und ``trimesh.volume`` kostete an 203 776 Dreiecken 0,29 s für nichts.
    if candidate.is_watertight and is_close(enclosed_volume(candidate), enclosed_volume(body)):
        return candidate
    return body


def _jitter(mesh: MeshData, seed: int | None, index: int) -> MeshData:
    """Stufe 3: die Eckpunkte anstupsen, damit zusammenfallende Flächen
    aufhören zusammenzufallen.

    Der Startwert wird bei der Operation gespeichert, damit derselbe Stups
    wieder passiert (§11.3) — ohne ihn wäre das Ergebnis unreproduzierbar.

    **Gleichverteilt, und zwar mit Absicht** (RM-187). Bis zum 22.09.2026
    kam der Stups aus ``Generator.normal``, und NumPy zieht die Normalverteilung
    über eine Zikkurat, deren Rand und Schwanz ``exp`` und ``log1p`` der
    Plattform rechnen: gleiche Werte nur „bis auf Rundung", also nicht auf
    jeder Maschine dieselben. ``Generator.random`` sind die Rohbits des
    Generators mal 2⁻⁵³ — Ganzzahlarithmetik und eine exakte Multiplikation.
    Die Breite ``√3 · JITTER_AMPLITUDE`` gibt dieselbe Standardabweichung wie
    vorher, ohne die seltenen Ausreißer der Glocke.
    """
    generator = np.random.default_rng((seed or 0) + index)
    body = mesh.raw.copy()
    reach = max(mesh.bounds.diagonal, 1.0) * JITTER_AMPLITUDE * math.sqrt(3.0)
    shape = np.asarray(body.vertices).shape
    body.vertices = body.vertices + (generator.random(size=shape) * 2.0 - 1.0) * reach
    return mesh.replacing(body)


def _voxel(kind: BooleanKind, meshes: list[MeshData]) -> MeshData | None:
    """Stufe 4: die Frage auf einem Raster entscheiden, die Antwort neu
    vernetzen.

    Robust, wo die Topologie es nicht ist, und es kostet Genauigkeit — darum
    sagt der Bericht es jedes Mal, wenn diese Stufe benutzt wurde (§17.3).
    """
    diagonal = max(mesh.bounds.diagonal for mesh in meshes)
    pitch = max(diagonal * VOXEL_PITCH_RELATIVE, 0.05)

    # Das Raster spannt sich über das, was im Ergebnis liegen kann — und das
    # hängt an der Frage: Eine Vereinigung wächst über alle Körper, eine
    # Differenz macht den ersten nur kleiner (das Werkzeug daneben braucht
    # keine Zellen), ein Schnitt liegt im Überlappungsbereich. Bis zum
    # 05.09.2026 spannte es sich immer über alle: Zwei 1-mm-Würfel, einer um
    # (1000, 1000, 1000) verschoben, forderten bei 0,05 mm Rasterweite
    # 20025³ Zellen an — acht Terabyte (Gesamtreview, G-13).
    minima = [np.asarray(mesh.bounds.minimum) for mesh in meshes]
    maxima = [np.asarray(mesh.bounds.maximum) for mesh in meshes]
    if kind == "difference":
        low, high = minima[0] - pitch * 2, maxima[0] + pitch * 2
    elif kind == "intersection":
        low = np.max(minima, axis=0) - pitch * 2
        high = np.min(maxima, axis=0) + pitch * 2
        if np.any(high <= low):
            return meshes[0].replacing(trimesh.Trimesh())
    else:
        low = np.min(minima, axis=0) - pitch * 2
        high = np.max(maxima, axis=0) + pitch * 2
    shape = tuple(int(np.ceil(value)) for value in (high - low) / pitch + 1)

    # Und vor der Allokation ein Budget: Die Rasterweite folgt der größten
    # Einzeldiagonale, die Ausdehnung dem gemeinsamen Hüllquader — der
    # Abstand zweier kleiner Körper kann das Raster beliebig groß machen.
    cells = math.prod(shape)
    if cells > MAX_VOXEL_CELLS:
        _log.warning(
            "voxel stage skipped: %s cells at pitch %.3g exceed the budget of %s",
            f"{cells:,}",
            pitch,
            f"{MAX_VOXEL_CELLS:,}",
        )
        return None

    combined = _rasterise(meshes[0], low, pitch, shape)
    for mesh in meshes[1:]:
        other = _rasterise(mesh, low, pitch, shape)
        if kind == "union":
            combined = combined | other
        elif kind == "difference":
            combined = combined & ~other
        else:
            combined = combined & other

    if not combined.any():
        # Leer, und Marching Cubes hat nichts zum Ablaufen. Wie bei den
        # Kernstufen: der leere Körper geht weiter, _plausible urteilt.
        return meshes[0].replacing(trimesh.Trimesh())
    body = trimesh.voxel.ops.matrix_to_marching_cubes(matrix=combined, pitch=pitch)
    # matrix_to_marching_cubes legt Zelle (0,0,0) an den Ursprung; aufs Raster
    # zurückschieben.
    body.apply_translation(low)
    return meshes[0].replacing(body)


def _rasterise(
    mesh: MeshData, origin: np.ndarray, pitch: float, shape: tuple[int, ...]
) -> np.ndarray:
    """Legt einen Körper auf das gemeinsame Raster."""
    grid = mesh.raw.voxelized(pitch=pitch).fill()
    offset = np.round((np.asarray(grid.transform)[:3, 3] - origin) / pitch).astype(int)
    target = np.zeros(shape, dtype=bool)
    source = np.asarray(grid.matrix, dtype=bool)

    starts = np.maximum(offset, 0)
    ends = np.minimum(offset + np.array(source.shape), np.array(shape))
    if np.any(ends <= starts):
        return target

    target_slice = tuple(slice(int(a), int(b)) for a, b in zip(starts, ends, strict=True))
    source_slice = tuple(
        slice(int(a - o), int(b - o)) for a, b, o in zip(starts, ends, offset, strict=True)
    )
    target[target_slice] = source[source_slice]
    return target


def shared_volume(first: trimesh.Trimesh, second: trimesh.Trimesh) -> float:
    """Wie viel Volumen zwei Körper gemeinsam haben — Berührung zählt als
    keines.

    Die Messung verwendet denselben Float64-Kern wie die Rückfallkette.
    Dessen Leerauskunft trennt Kontakt von dünnem positivem Schnittvolumen,
    ohne aus einer flachen Schale einen Schwerpunkt berechnen zu lassen.
    """
    try:
        shared = _kernel("intersection", [first, second], MeshData.of(first))
    except (*PROGRAMMING_ERRORS, *kernel_process.NOT_A_KERNEL_FAILURE):
        # Ein gestorbener Hilfsprozess ist keine Auskunft „nichts gemeinsam“:
        # Eine Passung hieße sonst still frei (Durchsicht RM-212, B3).
        raise
    except Exception:  # Kerne scheitern auf kerneigene Arten
        return 0.0
    if shared is None or shared.triangle_count == 0:
        return 0.0
    return signed_volume(shared.raw)


def _plausible(mesh: MeshData, allow_empty: bool = False) -> bool:
    """Ein Ergebnis muss ein Körper sein: geschlossen, mit positivem Volumen.
    Ein leerer, ein offener oder ein umgestülpter ist keine Antwort.

    **Der Satz stand hier schon, die Prüfung hielt ihn nicht.** ``abs(volume)``
    nimmt ein umgestülptes Ergebnis an — dessen Volumen ist negativ und sein
    Betrag groß —, und ein Körper mit einem Loch kam ohnehin durch: trimesh
    rechnet auch über eine offene Fläche ein Integral, es bedeutet nur nichts.
    Beides ist genau der Fall, für den es die Rückfallkette gibt; angenommen
    endete er als Ergebnis der ersten Stufe.

    Strenger heißt hier nicht öfter Stufe 4: Gemessen an 213 angenommenen
    Ergebnissen aus fünf Testdateien war keines offen und keines umgestülpt.
    Die Kette verliert dadurch nichts, sie hört nur auf, ein Nicht-Ergebnis für
    eines zu halten.

    Außer der Aufrufer sagt es anders — siehe ``allow_empty`` in
    :func:`boolean`.
    """
    if mesh.triangle_count == 0:
        return allow_empty
    # Ein positives Volumen hat keine Mindestgröße aus einer Längentoleranz.
    # Kontaktreste entfernt bereits ``kernel_jobs.native_contact`` anhand der nativen
    # Rechengrenze; ein echter kleiner Schnitt muss als Messwert erhalten
    # bleiben. Ob er für eine Passung oder Restwand zählt, prüft der Aufrufer.
    return bool(mesh.raw.is_watertight) and signed_volume(mesh.raw) > 0.0


#: Ab welchem Anteil am größten Eingang die Rasterstufe ihre Abweichung beziffert.
VOXEL_DEVIATION_SHARE: Final = 0.005


def _voxel_deviation(kind: BooleanKind, meshes: list[MeshData], result: MeshData) -> float:
    """Wie weit das Volumen neben dem liegt, was die Operation bewirken kann.

    Eine Differenz nimmt vom ersten Körper höchstens die übrigen weg und fügt
    nichts hinzu, eine Vereinigung liegt zwischen dem größten und der Summe,
    ein Schnitt zwischen null und dem kleinsten. Was das Ergebnis darüber oder
    darunter hat, erklärt keine Operation — nur das Raster (RM-246).
    """
    volumes = [signed_volume(mesh.raw) for mesh in meshes]
    if kind == "difference":
        lower, upper = volumes[0] - math.fsum(volumes[1:]), volumes[0]
    elif kind == "union":
        lower, upper = max(volumes), math.fsum(volumes)
    else:
        lower, upper = 0.0, min(volumes)
    reached = signed_volume(result.raw)
    return max(0.0, reached - upper, lower - reached)


def _findings_for(
    stage: SolverStage,
    kind: BooleanKind | None = None,
    meshes: list[MeshData] | None = None,
    result: MeshData | None = None,
) -> list[Finding]:
    if stage == "direct":
        return []
    if stage == "welded":
        return [
            Finding(
                code="boolean.welded",
                severity="info",
                message=_(
                    "Die Operation gelang erst, nachdem doppelte Punkte zusammengeführt waren."
                ),
            )
        ]
    if stage == "jittered":
        return [
            Finding(
                code="boolean.jittered",
                severity="warning",
                message=_(
                    "Die Operation gelang erst, nachdem die Ecken der Körper um einen winzigen "
                    "Betrag verschoben waren, weit unter der Druckgenauigkeit."
                ),
            )
        ]
    # **Und das Raster sagt, wie weit es danebenliegt** (RM-246). Am offenen
    # Laptop-Ständer (``parametric-laptop-riser.stl``) versetzte *Merkmal
    # versetzen* eine Bohrung um 1,5 mm, und das Volumen wuchs um 31 Prozent,
    # von 348 274 auf 457 343 mm³ — der Bericht sagte nur „gerundet". Schon an
    # einem heilen Körper legt das Raster zu (die Lochplatte um elf Prozent),
    # denn jede Zelle, die die Oberfläche berührt, zählt als Material. Eine
    # Absage nähme dem Kunden die Stufe, die ihm überhaupt eine Antwort gibt;
    # er bekommt sie mit der Zahl und dem Weg zum genauen Ergebnis.
    if kind is not None and meshes is not None and result is not None:
        deviation = _voxel_deviation(kind, meshes, result)
        largest = max(abs(signed_volume(mesh.raw)) for mesh in meshes)
        if largest > 0.0 and deviation > VOXEL_DEVIATION_SHARE * largest:
            return [
                Finding(
                    code="boolean.voxel",
                    severity="warning",
                    message=_(
                        "Auf einem Raster gerechnet: Die Maße sind gerundet, und das Volumen "
                        "weicht deutlich vom genauen Ergebnis ab. An einem reparierten Modell "
                        "rechnet der Schritt genau."
                    ),
                    values={
                        "deviation_mm3": deviation,
                        "share_percent": 100.0 * deviation / largest,
                    },
                )
            ]
    return [
        Finding(
            code="boolean.voxel",
            severity="warning",
            message=_("Auf einem Raster gelöst — die Maße sind gerundet."),
        )
    ]


def deepest(infos: Iterable[SolverInfo | None]) -> SolverInfo | None:
    """Von mehreren Läufen der Kette derjenige, der am weitesten
    zurückfallen musste.

    Eine Operation, die drei Boolesche Schnitte fährt, hat drei Antworten und
    darf nur eine melden — und die ehrliche ist die schlechteste: Wer wissen
    will, was seine Zahlen wert sind, interessiert sich für die Stufe, die das
    Ergebnis am stärksten geglättet hat. Eine Voxelstufe irgendwo in der Kette
    macht das ganze Ergebnis zu einem Voxelergebnis.

    ``attempted`` sammelt alles, was unterwegs probiert wurde, in der
    Reihenfolge der Kette — sonst sähe ein Ergebnis aus Stufe 4 so aus, als
    hätte es die drei davor nicht gebraucht.
    """
    known = [entry for entry in infos if entry is not None]
    if not known:
        return None
    worst = max(known, key=lambda entry: FULL_CHAIN.index(entry.strategy))
    attempted = [stage for stage in FULL_CHAIN if any(stage in e.attempted for e in known)]
    return dataclasses.replace(worst, attempted=tuple(attempted))


#: Titel und Grund, wenn eine boolesche Rechnung sauber durchläuft und **nichts
#: übrig lässt** — das Werkzeug deckt den Körper vollständig ab.
#:
#: Geteilt, weil zwei Kerne denselben Fall haben und ihn verschieden werfen
#: müssen: Das Netz kommt über die Rückfallkette hierher und trägt die
#: versuchten Stufen mit, der exakte Kern rechnet einmal und hat keine. Der
#: **Satz** ist derselbe, und zwei wörtliche Kopien wären zwei Stellen, an
#: denen er beim nächsten Nachbessern auseinanderläuft — dieselbe Begründung
#: wie beim Wegtext der Zwillinge (``TWIN_WAYS`` im Register).
#:
#: Der exakte Zwilling hatte den Fall bis zum 27.08.2026 gar nicht: Er gab
#: einen Körper mit null Volumen, null Flächen und ``is_watertight=False``
#: zurück und meldete nichts. Im Objektbaum stand danach ein Objekt mit Namen,
#: das man anklicken, umbenennen und speichern konnte — und das nichts war.
NOTHING_LEFT_TITLE: Final = _("Es bleibt kein Körper übrig.")
NOTHING_LEFT_DETAIL: Final = _(
    "Von dem Körper bleibt nichts übrig — das Werkzeug deckt ihn "
    "vollständig ab. Prüfen Sie Maß und Lage."
)


def fell_apart(
    before: Any,
    after: Any,
    *,
    applies: bool,
    code: str,
    message: Callable[[int], TranslatableText | str],
    values: Mapping[str, str] | None = None,
) -> Finding | None:
    """Ist etwas neben dem Körper liegengeblieben, statt an ihm zu hängen?
    (Regel 17)

    ``message`` bekommt die Zahl der losen Stücke und gibt den Satz zurück —
    als Funktion, weil die Zahl erst hier entsteht und ein Befund nirgends
    nachformatiert wird: Der Kunde las „in {loose} losen Stücken" mit
    geschweiften Klammern. Wer sie im Satz nennen will, füllt sie im
    Übersetzer (``_(…, loose=loose)``); wer nicht, nimmt sie nicht entgegen.

    **Die Teilezahl lügt nicht.** Sie ist binär statt toleranzbehaftet und
    fängt Fälle, die :func:`without_effect` bauartbedingt nicht sieht: Dort
    wird das Volumen gemessen, und bei erhabener Schrift oder aufgesetztem
    Muster ändert es sich ja — nur eben daneben. Die Volumenfrage ist damit
    beantwortet und die falsche gestellt.

    ``applies`` ist die Ausnahme, und sie hat bei jedem Aufrufer einen anderen
    Namen für dieselbe Sache: Ein graviertes Muster, eine vertiefte Schrift und
    ein abziehender Baustein **schneiden**, und Schneiden darf teilen — bei
    manchen ist das der Zweck.

    Dreimal wortgleich geschrieben, bis zum 04.09.2026 — in ``label_ops``,
    ``texture_ops`` und ``knowledge.parts.ops``, und alle drei Docstrings
    verwiesen brav aufeinander („Dieselbe Bauart wie …"), ohne dass es einer
    auflöste. Die Fälle bleiben getrennt, weil sie verschiedene Messungen und
    verschiedene Sätze tragen; die Regel steht jetzt hier.
    """
    pieces_before, pieces_after = pieces(before), pieces(after)
    if not applies or pieces_after <= pieces_before:
        return None
    loose = pieces_after - pieces_before
    return Finding(
        code=code,
        severity="error",
        # **Der Vorschlag steht im Satz, und der Knopf daneben** (Regel 17):
        # Jeder Aufrufer rät, eine Eingabe des Schritts zu ändern — Fläche,
        # Ort, Rückplatte —, und *Eingabe korrigieren* öffnet genau diesen
        # Schritt; die Auswertung trägt seine Kennung nach.
        message=message(loose),
        suggestions=(CORRECT_INPUT,),
        values={
            **(dict(values) if values else {}),
            "loose": str(loose),
            "before": str(pieces_before),
            "after": str(pieces_after),
        },
    )


def pieces(body: Any) -> int:
    """Wie viele Stücke ein Körper hat — topologisch am exakten, über die Dreiecke am Netz.

    Zwei exakte Körper, die sich nur berühren, sind zwei; vernetzt können
    sie eines sein. ``Solid.solid_count`` fragt die Form, ``component_count``
    die Dreiecke — und die Dreiecke eines exakten Körpers entstünden hier
    nur für diese Zählung.
    """
    if isinstance(body, BRepBody):
        return int(body.solid_count)
    return int(body.component_count)


#: Der Satz, wenn ein Körper nach einem Schritt aus mehr Teilen besteht als
#: davor (:func:`body_split`).
MESSAGE_BODY_SPLIT: Final = _(
    "Der Körper zerfällt nach diesem Schritt in lose Teile. Strg+Z nimmt ihn zurück."
)


def body_split(were: int, are: int, *, op: str, object_id: str | None = None) -> Finding | None:
    """Ein Körper, der nach einem Schritt in mehr Teile zerfällt als vorher, sagt es.

    Das Urteil hinter ``feature.body_split``, an **einer** Stelle: Die
    Auswertung fällt es für jede Operation, die Merkmale einführt
    (``scene.evaluate._split_findings``), und ein Baustein, der gewollt ein
    loses Teil neben seinen Träger legt, fällt es über den Träger allein
    (``knowledge.parts.ops``) — nur er weiß, welche Teile Träger sind und
    welches die Schraube ist (``OperationSpec.leaves_separate_parts``).
    Gezählt wird beim Aufrufer; ``were`` und ``are`` sind die Teile davor und
    danach.

    Warnung ohne Knopf: Der Weg zurück steht im Satz (Strg+Z), und ein
    zerfallener Körper kann gewollt sein — geteilt wird auch mit Absicht.
    """
    if are <= were:
        return None
    return Finding(
        code="feature.body_split",
        severity="warning",
        message=MESSAGE_BODY_SPLIT,
        object_id=object_id,
        values={"before": were, "after": are, "op": op},
        source="internal",
    )


def without_effect(
    before: HasVolume,
    after: HasVolume,
    kind: BooleanKind,
    profile: Profile | None = None,
) -> Finding | None:
    """Hat die Operation am Körper überhaupt etwas geändert? (Regel 17, §2.7)

    Eine Magnettasche, die neben dem Körper liegt, schnitt nichts und sagte
    nichts: keine Ausnahme, kein Befund, kein Hinweis in der Statusleiste. Im
    Verlauf stand ein Schritt, im Viewport lag dasselbe Teil wie vorher, und
    der Nutzer sucht den Fehler in der Geometrie statt in der Position. Das
    steht unterhalb dessen, was Regel 17 überhaupt erfasst — dort geht es um
    Ausnahmen, und hier gab es keine.

    Gemessen am Volumen und nicht an den Dreiecken: eine Differenz, die eine
    Fläche nur streift, ändert die Vernetzung, ohne etwas abzutragen, und wäre
    sonst eine Meldung wert, die niemanden weiterbringt.

    **Und gemessen an der Düse, nicht an ``EPS_GEOM``.** Ein Werkzeug, das den
    Körper knapp verfehlt, schneidet keine Null: es nimmt den Span mit, den die
    beiden Hüllen gemeinsam haben. Gemessen an einer Bohrung Ø4,2 durch eine
    14 mm dicke Platte, gesetzt in eine Öffnung des Rahmens statt aufs
    Material: abgetragen wurden 0,002 mm³ statt 194, und weil 0,002 größer ist
    als ``EPS_GEOM``, sagte niemand etwas. Der Nutzer sah ein unverändertes
    Teil und einen Schritt im Verlauf — genau das Bild, gegen das diese
    Funktion geschrieben wurde. Ohne ``profile`` bleibt es beim Rechenepsilon:
    ein Aufrufer, der keinen Drucker kennt, soll nicht einen erfinden.

    Ein Befund und kein Fehler: die Operation ist gelaufen, sie hat nur nichts
    bewirkt — und was daran falsch war, weiß der Nutzer besser als der Kern.

    **Netz oder exakter Körper — die Frage ist dieselbe.** Verlangt wird nur
    ein Volumen; ``Solid`` bringt eines mit wie ``MeshData``. Die Skizzen-Ops
    rechnen im exakten Kern (§30.1) und hatten deshalb keinen Zugang zu dieser
    Auskunft: eine Tasche neben dem Körper lief dort genauso stumm durch, wie
    es die Magnettasche einmal tat.

    **Gefragt wird am Netz-Zwilling, nicht am exakten Integral** (Durchsicht
    0.5.1, BOHRUNG-10; :func:`_measured_volume`).
    """
    first, second = _measured_volume(before), _measured_volume(after)
    change = abs(second - first)
    threshold = profile.smallest_printable_volume if profile is not None else EPS_GEOM
    if change > threshold:
        return None
    return Finding(
        code="boolean.without_effect",
        severity="warning",
        message=(
            _(
                "Der Schnitt hat nichts abgetragen — das Werkzeug liegt neben dem Körper. "
                "Position prüfen oder an einer Fläche ausrichten."
            )
            if kind == "difference"
            else _(
                "Die Vereinigung hat nichts hinzugefügt — der Körper steckt schon ganz im "
                "anderen. Position prüfen."
            )
        ),
        # ``removed_mm3`` sagt, wie knapp es war: eine glatte Null heißt
        # „daneben", ein Tausendstel heißt „gestreift", und das sind zwei
        # verschiedene Handgriffe am Ort.
        values={
            "volume_mm3": round(first, 3),
            "removed_mm3": round(change, 6),
        },
        # Regel 17: „Position prüfen“ heißt den Schritt öffnen; die Auswertung
        # trägt seine Kennung nach.
        suggestions=(CORRECT_INPUT,),
    )


def _measured_volume(body: HasVolume) -> float:
    """Das Volumen, an dem :func:`without_effect` misst — am exakten Körper das
    seines Netz-Zwillings.

    **Das exakte Integral kann eine Minute kosten** (Durchsicht 0.5.1,
    BOHRUNG-10). An der Lochplatte ``pegboard-gs-100-v2.step`` hält die Naht
    einer BSpline-Rundung ihre Toleranz nicht, der Kern fällt auf den UV-Weg,
    und das Volumen braucht 33 s — vorher und nachher je einmal: *Bohrung
    verschließen* stand 75 s, *Bohrung ändern* 124 s. Die Frage „hat sich
    etwas geändert?" beantwortet der Zwilling genauso, den die Anzeige ohnehin
    braucht: Unberührte Flächen vernetzen sich gleich, die Änderung trägt nur
    den Sehnenfehler der geschnittenen. Das Integral rechnet der
    Auswertungsarbeiter danach für die Zahlenzeile.
    """
    if not isinstance(body, MeshData):
        converted = getattr(body, "to_mesh", None)
        if callable(converted):
            twin = converted()
            if isinstance(twin, MeshData):
                return float(twin.volume)
    return float(body.volume)
