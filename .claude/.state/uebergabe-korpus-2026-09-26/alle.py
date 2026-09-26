"""Fährt lauf.py über die Modellauswahl, je Modell ein Prozess.

Aufruf: python alle.py <ergebnis.jsonl> <arbeitsordner>
"""

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = Path(r"F:\3D Dateien")
MODELS = [
    # Kanäle, Hohlräume
    "HydroBowl+–+Smart+Fruit+&+Veggie+Washer (1)/washing bowl v1.stl",  # noqa: RUF001
    "pista+biglie.3mf",
    "peruvian-style-ocarina.stl",
    # Gitter, Waben, Voronoi
    "埃菲尔铁塔（高18cm+、22cm、28cm）、一体无支撑/埃菲尔铁塔18cm_repariert.stl",  # noqa: RUF001
    "spiderman+voronoi+bambu+10cm_stls/obj_1_spiderman.stl",
    "kumiko_elongated-hexagon_desk-organizer_w150-typea.stl",
    "large-screwdriver-holder-with-honeycomb-pattern.stl",
    # Figuren, erzeugte Netze
    "Mausoleum Dragon.3mf",
    "Cat_1.stp",
    "mushroom.stl",
    "tree_with_tray_stl.stl",
    # konstruierte Teile
    "garden-hose-holder.3mf",
    "Modulares+Sieb/Siebhalter.stl",
    "the-over-engineered-backpack-wall-mount-v2.stl",
    "drill-holder.3mf",
    "Wedge-Lock (Set).stl",
    "carcassonne-4x4-grid-with-holes-on-bottom.stl",
    "mini-pot-x1.stl",
    "pegboard-gs-100-v2.step",
    "parametric-laptop-riser.stl",
    # mehrteilige Platten und Baugruppen
    "Scraper+with+Magnets+-+Elegoo.3mf",
    "Wizard+Tower+Staunton+Elegoo.3mf",
    "Filament+storage+system/Rack system for Filament.3mf",
    "Modern++Cutlery+Organizer+with+Divider.3mf",
    "Schwammablage+DM24+BS.3mf",
    "宠物便便器.3mf",
    "bromyde_press.3mf",
    "dice_w6_16mm_v00.stl",
]


def main() -> int:
    out = Path(sys.argv[1])
    work = Path(sys.argv[2])
    python = Path(sys.executable)
    for number, name in enumerate(MODELS, start=1):
        model = CORPUS / name
        started = time.perf_counter()
        print(f"[{number}/{len(MODELS)}] {name}", flush=True)
        try:
            run = subprocess.run(
                [
                    str(python),
                    str(HERE / "lauf.py"),
                    str(model),
                    str(out),
                    str(work / f"m{number:02d}"),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5400,
            )
            code = run.returncode
            tail = (run.stdout + run.stderr)[-600:]
        except subprocess.TimeoutExpired:
            code, tail = "timeout", ""
        print(f"    Exit {code} nach {time.perf_counter() - started:.0f} s", flush=True)
        if code != 0:
            print("    " + tail.replace("\n", "\n    "), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
