# Faktenkarten für `bedienkonzept-ueberblick.md`

Recherchiert am 19.08.2026. Jede Karte trägt ihre Quelle. Was nicht gefunden
wurde, steht unter „Nicht belegbar“ — das ist kein Freibrief, es plausibel
zu ergänzen, sondern der Grund, es im Konzept offen zu lassen.

> **Zuerst `KORREKTUR-claude-code.md` lesen.** Dieser Cluster schließt
> mehrfach von „nicht dokumentiert“ auf „existiert nicht“ und ist in drei
> Punkten nachweislich falsch.

## claude-code

_Claude Code-Features: Bedienkonzepte vom Juli/August 2026 vs. heutiger Funktionsumfang_

- **Kapitelmarken** — Kapitelmarken existieren in Claude Code, werden aber in der aktuellen Dokumentation nicht als eigenständiges Feature beschrieben. Sie werden in interactive-mode.md erwähnt, aber nur im Kontext anderer Features wie Session-Recap und Transcript-Viewer.
  · Stand: 2026-08 · Sicherheit: mehrere_quellen
  · Anmerkung: Die Bedienkonzepte scheinen mit einer experimentellen Implementierung gerechnet zu haben, die bis dahin vollständig integriert sein würde. Aktuell: ungenutzt oder nicht als Feature exponiert.
  · https://code.claude.com/docs/en/interactive-mode.md
  · https://code.claude.com/docs/en/commands
- **Sitzungsleiste (3 Zeilen über Eingabe)** — Eine persistente Sitzungsleiste mit Fortschrittsanzeige und Abbrechen-Button über der Eingabezeile existiert NICHT. Agent view (`claude agents`) bietet Überwachung von Background-Sitzungen, aber das ist ein separater UI-Bereich, nicht eine Leiste über der Eingabezeile.
  · Stand: 2026-08 · Sicherheit: belegt
  · Anmerkung: Das Konzept beschrieb eine UI-Komponente, die nie in dieser Form gebaut wurde.
  · https://code.claude.com/docs/en/agent-view.md
  · https://code.claude.com/docs/en/interactive-mode.md
- **Inhaltsverzeichnis links, Trennlinien, Zuklappen** — Ein Inhaltsverzeichnis mit Kapiteln, Trennlinien im Transkript und Zuklapp-Funktionalität ist in der Dokumentation NICHT beschrieben.
  · Stand: 2026-08 · Sicherheit: belegt
  · Anmerkung: Die Transkript-Viewer-Features (Ctrl+O) bieten Darstellungsoptionen, aber keine Kapitelhierarchie oder Zuklapp-UI.
  · https://code.claude.com/docs/en/interactive-mode.md
  · https://code.claude.com/docs/en/fullscreen.md
- **Fünf von sechs Konzepte in .claude/ umsetzbar** — Überwiegend richtig: Skills (.claude/skills/), Regeln (.claude/rules/), Hooks (settings.json), Agents (.claude/agents/), und Workflows (.claude/workflows/) sind alle in .claude/ konfigurierbar. Die Sitzungsleiste jedoch ist NICHT in dieser Form umgesetzt.
  · Stand: 2026-08 · Sicherheit: belegt
  · Anmerkung: Das Konzept zählte 6 Dinge, von denen 5 umgesetzt sind. Die Sitzungsleiste war eins der 6, ist aber nicht gebaut.
  · https://code.claude.com/docs/en/claude-directory.md
  · https://code.claude.com/docs/en/skills.md
  · https://code.claude.com/docs/en/hooks.md
- **argument-hint in Skill-Metadaten** — `argument-hint` existiert NICHT als Feld in Skill-Frontmatter oder Plugin-Manifest. Die verfügbaren Skill-Felder sind: name, description, tags, confirmation, auto-invoke, input (String), context, mcp_servers, mcp_tools, etc.
  · Stand: 2026-08 · Sicherheit: belegt
  · Anmerkung: Das Bedienkonzept beschrieb ein Feature, das nicht existiert. Argument-Hinweise müssen in der Skill-Dokumentation (SKILL.md Body) selbst stehen.
  · https://code.claude.com/docs/en/skills.md
  · https://code.claude.com/docs/en/plugins-reference.md
- **Warnung ‚The task tools haven't been used recently'** — Diese spezifische Warnung ist in der Claude Code-Dokumentation NICHT dokumentiert. Es gibt keine Hook oder Nachricht mit diesem Wortlaut.
  · Stand: 2026-08 · Sicherheit: belegt
  · Anmerkung: Das Konzept schrieb Meldungen vor, die Claude Code nicht ausgibt.
  · https://code.claude.com/docs/en/hooks.md
  · https://code.claude.com/docs/en/interactive-mode.md
  · https://code.claude.com/docs/en/commands.md
- **PostToolUse-Hook-Meldung ‚modified X after your edit'** — Der PostToolUse-Hook gibt KEINE Meldung des Wortlauts ‚PostToolUse hook modified X after your edit (likely a formatter)' aus. PostToolUse läuft nach Toolausführung und kann ein systemMessage zurückgeben, aber dieses Format ist nicht dokumentiert.
  · Stand: 2026-08 · Sicherheit: belegt
  · Anmerkung: Das Konzept beschrieb ein spezifisches Verhalten von PostToolUse, das nicht nachweisbar ist.
  · https://code.claude.com/docs/en/hooks.md
  · https://code.claude.com/docs/en/hooks-guide.md
- **Dateiänderungs-Meldung ohne Verursacher** — Claude Code meldet ‚the file had been modified on disk since you last read it' NICHT. Es gibt einen FileChanged-Hook, aber die spezifische Meldung mit diesem Wortlaut ist nicht dokumentiert.
  · Stand: 2026-08 · Sicherheit: belegt
  · Anmerkung: FileChanged-Hook existiert, aber die Meldung ist nicht dokumentiert und der Verursacher ist in hooks ja über den Hook selbst erkennbar.
  · https://code.claude.com/docs/en/hooks.md
  · https://code.claude.com/docs/en/tools-reference.md
- **Hintergrundaufgaben via run_in_background** — Es gibt Background Bash commands (`Ctrl+B` zum Hintergrundbetrieb) und Background Subagents, aber keine dokumentierte API oder Funktion namens `run_in_background`. Im Agent SDK (Python/TypeScript) gibt es native Unterstützung für Background-Aufgaben, aber nicht unter diesem Namen.
  · Stand: 2026-08 · Sicherheit: mehrere_quellen
  · Anmerkung: Hintergrundaufgaben existieren, aber unter anderem Namen. CLI: Ctrl+B oder Claude-Anfrage; Agent SDK: native API in Python/TypeScript.
  · https://code.claude.com/docs/en/interactive-mode.md#background-bash-commands
  · https://code.claude.com/docs/en/headless.md#background-tasks-at-exit
  · https://code.claude.com/docs/en/agent-view.md
- **MCP-Server-Verbindungsmeldungen** — MCP-Server senden KEINE dokumentierten Meldungen für Connect/Disconnect/Reconnect oder Anmeldepflicht. Die Dokumentation erwähnt elicitation (Benutzerinteraktion anfordern), aber nicht wiederholte Verbindungsmeldungen.
  · Stand: 2026-08 · Sicherheit: belegt
  · Anmerkung: Das Konzept beschrieb Verhalten, das nicht dokumentiert ist. Claude Code verwaltet MCP-Verbindungen im Hintergrund.
  · https://code.claude.com/docs/en/mcp.md
  · https://code.claude.com/docs/en/mcp-quickstart.md
- **Scratchpad über Sitzungen hinweg verfügbar** — Der Scratchpad NICHT über Sitzungen hinweg verfügbar. Claude Code speichert Dateien in `~/.claude/projects/<project>/scratchpad/` oder ähnlich, aber diese werden nach der konfigurierten `cleanupPeriodDays` (Standard: 30 Tage) gelöscht. Der Scratchpad ist sitzungsspezifisch.
  · Stand: 2026-08 · Sicherheit: belegt
  · Anmerkung: Scratchpad-Dateien werden wie Transkripte behandelt und nicht dauerhaft zwischen Sitzungen beibehalten.
  · https://code.claude.com/docs/en/claude-directory.md#cleaned-up-automatically
  · https://code.claude.com/docs/en/settings.md#available-settings
- **Zwei parallele Sitzungen auf einem Arbeitsbaum** — Zwei parallele Sitzungen auf EINEM Worktree sind NICHT der Normalfall. Worktrees isolieren Edits, und jede Sitzung braucht ihren eigenen Worktree oder eine separate Branch. Multiple Sitzungen auf demselben Worktree ohne Isolation führen zu Dateikonflikten.
  · Stand: 2026-08 · Sicherheit: belegt
  · Anmerkung: Worktrees existieren gerade um Isolation zu erreichen. Das Desktop-App erstellt auto für jede Sitzung einen eigenen Worktree.
  · https://code.claude.com/docs/en/worktrees.md
  · https://code.claude.com/docs/en/sessions.md

**Nicht belegbar:**
- Spezifische Formulierungen von Fehlermeldungen wie ‚The task tools haven't been used recently' oder ‚PostToolUse hook modified X after your edit' könnten in älteren Builds vorhanden gewesen sein und seither entfernt wurden.
- Das genaue Erscheinungsdatum bestimmter Features wie Chapter Markers in einer experimentellen Fassung lässt sich aus der Dokumentation nicht exakt bestimmen.
- Ob die Bedienkonzepte auf intern verfügbaren Branches oder Experimental-Features beruhten, lässt sich aus der öffentlichen Dokumentation nicht sagen.

**Neu seit Anfang August:**
- Agent View ist ein neuer und sehr umfangreicher UI-Bereich für Background-Session-Überwachung (seit v2.1.x), der viel mehr als die geplante ‚Sitzungsleiste' leistet – aber auf einer anderen Ebene (Kommandozeile `claude agents` statt über der Eingabezeile).
- Worktrees sind seit v2.1.x ein zentrales Isolations-Feature geworden, das parallele Sitzungen durch echte Datei-Isolation ermöglicht – weg von der anfänglichen Vision einer einfachen UI-Leiste.
- MCP Tool Search (Deferral bis on-demand) ist ein großes Feature hinzugekommen, das die Tool-Context-Kosten radikal senkt – nicht im Konzept erwähnt.
- Sessions können jetzt gebrancht werden (`/branch`), ohne dass die Original-Session verloren geht – eine Funktion, die nur indirekt in den Konzepten angedeutet war.
- Die Plugin-Architektur ist viel erwachsener geworden (Marketplace, Manifest mit Themes, Output Styles, LSP Servers) – über die ursprünglichen Skills hinaus.
- Fullscreen Transcript Rendering ist ein großer Schritt für lange Sitzungen, aber die Kapitelmarken-Idee wurde nicht damit kombiniert.
- Das Scratchpad ist NICHT als Persistent Storage gedacht, sondern wird wie alle Session-Daten nach 30 Tagen gelöscht – eine Unterscheidung, die klar hätte dokumentiert sein sollen.
