"""Schnittverträge der Medienwerkzeuge, ohne Fenster und ohne Sprachmodell."""

from __future__ import annotations

import hashlib
import json
import re
import wave

import pytest

from tools import make_longform_video, workshop_edit, workshop_guided_edit, workshop_sequence_edit


def test_voice_samples_are_placed_on_absolute_boundaries_after_all_filters(tmp_path, monkeypatch):
    clips = []
    for number in (1, 2):
        path = tmp_path / f"source-{number}.wav"
        path.write_bytes(bytes([number]))
        clips.append(path)
    shortened = False

    def normalize(arguments):
        filters = arguments[arguments.index("-af") + 1]
        assert filters.index("loudnorm") < filters.index("apad") < filters.index("atrim")
        count = int(re.search(r"end_sample=(\d+)", filters).group(1))
        value = bytes([1 if arguments[1] == str(clips[0]) else 2, 0]) * 2
        with wave.open(arguments[-1], "wb") as output:
            output.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
            output.writeframes(value * (count - int(shortened)))

    monkeypatch.setattr(workshop_edit, "run_ffmpeg", normalize)
    scenes = [
        {"start": 0.1, "duration": 0.23501, "audio": str(clips[0])},
        {"start": 0.33501, "duration": 0.26499, "audio": str(clips[1])},
    ]
    result = workshop_edit._voice_track(tmp_path, scenes, 0.6)
    with wave.open(str(result), "rb") as track:
        assert track.getnframes() == 28800
        data = track.readframes(track.getnframes())
    second = round(0.33501 * 48000)
    assert data[: 4800 * 4] == b"\0" * (4800 * 4)
    assert data[(second - 1) * 4 : second * 4] == bytes([1, 0, 1, 0])
    assert data[second * 4 : (second + 1) * 4] == bytes([2, 0, 2, 0])
    shortened = True
    with pytest.raises(ValueError, match="falsche Samplezahl"):
        workshop_edit._voice_track(tmp_path, scenes, 0.6)


def test_visible_customer_dialog_keeps_its_native_window_and_modality():
    from PySide6.QtCore import QPoint

    class Window:
        def mapToGlobal(self, point):  # noqa: N802 — Qt-Vertrag des Prüfstellvertreters
            return point + QPoint(3000, 80)

        def width(self):
            return 2560

        def height(self):
            return 1440

    class Dialog:
        def isVisible(self):  # noqa: N802 — Qt-Vertrag des Prüfstellvertreters
            return True

        def width(self):
            return 960

        def height(self):
            return 900

        def move(self, x, y):
            self.position = (x, y)

    dialog = Dialog()
    make_longform_video._place_dialog(Window(), dialog)
    assert dialog.position == (3800, 255)


def source():
    """Ein kleiner Aufnahmeplan mit Ergebnis und einem echten Handlungsschritt."""
    return {
        "hero": "result",
        "language": "de",
        "hook": {"title": "Ergebnis", "voice": "Das Ergebnis."},
        "short_hook": {"title": "Kurz", "voice": "Ein kurzer Einstieg."},
        "scenes": [
            {
                "key": "action",
                "short": True,
                "voice": "Ein Schritt.",
                "short_voice": "Kurz erklärt.",
                "first_slide": 2,
                "last_slide": 5,
            },
            {
                "key": "result",
                "short": False,
                "voice": "Das Modell bleibt änderbar.",
                "short_voice": "",
                "first_slide": 5,
                "last_slide": 8,
            },
        ],
    }


def test_short_keeps_the_proven_action_order_and_does_not_rewrite_the_source():
    plan = source()
    original = json.dumps(plan)
    cut = workshop_edit.scene_list(plan, short=True)
    assert [scene["key"] for scene in cut] == ["hook", "action"]
    assert cut[0]["first_slide"] == 5
    assert cut[1]["voice"] == "Kurz erklärt."
    assert cut[1]["last_slide"] == 5
    assert json.dumps(plan) == original


def test_incomplete_capture_never_produces_a_speech_manifest(tmp_path):
    manifest = tmp_path / "editorial.json"
    workshop_edit.write(manifest, source())
    workshop_edit.write(tmp_path / "capture.json", {"complete": False})
    with pytest.raises(ValueError, match="unvollständig"):
        workshop_edit.prepare(manifest)
    assert not (tmp_path / "speech-manifest.json").exists()


def test_short_can_show_a_readable_native_detail_without_recutting_the_tutorial():
    plan = source()
    plan["scenes"][0].update(
        short_first_slide=3,
        short_last_slide=4,
        short_focus=[40, 50, 200, 100],
        short_model_crop=[0, 0, 300, 200],
    )
    short = workshop_edit.scene_list(plan, short=True)[1]
    tutorial = workshop_edit.scene_list(plan, short=False)[1]
    assert (short["first_slide"], short["last_slide"]) == (3, 4)
    assert short["focus"] == [40, 50, 200, 100]
    assert tutorial["first_slide"] == 2
    assert tutorial["last_slide"] == 5
    assert "focus" not in tutorial


def test_gesture_short_keeps_its_own_approved_audio_targets():
    plan = source()
    plan["scenes"][0].update(
        voice_before="Tutorialansage.",
        voice_after="Tutorialergebnis.",
        short_voice_before="Kurze Ansage.",
        short_voice_after="Kurzes Ergebnis.",
        audio_before="tutorial-before.wav",
        audio_after="tutorial-after.wav",
        short_audio_before="short-before.wav",
        short_audio_after="short-after.wav",
    )
    short = workshop_sequence_edit.scenes_for(plan, short=True)[1]
    assert short["audio_before"] == "short-before.wav"
    assert short["audio_after"] == "short-after.wav"
    assert short["voice_before"] == "Kurze Ansage."
    assert plan["scenes"][0]["audio_before"] == "tutorial-before.wav"


def test_dialog_reading_time_is_not_cut_down_to_the_narration():
    assert workshop_edit.scene_seconds(8.0, {"minimum_seconds": 36.0}, short=False) == 36.0
    assert workshop_edit.scene_seconds(40.0, {"minimum_seconds": 36.0}, short=False) > 40.0


def test_speech_jobs_use_the_actual_selected_format_text(tmp_path):
    manifest = tmp_path / "editorial.json"
    workshop_edit.write(manifest, source())
    workshop_edit.write(tmp_path / "capture.json", {"complete": True})
    result = workshop_edit.read(workshop_edit.prepare(manifest))
    jobs = {job["target"]: job for job in result["jobs"]}
    assert len(jobs) == 5
    assert jobs["audio/tutorial-action.wav"]["text"] == "Ein Schritt."
    assert jobs["audio/short-action.wav"]["text"] == "Kurz erklärt."
    assert "audio/short-result.wav" not in jobs


def test_empty_narration_is_rejected_before_starting_a_voice(tmp_path):
    plan = source()
    plan["scenes"][0]["short_voice"] = " "
    manifest = tmp_path / "editorial.json"
    workshop_edit.write(manifest, plan)
    workshop_edit.write(tmp_path / "capture.json", {"complete": True})
    with pytest.raises(ValueError, match="short/action"):
        workshop_edit.prepare(manifest)


def test_subtitles_keep_measured_sentence_times_across_a_minute(tmp_path):
    events = [
        {"start": 59.75, "sentences": [{"start": 0.25, "end": 2.5, "text": "Vierzehn Millimeter."}]}
    ]
    path = tmp_path / "speech.srt"
    workshop_edit._subtitles(events, path)
    assert path.read_text("utf-8") == ("1\n00:01:00,000 --> 00:01:02,250\nVierzehn Millimeter.\n")
    assert workshop_edit.timestamp(59.9997) == "00:01:00,000"


def test_burned_captions_use_the_same_times_and_keep_control_characters_out(tmp_path):
    events = [
        {
            "start": 3.0,
            "sentences": [
                {
                    "start": 0.25,
                    "end": 2.5,
                    "text": "{Feld} Vierzehn Millimeter eintragen und die Vorschau kontrollieren.",
                }
            ],
        }
    ]
    path = tmp_path / "speech.ass"
    workshop_edit._short_captions(events, path)
    text = path.read_text("utf-8")
    assert "PlayResX: 1080" in text
    assert "0:00:03.25,0:00:05.50" in text
    assert "{Feld}" not in text
    assert r"\N" in text


def test_guided_cut_speaks_before_action_and_keeps_all_native_action_time():
    interaction = {
        "stages": [{"key": "select", "before": [0, 1], "action": [1, 3], "after": [3, 4]}]
    }
    capture = {"slides": [{"seconds": value} for value in (1.0, 0.7, 3.6, 1.5)]}
    script = {
        "stages": [
            {
                "key": "select",
                "de": {"before": "Ich wähle die Bohrung.", "after": "Zwölf Komma drei."},
                "minimum_after_action_seconds": 1.5,
            }
        ]
    }
    speech = {
        "select-before": {
            "text": "Ich wähle die Bohrung.",
            "seconds": 2.0,
            "path": "before.wav",
            "engine": "test",
            "sentences": [],
        },
        "select-after": {
            "text": "Zwölf Komma drei.",
            "seconds": 1.0,
            "path": "after.wav",
            "engine": "test",
            "sentences": [],
        },
    }
    phases, events = workshop_guided_edit.interaction_plan(
        interaction, capture, script, speech, "de"
    )
    action = phases[1]
    assert action["start"] >= 2.0
    assert action["duration"] == pytest.approx(4.3)
    assert action["playback_rate"] == 1.0
    assert events[1]["start"] == pytest.approx(action["start"] + 4.3)
    assert phases[-1]["duration"] >= 2.5
    speech["select-after"]["text"] = "Ein veralteter Sprechertext."
    with pytest.raises(ValueError, match="anderen Text"):
        workshop_guided_edit.interaction_plan(interaction, capture, script, speech, "de")


def test_guided_cut_keeps_intermediate_keystrokes_and_only_holds_after_the_last_frame():
    capture = {"slides": [{"seconds": value} for value in (0.6, 0.45, 0.45, 0.8)]}
    select = workshop_guided_edit.slide_at
    assert select(capture, 0, 4, 0.59) == 0
    assert select(capture, 0, 4, 0.7) == 1
    assert select(capture, 0, 4, 1.2) == 2
    assert select(capture, 0, 4, 2.0) == 3
    assert select(capture, 0, 4, 9.0) == 3
    with pytest.raises(ValueError, match="Bildbereich"):
        select(capture, 2, 2, 0.0)


def test_apply_camera_arrives_before_narration_and_the_real_click():
    interaction = {
        "stages": [{"key": "apply", "before": [0, 2], "action": [2, 3], "after": [3, 4]}]
    }
    capture = {"slides": [{"seconds": value} for value in (0.4, 0.6, 1.2, 1.0)]}
    script = {
        "stages": [
            {
                "key": "apply",
                "de": {"before": "Mit Übernehmen wende ich die Änderung an."},
                "minimum_after_action_seconds": 1.0,
            }
        ]
    }
    speech = {
        "apply-before": {
            "text": script["stages"][0]["de"]["before"],
            "seconds": 2.1,
            "path": "apply.wav",
            "engine": "test",
            "sentences": [],
        }
    }
    phases, events = workshop_guided_edit.interaction_plan(
        interaction, capture, script, speech, "de"
    )
    transition, instruction, action, result = phases
    assert transition["part"] == "transition"
    assert events[0]["start"] == pytest.approx(transition["duration"])
    assert instruction["first_slide"] == instruction["last_slide"] - 1
    assert action["start"] >= events[0]["start"] + 2.1
    assert action["duration"] == pytest.approx(1.2)
    assert result["start"] == pytest.approx(action["start"] + 1.2)


def test_sequence_preserves_all_dialog_input_and_speaks_result_after_it():
    scene = {
        "key": "printer",
        "title": "Drucker wählen",
        "first_slide": 0,
        "last_slide": 5,
        "action_first_slide": 1,
        "action_last_slide": 4,
        "minimum_seconds": 18,
        "voice_before": "Ich wähle den Drucker.",
        "voice_after": "Die Wahl ist übernommen.",
    }
    capture = {"slides": [{"seconds": value} for value in (1.0, 0.6, 4.0, 0.5, 2.0)]}
    speech = {
        f"printer-{part}": {
            "text": scene["voice_" + part],
            "seconds": duration,
            "path": part + ".wav",
            "engine": "test",
            "sentences": [],
        }
        for part, duration in (("before", 3.0), ("after", 2.0))
    }
    phases, events = workshop_sequence_edit.sequence_plan([scene], capture, speech)
    assert phases[1]["duration"] == pytest.approx(5.1)
    assert phases[1]["start"] >= 3.0
    assert events[1]["start"] == pytest.approx(phases[1]["start"] + 5.1)
    assert phases[-1]["start"] + phases[-1]["duration"] >= 18
    scene["action_last_slide"] = 6
    with pytest.raises(ValueError, match="außerhalb"):
        workshop_sequence_edit.sequence_plan([scene], capture, speech)


def test_sequence_hook_never_replays_the_hero_action_or_inherits_its_voice():
    original = {
        "hero": "apply",
        "hook": {"voice": "Hier ist das Ziel.", "title": "Das Ziel"},
        "scenes": [
            {
                "key": "apply",
                "first_slide": 0,
                "last_slide": 3,
                "action_first_slide": 1,
                "action_last_slide": 2,
                "voice_before": "Ich klicke.",
                "voice_after": "Fertig.",
            }
        ],
    }
    scenes = workshop_sequence_edit.scenes_for(original, short=False)
    assert "action_first_slide" not in scenes[0]
    assert scenes[0]["first_slide"] == 2
    assert scenes[0]["voice_before"] == "Hier ist das Ziel."
    assert scenes[0]["voice_after"] == ""
    assert scenes[1]["action_first_slide"] == 1
    assert original["scenes"][0]["voice_after"] == "Fertig."


def test_sequence_hook_does_not_reuse_hero_audio_targets(tmp_path):
    plan = {
        "hero": "apply",
        "language": "de",
        "hook": {"title": "Ergebnis", "voice": "Hier ist das Ergebnis."},
        "short_hook": {"title": "Kurz", "voice": "Das fertige Ergebnis."},
        "scenes": [
            {
                "key": "apply",
                "short": True,
                "first_slide": 0,
                "last_slide": 3,
                "action_first_slide": 1,
                "action_last_slide": 2,
                "voice_before": "Ich ändere das Maß.",
                "voice_after": "Das Maß ist geändert.",
                "short_voice_before": "Ich ändere es.",
                "short_voice_after": "Es ist geändert.",
                "audio_before": "hero-before.wav",
                "audio_after": "hero-after.wav",
                "short_audio_before": "short-hero-before.wav",
                "short_audio_after": "short-hero-after.wav",
            }
        ],
    }
    capture = {"complete": True, "slides": [{"seconds": 2.0} for _ in range(3)]}
    workshop_edit.write(tmp_path / "editorial.json", plan)
    workshop_edit.write(tmp_path / "capture.json", capture)

    jobs = workshop_edit.read(workshop_sequence_edit.prepare(tmp_path, short=False))["jobs"]

    tutorial_targets = {job["text"]: job["target"] for job in jobs}
    assert tutorial_targets["Hier ist das Ergebnis."] != tutorial_targets["Ich ändere das Maß."]
    assert tutorial_targets["Ich ändere das Maß."].endswith("hero-before.wav")

    short_jobs = workshop_edit.read(workshop_sequence_edit.prepare(tmp_path, short=True))["jobs"]
    short_targets = {job["text"]: job["target"] for job in short_jobs}
    assert short_targets["Das fertige Ergebnis."] != short_targets["Ich ändere es."]
    assert short_targets["Ich ändere es."].endswith("short-hero-before.wav")


def test_sequence_hook_keeps_only_the_hero_result_image_and_no_action_hold():
    plan = {
        "hero": "apply",
        "hook": {"title": "Ergebnis", "voice": "Hier ist das Ergebnis."},
        "short_hook": {"title": "Kurz", "voice": "Das Ergebnis."},
        "scenes": [
            {
                "key": "apply",
                "title": "Maß ändern",
                "first_slide": 0,
                "last_slide": 3,
                "action_first_slide": 1,
                "action_last_slide": 2,
                "voice_before": "Ich ändere das Maß.",
                "voice_after": "Das Maß ist geändert.",
                "before_model_crop": [0, 0, 100, 100],
                "after_model_crop": [100, 0, 200, 100],
                "before_focus": [10, 10, 20, 20],
                "after_focus": [120, 10, 40, 40],
                "hold_frames": [{"slide": 0, "seconds": 0.5, "reason": "Vorzustand ist lesbar."}],
            }
        ],
    }
    scenes = workshop_sequence_edit.scenes_for(plan, short=False)
    hook = scenes[0]
    assert hook["model_crop"] == [100, 0, 200, 100]
    assert hook["focus"] == [120, 10, 40, 40]
    assert "hold_frames" not in hook
    assert "audio_before" not in hook and "audio_after" not in hook

    capture = {"slides": [{"seconds": 2.0} for _ in range(3)]}
    speech = {
        "hook-before": {
            "text": "Hier ist das Ergebnis.",
            "seconds": 1.0,
            "path": "hook.wav",
            "engine": "test",
            "sentences": [],
        },
        "apply-before": {
            "text": "Ich ändere das Maß.",
            "seconds": 1.0,
            "path": "before.wav",
            "engine": "test",
            "sentences": [],
        },
        "apply-after": {
            "text": "Das Maß ist geändert.",
            "seconds": 1.0,
            "path": "after.wav",
            "engine": "test",
            "sentences": [],
        },
    }
    phases, _events = workshop_sequence_edit.sequence_plan(scenes, capture, speech)
    assert phases[0]["first_slide"] == 2


def test_control_scene_matches_the_recommended_workshop_editor_schema(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from tools import make_workshop_videos

    class Recorder:
        frame_size = (1920, 1080)

        def __init__(self):
            self.slides = []

        def add(self, _title, _detail, seconds, **_kwargs):
            self.slides.append({"seconds": seconds})

    monkeypatch.setattr(make_workshop_videos, "LANGUAGE", "de")
    scene = make_workshop_videos.Tutorial.control_scene(
        SimpleNamespace(recorder=Recorder()),
        "control",
        ("Zahl ändern", "Ich ändere die Zahl.", "Die Zahl ist geändert."),
        ("Change a value", "I change the value.", "The value has changed."),
        short=True,
    )
    plan = {
        "hero": "control",
        "language": "de",
        "hook": {"title": "Ergebnis", "voice": "Die Zahl ist geändert."},
        "short_hook": {"title": "Kurz", "voice": "Die Zahl stimmt."},
        "scenes": [scene],
    }
    manifest = tmp_path / "editorial.json"
    workshop_edit.write(manifest, plan)
    workshop_edit.write(tmp_path / "capture.json", {"complete": True})

    jobs = workshop_edit.read(workshop_edit.prepare(manifest))["jobs"]
    tutorial_scene = workshop_edit.scene_list(plan, short=False)[1]
    short_scene = workshop_edit.scene_list(plan, short=True)[1]

    assert scene["short_voice"] == "Ich ändere die Zahl. Die Zahl ist geändert."
    assert scene["detail"] == scene["voice"]
    assert tutorial_scene["detail"] == scene["voice"]
    assert short_scene["voice"] == scene["short_voice"]
    assert {job["target"] for job in jobs} == {
        "audio/tutorial-hook.wav",
        "audio/tutorial-control.wav",
        "audio/short-hook.wav",
        "audio/short-control.wav",
    }
    assert any(job["text"] == scene["short_voice"] for job in jobs)


def test_print_settings_entry_scene_matches_the_workshop_editor_schema(tmp_path, monkeypatch):
    from tools import make_workshop_videos

    monkeypatch.setattr(make_workshop_videos, "LANGUAGE", "de")
    scene = make_workshop_videos._print_settings_entry_scene(
        "settings",
        first_slide=0,
        last_slide=2,
        action_first_slide=1,
        target_bounds=[1450, 20, 160, 80],
        model_crop=[400, 200, 800, 500],
        frame_size=(1920, 1080),
    )
    plan = {
        "hero": scene["key"],
        "language": "de",
        "hook": {"title": "Ergebnis", "voice": "Die Werte bleiben prüfbar."},
        "short_hook": {"title": "Kurz", "voice": "Die Werte sind sichtbar."},
        "scenes": [scene],
    }
    manifest = tmp_path / "editorial.json"
    workshop_edit.write(manifest, plan)
    workshop_edit.write(tmp_path / "capture.json", {"complete": True})

    jobs = workshop_edit.read(workshop_edit.prepare(manifest))["jobs"]

    assert scene["short_voice"] == ""
    assert scene["detail"] == scene["voice"] == "Oben rechts öffne ich Drucker."
    assert any(job["text"] == scene["voice"] for job in jobs)


def test_recipe_scenes_are_completed_at_the_editorial_manifest_boundary(tmp_path):
    from tools.make_workshop_videos import _editorial_scenes

    captured = [
        {
            "key": "operation-entry",
            "title": "Operation öffnen",
            "short": True,
            "voice_before": "Ich öffne die Operation.",
            "voice_after": "Die Einstellungen stehen bereit.",
        },
        {
            "key": "part-entry",
            "title": "Baustein wählen",
            "short": True,
            "voice": "Ich wähle den Baustein aus.",
            "detail": "Der Katalog zeigt den gewählten Baustein.",
        },
    ]
    scenes = _editorial_scenes(captured)
    plan = {
        "hero": "operation-entry",
        "language": "de",
        "hook": {"title": "Ergebnis", "voice": "Die Änderung ist fertig."},
        "short_hook": {"title": "Kurz", "voice": "Das Ergebnis ist fertig."},
        "scenes": scenes,
    }
    manifest = tmp_path / "editorial.json"
    workshop_edit.write(manifest, plan)
    workshop_edit.write(tmp_path / "capture.json", {"complete": True})

    jobs = workshop_edit.read(workshop_edit.prepare(manifest))["jobs"]
    by_target = {job["target"]: job["text"] for job in jobs}

    assert scenes[0]["voice"] == "Ich öffne die Operation. Die Einstellungen stehen bereit."
    assert scenes[0]["detail"] == scenes[0]["voice"]
    assert scenes[0]["short_voice"] == scenes[0]["voice"]
    assert scenes[1]["detail"] == "Der Katalog zeigt den gewählten Baustein."
    assert scenes[1]["short_voice"] == scenes[1]["voice"]
    assert by_target["audio/tutorial-operation-entry.wav"] == scenes[0]["voice"]
    assert by_target["audio/short-operation-entry.wav"] == scenes[0]["short_voice"]
    assert by_target["audio/short-part-entry.wav"] == scenes[1]["short_voice"]


def test_workshop_frame_bounds_scale_clip_and_cover_print_entry():
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QImage

    from tools.make_workshop_videos import (
        _entry_frame_bounds,
        _frame_bounds,
        _row_focus_bounds,
        _slot_capture_bounds,
    )

    class Widget:
        def __init__(self, origin, size):
            self.origin = origin
            self.size = size

        def mapToGlobal(self, point):  # noqa: N802 — Qt-Vertrag des Prüfstellvertreters
            return QPoint(self.origin[0] + point.x(), self.origin[1] + point.y())

        def width(self):
            return self.size[0]

        def height(self):
            return self.size[1]

    window = Widget((100, 50), (800, 600))
    printer_button = Widget((90, 40), (100, 100))
    dialog = Widget((250, 150), (300, 200))

    target_bounds, entry_crop = _entry_frame_bounds(window, (1600, 1200), printer_button, dialog)
    assert target_bounds == [0, 0, 180, 180]
    assert entry_crop == [0, 0, 900, 600]
    picture = workshop_edit._cropped(QImage(1600, 1200, QImage.Format.Format_RGB32), entry_crop)
    assert (picture.width(), picture.height()) == (900, 600)

    lower_right = Widget((840, 630), (100, 100))
    assert _frame_bounds(window, (1600, 1200), lower_right) == [1480, 1160, 120, 40]

    viewport = Widget((140, 80), (500, 450))
    measure_box = Widget((600, 110), (180, 220))
    crop, focus = _slot_capture_bounds(window, (1600, 1200), viewport, measure_box)
    assert crop == [80, 60, 1280, 900]
    assert focus == [986, 106, 388, 468]
    cropped = workshop_edit._cropped(QImage(1600, 1200, QImage.Format.Format_RGB32), crop)
    assert (cropped.width(), cropped.height()) == (1280, 900)

    row = Widget((630, 180), (60, 30))
    assert _row_focus_bounds(window, (1600, 1200), measure_box, row) == [
        1000,
        236,
        360,
        108,
    ]


def test_sequence_can_label_and_shorten_waiting_without_cutting_the_real_action():
    scene = {
        "key": "setup",
        "title": "Einrichtung",
        "first_slide": 0,
        "last_slide": 5,
        "action_first_slide": 1,
        "action_last_slide": 3,
        "voice_before": "",
        "voice_after": "Die Suche ist fertig.",
        "after_hold": {"frame": 4, "seconds": 8, "note": "Programmsuche gekürzt"},
    }
    capture = {"slides": [{"seconds": value} for value in (1, 2, 3, 40, 22)]}
    speech = {
        "setup-after": {
            "text": "Die Suche ist fertig.",
            "seconds": 2.0,
            "path": "after.wav",
            "engine": "test",
            "sentences": [],
        }
    }
    phases, _ = workshop_sequence_edit.sequence_plan([scene], capture, speech)
    assert phases[1]["duration"] == pytest.approx(5)
    assert phases[-1]["duration"] == pytest.approx(8)
    assert phases[-1]["first_slide"] == 4
    assert phases[-1]["omitted_wait_slides"] == [3, 4]
    assert phases[-1]["edit_note"] == "Programmsuche gekürzt"
    scene["after_hold"]["frame"] = 2
    with pytest.raises(ValueError, match="keine Handlung"):
        workshop_sequence_edit.sequence_plan([scene], capture, speech)


def test_sequence_speaks_a_static_result_immediately_and_honours_the_whole_voice():
    scene = {
        "key": "saved",
        "title": "Gespeichert",
        "first_slide": 0,
        "last_slide": 1,
        "action_first_slide": 1,
        "action_last_slide": 1,
        "voice_before": "",
        "voice_after": "Der Eintrag ist gespeichert.",
        "still_seconds": 6,
    }
    capture = {"slides": [{"seconds": 10}]}
    speech = {
        "saved-after": {
            "text": "Der Eintrag ist gespeichert.",
            "seconds": 8.0,
            "path": "after.wav",
            "engine": "test",
            "sentences": [],
        }
    }
    phases, events = workshop_sequence_edit.sequence_plan([scene], capture, speech)
    assert len(phases) == 1
    assert phases[0]["part"] == "after"
    assert events[0]["start"] == 0
    assert phases[0]["duration"] == pytest.approx(8.5)
    assert phases[0]["mode"] == "held_result_frame"


def test_sequence_only_shortens_explicit_still_frames_and_keeps_surrounding_input():
    scene = {
        "key": "file",
        "title": "Öffnen",
        "first_slide": 0,
        "last_slide": 5,
        "action_first_slide": 1,
        "action_last_slide": 4,
        "voice_before": "",
        "voice_after": "",
        "hold_frames": [
            {"slide": 2, "seconds": 2.0, "reason": "Dateiname ist vollständig lesbar."}
        ],
    }
    capture = {"slides": [{"seconds": value} for value in (1.0, 0.35, 7.4, 0.7, 1.0)]}
    phases, _ = workshop_sequence_edit.sequence_plan([scene], capture, {})
    action = phases[1]
    assert action["duration"] == pytest.approx(3.05)
    assert action["source_seconds"] == pytest.approx(8.45)
    assert action["first_slide"] == 1 and action["last_slide"] == 4
    assert action["shortened_holds"][0]["slide"] == 2
    assert action["playback_rate"] == 1.0
    scene["hold_frames"][0]["slide"] = 1
    with pytest.raises(ValueError, match="Einzelbildbeleg"):
        workshop_sequence_edit.sequence_plan([scene], capture, {})


def test_word_times_are_bound_to_audio_bytes_original_words_and_nonoverlapping_ranges(tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"original audio bytes")
    speech = {"clip": {"path": str(audio), "text": "Ein Satz. Noch einer.", "seconds": 4.0}}
    entry = {
        "audio": str(audio),
        "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
        "sentences": [
            {"start": 0.2, "end": 1.5, "text": "Ein Satz."},
            {"start": 1.8, "end": 3.7, "text": "Noch einer."},
        ],
    }
    manifest = tmp_path / "alignment.json"
    workshop_edit.write(manifest, {"jobs": [entry]})
    workshop_edit.apply_alignment(speech, manifest)
    assert speech["clip"]["sentences"][1]["start"] == 1.8
    entry["sentences"][1]["start"] = 1.2
    workshop_edit.write(manifest, {"jobs": [entry]})
    with pytest.raises(ValueError, match="überlappen"):
        workshop_edit.apply_alignment(speech, manifest)
    entry["sentences"][1]["start"] = 1.8
    entry["sentences"][1]["text"] = "Anderer Text."
    workshop_edit.write(manifest, {"jobs": [entry]})
    with pytest.raises(ValueError, match="Sprechertext"):
        workshop_edit.apply_alignment(speech, manifest)
    audio.write_bytes(b"different audio bytes")
    with pytest.raises(ValueError, match="anderen Sprachdatei"):
        workshop_edit.apply_alignment(speech, manifest)
