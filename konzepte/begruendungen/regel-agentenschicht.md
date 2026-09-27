# Begründungen zu `.claude/rules/agentenschicht.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

## Die drei Vorrangregeln

> **Es waren vier, und die zweite hieß „Op-Liste vor OpenSCAD".** Sie ist am
> 26.08.2026 mit dem OpenSCAD-Ausbau entfallen — nicht gelockert, sondern
> gegenstandslos: Der Quelltextweg, vor dem sie warnte, existiert nicht mehr.
> Was sie inhaltlich schützte, sagt „Bausteine vor Primitiven" ohnehin. Eine
> Regel, die ein Modell vor etwas warnt, das es gar nicht tun kann, kostet
> Platz im Auftrag und lehrt eine Unterscheidung ohne Gegenstand
> (`PROMPT_VERSION = "4"`, Regelsammlung Version 3).

Warum „Fragen vor Raten" als Vorbedingung steht (die aktuelle Zahl der
Operationen führt die Regel selbst, ein Test hält sie):

> **„Fragen vor Raten" trägt nur als Vorbedingung, nicht als Gewohnheit.** Als
> vierter Punkt einer Liste war sie anleitend, und das hielt gegen die damals
> 84 Werkzeuge nicht […]: sobald der Systemprompt vollständig ankam, fiel die
> Quote von 3/3 auf 1/3 — wer genug Angebote hat, findet immer eines, das
> plausibel aussieht. Prompt-Version 2 stellt deshalb drei Prüfungen *vor* den
> ersten Werkzeugaufruf, jede einzeln hinreichend für eine Rückfrage: Ziel
> eindeutig, Maß genannt, Bezug vorhanden. Dazu der Satz, der das
> Herumprobieren abstellt („und sonst nichts") — ein Fall hatte zwanzig
> Aufrufe hintereinander abgesetzt.

## Kontext

Der Menüort in den Werkzeugbeschreibungen kam mit Prompt-Version 3; die 39
Referenzanfragen der Suite gibt es seit der Agent-Vertiefung.

## Das Kontextfenster ist die Bedingung, nicht die Feineinstellung

> Sein Vorgabefenster ist 4096 Token; allein die 85 Werkzeugschemata aus dem
> Register sind rund 109 000 Zeichen, gemessen 24 474 Token. Was nicht
> hineinpasst, fällt weg — und mit ihm der Systemprompt samt der
> Vorrangregeln. Das Modell ist dann nicht ungehorsam, es hat den Auftrag nie
> gesehen.
>
> Genau das war der Befund „der Agent greift nicht zu den Bausteinen (0/13)".
> Gemessen mit `qwen3:14b` an drei Anfragen, für die ein Baustein die richtige
> Antwort ist: 0 von 3 bei 4096, 8192 und 16384 (jedes Mal abgeschnitten), 3
> von 3 bei 32768 — und dabei **schneller** (21,2 s gegen 30–36 s je Frage),
> weil ein Modell, das den Auftrag kennt, nicht herumrät.

Die Zählung hinter der Schwelle „Grundlast unter einem Drittel des Fensters":

> Die Grundlast des Angebots wurde mit `qwen3:14b`, `num_ctx=32768` und
> `num_predict=1` vollständig mit **7 276 Token** gezählt (22,2 Prozent des
> Fensters); ein Zug mit ausführlichen Werkzeugen, Steckbrief und Verlauf kam
> in der Suite auf bis zu 14 215. […] Bis zum 23.09.2026 zählte der kompakte
> Auftrag aller Werkzeuge 27 293 Token bei 147 Werkzeugen (83,3 Prozent); die
> Chronik der Zählungen steht bei `PROMPT_TOKENS`.

Historische Vergleiche (sie belegen keine heutige Geschwindigkeit):

> Bei 85 Operationen nachgemessen, `qwen3:14b` gegen `num_ctx` 32768: 26 601
> Token für Systemprompt und alle 96 Werkzeuge, 19 249 für den kompakten Satz,
> den der Ollama-Pfad fährt — beide ganz angekommen. Das Fenster trägt also
> weiter. Gezählt ist die Luft trotzdem: über dem kompakten Satz bleiben rund
> 13 500 Token für Steckbrief, Verlauf und Antworten, und größer als 32768
> wird das Fenster nicht ohne Weiteres — bei diesem Wert belegt das Modell
> 14 GB und bleibt damit gerade noch auf einer 16-GB-Karte.

Die Fenstergröße und die Kürzungen der Kurzfassung:

> **Vom 16.09. bis zum 22.09.2026 stand das Fenster auf 40 960** (Entscheidung
> Robert): 143 Werkzeuge kosteten 36 731 Token, der Preis waren 11 statt 41
> Token je Sekunde. **Seit dem 22.09.2026 wieder 32 768** (RM-185): Die
> Kurzfassung zählt mit 147 Werkzeugen 27 293 Token statt 37 836. Drei
> Kürzungen, jede als Satz im kompakten Prompt (`prompt._COMPACT_FIELDS_HINT`,
> Prompt-Version 7):
>
> - **Rückseitenfelder** (`placement="advanced"`) behalten nur ihre Bedingung
>   (−5 755 Token). […]
> - **Die zehn Ortsfelder** fallen bei den `insert_*`-Bausteinen aus der
>   Kurzfassung (−2 905). […]
> - **Millimeter und Grad** stehen einmal im Prompt statt am Feld (−1 269);
>   eine andere Einheit bliebe am Feld (`tools.IMPLIED_UNITS`).
>
> Nicht übernommen, obwohl gemessen: die Zeile „Wann nicht" zu streichen
> (−2 123) — sie ist Inhalt.

Warum ausführliche Bausteine im Angebot ihre Ortsfelder wieder tragen: „ohne
sie setzte qwen3.5:9b Bausteine ohne Stelle."

> **Der Denkblock bleibt an.** `think: false` wurde am 23.09.2026 gemessen und
> zurückgenommen: dieselbe Basis mit qwen3:14b ohne Denkblock 14 statt 21 von
> 39, Baustein 2 statt 7 von 13 — der Zeitgewinn (24 min statt rund 3 h für
> die Suite) kostet die Treffer.

### Ein lokales Modell bekommt ein Angebot, nicht das ganze Register

Das Angebot kam mit Prompt-Version 8. Warum ohne die Kundenwörter der
Palette gesucht wird: „Mit ihnen fiel „Versteife die Wand mit einer Rippe"
von 3 von 3 auf 0 von 2 (qwen3:14b, Durchsicht 0.5.1, `grenzen.md`)".

> Gemessen am 25.09.2026 mit qwen3:14b: 30 461 Token für die Kurzfassung aller
> 153 Werkzeuge gegen **7 258** für die Grundlast des Angebots. **Und die
> Quote hält:** Am 26.09.2026 auf freier Karte, derselbe Code mit und ohne
> Angebot, qwen3:14b — mit Angebot bei 32 768 24 von 39, ohne 14 (neunmal riss
> das Fenster) und mit einem Fenster von 40 960 ebenfalls 24, aber in 149
> statt 44 Minuten und zu einem Zehntel auf dem Prozessor. Mit dem Zwilling
> als Kurzform 22 — im Rauschen: Zwei Läufe desselben Stands kippten bis zu
> sieben Fälle in jede Richtung.

### Nach dem Zug bleibt das Modell warm — bis ein anderer die Karte braucht

Die Lage mit zwei Modellen zugleich auf der Karte „ging dem Absturz vom
01.09.2026 voraus". Zur Obergrenze jeder lokalen Antwort: „gemma4:12b lief bei
der Werkzeugprobe in 14 400 Token ohne Ende."

## Eine Ablehnung muss sagen, was zu ändern ist

> Zwei Stellen haben das lange verschluckt, und beide sahen aus wie
> Fehlerbehandlung:
>
> - **Die Kette hält an, und der Grund bleibt im Bericht.** `checks.check`
>   meldete „Die Auswertung hält bei dieser Operation an" — der Satz, der
>   weiterhilft („Der gewählte Körper ist ein Netz"), stand daneben und ging
>   nicht mit. Gemessen an `pocket_plate`: viermal dieselbe Operation mit
>   anderen Zahlen, statt einmal den Körpertyp zu wechseln. Die Befunde der
>   anhaltenden Operation reisen jetzt mit.
> - **Die Fehlertexte des Kerns tragen keine Platzhalter** (§33.1). „Der Wert
>   liegt unter dem zulässigen Mindestwert" ist der ganze Satz; die Zahlen
>   stehen in `values`. Die Oberfläche setzt beides zusammen, die Antwort ans
>   Modell tat es nicht. **Der Feldname gehört ausdrücklich dazu** — ohne ihn
>   korrigierte das Modell dreimal die Tiefe, während `corners` die Grenze
>   riss.

## Sicherheit (§32)

> Hier stand die Prüfung, die OpenSCAD-Quelltext vor jedem Lauf durchsah
> (`import`, `include`, `use`, `surface` nur relativ). Sie ist seit dem
> 26.08.2026 gegenstandslos: Der einzige Weg, der fremden Code ausführte, ist
> ausgebaut. Damit wird aus einer Prüfung eine **Zusage** — eine Projektdatei
> kann nichts starten.

## Die Schnittstelle nach außen (MCP)

Die lesenden Rechnungen im Faden des Servers kamen mit RM-144. Warum jeder
Aufruf durch den Hauptthread geht: „Das Dokument gehört dem Fenster, und was
nebenher hineinschriebe, könnte weder Undo noch Prüfbericht erklären."
