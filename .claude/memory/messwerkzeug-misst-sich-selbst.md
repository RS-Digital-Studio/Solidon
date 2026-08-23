---
name: messwerkzeug-misst-sich-selbst
description: "Was ein Werkzeug meldet, ist eine Eigenschaft des Werkzeugs, bis man es an einem Fall geprüft hat, dessen Ausgang man kennt."
metadata:
  type: feedback
---

**Ein Werkzeugergebnis ist keine Eigenschaft des Gegenstands.** Am 23.08.2026 in
einer Nacht viermal zugeschnappt, bei drei verschiedenen Sitzungen, und jedes
Mal sah die Zahl aus wie ein Ergebnis:

| Werkzeug | Fehler | Was es wirklich maß |
|---|---|---|
| `grep -o "le plaque"` | zu weit | steckt in `seule plaque`, `nouvelle plaque` → 3 Treffer, richtig war 0 |
| `grep -oE "\ble plaque\b"` | zu eng | fand `un même plaque` nicht |
| `is_watertight` | falsche Frage | meldete „Loch", es waren 8 Dreiecke mit Fläche null; Euler-Zahl war 2 |
| doppelte Knotennummern | falsche Ebene | in OCCT verschieden — die Doppelung entstand erst durch `merge_vertices()` |
| eigene Regex über Testkörper | zu weit | zählte `range`, `ast`, `re` als „Grundmenge": 26 statt 16 |
| dieselbe Ausgabedatei für zwei Läufe | vermischt | Zusammenfassung eines abgebrochenen Laufs über dem neuen gelesen |
| `ls -la … | head -20` | abgeschnitten | 20 Dateien + 3 Kopfzeilen = 23; die letzten drei waren **alle** `Setup-*.exe`, weil `ls` alphabetisch sortiert |
| `ruff check app/ui/` | zu eng | `tests/` war nicht dabei, und dort lag die zu lange Zeile |

**Warum:** Jedes dieser Ergebnisse war *plausibel*. Ein Fehlbefund fühlt sich
nicht falsch an — er fühlt sich wie eine Messung an. Und weitergegeben wird er
**fester**, nicht lockerer: Jede Sitzung, die ihn übernimmt, streift eine
Unsicherheit ab, bis eine Zahl dasteht, die niemand mehr hinterfragt.
`3d-druck-33` hat meine unbelegte „siebzig" in einen eigenen Satz gehoben und
ihn danach zurückgezogen.

**How to apply:**

1. **Vor dem Melden an einem Fall prüfen, dessen Ausgang feststeht.** Für die
   Merkmalsarten hieß das: eine zehnte Art erfinden und sehen, dass der Test
   rot wird. Für eine Zählung: einen Treffer von Hand ansehen.
2. **Wer eine Zahl weitergibt, gibt das Muster mit.** Wer eine bekommt, prüft
   sie, bevor er sie in einen eigenen Satz hebt.
3. **Je Lauf ein eigener Dateiname.** Zwei Läufe in eine Datei zu schreiben
   erzeugt eine Zusammenfassung, die zu einem anderen Lauf gehört.
4. **Bei einer Prüfung fragen, ob sie die Frage beantwortet, die man hat.**
   `is_watertight` beantwortet „zählt jede Kante zwei Dreiecke?", nicht „hat
   der Körper ein Loch?" — dafür ist die Euler-Zahl da.
5. **Zählen, was man sieht, statt zu sehen, was man sucht.** Ich habe vier
   Download-Links geprüft, drei Dateien gesehen und „eine fehlt" geschlossen —
   statt zu fragen, warum die Liste nur siebzehn Zeilen hat. Die Zahl stand
   da. Eine abgeschnittene Ausgabe sieht vollständig aus: `head` sagt nicht,
   dass es abschneidet, anders als ein eingegrenzter Pfad, der wenigstens im
   Kommando steht.
6. **Eine elegante Erklärung ist die gefährlichste.** Zu demselben Fehlbefund
   bot eine andere Sitzung eine Ursache an, die auf jede Beobachtung passte
   (`website/dl/` ist ignoriert, ein Arbeitsbaum bekommt es nicht) — und sie
   erklärte sogar, warum ausgerechnet *eine* Datei fehlt. Das war Zufall. Wer
   eine Ursache **findet**, statt sie zu **messen**, hört an der Stelle auf zu
   suchen, an der die Geschichte aufgeht.

Die Gegenprobe kostet zwei Minuten und hat in dieser Nacht viermal eine falsche
Meldung verhindert und zweimal nicht, weil ich sie nicht gemacht hatte. Siehe
auch [[fremde-zwischenstaende-verfaelschen-messungen]] und
[[leistungstests-fremdlast]].
