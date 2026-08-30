# Material und Farbe kommen aus dem Filament

**Stand:** Entwurf, 30.08.2026 · **Anlass:** Robert am Druckeinstellungs-Dialog
· **Registerpunkt:** D14b · **Größe:** M, mit Kernberührung

---

## Der Anlass, wörtlich

> „bei druckeinstellungen die materialauswahl und farbe sind sinnlos, da wir ja
> nach den filamenten gehen"
>
> „das material kommt ja auch aus dem filament"
>
> „warum ein filamentwähler? es sind ja die die dem material zugeordnet sind"
>
> „kann ja mehrere geben"

Die letzten beiden Sätze sind eine Korrektur an meinem ersten Vorschlag und der
Kern dieser Notiz: Ein *Filamentwähler* in der Kopfzeile wäre derselbe Fehler
wie die Material-Combo, nur mit anderem Etikett. **Ein Projekt hat nicht ein
Filament.**

## Was heute dasteht

Die Kopfzeile des Dialogs führt drei Auswahlen: Qualität, Drucker, Material.
Auf der Vorderseite steht zusätzlich ein Farbfeld (`filament.colour`).

Zwei Ketten hängen daran, und sie sind verschieden fest:

| | Kette | Was ohne sie geschieht |
|---|---|---|
| **Material** | `material_choice` → `session.change_scene_profile` → `document.material` → `Session.profile` → `resolve_tolerance("auto:…")` | Spiel, Presssitz und jede Passung verlieren ihre Quelle (Regel 7) |
| **Farbe** | `filament.colour` → `slicer_keys` → `filament_colour` beim Slicer | Ein Teil ohne bemalte Spule kommt farblos beim Slicer an |

Die Farbe ist dabei schon heute zweitrangig: `handover.py` überschreibt sie mit
der Slot-Farbe, sobald es eine gibt — der Kommentar dort sagt es selbst („Die
Farbe gehört dem Slot, nicht der Einstellung"). Sie ist der **Rückfall für den
ungefärbten Fall**, nicht die eigentliche Auskunft. Das ist der Grund, aus dem
D14a nicht als eigener kleiner Punkt gebaut werden konnte.

## Warum Roberts Bild schon im Datenmodell steht

Der Umbau erfindet nichts, er räumt eine Doppelung weg:

| Träger | Feld | Bedeutung |
|---|---|---|
| `MaterialSlot` | `material_type` | Materialart der Spule, „PETG" |
| `MaterialSlot` | `material` | Herstellerprofil im Slicer |
| `MaterialSlot` | `colour` | die Farbe der Spule |
| `SceneObject` | `material` | in welchem Material **dieser Körper** gedruckt wird |
| `Document` | `material` | die Vorgabe des Projekts |

`SceneObject.material` trägt Roberts Satz bereits in seinem Docstring: „Eine
Szene ist nicht ein Material. Eine TPU-Dichtung im PETG-Gehäuse schrumpft
anders." Die Struktur für mehrere Materialien ist also da; was fehlt, ist die
**Herleitung**: Heute wird das Material an einer zweiten Stelle noch einmal
von Hand gewählt, obwohl die Spule es schon sagt.

## Der Entwurf

**1. Die Kopfzeile verliert die Material-Combo, die Vorderseite das Farbfeld.**
Übrig bleiben Qualität und Drucker — die zwei Dinge, die wirklich das ganze
Projekt betreffen.

**2. Das Material eines Körpers kommt aus seiner Spule.** Trägt ein Körper
Slots, bestimmt `material_type` des ersten belegten Slots sein
`SceneObject.material`. Mehrere Slots heißen mehrere Materialien — das ist der
Normalfall, keine Ausnahme.

**3. `Document.material` bleibt und wird zum ehrlichen Rückfall.** Ein Körper
ohne Spule braucht trotzdem Toleranzen; die Alternative wäre eine Passung ohne
Materialbezug, und die gibt es nicht (Regel 7). Es ist damit nicht mehr eine
Wahl neben den Spulen, sondern die Antwort auf „noch keine Spule gewählt".

**4. Wo steht die Wahl dann?** Am Filament, wo Robert sie verortet: im
Filamentwähler des Dialogs (Slot für Slot, mit Farbe und Namen) und über *Fläche
färben*. Das ist ein Ort statt zweier konkurrierender.

**5. Die Farbe folgt derselben Regel.** Sie kommt aus dem Slot; ohne Slot bekommt
der Slicer keine Farbvorgabe und nimmt seine eigene. Das ist ehrlicher als eine
Farbe, die niemand gewählt hat.

## Was dabei nicht kaputtgehen darf

Fünf Stellen, alle gemessen — sie sind die Abnahmeliste:

1. **Die Toleranzkette.** `resolve_tolerance("auto:…")` muss weiter ein Material
   finden, auch für einen Körper ohne Spule. Prüfung: eine Passung im Beispiel
   „Dose mit Deckel" vor und nach dem Umbau, gleiche Zahl.
2. **Fremde Dateien.** Eine eingelesene STL hat keine Spulen. Sie darf nicht
   plötzlich ohne Material dastehen — hier greift Punkt 3.
3. **Die Übergabe.** `handover.as_mapping` schreibt `filament_colour` und
   `filament_type` je Platte; `test_the_colour_reaches_the_slicer` und die
   Slot-Tests halten beide Richtungen fest.
4. **Der Override-Dialog.** `FilamentOverrideDialog` führt bereits die Werte,
   die physisch an der Spule hängen — er ist der natürliche Ort für Punkt 4 und
   darf nicht zu einem dritten Ort werden.
5. **Alte Projektdateien.** `document.material` bleibt im Format, also braucht
   es **keine** Formatversion; was sich ändert, ist die Herleitung im Speicher.
   Ein Projekt, das heute ein Material trägt, öffnet unverändert.

## Was offen bleibt

- **Welcher Slot gilt, wenn mehrere verschiedene Materialien tragen?** Für die
  *Toleranz* eines Körpers braucht es eine Antwort. Vorschlag: der Slot mit dem
  größten Flächenanteil, ersatzweise Slot 0 — zu entscheiden mit einem Bild vor
  Augen, nicht auf dem Papier.
- **Ob die Kopfzeile den Drucker behält.** Er hat dieselbe Frage nicht (ein
  Projekt hat einen Drucker), aber die Zeile wird schmaler; das ist eine
  Layoutfrage für den Bau.

## Abnahme

Die fünf Punkte oben je als Test, dazu die Kundenfahrt am Dialog erneut (die
vom 30.08.2026 liegt als Vergleich vor) und ein Blick auf die Vorderseite: Sie
soll nach dem Umbau **kürzer** sein, nicht nur anders.
