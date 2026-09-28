"""Die freie Stelle eines weiteren Modells wird einmal gerechnet und festgehalten.

Entscheidung Robert (Review F1): „Die freie Stelle wird beim ersten Laden
gerechnet und im Ladeschritt festgehalten, auf demselben Weg wie die
beantwortete Einheitenfrage. Danach bleibt das Modell liegen, wie in jedem
Slicer.“ (§17.1, Schritt 6; §15.7.)

Geprüft wird an einer Bohrung, nicht nur an der Lage: Das Modell bleibt, die
Bohrung trägt weiter ab und sitzt am Teil, wenn davor etwas gelöscht oder
geändert oder der Drucker gewechselt wird. Die drei Fälle sind die Sonden p4,
p5 und p10 aus dem Review des Zweigs `einfuegen-freier-platz`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import trimesh

from app.core.ingest.plan import import_plan
from app.core.knowledge import profiles
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Profile, Source

MESHES = Path(__file__).parent / "data" / "meshes"
CUBE = (MESHES / "cube_clean.stl").read_bytes()
BLOCK = (MESHES / "block_with_rounded_edge.stl").read_bytes()


def _evaluated(project: Project, profile: Profile) -> Any:
    """Auswerten und die Antworten festhalten — wie die Sitzung nach jedem Lauf."""
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, [entry.values for entry in result.scene.report.findings]
    History(project.document).record_answers(result.answers)
    return result


def _import(project: Project, history: History, name: str, payload: bytes) -> str:
    """Eine Datei über den Einlesplan, wie Fenster und Kommandozeile sie einfügen."""
    key = f"src_{len(project.document.sources) + 1}"
    project.document.sources[key] = Source(id=key, kind="import", path=f"sources/{name}", sha256="")
    project.sources[key] = payload
    chosen = import_plan(key, name, payload, "mm", first_model=not project.document.ops)
    history.apply(chosen.title, [chosen.draft])
    return project.document.ops[-1].outputs[0]


def _drill(history: History, body: str, entry: Any, diameter: float) -> None:
    """Von oben durch, ein Viertel der Breite vom linken Rand — wie ein Klick."""
    low, high = entry.mesh.bounds.minimum, entry.mesh.bounds.maximum
    history.apply(
        "Bohren",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(body,),
                outputs=(body,),
                params={
                    "diameter": diameter,
                    "x": float(low[0] + 0.25 * (high[0] - low[0])),
                    "y": float(entry.mesh.bounds.centre[1]),
                    "z": float(high[2]),
                    "axis": "z",
                    "depth": 0.0,
                },
            )
        ],
    )


def _hole_offset(entry: Any) -> float:
    """Wo das fehlende Material relativ zur Mitte des Körpers sitzt (Schwerpunkt in x)."""
    return float(entry.mesh.raw.center_mass[0] - entry.mesh.bounds.centre[0])


def _missed(result: Any) -> list[str]:
    return [
        entry.code
        for entry in result.scene.report.findings
        if entry.code in {"boolean.without_effect", "bore.over_the_edge"}
    ]


def test_deleting_the_model_before_leaves_the_next_and_its_bore(profile: Profile) -> None:
    """p4: Der Ladeschritt des ersten Modells geht — das zweite bleibt mit Bohrung.

    Vorher sprang der Block in die Mitte, und die Bohrung traf nichts mehr
    („Der Schnitt hat nichts abgetragen“).
    """
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    _import(project, history, "a.stl", CUBE)
    block = _import(project, history, "b.stl", BLOCK)
    placed = _evaluated(project, profile).scene.objects[block]
    whole = float(placed.mesh.volume)
    _drill(history, block, placed, 6.0)
    drilled = _evaluated(project, profile).scene.objects[block]
    assert float(drilled.mesh.volume) < whole - 1.0, "die Bohrung trägt ab"

    history.remove_operations([project.document.ops[0].id])
    after = _evaluated(project, profile)

    entry = after.scene.objects[block]
    assert tuple(entry.mesh.bounds.minimum) == pytest.approx(tuple(drilled.mesh.bounds.minimum))
    assert float(entry.mesh.volume) == pytest.approx(float(drilled.mesh.volume), rel=1e-9)
    assert _hole_offset(entry) == pytest.approx(_hole_offset(drilled), abs=1e-6)
    assert not _missed(after), "die Bohrung trifft weiter"


def test_changing_a_measure_before_leaves_the_next_and_its_bore(profile: Profile) -> None:
    """p5: Ein Maß davor ändert sich — das dritte Modell und seine Bohrung bleiben.

    Vorher rückte der Würfel um 2 mm, und die Bohrung saß still daneben.
    """
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    _import(project, history, "a.stl", CUBE)
    block = _import(project, history, "b.stl", BLOCK)
    history.apply(
        "Skalieren",
        [
            OperationDraft(
                op="scale_object",
                inputs=(block,),
                outputs=(block,),
                params={"factor": 1.0, "fx": 1.1, "fy": 1.0, "fz": 1.0},
            )
        ],
    )
    scale_step = project.document.ops[-1].id
    cube = _import(project, history, "c.stl", CUBE)
    placed = _evaluated(project, profile).scene.objects[cube]
    _drill(history, cube, placed, 4.0)
    drilled = _evaluated(project, profile).scene.objects[cube]

    history.change_params(scale_step, {"fx": 1.2})
    after = _evaluated(project, profile)

    entry = after.scene.objects[cube]
    assert tuple(entry.mesh.bounds.minimum) == pytest.approx(tuple(drilled.mesh.bounds.minimum))
    assert float(entry.mesh.volume) == pytest.approx(float(drilled.mesh.volume), rel=1e-9)
    assert _hole_offset(entry) == pytest.approx(_hole_offset(drilled), abs=1e-6), (
        "die Bohrung sitzt am Teil, wo sie gebohrt wurde"
    )


def test_another_printer_leaves_the_next_model_and_its_bore(profile: Profile) -> None:
    """p10: Derselbe Stand mit einem anderen Drucker (Creality K1, 220er Bett).

    Vorher rückte der Block um 18 mm, und die Bohrung traf nicht mehr. Jetzt
    bleibt er, wo er lag — steht er dort über das kleinere Bett hinaus, sagt
    es der Bericht, und *Auf dem Bett anordnen* holt ihn herein.
    """
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    _import(project, history, "a.stl", CUBE)
    block = _import(project, history, "b.stl", BLOCK)
    placed = _evaluated(project, profile).scene.objects[block]
    _drill(history, block, placed, 6.0)
    drilled = _evaluated(project, profile).scene.objects[block]

    k1 = profiles.make_profile("creality-k1", "petg")
    after = _evaluated(project, k1)

    entry = after.scene.objects[block]
    assert tuple(entry.mesh.bounds.minimum) == pytest.approx(tuple(drilled.mesh.bounds.minimum))
    assert float(entry.mesh.volume) == pytest.approx(float(drilled.mesh.volume), rel=1e-9)
    assert not _missed(after), "die Bohrung trifft weiter"


def test_the_spot_stands_in_the_step_and_its_key_reads_the_scene_no_longer(
    profile: Profile,
) -> None:
    """Die Stelle steht nach der ersten Auswertung im Ladeschritt (Mitte und
    Platte), und von da an liest der Schritt die Szene nicht mehr."""
    from app.core.registry import REGISTRY
    from app.core.registry.params import reads_scene

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    _import(project, history, "a.stl", CUBE)
    block = _import(project, history, "b.stl", BLOCK)
    step = project.document.ops[1]
    spec = REGISTRY.get(step.op)
    assert reads_scene(spec.params, step.params), "vor der ersten Auswertung sucht er"

    placed = _evaluated(project, profile).scene.objects[block]

    step = project.document.ops[1]
    assert step.params["spot_x"] == pytest.approx(placed.mesh.bounds.centre[0])
    assert step.params["spot_y"] == pytest.approx(placed.mesh.bounds.centre[1])
    assert step.params["spot_plate"] == 1
    assert not reads_scene(spec.params, step.params), "danach liest er nicht mehr"


def test_a_model_without_room_says_so_and_offers_to_arrange(profile: Profile) -> None:
    """F10: Wo keine Platte Platz hat, steht nicht „an die erste freie Stelle“,
    sondern ein eigener Satz mit dem Weg *Auf dem Bett anordnen*."""
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    _import(project, history, "a.stl", CUBE)
    huge = trimesh.creation.box(extents=(300.0, 300.0, 10.0))
    _import(project, history, "gross.stl", bytes(huge.export(file_type="stl")))

    result = _evaluated(project, profile)

    codes = {entry.code for entry in result.scene.report.findings}
    assert "arrange.no_free_spot" in codes
    assert "arrange.free_spot" not in codes
    refusal = next(
        entry for entry in result.scene.report.findings if entry.code == "arrange.no_free_spot"
    )
    assert [action.id for action in refusal.suggestions] == ["arrange_on_bed"]


def test_a_model_that_did_not_move_gets_no_finding(profile: Profile) -> None:
    """F10: Ohne Verschiebung kein Befund — ein Modell, das schon an der
    freien Stelle liegt (hier: allein im Projekt, mittig), bekommt keinen Satz
    über eine Stelle, an die es „kam“."""
    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    body.apply_translation((0.0, 0.0, 10.0))
    payload = bytes(body.export(file_type="stl"))
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/liegt.stl", sha256=""
    )
    project.sources["src_1"] = payload
    chosen = import_plan("src_1", "liegt.stl", payload, "mm", first_model=False)
    History(project.document).apply(chosen.title, [chosen.draft])

    result = _evaluated(project, profile)

    codes = {entry.code for entry in result.scene.report.findings}
    assert not codes & {"arrange.free_spot", "arrange.no_free_spot"}, codes
    assert project.document.ops[0].params["spot_plate"] == 1, "festgehalten wird trotzdem"
