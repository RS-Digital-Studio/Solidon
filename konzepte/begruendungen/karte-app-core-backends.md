# Begründungen zu `app/core/backends/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, Datenfluss
> und Stolperfallen verdichtet wurde. Die Karte steht dort; hier stehen die
> ausführlichen Fassungen, das Warum und die Anlässe ihres Tages — wörtlich,
> gegliedert nach den Überschriften der Karte. *Früher unter …* nennt die Stelle
> der alten Karte.

## Die Karte

*Früher unter „Die Karte“.*

| Datei | Rolle |
|---|---|
| `llm.py` | Das Sprachmodell hinter dem Agenten — gehostet oder lokal (Ollama) |
| `mesh.py` | Mesh-Erzeugung für Weg 3, lokal oder gehostet (Säule B) |
| `resources.py` | Gemeinsame Schwerlastspur für lokale KI auf derselben Grafikkarte |
| `keys.py` | Wo der eigene Schlüssel des Nutzers liegt |
| `comfy_setup.py` | Ein fremdes ComfyUI für Weg 3 einrichten (§36): Knoten, TripoSG-Quelltext, Pakete, die Gewichte — und seit dem 21.09.2026 auf Wunsch das Bildmodell für den Weg aus Text (`fetch_image_model`, feste Revision, Prüfsumme, eigenes Häkchen im Dialog) |
| `data/comfyui/` | Die Knoten dazu (TripoSG; Lizenzkette offen, RM-003) |

*Früher unter „Das Skript-Modell der Suite liegt nicht mehr hier“.*

`tests/scripted_backend.py` ist ein Modell mit vorgeschriebenen Antworten —
und seit dem 22.09.2026 auch der Generator der Suite (`ScriptedMeshBackend`),
der bis dahin in `mesh.py` im Kundenpaket lag.
Damit sind Sitzungsverlauf, Werkzeugaufrufe und Transaktionskopplung prüfbar,
ohne ein echtes Modell zu fragen (§35, §40). Bis zum 02.09.2026 lag es hier
als `scripted.py` und reiste damit im Kundenpaket mit, obwohl keine
Anwendungsdatei es je importierte — `app/CLAUDE.md`: „Nichts hier ist ein
Hilfsprogramm." Wer ein Backend für einen Test braucht, holt es aus `tests/`;
die echte Messung ist die Agenten-Suite und etwas anderes.

## Das lokale Modell

*Früher unter „Eine Falle beim lokalen Modell“.*

**Ob gekürzt wurde, entscheidet die Länge der Anfrage, nicht die
Werkzeugzahl** (`prompt_was_cut`). Seit dem Werkzeugangebot sagt die Zahl der
Werkzeuge nichts mehr über die Größe; `request_length` misst den gesendeten
Text, `least_tokens` und `most_tokens` spannen mit `LEAST_CHARS_PER_TOKEN`
und `MOST_CHARS_PER_TOKEN` den Bereich auf, den ein Tokenizer daraus zählen
kann. Gekürzt ist eine Antwort, die weniger zählt, als der Text mindestens
hat, oder die genau Ollamas Kürzungszahl meldet (halbes Fenster plus
`TRUNCATION_KEEPS`) bei einer Anfrage, die größer sein kann als das Fenster.
Die obere Schranke ist mit Absicht weit: gpt-oss packt 7,5 Zeichen in einen
Token. `tools/measure_local_model.py` fragt dieselbe Funktion.

`PROMPT_TOKENS` und `PROMPT_TOOL_COUNT` gehören zu derselben gezählten Anfrage.
Nach einer Änderung am Werkzeugsatz zählt
`tools/measure_local_model.py --count-tokens` den kompakten Systemprompt mit
dem Werkzeugangebot zur festen Frage „Hallo.“ genau einmal — die Grundlast
eines lokalen Zugs: alle Werkzeuge, keine Operation ausführlich
(`measure_local_model.base_tools`, dieselbe Rechnung wie die Sitzung).
Dieser funktionale Weg verwendet die konfigurierte Modell- und Kontextvorgabe,
fordert höchstens einen Antworttoken an und gibt den Modellspeicher zurück.
Er misst keine Geschwindigkeit und benötigt keinen Release-Lauf.

Die JSON-Auskunft hält Modell, Kontextfenster, Werkzeugzahl, Eingabe- und
Ausgabetoken sowie den SHA-256 der gesendeten Anfrage fest. Fehlende Zähler,
eine unvollständige Antwort oder erkennbare Kontextkürzung ergeben keinen
neuen Referenzwert. Erst die belegte Zählung erlaubt das Nachziehen beider
Konstanten; Zeichenzahl und Hochrechnung ersetzen sie nicht.

## Lokale KI teilt eine Grafikkarte

*Früher unter „Lokale KI teilt eine Grafikkarte“.*

Ollama und ComfyUI laufen auf demselben Rechner nie gleichzeitig durch
Solidon. `resources.local_ai_slot()` serialisiert nur Loopback-Adressen;
entfernte, möglicherweise geteilte Server bleiben unberührt. Das
Warten auf die Spur meldet genau einmal den Grund, bleibt abbrechbar und
endet spätestens nach zehn Minuten mit einem erneuten Versuch als Vorschlag.
Eine abgewiesene Chat-Freigabe betritt die Spur nicht und entlädt kein Modell.
**Nach dem Zug bleibt das Ollama-Modell geladen, bis ein anderer die Karte
braucht:** `resource_session` trägt es mit `resources.keep_warm(holder,
release)` ein (auf dem Prozessor entlädt es sofort), und `local_ai_slot(...,
holder=...)` gibt beim Betreten jedes warm gehaltene Modell frei außer dem
eigenen. Ein ComfyUI-Lauf nennt keinen Halter und räumt damit die Karte ganz;
ein zweiter Chat-Zug desselben Modells lädt nicht neu. Die Werkzeugprobe und
die Geschwindigkeitsmessung tragen ihr Modell ebenso ein (`_stays_warm`),
sonst hielte es seine drei Minuten `OLLAMA_KEEP_ALIVE` gegen einen Lauf, der
davon nichts weiß. Die Suite leert die Liste je Test (`tests/conftest.py`).
**Und das Beenden der Anwendung gibt frei** (`release_warm_before_exit`, an
`aboutToQuit` in `app/ui/app.py`): Danach betritt niemand mehr die Spur, und
das Modell blieb sonst drei Minuten auf der Karte. In einem Faden mit fünf
Sekunden Frist — ein hängender Dienst hält das Schließen nicht auf.
ComfyUI erhält beim Abbruch ausschließlich Solidons eigene
Auftrags-ID über `POST /api/jobs/{job_id}/cancel`. Der Endpunkt prüft und
unterbricht atomar; `cancelled: false` bestätigt einen bereits beendeten oder
unbekannten Auftrag. Ohne diese bestätigte Fähigkeit wird nur der eigene
Warteschlangeneintrag über `/queue` entfernt. Ein älterer Server kann einen
bereits laufenden Auftrag zu Ende rechnen, während Solidon sein Warten und
seine lokale KI-Sperre beendet. `/interrupt` wird nie aufgerufen: Eine
vorherige Warteschlangenabfrage verhindert den Wechsel zum nächsten Auftrag
nicht. Nach jedem Auftrag wird weiterhin der lokale Modellcache freigegeben.
