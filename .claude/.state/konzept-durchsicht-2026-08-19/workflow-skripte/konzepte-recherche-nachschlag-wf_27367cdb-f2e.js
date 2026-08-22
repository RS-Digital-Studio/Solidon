export const meta = {
  name: 'konzepte-recherche-nachschlag',
  description: 'Recherchiert die Themenfelder, die der erste Schub nicht abdeckte: Claude Code, MCP fuer CAD, Auslieferung und Infrastruktur, Barrierefreiheit, SindriCAD im Detail',
  phases: [
    { title: 'Nachschlag', detail: 'fuenf weitere Themenfelder' },
  ],
}

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['cluster', 'facts', 'not_verifiable', 'surprises'],
  properties: {
    cluster: { type: 'string' },
    facts: {
      type: 'array',
      maxItems: 40,
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['entity', 'statement', 'as_of', 'confidence', 'sources'],
        properties: {
          entity: { type: 'string' },
          statement: { type: 'string' },
          as_of: { type: 'string' },
          confidence: { type: 'string', enum: ['belegt', 'mehrere_quellen', 'unsicher'] },
          sources: { type: 'array', maxItems: 4, items: { type: 'string' } },
          note: { type: 'string' },
        },
      },
    },
    not_verifiable: { type: 'array', maxItems: 15, items: { type: 'string' } },
    surprises: { type: 'array', maxItems: 10, items: { type: 'string' } },
  },
}

const COMMON = `Du recherchierst für das Projekt Solidon den heutigen Stand eines Themenfelds. Heute ist der 19. August 2026.

**Werkzeuge:** Lade zuerst die Suchwerkzeuge mit einem einzigen Aufruf:
ToolSearch mit query "select:WebSearch,WebFetch"
Nutze WebSearch zum Finden und WebFetch, um die Seite wirklich zu lesen. Zahlen nur aus einer Seite, die du geholt hast.

**Regeln:** Jede Faktenkarte trägt mindestens eine vollständige URL. Dein Trainingswissen reicht bis Mai 2026 und ist zu alt — was du zu wissen glaubst, prüfst du nach oder lässt es weg. Findest du etwas nicht, schreibst du es in \`not_verifiable\`, wörtlich. **Nichts erfinden, nichts plausibel ergänzen.** Deutsch, echte Umlaute.

`

phase('Nachschlag')

const tasks = [
  () => agent(
    `Du beantwortest Fragen zu **Claude Code** für zwei Bedienkonzepte des Projekts Solidon, die im Juli/August 2026 geschrieben wurden und beschreiben, wie eine lange Agentensitzung bedienbar sein sollte.

Die Konzepte behaupten unter anderem:
1. Kapitelmarken seien in Claude Code als Werkzeug vorhanden, aber ungenutzt.
2. Eine Sitzungsleiste (drei feste Zeilen über der Eingabezeile mit Fortschritt und Abbrechen) gebe es nicht.
3. Ein Inhaltsverzeichnis links, Trennlinien im Transkript und Zuklappen von Kapiteln seien möglich.
4. Fünf von sechs Konzepten ließen sich allein in \`.claude/\` umsetzen, mit dem heutigen Funktionsumfang (Skills, Regeln, Hooks, Agents).
5. Skill-Dateien besäßen ein Feld \`argument-hint\`.
6. Claude Code erinnere wiederholt mit dem Wortlaut "The task tools haven't been used recently".
7. Claude Code melde "PostToolUse hook modified X after your edit (likely a formatter)".
8. Claude Code melde "the file had been modified on disk since you last read it", ohne den Verursacher zu nennen.
9. Hintergrundläufe seien über \`run_in_background\` verfügbar.
10. MCP-Server meldeten Verbinden, Trennen, Wiederverbinden und Anmeldepflicht ungefragt und mehrfach pro Sitzung.
11. Der Scratchpad stehe als Ablage über die Sitzung hinweg zur Verfügung.
12. Zwei parallele Sitzungen auf einem Arbeitsbaum seien der Normalfall.

**Deine Aufgabe:** Prüfe jede dieser zwölf Aussagen gegen den heutigen Funktionsumfang von Claude Code und sage, was davon heute stimmt, was überholt ist und was inzwischen anders oder besser gelöst ist. Ergänze, **was seit Juli 2026 an Claude Code dazugekommen ist**, das diese Konzepte berührt — insbesondere: Kapitelmarken, Hintergrundaufgaben und ihre Benachrichtigungen, Subagenten, Skills und ihre Metadatenfelder, Hooks und ihre Ereignisse, Plugins, Workflows/Mehragenten-Orchestrierung, Ausgabestile, Sitzungsverwaltung und Wiederaufnahme, die Oberfläche der Desktop- und Web-Fassung, Berechtigungsmodi.

Nenne für jede Aussage die Fundstelle in der offiziellen Dokumentation. Wo du aus deinem eigenen Werkzeugbestand sicher weißt, dass etwas existiert, sage das ausdrücklich als solches und belege es zusätzlich aus der Dokumentation.

Deutsch, echte Umlaute. Jede Faktenkarte mit Quelle.`,
    { label: 'nachschlag:claude-code', phase: 'Nachschlag', schema: SCHEMA, effort: 'high', agentType: 'claude-code-guide' }
  ),

  () => agent(
    COMMON + `Themenfeld: **MCP als Fernsteuerung für CAD- und 3D-Programme**.

Solidon bietet eine Fernsteuerung über MCP an und vergleicht sich mit anderen. Recherchiere den heutigen Stand (August 2026):

- **Model Context Protocol** selbst: aktuelle Fassung der Spezifikation, wichtige Änderungen 2026 (Transport, Elicitation, Sampling, Autorisierung, Werkzeug-Suche), wer es adoptiert hat
- **FreeCAD-MCP**: welche Umsetzungen gibt es, Sternezahl, Funktionsumfang (die Behauptung lautet: 165 Werkzeuge über 15 Module), Installationsweg, was geht und was nicht
- **blender-mcp**: Sternezahl heute (behauptet: 17.800), Funktionsumfang, Stand
- **Weitere CAD-/3D-MCP-Server**: für OpenSCAD, Onshape, Fusion, Rhino/Grasshopper, Cura/PrusaSlicer/OrcaSlicer, Bambu, sowie MCP-Server der KI-3D-Dienste (Meshy, Tripo, Hyper3D)
- **Meshy MCP-Server**: Grenzen und Preise je Aufruf (behauptet: 20 Anfragen/s, 10–100 gleichzeitige Aufgaben je Tarif, 1–50 Guthaben je Aufruf, Verkettung über input_task_id)

Für jeden: Sterne/Verbreitung, Lizenz, was er wirklich kann, und ob er 2026 noch gepflegt wird.`,
    { label: 'nachschlag:mcp-cad', phase: 'Nachschlag', schema: SCHEMA, effort: 'high' }
  ),

  () => agent(
    COMMON + `Themenfeld: **Auslieferung einer Windows-Desktop-Anwendung und die Infrastruktur dahinter**.

Solidon soll als Setup-Datei ausgeliefert werden, die Website liegt bei netcup. Recherchiere den heutigen Stand (August 2026) und prüfe dabei ausdrücklich diese Behauptungen:

- **Code Signing**: Seit Juni 2023 geben Zertifizierungsstellen keine exportierbaren PFX-Dateien mehr heraus (CA/Browser Forum Baseline Requirements) — gilt das heute noch, und was hat sich 2025/2026 geändert? Was kostet ein OV-Code-Signing-Zertifikat heute (behauptet: 250–400 €/Jahr)? Was kostet **Azure Trusted Signing** heute (behauptet: ~10 $/Monat), welche Nachweise verlangt es, ist es für Einzelunternehmer/Privatpersonen zugänglich, und wie lange dauert die Prüfung?
- **Microsoft SmartScreen**: wie werden unsignierte und frisch signierte Setups heute behandelt, wie baut sich Reputation auf
- **macOS**: Apple Developer Program (Preis heute, behauptet 99 $/Jahr), Notarisierung, Gatekeeper-Verhalten 2026, und ob ein auf Apple Silicon gebautes Paket auf Intel läuft (universal2)
- **PyInstaller**: aktuelle Fassung, Stand mit Python 3.13/3.14, bekannte Fallstricke mit PySide6/VTK, und ob Antivirus-Fehlalarme weiter ein Thema sind
- **Inno Setup**: aktuelle Fassung
- **Statik-Hoster**: Grenzen von Cloudflare Pages (behauptet: 25 MB je Datei), Netlify, GitHub Pages — Dateigrößen- und Gesamtgrenzen heute
- **Let's Encrypt**: Änderungen 2026 (Zertifikatslaufzeit, kurzlebige Zertifikate, Ende der Ablaufbenachrichtigungen)
- **GitHub Actions**: wie lange werden Artefakte aufbewahrt, Änderungen an den Runnern 2026, Windows- und macOS-Runner
- **Ed25519 / RFC 8032** als Signaturverfahren für Freischaltschlüssel: ist das weiter Stand der Technik, gibt es Warnungen gegen eine eigene Umsetzung in reinem Python`,
    { label: 'nachschlag:auslieferung', phase: 'Nachschlag', schema: SCHEMA, effort: 'high' }
  ),

  () => agent(
    COMMON + `Themenfeld: **Barrierefreiheit als Norm und als Pflicht**.

Solidon prüft seine Farbpaare gegen WCAG AA und will keine Bedeutung allein über Farbe tragen. Recherchiere den heutigen Stand (August 2026):

- **WCAG**: aktuelle Fassung (2.1, 2.2, Stand von 3.0/Silver), die Kontrastwerte, die heute gelten (3:1 für Bedienelemente und grafische Objekte, 4,5:1 für Text — stimmt das weiterhin, und ab welcher Schriftgröße gilt 3:1?), und welche Erfolgskriterien 2.2 hinzugefügt hat
- **EN 301 549**: aktuelle Fassung, Verhältnis zu WCAG, gilt sie für Desktop-Software
- **European Accessibility Act / Barrierefreiheitsstärkungsgesetz (BFSG)**: seit 28.06.2025 in Kraft — welche Produkte fallen darunter, ist eine verkaufte Desktop-CAD-Anwendung erfasst, gibt es eine Ausnahme für Kleinstunternehmen, und was gilt für Software, die nicht zu den ausdrücklich genannten Produkten gehört
- **Farbfehlsichtigkeit**: empfohlene Farbrampen (Viridis, Cividis, Okabe-Ito), Stand der Empfehlungen
- **Qt-Anwendungen und Barrierefreiheit**: Stand der Unterstützung in Qt 6 (Screenreader, Fokus, hoher Kontrast), Werkzeuge zum Prüfen

Achte darauf, deutsche und europäische Quellen zu nehmen, wo es um die Rechtslage geht.`,
    { label: 'nachschlag:barrierefreiheit', phase: 'Nachschlag', schema: SCHEMA, effort: 'high' }
  ),

  () => agent(
    COMMON + `Themenfeld: **SindriCAD im Einzelnen** — an diesem Programm hängt ein ganzes Konzeptdokument von Solidon.

SindriCAD ist ein freies parametrisches CAD-Programm für den 3D-Druck, öffentliche Beta seit 02.08.2026, von MakerViking (auch TinkerAtlas). Recherchiere den heutigen Stand (19. August 2026) so genau wie möglich:

- **Repository** github.com/MakerViking/sindricad: heutige Fassungsnummer, Sterne, Forks, Sprache, Größe, Datum der Anlage, Freigaberhythmus, offene Fehlerberichte — hole die GitHub-Seite selbst, und wenn möglich die Freigabeseite (releases) und die README
- **Was seit dem 02.08.2026 dazugekommen ist**: neue Fassungen, neue Funktionen, Presseecho
- **Funktionsumfang** heute: welche Modellierbefehle, Skizzen mit Zwangsbedingungen?, Texturen als echte Geometrie, Import/Export (STL, STEP, 3MF, GLB), Druckvorbereitung, Snapmaker-U1-Anbindung, gibt es eine KI-Funktion
- **Lizenz** (AGPL-3.0?) und was das für einen kommerziellen Wettbewerber bedeutet
- **Finanzierung**: die Behauptung lautet 335 $ Sockelkosten im Monat, 19 % des Ziels erreicht, ein Monat ohne Entwicklung wegen unbezahlter Werkzeuge, 99 $ für das Apple-Entwicklerprogramm — prüfe das gegen die Finanzierungsseite (Ko-fi, Patreon, GitHub Sponsors, o. ä.)
- **Verbreitung**: Downloadzahlen, Erwähnungen in der Presse (All3DP, 3Druck.com, Hackaday), Reddit-Echo

Wenn eine Zahl nicht auffindbar ist, sage das — dieses Dokument trägt sonst Zahlen, die niemand mehr prüfen kann.`,
    { label: 'nachschlag:sindricad', phase: 'Nachschlag', schema: SCHEMA, effort: 'high' }
  ),
]

const results = await parallel(tasks)
return results.filter(Boolean)
