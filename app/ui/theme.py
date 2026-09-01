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
#: 1,76 Unterschied zum Bernstein — deutlich zu sehen —, und die dunkle Schrift
#: darauf hält 4,50.
#:
#: Die letzte Stelle ist Absicht. Hier stand ``#c37210``, und damit hielt die
#: Schrift 4,466 — unter den 4,5, die dieselbe Suite an jeder anderen Textfläche
#: verlangt, und zwar auf dem lautesten Knopf der Anwendung. Ein Schritt heller
#: im Grün bringt 4,502; gekostet hat es 0,013 des Unterschieds zum Bernstein,
#: und mehr ist bei 4,5 Schriftkontrast nicht zu haben (gerechnet über den
#: ganzen Farbraum: 1,763 ist das Maximum).
_SELECTION_PRESSED = "#c37310"

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
        "start_card_line": "#7c8795",
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
        "start_card_line": "#7a838f",
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
        # **Der Körper stand in der Platte, nicht auf ihr** (B35). Gemessen am
        # 30.08.2026, Kontrast im hellen gegen das dunkle Thema:
        #
        # | | hell (vorher) | jetzt | dunkel |
        # |---|---|---|---|
        # | Körper / Plattenfläche | 2,05 | 3,36 | 7,50 |
        # | Körper / Plattenraster | 1,41 | 2,35 | 3,39 |
        # | Körper / Kante | 4,45 | 4,11 | 4,47 |
        #
        # **Die Kante war nicht die Ursache, und sie bleibt unangetastet.** Der
        # Befund nannte sie („im hellen Thema zu schwach"), gemessen stand sie
        # mit 4,45 gegen 4,47 in beiden Themen gleich gut da. Wer sie dunkler
        # gemacht hätte, hätte eine Zahl verbessert, die in Ordnung war,
        # während der Körper weiter in der Platte verschwindet.
        #
        # **Geändert hat sich vor allem die Platte**, nicht der Körper: Sie
        # rückt vom Körper weg und an den Bildgrund heran und hört damit
        # zugleich auf, das auffälligste Element im Bild zu sein. Der Körper
        # wird nur eine Spur dunkler.
        #
        # **Das dunkle Thema ist nicht erreichbar, und das ist kein Versäumnis.**
        # Dort ist der Körper hell und die Platte sehr dunkel — 7,50 Abstand.
        # Im hellen Thema liegt der Körper zwischen heller Platte und dunkler
        # Kante; beide Abstände lassen sich nicht zugleich groß machen.
        # Durchgerechnet über Körper, Fläche, Raster und Kante gemeinsam bleibt
        # bei „Fläche >= 4,0" keine Kombination übrig, die zugleich die vier
        # Zusagen aus ``test_the_viewport_follows_the_theme`` hält.
        #
        # **Ein erster Entwurf hellte Raster und Fläche gemeinsam auf** und
        # verlor dabei ihren gegenseitigen Abstand (1,02 statt der verlangten
        # 1,4) — ein Raster, das man auf seinem eigenen Grund nicht sieht.
        # Gefangen hat es derselbe Test, der die Zusage seit je hält.
        "object": "#78828e",
        "bed": "#bfcad8",
        # Zieht mit dem Hintergrund mit: Der abgedunkelte Verlauf war der
        # bisherigen Plattenfarbe auf 1,07 nahegekommen, und eine Druckplatte,
        # die man vom Nichts dahinter nicht unterscheidet, ist keine. Mit 1,21
        # bleibt sie darüber und tritt zugleich hinter den Körper zurück.
        "bed_surface": "#e5effb",
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


#: Welches Thema gerade gilt. Gesetzt von :func:`apply_theme`, gelesen von
#: allem, was eine Themenfarbe braucht, ohne ein Widget zu sein.
#:
#: **Ohne diesen Zustand blieb eine Farbe im hellen Thema falsch.** Der
#: Filamentwähler zeigt für „Ohne Filament" die Körperfarbe — er holte sie
#: fest aus dem dunklen Satz, mit der Begründung, ein Feld von vierzehn
#: Bildpunkten trage den Unterschied nicht. Gemessen sind es ``#7d8894``
#: gegen ``#b9c4d0``: zwei klar unterscheidbare Grautöne, und das Feld
#: verspricht in seiner Beschriftung „Farbe des Teils".
#:
#: Dieselbe Bauart wie die Anzeigeeinheit (``labels.display_unit``) und aus
#: demselben Grund: Wer die Farbe braucht, ist oft kein Widget und hat keinen
#: Weg zum Fenster — sie durch jeden Operationsdialog zu reichen, wäre der
#: teurere Weg zu derselben Auskunft.
_ACTIVE: Theme = "dark"


def current_theme() -> Theme:
    """Das Thema, das gerade gilt."""
    return _ACTIVE


def apply_theme(application: QApplication, theme: Theme) -> None:
    """Schaltet die ganze Anwendung um. Wirkt sofort.

    Palette und Stylesheet gehören zusammen: die Palette trägt die Farben, das
    Stylesheet die Form. Getrennt gesetzt wären sie zwei Wege, auf denen ein
    Themenwechsel halb ankommen kann.
    """
    from app.ui.cursors import apply_default_cursor
    from app.ui.style import apply_style

    global _ACTIVE
    _ACTIVE = theme
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


#: Die Ersatzfarbe eines Materialslots, dem niemand eine gegeben hat.
#:
#: Drei der vier Stellen, die Slots anlegen, lassen ``colour`` auf ``None``:
#: der Pinsel (§20), die Schrift und „Slot zuweisen" mit leerem Feld. Nur die
#: Texturzerlegung setzt echte Farben, denn sie liest sie aus dem Bild. Die
#: Ansicht nahm für einen Slot ohne Farbe die Körperfarbe — bei zwei bemalten
#: Slots waren das zwei gleiche Einträge in derselben Farbtabelle, und wer
#: zweifarbig bemalte, sah das Ergebnis zum ersten Mal im Slicer. Genau das,
#: was der Docstring von ``Viewport._slot_colours`` als behoben beschreibt.
#:
#: Die Farbe steht **nicht** im Dokument: keine Farbe zu haben ist ein
#: Zustand, den der Nutzer über „Slot zuweisen" auflöst, und eine geratene
#: Zahl in der Projektdatei wäre eine Behauptung. Hier ist sie eine Anzeige.
#:
#: **Eine Grauleiter, keine Buntpalette** (Entscheidung Robert, 26.08.2026 —
#: Konzept Filamente). Hier stand Okabe/Ito, und ihr erster Eintrag war ein
#: Orange (``#e69f00``), das von der Auswahlfarbe (``#f0a54a``) praktisch
#: nicht zu unterscheiden war — Kontrast 1,09, und die allererste Bemalung,
#: die je ein Kunde sah, sah aus wie eine Auswahl. Im Filament-Modell kommen
#: echte Farben vom Kunden (Farbwähler, Katalog); was hier steht, ist nur noch
#: der Stand **davor**: ein Filament, dem noch niemand eine Farbe gegeben hat,
#: zeigt sich grau.
#:
#: Grau, aber nicht **ein** Grau: Zwei farblose Filamente müssen im Bild
#: auseinander bleiben, sonst sieht der Kunde sein zweifarbiges Teil zum
#: ersten Mal im Slicer — der dokumentierte alte Fehler dieser Tabelle. Die
#: sieben Stufen sind deshalb eine Helligkeitsleiter: jedes Paar
#: unterscheidbar, alle fern der Auswahlfarbe und der Körperfarbe
#: (``#b9c4d0``), die häufigsten zwei maximal getrennt. Und die Farbe ist nie
#: die einzige Auskunft (Regel 18) — die Leiste nennt Name und Nummer daneben.
SLOT_COLOURS: Final = (
    "#8a9099",  # Mittelgrau — die erste Bemalung, deutlich unter der Körperhelligkeit
    "#414650",  # Dunkelgrau — maximal getrennt von der ersten
    "#6c727b",  # dazwischen
    "#2e323a",  # Anthrazit
    "#9da3ac",  # Hellgrau — noch klar unter der Körperfarbe
    "#575c65",  # dunkles Schiefergrau
    "#787e87",  # Steingrau
)


def slot_colour(index: int) -> str | None:
    """Welche Farbe ein Slot ohne eigene bekommt (siehe :data:`SLOT_COLOURS`).

    ``None`` für Slot 0: Er ist das unbemalte Teil, und welche Farbe das ist,
    weiß das Thema des Anrufers und nicht diese Tabelle. Über die Palette
    hinaus wird von vorn gezählt; ``MAX_SLOTS`` ist acht, die Palette reicht.
    """
    if index <= 0:
        return None
    return SLOT_COLOURS[(index - 1) % len(SLOT_COLOURS)]


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
