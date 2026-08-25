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

## Ein Maß, das aus einem fremden Maß folgt, ist ein Fehler in Wartestellung

Der Schnappverbinder hat es vorgemacht: Seine Armlänge kam aus der
Einbindetiefe eines **Passstifts** (`1,5 mal Ø`), und der Durchmesser ist
12 Prozent der Nahtbreite. Beide Regeln sind für sich richtig — ein Stift ist
so tief eingebunden, wie er dick ist, das ist Scherfestigkeit —, und
zusammengekettet ergaben sie eine Bedingung, die niemand aufgeschrieben hätte:
Ein Federarm hätte eine Naht von 44 mm gebraucht. Gemessen fiel jede
gewöhnliche Naht auf runde Stifte zurück, dokumentiert und freundlich, und das
Werkzeug griff nie.

Wer ein Maß aus einem anderen ableitet, prüft deshalb, ob es **dieselbe Frage**
beantwortet. Federweg ist nicht Scherfestigkeit; die Zahl kommt vom Körper, in
dem der Arm sitzt, nicht vom Stift daneben. Und wer eine Rückfallregel baut,
misst einmal nach, wann sie greift: Eine, die immer greift, ist keine
Rückfallregel, sondern die Regel.

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
gekennzeichnet. Eine **`.py` reist nie in Projektdateien mit** (Regel 13 in
der Fassung vom 24.08.2026: die Regel schützt vor ausführbarem Code): fehlt
eine, hält die Auswertung an und meldet, was fehlt. Sie erweitern die
Bibliothek, nicht die Anwendung — keine neuen Ops, kein Zugriff auf den Stack.

## Ein Rezept ist der eigene Baustein ohne Python

Seit dem 25.08.2026 gebaut (`parts/recipe.py`, Konzept Befestigungssysteme
§16–§19): ein Ausschnitt des Op-Stapels plus die Beschreibung seiner
Parameter, als Daten in `<Nutzerdaten>/parts/recipes/*.json`. Was dabei gilt:

- **Der Dokument-Ausschnitt reist als Dokument** (`scene.serialise`) und erbt
  dessen Migrationen; die Hülle trägt ihre eigene `FORMAT_VERSION`.
- **Die Version ist der Hash** über die kanonischen Daten (§24.4). Der
  Bereichstest-Bericht hängt am Rezept, aber **außerhalb** des Hashes —
  Prüfen macht aus dem Rezept kein anderes.
- **Ausgewertet wird mit dem Auswerter der Szene** (`recipe.build`): dieselbe
  Rückfallkette, dieselben `auto:`-Toleranzen, dieselbe §32-Quelltextprüfung.
  Beim Einsetzen läuft `build_with_profile` mit dem Profil des Dokuments
  (`ops.insert` bevorzugt es); `fn` mit dem Standardprofil trägt Vorschau und
  Bereichstest.
- **Genau ein Körper, benannte Merkmale** — beides wird beim `capture`
  abgewiesen, nicht später halb gebaut (Konzept §18a/§18d).
- **Der Bereichstest läuft in der Anwendung** (`parts/range_check.py`, §24.3):
  dieselben Ecken wie in der Suite, mit Fortschritt und Abbruch; das Ergebnis
  steht als `PartSpec.range_passed` am Katalogeintrag (§24.5 verlangt den
  Warnhinweis, kein Verbot).
- **`travelling_parts` warnt weiter nur vor `.py`s** — ein Rezept reist als
  Daten; sein `source` ist `recipe`, nicht `user`. Gekennzeichnet wird es
  trotzdem: **`own` heißt „gehört dem Kunden"** und umfasst seit dem
  25.08.2026 beide Gestalten (§24.5 will die Kennzeichnung im Katalog) — wer
  nur die `.py`-Gestalt meint, fragt `source == "user"`, nicht `own`.
- **`to_scad()` gibt es für Rezepte nicht** — benannt, nicht umgangen
  (Konzept §18e).

## Normteiltabelle

Zahlen sind frei verwendbar, Normtexte und Normtabellen nicht. Werte aus frei
zugänglichen Herstellerangaben zusammentragen, keine Normblätter abschreiben —
und die Herkunft im Kommentar nennen.

## Regelsammlung

Eine Änderung an `rules/` ist ein Eingriff in das Verhalten des Agenten:
Eintrag mit Datum und Anlass, Version erhöhen, Agenten-Suite vorher und
nachher laufen lassen, beide Ergebnisse festhalten. **Verschlechtert sich die
Quote, wird die Regel zurückgenommen** — nicht trotzdem behalten.
