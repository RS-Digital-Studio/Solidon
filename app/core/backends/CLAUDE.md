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
| `resources.py` | Gemeinsame Schwerlastspur für lokale KI auf derselben Grafikkarte |
| `keys.py` | Wo der eigene Schlüssel des Nutzers liegt |
| `comfy_setup.py` | Ein fremdes ComfyUI für Weg 3 einrichten (§36) |
| `data/comfyui/` | Die Knoten dazu (TripoSG, MIT) |

## Warum `comfy_setup.py` und `data/` im Kern liegen

Weil `tools/` im gebauten Paket **nicht mitreist**. Was der Nutzer aus der
laufenden Anwendung heraus einrichten können soll, muss hier stehen.

## Das Skript-Modell der Suite liegt nicht mehr hier

`tests/scripted_backend.py` ist ein Modell mit vorgeschriebenen Antworten.
Damit sind Sitzungsverlauf, Werkzeugaufrufe und Transaktionskopplung prüfbar,
ohne ein echtes Modell zu fragen (§35, §40). Bis zum 02.09.2026 lag es hier
als `scripted.py` und reiste damit im Kundenpaket mit, obwohl keine
Anwendungsdatei es je importierte — `app/CLAUDE.md`: „Nichts hier ist ein
Hilfsprogramm." Wer ein Backend für einen Test braucht, holt es aus `tests/`;
die echte Messung ist die Agenten-Suite und etwas anderes.

## Eine Falle beim lokalen Modell

**Ohne `num_ctx` schneidet Ollama den Prompt still ab.** Ein Modell, das die
Werkzeuge nicht aufruft, ist dann nicht zu dumm — es hat sie nie gesehen.
`tools/check_local_model.py` prüft genau das, bevor eine Modellmessung
etwas aussagt.

Der abbrechbare lokale HTTP-Transport hält den verbundenen Socket bis zum
Ende des Request-Threads fest. Auch bei HTTP/1.0 und `Connection: close`
erreicht ein Abbruch damit den Antwortkörper. Der Abbruch unterbricht den
Socket; Antwort und Verbindung schließt ihr Request-Thread, bevor der
Aufrufer zurückkehrt. Wird erst während eines Abbruchs eine Verbindung
hergestellt, verhindert die erneute Tokenprüfung das anschließende POST.

## Lokale KI teilt eine Grafikkarte

Ollama und ComfyUI laufen auf demselben Rechner nie gleichzeitig durch
Solidon. `resources.local_ai_slot()` serialisiert nur Loopback-Adressen;
entfernte, möglicherweise geteilte Server bleiben unberührt. Ollama hält das
Modell innerhalb eines vollständigen Agentenvorschlags warm und entlädt es im
`finally`. ComfyUI löscht oder unterbricht beim Abbruch nur Solidons eigene
Auftrags-ID und gibt seinen lokalen Modellcache nach jedem Auftrag frei.

## Grenzen

- **Abschaltbar heißt abschaltbar.** Fehlt das Backend, verschwindet die
  Fähigkeit — nicht die Anwendung.
- **Kein fremder Quelltext wird ausgeführt** (Regel 11), auch nicht der eines
  Sprachmodells.
- Ein Schlüssel gehört dem Nutzer und reist nie in einer Projektdatei mit.
