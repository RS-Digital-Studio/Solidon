"""Erzeugt Profilbild und Kanalbanner für den YouTube-Kanal.

Beides entsteht aus dem Anwendungssymbol (``app/images/icon/solidon3d.svg``)
und den Markenfarben, damit Kanal, Website und Anwendung dasselbe Bild zeigen.
Geschrieben werden je Erzeugnis die SVG-Quelle und die gerasterte PNG:

* ``profile-800.svg`` / ``.png`` — 800x800, YouTube maskiert es kreisrund.
  Alles Wesentliche bleibt deshalb innerhalb des einbeschriebenen Kreises.
* ``banner-2048x1152.svg`` / ``.png`` — YouTubes Mindestmaß im Verhältnis 16:9.
  Sichtbar ist je nach Gerät verschieden viel; die Aufteilung steht in
  ``SAFE_WIDTH`` und ``SAFE_HEIGHT``.
* ``banner-preview-zones.png`` — derselbe Banner mit eingezeichneten
  Sichtbereichen. Nur zum Ansehen, nicht zum Hochladen.

    python marketing/youtube/make_youtube_art.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QPainter,
    QPen,
)
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent.parent
HERE = Path(__file__).resolve().parent
APPLICATION_ICON = ROOT / "app" / "images" / "icon" / "solidon3d.svg"

# --- Marke -------------------------------------------------------------------

#: Der Deckflächenton des Anwendungssymbols für Akzente außerhalb des Körpers.
TOP_FACE = "#e08b4e"

#: Der Grund, auf dem das Symbol steht. Dunkel, damit das Orange trägt — der
#: Kanalkopf steht bei YouTube auf Weiß wie auf Schwarz.
INK_DARK = "#140c04"
INK_MID = "#241505"
TEXT_BRIGHT = "#f6ece1"
TEXT_MUTED = "#cbb39b"
TEXT_FAINT = "#9a836d"

#: Die Schrift. Die Website setzt Archivo, das aber nur als WOFF2 vorliegt und
#: von Qt nicht geladen wird; „Segoe UI Semibold" ist die nächstgelegene
#: Groteske, die auf dieser Maschine sicher vorhanden ist.
FONT_STRONG = "Segoe UI Semibold"
FONT_PLAIN = "Segoe UI"

# --- Texte -------------------------------------------------------------------

WORDMARK_LEFT = "Solidon"
WORDMARK_RIGHT = "3D"
CLAIM_LINE = "Fremde 3D-Modelle anpassen. Eigene konstruieren."
CLAIM_SECOND = "Druckbarkeit prüfen, bevor der Slicer läuft."
DOMAIN = "solidon3d.de"

# --- Maße --------------------------------------------------------------------

PROFILE_SIZE = 800

BANNER_WIDTH = 2048
BANNER_HEIGHT = 1152

#: Was YouTube je Gerät zeigt, umgerechnet auf 2048x1152. Der mittlere
#: Streifen ist der einzige Bereich, der überall ankommt — Symbol und Text
#: stehen ausschließlich darin.
SAFE_WIDTH = 1235
SAFE_HEIGHT = 338
SAFE_LEFT = (BANNER_WIDTH - SAFE_WIDTH) / 2
SAFE_TOP = (BANNER_HEIGHT - SAFE_HEIGHT) / 2
SAFE_MARGIN = 64.0

MAX_PROFILE_BYTES = 15_000_000
MAX_BANNER_BYTES = 6_000_000


def application_icon_body() -> str:
    """Liest den Inhalt des Anwendungssymbols für die Wiederverwendung im SVG."""
    source = APPLICATION_ICON.read_text(encoding="utf-8")
    opening_end = source.find(">")
    closing_start = source.rfind("</svg>")
    if opening_end < 0 or closing_start <= opening_end:
        raise ValueError(
            "Das Anwendungssymbol enthält kein vollständiges SVG. Prüfe "
            f"{APPLICATION_ICON.relative_to(ROOT)} und erzeuge die Kanalbilder erneut."
        )
    return source[opening_end + 1 : closing_start].strip()


def solid_body(size: float, offset_x: float, offset_y: float) -> str:
    """Das Anwendungssymbol als SVG-Gruppe, skaliert und verschoben.

    Die Quelle rechnet in einer 128er-Viewbox; ``size`` ist deren Kantenlänge
    im Zielbild. Der Körper füllt darin x 24..104 und y 18..110.
    """
    scale = size / 128.0
    icon = "\n".join(f"    {line}" for line in application_icon_body().splitlines())
    return (
        f'  <g transform="translate({offset_x:.2f} {offset_y:.2f}) scale({scale:.5f})">\n'
        f"{icon}\n"
        f"  </g>\n"
    )


def isometric_grid(width: int, height: int, spacing: int, opacity: float) -> str:
    """Ein isometrisches Liniennetz über die ganze Fläche.

    Zwei Scharen im Winkel der Symbolflanken (1:2 wie die Isometrie der
    Quelle). Als einzelne Pfade und nicht als ``<pattern>``, weil Qts
    SVG-Leser Muster nur unvollständig kennt.
    """
    parts: list[str] = [
        f'  <g stroke="#ffffff" stroke-opacity="{opacity}" stroke-width="1.2" fill="none">\n'
    ]
    reach = width + 2 * height
    step = spacing * 2
    for start in range(-reach, reach, step):
        parts.append(f'    <path d="M{start} {height} L{start + 2 * height} 0" />\n')
        parts.append(f'    <path d="M{start} 0 L{start + 2 * height} {height}" />\n')
    parts.append("  </g>\n")
    return "".join(parts)


def text_width(text: str, family: str, pixel_size: float) -> float:
    """Wie breit ein Text wird — gemessen, nicht geschätzt.

    Das Layout des Banners hängt daran: Der Block aus Symbol und Text wird im
    sicheren Bereich zentriert, und ein um zwanzig Pixel danebenliegender
    Schätzwert schiebt ihn sichtbar aus der Mitte.
    """
    font = QFont(family)
    font.setPixelSize(round(pixel_size))
    return QFontMetricsF(font).horizontalAdvance(text)


def build_profile() -> str:
    """Das Profilbild: Symbol auf dunklem Grund, mit Ring als Kante."""
    center = PROFILE_SIZE / 2
    body_box = 600.0
    grid = isometric_grid(PROFILE_SIZE, PROFILE_SIZE, 40, 0.045)
    body = solid_body(body_box, center - body_box / 2, center - body_box / 2)
    return f"""<svg xmlns="http://www.w3.org/2000/svg"
     width="{PROFILE_SIZE}" height="{PROFILE_SIZE}"
     viewBox="0 0 {PROFILE_SIZE} {PROFILE_SIZE}">
  <!-- Kanalbild für YouTube. Angezeigt wird ein Kreis: der Rand des Quadrats
       fällt weg, deshalb steht der Körper mittig und mit Abstand zum Ring. -->
  <defs>
    <radialGradient id="ground" cx="0.5" cy="0.42" r="0.72">
      <stop offset="0" stop-color="#33200c" />
      <stop offset="0.62" stop-color="{INK_MID}" />
      <stop offset="1" stop-color="{INK_DARK}" />
    </radialGradient>
    <radialGradient id="glow" cx="0.5" cy="0.40" r="0.52">
      <stop offset="0" stop-color="{TOP_FACE}" stop-opacity="0.16" />
      <stop offset="1" stop-color="{TOP_FACE}" stop-opacity="0" />
    </radialGradient>
  </defs>
  <rect width="{PROFILE_SIZE}" height="{PROFILE_SIZE}" fill="url(#ground)" />
{grid}  <circle cx="{center}" cy="{center}" r="{center}" fill="url(#glow)" />
  <circle cx="{center}" cy="{center}" r="370" fill="none"
          stroke="{TOP_FACE}" stroke-opacity="0.75" stroke-width="8" />
{body}</svg>
"""


def build_banner() -> str:
    """Der Kanalbanner: Symbol und Wortmarke im überall sichtbaren Streifen."""
    title_size = 96.0
    claim_size = 36.0
    second_size = 32.0
    domain_size = 28.0

    block_text_width = max(
        text_width(WORDMARK_LEFT + WORDMARK_RIGHT, FONT_STRONG, title_size),
        text_width(CLAIM_LINE, FONT_PLAIN, claim_size),
        text_width(CLAIM_SECOND, FONT_PLAIN, second_size),
    )

    # Der Körper füllt 80 von 128 Einheiten in der Breite.
    body_box = 320.0
    body_width = body_box * 80 / 128
    gap = 60.0

    block_width = body_width + gap + block_text_width
    if block_width > SAFE_WIDTH - 2 * SAFE_MARGIN:
        raise ValueError(
            f"Der Block wird {block_width:.0f} Pixel breit und ließe im sicheren Bereich "
            f"({SAFE_WIDTH} Pixel) keinen Rand von {SAFE_MARGIN:.0f} Pixeln. Entweder die "
            f"Texte kürzen oder in build_banner die Schriftgrößen senken."
        )

    block_left = (BANNER_WIDTH - block_width) / 2
    center_y = BANNER_HEIGHT / 2

    # Erst die Abstände, dann die Lage: Wortmarke und Zeilen werden als ein
    # Block auf die Mitte gesetzt. Wer stattdessen von der Mitte aus nach
    # unten schreibt, bekommt einen Text, der neben dem Körper sichtbar
    # tiefer hängt.
    cap_height = title_size * 0.72
    claim_gap = 72.0
    second_gap = 48.0
    domain_gap = 50.0
    text_height = cap_height + claim_gap + second_gap + domain_gap
    title_baseline = center_y - text_height / 2 + cap_height
    claim_baseline = title_baseline + claim_gap
    second_baseline = claim_baseline + second_gap
    domain_baseline = second_baseline + domain_gap

    text_left = block_left + body_width + gap
    body_left = block_left - (body_box - body_width) / 2
    body_top = center_y - body_box / 2

    # Der Körper steht auf einem weichen Schatten, sonst schwebt er über dem
    # Grund. Die Fußspitze liegt bei 110 von 128 Einheiten.
    shadow_x = body_left + body_box / 2
    shadow_y = body_top + body_box * 110 / 128
    shadow_rx = body_width * 0.78
    shadow_ry = body_width * 0.15

    grid = isometric_grid(BANNER_WIDTH, BANNER_HEIGHT, 56, 0.04)
    body = solid_body(body_box, body_left, body_top)
    return f"""<svg xmlns="http://www.w3.org/2000/svg"
     width="{BANNER_WIDTH}" height="{BANNER_HEIGHT}"
     viewBox="0 0 {BANNER_WIDTH} {BANNER_HEIGHT}">
  <!-- Kanalbanner für YouTube, 2048x1152. Vom Handy kommen nur die mittleren
       {SAFE_WIDTH}x{SAFE_HEIGHT} Pixel an — dort steht alles, was gelesen werden muss.
       Außen liegt nur Grund, den zusätzlich der Fernseher zeigt. -->
  <defs>
    <linearGradient id="ground" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{INK_DARK}" />
      <stop offset="0.45" stop-color="{INK_MID}" />
      <stop offset="1" stop-color="#0f0903" />
    </linearGradient>
    <radialGradient id="glow" cx="0.42" cy="0.5" r="0.46">
      <stop offset="0" stop-color="{TOP_FACE}" stop-opacity="0.26" />
      <stop offset="1" stop-color="{TOP_FACE}" stop-opacity="0" />
    </radialGradient>
    <linearGradient id="vignette" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#000000" stop-opacity="0.55" />
      <stop offset="0.22" stop-color="#000000" stop-opacity="0" />
      <stop offset="0.78" stop-color="#000000" stop-opacity="0" />
      <stop offset="1" stop-color="#000000" stop-opacity="0.55" />
    </linearGradient>
    <linearGradient id="rule" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{TOP_FACE}" stop-opacity="0.9" />
      <stop offset="1" stop-color="{TOP_FACE}" stop-opacity="0" />
    </linearGradient>
    <radialGradient id="shadow">
      <stop offset="0" stop-color="#000000" stop-opacity="0.46" />
      <stop offset="0.68" stop-color="#000000" stop-opacity="0.20" />
      <stop offset="1" stop-color="#000000" stop-opacity="0" />
    </radialGradient>
  </defs>
  <rect width="{BANNER_WIDTH}" height="{BANNER_HEIGHT}" fill="url(#ground)" />
{grid}  <rect width="{BANNER_WIDTH}" height="{BANNER_HEIGHT}" fill="url(#glow)" />
  <rect width="{BANNER_WIDTH}" height="{BANNER_HEIGHT}" fill="url(#vignette)" />
  <ellipse cx="{shadow_x:.1f}" cy="{shadow_y:.1f}"
           rx="{shadow_rx:.1f}" ry="{shadow_ry:.1f}" fill="url(#shadow)" />
{body}  <text x="{text_left:.1f}" y="{title_baseline:.1f}"
        font-family="{FONT_STRONG}" font-size="{title_size}"
        fill="{TEXT_BRIGHT}">{WORDMARK_LEFT}<tspan
        fill="{TOP_FACE}">{WORDMARK_RIGHT}</tspan></text>
  <rect x="{text_left:.1f}" y="{title_baseline + 22:.1f}"
        width="{block_text_width:.1f}" height="3" fill="url(#rule)" />
  <text x="{text_left:.1f}" y="{claim_baseline:.1f}"
        font-family="{FONT_PLAIN}" font-size="{claim_size}"
        fill="{TEXT_MUTED}">{CLAIM_LINE}</text>
  <text x="{text_left:.1f}" y="{second_baseline:.1f}"
        font-family="{FONT_PLAIN}" font-size="{second_size}"
        fill="{TEXT_FAINT}">{CLAIM_SECOND}</text>
  <text x="{text_left:.1f}" y="{domain_baseline:.1f}"
        font-family="{FONT_STRONG}" font-size="{domain_size}"
        fill="{TOP_FACE}">{DOMAIN}</text>
</svg>
"""


def rasterize(source: str, width: int, height: int, target: Path) -> QImage:
    """Rastert eine SVG-Quelle und schreibt sie als PNG."""
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError(f"{target.name}: die erzeugte SVG ist nicht lesbar")
    image = QImage(QSize(width, height), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    renderer.render(painter)
    painter.end()
    if not image.save(str(target), "PNG"):
        raise OSError(
            f"{target.name} konnte nicht geschrieben werden. Prüfe Schreibrechte und freien "
            "Speicherplatz und starte den Erzeuger erneut."
        )
    return image


def write_zone_preview(banner: QImage, target: Path) -> None:
    """Zeichnet die Sichtbereiche in eine Kopie des Banners.

    Nicht zum Hochladen — sie zeigt vorher, was auf dem Handy ankommt und was
    nur der Fernseher sieht.
    """
    preview = banner.copy()
    painter = QPainter(preview)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    zones = (
        (QRectF(3, 3, BANNER_WIDTH - 6, BANNER_HEIGHT - 6), "#e0574e", "Fernseher: alles"),
        (QRectF(3, SAFE_TOP, BANNER_WIDTH - 6, SAFE_HEIGHT), "#4ea3e0", "Desktop"),
        (QRectF(SAFE_LEFT, SAFE_TOP, SAFE_WIDTH, SAFE_HEIGHT), "#5fd08a", "Handy und Tablet"),
    )
    font = QFont(FONT_STRONG)
    font.setPixelSize(28)
    painter.setFont(font)
    for rect, color, label in zones:
        pen = QPen(QColor(color))
        pen.setWidth(4)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(rect)
        painter.setPen(QColor(color))
        painter.drawText(QRectF(rect.left() + 14, rect.top() + 12, 700, 44), 0, label)
    painter.end()
    if not preview.save(str(target), "PNG"):
        raise OSError(
            f"{target.name} konnte nicht geschrieben werden. Prüfe Schreibrechte und freien "
            "Speicherplatz und starte den Erzeuger erneut."
        )


def validate_upload_size(target: Path, maximum: int) -> None:
    """Hält die erzeugte PNG unter YouTubes jeweiliger Uploadgrenze."""
    actual = target.stat().st_size
    if actual > maximum:
        raise ValueError(
            f"{target.name} ist {actual / 1_000_000:.1f} MB groß, erlaubt sind höchstens "
            f"{maximum / 1_000_000:.0f} MB. Vereinfache das Bild oder erhöhe die "
            "PNG-Kompression und erzeuge es erneut."
        )


def main() -> int:
    _application = QGuiApplication.instance() or QGuiApplication(sys.argv)

    profile_svg = HERE / "profile-800.svg"
    profile_png = HERE / "profile-800.png"
    banner_svg = HERE / "banner-2048x1152.svg"
    banner_png = HERE / "banner-2048x1152.png"
    zones_png = HERE / "banner-preview-zones.png"

    profile_source = build_profile()
    profile_svg.write_text(profile_source, encoding="utf-8")
    rasterize(profile_source, PROFILE_SIZE, PROFILE_SIZE, profile_png)

    banner_source = build_banner()
    banner_svg.write_text(banner_source, encoding="utf-8")
    banner = rasterize(banner_source, BANNER_WIDTH, BANNER_HEIGHT, banner_png)
    validate_upload_size(profile_png, MAX_PROFILE_BYTES)
    validate_upload_size(banner_png, MAX_BANNER_BYTES)
    write_zone_preview(banner, zones_png)

    for path in (profile_svg, profile_png, banner_svg, banner_png, zones_png):
        print(f"Geschrieben: {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
