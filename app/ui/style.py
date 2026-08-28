"""Formsprache: Stylesheet, Typografie-Skala, Abstandsraster (Bauplan §19.3).

`theme.py` setzt Farben — Hintergrund, Text, Auswahl. Das war lange alles, und
darum sah die Anwendung aus wie jede andere Qt-Anwendung: Fusion-Knöpfe,
Fusion-Felder, Fusion-Reiter, keine eigenen Radien, keine Abstufung zwischen
Haupt- und Nebenknopf, keine Zustände über den Vorgaben.

Drei Dinge stehen hier, und sie hängen zusammen:

**Das Stylesheet** definiert Knöpfe, Felder, Listen, Reiter, Kopfzeilen und
Trenner einmal, mit ihren Zuständen (normal, überfahren, Fokus, gedrückt,
gesperrt). Es lebt in Python und nicht in einer `.qss`-Datei neben dem Paket:
Farben kommen aus dem Thema und die Schriftgrößen aus der Systemeinstellung, es
wäre also ohnehin eine Vorlage — und eine Datei, die beim Paketieren
vergessen wird, nimmt der Anwendung stillschweigend ihr ganzes Aussehen.

**Die Typografie-Skala** hat vier Stufen. Vorher war alles gleich laut: im
Objektbaum war der Name so groß wie das Maß, im Prüfbericht ein Fehler so groß
wie ein Hinweis. Nebentext — Maße, Einheiten, Herkunft — soll lesbar sein, nicht
mitreden.

**Das Abstandsraster** ist eine Zahl und ihre Vielfachen. Vorher standen Dinge
mal 2, mal 3, mal 5, mal 6 Pixel auseinander, jede Stelle für sich entschieden;
das ist der Eindruck, dass alles ein bisschen daneben sitzt, ohne dass man
einen einzelnen Fehler benennen kann.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from app.ui.theme import THEMES, Theme

#: Die Grundzahl des Rasters. Jeder Abstand in der Oberfläche ist ein
#: Vielfaches davon — ``tests/test_style.py`` prüft das.
SPACE = 4

TIGHT = SPACE
"""Zwischen Dingen, die zusammengehören: Symbol und Beschriftung."""
NORMAL = SPACE * 2
"""Der Regelabstand zwischen Bedienelementen einer Zeile."""
ROOMY = SPACE * 3
"""Die Innenkante eines Panels oder Dialogs."""
WIDE = SPACE * 4
"""Zwischen Abschnitten, die nichts miteinander zu tun haben."""

#: Die vier Stufen, in absteigender Lautstärke.
LEVELS = ("title", "section", "body", "caption")

#: Faktor und Gewicht je Stufe, bezogen auf die Grundschriftgröße des Systems.
#: Relativ und nicht absolut, weil §19.3 skalierbare Schrift verlangt: wer seine
#: Systemschrift größer stellt, bekommt hier alles größer, nicht nur den Rest.
SCALE: dict[str, tuple[float, int]] = {
    "title": (1.75, 600),
    "section": (1.15, 600),
    "body": (1.0, 400),
    "caption": (0.85, 400),
}


def type_scale(base: int) -> dict[str, tuple[int, int]]:
    """Punktgrößen und Gewichte der vier Stufen zu einer Grundgröße."""
    return {
        level: (max(round(base * factor), 1), weight) for level, (factor, weight) in SCALE.items()
    }


def set_level(widget: QWidget, level: str) -> None:
    """Setzt die Typografie-Stufe eines Widgets.

    Über eine Qt-Eigenschaft und nicht über ein eigenes Stylesheet je Widget:
    so steht die Gestaltung an einer Stelle, und ein Themenwechsel muss nicht
    hundert Einzelfälle einsammeln.
    """
    widget.setProperty("level", level)
    _repolish(widget)


def make_primary(button: QPushButton) -> QPushButton:
    """Macht einen Knopf zum Hauptknopf — und breit genug für seine eigene
    Beschriftung.

    ``setDefault(True)`` allein genügt nicht, und das ist der Fehler, den man
    erst im Bild sieht: Das Stylesheet setzt für ``QPushButton:default`` ein
    ``font-weight: 600``, gezeichnet wird also halbfett. Qt rechnet die
    bevorzugte Breite aber aus der **normalen** Schrift des Widgets — bei
    „Jetzt trennen" sind das 77 gegen 89 Bildpunkte. Wo ein Layout dem Knopf
    genau seine bevorzugte Breite gibt, und in einer engen Leiste tut es das,
    stand auf dem Hauptknopf „etzt trenne".

    Die Schrift hier am Widget zu setzen behebt beides an einer Stelle: Die
    Zeichnung bleibt, wie sie war, und die Breitenrechnung kennt sie jetzt.
    Fett bleibt dabei die zweite Kodierung neben der Akzentfarbe (Regel 18) —
    sie zu streichen wäre die andere Möglichkeit gewesen und die schlechtere.
    """
    button.setDefault(True)
    font = button.font()
    font.setWeight(QFont.Weight.DemiBold)
    button.setFont(font)
    return button


def _repolish(widget: QWidget) -> None:
    """Qt liest dynamische Eigenschaften nur beim Aufbau — hier noch einmal."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


#: Die zwei Pfeile am Zahlenfeld, als Zeichnung ohne Datei im Paket.
#:
#: Ein Dreieck, zweimal — nach oben und nach unten. ``{colour}`` füllt die
#: Textfarbe des Themas ein.
#: Die Zeichenfläche ist genau so groß wie der Platz im Stylesheet — ein
#: Dreieck aus einer 8-zu-5-Fläche in ein 8-zu-4-Feld gequetscht sitzt unscharf.
_ARROW_SVG: Final = {
    "up": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4">'
    '<path d="M0 4 L4 0 L8 4 Z" fill="{colour}"/></svg>',
    "down": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4">'
    '<path d="M0 0 L4 4 L8 0 Z" fill="{colour}"/></svg>',
}


def arrow_files(theme: Theme) -> dict[str, str] | None:
    """Legt die Pfeile des Zahlenfelds als Dateien ab und nennt ihre Pfade.

    **Warum überhaupt Dateien.** Qt hört auf, die Unterelemente eines
    ``QSpinBox`` selbst zu zeichnen, sobald ein Stylesheet an ihm eine
    Rahmeneigenschaft setzt — und das tut die Regel, die allen Eingabefeldern
    ihren Radius gibt. Übrig blieben zwei leere Kästchen. Ein Dreieck aus
    Rahmenkanten, wie man es in HTML baut, hilft nicht: Qt füllt die Fläche
    und zeichnet einen hellen Block. Bleibt ein Bild, und ein Bild braucht in
    einem Stylesheet einen Pfad.

    **Warum nicht im Paket.** Eine mitgelieferte Datei hätte eine feste Farbe,
    also bräuchte jedes Thema seine eigene — und eine Datei, die beim
    Paketieren vergessen wird, nimmt den Pfeilen ihr Aussehen genauso still,
    wie es hier verloren ging. Geschrieben wird deshalb in den Cache (§38), der
    jederzeit gelöscht werden darf; beim nächsten Start steht er wieder da.

    Gibt ``None`` zurück, wenn sich nichts schreiben lässt. Dann bleiben die
    Knöpfe leer — das ist der Zustand von vorher und kein Grund, eine
    Anwendung nicht zu starten.
    """
    from app.core.paths import ensure_dir, user_cache_dir

    try:
        folder = ensure_dir(user_cache_dir() / "style")
        paths = {}
        for direction, template in _ARROW_SVG.items():
            target = folder / f"spin-{direction}-{theme}.svg"
            target.write_text(template.format(colour=THEMES[theme]["text"]), encoding="utf-8")
            paths[direction] = target.as_posix()
        return paths
    except OSError:
        return None


def _arrow_rules(arrows: dict[str, str] | None) -> str:
    """Die Stylesheet-Zeilen, die die Pfeile ins Zahlenfeld setzen."""
    if not arrows:
        return ""
    return f"""
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url("{arrows["up"]}");
    width: {NORMAL}px;
    height: {SPACE}px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url("{arrows["down"]}");
    width: {NORMAL}px;
    height: {SPACE}px;
}}
"""


def stylesheet(theme: Theme, base_point_size: int, arrows: dict[str, str] | None = None) -> str:
    """Das Stylesheet der Anwendung, gefüllt aus Thema und Schriftgröße.

    ``arrows`` sind die Pfeile des Zahlenfelds, siehe :func:`arrow_files`. Ohne
    sie bleiben die Auf- und Ab-Knöpfe leer — für einen Test, der nur die
    Farben liest, ist das gleichgültig.
    """
    colours = THEMES[theme]
    sizes = type_scale(base_point_size)
    window = colours["window"]
    base = colours["base"]
    text = colours["text"]
    # Zwei Farben, nicht eine. ``muted`` ist Nebentext — Maße, Einheiten,
    # Spaltenköpfe, Gruppentitel, der stille Reiter: leise, aber zu lesen.
    # ``disabled`` heißt gesperrt und soll genau das zeigen. Beides lag auf
    # demselben Wert, und damit war beides falsch: Ein Fünftel aller
    # Beschriftungen trug die Sperrfarbe und kam auf 2,59 Kontrast im hellen
    # Thema, während ein gesperrter Knopf sich von einem stillen Spaltenkopf
    # nicht unterschied.
    muted = colours["muted"]
    disabled = colours["disabled"]
    line = colours["line"]
    highlight = colours["highlight"]
    on_highlight = colours["highlight_text"]
    highlight_pressed = colours["highlight_pressed"]
    accent_line = colours["accent_line"]
    hover = colours["alternate"]
    tooltip = colours["tooltip"]

    # Der Fokusring nimmt dieselbe Farbe wie die Akzentkante, und aus demselben
    # Grund: Er muss auf seinem Untergrund zu sehen sein. ``highlight`` ist
    # dafür nur im dunklen Thema geeignet — der Bernstein bringt gegen das
    # helle Fenster 1,70 und gegen ein weißes Feld 2,06, und WCAG 1.4.11
    # verlangt für die Umrandung eines Bedienelements 3,0. Ein Ring, den man
    # nicht sieht, ist für den, der ohne Maus arbeitet, gar keiner.
    # ``accent_line`` ist im dunklen Thema derselbe Bernstein und im hellen der
    # abgedunkelte Ton daneben: 3,66 auf Weiß, 3,01 auf dem Fenster.
    focus = accent_line

    # Der Rahmen eines Eingabefelds ist immer zwei Punkte breit — im
    # Ruhezustand wie im Fokus. Er war einen breit und wuchs beim Fokus auf
    # zwei, und das brach das Aufklappmenü jeder Combobox: Qt leitet die Höhe
    # des Popups aus dem Innenrechteck der Combobox ab, verlor durch den
    # zweiten Rahmenpunkt zwei Punkte, kippte damit in den Rollbetrieb und
    # verlor an dessen zwei Pfeilen weitere zehn. Zwölf Punkte sind ein halber
    # Eintrag: Wer „Bezugspunkt" anklickte, sah „Mündung" und darunter „Mitte"
    # waagerecht durchgeschnitten. Gemessen bei zwei, drei, vier und fünf
    # Einträgen, in beiden Themen, und es traf jede Combobox, die den Fokus
    # hatte — also jede, die man anklickt.
    #
    # Der Fokus sagt es deshalb über **Farbe und Strichart**: Der Ring bleibt
    # zwei Punkte breit und wird gestrichelt. Ein erster Anlauf ließ nur die
    # Farbe wechseln, mit dem Argument, ein Punkt Rahmenbreite sei ohnehin
    # keine wahrnehmbare Kodierung gewesen — das stimmt und trägt trotzdem
    # nicht: Regel 18 verlangt die zweite Kodierung, nicht den Nachweis, dass
    # die alte auch keine war. Kontrast unverändert 8,02 im dunklen Thema.
    #
    # **Und der Ruhezustand behält die volle Linienfarbe.** Ein erster Anlauf
    # dämpfte sie zur Feldfläche hin, damit der doppelt so breite Rahmen so
    # leise wirkt wie der einfache vorher — das sah im Bild gut aus und war
    # gemessen falsch: 1,90 statt 3,33 im dunklen Thema, also unter den 3,0,
    # die WCAG 1.4.11 für die Umrandung eines Bedienelements verlangt. Und die
    # Fläche trägt die Grenze nicht mit: Feld gegen Fenster sind 1,45. Wer den
    # Rahmen dämpft, nimmt dem Feld seine einzige Kante.
    field_line = line

    return f"""
/* --- Typografie: vier Stufen, Größe und Gewicht und Farbe --------------- */
*[level="title"] {{ font-size: {sizes["title"][0]}pt; font-weight: {sizes["title"][1]}; }}
*[level="section"] {{ font-size: {sizes["section"][0]}pt; font-weight: {sizes["section"][1]}; }}
*[level="body"] {{ font-size: {sizes["body"][0]}pt; font-weight: {sizes["body"][1]}; }}
*[level="caption"] {{
    font-size: {sizes["caption"][0]}pt;
    font-weight: {sizes["caption"][1]};
    color: {muted};
}}

/* --- Knöpfe: Haupt- und Nebenknopf sind zu unterscheiden ---------------- */
QPushButton {{
    background: {window};
    border: 1px solid {line};
    border-radius: {SPACE}px;
    padding: {TIGHT}px {ROOMY}px;
    min-height: {WIDE}px;
}}
QPushButton:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {line}; }}
QPushButton:default {{
    background: {highlight};
    color: {on_highlight};
    border-color: {highlight};
    font-weight: 600;
}}
QPushButton:default:hover {{ background: {highlight}; border-color: {text}; }}
QPushButton:disabled {{ color: {disabled}; border-color: {line}; background: {window}; }}
/* Der Hauptknopf gibt beim Drücken nach. Ohne eigene Regel gewann hier
   ``:default`` — es steht später und wiegt gleich schwer —, und der lauteste
   Knopf der Anwendung war der einzige, der auf einen Klick nichts tat.

   **Und die Regel allein genügte nicht.** Sie nahm ``accent_line``, und die
   *ist* im dunklen Thema der Bernstein selbst: gedrückt sah aus wie
   losgelassen, im voreingestellten Thema, auf jedem Hauptknopf. Im hellen
   fiel es nie auf, weil dort der abgedunkelte Ton steht. Jetzt steht der
   Druckzustand als eigene Farbe in der Themen-Tabelle — 1,78 Unterschied zum
   Ruhezustand, dunkle Schrift darauf 4,47. */
QPushButton:default:pressed {{
    background: {highlight_pressed};
    border-color: {highlight_pressed};
}}
/* Zwei Bildpunkte Rahmen statt einem, und der Innenabstand gibt den einen
   wieder her: sonst wandert die Beschriftung beim Durchtabben um einen Punkt,
   und ein Dialog zittert unter der Tabulatortaste. */
QPushButton:focus {{
    border: 2px solid {focus};
    padding: {TIGHT - 1}px {ROOMY - 1}px;
}}

QToolButton {{
    border: 1px solid transparent;
    border-radius: {SPACE}px;
    padding: {TIGHT}px {NORMAL}px;
}}
QToolButton:hover {{ background: {hover}; border-color: {line}; }}
QToolButton:checked {{ background: {highlight}; color: {on_highlight}; border-color: {highlight}; }}
QToolButton:focus {{
    border: 2px solid {focus};
    padding: {TIGHT - 1}px {NORMAL - 1}px;
}}

/* Panel-Kopfzeilen sind dauerhaft „gedrückt"; eingefärbt wären sie die
   lauteste Fläche im Fenster für die stillste Aussage. */
QToolButton#sectionHeading {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {line};
    border-radius: 0;
    padding: {NORMAL}px {NORMAL}px {TIGHT}px {NORMAL}px;
    text-align: left;
}}
QToolButton#sectionHeading:hover {{ background: {hover}; }}
QToolButton#sectionHeading:checked {{ background: transparent; color: {text}; }}
QToolButton#sectionHeading:checked:hover {{ background: {hover}; }}

/* Eine Beispielkachel ist ein großer Knopf mit zwei Zeilen darin. */
QFrame#exampleTile {{
    background: {base};
    border: 1px solid {line};
    border-radius: {NORMAL}px;
}}
/* Überfahren wechselt die **Fläche**, Fokus den **Rahmen**. Beides über den
   Rahmen zu sagen war im dunklen Thema — dem voreingestellten — keine Aussage:
   dort ist ``highlight`` derselbe Bernstein wie ``focus``, und die zwei
   Zustände unterschieden sich um einen Bildpunkt Rahmenbreite. Wer mit dem
   Tabulator durch die neun Kacheln geht, sah nicht, welche die Eingabetaste
   auslösen würde. */
QFrame#exampleTile:hover {{ background: {hover}; }}
QFrame#exampleTile:focus {{ border: 2px solid {focus}; }}

/* Der Unterstützen-Dialog trennt Erklärung und Handlung: Die drei Zusagen
   stehen als ruhige Karte zusammen, der einzige Weg nach draußen bleibt als
   Hauptknopf außerhalb. */
QFrame#donationFacts {{
    background: {base};
    border: 1px solid {line};
    border-radius: {NORMAL}px;
}}
QFrame#donationFacts QLabel {{ background: transparent; }}

/* --- Eingaben: der Fokus muss man sehen -------------------------------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {base};
    border: 2px solid {field_line};
    border-radius: {SPACE}px;
    padding: {TIGHT - 1}px {NORMAL - 1}px;
    selection-background-color: {highlight};
    selection-color: {on_highlight};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover,
QComboBox:hover, QPlainTextEdit:hover, QTextEdit:hover {{
    border-color: {muted};
}}
/* Nie die Breite — der Grund steht oben bei ``field_line``. Wohl aber die
   **Strichart**: Farbe allein wäre eine Bedeutung über Farbe, und Regel 18
   verlangt eine zweite Kodierung. Gestrichelt und nicht gepunktet, weil der
   feinere Strich im Bild unruhig wirkt und weniger Fläche trägt; dieselbe
   Wahl hat der Reiter schon getroffen (``QTabBar::tab:selected:focus``).
   Die Rahmenbreite bleibt bei zwei Punkten, also bleibt auch das
   Aufklappmenü der Combobox heil — gemessen, 48 von 48 Punkten. */
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 2px dashed {focus};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {disabled};
    background: {window};
}}

/* --- Die Pfeile am Zahlenfeld ------------------------------------------
   Sobald ein Stylesheet an einem ``QSpinBox`` eine Rahmeneigenschaft setzt,
   hört Qt auf, dessen Unterelemente nativ zu zeichnen. Übrig blieben zwei
   leere Kästchen mit einem Strich dazwischen — auf jedem Zahlenfeld jedes
   Dialogs, in beiden Themen. Wer das sieht, hält es für einen Grafikfehler
   und klickt nicht hin.

   Gezeichnet werden sie hier aus Rahmen: eine Fläche der Größe null, deren
   drei Kanten ein Dreieck stehen lassen. Ein Bild wäre die andere
   Möglichkeit und die schlechtere — es müsste als Datei neben dem Paket
   liegen, und eine Datei, die beim Paketieren vergessen wird, nimmt den
   Pfeilen ihr Aussehen genauso still, wie es hier verloren ging. */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    width: {ROOMY}px;
    background: transparent;
    border-left: 1px solid {line};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-position: top right;
    border-top-right-radius: {SPACE}px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: {SPACE}px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {hover};
}}
{_arrow_rules(arrows)}
QComboBox QAbstractItemView {{
    background: {base};
    border: 1px solid {line};
    selection-background-color: {highlight};
    selection-color: {on_highlight};
}}

/* --- Listen und Bäume: überfahren und gewählt sind zwei Zustände -------- */
QTreeView, QListView, QTableView, QTreeWidget, QListWidget {{
    background: {base};
    border: 1px solid {line};
    border-radius: {SPACE}px;
    alternate-background-color: {hover};
}}
QTreeView::item, QListView::item, QTableView::item {{ padding: {TIGHT}px; }}
QTreeView::item:hover, QListView::item:hover, QTableView::item:hover {{ background: {hover}; }}
QTreeView::item:selected, QListView::item:selected, QTableView::item:selected {{
    background: {highlight};
    color: {on_highlight};
}}
QHeaderView::section {{
    background: {window};
    color: {muted};
    border: none;
    border-bottom: 1px solid {line};
    padding: {TIGHT}px {NORMAL}px;
    font-weight: 600;
}}

/* Ein Kachelraster wählt über Rahmen **und** Hintergrund. Voll eingefärbt
   verschwände das Vorschaubild in der Auswahlfarbe. */
QListWidget#tileGrid::item:selected {{
    background: {hover};
    color: {text};
    border: 2px solid {highlight};
    border-radius: {SPACE}px;
}}
QListWidget#tileGrid::item:hover {{ background: {hover}; border-radius: {SPACE}px; }}

/* --- Reiter ------------------------------------------------------------ */
QTabWidget::pane {{ border: 1px solid {line}; border-radius: {SPACE}px; top: -1px; }}
QTabBar::tab {{
    background: transparent;
    color: {muted};
    border: 1px solid transparent;
    border-top-left-radius: {SPACE}px;
    border-top-right-radius: {SPACE}px;
    padding: {TIGHT}px {ROOMY}px;
}}
QTabBar::tab:hover {{ color: {text}; background: {hover}; }}
/* Der aktive Reiter trägt eine Akzentkante — und zwar zusätzlich zu Fläche,
   Farbe und Fettschrift, die er schon hatte (Regel 18 bleibt unberührt).
   Vorher unterschied ihn vom stillen allein der Flächenwechsel, und der lag
   bei 1,10 Kontrast: Ob Prüfbericht oder Chat gilt, war eine Frage des
   zweiten Blicks. Das obere Padding gibt die drei Pixel wieder her, sonst
   rutscht die Beschriftung nach unten. */
QTabBar::tab:selected {{
    color: {text};
    background: {base};
    border-color: {line};
    border-top: 3px solid {accent_line};
    border-bottom-color: {base};
    padding-top: {max(TIGHT - 2, 0)}px;
    font-weight: 600;
}}
/* Die Reiterleiste zeigte den Tastaturfokus mit null Bildpunkten Unterschied —
   in beiden Themen. Wer mit dem Tabulator hierher kommt, sah nicht, dass er
   hier ist, und die Pfeiltasten wechselten scheinbar grundlos den Reiter.

   ``:selected:focus`` und nicht ``:focus`` allein: Der Zustand gilt der Leiste,
   also träfe ``QTabBar::tab:focus`` alle Reiter zugleich — in einer QTabBar ist
   der aktuelle der fokussierte. Gestrichelt, weil der aktive Reiter schon
   Akzentkante, Fläche und Fettschrift trägt; eine zweite durchgezogene Linie
   wäre nicht zu unterscheiden. */
QTabBar::tab:selected:focus {{ border: 2px dashed {focus}; }}

/* --- Rahmen, Trenner, Gruppen ------------------------------------------ */
QGroupBox {{
    border: 1px solid {line};
    border-radius: {SPACE}px;
    margin-top: {ROOMY}px;
    padding-top: {NORMAL}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: {ROOMY}px;
    padding: 0 {TIGHT}px;
    color: {muted};
    font-weight: 600;
}}
/* Die Fuge zwischen zwei Bereichen ist auch ihr Griff. Sie war einen
   Bildpunkt breit — optisch eine feine Linie und praktisch nicht zu treffen;
   wer die Detailspalte des Katalogs verbreitern wollte, zielte auf einen
   Pixel. Jetzt ist sie so breit, dass ein Zeiger sie findet, und färbt sich
   beim Überfahren, damit sie sagt, dass sie sich ziehen lässt. */
QSplitter::handle {{ background: {window}; }}
QSplitter::handle:hover {{ background: {accent_line}; }}
QSplitter::handle:horizontal {{ width: {NORMAL}px; }}
QSplitter::handle:vertical {{ height: {NORMAL}px; }}

/* --- Bildlaufleisten: schmal und still --------------------------------- */
QScrollBar:vertical {{ background: transparent; width: {ROOMY}px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: {ROOMY}px; margin: 0; }}
QScrollBar::handle {{ background: {line}; border-radius: {SPACE}px; min-height: {WIDE}px; }}
QScrollBar::handle:hover {{ background: {muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* --- Menüs und Statuszeile --------------------------------------------- */
QMenuBar {{ background: {window}; border-bottom: 1px solid {line}; }}
QMenuBar::item {{ padding: {TIGHT}px {ROOMY}px; background: transparent; }}
QMenuBar::item:selected {{ background: {hover}; }}
QMenu {{ background: {base}; border: 1px solid {line}; padding: {TIGHT}px; }}
QMenu::item {{ padding: {TIGHT}px {WIDE}px; border-radius: {SPACE}px; }}
QMenu::item:selected {{ background: {highlight}; color: {on_highlight}; }}
QMenu::separator {{ height: 1px; background: {line}; margin: {TIGHT}px {NORMAL}px; }}
QStatusBar {{ border-top: 1px solid {line}; }}
QStatusBar::item {{ border: none; }}

/* Der Hinweis unter dem Zeiger war das letzte Element ohne eigene Form: Qt
   zeichnete ihn kantig und randlos, während daneben jedes Feld seinen Radius
   trug. Er erklärt die Werkzeugzeile und jeden gesperrten Knopf — also ist er
   kein Nebenschauplatz. */
QToolTip {{
    background: {tooltip};
    color: {text};
    border: 1px solid {line};
    border-radius: {SPACE}px;
    padding: {TIGHT}px {NORMAL}px;
}}

/* --- Fortschritt -------------------------------------------------------- */
QProgressBar {{
    border: 1px solid {line};
    border-radius: {SPACE}px;
    background: {base};
    text-align: center;
}}
QProgressBar::chunk {{ background: {highlight}; border-radius: {SPACE}px; }}
/* Gesperrt heißt leiser — und hier muss es dastehen, nicht in der Palette.
   Ein Stylesheet gewinnt gegen sie: die Disabled-Gruppe trägt den gedämpften
   Akzent, gezeichnet wurde trotzdem der volle. Gemessen an einem Balken,
   zweimal gerendert: 2018 Akzentpunkte bedienbar, 2018 gesperrt. Beim Regler
   nebenan hat die Palette gereicht, weil ihn kein Stylesheet anfasst — dort
   sind es jetzt 404 gegen 0. */
QProgressBar:disabled {{ color: {disabled}; }}
QProgressBar::chunk:disabled {{ background: {disabled}; }}

"""


def apply_style(application: QApplication, theme: Theme) -> None:
    """Legt das Stylesheet über die Anwendung. Wirkt sofort und überall."""
    font = application.font()
    application.setStyleSheet(stylesheet(theme, max(font.pointSize(), 1), arrow_files(theme)))
