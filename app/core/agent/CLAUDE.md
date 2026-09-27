# `app/core/agent/` — die Agentenschicht

Der Agent ist **kein Chatbot mit angehängtem 3D-Programm** (§26). Er arbeitet
mit genau den Operationen, die der Nutzer hat, sieht genau, was der Nutzer
sieht, und alles, was er tut, kommt als **eine** Transaktion an, die ein
einziges Undo zurücknimmt.

Einzuhalten ist `.claude/rules/agentenschicht.md` (Transaktion,
Vorrangregeln, Kontextfenster, Angebot für lokale Modelle, MCP, Suite), dazu
`kern.md`; Messwerte und Anlässe dieser Karte:
`konzepte/begruendungen/karte-app-core-agent.md`.

## Der Zug

```
Anfrage
   │
   ▼
context.py    Steckbrief + Systemprompt + Regelsammlung  ──> was er sieht
   │
   ▼
session.py    der Zug: Modell fragen, Werkzeug rufen, wiederholen
   │              │
   │              ├─ tools.py     was er tun kann (aus dem Register!)
   │              ├─ offer.py     was ein lokales Modell davon ausführlich sieht
   │              ├─ analysis.py  Analysen als Werkzeugantwort
   │              └─ checks.py    nach JEDER Operation prüfen
   ▼
proposal.py   ein Vorschlag = eine Transaktion
   │
   ▼
apply.py      annehmen oder verwerfen — beides vollständig
```

## Die Karte

| Datei | Rolle |
|---|---|
| `session.py` | Ein Zug, von der Anfrage zum Vorschlag (§26.5) |
| `context.py` | Was der Agent zu sehen bekommt (§26.1) |
| `prompt.py` | Der Systemprompt (§26.1, §39) |
| `tools.py` | Was er tun kann (§26.2) — aus `registry.tool_schemas()`, **derselben Quelle** wie Menü und Kommandozeile |
| `offer.py` | Was ein lokales Modell davon je Schritt ausführlich sieht — jedes Werkzeug bleibt aufrufbar |
| `analysis.py` | Analysen als Werkzeugantwort |
| `checks.py` | Die Prüfung nach jeder Operation eines Vorschlags (§26.5) |
| `proposal.py` | `Proposal`, `Question` |
| `apply.py` | `accept`, `discard`, `record`, `undo_applied` |
| `remote.py` | Die Schnittstelle nach außen: MCP über JSON-RPC |

Eine Operation, die der Agent kann und der Nutzer nicht, gibt es nicht; ein
Werkzeug, das an einer Op vorbei Geometrie anfasst, bricht Regel 2.
Mehrdeutigkeit endet in einer `Question`, nicht in einem Versuch (Regel 21).

## Vorschlag und Übernahme

- **Eine Umwandlung exakter Körper ist eine bewusste Übernahme**:
  `apply.auto_acceptable()` nimmt sie nicht automatisch, auch wenn der Befund
  nur Informationsstufe trägt (`Finding.converts_exact_body` ist die
  gemeinsame Erkennung); der Vorschlag bleibt mit Vorschau offen. `checks.check()` reicht neue Umwandlungsbefunde bis in
  Werkzeugantwort und Vorschlag; vor dem Zug vorhandene sperren keinen
  späteren, unabhängigen Vorschlag.
- `apply.changes_for()` bereitet Parameter, Passungen und Druckziel für
  Vorschau und Annahme aus dem jeweils aktuellen Dokument vor. Endet ein Zug
  mit ungeprüften Projektangaben, wertet `AgentSession` die Arbeitskopie
  abschließend aus — ein reiner Hauptmaß-, Passungs- oder Druckzielwechsel
  bekommt dieselben Befunde wie ein Operationsschritt, außer ein späterer
  Schritt hat sie schon geprüft.
- **Viele Formdetails bleiben ein Zustand**: Alle `fit.*`-Befunde der
  Passungsprüfung erreichen `checks.check()` und die Passungszeile des
  Steckbriefs — eine neue Diagnose braucht keine zweite Freigabeliste.
  `checks.check()` behält jeden Rohbefund; `checks.as_lines()` zählt
  `perceive.orphaned` und `perceive.mended` je Körper und Schritt, und
  `read_report` formatiert ebenso (Schwerepräfix, Schwerefilter) — sonst
  verdrängen hunderte wortgleiche Sätze den nächsten andersartigen Befund.

## Was für alle gilt, steht im Systemprompt

Ein Werkzeugschema beschreibt **seine** Operation; was für jedes Werkzeug
gleich gilt (`objects`, die Platzierungsangaben eines Bausteins aus
`PART_PLACEMENT_PARAMS` samt `nx`/`ny`/`nz` und dem Rückfall auf `axis`),
steht einmal im Prompt — wie im Handbuch einmal am Kopf der Kategorie.

- **Die Bedingung ist Wortgleichheit, nicht Namensgleichheit**: gestrichen wird
  nur, wo **alle** Felder aus `PART_PLACEMENT_PARAMS` beisammen sind; ein
  Werkzeug, das `x` aus eigenem Recht führt (verschieben, drehen), behält
  seinen Text. `tests/test_agent.py` prüft, dass jede Angabe **irgendwo**
  erklärt wird.
- **Was der Prompt verspricht, müssen die Werkzeuge tragen**: `session.py`
  entscheidet **einmal**, ob kompakt gefahren wird (`backend.id == "ollama"`),
  und reicht dieselbe Antwort an Prompt und Werkzeuge. Wer dem Prompt eine
  Zusage über die Werkzeuge hinzufügt, baut den Wächter dazu; jede
  Textänderung erhöht `PROMPT_VERSION`.

## Das Angebot für ein lokales Modell

`offer.ToolOffer` baut das Angebot des Zugs nach `agentenschicht.md`: jede
Operation in Registerreihenfolge, die gemeinten **ausführlich** (Kurzfassung
aus `tools.operation_tools(compact=True, part_placement=True)` plus
„Ort: …“), alle übrigen als **Kurzform** (Titel, `STUB_MARK`). Gemeint heißt
`registry.search.rank_operations` über Anfrage und letzte Nutzerbeiträge (nur
`SYNONYMS`), die Handlungen aus `perceive.actions.ACTION_ORDER` am gewählten
Merkmal, in leerer Szene die sichtbaren Grundkörper — von sich aus höchstens
`DETAILED_LIMIT`.

- Titel und Menüweg, die das Angebot selbst in eine Beschreibung setzt, gehen
  durch `tools.framed_if_foreign`: Bei einem mitgereisten Rezept enden beide
  mit dessen fremdem Titel (§32). Ein versteckter Zwilling trägt ausführlich
  den Satz aus `tools.second_choice_note`.
- **Eine Kurzform führt nichts aus**: Die Sitzung antwortet mit
  `ToolOffer.introduce`, zählt den Aufruf unter `Proposal.lookups` (nicht
  `tool_calls`, nicht `invalid_calls`) und schickt ab dem nächsten Schritt das
  ausführliche Schema; was `find_part` findet, ebenso. Der Prompt sagt es in
  `prompt._OFFER_HINT`. `tests/test_tool_offer.py` hält die Zusagen: keine
  Operation verschwindet, eine Kurzform führt nichts aus, das Angebot bleibt
  unter einem Drittel.

## Änderungen werden gemessen, nicht behauptet

Systemprompt, Regelsammlung oder Werkzeugbeschreibung geändert? Dann
`tools/run_agent_suite.py` (39 Referenzanfragen) **vorher und nachher** — er
kostet Geld und rund anderthalb Stunden je Modell, sein Exit-Code 1 ist eine
Quote, kein Fehlschlag. **Er braucht einen hinterlegten Schlüssel**
(`keys.read("anthropic")`), sonst endet er sofort mit „Kein Sprachmodell
erreichbar“ (Exit 2). Der Weg über Ollama taugt für diese Frage nicht: Eine
Quote, die von der Auslastung der Maschine handelt, misst nicht den Prompt.
Wer nicht abnehmen kann, sagt das — „gebaut und gemessen, aber nicht
abgenommen“ ist ein gültiger Stand. Verschlechtert sich die Quote, wird die
Änderung zurückgenommen.

## Fernwerte sind Daten

Der MCP-Pfadwächter erkennt explizite Pfadsyntax (`file:`, Laufwerke,
Verzeichnistrenner, Heimverzeichnis- und Punktsegmente); ein Punkt oder
Doppelpunkt mitten im Freitext macht keinen Dateizugriff, Objekt-, Profil-
und Beschriftungsnamen bleiben verwendbar. Importoperationen lesen nur im
Projekt registrierte Quellen über `ctx.sources`, nie einen Fernwert als
Dateinamen — neue Operationen halten dieselbe Grenze. Merkmalfelder aus
`kind="feature"`, `kind="features"` und `targets_feature` prüfen
unqualifizierte Kennungen und `obj_2:op5.hole_1` gleich; Passungspaare
brauchen immer einen qualifizierten Verweis, und auch darin bleiben lokale
Pfadangaben gesperrt.
