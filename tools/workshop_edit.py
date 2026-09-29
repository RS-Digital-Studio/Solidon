"""Gesprochene Tutorials aus belegten Rohaufnahmen schneiden, ohne die App zu öffnen.

``prepare <editorial.json>`` schreibt den Auftrag für ``speak_piper`` oder Chatterbox.
``render <editorial.json>`` baut Querformat, Short, Untertitel und Prüfbelege.
Die Aufnahme liefert ``make_workshop_videos --recipe ... --capture-only``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import textwrap
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tools.make_longform_video import _write_longform_music  # noqa: E402
from tools.make_video import run_ffmpeg  # noqa: E402
from tools.make_workshop_shorts import _fit_image, _image, _save, _text  # noqa: E402

BACKGROUND = "#10151d"
PANEL = "#1c2430"
ACCENT = "#f3a75b"
MUTED = "#b5c0ce"


def read(path: Path) -> Any:
    """Eine redaktionelle Eingabe ohne Ausführung laden."""
    return json.loads(path.read_text("utf-8"))


def write(path: Path, value: Any) -> None:
    """Maschinenlesbare Nachweise neben dem Erzeugnis behalten."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_alignment(speech: dict[str, dict[str, Any]], path: Path) -> None:
    """Geprüfte Wortzeiten nur auf genau die dazugehörigen unveränderten WAV-Dateien anwenden."""
    alignments = read(path)["jobs"]
    for voice_meta in speech.values():
        audio = Path(voice_meta["path"]).resolve()
        aligned = next(item for item in alignments if Path(item["audio"]).resolve() == audio)
        if hashlib.sha256(audio.read_bytes()).hexdigest() != aligned["sha256"]:
            raise ValueError("Die Wortzeiten gehören zu einer anderen Sprachdatei.")
        sentences = aligned["sentences"]
        combined = " ".join(sentence["text"] for sentence in sentences)
        if " ".join(combined.split()) != " ".join(voice_meta["text"].split()):
            raise ValueError("Die Wortzeiten verändern den freigegebenen Sprechertext.")
        previous_end = 0.0
        for sentence in sentences:
            if not (
                previous_end <= sentence["start"] < sentence["end"] <= voice_meta["seconds"] + 0.001
            ):
                raise ValueError("Die Wortzeiten überlappen oder liegen außerhalb der Sprachdatei.")
            previous_end = sentence["end"]
        voice_meta["sentences"] = sentences


def scene_list(source: dict[str, Any], *, short: bool) -> list[dict[str, Any]]:
    """Das echte Ergebnis eröffnet beide Formate; Schritte behalten ihre Reihenfolge."""
    hero = next(scene for scene in source["scenes"] if scene["key"] == source["hero"])
    hook = dict(hero, key="hook", **source["short_hook" if short else "hook"])
    steps = [dict(scene) for scene in source["scenes"] if not short or scene["short"]]
    if short:
        for scene in steps:
            scene["voice"] = scene["short_voice"]
            for field in ("first_slide", "last_slide", "model_crop", "focus"):
                if f"short_{field}" in scene:
                    scene[field] = scene[f"short_{field}"]
    return [hook, *steps]


def prepare(manifest: Path) -> Path:
    """Die Stimmen beider Formate mit kurzen Sätzen und eindeutigen Zieldateien planen."""
    source = read(manifest)
    capture = read(manifest.parent / "capture.json")
    if not capture["complete"]:
        raise ValueError("Die Aufnahme ist unvollständig; zuerst die Rohaufnahme beenden.")
    jobs = []
    for short in (False, True):
        kind = "short" if short else "tutorial"
        for scene in scene_list(source, short=short):
            if not scene.get("voice", "").strip():
                raise ValueError(f"Sprechertext fehlt: {kind}/{scene['key']}")
            jobs.append(
                {
                    "target": f"audio/{kind}-{scene['key']}.wav",
                    "language": source["language"],
                    "text": scene["voice"],
                }
            )
    target = manifest.parent / "speech-manifest.json"
    write(target, {"jobs": jobs})
    return target


def _cropped(picture: QImage, box: list[int] | None) -> QImage:
    """Nur belegte Bildbereiche verwenden und einen falschen Zuschnitt ablehnen."""
    if box is None:
        return picture
    x, y, width, height = box
    if (
        min(x, y) < 0
        or min(width, height) <= 0
        or x + width > picture.width()
        or y + height > picture.height()
    ):
        raise ValueError(f"Zuschnitt liegt außerhalb der Aufnahme; Rezept prüfen: {box}")
    return picture.copy(x, y, width, height)


def scene_seconds(speech_seconds: float, scene: dict[str, Any], *, short: bool) -> float:
    """Lesedauer eines Dialogs auch bei kurzem Sprechertext vollständig stehen lassen."""
    minimum = float(scene.get("minimum_seconds", 0.0))
    spoken = speech_seconds + (0.30 if short else 0.65)
    return math.ceil(max(spoken, minimum) * 30) / 30


def compose(
    picture: QImage,
    source: dict[str, Any],
    scene: dict[str, Any],
    index: int,
    count: int,
    *,
    short: bool,
    clean_model: QImage | None = None,
) -> QImage:
    """Große Bedienungsdetails und kurze Texte in freien, telefonlesbaren Bereichen zeigen."""
    width, height = (1080, 1920) if short else (1920, 1080)
    canvas = QImage(width, height, QImage.Format.Format_RGB32)
    canvas.fill(QColor(BACKGROUND))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    try:
        left = 72 if short else 70
        text_width = 820 if short else 1730
        top = 166 if short else 40
        _text(
            painter,
            QRectF(left, top, text_width, 40),
            source.get("series_label")
            or ("SOLIDON3D / WERKSTATT" if source["language"] == "de" else "SOLIDON3D / WORKSHOP"),
            25,
            colour=ACCENT,
            bold=True,
        )
        _text(
            painter,
            QRectF(left, top + 70, text_width, 170 if short else 100),
            scene["title"],
            57 if short else 56,
            bold=True,
        )
        focus = scene.get("focus")
        model = _cropped(picture, scene.get("model_crop") or [315, 75, 1350, 960])
        if clean_model is not None:
            model = clean_model.copy(
                0,
                round(clean_model.height() * 0.14),
                clean_model.width(),
                round(clean_model.height() * 0.76),
            )
        if short:
            model_rect = QRectF(left, 490 if focus else 525, 820, 310 if focus else 730)
            detail_rect = QRectF(left, 815, 820, 630)
            note_rect = QRectF(left, 1458 if focus else 1320, 820, 140)
        else:
            model_rect = QRectF(70, 244, 1090 if focus else 1780, 690)
            detail_rect = QRectF(1210, 244, 640, 690)
            note_rect = QRectF(70, 970, 1780, 65)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PANEL))
        painter.drawRoundedRect(model_rect, 24, 24)
        _fit_image(painter, model, model_rect.adjusted(10, 10, -10, -10))
        if focus:
            painter.drawRoundedRect(detail_rect, 20, 20)
            _fit_image(painter, _cropped(picture, focus), detail_rect.adjusted(12, 12, -12, -12))
        if not short:
            _text(painter, note_rect, scene["detail"], 30, colour=MUTED)
        if scene.get("time_compressed"):
            label = (
                "Zeitraffer · Wartezeiten gekürzt"
                if source["language"] == "de"
                else "Time-lapse · waits shortened"
            )
            _text(
                painter,
                QRectF(left, 431 if short else 1025, text_width, 42),
                label,
                20,
                colour=MUTED,
            )
        progress_y = 1646 if short else 1070
        painter.setBrush(QColor("#384250"))
        painter.drawRoundedRect(QRectF(left, progress_y, text_width, 5), 2, 2)
        painter.setBrush(QColor(ACCENT))
        painter.drawRoundedRect(QRectF(left, progress_y, text_width * (index + 1) / count, 5), 2, 2)
    finally:
        painter.end()
    return canvas


def timestamp(seconds: float) -> str:
    """SRT-Zeit aus Millisekunden, einschließlich eines möglichen Übertrags."""
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    whole, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{whole:02},{millis:03}"


def _subtitles(events: list[dict[str, Any]], target: Path) -> None:
    """Satzzeiten aus den tatsächlich erzeugten Audiodateien verwenden."""
    entries: list[str] = []
    for event in events:
        for sentence in event["sentences"]:
            start, end = event["start"] + sentence["start"], event["start"] + sentence["end"]
            entries.append(
                f"{len(entries) + 1}\n{timestamp(start)} --> {timestamp(end)}\n{sentence['text']}\n"
            )
    target.write_text("\n".join(entries), encoding="utf-8")


def _short_captions(events: list[dict[str, Any]], target: Path) -> None:
    """Ganze gesprochene Sätze im freien Hochformatbereich einbrennen."""

    def ass_time(seconds: float) -> str:
        ticks = round(seconds * 100)
        hours, ticks = divmod(ticks, 360000)
        minutes, ticks = divmod(ticks, 6000)
        whole, ticks = divmod(ticks, 100)
        return f"{hours}:{minutes:02}:{whole:02}.{ticks:02}"

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Segoe UI,38,&H00FFFFFF,&H00FFFFFF,&H001D1510,&H001D1510,"
        "0,0,0,0,100,100,0,0,3,3,0,2,72,188,320,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for event in events:
        for sentence in event["sentences"]:
            spoken = sentence["text"].replace("{", "").replace("}", "")
            caption = r"\N".join(textwrap.wrap(spoken, width=40, break_long_words=False))
            start = ass_time(event["start"] + sentence["start"])
            end = ass_time(event["start"] + sentence["end"])
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{caption}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def thumbnail(manifest: Path) -> Path:
    """Kurzer Nutzen neben einem unveränderten nativen Ergebnisbild."""
    source = read(manifest)
    canvas = QImage(1280, 720, QImage.Format.Format_RGB32)
    canvas.fill(QColor(BACKGROUND))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        _text(painter, QRectF(54, 65, 480, 50), "SOLIDON3D", 31, colour=ACCENT, bold=True)
        _text(painter, QRectF(54, 175, 505, 365), source["thumbnail"], 70, bold=True)
        if source.get("thumbnail_source"):
            picture = _cropped(
                _image(manifest.parent / source["thumbnail_source"]), source["thumbnail_crop"]
            )
        else:
            picture = _image(manifest.parent / "shots" / f"{source['hero']}.png")
            picture = picture.copy(
                0, round(picture.height() * 0.16), picture.width(), round(picture.height() * 0.72)
            )
        target = QRectF(564, 60, 670, 590)
        _fit_image(painter, picture, target)
        if source.get("thumbnail_focus"):
            scale = min(target.width() / picture.width(), target.height() / picture.height())
            x, y = source["thumbnail_focus"]
            crop_x, crop_y, _, _ = source["thumbnail_crop"]
            point = QPointF(
                target.center().x() - picture.width() * scale / 2 + (x - crop_x) * scale,
                target.center().y() - picture.height() * scale / 2 + (y - crop_y) * scale,
            )
            painter.setPen(QPen(QColor(ACCENT), 6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(point, 33, 25)
            end = point + QPointF(-34, 26)
            start = QPointF(510, 440)
            painter.drawLine(start, end)
            angle = math.atan2(end.y() - start.y(), end.x() - start.x())
            for side in (-0.5, 0.5):
                painter.drawLine(
                    end, end - QPointF(28 * math.cos(angle + side), 28 * math.sin(angle + side))
                )
        if source.get("thumbnail_label"):
            _text(
                painter,
                QRectF(54, 520, 500, 70),
                source["thumbnail_label"],
                49,
                colour=ACCENT,
                bold=True,
            )
        _text(
            painter,
            QRectF(54, 600, 500, 80),
            "SCHRITT FÜR SCHRITT" if source["language"] == "de" else "STEP BY STEP",
            28,
            colour=MUTED,
        )
    finally:
        painter.end()
    path = manifest.parent / f"solidon3d-{source['story']}-{source['language']}-thumbnail.jpg"
    if not canvas.save(str(path), b"JPEG", 94):
        raise OSError(f"Titelbild ließ sich nicht speichern: {path}")
    return path


def _voice_track(folder: Path, scenes: list[dict[str, Any]], seconds: float) -> Path:
    """Nach allen Filtern samplegenau polstern und Sprache absolut in die Zeitleiste setzen."""
    rate = 48000
    total = round(seconds * rate)
    target = folder / "narration.wav"
    proof = []
    written = 0
    with wave.open(str(target), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(rate)
        for index, scene in enumerate(scenes):
            start = round(float(scene["start"]) * rate)
            end = (
                round(float(scenes[index + 1]["start"]) * rate)
                if index + 1 < len(scenes)
                else total
            )
            count = end - start
            if start < written or count <= 0 or end > total:
                raise ValueError("Sprachabschnitte überlappen oder liegen außerhalb des Films.")
            padded = folder / f"voice-{index:02d}.wav"
            run_ffmpeg(
                [
                    "-i",
                    scene["audio"],
                    "-af",
                    "highpass=f=70,loudnorm=I=-18:TP=-2:LRA=7,"
                    f"aresample=48000,asetpts=N/SR/TB,apad=whole_len={count},atrim=end_sample={count}",
                    "-ar",
                    str(rate),
                    "-ac",
                    "2",
                    "-c:a",
                    "pcm_s16le",
                    str(padded),
                ]
            )
            with wave.open(str(padded), "rb") as clip:
                if (
                    clip.getframerate(),
                    clip.getnchannels(),
                    clip.getsampwidth(),
                    clip.getnframes(),
                ) != (rate, 2, 2, count):
                    raise ValueError(
                        f"Sprachclip hat nach den Filtern die falsche Samplezahl: {padded}"
                    )
                samples = clip.readframes(count)
            output.writeframes(b"\0" * ((start - written) * 4))
            output.writeframes(samples)
            written = end
            proof.append(
                {
                    "key": scene.get("key", str(index)),
                    "start_sample": start,
                    "end_sample": end,
                    "samples": count,
                    "rate": rate,
                    "source_sha256": hashlib.sha256(Path(scene["audio"]).read_bytes()).hexdigest(),
                    "padded_sha256": hashlib.sha256(padded.read_bytes()).hexdigest(),
                }
            )
        output.writeframes(b"\0" * ((total - written) * 4))
    write(folder / "narration-placement.json", {"rate": rate, "samples": total, "clips": proof})
    return target


def _audio_mix(
    folder: Path,
    scenes: list[dict[str, Any]],
    seconds: float,
    music: str,
    *,
    music_asset: Path | None = None,
    click_times: list[float] | None = None,
) -> Path:
    """Sprache, leise eigenständige Musik und kurze Schnittakzente zusammenführen."""
    import numpy as np

    voice = _voice_track(folder, scenes, seconds)
    if music_asset is None:
        bed = _write_longform_music(folder / "music.wav", seconds + 0.1, music)
        bed_gain = 0.25
    else:
        bed = folder / "music.wav"
        run_ffmpeg(
            [
                "-stream_loop",
                "-1",
                "-i",
                str(music_asset),
                "-af",
                "loudnorm=I=-30:TP=-8:LRA=11,afade=t=in:st=0:d=0.8,"
                f"afade=t=out:st={max(0.0, seconds - 1.2):.6f}:d=1.2",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-t",
                f"{seconds:.6f}",
                str(bed),
            ]
        )
        bed_gain = 1.0
    rate = 48000
    accents = np.zeros((round(seconds * rate), 2), dtype=np.float64)
    cues = click_times if click_times is not None else [scene["start"] for scene in scenes[1:]]
    for index, cue in enumerate(cues, 1):
        start = round(cue * rate)
        length = min(round(rate * 0.1), len(accents) - start)
        local = np.arange(length) / rate
        click = 0.09 * np.sin(2 * math.pi * (550 + index * 45) * local) * np.exp(-local * 48)
        accents[start : start + length] += click[:, None]
    effects = folder / "accents.wav"
    with wave.open(str(effects), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes((accents * 32767).astype("<i2").tobytes())
    mixed = folder / "mixed.wav"
    run_ffmpeg(
        [
            "-i",
            str(voice),
            "-i",
            str(bed),
            "-i",
            str(effects),
            "-filter_complex",
            f"[0:a]asplit=2[voice][control];[1:a]volume={bed_gain}[bed];"
            "[bed][control]sidechaincompress=threshold=0.06:ratio=5:attack=20:release=300[duck];"
            "[voice][duck][2:a]amix=inputs=3:normalize=0,loudnorm=I=-16:TP=-2:LRA=9,"
            "aresample=48000,asetpts=N/SR/TB,"
            f"apad=whole_len={round(seconds * rate)},atrim=end_sample={round(seconds * rate)}[out]",
            "-map",
            "[out]",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(mixed),
        ]
    )
    with wave.open(str(mixed), "rb") as output:
        if output.getframerate() != rate or output.getnframes() != round(seconds * rate):
            raise ValueError("Die fertige Mischung hat nicht die geplante Samplezahl.")
    return mixed


def verify(
    path: Path,
    expected_seconds: float,
    *,
    short: bool,
    expected_size: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Format, Laufzeit, Bildrate und die vollständige Dekodierbarkeit prüfen."""
    binary = shutil.which("ffprobe")
    if not binary:
        raise RuntimeError("ffprobe fehlt; vor dem Veröffentlichen bereitstellen.")
    result = subprocess.run(
        [binary, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    data = json.loads(result.stdout)
    video = next(stream for stream in data["streams"] if stream["codec_type"] == "video")
    audio = next(stream for stream in data["streams"] if stream["codec_type"] == "audio")
    width, height = expected_size or ((1080, 1920) if short else (1920, 1080))
    seconds = float(data["format"]["duration"])
    if (
        video["width"],
        video["height"],
        video["codec_name"],
        video["r_frame_rate"],
        audio["codec_name"],
    ) != (width, height, "h264", "30/1", "aac") or abs(seconds - expected_seconds) > 0.12:
        raise ValueError(f"Filmformat oder Laufzeit weicht ab; Export prüfen: {path}")
    ffmpeg = shutil.which("ffmpeg")
    subprocess.run(
        [ffmpeg or "ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
        check=True,
        capture_output=True,
    )
    return {
        "file": path.name,
        "seconds": seconds,
        "width": width,
        "height": height,
        "fps": 30,
        "audio": "aac",
        "video": "h264",
        "decoded": True,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }


def render(manifest: Path, *, short: bool) -> Path:
    """Rohzustände mit der echten Sprechdauer neu schneiden und die Herkunft behalten."""
    source = read(manifest)
    capture = read(manifest.parent / "capture.json")
    if not capture["complete"]:
        raise ValueError("Die Aufnahme ist unvollständig; zuerst aufnehmen.")
    kind = "short" if short else "tutorial"
    folder = manifest.parent / f"edit-{kind}"
    folder.mkdir(exist_ok=True)
    scenes = scene_list(source, short=short)
    lines = ["ffconcat version 1.0"]
    seconds = 0.0
    events = []
    contact = QImage(960, math.ceil(len(scenes) / 2) * 300, QImage.Format.Format_RGB32)
    contact.fill(QColor(BACKGROUND))
    contact_painter = QPainter(contact)
    image_count = 0
    try:
        for index, scene in enumerate(scenes):
            audio = manifest.parent / "audio" / f"{kind}-{scene['key']}.wav"
            speech = read(audio.with_suffix(".speech.json"))
            if speech["text"] != scene["voice"]:
                raise ValueError(f"Sprechertext geändert; Szene erneut sprechen: {scene['key']}")
            duration = scene_seconds(speech["seconds"], scene, short=short)
            raw = capture["slides"][scene["first_slide"] : scene["last_slide"]]
            if not raw:
                raise ValueError(f"Keine Rohbilder für {scene['key']}; Aufnahme prüfen.")
            source_seconds = sum(slide["seconds"] for slide in raw)
            scale = duration / source_seconds
            scene["time_compressed"] = scale < 0.9 and len(raw) > 1
            cover = None
            for slide_index, slide in enumerate(raw):
                picture = _image(manifest.parent / slide["path"])
                absolute_slide = scene["first_slide"] + slide_index
                for redaction in source.get("redactions", []):
                    if redaction["first_slide"] <= absolute_slide < redaction["last_slide"]:
                        masking = QPainter(picture)
                        for box in redaction["boxes"]:
                            masking.fillRect(QRectF(*box), QColor(BACKGROUND))
                        masking.end()
                frame = compose(picture, source, scene, index, len(scenes), short=short)
                target_frame = folder / f"frame-{image_count:05d}.png"
                _save(frame, target_frame)
                escaped = target_frame.resolve().as_posix().replace("'", "'\\''")
                lines.extend((f"file '{escaped}'", f"duration {slide['seconds'] * scale:.8f}"))
                if slide_index == len(raw) // 2:
                    cover = frame
                image_count += 1
            if cover is not None:
                _fit_image(
                    contact_painter, cover, QRectF((index % 2) * 480, (index // 2) * 300, 480, 290)
                )
                if index == 0:
                    _save(cover, folder / "cover.png")
            events.append(
                {
                    "key": scene["key"],
                    "start": seconds,
                    "duration": duration,
                    "title": scene["title"],
                    "voice": scene["voice"],
                    "audio": str(audio),
                    "sentences": speech["sentences"],
                    "first_slide": scene["first_slide"],
                    "last_slide": scene["last_slide"],
                    "source_note": scene.get("source_note"),
                    "source_seconds": source_seconds,
                    "playback_rate": 1.0 / scale,
                    "voice_engine": speech["engine"],
                }
            )
            seconds += duration
    finally:
        contact_painter.end()
    _save(contact, folder / "contact.png")
    if short and not 20 <= seconds <= 59:
        raise ValueError(
            f"Short hat {seconds:.1f} Sekunden; Sprechertext auf 25 bis 45 Sekunden kürzen."
        )
    lines.append(f"file '{escaped}'")
    listing = folder / "timeline.ffconcat"
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    audio = _audio_mix(folder, events, seconds, source["music"])
    suffix = "short-1080x1920" if short else "tutorial"
    revision = "-" + source["export_revision"] if source.get("export_revision") else ""
    target = (
        manifest.parent / f"solidon3d-{source['story']}-{source['language']}-{suffix}{revision}.mp4"
    )
    _subtitles(events, target.with_suffix(".srt"))
    video_filter = "fps=30,format=yuv420p"
    if short:
        captions = folder / "captions.ass"
        _short_captions(events, captions)
        escaped_captions = captions.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
        video_filter += f",ass=filename='{escaped_captions}'"
    run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-i",
            str(audio),
            "-vf",
            video_filter,
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
    write(target.with_suffix(".timeline.json"), events)
    proof = verify(target, seconds, short=short)
    proof.update(
        {
            "music": source["music"],
            "music_rights": "Eigene prozedurale Synthese; keine Samples",
            "voice": sorted({event["voice_engine"] for event in events}),
            "series_label": source.get("series_label"),
            "redactions": source.get("redactions", []),
            "burned_speech_captions": short,
            "captured_at": source["captured_at"],
            "source_files": source["source_files"],
            "native_slide_count": image_count,
        }
    )
    write(target.with_suffix(".verified.json"), proof)
    return target


def main() -> int:
    """Vorbereitung und Export bleiben getrennte, wiederholbare Schritte."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "render"))
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--only", choices=("tutorial", "short"))
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare(args.manifest))
        return 0
    app = QApplication.instance() or QApplication([])
    for short in (False, True):
        if args.only and args.only != ("short" if short else "tutorial"):
            continue
        print(render(args.manifest, short=short), flush=True)
    print(thumbnail(args.manifest), flush=True)
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
