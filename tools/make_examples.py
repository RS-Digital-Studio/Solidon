"""Build the three example projects (Bauplan §37.2, §2.2).

They are documentation, acceptance test and start screen content at once, so
they are built the way everything else is built: as operations on a stack. A
folder of hand-exported files would drift from the application the first time an
operation changed.

    python tools/make_examples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.backends.mesh import ScriptedMeshBackend
from app.core.bootstrap import load_operations
from app.core.examples import directory
from app.core.generate import from_text
from app.core.knowledge import profiles
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project, save
from app.core.types import Parameter, Source, SourceKind

CORPUS = Path(__file__).resolve().parent.parent / "tests" / "data" / "meshes"


def with_source(project: Project, name: str, mesh: str, kind: SourceKind = "import") -> None:
    project.document.sources[name] = Source(id=name, kind=kind, path=f"sources/{mesh}", sha256="")
    project.sources[name] = (CORPUS / mesh).read_bytes()


def way_one() -> Project:
    """Adapting a foreign model: import, repair, on the bed, drill (§2.2)."""
    project = new_project("centauri-carbon-2", "petg")
    with_source(project, "src_1", "plate_holes.stl")
    history = History(project.document)
    history.apply(
        "Modell laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    history.apply("Reparieren", [OperationDraft(op="repair", inputs=("obj_1",), params={})])
    history.apply("Auf das Bett", [OperationDraft(op="place_on_bed", inputs=("obj_1",))])
    history.apply(
        "Bohrung setzen",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 4.2, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"},
            )
        ],
    )
    return project


def way_two() -> Project:
    """Building new: parameters, a body, parts from the library (§2.2)."""
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.parameters["breite"] = Parameter(name="breite", value=60.0, unit="mm", title="Breite")
    document.parameters["tiefe"] = Parameter(name="tiefe", value=40.0, unit="mm", title="Tiefe")
    document.parameters["staerke"] = Parameter(name="staerke", value=6.0, unit="mm", title="Stärke")

    history = History(document)
    history.apply(
        "Grundkörper",
        [
            OperationDraft(
                op="create_box",
                params={
                    "width": "=@breite",
                    "depth": "=@tiefe",
                    "height": "=@staerke",
                    "name": "Halter",
                },
            )
        ],
    )
    history.apply(
        "Schraubenlöcher",
        [
            OperationDraft(
                op="insert_screw_hole",
                inputs=("obj_1",),
                params={"size": "M4", "depth": 6.0, "x": -20.0, "z": "=@staerke"},
            ),
            OperationDraft(
                op="insert_screw_hole",
                inputs=("obj_1",),
                params={"size": "M4", "depth": 6.0, "x": 20.0, "z": "=@staerke"},
            ),
        ],
    )
    history.apply(
        "Versteifung",
        [
            OperationDraft(
                op="insert_rib",
                inputs=("obj_1",),
                params={"length": 30.0, "height": 5.0, "wall": 6.0, "z": "=@staerke"},
            )
        ],
    )
    return project


def way_three() -> Project:
    """Ein erzeugtes Netz aufbereiten: Reparaturkette, dann auf das Bett (§2.2).

    Der Weg ist der echte — dieselben zwei Transaktionen, die eine Erzeugung
    macht, mit Prompt und Startwert in der Quelle (§27). Nur der Generator ist
    geskriptet: ein Beispielprojekt, für dessen Bau eine Grafikkarte nötig ist,
    ist kein Beispiel.

    Das Netz ist ``generated_figure.stl`` und nicht ``broken_open.stl``. Dem
    zweiten fehlt eine ganze Wand — das kann keine Reparatur schließen, und ein
    Beispiel, das nach der Reparatur immer noch „nicht geschlossen" meldet,
    führt vor, dass es nicht funktioniert. Die Figur bringt die Fehler mit, die
    ein Generator wirklich macht, und danach ist sie zu.
    """
    project = new_project("centauri-carbon-2", "petg")
    backend = ScriptedMeshBackend(fallback=(CORPUS / "generated_figure.stl").read_bytes())
    generation = from_text(project, backend, "eine kleine Figur", seed=7)

    History(project.document).apply(
        "Auf das Bett", [OperationDraft(op="place_on_bed", inputs=(generation.object_id,))]
    )
    return project


def housing() -> Project:
    """Ein Gehäuseboden, wie er wirklich gebraucht wird — Bausteine statt Handarbeit.

    Vier Bausteine, die einzeln je eine halbe Stunde Konstruktion wären: die
    Mutternfalle, die Heat-Set-Buchse, das Schraubenloch und die
    Kabeldurchführung mit Zugentlastung. Alle Maße kommen aus der
    Normteiltabelle, das Spiel aus dem Materialprofil (§24.2, §28.3).
    """
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.parameters["breite"] = Parameter(name="breite", value=70.0, unit="mm", title="Breite")
    document.parameters["tiefe"] = Parameter(name="tiefe", value=50.0, unit="mm", title="Tiefe")
    document.parameters["wand"] = Parameter(name="wand", value=8.0, unit="mm", title="Wandstärke")

    history = History(document)
    history.apply(
        "Boden",
        [
            OperationDraft(
                op="create_box",
                params={
                    "width": "=@breite",
                    "depth": "=@tiefe",
                    "height": "=@wand",
                    "name": "Gehäuseboden",
                },
            )
        ],
    )
    history.apply(
        "Befestigung",
        [
            OperationDraft(
                op="insert_nut_trap",
                inputs=("obj_1",),
                params={"size": "M3", "x": -25.0, "y": -15.0, "z": 4.0, "slide": 12.0},
            ),
            OperationDraft(
                op="insert_heatset_m4",
                inputs=("obj_1",),
                params={"size": "M3", "x": 25.0, "y": -15.0, "z": "=@wand"},
            ),
            OperationDraft(
                op="insert_screw_hole",
                inputs=("obj_1",),
                params={"size": "M3", "depth": 10.0, "x": 25.0, "y": 15.0, "z": "=@wand"},
            ),
        ],
    )
    history.apply(
        "Kabel",
        [
            OperationDraft(
                op="insert_cable_gland",
                inputs=("obj_1",),
                params={"size": "cable-5", "wall": "=@wand", "x": -25.0, "y": 15.0, "z": 4.0},
            )
        ],
    )
    # Zwei Minuten drucken statt zwei Stunden: der Ausschnitt um die
    # Mutternfalle trägt die echte Geometrie mit der echten Toleranz (§28.3).
    # Erst duplizieren, dann ausschneiden — sonst wäre das Gehäuse selbst weg,
    # denn das Prüfstück ist ein Ausschnitt und keine Kopie.
    history.apply(
        "Kopie zum Prüfen",
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 2})],
    )
    history.apply(
        "Prüfstück",
        [
            OperationDraft(
                op="test_piece",
                # Auf die Kopie, nicht auf das Original: duplicate_object
                # verbraucht obj_1 und legt obj_2 (Original) und obj_3 (Kopie) an.
                inputs=("obj_3",),
                params={"size": 24.0, "x": -25.0, "y": -15.0, "z": 4.0},
            )
        ],
    )
    return project


def two_colour_sign() -> Project:
    """Zweifarbig auf beiden Wegen, weil es beide Drucker gibt (§20).

    Die Schrift im Materialslot wird beim 3MF-Export zum Farbwechsel — eine
    Datei, ein Druck. Der Schriftzug daneben ist ein eigener Körper, für den
    Drucker, an dem von Hand gewechselt wird, und für Lettern zum Aufkleben.
    """
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Schild",
        [
            OperationDraft(
                op="create_box",
                params={"width": 80.0, "depth": 30.0, "height": 3.0, "name": "Schild"},
            )
        ],
    )
    history.apply(
        "Beschriftung",
        [
            OperationDraft(
                op="label_text",
                inputs=("obj_1",),
                params={"text": "WERKSTATT", "size": 10.0, "depth": 0.8, "z": 3.0, "slot": 1},
            )
        ],
    )
    history.apply(
        "Aufhängung",
        [
            OperationDraft(
                op="insert_keyhole",
                inputs=("obj_1",),
                params={"size": "M4", "x": -30.0, "y": 0.0, "z": 0.0, "axis": "z"},
            )
        ],
    )
    # Der zweite Weg zur Zweifarbigkeit: Buchstaben als eigener Körper, für den
    # Drucker mit einem Werkzeug und für Lettern zum Aufkleben.
    history.apply(
        "Lettern",
        [
            OperationDraft(
                op="create_label",
                params={
                    "text": "1979",
                    "size": 12.0,
                    "depth": 2.0,
                    "y": -40.0,
                    "name": "Lettern",
                },
            )
        ],
    )
    history.apply(
        "Zweites Filament",
        [OperationDraft(op="assign_slot", inputs=("obj_2",), params={"slot": 1, "name": "Weiß"})],
    )
    return project


def calibration_plate() -> Project:
    """Die drei Testkörper, mit denen ein Drucker vermessen wird (§28.3).

    Einmal drucken und man weiß dreierlei: welches Spiel eine Passung braucht,
    ab welcher Wandstärke wirklich Material liegt und ab welchem Winkel dieser
    Drucker Stützen braucht — statt der Faustregel 45 Grad. Die Werte gehören
    danach ins Materialprofil, nicht ins Modell.
    """
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Prüfkörper",
        [
            OperationDraft(
                op="create_box",
                params={"width": 30.0, "depth": 20.0, "height": 2.0, "name": "Toleranz"},
            ),
            OperationDraft(
                op="create_box",
                params={"width": 30.0, "depth": 20.0, "height": 2.0, "name": "Wandstärke"},
            ),
            OperationDraft(
                op="create_box",
                params={"width": 30.0, "depth": 20.0, "height": 2.0, "name": "Überhang"},
            ),
        ],
    )
    history.apply(
        "Leitern",
        [
            OperationDraft(op="insert_fit_ladder", inputs=("obj_1",), params={"z": 2.0}),
            OperationDraft(op="insert_wall_ladder", inputs=("obj_2",), params={"z": 2.0}),
            OperationDraft(op="insert_overhang_fan", inputs=("obj_3",), params={"z": 2.0}),
        ],
    )
    # arrange_bed arbeitet auf der ganzen Szene (``takes_whole_scene``), und wer
    # sie aufruft, muss ihr die Objekte auch geben — sonst rechnet sie auf nichts.
    history.apply(
        "Anordnen",
        [
            OperationDraft(
                op="arrange_bed", inputs=("obj_1", "obj_2", "obj_3"), params={"spacing": 8.0}
            )
        ],
    )
    return project


def hollow_and_split() -> Project:
    """Ein Teil, das nicht auf die Platte passt, und Material, das keiner sieht.

    Erst teilen, dann aushöhlen — und nicht umgekehrt: eine ausgehöhlte Wand
    ist als Schnittfläche zu dünn für Passstifte, und ein Teil ohne Stifte
    steht und fällt mit dem Kleber. In jede Schnittfläche kommen deshalb zwei,
    deren Spiel aus dem kalibrierten Materialprofil stammt (§28.3).

    Danach spart das Aushöhlen an jeder Hälfte, was ohnehin niemand sieht, und
    die Entlüftungen lassen das Material heraus, das sonst eingeschlossen
    bliebe.
    """
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Klotz",
        [
            OperationDraft(
                op="create_box",
                params={"width": 120.0, "depth": 120.0, "height": 120.0, "name": "Klotz"},
            )
        ],
    )
    history.apply(
        "Teilen und verstiften",
        [
            OperationDraft(
                op="split_pinned",
                inputs=("obj_1",),
                params={"axis": "z", "position": 60.0, "pins": 2},
            )
        ],
    )
    # Der Schnitt verbraucht obj_1 und legt obj_2 und obj_3 an; ab hier laufen
    # beide Hälften getrennt weiter.
    history.apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object",
                inputs=("obj_2",),
                params={"wall": 3.0, "vents": 2, "vent_diameter": 5.0},
            ),
            OperationDraft(
                op="hollow_object",
                inputs=("obj_3",),
                params={"wall": 3.0, "vents": 2, "vent_diameter": 5.0},
            ),
        ],
    )
    history.apply(
        "Anordnen",
        [OperationDraft(op="arrange_bed", inputs=("obj_2", "obj_3"), params={"spacing": 6.0})],
    )
    return project


def main() -> int:
    load_operations()
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    target = directory()
    target.mkdir(parents=True, exist_ok=True)

    from app.core.examples import EXAMPLES

    builders = {
        "weg1-halterung-anpassen": way_one,
        "weg2-halter-konstruieren": way_two,
        "weg3-generiert-aufbereiten": way_three,
        "gehaeuse-mit-bausteinen": housing,
        "schild-zweifarbig": two_colour_sign,
        "drucker-kalibrieren": calibration_plate,
        "aushoehlen-und-teilen": hollow_and_split,
    }
    for example in EXAMPLES:
        project = builders[example.id]()
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        if not result.complete:
            print(f"-- {example.id}: Kette hält an")
            for finding in result.scene.report.findings:
                print(f"   {finding.code}: {finding.message}")
            return 1

        path = save(project, target / example.filename)
        objects = ", ".join(
            f"{entry.name} {entry.mesh.volume / 1000.0:.1f} cm3"
            for entry in result.scene.objects.values()
        )
        print(f"ok {path.name}: {objects}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
