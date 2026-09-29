"""Echte Gesten in Ansage, Handlung und Ergebnis gliedern und telefonlesbar schneiden.

Die Aktionsbilder behalten ihre Rohdauer. Satzzeiten kommen aus den WAV-Belegen;
der Ausschnitt vergrößert ausschließlich vorhandene Pixel der Aufnahme.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tools.make_video import run_ffmpeg  # noqa: E402
from tools.make_workshop_shorts import _image, _save, _text  # noqa: E402
from tools.workshop_edit import (  # noqa: E402
    _audio_mix,
    _subtitles,
    apply_alignment,
    read,
    verify,
    write,
)

FPS = 30
ACCENT = "#ffb45b"
BACKGROUND = "#222831"


def interaction_plan(
    interaction: dict[str, Any],
    capture: dict[str, Any],
    script: dict[str, Any],
    speech: dict[str, dict[str, Any]],
    language: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Ansage vor der Geste; vorhandene Handlungszeit niemals verkürzen."""
    phases: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    seconds = 0.0
    for stage, words in zip(interaction["stages"], script["stages"], strict=True):
        if stage["key"] != words["key"]:
            raise ValueError("Aufnahme und Sprecherabschnitte passen nicht zusammen.")
        if stage["key"] == "apply":
            # Der Knopf muss lesbar im Bild sein, bevor seine Ansage beginnt.
            first, last = stage["before"]
            raw_seconds = sum(item["seconds"] for item in capture["slides"][first:last])
            duration = max(1.6, raw_seconds)
            phases.append(
                {
                    "key": "apply-transition",
                    "stage": "apply",
                    "part": "transition",
                    "start": seconds,
                    "duration": duration,
                    "first_slide": first,
                    "last_slide": last,
                    "source_seconds": raw_seconds,
                    "playback_rate": 1.0,
                }
            )
            seconds += duration
        for part in ("before", "action", "after"):
            first, last = stage[part]
            if stage["key"] == "apply" and part == "before":
                first = last - 1
            if last <= first:
                continue
            key = f"{stage['key']}-{part}"
            raw = capture["slides"][first:last]
            raw_seconds = sum(item["seconds"] for item in raw)
            sentence = words[language].get(part, "")
            audio = speech[key] if sentence else None
            if audio is not None and audio["text"] != sentence:
                raise ValueError(f"Die Sprachdatei enthält einen anderen Text: {key}")
            spoken = float(audio["seconds"]) if audio else 0.0
            if part == "action":
                duration = raw_seconds
            elif part == "before":
                duration = max(raw_seconds, spoken + 0.15)
                if stage["key"] == "compare":
                    # Den Rückblick erst nach der ganzen Ergebnisansage zeigen.
                    duration = max(duration, spoken + 3.5)
            else:
                duration = max(raw_seconds, spoken + words["minimum_after_action_seconds"])
            phase = {
                "key": key,
                "stage": stage["key"],
                "part": part,
                "start": seconds,
                "duration": duration,
                "first_slide": first,
                "last_slide": last,
                "source_seconds": raw_seconds,
                "playback_rate": 1.0,
            }
            phases.append(phase)
            if audio:
                events.append(
                    {
                        "key": key,
                        "start": seconds,
                        "audio": audio["path"],
                        "voice": sentence,
                        "voice_engine": audio["engine"],
                        "sentences": audio["sentences"],
                    }
                )
            seconds += duration
    # Ein Bildtakt mehr ist ein Haltebild, niemals schneller gesprochener Ton.
    total = math.ceil(seconds * FPS) / FPS
    phases[-1]["duration"] += total - seconds
    for index, event in enumerate(events):
        following = events[index + 1]["start"] if index + 1 < len(events) else total
        event["duration"] = following - event["start"]
    return phases, events


def slide_at(capture: dict[str, Any], first: int, last: int, elapsed: float) -> int:
    """Rohbilder mit ihrer aufgezeichneten Dauer durchlaufen, danach das letzte halten."""
    if not 0 <= first < last <= len(capture["slides"]):
        raise ValueError("Der Bildbereich fehlt oder liegt außerhalb der Aufnahme.")
    for index in range(first, last):
        elapsed -= capture["slides"][index]["seconds"]
        if elapsed < 0:
            return index
    return last - 1


def _blend(first: QRectF, last: QRectF, phase: float) -> QRectF:
    """Den redaktionellen Bildausschnitt ruhig verschieben, keine Modellform ändern."""
    amount = max(0.0, min(1.0, phase))
    amount = amount * amount * (3 - 2 * amount)
    return QRectF(
        first.x() + (last.x() - first.x()) * amount,
        first.y() + (last.y() - first.y()) * amount,
        first.width() + (last.width() - first.width()) * amount,
        first.height() + (last.height() - first.height()) * amount,
    )


def _native(painter: QPainter, picture: QImage, source: QRectF, target: QRectF) -> QRectF:
    """Einen ganzen Ausschnitt ohne Strecken in die freie Bildfläche setzen."""
    if not QRectF(picture.rect()).contains(source):
        raise ValueError(f"Ausschnitt liegt außerhalb des nativen Bilds: {source}")
    scale = min(target.width() / source.width(), target.height() / source.height())
    actual = QRectF(0, 0, source.width() * scale, source.height() * scale)
    actual.moveCenter(target.center())
    painter.drawImage(actual, picture, source)
    return actual


def _subtitle(events: list[dict[str, Any]], seconds: float) -> str:
    """Nur den aktuell gesprochenen Satz anzeigen."""
    for event in events:
        for sentence in event["sentences"]:
            if event["start"] + sentence["start"] <= seconds < event["start"] + sentence["end"]:
                return str(sentence["text"])
    return ""


def compose_guided(
    picture: QImage,
    interaction: dict[str, Any],
    phase: dict[str, Any],
    local_time: float,
    language: str,
    subtitle: str,
    *,
    comparison_label: str = "",
) -> QImage:
    """Modell oder Handlung groß zeigen; der Bildtext bleibt außerhalb der Bedienung."""
    canvas = QImage(1080, 1920, QImage.Format.Format_RGB32)
    canvas.fill(QColor(BACKGROUND))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    key, part = phase["stage"], phase["part"]
    bounds = interaction["bounds"]
    opening = QPointF(*bounds["opening_pixel"])
    full = QRectF(
        picture.width() * 0.275,
        picture.height() * 0.26,
        picture.width() * 0.367,
        picture.height() * 0.534,
    )
    detail = QRectF(opening.x() - 240, opening.y() - 75, 690, 625)
    area = QRectF(12, 290, 1030, 1030)
    titles = {
        "goal": ("12,3 → 14 mm", "12.3 → 14 mm"),
        "select": ("Bohrung auswählen", "Select the hole"),
        "enter": ("Durchmesser ändern", "Change the diameter"),
        "apply": ("Änderung übernehmen", "Apply the change"),
        "compare": ("Nur die Öffnung wächst", "Only the opening grows"),
        "finish": ("Erst das Rohr messen", "Measure the tube first"),
    }
    try:
        _text(
            painter,
            QRectF(60, 100, 900, 42),
            "SOLIDON3D · 0.5.1",
            28,
            colour="#c0cad5",
        )
        _text(painter, QRectF(60, 169, 900, 100), titles[key][language == "en"], 62, bold=True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(ACCENT))
        painter.drawRoundedRect(QRectF(60, 271, 110, 5), 2, 2)
        if key == "goal":
            # Die Öffnung trägt von Beginn an eine eindeutig redaktionelle Markierung.
            source = _blend(
                full, full.adjusted(25, 15, -25, -15), local_time / max(phase["duration"], 1)
            )
            shown = _native(painter, picture, source, area)
            scale = shown.width() / source.width()
            point = QPointF(
                shown.x() + (opening.x() - source.x()) * scale,
                shown.y() + (opening.y() - source.y()) * scale,
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(ACCENT), 6))
            painter.drawEllipse(point, 45, 28)
            start = point + QPointF(-130, -80)
            finish = point + QPointF(-37, -22)
            painter.drawLine(start, finish)
            painter.drawLine(finish, finish + QPointF(-21, -2))
            painter.drawLine(finish, finish + QPointF(-6, -20))
            _text(
                painter,
                QRectF(60, 1215, 900, 70),
                "Schirmaufnahme am Poolhalter"
                if language == "de"
                else "Umbrella opening in a pool holder",
                43,
                colour="#d6dce4",
            )
        elif key in ("select", "enter"):
            if key == "select" and part != "after":
                source = _blend(full, detail, local_time / 0.65) if part == "before" else detail
                _native(painter, picture, source, area)
            else:
                # Ein großer echter Maßfeld-Ausschnitt unter der zugehörigen Stelle.
                # Das ist eine Lupe, kein nachgebautes oder neu angeordnetes Formular.
                _native(painter, picture, detail, QRectF(60, 310, 900, 820))
                _text(
                    painter,
                    QRectF(60, 1125, 900, 66),
                    "Durchmesser" if language == "de" else "Diameter",
                    54,
                    colour="#c0cad5",
                )
                _native(
                    painter, picture, QRectF(*bounds["diameter_field"]), QRectF(0, 1202, 1080, 140)
                )
        elif key == "apply":
            if part == "after" or (part == "action" and local_time >= phase["duration"] - 0.4):
                _native(painter, picture, full, area)
            else:
                _native(painter, picture, detail, QRectF(60, 310, 900, 820))
                box = QRectF(*bounds["measure_box"])
                accept = QRectF(*bounds["apply_button"])
                button = QRectF(
                    accept.x() - 8,
                    accept.y() - 16,
                    box.right() - accept.x() + 8,
                    accept.height() + 32,
                )
                if part == "transition":
                    field = QRectF(*bounds["diameter_field"])
                    wide_field = QRectF(
                        field.x() - 8,
                        field.y() - 16,
                        box.right() - field.x() + 8,
                        field.height() + 32,
                    )
                    wide_buttons = QRectF(
                        wide_field.x(), button.y(), wide_field.width(), button.height()
                    )
                    finish_pan = phase["duration"] - 0.4
                    if local_time < finish_pan:
                        source = _blend(
                            wide_field,
                            wide_buttons,
                            (local_time - 0.2) / max(0.2, finish_pan - 0.2),
                        )
                    else:
                        source = _blend(wide_buttons, button, (local_time - finish_pan) / 0.3)
                else:
                    source = button
                _native(painter, picture, source, QRectF(0, 1150, 1080, 230))
        elif key == "compare":
            if comparison_label:
                viewport = bounds["viewport"]
                centre = QPointF(viewport[0] + viewport[2] / 2, viewport[1] + viewport[3] / 2)
                source = QRectF(centre.x() - 330, centre.y() - 300, 660, 660)
                _native(painter, picture, source, QRectF(30, 370, 990, 990))
                _text(
                    painter,
                    QRectF(60, 304, 900, 80),
                    comparison_label,
                    58,
                    colour=ACCENT,
                    bold=True,
                )
            else:
                _native(painter, picture, full, area)
        else:
            _native(painter, picture, full, area)
            _text(
                painter,
                QRectF(60, 1215, 900, 80),
                "14 mm sind hier ein Beispielmaß."
                if language == "de"
                else "14 mm is the example size here.",
                43,
                colour="#d6dce4",
            )
        if subtitle:
            rectangle = QRectF(60, 1440, 885, 235)
            font = QFont("Segoe UI")
            font.setPixelSize(60)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                rectangle, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop, subtitle
            )
    finally:
        painter.end()
    return canvas


def render_guided(
    folder: Path,
    script_path: Path,
    voice_folder: Path,
    *,
    preview: bool,
    music_manifest: Path | None = None,
    revision: str = "r3",
    alignment_path: Path | None = None,
) -> Path:
    """Den geführten Short mit Rohgesten, Originaltonlänge und Belegdatei erzeugen."""
    capture, interaction, source = (
        read(folder / name) for name in ("capture.json", "interaction.json", "editorial.json")
    )
    if not capture["complete"]:
        raise ValueError("Die native Aufnahme ist unvollständig.")
    script = read(script_path)
    language = capture["language"]
    speech = {}
    for stage in script["stages"]:
        for part in ("before", "after"):
            if stage[language][part]:
                key = f"{stage['key']}-{part}"
                path = voice_folder / f"r3-{key}.wav"
                speech[key] = {
                    **read(path.with_suffix(".speech.json")),
                    "path": str(path.resolve()),
                }
    if alignment_path is not None:
        apply_alignment(speech, alignment_path)
    phases, events = interaction_plan(interaction, capture, script, speech, language)
    seconds = phases[-1]["start"] + phases[-1]["duration"]
    output = folder / (("guided-preview-" if preview else "guided-short-") + revision)
    output.mkdir(exist_ok=True)
    listing = ["ffconcat version 1.0"]
    source_frames: list[dict[str, Any]] = []
    contact = QImage(1440, 1280, QImage.Format.Format_RGB32)
    contact.fill(QColor(BACKGROUND))
    contact_painter = QPainter(contact)
    contacts = 0
    seen = set()

    @lru_cache(maxsize=32)
    def raw(index: int) -> QImage:
        return _image(folder / capture["slides"][index]["path"])

    try:
        for number in range(round(seconds * FPS)):
            instant = number / FPS
            phase = next(
                item
                for item in phases
                if item["start"] <= instant < item["start"] + item["duration"] + 1e-9
            )
            local = instant - phase["start"]
            index = slide_at(capture, phase["first_slide"], phase["last_slide"], local)
            label = ""
            if phase["stage"] == "goal" and phase["part"] == "before":
                first, last = interaction["overview"]
                index = slide_at(capture, first, last, local)
            if phase["stage"] == "compare" and phase["part"] == "before":
                # Ergebnissatz zuerst auf dem Ergebnis; der Rückblick ist ausdrücklich benannt.
                comparison_start = float(speech["compare-before"]["seconds"]) + 0.3
                comparison_end = min(phase["duration"] - 0.5, comparison_start + 1.6)
                original = comparison_start <= local < comparison_end
                index = interaction["close_before" if original else "close_after"][0]
                label = (
                    ("Vorher · 12,3 mm" if original else "Nachher · 14 mm")
                    if language == "de"
                    else ("Before · 12.3 mm" if original else "After · 14 mm")
                )
            if phase["stage"] == "finish":
                index = next(stage for stage in interaction["stages"] if stage["key"] == "compare")[
                    "after"
                ][0]
            frame = compose_guided(
                raw(index),
                interaction,
                phase,
                local,
                language,
                _subtitle(events, instant),
                comparison_label=label,
            )
            target = output / f"frame-{number:05d}.png"
            _save(frame, target)
            escaped = target.resolve().as_posix().replace("'", "'\\''")
            listing.extend((f"file '{escaped}'", f"duration {1 / FPS:.8f}"))
            source_frames.append({"frame": number, "slide": index, "phase": phase["key"]})
            contact_key = phase["key"]
            if (
                contact_key
                in (
                    "goal-before",
                    "select-action",
                    "select-after",
                    "enter-action",
                    "apply-before",
                    "apply-action",
                    "compare-before",
                    "finish-before",
                )
                and contact_key not in seen
                and local >= min(phase["duration"] * 0.6, 2.0)
            ):
                phone = frame.scaled(
                    360,
                    640,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                _save(phone, output / f"phone-{contact_key}.png")
                contact_painter.drawImage((contacts % 4) * 360, (contacts // 4) * 640, phone)
                seen.add(contact_key)
                contacts += 1
    finally:
        contact_painter.end()
    _save(contact, output / "phone-contact.png")
    listing.append(f"file '{escaped}'")
    listing_path = output / "timeline.ffconcat"
    listing_path.write_text("\n".join(listing) + "\n", "utf-8")
    write(output / "source-frames.json", source_frames)
    write(output / "phases.json", phases)
    music_asset = None
    music_proof = None
    if music_manifest:
        music_proof = next(
            track for track in read(music_manifest)["tracks"] if track["story"] == source["story"]
        )
        music_asset = music_manifest.parent / music_proof["file"]
        if hashlib.sha256(music_asset.read_bytes()).hexdigest() != music_proof["sha256"]:
            raise ValueError("Das Musikasset weicht vom Herkunftsnachweis ab.")
    click_times = []
    for phase in phases:
        if phase["part"] == "action":
            click_times.append(phase["start"] + 0.6)
            if phase["stage"] == "select":
                click_times.append(phase["start"] + 1.78)
    audio = _audio_mix(
        output, events, seconds, source["music"], music_asset=music_asset, click_times=click_times
    )
    suffix = "preview-" + revision if preview else "short-1080x1920-" + revision
    target = folder / f"solidon3d-{source['story']}-{language}-{suffix}.mp4"
    run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing_path),
            "-i",
            str(audio),
            "-vf",
            "fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            f"{seconds:.6f}",
            "-movflags",
            "+faststart",
            str(target),
        ]
    )
    _subtitles(events, target.with_suffix(".srt"))
    write(target.with_suffix(".timeline.json"), events)
    proof = verify(target, seconds, short=True)
    proof.update(
        {
            "status": "Arbeitsfassung; Sicht- und Hörfreigabe offen",
            "voice_speed": 1.0,
            "action_speed": 1.0,
            "native_capture_size": [raw(0).width(), raw(0).height()],
            "capture_sha256": hashlib.sha256((folder / "capture.json").read_bytes()).hexdigest(),
            "interaction_sha256": hashlib.sha256(
                (folder / "interaction.json").read_bytes()
            ).hexdigest(),
            "speech_alignment_sha256": hashlib.sha256(alignment_path.read_bytes()).hexdigest()
            if alignment_path is not None
            else None,
            "music": music_proof["title"] if music_proof else source["music"],
            "music_rights": music_proof or "Eigene prozedurale Synthese; keine Samples",
            "voice": sorted({event["voice_engine"] for event in events}),
            "burned_speech_captions": True,
        }
    )
    write(target.with_suffix(".verified.json"), proof)
    return target


def main() -> int:
    """Die Aufnahme bleibt geschlossen; dieser Schritt liest ausschließlich Mediendateien."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--voice-folder", required=True, type=Path)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--music-manifest", type=Path)
    parser.add_argument("--revision", default="r3")
    parser.add_argument("--alignment", type=Path)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    print(
        render_guided(
            args.folder,
            args.script,
            args.voice_folder,
            preview=args.preview,
            music_manifest=args.music_manifest,
            revision=args.revision,
            alignment_path=args.alignment,
        ),
        flush=True,
    )
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
