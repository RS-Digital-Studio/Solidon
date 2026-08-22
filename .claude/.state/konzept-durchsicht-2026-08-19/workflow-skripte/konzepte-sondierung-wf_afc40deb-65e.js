export const meta = {
  name: 'konzepte-sondierung',
  description: 'Liest alle 18 Konzeptdateien und listet je Datei die prüfbaren Behauptungen (extern wie intern)',
  phases: [
    { title: 'Sondierung', detail: 'ein Leser je Konzeptdatei' },
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

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['file', 'title', 'stated_date', 'purpose', 'external_claims', 'internal_claims', 'staleness', 'sections'],
  properties: {
    file: { type: 'string' },
    title: { type: 'string' },
    stated_date: { type: 'string', description: 'Das im Dokument genannte Stand-Datum, wörtlich' },
    purpose: { type: 'string', description: 'Ein Satz: wozu dieses Dokument da ist' },
    external_claims: {
      type: 'array',
      maxItems: 20,
      description: 'Aussagen über die Welt ausserhalb des Repos, die online nachprüfbar sind',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claim', 'entity', 'kind', 'priority', 'where'],
        properties: {
          claim: { type: 'string', description: 'Die Behauptung, knapp und wörtlich genug zum Wiederfinden' },
          entity: { type: 'string', description: 'Produkt/Firma/Norm/Paket, um das es geht' },
          kind: { type: 'string', enum: ['preis', 'fassung', 'funktionsumfang', 'recht', 'api', 'datum', 'marktlage', 'sonstiges'] },
          priority: { type: 'string', enum: ['hoch', 'mittel', 'niedrig'] },
          where: { type: 'string', description: 'Abschnitt oder Zeilennummer' },
        },
      },
    },
    internal_claims: {
      type: 'array',
      maxItems: 15,
      description: 'Aussagen ueber den Stand des eigenen Codes/Projekts, die gegen Repo und ROADMAP prüfbar sind',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claim', 'how_to_verify', 'priority', 'where'],
        properties: {
          claim: { type: 'string' },
          how_to_verify: { type: 'string', description: 'Konkret: Datei, Test, Kommando oder ROADMAP-Abschnitt' },
          priority: { type: 'string', enum: ['hoch', 'mittel', 'niedrig'] },
          where: { type: 'string' },
        },
      },
    },
    staleness: {
      type: 'object',
      additionalProperties: false,
      required: ['score', 'reason'],
      properties: {
        score: { type: 'integer', minimum: 1, maximum: 5, description: '1 = zeitlos, 5 = altert schnell und sichtbar' },
        reason: { type: 'string' },
      },
    },
    sections: { type: 'array', maxItems: 40, items: { type: 'string' }, description: 'Die Überschriften der obersten Gliederungsebene' },
  },
}

phase('Sondierung')

const results = await parallel(FILES.map((f) => () =>
  agent(
    `Du sondierst eine Konzeptdatei des Projekts Solidon (Arbeitsverzeichnis ist die Repository-Wurzel).

DATEI: ${f}

Lies die Datei VOLLSTÄNDIG (sie ist lang — lies sie ganz, in mehreren Leseschritten, nicht nur den Anfang).

Deine Aufgabe ist reine Bestandsaufnahme. Du änderst NICHTS und schreibst KEINE Datei.

Trage zusammen:

1. Das im Dokument genannte Stand-Datum, wörtlich wie es dort steht.

2. **external_claims** — jede Aussage über die Welt außerhalb dieses Repositories, die man online nachprüfen kann und die altern kann. Also: Preise und Preismodelle fremder Programme, Fassungsnummern fremder Software, Funktionsumfang von Wettbewerbern, API-Schnittstellen und ihre Endpunkte, Rechtslage und Fristen, Marktaussagen ("die beiden führenden ..."), Erscheinungsdaten, verfügbare KI-Modelle und ihre Preise, Paketfassungen aus dem Python-Ökosystem. Nenne Produkt/Firma/Norm im Feld entity so, dass man danach suchen kann. Priorität hoch für alles, wo eine falsche Zahl eine Entscheidung im Dokument trägt.

3. **internal_claims** — Aussagen über den Stand von Solidon selbst, die seit dem Stand-Datum überholt sein könnten: Messwerte, Zählungen ("84 Operationen"), "ist noch nicht gebaut", "fehlt", "Entwurf", Bewertungen des Umsetzungsgrads, Verweise auf ROADMAP-Phasen. Gib jeweils an, wie man das heute konkret prüft.

4. **staleness** — wie schnell dieses Dokument altert und warum.

5. **sections** — die Überschriften der obersten Gliederungsebene, in Reihenfolge.

Sei vollständig bei dem, was zählt, und knapp im Wortlaut. Deutsch, echte Umlaute.`,
    { label: `sondieren:${f.replace('.claude/', '')}`, phase: 'Sondierung', schema: SCHEMA, effort: 'medium' }
  )
))

return results.filter(Boolean)
