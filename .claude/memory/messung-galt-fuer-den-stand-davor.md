---
name: messung-galt-fuer-den-stand-davor
description: "Nach einem Umbau gilt jede frühere Messung nur noch für den alten Stand — und wer nur die Lage nachmisst, die der Umbau betraf, prüft die falsche."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cc0c50ad-6ea5-4d75-b0d4-2e514a473ea3
  modified: 2026-08-31T06:57:31.716Z
---

Am 31.08.2026 habe ich das Kopfmenü der Website gebaut: am Rechner eine Leiste,
am Handy ein Aufklapper, aus einem Markup. Gemessen in drei Breiten, alles
grün. Dann kam ein Umbau — die sechs Verweise bekamen einen `<div>` um sich,
damit das Panel am Handy schweben kann statt zu schieben.

**Danach habe ich nur noch bei 375 Punkt gemessen.** Die Handy-Lage war ja die,
die der Umbau betraf. Am Rechner standen die sechs Verweise seitdem
untereinander in einer 160 Punkt schmalen Spalte — alle bei x=1245, auf sechs
Zeilen von 31 bis 177. Es ging so über zwei Commits hinaus und fiel erst auf,
als ich ein Bildschirmfoto für etwas ganz anderes machte.

**Why:** Die Desktop-Messung von vorher war nicht falsch. Sie war *richtig* —
für einen Stand, den es nach dem Umbau nicht mehr gab. Genau deshalb ist sie
gefährlicher als ein Fehler: Ein falscher Wert fällt irgendwann auf, ein
gültiger Wert über einen vergangenen Zustand nie.

Der Denkfehler steckt in „die Lage, die der Umbau betraf". Ein Umbau am Markup
betrifft **jede** Lage, die dieses Markup rendert — die Media Query entscheidet
nur, welche Regeln dazukommen, nicht welche Struktur da ist.

**Die technische Lehre daneben ist eigenständig:** Chromium nimmt den Inhalt
eines geschlossenen `<details>` über `content-visibility` **aus dem Layout**.
Das Element bleibt im Baum, misst null, und seine Kinder liegen alle auf seiner
Position. Eine eigene `display`-Regel macht sie sichtbar — und gibt ihnen
**keinen Platz zurück**. Wer `display` benutzt, um Inhalt aus einem `details`
herauszuholen, bekommt sichtbare Elemente ohne Layout. Die Lösung ist, den
Inhalt gar nicht erst hineinzulegen: Das Panel steht als **Geschwister** neben
dem Aufklapper, und `[open] + .panel` blendet es ein.

**Und die Messung selbst hat gelogen, weil ich sie falsch gefragt habe.**
`offsetParent` und `getBoundingClientRect()` meldeten „sechs sichtbar" —
beide antworten auf „hat es eine Box", nicht auf „ist es zu sehen". Was die
Frage beantwortete: die Positionen **aller** Elemente nebeneinanderlegen. Sechs
gleiche x-Werte sind eine Antwort, „sechs sichtbar" ist keine.

**How to apply:**

* **Nach einem Umbau am Markup jede Lage neu messen, nicht die geänderte.**
  Die Frage ist nicht „was habe ich angefasst", sondern „welche Zustände
  rendern dieses Markup".
* **Eine Zählung ist keine Prüfung.** „Sechs sichtbar" hat hier zweimal
  bestanden, während nichts zu sehen war. Wo eine Anordnung geprüft wird,
  gehören die **Koordinaten** ins Protokoll — gleiche Werte verraten
  Stapelung, verteilte verraten eine Reihe.
* **Ein Bildschirmfoto ist keine Zierde am Ende.** Gefunden hat es das Auge,
  nicht der Wert. Bei allem, was Anordnung betrifft, ist das Foto die
  Messung und die Zahl nur der Beleg.

Verwandt: [[abgelesene-zahl-altert-still]] (dort altert die Zahl im Text, hier
im Kopf des Messenden), [[gemessene-frage-ist-nicht-die-gestellte]],
[[zusicherung-wird-stumpf-ohne-rot-zu-werden]] — auch dort bleibt eine Prüfung
formal gültig und sagt nichts mehr.

---

**Die Kehrseite, gefunden von 15 am selben Tag: eine falsche Entwarnung ist
teurer als eine Fehlmeldung.**

Sie meldete mir einen Befund an meinem CSS-Umbau — roh, ohne Ursache, weil sie
ihn nicht auflösen konnte. Dann fand sie einen Fehler in ihrer **eigenen**
Messung (ihr Browser hielt eine veraltete Seite) und zog den Befund daraufhin
zurück.

**Beides war gleichzeitig wahr.** Ihr Browser war veraltet **und** sechzehn
Kartenkanten waren wirklich zugedeckt — ein Sammelblock 200 Zeilen weiter
unten setzte allen den alten Schatten wieder auf. Der eine Umstand widerlegt
den anderen nicht; sie hat genau das angenommen, und ich hätte fast aufgehört
zu suchen. Mein eigenes Foto sah gut aus.

Ihre Erklärung, warum es passiert, ist die übertragbare Hälfte: **Ein eigener
Fehler erklärt die Beobachtung plausibel, und Plausibilität fühlt sich wie
Beweis an** — besonders, wenn der Fehler peinlich ist. Man hat gerade etwas
über sich gelernt, das ist Bestätigung genug, und die Frage nach der Sache
selbst fällt aus.

**Die richtige Meldung lautet: „Meine Messung war unbrauchbar, der Befund ist
damit offen."** Nicht „Entwarnung". Eine Fehlmeldung kostet den Empfänger zehn
Minuten; eine falsche Entwarnung kostet den Fund — und liefert ihm noch eine
gute Begründung dafür, nicht weiterzusuchen.

**Und der Fund selbst hat eine eigene Lehre:** Der Sammelblock trug einen
Kommentar, der behauptete, er stehe früh genug, um überschrieben zu werden.
Er stand 200 Zeilen zu spät. **Ein Kommentar, der eine Reihenfolge behauptet,
ist keine Reihenfolge** — und er hat mich beim Lesen zweimal beruhigt, bevor
ich nachgezählt habe. Das ist die Schwester von
[[benannte-falle-schuetzt-nicht]]: Der Satz liest sich als Beleg, dass jemand
nachgedacht hat, und genau deshalb prüft die Stelle niemand ein zweites Mal.
Wo eine Regel von der Reihenfolge abhängt, macht man sie besser von ihr
unabhängig — hier: derselbe Wert in beiden Blöcken.

---

**Die billigste Gegenprobe, die es gibt — und sie braucht keinen Sollwert:**

> Wer eine Größe misst, sollte einmal absichtlich am Eingang drehen. Bewegt
> sich das Ergebnis nicht, misst man nicht, was man glaubt.

Sie ist die kleine Schwester von [[messwerkzeug-misst-sich-selbst]] („an einem
Fall mit bekanntem Ausgang prüfen"). Die ist schärfer, setzt aber voraus, dass
es einen solchen Fall gibt. **Diese hier geht immer**, denn man muss nur
wissen, dass sich etwas ändern *muss* — nicht wohin.

Zwei Belege vom 31.08.2026, beide teuer bezahlt: Meine Messung meldete zweimal
„sechs sichtbar", während sich darunter alles verschoben hatte. 15 setzte vier
verschiedene Breiten und bekam bei zweien denselben Zeichenwert, weil ein
geschlossenes `<details>` gar kein Layout hat.

**Ihre Ergänzung ist der praktische Teil: In einer Reihe fällt es von selbst
auf.** Ein einzelner Wert sieht plausibel aus; vier Eingänge mit vier gleichen
Antworten nebeneinander liest niemand als Messung. Sie hatte 891, 629, 579 und
530 Punkte gemessen — und erst als die Reihe vollständig dastand, sah sie es.
Wer nur einen Wert protokolliert, hat die Probe nicht gemacht, sondern nur
gemessen.

**Und im geteilten Baum kommt eine dritte Alterung dazu**, die 15 so
formuliert hat: *„Eine Zahl altert schneller als der Gedanke, der auf ihr
steht."* Ihre Messung der Kartenbreite war bei 1440 Punkten richtig — bis ich
dieselben Karten eine Stunde später umgebaut hatte. Nicht ihr Cache, nicht ihr
Fehler: fremde Arbeit zwischen Messung und Schluss. Wer im geteilten Baum eine
Zahl weiterverwendet, prüft vorher, ob ihr Gegenstand noch derselbe ist.

---

**Und die dritte Gestalt, am selben Tag: den Quelltext gemessen statt das
Bild.**

Auf der Suche nach Stellen, die ein Register (Tabs) verdienen, habe ich die
Changelog-Seite ausgemessen: 53 685 Zeichen, acht Versionen, 29 Abschnitte. Der
Schluss lag nahe — eine Bleiwüste, die dringend eine Gliederung braucht. Ich
war schon dabei, den Erzeuger umzubauen.

**Sieben der acht Versionen tragen `hidden`.** Die Seite hat längst einen
Versionswähler, und der Kunde sieht genau eine. Ohne JavaScript zeigt ein
`<noscript>`-Block alle — mit einem Satz, der es erklärt. Vorbildlich gebaut,
und ich hätte es überschrieben.

**Der Fehler ist genau der, den ich am selben Morgen bei meinem eigenen Menü
gemacht habe, nur andersherum:** Dort meldete die Messung „sichtbar", während
nichts zu sehen war; hier meldete der Quelltext „viel", während wenig zu sehen
ist. Beide Male habe ich eine Eigenschaft der **Datei** für eine Eigenschaft
der **Anzeige** genommen.

**How to apply:** Vor jedem „das ist zu viel / zu lang / zu unübersichtlich"
zählt nur, was gerendert im Bild steht. `hidden`, `display:none`,
`content-visibility` und ein Wähler machen aus zehn Abschnitten einen. Die
billigste Prüfung ist ein Blick in die Datei nach `hidden` — die zweitbilligste
ein Bildschirmfoto.

## Und in einer Freigabe altert sie am schnellsten

03.09.2026, Release 0.3.0. In meiner Freigabemeldung stand „Aktivierungsdienst
bereit". Gemessen war das um **02:26:28**, geschrieben wurde es um **05:29** —
und dazwischen hat eine andere Sitzung alle vier Endpunkte auf **503**
gemessen. Meine Zahl war zum Zeitpunkt ihrer Messung richtig und zum Zeitpunkt
ihrer Verwendung eine Behauptung über die Gegenwart, die sie nicht deckte.

Eine Freigabe ist der Ort, an dem das am teuersten ist: Sie besteht aus
lauter Messungen, die zu verschiedenen Zeiten entstanden sind, und liest sich
als **ein** Zustand. Wer sie zusammenschreibt, macht aus einer Zeitreihe eine
Momentaufnahme, ohne es zu merken.

**How to apply:** In einer Freigabe steht neben jeder Zahl, **wann** sie
gemessen wurde. Was älter ist als der letzte Eingriff in das gemessene System
— hier der Upload —, wird vor der Meldung neu gefahren, nicht zitiert. Und
was flackern kann, wird nicht einmal gemessen, sondern über eine Spanne
beobachtet: Ein Dienst, der zweimal antwortet, kann dazwischen unten gewesen
sein.
