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
from dataclasses import replace
from pathlib import Path
from typing import Any

# Vor allem, was Qt anfasst: die echte Plattform, siehe Modulkopf.
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
from app.core.scene.project import new_project
from app.core.types import Feature, Finding, Parameter
from app.i18n import install_catalog, set_language, tr
from app.i18n.catalog import available_languages, read_catalog

#: Welches Beispielprojekt im Hauptfenster steht.
#:
#: Die Dose mit Deckel und nicht die Halterung aus Weg 1. Beide zeigen dasselbe
#: Fenster, aber nicht dasselbe Programm: die Halterung ist eine Platte mit
#: fünf gebohrten Löchern, und der Objektbaum, die Parameterliste und der
#: Verlauf stehen daneben fast leer. Die Dose trägt vier benannte Maße, ist
#: ausgehöhlt, hat Kabeldurchführung und Einpressbuchse in der Wand, eine
#: Beschriftung und einen Deckel, der aus der Öffnung geschnitten ist. Wer das
#: Bild ansieht, soll sehen, was die Anwendung kann, und nicht, dass sie ein
#: Loch bohren kann.
#:
#: Die Befunde im Prüfbericht sind ohnehin gestellt (:func:`sample_findings`),
#: das Projekt muss also keine mitbringen.
EXAMPLE = "dose-mit-deckel.p3d"

#: Auf welchem Bildschirm aufgenommen wird — Index in ``QApplication.screens()``.
#:
#: Nicht der primäre, und das hat einen Grund: Der ist hier ein 21:9-Schirm mit
#: 3413 Bildpunkten Breite, und ein Fenster darauf ergibt ein Bild im Verhältnis
#: 2,45:1. Auf eine Handbuchseite gelegt wird daraus ein flacher Streifen, auf
#: dem die Schrift nicht mehr lesbar ist. Der zweite Schirm ist 2560x1440 und
#: liefert das Verhältnis, in dem Bildschirmfotos üblich sind.
#:
#: Gibt es ihn nicht, wird der erste genommen — ein Werkzeug, das an einem
#: abgezogenen Monitor scheitert, taugt nichts. Überschreiben mit ``--schirm N``.
SCREEN_INDEX = 1

#: Wie groß die *Fenster* für die Aufnahme sind: so groß wie das Fenster beim
#: ersten Start aufgeht.
#:
#: Und das ist bildschirmfüllend — ``app.py`` ruft ohne gespeicherte Geometrie
#: ``showMaximized()``. Ein Handbuch, das die Anwendung in einem 1180 Punkte
#: breiten Kasten zeigt, zeigt eine Anwendung, die so bei niemandem steht: Der
#: Viewport war darin ein Drittel des Bildes, und die drei Leisten daneben
#: sahen aus, als nähmen sie den ganzen Platz. Kein Vollbild — das versteckt
#: Menü- und Statusleiste, und beide gehören auf das Bild.
#:
#: ``None`` heißt „nimm die Arbeitsfläche des Zielschirms"; :func:`work_area`
#: löst es auf, sobald es eine ``QApplication`` gibt.
WINDOW: tuple[int, int] | None = None

#: Ein Dialog ist kein Fenster: Er geht so groß auf, wie sein Inhalt ist, und
#: bildschirmfüllend gibt es ihn nirgends. Die Höhe kommt ohnehin aus dem
#: Inhalt (``fit_height``), die Breite bleibt gesetzt, damit alle Sprachen
#: dasselbe Maß haben.
DIALOG = (520, 460)

#: Der Prüfbericht ist ein Ausschnitt der rechten Leiste und keine Ansicht für
#: sich — auf Bildschirmbreite gezogen stünden vier Befunde in einer Fläche,
#: die zu neun Zehnteln leer ist.
#:
#: 620 und nicht 460: Die Startseite und die Funktionsseite zeigen dieses Bild
#: in einer Spalte von rund 600 Bildpunkten, und bei 460 Punkten Quelle hieß
#: das **124 bis 131 Prozent** — ein hochgerechnetes Bildschirmfoto, also genau
#: die weiche Schrift, die ein Bildschirmfoto nie haben sollte. Gemessen, nicht
#: geschätzt: die Seite wurde geladen und ausgerechnet. Die Höhe folgt dem
#: Inhalt und nicht dem Verhältnis — vier Befunde in einer Fläche von 400
#: Punkten sind zur Hälfte leerer Grund.
REPORT = (620, 270)


#: Wie lange ein „Durchgang" beim Setzenlassen dauert, in Millisekunden.
#: ``settle(app, 30)`` sind damit anderthalb Sekunden — genug für einen
#: Bildaufbau, wenig genug, dass sechs Aufnahmen je Sprache erträglich bleiben.
SETTLE_MS = 50


def target_screen() -> Any:
    """Der Bildschirm, auf dem aufgenommen wird (siehe :data:`SCREEN_INDEX`)."""
    screens = QApplication.screens()
    if not screens:
        raise SystemExit("Kein Bildschirm — hier wird nichts aufgenommen")
    return screens[SCREEN_INDEX] if len(screens) > SCREEN_INDEX else screens[0]


def work_area() -> tuple[int, int]:
    """Wie groß ein maximiertes Fenster auf dem Zielschirm wird.

    ``availableGeometry`` und nicht ``geometry``: Die Taskleiste gehört nicht
    ins Bild, und ein Fenster, das sich unter sie schiebt, gibt es nicht.
    """
    if WINDOW is not None:
        return WINDOW
    area = target_screen().availableGeometry()
    return int(area.width()), int(area.height())


def settle(app: QApplication, rounds: int = 12) -> None:
    """Der Oberfläche Zeit geben, fertig zu werden, bevor abgedrückt wird.

    **Mit einem laufenden Event-Loop, nicht mit ``processEvents``.** Der
    Unterschied ist genau der Fehler, der das Hauptfenster zweimal mit leerem
    Viewport ins Handbuch gebracht hat: ein natives OpenGL-Fenster zeichnet
    unter ``processEvents`` nur, solange etwas passiert — die Kulisse stand im
    Bild, das Modell nicht. Ein echter Loop lässt Qt und den Treiber ihre
    Arbeit zu Ende bringen.
    """
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(rounds * SETTLE_MS, loop.quit)
    loop.exec()


def await_result(app: QApplication, session: object, seconds: float = 30.0) -> bool:
    """Warten, bis die Auswertung durch ist.

    Sie läuft in einem Arbeitsfaden (§15.6), also genügt kein Stapel
    ``processEvents``: ohne das Warten wird das Hauptfenster fotografiert,
    während es noch den Startbildschirm zeigt — genau das ist beim ersten
    Versuch passiert.

    Gewartet wird in kurzen Loop-Läufen und nicht mit ``sleep``: ein
    schlafender Hauptthread zeichnet nicht, und die Auswertung meldet sich
    über Signale, die einen Loop brauchen.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        settle(app, 1)
        if getattr(session, "last_result", None) is not None:
            settle(app)
            return True
    return False


def frame_sketch(window: Any, app: QApplication) -> None:
    """Den Skizzenmodus so aufsetzen, dass ein Bild davon etwas zeigt.

    Drei Dinge, und jedes hat einen Anlauf gekostet:

    * **Auf einer Fläche des Teils**, nicht auf der Grundebene. Das Beispiel
      steht angeordnet auf dem Bett, die Grundebene liegt im Ursprung — jeder
      Ausschnitt, der beides zeigt, schiebt die Zeichnung an den unteren
      Bildrand.
    * **Auf der höchsten** nach oben zeigenden Fläche, über die Geometrie
      gesucht und nicht über den Namen: Die größte Fläche der Szene ist der
      Deckel, und der liegt zum Drucken umgedreht — die Kamera sähe seine
      Unterseite und die eingeprägte Beschriftung spiegelverkehrt. Ein Filter
      über den Objektnamen träfe außerdem in fünf Sprachen etwas anderes.
    * **Die Bedienleiste ausgespart**, und ihre Höhe wird gemessen. Sie steht
      unten im Bild, und ihr Anteil hängt an der Fenstergröße: Was bei 2560
      Punkten passt, verdeckt bei 1400 die halbe Zeichnung.
    """
    from app.core.sketch import shapes
    from app.core.sketch.serialize import sketch_to_text

    ergebnis = window.session.last_result
    if ergebnis is None:
        raise SystemExit("nichts gerechnet — kein Bild vom Skizzenmodus")

    hoch_liegend: list[tuple[float, float, str]] = []
    for body in ergebnis.scene.objects.values():
        for feature_id, feature in body.features.items():
            normal = feature.params.get("normal", (0.0, 0.0, 0.0))
            if feature.kind != "face" or float(normal[2]) < 0.9:
                continue
            hoch_liegend.append(
                (
                    float(body.mesh.bounds.maximum[2]),
                    float(feature.params.get("area", 0.0)),
                    feature_id,
                )
            )
    if not hoch_liegend:
        raise SystemExit("keine nach oben zeigende Fläche — kein Bild vom Skizzenmodus")
    hoch_liegend.sort(reverse=True)

    window.start_sketch(
        # **Extrudieren und nicht Tasche schneiden.** Eine Tasche verbraucht
        # einen Körper (``consumes=1``), und im Bildlauf ist keiner ausgewählt:
        # ``run_operation`` bleibt dann in einer modalen Meldung stehen und der
        # ganze Lauf hängt. Für den Kunden ist dieselbe Stelle ein eigener
        # Befund — er hat auf der Fläche eines Körpers gezeichnet, und trotzdem
        # verlangt die Tasche eine Auswahl.
        "sketch_extrude",
        # **Maße auf dem Raster.** Das Raster steht auf fünf Millimetern, und
        # ein Rechteck von 46 mal 24 legt seine Kanten zwischen die Linien —
        # im Bild sieht das aus, als läge die Zeichnung schief im Netz. 50 mal
        # 30 liegt auf ±25 und ±15, der Kreis mit 20 auf ±10.
        sketch_to_text(shapes.rectangle(50.0, 30.0)),
        plane=f"feature:{hoch_liegend[0][2]}",
    )
    panel = window._sketch_panel
    if panel is None:
        raise SystemExit("der Skizzenmodus ging nicht auf — kein Bild davon")
    panel.canvas.insert_shape(shapes.circle(20.0))
    settle(app, 20)

    frame = window._sketch_frame()
    if frame is None:
        return
    xs = [x for x, _y in panel.canvas.points()]
    ys = [y for _x, y in panel.canvas.points()]
    sicht = max(window.viewport.height(), 1)
    leiste = min(0.6, panel.height() / sicht)
    hoch = (max(ys) - min(ys)) / max(1.0 - leiste, 0.2) * 1.35
    window.viewport.show_span_on_plane(
        frame,
        (
            (max(xs) + min(xs)) / 2.0,
            (max(ys) + min(ys)) / 2.0 + hoch * leiste / 2.0,
        ),
        ((max(xs) - min(xs)) * 1.35, hoch),
    )
    settle(app, 40)


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


def prepared(
    widget: QWidget,
    size: tuple[int, int] | None = None,
    *,
    hidden: bool = True,
    fit_height: bool = False,
    maximize: bool = True,
) -> QWidget:
    """Ein Fenster aufbauen — normalerweise, ohne es jemandem zu zeigen.

    ``size=None`` heißt bildschirmfüllend (:func:`work_area`), und das ist der
    Normalfall für alles, was in der Anwendung ein Fenster ist.

    ``hidden=False`` braucht das Hauptfenster: sein Viewport rendert über
    OpenGL, und OpenGL zeichnet nichts in ein Fenster, das nie auf dem
    Bildschirm war. Ohne das ist die Bildmitte auf dem Bild schwarz — also
    ausgerechnet das Modell, um das es geht. Ein sichtbares Fenster wird
    außerdem **auf den Zielschirm gesetzt und maximiert** statt auf ein Maß
    gezogen: Ein von Hand auf die Arbeitsfläche vergrößertes Fenster ist nicht
    dasselbe wie ein maximiertes — Windows legt bei maximierten Fenstern einen
    unsichtbaren Rahmen an, und ``grabWindow`` schneidet ihn mit ab.

    ``maximize=False`` lässt ein sichtbares Fenster bei ``size``. Das braucht
    ``tools/make_web_images.py``: Auf der Website steht dasselbe Fenster in
    einer Spalte von 650 Bildpunkten, und ein bildschirmfüllendes Bild ist dort
    auf ein Viertel gestaucht — man sieht, dass es eine Oberfläche ist, und
    nicht mehr, welche.

    ``fit_height`` nimmt die Höhe vom Inhalt statt aus ``size``. Für einen
    Dialog ist das der Unterschied zwischen einem Bild und einem falschen Bild:
    er wächst mit seinen Feldern, und auf eine feste Höhe gezogen zeigt er
    Leerraum, den niemand je sieht.
    """
    measured = size if size is not None else work_area()
    if hidden:
        widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    if fit_height:
        widget.resize(measured[0], widget.sizeHint().height())
    else:
        widget.resize(*measured)
    if not hidden:
        screen = target_screen()
        widget.setScreen(screen)
        widget.move(screen.availableGeometry().topLeft())
    widget.show()
    if not hidden and maximize:
        widget.showMaximized()
    if fit_height:
        # Nach dem Anzeigen noch einmal: erst dort kennt Qt die endgültigen
        # Schriftmaße, und ein umgebrochener Beschreibungssatz ändert die Höhe.
        widget.resize(measured[0], widget.sizeHint().height())
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
    "es": (
        "El modelo está abierto en tres puntos.",
        "14 triángulos apuntan hacia dentro.",
        "Una pared es más delgada que dos cordones de extrusión.",
        "El archivo no indicaba la unidad; se han supuesto milímetros.",
    ),
    "fr": (
        "Le modèle est ouvert à trois endroits.",
        "14 triangles sont orientés vers l'intérieur.",
        "Une paroi est plus mince que deux cordons d'extrusion.",
        "Le fichier n'indiquait pas d'unité ; les millimètres ont été supposés.",
    ),
    "it": (
        "Il modello è aperto in tre punti.",
        "14 triangoli sono rivolti verso l'interno.",
        "Una parete è più sottile di due passate di estrusione.",
        "Nel file non c'era l'unità; sono stati assunti millimetri.",
    ),
    "pt": (
        "O modelo está aberto em três sítios.",
        "14 triângulos apontam para dentro.",
        "Uma parede é mais fina do que dois cordões de extrusão.",
        "O ficheiro não indicava a unidade; foram assumidos milímetros.",
    ),
}

#: Der Name des Körpers im Operationsdialog, aus demselben Grund ausgeschrieben.
SAMPLE_OBJECT = {
    "de": "Halterung",
    "en": "Bracket",
    "es": "Soporte",
    "fr": "Support",
    "it": "Supporto",
    "pt": "Suporte",
}


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


def translate_parameter_titles(session: Any) -> None:
    """Setzt die Titel der Beispielparameter in die Sprache der Aufnahme.

    Die Titel stammen aus dem Code — ``tools/make_examples.py`` markiert sie
    mit ``_()``, und weil diese Datei in ``EXTRA_SOURCES`` steht, stehen sie
    im Katalog. Beim Speichern geht die Herkunft aber verloren: Für einen
    **Transaktionstitel** vermerkt die Projektdatei ``title_translatable``,
    für einen Parameter gibt es das Feld nicht. Geladen kommt deshalb ein
    nackter deutscher Text zurück, und ohne diesen Schritt stünde in der
    Parameterleiste jedes fremdsprachigen Bildes „Breite" statt „Ancho" —
    dieselbe Sorte Fehler, die schon einmal als deutscher Prüfbericht im
    englischen Handbuch zu sehen war.

    Aufgelöst wird nur hier, für die Aufnahme. Die Anwendung selbst darf das
    nicht tun: Sie kann einen Titel aus dem Code nicht von einem selbst
    getippten unterscheiden, und ein Abgleich mit dem Katalog übersetzte
    plötzlich auch den, der zufällig einem Eintrag gleicht — genau die
    Begründung, die in ``migrations.py`` für Transaktionstitel steht. Die
    saubere Stelle ist das Dateiformat; dort gehört es in den nächsten
    Schritt (7 → 8), der für P16.9 ohnehin ansteht.
    """
    parameters = session.project.document.parameters
    for name, parameter in list(parameters.items()):
        if parameter.title:
            parameters[name] = replace(parameter, title=tr(str(parameter.title)))


def take_all(app: QApplication, language: str) -> None:
    """Alle fünf Aufnahmen einer Sprache."""
    from app.core import examples
    from app.ui.catalog import PartCatalog, catalog_size
    from app.ui.main_window import MainWindow
    from app.ui.op_dialog import OperationDialog
    from app.ui.panels import ReportPanel
    from app.ui.recipe_dialog import RecipeDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.start_screen import StartScreen

    print(f"{language}:")

    start = prepared(StartScreen())
    settle(app)
    shoot(start, "start-screen", language)
    start.close()

    session = Session()
    window = prepared(MainWindow(session, UiSettings()), hidden=False)
    project = examples.directory() / EXAMPLE
    if not project.is_file():
        raise SystemExit(f"Beispielprojekt fehlt: {project}")
    session.open_project(project)
    translate_parameter_titles(session)
    # Die Leiste ist beim Öffnen schon gefüllt — ohne diesen zweiten Aufbau
    # stünden die alten, deutschen Titel im Bild, obwohl das Dokument längst
    # die übersetzten trägt.
    window.parameters.show_document(session.project.document)
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

    # **Der Skizzenmodus, und zwar dort, wo er stattfindet.** Bis zum
    # 25.08.2026 stand hier ein ``SketchPanel`` als eigenes Vollbild — die
    # Ansicht, die es seit P4 nicht mehr gibt. Gezeichnet wird im Viewport:
    # Die Kamera schwenkt auf die Zeichenebene, das Modell bleibt abgeblendet
    # stehen, das Panel ist die Leiste unter dem Bild, die Bedingungen sind ein
    # Reiter rechts. Deshalb dasselbe Fenster wie eben und ``from_screen`` —
    # was OpenGL zeichnet, holt nur der Bildschirm.
    frame_sketch(window, app)
    shoot(window, "sketch-mode", language, from_screen=True)

    # **Und was daraus wird.** Die Skizze allein zeigt die Hälfte; der Kunde
    # will sehen, dass am Ende ein Körper steht. Gegangen wird der Weg, den er
    # geht: *Fertig*, dann der Operationsdialog, dann *Übernehmen*.
    #
    # Der Dialog ist **nicht modal** (``_open_operation_dialog``, wegen der
    # Vorschau) — er blockiert hier also nichts, sondern steht danach in
    # ``window._op_dialog`` und wird von Hand angenommen. Ein Prüfstand, der
    # das nicht weiß, misst die Szene vor der Antwort und hält den Weg für tot;
    # genau das ist am 25.08.2026 einmal passiert.
    window.finish_sketch(keep=True)
    settle(app, 80)
    dialog = window._op_dialog
    if dialog is not None:
        dialog.accept()
        settle(app, 40)
    if not await_result(app, session):
        raise SystemExit("die Extrusion wurde nicht fertig — kein Bild vom Ergebnis")
    # **Die Ansicht zurück auf die Übersicht.** Sie stand zuletzt eng auf der
    # Zeichenebene, weil das Skizzenbild sie dorthin gestellt hat — auf dem
    # Ergebnis wäre davon nur eine graue Fläche zu sehen, und was entstanden
    # ist, müsste man im Objektbaum nachlesen.
    window.viewport.view_from("iso")
    window.viewport.reset_camera()
    settle(app, 60)
    shoot(window, "sketch-result", language, from_screen=True)

    # Zurücknehmen, damit das Beispiel für die folgenden Bilder unverändert ist.
    session.undo()
    await_result(app, session)
    # **Und den Änderungsstand mit zurücknehmen.** Sonst fragt ``closeEvent``
    # am Ende des Laufs nach ungespeicherten Änderungen — modal, und der ganze
    # Lauf steht. Gefunden mit py-spy an zwei Läufen, die beide in
    # ``confirm_unsaved`` warteten, nachdem alle Bilder längst geschrieben
    # waren.
    session._dirty = False
    settle(app, 20)

    # Unmittelbar davor und nicht früher: Die Auswertung nach dem Undo läuft
    # noch und setzt den Änderungsstand erneut. Ein Reset weiter oben wirkte
    # deshalb nicht, und der Lauf blieb ein zweites Mal in der Frage stehen.
    session._dirty = False
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

    # **Nicht auf DIALOG-Höhe zwingen.** Die Dialoge wachsen mit ihrem Inhalt
    # (143 bis 427 Bildpunkte, gemessen); auf 460 gezogen standen zweihundert
    # Punkte Leerraum zwischen dem letzten Feld und „Weitere Einstellungen", und
    # die Zahlenfelder waren auf 330 Punkte gestreckt. Das Bild zeigte einen
    # unfertigen Dialog, den es nicht gibt. Die Breite bleibt gesetzt, damit alle
    # Sprachen dasselbe Maß haben.
    dialog = prepared(
        OperationDialog(
            REGISTRY.get("drill_hole"),
            [SAMPLE_OBJECT.get(language, SAMPLE_OBJECT["de"])],
            values={"diameter": 4.2, "x": 20.0, "y": 0.0},
        ),
        DIALOG,
        fit_height=True,
    )
    settle(app)
    shoot(dialog, "op-dialog", language)
    dialog.close()

    # Der Katalog bestimmt seine Größe selbst (:func:`catalog.catalog_size`) —
    # ein Anteil des Bildschirms, gedeckelt. Ihn hier auf ein Maß zu ziehen
    # zeigte einen Dialog, den es so nicht gibt.
    catalog = prepared(PartCatalog(), catalog_size())
    settle(app, 30)
    shoot(catalog, "catalog", language)
    catalog.close()

    # Der Dialog, mit dem ein selbst gebautes Teil in den Katalog kommt. Er
    # bekommt hier Werte, die zeigen, worum es geht: Projektparameter mit
    # Titel und Einheit, damit die Zeilen nicht nach ihrem internen Namen
    # aussehen, und zwei erkannte Merkmale, damit die untere Liste nicht leer
    # ist — leer erklärt sie nämlich, warum sie leer ist, und das ist das
    # Bild eines Sonderfalls.
    recipe = prepared(
        RecipeDialog(
            replace(
                new_project().document,
                parameters={
                    "breite": Parameter(name="breite", value=120.0, unit="mm", title=tr("Breite")),
                    "hoehe": Parameter(
                        name="hoehe",
                        value=24.0,
                        unit="mm",
                        title=tr("Höhe"),
                        minimum=12.0,
                        maximum=60.0,
                    ),
                },
            ),
            {},
            (1, 2),
            (
                Feature(id="hole_1", kind="hole", provenance="detected", params={"diameter": 4.2}),
                Feature(id="face_2", kind="face", provenance="detected", params={"area": 2880.0}),
            ),
            session.profile,
        ),
        DIALOG,
        fit_height=True,
    )
    recipe.title.setText(tr("Halter für die Werkbank"))
    settle(app)
    shoot(recipe, "own-part", language)
    recipe.release()
    recipe.close()

    window.close()


def chosen_screen(arguments: list[str]) -> list[str]:
    """``--schirm N`` aus den Argumenten nehmen und :data:`SCREEN_INDEX` setzen.

    Gibt die übrigen Argumente zurück — die Sprachen. Wer nur einen Bildschirm
    hat, braucht das nie; wer den Zielschirm wechselt, will ihn nicht im
    Quelltext ändern müssen.
    """
    global SCREEN_INDEX
    if "--schirm" not in arguments:
        return arguments
    position = arguments.index("--schirm")
    if position + 1 >= len(arguments) or not arguments[position + 1].isdigit():
        raise SystemExit("--schirm braucht eine Nummer, etwa: --schirm 1")
    SCREEN_INDEX = int(arguments[position + 1])
    return arguments[:position] + arguments[position + 2 :]


def chosen_languages(wanted: tuple[str, ...]) -> tuple[str, ...]:
    """Welche Sprachen aufgenommen werden — alle, oder die genannten.

    Ohne Angabe alle. Mit Angabe nur diese: Eine Sprache, die dazukommt,
    braucht ihre Bilder, und die fünf fertigen deshalb neu aufzunehmen kostet
    das Vielfache der Zeit und ändert an ihnen nichts — außer dem Zeitstempel
    und, wenn zwischenzeitlich jemand an der Oberfläche war, unbeabsichtigt
    auch dem Inhalt.

        python tools/make_figures.py es fr it pt
    """
    available = available_languages()
    if not wanted:
        return available
    unknown = [language for language in wanted if language not in available]
    if unknown:
        raise SystemExit(
            f"Unbekannte Sprache: {', '.join(unknown)} — bekannt: {', '.join(available)}"
        )
    return wanted


def main() -> int:
    # Beim Start zurückgesetzt, nicht beim Import — die Begründung steht in
    # `tools/make_manual.py`: ein Modul, das die Plattform schon beim Importieren
    # umstellt, reißt jeden Testlauf mit, der es nur lesen will.
    os.environ.pop("QT_QPA_PLATFORM", None)

    from app.ui.app import install_qt_translations
    from app.ui.theme import apply_theme

    languages = tuple(chosen_screen(sys.argv[1:]))
    load_operations()
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    area = target_screen().availableGeometry()
    print(f"Bildschirm {SCREEN_INDEX}: {target_screen().name()} — {area.width()}x{area.height()}\n")
    # **Mit dem Thema, nicht nur mit der Palette.** Ohne diese Zeile nahmen
    # die Bilder die Anwendung ohne ihr Stylesheet auf: Kacheln ohne Rahmen,
    # Knöpfe ohne Abstufung, der Titel in Fließtextgröße. Ein Handbuch, das
    # etwas anderes zeigt als die Anwendung, ist an der Stelle falsch, an der
    # man ihm am ehesten glaubt.
    apply_theme(app, "dark")
    qt_translator = None
    for language in chosen_languages(languages):
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
