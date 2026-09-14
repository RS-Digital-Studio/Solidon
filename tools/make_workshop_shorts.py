"""Kurze Begleitfilme und Titelbilder aus echten Tutorialaufnahmen schneiden.

Die Aufnahmequelle ist ``short_shots.json`` neben einem Workshopfilm.
Bildquellen und Texte bleiben an die dort belegten App-Zustände gebunden.
Es werden weder neue Modellzustände noch Bedienfelder gezeichnet.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tools.make_longform_video import _write_longform_music  # noqa: E402
from tools.make_video import run_ffmpeg  # noqa: E402
from tools.make_workshop_videos import MUSIC_STYLES  # noqa: E402

BACKGROUND = "#14161a"
ACCENT = "#e08b4e"
FOREGROUND = "#f5f7fa"
MUTED = "#bec6d0"


def _text(
    painter: QPainter,
    rectangle: QRectF,
    value: str,
    size: int,
    *,
    colour: str = FOREGROUND,
    bold: bool = False,
) -> None:
    """Text vollständig im zugewiesenen Feld halten und Überlauf ablehnen."""
    font = QFont("Segoe UI")
    font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
    flags = Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft
    for pixels in range(size, max(21, size - 14), -1):
        font.setPixelSize(pixels)
        bounds = QFontMetrics(font).boundingRect(rectangle.toRect(), int(flags), value)
        if bounds.height() <= rectangle.height() and bounds.width() <= rectangle.width():
            painter.setFont(font)
            painter.setPen(QColor(colour))
            painter.drawText(rectangle, int(flags), value)
            return
    raise ValueError(f"Einblendung zu lang; bitte kürzen: {value}")


def _image(path: Path) -> QImage:
    """Eine tatsächlich vorhandene Aufnahme laden."""
    picture = QImage(str(path))
    if picture.isNull():
        raise ValueError(f"Aufnahme fehlt oder ist unlesbar: {path}")
    return picture


def _fit_image(painter: QPainter, picture: QImage, rectangle: QRectF) -> None:
    """Das ganze Modell maßstäblich zeigen, ohne es am Rand abzuschneiden."""
    fitted = picture.scaled(
        rectangle.size().toSize(),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = rectangle.x() + (rectangle.width() - fitted.width()) / 2
    y = rectangle.y() + (rectangle.height() - fitted.height()) / 2
    painter.drawImage(QRectF(x, y, fitted.width(), fitted.height()), fitted)


def _model_image(path: Path) -> QImage:
    """Leere Ränder des gleich ausgerichteten Aufnahmefensters ausschneiden."""
    picture = _image(path)
    return picture.copy(
        0, round(picture.height() * 0.27), picture.width(), round(picture.height() * 0.56)
    )


def _usable_detail(folder: Path, detail_path: str | None) -> QImage | None:
    """Ein Bedienelement nur zeigen, wenn es im Telefonformat lesbar bleibt.

    Die ganze Merkmalskarte (schmal und hoch) oder die Bewegen-Leiste (breit
    und flach) schrumpfen im 850 x 530-Feld auf unlesbare Größe; dann ist das
    Modell groß der bessere Short.
    """
    if not detail_path:
        return None
    picture = _image(folder / detail_path)
    ratio = picture.width() / max(1, picture.height())
    return picture if 0.6 <= ratio <= 4.0 else None


def _save(image: QImage, target: Path) -> None:
    """Ein misslungenes Schreiben als Fehler melden."""
    if not image.save(str(target)):
        raise OSError(f"Bild ließ sich nicht schreiben: {target}")


def _short_frame(
    folder: Path,
    source: dict[str, Any],
    shot: dict[str, Any],
    index: int,
    count: int,
) -> QImage:
    """Telefonlesbare Einblendungen um den echten Modellzustand anordnen."""
    canvas = QImage(1080, 1920, QImage.Format.Format_RGB32)
    canvas.fill(QColor(BACKGROUND))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        language = source["language"]
        preview = source.get("preview", False)
        label = "VORSCHAU" if language == "de" else "PREVIEW"
        kicker = "SOLIDON3D" + (f" · {label} {source.get('version', '')}" if preview else "")
        _text(painter, QRectF(64, 72, 850, 64), kicker, 27, colour=ACCENT, bold=True)
        _text(painter, QRectF(64, 164, 850, 192), shot["title"], 58, bold=True)
        _text(painter, QRectF(64, 376, 850, 140), shot["detail"], 34, colour=MUTED)
        model = _model_image(folder / shot["viewport_path"])
        detail = _usable_detail(folder, shot.get("detail_path"))
        model_rect = QRectF(64, 548, 850, 420 if detail is not None else 930)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#22272e"))
        painter.drawRoundedRect(model_rect, 18, 18)
        _fit_image(painter, model, model_rect.adjusted(8, 8, -8, -8))
        if detail is not None:
            _fit_image(painter, detail, QRectF(64, 1000, 850, 530))
        _text(
            painter,
            QRectF(64, 1570, 850, 110),
            "Schritt für Schritt im ganzen Video"
            if language == "de"
            else "Full step-by-step tutorial",
            34,
            bold=True,
        )
        _text(
            painter,
            QRectF(64, 1692, 850, 64),
            "solidon3d.de" if language == "de" else "solidon3d.de/en",
            29,
            colour=ACCENT,
        )
        painter.setBrush(QColor("#414a56"))
        painter.drawRoundedRect(QRectF(64, 1790, 850, 5), 2, 2)
        painter.setBrush(QColor(ACCENT))
        painter.drawRoundedRect(QRectF(64, 1790, 850 * (index + 1) / count, 5), 2, 2)
        _text(painter, QRectF(64, 1814, 850, 45), f"{index + 1} / {count}", 24, colour=MUTED)
    finally:
        painter.end()
    return canvas


def _thumbnail(folder: Path, source: dict[str, Any], shot: dict[str, Any]) -> Path:
    """Das nachgewiesene Ergebnis neben einem kurzen Titel zeigen."""
    canvas = QImage(1280, 720, QImage.Format.Format_RGB32)
    canvas.fill(QColor(BACKGROUND))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        _text(painter, QRectF(55, 64, 450, 58), "SOLIDON3D", 31, colour=ACCENT, bold=True)
        _text(
            painter,
            QRectF(55, 198, 480, 335),
            source.get("thumbnail_title", source["title"]),
            65,
            bold=True,
        )
        _fit_image(painter, _model_image(folder / shot["viewport_path"]), QRectF(550, 80, 690, 565))
        preview = source.get("preview", False)
        language = source["language"]
        footer = "Vorschau" if language == "de" else "Preview"
        footer = (
            f"{footer} {source.get('version', '')}"
            if preview
            else "Schritt für Schritt"
            if language == "de"
            else "Step by step"
        )
        _text(painter, QRectF(55, 600, 470, 72), footer, 30, colour=MUTED)
    finally:
        painter.end()
    target = folder / f"solidon3d-{source['story']}-{source['language']}-thumbnail.png"
    _save(canvas, target)
    return target


def _probe(path: Path, seconds: float) -> dict[str, Any]:
    """Bild, Ton und vollständige Laufzeit am fertigen Container prüfen."""
    binary = shutil.which("ffprobe")
    if binary is None:
        raise RuntimeError("ffprobe fehlt; FFmpeg bereitstellen und erneut schneiden.")
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
        video["width"] == 1080
        and video["height"] == 1920
        and video["r_frame_rate"] == "30/1"
        and video["codec_name"] == "h264"
        and audio["codec_name"] == "aac"
        and abs(duration - seconds) < 0.15
        and 25.0 <= duration <= 60.0
    ):
        raise ValueError(f"Shortformat unvollständig; Container prüfen: {path}")
    return {
        "file": path.name,
        "duration": duration,
        "width": 1080,
        "height": 1920,
        "audio": "aac",
        "fps": 30,
    }


def make_short(manifest: Path) -> Path:
    """Den Schnitt aus ausschließlich belegten Aufnahmen bauen."""
    source = json.loads(manifest.read_text("utf-8"))
    folder = manifest.parent
    shots = list(source["shots"])
    copy_path = ROOT / "marketing" / "youtube" / "workshop-2026-09-copy.json"
    copy = json.loads(copy_path.read_text("utf-8"))
    metadata = next(item for item in copy["stories"] if item["id"] == source["story"])[
        source["language"]
    ]
    source["thumbnail_title"] = metadata["thumbnail_title"]
    final = next((shot for shot in reversed(shots) if shot.get("cover")), shots[-1])
    # Das fertige Ergebnis eröffnet den Film; danach ist sein wirklicher Weg sichtbar.
    hook = dict(final, title=metadata["short_title"], duration=6.0)
    shots.insert(0, hook)
    if len(shots) < 4:
        raise ValueError("Mindestens vier belegte Zustände für den Ablauf aufnehmen.")
    frames = folder / "short-frames"
    frames.mkdir(exist_ok=True)
    timeline = ["ffconcat version 1.0"]
    seconds = 0.0
    events = []
    for index, shot in enumerate(shots):
        duration = float(shot.get("duration", 6.0))
        if not 3.0 <= duration <= 9.0:
            raise ValueError("Eine Short-Einblendung braucht drei bis neun Sekunden Lesedauer.")
        path = frames / f"{index:02d}.png"
        _save(_short_frame(folder, source, shot, index, len(shots)), path)
        escaped = path.resolve().as_posix().replace("'", "'\\''")
        timeline.extend((f"file '{escaped}'", f"duration {duration:.3f}"))
        events.append(
            {
                "start": seconds,
                "duration": duration,
                "title": shot["title"],
                "detail": shot["detail"],
            }
        )
        seconds += duration
    timeline.append(f"file '{escaped}'")
    plan = frames / "timeline.ffconcat"
    plan.write_text("\n".join(timeline) + "\n", encoding="utf-8")
    music = _write_longform_music(
        frames / "music.wav", seconds + 0.4, MUSIC_STYLES[source["story"]]
    )
    target = folder / f"solidon3d-{source['story']}-{source['language']}-short-1080x1920.mp4"
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
            "fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
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
            str(target),
        ]
    )
    proof = _probe(target, seconds)
    cover = next((shot for shot in reversed(shots) if shot.get("cover")), shots[-1])
    _thumbnail(folder, source, cover)
    _save(_short_frame(folder, source, shots[0], 0, len(shots)), target.with_suffix(".cover.png"))
    target.with_suffix(".timeline.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    target.with_suffix(".verified.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(proof, ensure_ascii=False), flush=True)
    return target


def main() -> int:
    """Eine oder mehrere Aufnahmebeschreibungen verarbeiten."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=Path)
    args = parser.parse_args()
    os.environ.pop("QT_QPA_PLATFORM", None)
    app = QApplication.instance() or QApplication([])
    for manifest in args.manifests:
        make_short(manifest)
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
