"""TRELLIS.2- und FLUX.2-[klein]-Gewichte für die Messung laden (RM-003/RM-004).

Läuft im Python von ComfyUI (dort liegt huggingface_hub). Jede Datei mit fester
Revision; danach SHA-256 gegen den Wert aus dem Ersatzbericht, erst dann an
ihren Platz unter models/. Bricht bei einer falschen Prüfsumme ab.
"""

import hashlib
import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

MODELS = Path(sys.argv[1])
SCRATCH = MODELS.parent / "_solidon_download"
FILES = [
    ("Comfy-Org/TRELLIS.2", "430a9d09b2416687018c8fe8edced2ad4858a439",
     "diffusion_models/trellis_2_int8_convrot.safetensors", "diffusion_models",
     "d01952ad137213f6a868f86b6b877026276f84af5eec23069217475a0bad3a31"),
    ("Comfy-Org/TRELLIS.2", "430a9d09b2416687018c8fe8edced2ad4858a439",
     "vae/trellis_2_shape_vae_bf16.safetensors", "vae",
     "de0cb4949a76c59ee5c091a995a69bcc8c51d5aeda939f0c641a50d2a72341f4"),
    ("Comfy-Org/TRELLIS.2", "430a9d09b2416687018c8fe8edced2ad4858a439",
     "clip_vision/dino_v3_vit_l.safetensors", "clip_vision",
     "5cb785e458de7c460579082418af81f5c62380c181599344bdc60898c63468ee"),
    ("black-forest-labs/FLUX.2-klein-4b-fp8", "5b4408e59397a4a37ccb46afe426d8ed86379441",
     "flux-2-klein-4b-fp8.safetensors", "diffusion_models",
     "97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6"),
    ("Comfy-Org/vae-text-encorder-for-flux-klein-4b", "5f526678002e43af5551dadb73ce2e8c91b43afe",
     "split_files/text_encoders/qwen_3_4b_fp4_flux2.safetensors", "text_encoders",
     "3eab03a77adb0ee5304a4e677d5c10ac22f9049c1d7c894adca4f8bb39206ca8"),
    ("Comfy-Org/vae-text-encorder-for-flux-klein-4b", "5f526678002e43af5551dadb73ce2e8c91b43afe",
     "split_files/vae/flux2-vae.safetensors", "vae",
     "868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


for repo, revision, name, folder, expected in FILES:
    target = MODELS / folder / Path(name).name
    if target.exists() and sha256(target) == expected:
        print("vorhanden", target, flush=True)
        continue
    got = Path(hf_hub_download(repo, name, revision=revision, local_dir=str(SCRATCH)))
    actual = sha256(got)
    if actual != expected:
        raise SystemExit(f"Prüfsumme falsch: {name} {actual} statt {expected}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(got), str(target))
    print("geladen", target, target.stat().st_size, flush=True)
shutil.rmtree(SCRATCH, ignore_errors=True)
print("fertig", flush=True)
