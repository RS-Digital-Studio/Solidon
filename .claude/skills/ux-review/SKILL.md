---
name: ux-review
description: >
  Entwirft und prüft konkrete Nutzerabläufe in Solidon und auf der Website und
  setzt sie auf Auftrag um: Auffindbarkeit, Schritte, Rückmeldung,
  Fehlerbehebung, Abbruch, Undo und Tastaturbedienung. Benutzen bei
  umständlicher Bedienung, neuen Abläufen und UX-Abnahmen in der Sitzung. Eine
  unabhängige, nur lesende Ablaufanalyse der Anwendung übernimmt der Agent
  bedienlogik; visuelle Gestaltung über /ui-design.
argument-hint: "[Ablauf, Ansicht oder Nutzerziel]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Bedienabläufe prüfen

## Nutzerauftrag und Ist-Ablauf

Das konkrete Ziel und den Startzustand festhalten: vorhandenes Modell oder
leeres Projekt, Auswahl, Vorkenntnisse, Eingabegerät. Den heutigen Ablauf aus
den wirklichen Aufrufern, Ereignissen und Zuständen ermitteln und bei
verfügbarem UI-Zugang selbst fahren; einen nur aus dem Code abgeleiteten
Ablauf als solchen kennzeichnen.

Maßstab für die Anwendung ist Bauplan §2 im Wortlaut — die vier Hauptwege
(§2.2) müssen ohne Handbuch gehen, und jeder Ablauf wird daran gemessen, ob er
einen davon verlängert oder verkürzt —, dazu §19 und die Regeln der berührten
Oberfläche (`.claude/rules/oberflaeche.md`, `wartezeit.md`, `fenster.md`,
`grenzen.md`). Die Zielgruppe hat keine CAD-Kenntnisse und kommt aus dem
Slicer. Für die Website gelten `website/CLAUDE.md` und `website/README.md`.

## Ablauf aufnehmen

Je Schritt:

| Ausgangszustand | Was der Nutzer sieht | Handlung | Rückmeldung und neuer Zustand | Rückweg |
|---|---|---|---|---|
| Konkrete Auswahl und vorhandene Daten | Sichtbarer Einstieg und verfügbare Werte | Klick, Taste oder Eingabe | Tatsächlich beobachteter Effekt | Abbruch, Zurück oder Undo, soweit vorhanden |

Den Hauptweg und seine realistischen Randfälle untersuchen: keine oder mehrere
Auswahlen, ungeeignete Eingabe, laufende Berechnung, Abbruch, Fehler und
erneuter Versuch. Nach einer Änderung den gemeinsamen Mutationspunkt und alle
Einstiege prüfen, die dieselbe Handlung auslösen — Menü, Kontextaktion,
Kürzel, Agent. Eine neue Beschriftung repariert keine falsche Zustandsfolge.

## Bewertung

- **Auffindbarkeit:** Ist der nächste Schritt aus dem aktuellen Zustand
  verständlich, ohne den Namen eines internen Moduls zu kennen? Eine Funktion,
  die man nicht findet, gibt es nicht.
- **Aufwand:** Schritte, Klicks, Blickwechsel und Entscheidungen vorher und
  nachher zählen. Weniger ist nur besser, wenn Klarheit und Kontrolle bleiben.
- **Vorgaben:** Was steht beim Öffnen schon richtig da? Vorn das, was man
  ändert, hinten das, was man nachschlägt.
- **Rückmeldung:** Sieht man, worauf sich die Handlung bezieht, ob sie läuft,
  was sie geändert hat und wie es weitergeht? Zeiten messen oder als ungemessen
  ausweisen.
- **Rückweg:** Abbruch und Undo/Redo für die betroffene Handlung;
  Agentenvorschläge bleiben eine Transaktion; Nachfragen nur, wo Regel 19 sie
  ausdrücklich erlaubt.
- **Fehler:** Nennt die Meldung einen gangbaren nächsten Schritt und erhält
  sie noch gültige Eingaben? Die Texte selbst formuliert der Agent
  oberflaechentexte.
- **Zugänglichkeit:** den Tastaturweg wirklich fahren — Fokusfolge,
  Aktivierung, Verlassen von Menüs und Dialogen, Rückkehr zum Ausgangspunkt.
  Aus sichtbaren Beschriftungen folgt keine Bildschirmleser-Abnahme.

## Kriterien des Funktionsdurchgangs

Die eine Quelle für Einfachheit (E) und Verständlichkeit (V) im
Funktionsdurchgang (`konzepte/konzept-funktionsdurchgang-2026-10.md` §4); Stufe
A misst der Prüfstand, B urteilt am Bild, C von Hand. Die Zahlen hält
`tools/function_checks.py`, ein Test hält beide gleich. Maßstab ist der
Slicer-Kunde, Startzustand die passende Auswahl, das Beispielziel steht vorab
in der Zeilenspezifikation.

| Kennung | Zählgröße | Schwelle | Stufe | Messung |
|---|---|---|---|---|
| E1 | Klicks bis zum Ergebnis mit den Vorgaben | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | A zählt, B urteilt | `steps` |
| E2 | Pflichteingaben bis zum Beispielziel | ≤ 1 bei 90 % der Funktionen; sonst ist die Vorgabe der Fund | A | `steps[].typed`, Anteil je Paket |
| E3 | Entscheidungen, die Vorwissen verlangen | ≤ 1 | A zählt, B wertet | `steps[].decision` |
| E4 | Blickwechsel zwischen Ansicht, rechter Karte, Dialog, Statusleiste, linker Karte | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | A | `steps[].zone`, `spot` |
| E5 | Felder vorn, Wörter über dem ersten Feld | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | A | `fields`, `texts` |
| E6 | Nachfragen außerhalb der Ausnahmen von Regel 19 | 0 | A | `modals` |
| E7 | Sackgassen: grau ohne Grund, leere Karte ohne Satz, Meldung ohne Handlung | 0 | A | `matrix`, `empty_states`, `messages` |
| V1 | Wörter der Negativliste im sichtbaren Text | 0 | A | `texts` gegen `tests/data/customer_vocabulary.json` |
| V2 | Satzlängen | die Grenzen aus `test_text_length` | A | `texts` |
| V3 | Felder mit eigenem Satz (Kurzhilfe und zugängliche Beschreibung) | 100 %; höchstens die Hälfte der Wörter mit dem Titel geteilt | A | `fields` |
| V4 | Vorhersage aus Titel, erstem Satz und Vorschau vor dem Übernehmen | Abweichung vom Ergebnis ist ein Fund | B | Urteil mit `prediction` |
| V5 | Meldungen: was nicht ging, warum, was jetzt | jede Handlung löst das Problem; ein Sperrgrund am grauen Element braucht keinen Knopf, nennt aber den Ausweg | A misst, B urteilt | `messages[].actions` |
| V6 | Kurzhilfen, die man bis zum Ziel öffnen muss | ≤ 1; nie das Handbuch | A misst, B zählt | `windows` (Handbuchfenster) |

## Vorschlag, Entscheidung, Abnahme

Der kürzeste verständliche Ablauf, der den belegten Produktvertrag erhält. Bei
einer Prüfung: priorisierte Befunde und konkrete Änderungen. Bei einem
Konzeptauftrag: Soll-Ablauf und prüfbare Abnahmekriterien. Bei beauftragter
Umsetzung: die betroffenen Pfade ändern und denselben Ablauf erneut fahren.

Wo Bauplan und Regeln eine Bedienfrage offenlassen, wird nach dem Besten für
Kunde, Druck und Modell entschieden, begründet und als Entscheidung
gekennzeichnet — keine Variantenliste zur Auswahl. Gefragt wird, wo Geld,
Veröffentlichung, Rechte oder schwer Umkehrbares berührt sind, oder wenn der
Auftrag selbst mehrdeutig ist. Routinemäßige, rücknehmbare Umsetzung im
beauftragten Rahmen braucht keine neue Freigabe.

Für visuelle Änderungen `/ui-design`, für eine Website-Browserprüfung
`/website-review`, für die betroffenen Tests `/pruefen` mit Dateipfaden. Ein
Bindungstest ersetzt den tatsächlichen Ablauf nicht; ohne UI-Zugang bleibt
dieser Nachweis offen.

Melden: Startzustand, Schritte, erwartetes und beobachtetes Verhalten, Beleg,
Auswirkung, Zählung vorher und nachher, getroffene Entscheidungen. Beobachtete
Hürden von vermutetem Nutzerverhalten trennen — eine Expertenprüfung ist kein
Usability-Test mit echten Nutzern.
