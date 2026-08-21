"""ComfyUI für Solidon einrichten (Bauplan §27, §36).

Solidon rechnet die Mesh-Erzeugung nicht selbst, sondern schickt einen Workflow
an ein lokales ComfyUI. Damit dieser Workflow läuft, muss auf der anderen Seite
dreierlei vorhanden sein: die Knoten, die er anspricht, das Modell, das sie
laden, und die Pakete, an denen beides hängt. Das von Hand zusammenzusuchen ist
der Punkt, an dem die meisten aufgeben — also nimmt es dieses Modul ab.

**Warum es hier steht und nicht in ``tools/``.** Dort stand es, und die
Anwendung wies auf es hin: „Einzurichten ist sie mit «python
tools/setup_comfyui.py»." Für den Kunden war das eine Sackgasse mit
Wegbeschreibung — ``tools/`` reist nicht im Paket mit, es gibt diese Datei auf
seinem Rechner nicht. Die Logik gehört also dorthin, wo sie beides erreicht:
in den Kern, den die Oberfläche aufrufen kann und der paketiert wird. Die
Kommandozeile in ``tools/setup_comfyui.py`` ist jetzt ein dünner Aufrufer
darauf und tut unverändert dasselbe.

**Was es nicht tut: ComfyUI installieren.** Das ist ein fremdes Programm mit
eigenem Installationsweg; hier wird nur eingerichtet, was Solidon braucht.
Und es startet ComfyUI nicht — der Ordner bringt sein eigenes Python mit, und
eine Anwendung, die den Startbefehl errät, startet irgendwann das Falsche.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.core.log import get_logger
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Die Knoten reisen als Daten mit — neben den Workflows, die sie ansprechen.
#: In der Spec deckt der Eintrag für ``app/core/backends/data`` beide ab.
NODE_SOURCE: Final = Path(__file__).parent / "data" / "comfyui" / "ComfyUI-TripoSG-Solidon"
NODE_NAME: Final = "ComfyUI-TripoSG-Solidon"

TRIPOSG_REPO: Final = "https://github.com/VAST-AI-Research/TripoSG.git"
WEIGHTS_REPO: Final = "VAST-AI/TripoSG"

#: Reine Python-Pakete, an denen der TripoSG-Quelltext hängt und die eine
#: ComfyUI-Installation nicht ohnehin mitbringt. ``fast_simplification`` steht
#: hier statt ``pymeshlab``: dasselbe Können, aber MIT statt GPL (Regel 15).
PACKAGES: Final = ("jaxtyping", "typeguard", "fast-simplification")

#: Wo ComfyUI erfahrungsgemäß liegt, wenn niemand etwas anderes sagt.
GUESSES: Final = (
    Path("F:/AI/ComfyUI_windows_portable/ComfyUI"),
    Path("D:/AI/ComfyUI_windows_portable/ComfyUI"),
    Path("C:/ComfyUI_windows_portable/ComfyUI"),
    Path.home() / "ComfyUI",
    Path.home() / "Documents" / "ComfyUI",
)

#: Ein Schritt darf lange dauern — die Gewichte sind 7,5 GB.
STEP_TIMEOUT_SECONDS: Final = 3600.0

#: Wie groß die Gewichte sind. Steht im Fortschrittstext, weil „das dauert"
#: ohne Zahl niemandem sagt, ob er Kaffee holen kann.
WEIGHT_GIGABYTES: Final = 7.5

ProgressFn = Callable[[TranslatableText | str], None]
CancelledFn = Callable[[], bool]


def _silent(step: TranslatableText | str) -> None:
    del step


class SetupFailed(RuntimeError):
    """Etwas fehlt, und der Text sagt, was zu tun ist.

    Kein ``AppError``: Dieses Modul wird auch von der Kommandozeile aufgerufen,
    und dort ist eine Zeichenkette die ganze Ausgabe. Die Oberfläche fängt sie
    und macht daraus, was §2.7 verlangt.
    """


@dataclass(frozen=True, slots=True)
class Result:
    """Was eingerichtet wurde, und was gegebenenfalls noch fehlt."""

    comfyui: Path
    nodes: Path
    weights: bool
    reason: TranslatableText | str = ""

    @property
    def done(self) -> bool:
        return not self.reason


def find_comfyui(given: str | Path | None = None) -> Path:
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
            str(
                _(
                    "Dort liegt kein ComfyUI — erwartet wird ein Ordner, in dem "
                    "„custom_nodes“ steht."
                )
            )
        )

    for candidate in GUESSES:
        if (candidate / "custom_nodes").is_dir():
            return candidate
    raise SetupFailed(
        str(
            _(
                "ComfyUI ist an den üblichen Stellen nicht gefunden worden. Der "
                "Ordner lässt sich angeben — gesucht wird der, in dem "
                "„custom_nodes“ steht."
            )
        )
    )


def find_python(comfyui: Path) -> Path:
    """Der Interpreter, mit dem ComfyUI selbst läuft.

    Nicht der, mit dem Solidon läuft: Eine tragbare Installation bringt ihr
    eigenes Python mit, und ein Paket im falschen kommt dort nie an, wo es
    gebraucht wird. Im gebauten Paket gibt es unser Python ohnehin nicht als
    Interpreter — dann bleibt nur der von ComfyUI, und ohne ihn hält die
    Einrichtung an, statt in die Leere zu installieren.
    """
    portable = comfyui.parent / "python_embeded" / "python.exe"
    if portable.is_file():
        return portable
    for name in ("venv", ".venv"):
        for relative in (f"{name}/Scripts/python.exe", f"{name}/bin/python"):
            candidate = comfyui / relative
            if candidate.is_file():
                return candidate
    if getattr(sys, "frozen", False):
        raise SetupFailed(
            str(
                _(
                    "In diesem ComfyUI ist kein eigenes Python zu finden. Die "
                    "Pakete für TripoSG müssen in die Umgebung, mit der ComfyUI "
                    "läuft — welche das ist, weiß Solidon hier nicht."
                )
            )
        )
    _log.info("no python inside %s, using %s", comfyui, sys.executable)
    return Path(sys.executable)


def _run(command: list[str], what: TranslatableText | str, progress: ProgressFn) -> None:
    progress(what)
    _log.info("comfy setup: %s", command[0])
    try:
        finished = subprocess.run(
            command, capture_output=True, text=True, timeout=STEP_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.SubprocessError) as problem:
        raise SetupFailed(f"{what}: {problem}") from problem
    if finished.returncode:
        tail = (finished.stderr or finished.stdout or "").strip().splitlines()[-6:]
        raise SetupFailed(f"{what}\n" + "\n".join(tail))


def copy_nodes(comfyui: Path, progress: ProgressFn = _silent) -> Path:
    """Die Solidon-Knoten in ``custom_nodes`` legen."""
    if not NODE_SOURCE.is_dir():
        raise SetupFailed(str(_("Die Knoten fehlen in dieser Installation von Solidon.")))
    progress(_("Knoten hinlegen"))
    target = comfyui / "custom_nodes" / NODE_NAME
    target.mkdir(parents=True, exist_ok=True)
    for name in ("nodes.py", "__init__.py"):
        shutil.copy2(NODE_SOURCE / name, target / name)
    _log.info("nodes copied to %s", target)
    return target


def fetch_triposg(target: Path, progress: ProgressFn = _silent) -> None:
    """Den TripoSG-Quelltext neben die Knoten holen."""
    if (target / "triposg").is_dir():
        return
    if shutil.which("git") is None:
        raise SetupFailed(
            str(
                _(
                    "Für den TripoSG-Quelltext wird git gebraucht. Entweder git "
                    "installieren, oder das Verzeichnis „triposg“ von Hand neben "
                    "die Knoten legen — woher, steht in der Doku."
                )
            )
        )
    scratch = target / "_clone"
    _run(
        ["git", "clone", "--depth", "1", TRIPOSG_REPO, str(scratch)],
        _("TripoSG holen"),
        progress,
    )
    shutil.move(str(scratch / "triposg"), str(target / "triposg"))
    for extra in ("LICENSE", "NOTICE"):
        if (scratch / extra).is_file():
            shutil.copy2(scratch / extra, target / f"{extra}-TripoSG")
    shutil.rmtree(scratch, ignore_errors=True)


def patch_sources(target: Path, progress: ProgressFn = _silent) -> None:
    """Die zwei Stellen richten, an denen der Quelltext hier nicht durchläuft.

    Beide sind angesagt und werden vor dem Schreiben geprüft: Wer den Ordner
    später neu holt, bekommt sie erneut, und wer sie schon hat, bekommt sie
    nicht zweimal.
    """
    progress(_("Zwei Stellen im Quelltext richten"))
    utils = target / "triposg" / "inference_utils.py"
    text = utils.read_text(encoding="utf-8")
    # Geprüft wird die Wirkung, nicht der eigene Kommentar: Wer den Marker
    # sucht, den er selbst geschrieben hat, patcht eine von Hand geänderte
    # Datei ein zweites Mal und macht aus ihr Bruch.
    if "try:\n    from diso import DiffDMC" not in text:
        alternative = "from diso import DiffDMC\n"
        if alternative not in text:
            raise SetupFailed(f"{utils.name}: " + str(_("Der erwartete Import steht nicht darin.")))
        text = text.replace(
            alternative,
            "# Von Solidon angepasst: diso ist eine CUDA-Erweiterung ohne\n"
            "# Windows-Wheel und wird nur im Flash-Decoder-Pfad gebraucht.\n"
            "try:\n"
            "    from diso import DiffDMC\n"
            "except ImportError:  # von Solidon\n"
            "    DiffDMC = None\n",
            1,
        )
        utils.write_text(text, encoding="utf-8")

    vae = target / "triposg" / "models" / "autoencoders" / "autoencoder_kl_triposg.py"
    text = vae.read_text(encoding="utf-8")
    if "self.embedder(queries).to(" not in text:
        alternative = "            queries = self.embedder(queries)\n"
        if alternative not in text:
            raise SetupFailed(f"{vae.name}: " + str(_("Der erwartete Aufruf steht nicht darin.")))
        text = text.replace(
            alternative,
            "            # von Solidon: Typ zurückholen — der Fourier-Embedder\n"
            "            # gibt float32 zurück, die nächste Linearschicht trägt\n"
            "            # halbe Gewichte und bricht sonst ab.\n"
            "            queries = self.embedder(queries).to(dtype=z.dtype)\n",
            1,
        )
        vae.write_text(text, encoding="utf-8")


def install_packages(python: Path, progress: ProgressFn = _silent) -> None:
    """Die fehlenden Pakete nachziehen, ohne die Installation umzubauen.

    ``--no-deps`` ist hier kein Geiz, sondern Notwehr: Die Anforderungsliste
    von TripoSG nennt ``numpy==1.22.3``, und wer das durchlässt, hat danach ein
    ComfyUI, das nicht mehr startet.
    """
    _run(
        [str(python), "-s", "-m", "pip", "install", "--no-deps", *PACKAGES],
        _("Pakete für TripoSG nachziehen"),
        progress,
    )


def weights_present(comfyui: Path) -> bool:
    """Liegen die Gewichte schon da?"""
    return (comfyui / "models" / "triposg" / "TripoSG" / "model_index.json").is_file()


def fetch_weights(comfyui: Path, python: Path, progress: ProgressFn = _silent) -> None:
    """Die Gewichte holen — rund 7,5 GB, und nur wenn sie fehlen."""
    if weights_present(comfyui):
        return
    target = comfyui / "models" / "triposg" / "TripoSG"
    _run(
        [
            str(python),
            "-s",
            "-c",
            "from huggingface_hub import snapshot_download;"
            f"snapshot_download({WEIGHTS_REPO!r}, local_dir={str(target)!r}, max_workers=8)",
        ],
        _("Gewichte laden — rund 7,5 GB, das dauert"),
        progress,
    )


def setup(
    comfyui: str | Path | None = None,
    *,
    weights: bool = True,
    progress: ProgressFn = _silent,
    cancelled: CancelledFn | None = None,
) -> Result:
    """Alle Schritte, in dieser Reihenfolge. Wirft :class:`SetupFailed`.

    Abgebrochen wird zwischen den Schritten, nicht in einem: Ein halb
    kopierter Knotenordner oder ein halb entpacktes Modell wäre schlimmer als
    ein Vorgang, der eine Minute länger läuft.
    """
    found = find_comfyui(comfyui)
    python = find_python(found)
    progress(_("ComfyUI gefunden"))

    target = copy_nodes(found, progress)
    if cancelled is not None and cancelled():
        return _stopped(found, target)
    fetch_triposg(target, progress)
    if cancelled is not None and cancelled():
        return _stopped(found, target)
    patch_sources(target, progress)
    install_packages(python, progress)
    if not weights:
        return Result(comfyui=found, nodes=target, weights=weights_present(found))
    if cancelled is not None and cancelled():
        return _stopped(found, target)
    fetch_weights(found, python, progress)
    _log.info("comfy setup finished in %s", found)
    return Result(comfyui=found, nodes=target, weights=True)


def _stopped(comfyui: Path, nodes: Path) -> Result:
    return Result(
        comfyui=comfyui,
        nodes=nodes,
        weights=weights_present(comfyui),
        reason=_("Abgebrochen. Was schon da ist, bleibt — ein neuer Lauf setzt fort."),
    )
