"""Weg 4 aus §2.2, Ende zu Ende (Bauplan §40, Konzept P16 §16).

    Grundkörper → weich verschmelzen → gleichmäßig vernetzen → formen →
    Prüfbericht → exportieren.

Das ist die Abnahme der organischen Phase: eine Figur vom Grundkörper bis zum
druckfertigen 3MF, ohne dass ein zweites Programm geöffnet wird. Und die
Zusage, an der alles hängt — dieselbe Figur nach dem Wiederöffnen der
Projektdatei liefert **identische** Geometrie.

Die Züge sind hier drei, keine viertausend. Was geprüft wird, ist die Kette
und nicht die Kunst: dass jeder Schritt den nächsten trägt, dass die Datei die
Rechnung überlebt und dass am Ende etwas herauskommt, das ein Drucker annimmt.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from app.core.export.writer import plan_export, write_plan
from app.core.geom.mesh import as_mesh_data
from app.core.geom.sculpt import strokes_to_text
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, load, new_project, save
from app.core.types import Profile, Stroke

#: Wie lange der ganze Weg höchstens dauern darf. Kein Budget aus §31 — das
#: gilt einzelnen Operationen —, sondern die Schwelle, ab der die Kette als
#: Ganzes nicht mehr benutzbar wäre. Gemessen liegt sie bei rund vier
#: Sekunden; dreißig fangen eine langsame Maschine ab und melden trotzdem,
#: wenn ein Schritt um eine Größenordnung entgleist.
WHOLE_WAY_SECONDS = 30.0


def figure_project() -> Project:
    """Die vier Schritte des Beispielprojekts, plus drei Pinselzüge.

    Derselbe Aufbau wie ``weg4-figur-formen.p3d`` — nur dass dieses Projekt
    auch den letzten Schritt geht, den das Beispiel dem Nutzer überlässt.
    """
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)

    history.apply(
        "Rumpf",
        [
            OperationDraft(
                op="create_box",
                params={"width": 24.0, "depth": 14.0, "height": 40.0, "name": "Figur"},
            )
        ],
    )
    history.apply(
        "Kopf", [OperationDraft(op="create_sphere", params={"diameter": 18.0, "name": "Kopf"})]
    )
    history.apply(
        "Kopf setzen",
        [
            OperationDraft(
                op="translate_object", inputs=("obj_2",), params={"dx": 0.0, "dy": 0.0, "dz": 26.0}
            )
        ],
    )
    history.apply(
        "Weich verschmelzen",
        [
            OperationDraft(
                op="blend_union", inputs=("obj_1", "obj_2"), params={"radius": 4.0, "grid": 1.2}
            )
        ],
    )
    history.apply(
        "Gleichmäßig vernetzen",
        [
            OperationDraft(
                op="remesh_uniform", inputs=("obj_3",), params={"edge": 1.5, "deviation": 0.0}
            )
        ],
    )
    history.apply(
        "Formen",
        [
            OperationDraft(
                op="sculpt_strokes",
                inputs=("obj_3",),
                params={
                    "strokes": strokes_to_text(
                        [
                            Stroke(
                                point=(0.0, 8.0, 30.0),
                                normal=(0.0, 1.0, 0.0),
                                radius=6.0,
                                strength=1.5,
                            ),
                            Stroke(
                                point=(12.0, 0.0, 10.0),
                                normal=(1.0, 0.0, 0.0),
                                radius=5.0,
                                strength=1.0,
                            ),
                            Stroke(
                                point=(0.0, 0.0, 44.0),
                                normal=(0.0, 0.0, 1.0),
                                radius=7.0,
                                strength=2.0,
                                tool="smooth",
                            ),
                        ]
                    ),
                    "symmetry": "x",
                },
            )
        ],
    )
    return project


def evaluated(project: Project, profile: Profile):  # type: ignore[no-untyped-def]
    return evaluate(project.document, profile, sources=ProjectSources(project))


# --- die Kette ------------------------------------------------------------------


def test_the_whole_way_runs_without_a_second_program(profile: Profile) -> None:
    """§16.3: vom Grundkörper bis zum Körper, in einem Fenster.

    Sechs Schritte, und jeder trägt den nächsten: Zwei Grundformen werden
    weich vereinigt, das Ergebnis gleichmäßig vernetzt, darauf wird geformt.
    Bricht einer davon, hält die Auswertung an, und dieser Test sagt es.
    """
    started = time.perf_counter()
    project = figure_project()
    result = evaluated(project, profile)
    taken = time.perf_counter() - started

    assert result.complete, "die Kette hält an"
    assert len(result.scene.objects) == 1, "am Ende steht eine Figur"
    body = as_mesh_data(next(iter(result.scene.objects.values())).mesh)
    assert body.is_watertight
    assert body.component_count == 1
    assert body.volume > 0.0
    print(f"\nWeg 4 vollständig: {taken:.2f} s")
    assert taken < WHOLE_WAY_SECONDS


def test_each_step_leaves_the_body_closed(profile: Profile) -> None:
    """Kein Schritt darf das Netz aufreißen — sonst fällt es dem nächsten vor
    die Füße, und der Fehler wird dort gesucht, wo er nicht ist.
    """
    project = figure_project()
    document = project.document

    for count in range(1, len(document.ops) + 1):
        partial = new_project("centauri-carbon-2", "petg")
        partial.document.ops = document.ops[:count]
        partial.document.transactions = document.transactions
        result = evaluate(partial.document, profile, sources=ProjectSources(partial))
        assert result.complete, f"Schritt {count} hält an"
        for entry in result.scene.objects.values():
            mesh = as_mesh_data(entry.mesh)
            assert mesh.is_watertight, f"Schritt {count} hat {entry.id} geöffnet"


# --- die Zusage, an der alles hängt ---------------------------------------------


def test_the_reopened_project_gives_identical_geometry(profile: Profile, tmp_path: Path) -> None:
    """§16.4: Hash-Vergleich nach dem Wiederöffnen.

    Das ist die Abnahme der ganzen Phase. Ein Sculpting-Vorgang, der beim
    zweiten Öffnen etwas anderes ergibt, wäre kein Op-Stapel, sondern ein
    Bild mit Zwischenschritten — und alles, was dieses Konzept über
    Reproduzierbarkeit sagt, wäre eine Behauptung.
    """
    project = figure_project()
    before = as_mesh_data(next(iter(evaluated(project, profile).scene.objects.values())).mesh)

    path = save(project, tmp_path / "figur.p3d")
    reopened = load(path)
    after = as_mesh_data(next(iter(evaluated(reopened, profile).scene.objects.values())).mesh)

    assert np.array_equal(np.asarray(before.raw.vertices), np.asarray(after.raw.vertices)), (
        "dieselbe Datei, dieselben Eckpunkte"
    )
    assert before.triangle_count == after.triangle_count


def test_the_strokes_survive_the_file(profile: Profile, tmp_path: Path) -> None:
    """Und die Züge selbst stehen danach unverändert im Dokument.

    Die Geometrie könnte auch zufällig gleich sein; hier steht, dass der
    Sammelwert die Reise übersteht — die Eigenschaft aus Regel 2, an der die
    ganze Bauart hängt.
    """
    project = figure_project()
    original = str(project.document.ops[-1].params["strokes"])

    reopened = load(save(project, tmp_path / "figur.p3d"))

    assert str(reopened.document.ops[-1].params["strokes"]) == original
    assert reopened.document.ops[-1].params["symmetry"] == "x"


# --- und hinaus -----------------------------------------------------------------


def test_the_way_ends_in_a_printable_file(profile: Profile, tmp_path: Path) -> None:
    """§16.3: bis zum druckfertigen 3MF, ohne ein zweites Programm."""
    project = figure_project()
    result = evaluated(project, profile)

    plan = plan_export(
        list(result.scene.objects.values()),
        project_name="Figur",
        profile=profile,
        export_format="3mf",
    )
    written = write_plan(plan, tmp_path)

    assert written[0].exists()
    assert written[0].name.endswith(".3mf")
    assert written[0].stat().st_size > 0


def test_the_report_says_what_the_printer_thinks(profile: Profile) -> None:
    """Was die Phase begründet: Am Ende steht kein Netz, sondern ein Urteil.

    Ein Sculpting-Programm liefert eine Form; hier liegt daneben, was der
    Drucker davon hält — und das ist der Unterschied, den §17 als
    Wettbewerbsvorsprung benennt.
    """
    project = figure_project()

    result = evaluated(project, profile)

    codes = {finding.code for finding in result.scene.report.findings}
    assert codes, "der Prüfbericht ist nicht leer"
    assert "sculpt.applied" in codes, "die Formsitzung meldet sich"


def test_a_changed_parameter_reruns_the_chain(profile: Profile) -> None:
    """Der eigentliche Gewinn gegenüber einem Sculpting-Programm.

    Der Übergang zwischen Rumpf und Kopf ist eine Zahl. Sie zu ändern baut die
    Figur neu — mit denselben Zügen darauf, ohne dass jemand sie wiederholt.
    """
    project = figure_project()
    thin = as_mesh_data(next(iter(evaluated(project, profile).scene.objects.values())).mesh)

    blend = next(entry for entry in project.document.ops if entry.op == "blend_union")
    History(project.document).change_params(blend.id, {"radius": 9.0})
    thick = as_mesh_data(next(iter(evaluated(project, profile).scene.objects.values())).mesh)

    assert thick.volume > thin.volume, "ein breiterer Übergang trägt auf"
    assert thick.is_watertight
