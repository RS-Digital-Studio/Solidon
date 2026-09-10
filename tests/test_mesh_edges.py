"""Die Kanten eines Netzes — als Züge, mit stabilen Schlüsseln.

Der Grund für dieses Gebiet steht in `app/core/geom/edges.py`: Ein
importiertes Modell soll dieselben Werkzeuge annehmen wie ein selbst
gezeichnetes (Entscheidung Robert, 10.09.2026). Verrunden und Fasen setzen
an einer **Kante** an, und ein Netz hat keine — es hat Dreiecke.

Zwei Zusagen tragen das Ganze, und beide stehen hier:

* Derselbe Schlüssel überlebt eine **Neuvernetzung**. Sonst zeigte er nach
  dem nächsten Schritt auf eine andere Kante, und zwar still.
* Derselbe Schlüssel kommt aus **beiden Kernen**. Sonst müsste alles
  darüber — Anklicken, Beschriftung, der Parameter der Operation — die zwei
  Rechenwege auseinanderhalten.
"""

from __future__ import annotations

import pytest
import trimesh

from app.core.geom.boolean import boolean
from app.core.geom.edges import edge_key, edges_of
from app.core.geom.mesh import MeshData

WIDTH, DEPTH, HEIGHT = 40.0, 30.0, 20.0
RADIUS = 10.0


def block() -> MeshData:
    return MeshData(trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT)))


def test_a_box_has_twelve_edges_and_no_more() -> None:
    """Zwölf Kanten, vier je Länge — und jede genau einmal.

    Die Flächendiagonalen sind keine: Dort knickt nichts. Ohne diese
    Unterscheidung bekäme der Kunde achtzehn Kanten an einem Quader, von
    denen sechs im Bild gar nicht zu sehen sind.
    """
    found = edges_of(block())

    assert len(found) == 12
    assert sorted(round(entry.length, 6) for entry in found) == [
        HEIGHT,
        HEIGHT,
        HEIGHT,
        HEIGHT,
        DEPTH,
        DEPTH,
        DEPTH,
        DEPTH,
        WIDTH,
        WIDTH,
        WIDTH,
        WIDTH,
    ]
    assert all(entry.convex for entry in found), "ein Quader hat nur Außenkanten"
    keys = [edge_key(entry) for entry in found]
    assert len(set(keys)) == len(keys), "zwei Kanten teilen keinen Schlüssel"


def test_a_finer_mesh_keeps_the_same_twelve_keys() -> None:
    """Die Zusage, an der alles hängt: Der Schlüssel überlebt die Vernetzung.

    Ein Netz mit 192 Dreiecken zeigt dieselben zwölf Kanten wie eines mit
    zwölf — **wenn** sie verkettet werden. Ohne die Verkettung wären es
    achtundvierzig Segmente, der Kunde sähe zwölf, und jede Verfeinerung
    änderte jeden Schlüssel.
    """
    coarse = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    fine = coarse.subdivide().subdivide()
    assert len(fine.faces) > len(coarse.faces) * 8, "sonst prüft der Test keine Verfeinerung"

    rough = edges_of(MeshData(coarse))
    dense = edges_of(MeshData(fine))

    assert len(dense) == len(rough) == 12
    assert all(len(entry.points) > 2 for entry in dense), "im feinen Netz ist eine Kante ein Zug"
    assert sorted(edge_key(entry) for entry in dense) == sorted(edge_key(entry) for entry in rough)


def test_both_kernels_name_the_same_edge_the_same_way() -> None:
    """Ein Schlüssel, zwei Kerne — sonst gäbe es zwei Kantenauswahlen.

    Der Quader steht in beiden Fällen an derselben Stelle: Der exakte Kern
    setzt ihn auf ``z = 0``, ``trimesh`` zentriert ihn, also wird das Netz um
    die halbe Höhe angehoben. Was dann noch verschieden wäre, läge an der
    Rechnung und nicht an der Lage.
    """
    brep = pytest.importorskip("app.core.brep.edit")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")

    exact = brep.box(WIDTH, DEPTH, HEIGHT)
    raw = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    raw.apply_translation((0.0, 0.0, HEIGHT / 2.0))

    from_brep = sorted(brep.edge_key(entry) for entry in brep.edges_of(exact))
    from_mesh = sorted(edge_key(entry) for entry in edges_of(MeshData(raw)))

    assert from_brep, "leeres Register des exakten Kerns — dann prüft das nichts"
    assert from_mesh == from_brep

    # **Und der Zylinder ist der Fall, der die beiden auseinandertrieb.**
    # Seine Kanten sind geschlossene Kreise: Der Schwerpunkt liegt auf der
    # Achse, und die Richtung von Anfang zu Ende ist entartet. Zwei Dinge
    # gingen daran schief — ein Mittelpunkt auf halber Weglänge statt im
    # Schwerpunkt, und eine winzige negative Zahl, die sich als „-0.000"
    # schreibt und damit ein anderer Schlüssel ist als „0.000".
    round_exact = brep.cylinder(2.0 * RADIUS, HEIGHT)
    round_raw = trimesh.creation.cylinder(radius=RADIUS, height=HEIGHT, sections=64)
    round_raw.apply_translation((0.0, 0.0, HEIGHT / 2.0))

    circles_brep = sorted(brep.edge_key(entry) for entry in brep.edges_of(round_exact))
    circles_mesh = sorted(edge_key(entry) for entry in edges_of(MeshData(round_raw)))

    assert len(circles_brep) == 2, "ein Zylinder hat zwei Kreiskanten — die Naht zählt nicht"
    assert circles_mesh == circles_brep
    assert not any("-0.000" in key for key in circles_mesh), "eine Null trägt kein Vorzeichen"


def test_a_groove_tells_its_inner_edges_from_its_outer_ones() -> None:
    """Konkav oder konvex — daran hängt, wohin eine Verrundung Material bewegt.

    An einer Außenkante geht welches weg, an einer Innenkante kommt welches
    dazu. Der exakte Kern liest das aus der Topologie; am Netz muss es an der
    Kante stehen, sonst rundet eine Nut nach der falschen Seite.
    """
    plate = MeshData(trimesh.creation.box(extents=(WIDTH, DEPTH, 10.0)))
    cutter = trimesh.creation.box(extents=(10.0, DEPTH + 10.0, 4.0))
    cutter.apply_translation((0.0, 0.0, 5.0))
    grooved = boolean("difference", [plate, MeshData(cutter)], quality="fine").mesh

    found = edges_of(grooved)
    inner = [entry for entry in found if not entry.convex]

    assert len(inner) == 2, "eine durchgehende Nut hat zwei Bodenkanten"
    assert all(round(entry.length, 3) == DEPTH for entry in inner)
    assert len(found) - len(inner) > 10, "und ringsum bleiben die Außenkanten"
