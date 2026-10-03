"""Die Schichtanalyse im Prüfbericht (Bauplan §17.3, §22.2, §22.3).

Die Druckvorschläge (:mod:`app.core.slice.advise`) ändern Werte im
Druckdialog. Was die Geometrie selbst sagt — ein Teil beginnt in der Luft,
eine Decke spannt frei, eine Stelle ist schmaler als die Düse, anders gedreht
bräuchte es weniger Stützen —, gehört dorthin, wo der Kunde nach dem Import
zuerst hinsieht: in den Prüfbericht. Jede Zeile nennt ihren Ort (der Klick
fliegt hin, die passende Analysekarte geht auf) und eine Handlung.

Alle Zahlen hier sind **intern geschätzt** (``source="internal"``): aus dem
eigenen Analyse-Schnitt, nicht aus einer Druckdatei. Mit Werten aus G-Code
werden sie nie verrechnet (Regel 14, §22.5).

**Nicht in der Auswertung, sondern danach.** Eine Schichtanalyse kostet an
200 000 Dreiecken eine Sekunde; wer sie in die Auswertung legte, verlängerte
jeden Klick um diese Zeit. :func:`print_findings` läuft deshalb im Arbeiter
nach der Auswertung, ist abbrechbar, und merkt sich das Ergebnis am Netz —
dasselbe Netz wird nicht zweimal geschnitten.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import replace
from functools import partial
from typing import Final, cast

import manifold3d
import numpy as np
from shapely.geometry import Polygon as ShapelyPolygon

from app.core.errors import ORIENT_FOR_PRINT, SHOW_SUPPORT_NEED, OperationCancelled
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge import profiles
from app.core.slice import advise
from app.core.slice.analysis import (
    _material,
    _material_cross,
    largest_overhang_patch,
    model_support,
    slice_body,
)
from app.core.types import (
    CancelToken,
    CheckState,
    Finding,
    ObjectId,
    PrintSettings,
    Profile,
    Scene,
    SceneObject,
    SliceResult,
)
from app.core.units import EPS_GEOM
from app.i18n import _

#: So viele Inseln eines Körpers bekommen eine eigene Zeile, die mit dem
#: größten Stützbedarf zuerst. Ein Gitter mit zweihundert schwebenden Stegen
#: ist ein Befund, nicht zweihundert; die Zahl aller steht in jeder Zeile.
ISLANDS_LISTED: Final = 5

#: Ab diesem Anteil gesparter Stützen lohnt der Satz „anders gedreht". Darunter
#: ist der Unterschied eine Frage der Rundung, und eine andere Lage kostet
#: Standfläche oder Oberfläche, die niemand gegen fünf Prozent tauschen will.
ORIENT_WORTH_SHARE: Final = 0.2

#: Ab so viel Stützraum in mm³ wird eine andere Lage überhaupt gesucht — ein
#: Würfel von einem Zentimeter. Darunter trägt die Suche (eine Sekunde je
#: Körper) mehr Wartezeit bei, als die Antwort Material spart.
ORIENT_WORTH_SUPPORT: Final = 1000.0

#: Bei mehr Körpern wird keine Lage je Körper gesucht; der Befund nennt dann
#: den Weg über *Druckoptimal ausrichten*, das die ganze Szene nimmt.
ORIENT_SEARCH_BODIES: Final = 8

#: Unter dieser zusammenhängenden Fläche in mm² trägt sich ein Überhang
#: selbst — dieselbe Zahl, mit der die Druckvorschläge Stützen verlangen
#: (:data:`app.core.slice.advise.OVERHANG_LAYER_WORTH_SUPPORT`).
OVERHANG_REPORTED_FROM: Final = advise.OVERHANG_LAYER_WORTH_SUPPORT

#: Der Schlüssel, unter dem das Netz seine Analyse für den Bericht behält.
_CACHE_KEY: Final = "solidon_print_findings"


def print_findings(
    scene: Scene,
    profile: Profile,
    settings: PrintSettings,
    *,
    cancelled: CancelToken | None = None,
    progress: Callable[[float], None] | None = None,
    fitted: bool | None = None,
    check_status: Callable[[CheckState], None] | None = None,
    missing_basis: tuple[str, ...] = (),
) -> list[Finding]:
    """Die Befunde der Schichtanalyse und der Druckeinstellungen für eine Szene.

    Je Körper: Inseln (mit Höhe, Ort und Stützbedarf), die größte frei
    hängende Fläche, die längste freie Brücke, die schmalste Stelle unter der
    Mindestbahnbreite — und, wo es sich lohnt, wie viel Stütze eine andere
    Lage spart. Dazu einmal für die Szene, was an Material und Drucker hängt
    (:func:`app.core.slice.advise.warnings_for`).

    Resin kennt keine Düse, keine Brücke und keine Bahn; dort bleibt allein
    die Insel, denn auch im Harzbad beginnt sie in der Flüssigkeit.

    ``fitted``: Trägt die Szene Passungen? Wer das Dokument kennt, fragt
    ``scene.fits.fit_kinds_for`` und zählt die gebauten mit; ohne Angabe gelten
    die eingetragenen der Szene.

    ``missing_basis`` nennt fehlende bestätigte Grundlagen des Aufrufers,
    insbesondere unbekannte Originalkennungen vor einer Ersatzprofilauflösung.
    Davon abhängige Prüfungen bleiben offen. ``check_status`` belegt die
    tatsächliche Ausführung; null Befunde sind keine solche Auskunft.
    """
    entries = list(scene.objects.values())

    def planned(key: str, object_id: ObjectId | None, geometry: bool) -> CheckState:
        required = (("geometry",) if geometry else ()) + ("printer", "material", "print_settings")
        return CheckState(
            key=key,
            object_id=object_id,
            applicable=True,
            required_basis=required,
            missing_basis=tuple(value for value in required if value in missing_basis),
        )

    settings_check = planned("slice.settings", None, False)
    body_checks = [planned("slice.print_findings", entry.id, True) for entry in entries]

    def publish(state: CheckState) -> None:
        if check_status is not None:
            check_status(state)

    for state in (settings_check, *body_checks):
        publish(state)
    if not entries:
        publish(
            CheckState(
                key="slice.print_findings",
                applicable=False,
                required_basis=("geometry", "printer", "material", "print_settings"),
                state="not_applicable",
            )
        )

    def checked(state: CheckState, work: Callable[[], list[Finding]]) -> list[Finding]:
        if state.missing_basis:
            return []
        publish(replace(state, state="running"))
        try:
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            result = work()
            if cancelled is not None:
                cancelled.raise_if_cancelled()
        except OperationCancelled:
            publish(replace(state, state="cancelled"))
            raise
        except Exception:
            publish(replace(state, state="failed"))
            raise
        publish(replace(state, state="completed"))
        return result

    findings = checked(
        settings_check,
        lambda: advise.warnings_for(
            settings, profile, None, fitted=bool(scene.fits) if fitted is None else fitted
        ),
    )
    bodies: list[tuple[SceneObject, CheckState]] = []
    for entry, state in zip(entries, body_checks, strict=True):
        if state.missing_basis:
            # Auch das Bereitstellen eines exakten Körpers als Netz gehört
            # zur abhängigen Prüfung und beginnt ohne Grundlage nicht.
            continue
        try:
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            usable = bool(as_mesh_data(entry.mesh).triangle_count)
        except OperationCancelled:
            publish(replace(state, state="cancelled"))
            raise
        except Exception:
            publish(replace(state, state="failed"))
            raise
        if usable:
            bodies.append((entry, state))
        else:
            publish(replace(state, applicable=False, state="not_applicable"))
    search = len(bodies) <= ORIENT_SEARCH_BODIES and not profile.printer.is_resin
    for number, (entry, state) in enumerate(bodies):
        findings += checked(
            state,
            partial(body_findings, entry, profile, settings, cancelled=cancelled, search=search),
        )
        if progress is not None:
            progress((number + 1) / len(bodies))
    return findings


def body_findings(
    entry: SceneObject,
    profile: Profile,
    settings: PrintSettings,
    *,
    cancelled: CancelToken | None = None,
    search: bool = True,
) -> list[Finding]:
    """Was die Schichtanalyse über einen Körper zu berichten hat."""
    mesh = as_mesh_data(entry.mesh)
    wall, angle = profiles.analysis_limits(profile, entry)
    result = analysed(mesh, settings, angle, wall, cancelled=cancelled)
    bottom = float(mesh.bounds.minimum[2])
    found = island_findings(entry.id, result, bottom)
    if profile.printer.is_resin:
        return found
    found += overhang_findings(entry.id, result)
    found += [_placed(finding, entry.id) for finding in advise.located_warnings(result, profile)]
    # Eine Lage, die nach der Regel der Druckvorschläge keine Stütze braucht,
    # spart durch eine andere keine — dieselbe Frage wie ``orientation.stays``.
    if (
        search
        and result.support_volume >= ORIENT_WORTH_SUPPORT
        and advise.support_need(result).needed
    ):
        found += orientation_findings(entry.id, mesh, profile, cancelled=cancelled)
    return found


def analysed(
    mesh: MeshData,
    settings: PrintSettings,
    angle: float,
    wall: float,
    *,
    cancelled: CancelToken | None = None,
) -> SliceResult:
    """Die Schichtanalyse dieses Netzes im Druckraster — gemerkt am Netz.

    Der Merker hängt an ``trimesh``s eigenem Cache des Netzes: Er verfällt,
    sobald sich die Ecken ändern, und stirbt mit dem Netz. Im Schlüssel steht,
    was das Ergebnis bestimmt — Raster, Winkel, Brückenbreite.
    """
    stored = remembered_analysis(mesh, settings, angle, wall)
    if stored is not None:
        return stored
    cache = getattr(mesh.raw, "_cache", None)
    name = _cache_name(settings, angle, wall)
    result = slice_body(
        mesh,
        settings.layers.layer_height,
        first_layer_height=settings.layers.first_layer_height,
        overhang_angle=angle,
        bridge_from=wall,
        cancelled=cancelled,
    )
    if cache is not None:
        cache[name] = result
    return result


def remembered_analysis(
    mesh: MeshData, settings: PrintSettings, angle: float, wall: float
) -> SliceResult | None:
    """Die Schichtanalyse, die der Prüfbericht für genau dieses Raster schon hat.

    Der Druckdialog fragt hier, bevor er selbst schneidet (DRUCK-14,
    Durchsicht 0.5.1): Der Prüfbericht rechnet nach jedem Laden dieselben
    Schichten mit demselben Winkel und derselben Brückenbreite, und seine
    Messung ist eine Obermenge — sie trägt zusätzlich das Stützvolumen, das die
    Vorschläge nicht lesen. Ohne Treffer ``None``; gerechnet wird hier nie.
    """
    cache = getattr(mesh.raw, "_cache", None)
    if cache is None:
        return None
    # ``trimesh``s Cache prüft selbst, ob sich die Ecken geändert haben, und
    # gibt für einen fehlenden Eintrag ``None``.
    stored = cache[_cache_name(settings, angle, wall)]
    return stored if isinstance(stored, SliceResult) else None


def _cache_name(settings: PrintSettings, angle: float, wall: float) -> str:
    """Der Eintrag im Cache des Netzes: Raster, Winkel, Brückenbreite."""
    key = (
        _CACHE_KEY,
        round(settings.layers.layer_height, 6),
        round(settings.layers.first_layer_height, 6),
        round(angle, 6),
        round(wall, 6),
    )
    return "|".join(str(part) for part in key)


def island_findings(object_id: ObjectId, result: SliceResult, bottom: float) -> list[Finding]:
    """Eine Zeile je Insel, mit Ort, Höhe und dem Raum darunter (§22.2).

    Eine Insel ist eine Kontur, die in der Luft beginnt. Was sie braucht, ist
    eine Säule bis zum nächsten Material oder bis zur Platte — derselbe
    Durchgang wie beim Stützvolumen, nur für dieses eine Stück.
    """
    islands: list[tuple[float, int, ShapelyPolygon]] = []
    materials: dict[int, manifold3d.CrossSection] = {}
    for index, layer in enumerate(result.layers):
        for contour in layer.islands:
            piece = ShapelyPolygon(contour.outline, contour.holes)
            if piece.is_empty or piece.area <= EPS_GEOM * EPS_GEOM:
                continue
            islands.append(
                (_column_under(piece, result, index, bottom, materials=materials), index, piece)
            )
    if not islands:
        return []
    islands.sort(key=lambda item: (-item[0], item[1]))
    count = len(islands)
    findings = []
    for support, index, piece in islands[:ISLANDS_LISTED]:
        spot = piece.representative_point()
        z = result.layers[index].z
        findings.append(
            Finding(
                code="slice.island_needs_support",
                severity="warning",
                message=_("Dieser Teil beginnt in der Luft und braucht eine Stütze darunter."),
                object_id=object_id,
                values={
                    "z_mm": round(z, 2),
                    "area_mm2": round(float(piece.area), 1),
                    "support_cm3": round(support / 1000.0, 2),
                    "count": count,
                },
                location=(float(spot.x), float(spot.y), float(z)),
                source="internal",
                suggestions=(ORIENT_FOR_PRINT, SHOW_SUPPORT_NEED),
            )
        )
    return findings


def _column_under(
    piece: ShapelyPolygon,
    result: SliceResult,
    index: int,
    bottom: float,
    *,
    materials: dict[int, manifold3d.CrossSection] | None = None,
) -> float:
    """Der Raum unter dem Stück; Materialkonturen werden unter Inseln geteilt."""
    if materials is None:
        materials = {}
    pending = _material_cross(piece)
    volume = 0.0
    for below_index in range(index - 1, -1, -1):
        step = result.layers[below_index + 1].z - result.layers[below_index].z
        if below_index not in materials:
            materials[below_index] = _material_cross(_material(result.layers[below_index]))
        pending -= materials[below_index]
        if pending.is_empty():
            return volume
        volume += float(pending.area()) * step
    return volume + float(pending.area()) * max(result.layers[0].z - bottom, 0.0)


def overhang_findings(object_id: ObjectId, result: SliceResult) -> list[Finding]:
    """Die größte frei hängende Fläche, wenn sie sich nicht selbst trägt.

    Gefragt wird das Stück, nicht die Schichtsumme (siehe
    :func:`app.core.slice.analysis.largest_overhang_patch`): Ein Gitter mit
    sechsundfünfzig kleinen Stegunterseiten braucht keine Stütze, eine Decke
    von 138 mm² an einem Stück schon.
    """
    if largest_overhang_patch(result) <= OVERHANG_REPORTED_FROM:
        return []
    candidates: list[tuple[float, tuple[int, int], float, ShapelyPolygon]] = []
    for index, layer in enumerate(result.layers):
        # Eine Insel ist auch ein Überhang — der ganze Querschnitt hängt in der
        # Luft. Sie hat ihre eigene Zeile (:func:`island_findings`); hier
        # stünde dieselbe Stelle ein zweites Mal.
        floating = [ShapelyPolygon(entry.outline, entry.holes) for entry in layer.islands]
        for number, contour in enumerate(layer.overhangs):
            piece = ShapelyPolygon(contour.outline, contour.holes)
            if piece.area <= OVERHANG_REPORTED_FROM:
                continue
            if any(piece.intersection(island).area > 0.5 * piece.area for island in floating):
                continue
            candidates.append((float(piece.area), (index, number), layer.z, piece))
    if not candidates:
        return []
    # **Und keine Kanaldecke**, aus demselben Grund wie in den Vorschlägen
    # (``advise._from_geometry``): Sie schließt sich selbst, und eine Stütze
    # darin käme nicht mehr heraus. An einem Block mit einem 20-mm-Tunnel
    # verlangten die Vorschläge keine Stütze, und der Bericht sagte über
    # dieselbe Decke „braucht Stützen" — wer ihm folgte, füllte den Tunnel.
    # Gefragt wird erst hier, wo ein Befund ansteht, und nur nach diesen
    # Stücken: Über alle sechzehntausend Stücke des Eiffelturms kostet die
    # Kanalfrage fünf Sekunden, über die wenigen großen ein Bruchteil davon.
    channels = model_support(result, only=frozenset(entry[1] for entry in candidates)).channels
    kept = [entry for entry in candidates if entry[1] not in channels]
    if not kept:
        return []
    area, _name, z, piece = max(kept, key=lambda entry: entry[0])
    spot = piece.representative_point()
    return [
        Finding(
            code="slice.large_overhang",
            severity="warning",
            message=_("Diese Fläche hängt frei über und braucht Stützen."),
            object_id=object_id,
            values={"z_mm": round(z, 2), "area_mm2": round(area, 1)},
            location=(float(spot.x), float(spot.y), float(z)),
            source="internal",
            suggestions=(ORIENT_FOR_PRINT, SHOW_SUPPORT_NEED),
        )
    ]


def orientation_findings(
    object_id: ObjectId,
    mesh: MeshData,
    profile: Profile,
    *,
    cancelled: CancelToken | None = None,
) -> list[Finding]:
    """Wie viel Stütze eine andere Lage spart — mit Drehwinkel (§22.3).

    Dieselbe Suche wie *Druckoptimal ausrichten*, nur ohne zu drehen: Sie sagt,
    ob sich der Klick lohnt, bevor er gemacht wird. Gemeldet wird erst ab
    :data:`ORIENT_WORTH_SHARE`; die Ausgangslage muss selbst zulässig sein,
    sonst gibt es keinen Vergleich, und ohne Vergleich keine Ersparnis.
    """
    saving = _orientation_saving(mesh, profile, cancelled=cancelled)
    if saving is None:
        return []
    share, turn, support = saving
    return [
        Finding(
            code="orient.saves_support",
            severity="info",
            message=_("Anders gedreht braucht das Teil weniger Stützen."),
            object_id=object_id,
            values={
                "saved_percent": round(100.0 * share),
                "angle_deg": round(turn),
                "support_cm3": round(support / 1000.0, 2),
            },
            source="internal",
            suggestions=(ORIENT_FOR_PRINT,),
        )
    ]


def _orientation_saving(
    mesh: MeshData, profile: Profile, *, cancelled: CancelToken | None = None
) -> tuple[float, float, float] | None:
    """Anteil gesparter Stütze, Drehwinkel und verbleibender Stützraum — oder
    ``None``, wenn sich keine Lage lohnt. Gemerkt am Netz wie die Analyse.

    Die Suche kostet an einem Besteckeinsatz mit 59 744 Dreiecken zehn
    Sekunden; eine zweite Auswertung desselben Netzes — ein Klick in den Baum,
    ein Wechsel der Auswahl — soll sie nicht noch einmal bezahlen.
    """
    from app.core.geom.orient import NoFittingOrientationError
    from app.core.slice.orientation import search

    name = "|".join(
        (
            "solidon_orientation_saving",
            profile.printer.id,
            f"{profile.printer.layer_height:.6f}",
            f"{profile.overhang_limit_degrees:.6f}",
            f"{profile.smallest_first_layer:.6f}",
        )
    )
    cache = getattr(mesh.raw, "_cache", None)
    if cache is not None:
        cache.verify()
        if name in cache:
            stored = cache[name]
            return None if stored is None else cast(tuple[float, float, float], stored)
    saving: tuple[float, float, float] | None = None
    try:
        found = search(mesh, profile=profile, cancelled=cancelled)
    except NoFittingOrientationError:
        found = None
    if found is not None and found.baseline is not None:
        before = found.baseline.support_volume
        share = found.improvement / before if before > EPS_GEOM else 0.0
        if share >= ORIENT_WORTH_SHARE:
            rotation = np.asarray(found.transform, dtype=float)[:3, :3]
            cosine = float(np.clip((np.trace(rotation) - 1.0) / 2.0, -1.0, 1.0))
            saving = (share, math.degrees(math.acos(cosine)), found.best.support_volume)
    if cache is not None:
        cache[name] = saving
    return saving


def _placed(finding: Finding, object_id: ObjectId) -> Finding:
    """Derselbe Befund, an seinen Körper gebunden — mit dem Weg zur Karte."""
    return replace(finding, object_id=object_id, source="internal")
