---
name: ux-review
description: >
  Entwirft und prüft konkrete Nutzerabläufe in Solidon und auf der Website:
  Auffindbarkeit, Schritte, Rückmeldung, Fehlerbehebung, Abbruch, Undo und
  Tastaturbedienung. Benutzen bei umständlicher Bedienung, neuen Abläufen und
  UX-Abnahmen; visuelle Gestaltung über ui-design.
---

# Bedienabläufe prüfen

## Nutzerauftrag und Ist-Ablauf

Formuliere das konkrete Ziel und den Startzustand: vorhandenes Modell oder
leeres Projekt, Auswahl, Vorkenntnisse und Eingabegerät, soweit für den Auftrag
relevant. Ermittle den heutigen Ablauf aus den wirklichen Aufrufern, Ereignissen
und Zuständen; fahre ihn bei verfügbarem UI-Zugang selbst. Kennzeichne einen
nur aus Code abgeleiteten Ablauf entsprechend.

Für Solidon lies die betroffenen Abschnitte über `.agents/skills/bauplan/SKILL.md`, insbesondere
Bedienkonzept und Barrierefreiheit. Ergänzend dienen
`.claude/agents/bedienlogik.md` und `.claude/agents/oberflaechentexte.md` als
Fachanweisungen; das verlangt keine automatische Delegation. Bei Website-
Aufträgen gelten zusätzlich `website/CLAUDE.md` und `website/README.md`.

## Ablauf aufnehmen

Beschreibe für jeden Schritt:

| Ausgangszustand | Was der Nutzer sieht | Handlung | Rückmeldung und neuer Zustand | Rückweg |
|---|---|---|---|---|
| Konkrete Auswahl und vorhandene Daten | Sichtbarer Einstieg und verfügbare Werte | Klick, Taste oder Eingabe | Tatsächlich beobachteter Effekt | Abbruch, Zurück oder Undo, soweit vorhanden |

Untersuche den Hauptweg und die für ihn relevanten Randfälle: keine oder mehrere
Auswahlen, ungeeignete Eingabe, laufende Berechnung, Abbruch, Fehler und erneuter
Versuch. Prüfe nach einer Änderung den gemeinsamen Mutationspunkt und andere
Einstiege wie Menü, Kontextaktion, Kürzel und Agentenaufruf, soweit sie dieselbe
Handlung auslösen. Eine neue Beschriftung repariert keine falsche Zustandsfolge.

## Bewertung

- **Auffindbarkeit:** Ist der nächste Schritt aus dem aktuellen Zustand
  verständlich, ohne den Namen eines internen Moduls kennen zu müssen?
- **Aufwand:** Zähle Schritte und notwendige Entscheidungen vorher/nachher.
  Weniger Klicks sind nur dann besser, wenn Klarheit und Kontrolle erhalten bleiben.
- **Rückmeldung:** Ist sichtbar, worauf sich die Handlung bezieht, ob sie läuft,
  was sie geändert hat und wie es weitergeht? Zeiten messen oder als ungemessen
  ausweisen; ein synchroner Aufruf allein belegt keine wahrnehmbare Verzögerung.
- **Rückweg:** Funktionieren Abbruch und Undo/Redo für die betroffene Handlung?
  Agentenvorschläge bleiben eine Transaktion. Bestätigungen gegen Regel 19
  einschließlich der ausdrücklich erlaubten Verlaufslöschung prüfen.
- **Fehler:** Nennt die Meldung einen gangbaren nächsten Schritt und erhält sie
  noch gültige Eingaben? Kein technischer Fehlertext ohne Handlungsoption.
- **Zugänglichkeit:** Den Tastaturweg wirklich fahren: Fokusfolge, Aktivierung,
  Verlassen von Menüs und Dialogen sowie Rückkehr zum Ausgangspunkt. Keine
  automatische Behauptung einer Screenreader-Abnahme aus sichtbaren Labels.

## Vorschlag und Abnahme

Liefere den kürzesten verständlichen Ablauf, der den belegten Produktvertrag
erhält. Bei einer reinen Prüfung: priorisierte Befunde und konkrete Änderungen.
Bei einem Konzeptauftrag: Soll-Ablauf und überprüfbare Abnahmekriterien.
Bei beauftragter Umsetzung: betroffene Pfade ändern und den gleichen Ablauf
erneut ausführen. Offene Produktentscheidungen benennen; routinemäßige,
rücknehmbare Umsetzung im beauftragten Rahmen benötigt keine neue Freigabe.

Für visuelle Änderungen `.agents/skills/ui-design/SKILL.md`, für eine Website-Browserprüfung
`.agents/skills/website-review/SKILL.md`, für betroffene automatisierte Tests `.agents/skills/pruefen/SKILL.md` mit
Dateipfaden verwenden. Ein erfolgreicher Bindungstest ersetzt den tatsächlichen
Interaktionsablauf nicht. Ohne UI-Zugang sind entsprechende Nachweise offen.

Melde den Befund mit Startzustand, Schritten, erwartetem und beobachtetem
Verhalten, Beleg und Auswirkung. Trenne beobachtete Hürden von vermutetem
Nutzerverhalten: Eine Expertenprüfung ist kein Usability-Test mit echten
Nutzern. Nenne abschließend geprüfte Varianten und offene Abnahmekriterien.
