"""Gemeinsames Gerüst für die Tests.

Der Geometriekern ist nicht Teil von P0, die Tests benutzen also ein Netz, das
nur die Fragen beantwortet, die das ``Mesh``-Protokoll stellt. Das genügt für
Szene, Stapel und Auswertung — und es hält diese Tests ehrlich darüber, was sie
prüfen.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

import pytest

# Oberflächentests brauchen eine Qt-Plattform, die ohne Bildschirm funktioniert.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Die Suite darf die eigenen Daten des Nutzers weder lesen noch schreiben
# (§38). Ohne das ändert ein kalibriertes Material auf dem Entwicklerrechner,
# was die Tests sehen — und schlimmer: ein Testlauf hinterließe Kalibrierungen
# in seinem Profilordner.
_ISOLATED = tempfile.mkdtemp(prefix="solidon-tests-")
for _variable in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED

from app.core import discover
from app.core.activation import store as activation_store
from app.core.knowledge import profiles
from app.core.types import BoundingBox, Document, Profile, SceneObject

#: Der Stichtag der Demo, gesichert bevor die Fixture unten ihn wegnimmt.
_SHIPPED_DEMO_UNTIL = activation_store.DEMO_UNTIL


@pytest.fixture(autouse=True)
def _the_calendar_stays_out_of_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Suite misst die Mechanik der Demo, nicht das Kalenderblatt.

    Der ausgelieferte Stichtag ist ein Datum. Ohne diese Zeile wäre die Suite
    ab dem Tag danach rot — an Dutzenden Stellen, die mit der Frist nichts zu
    tun haben, weil jede Dokumentänderung durch die Freischaltung geht.

    Wer die Frist selbst prüft, setzt sie ausdrücklich; `test_activation.py`
    tut das über die Fixture `demo`. Den **echten** Wert bekommt nur, wer ihn
    über `shipped_demo_until` verlangt — dort steht auch der Wecker, der
    anschlägt, wenn der Stichtag verstrichen ist.
    """
    monkeypatch.setattr(activation_store, "DEMO_UNTIL", None)


@pytest.fixture
def shipped_demo_until() -> object:
    """Der Stichtag, mit dem tatsächlich ausgeliefert wird — oder ``None``."""
    return _SHIPPED_DEMO_UNTIL


@pytest.fixture(autouse=True)
def _machine_stays_out_of_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Suite fragt nicht die Maschine, auf der sie läuft (§38).

    Dieselbe Begründung wie bei den Nutzerverzeichnissen oben: ein
    Entwicklerrechner mit installiertem OpenSCAD sieht sonst etwas anderes als
    ein Bauserver ohne, und ein Test, dessen Ergebnis davon abhängt, prüft
    nicht, was er zu prüfen vorgibt. Was ausdrücklich gesetzt wurde, gilt
    weiter — daran hängen die Tests, die einen Fund brauchen.
    """

    def only_what_was_set(tool_id: str, names: object) -> object:
        chosen = discover.remembered(tool_id)
        from pathlib import Path

        path = Path(chosen) if chosen else None
        return path if path is not None and path.is_file() else None

    monkeypatch.setattr(discover, "find_program", only_what_was_set)
    discover.forget_cache()


@pytest.fixture(autouse=True)
def _no_worker_outlives_its_window() -> Iterator[None]:
    """Nach jedem Test warten die Fenster auf ihre Arbeiter.

    ``MainWindow.wait_for_workers`` sagt selbst, warum es das gibt: **ein
    Thread, der sein Fenster überlebt, nimmt den Prozess mit.** Im Programm
    ruft der ``closeEvent`` es. In der Suite gibt es diesen Weg nicht — dort
    wird ein Fenster weggeräumt, nicht geschlossen, und wann der
    Speicherbereiniger das tut, entscheidet er.

    Das war der Absturz, der etwa jeden vierten Lauf mit einer
    Zugriffsverletzung statt eines Ergebnisses beendete: kein Testfehler, kein
    Name im Protokoll, jedes Mal an einer anderen Stelle — mal in
    ``test_analysis_ui``, mal in ``test_ui``, dazwischen grüne Läufe.

    Zentral und nicht in jedem ``window``-Fixture: es gibt neun davon, und das
    zehnte vergisst es.

    **Warten allein genügte nicht.** Der Ubuntu-Runner starb ab dem 06.08.2026
    in jedem Lauf mit einem Segmentierungsfehler, immer an derselben Zeile —
    ``HistoryPanel.show_document``, erste Anweisung, ``self.list.clear()`` —,
    aber jedes Mal in einem anderen Test. Eine Messung mit zerlegter Suite hat
    gezeigt, dass der Absturz *wandert*: es liegt an keinem Test, sondern an
    dem, was sich über den Lauf ansammelt.

    Angesammelt haben sich die Fenster. Ein ``window``-Fixture gibt sein
    ``MainWindow`` zurück und überlässt es danach dem Speicherbereiniger; die
    ``Session`` daneben lebt in ihrem eigenen Fixture weiter. Sammelt Python
    das Fenster ein, während eine Zustellung läuft, ruft ``sceneChanged`` in
    ein ``_on_scene``, dessen Widgets auf der C++-Seite schon weg sind — und
    ``clear()`` schreibt in freigegebenen Speicher. Unter Windows fällt das
    selten auf, weil der Allokator die Seite behält; unter Linux gibt er sie
    zurück, und der nächste ``wait_for_idle`` mit seinem ``processEvents``
    stellt genau dann zu.

    Deshalb kappt ``MainWindow.release`` hier die Verbindung — und **nur** sie.
    Das Fenster zu zerstören wäre der naheliegende Schluss und war der falsche:
    siehe die Begründung unten am Ende dieser Fixture.
    """
    yield
    from PySide6.QtWidgets import QApplication
    from shiboken6 import isValid

    application = QApplication.instance()
    if application is None:
        return
    for widget in list(application.topLevelWidgets()):
        # In dieser Liste stehen auch Wrapper, deren C++-Seite längst weg ist —
        # `isValid` ist keine Vorsicht, sondern die Bestätigung des Befunds:
        # genau solche Leichen hält Qt hier, und genau in eine davon schrieb
        # der Segmentierungsfehler.
        if not isValid(widget):
            continue
        release = getattr(widget, "release", None)
        if callable(release):
            # Arbeiter auslaufen lassen **und** die Sitzung abbestellen. Das
            # zweite ist das Neue: ohne es ruft ein späteres Ergebnis in
            # Widgets, die es nicht mehr gibt.
            release()
        else:
            waiter = getattr(widget, "wait_for_workers", None)
            if callable(waiter):
                waiter()
    # Zerstört wird hier **nichts**. Zwei Anläufe haben das versucht —
    # ``deleteLater`` allein änderte nichts (``processEvents`` führt
    # ``DeferredDelete`` nicht aus), und mit ``sendPostedEvents`` dazu
    # verschob sich der Absturz nur: ein zerstörtes Fenster nimmt den
    # VTK-Zustand mit, und der **nächste** Aufbau stirbt in
    # ``render_window_interactor.initialize``. Beides gemessen, in Fenstern
    # nacheinander, nicht erlitten in einem zwanzigminütigen Lauf.
    #
    # Was bleibt, ist die eigentliche Ursache: nicht die Lebenszeit, sondern
    # die Verbindung. ``release`` kappt sie oben.
    application.processEvents()


@dataclass(frozen=True, slots=True)
class FakeMesh:
    """Ein Netz-Platzhalter mit festen Kennzahlen."""

    triangles: int = 12
    vertices: int = 8
    size: tuple[float, float, float] = (10.0, 10.0, 10.0)
    watertight: bool = True
    components: int = 1
    slots: tuple[int, ...] = field(default_factory=tuple)

    @property
    def vertex_count(self) -> int:
        return self.vertices

    @property
    def triangle_count(self) -> int:
        return self.triangles

    @property
    def bounds(self) -> BoundingBox:
        return BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=self.size)

    @property
    def volume(self) -> float:
        return self.size[0] * self.size[1] * self.size[2]

    @property
    def area(self) -> float:
        width, depth, height = self.size
        return 2 * (width * depth + width * height + depth * height)

    @property
    def is_watertight(self) -> bool:
        return self.watertight

    @property
    def component_count(self) -> int:
        return self.components

    @property
    def slot_indices(self) -> Sequence[int]:
        return self.slots


@pytest.fixture(scope="session")
def qt_app() -> object:
    """Eine QApplication für den ganzen Lauf — Widgets stürzen ohne sie ab.

    Und mit derselben Zahlenschreibweise wie die Anwendung. ``app/ui/app.py``
    setzt ``QLocale`` auf die Anzeigesprache; die Suite baut ihre Fenster
    direkt und übersprang das, womit sie die Sprache des **Rechners** prüfte:
    hier stand „Raster 0,30 mm", auf dem Runner „Raster 0.30 mm", und ein Test
    über deutsche Kommas war grün, ohne dass jemand etwas dafür getan hätte.
    Dieselbe Begründung wie bei den Nutzerverzeichnissen und dem
    Maschinen-Fixture oben: wer die Umgebung nicht festlegt, prüft nicht, was
    er zu prüfen vorgibt.
    """
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QApplication

    from app.i18n import SOURCE_LANGUAGE

    QLocale.setDefault(QLocale(SOURCE_LANGUAGE))
    return QApplication.instance() or QApplication([])


@pytest.fixture
def mesh() -> FakeMesh:
    return FakeMesh()


@pytest.fixture
def profile() -> Profile:
    return profiles.make_profile("centauri-carbon-2", "petg")


@pytest.fixture
def document() -> Document:
    return Document(format_version=1, app_version="0.0.1")


def make_object(object_id: str = "obj_1", name: str = "Teil", **kwargs: object) -> SceneObject:
    return SceneObject(id=object_id, name=name, mesh=FakeMesh(**kwargs))  # type: ignore[arg-type]
