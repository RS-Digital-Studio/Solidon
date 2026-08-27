---
name: texte-altern-mit-ihrer-grenze
description: "Wer eine Fähigkeit hinzufügt, sucht die Texte, die ihre Abwesenheit versprochen haben — sie stehen selten in derselben Datei."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 33442ae8-b3cf-4eef-bce4-cf827af80603
  modified: 2026-08-26T22:57:39.833Z
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

**Und die Umkehrung gilt genauso: Wer eine Sache *streicht*, sucht die Texte,
die sie erwähnen — quer durch alle Module, nicht nur im Handbuch.** Am
26./27.08.2026 fiel der Punkt-Radius-Pinsel. Handbuch, Tour und Kataloge waren
nachgezogen, die Verneinungssuche gelaufen — und in
`app/ui/print_settings_dialog.py` stand am Farbfeld weiter „Mehrfarbig wird es
über *Bemalen* unter der Ansicht": ein **Kundentext**, der auf ein Werkzeug
zeigte, das es nicht mehr gab. Er lag in einem Dialogfeld, also weit weg von
der Sache, und keine Katalogprüfung schlägt an — der Satz ist ja übersetzt,
nur falsch.

Dieselbe Runde brachte zwei weitere Gestalten desselben Musters:
`figures.py` beschriftete die Werkzeugleiste **im gerenderten Bild** mit dem
gefallenen Werkzeug (wird nicht übersetzt, also prüft es niemand), und die
Suchwörter der Befehlspalette („anmalen", „pinseln") führten ins Leere.

**How to apply, zweite Hälfte:** Nach einem Ausbau grept man den Namen der
gestrichenen Sache über **alle** Verzeichnisse — `app/`, `tools/`, `website/`,
die Kataloge — und entscheidet je Treffer an seiner **Verwendung**: Kundentext,
gerendertes Bild, Suchwort, Kommentar oder historische Begründung. Nur das
Letzte darf stehen bleiben, und auch das mit einem Vermerk, dass es die Sache
nicht mehr gibt.

**Die dritte Gestalt sind Zahlen, und sie ist die leiseste.** Am 27.08.2026
rechnete ein Docstring in `panels.py` vor, warum am Flächenklick genau eine
Gruppe gefaltet wird: „19 Operationen, 10 Bausteine". Gemessen waren es 31 und
22 — der **Schluss** stimmte weiter, nur die Rechnung darunter beschrieb einen
Stand, den es nicht mehr gab, und wer sie beim nächsten Umbau als Grundlage
nimmt, rechnet mit zwölf Bausteinen zu wenig. Eine gemessene Zahl in einer
Begründung ist ein Messwert mit Datum, kein Argument: Sie gehört mit Datum
hingeschrieben und beim Anfassen neu gemessen, statt geglaubt.

Alle drei Gestalten — der tote Kundentext, die Zusage, die nur als Nebenwirkung
einer Sortierung überlebt, und die stumm gealterte Zahl — haben dasselbe
Verhalten: Sie halten, bis jemand *daneben* etwas ändert, und keine meldet sich
von selbst. Kein Test prüft einen Satz, keiner eine Zahl in einem Kommentar.

Verwandt: [[text-gesetzt-heisst-nicht-gezeigt]] und
[[fehlertexte-ohne-platzhalter]].
