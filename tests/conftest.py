"""Gemeinsames Gerüst für die Tests.

Der Geometriekern ist nicht Teil von P0, die Tests benutzen also ein Netz, das
nur die Fragen beantwortet, die das ``Mesh``-Protokoll stellt. Das genügt für
Szene, Stapel und Auswertung — und es hält diese Tests ehrlich darüber, was sie
prüfen.
"""

from __future__ import annotations

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


#: Fenster und eigenständig gebaute Viewports, die die Suite absichtlich bis
#: zum Prozessende hält. Beide tragen VTK-Zustand; nur das Hauptfenster zu
#: halten schützt Dateien nicht, die den Viewport als eigene Prüfeinheit bauen.
_PINNED_UI: list[object] = []

#: Steht auf True, solange ein Test Zerstörung **messen** will (Fixture
#: ``unpinned_windows``) — dann wird nicht gepinnt.
_PIN_PAUSED = False


def _pin_ui_widgets(module: object) -> None:
    """Hängt den Pin an ``MainWindow`` und ``Viewport`` — je Typ einmal.

    Ein Hauptfenster hält seinen Viewport ohnehin. Einige Ansichtsprüfungen
    bauen den Viewport aber absichtlich allein; dessen VTK-Zustand braucht
    denselben Lebenszeitvertrag wie das ganze Fenster.
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
            if not _PIN_PAUSED:
                _PINNED_UI.append(self)

        widget_type.__init__ = pinning
        widget_type._suite_pinned = True


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
    """Pinnt beim Import des Fenstermoduls, nicht erst beim nächsten Test.

    Die Fixture ``_windows_live_to_the_end`` sieht das Modul nur, wenn es beim
    Teststart schon geladen ist. ``tests/test_sketch_editor.py`` importiert es
    erst im Testrumpf: Das erste Fenster jenes Prozesses entstand ungepinnt,
    starb mit seiner letzten Referenz mitten im Lauf und riss ihn mit dem
    bekannten 0xc0000374. Der Haken fängt den Import selbst ab und kostet
    sonst nichts — insbesondere keinen eifrigen Import von Qt und VTK in
    Läufe, die beides nie anfassen.
    """

    def find_spec(self, fullname: str, path: object = None, target: object = None) -> object:
        if fullname not in {"app.ui.main_window", "app.ui.viewport"}:
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


@pytest.fixture(autouse=True)
def _windows_live_to_the_end() -> Iterator[None]:
    """Jedes MainWindow der Suite lebt absichtlich bis zum Prozessende.

    **Warum, mit Messreihe vom 25.08.2026.** Die Mine darunter steht in
    ``_no_worker_outlives_its_window``: Die Zerstörung eines Fensters mit
    VTK-Zustand mitten im Prozess reißt den Lauf — gleich, ob der
    Speicherbereiniger sie auslöst oder die Referenzzählung, gleich in
    welchem Thread. Seit dem Ring-Umbau sterben die Fenster über die
    Referenzzählung, sobald ihr Fixture die letzte Referenz fallen lässt;
    mit dem Testbestand vom 25.08. riss ``test_ui.py`` damit deterministisch
    (3/3, 0xc0000374, Position wandert mit der Zusammensetzung, nicht mit
    einem Test). Zwischen 16:58 und dem Abend desselben Tages hielt
    versehentlich ein Lambda-Ring in ``_add_action`` jedes Fenster fest —
    und genau in dieser Zeit lief die Gruppe nachweislich stabil, bei rund
    1700 angesammelten Widgets. Der Pin stellt diesen Zustand **absichtlich**
    her, statt ihn einem Fehler zu verdanken: Der Tod der Fenster verschiebt
    sich ans Prozessende, wo der bekannte Abbau-Riss **nach** der
    Zusammenfassung liegt (``suite-getrennt.sh`` kennt die Behandlung),
    statt mitten in den Daten.

    Kein Zudecken: Die Mine selbst bleibt offen und steht im Register der
    ROADMAP. Der Kunde stellt den Suite-Zustand nie her — er hat ein
    Fenster, und das stirbt beim Prozessende.

    Drei Zusagen: Gepinnte Fenster bekommen weiter ihr ``release()`` (die
    Fixture unten läuft über ``topLevelWidgets``, Threads sammeln sich
    nicht an). Tests, die Zerstörung **messen**, nehmen sich über
    ``unpinned_windows`` aus — der 41-Lambda-Fund vom 25.08. muss auch
    künftig rot werden können. Und gepinnt wird beim **Erzeugen**, nicht am
    Testende: Die letzte Referenz eines Fenster-Fixtures fällt vor dem
    Teardown der autouse-Fixtures, dort wäre es längst tot.
    """
    # Der Regelfall läuft über den Import-Haken oben; dieser Griff bleibt als
    # zweiter für ein Modul, das schon vor dem Haken geladen war.
    for module_name in ("app.ui.viewport", "app.ui.main_window"):
        module = sys.modules.get(module_name)
        if module is not None:
            _pin_ui_widgets(module)
    yield


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

        from app.ui import leash

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
    # **Nachtrag vom selben Tag: Der Import-Lock hat genau eine Quelle.**
    # 3d-druck-b8 hat alle dynamischen Importe in ``app/core`` und ``app/ui``
    # gesucht — ``__import__``, ``import_module``, ``find_spec``. Sieben
    # Treffer, und von einem ``Worker.work()`` aus erreichbar ist **einer**:
    #
    #     app/core/install.py:341   present()   __import__(requirement.module)
    #     Weg dorthin: _Survey.work() -> install.statuses() -> present()
    #
    # Die fünf in ``bootstrap`` laufen beim Start, ``manual.messages_text``
    # gehört zur Handbucherzeugung; keiner davon steht in einem Arbeiter.
    #
    # **Damit ist die Warnung oben ein Zeiger geworden.** Sie sagt nicht mehr
    # „geh da nicht hin", sondern „dort ist es, und sonst nirgends" — und das
    # ist der Unterschied zwischen einem Punkt, den niemand anfasst, und einem,
    # den jemand löst. Ein Kandidat für den Ersatz steht auch schon:
    # ``importlib.util.find_spec(name)`` beantwortet dieselbe Frage, ohne das
    # Modul zu laden, und nimmt den Lock nicht. **Es ist aber eine
    # Verhaltensänderung und keine Umformulierung** — ``find_spec`` sagt
    # „liegt da", ``__import__`` sagt „lädt", und ein Paket mit kaputter
    # kompilierter Erweiterung meldet sich damit als vorhanden. Der Kommentar
    # an jener Stelle weiß das und nennt genau diesen Fall als Grund.
    #
    # **Entschieden am 23.08.2026: ``__import__`` bleibt.** Der Grund sind die
    # drei Pakete, die dort geprüft werden — ``OCP.BRepPrimAPI``
    # (OpenCASCADE), ``vhacdx`` und ``keyring``. Die ersten beiden sind
    # kompilierte Erweiterungen, und bei einer großen C++-Bibliothek mit
    # DLL-Abhängigkeiten ist „liegt da, lädt aber nicht" kein Randfall, sondern
    # der wahrscheinlichste Defekt:
    #
    #     find_spec    OCP liegt da   -> der Dialog bietet keine Installation an,
    #                                    der Kunde hat einen Kern, der nicht geht,
    #                                    und keinen Weg, das zu ändern
    #     __import__   OCP lädt nicht -> der Dialog bietet sie an, der Kunde
    #                                    repariert es
    #
    # **Der Erstlauf-Dialog fragt nicht „liegen Dateien da", sondern „kann ich
    # damit arbeiten".** Und der Lock-Effekt ist ein Testproblem, kein
    # Kundenproblem: Beim Kunden läuft ``statuses()`` genau einmal, und niemand
    # ruft daneben ``processEvents()`` in einer Schleife über zwanzig Läufe.
    #
    # ``leash.wait_for_all`` steht bereit und ist geprüft, es gehört nur nicht
    # **hierhin**, unmittelbar vor eine Zustellung.
    # Was bleibt, ist die eigentliche Ursache: nicht die Lebenszeit, sondern
    # die Verbindung. ``release`` kappt sie oben.
    #
    # **Der vierte und der fünfte Anlauf sind am 25.08.2026 gemessen und am
    # selben Abend wieder ausgebaut worden.** Beide setzten am Sammler an:
    # (4) ``gc.disable()`` für die Suite plus gezieltes ``gc.collect()`` an
    # dieser Stelle — der Lauf riss dann **in dieser Zeile**, im Hauptthread,
    # „Garbage-collecting" im Stapel, Zugriffsverletzung: Nicht der Thread
    # ist das Problem, sondern das Zerstören selbst. (5) ``gc.disable()``
    # ohne jedes Sammeln — riss ebenfalls, an einer Allokation weiter hinten
    # und **ohne** gc im Stapel: Die Fenster sterben seit dem Ring-Umbau über
    # die Referenzzählung, der Sammler ist an ihrem Tod meist unbeteiligt.
    # Wer hier weitersucht: Die Mine ist die Zerstörung eines Fensters mit
    # VTK-Zustand mitten in der Suite, gleich durch wen und in welchem
    # Thread. Messwerte vom 25.08.2026: test_ui.py mit vollem Testbestand
    # riss 3/3 deterministisch an fester Position (0xc0000374); die Position
    # wandert mit der Zusammensetzung, nicht mit einem Test.
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
