# Leserblick: Das geschriebene Handbuch aus Kundensicht

Anlass: Rückmeldung vom 27.09.2026 — ein Interessent aus einem Elektronikbetrieb
fand das Handbuch schwer zu lernen, das Umherprobieren im Programm nicht
zielführend. Dieser Bericht liest die dreißig geschriebenen Seiten aus
`app/core/manual.py` (`INTRODUCTION` und die `spacemouse-access`-Seite aus
`knowledge_pages()`) mit den Augen eines Kunden, der von einem Slicer kommt,
keine CAD-Kenntnisse hat und schnell ein Ergebnis will: ein Loch in ein
heruntergeladenes Modell, ein eigenes Gehäuse, ein druckfertiges Teil.

Die erzeugte Referenz aus dem Register gehört nicht zu diesem Auftrag.
Alle Wort- und Satzzahlen sind mit `tools`-freiem Python direkt aus
`manual.py` gezählt (siehe Kennzahlen-Tabelle unten); die Satzzählung ist eine
Näherung über Satzzeichen, keine linguistische Analyse — an den auffälligen
Werten (Seiten mit vielen Sätzen über 25 Wörtern) wurde stichprobenhaft im
Text nachgesehen, dass die Zahl nicht nur an Aufzählungspunkten hängt.

## 1. Seite für Seite

| Schlüssel | Titel | Wörter | Erste Stunde? | Hauptproblem | Empfehlung |
|---|---|---|---|---|---|
| what | Was Solidon ist | 178 | ja | knapp, in Ordnung | behalten |
| start | Die ersten fünfzehn Minuten | 580 | ja | acht Schritte in Fließtext statt als Bildfolge | als Bildanleitung |
| window | Das Fenster | 840 | ja | ein Bild für neun beschriebene Bereiche | als Bildanleitung |
| looking | Hinsehen, bevor gedruckt wird | 502 | später | sieben Analysekarten in Worten aufgezählt | kürzen + Bildanleitung |
| features | Was Solidon im Modell erkennt | 2087 | später (Kern später oft) | längste Seite, kein einziges Bild, Referenzcharakter | in „Erste Hilfe“ (kurz) und „Nachschlagen“ (lang) teilen |
| moving | Bewegen und Färben | 841 | ja (Bewegen), später (Färben) | Werkzeuggriffe nur beschrieben, kein Bild | als Bildanleitung, in zwei Seiten teilen |
| sketch | Zeichnen | 1442 | später | zweitlängste Seite, Tastenliste als Fließtext | als Referenzkarte + kurze Bildanleitung |
| ways | Die vier Wege | 211 | ja | guter Überblick, ein Bild | behalten |
| sculpting | Formen | 363 | nie (Nischen-Werkzeug) | ok für seine Zielgruppe | ans Ende |
| history | Der Verlauf | 384 | ja | ein Bild, sonst verständlich | behalten, kürzen |
| parameters | Parameter und Ausdrücke | 390 | später | Konzept vor dem ersten Bedarf erklärt | ans Ende / bei Bedarf verlinken |
| tolerances | Material, Toleranzen, Passungen | 292 | später | für Zielgruppe (Gehäuse/Halter) sehr relevant, aber erst spät platziert | nach vorne holen |
| parts | Die Bausteine | 777 | ja | zehn Bilder, gutes Vorbild für den Rest | behalten, als Vorlage nutzen |
| own-parts | Eigene Bausteine | 596 | nie | für Fortgeschrittene, ein Bild | ans Ende |
| exchange | Bausteindateien austauschen | 386 | nie | Lizenzdetails vor jedem Bedarf | ans Ende, kürzen |
| print | Drucken | 506 | ja | ein Bild, aber viele Slicer-Fälle in Worten | als Bildanleitung ergänzen |
| resin | Harz statt Filament: Resin-Drucker | 187 | ja (nur für Resin-Kunden) | ok | behalten |
| export | Auf das Bett und hinaus | 426 | ja | vier Bilder, gut bebildert | behalten |
| splitting | Wenn das Teil nicht auf das Bett passt | 565 | später | detailreich, ein Bild für vier Verbindungsarten | Bildanleitung je Verbindungsart |
| variants | Ausprobieren statt raten: Varianten und Kalibrieren | 214 | später | überschneidet sich mit tolerances | mit tolerances zusammenlegen |
| chat | Der Chat | 291 | später | enthält §-Verweis (§26.4), Entwicklerblick | kürzen, §-Verweis entfernen |
| generating | Ein Modell erzeugen lassen | 289 | nie (Nischenweg) | enthält §-Verweis (§2.2) | ans Ende, §-Verweis entfernen |
| extras | Zusätzliche Programme einrichten | 1042 | später | lange Technikseite, kein Bild, Modellnamen/Token-Zahlen | in drei Seiten teilen (Slicer/Ollama/ComfyUI), je mit Bild |
| surfaces | Oberflächen und Füllungen | 338 | später | zwei Bilder, ok | behalten |
| labels | Beschriften | 340 | später | kein Bild trotz visuellem Thema | Bildanleitung |
| remote | Fernsteuerung | 204 | nie | „MCP“, „Claude Code“ ungeklärt für Zielgruppe | ans Ende, Fachbegriff erklären oder weglassen |
| activation | Freischaltung | 285 | ja (beim Kauf) | verständlich, aber reiner Fließtext für einen Klickweg | Bildanleitung ergänzen |
| trouble | Wenn etwas nicht geht | 896 | ja | guter Grundgedanke, aber unstrukturierte Liste ohne Sprungmarken | als FAQ mit Suchfeld/Sprungmarken |
| glossary | Wörterbuch | 768 | später (zum Nachschlagen) | gut, aber sehr lang zum Scrollen | behalten, alphabetisch mit Sprungleiste |
| spacemouse-access | Wenn die 3D-Maus nicht reagiert | 229 | nie (nur bei Gerät) | technisch, für Zielgruppe ohne 3D-Maus irrelevant | ans Ende |

## 2. Konkrete Befunde mit Zitat

### Fachwörter ohne Erklärung an der Stelle, an der sie zuerst auftauchen

- „der Solver zieht nach, was daran hängt" (sketch) — *Solver* wird nirgends
  im Fließtext für Anfänger erklärt; das Wörterbuch (glossary) kennt den
  Begriff gar nicht. Ein Kunde ohne CAD-Erfahrung weiß nicht, was hier
  „nachzieht".
- „OpenCASCADE hält Flächen und Kanten einzeln bearbeitbar" (extras) —
  interner Rechenkern-Name in einer Anwenderliste; für einen Elektroniker
  ohne Zusatzwert, klingt nach Programmiererjargon.
- „über MCP, dieselbe Schnittstelle, mit der Claude Code und ähnliche
  Werkzeuge arbeiten" (remote) — *MCP* und *Claude Code* sind für die
  Zielgruppe (Gehäusebau) fachfremd; die Seite erklärt nicht, wofür das im
  Alltag gut ist.
- „Presspassung — Übermaß statt Spiel" (glossary) — der Begriff *Presspassung*
  wird nur im Wörterbuch definiert, kommt im Fließtext von `tolerances` aber
  nirgends vor; wer ihn dort in einer Meldung liest, muss zufällig auf das
  Wörterbuch stoßen.

### Entwicklerblick statt Kundenblick

- „An jeder Transaktion steht, woher sie kommt (§26.4): Modell, Version des
  Systemprompts, Version der Regelsammlung." (chat) — eine Bauplan-Paragraphen-
  nummer in einem Kundendialog ist kein Text für den Kunden, sondern eine
  interne Quellenangabe, die in der Handbuchseite blieb.
- „Der dritte Weg (§2.2): Sie beschreiben ein Teil …" (generating) — dieselbe
  Falle: eine §-Nummer aus dem Bauplan steht im Fließtext, den ein Kunde
  liest, der den Bauplan nie sieht.
- „Bis zur Fassung 0.3.5 standen die Handlungen zur Auswahl in einer eigenen
  Karte über der Ansicht und die Maße hier" (features) — eine Versionshistorie
  aus Sicht der Entwicklung, die einem Neukunden nichts über die heutige
  Bedienung sagt und nur verwirrt, wenn er nie eine Version 0.3.5 gesehen hat.
- „An einem echten Kundenmodell fielen damit 296 von 1130 Einträgen weg"
  (features) — eine interne Messzahl aus einem Testlauf, keine Aussage, die
  einem neuen Kunden hilft, seine eigene Aufgabe zu lösen.

### Sätze über 25 Wörter (Beispiele, mit Seitenschlüssel)

- extras: „Wenn Ollama die Grafikkarte nicht nutzt, rechnet es auf dem
  Prozessor, und das ist keine andere Geschwindigkeit, sondern eine andere
  Größenordnung — gemessen auf einem Rechner mit Intel-Arc-Grafik knapp acht
  Token je Sekunde beim Einlesen." (34 Wörter)
- sketch: „Die Linien im Hintergrund folgen dem Zoom: Sie stehen in der Folge
  1, 2, 5 und werden gröber, sobald sie dichter als zwanzig Bildpunkte lägen —
  ein Raster, dessen Linien ineinanderlaufen, hilft niemandem." (rund 33
  Wörter)
- moving: „Schieben Sie einen Körper am Griff über die Druckfläche hinaus,
  holt Solidon ihn auf eine freie Stelle zurück — um die übrigen Körper
  derselben Platte herum." (rund 27 Wörter)
- window: „Ganz rechts steht das Auswahlfenster, über die volle Höhe, sobald
  Sie etwas gewählt haben: oben die Maße dessen, was Sie angeklickt haben,
  darunter die Handlungen dazu." (rund 26 Wörter)

Insgesamt zählt die Näherung **127 Sätze über 25 Wörtern** im gesamten
Handbuch (siehe Kennzahlen-Tabelle), Schwerpunkt auf `sketch` (18),
`features` (14) und `moving` (13) — den drei Seiten, die auch inhaltlich am
dichtesten sind.

### Klickwege in Worten statt Bild mit Pfeil

Das ist der wichtigste Befund für die angekündigte Umstellung auf
Bildschirmfotos. Jede Zeile nennt das Bedienelement, auf das ein Pfeil zeigen
müsste.

| Seite | Zitat (gekürzt) | Bedienelement für den Pfeil |
|---|---|---|
| start | „Rechts steht, was mit dem Modell nicht stimmt." | Prüfbericht-Reiter rechts |
| start | „vorn *Bohrung setzen*" | erster Eintrag im Auswahlfenster |
| window | „Oben die Werkzeugleiste: Neu, Öffnen, Speichern, *Modell einfügen*, *Zeichnen* …" | obere Werkzeugleiste, jeder Knopf einzeln |
| window | „Unter dem Modell die Werkzeugzeile: *Schnitt*, *Messen*, *Bewegen* …" | Werkzeugzeile unter der Ansicht |
| window | „Links liegen Objekte, Parameter, Verlauf und Filamente untereinander" | linke Spalte, vier Abschnitte |
| window | „Ganz rechts steht das Auswahlfenster" | Auswahlfenster rechts |
| window | „Unten die Statusleiste" | Statusleiste |
| features | „findet seine Maße im Fenster *Auswahl*. Es steht ganz rechts und über die volle Höhe" | Auswahlfenster, Kopf- und Handlungsbereich |
| features | „Rechtsklick darauf im Fenster oder im Objektbaum, *Auf dieser Fläche zeichnen*" | Kontextmenü-Eintrag |
| moving | „Drei Knöpfe in der Leiste wählen, worum es geht — *Verschieben*, *Drehen*, *Skalieren*" | die drei Leistenknöpfe |
| moving | „Der Würfel skaliert gleichmäßig" | Skalier-Griff im 3D-Fenster |
| parts | „Fläche anklicken, Baustein wählen, Größe wählen" | Katalog-Knopf, Größenfeld |
| own-parts | „Der Weg beginnt im Bausteinkatalog (*Datei → Bausteinkatalog …*, Strg+K) … *Auswahl als Baustein speichern …*" | Menüpunkt und Katalog-Knopf |
| extras | „Die Liste steht unter *Hilfe → Zusätzliche Programme*." | Menüeintrag und Dialogliste |
| labels | „Beschriftet wird auf zwei Wegen … *Text aufbringen* … *Schriftzug als Körper*" | die zwei Menüeinträge unter Erzeugen |
| print | „Der Drucker steht oben im Dialog … Die Düse steht daneben" | Kopf des Druckdialogs |
| trouble | „Der Weg dahin ist *Hilfe → Rückmeldung senden*" | Menüeintrag und Dialog |
| activation | „Der Weg ist *Hilfe → Solidon freischalten …*" | Menüeintrag und Dialogfelder |

`features` und `moving` fallen besonders auf: Beide beschreiben ausführlich,
was rechts im Auswahlfenster passiert (2087 bzw. 841 Wörter), tragen aber
**kein einziges Bild** — genau die Seiten, die am meisten von einem
Bildschirmfoto mit Nummern und Pfeilen profitieren würden.

## 3. Reihenfolge und Lernweg

**So liest heute niemand freiwillig durch** — dreißig Seiten linear zu lesen,
bevor man sein erstes Loch bohrt, ist der Umherprobieren-Reflex, den der
Interessent beschrieb. Für die Zielgruppe (Slicer-Erfahrung, kein CAD, will
schnell ein Ergebnis) ist eine strikt zweistufige Ordnung sinnvoller als die
heutige Reihenfolge:

**Stufe 1 — die ersten fünfzehn Minuten (heute schon fast richtig):**
`what` → `start` → `window` (nur die drei Kernzonen: Werkzeugleiste,
Ansicht, Auswahlfenster) → `looking` (nur Prüfbericht, nicht alle sieben
Analysekarten) → `parts` (Bausteine sind der schnellste Weg zu einem
Ergebnis) → `tolerances` (heute erst Seite zwölf von dreißig, aber für ein
Gehäuse mit Deckel sofort relevant — Spiel und Passung entscheiden, ob der
Deckel passt).

**Stufe 2 — nach Bedarf, nicht der Reihe nach:** `sketch`, `moving`,
`features`, `export`, `print`, `splitting`, `surfaces`, `labels`. Diese
Seiten sollten über Suchbegriffe und Verlinkung aus der Oberfläche erreichbar
sein (Knopf → passende Handbuchstelle), nicht über fortlaufendes Blättern.

**Stufe 3 — Referenz zum Nachschlagen:** `glossary`, `parameters`,
`own-parts`, `exchange`, `extras`, `chat`, `generating`, `remote`,
`activation`, `spacemouse-access`, `variants`, `resin`, `sculpting`. Diese
Themen braucht niemand in der ersten Stunde.

**Was ganz fehlt** — konkrete Aufgaben, wie der Kunde sie formuliert, nicht
wie das Programm sie strukturiert:

- „Mein erstes eigenes Teil von Null" — heute verteilt über `sketch`
  (Zeichnen), `ways` (Weg 2) und `parameters`; kein Kapitel führt diese drei
  an einem durchgehenden Beispiel zusammen.
- „Ein Gehäuse mit Deckel bauen, der wirklich passt" — genau der Fall des
  Interessenten. Die nötigen Teile stehen verteilt in `tolerances` (Spiel),
  `parts` (Mutternfalle, Rastnase, Filmscharnier) und `sketch` (Grundplatte
  zeichnen) — kein Kapitel führt sie als eine Aufgabe.
- „Ein Maß nachträglich ändern, ohne alles neu zu bauen" — das Prinzip steht
  in `history` und wird in `features` an Bohrungen gezeigt, aber es gibt
  keine eigene kurze Seite, die genau diese Sorge des Umsteigers direkt
  adressiert (aus einem Slicer/CAD-Programm, in dem eine Änderung oft alles
  zerstört).
- „Warum passt mein importiertes Teil nicht auf das Bett / warum ist es zu
  groß" — verteilt über `export`, `splitting` und `trouble`; für den ersten
  Fall des Interessenten (heruntergeladenes Modell) wäre ein Kapitel „Ein
  fremdes Modell passend machen" naheliegender als die heutige Aufteilung
  nach Werkzeugen.
- Eine Aufgabe „Wo finde ich etwas, das nicht im Menü steht" fehlt ganz —
  Rechtsklick-Handlungen sind wichtige Wege (siehe `start`, `features`,
  `sketch`), aber nirgends gebündelt als eigene, kurze Bildseite „Was der
  Rechtsklick zeigt".

## 4. Zählbare Kennzahlen

Direkt aus `manual.py` gezählt (Näherung bei Sätzen, siehe Kopf des
Berichts):

| Kennzahl | Wert |
|---|---|
| Geschriebene Seiten insgesamt | 30 |
| Wörter insgesamt | rund 16 449 |
| Seiten über 800 Wörter | 6 — `window` (840), `features` (2087), `moving` (841), `sketch` (1442), `extras` (1042), `trouble` (896) |
| Seiten ohne ein einziges Bild | 15 von 30 (50 %) — `what`, `features`, `moving`, `sculpting`, `exchange`, `resin`, `chat`, `generating`, `extras`, `labels`, `remote`, `activation`, `trouble`, `glossary`, `spacemouse-access` |
| Sätze über 25 Wörter insgesamt | rund 127 |
| Mittlere Satzlänge, gesamter Bestand | rund 15,5 Wörter |
| Seite mit der höchsten mittleren Satzlänge | `resin` (23,4 — aber nur 8 Sätze, statistisch schwach) und `moving` (18,7 bei 45 Sätzen, belastbarer) |
| Seite mit den meisten langen Sätzen absolut | `sketch` (18 von 82) |
| Bebilderte Seite mit den meisten Bildern | `parts` (10 Bilder auf 777 Wörter — das Vorbild für alle anderen) |

## 5. Die zehn wichtigsten Änderungen

1. **`features` und `moving` bekommen Bilder.** Beide beschreiben das
   Auswahlfenster und seine Griffe ausführlich in Worten (2087 bzw. 841
   Wörter) und zeigen keinen einzigen Screenshot — das ist der größte
   einzelne Hebel für den angekündigten Bildumbau.
2. **Eine echte Bildfolge für die ersten fünfzehn Minuten** (`start`): die
   acht Schritte stehen schon nummeriert im Text, aber mit nur fünf Bildern
   auf acht Schritte — jeder Schritt verdient sein eigenes nummeriertes Bild
   mit Pfeil auf das genannte Element.
3. **`tolerances` (Spiel und Passung) vor `sketch` und `parts` einordnen** —
   für die Zielgruppe „Gehäuse/Halter" ist das Spielmaß der Unterschied
   zwischen einem passenden und einem unbrauchbaren Deckel, steht aber erst
   an zwölfter Stelle.
4. **Ein neues Kapitel „Gehäuse mit Deckel bauen"**, das `sketch`,
   `tolerances` und die passenden Bausteine aus `parts` an einem
   durchgehenden Beispiel zusammenführt statt sie über drei Kapitel zu
   verteilen.
5. **`window` in ein einzelnes, vollständig durchnummeriertes Bild
   verwandeln** statt einer Textbeschreibung von neun Bereichen mit nur
   einem Bild — genau der vom Entwickler gewünschte Bildstil.
6. **Die §-Verweise aus Kundendialogen entfernen** (`chat`: §26.4,
   `generating`: §2.2) — Bauplan-Paragraphen gehören nicht in Text, den ein
   Kunde liest.
7. **`extras` in drei kurze, bebilderte Seiten teilen** (Slicer, Ollama,
   ComfyUI) statt einer 1042-Wort-Seite ohne ein einziges Bild für drei ganz
   verschiedene Einrichtungswege.
8. **`trouble` als durchsuchbare Liste mit Sprungmarken statt Fließtext** —
   der Grundgedanke „jeder Fehler nennt einen Weiter-Weg" ist schon richtig,
   die Auffindbarkeit einer bestimmten Zeile in 896 Wörtern nicht.
9. **Die Reihenfolge der Kapitel auf zwei Ebenen umstellen**: eine kurze
   Pflichtstrecke für die erste Stunde (`what`, `start`, `window`, `looking`,
   `parts`, `tolerances`), der Rest als Nachschlagewerk, das die Oberfläche
   selbst an der passenden Stelle verlinkt statt vorauszusetzen, dass jemand
   linear liest.
10. **Sätze über 25 Wörter in den drei dichtesten Seiten kürzen**
    (`sketch`, `features`, `moving` — zusammen 45 der 127 langen Sätze),
    insbesondere dort, wo ein langer Satz mehrere Bedienschritte in einem
    Nebensatz verbirgt statt sie als eigene Zeilen oder Bildunterschriften zu
    zeigen.
