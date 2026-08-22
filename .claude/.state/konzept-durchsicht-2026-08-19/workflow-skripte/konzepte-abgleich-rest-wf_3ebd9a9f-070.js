export const meta = {
  name: 'konzepte-abgleich-rest',
  description: 'Prüft die restlichen sechs Konzeptdateien gegen den heutigen Code und die ROADMAP',
  phases: [
    { title: 'Abgleich', detail: 'die sechs offenen Dokumente' },
  ],
}

const FILES = [
  '.claude/konzept-slicer-uebergabe.md',
  '.claude/konzept-live-durchsicht-2026-08.md',
  '.claude/konzept-p15-konstruieren-und-zeigen.md',
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
    report_path: { type: 'string' },
    counts: {
      type: 'object',
      additionalProperties: false,
      required: ['stimmt', 'ueberholt', 'falsch', 'unpruefbar'],
      properties: {
        stimmt: { type: 'integer' },
        ueberholt: { type: 'integer' },
        falsch: { type: 'integer' },
        unpruefbar: { type: 'integer' },
      },
    },
    headline_findings: {
      type: 'array',
      maxItems: 12,
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claim', 'verdict', 'evidence', 'fix'],
        properties: {
          claim: { type: 'string' },
          verdict: { type: 'string', enum: ['ueberholt', 'falsch', 'widerspruch_im_dokument'] },
          evidence: { type: 'string' },
          fix: { type: 'string' },
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

1. Lies die Arbeitsmappe. Ihr Abschnitt „Intern prüfbare Behauptungen" ist deine Liste. Lies auch die Konzeptdatei selbst, mindestens die Stellen um jede Behauptung herum.

2. Prüfe **jede** interne Behauptung am heutigen Repository: \`grep\`/Grep, Read, \`git log\`, \`git log -S\`, ROADMAP.md, die Tests. Wo eine Zahl behauptet wird, zähle sie nach. Nützlich:
   \`\`\`
   .venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations; from app.core.registry import REGISTRY; load_operations(); print(len(REGISTRY.all()))"
   \`\`\`
   Schon ermittelt: 85 Operationen, 17 Bausteine, 6 Sprachen (Deutsch als Quelle plus en/es/fr/it/pt), 133 Testdateien, Version 0.1.0, seit dem 01.08.2026 rund 686 Commits.

3. Urteile je Behauptung: **stimmt** · **überholt** · **falsch** · **unprüfbar**. Jedes Urteil außer „stimmt" braucht einen nachschlagbaren Beleg: Datei:Zeile, Testname, Kommando samt Ausgabe, ROADMAP-Abschnitt.

4. Achte besonders auf Aussagen der Form „fehlt", „ist nicht gebaut", „Entwurf", „noch offen" — und auf **Widersprüche innerhalb des Dokuments**, wo ein Nachtrag „erledigt" sagt, während der Haupttext weiter „fehlt" sagt. Das ist hier der häufigste Fehler.

${f.includes('bedienkonzept') ? `
**Besonderheit dieses Dokuments:** Es beschreibt nicht Solidon, sondern wie *Claude Code* als Werkzeug bedienbar sein soll. Sein Abschnitt „Was schiefging" steht auf Beobachtungen aus einer echten Sitzung. Prüfe deshalb hier vor allem: Was von dem, was das Dokument als Entwurf oder Vorschlag führt, ist inzwischen in \`.claude/\` dieses Projekts wirklich umgesetzt — Skills, Hooks, Agents, Regeln? Die Schlusstabelle des Dokuments sagt, was umgesetzt sei; prüfe sie Zeile für Zeile gegen \`.claude/skills/\`, \`.claude/hooks/\`, \`.claude/agents/\`, \`.claude/rules/\` und \`.claude/settings.json\`.
` : ''}
5. Schreibe den ausführlichen Bericht nach \`${SCRATCH}\\abgleich\\${slug}.md\` — je Behauptung ein Eintrag mit Urteil, Beleg und dem Satz, der im Konzept stattdessen stehen müsste.

**Du änderst die Konzeptdatei nicht** und überhaupt keine Datei im Repository. Nur lesen, prüfen, Bericht in den Arbeitsordner schreiben.

Deutsch, echte Umlaute.`,
    { label: `abgleich:${slug}`, phase: 'Abgleich', schema: SCHEMA, effort: 'high' }
  )
}))

return results.filter(Boolean)
