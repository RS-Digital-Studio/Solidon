"""Einmalig: Tests an die neuen Reparaturbefunde anpassen."""

from pathlib import Path

path = Path("tests/test_repair.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str) -> None:
    global text
    assert text.count(old) == 1, old[:80]
    text = text.replace(old, new, 1)


swap(
    '''    wide = next(f for f in result.findings if f.code == "repair.wide_hole_filled")
    assert wide.severity == "warning"
    assert "prüfen" in str(wide.message).lower()
''',
    '''    wide = next(f for f in result.findings if f.code == "repair.wide_hole_filled")
    assert wide.severity == "warning"
    # Der Klick auf die Zeile fliegt zur Öffnung, und der Rückweg ist ein
    # Knopf (Entscheidung Robert, 24.09.2026): „Offen lassen".
    assert [action.id for action in wide.suggestions] == ["leave_open"]
    assert wide.location is not None
    low, high = body.bounds.min, body.bounds.max
    assert all(low[axis] - 1e-6 <= wide.location[axis] <= high[axis] + 1e-6 for axis in range(3))
''',
)

swap(
    '''    history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=("obj_1",))])

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    found = next(
        finding
        for finding in result.scene.report.findings
        if finding.code == "repair.self_intersections_detected"
    )
    assert found.op_id == document.ops[-1].id
    assert found.object_id == "obj_1"
    assert found.severity == "warning"
    assert {action.id for action in found.suggestions} == {"correct_input", "show_locations"}
''',
    '''    history.apply(
        _("Reparieren"),
        [OperationDraft(op="repair", inputs=("obj_1",), params={"self_intersections": False})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    found = next(
        finding
        for finding in result.scene.report.findings
        if finding.code == "repair.self_intersections_detected"
    )
    assert found.op_id == document.ops[-1].id
    assert found.object_id == "obj_1"
    assert found.severity == "warning"
    # Ein Knopf, der den Schritt mit dem Haken neu rechnet — statt eines
    # Menüwegs im Satz und eines Dialogs, der die Klappe zu lässt.
    assert [action.id for action in found.suggestions] == [
        "resolve_intersections",
        "show_locations",
    ]
''',
)

swap(
    '''        result = original(*args, **kwargs)
        monkeypatch.setattr(repair_module, "MAX_INTERSECTION_PAIRS", 0)
        return result
''',
    '''        result = original(*args, **kwargs)
        monkeypatch.setattr(repair_module, "intersection_budget", lambda _triangles: 0)
        return result
''',
)

swap(
    '''    body, _ = merge_vertices(raw("cube_clean.stl"))
    monkeypatch.setattr(repair_module, "MAX_INTERSECTION_PAIRS", 0)

    result = repair(body, inspect_intersections=True)

    assert not result.changed
    assert [finding.code for finding in result.findings] == ["repair.self_intersections_incomplete"]
''',
    '''    body, _ = merge_vertices(raw("cube_clean.stl"))
    monkeypatch.setattr(repair_module, "intersection_budget", lambda _triangles: 0)

    result = repair(body, inspect_intersections=True)

    assert not result.changed
    assert [finding.code for finding in result.findings] == ["repair.self_intersections_incomplete"]
    # Ein Hinweis ohne Knopf: Es gibt keine markierten Stellen, zu denen er
    # führen könnte, und eine Warnung im Normalfall wäre keine mehr.
    incomplete = result.findings[0]
    assert incomplete.severity == "info"
    assert incomplete.suggestions == ()


def test_the_intersection_budget_grows_with_the_mesh() -> None:
    """Das Budget reißt an gewöhnlichen Teilen nicht und bleibt linear.

    Ein Besteckkorb mit 8 672 Dreiecken brachte 2,7 Millionen Sweep-Paare,
    ein Besenhalter mit 59 740 schon 22 Millionen — beide ohne Durchdringung,
    beide warnten bei jedem Reparieren „unvollständig" (Durchsicht 24.09.2026).
    """
    from app.core.geom.repair import (
        INTERSECTION_PAIRS_PER_TRIANGLE,
        MAX_INTERSECTION_PAIRS,
        intersection_budget,
    )

    assert intersection_budget(10) == MAX_INTERSECTION_PAIRS
    assert intersection_budget(59_740) >= 22_093_481, "der Besenhalter wird ganz geprüft"
    assert intersection_budget(1_000_000) == INTERSECTION_PAIRS_PER_TRIANGLE * 1_000_000
''',
)

swap(
    '''    result = repair(raw("broken_open.stl"), holes=False, self_intersections=True)

    by_code = {finding.code: finding for finding in result.findings}
    assert "repair.self_intersections_skipped" in by_code
    assert "repair.still_open" in by_code, "übersprungene Prüfung und Rest sind zwei Aussagen"
    skipped = str(by_code["repair.self_intersections_skipped"].message)
    remaining = str(by_code["repair.still_open"].message)
    assert "geschlossenen Körper" in skipped and "Außenseiten" in skipped
    assert "Kanten verfeinern" not in skipped
    assert skipped != remaining, "Prüfung übersprungen und Rest offen dürfen sich nicht doppeln"
''',
    '''    crossing, _ = merge_vertices(raw("broken_selfint.stl"))
    opened = MeshData.of(
        crossing.raw.submesh([range(1, crossing.triangle_count)], append=True, repair=False)
    )
    result = repair(opened, holes=False, self_intersections=True)

    by_code = {finding.code: finding for finding in result.findings}
    assert "repair.self_intersections_skipped" in by_code
    assert "repair.still_open" in by_code, "übersprungene Prüfung und Rest sind zwei Aussagen"
    skipped = by_code["repair.self_intersections_skipped"]
    assert skipped.values["reason"] == "open"
    assert "geschlossenen Modell" in str(skipped.message)
    assert "Kanten verfeinern" not in str(skipped.message)
    assert str(skipped.message) != str(by_code["repair.still_open"].message), (
        "Prüfung übersprungen und Rest offen dürfen sich nicht doppeln"
    )

    # **Und über nichts wird nichts gesagt**: Ein offenes Netz ohne eine
    # Überschneidung bekommt keine Zeile über einen Schritt, der nichts zu
    # tun gehabt hätte — sie schickte den Kunden auf eine Suche.
    quiet = repair(raw("broken_open.stl"), holes=False, self_intersections=True)
    assert "repair.self_intersections_skipped" not in {f.code for f in quiet.findings}
''',
)
path.write_text(text, encoding="utf-8", newline="\n")

path = Path("tests/test_geometry_review.py")
text = path.read_text(encoding="utf-8")
print(text.count('assert filled.values == {"before": before, "after": after}'))
print(text.count('assert filled.values == {"before": before, "after": 0}'))
print("ok")
