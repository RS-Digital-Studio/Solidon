"""Die Skizze als Parametertext (§30.1, §15): runde Reise, strenge Prüfung.

Der Text kann aus einer Projektdatei kommen, also gilt er als fremde Eingabe:
was nicht passt, ist eine :class:`ValidationError` mit einem Satz, nie ein
Traceback. Und weil Maßausdrücke im Text Projektparameter lesen, muss die
Auswertung erfahren können, welche das sind — daran hängt ihr Cache-Schlüssel.
"""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.core.sketch.serialize import (
    sketch_from_text,
    sketch_parameter_references,
    sketch_to_text,
)
from app.core.types import Sketch
from tests.test_sketch import rectangle


def test_a_sketch_survives_the_round_trip() -> None:
    sketch = rectangle()
    assert sketch_from_text(sketch_to_text(sketch)) == sketch


def test_the_references_name_what_the_measures_read() -> None:
    """Der Cache-Schlüssel der Auswertung fragt genau danach (§15)."""
    text = sketch_to_text(rectangle("=@outer/2", "@inner"))
    assert sketch_parameter_references(text) == {"outer", "inner"}


def test_an_unreadable_text_has_no_references() -> None:
    """Ein kaputter Text scheitert in der Op — nicht schon beim Schlüssel."""
    assert sketch_parameter_references("{kaputt") == frozenset()


def test_a_measure_dividing_by_a_parameter_keeps_its_references() -> None:
    """`=@d/@n` galt der Prüfung als Division durch null; der stille Fang
    machte daraus eine leere Referenzmenge, und die Skizze rechnete nach
    einer Parameteränderung mit dem alten Cache weiter (§15)."""
    text = sketch_to_text(rectangle("=@d/@n", "@inner"))
    assert sketch_parameter_references(text) == {"d", "n", "inner"}


def test_a_feature_plane_travels() -> None:
    """§30.1: neben den drei Hauptebenen ist eine erkannte Fläche eine Ebene."""
    sketch = Sketch(plane="feature:top_1", elements=(), constraints=())
    assert sketch_from_text(sketch_to_text(sketch)).plane == "feature:top_1"


def test_a_number_beyond_double_is_not_a_coordinate() -> None:
    """JSON kennt beliebig lange Ganzzahlen, ``float`` nicht — das darf eine
    Meldung sein, kein OverflowError."""
    huge = "1" + "0" * 400
    with pytest.raises(ValidationError):
        sketch_from_text(f'{{"elements": [{{"kind": "point", "points": [[{huge}, 0]]}}]}}')


def test_a_maliciously_deep_text_is_a_sentence_not_a_recursion_error() -> None:
    """Regel 17: auch der Stapelüberlauf des JSON-Parsers wird eine Meldung."""
    with pytest.raises(ValidationError):
        sketch_from_text("[" * 100_000)


@pytest.mark.parametrize(
    "text",
    [
        "{kaputt",
        "[]",
        '{"plane": 3, "elements": []}',
        '{"plane": "plane:zz", "elements": []}',
        '{"plane": "feature:", "elements": []}',
        '{"elements": [{"kind": "hexagon", "points": [[0, 0]]}]}',
        '{"elements": [{"kind": "line"}]}',
        '{"elements": [{"kind": "line", "points": [[0, 0], [true, 1]]}]}',
        '{"elements": [{"kind": "line", "points": [[0, 0], [NaN, 1]]}]}',
        '{"elements": [{"kind": "line", "points": [[0, 0], [1]]}]}',
        '{"elements": [], "constraints": [{"kind": "magnetic", "targets": [0]}]}',
        '{"elements": [], "constraints": [{"kind": "distance", "targets": [0, 1.5]}]}',
        '{"elements": [], "constraints": [{"kind": "distance", "targets": [0, true]}]}',
        '{"elements": [], "constraints": [{"kind": "distance", "targets": [0, 1], "value": 5}]}',
    ],
)
def test_what_does_not_fit_is_rejected_with_a_sentence(text: str) -> None:
    """Auch ``true`` und ``NaN`` sind keine Koordinaten — JSON ließe beide durch."""
    with pytest.raises(ValidationError):
        sketch_from_text(text)
