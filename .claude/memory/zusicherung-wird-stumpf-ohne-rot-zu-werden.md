---
name: zusicherung-wird-stumpf-ohne-rot-zu-werden
description: "Eine Änderung an anderer Stelle kann einem Test die Schärfe nehmen, ohne ihn rot zu machen — er bleibt grün und prüft nichts mehr."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cc0c50ad-6ea5-4d75-b0d4-2e514a473ea3
  modified: 2026-08-30T22:37:52.973Z
---

Am 31.08.2026 stand die Umstellung an, die Prüfbefunde der Börse aus einer
gemeinsamen Textquelle zu holen statt aus zwei Stellen im Code. Richtig, nötig,
und sie hätte meinen wichtigsten Test entwaffnet.

`test_both_checks_agree_on_the_same_file` vergleicht die **Sätze**, die App und
Server über dieselbe Datei sagen. Solange beide Seiten ihre Sätze selbst bauen,
ist das eine echte Zusicherung. Sobald beide sie aus derselben JSON lesen,
vergleicht er zwei **Lesevorgänge derselben Datei** — und die stimmen immer
überein, auch wenn die Prüfungen darunter Verschiedenes gefunden haben.

**Why:** Der Test wäre nicht rot geworden. Er wäre grün geblieben, hätte
ausgesehen wie vorher, und niemand hätte einen Anlass gehabt, ihn anzusehen.
Gefunden hat es 72 beim Lesen des Vorschlags — nicht ein Lauf, nicht eine
Messung, sondern jemand, der fragte, *was* der Test nach der Änderung noch
vergleicht.

Der Beleg dafür ist gemessen und lag schon vor: Die Mutationsprobe zu diesem
Test war `mb_strlen` → `strlen`, und sie wurde rot, **weil die Zahl im Satz
stand** („200 Zeichen" gegen „400 Zeichen"). Nach der Umstellung stünde dort
nur noch der Schlüssel, und dieselbe Mutation liefe durch.

Die allgemeine Form ist unangenehmer als die üblichen Testfallen: `tests.md`
kennt „Sollwert aus dem Prüfling" und „ein Verbotstest über eine leere Menge".
Beide entstehen **beim Schreiben** des Tests. Dieser hier entsteht später, an
einer ganz anderen Stelle, durch eine Änderung, die für sich richtig ist.

**How to apply:**

* **Vor einer Umstellung fragen, was der Test danach noch vergleicht** — nicht
  ob er noch läuft. Die Frage lautet: Können beide Seiten jetzt aus derselben
  Quelle antworten, ohne dieselbe Arbeit getan zu haben?
* **Die Mutationsprobe wiederholen, nachdem umgestellt ist.** Wird sie nicht
  wieder rot, ist der Test nach der Änderung nichts mehr wert. Eine einmal
  bestandene Probe gilt für den Stand, an dem sie lief.
* **Wo zwei Seiten dasselbe Urteil fällen sollen, vergleicht man die
  Entscheidung und ihre Zahlen** (`code` **und** `values`), nicht den
  formulierten Satz. Der Satz ist Anzeige; er darf aus einer gemeinsamen
  Quelle kommen. Das Urteil muss zweimal unabhängig entstehen.

Verwandt: [[sollwert-aus-dem-pruefling]] (dort zieht der Autor den Sollwert aus
dem Prüfling, hier zieht ihn eine spätere Änderung hinein),
[[messwerkzeug-misst-sich-selbst]] und [[was-die-suite-nicht-findet]] — auch
hier fand es kein Lauf, sondern ein Leser.
