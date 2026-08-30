"""Oberflächentexturen (Konzept P15 §7 Etappe 5, D8).

SindriCADs beworbenes Kernfeature, und das einzige aus ihrer Liste, das
Solidon gar nicht hatte. Zwei Dinge übernehmen wir ausdrücklich, weil sie
richtig sind: die Muster werden als **exakte Gitter** gebaut statt aus einem
abgetasteten Höhenfeld — sonst druckt ein Rändel gerundeten Brei statt
scharfer Rauten — und sie können **einwärts schneiden statt auswärts prägen**.

Eines kommt dazu, das dort niemand hat: die Prüfung, ob das Muster überhaupt
druckbar ist. Eine Rille, die schmaler ist als die Düse, wird nicht gedruckt,
sondern verschwindet.
"""

from __future__ import annotations

import math

import pytest

from app.core.errors import ValidationError
from app.core.geom import texture_ops
from app.core.types import PrinterProfile

NOZZLE = PrinterProfile(id="test", title="Test", build_volume=(220.0, 220.0, 250.0))


def test_every_pattern_reaches_the_edge_of_its_field() -> None:
    """Kein Muster hat einen Saum, den niemand bestellt hat.

    Bis an den Rand heißt nicht *auf* den Rand: ein Steg-Muster besteht aus
    Stegen **und** Rillen, und wo am Rand eine Rille liegt, endet das letzte
    Polygon davor. Was nicht sein darf, ist ein leerer Streifen breiter als
    eine Teilung — das wäre ein Muster, das zu früh aufhört.

    Und die Fläche muss dazwischen liegen: ein Muster, das alles bedeckt, ist
    keines, und eines, das fast nichts bedeckt, auch nicht.
    """
    width, height, pitch = 40.0, 30.0, 4.0
    for pattern in texture_ops.PATTERNS:
        shapes = texture_ops.pattern_shapes(pattern, width, height, pitch, seed=7)
        assert shapes, f"{pattern} liefert nichts"
        low_x = min(shape.bounds[0] for shape in shapes)
        low_y = min(shape.bounds[1] for shape in shapes)
        high_x = max(shape.bounds[2] for shape in shapes)
        high_y = max(shape.bounds[3] for shape in shapes)
        assert low_x <= -width / 2.0 + pitch, f"{pattern} lässt links einen Saum"
        assert high_x >= width / 2.0 - pitch, f"{pattern} lässt rechts einen Saum"
        assert low_y <= -height / 2.0 + pitch, f"{pattern} lässt unten einen Saum"
        assert high_y >= height / 2.0 - pitch, f"{pattern} lässt oben einen Saum"

        covered = sum(shape.area for shape in shapes)
        assert 0.1 < covered / (width * height) < 0.95, (
            f"{pattern} bedeckt {covered / (width * height):.0%} — das ist kein Muster"
        )


def test_a_pattern_is_deterministic_for_the_same_seed() -> None:
    """Regel 9: gleicher Startwert, gleiches Ergebnis — auch bei Voronoi."""
    first = texture_ops.pattern_shapes("voronoi", width=30.0, height=30.0, pitch=6.0, seed=42)
    again = texture_ops.pattern_shapes("voronoi", width=30.0, height=30.0, pitch=6.0, seed=42)
    other = texture_ops.pattern_shapes("voronoi", width=30.0, height=30.0, pitch=6.0, seed=43)

    assert [shape.area for shape in first] == pytest.approx([shape.area for shape in again])
    assert [shape.area for shape in first] != pytest.approx([shape.area for shape in other])


def test_a_hexagon_pattern_has_hexagonal_cells() -> None:
    """Eine Wabe ist eine Wabe: sechs Ecken, und die Fläche stimmt gegen die
    Formel für das regelmäßige Sechseck."""
    shapes = texture_ops.pattern_shapes("hexagon", width=40.0, height=40.0, pitch=8.0, seed=0)
    inner = [shape for shape in shapes if shape.area > 1.0]
    assert inner, "eine Wabe mit acht Millimetern Teilung hat ganze Zellen"

    # Randzellen sind beschnitten; die vollen haben die Fläche der Formel.
    full = max(shape.area for shape in inner)
    radius = 8.0 / 2.0 * texture_ops.HEX_FILL
    expected = 3.0 * math.sqrt(3.0) / 2.0 * radius**2
    assert full == pytest.approx(expected, rel=0.02)


# --- die Prüfung, die dort niemand hat -------------------------------------------


def test_a_structure_thinner_than_the_nozzle_is_refused() -> None:
    """E1: eine Rille, die schmaler ist als die Düse, wird nicht gedruckt —
    sie verschwindet.

    Das ist der Unterschied zwischen gleichziehen und übertreffen. SindriCAD
    kann dieselbe Textur anbieten; ob sie druckbar ist, weiß dort niemand.
    """
    with pytest.raises(ValidationError) as problem:
        texture_ops.check_printable("rib", pitch=0.3, depth=1.0, printer=NOZZLE)

    assert problem.value.field == "pitch"
    # Regel 17: der Fehler nennt, was jetzt möglich ist.
    assert problem.value.suggestions, "ein Fehler endet nie mit „fehlgeschlagen“"


def test_a_depth_below_one_layer_is_refused() -> None:
    """Eine Prägung flacher als eine Schicht ist keine Prägung."""
    with pytest.raises(ValidationError) as problem:
        texture_ops.check_printable("rib", pitch=3.0, depth=0.05, printer=NOZZLE)

    assert problem.value.field == "depth"


def test_a_sensible_texture_passes() -> None:
    """Zwei Millimeter Teilung, ein halber Millimeter tief — das druckt jeder."""
    texture_ops.check_printable("rib", pitch=2.0, depth=0.5, printer=NOZZLE)


# --- die Operation gegen einen echten Körper ------------------------------------


def _run(seed: int | None = None, **params: object) -> object:
    """Die Operation über das Register, wie jede Oberfläche es täte.

    Der Startwert reist im Kontext, nicht als Parameter (Regel 9) — genau so
    gibt ihn auch der Stapel weiter.
    """
    import trimesh

    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshData
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Profile, Scene, SceneObject

    load_operations()
    spec = REGISTRY.get("apply_texture")
    plate = SceneObject(
        id="obj_1",
        name="Platte",
        mesh=MeshData.of(trimesh.creation.box(extents=(40.0, 30.0, 6.0))),
    )
    return spec.fn(
        OpContext(
            scene=Scene(objects={"obj_1": plate}, parameters={}),
            inputs=[plate],
            params=spec.params(**params),
            profile=Profile(printer=NOZZLE, material=None),
            quality="fine",
            seed=seed,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def _on_cylinder(diameter: float, bore: float = 0.0, **params: object) -> object:
    """Die Operation auf einem Rohr bekannter Breite — für die Wickelbefunde.

    **96 Segmente, nicht die Vorgabe.** Ein grob aufgelöster Zylinder ist ein
    Vielflach: Seine Flächenmitten liegen *innerhalb* des Nenndurchmessers, ein
    exakt passender Wickel schwebte dort und fiele ab. Der Test meldete damit
    einen Zerfall, den nur sein eigener Prüfkörper erzeugt hatte — die Galerie
    zeichnet ihre Dose aus demselben Grund mit ``segments=96``.

    ``bore`` bohrt das Rohr aus: Ein Muster, dessen Wickelzylinder kleiner ist
    als der Körper, verschwindet in einem massiven Körper spurlos (dann meldet
    ``boolean.without_effect``, und das ist ein anderer Befund). Erst über
    einem Hohlraum liegt es frei und fällt ab — die Lage des ⌀75-Deckels.
    """
    import trimesh

    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshData
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Profile, Scene, SceneObject

    load_operations()
    spec = REGISTRY.get("apply_texture")
    shape = trimesh.creation.cylinder(radius=diameter / 2.0, height=30.0, sections=96)
    if bore > 0.0:
        shape = trimesh.boolean.difference(
            [shape, trimesh.creation.cylinder(radius=bore / 2.0, height=40.0, sections=96)]
        )
    body = SceneObject(id="obj_1", name="Rohr", mesh=MeshData.of(shape))
    return spec.fn(
        OpContext(
            scene=Scene(objects={"obj_1": body}, parameters={}),
            inputs=[body],
            params=spec.params(**params),
            profile=Profile(printer=NOZZLE, material=None),
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def _wrapped(diameter: float, wrap_diameter: float, bore: float = 0.0) -> object:
    """Ein umlaufendes Rändelmuster.

    **Die Breite ist der Umfang, nicht irgendeine Zahl.** Ein Band, das nicht
    genau einmal herumreicht, lässt an der Naht Elemente in der Luft stehen —
    dann meldet die Teilezahl einen Zerfall, den nur der Prüfstand erzeugt hat.
    Das Galerie-Rezept trägt aus demselben Grund ``width = 205.1``, was
    π mal 65,3 ist.
    """
    return _on_cylinder(
        diameter,
        bore,
        pattern="knurl_diamond",
        pitch=3.0,
        depth=0.8,
        mode="raised",
        wrap="cylinder",
        wrap_diameter=wrap_diameter,
        width=math.pi * wrap_diameter,
        height=10.0,
        z=0.0,
    )


def test_a_pattern_that_falls_off_the_body_is_reported() -> None:
    """**Die Lage, die der Durchmesser nicht sieht** (gemessen 30.08.2026).

    Läuft das Muster um einen Zylinder, der *kleiner* ist als der Körper, ragt
    nichts hinaus — :func:`_wrap_beyond_body` schweigt zu Recht. Es liegt dann
    innerhalb der Fläche, berührt sie nirgends, und die Vereinigung legt
    Hunderte lose Stücke daneben.

    Am ⌀75-Deckel der Galerie-Dose mit dem gealterten ``wrap_diameter`` von
    65,3 waren es **553 Komponenten**, wo eine war: wasserdicht, plausibles
    Volumen, auf dem Vorschaubild ein glatter Deckel. Was fehlte, sah aus wie
    eine Gestaltungsentscheidung.

    Die Teilezahl ist binär statt toleranzbehaftet und fängt beide Richtungen —
    dieselbe Bauart wie ``parts._hanging_loose``.
    """
    # Ein Rohr, außen 80 und innen 60: Die Wand steht zwischen Radius 30 und
    # 40. Der Wickel läuft auf 50, also auf Radius 25 — im Loch, unter der
    # Wand. Genau die Lage des ⌀75-Deckels, dessen Muster auf 65,3 lief,
    # während sein Rand bei 80,3 stand.
    result = _wrapped(80.0, 50.0, bore=60.0)

    codes = [finding.code for finding in result.findings]
    assert "texture.fell_apart" in codes, f"kein Befund, gemeldet wurde: {codes}"

    apart = next(f for f in result.findings if f.code == "texture.fell_apart")
    assert int(apart.values["before"]) == 1, "der Träger war vorher schon zerteilt"
    assert int(apart.values["after"]) > 1, "nichts ist abgefallen — der Test misst nichts"
    assert apart.severity == "error", "lose Stücke sind kein Schönheitsfehler"


def test_a_pattern_that_holds_says_nothing_about_parts() -> None:
    """Die Gegenprobe: Ein Muster, das hängt, wird nicht gemeldet.

    Ohne sie bliebe der Test oben grün, auch wenn die Prüfung jede Lage
    meldete. Und die Zahl davor muss stimmen: Wäre der Träger schon vorher
    zerteilt, wäre jedes „zerfallen" oben aus dem falschen Grund richtig.
    """
    result = _wrapped(50.0, 50.0)

    codes = [finding.code for finding in result.findings]
    assert "texture.fell_apart" not in codes, f"Fehlalarm bei haltendem Muster: {codes}"


def test_an_engraved_pattern_may_divide_the_body() -> None:
    """Vertieft schneidet, und Schneiden darf teilen.

    Dieselbe Ausnahme, die ``parts._hanging_loose`` für abziehende Bausteine
    macht: Bei manchen Mustern ist das Teilen der Zweck, und ein Befund wäre
    eine Warnung vor der eigenen Absicht.

    **Geprüft wird die Funktion und nicht der Weg über die Operation**, und das
    ist hier keine Bequemlichkeit: Über die Operation gibt es diese Lage nicht.
    Ein Rändelmuster prägt Vertiefungen, keine Durchbrüche — gemessen an einem
    Rohr mit 2 mm Wand und einem Muster von 2,5 mm Tiefe blieb der Körper ein
    Stück. Ein Test mit einem geschnittenen Muster wäre grün geblieben, auch
    wenn die Bedingung ``mode != "raised"`` fehlte, und hätte damit nichts
    gehalten. Die Mutationsprobe hat genau das gezeigt.
    """
    from types import SimpleNamespace

    from app.core.geom.texture_ops import _fell_apart

    vorher = SimpleNamespace(component_count=1)
    nachher = SimpleNamespace(component_count=42)

    assert _fell_apart(vorher, nachher, "engraved") is None, (
        "ein Schnitt, der teilt, wurde als Zerfall gemeldet"
    )
    assert _fell_apart(vorher, nachher, "raised") is not None, (
        "die Gegenprobe: bei erhabenem Muster muss dieselbe Lage gemeldet werden"
    )


def test_a_wrap_wider_than_the_body_is_reported() -> None:
    """**Die stille Lage, an der die Galerie-Dose hing** (30.08.2026).

    Der Wickeldurchmesser wird einmal aus einer angeklickten Fläche abgelesen
    und steht danach als feste Zahl im Schritt. Ändert ein Projektparameter die
    Geometrie, altert die Zahl mit — und das Muster läuft um einen Zylinder,
    den es nicht mehr gibt.

    Gemessen an ``schraubdose.p3d``: Ihr Rezept trägt ``wrap_diameter = 65.3``.
    Stellt der Kunde die Dose auf 50 mm, steht die Rändelung 11,5 mm über den
    Deckelrand. Der Druck gelingt, das Teil ist Ausschuss, und gemeldet hat es
    vorher nichts.
    """
    result = _wrapped(50.0, 65.3)

    codes = [finding.code for finding in result.findings]
    assert "texture.wrap_beyond_body" in codes, f"kein Befund, gemeldet wurde: {codes}"

    beyond = next(f for f in result.findings if f.code == "texture.wrap_beyond_body")
    assert beyond.values["wrap_diameter_mm"] == pytest.approx(65.3)
    assert beyond.values["body_diameter_mm"] == pytest.approx(50.0, abs=0.1)


def test_a_matching_wrap_says_nothing() -> None:
    """Die Gegenprobe: Ein Befund, der immer kommt, ist keiner.

    Ohne sie bliebe der Test oben grün, auch wenn die Prüfung jede Lage
    meldete — und der nächste Kunde läse eine Warnung, die nichts bedeutet.
    """
    result = _wrapped(50.0, 50.0)

    codes = [finding.code for finding in result.findings]
    assert "texture.wrap_beyond_body" not in codes, f"Fehlalarm bei passender Lage: {codes}"


def test_a_wrap_smaller_than_the_body_is_left_alone() -> None:
    """Der berechtigte Fall, der nicht gemeldet werden darf.

    Ein Muster auf einer kleinen Zylinderfläche eines großen Körpers hat einen
    kleineren Wickeldurchmesser als dessen Hüllquader — das ist keine gealterte
    Zahl, sondern die richtige. Gemeldet wird nur, was hinausragen **muss**:
    Ein Zylinder breiter als der ganze Körper kann keine seiner Flächen sein.
    """
    result = _wrapped(80.0, 30.0)

    codes = [finding.code for finding in result.findings]
    assert "texture.wrap_beyond_body" not in codes, f"Fehlalarm bei kleiner Fläche: {codes}"


def test_a_raised_texture_adds_material_and_an_engraved_one_removes_it() -> None:
    """Erhaben legt auf, vertieft schneidet ein — und beides misst sich am
    Volumen gegen den nackten Körper.

    Der Quader hat 40 × 30 × 6 = 7200 mm³. Beide Richtungen müssen davon
    abweichen, und zwar in entgegengesetzte Richtung; ein Muster, das nichts
    ändert, wäre eines, das nicht angekommen ist.
    """
    plain = 40.0 * 30.0 * 6.0

    raised = _run(pattern="rib", width=30.0, height=20.0, pitch=2.0, depth=0.6, z=3.0)
    engraved = _run(
        pattern="rib", width=30.0, height=20.0, pitch=2.0, depth=0.6, z=3.0, mode="engraved"
    )

    grown = raised.outputs[0].mesh.volume
    cut = engraved.outputs[0].mesh.volume
    assert grown > plain, "erhaben legt Material auf"
    assert cut < plain, "vertieft nimmt Material weg"
    # Symmetrisch: was oben dazukommt, fehlt unten — dieselben Stege.
    assert grown - plain == pytest.approx(plain - cut, rel=0.05)


def test_an_engraved_texture_beside_the_body_says_so() -> None:
    """„Wer Boolesches rechnet, fragt danach — ohne Ausnahme." Ein Muster weit
    neben dem Körper trug nichts ab und meldete nichts — dieselbe Auskunft, die
    Bohren, Stopfen und die Beschriftung längst geben (operationen.md)."""
    result = _run(
        pattern="rib",
        width=30.0,
        height=20.0,
        pitch=2.0,
        depth=0.6,
        x=200.0,
        z=3.0,
        mode="engraved",
    )

    assert result.outputs[0].mesh.volume == pytest.approx(40.0 * 30.0 * 6.0, rel=1e-6)
    assert "boolean.without_effect" in [finding.code for finding in result.findings]


def test_a_texture_that_cannot_print_is_refused_before_anything_is_built() -> None:
    """E1 an der Operation: die Frage kommt vor der Rechnung.

    Eine Teilung von 0,3 mm gegen eine 0,4-mm-Düse — das Muster verschwindet
    beim Drucken. Es gar nicht erst zu bauen ist schneller und ehrlicher, als
    einen Körper zu liefern, der glatt herauskommt.
    """
    with pytest.raises(ValidationError) as problem:
        _run(pattern="rib", width=20.0, height=20.0, pitch=0.3, depth=0.6, z=3.0)

    assert problem.value.field == "pitch"


def test_the_same_seed_gives_the_same_voronoi_body() -> None:
    """Regel 9: die Operation ist als ``deterministic=False`` deklariert und
    führt ihren Startwert — zweimal derselbe Wert, zweimal derselbe Körper."""
    first = _run(seed=5, pattern="voronoi", width=20.0, height=20.0, pitch=4.0, depth=0.5, z=3.0)
    again = _run(seed=5, pattern="voronoi", width=20.0, height=20.0, pitch=4.0, depth=0.5, z=3.0)
    other = _run(seed=6, pattern="voronoi", width=20.0, height=20.0, pitch=4.0, depth=0.5, z=3.0)

    assert first.outputs[0].mesh.volume == pytest.approx(again.outputs[0].mesh.volume)
    assert first.outputs[0].mesh.volume != pytest.approx(other.outputs[0].mesh.volume)


# --- umlaufend auf einem Zylinder (Konzept P15 §7 Etappe 5) ---------------------


def _run_on_cylinder(**params: object) -> object:
    """Dieselbe Operation, aber auf einem stehenden Zylinder Ø 20, 30 hoch."""
    import trimesh

    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshData
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Profile, Scene, SceneObject

    load_operations()
    spec = REGISTRY.get("apply_texture")
    shaft = SceneObject(
        id="obj_1",
        name="Griff",
        mesh=MeshData.of(trimesh.creation.cylinder(radius=10.0, height=30.0, sections=128)),
    )
    return spec.fn(
        OpContext(
            scene=Scene(objects={"obj_1": shaft}, parameters={}),
            inputs=[shaft],
            params=spec.params(**params),
            profile=Profile(printer=NOZZLE, material=None),
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_a_wrapped_texture_grows_the_shaft_all_the_way_around() -> None:
    """Ein Rändel gehört um den Griff, nicht als Fleck darauf.

    Flach aufgelegt ragt das Feld an den Rändern in die Luft und trifft den
    Zylinder nur in seiner Mitte — genau der Grund, warum ein Griff bis hierhin
    nicht texturierbar war. Gemessen an der Hüllbox: sie muss in **beiden**
    Querrichtungen wachsen, denn ein umlaufendes Muster steht auch dort, wo
    das flache Feld nie hinkam.
    """
    result = _run_on_cylinder(
        pattern="knurl_diamond",
        wrap="cylinder",
        wrap_diameter=20.0,
        width=62.8,
        height=20.0,
        pitch=2.5,
        depth=0.6,
    )
    mesh = result.outputs[0].mesh
    size = mesh.bounds.size
    assert size[0] > 20.0, "in X über den nackten Durchmesser hinaus"
    assert size[1] > 20.0, "und in Y genauso — sonst klebt es auf einer Seite"
    assert size[2] == pytest.approx(30.0, abs=0.05), "die Höhe bleibt die Höhe"
    assert mesh.volume > math.pi * 100.0 * 30.0


def test_wrapping_without_a_diameter_says_what_is_missing() -> None:
    """Regel 17: ohne Durchmesser gibt es keinen Zylinder, um den etwas läuft."""
    with pytest.raises(ValidationError) as problem:
        _run_on_cylinder(pattern="rib", wrap="cylinder", wrap_diameter=0.0, width=20.0, height=10.0)
    assert problem.value.suggestions


def test_the_flat_way_is_untouched() -> None:
    """Die Vorgabe bleibt flach, und flach bleibt, was es war.

    Ein Umschalter, der die Vorgabe mitverändert, ist kein Umschalter, sondern
    eine stille Migration jeder bestehenden Datei (§16.1)."""
    from app.core.registry import REGISTRY

    spec = REGISTRY.get("apply_texture")
    wrap = next(entry for entry in spec.params.spec() if entry.name == "wrap")
    assert wrap.default == "flat"
