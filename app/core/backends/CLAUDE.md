# `app/core/backends/` — was von außen kommt

LLM und Mesh-Erzeuger, jeweils hinter einer Schnittstelle (§27). **Beides
extern, beides abschaltbar** — ohne Netz, ohne Konto und ohne KI bleibt alles
außer dem Chat benutzbar.

Die Regeln stehen in `.claude/rules/agentenschicht.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `llm.py` | Das Sprachmodell hinter dem Agenten — gehostet oder lokal (Ollama) |
| `mesh.py` | Mesh-Erzeugung für Weg 3, lokal oder gehostet (Säule B) |
| `keys.py` | Wo der eigene Schlüssel des Nutzers liegt |
| `scripted.py` | Ein Modell, das sagt, was man ihm aufgetragen hat — **die Grundlage jedes Agententests** (§35, §40) |
| `comfy_setup.py` | Ein fremdes ComfyUI für Weg 3 einrichten (§36) |
| `data/comfyui/` | Die Knoten dazu (TripoSG, MIT) |

## Warum `comfy_setup.py` und `data/` im Kern liegen

Weil `tools/` im gebauten Paket **nicht mitreist**. Was der Nutzer aus der
laufenden Anwendung heraus einrichten können soll, muss hier stehen.

## TripoSG bleibt reproduzierbar

Quelltext und Gewichte tragen in `comfy_setup.py` jeweils einen vollständigen
Commit-Pin. Der Quelltext wird direkt von
`github.com/VAST-AI-Research/TripoSG` auf diesen Commit geholt und danach gegen
`HEAD` geprüft; `snapshot_download` erhält die feste Revision von
`huggingface.co/VAST-AI/TripoSG`, deren aufgelöster Stand ebenfalls geprüft
wird. Ein Wechsel zieht immer Pin, Setup und die beiden Reproduzierbarkeitstests
gemeinsam nach. LICENSE und NOTICE bleiben Teil der eingerichteten Knoten.

## `scripted.py` ist der Grund, warum Agententests ohne Geld laufen

Ein Modell mit vorgeschriebenen Antworten. Damit sind Sitzungsverlauf,
Werkzeugaufrufe und Transaktionskopplung prüfbar, ohne ein echtes Modell zu
fragen. Die echte Messung ist die Agenten-Suite und etwas anderes.

## Eine Falle beim lokalen Modell

**Ohne `num_ctx` schneidet Ollama den Prompt still ab.** Ein Modell, das die
Werkzeuge nicht aufruft, ist dann nicht zu dumm — es hat sie nie gesehen.
`tools/check_local_model.py` prüft genau das, bevor eine Modellmessung
etwas aussagt.

## Grenzen

- **Abschaltbar heißt abschaltbar.** Fehlt das Backend, verschwindet die
  Fähigkeit — nicht die Anwendung.
- **Kein fremder Quelltext wird ausgeführt** (Regel 11), auch nicht der eines
  Sprachmodells.
- Ein Schlüssel gehört dem Nutzer und reist nie in einer Projektdatei mit.
