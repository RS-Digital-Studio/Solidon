"""Der übersetzte Weg und der über GEOS müssen dasselbe rechnen (§22.1, §31).

``app/core/slice/_chain.pyx`` ist optional: gebaut wird es mit
``tools/build_slice_core.py``, und ohne es geht jeder Schnitt über
``shapely.polygonize``. Zwei Wege durch dieselbe Rechnung sind eine Einladung
zum Auseinanderdriften — und weil der eine übersetzt ist, fiele es niemandem
beim Lesen auf. Diese Datei hält sie aneinander.

Übersprungen wird, was nicht gebaut ist. Das ist kein Schlupfloch: die CI baut
es, und ohne das Modul prüft die restliche Suite ohnehin genau den Weg, gegen
den hier verglichen würde.

**Verglichen wird exakt, und das ist die Lehre aus einem Fehlschlag.** Die
Verkettung *könnte* genauer sein als GEOS — sie kennt die Kante, auf der ein
Punkt liegt, und bräuchte das Runden auf sechs Nachkommastellen nicht. Der
erste Anlauf hat das ausgenutzt, und diese Datei hat es durchgelassen, weil
sie nur Flächen und Löcher auf ``rel=1e-6`` verglich.

Gekostet hat es `test_evaluation.py`: `compensate_elephant_foot` zieht den
Querschnitt mit ``buffer`` ein, extrudiert die Differenz und schneidet sie ab
— und eine Boolesche Operation macht aus einer Abweichung in der **neunten**
Stelle eine andere Topologie. An einem ausgehöhlten Quader kamen 17 erkannte
Merkmale heraus statt 14, darunter ein Stift, den es nicht gibt, und die
Mehrdeutigkeit, an der die Auswertung anhalten sollte, verschwand.

Deshalb rundet die Verkettung jetzt genauso, und deshalb steht hier ``==``
statt ``approx``. Der übersetzte Weg ist der schnellere, nicht der genauere.
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData
from app.core.slice import analysis
from app.core.slice.analysis import cross_section, cross_sections, slice_body

pytestmark = pytest.mark.skipif(
    analysis._chain is None or not hasattr(analysis._chain, "plane_segments"),
    reason="app/core/slice/_chain ist nicht aktuell gebaut (tools/build_slice_core.py)",
)


@pytest.fixture
def without_compiled_core(monkeypatch: pytest.MonkeyPatch) -> None:
    """Derselbe Lauf, aber über GEOS — als wäre nie etwas übersetzt worden."""
    monkeypatch.setattr(analysis, "_chain", None)


#: Wie weit zwei Flächen auseinanderliegen dürfen, ohne dass es Geometrie ist.
#:
#: Die Punkte sind identisch — das prüft
#: :func:`test_the_coordinates_themselves_are_identical` und darauf kommt es
#: an. Verschieden ist nur, an welchem Punkt ein geschlossener Ring anfängt;
#: den sucht sich GEOS selbst. Die Flächenformel summiert dadurch in anderer
#: Reihenfolge, und das kostet die letzte Stelle: 27,572151919908 gegen
#: 27,572151919908002. Ein Millionstel Toleranz wäre hier falsch — es hat
#: genau den Fehler durchgelassen, für den es diese Datei gibt.
_ULP = 1e-12


def _holes(shape: object) -> int:
    """Wie viele Innenringe eine Schicht hat — über beide Geometriearten."""
    parts = getattr(shape, "geoms", None)
    if parts is not None:
        return sum(_holes(part) for part in parts)
    return len(getattr(shape, "interiors", ()))


def bodies() -> list[tuple[str, MeshData]]:
    """Körper, deren Querschnitte verschiedene Fälle treffen.

    Der Würfel ist der einfache Ring, das Rohr eines mit Loch, die Lochplatte
    mehrere Löcher nebeneinander, und die zwei Kugeln zerfallen in getrennte
    Konturen — der Fall, an dem sich Außen- und Innenring nicht mehr an der
    Zahl unterscheiden lassen.
    """
    tube = trimesh.creation.annulus(r_min=4.0, r_max=10.0, height=20.0)
    twin = trimesh.util.concatenate(
        [
            trimesh.creation.icosphere(subdivisions=3, radius=8.0).apply_translation(
                (-12.0, 0.0, 0.0)
            ),
            trimesh.creation.icosphere(subdivisions=3, radius=8.0).apply_translation(
                (12.0, 0.0, 0.0)
            ),
        ]
    )
    plate = trimesh.creation.box(extents=(40.0, 40.0, 6.0))
    for x in (-12.0, 0.0, 12.0):
        hole = trimesh.creation.cylinder(radius=3.0, height=20.0)
        hole.apply_translation((x, 0.0, 0.0))
        plate = trimesh.boolean.difference([plate, hole])
    return [
        ("Würfel", MeshData.of(trimesh.creation.box(extents=(20.0, 30.0, 10.0)))),
        ("Rohr", MeshData.of(tube)),
        ("Lochplatte", MeshData.of(plate)),
        ("zwei Kugeln", MeshData.of(twin)),
    ]


@pytest.mark.parametrize(
    "name,mesh", bodies(), ids=lambda value: value if isinstance(value, str) else ""
)
def test_both_ways_agree_on_every_layer(
    name: str, mesh: MeshData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fläche, Löcher und Konturzahl je Schicht, beide Wege gegeneinander."""
    low = float(mesh.bounds.minimum[2])
    high = float(mesh.bounds.maximum[2])
    heights = np.linspace(low + 0.3, high - 0.3, 25)

    compiled = cross_sections(mesh, heights)
    monkeypatch.setattr(analysis, "_chain", None)
    geos = cross_sections(mesh, heights)

    assert len(compiled) == len(geos)
    for index, (first, second) in enumerate(zip(compiled, geos, strict=True)):
        assert (first is None) == (second is None), f"{name}: layer {index} exists on one way only"
        if first is None or second is None:
            continue
        assert first.area == pytest.approx(second.area, rel=_ULP), (
            f"{name}: layer {index} differs in area"
        )
        assert first.geom_type == second.geom_type, f"{name}: layer {index} differs in shape kind"
        # Die Löcher zählen, nicht nur die Fläche: ein verlorener Innenring
        # ändert die Fläche um wenig und die Aussage über das Teil um viel.
        assert _holes(first) == _holes(second), f"{name}: layer {index} differs in holes"


def test_the_compiled_way_is_the_one_that_ran() -> None:
    """Ein Wächter für die Prüfung selbst.

    Ohne ihn bewiese ein grüner Lauf oben nichts: Griffe der übersetzte Weg
    nie, verglichen die Tests GEOS mit GEOS.
    """
    mesh = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    points, _layers, nodes = analysis._plane_segments(mesh, np.array([0.0]))
    assert len(points), "the plane must cut this box"
    assert analysis._rings_from(points, nodes) is not None, "the compiled way declined a clean cut"


@pytest.mark.parametrize(
    "name,mesh", bodies(), ids=lambda value: value if isinstance(value, str) else ""
)
def test_compiled_plane_segments_match_the_numpy_fallback(
    name: str, mesh: MeshData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der schnellere Schnitt darf weder eine Fläche noch eine Kante versetzen.

    Kanten- und Schichtnummern sind diskret und deshalb exakt. Die Punkte
    werden vor dem Polygonaufbau ohnehin auf sechs Stellen gerundet; genau
    diese Eingabe muss auf beiden Wegen bitgleich sein.
    """
    low = float(mesh.bounds.minimum[2])
    high = float(mesh.bounds.maximum[2])
    heights = np.linspace(low - 0.1, high + 0.1, 31)

    compiled = analysis._plane_segments(mesh, heights)
    monkeypatch.setattr(analysis, "_chain", None)
    fallback = analysis._plane_segments(mesh, heights)

    np.testing.assert_array_equal(compiled[1], fallback[1], err_msg=f"{name}: layers")
    np.testing.assert_array_equal(compiled[2], fallback[2], err_msg=f"{name}: edges")
    np.testing.assert_array_equal(
        np.round(compiled[0], 6), np.round(fallback[0], 6), err_msg=f"{name}: points"
    )


def test_an_open_mesh_falls_back_instead_of_guessing(without_compiled_core: None) -> None:
    """Eine offene Kante trägt nur ein Dreieck — der Grad ist eins, nicht zwei.

    Die Verkettung muss das erkennen und abgeben, statt einen Ring zu erfinden.
    Geprüft wird über das Ergebnis: der Schnitt kommt trotzdem heraus.
    """
    open_box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    open_box.faces = open_box.faces[:-2]
    mesh = MeshData.of(open_box)
    points, _layers, nodes = analysis._plane_segments(mesh, np.array([0.0]))
    assert analysis._rings_from(points, nodes) is None, "an open mesh must not chain"


def test_a_node_with_four_segments_is_not_split_into_two_false_nodes() -> None:
    """Zwei Ringe an demselben Knoten haben Grad vier, nicht zweimal Grad zwei.

    Der schnelle Weg paart sortierte Enden. Ohne die Prüfung zwischen zwei
    Paaren sähen vier gleiche Knotennummern wie zwei unabhängige Knoten aus;
    die Verkettung erfände zwei gültige Konturen aus einer mehrdeutigen.
    """
    nodes = np.array(((0, 1), (1, 2), (2, 0), (0, 3), (3, 4), (4, 0)), dtype=np.int64)
    points = np.zeros((len(nodes), 2, 2), dtype=np.float64)

    assert analysis._rings_from(points, nodes) is None


def test_the_cached_single_ring_is_the_public_contour_bit_for_bit() -> None:
    """Die gesparte Rückübersetzung darf weder Start noch Richtung ändern."""
    mesh = MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=8.0))
    result = slice_body(mesh, 0.5)
    heights = np.asarray([layer.z for layer in result.layers], dtype=float)
    sections = cross_sections(mesh, heights)

    for layer, section in zip(result.layers, sections, strict=True):
        assert section is not None
        assert layer.contours == analysis._to_polygons(section)


def test_the_numbers_of_a_whole_analysis_match() -> None:
    """Nicht nur die Konturen — was die Schichtanalyse daraus schließt.

    Fläche und Überhang gehen in die Druckberatung (§22.2); ein Unterschied
    zwischen den Wegen käme dort als anderer Ratschlag heraus.
    """
    mesh = MeshData.of(trimesh.creation.cone(radius=15.0, height=30.0, sections=48))
    compiled = slice_body(mesh, 0.5)
    saved = analysis._chain
    try:
        analysis._chain = None
        geos = slice_body(mesh, 0.5)
    finally:
        analysis._chain = saved

    assert len(compiled.layers) == len(geos.layers)
    for index, (first, second) in enumerate(zip(compiled.layers, geos.layers, strict=True)):
        assert first.area == pytest.approx(second.area, rel=_ULP), f"layer {index}: area"
        assert first.overhang_area == pytest.approx(second.overhang_area, rel=_ULP, abs=1e-12), (
            f"layer {index}: overhang"
        )


def test_a_single_section_matches_too() -> None:
    """``cross_section`` geht denselben Weg — mit einer Höhe statt vierhundert."""
    mesh = MeshData.of(trimesh.creation.annulus(r_min=3.0, r_max=9.0, height=12.0))
    compiled = cross_section(mesh, 0.0)
    saved = analysis._chain
    try:
        analysis._chain = None
        geos = cross_section(mesh, 0.0)
    finally:
        analysis._chain = saved

    assert compiled is not None and geos is not None
    assert compiled.area == pytest.approx(geos.area, rel=_ULP)
    assert len(compiled.interiors) == len(geos.interiors) == 1, "the bore must survive both ways"


def test_the_coordinates_themselves_are_identical() -> None:
    """Nicht die Kennzahlen — die Punkte.

    Fläche und Löcher zu vergleichen hat den einen Fehler durchgelassen, den
    es hier zu verhindern gilt: Ein Querschnitt, der um 10⁻⁹ abweicht, hat
    dieselbe Fläche und dieselbe Zahl Löcher, und trotzdem kommt hinter einer
    Booleschen Operation ein anderer Körper heraus. Verglichen wird deshalb,
    woraus die Kennzahlen entstehen.
    """
    mesh = MeshData.of(trimesh.creation.cylinder(radius=11.0, height=20.0, sections=37))
    compiled = cross_section(mesh, 0.0)
    saved = analysis._chain
    try:
        analysis._chain = None
        geos = cross_section(mesh, 0.0)
    finally:
        analysis._chain = saved

    assert compiled is not None and geos is not None
    first = np.asarray(compiled.exterior.coords)
    second = np.asarray(geos.exterior.coords)
    # Der Anfangspunkt eines geschlossenen Rings ist willkürlich; die Menge
    # der Punkte ist es nicht.
    assert first.shape == second.shape, "the two ways disagree on how many points a ring has"
    assert np.array_equal(np.sort(first, axis=0), np.sort(second, axis=0)), (
        "the two ways put the ring in different places"
    )
