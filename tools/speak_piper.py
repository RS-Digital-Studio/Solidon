"""Vorhandene lokale Piper-Stimmen für ein Schnittmanifest sprechen.

Läuft ausschließlich in der separaten Medienumgebung, nie in Solidon.
Die Ausgabe verwendet denselben Satzzeitnachweis wie ``speak_chatterbox``.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import wave
from pathlib import Path

from piper import PiperVoice

ROOT = Path(__file__).resolve().parent.parent
VOICES = {"de": "de_DE-thorsten-high", "en": "en_US-ljspeech-high"}


def main() -> int:
    """Je Sprache einmal laden und nur geänderte Sprechertexte neu erzeugen."""
    manifest = Path(sys.argv[1]).resolve()
    jobs = json.loads(manifest.read_text("utf-8"))["jobs"]
    models = {}
    for job in jobs:
        language = job["language"]
        model_path = ROOT / ".voices" / f"{VOICES[language]}.onnx"
        signature = hashlib.sha256(
            model_path.read_bytes() + Path(__file__).read_bytes()
        ).hexdigest()
        target = manifest.parent / job["target"]
        stamp = target.with_suffix(".speech.json")
        expected = {"text": job["text"], "language": language, "voice": signature}
        cached = json.loads(stamp.read_text("utf-8")) if stamp.exists() else {}
        if target.exists() and all(cached.get(key) == value for key, value in expected.items()):
            continue
        if language not in models:
            models[language] = PiperVoice.load(model_path)
        model = models[language]
        frames = []
        sentences = []
        elapsed = 0.0
        for index, sentence in enumerate(
            re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])", job["text"].strip())
        ):
            memory = io.BytesIO()
            with wave.open(memory, "wb") as output:
                model.synthesize_wav(sentence, output)
            memory.seek(0)
            with wave.open(memory, "rb") as speech:
                rate = speech.getframerate()
                channels = speech.getnchannels()
                width = speech.getsampwidth()
                count = speech.getnframes()
                data = speech.readframes(count)
            if index:
                frames.append(bytes(round(rate * 0.25) * channels * width))
                elapsed += 0.25
            seconds = count / rate
            sentences.append({"start": elapsed, "end": elapsed + seconds, "text": sentence})
            elapsed += seconds
            frames.append(data)
        target.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(target), "wb") as output:
            output.setnchannels(channels)
            output.setsampwidth(width)
            output.setframerate(rate)
            output.writeframes(b"".join(frames))
        proof = dict(
            expected,
            sentences=sentences,
            seconds=elapsed,
            sample_rate=rate,
            engine=f"Piper {VOICES[language]}",
        )
        stamp.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{target.name}: {elapsed:.2f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
