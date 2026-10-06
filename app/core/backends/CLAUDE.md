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
| `keys.py` | Wo der eigene Schlüssel des Nutzers liegt |
| `comfy_setup.py` | Ein fremdes ComfyUI für Weg 3 einrichten (§36): Knoten, TripoSG-Quelltext, Pakete, Gewichte — und auf Wunsch das Bildmodell für den Weg aus Text (`fetch_image_model`, feste Revision, Prüfsumme, eigenes Häkchen im Dialog) |
| `data/text_to_mesh.json`, `data/image_to_mesh.json` | Die ComfyUI-Abläufe der beiden Wege |
| `data/comfyui/` | Die Knoten dazu (TripoSG, MIT) — fremder Code mit eigener Karte |

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
  `Connection: close` den Antwortkörper, Antwort und Verbindung schließt der
  Request-Thread, bevor der Aufrufer zurückkehrt. Entsteht die Verbindung erst
  während eines Abbruchs, verhindert die erneute Tokenprüfung das POST.
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

## Gewichte werden vor der Freigabe geprüft

- TripoSG-Download und Bestandsübernahme nehmen denselben Prüfer im Python von
  ComfyUI: fester Modellstand, alle Größen, je LFS-Datei der gelieferte
  SHA-256 gestreamt — beim Download nach dem Kopieren, vor dem Austausch des
  alten Bestands; ohne LFS-Hash bleibt die Größenprüfung.
- Die Abschlussmarke (Format 2) hält Größen, Hashes und Änderungszeiten;
  `weights_present` prüft sie offline, ohne 7,5 GB neu zu lesen. Eine alte
  Marke oder eine geänderte Gewichtsdatei verlangt die Einrichtungsprüfung
  erneut. Keine Signatur: Wer Datei und Marke gemeinsam ändert, fällt nicht
  auf.
- ANTLR wird im ComfyUI-Python ohne verdeckte Bauabhängigkeit gebaut: erst
  `setuptools.build_meta` und `bdist_wheel` prüfen, nur wenn der Import fehlt
  den festen Setuptools-Wheel mit SHA-256 nachziehen; Abbruch und andere
  Fehler starten keine Installation.

## Grenzen

- **Abschaltbar heißt abschaltbar**: Fehlt das Backend, verschwindet die
  Fähigkeit, nicht die Anwendung.
- **Kein fremder Quelltext wird ausgeführt** (Regel 11), auch nicht der eines
  Sprachmodells.
- Ein Schlüssel gehört dem Nutzer und reist nie in einer Projektdatei mit.
