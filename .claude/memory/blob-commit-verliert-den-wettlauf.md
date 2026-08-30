---
name: blob-commit-verliert-den-wettlauf
description: Zwischen Blob-Bau und commit kann HEAD weiterrücken — dann scheitert der Commit hart, und das ist die gute Nachricht
metadata:
  type: feedback
---

Ein Commit über einen Blob aus `HEAD` scheitert mit

    fatal: cannot lock ref 'HEAD': is at <neu> but expected <alt>

wenn eine andere Sitzung zwischen `read-tree` und `commit` gelandet ist. Der
Commit fällt dann **nicht** — er ist einfach nicht passiert. Der Griff ist
immer derselbe: Blob **neu aus dem jetzigen HEAD** bauen und sofort committen.

**Why:** Am 31.08.2026 zweimal in einer Stunde, bei sechs gleichzeitigen
Sitzungen. Das Fenster ist genau so groß wie die Sorgfalt dazwischen — die
Sollprobe, das Lesen der Zahlen, das Prüfen auf fremde Marken. Wer gründlich
misst, vergrößert es.

Die eigentliche Gefahr steht daneben und ist die stille: **Der Blob altert
schneller als der Index.** Ein `git read-tree HEAD` ist in dem Moment richtig,
in dem er läuft; der Blob, den ich danach aus `git show HEAD:<pfad>` baue,
ebenso. Rückt HEAD dazwischen, hält der Ref-Lock den Commit auf — deshalb ist
dieser Fehler ein **Schutz** und kein Ärgernis. Ohne ihn hätte ich den fremden
Commit stillschweigend zurückgenommen, genau wie ein `-o` es täte.

**How to apply:** Die Kette so kurz wie möglich halten — messen und prüfen
**vor** `read-tree`, dann in einem Zug Index bauen, Blob setzen, Zahlen
ansagen, committen. Scheitert es trotzdem, nicht den Blob wiederverwenden:
neu bauen, denn er trägt den alten Stand. Verwandt:
[[index-altert-zwischen-lesen-und-commit]] (dieselbe Uhr, andere Seite) und
[[geteilter-index-haelt-alten-stand]].
