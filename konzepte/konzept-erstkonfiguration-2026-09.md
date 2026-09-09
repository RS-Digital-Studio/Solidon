# Slicer, Drucker, Filament — die Kette einmal festlegen (09.09.2026)

> **Stand:** Entwurf. Nichts davon ist gebaut. Anlass ist ein Befund aus der
> laufenden Anwendung und Roberts Ableitung daraus; die Messwerte unten sind
> vom 09.09.2026 an seinem eigenen Bestand (ElegooSlicer, Filamenthalter-M6).
>
> **Was schon gebaut ist:** die Beschleunigung, die den Befund erträglich
> gemacht hat (`dc36754f` und der Nachtrag zum Namensindex). Sie behebt das
> Symptom vollständig; dieses Konzept beschreibt, wie die Ursache verschwindet.

## Der Anlass

Robert hat im Druckeinstellungen-Dialog eine Qualitätsstufe gewählt. Das
Aufklappen ging schnell, das Auswählen nicht: Die Oberfläche stand **52
Sekunden**, davon 50,7 mit blockierter Ereignisschleife — kein Klick kam
durch, keine Anzeige bewegte sich.

Die Ursache lag nicht bei der Qualitätsstufe. Der Wechsel stößt die
Slicer-Profilsuche an, und deren Auswertung läuft im Qt-Hauptthread. Dort
baute jeder Aufruf von `resolve_values` und `binding` sich einen eigenen
Namensindex, und ein Index kostet einen Durchgang durch **jede** JSON-Datei
der Ablage:

| Was | Zahl |
|---|---|
| Profildateien im Programm | 12 017 |
| Profildateien im Nutzerordner | 4 778 |
| ein Indexlauf, warm gemessen | 0,87 s |
| Indexläufe je Filament (vorher) | 1 |

Der geteilte Index hat daraus 5,5 Sekunden gemacht. Das ist die Grenze dessen,
was Aufräumen erreichen kann: **Die Menge, über die gesucht wird, ist die
falsche.**

## Roberts Ableitung

> „wir brauchen doch nur die filamente die wir ausgewählt haben"
>
> „wir legen die filamente ja fest bzw haben wir unser filamentregal"
>
> „und den slicer sollten wir am anfang in erste Schritte festlegen bzw sehen
> wir ihn dann bei Druckeinstellungen, danach den drucker des slicers, danach
> die filamente düsen usw des Druckers — strukturiert gegliedert nach dem
> jeweiligen und man braucht dann ja immer nur die jeweiligen einträge"

Das ist keine Beschleunigung, sondern eine andere Frage. Heute sucht der
Dialog bei jedem Öffnen im ganzen Bestand nach dem, was passen könnte. Nach
diesem Entwurf steht die Kette fest, und der Dialog **zeigt** sie, statt sie
zu ermitteln.

## Die Kette

Vier Stufen, jede engt die nächste ein:

```
Slicer            →  Drucker            →  Düse        →  Filamente
(einmal gewählt)     (die des Slicers)     (die des       (die des Regals,
                                            Druckers)      zum Drucker passend)
```

Was jede Stufe leistet, und woher sie ihre Auswahl nimmt:

| Stufe | Wählt aus | Quelle | Menge heute |
|---|---|---|---|
| Slicer | den installierten Programmen | `discover.find_program` | 0 bis 4 |
| Drucker | den Maschinenprofilen dieses Slicers | `slicer_profiles.machines` | 1 001 beim ElegooSlicer |
| Düse | den Varianten dieses Druckermodells | `SlicerProfile.nozzle` | 2 bis 5 |
| Filament | dem **Filamentregal**, gefiltert auf den Drucker | `knowledge/filaments.py` | so viele Spulen wie da sind |

Die vierte Stufe ist Roberts eigentlicher Punkt und der größte Unterschied:
Solidon führt seit dem 08.09.2026 ein Filamentregal mit den **physischen
Spulen** des Kunden ([konzept-filamentlager-2026-09.md](konzept-filamentlager-2026-09.md)).
Wer sein Regal gepflegt hat, hat damit eine Liste von Dutzenden statt einer von
Tausenden — und die Zuordnung zum Slicer-Profil ist bereits Teil der
Spulenidentität.

## Wo das hingehört

**Nicht in einen neuen Dialog.** Die Erstkonfiguration hat einen Ort:
`app/ui/first_run.py`, den Erststart. Was dort nicht gefragt wird, fragt der
Druckeinstellungen-Dialog beim ersten Öffnen nach — und danach steht es.

Vier Eingriffe, in dieser Reihenfolge:

1. **`first_run.py` bekommt die Kette** als vier aufeinander aufbauende
   Schritte. Jeder zeigt nur, was die vorige Stufe zulässt; keiner ist
   Pflicht, denn Solidon muss auch ohne Slicer laufen (§2).
2. **Das Druckerprofil trägt die Wahl.** Slicer, Maschinenprofil und Düse
   gehören zum Drucker, nicht zu den Druckeinstellungen — ein zweiter
   Drucker hat einen anderen Slicer-Pfad. Heute liegen sie in `UiSettings`
   (`slicer_base_filament`, `slicer_filament_per_material`), also je Fenster
   statt je Gerät.
3. **Der Dialog zeigt statt zu suchen.** `_fill_processes` und
   `_fill_filaments` bekommen ihre Liste aus der festgelegten Kette; die
   Vollsuche bleibt als Weg für „etwas anderes wählen", ausgelöst durch einen
   Klick und nicht durch das Öffnen.
4. **Das Regal wird die Filamentquelle.** `match_filament` sucht heute die
   Vorgabe über alle zum Drucker passenden Profile. Mit einem gepflegten
   Regal ist die Vorgabe die Spule, die eingelegt ist.

## Was das kostet, und was es einspart

Gemessen am heutigen Weg mit Roberts Bestand:

| | heute (nach der Beschleunigung) | nach diesem Entwurf |
|---|---|---|
| Öffnen des Dialogs | 1,1 s | unverändert (der Slicer wird gesucht) |
| Qualitätsstufe wechseln | 5,5 s, davon 0,83 s blockiert | keine Profilsuche mehr |
| Erststart | keine Frage nach dem Slicer | vier Schritte, einmalig |

Der Gewinn ist nicht allein Zeit. Heute rät die Anwendung bei jedem Öffnen
neu, welches Filamentprofil gemeint ist, und trifft dabei die
Grundausführung — „PETG" statt der Spule, die wirklich im Drucker steckt. Nach
diesem Entwurf steht es fest, und der Export trägt, was der Kunde eingelegt hat.

## Fünf offene Entscheidungen

Sie gehören Robert, nicht diesem Dokument.

1. **Wie viele Schritte trägt der Erststart?** Vier ist die Kette, aber der
   Erststart hat heute schon Schritte, und §35 begrenzt nicht die Zahl der
   Assistentenseiten, wohl aber die Geduld. Denkbar wäre: Slicer und Drucker
   im Erststart, Düse und Filament beim ersten Druckdialog.
2. **Was passiert mit einem Projekt, das einen anderen Slicer trägt?**
   Übernehmen, fragen oder umstellen — und was, wenn der Slicer der Datei
   hier gar nicht installiert ist.
3. **Was, wenn das Regal leer ist?** Der heutige Weg (Vollsuche, schlichteste
   Grundausführung) bleibt der Rückfall — oder der Dialog fragt einmal nach.
4. **Bleibt die Wahl am Drucker oder am Projekt?** Ein Kunde mit zwei
   Druckern hat zwei Slicer-Ketten; ein Projekt kann auf beiden gedruckt
   werden.
5. **Was wird aus `slicer_filament_per_material`?** Die Zuordnung „für PETG
   nimm dieses Profil" ist heute die Brücke; mit dem Regal ist sie vielleicht
   überflüssig, vielleicht bleibt sie als Vorgabe für Material, für das keine
   Spule da ist.

## Was daran schon belegt ist

- Die 16 795 Dateien und die 0,87 s je Indexlauf sind gemessen (09.09.2026,
  ElegooSlicer auf Roberts Maschine).
- Die 52 Sekunden Blockade sind am echten Dialog mit `Filamenthalter-Solidon3D-M6.p3d`
  gemessen, die 5,5 Sekunden danach ebenso.
- Dass `match_filament` über alle zum Drucker passenden Profile läuft, steht
  in seinem eigenen Docstring, samt der früheren Messung „0,97 Sekunden mit
  Drucker, über zehn Minuten ohne".
- Das Filamentregal ist gebaut und trägt die Spulenidentität
  ([RM-146](../ROADMAP-ARCHIV.md#rm-146)).

## Was daran Vermutung ist

- Ob vier Schritte im Erststart die richtige Zahl sind, ist nicht gemessen.
- Ob das Regal in der Praxis gepflegt genug ist, um die Profilsuche zu
  ersetzen, weiß nur die Nutzung.
- Die Zahl 1 001 Maschinenprofile ist der ElegooSlicer-Bestand; für
  PrusaSlicer und Cura ist sie nicht erhoben.
