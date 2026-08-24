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
import math
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


class _RecordingActor:
    """Was ``add_mesh`` zurückgibt — so viel davon, wie der Code benutzt.

    Ein ``vtkActor`` trägt seine Darstellung in ``prop``, und Solidon setzt
    dort das Verwerfen der Rückseite an der Plattenfläche. Die Attrappe
    schreibt mit, statt zu tun, damit ein Test sie ansehen kann.
    """

    def __init__(self) -> None:
        self.prop = _RecordingProperty()


class _RecordingProperty:
    """Die Darstellung eines Actors — nur die Felder, die gesetzt werden."""

    def __init__(self) -> None:
        self.culling = "none"


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
        self.actors: list[_RecordingActor] = []
        """Die zurückgegebenen Actors, in der Reihenfolge von drawn.

        Damit ein Test nicht nur sehen kann, **was** gezeichnet wurde, sondern
        auch, was danach am Actor gesetzt wurde — die Plattenfläche etwa wirft
        ihre Rückseite weg."""

    def add_mesh(self, mesh: object, **kwargs: Any) -> object:
        # Das Netz kommt mit: Bei der Merkmalsfläche ist die **Zahl der
        # Dreiecke** die Aussage — gefärbt werden die des Merkmals und nicht
        # die des ganzen Körpers.
        self.meshes.append(mesh)
        self.drawn.append(("mesh", kwargs))
        # **Ein Actor, kein nacktes ``object()``.** Hier stand eines, und damit
        # sagte die Attrappe zu, dass mit dem Rückgabewert nichts geschieht.
        # Das stimmte, bis die Plattenfläche ihre Rückseite wegwerfen musste
        # (``surface.prop.culling``) — dann fiel der Aufruf über eine Attrappe,
        # die weniger kann als die Sache, die sie nachstellt. Ein echter Actor
        # hat ``prop``; wer ihn nachstellt, gibt ihm eines.
        actor = _RecordingActor()
        self.actors.append(actor)
        return actor

    def add_point_labels(self, _points: object, labels: Any, **kwargs: Any) -> object:
        # Die Beschriftungen kommen mit: Sie sind bei der Merkmals-Überlagerung
        # die eigentliche Aussage, und ob sie erscheinen, ist die Frage von
        # Regel 18 — nicht, ob überhaupt etwas gezeichnet wurde.
        self.labelled.append([str(text) for text in labels])
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

    ergebnis = viewport._result
    assert ergebnis is not None
    roh: Any = ergebnis.scene.objects["obj_1"].mesh
    original = np.asarray(roh.raw.vertices, dtype=np.float64)
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
    assert str(viewport._projection) == "perspective"


class _BrokenDriver(_RecordingPlotter):
    """Ein Plotter, dessen OpenGL die schönen Sachen nicht kann.

    Genau die Maschine, für die die ``try``-Blöcke geschrieben sind: Sie soll
    ein einfacheres Bild bekommen und keinen Absturz.
    """

    def enable_anti_aliasing(self, _mode: str) -> None:
        raise RuntimeError("kein FXAA auf diesem Treiber")

    def enable_ssao(self, **_kwargs: Any) -> None:
        raise RuntimeError("kein SSAO auf diesem Treiber")

    def disable_ssao(self) -> None:
        raise RuntimeError("kein SSAO auf diesem Treiber")


def test_a_driver_without_the_extras_gets_a_simpler_picture(qt_app: QApplication) -> None:
    """Kantenglättung und Umgebungsverdeckung hängen am Treiber.

    Eine Maschine, deren OpenGL sie nicht kann, soll ein einfacheres Bild
    bekommen und keinen Absturz — und was nicht ging, steht im Protokoll, nicht
    vor dem Nutzer. Der ``try`` steht seit je da; gefahren hat ihn nie jemand,
    weil der Rumpf hinter der Offscreen-Wache liegt und diese Maschine kann,
    was sie soll.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.plotter = _BrokenDriver()

    viewport._apply_render_quality()  # darf nicht werfen


def test_a_failed_occlusion_is_tried_again(qt_app: QApplication) -> None:
    """Was nicht ging, gilt nicht als getan.

    ``_occlusion_applied`` merkt sich den Stand, damit derselbe Aufruf nicht
    bei jedem Zeichnen wiederholt wird. Der ``return`` im Fehlerpfad sorgt
    dafür, dass ein **gescheiterter** Versuch dort nichts einträgt — sonst
    merkte sich der Viewport nach einem einmaligen Treiberfehler dauerhaft
    „ist an", während es aus ist, und probierte es nie wieder.

    Das ist dieselbe Frage wie beim Merkmal, das seinen Schritt anbietet: Ein
    Zustand, der einen Fehlschlag als Erfolg verbucht, ist schlechter als
    keiner.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.plotter = _BrokenDriver()
    # Die Eigenschaft folgt der Regel „keine Analysekarte" und ist damit an;
    # gesetzt wird sie nicht, sie *ist* die Regel.
    assert viewport.ambient_occlusion is True

    viewport._apply_ambient_occlusion()  # darf nicht werfen

    assert viewport._occlusion_applied is not True, (
        "ein gescheiterter Versuch darf sich nicht als erledigt merken"
    )


def test_the_camera_watcher_holds_the_view_only_weakly(qt_app: QApplication) -> None:
    """VTK hält den Beobachter, und eine starke Referenz von dort auf den
    Viewport überlebt jedes Schließen.

    Dieselbe Regel wie bei ``set_navigation`` und dieselbe Falle wie beim
    Zeitgeber der Schichtvorschau: Wer `self` in den Rückruf fängt, schließt
    einen Ring über die C++-Grenze, den Pythons Speicherbereiniger nicht
    sieht.
    """
    import gc
    import weakref

    from app.ui.viewport import Viewport

    class _MitInteractor(_RecordingPlotter):
        def __init__(self) -> None:
            super().__init__()
            self.beobachter: list[Any] = []
            self.interactor = self

        def AddObserver(self, _event: str, ruf: Any) -> int:  # noqa: N802 — VTK-Name
            self.beobachter.append(ruf)
            return 1

    viewport = Viewport()
    plotter = _MitInteractor()
    viewport.plotter = plotter
    viewport._watch_camera()

    assert plotter.beobachter, "kein Beobachter angemeldet"
    spur = weakref.ref(viewport)
    del viewport
    gc.collect()

    assert spur() is None, "der Beobachter hält die Ansicht fest — VTK überlebt sie, und damit sie"


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


def test_the_bed_surface_can_be_seen_through_from_below(
    profile: Profile, qt_app: QApplication
) -> None:
    """Von unten schaut man durch die Platte hindurch.

    **Robert am 23.08.2026:** „Man kann unten noch nicht durch die Druckfläche
    schauen, also die Platte. Das müsste auch noch behoben werden, dass man da
    durchschauen kann, wenn man's von unten bearbeiten will."

    Die Fläche wird gebraucht — ohne sie fiele der Schatten auf nichts —, aber
    nur von oben. ``culling = "back"`` wirft ihre Rückseite weg: Die Ebene
    zeigt mit ``direction=(0, 0, 1)`` nach oben, von unten sieht man ihre
    Rückseite, und die verschwindet, ohne die Vorderseite anzufassen.

    **``opacity`` wäre die falsche Antwort gewesen** — eine durchscheinende
    Platte nähme dem Schatten seinen Grund, und von oben sähe sie falsch aus.

    Belegt wurde die Wirkung an Bildern aus einem eigenen Arbeitsbaum: Der
    Stand davor zeigte von unten nur die Platte, danach den Körper. Dieser Test
    hält fest, dass die Eigenschaft gesetzt **wird** — ein Bild kann er nicht
    ansehen, und eine Zahl daraus war untauglich (sie zählte die Achsenmarke).
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    plotter = _RecordingPlotter()
    viewport.plotter = plotter
    viewport.show_build_volume(profile)

    flaechen = [
        actor
        for actor, (_art, kwargs) in zip(plotter.actors, plotter.drawn, strict=False)
        if str(kwargs.get("name", "")).startswith("bed_surface_")
    ]
    assert flaechen, "keine Plattenfläche gezeichnet — dann prüft der Test nichts"
    for actor in flaechen:
        assert actor.prop.culling == "back", (
            f"die Rückseite der Plattenfläche bleibt stehen: {actor.prop.culling}"
        )


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


# --- Die Kamera auf einer Zeichenebene (§30.1, P1b) --------------------------
#
# ``view_on_plane`` liegt hinter der Wache und läuft offscreen nie. Die
# Rechnung davor tut es — genau die Aufteilung, für die es diese Datei gibt.


def test_the_camera_looks_along_the_normal_of_the_plane() -> None:
    """Sie sieht auf die Ebene, nicht an ihr vorbei.

    Der Blick geht von der Position zum Ursprung, und das muss die Gegenrichtung
    der Normalen sein. Ein Vorzeichenfehler drehte den Betrachter auf die
    Rückseite des Teils — sichtbar sofort, prüfbar nur hier.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import camera_for_plane

    frame = frame_of((1.0, 0.0, 1.0), (5.0, -2.0, 3.0))
    position, focus, up = camera_for_plane(frame, 40.0)

    assert focus == pytest.approx(frame.origin), "geschaut wird auf den Ursprung der Zeichnung"
    span = math.dist(position, frame.origin)
    assert span == pytest.approx(40.0), "die Entfernung ist die verlangte"
    towards = tuple((frame.origin[axis] - position[axis]) / span for axis in range(3))
    assert towards == pytest.approx(tuple(-value for value in frame.normal))
    assert up == pytest.approx(frame.y_axis), "oben ist die zweite Rahmenachse"


def test_sketching_on_xy_gives_the_same_camera_as_the_top_view() -> None:
    """Sonst kippt das Bild beim Betreten des Skizzenmodus.

    Die Draufsicht gibt es längst als feste Vorgabe. Wer auf der XY-Ebene zu
    zeichnen beginnt, sieht dasselbe — und wenn nicht, dreht sich das Teil
    beim Moduswechsel um einen Winkel, den niemand erklären kann. Die Zusage
    steht in ``frame_of`` („dieselbe Skizze liegt auf dem Tisch und auf dem
    Deckel gleich herum"); hier ist die Zahl dazu.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import VIEW_DIRECTIONS, camera_for_plane

    towards_top, up_top = VIEW_DIRECTIONS["top"]
    position, focus, up = camera_for_plane(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)), 1.0)

    assert position == pytest.approx(towards_top), "die Kamera steht, wo die Draufsicht steht"
    assert focus == pytest.approx((0.0, 0.0, 0.0))
    assert up == pytest.approx(up_top), "und sie hält den Kopf genauso"


def test_a_sketch_plane_without_a_plotter_changes_nothing(qt_app: QApplication) -> None:
    """Offscreen gibt es keine Kamera, und das darf nicht wehtun.

    Die halbe Suite läuft ohne Plotter (``_available`` steigt bei
    ``QT_QPA_PLATFORM=offscreen`` aus). Ein Skizzenmodus, der dort mit einer
    Ausnahme endet, nähme jeden Fenstertest mit.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport

    viewport = Viewport()
    assert viewport.plotter is None, "diese Probe ergibt nur ohne Plotter einen Sinn"
    viewport.view_on_plane(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)))


def test_the_distance_falls_back_when_the_camera_has_no_span(qt_app: QApplication) -> None:
    """Eine Entfernung von null nähme der Kamerastellung ihre Richtung.

    ``_plane_distance`` nimmt den bisherigen Abstand zum Blickpunkt, damit der
    Ausschnitt beim Schwenken erhalten bleibt. Steht die Kamera auf ihrem
    eigenen Blickpunkt — vor dem ersten Bild —, wäre die Position gleich dem
    Ursprung und die Blickrichtung unbestimmt.

    Zurück kommt seit dem 24.08.2026 die **Untergrenze** und nicht mehr 1,0:
    Ein Millimeter ist zwar von null verschieden und rettet die Richtung, aber
    aus einem Millimeter Abstand sieht man die Zeichenebene nicht. Der Test
    daneben misst, woran das aufgefallen ist.
    """
    from app.ui.viewport import LEAST_PLANE_DISTANCE, Viewport

    viewport = Viewport()
    viewport.plotter = _StillCamera()  # type: ignore[assignment]

    assert viewport._plane_distance() == pytest.approx(LEAST_PLANE_DISTANCE)


class _StillCamera:
    """Eine Attrappe, deren Kamera auf ihrem Blickpunkt sitzt."""

    class _Camera:
        position = (7.0, 7.0, 7.0)
        focal_point = (7.0, 7.0, 7.0)

    camera = _Camera()


# --- Das Raster einer Zeichenebene (§30.1, P2b) ------------------------------


def test_the_grid_lies_in_the_plane_it_belongs_to() -> None:
    """Ein Raster neben der Ebene behauptet den falschen Ort.

    Es sagt, wo die Zeichnung liegt und wie groß sie ist. Läge es daneben,
    wäre beides falsch — und auf einer geneigten Fläche fällt genau das
    auf, auf einer waagerechten nicht.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import sketch_grid

    frame = frame_of((1.0, 0.0, 1.0), (5.0, -2.0, 3.0))
    lines = sketch_grid(frame, step=5.0, reach=20.0)

    assert lines, "ein Raster mit Weite und Ausdehnung ist nicht leer"
    for start, end in lines:
        for point in (start, end):
            gap = tuple(point[axis] - frame.origin[axis] for axis in range(3))
            along = sum(gap[axis] * frame.normal[axis] for axis in range(3))
            assert along == pytest.approx(0.0, abs=1e-9), f"{point} liegt neben der Ebene"


def test_the_grid_counts_its_lines_from_width_and_step() -> None:
    """Zwei Richtungen, je eine Linie auf null und beidseits so viele wie
    hineinpassen — bei 20 mm Ausdehnung und 5 mm Weite also neun je Achse.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import sketch_grid

    lines = sketch_grid(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)), step=5.0, reach=20.0)

    assert len(lines) == 2 * (2 * 4 + 1), "vier je Seite, die Null, und das in zwei Richtungen"


def test_a_grid_without_a_step_is_empty_and_not_an_error() -> None:
    """Eine Weite von null ist kein Sonderfall, sondern kein Raster.

    Ohne diesen Zweig teilte ``reach / step`` durch null — und zwar in einer
    Zeichenfläche, die gerade aufgebaut wird.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import sketch_grid

    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    assert sketch_grid(frame, step=0.0, reach=20.0) == []
    assert sketch_grid(frame, step=5.0, reach=0.0) == []


def test_a_fine_grid_over_a_wide_plane_stops_at_the_limit() -> None:
    """Ein Millimeter Raster über einem Meter Ebene wären zweitausend Linien.

    Gezeichnet kämen sie als Fläche an, und gerechnet kosten sie. Die Grenze
    greift, statt die Ansicht zu füllen.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import MOST_GRID_LINES, sketch_grid

    lines = sketch_grid(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)), step=1.0, reach=1000.0)

    assert len(lines) == 2 * (2 * MOST_GRID_LINES + 1)


def test_on_the_flat_plane_the_grid_runs_along_the_axes() -> None:
    """Auf XY muss das Raster achsparallel liegen — sonst ist es schief.

    Die Probe dafür ist billig: Jede Linie hält entweder ihr x oder ihr y,
    und das dritte bleibt null.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import sketch_grid

    lines = sketch_grid(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 7.0)), step=10.0, reach=20.0)

    for start, end in lines:
        held_x = start[0] == pytest.approx(end[0])
        held_y = start[1] == pytest.approx(end[1])
        assert held_x != held_y, "eine Rasterlinie hält genau eine der beiden Achsen"
        assert start[2] == pytest.approx(7.0) and end[2] == pytest.approx(7.0)


def test_two_strokes_share_one_flat_line_list() -> None:
    """VTK erwartet je Linie erst ihre Länge, dann ihre Indizes.

    Zwei Strecken über vier Punkten sind ``[2, 0, 1, 2, 2, 3]``. Die dritte
    Zahl ist eine **Länge** und sieht aus wie ein Index — deshalb ist diese
    Rechnung eine eigene Funktion und nicht eine Zeile im Zeichnen.
    """
    from app.ui.viewport import polyline_spans

    assert polyline_spans([2]) == [2, 0, 1]
    assert polyline_spans([2, 2]) == [2, 0, 1, 2, 2, 3]
    assert polyline_spans([3, 2]) == [3, 0, 1, 2, 2, 3, 4]


def test_a_curve_with_one_point_is_skipped_but_still_counted() -> None:
    """Der Fall, an dem eine naive Fassung stillschweigend falsch wird.

    Ein einzelner Punkt hat keine Strecke und gehört nicht in die Linienliste
    — aber er liegt im Netz und **verschiebt die Indizes aller folgenden**.
    Wer ihn nur überspringt, ohne weiterzuzählen, zeichnet danach jede Linie
    einen Punkt zu früh.
    """
    from app.ui.viewport import polyline_spans

    assert polyline_spans([1, 2]) == [2, 1, 2], "die Strecke nutzt Punkt 1 und 2, nicht 0 und 1"
    assert polyline_spans([2, 1, 2]) == [2, 0, 1, 2, 3, 4]
    assert polyline_spans([1]) == []
    assert polyline_spans([]) == []


def test_showing_a_sketch_without_a_plotter_changes_nothing(qt_app: QApplication) -> None:
    """Offscreen gibt es keine Szene, und das darf nicht wehtun.

    ``show_sketch`` und ``clear_sketch`` laufen in jedem Fenstertest mit,
    sobald der Skizzenmodus angefasst wird. Eine Ausnahme hier nähme die
    halbe Suite mit.
    """
    from app.core.sketch.planes import frame_of
    from app.core.sketch.profile import SketchCurve
    from app.ui.viewport import Viewport

    viewport = Viewport()
    assert viewport.plotter is None, "diese Probe ergibt nur ohne Plotter einen Sinn"

    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    viewport.show_sketch(
        [SketchCurve(points=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)))], frame, 1.0, 20.0
    )
    viewport.clear_sketch()

    assert viewport._sketch_actors == [], "ohne Plotter entsteht kein Actor"


def test_the_camera_stands_in_front_of_the_front_view_not_behind_it() -> None:
    """Auf ``plane:xz`` zeigt die Normale nach hinten, die Kamera nicht.

    **Der Fall, den P1b nicht geprüft hat.** Dort war ``camera_for_plane``
    gegen Flächen-Rahmen und gegen ``plane:xy`` gemessen — die zwei Fälle, in
    denen Normale und Bildnormale zusammenfallen. Bei ``plane:xz`` fallen sie
    auseinander: Man zeichnet von vorn (−Y) und extrudiert nach hinten (+Y).
    Eine Kamera auf der Normalen stünde hinter der Zeichenebene, und die erste
    Achse liefe im Bild nach links — die Skizze wäre spiegelverkehrt.
    """
    from app.core.sketch.planes import frame_for_plane
    from app.ui.viewport import camera_for_plane

    frame = frame_for_plane("plane:xz")
    assert frame is not None
    position, focus, up = camera_for_plane(frame, 30.0)

    assert position == pytest.approx((0.0, -30.0, 0.0)), "von vorn, nicht von hinten"
    assert focus == pytest.approx((0.0, 0.0, 0.0))
    assert up == pytest.approx((0.0, 0.0, 1.0)), "Z zeigt im Bild nach oben"

    # Und die Probe, um die es geht: die erste Achse der Zeichnung läuft im
    # Bild nach rechts. Rechts ist das Kreuzprodukt aus Blickrichtung und Oben.
    towards = tuple(focus[axis] - position[axis] for axis in range(3))
    span = math.dist((0.0, 0.0, 0.0), towards)
    forward = tuple(value / span for value in towards)
    right = (
        forward[1] * up[2] - forward[2] * up[1],
        forward[2] * up[0] - forward[0] * up[2],
        forward[0] * up[1] - forward[1] * up[0],
    )
    assert right == pytest.approx(frame.x_axis), "die erste Achse liegt im Bild rechts"


def test_the_three_base_planes_all_show_their_first_axis_to_the_right() -> None:
    """Dieselbe Probe für alle drei — keine darf gespiegelt ankommen."""
    from app.core.sketch.planes import frame_for_plane
    from app.ui.viewport import camera_for_plane

    for plane in ("plane:xy", "plane:xz", "plane:yz"):
        frame = frame_for_plane(plane)
        assert frame is not None, plane
        position, focus, up = camera_for_plane(frame, 25.0)
        towards = tuple(focus[axis] - position[axis] for axis in range(3))
        span = math.dist((0.0, 0.0, 0.0), towards)
        forward = tuple(value / span for value in towards)
        right = (
            forward[1] * up[2] - forward[2] * up[1],
            forward[2] * up[0] - forward[0] * up[2],
            forward[0] * up[1] - forward[1] * up[0],
        )
        assert right == pytest.approx(frame.x_axis), f"{plane} kommt gespiegelt an"


def test_the_grid_follows_the_camera_and_not_the_hidden_drawing_area() -> None:
    """Zwei Maßstäbe, und nur einer stimmt im Viewport.

    Die Zeichenfläche ist im Skizzenmodus unsichtbar; ihr Maßstab steht auf
    dem Startwert, weil dort niemand mehr zoomt. Gemessen kam damit ein
    Raster von 20 mm heraus, während auf 1 mm gefangen wurde — zwei Zahlen
    für dieselbe Sache, und die sichtbare war die falsche.
    """
    from app.ui.sketch_editor import GRID_STEPS, MIN_GRID_PX, grid_step_for

    for scale in (0.5, 1.2, 7.5, 23.0, 100.0):
        step = grid_step_for(scale)
        assert step in GRID_STEPS, f"{scale}: {step} ist keine Stufe der Folge"
        feiner = [one for one in GRID_STEPS if one < step]
        if feiner:
            assert feiner[-1] * scale < MIN_GRID_PX, (
                f"{scale}: eine feinere Stufe hätte auch noch gepasst"
            )

    # Und die Richtung: näher heran heißt feiner, nicht gröber.
    assert grid_step_for(23.0) < grid_step_for(1.2)


def test_the_camera_keeps_its_distance_from_an_empty_scene(qt_app: QApplication) -> None:
    """Ohne Modell hat ``reset_camera`` nie stattgefunden.

    pyvista startet dann mit einer Kamera 1,62 Einheiten vor dem Ursprung.
    Diesen Abstand treu zu übernehmen hieße, aus 1,6 Millimetern auf die
    Zeichenebene zu sehen — gemessen 918 Bildpunkte je Millimeter und ein
    Raster von 0,1 mm.

    Getroffen hätte es ausgerechnet **Weg 2**, neu konstruieren: Nur dort ist
    die Szene leer, wenn der Skizzenmodus beginnt.
    """
    from app.core.units import EPS_GEOM
    from app.ui.viewport import LEAST_PLANE_DISTANCE, Viewport

    # Genau die Stellung, mit der pyvista einen leeren Plotter aufmacht.
    class _FreshPlotter:
        class _Camera:
            position = (1.0, -1.0, 0.8)
            focal_point = (0.0, 0.0, 0.0)

        camera = _Camera()

    viewport = Viewport()
    viewport.plotter = _FreshPlotter()  # type: ignore[assignment]

    span = math.dist(_FreshPlotter._Camera.position, _FreshPlotter._Camera.focal_point)
    assert span == pytest.approx(1.6248, abs=1e-3), "die gemessene Startstellung"
    assert span > EPS_GEOM, "sie ist nicht null — die alte Untergrenze hätte sie durchgelassen"

    assert viewport._plane_distance() == pytest.approx(LEAST_PLANE_DISTANCE)
    assert LEAST_PLANE_DISTANCE > 100.0, "unter hundert Millimetern sieht man kein Druckteil"


def test_without_a_plotter_the_scale_falls_back_instead_of_dividing_by_zero(
    qt_app: QApplication,
) -> None:
    """Ohne Bild gibt es nichts zu messen, und null wäre die falsche Antwort."""
    from app.core.sketch.planes import frame_for_plane
    from app.ui.viewport import FALLBACK_SCALE, Viewport

    frame = frame_for_plane("plane:xy")
    assert frame is not None
    viewport = Viewport()
    assert viewport.pixels_per_mm(frame) == pytest.approx(FALLBACK_SCALE)


def test_the_bed_floor_steps_aside_but_its_edges_stay(qt_app: QApplication) -> None:
    """Zwei Gitter übereinander sind eines zu viel — eine Grenze ist kein Gitter.

    Bettraster und Zeichenraster sind beide graue Linien in derselben
    Größenordnung; bei einer Skizze auf ``plane:xy`` liegen sie exakt
    ineinander, und welches die Ebene ist, auf der gerade gezeichnet wird,
    sähe man nicht mehr. Der Boden tritt deshalb ab.

    **Die Bauraumkanten und die Maßskala gehen nicht mit**, und das ist der
    Unterschied, der beim ersten Anlauf verlorenging: Das Handbuch verspricht
    genau sie — „wer darüber hinauszeichnet, liest es an derselben Linie" —,
    und beim Zeichnen ist das die früheste Stelle, an der auffällt, dass ein
    Teil nicht auf das Bett passt. Sie mit auszublenden nimmt dem Kunden die
    Auskunft dort, wo sie am meisten wert ist.

    Offscreen gibt es keine Actors (Entscheidung G), also stehen hier
    Attrappen mit der einen Methode, die benutzt wird.
    """
    from app.core.sketch.planes import frame_for_plane
    from app.ui.viewport import Viewport

    class _Actor:
        def __init__(self, name: str) -> None:
            self.name = name
            self.visible = True

        def SetVisibility(self, on: bool) -> None:  # noqa: N802 - VTKs Name
            self.visible = bool(on)

    surface, grid = _Actor("Fläche"), _Actor("Raster")
    edges, scale = _Actor("Kanten"), _Actor("Skala")

    viewport = Viewport()
    viewport._frame_actors = [surface, grid, edges, scale]
    viewport._ground_actors = [surface, grid]

    frame = frame_for_plane("plane:xy")
    assert frame is not None
    viewport.set_sketching(frame)
    assert not surface.visible and not grid.visible, "der Boden tritt ab"
    assert edges.visible and scale.visible, (
        "die Grenze bleibt — sonst sieht niemand mehr, wo das Bett endet"
    )

    viewport.set_sketching(None)
    assert all(actor.visible for actor in (surface, grid, edges, scale)), (
        "nach dem Modus steht der Bauraum wieder vollständig da"
    )

    # Und die Bodenliste ist eine **Teilmenge**, keine zweite Sammlung: Wer sie
    # getrennt füllt, hat beim nächsten Bauraum einen Actor, den niemand mehr
    # aufräumt.
    assert {id(a) for a in viewport._ground_actors} <= {id(a) for a in viewport._frame_actors}, (
        "jeder Boden-Actor hängt auch in der Liste, die aufgeräumt wird"
    )
