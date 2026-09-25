"""Einmalig: Review R12/R16/R21 — Suchbudget, Hinweis nach dem Auflösen, ein Befund
für jede gefundene Überschneidung."""

from __future__ import annotations

from pathlib import Path

path = Path("app/core/geom/repair.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str) -> None:
    global text
    assert text.count(old) == 1, (text.count(old), old[:100])
    text = text.replace(old, new)


swap(
    '''    Bericht nur zum Auflösen rät, wo es tragen kann: ``"open"`` (offen oder
    verzweigt), ``"winding"`` (Außenseiten zeigen gegeneinander), ``"flat"``
    (kein Volumen), ``"self"`` (eine Schale kreuzt sich selbst,
    :func:`_crossing_shape`), ``"cavity"`` (eine Innenschale, deren Zuordnung
    nicht belegt ist).
    """
    if not mesh.is_watertight:
        return "open"
    if not mesh.raw.is_winding_consistent:
        return "winding"
    if not signed_volume(mesh.raw) > 0.0:
        return "flat"
''',
    '''    Bericht nur zum Auflösen rät, wo es tragen kann: ``"open"`` (offen oder
    verzweigt), ``"winding"`` (Außenseiten zeigen gegeneinander),
    ``"inverted"`` (innen und außen vertauscht), ``"flat"`` (kein Volumen),
    ``"self"`` (eine Schale kreuzt sich selbst, :func:`_crossing_shape`),
    ``"cavity"`` (eine Innenschale, deren Zuordnung nicht belegt ist).
    **Verkehrt ist nicht flach** (Review R21): Ein umgestülpter Körper hieß
    „ohne Volumen", und dafür gab es keinen Befund.
    """
    if not mesh.is_watertight:
        return "open"
    if not mesh.raw.is_winding_consistent:
        return "winding"
    volume = signed_volume(mesh.raw)
    if abs(volume) <= EPS_GEOM * mesh.area:
        return "flat"
    if volume < 0.0:
        return "inverted"
''',
)

swap(
    '''    wird nur, wo es tragen kann (:func:`_intersections_resolvable`); sonst
    endete der Rat in der nächsten Warnung (Durchsicht 24.09.2026: vier von
    zwölf Körpern des Korpus).
    """
    crossings = crossings_of(result.mesh, cancelled, _search_progress(progress))
''',
    '''    wird nur, wo es tragen kann (:func:`_intersections_resolvable`); sonst
    endete der Rat in der nächsten Warnung (Durchsicht 24.09.2026: vier von
    zwölf Körpern des Korpus). **Und jede gefundene Überschneidung hat eine
    Zeile** (Review R21): Ein Körper ohne Volumen oder verkehrt herum bekam
    keine, und danach hieß es „nichts zu reparieren".

    **Gesucht wird so weit, wie es trägt** (Review R12): Am offenen oder
    gegeneinander gewickelten Netz löst die Reparatur ohnehin nichts auf, und
    über der Kartengrenze (``perceive.maps.MAP_LIMIT_TRIANGLES``) wuchs das
    Budget mit dem Netz — am Drachen 70 s für „nichts zu tun". Dort gilt der
    Sockel von :data:`MAX_INTERSECTION_PAIRS`; was die Suche nicht erreicht,
    sagt der Hinweis „vorzeitig beendet".
    """
    from app.core.perceive.maps import MAP_LIMIT_TRIANGLES

    mesh = result.mesh
    searchable = mesh.is_watertight and mesh.raw.is_winding_consistent
    budget = (
        None if searchable and mesh.triangle_count <= MAP_LIMIT_TRIANGLES else MAX_INTERSECTION_PAIRS
    )
    crossings = crossings_of(mesh, cancelled, _search_progress(progress), budget=budget)
''',
)

swap(
    '''            result.findings.append(
                Finding(
                    code="repair.self_intersections",
                    severity="info",
                    message=_("Überschneidungen wurden aufgelöst."),
                    values={"parts": result.mesh.component_count},
                )
            )
            return
    if blocked == "self":
        pass
    elif not self_intersections:
''',
    '''            result.findings.append(
                Finding(
                    code="repair.self_intersections",
                    severity="info",
                    message=_("Überschneidungen wurden aufgelöst."),
                    values={"parts": result.mesh.component_count},
                )
            )
            if not complete:
                # Aufgelöst ist, was gefunden war; was die Suche nicht erreicht
                # hat, bleibt ungesehen (Review R16).
                result.findings.append(
                    Finding(
                        code="repair.self_intersections_incomplete",
                        severity="info",
                        message=_(
                            "Die Suche nach Überschneidungen wurde vorzeitig beendet; es kann "
                            "weitere geben."
                        ),
                    )
                )
            return
    if blocked == "self":
        pass
    elif not self_intersections or blocked == "flat":
''',
)
swap(
    '''    elif blocked in ("open", "winding"):
        result.findings.append(
            Finding(
                code="repair.self_intersections_skipped",
                severity="warning",
                message=_(
                    "Überschneidungen lassen sich erst an einem geschlossenen Modell auflösen."
                )
                if blocked == "open"
                else _(
                    "Überschneidungen lassen sich nicht auflösen, solange Außenseiten "
                    "gegeneinander zeigen."
                ),
''',
    '''    elif blocked in ("open", "winding", "inverted"):
        result.findings.append(
            Finding(
                code="repair.self_intersections_skipped",
                severity="warning",
                message=_(
                    "Überschneidungen lassen sich erst an einem geschlossenen Modell auflösen."
                )
                if blocked == "open"
                else _(
                    "Überschneidungen lassen sich nicht auflösen, solange Außenseiten "
                    "gegeneinander zeigen."
                )
                if blocked == "winding"
                else _(
                    "Überschneidungen lassen sich nicht auflösen, solange innen und außen "
                    "vertauscht sind."
                ),
''',
)
swap(
    '''    elif blocked != "flat":
        # Eine Fläche ohne Dicke hat ihren eigenen Befund; hier bliebe nur
        # der Fall, den die Vereinigung nicht sicher lösen konnte.
        result.findings.append(
''',
    '''    else:
        # Übrig ist der Fall, den die Vereinigung nicht sicher lösen konnte.
        result.findings.append(
''',
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
