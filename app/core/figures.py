"""Die Abbildungen des Handbuchs (Bauplan §2.6, §37.2).

Ein Handbuch ohne Bilder erklärt einem Anfänger nichts. Wer zum ersten Mal
hört, dass „das Spiel aus dem Materialprofil kommt", braucht keinen zweiten
Satz dazu — er braucht eine Zeichnung, auf der ein Zapfen in einem Loch steckt
und der Spalt dazwischen bemaßt ist.

Drei Sorten Abbildung, und keine davon wird von Hand gepflegt:

* **Gezeichnet.** Fensteraufbau, Operationsstapel, Passungsspiel,
  Überhangwinkel. Dafür gibt es keinen Körper zum Rendern, also entstehen sie
  als Linien und Beschriftungen über :mod:`app.core.drawing`. Weil die
  Beschriftung Text bleibt, ist sie übersetzt und nicht in Pixel gebrannt.
* **Gerendert.** Bausteine und Op-Ergebnisse werden aus der echten Geometrie
  projiziert. Ein Bild einer Mutternfalle, das eine ältere Mutternfalle zeigt,
  wäre schlimmer als keins.
* **Aufgenommen.** Bildschirmfotos der Oberfläche, erzeugt von
  ``tools/make_figures.py`` in beiden Sprachen. Sie liegen als Dateien vor,
  weil ein Fenster im Handbuch nicht noch einmal geöffnet werden kann.

**Alt-Text ist Pflicht, nicht Zubehör.** Er steht in jedem Eintrag, und er
sagt, was das Bild zeigt — nicht, dass es eines gibt. Das trägt zwei Fälle:
den Leser, der die Abbildung nicht sehen kann, und den Rechner, auf dem die
Geometriepakete fehlen und deshalb nichts gerendert wird. In beiden Fällen
bleibt die Aussage erhalten (Regel 18).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from app.core import drawing
from app.core.drawing import Canvas, Theme
from app.core.log import get_logger
from app.i18n import SOURCE_LANGUAGE, TranslatableText, _

_log = get_logger(__name__)

if TYPE_CHECKING:
    # Wie in :mod:`app.core.drawing`: zur Laufzeit wird nichts davon importiert,
    # damit der Katalog auch ohne die Geometriepakete gelesen werden kann.
    import trimesh

    from app.core.scene import EvaluationResult

FigureKind = Literal["drawn", "rendered", "shot"]

#: Wo die Bildschirmfotos liegen. Je Sprache ein Ordner — im Bild steht Text,
#: und der wäre sonst in genau einer Sprache richtig.
IMAGE_ROOT: Final = Path(__file__).resolve().parent.parent / "images" / "manual"


@dataclass(frozen=True, slots=True)
class Figure:
    """Eine Abbildung des Handbuchs."""

    key: str
    alt: TranslatableText | str
    """Was das Bild zeigt, in einem Satz. Pflicht — siehe Modulkopf."""
    caption: TranslatableText | str = ""
    """Bildunterschrift. Darf leer bleiben, wenn der Alt-Text alles sagt."""
    kind: FigureKind = "drawn"
    build: Callable[[Theme], str] | None = None
    """Erzeugt das SVG. Bei ``shot`` leer — dort liegt eine Datei."""

    def path(self, language: str = SOURCE_LANGUAGE) -> Path:
        """Der Dateiort eines Bildschirmfotos."""
        return IMAGE_ROOT / language / f"{self.key}.png"

    def available(self, language: str = SOURCE_LANGUAGE) -> bool:
        """Ob diese Abbildung hier und jetzt entstehen kann.

        Gerenderte Bilder brauchen die Geometriepakete, aufgenommene eine
        Datei. Fehlt eines, ist das kein Fehler — das Handbuch zeigt dann den
        Alt-Text und bleibt vollständig lesbar.
        """
        if self.kind == "shot":
            return self.path(language).is_file()
        if self.kind == "rendered":
            return _geometry_available()
        return True


# --- gezeichnete Schemata ------------------------------------------------------------


def _window(theme: Theme) -> str:
    """Das Fensterschema aus §2.5 — drei Zonen, nicht sechs."""
    canvas = Canvas(600, 330, theme)
    colours = canvas.colours
    canvas.background()

    canvas.box(10, 10, 580, 26, fill=colours.fill)
    canvas.label(20, 28, str(_("Werkzeugleiste")), size=11)

    labels = (_("Objektbaum"), _("Parameter"), _("Verlauf"))
    for index, title in enumerate(labels):
        top = 46 + index * 62
        canvas.box(10, top, 150, 54, fill=colours.fill)
        canvas.label(20, top + 22, str(title), size=11, bold=True)
        for row in range(2):
            canvas.line(
                20,
                top + 34 + row * 10,
                120 - row * 24,
                top + 34 + row * 10,
                stroke=colours.muted,
                weight=2.0,
            )

    canvas.box(170, 46, 260, 202, stroke=colours.accent, weight=2.0)
    canvas.label(
        300, 140, str(_("Viewport")), anchor="middle", size=13, bold=True, colour=colours.accent
    )
    # Mittig wie das ``Viewport``-Wort darüber — beide teilen die x-Mitte.
    canvas.caption(300, 158, str(_("das Modell, immer sichtbar")), size=10, anchor="middle")

    canvas.box(440, 46, 150, 202, fill=colours.fill, dashed=True)
    canvas.label(515, 76, str(_("Chat")), anchor="middle", size=11, bold=True)
    canvas.label(515, 96, str(_("oder")), anchor="middle", size=10, colour=colours.muted)
    canvas.label(515, 116, str(_("Prüfbericht")), anchor="middle", size=11, bold=True)
    canvas.wrapped(
        515,
        146,
        str(_("Umschaltbar und ganz ausblendbar")),
        width=18,
        anchor="middle",
        colour=colours.muted,
    )

    # Die zweite Leiste, unter dem Modell. Sie fehlte hier, und der Text des
    # Kapitels nannte sie deshalb auch nicht — dabei liegen in ihr die
    # Werkzeuge, mit denen man hinsieht, und die zwei, die etwas ändern.
    #
    # **Ein Bild altert stumm.** „Bemalen" stand hier weiter, nachdem das
    # Werkzeug aus der Leiste gefallen war (Filament-Umbau, 26.08.2026) —
    # und keine Katalogprüfung hätte es gemeldet: Der Text wird **gerendert**
    # und nicht übersetzt. Wer ein Werkzeug hinzunimmt oder streicht, sieht
    # hier nach; die Reihenfolge ist die der Leiste.
    canvas.box(170, 254, 260, 24, fill=colours.fill)
    canvas.label(180, 270, str(_("Schnitt · Messen · Bewegen · Analyse · Trennen")), size=9)

    canvas.box(10, 288, 580, 26, fill=colours.fill)
    canvas.label(20, 306, str(_("Statusleiste: Maße · Auswahl · Fortschritt · Warnungen")), size=10)
    return canvas.svg()


def _stack(theme: Theme) -> str:
    """Der Operationsstapel: warum nachträgliches Ändern geht."""
    canvas = Canvas(600, 280, theme)
    colours = canvas.colours
    canvas.background()

    steps = (
        (_("Modell laden"), ""),
        (_("Reparieren"), str(_("3 Löcher geschlossen"))),
        (_("Bohrung Ø 4,2 mm"), str(_("bei x = 20 mm"))),
        (_("Auf das Bett"), ""),
    )
    for index, (title, note) in enumerate(steps):
        top = 22 + index * 52
        marked = index == 2
        canvas.box(
            20,
            top,
            250,
            40,
            stroke=colours.accent if marked else colours.ink,
            fill=colours.fill,
            weight=2.0 if marked else 1.4,
        )
        canvas.label(34, top + 18, str(title), size=11, bold=True)
        if note:
            canvas.caption(34, top + 32, note)
        if index < len(steps) - 1:
            canvas.arrow(145, top + 40, 145, top + 52, stroke=colours.muted)

    canvas.arrow(360, 148, 280, 148, stroke=colours.accent)
    canvas.label(370, 138, str(_("Doppelklick")), size=11, bold=True, colour=colours.accent)
    canvas.wrapped(
        370,
        154,
        str(_("öffnet den Schritt wieder — die Zahl ändern genügt")),
        width=26,
        colour=colours.ink,
    )

    canvas.line(20, 246, 580, 246, stroke=colours.muted, dashed=True)
    canvas.wrapped(
        20,
        264,
        str(_("Neu gerechnet wird nur, was unter dem geänderten Schritt hängt.")),
        width=70,
        colour=colours.muted,
    )
    return canvas.svg()


def _fit(theme: Theme) -> str:
    """Passungsspiel — die Zahl, die nicht eingetippt wird.

    Der Wert im Bild kommt aus dem Materialprofil und ist nicht hier
    eingetragen. Sonst stünde ausgerechnet auf der Abbildung, die erklärt, dass
    Toleranzen nicht abgetippt werden, eine abgetippte Toleranz — und die wäre
    beim ersten Nachschärfen der Startwerte falsch.
    """
    from app.core.knowledge import profiles
    from app.core.units import format_length

    canvas = Canvas(540, 268, theme)
    colours = canvas.colours
    canvas.background()

    material = profiles.material("petg")
    canvas.label(20, 26, str(_("Querschnitt: Zapfen in Bohrung")), size=11, bold=True)

    top, bottom = 78, 216
    # Das Material links und rechts, schraffiert — Schnittflächen sind
    # schraffiert, so liest sie jeder, der je eine Zeichnung gesehen hat.
    for left in (60, 280):
        canvas.hatched(left, top, 120, bottom - top)
        canvas.box(left, top, 120, bottom - top, stroke=colours.ink)
    canvas.caption(60, bottom + 20, str(_("Bauteil mit Bohrung, im Schnitt")))

    canvas.box(
        196, top + 16, 68, bottom - top - 16, fill=colours.fill, stroke=colours.ink, weight=1.8
    )
    canvas.label(230, 150, str(_("Zapfen")), anchor="middle", size=11)

    # Das Maß steht über den Blöcken: bei einem Spalt von sechzehn Pixeln ist
    # jede Beschriftung breiter als ihr Maß, und dort oben stört sie nichts.
    canvas.line(180, 58, 180, bottom, stroke=colours.accent, dashed=True, weight=1.0)
    canvas.line(196, 58, 196, bottom, stroke=colours.accent, dashed=True, weight=1.0)
    canvas.dimension(
        180,
        62,
        196,
        62,
        f"{_('Spiel')} {format_length(material.clearance)}",
        stroke=colours.accent,
    )

    canvas.wrapped(
        420,
        110,
        str(_("kommt aus dem Materialprofil, nicht aus dem Dialog")),
        width=20,
        colour=colours.ink,
    )
    canvas.wrapped(
        420,
        176,
        str(_("Kalibrieren ändert sie — auch für alte Projekte")),
        width=20,
        colour=colours.muted,
    )
    return canvas.svg()


def _overhang(theme: Theme) -> str:
    """Ab welchem Winkel Stützen nötig werden — gemessen gegen die Senkrechte.

    Der Winkel wird eingezeichnet und nicht nur beziffert. Die Verwechslung,
    gegen welche Richtung gemessen wird, macht jeder einmal — und eine Zahl
    ohne Bogen daneben lädt geradezu dazu ein.
    """
    canvas = Canvas(560, 260, theme)
    colours = canvas.colours
    canvas.background()
    canvas.label(20, 26, str(_("Überhang, gemessen gegen die Senkrechte")), size=11, bold=True)

    base_y = 186
    height = 74.0
    foot = 34.0

    for index, (angle, needs_support) in enumerate(((40, False), (65, True))):
        left = 46 + index * 268
        tone = colours.warn if needs_support else colours.accent
        lean = height * math.tan(math.radians(angle))

        # Das Druckbett unter beiden Körpern.
        canvas.line(
            left - 24, base_y, left + foot + lean + 24, base_y, stroke=colours.muted, weight=2.5
        )

        # Der Körper: unten schmal, oben um `lean` weiter — die rechte Kante ist
        # der Überhang.
        canvas.polygon(
            [
                (left, base_y),
                (left + foot, base_y),
                (left + foot + lean, base_y - height),
                (left, base_y - height),
            ],
            stroke=colours.ink,
            fill=colours.fill,
        )

        # Die Senkrechte, gegen die gemessen wird, und der Bogen dazwischen.
        canvas.line(
            left + foot,
            base_y,
            left + foot,
            base_y - height - 10,
            stroke=colours.muted,
            dashed=True,
            weight=1.0,
        )
        canvas.arc(left + foot, base_y, 30.0, float(angle), stroke=tone)
        canvas.label(left + foot + 12, base_y - 34, f"{angle}°", size=13, bold=True, colour=tone)

        mark = _("Stützen nötig") if needs_support else _("druckt frei")
        canvas.label(
            left + foot, base_y + 20, str(mark), anchor="middle", size=11, bold=True, colour=tone
        )

    canvas.wrapped(
        20,
        238,
        str(
            _(
                "Der Grenzwinkel steht im Druckerprofil — 45 Grad ist nur eine "
                "Faustregel. Der Überhangfächer misst ihn für den eigenen Drucker."
            )
        ),
        width=88,
        colour=colours.muted,
    )
    return canvas.svg()


def _elephant_foot(theme: Theme) -> str:
    """Warum die erste Schicht breiter ist als der Rest."""
    from app.core.knowledge import profiles
    from app.core.units import format_length

    canvas = Canvas(500, 234, theme)
    colours = canvas.colours
    canvas.background()
    canvas.label(20, 26, str(_("Die erste Schicht wird breiter gedrückt")), size=11, bold=True)

    base_y = 176
    canvas.line(30, base_y, 300, base_y, stroke=colours.muted, weight=2.5)
    canvas.caption(30, base_y + 20, str(_("Druckbett")))

    for index in range(7):
        top = base_y - 12 - index * 14
        widen = 9 if index == 0 else 0
        canvas.box(
            120 - widen,
            top,
            90 + widen * 2,
            12,
            fill=colours.fill,
            stroke=colours.warn if index == 0 else colours.ink,
            weight=1.8 if index == 0 else 1.0,
            radius=1.0,
        )

    foot = profiles.material("petg").elephant_foot
    canvas.line(111, base_y - 12, 111, 68, stroke=colours.warn, dashed=True, weight=1.0)
    canvas.line(120, base_y - 12, 120, 68, stroke=colours.warn, dashed=True, weight=1.0)
    canvas.dimension(
        111,
        72,
        120,
        72,
        f"{_('Elefantenfuß')} {format_length(foot)}",
        stroke=colours.warn,
    )
    canvas.wrapped(
        330,
        120,
        str(_("Unten ist das Teil breiter, als es gezeichnet wurde.")),
        width=20,
        colour=colours.ink,
    )
    return canvas.svg()


def _wall(theme: Theme) -> str:
    """Die Mindestwandstärke, und woher sie kommt."""
    from app.core.knowledge import profiles
    from app.core.units import format_length

    canvas = Canvas(500, 224, theme)
    colours = canvas.colours
    canvas.background()
    canvas.label(20, 26, str(_("Mindestwandstärke: zwei Bahnen nebeneinander")), size=11, bold=True)

    printer = profiles.printer("centauri-carbon-2")
    top, height = 74, 100
    canvas.box(150, top, 30, height, fill=colours.fill, stroke=colours.ink)
    canvas.line(165, top, 165, top + height, stroke=colours.muted, dashed=True, weight=1.0)
    canvas.caption(126, top + height + 24, str(_("die Wand im Schnitt")))

    canvas.dimension(
        150,
        60,
        180,
        60,
        format_length(printer.extrusion_width * 2),
        stroke=colours.accent,
    )
    canvas.wrapped(
        236,
        84,
        str(
            _(
                "Eine einzelne Bahn trägt nichts und reißt beim Entfernen der "
                "Stützen. Zwei sind das Mindeste, das hält."
            )
        ),
        width=30,
        colour=colours.ink,
    )
    canvas.wrapped(
        236,
        158,
        f"{_('Bahnbreite und Düse stehen im Druckerprofil')} "
        f"({format_length(printer.nozzle_diameter)} {_('Düse')}).",
        width=30,
        colour=colours.muted,
    )
    return canvas.svg()


def _texture(theme: Theme) -> str:
    """Warum ein Rändel umlaufen muss und nicht aufliegen darf."""
    canvas = Canvas(560, 240, theme)
    colours = canvas.colours
    canvas.background()
    canvas.label(20, 26, str(_("Ein Muster auf einem runden Griff")), size=11, bold=True)

    # Links: flach aufgelegt — das Feld trifft den Kreis nur in der Mitte.
    canvas.caption(58, 62, str(_("flach")))
    canvas.circle(110, 130, 46, fill=colours.fill, stroke=colours.ink)
    canvas.line(64, 78, 156, 78, stroke=colours.warn, weight=2.0)
    canvas.caption(46, 206, str(_("liegt auf, trägt nur in der Mitte")))

    # Rechts: umlaufend — kurze Striche rund um den Kreis.
    canvas.caption(392, 62, str(_("umlaufend")))
    canvas.circle(410, 130, 46, fill=colours.fill, stroke=colours.ink)
    for index in range(16):
        angle = index * 2.0 * math.pi / 16.0
        inner_x = 410 + 46 * math.cos(angle)
        inner_y = 130 + 46 * math.sin(angle)
        outer_x = 410 + 54 * math.cos(angle)
        outer_y = 130 + 54 * math.sin(angle)
        canvas.line(inner_x, inner_y, outer_x, outer_y, stroke=colours.accent, weight=2.0)
    canvas.caption(360, 206, str(_("greift rundherum")))

    canvas.wrapped(
        190,
        104,
        str(
            _(
                "Der Schalter „Auflegen“ entscheidet darüber. Der Durchmesser "
                "kommt aus der angeklickten Fläche."
            )
        ),
        width=24,
        colour=colours.muted,
    )
    return canvas.svg()


#: Wie groß eine Musterkachel gezeichnet wird, und mit welcher Teilung. Die
#: Werte sind Zeichenmaße, keine Millimeter: gezeigt wird die *Form* des
#: Musters, und die hängt an der Teilung, nicht an der Größe des Feldes.
TILE_SIZE: Final = 120.0
TILE_PITCH: Final = 16.0


def texture_tile(pattern: str, theme: Theme, size: float = TILE_SIZE) -> str:
    """Eine Musterkachel, gezeichnet aus **denselben** Polygonen, aus denen der
    Körper entsteht (§25).

    Ein von Hand gemaltes Vorschaubild wäre eine zweite Wahrheit: es zeigte,
    was jemand für das Muster hielt, als er es malte. Hier kommt die Zeichnung
    aus :func:`app.core.geom.texture_ops.pattern_shapes` — was im Bild steht,
    ist das, was gerechnet wird.

    Ohne die Geometriepakete gibt es kein Bild, sondern einen leeren Rahmen;
    der Alt-Text trägt die Aussage dann allein (siehe Modulkopf).
    """
    canvas = Canvas(size, size, theme)
    colours = canvas.colours
    canvas.background()
    try:
        from app.core.geom.texture_ops import pattern_shapes

        shapes = pattern_shapes(pattern, size, size, TILE_PITCH, seed=1)
    except Exception:  # pragma: no cover — ohne shapely/trimesh bleibt der Rahmen
        shapes = []

    for shape in shapes:
        for ring in _rings_of(shape):
            # Die Polygone liegen um den Ursprung; die Zeichenfläche zählt von
            # links oben. Y wird gespiegelt, sonst stünde ein Muster im Bild
            # auf dem Kopf — bei Rippen fällt das nicht auf, bei Waben schon.
            points = [(x + size / 2.0, size / 2.0 - y) for x, y in ring]
            canvas.polygon(points, fill=colours.accent, stroke=colours.ink, weight=0.8)
    canvas.box(0.0, 0.0, size, size, stroke=colours.muted)
    return canvas.svg()


def _rings_of(shape: object) -> list[list[tuple[float, float]]]:
    """Die äußeren Ringe eines Shapely-Gebildes, ohne Shapely zu importieren."""
    geoms = getattr(shape, "geoms", None)
    if geoms is not None:
        return [ring for part in geoms for ring in _rings_of(part)]
    exterior = getattr(shape, "exterior", None)
    if exterior is None:
        return []
    return [[(float(x), float(y)) for x, y in exterior.coords]]


def _textures(theme: Theme) -> str:
    """Alle acht Muster nebeneinander — die Antwort auf „welches denn?"."""
    from app.core.geom.texture_ops import PATTERNS

    columns = 4
    tile = 96.0
    gap = 14.0
    label_height = 20.0
    rows = (len(PATTERNS) + columns - 1) // columns
    canvas = Canvas(
        columns * tile + (columns + 1) * gap,
        rows * (tile + label_height) + (rows + 1) * gap,
        theme,
    )
    colours = canvas.colours
    canvas.background()

    for index, pattern in enumerate(PATTERNS):
        left = gap + (index % columns) * (tile + gap)
        top = gap + (index // columns) * (tile + label_height + gap)
        try:
            from app.core.geom.texture_ops import pattern_shapes

            shapes = pattern_shapes(pattern, tile, tile, TILE_PITCH * tile / TILE_SIZE, seed=1)
        except Exception:  # pragma: no cover — siehe :func:`texture_tile`
            shapes = []
        for shape in shapes:
            for ring in _rings_of(shape):
                points = [(left + x + tile / 2.0, top + tile / 2.0 - y) for x, y in ring]
                canvas.polygon(points, fill=colours.accent, stroke=colours.ink, weight=0.7)
        canvas.box(left, top, tile, tile, stroke=colours.muted)
        canvas.caption(left, top + tile + 14.0, str(TEXTURE_NAMES[pattern]))
    return canvas.svg()


#: Wie die acht Muster heißen. Hier, nicht in der Oberfläche: das Handbuch
#: beschriftet damit seine Abbildung, der Dialog seine Auswahl, und zwei
#: Listen liefen erfahrungsgemäß auseinander.
TEXTURE_NAMES: Final[dict[str, TranslatableText]] = {
    "rib": _("Rippe"),
    "wave": _("Welle"),
    "knurl_straight": _("Rändel gerade"),
    "knurl_diamond": _("Rändel gekreuzt"),
    "hexagon": _("Wabe"),
    "dimple": _("Noppen"),
    "voronoi": _("Voronoi"),
    "noise": _("Rauschen"),
}


def _ways(theme: Theme) -> str:
    """Die vier Hauptwege aus §2.2, als Ablauf.

    Der vierte fehlte hier, während er im Handbuchkapitel daneben längst
    beschrieben stand — die Abbildung zeigte drei, der Text vier. Die Höhe
    folgt der Zahl der Zeilen und ist nicht mehr fest: Eine Zeile dazu und die
    letzte stünde sonst außerhalb des Bildes.
    """
    rows = 4
    canvas = Canvas(620, 30 + rows * 76 - 16, theme)
    colours = canvas.colours
    canvas.background()

    ways = (
        (
            _("Fremdes Modell anpassen"),
            (_("einlesen"), _("reparieren"), _("bohren"), _("exportieren")),
        ),
        (
            _("Selbst konstruieren"),
            (_("Maße benennen"), _("Grundkörper · Skizze"), _("Bausteine"), _("exportieren")),
        ),
        (
            _("Erzeugtes aufbereiten"),
            (_("erzeugen"), _("Reparaturkette"), _("prüfen"), _("exportieren")),
        ),
        (
            _("Organisch formen"),
            (_("Grundkörper"), _("verschmelzen"), _("ausformen"), _("exportieren")),
        ),
    )
    assert len(ways) == rows, "die Höhe des Bildes folgt der Zahl der Zeilen"
    for row, (title, steps) in enumerate(ways):
        top = 30 + row * 76
        canvas.label(20, top, str(title), size=11, bold=True)
        for index, step in enumerate(steps):
            left = 20 + index * 148
            canvas.box(left, top + 10, 118, 34, fill=colours.fill)
            canvas.label(left + 59, top + 32, str(step), anchor="middle", size=10)
            if index < len(steps) - 1:
                canvas.arrow(left + 118, top + 27, left + 148, top + 27, stroke=colours.muted)
    return canvas.svg()


def _sketch_editor(theme: Theme) -> str:
    """Der Skizzenmodus: Werkzeuge, Zeichenfläche, Bedingungen, Freiheitsgrade.

    Ein Schema und kein Bildschirmfoto, aus demselben Grund wie beim Fenster:
    die Beschriftung bleibt Text, also übersetzt, und die Zeichnung veraltet
    nicht mit dem nächsten Symbolsatz. Die Kürzel stehen dran, weil sie im
    Bild dieselben sind wie in der Anwendung — sie kommen aus
    ``app/ui/sketch_editor.py`` und sind hier nachgetragen, nicht erfunden.
    """
    canvas = Canvas(620, 340, theme)
    colours = canvas.colours
    canvas.background()

    # Die Werkzeugzeile — ein Schema, keine vollständige Liste. Nicht im Bild
    # stehen Auswählen (Esc), Punkt (P) und Verlängern (neben Trimmen); sie
    # stehen im Handbuchtext daneben, der alle Tasten nennt. Sonst würde die
    # Zeile zur Aufzählung, und das Bild soll zeigen, wo die Werkzeuge liegen,
    # nicht welche es gibt.
    #
    # Hier stand „Sechs von acht Werkzeugen" und darunter zwei Weggelassene.
    # Die Rechnung ging nie auf: ``sketch_editor.TOOL_KEYS`` führt sieben
    # Einträge, dazu kommen Verlängern und der Sammelknopf für Grundformen.
    # Übergangen war ausgerechnet der Punkt — er fehlte im Bild **und** in der
    # Aufzählung dessen, was fehlt. Deshalb steht hier keine Zahl mehr: Sie
    # altert mit dem nächsten Werkzeug, die Aufzählung nicht.
    canvas.box(10, 10, 600, 32, fill=colours.fill)
    for index, (name, key) in enumerate(
        ((_("Linie"), "L"), (_("Kreis"), "C"), (_("Bogen"), "A"), (_("Spline"), "S"))
    ):
        left = 20 + index * 92
        canvas.box(left, 16, 84, 20, stroke=colours.muted, radius=2.0)
        canvas.label(left + 8, 31, str(name), size=10)
        canvas.label(left + 76, 31, key, anchor="end", size=10, bold=True, colour=colours.muted)
    canvas.box(388, 16, 96, 20, stroke=colours.muted, radius=2.0)
    canvas.label(396, 31, str(_("Grundform")), size=10)
    canvas.box(492, 16, 108, 20, stroke=colours.muted, radius=2.0)
    canvas.label(500, 31, str(_("Trimmen · Versetzen")), size=10)

    # Die Ebene gehört vor das Zeichnen: sie entscheidet, wohin extrudiert
    # wird — und wie die Schichten zur Zeichnung liegen.
    canvas.box(10, 50, 168, 22, fill=colours.fill, radius=2.0)
    canvas.label(20, 65, str(_("Draufsicht (XY) — liegend")), size=10, bold=True)
    canvas.caption(
        188, 65, str(_("Schichten liegen parallel zur Zeichnung — sie wächst nach oben heraus."))
    )

    # Die Zeichenfläche mit Raster.
    canvas.box(10, 82, 424, 208, fill=colours.paper)
    for step in range(1, 11):
        x = 10 + step * 38
        canvas.line(x, 82, x, 290, stroke=colours.muted, weight=0.4)
    for step in range(1, 6):
        y = 82 + step * 34
        canvas.line(10, y, 434, y, stroke=colours.muted, weight=0.4)

    # Der Rand des Bauraums, wie ihn die Zeichenfläche selbst zeigt: die
    # früheste Stelle, an der ein zu großes Teil auffällt.
    canvas.box(22, 94, 400, 184, stroke=colours.muted, dashed=True, weight=1.0, radius=0.0)
    canvas.caption(28, 110, str(_("Rand des Bauraums")))

    # Der Umriss: das Rechteck der Grundform, mit einem Kreis darin. Die Maße
    # sind die Vorgaben des Grundform-Menüs, nicht erfundene Zahlen.
    canvas.polygon(
        [(80, 140), (300, 140), (300, 200), (80, 200)], stroke=colours.ink, fill=colours.fill
    )
    canvas.circle(250, 170, 20, stroke=colours.ink, fill=colours.paper)
    canvas.tick(80, 210)
    canvas.tick(300, 210)
    canvas.dimension(80, 224, 300, 224, "40 mm", stroke=colours.accent)
    canvas.label(312, 144, str(_("gefangen")), size=10, colour=colours.accent)
    canvas.circle(300, 140, 5, stroke=colours.accent, weight=2.0)

    # Die Bedingungsliste. Die Nummern in Klammern sind die Punkte, die eine
    # Bedingung hält — überfahren lässt sie in der Zeichnung aufleuchten.
    canvas.box(444, 82, 166, 208, fill=colours.fill)
    canvas.label(454, 100, str(_("Bedingungen")), size=11, bold=True)
    entries = (
        (_("Waagerecht"), "(0, 1)"),
        (_("Rechtwinklig"), "(1, 2)"),
        (_("Abstand 40 mm"), "(0, 1)"),
        (_("Deckung"), "(3, 4)"),
        (_("Tangential"), "(4, 5)"),
    )
    for index, (kind, targets) in enumerate(entries):
        top = 120 + index * 24
        canvas.line(454, top + 4, 600, top + 4, stroke=colours.muted, weight=0.5)
        canvas.label(454, top, str(kind), size=10)
        canvas.label(600, top, targets, anchor="end", size=10, colour=colours.muted)
    canvas.caption(454, 276, str(_("Entf entfernt die gewählte.")))

    # Die Statuszeile — die eigentliche Auskunft des Editors.
    canvas.box(10, 300, 600, 30, fill=colours.fill)
    canvas.label(
        20, 320, str(_("Bestimmt — alle Freiheitsgrade sind vergeben.")), size=11, bold=True
    )
    return canvas.svg()


def _sketch_uses(theme: Theme) -> str:
    """Ein Umriss, drei Arten Körper — und die Wahl fällt am Ende.

    Der Grund für dieses Bild steht in §2.2, Weg 2: die Entscheidung, was aus
    einer Zeichnung wird, fällt bei „Fertig" und nicht vorab in einem Menü.
    Wer sie vorab treffen soll, muss wissen, was zur Auswahl steht — und fünf
    Menüeinträge sagen das nicht.
    """
    canvas = Canvas(620, 320, theme)
    colours = canvas.colours
    canvas.background()

    canvas.label(20, 26, str(_("Derselbe Umriss, drei Arten")), size=11, bold=True)

    # Der Umriss links, in derselben Form wie im Editorschema — und wirklich
    # bemaßt, weil die Unterschrift das behauptet.
    canvas.polygon(
        [(30, 108), (150, 108), (150, 168), (30, 168)], stroke=colours.ink, fill=colours.fill
    )
    canvas.circle(120, 138, 14, stroke=colours.ink, fill=colours.paper)
    canvas.tick(30, 178)
    canvas.tick(150, 178)
    canvas.dimension(30, 190, 150, 190, "40 mm", stroke=colours.accent)
    canvas.caption(30, 214, str(_("bemaßt und bestimmt")))
    canvas.arrow(162, 138, 196, 138, stroke=colours.accent)

    # Drei Zeilen und nicht drei Spalten: die Titel kommen aus dem Register und
    # sind Sätze, keine Wörter — nebeneinander lief der dritte aus dem Bild.
    rows = (
        (60.0, _("Grundform extrudieren"), _("gerade nach oben")),
        (140.0, _("Rotationskörper aufziehen"), _("um die senkrechte Achse")),
        (220.0, _("Entlang eines Bogens führen"), _("Rohrbogen in einem Schritt")),
    )
    for top, title, note in rows:
        canvas.label(350, top + 24, str(title), size=11, bold=True)
        canvas.caption(350, top + 40, str(note))

    # Extrudiert: dieselbe Fläche, nach hinten oben versetzt und verbunden.
    depth = 14.0
    left, top = 224.0, 66.0
    canvas.polygon(
        [(left, top + depth), (left + 76, top + depth), (left + 76, top + 44), (left, top + 44)],
        stroke=colours.ink,
        fill=colours.fill,
    )
    canvas.polygon(
        [
            (left + depth, top),
            (left + 76 + depth, top),
            (left + 76 + depth, top + 44 - depth),
            (left + depth, top + 44 - depth),
        ],
        stroke=colours.muted,
    )
    for corner_x, corner_y in (
        (left, top + depth),
        (left + 76, top + depth),
        (left + 76, top + 44),
    ):
        canvas.line(
            corner_x, corner_y, corner_x + depth, corner_y - depth, stroke=colours.muted, weight=1.0
        )

    # Gedreht: der Querschnitt links und rechts der Achse, Drehpfeil darüber.
    axis_x = 262.0
    canvas.line(axis_x, 146, axis_x, 210, stroke=colours.muted, dashed=True, weight=1.0)
    for side in (-1.0, 1.0):
        near = axis_x + side * 38
        far = axis_x + side * 16
        canvas.polygon(
            [(near, 166), (far, 166), (far, 206), (near, 206)],
            stroke=colours.ink,
            fill=colours.fill,
        )
    # Der Drehpfeil bleibt über den Querschnitten: quer durch einen von ihnen
    # hindurch sah er aus wie eine Kante des Körpers.
    canvas.arc(axis_x, 150, 14.0, 150.0, stroke=colours.accent)

    # Geführt: ein Band entlang eines Viertelbogens, an beiden Enden geschlossen.
    pivot_x, pivot_y = 232.0, 284.0
    canvas.arc(pivot_x, pivot_y, 56.0, 90.0, stroke=colours.ink)
    canvas.arc(pivot_x, pivot_y, 34.0, 90.0, stroke=colours.ink)
    canvas.line(pivot_x + 34, pivot_y, pivot_x + 56, pivot_y, stroke=colours.ink)
    canvas.line(pivot_x, pivot_y - 56, pivot_x, pivot_y - 34, stroke=colours.ink)

    canvas.wrapped(
        20,
        258,
        str(
            _(
                "Dazu Tasche schneiden und zwischen zwei Umrissen aufspannen. "
                "Gewählt wird bei „Fertig“, mit der Zeichnung vor Augen — und "
                "„Zurück zum Zeichnen“ wirft nichts weg."
            )
        ),
        width=44,
        colour=colours.muted,
    )
    return canvas.svg()


def _split(theme: Theme) -> str:
    """Zu groß für das Bett — teilen und verstiften."""
    canvas = Canvas(560, 230, theme)
    colours = canvas.colours
    canvas.background()

    canvas.label(20, 24, str(_("Zu groß für das Druckbett")), size=11, bold=True)
    canvas.box(20, 40, 170, 120, stroke=colours.muted, dashed=True)
    canvas.caption(20, 176, str(_("Druckbett von oben")))
    canvas.box(50, 72, 190, 56, stroke=colours.warn, fill=colours.fill, weight=2.0)
    canvas.label(120, 105, str(_("Objekt")), anchor="middle", size=11)
    # Der Teil, der über den Rand hinausgeht, wird schraffiert und nicht nur
    # rot umrandet — Regel 18 gilt auch für eine Zeichnung im Handbuch.
    canvas.hatched(190, 74, 48, 52, angle=-45)
    canvas.arrow(214, 60, 214, 72, stroke=colours.warn)
    canvas.label(238, 56, str(_("passt nicht")), size=10, colour=colours.warn)

    canvas.arrow(252, 100, 288, 100, stroke=colours.muted, weight=2.0)

    canvas.label(300, 24, str(_("Automatisch geteilt")), size=11, bold=True)
    canvas.box(300, 40, 170, 120, stroke=colours.muted, dashed=True)
    for index in range(2):
        left = 312 + index * 84
        canvas.box(left, 72, 76, 56, stroke=colours.accent, fill=colours.fill)
    canvas.circle(392, 88, 4, fill=colours.accent, stroke=colours.accent)
    canvas.circle(392, 112, 4, fill=colours.accent, stroke=colours.accent)
    canvas.caption(300, 176, str(_("zwei Passstifte je Schnittfläche")))
    canvas.wrapped(
        20,
        206,
        str(
            _(
                "Die Trennebene wird gesucht, nicht geraten — und "
                "jeder Schnitt bleibt eine Zahl, die man ändern kann."
            )
        ),
        width=76,
        colour=colours.muted,
    )
    return canvas.svg()


def _layers(theme: Theme) -> str:
    """Was die Schichtanalyse findet — und was sie nicht tut."""
    canvas = Canvas(560, 240, theme)
    colours = canvas.colours
    canvas.background()
    canvas.label(20, 26, str(_("Was die Schichtanalyse sieht")), size=11, bold=True)

    base_y = 170
    canvas.line(20, base_y, 360, base_y, stroke=colours.muted, weight=2.5)
    canvas.box(40, base_y - 90, 40, 90, fill=colours.fill, stroke=colours.ink)
    canvas.box(200, base_y - 90, 40, 90, fill=colours.fill, stroke=colours.ink)
    canvas.box(40, base_y - 108, 200, 18, fill=colours.fill, stroke=colours.ink)
    canvas.dimension(
        80, base_y - 118, 200, base_y - 118, str(_("Spannweite")), stroke=colours.accent
    )

    canvas.box(280, base_y - 60, 34, 20, fill=colours.fill, stroke=colours.warn, weight=2.0)
    canvas.line(297, base_y - 40, 297, base_y, stroke=colours.warn, dashed=True, weight=1.0)
    canvas.wrapped(
        280, base_y + 20, str(_("Insel — hängt in der Luft")), width=16, colour=colours.warn
    )

    canvas.wrapped(
        390,
        70,
        str(_("Solidon sucht und bewertet: Inseln, Spannweiten, dünne Stellen, die beste Lage.")),
        width=22,
        colour=colours.ink,
    )
    canvas.wrapped(
        390,
        150,
        str(_("Die Druckdatei schreibt weiterhin der Slicer.")),
        width=22,
        colour=colours.muted,
    )
    return canvas.svg()


# --- gerenderte Körper ---------------------------------------------------------------


def _part(
    name: str, size: int = 190, *, around: float = -35.0, down: float = 25.0
) -> Callable[[Theme], str]:
    """Einen Baustein aus dem Register rendern — dieselbe Quelle wie der Katalog.

    Der Blickwinkel steht je Baustein und nicht global: was erklärt werden
    soll, ist bei einer Mutternfalle das Sechseck und bei einer Rastnase der
    federnde Arm, und die beiden liegen nicht in derselben Richtung.
    """

    def build(theme: Theme) -> str:
        from app.core.bootstrap import load_operations
        from app.core.knowledge.parts import preview
        from app.core.knowledge.parts.registry import PARTS

        load_operations()
        return preview.render(
            PARTS.get(name), size=size, theme=theme, edges=True, around=around, down=down
        ).svg

    return build


def _drilled(theme: Theme) -> str:
    """Eine Platte vor und nach einer Bohrung — beides über die echte Op.

    Nicht mit ``trimesh`` zusammengesetzt, obwohl das kürzer wäre: Geometrie
    entsteht in einer Operation und sonst nirgends (Regel 2). Der Nebeneffekt
    ist, dass dieses Bild zeigt, was ``drill_hole`` heute tut, und nicht, was
    es einmal tat.
    """
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import new_project

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Grundkörper",
        [OperationDraft(op="create_box", params={"width": 60.0, "depth": 40.0, "height": 8.0})],
    )
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    before = evaluate(project.document, profile=profile)

    history.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 8.0, "x": 0.0, "y": 0.0, "z": 8.0, "axis": "z"},
            )
        ],
    )
    after = evaluate(project.document, profile=profile)

    tone = drawing.palette(theme).solid
    return drawing.side_by_side(
        drawing.project(_first_mesh(before), 190, tone, theme=theme, background=True, edges=True),
        drawing.project(_first_mesh(after), 190, tone, theme=theme, background=True, edges=True),
        theme=theme,
        labels=(str(_("vorher")), str(_("nachher: Bohrung Ø 8 mm"))),
    )


def _first_mesh(result: EvaluationResult) -> trimesh.Trimesh:
    """Das Netz des ersten Objekts einer Auswertung."""
    from app.core.geom.mesh import as_mesh_data

    first = next(iter(result.scene.objects.values()))
    return as_mesh_data(first.mesh).raw


def _geometry_available() -> bool:
    """Ob die Geometriepakete da sind. Ohne sie bleibt es beim Alt-Text."""
    try:
        # Nur nachsehen, ob sie da sind — deshalb ohne die üblichen Kurznamen.
        import numpy  # noqa: F401, ICN001
        import trimesh  # noqa: F401
    except ImportError:
        return False
    return True


# --- der Katalog ---------------------------------------------------------------------


def _parameter_field(theme: Theme) -> str:
    """Der ``fx``-Knopf neben einem Zahlenfeld, in beiden Zuständen.

    Das Kapitel „Parameter und Ausdrücke" erklärt in Worten, was ein Bild in
    einem Blick zeigt: dass neben jedem Maß ein Knopf steht, der das Feld
    umschaltet. Wer den Knopf nie gesehen hat, sucht ihn nach dieser
    Beschreibung trotzdem — er ist zwei Zeichen breit und steht am Rand.

    Gezeichnet statt aufgenommen, aus demselben Grund wie beim Fenster: Die
    Beschriftung bleibt Text und damit übersetzt, und ein Bildschirmfoto
    veraltet mit dem nächsten Symbolsatz.
    """
    canvas = Canvas(620, 232, theme)
    colours = canvas.colours
    canvas.background()

    for oben, titel, wert, aktiv, satz in (
        (
            28,
            _("Aus: eine Zahl"),
            "70,00 mm",
            False,
            _("Drehknöpfe, Grenzen und Einheit — wie jedes andere Maß."),
        ),
        (
            124,
            _("An: ein Ausdruck"),
            "=@breite/2",
            True,
            _("Der Wert folgt dem Parameter, auch wenn der sich ändert."),
        ),
    ):
        canvas.label(20, oben, str(titel), size=11, bold=True, colour=colours.muted)

        # Das Zahlenfeld. Der Rahmen ist derselbe wie in der Anwendung: ein
        # Kasten mit Text links und den Drehknöpfen am rechten Rand.
        canvas.box(20, oben + 12, 168, 30, stroke=colours.muted, fill=colours.paper)
        canvas.label(32, oben + 32, wert, size=12)
        if not aktiv:
            canvas.label(178, oben + 26, "▲", anchor="end", size=8, colour=colours.muted)
            canvas.label(178, oben + 38, "▼", anchor="end", size=8, colour=colours.muted)

        # Der Knopf. Gefüllt heißt eingeschaltet — dazu die zweite Kodierung,
        # die Regel 18 verlangt: der Rahmen wird kräftiger, nicht nur bunter.
        canvas.box(
            196,
            oben + 12,
            36,
            30,
            stroke=colours.accent if aktiv else colours.muted,
            fill=colours.fill if aktiv else colours.paper,
            weight=2.0 if aktiv else 1.4,
        )
        canvas.label(
            214,
            oben + 32,
            "fx",
            anchor="middle",
            size=12,
            bold=aktiv,
            colour=colours.accent if aktiv else colours.muted,
        )
        canvas.caption(248, oben + 32, str(satz))

    # Was dabei herauskommt — die Rechnung, die der Text beschreibt.
    canvas.line(20, 196, 600, 196, stroke=colours.muted, dashed=True)
    canvas.label(
        20,
        216,
        str(_("Bei breite = 70 mm steht im Feld 35,00 mm — gerechnet, nicht getippt.")),
        size=11,
    )
    return canvas.svg()


FIGURES: Final[tuple[Figure, ...]] = (
    Figure(
        key="window",
        alt=_(
            "Das Fenster: oben die Werkzeugleiste, links Objektbaum, Parameter und "
            "Verlauf untereinander, in der Mitte der Viewport mit dem Modell und "
            "darunter die Werkzeugzeile, rechts wahlweise Chat oder Prüfbericht, unten "
            "die Statusleiste."
        ),
        caption=_("Drei Zonen, keine Betriebsarten. Rechts lässt sich ganz ausblenden."),
        build=_window,
    ),
    Figure(
        key="stack",
        alt=_(
            "Vier Schritte untereinander — Modell laden, Reparieren, Bohrung Ø 4,2 mm, "
            "Auf das Bett. Ein Pfeil zeigt auf den dritten Schritt: ein Doppelklick "
            "öffnet ihn wieder, und nur die Schritte darunter werden neu gerechnet."
        ),
        caption=_("Jeder Schritt bleibt eine Zahl — auch morgen noch."),
        build=_stack,
    ),
    Figure(
        key="texture",
        alt=_(
            "Zwei Kreise nebeneinander. Links liegt ein gerader Strich oben auf dem "
            "Kreis auf und berührt ihn nur in der Mitte; rechts stehen kurze Striche "
            "rundherum vom Rand ab."
        ),
        caption=_("Ein Rändel gehört um den Griff, nicht als Fleck darauf."),
        build=_texture,
    ),
    Figure(
        key="textures",
        alt=_(
            "Acht Musterkacheln in zwei Reihen: Rippe als parallele Streifen, Welle "
            "als wellige Streifen, Rändel gerade und gekreuzt als schräge Streifen "
            "beziehungsweise Rauten, Wabe als Sechsecke, Noppen als Punktraster, "
            "Voronoi als unregelmäßige Zellen und Rauschen als verstreute Flecken."
        ),
        caption=_("Alle acht Muster, gezeichnet aus denselben Umrissen, die gedruckt werden."),
        build=_textures,
    ),
    Figure(
        key="ways",
        alt=_(
            "Drei Abläufe untereinander: ein fremdes Modell anpassen (einlesen, "
            "reparieren, bohren, exportieren), selbst konstruieren (Maße benennen, "
            "Grundkörper oder Skizze, Bausteine, exportieren) und Erzeugtes aufbereiten "
            "(erzeugen, Reparaturkette, prüfen, exportieren)."
        ),
        caption=_("Zu jedem Weg liegt ein Beispielprojekt auf dem Startbildschirm."),
        build=_ways,
    ),
    Figure(
        key="sketch-editor",
        alt=_(
            "Der Skizzenmodus: oben die Zeichenwerkzeuge mit ihren Kürzeln — Linie L, "
            "Kreis C, Bogen A, Spline S —, darunter die Ebenenwahl mit dem Hinweis, wie "
            "die Schichten dazu liegen. In der Zeichenfläche ein bemaßtes Rechteck von "
            "40 mm mit einem Kreis darin, der Rand des Bauraums gestrichelt, ein "
            "gefangener Punkt markiert. Rechts die Liste der Bedingungen — waagerecht, "
            "rechtwinklig, Abstand, Deckung, tangential — mit den Punkten, die jede "
            "hält. Unten die Statuszeile: bestimmt, alle Freiheitsgrade sind vergeben."
        ),
        caption=_(
            "Die Statuszeile ist die eigentliche Auskunft: was noch frei ist, wandert "
            "beim nächsten Zug."
        ),
        build=_sketch_editor,
    ),
    Figure(
        key="parameter-field",
        alt=_(
            "Zweimal dasselbe Zahlenfeld nebeneinander. Oben steht darin „70,00 mm“ "
            "mit Drehknöpfen am Rand, daneben ein blasser Knopf „fx“. Unten steht im "
            "Feld der Ausdruck „=@breite/2“, und der Knopf „fx“ ist eingeschaltet — "
            "kräftiger Rahmen, farbige Schrift. Darunter die Rechnung: bei einer "
            "Breite von 70 mm zeigt das Feld 35,00 mm."
        ),
        caption=_(
            "Derselbe Knopf steht neben jedem Maß. Eingeschaltet nimmt das Feld einen "
            "Ausdruck statt einer Zahl."
        ),
        build=_parameter_field,
    ),
    Figure(
        key="sketch-uses",
        alt=_(
            "Links ein bemaßter Umriss, ein Pfeil führt nach rechts zu drei Körpern "
            "daraus: derselbe Umriss gerade nach oben extrudiert, um eine senkrechte "
            "Achse zu einer Hülse gedreht, und als Band entlang eines Viertelbogens "
            "geführt."
        ),
        caption=_("Was aus der Zeichnung wird, entscheidet sich nach dem Zeichnen."),
        build=_sketch_uses,
    ),
    Figure(
        key="fit",
        alt=_(
            "Querschnitt durch ein Bauteil: ein Zapfen steckt in einer Bohrung, der "
            "Spalt dazwischen ist bemaßt. Die Zahl steht im Materialprofil und wird "
            "nicht im Dialog eingetragen."
        ),
        caption=_("Wer kalibriert, verbessert damit auch Teile, die vorher entstanden sind."),
        build=_fit,
    ),
    Figure(
        key="overhang",
        alt=_(
            "Zwei Überhänge nebeneinander: 40 Grad druckt frei, 65 Grad braucht "
            "Stützen. Gemessen wird gegen die Senkrechte."
        ),
        build=_overhang,
    ),
    Figure(
        key="elephant-foot",
        alt=_(
            "Ein Stapel Schichten auf dem Druckbett. Die unterste ist breiter als alle "
            "darüber, weil sie angedrückt wird — der Elefantenfuß."
        ),
        caption=_("Bei Passungen an der ersten Schicht rechnet Solidon ihn mit ein."),
        build=_elephant_foot,
    ),
    Figure(
        key="wall",
        alt=_(
            "Eine Wand im Querschnitt, aus zwei nebeneinanderliegenden "
            "Extrusionsbahnen — die dünnste Wand, die trägt. Die Breite steht im "
            "Druckerprofil."
        ),
        caption=_("Eine einzelne Bahn trägt nichts und reißt beim Entfernen der Stützen."),
        build=_wall,
    ),
    Figure(
        key="split",
        alt=_(
            "Links ein Objekt, das über den Rand des Druckbetts hinausragt. Rechts "
            "dasselbe Objekt in zwei Teile geschnitten, mit zwei Passstiften in der "
            "Schnittfläche."
        ),
        caption=_("Die Passstifte sorgen dafür, dass die Hälften nur in einer Lage zusammengehen."),
        build=_split,
    ),
    Figure(
        key="layers",
        alt=_(
            "Eine Brücke zwischen zwei Pfeilern mit bemaßter Spannweite, daneben ein "
            "kleiner Block, der in der Luft hängt — eine Insel."
        ),
        caption=_("Analysiert wird hier, geschnitten wird weiterhin im Slicer."),
        build=_layers,
    ),
    Figure(
        key="part-nut-trap",
        alt=_(
            "Eine Mutternfalle: die sechseckige Tasche, in die beim Drucken eine "
            "Sechskantmutter eingelegt wird."
        ),
        caption=_("Ein Klick statt einer halben Stunde — und das Maß kommt aus der Tabelle."),
        kind="rendered",
        build=_part("nut_trap", around=55.0, down=25.0),
    ),
    Figure(
        key="part-heatset",
        alt=_(
            "Eine Einpressbuchse-Bohrung: der abgestufte Kanal, in den eine "
            "Gewindebuchse mit dem Lötkolben eingeschmolzen wird."
        ),
        caption=_("Das Gewinde hält im Metall, nicht im Kunststoff."),
        kind="rendered",
        build=_part("heatset_m4", around=-35.0, down=50.0),
    ),
    Figure(
        key="part-snap-fit",
        alt=_(
            "Eine Rastnase: der federnde Arm mit der schrägen Nase, die beim Fügen "
            "ausweicht und danach zurückschnappt."
        ),
        kind="rendered",
        build=_part("snap_fit", around=-35.0, down=8.0),
    ),
    Figure(
        key="part-hinge",
        alt=_(
            "Ein Filmscharnier: die dünne Stelle zwischen zwei Platten, die als Gelenk "
            "wirkt, weil sie sich biegt statt zu brechen."
        ),
        kind="rendered",
        build=_part("living_hinge", around=-35.0, down=55.0),
    ),
    Figure(
        key="part-pegboard-hook",
        alt=_(
            "Ein Lochwand-Einhänger: Haken im Raster einer Lochwand, mit der "
            "federnden Rastzunge, die hinter der Platte einrastet."
        ),
        caption=_(
            "Von oben eingehängt, durch die Zunge gehalten — zum Lösen durch den Schlitz gedrückt."
        ),
        kind="rendered",
        build=_part("pegboard_hook", around=-35.0, down=25.0),
    ),
    Figure(
        key="part-gusset",
        alt=_(
            "Ein Eckwinkel: das Dreieck in einer Innenecke, das zwei Wände im "
            "rechten Winkel gegeneinander hält."
        ),
        kind="rendered",
        build=_part("gusset", around=-35.0, down=25.0),
    ),
    Figure(
        key="part-foot",
        alt=_(
            "Ein Standfuß: ein gedruckter Fuß mit Fase nach unten, damit der "
            "Elefantenfuß der ersten Schicht ins Leere quetscht."
        ),
        kind="rendered",
        build=_part("foot", around=-35.0, down=25.0),
    ),
    Figure(
        key="part-cable-clip",
        alt=_(
            "Ein Kabelclip: der Bügel auf einer Fläche, dessen Öffnung enger ist "
            "als das Kabel, das er führt."
        ),
        kind="rendered",
        build=_part("cable_clip", around=-35.0, down=25.0),
    ),
    Figure(
        key="part-hinge-eye",
        alt=_(
            "Ein Scharnierauge: eine Lasche mit Bohrung, durch die ein Passstift "
            "geht — die Hälfte eines Gelenks, das sich dreht statt zu biegen."
        ),
        kind="rendered",
        build=_part("hinge_eye", around=-35.0, down=25.0),
    ),
    Figure(
        key="part-fit-ladder",
        alt=_(
            "Der Toleranz-Testkörper: mehrere Zapfen und Bohrungen mit gestaffeltem "
            "Spiel auf einer Platte."
        ),
        caption=_("Einmal drucken, ausprobieren, Wert eintragen — danach stimmt jede Passung."),
        kind="rendered",
        build=_part("fit_ladder", size=220, around=-35.0, down=55.0),
    ),
    Figure(
        key="drill",
        alt=_(
            "Dieselbe Platte zweimal: links ohne Bohrung, rechts mit einem "
            "durchgehenden Loch von 8 mm."
        ),
        caption=_("Beide Bilder rechnet dieselbe Operation, die auch im Menü steht."),
        kind="rendered",
        build=_drilled,
    ),
    Figure(
        key="start-screen",
        alt=_(
            "Der Startbildschirm: zuletzt geöffnete Projekte, die Beispielprojekte "
            "und ein großes Feld, auf das man eine Datei ziehen kann."
        ),
        caption=_("Kein leerer Startbildschirm — es gibt immer etwas zum Anfangen."),
        kind="shot",
    ),
    Figure(
        key="main-window",
        alt=_(
            "Das Hauptfenster mit einem geladenen Modell im Viewport, dem Objektbaum "
            "links und dem Prüfbericht rechts."
        ),
        kind="shot",
    ),
    Figure(
        key="op-dialog",
        alt=_(
            "Ein Operationsdialog: vorn die zwei bis drei Werte, die man tatsächlich "
            "ändert, darunter der zugeklappte Bereich „Weitere Einstellungen“."
        ),
        caption=_(
            "Gestufte Tiefe: eine gute Vorgabe ist mehr wert als eine gute Einstellmöglichkeit."
        ),
        kind="shot",
    ),
    Figure(
        key="report",
        alt=_(
            "Der Prüfbericht mit Befunden, jeder mit Schweregrad, Ort und einer "
            "anklickbaren Handlung."
        ),
        caption=_("Ein Befund endet nie bei der Feststellung."),
        kind="shot",
    ),
    Figure(
        key="catalog",
        alt=_(
            "Der Bausteinkatalog: Vorschaubilder statt einer Namensliste, nach Gruppen geordnet."
        ),
        kind="shot",
    ),
    Figure(
        key="own-part",
        alt=_(
            "Der Dialog „Auswahl als Baustein speichern“: ganz oben die Zeile, "
            "welche Schritte des Verlaufs mitgehen — ausgewählte oder der ganze "
            "Stapel —, darunter Name, Gruppe und Beschreibung, dann je "
            "Projektparameter eine Zeile mit Beschriftung, Einheit, kleinstem "
            "und größtem Wert, Vorgabe und Platz im späteren Dialog. Unten die "
            "erkannten Merkmale mit dem Namen, unter dem sie später anklickbar "
            "sind."
        ),
        caption=_("Was einstellbar sein soll, sagt der, der das Teil gebaut hat."),
        kind="shot",
    ),
    Figure(
        key="sketch-result",
        alt=_(
            "Dasselbe Fenster nach dem Fertigstellen: Aus der Zeichnung ist ein Körper "
            "geworden, der im Objektbaum, im Verlauf und in der Ansicht steht. Der "
            "Kreis der Zeichnung ist ein Loch im Teil."
        ),
        caption=_("Was gezeichnet war, ist jetzt ein Schritt im Verlauf."),
        kind="shot",
    ),
    Figure(
        key="sketch-mode",
        alt=_(
            "Der Skizzenmodus: gezeichnet wird in der Ansicht, auf der Fläche des "
            "Teils, die in der Leiste unten steht. Die Leiste trägt die "
            "Zeichenwerkzeuge, die Ebenenwahl mit dem Hinweis auf die Druckschichten, "
            "die Reihe der Bedingungsknöpfe und die Zahl der freien Freiheitsgrade. "
            "Rechts stehen die Bedingungen der Zeichnung als eigener Reiter, einzeln "
            "aufgelistet."
        ),
        caption=_("Die Ansicht bleibt die Ansicht — die Zeichnung liegt darin."),
        kind="shot",
    ),
)

_BY_KEY: Final[dict[str, Figure]] = {figure.key: figure for figure in FIGURES}

#: Fertige SVG, damit eine Seite beim zweiten Öffnen nicht neu rechnet.
_CACHE: dict[tuple[str, Theme], str] = {}


def find(key: str) -> Figure | None:
    return _BY_KEY.get(key)


def svg(key: str, theme: Theme = "light") -> str | None:
    """Das SVG einer Abbildung, oder ``None``, wenn sie hier nicht entstehen kann.

    Kein Fehler im Fehlerfall, mit Absicht: eine fehlende Abbildung darf ein
    Handbuch nicht unlesbar machen. Der Aufrufer zeigt dann den Alt-Text, der
    ohnehin die Aussage trägt.
    """
    figure = _BY_KEY.get(key)
    if figure is None or figure.build is None:
        return None
    cached = _CACHE.get((key, theme))
    if cached is not None:
        return cached
    try:
        drawn = figure.build(theme)
    except Exception as problem:
        # Ein Baustein, den es nicht mehr gibt, ein fehlendes Zusatzpaket, ein
        # Netz, das nicht zustande kommt: alles Gründe, dieses eine Bild
        # wegzulassen — und keiner, das Kapitel nicht anzuzeigen. Aber mit
        # Spur: Ohne die Zeile verschwand eine dauerhaft brechende Abbildung
        # aus Fenster, Handbuch und Website, und niemand erfuhr es (L-10).
        _log.warning("figure %s could not be drawn: %s", key, problem)
        return None
    _CACHE[(key, theme)] = drawn
    return drawn


def forget() -> None:
    """Den Zwischenspeicher leeren — nach einem Sprach- oder Themenwechsel."""
    _CACHE.clear()
