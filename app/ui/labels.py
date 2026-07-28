"""Short texts several parts of the surface need to agree on.

A feature is written the same way in the viewport overlay, in the object tree and
in the status bar — ``hole_3 · Ø4.2``. One place for it means the name the user
reads is the name the agent uses (§18.5, Leitprinzip 5).
"""

from __future__ import annotations

from app.core.types import Feature, FeatureId
from app.core.units import format_length
from app.i18n import tr


def feature_label(feature_id: FeatureId, feature: Feature) -> str:
    """``hole_3 · Ø4.2`` — the label §18.5 asks for, name first."""
    params = feature.params
    if feature.kind == "hole":
        return f"{feature_id} · Ø{format_length(float(params.get('diameter', 0.0)))}"
    if feature.kind == "face":
        return f"{feature_id} · {float(params.get('area', 0.0)):.0f} mm²"
    if feature.kind == "edge_loop":
        return f"{feature_id} · {params.get('open_edges', 0)} {tr('offene Kanten')}"
    return feature_id
