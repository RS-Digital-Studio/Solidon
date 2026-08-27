"""Richtet eine vorhandene ComfyUI-Installation für Solidon ein.

**Die Arbeit steckt in :mod:`app.core.backends.comfy_setup`**, und das ist der
Punkt dieser Datei: Bis hierhin stand sie hier, und die Anwendung wies auf sie
hin — „Einzurichten ist sie mit «python tools/setup_comfyui.py»". Für jemanden,
der Solidon als Installationsdatei bekommt, war das eine Wegbeschreibung zu
einer Datei, die es auf seinem Rechner nicht gibt: ``tools/`` reist nicht im
Paket mit.

Also liegt die Logik im Kern, wo die Oberfläche sie aufrufen kann und wo sie
paketiert wird. Diese Kommandozeile bleibt für den Entwicklungsbaum und tut
unverändert dasselbe:

    python tools/setup_comfyui.py
    python tools/setup_comfyui.py --comfyui "D:/ComfyUI" --skip-weights

Was sie **nicht** tut: ComfyUI installieren. Das ist ein fremdes Programm mit
eigenem Installationsweg.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.backends import comfy_setup

# Eine deutsche Windows-Konsole schreibt cp1252, und der Pfeil in der
# Schlussmeldung steht darin nicht. Ohne diese zwei Zeilen endet ein sonst
# erfolgreicher Lauf mit einem UnicodeEncodeError — ausgerechnet beim Satz,
# der sagt, dass alles geklappt hat.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--comfyui", help="Pfad zur ComfyUI-Installation")
    parser.add_argument(
        "--skip-weights", action="store_true", help="Die 7,5 GB Gewichte nicht laden"
    )
    args = parser.parse_args()

    try:
        result = comfy_setup.setup(
            args.comfyui,
            weights=not args.skip_weights,
            progress=lambda step: print(f"  {step} ..."),
        )
    except comfy_setup.SetupFailed as problem:
        print(f"\nAbgebrochen: {problem}", file=sys.stderr)
        return 1

    print(f"\nComfyUI: {result.comfyui}\nKnoten:  {result.nodes}")
    if not result.weights:
        print("Gewichte: nicht geladen")
    print(
        "\nFertig. ComfyUI neu starten, dann in Solidon: Datei → Modell erzeugen.\n"
        "Für den Weg über Text wird zusätzlich ein SDXL-Modell unter "
        "models/checkpoints gebraucht."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
