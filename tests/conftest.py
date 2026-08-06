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
_ISOLATED = tempfile.mkdtemp(prefix="formwerk-tests-")
for _variable in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED

from app.core import discover
from app.core.knowledge import profiles
from app.core.types import BoundingBox, Document, Profile, SceneObject


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
    """
    yield
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    if application is None:
        return
    for widget in list(application.topLevelWidgets()):
        waiter = getattr(widget, "wait_for_workers", None)
        if callable(waiter):
            waiter()


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
    """Eine QApplication für den ganzen Lauf — Widgets stürzen ohne sie ab."""
    from PySide6.QtWidgets import QApplication

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
