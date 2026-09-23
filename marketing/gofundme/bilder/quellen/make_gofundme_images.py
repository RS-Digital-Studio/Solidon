"""Macht aus den Vollbildaufnahmen die Bilder für GoFundMe.

    .venv\\Scripts\\python.exe marketing/gofundme/bilder/quellen/make_gofundme_images.py
    ... make_gofundme_images.py --sprache de --nur titelbild

Die Aufnahmen entstehen mit ``aufnahmen.py``: das ganze Solidon3D-Fenster der
Demo 0.4.4, maximiert auf dem 2560x1440-Schirm, in nativen Pixeln. Dieses
Skript schneidet daraus je Motiv einen Ausschnitt von 1920x1080 **ohne ihn zu
skalieren**, legt eine knappe Überschrift darüber und schreibt PNG, JPG und
ein Prüfblatt.

**Warum Ausschnitte an diesen Stellen.** GoFundMe beschneidet jedes Bild je
Gerät anders (gemessen am 23.09.2026, Einzelheiten in ``bericht.md``): Auf dem
Desktop bleiben rund 80 % der Breite, auf dem Telefon nur die mittleren 44 %,
und dort liegen ab etwa 60 % der Höhe Titel und Etikett über dem Bild. Die
Handlung steht deshalb in der Mitte des Ausschnitts und oberhalb von 620; die
Kamera wurde bei der Aufnahme so gestellt, dass sie dort landet.

**Die Überschrift liegt über dem Bild**, auf einer weichen Abdunklung, nicht
auf einer eigenen leeren Fläche (Robert, 23.09.2026). Die Maßmarken nennen nur
Werte, die die Anwendung selbst anzeigt (34,09 mm und 38,00 mm am
Rollenhalter).

Gerendert wird mit Chrome ohne Fenster, weil nur ein Browser die Schriften
der Website (Archivo, Source Sans 3, beide SIL OFL 1.1) aus den WOFF2-Dateien
lädt; Qt kann das nicht, siehe ``marketing/youtube/make_youtube_art.py``.
"""

# ruff: noqa: RUF001, RUF002
# Das Malzeichen und der Gedankenstrich im Kampagnentitel sind die Zeichen,
# die auf den Bildern stehen sollen, kein kleines x und kein Bindestrich; die
# Anwendung nimmt dafür dieselbe Ausnahme (``app/ui/*`` in ``pyproject.toml``).

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
PICTURES = HERE.parent
ROOT = HERE.parents[3]
CAPTURES = HERE / "aufnahmen"
CHECKS = PICTURES / "pruefung"
FONTS = ROOT / "website" / "fonts"

WIDTH = 1920
HEIGHT = 1080

#: Was auf jedem Gerät zu sehen ist: links, oben, rechts, unten.
#:
#: Breite: Telefon zeigt 44 % der Breite um die Mitte (537 bis 1383), mit Rand.
#: Höhe: Ab etwa 648 legt GoFundMe auf dem Telefon Etikett und Titel darüber.
SAFE_ALL = (560, 100, 1360, 620)

#: Was auf dem Desktop und in der Link-Vorschau zusätzlich zu sehen ist.
#:
#: Der engste Desktop-Zuschnitt ist 4:3 (1200x900), also 75 % der Breite.
SAFE_DESKTOP = (240, 0, 1680, 1080)

#: Die Farben der Website im dunklen Schema (``website/style.css``).
INK = "#f7f3ed"
MUTED = "#e2dbd2"
ACCENT = "#e08b4e"
ACCENT_INK = "#1b120a"

#: Wie breit Überschrift und Unterzeile höchstens werden: die 800 Punkte von
#: :data:`SAFE_ALL` mit etwas Luft. Längeres setzt die Seite selbst kleiner.
HEADLINE_LIMIT = 760
SUB_LIMIT = 790

#: Die JPG-Qualität. 92 hält die feine Schrift der Oberfläche sauber und
#: bleibt deutlich unter GoFundMes Grenze von 20 MB.
JPEG_QUALITY = 92


# --- Motive ------------------------------------------------------------------


@dataclass
class Pill:
    """Eine Maßmarke: Beschriftung an einer Stelle des Ausschnitts, wahlweise
    mit Linie zu einem Punkt."""

    text: str
    label: tuple[float, float]
    point: tuple[float, float] | None = None
    size: int = 38


@dataclass
class Motif:
    """Ein Bild der Kampagne in einer Sprache."""

    stem: str
    capture: str
    crop: tuple[int, int]
    headline: str
    sub: str = ""
    kicker: str = ""
    pills: list[Pill] = field(default_factory=list)


def points(language: str) -> dict[str, dict[str, list[float]]]:
    """Die Fensterkoordinaten, die ``aufnahmen.py`` mitgeschrieben hat."""
    return json.loads((CAPTURES / f"{language}.json").read_text(encoding="utf-8"))


def motifs(language: str) -> list[Motif]:
    """Alle Motive einer Sprache.

    Jeder Ausschnitt ist 1920x1080 aus einem Fenster von 2560x1369; ``crop`` ist
    seine linke obere Ecke im Fenster.
    """
    de = language == "de"
    spots = points(language)

    def at(capture: str, name: str, crop: tuple[int, int]) -> tuple[float, float]:
        x, y = spots[capture][name]
        return x - crop[0], y - crop[1]

    def mm(value: float) -> str:
        text = f"{value:.2f}"
        return text.replace(".", ",") if de else text

    old = mm(spots["halter-vorher"]["durchmesser_alt"])
    new = mm(spots["halter-nachher"]["durchmesser_neu"])
    new_short = f"{spots['halter-nachher']['durchmesser_neu']:g}"

    # Der Rollenhalter in der Übersicht: Ausschnitt ab 400/150, die rechte große
    # Bohrung liegt damit mittig, die linke steht im Desktop-Teil.
    plate = (400, 150)
    left_before, right_before = (
        at("halter-vorher", "loch_links", plate),
        at("halter-vorher", "loch_rechts", plate),
    )
    left_after, right_after = (
        at("halter-nachher", "loch_links", plate),
        at("halter-nachher", "loch_rechts", plate),
    )

    def plate_pills(left_text: str, right_text: str, left, right) -> list[Pill]:
        # Rechts über der Bohrung, links unter ihr: Die Bohrungen sind hoch
        # und schmal, darüber und darunter ist Wand.
        return [
            Pill(right_text, (right[0], right[1] - 205), (right[0], right[1] - 150)),
            # Links außerhalb der Handy-Mitte (endet vor 537), damit die Marke dort
            # ganz fehlt statt halb angeschnitten zu stehen.
            Pill(left_text, (350.0, left[1] + 215), (left[0] - 20, left[1] + 140)),
        ]

    # Die angeklickte Bohrung: für das Titelbild ab 392/80 — der Ausschnitt
    # endet an der Kante der rechten Leiste (2312), statt sie mitten im Text
    # zu schneiden, und die Bohrung liegt trotzdem im Handy-Teil —, für das
    # zweite Galeriebild rechtsbündig (ab 640/80), damit die Karte „Bohrung
    # ändern“ ganz im Bild steht.
    hole_centred, hole_right = (392, 80), (640, 80)
    hole = at("halter-bohrung", "loch", hole_centred)

    return [
        Motif(
            stem="titelbild",
            capture="halter-bohrung",
            crop=hole_centred,
            kicker="Solidon3D",
            headline="Loch zu klein?" if de else "Hole too small?",
            sub=(
                "Anklicken, neues Maß eintippen. Ohne CAD."
                if de
                else "Click it, type the new size. No CAD."
            ),
            # Mitten in der Bohrung, über ihrer eigenen Beschriftung: Dort ist
            # der Hintergrund dunkel, und die Marke gehört sichtbar zum Loch.
            pills=[Pill(f"{old} mm → {new_short} mm", (hole[0], hole[1] - 95), None, 42)],
        ),
        Motif(
            stem="galerie-1-vorher",
            capture="halter-vorher",
            crop=plate,
            headline="Passt fast." if de else "Almost fits.",
            sub=(
                "Die Bohrung hat 34 mm, gebraucht werden 38."
                if de
                else "The hole is 34 mm, the part needs 38."
            ),
            pills=plate_pills(f"Ø {old} mm", f"Ø {old} mm", left_before, right_before),
        ),
        Motif(
            stem="galerie-2-anklicken",
            capture="halter-bohrung",
            crop=hole_right,
            headline="Neues Maß tippen." if de else "Type the new size.",
            sub=(
                "Die Vorschau zeigt, was sich ändert."
                if de
                else "The preview shows what will change."
            ),
        ),
        Motif(
            stem="galerie-3-nachher",
            capture="halter-nachher",
            crop=plate,
            headline="38 mm statt 34." if de else "38 mm, not 34.",
            sub=("Der Rest bleibt, wie er war." if de else "Everything else stays as it was."),
            pills=plate_pills(f"Ø {old} mm", f"Ø {new} mm", left_after, right_after),
        ),
        Motif(
            stem="galerie-4-pruefbericht",
            capture="pruefbericht",
            # Rechtsbündig und von oben: Der Prüfbericht steht rechts oben im
            # Fenster, seine Warnung bei 260 — unter der Überschrift, im
            # Desktop-Teil des Bildes.
            crop=(640, 0),
            headline="Vorher prüfen." if de else "Check first.",
            # Die Warnung des Berichts groß und mittig, mit Linie zu ihrer Zeile
            # im Prüfbericht (Fenster 1930/262): Auf dem Telefon ist der Bericht
            # angeschnitten, die Marke nicht. Der Wortlaut ist der der Anwendung.
            pills=[
                Pill(
                    "Die Passung sitzt enger als vorgesehen."
                    if de
                    else "The fit is tighter than intended.",
                    (900.0, 430.0),
                    (1290.0, 262.0),
                    34,
                )
            ],
        ),
        Motif(
            stem="galerie-5-drucken",
            capture="drucken",
            # Der Dialog steht bei 1000/432 im Fenster; ab 320/132 liegt er
            # mittig und beginnt unter der Überschrift.
            crop=(320, 132),
            headline="Ab in den Slicer." if de else "Off to the slicer.",
            sub=(
                "Vorschläge mit Grund, dann weiter zum Slicer."
                if de
                else "Suggestions with reasons, then on to your slicer."
            ),
        ),
        Motif(
            stem="update-1",
            capture="halter-nachher",
            crop=plate,
            headline="185 Neuerungen" if de else "185 changes",
            sub=(
                "in vier Versionen seit dem 13. September"
                if de
                else "in four versions since 13 September"
            ),
            # Anzahl je Version: ``data-announcement`` in ``website/changelog.html``;
            # Tag im Download-Kasten: Git-Log von ``website/version.json``.
            pills=[
                Pill(text, (600 + index * 240, 985), None, 32)
                for index, text in enumerate(("0.4.1: 96", "0.4.2: 48", "0.4.3: 19", "0.4.4: 22"))
            ],
        ),
    ]


# --- HTML --------------------------------------------------------------------


def file_url(path: Path) -> str:
    """Ein Pfad als ``file:``-Adresse, mit Leerzeichen und Umlauten."""
    return path.resolve().as_uri()


def page(language: str, motif: Motif) -> str:
    """Die HTML-Seite eines Motivs in genau 1920x1080 Punkten."""
    capture = CAPTURES / f"{motif.capture}-{language}.png"
    with Image.open(capture) as image:
        width, height = image.size
    x0, y0 = motif.crop
    if x0 < 0 or y0 < 0 or x0 + WIDTH > width or y0 + HEIGHT > height:
        raise SystemExit(
            f"{motif.stem}: Ausschnitt {x0}/{y0} passt nicht in die Aufnahme {width}x{height}."
        )
    lines, labels = [], []
    for pill in motif.pills:
        lx, ly = pill.label
        if pill.point is not None:
            px, py = pill.point
            lines.append(
                f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{lx:.1f}" y2="{ly:.1f}" '
                f'stroke="{ACCENT}" stroke-width="4" stroke-linecap="round"/>'
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="9" fill="{ACCENT}" '
                f'stroke="#101010" stroke-width="3"/>'
            )
        style = f"left:{lx:.1f}px;top:{ly:.1f}px;font-size:{pill.size}px"
        labels.append(f'<div class="pill" style="{style}">{html.escape(pill.text)}</div>')
    svg = (
        f'<svg class="lines" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">{"".join(lines)}</svg>'
    )
    kicker = f'<div class="kicker">{html.escape(motif.kicker)}</div>' if motif.kicker else ""
    sub = f'<div class="sub"><span>{html.escape(motif.sub)}</span></div>' if motif.sub else ""
    archivo = file_url(FONTS / "Archivo-Variable.woff2")
    source_sans = file_url(FONTS / "SourceSans3-Variable.woff2")
    return f"""<!doctype html>
<html lang="{language}"><head><meta charset="utf-8"><style>
@font-face {{ font-family: "Archivo"; src: url("{archivo}") format("woff2");
  font-weight: 100 900; }}
@font-face {{ font-family: "Source Sans 3"; src: url("{source_sans}") format("woff2");
  font-weight: 200 900; }}
html {{ background: #101010; }}
html, body {{ margin: 0; width: {WIDTH}px; height: {HEIGHT}px; overflow: hidden; }}
body {{ position: relative; color: {INK}; }}
.shot {{ position: absolute; left: {-x0}px; top: {-y0}px; width: {width}px;
  height: {height}px; }}
.shade {{ position: absolute; inset: 0;
  background: radial-gradient(ellipse 700px 270px at 960px 185px,
    rgba(12,11,10,.9) 0%, rgba(12,11,10,.72) 45%, rgba(12,11,10,0) 100%); }}
.kicker {{ position: absolute; left: 0; right: 0; top: 98px; text-align: center;
  font: 700 26px/1 "Archivo"; letter-spacing: .2em; text-transform: uppercase;
  color: {ACCENT}; text-shadow: 0 2px 10px rgba(0,0,0,.8); }}
.headline {{ position: absolute; left: 0; right: 0; top: 130px; text-align: center;
  font: 800 96px/1 "Archivo"; letter-spacing: -.012em;
  text-shadow: 0 3px 22px rgba(0,0,0,.85), 0 1px 3px rgba(0,0,0,.9); }}
.sub {{ position: absolute; left: 0; right: 0; top: 240px; text-align: center;
  font: 600 36px/1.2 "Source Sans 3"; color: {MUTED};
  text-shadow: 0 2px 14px rgba(0,0,0,.9), 0 1px 2px rgba(0,0,0,.9); }}
.lines {{ position: absolute; left: 0; top: 0; }}
.pill {{ position: absolute; transform: translate(-50%, -50%); white-space: nowrap;
  background: {ACCENT}; color: {ACCENT_INK}; font-family: "Source Sans 3";
  font-weight: 700; line-height: 1; padding: 10px 22px 11px; border-radius: 999px;
  box-shadow: 0 10px 28px -6px rgba(0,0,0,.7), 0 0 0 3px rgba(16,16,16,.55); }}
</style></head><body>
<img class="shot" src="{file_url(capture)}">
<div class="shade"></div>
{kicker}
<div class="headline"><span>{html.escape(motif.headline)}</span></div>
{sub}
{svg}
{"".join(labels)}
<script>
// Überschrift und Unterzeile passen in die Breite, die jedes Gerät zeigt
// (SAFE_ALL). Zu lange Zeilen werden kleiner gesetzt, nicht abgeschnitten.
document.fonts.ready.then(() => {{
  for (const [selector, limit] of [[".headline", {HEADLINE_LIMIT}], [".sub", {SUB_LIMIT}]]) {{
    const box = document.querySelector(selector);
    if (!box) continue;
    const text = box.querySelector("span");
    let size = parseFloat(getComputedStyle(box).fontSize);
    while (text.getBoundingClientRect().width > limit && size > 24) {{
      size -= 1;
      box.style.fontSize = size + "px";
    }}
  }}
}});
</script>
</body></html>
"""


# --- Rendern -----------------------------------------------------------------


def chrome() -> str:
    """Wo Chrome liegt; ``CHROME`` im Environment geht vor."""
    candidates = [
        os.environ.get("CHROME", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        shutil.which("chrome") or "",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit(
        "Chrome nicht gefunden. Installieren oder den Pfad in der Umgebungsvariable CHROME "
        "angeben; gerendert wird mit Chrome, weil nur ein Browser die WOFF2-Schriften lädt."
    )


def render(html_file: Path, target: Path, profile: Path) -> None:
    """Eine Seite als PNG in genau 1920×1080 aufnehmen."""
    command = [
        chrome(),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        f"--window-size={WIDTH},{HEIGHT}",
        "--allow-file-access-from-files",
        "--virtual-time-budget=3000",
        f"--user-data-dir={profile}",
        f"--screenshot={target}",
        file_url(html_file),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode != 0 or not target.is_file():
        raise SystemExit(
            f"Chrome hat {target.name} nicht geschrieben (Exit {result.returncode}). "
            f"Ausgabe: {result.stderr.strip()[-400:]}"
        )
    with Image.open(target) as image:
        if image.size != (WIDTH, HEIGHT):
            raise SystemExit(
                f"{target.name} ist {image.size[0]}×{image.size[1]} statt {WIDTH}×{HEIGHT}. "
                "Chrome-Fenstergröße prüfen."
            )


def to_jpeg(png: Path) -> Path:
    """Die JPG-Fassung zum Hochladen."""
    target = png.with_suffix(".jpg")
    with Image.open(png) as image:
        image.convert("RGB").save(
            target, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True
        )
    return target


# --- Prüfblatt ---------------------------------------------------------------


def system_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Eine Systemschrift fürs Prüfblatt; die Website-Schriften liegen nur als WOFF2 vor."""
    names = ["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]
    for name in names:
        for folder in (Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",):
            path = folder / name
            if path.is_file():
                return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def cover(image: Image.Image, width: int, height: int, focus_x: float = 0.5) -> Image.Image:
    """Wie ``object-fit: cover``: füllen, mittig beschneiden."""
    scale = max(width / image.width, height / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS
    )
    left = round((resized.width - width) * focus_x)
    top = round((resized.height - height) / 2)
    return resized.crop((left, top, left + width, top + height))


def centre_crop(image: Image.Image, ratio: float) -> Image.Image:
    """Mittiger Zuschnitt auf ein Seitenverhältnis, wie GoFundMes Fassungen."""
    if image.width / image.height > ratio:
        width = round(image.height * ratio)
        left = (image.width - width) // 2
        return image.crop((left, 0, left + width, image.height))
    height = round(image.width / ratio)
    top = (image.height - height) // 2
    return image.crop((0, top, image.width, top + height))


def phone_view(image: Image.Image, title: str) -> Image.Image:
    """Die Telefonansicht: 4:3-Fassung in 375×478, mit GoFundMes Überlagerung.

    Doppelte Auflösung, damit sich das Prüfblatt lesen lässt. Die Lagen der
    Überlagerung sind am 23.09.2026 an der Kampagnenseite gemessen.
    """
    scale = 2
    width, height = 375 * scale, 478 * scale
    four_three = centre_crop(image, 4 / 3).resize((1200, 900), Image.Resampling.LANCZOS)
    view = cover(four_three, width, height).convert("RGBA")
    shade = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shade)
    start = int(height * 0.45)
    for y in range(start, height):
        alpha = int(200 * (y - start) / (height - start))
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    view = Image.alpha_composite(view, shade)
    draw = ImageDraw.Draw(view)
    draw.rounded_rectangle(
        (16 * scale, 12 * scale, 150 * scale, 38 * scale), 13 * scale, fill=(0, 0, 0, 90)
    )
    draw.text(
        (26 * scale, 16 * scale),
        "Robert Schneider",
        font=system_font(13 * scale, True),
        fill="white",
    )
    badge_top = int(height * 0.60)
    draw.rounded_rectangle(
        (70 * scale, badge_top, 305 * scale, badge_top + 20 * scale),
        4 * scale,
        fill=(207, 237, 150, 255),
    )
    draw.text(
        (80 * scale, badge_top + 2 * scale),
        "Monatliche Unterstützung benötigt",
        font=system_font(11 * scale, True),
        fill=(20, 40, 20),
    )
    font = system_font(19 * scale, True)
    y = int(height * 0.68)
    for line in wrap(title, font, width - 48 * scale, draw):
        box = draw.textbbox((0, 0), line, font=font)
        draw.text(((width - (box[2] - box[0])) / 2, y), line, font=font, fill="white")
        y += 25 * scale
    for index in range(3):
        cx = width / 2 + (index - 1) * 14 * scale
        draw.ellipse(
            (
                cx - 3 * scale,
                int(height * 0.93) - 3 * scale,
                cx + 3 * scale,
                int(height * 0.93) + 3 * scale,
            ),
            fill=(255, 255, 255, 230 if index else 255),
        )
    return view.convert("RGB")


def wrap(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    width: float,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    """Bricht einen Text auf eine Breite um."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), trial, font=font)
        if box[2] - box[0] <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def check_sheet(png: Path, title: str, target: Path) -> None:
    """Das Prüfblatt: Desktop, Telefon, Quadrat, 360 Punkte Breite, Zonen.

    Nur zum Ansehen, nicht zum Hochladen.
    """
    with Image.open(png) as source:
        image = source.convert("RGB")
    desktop = cover(image.resize((720, 405), Image.Resampling.LANCZOS), 605, 423)
    desktop = desktop.resize((908, 635), Image.Resampling.LANCZOS)
    phone = phone_view(image, title)
    square = centre_crop(image, 1.0).resize((400, 400), Image.Resampling.LANCZOS)
    thumb = image.resize((360, 203), Image.Resampling.LANCZOS)
    zones = image.copy()
    draw = ImageDraw.Draw(zones)
    draw.rectangle(SAFE_DESKTOP, outline=(80, 170, 255), width=6)
    draw.rectangle(SAFE_ALL, outline=(255, 70, 70), width=6)
    zones = zones.resize((960, 540), Image.Resampling.LANCZOS)

    gap = 40
    label_font = system_font(24, True)
    width = gap + desktop.width + gap + phone.width + gap
    lower = max(zones.height, square.height + 50 + thumb.height)
    height = gap + 40 + max(desktop.height, phone.height) + gap + 40 + lower + gap
    sheet = Image.new("RGB", (width, height), (40, 42, 46))
    draw = ImageDraw.Draw(sheet)
    x, y = gap, gap
    draw.text((x, y), "Desktop 605×423 (aus 720×405), 1,5-fach", font=label_font, fill="white")
    sheet.paste(desktop, (x, y + 40))
    px = x + desktop.width + gap
    draw.text((px, y), "Telefon 375×478 (aus 1200×900), 2-fach", font=label_font, fill="white")
    sheet.paste(phone, (px, y + 40))
    y2 = y + 40 + max(desktop.height, phone.height) + gap
    draw.text(
        (x, y2), "Zonen: rot = überall sichtbar, blau = Desktop", font=label_font, fill="white"
    )
    sheet.paste(zones, (x, y2 + 40))
    qx = x + zones.width + gap
    draw.text((qx, y2), "1:1 (960×960) und 360 px breit", font=label_font, fill="white")
    sheet.paste(square, (qx, y2 + 40))
    sheet.paste(thumb, (qx, y2 + 40 + square.height + 50))
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, "JPEG", quality=85, optimize=True)


# --- Ablauf ------------------------------------------------------------------

#: Der Kampagnentitel, wie ihn GoFundMe auf dem Telefon über das Bild legt.
TITLES = {
    "de": "Solidon3D: STL anpassen ohne CAD – ein Ein-Personen-Projekt",
    "en": "Solidon3D: Edit STL Files Without CAD – a One-Person Project",
}


def main() -> int:
    """Rendert alle Motive in den gewählten Sprachen."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sprache",
        choices=("de", "en"),
        action="append",
        help="nur diese Sprache (mehrfach möglich)",
    )
    parser.add_argument(
        "--nur",
        action="append",
        metavar="MOTIV",
        help="nur dieses Motiv, z. B. titelbild (mehrfach möglich)",
    )
    arguments = parser.parse_args()
    languages = tuple(arguments.sprache or ("de", "en"))

    work = Path(tempfile.mkdtemp(prefix="gofundme-bilder-"))
    try:
        for language in languages:
            for motif in motifs(language):
                if arguments.nur and motif.stem not in arguments.nur:
                    continue
                name = f"{motif.stem}-{language}"
                html_file = work / f"{name}.html"
                html_file.write_text(page(language, motif), encoding="utf-8")
                png = PICTURES / f"{name}.png"
                render(html_file, png, work / "profil")
                jpeg = to_jpeg(png)
                check_sheet(png, TITLES[language], CHECKS / f"{name}.jpg")
                print(
                    f"  {name}: {png.stat().st_size // 1024} KB PNG, "
                    f"{jpeg.stat().st_size // 1024} KB JPG"
                )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
