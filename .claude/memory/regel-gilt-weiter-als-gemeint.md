---
name: regel-gilt-weiter-als-gemeint
description: "Eine richtige Regel mit ungeprüftem Geltungsbereich — dreimal an einem Morgen, in drei Dateien ohne Zusammenhang; die Frage lautet: wo gilt das noch, wo ich es nicht gemeint habe?"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4e2b249b-1d42-4020-bb0e-bdcf350ef625
  modified: 2026-08-31T04:57:40.907Z
---

Am 31.08.2026 fielen an einem Vormittag drei Befunde derselben Gestalt auf,
in drei Dateien, die nichts miteinander zu tun haben:

* **`prefers-reduced-motion`** schaltete im Aufmacher nicht nur die
  Scroll-Drehung ab, sondern das ganze Skript — **auch den Regler**. Wer die
  Einstellung gesetzt hatte, bekam einen Knopf, der auf keinen Klick
  antwortete.
* **`min-height: 8rem`** auf einem Ergebnisfeld sollte das Springen beim Laden
  verhindern und galt auch, wenn nichts lud: unter einem einzigen Satz standen
  acht Zeilen Leere.
* **`section { padding: 3.5rem 0 }`** galt bei 5673 Zeichen Inhalt wie bei 101
  Punkten Höhe — Faktor 37 zwischen der dünnsten und der dichtesten Sektion.

Jede der drei Regeln ist **richtig**. Falsch war jedes Mal nur, wo sie außerdem
noch gilt.

**Why:** Beim Schreiben prüft man den Fall, für den man die Regel baut — er ist
der Anlass, er steht vor Augen, und er stimmt. Der Rand ist der, an den niemand
denkt, **weil er nicht der Anlass war**. Das ist die Gegenrichtung zu
[[waechter-sieht-nur-das-getane]] und zur Lehre „ein Wächter ist so scharf wie
seine weiteste Ausnahme": Dort ist die *Ausnahme* zu weit, hier die *Regel*.

Der teuerste der drei war der erste, und zwar nicht, weil er am schlechtesten
aussah: Er schaltete die **Bedienung** ab — für genau die Besucher, die eine
Einstellung gesetzt haben und deshalb am wenigsten damit rechnen, dass etwas
kaputt ist. Eine Regel, die Rücksicht nehmen soll, wurde zur Ausgrenzung.

**How to apply:** Nach jeder neuen Regel — CSS-Selektor, `@media`-Block,
`if`-Zweig, Wächter-Muster — **einen Satz** fragen: *Wo gilt das noch, wo ich
es nicht gemeint habe?* Die Frage zielt auf den **Rand** und nicht auf den
Kern; der Kern ist ja der Anlass und stimmt.

Zwei Prüfmuster, die den Rand sichtbar machen:

* **Die Bedingung umkehren und einmal hinsehen.** Was zeigt die Seite, wenn
  *nichts* lädt, wenn der Inhalt *kurz* ist, wenn die Bewegung *abbestellt*
  ist? Das ist billiger als jede Überlegung — der Browser beantwortet es in
  Sekunden (`--force-prefers-reduced-motion` und Geschwister).
* **Trennen, was verschiedene Gründe hat.** „Automatische Bewegung" und
  „Bedienung auf Geste" standen in einem Block, weil beide mit Bewegung zu tun
  haben. Sie haben verschiedene Gründe und gehören deshalb in zwei.

Dasselbe gilt für Repository-Regeln. „Keine Toleranz als Zahl" schützt
Fertigungsspiel, verbietet aber ohne benannten Geltungsbereich versehentlich
`EPS_GEOM`; „jede Ausnahme braucht eine Handlung" schützt den Nutzer, fordert
aber für eine interne Assertion sonst einen erfundenen Knopf. Eine harte Regel
wird nicht weicher, wenn sie den richtigen Rand benennt. Sie wird prüfbarer:
Fertigungswerte kommen aus Projekt oder Profil, Rechentoleranzen aus den drei
benannten Konstanten; jeder nutzersichtbare `AppError` führt weiter, interne
Programmierfehler werden diagnostiziert und an der Oberflächengrenze übersetzt.
