"""Das Schaustück für die Website — ein Teil, das zeigt, was die App kann.

    .venv\\Scripts\\python.exe tools/make_showpiece.py [ziel.p3d]

**Warum nicht eines der Beispielprojekte.** Die haben ihren Zweck und
erfüllen ihn: Sie führen durch die vier Wege und zeigen je eine Sache ohne
Ablenkung. Der Gehäuseboden aus ``make_examples.housing`` etwa ist eine
flache Platte mit vier Bausteinen — als Lehrstück richtig, weil nichts vom
Wesentlichen ablenkt.

Auf einer Website ist genau das falsch. Wer dort eine flache Platte sieht,
denkt „das kann jeder" und liest nicht weiter. Ein Schaustück muss in einem
einzigen Bild beantworten, warum man dieses Programm haben will — und dafür
darf es alles auf einmal zeigen.

**Was es zeigt, und warum jedes Stück darin steht:**

| Schritt | Was man sieht |
|---|---|
| B-Rep-Quader statt Netz | Voraussetzung für alles Weitere, unsichtbar aber tragend |
| Kanten verrundet | Der Unterschied zwischen „gedruckt" und „hergestellt" |
| Ausgehöhlt | Die Wandstärke ist an der offenen Seite ablesbar |
| Heat-Set-Buchsen | Ein Normteil, das aus der Tabelle kommt, nicht aus der Hand |
| Kabeldurchführung | Ein Bauteil, das man sonst eine halbe Stunde konstruiert |
| Versteifungsrippen | Dass jemand an Steifigkeit gedacht hat |
| Standfüße, Rastnasen | Dass das Teil in die Hand genommen werden soll |
| Deckel danebengelegt | **Der wichtigste Schritt** — aufgesetzt verdeckt er alles |
| Zwei Materialfarben | Aus einer grauen Kiste wird ein Produkt |
| Erhabener Schriftzug | Dass Text Geometrie ist und kein Aufkleber |

**Der Deckel liegt daneben, und das ist keine Kosmetik.** Der erste Aufbau
setzte ihn auf, und das Bild zeigte eine geschlossene Kiste mit runden
Kanten: Schraubdome, Rippen, Wandstärke und Aushöhlung — die ganze Arbeit —
waren unsichtbar. Ein Schaustück, das seine eigene Arbeit versteckt, zeigt
eine Kiste.

**Drei Fallen beim Bauen, alle drei einmal zugeschnappt:**

* ``fillet_edges`` braucht einen **B-Rep**-Körper. Mit ``create_box`` hält die
  Kette an, und die Fehlermeldung sagt es genau: „Aktiviere bei einer
  Grundform die Option „Flächen und Kanten später bearbeiten“."
* Die Feldnamen stehen im **Register**, nicht in der Vermutung. Der erste
  Anlauf verlor vier von neun Schritten an geratenen Namen (``thickness``
  statt ``wall``) und Werten außerhalb ihrer Grenzen (``vents=12`` bei einem
  Maximum von sechs). Gelesen werden sie über ``dataclasses.fields`` am
  Parametertyp der Operation.
* **Eine Höhe gilt nur so lange, wie das Teil dort steht.** Der Schriftzug
  stand zuerst vor dem Umlegen im Drehbuch und landete an der *Unterkante*
  des Deckels: Der lag zu dem Zeitpunkt bei z 41 bis 47, danach bei 0 bis
  6,4. Er ist deshalb der letzte Schritt.
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.knowledge import profiles  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import (  # noqa: E402
    Project,
    ProjectSources,
    new_project,
    save,
)
from app.core.types import Parameter, Source  # noqa: E402

#: Die Maße des Gehäuses, als benannte Projektparameter.
#:
#: Deutsch, und das ist kein Versehen: Parameternamen gehören dem Nutzer und
#: erscheinen in seiner Oberfläche. Dieselbe Entscheidung wie in
#: ``make_examples.housing``.
SIZES = (
    ("breite", 120.0, "Breite"),
    ("tiefe", 80.0, "Tiefe"),
    ("hoehe", 45.0, "Höhe"),
    ("wand", 2.4, "Wandstärke"),
)

#: Wie weit der Deckel neben dem Gehäuse liegt, in Millimetern.
#:
#: Nach **x** und nicht nach y: Ein Bild ist breiter als hoch, und bei 105 mm
#: nach hinten stand der Deckel zur Hälfte außerhalb der Ansicht.
LID_OFFSET = 135.0


def steps() -> list[tuple[str, list[OperationDraft]]]:
    """Die zwölf Schritte, in der Reihenfolge, in der sie aufeinander aufbauen."""
    return [
        (
            "Gehäusekörper",
            [
                OperationDraft(
                    op="create_brep_box",
                    params={
                        "width": "=@breite",
                        "depth": "=@tiefe",
                        "height": "=@hoehe",
                        "name": "Gehäuse",
                    },
                )
            ],
        ),
        (
            "Kanten verrunden",
            [OperationDraft(op="fillet_edges", inputs=("obj_1",), params={"radius": 4.0})],
        ),
        (
            "Aushöhlen",
            [
                OperationDraft(
                    op="hollow_object",
                    inputs=("obj_1",),
                    # ``open_top`` und ``vents`` schließen einander aus: Lüftung
                    # gibt es nur im geschlossenen Körper. Hier kommt der Deckel
                    # oben drauf, also bleibt es offen.
                    params={"wall": "=@wand", "open_top": True, "vents": 0},
                )
            ],
        ),
        (
            "Schraubdome",
            [
                OperationDraft(
                    op="insert_heatset_m4",
                    inputs=("obj_1",),
                    params={"size": "M3", "x": x, "y": y, "z": "=@wand"},
                )
                # **Zehn Millimeter vom Rand, gerechnet statt eingetragen.**
                # Auf festem ±50 fielen die vier Buchsen unterhalb von 110 mm
                # Breite aus der Wand: fünf lose Stücke bei 70 bis 90, drei
                # bei 100 — wasserdicht, plausibles Volumen, kein Befund.
                for x, y in (
                    ("=-(@breite / 2 - 10)", "=-(@tiefe / 2 - 10)"),
                    ("=@breite / 2 - 10", "=-(@tiefe / 2 - 10)"),
                    ("=-(@breite / 2 - 10)", "=@tiefe / 2 - 10"),
                    ("=@breite / 2 - 10", "=@tiefe / 2 - 10"),
                )
            ],
        ),
        (
            "Kabeldurchführung",
            [
                OperationDraft(
                    op="insert_cable_gland",
                    inputs=("obj_1",),
                    params={"diameter": 6.0, "x": 0.0, "y": -40.0, "z": 22.0},
                )
            ],
        ),
        (
            "Versteifungsrippen",
            [
                OperationDraft(
                    op="insert_rib",
                    inputs=("obj_1",),
                    params={
                        "length": "=@tiefe - 20",
                        "height": 14.0,
                        "thickness": 2.4,
                        "fillet": 2.0,
                        "x": x,
                        "y": 0.0,
                        "z": "=@wand",
                        "axis": "y",
                    },
                )
                for x in ("=-@breite / 4", "=@breite / 4")
            ],
        ),
        (
            "Standfüße",
            [
                OperationDraft(
                    op="insert_foot", inputs=("obj_1",), params={"x": x, "y": y, "z": 0.0}
                )
                # Acht Millimeter vom Rand — dieselbe Rechnung wie bei den
                # Schraubdomen, nur weiter außen.
                for x, y in (
                    ("=-(@breite / 2 - 8)", "=-(@tiefe / 2 - 8)"),
                    ("=@breite / 2 - 8", "=-(@tiefe / 2 - 8)"),
                    ("=-(@breite / 2 - 8)", "=@tiefe / 2 - 8"),
                    ("=@breite / 2 - 8", "=@tiefe / 2 - 8"),
                )
            ],
        ),
        (
            "Deckel",
            [OperationDraft(op="create_lid", inputs=("obj_1",), params={"thickness": "=@wand"})],
        ),
        (
            "Rastnasen",
            [
                OperationDraft(
                    op="insert_latch",
                    inputs=("obj_1",),
                    params={
                        "width": 12.0,
                        "height": 3.0,
                        "x": x,
                        # Einen Millimeter vor der Wand, auf der Viertelbreite:
                        # bei der Vorgabe dieselben ±30 und 39 wie zuvor.
                        "y": "=@tiefe / 2 - 1",
                        "z": 40.0,
                        "axis": "y",
                    },
                )
                for x in ("=-@breite / 4", "=@breite / 4")
            ],
        ),
        (
            "Farben",
            [
                OperationDraft(
                    op="assign_slot",
                    inputs=("obj_1",),
                    params={"slot": 1, "name": "PETG Hellgrau", "colour": "#b6bcc4"},
                ),
                OperationDraft(
                    op="assign_slot",
                    inputs=("obj_2",),
                    params={"slot": 2, "name": "PETG Orange", "colour": "#f0a54a"},
                ),
            ],
        ),
        (
            "Deckel danebenlegen",
            [
                OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": LID_OFFSET}),
                OperationDraft(op="place_on_bed", inputs=("obj_1",)),
                OperationDraft(op="place_on_bed", inputs=("obj_2",)),
            ],
        ),
        (
            "Schriftzug auf dem Deckel",
            [
                OperationDraft(
                    op="label_text",
                    inputs=("obj_2",),
                    params={
                        "text": "SOLIDON",
                        "size": 12.0,
                        "depth": 0.8,
                        "mode": "raised",
                        "x": LID_OFFSET,
                        "y": 0.0,
                        "z": 6.4,
                        "nz": 1.0,
                    },
                )
            ],
        ),
        (
            "Auf dem Bett anordnen",
            # **Die Objekte ausdrücklich.** ``arrange_bed`` arbeitet über
            # ``ctx.inputs``; ohne sie lief der Schritt durch und ordnete
            # nichts — der Deckel blieb, wo er lag, und der Prüfbericht
            # behielt seinen Befund. Das Fenster macht es genauso
            # (``inputs_for`` in ``main_window``), nur dort zur Laufzeit.
            [OperationDraft(op="arrange_bed", inputs=("obj_1", "obj_2"), params={})],
        ),
    ]


def build() -> tuple[Project, int]:
    """Das Schaustück bauen — Schritt für Schritt, jeder einzeln geprüft.

    Ein Schritt, der die Kette anhält, wird zurückgenommen und gemeldet; er
    wird **nicht** stillschweigend übergangen. Sonst steht am Ende ein halbes
    Teil, das aussieht, als wäre es so gemeint.
    """
    project = new_project()
    document = project.document
    for name, value, title in SIZES:
        document.parameters[name] = Parameter(name=name, value=value, unit="mm", title=title)

    history = History(document)
    profile = profiles.make_profile()
    built = 0
    print(f"{'Schritt':26} {'Ergebnis':10} {'Körper':>6}")
    for title, drafts in steps():
        try:
            history.apply(title, drafts)
        except Exception as problem:
            print(f"{title:26} {'ABGELEHNT':10} {'—':>6}  {problem}")
            continue
        result = evaluate(document, profile)
        if not result.complete:
            blamed = [
                f"{entry.code}: {entry.message}"
                for entry in result.scene.report.findings
                if entry.code.startswith("op.")
            ]
            print(f"{title:26} {'HÄLT AN':10} {len(result.scene.objects):6}")
            for line in blamed:
                print(f"{'':26} {line}")
            history.undo()
            continue
        built += 1
        print(f"{title:26} {'gebaut':10} {len(result.scene.objects):6}")
    return project, built


#: Die Maße des Rollenhalters.
#:
#: Deutsch wie bei ``SIZES`` daneben, und aus demselben Grund: Parameternamen
#: gehören dem Nutzer und erscheinen in seiner Oberfläche.
HOLDER_SIZES = (
    ("rollenbreite", 68.0, "Rollenbreite"),
    ("wand", 6.0, "Wandstärke"),
    ("achse", 14.0, "Achsdurchmesser"),
)

#: Wie weit jede Laufachse von der Mitte weg liegt, in Millimetern.
#:
#: Ein **Versatz**, kein Abstand: Die eine Achse steht bei -32, die andere bei
#: +32, zwischen ihnen liegen also 64 Millimeter. Dieser Abstand trägt jede
#: Rolle von 130 bis 210 mm Durchmesser, ohne dass sie dazwischen durchfällt.
AXLE_OFFSET = 32.0
WALL_HEIGHT = 48.0
PLATE_DEPTH = 104.0
PLATE_THICKNESS = 9.0

#: Wie hoch die Achsmitte über der Plattenunterkante liegt.
AXLE_HEIGHT = PLATE_THICKNESS + WALL_HEIGHT - 6.0

#: Ein Schritt des Rollenhalters.
#:
#: Anders als beim Gehäuse stehen die Objektkennungen hier **nicht** vorher
#: fest: ``union_objects`` verbraucht beide Eingänge und legt einen **neuen**
#: Körper an — ``obj_1`` und ``obj_2`` sind danach beide weg, und wer die
#: nächste Operation auf ``obj_1`` schreibt, greift ins Leere. Jeder Schritt
#: bekommt deshalb die Kennung des Hauptkörpers und die des zuletzt erzeugten
#: Zusatzkörpers gereicht; ``build_holder`` liest beide nach jedem Schritt neu.
HolderStep = Callable[[str, str], list[OperationDraft]]


def _side_wall(side: float) -> list[tuple[str, HolderStep]]:
    """Eine Wange: erzeugen, an ihren Platz schieben, anwachsen lassen."""
    sign = "" if side > 0 else "-"
    name = "Rechte" if side > 0 else "Linke"
    return [
        (
            f"{name} Wange",
            lambda main_id, extra_id: [
                OperationDraft(
                    op="create_box",
                    params={
                        "width": "=@wand",
                        "depth": PLATE_DEPTH,
                        "height": WALL_HEIGHT,
                        "anchor": "centre",
                        "name": "Wange",
                    },
                )
            ],
        ),
        (
            f"{name} Wange stellen",
            lambda main_id, extra_id: [
                OperationDraft(
                    op="translate_object",
                    inputs=(extra_id,),
                    params={
                        "dx": f"={sign}(@rollenbreite / 2 + @wand / 2)",
                        # **``anchor="centre"`` zentriert in X und Y — in Z
                        # steht der Quader auf null.** Ein ``dz`` von halber
                        # Höhe hebt die Wange um genau diese halbe Höhe zu
                        # weit, und sie schwebt über der Platte, statt darauf
                        # zu stehen. Die Rechnung sah richtig aus; gesehen hat
                        # es erst das Bild.
                        "dz": PLATE_THICKNESS,
                    },
                )
            ],
        ),
        (
            f"{name} Wange anwachsen",
            lambda main_id, extra_id: [
                OperationDraft(op="union_objects", inputs=(main_id, extra_id))
            ],
        ),
    ]


def _bore(offset: float, name: str) -> list[tuple[str, HolderStep]]:
    """Das Lagerauge für eine Laufachse — quer durch **beide** Wangen."""
    return [
        (
            f"{name} Lagerauge",
            lambda main_id, extra_id: [
                OperationDraft(
                    op="drill_hole",
                    inputs=(main_id,),
                    params={
                        "diameter": "=@achse",
                        "x": 0.0,
                        "y": offset,
                        "z": AXLE_HEIGHT,
                        "axis": "x",
                        "depth": 0.0,
                    },
                )
            ],
        )
    ]


def _axle(offset: float, name: str) -> list[tuple[str, HolderStep]]:
    """Eine Laufachse — ein **eigenes** Teil, das in seinem Lagerauge steckt.

    Eingewachsen war sie eine Brücke von 68 mm mit rundem Querschnitt, und
    Solidons eigene Beratung sagte dazu „die Überhänge sind zu groß, um sich
    selbst zu tragen". Gesteckt druckt der Halter ohne eine einzige Stütze und
    die Achse liegend ebenso — und das Teil zeigt nebenbei eine Passung, die
    ein einzelner Körper nicht zeigen kann.
    """
    return [
        (
            f"{name} Achse",
            lambda main_id, extra_id: [
                OperationDraft(
                    op="create_cylinder",
                    params={
                        "diameter": "=@achse",
                        # Beidseitig sechs Millimeter länger als der Halter
                        # breit ist: So gibt es an jeder Seite einen Zapfen
                        # zum Anfassen, und man sieht im Bild, dass die Achse
                        # ein eigenes Teil ist.
                        "height": "=@rollenbreite + 2 * @wand + 12",
                        "segments": 64,
                        "name": "Laufachse",
                    },
                )
            ],
        ),
        (
            f"{name} Achse legen",
            lambda main_id, extra_id: [
                OperationDraft(
                    op="rotate_object", inputs=(extra_id,), params={"axis": "y", "angle": 90.0}
                )
            ],
        ),
        (
            f"{name} Achse setzen",
            lambda main_id, extra_id: [
                OperationDraft(
                    op="translate_object",
                    inputs=(extra_id,),
                    # **Der Zylinder steht auf z = 0 und wird um seine eigene
                    # Mitte gedreht** — danach liegt seine Achse auf halber
                    # Länge. Wer die Zielhöhe direkt einträgt, addiert auf
                    # diese vierzig Millimeter darauf: Im ersten Lauf
                    # schwebten beide Achsen über den Wangen, statt darin zu
                    # liegen.
                    params={
                        "dy": offset,
                        "dz": f"={AXLE_HEIGHT} - (@rollenbreite + 2 * @wand + 12) / 2",
                    },
                )
            ],
        ),
        (
            f"{name} Achse färben",
            lambda main_id, extra_id: [
                OperationDraft(
                    op="assign_slot",
                    inputs=(extra_id,),
                    # Ein zweiter Farbtopf für die zwei Achsen: Sie sind eigene
                    # Teile, und wer das im Bild nicht sieht, hält sie für
                    # angewachsen — also für etwas, das mit Stützen gedruckt
                    # werden müsste.
                    params={"slot": 2, "name": "PETG Anthrazit", "colour": "#7b8794"},
                )
            ],
        ),
    ]


def holder_steps() -> list[tuple[str, HolderStep]]:
    """Der Rollenhalter und seine zwei gesteckten Achsen."""
    return [
        (
            "Grundplatte",
            lambda main_id, extra_id: [
                OperationDraft(
                    op="create_box",
                    params={
                        "width": "=@rollenbreite + 2 * @wand + 26",
                        "depth": PLATE_DEPTH,
                        "height": PLATE_THICKNESS,
                        "anchor": "centre",
                        "name": "Rollenhalter",
                    },
                )
            ],
        ),
        *_side_wall(-1.0),
        *_side_wall(1.0),
        (
            "Materialfenster",
            lambda main_id, extra_id: [
                OperationDraft(
                    op="drill_hole",
                    inputs=(main_id,),
                    # Quer durch **beide** Wangen in einem Zug: dazwischen ist
                    # Luft, und ein Loch je Wange wäre derselbe Schnitt
                    # zweimal. Es spart ein Drittel Filament und macht aus
                    # zwei Brettern ein Gestell.
                    params={
                        "diameter": 34.0,
                        "x": 0.0,
                        "y": 0.0,
                        "z": PLATE_THICKNESS + WALL_HEIGHT / 2,
                        "axis": "x",
                        "depth": 0.0,
                    },
                )
            ],
        ),
        *_bore(-AXLE_OFFSET, "Vorderes"),
        *_bore(AXLE_OFFSET, "Hinteres"),
        *_axle(-AXLE_OFFSET, "Vordere"),
        *_axle(AXLE_OFFSET, "Hintere"),
        (
            "Farbe",
            lambda main_id, extra_id: [
                OperationDraft(
                    op="assign_slot",
                    inputs=(main_id,),
                    # **Heller als der Grund, nicht dunkler.** Anthrazit
                    # (#4d5763) war die realistischere Filamentfarbe und im
                    # dunklen Viewport falsch: Die Beleuchtung ist auf die
                    # Standard-Körperfarbe #b9c4d0 eingestellt, und darunter
                    # verschwindet das Teil im Hintergrund, statt sich
                    # abzuheben.
                    params={"slot": 1, "name": "PETG Naturweiß", "colour": "#d5dae0"},
                )
            ],
        ),
        (
            "Auf das Bett",
            lambda main_id, extra_id: [OperationDraft(op="place_on_bed", inputs=(main_id,))],
        ),
    ]


def build_holder() -> tuple[Project, int]:
    """Den Rollenhalter bauen — mit Kennungen, die erst zur Laufzeit feststehen."""
    project = new_project()
    document = project.document
    for name, value, title in HOLDER_SIZES:
        document.parameters[name] = Parameter(name=name, value=value, unit="mm", title=title)

    history = History(document)
    profile = profiles.make_profile()
    built = 0
    main_id = ""
    extra_id = ""
    known: set[str] = set()
    print(f"{'Schritt':26} {'Ergebnis':10} {'Körper':>6}")
    for title, make in holder_steps():
        try:
            history.apply(title, make(main_id, extra_id))
        except Exception as problem:
            print(f"{title:26} {'ABGELEHNT':10} {'—':>6}  {problem}")
            continue
        result = evaluate(document, profile)
        if not result.complete:
            blamed = [
                f"{entry.code}: {entry.message}"
                for entry in result.scene.report.findings
                if entry.code.startswith("op.")
            ]
            print(f"{title:26} {'HÄLT AN':10} {len(result.scene.objects):6}")
            for line in blamed:
                print(f"{'':26} {line}")
            history.undo()
            continue
        built += 1
        present = list(result.scene.objects)
        # Der Hauptkörper ist der, der schon da war; der Zusatz der zuletzt
        # dazugekommene. Nach einem ``union`` bleibt genau einer übrig, und
        # der ist beides.
        fresh = [key for key in present if key not in known]
        known = set(present)
        if len(present) == 1:
            main_id = extra_id = present[0]
        else:
            extra_id = fresh[-1] if fresh else present[-1]
            main_id = next(key for key in present if key != extra_id)
        print(f"{title:26} {'gebaut':10} {len(present):6}")
    return project, built


#: Wo die Anpassung sitzt und wie groß sie ist.
#:
#: Vorn in der Grundplatte, dort wo man das Teil anschrauben würde. Fünf
#: Millimeter ist die Schraube, die jeder hat, und ``z`` liegt auf der
#: Plattenstärke, weil ``drill_hole`` von oben zählt.
ADAPTED_HOLE = {"diameter": 5.0, "x": 0.0, "y": -38.0, "z": PLATE_THICKNESS, "axis": "z"}


def build_adapted() -> tuple[Project, int, int]:
    """Das Schaustück für Weg 1: ein eingelesenes Modell, das angepasst wird.

    **Warum nicht das Beispielprojekt.** ``weg1-halterung-anpassen.p3d`` hat
    genau diese Struktur und zeigt dabei eine flache Platte mit fünf
    Bohrungen. Als Lehrstück richtig — es zeigt eine Sache ohne Ablenkung —,
    auf einer Website falsch: Wer dort eine flache Platte sieht, denkt „das
    kann jeder" und liest nicht weiter.

    **Warum der Rollenhalter.** Er steht im Aufmacher, und wenn das Video ihn
    wieder zeigt, erzählen Bühne und Sektion dieselbe Geschichte. Er wird hier
    frisch gebaut und nicht aus ``rollenhalter.p3d`` gelesen: Beide entstehen
    dann im selben Lauf aus derselben Quelle, und ein geänderter Halter kann
    nicht an einem alten Abzug vorbeilaufen.

    **Der Weg ist echt, auch wenn das Modell von uns stammt.** Es wird als STL
    geschrieben, als STL eingelesen, repariert und angepasst — genau das, was
    der Kunde mit einer heruntergeladenen Datei täte. Der Unterschied ist
    keiner, den man im Bild sieht; wir haben nur keine fremde, die wir zeigen
    dürfen.

    **Die Anpassung muss sichtbar sein**, sonst zeigt das Video ein Standbild
    mit einem Ladevorgang. Gewählt ist eine Bohrung durch die Grundplatte —
    der Fall aus §18.5, „indem man auf die Stelle zeigt, die stört".
    """
    source, _ = build_holder()
    profile = profiles.make_profile()
    scene = evaluate(source.document, profile).scene
    # Nur der Halter selbst — die beiden Achsen sind eigene Objekte und kämen
    # als lose Stücke in einer Datei an.
    body = next(entry for entry in scene.objects.values() if entry.name.startswith("Rollenhalter"))
    with tempfile.TemporaryDirectory() as folder:
        mesh = Path(folder) / "rollenhalter-import.stl"
        body.mesh.raw.export(str(mesh))
        data = mesh.read_bytes()
    print(f"Ausgangsdatei: {len(data) / 1024:.0f} kB, {body.mesh.triangle_count} Dreiecke")

    project = new_project()
    # **Die Datei reist im Projekt mit** (§16.1): ein Eintrag im Dokument und
    # die Bytes daneben. ``save`` schreibt beides in den Container und rechnet
    # die Prüfsumme.
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/rollenhalter-import.stl", sha256=""
    )
    project.sources["src_1"] = data

    plan: list[tuple[str, list[OperationDraft]]] = [
        (
            "Modell einlesen",
            [
                OperationDraft(
                    op="load", params={"source": "src_1", "unit": "mm", "name": "Rollenhalter"}
                )
            ],
        ),
        ("Reparieren", [OperationDraft(op="repair", inputs=("obj_1",), params={})]),
        ("Auf das Bett", [OperationDraft(op="place_on_bed", inputs=("obj_1",))]),
        (
            "Befestigungsloch setzen",
            [
                OperationDraft(
                    op="drill_hole", inputs=("obj_1",), params={**ADAPTED_HOLE, "depth": 0.0}
                )
            ],
        ),
    ]

    history = History(project.document)
    built = 0
    print(f"{'Schritt':26} {'Ergebnis':10} {'Körper':>6}")
    for title, drafts in plan:
        try:
            history.apply(title, drafts)
        except Exception as problem:
            print(f"{title:26} {'ABGELEHNT':10} {'—':>6}  {problem}")
            continue
        # **Ohne Lesezugriff findet ``load`` seine Datei nicht.** ``evaluate``
        # bekommt nur das Dokument; die Bytes liegen im Projekt daneben, und
        # ``ProjectSources`` ist die Brücke. Ohne sie endet der erste Schritt
        # in ``op.load.InternalError`` — eine Meldung, die nach Programmfehler
        # klingt und einen fehlenden Zugang meint.
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        if not result.complete:
            for entry in result.scene.report.findings:
                if entry.code.startswith("op."):
                    print(f"{'':26} {entry.code}: {entry.message}")
            print(f"{title:26} {'HÄLT AN':10} {len(result.scene.objects):6}")
            history.undo()
            continue
        built += 1
        print(f"{title:26} {'gebaut':10} {len(result.scene.objects):6}")
    return project, built, len(plan)


def main() -> int:
    # ``rollenhalter`` als Argument wählt das zweite Schaustück. Kein eigenes
    # Werkzeug daneben: Beide sind Teile für dieselbe Website, und zwei
    # Programme, die dasselbe tun, laufen unweigerlich auseinander.
    holder = "rollenhalter" in sys.argv
    # ``anpassen`` baut auf ``rollenhalter`` auf und schreibt ein anderes
    # Projekt — deshalb ein eigener Zweig und keine dritte Bedingung in der
    # Zeile darunter.
    if "anpassen" in sys.argv:
        project, built, total = build_adapted()
    else:
        project, built = build_holder() if holder else build()
        total = len(holder_steps()) if holder else len(steps())
    # **Mit Quellenzugang**, sonst zählt die Schlusszeile eine leere Szene.
    # Gemessen beim ersten Lauf der Anpassung: „4 von 4 Schritten, 0 Körper" —
    # jeder Schritt gebaut, und darunter nichts. ``load`` findet seine Datei
    # nur über ``ProjectSources``; für die beiden anderen Bauarten ist der
    # Leser leer und ändert nichts.
    result = evaluate(project.document, profiles.make_profile(), sources=ProjectSources(project))
    print(f"\n{built} von {total} Schritten, {len(result.scene.objects)} Körper")
    for entry in result.scene.objects.values():
        print(f"   {entry.name:26} {entry.mesh.triangle_count:7} Dreiecke")
    if built < total:
        print("\nNicht vollständig — das Schaustück wird nicht geschrieben.")
        return 1
    chosen = [entry for entry in sys.argv[1:] if entry.endswith(".p3d")]
    if "anpassen" in sys.argv:
        default = ROOT / "website" / "teile" / "weg1-halter-anpassen.p3d"
    elif holder:
        default = ROOT / "website" / "teile" / "rollenhalter.p3d"
    else:
        default = ROOT / "website" / "schaustueck.p3d"
    target = Path(chosen[0]) if chosen else default
    target.parent.mkdir(parents=True, exist_ok=True)
    save(project, target)
    print(f"\nGespeichert: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
