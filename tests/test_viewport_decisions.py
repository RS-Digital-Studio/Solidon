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
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

import pytest

pytest.importorskip("PySide6")

import numpy as np
import trimesh
from PySide6.QtWidgets import QApplication

from app.core.geom.measure import SnapResult
from app.core.geom.mesh import MeshData
from app.core.types import Profile
from app.ui.theme import THEMES, viewport_colours
from app.ui.viewport import PLATE_GAP

# --- vor der Wache: was ohne VTK prüfbar ist ------------------------------------


@pytest.fixture(autouse=True)
def _release_each_view_before_the_next() -> Iterator[None]:
    """Räumt nach jedem Test auf, damit sich keine Ansichten anhäufen.

    **Ohne diese Fixture hängt die ganze Datei an der Größe eines Viewports.**
    Gemessen am 03.09.2026: Zwei zusätzliche Instanzattribute — zwei leere
    Wörterbücher, sonst nichts — ließen den Lauf bei Test 29 von 148 mit
    ``0xC0000374`` abbrechen, einer Heap-Beschädigung. Eines allein lief
    durch, zwei nicht:

        HEAD + 1 belangloses Attribut     142 passed
        HEAD + 2 belanglose Attribute     Riss bei 28 Fortschrittszeichen
        HEAD + 310 Kommentarzeilen        142 passed

    Die Zeile, die es auslöste, war also nie die Ursache — fünf Einzelproben
    an meinem eigenen Code blieben deshalb alle rot und schlossen nichts aus.
    Was wirklich geschieht: Die Tests erzeugen ihre Ansichten lokal und geben
    sie nie frei. Sie sammeln sich an, bis
    ``test_the_camera_watcher_holds_the_view_only_weakly`` ein ``gc.collect``
    ruft und sie **alle auf einmal** sterben — dabei reißt VTK. Werden die
    Objekte größer, reißt es früher.

    Ein Sammellauf nach jedem Test löst sie einzeln auf, und die Datei läuft
    wieder ganz durch. Das kostet den Lauf 2,3 → 8,7 Sekunden, und das ist
    der Preis dafür, dass die nächste Sitzung ein Feld hinzufügen darf, ohne
    eine Woche zu suchen.

    **Das ist keine Tarnung eines echten Fehlers.** In der Anwendung gibt es
    einen Viewport und nicht hundertachtundvierzig; die Anhäufung entsteht
    erst im Testlauf. Was sie deckt, ist ein bekannter Riss beim Abbau
    (`ROADMAP.md`), und der wird davon nicht besser oder schlechter — nur
    verteilt statt gebündelt.
    """
    import gc

    yield
    gc.collect()


def test_the_effective_qt_platform_keeps_vtk_out_after_the_environment_changes(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Plattform steht beim ``QApplication``-Aufbau fest, nicht danach.

    ``tools.make_manual.main`` entfernt ``QT_QPA_PLATFORM``, wenn es als
    Werkzeug läuft. Ein Test ruft diesen Einstieg im selben Prozess auf. Qt
    bleibt dabei offscreen; nur die Umgebungsvariable ist fort. Wer allein sie
    fragt, baut danach einen echten VTK-Interactor ohne passenden Qt-Kontext
    und der nächste Fensteraufbau stirbt nativ statt mit einem Testfehler.
    """
    from app.ui import viewport

    assert qt_app.platformName() == "offscreen"
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)

    assert not viewport._available()


def test_x11_is_chosen_wherever_the_3d_view_can_have_it() -> None:
    """Qt 6 nimmt in einer Wayland-Sitzung von sich aus Wayland, und dort hat
    VTK kein Fenster (Martin Donecker, CachyOS, 28.08.2026).

    Die Weiche ist eine reine Funktion mit der Plattform als Parameter, weil
    der Zweig nur in einer Wayland-Sitzung zündet — und die sieht weder diese
    Windows-Maschine noch die Linux-CI unter Xvfb. Vier Lagen: Wayland mit
    Xwayland → X11; Wayland ohne Xwayland → nichts zu wählen, die Ansicht sagt
    es; ein Werkzeug oder Test, das offscreen will → bleibt; andere Systeme →
    nichts. Und ein global gesetztes ``wayland`` gilt allen Qt-Programmen,
    nicht diesem — es wird ersetzt, der Bericht sagt es.
    """
    from app.ui.qt_platform import qpa_platform

    wayland_with_xwayland = {
        "DISPLAY": ":1",
        "WAYLAND_DISPLAY": "wayland-0",
        "XDG_SESSION_TYPE": "wayland",
    }
    # X11 zuerst — und Wayland dahinter, damit ein Ubuntu ohne libxcb-cursor0
    # ohne 3D-Ansicht startet statt gar nicht (Qt geht die Liste durch).
    assert qpa_platform("linux", wayland_with_xwayland) == "xcb;wayland"
    assert qpa_platform("linux", {"DISPLAY": ":1", "XDG_SESSION_TYPE": "wayland"}) == "xcb;wayland"
    assert (
        qpa_platform("linux", {**wayland_with_xwayland, "QT_QPA_PLATFORM": "wayland"})
        == "xcb;wayland"
    )
    assert (
        qpa_platform("linux", {"DISPLAY": ":0", "QT_QPA_PLATFORM": "wayland;xcb"}) == "xcb;wayland"
    )
    assert (
        qpa_platform("linux", {"DISPLAY": ":0", "QT_QPA_PLATFORM": "Wayland-EGL"}) == "xcb;wayland"
    )
    assert qpa_platform("linux", {"DISPLAY": ":0"}) == "xcb", (
        "eine reine X11-Sitzung hat kein Wayland, hinter das sie fallen könnte"
    )

    assert qpa_platform("linux", {"WAYLAND_DISPLAY": "wayland-0"}) is None, "ohne Xwayland"
    assert qpa_platform("linux", {"DISPLAY": "  ", "XDG_SESSION_TYPE": "wayland"}) is None
    for tool_platform in ("offscreen", "minimal", "vnc", "xcb", "eglfs"):
        assert qpa_platform("linux", {"DISPLAY": ":0", "QT_QPA_PLATFORM": tool_platform}) is None
    assert qpa_platform("win32", {"DISPLAY": ":0", "XDG_SESSION_TYPE": "wayland"}) is None
    assert qpa_platform("darwin", {"DISPLAY": ":0"}) is None


def test_the_choice_lands_in_the_environment_and_remembers_what_stood_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gesetzt wird einmal, und der Vorwert bleibt für den Fehlerbericht."""
    import os

    from app.core.report import QT_PLATFORM_BEFORE_VARIABLE, QT_PLATFORM_UNSET
    from app.ui import qt_platform

    monkeypatch.setattr(qt_platform.sys, "platform", "linux")
    for key in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("QT_QPA_PLATFORM", "wayland")
    monkeypatch.delenv(QT_PLATFORM_BEFORE_VARIABLE, raising=False)

    assert qt_platform.prefer_x11_for_the_viewport() == "xcb;wayland"
    assert os.environ["QT_QPA_PLATFORM"] == "xcb;wayland"
    assert os.environ[QT_PLATFORM_BEFORE_VARIABLE] == "wayland"
    # Ein zweiter Aufruf — ``main`` und ``build_application`` rufen beide —
    # findet die eigene Wahl vor und lässt den gemerkten Vorwert stehen.
    assert qt_platform.prefer_x11_for_the_viewport() is None
    assert os.environ[QT_PLATFORM_BEFORE_VARIABLE] == "wayland"

    monkeypatch.delenv("QT_QPA_PLATFORM")
    monkeypatch.delenv(QT_PLATFORM_BEFORE_VARIABLE)
    assert qt_platform.prefer_x11_for_the_viewport() == "xcb"
    assert os.environ[QT_PLATFORM_BEFORE_VARIABLE] == QT_PLATFORM_UNSET, (
        "vorher nichts — und das steht dann auch da, nicht eine leere Variable"
    )

    monkeypatch.setattr(qt_platform.sys, "platform", "win32")
    monkeypatch.delenv("QT_QPA_PLATFORM")
    monkeypatch.delenv(QT_PLATFORM_BEFORE_VARIABLE)
    assert qt_platform.prefer_x11_for_the_viewport() is None
    assert "QT_QPA_PLATFORM" not in os.environ
    assert QT_PLATFORM_BEFORE_VARIABLE not in os.environ


def test_a_wayland_session_keeps_vtk_out_and_says_what_to_do(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auf Wayland stirbt VTK nativ; die Wache greift davor, und die Ansicht
    nennt den Weg heraus (§2.7) statt nur zu fehlen."""
    from app.ui import viewport

    monkeypatch.setattr(viewport, "_effective_platform", lambda: "wayland")
    monkeypatch.delenv("DISPLAY", raising=False)
    assert not viewport._available()
    hint = viewport.unavailable_hint()
    assert "X11" in hint and "Xwayland" in hint, hint

    # Mit DISPLAY stand X11 an erster Stelle — landet Qt trotzdem auf Wayland,
    # ließ sich das X11-Plugin nicht laden, und das heißt fast immer
    # libxcb-cursor0. Der Hinweis nennt sie, nicht Xwayland.
    monkeypatch.setenv("DISPLAY", ":0")
    hint = viewport.unavailable_hint()
    assert "libxcb-cursor0" in hint and "Xwayland" not in hint, hint

    monkeypatch.setattr(viewport, "_effective_platform", lambda: "wayland-egl")
    assert not viewport._available()

    monkeypatch.setattr(viewport, "_effective_platform", lambda: "offscreen")
    assert viewport.unavailable_hint() == "", "wo es nichts zu tun gibt, steht auch nichts"


def test_plotter_release_is_idempotent(qt_app: QApplication) -> None:
    """Der native Renderer wird genau einmal und über eine Besitzstelle gelöst."""
    from app.ui.viewport import Viewport

    class _Plotter:
        def __init__(self) -> None:
            self.close_calls = 0

        def close(self) -> None:
            self.close_calls += 1

    viewport = Viewport()
    plotter = _Plotter()
    viewport.plotter = plotter

    viewport.release_plotter()
    viewport.release_plotter()

    assert plotter.close_calls == 1
    assert viewport.plotter is None


def test_failed_plotter_release_is_not_retried(qt_app: QApplication) -> None:
    """Ein nativer Treiberfehler hält weder Qt offen noch den Besitzer fest."""
    from app.ui.viewport import Viewport

    class _FailingPlotter:
        def __init__(self) -> None:
            self.close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            raise RuntimeError("native close failed")

    viewport = Viewport()
    plotter = _FailingPlotter()
    viewport.plotter = plotter

    viewport.release_plotter()
    viewport.release_plotter()

    assert plotter.close_calls == 1
    assert viewport.plotter is None


def test_imported_colours_reach_the_viewport_as_rgb_cells(qt_app: QApplication) -> None:
    """Eine Farbe aus OBJ/PLY/GLB wird gezeichnet, nicht nur gespeichert (§20)."""
    from app.ui.viewport import Viewport

    body = trimesh.creation.box(extents=(20.0, 16.0, 12.0))
    body.visual.face_colors = np.tile([24, 140, 220, 255], (len(body.faces), 1))
    mesh = MeshData.of(body)
    surface = SimpleNamespace(cell_data={})
    viewport = Viewport()

    options = viewport._slot_colours(
        surface, mesh, SimpleNamespace(material_slots=[]), mesh.triangle_count
    )

    assert options == {"scalars": "source_colour", "rgb": True, "show_scalar_bar": False}
    assert np.all(surface.cell_data["source_colour"] == [24, 140, 220])


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


def test_a_rebuilt_scene_forgets_a_feature_that_no_longer_exists(
    qt_app: QApplication,
) -> None:
    """Nach einer Änderung fällt die Auswahl auf den bleibenden Körper zurück."""
    import dataclasses

    from app.ui.viewport import Viewport

    before = _scene_with_two_holes()
    viewport = Viewport()
    viewport.show_scene(before)
    viewport.select("obj_1")
    viewport.select_feature("hole_2")

    old = before.scene.objects["obj_1"]
    after = dataclasses.replace(
        before,
        scene=dataclasses.replace(
            before.scene,
            objects={
                "obj_1": dataclasses.replace(
                    old,
                    features={"hole_1": old.features["hole_1"]},
                )
            },
        ),
    )
    viewport.show_scene(after)

    assert viewport.selected_feature is None, "das entfernte Merkmal blieb intern gewählt"
    assert viewport.highlighted_object() == "obj_1", "der bleibende Körper übernimmt die Auswahl"


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
        self.camera = SimpleNamespace(
            position=(100.0, -100.0, 80.0),
            focal_point=(0.0, 0.0, 0.0),
            parallel_scale=50.0,
        )
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


@pytest.mark.parametrize("filtered", ["hidden", "other_plate"])
def test_an_invisible_feature_leaves_no_floating_marking(
    filtered: str,
    qt_app: QApplication,
) -> None:
    """Ausgeblendet heißt auch: keine Fläche und kein Etikett ohne Körper."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.show_scene(_with_faces(_scene_with_two_holes(), "hole_2", (0, 1)))
    viewport._selected = "obj_1"
    viewport._selected_feature = "hole_2"
    if filtered == "hidden":
        viewport._hidden = frozenset({"obj_1"})
    else:
        viewport._plate = 1
    plotter = _RecordingPlotter()
    viewport.plotter = plotter

    viewport._redraw_features()

    assert viewport.highlighted_object() is None
    assert viewport.highlighted_faces() == ()
    assert "feature-patch" not in plotter.names()
    assert not plotter.labelled, "ohne Körper darf kein Merkmalsname im Raum schweben"


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
    from app.ui.viewport import SELECTED_HOLE_OPACITY

    assert flaeche[0].get("opacity") == SELECTED_HOLE_OPACITY, (
        "eine deckende Bohrungswand schließt die Öffnung optisch wie ein Deckel"
    )
    assert flaeche[0]["backface_params"]["opacity"] == SELECTED_HOLE_OPACITY, (
        "die Innenwand muss von beiden Öffnungen gleich durchscheinend bleiben"
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


def test_a_solid_feature_stays_opaque_while_only_hover_is_translucent(
    qt_app: QApplication,
) -> None:
    """Der Durchblick ist eine Bohrungsregel, keine blasse Gesamtauswahl."""
    import dataclasses

    from app.ui.viewport import HOVERED_FEATURE_OPACITY, Viewport

    result = _with_faces(_scene_with_two_holes(), "hole_2", (0, 1))
    entry = result.scene.objects["obj_1"]
    face = dataclasses.replace(entry.features["hole_2"], kind="face")
    result.scene.objects["obj_1"] = dataclasses.replace(
        entry,
        features={**entry.features, "hole_2": face},
    )
    viewport = Viewport()
    viewport.show_scene(result)
    viewport._selected = "obj_1"
    viewport._selected_feature = "hole_2"
    plotter = _RecordingPlotter()
    viewport.plotter = plotter

    viewport._redraw_features()

    selected = next(
        kwargs for _kind, kwargs in plotter.drawn if kwargs.get("name") == "feature-patch"
    )
    assert "opacity" not in selected, "eine feste Fläche bleibt als Auswahl kräftig und deckend"

    plotter.drawn.clear()
    plotter.labelled.clear()
    viewport._selected_feature = None
    viewport._hover_feature = True
    viewport._hovered_object = "obj_1"
    viewport._hovered_feature = "hole_2"
    viewport._redraw_features()

    hovered = next(
        kwargs for _kind, kwargs in plotter.drawn if kwargs.get("name") == "feature-hover"
    )
    assert hovered["opacity"] == HOVERED_FEATURE_OPACITY


def test_hover_and_selection_are_two_visible_states(qt_app: QApplication) -> None:
    """§18.5 unterscheidet Überfahren von Anklicken, nicht nur im Zeiger.

    Hover ist durchscheinend in der Merkmalsfarbe; die Auswahl ist deckend in
    Bernstein. Ohne den eigenen Hover-Actor änderte sich beim Überfahren nur
    der Mauszeiger, obwohl der Bauplan das Merkmal selbst hervorhebt.
    """
    from app.ui.viewport import FEATURE_LABEL_COLOUR, HOVERED_HOLE_OPACITY, Viewport

    viewport = Viewport()
    viewport.show_scene(_with_faces(_scene_with_two_holes(), "hole_2", (0, 1)))
    viewport._selected = "obj_1"
    viewport._hover_feature = True
    viewport._hovered_object = "obj_1"
    viewport._hovered_feature = "hole_2"
    plotter = _RecordingPlotter()
    viewport.plotter = plotter

    viewport._redraw_features()

    hover = [kwargs for kind, kwargs in plotter.drawn if kwargs.get("name") == "feature-hover"]
    assert len(hover) == 1
    assert str(hover[0]["color"]) == FEATURE_LABEL_COLOUR
    assert hover[0]["opacity"] == HOVERED_HOLE_OPACITY
    assert "feature-patch" not in plotter.names(), "überfahren ist noch keine Auswahl"
    labels = [text for group in plotter.labelled for text in group]
    assert len(labels) == 1 and "8" in labels[0], (
        "auch ohne dauerhafte Überlagerung sagt die Hervorhebung, welches Merkmal sie meint"
    )

    viewport._selected_feature = "hole_2"
    plotter.drawn.clear()
    plotter.labelled.clear()
    viewport._redraw_features()

    assert "feature-patch" in plotter.names()
    assert "feature-hover" not in plotter.names(), (
        "die deckende Auswahl ersetzt Hover, statt zwei Flächen übereinanderzulegen"
    )


def test_difference_colours_take_priority_over_selection(qt_app: QApplication) -> None:
    """Vorschau-Orange und Auswahl-Bernstein dürfen sich nicht vermischen.

    Die Auswahl bleibt semantisch erhalten; nur ihre Modellfarbe weicht,
    solange die Differenz sichtbar ist. Beim gehaltenen Vorher-Vergleich kommt
    sie zurück, weil dort keine Vorschaufarbe mehr erklärt werden muss.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.show_scene(_with_faces(_scene_with_two_holes(), "hole_2", (0, 1)))
    viewport.select("obj_1")
    viewport.select_feature("hole_2")
    assert viewport.highlighted_faces() == (0, 1)

    difference = object()
    viewport.show_difference(difference)

    assert viewport.selected_feature == "hole_2", "die Auswahl selbst bleibt bestehen"
    assert viewport.highlighted_faces() == (), "die Vorschau besitzt jetzt die Modellfarben"
    assert viewport.highlighted_object() is None

    viewport.hold_before(True)
    assert viewport.highlighted_faces() == (0, 1), "im Vorher-Bild kehrt die Auswahl zurück"

    viewport.hold_before(False)
    assert viewport.highlighted_faces() == ()
    viewport.show_difference(None)
    assert viewport.highlighted_faces() == (0, 1), "nach der Vorschau ist die Auswahl wieder da"


def test_difference_colours_also_replace_a_whole_body_highlight(
    qt_app: QApplication,
) -> None:
    """Dasselbe gilt eine Stufe höher für die Körperauswahl."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.show_scene(_scene_with_two_holes())
    viewport.select("obj_1")
    assert viewport.highlighted_object() == "obj_1"

    viewport.show_difference(object())
    assert viewport.highlighted_object() is None

    viewport.hold_before(True)
    assert viewport.highlighted_object() == "obj_1"


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
        ratio = 1.0

        @staticmethod
        def height() -> int:
            return 600

        @classmethod
        def devicePixelRatioF(cls) -> float:  # noqa: N802 — Qt-Name
            return cls.ratio

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

    # **Und in Gerätepunkten, nicht in Logikpunkten** (Gesamtreview J-5):
    # pyvistas ``rwi`` multipliziert jede Mausposition mit dem
    # ``devicePixelRatio``, bevor sie an VTK geht — die Zeigersuche muss
    # dieselbe Rechnung machen, sonst fragt sie auf einem skalierten
    # Bildschirm die falsche Stelle. Höhe 600 Logikpunkte sind bei 1,5 dann
    # 900 Gerätepunkte.
    _Interactor.ratio = 1.5
    viewport._note_pointer(_Punkt(120, 100))
    assert viewport._hover_at == (180, 750), (
        f"bei dpr 1,5 zählt VTK in Gerätepunkten: {viewport._hover_at} statt (180, 750)"
    )


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


def test_the_camera_watcher_holds_the_view_only_weakly(
    qt_app: QApplication, unpinned_windows: None
) -> None:
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


def test_a_released_view_is_actually_released(qt_app: QApplication, unpinned_windows: None) -> None:
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


def test_a_callback_after_the_view_is_gone_stays_quiet(
    qt_app: QApplication, unpinned_windows: None
) -> None:
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


def test_the_sketch_grid_separates_fine_lines_landmarks_and_axes() -> None:
    """Ein gleichförmiges Netz ist eine Tapete, kein lesbarer Maßstab."""
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import sketch_grid, sketch_grid_layers

    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    layers = sketch_grid_layers(frame, step=5.0, reach=30.0)

    assert len(layers.axes) == 2, "der Ursprung trägt eine Linie je Achse"
    assert len(layers.major) == 4, "bei jedem fünften Schritt liegt eine Leitlinie"
    assert len(layers.minor) + len(layers.major) + len(layers.axes) == len(
        sketch_grid(frame, step=5.0, reach=30.0)
    )


def test_the_sketch_focus_moves_to_the_centre_above_the_toolbar() -> None:
    """Eine untere Karte von 400 px lässt die freie Bildmitte 200 px höher liegen."""
    from app.ui.viewport import occluded_view_shift

    # 200 mm sichtbare Höhe bei 1000 px: 0,2 mm/px. Die nötigen 200 px
    # Bildverschiebung entsprechen daher 40 mm Weltmaß.
    assert occluded_view_shift(100.0, 1000, 400) == pytest.approx(40.0)
    assert occluded_view_shift(100.0, 1000, -400) == pytest.approx(-40.0)


def test_the_sketch_focus_tracks_zoom_and_is_removed_exactly(
    qt_app: QApplication,
) -> None:
    """Die Pixelhöhe der Karte bleibt gleich, ihr Weltmaß nach Zoom nicht."""
    from app.ui.viewport import Viewport

    camera = SimpleNamespace(parallel_projection=True, parallel_scale=100.0)
    plotter = SimpleNamespace(
        camera=camera,
        camera_position=[
            (0.0, 0.0, 10.0),
            (0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
    )
    viewport = Viewport()
    viewport.resize(1000, 1000)
    viewport.plotter = plotter
    viewport._zone_margins = (0, 0, 400)

    assert viewport._apply_sketch_occlusion()
    assert plotter.camera_position[1] == pytest.approx((0.0, -40.0, 0.0))

    camera.parallel_scale = 50.0
    assert viewport._apply_sketch_occlusion()
    assert plotter.camera_position[1] == pytest.approx((0.0, -20.0, 0.0))

    assert viewport._remove_sketch_occlusion()
    assert plotter.camera_position[1] == pytest.approx((0.0, 0.0, 0.0))


def test_an_absolute_view_change_replaces_the_saved_sketch_shift(
    qt_app: QApplication,
) -> None:
    """Die ViewBar darf keinen Versatz einer überschriebenen Kamera abziehen."""
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport

    camera = SimpleNamespace(parallel_projection=True, parallel_scale=100.0)
    plotter = SimpleNamespace(
        camera=camera,
        camera_position=[
            (0.0, -40.0, 10.0),
            (0.0, -40.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
    )
    viewport = Viewport()
    viewport.resize(1000, 1000)
    viewport.plotter = plotter
    viewport._sketch_frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    viewport._zone_margins = (0, 0, 400)
    viewport._sketch_occlusion_shift = (0.0, -40.0, 0.0)
    settled: list[bool] = []
    viewport.reset_camera = lambda: None
    viewport._settle_sketch_view = lambda: settled.append(True)  # type: ignore[method-assign]
    viewport._redraw_shadows = lambda: None

    viewport.view_from("right")

    assert plotter.camera_position[1] == pytest.approx((0.0, 0.0, -40.0))
    assert viewport._sketch_occlusion_shift == pytest.approx((0.0, 0.0, -40.0))
    assert settled == [True], "die ViewBar meldet die neue Skizzenansicht ans Ebenenfeld"


def test_the_sketch_cards_have_parseable_theme_styles(qt_app: QApplication) -> None:
    """Die modernen Karten dürfen nicht auf Qts ungestylten Rückfall fallen."""
    from app.ui.viewport import SketchActionBadge, SketchPlanePicker, SketchSelectionBadge

    cards = (SketchPlanePicker(), SketchSelectionBadge(), SketchActionBadge())

    for card in cards:
        assert "}}" not in card.styleSheet(), card.styleSheet()


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


def test_a_body_in_pieces_casts_one_shadow_per_piece(qt_app: QApplication) -> None:
    """Ein Körper ist nicht immer ein Stück — und der Schatten weiß es jetzt.

    Der Kontaktschatten ist die konvexe Hülle des Körpers. Über ein Stück ist
    das richtig und billig: Ein Ansichtswechsel kostet dann nur die Projektion
    statt einer Triangulierung über jeden Punkt des Anzeigenetzes. Über
    **drei** Stücke spannt dieselbe Hülle über die Luft dazwischen und wirft
    den Schatten eines Dings, das es nicht gibt.

    Der Fall ist keiner aus dem Lehrbuch: Ein Baustein auf einem zu schmalen
    Träger hinterlässt genau das — den Träger und zwei Haken daneben (Befund
    Robert, 25.08.2026, am Bildschirm gesehen, bevor der Prüfbericht es sagte).
    """
    import numpy as np
    import pyvista as pv

    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        one = pv.Cube(center=(0.0, 0.0, 0.0), x_length=10, y_length=10, z_length=10)
        assert len(viewport._shadow_hulls_of(one.triangulate())) == 1, (
            "ein einteiliger Körper wirft einen Schatten — wie vorher"
        )

        far = pv.Cube(center=(40.0, 0.0, 0.0), x_length=4, y_length=4, z_length=4)
        farther = pv.Cube(center=(-40.0, 0.0, 0.0), x_length=4, y_length=4, z_length=4)
        apart = (one + far + farther).triangulate()

        hulls = viewport._shadow_hulls_of(apart)

        assert len(hulls) == 3, f"drei Stücke, drei Hüllen — gefunden: {len(hulls)}"
        # Und keine davon reicht über den Zwischenraum: Die breiteste Hülle ist
        # der Würfel selbst, nicht die Spanne über alle drei.
        widest = max(
            float(np.asarray(hull)[:, 0].max() - np.asarray(hull)[:, 0].min()) for hull in hulls
        )
        assert widest < 20.0, (
            f"eine Hülle spannt über {widest:.1f} mm — das ist der Abstand, nicht ein Stück"
        )
    finally:
        viewport.deleteLater()


# --- Der Drehpunkt beim Drehbeginn (§2.9) ------------------------------------


def test_the_rotation_focus_moves_in_depth_but_never_sideways() -> None:
    """Der Fokus bekommt die Tiefe der Körper, ohne das Bild zu ändern.

    Nach einem weiten Verschieben drehte die Kamera um den alten Punkt: Beim
    Aufbau wurde der Fokus nicht mehr nachgeführt, weil das Nachrücken das
    Bild springen ließ (Robert, 23.08.2026: „kamera bei aktueller position
    dann immer lassen"). Beim Drehbeginn gesetzt, muss der neue Fokus deshalb
    **auf dem Sichtstrahl** liegen — jede seitliche Bewegung wäre genau der
    Sprung, den diese Anweisung verbietet, nur eine Geste später.
    """
    from app.ui.viewport import rotation_focus

    position = (0.0, -10.0, 0.0)
    focus = (0.0, 0.0, 0.0)
    # Ein Körper, weit zur Seite geschoben — und tiefer im Bild.
    centre = (30.0, 10.0, 4.0)

    target = rotation_focus(position, focus, centre)

    assert target is not None
    assert target[0] == pytest.approx(0.0), "keine seitliche Bewegung"
    assert target[2] == pytest.approx(0.0), "auch nicht nach oben"
    assert target[1] == pytest.approx(10.0), "die Tiefe der Körpermitte entlang des Strahls"


def test_a_centre_behind_the_camera_leaves_the_focus_alone() -> None:
    """Hinter der Kamera gibt es nichts anzusehen — der Drehpunkt bleibt."""
    from app.ui.viewport import rotation_focus

    assert rotation_focus((0.0, -10.0, 0.0), (0.0, 0.0, 0.0), (0.0, -30.0, 0.0)) is None


def test_a_fitting_focus_stays_and_a_dead_camera_cannot_aim() -> None:
    """Nichts zu tun und nichts zu wissen sind beide kein Grund zu setzen."""
    from app.ui.viewport import rotation_focus

    # Die Körpermitte liegt seitlich auf Fokustiefe — der Fokus stimmt schon.
    assert rotation_focus((0.0, -10.0, 0.0), (0.0, 0.0, 0.0), (5.0, 0.0, 3.0)) is None
    # Kamera auf ihrem Blickpunkt: keine Richtung, aus der sich rechnen ließe.
    assert rotation_focus((7.0, 7.0, 7.0), (7.0, 7.0, 7.0), (0.0, 0.0, 0.0)) is None


class _AimedCamera:
    """Eine Attrappe mit den vier Methoden, die ``_aim_rotation`` benutzt."""

    def __init__(self) -> None:
        self.set_to: tuple[float, ...] | None = None

    def GetPosition(self) -> tuple[float, float, float]:  # noqa: N802 — VTK-Name
        return (0.0, -10.0, 0.0)

    def GetFocalPoint(self) -> tuple[float, float, float]:  # noqa: N802 — VTK-Name
        return (0.0, 0.0, 0.0)

    def SetFocalPoint(self, *point: float) -> None:  # noqa: N802 — VTK-Name
        self.set_to = point


class _AimedPlotter:
    """Renderer und Kamera, mehr braucht der Drehbeginn nicht."""

    class _Renderer:
        def __init__(self, camera: _AimedCamera) -> None:
            self._camera = camera
            self.clipped = False

        def GetActiveCamera(self) -> _AimedCamera:  # noqa: N802 — VTK-Name
            return self._camera

        def ResetCameraClippingRange(self) -> None:  # noqa: N802 — VTK-Name
            self.clipped = True

    def __init__(self) -> None:
        self.camera = _AimedCamera()
        self.renderer = self._Renderer(self.camera)


def test_the_rotation_start_aims_over_the_weak_callback(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Drehbeginn setzt den Fokus — über den schwachen Rückruf.

    Der Weg ist derselbe wie bei den übrigen Rückrufen an den
    Interaktionsstil: ``_weak_callbacks`` hält die Ansicht schwach, sonst
    stünde die Schleife Stil → Viewport → Plotter → Interactor → Stil wieder
    da. Geprüft wird die Kette bis in die Kamera, mit einer Attrappe, die
    genau die benutzten VTK-Methoden trägt.
    """
    from app.ui.viewport import Viewport, _weak_callbacks

    viewport = Viewport()
    try:
        plotter = _AimedPlotter()
        viewport.plotter = plotter  # type: ignore[assignment]
        monkeypatch.setattr(viewport, "rotation_centre", lambda: (30.0, 10.0, 4.0))

        _weak_callbacks(viewport).on_rotate_start()

        assert plotter.camera.set_to == pytest.approx((0.0, 10.0, 0.0))
        assert plotter.renderer.clipped, "ein neuer Fokus braucht neue Schnittebenen"
    finally:
        viewport.plotter = None
        viewport.deleteLater()


def test_a_body_is_split_once_while_its_mesh_stays(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zerlegt wird ein Körper, wenn sein Netz ein anderes ist — sonst nicht.

    ``split_bodies`` kostet 21 ms bei zweiundachtzigtausend Dreiecken, und
    ``_shadow_hulls_of`` nannte das „einmal je Szenenaufbau, nicht je Bild".
    Der zweite Halbsatz stimmt, der erste beruhigt zu Unrecht: Ein Aufbau ist
    nichts Seltenes. ``show_scene`` läuft bei jeder Auswahl, jedem
    Themenwechsel, jedem Ein- und Ausblenden — und bei **jedem Schritt** der
    Schieber für Explosion, Schnitt und Schicht. Bei zwanzig Teilen auf der
    Platte sind das über vierhundert Millisekunden je Schieberschritt, im
    Qt-Hauptthread.

    Geprüft wird die **Entscheidung** und nicht die Zeit: wie oft zerlegt
    wird. Eine Messung in Millisekunden gehört ins Leistungsbudget (§31) und
    hieße hier auf jeder Maschine etwas anderes.

    Der letzte Schritt ist der, der den Cache ehrlich hält: Ein anderes Netz
    **muss** neu zerlegt werden. Der Schnittschieber erzeugt genau das, und
    ein zerschnittener Körper zerfällt womöglich in andere Stücke als vorher.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        split: list[object] = []

        def _count(surface: object) -> list[str]:
            split.append(surface)
            return ["hülle"]

        monkeypatch.setattr(viewport, "_shadow_hulls_of", _count)

        mesh = object()
        other = object()

        assert viewport._shadow_hulls_for("body_1", "fläche", mesh) == ["hülle"]
        assert len(split) == 1, "das erste Mal wird gerechnet"

        viewport._shadow_hulls_for("body_1", "fläche", mesh)
        viewport._shadow_hulls_for("body_1", "fläche", mesh)
        assert len(split) == 1, "dasselbe Netz wird kein zweites Mal zerlegt"

        viewport._shadow_hulls_for("body_2", "fläche", mesh)
        assert len(split) == 2, "ein anderer Körper hat seinen eigenen Eintrag"

        viewport._shadow_hulls_for("body_1", "fläche", other)
        assert len(split) == 3, "ein anderes Netz schon — der Schnitt baut eines"
    finally:
        viewport.deleteLater()


def test_the_wheel_zooms_in_both_projections() -> None:
    """Das Rad war orthografisch tot, und kein Test hat es gemessen.

    ``vtkCamera.Dolly`` teilt die Distanz zur Fokusebene — in der
    Parallelprojektion bestimmt aber allein ``parallel_scale`` die Bildgröße,
    und die Position ist ihr gleichgültig. Der Skizzenmodus stellt
    orthografisch (§30.1), also tat dort jeder Radschritt **nichts**:
    gemessen am 26.08.2026 am echten Fenster, acht Schritte, Bild byteweise
    unverändert. ``apply_wheel_zoom`` trägt die Fallunterscheidung, die VTKs
    eigener Trackball-Dolly (rechte Taste im CAD-Schema) intern schon trug.

    Gegen die echte ``vtkCamera`` und nicht gegen eine Attrappe: Die Aussage
    „Dolly ändert die Scale nicht" ist eine über VTK, und eine Attrappe
    bezeugte nur sich selbst. Ein Kameraobjekt braucht kein Fenster.
    """
    from vtkmodules.vtkRenderingCore import vtkCamera

    from app.ui.viewport import apply_wheel_zoom

    camera = vtkCamera()
    camera.SetParallelProjection(True)
    camera.SetParallelScale(50.0)
    apply_wheel_zoom(camera, 2.0)
    assert camera.GetParallelScale() == pytest.approx(25.0), (
        "hineinzoomen muss den sichtbaren Ausschnitt verkleinern"
    )

    camera.SetParallelProjection(False)
    camera.SetPosition(0.0, 0.0, 100.0)
    camera.SetFocalPoint(0.0, 0.0, 0.0)
    apply_wheel_zoom(camera, 2.0)
    assert camera.GetDistance() == pytest.approx(50.0), (
        "perspektivisch bleibt der Weg der alte: Dolly teilt die Distanz"
    )


# --- Der Ziehgriff der Querschau (§30.1) -------------------------------------


def flat_curves() -> tuple[Any, ...]:
    """Ein Rechteck als Kurve auf der XY-Ebene, wie ``curves_of`` es liefert."""
    from app.core.sketch.profile import SketchCurve

    corners = [
        (0.0, 0.0, 0.0),
        (40.0, 0.0, 0.0),
        (40.0, 20.0, 0.0),
        (0.0, 20.0, 0.0),
    ]
    return (SketchCurve(points=(*corners, corners[0]), construction=False),)


def test_the_cage_grows_out_of_the_outline_along_the_normal() -> None:
    """Was beim Ziehen wächst, liegt über der Zeichnung und nicht daneben.

    Die Drahtform ist die einzige Auskunft während des Zugs — eine, die um
    einen halben Millimeter neben der Ebene läge, behauptete einen anderen
    Körper als den, der danach entsteht.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import pull_cage

    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    lines = pull_cage(frame, flat_curves(), height=12.0)

    assert lines, "eine Höhe über einem Umriss ergibt eine Drahtform"
    heights = {round(point[2], 9) for start, end in lines for point in (start, end)}
    assert heights == {0.0, 12.0}, f"nur Boden und Deckel, gemessen {sorted(heights)}"


def test_the_cage_reaches_the_full_height_and_no_further() -> None:
    """Die Höhe der Drahtform ist die Zahl, die am Zeiger steht.

    Getrennt vom Test darüber, weil eine Drahtform, die *irgendwo* über der
    Ebene endet, dort auch grün wäre — geprüft wird der Wert.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import pull_cage

    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    for height in (0.5, 7.0, 250.0):
        lines = pull_cage(frame, flat_curves(), height=height)
        top = max(point[2] for start, end in lines for point in (start, end))
        assert top == pytest.approx(height)


def test_the_cage_follows_a_tilted_plane_instead_of_world_up() -> None:
    """Auf einer angeklickten Fläche ist „hoch" die Normale dieser Fläche.

    Dieselbe Zusage wie bei ``axis_hit``, hier für das Bild: Ein Körper, der
    entlang der Ebenennormalen entsteht, muss auch dorthin wachsen zu sehen
    sein — sonst zeigt die Vorschau etwas anderes als das Ergebnis.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import pull_cage

    frame = frame_of((1.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    curves = flat_curves()
    lines = pull_cage(frame, curves, height=10.0)

    lifted = {tuple(round(value, 6) for value in end) for start, end in lines}
    for point in curves[0].points:
        expected = tuple(round(point[axis] + 10.0 * frame.normal[axis], 6) for axis in range(3))
        assert expected in lifted, f"{expected} fehlt in der angehobenen Kopie"


def test_construction_geometry_is_not_pulled_up() -> None:
    """Hilfsgeometrie bildet kein Profil, also entsteht daran kein Körper.

    Eine mitgezogene Konstruktionslinie wäre eine Wand, die im Ergebnis nicht
    vorkommt — dieselbe Grenze, die ``regions_of`` später zieht.
    """
    from app.core.sketch.planes import frame_of
    from app.core.sketch.profile import SketchCurve
    from app.ui.viewport import pull_cage

    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    helper = SketchCurve(points=((0.0, 0.0, 0.0), (100.0, 100.0, 0.0)), construction=True)
    assert pull_cage(frame, (helper,), height=10.0) == []


def test_a_height_of_zero_draws_nothing() -> None:
    """Kein Sonderfall, sondern ein Körper ohne Ausdehnung.

    Der Zug beginnt bei null: Ohne diesen Zweig legte der erste Mausdruck eine
    Drahtform mit deckungsgleichem Boden und Deckel in die Szene, also
    doppelte Linien auf der Zeichnung.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import pull_cage

    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    assert pull_cage(frame, flat_curves(), height=0.0) == []


def test_the_cage_caps_its_ribs_on_a_finely_sampled_curve() -> None:
    """Ein Kreis mit vierundsechzig Punkten wird keine Wand aus Strichen.

    Die Sprossen machen aus zwei Umrissen einen Körper; eine je Punkt ergäbe
    bei einer abgetasteten Kurve eine geschlossene Fläche, hinter der die
    Zeichnung verschwindet. Erste und letzte bleiben dabei immer dabei — an
    den Enden hängt die Form.
    """
    from app.core.sketch.planes import frame_of
    from app.core.sketch.profile import SketchCurve
    from app.ui.viewport import MOST_PULL_RIBS, pull_cage

    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    ring = SketchCurve(
        points=tuple(
            (
                10.0 * math.cos(step / 64.0 * math.tau),
                10.0 * math.sin(step / 64.0 * math.tau),
                0.0,
            )
            for step in range(65)
        ),
        construction=False,
    )
    lines = pull_cage(frame, (ring,), height=5.0)
    ribs = [pair for pair in lines if pair[0][2] != pair[1][2]]

    assert len(ribs) <= MOST_PULL_RIBS + 1, f"{len(ribs)} Sprossen sind eine Wand"
    feet = {tuple(round(value, 6) for value in pair[0]) for pair in ribs}
    for index in (0, 64):
        point = tuple(round(value, 6) for value in ring.points[index])
        assert point in feet, "Anfang und Ende tragen immer eine Sprosse"


def test_a_rectangle_keeps_a_rib_at_every_corner() -> None:
    """Und bei fünf Punkten bleiben alle fünf.

    Die Gegenprobe zum Deckel darüber: Wer die Sprossen pauschal ausdünnt,
    verliert an einem Rechteck eine Ecke, und aus dem Kasten wird ein Dach.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import pull_cage

    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    lines = pull_cage(frame, flat_curves(), height=6.0)
    ribs = [pair for pair in lines if pair[0][2] != pair[1][2]]

    assert len(ribs) == 5, f"fünf Punkte, fünf Sprossen — gemessen {len(ribs)}"


def test_the_grip_measures_against_the_segments_not_the_corners() -> None:
    """Ein Griff, der nur an den Ecken greift, verlangt eine Zielübung.

    Dieselbe Unterscheidung wie bei der Merkmalssuche: gemessen wird gegen den
    nächsten Ort *auf* der Strecke. Die Mitte einer 40 Punkte langen Kante ist
    von jeder Ecke zwanzig entfernt und von der Kante null.
    """
    from app.ui.viewport import polyline_distance

    line = [(0.0, 0.0), (40.0, 0.0)]
    assert polyline_distance(line, (20.0, 0.0)) == pytest.approx(0.0)
    assert polyline_distance(line, (20.0, 3.0)) == pytest.approx(3.0)


def test_the_grip_ends_where_the_drawing_ends() -> None:
    """Er reicht nicht entlang der verlängerten Geraden weiter.

    Sonst wäre in der Querschau — dort projiziert der Umriss auf einen Strich —
    die ganze Bildzeile ein Griff, und die Kamera hätte ihre linke Taste
    verloren.
    """
    from app.ui.viewport import polyline_distance

    line = [(0.0, 0.0), (40.0, 0.0)]
    assert polyline_distance(line, (60.0, 0.0)) == pytest.approx(20.0)


def test_nothing_drawn_is_infinitely_far_away() -> None:
    """Von nichts ist alles gleich weit weg — und damit greift nichts.

    Ohne diesen Zweig gäbe ``min`` über eine leere Folge einen Fehler, und zwar
    genau beim Betreten des Modus, wenn noch keine Linie steht.
    """
    from app.ui.viewport import polyline_distance

    assert polyline_distance([], (0.0, 0.0)) == math.inf
    assert polyline_distance([(3.0, 4.0)], (0.0, 0.0)) == pytest.approx(5.0)


def test_the_pulled_height_snaps_to_the_grid_that_is_drawn() -> None:
    """Eine aufgezogene Höhe ist eine runde Zahl.

    Zwei Gründe in einem: 20 statt 19,7 ist die Zahl, die jemand meinte, und
    ein Zug, der zwischen zwei Rasterpunkten nichts ändert, muss nicht neu
    zeichnen — dieselbe Ersparnis, an der die Fangmarke hängt.
    """
    from app.ui.viewport import pulled_height

    assert pulled_height(19.7, step=5.0, limits=(0.1, 1000.0)) == pytest.approx(20.0)
    assert pulled_height(19.7, step=0.0, limits=(0.1, 1000.0)) == pytest.approx(19.7)


def test_the_pulled_height_stays_inside_the_limits_of_the_operation() -> None:
    """Die Zahl am Zeiger ist die, die der Dialog danach annimmt.

    Eine Höhe von 4000 mm lehnt ``sketch_extrude`` ab; sie am Zeiger zu zeigen
    und danach abzulehnen wäre eine Zusage, die der nächste Schritt bricht.
    Das Vorzeichen bleibt erhalten: außen ist Aufbau, innen ist Tasche.
    """
    from app.ui.viewport import pulled_height

    assert pulled_height(4000.0, step=0.0, limits=(0.1, 1000.0)) == pytest.approx(1000.0)
    assert pulled_height(-30.0, step=0.0, limits=(0.1, 1000.0)) == pytest.approx(-30.0)
    assert pulled_height(-4000.0, step=0.0, limits=(0.1, 1000.0)) == pytest.approx(-1000.0)


def test_without_known_limits_the_height_is_not_clamped() -> None:
    """Eine erfundene Grenze wäre schlechter als keine.

    ``set_sketch_pull`` ohne Grenzen heißt „unbekannt", nicht „null bis null" —
    ohne diesen Zweig wäre jede Höhe auf null geklemmt und der Griff tot.
    """
    from app.ui.viewport import pulled_height

    assert pulled_height(4000.0, step=0.0, limits=(0.0, 0.0)) == pytest.approx(4000.0)


def gripping(viewport: Any, *, height: float | None = 10.0) -> None:
    """Stellt die Ansicht so, als läge der Zeiger auf dem Griff.

    **Ohne diese Attrappe ist jeder Test über den Griff grün und prüft
    nichts** (§35). Offscreen ist ``plotter`` None, also gibt ``_display_of``
    nichts, ``grip_reach`` unendlich und ``sketch_pull_ready`` **immer**
    ``False`` — auch mit gesetztem Angebot. Die erste Fassung dieses Tests
    behauptete damit „ohne Frage kein Griff" und hätte auch bei einem Griff,
    der jede Frage übergeht, bestanden (gefunden von der Review-Sitzung,
    27.08.2026).

    Ersetzt werden genau die drei Methoden, die einen Plotter brauchen — die
    Reichweite im Bild, der Ort auf der Ebene und das Maß entlang der Achse.
    Alles davor und danach ist echt: die Reihenfolge der Bedingungen, die Frage
    an das Fenster und das Signal. ``height=None`` stellt den Fall, dass sich
    von dieser Blickrichtung aus keine Höhe ablesen lässt.
    """
    viewport.grip_reach = lambda x, y: 0.0
    viewport.pull_base_at = lambda x, y: (0.0, 0.0)
    viewport.pull_height_at = lambda base, x, y: height


def test_the_grip_is_not_offered_without_the_window_answering(qt_app: QApplication) -> None:
    """Ohne ``set_sketch_pull`` gibt es die Geste nicht.

    Die Ansicht kennt den Zustand der Zeichnung nicht — Querschau,
    geschlossener Umriss, gewählte Operation. Wer die Frage nicht stellt,
    bekommt keinen Griff, und die linke Taste bleibt bei der Kamera.

    Mit der Attrappe aus :func:`gripping`, damit der Test an der **Frage**
    scheitert und nicht am fehlenden Bild.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_sketching(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)))
    gripping(viewport)

    assert viewport.sketch_pull_ready(10, 10) is False


def test_the_answer_of_the_window_decides_the_grip(qt_app: QApplication) -> None:
    """Drei Antworten, drei Ausgänge — und einer davon ist ein Satz.

    ``"ready"`` gibt die Taste dem Griff; ein **Grund** gibt sie der Kamera und
    sagt, warum (Regel 17); eine leere Antwort gibt sie der Kamera und schweigt,
    denn dort war die Geste nicht gemeint. Der mittlere Fall war in der ganzen
    Suite nicht belegt: ``sketchPullBlocked`` kam nirgends vor.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_sketching(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)))
    gripping(viewport)
    heard: list[str] = []
    viewport.sketchPullBlocked.connect(heard.append)

    viewport.set_sketch_pull(lambda: "ready", (0.1, 1000.0))
    assert viewport.sketch_pull_ready(10, 10) is True
    assert heard == [], "wo es geht, wird nichts gesagt"

    viewport.set_sketch_pull(lambda: "Zum Aufziehen fehlt der geschlossene Umriss.", (0.1, 1000.0))
    assert viewport.sketch_pull_ready(10, 10) is False
    assert heard == ["Zum Aufziehen fehlt der geschlossene Umriss."], heard

    heard.clear()
    viewport.set_sketch_pull(lambda: "", (0.1, 1000.0))
    assert viewport.sketch_pull_ready(10, 10) is False
    assert heard == [], "wo die Geste nicht angeboten wird, gibt es nichts zu erklären"


def test_a_view_that_cannot_read_a_height_offers_no_grip(qt_app: QApplication) -> None:
    """Angeboten wird nur, was auch geht — und das entscheidet die Rechnung.

    Der Griff hing an der Ebenen**wahl**, gearbeitet wird mit der
    Blick**richtung**. Bei einer Skizze auf einer angeklickten Fläche fallen die
    beiden immer auseinander: Der Blick hat dort nie denselben Namen wie die
    Zeichenebene, und bei frontaler Ansicht gab ``axis_hit`` nichts zurück —
    der Griff nahm die linke Taste und tat stumm nichts.

    Keine zweite Schwelle, sondern dieselbe wie in ``axis_hit``: gefragt wird
    die Rechnung selbst.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_sketching(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)))
    heard: list[str] = []
    viewport.sketchPullBlocked.connect(heard.append)
    viewport.set_sketch_pull(lambda: "ready", (0.1, 1000.0))

    gripping(viewport, height=None)
    assert viewport.sketch_pull_ready(10, 10) is False
    assert heard == [], "ein Blick, aus dem keine Höhe folgt, ist kein Fehler des Nutzers"

    gripping(viewport, height=10.0)
    assert viewport.sketch_pull_ready(10, 10) is True, "und mit lesbarer Höhe gilt sie wieder"


def test_a_typed_height_above_the_maximum_is_not_applied(qt_app: QApplication) -> None:
    """Die Obergrenze gilt für die Tastatur genauso wie für den Zug.

    Geprüft wurde nur die Untergrenze: Getippte 4000 gingen bei einem
    Höchstwert von 1000 durch, und der Dialog klemmte sie danach kommentarlos —
    also genau die Zusage gebrochen, dass die Grenze an **einer** Stelle steht.

    Abgelehnt und nicht geklemmt: Wer tippt, meint genau diese Zahl, und sie
    stillschweigend zu ändern wäre die Antwort auf eine andere Frage. Die Zahl
    bleibt im Feld markiert stehen.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    heard: list[float] = []
    viewport.sketchPulled.connect(heard.append)
    viewport._pull_limits = (0.1, 1000.0)
    viewport._pull_from = (0.0, 0.0)
    viewport._drag_kind = "pull"
    viewport.drag_bar.typing = True
    viewport.drag_bar.value.setText("4000")

    viewport._apply_typed()

    assert not heard, "eine Höhe über dem Höchstwert wird nicht angewandt"
    assert viewport._drag_kind == "pull", "der Zug läuft weiter, das Feld bleibt stehen"


def test_pulling_inward_requests_a_pocket_instead_of_making_a_sliver(
    qt_app: QApplication,
) -> None:
    """Ein Zug nach innen bleibt negativ und wird dadurch zur Tasche."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    pulled: list[float] = []
    blocked: list[str] = []
    viewport.sketchPulled.connect(pulled.append)
    viewport.sketchPullBlocked.connect(blocked.append)
    viewport._pull_limits = (0.1, 1000.0)
    viewport._cut_limits = (0.1, 1000.0)
    viewport._pull_from = (0.0, 0.0)
    viewport._drag_kind = "pull"
    viewport._pull_height = -30.0

    viewport.finish_sketch_pull()

    assert pulled == [pytest.approx(-30.0)]
    assert not blocked
    assert viewport.pulling() is False


def test_the_visible_arrow_and_cross_are_grabbable(qt_app: QApplication) -> None:
    """Was als Griff gezeichnet wird, greift bis an Pfeilspitze und Kreuz.

    Der sichtbare Griff ist 38 Bildpunkte lang; nur zehn Bildpunkte um den
    Umriss zu prüfen machte gerade seine Enden zur Attrappe.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import CURSOR_PIXELS, Viewport

    viewport = Viewport()
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    viewport.set_sketching(frame)
    viewport._sketch_curves = flat_curves()
    viewport.pixels_per_mm = lambda _frame: 1.0
    # **Beide Maßstäbe setzen, nicht nur einen.** Der Ziehgriff misst
    # seit dem 30.08.2026 auch senkrecht zur Ebene — dort zeigt sein
    # Schaft, und nur diese Richtung wird im Bild verkürzt. Wer nur
    # ``pixels_per_mm`` patcht, lässt die zweite Messung auf ihren
    # Rückfallwert laufen und bekommt eine Griffgröße, die niemand
    # gesetzt hat.
    viewport.pixels_per_mm_upright = lambda _frame: 1.0
    viewport._display_of = lambda point: (float(point[0]), float(point[2]))
    handle = viewport._pull_handle_segments()
    outward = handle[0][1]
    viewport.set_sketch_pull(lambda: "ready", (0.1, 1000.0), (0.1, 1000.0))
    viewport.pull_height_at = lambda base, x, y: 10.0

    assert viewport.grip_reach(int(outward[0]), int(outward[2])) > CURSOR_PIXELS
    assert viewport.pull_handle_reach(int(outward[0]), int(outward[2])) <= CURSOR_PIXELS
    assert viewport.sketch_pull_ready(int(outward[0]), int(outward[2]))


def test_without_an_editable_body_only_the_outward_pull_is_visible_and_valid(
    qt_app: QApplication,
) -> None:
    """Ein fehlendes Taschenziel verschwindet aus Griff und Zugvorschau."""
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_sketching(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)))
    viewport._sketch_curves = flat_curves()
    viewport.pixels_per_mm = lambda _frame: 1.0
    # **Beide Maßstäbe setzen, nicht nur einen.** Der Ziehgriff misst
    # seit dem 30.08.2026 auch senkrecht zur Ebene — dort zeigt sein
    # Schaft, und nur diese Richtung wird im Bild verkürzt. Wer nur
    # ``pixels_per_mm`` patcht, lässt die zweite Messung auf ihren
    # Rückfallwert laufen und bekommt eine Griffgröße, die niemand
    # gesetzt hat.
    viewport.pixels_per_mm_upright = lambda _frame: 1.0
    viewport.set_sketch_pull(
        lambda: "ready",
        (0.1, 1000.0),
        (0.1, 1000.0),
        lambda: False,
    )

    assert len(viewport._visible_pull_handle_segments()) == 3
    assert viewport._pull_takes(10.0)
    assert not viewport._pull_takes(-10.0)

    hidden: list[bool] = []
    viewport._pull_from = (0.0, 0.0)
    viewport._pull_height = 10.0
    viewport.pull_height_at = lambda _base, _x, _y: -10.0
    viewport._show_pull_cage = lambda: hidden.append(True)
    viewport.continue_sketch_pull(10, 10)

    assert viewport._pull_height == pytest.approx(0.0)
    assert hidden == [True], "beim Richtungswechsel verschwindet die alte Aufbauvorschau"


def test_a_rejected_pull_clears_its_wire_preview(qt_app: QApplication) -> None:
    """Eine Absage lässt weder Drahtkäfig noch alte Zahl im Bild stehen."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport._pull_height = -8.0
    viewport._pull_actors = [object()]

    viewport.cancel_sketch_pull()

    assert viewport._pull_actors == []
    assert viewport._pull_height == pytest.approx(0.0)


def test_a_segment_of_zero_length_is_measured_as_a_point(qt_app: QApplication) -> None:
    """Zwei gleiche Punkte sind eine Strecke ohne Richtung, kein Toleranzfall.

    Hier stand ``EPS_GEOM`` — eine Fertigungstoleranz in Millimetern — gegen
    das Quadrat eines Abstands in **Bildpunkten**. Wirkungslos, aber ein Leser
    hält so etwas für eine geprüfte Wahl. Ein geschlossener Umriss trägt seinen
    ersten Punkt am Ende noch einmal; wer ihn zweimal hintereinander legt,
    bekommt genau diese Strecke.
    """
    from app.ui.viewport import polyline_distance

    doubled = [(10.0, 10.0), (10.0, 10.0), (40.0, 10.0)]
    assert polyline_distance(doubled, (10.0, 14.0)) == pytest.approx(4.0)
    assert polyline_distance([(10.0, 10.0), (10.0, 10.0)], (13.0, 14.0)) == pytest.approx(5.0)


def test_letting_go_of_the_grip_becomes_an_operation(qt_app: QApplication) -> None:
    """Der Zug endet als Signal und nicht als Geometrie (Regel 2).

    Die Ansicht ändert nie selbst ein Modell: Was beim Loslassen herauskommt,
    ist eine Zahl, und das Fenster macht daraus ``sketch_extrude``.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    heard: list[float] = []
    viewport.sketchPulled.connect(heard.append)
    viewport._pull_limits = (0.1, 1000.0)
    viewport._pull_from = (0.0, 0.0)
    viewport._pull_height = 14.0
    viewport._drag_kind = "pull"

    viewport.finish_sketch_pull()

    assert heard == [pytest.approx(14.0)], "die gezogene Höhe kommt genau einmal an"
    assert viewport.pulling() is False, "und der Zug ist danach vorbei"


def test_a_click_on_the_grip_is_not_a_pull(qt_app: QApplication) -> None:
    """Ohne Bewegung entsteht keine Operation.

    Die Untergrenze der Operation ist die Grenze, unterhalb derer nichts
    entstehen kann — ein Druck ohne Zug ergäbe sonst einen Schritt im Verlauf
    über einen Körper von null Millimetern Höhe.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    heard: list[float] = []
    viewport.sketchPulled.connect(heard.append)
    viewport._pull_limits = (0.1, 1000.0)
    viewport._pull_from = (0.0, 0.0)
    viewport._pull_height = 0.0
    viewport._drag_kind = "pull"

    viewport.finish_sketch_pull()

    assert not heard, "null Millimeter sind kein Zug"


def test_a_typed_height_takes_the_same_way_out_as_a_pulled_one(qt_app: QApplication) -> None:
    """Die Eingabetaste während des Zugs (§18.11) — mit derselben Grenze.

    Zwei Wege zu derselben Operation wären zwei Gelegenheiten, die Grenze zu
    vergessen: Getippt geht die Zahl durch ``finish_sketch_pull``, und eine
    unbrauchbare bleibt im Feld stehen, statt angewandt zu werden.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    heard: list[float] = []
    viewport.sketchPulled.connect(heard.append)
    viewport._pull_limits = (0.1, 1000.0)
    viewport._pull_from = (0.0, 0.0)
    viewport._drag_kind = "pull"
    viewport.drag_bar.typing = True
    viewport.drag_bar.value.setText("25")

    viewport._apply_typed()
    assert heard == [pytest.approx(25.0)], "die getippte Höhe gewinnt"

    heard.clear()
    viewport._pull_from = (0.0, 0.0)
    viewport._drag_kind = "pull"
    viewport.drag_bar.typing = True
    viewport.drag_bar.value.setText("0")

    viewport._apply_typed()
    assert not heard, "eine Höhe unter der Untergrenze wird nicht angewandt"
    assert viewport._drag_kind == "pull", "und der Zug läuft weiter, das Feld bleibt stehen"


def test_escape_during_a_pull_applies_nothing(qt_app: QApplication) -> None:
    """Esc verwirft den Zug — und räumt die Drahtform ab, nicht den Stil.

    ``_end_drag`` holt sonst den Navigationsstil zurück, und das baute den
    Interaktionsstil mitten in der Geste neu auf: Das Loslassen käme bei einem
    Stil an, der von seinem Drücken nichts weiß.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    heard: list[float] = []
    viewport.sketchPulled.connect(heard.append)
    viewport._pull_limits = (0.1, 1000.0)
    viewport._pull_from = (0.0, 0.0)
    viewport._pull_height = 30.0
    viewport._drag_kind = "pull"

    viewport._end_drag()

    assert not heard, "Esc wendet nichts an"
    assert viewport.pulling() is False
    assert viewport._drag_kind is None


def test_leaving_the_sketch_plane_ends_a_running_pull(qt_app: QApplication) -> None:
    """Ein Zug gehört der Ebene, auf der er begann.

    Dieselbe Begründung wie bei der Fangmarke: Ein Ebenenwechsel geht durch
    ``set_sketching`` mit einem neuen Rahmen, und eine Drahtform, die dann
    stehen bleibt, schwebt auf der vorigen Ebene im Raum.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport._pull_from = (0.0, 0.0)
    viewport._pull_height = 12.0
    viewport._drag_kind = "pull"

    viewport.set_sketching(frame_of((0.0, 1.0, 0.0), (0.0, 0.0, 0.0)))

    assert viewport.pulling() is False, "die neue Ebene beginnt ohne laufenden Zug"


def test_in_the_sketch_mode_the_drag_callback_pulls_instead_of_moving(
    qt_app: QApplication,
) -> None:
    """Dieselbe Geste, zwei Bedeutungen — und die Weiche steht im Rückruf.

    Der Interaktionsstil kennt nur vier Schritte (bereit, Start, Zug, Ende).
    Ohne die Weiche liefe ein Zug im Skizzenmodus in den Körperzug: Er fragte
    nach dem gewählten Körper, fände keinen, und der Ziehgriff wäre still
    nicht vorhanden.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport, _weak_callbacks

    viewport = Viewport()
    viewport.set_sketching(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)))
    steps: list[str] = []

    def note(what: str, answer: bool = True) -> Any:
        def called(*_args: object) -> bool:
            steps.append(what)
            return answer

        return called

    viewport.sketch_pull_ready = note("ready")
    viewport.begin_sketch_pull = note("start")
    viewport.continue_sketch_pull = note("move")
    viewport.finish_sketch_pull = note("end")
    viewport.can_drag_body_at = note("body")

    callbacks = _weak_callbacks(viewport)
    callbacks.on_body_drag("ready", 10, 10)
    callbacks.on_body_drag("start", 10, 10)
    callbacks.on_body_drag("move", 10, 30)
    callbacks.on_body_drag("end", 10, 30)

    assert steps == ["ready", "start", "move", "end"], f"gemessen {steps}"


def test_outside_the_sketch_mode_the_same_callback_moves_a_body(qt_app: QApplication) -> None:
    """Die Gegenprobe: Ohne Zeichenebene bleibt es der Körperzug.

    Ein Test über die Weiche allein wäre auch grün, wenn sie **immer** in den
    Ziehgriff führte — und dann hätte das direkte Verschieben aufgehört zu
    existieren.
    """
    from app.ui.viewport import Viewport, _weak_callbacks

    viewport = Viewport()
    steps: list[str] = []

    def note(what: str, answer: bool) -> Any:
        def called(*_args: object) -> bool:
            steps.append(what)
            return answer

        return called

    viewport.can_drag_body_at = note("body", False)
    viewport.sketch_pull_ready = note("pull", True)

    callbacks = _weak_callbacks(viewport)
    callbacks.on_body_drag("ready", 10, 10)

    assert steps == ["body"], f"gemessen {steps}"


def test_the_value_field_can_stand_at_the_pointer(qt_app: QApplication) -> None:
    """Die Zahl zum Zug steht beim Ziehgriff am Zeiger, nicht am Fensterrand.

    Dieselbe Entscheidung wie beim Maßfeld der Zeichenfläche: Wer eine Höhe
    aufzieht, sieht auf ihre Spitze. Und **nicht darunter** — ein Feld unter
    dem Zeiger fängt die Mausbewegungen ab, und der Zug bliebe stehen.
    """
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QWidget

    from app.ui.viewport import MEASURE_GAP, DragValueBar

    host = QWidget()
    host.resize(800, 600)
    bar = DragValueBar(host)
    bar.resize(120, 30)

    bar.anchor = QPoint(300, 200)
    bar.place()
    assert bar.pos() == QPoint(300 + MEASURE_GAP, 200 + MEASURE_GAP)

    # An der unteren rechten Ecke kippt es auf die andere Seite — dorthin zieht
    # man die letzte Höhe eines Umrisses.
    bar.anchor = QPoint(780, 590)
    bar.place()
    assert bar.pos().x() < 780, "am rechten Rand nach links"
    assert bar.pos().y() < 590, "am unteren Rand nach oben"


def test_without_an_anchor_the_value_field_stays_at_the_top(qt_app: QApplication) -> None:
    """Die Griffe von §18.11 behalten ihren Platz.

    Dort zieht man an einem Gizmo, den man ansieht, und ein Feld unter dem
    Zeiger verdeckte gerade ihn. Ohne diese Gegenprobe wäre der Anker eine
    Änderung an allen vier Zugarten.
    """
    from PySide6.QtWidgets import QWidget

    from app.ui.viewport import BANNER_TOP, DragValueBar

    host = QWidget()
    host.resize(800, 600)
    bar = DragValueBar(host)
    bar.resize(120, 30)

    bar.place()

    assert bar.pos().y() == BANNER_TOP
    assert bar.pos().x() == (800 - 120) // 2


def test_dismissing_the_value_field_forgets_the_anchor(qt_app: QApplication) -> None:
    """Sonst stünde die Zahl des nächsten Gizmo-Zugs dort, wo einmal der
    Ziehgriff war — ein Ort ohne Bezug zu dem, was gerade gezogen wird."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QWidget

    from app.ui.viewport import DragValueBar

    host = QWidget()
    bar = DragValueBar(host)

    bar.anchor = QPoint(100, 100)
    bar.dismiss()

    assert bar.anchor is None


def test_a_pull_to_the_stop_still_becomes_an_operation(qt_app: QApplication) -> None:
    """Der Anschlag ist eine Zusage und keine Absage.

    Wer weit über die Obergrenze hinauszieht, sieht in der Leiste den
    geklemmten Wert — **und der ist, was gilt**. Die Richtungsprüfung fragte
    einen Anlauf lang die vollständige Grenze und lehnte damit genau diesen
    Fall ab: kein Körper, dazu „andersherum ziehen" als Meldung zu einem Zug,
    der in die richtige Richtung ging (gefunden von der Review-Sitzung,
    27.08.2026). Die Frage nach der **Richtung** hat nur eine Grenze.
    """
    from app.ui.viewport import Viewport, pulled_height

    viewport = Viewport()
    pulled: list[float] = []
    blocked: list[str] = []
    viewport.sketchPulled.connect(pulled.append)
    viewport.sketchPullBlocked.connect(blocked.append)
    viewport._pull_limits = (0.1, 1000.0)
    viewport._pull_from = (0.0, 0.0)
    viewport._drag_kind = "pull"
    viewport._pull_height = pulled_height(4000.0, 0.0, viewport._pull_limits)
    assert viewport._pull_height == pytest.approx(1000.0), "die Leiste zeigt den Anschlag"

    viewport.finish_sketch_pull()

    assert pulled == [pytest.approx(1000.0)], f"gemessen {pulled}"
    assert not blocked, blocked


def test_a_typed_height_survives_a_pull_in_the_wrong_direction(qt_app: QApplication) -> None:
    """Wer tippt, hat die Frage nach der Richtung beantwortet.

    und die Richtungsprüfung lehnte damit auch die **eingetippte** Höhe ab: Der
    Griff war per Tastatur nicht mehr zu retten, obwohl §18.11 genau dafür die
    Zahleneingabe während des Zugs vorsieht.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    pulled: list[float] = []
    blocked: list[str] = []
    viewport.sketchPulled.connect(pulled.append)
    viewport.sketchPullBlocked.connect(blocked.append)
    viewport._pull_limits = (0.1, 1000.0)
    viewport._pull_from = (0.0, 0.0)
    viewport._drag_kind = "pull"
    viewport._pull_height = 0.1
    viewport.drag_bar.typing = True
    viewport.drag_bar.value.setText("25")

    viewport._apply_typed()

    assert pulled == [pytest.approx(25.0)], f"gemessen {pulled}"
    assert not blocked, blocked


def test_camera_near_a_sketch_main_view_snaps_by_direction() -> None:
    """Schieben ändert nichts; nur ein Blick nahe einer Hauptansicht rastet."""
    from app.ui.viewport import sketch_view_near

    assert sketch_view_near((0.2, -0.1, 10.0), (0.2, -0.1, 0.0)) == "plane:xy"
    assert sketch_view_near((0.0, -10.0, 0.1), (0.0, 0.0, 0.0)) == "plane:xz"
    assert sketch_view_near((10.0, 0.1, 0.0), (0.0, 0.0, 0.0)) == "plane:yz"
    assert sketch_view_near((10.0, -10.0, 8.0), (0.0, 0.0, 0.0)) is None
    assert sketch_view_near((0.0, 0.0, -10.0), (0.0, 0.0, 0.0)) is None


def test_the_model_view_snaps_to_all_six_axis_views() -> None:
    """Am Modell rasten auch die Rückseiten ein — beim Zeichnen nicht.

    **Der Unterschied ist keine Nachlässigkeit, sondern die Sache.** Eine
    Skizze auf ``plane:xz`` von hinten betrachtet läge gespiegelt zu ihrem
    eigenen Namen; deshalb kennt ``sketch_view_near`` nur die drei Ebenen, auf
    denen gezeichnet wird. Wer ein Modell ansieht, will einfach dorthin
    schauen — von hinten ist so gut wie von vorn.

    Robert am 30.08.2026: „die seitenansicht, vorderansicht und draufsicht
    sollten in der nähe einrasten."
    """
    from app.ui.viewport import axis_view_near, sketch_view_near

    von_hinten = ((0.0, 10.0, 0.0), (0.0, 0.0, 0.0))
    von_unten = ((0.0, 0.0, -10.0), (0.0, 0.0, 0.0))
    von_links = ((-10.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    assert axis_view_near(*von_hinten) == "back"
    assert axis_view_near(*von_unten) == "bottom"
    assert axis_view_near(*von_links) == "left"

    assert sketch_view_near(*von_hinten) is None, (
        "eine Skizze darf nicht auf ihre Rückseite einrasten — sie läge gespiegelt zu ihrem Namen"
    )
    assert sketch_view_near(*von_unten) is None
    assert sketch_view_near(*von_links) is None


def test_the_oblique_view_never_catches_a_turning_camera() -> None:
    """``iso`` rastet nicht ein, obwohl die Werkzeugleiste sie anbietet.

    Sie liegt mitten im Drehraum: Wer ein Modell dreht, käme dort ständig
    vorbei, und ein Einrasten wäre kein Ziel, sondern ein Hindernis. Eine
    Achsenansicht dagegen will man genau treffen.
    """
    from app.ui.viewport import VIEW_DIRECTIONS, axis_view_near

    richtung, _up = VIEW_DIRECTIONS["iso"]
    laenge = sum(wert * wert for wert in richtung) ** 0.5
    genau_darauf = tuple(wert / laenge * 10.0 for wert in richtung)

    assert axis_view_near(genau_darauf, (0.0, 0.0, 0.0)) is None, (
        "die schräge Ansicht darf keine Kamera fangen — sonst rastet jeder "
        "Zug durch den Drehraum darauf ein"
    )


def test_the_snap_reaches_far_enough_to_cover_an_unusable_drag() -> None:
    """Der Fangbereich muss die Lagen abdecken, in denen der Ziehgriff nichts taugt.

    **Die Verbindung zwischen zwei Zahlen, die sonst nichts voneinander
    wüssten.** Am Ziehgriff wird eine Höhe aus der Mausbewegung abgelesen, und
    die Empfindlichkeit wächst mit ``1/sin`` des Kippwinkels: Bei einem Grad
    bedeuten zehn Pixel rund siebzig Millimeter, bei fünf Grad noch vierzehn.
    Die einzige Grenze in ``axis_hit`` ist ``_PARALLEL_ENOUGH = 1e-3``, also
    **0,057°** — eine numerische Schranke gegen Division durch fast Null, keine
    bedienbare.

    Bedienbar wird es, wenn ein Pixel höchstens einen Rasterschritt bedeutet:
    bei 1 mm Raster und 0,125 mm je Pixel in der Seitenansicht ist das
    ``sin >= 0,125``, also rund **7°**. Der Fangbereich liegt darüber, und
    deshalb braucht es keine zweite Schwelle daneben — wer im Skizzenmodus
    dreht und loslässt, landet nie in der unbrauchbaren Zone.

    Dieser Test hält genau das fest: Wird der Fangbereich unter 7° gesenkt,
    reißt er, und wer ihn senkt, weiß warum.
    """
    import math

    from app.ui.viewport import sketch_view_near

    unbrauchbar_bis_grad = 7.0
    knapp_darunter = math.radians(unbrauchbar_bis_grad - 0.5)
    aus_der_draufsicht = (0.0, math.sin(knapp_darunter) * 10.0, math.cos(knapp_darunter) * 10.0)

    assert sketch_view_near(aus_der_draufsicht, (0.0, 0.0, 0.0)) == "plane:xy", (
        f"bei {unbrauchbar_bis_grad - 0.5}° muss die Kamera noch einrasten — sonst "
        "bleibt der Ziehgriff in einer Lage stehen, in der zehn Pixel über "
        "zehn Millimeter bedeuten"
    )


def test_sketch_drag_callback_edits_before_it_moves_the_camera(
    qt_app: QApplication,
) -> None:
    """Ein Zug auf Geometrie gehört der Auswahl, nicht der Kameranavigation."""
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport, _weak_callbacks

    viewport = Viewport()
    viewport.set_sketching(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)))
    viewport._sketch_hit = lambda x, y: (float(x), float(y))
    viewport.pull_handle_reach = lambda x, y: math.inf
    viewport.sketch_pull_ready = lambda x, y: False
    steps: list[object] = []
    viewport.set_sketch_edit(
        lambda point: True,
        lambda point: steps.append(("start", point)) or True,
        lambda point: steps.append(("move", point)),
        lambda: steps.append("end"),
    )

    callbacks = _weak_callbacks(viewport)
    assert callbacks.on_body_drag("ready", 4, 5)
    assert callbacks.on_body_drag("start", 4, 5)
    callbacks.on_body_drag("move", 8, 9)
    callbacks.on_body_drag("end", 8, 9)

    assert steps == [("start", (4.0, 5.0)), ("move", (8.0, 9.0)), "end"]


def test_explicit_pull_handle_wins_over_sketch_editing(qt_app: QApplication) -> None:
    """Der sichtbare Pfeil kann nicht in einen Auswahl- oder Kamerazug fallen."""
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport, _weak_callbacks

    viewport = Viewport()
    viewport.set_sketching(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)))
    viewport._sketch_hit = lambda x, y: (float(x), float(y))
    viewport.pull_handle_reach = lambda x, y: 0.0
    viewport.sketch_pull_ready = lambda x, y: True
    steps: list[str] = []
    viewport.set_sketch_edit(
        lambda point: True,
        lambda point: steps.append("edit") or True,
        lambda point: None,
        lambda: None,
    )
    viewport.begin_sketch_pull = lambda x, y: steps.append("pull") or True
    viewport.continue_sketch_pull = lambda x, y: None
    viewport.finish_sketch_pull = lambda: None

    callbacks = _weak_callbacks(viewport)
    assert callbacks.on_body_drag("ready", 10, 10)
    assert callbacks.on_body_drag("start", 10, 10)

    assert steps == ["pull"]


def test_sketch_render_state_keeps_selection_and_control_points_offscreen(
    qt_app: QApplication,
) -> None:
    """Die Auswahl ist auch ohne VTK als Teil des sichtbaren Vertrags prüfbar."""
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport

    viewport = Viewport()
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    controls = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0))
    viewport.show_sketch(
        flat_curves(),
        frame,
        selected_curves=(0,),
        control_points=controls,
        selected_points=(1,),
    )

    assert viewport._sketch_selected_curves == (0,)
    assert viewport._sketch_control_points == controls
    assert viewport._sketch_selected_points == (1,)


# --- Der Ziehgriff bei gekippter Kamera ---------------------------------------


def _profilkurve():
    """Ein geschlossenes Rechteck als Umriss, an dem der Griff sitzt."""
    from app.core.sketch.profile import SketchCurve

    return SketchCurve(
        points=(
            (-20.0, -20.0, 0.0),
            (20.0, -20.0, 0.0),
            (20.0, 20.0, 0.0),
            (-20.0, 20.0, 0.0),
            (-20.0, -20.0, 0.0),
        )
    )


def test_the_handle_stretches_lengthwise_but_not_across() -> None:
    """Der Schaft wird gestreckt, Flügel und Kreuz bleiben, wie sie waren.

    **Weil nur eine der beiden Richtungen im Bild verkürzt wird.** Der Schaft
    zeigt entlang der Ebenennormalen und schrumpft mit dem Sinus des
    Kippwinkels; Pfeilflügel und Kreuz liegen *in* der Ebene und tun das nicht.
    Wer beide über dieselbe Zahl bemisst, bläst beim Strecken die Querstücke
    mit auf — gemessen am 30.08.2026 eine Griffspanne von 156 statt 69
    Bildpunkten, aus einem Griff, den man nicht findet, wurde einer, der das
    Profil verdeckt.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import pull_handle

    rahmen = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    kurven = (_profilkurve(),)

    schmal = pull_handle(rahmen, kurven, 10.0, 2.0)
    breit = pull_handle(rahmen, kurven, 10.0, 8.0)
    assert len(schmal) == len(breit), "die Zahl der Striche hängt nicht an der Breite"

    def weiteste_quer(striche):
        return max(abs(punkt[0]) for strich in striche for punkt in strich)

    def weiteste_laengs(striche):
        return max(abs(punkt[2]) for strich in striche for punkt in strich)

    assert weiteste_quer(breit) > weiteste_quer(schmal), (
        "eine größere Querweite muss die Flügel breiter machen"
    )
    assert weiteste_laengs(breit) == pytest.approx(weiteste_laengs(schmal)), (
        "die Querweite darf den Schaft nicht verlängern — genau diese Kopplung war der Fehler"
    )


def test_without_a_cross_size_the_handle_behaves_as_before() -> None:
    """``across`` ohne Wert heißt ``size`` — die alte Form bleibt erreichbar.

    In der Seitenansicht sind beide Maße ohnehin gleich; ein Aufrufer, der nur
    eine Zahl kennt, bekommt weiterhin genau das, was er bekam.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import pull_handle

    rahmen = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    kurven = (_profilkurve(),)

    assert pull_handle(rahmen, kurven, 7.0) == pull_handle(rahmen, kurven, 7.0, 7.0)


def test_the_stretch_is_bounded_by_the_snap_that_precedes_it() -> None:
    """Die Streckgrenze endet dort, wo das Einrasten beginnt.

    **Eine Zahl aus der Sache und keine Streuzahl.** Der Schaft wird gestreckt,
    damit er im Bild seine Länge behält, und das wächst gegen unendlich, je
    flacher der Blick steht. Begrenzt wird es dort, wo es aufhört, gebraucht zu
    werden: Unter zehn Grad rastet die Kamera auf die nächste Hauptansicht ein
    (``_settle_sketch_view``), es gibt dort also keinen flachen Blick mehr. Bei
    genau zehn Grad ist der nötige Faktor ``1/sin(10°) = 5,76``.

    Wird die Grenze darunter gesetzt, greift sie **vor** dem Einrasten — dann
    bleibt zwischen zehn und dem Einrastwinkel eine Lücke, in der der Griff
    wieder zu kurz ist.
    """
    import math

    from app.ui.viewport import PULL_HANDLE_STRETCH, sketch_view_near

    noetig_bei_zehn = 1.0 / math.sin(math.radians(10.0))
    assert noetig_bei_zehn <= PULL_HANDLE_STRETCH, (
        f"die Streckgrenze {PULL_HANDLE_STRETCH} liegt unter den {noetig_bei_zehn:.2f}, "
        "die bei zehn Grad nötig sind — dort wäre der Griff wieder zu kurz"
    )

    # Und die zehn Grad sind wirklich der Rand des Einrastens: knapp darunter
    # fängt es, knapp darüber nicht.
    for grad, erwartet in ((9.5, "plane:xy"), (10.5, None)):
        rad = math.radians(grad)
        kamera = (0.0, math.sin(rad) * 10.0, math.cos(rad) * 10.0)
        assert sketch_view_near(kamera, (0.0, 0.0, 0.0)) == erwartet, (
            f"bei {grad}° erwartet: {erwartet} — die Streckgrenze ist auf diesen Rand gerechnet"
        )


def test_each_navigation_scheme_does_what_its_name_promises() -> None:
    """Vier Schemata, und zwei hielten ihren eigenen Namen nicht (V3).

    „Wie im CAD — mittlere Taste dreht" stand im Einstellungsdialog, und die
    mittlere Taste hatte **gar keinen Beobachter**: In `cad` drehte die linke,
    in `blender` ebenso. Wer aus einem CAD oder aus Blender kam, drückte das
    Rad, nichts geschah, und die linke Taste drehte das Modell weg, statt
    etwas auszuwählen.

    Geprüft wird an der Tabelle, aus der der Interaktionsstil seine Aufrufe
    holt — die Kette im Stil ist eine VTK-Klasse und lief offscreen nie;
    genau deshalb konnte der falsche Satz zwei Schemata lang dastehen.
    """
    from app.ui.viewport import navigation_action

    # Cura und die Slicer-Familie bleiben, wie sie waren.
    assert navigation_action("slicer", "left", False) == "select"
    assert navigation_action("slicer", "left", True) == "pan"
    assert navigation_action("slicer", "right", False) == "rotate"
    assert navigation_action("orbit", "left", False) == "rotate"
    assert navigation_action("orbit", "right", False) == "pan"

    # Die mittlere Taste schiebt dort weiter — das tat sie über VTKs eigene
    # Behandlung schon immer, und ein neuer Beobachter darf es nicht nehmen.
    for scheme in ("slicer", "orbit"):
        assert navigation_action(scheme, "middle", False) == "pan", scheme
        assert navigation_action(scheme, "middle", True) == "pan", scheme

    # Und die zwei, die ihren Namen jetzt halten.
    assert navigation_action("cad", "middle", False) == "rotate"
    assert navigation_action("cad", "middle", True) == "pan"
    assert navigation_action("cad", "left", False) == "select"
    assert navigation_action("cad", "right", False) == "zoom"

    assert navigation_action("blender", "middle", False) == "rotate"
    assert navigation_action("blender", "middle", True) == "pan"
    assert navigation_action("blender", "left", False) == "select"


def test_every_scheme_can_rotate_and_pan() -> None:
    """Keine Belegung darf eine Kamerabewegung verlieren.

    Wer ein Schema wählt, muss damit drehen **und** schieben können; ein
    Schema ohne eines von beidem wäre eine Sackgasse, in der ein Teil der
    Szene unerreichbar bleibt.

    **Ausgewählt wird nicht über diese Tabelle**, und das ist der Grund,
    warum hier ``select`` nicht mitgeprüft wird: Der erste Entwurf dieses
    Tests verlangte es und meldete prompt „orbit kann nicht auswählen" — ein
    Fehlbefund. Ein Klick ohne Zug geht in **jedem** Schema an ``on_pick``
    (``_left_up``), gleich was die Taste beim Ziehen tut. Die Tabelle
    beschreibt das Ziehen, nicht den Klick.
    """
    from app.ui.viewport import _NAVIGATION, navigation_action

    for scheme in _NAVIGATION:
        reachable = {
            navigation_action(scheme, button, shift)  # type: ignore[arg-type]
            for button in ("left", "middle", "right")
            for shift in (False, True)
        }
        assert {"rotate", "pan"} <= reachable, (
            f"{scheme} kann nicht beides: erreichbar ist {sorted(reachable)}"
        )


def test_the_navigation_texts_say_what_the_scheme_does() -> None:
    """Die Beschreibung im Dialog und das Verhalten kommen aus einer Quelle.

    Nicht wörtlich geprüft — ein Text soll sich lesen lassen —, aber an der
    Aussage, die der Kunde daraus zieht: Wo „mittlere Taste dreht" steht,
    muss die mittlere Taste drehen, und wo „links wählt" steht, darf links
    die Kamera nicht bewegen. Genau diese Zusage war zweimal gebrochen.
    """
    from app.ui.settings_dialog import NAVIGATION
    from app.ui.viewport import _NAVIGATION, navigation_action

    assert set(NAVIGATION) == set(_NAVIGATION), "jedes Schema hat genau eine Beschreibung"

    for scheme, label in NAVIGATION.items():
        text = str(label).lower()
        if "mittlere taste dreht" in text:
            assert navigation_action(scheme, "middle", False) == "rotate", scheme  # type: ignore[arg-type]
        if "links wählt" in text:
            assert navigation_action(scheme, "left", False) == "select", scheme  # type: ignore[arg-type]
        if "links dreht" in text:
            assert navigation_action(scheme, "left", False) == "rotate", scheme  # type: ignore[arg-type]
        if "rechts dreht" in text:
            assert navigation_action(scheme, "right", False) == "rotate", scheme  # type: ignore[arg-type]
        if "rechts zoomt" in text:
            assert navigation_action(scheme, "right", False) == "zoom", scheme  # type: ignore[arg-type]
        if "rechts schiebt" in text:
            assert navigation_action(scheme, "right", False) == "pan", scheme  # type: ignore[arg-type]


def test_the_body_gets_more_light_where_its_colour_is_darker() -> None:
    """Das Frontlicht hängt am Thema, und die Richtung ist begründet.

    Der Körper ist im hellen Thema ``#78828e`` und im dunklen ``#b9c4d0`` —
    0,217 gegen 0,532 Luminanz, also 2,45-mal dunkler. Schattierung
    multipliziert; damit sind auf ihm auch alle Helligkeitsunterschiede
    2,45-mal kleiner, und der Körper wird zur flachen Silhouette. Gemessen am
    30.08.2026 zwischen den zwei sichtbaren Außenwänden der Beispieldose:
    0,0155 im hellen gegen 0,0380 im dunklen Thema.

    Die Zusage ist deshalb keine Zahl, sondern eine **Richtung**: Wo die
    Grundfarbe dunkler ist, braucht der Körper mehr Frontlicht. Wer die Werte
    stimmt, darf sie ändern; wer sie vertauscht, macht den Befund wieder auf.
    """
    from app.ui.theme import viewport_colours
    from app.ui.viewport import HEADLIGHT

    assert set(HEADLIGHT) == {"light", "dark"}, "beide Themen brauchen einen Wert"
    assert all(0.0 <= wert <= 1.0 for wert in HEADLIGHT.values()), HEADLIGHT

    def luminanz(farbe: str) -> float:
        roh = [int(farbe[stelle : stelle + 2], 16) / 255.0 for stelle in (1, 3, 5)]
        linear = [k / 12.92 if k <= 0.03928 else ((k + 0.055) / 1.055) ** 2.4 for k in roh]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    hell = luminanz(viewport_colours("light")["object"])
    dunkel = luminanz(viewport_colours("dark")["object"])
    # Die Gegenprobe zur Begründung: Ist der Körper im hellen Thema *nicht*
    # dunkler, trägt die ganze Argumentation nicht und der Test prüft eine
    # Richtung, die es nicht gibt.
    assert hell < dunkel, (
        f"der Körper ist im hellen Thema {hell:.3f} und im dunklen {dunkel:.3f} — "
        "die Begründung des Frontlichts setzt das Gegenteil voraus"
    )
    assert HEADLIGHT["light"] > HEADLIGHT["dark"], (
        f"heller Körper {hell:.3f} bekommt {HEADLIGHT['light']}, "
        f"dunkler {dunkel:.3f} bekommt {HEADLIGHT['dark']} — falsch herum"
    )


def test_the_theme_really_reaches_the_headlight() -> None:
    """``set_theme`` stellt das Frontlicht ein — und findet es über seine Art.

    Offscreen gibt es keinen Plotter, also eine Attrappe mit genau dem, was
    benutzt wird (wie in ``test_cursors.py``). Geprüft wird beides: dass der
    Wert des Themas ankommt, und dass **nur** das Headlight ihn bekommt — die
    vier Kameralichter des Light Kits stehen über und hinter dem Teil und
    haben mit dieser Entscheidung nichts zu tun.

    Gesucht wird über ``light_type`` und nicht über die Stelle in der Liste:
    Welche Lichter pyvista aufstellt und in welcher Reihenfolge, ist seine
    Sache und kann sich mit einer neuen Fassung ändern.
    """
    from types import SimpleNamespace

    from app.ui.viewport import HEADLIGHT, Viewport

    def lampe(art: str) -> SimpleNamespace:
        return SimpleNamespace(light_type=art, intensity=0.25)

    for thema in ("light", "dark"):
        lichter = [
            lampe("Headlight"),
            lampe("Camera Light"),
            lampe("Camera Light"),
            lampe("Camera Light"),
            lampe("Camera Light"),
        ]
        attrappe = SimpleNamespace(renderer=SimpleNamespace(lights=lichter))
        blind = cast(Any, Viewport.__new__(Viewport))
        blind.plotter = attrappe
        Viewport._light_the_body(blind, thema)

        assert lichter[0].intensity == HEADLIGHT[thema], (
            f"{thema}: Frontlicht steht auf {lichter[0].intensity}, erwartet {HEADLIGHT[thema]}"
        )
        assert all(licht.intensity == 0.25 for licht in lichter[1:]), (
            "die Kameralichter des Light Kits gehören nicht dazu"
        )

    # Und ohne Headlight passiert nichts, statt dass es kracht: Was pyvista
    # aufstellt, ist seine Sache, und ein Körper ohne Frontlicht ist dunkler,
    # aber sichtbar.
    ohne = [lampe("Camera Light"), lampe("Scene Light")]
    blind = cast(Any, Viewport.__new__(Viewport))
    blind.plotter = SimpleNamespace(renderer=SimpleNamespace(lights=ohne))
    Viewport._light_the_body(blind, "light")
    assert all(licht.intensity == 0.25 for licht in ohne), "ohne Headlight bleibt alles stehen"


def test_switching_the_theme_actually_touches_the_headlight() -> None:
    """Und ``set_theme`` ruft es — die Zusage, die der Test darüber nicht hält.

    Gemessen bei der Mutationsprobe am 30.08.2026: Nimmt man den Ruf aus
    ``set_theme`` heraus, bleibt der Test darüber **grün**. Er prüft, was die
    Methode tut, wenn man sie ruft, und nicht, dass sie gerufen wird —
    durchgereicht ist nicht gerufen, und eine Kette endet am letzten Glied.

    Eine Attrappe hilft hier nicht: ``set_theme`` fasst ein Dutzend Kinder an,
    bevor es zum Plotter kommt, und was man dafür alles nachbauen müsste, wäre
    selbst die Fehlerquelle. Gelesen wird deshalb der Quelltext der Methode —
    dieselbe Bauart wie die Setzstellen-Prüfung in ``test_cursors.py``.
    """
    import inspect

    from app.ui.viewport import Viewport

    quelle = inspect.getsource(Viewport.set_theme)
    assert "_light_the_body" in quelle, (
        "set_theme stellt das Frontlicht nicht ein — der Themenwechsel lässt "
        "den Körper in der Beleuchtung des vorigen Themas stehen"
    )
    # Die Gegenprobe zur Suchmethode: Der Name muss dort auch wirklich zu
    # finden sein können, sonst prüft die Zeile darüber eine leere Menge.
    assert "set_background" in quelle, "die gelesene Quelle ist nicht set_theme"


def test_the_contact_shadow_is_as_quiet_on_light_ground_as_on_dark() -> None:
    """Dieselbe Deckkraft ist auf hellem Grund viel lauter — also zwei Werte.

    Der Schatten legt ``SHADOW_COLOUR`` über die Plattenfläche, und wie stark
    das wirkt, hängt daran, wie weit von dort überhaupt noch Weg nach unten
    ist. Bei 0,18 in beiden Themen gemessen (30.08.2026, Beispieldose):
    Kontrast 1,44 im hellen gegen 1,05 im dunklen, ein Luminanzunterschied von
    0,2012 gegen 0,0037 — das Vierundfünfzigfache. Die B35-Aufhellung der
    Plattenfläche hatte das verschärft.

    „Der Schatten wie im dunklen Thema reicht" (Robert, 30.08.2026): Mit 0,03
    im hellen Thema steht er bei 1,06 und damit auf dem Wert des dunklen, das
    bei seinen 0,18 unangetastet bleibt.

    Geprüft wird wieder die **Richtung** und nicht die Zahl — wer die Werte
    stimmt, darf sie ändern; wer sie vertauscht, macht den Befund wieder auf.
    """
    from app.ui.theme import viewport_colours
    from app.ui.viewport import SHADOW_OPACITY

    assert set(SHADOW_OPACITY) == {"light", "dark"}, "beide Themen brauchen einen Wert"
    assert all(0.0 <= wert <= 1.0 for wert in SHADOW_OPACITY.values()), SHADOW_OPACITY

    def luminanz(farbe: str) -> float:
        roh = [int(farbe[stelle : stelle + 2], 16) / 255.0 for stelle in (1, 3, 5)]
        linear = [k / 12.92 if k <= 0.03928 else ((k + 0.055) / 1.055) ** 2.4 for k in roh]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    hell = luminanz(viewport_colours("light")["bed_surface"])
    dunkel = luminanz(viewport_colours("dark")["bed_surface"])
    # Die Gegenprobe zur Begründung: Liegt die helle Plattenfläche nicht höher,
    # gibt es den Effekt nicht, und dieser Test prüfte eine erfundene Ursache.
    assert hell > dunkel, (
        f"Plattenfläche hell {hell:.3f}, dunkel {dunkel:.3f} — die Begründung "
        "der zwei Deckkräfte setzt das Gegenteil voraus"
    )
    assert SHADOW_OPACITY["light"] < SHADOW_OPACITY["dark"], (
        f"heller Grund {hell:.3f} bekommt {SHADOW_OPACITY['light']}, dunkler "
        f"{dunkel:.3f} bekommt {SHADOW_OPACITY['dark']} — falsch herum"
    )


def test_the_theme_reaches_the_shadow_and_the_drawing_reads_it() -> None:
    """Und beide Enden der Kette: ``set_theme`` setzt, das Zeichnen liest.

    Zwei Zusagen, und die zweite ist die, an der es zuerst reißt: Eine
    themenabhängige Konstante nützt nichts, solange die Zeichenstelle weiter
    die **Konstante** liest statt den gemerkten Wert. Dieselbe Lücke hat die
    Mutationsprobe am Frontlicht gezeigt — durchgereicht ist nicht gerufen.
    """
    import inspect

    from app.ui.viewport import Viewport

    quelle = inspect.getsource(Viewport.set_theme)
    assert "_shadow_opacity" in quelle, (
        "set_theme merkt sich die Deckkraft nicht — ein Themenwechsel ließe "
        "den Schatten in der Stärke des vorigen Themas stehen"
    )
    assert "set_background" in quelle, "die gelesene Quelle ist nicht set_theme"

    gezeichnet = inspect.getsource(Viewport._place_shadows)
    assert "self._shadow_opacity" in gezeichnet, (
        "das Zeichnen liest die Konstante statt des gemerkten Werts"
    )


def test_a_finding_gets_a_mark_that_goes_away_again(qt_app: QApplication) -> None:
    """Die Marke einer angeklickten Warnung — und sie bleibt nicht stehen.

    Ein Klick auf einen Befund brachte die Kamera an einen Ort und sonst
    nichts; wo eine Analysekarte läuft, färbt sie die Stelle ein, und die
    Hälfte der Befunde hat keine. Gemessen am 30.08.2026 über alle 58 Befunde
    der Beispielprojekte: **keiner** löste überhaupt eine sichtbare Reaktion
    aus.

    Geprüft wird ohne Fenster über eine Attrappe mit genau den Methoden, die
    ``mark_finding`` benutzt — wie in ``test_cursors.py``. Sie zählt mit, was
    hinzugefügt und was wieder entfernt wird; das ist die Zusage, um die es
    geht, denn eine Marke, die stehen bleibt, wäre eine zweite Auswahl neben
    der echten.
    """
    from types import SimpleNamespace

    from app.ui.viewport import FINDING_MARK_MS, Viewport

    gelegt: list[str] = []
    starts: list[int] = []
    stops: list[None] = []

    class Attrappe:
        camera = SimpleNamespace(
            position=(0.0, -100.0, 60.0), focal_point=(0.0, 0.0, 0.0), parallel_scale=50.0
        )

        def add_mesh(self, *args: Any, **kwargs: Any) -> str:
            gelegt.append(str(kwargs.get("name", "mesh")))
            return str(kwargs.get("name", "mesh"))

        def add_point_labels(self, *args: Any, **kwargs: Any) -> str:
            gelegt.append(str(kwargs.get("name", "label")))
            return str(kwargs.get("name", "label"))

        def remove_actor(self, actor: Any, render: bool = True) -> None:
            gelegt.remove(str(actor))

        def render(self) -> None:
            pass

    blind = cast(Any, Viewport.__new__(Viewport))
    blind.plotter = Attrappe()
    blind._finding_actors = []
    blind._finding_mark = None
    current = SimpleNamespace(name="dieselbe Auswertung")
    blind._result = current
    blind._finding_timer = SimpleNamespace(
        start=starts.append,
        stop=lambda: stops.append(None),
    )

    Viewport.mark_finding(blind, (10.0, 5.0, 2.0), "Wandstärke 0,8 mm")
    assert gelegt == ["finding_ring", "finding_label"], (
        f"Ring und Beschriftung gehören beide dazu: {gelegt}"
    )
    assert blind._finding_mark == ((10.0, 5.0, 2.0), "Wandstärke 0,8 mm", "")
    assert starts == [FINDING_MARK_MS], "die Nutzerhandlung startet genau eine Frist"
    stopped_after_mark = len(stops)

    # Ein Szenenneuaufbau kann die nativen Aktoren verlieren, während die
    # Python-Referenzen noch stehen. Dieselbe Auswertung zeichnet aus dem
    # semantischen Zustand neu, ohne den Zeitgeber noch einmal zu starten.
    gelegt.clear()
    assert Viewport._prepare_finding_mark(blind, current)
    Viewport._draw_finding_mark(blind)
    assert gelegt == ["finding_ring", "finding_label"]
    assert starts == [FINDING_MARK_MS], "eine Kartenberechnung verlängert die Marke nicht"
    assert len(stops) == stopped_after_mark, "dieselbe Auswertung beendet die Frist nicht"

    # Ein neues Ergebnis darf denselben Punkt nicht mit neuer Geometrie
    # verwechseln. Es verwirft Aktoren und semantischen Zustand gemeinsam.
    changed = SimpleNamespace(name="neue Auswertung")
    assert not Viewport._prepare_finding_mark(blind, changed)
    assert blind._finding_mark is None
    assert blind._finding_actors == []

    # Noch einmal setzen, damit auch das reguläre Ablaufen der Frist geprüft
    # wird und nicht nur der Wechsel auf ein neues Ergebnis.
    Viewport.mark_finding(blind, (10.0, 5.0, 2.0), "Wandstärke 0,8 mm")

    Viewport._hide_finding_mark(blind)
    assert gelegt == [], f"nach der Frist steht nichts mehr: {gelegt}"
    assert blind._finding_actors == [], "und die Liste ist leer"
    assert blind._finding_mark is None, "auch der semantische Zustand ist abgelaufen"

    # Die Frist ist kurz genug, dass niemand sie für einen Zustand hält, und
    # lang genug, um die Stelle nach dem Flug zu finden.
    assert 1000 <= FINDING_MARK_MS <= 5000, FINDING_MARK_MS


def test_a_scene_rebuild_restores_only_a_visible_finding_mark(
    qt_app: QApplication,
) -> None:
    """Die echte Szenenmethode hält die Marke an Ergebnis und Sichtbarkeit.

    Der Fehler entstand nicht in den Zeichenhelfern allein: ``show_scene``
    räumt die nativen Aktoren beim Kartenaufbau ab. Deshalb fährt dieser Test
    den vollständigen Anschluss mit einer schreibenden Plotter-Attrappe. Er
    prüft zugleich den Filterfall — ein ausgeblendeter Körper bekommt keinen
    körperlosen Ring im Raum.
    """
    import dataclasses

    from app.ui.viewport import FINDING_MARK_MS, Viewport

    result = _scene_with_two_holes()
    viewport = Viewport()
    viewport.show_scene(result)
    plotter = _RecordingPlotter()
    viewport.plotter = plotter
    starts: list[int] = []
    stops: list[None] = []
    viewport._finding_timer = cast(
        Any,
        SimpleNamespace(start=starts.append, stop=lambda: stops.append(None)),
    )

    viewport.mark_finding((0.0, 0.0, 5.0), "Passung zu eng", "obj_1")
    first = tuple(viewport._finding_actors)
    stopped_after_mark = len(stops)
    assert len(first) == 2

    plotter.drawn.clear()
    viewport.show_scene(result)
    assert len(viewport._finding_actors) == 2
    assert tuple(viewport._finding_actors) != first, "der Neuaufbau zeichnet frische Aktoren"
    assert plotter.names().count("finding_ring") == 1
    assert plotter.names().count("finding_label") == 1
    assert starts == [FINDING_MARK_MS], "der Kartenaufbau verlängert die Frist nicht"
    assert len(stops) == stopped_after_mark, "der Kartenaufbau beendet die Frist nicht"

    viewport.set_hidden(frozenset({"obj_1"}))
    assert viewport._finding_mark is not None, "die kurze Restfrist darf weiterlaufen"
    assert viewport._finding_actors == [], "ohne Körper schwebt keine Marke im Raum"

    viewport.set_hidden(frozenset())
    assert len(viewport._finding_actors) == 2, "wieder sichtbar wird dieselbe Marke nachgezeichnet"
    assert starts == [FINDING_MARK_MS]

    viewport.set_plate(1)
    assert viewport._finding_mark is not None
    assert viewport._finding_actors == [], "auf einer anderen Platte bleibt der Raum leer"

    viewport.set_plate(-1)
    assert len(viewport._finding_actors) == 2, "in der Gesamtansicht kehrt die Marke zurück"
    assert starts == [FINDING_MARK_MS]

    changed = dataclasses.replace(result)
    viewport.show_scene(changed)
    assert viewport._finding_mark is None
    assert viewport._finding_actors == []
    assert len(stops) == stopped_after_mark + 1

    viewport.mark_finding((0.0, 0.0, 5.0), "Passung zu eng", "obj_1")
    viewport.show_scene(None)
    assert viewport._finding_mark is None
    assert viewport._finding_actors == []


def test_a_place_from_the_scene_is_shifted_into_the_view(qt_app: QApplication) -> None:
    """Ein Ort aus der Szene wird für die Ansicht verschoben — beide Richtungen.

    ``fly_to`` nahm seinen Punkt roh. Bei einem Körper auf Platte 2 liegt der
    eine Bettbreite neben dem, was der Kunde sieht (§25) — dieselbe
    Verwechslung, die beim Klick schon einmal eine Bohrung danebengesetzt hat,
    hier in der Gegenrichtung.
    """
    from types import SimpleNamespace

    from app.ui.viewport import Viewport

    blind = cast(Any, Viewport.__new__(Viewport))
    blind.plotter = None

    # Ohne Kennung und ohne Auswertung bleibt der Punkt, wie er ist: Ein
    # Versatz, den man nicht zuordnen kann, ist keiner.
    blind._result = None
    assert Viewport.view_point_of(blind, (1.0, 2.0, 3.0)) == (1.0, 2.0, 3.0)
    assert Viewport.view_point_of(blind, (1.0, 2.0, 3.0), "obj_1") == (1.0, 2.0, 3.0)

    eintrag = SimpleNamespace(id="obj_1")
    blind._result = SimpleNamespace(scene=SimpleNamespace(objects={"obj_1": eintrag}))
    blind._view_offset = lambda entry, result: [220.0, 0.0, 0.0]  # eine Bettbreite
    verschoben = Viewport.view_point_of(blind, (1.0, 2.0, 3.0), "obj_1")
    assert verschoben == (221.0, 2.0, 3.0), verschoben
    # Und ein unbekannter Körper verschiebt nichts — sonst versetzte ein
    # veralteter Befund die Marke ins Nirgendwo.
    assert Viewport.view_point_of(blind, (1.0, 2.0, 3.0), "obj_9") == (1.0, 2.0, 3.0)


def test_the_history_can_point_at_a_single_step_and_at_a_group(
    qt_app: QApplication,
) -> None:
    """``point_at`` findet den Schritt — auch wenn er in einer Transaktion steckt.

    Eine Transaktion aus mehreren Operationen trägt bewusst **keine**
    ``UserRole``: Ein Doppelklick müsste sonst raten, welcher der vier sich
    öffnen soll. Ihre Schritte stehen in ``OPS_ROLE`` am Gruppenknoten. Wer
    nur die ``UserRole`` liest, zeigt bei jedem Sammelschritt ins Leere — und
    das sind gerade die interessanten.
    """
    from PySide6.QtCore import Qt as QtNS
    from PySide6.QtWidgets import QListWidgetItem

    from app.ui.panels import OPS_ROLE, HistoryPanel

    panel = HistoryPanel()
    einzeln = QListWidgetItem("1  Bohrung setzen")
    einzeln.setData(QtNS.ItemDataRole.UserRole, 1)
    einzeln.setData(OPS_ROLE, (1,))
    gruppe = QListWidgetItem("Teilung in vier")
    gruppe.setData(OPS_ROLE, (2, 3, 4, 5))
    panel.list.addItem(einzeln)
    panel.list.addItem(gruppe)

    assert panel.point_at(1), "der einzelne Schritt wird über die UserRole gefunden"
    assert panel.list.currentItem() is einzeln

    assert panel.point_at(4), "ein Schritt in einer Transaktion über OPS_ROLE"
    assert panel.list.currentItem() is gruppe, (
        "bei einem Sammelschritt ist die Gruppenzeile die Antwort"
    )

    # Und was es nicht gibt, wird nicht behauptet: Der Aufrufer entscheidet
    # daran, ob er den Abschnitt überhaupt aufklappt.
    assert not panel.point_at(99)


def test_clicking_a_finding_is_never_without_an_answer() -> None:
    """Die Zusage von V6, an ihren drei Stufen im Quelltext festgehalten.

    Gemessen am 30.08.2026 über alle 58 Befunde der Beispielprojekte: **keiner**
    löste beim Klick eine sichtbare Reaktion aus. Zwei Ursachen — ein
    Operationsfehler trägt weder Ort noch Merkmale (der Kern gibt ihm
    ``object_id`` und ``op_id``), und der Ort eines Kartenbefunds steht erst
    fest, wenn die Karte gerechnet ist, was beim ersten Klick nie der Fall ist.

    Ein Test am gebauten Fenster wäre der bessere, und er liefe hier ins Leere:
    Die Kartenrechnung braucht einen Arbeiter-Thread, und der ist offscreen
    genau der Teil, der nicht läuft. Gelesen wird deshalb der Quelltext — wie
    bei den Setzstellen in ``test_cursors.py``. Er hält die drei Stufen
    auseinander; ob sie im Fenster greifen, ist gemessen und steht in der
    Roadmap.
    """
    import inspect

    from app.ui.main_window import MainWindow

    quelle = inspect.getsource(MainWindow._on_finding_activated)
    assert "point_at" in quelle, "Stufe 3: der Verlauf zeigt den gescheiterten Schritt"
    # **„ohne Ort" stand hier und war die falsche Lesart.** Die Stufen
    # schließen einander nicht aus: Auch mit Ort wird der Körper ausgewählt.
    # Der Code führte sie exklusiv aus (ein `return` nach dem Flug), und dieser
    # Wächter sah es nicht — er sucht den Aufruf im Quelltext, und der stand
    # da; er lief nur nicht. Die Wirkung prüft jetzt
    # `test_a_click_with_a_place_also_selects_the_body` in `test_analysis_ui`.
    assert "select_object" in quelle, "Stufe 2: der Körper wird ausgewählt"
    assert "_finding_awaiting_map" in quelle, (
        "Stufe 1: der Klick merkt sich, dass er auf eine Karte wartet"
    )

    nachgeholt = inspect.getsource(MainWindow._map_ready)
    assert "_show_finding_at" in nachgeholt, (
        "die fertige Karte holt den Flug nach — sonst ist der erste Klick "
        "immer folgenlos und der zweite tut es"
    )

    zeigen = inspect.getsource(MainWindow._show_finding_at)
    assert "view_point_of" in zeigen, "aus der Szene in die Ansicht (§25)"
    assert "mark_finding" in zeigen, "und am Ziel steht eine Marke"


# --- die Schraffur einer geschützten Sichtfläche (T8, Regel 18) -------------------


def quadrat(normale: str) -> Any:
    """Ein 10-mm-Quadrat aus zwei Dreiecken, in der Ebene quer zur Normalen.

    Als Eckpunktliste je Dreieck, genau wie der Merkmals-Patch sie baut: drei
    Zeilen je Dreieck, geteilte Ecken doppelt.
    """
    import numpy as np

    flach = np.array(
        [
            [0.0, 0.0],
            [10.0, 0.0],
            [10.0, 10.0],
            [0.0, 0.0],
            [10.0, 10.0],
            [0.0, 10.0],
        ]
    )
    leer = np.zeros((6, 1))
    if normale == "z":
        return np.hstack([flach, leer])
    if normale == "x":
        return np.hstack([leer, flach])
    return np.hstack([flach[:, :1], leer, flach[:, 1:]])


def test_the_hatch_covers_the_face_at_the_asked_spacing() -> None:
    """Die Striche liegen in der Fläche, im verlangten Abstand.

    Der Nullpunkt: Zehn Millimeter Fläche, zwei Millimeter Abstand, also vier
    Striche dazwischen. Sie liegen in der Ebene der Fläche und innerhalb ihrer
    Grenzen — eine Schraffur, die über den Rand ragt, wäre keine.
    """
    import numpy as np

    from app.ui.viewport import hatch_lines

    segmente = hatch_lines(quadrat("z"), (0.0, 0.0, 1.0), 2.0)

    assert segmente, "eine 10-mm-Fläche trägt bei 2 mm Abstand Striche"
    punkte = np.array([ort for strich in segmente for ort in strich])
    assert np.allclose(punkte[:, 2], 0.0), "die Striche liegen in der Fläche"
    assert punkte[:, 0].min() >= -1e-9 and punkte[:, 0].max() <= 10.0 + 1e-9
    assert punkte[:, 1].min() >= -1e-9 and punkte[:, 1].max() <= 10.0 + 1e-9
    hoehen = sorted({round(float(wert), 6) for wert in punkte[:, 1]})
    assert hoehen == [2.0, 4.0, 6.0, 8.0], f"vier Striche im Abstand zwei, gefunden {hoehen}"


def test_the_hatch_works_on_any_orientation() -> None:
    """**Der Fall, an dem eine feste Achse scheitert.**

    Wer quer zu ``z`` schneidet, bekommt auf einer Fläche, die selbst in der
    xy-Ebene liegt, keinen einzigen Schnittpunkt: Die Ebenen lägen parallel
    zur Fläche. Die Schnittrichtung kommt deshalb aus der Normalen, und dieser
    Test fährt alle drei Lagen.
    """
    from app.ui.viewport import hatch_lines

    for richtung, normale in (
        ("z", (0.0, 0.0, 1.0)),
        ("x", (1.0, 0.0, 0.0)),
        ("y", (0.0, 1.0, 0.0)),
    ):
        segmente = hatch_lines(quadrat(richtung), normale, 2.0)
        assert len(segmente) >= 4, f"Fläche mit Normale {richtung}: {len(segmente)} Striche"


def test_a_face_smaller_than_the_spacing_stays_bare() -> None:
    """Kein Strich ist besser als einer, der die Fläche halbiert.

    Bei einer Fläche, die schmaler ist als der Abstand, trägt die Schraffur
    nichts zur Lesbarkeit bei — sie sähe wie eine Kante aus.
    """
    from app.ui.viewport import hatch_lines

    assert hatch_lines(quadrat("z"), (0.0, 0.0, 1.0), 20.0) == []
    assert hatch_lines(quadrat("z"), (0.0, 0.0, 1.0), 0.0) == []
    assert hatch_lines(quadrat("z"), (0.0, 0.0, 0.0), 2.0) == [], "ohne Normale keine Richtung"


def test_the_hatch_stays_within_its_limit() -> None:
    """Eine große Fläche mit engem Abstand kostet sonst beim Drehen.

    Ohne Deckel ergäben zehn Millimeter bei 0,01 Abstand tausend Striche, und
    keiner davon sagt mehr als der vorige.
    """
    from app.ui.viewport import hatch_lines

    segmente = hatch_lines(quadrat("z"), (0.0, 0.0, 1.0), 0.01, limit=12)

    hoehen = {round(strich[0][1], 6) for strich in segmente}
    assert len(hoehen) <= 12, f"höchstens zwölf Striche, gefunden {len(hoehen)}"
    assert len(hoehen) >= 10, "und nicht plötzlich gar keine mehr"


def test_a_protected_face_is_remembered_and_released(qt_app: QApplication) -> None:
    """Sperren, freigeben, und die Auskunft dazu (T8, §22.3).

    ``set_protected`` läuft vor der Plotter-Wache zu Ende: Die Markierung ist
    eine Aussage über das Werkstück, das Zeichnen ist die Folge davon. Deshalb
    ist sie offscreen prüfbar, und deshalb steht sie hier.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    assert viewport.protected_features("obj_1") == ()

    viewport.set_protected("obj_1", "face_3", True)
    viewport.set_protected("obj_1", "face_7", True)
    assert viewport.protected_features("obj_1") == ("face_3", "face_7")
    assert viewport.protected_features("obj_2") == (), "eine Sperre gehört ihrem Körper"

    viewport.set_protected("obj_1", "face_3", False)
    assert viewport.protected_features("obj_1") == ("face_7",)

    viewport.set_protected("obj_1", "face_7", False)
    assert viewport.protected_features("obj_1") == ()
    assert not viewport._protected, "der leere Eintrag bleibt nicht als Karteileiche stehen"


def test_without_a_scene_there_are_no_protected_patches(qt_app: QApplication) -> None:
    """Ohne Auswertung gibt es keine Punkte — und keine Ausnahme.

    ``protected_patches`` ist die Eingabe der Nahtsuche. Sie wird auch dann
    gerufen, wenn gerade nichts gerechnet ist; eine leere Liste ist dann die
    richtige Antwort und ein Absturz die falsche.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_protected("obj_1", "face_3", True)

    assert viewport.protected_patches("obj_1") == []


def test_the_pocket_preview_starts_at_the_top_of_the_body(qt_app: QApplication) -> None:
    """Umriss auf dem Bett, Teil darüber: Die Drahtform wächst von der Oberkante nach unten.

    Bis zum 02.09.2026 wuchs sie von der Zeichenebene in die Luft unter dem
    Teil, während ``sketch_pocket`` oben schnitt — Tiefe richtig, Ort falsch.
    Nach außen bleibt die Zeichenebene der Ausgangspunkt.
    """
    from app.core.sketch.planes import frame_of
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport._sketch_frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    viewport.set_sketch_pull(
        lambda: "ready", (0.1, 1000.0), (0.1, 1000.0), lambda: True, lambda: 20.0
    )

    viewport._pull_height = -5.0
    lowered = viewport._pull_frame()
    assert lowered.origin[2] == pytest.approx(20.0)
    assert lowered.normal == viewport._sketch_frame.normal

    viewport._pull_height = 5.0
    assert viewport._pull_frame() is viewport._sketch_frame

    viewport.set_sketch_pull(
        lambda: "ready", (0.1, 1000.0), (0.1, 1000.0), lambda: True, lambda: 0.0
    )
    viewport._pull_height = -5.0
    assert viewport._pull_frame() is viewport._sketch_frame, "Ebene ist Oberkante: nichts zu heben"


def test_a_cut_through_an_editable_body_still_shows_it(qt_app: QApplication) -> None:
    """Ein Schnitt durch einen B-Rep-Körper zeigt ihn — er verschwindet nicht.

    **Der Fall, wie Robert ihn gemeldet hat (03.09.2026):** Ein selbst
    gezeichnetes Teil, im Objektbaum als „weiter bearbeitbar" geführt, also
    ein ``Solid`` aus dem zweiten Kern. Knopf *Schnitt*, Regler in die Mitte —
    und die Bühne war leer. Kein Fehler, keine Meldung, kein Modell.

    Die Ursache lag im Weg dorthin: ``cut`` arbeitet auf ``MeshData``, liest
    ``mesh.slots`` und setzt sein Ergebnis über ``replacing`` ein. Ein
    ``Solid`` führt stattdessen ``slot_indices``, und sein ``replacing``
    erwartet eine OCC-Form. Der Aufbau der Ansicht brach mit
    ``AttributeError: 'Solid' object has no attribute 'slots'`` ab, **nachdem**
    die alten Aktoren entfernt waren — daher die leere Bühne statt einer
    Fehlermeldung.

    Geprüft wird deshalb das, was der Kunde sieht: dass nach dem Schnitt
    überhaupt noch etwas gezeichnet ist. Die Gegenprobe (Vernetzung
    herausgenommen) lässt die Zusicherung unten fallen.
    """
    from app.core.geom.section import SectionPlane
    from app.ui.viewport import Viewport

    class _Solid:
        """So viel ``Solid``, wie der Schnittweg anfasst — ohne OpenCASCADE."""

        def __init__(self, mesh: MeshData) -> None:
            self._mesh = mesh

        @property
        def raw(self) -> Any:
            return self._mesh.raw

        @property
        def triangle_count(self) -> int:
            return self._mesh.triangle_count

        @property
        def bounds(self) -> Any:
            return self._mesh.bounds

        @property
        def slot_indices(self) -> tuple[int, ...]:
            return ()

        def to_mesh(self) -> MeshData:
            return self._mesh

        def replacing(self, shape: Any) -> Any:
            raise AssertionError("ein Solid nimmt kein Netz — hier wird vorher vernetzt")

    viewport = Viewport()
    körper = _Solid(MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 16.0))))
    viewport._section = SectionPlane(normal=(0.0, 0.0, 1.0), position=0.0)

    geschnitten = viewport._sectioned(körper)

    assert geschnitten is not körper, "ohne Vernetzung geht der Schnitt gar nicht erst los"
    assert len(geschnitten.raw.faces) > 0, "nach dem Schnitt bleibt Geometrie übrig"
    assert float(geschnitten.raw.bounds[1][2]) <= 0.0 + 1e-9, "und sie liegt unter der Ebene"


def test_the_last_measurement_can_go_without_taking_the_others(qt_app: QApplication) -> None:
    """Ein falsch gesetztes Maß geht einzeln — nicht die ganze Reihe mit.

    **Der Befund (Robert, 03.09.2026):** „das messen lässt sich auch nicht
    verschieben oder wieder löschen". Es gab genau einen Weg, ein Maß
    loszuwerden: *Bemaßungen löschen*, und der nimmt alle. Wer nach dem
    fünften Maß einmal danebenklickte, verlor die vier davor mit.

    Zwei Fälle, und die Reihenfolge ist die Aussage: Ein **halb gesetztes**
    Maß zählt zuerst. Wer den ersten Punkt gesetzt hat und die Rücktaste
    drückt, meint diesen Punkt — nicht das fertige Maß davor, das er gerade
    behalten will.
    """
    from app.core.geom.measure import Measurement
    from app.ui.viewport import Viewport

    viewport = Viewport()
    for index in range(3):
        viewport.measurements.add(
            Measurement(kind="distance", value=float(index + 1), points=((0.0, 0.0, 0.0),))
        )
    assert len(viewport.measurements.entries) == 3

    viewport.undo_measurement()

    assert [entry.value for entry in viewport.measurements.entries] == [1.0, 2.0], (
        "nur das letzte Maß geht"
    )

    viewport._pending_point = (1.0, 2.0, 3.0)
    viewport.undo_measurement()

    assert viewport._pending_point is None, "der halb gesetzte Punkt geht zuerst"
    assert len(viewport.measurements.entries) == 2, "und kostet kein fertiges Maß"

    viewport.undo_measurement()
    viewport.undo_measurement()
    viewport.undo_measurement()

    assert viewport.measurements.entries == [], "und die leere Liste hält es aus"


#: Ein Fangergebnis, das mehrere Tests hier gemeinsam benutzen.
_SNAP = SnapResult(point=(7.0, 8.0, 9.0), kind="vertex", distance=0.5)


def test_the_snap_reach_keeps_the_same_width_on_screen(qt_app: QApplication) -> None:
    """Die Fangweite wird in Bildpunkten gedacht, nicht in Millimetern.

    **Der Befund (Robert, 03.09.2026):** „bei messen ist das zielen relativ
    schwer". Der Kern fängt in zwei Prozent der Modelldiagonale — an einem
    200 mm langen Teil vier Millimeter. Das ist keine feste Größe für eine
    Zielgeste: Herangezoomt sind vier Millimeter zweihundert Bildpunkte, und
    der Fang reißt den Punkt quer über die Fläche; herausgezoomt sind es zwei,
    und es gibt praktisch keinen Fang mehr.

    Geprüft wird die Umkehrung: Doppelt so viele Bildpunkte je Millimeter
    heißt halb so viel Millimeter Fangweite — im Bild also unverändert. Und
    ohne Bild kommt ``None`` zurück, damit der Kern bei seiner eigenen Weite
    bleibt statt durch null zu teilen.
    """
    from app.ui.viewport import MEASURE_SNAP_PIXELS, Viewport

    viewport = Viewport()
    assert viewport._snap_radius_at((0.0, 0.0, 0.0)) is None, (
        "ohne Bild gibt es keine Bildpunkte, in denen man rechnen könnte"
    )

    for scale in (4.0, 8.0):
        viewport._pixels_per_mm_at = lambda _point, _scale=scale: _scale  # type: ignore[method-assign]
        gemessen = viewport._snap_radius_at((0.0, 0.0, 0.0))
        assert gemessen is not None
        assert abs(gemessen * scale - MEASURE_SNAP_PIXELS) < 1e-9, (
            f"bei {scale} Bildpunkten je Millimeter sind {gemessen} mm nicht "
            f"{MEASURE_SNAP_PIXELS} Bildpunkte"
        )


def test_the_snap_pulls_to_a_corner_only_within_its_reach(qt_app: QApplication) -> None:
    """Der Fang zieht auf die Ecke, wenn sie in Reichweite ist — sonst nicht.

    Die Reichweite ist das Ganze an dieser Sache, und sie kommt jetzt aus dem
    Bild (:meth:`Viewport._snap_radius_at`). Also wird sie hier gesetzt und
    beide Seiten geprüft: derselbe Klick, einmal mit großzügiger Weite auf der
    Ecke, einmal mit enger Weite frei auf der Fläche.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.viewport import Viewport

    viewport = Viewport()
    mesh = MeshData(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    viewport._result = EvaluationResult(
        scene=Scene(objects={"obj_1": SceneObject(id="obj_1", name="A", mesh=mesh)})
    )
    # Auf der Deckfläche, zwei Millimeter von beiden Randkanten entfernt und
    # damit 2,83 mm von der Ecke (20, 20, 5). Drei Weiten, drei Antworten.
    daneben = (18.0, 18.0, 5.0)

    viewport._snap_radius_at = lambda _point: 4.0  # type: ignore[method-assign]
    nah = viewport._snap_for_measure(daneben)
    assert nah is not None and nah.kind == "vertex", f"in Reichweite wird die Ecke genommen: {nah}"
    assert nah.point == (20.0, 20.0, 5.0)

    viewport._snap_radius_at = lambda _point: 2.5  # type: ignore[method-assign]
    mitte = viewport._snap_for_measure(daneben)
    assert mitte is not None and mitte.kind == "edge", (
        f"zu weit für die Ecke, nah genug an der Kante: {mitte}"
    )

    viewport._snap_radius_at = lambda _point: 0.5  # type: ignore[method-assign]
    fern = viewport._snap_for_measure(daneben)
    assert fern is not None and fern.kind == "free", f"außer Reichweite bleibt der Klick: {fern}"
    assert fern.point == daneben

    viewport._result = None
    assert viewport._snap_for_measure(daneben) is None, (
        "ohne Auswertung gibt es keinen Körper und nichts zu fangen"
    )


def test_the_pointer_shows_where_the_measuring_click_would_land(qt_app: QApplication) -> None:
    """Der Zeiger stellt beim Messen dieselbe Frage wie der Klick.

    Dieselbe Zusage wie bei der gestuften Auswahl: Eine Vorschau, die woanders
    fängt als der Klick, verspricht etwas, das nicht eintritt. Geprüft wird
    deshalb nicht, dass *irgendetwas* gezeichnet wird, sondern dass die
    Ruhepause **dieselbe Rechnung mit demselben Punkt** anstößt — und dass sie
    beim Messen die Merkmalssuche gar nicht erst fragt.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.plotter = SimpleNamespace(  # type: ignore[assignment]
        renderer=None, interactor=SimpleNamespace(setCursor=lambda shape: None)
    )
    viewport._hover_at = (120, 80)
    viewport.set_measure_mode("distance")

    gefragt: list[Any] = []
    gemerkt: list[Any] = []
    viewport._world_at = lambda x, y: (7.0, 8.0, 9.0)  # type: ignore[method-assign]
    viewport._snap_for_measure = lambda point: gefragt.append(point) or _SNAP  # type: ignore[method-assign]
    viewport._draw_snap_preview = lambda found: gemerkt.append(found)  # type: ignore[method-assign]
    viewport._aim_at = lambda x, y: pytest.fail("beim Messen wird kein Merkmal gesucht")  # type: ignore[method-assign]

    viewport._look_under_pointer()

    assert gefragt == [(7.0, 8.0, 9.0)], "der Zeiger fragt den Fang an der Stelle des Klicks"
    assert gemerkt == [_SNAP], "und zeigt, was dabei herauskommt"

    # Und wo nichts unter dem Zeiger liegt, bleibt keine Marke stehen.
    weg: list[str] = []
    viewport._world_at = lambda x, y: None  # type: ignore[method-assign]
    viewport._clear_snap_preview = lambda: weg.append("weg")  # type: ignore[method-assign]
    viewport._look_under_pointer()
    assert weg == ["weg"], "über dem Leeren verschwindet die Marke"


def test_the_snap_mark_says_what_it_caught_without_colour(qt_app: QApplication) -> None:
    """Worauf gefangen wurde, steht in der Größe und in einem Satz.

    Farbe trägt hier gar keine Bedeutung — die Marke ist immer in der Messfarbe
    (Regel 18). Unterschieden wird über die Länge der Arme, und wer nicht
    sieht, bekommt denselben Unterschied als Satz in der Beschreibung der
    Ansicht. Beides muss drei verschiedene Antworten geben, sonst ist die
    Auskunft keine.
    """
    from app.ui.viewport import SNAP_MARK_PIXELS, Viewport, snap_sentence

    laengen = [SNAP_MARK_PIXELS[art] for art in ("vertex", "edge", "free")]
    assert laengen == sorted(laengen, reverse=True), (
        f"eine Ecke bekommt den größten Stern, eine freie Stelle den kleinsten: {laengen}"
    )
    assert len(set(laengen)) == 3, "drei Arten, drei Größen"

    saetze = {snap_sentence(art) for art in ("vertex", "edge", "free")}
    assert len(saetze) == 3, f"drei Arten, drei Sätze: {saetze}"
    assert all(satz.strip() for satz in saetze), "und keiner davon leer"

    # Und die Marke geht mit dem Werkzeug: Wer das Messen verlässt, lässt
    # keinen Stern im Bild stehen.
    viewport = Viewport()
    viewport._snap_shown = _SNAP
    viewport.set_measure_mode("off")
    assert viewport.snap_preview is None, "das Werkzeug nimmt seine Marke mit"


def test_a_dimension_on_the_second_plate_follows_its_body(qt_app: QApplication) -> None:
    """Ein Maß liegt in der Szene und steht im Bild — die zwei Orte sind
    verschieden, sobald ein zweites Bett danebensteht (§25).

    `arrange_bed` setzt Platte 2 an denselben Nullpunkt wie Platte 1, denn
    beide werden einzeln gedruckt; gezeichnet werden sie nebeneinander. Ein Maß
    an einem Körper auf Platte 2 lag deshalb eine Bettbreite neben dem Teil,
    das es misst — die Ansicht rechnete für Körper, Merkmalsflächen und Griffe
    um und für Maße nicht.

    **Und die Zuordnung ist der schwierige Teil, nicht die Rechnung.** In der
    Szene liegen die zwei Platten *übereinander*: Ein Punkt (18, 18, 5) gehört
    zu beiden Körpern, und aus ihm allein lässt sich die Platte nicht ablesen.
    Der Klick weiß es, weil er aus dem Bild kommt — deshalb merkt sich das Maß
    seine Kennung je Punkt (`Measurement.object_ids`), und deshalb fragt der
    Viewport sie über `_object_at_view` und nicht über `_object_at`.
    """
    import dataclasses

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.viewport import Viewport

    viewport = Viewport()
    mesh = MeshData(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    erste = SceneObject(id="obj_1", name="A", mesh=mesh)
    zweite = dataclasses.replace(erste, id="obj_2", name="B", plate=1)
    viewport._result = EvaluationResult(scene=Scene(objects={"obj_1": erste, "obj_2": zweite}))
    # So, wie ``show_build_volume`` es hinterlässt: zwei Betten gezeichnet,
    # keine einzelne Platte gewählt.
    viewport._beds_drawn = 2
    viewport._plate = -1
    viewport._bed_extent = (220.0, 220.0)

    stelle = (18.0, 18.0, 5.0)

    assert viewport._object_at(stelle) == "obj_1", (
        "in der Szene liegen beide Körper an derselben Stelle — die Frage ist "
        "dort gar nicht zu beantworten"
    )
    assert viewport._object_at_view(stelle) == "obj_1", "im Bild liegt dort Platte 1"
    weiter = (stelle[0] + 220.0 + PLATE_GAP, stelle[1], stelle[2])
    assert viewport._object_at_view(weiter) == "obj_2", "und eine Bettbreite weiter Platte 2"

    auf_eins = viewport.view_point_of(stelle, "obj_1")
    auf_zwei = viewport.view_point_of(stelle, "obj_2")
    assert auf_eins == stelle, "die erste Platte bleibt, wo sie ist"
    assert auf_zwei[0] > stelle[0] + 200.0, f"die zweite steht daneben: {auf_zwei}"
    assert auf_zwei[1] == stelle[1] and auf_zwei[2] == stelle[2], "und nur nach +X"

    # Mit einer einzeln betrachteten Platte steht wieder ein Bett im Bild,
    # und dann gehört auch ihr Punkt an seinen Ort.
    viewport._plate = 1
    assert viewport.view_point_of(stelle, "obj_2") == stelle, (
        "eine Platte allein wird nicht verschoben"
    )

    # Und ohne Kennung bleibt der Punkt, wie er ist — ein Versatz, den man
    # nicht zuordnen kann, ist keiner.
    viewport._plate = -1
    assert viewport.view_point_of(stelle, "") == stelle


def test_a_measuring_click_writes_down_which_body_it_hit(qt_app: QApplication) -> None:
    """Die Kennung wird beim Klick gemerkt — sonst nützt sie beim Zeichnen nichts.

    Das ist das letzte Glied der Kette aus dem Test darüber: `view_point_of`
    kann noch so richtig rechnen, wenn `_on_picked` seine Kennung nicht
    mitschreibt. Gemessen wird deshalb am fertigen `Measurement` und nicht an
    der Rechnung davor.

    Zwei Klicks auf **verschiedene** Platten, weil das der Fall ist, für den es
    die Kennung je Punkt überhaupt gibt: Ein Maß darf zwei Körper verbinden.
    """
    import dataclasses

    import trimesh

    from app.core.geom.measure import SnapResult
    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.viewport import Viewport

    viewport = Viewport()
    mesh = MeshData(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    erste = SceneObject(id="obj_1", name="A", mesh=mesh)
    zweite = dataclasses.replace(erste, id="obj_2", name="B", plate=1)
    viewport._result = EvaluationResult(scene=Scene(objects={"obj_1": erste, "obj_2": zweite}))
    viewport._beds_drawn = 2
    viewport._plate = -1
    viewport._bed_extent = (220.0, 220.0)
    viewport.set_measure_mode("distance")

    # Der Fang gibt den Punkt unverändert zurück; hier geht es um die Kennung.
    viewport._snap_for_measure = lambda point: SnapResult(point=point, kind="free")  # type: ignore[method-assign]

    auf_eins = (18.0, 18.0, 5.0)
    auf_zwei = (18.0 + 220.0 + PLATE_GAP, 18.0, 5.0)
    viewport._on_picked(auf_eins)
    assert viewport._pending_owner == "obj_1", "der erste Punkt merkt seinen Körper"
    viewport._on_picked(auf_zwei)

    assert len(viewport.measurements.entries) == 1
    mass = viewport.measurements.entries[0]
    assert mass.object_ids == ("obj_1", "obj_2"), (
        f"beide Kennungen gehören ans Maß, in der Reihenfolge der Klicks: {mass.object_ids}"
    )
    assert viewport._pending_owner == "", "und danach ist nichts mehr halb gesetzt"

    # Der zweite Punkt liegt in der Szene an derselben Stelle wie der erste —
    # die Zahl misst also nur die Rückrechnung aus dem Bild.
    assert mass.value == pytest.approx(0.0, abs=1e-9), (
        "beide Platten liegen in der Szene übereinander, der Abstand ist null"
    )


def test_the_candidates_of_a_question_are_shown_and_taken_back(
    qt_app: QApplication,
) -> None:
    """Eine mehrdeutige Frage zeigt, wovon sie redet (§21.3).

    Der Bauplan verlangt es wörtlich — „zeigt die Kandidaten hervorgehoben und
    fragt über `ctx.ask`" —, und gebaut war alles außer der Hervorhebung: Der
    Dialog nannte `hole_1`, `hole_2`, `hole_3`, und der Kunde sollte zwischen
    drei Bohrungen entscheiden, die er nicht sieht (Fund 3d-druck-a0).

    Geprüft wird die Auskunft und ihre Rücknahme. **Paare und nicht
    Kennungen**: Merkmalskennungen sind je Körper vergeben, und beim leeren
    Objektnamen sucht `orphans._candidates` über alle Körper — zwei `hole_1`
    an zwei Körpern sind zwei Fundorte, nicht einer.
    """
    import dataclasses

    from app.ui.viewport import Viewport

    viewport = Viewport()
    ergebnis = _scene_with_two_holes()
    zweiter = dataclasses.replace(ergebnis.scene.objects["obj_1"], id="obj_2", name="B")
    ergebnis.scene.objects["obj_2"] = zweiter
    viewport.show_scene(ergebnis)

    assert viewport.candidates == (), "ohne Frage leuchtet nichts"

    viewport.show_candidates((("obj_1", "hole_1"), ("obj_2", "hole_1")))
    assert viewport.candidates == (("obj_1", "hole_1"), ("obj_2", "hole_1")), (
        "dieselbe Kennung an zwei Körpern sind zwei Kandidaten"
    )

    viewport.show_candidates(
        (("obj_1", "hole_1"), ("obj_1", "hole_2")), emphasis=("obj_1", "hole_2")
    )
    assert viewport._candidate_emphasis == ("obj_1", "hole_2"), (
        "die markierte Zeile im Dialog ist der betonte Kandidat"
    )

    viewport.show_candidates()
    assert viewport.candidates == (), "und die leere Folge nimmt alles zurück"

    # Eine neue Auswertung nimmt sie ebenfalls mit: Sie zeigen auf Dreiecke
    # einer bestimmten Auswertung, und danach kann dieselbe Kennung eine
    # andere Fläche meinen.
    viewport.show_candidates((("obj_1", "hole_1"),))
    viewport.show_scene(_scene_with_two_holes())
    assert viewport.candidates == (), "eine neue Auswertung räumt die Frage weg"


class _DepthActor:
    """So viel Aktor, wie die Tiefenordnung anfasst."""

    def __init__(self, centre: tuple[float, float, float]) -> None:
        self._centre = centre

    def GetCenter(self) -> tuple[float, float, float]:  # noqa: N802 — VTK-Name
        return self._centre


class _DepthRenderer:
    """Der Renderer als Liste: Wer wird wann gezeichnet?"""

    def __init__(self) -> None:
        self.order: list[object] = []

    def RemoveActor(self, actor: object) -> None:  # noqa: N802 — VTK-Name
        if actor in self.order:
            self.order.remove(actor)

    def AddActor(self, actor: object) -> None:  # noqa: N802 — VTK-Name
        self.order.append(actor)


def test_transparent_bodies_are_drawn_from_back_to_front(qt_app: QApplication) -> None:
    """Ein durchsichtiges Bild darf nicht davon abhängen, in welcher
    Reihenfolge die Körper entstanden sind.

    **Der Befund, im Bild gemessen (Robert, 03.09.2026):** Zwei transparente
    Quader hintereinander, dieselbe Szene in zwei Einfügereihenfolgen — 13 784
    Bildpunkte Unterschied, größte Abweichung 47 von 255. VTK mischt
    transluzente Flächen in der Reihenfolge der Prop-Sammlung, und die folgt
    dem Anlegen (Quelltextfund 3d-druck-85).

    Zwei andere Wege sind gemessen und gescheitert: `enable_depth_peeling`
    nimmt an und fährt nicht, `vtkDepthSortPolyData` sortiert innerhalb eines
    Körpers statt zwischen zweien. Die Aktoren selbst umzuhängen gibt **0**
    Bildpunkte Unterschied.

    Geprüft wird hier die Ordnung und die Wache davor — offscreen gibt es
    keinen Plotter, also steht die Reihenfolge in einer Attrappe, die genau
    die zwei Methoden kennt, die benutzt werden.
    """
    from types import SimpleNamespace

    from app.ui.viewport import Viewport

    viewport = Viewport()
    nah = _DepthActor((0.0, -30.0, 0.0))
    fern = _DepthActor((0.0, 30.0, 0.0))
    renderer = _DepthRenderer()
    renderer.order = [nah, fern]
    viewport._actors = {"nah": nah, "fern": fern}  # type: ignore[assignment]
    viewport.plotter = SimpleNamespace(  # type: ignore[assignment]
        renderer=renderer,
        camera=SimpleNamespace(GetPosition=lambda: (0.0, -500.0, 0.0)),
    )

    # Massiv: der Tiefenpuffer ordnet, hier gibt es nichts zu tun.
    assert not viewport.sees_through
    viewport._order_by_depth()
    assert renderer.order == [nah, fern], "ohne Durchsicht bleibt alles, wie es ist"

    # Der Modus wird hier gesetzt und nicht geschaltet: ``set_display_mode``
    # baut die ganze Szene neu auf, und die Attrappe kennt genau die zwei
    # Methoden, um die es geht. Dass der Schalter den Modus setzt, prüft der
    # Test daneben.
    viewport._mode = "transparent"
    assert viewport.sees_through
    viewport._order_by_depth()
    assert renderer.order == [fern, nah], (
        "durchsichtig wird von hinten nach vorn gezeichnet — der ferne zuerst"
    )

    # Zweiter Aufruf bei unveränderter Kamera: keine Arbeit. Die Methode hängt
    # an ``_draw`` und läuft bei jedem Bild.
    # **Verkehrt herum gelegt**, damit die Probe den Fall trifft: In richtiger
    # Ordnung sähe ein zweiter Durchgang genauso aus wie keiner, und die
    # Zusicherung wäre auch ohne Wache grün.
    renderer.order = ["fremd", nah, fern]  # type: ignore[list-item]
    viewport._order_by_depth()
    assert renderer.order == ["fremd", nah, fern], "ohne Kamerabewegung wird nichts angefasst"

    # Und wenn die Kamera auf die andere Seite geht, dreht sich die Ordnung um.
    viewport.plotter.camera = SimpleNamespace(GetPosition=lambda: (0.0, 500.0, 0.0))
    renderer.order = [fern, nah]
    viewport._order_by_depth()
    assert renderer.order == [nah, fern], "von der anderen Seite ist der andere hinten"

    # Der Skizzenmodus zählt ebenso: Er stellt den Körper leise, damit die
    # Zeichnung darauf lesbar bleibt.
    viewport._mode = "solid"
    assert not viewport.sees_through
    viewport._sketch_frame = object()
    assert viewport.sees_through


class _BedSurface:
    """So viel Bettfläche, wie die Durchsicht anfasst."""

    def __init__(self) -> None:
        self.prop = SimpleNamespace(opacity=1.0)


def test_the_bed_lets_a_sunken_body_show_through(qt_app: QApplication) -> None:
    """Ein Teil unter der Druckplatte war vollständig unsichtbar.

    **Gemessen am laufenden Fenster (03.09.2026):** Ein Quader von 40 auf 40
    auf 30 mm, 35 mm unter Z=0, von schräg oben gezählt — **1** Bildpunkt von
    263 583. Ohne die Bettfläche wären es alle. Wer sein Modell versenkt oder
    falsch positioniert hat, sah davon nichts und merkte es beim Slicen
    (Robert: „dass man die Modelle auch unter dem Bett durchsehen sollte").

    **Nur wenn wirklich etwas darunter liegt** — so hat Robert es gestellt,
    und damit stellt sich die Frage nach dem Kontaktschatten gar nicht: Über
    einer leeren Platte bleibt sie deckend.

    Geprüft wird die Regel, die Anwendung und die Rücknahme. Die Bettfläche
    ist eine Attrappe mit genau der einen Eigenschaft, die angefasst wird —
    offscreen gibt es keinen Plotter.
    """
    import dataclasses

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.viewport import BED_SUNKEN_OPACITY, Viewport

    viewport = Viewport()
    flaeche = _BedSurface()
    viewport._bed_surfaces = [flaeche]  # type: ignore[list-item]

    assert not viewport.sunken_body(), "ohne Auswertung liegt nichts unter der Platte"

    oben = SceneObject(
        id="oben",
        name="oben",
        mesh=MeshData(
            trimesh.creation.box(extents=(40.0, 40.0, 30.0)).apply_translation((0.0, 0.0, 15.0))
        ),
    )
    viewport._result = EvaluationResult(scene=Scene(objects={"oben": oben}))
    assert not viewport.sunken_body(), "ein Körper auf der Platte ragt nicht darunter"
    viewport._apply_bed_transparency()
    assert flaeche.prop.opacity == 1.0, "und dann bleibt die Platte deckend"
    assert not viewport.sees_through

    unten = dataclasses.replace(
        oben,
        id="unten",
        mesh=MeshData(
            trimesh.creation.box(extents=(40.0, 40.0, 30.0)).apply_translation((0.0, 0.0, -20.0))
        ),
    )
    viewport._result = EvaluationResult(scene=Scene(objects={"unten": unten}))
    assert viewport.sunken_body(), "dieser ragt darunter"
    viewport._apply_bed_transparency()
    assert flaeche.prop.opacity == BED_SUNKEN_OPACITY, "und dann scheint die Platte durch"
    assert viewport.sees_through, (
        "eine durchscheinende Fläche unter allen Körpern braucht die Tiefenordnung"
    )

    # Und zurück: Wer sein Teil wieder heraufholt, bekommt seine Platte wieder.
    viewport._result = EvaluationResult(scene=Scene(objects={"oben": oben}))
    viewport._apply_bed_transparency()
    assert flaeche.prop.opacity == 1.0

    # Ein ausgeblendeter Körper zählt nicht — was nicht im Bild ist, kann
    # niemand meinen (§18.8).
    viewport._result = EvaluationResult(scene=Scene(objects={"unten": unten}))
    assert viewport.sunken_body()
    viewport._hidden = frozenset({"unten"})
    assert not viewport.sunken_body(), "ausgeblendet ist nicht unter der Platte"


class _FramingPlotter:
    """So viel Plotter, wie das Einpassen anfasst: es rahmt und merkt sich das."""

    def __init__(self) -> None:
        self.framed: list[tuple[float, ...] | None] = []
        self.camera_set = False

    def reset_camera(self, bounds: tuple[float, ...] | None = None) -> None:
        self.framed.append(bounds)


def test_fitting_frames_the_chosen_body(qt_app: QApplication) -> None:
    """Pos1 zeigt das gewählte Teil, nicht wieder die ganze Baugruppe.

    **Roberts Entscheidung vom 03.09.2026.** Wer ein Teil aus einer Baugruppe
    anklickt und Pos1 drückt, will es formatfüllend sehen. Ohne Auswahl bleibt
    es beim Alten — das war Teil der Frage, damit nichts wegfällt, was heute
    funktioniert.

    Drei Dinge hängen daran, und alle drei stehen hier:

    * **Der Versatz gehört dazu.** Ein auseinandergezogener Körper oder einer
      auf der zweiten Platte wird anderswo gezeichnet, als er in der Szene
      liegt; ohne ihn rahmte die Kamera die leere Stelle.
    * **Was nicht im Bild ist, wird nicht gerahmt** (§18.8, §25). Ein
      ausgeblendeter Ausgewählter fällt zurück auf die Szene.
    * **Die automatische Rahmung folgt der Auswahl nicht.** ``_fit_once_for``
      rahmt, *weil* die Szene der Ansicht entwachsen ist — ein Rahmen um den
      kleinen Ausgewählten beantwortete genau das nicht.
    """
    import dataclasses

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.viewport import Viewport

    viewport = Viewport()
    klein = SceneObject(
        id="klein",
        name="klein",
        mesh=MeshData(
            trimesh.creation.box(extents=(10.0, 10.0, 10.0)).apply_translation((0.0, 0.0, 5.0))
        ),
    )
    gross = dataclasses.replace(
        klein,
        id="gross",
        name="gross",
        mesh=MeshData(
            trimesh.creation.box(extents=(100.0, 100.0, 100.0)).apply_translation(
                (200.0, 0.0, 50.0)
            )
        ),
    )
    viewport._result = EvaluationResult(scene=Scene(objects={"klein": klein, "gross": gross}))

    assert viewport._selected_bounds() is None, "ohne Auswahl gibt es keinen gewählten Quader"

    viewport._selected = "klein"
    chosen = viewport._selected_bounds()
    assert chosen is not None
    assert chosen[0] == pytest.approx(-5.0) and chosen[1] == pytest.approx(5.0)
    assert chosen[5] == pytest.approx(10.0), "der kleine Körper, nicht die Szene"

    # Ausgeblendet ist nicht im Bild — dann zählt wieder die ganze Szene.
    viewport._hidden = frozenset({"klein"})
    assert viewport._selected_bounds() is None
    viewport._hidden = frozenset()

    # **Und die Szene bleibt die Szene.** ``_fitted_bounds`` beantwortet „ist
    # sie gewachsen?"; stünde der Ausgewählte darin, hielte ``outgrown`` jede
    # Auswahl eines kleinen Teils für eine gewachsene Szene.
    viewport.reset_camera()
    assert viewport._fitted_bounds is not None
    assert viewport._fitted_bounds[1] == pytest.approx(250.0), (
        "gemerkt wird die Ausdehnung der Szene, auch wenn die Kamera einen einzelnen Körper rahmt"
    )

    # **Und jetzt die Kamera selbst.** Ohne diesen Teil war der Test grün, als
    # ich die Auswahl aus ``reset_camera`` wieder ausbaute — er maß die
    # Vorarbeit und nicht die Wirkung (Gegenprobe am 03.09.2026).
    plotter = _FramingPlotter()
    viewport.plotter = plotter  # type: ignore[assignment]
    viewport.reset_camera()
    gerahmt = plotter.framed[-1]
    assert gerahmt is not None
    mitte = (gerahmt[0] + gerahmt[1]) / 2.0
    assert mitte == pytest.approx(0.0, abs=1.0), (
        f"gerahmt wird der gewählte Körper um X=0, nicht die Szene um X=100 ({mitte:.0f})"
    )
    assert gerahmt[1] - gerahmt[0] < 30.0, "und in seiner Größe, nicht in der der Szene"

    # Ohne Auswahl dieselbe Frage, andere Antwort.
    viewport._selected = None
    viewport.reset_camera()
    weit = plotter.framed[-1]
    assert weit is not None
    assert weit[1] - weit[0] > 200.0, "ohne Auswahl bleibt es die ganze Szene"
    viewport._selected = "klein"

    # **Im Skizzenmodus gilt es nicht** — dort ist der Körper Zusammenhang,
    # nicht Gegenstand.
    viewport._sketch_frame = object()  # type: ignore[assignment]
    viewport.reset_camera()
    beim_zeichnen = plotter.framed[-1]
    assert beim_zeichnen is not None
    assert beim_zeichnen[1] - beim_zeichnen[0] > 200.0
    viewport._sketch_frame = None

    # Der automatische Weg fragt ausdrücklich nicht nach der Auswahl.
    gefragt: list[bool] = []
    viewport.reset_camera = lambda **kwargs: gefragt.append(  # type: ignore[method-assign]
        bool(kwargs.get("follow_selection", True))
    )
    viewport._fitted_to = None
    viewport._fit_once_for(viewport._result)
    assert gefragt == [False], "die Rahmung nach dem Wachsen nimmt die ganze Szene"


class _EdgySurface:
    """So viel PolyData, wie die Kantensuche anfasst — und sie zählt mit."""

    def __init__(self, cells: int = 100) -> None:
        self.n_cells = cells
        self.searched = 0

    def extract_feature_edges(self, **kwargs: object) -> _EdgySurface:
        self.searched += 1
        found = _EdgySurface(cells=12)
        return found


def test_the_body_edges_are_searched_once_per_mesh(qt_app: QApplication) -> None:
    """Die Kantensuche lief bei jedem Aufbau neu — und ein Aufbau ist häufig.

    **Gemessen am Kundenmodell `chufang.3mf`** (32 Körper, 5 476 596
    Dreiecke, 03.09.2026): Ein Szenenaufbau kostete **1,02 s**, davon
    **453 ms** allein `extract_feature_edges`. Das ist der teuerste einzelne
    Posten — und `show_scene` läuft bei jeder Auswahl eines Körpers, jedem
    Themenwechsel und jedem Schritt der Schieber für Explosion, Schnitt und
    Schicht.

    Der Kommentar bei :data:`FEATURE_EDGE_LIMIT` rechnet mit „dreißig
    Millisekunden je Körper und Szenenaufbau"; die Rechnung stimmt, ihre
    Annahme nicht. Dieselbe Fehleinschätzung stand schon einmal beim Schatten
    (`_shadow_hulls_for`: „einmal je Szenenaufbau" hieß dort „selten"), und
    dort ist sie längst behoben — die Kanten daneben blieben.

    Mit dem Cache: **61 ms**, der Aufbau 0,74 s.

    Geprüft wird, woran der Cache hängt (die Identität des Netzes, nicht sein
    Inhalt) und dass ein anderes Netz neu sucht — der Schnittschieber erzeugt
    genau das und soll den Cache nicht treffen.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    fläche = _EdgySurface()
    netz = object()

    zuerst = viewport._feature_edges_for("body", fläche, netz)
    assert fläche.searched == 1
    assert zuerst is not None

    noch_einmal = viewport._feature_edges_for("body", fläche, netz)
    assert fläche.searched == 1, "dasselbe Netz wird nicht zweimal durchsucht"
    assert noch_einmal is zuerst, "und es kommt dieselbe Geometrie zurück"

    # Ein geschnittener Körper ist ein anderes Netz — dort wäre der alte
    # Kantenzug falsch.
    geschnitten = object()
    danach = viewport._feature_edges_for("body", fläche, geschnitten)
    assert fläche.searched == 2, "ein anderes Netz wird durchsucht"
    assert danach is not zuerst

    # Ohne Netz gibt es nichts zu merken — dann bleibt es beim Suchen.
    viewport._feature_edges_for("body", fläche, None)
    viewport._feature_edges_for("body", fläche, None)
    assert fläche.searched == 4, "ohne Schlüssel kein Cache"


def _scene_with_a_hole_and_a_fillet() -> Any:
    """Ein Körper mit einer Bohrung und einer Verrundung.

    Die kleinste Szene für die Frage „an welchem Merkmal hängt der Griff":
    Eine Bohrung lässt sich versetzen, eine Verrundung nicht — sie hängt an
    ihrer Kante, und versetzt bliebe die Kante scharf.
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
        "fillet_1": Feature(
            id="fillet_1",
            kind="fillet",
            provenance="detected",
            params={"radius": 2.0, "centre": (10.0, 0.0, 5.0)},
        ),
        "face_1": Feature(
            id="face_1",
            kind="face",
            provenance="detected",
            params={"centre": (0.0, 0.0, 5.0), "normal": (0.0, 0.0, 1.0)},
        ),
    }
    return EvaluationResult(
        scene=Scene(
            objects={"obj_1": SceneObject(id="obj_1", name="A", mesh=mesh, features=features)}
        )
    )


def test_the_handle_sits_on_every_feature_that_can_be_moved(qt_app: QApplication) -> None:
    """„Wenn man die Wulst wählt verschiebt man die Wulst, immer das
    Ausgewählte" (Robert, 03.09.2026).

    Der Griff hing nur an Flächen. Bei jedem anderen Merkmal sprang er in die
    Mitte des Hüllquaders — gemessen an ``motor-mountstp.stl`` mit 27
    Merkmalen saß er bei einer gewählten Bohrung **28 mm daneben**, am anderen
    Ende des Teils, und nichts sagte es. Eine Kundenrückmeldung zu 0.3.0
    nennt dieselbe Lücke: „Move existing holes and other recognised
    details/features", Bewertung 1 von 5.

    Die Grenze zieht das Register und keine Liste in der Ansicht: Es zählt,
    ob es eine Operation gibt, die dieses Merkmal versetzt. Gemessen am
    03.09.2026 sind das ``hole``, ``pin``, ``cone`` und ``sphere`` — die
    Verrundung bleibt außen vor, und ein Griff, der nichts auslösen kann,
    wäre schlimmer als keiner.

    **Der Test nagelt die Liste bewusst nicht fest.** Er fragt nach einer Art,
    die drin sein muss, und einer, die draußen bleibt; die genaue Menge
    gehört dem Register und ändert sich dort. Eine Zusicherung auf die
    vollständige Menge machte jeden Zuwachs an ``move_feature`` zu einem
    roten Lauf in einer Datei, die davon nichts weiß.
    """
    from app.core import bootstrap
    from app.ui.viewport import Viewport, movable_feature_kinds

    bootstrap.load_operations()
    beweglich = movable_feature_kinds()
    assert "hole" in beweglich, f"ohne bewegliche Bohrung prüft dieser Test nichts: {beweglich}"
    assert "fillet" not in beweglich, beweglich

    viewport = Viewport()
    viewport.show_scene(_scene_with_a_hole_and_a_fillet())
    viewport.select("obj_1")

    viewport.select_feature("hole_1")
    ziel = viewport.gizmo_feature()
    assert ziel is not None and ziel.id == "hole_1", "die Bohrung trägt den Griff"
    assert viewport.gizmo_target() is None, (
        "sie ist keine Fläche — Press/Pull entlang einer Normalen gibt es dort nicht"
    )

    viewport.select_feature("fillet_1")
    assert viewport.gizmo_feature() is None, (
        "eine Verrundung lässt sich nicht versetzen — der Griff bleibt am Körper"
    )

    viewport.select_feature("face_1")
    flaeche = viewport.gizmo_feature()
    assert flaeche is not None and flaeche.id == "face_1"
    assert viewport.gizmo_target() is not None, "die Fläche behält ihren Press/Pull-Weg"


def test_the_movable_kinds_come_from_the_register(qt_app: QApplication) -> None:
    """Die Artenliste steht im Register, nicht in der Ansicht.

    Eine Aufzählung hier wäre eine zweite Wahrheit, die beim nächsten Zuwachs
    veraltet — und die Grenze bewegt sich: Kuppe und Kugel sind heute
    ausdrücklich gesperrt, weil ihre erkannte Mitte im Material liegt, und
    genau das kann sich ändern.
    """
    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.viewport import GIZMO_FEATURE_OPS, movable_feature_kinds

    # **Ohne das Register ist die Menge leer, und die Frage geht ins Leere.**
    # Der Test lief zuerst nur grün, wenn eine andere Datei vorher geladen
    # hatte — also je nach Reihenfolge. Genau der Fall, den die Zusicherung
    # unten fängt.
    bootstrap.load_operations()
    erwartet: set[str] = set()
    gefunden = 0
    for name in GIZMO_FEATURE_OPS:
        if not REGISTRY.has(name):
            # Eine Operation, die es (noch) nicht gibt, ist kein Fehler — genau
            # dafür fragt `movable_feature_kinds` mit `has`. Sie darf nur nicht
            # **alle** fehlen, sonst prüft der Test eine leere Menge.
            continue
        gefunden += 1
        erwartet.update(REGISTRY.get(name).applies_to or ())
    assert gefunden, f"keine der Griff-Operationen im Register: {GIZMO_FEATURE_OPS}"
    assert erwartet, "eine leere Menge liesse den Griff nie an einem Merkmal sitzen"
    assert movable_feature_kinds() == frozenset(erwartet)


def test_the_handle_says_what_it_will_move(qt_app: QApplication) -> None:
    """Drei Lagen, drei Sätze — und keiner davon behauptet die Grenze.

    Der Satz wird aus dem Ziel abgeleitet. Erweitert jemand ``move_feature``
    um eine Art, sagt er es von selbst; eine Aufzählung im Text wäre am selben
    Tag falsch (dieselbe Falle wie bei Texten, die eine Abwesenheit
    versprechen).
    """
    import dataclasses

    from app.core.types import Feature
    from app.ui.viewport import gizmo_sentence

    bohrung = Feature(id="hole_1", kind="hole", provenance="detected", params={})
    flaeche = dataclasses.replace(bohrung, id="face_1", kind="face")

    ganz = gizmo_sentence(None)
    merkmal = gizmo_sentence(bohrung)
    auf_flaeche = gizmo_sentence(flaeche)

    assert ganz and merkmal and auf_flaeche
    assert len({ganz, merkmal, auf_flaeche}) == 3, "drei Lagen, drei Aussagen"
    assert "{" not in ganz + merkmal + auf_flaeche, "ein Platzhalter blieb stehen"


def test_a_drag_on_a_feature_moves_the_feature_and_not_the_part(
    qt_app: QApplication,
) -> None:
    """Der Griff sitzt auf der Bohrung — also wandert die Bohrung.

    **Das ist die Hälfte, die den Fix erst zu einem macht.** Der Griff auf das
    Merkmal zu setzen und den Zug weiter über ``transformDragged`` laufen zu
    lassen wäre eine Verschlimmerung: Er stünde auf dem Loch, sagte „Der Griff
    bewegt das gewählte Merkmal, nicht das ganze Teil." — und verschöbe
    darunter das Teil. Vorher log er über seinen Ort, danach zusätzlich in
    Worten.

    Geprüft wird deshalb **beides**: dass die Merkmalsmeldung kommt, und dass
    die Objektmeldung ausbleibt. Eine allein wäre kein Beleg — genau die
    Verwechslung, die ohne die zweite Zusicherung entsteht.
    """
    from app.core.geom.transform import TransformSteps
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.show_scene(_scene_with_a_hole_and_a_fillet())
    viewport.select("obj_1")
    viewport.select_feature("hole_1")

    versetzt: list[tuple[str, Any]] = []
    gedreht: list[tuple[str, str, float]] = []
    am_teil: list[Any] = []
    viewport.featureMoved.connect(lambda fid, ziel: versetzt.append((fid, ziel)))
    viewport.featureTurned.connect(lambda fid, achse, winkel: gedreht.append((fid, achse, winkel)))
    viewport.transformDragged.connect(am_teil.append)

    verbraucht = viewport._emit_feature_drag(
        TransformSteps(offset=(5.0, 0.0, 0.0), axis=None, angle=0.0, scale=1.0)
    )
    assert verbraucht, "ein Zug am Merkmal gehört dem Merkmal"
    assert not am_teil, "das ganze Teil darf sich dabei nicht bewegen"
    assert len(versetzt) == 1, versetzt
    kennung, ziel = versetzt[0]
    assert kennung == "hole_1"
    # Die Zielmitte kommt absolut: Mitte des Merkmals plus der gezogene Weg.
    mitte = viewport._features_of_selection()["hole_1"].params["centre"]
    assert ziel == pytest.approx((mitte[0] + 5.0, mitte[1], mitte[2]))
    assert not gedreht, "ein Verschieben ist keine Drehung"


def test_a_turn_on_a_feature_carries_the_settled_angle(qt_app: QApplication) -> None:
    """Gedreht wird um den Winkel, der auch gilt — nicht um den rohen.

    Der Zeiger zeigte am Vormittag den rohen Winkel, während das Loslassen
    rastete: Wer bei einem Fang von 15° um fünf Grad drehte, las „5,0°" und
    bekam nichts. Dieselbe Falle steht hier ein zweites Mal bereit, denn das
    Fenster könnte den gerasteten Wert nicht nachrechnen, ohne den Fang der
    Leiste und den 45°-Magneten zu kennen. Also reist er mit.

    Und weiter: Ein Zug, der **beides** zu sein scheint, wird eine Drehung —
    pyvistas Widget gibt entweder einen Ring oder einen Pfeil her, und zwei
    Meldungen wären zwei Transaktionen für eine Geste (§15.5).
    """
    from app.core.geom.transform import TransformSteps
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.show_scene(_scene_with_a_hole_and_a_fillet())
    viewport.select("obj_1")
    viewport.select_feature("hole_1")

    versetzt: list[Any] = []
    gedreht: list[tuple[str, str, float]] = []
    viewport.featureMoved.connect(lambda fid, ziel: versetzt.append((fid, ziel)))
    viewport.featureTurned.connect(lambda fid, achse, winkel: gedreht.append((fid, achse, winkel)))

    # `_on_gizmo_released` rastet, bevor es hierher kommt — geprüft wird, dass
    # genau der gerastete Wert ankommt und nicht ein zweiter, eigener.
    verbraucht = viewport._emit_feature_drag(
        TransformSteps(offset=(0.4, 0.0, 0.0), axis="z", angle=45.0, scale=1.0)
    )
    assert verbraucht
    assert gedreht == [("hole_1", "z", 45.0)]
    assert not versetzt, "ein Zug ist eine Geste und wird eine Operation"


def test_a_drag_on_the_body_still_belongs_to_the_body(qt_app: QApplication) -> None:
    """Ohne gewähltes Merkmal ändert sich nichts am gewohnten Weg.

    Die Gegenrichtung der beiden Tests darüber, und ohne sie wäre die
    Abzweigung nicht geprüft, sondern nur benutzt: Ein Zug am Körper muss
    weiterhin ``transformDragged`` auslösen. Eine Abzweigung, die alles
    einfängt, wäre von einer, die richtig trennt, an den zwei Tests oben
    nicht zu unterscheiden.

    Dass eine **Verrundung** hier steht und nicht „gar kein Merkmal", ist der
    schärfere Fall: Sie ist gewählt, sie hat eine Mitte — und es gibt keine
    Operation, die sie versetzt. Der Zug gehört deshalb dem Teil.
    """
    from app.core.geom.transform import TransformSteps
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.show_scene(_scene_with_a_hole_and_a_fillet())
    viewport.select("obj_1")

    versetzt: list[Any] = []
    viewport.featureMoved.connect(lambda fid, ziel: versetzt.append((fid, ziel)))
    zug = TransformSteps(offset=(5.0, 0.0, 0.0), axis=None, angle=0.0, scale=1.0)

    assert viewport._emit_feature_drag(zug) is False, "ohne Merkmal gilt der Zug dem Körper"

    viewport.select_feature("fillet_1")
    assert viewport._emit_feature_drag(zug) is False, (
        "eine Verrundung lässt sich nicht versetzen — der Zug bleibt beim Teil"
    )
    assert not versetzt


def test_the_shadow_follows_the_part_while_it_is_dragged(qt_app: QApplication) -> None:
    """Ein Teil, dessen Schatten am Boden klebt, sieht falsch aus.

    Gemessen am laufenden Fenster, ein Zug über 20 mm in X und 10 mm nach
    oben: **null von drei** Schattenaktoren bewegten sich, während der Körper
    wegwanderte. `_redraw_shadows` reagiert nur auf Kamerabewegungen, nicht
    auf Objektbewegungen — es gab schlicht niemanden, der beim Ziehen
    nachzieht.

    Die Rechnung ist eine Translation: `shadow_points` wirft schräg, jeder
    Punkt fällt um seine Höhe mal der waagerechten Lichtrichtung zur Seite.
    Für **jeden** Punkt derselbe Versatz, also genügt es, den fertigen Aktor
    zu setzen — und die Höhe wirkt dabei seitlich, was die beste Auskunft der
    Geste ist: Wer ein Teil anhebt, sieht am Schatten, wie hoch es steht.
    """
    from app.core.geom.transform import TransformSteps
    from app.ui.viewport import Viewport

    class _Actor:
        def __init__(self) -> None:
            self.position = (0.0, 0.0, 0.0)

    viewport = Viewport()
    viewport.select("obj_1")
    schatten = [_Actor(), _Actor()]
    viewport._shadow_owners = {"obj_1": schatten}
    viewport._shadow_cast = (-0.5, -0.25)

    viewport._drag_shadow(TransformSteps(offset=(20.0, 0.0, 10.0), axis=None, angle=0.0, scale=1.0))
    # 20 + 10·(-0,5) = 15 in X, 0 + 10·(-0,25) = -2,5 in Y, und immer 0 in Z:
    # Der Schatten liegt auf dem Bett, er hebt sich nicht mit.
    for aktor in schatten:
        assert aktor.position == pytest.approx((15.0, -2.5, 0.0))

    # **Eine Drehung lässt ihn stehen — auch wenn sie mit einer Verschiebung
    # kommt.** Sie ändert die Silhouette, und die liesse sich nur durch
    # Neuprojizieren einholen; ein Schatten an der neuen Stelle in der alten
    # Form wäre schlechter als ein stehender.
    #
    # Der Versatz gehört zwingend in diesen Fall: Eine Drehung *ohne* ihn
    # ergäbe rechnerisch (0, 0, 0), und der Test könnte „stehen geblieben"
    # nicht von „mitgezogen um nichts" unterscheiden — die Gegenprobe blieb
    # damit grün.
    for aktor in schatten:
        aktor.position = (0.0, 0.0, 0.0)
    viewport._drag_shadow(TransformSteps(offset=(20.0, 0.0, 10.0), axis="z", angle=30.0, scale=1.0))
    for aktor in schatten:
        assert aktor.position == (0.0, 0.0, 0.0)


def test_the_handle_takes_the_size_of_what_is_selected(qt_app: QApplication) -> None:
    """Der Griff misst sich an dem, was gewählt ist — nicht am ganzen Teil.

    Gemessen am laufenden Fenster an ``broomholdervcd_d35mm.stl``:

        Körperaktor    133,58 mm  ->  Griff  40,07 mm
        Scheibe hole_1  22,67 mm  ->  Griff   6,80 mm

    **Und das ist Absicht** (Entscheidung Robert, 03.09.2026). Am selben Tag
    war die Gegenfassung gebaut — ein Faktor, der beide gleich groß machte —,
    und sie ist zurückgenommen worden: Wer eine Ø6-Bohrung gewählt hat, bewegt
    die Bohrung, und ein Griff in Teilgröße läge weit über sie hinaus und sähe
    aus, als ginge es um das ganze Teil.

    Der Test hält damit eine **Entscheidung** fest und nicht bloß den
    Ist-Zustand: Ohne ihn baut die nächste Sitzung denselben Faktor wieder ein
    — die Beobachtung „der Griff ist an einer Bohrung winzig" stimmt ja, sie
    ist nur kein Fehler.

    Geprüft wird, was **ankommt**, nicht was dasteht: pyvista rechnet den
    Anteil gegen die Diagonale des Aktors, den es bekommt. Also müssen beide
    stimmen — der unveränderte Anteil und die Scheibe als Aktor.
    """
    from app.ui.viewport import GIZMO_SCALE, Viewport

    gesehen: dict[str, object] = {}

    class _Nachgiebig:
        """Antwortet auf alles — Attribut wie Aufruf.

        Der Weg durch ``set_gizmo`` berührt Picker, Interactor und Beobachter;
        sie einzeln nachzubauen hiesse, den Weg zu beschreiben statt ihn zu
        gehen, und beim nächsten Zwischenschritt wäre der Test wieder rot,
        ohne dass sich an seiner Zusage etwas geändert hat.
        """

        def __getattr__(self, name: str) -> Any:
            return _Nachgiebig()

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return _Nachgiebig()

    class _Plotter(_Nachgiebig):
        def add_affine_transform_widget(self, actor: Any, **kwargs: Any) -> Any:
            gesehen["actor"] = actor
            gesehen["scale"] = kwargs.get("scale")
            return SimpleNamespace(_origin=(0.0, 0.0, 0.0), axes=None)

    viewport = Viewport()
    viewport.show_scene(_scene_with_a_hole_and_a_fillet())
    viewport.select("obj_1")
    # Die Scheibe muss ihre Länge kennen: `_label_gizmo` misst daran, wie weit
    # die Achsenbuchstaben hinter den Spitzen stehen.
    scheibe = SimpleNamespace(GetLength=lambda: 22.67, center=(0.0, 0.0, 0.0))
    viewport._face_handle = lambda feature: scheibe  # type: ignore[method-assign]
    viewport.plotter = _Plotter()  # type: ignore[assignment]

    viewport.select_feature("hole_1")
    viewport.set_gizmo(True)

    assert gesehen.get("actor") is scheibe, "der Griff hängt an der Scheibe des Merkmals"
    assert gesehen.get("scale") == GIZMO_SCALE, (
        "kein Umrechnungsfaktor auf die Körpergröße — am 03.09.2026 verworfen"
    )


def test_a_finished_fade_leaves_no_reference_to_a_dead_animation(qt_app: QApplication) -> None:
    """Eine abgelaufene Blende darf nicht noch einmal angehalten werden.

    **Gefunden am laufenden Fenster, nicht in der Suite** — und das ist der
    Punkt dieses Tests. `tween` startet mit `DeleteWhenStopped`: Nach dem
    letzten Bild ist die C++-Hülle weg, während die Python-Referenz bleibt.
    Der nächste Auswahlwechsel ruft `stop()` darauf und bekommt
    ``RuntimeError: Internal C++ object (QVariantAnimation) already deleted``.

    Offscreen läuft **nie** eine Animation (`animations_enabled`), also konnte
    die ganze Suite das nicht sehen: ein Fehler, der nur in der Lage auftritt,
    die der Kunde hat.
    """
    from app.ui.viewport import Viewport

    class _Tot:
        """Eine Hülle, deren C++-Objekt weg ist — wie nach `DeleteWhenStopped`."""

        def stop(self) -> None:
            raise AssertionError("eine tote Animation darf nicht angehalten werden")

    viewport = Viewport()
    # So sieht es nach einer abgelaufenen Blende aus: `on_done` hat geräumt.
    viewport._forget_selection_fade()
    assert viewport._selection_fade is None
    viewport._stop_selection_fade()  # darf nichts tun und nichts werfen

    # Und eine, die noch lebt, wird angehalten und danach vergessen.
    angehalten: list[bool] = []

    class _Lebt:
        def stop(self) -> None:
            angehalten.append(True)

    viewport._selection_fade = _Lebt()
    viewport._stop_selection_fade()
    assert angehalten == [True]
    assert viewport._selection_fade is None, "sonst trifft der nächste Halt eine tote Hülle"


def test_a_click_looks_for_bodies_and_nothing_else(qt_app: QApplication) -> None:
    """Der Bewegungsgriff darf keine Auswahl abfangen.

    „Ich kann die Bohrung in der Mitte nicht mehr auswählen wenn ich sie
    anklicke" (Robert, 03.09.2026). Ein `vtkCellPicker` trifft alles, was im
    Bild steht, und im Bild steht mehr als die Szene: die Pfeile des Griffs,
    sein Skalierwürfel, Marken, Schatten, das Bett. Gemessen am laufenden
    Fenster, Klick genau auf die Bohrungsmitte:

        Griff aus                   -> 'hole_1'
        Griff an, nichts gewählt    -> None       <- der Pfeil lag davor
        Griff an, Bohrung gewählt   -> 'hole_1'

    **Und der erste Prüfstand war grün.** Er fragte `_click_target(punkt)` mit
    einem Weltpunkt und umging damit genau die Stelle, an der der Fehler saß.
    Erst der Weg über `_world_at(x, y)` — der, den ein Klick nimmt — hat ihn
    gezeigt.

    Geprüft wird deshalb die Ursache: dass der Picker seine Kandidatenliste
    aus den Körperaktoren füllt und ``PickFromListOn`` einschaltet. Ohne
    Körper bleibt sie aus — im Skizzenmodus und im leeren Projekt gibt es
    keine, und eine leere Liste träfe nie etwas.
    """
    from app.ui.viewport import Viewport

    gesehen: dict[str, object] = {}

    class _Picker:
        def SetTolerance(self, value: float) -> None:  # noqa: N802 — VTK-Name
            gesehen["tolerance"] = value

        def AddPickList(self, actor: Any) -> None:  # noqa: N802 — VTK-Name
            gesehen.setdefault("liste", []).append(actor)  # type: ignore[union-attr]

        def PickFromListOn(self) -> None:  # noqa: N802 — VTK-Name
            gesehen["begrenzt"] = True

        def Pick(self, *args: Any) -> int:  # noqa: N802 — VTK-Name
            return 1

        def GetPickPosition(self) -> tuple[float, float, float]:  # noqa: N802 — VTK-Name
            return (1.0, 2.0, 3.0)

    viewport = Viewport()
    viewport.plotter = SimpleNamespace(renderer=object())  # type: ignore[assignment]
    koerper = object()
    viewport._actors = {"obj_1": koerper}

    import vtkmodules.vtkRenderingCore as VtkRenderingCore

    echt = VtkRenderingCore.vtkCellPicker
    VtkRenderingCore.vtkCellPicker = _Picker  # type: ignore[misc]
    try:
        assert viewport._world_at(700, 512) == pytest.approx((1.0, 2.0, 3.0))
        assert gesehen.get("liste") == [koerper], "nur die Körper stehen zur Wahl"
        assert gesehen.get("begrenzt") is True, "sonst trifft der Klick auch den Griff"

        # Ohne Körper bleibt die Begrenzung aus — sonst träfe nie etwas.
        gesehen.clear()
        viewport._actors = {}
        viewport._world_at(700, 512)
        assert "liste" not in gesehen
        assert "begrenzt" not in gesehen, "eine leere Kandidatenliste trifft nie etwas"
    finally:
        VtkRenderingCore.vtkCellPicker = echt  # type: ignore[misc]


def test_the_handle_of_a_hole_sits_at_its_mouth(qt_app: QApplication) -> None:
    """Der Griff einer Bohrung gehört an die Öffnung, nicht in ihre Mitte.

    „Ich bin mit meinem Mauszeiger auch immer drüber aber es klappt nicht …
    weder Seitenansicht, Schrägansicht noch Draufsicht" (Robert, 03.09.2026).
    Gemessen am laufenden Fenster, Bohrung Ø 7,34 durch eine 35 mm dicke
    Platte:

        Griffspanne     61,14 mm   — gross genug
        Ursprung z      17,50 mm   — mitten im Material
        Pfeil X, Y      -> der Körper
        Pfeil Z         -> ein Griff-Aktor

    Die erkannte Mitte liegt auf halber Tiefe. Die waagerechten Pfeile stecken
    damit im Teil, und aus jeder Blickrichtung liegt Wand davor. Nach dem
    Umsetzen an die Öffnung trafen alle drei Achsen den Griff.

    **Zur Kamera hin**, weil eine durchgehende Bohrung zwei Öffnungen hat und
    die andere wieder hinter dem Teil läge.
    """
    from app.core.types import Feature
    from app.ui.viewport import Viewport

    viewport = Viewport()
    loch = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 17.5),
            "axis": (0.0, 0.0, 1.0),
            "depth": 35.0,
            "diameter": 7.34,
        },
    )

    # Ohne Plotter gilt die Achsrichtung — offscreen gibt es keine Kamera.
    sitz = viewport._handle_seat(loch, (0.0, 0.0, 17.5))
    assert tuple(float(v) for v in sitz) == pytest.approx((0.0, 0.0, 35.0)), (
        "die Öffnung liegt eine halbe Tiefe über der Mitte"
    )

    # Eine Fläche hat keine Tiefe — ihre Mitte liegt schon auf der Oberfläche.
    flaeche = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"centre": (1.0, 2.0, 3.0), "normal": (0.0, 0.0, 1.0)},
    )
    assert viewport._handle_seat(flaeche, (1.0, 2.0, 3.0)) == (1.0, 2.0, 3.0)


def test_the_mark_covers_the_feature_and_does_not_stand_over_it(
    qt_app: QApplication,
) -> None:
    """Die Scheibe deckt das Merkmal — sie steht nicht darüber hinaus.

    „Ein kleiner Überstand ist noch da" (Robert, 03.09.2026). Die Scheibe mass
    sich an der Objektdiagonale; an seinem Teil (105 x 61,25 x 35) waren das
    Ø 15,18 mm über einer Bohrung von Ø 7,34 — 2,1-mal so breit, 3,92 mm
    Überstand je Seite.

    **Marke und Werkzeug sind zwei Dinge.** Die Scheibe markiert und deckt
    genau das Merkmal; der Griff wird bedient und misst sich am Körper
    (:meth:`_gizmo_scale_for`), damit er aus dem Teil herausragt. Beide an
    dieselbe Grösse zu hängen war der Fehler: Ein Griff in Merkmalsgrösse ist
    unerreichbar, eine Marke in Teilgrösse steht über.

    Eine Fläche hat kein eigenes Mass — für sie bleibt der Anteil der
    Diagonale, und der Grund steht bei ``FACE_HANDLE_SHARE``.
    """
    from app.core.types import Feature
    from app.ui.viewport import FACE_HANDLE_MINIMUM, Viewport

    viewport = Viewport()
    loch = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "diameter": 7.34},
    )
    assert viewport._handle_radius(loch) == pytest.approx(3.67), "genau der halbe Durchmesser"

    winzig = Feature(
        id="hole_2",
        kind="hole",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "diameter": 0.5},
    )
    assert viewport._handle_radius(winzig) == FACE_HANDLE_MINIMUM, (
        "eine Ø0,5-Bohrung bekäme sonst eine Marke, die niemand sieht"
    )


def test_a_view_setter_that_changes_nothing_rebuilds_nothing(qt_app: QApplication) -> None:
    """Sieben Setter bauten die Szene neu auf, auch wenn sich nichts änderte.

    **Der sichtbare Anlass (Robert, 03.09.2026):** „wenn wir ein Körper oder
    Merkmal verschieben oder drehen usw springt es nach Loslassen nochmal zur
    alten Stelle bevor es an der neuen landet." Gemessen am laufenden Fenster
    war die Ursache nicht der Griff und nicht der Schatten, sondern
    `set_analysis_map(None, None)`: dreimal gerufen, während das Ergebnis der
    Operation längst vorlag, und jeder dieser Aufbauten nahm dem Actor seine
    Vorschau-Matrix. **491 ms** stand das Teil dort, wo es hergekommen war.

    **Der teurere Teil war unsichtbar.** Zähler um `show_scene` und alle acht
    Setter, vier gewöhnliche Handlungen an `aushoehlen-und-teilen.p3d`:

    | Handlung | vorher | nachher |
    |---|---|---|
    | Körper anklicken | 1 | 0 |
    | zweiten anklicken | 1 | 0 |
    | Themenwechsel | 3 | 1 |
    | dasselbe Thema noch einmal | 1 | 0 |
    | Modus zweimal auf denselben Wert | 2 | 1 |
    | **Summe** | **8** | **2** |

    An `chufang.3mf` (32 Körper, 5 476 596 Dreiecke) kostet ein Aufbau
    **0,74 s** — ein Klick auf einen Körper also drei Viertel Sekunden für
    nichts.

    `set_hidden` hatte die Prüfung seit je und ist die Vorlage. Geprüft wird
    hier jeder Setter einzeln: zweimal derselbe Wert, und nur der erste darf
    aufbauen.
    """
    import dataclasses

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.viewport import Viewport

    viewport = Viewport()
    body = SceneObject(
        id="obj",
        name="obj",
        mesh=MeshData(
            trimesh.creation.box(extents=(10.0, 10.0, 10.0)).apply_translation((0.0, 0.0, 5.0))
        ),
    )
    viewport._result = EvaluationResult(scene=Scene(objects={"obj": body}))

    aufbauten = [0]
    original = viewport.show_scene

    def zaehlend(result: object) -> None:
        aufbauten[0] += 1
        original(result)

    viewport.show_scene = zaehlend  # type: ignore[method-assign]

    # Je Setter: der erste Aufruf zählt, der zweite mit demselben Wert nicht.
    fälle: list[tuple[str, object, object]] = [
        ("set_hidden", frozenset({"obj"}), frozenset({"obj"})),
        ("set_plate", 1, 1),
        ("set_explosion", 2.5, 2.5),
        ("set_display_mode", "wireframe", "wireframe"),
        ("set_shading", "smooth", "smooth"),
        ("set_analysis_map", None, None),
    ]
    for name, erst, zweit in fälle:
        setter = getattr(viewport, name)
        vorher = aufbauten[0]
        if name == "set_analysis_map":
            # Zwei Argumente, und der gemessene Fall ist genau „keine Karte".
            setter(None, None)
            setter(None, None)
            assert aufbauten[0] - vorher == 0, (
                "keine Karte auf keine Karte ist keine Änderung — genau der "
                "Fall, der den Körper zurückspringen ließ"
            )
            continue
        setter(erst)
        nach_dem_ersten = aufbauten[0] - vorher
        setter(zweit)
        nach_dem_zweiten = aufbauten[0] - vorher
        assert nach_dem_ersten == 1, f"{name}: die echte Änderung baut auf"
        assert nach_dem_zweiten == 1, f"{name}: derselbe Wert baut nicht noch einmal auf"

    # **``set_theme`` wird an seiner Wirkung geprüft, nicht am Aufbau.** Er
    # steigt offscreen vor ``show_scene`` aus (``if self.plotter is None``),
    # und ein Test über den Zähler wäre hier grün, ohne etwas zu sagen — die
    # Prüfung sitzt aber davor und gilt auch ohne Plotter.
    viewport.set_theme("light")
    gemerkt = viewport._object_colour
    viewport._object_colour = "#000000"
    viewport.set_theme("light")
    assert viewport._object_colour == "#000000", (
        "dasselbe Thema fasst die Farben nicht noch einmal an"
    )
    viewport.set_theme("dark")
    assert viewport._object_colour != "#000000", "ein anderes Thema schon"
    assert viewport._theme == "dark"
    viewport.set_theme("light")
    assert viewport._object_colour == gemerkt, "und zurück ergibt wieder dieselben Farben"

    # Das Auseinanderziehen vergleicht den **normalisierten** Wert: Wer zweimal
    # einen negativen Faktor schickt, meint zweimal null.
    vorher = aufbauten[0]
    viewport.set_explosion(-1.0)
    viewport.set_explosion(-5.0)
    assert aufbauten[0] - vorher == 1, (
        "zwei negative Faktoren sind beide null — der zweite ändert nichts"
    )

    # Und die Schnittebene hängt an beiden Werten, nicht nur an der Ebene.
    from app.core.geom.section import SectionPlane

    ebene = SectionPlane(normal=(1.0, 0.0, 0.0), position=0.0)
    vorher = aufbauten[0]
    viewport.set_section(ebene, 1.0)
    viewport.set_section(dataclasses.replace(ebene), 1.0)
    assert aufbauten[0] - vorher == 1, "dieselbe Ebene bei derselben Dicke ist keine Änderung"
    viewport.set_section(dataclasses.replace(ebene), 2.0)
    assert aufbauten[0] - vorher == 2, "eine andere Dicke schon"


def test_a_dragged_feature_leaves_a_mark_where_it_came_from(qt_app: QApplication) -> None:
    """Der Zug zeigt beides: wohin — und von wo.

    „Die Bohrung, die beim Verschieben die Vorschau haben sollte" (Robert,
    03.09.2026). Die Marke wandert mit dem Griff und hat seit `_handle_radius`
    genau den Durchmesser des Merkmals; sie **ist** damit die Vorschau der
    Zielstelle. Was fehlte, war der Bezug: Der Körper steht während des Zugs
    still — seine Geometrie ändert sich erst bei der Auswertung —, und ohne
    eine Marke am Ausgangsort sah es aus, als bewege sich nichts oder als ziehe
    man das ganze Teil.

    Gemessen am laufenden Fenster, Bohrung Ø 7,48, Zug über 25 mm:

        vor dem Zug        kein Ring
        während des Zugs   Ring bei (0, 0, 35), Ø 7,48 — die Ausgangsstelle
        nach dem Zug       weg

    **Er erscheint erst mit dem ersten sichtbaren Stück des Zugs.** Ihn schon
    beim Anhängen des Griffs zu zeigen hiesse, eine Bewegung zu behaupten, die
    noch keine ist — dieselbe Zurückhaltung, die das Wertfeld daneben übt.
    """
    from app.core.types import Feature
    from app.ui.viewport import Viewport

    gezeichnet: list[dict[str, object]] = []

    class _Nachgiebig:
        def __getattr__(self, name: str) -> Any:
            return _Nachgiebig()

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return _Nachgiebig()

    class _Plotter(_Nachgiebig):
        def add_mesh(self, mesh: Any, **kwargs: Any) -> Any:
            gezeichnet.append(dict(kwargs))
            return SimpleNamespace(GetBounds=lambda: (0.0, 7.48, 0.0, 7.48, 35.0, 35.0))

        def remove_actor(self, actor: Any, **kwargs: Any) -> None:
            gezeichnet.append({"entfernt": True})

    viewport = Viewport()
    viewport.plotter = _Plotter()  # type: ignore[assignment]
    loch = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 17.5),
            "axis": (0.0, 0.0, 1.0),
            "depth": 35.0,
            "diameter": 7.48,
        },
    )
    # Der Sitz entsteht beim Anlegen der Marke; der Ring nimmt denselben.
    viewport._face_seat = ((0.0, 0.0, 35.0), (0.0, 0.0, 1.0), 3.74)

    assert viewport._ghost_actor is None
    viewport._show_ghost(loch)
    assert viewport._ghost_actor is not None, "der Ring markiert die Ausgangsstelle"
    ring = next(k for k in gezeichnet if k.get("name") == "feature-ghost")
    assert ring["pickable"] is False, "eine Marke fängt keine Klicks (Robert, 03.09.2026)"

    viewport._drop_ghost()
    assert viewport._ghost_actor is None, "nach dem Zug gilt die Auswertung, nicht der Ring"
