"""RM-004: Weg 3 echt — Text und Bild über ComfyUI bis zum Export, ohne Fenster.

Aufruf aus der Wurzel des Repositorys, ComfyUI muss unter 127.0.0.1:8188 laufen:

    .venv\\Scripts\\python.exe .claude\\.state\\ki-2026-10-06\\weg3_echt.py <ausgabeordner>

Nutzerverzeichnisse gehen in einen Temp-Ordner (Roberts Daten bleiben
unberührt), die Demofrist wird wie in ``tests/conftest.py`` aufgehoben. Das
Eingangsbild des Bildwegs erzeugt SDXL hier selbst — kein fremdes Foto.
Geschrieben wird ein Protokoll ``bericht.json`` mit Revisionen, Kennzahlen,
Befunden, Zeiten und den Prüfsummen der Exportdateien.
"""

import hashlib
import json
import os
import platform
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
_scratch = Path(tempfile.mkdtemp(prefix="rm004-"))
os.environ["APPDATA"] = str(_scratch / "roaming")
os.environ["LOCALAPPDATA"] = str(_scratch / "local")
sys.path.insert(0, str(ROOT))

from app.core.activation import store as activation_store  # noqa: E402

activation_store.DEMO_UNTIL = None
activation_store.TRIAL_FROM = activation_store.DEMO_FROM

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.backends import comfy_setup  # noqa: E402
from app.core.backends.mesh import ComfyBackend  # noqa: E402
from app.core.export.writer import plan_export, write_plan  # noqa: E402
from app.core.generate import from_image, from_text  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.scene import evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, load, new_project, save  # noqa: E402

PROMPT = "a small vase with a wavy rim"
IMAGE_PROMPT = "a small toy rocket with three fins"
SEED = 7
URL = "http://127.0.0.1:8188"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sdxl_image(prompt: str, seed: int) -> bytes:
    """Ein Eingangsbild aus SDXL — derselbe Bildteil wie im Textablauf."""
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": comfy_setup.IMAGE_MODEL_FILE}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": f"{prompt}, single complete object, centered, full object visible, three-quarter view, even studio lighting, plain white background, product photo, sharp focus"}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "blurry, multiple objects, cropped, text, watermark, person"}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "seed": seed, "steps": 25, "cfg": 6.0, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "solidon/rm004"}},
    }
    body = json.dumps({"prompt": graph, "client_id": str(uuid.uuid4())}).encode()
    with urllib.request.urlopen(urllib.request.Request(f"{URL}/prompt", body, {"Content-Type": "application/json"}), timeout=30) as answer:
        prompt_id = json.load(answer)["prompt_id"]
    for _ in range(600):
        with urllib.request.urlopen(f"{URL}/history/{prompt_id}", timeout=30) as answer:
            history = json.load(answer)
        if prompt_id in history and history[prompt_id].get("outputs"):
            image = history[prompt_id]["outputs"]["7"]["images"][0]
            query = urllib.parse.urlencode({"filename": image["filename"], "subfolder": image["subfolder"], "type": image["type"]})
            with urllib.request.urlopen(f"{URL}/view?{query}", timeout=60) as answer:
                return answer.read()
        time.sleep(2)
    raise SystemExit("SDXL-Bild kam nicht")


def free_card() -> None:
    """Nach jedem Auftrag die Karte freigeben, wie der Vertrag in backends/CLAUDE.md."""
    body = json.dumps({"unload_models": True, "free_memory": True}).encode()
    urllib.request.urlopen(urllib.request.Request(f"{URL}/free", body, {"Content-Type": "application/json"}), timeout=30).read()


def run(way: str, make) -> dict:
    project = new_project("centauri-carbon-2", "petg")
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    started = time.perf_counter()
    generation = make(project)
    generated = time.perf_counter() - started
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    body = result.scene.objects[generation.object_id]
    path = OUT / f"{way}.p3d"
    save(project, path)
    reopened = load(path)
    again = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    reopened_body = again.scene.objects[generation.object_id]
    files = []
    for fmt in ("stl", "3mf"):
        plan = plan_export([reopened_body], project_name=way, profile=profile, export_format=fmt, scene=again.scene, document=reopened.document)
        target = OUT / fmt
        target.mkdir(exist_ok=True)
        files += [{"datei": str(p.relative_to(OUT)), "bytes": p.stat().st_size, "sha256": sha(p)} for p in write_plan(plan, target, fmt)]
    raw = OUT / f"{way}-roh{generation.result.suffix}"
    raw.write_bytes(generation.result.payload)
    free_card()
    return {
        "weg": way,
        "prompt": generation.result.prompt,
        "seed": generation.result.seed,
        "erzeugen_s": round(generated, 1),
        "roh": {"datei": raw.name, "bytes": raw.stat().st_size, "sha256": sha(raw), "dreiecke": generation.result.mesh.triangle_count},
        "schritte": [op.op for op in project.document.ops],
        "transaktionen": len(project.document.transactions),
        "koerper": {
            "dreiecke": body.mesh.triangle_count,
            "geschlossen": bool(body.mesh.is_watertight),
            "volumen_cm3": round(body.mesh.volume / 1000.0, 2),
            "masse_mm": [round(v, 1) for v in body.mesh.bounds.size],
        },
        "befunde": [{"code": f.code, "schwere": f.severity, "satz": str(f.message)} for f in result.scene.report.findings],
        "wiedergeoeffnet_gleich": bool(abs(reopened_body.mesh.volume - body.mesh.volume) < 1e-6 and reopened_body.mesh.triangle_count == body.mesh.triangle_count),
        "export": files,
    }


backend = ComfyBackend()
report = {
    "datum": time.strftime("%Y-%m-%d %H:%M:%S"),
    "plattform": f"{platform.system()} {platform.release()} {platform.machine()}",
    "python": sys.version.split()[0],
    "revisionen": {
        "triposg_commit": comfy_setup.TRIPOSG_COMMIT,
        "triposg_gewichte": f"{comfy_setup.WEIGHTS_REPO}@{comfy_setup.WEIGHTS_REVISION}",
        "freistellen": f"{comfy_setup.BACKGROUND_REPO}@{comfy_setup.BACKGROUND_REVISION} ({comfy_setup.BACKGROUND_SHA256})",
        "bildmodell": f"{comfy_setup.IMAGE_MODEL_REPO}@{comfy_setup.IMAGE_MODEL_REVISION} ({comfy_setup.IMAGE_MODEL_SHA256})",
        "comfyui": str(comfy_setup.find_comfyui()),
    },
    "bereitschaft": {w: str(backend.readiness(w)) for w in ("text_to_mesh", "image_to_mesh")},
    "laeufe": [],
}
report["laeufe"].append(run("text", lambda project: from_text(project, backend, PROMPT, seed=SEED)))
image = sdxl_image(IMAGE_PROMPT, SEED)
(OUT / "eingang.png").write_bytes(image)
report["eingangsbild"] = {"prompt": IMAGE_PROMPT, "seed": SEED, "sha256": hashlib.sha256(image).hexdigest()}
free_card()
report["laeufe"].append(run("bild", lambda project: from_image(project, backend, image, seed=SEED)))
(OUT / "bericht.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=1))
