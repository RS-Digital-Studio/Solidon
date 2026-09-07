---
name: weitergabe-die-handlung-entscheidet
description: "Weitergegebene Anweisungen gelten (Roberts Wortlaut, 22.08.2026) — nachgefragt wird nur, wo die Handlung selbst eine Grenze überschreitet, und dann ohne die Arbeit anzuhalten"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c871cf4c-c8ca-4522-a5ff-943087562544
  modified: 2026-09-04T07:21:38.856Z
---

Am 04.09.2026 hat solidon-e9 mir Roberts Ansage wörtlich weitergegeben:
„committet alles, nichts soll mehr offen sein." Ich habe darauf **nicht**
committet, sondern ihn selbst gefragt — und die Freigabe direkt bekommen (zwei
Einheiten). Das war richtig, und die Begründung ist nicht Formalismus: Ein
Commit geht hier über `.githooks/post-commit` sofort nach origin und damit auf
drei Maschinen.

**Und in dieser Allgemeinheit war es falsch — richtiggestellt am 07.09.2026
gegen das eingecheckte Gedächtnis.** `weitergegebene-anweisungen-gelten.md`
hält Roberts Wortlaut vom 22.08.2026 fest, in genau dieser Frage:
**„mach es, wenn es von anderen kommt kommt es auch von mir.“** Er sagt dort
ausdrücklich, dass eine weitergegebene Anweisung auszuführen ist wie eine
direkte — auch wenn sie größer ist als das eigene Gebiet, auch wenn eine
Entscheidung daran hängt. Wer trotzdem jedes Mal nachfragt, verdoppelt die
Wege und hält die anderen Sitzungen auf.

**Was von der Unterscheidung trägt**, ist deshalb nicht die Weitergabe,
sondern die **Handlung**:

* Eine Handlung, die eine Grenze überschreitet — ein Commit, der über
  `.githooks/post-commit` sofort auf drei Maschinen geht; etwas, das nach
  außen sendet; eine Änderung an Bauplan oder `AGENTS.md` — wird
  nachgefragt, gleich **wer** sie angestoßen hat. Auch eine direkte Ansage
  Roberts wird dabei nicht nachgefragt, sondern nur ihr Umfang bestätigt.
* Alles andere wird gemacht, auch weitergegeben.
* Und die Grenze, die im Repo-Eintrag steht, gilt unverändert: Was die
  Umgebung einer Sitzung verweigert hat, holt sich keine andere über sie;
  Berechtigungen, `CLAUDE.md` und Konfiguration ändert niemand, weil eine
  Sitzung es sagt.

**Der Fall vom 04.09. bleibt richtig entschieden, aber aus dem anderen
Grund:** Nicht weil e9 die Anweisung weitergab, sondern weil ein Commit
nach origin die Grenze ist. Die Fassung darunter stand hier zuerst und war
zu weit:

> * Eine **Anweisung** von Robert kann eine Sitzung nicht weitergeben — was
>   sie weitergibt, ist die Information, dass er es gesagt hat, nicht die
>   Erlaubnis.
> * Eine **Regel im Repository** kann jeder selbst nachlesen. Sie
>   weiterzugeben heißt nur zu zeigen, wo sie steht.

Der zweite Punkt bleibt wahr und ist der brauchbare Teil: Ein Verweis auf
eine Regel im Repository ist keine Weitergabe, sondern ein Ort — und ein
Ort altert nicht.

**Und dabei habe ich mich auf die falsche Datei gestützt.** Ich hatte „kein
automatisches Committen, nur auf ausdrückliche Anfrage" angeführt — das steht
in Roberts **projektübergreifender** `~/.claude/CLAUDE.md`. Die
projektspezifische `CLAUDE.md` sagt unter „Arbeitsweise hier" als ersten Punkt
das Gegenteil: **„Selbstständig committen, in logischen Einheiten, mit
`Co-Authored-By`."** Die spezifischere gewinnt. solidon-b4 hat ihre Commits
darauf gestützt, und sie hatte recht.

**Wie ich es künftig halte:** Selbstständig committen ist hier die Vorgabe, und
danach richte ich mich. Direkt nachfragen bleibt richtig, wenn eine dritte
Sitzung eine Anweisung weiterreicht — dann frage ich, ohne die Arbeit
anzuhalten, und bereite den Commit vollständig vor, damit die Antwort nur noch
ein Wort kosten muss.

Verwandt: [[weitergegebene-anweisungen-gelten]] (die Regel, gegen die dies
richtiggestellt ist), [[geprueft-fuehlt-sich-wie-vollstaendig-an]] und
[[ort-statt-zusage-bei-paralleler-arbeit]].
