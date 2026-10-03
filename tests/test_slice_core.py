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

from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.slice import analysis
from app.core.slice.analysis import cross_section, cross_sections, slice_body


@pytest.fixture(autouse=True)
def segment_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Diese Gegenüberstellung fährt wirklich die beiden Segmentwege."""
    monkeypatch.setattr(analysis, "_solid_sections", lambda *_args, **_kwargs: None)


pytestmark = pytest.mark.skipif(
    analysis._chain is None
    or getattr(analysis._chain, "PLANE_SEGMENTS_API", None) != analysis.PLANE_SEGMENTS_API,
    reason="app/core/slice/_chain ist nicht aktuell gebaut (tools/build_slice_core.py)",
)


@pytest.mark.parametrize("angle", [0.0, 0.37, 1.2])
@pytest.mark.parametrize("positions", [[0.0, 1.0, -1.0, 0.5], [], [8.0], [0.5, 0.5]])
def test_native_material_spans_equal_numpy_exactly(
    monkeypatch: pytest.MonkeyPatch, angle: float, positions: list[float]
) -> None:
    """Löcher, Randkontakte, leere und doppelte Lagen behalten dieselben Paritätspaare."""
    native = analysis._chain
    if native is None or not hasattr(native, "cuts_along"):
        pytest.skip("Der native Spannweitenkern ist noch nicht gebaut.")
    outer = np.array([[-3.0, -2.0], [3.0, -2.0], [3.0, 2.0], [-3.0, 2.0]])
    inner = np.array([[-1.0, -1.0], [-1.0, 1.0], [1.0, 1.0], [1.0, -1.0]])
    heads = np.vstack((outer, inner))
    tails = np.vstack((np.roll(outer, -1, axis=0), np.roll(inner, -1, axis=0)))
    direction = np.array([np.cos(angle), np.sin(angle)])
    normal = np.array([-direction[1], direction[0]])
    samples = np.array(positions)
    actual = analysis._cuts_along(heads, tails, direction, normal, samples)
    monkeypatch.setattr(analysis, "_chain", None)
    expected = analysis._cuts_along(heads, tails, direction, normal, samples)
    if expected is None:
        assert actual is None
    else:
        assert actual is not None
        for found, wanted in zip(actual, expected, strict=True):
            np.testing.assert_array_equal(found, wanted)


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

MESHES = Path(__file__).parent / "data" / "meshes"


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
    # Teile als eigene Schalen, die sich überlappen oder ineinanderstecken
    # (RM-485): Hier entscheidet die Umlaufrichtung, und beide Wege müssen sie
    # gleich lesen.
    bars = [
        ((40.0, 10.0, 10.0), (0.0, 15.0, 0.0)),
        ((40.0, 10.0, 10.0), (0.0, -15.0, 0.0)),
        ((10.0, 40.0, 10.0), (15.0, 0.0, 0.0)),
        ((10.0, 40.0, 10.0), (-15.0, 0.0, 0.0)),
    ]
    frame = trimesh.util.concatenate(
        [
            trimesh.creation.box(extents, trimesh.transformations.translation_matrix(centre))
            for extents, centre in bars
        ]
    )
    nested = trimesh.util.concatenate(
        [
            trimesh.creation.box(extents=(20.0, 20.0, 20.0)),
            trimesh.creation.cylinder(radius=3.0, height=10.0, sections=32),
        ]
    )
    enclosing = read_mesh((MESHES / "parts_enclosing_air.stl").read_bytes(), ".stl")
    return [
        ("Würfel", MeshData.of(trimesh.creation.box(extents=(20.0, 30.0, 10.0)))),
        ("Rohr", MeshData.of(tube)),
        ("Lochplatte", MeshData.of(plate)),
        ("zwei Kugeln", MeshData.of(twin)),
        ("Rahmen aus Balken", MeshData.of(frame)),
        ("Teil im Teil", MeshData.of(nested)),
        ("Teile um Luft", normalise(enclosing, "mm").mesh),
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


@pytest.mark.parametrize("first_layer_height", [None, 0.32])
def test_a_bridge_keeps_its_supported_span_on_both_paths(
    monkeypatch: pytest.MonkeyPatch, first_layer_height: float | None
) -> None:
    """Die Auflager des schmalen Stegs bleiben auch ohne übersetzten Kern bekannt."""
    mesh = read_mesh((MESHES / "bridge_two_end_supports.ply").read_bytes(), ".ply")
    compiled = slice_body(mesh, 0.2, first_layer_height=first_layer_height)
    monkeypatch.setattr(analysis, "_chain", None)
    geos = slice_body(mesh, 0.2, first_layer_height=first_layer_height)

    assert max(layer.bridge_width for layer in compiled.layers) == pytest.approx(30.0, abs=0.2)
    assert [layer.bridge_width for layer in compiled.layers] == pytest.approx(
        [layer.bridge_width for layer in geos.layers], abs=_ULP
    )


def test_the_compiled_way_is_the_one_that_ran() -> None:
    """Ein Wächter für die Prüfung selbst.

    Ohne ihn bewiese ein grüner Lauf oben nichts: Griffe der übersetzte Weg
    nie, verglichen die Tests GEOS mit GEOS.
    """
    mesh = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    points, _layers, nodes = analysis._plane_segments(mesh, np.array([0.0]))
    assert len(points), "the plane must cut this box"
    assert analysis._rings_from(points, nodes) is not None, "the compiled way declined a clean cut"


class _CancelOnCall:
    """Bricht deterministisch bei einer bestimmten Abbruchprüfung ab."""

    def __init__(self, call: int) -> None:
        self.call = call
        self.asked = 0

    @property
    def is_cancelled(self) -> bool:
        return self.asked >= self.call

    def raise_if_cancelled(self) -> None:
        self.asked += 1
        if self.asked >= self.call:
            raise OperationCancelled


class _NeverCancel:
    """Zählt Fragen, ohne den Lauf zu verändern."""

    def __init__(self) -> None:
        self.asked = 0

    @property
    def is_cancelled(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        self.asked += 1


def test_the_compiled_face_work_can_be_cancelled_from_inside() -> None:
    """Die Abbruchprüfung liegt im nativen Flächenlauf, nicht nur davor."""
    mesh = MeshData.of(trimesh.creation.icosphere(subdivisions=6, radius=20.0))
    token = _CancelOnCall(4)

    with pytest.raises(OperationCancelled):
        slice_body(mesh, 0.2, detail="support", cancelled=token)

    assert token.asked == 4, "the fourth check is inside the compiled face loop"


def test_the_numpy_face_work_can_be_cancelled_between_chunks(
    without_compiled_core: None,
) -> None:
    """Auch die optionale Rückfallkette hält nicht bis zum Gesamtschnitt fest."""
    mesh = MeshData.of(trimesh.creation.icosphere(subdivisions=6, radius=20.0))
    token = _CancelOnCall(4)

    with pytest.raises(OperationCancelled):
        slice_body(mesh, 0.2, detail="support", cancelled=token)

    assert token.asked == 4, "the fourth check follows the first NumPy face chunk"


def test_a_cancellable_cut_keeps_the_same_segments_on_both_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aufteilen für Abbruchfähigkeit ändert weder Reihenfolge noch Punkte."""
    mesh = MeshData.of(trimesh.creation.icosphere(subdivisions=5, radius=20.0))
    heights = np.linspace(-19.8, 19.8, 41)
    compiled_token = _NeverCancel()
    compiled = analysis._plane_segments(mesh, heights, cancelled=compiled_token)

    monkeypatch.setattr(analysis, "_chain", None)
    fallback_token = _NeverCancel()
    fallback = analysis._plane_segments(mesh, heights, cancelled=fallback_token)

    assert compiled_token.asked > 1, "the compiled loop itself asks"
    assert fallback_token.asked > 1, "the fallback chunks ask"
    np.testing.assert_array_equal(compiled[1], fallback[1], err_msg="layers")
    np.testing.assert_array_equal(compiled[2], fallback[2], err_msg="edges")
    np.testing.assert_array_equal(
        np.round(compiled[0], 6), np.round(fallback[0], 6), err_msg="points"
    )


def test_a_token_that_never_cancels_changes_no_analysis_number() -> None:
    """Der neue Vertrag ist wirkungslos, solange niemand abbricht."""
    mesh = MeshData.of(trimesh.creation.cone(radius=15.0, height=30.0, sections=48))
    expected = slice_body(mesh, 0.5)
    token = _NeverCancel()

    actual = slice_body(mesh, 0.5, cancelled=token)

    assert token.asked > len(actual.layers), "the expensive phases ask too"
    assert actual == expected


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


def test_a_ring_through_a_vertex_uses_the_loose_segments() -> None:
    """Eine Fläche mit einer auslaufenden Schwalbenschwanzkante bleibt erhalten.

    Auf z = 9,5 trifft die Ebene die Spitze des angesetzten Keils. Dessen
    Rand läuft auf derselben Linie vor und zurück; zusammen mit dem Quader
    ist die topologisch verkettete Kontur deshalb selbstschneidend. Die losen
    Segmente ergeben eindeutig den 40 × 20-mm-Querschnitt des Quaders.

    Genau diese Schicht fehlte am ersten rechten Teil von CORE-31. Die nächste
    sah dadurch wie eine Insel aus und machte aus 84,0 mm³ Stützraum 905,0.
    """
    mesh = read_mesh((MESHES / "dovetail_vertex_plane.ply").read_bytes(), ".ply")
    assert mesh.is_watertight
    assert mesh.component_count == 1

    compiled_section = cross_section(mesh, 9.5)
    compiled = slice_body(mesh, 1.0, detail="support")
    saved = analysis._chain
    try:
        analysis._chain = None
        geos_section = cross_section(mesh, 9.5)
        geos = slice_body(mesh, 1.0, detail="support")
    finally:
        analysis._chain = saved

    assert compiled_section is not None
    assert geos_section is not None
    assert geos_section.area == pytest.approx(800.0)
    assert compiled_section.area == pytest.approx(geos_section.area)
    assert [layer.z for layer in compiled.layers] == [layer.z for layer in geos.layers]
    assert geos.support_volume == pytest.approx(84.0)
    assert compiled.support_volume == pytest.approx(geos.support_volume)


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


def test_widths_and_tapers_do_not_depend_on_where_a_ring_starts() -> None:
    """Ein Rohr mit versetzter Bohrung: die Wand läuft von 1,5 auf 4,5 mm —
    ein Keil über den ganzen Umfang.

    Der übersetzte Weg beginnt einen Ring an seiner ersten Kante, GEOS an
    einer eigenen. Die Breitensuche vereinfacht die Kontur mit
    Douglas-Peucker, der Keil tastet sie alle Millimeter ab dem Anfangspunkt
    ab — beides hing am Anfangspunkt, und am Stand vor dem 23.09.2026 meldete
    dieselbe Schicht auf dem einen Weg 62 mm Keil und auf dem anderen 60.
    Jetzt wird vor beiden Fragen geordnet (``analysis._canonical``).
    """
    outer = trimesh.creation.cylinder(radius=15.0, height=20.0, sections=64)
    inner = trimesh.creation.cylinder(radius=12.0, height=24.0, sections=48)
    inner.apply_translation((1.5, 0.0, 0.0))
    tube = trimesh.boolean.difference([outer, inner])
    tube.apply_translation((0.0, 0.0, 10.0))
    mesh = MeshData.of(tube)

    compiled = slice_body(mesh, 0.5)
    saved = analysis._chain
    try:
        analysis._chain = None
        geos = slice_body(mesh, 0.5)
    finally:
        analysis._chain = saved

    assert [layer.taper_length for layer in compiled.layers] == [
        layer.taper_length for layer in geos.layers
    ]
    assert [layer.min_width for layer in compiled.layers] == [
        layer.min_width for layer in geos.layers
    ]
    assert any(layer.taper_length > 0.0 for layer in compiled.layers), "der Keil ist da"


def test_native_ring_nesting_proves_the_containment_tree() -> None:
    """Loch, Insel im Loch und zweite Hülle haben dieselbe eindeutige Elternschaft."""
    rings = [
        np.array([[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]]),
        np.array([[2.0, 2.0], [2.0, 18.0], [18.0, 18.0], [18.0, 2.0]]),
        np.array([[4.0, 4.0], [6.0, 4.0], [6.0, 6.0], [4.0, 6.0]]),
        np.array([[30.0, 0.0], [40.0, 0.0], [40.0, 10.0], [30.0, 10.0]]),
    ]
    metadata = analysis._chain.ring_nesting(np.vstack(rings), np.repeat(np.arange(4), 4))
    assert metadata is not None
    starts, ends, areas, depths, parents = metadata
    np.testing.assert_array_equal(starts, [0, 4, 8, 12])
    np.testing.assert_array_equal(ends, [4, 8, 12, 16])
    np.testing.assert_array_equal(areas > 0, [True, False, True, True])
    np.testing.assert_array_equal(depths, [0, 1, 2, 0])
    np.testing.assert_array_equal(parents, [-1, 0, 1, -1])


@pytest.mark.parametrize("offset", [0.0, 1e-14, -1e-14])
def test_native_ring_nesting_leaves_uncertain_contacts_to_geos(offset: float) -> None:
    """Auf oder numerisch direkt neben der Kante wird keine Elternschaft geraten."""
    outer = np.array([[0.0, 0.0], [10.0, 10.0], [0.0, 20.0], [-10.0, 10.0]])
    inner = np.array([[5.0 + offset, 5.0], [4.0, 6.0], [5.0, 7.0], [6.0, 6.0]])
    assert (
        analysis._chain.ring_nesting(np.vstack((outer, inner)), np.repeat(np.arange(2), 4)) is None
    )


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("capture", [False, True])
def test_native_and_geos_nested_rings_keep_every_contour(
    monkeypatch: pytest.MonkeyPatch, directed: bool, capture: bool
) -> None:
    """Verschachtelte, getrennte, berührende und kreuzende Ringe behalten ihren Rückweg."""
    from shapely import affinity
    from shapely.geometry import Polygon

    outer = Polygon([(0, 0), (12, 0), (12, 10), (0, 10)])
    sources = [
        [outer, affinity.scale(outer, xfact=0.6, yfact=0.6)],
        [outer, affinity.translate(outer, xoff=20)],
        [outer, affinity.translate(outer, xoff=12)],
        [outer, affinity.translate(outer, xoff=6)],
        [
            outer,
            affinity.scale(outer, xfact=0.2, yfact=0.2),
            affinity.scale(outer, xfact=0.6, yfact=0.6),
        ],
        [Polygon([(0, 0), (10, 10), (0, 10), (10, 0)]), outer],
    ]
    native = analysis._chain
    for shapes in sources:
        for shift in (0.0, 1e8):
            rings = [np.asarray(shape.exterior.coords)[:-1] + shift for shape in shapes]
            coordinates = np.vstack(rings)
            ring_of = np.repeat(np.arange(len(rings)), [len(ring) for ring in rings])
            monkeypatch.setattr(analysis, "_chain", native)
            found = analysis._nested(
                coordinates, ring_of, capture_contours=capture, directed=directed
            )
            monkeypatch.setattr(analysis, "_chain", None)
            wanted = analysis._nested(
                coordinates, ring_of, capture_contours=capture, directed=directed
            )
            if wanted is None:
                assert found is None
            else:
                assert found is not None
                assert found[0].wkb == wanted[0].wkb
                assert found[1] == wanted[1]


@pytest.mark.parametrize("case", ["empty", "many", "gap", "short", "negative", "nan", "overflow"])
def test_native_ring_nesting_declines_unproved_input(case: str) -> None:
    """Keine festen Hilfspuffer mit ungültigen Indizes oder ungesicherten Zahlen benutzen."""
    coordinates = np.array([[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]])
    ring_of = np.zeros(4, dtype=np.int64)
    if case == "empty":
        coordinates, ring_of = coordinates[:0], ring_of[:0]
    elif case == "many":
        coordinates = np.tile(coordinates, (17, 1))
        ring_of = np.repeat(np.arange(17), 4)
    elif case == "gap":
        ring_of[:] = 1
    elif case == "short":
        coordinates, ring_of = coordinates[:2], ring_of[:2]
    elif case == "negative":
        ring_of[:] = -1
    elif case == "nan":
        coordinates[0, 0] = np.nan
    else:
        coordinates *= 1e200
    assert analysis._chain.ring_nesting(coordinates, ring_of) is None


def test_native_ring_nesting_checks_dimensions_before_reading() -> None:
    """Ein falsches Koordinatenfeld wird vor dem nativen Zugriff zurückgewiesen."""
    with pytest.raises(ValueError, match="zweidimensionalen"):
        analysis._chain.ring_nesting(np.zeros((4, 1)), np.zeros(4, dtype=np.int64))
    with pytest.raises(ValueError, match="Ringkennung"):
        analysis._chain.ring_nesting(np.zeros((4, 2)), np.zeros(3, dtype=np.int64))


def test_unioned_clip_rings_use_the_proved_tree_without_a_second_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auch die Stützsäule übernimmt die belegte Loch-/Inselhierarchie unmittelbar."""
    import shapely

    rings = [
        np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]),
        np.array([[1.0, 1.0], [1.0, 9.0], [9.0, 9.0], [9.0, 1.0]]),
        np.array([[3.0, 3.0], [5.0, 3.0], [5.0, 5.0], [3.0, 5.0]]),
    ]

    def unexpected_index(*args: object, **kwargs: object) -> None:
        pytest.fail("Die eindeutige Ringhierarchie wird erneut über einen Index gesucht.")

    monkeypatch.setattr(shapely, "STRtree", unexpected_index)
    shape = analysis._shape_from_rings(rings)
    assert shape is not None and shape.is_valid
    assert shape.area == pytest.approx(40.0)
    assert len(shape.geoms) == 2
    assert len(shape.geoms[0].interiors) == 1


@pytest.mark.parametrize("shift", [0.0, 1e8])
def test_unioned_clip_rings_keep_the_previous_exact_geometry(
    monkeypatch: pytest.MonkeyPatch,
    shift: float,
) -> None:
    """Weder Lochzuordnung noch Anfang und Umlaufsinn bereits vereinigter Ringe ändern sich."""
    from shapely.geometry import Polygon

    native = analysis._chain
    for hole in ([[(1, 1), (1, 9), (9, 9), (9, 1)]], []):
        shape = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], hole)
        material = analysis._material_cross(shape)
        rings = [np.asarray(ring) + shift for ring in material.to_polygons()]
        monkeypatch.setattr(analysis, "_chain", native)
        found = analysis._shape_from_rings(rings)
        monkeypatch.setattr(analysis, "_chain", None)
        wanted = analysis._shape_from_rings(rings)
        assert wanted is not None and found is not None
        assert wanted.wkb == found.wkb
