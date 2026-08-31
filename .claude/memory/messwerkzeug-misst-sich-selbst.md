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
| Korpuslauf über 14 Dateien | Lücke | enthielt keinen Torus; der fünfte Tabelleneintrag wurde geraten und war falsch |
| vier `assert x not in text` | wirkungslos | prüften auf dem gestrippten Text, wo die verbotenen Tags längst weg waren |
| `QFont(name, 10)` gegen `font-size="10"` | falsche Einheit | zehn **Punkt** statt zehn Pixel — bei 96 dpi ein Drittel breiter |
| `QFontMetrics` unter `offscreen` | keine Schrift | Qt meldet dort **null** Familien; die Ersatzschrift misst glatte 10 px je Zeichen |

**Drei Arten, und alle drei sehen aus wie ein Ergebnis: zu weit, zu eng, gar
nicht.** Am 23.08.2026 an einem Abend alle drei — ein Regex, der jede Zeile traf
(78 Treffer bei 78 Zeilen), einer, der die gesuchte Stelle knapp verfehlte, und
vier Verbote, die überhaupt nichts trafen. Die dritte ist die gefährlichste,
weil nur sie **schweigt**.

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
6. **Wo die Messung nicht hinreicht, hört die Tabelle nicht auf.** Am
   23.08.2026 belegte ein Lauf über vierzehn Korpusdateien vier von fünf
   Einträgen einer Zuordnungstabelle. Der fünfte kam aus dem Kopf, weil kein
   Torus im Korpus lag — und war doppelt falsch, Name und Faktor. **Vier
   gemessene und ein geratener Eintrag sehen beim Lesen gleich aus.** Wer eine
   Messung erweitern müsste, erweitert sie; wer stattdessen ergänzt, markiert
   die Zeile wenigstens. Gefunden hat es eine andere Sitzung beim Nachmessen,
   nicht ein Test: Der Eintrag lief ins `continue`, und weil die Schätzung
   daneben ohnehin auf 0,4 % traf, **sah ein stummer Eintrag aus wie ein
   wirksamer**. Ein Test gegen die *Verbindung* (trägt das Merkmal den
   Parameter, den die Tabelle sucht?) fängt das, ein Test gegen das *Ergebnis*
   nicht.
7. **Eine Negativprüfung ohne ihr Fehlerbild ist eine Behauptung.** Am
   23.08.2026 habe ich vier Verbote geschrieben (`<em>`, `\*`, `\<`,
   `&lt;em&gt;`) und sie auf einem Text geprüft, aus dem die Tags vorher
   entfernt worden waren. **Alle vier liefen ins Leere.** Meine eigene
   Gegenprobe hatte es sogar ausgegeben — `Reste: —`, auch am kaputten Text —
   und ich las es als „keine Reste" statt als „greift nicht". Ein `not in`, das
   am echten Fehlerbild nicht anschlägt, ist von einem wirksamen nicht zu
   unterscheiden: **Beide sind grün.** Ein Positivtest schlägt fehl, wenn er
   nichts findet; ein Negativtest schweigt. Deshalb gehört die Gegenprobe in
   den Test selbst — Fehlerbild nachstellen, prüfen, dass das eigene Verbot
   daran anschlägt.
8. **Wer Textbreiten misst, prüft zuerst, welche Schrift antwortet.** Am
   31.08.2026 zweimal hintereinander an derselben Frage — passt die
   Ebenenzeile des Skizzen-Schemas in allen sechs Sprachen? Die erste Sonde
   nahm `QFont("Segoe UI", 10)`: Das sind zehn **Punkt**, das `font-size="10"`
   des SVG sind Pixel, bei 96 dpi ein Drittel Unterschied. Die zweite lief
   unter `QT_QPA_PLATFORM=offscreen`, und dort meldet Qt **null**
   Schriftfamilien — `QFontInfo(f).family()` gibt `''`, `exactMatch()` ist
   `False`, und die Ersatzschrift misst glatte zehn Pixel je Zeichen. **Beide
   Fassungen meldeten sechs Sprachen als überlaufend, auch Deutsch, wo das
   bestehende Bild nachweislich passt** — und die glatten Zahlen (130 = 13
   Zeichen, 250 = 25) waren das Erkennungszeichen, das ich zweimal übersah.
   Zwei Zeilen genügen: `QFontDatabase.families()` abfragen und bei null
   abbrechen, und `setPixelSize` statt der Punktgröße. Das gilt für jede
   Messung an Schriftmetrik — mit ausdrücklich gesetzter Familie auch, denn
   die Familie zu *setzen* heißt nicht, sie zu *bekommen*.
9. **Fällt eine Messung aus, miss den Nullpunkt, bevor du eine Grenze
   glaubst.** Am 31.08.2026 brach eine Ollama-Anfrage mit allen 106
   Werkzeugen (117 KB) nach 882 Sekunden mit HTTP 500 ab, und die Erklärung
   lag bereit: Die Werkzeugliste ist seit dem 30.08. um zehn gewachsen, sie
   muss über eine Grenze gestoßen sein. Sie war plausibel, sie hatte ein
   Datum, und sie war falsch. Der Beweis kostete einen Lauf: **null
   Werkzeuge, zwei Zeichen Schema — Abbruch nach 312 Sekunden.** Wo die
   kleinste denkbare Anfrage scheitert, kann die Größe nicht die Ursache
   sein; der Dienst hing, und ein Neustart behob es.

   Dasselbe Muster gilt für jede Messung an einer Gegenstelle: Der Nullpunkt
   sagt, ob man die eigene Nutzlast misst oder den Zustand des anderen. Er
   ist billiger als jede Bisektion und beantwortet die Frage, die vor ihr
   steht. Zwei Zeichen, die neben `api/ps` gelesen werden — kein geladenes
   Modell, während angeblich eine Anfrage läuft —, sind mehr wert als fünf
   Messpunkte über eine Achse, die gar nicht die richtige ist.
10. **Eine elegante Erklärung ist die gefährlichste.** Zu demselben Fehlbefund
   bot eine andere Sitzung eine Ursache an, die auf jede Beobachtung passte
   (`website/dl/` ist ignoriert, ein Arbeitsbaum bekommt es nicht) — und sie
   erklärte sogar, warum ausgerechnet *eine* Datei fehlt. Das war Zufall. Wer
   eine Ursache **findet**, statt sie zu **messen**, hört an der Stelle auf zu
   suchen, an der die Geschichte aufgeht.

Die Gegenprobe kostet zwei Minuten und hat in dieser Nacht viermal eine falsche
Meldung verhindert und zweimal nicht, weil ich sie nicht gemacht hatte. Siehe
auch [[fremde-zwischenstaende-verfaelschen-messungen]] und
[[leistungstests-fremdlast]].
