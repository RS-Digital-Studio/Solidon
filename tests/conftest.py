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

    # Das Original bleibt unter eigenem Namen erreichbar, für die wenigen
    # Tests, die **genau es** prüfen wollen (`test_discover.py`). Ohne diese
    # Zeile fragt ein solcher Test die Attrappe darüber und ist grün, ohne
    # etwas geprüft zu haben — die Attrappe protokolliert zum Beispiel nie.
    monkeypatch.setattr(discover, "unpatched_find_program", discover.find_program, raising=False)
    monkeypatch.setattr(discover, "find_program", only_what_was_set)
    discover.forget_cache()


@pytest.fixture(autouse=True)
def _the_network_stays_out_of_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Suite fragt nicht, ob auf dieser Maschine ein Modell läuft (§38).

    **Der Fall.** Am 23.08.2026 stand in einem Absturzstapel von ``test_ui.py``:

        app/core/backends/llm.py:501    available
        app/ui/first_run.py:445         _chat_text
        app/ui/leash.py:173             run              (Arbeitsthread)
        ... socket.py:853               create_connection

    ``first_available()`` geht die Backends durch und fragt jedes, ob es
    erreichbar ist; ``OllamaBackend`` prüft das mit einem Socket auf
    ``localhost:11434``. Auf einem Rechner, auf dem Ollama läuft, antwortet er
    **ja** — die Oberfläche baut einen Chat auf, ein Arbeitsthread rechnet, und
    der Test misst etwas anderes als auf dem Bauserver, wo gar keins läuft.

    Dieselbe Begründung wie bei OpenSCAD eine Fixture darüber, nur eine Ebene
    weiter: Die Isolation deckte Qt, die Nutzerverzeichnisse und die
    Fremdprogramme ab — **das Netz nicht.**

    **Geleert wird die Liste der Backends, nicht die Erreichbarkeitsprüfung.**
    Der Unterschied ist wichtig: ``test_backends.py`` prüft ``available`` an
    einer selbst gebauten Instanz gegen einen garantiert geschlossenen Port
    (``localhost:1``), und das soll es weiter tun. Wer die Prüfung selbst
    ersetzte, machte aus diesem Test eine Attrappe, die nichts mehr misst.

    Das Original bleibt unter eigenem Namen erreichbar — für den Fall, dass ein
    Test genau die Liste braucht.
    """
    from app.core.backends import llm

    monkeypatch.setattr(llm, "unpatched_backends", llm.backends, raising=False)
    monkeypatch.setattr(llm, "backends", tuple)


@pytest.fixture(autouse=True)
def _the_display_unit_starts_at_millimetres() -> Iterator[None]:
    """Die Anzeigeeinheit ist ein Prozesszustand, also gehört sie zurückgesetzt.

    Sie liegt in ``app/ui/labels`` und nicht an jedem Widget, weil die
    Merkmalsbeschriftung von drei Stellen ohne Widget geschrieben wird (§19.3).
    Der Preis dafür steht hier: Ein Test, der auf Zoll stellt, würde sonst
    jeden folgenden mitnehmen — und der fiele an einer Zahl um, die nichts mit
    ihm zu tun hat.

    Zentral und nicht im jeweiligen Test, aus demselben Grund wie die Fixture
    darunter: es gibt neun ``window``-Fixtures, und das zehnte vergisst es.
    Der Import liegt innen, damit die Fixture auch ohne PySide6 durchläuft —
    ``labels`` zieht Qt.
    """
    yield
    try:
        from app.ui import labels
    except ImportError:  # pragma: no cover - ohne PySide6 gibt es nichts zu räumen
        return
    labels.set_display_unit("mm")


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
        # **Die Namen werden abgeleitet, nicht gepflegt.** Für dieselbe Sache
        # — „warte, bis dein Arbeiter fertig ist" — gibt es in ``app/ui``
        # derzeit fünf Namen:
        #
        #     release            MainWindow (wartet **und** bestellt ab)
        #     wait_for_workers   MainWindow, PrintSettingsDialog, GenerateDialog
        #     wait_for_survey    FirstRunDialog, InstallDialog
        #     wait_for_look      KeyDialog
        #     wait_for_setup     ComfyDialog
        #
        # Eine aufgezählte Liste wäre am 23.08.2026 zweimal falsch gewesen: Sie
        # kannte ``release`` und ``wait_for_workers``, und die Absturzsuche fand
        # nacheinander ``wait_for_survey`` und ``wait_for_look``. Beim dritten
        # Mal wäre sie wieder falsch — also fragt die Fixture nach dem Muster.
        #
        # **Der Fall, der das ausgelöst hat.**
        # ``test_the_language_picker_shows_names_not_codes`` baut einen
        # ``FirstRunDialog``, liest dessen Sprachliste und ist fertig. Der Dialog
        # startet im Konstruktor einen Erhebungs-Thread; niemand schließt ihn,
        # also wartet niemand. Der Test **allein** beendet den Prozess mit
        # ``0xC0000409`` — dreimal von dreimal, in einer Drittelsekunde. Dasselbe
        # gilt für die beiden ``KeyDialog``-Tests in ``test_chat_ui.py``.
        #
        # ``release`` zuerst, weil es mehr tut als warten; danach alles, was
        # ``wait_for_`` heißt. Ein Name, den es noch nicht gibt, ist damit schon
        # abgedeckt.
        release = getattr(widget, "release", None)
        if callable(release):
            release()
        else:
            for name in sorted(dir(widget)):
                if not name.startswith("wait_for_"):
                    continue
                waiter = getattr(widget, name, None)
                if callable(waiter):
                    waiter()
    # **Die Zählung, mit der sich das Anhäufen messen lässt.**
    #
    # Am 23.08.2026 ließ sich der wandernde Absturz in test_ui.py nicht
    # eingrenzen: sechs Läufe, vier Abstürze, vier verschiedene Stellen — nach
    # 14, 81, 124 und 202 Tests. Kein einzelner Test. Also wurde gezählt statt
    # gesucht, und die Zahl ist eindeutig:
    #
    #     nach Test   1:      0 Top-Level-Widgets
    #     nach Test  51:    377
    #     nach Test 126:   1188
    #     nach Test 257:   1705
    #
    # **Alle 1705 sind isValid** — keine Leichen, sondern lebende Objekte.
    # Der Speicherbereiniger holt gelegentlich etwas (bei 151 waren es 840, bei
    # 176 wieder 1393), kommt aber nicht hinterher.
    #
    # **Sie erklärt den Absturz nicht.** Nach 14 Tests gab es etwa achtzig
    # Widgets, und der Lauf riss trotzdem — wäre die Menge die Ursache, dürfte
    # dort nichts passieren. Plausibel ist, dass sie eine von zwei Bedingungen
    # ist: Der Speicherbereiniger läuft in dem Thread, dessen Allokation die
    # Schwelle reißt, und mehr Objekte machen beides wahrscheinlicher, ohne es
    # zu erzwingen.
    #
    # **Wozu sie trotzdem taugt: als Fortschrittsmaß.** 1705 ist
    # deterministisch, eine Absturzrate ist es nicht. Wer an den
    # Widget-Lebensdauern arbeitet, sieht das Ergebnis nach *einem* Lauf statt
    # nach zehn.
    #
    #     SOLIDON_ZAEHLE_WIDGETS=pfad.tsv python -m pytest tests/test_ui.py
    #
    # Drei Spalten je Test: alle Top-Level-Widgets, davon gültige, und die Zahl
    # der bekannten QWidget-Unterklassen.
    if os.environ.get("SOLIDON_ZAEHLE_WIDGETS"):
        from pathlib import Path

        from PySide6.QtWidgets import QWidget

        oben = application.topLevelWidgets()
        lebende = [widget for widget in oben if isValid(widget)]
        ziel = Path(os.environ["SOLIDON_ZAEHLE_WIDGETS"])
        with ziel.open("a", encoding="utf-8") as datei:
            print(len(oben), len(lebende), len(QWidget.__subclasses__()), file=datei)

    # Zerstört wird hier **nichts**. Zwei Anläufe haben das versucht —
    # ``deleteLater`` allein änderte nichts (``processEvents`` führt
    # ``DeferredDelete`` nicht aus), und mit ``sendPostedEvents`` dazu
    # verschob sich der Absturz nur: ein zerstörtes Fenster nimmt den
    # VTK-Zustand mit, und der **nächste** Aufbau stirbt in
    # ``render_window_interactor.initialize``. Beides gemessen, in Fenstern
    # nacheinander, nicht erlitten in einem zwanzigminütigen Lauf.
    #
    # **Woran der Hänger wirklich liegt — aufgeklärt am 23.08.2026 mit
    # ``py-spy dump --native`` an einem laufenden ``test_ui.py``.** Er steht
    # hier, weil hier gesucht wird, wenn er das nächste Mal zuschlägt:
    #
    #     Hauptthread   hält den GIL, wartet auf den Qt-Mutex
    #                   QComboBox::setCurrentIndex → QAbstractItemView::setModel
    #                   → QObject::connectImpl → QBasicMutex::lockInternal
    #
    #     Nebenthread   hält den Qt-Mutex, wartet auf den GIL
    #                   QWidget::~QWidget → QMenuBar::~QMenuBar → QMenu::~QMenu
    #                   → QObject::~QObject → Sbk_GetPyOverride (shiboken6)
    #                   → PyGILState_Ensure
    #
    # **Ein ``QMenuBar`` wird in einem Nebenthread zerstört.** Sein Destruktor
    # nimmt den Qt-Mutex und braucht dann den GIL für die shiboken-Hülle; der
    # Hauptthread hält den GIL und wartet auf genau diesen Mutex. Niemand tut
    # das absichtlich: Pythons Speicherbereiniger läuft in dem Thread, dessen
    # Allokation gerade die Schwelle reißt, und findet dort ein Fenster ohne
    # letzte Python-Referenz. Gefunden von 3d-druck-b8.
    #
    # **Ein zweiter Stapelabzug, unabhängig und mit anderen Widgets** — am
    # 23.08.2026 an einem eigenen hängenden Torlauf gezogen, ebenfalls mit
    # ``py-spy dump --native``:
    #
    #     MainThread    hält den GIL, wartet auf den Qt-Mutex
    #                   QScrollArea::QScrollArea → QObject::connect
    #                   → QBasicMutex::lockInternal
    #
    #     Thread 52656  hält den Qt-Mutex, wartet auf den GIL
    #                   SbkDeallocWrapper → QWidget::~QWidget
    #                   → QObjectPrivate::deleteChildren → QObject::~QObject
    #                   → Sbk_GetPyOverride → PyGILState_Ensure
    #
    # Zwei Dinge macht er klarer als der erste. **Erstens: Es liegt nicht an
    # ``QMenuBar``.** Dort war es ein Menü beim Aufbau einer ``QComboBox``,
    # hier ein beliebiges ``QWidget`` beim Aufbau einer ``QScrollArea`` — die
    # Paarung ist zufällig, das Muster ist es nicht. Jedes Widget, dessen
    # letzte Python-Referenz in einem Nebenthread fällt, kann es auslösen.
    #
    # **Zweitens: ``SbkDeallocWrapper`` ganz unten benennt den Auslöser.** Das
    # ist shibokens Deallocator — die *Python*-Hülle wird freigegeben, und das
    # zieht die C++-Zerstörung nach sich. Nicht Qt räumt hier auf, sondern
    # Pythons Speicherbereiniger, und er tut es in dem Thread, in dem er
    # gerade läuft.
    #
    # Das erklärt vier Beobachtungen, die einzeln keinen Sinn ergaben:
    #
    # * Warum die Läufe **stehen** statt zu stürzen — ein Deadlock rechnet nicht.
    # * Warum ``gc.collect()`` hier nichts brachte — der Lauf im Hauptthread ist
    #   der harmlose; gefährlich ist der im Nebenthread, und den löst kein
    #   ``collect()`` aus, sondern eine Allokation.
    # * Warum ``undisturbed()`` nicht wirkte — es hält den Sammler an, während
    #   *diese* Zeile läuft; der Nebenthread alloziert weiter, wann er will.
    # * Warum es das erst seit dem 22.08.2026 gibt: Solange Lambda-Ringe die
    #   Fenster hielten, sammelte sie **niemand** ein. Seit sie sterben können,
    #   können sie im falschen Thread sterben. Der Ring-Umbau war richtig und
    #   hat den Speicher flach gemacht — und er hat diesen Deadlock erst
    #   möglich gemacht. Wer ihn für unbeteiligt hält, sucht falsch.
    #
    # **Für den nächsten Anlauf, und er hat zwei Baustellen statt einer:**
    # Zerstörung gehört in den Hauptthread (``deleteLater``), aber die zwei
    # gescheiterten Anläufe oben zeigen die zweite Klippe — ``processEvents``
    # führt ``DeferredDelete`` nicht aus, und mit ``sendPostedEvents`` dazu
    # nimmt ein zerstörtes Fenster den VTK-Zustand mit. Wer nur die erste löst,
    # trifft die zweite.
    #
    # **Hier stand ein ``gc.collect()``, und es ist am 23.08.2026 gefallen.**
    # Der Gedanke war richtig: Wann Python die losgelassenen Fenster einsammelt,
    # entscheidet sonst der Zufall, und der trifft auch die Zeit, in der Qt
    # denselben Widgets Ereignisse zustellt. Gemessen hat es trotzdem nichts
    # gebracht — zehn Läufe je Seite in einem eigenen Arbeitsbaum, unter dem
    # Schloss auf ruhiger Maschine: **1/10 Abstürze ohne, 1/10 mit**, beide mit
    # derselben Zugriffsverletzung.
    #
    # Der Grund steht in zwei Stapeln von zwei Sitzungen desselben Abends: Der
    # abstürzende Faden steht in ``QObject::~QObject`` unter ``QThread::start``.
    # **Ein Aufräumen im Hauptthread nach dem Test fängt nicht, was ein
    # Arbeiter-Thread während des Tests zerstört.** Wer die Zeile wieder
    # einbauen will, misst vorher zehn Läufe je Seite; sie sieht überzeugend aus
    # und ist es nicht.
    # **Hier stand ein ``leash.wait_for_all(2000)``, und es ist am 23.08.2026
    # gefallen — nach zwanzig Läufen, die alle dasselbe sagten.**
    #
    # Der Gedanke war belegt: Die Schleife oben geht über
    # ``topLevelWidgets()``, und ein Arbeiter, der an einem längst weggeräumten
    # **Dialog** hing, steht dort nicht. Ein Stapelabzug zeigte genau ihn —
    # ``install.py`` beim ``__import__`` in einem Arbeiter, während der
    # Hauptthread hier ``processEvents()`` rief. ``__import__`` nimmt den
    # Import-Lock, und deshalb **standen** diese Läufe still, statt zu stürzen.
    #
    # Das Warten hat den Hänger nicht behoben, sondern einen **zweiten,
    # sicheren Absturz** erzeugt. Gemessen, jedes Mal an ``test_ui.py``:
    #
    #     vor der Änderung                        0 von 3 gerissen
    #     mit ``wait_for_all``                   10 von 10, Stapel jedes Mal
    #                                            „Garbage-collecting" über dieser Zeile
    #     ohne ``wait_for_all`` (Gegenprobe)      2 von 3, und an anderer Stelle
    #     mit ``wait_for_all`` + ``undisturbed``  5 von 5
    #
    # Der Mechanismus: Das Warten macht die Arbeiter **hier** fertig statt
    # irgendwann später. Damit liegt an dieser Stelle mehr Totes herum, der
    # gc-Lauf in ``processEvents`` findet mehr zum Abräumen, und was er abräumt,
    # während Qt an dieselben Widgets zustellt, wird zweimal zerstört. Auch
    # ``undisturbed()``, das genau dagegen gebaut ist, hält es nicht auf.
    #
    # Die Rechnung, die den Ausschlag gab: **ein sicherer Absturz gegen einen
    # seltenen Deadlock.** Der Hänger kam sechsmal in einer Nacht; dieser
    # Absturz traf jeden Lauf jeder Sitzung. Der Hänger bleibt damit offen —
    # ``leash.wait_for_all`` steht bereit und ist geprüft, es gehört nur nicht
    # **hierhin**, unmittelbar vor eine Zustellung.
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
