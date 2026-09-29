"""Vorhandene lokale Piper-Stimmen für ein Schnittmanifest sprechen.

    python tools/speak_piper.py <auftrag.json> [--piper PFAD]

Piper steht unter GPL-3.0-or-later und wird deshalb nur als Programm
aufgerufen, nie importiert (Regel 15): ``piper`` aus der separaten
Medienumgebung ``.venv-video``, sonst aus dem Suchpfad oder was ``--piper``
nennt. Dieses Skript braucht nur die Standardbibliothek und läuft nie in
Solidon. Die Ausgabe verwendet denselben Satzzeitnachweis wie
``speak_chatterbox``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
VOICES = {"de": "de_DE-thorsten-high", "en": "en_US-ljspeech-high"}

#: Wo ``pip install piper-tts`` das Programm in der Medienumgebung ablegt.
MEDIA_PIPER = (
    ROOT / ".venv-video" / "Scripts" / "piper.exe",
    ROOT / ".venv-video" / "bin" / "piper",
)


class Speech(NamedTuple):
    """Ein gesprochener Satz: Format und Rohdaten einer WAV-Datei."""

    rate: int
    channels: int
    width: int
    count: int
    data: bytes


def find_piper(explicit: Path | None) -> Path:
    """Das Piper-Programm: ausdrücklich genannt, aus der Medienumgebung oder aus dem Suchpfad."""
    if explicit is not None:
        if explicit.is_file():
            return explicit
        raise SystemExit(f"{explicit} gibt es nicht — den Pfad zu piper(.exe) prüfen.")
    for candidate in MEDIA_PIPER:
        if candidate.is_file():
            return candidate
    found = shutil.which("piper")
    if found:
        return Path(found)
    raise SystemExit(
        "Piper fehlt. In der Medienumgebung einrichten "
        "(python -m venv .venv-video, dann .venv-video\\Scripts\\pip install piper-tts) "
        "oder den Pfad mit --piper nennen."
    )


def speak(piper: Path, model: Path, sentences: list[str]) -> list[Speech]:
    """Jeder Satz eine Aufnahme, in einem Programmlauf — die Stimme lädt einmal je Auftrag.

    Die Sätze gehen als UTF-8-Datei hinein, eine Zeile je Satz: Piper liest
    ``-i`` ausdrücklich als UTF-8, die Standardeingabe dagegen in der
    Kodierung der Konsole, und die verlöre die Umlaute. Mit ``-d`` schreibt
    Piper je Zeile eine Datei, benannt nach einer monotonen Uhr — die
    Reihenfolge der Namen ist die der Zeilen.
    """
    with tempfile.TemporaryDirectory(prefix="piper-") as scratch:
        folder = Path(scratch)
        text = folder / "sentences.txt"
        text.write_text("".join(" ".join(line.split()) + "\n" for line in sentences), "utf-8")
        finished = subprocess.run(
            [str(piper), "-m", str(model), "-i", str(text), "-d", str(folder / "wav")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if finished.returncode != 0:
            raise SystemExit(
                f"Piper endete mit {finished.returncode}:\n{finished.stderr.strip()}\n"
                f"Stimme {model.name} und Programm {piper} prüfen."
            )
        spoken = sorted((folder / "wav").glob("*.wav"), key=lambda path: int(path.stem))
        if len(spoken) != len(sentences):
            raise SystemExit(
                f"Piper lieferte {len(spoken)} Dateien für {len(sentences)} Sätze — "
                "ein leerer Satz im Auftrag? Den Sprechertext prüfen."
            )
        takes = []
        for path in spoken:
            with wave.open(str(path), "rb") as speech:
                count = speech.getnframes()
                takes.append(
                    Speech(
                        speech.getframerate(),
                        speech.getnchannels(),
                        speech.getsampwidth(),
                        count,
                        speech.readframes(count),
                    )
                )
        return takes


def main(argv: list[str] | None = None) -> int:
    """Je Auftrag einmal sprechen und nur geänderte Sprechertexte neu erzeugen."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("manifest", type=Path, help="Sprachauftrag von workshop_edit.py prepare")
    parser.add_argument("--piper", type=Path, help="Pfad zu piper(.exe), falls nicht gefunden")
    arguments = parser.parse_args(argv)
    manifest = arguments.manifest.resolve()
    jobs = json.loads(manifest.read_text("utf-8"))["jobs"]
    piper: Path | None = None
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
        piper = piper or find_piper(arguments.piper)
        parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])", job["text"].strip())
        frames = []
        sentences = []
        elapsed = 0.0
        takes = speak(piper, model_path, parts)
        rate, channels, width = takes[0].rate, takes[0].channels, takes[0].width
        for index, (sentence, take) in enumerate(zip(parts, takes, strict=True)):
            if index:
                frames.append(bytes(round(rate * 0.25) * channels * width))
                elapsed += 0.25
            seconds = take.count / rate
            sentences.append({"start": elapsed, "end": elapsed + seconds, "text": sentence})
            elapsed += seconds
            frames.append(take.data)
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
