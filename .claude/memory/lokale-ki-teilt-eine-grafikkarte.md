---
name: lokale-ki-teilt-eine-grafikkarte
description: "Ollama, ComfyUI, VTK und der Desktop teilen denselben VRAM; lokale KI-Läufe müssen serialisiert und danach entladen werden."
metadata:
  node_type: memory
  type: reference
  modified: 2026-09-01
---

Ein lokales KI-Backend ist nicht nur ein Hintergrunddienst, sondern ein
Besitzer der gemeinsamen Grafikkarte. Gemessen am 01.09.2026 belegte
`qwen3:14b` mit `num_ctx=32768` 13.707 MiB einer 16-GB-RTX-4080. Ein danach
gestarteter ComfyUI-Lauf musste zusätzlich SDXL, CLIP, BiRefNet und TripoSG
laden und dauerte 193,74 Sekunden; kurz darauf folgte ein harter Neustart mit
Kernel-Power 41, ohne Bugcheck, TDR oder VTK-Fehler.

Darum gelten drei Verträge zusammen:

- Lokale Ollama- und ComfyUI-Läufe aus Solidon werden über eine gemeinsame
  Schwerlastspur serialisiert.
- Ollama bleibt nur zwischen den Schritten eines Agentenvorschlags warm und
  wird danach auch bei Fehler oder Abbruch mit `keep_alive: 0` entladen.
- ComfyUI erhält beim Abbruch die konkrete `prompt_id`; wartende Aufträge
  werden über `/queue` gelöscht, laufende gezielt über `/interrupt` beendet.
  Nach dem Auftrag gibt `/free` den lokalen Modellcache frei.

Entfernte Server werden weder gesperrt noch entladen: Sie können geteilt sein
und gehören nicht ausschließlich dieser Anwendung.

**Nachtrag 15.09.2026 — die Kante kostet Minuten, nicht nur Platz.** qwen3:14b
mit `num_ctx` 32 768 braucht 14,4 GB; mit 1,6 GB Desktop (dwm, Claude,
Chrome) bleiben 14,7 frei. Die Gewichte sind in acht Sekunden oben, danach
kriecht der KV-Cache (5 GB f16) mit 60 MB/s in den Speicher, weil der
Windows-Treiber am Rand umlagert: 56 bis 314 s je Modellstart, und
`keep_alive: 0` zahlt das je Zug. Am Nachmittag mit leererem Desktop derselbe
Start in Sekunden. Wer Ollama-Zeiten misst, schreibt die freie VRAM-Menge
vor dem Start dazu (`nvidia-smi --query-gpu=memory.used`); wer sie senken
will, hat zwei Hebel: Warmhalten (Vertrag oben) oder `OLLAMA_KV_CACHE_TYPE=q8_0`
am Dienst, das die 5 GB halbiert (RM-081).
