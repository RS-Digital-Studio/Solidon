---
name: ollama-werkzeugaufrufe-modellwahl
description: Lokale Modelle vor der Fehlersuche auf wants_tools prüfen — Parameterzahl und gemeldete Fähigkeit sagen nichts darüber.
metadata: 
  node_type: memory
  type: project
  originSessionId: 493de4ef-2355-4029-9d86-1e68996c4909
  modified: 2026-08-31T18:00:00.000Z
---

## Ergebnis vom 31.08.2026 — die aktuelle Kundenlage

Auf der RTX 4080 mit 16 GB, Ollama 0.33.2 und `qwen3:14b` wurde der
**vollständige** aktuelle Satz aus 106 Werkzeugen (rund 156 KB Schema) neu
gefahren. Fünf von fünf vollständigen Anweisungen riefen das richtige Werkzeug
auf. Die einzelnen Züge brauchten 17,0 / 17,4 / 11,8 / 25,2 / 13,6 Sekunden,
Median 17 Sekunden; das Modell lag vollständig im Grafikspeicher.

Die unabhängige Wiederholung desselben Laufs am Abend blieb bei **5/5**:
16,5 / 25,8 / 11,2 / 21,6 / 12,8 Sekunden, Median 16,5 Sekunden, erneut
**100 % im Grafikspeicher**.

Der vollständige Prompt umfasste 19 641 Token. Sein kaltes Einlesen brauchte
13,1 Sekunden (1 504 Token/s), warm lag der Median bei 2,3 Sekunden. Die früher
genannten 7,8 Token/s und rund 42 Minuten beschreiben ausschließlich einen
**CPU-Rückfall**, bei dem Ollama die Grafikkarte nicht nutzte. Sie sind keine
GPU-Leistung und kein allgemeiner Ollama-Wert.

Die 16 GB sind die Ausstattung des gemessenen Rechners, keine abgeleitete
Mindestanforderung. Ob ein anderer Rechner das Modell vollständig auf seiner
Grafikkarte hält und Werkzeuge korrekt aufruft, beantwortet nur die eingebaute
Probe auf diesem Rechner. Die historischen Tabellen darunter erklären die
Fehlerentwicklung; für eine aktuelle Empfehlung gilt dieser Abschnitt.

> **Achtung (26.08.2026): Jede Messtabelle in dieser Notiz außer der
> Fenster-Tabelle im Nachtrag vom 08.08 wurde OHNE `num_ctx` gemessen — also
> gegen ein stilles 4096-Token-Fenster, das den Systemprompt kappte. Sie sind
> Vorgeschichte, kein Ergebnis; wer eine Zahl daraus zieht, zieht eine
> Trunkierung, nicht die Fähigkeit eines Modells. Eine neue Reihe mit gesetztem
> `num_ctx` erhebt 3d-druck-ce gerade (der Widerspruch „voller Satz 16386,
> kompakter 22300" war genau dieselbe Trunkierung: 16386 = 32768/2 + 2). Die
> Tabellen unten werden ersetzt, sobald ces Reihe steht — bis dahin nicht als
> Modellvergleich lesen.**

Formwerks `DEFAULT_OLLAMA_MODEL` war `qwen2.5-coder:14b`. Gemessen am
07.08.2026 gegen Ollama 0.32.6 **funktionierte es für den Agenten nicht**: Das
Modell gibt Werkzeugaufrufe als rohes JSON im Textinhalt aus, ohne die
`<tool_call>`-Tags, die sein eigenes Ollama-Template verlangt. Ollama kann sie
darum nicht parsen, `Reply.wants_tools` bleibt `False`, und der Agent sieht nur
Prosa. Seit „Das empfohlene Modell schrieb seine Aufrufe hin" (bb28c8b) ist die
Vorgabe `llama3.1:8b`.

**Entscheidend ist die Zahl der angebotenen Werkzeuge.** `tool_schemas()`
liefert **7**, solange `load_operations()` nicht lief, und **83** danach (rund
96 KB Schema) — und der Agent ist immer im zweiten Fall. Wer mit sieben misst,
misst eine Lage, die es nicht gibt. Genau daran ist die erste Modellwahl
gescheitert:

| Modell | 7 Werkzeuge | 83 Werkzeuge |
|---|---|---|
| `qwen3:14b` | 4/5 | **4/5** — seit 6540a2e die Vorgabe |
| `llama3.1:8b` | 5/5 | **2/5** |
| `mistral-nemo` | 2/5 | — |
| `qwen2.5-coder:14b` | 0/5 | 0/5 |

`llama3.1:8b` kennt die richtige Antwort auch unter voller Last — es schreibt
sie als Fließtext hin (`{"name": "translate_object", ...}`), statt sie
aufzurufen.

## Nachtrag 08.08.2026: Es war das Kontextfenster, und das entwertet alles unten

**Ollama öffnet ohne `num_ctx` 4096 Token und schneidet den Rest ab — still.**
Die 84 Werkzeugschemata sind allein 21 162 Token. Was nicht hineinpasst, fällt
weg, und mit ihm der Systemprompt samt der vier Vorrangregeln. Das Modell ist
dann nicht ungehorsam; es hat den Auftrag nie gesehen.

`prompt_eval_count` in Ollamas Antwort verrät es: liegt es bei etwa der Hälfte
des Fensters statt bei der echten Promptgröße, wurde gekürzt.

| Fenster | verarbeitet | je Frage | Baustein getroffen |
|---|---|---|---|
| 4096 (Vorgabe) | 2 050 | 30,1 s | 0 von 3 |
| 8 192 | 4 098 | 34,1 s | 0 von 3 |
| 16 384 | 8 194 | 36,1 s | 0 von 3 |
| **32 768** | **21 162** | **21,2 s** | **3 von 3** |

Seit „Der Agent hatte den Auftrag nie gesehen" (a5da6a2) setzt
`OLLAMA_CONTEXT_TOKENS = 32768`. Der damalige Lauf belegte auf diesem Rechner
rund 14 GB statt 9,3. Daraus folgt keine allgemeine Mindestanforderung; die
aktuelle Messung und ihre Grenze stehen oben.

**Damit sind die Messreihen darunter Vorgeschichte.** Die Werkzeugmengen-Tabelle
misst nicht, wie ein Modell mit vielen Werkzeugen umgeht, sondern ab wann sie
nicht mehr ins Fenster passen. Und der Modellvergleich verglich zwei Modelle,
von denen keines den Systemprompt ganz bekam — bevor daraus eine Anschaffung
wird, gehört er wiederholt. `TIMEOUT_SECONDS` für gehostete Modelle bleibt bei
120, der getrennte lokale `LOCAL_TIMEOUT_SECONDS` bei 600. Die gemessene
CPU-Rückfallphase von rund 42 Minuten würde diesen noch synchronen Transport
nie abschließen und ließe sich während des Wartens nicht zuverlässig abbrechen.
Die Probe führt deshalb zu GPU oder gehostetem Zugang; eine längere Grenze darf
erst mit einem wirklich abbrechbaren Transport kommen.

---

**Die Menge entscheidet auch, ob die Vorrangregeln tragen** — so stand es hier,
und der Nachtrag oben sagt, warum es die falsche Erklärung war. Derselbe Fall,
dasselbe Modell (`qwen3:14b`), verschieden große Angebote:

| Angebot | wall_holder | magnet_lid | spacer |
|---|---|---|---|
| 10 | `find_part` | `find_part` | `find_part` |
| 25 | `create_box` … | `create_from_scad` | `create_brep_cylinder` ×4 |
| 83 | `sketch_sweep` … | Prosa | Prosa |

**Die Grenze schien der Grafikspeicher zu sein.** `qwen3:30b-a3b` traf mit
allen 83 Werkzeugen 5/5, belegt aber 19 GB bei 16 auf der Karte; die volle
Suite endete bei 4/33 mit 17 Zeitüberschreitungen.

| Modell | Werkzeugtest | Suite |
|---|---|---|
| `qwen3:14b` (Vorgabe, 9,3 GB) | 4/5 | **8/33** |
| `qwen3:30b-a3b` (19 GB) | **5/5** | 4/33 |

**Warum das wichtig ist:** Formwerks Übersetzung nach Ollama ist korrekt — der
rohe `POST /api/chat` mit handgeschriebenem Schema verhält sich identisch. Der
Fehler liegt allein in der Modellwahl. Wer den Agenten lokal testet und nur
Prosa sieht, sucht sonst im eigenen Code.

**Wie anwenden:** Bevor an der Agentenschicht mit einem lokalen Modell gesucht
wird, `tools/check_local_model.py <modell>` fahren. Die Größenwarnung
`ollama_size_warning` deckt das **nicht** ab — sie misst nur Parameterzahl, und
14,8 B liegt weit über der 7-B-Grenze. Auch die von Ollama gemeldete Fähigkeit
`tools` sagt nichts: qwen2.5-coder meldet sie und kann es trotzdem nicht. Nur
ein echter Zug beantwortet die Frage, und den macht `llm.ollama_tool_check`.

**Und `load_operations()` nicht vergessen.** Jedes Werkzeug außerhalb von
Anwendung und CLI muss es selbst aufrufen — `tools/run_agent_suite.py` lief
ohne den Aufruf überhaupt nicht, `check_local_model.py` maß daneben. Ein leeres
Register fällt nicht auf: es wirft keinen Fehler, es liefert nur weniger.

Siehe [[comfyui-installation-d-ai]] für die andere Hälfte derselben Durchsicht.
