"""Flache Umrisse mit einer Höhe (Bauplan §25, „SVG und DXF mit
Extrusion").

Ein Logo, eine Dichtung, eine Frontplatte, eine von einem Foto abgezeichnete
Schablone: zwei Dimensionen plus eine Dicke sind ein großer Teil dessen, was
gedruckt wird, und der übliche Weg dahin ist ein Umweg über ein
Modellierprogramm. Das hier ist der kurze Weg.

Löcher kommen als Löcher heraus. Das klingt selbstverständlich und ist der
Teil, der in naiven Umsetzungen schiefgeht — eine Kontur in einer anderen
Kontur ist ein Loch, und das entscheidet die Verschachtelung, nicht die
Reihenfolge, in der die Datei sie aufzählt. Gelesen wird die Zeichnung von
trimesh; verschachtelt wird seit dem 24.08.2026 hier, über shapely — trimeshs
eigener Weg (``polygons_full``) läuft durch ``rtree``, und warum das Paket den
Prozess nicht mehr betreten darf, steht an
:func:`app.core.geom.mesh.on_surface`.

**Einheiten.** SVG hat keine verlässliche: eine Datei sagt 100 und meint
Pixel, Millimeter oder Punkt, je nachdem wer sie geschrieben hat. Also werden
die Koordinaten als Millimeter gelesen, und es gibt eine Zielbreite, um es
anders zu sagen — eine als Erkennung verkleidete Vermutung wäre schlechter als
eine Zahl, die jemand sieht und ändern kann (§11.1).
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import PROGRAMMING_ERRORS, ValidationError

# Vor ``trimesh.load_path``, nicht erst in ``nested_polygons``: Der Aufruf
# ersetzt trimeshs ``enclosure_tree`` (siehe Modulkopf von ``enclosure``), und
# ``extrude`` ruft den Loader **vor** der Verschachtelung.
# Heute fasst der Loader die Funktion nicht an — eine trimesh-Version, die im
# Laden eine Fläche rechnet, kippte das ohne Vorwarnung. Dieselbe Zeile wie in
# ``geom.section``.
from app.core.geom import enclosure
from app.core.geom.mesh import MeshData, concatenated
from app.core.log import get_logger
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Was sich hier lesen lässt. Beides kommt aus den Pfad-Ladern von trimesh.
OUTLINE_SUFFIXES: tuple[str, ...] = (".svg", ".dxf")


@dataclass(frozen=True, slots=True)
class OutlineResult:
    """Der extrudierte Körper und wie der Umriss aussah."""

    mesh: MeshData
    contours: int
    width: float
    """Breite des Umrisses vor dem Skalieren, in den Zahlen der Datei selbst."""


@dataclass(frozen=True, slots=True)
class OutlineProfile:
    """Eine Außenkontur mit ihren Innenringen und geometrischer Kennung."""

    id: str
    polygon: Any


def is_outline(suffix: str) -> bool:
    return suffix.lower() in OUTLINE_SUFFIXES


def _svg_defaults(payload: bytes) -> bytes:
    """Ergänzt SVG-Standardwerte, die der Pfadleser ausdrücklich erwartet.

    An Rechtecken bedeutet ein fehlendes x oder y jeweils null. Die Kopie
    behält alle vorhandenen Werte und Transformationen; die eingebettete
    Originalquelle bleibt unverändert. ElementTree lädt keine externen
    Entitäten und begrenzt die Expansion interner Entitäten selbst.
    """
    root = ET.fromstring(payload)
    changed = False
    for element in root.iter():
        if element.tag not in ("rect", "{http://www.w3.org/2000/svg}rect"):
            continue
        for name in ("x", "y"):
            if name not in element.attrib:
                element.set(name, "0")
                changed = True
    return ET.tostring(root, encoding="utf-8") if changed else payload


def nested_polygons(rings: list[np.ndarray]) -> list[Any]:
    """Geschlossene Ringe nach ihrer Verschachtelung zu Flächen mit Löchern.

    Ringreparatur und Aufbau sind die von trimeshs ``polygons_full``
    (``paths_to_polygons``, Löcher gedreht, das Ergebnis noch einmal
    repariert); die Verschachtelung selbst kommt aus
    :func:`app.core.geom.enclosure.enclosure_tree` — **eine** Fassung für
    Zeichnung und Schnittdeckel, damit die beiden nicht auseinanderdriften.
    Warum sie ``rtree`` ersetzt, steht dort und an
    :func:`app.core.geom.mesh.on_surface`.

    Ein erster eigener Versuch mit inneren Punkten und ``buffer(0)`` ist an
    der Messung gescheitert — 295 statt 407 Konturen an einer der drei
    Beispielzeichnungen. Wer nur den Index tauscht, aber anders repariert
    oder anders enthält, bekommt andere Flächen; deshalb hier Zeile für
    Zeile trimeshs Weg. An allen drei Beispiel-SVGs sind Konturen,
    Dreieckszahlen und Volumina identisch mit ``polygons_full``, gemessen
    ohne ``rtree`` im Prozess.
    """
    from shapely.geometry import Polygon
    from trimesh.path.polygons import paths_to_polygons, repair_invalid

    from app.core.geom.enclosure import enclosure_tree

    closed = list(paths_to_polygons(rings))
    roots, tree = enclosure_tree(closed)
    result = []
    for root in roots:
        if closed[root] is None:
            continue
        holes = [
            np.array(closed[child].exterior.coords)[::-1]
            for child in tree[root]
            if closed[child] is not None
        ]
        repaired = repair_invalid(Polygon(shell=closed[root].exterior, holes=holes))
        if repaired is not None:
            result.append(repaired)
    return result


def read_profiles(payload: bytes, suffix: str) -> tuple[OutlineProfile, ...]:
    """Liest getrennte Profile; Innenringe und transformierte Lage bleiben erhalten.

    Die Kennung stammt aus der normalisierten Geometrie, nicht aus der
    Reihenfolge der XML-Elemente. Auch unbrauchbare Profile bleiben sichtbar.
    """
    if not is_outline(suffix):
        raise ValidationError(
            field="file",
            detail=_("Dieses Format ist keine flache Zeichnung."),
            value=suffix,
            constraint="not_outline",
        )

    enclosure.install()
    try:
        source = _svg_defaults(payload) if suffix.lower() == ".svg" else payload
        path = trimesh.load_path(io.BytesIO(source), file_type=suffix.lower().lstrip("."))
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # jeder Parser scheitert auf seine eigene Art
        raise ValidationError(
            field="file",
            detail=_("Die Zeichnung ließ sich nicht lesen."),
            constraint="unreadable",
            values={"suffix": suffix},
        ) from problem

    rings = [np.asarray(entry, dtype=float) for entry in getattr(path, "discrete", ())]
    polygons = nested_polygons(rings)
    if not polygons:
        raise ValidationError(
            field="file",
            detail=_("In dieser Zeichnung ist keine geschlossene Fläche."),
            constraint="no_area",
            values={"suffix": suffix},
        )

    return tuple(
        OutlineProfile(hashlib.sha256(entry.normalize().wkb).hexdigest(), entry)
        for entry in polygons
    )


def selected_profiles(
    profiles: tuple[OutlineProfile, ...], contours: str
) -> tuple[OutlineProfile, ...]:
    """Löst gespeicherte Kennungen auf; nur der historische Leerwert meint alle."""
    if not contours:
        return profiles
    try:
        selected = json.loads(contours)
    except (ValueError, TypeError) as problem:
        raise ValidationError(
            field="contours",
            detail=_("Wählen Sie die gewünschten Konturen erneut in der Vorschau."),
            constraint="invalid_contours",
        ) from problem
    if (
        not isinstance(selected, list)
        or not selected
        or any(not isinstance(entry, str) for entry in selected)
        or not set(selected).issubset(entry.id for entry in profiles)
    ):
        raise ValidationError(
            field="contours",
            detail=_("Wählen Sie mindestens eine vorhandene Kontur in der Vorschau."),
            constraint="invalid_contours",
        )
    identifiers = set(selected)
    return tuple(entry for entry in profiles if entry.id in identifiers)


def _solid_reason(profile: OutlineProfile, body: Any) -> str:
    """Erklärt leere und nicht geschlossene Extrusionen mit der Kerngrenze."""
    if profile.polygon.area <= EPS_GEOM * profile.polygon.length:
        return str(_("Diese Kontur ist zu dünn oder flächenlos. Wählen Sie eine andere Kontur."))
    if not body.is_watertight or not body.is_volume:
        return str(
            _("Diese Kontur bildet keinen geschlossenen Körper. Prüfen Sie ihre Innenringe.")
        )
    return ""


def profile_reason(profile: OutlineProfile) -> str:
    """Prüft die echte Extrusion für die Profilauswahl, ohne etwas zu entfernen."""
    try:
        body = trimesh.creation.extrude_polygon(profile.polygon, height=1.0)
    except PROGRAMMING_ERRORS:
        raise
    except Exception:  # Triangulierer melden ungültige Flächen unterschiedlich
        return str(_("Diese Kontur lässt sich nicht füllen. Prüfen Sie die Zeichnung."))
    return _solid_reason(profile, body)


def extrude(
    payload: bytes, suffix: str, height: float, width: float = 0.0, *, contours: str = ""
) -> OutlineResult:
    """Liest eine Zeichnung und gibt den gewählten Profilen eine gemeinsame Dicke."""
    return extrude_profiles(read_profiles(payload, suffix), height, width, contours=contours)


def extrude_profiles(
    profiles: tuple[OutlineProfile, ...], height: float, width: float = 0.0, *, contours: str = ""
) -> OutlineResult:
    """Gemeinsamer Rechenweg für Operation und Vorschau bereits gelesener Profile.

    ``width`` skaliert die ausgewählte Fläche in der Ebene; null behält die
    Zahlen der Datei als Millimeter. Der leere Altwert behält auch die alte
    Extrusion ungeprüfter Konturen, damit Projekte unverändert rechnen.
    """
    if height <= EPS_GEOM:
        raise ValueError("an extrusion needs a positive height")
    chosen = selected_profiles(profiles, contours)
    parts = []
    for entry in chosen:
        try:
            body = trimesh.creation.extrude_polygon(entry.polygon, height=height)
        except PROGRAMMING_ERRORS:
            raise
        except Exception as problem:
            raise ValidationError(
                field="contours",
                detail=_("Diese Kontur lässt sich nicht füllen. Prüfen Sie die Zeichnung."),
                constraint="invalid_contours",
            ) from problem
        reason = _solid_reason(entry, body) if contours else ""
        if reason:
            raise ValidationError(field="contours", detail=reason, constraint="invalid_contours")
        parts.append(body)
    body = parts[0] if len(parts) == 1 else concatenated(parts)

    # Gemessen wird der **Körper** aus den geschlossenen Ringen, nicht
    # ``path.bounds`` über die ganze Zeichnung: eine offene Hilfs-, Maß- oder
    # Rahmenlinie steht dort mit drin, im Körper aber nicht — bei DXF ist das
    # der Normalfall. An der Zeichnung gemessen wurde aus 40 mm ein Teil von 17,
    # und der Befund meldete die Breite der Linie. Maß und Meldung kommen jetzt
    # aus einer Quelle.
    actual = float(body.bounds[1][0] - body.bounds[0][0])
    scale = (width / actual) if width > EPS_GEOM and actual > EPS_GEOM else 1.0
    if abs(scale - 1.0) > EPS_GEOM:
        # Nur in der Ebene: die Höhe wurde in Millimetern verlangt und schrumpft
        # nicht, weil die Zeichnung auf eine Breite skaliert wurde.
        body.apply_scale([scale, scale, 1.0])
    # Auf die Platte und zentriert: ein Umriss, gezeichnet um irgendeine Ecke
    # eines Zeichenblatts, landete sonst dort, wo diese Ecke war.
    body.apply_translation(-body.bounds[0] * [0, 0, 1] - [*body.centroid[:2], 0.0])

    _log.info("extruded %d contour(s)", len(chosen))
    return OutlineResult(mesh=MeshData.of(body), contours=len(chosen), width=actual)
