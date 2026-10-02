"""Filme aus den Bildanleitungen des Handbuchs schneiden (Konzept Handbuch, HB-12).

    .venv\\Scripts\\python.exe tools/make_guide_video.py [sprachen …] [--nur ANLEITUNG]
        [--quelle ORDNER] [--ziel ORDNER]

Der Kunde, der den Umbau des Handbuchs anstieß, fragte nach einem
Video-Tutorial. Es entsteht aus denselben Geschichten wie die Bildanleitungen:
aus den Schrittbildern, die ``make_guides.py`` beim Release in der echten
Oberfläche aufnimmt, und aus den Sätzen der Anleitungen in der jeweiligen
Sprache. Ohne Angabe entstehen je Sprache zwei Filme, geordnet wie auf „Wo
fange ich an?“: *Vom Start bis zum Druck* und *Einzelne Aufgaben*, jeder mit
Kapitelmarken je Anleitung. ``--nur`` macht aus einzelnen Anleitungen je einen
eigenen Film.

**Kein zweiter Weg durch die Oberfläche.** Was der Film zeigt, hat die
Aufnahme geprüft; ändert sich ein Knopf, scheitert schon sie (Konzept §6).
Passen die Bilder nicht zu den Anleitungen, weil ein Satz oder ein Ziel sich
seit der Aufnahme geändert hat oder sie aus einer anderen Version stammen,
bricht dieses Werkzeug ab und nennt die Anleitung: Ein Film, der einen anderen
Schritt zeigt, als er einblendet, wäre schlechter als keiner.

**Keine Stimme.** Der Satz eines Schritts steht unter seinem Bild, die Namen,
die der Kunde im Fenster sucht, in der Farbe der Markierung; ein ruhiges,
selbst erzeugtes Musikbett trägt den Ablauf wie bei den Langfilmen
(``make_longform_video``). So bekommt jede Sprache denselben Film. Wie lange
ein Bild steht, richtet sich nach den Wörtern, die dazu zu lesen sind.

Läuft beim Release nach ``make_guides.py`` (Skill ``/erzeugen``); zwischen
zwei Versionen läuft es nicht. Die Filme landen unter ``marketing/``, das nur
lokal liegt (``.gitignore``); hochgeladen wird von Hand.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QTextDocument
from PySide6.QtWidgets import QApplication

from app.branding import APP_NAME, APP_VERSION, website_page_url
from app.core import figures, guides, manual, markup
from app.i18n import TranslatableText, _, set_language, tr
from app.i18n.catalog import available_languages, install_language

#: Wohin die Filme gehen, je Sprache ein Unterordner. ``marketing/`` liegt nur
#: lokal (Entscheidung Robert, 26.09.2026).
OUTPUT: Final = Path(__file__).resolve().parent.parent / "marketing" / "video" / "guides"

WIDTH: Final = 1920
HEIGHT: Final = 1080
FPS: Final = 30

#: Rand links und rechts, wie groß ein Satz unter dem Bild höchstens steht und
#: wie klein er werden darf, bevor das Werkzeug abbricht, statt ihn unlesbar
#: zu setzen.
SIDE: Final = 60
CAPTION_PIXELS: Final = 46
SMALLEST_PIXELS: Final = 24

#: Standzeit: ein Blick auf das Bild, dann Lesezeit je Wort. Gemessen an der
#: Lesegeschwindigkeit für Untertitel (rund drei Wörter je Sekunde), etwas
#: langsamer, weil zugleich das Bild gelesen wird.
LOOK_SECONDS: Final = 2.2
WORD_SECONDS: Final = 0.36
STEP_SECONDS: Final = (4.5, 11.0)
LEGEND_SECONDS: Final = (8.0, 32.0)
TITLE_SECONDS: Final = (4.0, 7.0)
OPENING_SECONDS: Final = 7.0
CLOSING_SECONDS: Final = 6.0

#: Überblendung zwischen zwei Standbildern, in Einzelbildern. Ein harter
#: Schnitt zwischen fünfzig Bildern wirkt wie eine Diaschau.
BLEND_FRAMES: Final = 8

#: Kapitelmarken nimmt YouTube erst ab dieser Zahl.
MIN_CHAPTERS: Final = 3

#: Das Musikbett aus ``make_longform_video`` — ruhig und ohne Samples.
MUSIC: Final = "Montagehalter aus Skizze"

_EMPHASIS: Final = re.compile(r"\*([^*]+)\*")
_STRONG: Final = re.compile(r"\*\*(.+?)\*\*")


@dataclass(frozen=True, slots=True)
class Film:
    """Ein Film: der Name seiner Datei, sein Titel und die Anleitungen darin, je ein Kapitel."""

    name: str
    title: TranslatableText | str
    chapters: tuple[guides.Guide, ...]


@dataclass(frozen=True, slots=True)
class Still:
    """Ein Standbild des Films, wie lange es steht, und was es zeigt."""

    image: QImage
    seconds: float
    chapter: str = ""
    """Die Kapitelmarke, die mit diesem Bild beginnt."""
    note: str = ""
    """Was das Bild zeigt, für ``.timeline.json``."""


def films(only: list[str]) -> list[Film]:
    """Die Filme eines Laufs — die beiden Teile von „Wo fange ich an?“ oder einzelne."""
    if only:
        chosen = [guide for guide in guides.GUIDES if guide.key in only]
        return [Film(guide.key, guide.title, (guide,)) for guide in chosen]
    titles: dict[manual.Part, TranslatableText] = {
        "start": _("Vom Start bis zum Druck"),
        "tasks": _("Einzelne Aufgaben"),
    }
    guide_by_key = {guide.key: guide for guide in guides.GUIDES}
    outline = dict(manual.OUTLINE)
    result: list[Film] = []
    for part, title in titles.items():
        chapters = tuple(guide_by_key[key] for key in outline[part] if key in guide_by_key)
        if chapters:
            result.append(Film(part, title, chapters))
    return result


def check_pictures(folder: Path, chosen: tuple[guides.Guide, ...]) -> None:
    """Abbrechen, wenn ein Bild nicht zu seiner Anleitung oder zu dieser Version gehört."""
    stamp_path = folder / "guides.json"
    if not stamp_path.is_file():
        raise SystemExit(f"{stamp_path} fehlt. Zuerst tools/make_guides.py für diese Sprache.")
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))["guides"]
    stale = []
    for guide in chosen:
        entry = stamp.get(guide.key)
        if entry is None:
            stale.append(f"{guide.key}: nie aufgenommen")
        elif entry["fingerprint"] != guides.fingerprint(guide):
            stale.append(f"{guide.key}: seit der Aufnahme geändert")
        elif entry["version"] != APP_VERSION:
            stale.append(f"{guide.key}: aufgenommen mit {entry['version']}")
    if stale:
        raise SystemExit(
            f"Die Bilder in {folder} passen nicht zu den Anleitungen ({'; '.join(stale)}). "
            "Mit tools/make_guides.py neu aufnehmen."
        )


def caption_html(text: str, accent: str) -> str:
    """Ein Schrittsatz als HTML: Namen in der Farbe der Markierung, Verweise kursiv.

    Ein Verweis auf eine Seite ist im Film nicht anklickbar. Als bloßer Text
    verschwamm der Titel im Satz („wie in Das erste eigene Teil einen
    Quader“), kursiv liest er sich als Titel (Durchsicht 28.09.2026).
    """
    marked = markup.MANUAL_LINK.sub(lambda match: f"\x02{match.group(1)}\x03", text)
    escaped = html.escape(marked, quote=False)
    escaped = _STRONG.sub(r"<b>\1</b>", escaped)
    escaped = _EMPHASIS.sub(rf'<span style="color:{accent}; font-weight:600">\1</span>', escaped)
    return escaped.replace("\x02", "<i>").replace("\x03", "</i>")


def reading_seconds(words: int, bounds: tuple[float, float]) -> float:
    """Wie lange ein Bild steht, zu dem ``words`` Wörter zu lesen sind."""
    low, high = bounds
    return round(min(high, max(low, LOOK_SECONDS + WORD_SECONDS * words)), 2)


def _words(*texts: str) -> int:
    return sum(len(markup.plain(text).split()) for text in texts)


def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def chapter_marks(events: list[dict[str, Any]]) -> str:
    """Die Kapitelmarken für die Beschreibung auf YouTube, oder nichts.

    YouTube nimmt Kapitel erst ab drei, das erste bei 0:00 und jedes mindestens
    zehn Sekunden lang. Die Titelkarte des Films allein wäre kürzer; das erste
    Kapitel beginnt deshalb mit ihr. Ein Film aus einer Anleitung hat keine.
    """
    chapters = [
        (float(event["start"]), str(event["chapter"])) for event in events if event["chapter"]
    ]
    if len(chapters) < MIN_CHAPTERS:
        return ""
    chapters[0] = (0.0, chapters[0][1])
    return "".join(f"{_clock(start)} {title}\n" for start, title in chapters)


class _Painter:
    """Zeichnet die Standbilder in den Farben des dunklen Themas der Anwendung."""

    def __init__(self) -> None:
        from app.ui.theme import THEMES

        palette = THEMES["dark"]
        self.base = QColor(palette["base"])
        self.card = QColor(palette["alternate"])
        self.text = QColor(palette["text"])
        self.muted = QColor(palette["muted"])
        self.accent = QColor(palette["highlight"])
        self.ink = QColor(palette["highlight_text"])
        self.family = QApplication.font().family()

    def canvas(self) -> tuple[QImage, QPainter]:
        image = QImage(WIDTH, HEIGHT, QImage.Format.Format_RGB32)
        image.fill(self.base)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        return image, painter

    def document(self, body: str, pixels: int, width: float, colour: QColor) -> QTextDocument:
        document = QTextDocument()
        font = QFont(self.family)
        font.setPixelSize(pixels)
        document.setDefaultFont(font)
        document.setDocumentMargin(0)
        document.setTextWidth(width)
        document.setHtml(f'<div style="color:{colour.name()}">{body}</div>')
        return document

    def rich(
        self,
        painter: QPainter,
        area: QRectF,
        body: str,
        pixels: int,
        *,
        colour: QColor | None = None,
        bold: bool = False,
        centred: bool = False,
    ) -> float:
        """Text in ``area`` setzen, notfalls kleiner, nie abgeschnitten. Gibt die Höhe zurück."""
        shown = f"<b>{body}</b>" if bold else body
        for size in range(pixels, SMALLEST_PIXELS - 1, -1):
            document = self.document(shown, size, area.width(), colour or self.text)
            height = document.size().height()
            if height <= area.height():
                top = area.top() + ((area.height() - height) / 2 if centred else 0.0)
                painter.save()
                painter.translate(area.left(), top)
                document.drawContents(painter, QRectF(0, 0, area.width(), height))
                painter.restore()
                return height
        raise SystemExit(f"Einblendung zu lang für das Bild, bitte kürzen: {markup.plain(body)}")

    def plain(
        self,
        painter: QPainter,
        area: QRectF,
        text: str,
        pixels: int,
        colour: QColor,
        *,
        bold: bool = False,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
    ) -> None:
        font = QFont(self.family)
        font.setPixelSize(pixels)
        font.setBold(bold)
        painter.setFont(font)
        painter.setPen(colour)
        painter.drawText(area, int(align | Qt.AlignmentFlag.AlignVCenter), text)

    def legend(self, painter: QPainter, area: QRectF, heading: str, labels: list[str]) -> None:
        """Satz und nummerierte Zeilen einer Legende, alle in einer Größe, die für alle passt.

        Je Zeile verkleinert, bekäme die erste den Platz und die letzte keinen;
        eine Schrift für die ganze Spalte liest sich außerdem ruhiger.
        """
        indent = 56.0
        for size in range(34, SMALLEST_PIXELS - 1, -1):
            gap = round(size * 0.55)
            top_doc = self.document(heading, size + 4, area.width(), self.text)
            docs = [
                self.document(label, size, area.width() - indent, self.text) for label in labels
            ]
            needed = top_doc.size().height() + 2 * gap
            needed += sum(doc.size().height() for doc in docs) + gap * (len(docs) - 1)
            if needed > area.height():
                continue
            top = area.top()
            for document, left, width in (
                (top_doc, area.left(), area.width()),
                *((doc, area.left() + indent, area.width() - indent) for doc in docs),
            ):
                height = document.size().height()
                if document is not top_doc:
                    number = str(docs.index(document) + 1)
                    radius = min(20.0, size * 0.72)
                    self.badge(
                        painter, QPointF(area.left() + 20, top + size * 0.68), radius, number
                    )
                painter.save()
                painter.translate(left, top)
                document.drawContents(painter, QRectF(0, 0, width, height))
                painter.restore()
                top += height + (2 * gap if document is top_doc else gap)
            return
        raise SystemExit(f"Legende zu lang für das Bild, bitte kürzen: {markup.plain(heading)}")

    def badge(self, painter: QPainter, centre: QPointF, radius: float, text: str) -> None:
        """Die Nummer wie im Bild: gefüllter Kreis in der Farbe der Markierung."""
        painter.setPen(QPen(self.ink, 3))
        painter.setBrush(self.accent)
        painter.drawEllipse(centre, radius, radius)
        font = QFont(self.family)
        font.setBold(True)
        font.setPixelSize(round(radius * 1.1))
        painter.setFont(font)
        painter.setPen(self.ink)
        painter.drawText(
            QRectF(centre.x() - radius, centre.y() - radius, 2 * radius, 2 * radius),
            int(Qt.AlignmentFlag.AlignCenter),
            text,
        )

    def picture(self, painter: QPainter, picture: QImage, area: QRectF) -> None:
        """Das Schrittbild ganz und unverzerrt, mittig in ``area``."""
        fitted = picture.scaled(
            area.size().toSize(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        left = area.left() + (area.width() - fitted.width()) / 2
        top = area.top() + (area.height() - fitted.height()) / 2
        painter.drawImage(QPointF(left, top), fitted)

    def progress(self, painter: QPainter, share: float) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.card)
        painter.drawRoundedRect(QRectF(SIDE, HEIGHT - 26, WIDTH - 2 * SIDE, 6), 3, 3)
        painter.setBrush(self.accent)
        filled = (WIDTH - 2 * SIDE) * max(0.0, min(1.0, share))
        painter.drawRoundedRect(QRectF(SIDE, HEIGHT - 26, filled, 6), 3, 3)


def _opening(draw: _Painter, film: Film) -> QImage:
    """Titel des Films und die Anleitungen darin, nummeriert wie die Kapitel."""
    image, painter = draw.canvas()
    try:
        draw.plain(painter, QRectF(120, 110, 1680, 50), APP_NAME, 34, draw.accent, bold=True)
        draw.rich(painter, QRectF(120, 170, 1680, 200), html.escape(str(film.title)), 84, bold=True)
        if len(film.chapters) > 1:
            top = 400.0
            for number, guide in enumerate(film.chapters, 1):
                draw.badge(painter, QPointF(146, top + 26), 22, str(number))
                draw.plain(painter, QRectF(196, top, 1560, 52), str(guide.title), 36, draw.text)
                top += 64
        else:
            summary = html.escape(markup.plain(str(film.chapters[0].summary)))
            draw.rich(painter, QRectF(120, 400, 1500, 200), summary, 44, colour=draw.muted)
        version = f"{tr('Version')} {APP_VERSION}"
        draw.plain(painter, QRectF(120, 990, 800, 40), version, 26, draw.muted)
    finally:
        painter.end()
    return image


def _title(draw: _Painter, film: Film, number: int, share: float) -> QImage:
    """Die Karte vor einer Anleitung: Nummer, Titel, Kurzfassung."""
    guide = film.chapters[number - 1]
    image, painter = draw.canvas()
    try:
        kicker = f"{film.title}  ·  {number} / {len(film.chapters)}"
        draw.plain(painter, QRectF(120, 300, 1680, 50), kicker, 32, draw.accent, bold=True)
        title = html.escape(str(guide.title))
        below = 370 + draw.rich(painter, QRectF(120, 370, 1680, 220), title, 80, bold=True)
        summary = html.escape(markup.plain(str(guide.summary)))
        draw.rich(painter, QRectF(120, below + 36, 1500, 200), summary, 44, colour=draw.muted)
        draw.progress(painter, share)
    finally:
        painter.end()
    return image


def _step(
    draw: _Painter, guide: guides.Guide, number: int, picture: QImage, share: float
) -> QImage:
    """Ein Schritt: Bild oben, Nummer und Satz darunter — bei einer Legende daneben."""
    one = guide.steps[number - 1]
    count = len(guide.steps)
    image, painter = draw.canvas()
    try:
        draw.plain(painter, QRectF(SIDE, 22, 1300, 48), str(guide.title), 30, draw.muted)
        if count > 1:
            counter = tr("Schritt {number} von {count}", number=number, count=count)
            draw.plain(
                painter,
                QRectF(WIDTH - SIDE - 600, 22, 600, 48),
                counter,
                30,
                draw.muted,
                align=Qt.AlignmentFlag.AlignRight,
            )
        if one.is_legend:
            draw.picture(painter, picture, QRectF(SIDE, 90, 1180, 940))
            draw.legend(
                painter,
                QRectF(1280, 110, WIDTH - SIDE - 1280, 900),
                caption_html(str(one.text), draw.accent.name()),
                [html.escape(str(mark.label)) for mark in one.marks],
            )
        else:
            draw.picture(painter, picture, QRectF(SIDE, 90, WIDTH - 2 * SIDE, 740))
            draw.badge(painter, QPointF(SIDE + 34, 928), 34, str(number))
            draw.rich(
                painter,
                QRectF(SIDE + 96, 852, WIDTH - 2 * SIDE - 96, 152),
                caption_html(str(one.text), draw.accent.name()),
                CAPTION_PIXELS,
                centred=True,
            )
        draw.progress(painter, share)
    finally:
        painter.end()
    return image


def _closing(draw: _Painter, language: str) -> QImage:
    """Wo es weitergeht: das Handbuch in der Anwendung und die Website."""
    image, painter = draw.canvas()
    try:
        draw.plain(painter, QRectF(120, 330, 1680, 50), APP_NAME, 34, draw.accent, bold=True)
        way = f"<b>{html.escape(tr('Hilfe'))} → {html.escape(tr('Handbuch …'))}</b>"
        body = html.escape(tr("Alles zum Nachlesen im Handbuch: {way} oder F1.")).replace(
            "{way}", way
        )
        below = 400 + draw.rich(painter, QRectF(120, 400, 1680, 220), body, 56)
        address = website_page_url("", language).removeprefix("https://").rstrip("/")
        draw.plain(painter, QRectF(120, below + 40, 1680, 60), address, 40, draw.accent)
    finally:
        painter.end()
    return image


def _stills(draw: _Painter, film: Film, source: Path, language: str) -> list[Still]:
    """Die Standbilder eines Films in ihrer Reihenfolge."""
    stills = [Still(_opening(draw, film), OPENING_SECONDS, note="opening")]
    total = sum(len(guide.steps) + 1 for guide in film.chapters)
    done = 0
    for number, guide in enumerate(film.chapters, 1):
        done += 1
        if len(film.chapters) > 1:
            seconds = reading_seconds(_words(str(guide.title), str(guide.summary)), TITLE_SECONDS)
            stills.append(
                Still(
                    _title(draw, film, number, done / total),
                    seconds,
                    chapter=str(guide.title),
                    note=guide.key,
                )
            )
        for step_number, one in enumerate(guide.steps, 1):
            done += 1
            key = guide.figure_key(step_number)
            figure = figures.find(key)
            if figure is None:
                raise SystemExit(f"{key}: keine Abbildung dieses Namens im Katalog")
            picture = QImage(str(source / figure.path().name))
            if picture.isNull():
                raise SystemExit(f"{source / figure.path().name}: Bild fehlt oder ist unlesbar")
            if one.is_legend:
                words = _words(str(one.text), *(str(mark.label) for mark in one.marks))
                seconds = reading_seconds(words, LEGEND_SECONDS)
            else:
                seconds = reading_seconds(_words(str(one.text)), STEP_SECONDS)
            stills.append(
                Still(
                    _step(draw, guide, step_number, picture, done / total),
                    seconds,
                    note=f"{guide.key} {step_number}: {markup.plain(str(one.text))}",
                )
            )
    stills.append(Still(_closing(draw, language), CLOSING_SECONDS, note="closing"))
    return stills


def _blend(before: QImage, after: QImage, share: float) -> QImage:
    image = before.copy()
    painter = QPainter(image)
    painter.setOpacity(share)
    painter.drawImage(0, 0, after)
    painter.end()
    return image


def _save(image: QImage, path: Path) -> None:
    if not image.save(str(path), "PNG", 60):
        raise SystemExit(f"Bild ließ sich nicht schreiben: {path}")


def _timeline(stills: list[Still], folder: Path) -> tuple[Path, float, list[dict[str, Any]]]:
    """Die Standbilder samt Überblendungen als ffconcat-Liste; dazu Länge und Ablauf."""
    lines = ["ffconcat version 1.0"]
    events: list[dict[str, Any]] = []
    frame = 1.0 / FPS
    seconds = 0.0
    last = ""
    for index, still in enumerate(stills):
        path = folder / f"{index:03d}.png"
        _save(still.image, path)
        last = path.resolve().as_posix().replace("'", "'\\''")
        lines += [f"file '{last}'", f"duration {still.seconds:.3f}"]
        events.append(
            {
                "start": round(seconds, 3),
                "seconds": still.seconds,
                "chapter": still.chapter,
                "shows": still.note,
            }
        )
        seconds += still.seconds
        if index + 1 < len(stills):
            for step in range(1, BLEND_FRAMES + 1):
                share = step / (BLEND_FRAMES + 1)
                path = folder / f"{index:03d}-{step}.png"
                _save(_blend(still.image, stills[index + 1].image, share), path)
                last = path.resolve().as_posix().replace("'", "'\\''")
                lines += [f"file '{last}'", f"duration {frame:.6f}"]
                seconds += frame
    # Der Concat-Leser nimmt die Dauer des letzten Eintrags nur, wenn danach
    # noch eine Datei steht.
    lines.append(f"file '{last}'")
    plan = folder / "timeline.ffconcat"
    plan.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return plan, seconds, events


def _probe(path: Path, seconds: float) -> dict[str, Any]:
    """Bild, Ton und Länge am fertigen Film prüfen, nicht an der Befehlszeile."""
    binary = shutil.which("ffprobe")
    if binary is None:
        raise SystemExit("ffprobe fehlt. Installieren mit: winget install Gyan.FFmpeg")
    result = subprocess.run(
        [binary, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    info = json.loads(result.stdout)
    video = next(stream for stream in info["streams"] if stream["codec_type"] == "video")
    audio = next(stream for stream in info["streams"] if stream["codec_type"] == "audio")
    duration = float(info["format"]["duration"])
    if not (
        video["width"] == WIDTH
        and video["height"] == HEIGHT
        and video["r_frame_rate"] == f"{FPS}/1"
        and video["codec_name"] == "h264"
        and audio["codec_name"] == "aac"
        and abs(duration - seconds) < 0.2
    ):
        raise SystemExit(f"Der Film entspricht nicht dem Format, bitte prüfen: {path}")
    return {
        "file": path.name,
        "seconds": round(duration, 2),
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "video": "h264",
        "audio": "aac",
        "version": APP_VERSION,
    }


def make_film(film: Film, language: str, source: Path, target: Path) -> Path:
    """Einen Film in einer Sprache schneiden, prüfen und mit Kapiteln ablegen."""
    from tools.make_longform_video import _write_longform_music
    from tools.make_video import run_ffmpeg

    check_pictures(source, film.chapters)
    draw = _Painter()
    target.mkdir(parents=True, exist_ok=True)
    movie = target / f"solidon-guides-{film.name}-{language}.mp4"
    with tempfile.TemporaryDirectory(prefix="solidon-film-") as room:
        folder = Path(room)
        stills = _stills(draw, film, source, language)
        plan, seconds, events = _timeline(stills, folder)
        music = _write_longform_music(folder / "music.wav", seconds + 0.5, MUSIC)
        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(plan),
                "-i",
                str(music),
                "-vf",
                f"fps={FPS},format=yuv420p",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-tune",
                "stillimage",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-t",
                f"{seconds:.3f}",
                "-movflags",
                "+faststart",
                str(movie),
            ]
        )
        _save(stills[0].image, movie.with_suffix(".cover.png"))
    proof = _probe(movie, seconds)
    marks = chapter_marks(events)
    if marks:
        movie.with_suffix(".chapters.txt").write_text(marks, encoding="utf-8", newline="\n")
    movie.with_suffix(".timeline.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    movie.with_suffix(".verified.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"  {movie.name}  {_clock(seconds)}  {len(stills)} Bilder", flush=True)
    return movie


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Filme aus den Bildanleitungen des Handbuchs schneiden."
    )
    parser.add_argument(
        "languages", nargs="*", metavar="SPRACHE", help="Sprachen, ohne Angabe alle"
    )
    parser.add_argument(
        "--nur",
        dest="only",
        action="append",
        default=[],
        metavar="ANLEITUNG",
        help="je Anleitung ein eigener Film (mehrfach möglich)",
    )
    parser.add_argument(
        "--quelle",
        dest="source",
        type=Path,
        default=figures.IMAGE_ROOT,
        metavar="ORDNER",
        help="Bilder der Anleitungen, je Sprache ein Unterordner (Vorgabe: app/images/manual)",
    )
    parser.add_argument(
        "--ziel",
        dest="target",
        type=Path,
        default=OUTPUT,
        metavar="ORDNER",
        help="Ordner für die Filme, je Sprache ein Unterordner (Vorgabe: marketing/video/guides)",
    )
    arguments = parser.parse_args(argv)

    known = {guide.key for guide in guides.GUIDES}
    unknown = sorted(set(arguments.only) - known)
    if unknown:
        raise SystemExit(
            f"Unbekannte Anleitung: {', '.join(unknown)}. Bekannt: {', '.join(sorted(known))}"
        )
    available = available_languages()
    wrong = [language for language in arguments.languages if language not in available]
    if wrong:
        raise SystemExit(f"Unbekannte Sprache: {', '.join(wrong)}. Da: {', '.join(available)}")

    # Nicht offscreen: Dort fehlen die Schriften (dieselbe Bedingung wie
    # ``make_figures.py``).
    os.environ.pop("QT_QPA_PLATFORM", None)
    app = QApplication.instance() or QApplication([])
    for language in arguments.languages or available:
        install_language(language)
        set_language(language)
        print(f"{language}:", flush=True)
        for film in films(arguments.only):
            make_film(film, language, arguments.source / language, arguments.target / language)
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
