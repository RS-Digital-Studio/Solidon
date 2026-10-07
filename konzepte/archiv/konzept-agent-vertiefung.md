# Konzept — Der Agent wird Teil der Anwendung

> **Umgesetzt und abgenommen (08.08.2026, Nachbesserungen 09.08.2026).**
> Alle sechs Schritte aus Abschnitt 7 stehen in `ROADMAP.md:3806–3878` mit
> Haken; die Nachher-Messung steht bei `ROADMAP.md:3888–3895`. Dieses
> Dokument ist ab hier **Begründungsgedächtnis, keine Arbeitsliste** — der
> Haupttext steht weiter im Futur, weil er beim Planen so geschrieben wurde.
> Was jeweils daraus wurde, sagen die Erledigt-Vermerke darunter. Der Stand
> steht in `ROADMAP.md`, Abschnitt „Die Agent-Vertiefung".

Stand 08.08.2026, ergänzt am 14.08.2026, nachrecherchiert am 19.08.2026,
aus einer vollständigen Gegenüberstellung von Ist
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

> **Erledigt.** Die Basislinie ist gefahren: 17/33 mit vollem Fenster
> (08.08.2026 mittags), nach der Umsetzung 28/39 = 72 %
> (`ROADMAP.md:3888–3895`). `num_ctx` steht fest bei 32768
> (`app/core/backends/llm.py:373` `OLLAMA_CONTEXT_TOKENS`, gesetzt in jedem
> Aufruf, `:475`). Werkzeugmengen-Tabelle und Modellvergleich sind bis heute
> (19.08.2026) **nicht** wiederholt worden — sie bleiben zurückgezogen.
> Gegen Anthropic ist die Suite weiterhin nicht gefahren (kein Schlüssel
> hinterlegt, `ROADMAP.md:3909`).

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

> **Erledigt — der lokale Teil.** 17/33 vorher, 28/39 nachher (auf den 33
> alten Fällen 25/33 = 76 %), `qwen3:14b`, volles Fenster
> (`ROADMAP.md:3888–3895`). Die 8/33 ist damit ersetzt; sie steht nur noch
> historisch (`ROADMAP.md:2813`, `:3059`). Die Suite umfasst heute **39**
> Referenzanfragen (21 zu Säule C, 18 zu Säule A) — die Zahl 15 + 18 oben
> war schon 08.08. überholt; festgehalten in `AGENTS.md:231`,
> `3d-agent-bauplan.md:1569` und
> `tests/test_agent_suite.py:156 test_the_suite_has_the_size_the_plan_asks_for`.

> **Offen — der Lauf gegen Anthropic.** Er steht aus, und bevor er gefahren
> wird, ist außen zweierlei passiert (Recherche 19.08.2026):
> `DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"` (`llm.py:172`) ist ein
> Bequemlichkeits-Alias auf den Schnappschuss `claude-sonnet-4-5-20250929`,
> kein festgenageltes Modell — ab der 4.6-Generation gibt es keine Aliase
> mehr, dort ist die datumslose ID selbst der Schnappschuss
> (https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions).
> Und dieser Schnappschuss trägt ein vorläufiges Rückzugsdatum „not sooner
> than September 29, 2026" bei Status „Active"; eine Abkündigung ist nicht
> ausgesprochen
> (https://platform.claude.com/docs/en/about-claude/model-deprecations).
> Der Nachfolger `claude-sonnet-5` kostet 2 USD Eingabe / 10 USD Ausgabe je
> Mio. Token bei 1 Mio. Kontext gegen 3/15 USD bei 200k für Sonnet 4.5
> (https://platform.claude.com/docs/en/about-claude/models/overview) — der
> Wechsel ist billiger und größer, nicht bloß fällig. Eine Basislinie gegen
> ein Modell zu fahren, das in sechs Wochen zurückgezogen werden darf, misst
> die falsche Zahl; die Modellwahl gehört vor den Lauf, nicht danach.

### 2.2 Die tote Kennzahl zum Leben bringen

`TARGET_VALID = 0.95` und `Outcome.invalid` stehen in
`tools/run_agent_suite.py`, gemessen wird nichts: `run_case` füllt `invalid`
nie. Die Sitzung lehnt schemaungültige Ops bereits ab — diese Ablehnungen
werden gezählt und je Fall ausgewiesen. Der Anteil schemagültiger Aufrufe im
ersten Versuch ist genau die Kennzahl, die sagt, ob die Werkzeugschemata für
das Modell verständlich sind.

> **Erledigt.** Die Kennzahl misst: `run_case` füllt `outcome.invalid` aus
> `proposal.invalid_calls` (`tools/run_agent_suite.py:127`), weist sie je
> Fall aus (`:181`) und als Quote (`:196–201`); `Proposal` führt `tool_calls`
> und `invalid_calls` (`app/core/agent/proposal.py:54,56`). Gemessen: **156
> von 160 = 98 %** im ersten Versuch, Ziel `TARGET_VALID = 0.95` erfüllt
> (`ROADMAP.md:3893`). Tests: `tests/test_agent_suite.py:319
> test_invalid_calls_are_counted`, dazu `:707` und `:750`.

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

> **Erledigt, beides.** `cache_control` (ephemeral) sitzt auf dem
> Systemblock (`app/core/backends/llm.py:231`) und auf dem letzten
> Werkzeugschema (`:239`); `max_tokens` ist ein Backend-Parameter mit
> Vorgabe 8192 (`:185`), gedeckelt über `limit` (`:215`) im Payload
> (`:222`). `MAX_STEPS = 8` und `MAX_TOKENS = 120_000` stehen unverändert
> (`app/core/agent/session.py:78–79`).

> **Die Zahl ist gewachsen.** Die ~99 KB oben sind die Messung vom
> 08.08.2026; heute (19.08.2026) sind es **110 KB JSON aus 96 Schemata**
> (85 Ops plus 11 Zusatzwerkzeuge) — die ROADMAP hielt am 08.08. noch 86
> Schemata fest (`ROADMAP.md:3897`). Neu über die Leitung gehen sie nur
> beim ersten Schritt eines Zuges; ab dem zweiten greift die
> Zwischenspeicherung. Die Aussage bleibt also richtig, nur ihr Grund ist
> jetzt behoben statt offen.

> **Ein Außenfakt, der diesen Payload betrifft (Recherche 19.08.2026).**
> `AnthropicBackend.complete` sendet `temperature` unbedingt mit
> (`llm.py:223`, Vorgabe 0.0). `temperature`, `top_p` und `top_k` sind ab
> Claude Opus 4.7 abgekündigt: ein Nicht-Standardwert liefert einen
> 400-Fehler
> (https://platform.claude.com/docs/en/about-claude/model-deprecations).
> Mit Sonnet 4.5 und 4.6 geht es weiter; mit jedem neueren Modell scheitert
> der Aufruf. Das ist keine Aufgabe dieses Konzepts, aber es gehört an die
> Stelle, an der jemand als Nächstes das Modell wechselt.

### 2.4 Eine Werkzeuglogik statt zwei

Die drei Zusatzwerkzeuge sind in `main_window.run_remote` ein zweites Mal
implementiert (`_remote_report`, `_remote_parameter`, `_remote_fit`) — die
Logik aus `session.py` dupliziert, mit eigenen Fehlerpfaden. Die gemeinsame
Ausführung wandert in ein Kernmodul (`agent/toolexec.py` oder direkt in
`tools.py`), Sitzung und Fernsteuerung rufen dieselben Funktionen. Alles,
was dieses Konzept an Werkzeugen ergänzt, entsteht von vornherein nur dort —
sonst verdoppelt sich die Pflege mit jedem Punkt dieses Konzepts.

> **Erledigt — die gemeinsame Logik liegt in `session.py`, ein
> `toolexec.py` ist nie entstanden.** `_remote_report`
> (`app/ui/main_window.py:4718`), `_remote_fit` (`:4731`) und
> `_remote_parameter` (`:4748`) heißen weiter so, sind aber nur noch
> Weiterleitungen auf `report_text`, `build_fit` und `parse_number` in
> `app/core/agent/session.py:608,641,624` (die Docstrings nennen „Konzept
> 2.4"). Dazu kamen `standard_text` (`session.py:687`), `find_part_text`
> (`:755`) und `analysis_text` (`app/core/agent/analysis.py:66`). Ein
> eigenes Modul hätte nur einen Namen mehr gekostet — der Vorschlag oben
> nannte es als Möglichkeit, nicht als Bedingung.

---

## 3. Wahrnehmung: der Agent sieht, was der Nutzer sieht

Heute arbeitet der Agent halbblind: Nach `drill_hole` kennt er die ID der
neuen Bohrung nicht, bestehende Passungen sieht er nie, Analysen erreichen
ihn nicht, und die gerenderten Ansichten, die §23 neben dem Steckbrief
verlangt, existieren im Kontext nicht.

> **Erledigt — dieser Absatz beschreibt den Stand vom 08.08.2026 vormittags,
> nicht den heutigen.** Alle vier Lücken sind zu: Merkmals-IDs im
> Op-Ergebnis, `read_digest`, `read_analysis` und die beiden gerenderten
> Ansichten (`ROADMAP.md:3814–3874`). Die Einzelnachweise stehen bei den
> Unterabschnitten.

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

> **Erledigt — und teurer bezahlt als geplant.** Beides ist gebaut
> (`ROADMAP.md:3814–3821`); `read_digest` steht in der Werkzeugliste
> (`app/core/agent/tools.py:30–40`). Der Weg dorthin legte zwei Kernfehler
> frei, die nichts mit dem Agenten zu tun hatten: ein gebohrtes Loch wurde
> nie ein Merkmal, weil `apply_mapping` das unzugeordnete neue Merkmal über
> einen Überlebenden schrieb — eines von beiden verschwand wortlos aus der
> Szene; und darunter lag der vorzeichenempfindliche Achsenvergleich in
> `cost`, der nach einer 25°-Drehung die Hälfte der Löcher verwaiste. Eine
> Bohrungsachse ist eine Linie, keine Richtung. Beide Fälle hält
> `tests/test_matching.py` fest (`ROADMAP.md:3822–3835`).

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

> **Erledigt, alle vier Blöcke.** `app/core/perceive/digest.py`: Passungen
> mit Verletzt-Zustand (`:66–84`), Druckeinstellungen in einer Zeile
> (`:87–101`), Quellen (`:113–119`), Verlauf mit Parametern samt Deckelung
> als benannte Grenze (`:272–296`). Der größere Kontext trägt: die Quote
> stieg von 52 % auf 72 %, statt einzubrechen (`ROADMAP.md:3897–3899`).

### 3.3 Analysen erreichbar: `read_analysis`

Ein lesendes Zusatzwerkzeug neben `read_report`, mit `kind` und optional
`objects`:

| `kind` | liefert | Quelle |
|---|---|---|
| `printability` | Überhangfläche, Stützvolumen, Inseln, Brückenweiten, minimale Strukturbreite, erste Schichtfläche | `slice/analysis.py` |
| `estimate` | Druckzeit- und Materialschätzung | `slice/estimate.py` |
| `advice` | Einstellungsvorschläge mit Begründung (Pfad, alter/neuer Wert) | `slice/advise.py` |
| `orientation` | die besten Orientierungen mit Kennzahlen | `slice/orientation.py` |

> **Erledigt — mit vier Arten statt fünf.** `ANALYSIS_KINDS` führt
> `printability`, `estimate`, `advice` und `orientation`
> (`app/core/agent/analysis.py:43`); dasselbe Enum steht im Werkzeugschema
> (`app/core/agent/tools.py:304`) und im Bauplan (`3d-agent-bauplan.md:1230`).
> **`maps` ist bei der Umsetzung entfallen** und stand bis heute nur noch
> hier — die Zeile ist deshalb gestrichen. Die Kennzahlen der Analysekarten
> stecken in `printability`; als eigene Art hätte sie keinen Zug beantwortet,
> den die vier nicht schon beantworten. Wer sie doch braucht, trägt sie
> nach — aber dann in `analysis.py`, nicht in dieser Tabelle.

Regeln dazu:

- Gerechnet wird auf der Arbeitskopie in Entwurfsqualität, mit hartem
  Zeitdeckel je Aufruf; `orientation` ist die teuerste und bekommt den
  engsten. Ein überschrittener Deckel ist ein Ergebnis („Analyse nach n s
  abgebrochen — Teilstand: …"), kein Fehler.

  > **Anders gebaut: der Deckel zählt Dreiecke, nicht Sekunden.**
  > `TRIANGLE_LIMIT = 500_000` steht vorab prüfbar in
  > `app/core/agent/analysis.py:45–48`, und der Kommentar dort sagt den
  > Grund: „Ein Zeitlimit mitten in einer laufenden Rechnung gäbe es nur mit
  > Gewalt gegen den Thread." Damit gibt es auch keinen Teilstand nach
  > Zeitablauf — eine zu große Szene bekommt vorher eine Absage mit Grund.
  > Die Orientierungssuche fährt 24 Kandidaten mit festem Startwert
  > (`:51–58`). `ROADMAP.md:3849` nennt es „harter Dreiecksdeckel statt
  > Zeitgewalt".
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

> **Erledigt.** `read_standard` steht in der Werkzeugliste
> (`app/core/agent/tools.py:30–40`), die gemeinsame Ausführung als
> `standard_text` in `app/core/agent/session.py:687`.

### 3.5 Gerenderte Ansichten (§23) — der Agent bekommt Augen

§23 verlangt die gerenderten Ansichten neben dem Steckbrief; `context.py`
baut heute reinen Text, und `backends/llm.py` kennt keinen Bildpfad. Der
Ausbau, in drei Teilen entlang der bestehenden Schnitte:

1. **`Message` trägt optional Bildteile** (PNG-Bytes plus Beschriftung,
   z. B. „Ansicht von schräg oben"). `LLMBackend` bekommt die Eigenschaft
   `supports_images`; ein Backend ohne sie bekommt Nachrichten ohne
   Bildteile — der Textpfad bleibt für jedes Modell vollständig, Bilder
   sind Zugabe, nie Voraussetzung (Leitprinzip 8).
2. **`AnthropicBackend`** baut daraus `image`-Blöcke (base64).
   **`OllamaBackend`** meldet `supports_images = False` und bekommt deshalb
   nie Bildteile; eine Fähigkeitsprüfung wie `ollama_tool_check` gehört
   dorthin, sobald ein Vision-Modell gemessen ist.

   > **Hier stand ein Widerspruch, und er war schon beim Schreiben einer.**
   > Punkt 2 versprach, Ollama fülle das `images`-Feld „wenn das gewählte
   > Modell Vision beherrscht" — Punkt 3 desselben Abschnitts nahm es im
   > selben Atemzug zurück („bleibt vorerst fest ohne Bilder"). Gebaut ist
   > Punkt 3: `supports_images` gibt fest `False` zurück
   > (`app/core/backends/llm.py:429–434`), und keine Stelle füllt für Ollama
   > ein `images`-Feld. Punkt 2 ist oben auf den gebauten Stand gebracht.
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

> **Erledigt, alle drei Teile.** `Message.images`
> (`app/core/backends/llm.py:65`), `LLMBackend.supports_images` (`:101`),
> Anthropic `True` (`:200`) mit base64-`image`-Blöcken (`:264–275`), Ollama
> fest `False` (`:429`); `app/core/agent/context.py:66,72` reicht die
> Ansichten als `images` herein. Der Test dazu heißt
> `test_views_reach_only_a_backend_that_can_see`
> (`tests/test_agent_suite.py:578`). Die drei mehrdeutigen Fälle fragen
> weiterhin 3/3 (`ROADMAP.md:3892`).
>
> **Ein Satz fehlte hier und ist nachgetragen:** Gerendert wird im
> **Hauptthread**, in `propose_async`, bevor der Arbeiter startet
> (`app/ui/session.py:1077`). VTK im Arbeiter-Thread war eine Absturzfamilie
> (`ROADMAP.md:3922–3925`) — wer die Ansichten später anfasst, muss das
> wissen.

---

## 4. Sichtbarkeit: der Nutzer sieht, was der Agent tut

> **Erledigt — alle fünf Punkte.** Die Belege stehen bei den
> Unterabschnitten; die Sammelstelle ist `ROADMAP.md:3836–3845` (Schritt 2)
> und `:3860–3870` (Schritt 4). Das „Heute:" in 4.1 und das „fehlt" in 4.4
> beschreiben den 08.08.2026 vormittags, nicht den heutigen Stand.

### 4.1 Fortschritt statt endlosem Balken

Heute: Eingabe gesperrt, „Der Agent denkt nach.", endloser Balken — bis zu
acht Schritte lang keine Auskunft. Die Sitzung bekommt einen
Fortschritts-Callback (dasselbe Muster wie `ctx.progress`, kein Qt im Kern):
je Schritt Schrittnummer und Werkzeugtitel aus dem Register. Der Chat zeigt
„Schritt 3 — Bohren auf obj_1" mit Schrittzähler; der Abbrechen-Knopf bleibt
unverändert (Prüfung zwischen den Schritten, wie heute). Fragt der Agent
(`ask_user`), sagt die Statuszeile das, bevor der Dialog aufgeht.

> **Erledigt.** Der Rückruf sitzt im Kern (`app/core/agent/session.py:159`
> `progress: ProgressFn | None`, gemeldet in `:199` und `:224`), die
> Statuszeile „Schritt 3/8 — …" in `app/ui/chat.py:509–512`. Test:
> `test_the_turn_reports_its_progress` (`tests/test_agent_suite.py:523`).

### 4.2 Der Vorschlag zeigt seine Kosten und seine Fragen

`Proposal` sammelt `steps`, `input_tokens`/`output_tokens` und `questions`
samt Antworten — die UI zeigt davon nichts. Die Entscheidungszeile wird
ergänzt: Schrittzahl und Tokenzahlen in einer unaufdringlichen Nebenzeile,
die gestellten Rückfragen samt gegebener Antworten aufklappbar (sie sind
Teil der Begründung des Vorschlags). Bei `stopped` steht der Grund
ausgeschrieben: „Nach 8 Schritten angehalten — der Vorschlag zeigt den
Stand bis hierhin." Damit ist der harte Deckel aus §26.5 nicht nur
vorhanden, sondern sichtbar.

> **Erledigt.** Schritte und Token stehen in der Entscheidungszeile
> (`app/ui/chat.py:502–515`), die Rückfragen samt Antworten aufklappbar
> (`:196–203`, `:350–357`), und die erreichte Grenze steht ausgeschrieben
> (`:517–521`).

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

> **Erledigt — der Menüort steht in der Werkzeugbeschreibung, nicht im
> Systemprompt.** `PROMPT_VERSION` steht auf `"3"`
> (`app/core/agent/prompt.py:28`), und der Kommentar darüber sagt, warum:
> „der steht seither in jeder Werkzeugbeschreibung, das Modell muss ihn nur
> nennen". Gebaut in `app/core/agent/tools.py:109–113` über `menu_path` —
> und dort steht auch, warum es der volle Pfad sein muss: **nur Gruppe und
> Titel zu nennen traf für 72 von 77 Ops den falschen Ort.** Die zwei
> Suite-Fälle heißen `where_menu` und `where_hollow`
> (`tests/agent_cases.py:146–159`); der zweite ist eine reine Wo-Frage
> geworden statt der geplanten Wie-Frage mit „mach es".

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

> **Erledigt, alle drei Punkte.** Die vier Bedingungen stehen in
> `auto_acceptable` (`app/core/agent/apply.py:39`), die Einstellung heißt
> `auto_accept_reversible` mit Vorgabe `True` (`app/ui/settings.py:89–93`,
> Dialog `app/ui/settings_dialog.py:108–114`), ausgelöst wird sie in
> `app/ui/main_window.py:4185`, und die Übernommen-Leiste sitzt in
> `app/ui/chat.py:84,316–326`.
>
> **Eine Nachbesserung am 09.08. gehört dazu:** Der Rückgängig-Knopf prüfte
> nicht, welche Transaktion obenauf liegt — wer nach der Übernahme weiter
> arbeitete und dann drückte, nahm die falsche zurück. Er hängt jetzt am
> Dokument und prüft selbst (`ROADMAP.md:3917–3921`).

### 4.5 Der gedeckelte Verlauf sagt, dass er gedeckelt ist

`HISTORY_LIMIT = 12`: ältere Chatbeiträge verschwinden aus dem Kontext ohne
Hinweis — der Agent widerspricht sich dann scheinbar grundlos. Fallen
Beiträge weg, steht am Anfang des mitreisenden Verlaufs eine Zeile
„[n ältere Beiträge nicht mitgesendet]". Eine Zeile, kein neues Verhalten —
aber das Modell weiß, dass es Vorgeschichte gibt, und rät nicht.

> **Erledigt.** `app/core/agent/context.py:119–128` rechnet
> `skipped = len(entries) - HISTORY_LIMIT` und setzt die Zeile, wenn etwas
> wegfällt; der Kommentar dort verweist auf diesen Abschnitt.

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

> **Erledigt.** `set_print_target` steht in der Werkzeugliste
> (`app/core/agent/tools.py:30–40`); der Suite-Fall dazu prüft, dass Drucker
> und Material als `DocumentChange` reisen und ein Undo beide zurücknimmt
> (`tests/agent_cases.py:144`).

### 5.3 Skizzen über benannte Grundformen (§30.1)

**Aufgelöst bei der Umsetzung (08.08.2026): der Weg existierte bereits.**
Die Ist-Aufnahme, auf der dieses Konzept fußt, sah die Sperre des rohen
`sketch`-Parameters und schloss daraus, der vorgesehene Weg fehle ganz —
sie hat die Grundform-Parameter daneben übersehen. Tatsächlich tragen die
Skizzen-Ops seit P13 `shape`, `length`, `width`, `corners` und Verwandte
als reguläre Parameter (`app/core/sketch/shapes.py`: Rechteck, Langloch,
Kreis, Vieleck — exakt konstruiert, vom Solver bestätigt), und genau diese
Felder stehen im Werkzeugschema des Agenten. Die vier Suite-Fälle waren
nie strukturell ungewinnbar; was fehlte, war der Beweis.

Der steht jetzt als Test: eine geratene Punktliste wird abgelehnt und
zählt als ungültiger Aufruf, dieselbe Op läuft über die Grundformen durch,
und jede von den vier Fällen erwartete Op bietet `shape` an und `sketch`
nicht (`tests/test_agent_suite.py`). Eine Bauplan-Ansage braucht es nicht —
§30.1 beschreibt genau diesen Stand. Die Lehre gehört ins Konzept: eine
Aussage ohne §-Beleg ist eine Vermutung, auch die eigene.

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
   `read_standard`, `set_print_target`. Die Liste bleibt abschließend — was
   dort nicht steht, gibt es nicht. (Hier stand bis zum 19.08.2026 ein
   fünftes, `set_print_setting` — derselbe Rest des zurückgenommenen
   Setzers, der schon in der Tabelle von Abschnitt 7 stand.)
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

> **Erledigt — alle vier Ergänzungen stehen im Bauplan.**
> §26.2: `3d-agent-bauplan.md:1228–1231`, dazu die Begründung, warum es
> keinen Setzer gibt (`:1233–1239`). §30.1: `:1412–1415` („Der Agent erzeugt
> Skizzen ausschließlich über benannte Grundformen"). §35: `:1569`
> („39 Referenzanfragen — 21 zu Säule C, 18 zu Säule A"). §23: `:1065–1069`
> (Ansichten „erreichen nur ein Backend, das Bilder versteht; an jedes
> andere entfallen sie ersatzlos").
>
> **Ein Rest ist beim Übertragen liegengeblieben:** `3d-agent-bauplan.md:1244`
> sagt „Die **fünf** Werkzeuge ab `read_digest` kamen mit der
> Agent-Vertiefung dazu" — aufgezählt sind vier. Das ist wieder der
> zurückgenommene `set_print_setting`. Die Zahl gehört auf vier; eine
> Bauplanänderung wird angesagt und nicht nebenbei gemacht, deshalb steht
> sie hier und nicht dort.

---

## 7. Reihenfolge und Abnahme

Sechs Schritte, jeder einzeln lieferbar, die Suite nach jedem grün und
nicht schlechter als die Basislinie. Innerhalb eines Schritts gilt die
Arbeitsweise des Hauses: kleine Schritte, Test zuerst, `/pruefen` vor jedem
Commit.

> **Alle sechs Schritte sind abgenommen** (`ROADMAP.md:3806–3878`,
> Nachbesserungen am 09.08. bei `:3912–3950`). Die Tabelle steht als
> Begründung dessen, was gebaut wurde, nicht mehr als Arbeitsliste.

| Schritt | Inhalt | Abnahme |
|---|---|---|
| **0 — Messgrundlage** | 2.1 Basislinie, 2.2 `invalid`-Kennzahl, 2.3 Zwischenspeicherung + `max_tokens` | Voller Suite-Lauf dokumentiert (ROADMAP + `rules.toml`-Verlauf); `invalid` wird je Fall ausgewiesen; Tokenkosten je Zug messbar gefallen |
| **1 — Wahrnehmung Text** | 3.1 frischer Steckbrief, 3.2 Steckbrief-Blöcke, 3.4 `read_standard`, 4.5 Verlaufshinweis | Op-Ergebnisse nennen neue Feature-IDs (Test gegen `ScriptedBackend`); Steckbrief-Tests für Passungen/Einstellungen/Quellen/Verlauf; Suite ≥ Basislinie |
| **2 — Sichtbarkeit** | 4.1 Fortschritt, 4.2 Kosten und Fragen am Vorschlag, 4.3 Suchfeld-Absatz | Offscreen-Test: Statuszeile trägt Schritt und Werkzeugtitel; Entscheidungszeile zeigt Schritte/Tokens; zwei neue Suite-Fälle für den Menüort bestehen |
| **3 — Handlungsraum** | 3.3 `read_analysis`, 5.1 Druckeinstellungen **lesen** (nicht setzen — siehe dort), 5.2 `set_print_target` | Bauplan-Ansage 1 eingetragen; jede Analyse mit Herkunftspräfix und Zeitdeckel (Test); neue Suite-Fälle bestehen |
| **4 — Augen und Autopilot** | 3.5 Ansichten, 4.4 automatische Übernahme | Bild erreicht Anthropic-Payload (Test gegen Transport-Attrappe); Backend ohne `supports_images` bekommt reinen Text; Auto-Übernahme greift nur unter allen vier Bedingungen (Test je Bedingung); mehrdeutige Fälle fragen weiterhin 3/3 |
| **5 — Grundform-Skizzen** | 5.3 `shape`-Schema | Bauplan-Ansage 2 eingetragen; Geometrietests je Grundform gegen den Korpus; die vier Skizzen-Suite-Fälle sind gewinnbar und gewonnen |

Begleitend, ohne eigenen Schritt: 2.4 (eine Werkzeuglogik) beginnt vor
Schritt 3 — die neuen Werkzeuge entstehen nur einmal.

> **Die Zeile zu Schritt 3 nannte bis zum 14.08.2026 ein Werkzeug
> `set_print_setting`**, das §5.1 desselben Dokuments schon am 08.08. mit
> Begründung zurückgenommen hatte — und das es folgerichtig nicht gibt: die
> Werkzeugliste in `agent/tools.py` führt `read_analysis`, `read_standard` und
> `set_print_target`, keinen Setzer für Einstellungen. Mit dem Werkzeug fiel
> auch seine Abnahme („Einstellungsänderung reist im Undo mit") — sie prüfte,
> was gar nicht gebaut werden sollte.

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

  > **Eingetreten — und deshalb in der Fernsteuerung abgelehnt.** Im
  > Hauptthread gemessen: 5,3 s. `read_analysis(orientation)` ist über MCP
  > gesperrt, bis die Fernsteuerung einen Arbeiter hat
  > (`ROADMAP.md:3939–3941`). Das ist der einzige Punkt dieses Konzepts, der
  > noch eine Adresse in der Zukunft hat. Einen Teilstand gibt es nicht, der
  > Deckel zählt Dreiecke (siehe 3.3).

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

Jede Zeile dieser Tabelle ist eingelöst — die Nachweise stehen bei den
Abschnitten, auf die sie zeigt. Offen ist allein die letzte, und die war nie
ein Fund, sondern eine Ausbaustufe.

---

## Nachrecherchiert am 19.08.2026

Dieses Dokument war ein Umsetzungsplan, und der Plan ist abgearbeitet. Von
fünfzehn nachgeprüften Aussagen über den eigenen Code waren **zwei noch
richtig, zwölf überholt und eine falsch** — der Haupttext stand durchgehend
im Futur und las sich als offene Arbeit, während ROADMAP alle sechs Schritte
mit Haken führt. Der Kopfvermerk sagt das jetzt vorweg, die Erledigt-Vermerke
darunter sagen es im Einzelnen, samt Stelle im Code.

**Was anders gebaut wurde, als hier stand** — und ohne diese Durchsicht
nirgends stünde:

- `read_analysis(maps)` ist nie entstanden; die Tabelle in 3.3 war die
  letzte Stelle im Repository, die das Werkzeug noch versprach.
- Der Zeitdeckel wurde ein **Dreiecksdeckel**, weil ein Zeitlimit mitten in
  der Rechnung nur mit Gewalt gegen den Thread ginge.
- Der Menüort steht in der **Werkzeugbeschreibung**, nicht im Systemprompt —
  und er muss der volle Pfad sein: Gruppe und Titel allein trafen für 72 von
  77 Ops den falschen Ort.
- Die gemeinsame Werkzeuglogik liegt in `agent/session.py`; ein
  `toolexec.py` gibt es nicht.
- Gerendert wird im Hauptthread, nicht im Arbeiter — VTK im Arbeiter-Thread
  war eine Absturzfamilie.

**Ein Widerspruch war von Anfang an einer:** 3.5 Punkt 2 versprach Bilder
für Ollama, Punkt 3 nahm sie im selben Abschnitt zurück. Gebaut ist Punkt 3.

**Was die Außenrecherche geändert hat.** Die Aussagen über das
Anthropic-Backend hängen an einem Modell, das sich bewegt:

- `DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"` (`llm.py:172`) ist ein
  Alias auf den Schnappschuss `claude-sonnet-4-5-20250929`, Status aktiv,
  vorläufiges Rückzugsdatum „not sooner than September 29, 2026". Ab der
  4.6-Generation gibt es keine Aliase mehr — dort ist die datumslose ID
  selbst der Schnappschuss.
- Der Nachfolger `claude-sonnet-5` kostet weniger und kann mehr: 2 USD
  Eingabe / 10 USD Ausgabe je Mio. Token bei 1 Mio. Kontext gegen 3/15 USD
  bei 200k.
- **`temperature` wird unbedingt mitgesendet** (`llm.py:223`, Vorgabe 0.0).
  Ab Claude Opus 4.7 ist der Parameter abgekündigt und ein
  Nicht-Standardwert liefert einen 400er. Mit Sonnet 4.5 und 4.6 geht es
  weiter; mit jedem neueren Modell scheitert der Aufruf. Das ist keine
  Aufgabe dieses Konzepts, aber wer als Nächstes das Modell wechselt, muss
  es wissen.

Die Zahlen in 2.3 sind mitgewachsen: aus ~99 KB in 86 Schemata wurden
**110 KB in 96 Schemata** (85 Operationen plus elf Zusatzwerkzeuge).

**Nicht belegbar und deshalb offen gelassen:** Die Suite ist gegen Anthropic
weiterhin nicht gefahren — es liegt kein Schlüssel vor. Werkzeugmengen-
Tabelle und Modellvergleich sind seit dem `num_ctx`-Fund nicht wiederholt
worden und bleiben zurückgezogen; keine Zahl in diesem Dokument ersetzt sie.

**Ein Nebenbefund außerhalb dieser Datei:** `3d-agent-bauplan.md:1244` zählt
fünf neue Werkzeuge und nennt vier. Eine Bauplanänderung wird angesagt, nicht
nebenbei gemacht — deshalb steht der Fund hier.
