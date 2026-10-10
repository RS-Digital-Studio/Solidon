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

from app.core.export.writer import plan_export, write_plan
from app.core.generate import from_image, from_text
from app.core.geom.attributes import used_slots
from app.core.ingest import threemf
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, load, new_project, save
from app.core.types import Profile
from tests.scripted_backend import ScriptedMeshBackend

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def project() -> Project:
    return new_project("centauri-carbon-2", "petg")


def generated_body() -> bytes:
    """Was ein Generator wirklich liefert: eine offene Schale plus einen losen
    Krümel.

    PLY, weil es die Farben je Fläche behält, mit denen ein erzeugtes Modell
    ankommt — und genau diese Farben muss §20 in Filamente verwandeln.

    **Die Farbgrenze halbiert die Schale, und zwar nach ihrer Fläche** — das
    ist eine Messung: Am Mittelwert der Dreiecksschwerpunkte hing die
    Aufteilung an der Vernetzung und kippte, sobald sich eine Fläche änderte.
    Als die Reparatur beim Import (22.09.2026) drei Dreiecke ergänzte, fiel
    eine der beiden Farbgruppen unter die Fläche, ab der ein Filament noch
    eines ist — aus zwei wurde eines, und der Test maß die Dreieckszahl statt
    die Quantisierung. Nach der Fläche der Schale geteilt tragen beide
    Gruppen etwa die Hälfte von ihr, gleich wie das Netz vernetzt ist — und
    beide überleben, dass der Krümel in der Kette als Kleinstteil wegfällt.
    """
    shell = trimesh.load_mesh(MESHES / "broken_open.stl", process=False)
    crumb = trimesh.creation.box(extents=(0.4, 0.4, 0.4))
    crumb.apply_translation([40.0, 40.0, 0.0])
    body = trimesh.util.concatenate([shell, crumb])

    # Die Grenze, die **die Schale** nach Fläche halbiert: Ihre Dreiecke nach
    # der Lage sortieren und dort schneiden, wo die halbe Oberfläche erreicht
    # ist. Nicht über den ganzen Körper, denn der Krümel fällt in der Kette als
    # Kleinstteil weg (``repair.components_removed``) — läge die Grenze
    # zwischen ihm und der Schale, bliebe danach eine Farbe übrig.
    middle = body.triangles_center[:, 0]
    shell_middle = shell.triangles_center[:, 0]
    shell_areas = np.asarray(shell.area_faces, dtype=float)
    order = np.argsort(shell_middle)
    reached = np.searchsorted(np.cumsum(shell_areas[order]), shell_areas.sum() / 2.0)
    across = float(shell_middle[order[min(int(reached), len(order) - 1)]])
    shades = np.linspace(0, 1, len(body.faces))
    colours = np.zeros((len(body.faces), 4), dtype=np.uint8)
    colours[:, 3] = 255
    colours[:, 0] = (255 * (middle > across)).astype(np.uint8)
    colours[:, 2] = (255 * (middle <= across)).astype(np.uint8)
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
    # Vier Schritte: laden, auf Arbeitsgröße bringen (ein Bildmodell liefert
    # auf einem Einheitswürfel), reparieren und zuletzt aufs Kundenmaß bringen,
    # das zugleich legt und aufsetzt — nach der Kette, denn die Reparatur kann
    # unter dem Körper etwas wegnehmen, und eine Maßänderung rechnet so nur
    # diesen letzten Schritt neu (RM-676).
    assert [entry.op for entry in project.document.ops] == [
        "load",
        "fit_to_size",
        "repair",
        "fit_to_size",
    ]


@pytest.mark.parametrize(
    ("prompt", "title"),
    [
        ("Rohrhalter für 20/", "Rohrhalter für 20⁄"),
        ("Halter für 1/2 Zoll Rohr", "Halter für 1⁄2 Zoll Rohr"),
        ("..", "Erzeugt"),
        ("...", "Erzeugt"),
        ('Deckel: "rund"?', "Deckel rund"),
    ],
)
def test_any_prompt_gives_a_source_that_loads(
    project: Project, profile: Profile, prompt: str, title: str
) -> None:
    """Der Quellname kommt aus dem Prompt; ein Schrägstrich machte daraus einen
    Ordner, Punkte nahmen die Endung mit, und `load` hielt mit „Dieses
    Dateiformat kann nicht gelesen werden.“ (RM-362, W3-5)."""
    result = from_text(project, backend(), prompt, seed=7)

    source = project.document.sources[result.source_id]
    assert Path(source.path).suffix == ".ply"
    assert source.origin is not None and source.origin.title == title
    assert source.origin.prompt == prompt
    scene = evaluated(project, profile)
    assert scene.complete
    assert scene.scene.objects[result.object_id].mesh.triangle_count > 0


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
    """Sie läuft automatisch, und das ist nicht dasselbe wie unvermeidlich.

    Seit die Erzeugung **ein** Rückgängig-Schritt ist (RM-372), nimmt ein
    Strg+Z das ganze Modell; die Reparatur bleibt trotzdem ein eigener Schritt
    im Verlauf, den man ändern kann — hier ohne jede Bereinigung.
    """
    from_text(project, backend(), "eine kleine Figur", seed=7)
    with_repair = evaluated(project, profile)
    object_id = next(iter(with_repair.scene.objects))
    repaired = with_repair.scene.objects[object_id].mesh.triangle_count

    history = History(project.document)
    repair = next(entry for entry in history.operations if entry.op == "repair")
    history.change_params(repair.id, dict.fromkeys(repair.params, False))
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


def _open_shell_with_inner_counter_hull() -> trimesh.Trimesh:
    """Was TRELLIS.2 über ComfyUIs ``RemeshMesh`` im Modus ``udf`` liefern kann.

    Außen eine Kugel mit einem Loch — das Rohnetz von TRELLIS.2 darf offen
    sein —, innen eine zweite, nach innen gewendete Kugel knapp unter der
    Außenhaut: die Gegenseite des Abstandsfelds. Auf dem Einheitswürfel, wie
    ein Bildmodell liefert.
    """
    outer = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    top = outer.triangles_center[:, 2] > 0.99
    assert 0 < int(top.sum()) < 40, "ein Loch, kein abgeschnittener Deckel"
    outer.update_faces(~top)
    outer.remove_unreferenced_vertices()
    assert not outer.is_watertight, "die Außenhaut ist offen"
    inner = trimesh.creation.icosphere(subdivisions=4, radius=0.97)
    inner.invert()
    assert inner.volume < 0, "die Gegenhülle zeigt nach innen"
    return trimesh.util.concatenate([outer, inner])


def test_an_open_shell_with_an_inner_counter_hull_becomes_one_full_body(
    project: Project, profile: Profile
) -> None:
    """Die Reparaturkette macht aus Außenhaut mit Loch und Gegenhülle einen vollen Körper.

    Ohne den Schritt blieb die Gegenhülle als Hohlraum stehen — gültig,
    geschlossen, und gedruckt ein Körper mit Wänden von anderthalb
    Millimetern, der beim ersten Druck zerbricht. ComfyUI #16147 meldet genau
    das für TRELLIS.2. Seit ``1a05c7a50`` behält der Ablauf die Hülle in
    ComfyUI bewusst — an einer dünnen Wand ist sie die zweite Seite (RM-550) —,
    und diese Kette ist der einzige Ort, an dem die Innenhülle eines vollen
    Körpers fällt. Die erste Zusicherung hält das fest.
    """
    import json

    from app.core.backends.mesh import WORKFLOW_DIR

    shipped = json.loads((WORKFLOW_DIR / "image_to_mesh.json").read_text(encoding="utf-8"))
    remesh = next(node for node in shipped.values() if node["class_type"] == "RemeshMesh")
    assert remesh["inputs"]["sign_mode.drop_inverted_components"] is False, (
        "der Ablauf wirft die Hülle nicht weg — die Reparatur ist der einzige Ort"
    )
    payload = bytes(
        trimesh.exchange.export.export_mesh(
            _open_shell_with_inner_counter_hull(), None, file_type="glb"
        )
    )
    generation = from_text(
        project, ScriptedMeshBackend(fallback=payload, suffix=".glb"), "eine Kugel", seed=7
    )

    scene = evaluated(project, profile)
    body = scene.scene.objects[generation.object_id].mesh
    codes = {finding.code for finding in scene.scene.report.findings}

    assert "repair.inner_shells_removed" in codes, codes
    assert body.is_watertight, "das Loch der Außenhaut ist zu"
    assert body.component_count == 1, "die Gegenhülle ist weg"
    # Auf Arbeitsgröße misst die Kugel 100 mm; voll hat sie das Volumen der
    # Außenhaut, hohl nur rund ein Elftel davon (1 - 0,97³).
    full = trimesh.creation.icosphere(subdivisions=4, radius=50.0).volume
    assert body.volume == pytest.approx(full, rel=0.02)


def test_a_modelled_cavity_stays_unless_asked() -> None:
    """Ein modelliertes Teil darf einen Hohlraum tragen — der Schritt läuft nur auf Wunsch."""
    from app.core.geom.mesh import MeshData
    from app.core.geom.repair import repair

    outer = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    cavity = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    cavity.invert()
    hollow = MeshData.of(trimesh.util.concatenate([outer, cavity]))

    kept = repair(hollow)
    emptied = repair(hollow, inner_shells=True)

    assert kept.mesh.component_count == 2, "ohne Wunsch bleibt der Hohlraum"
    assert kept.mesh.volume == pytest.approx(8000.0 - 1000.0)
    assert emptied.mesh.component_count == 1
    assert emptied.mesh.volume == pytest.approx(8000.0)
    assert "repair.inner_shells_removed" in {finding.code for finding in emptied.findings}


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        # Würfel mit Kante 2: Faktor 50, also 100 mm Kante und 100³ mm³.
        ((2.0, 2.0, 2.0), 100.0 * 100.0 * 100.0),
        # Ungleiche Kanten: Die längste (2) bestimmt den Faktor 50, die
        # anderen folgen: 50 mal 100 mal 25 mm.
        ((1.0, 2.0, 0.5), 50.0 * 100.0 * 25.0),
        # Die längste Kante liegt auf einer anderen Achse: dasselbe Maß.
        ((0.5, 1.0, 4.0), 12.5 * 25.0 * 100.0),
        # Schon auf Arbeitsgröße bis auf weniger, als ein Punkt sich bewegen
        # dürfte: Faktor eins wie in ``fit_to_size`` (``fitted_factor``).
        ((100.0 + 1e-7, 50.0, 50.0), (100.0 + 1e-7) * 50.0 * 50.0),
    ],
)
def test_the_volume_at_working_size_is_that_of_the_body_on_its_largest_edge(
    size: tuple[float, float, float], expected: float
) -> None:
    """Die Versuchszeile des Dialogs nannte das Volumen des rohen Netzes.

    „2 mm³" stand dort, und zwei Schritte später hatte der Körper hundert
    Millimeter Kante. Gefragt ist das Volumen in der Größe, in der der Körper
    ins Projekt kommt; der Sollwert folgt aus der Konstruktion.
    """
    from app.core.generate import WORKING_SIZE_MM, working_volume
    from tests.helpers import FakeMesh

    assert WORKING_SIZE_MM == 100.0, "die Sollwerte oben rechnen mit 100 mm"
    assert working_volume(FakeMesh(size=size)) == pytest.approx(expected, rel=1e-12)  # type: ignore[arg-type]


def test_the_volume_at_working_size_is_what_the_stack_makes_of_it(
    project: Project, profile: Profile
) -> None:
    """Zwei Rechnungen, eine Antwort: die Auskunft des Dialogs und der Stapel.

    ``working_volume`` sagt voraus, was ``fit_to_size`` aus dem Netz macht.
    Misst die Op einmal anders — Diagonale statt längster Kante —, läuft die
    Vorhersage still davon; hier wird sie rot. Als GLB, denn so liefert
    TripoSG, und das Laden dreht dabei Y nach oben auf Z.
    """
    from app.core.generate import working_volume

    quader = trimesh.creation.box(extents=(1.0, 2.0, 0.5))
    payload = bytes(trimesh.exchange.export.export_mesh(quader, None, file_type="glb"))
    generator = ScriptedMeshBackend(fallback=payload, suffix=".glb")

    generation = from_text(project, generator, "ein Quader", seed=7)
    body = evaluated(project, profile).scene.objects[generation.object_id].mesh

    # 50 mal 100 mal 25 mm aus der Konstruktion: Faktor 100 / 2.
    assert body.volume == pytest.approx(50.0 * 100.0 * 25.0, rel=1e-6)
    assert working_volume(generation.result.mesh) == pytest.approx(body.volume, rel=1e-6)


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

    assert len(generation.transactions) == 1, "eine Erzeugung ist ein Rückgängig-Schritt (RM-372)"
    assert [entry.op for entry in project.document.ops] == [
        "load",
        "fit_to_size",
        "repair",
        "decimate_mesh",
        "fit_to_size",
    ], "Dezimieren nach der Reparatur, Kundenmaß und Aufsetzen zuletzt"
    # Die frische Vergleichsrechnung steht im kleinen Fall
    # (``…reruns_only_the_size``); hier wäre sie eine zweite volle Kette über
    # dem Dreieckslimit.
    calls, first, _after, _fresh = _resized(project, profile, 180.0, compare=False)
    entry = first.scene.objects[generation.object_id]
    assert entry.mesh.triangle_count <= GENERATED_TRIANGLE_TARGET * 1.1
    assert entry.mesh.is_watertight
    assert entry.mesh.component_count == 1
    # RM-676 über dem Dreieckslimit: Weder Reparatur noch Dezimieren laufen
    # für eine Maßänderung noch einmal.
    assert dict(calls) == {"fit_to_size": 1}, calls


def test_a_fine_generated_mesh_keeps_resolution_within_the_recognition_budget(
    project: Project, profile: Profile
) -> None:
    """Erkennbare Netze behalten ihre Auflösung auch im Erzeugungsweg.

    Die Automatik und die Erkennung beziehen ihre Grenze aus derselben
    Quelle. Ein feines Netz unter dem angehobenen Budget wird deshalb nicht
    unnötig vereinfacht und verliert trotzdem keine erkannten Merkmale.
    """
    import trimesh

    from app.core.scene.evaluate import FEATURE_LIMIT_TRIANGLES

    # Dieses feine Netz wurde von der alten 200-000-Grenze vereinfacht.
    mittel = trimesh.creation.icosphere(subdivisions=7, radius=30.0)
    assert 200_000 < len(mittel.faces) <= FEATURE_LIMIT_TRIANGLES, (
        f"{len(mittel.faces)} Dreiecke liegen nicht im Bereich, um den es geht"
    )
    payload = bytes(trimesh.exchange.export.export_mesh(mittel, None, file_type="ply"))

    generator = ScriptedMeshBackend(fallback=payload, suffix=".ply")
    generation = from_text(project, generator, "eine Vase", seed=7)

    assert len(generation.transactions) == 1, "eine Erzeugung ist ein Rückgängig-Schritt"
    assert "decimate_mesh" not in [entry.op for entry in project.document.ops], (
        "Laden, Größe, Reparieren samt Aufsetzen — keine Dezimierung"
    )

    result = evaluated(project, profile)
    entry = result.scene.objects[generation.object_id]

    assert entry.mesh.triangle_count == len(mittel.faces), "unnötig Auflösung verloren"
    assert entry.features, "Erkennung trotz zulässiger Auflösung übersprungen"
    assert entry.mesh.is_watertight, "im Erzeugungsweg aufgerissen"
    assert entry.mesh.component_count == 1, (
        f"im Erzeugungsweg in {entry.mesh.component_count} Teile zerfallen"
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


# --- ein erzeugtes Modell ist ein weiteres Modell (Robert, 28.09.2026) ---------


def _sphere_backend() -> ScriptedMeshBackend:
    """Eine geschlossene Kugel auf dem Einheitswürfel, wie ein Bildmodell sie liefert."""
    kugel = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    return ScriptedMeshBackend(
        fallback=bytes(trimesh.exchange.export.export_mesh(kugel, None, file_type="ply")),
        suffix=".ply",
    )


def _with_a_model_first(project: Project, name: str, payload: bytes) -> None:
    """Ein Modell über den Einlesplan, wie das Fenster es als erstes einfügt."""
    from app.core.ingest.plan import import_plan
    from app.core.types import Source

    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    project.sources["src_1"] = payload
    chosen = import_plan("src_1", name, payload, "mm", first_model=True)
    History(project.document).apply(chosen.title, [chosen.draft])


def _apart(one, other, spacing: float) -> bool:
    a, b = one.mesh.bounds, other.mesh.bounds
    return bool(
        a.maximum[0] + spacing <= b.minimum[0] + 1e-6
        or b.maximum[0] + spacing <= a.minimum[0] + 1e-6
        or a.maximum[1] + spacing <= b.minimum[1] + 1e-6
        or b.maximum[1] + spacing <= a.minimum[1] + 1e-6
    )


def test_a_generated_model_in_an_empty_project_stands_in_the_middle(
    project: Project, profile: Profile
) -> None:
    """Wie das erste eingefügte Modell (§17.1, Schritt 6): aufgesetzt und mittig —
    gelegt nach der Größenanpassung, am fertigen Maß von 100 mm."""
    result = from_text(project, _sphere_backend(), "eine Kugel", seed=7)
    scene = evaluated(project, profile)

    assert scene.complete
    body = scene.scene.objects[result.object_id]
    assert body.plate == 0
    assert max(body.mesh.bounds.size) == pytest.approx(100.0, abs=1e-3)
    assert body.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6), "aufgesetzt"
    assert body.mesh.bounds.centre[:2] == pytest.approx((0.0, 0.0), abs=1e-6), "mittig"


def test_a_generated_model_goes_to_a_free_spot_beside_what_is_there(
    project: Project, profile: Profile
) -> None:
    """Ein erzeugtes Modell ist aus Kundensicht ein weiteres Modell: an die
    erste freie Stelle der ersten Platte, ganz auf der Druckfläche, im Abstand
    der Anordnung — und der Würfel davor bleibt, wo er war."""
    from app.core.build_area import fits_on_bed
    from app.core.geom.prepare import ARRANGE_SPACING

    _with_a_model_first(project, "wuerfel.stl", (MESHES / "cube_clean.stl").read_bytes())
    result = from_text(project, _sphere_backend(), "eine Kugel", seed=7)
    scene = evaluated(project, profile)

    assert scene.complete
    cube, body = scene.scene.objects["obj_1"], scene.scene.objects[result.object_id]
    assert cube.mesh.bounds.centre[:2] == pytest.approx((0.0, 0.0)), "der Würfel bleibt"
    assert (cube.plate, body.plate) == (0, 0), "Platz war auf der ersten Platte"
    assert max(body.mesh.bounds.size) == pytest.approx(100.0, abs=1e-3), "am fertigen Maß"
    assert fits_on_bed(body.mesh, profile.printer), "ganz auf der Druckfläche"
    assert body.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6), "aufgesetzt"
    assert _apart(cube, body, ARRANGE_SPACING), "nicht im Würfel"
    codes = {entry.code for entry in scene.scene.report.findings}
    assert "arrange.free_spot" in codes


def test_a_generated_model_stays_seated_when_the_repair_takes_a_crumb_below_it(
    project: Project, profile: Profile
) -> None:
    """Review F8 (Sonde p1): Ein loser Krümel unter der Kugel stand nach
    *Auf Maß bringen* auf dem Bett, die Reparaturkette nahm ihn weg, und der
    Körper schwebte 5,21 mm darüber. Aufgesetzt wird deshalb nach der Kette."""
    kugel = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    splitter = trimesh.creation.icosphere(subdivisions=1, radius=0.01)
    splitter.apply_translation([0.0, 0.0, -1.1])
    body = trimesh.util.concatenate([kugel, splitter])
    backend = ScriptedMeshBackend(
        fallback=bytes(trimesh.exchange.export.export_mesh(body, None, file_type="ply")),
        suffix=".ply",
    )

    result = from_text(project, backend, "eine Kugel", seed=7)
    scene = evaluated(project, profile)

    assert scene.complete
    entry = scene.scene.objects[result.object_id]
    assert entry.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6), "auf dem Bett"
    assert "arrange.above_bed" not in {finding.code for finding in scene.scene.report.findings}
    last = project.document.ops[-1]
    assert (last.op, last.params.get("free_spot")) == ("fit_to_size", True), (
        "gelegt und aufgesetzt wird im letzten Schritt, nach der Reparatur"
    )
    # Und am Kundenmaß, nicht an dem, was die Reparatur von der Arbeitsgröße
    # übrig ließ: Der Krümel machte die Kante länger als die Kugel.
    assert max(entry.mesh.bounds.size) == pytest.approx(100.0, abs=1e-3)


def _fingerprints(result) -> dict[str, str]:
    """Je Körper ein Abdruck seiner Ecken und Dreiecke — bitgleich oder nicht."""
    import hashlib

    from app.core.geom.mesh import as_mesh_data

    prints = {}
    for object_id, entry in result.scene.objects.items():
        raw = as_mesh_data(entry.mesh).raw
        digest = hashlib.sha256(np.asarray(raw.vertices, dtype=np.float64).tobytes())
        digest.update(np.asarray(raw.faces, dtype=np.int64).tobytes())
        prints[object_id] = digest.hexdigest()
    return prints


def test_a_generation_is_one_step_in_the_history(project: Project, profile: Profile) -> None:
    """RM-372: Eine Erzeugung legte drei bis vier Transaktionen an. Nach dem
    ersten Strg+Z änderte sich bei einem dichten Netz nichts Sichtbares, nach
    dem zweiten lag ein Krümel von zwei Millimetern da, erst der dritte nahm
    das Modell weg (Review N5 hatte nur das Aufsetzen in die Reparatur gelegt).

    Jetzt ist sie eine Transaktion mit dem Titel der Erzeugung; die Schritte
    stehen einzeln im Verlauf, ein Strg+Z nimmt das ganze Modell, Strg+Y legt
    es bitgleich wieder hin.
    """
    from app.core.scene import ResultCache

    generation = from_text(project, _sphere_backend(), "eine Kugel", seed=7)

    transactions = project.document.transactions
    assert [entry.id for entry in transactions] == list(generation.transactions)
    assert len(transactions) == 1, [str(entry.title) for entry in transactions]
    assert str(transactions[0].title) == "Modell erzeugen"
    by_id = {operation.id: operation.op for operation in project.document.ops}
    assert [by_id[op_id] for op_id in transactions[0].ops] == [
        "load",
        "fit_to_size",
        "repair",
        "fit_to_size",
    ], "die Schritte bleiben einzeln im Verlauf"
    before = _fingerprints(evaluate(project.document, profile, sources=ProjectSources(project)))
    assert generation.object_id in before

    history = History(project.document)
    history.undo()
    taken_back = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=ResultCache()
    )
    assert project.document.ops == [], "ein Strg+Z nimmt das ganze Modell"
    assert not taken_back.scene.objects

    history.redo()
    again = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=ResultCache()
    )
    assert _fingerprints(again) == before, "Strg+Y legt das Modell bitgleich wieder hin"


def test_the_agent_takes_a_generation_back_as_one_step(project: Project) -> None:
    """Der Agentenweg derselben Erzeugung (RM-372): „Nimm das Modell zurück“
    nennt die Transaktion der Erzeugung, und die Rücknahme erfasst genau sie —
    keine Ankündigung, dass drei jüngere mitgehen (``agent.undo_sweeps``)."""
    from app.core.agent.apply import accept, sweep_for
    from app.core.agent.proposal import Proposal

    generation = from_text(project, _sphere_backend(), "eine Kugel", seed=7)
    (made,) = generation.transactions

    assert sweep_for(project.document, made) == (made,)
    history = History(project.document)
    accept(Proposal(request="nimm das Modell zurück", undo_of=made, undo_sweeps=(made,)), history)

    assert project.document.ops == []
    assert project.document.transactions == []


def test_a_generated_model_goes_to_the_next_plate_when_the_first_is_full(
    project: Project, profile: Profile
) -> None:
    """Eine Platte von 230 mm lässt auf dem 256er Bett keinen Platz für 100 mm:
    Das erzeugte Modell kommt auf die nächste Platte, dort mittig."""
    from app.core.build_area import fits_on_bed

    plate = trimesh.creation.box(extents=(230.0, 230.0, 4.0))
    _with_a_model_first(project, "platte.stl", bytes(plate.export(file_type="stl")))
    result = from_text(project, _sphere_backend(), "eine Kugel", seed=7)
    scene = evaluated(project, profile)

    assert scene.complete
    body = scene.scene.objects[result.object_id]
    assert body.plate == 1
    assert fits_on_bed(body.mesh, profile.printer)
    assert body.mesh.bounds.centre[:2] == pytest.approx((0.0, 0.0), abs=1e-6)


# --- Zerfallene Rohnetze (RM-550) ------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("generated_fell_apart.glb", True),
        ("generated_touching.glb", False),
        ("cubes_touching_edge.glb", False),
    ],
)
def test_a_raw_mesh_that_fell_apart_in_the_generator_is_recognised(
    name: str, expected: bool
) -> None:
    """Ein Rohnetz, das schon im Generator zerfällt, repariert keine Kette (RM-550).

    Gemessen an echten Läufen von TRELLIS.2: Ein zerfallenes Netz hat
    Tausende Kanten mit mehr als zwei Flächen, und keine lässt sich trennen;
    jeder dieser Läufe endete offen. Ein heiles hat ein paar Dutzend, dort, wo
    sich zwei Stücke berühren, und die Reparatur trennt sie. Ein kleines Netz
    mit einer einzigen Berührkante liegt über dem Anteil und ist trotzdem
    heil — deshalb zählt erst, was nach dem Trennen bleibt.
    """
    from app.core.generate import fell_apart
    from app.core.geom.mesh import read_mesh

    mesh = read_mesh((Path(__file__).parent / "data" / "meshes" / name).read_bytes(), ".glb")

    assert fell_apart(mesh) is expected


# --- Nur eine Haut (RM-577) -------------------------------------------------------


def _cup(wall: float) -> bytes:
    """Ein oben offener Becher 100 × 100 × 60 mm mit Wand ``wall`` — als Vollkörper
    geschlossen, im Mittel so dick wie seine Wand."""
    import manifold3d

    outer = manifold3d.Manifold.cube((100.0, 100.0, 60.0))
    inner = manifold3d.Manifold.cube((100.0 - 2 * wall, 100.0 - 2 * wall, 60.0)).translate(
        (wall, wall, wall)
    )
    body = (outer - inner).to_mesh()
    cup = trimesh.Trimesh(
        np.asarray(body.vert_properties)[:, :3], np.asarray(body.tri_verts), process=False
    )
    return bytes(trimesh.exchange.export.export_mesh(cup, None, file_type="stl"))


@pytest.mark.parametrize(("wall", "warned"), [(0.3, True), (5.0, False)])
def test_a_generated_body_that_is_only_a_skin_is_reported(
    project: Project, profile: Profile, wall: float, warned: bool
) -> None:
    """TRELLIS.2 lieferte fünf von 17 Körpern als Haut von 0,3 mm um einen Hohlraum,
    geschlossen und ohne Befund (RM-577). Am Endstand steht jetzt ein Befund mit
    dem Ausweg *Neu erzeugen* — gemessen gegen die dünnste Wand des Materials."""
    from app.core.errors import GENERATE_AGAIN

    from_text(project, ScriptedMeshBackend(fallback=_cup(wall), suffix=".stl"), "Becher", seed=1)

    scene = evaluated(project, profile)

    skins = [f for f in scene.scene.report.findings if f.code == "scene.thin_skin"]
    assert bool(skins) is warned, [f.code for f in scene.scene.report.findings]
    if warned:
        assert skins[0].severity == "warning" and GENERATE_AGAIN in skins[0].suggestions
        assert skins[0].values["thickness_mm"] < skins[0].values["least_mm"]
        assert "{" not in str(skins[0].message)


def test_the_skin_limit_is_the_wall_of_the_profile_not_a_number(
    project: Project, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 7: Druckt das Material Wände ab 0,2 mm, ist ein Becher mit 0,3 mm
    keine Haut — mit einer festen Grenze im Code bliebe der Befund (Nachprüfung K, N8)."""
    import importlib

    checks = importlib.import_module("app.core.scene.evaluate")
    from_text(project, ScriptedMeshBackend(fallback=_cup(0.3), suffix=".stl"), "Becher", seed=1)
    monkeypatch.setattr(checks, "analysis_limits", lambda _profile, _entry: (0.2, 45.0))

    scene = evaluated(project, profile)

    assert "scene.thin_skin" not in {f.code for f in scene.scene.report.findings}


def _thick_cube_beside_a_wide_thin_plate() -> trimesh.Trimesh:
    """Zwei Schalen: ein Würfel von 15 mm mit gut einem Zehntel der Fläche und eine
    Platte von 75 × 75 × 0,05 mm, die den Rest trägt."""
    cube = trimesh.creation.box(extents=(15.0, 15.0, 15.0))
    plate = trimesh.creation.box(extents=(75.0, 75.0, 0.05))
    plate.apply_translation((0.0, 0.0, 30.0))
    return trimesh.util.concatenate([cube, plate])


def test_the_dialog_and_the_report_judge_a_skin_alike(project: Project, profile: Profile) -> None:
    """Eine dicke Schale neben einer großen dünnen ist an beiden Orten kein Hautkörper —
    eine Herleitung für Dialog und Bericht (Nachprüfung K, N7). Über den ganzen
    Körper gerechnet hätte der Bericht hier eine Haut von 0,6 mm genannt."""
    from app.core.generate import skin_thickness
    from app.core.geom.mesh import MeshData, only_a_skin

    body = _thick_cube_beside_a_wide_thin_plate()
    least = profile.minimum_wall_thickness
    whole = 2.0 * body.volume / body.area
    assert only_a_skin(whole, least), "die alte Rechnung hätte eine Haut gemeldet"
    assert not only_a_skin(skin_thickness(MeshData.of(body)), least)

    payload = bytes(trimesh.exchange.export.export_mesh(body, None, file_type="stl"))
    from_text(project, ScriptedMeshBackend(fallback=payload, suffix=".stl"), "Zwei", seed=1)
    scene = evaluated(project, profile)

    assert "scene.thin_skin" not in {f.code for f in scene.scene.report.findings}


def test_a_thin_imported_body_is_not_called_a_generated_skin(
    project: Project, profile: Profile
) -> None:
    """Ein eingelesenes dünnes Teil hat seine Wand mit Absicht — die Frage gilt nur
    erzeugten Körpern (RM-577)."""
    from app.core.ingest.plan import import_plan
    from app.core.scene.project import checksum
    from app.core.types import Source

    payload = _cup(0.3)
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/becher.stl", sha256=checksum(payload)
    )
    project.sources["src_1"] = payload
    plan = import_plan("src_1", "becher.stl", payload, first_model=True)
    History(project.document).apply(plan.title, [plan.draft])

    scene = evaluated(project, profile)

    assert "scene.thin_skin" not in {f.code for f in scene.scene.report.findings}


def test_the_stored_skin_from_the_measurement_is_measured_as_one() -> None:
    """Die gespeicherte Haut (Text, Startwert 14) misst 0,26 mm, ein heiler Würfel
    viele Millimeter (``generate.skin_thickness``, RM-577)."""
    from app.core.generate import skin_thickness
    from app.core.geom.mesh import MeshData

    stored = np.load(MESHES / "generated_skin.npz")
    skin = MeshData.of(
        trimesh.Trimesh(stored["vertices"].astype(float), stored["faces"], process=False)
    )
    cube = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))

    assert 0.2 < (skin_thickness(skin) or 0.0) < 0.35
    assert (skin_thickness(cube) or 0.0) > 10.0


# --- *Größe ändern* rechnet nur das Maß neu (RM-676) ---------------------------


def _summary(result, object_id: str) -> tuple[object, ...]:
    """Was der Kunde vom Ergebnis sieht: Volumen, Maße, Lage und die Befunde."""
    body = result.scene.objects[object_id]
    return (
        round(float(body.mesh.volume), 6),
        tuple(round(float(value), 6) for value in body.mesh.bounds.size),
        round(float(body.mesh.bounds.minimum[2]), 6),
        body.plate,
        sorted(
            (entry.code, entry.severity, entry.op_id, entry.object_id)
            for entry in result.scene.report.findings
        ),
    )


def _resized(project: Project, profile: Profile, largest: float, *, compare: bool = True):
    """*Größe ändern* wie am Befund: der Schritt, den ``transform.fitted`` anbietet,
    bekommt ein neues Maß, und der Lauf danach nimmt den Cache des ersten.

    Gibt zurück, welche Operationen dafür gerechnet haben, das erste Ergebnis,
    das danach und zum Vergleich eine frische Rechnung desselben Dokuments ohne
    Cache — mit ``compare=False`` keine, wo die volle Kette teuer ist.
    """
    import dataclasses
    from collections import Counter

    from app.core.registry import REGISTRY
    from app.core.registry.registry import Registry
    from app.core.scene import ResultCache

    calls: Counter[str] = Counter()

    def counted(name: str, fn):
        def run(ctx):
            calls[name] += 1
            return fn(ctx)

        return run

    registry = Registry()
    for spec in REGISTRY.all():
        registry.register(dataclasses.replace(spec, fn=counted(spec.name, spec.fn)))
    cache = ResultCache()
    document = project.document

    def run(into: ResultCache, with_registry: Registry | None):
        return evaluate(
            document, profile, sources=ProjectSources(project), cache=into, registry=with_registry
        )

    first = run(cache, registry)
    offered = [
        entry
        for entry in first.scene.report.findings
        if entry.code == "transform.fitted"
        and any(action.id == "change_step" for action in entry.suggestions)
    ]
    assert [entry.op_id for entry in offered] == [document.ops[-1].id], (
        "*Größe ändern* steht genau einmal im Bericht, am letzten Schritt"
    )
    step = History(document).operation(offered[0].op_id)
    transactions = len(document.transactions)

    calls.clear()
    History(document).change_params(step.id, {**dict(step.params), "largest": largest})
    assert len(document.transactions) == transactions + 1, "ein Rückgängig-Schritt"
    after = run(cache, registry)
    fresh = run(ResultCache(), None) if compare else None
    return calls, first, after, fresh


def _same_result(after, fresh) -> None:
    """Mit und ohne Cache bitgleich (§11.2, §15.1): Netze, Merkmale, Befunde."""
    assert _fingerprints(after) == _fingerprints(fresh)
    assert {key: sorted(entry.features) for key, entry in after.scene.objects.items()} == {
        key: sorted(entry.features) for key, entry in fresh.scene.objects.items()
    }
    for object_id in after.scene.objects:
        assert _summary(after, object_id) == _summary(fresh, object_id)


def test_changing_the_size_of_a_generated_model_reruns_only_the_size(
    project: Project, profile: Profile
) -> None:
    """RM-676: *Größe ändern* am erzeugten Drachen (der „Stuhl“ der
    Regressionsmessung) rechnete Reparatur, Aufsetzen und die Merkmalserkennung
    am vollen Netz neu — 67 bis 139 s statt der 18 bis 22 s, die das angehängte
    Skalieren in v0.5.1 brauchte.

    Die Kette repariert jetzt an der Arbeitsgröße und trägt das Kundenmaß als
    eigenen Schritt dahinter; eine Maßänderung rechnet nur ihn. Das Ergebnis ist
    dasselbe wie eine frische Rechnung im neuen Maß, und ein Strg+Z holt das alte.
    """
    generation = from_text(project, backend(), "eine kleine Figur", seed=7)

    calls, _first, result, fresh = _resized(project, profile, 250.0)

    assert dict(calls) == {"fit_to_size": 1}, calls
    _same_result(result, fresh)
    body = result.scene.objects[generation.object_id]
    assert max(body.mesh.bounds.size) == pytest.approx(250.0, abs=1e-3)
    assert body.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6), "steht auf dem Bett"

    History(project.document).undo()
    back = evaluated(project, profile).scene.objects[generation.object_id]
    assert max(back.mesh.bounds.size) == pytest.approx(100.0, abs=1e-3), "Strg+Z holt das Maß"
    assert project.document.ops[-1].op == "fit_to_size"


def test_the_working_size_step_names_the_step_that_sets_the_size(
    project: Project, profile: Profile
) -> None:
    """Review D, M1: Zwei gleich benannte *Auf Maß bringen* stehen im Verlauf. Der
    Bericht bietet *Größe ändern* nur am letzten an (``SETTLED_BY``), und dieselbe
    Auskunft kennt der Verlauf: Der frühere nennt den späteren, der letzte keinen.
    Zwei Wege zu derselben Antwort — hier gegeneinander gehalten.
    """
    from app.core.scene.evaluate import size_set_by

    from_text(project, backend(), "eine kleine Figur", seed=7)
    ops = project.document.ops
    sizing = [entry.id for entry in ops if entry.op == "fit_to_size"]
    assert len(sizing) == 2, [entry.op for entry in ops]

    result = evaluated(project, profile)
    offered = [
        entry.op_id
        for entry in result.scene.report.findings
        if entry.code == "transform.fitted"
        and any(action.id == "change_step" for action in entry.suggestions)
    ]

    assert size_set_by(ops, sizing[0]) == sizing[1]
    assert size_set_by(ops, sizing[1]) is None
    assert offered == [step for step in sizing if size_set_by(ops, step) is None]
    assert size_set_by(ops, ops[0].id) is None, "nur ein Maßschritt wird überholt"


#: Was ``generated_chain_before_rm676_v49.p3d`` am Stand vor RM-676 (welle2
#: ``a9e4d3f64``) beim Schreiben ergab: Der Krümel bestimmte das Maß vor der
#: Reparatur, übrig blieb ein Körper mit 39,84 mm Kante, gelegt um die Mitte
#: von Schale und Krümel.
SAVED_EARLIER_CHAIN = {
    "volume": 63238.1004011136,
    "size": (39.84063684470132, 39.84063684470132, 39.84063684470132),
    "minimum": (-50.0, -50.0, 0.0),
    "findings": [
        ("arrange.free_spot", "info", 2),
        ("repair.components_removed", "info", 3),
        ("repair.holes_filled", "info", 3),
        ("repair.welded", "info", 3),
        ("repair.wide_hole_filled", "warning", 3),
        ("transform.fitted", "info", 2),
    ],
}


def test_a_project_saved_with_the_earlier_chain_computes_as_saved(profile: Profile) -> None:
    """Gespeicherte Erzeugungen behalten ihre Kette (RM-676): erst das Maß, dann
    die Reparatur, dann aufsetzen. Sie wird nicht umgebaut — die Reparatur an
    einem anderen Maß rechnete ein anderes Netz —, und *Größe ändern* bleibt
    dort am Maßschritt, wo es war.
    """
    project = load(MESHES.parent / "projects" / "generated_chain_before_rm676_v49.p3d")
    ops = project.document.ops
    assert [entry.op for entry in ops] == ["load", "fit_to_size", "repair", "place_on_bed"]

    result = evaluated(project, profile)

    assert result.complete
    body = result.scene.objects["obj_1"]
    assert float(body.mesh.volume) == pytest.approx(SAVED_EARLIER_CHAIN["volume"], rel=1e-9)
    assert tuple(body.mesh.bounds.size) == pytest.approx(SAVED_EARLIER_CHAIN["size"], abs=1e-9)
    assert tuple(body.mesh.bounds.minimum) == pytest.approx(
        SAVED_EARLIER_CHAIN["minimum"], abs=1e-9
    )
    assert (
        sorted((f.code, f.severity, f.op_id) for f in result.scene.report.findings)
        == SAVED_EARLIER_CHAIN["findings"]
    )
    offered = [
        entry.op_id
        for entry in result.scene.report.findings
        if entry.code == "transform.fitted"
        and any(action.id == "change_step" for action in entry.suggestions)
    ]
    assert offered == [ops[1].id]
