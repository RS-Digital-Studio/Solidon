---
paths:
  - "app/core/knowledge/**/*.py"
---

# Regeln für Bausteine, Normteile und Regelsammlung

Der Grundsatz aus §24: **Der Agent setzt geprüfte Bausteine zusammen, statt
Geometrie zu erfinden.** Was hier liegt, ist der Vorrat, aus dem er schöpft —
und damit Teil des Rechenwegs, nicht bloß Beiwerk.

## Bausteine

- `@register_part(...)` mit `params`, `features`, `preview`, `doc`.
- Gebaut wird gegen **`manifold3d`**, nicht gegen OpenSCAD. Damit hängt
  `insert_part` an keiner Installation und bleibt testbar.
- Benannte Features zurückgeben (`bore`, `chamfer`, …) — das sind die
  Provenienz-IDs, an denen später Ops und Passungen ansetzen.
- `to_scad()` bleibt als Ausgabeformat erhalten.
- Vorschaubild wird **gerendert**, nicht von Hand gepflegt.
- Maße von Normteilen kommen aus der Tabelle, nie hart in den Baustein.
  „Loch für M4-Einpressmutter" ist ein Nachschlagewert.

## Ein abgezogener Baustein liegt unter seiner Mündung

Der Ursprung ist die Fläche, auf die geklickt wurde; was abgetragen wird, liegt
**darunter** (§24.1). Nach oben gebaut steht der Körper vollständig neben dem
Bauteil und nimmt nichts weg — zweimal geschehen, bei der Passbohrung und der
Rasttasche, und beide Male sagte der Docstring es längst.

**Verschieben genügt dabei nicht überall.** Eine Bohrung ist bis auf ihre Fase
drehsymmetrisch; sie um ihre Tiefe nach unten zu schieben ist richtig, solange
die Fase eigens an die Mündung gesetzt wird. Ein Körper mit einem Oben und
einem Unten — eine Rastkante, ein Schwalbenschwanz, jede Sperrfläche — kippt
dabei um: Die Kante landet am tiefen Ende, wo der Haken erst hinkommt, statt
zwischen Mündung und Haken zu stehen. Gebaut wird dann **von der Mündung nach
unten, Stück für Stück**, nicht als Ganzes verschoben.

Und die Prüfung dazu misst die **Richtung**, nicht nur die Berührung: Zwei
Volumen, die sich treffen, treffen sich am falschen Ende genauso. Was der Test
sagen muss, ist, an welchem Ende die Sperrfläche sitzt.

## Test über den ganzen Bereich

Jeder Baustein wird über seinen Parameterbereich durchgerechnet: wasserdicht,
Mindestwandstärke eingehalten, keine Selbstdurchdringung an den Grenzen,
Features korrekt benannt. **Ein Baustein ohne diesen Test gilt als nicht
vorhanden** (§24.3).

## Version

Ändert sich ein Maß an einem bestehenden Baustein, rechnet ein altes Projekt
sonst still anders:

1. `parts_version` erhöhen
2. Änderungsverlauf ergänzen: was, wann, warum, mit Auswirkung auf die Maße
3. Beim Öffnen meldet die Anwendung die *benutzten* geänderten Bausteine, mit
   der Wahl zwischen neu rechnen und altem Stand

## Eigene Bausteine sind kein Plugin-System

Aus `<Nutzerdaten>/parts/*.py`, beim Start eingelesen, im Katalog
gekennzeichnet. Sie **reisen nie in Projektdateien mit** (Regel 13): fehlt
einer, hält die Auswertung an und meldet, was fehlt. Sie erweitern die
Bibliothek, nicht die Anwendung — keine neuen Ops, kein Zugriff auf den Stack.

## Normteiltabelle

Zahlen sind frei verwendbar, Normtexte und Normtabellen nicht. Werte aus frei
zugänglichen Herstellerangaben zusammentragen, keine Normblätter abschreiben —
und die Herkunft im Kommentar nennen.

## Regelsammlung

Eine Änderung an `rules/` ist ein Eingriff in das Verhalten des Agenten:
Eintrag mit Datum und Anlass, Version erhöhen, Agenten-Suite vorher und
nachher laufen lassen, beide Ergebnisse festhalten. **Verschlechtert sich die
Quote, wird die Regel zurückgenommen** — nicht trotzdem behalten.
