"""Was die Ansicht *entscheidet*, nicht was sie zeichnet (§35).

Offscreen ist ``Viewport.plotter`` None, und vierzig Methoden steigen an ihrer
Wache aus, bevor ihr Rumpf läuft — bei dreißig davon läuft er in der ganzen
Suite kein einziges Mal. Der Bauplan hat daraus eine Reihenfolge gemacht: Ein
Test hinter einer Wache, die nie fällt, ist grün und prüft nichts; die Antwort
darauf ist nicht die nächste Attrappe, sondern die prüfbare Aussage aus dem
Unprüfbaren herauszulösen.

Diese Datei nimmt beide Hälften. Zuerst die Aussagen, die **vor** der Wache
stehen und trotzdem nie geprüft wurden — sie brauchen kein VTK, sie brauchten
nur jemanden, der sie aufruft. Danach die, für die eine Attrappe nötig ist:
eine mit genau den Methoden, die benutzt werden, wie in ``test_cursors.py``.

**Der Anlass steht in der Roadmap** („Vierzig Prozent der Ansicht sieht das Tor
nie", 22.08.2026): Die Frage war, ob die Druckplatte nach einem Themenwechsel
hell wird, und die Antwort lautete, das könne kein Test sagen. Sie lautet
inzwischen anders — die Hälfte davon liegt seit je vor der Wache.

**Was diese Datei erreicht, und was ausdrücklich nicht.** Der Punkt verlangt
eine Entscheidung je Methode und dass die übrigen als „nicht geprüft" geführt
werden, statt stillschweigend mitzulaufen. Also:

*Erreicht, ohne VTK:* ``set_theme`` (vier Farben, vor der Wache),
``show_scene`` in seinem ``result is None``-Zweig (Auswahl, Merkmal, Maße) und
``_weak_callbacks`` — die fünf Rückrufe an den Interaktionsstil standen bis
hierher in ``set_navigation`` hinter der Wache und liefen offscreen nie.

*Erreicht, über eine Attrappe:* ``show_build_volume`` und ``_draw_one_bed`` —
Farben je Actor und die Namen je Platte.

*Ausdrücklich nicht erreicht, und das ist der nützliche Teil:*
``_world_at`` und ``_face_handle`` brauchen einen echten Picker; eine Attrappe
dafür wäre eine Nachbildung von VTK und prüfte am Ende sie selbst. Ebenso
liegen ``_draw_brush``, ``_redraw_features``, ``_redraw_feature_patch``,
``_redraw_measurements``, ``_redraw_layer``, ``_label_gizmo``, ``fly_to`` und
``_add_orientation_widget`` weiter unerreicht. Bei ihnen lohnt zuerst dasselbe
wie bei ``set_navigation``: die rechnende Hälfte herausziehen, statt eine
Attrappe davorzustellen. Gemessen liegt bei ``_redraw_feature_patch`` und
``_draw_brush`` das Verhältnis bei 15:2 und 13:3 rechnenden zu zeichnenden
Anweisungen — dort steht die meiste ungeprüfte Aussage.
"""

from __future__ import annotations

import gc
import weakref
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.types import Profile
from app.ui.theme import THEMES, viewport_colours

# --- vor der Wache: was ohne VTK prüfbar ist ------------------------------------


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_theme_reaches_the_viewport(theme: str, qt_app: QApplication) -> None:
    """Der Viewport übernimmt die vier Farben seines Themas.

    Sie stehen in ``set_theme`` vor dem Plotter-Zweig, und das ist richtig so:
    welche Farbe gilt, ist eine Aussage über die Ansicht und nicht über VTK.
    Geprüft wurde sie trotzdem nie — ``tests/test_theme_and_palette.py`` prüft
    die *Palette*, also dass ``viewport_colours`` zueinander passende Werte
    liefert, aber nicht, dass der Viewport sie annimmt. Dazwischen passt ein
    ganzer Fehler: ein Thema, das gesetzt wird und nirgends ankommt.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_theme(theme)

    wanted = viewport_colours(theme)  # type: ignore[arg-type]
    assert viewport._object_colour == wanted["object"]
    assert viewport._bed_colour == wanted["bed"]
    assert viewport._bed_surface == wanted["bed_surface"]
    assert viewport._edge_colour == wanted["edge"]


def test_the_bed_changes_colour_with_the_theme(qt_app: QApplication) -> None:
    """Die Frage, mit der der ganze Punkt anfing: Wird die Platte hell?

    Ein Thema, das den Hintergrund wechselt und die Platte stehen lässt, ergibt
    ein helles Fenster mit einem dunklen Raster darin — oder umgekehrt. Der
    Kontrast der Palette ist anderswo geprüft; hier steht, dass der Viewport
    **beide** Bettfarben wirklich austauscht und nicht nur eine davon.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_theme("dark")
    dark = (viewport._bed_colour, viewport._bed_surface)
    viewport.set_theme("light")
    light = (viewport._bed_colour, viewport._bed_surface)

    assert dark[0] != light[0], "das Raster der Platte blieb, wie es war"
    assert dark[1] != light[1], "der Grund unter dem Raster blieb, wie er war"


def test_switching_back_and_forth_lands_where_it_started(qt_app: QApplication) -> None:
    """Zweimal umschalten führt zurück — sonst sammelt sich beim Wechseln
    etwas an, das niemand zurücksetzt."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_theme("light")
    first = (viewport._object_colour, viewport._bed_colour, viewport._edge_colour)
    viewport.set_theme("dark")
    viewport.set_theme("light")

    assert (viewport._object_colour, viewport._bed_colour, viewport._edge_colour) == first


def test_an_empty_scene_forgets_what_was_selected(qt_app: QApplication) -> None:
    """Was eine leere Szene nicht mehr hat: Auswahl, Merkmal, Maße.

    Die drei Zeilen stehen in ``show_scene`` vor dem Plotter-Zweig, und der
    Kommentar daneben sagt auch, warum: Das sind Aussagen über die Szene und
    nicht über VTK. Geprüft war davon nichts — der eine Test, der
    ``show_scene(None)`` aufruft, sieht auf die Kamera (``_fitted_to``).

    Ohne diese Zeilen behält der Viewport die Auswahl eines Projekts, das nicht
    mehr offen ist: Der Objektbaum ist leer, und der Prüfbericht fragt nach
    einem Körper, den es nicht gibt.
    """
    from app.core.geom.measure import Measurement
    from app.ui.viewport import Viewport

    viewport = Viewport()
    # Über die Wege, die auch die Anwendung nimmt — die Felder von Hand zu
    # setzen prüfte, dass ``show_scene`` sie leert, und nicht, dass eine
    # Auswahl dort überhaupt ankommt.
    viewport.select("obj_1")
    viewport.select_feature("hole_1")
    viewport.measurements.add(Measurement(kind="distance", value=12.5))
    # Über eine eigene Größe und nicht über das Feld: Eine Zusicherung auf dem
    # Attribut engt seinen Typ für den Rest der Funktion auf ``str`` ein, und
    # mypy hält die Prüfung darunter dann für unerreichbar.
    arrived = viewport._selected
    assert arrived == "obj_1", "die Auswahl kam nicht an"

    viewport.show_scene(None)

    assert viewport._selected is None, "die Auswahl überlebte das leere Projekt"
    assert viewport._selected_feature is None, "und das gewählte Merkmal auch"
    assert not len(viewport.measurements), "die Maße des vorigen Projekts blieben stehen"


# --- hinter der Wache: mit einer Attrappe ---------------------------------------


class _RecordingPlotter:
    """Eine Attrappe mit genau den Methoden, die das Zeichnen der Platte ruft.

    Sie schreibt mit, statt darzustellen: Jeder Aufruf landet als
    ``(name, kwargs)`` in :attr:`drawn`. Damit lassen sich zwei Aussagen prüfen,
    die sonst niemand erreicht — welche Farbe an der Platte ankommt, und ob die
    Namen der Actors die Plattennummer tragen.
    """

    def __init__(self) -> None:
        self.drawn: list[tuple[str, dict[str, Any]]] = []
        self.meshes: list[Any] = []
        self.labelled: list[list[str]] = []
        self.removed: list[object] = []
        self.renders = 0

    def add_mesh(self, mesh: object, **kwargs: Any) -> object:
        # Das Netz kommt mit: Bei der Merkmalsfläche ist die **Zahl der
        # Dreiecke** die Aussage — gefärbt werden die des Merkmals und nicht
        # die des ganzen Körpers.
        self.meshes.append(mesh)
        self.drawn.append(("mesh", kwargs))
        return object()

    def add_point_labels(self, _points: object, labels: object, **kwargs: Any) -> object:
        # Die Beschriftungen kommen mit: Sie sind bei der Merkmals-Überlagerung
        # die eigentliche Aussage, und ob sie erscheinen, ist die Frage von
        # Regel 18 — nicht, ob überhaupt etwas gezeichnet wurde.
        self.labelled.append([str(text) for text in labels])  # type: ignore[union-attr]
        self.drawn.append(("labels", kwargs))
        return object()

    def remove_actor(self, actor: object, **_kwargs: Any) -> None:
        self.removed.append(actor)

    def render(self) -> None:
        self.renders += 1

    def names(self) -> list[str]:
        """Die Actor-Namen in der Reihenfolge, in der gezeichnet wurde."""
        return [str(kwargs["name"]) for _kind, kwargs in self.drawn if "name" in kwargs]

    def colour_of(self, name: str) -> str:
        """Die Farbe, mit der dieser eine Actor gezeichnet wurde.

        Je Name und nicht als Menge über alles: Eine Prüfung, die nur fragt, ob
        eine Farbe *irgendwo* vorkommt, bleibt grün, wenn ein einzelner Actor
        auf eine falsche wechselt — dieselbe Farbe steht an drei weiteren
        Stellen. Gemessen: Die Gegenprobe mit einer fest verdrahteten Farbe im
        Raster lief durch, bis diese Zuordnung da war.
        """
        for _kind, kwargs in self.drawn:
            if str(kwargs.get("name")) == name:
                return str(kwargs.get("color"))
        raise AssertionError(f"kein Actor namens {name!r} — gezeichnet wurde: {self.names()}")


def test_the_bed_is_drawn_in_the_colours_of_the_theme(
    profile: Profile, qt_app: QApplication
) -> None:
    """Die andere Hälfte derselben Frage.

    Dass ``set_theme`` die Farben setzt, steht oben. Hier steht, dass sie beim
    Zeichnen auch benutzt werden — der Rumpf von ``_draw_one_bed`` ist der
    größte, der in der Suite nie läuft, und ein Thema, das bis an ihn heran
    stimmt und dort nicht ankommt, sähe im Bild genauso falsch aus wie eines,
    das gar nicht gesetzt wurde.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_theme("light")
    plotter = _RecordingPlotter()
    viewport.plotter = plotter
    viewport.show_build_volume(profile)

    assert plotter.drawn, "die Platte wurde nie gezeichnet"
    assert plotter.colour_of("bed_0") == viewport._bed_colour, (
        "das Raster nahm die Farbe des Themas nicht an"
    )
    assert plotter.colour_of("bed_surface_0") == viewport._bed_surface, (
        "der Grund nahm die Farbe des Themas nicht an"
    )
    assert plotter.colour_of("build_volume_0") == viewport._bed_colour, (
        "der Eckwinkel des Bauraums nahm die Farbe des Themas nicht an"
    )


def _scene_with_two_holes() -> Any:
    """Ein Körper mit zwei benannten Bohrungen — die kleinste Szene, an der
    sich „welches Merkmal wird beschriftet" überhaupt stellen lässt.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Feature, Scene, SceneObject

    mesh = MeshData(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    features = {
        "hole_1": Feature(
            id="hole_1",
            kind="hole",
            provenance="detected",
            params={"diameter": 5.0, "centre": (-10.0, 0.0, 5.0), "axis": (0.0, 0.0, 1.0)},
        ),
        "hole_2": Feature(
            id="hole_2",
            kind="hole",
            provenance="detected",
            params={"diameter": 8.0, "centre": (10.0, 0.0, 5.0), "axis": (0.0, 0.0, 1.0)},
        ),
    }
    return EvaluationResult(
        scene=Scene(
            objects={"obj_1": SceneObject(id="obj_1", name="A", mesh=mesh, features=features)}
        )
    )


def _with_faces(result: Any, feature_id: str, faces: tuple[int, ...]) -> Any:
    """Demselben Merkmal Dreiecke zuordnen, wie die Erkennung es täte."""
    import dataclasses

    entry = result.scene.objects["obj_1"]
    merkmal = dataclasses.replace(entry.features[feature_id], face_indices=faces)
    features = {**entry.features, feature_id: merkmal}
    result.scene.objects["obj_1"] = dataclasses.replace(entry, features=features)
    return result


def test_the_chosen_feature_keeps_its_label_without_the_overlay(qt_app: QApplication) -> None:
    """Regel 18: Ohne Beschriftung wäre die Aussage allein die Farbe.

    Die Merkmals-Überlagerung lässt sich abschalten, und dann verschwinden die
    Beschriftungen — bis auf die des **gewählten** Merkmals. Dessen Fläche
    leuchtet in der Auswahlfarbe, und eine Aussage allein über Farbe ist genau
    die, die Regel 18 verbietet.

    Der Kommentar an ``_redraw_features`` sagt das seit je zu; geprüft hat es
    nichts. Der Rumpf liegt hinter der Offscreen-Wache, und der Nachbartest
    prüft eine andere Hälfte derselben Sache — dass ein Klick auch ohne
    Überlagerung trifft (``test_clicking_needs_no_overlay_switch``). Beides ist
    nötig: Treffen kann man ein Merkmal, das man nicht lesen kann.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.show_scene(_scene_with_two_holes())
    viewport._selected = "obj_1"
    viewport._selected_feature = "hole_2"
    plotter = _RecordingPlotter()
    viewport.plotter = plotter

    viewport.set_feature_overlay(True)
    mit_overlay = [text for gruppe in plotter.labelled for text in gruppe]
    assert len(mit_overlay) == 2, f"mit Überlagerung stehen beide da: {mit_overlay}"

    plotter.labelled.clear()
    viewport.set_feature_overlay(False)
    ohne_overlay = [text for gruppe in plotter.labelled for text in gruppe]

    assert len(ohne_overlay) == 1, (
        f"ohne Überlagerung bleibt genau die des gewählten Merkmals: {ohne_overlay}"
    )
    assert "8" in ohne_overlay[0], (
        f"und es ist die des gewählten (Ø 8), nicht die des anderen: {ohne_overlay[0]}"
    )


def test_only_the_triangles_of_the_feature_take_the_selection_colour(
    qt_app: QApplication,
) -> None:
    """§18.5: Ein Klick auf eine Bohrung wählt zweierlei — den Körper und die
    Stelle. Gefärbt wird die Stelle.

    Vorher nahm der **ganze Körper** die Auswahlfarbe an, und die Bohrung, die
    gemeint war, unterschied sich von der Wand daneben durch nichts. Der Rumpf,
    der das behebt, liegt hinter der Offscreen-Wache und lief in keinem Test.

    Geprüft wird die **Zahl der Dreiecke**, denn genau daran hängt die Aussage:
    zwei zugeordnete gegen zwölf des Quaders. Ein Test, der nur fragt, ob
    überhaupt eine Fläche gezeichnet wurde, wäre auch vor der Behebung grün
    gewesen.

    Dazu der Versatz entlang der Flächennormalen: Ohne ihn läge die Fläche
    exakt auf dem Netz darunter, und welche von beiden man sieht, entschiede
    der Tiefenpuffer. Die Punkte müssen also **neben** dem Original liegen.
    """
    import numpy as np

    from app.ui.viewport import SELECTED_COLOUR, Viewport

    viewport = Viewport()
    viewport.show_scene(_with_faces(_scene_with_two_holes(), "hole_2", (0, 1)))
    viewport._selected = "obj_1"
    viewport._selected_feature = "hole_2"
    plotter = _RecordingPlotter()
    viewport.plotter = plotter

    viewport._redraw_feature_patch()

    flaeche = [kwargs for kind, kwargs in plotter.drawn if kwargs.get("name") == "feature-patch"]
    assert flaeche, f"keine Merkmalsfläche gezeichnet — gezeichnet wurde: {plotter.names()}"
    assert str(flaeche[0].get("color")) == str(SELECTED_COLOUR), (
        "die Fläche nahm die Auswahlfarbe nicht an"
    )

    netz = plotter.meshes[-1]
    assert netz.n_cells == 2, (
        f"gefärbt sind die zwei Dreiecke des Merkmals, nicht die zwölf des Quaders: {netz.n_cells}"
    )

    original = np.asarray(viewport._result.scene.objects["obj_1"].mesh.raw.vertices, dtype=float)
    punkte = np.asarray(netz.points, dtype=float)
    abstand = np.min(np.linalg.norm(punkte[:, None, :] - original[None, :, :], axis=2), axis=1)
    assert float(abstand.max()) > 0.0, (
        "ohne Versatz liegt die Fläche exakt auf dem Netz, und der Tiefenpuffer entscheidet"
    )


def test_a_round_body_gets_no_edges_and_a_box_does(qt_app: QApplication) -> None:
    """§18.1: Hier stehen die Kanten des *Körpers*, nicht die des Netzes.

    „Massiv mit Kanten" zeichnet jede Dreieckskante — das beantwortet, wie fein
    das Netz ist. Es beantwortet nicht, wo das Teil eine Kante hat: Bei einem
    Zylinder aus zweihundert Segmenten geht die eine, auf die es ankommt, in
    zweihundertneunundneunzig anderen unter.

    Der Docstring sagt beides wörtlich zu — „ein rundes Teil bekommt gar
    keine: eine Kugel hat keine Kante, und eine erfundene wäre schlimmer als
    keine" —, und geprüft hat es nichts. Der Rumpf liegt hinter der
    Offscreen-Wache.

    Zwei Körper, eine Frage: Der Quader hat zwölf echte Kanten, die Kugel
    keine. Ein Test mit nur einem der beiden wäre auch dann grün, wenn die
    Methode immer zeichnete oder nie.
    """
    import pyvista as pv

    from app.ui.viewport import Viewport

    viewport = Viewport()
    plotter = _RecordingPlotter()
    viewport.plotter = plotter

    viewport._draw_feature_edges(pv.Box().triangulate(), "obj_1")
    viewport._draw_feature_edges(pv.Sphere(theta_resolution=32, phi_resolution=32), "obj_2")

    gezeichnet = plotter.names()
    assert "edges:obj_1" in gezeichnet, f"der Quader hat Kanten: {gezeichnet}"
    assert "edges:obj_2" not in gezeichnet, (
        f"eine Kugel hat keine Kante, und eine erfundene wäre schlimmer: {gezeichnet}"
    )


def test_edges_belong_to_the_solid_mode_only(qt_app: QApplication) -> None:
    """In den anderen drei Modi ist entweder alles schon gezeichnet oder man
    sieht hindurch — dann wäre eine zweite Linienlage nur Gitter.

    Die Bedingung steht in derselben Zeile wie die Offscreen-Wache
    (``self._mode != "solid"``), und genau deshalb hat sie nie jemand gefahren.
    """
    import pyvista as pv

    from app.ui.viewport import Viewport

    viewport = Viewport()
    plotter = _RecordingPlotter()
    viewport.plotter = plotter
    quader = pv.Box().triangulate()

    viewport._mode = "wireframe"
    viewport._draw_feature_edges(quader, "obj_1")
    assert "edges:obj_1" not in plotter.names(), "im Drahtgitter ist schon alles gezeichnet"

    viewport._mode = "solid"
    viewport._draw_feature_edges(quader, "obj_1")
    assert "edges:obj_1" in plotter.names(), "im massiven Modus gehören sie dazu"


def test_the_pointer_is_flipped_from_qt_to_vtk(qt_app: QApplication) -> None:
    """VTK zählt seine Y-Achse von unten, Qt von oben.

    Ohne die Umrechnung sucht das Hover-Picking am gespiegelten Ort — und das
    ist die Sorte Fehler, die lange überlebt: **In der Bildmitte stimmt sie
    zufällig.** Bei 600 Bildpunkten Höhe ist 600 − 300 wieder 300, und wer dort
    prüft, sieht nichts.

    Gemessen wird deshalb **außerhalb** der Mitte. Ein Test bei y = 300 wäre
    auch dann grün, wenn die Zeile ganz fehlte.
    """
    from app.ui.viewport import Viewport

    class _Punkt:
        def __init__(self, x: int, y: int) -> None:
            self._x, self._y = x, y

        def x(self) -> int:
            return self._x

        def y(self) -> int:
            return self._y

    class _Interactor:
        @staticmethod
        def height() -> int:
            return 600

    class _MitInteractor(_RecordingPlotter):
        interactor = _Interactor()

    viewport = Viewport()
    viewport.plotter = _MitInteractor()

    viewport._note_pointer(_Punkt(120, 100))
    assert viewport._hover_at == (120, 500), (
        f"Qt zählt von oben, VTK von unten: {viewport._hover_at} statt (120, 500)"
    )

    # Und der Beleg, warum die Mitte nichts prüft: dort ist beides gleich.
    viewport._note_pointer(_Punkt(120, 300))
    assert viewport._hover_at == (120, 300), "in der Mitte fällt der Fehler nicht auf"


def test_orthographic_reaches_the_plotter(qt_app: QApplication) -> None:
    """§18.1: Orthografisch ist das, was gemessene Längen vertrauenswürdig
    macht.

    Der Zustand steht **vor** der Wache (`self._projection = projection`) und
    ist damit offscreen prüfbar — was dahinter liegt, ist der Aufruf am
    Plotter, und der lief in keinem Test. Ein Umschalter, der seinen Zustand
    merkt und ihn nicht weitergibt, sieht in jeder Abfrage richtig aus und
    zeigt im Bild eine Perspektive, in der gemessene Längen nicht stimmen.

    Beide Richtungen, weil eine allein auch dann grün wäre, wenn die Methode
    immer dasselbe täte.
    """
    from app.ui.viewport import Viewport

    class _MitProjektion(_RecordingPlotter):
        def __init__(self) -> None:
            super().__init__()
            self.gerufen: list[str] = []

        def enable_parallel_projection(self) -> None:
            self.gerufen.append("parallel an")

        def disable_parallel_projection(self) -> None:
            self.gerufen.append("parallel aus")

    viewport = Viewport()
    plotter = _MitProjektion()
    viewport.plotter = plotter

    viewport.set_projection("orthographic")
    assert plotter.gerufen[-1] == "parallel an", plotter.gerufen
    assert viewport._projection == "orthographic"

    viewport.set_projection("perspective")
    assert plotter.gerufen[-1] == "parallel aus", plotter.gerufen
    assert viewport._projection == "perspective"


def test_the_callbacks_reach_the_view_while_it_lives(qt_app: QApplication) -> None:
    """Erst die Gegenrichtung: Ein Rückruf, der *nie* etwas tut, wäre auch
    schwach — und damit wären die zwei Tests darunter wertlos.

    ``is_sculpting`` ist dafür der richtige Zeuge: eine reine Auskunft über den
    Zustand der Ansicht, ohne Picker und ohne Renderer.
    """
    from app.ui.viewport import Viewport, _weak_callbacks

    viewport = Viewport()
    calls = _weak_callbacks(viewport)

    viewport._sculpting = True
    assert calls.is_sculpting() is True, "der Rückruf erreicht die Ansicht nicht"
    viewport._sculpting = False
    assert calls.is_sculpting() is False


def test_every_callback_holds_the_view_only_weakly(qt_app: QApplication) -> None:
    """Die Vorkehrung gegen den Absturz ohne Zeile, zum ersten Mal geprüft.

    VTK hält den Stil, der Stil hält diese Rückrufe. Hielten sie die Ansicht
    stark, wäre die Schleife geschlossen: Der Viewport überlebte jedes
    Schließen, der Speicherbereiniger räumte ihn später ab, und dann stünde ein
    C++-Objekt hinter einer Python-Referenz, die es nicht mehr gibt.

    Geprüft wird an den Zellen der Rückrufe und nicht daran, ob die Ansicht
    verschwindet: Das täte sie auch dann nicht, wenn ein *anderer* Halter sie
    festhielte, und dieser Test soll seine eigene Aussage prüfen. Die andere
    steht darunter.
    """
    from app.ui.viewport import Viewport, _weak_callbacks

    viewport = Viewport()
    calls = _weak_callbacks(viewport)

    for name in calls._fields:
        held = [cell.cell_contents for cell in getattr(calls, name).__closure__ or ()]
        assert held, f"{name} schließt über nichts — hat es die Ansicht noch?"
        for value in held:
            assert isinstance(value, weakref.ReferenceType), (
                f"{name} hält die Ansicht stark statt schwach"
            )


def test_a_released_view_is_actually_released(qt_app: QApplication) -> None:
    """Und niemand sonst hält sie fest — die Probe auf alle Halter zusammen.

    **Der Fund, aus dem dieser Test entstand.** Bis dahin überlebten *zwanzig
    von zwanzig* losgelassenen Ansichten ihr ``del`` samt ``gc.collect()``. Der
    Halter war ein Lambda am eigenen Schichtzeitgeber: Viewport → QTimer →
    Rückruf → Viewport. Über die C++-Grenze sieht Pythons Speicherbereiniger
    die mittlere Kante nicht und kann die Schleife nicht brechen.

    Der Test steht hier und nicht bei den Zeitgebern, weil er die Sorte Fehler
    fängt, die keine Ausnahme wirft: Jede weitere starke Verbindung an ein
    eigenes Kind macht ihn rot, gleich wer sie einbaut.
    """
    from app.ui.viewport import Viewport

    watchers = []
    for _ in range(5):
        viewport = Viewport()
        watchers.append(weakref.ref(viewport))
        del viewport
    gc.collect()

    alive = [watch for watch in watchers if watch() is not None]
    assert not alive, f"{len(alive)} von 5 Ansichten überlebten ihr Loslassen"


def test_a_callback_after_the_view_is_gone_stays_quiet(qt_app: QApplication) -> None:
    """Und es kracht auch nicht: Ein Ereignis, das nach dem Schließen ankommt,
    findet keine Ansicht und tut nichts. Genau dafür fragt jeder der fünf
    Rückrufe erst nach, statt die Referenz zu benutzen."""
    from app.ui.viewport import Viewport, _weak_callbacks

    viewport = Viewport()
    calls = _weak_callbacks(viewport)
    del viewport
    gc.collect()

    calls.on_context(10, 20)
    calls.on_pick(10, 20)
    calls.on_cursor("rotate")
    calls.on_paint(10, 20, True)


def test_each_plate_draws_under_its_own_names(profile: Profile, qt_app: QApplication) -> None:
    """Vier Betten bleiben vier, weil ihre Actors verschiedene Namen tragen.

    ``name=`` ersetzt in pyvista, was denselben Namen hat: Mit festen Namen
    bliebe von vier Betten genau eines übrig, und der Docstring der Methode sagt
    das auch. Geprüft war es nicht — die Zeile, die den Namen bildet, läuft
    offscreen nie.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    plotter = _RecordingPlotter()
    viewport.plotter = plotter
    viewport._beds_for_view = lambda: 3  # type: ignore[method-assign]
    viewport.show_build_volume(profile)

    names = plotter.names()
    assert len(names) == len(set(names)), f"zwei Actors teilen sich einen Namen: {names}"
    for plate in range(3):
        assert f"bed_{plate}" in names, f"Platte {plate + 1} bekam kein Raster"
        assert f"bed_surface_{plate}" in names, f"Platte {plate + 1} bekam keinen Grund"
