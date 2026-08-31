"""Baut die mitgelieferten Beispielprojekte (Bauplan §37.2, §2.2).

Sie sind Dokumentation, Abnahmetest und Startbildschirm-Inhalt zugleich, also
werden sie gebaut, wie alles andere gebaut wird: als Operationen auf einem
Stapel. Ein Ordner mit von Hand exportierten Dateien driftete von der Anwendung
ab, sobald sich zum ersten Mal eine Operation ändert.

    python tools/make_examples.py
"""

from __future__ import annotations

import dataclasses
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
from app.i18n import TranslatableText, _

CORPUS = Path(__file__).resolve().parent.parent / "tests" / "data" / "meshes"


def with_source(project: Project, name: str, mesh: str, kind: SourceKind = "import") -> None:
    project.document.sources[name] = Source(id=name, kind=kind, path=f"sources/{mesh}", sha256="")
    project.sources[name] = (CORPUS / mesh).read_bytes()


def way_one() -> Project:
    """Ein fremdes Modell anpassen: einlesen, reparieren, aufs Bett,
    bohren (§2.2).
    """
    project = new_project()
    with_source(project, "src_1", "plate_holes.stl")
    history = History(project.document)
    # **Mit Namen.** Ohne ihn nimmt die Op den Dateinamen, und der ist hier der
    # eines Testkorpus-Netzes: Das erste Objekt, das ein Demonutzer je im
    # Objektbaum sieht, hieß „plate_holes". Jedes andere Beispiel benennt seine
    # Körper ("Halter", "Figur", "Gehäuseboden", "Schild") — dieses eine,
    # das zuerst geöffnet wird, tat es nicht.
    history.apply(
        _("Modell laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm", "name": "Halterung"})],
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
    project = new_project()
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
    project = new_project()
    backend = ScriptedMeshBackend(fallback=(CORPUS / "generated_figure.stl").read_bytes())
    # **Mit `name`, sonst wird der Prompt zum Objektnamen.** `from_text` nimmt
    # ohne ihn den Prompt (`into_project`, gekürzt auf fünf Wörter), und der ist
    # deutsch: Ein englischer Kunde las hinter jedem der neun Befunde dieses
    # Beispiels „eine kleine Figur". Gemeldet von Robert am 23.08.2026 als
    # „zwei Punkte immer in deutsch".
    #
    # „Figur" steht in :data:`EXAMPLE_NAMES`, also macht `mark_translatable`
    # daraus einen übersetzbaren Namen. Der Prompt selbst bleibt, wie er ist —
    # er gehört zur Provenienz (`SourceOrigin.prompt`) und beschreibt, was
    # jemand eingegeben hat, nicht was das Ergebnis heißt.
    generation = from_text(project, backend, "eine kleine Figur", seed=7, name="Figur")

    History(project.document).apply(
        _("Auf das Bett"), [OperationDraft(op="place_on_bed", inputs=(generation.object_id,))]
    )
    return project


def way_four() -> Project:
    """Eine Figur formen: verschmelzen, vernetzen, ausformen (§2.2, Weg 4).

    Der Aufbau ist der, den P16.11 dem Käfigeditor entgegenhält — Grundkörper
    weich verschmolzen. Die Züge legt dieses Skript nicht: Ein Beispiel, das
    mit viertausend gespeicherten Pinselzügen ankommt, zeigt ein Ergebnis und
    keinen Weg. Es endet dort, wo der Nutzer den Pinsel nimmt, und die Tour
    sagt ihm das.
    """
    project = new_project()
    history = History(project.document)

    history.apply(
        _("Rumpf"),
        [
            OperationDraft(
                op="create_box",
                params={"width": 24.0, "depth": 14.0, "height": 40.0, "name": "Figur"},
            )
        ],
    )
    history.apply(
        _("Kopf"),
        [OperationDraft(op="create_sphere", params={"diameter": 18.0, "name": "Kopf"})],
    )
    history.apply(
        _("Kopf setzen"),
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_2",),
                params={"dx": 0.0, "dy": 0.0, "dz": 26.0},
            )
        ],
    )
    history.apply(
        _("Weich verschmelzen"),
        [
            OperationDraft(
                op="blend_union",
                inputs=("obj_1", "obj_2"),
                params={"radius": 4.0, "grid": 1.2},
            )
        ],
    )
    history.apply(
        _("Dreiecke angleichen"),
        [
            OperationDraft(
                op="remesh_uniform",
                # Zwei Körper hinein, einer heraus — aber der eine trägt die
                # Kennung des ersten Eingangs weiter, statt eine frische zu
                # bekommen. Hier stand ``obj_3``, und die gab es nie: Weder
                # das Verschieben noch das Verschmelzen hebt die Wasserlinie,
                # beide behalten die Kennung, die sie hereinbekommen haben.
                inputs=("obj_1",),
                params={"edge": 1.5, "deviation": 0.0},
            )
        ],
    )
    # **Das Beispiel endete 0,29 mm unter dem Druckbett** (gemessen am
    # 23.08.2026): Das weiche Verschmelzen mit Radius 4 rundet auch nach unten
    # ab und zieht die Unterkante unter Z = 0. Der Prüfbericht sagte es als
    # Hinweis, und beim Export wäre daraus eine Warnung geworden — ein
    # Beispiel für einen der vier Hauptwege (§2.2) darf nicht in etwas enden,
    # das der Slicer erst zurechtrücken muss. Bauplan §2.2 nennt „stellen"
    # ohnehin als Teil dieses Weges.
    history.apply(
        _("Auf das Bett setzen"),
        [OperationDraft(op="place_on_bed", inputs=("obj_1",), params={})],
    )
    return project


def housing() -> Project:
    """Ein Gehäuseboden, wie er wirklich gebraucht wird — Bausteine statt Handarbeit.

    Vier Bausteine, die einzeln je eine halbe Stunde Konstruktion wären: die
    Mutternfalle, die Heat-Set-Buchse, das Schraubenloch und die
    Kabeldurchführung mit Zugentlastung. Alle Maße kommen aus der
    Normteiltabelle, das Spiel aus dem Materialprofil (§24.2, §28.3).
    """
    project = new_project()
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
                # Auf die Kopie, nicht auf das Original: ``duplicate_object``
                # lässt den Eingang seine Kennung behalten und hängt die Kopie
                # als ``obj_2`` daneben. (Bis zum 27.08.2026 vergab es auch für
                # das Original eine frische Kennung — dann hieß die Kopie
                # ``obj_3``, und das Original war weg.)
                inputs=("obj_2",),
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
    project = new_project()
    history = History(project.document)
    history.apply(
        _("Schild"),
        [
            OperationDraft(
                op="create_box",
                params={"width": 80.0, "depth": 45.0, "height": 3.0, "name": "Schild"},
            )
        ],
    )
    history.apply(
        _("Beschriftung"),
        [
            OperationDraft(
                op="label_text",
                inputs=("obj_1",),
                params={
                    "text": "Solidon3D",
                    "size": 10.0,
                    "depth": 0.8,
                    # Nach oben gerückt: darunter stehen die Lettern.
                    "x": 5.0,
                    "y": 10.0,
                    "z": 3.0,
                    "slot": 1,
                },
            )
        ],
    )
    history.apply(
        _("Aufhängung"),
        [
            OperationDraft(
                op="insert_keyhole",
                inputs=("obj_1",),
                # **Von hinten, mit dem kleinsten möglichen Durchbruch** (Robert,
                # 31.08.2026: „aufhängung nach hinten, von vorne nicht sichtbar").
                #
                # Ganz unsichtbar geht nicht, und das ist die Bauart und kein
                # Mangel: Der Schaftschlitz muss durch die Platte, sonst greift
                # die Schraube nicht — der Baustein sagt es selbst („der Schlitz,
                # in den der Schaft gleitet, ganz hindurch"). Was sich vermeiden
                # lässt, ist die **Kopftasche** auf der Sichtseite.
                #
                # Gemessen an der Platte 80 auf 45: Von der Oberseite fehlen mit
                # ``head_room = 1,5`` noch 23,1 mm² statt 26,5 — der Rest ist der
                # Schlitz selbst. Die Dicke ändert daran nichts, geprüft von 3
                # bis 6 mm.
                #
                # ``axis="y"`` und nicht ``"z"``: Mit Z fehlt der Oberseite gar
                # nichts, aber dann liegt das Schlüsselloch in der Plattenebene
                # und die Schraube kann nicht greifen — die Operation meldet das
                # seit dem 30.08.2026 als ``parts.up_points_nowhere``. Ein Schild,
                # das nicht hängt, ist unsichtbar kaputt statt sichtbar heil.
                params={
                    "size": "M4",
                    # **An die Rückseite geklickt, nicht auf Koordinaten
                    # gesetzt.** Die Operation sagt diesen Weg selbst an, wenn
                    # man es anders versucht: „Klicken Sie die Fläche an, an die
                    # er kommt: Sie gibt ihm die Richtung, und er richtet sich
                    # selbst auf." Frei platziert stand die Warnung
                    # ``parts.up_points_nowhere`` im Prüfbericht des Beispiels
                    # — auf dem Belegbild der Verkaufsseite die einzige Warnung
                    # weit und breit.
                    #
                    # ``face_1`` ist die Unterseite: von den sechs Flächen der
                    # Platte die mit der Normalen (0, 0, -1). Damit sitzt die
                    # Aufhängung hinten, und die Sichtseite bleibt zu — Roberts
                    # Vorgabe vom 31.08.2026, „aufhängung nach hinten, von vorne
                    # nicht sichtbar".
                    "at_feature": "face_1",
                    "x": -30.0,
                    "y": 0.0,
                    # **Beides kleiner als die Platte dick ist.** Die Vorgabe
                    # von ``depth`` ist 4,0 und damit größer als die 3,0 hier —
                    # der Schlitz kam auf der Sichtseite wieder heraus, obwohl
                    # der Baustein an der Rückfläche sitzt. Gemessen bleibt bei
                    # 2,0 ein Boden von 1,0 mm stehen: bei 0,2 mm Schichthöhe
                    # fünf Lagen, genug zum Tragen und dicht von vorne.
                    "depth": 2.0,
                    "head_room": 1.5,
                },
            )
        ],
    )
    # Der zweite Weg zur Zweifarbigkeit: Buchstaben als eigener Körper — beim
    # Drucker ein Werkzeugwechsel, von Hand ein Satz Lettern zum Aufkleben.
    #
    # **Sie liegen auf dem Schild, nicht daneben** (Robert, 31.08.2026: „dass
    # bei dem solidon3d 2026 bild was rausgeschnitten ist ist auch nicht gut").
    # Vorher stand hier ``y = -40`` — vierzig Millimeter unter einem Schild,
    # das dreißig tief ist, also weit außerhalb. Gemeint war „ein eigener
    # Körper", zu sehen war ein Teil mit einem Loch und Abfall daneben. Auf
    # dem Belegbild der Verkaufsseite las sich das als Fehler im Bild.
    #
    # Die Maße sind gemessen, nicht geschätzt: „Solidon3D" bei Größe 10 ist
    # 49,6 mal 7,7 mm, „2026" bei Größe 8 nur 19,3 mal 6,1. Zwei Zeilen passen
    # auf das Schild, sofern sie rechts vom Schlüsselloch bleiben — das sitzt
    # bei x = -30 und reicht bis etwa -25.
    #
    # **Und das Schild ist dafür von 30 auf 45 mm gewachsen.** Bei 30 blieben
    # zwischen den beiden Zeilen sechs Millimeter, und in der Schrägansicht des
    # Belegbilds schoben sie sich perspektivisch übereinander — gemessen am
    # Bild, nicht an den Zahlen: Die Lage stimmte, das Bild sah unruhig aus.
    history.apply(
        _("Lettern"),
        [
            OperationDraft(
                op="create_label",
                params={
                    "text": "2026",
                    "size": 8.0,
                    "depth": 2.0,
                    "x": 5.0,
                    "y": -12.0,
                    "z": 3.0,
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


def sketched_plate() -> Project:
    """Der Skizzenweg (§30.1): Umriss aus Bedingungen, nicht aus Punkten.

    **Der einzige Bereich, für den es kein Beispiel gab.** Neun Beispiele
    zeigten am 31.08.2026 keine einzige ``sketch_*``-Operation — ein ganzer
    Kern mit eigenem Löser, in den ersten fünf Minuten unsichtbar.

    Gezeigt wird das, was die Skizze von einer Punktliste unterscheidet: Der
    Kreis trägt seinen Durchmesser als **Bedingung**, und die Bedingung rechnet
    mit dem Projektparameter. Wer ``durchmesser`` auf 80 stellt, bekommt einen
    Umriss, der wirklich rund ist — der Löser gibt eine exakte Kurve in den
    Kern, keine Sehnenkette.
    """
    project = new_project()
    document = project.document
    document.parameters["durchmesser"] = Parameter(
        name="durchmesser", value=60.0, unit="mm", title=_("Durchmesser")
    )
    document.parameters["staerke"] = Parameter(
        name="staerke", value=8.0, unit="mm", title=_("Stärke")
    )

    history = History(document)
    history.apply(
        _("Runde Platte"),
        [
            OperationDraft(
                op="sketch_extrude",
                params={
                    "shape": "circle",
                    # Beim Kreis **ist** die Länge der Durchmesser — die Skizze
                    # legt ihn als Abstandsbedingung zwischen Mitte und Rand ab.
                    "length": "=@durchmesser",
                    "height": "=@staerke",
                    "name": "Platte",
                },
            )
        ],
    )
    history.apply(
        _("Tasche"),
        [
            OperationDraft(
                op="sketch_pocket",
                inputs=("obj_1",),
                params={
                    "shape": "rectangle",
                    "length": "=@durchmesser/2",
                    "width": "=@durchmesser/3",
                    "depth": "=@staerke/2",
                },
            )
        ],
    )
    return project


def calibration_plate() -> Project:
    """Die drei Testkörper, mit denen ein Drucker vermessen wird (§28.3).

    Einmal drucken und man weiß dreierlei: welches Spiel eine Passung braucht,
    ab welcher Wandstärke wirklich Material liegt und ab welchem Winkel dieser
    Drucker Stützen braucht — statt der Faustregel 45 Grad. Die Werte gehören
    danach ins Materialprofil, nicht ins Modell.
    """
    project = new_project()
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
    project = new_project()
    history = History(project.document)
    history.apply(
        _("Klotz"),
        [
            OperationDraft(
                op="create_box",
                # Achtzig Millimeter zeigen Hohlraum und Passstifte deutlich,
                # passen aber auch zu zweit auf ein übliches 180-mm-Bett. Das
                # frühere 120-mm-Beispiel begrüßte kleinere Drucker mit einem
                # Überstand statt mit einem druckfertigen Projekt.
                params={"width": 80.0, "depth": 80.0, "height": 80.0, "name": "Klotz"},
            )
        ],
    )
    history.apply(
        _("Teilen und verstiften"),
        [
            OperationDraft(
                op="split_pinned",
                inputs=("obj_1",),
                params={"axis": "z", "position": 40.0, "pins": 2},
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
    project = new_project()
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
        profiles.make_profile(),
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


#: Die Objektnamen, die in den mitgelieferten Beispielen gesetzt werden.
#:
#: **Warum eine Liste und nicht „jeder gesetzte Name".** Ein Beispiel ist eine
#: Datei wie jede andere, und ein Name darin könnte auch von einem Nutzer
#: stammen — dann wäre er wörtlich gemeint (§4.1). Diese dreizehn kommen aus
#: dem Code hier daneben; sie sind Message-IDs, weil sie es sind, und nicht,
#: weil sie an einer bestimmten Stelle stehen.
#:
#: Wer einen Namen hinzufügt, trägt ihn hier ein **und** in die fünf Kataloge.
#: `tests/test_translations.py` fängt das Zweite; das Erste fängt niemand, und
#: darum steht es hier als Satz.
EXAMPLE_NAMES: frozenset[TranslatableText] = frozenset(
    {
        _("Dose"),
        _("Figur"),
        _("Gehäuseboden"),
        _("Halter"),
        _("Halterung"),
        _("Klotz"),
        _("Kopf"),
        _("Lettern"),
        _("Schild"),
        _("Toleranz"),
        _("Wandstärke"),
        _("Weiß"),
        _("Überhang"),
    }
)
"""Die dreizehn Namen als Übersetzungsmarker, nicht als Zeichenketten.

**Damit findet der Einsammler sie.** ``app/i18n/extract.py`` sucht nach
``_()``-Aufrufen und liest diese Datei ausdrücklich mit (``EXTRA_SOURCES``);
stünden hier schlichte Zeichenketten, wären die Katalogeinträge daneben
„no longer used" und der Sprachtest rot — in beide Richtungen, denn er prüft
auch, ob ein Eintrag noch gebraucht wird.

**Und die Mengenprüfung funktioniert trotzdem mit einer Zeichenkette**, weil
``TranslatableText`` seit dem 22.08.2026 über seine Message-ID vergleicht und
hasht. ``"Dose" in EXAMPLE_NAMES`` ist wahr, obwohl in der Menge kein ``str``
liegt. Ohne diese Eigenschaft bräuchte es hier zwei Listen, die auseinander
laufen können."""


def fixed_seeds(project: Project) -> None:
    """Gibt jeder Operation mit Startwert einen festen (§11.3).

    **Warum die Beispiele das brauchen und ein Nutzerprojekt nicht.** Wo der
    Aufrufer keinen Startwert mitbringt, zieht ``History`` einen — mit
    ``secrets.randbelow``, und das ist für eine Nutzersitzung genau richtig:
    Entscheidend ist, dass er *aufgehoben* wird, nicht, wer ihn sich ausgedacht
    hat. Für eine Datei, die im Repository liegt, kehrt sich das um: Zwei Läufe
    dieses Werkzeugs erzeugten neun Dateien, die sich in genau einer Zahl
    unterschieden, und `git status` meldete sie fortan als geändert.

    **Das war die zweite Hälfte derselben Sache.** Die erste waren die
    ZIP-Zeitstempel (:data:`app.core.scene.project.CONTAINER_TIMESTAMP`); als
    die fest standen, blieb dieser Unterschied übrig und sah aus wie derselbe
    Fehler. Eine Erklärung, die stimmt, ist nicht immer die ganze.

    Der Wert leitet sich aus der Position im Stapel ab, damit zwei Operationen
    desselben Beispiels nicht denselben bekommen — ein gemeinsamer Startwert
    ließe zwei zufällige Prozeduren im Gleichschritt laufen, und das ist eine
    Eigenschaft, die niemand wollte und die niemand sähe.
    """
    for index, operation in enumerate(project.document.ops):
        if operation.seed is None:
            continue
        project.document.ops[index] = dataclasses.replace(operation, seed=1000 + index)


def mark_translatable(project: Project) -> None:
    """Vermerkt an jeder Operation, welche Parameter Message-IDs tragen (§4.1).

    **Gesetzt wird nach dem Bauen und nicht beim Bauen**, und das hat einen
    Grund, der über die Bequemlichkeit hinausgeht: Die Beispiele werden über
    ``OperationDraft`` gebaut, und der Draft ist die Beschreibung einer
    *Handlung* — er weiß nicht, ob ein Name aus dem Code oder aus einer
    Tastatur kommt. Das weiß nur diese Datei, weil sie die Namen selbst
    hinschreibt.

    Damit bleibt die Zusage aus §4.1 an der einen Stelle, an der sie gilt: Ein
    Name aus einem mitgelieferten Beispiel ist übersetzbar, jeder andere ist
    wörtlich — auch wenn er zufällig gleich lautet.
    """
    for index, operation in enumerate(project.document.ops):
        name = operation.params.get("name")
        if isinstance(name, str) and name in EXAMPLE_NAMES:
            project.document.ops[index] = dataclasses.replace(operation, translatable=("name",))


def main() -> int:
    load_operations()
    # Die Vorgaben und **kein** benannter Drucker: Ein Beispiel soll den Weg
    # zeigen, nicht die Werkstatt dessen, der es gebaut hat. Trug es einen
    # Drucker, überschrieb es beim Öffnen die Wahl, die der Kunde im ersten
    # Dialog getroffen hatte — samt Material, Gewicht, Druckzeit und den
    # Toleranzen, mit denen die Bohrung im nächsten Schritt gerechnet wird.
    #
    # Für die Auswertung hier ist das Profil ohnehin gleichgültig: Gemessen
    # über alle neun Beispiele kommt mit ``centauri-carbon-2``/``petg``
    # dieselbe Geometrie heraus wie mit den Vorgaben. Die Datei speichert
    # Operationen und Werte, nicht das Ergebnis — gerechnet wird beim Öffnen,
    # und zwar mit dem Profil des Kunden.
    profile = profiles.make_profile()
    target = directory()
    target.mkdir(parents=True, exist_ok=True)

    from app.core.examples import EXAMPLES

    builders = {
        "weg1-halterung-anpassen": way_one,
        "weg2-halter-konstruieren": way_two,
        "weg3-generiert-aufbereiten": way_three,
        "weg4-figur-formen": way_four,
        "gehaeuse-mit-bausteinen": housing,
        "schild-zweifarbig": two_colour_sign,
        "skizze-mit-massen": sketched_plate,
        "drucker-kalibrieren": calibration_plate,
        "aushoehlen-und-teilen": hollow_and_split,
        "dose-mit-deckel": box_with_lid,
    }
    for example in EXAMPLES:
        project = builders[example.id]()
        fixed_seeds(project)
        mark_translatable(project)
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
        # ``write_bytes`` und nicht ``write_text``: Letzteres schreibt auf
        # Windows CRLF, und `.gitattributes` verlangt LF (`* text=auto
        # eol=lf`). Die neun Vorschaubilder standen dadurch dauerhaft als
        # geändert im Baum — in einer Sitzung, die vier Arbeitsstände teilt,
        # sieht das aus wie fremde Arbeit, und man lässt es in Ruhe.
        picture.write_bytes(preview.encode("utf-8"))

        objects = ", ".join(
            f"{entry.name} {entry.mesh.volume / 1000.0:.1f} cm3"
            for entry in result.scene.objects.values()
        )
        print(f"ok {path.name}: {objects}  [{len(preview) / 1024:.0f} kB Vorschau]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
