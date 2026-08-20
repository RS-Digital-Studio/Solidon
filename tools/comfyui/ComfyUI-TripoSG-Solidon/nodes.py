"""TripoSG als ComfyUI-Knoten — Bild zu Körper, ohne Lizenzhaken.

Warum es diesen Knoten gibt: Hunyuan3D liefert gute Formen, steht aber unter
der Tencent Community License, und deren Geltungsbereich schließt die
Europäische Union ausdrücklich aus. TripoSG (VAST-AI-Research) steht unter
MIT — Code und Gewichte — und ist damit das, was hier gebraucht wird.

Der Knoten hält sich an vier Dinge, die über die Qualität entscheiden:

1. **Das Bild wird zugeschnitten, bevor es das Modell sieht.** Die Pipeline
   reicht das Bild an DINOv2 weiter, und der skaliert auf 518 Pixel herunter.
   Ein Objekt, das ein Viertel des Bildes füllt, kommt dort mit einem Viertel
   der Auflösung an — Details, die nie ankamen, kann kein Diffusionsschritt
   erfinden. Zugeschnitten auf die Silhouette plus Rand ist der größte
   einzelne Hebel, den dieser Knoten hat.
2. **Alpha wird komponiert, nicht durchgereicht.** DINOv2 verwirft den
   Alphakanal. Wer ein freigestelltes Bild ohne Komposition schickt, bekommt
   je nach Bibliothek Schwarz hinter dem Objekt und damit einen Rand, den das
   Modell als Geometrie liest.
3. **Der Flash-Decoder bleibt aus.** Er braucht ``diso``, eine CUDA-Erweiterung
   ohne Windows-Wheel. Marching Cubes über die hierarchische Extraktion
   liefert dieselbe Oberfläche, nur langsamer.
4. **Vereinfacht wird ohne pymeshlab.** Das ist GPL; ``fast_simplification``
   ist MIT und tut hier dasselbe.

Was herauskommt, ist ein Rohkörper. Er wird nicht schöngerechnet — die
Reparatur gehört dorthin, wo sie sichtbar und rücknehmbar ist.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import comfy.model_management as mm  # type: ignore[import-not-found]
import folder_paths  # type: ignore[import-not-found]
import numpy as np
import torch
import trimesh
from PIL import Image

# Der eingebettete TripoSG-Quelltext liegt neben dieser Datei. Er kommt in den
# Suchpfad, statt ihn zu installieren: so bleibt er an das Verzeichnis
# gebunden und kollidiert nicht mit einer zweiten Fassung im Environment.
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from triposg.pipelines.pipeline_triposg import TripoSGPipeline  # noqa: E402

# Eigener Modellordner. ComfyUI kennt ihn nicht von Haus aus, also wird er
# angemeldet — dann taucht das Modell im Auswahlfeld auf, statt als Pfad im
# Graphen zu stehen.
_MODEL_DIR = Path(folder_paths.models_dir) / "triposg"
_MODEL_DIR.mkdir(parents=True, exist_ok=True)


def _available_models() -> list[str]:
    """Die Unterordner von ``models/triposg``, jeder eine Diffusers-Ablage."""
    found = [p.name for p in sorted(_MODEL_DIR.iterdir()) if (p / "model_index.json").is_file()]
    return found or ["TripoSG"]


def _as_pil(image: torch.Tensor, mask: torch.Tensor | None) -> Image.Image:
    """ComfyUI-Tensor zu PIL, Maske als Alpha wenn eine da ist.

    ComfyUI führt Bilder als ``(B, H, W, C)`` in ``0..1``. Genommen wird das
    erste Bild des Stapels: Dieser Knoten erzeugt einen Körper, keine Serie.
    """
    array = (image[0].detach().cpu().numpy() * 255.0).round().clip(0, 255).astype(np.uint8)
    pil = Image.fromarray(array, mode="RGB" if array.shape[2] == 3 else "RGBA").convert("RGBA")

    if mask is not None:
        alpha = (mask[0].detach().cpu().numpy() * 255.0).round().clip(0, 255).astype(np.uint8)
        if alpha.shape[:2] == (pil.height, pil.width):
            pil.putalpha(Image.fromarray(alpha, mode="L"))
    return pil


def _framed(pil: Image.Image, margin: float, background: int) -> Image.Image:
    """Auf die Silhouette zuschneiden, quadratisch fassen, Hintergrund füllen.

    ``margin`` ist der Anteil der längeren Objektkante, der ringsum frei
    bleibt. Ganz ohne Rand schneidet die spätere Skalierung in die Kontur;
    zu viel Rand verschenkt genau die Auflösung, um die es hier geht. Um 0,1
    herum liegt das Optimum, und dort steht auch die Vorgabe.

    Ist kein Alphakanal da oder ist er durchgehend deckend, bleibt das Bild
    wie es ist — dann hat jemand bewusst ein volles Bild geschickt.
    """
    alpha = pil.getchannel("A")
    box = alpha.getbbox()
    if box is None or box == (0, 0, pil.width, pil.height):
        flat = Image.new("RGB", pil.size, (background,) * 3)
        flat.paste(pil, mask=alpha)
        return flat

    left, top, right, bottom = box
    width, height = right - left, bottom - top
    # Quadratisch fassen: die Pipeline skaliert ohnehin auf ein Quadrat, und
    # wer das ihr überlässt, lässt sie das Objekt verzerren.
    side = int(max(width, height) * (1.0 + 2.0 * margin))

    canvas = Image.new("RGB", (side, side), (background,) * 3)
    cut = pil.crop(box)
    canvas.paste(cut, (side // 2 - width // 2, side // 2 - height // 2), mask=cut.getchannel("A"))
    return canvas


#: Unterhalb dieser Kantenlänge — gemessen im Einheitswürfel, in dem TripoSG
#: rechnet — ist das Ergebnis kein Körper mehr, sondern ein Rest.
_COLLAPSED_EXTENT = 0.01

#: Und unterhalb dieser Dreieckszahl ebenfalls. Beide zusammen, weil eine
#: entgleiste Rechnung mal zwei Dreiecke an einem Punkt liefert und mal ein
#: paar hundert auf einer Fläche ohne Dicke.
_COLLAPSED_FACES = 64


def _collapsed(vertices: np.ndarray, faces: np.ndarray) -> bool:
    """Ist das kein Körper, sondern ein Rest?"""
    if vertices.size == 0 or faces.size == 0 or len(faces) < _COLLAPSED_FACES:
        return True
    return float(np.ptp(vertices, axis=0).max()) < _COLLAPSED_EXTENT


def _refuse_empty(vertices: np.ndarray, faces: np.ndarray, *, seed: int, steps: int) -> None:
    """Bricht ab, wenn die Rechnung nichts als einen Rest hergegeben hat.

    Beobachtet wurde dieser Fall bisher nicht — geprüft wird er trotzdem, und
    zwar hier und nicht später. Ein Splitter, der ungeprüft weiterläuft, ist
    schlimmer als ein Fehler: Die Reparaturkette macht daraus ein Dreieck,
    jede folgende Operation meldet brav Erfolg, und am Ende steht ein leeres
    Projekt, dem niemand ansieht, wo es schiefging. Genau so sah es aus, als
    die Auswahl der größten Komponente noch Volumen mit Dreieckszahl verglich.

    Die Zahlen, die der Nutzer ändern kann, stehen mit im Satz — ohne sie wäre
    die Meldung nur eine Feststellung (Regel 17).
    """
    if not _collapsed(vertices, faces):
        return
    raise RuntimeError(
        f"TripoSG hat keinen Körper geliefert, sondern einen Rest "
        f"({len(faces)} Dreiecke). Zeigt das Bild kein freigestelltes "
        f"Einzelobjekt, liegt es daran. Sonst hilft, in dieser Reihenfolge: "
        f"einen anderen Startwert als {seed} nehmen, die Schritte über {steps} "
        f"hinaus erhöhen, oder das Modell mit precision=float32 laden."
    )


class TripoSGLoader:
    """Lädt die Pipeline einmal und hält sie."""

    # Ein Modell laden kostet Sekunden und Gigabyte. Der Cache hängt am
    # Knoten und nicht am Auftrag, sonst zahlt jeder Lauf denselben Preis.
    _cache: dict[tuple[str, str], Any] = {}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "model": (_available_models(),),
                "precision": (["float16", "bfloat16", "float32"], {"default": "float16"}),
            }
        }

    RETURN_TYPES = ("TRIPOSG_PIPE",)
    RETURN_NAMES = ("pipeline",)
    FUNCTION = "load"
    CATEGORY = "TripoSG"

    def load(self, model: str, precision: str) -> tuple[Any]:
        key = (model, precision)
        if key in self._cache:
            return (self._cache[key],)

        dtype = {"float16": torch.float16, "bfloat16": torch.bfloat16, "float32": torch.float32}[
            precision
        ]
        path = _MODEL_DIR / model
        if not (path / "model_index.json").is_file():
            raise FileNotFoundError(
                f"Unter {path} liegt kein TripoSG-Modell. Erwartet wird eine "
                "Diffusers-Ablage mit model_index.json, transformer/, vae/ und "
                "image_encoder_dinov2/."
            )

        pipeline = TripoSGPipeline.from_pretrained(str(path), torch_dtype=dtype)
        pipeline.to(mm.get_torch_device())
        self._cache[key] = pipeline
        return (pipeline,)


class TripoSGImageToMesh:
    """Ein Bild hinein, ein Rohkörper heraus."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "pipeline": ("TRIPOSG_PIPE",),
                "image": ("IMAGE",),
                "steps": ("INT", {"default": 50, "min": 8, "max": 100}),
                "guidance_scale": ("FLOAT", {"default": 7.0, "min": 1.0, "max": 20.0, "step": 0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                # Die Auflösung des Extraktionsgitters. Gemessen an vier
                # Fällen bringt 9 gegenüber 8 keinen sichtbaren Unterschied,
                # kostet aber die vierfache Dreieckszahl und die doppelte
                # Zeit — die Vorgabe steht deshalb auf 8. Wer ein Teil mit
                # sehr feinen Durchbrüchen hat, dreht sie hoch.
                "octree_depth": ("INT", {"default": 8, "min": 6, "max": 10}),
                "crop_margin": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 0.5, "step": 0.01}),
            },
            "optional": {
                "mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("TRIPOSG_MESH",)
    RETURN_NAMES = ("mesh",)
    FUNCTION = "generate"
    CATEGORY = "TripoSG"

    def generate(
        self,
        pipeline: Any,
        image: torch.Tensor,
        steps: int,
        guidance_scale: float,
        seed: int,
        octree_depth: int,
        crop_margin: float,
        mask: torch.Tensor | None = None,
    ) -> tuple[trimesh.Trimesh]:
        prepared = _framed(_as_pil(image, mask), crop_margin, background=255)
        device = mm.get_torch_device()

        def rechnen(schritte: int) -> tuple[np.ndarray, np.ndarray]:
            # Der Zufallsgeber wird jedes Mal neu gesetzt: Er führt einen
            # Zustand, und ein zweiter Lauf auf demselben Objekt wäre sonst
            # ein anderer — genau das, was ein gespeicherter Startwert
            # verhindern soll.
            generator = torch.Generator(device=device).manual_seed(int(seed))
            output = pipeline(
                image=prepared,
                num_inference_steps=schritte,
                guidance_scale=float(guidance_scale),
                generator=generator,
                # Der hierarchische Pfad braucht kein diso. Beide Tiefen ziehen
                # mit, sonst arbeitet die feine Stufe auf einem groben Gitter.
                use_flash_decoder=False,
                dense_octree_depth=int(octree_depth) - 1,
                hierarchical_octree_depth=int(octree_depth),
            )
            return (
                np.asarray(output.samples[0][0], dtype=np.float64),
                np.asarray(output.samples[0][1], dtype=np.int64),
            )

        vertices, faces = rechnen(int(steps))
        _refuse_empty(vertices, faces, seed=int(seed), steps=int(steps))

        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        mm.soft_empty_cache()
        return (mesh,)


class TripoSGPostprocess:
    """Das Nötigste aufräumen — mehr nicht.

    Ein Generator liefert lose Fetzen und entartete Dreiecke als Normalfall.
    Die kommen hier weg, weil sie jede weitere Rechnung stören. Alles
    darüber hinaus — Löcher schliessen, wasserdicht machen, ausrichten —
    bleibt bewusst aus: das gehört an die Stelle, an der es ein Mensch sieht
    und zurücknehmen kann.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "mesh": ("TRIPOSG_MESH",),
                "keep_largest_only": ("BOOLEAN", {"default": True}),
                "remove_degenerate": ("BOOLEAN", {"default": True}),
                "target_faces": ("INT", {"default": 0, "min": 0, "max": 2000000, "step": 10000}),
            }
        }

    RETURN_TYPES = ("TRIPOSG_MESH", "STRING")
    RETURN_NAMES = ("mesh", "report")
    FUNCTION = "clean"
    CATEGORY = "TripoSG"

    def clean(
        self,
        mesh: trimesh.Trimesh,
        keep_largest_only: bool,
        remove_degenerate: bool,
        target_faces: int,
    ) -> tuple[trimesh.Trimesh, str]:
        before = len(mesh.faces)
        work = mesh.copy()

        if remove_degenerate:
            work.update_faces(work.nondegenerate_faces())
            work.remove_unreferenced_vertices()
            work.merge_vertices()

        if keep_largest_only:
            parts = work.split(only_watertight=False)
            if len(parts) > 1:
                # Nach Volumen, und die Dreieckszahl entscheidet nur bei
                # Gleichstand. Als Tupel und nicht als ``volume or faces``:
                # Ein offenes Fragment hat das Volumen 0,0 — und weil das
                # falsch ist im Sinne von Python, fiel der Ausdruck auf seine
                # Dreieckszahl zurück und verglich sie mit dem *Volumen* der
                # anderen. Zwei Dreiecke schlugen so einen Körper von 1,57,
                # und aus einem vollständigen Modell wurde ein Splitter.
                work = max(parts, key=lambda part: (abs(part.volume), len(part.faces)))

        if target_faces and len(work.faces) > target_faces:
            work = work.simplify_quadric_decimation(face_count=target_faces)

        work.fix_normals()
        report = (
            f"faces {before} -> {len(work.faces)}, "
            f"watertight={work.is_watertight}, "
            f"volume={work.volume:.4f}"
        )
        return (work, report)


class TripoSGExportMesh:
    """Schreibt den Körper in den Ausgabeordner und meldet den Pfad."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "mesh": ("TRIPOSG_MESH",),
                "filename_prefix": ("STRING", {"default": "solidon/triposg"}),
                "file_format": (["glb", "stl", "obj", "ply"], {"default": "glb"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("path",)
    FUNCTION = "export"
    CATEGORY = "TripoSG"
    OUTPUT_NODE = True

    def export(
        self, mesh: trimesh.Trimesh, filename_prefix: str, file_format: str
    ) -> dict[str, Any]:
        full, name, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, folder_paths.get_output_directory()
        )
        filename = f"{name}_{counter:05}_.{file_format}"
        mesh.export(str(Path(full) / filename))

        # Der relative Pfad ist das, was ein Aufrufer über ``/view`` wieder
        # herunterladen kann. Beide Schreibweisen werden gemeldet, weil
        # verschiedene Leser verschiedene erwarten: die Vorschau nimmt den
        # blanken Pfad, die Bildknoten das Feld-Format.
        relative = f"{subfolder}/{filename}" if subfolder else filename
        return {
            "ui": {
                "3d": [relative],
                "result": [{"filename": filename, "subfolder": subfolder, "type": "output"}],
            },
            "result": (relative,),
        }


NODE_CLASS_MAPPINGS = {
    "TripoSGLoader": TripoSGLoader,
    "TripoSGImageToMesh": TripoSGImageToMesh,
    "TripoSGPostprocess": TripoSGPostprocess,
    "TripoSGExportMesh": TripoSGExportMesh,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TripoSGLoader": "TripoSG — Modell laden",
    "TripoSGImageToMesh": "TripoSG — Bild zu Körper",
    "TripoSGPostprocess": "TripoSG — Aufräumen",
    "TripoSGExportMesh": "TripoSG — Exportieren",
}
