"""Sprecherfassungen mit Qwen3-TTS in der getrennten Medienumgebung erzeugen.

    .venv-qwen-tts\\Scripts\\python.exe tools/speak_qwen.py auftrag.json

Das Manifest nennt lokale, prüfsummengebundene Gewichte und je Sprache eine
eigene synthetische oder ausdrücklich freigegebene Referenzstimme. ``design``
erzeugt eigene Referenzen; ``clone`` hält die Stimme über mehrere Filme.
Weder Pakete noch Modellgewichte werden mit Solidon ausgeliefert.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def digest(path: Path) -> str:
    """Große Gewichte lesen, ohne sie zusätzlich im Speicher zu halten."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main() -> int:
    """Ein Modell laden und nur geänderte, einzeln belegte Sätze erzeugen."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    options = parser.parse_args()
    manifest_path = options.manifest.resolve()
    manifest = json.loads(manifest_path.read_text("utf-8-sig"))
    base = manifest_path.parent
    model_path = (base / manifest["model_path"]).resolve()
    source = json.loads((base / manifest["model_source"]).read_text("utf-8"))
    for entry in source["files"]:
        if entry["file"].endswith(".safetensors"):
            path = model_path / entry["file"]
            if digest(path) != entry["sha256"]:
                raise SystemExit(f"Die Modellprüfung stimmt nicht: {path.name}")
    mode = manifest["mode"]
    if mode not in {"design", "clone"}:
        raise SystemExit("Der Auftrag muss design oder clone angeben.")

    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    torch.set_num_threads(4)
    model = Qwen3TTSModel.from_pretrained(
        str(model_path),
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        local_files_only=True,
    )
    seed = int(manifest.get("seed", 20260928))
    gap_seconds = float(manifest.get("sentence_gap", 0.28))
    prompts = {}
    for language, reference in manifest.get("references", {}).items():
        audio_path = (base / reference["audio"]).resolve()
        if reference["origin"] == "licensed_voice":
            rights_path = (base / reference["rights_proof"]).resolve()
            if digest(rights_path) != reference["rights_sha256"]:
                raise SystemExit("Der Rechtebeleg der Referenzstimme hat sich geändert.")
            rights = json.loads(rights_path.read_text("utf-8-sig"))
            if not (
                rights.get("license") == "CC0-1.0"
                and rights.get("voice_synthesis") is True
                and rights.get("commercial_use") is True
                and rights.get("consent_source")
                and rights.get("audio_sha256") == reference["sha256"]
            ):
                raise SystemExit(
                    "Die Referenz braucht einen geprüften Rechte- und Einwilligungsbeleg."
                )
        elif reference["origin"] != "synthetic_original":
            raise SystemExit("Die Herkunft der Referenzstimme ist nicht freigegeben.")
        if digest(audio_path) != reference["sha256"]:
            raise SystemExit(f"Die Referenzstimme hat sich geändert: {audio_path.name}")
        prompts[language] = model.create_voice_clone_prompt(
            ref_audio=str(audio_path), ref_text=reference["text"], x_vector_only_mode=False
        )

    for job in manifest["jobs"]:
        target = (base / job["target"]).resolve()
        stamp = target.with_suffix(".speech.json")
        signature_data = {
            "helper": digest(Path(__file__)),
            "model": source["revision"],
            "mode": mode,
            "seed": seed,
            "gap": gap_seconds,
            "reference": manifest.get("references", {}).get(job["language"]),
            "instruction": job.get("instruction", ""),
            "continuous": bool(job.get("continuous", False)),
        }
        signature = hashlib.sha256(
            json.dumps(signature_data, sort_keys=True).encode("utf-8")
        ).hexdigest()
        expected = {"text": job["text"], "language": job["language"], "voice": signature}
        cached = json.loads(stamp.read_text("utf-8")) if stamp.exists() else {}
        if (
            target.is_file()
            and all(cached.get(key) == value for key, value in expected.items())
            and cached.get("sha256") == digest(target)
        ):
            print(f"Unverändert: {target.name}", flush=True)
            continue

        pieces = []
        timings = []
        elapsed = 0.0
        started = time.monotonic()
        sentences = (
            [job["text"]]
            if mode == "design" or job.get("continuous", False)
            else re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])", job["text"].strip())
        )
        for index, sentence in enumerate(sentences):
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            settings = {
                "text": sentence,
                "language": {"de": "German", "en": "English"}[job["language"]],
                "non_streaming_mode": True,
                "max_new_tokens": 1400,
                "temperature": 0.7,
            }
            if mode == "design":
                samples, rate = model.generate_voice_design(**settings, instruct=job["instruction"])
            else:
                samples, rate = model.generate_voice_clone(
                    **settings, voice_clone_prompt=prompts[job["language"]]
                )
            wave = np.asarray(samples[0], dtype=np.float32)
            if not wave.size or not np.isfinite(wave).all():
                raise SystemExit(f"Ungültiger Ton für {target.name}; neu erzeugen.")
            if index:
                gap = np.zeros(round(rate * gap_seconds), dtype=np.float32)
                pieces.append(gap)
                elapsed += len(gap) / rate
            duration = len(wave) / rate
            timings.append({"start": elapsed, "end": elapsed + duration, "text": sentence})
            elapsed += duration
            pieces.append(wave)
        joined = np.concatenate(pieces)
        peak = float(np.max(np.abs(joined)))
        gain = min(1.0, 0.85 / peak) if peak else 1.0
        target.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(target), joined * gain, rate, subtype="PCM_24")
        proof = dict(
            expected,
            sentences=timings,
            sample_rate=rate,
            seconds=elapsed,
            engine="Qwen3-TTS-12Hz-1.7B",
            synthesis=signature_data,
            peak_before_gain=peak,
            gain=gain,
            sha256=digest(target),
            render_seconds=time.monotonic() - started,
            listening_review="Noch offen; Synthese und Wortabgleich ersetzen kein Hören.",
        )
        stamp.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{target.name}: {elapsed:.2f} s · {rate} Hz", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
