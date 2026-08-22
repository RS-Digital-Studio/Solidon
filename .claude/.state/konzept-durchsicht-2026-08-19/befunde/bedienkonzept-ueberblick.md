# Sondierung: .claude/bedienkonzept-ueberblick.md

**Titel:** Überblick über einen langen Agentenlauf
**Stand laut Dokument:** kein ausgewiesenes Stand-Datum; einziges Datum im Text: „der Übersetzungsrunde vom 31.07. bis 01.08.2026"
**Zweck:** Bedienkonzept-Entwurf für Claude Code: sechs Konzepte (Sitzungsleiste, Kapitel, /stand, Sitzungsbericht, Bekannt-rot, Fremde Hand), die einen langen Agentenlauf beobachtbar machen sollen, hergeleitet an einer echten Übersetzungssitzung.

**Alterung:** 4/5 — Der Kern des Dokuments — die sechs Konzepte und ihre Begründung — ist zeitlos. Was schnell altert, ist die Schlusstabelle §10: sie behauptet einen Umsetzungsgrad, der sich mit jedem neuen Skill, jeder AGENTS.md-Regel und jeder Claude-Code-Fassung verschiebt (Sitzungsleiste, Kapitelmarken). Dazu die harten Zahlen der Bezugssitzung (21 Commits, 1926 grün / 1 rot, 289 Dateien), die als Beleg dienen und schon heute überholt sein dürften. Das Dokument trägt kein ausgewiesenes Stand-Datum, was das Altern unsichtbar macht.

## Gliederung

- Überblick über einen langen Agentenlauf (Titel)
- 1. Die Analogie, aus der alles folgt
- 2. Die vier Fragen
- 3. Konzept A — Die Sitzungsleiste
- 4. Konzept B — Kapitel
- 5. Konzept C — /stand
- 6. Konzept D — Der Sitzungsbericht
- 7. Konzept E — Bekannt-rot
- 8. Konzept F — Fremde Hand
- 9. Was nicht gebaut wird
- 10. Was davon heute schon geht
- 11. Der Prüfstein

## Extern prüfbare Behauptungen (7)

- **[hoch/funktionsumfang] Claude Code (Anthropic)** — Kapitelmarken sind in Claude Code bereits als Werkzeug vorhanden („das Werkzeug gibt es, benutzt wurde es nicht") und ohne Änderung am Werkzeug nutzbar  
  _Ort:_ §10, Tabellenzeile „B Kapitel"
- **[hoch/funktionsumfang] Claude Code (Anthropic)** — Eine Sitzungsleiste (drei feste Zeilen über der Eingabezeile mit Fortschritt und Abbrechen) gibt es in Claude Code nicht; Konzept A „braucht Claude Code selbst" und ist das einzige, was nicht im Repo umsetzbar ist  
  _Ort:_ §3 und §10, Tabellenzeile „A Sitzungsleiste"
- **[hoch/funktionsumfang] Claude Code (Anthropic)** — Fünf von sechs Konzepten lassen sich allein in .claude/ dieses Projekts umsetzen, also mit dem heutigen Funktionsumfang von Claude Code (Skills, Regeln, Scratchpad)  
  _Ort:_ §10, Schlusssatz
- **[mittel/funktionsumfang] Claude Code (Anthropic) — Transkriptansicht** — Ein Inhaltsverzeichnis links, Trennlinien im Transkript, Zuklappen von Kapiteln und „alle zu" sind als Bedienung möglich bzw. angenommene Oberfläche der Sitzung  
  _Ort:_ §4, Abläufe „Kapitel entsteht" / „Nutzer sucht eine Stelle"
- **[mittel/api] Claude Code Skills / Slash-Befehle** — Slash-Befehle lassen sich als Skills neben /pruefen und /roadmap anlegen (/stand, /bericht)  
  _Ort:_ §10, Zeilen C und D
- **[mittel/funktionsumfang] Claude Code Scratchpad-Verzeichnis** — Der Scratchpad steht als Ablage für eine Testbasislinie über die Sitzung hinweg zur Verfügung  
  _Ort:_ §10, Zeile E
- **[niedrig/funktionsumfang] Claude Code (parallele Sitzungen)** — Zwei parallele Sitzungen auf einem Arbeitsbaum sind hier der Normalfall  
  _Ort:_ §8, erster Absatz

## Intern prüfbare Behauptungen (11)

- **[mittel]** Die Bezugssitzung umfasste 21 Commits, 289 Dateien, 16 269 eingefügte Zeilen (an anderer Stelle +16 269 / −4 820)  
  _Prüfen:_ git log --since=2026-07-31 --until=2026-08-02 --oneline und git diff --shortstat über diesen Bereich  
  _Ort:_ Kopfabsatz und §5-Beispielblock
- **[hoch]** Testlage der Bezugssitzung: 1926 grün, 1 rot (Leistungsmessung unter Fremdlast, rot seit Sitzungsbeginn)  
  _Prüfen:_ .venv\Scripts\python.exe -m pytest -q — Gesamtzahl und rote Tests heute gegenprüfen, Leistungstest mit -m performance  
  _Ort:_ §3 Zeile 3, §5 Block, §7
- **[niedrig]** Die Sitzung hatte elf Kapitel entlang der Pakete app/core/scene, geom, brep+registry+agent, perceive+slice, knowledge, ui+cli, viermal tests/  
  _Prüfen:_ gegen git log der Übersetzungsrunde und die Commit-Meldungen abgleichen  
  _Ort:_ §4, erster Absatz
- **[mittel]** Kapitelmarken wurden in Solidon-Sitzungen bisher nicht gesetzt („benutzt wurde es nicht")  
  _Prüfen:_ aktuelle Sitzungspraxis bzw. .claude/-Vorgaben prüfen; keine Repo-Datei fordert Kapitelmarken  
  _Ort:_ §10, Zeile B
- **[hoch]** /stand existiert noch nicht, sondern ist als Skill vorgeschlagen  
  _Prüfen:_ ls .claude/skills — heute vorhanden: bauplan, liefern, neue-op, neuer-baustein, neues-druckteil, pruefen, regelcheck, roadmap; kein stand  
  _Ort:_ §5 und §10, Zeile C
- **[hoch]** /bericht existiert noch nicht, sondern ist als Skill vorgeschlagen  
  _Prüfen:_ ls .claude/skills — kein bericht-Skill vorhanden  
  _Ort:_ §6 und §10, Zeile D
- **[hoch]** Bekannt-rot-Basislinie ist nicht gebaut; /pruefen vergleicht keine Basislinie  
  _Prüfen:_ .claude/skills/pruefen lesen — enthält es einen Basislinien-Vergleich?  
  _Ort:_ §7 und §10, Zeile E
- **[hoch]** „Fremde Hand" ist noch keine Regel in AGENTS.md und keine Prüfung in /regelcheck  
  _Prüfen:_ grep -i "fremde" AGENTS.md und .claude/skills/regelcheck; AGENTS.md führt derzeit 22 Regeln, keine davon zu fremden Pfaden  
  _Ort:_ §8 und §10, Zeile F
- **[mittel]** Die Regeln zur Wartezeit stammen aus .claude/rules/oberflaeche.md, Bauplan §2.8 und §15.3, samt Wartezeit-Tabelle (unter 2 s / bis 30 s / darüber)  
  _Prüfen:_ .claude/rules/oberflaeche.md und 3d-agent-bauplan.md §2.8, §15.3 lesen und Schwellen abgleichen  
  _Ort:_ §1
- **[mittel]** Drei Nebenfunde der Bezugssitzung offen: kaputte Escape-Sequenz (riss vier Regeltests), unterbestimmte Skizze als Konzeptfrage, rote Leistungsmessung unter Fremdlast  
  _Prüfen:_ ROADMAP.md unter den Funden der Durchsichten suchen; Regeltests und Leistungstests laufen lassen  
  _Ort:_ §6, Absatz nach der Liste
- **[hoch]** Der Entwurfsstatus insgesamt: laut CLAUDE.md „noch nicht Praxis", der Umsetzungsstand steht in der Schlusstabelle  
  _Prüfen:_ §10-Tabelle Zeile für Zeile gegen .claude/skills, AGENTS.md und ROADMAP.md prüfen  
  _Ort:_ §10 (in CLAUDE.md als „Schlusstabelle" referenziert)