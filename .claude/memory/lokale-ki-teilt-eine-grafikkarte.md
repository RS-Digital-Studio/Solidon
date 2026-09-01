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
