"""Gewinde ändern und verschließen — außen und innen, in beiden Kernen (P2.6).

Ein Gewinde ist eine bewendelte Strecke auf einem Schaft oder in einer
Bohrung. *Merkmal entfernen* nimmt außen den Gang bis auf den Kern und
schließt innen die Bohrung; *Merkmal ändern* setzt Durchmesser und Steigung
neu — mit demselben Bausteingewinde wie beim Einsetzen (``build.threaded``),
je Kern. Die Sollwerte sind Pappus über das Gangprofil (``shapes.ridge_profile``)
plus der Kern, wie in ``test_exact_parts._thread_volume``.
"""

from __future__ import annotations

import math
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.parts import build, shapes
from app.core.knowledge.parts.shapes import building
from app.core.types import Feature, Profile, SceneObject
from tests.helpers import exact_kernel
from tests.test_exact_parts import _thread_volume
from tests.test_missing_ops import run
from tests.test_thread_import import BASES

PLATE = (40.0, 40.0, 10.0)
PLATE_VOLUME = PLATE[0] * PLATE[1] * PLATE[2]
LENGTH = 8.0


def _root(diameter: float, pitch: float) -> float:
    return shapes.ridge_profile(diameter, pitch)[0][0]


def _built(kind: str, diameter: float, pitch: float, length: float, *, internal: bool) -> float:
    """Das Volumen des Bausteingewindes, wie der jeweilige Kern es baut.

    Exakt nach Pappus — der genähte Körper trifft ihn auf 2 · 10⁻⁷ (gemessen
    M8 × 1,25 × 8: 8 · 10⁻⁵ mm³). Am Netz das facettierte Netz selbst: Der Kern
    ist ein 48-Eck, der Gang ein Sehnenzug, zusammen 1,4 Prozent unter der
    Analytik. Geprüft wird hier, was die Operation zusammensetzt; wie treu
    ``build.threaded`` am Netz facettiert, prüft ``test_exact_parts``.
    """
    if kind == "brep":
        return _thread_volume(diameter, pitch, length, internal=internal)
    return float(build.threaded(diameter, pitch, length, internal=internal).volume)


def _cylinder(kind: str, radius: float, length: float) -> float:
    """Ein Zylinder, wie ihn der Kern schneidet: exakt rund, am Netz das 48-Eck des Werkzeugs."""
    if kind == "brep":
        return math.pi * radius**2 * length
    return float(shapes.cylinder(2.0 * radius, length).volume)


def _sunk(kind: str, diameter: float, pitch: float, length: float) -> float:
    """Was ein um den Überlapp eingesunkenes Gewinde im Sockel verliert.

    Nicht nur der Kern: Die Scheibe unter der Sockeloberfläche trägt den
    Gang anteilig — das Gewinde ist schraubensymmetrisch, jeder Querschnitt
    hat dieselbe Fläche, also ist es der Anteil ``Überlapp / Länge`` des
    ganzen Gewindes (am exakten M8 gemessen: 0,4303 statt 0,3447 mm³).
    """
    return _built(kind, diameter, pitch, length, internal=False) * BOOLEAN_OVERLAP / length


def _bore(diameter: float, pitch: float) -> float:
    """Die Bohrung unter einem Innengewinde mit dieser Bezeichnung — zwei Gangtiefen enger.

    Ein Merkmal nennt innen den Grund-Ø der Gänge (so schreibt es der Baustein,
    so lesen es beide Kerne); ``build.threaded`` rechnet in der Bohrung.
    """
    return diameter - 2.0 * pitch * shapes.RIDGE_SHARE


def _thread_feature(
    centre: tuple[float, float, float], *, internal: bool, length: float, handedness: str = "right"
) -> Feature:
    return Feature(
        id="thread_1",
        kind="thread",
        provenance="generated",
        params={
            "diameter": 6.0,
            "pitch": 1.0,
            "handedness": handedness,
            "centre": centre,
            "axis": (0.0, 0.0, 1.0),
            "internal": internal,
            "length": length,
        },
        measure_sources=dict.fromkeys(
            ("diameter", "pitch", "centre", "axis", "length"), "parameter"
        ),
    )


def _plate(kind: str) -> Any:
    from app.core.brep import edit

    if kind == "brep":
        return edit.box(*PLATE)
    return as_mesh_data(edit.box(*PLATE))


def _joined(kind: str, plate: Any, tool: Any, how: str) -> Any:
    if kind == "brep":
        from app.core.brep import edit

        return edit.unified(edit.boolean(how, [plate, tool]))  # type: ignore[arg-type]
    return boolean(how, [plate, tool], quality="fine").mesh  # type: ignore[arg-type]


@cache
def _studded_plate(kind: str, handedness: str = "right") -> SceneObject:
    """Platte 40 x 40 x 10 mit einem aufgesetzten M6 x 1 der Länge 8, um den Überlapp gesenkt.

    Einmal je Modul gebaut: Die Operationen lesen ihren Eingang nur, und ein
    exakter Träger mit Gewinde kostete je Test eine Vereinigung und ein
    Volumenintegral (Review 21.09.2026).
    """
    bottom = PLATE[2] - BOOLEAN_OVERLAP
    if kind == "brep":
        with building("brep"):
            stud = build.threaded(6.0, 1.0, LENGTH, bottom=bottom)
    else:
        stud = build.threaded(6.0, 1.0, LENGTH, bottom=bottom)
    body = _joined(kind, _plate(kind), stud, "union")
    feature = _thread_feature(
        (0.0, 0.0, bottom + LENGTH / 2.0), internal=False, length=LENGTH, handedness=handedness
    )
    return SceneObject(
        id="obj_1", name="Platte", mesh=body, kind=kind, features={feature.id: feature}
    )


@cache
def _tapped_plate(kind: str) -> SceneObject:
    """Dieselbe Platte mit einem durchgehenden M6 × 1 darin — einmal je Modul."""
    if kind == "brep":
        with building("brep"):
            tap = build.threaded(
                _bore(6.0, 1.0),
                1.0,
                PLATE[2] + 2.0 * BOOLEAN_OVERLAP,
                internal=True,
                bottom=-BOOLEAN_OVERLAP,
            )
    else:
        tap = build.threaded(
            _bore(6.0, 1.0),
            1.0,
            PLATE[2] + 2.0 * BOOLEAN_OVERLAP,
            internal=True,
            bottom=-BOOLEAN_OVERLAP,
        )
    body = _joined(kind, _plate(kind), tap, "difference")
    feature = _thread_feature((0.0, 0.0, PLATE[2] / 2.0), internal=True, length=PLATE[2])
    return SceneObject(
        id="obj_1", name="Platte", mesh=body, kind=kind, features={feature.id: feature}
    )


def _stays(result: Any, kind: str) -> SceneObject:
    output = result.outputs[0]
    assert output.kind == kind
    assert not any(finding.converts_exact_body for finding in result.findings)
    if kind == "brep":
        assert output.mesh.is_closed and output.mesh.solid_count == 1
    else:
        assert isinstance(output.mesh, MeshData)
        assert output.mesh.is_watertight and output.mesh.component_count == 1
    return output


def _tolerance(kind: str) -> float:
    """Exakt die Nähgenauigkeit des Gewindes (10⁻⁵); am Netz seine Facettierung."""
    return 1e-5 if kind == "brep" else 2e-3


@pytest.fixture(params=["brep", "mesh"])
def kind(request: Any) -> str:
    if request.param == "brep":
        exact_kernel()
    load_operations()
    return str(request.param)


def test_the_stud_and_the_tapped_hole_measure_as_built(kind: str) -> None:
    """Die Fixtures sind, was sie vorgeben: Platte plus Bolzen, Platte minus Gewindebohrung."""
    stud = _studded_plate(kind)
    added = _built(kind, 6.0, 1.0, LENGTH, internal=False) - _sunk(kind, 6.0, 1.0, LENGTH)
    assert float(stud.mesh.volume) - PLATE_VOLUME == pytest.approx(added, rel=_tolerance(kind))
    tapped = _tapped_plate(kind)
    cut = _built(kind, _bore(6.0, 1.0), 1.0, PLATE[2], internal=True)
    assert PLATE_VOLUME - float(tapped.mesh.volume) == pytest.approx(cut, rel=_tolerance(kind))


def test_removing_an_outer_thread_leaves_the_plain_core(kind: str, profile: Profile) -> None:
    """*Merkmal entfernen* nimmt außen den Gang bis auf den Kern — der Kern bleibt stehen."""
    source = _studded_plate(kind)
    result = run("remove_feature", source, profile, at_feature="thread_1")
    output = _stays(result, kind)
    # Der Kern steht vom Sockel bis zur alten Spitze; der eingesunkene Anteil ist Sockelmaterial.
    # Gemessen wird das, was die Operation bewirkt — der Kern über der Platte —, nicht die
    # Platte mit: Auf die ganze Platte bezogen wäre die Schranke größer als der Gang selbst.
    core = _cylinder(kind, _root(6.0, 1.0), LENGTH - BOOLEAN_OVERLAP)
    assert float(output.mesh.volume) - PLATE_VOLUME == pytest.approx(core, rel=_tolerance(kind))
    assert "thread_1" not in output.features
    assert any(finding.code == "remove_feature.gone" for finding in result.findings)


def test_closing_an_inner_thread_fills_the_bore(kind: str, profile: Profile) -> None:
    """*Merkmal entfernen* schließt innen die Bohrung: Übrig bleibt die volle Platte."""
    source = _tapped_plate(kind)
    result = run("remove_feature", source, profile, at_feature="thread_1")
    output = _stays(result, kind)
    assert float(output.mesh.volume) == pytest.approx(
        PLATE_VOLUME, rel=1e-9 if kind == "brep" else 1e-6
    )
    assert "thread_1" not in output.features


def test_changing_an_outer_thread_recuts_it_on_the_same_axis(kind: str, profile: Profile) -> None:
    """*Merkmal ändern* setzt Durchmesser und Steigung neu, an derselben Achse und Mitte."""
    source = _studded_plate(kind)
    result = run("resize_feature", source, profile, at_feature="thread_1", diameter=8.0, pitch=1.25)
    output = _stays(result, kind)
    stud = _built(kind, 8.0, 1.25, LENGTH, internal=False) - _sunk(kind, 8.0, 1.25, LENGTH)
    assert float(output.mesh.volume) - PLATE_VOLUME == pytest.approx(stud, rel=_tolerance(kind))
    changed = output.features["thread_1"]
    assert changed.kind == "thread"
    assert changed.params["diameter"] == 8.0 and changed.params["pitch"] == 1.25
    assert changed.params["internal"] is False
    assert changed.params["centre"] == pytest.approx(
        (0.0, 0.0, PLATE[2] - BOOLEAN_OVERLAP + LENGTH / 2.0)
    )
    # Unabhängig nachgemessen: die Erkennung liest das neue Gewinde.
    if kind == "brep":
        from app.core.brep.features import features_of

        found = [f for f in features_of(output.mesh).values() if f.kind == "thread"]
    else:
        from app.core.perceive.features import detect

        found = [f for f in detect(as_mesh_data(output.mesh)).values() if f.kind == "thread"]
    assert len(found) == 1
    assert found[0].params["diameter"] == pytest.approx(8.0, abs=0.05)
    assert found[0].params["pitch"] == pytest.approx(1.25, abs=0.02)


def test_changing_an_inner_thread_fills_and_recuts(kind: str, profile: Profile) -> None:
    """Innen heißt ändern: füllen und neu schneiden, mit dem Werkzeug in der Bohrung darunter."""
    source = _tapped_plate(kind)
    result = run("resize_feature", source, profile, at_feature="thread_1", diameter=8.0, pitch=1.25)
    output = _stays(result, kind)
    # Das Merkmal sagt M8 mal 1,25; das Werkzeug rechnet in der Bohrung darunter. Ohne die
    # Umrechnung wurde aus einer M6-Mutter eine mit Bohrung Ø 6 (Review, 21.09.2026).
    cut = _built(kind, _bore(8.0, 1.25), 1.25, PLATE[2], internal=True)
    assert PLATE_VOLUME - float(output.mesh.volume) == pytest.approx(cut, rel=_tolerance(kind))
    changed = output.features["thread_1"]
    assert changed.params["internal"] is True
    assert changed.params["diameter"] == 8.0 and changed.params["pitch"] == 1.25


def test_the_same_measures_change_nothing(kind: str, profile: Profile) -> None:
    """Dieselben Maße lassen den Körper stehen und sagen es als Befund."""
    source = _studded_plate(kind)
    result = run("resize_feature", source, profile, at_feature="thread_1", diameter=6.0, pitch=0.0)
    assert result.outputs[0] is source
    assert [finding.code for finding in result.findings] == ["resize_feature.unchanged"]


def test_a_left_hand_thread_is_refused_with_advice(kind: str, profile: Profile) -> None:
    """Ein belegtes Linksgewinde wird nicht still rechts neu geschnitten."""
    source = _studded_plate(kind, handedness="left")
    with pytest.raises(ValidationError) as caught:
        run("resize_feature", source, profile, at_feature="thread_1", diameter=8.0, pitch=1.25)
    assert caught.value.constraint == "left_handed"
    assert caught.value.suggestions


def test_a_pitch_that_leaves_no_core_is_refused(kind: str, profile: Profile) -> None:
    """Eine Steigung, die den Kern aufbraucht, ist eine Absage mit Vorschlag."""
    source = _studded_plate(kind)
    with pytest.raises(ValidationError) as caught:
        run("resize_feature", source, profile, at_feature="thread_1", diameter=6.0, pitch=6.0)
    assert caught.value.constraint == "thread_pitch"


def test_a_thread_without_a_length_says_so(kind: str, profile: Profile) -> None:
    """Ohne Strecke gibt es nichts zu verschließen — die Absage nennt sie."""
    source = _studded_plate(kind)
    short = {**source.features["thread_1"].params, "length": 0.0}
    feature = Feature(id="thread_1", kind="thread", provenance="generated", params=short)
    source = SceneObject(
        id="obj_1", name="Platte", mesh=source.mesh, kind=kind, features={"thread_1": feature}
    )
    with pytest.raises(ValidationError) as caught:
        run("remove_feature", source, profile, at_feature="thread_1")
    assert caught.value.constraint == "not_movable"
    assert "Strecke" in str(caught.value.detail)


def _corpus(name: str) -> Any:
    from app.core.brep import step

    return step.read((Path(__file__).parent / "data" / "threads" / f"{name}.step").read_bytes())


def _recognised(kind: str, solid: Any) -> tuple[SceneObject, Feature]:
    """Ein Körper aus dem Gewindekorpus mit dem Gewinde, wie der jeweilige Kern es liest."""
    if kind == "brep":
        from app.core.brep.features import features_of

        features = features_of(solid)
        body: Any = solid
    else:
        from app.core.perceive.features import detect

        body = as_mesh_data(solid)
        features = detect(body)
    threads = [feature for feature in features.values() if feature.kind == "thread"]
    assert len(threads) == 1, "der Korpus trägt genau ein Gewinde"
    source = SceneObject(id="obj_1", name="Korpus", mesh=body, kind=kind, features=features)
    return source, threads[0]


def test_a_recognised_rod_loses_its_thread_down_to_the_root(kind: str, profile: Profile) -> None:
    """``m6_rechts``: ein ISO-Gewinde Ø 6 über die ganze Stange — danach ein glatter Kern.

    Das ist der Zweig, den kein erzeugtes Merkmal fährt: Fuß und Kamm kommen
    vom Leser, die Enden liegen beide in der Luft. Der Kern bleibt um den
    Überlapp unter dem gemessenen Fuß — genau darauf geschnitten blieb exakt
    eine Rille von der Tiefe der Leserunsicherheit und am Netz blieben 52
    Splitter (``prepare_ops._remove_thread``).
    """
    exact_kernel()
    source, thread = _recognised(kind, _corpus("m6_rechts"))
    assert thread.provenance == "detected"
    length = float(thread.params["length"])
    if kind == "brep":
        inner = min(float(thread.params["root_radius"]), float(thread.params["crest_radius"]))
    else:
        # Der Netzleser nennt keine Radien; der Talgrund ist die innerste Ecke
        # der eigenen Dreiecke, eine Steigung von den Stirnflächen entfernt —
        # unabhängig von der Operation gemessen, mit derselben Frage.
        raw = as_mesh_data(source.mesh).raw
        corners = np.unique(np.asarray(raw.faces)[list(thread.face_indices)])
        relative = np.asarray(raw.vertices)[corners] - np.asarray(thread.params["centre"])
        along = relative @ np.asarray(thread.params["axis"])
        radial = np.linalg.norm(
            relative - np.outer(along, np.asarray(thread.params["axis"])), axis=1
        )
        # Die Ecken reichen um den Gangauslauf über den Kern hinaus; der Kern
        # selbst ist so lang, wie der Korpus gebaut wurde (``data/README.md``).
        assert float(along.max() - along.min()) == pytest.approx(12.0, abs=0.05)
        length = float(BASES["m6_rechts"]["length"])
        middle = float(along.max() + along.min()) / 2.0
        clear = length / 2.0 - float(thread.params["pitch"])
        inner = float(radial[np.abs(along - middle) < clear].min())
        assert 2.2 < inner < 2.45, "der ISO-Talgrund liegt bei 3 minus 0,6134"
    result = run("remove_feature", source, profile, at_feature=thread.id)
    output = _stays(result, kind)
    # Am Netz bleibt vom Gangauslauf, was innerhalb des Kerns über die
    # Stirnfläche hinausreicht: 4 · 10⁻³ mm³ auf 203, gemessen.
    assert float(output.mesh.volume) == pytest.approx(
        _cylinder(kind, inner - BOOLEAN_OVERLAP, length), rel=1e-6 if kind == "brep" else 1e-4
    )
    # Und nichts steht mehr außerhalb des Kerns — kein Rest der Stirnflächen.
    left = as_mesh_data(output.mesh).raw
    relative = np.asarray(left.vertices) - np.asarray(thread.params["centre"])
    along = relative @ np.asarray(thread.params["axis"])
    radial = np.linalg.norm(relative - np.outer(along, np.asarray(thread.params["axis"])), axis=1)
    assert float(radial.max()) <= inner - BOOLEAN_OVERLAP + 1e-6
    assert thread.id not in output.features


def test_a_recognised_tapped_block_closes_to_the_plain_block(profile: Profile) -> None:
    """``m8_innen``: Block 20 × 20 × 10 minus Innengewinde — zu ist er wieder der Block."""
    exact_kernel()
    source, thread = _recognised("brep", _corpus("m8_innen"))
    assert thread.params["internal"] is True
    result = run("remove_feature", source, profile, at_feature=thread.id)
    output = _stays(result, "brep")
    # Der Leser nennt die Strecke auf ein Millionstel; so weit steht der Stopfen
    # über der Stirnfläche — gemessen 7 · 10⁻⁵ mm³ auf 4000.
    assert float(output.mesh.volume) == pytest.approx(20.0 * 20.0 * 10.0, rel=1e-7)


def test_a_recognised_rod_recut_carries_only_the_set_thread(profile: Profile) -> None:
    """Auf M8 × 1,25 geschnitten steht danach **ein** Gewinde da — das gesetzte.

    Ein behaupteter Übergang ließ die Erkennung daneben ein zweites unter
    frischem Namen anlegen (Review, 21.09.2026); das Volumen ist das ganze
    Bausteingewinde, denn die Hülle nahm die ganze Stange.
    """
    exact_kernel()
    source, thread = _recognised("brep", _corpus("m6_rechts"))
    result = run("resize_feature", source, profile, at_feature=thread.id, diameter=8.0, pitch=1.25)
    output = _stays(result, "brep")
    length = float(thread.params["length"])
    assert float(output.mesh.volume) == pytest.approx(
        _thread_volume(8.0, 1.25, length, internal=False), rel=_tolerance("brep")
    )
    threads = [f for f in output.features.values() if f.kind == "thread"]
    assert [f.id for f in threads] == [thread.id]
    assert threads[0].provenance == "generated"
    assert not any(finding.code == "resize_feature.feature_lost" for finding in result.findings)


def test_a_mesh_read_thread_is_not_refused_as_left_handed(profile: Profile) -> None:
    """Ein am Netz gelesenes Rechtsgewinde sperrt nicht.

    Bis zum 22.09.2026 riet der Netzleser die Händigkeit am gedruckten Profil
    (``build.threaded(6, 1, 8)``: Netz „left“, exakt „right“), und die Auskunft
    hieß ``fit`` — sie zählte nicht. Seit er an den Kanten misst, heißt sie
    ``facets`` und stimmt; ein Rechtsgewinde bleibt änderbar.
    """
    load_operations()
    source, thread = _recognised("mesh", _corpus("m6_rechts"))
    assert thread.measure_sources.get("handedness") == "facets"
    assert thread.params["handedness"] == "right"
    result = run("resize_feature", source, profile, at_feature=thread.id, diameter=8.0, pitch=1.25)
    output = _stays(result, "mesh")
    assert output.features[thread.id].params["diameter"] == 8.0


def test_a_mesh_read_left_hand_thread_is_refused(profile: Profile) -> None:
    """Ein am Netz gemessenes Linksgewinde sperrt das Ändern — wie am exakten Körper.

    Vorher galt am Netz jede Händigkeit als geraten, und *Merkmal ändern*
    schnitt ein Linksgewinde still rechts neu (P2.5).
    """
    exact_kernel()
    from tests.test_thread_import import _mirrored

    load_operations()
    source, thread = _recognised("mesh", _mirrored(_corpus("m6_rechts")))
    assert thread.params["handedness"] == "left"
    assert thread.measure_sources.get("handedness") == "facets"
    with pytest.raises(ValidationError) as caught:
        run("resize_feature", source, profile, at_feature=thread.id, diameter=8.0, pitch=1.25)
    assert caught.value.constraint == "left_handed"


def test_a_natively_read_left_hand_thread_is_refused(profile: Profile) -> None:
    """Ein an den Kanten gelesenes Linksgewinde sperrt das Ändern — der Beleg ist nativ."""
    exact_kernel()
    from tests.test_thread_import import _mirrored

    source, thread = _recognised("brep", _mirrored(_corpus("m6_rechts")))
    assert thread.params["handedness"] == "left"
    with pytest.raises(ValidationError) as caught:
        run("resize_feature", source, profile, at_feature=thread.id, diameter=8.0, pitch=1.25)
    assert caught.value.constraint == "left_handed"


def test_a_multi_start_thread_is_refused_instead_of_becoming_single(profile: Profile) -> None:
    """Ein mehrgängiges Gewinde wird nicht still eingängig neu geschnitten."""
    exact_kernel()
    source, thread = _recognised("brep", _corpus("zweigaengig"))
    assert thread.params["starts"] == 2
    with pytest.raises(ValidationError) as caught:
        run("resize_feature", source, profile, at_feature=thread.id, diameter=8.0, pitch=1.25)
    assert caught.value.constraint == "multi_start"
    assert caught.value.suggestions


@pytest.mark.parametrize("operation", ["resize_feature", "remove_feature"])
def test_a_tapered_thread_is_refused_instead_of_cut_with_cylinders(
    operation: str, profile: Profile
) -> None:
    """Ein kegeliges Rohrgewinde wird weder zylindrisch neu geschnitten noch entfernt.

    Hülle, Kern und Füllung der Gewindehandlungen sind Zylinder; an einem
    Kegel (1:16, ``konisch.step``) trügen sie ein Ende ab und ließen das andere
    stehen. Der Leser kennt den Kegel seit dem 22.09.2026 (P2.5), die
    Handlungen sagen deshalb ab statt still falsch zu schneiden.
    """
    exact_kernel()
    source, thread = _recognised("brep", _corpus("konisch"))
    assert thread.params["taper"] > 0.0
    values = {"diameter": 12.0, "pitch": 1.5} if operation == "resize_feature" else {}
    with pytest.raises(ValidationError) as caught:
        run(operation, source, profile, at_feature=thread.id, **values)
    assert caught.value.constraint == "tapered"
    assert caught.value.suggestions


def test_closing_a_blind_generated_thread_leaves_no_pocket(profile: Profile) -> None:
    """Hinter dem Grund liegt Material: Der Stopfen greift hinein statt davor zu enden.

    Ein Rückzug um den Überlapp — gedacht für den eingesunkenen Bolzen — ließ
    hier 0,28 mm³ als eingeschlossenen Hohlraum stehen (Review, 21.09.2026).
    """
    load_operations()
    depth = 6.0
    tap = build.threaded(
        _bore(6.0, 1.0), 1.0, depth + BOOLEAN_OVERLAP, internal=True, bottom=-depth
    )
    body = _joined("mesh", _plate("mesh"), shapes.moved(tap, (0.0, 0.0, PLATE[2])), "difference")
    feature = _thread_feature((0.0, 0.0, PLATE[2] - depth / 2.0), internal=True, length=depth)
    source = SceneObject(
        id="obj_1", name="Platte", mesh=body, kind="mesh", features={feature.id: feature}
    )
    assert source.mesh.component_count == 1
    result = run("remove_feature", source, profile, at_feature="thread_1")
    output = _stays(result, "mesh")
    assert float(output.mesh.volume) == pytest.approx(PLATE_VOLUME, rel=1e-6)


def test_the_panel_offers_changing_and_removing_a_thread() -> None:
    """Das Merkmalfenster bietet an einem Gewinde Ändern und Entfernen, mit Steigungsfeld."""
    from app.core.perceive.actions import actions_for

    load_operations()
    feature = _studded_plate("mesh").features["thread_1"]
    rows = actions_for(feature)
    offered = {row.op for row in rows if row.op is not None}
    assert offered == {"resize_feature", "remove_feature"}
    refused = {str(row.reason) for row in rows if row.op is None}
    assert any("Schaft" in reason for reason in refused)
    resize = next(row for row in rows if row.op == "resize_feature")
    pitch = next(field for field in resize.fields if field.name == "pitch")
    assert pitch.value == 1.0
    # Und an einem Zapfen steht das Feld nicht: eine Steigung ohne Gegenstand.
    pin = Feature(
        id="pin_1", kind="pin", provenance="detected", params={"diameter": 6.0, "centre": (0, 0, 0)}
    )
    pin_resize = next(row for row in actions_for(pin) if row.op == "resize_feature")
    assert "pitch" not in {field.name for field in pin_resize.fields}
    assert "tube_diameter" not in {field.name for field in pin_resize.fields}


def test_the_exact_thread_survives_a_step_round_trip(profile: Profile) -> None:
    """Das neu geschnittene exakte Gewinde geht durch STEP und kommt mit seinem Volumen zurück."""
    exact_kernel()
    load_operations()
    from app.core.brep import step

    result = run(
        "resize_feature",
        _studded_plate("brep"),
        profile,
        at_feature="thread_1",
        diameter=8.0,
        pitch=1.25,
    )
    solid: Any = result.outputs[0].mesh
    back = step.read(step.write(solid))
    assert back.volume == pytest.approx(solid.volume, rel=1e-7)


def test_both_kernels_agree_on_the_recut_thread(profile: Profile) -> None:
    """Netz und exakter Kern schneiden dasselbe Gewinde — bis auf die Facettierung."""
    exact_kernel()
    load_operations()
    exact = run(
        "resize_feature",
        _studded_plate("brep"),
        profile,
        at_feature="thread_1",
        diameter=8.0,
        pitch=1.25,
    ).outputs[0]
    meshed = run(
        "resize_feature",
        _studded_plate("mesh"),
        profile,
        at_feature="thread_1",
        diameter=8.0,
        pitch=1.25,
    ).outputs[0]
    assert abs(float(meshed.mesh.volume) / float(exact.mesh.volume) - 1.0) < 2e-3
