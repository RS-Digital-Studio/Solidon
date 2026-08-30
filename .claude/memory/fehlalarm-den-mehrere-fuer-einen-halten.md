---
name: fehlalarm-den-mehrere-fuer-einen-halten
description: "Ein Wächter-Befund, den drei Sitzungen als Fehlalarm einordneten, war echt — und die Begründung, die ich dafür schrieb, war plausibler als die Messung."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f1fa50e5-23de-4673-8c99-66e1556eff5d
  modified: 2026-08-30T21:24:41.735Z
---

Am 30.08.2026 war `test_no_number_reaches_the_user_past_the_localisation[panels.py]`
rot. Die gemeldeten Zeilen standen in `metrics.horizontalAdvance(f"{…:.2f}")` —
eine **Breitenmessung**, kein Text, der beim Nutzer landet. Zwei fremde
Sitzungen ordneten es als Fehlalarm ein und meldeten es als solchen weiter; ich
war beim ersten Lesen derselben Meinung.

Es war echt. Die Funktion verrechnet die Messung mit einer zweiten:

```
widest = breite von f"{minimum:.2f}"        # mit Punkt
frame  = sizeHint().width() - widest
return   breite von (spin.text() + "0") + frame   # spin.text() ist lokalisiert
```

`spin.text()` liefert den **angezeigten** Text, im deutschen Fenster mit Komma.
`widest` maß mit Punkt. Die Differenz landet über `frame` im Ergebnis.

**Die Regel daraus:** Eine reine Messung darf ein anderes Trennzeichen haben als
die Anzeige. Sobald ihr Ergebnis mit einer zweiten Messung *verrechnet* wird,
müssen beide dieselbe Schreibweise messen — sonst steckt die Differenz der
Trennzeichen im Ergebnis, und niemand sucht sie dort. „Das ist doch nur eine
Messung" ist deshalb kein Freibrief; die Frage ist, **was mit ihr geschieht**.

**Und der teurere Teil: Die Wirkung war null, meine Begründung behauptete mehr.**
Ich schrieb als Kommentar „Punkt und Komma sind in den meisten Schriften nicht
gleich breit — der Boden fiel damit in jeder Sprache um dieselbe Kleinigkeit
falsch aus". Das klang richtig und war ungemessen. Gemessen: **108 px in beiden
Fällen**, de_DE wie en_GB, Differenz 0.

Die Korrektur bleibt trotzdem richtig, aber aus einem anderen Grund als dem, den
ich hingeschrieben hatte: Die Rechnung soll **nicht davon abhängen**, welche
Schrift gerade gilt. Der Kommentar sagt jetzt die Null und diesen Grund.

**Wer eine Wirkung in einen Kommentar schreibt, hat sie gemessen — oder schreibt
hin, dass er sie nicht gemessen hat.** Eine plausible Zahl im Kommentar ist
schlimmer als keine: Sie beendet die Frage, ohne sie beantwortet zu haben.
Verwandt mit [[exakte-passung-ist-kein-beweis]] und
[[messwerkzeug-misst-sich-selbst]]; die Einordnung „Fehlalarm" gehört zur
Familie [[benannte-falle-schuetzt-nicht]] — je überzeugender die Erklärung, desto
sicherer verhindert sie die Prüfung.
