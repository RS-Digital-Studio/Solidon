export const meta = {
  name: 'solidon-durchsicht-rest',
  description: 'Zweite, kleine Durchsicht: Handbuch, Beispielprojekte, Kommandozeile, Tastenkuerzel',
  phases: [
    { title: 'Durchsicht', detail: 'vier Gebiete, die der erste Lauf nicht abdeckt' },
    { title: 'Gegenpruefung', detail: 'je Fund ein Widerlegungsversuch' },
  ],
}

const CONTEXT = `
Projekt Solidon: Desktop-CAD in Python 3.14 mit PySide6, Arbeitsverzeichnis C:\\Users\\rober\\Documents\\Solidon.
Unterlagen: 3d-agent-bauplan.md (Sollverhalten), AGENTS.md (22 harte Regeln), .claude/rules/oberflaeche.md, ROADMAP.md.
Python: .venv\\Scripts\\python.exe

WICHTIG:
- Aendere KEINE Datei. Nur lesen, suchen, messen.
- Jeder Fund braucht Belegstelle (datei:zeile) und Zitat.
- Rate nicht. Ohne Beleg kein Fund.
- Morgen (20.08.2026) soll die Demo auf der Webseite stehen: markiere demo_blocker=true, wenn ein Erstnutzer es trifft.
- Auch kleine Funde sind gewollt.
`

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['area', 'findings'],
  properties: {
    area: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'where', 'evidence', 'why', 'fix', 'severity', 'demo_blocker', 'category'],
        properties: {
          title: { type: 'string' },
          where: { type: 'string' },
          evidence: { type: 'string' },
          why: { type: 'string' },
          fix: { type: 'string' },
          severity: { type: 'string', enum: ['hoch', 'mittel', 'niedrig'] },
          demo_blocker: { type: 'boolean' },
          category: { type: 'string', enum: ['bedienbarkeit', 'funktion', 'uebersicht', 'design', 'text', 'demo', 'barrierefreiheit', 'fehler'] },
        },
      },
    },
  },
}

const VERDICT = {
  type: 'object',
  additionalProperties: false,
  required: ['stands', 'reason'],
  properties: {
    stands: { type: 'boolean' },
    reason: { type: 'string' },
    correction: { type: 'string' },
  },
}

const AREAS = [
  {
    key: 'handbuch',
    prompt: `Gebiet: Das Handbuch — geschriebene Seiten plus erzeugte Referenz.
Dateien: app/core/manual.py, app/ui/manual_window.py, tools/make_manual.py, app/core/figures.py,
website/handbuch.html, website/en/manual.html, app/images/manual/.
Frage: Taugt das Handbuch fuer jemanden, der Solidon zum ersten Mal oeffnet (F1 und "die ersten fuenfzehn Minuten")?
Pruefe: Gliederung und Reihenfolge der Kapitel; ob jedes Kapitel sagt, was der Leser danach kann; ob die Abbildungen
zum Text passen und aktuell sind (Datum der Dateien gegen die letzten Aenderungen an app/ui); ob die erzeugte
Referenz lesbar ist oder eine Tabellenwueste; ob die im Fenster angezeigte Fassung und die Website-Fassung dasselbe
sagen; Suche im Handbuchfenster; Sprungmarken. Melde jede Stelle, an der das Handbuch Fachwissen voraussetzt oder
etwas beschreibt, das die Anwendung nicht (mehr) so tut.`,
  },
  {
    key: 'beispiele',
    prompt: `Gebiet: Die neun Beispielprojekte — das Erste, was ein Demonutzer anklickt.
Dateien: app/core/examples.py, tools/make_examples.py, app/examples/*.p3d, app/core/tour.py.
Frage: Sind die Beispiele gut? Pruefe fuer jedes: sagt Titel und Beschreibung einem Laien etwas; heissen die
Objekte darin verstaendlich (nicht "plate_holes"); passt die Tour dazu und sind ihre Schritte in der Anwendung
wirklich machbar; wie lange dauert das Auswerten (messen, nicht schaetzen — nutze das CLI oder ein kleines Skript);
erzeugt eines davon Warnungen im Pruefbericht, die einen Erstnutzer erschrecken. Pruefe auch die Reihenfolge auf
dem Startbildschirm und ob die Begriffe "Weg 1" bis "Weg 4" einem Laien etwas sagen.`,
  },
  {
    key: 'kommandozeile',
    prompt: `Gebiet: Die Kommandozeile.
Dateien: app/cli/main.py, tests/test_cli.py.
Frage: Ist sie brauchbar? Pruefe: Hilfetexte jedes Unterbefehls (auch --help der Unterbefehle, wirklich ausfuehren
mit .venv\\Scripts\\python.exe -m app.cli.main <befehl> --help); Fehlermeldungen bei falschen Eingaben (Regel 17:
jede Ausnahme mit Handlungsvorschlag); ob "run" alle 85 Operationen erreicht und wie man deren Parameter erfaehrt;
Ausgabeformate (menschenlesbar und maschinenlesbar?); Rueckgabewerte; ob ask als Abfrage funktioniert und was bei
nicht-interaktiver Eingabe passiert; ob Fortschritt als Zeile kommt. Melde jede Stelle, an der die Kommandozeile
etwas kann, das die Oberflaeche nicht kann, oder umgekehrt — ohne Grund.`,
  },
  {
    key: 'kuerzel',
    prompt: `Gebiet: Tastenkuerzel und Bedienung ohne Maus.
Dateien: app/ui/shortcut_schemes.py, app/ui/shortcuts_window.py, app/ui/main_window.py (Kuerzel-Registrierung),
app/core/registry/registry.py (shortcut-Feld), tests/test_shortcuts.py falls vorhanden.
Frage: Pruefe die Kuerzelbelegung vollstaendig: Zaehle sie aus (nutze .venv\\Scripts\\python.exe), suche
Doppelbelegungen, pruefe gegen die Gewohnheiten (Strg+Z/Y, Strg+S, F1, Entf, Esc, Pos1) und gegen die drei
Navigationsschemata aus §2.9. Pruefe das Kuerzelfenster: ist es vollstaendig, gruppiert, durchsuchbar, und nennt es
auch die Kuerzel, die nicht aus dem Register kommen (Werkzeuge Alt+1..8, Ansichten, Palette)? Pruefe, ob jede
Handlung ohne Maus erreichbar ist und ob irgendwo ein Kuerzel dokumentiert ist, das es nicht gibt (oder umgekehrt).`,
  },
]

phase('Durchsicht')
log(`${AREAS.length} weitere Gebiete`)

const results = await pipeline(
  AREAS,
  (a) => agent(`${CONTEXT}\n\n${a.prompt}\n\nGib die Funde ueber das Schema zurueck, nach Schwere sortiert.`,
    { label: `rest:${a.key}`, phase: 'Durchsicht', schema: SCHEMA }),
  (res, a) => {
    if (!res || !res.findings || !res.findings.length) return { area: a.key, findings: [] }
    return parallel(res.findings.slice(0, 5).map((f) => () =>
      agent(`${CONTEXT}

Gegenpruefung. Versuche den Fund zu WIDERLEGEN. Unsicher heisst stands=false.

Gebiet: ${a.key}
Behauptung: ${f.title}
Stelle: ${f.where}
Beleg: ${f.evidence}

Lies die Stelle selbst und pruefe, ob ROADMAP.md, eine Regel oder ein Test die Sache schon anders regelt.`,
        { label: `gegen:${a.key}`, phase: 'Gegenpruefung', schema: VERDICT })
        .then((v) => ({ ...f, area: a.key, verdict: v }))
    ))
  }
)

const all = results.flat().filter(Boolean).filter((f) => f && f.verdict)
const stands = all.filter((f) => f.verdict.stands)
log(`${stands.length} von ${all.length} Funden halten stand`)

return {
  bestaetigt: stands.map((f) => ({
    gebiet: f.area, titel: f.title, stelle: f.where, beleg: f.evidence, warum: f.why, fix: f.fix,
    schwere: f.severity, demo: f.demo_blocker, art: f.category, gegenpruefung: f.verdict.reason,
  })),
  gefallen: all.filter((f) => !f.verdict.stands).map((f) => ({ titel: f.title, grund: f.verdict.reason })),
}
