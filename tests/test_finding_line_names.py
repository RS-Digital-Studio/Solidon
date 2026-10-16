"""Die Berichtszeile nennt einen Körper einmal (FD-105, Teil Karten).

Seit F6 tragen Passungsbefunde in ``a``/``b`` die Körpernamen statt der
Kennungen (``scene/fits.py``). ``panels._line_for`` setzte den Namen aus
``object_id`` trotzdem davor: „Zwei Teile überschneiden sich. — Quader ·
Quader · Deckel“. Der Name steht jetzt nur vorn, wo ihn kein Wert der Zeile
schon nennt.
"""

from __future__ import annotations

from app.core.types import Finding
from app.ui.panels import _line_for


def _collision(**values: str) -> Finding:
    return Finding(
        code="fit.collision",
        severity="warning",
        message="Zwei Teile überschneiden sich.",
        object_id="obj_1",
        values=values,
    )


def test_a_body_named_among_the_values_is_not_named_twice() -> None:
    line = _line_for(_collision(a="Quader", b="Deckel"), {"obj_1": "Quader", "obj_2": "Deckel"})

    assert line.count("Quader") == 1, line
    assert "Deckel" in line, line


def test_a_body_without_a_value_keeps_its_name_in_front() -> None:
    """Gegenprobe: Ohne Namen unter den Werten steht der Körper wie bisher vorn."""
    line = _line_for(_collision(), {"obj_1": "Quader"})

    assert line.endswith("— Quader"), line
