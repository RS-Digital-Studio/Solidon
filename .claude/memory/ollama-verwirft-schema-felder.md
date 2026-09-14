---
name: ollama-verwirft-schema-felder
description: "Ollama parst Werkzeugschemata in eine feste Struktur und verwirft pattern, minimum, maximum, default vor dem Rendern — was das lokale Modell sieht, sind Name, Beschreibung, Typ, Enum, Items; einen zu langen Prompt kürzt es still auf die Hälfte, und reicht Prompt plus Antwort über das Fenster, schiebt llama.cpp den Kontext ohne ein Zeichen in der Antwort (14.09.2026)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 1d7e5e75-9e5f-4fd1-86b2-4be658771056
  modified: 2026-09-14T16:33:06.306Z
---

Gemessen am 14.09.2026 mit `tools/measure_local_model.py` gegen qwen3:14b
(RM-173): Der kompakte Werkzeugsatz kostete 31 465 Token; ohne den
Bindungs-Regex an 618 Feldern (29 664 Zeichen) 31 539 (die Differenz ist ein
neuer Satz im Prompt); ohne `minimum`, `maximum` und `default` **dieselbe**
Zahl. Ollama parst `tools[].function.parameters.properties` in eine feste
Struktur (`type`, `description`, `enum`, `items`) und rendert nur die — alles
andere im JSON kommt beim Modell nie an. Was zählt: Parameterbeschreibungen
(11,7k Token), Werkzeugbeschreibungen (4,7k), das Gerüst aus Namen und Typen
(12,4k), Enums (1,2k), der Systemprompt (1,4k).

Dazu die zweite Messung: Ein Prompt von 4 098 Token gegen `num_ctx` 2 048 kam
mit `prompt_eval_count` 1 026 zurück — kein Hinweis, kein `done_reason`;
Ollama behält den Anfang bis `n_keep` und die zweite Hälfte des Rests. Und
`num_ctx` 40 960 für qwen3:14b läuft auf der RTX 4080 über (`ollama ps`:
16 GB, `10 %/90 % CPU/GPU`).

**Why:** Wer Token spart, indem er Schemafelder streicht, die Ollama ohnehin
verwirft, misst nichts — und wer glaubt, das Modell kenne `@name`, weil es im
Regex steht, irrt: Es hat ihn nie gelesen. `tools/check_local_model.py`
schickte bis zu diesem Tag das volle Schema und maß über Wochen ein still
halbiertes.

**How to apply:** Vor jeder Schema-Optimierung fürs lokale Modell die
Variante mit `measure_local_model` (oder `_ask` am warmen Modell) messen,
nicht die Zeichenzahl. Bei jedem Ollama-Weg `prompt_eval_count` gegen
`PROMPT_TOKENS` halten — `BackendPromptTruncated` tut das im Backend. Siehe
[[pruefjob-nur-beim-tag-hat-nie-gemessen]] und
[[messwerkzeug-misst-sich-selbst]].

**Nachtrag 14.09.2026, abends — die zweite Gestalt.** Im Ollama-Serverlog
(`%LOCALAPPDATA%\Ollama\server.log`) des Suitelaufs: `stop processing:
n_tokens = 16765, truncated = 1` — der zweite Schritt eines Zugs begann mit
32 300 Token und erzeugte 847; llama.cpp schiebt den Kontext, sobald der
nächste Token das Fenster erreicht, behält `n_keep` vorn und verwirft die
Hälfte des Rests. Die API-Antwort trägt nichts davon: `done_reason: stop`,
`prompt_eval_count` zählt den ganzen Prompt (auch den gepufferten Teil).
Erkennbar nur an `prompt_eval_count + eval_count >= num_ctx` —
`BackendContextShifted` prüft genau das. Im Basislauf der Suite waren 16
von 45 Schritten so geschoben. Und: `llama-server started in 146 seconds`
unter Fremdlast (drei Torläufe nebenan) — der Modellstart, nicht der Prompt,
kostet nach jedem entladenen Zug die Minuten; ruhig sind es Sekunden. Wer
Ollama-Zeiten misst, liest die `[GIN]`-Zeilen und die `print_timing`-Zeilen
im Log, sie trennen Laden, Prompt und Antwort.
