"""Helles und dunkles Thema (Bauplan §19.3).

Beide Themen werden hier gebaut statt der Plattform überlassen, denn Kontrast
ist Teil des Produkts: Viewport, Analysekarten und Differenzansicht setzen alle
ein bekanntes Hintergrundbild voraus. Farben, die Bedeutung tragen, leben in
``palette.py``; was hier steht, ist nur der Rahmen darum.
"""

from __future__ import annotations

from typing import Final, Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

Theme = Literal["dark", "light"]

#: Die Auswahlfarbe, in beiden Themen dieselbe.
#:
#: Sie kommt aus ``palette.ROLES["select"]`` und ist damit dieselbe, in der der
#: Viewport einen gewählten Körper färbt. Vorher waren es zwei: Qts Blau in der
#: Liste, Bernstein im Bild — dieselbe Handlung, zwei Farben, nichts verband
#: sie. Wer im Baum klickte, sah eine blaue Zeile und einen orangen Körper und
#: musste selbst schließen, dass das dasselbe meint.
#:
#: Die Schrift darauf ist dunkel und nicht weiß. Nachgemessen: Bernstein gegen
#: Weiß bringt 2,06 Kontrast, gegen ``#1c2026`` sind es 7,93. Ein heller Balken
#: verlangt dunkle Schrift, auch im dunklen Thema.
_SELECTION = "#f0a54a"
_ON_SELECTION = "#1c2026"

#: Derselbe Bernstein, gedrückt.
#:
#: Der Hauptknopf gab im **dunklen** Thema auf einen Klick nichts zurück, und
#: das lag an einer geborgten Farbe: Die Regel dafür nahm ``accent_line``, und
#: die *ist* im dunklen Thema :data:`_SELECTION` — gedrückt sah aus wie
#: losgelassen. Im hellen fiel es nie auf, weil dort der abgedunkelte Ton
#: steht. Der lauteste Knopf der Anwendung war also der einzige ohne Rückmeldung.
#:
#: Der Wert ist in beiden Themen derselbe, weil der Ruhezustand es auch ist:
#: 1,78 Unterschied zum Bernstein — deutlich zu sehen —, und die dunkle Schrift
#: darauf hält 4,47.
_SELECTION_PRESSED = "#c37210"

#: Die Kante, mit der ein *bleibender* Zustand markiert wird — der aktive
#: Reiter, der offene Abschnitt.
#:
#: Warum nicht einfach :data:`_SELECTION`: Der Bernstein ist hell. Gegen das
#: dunkle Fenster bringt er 5,4, gegen das helle nur **1,37** — dort wäre die
#: Kante ein Hauch. Im hellen Thema steht deshalb ein abgedunkelter Ton
#: derselben Farbe, gerechnet auf 3,0 gegen sein Fenster. Es ist dieselbe
#: Farbe im Sinne der Bedeutung, nur so hell, wie ihr Untergrund es zulässt.
_ACCENT_LINE: Final = {"dark": _SELECTION, "light": "#c37210"}

#: Window, panel and text colours per theme, contrast checked against WCAG AA.
#:
#: ``line`` ist die Farbe jeder Trennung — Rahmen, Trenner, Kopfzeilenkante.
#: Sie trägt keine Schrift und muss deshalb nicht AA erfüllen; sie muss
#: *sichtbar* sein.
#:
#: **Die Flächen liegen bewusst weiter auseinander als früher.** Der Stand
#: davor: Panel gegen Fenster 1,10, Zebrazeile gegen Panel 1,16, der
#: Viewport-Verlauf 1,21, die Trennlinie 1,43 — sieben Flächenrollen in einem
#: Helligkeitsband von 3,7 Prozentpunkten. Nichts trat vor oder zurück, und
#: ohne Auswahl war das Fenster wörtlich einfarbig. Die Zahlen unten sind aus
#: Zielkontrasten gerechnet und danach am Bild geprüft, nicht geschätzt.
#:
#: **Und sie sind je Thema verschieden.** Ein dunkles Thema verträgt die
#: Spreizung, die ein helles schmutzig aussehen lässt: 1,45 zwischen Panel und
#: Fenster steht dunkel gut und macht hell aus dem Weiß ein Grau. Hell arbeitet
#: deshalb mit 1,22. Wer beide über einen Kamm schert, verdirbt eines von
#: beiden.
#:
#: **``grid_minor`` und ``grid_major`` sind die Linien der Zeichenfläche.** Sie
#: standen nicht hier, und das war der ganze Fehler: `sketch_editor` nahm
#: ``palette.mid()`` mit Alpha 60 und 140 — eine Rolle, die diese Tabelle nie
#: gesetzt hat. Was ankam, war Qts Vorgabe ``#282828``, in **beiden** Themen
#: dieselbe. Gemischt über die Zeichenfläche ergab das im dunklen Thema 1,02
#: und 1,05 Kontrast: ein Raster, das gezeichnet wird und das niemand sieht,
#: während „Am Raster fangen" auf an steht. Im hellen Thema war die Hauptlinie
#: mit 3,55 umgekehrt kräftiger als die Trennlinie des Themas selbst.
#:
#: Die Werte sind aus Zielkontrasten gegen ``base`` gerechnet und danach am Bild
#: geprüft — und das Ansehen hat sie verschoben. Gerechnet standen beide Themen
#: auf 1,35 und 2,0; hell sitzt das, dunkel war es weiter zu leise. Dieselbe
#: Asymmetrie wie bei den Flächen oben, nur in der anderen Richtung: derselbe
#: Kontrastwert liest sich auf dunklem Grund schwächer. Dunkel steht deshalb auf
#: **1,60 und 2,59**, hell auf **1,35 und 2,0**.
#:
#: Gezeichnet wird das Raster **ohne Kantenglättung und auf halbe Pixel gelegt**
#: (:meth:`SketchCanvas._paint_grid`). Eine geglättete Linie von einem Pixel
#: liegt auf zwei Spalten, jede halb gemischt — aus 1,36 wurden gemessene 1,26,
#: und die Zahlen hier wären wieder eine Schätzung.
THEMES: dict[Theme, dict[str, str]] = {
    "dark": {
        "window": "#343a45",
        "base": "#1b1f25",
        "alternate": "#2c323b",
        "line": "#647182",
        "grid_minor": "#39414b",
        "grid_major": "#55606f",
        "text": "#e6e9ee",
        "disabled": "#7c848f",
        "muted": "#a8b0ba",
        "highlight": _SELECTION,
        "highlight_text": _ON_SELECTION,
        "highlight_pressed": _SELECTION_PRESSED,
        "accent_line": _ACCENT_LINE["dark"],
        "tooltip": "#2c323c",
        "viewport_bottom": "#20242b",
        "viewport_top": "#3b4350",
        "object": "#b9c4d0",
        "bed": "#5a6472",
        "bed_surface": "#2a303a",
        "edge": "#4c5258",
    },
    "light": {
        "window": "#e7e9ed",
        "base": "#ffffff",
        "alternate": "#e8eaed",
        "line": "#9ea7b5",
        "grid_minor": "#dbdee3",
        "grid_major": "#b1b8c3",
        "text": "#1c2026",
        "disabled": "#8b929b",
        "muted": "#5d646d",
        "highlight": _SELECTION,
        "highlight_text": _ON_SELECTION,
        "highlight_pressed": _SELECTION_PRESSED,
        "accent_line": _ACCENT_LINE["light"],
        # Weiß und nicht das Blassgelb, das Qt hier mitbringt: Der Hinweis
        # erscheint über Leisten und Knöpfen, also über ``window``, und hebt
        # sich davon ab. Das Gelb kam aus Windows und passte zu keiner anderen
        # Fläche des Fensters — es war die einzige Farbe im hellen Thema, die
        # nicht aus dieser Tabelle stammte.
        "tooltip": "#ffffff",
        "viewport_bottom": "#d5dae1",
        "viewport_top": "#f4f6f8",
        "object": "#7d8894",
        "bed": "#9aa3ae",
        # Zieht mit dem Hintergrund mit: Der abgedunkelte Verlauf war der
        # bisherigen Plattenfarbe auf 1,07 nahegekommen, und eine Druckplatte,
        # die man vom Nichts dahinter nicht unterscheidet, ist keine.
        "bed_surface": "#bcc4ce",
        "edge": "#1c2228",
    },
}


def build_palette(theme: Theme) -> QPalette:
    colours = THEMES[theme]
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colours["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colours["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colours["base"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colours["alternate"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colours["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colours["window"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colours["text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colours["tooltip"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colours["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colours["highlight"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colours["highlight_text"]))
    # Der Platzhaltertext stand als einzige Rolle nicht hier — und was hier
    # nicht steht, kommt aus der Systempalette. Auf einem Rechner mit dunkel
    # eingestelltem Windows war er hell, und im hellen Thema damit weiß auf
    # Weiß: Das Suchfeld des Prüfberichts war leer, der Chat fragte nichts
    # mehr, und im Schlüsseldialog fehlte das Muster ``SOLIDON3D-1-…``, das
    # als Einziges sagt, wie ein Schlüssel aussieht. Dreizehn Felder tragen
    # ihre Auskunft dort.
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(colours["disabled"]))
    # Die beiden Rasterrollen der Zeichenfläche. Qt nennt sie ``Midlight`` und
    # ``Mid``; hier heißen sie nach ihrem Zweck, und die Zeichenfläche greift
    # über die Palette darauf zu, statt eine eigene Konstante zu führen. Damit
    # zieht ein Themenwechsel sie mit, wie jede andere Farbe auch.
    palette.setColor(QPalette.ColorRole.Midlight, QColor(colours["grid_minor"]))
    palette.setColor(QPalette.ColorRole.Mid, QColor(colours["grid_major"]))
    # Der Akzent überlebte das Sperren. Gemessen an einem Regler und einem
    # Fortschrittsbalken, je zweimal gerendert: 2638 Akzentpunkte bedienbar,
    # 2638 gesperrt — pixelgleich, in beiden Themen. Fusion zeichnet die Rille
    # des Reglers und den Balken mit ``Highlight``, und diese Rolle stand nur
    # für die aktive Gruppe hier. Der gesperrte Schnittregler sah damit
    # bedienbar aus, obwohl ``SectionBar`` ihn ohne Achse abschaltet — dasselbe
    # Bild wie beim gesperrten Ankreuzfeld eine Zeile weiter unten, nur an der
    # Fläche statt an der Schrift.
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(colours["disabled"])
    )
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        # ``WindowText`` fehlte, und daran hängen genau die Elemente, die das
        # Stylesheet nicht anfasst: QLabel, QCheckBox, QRadioButton,
        # QGroupBox. Ein gesperrtes Ankreuzfeld war pixelgleich mit einem
        # bedienbaren — „Scheibe" in der Schnittleiste und „Projektdatei
        # anhängen" im Fehlerbericht sahen anklickbar aus und waren es nicht.
        QPalette.ColorRole.WindowText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colours["disabled"]))
    return palette


def apply_theme(application: QApplication, theme: Theme) -> None:
    """Schaltet die ganze Anwendung um. Wirkt sofort.

    Palette und Stylesheet gehören zusammen: die Palette trägt die Farben, das
    Stylesheet die Form. Getrennt gesetzt wären sie zwei Wege, auf denen ein
    Themenwechsel halb ankommen kann.
    """
    from app.ui.cursors import apply_default_cursor
    from app.ui.style import apply_style

    application.setStyle("Fusion")
    application.setPalette(build_palette(theme))
    apply_style(application, theme)
    # Der Zeiger gehört zum Aussehen wie die Farben. Er hing lange nur am
    # Viewport, und in den Panels stand der gewöhnliche Pfeil daneben — zwei
    # Programme in einem Fenster. Hier gesetzt, weil ein Themenwechsel die
    # einzige Gelegenheit ist, die *jedes* Fenster erreicht.
    for window in application.topLevelWidgets():
        apply_default_cursor(window)


def viewport_colours(theme: Theme) -> dict[str, str]:
    """Die Farben, die die 3D-Ansicht braucht — Hintergrundverlauf, Körper,
    Druckplatte.
    """
    colours = THEMES[theme]
    return {
        "bottom": colours["viewport_bottom"],
        "top": colours["viewport_top"],
        "object": colours["object"],
        "bed": colours["bed"],
        "bed_surface": colours["bed_surface"],
        "edge": colours["edge"],
    }


def relative_luminance(colour: str) -> float:
    """WCAG-Luminanz — die Grundlage der Kontrastprüfung in den Tests."""
    channels = []
    for value in (colour[1:3], colour[3:5], colour[5:7]):
        component = int(value, 16) / 255.0
        channels.append(
            component / 12.92 if component <= 0.03928 else ((component + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first: str, second: str) -> float:
    """Kontrast zwischen zwei Farben, 1 (keiner) bis 21 (schwarz auf weiß)."""
    lighter = max(relative_luminance(first), relative_luminance(second))
    darker = min(relative_luminance(first), relative_luminance(second))
    return (lighter + 0.05) / (darker + 0.05)


# Qt-Attribute für HiDPI. Gesetzt, bevor es die Anwendung gibt (§19.3).
def enable_hidpi() -> None:
    """HiDPI-Skalierung mit scharfen Pixmaps — muss vor QApplication laufen."""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
