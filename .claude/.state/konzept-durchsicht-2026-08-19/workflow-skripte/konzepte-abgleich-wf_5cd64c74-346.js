export const meta = {
  name: 'konzepte-abgleich',
  description: 'Prüft je Konzeptdatei die internen Behauptungen gegen den heutigen Code und die ROADMAP',
  phases: [
    { title: 'Abgleich', detail: 'ein Prüfer je Konzeptdatei' },
  ],
}

const FILES = [
  'konzept-agent-vertiefung.md',
  'konzept-bedienung.md',
  'konzept-durchsicht-2026-08-14.md',
  'konzept-erstnutzer-2026-08.md',
  'konzept-erzeugen-agent-oberflaeche-2026-08.md',
  'konzept-kundensicht-2026-08.md',
  'konzept-meshy-hyper3d-2026-08.md',
  'konzept-organische-modellierung-2026-08.md',
  'konzept-sindricad.md',
  'konzept-wettbewerb-2026-08.md',
  '.claude/konzept-demo-2026-10.md',
  '.claude/konzept-fassungspflege-2026-08.md',
  '.claude/konzept-live-durchsicht-2026-08.md',
  '.claude/konzept-p15-konstruieren-und-zeigen.md',
  '.claude/konzept-slicer-uebergabe.md',
  '.claude/konzept-veroeffentlichung-1.0.md',
  '.claude/bedienkonzept-ueberblick.md',
  '.claude/bedienkonzept-funktionen.md',
]

const SCRATCH = 'C:\\Users\\rober\\AppData\\Local\\Temp\\claude\\C--Users-rober-Documents-Solidon\\aecc4f5d-ab71-44d0-8fba-57c7ffd6f074\\scratchpad'

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['file', 'report_path', 'counts', 'headline_findings'],
  properties: {
    file: { type: 'string' },
    report_path: { type: 'string', description: 'Wohin der ausführliche Bericht geschrieben wurde' },
    counts: {
      type: 'object',
      additionalProperties: false,
      required: ['stimmt', 'ueberholt', 'falsch', 'unpruefbar'],
      properties: {
        stimmt: { type: 'integer' },
        ueberholt: { type: 'integer', description: 'War richtig, ist inzwischen erledigt oder anders gebaut' },
        falsch: { type: 'integer', description: 'War schon beim Schreiben nicht richtig' },
        unpruefbar: { type: 'integer' },
      },
    },
    headline_findings: {
      type: 'array',
      maxItems: 12,
      description: 'Die Abweichungen, die beim Lesen des Dokuments zu einer falschen Entscheidung führen würden',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claim', 'verdict', 'evidence', 'fix'],
        properties: {
          claim: { type: 'string', description: 'Was das Dokument sagt' },
          verdict: { type: 'string', enum: ['ueberholt', 'falsch', 'widerspruch_im_dokument'] },
          evidence: { type: 'string', description: 'Der Beleg: Datei:Zeile, Testname, Kommando mit Ausgabe, ROADMAP-Abschnitt' },
          fix: { type: 'string', description: 'Was im Dokument stattdessen stehen muss' },
        },
      },
    },
  },
}

phase('Abgleich')

const results = await parallel(FILES.map((f) => () => {
  const slug = f.replace('.claude/', '').replace('.md', '')
  return agent(
    `Du prüfst, ob eine Konzeptdatei des Projekts Solidon noch den heutigen Stand des Codes beschreibt. Heute ist der 19. August 2026. Arbeitsverzeichnis ist die Repository-Wurzel.

KONZEPTDATEI: ${f}
ARBEITSMAPPE (Ergebnis der Sondierung, deine Arbeitsliste): ${SCRATCH}\\befunde\\${slug}.md

**Vorgehen**

1. Lies die Arbeitsmappe. Ihr Abschnitt „Intern prüfbare Behauptungen" ist deine Liste. Lies auch die Konzeptdatei selbst, mindestens die Stellen um jede Behauptung herum — die Mappe ist eine Abkürzung, nicht die Quelle.

2. Prüfe **jede** interne Behauptung am heutigen Repository. Mittel: \`grep\`/Grep, Read, \`git log\`, \`git log -S\`, ROADMAP.md, die Tests. Wo eine Zahl behauptet wird (Anzahl Operationen, Menüzeilen, Tests, Sprachen), zähle sie nach, statt sie zu glauben. Nützliche Zählungen laufen so:
   \`\`\`
   .venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations; from app.core.registry import REGISTRY; load_operations(); print(len(REGISTRY.all()))"
   \`\`\`
   Zum Vergleich schon ermittelt: 85 Operationen, 17 Bausteine, 6 Sprachen (Deutsch als Quelle plus en/es/fr/it/pt), 133 Testdateien, Version 0.1.0, seit dem 01.08.2026 rund 686 Commits.

3. Urteile je Behauptung: **stimmt** · **überholt** (war richtig, ist inzwischen erledigt oder anders gebaut) · **falsch** (war schon damals nicht richtig) · **unprüfbar**. Jedes Urteil außer „stimmt" braucht einen Beleg, der jemand anders nachschlagen kann: Datei:Zeile, Testname, Kommando samt Ausgabe, oder ROADMAP-Abschnitt.

4. Achte besonders auf: Aussagen der Form „fehlt", „ist nicht gebaut", „Entwurf", „noch offen" — die altern am schnellsten. Und auf **Widersprüche innerhalb des Dokuments**: ein Nachtrag sagt „erledigt", während der Haupttext weiter „fehlt" sagt. Das ist in diesem Projekt schon mehrfach vorgekommen und der häufigste Fehler.

5. Schreibe den ausführlichen Bericht nach \`${SCRATCH}\\abgleich\\${slug}.md\` — je Behauptung ein Eintrag mit Urteil, Beleg und dem Satz, der im Konzept stattdessen stehen müsste. Lege das Verzeichnis an, falls es fehlt.

**Du änderst die Konzeptdatei nicht** und überhaupt keine Datei im Repository. Nur lesen, prüfen, und den Bericht in den Arbeitsordner schreiben.

Gib mir zurück: die Zählung und die Funde, die beim Lesen des Dokuments zu einer falschen Entscheidung führen würden. Deutsch, echte Umlaute.`,
    { label: `abgleich:${slug}`, phase: 'Abgleich', schema: SCHEMA, effort: 'high' }
  )
}))

return results.filter(Boolean)
