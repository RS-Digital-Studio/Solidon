---
name: datei-ohne-manifest-hat-keinen-pruefer
description: "Die AppImage steht in keiner version.json — jede Prüfung, die übers Manifest geht, überspringt sie stumm."
metadata: 
  node_type: memory
  type: project
  originSessionId: e44e7ebf-a72f-4543-a02a-0efbcc35b48d
  modified: 2026-09-03T03:30:38.795Z
---

Beim Release 0.3.0 am 03.09.2026 geprüft: Vier Pakete stehen in
`version.json`, **fünf** stehen im Download-Kasten. Die AppImage (381 MB) ist
die fünfte, und sie steht dort mit Absicht nicht — `updates.py` bietet sie
nicht als Update an.

Die Folge hat mit dieser Absicht nichts zu tun: **Jede Prüfung, die über das
Manifest iteriert, überspringt sie.** Die Prüfsummenprüfung des Uploads, mein
Kettenabgleich CI → `version.json` → Server, die Größenprüfung — alle fragen
`for eintrag in packages`. Die Server-Nachprüfung erreicht sie nur über die
Seitenlinks und fragt dort das Schwächste, was man fragen kann: „antwortet sie
mit mehr als null Bytes".

Von Hand nachgemessen war sie in Ordnung: Größe identisch, **erstes und
letztes Megabyte bitgleich** mit dem gebauten Artefakt. Das letzte ist der
Punkt — ein abgebrochener Upload fehlt am Ende, und genau dort sieht niemand
hin ([[website-upload-grosse-dateien]]: ein halbes Paket sieht ganz aus).

**Why:** Ein Manifest ist eine Liste dessen, was jemand *aufgeschrieben* hat,
und wird beim Prüfen zur Liste dessen, was *existiert*. Die Lücke dazwischen
ist unsichtbar, weil kein Prüfer über sie berichtet — er zählt ja nur, was er
gefunden hat ([[suche-prueft-ihre-eigene-trefferzahl]]).

**How to apply:** Vor einer Auslieferung die **verteilte** Menge gegen die
**geprüfte** Menge halten: was liegt in `website/dl/`, was verlinken die
Seiten, was steht im Manifest? Wo die Zahlen auseinandergehen, steht eine
Datei ohne Prüfer. Dauerhaft wäre der Griff, `promised_files()` auch die
Seitenlinks lesen zu lassen — dann verschwindet die Sonderbehandlung.
