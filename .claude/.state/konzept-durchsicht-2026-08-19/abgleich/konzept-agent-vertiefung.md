# Abgleich: konzept-agent-vertiefung.md gegen den Stand vom 19.08.2026

Geprüft: alle 15 intern prüfbaren Behauptungen der Sondierung, dazu fünf
Stellen, die beim Lesen des Dokuments zusätzlich auffielen. Die externen
Behauptungen (Anthropic-/Ollama-APIs, Preise) sind hier nicht Gegenstand.

**Kurzfassung:** Das Dokument ist ein Umsetzungsplan, und der Plan ist
vollständig umgesetzt. ROADMAP.md führt alle sechs Schritte (0–5) als
erledigt (`ROADMAP.md:3806–3878`), die Nachher-Messung steht bei
`ROADMAP.md:3888–3895`. Der Haupttext des Konzepts steht dagegen weiter im
Futur („bekommt", „wird", „fehlt") und liest sich als offene Arbeit.

Zählung: **stimmt 2 · überholt 17 · falsch 1 · unprüfbar 0**

---

## Die tragende Abweichung zuerst

### E. Der Vorspann sagt „was fehlt", der Bau ist fertig

**Behauptung** (Zeilen 8–10): „Was fehlt, liegt an drei Stellen — was der
Agent **sieht**, was er **erreichen kann**, und was der Nutzer **von ihm
sieht**. Dieses Konzept schließt alle drei". Ebenso Abschnitt 3 („Heute
arbeitet der Agent halbblind"), 4.1 („Heute: … endloser Balken"), 4.4 („Die
… Übernahme fehlt"), die gesamte Tabelle in 7 und die Abdeckungstabelle in 8.

**Urteil:** überholt.

**Beleg:** `ROADMAP.md:3806–3878` führt alle sechs Schritte mit `[x]`:
Schritt 0 (Basislinie, `invalid`-Kennzahl, `cache_control`, `max_tokens`),
Schritt 1 (Merkmals-IDs im Op-Ergebnis, `read_digest`, vier Steckbrief-Blöcke,
`read_standard`, Verlaufshinweis), Schritt 2 (Fortschritt, Kosten/Fragen,
Menüort), Schritt 3 (`read_analysis`, `set_print_target`), Schritt 4
(Ansichten, automatische Übernahme), Schritt 5 (Grundform-Skizzen als
Beweis). Nachbesserungen dazu am 09.08. (`ROADMAP.md:3912–3950`).

**Stattdessen:** Ein Kopfvermerk über dem Vorspann — „Umgesetzt und
abgenommen (08.08.2026, Nachbesserungen 09.08.); dieses Dokument ist ab hier
Begründungsgedächtnis, keine Arbeitsliste. Der Stand steht in ROADMAP.md,
Abschnitt ‚Die Agent-Vertiefung‘." — und in Abschnitt 7 je Zeile ein
Erledigt-Haken.

---

## Die 15 Behauptungen der Sondierung

### 1. „Alle bisherigen Suite-Messreihen sind ungültig (num_ctx), die neue Basislinie steht aus"

Ort: Vorspann Zeilen 12–17, Abschnitt 2.1.

**Urteil:** überholt.

**Beleg:** `app/core/backends/llm.py:373` `OLLAMA_CONTEXT_TOKENS = 32768`,
gesetzt in jedem Aufruf (`llm.py:475`). Basislinie mit vollem Fenster:
17/33 (`ROADMAP.md:3809–3810`), Nachher-Messung 28/39 = 72 %
(`ROADMAP.md:3890`). Die Werkzeugmengen-Tabelle und der Modellvergleich sind
nicht wiederholt worden — sie bleiben zurückgezogen; das steht so aber
nirgends fortgeschrieben.

**Noch offen und richtig im Dokument:** der Lauf gegen Anthropic steht aus
(„kein Schlüssel hinterlegt", `ROADMAP.md:3909`).

**Stattdessen:** „Die Basislinie ist gefahren: 17/33 mit vollem Fenster
(08.08. Mittag), 28/39 nach der Umsetzung. `num_ctx` steht fest bei 32768
(`llm.py:373`). Werkzeugmengen-Tabelle und Modellvergleich sind bis heute
nicht wiederholt — sie bleiben zurückgezogen. Gegen Anthropic ist die Suite
weiterhin nicht gefahren."

### 2. „Das Ergebnis ersetzt die 8/33 in der ROADMAP als Referenz"

Ort: 2.1.

**Urteil:** überholt (ist geschehen).

**Beleg:** `ROADMAP.md:3888–3895` führt die Tabelle „vorher (33 Fälle) /
nachher (39 Fälle)". Die 8/33 steht nur noch historisch
(`ROADMAP.md:2813`, `:3059`).

**Stattdessen:** „Die 8/33 ist ersetzt; Referenz ist 28/39 (72 %)."

### 3. „Die Suite umfasst 33 Referenzanfragen (15 + 18 Fälle)"

Ort: 2.1, 6 Punkt 3.

**Urteil:** überholt.

**Beleg:** `.venv/Scripts/python.exe -c "from tests.agent_cases import
ALL_CASES; print(len(ALL_CASES))"` → `39`; `CASES` = 21, `CASES_A` = 18.
`AGENTS.md:231` und `3d-agent-bauplan.md:1569` nennen beide 39
(„21 zu Säule C … 18 zu Säule A"). Der Test dazu:
`tests/test_agent_suite.py:156`
`test_the_suite_has_the_size_the_plan_asks_for`.

**Stattdessen:** „Die Suite umfasst 39 Referenzanfragen (21 + 18); die
sechs neuen kamen mit dieser Vertiefung dazu."

### 4. „`TARGET_VALID = 0.95` und `Outcome.invalid` sind toter Code"

Ort: 2.2.

**Urteil:** überholt.

**Beleg:** `tools/run_agent_suite.py:127` `outcome.invalid =
proposal.invalid_calls`, Ausweis je Fall in `:181`, Quote in `:196–201`.
`Proposal` führt `tool_calls`/`invalid_calls`
(`app/core/agent/proposal.py:54,56`). Gemessen: 156/160 = 98 %
(`ROADMAP.md:3893`). Tests: `tests/test_agent_suite.py:319`
`test_invalid_calls_are_counted`, `:707`, `:750`.

**Stattdessen:** „Die Kennzahl misst: `run_case` füllt `invalid` aus
`proposal.invalid_calls`, der Läufer weist sie je Fall und als Quote aus —
98 % im ersten Versuch, Ziel 95 % erfüllt."

### 5. „`max_tokens` ist mit 4096 fest verdrahtet; keine Prompt-Zwischenspeicherung"

Ort: 2.3.

**Urteil:** überholt.

**Beleg:** `app/core/backends/llm.py:185` `max_tokens: int = 8192`, gedeckelt
über `limit = self.max_tokens` (`:215`) im Payload (`:222`). Zwischen-
speicherung: `cache_control` auf dem Systemblock (`:231`) und auf dem
letzten Werkzeugschema (`:239`).

**Stattdessen:** „`max_tokens` ist ein Backend-Parameter mit Vorgabe 8192;
Systemblock und letztes Werkzeugschema tragen `cache_control` (ephemeral)."

### 6. „Die drei Zusatzwerkzeuge sind in `main_window.run_remote` ein zweites Mal implementiert"

Ort: 2.4.

**Urteil:** überholt — zusammengezogen, aber an anderer Stelle als
angekündigt.

**Beleg:** Die Methoden heißen weiter `_remote_report`
(`app/ui/main_window.py:4718`), `_remote_fit` (`:4731`), `_remote_parameter`
(`:4748`), rufen aber die gemeinsamen Funktionen `report_text`, `build_fit`,
`parse_number` aus `app/core/agent/session.py:608,641,624`; die Docstrings
nennen die Konsolidierung ausdrücklich („Konzept 2.4"). Ein
`app/core/agent/toolexec.py` gibt es **nicht** — die gemeinsame Logik liegt
in `session.py`, dazu `standard_text` (`session.py:687`), `find_part_text`
(`:755`) und `analysis_text` (`app/core/agent/analysis.py:66`).

**Stattdessen:** „Die gemeinsame Ausführung liegt in `agent/session.py`
(`report_text`, `parse_number`, `build_fit`, `standard_text`,
`find_part_text`) und `agent/analysis.py`; ein eigenes Modul `toolexec.py`
ist nicht entstanden. Die `_remote_*`-Methoden in `main_window` sind nur noch
Weiterleitungen."

### 7. „`perceive/digest.py` fehlen vier Blöcke"

Ort: 3.2.

**Urteil:** überholt.

**Beleg:** `app/core/perceive/digest.py`: Passungen mit Zustand
(`:66–84`), Druckeinstellungen in einer Zeile (`:87–101`), Quellen
(`:113–119`), Verlauf mit Parametern samt Deckelung (`:272–296`).

**Stattdessen:** „Der Steckbrief führt alle vier Blöcke; die Deckelung der
Verlaufszeile steht in `digest.py` als benannte Grenze."

### 8. „`context.py` baut reinen Text, `backends/llm.py` kennt keinen Bildpfad"

Ort: 3.5.

**Urteil:** überholt.

**Beleg:** `Message.images` (`app/core/backends/llm.py:65`),
`LLMBackend.supports_images` (`:101`), Anthropic `True` (`:200`) mit
base64-`image`-Blöcken (`:264–275`), Ollama fest `False` (`:429`).
`app/core/agent/context.py:66,72` reicht `views` als `images` herein.
Gerendert wird in der Oberfläche: `app/ui/snapshots.py`. Test:
`tests/test_agent_suite.py:578`
`test_views_reach_only_a_backend_that_can_see`.

**Stattdessen:** „`Message` trägt Bildteile, `LLMBackend` hat
`supports_images`, Anthropic baut base64-`image`-Blöcke, Ollama bleibt fest
ohne."

### 9. „`app/ui/snapshots.py` rendert zwei Ansichten offscreen"

Ort: 3.5 Punkt 3.

**Urteil:** stimmt.

**Beleg:** `app/ui/snapshots.py:1–27`, `VIEW_SIZE = (480, 360)`, zwei
Ansichten (isometrisch, von oben), Offscreen-Plotter mit `finally`-Abriss.

**Nachtrag, der im Dokument fehlt:** Gerendert wird im **Hauptthread** in
`propose_async`, nicht im Arbeiter — VTK im Arbeiter-Thread war eine
Absturzfamilie (`ROADMAP.md:3922–3925`, `app/ui/session.py:1077`).

**Stattdessen:** Satz beibehalten, ergänzt um „… im Hauptthread, bevor der
Arbeiter startet; VTK rendert nie im Arbeiter-Thread."

### 10. „`HISTORY_LIMIT = 12` schneidet den Verlauf ohne Hinweis"

Ort: 4.5.

**Urteil:** überholt.

**Beleg:** `app/core/agent/context.py:119–128`: `skipped = len(entries) -
HISTORY_LIMIT`, und bei `> 0` reist die Zeile
„[n ältere Beiträge nicht mitgesendet]" mit. Der Kommentar nennt „Konzept
Agent-Vertiefung 4.5".

**Stattdessen:** „Fallen Beiträge weg, sagt eine Zeile am Anfang des
mitreisenden Verlaufs, wie viele — gebaut in `context.py`."

### 11. „Die UI zeigt Schritte, Tokenzahlen und Rückfragen nicht; kein Fortschritt"

Ort: 4.1, 4.2.

**Urteil:** überholt.

**Beleg:** Fortschritts-Rückruf im Kern: `app/core/agent/session.py:159`
`progress: ProgressFn | None`, gemeldet in `:199` und `:224`, ausgeführt in
`:542`. In der Oberfläche: Statuszeile „Schritt 3/8 — …"
(`app/ui/chat.py:509–512`), Schritte und Token in der Entscheidungszeile
(`:502–515`), Rückfragen aufklappbar (`:196–203`, `:350–357`), erreichte
Grenze ausgeschrieben (`:517–521`). Test: `tests/test_agent_suite.py:523`
`test_the_turn_reports_its_progress`.

**Stattdessen:** „Statuszeile, Schrittzähler, Tokenzahlen, aufklappbare
Rückfragen und der ausgeschriebene Abbruchgrund sind gebaut."

### 12. „Die automatische Übernahme (§26.5) fehlt"

Ort: 4.4.

**Urteil:** überholt.

**Beleg:** `app/core/agent/apply.py:39` `auto_acceptable(proposal,
registry)`; Einstellung `auto_accept_reversible` mit Vorgabe `True`
(`app/ui/settings.py:89–93`, Dialog `app/ui/settings_dialog.py:108–114,
234`); Auslösung in `app/ui/main_window.py:4185`. Übernommen-Leiste in
`app/ui/chat.py:84,316–326`. Nachbesserung 09.08.: der Rückgängig-Knopf
prüfte nicht, welche Transaktion obenauf liegt — jetzt am Dokument gehängt
(`ROADMAP.md:3917–3921`).

**Stattdessen:** „Gebaut: vier Bedingungen in `agent_apply.auto_acceptable`,
Übernommen-Leiste mit Rückgängig-Knopf, abschaltbar über
`auto_accept_reversible` (Vorgabe: an). Der Rückgängig-Knopf prüft selbst,
ob seine Transaktion noch obenauf liegt."

### 13. „Die Werkzeugliste führt `read_analysis`, `read_standard` und `set_print_target`, keinen Setzer für Einstellungen"

Ort: Kasten in 7 (Nachtrag vom 14.08.2026).

**Urteil:** teils stimmt, teils überholt — die Aufzählung ist unvollständig.

**Beleg:** `app/core/agent/tools.py:30–40` führt `ask_user`,
`undo_transaction`, `add_parameter`, `set_parameter`, `add_fit`,
`read_report`, `find_part`, **`read_digest`**, `read_standard`,
`read_analysis`, `set_print_target`. Ein `set_print_setting` gibt es
tatsächlich nicht — das stimmt und ist im Bauplan begründet
(`3d-agent-bauplan.md:1233–1239`).

**Stattdessen:** „… die Werkzeugliste in `agent/tools.py` führt
`read_digest`, `read_analysis`, `read_standard` und `set_print_target`,
keinen Setzer für Einstellungen."

### 14. „Skizzen-Ops tragen seit P13 `shape`/`length`/`width`/`corners`; der Beweis steht als Test"

Ort: 5.3.

**Urteil:** stimmt.

**Beleg:** `app/core/sketch/shapes.py:1–11` (Rechteck, Langloch, Kreis,
Vieleck, exakt konstruiert, Solver bestätigt). Test:
`tests/test_agent_suite.py:841`
`test_the_sketch_parameter_stays_locked_but_shapes_pass`. Bauplan:
`3d-agent-bauplan.md:1412–1415`.

### 15. „Vier Bauplan-Ergänzungen (§26.2, §30.1, §35/§40, §23) stehen noch aus"

Ort: 6.

**Urteil:** überholt — alle vier sind eingetragen.

**Beleg:**
- §26.2: `3d-agent-bauplan.md:1228–1231` (`read_digest`, `read_standard`,
  `read_analysis`, `set_print_target`) plus die Begründung, warum es keinen
  Setzer gibt (`:1233–1239`).
- §30.1: `:1412–1415` („Der Agent erzeugt Skizzen ausschließlich über
  benannte Grundformen").
- §35: `:1569` „39 Referenzanfragen — 21 zu Säule C …, 18 zu Säule A".
- §23: `:1065–1069` — Ansichten „erreichen nur ein Backend, das Bilder
  versteht; an jedes andere entfallen sie ersatzlos".

**Stattdessen:** „Alle vier Ergänzungen sind eingetragen (§26.2, §30.1, §35,
§23)."

---

## Was beim Lesen zusätzlich auffiel

### A. `read_analysis(maps)` ist nie gebaut worden — und nichts sagt das

Ort: Tabelle in 3.3, Zeile `maps` („die aggregierten Kennzahlen der
Analysekarten … `perceive/maps.py`").

**Urteil:** überholt (anders gebaut), ohne Vermerk irgendwo.

**Beleg:** `app/core/agent/analysis.py:43`
`ANALYSIS_KINDS = ("printability", "estimate", "advice", "orientation")`;
das Werkzeugschema führt dasselbe Enum (`app/core/agent/tools.py:304`), und
die Beschreibung nennt vier Arten (`:293–297`). Der Bauplan nennt ebenfalls
nur vier (`3d-agent-bauplan.md:1230`). In `ROADMAP.md` steht zu Schritt 3
(`:3846–3850`) nur die Aufzählung der vier — die Rücknahme von `maps` ist
nirgends begründet.

**Stattdessen:** Zeile `maps` aus der Tabelle streichen und darunter einen
Satz: „`maps` (Analysekarten) ist bei der Umsetzung entfallen — die
Kennzahlen der Karten stecken in `printability`; als eigene Art hätte sie
keinen zusätzlichen Zug beantwortet." (Oder, falls das nicht der Grund war:
den wirklichen nennen.) So oder so ist die Tabelle die einzige Stelle im
Repository, die das Werkzeug noch verspricht.

### B. Aus dem „harten Zeitdeckel" wurde ein Dreiecksdeckel

Ort: 3.3, erste Regel („mit hartem Zeitdeckel je Aufruf … Ein
überschrittener Deckel ist ein Ergebnis (‚Analyse nach n s abgebrochen —
Teilstand: …‘), kein Fehler").

**Urteil:** überholt.

**Beleg:** `app/core/agent/analysis.py:45–48`: „Ab dieser Dreieckszahl wird
nicht im Zug gerechnet. Der Deckel ist hart und vorab prüfbar — ein
Zeitlimit mitten in einer laufenden Rechnung gäbe es nur mit Gewalt gegen
den Thread." `TRIANGLE_LIMIT = 500_000`. Die Orientierungssuche fährt 24
Kandidaten mit festem Startwert 7 (`:51–58`). Einen Teilstand nach
Zeitablauf gibt es nicht. `ROADMAP.md:3849` nennt das ausdrücklich: „harter
Dreiecksdeckel statt Zeitgewalt".

**Stattdessen:** „Gerechnet wird auf der Arbeitskopie, gedeckelt über die
Dreieckszahl (`TRIANGLE_LIMIT`, vorab prüfbar) statt über die Zeit; ein
Zeitlimit mitten in der Rechnung ginge nur mit Gewalt gegen den Thread. Zu
große Szenen bekommen eine Absage mit Grund, keinen Teilstand."

### C. 3.5 Punkt 2 widerspricht 3.5 Punkt 3 — und Punkt 3 ist gebaut

Ort: 3.5 Punkt 2 („`OllamaBackend` füllt das `images`-Feld, aber nur wenn
das gewählte Modell Vision beherrscht — die Fähigkeit wird wie
`ollama_tool_check` einmal geprüft") gegen Punkt 3 („Ollama bleibt vorerst
fest ohne Bilder").

**Urteil:** falsch (Widerspruch im Dokument, schon beim Schreiben).

**Beleg:** `app/core/backends/llm.py:429–434`: `supports_images` gibt fest
`False` zurück, mit dem Vermerk „Zieht eines ein, gehört hier eine Prüfung
wie `ollama_tool_check` hin". `grep -n images app/core/backends/llm.py`
zeigt keine Stelle, an der Ollama ein `images`-Feld füllt.

**Stattdessen:** Punkt 2 auf Anthropic beschränken: „`AnthropicBackend` baut
daraus `image`-Blöcke (base64). `OllamaBackend` meldet `supports_images =
False` und bekommt deshalb nie Bildteile; eine Fähigkeitsprüfung wie
`ollama_tool_check` gehört dorthin, sobald ein Vision-Modell gemessen ist."

### D. Die Zahlen in 2.3 sind gewachsen

Ort: 2.3 („~99 KB Werkzeugschemata … bei jedem der bis zu 8 Schritte neu
über die Leitung").

**Urteil:** überholt.

**Beleg:** heute 96 Schemata (85 Ops plus 11 Zusatzwerkzeuge), 110 KB
JSON — gemessen mit
`.venv/Scripts/python.exe -c "import json; from app.core.bootstrap import
load_operations; from app.core.registry import REGISTRY; from
app.core.agent.tools import tool_schemas; load_operations(); s =
tool_schemas(REGISTRY); print(len(s), len(json.dumps(s,
ensure_ascii=False))/1024)"` → `96 110.2`. `MAX_STEPS = 8` und
`MAX_TOKENS = 120_000` stehen weiter (`app/core/agent/session.py:78–79`).
Neu gehen sie nur beim ersten Schritt über die Leitung — ab dem zweiten
greift `cache_control`.

**Stattdessen:** Vergangenheitsform und aktuelle Zahl: „Vor der
Zwischenspeicherung gingen ~99 KB Werkzeugschemata bei jedem der bis zu acht
Schritte neu über die Leitung; heute sind es 110 KB (96 Schemata), und ab
Schritt 2 liegt das stabile Präfix im Zwischenspeicher."

### F. Nebenbefund außerhalb der Konzeptdatei

`3d-agent-bauplan.md:1244` sagt „Die **fünf** Werkzeuge ab `read_digest`
kamen mit der Agent-Vertiefung dazu" — aufgezählt sind vier
(`read_digest`, `read_standard`, `read_analysis`, `set_print_target`). Das
ist der letzte Rest des zurückgenommenen `set_print_setting`; die Zahl
gehört auf vier korrigiert. Nicht Gegenstand dieses Abgleichs, aber derselbe
Ursprung wie der Nachtrag vom 14.08.

---

## Was unverändert richtig ist

- Die Nicht-Ziele aus Abschnitt 1 gelten alle noch: kein Text-Streaming
  (`app/core/backends/llm.py:471` `"stream": False`), alle Ops in der
  Werkzeugliste (96 Schemata ≥ 85 Ops), keine neue Abhängigkeit, keine
  Koordinaten aus dem Agenten (`tests/test_agent_suite.py:841`).
- 5.1 (Druckeinstellungen: lesen ja, setzen nein) — im Bauplan als Festlegung
  angekommen (`3d-agent-bauplan.md:1233–1239`).
- 5.4 (kein Export-, kein Redo-Werkzeug) — in `agent/tools.py:30–40` gibt es
  weder das eine noch das andere.
- Die drei absichtlich mehrdeutigen Fälle sind weiterhin drei
  (`tests/agent_cases.py`, `AMBIGUOUS`), und sie fragen 3/3
  (`ROADMAP.md:3892`).
- Der offene Rest aus 7 („Risiken"): `read_analysis(orientation)` ist in der
  Fernsteuerung abgelehnt, bis sie einen Arbeiter hat — 5,3 s im
  Hauptthread gemessen (`ROADMAP.md:3939–3941`). Das ist der einzige Punkt
  des Konzepts, der noch eine Adresse in der Zukunft hat.
