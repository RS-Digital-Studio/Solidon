"""Richtet eine vorhandene ComfyUI-Installation für Solidon ein.

Solidon rechnet die Mesh-Erzeugung nicht selbst, sondern schickt einen
Workflow an ein lokales ComfyUI (Bauplan §27). Damit dieser Workflow läuft,
muss auf der anderen Seite dreierlei vorhanden sein: die Knoten, die er
anspricht, das Modell, das sie laden, und die Pakete, an denen beides hängt.
Das von Hand zusammenzusuchen ist der Punkt, an dem die meisten aufgeben —
also nimmt dieses Werkzeug es ab.

Was es tut, in dieser Reihenfolge:

1. **ComfyUI finden.** An den üblichen Stellen, sonst über ``--comfyui``.
2. **Die Knoten hinlegen.** ``ComfyUI-TripoSG-Solidon`` aus diesem
   Verzeichnis, dazu der TripoSG-Quelltext von GitHub (MIT).
3. **Zwei Stellen richten.** Der Quelltext setzt eine CUDA-Erweiterung
   voraus, die es für Windows nicht gibt, und verliert an einer Stelle den
   Zahlentyp. Beides wird benannt und geprüft angewandt, nicht heimlich.
4. **Pakete nachziehen** — mit ``--no-deps``, weil die Anforderungsliste von
   TripoSG ``numpy==1.22.3`` festnagelt und eine ComfyUI-Installation daran
   zerbricht.
5. **Die Gewichte holen**, rund 7,5 GB, nur wenn sie fehlen.

Was es **nicht** tut: ComfyUI installieren. Das ist ein fremdes Programm mit
eigenem Installationsweg; hier wird nur eingerichtet, was Solidon braucht.

    python tools/setup_comfyui.py
    python tools/setup_comfyui.py --comfyui "D:/ComfyUI" --skip-weights
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
NODE_SOURCE = HERE / "comfyui" / "ComfyUI-TripoSG-Solidon"
NODE_NAME = "ComfyUI-TripoSG-Solidon"

# Eine deutsche Windows-Konsole schreibt cp1252, und der Pfeil in der
# Schlussmeldung steht darin nicht. Ohne diese zwei Zeilen endet ein sonst
# erfolgreicher Lauf mit einem UnicodeEncodeError — ausgerechnet beim Satz,
# der sagt, dass alles geklappt hat.
for strom in (sys.stdout, sys.stderr):
    if hasattr(strom, "reconfigure"):
        strom.reconfigure(encoding="utf-8", errors="replace")

TRIPOSG_REPO = "https://github.com/VAST-AI-Research/TripoSG.git"
WEIGHTS_REPO = "VAST-AI/TripoSG"

#: Reine Python-Pakete, an denen der TripoSG-Quelltext hängt und die eine
#: ComfyUI-Installation nicht ohnehin mitbringt. ``fast_simplification`` steht
#: hier statt ``pymeshlab``: dasselbe Können, aber MIT statt GPL (Regel 15).
PACKAGES = ("jaxtyping", "typeguard", "fast-simplification")

#: Wo ComfyUI erfahrungsgemäß liegt, wenn niemand etwas anderes sagt.
GUESSES = (
    Path("F:/AI/ComfyUI_windows_portable/ComfyUI"),
    Path("D:/AI/ComfyUI_windows_portable/ComfyUI"),
    Path("C:/ComfyUI_windows_portable/ComfyUI"),
    Path.home() / "ComfyUI",
    Path.home() / "Documents" / "ComfyUI",
)


class SetupFailed(RuntimeError):
    """Etwas fehlt, und der Text sagt, was zu tun ist."""


def find_comfyui(given: str | None) -> Path:
    """Der Ordner, in dem ``main.py`` und ``custom_nodes`` liegen."""
    if given:
        path = Path(given)
        # Ein Nutzer zeigt genauso oft auf den Ordner darüber wie auf den
        # richtigen. Beides anzunehmen kostet zwei Zeilen und spart eine
        # Rückfrage.
        for candidate in (path, path / "ComfyUI"):
            if (candidate / "custom_nodes").is_dir():
                return candidate
        raise SetupFailed(
            f"Unter {path} liegt kein ComfyUI — erwartet wird ein Ordner mit 'custom_nodes' darin."
        )

    for candidate in GUESSES:
        if (candidate / "custom_nodes").is_dir():
            return candidate
    raise SetupFailed(
        "ComfyUI wurde an den üblichen Stellen nicht gefunden. Der Pfad gehört "
        "dann an --comfyui, zum Beispiel:\n"
        '  python tools/setup_comfyui.py --comfyui "D:/ComfyUI_windows_portable/ComfyUI"'
    )


def find_python(comfyui: Path) -> Path:
    """Der Interpreter, mit dem ComfyUI selbst läuft.

    Nicht der, mit dem dieses Werkzeug läuft: Eine tragbare Installation
    bringt ihr eigenes Python mit, und ein Paket im falschen kommt dort nie
    an, wo es gebraucht wird.
    """
    portable = comfyui.parent / "python_embeded" / "python.exe"
    if portable.is_file():
        return portable
    for name in ("venv", ".venv"):
        for relativ in (f"{name}/Scripts/python.exe", f"{name}/bin/python"):
            candidate = comfyui / relativ
            if candidate.is_file():
                return candidate
    print(f"  ! Kein eigenes Python gefunden, es wird {sys.executable} benutzt.")
    return Path(sys.executable)


def run(command: list[str], what: str) -> None:
    print(f"  {what} ...")
    result = subprocess.run(command, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-6:]
        raise SetupFailed(f"{what} ist fehlgeschlagen:\n    " + "\n    ".join(tail))


def copy_nodes(comfyui: Path) -> Path:
    """Die Solidon-Knoten in ``custom_nodes`` legen."""
    if not NODE_SOURCE.is_dir():
        raise SetupFailed(f"Die Knoten fehlen unter {NODE_SOURCE}.")
    target = comfyui / "custom_nodes" / NODE_NAME
    target.mkdir(parents=True, exist_ok=True)
    for name in ("nodes.py", "__init__.py"):
        shutil.copy2(NODE_SOURCE / name, target / name)
    print(f"  Knoten liegen unter {target}")
    return target


def fetch_triposg(target: Path) -> None:
    """Den TripoSG-Quelltext neben die Knoten holen."""
    if (target / "triposg").is_dir():
        print("  TripoSG-Quelltext ist schon da")
        return
    if shutil.which("git") is None:
        raise SetupFailed(
            "git wird gebraucht, um den TripoSG-Quelltext zu holen. Entweder "
            "git installieren oder das Verzeichnis 'triposg' aus "
            f"{TRIPOSG_REPO} von Hand nach {target} legen."
        )
    scratch = target / "_clone"
    run(["git", "clone", "--depth", "1", TRIPOSG_REPO, str(scratch)], "TripoSG holen")
    shutil.move(str(scratch / "triposg"), str(target / "triposg"))
    for extra in ("LICENSE", "NOTICE"):
        if (scratch / extra).is_file():
            shutil.copy2(scratch / extra, target / f"{extra}-TripoSG")
    shutil.rmtree(scratch, ignore_errors=True)
    print("  TripoSG-Quelltext geholt (MIT)")


def patch_sources(target: Path) -> None:
    """Die zwei Stellen richten, an denen der Quelltext hier nicht durchläuft.

    Beide sind angesagt und werden vor dem Schreiben geprüft: Wer den Ordner
    später neu holt, bekommt sie erneut, und wer sie schon hat, bekommt sie
    nicht zweimal.
    """
    utils = target / "triposg" / "inference_utils.py"
    text = utils.read_text(encoding="utf-8")
    # Geprüft wird die Wirkung, nicht der eigene Kommentar: Wer den Marker
    # sucht, den er selbst geschrieben hat, patcht eine von Hand geänderte
    # Datei ein zweites Mal und macht aus ihr Bruch.
    if "try:\n    from diso import DiffDMC" not in text:
        alt = "from diso import DiffDMC\n"
        if alt not in text:
            raise SetupFailed(f"In {utils.name} steht der diso-Import nicht, wo er erwartet wird.")
        text = text.replace(
            alt,
            "# Von Solidon angepasst: diso ist eine CUDA-Erweiterung ohne\n"
            "# Windows-Wheel und wird nur im Flash-Decoder-Pfad gebraucht.\n"
            "try:\n"
            "    from diso import DiffDMC\n"
            "except ImportError:  # von Solidon\n"
            "    DiffDMC = None\n",
            1,
        )
        utils.write_text(text, encoding="utf-8")
        print("  diso-Import entschärft")
    else:
        print("  diso-Import war schon entschärft")

    vae = target / "triposg" / "models" / "autoencoders" / "autoencoder_kl_triposg.py"
    text = vae.read_text(encoding="utf-8")
    if "self.embedder(queries).to(" not in text:
        alt = "            queries = self.embedder(queries)\n"
        if alt not in text:
            raise SetupFailed(
                f"In {vae.name} steht der Embedder-Aufruf nicht, wo er erwartet wird."
            )
        text = text.replace(
            alt,
            "            # von Solidon: Typ zurückholen — der Fourier-Embedder\n"
            "            # gibt float32 zurück, die nächste Linearschicht trägt\n"
            "            # halbe Gewichte und bricht sonst ab.\n"
            "            queries = self.embedder(queries).to(dtype=z.dtype)\n",
            1,
        )
        vae.write_text(text, encoding="utf-8")
        print("  Zahlentyp im Decoder gerichtet")
    else:
        print("  Zahlentyp war schon gerichtet")


def install_packages(python: Path) -> None:
    """Die fehlenden Pakete nachziehen, ohne die Installation umzubauen.

    ``--no-deps`` ist hier kein Geiz, sondern Notwehr: Die Anforderungsliste
    von TripoSG nennt ``numpy==1.22.3``, und wer das durchlässt, hat danach
    ein ComfyUI, das nicht mehr startet.
    """
    run(
        [str(python), "-s", "-m", "pip", "install", "--no-deps", *PACKAGES],
        f"Pakete nachziehen ({', '.join(PACKAGES)})",
    )


def fetch_weights(comfyui: Path, python: Path) -> None:
    """Die Gewichte holen — rund 7,5 GB, und nur wenn sie fehlen."""
    target = comfyui / "models" / "triposg" / "TripoSG"
    if (target / "model_index.json").is_file():
        print(f"  Gewichte liegen schon unter {target}")
        return
    print(f"  Gewichte holen (rund 7,5 GB) nach {target} — das dauert.")
    run(
        [
            str(python),
            "-s",
            "-c",
            "from huggingface_hub import snapshot_download;"
            f"snapshot_download({WEIGHTS_REPO!r}, local_dir={str(target)!r}, max_workers=8)",
        ],
        "TripoSG-Gewichte laden",
    )
    print("  Gewichte geholt (MIT)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--comfyui", help="Pfad zur ComfyUI-Installation")
    parser.add_argument(
        "--skip-weights", action="store_true", help="Die 7,5 GB Gewichte nicht laden"
    )
    args = parser.parse_args()

    try:
        comfyui = find_comfyui(args.comfyui)
        print(f"ComfyUI: {comfyui}")
        python = find_python(comfyui)
        print(f"Python:  {python}\n")

        target = copy_nodes(comfyui)
        fetch_triposg(target)
        patch_sources(target)
        install_packages(python)
        if args.skip_weights:
            print("  Gewichte übersprungen (--skip-weights)")
        else:
            fetch_weights(comfyui, python)
    except SetupFailed as problem:
        print(f"\nAbgebrochen: {problem}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("\nAbgebrochen: Ein Schritt hat zu lange gebraucht.", file=sys.stderr)
        return 1

    print(
        "\nFertig. ComfyUI neu starten, dann in Solidon: Datei → Modell erzeugen.\n"
        "Für den Weg über Text wird zusätzlich ein SDXL-Modell unter "
        "models/checkpoints gebraucht."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
