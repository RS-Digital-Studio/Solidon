---
name: was-die-suite-nicht-findet
description: "Sechs Fehler an einem Tag, sechs verschiedene Finder, kein einziger davon pytest — ein grüner Lauf ist eine Aussage über die Tests, die man geschrieben hat, und über nichts sonst."
metadata:
  type: feedback
---

**Am 25.08.2026 sind sechs Fehler in meiner eigenen Arbeit gefunden worden, und
die Suite hat keinen davon gefunden.** Gezählt wurde nicht, um sich zu geißeln,
sondern weil die Liste der *Finder* etwas sagt, das keine einzelne
Fehlerbeschreibung sagt:

| Fehler | Wer ihn fand |
|---|---|
| Gruppe des Rezepts würde `InternalError` werfen | ein Bildschirmfoto (der Wert stand deutsch im portugiesischen Dialog) |
| Drei Feldzeilen ohne Angabe, zu welchem Parameter sie gehören | dasselbe Bildschirmfoto |
| Eine von drei Knopfbedingungen war ungeprüft | eine Mutation im Code, nicht im Test |
| `op_ids` als Plätze statt IDs — der letzte Schritt fiel aus jedem Rezept | eine Nachbarsitzung im echten Fenster |
| Szene und Körper sind Wörterbücher — Kennungen statt Merkmale weitergereicht | das Lesen des Typs, weil ein `getattr(…, default)` verdächtig aussah |
| Ein deutscher Bezeichner unter 142 | eine vollständige AST-Durchsicht, angeregt von einer Nachbarsitzung |

Dazu am selben Tag: *Einpassen* wirkte im Skizzenmodus überhaupt nicht (Kamera
vor und nach dem Druck identisch), und ein Test, den ich dafür geschrieben
hatte, rechnete die Formel nach statt die Methode zu rufen — er blieb grün, als
der Fehler zurück in den Code gesetzt wurde.

**Why:** Ein grüner Lauf ist eine Aussage über die Tests, die man geschrieben
hat, und über nichts sonst. Er sagt nichts über das, was keinen Test hat, und
er sagt besonders wenig über die Nähte zwischen zwei Modulen: Dort baut jeder
Test die eine Seite selbst und bekommt die andere als Attrappe — und eine
Attrappe bestätigt die Annahme, die man beim Schreiben hatte. Vier der sechs
Fehler oben liegen genau dort.

**How to apply:** Nach einer Änderung an der Oberfläche gilt die Reihenfolge
**ansehen, mutieren, durchfahren** — und zwar zusätzlich zur Suite, nicht
statt ihrer.

* **Ansehen** heißt: das Fenster rendern und das Bild lesen, unter der echten
  Plattform und in einer fremden Sprache ([[oberflaeche-von-hand-fahren]]).
  Zwei der sechs standen im Bild und in keinem Testergebnis.
* **Mutieren** heißt: jede Bedingung einzeln kaputt machen und den Test dabei
  ansehen — **im Code, nicht im Test**. Eine Gegenprobe, die den Test ändert,
  prüft, ob der Test zu sich selbst passt ([[sollwert-aus-dem-pruefling]]).
* **Durchfahren** heißt: den Weg gehen, den der Kunde geht, vom Knopf bis zum
  Ergebnis. Die Methode dahinter zu rufen prüft die Methode und nicht den Weg.

Und wenn ein Prüfstand nichts findet, ist die erste Frage, ob er etwas
angesehen hat ([[messwerkzeug-misst-sich-selbst]]): Mein Sprachprüfstand baute
denselben Dialog sechsmal auf Deutsch, schrieb sechs Dateien und sah
vollständig aus. Dieselbe Falle wie ein Verbotstest über eine leere Menge.

## Die häufigste Klasse hat keine Signatur im Quelltext

Am 03.09.2026 fanden **fünf Sitzungen unabhängig voneinander denselben
Fehlertyp**, und die Commit-Titel lesen sich wie Varianten eines Satzes:

* „Der Dialog fragte nach der Schraubengröße und bot keine Antwort an"
* „Der Befund nannte den Ausweg und bot ihn nicht an"
* „Der Agent ordnete auf Platten an und sah das Ergebnis nicht"
* „Die Ansicht vergaß, wie man sie eingestellt hatte"
* „Auto Split schnitt offene Netze und sagte nichts dazu"

Jedes Mal ist die Auskunft **da** und kommt beim Kunden nicht an.

**Und ein Wächter dafür ist gemessen unmöglich.** 3d-druck-85 hat es geprüft,
bevor sie einen baute: 36 Stellen in ``app/`` werfen einen Teil eines
Rückgabewerts weg, und **null** davon tragen eine Auskunft — alles numerische
Nebenwerte aus numpy, marching_cubes, partition. Der Wächter wäre grün gewesen
und hätte Sicherheit vorgetäuscht, wo keine ist; das ist schlechter als keiner.

Der Grund steht in ihrer Diagnose, und sie ist genauer als „Auskunft
verworfen": Die Fälle sind **„nie erzeugt oder nie abgerufen"**. Eine Funktion,
die einen Grund zurückgibt, den niemand ruft, sieht im Quelltext aus wie jede
andere; ein Aufruf, der an der falschen Stelle steht, ebenso. Zweimal an einem
Tag im Druckweg: ``settings_for_export`` löste die Werte an seiner eigenen
Stelle auf, sodass der Ausgang im Kern nie erreicht wurde — und
``chosen_machine`` wurde bei der Ersteinrichtung gefragt statt bei der
Übergabe, wo die Antwort etwas geändert hätte.

**Alle fünf kamen aus dem Durchfahren aus Kundensicht. Keiner aus einem Test.**
Das ist der Satz, für den diese Notiz da ist — hier steht er zum zweiten Mal,
mit fünf Fällen an einem Tag statt sechs.

## Zum dritten Mal, und diesmal mit dem Grund (03.09.2026)

Zwei Sitzungen zählten am selben Abend unabhängig dasselbe. a0: „Von
den letzten **sechs** Funden in meinem Gebiet kam **keiner** aus meinen
eigenen Tests." Bei mir dieselbe Bilanz über den ganzen Tag:

| Fund | wer fand ihn | wie |
|---|---|---|
| Verrundungen mit Radius 0,0007 mm | 7f | Objektbaum eines Kundenmodells angesehen |
| eine Senkung als drei Kegel | a0 | beim Gegenlesen eines Changelogs |
| Körper springt nach dem Loslassen zurück | Robert | am Bildschirm |
| Cache hält bis zu 991 MiB | Robert (Auftrag an 06/19) | gezielte Suche nach einer Fehlerklasse |
| Kugelpfanne wird zur Senkung | ich | 81s Frage nach weiteren Zwillingen |
| sieben von acht Szenenaufbauten unnötig | ich | beim Messen des Rücksprungs |

**Keiner kam aus der Suite, und keiner aus einem Test, den es schon gab.** Vier
kamen von außen — ein Kunde, ein Fragebogen, ein fremdes Gegenlesen,
eine fremde Frage.

**Der Grund, den a0 benannt hat und der die Notiz ergänzt:** Die Tests
waren dabei nicht schlecht, sie waren grün *und* richtig. Sie maßen
nur

* den richtigen Wert an der **falschen Bauart** (der Testkorpus hat keine
  tesselierte Kunst, also keine Verrundung mit einem Tausendstel Radius),
* an der **falschen Auflösung** (die Kugelpfanne kippt zwischen 482 und
  1602 Dreiecken; ein Test mit der groben Variante sieht den Fall nie),
* gegen einen **vorgestellten Sollwert** (halbe Kugel statt 4-mm-Kalotte).

Alle drei sind Eigenschaften des **Prüfkorpus**, nicht der Zusicherung.
Ein Test kann nur falsch werden, wo sein Gegenstand die Sache trifft.

**Was praktisch daraus folgt** — über „aus Kundensicht durchfahren"
hinaus, das oben schon steht:

* **Dieselbe Sache in mehreren Auflösungen messen.** Der teuerste Fund des
  Tages (feineres Netz, schlechtere Erkennung) war nur sichtbar, weil derselbe
  Körper dreimal mit verschiedener Feinheit durchlief. Eine Auflösung ist
  eine Stichprobe.
* **Echte Kundendateien in den Prüflauf**, nicht nur den Korpus. Die Modelle in
  `Downloads` haben heute drei Funde geliefert, die kein selbst gebauter
  Körper hatte.
* **Fremdes Gegenlesen ist die produktivste Sorte Test.** Vier der sechs kamen
  von jemandem, der etwas anderes suchte.

Verwandt: [[eine-kette-endet-am-letzten-glied]], [[text-gesetzt-heisst-nicht-gezeigt]].
