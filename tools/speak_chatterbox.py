"""Einen Satz mit Chatterbox sprechen — aufgerufen aus der eigenen Umgebung.

    .venv-tts\\Scripts\\python.exe tools/speak_chatterbox.py ziel.wav de "Text"

Eigenes Programm und kein Modul von ``make_video.py``, weil es in einer
**anderen** virtuellen Umgebung lebt: Chatterbox bringt PyTorch mit, piper
bringt onnxruntime mit, und beide zusammen in der Projektumgebung wären eine
Abhängigkeitskette, die mit Solidon nichts zu tun hat. Aufgerufen wird es
deshalb wie ffmpeg — als fremdes Programm über die Kommandozeile.

Die Modellgewichte stehen unter der MIT-Lizenz, kommerzieller Gebrauch
eingeschlossen; nachgesehen, nicht angenommen. Jede erzeugte Datei trägt ein
unhörbares Wasserzeichen von Resemble AI, das sich nicht abschalten lässt —
es macht die Stimme maschinell als synthetisch erkennbar, was der
Kennzeichnungspflicht der Plattformen nicht widerspricht, aber bekannt sein
sollte.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import torch
import torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

#: Wie stark betont wird. Aus fünf gegeneinander gehörten Versionen gewählt:
#: die Vorgabe 0,5 klingt gleichförmig, 0,85 überzeichnet.
EXAGGERATION = 0.7

#: Wie eng am Text geblieben wird. Niedriger heißt ruhigerer Fluss mit mehr
#: Pausen.
CFG_WEIGHT = 0.5

#: Der Startwert — und damit **die Stimme**.
#:
#: Chatterbox würfelt den Sprecher bei jedem Aufruf neu. Gemessen: dreimal
#: derselbe Satz mit denselben Einstellungen ergab Grundtöne von 124, 143 und
#: 151 Hz — drei verschiedene Leute. Eine Referenzaufnahme half nicht, sie
#: streute sogar leicht stärker.
#:
#: Mit festem Startwert sind drei Läufe **bitweise identisch**. Der Wert hier
#: ist deshalb keine Einstellung, sondern eine Besetzungsentscheidung: ihn zu
#: ändern heißt, den Sprecher auszutauschen. Wer das nach dem ersten
#: veröffentlichten Video tut, hat im zweiten eine andere Stimme.
#:
#: Aus acht gegeneinander gehörten Sprechern gewählt (132 bis 183 Hz
#: Grundton). Dieser trägt zugleich den geringsten englischen Einschlag —
#: was sich nicht vorhersagen ließ, sondern nur durch Hören herauskam.
SEED = 1234

#: Die Aufnahme, die festlegt, **wer** spricht.
#:
#: Der Startwert allein genügt nicht, und das ist der wichtigste Befund dieser
#: ganzen Suche: der Sprecher hängt bei Chatterbox nicht nur am Zufall,
#: sondern **auch am Text**. Drei verschiedene Sätze mit demselben Startwert
#: ergaben Grundtöne von 131, 143 und 168 Hz — drei Personen in einem Video.
#:
#: Mit dieser Referenz schrumpft die Spanne auf 125 bis 135 Hz, also von fünf
#: Halbtönen auf gut einen. Startwert und Referenz sind keine Alternativen:
#: die Referenz legt fest, wer spricht, der Startwert, wie gesampelt wird.
#: Erst zusammen ergeben sie eine feste Stimme.
#:
#: Die Datei ist selbst mit ``SEED`` erzeugt und aus acht Kandidaten
#: ausgewählt. Sie gehört ins Repository: ohne sie klingt jeder Neuaufbau
#: anders, und die Stimme eines Kanals ist kein Detail.
REFERENCE_VOICE = Path(__file__).resolve().parent / "voice-reference.wav"

#: Wie lange die Pause zwischen zwei Sätzen ist, in Sekunden.
#:
#: Gebraucht, weil jeder Satz **einzeln** erzeugt wird (siehe :func:`split`).
#: Ohne sie stoßen die Sätze aneinander, als wäre der Sprecher außer Atem.
SENTENCE_GAP = 0.35


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--manifest":
        manifest = Path(sys.argv[2]).resolve()
        jobs = json.loads(manifest.read_text("utf-8"))["jobs"]
        for job in jobs:
            job["target"] = str((manifest.parent / job["target"]).resolve())
        reference = REFERENCE_VOICE
    elif len(sys.argv) >= 4:
        jobs = [{"target": sys.argv[1], "language": sys.argv[2], "text": sys.argv[3]}]
        reference = Path(sys.argv[4]) if len(sys.argv) > 4 else REFERENCE_VOICE
    else:
        print(__doc__)
        return 2
    if not reference.is_file():
        raise SystemExit(
            f"Die Referenzstimme fehlt: {reference}\n"
            f"Ohne sie wechselt der Sprecher von Satz zu Satz — siehe REFERENCE_VOICE. "
            f"Wiederherstellen lässt sie sich mit Startwert {SEED} und dem Satz aus der "
            f"Stimmauswahl; einfacher ist es, sie aus der Versionsgeschichte zu holen."
        )

    signature = hashlib.sha256(reference.read_bytes() + Path(__file__).read_bytes()).hexdigest()
    pending = []
    for job in jobs:
        target = Path(job["target"])
        stamp = target.with_suffix(".speech.json")
        expected = {"text": job["text"], "language": job["language"], "voice": signature}
        cached = json.loads(stamp.read_text("utf-8")) if stamp.exists() else {}
        if target.exists() and all(cached.get(key) == value for key, value in expected.items()):
            print(f"Unverändert: {target.name}", flush=True)
        else:
            pending.append((target, expected))
    if not pending:
        return 0
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    for target, expected in pending:
        result = render_speech(model, expected["text"], expected["language"], reference)
        joined, timings = result
        target.parent.mkdir(parents=True, exist_ok=True)
        torchaudio.save(str(target), joined, model.sr)
        proof = dict(
            expected,
            sentences=timings,
            sample_rate=model.sr,
            seconds=joined.shape[-1] / model.sr,
            engine="ChatterboxMultilingualTTS",
        )
        target.with_suffix(".speech.json").write_text(
            json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"{target.name}: {proof['seconds']:.2f} s · {model.sr} Hz · {device}", flush=True)
    return 0


def render_speech(model, text: str, language: str, reference: Path):
    """Ein Modell für mehrere Szenen halten und echte Satzzeiten für Untertitel belegen."""
    extra = {"audio_prompt_path": str(reference)}
    pieces = []
    timings = []
    seconds = 0.0
    gap = torch.zeros(1, int(model.sr * SENTENCE_GAP))
    for index, sentence in enumerate(split(text)):
        # **Vor jedem Satz**, nicht einmal beim Start: das Modell zieht bei
        # jedem ``generate`` aus demselben Zufallsstrom weiter, und der
        # zweite Satz käme sonst von einem anderen Sprecher als der erste.
        torch.manual_seed(SEED)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(SEED)
        wav = model.generate(
            sentence,
            language_id=language,
            exaggeration=EXAGGERATION,
            cfg_weight=CFG_WEIGHT,
            **extra,
        )
        if index:
            pieces.append(gap)
            seconds += SENTENCE_GAP
        pieces.append(wav)
        duration = wav.shape[-1] / model.sr
        timings.append({"start": seconds, "end": seconds + duration, "text": sentence})
        seconds += duration
    joined = torch.cat(pieces, dim=-1)
    return joined, timings


def split(text: str) -> list[str]:
    """Den Text in Sätze zerlegen — einer je Aufruf ans Modell.

    **Der Grund ist ein Fehler, kein Stilwunsch.** Chatterbox bricht lange
    Eingaben ab: derselbe Zweisatz kam als 6,2 bis 7,7 Sekunden zurück, wo
    piper 9,5 brauchte, und im Protokoll stand ein erzwungenes Satzende. Das
    Ende fehlte schlicht. Kurze Eingaben laufen nicht in diese Grenze.

    Zerlegt wird an Satzzeichen, gefolgt von einem Leerzeichen und einem
    Großbuchstaben — „Siebzig Millimeter breit, mit Mutternfallen" bleibt
    damit zusammen, „…aus Solidon. Siebzig…" nicht. Abkürzungen mit Punkt
    kämen hier nicht vor; stünde je eine im Drehbuch, wäre das die Stelle.
    """
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])", text.strip())
    return [part for part in (piece.strip() for piece in parts) if part]


if __name__ == "__main__":
    raise SystemExit(main())
