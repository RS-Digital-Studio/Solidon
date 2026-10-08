# `app/core/backends/` — was von außen kommt

LLM und Mesh-Erzeuger, jeweils hinter einer Schnittstelle (§27). **Beides
extern, beides abschaltbar** — ohne Netz, ohne Konto und ohne KI bleibt alles
außer dem Chat benutzbar. Einzuhalten ist `.claude/rules/agentenschicht.md`
(dort auch Kontextfenster, Kürzung und warm gehaltene Modelle), dazu
`kern.md` („Einrichten heißt nicht laufen“); Anlässe:
`konzepte/begruendungen/karte-app-core-backends.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `llm.py` | Das Sprachmodell hinter dem Agenten — gehostet oder lokal (Ollama); `OLLAMA_CONTEXT_TOKENS`, `OLLAMA_ANSWER_TOKENS`, `prompt_was_cut`, `PROMPT_TOKENS`/`PROMPT_TOOL_COUNT` |
| `mesh.py` | Mesh-Erzeugung für Weg 3, lokal oder gehostet (Säule B) |
| `resources.py` | Gemeinsame Schwerlastspur für lokale KI auf derselben Grafikkarte (`local_ai_slot`, `keep_warm`) |
| `machine.py` | Was dieser Rechner mitbringt: Apple Silicon und Arbeitsspeicher über das System, eine NVIDIA-Karte über `nvidia-smi` (`this_machine`, `Machine.graphics_gb`) |
| `needs.py` | Die eine Quelle für Voraussetzungen vor dem Laden: was ein Modell bzw. Weg 3 braucht, ob dieser Rechner es hat, und der Ausweg (`chat_needs`, `graphics_verdict`, `chat_disk_need`, `pull_space_problem`, `generator_needs`, `duration_text`) |
| `keys.py` | Wo der eigene Schlüssel des Nutzers liegt |
| `comfy_setup.py` | Ein fremdes ComfyUI für Weg 3 einrichten (§36): Fassung prüfen (`check_version`), Modelldateien laden (`ModelFile`: Repo, Revision, Byte, SHA-256, Zielordner, Rolle) — TRELLIS.2 und BiRefNet für den Bildweg, auf Wunsch FLUX.2 [klein] 4B für den Textweg —, Reste der TripoSG-Einrichtung räumen (`remove_legacy`) |
| `data/text_to_image.json`, `data/image_to_mesh.json` | Die ComfyUI-Abläufe: Bild aus Text und Netz aus Bild; der Weg aus Text fährt beide nacheinander (`mesh.WORKFLOW_STAGES`), nur aus eingebauten Knoten (ab ComfyUI 0.35); geprüft gegen `tests/data/comfyui/object_info.json`, erzeugt mit `tools/comfy_node_info.py` |

`comfy_setup.py` und `data/` liegen im Kern, weil `tools/` im gebauten Paket
**nicht mitreist** — was der Nutzer aus der laufenden Anwendung heraus
einrichten soll, muss hier stehen. **Umgekehrt gehört nichts hierher, was nur
ein Test braucht**: Das Modell mit vorgeschriebenen Antworten und der
Generator der Suite (`ScriptedMeshBackend`) liegen in
`tests/scripted_backend.py` — Sitzungsverlauf, Werkzeugaufrufe und
Transaktionskopplung sind so ohne echtes Modell prüfbar (§35, §40); die echte
Messung ist die Agenten-Suite.

## Das lokale Modell

- **Ohne `num_ctx` schneidet Ollama den Prompt still ab** — ein Modell, das die
  Werkzeuge nicht aufruft, hat sie dann nie gesehen. `tools/check_local_model.py`
  prüft das, bevor eine Modellmessung etwas aussagt.
- **Kürzung erkennen** (`prompt_was_cut`, Regel in `agentenschicht.md`):
  `request_length` misst den gesendeten Text, `least_tokens`/`most_tokens`
  spannen mit `LEAST_CHARS_PER_TOKEN` und `MOST_CHARS_PER_TOKEN` den Bereich
  auf, den ein Tokenizer daraus zählen kann — die obere Schranke absichtlich
  weit.
- **Antwortgrenze** in `llm.py`: `OLLAMA_ANSWER_TOKENS` als `num_predict`;
  Ollama meldet den Abbruch als `length` (`TRUNCATED_STOPS`). Regel in
  `agentenschicht.md`.
- **Der abbrechbare HTTP-Transport** hält den verbundenen Socket bis zum Ende
  des Request-Threads; ein Abbruch erreicht so auch bei HTTP/1.0 und
  `Connection: close` den Antwortkörper. Antwort und Verbindung schließt der
  Request-Thread selbst; der Aufrufer wartet nach einem Abbruch höchstens
  `CANCEL_JOIN_SECONDS` auf ihn und protokolliert, wenn er nicht endet.
  Entsteht die Verbindung erst während eines Abbruchs, verhindert die erneute
  Tokenprüfung das POST. Über HTTP liest und sendet der Request-Thread an einem
  `_WatchedSocket`, der den Abbruch selbst bemerkt (`CANCEL_WATCH_SECONDS`):
  Ein `shutdown` aus dem wartenden Thread weckte das `recv` unter macOS nicht
  sicher, und über Ungelesenem setzt er die Verbindung unter Windows zurück.
  Die Verbindung baut `_local_connection`; Tests setzen dort ihre Attrappe ein.
- **Vor dem Laden die Voraussetzungen** (RM-564, Entscheidung Robert):
  `Machine.graphics_gb` ist auf Apple Silicon der Anteil, den macOS der
  Grafik lässt, sonst eine erkannte Karte abzüglich `CARD_RESERVE_GB`.
  `recommended_ollama_model` wählt das beste gemessene Modell, das ganz
  hineinpasst, `default_ollama_model` sonst das kleinste — beide nur, wenn
  Ollama hier rechnet (`ollama_runs_here`). Die Sätze stehen in `needs.py`;
  Mac-Werte sind gerechnet und sagen es. Gefragt wird nur über
  `machine.this_machine()`, erhoben im Arbeiter — die Suite setzt dort einen
  neutralen Rechner ein.
- **`PROMPT_TOKENS` und `PROMPT_TOOL_COUNT`** stehen in `llm.py` und gehören
  zu derselben gezählten Anfrage; gezählt wird mit
  `tools/measure_local_model.py --count-tokens` (ein Antworttoken, JSON mit
  SHA-256 der Anfrage). Wann und wie neu gezählt wird: `agentenschicht.md`.

## Lokale KI teilt eine Grafikkarte

- **Ollama und ComfyUI laufen nie gleichzeitig durch Solidon**:
  `resources.local_ai_slot()` serialisiert nur Loopback-Adressen, entfernte
  Server bleiben unberührt. Das Warten meldet einmal den Grund, bleibt
  abbrechbar und endet nach zehn Minuten mit dem erneuten Versuch als
  Vorschlag; eine abgewiesene Chat-Freigabe betritt die Spur nicht.
- **Nach dem Zug bleibt das Modell geladen, bis ein anderer die Karte
  braucht** (Regel: `agentenschicht.md`): `resource_session` trägt es mit
  `resources.keep_warm(holder, release)` ein, `local_ai_slot(..., holder=...)`
  gibt beim Betreten jedes fremde frei. Ein ComfyUI-Lauf nennt keinen Halter
  und räumt die Karte ganz; Werkzeugprobe und Geschwindigkeitsmessung tragen
  ihr Modell ebenso ein (`_stays_warm`). Die Suite leert die Liste je Test
  (`tests/conftest.py`). **Das Beenden gibt frei**
  (`release_warm_before_exit` an `aboutToQuit` in `app/ui/app.py`), in einem
  Faden mit fünf Sekunden Frist.
- **Abbruch in ComfyUI** nur für Solidons eigene Auftrags-ID über
  `POST /api/jobs/{job_id}/cancel` (atomar; `cancelled: false` bestätigt einen
  beendeten oder unbekannten Auftrag). Ohne diese Fähigkeit wird nur der
  eigene Eintrag über `/queue` entfernt — ein älterer Server rechnet einen
  laufenden Auftrag dann zu Ende. `/interrupt` wird nie gerufen. Nach jedem
  Auftrag wird der Modellcache freigegeben. Vertrag:
  [ComfyUIs server.py](https://github.com/Comfy-Org/ComfyUI/blob/master/server.py),
  `_cancel_job_by_id` und `interrupt_if_running`.

## Die Modelle und ihre Dateien

| Rolle | Modell (Lizenz) | Datei | Ordner |
|---|---|---|---|
| `shape` | TRELLIS.2-4B, Microsoft (MIT) | `trellis_2_int8_convrot.safetensors` | `models/diffusion_models` |
| `shape_vae` | TRELLIS.2-Form-VAE (MIT) | `trellis_2_shape_vae_bf16.safetensors` | `models/vae` |
| `image_encoder` | DINOv3 ViT-L/16, Meta (DINOv3 License) | `dino_v3_vit_l.safetensors` | `models/clip_vision` |
| `background` | BiRefNet (MIT) | `birefnet.safetensors` | `models/background_removal` |
| `image` | FLUX.2 [klein] 4B, Black Forest Labs (Apache-2.0) | `flux-2-klein-4b-fp8.safetensors` | `models/diffusion_models` |
| `text_encoder` | Qwen3-4B (Apache-2.0) | `qwen_3_4b_fp4_flux2.safetensors` | `models/text_encoders` |
| `image_vae` | FLUX.2-VAE | `flux2-vae.safetensors` | `models/vae` |

Revisionen, Byte und SHA-256 stehen an `comfy_setup.SHAPE_FILES`,
`BACKGROUND` und `IMAGE_MODEL_FILES`; Belege und Kanzleifragen in
`konzepte/nachweise-generatoren-2026-10/`.

- **Die Rolle entscheidet, nicht der Dateiname** (`mesh.role_candidates`):
  Auflösung beim Erzeugen, `missing_models`, die Auswahl im Dialog und
  `comfy_setup.file_present` fragen dieselbe Funktion. Rollen im geteilten
  Ordner (`diffusion_models`, `vae`, …) sind `strict` — eine Datei, die kein
  Muster trifft, füllt sie nicht aus.
- **Jede Datei mit fester Revision und SHA-256**: `_FETCH_FILE` lädt im Python
  von ComfyUI in den Zwischenordner, prüft die Summe gestreamt und wechselt
  erst die geprüfte Datei am Ziel ein. Eine Datei unter unserem Namen zählt
  nur in voller Größe.
- **Die Fassung zuerst**: `check_version` liest `comfyui_version.py` (nie
  ausgeführt) und hält vor jedem Download an, wenn sie unter
  `mesh.MINIMUM_COMFYUI` liegt. Ohne Versionsdatei (ComfyUI Desktop) nennt
  der laufende Server fehlende Knoten (`missing_nodes`, `Readiness.NO_NODES`).
- **`RemeshMesh` im Modus `udf`, beide Verwurfschalter aus**, davor
  `FillHoles`: Das Rohnetz von TRELLIS.2 hat keinen einheitlichen
  Umlaufsinn, `udf` legt um jede Fläche eine nach innen gewendete zweite
  Hülle. An einer dünnen Wand sind beide zusammen die Wand; die Innenhülle
  eines vollen Körpers nimmt Solidons Reparatur mit `repair(inner_shells=True)`
  (`generate.GENERATED_REPAIR`). Begründung im Docstring von `mesh.py`. Nach
  `DecimateMesh` füllt ein zweites `FillHoles` die kleinen Vierecklöcher, die
  das Ausdünnen offen lässt.
- **Platz, Karte und Dauer stehen vor dem Laden da** (RM-564,
  `needs.generator_needs`): die gewählten Dateien plus `HEADROOM_GIGABYTES`
  gegen `free_gigabytes`, die Karte gegen `MEASURED_GRAPHICS_GB`, die
  gemessene Dauer (`FIRST_*_SECONDS`, `WARM_SECONDS_*`, RTX 4080); auf
  Apple Silicon als gerechnet bzw. nicht gemessen.

## Grenzen

- **Abschaltbar heißt abschaltbar**: Fehlt das Backend, verschwindet die
  Fähigkeit, nicht die Anwendung.
- **Kein fremder Quelltext wird ausgeführt** (Regel 11), auch nicht der eines
  Sprachmodells.
- Ein Schlüssel gehört dem Nutzer und reist nie in einer Projektdatei mit.
