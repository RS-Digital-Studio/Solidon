---
name: comfyui-installation-d-ai
description: "ComfyUI liegt real auf D:\\AI, F:\\AI ist nur eine Junction — Tracebacks nennen D:, und die Knoten sind die 2.1-Sammlung."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 493de4ef-2355-4029-9d86-1e68996c4909
  modified: 2026-08-30T08:11:06.391Z
---

> **Überholt am 30.08.2026: Es läuft ein anderes ComfyUI.** `find_comfyui()`
> findet das **Comfy Desktop** unter
> `C:\Users\rober\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI`
> — über die Registrierungsdatei, die Comfy Desktop selbst schreibt, nicht
> über die Rateorte. Dort liegen TripoSG und BiRefNet, und dort lief der
> gemessene Bildweg (14,9 s, 112 564 Dreiecke, wasserdicht). Sein Python samt
> `huggingface_hub` steht unter `…\ComfyUI\.venv\Scripts\python.exe`.
> Alles Weitere unten gilt für die portable Installation — nur ist sie nicht
> mehr die, die Solidon anspricht.

Die ComfyUI-Installation, gegen die Formwerks Mesh-Erzeugung lief, liegt
physisch unter `D:\AI\ComfyUI_windows_portable`. `F:\AI\ComfyUI_windows_portable`
ist eine **Junction** darauf — Tracebacks aus ComfyUI nennen deshalb `D:\`,
auch wenn man über `F:\` gearbeitet hat. Das ist kein zweiter Baum.

Stand (07.08.2026): ComfyUI 0.22.0, embedded Python 3.12.10, PyTorch
2.12.0+cu130, RTX 4080 mit 16 GB. Start über
`python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build
--disable-auto-launch`, Port 8188.

Solidons eigener Ablauf benutzt diese Sammlung **nicht mehr** — siehe
[[triposg-statt-hunyuan]]. Sie ist aber weiterhin installiert, und wer einen
eigenen Graphen fährt, findet sie so vor:

Für die 3D-Erzeugung ist **`ComfyUI-Hunyuan3d-2-1`** installiert, nicht Kijais
`ComfyUI-Hunyuan3DWrapper`. Die Knotennamen unterscheiden sich vollständig:
`Hy3DMeshGenerator`, `Hy3D21VAELoader`, `Hy3D21VAEDecode`,
`Hy3D21PostprocessMesh`, `Hy3D21ExportMesh` — es gibt **keinen**
`Hy3DModelLoader` und keinen `Hy3DGenerateMesh`. Gewichte liegen als
`hunyuan3d-dit-v2-1-fp16.ckpt` (diffusion_models) und
`Hunyuan3D-vae-v2-1-fp16.ckpt` (vae).

Zwei Fallen beim Ansprechen über die HTTP-API:

- **Jeder Eingang muss gesetzt sein**, auch ein als `optional` deklarierter.
  Die Oberfläche schickt immer alle mit; Knoten wie `RMBG` und
  `Hy3D21VAEDecode` lesen sie ungeprüft und werfen sonst `KeyError` bzw.
  `missing positional arguments`.
- **Der Rückgabeweg ist ein blanker Pfad.** `Hy3D21ExportMesh` taucht in
  `/history` gar nicht auf; erst ein nachgeschaltetes `Preview3D` liefert
  `{"result": ["ordner\\datei.glb", null, null]}` — ein String, kein Eintrag
  mit Feldern. Siehe [[formwerk-mesh-erzeugung-geprueft]].

Hunyuan3D 2.1 hat **keinen Texteingang**. Text zu Mesh geht nur über
Text → Bild (SDXL) → Freistellen → Bild zu Mesh.
