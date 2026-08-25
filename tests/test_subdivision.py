"""Gleichmäßig vernetzen und unterteilen (Konzept P16.3, Bauplan §25).

Zwei Operationen, die dasselbe Wort benutzen und Verschiedenes tun.
``remesh_uniform`` ändert die *Verteilung* der Dreiecke, ohne die Form
anzufassen; ``subdivide_surface`` ändert die *Form*, indem es zwischen den
Dreiecken interpoliert. Beide sind die Vorstufe des Sculptings — ein Pinsel
verschiebt Eckpunkte, und wo keine sind, entsteht keine Falte.

Die interessanteste Zahl dieser Datei steht in
``test_uniform_remeshing_costs_a_fraction_of_the_triangles``. Sie ist der
ganze Grund, warum ``remesh_uniform`` neben ``remesh_mesh`` steht und nicht
darin.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import NotManifoldError, ValidationError
from app.core.geom import mesh_ops
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, OpResult, Profile, Quality, Scene, SceneObject

MESHES = Path(__file__).parent / "data" / "meshes"


def corpus(name: str) -> MeshData:
    """Eine Datei aus dem Referenzkorpus, so wie die Anwendung sie einliest.

    Über ``normalise``, nicht über ``read_mesh`` allein: ein STL trägt jedes
    Dreieck einzeln, und ohne das Verschweißen hat ``plate_holes`` 796
    Komponenten statt einer. Ein Geometrietest, der damit rechnet, misst die
    Datei und nicht die Operation.
    """
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def run(
    op: str,
    entry: SceneObject,
    profile: Profile,
    quality: Quality = "fine",
    **params: object,
) -> OpResult:
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality=quality,
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def spread(mesh: MeshData) -> float:
    """Wie ungleichmäßig die Kanten sind: Streuung als Anteil des Mittelwerts.

    Eine einzelne Kantenlänge sagt nichts — gefragt ist, ob alle ungefähr
    gleich lang sind. Eine Kugel aus dem Ikosaeder liegt bei 0,07, ein
    CAD-Netz mit Bohrungsfacetten neben großen Flächen bei über 2.
    """
    lengths = mesh_ops.edge_lengths(mesh)
    return float(lengths.std() / np.median(lengths))


def object_of(mesh: MeshData, name: str = "Teil") -> SceneObject:
    return SceneObject(id="obj_1", name=name, mesh=mesh)


# --- gleichmäßig vernetzen ------------------------------------------------------


def test_uniform_remeshing_evens_out_more_than_splitting_does(
    profile: Profile,
) -> None:
    """Der Unterschied zu ``remesh_mesh``, in einer Zahl.

    Bis trimesh 4 war er schroff: Teilen ließ die Kantenstreuung, wie sie war
    — an ``plate_holes`` vorher 2,224 und nachher 2,224, auf die vierte Stelle
    identisch. Die Operation machte das Netz feiner, nicht gleichmäßiger.

    trimesh 5 teilt selbst gleichmäßig und kommt auf **0,555** (gemessen am
    14.08.2026). Der Vorsprung ist damit kleiner geworden, aber er steht:
    ``remesh_uniform`` liegt bei **0,410** — und braucht dafür ein Fünftel der
    Dreiecke, siehe den Test darunter.
    """
    plate = corpus("plate_holes.stl")
    before = spread(plate)

    only_split = mesh_ops.remesh(plate, 1.5)
    result = run("remesh_uniform", object_of(plate), profile, edge=1.5)
    evened = result.outputs[0].mesh

    assert before > 2.0, "die Vorlage ist ungleichmäßig, sonst prüft dieser Test nichts"
    assert spread(only_split) < before, "seit trimesh 5 teilt auch remesh_mesh gleichmäßiger"
    assert spread(evened) < spread(only_split), "gleichmäßig vernetzen liegt weiter vorn"
    assert spread(evened) < 0.5


def test_uniform_remeshing_keeps_the_shape_exactly(profile: Profile) -> None:
    """Ohne zugelassene Abweichung wird kein Eckpunkt verschoben.

    Das ist die Zusage, die ``remesh_uniform`` von ``decimate_mesh``
    unterscheidet: Es kommen Dreiecke dazu, es geht keine Form verloren.
    """
    plate = corpus("plate_holes.stl")

    result = run("remesh_uniform", object_of(plate), profile, edge=1.5)

    after = result.outputs[0].mesh
    assert after.volume == pytest.approx(plate.volume, abs=1e-6)
    assert after.is_watertight
    assert after.component_count == 1


def test_uniform_remeshing_costs_a_fraction_of_the_triangles(profile: Profile) -> None:
    """Warum es eine eigene Operation ist und keine Zeile in ``remesh_mesh``.

    Für dieselbe Zielkantenlänge von 1,5 mm braucht ``remesh_mesh`` auf
    ``plate_holes`` **160 084** Dreiecke, ``remesh_uniform`` **30 648** —
    Faktor 5,2 (gemessen am 14.08.2026 unter trimesh 5.0.0).

    Hier stand Faktor **hundert**: 3 260 416 gegen rund 30 000. Der Abstand
    ist eingebrochen, weil trimesh 5 sparsamer teilt, statt jede winzige
    Bohrungsfacette mitzuzerteilen. Die Operation bleibt die schonendere und
    die gleichmäßigere — aber ihr Vorsprung trägt sich nicht mehr von selbst.
    Wer sie infrage stellt, misst neu, statt diese Zahlen fortzuschreiben.
    """
    plate = corpus("plate_holes.stl")

    result = run("remesh_uniform", object_of(plate), profile, edge=1.5)

    evened = result.outputs[0].mesh
    assert evened.triangle_count < mesh_ops.remesh(plate, 1.5).triangle_count / 5
    assert evened.triangle_count > plate.triangle_count, "feiner wird es trotzdem"


def test_a_permitted_deviation_clears_out_needless_detail_and_says_what_it_cost(
    profile: Profile,
) -> None:
    """Die zweite Hälfte der Gleichmäßigkeit: die zu feinen Stellen.

    Teilen allein erreicht die Obergrenze der Kantenlänge, nicht die
    Untergrenze — die Facetten einer kleinen Bohrung bleiben winzig. Wer sie
    loswerden will, erlaubt eine Abweichung, und dann sagt der Befund, wie
    weit die Fläche dafür gewandert ist.
    """
    plate = corpus("plate_holes.stl")

    exact = run("remesh_uniform", object_of(plate), profile, edge=1.5)
    coarse = run("remesh_uniform", object_of(plate), profile, edge=1.5, deviation=0.2)

    assert coarse.outputs[0].mesh.triangle_count < exact.outputs[0].mesh.triangle_count
    assert spread(coarse.outputs[0].mesh) < spread(exact.outputs[0].mesh)
    measured = next(f for f in coarse.findings if f.code == "mesh.deviation")
    assert float(measured.values["deviation_mm"]) > 0.0, "es sagt, was es gekostet hat"


def test_an_edge_length_that_cannot_be_reached_says_which_one_can(profile: Profile) -> None:
    """Fehler als Vorschlag, bevor der Fehler passiert.

    Eine zu kleine Kantenlänge ergäbe Millionen Dreiecke. Die Operation rechnet
    das vorher aus, statt erst minutenlang zu laufen — und nennt die Länge, die
    noch geht, sonst rät der Nutzer die nächste Zahl genauso.
    """
    plate = corpus("plate_holes.stl")

    with pytest.raises(ValidationError) as raised:
        run("remesh_uniform", object_of(plate), profile, edge=0.05)

    assert raised.value.suggestions
    assert float(raised.value.values["reachable"]) > 0.05


def test_a_body_without_volume_is_turned_away_with_a_way_out(profile: Profile) -> None:
    """Der Befund aus P16.2, jetzt als Verhalten.

    ``generated_figure.stl`` trägt absichtlich die Fehler eines Generators, und
    der Geometriekern nimmt kein Netz an, das kein Volumen umschließt — er gibt
    ein leeres zurück. Ein leeres Ergebnis wäre die schlechteste Antwort: Der
    Körper verschwindet, und niemand weiß warum.
    """
    figure = corpus("generated_figure.stl")
    assert not figure.is_watertight, "die Vorlage ist offen, sonst prüft der Test nichts"

    with pytest.raises(NotManifoldError) as raised:
        run("remesh_uniform", object_of(figure), profile, edge=1.5)

    assert raised.value.suggestions
    # Die Zahl wird gerechnet, nicht gezählt — also wird sie hier gegen die
    # Zählung gehalten. Mit vertauschten Summanden kommt derselbe Betrag mit
    # umgekehrtem Vorzeichen heraus, und das fiele sonst niemandem auf.
    edges = np.sort(np.asarray(figure.raw.edges, dtype=np.int64), axis=1)
    _unique, counts = np.unique(edges, axis=0, return_counts=True)
    assert raised.value.open_edges == int((counts == 1).sum()) > 0


def test_uniform_remeshing_is_the_same_twice(profile: Profile) -> None:
    """Zweimal auswerten gibt identische Geometrie — sonst ist der Cache falsch."""
    plate = corpus("plate_holes.stl")

    first = run("remesh_uniform", object_of(plate), profile, edge=2.0, deviation=0.1)
    second = run("remesh_uniform", object_of(plate), profile, edge=2.0, deviation=0.1)

    assert np.array_equal(
        np.asarray(first.outputs[0].mesh.raw.vertices),
        np.asarray(second.outputs[0].mesh.raw.vertices),
    )


def test_both_qualities_deliver_the_edge_length_that_was_asked_for(profile: Profile) -> None:
    """Entwurf und Fein liefern hier dasselbe, und das mit Absicht.

    Die Kantenlänge *ist* die Zusage dieser Operation. Sie im Entwurf
    stillschweigend zu verdoppeln hieße, ein anderes Netz zu liefern als
    bestelltes — und der nächste Schritt, das Sculpting, rechnet mit genau
    dieser Auflösung.
    """
    plate = corpus("plate_holes.stl")

    draft = run("remesh_uniform", object_of(plate), profile, "draft", edge=2.0)
    fine = run("remesh_uniform", object_of(plate), profile, "fine", edge=2.0)

    assert draft.outputs[0].mesh.triangle_count == fine.outputs[0].mesh.triangle_count


# --- unterteilen ----------------------------------------------------------------


def test_subdivision_rounds_a_faceted_ball(profile: Profile) -> None:
    """Der Zweck der Operation, an einem Körper, dessen Ziel sich ausrechnen
    lässt.

    Ein Ikosaeder mit einer Unterteilung misst 29 270 mm³; die Kugel mit
    Radius 20, die er meint, misst 33 510. Reines Teilen käme nie dorthin — es
    fügt Punkte auf den Facetten ein, und die liegen alle in der Ebene. Erst
    die Interpolation über die Tangenten hebt sie auf die gekrümmte Fläche.
    """
    ball = MeshData.of(trimesh.creation.icosphere(subdivisions=1, radius=20.0))
    exact = 4.0 / 3.0 * np.pi * 20.0**3

    result = run("subdivide_surface", object_of(ball), profile, edge=1.5)

    rounded = result.outputs[0].mesh
    assert rounded.volume > ball.volume, "aus dem Vieleck wird eine Kugel"
    assert rounded.volume == pytest.approx(exact, rel=0.01)
    assert rounded.is_watertight


def test_subdivision_leaves_the_sharp_edges_of_a_cube_alone(profile: Profile) -> None:
    """Eine Kante über dem Winkel bleibt eine Kante.

    Ohne diese Eigenschaft wäre die Operation für alles unbrauchbar, was neben
    einer Rundung auch eine Fläche hat — und das ist so ziemlich jedes
    Druckteil.
    """
    cube = corpus("cube_clean.stl")

    result = run("subdivide_surface", object_of(cube), profile, edge=1.5)

    after = result.outputs[0].mesh
    assert after.volume == pytest.approx(cube.volume, abs=1e-6), "der Würfel bleibt ein Würfel"
    assert after.triangle_count > cube.triangle_count, "feiner wird er trotzdem"


def test_a_wider_angle_rounds_the_cube_off_as_well(profile: Profile) -> None:
    """Die Gegenprobe — sonst könnte der Test oben auch grün sein, weil gar
    nichts passiert.
    """
    cube = corpus("cube_clean.stl")

    result = run("subdivide_surface", object_of(cube), profile, edge=1.5, angle=100.0)

    assert result.outputs[0].mesh.volume > cube.volume * 2.0


def test_subdivision_does_not_collapse_a_cad_mesh_into_quads(profile: Profile) -> None:
    """Das Fehlerbild, das dieses Paket gekostet hat — als Test statt als Notiz.

    Der naheliegende Weg über ``smooth_out`` markiert je zwei koplanare
    Dreiecke als Viereck und überspringt beim Verfeinern deren Diagonale.
    Bei einem CAD-Netz, in dem *jede* ebene Fläche aus genau zwei Dreiecken
    besteht, bricht das zusammen: aus 31 322 mm³ wurden 25 832, mit 2 772
    Kanten der Länge null — und das Ergebnis meldete sich weiter als
    wasserdicht. Der Weg über die Normalen umgeht die Vierecks-Erkennung.
    """
    plate = corpus("plate_holes.stl")

    result = run("subdivide_surface", object_of(plate), profile, edge=1.5)

    after = result.outputs[0].mesh
    # Nicht bitgenau, und das ist richtig: Diese Operation *darf* die Form
    # ändern. Bei einem Netz aus lauter scharfen Kanten bleibt davon nur das
    # Rauschen der Interpolation — hier ein Milliardstel Prozent, während der
    # Zusammenbruch ein Sechstel des Körpers kostete.
    assert after.volume == pytest.approx(plate.volume, rel=1e-6)
    assert after.is_watertight
    assert after.component_count == 1
    assert float(mesh_ops.edge_lengths(after).min()) > 0.0, "keine entarteten Dreiecke"


def test_subdividing_a_body_without_volume_is_turned_away_too(profile: Profile) -> None:
    """Dieselbe Vorbedingung wie beim gleichmäßigen Vernetzen, derselbe Ausweg."""
    figure = corpus("generated_figure.stl")

    with pytest.raises(NotManifoldError) as raised:
        run("subdivide_surface", object_of(figure), profile, edge=1.5)

    assert raised.value.suggestions


def test_subdivision_is_the_same_twice(profile: Profile) -> None:
    ball = MeshData.of(trimesh.creation.icosphere(subdivisions=1, radius=20.0))

    first = run("subdivide_surface", object_of(ball), profile, edge=2.0)
    second = run("subdivide_surface", object_of(ball), profile, edge=2.0)

    assert np.array_equal(
        np.asarray(first.outputs[0].mesh.raw.vertices),
        np.asarray(second.outputs[0].mesh.raw.vertices),
    )


def test_subdivision_says_how_far_the_surface_moved(profile: Profile) -> None:
    """Eine Operation, die die Form ändert, sagt wie sehr — wie das Dezimieren
    und das Glätten es tun.
    """
    ball = MeshData.of(trimesh.creation.icosphere(subdivisions=1, radius=20.0))

    result = run("subdivide_surface", object_of(ball), profile, edge=1.5)

    measured = next(f for f in result.findings if f.code == "mesh.deviation")
    assert float(measured.values["deviation_mm"]) > 0.0


def _hollow_sphere(profile: Profile) -> MeshData:
    """Eine dünnwandige Hohlkugel — der Fall, in dem Vereinfachen wehtut.

    Zwei Schalen im Abstand von 1,2 mm, dazu die Entlüftung: 197 000 Dreiecke,
    von denen die inneren dicht neben den äußeren liegen. Genau so kam die
    ausgehöhlte Ente aus dem Kundendurchgang heraus.
    """
    kugel = MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=30.0))
    return run("hollow_object", object_of(kugel), profile, wall=1.2, vents=1).outputs[0].mesh


def test_a_body_that_opens_up_while_being_simplified_says_so(profile: Profile) -> None:
    """Gemessen an einer heruntergeladenen Ente: *Netz vereinfachen* auf 60 000
    Dreiecke machte aus einem geschlossenen Körper einen offenen.

    Im Prüfbericht stand dazu ein einziger Satz — „Die Fläche hat sich dabei
    kaum verschoben". Richtig, und vollkommen nebensächlich: Was zählt, ist,
    dass danach kein Körper mehr da ist, den man drucken kann. Wer es nicht
    hier erfährt, erfährt es beim Export, einen Arbeitsschritt später.

    Die Kennung endet auf ``not_watertight`` und gehört damit zur Familie, die
    dieselben zwei Handlungen trägt (``FINDING_ACTIONS``).
    """
    hohl = _hollow_sphere(profile)
    assert hohl.is_watertight, "der Ausgangspunkt des Tests"

    # **60 000, und das ist die Zahl aus dem Kundendurchgang oben.** Hier stand
    # 800, und der Test war aus dem falschen Grund grün: Die Entlüftung ging bis
    # zum 25.08.2026 durch den ganzen Körper — auch durch die Decke —, und der
    # so entstandene Tunnel riss beim Vereinfachen als Erstes auf. Seit die
    # Entlüftung im Hohlraum endet (geom.hollow._vent), bleibt eine grob
    # vereinfachte Kugel ein geschlossener Klumpen: Bei 800 Dreiecken ist die
    # Innenschale ganz verschwunden. Aufreißen tut die **Wand**, und dafür
    # braucht es eine Auflösung, bei der beide Schalen noch da sind.
    result = run("decimate_mesh", object_of(hohl), profile, triangles=60_000)

    assert not result.outputs[0].mesh.is_watertight, "so grob geht die Wand auf"
    assert "mesh.not_watertight" in [entry.code for entry in result.findings]


def test_a_simplification_that_holds_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe: Wo der Körper geschlossen bleibt, sagt niemand etwas.

    Eine **massive** Kugel übersteht dasselbe Ziel geschlossen — der
    Unterschied ist die dünne Wand und nicht die Grobheit. Ohne diesen Fall
    prüfte der Test oben bloß, dass irgendein Befund entsteht, und ein Satz
    über einen Zustand, der nicht eingetreten ist, ist schlimmer als keiner.

    (Ob eine Hohlkugel bei einem *milderen* Ziel geschlossen bleibt, ist keine
    Zusage, die hier stehen darf: Gemessen bleibt sie bei 2000 Dreiecken
    geschlossen und geht bei 20 000 auf — die Reihenfolge der Kantenkollapse
    entscheidet, nicht die Zahl.)
    """
    massiv = MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=30.0))

    result = run("decimate_mesh", object_of(massiv), profile, triangles=800)

    assert result.outputs[0].mesh.is_watertight, "eine massive Kugel hält das aus"
    assert "mesh.not_watertight" not in [entry.code for entry in result.findings]
