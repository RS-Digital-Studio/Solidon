"""Baut die drei Beispielprojekte (Bauplan §37.2, §2.2).

Sie sind Dokumentation, Abnahmetest und Startbildschirm-Inhalt zugleich, also
werden sie gebaut, wie alles andere gebaut wird: als Operationen auf einem
Stapel. Ein Ordner mit von Hand exportierten Dateien driftete von der Anwendung
ab, sobald sich zum ersten Mal eine Operation ändert.

    python tools/make_examples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.backends.mesh import ScriptedMeshBackend
from app.core.bootstrap import load_operations
from app.core.examples import directory, render_preview
from app.core.generate import from_text
from app.core.knowledge import profiles
from app.core.lid_flow import apply_lid
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project, save
from app.core.types import Parameter, Source, SourceKind
from app.i18n import _

CORPUS = Path(__file__).resolve().parent.parent / "tests" / "data" / "meshes"


def with_source(project: Project, name: str, mesh: str, kind: SourceKind = "import") -> None:
    project.document.sources[name] = Source(id=name, kind=kind, path=f"sources/{mesh}", sha256="")
    project.sources[name] = (CORPUS / mesh).read_bytes()


def way_one() -> Project:
    """Ein fremdes Modell anpassen: einlesen, reparieren, aufs Bett,
    bohren (§2.2).
    """
    project = new_project("centauri-carbon-2", "petg")
    with_source(project, "src_1", "plate_holes.stl")
    history = History(project.document)
    history.apply(
        _("Modell laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=("obj_1",), params={})])
    history.apply(_("Auf das Bett"), [OperationDraft(op="place_on_bed", inputs=("obj_1",))])
    history.apply(
        _("Bohrung setzen"),
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
    """Neu bauen: Parameter, ein Körper, Bausteine aus der Bibliothek (§2.2)."""
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.parameters["breite"] = Parameter(
        name="breite", value=60.0, unit="mm", title=_("Breite")
    )
    document.parameters["tiefe"] = Parameter(name="tiefe", value=40.0, unit="mm", title=_("Tiefe"))
    document.parameters["staerke"] = Parameter(
        name="staerke", value=6.0, unit="mm", title=_("Stärke")
    )

    history = History(document)
    history.apply(
        _("Grundkörper"),
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
        _("Schraubenlöcher"),
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
        _("Versteifung"),
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
        _("Auf das Bett"), [OperationDraft(op="place_on_bed", inputs=(generation.object_id,))]
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
    document.parameters["breite"] = Parameter(
        name="breite", value=70.0, unit="mm", title=_("Breite")
    )
    document.parameters["tiefe"] = Parameter(name="tiefe", value=50.0, unit="mm", title=_("Tiefe"))
    document.parameters["wand"] = Parameter(
        name="wand", value=8.0, unit="mm", title=_("Wandstärke")
    )

    history = History(document)
    history.apply(
        _("Boden"),
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
        _("Befestigung"),
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
        _("Kabel"),
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
        _("Kopie zum Prüfen"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 2})],
    )
    history.apply(
        _("Prüfstück"),
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
        _("Schild"),
        [
            OperationDraft(
                op="create_box",
                params={"width": 80.0, "depth": 30.0, "height": 3.0, "name": "Schild"},
            )
        ],
    )
    history.apply(
        _("Beschriftung"),
        [
            OperationDraft(
                op="label_text",
                inputs=("obj_1",),
                params={"text": "WERKSTATT", "size": 10.0, "depth": 0.8, "z": 3.0, "slot": 1},
            )
        ],
    )
    history.apply(
        _("Aufhängung"),
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
        _("Lettern"),
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
        _("Zweites Filament"),
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
        _("Prüfkörper"),
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
        _("Leitern"),
        [
            OperationDraft(op="insert_fit_ladder", inputs=("obj_1",), params={"z": 2.0}),
            OperationDraft(op="insert_wall_ladder", inputs=("obj_2",), params={"z": 2.0}),
            OperationDraft(op="insert_overhang_fan", inputs=("obj_3",), params={"z": 2.0}),
        ],
    )
    # arrange_bed arbeitet auf der ganzen Szene (``takes_whole_scene``), und wer
    # sie aufruft, muss ihr die Objekte auch geben — sonst rechnet sie auf nichts.
    history.apply(
        _("Anordnen"),
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
        _("Klotz"),
        [
            OperationDraft(
                op="create_box",
                params={"width": 120.0, "depth": 120.0, "height": 120.0, "name": "Klotz"},
            )
        ],
    )
    history.apply(
        _("Teilen und verstiften"),
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
        _("Aushöhlen"),
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
        _("Anordnen"),
        [OperationDraft(op="arrange_bed", inputs=("obj_2", "obj_3"), params={"spacing": 6.0})],
    )
    return project


def box_with_lid() -> Project:
    """Eine Dose mit Deckel — das Stück, an dem alles zusammenkommt.

    Die anderen Beispiele zeigen je einen Weg. Dieses zeigt, was daraus wird,
    wenn man sie hintereinander legt: benannte Maße, ein ausgehöhlter Körper
    mit offener Oberseite, Bausteine in der Wand, ein Deckel, der aus der
    Öffnung geschnitten und nicht nachgezeichnet ist (§14), eine Beschriftung
    darauf und beides nebeneinander auf dem Bett.

    Es ist zugleich das Bild, das auf dem Startbildschirm und im Handbuch
    steht. Ein Beispiel, das aussieht wie eine Platte mit fünf Löchern, zeigt
    ein Programm, das Löcher bohren kann.
    """
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.parameters["breite"] = Parameter(
        name="breite", value=80.0, unit="mm", title=_("Breite")
    )
    document.parameters["tiefe"] = Parameter(name="tiefe", value=55.0, unit="mm", title=_("Tiefe"))
    document.parameters["hoehe"] = Parameter(name="hoehe", value=40.0, unit="mm", title=_("Höhe"))
    document.parameters["wand"] = Parameter(
        name="wand", value=2.4, unit="mm", title=_("Wandstärke")
    )

    history = History(document)
    history.apply(
        _("Körper"),
        [
            OperationDraft(
                op="create_box",
                params={
                    "width": "=@breite",
                    "depth": "=@tiefe",
                    "height": "=@hoehe",
                    "name": "Dose",
                },
            )
        ],
    )
    # Oben offen: erst dadurch hat der Deckel eine Öffnung, an der er sich
    # abnehmen kann. Eine geschlossene Aushöhlung wäre ein Hohlraum, kein Fach.
    history.apply(
        _("Aushöhlen"),
        [
            OperationDraft(
                op="hollow_object",
                inputs=("obj_1",),
                params={"wall": "=@wand", "open_top": True},
            )
        ],
    )
    history.apply(
        _("Kabel und Befestigung"),
        [
            OperationDraft(
                op="insert_cable_gland",
                inputs=("obj_1",),
                params={"size": "cable-5", "wall": "=@wand", "x": -40.0, "y": 0.0, "z": 26.0},
            ),
            # Auf den Boden, nicht auf die Oberkante. Sie stand auf
            # ``z = "=@hoehe"``, und dort war einmal ein Deckel — seit die
            # Dose oben offen ist, liegt über dem Innenraum nichts mehr, in
            # das sich eine Buchse setzen ließe. Der Prüfbericht sagte es bei
            # jedem Öffnen des Beispiels („Der Schnitt hat nichts abgetragen"),
            # und ein Beispiel ist Dokumentation: was darin warnt, ist eine
            # Aussage über die Anwendung.
            OperationDraft(
                op="insert_heatset_m4",
                inputs=("obj_1",),
                params={"size": "M3", "x": 30.0, "y": 20.0, "z": "=@wand"},
            ),
        ],
    )

    # Die Beschriftung kommt **vor** den Deckel und sitzt auf der Dose.
    #
    # Nach dem Deckel ginge sie schief, und zwar sichtbar: eine Passung zeigt
    # auf Merkmale (§14), eine Boolesche Operation danach baut den Körper neu,
    # und der Kragen heißt dann nicht mehr ``lid_collar``. Beim Öffnen fragt
    # die Verwaisungsprüfung, welches Merkmal gemeint war (§21.3) — richtig
    # gefragt, aber nichts, was in einem Beispiel stehen sollte.
    history.apply(
        _("Beschriftung"),
        [
            OperationDraft(
                op="label_text",
                inputs=("obj_1",),
                params={"text": "SOLIDON3D", "size": 6.0, "depth": 0.6, "slot": 1},
            )
        ],
    )

    # Der Deckel geht über seinen Ablauf und nicht über die nackte Operation:
    # nur so entsteht das Passungspaar zwischen Öffnung und Kragen (§14), und
    # daran hängen beim Slicen die genaue Außenwand und das gebremste Tempo.
    applied = apply_lid(
        document,
        "obj_1",
        {"thickness": 3.0, "collar": 5.0},
        profiles.make_profile("centauri-carbon-2", "petg"),
    )
    # ``create_lid`` verbraucht seine Eingabe und legt zwei Ausgänge an: die
    # Dose kommt als erste zurück, der Deckel als zweite. Ab hier heißt die
    # Dose deshalb nicht mehr ``obj_1``.
    box, lid = applied.object_ids[0], applied.object_ids[1]

    # Anordnen ist eine Transformation und meldet seine Bewegung
    # (``OpResult.transform``) — die Merkmale überstehen das, und damit auch
    # die Passung.
    history.apply(
        _("Anordnen"),
        [OperationDraft(op="arrange_bed", inputs=(box, lid), params={"spacing": 8.0})],
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
        "dose-mit-deckel": box_with_lid,
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

        # Das Vorschaubild entsteht aus demselben Lauf, der das Beispiel baut.
        # Ein Bild, das jemand später von Hand nachzieht, zeigt irgendwann ein
        # anderes Teil als die Datei daneben — dieselbe Begründung, aus der
        # auch die Bausteinvorschauen gerendert und nicht gepflegt werden
        # (§24.3).
        preview = render_preview(entry.mesh for entry in result.scene.objects.values())
        picture = target / example.preview_name
        picture.write_text(preview, encoding="utf-8")

        objects = ", ".join(
            f"{entry.name} {entry.mesh.volume / 1000.0:.1f} cm3"
            for entry in result.scene.objects.values()
        )
        print(f"ok {path.name}: {objects}  [{len(preview) / 1024:.0f} kB Vorschau]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
