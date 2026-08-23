---
name: texte-altern-mit-ihrer-grenze
description: "Wer eine Fähigkeit hinzufügt, sucht die Texte, die ihre Abwesenheit versprochen haben — sie stehen selten in derselben Datei."
metadata:
  type: feedback
---

**Ein Text, der eine Grenze beschreibt, altert mit der Grenze.** Am 23.08.2026
in Solidon: Der Satz „Es wird nichts geladen und nichts ersetzt" war richtig,
solange der Update-Weg wirklich nur ein Link war. Mit `download()` und
`start_installer()` wurde er falsch — nicht falsch geschrieben, falsch
**geworden**.

Für diesen einen Satz waren es am Ende:

    3 Stellen im Code      Tooltip Einstellungen, Tooltip Menü, ein Docstring
    2 x 5 Kataloge         alle fünf Sprachen, zweimal
    1 Website-Seite        datenschutz.html
    1 Vertragstext         EULA

**Why:** Beim Lesen sieht so ein Satz aus wie eine Zusicherung, die man gerade
prüft, nicht wie eine Behauptung, die man prüfen müsste. Ich habe die
betroffene Methode dreimal gelesen, während ich absicherte, dass nichts ohne
Klick geladen wird — und den Docstring direkt darüber, der das Gegenteil
behauptete, nicht als falsch erkannt. Gefunden hat ihn eine andere Sitzung,
und zwar nur, weil sie zwei Stunden vorher denselben Satz in einem ganz
anderen Format korrigiert hatte.

**How to apply:** Wer eine Fähigkeit hinzufügt, sucht **vorher** nach Texten,
die ihre Abwesenheit versprechen — im Code, in den Katalogen, auf der Website,
in den Rechtstexten. Der Suchbegriff ist die Verneinung dessen, was man baut
(„nichts", „nie", „kein", „ohne"), nicht der Name der neuen Sache. Und beim
Tauschen eines Katalogtexts muss der **alte Schlüssel raus**: Eine Prüfung,
die beide Richtungen kennt, meldet ihn sonst als „no longer used" — das ist
die Hälfte, die einen halben Umzug fängt.

Verwandt: [[text-gesetzt-heisst-nicht-gezeigt]] und
[[fehlertexte-ohne-platzhalter]].
