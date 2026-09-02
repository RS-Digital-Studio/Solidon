"""Weg 3 aus §2.2, Ende zu Ende (Bauplan §40 für P9).

    Text oder Bild → Mesh → Reparaturkette läuft automatisch → Prüfbericht →
    gegebenenfalls teilen und verstiften → exportieren.

Teilen und Verstiften ist P10; alles davor steht hier. Der Generator ist
geskriptet, und was er übergibt, ist mit Absicht die Sorte Netz, die ein echter
liefert: offen, mit einem losen Fragment, und in mehr Schattierungen gefärbt,
als irgendein Drucker Filamente hat.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.backends.mesh import ScriptedMeshBackend
from app.core.export.writer import plan_export, write_plan
from app.core.generate import from_image, from_text
from app.core.geom.attributes import used_slots
from app.core.ingest import threemf
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, load, new_project, save
from app.core.types import Profile

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def project() -> Project:
    return new_project("centauri-carbon-2", "petg")


def generated_body() -> bytes:
    """Was ein Generator wirklich liefert: eine offene Schale plus einen losen
    Krümel.

    PLY, weil es die Farben je Fläche behält, mit denen ein erzeugtes Modell
    ankommt — und genau diese Farben muss §20 in Filamente verwandeln.
    """
    shell = trimesh.load_mesh(MESHES / "broken_open.stl", process=False)
    crumb = trimesh.creation.box(extents=(0.4, 0.4, 0.4))
    crumb.apply_translation([40.0, 40.0, 0.0])
    body = trimesh.util.concatenate([shell, crumb])

    middle = body.triangles_center[:, 0]
    shades = np.linspace(0, 1, len(body.faces))
    colours = np.zeros((len(body.faces), 4), dtype=np.uint8)
    colours[:, 3] = 255
    colours[:, 0] = (255 * (middle > middle.mean())).astype(np.uint8)
    colours[:, 2] = (255 * (middle <= middle.mean())).astype(np.uint8)
    # Ein wenig Rauschen auf dem Grünkanal: eine Darstellung hält die
    # auseinander, ein Drucker nicht — und die Quantisierung muss die sein, die
    # das sagt.
    colours[:, 1] = (40 * shades).astype(np.uint8)
    body.visual.face_colors = colours
    return bytes(trimesh.exchange.export.export_mesh(body, None, file_type="ply"))


def backend() -> ScriptedMeshBackend:
    return ScriptedMeshBackend(fallback=generated_body(), suffix=".ply")


def evaluated(project: Project, profile: Profile):
    return evaluate(project.document, profile, sources=ProjectSources(project))


def test_a_description_becomes_a_body_in_the_scene(project: Project, profile: Profile) -> None:
    result = from_text(project, backend(), "eine kleine Figur", seed=7)

    scene = evaluated(project, profile)

    assert scene.complete
    assert result.object_id in scene.scene.objects
    assert scene.scene.objects[result.object_id].mesh.triangle_count > 0


def test_the_generated_file_is_a_source_and_not_an_operation(project: Project) -> None:
    """§11.3: ein Generator ist keine Funktion, aufgehoben werden also die
    Bytes.
    """
    result = from_text(project, backend(), "eine kleine Figur", seed=7)

    source = project.document.sources[result.source_id]
    assert source.kind == "generated"
    assert source.origin is not None
    assert source.origin.prompt == "eine kleine Figur"
    assert source.origin.seed == 7
    assert source.origin.author == "scripted"
    assert project.sources[result.source_id] == result.result.payload
    # Drei Schritte: laden, reparieren, auf Arbeitsgröße bringen. Der dritte
    # kam dazu, weil ein Bildmodell auf einen Einheitswürfel normiert liefert.
    assert [entry.op for entry in project.document.ops] == ["load", "fit_to_size", "repair"]


def test_the_repair_chain_runs_without_being_asked(project: Project, profile: Profile) -> None:
    """§2.2: „Reparaturkette läuft automatisch" — und es ist im Prüfbericht zu
    sehen.
    """
    from_text(project, backend(), "eine kleine Figur", seed=7)

    scene = evaluated(project, profile)

    codes = {finding.code for finding in scene.scene.report.findings}
    assert any(code.startswith("repair.") for code in codes), codes
    assert "repair.components_removed" in codes, "the loose crumb is gone"


def test_the_repair_is_one_step_that_can_be_taken_back(project: Project, profile: Profile) -> None:
    """Sie läuft automatisch, und das ist nicht dasselbe wie unvermeidlich."""
    from_text(project, backend(), "eine kleine Figur", seed=7)
    with_repair = evaluated(project, profile)
    object_id = next(iter(with_repair.scene.objects))
    repaired = with_repair.scene.objects[object_id].mesh.triangle_count

    # Zwei Undo: das Auf-Maß-Bringen und die Reparatur. Seit die Generierung
    # ihren Körper auf Arbeitsgröße bringt, liegt zwischen dem Laden und dem
    # Ergebnis ein Schritt mehr — und nur einer zurückzunehmen ließe die
    # Reparatur stehen, um die es hier geht.
    history = History(project.document)
    history.undo()
    history.undo()
    without = evaluated(project, profile)

    assert without.complete
    assert without.scene.objects[object_id].mesh.triangle_count > repaired


def test_a_picture_takes_the_same_way(project: Project, profile: Profile) -> None:
    result = from_image(project, backend(), b"\x89PNG not really", seed=2)

    scene = evaluated(project, profile)

    assert scene.complete
    assert result.object_id in scene.scene.objects
    assert project.document.sources[result.source_id].origin.seed == 2


def test_the_colours_become_filaments_and_reach_the_3mf(
    project: Project, profile: Profile, tmp_path: Path
) -> None:
    """Das ganze §20 an einem erzeugten Körper: Textur hinein, Farbgruppen
    heraus.
    """
    result = from_text(project, backend(), "eine kleine Figur", seed=7)
    History(project.document).apply(
        "Farben",
        [
            OperationDraft(
                op="slots_from_texture",
                inputs=(result.object_id,),
                params={"filaments": 2},
                seed=1,
            )
        ],
    )

    scene = evaluated(project, profile)
    entry = scene.scene.objects[result.object_id]

    assert scene.complete
    assert used_slots(entry.mesh) == (0, 1), "hundreds of shades onto two filaments"
    assert len(entry.material_slots) == 2

    plan = plan_export([entry], project_name="Figur", profile=profile, export_format="3mf")
    written = write_plan(plan, tmp_path, "3mf")

    groups = threemf.read(written[0].read_bytes(), entry.mesh.triangle_count)
    assert groups is not None
    assert len(groups.materials) == 2
    assert set(groups.slots) == {0, 1}


def test_the_same_seed_gives_the_same_filaments(
    project: Project, profile: Profile, tmp_path: Path
) -> None:
    """§20: die Quantisierung ist reproduzierbar, sonst hört die Datei auf,
    das Teil zu beschreiben.

    Reproduzierbar über ein Speichern hinweg, und das ist der Fall, auf den es
    ankommt: der Startwert, den der Verlauf vergeben hat, muss aus der Datei
    wieder herauskommen (§11.3).
    """
    result = from_text(project, backend(), "eine kleine Figur", seed=7)
    History(project.document).apply(
        "Farben",
        [
            OperationDraft(
                op="slots_from_texture", inputs=(result.object_id,), params={"filaments": 3}
            )
        ],
    )
    first = evaluated(project, profile).scene.objects[result.object_id].mesh.slots
    save(project, tmp_path / "figur.p3d")

    reopened = load(tmp_path / "figur.p3d")
    second = evaluated(reopened, profile).scene.objects[result.object_id].mesh.slots

    assert project.document.ops[-1].seed is not None, "a randomised step carries its seed"
    assert first == second


def test_the_project_survives_being_saved_and_opened(
    project: Project, profile: Profile, tmp_path: Path
) -> None:
    """Weg 3 endet in einer Datei wie jeder andere Weg — mit unversehrter
    Provenienz.
    """
    result = from_text(project, backend(), "eine kleine Figur", seed=7)
    save(project, tmp_path / "figur.p3d")

    reopened = load(tmp_path / "figur.p3d")
    scene = evaluated(reopened, profile)

    assert scene.complete
    source = reopened.document.sources[result.source_id]
    assert source.origin is not None
    assert (source.origin.prompt, source.origin.seed) == ("eine kleine Figur", 7)


def test_the_way_ends_in_a_file(project: Project, profile: Profile, tmp_path: Path) -> None:
    result = from_text(project, backend(), "eine kleine Figur", seed=7)
    scene = evaluated(project, profile)

    plan = plan_export(
        [scene.scene.objects[result.object_id]], project_name="Figur", profile=profile
    )
    written = write_plan(plan, tmp_path)

    assert written[0].exists()
    assert written[0].name.endswith(".stl")


def test_a_tiny_generated_body_survives_the_chain(project: Project, profile: Profile) -> None:
    """Ein erzeugtes Netz kommt geschlossen an und muss es bleiben.

    Es kam geschlossen an und wurde es hier nicht mehr: Verschweißen und
    Entarten messen beide absolut, und ein Bildmodell misst auf einem
    Einheitswürfel ein bis zwei Millimeter. Unter der Toleranz lag dann nicht
    der Doppelpunkt, sondern die halbe Lehne — vier von vier Möbeln gingen
    auf, ohne dass sich ein Dreieck geändert hätte.

    Die Reihenfolge behebt es: erst auf Maß, dann bereinigen. Neu vernetzen
    hätte es auch geschlossen und die Feinheit gekostet.
    """
    # Ein Würfel von zwei Millimetern, fein vernetzt: die Größe, in der ein
    # Bildmodell ankommt, und die Feinheit, die es mitbringt. Das geskriptete
    # Standardnetz taugt hier nicht — es ist mit Absicht kaputt.
    winzig = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    assert winzig.is_watertight, "die Vorlage selbst ist geschlossen"
    tiny = ScriptedMeshBackend(
        fallback=bytes(trimesh.exchange.export.export_mesh(winzig, None, file_type="ply")),
        suffix=".ply",
    )

    result = from_text(project, tiny, "eine kleine Figur", seed=7)
    scene = evaluated(project, profile)

    body = scene.scene.objects[result.object_id].mesh
    assert body.is_watertight, "was geschlossen ankam, geht auf dem Weg nicht auf"
    assert max(body.bounds.size) == pytest.approx(100.0, abs=1e-3), "und steht auf Arbeitsgröße"


def test_a_generated_mesh_arrives_workable(project: Project, profile: Profile) -> None:
    """§2.2 Weg 3 endet nicht bei „liegt in der Szene", sondern bei
    „damit lässt sich arbeiten".

    Ein Generator liefert typisch anderthalb Millionen Dreiecke. Damit hat
    niemand ein Problem außer der Merkmalserkennung — und ohne Merkmale gibt es
    nichts, worauf ein Klick oder der Agent zeigen könnte. Der Ausweg stand
    bisher als Nebensatz im Prüfbericht; jetzt geht ihn die Kette selbst.
    """
    import trimesh

    from app.core.generate import GENERATED_TRIANGLE_LIMIT, GENERATED_TRIANGLE_TARGET

    # Ein feines Netz, wie es aus einem Generator kommt.
    fein = trimesh.creation.icosphere(subdivisions=8, radius=30.0)
    assert len(fein.faces) > GENERATED_TRIANGLE_LIMIT, "sonst prüft der Test nichts"
    payload = bytes(trimesh.exchange.export.export_mesh(fein, None, file_type="ply"))

    generator = ScriptedMeshBackend(fallback=payload, suffix=".ply")
    generation = from_text(project, generator, "eine Figur", seed=7)

    assert len(generation.transactions) == 4, "Laden, Größe, Reparieren, Dezimieren"
    result = evaluated(project, profile)
    entry = result.scene.objects[generation.object_id]
    assert entry.mesh.triangle_count <= GENERATED_TRIANGLE_TARGET * 1.1


def test_a_mesh_between_the_two_old_limits_keeps_its_features(
    project: Project, profile: Profile
) -> None:
    """Die Zwickmühle aus zwei Grenzen, die sich widersprachen.

    Die Merkmalserkennung steigt oberhalb von 200 000 Dreiecken aus, die
    Automatik dezimierte aber erst ab 500 000 — begründet mit
    ``agent.analysis.TRIANGLE_LIMIT``, was die Grenze des *Steckbriefs* ist und
    nicht die der *Erkennung*. Was dazwischen lag, behielt seine Auflösung und
    verlor die Merkmale: kein Klick auf eine Bohrung, keine Passung, nichts für
    den Agenten. Bei externen Generatoren ist das der Normalfall.

    Aufgelöst werden konnte das erst, nachdem ``decimate`` ein unverschweißtes
    Netz nicht mehr zerriss — vorher tauschte jede Senkung dieser Grenze
    wasserdicht gegen Merkmale. Deshalb prüft dieser Test **beides** an einem
    Körper: dass er dezimiert wird, dass er dabei geschlossen bleibt, und dass
    am Ende Merkmale dastehen.
    """
    import trimesh

    from app.core.scene.evaluate import FEATURE_LIMIT_TRIANGLES

    # Genau der Bereich, der vorher durchfiel: über der Erkennungsgrenze,
    # unter den alten 500 000.
    mittel = trimesh.creation.icosphere(subdivisions=7, radius=30.0)
    assert FEATURE_LIMIT_TRIANGLES < len(mittel.faces) < 500_000, (
        f"{len(mittel.faces)} Dreiecke liegen nicht im Bereich, um den es geht"
    )
    payload = bytes(trimesh.exchange.export.export_mesh(mittel, None, file_type="ply"))

    generator = ScriptedMeshBackend(fallback=payload, suffix=".ply")
    generation = from_text(project, generator, "eine Vase", seed=7)

    assert len(generation.transactions) == 4, "Laden, Größe, Reparieren, Dezimieren"

    result = evaluated(project, profile)
    entry = result.scene.objects[generation.object_id]

    assert entry.mesh.triangle_count <= FEATURE_LIMIT_TRIANGLES, (
        f"{entry.mesh.triangle_count} Dreiecke — über der Grenze der Erkennung"
    )
    assert entry.mesh.is_watertight, "beim Dezimieren aufgerissen"
    assert entry.mesh.component_count == 1, (
        f"beim Dezimieren in {entry.mesh.component_count} Teile zerfallen"
    )
    codes = {finding.code for finding in result.scene.report.findings}
    assert "perceive.too_large" not in codes, (
        "die Erkennung steigt weiter aus — die Grenzen widersprechen sich noch"
    )


def test_the_list_of_steps_leaves_none_of_them_out(project: Project, profile: Profile) -> None:
    """**``fit_to_size`` fehlte in der Liste.**

    Wer sie abarbeitet, um eine Erzeugung zurückzurollen, ließ genau diese
    Transaktion stehen: den Körper auf 100 mm gebracht, ohne die Quelle, aus
    der er kam. Geprüft wird deshalb nicht die Zahl, sondern die
    Vollständigkeit — was in einem Zug entstanden ist, steht auch drin.
    """
    generator = ScriptedMeshBackend(fallback=generated_body(), suffix=".ply")

    generation = from_text(project, generator, "eine Figur", seed=7)

    im_dokument = [entry.id for entry in project.document.transactions]
    assert list(generation.transactions) == im_dokument, (
        "jede Transaktion dieses Zuges gehört in die Liste"
    )
    schritte = [operation.op for operation in project.document.ops]
    assert "fit_to_size" in schritte, "sonst prüft dieser Test nichts"
