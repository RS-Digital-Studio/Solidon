---
name: entwickler-sieht-den-cache-fehler-nie
description: "Der Ergebniscache trägt einen Code-Hash im Pfad — jede Codeänderung verwirft ihn. Wer täglich baut, sieht Cache-Fehler nie; der Kunde fährt denselben Stand wochenlang. Zwei Fälle: Sprache, Dateiname — was die Op liest, gehört in den Schlüssel."
metadata:
  type: feedback
---

Am 31.08.2026 maßen zwei Sitzungen denselben Objektnamen und bekamen
verschiedene Werte: `Can Lid` bei der einen, `Dose Deckel` bei der anderen.
Beide Messungen waren richtig.

Die Ursache: `create_lid` baut den Namen sprachabhängig, der **Ergebniscache
speichert ihn mit**, und der Op-Hash kennt die Sprache nicht. Wer auf Deutsch
öffnet und dann auf Englisch umstellt, bekommt den deutschen Namen zurück.

**Der Teil, der über den Einzelfall hinausgeht, steht im Cache-Pfad:**

```
…/RS Digital/Solidon3D/cache/results/0.2.2+8a5c21
                                     ^^^^^^^^^^^^ Version + Code-Hash
```

Nach einem Commit hieß derselbe Ordner `0.2.2+296450`. **Jede Codeänderung
verwirft den gesamten Ergebniscache.** Daraus folgt, wen diese Fehlerklasse
trifft:

| | Code ändert sich | Cache-Fehler sichtbar |
|---|---|---|
| Entwickler | mehrmals täglich | fast nie — der Cache ist ständig frisch |
| **Kunde** | erst beim nächsten Update | **jedes Mal, wochenlang** |

Der Fehler ist für uns nahezu unsichtbar und für ihn dauerhaft. Er erklärt
auch, warum die zwei Sitzungen sich widersprachen: Die eine hatte nach einer
Codeänderung gemessen, die andere nach sechs Läufen mit demselben Stand.

**Why:** Wer nach jeder Codeänderung misst, stellt eine Lage her, die beim
Kunden nie vorkommt. Das ist die Kehrseite von „frisch messen ist sauber" —
für alles Zwischengespeicherte ist genau das der blinde Fleck.

**How to apply:** **Wer nach jeder Codeänderung misst, sieht nie, was der
Kunde sieht — er fährt denselben Stand monatelang.** Bei jedem Verdacht auf
zwischengespeicherte Werte den Cache **absichtlich warm** fahren: dieselbe
Lage zweimal, mit einer Änderung dazwischen, die den Op-Hash *nicht* berührt
(Sprache, Anzeigeeinheit, Thema, Profil). Wenn ein Wert dann nicht mitgeht,
ist er eingefroren.

Und die Gegenprobe zum Fix gehört dazu: **Der Cache darf zwischen beiden
Läufen nicht verworfen werden** — dieselbe Zahl an Einträgen vorher und
nachher ist der Beleg, dass der Fix heilt und nicht bloß leert. Hier: 10 → 10,
und der Name stimmte trotzdem, weil er jetzt ein `TranslatableText` ist statt
eines `str`.

**Zweiter Fall derselben Klasse, 26.09.2026 (Durchsicht 0.5.1):** Der
Schlüssel einer Quelle trug nur ihre Inhaltsprüfsumme, `load` liest aber
auch den **Dateinamen** (Körpername, Endung wählt den Leser). Eine
umbenannte Kopie einer früher geöffneten Datei kam mit dem alten Namen aus
dem Plattencache. Sichtbar wurde es nicht am Produkt, sondern als
reihenfolgeabhängiger Testfehler: Die Suite teilt ein Cache-Verzeichnis
über alle xdist-Arbeiter, und erst `--dist worksteal` stellte einen Test,
der dieselben Bytes als `deckel.stl` las, vor
`test_info_describes_the_evaluated_scene`.

Die allgemeine Frage an jeden Schlüssel: **Was liest die Operation außer
ihren Parametern?** Sprache, Dateiname, Endung, Profil — alles, was im
Ergebnis landet, gehört hinein. Und ein Test, der plötzlich den Wert eines
**anderen** Tests sieht, ist zuerst ein Verdacht auf den Plattencache, nicht
auf die Testreihenfolge.

Verwandt:
[[pruefstand-geht-den-weg-der-oberflaeche]] — der Kundenweg ist auch ein
Zeitverlauf, nicht nur eine Klickfolge.
