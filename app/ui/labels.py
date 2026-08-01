"""Kurze Texte, auf die sich mehrere Teile der Oberfläche einigen müssen.

Ein Merkmal wird in der Viewport-Überlagerung, im Objektbaum und in der
Statusleiste gleich geschrieben — ``hole_3 · ⌀4.2``. Ein Ort dafür heißt: der
Name, den der Nutzer liest, ist der Name, den der Agent benutzt (§18.5,
Leitprinzip 5).
"""

from __future__ import annotations

from app.core.types import Feature, FeatureId
from app.core.units import format_length
from app.i18n import tr


def feature_label(feature_id: FeatureId, feature: Feature) -> str:
    """``hole_3 · ⌀4.2`` — die Beschriftung, die §18.5 verlangt, Name zuerst."""
    params = feature.params
    if feature.kind == "hole":
        return f"{feature_id} · Ø{format_length(float(params.get('diameter', 0.0)))}"
    if feature.kind == "face":
        return f"{feature_id} · {float(params.get('area', 0.0)):.0f} mm²"
    if feature.kind == "edge_loop":
        return f"{feature_id} · {params.get('open_edges', 0)} {tr('offene Kanten')}"
    return feature_id
