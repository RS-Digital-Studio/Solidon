"""Was ein Dialog vorn sagt, passt zu dem, was davor stand (FD-112, FD-119).

Ohne Fenster: Gefragt werden Register und Kataloge, aus denen der Dialog seine
Beschriftungen und seinen ersten Satz baut.
"""

from __future__ import annotations

from app.core import bootstrap
from app.core.registry import REGISTRY
from app.i18n import tr


def test_no_field_is_named_like_the_place_line_in_front() -> None:
    """FD-119: Am Prüfstück hießen die Lesezeile vorn und die Auswahl darunter
    beide „Stelle“ — welches Feld legt die Stelle fest? Eine Beschriftung steht
    nur einmal im Dialog (``fenster.md``, „Formulare“)."""
    from app.ui.op_dialog import place_fields

    bootstrap.load_operations()
    place = str(tr("Stelle"))
    clashing = sorted(
        spec.name
        for spec in REGISTRY.all()
        if place_fields(spec) is not None
        and any(str(entry.title) == place for entry in spec.params.spec())
    )
    assert clashing == [], f"Feld „Stelle“ neben der Lesezeile „Stelle“: {clashing}"
