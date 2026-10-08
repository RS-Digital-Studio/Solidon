"""Posing (Konzept P16.8, Entscheidung I).

Drei Streichungen machen das gegenüber einem Animationsprogramm klein, und
alle drei werden hier geprüft: eine Pose statt einer Bewegung,
Vorwärtskinematik statt inverser, gerechnete Gewichte statt gespeicherter.

Der vierte Punkt ist der, an dem Posing hierher gehört und nicht zu Blender —
ein Gelenkwinkel darf ein Projektparameter sein.

**Dieser Satz stand hier, und er stimmte nicht.** Er endete auf „das prüft die
Ausdrucksauflösung der Szene, nicht diese Datei", und genau daran lag es: Sie
prüft es nicht. ``resolve_params`` sieht die **oberste** Ebene eines
Parametersatzes, und die Stellung steht dort als **ein** Wert, ein JSON-Text.
Was darin an Ausdrücken steckt, sah nie jemand — ``pose_from_text`` rief
``float()`` darauf, und der Nutzer las „Diese Stellung lässt sich nicht
lesen", nachdem vier Stellen ihm zugesagt hatten, dass es geht.

Geprüft wird es jetzt hier, unten in dieser Datei: Auflösen, Sammeln,
Schreiben und der Rückweg durch den Dialog. Ende zu Ende steht es in
``test_pose_session.py`` — dort auch der Teil, der wirklich weh tut: dass eine
Parameteränderung den Körper **mitbewegt** und nicht am Cache hängen bleibt.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.geom.pose import (
    armature_from_text,
    armature_to_text,
    pose_from_text,
    pose_to_text,
    posed,
    transforms,
    weights,
)
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Bone, OpContext, OpResult, Pose, Profile, Scene, SceneObject


def arm() -> MeshData:
    """Ein liegender Stab entlang X, fein genug zum Beugen."""
    body = trimesh.creation.cylinder(radius=3.0, height=40.0, sections=24)
    body.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0]))
    vertices, faces = trimesh.remesh.subdivide_to_size(
        np.asarray(body.vertices, dtype=float), np.asarray(body.faces, dtype=np.int64), 2.0
    )
    fine = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    fine.merge_vertices()
    return MeshData.of(fine)


def two_bones() -> list[Bone]:
    """Ober- und Unterarm, das Kind am Fuß des Elternteils."""
    return [
        Bone(name="upper", head=(-20.0, 0.0, 0.0), tail=(0.0, 0.0, 0.0)),
        Bone(name="lower", head=(0.0, 0.0, 0.0), tail=(20.0, 0.0, 0.0), parent="upper"),
    ]


def run(entry: SceneObject, profile: Profile, **params: object) -> OpResult:
    spec = REGISTRY.get("pose_armature")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


# --- die Gewichte ---------------------------------------------------------------


def test_every_vertex_belongs_somewhere() -> None:
    """Zeilenweise auf eins normiert — ein Eckpunkt, der nirgends hängt,
    bliebe beim Beugen stehen, während sein Nachbar mitgeht.
    """
    field = weights(arm(), two_bones())

    assert field.shape[1] == 2
    assert np.allclose(field.sum(axis=1), 1.0)
    assert (field >= 0.0).all()


def test_a_vertex_belongs_to_the_bone_it_sits_on() -> None:
    """Nah heißt stark. Ohne das wäre die Rechnung eine beliebige Verteilung."""
    body = arm()
    field = weights(body, two_bones())
    points = np.asarray(body.raw.vertices, dtype=float)

    left = points[:, 0] < -10.0
    right = points[:, 0] > 10.0
    assert field[left, 0].mean() > field[left, 1].mean(), "links hängt am Oberarm"
    assert field[right, 1].mean() > field[right, 0].mean(), "rechts am Unterarm"


def test_the_distance_is_to_the_segment_not_the_axis() -> None:
    """Ein Knochen hat zwei Enden, und dazwischen liegt er.

    Auf einer unendlichen Achse bände der Oberarm die Fußspitze an sich,
    sobald beide zufällig auf einer Geraden liegen.
    """
    far = MeshData.of(trimesh.creation.icosphere(subdivisions=1, radius=1.0))
    moved = far.raw.copy()
    moved.apply_translation((200.0, 0.0, 0.0))

    field = weights(MeshData.of(moved), two_bones())

    # Auf der Achse lägen beide Knochen im Abstand null; am Segment liegt der
    # Unterarm 180 mm entfernt, der Oberarm 200 — und zwar für jede Ecke.
    assert (field[:, 1] > field[:, 0]).all(), "der nähere Knochen gewinnt überall"


# --- Vorwärtskinematik ----------------------------------------------------------


def test_a_child_inherits_what_its_parent_did() -> None:
    """Wer den Oberarm hebt, hebt den Unterarm mit, ohne ihn zu nennen.

    Das *ist* Vorwärtskinematik, und ohne sie bliebe der Unterarm stehen,
    während der Oberarm sich dreht.
    """
    matrices = transforms(two_bones(), {"upper": (0.0, 90.0, 0.0)})

    # Die Spitze liegt 40 mm vom Kopf des Oberarms entfernt. Um 90 Grad um Y
    # gedreht steht sie senkrecht darunter — bei x des Kopfes, nicht bei null:
    # Gedreht wird um den Kopf, und der sitzt bei x = -20.
    tip = np.array([20.0, 0.0, 0.0, 1.0])
    moved = matrices["lower"] @ tip
    assert moved[0] == pytest.approx(-20.0, abs=1e-6), "der Unterarm ist mitgedreht"
    assert moved[2] == pytest.approx(-40.0, abs=1e-6)


def test_a_bone_turns_about_its_own_head() -> None:
    """Um den Kopf des Knochens, nicht um den Weltursprung.

    Ein Arm, der sich um den Ursprung dreht, fliegt vom Körper weg — der
    klassische erste Fehler beim Skinning.
    """
    matrices = transforms(two_bones(), {"upper": (0.0, 90.0, 0.0)})

    head = np.array([-20.0, 0.0, 0.0, 1.0])
    assert np.allclose((matrices["upper"] @ head)[:3], head[:3], atol=1e-9)
    # Und die Spitze schwingt um ihn: 20 mm vom Kopf, eine Vierteldrehung um Y
    # nach unten — nicht um den Ursprung, wo sie bei (0, 0, -0) bliebe.
    tail = np.array([0.0, 0.0, 0.0, 1.0])
    assert (matrices["upper"] @ tail)[:3] == pytest.approx((-20.0, 0.0, -20.0), abs=1e-9)


def test_bones_are_ordered_parents_first_whatever_the_list_says() -> None:
    """Die Reihenfolge in der Datei ist keine Zusage über den Baum."""
    reversed_order = list(reversed(two_bones()))

    matrices = transforms(reversed_order, {"upper": (0.0, 90.0, 0.0)})

    tip = np.array([20.0, 0.0, 0.0, 1.0])
    assert (matrices["lower"] @ tip)[0] == pytest.approx(-20.0, abs=1e-6)


def test_a_bone_hanging_on_itself_is_refused() -> None:
    """Ein Zyklus hält an, statt endlos zu laufen — mit einem Vorschlag."""
    circular = [
        Bone(name="a", head=(0.0, 0.0, 0.0), tail=(1.0, 0.0, 0.0), parent="b"),
        Bone(name="b", head=(1.0, 0.0, 0.0), tail=(2.0, 0.0, 0.0), parent="a"),
    ]

    with pytest.raises(ValidationError) as raised:
        transforms(circular, {})

    assert raised.value.suggestions


# --- was mit dem Körper passiert ------------------------------------------------


def test_bending_moves_the_far_end_and_leaves_the_near_one(profile: Profile) -> None:
    """Der Zweck, an einer Form, deren Ergebnis sich vorhersagen lässt."""
    body = arm()
    entry = SceneObject(id="obj_1", name="Arm", mesh=body)

    result = run(
        entry,
        profile,
        armature=armature_to_text(two_bones()),
        pose=pose_to_text([Pose(bone="lower", angles=(0.0, 45.0, 0.0))]),
    )

    after = result.outputs[0].mesh
    before_points = np.asarray(body.raw.vertices, dtype=float)
    after_points = np.asarray(after.raw.vertices, dtype=float)
    moved = np.linalg.norm(after_points - before_points, axis=1)
    assert moved[before_points[:, 0] > 15.0].mean() > 1.0, "das ferne Ende geht mit"
    assert moved[before_points[:, 0] < -15.0].mean() < 0.5, "das nahe bleibt"
    assert after.triangle_count == body.triangle_count


def test_an_empty_pose_leaves_the_body_alone(profile: Profile) -> None:
    """Der Nullpunkt — alle Winkel null heißt: nichts tun."""
    body = arm()
    entry = SceneObject(id="obj_1", name="Arm", mesh=body)

    result = run(
        entry,
        profile,
        armature=armature_to_text(two_bones()),
        pose=pose_to_text([Pose(bone="lower", angles=(0.0, 0.0, 0.0))]),
    )

    assert np.array_equal(
        np.asarray(result.outputs[0].mesh.raw.vertices), np.asarray(body.raw.vertices)
    )


def test_posing_twice_gives_the_same_body(profile: Profile) -> None:
    """Zweimal auswerten muss identisch sein."""
    entry = SceneObject(id="obj_1", name="Arm", mesh=arm())
    text = armature_to_text(two_bones())
    stance = pose_to_text([Pose(bone="lower", angles=(0.0, 30.0, 0.0))])

    once = run(entry, profile, armature=text, pose=stance)
    twice = run(entry, profile, armature=text, pose=stance)

    assert np.array_equal(
        np.asarray(once.outputs[0].mesh.raw.vertices),
        np.asarray(twice.outputs[0].mesh.raw.vertices),
    )


def test_without_an_armature_it_says_what_is_missing(profile: Profile) -> None:
    """„Nichts zu tun" ist ein Ergebnis und gehört gesagt."""
    entry = SceneObject(id="obj_1", name="Arm", mesh=arm())

    result = run(entry, profile, armature="", pose="")

    assert {f.code for f in result.findings} == {"pose.no_armature"}


def test_a_hard_bend_reports_the_pinch(profile: Profile) -> None:
    """Lineares Blend-Skinning schnürt ein — das ist bekannt und gehört gesagt.

    Das Volumen ist die Zahl, an der es auffällt, bevor jemand das Ergebnis
    von Hand nachmisst.
    """
    entry = SceneObject(id="obj_1", name="Arm", mesh=arm())

    result = run(
        entry,
        profile,
        armature=armature_to_text(two_bones()),
        pose=pose_to_text([Pose(bone="lower", angles=(0.0, 150.0, 0.0))]),
    )

    assert "pose.pinched" in {finding.code for finding in result.findings}


def test_a_gentle_bend_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe — sonst warnt jede Stellung und keine Warnung zählt."""
    entry = SceneObject(id="obj_1", name="Arm", mesh=arm())

    result = run(
        entry,
        profile,
        armature=armature_to_text(two_bones()),
        pose=pose_to_text([Pose(bone="lower", angles=(0.0, 15.0, 0.0))]),
    )

    assert "pose.pinched" not in {finding.code for finding in result.findings}


# --- die runde Reise ------------------------------------------------------------


def test_the_armature_survives_the_round_trip() -> None:
    """Eine der fünf Eigenschaften aus Regel 2."""
    bones = two_bones()

    again = armature_from_text(armature_to_text(bones))

    assert [bone.name for bone in again] == ["upper", "lower"]
    assert again[1].parent == "upper"
    assert again[0].head == pytest.approx(bones[0].head)


def test_the_pose_survives_the_round_trip() -> None:
    poses = [Pose(bone="lower", angles=(1.5, -30.0, 0.0))]

    again = pose_from_text(pose_to_text(poses))

    assert len(again) == 1
    assert again[0].bone == "lower"
    assert again[0].angles == pytest.approx((1.5, -30.0, 0.0))


def test_no_bones_no_movement() -> None:
    """Der Helfer ohne Operation herum, an seinem entartetsten Fall."""
    body = arm()

    assert posed(body, [], []) is body
    assert posed(body, two_bones(), []) is body


# --- fremde Eingabe -------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "b1: 0,30,0",
        "{kaputt",
        '["kein", "objekt"]',
        '{"b1": [0, 30]}',
        '{"b1": "keine liste"}',
    ],
)
def test_an_unreadable_pose_is_a_validation_error(text: str) -> None:
    """Die naheliegendste Handeingabe ist kein JSON — sie bekommt einen Satz
    mit der erwarteten Form (Regel 17), keinen toten Auswertungs-Thread."""
    with pytest.raises(ValidationError) as caught:
        pose_from_text(text)

    assert caught.value.suggestions
    assert caught.value.field == "pose"


@pytest.mark.parametrize(
    "text",
    [
        "{kaputt",
        '{"n": "kein array"}',
        '[{"n": "b1"}]',
        '[{"n": "b1", "h": [0, 0], "t": [1, 0, 0]}]',
    ],
)
def test_an_unreadable_armature_is_a_validation_error(text: str) -> None:
    with pytest.raises(ValidationError) as caught:
        armature_from_text(text)

    assert caught.value.suggestions
    assert caught.value.field == "armature"


# --- Winkel aus Projektparametern (§13) -------------------------------------------


def test_an_angle_may_be_a_project_parameter() -> None:
    """Vier Stellen versprachen das, und keine hielt es.

    Der Registereintrag (``Ein Winkel darf ein Projektparameter sein``), der
    Docstring von ``Pose`` (``=@arm_angle`` in einer Pose, und die Passung am
    Sockel rechnet mit), der ``fx``-Umschalter am Winkelfeld des Dialogs und
    der Kopf dieser Datei. Der Kern antwortete auf genau das mit ``Diese
    Stellung laesst sich nicht lesen``: ``pose_from_text`` rief ``float()``
    auf den Ausdruck.

    Der Denkfehler steht im Kopf dieser Datei: *das prueft die
    Ausdrucksaufloesung der Szene*. Sie tut es nicht — ``resolve_params``
    sieht die **oberste** Ebene eines Parametersatzes, und die Stellung ist
    dort ein JSON-Text. Was darin steht, sieht sie nie.
    """
    text = '{"arm":["=@winkel * 2",0,0]}'

    poses = pose_from_text(text, {"winkel": 15.0})

    assert poses == [Pose(bone="arm", angles=(30.0, 0.0, 0.0))]


def test_a_bare_reference_works_like_an_expression() -> None:
    """``@winkel`` ist dieselbe Bindung wie ``=@winkel``, nur kuerzer.

    Beide Praefixe kennt ``is_expression``, und ein Winkelfeld schreibt das
    eine so leicht wie das andere.
    """
    assert pose_from_text('{"arm":["@winkel",0,0]}', {"winkel": 12.0})[0].angles[0] == 12.0


def test_a_pose_without_values_still_reads_plain_numbers() -> None:
    """Wer keine Parameter reicht, bekommt weiter, was er immer bekam.

    Die Signatur waechst um ein Vorgabeargument, nicht um eine Pflicht — sonst
    muesste jeder Aufrufer im Programm mitziehen, auch die, die nie einen
    Ausdruck sehen.
    """
    assert pose_from_text('{"arm":[30,0,0]}') == [Pose(bone="arm", angles=(30.0, 0.0, 0.0))]


def test_an_unknown_parameter_says_which_one() -> None:
    """Ein Tippfehler im Parameternamen ist kein unlesbarer Text.

    ``Diese Stellung laesst sich nicht lesen`` waere hier die falsche Antwort:
    Die Stellung ist gelesen, und was fehlt, ist ein Parameter. Wer den Satz
    liest, sucht sonst am JSON statt am Namen.
    """
    with pytest.raises(ValidationError) as caught:
        pose_from_text('{"arm":["=@gibtsnicht",0,0]}', {"winkel": 15.0})

    assert "gibtsnicht" in f"{caught.value.title} {caught.value.detail} {caught.value.values}"


def test_the_pose_says_which_parameters_it_reads() -> None:
    """Das Gegenstueck zu ``sketch_parameter_references`` (§15).

    Die Auswertung mischt die Werte der gelesenen Parameter in den
    Cache-Schluessel. Ohne das bliebe nach einer Parameteraenderung das alte
    Ergebnis stehen — der Arm bliebe gebeugt, waehrend die Zahl daneben schon
    die neue ist.
    """
    from app.core.geom.pose import pose_parameter_references

    text = '{"arm":["=@winkel * 2",0,"@neigung"],"bein":[0,"=@winkel",0]}'

    assert pose_parameter_references(text) == {"winkel", "neigung"}


def test_an_unreadable_pose_has_no_references() -> None:
    """Ein kaputter Text haengt von nichts ab.

    Er scheitert beim Lauf der Operation mit seiner eigenen Meldung; hier
    waere eine zweite Fehlerquelle nur im Weg — genau wie bei
    ``sketch_parameter_references``.
    """
    from app.core.geom.pose import pose_parameter_references

    assert pose_parameter_references("{kaputt") == frozenset()


def test_one_writer_for_the_format_even_with_expressions() -> None:
    """Der Dialog baute sein eigenes JSON, weil der Kern-Schreiber nur Zahlen kann.

    ``ArmatureField.value`` faellt auf ``json.dumps`` zurueck, sobald ein Feld
    einen Ausdruck traegt — ein zweiter Schreiber fuer dasselbe Format, genau
    das, was sein eigener Docstring vermeiden wollte. ``pose_text`` nimmt
    beides, und damit gibt es wieder einen.
    """
    from app.core.geom.pose import pose_text

    written = pose_text({"arm": ["=@winkel", 0.0, 0.0]})

    assert pose_from_text(written, {"winkel": 15.0}) == [Pose(bone="arm", angles=(15.0, 0.0, 0.0))]


def test_the_raw_angles_survive_being_read_back() -> None:
    """Der Dialog schrieb Ausdruecke woertlich und las sie nicht zurueck.

    ``ArmatureField.value`` sagt in seinem Docstring zu, dass ein Ausdruck
    stehen bleibt — beim **Schreiben** stimmte das. Beim Oeffnen ging
    ``_angles_from`` ueber ``pose_from_text``, das drei Zahlen zurueckgibt;
    ein Ausdruck liess es scheitern, der Fang machte daraus ein leeres Raster,
    und alle drei Winkel des Knochens standen auf null. Ein Rundlauf durch den
    Dialog verlor damit genau die Bindung, die er zu erhalten versprach.

    ``pose_angles`` gibt die Rohwerte: Zahl oder Ausdruck, wie sie dastehen.
    """
    from app.core.geom.pose import pose_angles

    text = '{"arm":["=@winkel * 2",0,30],"bein":[0,0,0]}'

    assert pose_angles(text) == {"arm": ("=@winkel * 2", 0.0, 30.0), "bein": (0.0, 0.0, 0.0)}


def test_unreadable_raw_angles_are_an_empty_grid() -> None:
    """Ein unlesbarer Text ist im Dialog kein Fehler, sondern ein leeres Raster.

    Der Dialog soll aufgehen; was nicht zu lesen war, wird beim Uebernehmen
    ohnehin ueberschrieben. Diese Zusage stand schon in ``_angles_from`` und
    zieht mit um.
    """
    from app.core.geom.pose import pose_angles

    assert pose_angles("{kaputt") == {}
    assert pose_angles("") == {}


def test_a_parameter_change_reaches_a_cached_pose(profile: Profile) -> None:
    """§15: der Cache-Schluessel deckt alles, wovon das Ergebnis abhaengt.

    Der Ende-zu-Ende-Beleg steht in ``test_pose_session.py`` und geht ueber
    die Oberflaeche — faellt Qt aus, faellt der Beleg fuer §15 mit. Dieser
    hier haengt an nichts als dem Kern.

    Ohne den Eintrag in ``NESTED_REFERENCES`` ueberlebt der alte Koerper die
    Parameteraenderung im Cache: Der Text der Operation aendert sich ja nicht,
    der Ausdruck steckt darin, und ``resolve_params`` sieht nur die oberste
    Ebene. Der Arm bliebe gebeugt, waehrend die Zahl daneben schon die neue
    ist.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene.cache import ResultCache
    from app.core.scene.evaluate import evaluate
    from app.core.types import Document, Operation, Parameter

    def dokument(neigung: float) -> Document:
        return Document(
            format_version=1,
            app_version="0.0.1",
            parameters={"neigung": Parameter(name="neigung", value=neigung)},
            ops=[
                Operation(
                    id=1,
                    op="create_box",
                    outputs=("obj_1",),
                    params={"width": 10.0, "depth": 10.0, "height": 40.0},
                ),
                Operation(
                    id=2,
                    op="pose_armature",
                    inputs=("obj_1",),
                    outputs=("obj_1",),
                    params={
                        "armature": '[{"n":"b1","h":[0,0,0],"t":[0,0,40]}]',
                        "pose": '{"b1":["=@neigung",0,0]}',
                    },
                ),
            ],
        )

    cache = ResultCache()
    zehn = evaluate(dokument(10.0), profile, cache=cache)
    assert zehn.complete
    schmal = as_mesh_data(zehn.scene.objects["obj_1"].mesh).bounds.size

    vierzig = evaluate(dokument(40.0), profile, cache=cache)
    assert vierzig.complete
    weit = as_mesh_data(vierzig.scene.objects["obj_1"].mesh).bounds.size

    assert schmal != weit, (
        "derselbe Stapel, ein anderer Parameter — der Cache darf das alte Ergebnis nicht halten"
    )


def test_the_armature_text_passes_through_the_collector_harmlessly() -> None:
    """Beide Felder von ``PoseParams`` tragen ``kind="armature"``.

    Der Sammler bekommt deshalb auch den **Skelett**-Text zu sehen, und der
    ist eine JSON-*Liste* statt eines Objekts. Das Ergebnis ist leer, und das
    ist richtig: Ein Knochen ist eine Koordinate und kein Mass, das jemand an
    einen Parameter haengt. Geprueft wird es, weil ein stiller
    ``AttributeError`` wie ein Entwurf aussieht und nicht wie eine
    Entscheidung — wer das Skelett spaeter um Ausdruecke erweitert, faellt
    hier auf und nicht im Cache.
    """
    from app.core.geom.pose import pose_parameter_references

    assert pose_parameter_references('[{"n":"b1","h":[0,0,0],"t":[0,0,40]}]') == frozenset()


# --- das Skelett, das noch fehlt -------------------------------------------------


def test_the_missing_armature_is_a_warning_and_names_the_way(profile: Profile) -> None:
    """Ein Schritt, der nichts bewegen **kann**, ist mehr als eine Auskunft.

    Gemessen am 14.09.2026 über das Fenster: *Stellung geben* ohne Skelett
    legte einen Schritt an, das Teil blieb, wie es war, und im Band stand „am
    Volumen ändert sich nichts". Der Befund dazu gab es längst — er war nur
    ``info``, und ``Session._warning_of`` reicht ausschließlich Warnungen und
    Fehler ins Band weiter. Der einzige Satz, der den Fall erklärt, kam damit
    nirgends an.

    Zwei Dinge hängen daran und werden hier beide geprüft: die **Stufe**, weil
    der Kunde den Satz sonst nicht zu sehen bekommt, und der **Weg** im Satz
    selbst — wohin jemand geht, der ein Skelett setzen will. „Es fehlt etwas"
    ohne die Stelle, an der es entsteht, ist eine halbe Auskunft (Regel 17).
    """
    entry = SceneObject(id="obj_1", name="Arm", mesh=arm())

    result = run(entry, profile, armature="", pose="")

    treffer = [f for f in result.findings if f.code == "pose.no_armature"]
    assert treffer, "der Fall meldet sich gar nicht"
    assert treffer[0].severity == "warning", (
        "info erreicht das Band nicht — Session._warning_of nimmt nur warning und error"
    )
    assert "Skeletteditor" in str(treffer[0].message), (
        f"der Satz nennt die Stelle nicht, an der ein Skelett entsteht: {treffer[0].message}"
    )


def test_the_missing_armature_reaches_the_report_at_its_own_step(profile: Profile) -> None:
    """Der Anschluss: Was das Band liest, sind Stufe **und** Schrittnummer.

    ``Session._warning_of`` nimmt aus dem Prüfbericht die erste Warnung, deren
    ``op_id`` zu den vorgeschauten Schritten gehört. Die Stufe prüft der Test
    darüber am Befund selbst; hier steht die zweite Hälfte, die die Operation
    nicht setzt: Die Schrittnummer stempelt erst die Auswertung auf
    (``evaluate``). Ohne sie bliebe der Satz im Bericht liegen, und im Band
    stünde weiter „am Volumen ändert sich nichts".
    """
    from app.core.scene.evaluate import evaluate
    from app.core.types import Document, Operation

    document = Document(
        format_version=1,
        app_version="0.0.1",
        ops=[
            Operation(
                id=1,
                op="create_box",
                outputs=("obj_1",),
                params={"width": 10.0, "depth": 10.0, "height": 40.0},
            ),
            Operation(id=2, op="pose_armature", inputs=("obj_1",), outputs=("obj_1",)),
        ],
    )

    result = evaluate(document, profile)

    assert result.complete, "die Kette hält nicht an — der Schritt bleibt änderbar"
    treffer = [f for f in result.scene.report.findings if f.code == "pose.no_armature"]
    assert treffer, "der Befund kommt im Prüfbericht nicht an"
    assert treffer[0].op_id == 2, f"ohne Schrittnummer liest das Band ihn nicht: {treffer[0]}"
    assert treffer[0].severity == "warning"


def test_a_click_on_the_skin_becomes_a_joint_on_the_axis() -> None:
    """RM-367 W4-7: Ein Knochen lag auf dem angeklickten Hautpunkt statt im Gelenk.

    Ein Zylinder vom Radius 5 um die Z-Achse, von der Seite angeschaut: Ein
    Klick auf (5, 0, 10) wird (0, 0, 10), die Mitte unter dem Klick. Ein Klick
    neben die Haut, ein streifender Blick und ein Blick ins Leere bleiben, wo
    sie sind.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.geom.pose import inside_the_body

    body = trimesh.creation.cylinder(radius=5.0, height=40.0, sections=64)
    body.apply_translation((0.0, 0.0, 20.0))
    mesh = MeshData.of(body)
    for angle in (0.0, 1.0, 2.5, 4.0):
        point = (5.0 * math.cos(angle), 5.0 * math.sin(angle), 10.0)
        towards = (-math.cos(angle), -math.sin(angle), 0.0)
        inside = inside_the_body(mesh, point, towards)
        assert math.hypot(inside[0], inside[1]) < 0.3, (angle, inside)
        assert inside[2] == pytest.approx(10.0, abs=0.3)

    on_top = (0.0, 0.0, 40.0)
    assert inside_the_body(mesh, on_top, (1.0, 0.0, 0.0)) == on_top, "streifend bleibt"
    beside = (9.0, 0.0, 10.0)
    assert inside_the_body(mesh, beside, (-1.0, 0.0, 0.0)) == beside, "neben der Haut bleibt"


# --- fester Rumpf und Beugen mit der Maus (RM-561) --------------------------------


def rod() -> MeshData:
    """Ein stehender Stab 12 × 12 × 60 mm, fein genug zum Beugen."""
    body = trimesh.creation.box(extents=(12.0, 12.0, 60.0))
    body.apply_translation((0.0, 0.0, 30.0))
    vertices, faces = trimesh.remesh.subdivide_to_size(
        np.asarray(body.vertices, dtype=float), np.asarray(body.faces, dtype=np.int64), 2.0
    )
    fine = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    fine.merge_vertices()
    return MeshData.of(fine)


def upper_bones() -> list[Bone]:
    """Nur die obere Hälfte trägt Knochen — wie ein Arm ohne Rumpfknochen."""
    return [
        Bone(name="oben", head=(0.0, 0.0, 30.0), tail=(0.0, 0.0, 45.0)),
        Bone(name="spitze", head=(0.0, 0.0, 45.0), tail=(0.0, 0.0, 58.0), parent="oben"),
    ]


def test_what_no_bone_reaches_stays_where_it_is() -> None:
    """Die verborgene Voraussetzung fällt: Wer nur den oberen Teil mit Knochen
    versieht und beugt, beugt den oberen Teil. Bis Format 48 hing der Fuß am
    nächsten Knochen und drehte mit (Gegenprobe ``fixed_rest=False``)."""
    body = rod()
    turn = [Pose(bone="oben", angles=(0.0, 30.0, 0.0))]
    now = posed(body, upper_bones(), turn, fixed_rest=True)
    then = posed(body, upper_bones(), turn, fixed_rest=False)
    foot = np.asarray(body.raw.vertices)[:, 2] < 5.0

    still = np.linalg.norm(now.raw.vertices[foot] - body.raw.vertices[foot], axis=1).max()
    swung = np.linalg.norm(then.raw.vertices[foot] - body.raw.vertices[foot], axis=1).max()
    assert still < 1e-3, f"der Fuß bleibt stehen: {still:.4f} mm"
    assert swung > 5.0, f"Gegenprobe: bis Format 48 drehte er mit, {swung:.2f} mm"


def test_a_bone_still_carries_its_own_skin() -> None:
    """Der Rumpf hält nur, was kein Knochen hält: Was in der Reichweite eines
    Knochens liegt, folgt ihm genau wie bisher."""
    from app.core.geom.pose import REACH, _closest_on_segment

    body = rod()
    turn = [Pose(bone="oben", angles=(0.0, 30.0, 0.0))]
    now = posed(body, upper_bones(), turn, fixed_rest=True)
    then = posed(body, upper_bones(), turn, fixed_rest=False)
    points = np.asarray(body.raw.vertices, dtype=float)
    within = np.zeros(len(points), dtype=bool)
    for bone in upper_bones():
        head, tail = np.asarray(bone.head), np.asarray(bone.tail)
        reach = float(np.linalg.norm(tail - head)) * REACH
        within |= _closest_on_segment(points, head, tail) <= reach
    assert within.sum() > 100, "Voraussetzung: die Haut um die Knochen"
    assert np.abs(now.raw.vertices[within] - then.raw.vertices[within]).max() < 1e-9


def test_the_rest_weight_rises_smoothly() -> None:
    """Zwischen Knochen und Rumpf gleitet die Haut, sie reißt nicht: Kein Eckpunkt
    springt mehr als die Nachbarn um ihn herum."""
    from app.core.geom.pose import Skin

    body = rod()
    skin = Skin(body, upper_bones(), fixed_rest=True)
    held = skin.field.sum(axis=1)
    edges = np.asarray(body.raw.edges_unique)
    jump = np.abs(held[edges[:, 0]] - held[edges[:, 1]]).max()
    assert held.min() >= 0.0 and held.max() <= 1.0 + 1e-12
    assert jump < 0.25, f"größter Sprung des Haltens zwischen Nachbarn: {jump:.3f}"


def test_the_skin_computes_what_posed_computes() -> None:
    """Die Vorschau beim Ziehen und die Operation sind dieselbe Rechnung."""
    from app.core.geom.pose import Skin

    body = rod()
    angles = {"oben": (0.0, 20.0, 0.0), "spitze": (10.0, 0.0, 0.0)}
    poses = [Pose(bone=name, angles=turn) for name, turn in angles.items()]
    skin = Skin(body, upper_bones(), fixed_rest=True)
    assert np.array_equal(
        skin.posed(angles).raw.vertices,
        posed(body, upper_bones(), poses, fixed_rest=True).raw.vertices,
    )


@pytest.mark.parametrize(
    "angles",
    [
        (0.0, 0.0, 0.0),
        (30.0, 0.0, 0.0),
        (0.0, -45.0, 0.0),
        (12.5, 33.0, -70.0),
        (-120.0, 10.0, 80.0),
    ],
)
def test_angles_read_back_from_their_rotation(angles: tuple[float, float, float]) -> None:
    from app.core.geom.pose import _angles_of, _rotation

    assert _angles_of(_rotation(angles)) == pytest.approx(angles, abs=0.01)


def test_dragging_a_joint_turns_its_bone_about_the_head_in_the_view() -> None:
    """Ziehen am Gelenk dreht den Knochen, der dort endet, um seinen Kopf und um
    die Blickachse; geschrieben werden seine drei Winkel. Mit gebeugtem Elternteil
    dreht er um den Kopf, wo das Bild ihn zeigt, und die Eltern bleiben."""
    from app.core.geom.pose import bent, posed_bones

    bones = two_bones()
    assert bent(bones, {}, "upper", (0.0, 1.0, 0.0), 30.0) == pytest.approx((0.0, 30.0, 0.0))

    angles = {"upper": (0.0, 0.0, 40.0)}
    before = posed_bones(bones, angles)
    turned = dict(angles, lower=bent(bones, angles, "lower", (0.0, 0.0, 1.0), 25.0))
    after = posed_bones(bones, turned)
    assert np.allclose(after[0], before[0]), "der Elternteil bleibt"
    head, tail = np.asarray(after[1][0]), np.asarray(after[1][1])
    assert head == pytest.approx(np.asarray(before[1][0])), "um den eigenen Kopf"
    direction = math.degrees(math.atan2(tail[1] - head[1], tail[0] - head[0]))
    assert direction == pytest.approx(65.0, abs=0.05), "40° der Eltern und 25° gezogen"
