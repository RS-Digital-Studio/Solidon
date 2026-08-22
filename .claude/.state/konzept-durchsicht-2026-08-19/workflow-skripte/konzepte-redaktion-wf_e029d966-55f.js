export const meta = {
  name: 'konzepte-redaktion',
  description: 'Zieht jede Konzeptdatei auf den Stand vom 19.08.2026 nach — belegte Aussenfakten, erledigte Punkte, aufgeloeste Widersprueche',
  phases: [
    { title: 'Redaktion', detail: 'ein Redakteur je Konzeptdatei' },
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

const ST = 'C:\\Users\\rober\\Documents\\Solidon\\.claude\\.state\\konzept-durchsicht-2026-08-19'

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['file', 'aenderungen', 'offen_gelassen', 'zusammenfassung'],
  properties: {
    file: { type: 'string' },
    aenderungen: {
      type: 'array',
      maxItems: 25,
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['art', 'stelle', 'was'],
        properties: {
          art: { type: 'string', enum: ['aussenfakt', 'erledigt-vermerk', 'widerspruch-aufgeloest', 'zahl-berichtigt', 'stand-datum', 'sonstiges'] },
          stelle: { type: 'string', description: 'Abschnitt des Dokuments' },
          was: { type: 'string', description: 'Was vorher stand und was jetzt steht, knapp' },
        },
      },
    },
    offen_gelassen: {
      type: 'array',
      maxItems: 15,
      items: { type: 'string', description: 'Was bewusst NICHT geaendert wurde und warum — vor allem: was nicht belegbar war' },
    },
    zusammenfassung: { type: 'string', description: 'Zwei bis vier Saetze: was dieses Dokument jetzt anders sagt als vorher' },
  },
}

phase('Redaktion')

const results = await parallel(FILES.map((f) => {
  const slug = f.replace('.claude/', '').replace('.md', '')
  return () => agent(
    `Du ziehst eine Konzeptdatei des Projekts Solidon auf den heutigen Stand nach. Heute ist der **19. August 2026**. Arbeitsverzeichnis ist die Repository-Wurzel.

**DEINE DATEI (und nur diese darfst du ändern):** \`${f}\`

**Dein Material** — lies es, bevor du etwas änderst:
- \`${ST}\\befunde\\${slug}.md\` — welche Behauptungen das Dokument aufstellt
- \`${ST}\\abgleich\\${slug}.md\` — dieselben Behauptungen gegen den heutigen Code geprüft, mit Belegen
- \`${ST}\\faktenkarten\\${slug}.md\` — was die Online-Recherche vom 19.08.2026 zur Außenwelt ergeben hat, jede Karte mit Quelle
${slug.startsWith('bedienkonzept') ? `- \`${ST}\\KORREKTUR-claude-code.md\` — **zuerst lesen.** Die Recherche zu Claude Code ist in drei Punkten nachweislich falsch; die Korrektur sagt, welche.
` : ''}
Die Faktenkarten sind lang. Lies sie gezielt: suche die Einträge zu den Namen, die **dein** Dokument nennt.

---

## Was du tust

**1. Außenfakten berichtigen.** Wo das Dokument eine Zahl, Fassung, einen Preis oder eine Rechtslage nennt, die die Recherche widerlegt: berichtige sie und schreibe den Stand dazu. Form: die neue Zahl im Text, dahinter in Klammern oder im Satz das Datum. Bei etwas, das eine Entscheidung trägt, nenne die Quelle als URL in einer Fußnote oder direkt im Satz.

**2. Erledigtes als erledigt kennzeichnen.** Wo der Abgleich „überholt" sagt, weil der Code den Vorschlag inzwischen eingelöst hat, setzt du die Hausform dieses Projekts — ein Blockzitat direkt unter der betroffenen Stelle:

> **Erledigt.** \`app/core/slice/advise.py:524\` schlägt Bügeln vor, wenn eine bündige Passung im Spiel ist (a28bd00, 07.08.2026).

Und wenn es **anders** gebaut wurde als vorgeschlagen, sagst du das — genau dafür ist der Vermerk da:

> **Erledigt — die Vokabel heißt \`pin\`, nicht \`boss\`.** …

**3. Falsches berichtigen.** Wo der Abgleich „falsch" sagt, war die Aussage schon beim Schreiben nicht richtig. Die berichtigst du im Text selbst und sagst dazu, was stattdessen gilt — mit dem Beleg aus dem Abgleich (Datei:Zeile, Commit, Testname).

**4. Widersprüche auflösen.** Wo Haupttext und Nachtrag einander widersprechen — der eine sagt „fehlt", der andere „erledigt" —, gewinnt der Code. Löse den Widerspruch an **beiden** Stellen auf, nicht nur an einer. Das ist in diesem Projekt der häufigste Fehler.

**5. Stand-Datum fortschreiben.** Die Kopfzeile bekommt den neuen Stand, ohne den alten zu verschweigen. Etwa: „Stand 12.08.2026, nachrecherchiert am 19.08.2026."

**6. Am Dateiende** ein Abschnitt \`## Nachrecherchiert am 19.08.2026\` — knapp: was sich als überholt erwies, was die Außenrecherche geändert hat, und **was nicht belegbar war**.

---

## Was du nicht tust

- **Keine Messung und keine Beobachtung löschen.** Ein Messwert vom 5. August ist am 19. August nicht falsch, sondern datiert. Er bleibt stehen und bekommt den heutigen Wert daneben. Dasselbe gilt für Bildschirmbeobachtungen und Bedienläufe: sie sind Geschichte, kein Rückstand.
- **Nichts erfinden.** Was die Faktenkarten unter „Nicht belegbar" führen, bleibt im Dokument offen und wird als offen gekennzeichnet — nicht plausibel ergänzt. Eine erfundene Zahl richtet mehr Schaden an als eine fehlende.
- **Keine Quelle erfinden.** Nur URLs, die in den Faktenkarten stehen.
- **Keine andere Datei anfassen.** Nicht die ROADMAP, nicht den Bauplan, keine zweite Konzeptdatei, keinen Code.
- **Das Dokument nicht neu schreiben.** Du änderst gezielt, was falsch oder überholt ist. Aufbau, Ton und Argumentation bleiben.

## Sprache

Deutsche Prosa mit echten Umlauten, englische Bezeichner. Der Ton dieses Projekts ist die Aussage, nicht das Etikett: „Der Prüfbericht sagte, was nicht stimmt, und hörte da auf" — nicht „Verbesserung des Prüfberichts". Halte dich an den Ton, den die Datei schon hat.

Gib zurück, was du geändert hast, und was du bewusst offen gelassen hast.`,
    { label: `redaktion:${slug}`, phase: 'Redaktion', schema: SCHEMA, effort: 'high' }
  )
}))

return results.filter(Boolean)
