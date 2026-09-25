"""Einmalig: test_geometry_review und test_maps an die neuen Befunde."""

from pathlib import Path

path = Path("tests/test_geometry_review.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str) -> None:
    global text
    assert text.count(old) == 1, old[:80]
    text = text.replace(old, new, 1)


swap(
    '''    assert filled.values == {"before": before, "after": after}
    assert (
        str(filled.message)
        == f"{before - after} von {before} offenen Kanten geschlossen; {after} bleiben offen."
    )
''',
    '''    # Gezählt werden Stellen, nicht Randkanten: zwei Ringe, zwei Löcher. Die
    # Kanten bleiben in den Werten für den Tooltip.
    assert filled.values == {"holes": 2, "before": before, "after": after}
    assert str(filled.message) == "2 Löcher wurden geschlossen."
''',
)
swap(
    '''    assert filled.values == {"before": before, "after": 0}
    assert (
        str(filled.message) == f"{before} von {before} offenen Kanten geschlossen; 0 bleiben offen."
    )
''',
    '''    assert filled.values == {"holes": 1, "before": before, "after": 0}
    assert str(filled.message) == "Ein Loch wurde geschlossen."
''',
)
swap(
    '''    Der Ringfüller schließt jetzt beide. Der Bericht sagt damit zweierlei: wie
    viele Kanten geschlossen wurden, und dass eine der Öffnungen groß genug''',
    '''    Der Ringfüller schließt jetzt beide. Der Bericht sagt damit zweierlei: wie
    viele Löcher geschlossen wurden, und dass eine der Öffnungen groß genug''',
)
path.write_text(text, encoding="utf-8", newline="\n")

path = Path("tests/test_maps.py")
text = path.read_text(encoding="utf-8")
assert text.count('monkeypatch.setattr(repair, "MAX_INTERSECTION_PAIRS", 0)') == 2
text = text.replace(
    'monkeypatch.setattr(repair, "MAX_INTERSECTION_PAIRS", 0)',
    'monkeypatch.setattr(repair, "intersection_budget", lambda _triangles: 0)',
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
