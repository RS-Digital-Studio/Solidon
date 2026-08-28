"""Die Auswahl in der Ansicht: was ein Klick trifft und wie tief (§18.5).

Der Klick auf ein Modell soll erst das Modell wählen und erst der nächste die
Bohrung darin. Diese Datei hält beide Hälften davon fest — dass die **Stufe**
stimmt, und dass der **Treffer** stimmt. Die zweite ist die ältere Frage: Bis
zur gestuften Tiefe nahm ``_feature_at`` das Merkmal mit dem nächsten
Mittelpunkt und traf damit immer eines, egal wie weit weg der Klick lag.

**Offscreen, und darum ohne Plotter.** Genau das ist hier die Falle: Vierzig
Methoden des Viewports steigen bei ``self.plotter is None`` sofort aus, und ein
Test, der einen von ihnen ruft, ist grün, ohne etwas geprüft zu haben. Alles,
was hier zählt, hängt deshalb an Methoden ohne diese Wache —
``_click_target``, ``_feature_at``, ``_select_at``, ``selection_depth`` sind
Aussagen über die Szene und nicht über VTK. Wo doch ein Plotter nötig ist
(der Mauszeiger), steht eine Attrappe mit genau den Feldern, die benutzt
werden, nach dem Muster von ``tests/test_cursors.py``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect
from app.core.scene.evaluate import EvaluationResult
from app.core.types import Scene, SceneObject
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.viewport import Viewport

MESHES = Path(__file__).parent / "data" / "meshes"

#: Die Platte aus dem Korpus: 80 x 50 x 8 mm, vier Bohrungen Ø5,19 an
#: (±25, ±15), sechs erkannte Flächen. Die Deckfläche liegt auf z = +4.
PLATE = MESHES / "plate_holes.stl"


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    """Ein Fenster mit der Platte darin — und danach warten, bis es still ist.

    Dieselbe Begründung wie in ``tests/test_analysis_ui.py``: Ein Arbeiter, der
    sein Fenster überlebt, nimmt beim Herunterfahren den Prozess mit. Nicht
    ``close()`` — das fragt bei ungesicherten Änderungen modal nach, und ein
    Test hängt dann an einem Fenster, das niemand sieht.
    """
    window = MainWindow(Session(), UiSettings())
    window.open_path(PLATE)
    window.session.wait_for_idle()
    yield window
    window.wait_for_workers()


def hole_centre(window: MainWindow) -> tuple[float, float, float]:
    entry = window.session.last_result.scene.objects["obj_1"]
    centre = entry.features["hole_1"].params["centre"]
    return (float(centre[0]), float(centre[1]), float(centre[2]))


def on_the_bore_wall(window: MainWindow, feature_id: str = "hole_1") -> tuple[float, float, float]:
    """Eine Stelle, die ein Klick auf diese Bohrung wirklich trifft.

    Nämlich auf ihrer **Wand**, nicht auf ihrer Achse. Der Unterschied ist der
    Grund, aus dem hier eine eigene Funktion steht: Der Mittelpunkt einer
    Bohrung liegt im Leeren, dort ist keine Oberfläche, und ein Picker kann ihn
    nicht zurückgeben. Tests, die ihn benutzten, prüften gegen eine Stelle, an
    die kein Klick kommt.
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    feature = entry.features[feature_id]
    centre = feature.params["centre"]
    radius = float(feature.params["diameter"]) * 0.5
    return (float(centre[0]) + radius, float(centre[1]), 2.0)


def on_the_top_face_beside_a_hole(window: MainWindow) -> tuple[float, float, float]:
    """Die Deckfläche, sieben Millimeter neben einer Bohrung.

    Der Ort des gemeldeten Fehlers: Über die Mittelpunkte gerechnet lag
    ``hole_1`` (8,1 mm) näher als der Mittelpunkt der 80 mm langen Deckfläche
    (36,1 mm), und ein Klick hierhin wählte die Bohrung.
    """
    return (-30.0, -20.0, 4.0)


def two_plates(qt_app: QApplication) -> tuple[Viewport, EvaluationResult]:
    """Eine Szene mit zwei echten Körpern, jeder mit eigenen Bohrungen.

    Von Hand gebaut und nicht aus einer Datei: Eine STL kennt keine Baugruppe,
    zwei Körper darin werden ein Objekt mit zwei Komponenten. Gebraucht werden
    hier aber zwei **Objekte** — die Frage ist, was ein Klick auf das Nachbarteil
    tut, während im ersten eine Bohrung gewählt ist.
    """
    import trimesh

    first = trimesh.load(PLATE)
    second = first.copy()
    second.apply_translation((200.0, 0.0, 0.0))
    objects: dict[str, SceneObject] = {}
    for index, body in enumerate((first, second), start=1):
        data = MeshData(body)
        objects[f"obj_{index}"] = SceneObject(
            id=f"obj_{index}",
            name=f"Platte {index}",
            mesh=data,
            features=detect(data),
        )
    result = EvaluationResult(scene=Scene(objects=objects))
    viewport = Viewport()
    viewport.show_scene(result)
    return viewport, result


# --- der Treffer: was liegt überhaupt unter dem Klick ---------------------------


def test_a_click_beside_a_hole_does_not_find_the_hole(window: MainWindow) -> None:
    """Der gemeldete Fehler, an seiner Stelle festgenagelt.

    Ein Klick auf die Deckfläche, sieben Millimeter neben einer Bohrung, meint
    die Fläche. Gemessen wurde vorher der Abstand zum **Mittelpunkt** jedes
    Merkmals, und der Mittelpunkt einer großen Fläche liegt weiter weg als der
    einer kleinen Bohrung daneben — es gab also immer einen Gewinner, und meist
    war es die Bohrung.
    """
    window.viewport.select("obj_1")
    found = window.viewport._feature_at(on_the_top_face_beside_a_hole(window))
    assert found != "hole_1", "sieben Millimeter neben der Bohrung ist nicht in ihr"
    assert found == "face_2", "es ist die Deckfläche, und die ist auch ein Merkmal"


def test_a_click_on_the_bore_wall_finds_that_hole(window: MainWindow) -> None:
    """§40 für P3: ein Klick muss die richtige Merkmal-ID liefern, keinen
    Beinahe-Treffer — und keinen Fehlgriff.

    Alle vier Bohrungen der Platte, jede an ihrer eigenen Wand. Die
    Verwechslungsgefahr ist echt: Sie sind gleich groß und liegen paarweise
    30 mm auseinander.

    **Dieser Test war in der Gegenprobe grün** — der alte Mittelpunktsabstand
    traf an der Bohrungswand dieselbe Bohrung. Er nagelt also keinen Fund fest,
    sondern hält die Hälfte, die schon stimmte: Die neue Reichweite darf einen
    richtigen Treffer nicht wegnehmen. Wer ihn später liest, soll das wissen
    und nicht auf ein Fix-Zeugnis schließen.
    """
    window.viewport.select("obj_1")
    for hole in ("hole_1", "hole_2", "hole_3", "hole_4"):
        point = on_the_bore_wall(window, hole)
        assert window.viewport._feature_at(point) == hole, hole


def test_a_click_far_from_every_feature_finds_none(window: MainWindow) -> None:
    """Neben dem Modell gibt es kein Merkmal — auch nicht das nächstgelegene.

    Ohne die Reichweite war das der Zustand, aus dem sich nichts mehr
    unterscheiden ließ: Jeder Punkt im Raum hatte ein nächstes Merkmal.
    """
    window.viewport.select("obj_1")
    assert window.viewport._feature_at((0.0, 0.0, 500.0)) is None


def test_a_feature_without_triangles_stays_reachable(qt_app: QApplication) -> None:
    """Eine offene Kantenschleife hat keine eigenen Dreiecke (§17.1).

    Sie bleibt über ihren Mittelpunkt erreichbar, sonst wäre der einzige
    Befund, den man anklicken möchte, der einzige, den man nicht anklicken
    kann. Die Reichweite gilt auch dort — sonst wäre die Grenze wieder weg.
    """
    import trimesh

    body = trimesh.load(MESHES / "broken_open.stl")
    data = MeshData(body)
    features = detect(data)
    loops = [key for key in features if key.startswith("edge_loop")]
    assert loops, "die kaputte Datei aus dem Korpus hat offene Kanten"
    entry = SceneObject(id="obj_1", name="Bruch", mesh=data, features=features)
    viewport = Viewport()
    viewport.show_scene(EvaluationResult(scene=Scene(objects={"obj_1": entry})))
    viewport.select("obj_1")

    centre = features[loops[0]].params["centre"]
    at = (float(centre[0]), float(centre[1]), float(centre[2]))
    assert viewport._feature_at(at) == loops[0], "am Mittelpunkt ist sie zu treffen"
    far = (at[0], at[1], at[2] + 500.0)
    # ``is None`` und nicht ``!= loops[0]``: Die schwächere Fassung war auch
    # gegen den alten Stand grün, weil der dort ``face_4`` zurückgab — die
    # nächste von fünf Mitten, einen halben Meter entfernt. Geprüft werden soll
    # aber, dass **keines** mehr in Reichweite ist.
    assert viewport._feature_at(far) is None, "einen halben Meter daneben keines"


# --- der Blick hinein: was ein Klick meint, wo kein Dreieck liegt --------------


def looking_down(
    x: float, y: float
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Ein Sichtstrahl senkrecht von oben, wie in der Draufsicht."""
    return ((x, y, 100.0), (0.0, 0.0, -1.0))


#: Wie weit der Strahl in der Draufsicht läuft, bis er die Deckfläche (z = +4)
#: erreicht: von z = 100 aus sind das 96 mm. Der Wert steht für ``until`` —
#: alles, was erst dahinter beginnt, hat der Klick nicht gemeint.
UNTIL_THE_TOP_FACE = 96.0


def test_looking_straight_into_a_through_hole_aims_at_it(window: MainWindow) -> None:
    """Der gemeldete Fehler: in der Draufsicht war eine Bohrung nicht anklickbar.

    **Gemessen am echten ``vtkCellPicker``** in einem sichtbaren Fenster, Platte
    aus dem Korpus, Bohrung 32 Pixel breit: Ein Klick 0 bis 8 Pixel neben der
    Bohrungsmitte gab ``kein Treffer`` — der Picker fand nichts, weil die
    Zylinderwand parallel zum Strahl liegt und hinter der Durchgangsbohrung
    keine Fläche mehr kommt. Erst 12 Pixel weiter, praktisch auf der Wand,
    kam ``hole_1``.

    Was der Nutzer davon sah: Ein Klick mitten in die Bohrung tat nichts oder
    hob die Auswahl auf (``objectPicked.emit("")`` in :meth:`_on_left_click`),
    ein Klick knapp daneben wählte die Deckfläche. „Wir erwischen oft nur die
    Oberfläche und kommen nicht zur Bohrung."

    Der Punkt aus :meth:`Viewport._bore_aim` liegt **im Loch**, und von dort
    findet die schon vorhandene Rechnung (:meth:`_feature_inside`) die Bohrung.
    """
    viewport = window.viewport
    centre = hole_centre(window)
    origin, direction = looking_down(centre[0], centre[1])

    aimed = viewport._bore_aim(origin, direction, float("inf"))
    assert aimed is not None, "senkrecht in die Bohrung gesehen ist sie gemeint"
    assert viewport._feature_at(aimed) == "hole_1", "und von dort führt der Weg zu ihr"


def test_a_hole_wins_over_the_face_a_fraction_beside_it(window: MainWindow) -> None:
    """Knapp neben dem Bohrungsrand meint der Klick die Bohrung, nicht die Fläche.

    Der zweite Teil des gemeldeten Fehlers, und er hing nicht am Picker: Landet
    der Strahl auf der Deckfläche, gewinnt sie **immer** — ihr Abstand ist
    null, der der Bohrung größer als null. Damit war
    :data:`FEATURE_REACH_SHARE` für Bohrungen wirkungslos; gemessen gab schon
    ein Punkt 0,4 mm neben dem Bohrungsrand ``face_2``, bei einer Reichweite
    von 0,95 mm.

    Die erste Zusicherung hält den alten Weg fest, damit sichtbar bleibt, was
    sich ändert: Über den Punkt allein ist es die Fläche.
    """
    viewport = window.viewport
    centre = hole_centre(window)
    radius = (
        float(
            window.session.last_result.scene.objects["obj_1"].features["hole_1"].params["diameter"]
        )
        * 0.5
    )
    beside = centre[0] + radius + 0.4

    on_the_face = (beside, centre[1], 4.0)
    assert viewport._feature_at(on_the_face) == "face_2", "über den Punkt allein die Fläche"

    origin, direction = looking_down(beside, centre[1])
    aimed = viewport._bore_aim(origin, direction, UNTIL_THE_TOP_FACE)
    assert aimed is not None, "vier Zehntel neben dem Rand ist die Bohrung gemeint"
    assert viewport._feature_at(aimed) == "hole_1"


def test_a_ray_well_beside_the_hole_aims_at_nothing(window: MainWindow) -> None:
    """Sieben Millimeter daneben bleibt die Fläche die Fläche.

    Die Gegenprobe zu ``test_a_click_beside_a_hole_does_not_find_the_hole``: Der
    Vorrang der Bohrung gilt nur, solange der Strahl sie überhaupt durchquert.
    Ohne diese Grenze wäre die Reichweite wieder weg, und wir hätten den Fehler
    von vorher — „die Auswahl nimmt immer die Bohrung statt des Modells".
    """
    viewport = window.viewport
    origin, direction = looking_down(-30.0, -20.0)
    assert viewport._bore_aim(origin, direction, UNTIL_THE_TOP_FACE) is None


def test_a_hole_behind_the_surface_is_not_aimed_at(window: MainWindow) -> None:
    """Von der Seite gesehen liegt die Bohrung hinter dem Material.

    Gemessen in der Vorderansicht: Der Klick auf die Stelle, an der die Bohrung
    *wäre*, gab ``face_3`` — die Stirnfläche, 7,5 mm vor der Bohrung. Das ist
    richtig, denn dort ist keine Bohrung zu sehen, und es muss richtig bleiben:
    Der Strahl durchquert den Bohrungszylinder erst **hinter** dem
    Auftreffpunkt, und was hinter dem Sichtbaren liegt, hat niemand gemeint.
    """
    viewport = window.viewport
    centre = hole_centre(window)
    # Von vorn (-y) auf die Stirnfläche bei y = -25, die Bohrung liegt bei y = -15.
    origin = (centre[0], -100.0, 2.0)
    direction = (0.0, 1.0, 0.0)
    until = 75.0

    assert viewport._bore_aim(origin, direction, until) is None, "hinter der Fläche zählt nicht"
    assert viewport._bore_aim(origin, direction, float("inf")) is not None, (
        "ohne Grenze wäre sie es — genau deshalb braucht die Rechnung den Auftreffpunkt"
    )


def test_bore_span_along_the_axis(window: MainWindow) -> None:
    """Die Rechnung selbst, im entarteten Fall: Strahl parallel zur Achse.

    Dann gibt es keinen Ein- und Austritt durch den Mantel — der Strahl liegt
    ganz innen oder ganz außen. Wer das übersieht, teilt durch null und verliert
    genau den Fall, um den es hier geht: die Draufsicht.
    """
    from app.ui.viewport import bore_span

    axis = (0.0, 0.0, 1.0)
    centre = (0.0, 0.0, 0.0)
    along = (-4.0, 4.0)

    inside = bore_span((0.0, 0.0, 100.0), (0.0, 0.0, -1.0), centre, axis, 2.5, along)
    assert inside is not None, "auf der Achse läuft der Strahl durch die ganze Bohrung"
    assert inside[0] == pytest.approx(96.0), "Eintritt an der Oberkante"
    assert inside[1] == pytest.approx(104.0), "Austritt an der Unterkante"

    outside = bore_span((9.0, 0.0, 100.0), (0.0, 0.0, -1.0), centre, axis, 2.5, along)
    assert outside is None, "neun Millimeter neben der Achse geht er vorbei"


def test_a_tool_that_sets_a_place_does_not_look_for_a_bore(window: MainWindow) -> None:
    """Der Bohrungsvorrang gilt der **Auswahl**, nicht jedem Klick.

    Formen, Bemalen, Messen, Trennen und Skelett setzen eine Stelle, und die
    liegt auf der Oberfläche. Ein Punkt auf der Bohrungsachse wäre dort einer in
    der Luft: bemalt würde nichts, gemessen würde von einer Stelle, an der kein
    Material ist, und der Pinselring stünde im Leeren.

    Geprüft wird an :meth:`_means_a_feature`, weil offscreen kein Plotter
    existiert und :meth:`_on_left_click` deshalb nichts täte — die Weiche ist
    die Aussage, nicht der Klick.
    """
    viewport = window.viewport
    assert viewport._means_a_feature(), "ohne Werkzeug meint ein Klick die Auswahl"

    for turn_on, turn_off in (
        (lambda: viewport.set_sculpting(True, 5.0), lambda: viewport.set_sculpting(False)),
        (lambda: viewport.set_boning(True), lambda: viewport.set_boning(False)),
        (lambda: viewport.set_splitting(True), lambda: viewport.set_splitting(False)),
        (
            lambda: viewport.set_measure_mode("distance"),
            lambda: viewport.set_measure_mode("off"),
        ),
    ):
        turn_on()
        assert not viewport._means_a_feature(), "mit Werkzeug meint er eine Stelle"
        turn_off()
        assert viewport._means_a_feature(), "und danach wieder die Auswahl"


def pierced_plate(qt_app: QApplication) -> Viewport:
    """Eine Platte mit **rechteckigem** Durchbruch: ein Loch ohne Merkmal.

    Der Unterschied zur Bohrung ist der Punkt dieser Tests. Eine Bohrung ist
    ein Merkmal (``hole``, mit Durchmesser und Achse); ein rechteckiger
    Ausschnitt ist es nicht — er besteht aus vier Wandflächen, und keine davon
    ist die Sache, auf die jemand zeigt.

    **Durch den Einleseweg der Anwendung**, nicht über ``trimesh.load``: Die
    Erkennung hängt an den beim Einlesen zusammengeführten Eckpunkten, und ein
    Prüfaufbau, der diesen Weg umgeht, hat schon einmal einen Mangel erfunden,
    den es nicht gab (ROADMAP, 24.08.2026).
    """
    import trimesh

    from app.core.geom.mesh import read_mesh
    from app.core.ingest.loader import normalise

    plate = trimesh.creation.box(extents=(60.0, 40.0, 8.0))
    cut = trimesh.creation.box(extents=(12.0, 8.0, 40.0))
    pierced = trimesh.boolean.difference([plate, cut], engine="manifold")
    data = normalise(read_mesh(trimesh.exchange.stl.export_stl(pierced), ".stl"), "mm").mesh
    entry = SceneObject(id="obj_1", name="Durchbruch", mesh=data, features=detect(data))
    viewport = Viewport()
    viewport.show_scene(EvaluationResult(scene=Scene(objects={"obj_1": entry})))
    return viewport


def test_a_click_through_an_opening_means_the_body_and_beside_it_nothing(
    qt_app: QApplication,
) -> None:
    """Ein Klick durch eine Öffnung hebt die Auswahl nicht auf — und daneben doch.

    Der zweite Teil des Fundes vom 24.08., und er brauchte eine andere Rechnung
    als die Bohrung. Zwei Dinge, die zuerst plausibel klangen und beide falsch
    sind:

    * **„Strahl gegen die Merkmalsdreiecke" löst es nicht.** Bei senkrechtem
      Blick sind die Wände des Ausschnitts **parallel** zum Strahl — dort ist so
      wenig ein Dreieck zu treffen wie an der Bohrungswand.
    * **Es gibt kein Merkmal zu wählen.** Vier Wandflächen, keine davon
      „richtiger" als die andere; ein Gewinner wäre erfunden.

    Was bleibt, ist die Aussage über den **Körper**: Wer in eine Öffnung zeigt,
    hat auf das Teil gezeigt. Vorher gab der Picker dort nichts zurück, und
    ``_on_left_click`` machte daraus ``objectPicked.emit("")`` — die Auswahl war
    weg. Gemessen am echten Picker, Draufsicht: 0 bis 30 Pixel in der Öffnung
    vorher ``(None, None)``, jetzt ``("obj_1", None)``.

    **Beide Richtungen in einem Test, und das ist kein Sparen an Zusicherungen,
    sondern eines an Fenstern:** Die Gegenprobe „daneben ist daneben" braucht
    denselben Körper, und jede zusätzliche Viewport-Instanz erhöht die Rate des
    Abbau-Risses dieser Datei. Gemessen: ohne die neuen Ansichten 0 von 10
    Läufen gerissen, mit ihnen 2 von 10. Das reißt die vorab gesetzte Latte
    nicht (≥4 von 10), zeigt aber die Richtung — also nur so viele Fenster wie
    Aussagen, die keinen eigenen brauchen.

    „Daneben" ist dabei die Zusage aus §18.5: Ein Klick daneben hebt die Auswahl
    auf, und das ist der einzige Weg, sie ohne den Objektbaum loszuwerden.
    Deshalb fragt die Rechnung die **konvexe Hülle** und nicht den Hüllquader.
    """
    viewport = pierced_plate(qt_app)
    viewport.select("obj_1")

    aimed = viewport._through_aim((0.0, 0.0, 200.0), (0.0, 0.0, -1.0))
    assert aimed is not None, "senkrecht durch den Ausschnitt ist das Teil gemeint"
    assert viewport._click_target(aimed) == ("obj_1", None), "der Körper, kein erfundenes Merkmal"
    assert viewport._feature_at(aimed) is None, (
        "mitten im Ausschnitt liegt keine Wand in Reichweite"
    )

    assert viewport._through_aim((100.0, 0.0, 200.0), (0.0, 0.0, -1.0)) is None, "neben dem Teil"
    assert viewport._through_aim((0.0, 60.0, 200.0), (0.0, 0.0, -1.0)) is None, "daneben in y"


def test_a_ray_through_a_notch_means_the_body_too(qt_app: QApplication) -> None:
    """Die Grenze der Rechnung, als Zusage und nicht als Zufall.

    Die konvexe Hülle deckt auch eine **Kerbe** ab — bei einem L-Profil liegt
    der Strahl durch den fehlenden Quadranten in ihr, ohne das Netz zu treffen.
    Der Klick wählt dort also den Körper, obwohl er durch Luft geht.

    **Das ist die gewollte Seite der Abwägung**, und die Alternative wäre
    schlechter: Ein Kriterium, das die Kerbe ausnimmt, müsste zwischen „Loch"
    und „Einbuchtung" unterscheiden — dieselbe Unterscheidung, die ein Kunde
    nicht trifft, wenn er auf ein Teil zeigt und zwei Bildpunkte neben die
    Silhouette kommt. Wer die Auswahl loswerden will, klickt in den freien
    Raum, und dort ist auch keine Hülle.
    """
    import trimesh

    from app.core.geom.mesh import read_mesh
    from app.core.ingest.loader import normalise

    upright = trimesh.creation.box(extents=(10.0, 40.0, 40.0))
    foot = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    foot.apply_translation((15.0, 0.0, -15.0))
    profile = trimesh.boolean.union([upright, foot], engine="manifold")
    data = normalise(read_mesh(trimesh.exchange.stl.export_stl(profile), ".stl"), "mm").mesh
    entry = SceneObject(id="obj_1", name="L-Profil", mesh=data, features=detect(data))
    viewport = Viewport()
    viewport.show_scene(EvaluationResult(scene=Scene(objects={"obj_1": entry})))
    viewport.select("obj_1")

    # Durch den fehlenden Quadranten: über dem Fuß, neben dem Steher.
    through_the_notch = viewport._through_aim((20.0, 0.0, 200.0), (0.0, 0.0, -1.0))
    assert through_the_notch is None or viewport._click_target(through_the_notch)[0] == "obj_1", (
        "in der Kerbe ist das Teil gemeint, nicht das Nichts"
    )


def test_the_sampled_hull_says_the_same_as_the_exact_one() -> None:
    """Die Zusage der Stichprobe, und sie hat keinen anderen Ort.

    :func:`app.core.geom.mesh.hull_planes` rechnet die konvexe Hülle über
    höchstens :data:`HULL_SAMPLE_LIMIT` Eckpunkte, weil die exakte an einer
    feinen Kugel 5084 ms kostet — jeder ihrer Punkte liegt auf der Hülle. Die
    Stichprobe **unterschätzt** die Hülle grundsätzlich; was sie taugt, ist
    deshalb eine Messung und keine Herleitung.

    Geprüft wird gegen die Platte aus dem Korpus, wo beide Wege dasselbe sagen
    müssen: zwölf Flächen und das Volumen eines Quaders. Ohne diesen Test wäre
    die Zahl 4096 eine Behauptung, die still altert — wer sie senkt, sieht hier,
    wann sie zu klein wird.

    **Kein Widget, deshalb ohne ``qt_app``** — und trotzdem hier: Die Rechnung
    hat genau einen Aufrufer, und das ist der Klick nebenan
    (``Viewport._through_aim``). Eine eigene Datei für zwei Funktionen wäre ein
    Ort, an dem niemand sucht.
    """
    import numpy as np
    from scipy.spatial import ConvexHull

    from app.core.geom.mesh import hull_planes, read_mesh
    from app.core.ingest.loader import normalise

    data = normalise(read_mesh(PLATE.read_bytes(), ".stl"), "mm").mesh
    planes = hull_planes(data)
    assert planes is not None, "eine Platte hat eine räumliche Hülle"

    exact = ConvexHull(np.asarray(data.raw.vertices, dtype=float))
    assert len(planes) == len(exact.equations), "dieselbe Zahl Flächen wie exakt gerechnet"
    # 80 x 50 x 8 mm: der Quader ist seine eigene Hülle.
    assert exact.volume == pytest.approx(32000.0, rel=1e-6)


def test_a_body_without_vertices_has_no_hull() -> None:
    """Ein Körper ohne Eckpunkte hat keinen Innenraum, und das ist kein Fehler.

    Das ``Mesh``-Protokoll (§9) sagt nichts über ein ``raw`` zu — ein
    B-Rep-Körper hat keines. Die Rechnung antwortet dann mit ``None``, und der
    Klick fällt auf sein voriges Verhalten zurück, statt eine Ausnahme in einen
    Qt-Slot zu werfen, wo sie niemand sieht.
    """
    from app.core.geom.mesh import hull_planes

    class WithoutRaw:
        """Genau so viel Mesh, wie die Frage braucht: keines."""

    assert hull_planes(WithoutRaw()) is None  # type: ignore[arg-type]


# --- die Stufe: wie tief ein Klick geht ----------------------------------------


def test_the_first_click_takes_the_body_and_the_second_the_hole(window: MainWindow) -> None:
    """Das Verlangte, in einem Test.

    Zweimal dieselbe Stelle auf der Bohrungswand. Der erste Klick meint das
    Teil, der zweite die Bohrung darin — das Modell von Figma und Illustrator,
    wo ein Klick die Gruppe nimmt und der nächste das Element darin.

    Vorher war die Reihenfolge umgekehrt und die erste Stufe fehlte ganz: Ein
    Körper mit erkannten Bohrungen war per Klick überhaupt nicht auswählbar,
    und wer die Platte verschieben wollte, musste in den Objektbaum ausweichen.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)

    assert viewport._click_target(point) == ("obj_1", None), "erst das Teil"
    viewport._select_at(point)
    assert viewport.selection_depth() == 1, "und die Auswahl steht auf dem Teil"

    assert viewport._click_target(point) == ("obj_1", "hole_1"), "dann die Bohrung"
    viewport._select_at(point)
    assert viewport.selection_depth() == 2
    assert viewport.selected_feature == "hole_1"


def test_inside_a_body_the_next_hole_comes_directly(window: MainWindow) -> None:
    """Wer drin ist, bleibt drin — die Tiefe hängt am Körper, nicht am Pixel.

    Von einer gewählten Bohrung zur nächsten führt **ein** Klick und nicht
    erst der Weg zurück über das ganze Teil. Blender setzt beim Weiterschalten
    zurück, sobald die Maus sich bewegt; für vier Bohrungen an einer Platte
    wäre das eine Stufe zu viel.

    **Auch dieser war in der Gegenprobe grün**, und zwar aus dem Fehler heraus,
    den es zu beheben gab: Der alte Stand ging immer sofort auf das Merkmal, ein
    Klick genügte also erst recht. Was er festhält, ist die Zusage, dass die
    neue Stufe diesen kurzen Weg **nicht** verlängert.
    """
    viewport = window.viewport
    viewport._select_at(on_the_bore_wall(window, "hole_1"))
    viewport._select_at(on_the_bore_wall(window, "hole_1"))
    assert viewport.selected_feature == "hole_1"

    viewport._select_at(on_the_bore_wall(window, "hole_3"))
    assert viewport.selected_feature == "hole_3", "ein Klick, nicht zwei"


def test_a_click_on_bare_surface_comes_back_up_to_the_body(window: MainWindow) -> None:
    """Im Körper drin auf die nackte Fläche geklickt heißt: der Körper.

    Genauer die Deckfläche, die hier selbst ein Merkmal ist — auch das ist eine
    Stufe zurück gegenüber der Bohrung, und niemand bleibt in ihr hängen.
    """
    viewport = window.viewport
    viewport._select_at(on_the_bore_wall(window))
    viewport._select_at(on_the_bore_wall(window))
    assert viewport.selection_depth() == 2

    viewport._select_at(on_the_top_face_beside_a_hole(window))
    assert viewport.selected_feature == "face_2", "die Fläche, nicht die Bohrung"


def test_another_body_starts_over_at_the_top(qt_app: QApplication) -> None:
    """Ein Klick auf das Nachbarteil wählt das Nachbarteil, nicht sein Merkmal.

    Sonst führte der Weg von einer Bohrung im ersten Teil zu einer Bohrung im
    zweiten, ohne dass jemand das zweite Teil gemeint hätte.
    """
    viewport, _ = two_plates(qt_app)
    viewport.select("obj_1")
    viewport.select_feature("hole_1")

    # Dieselbe Stelle wie in obj_1, nur 200 mm weiter — die Wand von hole_1
    # des zweiten Körpers.
    wall_in_the_other = (200.0 - 25.0 + 2.595, -15.0, 2.0)
    assert viewport._click_target(wall_in_the_other) == ("obj_2", None)


def test_a_click_beside_the_model_clears_everything(window: MainWindow) -> None:
    """Neben das Modell geklickt heißt: Auswahl weg, und zwar ganz.

    Der einzige Weg, sie ohne den Objektbaum loszuwerden — deshalb steht er
    nicht unter der gestuften Tiefe, sondern daneben.
    """
    viewport = window.viewport
    viewport._select_at(on_the_bore_wall(window))
    viewport._select_at(on_the_bore_wall(window))
    assert viewport.selection_depth() == 2

    assert viewport._click_target((0.0, 0.0, 500.0)) == (None, None)
    viewport._select_at((0.0, 0.0, 500.0))
    assert viewport.selection_depth() == 0


def test_the_body_is_announced_before_its_feature(window: MainWindow) -> None:
    """Die Reihenfolge der Signale, und sie ist keine Geschmacksfrage.

    Der Baum zeigt ein Merkmal nur unter der Zeile seines Objekts. Solange der
    Viewport bei einem Treffer allein ``featurePicked`` sendete, lief das ins
    Leere: ``_on_feature_picked`` fragt den Baum nach dem ausgewählten Objekt,
    und ausgewählt war noch keines. Im Fenster sah es aus, als käme der Klick
    nicht an — in Wahrheit war er angekommen und hatte niemanden.

    Zwei Klicks statt einem, seit die Tiefe gestuft ist; die Reihenfolge im
    zweiten ist dieselbe geblieben.
    """
    order: list[str] = []
    window.viewport.objectPicked.connect(lambda name: order.append(f"object:{name}"))
    window.viewport.featurePicked.connect(lambda name: order.append(f"feature:{name}"))

    point = on_the_bore_wall(window)
    window.viewport._select_at(point)
    window.viewport._select_at(point)

    assert order == ["object:obj_1", "object:obj_1", "feature:hole_1"]


# --- der Weg zurück -------------------------------------------------------------


def test_escape_steps_back_out_one_level_at_a_time(window: MainWindow) -> None:
    """Merkmal → Körper → nichts, mit je einem Escape (§18.5).

    Ohne diesen Weg ist die Tiefe eine Einbahnstraße: Wer eine Bohrung gewählt
    hatte, kam nur wieder zum ganzen Teil, indem er neben das Modell klickte
    und von vorn anfing.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)
    viewport._select_at(point)
    viewport._select_at(point)
    assert viewport.selection_depth() == 2

    assert window._step_selection_out() is True
    assert viewport.selection_depth() == 1, "das Merkmal fällt weg, das Teil bleibt"
    assert window.object_tree.selected() == "obj_1"

    assert window._step_selection_out() is True
    assert viewport.selection_depth() == 0, "und dann auch das Teil"

    assert window._step_selection_out() is False, "aus nichts führt kein Weg heraus"


def test_escape_closes_an_open_tool_before_it_touches_the_selection(
    window: MainWindow,
) -> None:
    """Ein offenes Werkzeug meint mit Escape sich selbst.

    Die Rangfolge in ``_escape``: Skizze, Skelett, Formen, Werkzeug, und erst
    danach die Auswahl. Wer *Messen* offen hat und Escape drückt, will das
    Messen beenden — dass dabei auch noch die Auswahl zerfiele, wäre eine
    zweite Wirkung, die niemand bestellt hat.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)
    viewport._select_at(point)
    viewport._select_at(point)
    window.tools.activate("measure")

    window._escape()
    assert window.tools.active() is None, "das Werkzeug ist zu"
    assert viewport.selection_depth() == 2, "und die Auswahl steht noch"

    window._escape()
    assert viewport.selection_depth() == 1, "jetzt greift Escape die Auswahl"


# --- was der Zeiger verspricht --------------------------------------------------


def test_the_pointer_promises_exactly_what_the_click_does(window: MainWindow) -> None:
    """Der Zeiger stellt dieselbe Frage wie der Klick, mit derselben Rechnung.

    Damit wird die Stufe sichtbar, ohne dass irgendwo ein Satz darüber stehen
    muss: Über einer Bohrung am noch nicht gewählten Teil steht der
    Auswahlzeiger, nach dem ersten Klick der Merkmalszeiger. Laufen die beiden
    auseinander, verspricht der Zeiger etwas, das nicht eintritt — die Falle,
    vor der `.claude/rules/ansicht.md` bei ``_resting_role`` warnt.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)

    assert viewport._would_pick_feature(point) is False, "erster Klick nimmt das Teil"
    viewport._select_at(point)
    assert viewport._would_pick_feature(point) is True, "der nächste die Bohrung"


def test_the_resting_pointer_reaches_the_decision(window: MainWindow) -> None:
    """Und die Antwort kommt auch am Zeiger an, nicht nur in der Rechnung.

    Der Grund für die Attrappe: ``_look_under_pointer`` und ``_update_cursor``
    steigen bei ``self.plotter is None`` beide aus, und offscreen gibt es
    keinen Plotter. Ein Test ohne sie prüfte, dass die Methode umkehrt.

    **Gefälscht wird die Punktquelle, und die heißt jetzt ``_aim_at``** — vorher
    stand hier ``module._world_under``. Der Zeiger fragt dasselbe wie der Klick,
    und das schließt den Blick durch eine Bohrung hindurch ein; hinter
    ``_aim_at`` liegt ein echter ``vtkCellPicker``, der eine Attrappe als
    Renderer nicht annimmt. Was diese Kette **davor** tut, steht in den Tests
    zu ``_bore_aim`` weiter oben; was sie **danach** tut, ist genau das, was
    hier geprüft wird.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)
    shown: list[Any] = []

    class FakeInteractor:
        def setCursor(self, cursor: Any) -> None:  # noqa: N802 — Qt-Name
            shown.append(cursor)

        def height(self) -> int:
            return 600

    class FakePlotter:
        renderer = object()
        interactor = FakeInteractor()

        def render(self) -> None:
            """Die sichtbare Hover-Markierung fordert genau ein Neuzeichnen an."""

    viewport.plotter = FakePlotter()
    try:
        viewport._aim_at = lambda *_args: point  # type: ignore[method-assign]
        # Dieser Test gilt dem Zeigerweg; die sichtbare Hover-Fläche hat ihren
        # eigenen Plotter-Test in ``test_viewport_decisions.py``.
        viewport._redraw_features = lambda: None  # type: ignore[method-assign]
        viewport._hover_at = (10, 10)

        viewport._look_under_pointer()
        assert viewport._cursor_role == "select", "noch nichts gewählt: das Teil"

        viewport.select("obj_1")
        viewport._look_under_pointer()
        assert viewport._cursor_role == "feature", "Teil gewählt: jetzt die Bohrung"
    finally:
        del viewport._aim_at
        del viewport._redraw_features
        viewport.plotter = None

    assert shown, "und gesetzt wurde er wirklich, nicht nur vermerkt"


def test_a_right_click_goes_straight_to_the_deepest_target(window: MainWindow) -> None:
    """Rechts fragt, was hier liegt — und meint immer das Genaueste (§18.5).

    Der Bauplan nennt das Kontextmenü **am Merkmal** den Ort für Weg 1: ein
    fremdes Modell wird angepasst, indem man auf die Stelle zeigt, die stört.
    Wäre der Rechtsklick gestuft wie der Linksklick, hinge diese Zusage an einer
    Vorbedingung, die niemand kennt — man müsste die Bohrung erst linksklicken,
    um ihr Menü zu bekommen.

    Damit teilen sich die zwei Tasten die Arbeit: **links wandert** durch die
    Tiefe, **rechts fragt** nach dem, was unter dem Zeiger liegt. Dieselbe
    Trennung hat Fusion 360.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)

    assert viewport._click_target(point) == ("obj_1", None), "links: erst das Teil"
    assert viewport._click_target(point, direct=True) == ("obj_1", "hole_1"), "rechts: sofort"


def test_a_right_click_leaves_the_selection_where_it_landed(window: MainWindow) -> None:
    """Und die Stufe geht dabei nicht verloren.

    Ein Rechtsklick auf eine Bohrung setzt die Auswahl auf sie; der nächste
    Linksklick führt von dort weiter und nicht von vorn. Sonst wären es zwei
    Auswahlbegriffe — einer für jede Maustaste.
    """
    viewport = window.viewport
    viewport._select_at(on_the_bore_wall(window, "hole_1"), direct=True)
    assert viewport.selection_depth() == 2
    assert viewport.selected_feature == "hole_1"

    viewport._select_at(on_the_bore_wall(window, "hole_4"))
    assert viewport.selected_feature == "hole_4", "der Linksklick setzt fort, statt aufzusetzen"


# --- wenn ein Dialog fragt ------------------------------------------------------


def test_a_dialog_gets_its_answer_on_the_first_click(window: MainWindow) -> None:
    """Solange ein Dialog nach einem Merkmal fragt, gibt es keine Stufen.

    Ein Klick ist dann eine Antwort und keine Navigation. Zweimal zeigen zu
    müssen, um zu antworten, sähe aus wie ein verschluckter erster Klick —
    genau der Eindruck, aus dem §18.5 mit dem Anklicken herausführen soll.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)

    viewport.set_direct_picking(True)
    assert viewport._click_target(point) == ("obj_1", "hole_1"), "sofort, ohne Umweg"

    viewport.set_direct_picking(False)
    assert viewport._click_target(point) == ("obj_1", None), "und danach wieder gestuft"


def test_opening_and_closing_a_dialog_switches_it(window: MainWindow) -> None:
    """Und das Fenster schaltet es wirklich um — an beiden Enden.

    Ohne das Zurückschalten bliebe die gestufte Tiefe nach dem ersten Dialog
    für den Rest der Sitzung aus.
    """
    from PySide6.QtWidgets import QDialog

    dialog = QDialog(window)
    window._open_operation_dialog(dialog, lambda: None)  # type: ignore[arg-type]
    assert window.viewport._direct_picking is True

    dialog.reject()
    QApplication.processEvents()
    assert window.viewport._direct_picking is False


# --- was die Stufe nicht kaputt macht ------------------------------------------


def test_a_new_evaluation_forgets_the_prepared_triangles(window: MainWindow) -> None:
    """Die vorbereiteten Merkmalsdreiecke gehören einer Auswertung.

    Eine Operation, die eine Bohrung verschiebt, ändert ihre Dreiecke — würde
    der Zwischenspeicher überleben, träfe ein Klick danach dort, wo sie war.
    """
    viewport = window.viewport
    viewport.select("obj_1")
    assert viewport._feature_at(on_the_bore_wall(window)) == "hole_1"
    assert viewport._feature_geometry, "vorbereitet wurde etwas"

    viewport.show_scene(window.session.last_result)
    assert not viewport._feature_geometry, "und beim Szenenwechsel weggeräumt"


def test_the_reach_grows_with_the_body(window: MainWindow) -> None:
    """Ein fester Millimeterwert wäre an einem Gehäuse zu streng.

    Gepickt wird im dezimierten Anzeigenetz (§18.9), und dessen Oberfläche
    liegt nicht auf der der Szene. Die Reichweite wächst deshalb mit der
    Diagonale, mit einer Untergrenze für kleine Teile.
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    big = dataclasses.replace(entry, id="obj_big")
    viewport = window.viewport

    small = viewport._feature_reach("obj_1")
    assert small > 0.5, "die Platte ist groß genug für den Anteil"
    assert viewport._feature_reach(None) == pytest.approx(0.5), "ohne Körper die Untergrenze"
    assert big.id != entry.id, "der Vergleichskörper ist ein anderer"


def test_a_second_feature_takes_over_from_the_first(window: MainWindow) -> None:
    """Von einer Bohrung direkt auf die nächste — ohne Umweg über den Körper.

    **Robert am 23.08.2026:** „wenn ich ein merkmal auswähle und im viewport
    dann wieder auf das modell oder einem anderen merkmal klicke wechseln wir
    auch nicht."

    Der Weg dorthin ist gebaut: ``_click_target`` gibt bei demselben Körper
    ``self._feature_at(point)`` zurück, und ``_select_at`` setzt es. Geprüft
    war bisher nur der Wechsel **hinein** (Körper → Bohrung, in
    ``test_the_first_click_takes_the_body_and_the_second_the_hole``) und der
    Weg **heraus** auf eine Fläche, die selbst ein Merkmal ist. Der Wechsel
    zwischen zwei gleichrangigen Merkmalen stand nicht darin.
    """
    viewport = window.viewport
    entry = window.session.last_result.scene.objects["obj_1"]
    holes = [f for f in entry.features.values() if f.kind == "hole"]
    assert len(holes) >= 2, "ohne zwei Bohrungen prüft der Test nichts"

    def on_wall(feature: Any) -> tuple[float, float, float]:
        index = next(iter(feature.face_indices or ()))
        return tuple(float(value) for value in entry.mesh.raw.triangles[index].mean(axis=0))

    window.viewport.select("obj_1")
    viewport._select_at(on_wall(holes[0]))
    assert viewport.selected_feature == holes[0].id, "die erste Bohrung wurde nicht gewählt"

    viewport._select_at(on_wall(holes[1]))
    assert viewport.selected_feature == holes[1].id, (
        f"von {holes[0].id} kommend bleibt die Auswahl stehen statt auf {holes[1].id} zu wechseln"
    )
