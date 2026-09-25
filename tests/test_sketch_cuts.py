"""Schneiden mit den drei Skizzenwerkzeugen (CAD-Konzept P6.5a–c, RM-188).

Drehen, entlang einer Bahn führen und zwischen zwei Umrissen überblenden
gab es bis hierher nur als **Erzeuger**: Sie setzten einen neuen Körper in
die Szene. Eine Ringnut in einer Welle, ein geführter Kanal durch einen Block
und ein Übergang von eckig auf rund *in* einem Teil waren damit nur über zwei
Schritte zu haben — Werkzeugkörper erzeugen, dann *Abziehen* — und das
Werkzeug lag danach als eigener Körper im Verlauf.

Jede Zahl hier kommt aus der Konstruktion und nicht aus dem Prüfling:
Pappus für die Nut, Querschnitt mal Bahnlänge für den Kanal, die
Pyramidenstumpfformel für den Übergang. Lage, Endquerschnitte und der
Achsschnitt werden an Punkten geprüft, deren Innen oder Außen aus den Maßen
folgt — mit einem Abstand zur Sollkante, der größer ist als die zugelassene
Sehnenhöhe des Netzwegs (``units.MAX_FACET_SAG``).

Beide Kerne: ein exakter Zielkörper bleibt exakt, ein Netz geht über die
Boolesche Rückfallkette, und die erreichte Stufe steht in ``solver``.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.core.brep.kernel import Solid, available
from app.core.errors import AppError, GeometryError, ValidationError
from app.core.geom.mesh import MeshData, as_mesh_data, read_mesh
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY, needed_inputs
from app.core.scene.cancel import NeverCancelled
from app.core.sketch.serialize import sketch_to_text
from app.core.types import OpContext, OpResult, Scene, SceneObject, Sketch, SketchElement
from app.core.units import MAX_FACET_SAG

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")

MESHES = Path(__file__).parent / "data" / "meshes"

#: Wie weit ein Prüfpunkt von der Sollkante wegliegt. Mehr als die Sehnenhöhe
#: des Netzwegs, damit ein Punkt am facettierten Werkzeug nicht auf die
#: falsche Seite fällt — und weit unter jedem Maß der Konstruktion.
MARGIN = 2.0 * MAX_FACET_SAG + 0.05


class Asked:
    """Nimmt die Fragen der Operation mit und antwortet mit der gewünschten Wahl."""

    def __init__(self, pick: int = 0) -> None:
        self.pick = pick
        self.questions: list[tuple[str, list[str]]] = []

    def __call__(self, question: str, choices: list[str]) -> str:
        self.questions.append((str(question), list(choices)))
        return choices[self.pick]


def run(
    op: str,
    entry: SceneObject | None = None,
    *,
    ask: Any = None,
    quality: str = "fine",
    **params: object,
) -> OpResult:
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry} if entry else {}, parameters={}),
            inputs=[entry] if entry else [],
            params=spec.params(**params),
            profile=None,
            quality=quality,  # type: ignore[arg-type]
            seed=None,
            progress=lambda fraction, text: None,
            ask=ask or (lambda question, choices: choices[0]),
            cancelled=NeverCancelled(),
        )
    )


def made(op: str, **params: object) -> SceneObject:
    """Ein Grundkörper des exakten Kerns, mit Kennung wie im Stapel."""
    entry = run(op, **params).outputs[0]
    entry.id = "obj_1"
    return entry


def corpus(name: str) -> SceneObject:
    """Ein Netz aus dem Referenzkorpus, gelesen wie beim Import."""
    mesh = normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh
    return SceneObject(id="obj_1", name=name, mesh=mesh)


def inside(body: Any, point: tuple[float, float, float]) -> bool:
    """Liegt der Punkt im Material? Exakt über den Klassierer, am Netz über die Windungszahl.

    Die Windungszahl braucht keinen Suchbaum und keine Strahlen: Sie summiert
    die Raumwinkel aller Dreiecke (Van Oosterom und Strackee) und ist für
    einen geschlossenen Körper innen eins, außen null.
    """
    if isinstance(body, Solid):
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        from OCP.gp import gp_Pnt
        from OCP.TopAbs import TopAbs_IN

        return bool(
            BRepClass3d_SolidClassifier(body.shape, gp_Pnt(*point), 1e-7).State() == TopAbs_IN
        )
    raw = body.raw if isinstance(body, MeshData) else body
    corners = np.asarray(raw.vertices, dtype=float)[np.asarray(raw.faces)] - np.asarray(point)
    a, b, c = corners[:, 0], corners[:, 1], corners[:, 2]
    la, lb, lc = (np.linalg.norm(v, axis=1) for v in (a, b, c))
    numerator = np.einsum("ij,ij->i", a, np.cross(b, c))
    denominator = (
        la * lb * lc
        + np.einsum("ij,ij->i", a, b) * lc
        + np.einsum("ij,ij->i", b, c) * la
        + np.einsum("ij,ij->i", c, a) * lb
    )
    winding = float(np.sum(np.arctan2(numerator, denominator))) / (2.0 * math.pi)
    return winding > 0.5


def removed(before: SceneObject, result: OpResult) -> float:
    return float(before.mesh.volume - result.outputs[0].mesh.volume)


def polygon(*points: tuple[float, float], plane: str = "plane:xy") -> str:
    """Ein geschlossener Streckenzug als gezeichnete Skizze."""
    return sketch_to_text(
        Sketch(
            plane=plane,
            elements=tuple(
                SketchElement("line", (points[index], points[(index + 1) % len(points)]))
                for index in range(len(points))
            ),
            constraints=(),
        )
    )


def path(*points: tuple[float, float], plane: str = "plane:xz") -> str:
    """Eine offene Bahn als Streckenzug."""
    return sketch_to_text(
        Sketch(
            plane=plane,
            elements=tuple(
                SketchElement("line", (points[index], points[index + 1]))
                for index in range(len(points) - 1)
            ),
            constraints=(),
        )
    )


def curved_path(*elements: SketchElement, plane: str = "plane:xz") -> str:
    return sketch_to_text(Sketch(plane=plane, elements=elements, constraints=()))


# --- Register: drei Handlungen, kein neuer Menüeintrag ------------------------

CUTS = ("sketch_revolve_cut", "sketch_sweep_cut", "sketch_loft_cut")


@pytest.mark.parametrize("name", CUTS)
def test_every_cut_takes_one_body_and_keeps_it(name: str) -> None:
    """Ein Schnitt ändert den gewählten Körper — er setzt keinen neuen daneben.

    Deshalb eine eigene Operation je Werkzeug und kein Umschalter an den
    Erzeugern: Das Register kennt je Operation eine feste Eingangszahl, und
    der Stapel vergibt die Kennungen, bevor etwas rechnet (§11). Ein Erzeuger
    nimmt nichts und gibt einen neuen Körper; ein Schnitt nimmt einen und gibt
    ihn verändert unter seiner Kennung zurück — wie *Tasche schneiden* neben
    *Grundform hochziehen*.
    """
    spec = REGISTRY.get(name)
    assert spec.category == "sketch"
    assert spec.consumes == 1 and spec.produces == 1
    assert needed_inputs(spec) == 1
    assert not spec.deterministic, "die Netzkette stört mit gespeichertem Startwert (§17.2)"
    assert spec.doc and spec.title


def test_the_cuts_live_in_the_sketch_dialog_and_not_in_the_menu() -> None:
    """Konzept §10: „Revolve-Cut wird kein zweiter Eintrag, sondern ein Feld im Dialog."

    Das Feld ist die Art in *Aus Skizze erzeugen …*: Wer gedreht hat und eine
    Nut will, wählt dort die Schnittvariante, ohne zurück zur Auswahl zu
    müssen — derselbe Weg, den *Tasche schneiden* neben dem Hochziehen geht.
    """
    from app.core.registry import VARIANT_GROUPS, variant_members

    group = VARIANT_GROUPS[0]
    members = list(group.members)
    for cut, maker in zip(CUTS, ("sketch_revolve", "sketch_sweep", "sketch_loft"), strict=True):
        assert cut in variant_members()
        assert members.index(cut) == members.index(maker) + 1, (
            f"{cut} steht direkt hinter seinem Erzeuger {maker}"
        )


def test_the_makers_keep_their_parameters() -> None:
    """Alte Projekte rechnen unverändert: Die drei Erzeuger behalten Namen und Felder."""
    expected = {
        "sketch_revolve": [
            "shape",
            "length",
            "width",
            "offset",
            "angle",
            "name",
            "corners",
            "sketch",
        ],
        "sketch_sweep": [
            "shape",
            "length",
            "width",
            "along",
            "bend_radius",
            "bend_angle",
            "path_sketch",
            "name",
            "corners",
            "sketch",
        ],
        "sketch_loft": [
            "shape",
            "length",
            "width",
            "height",
            "top",
            "top_scale",
            "top_sketch",
            "name",
            "corners",
            "sketch",
        ],
    }
    for name, fields in expected.items():
        assert [entry.name for entry in REGISTRY.get(name).params.spec()] == fields


# --- P6.5a: Schnitt durch Drehen ------------------------------------------------


def shaft() -> SceneObject:
    """Welle Ø20 × 40, exakt, von z = 0 bis 40 um die Z-Achse."""
    return made("create_brep_cylinder", diameter=20.0, height=40.0)


def test_a_ring_groove_takes_its_pappus_volume_from_an_exact_shaft() -> None:
    """Rechteck 3 × 3 ab Radius 8: Die Nut reicht von r = 8 bis zur Mantelfläche r = 10.

    Das Werkzeug ragt einen Millimeter über den Mantel hinaus (bis r = 11),
    damit keine Fläche des Werkzeugs auf der Welle liegt. Abgetragen wird der
    Ring zwischen r = 8 und r = 10 über 3 mm Höhe: π (10² − 8²) · 3 = 108 π.
    """
    entry = shaft()
    result = run(
        "sketch_revolve_cut",
        entry,
        shape="rectangle",
        length=3.0,
        width=3.0,
        offset=8.0,
        axis_z=18.0,
    )
    body = result.outputs[0]
    assert body.kind == "brep"
    assert isinstance(body.mesh, Solid)
    assert removed(entry, result) == pytest.approx(108.0 * math.pi, rel=1e-9)
    assert body.mesh.solid_count == 1 and body.mesh.is_closed
    assert result.solver is not None and result.solver.strategy == "direct"
    assert body.id == entry.id, "der Schnitt setzt den Körper fort, er erzeugt keinen neuen"


def test_the_axial_section_of_a_groove_shows_its_profile() -> None:
    """Achsschnitt: In der Ebene durch die Achse liegt die Nut als Rechteck.

    Geprüft auf beiden Seiten der Achse, an allen vier Ecken der Nut von innen
    und außen — so fällt ein verschobener, gekippter oder zu schmaler Schnitt
    auf, den das Volumen allein nicht verrät.
    """
    entry = shaft()
    body = (
        run(
            "sketch_revolve_cut",
            entry,
            shape="rectangle",
            length=3.0,
            width=3.0,
            offset=8.0,
            axis_z=18.0,
        )
        .outputs[0]
        .mesh
    )
    for side in (1.0, -1.0):
        for z in (18.0 + MARGIN, 21.0 - MARGIN):
            assert not inside(body, (side * (8.0 + MARGIN), 0.0, z)), "im Nutgrund ist Luft"
            assert not inside(body, (side * (10.0 - MARGIN), 0.0, z)), "am Mantel ist Luft"
        assert inside(body, (side * (8.0 - MARGIN), 0.0, 19.5)), (
            "unter dem Nutgrund bleibt Material"
        )
        assert inside(body, (side * 9.0, 0.0, 18.0 - MARGIN)), "unter der Nut bleibt Material"
        assert inside(body, (side * 9.0, 0.0, 21.0 + MARGIN)), "über der Nut bleibt Material"


def test_a_partial_groove_takes_its_share_where_it_starts() -> None:
    """Teilwinkel: 90 Grad ab 45 Grad nehmen ein Viertel, und zwar genau dort."""
    entry = shaft()
    result = run(
        "sketch_revolve_cut",
        entry,
        shape="rectangle",
        length=3.0,
        width=3.0,
        offset=8.0,
        axis_z=18.0,
        angle=90.0,
        start_angle=45.0,
    )
    body = result.outputs[0].mesh
    assert removed(entry, result) == pytest.approx(27.0 * math.pi, rel=1e-9)

    def at(degrees: float) -> tuple[float, float, float]:
        return (9.0 * math.cos(math.radians(degrees)), 9.0 * math.sin(math.radians(degrees)), 19.5)

    assert not inside(body, at(90.0)), "mitten im Teilstück ist Luft"
    assert not inside(body, at(45.0 + 5.0)) and not inside(body, at(135.0 - 5.0))
    assert inside(body, at(45.0 - 5.0)) and inside(body, at(135.0 + 5.0)), (
        "davor und dahinter Material"
    )
    assert inside(body, at(0.0)) and inside(body, at(270.0))


def test_a_groove_inside_a_bore_follows_the_bore_axis() -> None:
    """Innenkontur: eine Nut in der Wand einer Bohrung, deren Achse gewählt ist.

    Die Rohrwand liegt zwischen r = 10 und r = 20, verschoben nach (30 | 10).
    Der Querschnitt beginnt bei r = 9 (in der Bohrung, also in der Luft) und
    reicht 2 mm nach außen: abgetragen wird der Ring von r = 10 bis 11 über
    3 mm, π (11² − 10²) · 3 = 63 π. Die Lage kommt aus dem Merkmal — der
    Achspunkt legt nur fest, wo entlang der Achse der Querschnitt beginnt.
    """
    from app.core.brep import edit
    from app.core.brep.features import features_of

    tube = edit.moved(
        edit.boolean("difference", [edit.cylinder(40.0, 20.0), edit.cylinder(20.0, 20.0)]),
        (30.0, 10.0, 0.0),
    )
    features = features_of(tube)
    bore = next(fid for fid, feature in features.items() if feature.kind == "hole")
    entry = SceneObject(id="obj_1", name="Rohr", mesh=tube, kind="brep", features=features)

    result = run(
        "sketch_revolve_cut",
        entry,
        shape="rectangle",
        length=2.0,
        width=3.0,
        offset=9.0,
        axis_z=8.0,
        axis_feature=bore,
    )
    assert removed(entry, result) == pytest.approx(63.0 * math.pi, rel=1e-9)
    body = result.outputs[0].mesh
    assert not inside(body, (30.0 + 10.5, 10.0, 9.5)), "die Nut sitzt in der Bohrungswand"
    assert inside(body, (30.0 + 11.0 + MARGIN, 10.0, 9.5)), "dahinter bleibt die Wand"


def test_an_axis_feature_without_an_axis_is_refused_with_a_way_forward() -> None:
    entry = made("create_brep_box", width=20.0, depth=20.0, height=20.0)
    face = next(fid for fid, feature in entry.features.items() if feature.kind == "face")
    with pytest.raises(ValidationError) as caught:
        run("sketch_revolve_cut", entry, axis_feature=face)
    assert caught.value.suggestions


def test_a_groove_on_a_mesh_shaft_goes_through_the_fallback_chain() -> None:
    """Dieselbe Nut an einem eingelesenen Netz — ``dense_cylinder.stl``, Ø5 × 40.

    Sollwert: π (2,5² − 2²) · 2 = 4,5 π. Das Werkzeug wird mit
    ``MAX_FACET_SAG`` vernetzt; jeder Punkt seiner Oberfläche liegt damit
    höchstens so weit vom exakten Werkzeug entfernt, und das abgetragene
    Volumen weicht um höchstens diese Sehnenhöhe mal der berührten Fläche ab.
    """
    entry = corpus("dense_cylinder.stl")
    result = run(
        "sketch_revolve_cut",
        entry,
        shape="rectangle",
        length=1.5,
        width=2.0,
        offset=2.0,
        axis_z=-1.0,
    )
    body = result.outputs[0]
    assert body.kind == "mesh"
    assert body.mesh.is_watertight
    assert result.solver is not None and result.solver.strategy in ("direct", "welded")
    touched = 2.0 * math.pi * 2.0 * 2.0 + 2.0 * math.pi * (2.5**2 - 2.0**2)
    assert removed(entry, result) == pytest.approx(4.5 * math.pi, abs=MAX_FACET_SAG * touched)
    assert not inside(body.mesh, (2.25, 0.0, 0.0)), "die Nut ist offen"
    assert inside(body.mesh, (1.5, 0.0, 0.0)), "der Kern bleibt"


def test_a_profile_across_the_axis_is_refused() -> None:
    entry = shaft()
    crossing = polygon((-2.0, 0.0), (4.0, 0.0), (4.0, 3.0), (-2.0, 3.0))
    with pytest.raises(ValidationError) as caught:
        run("sketch_revolve_cut", entry, sketch=crossing)
    assert caught.value.suggestions


def test_a_groove_beside_the_shaft_says_it_cut_nothing() -> None:
    """Fehlender Kontakt: keine still unveränderte Ausgabe, sondern ein Befund mit Weg."""
    entry = shaft()
    result = run(
        "sketch_revolve_cut",
        entry,
        shape="rectangle",
        length=3.0,
        width=3.0,
        offset=8.0,
        axis_z=60.0,
    )
    codes = {finding.code: finding for finding in result.findings}
    assert "boolean.without_effect" in codes
    assert codes["boolean.without_effect"].suggestions
    assert removed(entry, result) == pytest.approx(0.0, abs=1e-6)


def test_a_groove_that_swallows_the_part_says_nothing_is_left() -> None:
    entry = made("create_brep_cylinder", diameter=10.0, height=4.0)
    with pytest.raises(GeometryError) as caught:
        run(
            "sketch_revolve_cut",
            entry,
            shape="rectangle",
            length=20.0,
            width=10.0,
            offset=0.0,
            axis_z=-1.0,
        )
    assert caught.value.suggestions


def test_an_unsound_exact_cut_is_not_delivered_but_cut_on_the_mesh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine gültig gemeldete, aber ungültige exakte Differenz geht nicht hinaus.

    Gemessen an ``carpet-corner-clip.step`` (F:\\3D Dateien): Die Nut in der
    Bohrung sank das Volumen um genau das Werkzeug, der Körper war ungültig,
    und der Klassierer fand die Luft der Bohrung danach innen. Hier wird der
    Fall erzwungen, damit der Rückweg einmal gefahren wird — wie jede Stufe der
    Rückfallkette (§17.2): derselbe Schnitt am Netz, mit Befund und Grund.
    """
    from app.core.brep import profiles

    monkeypatch.setattr(profiles, "is_sound", lambda solid: False)
    entry = shaft()
    result = run(
        "sketch_revolve_cut",
        entry,
        shape="rectangle",
        length=3.0,
        width=3.0,
        offset=8.0,
        axis_z=18.0,
    )
    body = result.outputs[0]
    assert body.kind == "mesh" and body.mesh.is_watertight
    assert "sketch.exact_cut_unsound" in {finding.code for finding in result.findings}
    assert result.solver is not None and result.solver.strategy in ("direct", "welded")
    touched = (
        2.0 * math.pi * 8.0 * 3.0 + 2.0 * math.pi * (10.0**2 - 8.0**2) + 2.0 * math.pi * 10.0 * 3.0
    )
    # Gemessen gegen das Netz des Körpers, an dem gerechnet wurde — nicht gegen
    # den exakten Körper, dessen Tessellierung selbst schon um die Sehnen
    # kleiner ist.
    before = as_mesh_data(entry.mesh).volume
    assert before - body.mesh.volume == pytest.approx(108.0 * math.pi, abs=MAX_FACET_SAG * touched)
    assert not inside(body.mesh, (9.0, 0.0, 19.5))


def test_the_revolve_maker_is_unchanged_by_the_shared_profile() -> None:
    """Der Erzeuger nimmt denselben Querschnitt wie der Schnitt — und rechnet wie vorher."""
    body = (
        run("sketch_revolve", shape="rectangle", length=10.0, width=4.0, offset=5.0).outputs[0].mesh
    )
    assert body.volume == pytest.approx(math.pi * (15.0**2 - 5.0**2) * 4.0, rel=1e-9)


# --- P6.5b: Schnitt entlang einer Bahn -----------------------------------------


def block(height: float = 40.0) -> SceneObject:
    """Block 40 × 40 × height, exakt, mittig über dem Ursprung ab z = 0."""
    return made("create_brep_box", width=40.0, depth=40.0, height=height)


def test_a_channel_along_an_arc_takes_section_times_length() -> None:
    """Kanal Ø4 entlang eines Viertelbogens R10, von der Oberseite nach unten.

    Pappus: π · 2² · (π/2 · 10) = 20 π². Der Bahnanfang liegt ohne Angabe an
    der Oberseite (z = 40), weil die Bahn nach unten beginnt.
    """
    entry = block()
    result = run(
        "sketch_sweep_cut", entry, shape="circle", length=4.0, bend_radius=10.0, bend_angle=90.0
    )
    body = result.outputs[0]
    assert body.kind == "brep"
    assert removed(entry, result) == pytest.approx(20.0 * math.pi**2, rel=1e-6)
    assert body.mesh.solid_count == 1 and body.mesh.is_closed
    assert result.solver is not None and result.solver.strategy == "direct"


def test_a_channel_has_its_cross_sections_and_its_ends_where_the_path_puts_them() -> None:
    """Unabhängig geprüfte Querschnitte und Endlagen.

    * **Eintritt:** In der Oberseite ein Kreis r = 2 um (0 | 0).
    * **Mitte:** Nach 45 Grad liegt die Bahn bei (R (1 − cos 45°) | 0 |
      40 − R sin 45°); quer zur Bahn, in Y, reicht der Kanal genau r.
    * **Ende:** Nach 90 Grad zeigt die Bahn nach +X und endet bei (10 | 0 | 30)
      — davor ist Luft, dahinter Material.
    """
    entry = block()
    body = (
        run(
            "sketch_sweep_cut", entry, shape="circle", length=4.0, bend_radius=10.0, bend_angle=90.0
        )
        .outputs[0]
        .mesh
    )
    top = 40.0 - MARGIN
    assert not inside(body, (2.0 - MARGIN, 0.0, top)) and not inside(
        body, (0.0, -2.0 + MARGIN, top)
    )
    assert inside(body, (2.0 + MARGIN, 0.0, top)) and inside(body, (0.0, 2.0 + MARGIN, top))

    mid = (10.0 * (1.0 - math.cos(math.pi / 4)), 0.0, 40.0 - 10.0 * math.sin(math.pi / 4))
    assert not inside(body, (mid[0], 2.0 - MARGIN, mid[2]))
    assert inside(body, (mid[0], 2.0 + MARGIN, mid[2]))

    assert not inside(body, (10.0 - MARGIN, 0.0, 30.0)), "vor dem Ende ist der Kanal offen"
    assert inside(body, (10.0 + MARGIN, 0.0, 30.0)), "hinter dem Ende steht Material"


def test_the_channel_turns_about_the_vertical_through_its_start() -> None:
    """Orientierung: 90 Grad gedreht biegt derselbe Bogen nach +Y statt nach +X ab."""
    entry = block()
    body = (
        run(
            "sketch_sweep_cut",
            entry,
            shape="circle",
            length=4.0,
            bend_radius=10.0,
            bend_angle=90.0,
            turn=90.0,
        )
        .outputs[0]
        .mesh
    )
    assert not inside(body, (0.0, 10.0 - MARGIN, 30.0))
    assert inside(body, (10.0 - MARGIN, 0.0, 30.0))


def test_a_channel_can_start_from_below() -> None:
    """Nach oben beginnend liegt der Anfang ohne Angabe an der Unterseite."""
    entry = block()
    body = (
        run(
            "sketch_sweep_cut",
            entry,
            shape="circle",
            length=4.0,
            bend_radius=10.0,
            bend_angle=90.0,
            heading="up",
        )
        .outputs[0]
        .mesh
    )
    assert not inside(body, (0.0, 0.0, MARGIN)), "der Eintritt liegt in der Unterseite"
    assert not inside(body, (10.0 - MARGIN, 0.0, 10.0)), "das Ende liegt bei z = 10"
    assert inside(body, (0.0, 0.0, 40.0 - MARGIN))


def test_a_drawn_channel_through_a_mesh_block_leaves_by_the_side() -> None:
    """Der Kanal durch ``cube_clean.stl`` (20³, mittig um den Ursprung).

    Bahn: 4 mm nach unten, Viertelbogen R5 nach +X, dann 10 mm geradeaus — das
    Ende liegt bei x = 15, also außerhalb; der Kanal tritt an der Seite
    x = 10 aus, mittig bei z = 10 − 4 − 5 = 1. Im Körper liegen 4 + π/2 · 5 + 5
    Millimeter Bahn. Sie ist nach unten gezeichnet und bleibt deshalb, wie sie
    ist — die Anfangsrichtung „nach unten" dreht nur um, was nach oben beginnt.
    """
    entry = corpus("cube_clean.stl")
    route = curved_path(
        SketchElement("line", ((0.0, 0.0), (0.0, -4.0))),
        SketchElement("arc", ((5.0, -4.0), (0.0, -4.0), (5.0, -9.0))),
        SketchElement("line", ((5.0, -9.0), (15.0, -9.0))),
    )
    result = run(
        "sketch_sweep_cut",
        entry,
        shape="circle",
        length=3.0,
        along="drawn",
        path_sketch=route,
        z=10.0,
    )
    body = result.outputs[0]
    assert body.kind == "mesh" and body.mesh.is_watertight
    assert result.solver is not None
    length = 4.0 + math.pi / 2.0 * 5.0 + 5.0
    area = math.pi * 1.5**2
    touched = 2.0 * math.pi * 1.5 * length + 2.0 * area
    assert removed(entry, result) == pytest.approx(area * length, abs=MAX_FACET_SAG * touched)
    # Austritt an der Seite x = 10, mittig bei z = 1.
    assert not inside(body.mesh, (10.0 - MARGIN, 0.0, 1.0))
    assert inside(body.mesh, (10.0 - MARGIN, 0.0, 1.0 + 1.5 + MARGIN))
    # Eintritt oben.
    assert not inside(body.mesh, (0.0, 0.0, 10.0 - MARGIN))


@pytest.mark.parametrize(("plane", "side"), [("plane:xz", (1.0, 0.0)), ("plane:yz", (0.0, 1.0))])
def test_a_path_drawn_upwards_is_turned_into_the_body_and_keeps_its_side(
    plane: str, side: tuple[float, float]
) -> None:
    """Eine nach oben gezeichnete Bahn läuft von der Oberseite nach unten — und
    biegt dabei zur selben Seite ab wie gezeichnet.

    Umgedreht wird um die Achse, die in der Bahnebene quer liegt: X bei der
    Vorderansicht, Y bei der Seitenansicht. Um X gedreht böge eine Bahn der
    Seitenansicht nach -Y statt nach +Y ab.
    """
    entry = block()
    route = path((0.0, 0.0), (0.0, 10.0), (10.0, 10.0), plane=plane)
    body = (
        run("sketch_sweep_cut", entry, shape="circle", length=4.0, along="drawn", path_sketch=route)
        .outputs[0]
        .mesh
    )
    assert not inside(body, (0.0, 0.0, 40.0 - MARGIN)), "der Eintritt liegt oben"
    near = (side[0] * 5.0, side[1] * 5.0, 30.0)
    far = (-side[0] * 5.0, -side[1] * 5.0, 30.0)
    assert not inside(body, near), "der Kanal biegt zur gezeichneten Seite"
    assert inside(body, far), "und nicht zur anderen"


def test_a_drawn_bend_tighter_than_the_section_is_refused() -> None:
    """Enge Krümmung: Ein Bogen R1 kann einen Querschnitt Ø4 nicht führen.

    OpenCASCADE baut daraus einen Körper, der sich selbst durchdringt, und
    seine eigene Gültigkeitsprüfung (``BRepCheck_Analyzer``) sagt „gültig" —
    erst die Selbstschnittprüfung sieht es. Der Satz nennt die Ursache vorher.
    """
    entry = block()
    route = curved_path(
        SketchElement("line", ((0.0, 0.0), (0.0, -10.0))),
        SketchElement("arc", ((1.0, -10.0), (0.0, -10.0), (1.0, -11.0))),
        SketchElement("line", ((1.0, -11.0), (15.0, -11.0))),
    )
    with pytest.raises(ValidationError) as caught:
        run("sketch_sweep_cut", entry, shape="circle", length=4.0, along="drawn", path_sketch=route)
    assert caught.value.constraint == "tight_bend"
    assert caught.value.suggestions


def test_a_path_that_crosses_itself_is_refused() -> None:
    entry = block()
    route = path((0.0, 0.0), (0.0, -20.0), (10.0, -10.0), (-10.0, -10.0))
    with pytest.raises(ValidationError) as caught:
        run("sketch_sweep_cut", entry, shape="circle", length=4.0, along="drawn", path_sketch=route)
    assert caught.value.constraint == "path_crosses"
    assert caught.value.suggestions


def test_a_path_whose_legs_touch_through_the_section_is_refused() -> None:
    """Selbstüberschneidung ohne Kreuzung: Hin- und Rückweg liegen 6 mm auseinander,
    der Querschnitt ist 10 mm breit — die Röhre trifft sich selbst."""
    entry = block()
    route = path((0.0, 0.0), (0.0, -20.0), (6.0, -20.0), (6.0, 0.0))
    with pytest.raises(GeometryError) as caught:
        run(
            "sketch_sweep_cut", entry, shape="circle", length=10.0, along="drawn", path_sketch=route
        )
    assert caught.value.suggestions
    # Die Ursache und nicht ein Folgefehler: Ohne die Prüfung scheiterte erst das
    # Bewegen des Werkzeugs, mit einem Satz über Transformationen.
    assert caught.value.values.get("reason") == "tool_intersects_itself"


def test_the_sweep_maker_refuses_the_same_broken_tool() -> None:
    """Der Erzeuger lieferte denselben kaputten Körper still aus — jetzt nicht mehr."""
    route = path((0.0, 0.0), (0.0, 20.0), (6.0, 20.0), (6.0, 0.0))
    with pytest.raises(AppError):
        run("sketch_sweep", shape="circle", length=10.0, along="drawn", path_sketch=route)


def test_a_channel_beside_the_block_says_it_cut_nothing() -> None:
    entry = block()
    result = run("sketch_sweep_cut", entry, shape="circle", length=4.0, bend_radius=10.0, x=100.0)
    findings = [finding for finding in result.findings if finding.code == "boolean.without_effect"]
    assert findings and findings[0].suggestions


def test_the_channel_stays_the_same_in_the_draft_quality() -> None:
    """Beide Qualitätsstufen: Im Entwurf endet die Kette nach Stufe 2 — das Maß bleibt."""
    entry = corpus("cube_clean.stl")
    route = path((0.0, 0.0), (0.0, -30.0))
    fine = run(
        "sketch_sweep_cut",
        entry,
        shape="circle",
        length=4.0,
        along="drawn",
        path_sketch=route,
        z=15.0,
    )
    draft = run(
        "sketch_sweep_cut",
        entry,
        shape="circle",
        length=4.0,
        along="drawn",
        path_sketch=route,
        z=15.0,
        quality="draft",
    )
    assert draft.solver is not None and draft.solver.strategy in ("direct", "welded")
    assert removed(entry, draft) == pytest.approx(removed(entry, fine), rel=1e-9)


# --- P6.5c: Schnitt durch Überblenden -------------------------------------------


def test_a_through_transition_is_a_frustum_by_the_formula() -> None:
    """Rechteck 20 × 10 oben, halb so groß unten, durch den ganzen Block (30 mm).

    Pyramidenstumpf: h/3 · (A₁ + A₂ + √(A₁A₂)) = 10 · (200 + 50 + 100) = 3500.
    """
    entry = block(height=30.0)
    result = run(
        "sketch_loft_cut",
        entry,
        shape="rectangle",
        length=20.0,
        width=10.0,
        top_scale=0.5,
        through=True,
    )
    body = result.outputs[0]
    assert body.kind == "brep"
    assert removed(entry, result) == pytest.approx(3500.0, rel=1e-9)
    assert body.mesh.solid_count == 1 and body.mesh.is_closed
    assert result.solver is not None and result.solver.strategy == "direct"


def test_a_transition_has_both_end_sections_and_the_one_between() -> None:
    """Endquerschnitte und innere Öffnung, an den Maßen der Konstruktion geprüft.

    Oben die gezeichnete Öffnung 20 × 10, unten die halbe 10 × 5, auf halber
    Tiefe dazwischen 15 × 7,5 — beim Pyramidenstumpf geradlinig gemittelt.
    """
    entry = block(height=30.0)
    body = (
        run(
            "sketch_loft_cut",
            entry,
            shape="rectangle",
            length=20.0,
            width=10.0,
            top_scale=0.5,
            through=True,
        )
        .outputs[0]
        .mesh
    )
    for z, half_x, half_y in ((30.0 - MARGIN, 10.0, 5.0), (15.0, 7.5, 3.75), (MARGIN, 5.0, 2.5)):
        assert not inside(body, (half_x - 2 * MARGIN, half_y - 2 * MARGIN, z)), z
        assert inside(body, (half_x + 2 * MARGIN, 0.0, z)), z
        assert inside(body, (0.0, half_y + 2 * MARGIN, z)), z


def test_a_blind_transition_ends_at_its_depth() -> None:
    entry = block(height=30.0)
    result = run(
        "sketch_loft_cut",
        entry,
        shape="rectangle",
        length=20.0,
        width=10.0,
        top_scale=0.5,
        depth=12.0,
    )
    # Stumpf von 20 x 10 auf 10 x 5 über 12 mm.
    assert removed(entry, result) == pytest.approx(12.0 / 3.0 * (200.0 + 50.0 + 100.0), rel=1e-9)
    body = result.outputs[0].mesh
    assert not inside(body, (0.0, 0.0, 30.0 - 12.0 + MARGIN))
    assert inside(body, (0.0, 0.0, 30.0 - 12.0 - MARGIN)), "unter der Tiefe bleibt der Boden"


def _square_to_diamond() -> tuple[str, str]:
    """Quadrat 20 × 20 unten, dasselbe Quadrat um 45 Grad gedreht oben.

    Zwei Zuordnungen der Ecken sind dann genau gleich nah — 45 Grad links- oder
    rechtsherum. Welche gemeint ist, sagt die Zeichnung nicht.
    """
    r = 10.0 * math.sqrt(2.0)
    lower = polygon((-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0))
    upper = polygon((r, 0.0), (0.0, r), (-r, 0.0), (0.0, -r))
    return lower, upper


def test_a_transition_between_two_equally_near_turns_asks_which_one() -> None:
    """Regel 21: Mehrdeutigkeit hält an und fragt — und die Antwort reist mit."""
    lower, upper = _square_to_diamond()
    entry = block(height=30.0)
    asked = Asked(pick=0)
    result = run(
        "sketch_loft_cut",
        entry,
        ask=asked,
        sketch=lower,
        top="drawn",
        top_sketch=upper,
        depth=20.0,
    )
    assert len(asked.questions) == 1
    assert len(asked.questions[0][1]) == 2
    assert result.answered == {"twist": "counterclockwise"}


def test_the_two_turns_are_mirror_images_and_the_answer_decides() -> None:
    """Linksherum und rechtsherum: gleiches Volumen, andere Form.

    Auf halber Tiefe liegen die Kanten der Mantelflächen zwischen den
    zugeordneten Ecken. Linksherum geht die Kante von (10 | 10) nach (0 | r),
    rechtsherum nach (r | 0); bei x = 4 liegt sie einmal bei y ≈ 11,66, einmal
    bei y ≈ 8,34. Der Punkt (4 | 10) ist damit einmal Luft und einmal Material.
    """
    lower, upper = _square_to_diamond()
    entry = block(height=30.0)
    left = run(
        "sketch_loft_cut",
        entry,
        sketch=lower,
        top="drawn",
        top_sketch=upper,
        depth=20.0,
        twist="counterclockwise",
    )
    right = run(
        "sketch_loft_cut",
        entry,
        sketch=lower,
        top="drawn",
        top_sketch=upper,
        depth=20.0,
        twist="clockwise",
    )
    assert removed(entry, left) == pytest.approx(removed(entry, right), rel=1e-9)
    probe = (4.0, 10.0, 30.0 - 10.0)
    assert not inside(left.outputs[0].mesh, probe)
    assert inside(right.outputs[0].mesh, probe)
    assert left.answered == {} and right.answered == {}


def test_a_clearly_nearer_turn_is_taken_without_asking() -> None:
    """30 Grad gedreht ist eindeutig: die Ecken wandern um 30 und nicht um 60 Grad."""
    entry = block(height=30.0)
    r = 10.0 * math.sqrt(2.0)
    turned = [
        (
            r * math.cos(math.radians(45.0 + 30.0 + 90.0 * k)),
            r * math.sin(math.radians(45.0 + 30.0 + 90.0 * k)),
        )
        for k in range(4)
    ]
    # Die Ecken beginnen absichtlich an einer anderen Stelle und laufen andersherum —
    # Klickreihenfolge und Drehsinn der Zeichnung sind Zufall.
    upper = polygon(*reversed(turned[1:] + turned[:1]))
    lower = polygon((-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0))
    asked = Asked()
    result = run(
        "sketch_loft_cut", entry, ask=asked, sketch=lower, top="drawn", top_sketch=upper, depth=20.0
    )
    assert asked.questions == []
    # Auf halber Tiefe: Mitte der Ecke (10 | 10) und ihrer um 30 Grad gedrehten Partnerin.
    partner = (r * math.cos(math.radians(75.0)), r * math.sin(math.radians(75.0)))
    mid = ((10.0 + partner[0]) / 2.0, (10.0 + partner[1]) / 2.0)
    shrink = 0.9
    assert not inside(result.outputs[0].mesh, (mid[0] * shrink, mid[1] * shrink, 20.0))


def test_outlines_that_cannot_be_paired_are_refused_with_the_reason() -> None:
    """Unvereinbar: ein Umriss oben, zwei unten — was womit, stünde nicht fest."""
    entry = block(height=30.0)
    lower = polygon((-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0))
    two = sketch_to_text(
        Sketch(
            plane="plane:xy",
            elements=(
                SketchElement("circle", ((-5.0, 0.0), (-3.0, 0.0))),
                SketchElement("circle", ((5.0, 0.0), (7.0, 0.0))),
            ),
            constraints=(),
        )
    )
    with pytest.raises(ValidationError) as caught:
        run("sketch_loft_cut", entry, sketch=lower, top="drawn", top_sketch=two, depth=10.0)
    assert caught.value.constraint == "region_count"
    assert caught.value.suggestions


def test_a_transition_on_a_mesh_keeps_its_form_within_the_facet_sag() -> None:
    """Formabweichung: Derselbe Übergang in ``cube_clean.stl`` und im exakten Würfel.

    Jeder Eckpunkt des Netzergebnisses liegt höchstens ``MAX_FACET_SAG`` von der
    Oberfläche des exakten Ergebnisses entfernt — die Grenze, mit der das
    Werkzeug vernetzt wird. Oben Quadrat 10 × 10, unten Kreis Ø6, 12 mm tief.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt

    from app.core.brep import edit

    circle = sketch_to_text(
        Sketch(
            plane="plane:xy",
            elements=(SketchElement("circle", ((0.0, 0.0), (3.0, 0.0))),),
            constraints=(),
        )
    )
    params: dict[str, object] = {
        "shape": "rectangle",
        "length": 10.0,
        "width": 10.0,
        "top": "drawn",
        "top_sketch": circle,
        "depth": 12.0,
    }
    mesh_entry = corpus("cube_clean.stl")
    mesh_result = run("sketch_loft_cut", mesh_entry, **params)
    exact_entry = SceneObject(
        id="obj_1",
        name="Würfel",
        mesh=edit.moved(edit.box(20.0, 20.0, 20.0), (0.0, 0.0, -10.0)),
        kind="brep",
    )
    exact_result = run("sketch_loft_cut", exact_entry, **params)
    exact = exact_result.outputs[0].mesh
    assert isinstance(exact, Solid)

    vertices = np.asarray(mesh_result.outputs[0].mesh.raw.vertices, dtype=float)
    assert len(vertices) > 12, "das Netz trägt den Übergang"
    worst = 0.0
    for vertex in vertices[:: max(1, len(vertices) // 400)]:
        probe = BRepExtrema_DistShapeShape(
            BRepBuilderAPI_MakeVertex(gp_Pnt(*vertex)).Vertex(), exact.shape
        )
        worst = max(worst, float(probe.Value()))
    assert worst <= MAX_FACET_SAG + 1e-6
    assert removed(mesh_entry, mesh_result) == pytest.approx(
        removed(exact_entry, exact_result), rel=0.02
    )


# --- Über den Stapel: Parameter ändern, Undo, speichern, öffnen ------------------


def test_a_groove_survives_a_parameter_change_an_undo_and_a_round_trip(
    profile: Any, tmp_path: Path
) -> None:
    """Kundenweg „Ringnut" (Konzept §13.9) über den Verlauf und die Projektdatei."""
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, load, new_project, save

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Welle",
        [OperationDraft(op="create_brep_cylinder", params={"diameter": 20.0, "height": 40.0})],
    )
    history.apply(
        "Ringnut",
        [
            OperationDraft(
                op="sketch_revolve_cut",
                inputs=("obj_1",),
                params={
                    "shape": "rectangle",
                    "length": 3.0,
                    "width": 3.0,
                    "offset": 8.0,
                    "axis_z": 18.0,
                },
            )
        ],
    )
    whole = math.pi * 100.0 * 40.0

    def volume() -> float:
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        assert result.complete, [finding.message for finding in result.scene.report.findings]
        (entry,) = result.scene.objects.values()
        return float(entry.mesh.volume)

    assert volume() == pytest.approx(whole - 108.0 * math.pi, rel=1e-9)

    groove = project.document.ops[-1]
    history.change_params(groove.id, {**groove.params, "width": 5.0})
    assert volume() == pytest.approx(whole - 180.0 * math.pi, rel=1e-9)

    history.undo()
    assert volume() == pytest.approx(whole - 108.0 * math.pi, rel=1e-9)

    saved = save(project, tmp_path / "welle.p3d")
    project = load(saved)
    assert volume() == pytest.approx(whole - 108.0 * math.pi, rel=1e-9)
