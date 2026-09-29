"""Belegte Tutorials und Shorts nach Ansage, echter Handlung und Ergebnis schneiden.

Der Helfer liest ausschließlich abgeschlossene Aufnahmen. Er verkürzt keine
Maus- oder Tastaturhandlung und zeichnet keine Bedienelemente nach.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import sys
from itertools import pairwise
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
from tools.workshop_guided_edit import BACKGROUND, _native, _subtitle  # noqa: E402


def scenes_for(source: dict[str, Any], *, short: bool) -> list[dict[str, Any]]:
    """Das nachgewiesene Ergebnis zuerst zeigen, danach die ausgewählten Lernschritte."""
    hero = next(scene for scene in source["scenes"] if scene["key"] == source["hero"])
    hook = {**hero, **source["short_hook" if short else "hook"], "key": "hook"}
    if hero.get("action_last_slide", hero["first_slide"]) > hero.get(
        "action_first_slide", hero["first_slide"]
    ):
        hook["first_slide"] = min(hero["action_last_slide"], hero["last_slide"] - 1)
    hook.pop("action_first_slide", None)
    hook.pop("action_last_slide", None)
    hook["minimum_seconds"] = 0.0
    hook["voice_before"] = hook["voice"]
    hook["voice_after"] = ""
    if hook.get("audio"):
        hook["audio_before"] = hook["audio"]
    result = [hook]
    for scene in source["scenes"]:
        if scene.get("hook_only"):
            continue
        if short and not scene.get("short"):
            continue
        scene = dict(scene)
        if short:
            for field in (
                "voice_before",
                "voice_after",
                "audio_before",
                "audio_after",
                "model_crop",
                "focus",
                "before_focus",
                "action_focus",
                "after_focus",
                "before_model_crop",
                "action_model_crop",
                "after_model_crop",
                "minimum_seconds",
                "minimum_after_action_seconds",
                "still_seconds",
                "after_still_seconds",
                "first_slide",
                "last_slide",
                "action_first_slide",
                "action_last_slide",
            ):
                if "short_" + field in scene:
                    scene[field] = scene["short_" + field]
        if "voice_before" not in scene or "voice_after" not in scene:
            raise ValueError(f"Ansage und Ergebnistext fehlen: {scene['key']}")
        result.append(scene)
    return result


def prepare(folder: Path, *, short: bool) -> Path:
    """Nur die wirklich verwendeten Abschnitte als zusammenhängende Sprachaufträge ausgeben."""
    source, capture = (read(folder / name) for name in ("editorial.json", "capture.json"))
    if not capture["complete"]:
        raise ValueError("Die Aufnahme ist unvollständig; zuerst den Kundenweg abschließen.")
    kind = "short" if short else "tutorial"
    jobs = []
    for scene in scenes_for(source, short=short):
        for part in ("before", "after"):
            sentence = scene["voice_" + part].strip()
            if sentence:
                jobs.append(
                    {
                        "target": str(
                            Path(
                                scene.get("audio_" + part)
                                or folder / "audio" / f"r3-{kind}-{scene['key']}-{part}.wav"
                            ).resolve()
                        ),
                        "language": source["language"],
                        "text": sentence,
                        "continuous": True,
                    }
                )
    target = folder / f"speech-jobs-{kind}-r3.json"
    write(target, {"jobs": jobs})
    return target


def sequence_plan(
    scenes: list[dict[str, Any]], capture: dict[str, Any], speech: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Eine Ansage hält den Vorzustand; alle wirklichen Aktionsbilder laufen in Rohdauer."""
    phases: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    seconds = 0.0
    for scene in scenes:
        first, last = int(scene["first_slide"]), int(scene["last_slide"])
        if not 0 <= first < last <= len(capture["slides"]):
            raise ValueError(f"Ungültiger Rohbildbereich: {scene['key']}")
        action_first = int(scene.get("action_first_slide", last))
        action_last = int(scene.get("action_last_slide", last))
        if not first <= action_first <= action_last <= last:
            raise ValueError(f"Handlung liegt außerhalb ihrer Szene: {scene['key']}")
        hold_frames = {}
        for hold_frame in scene.get("hold_frames", []):
            index, kept = int(hold_frame["slide"]), float(hold_frame["seconds"])
            if (
                not first <= index < last
                or not math.isfinite(kept)
                or not 0.5 <= kept < float(capture["slides"][index]["seconds"])
                or not hold_frame.get("reason")
            ):
                raise ValueError(
                    "Eine gekürzte Bildhaltung braucht einen gültigen Einzelbildbeleg."
                )
            hold_frames[index] = hold_frame
        has_action = action_last > action_first
        scene_start = seconds
        for part in ("before", "action", "after"):
            if part == "action" and not has_action:
                continue
            text = scene.get("voice_" + part, "").strip()
            if (
                part == "before"
                and not has_action
                and not text
                and scene.get("voice_after", "").strip()
            ):
                continue
            if part == "after" and not has_action and not text:
                continue
            key = f"{scene['key']}-{part}"
            audio = speech[key] if text else None
            if audio is not None and audio["text"] != text:
                raise ValueError(f"Veralteter Sprechertext: {key}")
            voice_seconds = float(audio["seconds"]) if audio else 0.0
            if part == "action":
                start, end = action_first, action_last
                duration = sum(slide["seconds"] for slide in capture["slides"][start:end])
            elif part == "before":
                start, end = first, max(first + 1, action_first)
                duration = max(0.5, voice_seconds + 0.3)
                if not has_action:
                    end = last
                    duration = max(duration, float(scene.get("minimum_seconds", 0.0)))
            else:
                start, end = (min(action_last, last - 1) if has_action else first), last
                duration = max(
                    float(scene.get("minimum_after_action_seconds", 1.5)),
                    voice_seconds + 0.5,
                    float(scene.get("minimum_seconds", 0.0)) - (seconds - scene_start),
                )
            hold = scene.get("after_hold") if part == "after" else None
            static_seconds = (
                scene.get("still_seconds")
                if not has_action
                else scene.get("after_still_seconds")
                if part == "after"
                else None
            )
            omitted = None
            if hold is not None:
                frame = int(hold["frame"])
                if not has_action or not action_last <= frame < last or not hold.get("note"):
                    raise ValueError("Eine gekürzte Wartezeit darf keine Handlung überspringen.")
                omitted = [action_last, frame]
                start, end = frame, frame + 1
                duration = max(duration, float(hold["seconds"]))
            if static_seconds is not None:
                start, end = last - 1, last
                duration = max(duration, float(static_seconds))
            source_seconds = sum(slide["seconds"] for slide in capture["slides"][start:end])
            shortened = [hold_frames[index] for index in range(start, end) if index in hold_frames]
            rendered_source_seconds = source_seconds - sum(
                float(capture["slides"][item["slide"]]["seconds"]) - float(item["seconds"])
                for item in shortened
            )
            if part == "action":
                duration = rendered_source_seconds
            # Jede Szene darf länger stehen bleiben; tatsächliche Bewegung wird nie gestaucht.
            if hold is None and static_seconds is None:
                duration = max(duration, rendered_source_seconds)
            phase = {
                "key": key,
                "scene": scene["key"],
                "part": part,
                "start": seconds,
                "duration": duration,
                "first_slide": start,
                "last_slide": end,
                "source_seconds": source_seconds,
                "playback_rate": 1.0,
            }
            if shortened:
                phase.update(
                    shortened_holds=shortened,
                    rendered_source_seconds=rendered_source_seconds,
                )
            if hold is not None:
                phase.update(
                    mode="held_result_frame",
                    omitted_wait_slides=omitted,
                    edit_note=hold["note"],
                )
            elif static_seconds is not None:
                phase["mode"] = "held_result_frame"
            phases.append(phase)
            if audio:
                events.append(
                    {
                        "key": key,
                        "start": seconds,
                        "audio": audio["path"],
                        "voice": text,
                        "voice_engine": audio["engine"],
                        "sentences": audio["sentences"],
                        "title": scene["title"],
                    }
                )
            seconds += duration
    total = math.ceil(seconds * 30) / 30
    phases[-1]["duration"] += total - seconds
    for index, event in enumerate(events):
        following = events[index + 1]["start"] if index + 1 < len(events) else total
        event["duration"] = following - event["start"]
    return phases, events


def compose(
    picture: QImage,
    source: dict[str, Any],
    scene: dict[str, Any],
    part: str,
    subtitle: str,
    *,
    short: bool,
) -> QImage:
    """Die echte Oberfläche trägt das Bild; Titel und Untertitel belegen eigene sichere Bereiche."""
    width, height = (1080, 1920) if short else (1920, 1080)
    output_size = (width, height) if short else (2560, 1440)
    canvas = QImage(*output_size, QImage.Format.Format_RGB32)
    canvas.fill(QColor(BACKGROUND))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    if not short:
        painter.scale(4 / 3, 4 / 3)
    crop = (
        scene.get(part + "_model_crop")
        or scene.get("model_crop")
        or [0, 0, picture.width(), picture.height()]
    )
    try:
        _text(
            painter,
            QRectF(60, 96 if short else 24, width - 140, 48),
            "SOLIDON3D · 0.5.1",
            28 if short else 20,
            colour="#c0cad5",
        )
        _text(
            painter,
            QRectF(60, 160 if short else 60, width - 140, 116 if short else 68),
            scene["title"],
            60 if short else 39,
            bold=True,
        )
        area = QRectF(30, 330, 990, 1000) if short else QRectF(30, 148, 1860, 862)
        focus = scene.get(part + "_focus", scene.get("focus"))
        if focus:
            model_area = QRectF(45, 330, 960, 640) if short else QRectF(30, 148, 1200, 862)
            focus_area = QRectF(0, 1010, 1080, 320) if short else QRectF(1260, 250, 630, 580)
            if not short and scene.get("wide_focus"):
                # Ganze native Erklärungssätze brauchen Breite; der Dialog bleibt daneben sichtbar.
                model_area = QRectF(30, 148, 450, 862)
                focus_area = QRectF(510, 148, 1380, 862)
            shown = _native(painter, picture, QRectF(*crop), model_area)
            _native(painter, picture, QRectF(*focus), focus_area)
        else:
            shown = _native(painter, picture, QRectF(*crop), area)
        if scene.get("marker"):
            point = scene["marker"]
            scale = shown.width() / crop[2]
            centre = QPointF(
                shown.x() + (point[0] - crop[0]) * scale,
                shown.y() + (point[1] - crop[1]) * scale,
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#f4aa44"), 5))
            painter.drawEllipse(centre, 38, 25)
        if short and subtitle:
            font = QFont("Segoe UI")
            font.setPixelSize(60)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor("white"))
            painter.drawText(QRectF(60, 1440, 885, 235), Qt.TextFlag.TextWordWrap, subtitle)
        if not short and scene.get("reference_image"):
            labels = scene["reference_image"]["labels"]
            _text(painter, QRectF(60, 1015, 1760, 44), labels[source["language"]], 24)
        if part == "after" and scene.get("after_hold"):
            _text(
                painter,
                QRectF(60, 1345 if short else 1015, width - 140, 44),
                scene["after_hold"]["note"],
                28 if short else 24,
                colour="#c0cad5",
            )
    finally:
        painter.end()
    return canvas


def render(
    folder: Path,
    *,
    short: bool,
    music_manifest: Path,
    revision: str,
    alignment_path: Path | None = None,
) -> Path:
    """Gesicherte Rohbilder, WAV-Belege und lizenzierte Themenmusik zu einer Fassung verbinden."""
    source, capture = (read(folder / name) for name in ("editorial.json", "capture.json"))
    if not capture["complete"]:
        raise ValueError("Die Aufnahme ist unvollständig; zuerst die Aufnahme abschließen.")
    kind = "short" if short else "tutorial"
    scenes = scenes_for(source, short=short)
    by_key = {scene["key"]: scene for scene in scenes}
    speech = {}
    for scene in scenes:
        for part in ("before", "after"):
            if scene["voice_" + part].strip():
                key = f"{scene['key']}-{part}"
                path = Path(scene.get("audio_" + part) or folder / "audio" / f"r3-{kind}-{key}.wav")
                speech[key] = {
                    **read(path.with_suffix(".speech.json")),
                    "path": str(path.resolve()),
                }
    if alignment_path is not None:
        apply_alignment(speech, alignment_path)
    phases, events = sequence_plan(scenes, capture, speech)
    output = folder / f"sequence-{kind}-{revision}"
    output.mkdir(exist_ok=True)
    music = next(
        track for track in read(music_manifest)["tracks"] if track["story"] == source["story"]
    )
    asset = music_manifest.parent / music["file"]
    if hashlib.sha256(asset.read_bytes()).hexdigest() != music["sha256"]:
        raise ValueError("Der Musikhash stimmt nicht mit dem Rechtebeleg überein.")
    lines = ["ffconcat version 1.0"]
    pictures = []
    number = 0
    contacts = QImage(960, math.ceil(len(scenes) / 2) * 290, QImage.Format.Format_RGB32)
    contacts.fill(QColor(BACKGROUND))
    contact_painter = QPainter(contacts)
    seen: set[str] = set()
    try:
        for phase in phases:
            scene = by_key[phase["scene"]]
            elapsed = 0.0
            hold_frames = {
                item["slide"]: item["seconds"] for item in phase.get("shortened_holds", [])
            }
            for index in range(phase["first_slide"], phase["last_slide"]):
                raw = capture["slides"][index]
                duration = float(hold_frames.get(index, raw["seconds"]))
                if index == phase["last_slide"] - 1:
                    duration += phase["duration"] - phase.get(
                        "rendered_source_seconds", phase["source_seconds"]
                    )
                picture = _image(folder / raw["path"])
                for mask in source.get("redactions", []):
                    if mask["first_slide"] <= index < mask["last_slide"]:
                        painter = QPainter(picture)
                        for box in mask["boxes"]:
                            painter.fillRect(QRectF(*box), QColor(BACKGROUND))
                        painter.end()
                reference = scene.get("reference_image")
                if reference:
                    path = Path(reference["path"])
                    if hashlib.sha256(path.read_bytes()).hexdigest() != reference["sha256"]:
                        raise ValueError(
                            "Die Bildvorlage stimmt nicht mit ihrem Quellenbeleg überein."
                        )
                    picture = _image(path)
                    scene = dict(
                        scene, model_crop=[0, 0, picture.width(), picture.height()], focus=None
                    )
                # Untertitelwechsel teilen nur die Haltezeit, keine wirkliche Handlung.
                cuts = [0.0, duration]
                if short:
                    origin = phase["start"] + elapsed
                    cuts.extend(
                        boundary - origin
                        for event in events
                        for sentence in event["sentences"]
                        for boundary in (
                            event["start"] + sentence["start"],
                            event["start"] + sentence["end"],
                        )
                        if origin < boundary < origin + duration
                    )
                cuts = sorted(set(cuts))
                for begin, end in pairwise(cuts):
                    frame = compose(
                        picture,
                        source,
                        scene,
                        phase["part"],
                        _subtitle(events, phase["start"] + elapsed + begin + 0.001),
                        short=short,
                    )
                    target = output / f"frame-{number:05d}.png"
                    _save(frame, target)
                    escaped = target.resolve().as_posix().replace("'", "'\\''")
                    lines.extend((f"file '{escaped}'", f"duration {end - begin:.8f}"))
                    pictures.append(
                        {
                            "frame": number,
                            "source_slide": index,
                            "phase": phase["key"],
                            "seconds": end - begin,
                        }
                    )
                    number += 1
                    if scene["key"] not in seen:
                        count = len(seen)
                        area = QRectF((count % 2) * 480, (count // 2) * 290, 480, 270)
                        _native(contact_painter, frame, QRectF(frame.rect()), area)
                        seen.add(scene["key"])
                elapsed += duration
    finally:
        contact_painter.end()
    _save(contacts, output / "contact.png")
    lines.append(f"file '{escaped}'")
    listing = output / "frames.ffconcat"
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(output / "phases.json", phases)
    write(output / "source-frames.json", pictures)
    total = phases[-1]["start"] + phases[-1]["duration"]
    audio = _audio_mix(output, events, total, source["music"], music_asset=asset, click_times=[])
    target = folder / f"solidon3d-{source['story']}-{source['language']}-{kind}-{revision}.mp4"
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
            f"{total:.6f}",
            "-movflags",
            "+faststart",
            str(target),
        ]
    )
    _subtitles(events, target.with_suffix(".srt"))
    write(target.with_suffix(".timeline.json"), events)
    proof = verify(
        target, total, short=short, expected_size=(1080, 1920) if short else (2560, 1440)
    )
    proof.update(
        {
            "status": "Arbeitsfassung; Sicht- und Hörfreigabe offen",
            "action_speed": 1.0,
            "voice_speed": 1.0,
            "native_capture_size": [picture.width(), picture.height()],
            "music": music["title"],
            "music_rights": music,
            "capture_sha256": hashlib.sha256((folder / "capture.json").read_bytes()).hexdigest(),
            "editorial_sha256": hashlib.sha256(
                (folder / "editorial.json").read_bytes()
            ).hexdigest(),
            "burned_speech_captions": short,
            "speech_alignment_sha256": hashlib.sha256(alignment_path.read_bytes()).hexdigest()
            if alignment_path is not None
            else None,
            "audio_placement_sha256": hashlib.sha256(
                (output / "narration-placement.json").read_bytes()
            ).hexdigest(),
        }
    )
    write(target.with_suffix(".verified.json"), proof)
    return target


def main() -> int:
    """Sprachauftrag oder Schnitt erzeugen; keine Fensteraufnahme und kein Backend starten."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "render"))
    parser.add_argument("folder", type=Path)
    parser.add_argument("--format", choices=("tutorial", "short"), default="tutorial")
    parser.add_argument("--music-manifest", type=Path)
    parser.add_argument("--revision", default="r3")
    parser.add_argument("--alignment", type=Path)
    args = parser.parse_args()
    short = args.format == "short"
    if args.mode == "prepare":
        print(prepare(args.folder, short=short))
    else:
        if args.music_manifest is None:
            parser.error("Der Schnitt benötigt --music-manifest mit Quellen- und Lizenzbeleg.")
        app = QApplication.instance() or QApplication([])
        print(
            render(
                args.folder,
                short=short,
                music_manifest=args.music_manifest,
                revision=args.revision,
                alignment_path=args.alignment,
            )
        )
        app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
