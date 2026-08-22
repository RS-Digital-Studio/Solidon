# Sondierung: konzept-agent-vertiefung.md

**Titel:** Konzept — Der Agent wird Teil der Anwendung
**Stand laut Dokument:** Stand 08.08.2026
**Zweck:** Konzept, das die drei Lücken der Agentenschicht (was der Agent sieht, was er erreichen kann, was der Nutzer von ihm sieht) samt Fundament schließt — mit Bauplan-Ansagen, sechs Umsetzungsschritten und Abnahmekriterien.

**Alterung:** 5/5 — Das Dokument ist eine Ist-Soll-Gegenüberstellung mit Umsetzungsplan; es enthält bereits mehrere nachträgliche Korrekturen (08.08. und 14.08.2026), d. h. es wird während der Umsetzung laufend überholt. Zusätzlich hängen tragende Aussagen an Suite-Messwerten, die selbst als ungültig markiert sind, an Codezuständen (Dateien, Konstanten, fehlende Werkzeuge) und an fremden APIs (Anthropic Prompt Caching, Ollama num_ctx/images), die sich unabhängig ändern.

## Gliederung

- Konzept — Der Agent wird Teil der Anwendung (Titel/Vorspann)
- 1. Ziele und Nicht-Ziele
- 2. Fundament: erst messen, dann bauen
- 3. Wahrnehmung: der Agent sieht, was der Nutzer sieht
- 4. Sichtbarkeit: der Nutzer sieht, was der Agent tut
- 5. Handlungsraum: der Agent erreicht dieselben Hebel wie die Menüs
- 6. Bauplan-Änderungen — die Ansage
- 7. Reihenfolge und Abnahme
- 8. Abdeckung — jeder Fund der Durchsicht hat eine Adresse

## Extern prüfbare Behauptungen (12)

- **[hoch/api] Anthropic Messages API — Prompt Caching (cache_control ephemeral)** — cache_control (ephemeral) auf dem letzten Werkzeugschema und dem Systemblock lässt alles Stabile im Zwischenspeicher — kein SDK nötig, zwei Felder im Payload  
  _Ort:_ 2.3 Zwischenspeicherung und Antwortbudget im Anthropic-Backend
- **[hoch/preis] Anthropic Messages API — Cache-Rabatt/Latenz** — Wirkung: Schritt 2 bis 8 eines Zuges kosten einen Bruchteil, die Latenz fällt spürbar  
  _Ort:_ 2.3
- **[mittel/api] Anthropic Messages API — max_tokens-Obergrenze je Modell** — max_tokens wird Parameter des Backends mit Vorgabe 8192  
  _Ort:_ 2.3
- **[hoch/api] Anthropic Messages API — Bildeingabe, base64-Blöcke** — AnthropicBackend baut image-Blöcke (base64)  
  _Ort:_ 3.5 Punkt 2
- **[hoch/api] Ollama API — images-Feld in /api/chat** — OllamaBackend füllt das images-Feld, aber nur wenn das gewählte Modell Vision beherrscht  
  _Ort:_ 3.5 Punkt 2
- **[hoch/api] Ollama — Option num_ctx / Kontextfenster** — Unter num_ctx 32768 fiel der Systemprompt still weg; die Läufe fahren mit num_ctx = 32768  
  _Ort:_ Vorspann und 2.1
- **[mittel/funktionsumfang] Ollama — Vorgabemodell des Projekts, Vision-Fähigkeit** — Das Vorgabemodell von Ollama ist kein Vision-Modell, Ollama bleibt vorerst fest ohne Bilder  
  _Ort:_ 3.5 Punkt 3
- **[mittel/funktionsumfang] Ollama — Tool-/Vision-Unterstützung je Modell** — Die Vision-Fähigkeit wird wie ollama_tool_check einmal geprüft — d. h. Ollama-Modelle unterscheiden sich in Werkzeug- und Bildfähigkeit  
  _Ort:_ 3.5 Punkt 2
- **[mittel/preis] Anthropic / Ollama — Token-Preise je Modell** — Eine Geldrechnung des Kostendeckels braucht Preisdaten je Modell und bleibt Ausbaustufe  
  _Ort:_ 8 Abdeckung, letzte Zeile
- **[mittel/api] Anthropic Messages API — Tool-Schema-Übertragung je Anfrage** — ~99 KB Werkzeugschemata und Systemprompt gehen bei jedem der bis zu 8 Schritte neu über die Leitung  
  _Ort:_ 2.3
- **[niedrig/preis] Anthropic API — kostenpflichtiger Zugang/API-Schlüssel** — Ein Lauf gegen Anthropic setzt einen Schlüssel voraus („wenn ein Schlüssel da ist")  
  _Ort:_ 2.1
- **[niedrig/funktionsumfang] Anthropic Messages API / Ollama — Streaming-Unterstützung** — Die Backends können Text-Streaming nicht einheitlich  
  _Ort:_ 1 Nicht-Ziele

## Intern prüfbare Behauptungen (15)

- **[hoch]** Alle bisherigen Suite-Messreihen sind ungültig (num_ctx-Fund); die Werkzeugmengen-Tabelle und der Modellvergleich gelten als zurückgezogen  
  _Prüfen:_ ROADMAP.md, Abschnitt Agenten-Suite/Durchsichten: steht dort inzwischen eine neue Basislinie? tools/run_agent_suite.py auf num_ctx-Vorgabe prüfen  
  _Ort:_ Vorspann, 2.1
- **[hoch]** Die 8/33 in der ROADMAP ist die aktuelle Referenz und soll ersetzt werden  
  _Prüfen:_ ROADMAP.md nach „8/33" bzw. aktuellem Suite-Ergebnis durchsuchen  
  _Ort:_ 2.1
- **[hoch]** Die Suite umfasst 33 Referenzanfragen (15 + 18 Fälle)  
  _Prüfen:_ tools/run_agent_suite.py bzw. tests/test_agent_suite.py: Fälle zählen; AGENTS.md nennt 39 Referenzanfragen — Widerspruch prüfen  
  _Ort:_ 2.1, 6 Punkt 3
- **[hoch]** TARGET_VALID = 0.95 und Outcome.invalid sind toter Code, run_case füllt invalid nie  
  _Prüfen:_ grep TARGET_VALID / invalid in tools/run_agent_suite.py  
  _Ort:_ 2.2
- **[hoch]** max_tokens ist mit 4096 fest verdrahtet, Zugbudget 120000  
  _Prüfen:_ grep max_tokens in app/core/backends/ (Anthropic-Backend)  
  _Ort:_ 2.3
- **[hoch]** Die drei Zusatzwerkzeuge sind in main_window.run_remote ein zweites Mal implementiert (_remote_report, _remote_parameter, _remote_fit)  
  _Prüfen:_ grep _remote_report in app/ui/main_window.py; existiert app/core/agent/toolexec.py?  
  _Ort:_ 2.4
- **[hoch]** perceive/digest.py fehlen vier Blöcke: Passungen, Druckeinstellungen, Quellen, Verlauf mit Parametern  
  _Prüfen:_ app/core/agent oder app/core/perceive/digest.py lesen; Tests in tests/ nach Steckbrief-Blöcken suchen  
  _Ort:_ 3.2
- **[hoch]** context.py baut reinen Text, backends/llm.py kennt keinen Bildpfad; Message trägt keine Bildteile, LLMBackend hat kein supports_images  
  _Prüfen:_ grep supports_images und image in app/core/agent/context.py und app/core/backends/llm.py  
  _Ort:_ 3.5
- **[mittel]** app/ui/snapshots.py rendert zwei Ansichten offscreen (bei der Umsetzung 08.08.2026 korrigiert)  
  _Prüfen:_ Existenz und Inhalt von app/ui/snapshots.py prüfen  
  _Ort:_ 3.5 Punkt 3
- **[mittel]** HISTORY_LIMIT = 12 schneidet den Verlauf ohne Hinweis  
  _Prüfen:_ grep HISTORY_LIMIT in app/core/agent/  
  _Ort:_ 4.5
- **[mittel]** Die UI zeigt Schritte, Tokenzahlen und Rückfragen des Proposal nicht; kein Fortschritt, nur endloser Balken  
  _Prüfen:_ app/ui/chat.py auf Statuszeile/Tokenanzeige lesen  
  _Ort:_ 4.1, 4.2
- **[mittel]** Die automatische Übernahme (§26.5) fehlt; die UI sagt grundsätzlich nein, nur im Docstring von chat.py dokumentiert  
  _Prüfen:_ app/ui/chat.py: Docstring und Übernahme-Logik; Einstellung/Präferenz vorhanden?  
  _Ort:_ 4.4
- **[hoch]** Werkzeugliste in agent/tools.py führt read_analysis, read_standard und set_print_target, keinen Setzer für Einstellungen; read_digest ist geplant  
  _Prüfen:_ grep register/tool-Namen in app/core/agent/tools.py  
  _Ort:_ 5.1, 5.2, Kasten in 7
- **[mittel]** Skizzen-Ops tragen seit P13 shape/length/width/corners; app/core/sketch/shapes.py existiert; Beweis als Test in tests/test_agent_suite.py  
  _Prüfen:_ app/core/sketch/shapes.py lesen; grep shape in den Skizzen-Op-Schemata; Test in tests/test_agent_suite.py laufen lassen  
  _Ort:_ 5.3
- **[hoch]** Vier Bauplan-Ergänzungen (§26.2, §30.1, §35/§40, §23) stehen noch aus  
  _Prüfen:_ 3d-agent-bauplan.md: §26.2 Werkzeugliste, §30.1 shape-Schema, §35/§40 Suite-Umfang, §23 Vermerk prüfen  
  _Ort:_ 6