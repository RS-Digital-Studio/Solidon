# Konzept — Der Agent wird Teil der Anwendung

Stand 08.08.2026, aus einer vollständigen Gegenüberstellung von Ist
(`app/core/agent/`, `app/ui/chat.py`, `app/core/backends/`) und Soll
(Bauplan, ROADMAP). Der Unterbau der Agentenschicht ist richtig gebaut:
eine Werkzeugoberfläche aus dem Register, ein Vorschlag ist genau eine
Transaktion, nach jeder Op läuft die Prüfung, jede Transaktion trägt ihre
Herkunft. Was fehlt, liegt an drei Stellen — was der Agent **sieht**, was
er **erreichen kann**, und was der Nutzer **von ihm sieht**. Dieses Konzept
schließt alle drei, plus das Fundament darunter.

Eine Aussage vorweg, weil sie die Reihenfolge bestimmt: **Die Suite-Zahlen,
an denen heute jede Aussage über den Agenten hängt, sind ungültig.** Alle
Messreihen entstanden unter einem still abgeschnittenen Prompt (der
`num_ctx`-Fund: unter 32768 Token fiel der Systemprompt weg, 0/3 statt 3/3
bei Bausteinen). Wer auf diesem Stand „verbessert", misst gegen Rauschen.
Deshalb steht die neue Basislinie vor jedem anderen Punkt.

---

## 1. Ziele und Nicht-Ziele

**Ziele.** Der Agent sieht denselben Zustand wie der Nutzer (Steckbrief
vollständig, Analysen erreichbar, Ansichten als Bild). Er erreicht dieselben
Hebel wie die Menüs (Druckeinstellungen, Projektdrucker und -material,
Skizzen über benannte Grundformen). Der Chat zeigt, was der Agent gerade tut
und was ein Vorschlag gekostet hat. Jede Erweiterung wird an der Suite
gemessen, vorher und nachher.

**Nicht-Ziele — was ausdrücklich so bleibt:**

- **Alle Ops aus dem Register bleiben in der Werkzeugliste.** Keine Auswahl
  nach `applies_to` als Antwort auf die Werkzeuglast — nach der Messung
  ausdrücklich bestätigt (ROADMAP).
- **Keine Koordinaten aus dem Agenten** (Leitprinzip 5), kein roher
  `sketch`-Parameter — die Sperre in `session.py` bleibt.
- **Kein zweiter Weg ins Dokument** neben der Werkzeugliste (§26.6); die
  MCP-Auflagen (nur `127.0.0.1`, kein Quelltext, kein Pfad, jede Handlung
  eine Transaktion) gelten unverändert für alles Neue.
- **Kein Text-Streaming in dieser Ausbaustufe.** Die Backends können es
  nicht einheitlich, und der Fortschritt (Abschnitt 4.1) löst das eigentliche
  Problem — die Black Box — billiger. Streaming bleibt als spätere Option
  notiert, wird hier nicht gebaut.
- **Keine neuen Abhängigkeiten.** Alles Folgende geht mit dem Bestand.

---

## 2. Fundament: erst messen, dann bauen

### 2.1 Neue Basislinie der Agenten-Suite

Ein vollständiger Lauf beider Säulen (15 + 18 Fälle) mit `num_ctx = 32768`,
lokal und — wenn ein Schlüssel da ist — einmal gegen Anthropic. Das Ergebnis
ersetzt die 8/33 in der ROADMAP als Referenz; die Werkzeugmengen-Tabelle und
der Modellvergleich gelten bis zur Wiederholung als zurückgezogen. Jede
Änderung aus diesem Konzept, die Prompt, Kontext oder Werkzeugliste berührt,
misst gegen diese Basislinie — Verschlechterung heißt zurücknehmen, wie bei
der Regelsammlung (§39).

### 2.2 Die tote Kennzahl zum Leben bringen

`TARGET_VALID = 0.95` und `Outcome.invalid` stehen in
`tools/run_agent_suite.py`, gemessen wird nichts: `run_case` füllt `invalid`
nie. Die Sitzung lehnt schemaungültige Ops bereits ab — diese Ablehnungen
werden gezählt und je Fall ausgewiesen. Der Anteil schemagültiger Aufrufe im
ersten Versuch ist genau die Kennzahl, die sagt, ob die Werkzeugschemata für
das Modell verständlich sind.

### 2.3 Zwischenspeicherung und Antwortbudget im Anthropic-Backend

- **Prompt-Zwischenspeicherung:** ~99 KB Werkzeugschemata und der
  Systemprompt gehen heute bei jedem der bis zu 8 Schritte eines Zuges neu
  über die Leitung. `cache_control` (ephemeral) auf dem letzten
  Werkzeugschema und dem Systemblock lässt alles Stabile im Zwischenspeicher
  — kein SDK nötig, zwei Felder im Payload von `AnthropicBackend.complete`.
  Wirkung: Schritt 2 bis 8 eines Zuges kosten einen Bruchteil, die Latenz
  fällt spürbar.
- **`max_tokens` fällt als Konstante.** 4096 fest verdrahtet neben einem
  Zugbudget von 120 000 ist unbegründet; der Wert wird ein Parameter des
  Backends mit Vorgabe 8192, gedeckelt durch das verbleibende Zugbudget.

### 2.4 Eine Werkzeuglogik statt zwei

Die drei Zusatzwerkzeuge sind in `main_window.run_remote` ein zweites Mal
implementiert (`_remote_report`, `_remote_parameter`, `_remote_fit`) — die
Logik aus `session.py` dupliziert, mit eigenen Fehlerpfaden. Die gemeinsame
Ausführung wandert in ein Kernmodul (`agent/toolexec.py` oder direkt in
`tools.py`), Sitzung und Fernsteuerung rufen dieselben Funktionen. Alles,
was dieses Konzept an Werkzeugen ergänzt, entsteht von vornherein nur dort —
sonst verdoppelt sich die Pflege mit jedem Punkt dieses Konzepts.

---

## 3. Wahrnehmung: der Agent sieht, was der Nutzer sieht

Heute arbeitet der Agent halbblind: Nach `drill_hole` kennt er die ID der
neuen Bohrung nicht, bestehende Passungen sieht er nie, Analysen erreichen
ihn nicht, und die gerenderten Ansichten, die §23 neben dem Steckbrief
verlangt, existieren im Kontext nicht.

### 3.1 Frischer Steckbrief mitten im Zug — der größte Quotenhebel

Zwei Maßnahmen, die zusammengehören:

1. **Das Werkzeugergebnis jeder geometrieändernden Op nennt die neuen und
   geänderten Merkmale mit ihren IDs.** Die Auswertung der Arbeitskopie
   läuft nach jeder Op ohnehin (für `checks.py`); was fehlt, ist nur, ihre
   Merkmalssicht in den Ergebnistext zu heben: „`drill_hole` angewandt —
   neue Bohrung `hole_5` (Ø 6,0, Achse +Z, Durchgang) auf `obj_1`". Damit
   kann der Agent im nächsten Schritt auf das verweisen, was er gerade
   erzeugt hat — heute muss er raten.
2. **Neues Zusatzwerkzeug `read_digest`** (optional `objects`): liefert den
   aktuellen Steckbrief der Arbeitskopie, im selben Format wie das Weltbild
   zu Zugbeginn. Für den Fall, dass der Agent nach mehreren Schritten den
   Überblick neu braucht, statt ihn aus Einzelergebnissen zu rekonstruieren.

### 3.2 Der Steckbrief wird vollständig

`perceive/digest.py` bekommt vier Blöcke, die heute fehlen:

- **Passungen:** je Passung eine Zeile (`fit_1: obj_1:hole_2 ↔ obj_2:pin_1,
  press, auto:petg — eingehalten/verletzt`). Der Agent kann Passungen
  anlegen, aber nicht nachsehen, welche es gibt — das ist die absurdeste
  der Lücken.
- **Druckeinstellungen in einer Zeile:** Stufe, Material, Drucker plus die
  Werte, die vom Profil abweichen. Nicht das ganze Profil — die Zeile sagt,
  was eingestellt ist, `read_analysis` (3.3) sagt, was einzustellen wäre.
- **Quellen:** die Dateinamen aus `document.sources`, eine Zeile. „Mach es
  wie beim importierten Deckel" scheitert heute daran, dass der Agent nicht
  weiß, was importiert wurde.
- **Verlauf mit Parametern:** die Verlaufszeile nennt je Op die gesetzten
  Hauptwerte in Kurzform (`t3 „Bohren" (drill_hole d=6 depth=durch)`),
  gedeckelt, damit der Steckbrief nicht wuchert. Heute stehen dort nur
  Titel und Op-Nummern — der Agent kann aus dem Verlauf nichts lernen.

Der Steckbrief wächst damit; die Deckelung (Kurzformen, Grenzwerte) gehört
in denselben Schritt, und die Suite misst, ob der größere Kontext trägt.

### 3.3 Analysen erreichbar: `read_analysis`

Ein lesendes Zusatzwerkzeug neben `read_report`, mit `kind` und optional
`objects`:

| `kind` | liefert | Quelle |
|---|---|---|
| `printability` | Überhangfläche, Stützvolumen, Inseln, Brückenweiten, minimale Strukturbreite, erste Schichtfläche | `slice/analysis.py` |
| `estimate` | Druckzeit- und Materialschätzung | `slice/estimate.py` |
| `advice` | Einstellungsvorschläge mit Begründung (Pfad, alter/neuer Wert) | `slice/advise.py` |
| `maps` | die aggregierten Kennzahlen der Analysekarten (Wandstärke, Überhang, Defekte, …) | `perceive/maps.py` |
| `orientation` | die besten Orientierungen mit Kennzahlen | `slice/orientation.py` |

Regeln dazu:

- Gerechnet wird auf der Arbeitskopie in Entwurfsqualität, mit hartem
  Zeitdeckel je Aufruf; `orientation` ist die teuerste und bekommt den
  engsten. Ein überschrittener Deckel ist ein Ergebnis („Analyse nach n s
  abgebrochen — Teilstand: …"), kein Fehler.
- **Herkunft immer ausweisen** (Regel 14): alles hier ist Schichtanalyse,
  nie G-Code. Der Ergebnistext sagt das mit einem festen Präfix, damit die
  Zahl im Chat nicht als Slicer-Wahrheit weiterläuft.
- Damit kann der Agent Fragen wie „Ist das so druckbar?" oder „Wie lange
  druckt das?" beantworten, statt aus den zwei Warnzeilen des Prüfberichts
  zu raten — und er kann seine eigenen Vorschläge gegenprüfen, bevor er sie
  abgibt.

### 3.4 Normteile nachschlagbar: `read_standard`

Kleines lesendes Werkzeug über `knowledge/standards.py`: „M6" →
Kernloch, Durchgangsloch fein/mittel/grob, Schlüsselweite, Senkmaße.
Heute ist die Tabelle nur indirekt über Bausteinparameter erreichbar;
„welches Kernloch für M6?" kann der Agent nicht beantworten, obwohl die
Zahl im Programm steht.

### 3.5 Gerenderte Ansichten (§23) — der Agent bekommt Augen

§23 verlangt die gerenderten Ansichten neben dem Steckbrief; `context.py`
baut heute reinen Text, und `backends/llm.py` kennt keinen Bildpfad. Der
Ausbau, in drei Teilen entlang der bestehenden Schnitte:

1. **`Message` trägt optional Bildteile** (PNG-Bytes plus Beschriftung,
   z. B. „Ansicht von schräg oben"). `LLMBackend` bekommt die Eigenschaft
   `supports_images`; ein Backend ohne sie bekommt Nachrichten ohne
   Bildteile — der Textpfad bleibt für jedes Modell vollständig, Bilder
   sind Zugabe, nie Voraussetzung (Leitprinzip 8).
2. **`AnthropicBackend`** baut daraus `image`-Blöcke (base64);
   **`OllamaBackend`** füllt das `images`-Feld, aber nur wenn das gewählte
   Modell Vision beherrscht — die Fähigkeit wird wie `ollama_tool_check`
   einmal geprüft, nicht vermutet.
3. **Gerendert wird in der Oberfläche, nicht im Kern** — korrigiert bei der
   Umsetzung (08.08.2026): `figures.py` rendert SVG (die Netzprojektion aus
   `drawing.py`), und die Modelle nehmen PNG; ein Rasterweg im Kern wäre
   ein zweiter Renderweg gegen die eigene Doktrin. Die UI rendert zum
   Zugbeginn zwei kleine Ansichten offscreen (`app/ui/snapshots.py`,
   isometrisch und von oben) und reicht sie als beschriftete Bytes herein;
   die Kommandozeile lässt es weg, und beides ist richtig. Eine
   Auffrischung mitten im Zug gibt es nicht — der Zwischenzustand ist
   Sache von `read_digest`. Ollama bleibt vorerst fest ohne Bilder: das
   Vorgabemodell ist kein Vision-Modell, und eine ungemessene Fähigkeit
   wird nicht behauptet.

Der Nutzen ist konkret: „das Loch vorne links" ist im Text mehrdeutig, im
Bild nicht — und die drei absichtlich mehrdeutigen Suite-Fälle messen genau
das. Die Erwartung bleibt trotzdem `ask_user` bei echter Mehrdeutigkeit;
das Bild reduziert die falschen Sicherheiten, es ersetzt die Rückfrage nicht.

---

## 4. Sichtbarkeit: der Nutzer sieht, was der Agent tut

### 4.1 Fortschritt statt endlosem Balken

Heute: Eingabe gesperrt, „Der Agent denkt nach.", endloser Balken — bis zu
acht Schritte lang keine Auskunft. Die Sitzung bekommt einen
Fortschritts-Callback (dasselbe Muster wie `ctx.progress`, kein Qt im Kern):
je Schritt Schrittnummer und Werkzeugtitel aus dem Register. Der Chat zeigt
„Schritt 3 — Bohren auf obj_1" mit Schrittzähler; der Abbrechen-Knopf bleibt
unverändert (Prüfung zwischen den Schritten, wie heute). Fragt der Agent
(`ask_user`), sagt die Statuszeile das, bevor der Dialog aufgeht.

### 4.2 Der Vorschlag zeigt seine Kosten und seine Fragen

`Proposal` sammelt `steps`, `input_tokens`/`output_tokens` und `questions`
samt Antworten — die UI zeigt davon nichts. Die Entscheidungszeile wird
ergänzt: Schrittzahl und Tokenzahlen in einer unaufdringlichen Nebenzeile,
die gestellten Rückfragen samt gegebener Antworten aufklappbar (sie sind
Teil der Begründung des Vorschlags). Bei `stopped` steht der Grund
ausgeschrieben: „Nach 8 Schritten angehalten — der Vorschlag zeigt den
Stand bis hierhin." Damit ist der harte Deckel aus §26.5 nicht nur
vorhanden, sondern sichtbar.

### 4.3 Der Chat ist auch ein Suchfeld (§2.6)

Der Bauplan verlangt: „Wie mache ich das Loch größer?" wird mit dem
Vorschlag **und** dem Hinweis beantwortet, wo die Funktion im Menü steht.
Die Information steckt bereits in den Werkzeugschemata (Titel, Kategorie,
Kürzel aus dem Register) — es fehlt ein Absatz im Systemprompt: bei
Erklär- und Wie-Fragen nennt die Antwort den Menüort in der Form
„Kategorie → Titel (Kürzel)". Kein neues Werkzeug, keine neue Datenquelle;
`PROMPT_VERSION` zählt hoch, die Suite bekommt zwei Fälle, die genau das
erwarten (eine reine Wie-Frage, eine Wie-Frage mit anschließendem „mach
es").

### 4.4 Automatische Übernahme eindeutig umkehrbarer Vorschläge (§26.5)

Der Bauplan sagt „kann automatisch laufen", die UI sagt heute grundsätzlich
nein (dokumentiert nur im Docstring von `chat.py`). Regel 19 — keine
Bestätigung vor rücknehmbaren Handlungen — spricht für den Bauplan.
Festlegung:

- **Übernommen wird automatisch**, wenn der Vorschlag ausschließlich aus
  Ops mit `reversible=True` besteht, keine Warnungen oder Fehler in den
  Befunden trägt, kein `create_from_scad` enthält und keine Rückfrage
  offen war. Parameter und Passungen sind dabei unschädlich — sie reisen
  als `DocumentChange` mit und ein Undo nimmt sie mit zurück.
- **Die Vorschau-Mechanik bleibt**, nur die Entscheidung entfällt: die
  Leiste wird zur Übernommen-Leiste („Übernommen (t7) — Rückgängig nimmt
  alles zurück", Leertaste zeigt weiter das Vorher), der Verwerfen-Knopf
  wird zum Rückgängig-Knopf. Ein Klick, derselbe Effekt wie heute zwei.
- **Abschaltbar in den Einstellungen** (eine Präferenz, keine
  Betriebsarten-Umschaltung im Sinn von §41). Vorgabe: an — das ist die
  Linie des Bauplans.

### 4.5 Der gedeckelte Verlauf sagt, dass er gedeckelt ist

`HISTORY_LIMIT = 12`: ältere Chatbeiträge verschwinden aus dem Kontext ohne
Hinweis — der Agent widerspricht sich dann scheinbar grundlos. Fallen
Beiträge weg, steht am Anfang des mitreisenden Verlaufs eine Zeile
„[n ältere Beiträge nicht mitgesendet]". Eine Zeile, kein neues Verhalten —
aber das Modell weiß, dass es Vorgeschichte gibt, und rät nicht.

---

## 5. Handlungsraum: der Agent erreicht dieselben Hebel wie die Menüs

### 5.1 Druckeinstellungen: lesen ja, setzen nein

**Korrigiert bei der Umsetzung (08.08.2026).** Der ursprüngliche Entwurf sah
`set_print_setting(path, value, reason)` als `DocumentChange` vor — das
kollidiert mit zwei geltenden Festlegungen, die der Entwurf übersehen hat:
Druckeinstellungen reisen **nicht** in Transaktionen (§15.5 zieht die Grenze
an der Auswertung — Einstellungen reisen zum Slicer), und §28.2 sagt
„Übernommen wird auf Klick, nie von allein". Ein setzendes Werkzeug hätte
entweder Regel 16 gebrochen (ein Undo nähme die Einstellung nicht zurück)
oder eine Formatänderung samt Migration verlangt, um eine Grenze aufzuweichen,
die mit Absicht dort verläuft.

Es bleibt beim Lesen, und das schließt den Kreis trotzdem: die
Steckbriefzeile (3.2) sagt, was gilt, `read_analysis("advice")` (3.3) liefert
die begründeten Vorschläge aus `advise.py`, der Agent nennt sie samt Grund —
und der Klick bleibt im Druckdialog, wo er hingehört.

### 5.2 Projektdrucker und -material: `set_print_target`

`DocumentState` kennt `printer`/`material` als transaktionsfähige Änderung,
nur das Werkzeug fehlt. Ein Werkzeug mit zwei optionalen Feldern
(`printer`, `material`), Werte gegen die bekannten Profile geprüft,
Toleranzen bleiben `auto:<material>` (Regel 7) und rechnen sich beim
Materialwechsel von selbst um — genau dafür ist die Verweisform da.

### 5.3 Skizzen über benannte Grundformen (§30.1)

Die größte strukturelle Lücke: §30.1 sagt, der Agent erzeugt Skizzen
**ausschließlich über benannte Grundformen** — gebaut ist nur die Sperre
des rohen `sketch`-Parameters, der vorgesehene Weg fehlt ganz. Vier
Suite-Fälle (`free_shape`, `hex_base`, `pocket_plate`, `handrail_bend`)
erwarten Skizzen-Ops, die der Agent strukturell nicht gewinnen kann.

Festlegung:

- Die fünf Skizzen-Ops akzeptieren alternativ zum `sketch`-Verweis eine
  **`shape`-Beschreibung**: Grundform (`rect`, `circle`, `slot`,
  `polygon_regular`, `arc_path`), Maße als Parameter oder Zahlen, Lage
  über einen Anker (Feature-ID plus Versatz entlang benannter Achsen).
  Keine Punktliste, nirgends — die Grammatik kennt nur Formen und Anker,
  Leitprinzip 5 bleibt unverletzt.
- Der Kern übersetzt die Beschreibung deterministisch in eine Skizze; im
  Verlauf steht die Op wie jede andere, der Nutzer kann die erzeugte
  Skizze im Skizzeneditor öffnen und weiterbearbeiten.
- Der rohe `sketch`-Parameter bleibt für den Agenten gesperrt
  (`session.py`-Sperre unverändert); `shape` ist der einzige Weg.
- Das Schema von `shape` wird in §30.1 festgeschrieben (Ansage, Abschnitt
  6), die vier Suite-Fälle bekommen ihre Erwartungen präzisiert.

### 5.4 Was bewusst nicht in den Handlungsraum kommt

- **Export und Slicer-Übergabe** bleiben beim Nutzer. Ein Agent, der
  Dateien auf die Platte schreibt und externe Programme startet, ist eine
  andere Vertrauensstufe als einer, der rücknehmbare Transaktionen
  vorschlägt — und der Bedarf ist über `estimate`/`printability` (3.3)
  gedeckt: der Agent kann sagen, was ein Export ergäbe, der Klick bleibt
  ein Klick. Wenn sich das als zu eng erweist, ist es eine eigene Ansage,
  kein Nebenprodukt.
- **Redo als Werkzeug** kommt nicht. `undo_transaction` existiert, weil
  „nimm das zurück" eine natürliche Chat-Anweisung ist; „stell das
  Zurückgenommene wieder her" sagt man dem Verlauf, nicht dem Agenten.
  Ein Werkzeug mehr für einen Weg, den die UI in einem Klick hat, wäre
  Werkzeuglast ohne Quotengewinn.
- **Kalibrierung, Varianten, Katalogblättern, Handbuch, Tour** bleiben
  UI-Angelegenheiten; `find_part` (Suche) und `read_standard` (3.4) decken
  den Wissensbedarf des Agenten.

---

## 6. Bauplan-Änderungen — die Ansage

Dieses Konzept verlangt vier Ergänzungen am Bauplan; sie werden vor der
Umsetzung der jeweiligen Punkte eingetragen:

1. **§26.2 Werkzeugliste** wächst um `read_digest`, `read_analysis`,
   `read_standard`, `set_print_setting`, `set_print_target`. Die Liste
   bleibt abschließend — was dort nicht steht, gibt es nicht.
2. **§30.1** bekommt das `shape`-Schema der benannten Grundformen
   (Formenliste, Ankerprinzip, Verbot der Punktliste ausgeschrieben).
3. **§35/§40 Suite-Umfang:** die 33 Referenzanfragen wachsen um die Fälle
   der neuen Werkzeuge (Druckbarkeit, Schätzung, Normteil,
   Einstellungsänderung, Menüort-Antwort, Grundform-Skizzen); die Zahl im
   Bauplan wird fortgeschrieben.
4. **§23** bleibt inhaltlich, bekommt aber den Vermerk, dass Ansichten an
   Backends ohne Bildfähigkeit entfallen und der Textpfad vollständig
   bleiben muss (Leitprinzip 8, präzisiert).

Nicht geändert werden: §26.5 (die automatische Übernahme ist dort schon als
„kann" angelegt), §26.6 (MCP-Auflagen gelten unverändert auch für die neuen
Werkzeuge — die lesenden sind unkritisch, die schreibenden laufen wie jede
Op als eigene Transaktion mit Herkunft), §22.5/Regel 14 (Herkunftstrennung
wird von `read_analysis` ausdrücklich eingehalten, nicht aufgeweicht).

---

## 7. Reihenfolge und Abnahme

Sechs Schritte, jeder einzeln lieferbar, die Suite nach jedem grün und
nicht schlechter als die Basislinie. Innerhalb eines Schritts gilt die
Arbeitsweise des Hauses: kleine Schritte, Test zuerst, `/pruefen` vor jedem
Commit.

| Schritt | Inhalt | Abnahme |
|---|---|---|
| **0 — Messgrundlage** | 2.1 Basislinie, 2.2 `invalid`-Kennzahl, 2.3 Zwischenspeicherung + `max_tokens` | Voller Suite-Lauf dokumentiert (ROADMAP + `rules.toml`-Verlauf); `invalid` wird je Fall ausgewiesen; Tokenkosten je Zug messbar gefallen |
| **1 — Wahrnehmung Text** | 3.1 frischer Steckbrief, 3.2 Steckbrief-Blöcke, 3.4 `read_standard`, 4.5 Verlaufshinweis | Op-Ergebnisse nennen neue Feature-IDs (Test gegen `ScriptedBackend`); Steckbrief-Tests für Passungen/Einstellungen/Quellen/Verlauf; Suite ≥ Basislinie |
| **2 — Sichtbarkeit** | 4.1 Fortschritt, 4.2 Kosten und Fragen am Vorschlag, 4.3 Suchfeld-Absatz | Offscreen-Test: Statuszeile trägt Schritt und Werkzeugtitel; Entscheidungszeile zeigt Schritte/Tokens; zwei neue Suite-Fälle für den Menüort bestehen |
| **3 — Handlungsraum** | 3.3 `read_analysis`, 5.1 `set_print_setting`, 5.2 `set_print_target` | Bauplan-Ansage 1 eingetragen; jede Analyse mit Herkunftspräfix und Zeitdeckel (Test); Einstellungsänderung reist im Undo mit (Test); neue Suite-Fälle bestehen |
| **4 — Augen und Autopilot** | 3.5 Ansichten, 4.4 automatische Übernahme | Bild erreicht Anthropic-Payload (Test gegen Transport-Attrappe); Backend ohne `supports_images` bekommt reinen Text; Auto-Übernahme greift nur unter allen vier Bedingungen (Test je Bedingung); mehrdeutige Fälle fragen weiterhin 3/3 |
| **5 — Grundform-Skizzen** | 5.3 `shape`-Schema | Bauplan-Ansage 2 eingetragen; Geometrietests je Grundform gegen den Korpus; die vier Skizzen-Suite-Fälle sind gewinnbar und gewonnen |

Begleitend, ohne eigenen Schritt: 2.4 (eine Werkzeuglogik) beginnt vor
Schritt 3 — die neuen Werkzeuge entstehen nur einmal.

**Risiken, benannt:**

- **Kontextwachstum.** Steckbrief-Blöcke, Analysen und Bilder machen den
  Zug teurer; die Zwischenspeicherung (2.3) kompensiert das bei Anthropic,
  lokal zählt `num_ctx` — nach Schritt 1 und 4 wird geprüft, ob 32768
  weiter reicht, mit derselben Messmethode wie beim `num_ctx`-Fund.
- **Lokale Modelle ohne Vision** bleiben zweite Klasse bei 3.5 — gewollt
  (Leitprinzip 8), aber es gehört in die Modellhinweise der Einrichtung.
- **Die automatische Übernahme** ändert das gefühlte Verhalten des Chats.
  Die vier Bedingungen sind eng gewählt; wenn die Praxis zeigt, dass
  Nutzer trotzdem überrascht sind, ist die Vorgabe der Präferenz die
  Stellschraube — nicht die Mechanik.
- **`read_analysis(orientation)`** kann trotz Deckel lang wirken; der
  Fortschritt (4.1) zeigt den laufenden Schritt, und der Deckel liefert
  einen Teilstand statt eines Fehlers.

---

## 8. Abdeckung — jeder Fund der Durchsicht hat eine Adresse

| Fund | Abschnitt |
|---|---|
| Suite-Messungen ungültig (num_ctx), Basislinie fehlt | 2.1 |
| `TARGET_VALID`/`Outcome.invalid` toter Code | 2.2 |
| Keine Prompt-Zwischenspeicherung, 99 KB je Schritt | 2.3 |
| `max_tokens = 4096` fest verdrahtet | 2.3 |
| MCP-Zusatzwerkzeuge doppelt implementiert | 2.4 |
| Agent kennt neue Feature-IDs nach einer Op nicht | 3.1 |
| Kein Werkzeug für frischen Steckbrief | 3.1 |
| Passungen nicht im Steckbrief | 3.2 |
| Druckeinstellungen unsichtbar | 3.2, 5.1 — lesen, nicht setzen (korrigiert) |
| Quellen/Dateinamen unsichtbar | 3.2 |
| Op-Parameter im Verlauf fehlen | 3.2 |
| Schichtanalyse/Karten/Schätzung/Orientierung unerreichbar | 3.3 |
| Normteiltabelle nicht nachschlagbar | 3.4 |
| Gerenderte Ansichten (§23) erreichen den Agenten nicht | 3.5 |
| Kein Fortschritt, nur endloser Balken | 4.1 |
| Schritte/Tokens/Fragen gesammelt, nie gezeigt | 4.2 |
| §2.6 „Chat ist auch ein Suchfeld" nicht eingelöst | 4.3 |
| §26.5 automatische Übernahme fehlt | 4.4 |
| `HISTORY_LIMIT` schneidet ohne Hinweis | 4.5 |
| Drucker/Material des Projekts nicht wechselbar | 5.2 |
| §30.1 Grundform-Skizzen nicht gebaut, vier Suite-Fälle ungewinnbar | 5.3 |
| Export/Slicing ohne Werkzeug | 5.4 — bewusst so, mit Begründung |
| Redo ohne Werkzeug | 5.4 — bewusst so, mit Begründung |
| Kostendeckel nur als Token, nicht als Geld | 4.2 macht ihn sichtbar; eine Geldrechnung braucht Preisdaten je Modell und bleibt Ausbaustufe |
