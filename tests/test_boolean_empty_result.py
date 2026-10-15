"""Was ein leeres Ergebnis der Booleschen sagt — je Art, je Kette, an beiden Kernen.

Eine Differenz ist leer, wenn das Werkzeug den Körper deckt, eine Schnittmenge,
wenn es ihn verfehlt; eine Vereinigung zweier Körper nie. Den Titel der
schnellen Rechnung trägt nur eine Kette, die die Güte gekürzt hat
(Durchsichten welle4-b und über fix/review-kern).
"""

from __future__ import annotations

from typing import Any

import pytest
import trimesh

from app.core.errors import BooleanFailedError, GeometryError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from tests.test_boolean import box, run_op, solid


@pytest.mark.parametrize(
    ("kind", "said", "offered"),
    [
        ("difference", "deckt ihn vollständig ab", "correct_input"),
        ("intersection", "trifft ihn nicht", "correct_input"),
        ("union", "Reparieren", "repair_and_retry"),
    ],
)
@pytest.mark.parametrize(
    ("stages", "quality"), [(("direct",), "fine"), (("direct", "welded"), "draft"), (None, "fine")]
)
def test_an_empty_result_names_the_cause_its_kind_allows(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    said: str,
    offered: str,
    stages: tuple[str, ...] | None,
    quality: str,
) -> None:
    """Durchsicht welle4-b, L3: „Nichts übrig“ nennt nur, was die Art erklären kann.

    Seit FD-6 bekam jeder Aufruf mit festgelegten Stufen bei leerem Ergebnis
    „das Werkzeug deckt ihn vollständig ab. Prüfen Sie Maß und Lage“ — auch die
    Vereinigung beim Umlaufen einer Textur, die gar kein Werkzeug hat, und die
    Schnittmenge, deren leeres Ergebnis heißt, dass das Werkzeug den Körper
    verfehlt. Eine Vereinigung zweier Körper ist nie leer: Liefert jede Stufe
    nichts, hat der Kern aufgegeben, und *Reparieren* ist der Weg. Dasselbe am
    Ende der vollen Kette.
    """
    from app.core.geom import boolean as boolean_module

    plate = MeshData.of(trimesh.creation.box(extents=(80.0, 50.0, 8.0)))
    tool = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    monkeypatch.setattr(
        boolean_module, "_run_stage", lambda *args, **kwargs: MeshData.of(trimesh.Trimesh())
    )

    with pytest.raises(BooleanFailedError) as caught:
        boolean(kind, [plate, tool], stages=stages, quality=quality)  # type: ignore[arg-type]

    detail = str(caught.value.detail)
    assert said in detail, f"{kind}: {detail!r}"
    assert offered in {action.id for action in caught.value.suggestions}, caught.value.suggestions
    if kind == "union":
        assert "Maß und Lage" not in detail, f"die Vereinigung schickt zu den Maßen: {detail!r}"


@pytest.mark.parametrize(
    ("stages", "quality", "quick"),
    [(("direct",), "fine", False), (("direct", "welded"), "draft", False), (None, "draft", True)],
)
def test_only_a_chain_the_quality_cut_short_is_called_the_quick_one(
    monkeypatch: pytest.MonkeyPatch,
    stages: tuple[str, ...] | None,
    quality: str,
    quick: bool,
) -> None:
    """Der Titel „Mit der schnellen Rechnung …“ gehört der gekürzten Kette.

    Er sagt, dass eine vollständige Rechnung noch folgt. Hat der Aufrufer seine
    Stufen festgelegt, folgt keine (FD-6) — eine leere Vereinigung beim
    Umlaufen einer Textur trug ihn trotzdem, weil der Titel nur fragte, ob die
    Voxelstufe dran war (Durchsicht über fix/review-kern, Beobachtung). Dort
    gilt der Titel der Klasse: Auf keinem Weg, den der Schritt zulässt.
    """
    from app.core.geom import boolean as boolean_module

    plate = MeshData.of(trimesh.creation.box(extents=(80.0, 50.0, 8.0)))
    tool = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    monkeypatch.setattr(
        boolean_module, "_run_stage", lambda *args, **kwargs: MeshData.of(trimesh.Trimesh())
    )

    with pytest.raises(BooleanFailedError) as caught:
        boolean("union", [plate, tool], stages=stages, quality=quality)  # type: ignore[arg-type]

    title = str(caught.value.title)
    assert caught.value.cut_short is quick
    if quick:
        assert "schnellen Rechnung" in title, title
    else:
        assert title == str(BooleanFailedError.default_title), title


def test_an_empty_union_in_the_preview_blames_no_size(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auch in der schnellen Vorschau: Eine leere Vereinigung liegt nie an den Maßen.

    Differenz und Schnittmenge sagen dort, dass erst die vollständige Rechnung
    zwischen Maß und schneller Rechnung entscheidet; die Vereinigung bekommt
    den Satz mit *Reparieren* und bleibt eine gekürzte Kette, die das Fenster
    selbst zu Ende rechnet (``cut_short``).
    """
    from app.core.geom import boolean as boolean_module

    plate = MeshData.of(trimesh.creation.box(extents=(80.0, 50.0, 8.0)))
    tool = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    monkeypatch.setattr(
        boolean_module, "_run_stage", lambda *args, **kwargs: MeshData.of(trimesh.Trimesh())
    )

    caught = {}
    for kind in ("difference", "intersection", "union"):
        with pytest.raises(BooleanFailedError) as error:
            boolean(kind, [plate, tool], quality="draft")  # type: ignore[arg-type]
        caught[kind] = error.value

    for kind in ("difference", "intersection"):
        assert "Rechenstufen" in str(caught[kind].detail), str(caught[kind].detail)
    assert "Reparieren" in str(caught["union"].detail), str(caught["union"].detail)
    assert "Maßen" not in str(caught["union"].detail), str(caught["union"].detail)
    assert all(error.cut_short for error in caught.values()), "das Fenster rechnet selbst weiter"


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_an_empty_intersection_says_one_sentence_on_both_kernels(kernel: str) -> None:
    """*Schnittmenge* zweier getrennter Körper sagt an beiden Kernen denselben Satz.

    Er stand zweimal wörtlich in ``ops._boolean_op``, und den exakten Weg
    prüfte kein Test. Er spricht über die gewählten Körper; ein internes
    Werkzeug, das einen Körper verfehlt, sagt etwas anderes
    (``NOTHING_SHARED_DETAIL``, Durchsicht über fix/review-kern, L6).
    """
    from app.core.geom.boolean import (
        NO_COMMON_PART_DETAIL,
        NO_COMMON_PART_TITLE,
        NOTHING_SHARED_DETAIL,
    )

    if kernel == "brep":
        from tests.helpers import exact_kernel

        exact_kernel()
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.gp import gp_Pnt

        from app.core.brep.kernel import Solid

        first: Any = Solid(
            BRepPrimAPI_MakeBox(gp_Pnt(-10.0, -10.0, -10.0), 20.0, 20.0, 20.0).Shape()
        )
        second: Any = Solid(
            BRepPrimAPI_MakeBox(gp_Pnt(90.0, -10.0, -10.0), 20.0, 20.0, 20.0).Shape()
        )
    else:
        first, second = solid(), box(20.0, (100.0, 0.0, 0.0))

    with pytest.raises(GeometryError) as problem:
        run_op("intersect_objects", first, second)

    assert str(problem.value.title) == str(NO_COMMON_PART_TITLE), problem.value.title
    assert str(problem.value.detail) == str(NO_COMMON_PART_DETAIL), problem.value.detail
    assert str(problem.value.detail) != str(NOTHING_SHARED_DETAIL)
