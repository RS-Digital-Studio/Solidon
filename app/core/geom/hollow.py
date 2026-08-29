"""Aushöhlen, mit den Entlüftungen, die es druckbar machen (Bauplan §25).

Ein massives Teil ist Material und Stunden, die niemand braucht. Es
auszuhöhlen ist eine gute Idee mit einer Bedingung: Harz und ungeschmolzenes
Pulver beiseite — ein FDM-Druck mit geschlossenem Hohlraum sperrt Luft ein,
und die erste Brücke darüber sackt durch. Die Entlüftung ist hier also keine
Option — sie ist die zweite Hälfte der Operation, und die Vorgabe.

Wie die Innenwand gefunden wird: der Körper kommt auf dasselbe Raster wie die
Analysekarten (§18.4), das Raster wird um die Wandstärke erodiert, und was
übrig bleibt, wird neu vernetzt. Das ist die Voxelstufe aus §17.2 mit ihrer
Genauigkeit und ihrer Ehrlichkeit — die Wand stimmt auf einen halben
Rasterschritt, und der Bericht sagt es.

Ein Versatz auf den Dreiecken selbst wäre exakt und faltete sich an jeder
konkaven Ecke ein — genau dort, wo ein hohles Teil die Wand am nötigsten
braucht.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import trimesh

from app.core.errors import PROGRAMMING_ERRORS
from app.core.geom.boolean import boolean, deepest
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import (
    CancelToken,
    Finding,
    Profile,
    ProgressFn,
    Quality,
    SolverInfo,
    Vec3,
)
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Wie fein das Raster ist, relativ zur stehenbleibenden Wand. Ein Drittel der
#: Wand heißt: die Wand stimmt auf ein Sechstel ihrer selbst.
PITCH_SHARE = 1.0 / 3.0

#: Nie feiner als das — ein Raster aus hundert Millionen Zellen hilft niemandem.
MIN_PITCH = 0.3

#: Wie weit die Entlüftung in den Hohlraum hineinragt, damit sie den Boden
#: sicher durchstößt. Ein Marching-Cubes-Rand liegt auf einen halben
#: Rasterschritt genau; der feinste Rasterschritt ist ``MIN_PITCH`` = 0,3 mm
#: (an dünnen Wänden), ein Millimeter Überstand deckt ihn und die halben
#: Schritte gröberer Raster sicher. In fünf Körpern gemessen bricht sie durch.
VENT_BREAKTHROUGH = 1.0

#: Vorgabe-Durchmesser der Entlüftung. Weit genug, damit Luft entweicht, eng
#: genug, dass das Loch danach nicht verschlossen werden muss.
VENT_DIAMETER = 4.0


@dataclass(slots=True)
class HollowResult:
    """Der hohle Körper, und was dazu zu sagen war."""

    mesh: MeshData
    removed: float = 0.0
    """Volumen, das entfernt wurde, in mm³."""
    vents: tuple[Vec3, ...] = ()
    findings: list[Finding] = field(default_factory=list)
    solver: SolverInfo | None = None
    """Die Rückfallstufe, auf der das Ergebnis zustande kam (§17.2).

    Aushöhlen fährt bis zu sechs Boolesche Schnitte — den Hohlraum, die
    Öffnung und je einen pro Entlüftung. Gemeldet hat es keine einzige Stufe,
    und damit stand im Bericht nichts darüber, ob die Wandstärke aus einem
    exakten Schnitt kommt oder aus einer Voxelnäherung."""


def hollow(
    mesh: MeshData,
    wall: float,
    *,
    vents: int = 1,
    vent_diameter: float = VENT_DIAMETER,
    open_top: bool = False,
    quality: Quality = "fine",
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> HollowResult:
    """Lässt eine Wand von ``wall`` Millimetern stehen und nimmt den Rest
    heraus.

    ``open_top`` nimmt zusätzlich die Decke über dem Hohlraum weg. Damit ist
    das Ergebnis eine Dose statt eines geschlossenen Körpers, und *Deckel
    erzeugen* findet die Öffnung, die es verlangt — der Weg dorthin führte
    sonst über zwei Zylinder und eine Differenz.
    """
    if wall <= EPS_GEOM:
        raise ValueError("a wall thickness has to be positive")

    # §15.6: Aushöhlen rastert einen ganzen Körper und fährt danach bis zu sechs
    # Boolesche Schnitte. Das dauert an einem gescannten Teil Minuten, und bis
    # hierher erfuhr niemand davon — weder wie weit es ist noch dass man
    # abbrechen kann. Gemeldet wird zwischen den Stufen: eine Stufe selbst ist
    # ein nativer Aufruf und kooperativ nicht zu unterbrechen (dieselbe Grenze
    # wie in :func:`app.core.geom.boolean.boolean`).
    _step(progress, cancelled, 0.05, _("Raster aufbauen"))
    field = _inner_field(mesh, wall)
    cavity = _meshed(field[0], field[1], field[2], mesh) if field is not None else None
    if cavity is None or cavity.triangle_count == 0:
        return HollowResult(
            mesh=mesh,
            findings=[too_thin(wall)],
        )

    before = mesh.volume
    _step(progress, cancelled, 0.4, _("Hohlraum ausschneiden"))
    outcome = boolean("difference", [mesh, cavity], quality=quality, cancelled=cancelled)
    body = outcome.mesh
    findings = list(outcome.findings)
    stages: list[SolverInfo | None] = [outcome.solver]

    if open_top and field is not None:
        opening = _mouth(field[0])
        tool = _meshed(opening, field[1], field[2], mesh) if opening is not None else None
        if tool is None:
            findings.append(
                Finding(
                    code="hollow.no_opening",
                    severity="warning",
                    message=_(
                        "Die Decke ließ sich nicht öffnen — der Hohlraum reicht "
                        "nicht bis unter die Oberseite."
                    ),
                )
            )
        else:
            opened = boolean("difference", [body, tool], quality=quality, cancelled=cancelled)
            body = opened.mesh
            findings.extend(opened.findings)
            stages.append(opened.solver)

    placed: tuple[Vec3, ...] = ()
    # Eine offene Dose ist ihre eigene Entlüftung. Ein Loch im Boden wäre dort
    # kein Schutz vor der durchsackenden Decke, sondern ein Loch im Boden.
    if vents > 0 and not open_top:
        _step(progress, cancelled, 0.8, _("Entlüftungen bohren"))
        body, placed, drilled = _vent(
            body, cavity, vent_diameter, vents, quality, progress, cancelled
        )
        stages.extend(drilled)
        if not placed:
            findings.append(
                Finding(
                    code="hollow.no_vent",
                    severity="warning",
                    message=_(
                        "Es war keine Stelle für eine Entlüftung zu finden — "
                        "ein geschlossener Hohlraum drückt beim Drucken die Decke hoch."
                    ),
                )
            )

    removed = before - body.volume
    steps, pitch = erosion_steps(wall)
    _log.info("hollowed out %.1f mm³ behind a %.2f mm wall", removed, wall)
    findings.append(
        Finding(
            code="hollow.done",
            severity="info",
            message=_("Ausgehöhlt. Die Wandstärke stimmt im Rahmen des Rasters."),
            values={
                "wall_mm": round(wall, 2),
                # Was die Erosion wirklich weggenommen hat, und wie weit der
                # Rasterrand daneben liegen kann. Der Sollwert allein war
                # keine Auskunft: Er stand auch dort, wo das Raster ihn gar
                # nicht treffen konnte.
                "eroded_mm": round(steps * pitch, 3),
                "tolerance_mm": round(pitch / 2.0, 3),
                "removed_cm3": round(removed / 1000.0, 1),
                "vents": len(placed),
            },
        )
    )
    worst = abs(steps * pitch - wall) + pitch / 2.0
    if worst > wall * PITCH_SHARE / 2.0 + EPS_GEOM:
        # Unter ``MIN_PITCH`` kommt das Raster nicht, also verfehlt eine dünne
        # Wand das Versprechen „ein Sechstel" — bei 0,5 mm um das Dreifache.
        # Das gehört gesagt (§2.7), mit dem Handgriff, der es behebt: Der Wert
        # steht im Dialog, und eine dickere Wand ist ein Zahlendreher weit weg.
        findings.append(
            Finding(
                code="hollow.coarse_grid",
                severity="warning",
                message=_(
                    "Für diese Wandstärke ist das Raster zu grob — die stehende Wand "
                    "kann spürbar dicker werden als eingetragen. Eine Wand ab einem "
                    "Millimeter trifft das Raster genau."
                ),
                values={
                    "wall_mm": round(wall, 2),
                    "eroded_mm": round(steps * pitch, 3),
                    "worst_case_mm": round(worst, 3),
                    # Die strukturelle Grenze als Zahl: ab hier trifft das Raster.
                    "fair_wall_mm": round(3.0 * MIN_PITCH, 2),
                },
            )
        )
    return HollowResult(
        mesh=body,
        removed=removed,
        vents=placed,
        findings=findings,
        solver=deepest(stages),
    )


def below_printable_wall(wall: float, profile: Profile | None) -> Finding | None:
    """Ist die Wand dünner, als der Drucker sie legen kann?

    **Beide Zwillinge trugen dafür eine Zahl, und beide waren falsch.** Im
    Schema stand ``minimum=0.4`` am Netz und ``minimum=0.2`` am exakten Kern —
    Zahlenkonstanten für eine Toleranz, also ein Verstoß gegen Regel 7 in
    seiner reinsten Form. Aufgefallen ist es an der Abweichung; der eigentliche
    Fund ist, dass auch die 0,4 nur **zufällig** stimmt, nämlich für eine
    0,4er Düse. Gemessen am Centauri mit 0,42 mm Bahnbreite sind zwei
    Extrusionsbreiten **0,84 mm** — die Schemagrenze ließ dort das Doppelte an
    zu dünner Wand durch, ohne ein Wort.

    Ein Schema-Minimum kann das nicht leisten: Es steht zur Deklarationszeit
    fest, das Profil kommt erst mit dem Auftrag. Also fragt die Operation, und
    zwar die Regel selbst (``Profile.minimum_wall_thickness``, §39) statt einer
    Kopie davon.

    Ein Befund und kein Fehler: Die Geometrie entsteht ja — sie ist nur nicht
    druckbar, und das ist eine Aussage über den Drucker, nicht über den Körper.
    Wer denselben Körper auf einer feineren Düse fährt, hat kein Problem.
    """
    # **Ohne Drucker keine Aussage.** Dieselbe Regel wie bei
    # ``boolean.without_effect`` nebenan („ein Aufrufer, der keinen Drucker
    # kennt, soll keinen erfinden"): Die Grenze *ist* der Drucker, also gibt es
    # sie ohne ihn nicht. Der Fall kommt vor — ein direkter Aufruf der
    # Operation ohne Profil, wie ihn Tests und die Kommandozeile bauen —, und
    # er wäre bis zum 27.08.2026 in einem AttributeError geendet: Die alte
    # Zahlenkonstante brauchte kein Profil, diese Frage schon.
    if profile is None:
        return None
    least = profile.minimum_wall_thickness
    if wall >= least - EPS_GEOM:
        return None
    return Finding(
        code="hollow.wall_below_nozzle",
        severity="warning",
        message=_("Die Wand ist dünner, als der Drucker sie legen kann."),
        values={"wall_mm": round(wall, 2), "least_mm": round(least, 2)},
    )


def hollowed(wall: float, removed_mm3: float) -> Finding:
    """Ausgehöhlt — und wie viel dabei herausgekommen ist.

    Das Gegenstück zu :func:`too_thin`, und aus demselben Grund geteilt: Beide
    Kerne haben den Fall, und für den Kunden ist es dieselbe Auskunft.

    **Der Erfolgsfall war der letzte, in dem die Zwillinge auseinanderliefen.**
    Nach dem Fix vom 27.08.2026 meldeten beide dieselben Warnungen; gefahren
    mit einer Wandstärke, die *funktioniert*, sagte der Netz-Zwilling
    ``hollow.done`` mit seinen Zahlen und der exakte schwieg. Gerade dort
    zählt die Auskunft am meisten: Wie viel Material weg ist, ist der Grund,
    aus dem man aushöhlt.

    **Weniger Werte als der Netz-Zwilling, und das ist kein Mangel.** Dort
    stehen zusätzlich ``eroded_mm``, ``tolerance_mm`` und ``vents`` — sie
    beschreiben das Raster und die Entlüftungen, und beides hat der exakte
    Kern nicht (siehe ``registry._HOLLOW_TOGGLE``). Eine Null dafür wäre eine
    Aussage über etwas, das es nicht gibt.
    """
    return Finding(
        code="hollow.done",
        severity="info",
        message=_("Ausgehöhlt."),
        values={"wall_mm": round(wall, 2), "removed_cm3": round(removed_mm3 / 1000.0, 1)},
    )


def too_thin(wall: float) -> Finding:
    """Für diese Wandstärke bleibt kein Hohlraum übrig.

    Geteilt, weil **beide Kerne** denselben Fall haben: Das Netz merkt es am
    leeren Hohlraumnetz, der exakte am unveränderten Volumen — und für den
    Kunden ist es dieselbe Auskunft. Bis zum 27.08.2026 hatte nur das Netz sie;
    ``shell_exact`` gab in keinem einzigen von dreizehn gemessenen
    Wandstärkenfällen einen Befund zurück, obwohl von 15 bis 50 Millimetern
    nur ein einziger Wert überhaupt etwas bewirkt. Zwei wörtliche Kopien des
    Satzes wären zwei Stellen, an denen er auseinanderläuft.
    """
    return Finding(
        code="hollow.too_thin",
        severity="warning",
        message=_("Für diese Wandstärke bleibt kein Hohlraum übrig."),
        values={"wall_mm": round(wall, 2)},
    )


def _inner_field(mesh: MeshData, wall: float) -> tuple[np.ndarray, Vec3, float] | None:
    """Das Raster des Körpers, eingezogen um die Wandstärke.

    Getrennt von der Vernetzung, weil zwei Dinge daraus entstehen: der
    Hohlraum, der herausgeschnitten wird, und die Öffnung, die ihn nach oben
    freilegt. Zweimal zu rastern wäre derselbe Lauf über dieselben Dreiecke.
    """
    from scipy import ndimage

    from app.core.perceive.maps import solid_field

    steps, pitch = erosion_steps(wall)
    field = solid_field(mesh, pitch)
    inner = ndimage.binary_erosion(field.filled, iterations=steps)
    if not inner.any():
        return None
    return inner, field.origin, pitch


def erosion_steps(wall: float) -> tuple[int, float]:
    """Wie oft erodiert wird und mit welcher Rasterweite.

    Eine Zeile Rechnung, und trotzdem eine eigene Funktion: :func:`hollow`
    **meldet** diese zwei Zahlen, und sie müssen dieselben sein, mit denen
    gerechnet wurde. Zweimal hingeschrieben wären sie beim ersten Nachbessern
    an einer Stelle andere.

    Die Weite ist ein Drittel der Wand, aber nie feiner als ``MIN_PITCH``. Die
    strukturelle Grenze ist damit ``3 * MIN_PITCH`` = 0,9 mm: darüber geht die
    Wand in ganzen Schritten auf und stimmt auf ein Sechstel; darunter greift
    ``MIN_PITCH``, und die ±1/6-Zusage hält nicht mehr — 0,8 mm werden drei
    Schritte à 0,3, also 0,9 mm Erosion, und 0,5 mm werden zwei Schritte à 0,3,
    also 0,6 mm (+30 %). Das ist kein Fehler, den man wegrunden kann — ein
    feineres Raster **wäre** genauer und ist ausdrücklich nicht gewollt.

    Der Versuch, es andersherum zu rechnen (erst die Schrittzahl, dann
    ``wall / steps``), ist gemessen worden und war schlechter: Er trifft die
    Wand rechnerisch exakt und macht dafür das Raster gröber, und die
    Unschärfe des Rasterrandes wächst schneller, als die Rundung einbringt —
    an einem 40er Würfel mit 0,5 mm Wand von 30 % auf 50 % Abweichung. Und das
    feinere Raster kostet Speicher: gemessen ``wall / 3`` gegen den Bestand
    +325 MB (3,4-fach) am 40er Würfel, +898 MB (4,2-fach) am 100-mm-Teil,
    +1354 auf 2326 MB an ``dense_1m`` — der Grund für die feste Untergrenze.

    Was bleibt, gehört deshalb in den Befund und nicht in eine Rundung:
    ``steps * pitch`` ist der Betrag, der wirklich abgetragen wird, und
    ``pitch / 2`` die Unschärfe darüber hinaus.
    """
    pitch = max(wall * PITCH_SHARE, MIN_PITCH)
    return max(1, round(wall / pitch)), pitch


def _meshed(matrix: np.ndarray, origin: Vec3, pitch: float, like: MeshData) -> MeshData | None:
    """Ein Rasterkörper als Netz, an seinem Platz."""
    body = trimesh.voxel.ops.matrix_to_marching_cubes(matrix=matrix, pitch=pitch)
    body.apply_translation(np.asarray(origin, dtype=float))
    return like.replacing(body) if len(body.faces) else None


def _mouth(matrix: np.ndarray) -> np.ndarray | None:
    """Das Raster der Öffnung: der oberste Querschnitt des Hohlraums, nach oben
    durchgezogen.

    Der oberste und nicht die Vereinigung aller — eine Dose soll ihre Decke
    verlieren, nicht ihre Schulter. Wo der Hohlraum nach oben zuläuft, wird die
    Öffnung entsprechend enger; das ist bei einer Kugel wenig sinnvoll und bei
    allem, was wie ein Behälter aussieht, genau richtig.

    Nach oben bis an den Rand des Rasters, und der liegt eine Zelle über dem
    Körper (``solid_field`` legt ihn dort hin). Damit ragt das Werkzeug hinaus,
    statt eine Fläche mit dem Deckel zu teilen (§39).
    """
    levels = np.flatnonzero(matrix.any(axis=(0, 1)))
    if not len(levels):
        return None
    top = int(levels[-1])
    opening = np.zeros_like(matrix)
    opening[:, :, top:] = matrix[:, :, top][:, :, None]
    return opening if opening.any() else None


def _step(
    progress: ProgressFn | None, cancelled: CancelToken | None, fraction: float, text: object
) -> None:
    """Ein Schritt weiter — und die Frage, ob es noch gewollt ist (§15.6)."""
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if progress is not None:
        progress(fraction, str(text))


def _vent(
    body: MeshData,
    cavity: MeshData,
    diameter: float,
    count: int,
    quality: Quality,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> tuple[MeshData, tuple[Vec3, ...], list[SolverInfo | None]]:
    """Bohrt vom Hohlraum nach unten durch den Boden.

    Nach unten mit Absicht: eine Entlüftung in der Bodenfläche sitzt auf der
    Druckplatte, wo sie weder zu sehen noch im Weg ist, und die Luft entweicht
    in der Richtung, in der der Druck wächst.

    **Und nur nach unten** — das stand hier von Anfang an und stimmte nicht.
    Der Bohrer war so lang wie der ganze Körper plus vier Millimeter und lag
    mittig darüber: Er kam zwei Millimeter unter dem Boden heraus **und zwei
    über der Decke**. Aus „einer Entlüftung im Boden" wurde ein durchgehendes
    Loch, und eine Dose, die zu bleiben hatte, war oben offen. Jetzt endet er
    im Hohlraum, einen Millimeter über dessen Boden.
    """
    from app.core.geom.transform import apply, translation

    inside = cavity.bounds
    outside = body.bounds
    stages: list[SolverInfo | None] = []
    if inside.size[2] <= EPS_GEOM:
        return body, (), stages

    spots: list[Vec3] = []
    for index in range(count):
        # Entlang X über die Mitte des Hohlraums verteilt, damit mehrere
        # Entlüftungen nicht in derselben Ecke landen.
        share = (2 * index + 1) / (2 * count)
        x = inside.minimum[0] + inside.size[0] * share
        spots.append((float(x), float(inside.centre[1]), 0.0))

    drilled = body
    placed: list[Vec3] = []
    # Von zwei Millimetern unter dem Boden bis knapp in den Hohlraum hinein.
    bottom = float(outside.minimum[2]) - 2.0
    top = float(inside.minimum[2]) + VENT_BREAKTHROUGH
    height = top - bottom
    if height <= EPS_GEOM:
        return body, (), stages
    for index, spot in enumerate(spots, start=1):
        _step(progress, cancelled, 0.8 + 0.15 * index / len(spots), _("Entlüftungen bohren"))
        tool = trimesh.creation.cylinder(radius=diameter / 2.0, height=height)
        tool = apply(
            MeshData.of(tool),
            translation((spot[0], spot[1], bottom + height / 2.0)),
        )
        try:
            outcome = boolean("difference", [drilled, tool], quality=quality, cancelled=cancelled)
            drilled, stage = outcome.mesh, outcome.solver
        except PROGRAMMING_ERRORS:
            raise
        except Exception as problem:  # eine Entlüftung, die nicht geht, ist nicht fatal
            _log.info("vent at %s failed: %s", spot, problem)
            continue
        placed.append(spot)
        stages.append(stage)
    return drilled, tuple(placed), stages
