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

from PySide6.QtWidgets import QApplication, QWidget

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


def _repolish(widget: QWidget) -> None:
    """Qt liest dynamische Eigenschaften nur beim Aufbau — hier noch einmal."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


def stylesheet(theme: Theme, base_point_size: int) -> str:
    """Das Stylesheet der Anwendung, gefüllt aus Thema und Schriftgröße."""
    colours = THEMES[theme]
    sizes = type_scale(base_point_size)
    window = colours["window"]
    base = colours["base"]
    text = colours["text"]
    muted = colours["disabled"]
    line = colours["line"]
    highlight = colours["highlight"]
    on_highlight = colours["highlight_text"]
    accent_line = colours["accent_line"]
    hover = colours["alternate"]

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
QPushButton:disabled {{ color: {muted}; border-color: {line}; background: {window}; }}
QPushButton:focus {{ border: 2px solid {highlight}; }}

QToolButton {{
    border: 1px solid transparent;
    border-radius: {SPACE}px;
    padding: {TIGHT}px {NORMAL}px;
}}
QToolButton:hover {{ background: {hover}; border-color: {line}; }}
QToolButton:checked {{ background: {highlight}; color: {on_highlight}; border-color: {highlight}; }}
QToolButton:focus {{ border: 2px solid {highlight}; }}

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
QFrame#exampleTile:hover {{ border-color: {highlight}; background: {hover}; }}
QFrame#exampleTile:focus {{ border: 2px solid {highlight}; }}

/* --- Eingaben: der Fokus muss man sehen -------------------------------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {base};
    border: 1px solid {line};
    border-radius: {SPACE}px;
    padding: {TIGHT}px {NORMAL}px;
    selection-background-color: {highlight};
    selection-color: {on_highlight};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 2px solid {highlight};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {muted};
    background: {window};
}}
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
QSplitter::handle {{ background: {line}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

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

/* --- Fortschritt -------------------------------------------------------- */
QProgressBar {{
    border: 1px solid {line};
    border-radius: {SPACE}px;
    background: {base};
    text-align: center;
}}
QProgressBar::chunk {{ background: {highlight}; border-radius: {SPACE}px; }}
"""


def apply_style(application: QApplication, theme: Theme) -> None:
    """Legt das Stylesheet über die Anwendung. Wirkt sofort und überall."""
    font = application.font()
    application.setStyleSheet(stylesheet(theme, max(font.pointSize(), 1)))
