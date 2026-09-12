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
entfernte, möglicherweise geteilte Server bleiben unberührt. Das
Warten auf die Spur meldet genau einmal den Grund, bleibt abbrechbar und
endet spätestens nach zehn Minuten mit einem erneuten Versuch als Vorschlag.
Eine abgewiesene Chat-Freigabe betritt die Spur nicht und entlädt kein Modell.
Ollama hält das Modell innerhalb eines vollständigen Agentenvorschlags warm und entlädt es im
`finally`. ComfyUI erhält beim Abbruch ausschließlich Solidons eigene
Auftrags-ID über `POST /api/jobs/{job_id}/cancel`. Der Endpunkt prüft und
unterbricht atomar; `cancelled: false` bestätigt einen bereits beendeten oder
unbekannten Auftrag. Ohne diese bestätigte Fähigkeit wird nur der eigene
Warteschlangeneintrag über `/queue` entfernt. Ein älterer Server kann einen
bereits laufenden Auftrag zu Ende rechnen, während Solidon sein Warten und
seine lokale KI-Sperre beendet. `/interrupt` wird nie aufgerufen: Eine
vorherige Warteschlangenabfrage verhindert den Wechsel zum nächsten Auftrag
nicht. Nach jedem Auftrag wird weiterhin der lokale Modellcache freigegeben.

Der Vertrag des atomaren Endpunkts steht in
[ComfyUIs server.py](https://github.com/Comfy-Org/ComfyUI/blob/master/server.py)
bei `_cancel_job_by_id` und `interrupt_if_running`.

## Grenzen

- **Abschaltbar heißt abschaltbar.** Fehlt das Backend, verschwindet die
  Fähigkeit — nicht die Anwendung.
- **Kein fremder Quelltext wird ausgeführt** (Regel 11), auch nicht der eines
  Sprachmodells.
- Ein Schlüssel gehört dem Nutzer und reist nie in einer Projektdatei mit.

## Gewichte werden vor der Freigabe geprüft

TripoSG-Download und Bestandsübernahme verwenden denselben Prüfer im Python
von ComfyUI. Der feste Modellstand und alle Größen müssen stimmen; für jede
LFS-Datei wird der von Hugging Face gelieferte SHA-256 gestreamt geprüft.
Beim Download geschieht das nach dem Kopieren, vor dem Austausch des alten
Bestands. Ohne gelieferten LFS-Hash bleibt die Größenprüfung.

Die Abschlussmarke mit Format 2 hält Größen, geprüfte Hashes und zugehörige
Änderungszeiten. `weights_present` prüft diese Marke und den aktuellen
Dateistand offline, ohne bei jeder Anzeige 7,5 GB erneut zu lesen. Eine alte
Größenmarke oder eine nachträglich geänderte Gewichtsdatei verlangt erneut die
Einrichtungsprüfung. Das ist keine Signatur der lokalen Ablage und schützt
nicht gegen jemanden, der Datei und Abschlussmarke gemeinsam manipuliert.
