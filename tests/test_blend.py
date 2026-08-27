"""Weiches Verschmelzen (Konzept P16.4, Entscheidung N).

Die einzige Operation der organischen Phase, die *parametrisch* organisch ist:
drei Zahlen, kein Handgriff, voll im Stapel änderbar. Für einen ergonomischen
Griff an einem technischen Teil ist sie das bessere Werkzeug als jeder Pinsel.

Sie rechnet nicht wie die anderen booleschen Operationen. Statt Flächen zu
schneiden legt sie beide Körper als Abstandsfeld auf ein Raster, mischt die
Felder weich und zieht die neue Oberfläche daraus. Das kostet Genauigkeit —
gemessen wird hier deshalb gegen die scharfe Vereinigung, die es exakt kann,
und der Abstand dazwischen ist die Zahl, die zählt.
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from app.core.errors import NotManifoldError, ValidationError
from app.core.geom.mesh import MeshData
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, OpResult, Profile, Quality, Scene, SceneObject


def rod(along: str = "z") -> MeshData:
    """Ein Zylinder, 20 mm dick, 60 mm lang, entlang einer Achse."""
    body = trimesh.creation.cylinder(radius=10.0, height=60.0, sections=48)
    if along == "y":
        body.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0]))
    return MeshData.of(body)


def run(
    first: MeshData,
    second: MeshData,
    profile: Profile,
    quality: Quality = "fine",
    **params: object,
) -> OpResult:
    spec = REGISTRY.get("blend_union")
    entries = [
        SceneObject(id="obj_1", name="Erster", mesh=first),
        SceneObject(id="obj_2", name="Zweiter", mesh=second),
    ]
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry for entry in entries}),
            inputs=entries,
            params=spec.params(**params),
            profile=profile,
            quality=quality,
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_without_a_radius_it_is_the_ordinary_union(profile: Profile) -> None:
    """Der Nullpunkt der Operation, und die Messlatte für alles andere.

    Mit Radius null ist die weiche Vereinigung die gewöhnliche. Sie kommt
    nicht auf dieselbe Zahl — ein Rasterverfahren rundet, wo ein exakter
    Schnitt trifft —, aber sie muss nah dran sein. Ist sie es nicht, stimmt
    das Abstandsfeld nicht, und jeder Radius darüber wäre auch falsch.
    """
    first, second = rod("z"), rod("y")
    sharp = first.raw.union(second.raw)

    result = run(first, second, profile, radius=0.0, grid=1.0)

    merged = result.outputs[0].mesh
    assert merged.volume == pytest.approx(sharp.volume, rel=0.02)
    assert merged.is_watertight
    assert merged.component_count == 1


def test_the_result_stays_inside_the_hull_it_was_given(profile: Profile) -> None:
    """Die Lücke, durch die ein Fehler bis in einen Commit kam.

    Volumen und Wasserdichtheit waren geprüft, die *Ausdehnung* nicht — und
    genau dort saß der Fehler: Das Vorzeichen des Abstandsfeldes kam aus
    gemittelten Eckpunktnormalen, und die stehen an der Deckkante eines
    Zylinders 45 Grad schräg. Über der Deckfläche kippten sie, und der Körper
    wuchs um acht Millimeter ins Leere, ohne dass das Volumen auffällig genug
    gewesen wäre. Ein Rohr, das nach dem Verschmelzen länger ist als vorher,
    ist kein Detail.

    Geprüft wird gegen die Hülle beider Eingangskörper, großzügig um den
    Übergang erweitert: Der Wulst darf nach außen wachsen, aber nicht weit.
    """
    first, second = rod("z"), rod("y")
    radius = 4.0
    low = np.minimum(first.raw.bounds[0], second.raw.bounds[0]) - radius
    high = np.maximum(first.raw.bounds[1], second.raw.bounds[1]) + radius

    merged = run(first, second, profile, radius=radius, grid=1.0).outputs[0].mesh

    assert np.all(np.asarray(merged.raw.bounds[0]) > low), "der Körper wächst nach unten ins Leere"
    assert np.all(np.asarray(merged.raw.bounds[1]) < high), "und nach oben"


def test_the_radius_puts_material_into_the_throat(profile: Profile) -> None:
    """Wofür es die Operation gibt: die Kehle, die niemand drucken will.

    Zwei gekreuzte Rohre treffen sich in einer scharfen Innenkante. Sie ist
    die Stelle, an der ein Druck reißt, und mit keinem Pinsel zu erreichen —
    sie liegt innen. Je größer der Radius, desto mehr Material sitzt darin,
    und das lässt sich wiegen.
    """
    first, second = rod("z"), rod("y")

    volumes = [
        run(first, second, profile, radius=radius, grid=1.0).outputs[0].mesh.volume
        for radius in (0.0, 3.0, 6.0, 10.0)
    ]

    assert volumes == sorted(volumes), "mehr Radius, mehr Kehle — ohne Ausnahme"
    assert volumes[-1] > volumes[0] * 1.05, "und zwar spürbar, nicht im Rauschen"


def test_every_radius_leaves_one_closed_body(profile: Profile) -> None:
    """Ein Wulst, der das Netz aufreißt, wäre schlimmer als keiner."""
    first, second = rod("z"), rod("y")

    for radius in (0.0, 5.0, 12.0):
        merged = run(first, second, profile, radius=radius, grid=1.0).outputs[0].mesh
        assert merged.is_watertight, f"Radius {radius} hat das Netz geöffnet"
        assert merged.component_count == 1


def test_two_bodies_that_do_not_touch_are_drawn_together(profile: Profile) -> None:
    """Das Gegenstück zu Metaballs, und der Grund, warum es ein Basisnetz baut.

    Zwei Kugeln mit einem Spalt dazwischen: Die gewöhnliche Vereinigung lässt
    sie zwei Körper bleiben. Ein Übergang, der weit genug reicht, zieht eine
    Brücke — daraus entsteht die grobe Form, auf der später geformt wird.

    **Weit genug heißt etwa dreimal der Spalt**, und das ist nicht zu raten:
    Der Wulst hebt das Feld in der Mitte um ein Viertel des Übergangs an, muss
    dort aber den halben Spalt überwinden. Gemessen an 4 mm und 6 mm Spalt
    steht die Brücke beim Dreifachen und beim Zweifachen noch nicht. Der
    Dialogtext sagt es deshalb, statt es den Nutzer suchen zu lassen.
    """
    gap = 6.0
    first = MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=12.0))
    apart = trimesh.creation.icosphere(subdivisions=3, radius=12.0)
    apart.apply_translation((24.0 + gap, 0.0, 0.0))
    second = MeshData.of(apart)

    separate = run(first, second, profile, radius=0.0, grid=1.0)
    narrow = run(first, second, profile, radius=gap * 2.0, grid=1.0)
    bridged = run(first, second, profile, radius=gap * 3.0, grid=1.0)

    assert separate.outputs[0].mesh.component_count == 2, "ohne Übergang bleiben es zwei"
    assert narrow.outputs[0].mesh.component_count == 2, "zu schmal reicht nicht über den Spalt"
    assert bridged.outputs[0].mesh.component_count == 1, "dreifach wird eine Form daraus"
    assert bridged.outputs[0].mesh.is_watertight
    # Und wer zu schmal wählt, erfährt es, statt zwei Körper für einen zu halten.
    assert "blend.still_apart" in {finding.code for finding in narrow.findings}
    assert "blend.still_apart" not in {finding.code for finding in bridged.findings}


def test_a_box_on_the_grid_lines_still_closes(profile: Profile) -> None:
    """Das Fehlerbild, das dieses Paket gekostet hat.

    Ein achsparalleler Quader mit runden Maßen legt seine Flächen genau auf
    die Rasterpunkte. Dort ist das Abstandsfeld exakt null, und die
    Isoflächensuche findet keinen Vorzeichenwechsel, an dem sie ein Dreieck
    aufspannen könnte: Das Ergebnis zerfiel in 793 Bruchstücke und war um drei
    Prozent zu groß. Deshalb liegt das Raster versetzt.
    """
    first = MeshData.of(trimesh.creation.box(extents=(40.0, 30.0, 20.0)))
    other = trimesh.creation.box(extents=(20.0, 20.0, 40.0))
    second = MeshData.of(other)

    merged = run(first, second, profile, radius=0.0, grid=1.0).outputs[0].mesh

    assert merged.is_watertight
    assert merged.component_count == 1
    assert merged.volume == pytest.approx(first.raw.union(other).volume, rel=0.05)


def test_the_same_parameters_give_the_same_body(profile: Profile) -> None:
    """Die Abstandsabfrage läuft über alle Kerne — Nebenläufigkeit darf das
    Ergebnis nicht anfassen.
    """
    first, second = rod("z"), rod("y")

    once = run(first, second, profile, radius=5.0, grid=1.5).outputs[0].mesh
    twice = run(first, second, profile, radius=5.0, grid=1.5).outputs[0].mesh

    assert np.array_equal(np.asarray(once.raw.vertices), np.asarray(twice.raw.vertices))


def test_a_grid_too_fine_to_compute_says_which_one_works(profile: Profile) -> None:
    """Fehler als Vorschlag, bevor der Fehler passiert — wie beim Vernetzen."""
    first, second = rod("z"), rod("y")

    with pytest.raises(ValidationError) as raised:
        run(first, second, profile, radius=0.0, grid=0.02)

    assert raised.value.suggestions
    assert float(raised.value.values["reachable"]) > 0.02


def test_a_body_without_volume_is_turned_away(profile: Profile) -> None:
    """Ein Abstandsfeld braucht ein Innen. Eine offene Fläche hat keines."""
    open_body = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    open_body.update_faces(np.arange(len(open_body.faces)) > 1)

    with pytest.raises(NotManifoldError) as raised:
        run(MeshData.of(open_body), rod("z"), profile, radius=2.0, grid=1.0)

    assert raised.value.suggestions


def test_the_finding_says_the_result_is_rastered(profile: Profile) -> None:
    """Was Genauigkeit kostet, wird ausgewiesen — wie die Voxelstufe es tut.

    Wer diese Operation für eine Passung benutzt, hat sich vertan, und er darf
    das nicht erst am gedruckten Teil merken.
    """
    first, second = rod("z"), rod("y")

    result = run(first, second, profile, radius=4.0, grid=1.0)

    codes = {finding.code for finding in result.findings}
    assert "blend.rastered" in codes
    finding = next(f for f in result.findings if f.code == "blend.rastered")
    assert float(finding.values["grid_mm"]) == pytest.approx(1.0)


def test_draft_quality_is_coarser_than_fine(profile: Profile) -> None:
    """Hier trägt der Unterschied, anders als beim Vernetzen.

    Die Rasterweite ist keine Zusage über das Ergebnis, sondern der Preis für
    seine Genauigkeit — und im Entwurf wird iteriert, nicht abgenommen.
    """
    first, second = rod("z"), rod("y")

    draft = run(first, second, profile, "draft", radius=4.0, grid=1.0)
    fine = run(first, second, profile, "fine", radius=4.0, grid=1.0)

    assert draft.outputs[0].mesh.triangle_count < fine.outputs[0].mesh.triangle_count
    assert draft.outputs[0].mesh.is_watertight
