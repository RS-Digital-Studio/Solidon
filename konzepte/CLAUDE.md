# `konzepte/` — das Warum

Konzepte, Durchsichten, Nachweise und Entscheidungen. **Der Index ist
`konzepte/README.md`** und nennt zu jedem den Stand. Das Warum dieser Karte:
`konzepte/begruendungen/karte-konzepte.md`.

| Ort | Inhalt |
|---|---|
| `konzept-*.md` und die übrigen Dokumente | Warum etwas so gebaut wurde — kein Auftrag und keine Arbeitsliste |
| `archiv/` | Erledigte und abgelöste Dokumente, unter ihrem alten Namen; im Index eigener Abschnitt „Archiv“ |
| `nachweise-*/` | Messprotokolle und Belege zu einem Konzept; `nachweise-release-*/` die einer Release-Durchsicht, auf die offene Punkte verweisen — unverändert abgelegt, von ruff ausgenommen |
| `begruendungen/` | Das Warum, das aus Regeln und Karten verschoben wurde, als sie auf das Einzuhaltende verdichtet wurden — je Quelle eine Datei (`regel-<name>.md`, `karte-<pfad>.md`), gegliedert nach deren Überschriften |

**Offene Arbeit steht im Register von `ROADMAP.md` und nirgends sonst.** Die
Statustabellen der Konzepte altern: Wer „offen“ in einem Konzept liest,
**prüft es am Code, bevor er es glaubt**, und trägt es ins Register nach, wenn
es stimmt. Bei Widerspruch gilt der Bauplan (`3d-agent-bauplan.md`) — ein
Konzept schlägt vor, der Bauplan entscheidet; eine Aussage ohne §-Beleg ist
eine Vermutung.

## Wenn ein Konzept erledigt oder abgelöst ist

Der Abschnitt der Arbeitsliste wandert nach `ROADMAP-ARCHIV.md`, datiert. Das
Konzept zieht mit `git mv` nach `archiv/`, sobald nichts Geltendes mehr darauf
zeigt: kein offener Punkt in `ROADMAP.md`, keine Regel in `.claude/rules/`,
keine Karte, nicht `AGENTS.md`, `CLAUDE.md` oder der Bauplan als Grundlage.
Eine noch geltende Entscheidung oder ein Verfahren bleibt, und im Zweifel
bleibt das Dokument auch. Im selben Commit:

- jeden Verweis nachziehen — `git grep -n "konzepte/<name>"` über das ganze
  Repository, dazu die relativen Links in `konzepte/` (auch die aus dem
  verschobenen Dokument heraus) und bloße Nennungen `<name>.md` in den
  Dokumenten daneben; Nachweisordner bleiben unverändert;
- die Zeile im Index in den Abschnitt „Archiv“ verschieben, mit Gebiet und
  dem Grund, falls die alte Statuszeile ihn nicht nennt.

Name und Inhalt bleiben; das Dokument erklärt weiter das Warum.
