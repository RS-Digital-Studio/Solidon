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

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import torch
import torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

#: Wie stark betont wird. Aus fünf gegeneinander gehörten Fassungen gewählt:
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
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    target = Path(sys.argv[1])
    language = sys.argv[2]
    text = sys.argv[3]
    reference = Path(sys.argv[4]) if len(sys.argv) > 4 else REFERENCE_VOICE
    if not reference.is_file():
        raise SystemExit(
            f"Die Referenzstimme fehlt: {reference}\n"
            f"Ohne sie wechselt der Sprecher von Satz zu Satz — siehe REFERENCE_VOICE. "
            f"Wiederherstellen lässt sie sich mit Startwert {SEED} und dem Satz aus der "
            f"Stimmauswahl; einfacher ist es, sie aus der Versionsgeschichte zu holen."
        )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    extra = {"audio_prompt_path": str(reference)}

    pieces = []
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
        pieces.append(wav)

    joined = torch.cat(pieces, dim=-1)
    target.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(target), joined, model.sr)
    print(f"{joined.shape[-1] / model.sr:.2f} s · {model.sr} Hz · {device}")
    return 0


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
