"""Merkmalsverweise, die ihr Merkmal verloren haben (Bauplan §21.3).

Die Trennung ist der Kern: **ein Verweis**, der ins Leere zeigt, hält die
Auswertung an und fragt (`feature.orphaned`). Ein erkanntes Merkmal, das
niemand benutzt und das eine Operation nebenbei verliert, ist dagegen der
Regelfall jeder Formänderung und bleibt eine Feststellung
(`perceive.orphaned`, `info`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.errors import AmbiguityError
from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive.features import detect
from app.core.scene import orphans
from app.core.types import Document, FeatureRef, Fit, Operation, Profile, Scene, SceneObject

MESHES = Path(__file__).parent / "data" / "meshes"

load_operations()


@pytest.fixture
def scene(profile: Profile) -> Scene:
    mesh = normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    return Scene(objects={"obj_1": entry}, profile=profile)


def document_with(*fits: Fit) -> Document:
    document = Document(format_version=1, app_version="0.0.1")
    document.fits.extend(fits)
    return document


def fit_to(feature_id: str, name: str = "stift_1") -> Fit:
    """Beide Seiten auf der Platte, damit nur die geprüfte Seite fehlen kann."""
    return Fit(
        name=name,
        a=FeatureRef("obj_1", feature_id),
        b=FeatureRef("obj_1", "hole_4"),
        kind="clearance",
    )


def refuse(question: str, choices: list[str]) -> str:
    raise AmbiguityError(question, candidates=tuple(choices))


def test_references_that_resolve_are_left_alone(scene: Scene) -> None:
    document = document_with(fit_to("hole_1"))

    result = orphans.check(document, scene, refuse)

    assert result.findings == []
    assert not result.changed


def test_a_lost_reference_is_put_to_the_user(scene: Scene) -> None:
    """§21.3: die Kette fragt, sie sucht sich nie selbst ein Loch aus."""
    document = document_with(fit_to("hole_9"))
    asked: list[tuple[str, list[str]]] = []

    def answer(question: str, choices: list[str]) -> str:
        asked.append((question, choices))
        return "hole_2"

    result = orphans.check(document, scene, answer)

    assert asked and "hole_9" in asked[0][0]
    assert "hole_1" in asked[0][1], "the candidates are the holes of the same object"
    assert document.fits[0].a.feature_id == "hole_2", "the answer is written into the file"
    assert result.rewritten == 1
    assert result.findings[0].code == "feature.rewritten"


def test_the_question_is_asked_once_not_on_every_run(scene: Scene) -> None:
    document = document_with(fit_to("hole_9"))
    calls: list[str] = []

    def answer(question: str, choices: list[str]) -> str:
        calls.append(question)
        return "hole_2"

    orphans.check(document, scene, answer)
    orphans.check(document, scene, answer)

    assert len(calls) == 1, "after the rewrite the reference resolves by itself"


def test_the_user_can_drop_the_fit_instead(scene: Scene) -> None:
    document = document_with(fit_to("hole_9"))

    result = orphans.check(document, scene, lambda question, choices: orphans.REMOVE_CHOICE)

    assert document.fits == []
    assert result.removed == 1
    assert result.findings[0].code == "feature.orphaned"


def test_a_reference_without_any_candidate_is_an_error(scene: Scene) -> None:
    """Nichts zur Auswahl heißt nichts zu fragen — es wird gemeldet, nicht
    geraten.
    """
    document = document_with(
        Fit(
            name="weg",
            a=FeatureRef("obj_7", "hole_1"),
            b=FeatureRef("obj_2", "pin_1"),
            kind="clearance",
        )
    )

    result = orphans.check(document, scene, refuse)

    assert result.findings[0].severity == "error"
    assert not result.changed


def test_the_candidates_keep_to_the_kind(scene: Scene) -> None:
    """Ein Loch wird durch ein Loch ersetzt, nie durch eine Fläche."""
    document = document_with(fit_to("hole_9"))
    seen: list[list[str]] = []

    orphans.check(document, scene, lambda question, choices: seen.append(choices) or "hole_1")

    assert all(name.startswith("hole_") for name in seen[0][:-1])
    assert seen[0][-1] == orphans.REMOVE_CHOICE


def test_both_sides_of_a_fit_are_checked(scene: Scene) -> None:
    document = document_with(
        Fit(
            name="stift_1",
            a=FeatureRef("obj_1", "hole_1"),
            b=FeatureRef("obj_1", "hole_9"),
            kind="clearance",
        )
    )

    orphans.check(document, scene, lambda question, choices: "hole_3")

    assert document.fits[0].b.feature_id == "hole_3"


def test_the_references_of_a_document_are_listed() -> None:
    document = document_with(fit_to("hole_1"), fit_to("hole_2", name="stift_2"))

    found = orphans.references(document)

    assert [entry.where for entry in found] == [
        "fit:stift_1:a",
        "fit:stift_1:b",
        "fit:stift_2:a",
        "fit:stift_2:b",
    ]
    assert found[0].fit_name == "stift_1"
    assert found[1].side == "b"


def test_the_candidates_can_be_shown_highlighted(scene: Scene) -> None:
    """§21.3 will die Kandidaten in der Ansicht markiert, sie kommen also mit
    ihren Daten.
    """
    found = orphans.candidates_of(scene, FeatureRef("obj_1", "hole_9"))

    assert found and all(feature.kind == "hole" for feature in found.values())


# --- Operationen benennen auch Merkmale, und wurden nie geprüft ------------------


def document_with_op(named: str, op: str = "insert_heatset_m4") -> Document:
    """Ein Dokument, dessen eine Operation ein Merkmal namentlich benennt."""
    document = Document(format_version=1, app_version="0.0.1")
    document.ops.append(
        Operation(id=1, op=op, inputs=("obj_1",), outputs=("obj_1",), params={"at_feature": named})
    )
    return document


def test_an_operation_that_names_a_feature_is_a_reference() -> None:
    """Die Lücke, die das hier schließt: achtzehn Operationen deklarieren
    eines, und keine wurde aufgezählt.

    ``references`` sagte „Operationen tragen Koordinaten, keine Merkmal-IDs" —
    und das war falsch, seit es die Bausteinbibliothek gibt. Eine Datei, deren
    Loch fort war, bekam nicht die Frage aus §21.3; sie hielt an dieser
    Operation mit einem Fehler an.
    """
    found = orphans.references(document_with_op("hole_1"))

    assert [entry.where for entry in found] == ["op:1:at_feature"]
    assert found[0].ref == FeatureRef("obj_1", "hole_1")


def test_an_empty_reference_is_not_a_reference() -> None:
    """Die meisten Operationen lassen es leer, und ein leerer Name zeigt
    nirgendwohin.
    """
    assert orphans.references(document_with_op("")) == []


def test_a_lost_reference_of_an_operation_is_put_to_the_user(scene: Scene) -> None:
    document = document_with_op("hole_9")
    answers: list[str] = []

    def answer(question: str, choices: list[str]) -> str:
        answers.append(question)
        return "hole_2"

    result = orphans.check(document, scene, answer)

    assert answers, "the question was asked"
    assert result.rewritten == 1
    assert document.ops[0].params["at_feature"] == "hole_2", "and the answer is in the file"


def test_dropping_it_clears_the_name_and_keeps_the_step(scene: Scene) -> None:
    """Eine Operation ist ein Schritt, den jemand getan hat — sie zu löschen
    nähme die Geometrie mit.
    """
    document = document_with_op("hole_9")

    result = orphans.check(document, scene, lambda question, choices: orphans.REMOVE_CHOICE)

    assert result.removed == 1
    assert len(document.ops) == 1, "the step stays"
    assert document.ops[0].params["at_feature"] == "", "only the name is gone"


def test_aligning_names_a_feature_too_and_says_so() -> None:
    """*An Merkmal ausrichten* nennt zwei Merkmale und wurde von keinem
    Raster erfasst.

    Die Prüfung sucht nach der **Art** (``kind="feature"``), die Vorbelegung
    in ``placement.py`` nach dem **Namen** (``at_feature``). Einundzwanzig
    Operationen erfüllen beides, weil ihr Feld so heißt und so deklariert ist.
    Diese eine nennt ihres ``feature`` und deklarierte nichts — und fiel damit
    durch beide Raster: keine Rückfrage nach §21.3, keine Auswahlliste im
    Dialog, keine Vorbelegung aus einem Klick.

    Sichtbar wurde es an der Bedienung — der Kunde sollte ``hole_1`` tippen —,
    aber der Schaden liegt hier: Wer ein Merkmal umbenennt, bekommt für
    einundzwanzig Operationen die Frage aus §21.3 und für diese einen Fehler
    eine Operation später.

    **Das zweite Feld fehlt hier absichtlich.** ``target`` benennt ein Merkmal
    eines *anderen* Objekts (``obj_2:hole_1``), und ``references`` baut jeden
    Verweis mit ``operation.inputs[0]`` — für ``target`` käme dabei
    ``obj_1:"obj_2:hole_1"`` heraus. Es braucht eine eigene Art, nicht diese;
    ein ``kind="feature"`` daran wäre kein Fortschritt, sondern ein falscher
    Verweis.
    """
    document = Document(format_version=1, app_version="0.0.1")
    document.ops.append(
        Operation(
            id=1,
            op="align_to_feature",
            inputs=("obj_1",),
            outputs=("obj_1",),
            params={"feature": "hole_1", "target": "obj_2:hole_3"},
        )
    )

    found = orphans.references(document)

    assert [entry.where for entry in found] == ["op:1:feature"]
    assert found[0].ref == FeatureRef("obj_1", "hole_1")


def test_an_operation_the_registry_does_not_know_is_skipped() -> None:
    """Eine Datei aus einer neueren Version, oder ein nicht geladenes Plugin."""
    assert orphans.references(document_with_op("hole_1", op="op_from_the_future")) == []


def test_a_feature_nobody_refers_to_is_not_a_warning() -> None:
    """§21.3 knüpft das Melden an einen Verweis, und das aus gutem Grund.

    Beim Aushöhlen mit offener Decke verschwindet die Deckfläche — genau das
    war die Absicht. Als Warnung gezählt, steht sie im Bericht jeder gelungenen
    Dose, schiebt ihn in der Oberfläche nach vorn und macht den Platz wertlos,
    an dem echte Warnungen stehen. Was einen Verweis bricht, meldet weiterhin
    `feature.orphaned`, und zwar als Fehler.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "app" / "core" / "scene" / "evaluate.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    severities: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or getattr(node.func, "id", "") != "Finding":
            continue
        fields = {kw.arg: kw.value for kw in node.keywords}
        code = fields.get("code")
        mentions = code is not None and "perceive.orphaned" in ast.unparse(code)
        if mentions and "severity" in fields:
            severities.append(ast.unparse(fields["severity"]))

    assert severities == ["'info'"], f"perceive.orphaned ist keine Warnung: {severities}"


def test_kind_of_knows_every_feature_kind() -> None:
    """Die handgepflegte Liste kannte cone/sphere/torus/fillet nicht und
    führte das tote slot — für einen verschwundenen Kegel wurden Flächen und
    Bohrungen als „plausible Nachfolger" angeboten (Fund des Gesamtreviews
    vom 25.08.2026). Die Liste kommt jetzt aus ``FeatureKind``.
    """
    from typing import get_args

    from app.core.scene.orphans import _kind_of
    from app.core.types import FeatureKind

    for kind in get_args(FeatureKind):
        assert _kind_of(f"{kind}_3") == kind, f"{kind} muss sein eigenes Präfix erkennen"
    assert _kind_of("edge_loop_1") == "edge_loop", "der längste Treffer gewinnt"
    assert _kind_of("slot_1") is None, "slot war nie eine Merkmalsart"


# --- Skizzenebenen (Fund 16 des Update-Reviews, 26.08.2026) ----------------------


def sketch_on(plane: str) -> str:
    """Eine kleine Skizze auf der genannten Ebene, als gespeicherter Text."""
    import dataclasses

    from app.core.sketch.serialize import sketch_to_text
    from app.core.sketch.shapes import rectangle

    return sketch_to_text(dataclasses.replace(rectangle(10.0, 10.0), plane=plane))


def document_with_sketch(plane: str) -> Document:
    document = Document(format_version=1, app_version="0.0.1")
    document.ops.append(
        Operation(
            id=1,
            op="sketch_extrude",
            inputs=(),
            outputs=("obj_2",),
            params={"sketch": sketch_on(plane), "height": 5.0},
        )
    )
    return document


def test_a_sketch_plane_on_a_face_is_a_reference() -> None:
    """Eine Skizze auf einer Fläche benennt ein Merkmal — nur eben im
    Skizzentext statt in einem feature-Parameter.

    Der Verweisfilter kannte sie nicht: Eine Datei, deren Fläche fort war,
    bekam genau bei „Skizze auf Fläche" keine §21.3-Frage, und die
    Mehrdeutigkeitsfrage der Zuordnung wurde für die Fläche übersprungen.
    Der leere Objektname ist Absicht: Wem die Fläche gehört, weiß erst die
    Auswertung — ``frame_for`` sucht über alle Körper, weil
    ``sketch_extrude`` nichts verbraucht.
    """
    found = orphans.references(document_with_sketch("feature:face_1"))

    assert [entry.where for entry in found] == ["plane:1:sketch"]
    assert found[0].ref == FeatureRef("", "face_1")


def test_a_new_sketch_plane_keeps_its_object_in_the_reference() -> None:
    """Gleiche Flächennamen auf zwei Körpern dürfen nicht zusammenfallen."""
    found = orphans.references(document_with_sketch("feature:obj_7:face_1"))

    assert [entry.where for entry in found] == ["plane:1:sketch"]
    assert found[0].ref == FeatureRef("obj_7", "face_1")


def test_a_world_plane_is_no_reference() -> None:
    """``plane:xy`` hängt an der Welt, nicht an einem Merkmal."""
    assert orphans.references(document_with_sketch("plane:xy")) == []


def test_a_resolving_sketch_plane_asks_nothing(scene: Scene) -> None:
    the_face = next(
        name for name, feature in scene.objects["obj_1"].features.items() if feature.kind == "face"
    )
    document = document_with_sketch(f"feature:{the_face}")

    result = orphans.check(document, scene, refuse)

    assert result.findings == []
    assert not result.changed


def test_a_lost_sketch_plane_is_put_to_the_user(scene: Scene) -> None:
    """Die Frage kommt, die Antwort landet im Skizzentext — und streichen
    lässt sich eine Ebene nicht: ohne sie gibt es die Skizze nicht."""
    from app.core.sketch.serialize import sketch_from_text

    document = document_with_sketch("feature:face_99")
    asked: list[tuple[str, list[str]]] = []

    def answer(question: str, choices: list[str]) -> str:
        asked.append((question, choices))
        return choices[0]

    result = orphans.check(document, scene, answer)

    assert asked and "face_99" in asked[0][0]
    assert orphans.REMOVE_CHOICE not in asked[0][1], "eine Ebene bietet kein Streichen an"
    assert all(choice.startswith("face_") for choice in asked[0][1]), "Flächen, nichts anderes"
    rewritten = sketch_from_text(str(document.ops[0].params["sketch"]))
    assert rewritten.plane == f"feature:{asked[0][1][0]}", "die Antwort steht im Skizzentext"
    assert result.rewritten == 1


def test_a_declined_sketch_plane_stays_untouched(scene: Scene) -> None:
    """Wer nicht antwortet, verliert nichts: Die Operation hält später mit
    dem eigenen Satz von ``frame_for`` an (§15.2) — das ist die Sackgasse
    nicht, die eine stumm gestrichene Ebene wäre."""
    document = document_with_sketch("feature:face_99")
    before = document.ops[0].params["sketch"]

    def decline(question: str, choices: list[str]) -> None:
        return None

    result = orphans.check(document, scene, decline)

    assert document.ops[0].params["sketch"] == before
    assert result.rewritten == 0 and result.removed == 0
    assert result.findings and result.findings[0].code == "feature.orphaned"
