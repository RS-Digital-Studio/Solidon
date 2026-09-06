"""Wird ein losgelassenes Widget wirklich freigegeben? (Regel 18 nicht, aber §35)

**Die Abnahme für den Umbau der Referenzringe, und sie zählt keine Stellen.**
Ein Rückruf, der `self` fängt, an einem Sender, der ein Kind von `self` ist,
schließt einen Ring über die C++-Grenze: `self` → Sender → Rückruf → `self`.
Pythons Speicherbereiniger sieht die mittlere Kante nicht und kann ihn nicht
brechen — das Widget lebt bis zum Prozessende, und in der Suite sind das
siebenhundert Fenster nacheinander.

Dagegen hilft keine Zählung: Dreiunddreißig richtig umgebaute Stellen plus eine
neue falsche ergeben denselben Zustand wie vorher. Was hilft, ist diese Frage,
je Widget-Klasse gestellt — sie wird rot, sobald irgendwo ein Lambda dazukommt,
und sie muss dafür nicht wissen, wo.

Die Formen, gemessen am 22.08.2026 (je zehn Objekte losgelassen):

    connect(self.tue)                       0 von 10 überleben   frei
    connect(lambda: self.tue())            10 von 10             Ring
    connect(partial(self.tue, 1))          10 von 10             Ring
    connect(lambda x=1: self.tue(x))       10 von 10             Ring

`functools.partial` ist die Überraschung darin: Es sieht aus wie die saubere
Fassung eines Lambdas und hält den Besitzer genauso fest.
"""

from __future__ import annotations

import gc
import weakref
from collections.abc import Callable
from typing import cast

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QWidget

#: **Der Weg für die, die beim Aufbau zu arbeiten anfangen.**
#:
#: Hier stand lange, dass ``InstallDialog``, ``KeyDialog`` und ``PartCatalog``
#: „hier hineingehören, sobald es einen verlässlichen Weg gibt, ihre laufende
#: Arbeit abzuwarten". Den gibt es seit dem 23.08.2026, und er ist keine
#: Erfindung dieses Tests, sondern das, was das Hauptfenster beim Schließen
#: auch tut:
#:
#:     release()  →  leash.wait_for_all()  →  processEvents()
#:
#: Der letzte Schritt ist der, der fehlte. ``leash._alive`` hält einen
#: Arbeiter modulweit, und er hält über sein ``finished``-Lambda die Leine und
#: damit den Dialog. Aufgeräumt wird erst, wenn das Signal ankommt — dafür
#: braucht es eine Runde Ereignisverarbeitung. Gemessen an ``FirstRunDialog``
#: und ``PrintSettingsDialog``:
#:
#:     nur loslassen         10 von 10 überleben
#:     release()             10 von 10
#:     release() + Schleife   0 von 10
#:
#: Dass ``release()`` **allein** nichts ändert, ist der Teil, den man sonst
#: falsch schließt: Es sieht aus wie ein Leck und ist ein fehlendes
#: ``processEvents``.

#: Wie viele je Klasse gebaut und losgelassen werden.
#:
#: Zehn und nicht eines: Ein einzelnes Widget kann aus Gründen überleben, die
#: mit dem Ring nichts zu tun haben — ein Zwischenergebnis in einem Rahmen, ein
#: Verweis in einer Ausnahme, die noch im Traceback hängt. Bleiben alle zehn,
#: ist es kein Zufall.
HOW_MANY = 10

#: Wie oft die Ereignisschlange geleert wird, bevor gezählt wird.
#:
#: Fünf und nicht eine: Ein ``finished`` löst ``hold_until_done`` aus, das
#: seinerseits einreiht. Eine einzelne Runde erwischt die erste Stufe und
#: lässt die zweite stehen.
EVENT_ROUNDS = 5


def _builders() -> list[tuple[str, Callable[[], QWidget]]]:
    """Die Widget-Klassen, die auf ihre Freigabe geprüft werden.

    Als Funktionen und nicht als Klassen: Die Einfuhr gehört in den Test und
    nicht in den Kopf der Datei, sonst braucht diese Datei Qt schon beim
    Einsammeln der Tests.
    """
    from app.core import install, tools, updates
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.types import Parameter, ParamSpec
    from app.ui.analysis_bar import AnalysisBar, LayerBar
    from app.ui.catalog import PartCatalog
    from app.ui.chat import ChatPanel
    from app.ui.command_palette import CommandPalette
    from app.ui.dialogs import AskDialog, CalibrationDialog, KeyDialog, ParameterDialog
    from app.ui.explode_bar import ExplodeBar
    from app.ui.filament_picker import NewFilamentDialog
    from app.ui.first_run import FirstRunDialog, ToolRow
    from app.ui.install_dialog import InstallDialog, _Row
    from app.ui.main_window import MainWindow
    from app.ui.op_dialog import (
        ArmatureField,
        ArmatureSummary,
        ImageSourceField,
        OperationDialog,
        SketchUseDialog,
        ValueField,
    )
    from app.ui.overlay import OverlayHost
    from app.ui.panels import HistoryPanel, ObjectTree, ParameterPanel, ReportPanel
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.section_bar import MeasureBar, SectionBar
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.settings_dialog import SettingsDialog
    from app.ui.shortcuts_window import ShortcutsWindow
    from app.ui.sketch_editor import ExpressionDialog, PointDialog, SketchPanel
    from app.ui.tool_strip import ToolStrip
    from app.ui.tour import StepLabel, TourPanel
    from app.ui.update_dialog import UpdateDialog
    from app.ui.variants_dialog import VariantsDialog
    from app.ui.viewport import HoldToCompare, ViewBar, Viewport

    class ComparisonHost(QWidget):
        """Der schmale Vertrag, den ``HoldToCompare`` vom Viewport braucht."""

        def hold_before(self, held: bool) -> None:
            """Für die Lebensdauerprüfung muss die Vorschau nichts zeichnen."""

    # Die Ops müssen geladen sein, sonst hat das Register nichts, womit ein
    # Operationsdialog gebaut werden könnte.
    load_operations()
    spec = REGISTRY.all()[0]
    release = updates.Release(version="9.9.9", url="https://example.invalid/")

    def report_with_offer() -> QWidget:
        """Ein Prüfbericht mit gewähltem Befund und Handlungsknopf, im Wirt.

        Der nackte ``ReportPanel``-Bauer darunter sah den Ring nie: Erst die
        Knopfzeile unter der Liste verband ein Lambda, das die gebundenen
        Handler des Fensters fing — zehn von zehn Wirten mit gewähltem Befund
        überlebten ihr Loslassen (30.08.2026). Der Wirt spielt das Fenster:
        ``handlers_of`` sucht ``error_handlers`` die Eltern hinauf.
        """
        from app.core.errors import AppError
        from app.core.scene import EvaluationResult
        from app.core.types import Finding, Report, Scene

        class Host(QWidget):
            def error_handlers(self) -> dict[str, Callable[[AppError], None]]:
                return {"place_on_bed": self._handle}

            def _handle(self, error: AppError) -> None:
                """Nie gerufen — es zählt, dass ein Knopf auf ihn zeigt."""

        host = Host()
        panel = ReportPanel(host)
        panel.show_result(
            EvaluationResult(
                scene=Scene(
                    report=Report(
                        findings=(
                            Finding(
                                code="arrange.below_bed",
                                severity="info",
                                message="Ein Objekt liegt unter dem Druckbett",
                                object_id="obj_1",
                            ),
                        )
                    )
                )
            )
        )
        panel.list.setCurrentRow(0)
        return host

    return [
        ("Viewport", Viewport),
        ("SketchPanel", SketchPanel),
        # **Die drei kamen dazu, weil die Frage nach der Vollständigkeit
        # gestellt wurde.** Der Test war grün und deckte 14 von 70
        # QWidget-Klassen ab; von den 34 der übrigen, die sich ohne Argumente
        # bauen lassen, hielten am 23.08.2026 sechs. Drei davon stehen oben im
        # Kommentar und sind erklärt — diese drei nicht, und bei allen dreien
        # nannte ``gc.get_referrers`` dieselbe Ursache: die Zelle eines
        # Abschlusses, ein Lambda aus einer Schleife.
        ("ViewBar", ViewBar),
        ("ChatPanel", ChatPanel),
        ("SketchUseDialog", SketchUseDialog),
        # Das Fenster wiegt am schwersten: Die Suite baut über siebenhundert
        # davon nacheinander auf, und jedes ließ rund 7 MB stehen.
        ("MainWindow", lambda: MainWindow(Session(), UiSettings())),
        ("AnalysisBar", AnalysisBar),
        ("LayerBar", LayerBar),
        ("SectionBar", SectionBar),
        ("MeasureBar", MeasureBar),
        ("ExplodeBar", ExplodeBar),
        ("ToolStrip", ToolStrip),
        ("CommandPalette", CommandPalette),
        ("ObjectTree", ObjectTree),
        ("ParameterPanel", ParameterPanel),
        ("HistoryPanel", HistoryPanel),
        ("ReportPanel", ReportPanel),
        ("ReportPanelWithOffer", report_with_offer),
        # **Die zweiundzwanzig, die Argumente brauchen.** Sie fehlten hier,
        # und zwar nicht zufällig: Was sich ohne Argumente bauen lässt, ist
        # meist ein Bedienelement; was welche braucht, steht mitten in einem
        # Arbeitsablauf — also gerade das, was ein Kunde am häufigsten sieht.
        # Von ihnen hielten am 23.08.2026 vier ihr Loslassen fest, alle vier
        # über die Zelle eines Abschlusses.
        ("AskDialog", lambda: AskDialog("Frage?", ["a", "b"])),
        ("CalibrationDialog", lambda: CalibrationDialog("pla")),
        ("ParameterDialog", lambda: ParameterDialog({"w": Parameter(name="w", value=10.0)})),
        ("KeyDialog", KeyDialog),
        ("FirstRunDialog", lambda: FirstRunDialog(UiSettings())),
        ("ToolRow", lambda: ToolRow(tools.ToolState(tools.TOOLS[0], None))),
        ("InstallDialog", InstallDialog),
        # Der Dialog-Bauer darüber sah die Ringe seiner Zeilen nicht: Eine
        # ``_Row``, deren Knopf-Lambda ``self`` fängt, hält sich selbst — der
        # Dialog stirbt trotzdem, gezählt wird er, und die Zombie-Zeilen
        # blieben unsichtbar. Deshalb die Zeile selbst, und der Filament-Dialog
        # mit demselben Muster daneben.
        ("InstallRow", lambda: _Row(install.REQUIREMENTS[0])),
        ("NewFilamentDialog", NewFilamentDialog),
        ("PartCatalog", PartCatalog),
        ("ArmatureField", lambda: ArmatureField(["a", "b"])),
        ("ArmatureSummary", lambda: ArmatureSummary("t", ["a"])),
        ("ImageSourceField", lambda: ImageSourceField({}, None)),
        ("OperationDialog", lambda: OperationDialog(spec, [])),
        ("ValueField", lambda: ValueField(ParamSpec(name="w", kind="number", title="Breite"))),
        ("OverlayHost", lambda: OverlayHost(QWidget())),
        ("PrintSettingsDialog", lambda: PrintSettingsDialog(Session(), UiSettings())),
        ("SettingsDialog", lambda: SettingsDialog(UiSettings())),
        ("ShortcutsWindow", lambda: ShortcutsWindow(None)),
        ("ExpressionDialog", lambda: ExpressionDialog({"w": 10.0})),
        ("PointDialog", lambda: PointDialog((0.0, 0.0), ("X", "Y"))),
        ("StepLabel", lambda: StepLabel("Schritt")),
        ("TourPanel", lambda: TourPanel(Session())),
        ("UpdateDialog", lambda: UpdateDialog(release)),
        ("VariantsDialog", lambda: VariantsDialog(Session())),
        # Der echte Viewport steht oben bereits selbst in der Prüfung. Ihn hier
        # als bloßen Elternträger ein zweites Mal je Runde zu bauen, erzeugt
        # weitere Viewports und misst deren Sammelabbau statt des
        # Referenzrings von ``HoldToCompare``. Der schmale Wirt erhält genau die
        # entscheidende Bauart: Elternbesitz plus Rückverweis vom Kind.
        (
            "HoldToCompare",
            lambda: HoldToCompare(cast(Viewport, ComparisonHost())),
        ),
    ]


@pytest.mark.parametrize("name,build", _builders())
def test_a_released_widget_is_actually_released(
    name: str,
    build: Callable[[], QWidget],
    qt_app: QApplication,
    unpinned_windows: None,
) -> None:
    """Zehn bauen, zehn loslassen, zählen, wie viele bleiben.

    Bleibt auch nur eines, hält es etwas fest, das es nicht sollte — und der
    Weg dorthin ist immer derselbe: ``gc.get_referrers`` auf das überlebende
    Objekt, und unter den Haltern die Zellen ansehen. So ist der erste Ring
    gefunden worden (ein Lambda am eigenen Schichtzeitgeber des Viewports),
    und so wird der nächste gefunden.
    """
    from PySide6.QtWidgets import QApplication

    from app.ui import leash

    watchers = []
    for _ in range(HOW_MANY):
        widget = build()
        # **Derselbe Weg, den ein Fenster beim Schließen geht.** Wer eine
        # ``WorkerLeash`` hält, hat seit dem 23.08.2026 ein ``release()``; ohne
        # es bleibt ein Arbeiter in ``leash._alive``, hält über sein
        # ``finished``-Lambda die Leine und damit sein Widget. Das sähe hier
        # wie ein Ring aus und wäre keiner.
        # **Die ungebundene Funktion von der Klasse, nicht die gebundene vom
        # Objekt.** ``getattr(widget, "release")`` erzeugt eine gebundene
        # Methode, und die hält ihr ``__self__`` — nach der Schleife stand in
        # dieser Variablen das zehnte Fenster, und der Test meldete „1 von 10
        # überlebten", dreimal von dreimal. Er hielt es selbst fest.
        release = getattr(type(widget), "release", None)
        if callable(release):
            release(widget)
        watchers.append(weakref.ref(widget))
        del widget

    # Und der Schritt, der lange gefehlt hat: ``release`` wartet, aber
    # abgeräumt wird erst, wenn das ``finished``-Signal ankommt.
    leash.wait_for_all()
    application = QApplication.instance()
    if application is not None:
        for _ in range(EVENT_ROUNDS):
            application.processEvents()
    gc.collect()

    alive = [watch for watch in watchers if watch() is not None]
    assert not alive, f"{len(alive)} von {HOW_MANY} {name} überlebten ihr Loslassen"


def test_everything_that_holds_a_leash_can_be_told_to_let_go() -> None:
    """Wer Arbeiter hält, hat einen ``release()`` — und zwar unter diesem Namen.

    **Fünf Namen für dieselbe Sache, gefunden am 23.08.2026 beim Aufräumen des
    Abbau-Absturzes:**

        release            MainWindow
        wait_for_workers   MainWindow, PrintSettingsDialog, GenerateDialog
        wait_for_survey    FirstRunDialog, InstallDialog
        wait_for_look      KeyDialog
        wait_for_setup     ComfySetupDialog

    Drei weitere Klassen hielten eine ``WorkerLeash`` und hatten gar nichts:
    ``SupportDialog``, ``UpdateDialog``, ``VariantsDialog``. Sie waren nur
    deshalb unauffällig, weil kein Test sie baute, ohne sie zu schließen —
    genau wie ``FirstRunDialog``, bis jemand den Sprachwähler prüfen wollte.
    Dann stirbt der Prozess beim Abbau, und die Ursache steht drei Dateien
    weiter.

    Wer eine Fixture darauf baut, sammelt Namen: Sie kannte zwei von fünf, dann
    drei, dann vier. **Diese Prüfung sammelt keine** — sie fragt am Quelltext,
    wer eine Leine anlegt, und verlangt von jedem dasselbe Wort.

    Die fachlichen Namen bleiben daneben stehen, und das ist kein Zugeständnis:
    ``wait_for_survey`` gibt einen Wahrheitswert zurück und wird vom
    Produktivcode gerufen (``FirstRunDialog.reject``), ``release`` räumt auf und
    gibt nichts zurück. Zwei Sachen, zwei Namen — nur soll die eine überall
    gleich heißen.
    """
    import ast
    from pathlib import Path

    holders: dict[str, Path] = {}
    for path in sorted(Path("app/ui").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            source = ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
            if "WorkerLeash(" in source:
                holders[node.name] = path

    assert len(holders) >= 10, (
        f"nur {len(holders)} Leinen-Halter gefunden — sucht das noch richtig?"
    )

    without = []
    for name, path in sorted(holders.items()):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == name:
                methods = {m.name for m in node.body if isinstance(m, ast.FunctionDef)}
                if "release" not in methods:
                    without.append(f"{name} ({path.name})")

    assert not without, "hält Arbeiter, kennt aber kein release(): " + ", ".join(without)


# --- Filter, die den Tod ihres Überwachten überleben ---------------------------


class _NotesWhoStopsWatching(QWidget):
    """Ein Widget, das mitschreibt, wer aufhört, es zu beobachten.

    Qt gibt seine Filterliste nicht heraus — man kann ein Widget nicht fragen,
    wer es beobachtet. Was man fragen kann, ist das Gegenteil: Wer bestellt ab?
    """

    def __init__(self) -> None:
        super().__init__()
        self.dropped: list[object] = []

    def removeEventFilter(self, obj: object) -> None:  # noqa: N802 — Qt gibt den Namen
        self.dropped.append(obj)
        super().removeEventFilter(obj)  # type: ignore[arg-type]


def _watchers() -> list[tuple[str, Callable[[], object]]]:
    """Die Filter, die auf einem **sterblichen** Widget sitzen.

    Nicht dabei sind die vier, die auf der ``QCoreApplication`` installieren
    (``app.py``, ``shortcut_schemes.py``, ``survey.py:194``,
    ``viewport.py:5720``): Die Anwendung stirbt zuletzt, ein ``Destroy`` von
    ihr gibt es zu Lebzeiten des Filters nicht.
    """
    from app.core.types import ParamSpec
    from app.ui.catalog import PartCatalog
    from app.ui.chat import ChatPanel
    from app.ui.op_dialog import ValueField
    from app.ui.overlay import OverlayHost
    from app.ui.sketch_editor import SketchPanel
    from app.ui.survey import SurveyNotice
    from app.ui.viewport import Viewport

    return [
        ("PartCatalog", PartCatalog),
        ("ChatPanel", ChatPanel),
        ("ValueField", lambda: ValueField(ParamSpec(name="w", kind="number", title="Breite"))),
        ("SketchPanel", SketchPanel),
        ("SurveyNotice", SurveyNotice),
        ("Viewport", Viewport),
        ("OverlayHost", lambda: OverlayHost(QWidget())),
    ]


@pytest.mark.parametrize("name,build", _watchers())
def test_a_filter_stops_watching_what_dies(
    name: str,
    build: Callable[[], object],
    qt_app: QApplication,
    unpinned_windows: None,
) -> None:
    """Ein ``Destroy`` am Überwachten muss den Filter abbestellen.

    **Die Richtung ist der ganze Punkt** (siehe
    :func:`app.ui.leash.stop_watching_the_dying`): Stirbt das *Filterobjekt*,
    räumt Qt selbst auf. Stirbt das *überwachte* Objekt, läuft der Filter des
    Überlebenden in dessen Abbau hinein und fragt halb abgeräumte Widgets nach
    ihrer Geometrie.

    **Was dieser Test nicht behauptet.** Bei den Stellen, an denen Filter und
    Überwachter dieselbe Lebensdauer haben — ein Elternteil, der sein eigenes
    Kind beobachtet, wie in ``chat.py`` oder ``op_dialog.py`` —, sterben beide
    zusammen, und dann rettet das Abbestellen nichts. Es trägt dort für den
    anderen Fall: ein Kind, das **einzeln** geht, weil ein Layout wechselt oder
    jemand ``deleteLater`` ruft.

    **Wie oft der Zweig wirklich läuft, ist gemessen** — in vier
    Fensterdateien mit vier Millionen Filteraufrufen schlägt er 119 Mal an, und
    jedes Mal in ``OverlayHost``. Die Tabelle steht bei
    :func:`app.ui.leash.stop_watching_the_dying`. Dieser Test hält die sieben
    Stellen deshalb nicht für behoben, sondern für vorgesorgt: Er sichert, dass
    der Griff *wirkt*, wenn der Fall eintritt — nicht, dass er eintritt.
    """
    from PySide6.QtCore import QEvent

    watcher = build()
    dying = _NotesWhoStopsWatching()
    handled = watcher.eventFilter(dying, QEvent(QEvent.Type.Destroy))  # type: ignore[attr-defined]

    assert dying.dropped == [watcher], (
        f"{name} bestellt beim Destroy des Überwachten nicht ab — abbestellt wurde: {dying.dropped}"
    )
    assert handled is False, (
        f"{name} verschluckt das Destroy (gab {handled!r}) — es muss weiterlaufen, "
        "sonst sieht der Rest der Kette den Abbau nicht"
    )


def test_every_filter_on_a_mortal_widget_unwatches_it() -> None:
    """Wer neu installiert, bestellt auch ab — oder installiert auf der Anwendung.

    Der Wächter zu den sieben oben: Der parametrisierte Test kennt seine
    Klassen und sieht eine achte nicht. Dieser hier liest den Quelltext und
    schlägt an, sobald ``installEventFilter`` an einer Stelle steht, deren
    Filter nicht abbestellt.

    **Gefragt wird nach dem Filter, nicht nach der Datei** — und das ist der
    Unterschied, an dem die erste Fassung dieses Tests falsch rot wurde. Sie
    verlangte den Ruf in der Datei, in der ``installEventFilter`` steht; bei
    ``main_window.py:1552`` steht dort aber ``self.sketch_bar.installEventFilter(
    self.overlay)``, und der Filter ist ein ``OverlayHost`` aus einer anderen
    Datei. Die Stelle war gedeckt, der Wächter zählte das Falsche.

    Deshalb zwei Gruppen:

    * ``x.installEventFilter(self)`` — der Filter ist die Klasse dieser Datei,
      also muss der Ruf hier stehen. Streng geprüft.
    * ``x.installEventFilter(<etwas anderes>)`` — der Filter lebt woanders und
      ist statisch nicht aufzulösen. Getragen wird die Stelle vom
      parametrisierten Test darüber; hier wird nur die Zahl festgehalten,
      damit eine neue Stelle dieser Art auffällt.

    **Die Sollprobe steht in beiden Zahlen**, und sie hat einen Grund: Ein
    Muster, das nichts findet, sieht aus wie eines, das nichts zu beanstanden
    hat.
    """
    import ast
    from pathlib import Path

    #: Was auf der ``QCoreApplication`` installiert, braucht kein Abbestellen —
    #: sie überlebt jeden Filter. Erkannt am Namen des Empfängers, nicht an
    #: einer Liste von Dateien: Eine neue Stelle dieser Art soll durchgehen.
    immortal = ("application", "app", "instance")

    own: list[str] = []
    foreign: list[str] = []
    for path in sorted(Path("app/ui").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "installEventFilter" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "installEventFilter" or not node.args:
                continue
            root = node.func.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in immortal:
                continue
            where = f"{path.name}:{node.lineno}"
            argument = node.args[0]
            if isinstance(argument, ast.Name) and argument.id == "self":
                own.append(where)
            else:
                foreign.append(where)

    assert len(own) >= 7, (
        f"nur {len(own)} Filter fanden sich, die sich selbst auf ein sterbliches "
        f"Widget setzen ({own}) — sucht das noch richtig? Am 30.08.2026 waren es sieben"
    )
    assert len(foreign) >= 1, (
        f"kein Filter mehr, der auf einem fremden Objekt sitzt ({foreign}) — "
        "main_window.py:1552 war einer; wenn er weg ist, gehört diese Zahl nachgezogen"
    )

    without = sorted(
        {
            place.split(":")[0]
            for place in own
            if "stop_watching_the_dying"
            not in (Path("app/ui") / place.split(":")[0]).read_text(encoding="utf-8")
        }
    )
    assert not without, (
        "setzt sich als Filter auf ein sterbliches Widget, bestellt aber nie ab: "
        + ", ".join(without)
        + " — siehe app/ui/leash.py:stop_watching_the_dying"
    )


# --- Dialoge, die das Fenster als sein Kind baut und verdrahtet -----------------


def _openers() -> list[tuple[str, str, Callable[[object], None]]]:
    """Fensterwege, die einen Dialog als eigenes Kind bauen und verdrahten.

    Der parametrisierte Test oben baut jeden Dialog **für sich** und sieht
    damit nur dessen eigene Ringe. Was er nicht sieht, ist der Ring, der beim
    Verdrahten entsteht: Sechs Lambdas in ``_make_catalog`` und zwei in
    ``_generate`` fangen das Fenster, der Dialog ist sein Kind, und ohne
    Freigeben leben beide bis zum Prozessende.
    """

    def open_catalogue(window: object) -> None:
        window._open_catalog()  # type: ignore[attr-defined]

    def open_generator(window: object) -> None:
        window._generate(None)  # type: ignore[attr-defined]

    return [
        ("Bausteinkatalog", "app.ui.catalog.PartCatalog", open_catalogue),
        ("Erzeugen-Dialog", "app.ui.generate_dialog.GenerateDialog", open_generator),
    ]


@pytest.mark.parametrize("name,dialog_path,open_it", _openers())
def test_a_window_that_opened_a_dialog_still_lets_go(
    name: str,
    dialog_path: str,
    open_it: Callable[[object], None],
    monkeypatch: pytest.MonkeyPatch,
    qt_app: QApplication,
    unpinned_windows: None,
) -> None:
    """Öffnen, abbrechen, loslassen — und das Fenster ist weg.

    ``exec()`` wird ersetzt und nicht wirklich gefahren: Es hielte den Lauf an,
    bis jemand klickt. Zurückgegeben wird *abgebrochen* — der Weg dessen, der
    das Fenster wieder schließt, und genau der, auf dem niemand aufräumte.
    """
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication, QDialog

    from app.ui import leash
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    monkeypatch.setattr(
        dialog_path + ".exec", lambda self: QDialog.DialogCode.Rejected, raising=True
    )

    watchers = []
    for _ in range(HOW_MANY):
        window = MainWindow(Session(), UiSettings())
        open_it(window)
        window.release()
        watchers.append(weakref.ref(window))
        del window

    leash.wait_for_all()
    application = QApplication.instance()
    if application is not None:
        for _ in range(EVENT_ROUNDS):
            application.processEvents()
        # **``processEvents`` räumt kein ``deleteLater`` ab.** Eine
        # aufgeschobene Löschung wird erst zugestellt, wenn die Ereignisschleife
        # endet, die sie eingereiht hat — im Betrieb ist das die des Fensters,
        # hier gibt es keine. Ohne diese Zeile misst der Test den Fix nicht.
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()

    alive = [watch for watch in watchers if watch() is not None]
    assert not alive, (
        f"{len(alive)} von {HOW_MANY} Fenstern überlebten, nachdem sie den "
        f"{name} geöffnet hatten — der Dialog wird nicht freigegeben"
    )
