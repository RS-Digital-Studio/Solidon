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
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.parts import build, shapes
from app.core.types import Feature, Profile, SceneObject
from tests.helpers import exact_kernel, studded_thread_plate, tapped_thread_plate, thread_volume
from tests.helpers import run_operation as run
from tests.test_thread_import import BASES

PLATE = (40.0, 40.0, 10.0)
PLATE_VOLUME = PLATE[0] * PLATE[1] * PLATE[2]
LENGTH = 8.0


def _root(diameter: float, pitch: float) -> float:
    return shapes.ridge_profile(diameter, pitch)[0][0]


def _built(
    kind: str,
    diameter: float,
    pitch: float,
    length: float,
    *,
    internal: bool,
    starts: int = 1,
    form: str = "flat",
    slope: float = 0.0,
) -> float:
    """Das Volumen des Bausteingewindes, wie der jeweilige Kern es baut.

    Exakt nach Pappus — der genähte Körper trifft ihn auf 2 · 10⁻⁷ (gemessen
    M8 × 1,25 × 8: 8 · 10⁻⁵ mm³); die Gangzahl ändert ihn nicht. Am Netz das
    facettierte Netz selbst: Der Kern ist ein 48-Eck, der Gang ein Sehnenzug,
    zusammen 1,4 Prozent unter der Analytik. Geprüft wird hier, was die
    Operation zusammensetzt; wie treu ``build.threaded`` am Netz facettiert,
    prüft ``test_exact_parts``.
    """
    if kind == "brep" and not slope:
        return thread_volume(diameter, pitch, length, internal=internal, profile=form)
    return float(
        build.threaded(
            diameter,
            pitch,
            length,
            internal=internal,
            starts=starts,
            profile=cast(shapes.ThreadProfile, form),
            taper=slope,
            reference=length / 2.0,
        ).volume
    )


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


def _threaded_plate(
    kind: str,
    *,
    internal: bool,
    left: bool = False,
    starts: int = 1,
    slope: float = 0.0,
    form: str = "flat",
    diameter: float = 6.0,
    pitch: float = 1.0,
) -> SceneObject:
    """Die Platte mit aufgesetztem oder durchgehendem Gewinde, links, mehrgängig oder kegelig.

    Gebaut wie ein Baustein es baut (``build.threaded``), erklärt wie er es
    erklärt (``build.thread``) — der Kegel mit seinem Maß in der Mitte.
    """
    exact_kernel()
    profile = cast(shapes.ThreadProfile, form)
    depth = shapes.ridge_depth(pitch, profile)
    if internal:
        length = PLATE[2]
        bottom = -BOOLEAN_OVERLAP
        built = length + 2.0 * BOOLEAN_OVERLAP
        middle = PLATE[2] / 2.0
        size = diameter - 2.0 * depth
    else:
        length = LENGTH
        bottom = PLATE[2] - BOOLEAN_OVERLAP
        built = length
        middle = bottom + length / 2.0
        size = diameter
    options: dict[str, Any] = {
        "internal": internal,
        "bottom": bottom,
        "profile": profile,
        "starts": starts,
        "left": left,
        "taper": slope,
        "reference": middle,
    }
    if kind == "brep":
        with shapes.building("brep"):
            tool = build.threaded(size, pitch, built, **options)
    else:
        tool = build.threaded(size, pitch, built, **options)
    body = _joined(kind, _plate(kind), tool, "difference" if internal else "union")
    _identifier, feature = build.thread(
        "thread_1",
        diameter,
        pitch,
        (0.0, 0.0, middle),
        internal=internal,
        length=length,
        left=left,
        starts=starts,
        taper=slope,
    )
    if form != "flat":
        feature = Feature(
            id=feature.id,
            kind=feature.kind,
            provenance=feature.provenance,
            params={**feature.params, "profile": form},
            measure_sources=feature.measure_sources,
        )
    return SceneObject(
        id="obj_1", name="Platte", mesh=body, kind=kind, features={feature.id: feature}
    )


def _read_threads(kind: str, output: SceneObject) -> list[Feature]:
    """Die Gewinde, wie die Erkennung des jeweiligen Kerns sie unabhängig liest."""
    if kind == "brep":
        from app.core.brep.features import features_of

        return [f for f in features_of(output.mesh).values() if f.kind == "thread"]
    from app.core.perceive.features import detect

    return [f for f in detect(as_mesh_data(output.mesh)).values() if f.kind == "thread"]


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
    stud = studded_thread_plate(kind)
    added = _built(kind, 6.0, 1.0, LENGTH, internal=False) - _sunk(kind, 6.0, 1.0, LENGTH)
    assert float(stud.mesh.volume) - PLATE_VOLUME == pytest.approx(added, rel=_tolerance(kind))
    tapped = tapped_thread_plate(kind)
    cut = _built(kind, _bore(6.0, 1.0), 1.0, PLATE[2], internal=True)
    assert PLATE_VOLUME - float(tapped.mesh.volume) == pytest.approx(cut, rel=_tolerance(kind))


def test_removing_an_outer_thread_leaves_the_plain_core(kind: str, profile: Profile) -> None:
    """*Merkmal entfernen* nimmt außen den Gang bis auf den Kern — der Kern bleibt stehen."""
    source = studded_thread_plate(kind)
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
    source = tapped_thread_plate(kind)
    result = run("remove_feature", source, profile, at_feature="thread_1")
    output = _stays(result, kind)
    assert float(output.mesh.volume) == pytest.approx(
        PLATE_VOLUME, rel=1e-9 if kind == "brep" else 1e-6
    )
    assert "thread_1" not in output.features


def test_changing_an_outer_thread_recuts_it_on_the_same_axis(kind: str, profile: Profile) -> None:
    """*Merkmal ändern* setzt Durchmesser und Steigung neu, an derselben Achse und Mitte."""
    source = studded_thread_plate(kind)
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
    source = tapped_thread_plate(kind)
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
    source = studded_thread_plate(kind)
    result = run("resize_feature", source, profile, at_feature="thread_1", diameter=6.0, pitch=0.0)
    assert result.outputs[0] is source
    assert [finding.code for finding in result.findings] == ["resize_feature.unchanged"]


def test_a_left_hand_thread_is_recut_left_handed(kind: str, profile: Profile) -> None:
    """Ein Linksgewinde wird links neu geschnitten — nicht still rechts (RM-544).

    Bis RM-544 sagte *Merkmal ändern* hier ab. Gespiegelt bleibt das Volumen
    das des Rechtsgewindes; den Drehsinn liest die Erkennung unabhängig nach.
    """
    source = _threaded_plate(kind, internal=False, left=True)
    result = run("resize_feature", source, profile, at_feature="thread_1", diameter=8.0, pitch=1.25)
    output = _stays(result, kind)
    stud = _built(kind, 8.0, 1.25, LENGTH, internal=False) - _sunk(kind, 8.0, 1.25, LENGTH)
    assert float(output.mesh.volume) - PLATE_VOLUME == pytest.approx(stud, rel=_tolerance(kind))
    assert output.features["thread_1"].params["handedness"] == "left"
    found = _read_threads(kind, output)
    assert len(found) == 1
    assert found[0].params["handedness"] == "left"
    assert found[0].params["diameter"] == pytest.approx(8.0, abs=0.05)


def test_a_left_hand_inner_thread_is_recut_left_handed(kind: str, profile: Profile) -> None:
    """Innen ebenso: füllen und links neu schneiden, mit dem Werkzeug in der Bohrung."""
    source = _threaded_plate(kind, internal=True, left=True)
    result = run("resize_feature", source, profile, at_feature="thread_1", diameter=8.0, pitch=1.25)
    output = _stays(result, kind)
    cut = _built(kind, _bore(8.0, 1.25), 1.25, PLATE[2], internal=True)
    assert PLATE_VOLUME - float(output.mesh.volume) == pytest.approx(cut, rel=_tolerance(kind))
    assert output.features["thread_1"].params["handedness"] == "left"
    found = _read_threads(kind, output)
    assert [thread.params["handedness"] for thread in found] == ["left"]


def test_a_multi_start_thread_keeps_its_starts(kind: str, profile: Profile) -> None:
    """Ein zweigängiges Gewinde bleibt zweigängig: Vorschub zwei Steigungen (RM-544).

    Im Längsschnitt folgt Gang auf Gang im Abstand der Steigung, das Volumen
    ist also das eines eingängigen mit derselben Steigung.
    """
    source = _threaded_plate(kind, internal=False, starts=2)
    result = run("resize_feature", source, profile, at_feature="thread_1", diameter=8.0, pitch=1.25)
    output = _stays(result, kind)
    stud = _built(kind, 8.0, 1.25, LENGTH, internal=False, starts=2)
    stud -= stud * BOOLEAN_OVERLAP / LENGTH
    assert float(output.mesh.volume) - PLATE_VOLUME == pytest.approx(stud, rel=_tolerance(kind))
    changed = output.features["thread_1"].params
    assert changed["starts"] == 2 and changed["lead"] == pytest.approx(2.5)
    found = _read_threads(kind, output)
    assert len(found) == 1
    assert found[0].params["starts"] == 2
    assert found[0].params["pitch"] == pytest.approx(1.25, abs=0.02)


def test_a_whitworth_thread_keeps_its_profile(kind: str, profile: Profile) -> None:
    """Ein Whitworth-Gewinde (G) wird mit seinem 55°-Profil neu geschnitten, nicht flach."""
    source = _threaded_plate(kind, internal=False, form="whitworth", diameter=20.955, pitch=1.814)
    result = run(
        "resize_feature", source, profile, at_feature="thread_1", diameter=26.441, pitch=1.814
    )
    output = _stays(result, kind)
    stud = _built(kind, 26.441, 1.814, LENGTH, internal=False, form="whitworth")
    stud -= stud * BOOLEAN_OVERLAP / LENGTH
    assert float(output.mesh.volume) - PLATE_VOLUME == pytest.approx(stud, rel=_tolerance(kind))
    assert output.features["thread_1"].params["profile"] == "whitworth"


def test_a_pitch_that_leaves_no_core_is_refused(kind: str, profile: Profile) -> None:
    """Eine Steigung, die den Kern aufbraucht, ist eine Absage mit Vorschlag."""
    source = studded_thread_plate(kind)
    with pytest.raises(ValidationError) as caught:
        run("resize_feature", source, profile, at_feature="thread_1", diameter=6.0, pitch=6.0)
    assert caught.value.constraint == "thread_pitch"


def test_a_thread_without_a_length_says_so(kind: str, profile: Profile) -> None:
    """Ohne Strecke gibt es nichts zu verschließen — die Absage nennt sie."""
    source = studded_thread_plate(kind)
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
        thread_volume(8.0, 1.25, length, internal=False), rel=_tolerance("brep")
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


def test_a_mesh_read_left_hand_thread_is_recut_left_handed(profile: Profile) -> None:
    """Ein am Netz gemessenes Linksgewinde wird links neu geschnitten — wie am exakten Körper.

    Vorher galt am Netz jede Händigkeit als geraten, und *Merkmal ändern*
    schnitt ein Linksgewinde still rechts neu (P2.5); danach sagte es ab, bis
    RM-544 den Drehsinn mitnahm.
    """
    exact_kernel()
    from tests.helpers import mirrored_thread

    load_operations()
    source, thread = _recognised("mesh", mirrored_thread(_corpus("m6_rechts")))
    assert thread.params["handedness"] == "left"
    assert thread.measure_sources.get("handedness") == "facets"
    result = run("resize_feature", source, profile, at_feature=thread.id, diameter=8.0, pitch=1.25)
    output = _stays(result, "mesh")
    assert [found.params["handedness"] for found in _read_threads("mesh", output)] == ["left"]


def test_a_natively_read_left_hand_thread_is_recut_left_handed(profile: Profile) -> None:
    """Ein an den Kanten gelesenes Linksgewinde wird links neu geschnitten — der Beleg ist nativ."""
    exact_kernel()
    from tests.helpers import mirrored_thread

    source, thread = _recognised("brep", mirrored_thread(_corpus("m6_rechts")))
    assert thread.params["handedness"] == "left"
    result = run("resize_feature", source, profile, at_feature=thread.id, diameter=8.0, pitch=1.25)
    output = _stays(result, "brep")
    threads = [f for f in output.features.values() if f.kind == "thread"]
    assert [f.params["handedness"] for f in threads] == ["left"]
    assert [found.params["handedness"] for found in _read_threads("brep", output)] == ["left"]


def test_a_recognised_multi_start_rod_is_recut_with_its_starts(profile: Profile) -> None:
    """``zweigaengig`` (Ø 8, Steigung 1, zwei Gänge) auf Ø 10 × 1,25: weiter zwei Gänge.

    Bis RM-544 sagte das Ändern ab, statt still ein eingängiges daraus zu
    machen. Die Hülle nimmt die ganze Stange; übrig ist das neue Gewinde.
    """
    exact_kernel()
    source, thread = _recognised("brep", _corpus("zweigaengig"))
    assert thread.params["starts"] == 2
    result = run("resize_feature", source, profile, at_feature=thread.id, diameter=10.0, pitch=1.25)
    output = _stays(result, "brep")
    length = float(thread.params["length"])
    assert float(output.mesh.volume) == pytest.approx(
        thread_volume(10.0, 1.25, length, internal=False), rel=_tolerance("brep")
    )
    found = _read_threads("brep", output)
    assert len(found) == 1
    assert found[0].params["starts"] == 2
    assert found[0].params["lead"] == pytest.approx(2.5, abs=0.01)


#: Der Kegel der Rohrgewinde, 1:16 auf den Durchmesser — Zuwachs des Halbmessers je mm.
SLOPE = 1.0 / 32.0


def _frustum(radius: float, slope: float, low: float, high: float) -> float:
    """Ein Kegelstumpf um die Achse: Halbmesser ``radius + slope · z`` von ``low`` bis ``high``."""
    return math.pi * (
        radius**2 * (high - low)
        + radius * slope * (high**2 - low**2)
        + slope**2 * (high**3 - low**3) / 3.0
    )


def _tapered_thread(
    diameter: float, pitch: float, low: float, high: float, *, internal: bool
) -> float:
    """Ein kegeliges Bausteingewinde nach Pappus, ``diameter`` in der Höhe null.

    Das Volumen je Millimeter ist quadratisch im Durchmesser und der linear in
    der Höhe — Simpson ist darauf genau (am genähten Körper Ø 10 × 1,5 gemessen:
    3 · 10⁻¹⁰).
    """

    def per_mm(z: float) -> float:
        return thread_volume(diameter + 2.0 * SLOPE * z, pitch, 1.0, internal=internal)

    return (high - low) / 6.0 * (per_mm(low) + 4.0 * per_mm((low + high) / 2.0) + per_mm(high))


def test_removing_a_tapered_outer_thread_leaves_the_tapered_core(
    kind: str, profile: Profile
) -> None:
    """*Merkmal entfernen* an einem Kegel: Übrig bleibt der kegelige Kern (RM-544).

    Hülle und Kern des Werkzeugs folgen dem Kegel; Zylinder trügen ein Ende ab
    und ließen am anderen den Gang stehen.
    """
    source = _threaded_plate(kind, internal=False, slope=SLOPE)
    result = run("remove_feature", source, profile, at_feature="thread_1")
    output = _stays(result, kind)
    core = _frustum(_root(6.0, 1.0), SLOPE, -LENGTH / 2.0 + BOOLEAN_OVERLAP, LENGTH / 2.0)
    if kind == "mesh":
        # Am Netz ist der Kern das Vieleck des Werkzeugs, wie bei ``_cylinder``.
        corners = shapes.SEGMENTS
        core *= corners / (2.0 * math.pi) * math.sin(2.0 * math.pi / corners)
    assert float(output.mesh.volume) - PLATE_VOLUME == pytest.approx(core, rel=_tolerance(kind))
    assert "thread_1" not in output.features


def test_closing_a_tapered_inner_thread_fills_the_bore(kind: str, profile: Profile) -> None:
    """Ein kegeliges Innengewinde schließt sich zur vollen Platte."""
    source = _threaded_plate(kind, internal=True, slope=SLOPE)
    result = run("remove_feature", source, profile, at_feature="thread_1")
    output = _stays(result, kind)
    assert float(output.mesh.volume) == pytest.approx(
        PLATE_VOLUME, rel=1e-9 if kind == "brep" else 1e-6
    )


def test_changing_a_tapered_outer_thread_keeps_its_taper(kind: str, profile: Profile) -> None:
    """Neu geschnitten bleibt der Kegel; das neue Maß gilt in der Mitte wie das alte."""
    source = _threaded_plate(kind, internal=False, slope=SLOPE)
    result = run("resize_feature", source, profile, at_feature="thread_1", diameter=8.0, pitch=1.25)
    output = _stays(result, kind)
    half = LENGTH / 2.0
    if kind == "brep":
        stud = _tapered_thread(8.0, 1.25, -half + BOOLEAN_OVERLAP, half, internal=False)
    else:
        stud = _built(kind, 8.0, 1.25, LENGTH, internal=False, slope=SLOPE)
        stud -= stud * BOOLEAN_OVERLAP / LENGTH
    assert float(output.mesh.volume) - PLATE_VOLUME == pytest.approx(stud, rel=_tolerance(kind))
    changed = output.features["thread_1"].params
    assert changed["taper"] == pytest.approx(source.features["thread_1"].params["taper"])
    if kind == "brep":
        found = _read_threads(kind, output)
        assert len(found) == 1
        assert found[0].params["taper"] == pytest.approx(changed["taper"], rel=1e-3)
        assert found[0].params["diameter"] == pytest.approx(8.0, abs=0.05)


def test_changing_a_tapered_inner_thread_keeps_its_taper(kind: str, profile: Profile) -> None:
    """Innen ebenso: füllen und kegelig neu schneiden, das Maß in der Mitte."""
    source = _threaded_plate(kind, internal=True, slope=SLOPE)
    result = run("resize_feature", source, profile, at_feature="thread_1", diameter=8.0, pitch=1.25)
    output = _stays(result, kind)
    half = PLATE[2] / 2.0
    if kind == "brep":
        cut = _tapered_thread(_bore(8.0, 1.25), 1.25, -half, half, internal=True)
    else:
        cut = _built(kind, _bore(8.0, 1.25), 1.25, PLATE[2], internal=True, slope=SLOPE)
    assert PLATE_VOLUME - float(output.mesh.volume) == pytest.approx(cut, rel=_tolerance(kind))
    assert output.features["thread_1"].params["taper"] > 0.0


def test_a_recognised_tapered_rod_loses_its_thread_down_to_the_cone(profile: Profile) -> None:
    """``konisch`` (Ø 10 × 1,5, Kegel 1:16): entfernt bleibt der Kegel unter dem Talgrund."""
    exact_kernel()
    source, thread = _recognised("brep", _corpus("konisch"))
    assert thread.params["taper"] > 0.0
    slope = math.tan(math.radians(float(thread.params["taper"])))
    inner = min(float(thread.params["root_radius"]), float(thread.params["crest_radius"]))
    length = float(thread.params["length"])
    result = run("remove_feature", source, profile, at_feature=thread.id)
    output = _stays(result, "brep")
    assert float(output.mesh.volume) == pytest.approx(
        _frustum(inner - BOOLEAN_OVERLAP, slope, -length / 2.0, length / 2.0), rel=1e-6
    )
    assert thread.id not in output.features


def test_a_recognised_tapered_rod_is_recut_tapered(profile: Profile) -> None:
    """``konisch`` auf Ø 12 × 1,5 in der Mitte: wieder kegelig, mit demselben Kegel."""
    exact_kernel()
    source, thread = _recognised("brep", _corpus("konisch"))
    result = run("resize_feature", source, profile, at_feature=thread.id, diameter=12.0, pitch=1.5)
    output = _stays(result, "brep")
    found = _read_threads("brep", output)
    assert len(found) == 1
    assert found[0].params["taper"] == pytest.approx(float(thread.params["taper"]), rel=1e-3)
    assert found[0].params["diameter"] == pytest.approx(12.0, abs=0.05)


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
    feature = studded_thread_plate("mesh").features["thread_1"]
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
        studded_thread_plate("brep"),
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
        studded_thread_plate("brep"),
        profile,
        at_feature="thread_1",
        diameter=8.0,
        pitch=1.25,
    ).outputs[0]
    meshed = run(
        "resize_feature",
        studded_thread_plate("mesh"),
        profile,
        at_feature="thread_1",
        diameter=8.0,
        pitch=1.25,
    ).outputs[0]
    assert abs(float(meshed.mesh.volume) / float(exact.mesh.volume) - 1.0) < 2e-3
