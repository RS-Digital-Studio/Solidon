"""Prüfpunkt Käfigmodellierung (Konzept P16.11, Entscheidung H2).

Die Frage ist alt und wird hier zum ersten Mal messbar: Braucht Solidon einen
Käfigeditor — Vertex-, Kanten- und Flächenauswahl, Extrudieren, Schleifen,
Messerschnitt —, um die grobe Form zu bauen, auf der später geformt wird? Das
wäre eine ganze Phase, so groß wie der Skizzeneditor.

Entscheidung H2 sagt: wahrscheinlich nicht, weil es dafür bereits einen Weg
gibt, der zur Architektur passt — Primitive plus `blend_union`, unser
Gegenstück zu ZSpheres und Dynamesh. Drei Zahlen statt hundert Vertices, und
alles davon im Stapel änderbar.

**Das Kriterium steht hier, bevor P16.5 beginnt**, damit es hinterher nicht
passend gemacht wird. Fünf Bedingungen, vier davon schon heute prüfbar:

1. Die Figur ist ein Körper — wasserdicht, eine Komponente, ohne Löcher.
2. Sie entsteht in höchstens fünfzehn Schritten.
3. Gleichmäßig vernetzt streuen ihre Kanten unter 0,5 — sonst wirkt ein
   Pinsel an verschiedenen Stellen verschieden.
4. Ihre Maße sind Zahlen: Ein längerer Arm ist eine Parameteränderung, kein
   neuer Aufbau.
5. *(erst mit P16.5 prüfbar)* Der Pinsel bringt sie von der groben Form zur
   Figur, ohne dass Topologie fehlt.

Reißt eine der ersten vier, kommt der Käfig — und dann als eigene Phase mit
eigenem Konzept, nicht als Anhängsel.
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from app.core.geom.blend import blend_bodies
from app.core.geom.mesh import MeshData
from app.core.geom.mesh_ops import edge_lengths, uniform

#: Wie viele Schritte eine Grundfigur höchstens kosten darf. Darüber ist der
#: Weg über Primitive keiner mehr — dann klickt man länger, als ein Käfig
#: gekostet hätte.
MAX_STEPS = 15

#: Wie ungleichmäßig die Kanten nach dem gleichmäßigen Vernetzen noch sein
#: dürfen. Derselbe Wert, den `remesh_uniform` an `plate_holes` erreicht.
MAX_SPREAD = 0.5


def limb(length: float, thickness: float, at: tuple[float, float, float], along: str) -> MeshData:
    """Ein Glied: Zylinder mit Kugel am Ende, wie eine ZSphere-Kette."""
    body = trimesh.creation.cylinder(radius=thickness / 2.0, height=length, sections=32)
    if along == "x":
        body.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0]))
    body.apply_translation(at)
    return MeshData.of(body)


def figure() -> tuple[MeshData, int]:
    """Eine humanoide Grundfigur aus Primitiven und weichen Vereinigungen.

    Rumpf, Kopf, zwei Arme, zwei Beine — sechs Grundformen, fünf
    Verschmelzungen. Das ist der Aufbau, den Entscheidung H2 dem Käfig
    entgegenhält, und hier steht er als Rechnung statt als Behauptung.
    """
    steps = 0
    torso = MeshData.of(trimesh.creation.box(extents=(24.0, 14.0, 40.0)))
    steps += 1

    head = trimesh.creation.icosphere(subdivisions=2, radius=9.0)
    head.apply_translation((0.0, 0.0, 28.0))
    steps += 1

    parts = [MeshData.of(head)]
    for side in (-1.0, 1.0):
        parts.append(limb(22.0, 7.0, (side * 22.0, 0.0, 12.0), "x"))
        parts.append(limb(30.0, 9.0, (side * 7.0, 0.0, -32.0), "z"))
        steps += 2

    merged = torso
    for part in parts:
        merged = blend_bodies(merged, part, 4.0, 1.2)
        steps += 1
    return merged, steps


@pytest.mark.slow
def test_a_base_figure_comes_out_as_one_closed_body() -> None:
    """Bedingung 1: Was aus dem Aufbau fällt, muss ein Körper sein.

    Ein Basisnetz mit Löchern oder losen Teilen ist keines — der Pinsel
    verschiebt Eckpunkte, er repariert keine Topologie.
    """
    merged, _steps = figure()

    assert merged.is_watertight
    assert merged.component_count == 1
    assert merged.volume > 0.0
    # Ohne Löcher: eine geschlossene Fläche vom Geschlecht null hat die
    # Euler-Charakteristik zwei. Ein Griff oder Tunnel im Basisnetz wäre eine
    # Absicht, die niemand geäußert hat.
    body = merged.raw
    euler = len(body.vertices) - len(body.edges_unique) + len(body.faces)
    assert euler == 2, f"Euler-Charakteristik {euler} — die Form hat einen Durchgang"


@pytest.mark.slow
def test_a_base_figure_costs_at_most_fifteen_steps() -> None:
    """Bedingung 2: Der Weg über Primitive muss kürzer sein als ein Käfig.

    Sechs Grundformen und fünf Verschmelzungen sind elf Schritte. Wären es
    vierzig, hätte H2 unrecht — dann klickt man länger, als ein Käfigeditor
    gekostet hätte, und das Argument gegen ihn fällt.
    """
    _merged, steps = figure()

    assert steps <= MAX_STEPS


@pytest.mark.slow
def test_a_base_figure_takes_an_even_mesh() -> None:
    """Bedingung 3: Der Pinsel braucht überall dieselbe Vertexdichte.

    Aus dem Raster kommt ein Netz mit ungleichen Dreiecken; ob es sich
    gleichmäßig vernetzen lässt, entscheidet, ob darauf geformt werden kann.
    """
    merged, _steps = figure()

    evened = uniform(merged, 1.5, 0.0)

    lengths = edge_lengths(evened)
    spread = float(lengths.std() / np.median(lengths))
    assert spread < MAX_SPREAD, f"Kantenstreuung {spread:.3f} — der Pinsel wirkt ungleichmäßig"
    assert evened.is_watertight


@pytest.mark.slow
def test_the_figure_changes_by_changing_a_number() -> None:
    """Bedingung 4: der eigentliche Grund, warum Primitive den Käfig schlagen.

    Ein längerer Arm ist hier eine Zahl. In einem Käfig wäre er eine Auswahl,
    ein Zug und eine Hoffnung, dass die Schleifen noch stimmen — und beim
    nächsten Mal wieder. Das ist der Unterschied zwischen einem Modell, das man
    ändert, und einem, das man neu baut.
    """
    torso = MeshData.of(trimesh.creation.box(extents=(24.0, 14.0, 40.0)))

    short = blend_bodies(torso, limb(18.0, 7.0, (20.0, 0.0, 12.0), "x"), 4.0, 1.2)
    long = blend_bodies(torso, limb(30.0, 7.0, (24.0, 0.0, 12.0), "x"), 4.0, 1.2)

    assert long.volume > short.volume
    assert long.bounds.size[0] > short.bounds.size[0]
    assert short.is_watertight and long.is_watertight
