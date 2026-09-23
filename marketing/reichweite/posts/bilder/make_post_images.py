"""Beitragsbilder aus den Vollbildaufnahmen der Anwendung zuschneiden und beschriften.

Aufruf aus dem Projektwurzelverzeichnis, nach ``capture_app.py``::

    .venv\\Scripts\\python.exe marketing\\reichweite\\posts\\bilder\\make_post_images.py

Jedes Bild ist **ein zusammenhängender Ausschnitt in nativen Pixeln** aus einer
Aufnahme des maximierten Solidon-Fensters (2560 x 1369, Stand 0.4.4) unter
``aufnahmen/``. Nichts wird vergrößert, verkleinert oder nachgezeichnet: Der
Ausschnitt hat genau die Größe des Beitragsbilds (1080 x 1350 oder 1080 x 1080).
Darüber liegt ein Textband, knapp und groß, oben oder unten, je nachdem, wo es
das Bedienelement der Handlung nicht verdeckt.

Schrift: Segoe UI wie in den Titelbildern der Werkstattfilme; fehlt sie,
Liberation Sans aus ``app/core/geom/data/fonts``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAPTURES = HERE / "aufnahmen"

BAND = (20, 22, 26, 255)
ACCENT = (224, 139, 78)
FOREGROUND = (245, 247, 250)
MUTED = (200, 206, 214)
MARGIN = 56
#: Geschütztes Leerzeichen: Der Umbruch trennt nur an gewöhnlichen Leerzeichen.
NBSP = chr(0xA0)
#: Ab dieser Fensterzeile beginnt die Statuszeile. Sie trägt den Demo-Countdown
#: vom Aufnahmetag; ein Beitrag erscheint Tage später. Enthält ein Ausschnitt sie,
#: deckt eine Fußleiste sie ab, statt einen veralteten Tagesstand zu zeigen.
STATUS_BAR_TOP = 1328

FONT_DIRS = (Path("C:/Windows/Fonts"), ROOT / "app" / "core" / "geom" / "data" / "fonts")
FONT_FILES = {
    "bold": ("segoeuib.ttf", "LiberationSans-Bold.ttf"),
    "regular": ("segoeui.ttf", "LiberationSans-Regular.ttf"),
}


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    """Die erste vorhandene Schrift der gewünschten Stärke laden."""
    for name in FONT_FILES[weight]:
        for folder in FONT_DIRS:
            path = folder / name
            if path.is_file():
                return ImageFont.truetype(str(path), size)
    raise SystemExit(f"Keine Schrift für {weight} gefunden.")


@dataclass(frozen=True)
class Spec:
    """Ein Beitragsbild: Quelle, nativer Ausschnitt, Textband."""

    name: str
    capture: str
    crop: tuple[int, int, int, int]  # x, y, Breite, Höhe in Fensterpixeln
    band: str  # "top", "bottom" oder "block" (Kasten oben links)
    headline: str
    sub: str
    right: str  # rechts in der Kopfzeile des Bandes, meist die Adresse
    block: tuple[int, int] = (0, 0)  # Breite und Höhe des Kastens bei ``band="block"``
    footer: str = ""  # Fußleiste über der Statuszeile, wenn der Ausschnitt sie enthält


def wrap(
    draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, width: int
) -> list[str]:
    """Text wortweise auf die verfügbare Breite umbrechen."""
    lines: list[str] = []
    current = ""
    # Nur an gewöhnlichen Leerzeichen trennen: Ein geschütztes Leerzeichen hält
    # „30. Oktober“ zusammen.
    for word in text.split(" "):
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=face) <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fitted(
    draw: ImageDraw.ImageDraw, text: str, weight: str, start: int, width: int, max_lines: int
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Größte Schrift, bei der der Text in höchstens ``max_lines`` Zeilen passt."""
    for size in range(start, 29, -2):
        face = font(weight, size)
        lines = wrap(draw, text, face, width)
        if len(lines) <= max_lines and all(draw.textlength(ln, font=face) <= width for ln in lines):
            return face, lines
    raise SystemExit(f"Text passt nicht, bitte kürzen: {text}")


def render(spec: Spec) -> Path:
    """Ausschnitt nehmen, Band setzen, speichern."""
    source = CAPTURES / spec.capture
    if not source.is_file():
        raise SystemExit(f"Aufnahme fehlt: {source} — zuerst capture_app.py laufen lassen")
    shot = Image.open(source).convert("RGB")
    x, y, width, height = spec.crop
    if x < 0 or y < 0 or x + width > shot.width or y + height > shot.height:
        raise SystemExit(f"{spec.name}: Ausschnitt liegt außerhalb der Aufnahme {shot.size}")
    canvas = shot.crop((x, y, x + width, y + height)).convert("RGBA")

    measure = ImageDraw.Draw(canvas)
    boxed = spec.band == "block"
    area_width = spec.block[0] if boxed else width
    text_width = area_width - 2 * MARGIN
    square = height <= width
    kicker = font("bold", 26)
    head_face, head_lines = fitted(
        measure, spec.headline, "bold", 88 if boxed else 72 if square else 80, text_width, 3
    )
    sub_face, sub_lines = (
        fitted(measure, spec.sub, "regular", 38 if boxed else 34 if square else 36, text_width, 3)
        if spec.sub
        else (font("regular", 34), [])
    )
    head_step = int(head_face.size * 1.12)
    sub_step = int(sub_face.size * 1.28)
    band_height = 24 + 30 + 10 + head_step * len(head_lines) + sub_step * len(sub_lines) + 28

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if boxed:
        if band_height > spec.block[1]:
            raise SystemExit(f"{spec.name}: Text passt nicht in den Kasten")
        band_height = spec.block[1]
    top = height - band_height if spec.band == "bottom" else 0
    draw.rectangle((0, top, area_width, top + band_height), fill=BAND)
    if boxed:
        draw.rectangle((area_width - 3, 0, area_width, band_height), fill=ACCENT)
        draw.rectangle((0, band_height - 3, area_width, band_height), fill=ACCENT)
    else:
        edge = top + band_height - 3 if spec.band == "top" else top
        draw.rectangle((0, edge, width, edge + 3), fill=ACCENT)
    content = band_height if not boxed else 24 + 30 + 10 + head_step * len(head_lines)
    if boxed:
        content += sub_step * len(sub_lines) + 28
    cursor = top + 24 + (max(0, band_height - content) // 2 if boxed else 0)
    draw.text((MARGIN, cursor), "SOLIDON3D", font=kicker, fill=ACCENT)
    if spec.right:
        right_width = draw.textlength(spec.right, font=kicker)
        draw.text((area_width - MARGIN - right_width, cursor), spec.right, font=kicker, fill=ACCENT)
    cursor += 30 + 10
    for line in head_lines:
        draw.text((MARGIN, cursor), line, font=head_face, fill=FOREGROUND)
        cursor += head_step
    for line in sub_lines:
        draw.text((MARGIN, cursor), line, font=sub_face, fill=MUTED)
        cursor += sub_step

    if y + height > STATUS_BAR_TOP and spec.band != "bottom":
        if not spec.footer:
            raise SystemExit(f"{spec.name}: Ausschnitt enthält die Statuszeile, Fußleiste fehlt")
        strip = STATUS_BAR_TOP - y - 4
        draw.rectangle((0, strip, width, height), fill=BAND)
        draw.rectangle((0, strip, width, strip + 3), fill=ACCENT)
        small = font("regular", 26)
        draw.text((MARGIN, strip + 8), spec.footer, font=small, fill=MUTED)
        address = spec.right or "solidon3d.de"
        right_width = draw.textlength(address, font=kicker)
        draw.text((width - MARGIN - right_width, strip + 7), address, font=kicker, fill=ACCENT)

    result = Image.alpha_composite(canvas, overlay).convert("RGB")
    target = HERE / f"{spec.name}.png"
    result.save(target, optimize=True)
    return target


SPECS = [
    Spec(
        "bohrung-senkung-de-1080x1350",
        "bohrung-de.png",
        (1480, 19, 1080, 1350),
        "block",
        "Loch zu klein?",
        "Anklicken, rechts den neuen Durchmesser eintippen. Die Senkung wächst mit.",
        "",
        (836, 612),
        "Kostenlose Demo bis 30. Oktober",
    ),
    Spec(
        "bohrung-senkung-en-1080x1080",
        "bohrung-en.png",
        (1480, 60, 1080, 1080),
        "block",
        "Hole too small?",
        "Click it, type the new diameter on the right. The countersink grows with it.",
        "solidon3d.de/en",
        (836, 571),
    ),
    Spec(
        "gegenstuecke-de-1080x1350",
        "gegenstuecke-de.png",
        (700, 19, 1080, 1350),
        "top",
        "Zwei Teile sollen zusammenstecken?",
        "Beide Flächen anklicken, Maße einmal eintragen: Stift und Loch entstehen zusammen.",
        "",
        footer="Kostenlose Demo bis 30. Oktober",
    ),
    Spec(
        "gegenstuecke-en-1080x1080",
        "gegenstuecke-en.png",
        (700, 246, 1080, 1080),
        "bottom",
        "Two parts, one pin?",
        "Click both faces, enter the size once. Pin and hole are made together.",
        "solidon3d.de/en",
    ),
    Spec(
        "frage-teil-anpassen-de-1080x1080",
        "frage-de.png",
        (0, 0, 1080, 1080),
        "bottom",
        "Welches Teil musstest du zuletzt ändern?",
        "Schreib es in die Kommentare.",
        "solidon3d.de",
    ),
    Spec(
        "pruefbericht-de-1080x1350",
        "pruefbericht-de.png",
        (1216, 19, 1080, 1350),
        "block",
        "Was schiefgehen würde, steht vorher da.",
        "Der Prüfbericht meldet offene Stellen, zu dünne Wände und zu enge Passungen.",
        "",
        (684, 606),
        "Kostenlose Demo bis 30. Oktober",
    ),
    Spec(
        "langloch-de-1080x1350",
        "langloch-de.png",
        (1480, 19, 1080, 1350),
        "block",
        "Schraube soll verstellbar sein?",
        "Loch anklicken, rechts eine Länge eintippen: Aus dem runden Loch wird ein Langloch.",
        "",
        (836, 612),
        "Kostenlose Demo bis 30. Oktober",
    ),
    Spec(
        "demo-gehaeuse-de-1080x1350",
        "demo-de.png",
        (0, 0, 1080, 1350),
        "bottom",
        f"Die Demo läuft bis zum 30.{NBSP}Oktober.",
        "Vollständig, ohne Konto, ohne Wasserzeichen. Dieses Gehäuse hat 24 Schritte, "
        "jeder bleibt änderbar.",
        "solidon3d.de",
    ),
    Spec(
        "demo-gehaeuse-en-1080x1080",
        "demo-en.png",
        (320, 0, 1080, 1080),
        "bottom",
        f"The free demo runs until 30{NBSP}October.",
        "Complete, no account, no watermark. This enclosure has 24 steps, each one still editable.",
        "solidon3d.de/en",
    ),
    Spec(
        "schraubdose-de-1080x1350",
        "schraubdose-de.png",
        (0, 0, 1080, 1350),
        "bottom",
        "Ein Gewinde, das greift.",
        "Hals und Deckel kommen aus derselben Steigung, das Spiel aus deinem Materialprofil.",
        "solidon3d.de",
    ),
    Spec(
        "rueckmeldung-de-1080x1350",
        "rueckmeldung-de.png",
        (706, 19, 1080, 1350),
        "top",
        "Solidon3D kommt von einer Person.",
        "Rückmeldung direkt aus dem Programm: Es antwortet der, der den Code geschrieben hat.",
        "",
        footer="Kein Konto, keine Cloud",
    ),
    Spec(
        "unterstuetzen-de-1080x1350",
        "unterstuetzen-de.png",
        (723, 19, 1080, 1350),
        "top",
        "Solidon3D bis Version 1.0 unterstützen",
        "Freiwillig und ohne Gegenleistung, über PayPal oder GoFundMe.",
        "",
        footer="gofund.me/08c5f0edb",
    ),
]


def main() -> None:
    import sys

    wanted = set(sys.argv[1:])
    for spec in SPECS:
        if wanted and spec.name not in wanted:
            continue
        target = render(spec)
        print(f"{target.name}  {spec.crop[2]}x{spec.crop[3]}  aus {spec.capture}")


if __name__ == "__main__":
    main()
