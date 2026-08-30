---
name: aus-kundensicht-perfekt
description: "Robert am 23.08.2026: alles immer perfekt aus Kundensicht machen — nicht aus Entwicklersicht, und nicht nur das Beauftragte."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a6e000e4-7f10-4e2d-92c3-c5df9b4a17cf
  modified: 2026-08-30T12:39:55.313Z
---

Roberts Worte: *„mach es aus kundensicht perfekt, du sollst alles was du tust
immer perfekt aus kundensicht machen merk dir das."* Gesagt zu der Frage, ob
zwei Menüeinträge zusammengelegt werden sollen, die dasselbe tun — die Antwort
war ja, obwohl es eine Formatmigration kostet.

**Why:** Der Maßstab ist nicht, ob eine Sache technisch richtig ist, sondern ob
sie für den zahlenden Kunden richtig ist. Zwei Einträge, die dasselbe tun, sind
technisch harmlos und aus Kundensicht ein Ratespiel. Aufwand ist kein
Gegenargument: Eine Migration für bestehende Projektdateien ist teurer als ein
Menüeintrag und trotzdem die richtige Antwort.

**How to apply:**

- Bei jeder Entscheidung zuerst fragen: *Was sieht der Kunde, und muss er
  raten?* Erst danach, was es kostet.
- Die Frage ist nie, ob **ich** es verstehe. Ein Fachbegriff, der mir
  selbstverständlich ist, ist für den Kunden eine Hürde — neun `doc`-Sätze
  sagten „B-Rep-Körper", während der Umschalter längst „exakter Körper" hieß.
- Nicht nur das Beauftragte prüfen, sondern die Kundenwirkung des Ganzen. Wer
  eine Funktion anfasst, sieht nach, ob ihr Name, ihre Vorgabe, ihre Grenze und
  ihre Fehlermeldung zusammen einen Sinn ergeben.
- Der beste Beleg ist eine Zahl mit Gegenprobe: 37 Suchwörter, 28 führten ans
  Ziel, nach der Änderung 32 — das schlägt jede Meinung über Verständlichkeit.
- Gilt auch dort, wo der Kunde es nie sieht: Ein Update, das ihn nicht erreicht,
  ist kein Update. Siehe [[version-vor-jedem-bau-erhoehen]].

**Präzisiert am 30.08.2026, nach dem 0.2.2-Release:** *„immer daran denken
auch alle andere session und dass auch immer in der gesamten app sie ist für
kunden ohne cad kenntnisse und sollte einfach und schnell bedienbar sein,
aber perfekt mit allem was wir auf der webseite versprechen."* Drei Schärfungen
gegenüber dem Satz von oben:

- **Die Zielgruppe hat keine CAD-Kenntnisse.** Der Vergleichsmaßstab für
  Bedienung ist der Slicer, aus dem diese Kunden kommen (Cura, Prusa,
  Elegoo/Orca) — nicht Fusion und kein CAD. Jeder Fachbegriff, jede
  CAD-Gewohnheit (erst Werkzeug, dann Geste) ist eine Hürde.
- **Einfach UND schnell** — beides zusammen. Ein kurzer Weg, den man suchen
  muss, ist nicht einfach; ein einfacher Weg über fünf Klicks ist nicht
  schnell.
- **Die Website ist die Sollliste.** Was dort versprochen wird, muss in der
  App perfekt eingelöst sein — Versprechen und Produkt werden gegeneinander
  geprüft, in beide Richtungen (siehe [[texte-altern-mit-ihrer-grenze]]).

Und unmittelbar danach die vierte Schärfung: *„alles auch komplett
hochwertig, schön, modern, innovativ, selbsterklärend und intuitiv."*
Einfachheit ist die halbe Zusage — die andere Hälfte ist Anmutung:

- **Hochwertig und schön** ist kein Beiwerk, sondern Kaufgrund (Roberts
  globale Vorgabe: visuell hochwertig = zahlende Kunden). Ein Feature,
  das funktioniert und billig aussieht, ist nicht fertig.
- **Selbsterklärend und intuitiv** heißt: Die Grundwege brauchen kein
  Handbuch. Ein Bedienelement sieht aus wie das, was es tut; was
  klickbar ist, wirkt klickbar; der nächste Schritt liegt da, wo die
  Hand schon ist.
- **Modern und innovativ** heißt nicht Effekthascherei, sondern: keine
  Bedienmuster aus Gewohnheit übernehmen, die der Slicer-Kunde nie
  gelernt hat — und wo Solidon etwas besser kann als jeder Slicer (die
  Zahl während des Zugs), das sichtbar machen statt verstecken.

Gilt für jede Sitzung und jedes Gebiet, nicht nur für Bedienpakete —
und ausdrücklich (Robert, 30.08.2026) *„auch für die webseite und alles
was mit der app zu tun hat"*: Website, Handbuch, Presse, Installer,
Update-Fenster, Fehlertexte — der ganze Auftritt, nicht nur das
Programmfenster.
