"""Gemeinsames Gerüst für die Tests.

Der Geometriekern ist nicht Teil von P0, die Tests benutzen also ein Netz, das
nur die Fragen beantwortet, die das ``Mesh``-Protokoll stellt. Das genügt für
Szene, Stapel und Auswertung — und es hält diese Tests ehrlich darüber, was sie
prüfen.
"""

from __future__ import annotations

import gc
import os
import sys
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
# HOME gehört dazu, und zwar für macOS: Dort läuft jede Nutzerverzeichnis-
# Auflösung über ``Path.home()`` (~/Library/…), und ohne den Eintrag las und
# schrieb die Suite in Roberts echtem Profil — §38 griff auf genau der
# Plattform nicht, die die XDG-Variablen nie liest (Gesamtreview-b, Tests 1).
# Auf Windows ist der Eintrag folgenlos (Python nimmt USERPROFILE); der Beleg
# auf macOS ist der nächste Suitenlauf dort — von dieser Maschine aus ist er
# nicht zu führen.
for _variable in (
    "APPDATA",
    "LOCALAPPDATA",
    "HOME",
    "XDG_DATA_HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
):
    os.environ[_variable] = _ISOLATED

from app.core import discover
from app.core.activation import store as activation_store
from app.core.knowledge import profiles
from app.core.perceive import features
from app.core.types import BoundingBox, Document, Profile, SceneObject

#: Der Stichtag der Demo, gesichert bevor die Fixture unten ihn wegnimmt.
_SHIPPED_DEMO_UNTIL = activation_store.DEMO_UNTIL
#: Der tatsächlich ausgelieferte Testbeginn. Die Suite aktiviert den
#: erhaltenen Pfad darunter für seine Mechaniktests wieder.
_SHIPPED_TRIAL_FROM = activation_store.TRIAL_FROM


#: Fenster und eigenständig gebaute Viewports, die bis zu ihrem geordneten
#: Testabbau gehalten werden. Der Pin verhindert, dass die letzte Referenz
#: schon während eines Fixture-Teardowns fällt; nach ``release`` wird er noch
#: im selben Test wieder gelöst.
_PINNED_UI: list[object] = []

#: Steht auf True, solange ein Test Zerstörung **messen** will (Fixture
#: ``unpinned_windows``) — dann wird nicht gepinnt.
_PIN_PAUSED = False


def _pin_ui_object(value: object) -> None:
    """Eine Oberfläche genau einmal bis zum Abbau ihres Tests halten."""
    if not _PIN_PAUSED and not any(held is value for held in _PINNED_UI):
        _PINNED_UI.append(value)


def _pin_ui_widgets(module: object) -> None:
    """Hängt den Pin an Fenster, Viewport und Leinenbesitzer — je Typ einmal.

    Ein Hauptfenster hält seinen Viewport ohnehin. Einige Ansichtsprüfungen
    bauen den Viewport aber absichtlich allein; dessen Renderer-Zustand braucht
    denselben Lebenszeitvertrag wie das ganze Fenster. Elternlose Dialoge mit
    Arbeitern brauchen ihn ebenfalls: Ohne den früheren Rückverweis ihrer
    ``WorkerLeash`` kann ihre letzte Testreferenz vor der zentralen
    ``release``-Fixture fallen. Die Leine hält den Besitzer im Produkt bewusst
    nicht; die Suite hält nur das Qt-Widget bis zu genau diesem Teardown.
    """
    for type_name in ("MainWindow", "Viewport"):
        widget_type = getattr(module, type_name, None)
        if widget_type is None or getattr(widget_type, "_suite_pinned", False):
            continue
        original = widget_type.__init__

        def pinning(
            self: object,
            *args: object,
            _original: object = original,
            **kwargs: object,
        ) -> None:
            _original(self, *args, **kwargs)  # type: ignore[operator]
            _pin_ui_object(self)

        widget_type.__init__ = pinning
        widget_type._suite_pinned = True

    leash_type = getattr(module, "WorkerLeash", None)
    if leash_type is None or getattr(leash_type, "_suite_owner_pinned", False):
        return
    original_leash_init = leash_type.__init__

    def pinning_leash_owner(
        self: object,
        context: object,
        *args: object,
        **kwargs: object,
    ) -> None:
        original_leash_init(self, context, *args, **kwargs)
        from PySide6.QtWidgets import QWidget

        # MainWindow und Viewport werden erst nach ihrem vollständigen Aufbau
        # über den Klassenhaken oben gehalten. Alle anderen QWidget-Besitzer
        # der Leine sind Dialoge, deren Konstruktor den Arbeiter bereits
        # startet und die deshalb bis zur release-Fixture leben müssen.
        if isinstance(context, QWidget) and not getattr(type(context), "_suite_pinned", False):
            _pin_ui_object(context)

    leash_type.__init__ = pinning_leash_owner
    leash_type._suite_owner_pinned = True


class _PinningLoader:
    """Führt den echten Lader aus und pinnt danach — sonst nichts."""

    def __init__(self, wrapped: object) -> None:
        self._wrapped = wrapped

    def create_module(self, spec: object) -> object:
        return self._wrapped.create_module(spec)  # type: ignore[attr-defined]

    def exec_module(self, module: object) -> None:
        self._wrapped.exec_module(module)  # type: ignore[attr-defined]
        _pin_ui_widgets(module)


class _PinOnImport:
    """Pinnt beim Import der Lebensdauermodule, nicht erst beim nächsten Test.

    Die Fixture ``_windows_live_until_their_test_ends`` sieht das Modul nur, wenn es beim
    Teststart schon geladen ist. ``tests/test_sketch_editor.py`` importiert es
    erst im Testrumpf: Das erste Fenster jenes Prozesses entstand ungepinnt,
    starb mit seiner letzten Referenz mitten im Lauf und riss ihn mit dem
    bekannten 0xc0000374. Der Haken fängt den Import selbst ab und kostet
    sonst nichts — insbesondere keinen eifrigen Import von Qt und pygfx in
    Läufe, die beides nie anfassen. ``app.ui.leash`` kommt hinzu, damit ein
    elternloser Dialog bis zu seiner zentralen ``release``-Phase lebt, ohne
    dass der Produktcode dafür seinen Besitzer zyklisch halten muss.
    """

    def find_spec(self, fullname: str, path: object = None, target: object = None) -> object:
        if fullname not in {"app.ui.leash", "app.ui.main_window", "app.ui.viewport"}:
            return None
        import importlib.util

        # Sich selbst kurz aus der Kette nehmen, sonst fragt find_spec hierher
        # zurück. Der Importmechanismus hält währenddessen sein Schloss.
        sys.meta_path.remove(self)
        try:
            spec = importlib.util.find_spec(fullname)
        finally:
            sys.meta_path.insert(0, self)
        if spec is None or spec.loader is None:
            return None
        spec.loader = _PinningLoader(spec.loader)  # type: ignore[assignment]
        return spec


sys.meta_path.insert(0, _PinOnImport())


#: Die Testdateien, in denen verwaiste Dialoge zwischen den Tests sterben —
#: und **nur** sie. Gemessen am 03.09.2026: Ein Sammellauf nach jedem Test
#: über die ganze Suite reißt selbst (0xc0000374, Stapel „Garbage-collecting",
#: zweimal von zwei), sobald Geometrie im Prozess liegt; dieselbe Gruppe ohne
#: ihn läuft 636 grün in 57 s. Das ist die Kehrseite derselben Mine, die in
#: ``_no_worker_outlives_its_window`` steht: Zerstörung zur falschen Zeit.
#: Wer eine Datei aufnimmt, misst sie vorher am Stück und in Gesellschaft.
_DIALOG_MODULES = frozenset({"test_print_settings_ui", "test_install"})


@pytest.fixture(autouse=True)
def _orphaned_widgets_die_between_tests(request: pytest.FixtureRequest) -> Iterator[None]:
    """Verwaiste Widgets sterben zwischen zwei Tests — nie mitten im Bau des nächsten.

    **Die Mine, mit Messreihe vom 02.09.2026.** ``test_print_settings_ui.py``
    riss am Stück deterministisch (lokal Exit 139, in der CI beide Anläufe
    derselben Fünferportion), der Stapel jedes Mal in ``QLabel(...)`` beim
    Bau eines Dialogs — dieser Frame ist die nächste Allokation, nicht die
    Ursache. Die Ursache: Ein Dialog ohne Parent, den ein Test dem
    Speicherbereiniger überlässt, stirbt in dessen nächstem Lauf, und den
    löst eine Allokation aus — mitten im Konstruktor des nächsten Dialogs.
    Ein Widget zerstören, während ein anderes gerade entsteht, ist der Riss.

    Gemessen an derselben Fünferportion: ``gc.disable()`` grün, ein Abbau
    nach jedem Test sechsmal von sechs grün, ohne beides zweimal von zwei
    rot. Die ganze Datei: ohne Abbau Segfault, mit Abbau 114 grün in drei
    Sekunden. Die Anwendung ist nicht betroffen — sie baut den Dialog mit
    Parent und ruft ``deleteLater`` nach ``exec``.

    **Und nur in den zwei Dateien aus ``_DIALOG_MODULES``.** Über die ganze
    Suite gelegt riss der Sammellauf am 03.09.2026 selbst — der Kommentar
    dort nennt die Messung. Die Bedingung ist eine gemessene Grenze und keine
    Vorsicht: Wer eine dritte Datei aufnimmt, misst sie vorher.

    **Nur dort, wo die Suite keine Fenster hält.** Ein ``gc.collect()`` nach
    jedem Test ist am 23.08.2026 gefallen (die Messreihe steht in
    ``_no_worker_outlives_its_window``): In einer Fensterdatei zerstörte es
    auch Renderer-Zustand zu einem beliebigen Zeitpunkt. Der Pin
    (``_windows_live_until_their_test_ends``) schützt heute bis zum geordneten
    Fensterabbau. Erst danach darf diese Fixture verwaiste Dialoge sammeln,
    und nur, wenn noch ein Top-Level-Widget lebt.

    **Über den Sammler, nicht über ``deleteLater``.** Beides gemessen:
    ``deleteLater`` plus ``sendPostedEvents`` zwischen den Tests ließ
    ``test_generate_ui.py`` mit 127 enden statt mit 0 — zweimal von zwei,
    mit ``close()`` davor ebenso. Ein Dialog mit Arbeitern hinterlässt bei
    vorzeitiger Qt-Zerstörung etwas, das am Prozessende reißt; der Sammler
    zerstört ihn erst, wenn nichts mehr auf ihn zeigt, und im Hauptthread
    zwischen zwei Tests.

    Zuerst definiert, damit ihr Abbau zuletzt läuft — nach ``release`` der
    Fenster und nach jedem ``monkeypatch``.
    """
    yield
    if request.node.module.__name__.rpartition(".")[2] not in _DIALOG_MODULES:
        return
    if "PySide6.QtWidgets" not in sys.modules or _PINNED_UI:
        return
    from PySide6.QtWidgets import QApplication
    from shiboken6 import isValid

    application = QApplication.instance()
    if application is None:
        return
    if any(isValid(widget) for widget in application.topLevelWidgets()):
        gc.collect()


@pytest.fixture(autouse=True)
def _windows_live_until_their_test_ends() -> Iterator[None]:
    """Hält neue Fenster bis zu ihrem geordneten Abbau in diesem Test.

    Der Pin muss beim Erzeugen greifen: Ein Fenster-Fixture verliert seine
    letzte normale Referenz vor dem Teardown der autouse-Fixtures. Bis 0.3.4
    blieb der Pin danach bis zum Prozessende stehen, weil VTKs Renderer keinen
    unabhängigen Abbau trug. Mit pygfx ist das Gegenteil nötig und möglich:
    ``release`` kappt Rückrufe und wartet auf Arbeiter, der Renderer wird an
    seiner noch lebenden Fläche geschlossen, danach stellt Qt die Löschung im
    Hauptthread zu.

    Gemessen an den ersten 60 Analyse-UI-Tests sammelte der alte Vertrag 34
    gültige ``MainWindow``-Wurzeln und 1073 Qt-Fenster samt Kind-Popups an;
    derselbe Lauf riss im Release-Tor wandernd in einer Zustellung an ein neu
    gebautes Fenster. Wer Zerstörung selbst misst, pausiert den Pin weiterhin
    über ``unpinned_windows``.
    """
    # Pytest hält die Funktionsargumente eines gerade beendeten Tests noch bis
    # hinter dessen Fixture-Abbau. Dadurch kann ein kompletter, bereits nativ
    # gelöschter Fensterbaum erst hier zyklisch frei werden. Er wird im
    # Hauptthread eingesammelt, bevor ein neuer Arbeiter starten kann.
    _collect_released_ui()
    # Der Regelfall läuft über den Import-Haken oben; dieser Griff bleibt als
    # zweiter für ein Modul, das schon vor dem Haken geladen war.
    for module_name in ("app.ui.viewport", "app.ui.main_window"):
        module = sys.modules.get(module_name)
        if module is not None:
            _pin_ui_widgets(module)
    first = len(_PINNED_UI)
    try:
        yield
    finally:
        held = _PINNED_UI[first:]
        del _PINNED_UI[first:]
        _release_pinned_ui(held)


def _release_pinned_ui(held: list[object]) -> None:
    """Gepinnte Qt-Wurzeln in derselben Reihenfolge wie die Suite abbauen."""
    if "PySide6.QtWidgets" not in sys.modules:
        held.clear()
        return

    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication, QWidget
    from shiboken6 import isValid

    def roots_of(values: list[object]) -> list[QWidget]:
        """Qt-Wurzeln bestimmen, ohne eine letzte Hülle im Außenrahmen zu halten."""
        found: list[QWidget] = []
        for value in values:
            if not isinstance(value, QWidget) or not isValid(value):
                continue
            root = value
            while True:
                parent = root.parent()
                if not isinstance(parent, QWidget):
                    break
                root = parent
            if not any(known is root for known in found):
                found.append(root)
        return found

    def release_renderers(values: tuple[object, ...]) -> None:
        """Renderer schließen, solange ihre Python-Wurzeln sicher leben."""
        for value in values:
            if not isinstance(value, QWidget) or not isValid(value):
                continue
            release_renderer = getattr(type(value), "release_renderer", None)
            if callable(release_renderer):
                release_renderer(value)

    def schedule_deletion(values: list[QWidget]) -> None:
        """Wurzeln vormerken, ohne die letzte Hülle im Außenrahmen zu halten."""
        for value in values:
            if isValid(value):
                value.hide()
                value.deleteLater()

    roots = roots_of(held)

    # ``_no_worker_outlives_its_window`` lief wegen der Fixture-Abhängigkeit
    # davor. Hier bleibt nur der native Abbau des Renderers und der Qt-Wurzel;
    # beides geschieht, solange der Pin seine Python-Hülle hält.
    release_renderers((*held, *roots))

    schedule_deletion(roots)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application = QApplication.instance()
    if application is not None:
        application.processEvents()
    # Die Python-Hüllen bleiben bis hinter Qts rekursiven C++-Abbau stark
    # gehalten. Würde der Pin vorher fallen, könnte eine Elternhülle mitten in
    # der Zerstörung ihres Kinddialogs verschwinden; der nächste native
    # Widget- oder Workeraufbau trifft dann auf beschädigten Speicher.
    held.clear()
    roots.clear()
    # ``DeferredDelete`` hat die C++-Hierarchie jetzt vollständig im
    # Hauptthread zerstört. Python-Ringe um ihre Shiboken-Hüllen müssen an
    # derselben sicheren Grenze folgen: In 30 UI-Tests blieben sonst nach
    # jedem Abbau 300 bis 970 ungültige QWidget-Hüllen zurück. Ein späterer
    # zyklischer Sammlerlauf verschob ihren Abbau damit an eine spätere
    # Allokationsstelle. Die nativen Abbrüche traten dort wandernd auf; einen
    # bestimmten auslösenden Faden belegt diese Messung nicht.
    #
    # Das ist nicht der alte, unwirksame Sammelversuch aus
    # ``_no_worker_outlives_its_window``: Er lief vor einem geordneten nativen
    # Abbau. Hier sind Renderer geschlossen, Worker zugestellt und C++-Wurzeln
    # bereits gelöscht; gesammelt werden nur noch deren Python-Ringe.
    _collect_released_ui()


def _collect_released_ui() -> None:
    """Bereits nativ gelöschte Python-Widgetringe im Hauptthread sammeln."""
    if "PySide6.QtWidgets" not in sys.modules:
        return
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        return
    gc.collect()


@pytest.fixture
def unpinned_windows() -> Iterator[None]:
    """Für Tests, die Zerstörung messen — der Pin pausiert.

    Ohne diesen Ausweg wäre der Leck-Detektor stumpf: Ein Fenster, das die
    Suite selbst festhält, überlebt jedes Loslassen, und ein Fund wie die 41
    Lambda-Ringe in ``_add_action`` (25.08.2026) bliebe unauffindbar.
    """
    global _PIN_PAUSED
    _PIN_PAUSED = True
    try:
        yield
    finally:
        _PIN_PAUSED = False


@pytest.fixture(autouse=True)
def _the_calendar_stays_out_of_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Suite misst die Mechanik der Demo, nicht das Kalenderblatt.

    Der ausgelieferte Stichtag ist ein Datum. Ohne diese Zeile wäre die Suite
    ab dem Tag danach rot — an Dutzenden Stellen, die mit der Frist nichts zu
    tun haben, weil jede Dokumentänderung durch die Freischaltung geht.

    Wer die Frist selbst prüft, setzt sie ausdrücklich; `test_activation.py`
    tut das über die Fixture `demo`. Für alle anderen Läufe beginnt stattdessen
    ein Testzeitraum am Auslieferungstag, damit die Suite nicht vom Kalender
    gesperrt wird. Den **echten** Wert bekommt nur, wer ihn über
    `shipped_demo_until` verlangt — dort steht auch der Wecker, der anschlägt,
    wenn der Stichtag verstrichen ist.
    """
    monkeypatch.setattr(activation_store, "DEMO_UNTIL", None)
    monkeypatch.setattr(activation_store, "TRIAL_FROM", activation_store.DEMO_FROM)


@pytest.fixture
def shipped_demo_until() -> object:
    """Der Stichtag, mit dem tatsächlich ausgeliefert wird — oder ``None``."""
    return _SHIPPED_DEMO_UNTIL


@pytest.fixture
def shipped_trial_from() -> object:
    """Der Testbeginn der ausgelieferten Fassung — vor dem Suite-Patch."""
    return _SHIPPED_TRIAL_FROM


@pytest.fixture(autouse=True)
def _machine_stays_out_of_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Suite fragt nicht die Maschine, auf der sie läuft (§38).

    Dieselbe Begründung wie bei den Nutzerverzeichnissen oben: ein
    Entwicklerrechner mit installiertem Slicer sieht sonst etwas anderes als
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
    def only_what_was_set_plural(tool_id: str, names: object) -> object:
        single = only_what_was_set(tool_id, names)
        return () if single is None else (single,)

    monkeypatch.setattr(discover, "unpatched_find_program", discover.find_program, raising=False)
    monkeypatch.setattr(discover, "find_program", only_what_was_set)
    # **Die Mehrzahl braucht denselben Riegel**, und ohne ihn war er weg: Seit
    # der Slicer-Auswahl fragt der Dialog :func:`discover.find_programs`, und
    # die suchte an der Attrappe vorbei auf der echten Maschine. Ein
    # Entwicklerrechner mit drei Slicern sah damit etwas anderes als der
    # Bauserver mit keinem — genau die Abhängigkeit, die diese Fixture
    # ausschließt (§38). Aufgefallen an zwei Tests, die ohne Fund rechneten
    # und plötzlich ElegooSlicer vorfanden (30.08.2026).
    monkeypatch.setattr(discover, "unpatched_find_programs", discover.find_programs, raising=False)
    monkeypatch.setattr(discover, "find_programs", only_what_was_set_plural)
    discover.forget_cache()


@pytest.fixture(autouse=True)
def _remembered_features_stay_out_of_it() -> None:
    """Kein Test erbt die Erkennung eines anderen.

    ``perceive.features`` merkt sich Erkennungsergebnisse je Netz, damit
    dieselbe Geometrie nicht nach jeder Operation neu untersucht wird — 65
    Prozent der Erkennungszeit über die neun Beispiele lagen auf bitgleichen
    Netzen. Der Cache lebt so lange wie der Prozess, und ein Testlauf ist ein
    Prozess: Ohne diese Zeile hängt das Ergebnis eines Tests davon ab, welcher
    vor ihm lief.

    Aufgefallen ist es sofort und an der richtigen Stelle:
    ``test_the_expensive_search_runs_once_per_detection`` zählt die Aufrufe der
    teuren Suche und erwartet genau einen — bei gefülltem Cache lief sie null
    mal. Der Test hat recht und bleibt, wie er ist; falsch war die fehlende
    Isolation. Dieselbe Begründung wie bei ``discover.forget_cache()`` weiter
    oben (§38).
    """
    features.forget_cache()


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

    Dieselbe Begründung wie bei den Fremdprogrammen eine Fixture darüber, nur
    eine Ebene weiter: Die Isolation deckte Qt, die Nutzerverzeichnisse und die
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
def _the_language_starts_at_the_source() -> Iterator[None]:
    """Die Anzeigesprache ist derselbe Fall wie die Einheit darunter.

    ``set_language`` schreibt eine Modulvariable, nicht ein Widget — ein Test,
    der auf Französisch stellt, nähme jeden folgenden mit, und der fiele an
    einem Text um, der nichts mit ihm zu tun hat. Für die Einheit gab es diese
    Klammer seit je, für die Sprache nicht.

    **Und sie fängt heute nichts**, das gehört dazu: Eine Sonde über einen
    ganzen Lauf (407 Tests) hat **null** Sprachwechsel gemeldet. Sie steht hier
    nicht wegen eines Falles, sondern weil die Asymmetrie sonst der nächste
    Fund wäre — dieselbe Sorte Zustand, einmal geklammert und einmal nicht.

    **Zurückgesetzt wird auf die Quellsprache, also den Auslieferungszustand.**
    Das ist bei der Sprache dasselbe wie der Kundenzustand; bei anderen
    Zuständen ist es das nicht, und dann wäre eine solche Fixture falsch —
    siehe den Hinweis zum Stylesheet unten.
    """
    yield
    try:
        from app.i18n import SOURCE_LANGUAGE, set_language
    except ImportError:  # pragma: no cover - ohne die Kataloge gibt es nichts zu räumen
        return
    set_language(SOURCE_LANGUAGE)


#: **Was hier absichtlich NICHT zurückgesetzt wird: das Stylesheet.**
#:
#: ``apply_theme`` legt es über die *Anwendung*, und ``app.py`` tut das beim
#: Start — der Kunde sieht die Oberfläche also nie ohne. Eine Fixture, die es
#: nach jedem Test abräumt, stellte einen Zustand her, den es im Betrieb nicht
#: gibt: Ein Test, der Abstände oder Innenmaße misst, bekäme Zahlen, die
#: niemand je sieht.
#:
#: **Womit dieser Hinweis am 30.08.2026 begründet war, trug allerdings nicht.**
#: Hier stand, die Parameterkarte messe ohne Stylesheet 258 und mit 270 gegen
#: eine Zone von 260, ein Rücksetzen hätte also einen Kundenfehler zugedeckt.
#: Beide Zahlen stammten aus einem Offscreen-Lauf, und dort hat Qt gar keine
#: Schrift — am echten Bildschirm sind es 166 mit Stylesheet wie ohne. Der
#: Hinweis bleibt, weil das Stylesheet Abstände wirklich verändert; die
#: Kartenbreite ist nur kein Beleg dafür.
#:
#: Wer eine Rücksetzung baut, prüft deshalb zuerst: Setzt sie auf das zurück,
#: was der Kunde hat, oder auf ein nacktes Nichts? Ein Thema, ein Stylesheet,
#: ein geladenes Register gehören zur Betriebslage. Wer eine Breite oder ein
#: Layout misst, stellt sie **her** (``apply_theme`` im Test), statt sie
#: wegzuräumen.


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
    labels.set_circle_measure("diameter")


@pytest.fixture(autouse=True)
def _no_backend_stays_rejected() -> Iterator[None]:
    """Dieselbe Begründung wie darüber, für einen zweiten Prozesszustand.

    Seit dem 24.08.2026 merkt sich ``llm._rejected``, welchen Zugang die
    Gegenseite abgelehnt hat — sonst sperrt ein ungültiger Schlüssel das lokale
    Modell für den Rest der Sitzung aus. Gesetzt wird der Merker **nicht nur im
    Test**: ``AnthropicBackend.complete`` tut es bei jedem 401 selbst. Ein Test,
    der einen abgelehnten Schlüssel durchspielt, nähme also jeden folgenden mit,
    und der fiele an einem Backend um, das er nie angefasst hat — mit
    ``pytest-randomly`` an einem anderen je Lauf.
    """
    yield
    from app.core.backends import llm

    llm.accept_again()


@pytest.fixture(autouse=True)
def _no_user_parts_stay_loaded() -> Iterator[None]:
    """Dritter Prozesszustand, dieselbe Begründung wie die zwei darüber.

    bootstrap.load_user_parts merkt sich, dass es gelaufen ist, und seit dem
    24.08.2026 auch, **welche** Operationen aus dem Nutzerordner kamen — die
    Oberfläche hält sie aus der Menüleiste heraus (§24.5, Konzept E1).

    Gesetzt wird das im Test wie im Produkt: tests/test_parts_catalog.py
    ruft load_user_parts mit einem eigenen Verzeichnis. Heute trägt der
    Merker danach nichts, weil jene Datei absichtlich kaputt ist und gar nichts
    lädt — ein Test mit einem **gültigen** eigenen Baustein nähme jeden
    folgenden mit, und der fiele an einer Menüleiste um, die er nie angefasst
    hat. Mit pytest-randomly an einem anderen je Lauf.

    **Und die Register selbst, nicht nur die Merker.** Nur die Merker zu
    leeren kehrte den Schutz um: Die Operationen und Katalogeinträge eines
    gültigen eigenen Bausteins blieben registriert, während die Auskunft
    ``user_operations()`` behauptete, es gebe keine — die Menüleiste zeigte
    sie dann, und die Grenzentests zählten Einträge, die aus einer fremden
    Maschine stammen. Abgemeldet wird über die Namen, die der Merker vor dem
    Leeren noch kennt; ``remove`` ist an beiden Registern idempotent.
    """
    yield
    from app.core import bootstrap

    if bootstrap._user_operations:
        from app.core.knowledge.parts.ops import part_of
        from app.core.knowledge.parts.registry import PARTS
        from app.core.registry import REGISTRY

        for operation in bootstrap._user_operations:
            spec = part_of(operation)
            if spec is not None:
                PARTS.remove(spec.name)
            REGISTRY.remove(operation)
    bootstrap._user_loaded = False
    bootstrap._user_findings = ()
    bootstrap._user_operations = ()


#: Die Warte-Methoden je Widget-Klasse, einmal ermittelt.
#:
#: **``dir()`` je Klasse statt je Widget.** Die Fixture unten geht nach *jedem*
#: Test durch *alle* Top-Level-Widgets, und ``dir()`` auf einer Qt-Klasse
#: liefert 352 Namen. Bei 159 Widgets sind das 5,8 ms je Test und 1,5 s über
#: einen Lauf von ``test_ui.py`` — für eine Antwort, die sich je Klasse nie
#: ändert. Die Widgets verteilen sich auf eine Handvoll Klassen; gemessen am
#: 23.08.2026 waren es vier.
_WARTE_METHODEN: dict[type, tuple[str, ...]] = {}


def _wartet_auf_arbeiter(klasse: type) -> tuple[str, ...]:
    """Wie diese Klasse „warte auf deinen Arbeiter" nennt — leer, wenn gar nicht."""
    bekannt = _WARTE_METHODEN.get(klasse)
    if bekannt is None:
        bekannt = tuple(name for name in sorted(dir(klasse)) if name.startswith("wait_for_"))
        _WARTE_METHODEN[klasse] = bekannt
    return bekannt


@pytest.fixture(autouse=True)
def _no_worker_outlives_its_window(
    _windows_live_until_their_test_ends: None,
) -> Iterator[None]:
    """Nach jedem Test alle UI-Arbeiter geordnet fertigstellen.

    Der Produktweg wartet beim Schließen eines Fensters selbst. Tests schließen
    ihre Widgets häufig nicht ausdrücklich; deshalb ruft diese zentrale
    Fixture zunächst deren vorhandene ``release``- oder ``wait_for_*``-Wege
    auf und wartet anschließend auch auf fensterlose Leinen. Die abhängige
    Fixture ``_windows_live_until_their_test_ends`` hält die Python-Hüllen
    dabei bis zur zugestellten Qt-Löschung und sammelt erst danach ihre Ringe.
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
        # **Von der Klasse geholt, nicht vom Objekt** — und das ist kein Stil.
        # ``getattr(objekt, "name")`` erzeugt eine **gebundene** Methode, und
        # die hält ihr ``__self__``. Die Variable überlebt den Schleifendurchlauf
        # und hält damit das zuletzt behandelte Fenster bis zum nächsten
        # Testende fest: **Die Aufräumfixture hielt selbst ein Widget, das sie
        # loslassen sollte.** Gefunden am 23.08.2026 von 3d-druck-b8, deren
        # eigener Lebensdauertest dieselben vier Zeilen trug und deshalb
        # „1 von 10 überlebten" meldete — nie null, nie zehn, immer genau eines.
        release = getattr(type(widget), "release", None)
        if callable(release):
            release(widget)
        else:
            for name in _wartet_auf_arbeiter(type(widget)):
                waiter = getattr(type(widget), name, None)
                if callable(waiter):
                    waiter(widget)
    # Fensterlose Dialoge können schon aus ``topLevelWidgets`` verschwunden
    # sein, während ihre Leine den Arbeiter noch hält. Die modulweite Menge ist
    # die einzige vollständige Auskunft; erst nach dem Warten dürfen Qts
    # eingereihte ``finished``-Signale und Löschungen laufen.
    from app.ui import leash

    leash.wait_for_all()
    for _ in range(5):
        application.processEvents()
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
        from collections import Counter
        from pathlib import Path

        from PySide6.QtWidgets import QWidget

        oben = application.topLevelWidgets()
        lebende = [widget for widget in oben if isValid(widget)]
        # **Die vierte Spalte beantwortet eine andere Frage als die ersten
        # drei.** Solange ein Arbeiter lebt, hält ihn ``leash._alive``
        # modulweit, und über sein ``finished``-Lambda hält er seinen Dialog —
        # das ist kein Leck, sondern der Zweck der Leine (``leash.py:213``).
        # Wenn die Widgetzahl also zu einem guten Teil aus Fenstern mit
        # laufendem Arbeiter besteht, lautet die Frage nicht „wer hält sie",
        # sondern **„warum laufen so viele Arbeiter noch"**. Vorgeschlagen von
        # 3d-druck-b8 am 23.08.2026.
        ziel = Path(os.environ["SOLIDON_ZAEHLE_WIDGETS"])
        with ziel.open("a", encoding="utf-8") as datei:
            # **Die fünfte Spalte sagt, *was* liegenbleibt, und das ist die
            # eigentliche Auskunft.** Am 23.08.2026 bestanden 198
            # liegengebliebene Fenster aus 120 ``QMenu``, 53 ``QFrame``,
            # 21 ``KeyDialog`` und 4 ``MainWindow`` — **87 Prozent waren keine
            # Dialoge.** Wer nur die Summe sieht, räumt an Dialogen auf und
            # bewegt sie kaum; die Masse sind Menüs, die in Qt eigenständige
            # Fenster sind.
            # **Die Wurzeln sind die Zahl, die etwas bedeutet.** Ein ``QMenu``
            # ist in Qt ein Popup und steht deshalb in ``topLevelWidgets()``,
            # obwohl es ein **Kind** ist — es lebt und stirbt mit seiner
            # Menüleiste. Am 23.08.2026 hat 3d-druck-b8 die 159 Fenster
            # vollständig aufgelöst, ohne Rest:
            #
            #     ein MainWindow bringt  30 QMenu + 8 QFrame mit
            #     ein KeyDialog bringt    1 QFrame mit
            #
            #     3 mal 30                      =  90 QMenu
            #     3 mal 8 + 21 mal 1           =  45 QFrame
            #                                      21 KeyDialog + 3 MainWindow
            #
            # **159 Fenster sind 24 unabhängige Objekte.** Wer die Summe liest,
            # ist um Faktor 6,6 daneben: Ein befreiter Dialog senkt sie um 2, ein
            # befreites Hauptfenster um 39. „159 → 120" sieht nach 39 Objekten
            # aus und ist eines.
            wurzeln = [widget for widget in lebende if widget.parent() is None]
            zaehlung = Counter(type(widget).__name__ for widget in wurzeln)
            print(
                len(oben),
                len(wurzeln),
                len(QWidget.__subclasses__()),
                len(leash.alive()) if hasattr(leash, "alive") else len(leash._alive),
                ",".join(f"{name}:{wie_oft}" for name, wie_oft in zaehlung.most_common()),
                file=datei,
            )

    # Erst die abhängige Fixture löscht Renderer und Qt-Wurzeln. Hier muss nur
    # noch die letzte von ``finished`` eingereihte Zustellung ankommen, solange
    # alle Fensterhüllen gepinnt und gültig sind.
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


@pytest.fixture(autouse=True)
def _the_pointer_size_of_this_machine_stays_out_of_it() -> Iterator[None]:
    """Die Zeigergröße des Entwicklerrechners gehört nicht ins Ergebnis (§38).

    Dieselbe Begründung wie bei den Nutzerverzeichnissen und den gefundenen
    Fremdprogrammen, nur eine Ebene weiter: Seit dem 27.08.2026 liest
    ``cursors.system_size`` die **echte** Systemeinstellung — unter Windows aus
    der Registry, unter macOS über ``defaults``, unter Linux aus
    ``XCURSOR_SIZE``. Eine Maschine, auf der jemand seine Zeiger auf 48
    gestellt hat, sähe damit etwas anderes als der Bauserver, und der gemerkte
    Wert überlebte zusätzlich jeden Test.

    Geleert wird nur, wenn das Modul überhaupt geladen ist: Für die
    allermeisten Tests wäre ein Import von ``app.ui.cursors`` das Laden von Qt
    ohne jeden Anlass.
    """
    yield
    module = sys.modules.get("app.ui.cursors")
    if module is not None:
        module.forget()
