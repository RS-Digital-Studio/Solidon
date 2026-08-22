# Korrektur am Rechercheergebnis „Claude Code"

Der Rechercheur hat für den Cluster *Claude Code* aus **„steht nicht in der
Dokumentation"** auf **„gibt es nicht"** geschlossen. Das ist ein Fehlschluss,
und mindestens drei seiner zwölf Karten sind dadurch falsch. Die Redaktion darf
diesen Cluster nicht ungeprüft übernehmen.

## Nachweislich falsch

- **`argument-hint` gebe es nicht.** Falsch. Sieben Skills dieses Projekts
  führen das Feld und werden damit benutzt:
  `bauplan`, `neue-op`, `neuer-baustein`, `neues-druckteil`, `pruefen`,
  `regelcheck`, `roadmap` — jeweils Zeile 7 oder 8 in `SKILL.md`.
  Die Behauptung des Bedienkonzepts stimmt.

- **`run_in_background` gebe es nicht.** Falsch. Es ist ein Parameter des
  Bash-Werkzeugs und des Agent-Werkzeugs in der laufenden Sitzung; die
  Werkzeugbeschreibung nennt ihn ausdrücklich, und diese Durchsicht hat ihre
  eigenen Läufe damit gestartet. Die Behauptung des Bedienkonzepts stimmt.

- **Kapitelmarken seien „nicht als Feature exponiert".** Irreführend. Das
  Werkzeug `mark_chapter` steht in dieser Sitzung zur Verfügung und legt
  Kapitel samt Inhaltsverzeichnis an. Die Behauptung des Bedienkonzepts —
  „das Werkzeug gibt es, benutzt wurde es nicht" — trifft damit weiterhin zu.

## Missverstanden

- **Scratchpad.** Das Konzept sagt „über die Sitzung hinweg", also *während*
  der Sitzung. Der Rechercheur hat es als „über Sitzungen hinweg" gelesen und
  widerlegt, was niemand behauptet hat. Beides ist richtig: innerhalb der
  Sitzung verfügbar, zwischen Sitzungen nicht.

## Wahrscheinlich richtig, aber schwach belegt

Die Aussagen zu den Meldungstexten („The task tools haven't been used
recently", „PostToolUse hook modified X after your edit", „the file had been
modified on disk since you last read it") sind Beobachtungen aus einer echten
Sitzung im Juli/August 2026. Dass sie nicht in der Dokumentation stehen, sagt
nichts über ihre Existenz — Laufzeitmeldungen stehen dort selten. Sie bleiben
im Konzept, aber mit dem Vermerk, dass sie Beobachtung sind und sich mit der
Fassung ändern können.

## Was aus dem Cluster brauchbar ist

Die *Ergänzungen* — was seit Juli 2026 dazugekommen ist (Agent View für
Hintergrundsitzungen, Worktree-Isolation je Sitzung, Workflows unter
`.claude/workflows/`) — sind neu und gehören in die Bedienkonzepte. Nur die
Negativurteile sind unbrauchbar.
