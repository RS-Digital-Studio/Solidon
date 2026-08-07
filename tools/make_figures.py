"""Die Bildschirmfotos für das Handbuch aufnehmen (Bauplan §37.2).

Fünf Abbildungen des Handbuchs zeigen die Oberfläche selbst — Startbildschirm,
Hauptfenster, Operationsdialog, Prüfbericht, Bausteinkatalog. Sie werden hier
aufgenommen und nicht von Hand gemacht: ein Bildschirmfoto, das jemand vor drei
Versionen gezogen hat, zeigt drei Versionen alte Knöpfe, und niemand merkt es.

    .venv\\Scripts\\python.exe tools/make_figures.py

Je Sprache ein Durchgang, denn in einem Fenster steht Text. Die Dateien landen
unter ``app/images/manual/<sprache>/``.

**Zwei Dinge, an denen es sonst scheitert.**

Erstens läuft das hier *nicht* offscreen. ``QT_QPA_PLATFORM=offscreen`` bringt
auf dieser Maschine null Schriftfamilien mit, und jedes Bild wäre eine Reihe
leerer Kästchen. Gebraucht wird die echte Plattform — angezeigt wird trotzdem
nichts, dafür sorgt ``WA_DontShowOnScreen``.

Zweitens ist das kein Testlauf. Die Suite prüft, ob die Dateien *da* sind und
ob jede Abbildung ihren Alt-Text hat; sie nimmt keine auf. Ein Test, der eine
Oberfläche fotografiert, prüft am Ende die Schriftglättung des Bauservers.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

# Vor allem, was Qt anfasst: die echte Plattform, siehe Modulkopf.
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Die Eingabeaufforderung unter Windows kommt sonst schon am ersten Umlaut ins
# Straucheln, und ein Werkzeug, das an seiner eigenen Ausgabe abstürzt, ist ein
# schlechtes Werkzeug.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from app.core import figures
from app.core.bootstrap import load_operations
from app.core.registry.registry import REGISTRY
from app.core.types import Finding
from app.i18n import SUPPORTED_LANGUAGES, install_catalog, set_language
from app.i18n.catalog import read_catalog

#: Welches Beispielprojekt im Hauptfenster steht.
#:
#: Das Gehäuse und nicht die Halterung aus Weg 1. Beide zeigen dasselbe
#: Fenster, aber nicht dasselbe Programm: die Halterung ist eine Platte mit
#: fünf gebohrten Löchern, und der Objektbaum, die Parameterliste und der
#: Verlauf stehen daneben fast leer. Das Gehäuse trägt drei benannte Maße,
#: vier Bausteine — Mutternfalle, Heat-Set-Buchse, Schraubenloch,
#: Kabeldurchführung — und ein Prüfstück daneben. Wer das Bild ansieht,
#: soll sehen, was die Anwendung kann, und nicht, dass sie ein Loch bohren
#: kann.
#:
#: Die Befunde im Prüfbericht sind ohnehin gestellt (:func:`sample_findings`),
#: das Projekt muss also keine mitbringen.
EXAMPLE = "dose-mit-deckel.p3d"

#: Wie groß die Fenster für die Aufnahme sind. Breiter als nötig wäre auf einer
#: Handbuchseite nur kleiner zu sehen.
WINDOW = (1180, 760)
DIALOG = (520, 460)
REPORT = (460, 300)


def settle(app: QApplication, rounds: int = 12) -> None:
    """Der Oberfläche Zeit geben, fertig zu werden, bevor abgedrückt wird."""
    for _round in range(rounds):
        app.processEvents()


def await_result(app: QApplication, session: object, seconds: float = 30.0) -> bool:
    """Warten, bis die Auswertung durch ist.

    Sie läuft in einem Arbeitsfaden (§15.6), also genügt kein Stapel
    ``processEvents``: ohne das Warten wird das Hauptfenster fotografiert,
    während es noch den Startbildschirm zeigt — genau das ist beim ersten
    Versuch passiert.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if getattr(session, "last_result", None) is not None:
            settle(app)
            return True
        time.sleep(0.05)
    return False


def shoot(widget: QWidget, key: str, language: str, *, from_screen: bool = False) -> None:
    """Ein Widget aufnehmen und unter dem Schlüssel seiner Abbildung ablegen.

    ``from_screen`` greift den Bildschirmausschnitt statt das Widget. Für das
    Hauptfenster ist das nötig: ``QWidget.grab`` malt das Widget über den
    Qt-Painter nach, und der weiß nichts von dem, was OpenGL in den Viewport
    gezeichnet hat — die Bildmitte bliebe schwarz.
    """
    figure = figures.find(key)
    if figure is None:
        raise SystemExit(f"Keine Abbildung namens {key!r} im Katalog")
    target = figure.path(language)
    target.parent.mkdir(parents=True, exist_ok=True)
    if from_screen:
        screen = widget.screen() or QApplication.primaryScreen()
        shot = screen.grabWindow(widget.winId())
    else:
        shot = widget.grab()
    shot.save(str(target))
    print(f"  {key:14s} → {target.relative_to(Path.cwd()) if target.is_absolute() else target}")


def release_viewport(window: Any) -> None:
    """Den OpenGL-Kontext des Hauptfensters freigeben, bevor das nächste kommt.

    ``close()`` allein tut das nicht: das ``QtInteractor`` bleibt am Fenster
    hängen, und mit ihm sein Renderfenster. **Die Anwendung merkt das nie** —
    sie baut ein Hauptfenster und dann keins mehr. Dieses Werkzeug baut je
    Sprache eines, und das zweite bekommt einen Kontext, der dem ersten noch
    gehört.

    Sichtbar wurde es am Orientierungswürfel: im ersten Durchgang saß er, wo er
    hingehört, im zweiten lag er als handtellergroßes Achsenkreuz quer über dem
    Modell. Das englische Handbuchbild zeigte statt des Gehäuses ein X, ein Y
    und ein Z. Ein Bild mit einem Fehler, den die Anwendung nicht hat, ist
    schlimmer als gar keines — ihm glaubt man.
    """
    plotter = getattr(getattr(window, "viewport", None), "plotter", None)
    if plotter is None:
        return
    try:
        plotter.close()
    except Exception as problem:  # pragma: no cover - hängt am Treiber
        print(f"  (Viewport ließ sich nicht schließen: {problem})")
    window.viewport.plotter = None


def prepared(widget: QWidget, size: tuple[int, int], *, hidden: bool = True) -> QWidget:
    """Ein Fenster aufbauen — normalerweise, ohne es jemandem zu zeigen.

    ``hidden=False`` braucht das Hauptfenster: sein Viewport rendert über
    OpenGL, und OpenGL zeichnet nichts in ein Fenster, das nie auf dem
    Bildschirm war. Ohne das ist die Bildmitte auf dem Bild schwarz — also
    ausgerechnet das Modell, um das es geht.
    """
    if hidden:
        widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    widget.resize(*size)
    widget.show()
    return widget


#: Die Texte der gestellten Befunde, je Sprache ausgeschrieben.
#:
#: **Nicht über ``_()``.** Der Textsammler liest ``app/``, und was hier steht,
#: käme deshalb nie in den Katalog: ``translate()`` fiele auf die Message-ID
#: zurück, also auf Deutsch. Genau das war im englischen Handbuch zu sehen —
#: ein Bildschirmfoto des Prüfberichts mit deutschen Befunden mitten im
#: englischen Text.
SAMPLE_FINDINGS: dict[str, tuple[str, str, str, str]] = {
    "de": (
        "Das Modell ist an drei Stellen offen.",
        "14 Dreiecke zeigen nach innen.",
        "Eine Wand ist dünner als zwei Extrusionsbahnen.",
        "Die Einheit stand nicht in der Datei; angenommen wurden Millimeter.",
    ),
    "en": (
        "The model is open in three places.",
        "14 triangles face inwards.",
        "A wall is thinner than two extrusion paths.",
        "The file did not state a unit; millimetres were assumed.",
    ),
}

#: Der Name des Körpers im Operationsdialog, aus demselben Grund ausgeschrieben.
SAMPLE_OBJECT = {"de": "Halterung", "en": "Bracket"}


def sample_findings(language: str) -> list[Finding]:
    """Befunde, wie sie ein eingelesenes Fremdmodell erzeugt.

    Gestellt und nicht gerechnet: der Prüfbericht soll auf dem Bild die Sorten
    zeigen, die es gibt — Hinweis, Warnung, Fehler —, und ein Beispielprojekt,
    das zufällig gerade alle drei hat, gibt es nicht.
    """
    open_body, flipped, thin, unit = SAMPLE_FINDINGS.get(language, SAMPLE_FINDINGS["de"])
    return [
        Finding(
            code="ingest.not_watertight",
            severity="warning",
            message=open_body,
            values={"holes": 3},
        ),
        Finding(
            code="ingest.flipped_faces",
            severity="warning",
            message=flipped,
            values={"faces": 14},
        ),
        Finding(code="slice.thin_wall", severity="info", message=thin),
        Finding(code="ingest.unit_guessed", severity="info", message=unit),
    ]


def take_all(app: QApplication, language: str) -> None:
    """Alle fünf Aufnahmen einer Sprache."""
    from app.core import examples
    from app.ui.catalog import PartCatalog
    from app.ui.main_window import MainWindow
    from app.ui.op_dialog import OperationDialog
    from app.ui.panels import ReportPanel
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.start_screen import StartScreen

    print(f"{language}:")

    start = prepared(StartScreen(), WINDOW)
    settle(app)
    shoot(start, "start-screen", language)
    start.close()

    session = Session()
    window = prepared(MainWindow(session, UiSettings()), WINDOW, hidden=False)
    project = examples.directory() / EXAMPLE
    if not project.is_file():
        raise SystemExit(f"Beispielprojekt fehlt: {project}")
    session.open_project(project)
    # Nicht über ``open_path``: das schriebe das Beispiel in die Zuletzt-Liste
    # des echten Benutzerprofils. Die Ansichtsumschaltung, die dort mit
    # drinsteckt, wird deshalb hier von Hand nachgeholt — ohne sie fotografiert
    # das Werkzeug den Startbildschirm, was es beim ersten Versuch tat.
    window._show_start_screen(False)
    if not await_result(app, session):
        raise SystemExit("Die Auswertung wurde nicht fertig — kein Bild vom Hauptfenster")
    window.report.add_findings(sample_findings(language))
    window.raise_()
    window.activateWindow()
    settle(app, 60)
    shoot(window, "main-window", language, from_screen=True)
    window.close()
    release_viewport(window)

    # Der Prüfbericht als eigenes Fenster: im Hauptfenster steckt er in einem
    # Reiter und ist genau so hoch wie der Reiter, was ein Bild von zwölf Pixeln
    # Höhe ergibt.
    report = prepared(ReportPanel(), REPORT)
    report.add_findings(sample_findings(language))
    settle(app)
    shoot(report, "report", language)
    report.close()

    dialog = prepared(
        OperationDialog(
            REGISTRY.get("drill_hole"),
            [SAMPLE_OBJECT.get(language, SAMPLE_OBJECT["de"])],
            values={"diameter": 4.2, "x": 20.0, "y": 0.0},
        ),
        DIALOG,
    )
    settle(app)
    shoot(dialog, "op-dialog", language)
    dialog.close()

    catalog = prepared(PartCatalog(), WINDOW)
    settle(app, 30)
    shoot(catalog, "catalog", language)
    catalog.close()
    window.close()


def main() -> int:
    from app.ui.app import install_qt_translations
    from app.ui.theme import apply_theme

    load_operations()
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    # **Mit dem Thema, nicht nur mit der Palette.** Ohne diese Zeile nahmen
    # die Bilder die Anwendung ohne ihr Stylesheet auf: Kacheln ohne Rahmen,
    # Knöpfe ohne Abstufung, der Titel in Fließtextgröße. Ein Handbuch, das
    # etwas anderes zeigt als die Anwendung, ist an der Stelle falsch, an der
    # man ihm am ehesten glaubt.
    apply_theme(app, "dark")
    qt_translator = None
    for language in SUPPORTED_LANGUAGES:
        install_catalog(language, read_catalog(language))
        set_language(language)
        # Auch Qt selbst spricht die Sprache der Aufnahme — sonst zeigen die
        # Bilder „Cancel" auf Dialogen, die in der Anwendung (über
        # build_application) längst „Abbrechen" sagen.
        if qt_translator is not None:
            app.removeTranslator(qt_translator)
        qt_translator = install_qt_translations(app, language)
        take_all(app, language)
    print("\nFertig. Die Suite prüft nur, dass die Dateien da sind — siehe Modulkopf.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
