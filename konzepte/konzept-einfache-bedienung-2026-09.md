# Einfach für Kunden — was die Vorschau verschweigt und was die einfachen Werkzeuge anders machen

> **Stand:** 14.09.2026 — Messung, Recherche, acht Änderungen gebaut;
> nichts mehr offen. **Anlass:** Robert am 13.09.2026: „bei vielen operationen
> fehlen noch vorschau, bei aushöhlen reagiert die checkbox zum öffnen ab und
> zu nicht, viele operationen sind auch recht umständlich, die ganze app soll
> einfach für kunden sein" — und: „recherchiere auch mal wie man es ganz
> einfach alles machen kann".
> **Rahmen:** Roberts Entscheidung vom 29.08.2026 gilt weiter — „eher den
> aktuellen stand aber optimiert", kein Umbau der Bedienzone
> (`konzept-befehlsband-2026-08.md`). Alles hier ist Optimierung am Bestand.
> RM-168 bis RM-171 sind am 14.09.2026 zugegangen und stehen mit ihrem
> Nachweis im Archiv; dieses Dokument führt keine offene Arbeit mehr.

## §1 Gemessen, nicht gefühlt

Eine Sonde baute das Hauptfenster wie die Anwendung (`MainWindow` über
`Session`), lud je Operation eine passende Szene, rief `run_operation` wie das
Menü und las den Viewport ab: Dialog offen? Differenz da? Was steht im Band?
110 Operationen, ein Prozess je Kategorie (ein Prozess über alle riss nach
rund sechzig Fenstern nativ ab — dieselbe Grenze wie in der Suite).

### §1.1 Die Vorschau fehlte nicht — sie schwieg

| Zustand beim Öffnen mit Vorgaben | Operationen | Was das Band sagte |
|---|---|---|
| Vorschau im Bild | 62 | „Vorschau — noch nicht übernommen" |
| Differenz leer, Bild unverändert | 17 | **dasselbe** |
| Keine Differenz (Kette angehalten oder Fehler) | 11 | **dasselbe** |
| Kein Dialog (keine Parameter, läuft sofort) | 5 | — |
| Braucht Quelle oder eigenen Editor, nicht gemessen | 7 | — |
| Ohne passende Szene in der Sonde | 8 | — |

Die elf ohne Differenz, mit dem Grund, den der Kern kannte und niemand sah:

| Operation | Grund (kam erst beim Übernehmen) |
|---|---|
| Teilen, An gezeichneter Linie trennen | Diese Ebene teilt das Objekt nicht. |
| In Einzelteile zerlegen | Der Körper besteht aus einem Stück; es gibt nichts zu zerlegen. |
| Offene Fläche schließen | Dieser Körper ist schon geschlossen — … |
| Deckel erzeugen, Drehdeckel erzeugen | Diese Fläche zeigt nicht nach oben — eine Öffnung für einen Deckel schon. |
| Gitter füllen | Der Innenraum lässt sich nicht eindeutig bestimmen. Den Körper mit Aushöhlen vorbereiten … |
| Schriftzug als Körper, Text aufbringen | Ohne Text gibt es nichts anzulegen. |
| Merkmal ändern, An Merkmal ausrichten | (Sondenlage: kein passendes Merkmal gewählt) |

Die siebzehn mit leerer Differenz: Verschieben um null, Drehen um null,
Skalieren auf eins, Spiegeln eines symmetrischen Quaders, alle vier
Filament-Operationen, Umbenennen, Material, jede Netzoperation, die Dreiecke
tauscht und kein Volumen (Verringern, Verfeinern, Angleichen, Unterteilen,
Flächenbearbeitung beenden), Reparieren an einem sauberen Körper, Anordnen
und Ausrichten an einem Körper, der schon liegt.

**Der Befund:** Drei verschiedene Lagen trugen denselben Satz. Nur bei der
ersten war er wahr.

### §1.2 „Ab und zu" ist eine Fläche von 14 mal 14 Bildpunkten

`QCheckBox(self)` ohne Text: Qt prüft Klicks in `hitButton` gegen Kästchen und
Text, und ohne Text bleibt das Kästchen. Im Aushöhlen-Dialog gemessen
(`QStyle.SE_CheckBoxClickRect`): **14 × 14** in einem Feld von **241 × 14**.
Ein Klick in die Mitte des Feldes tat nichts, ein Klick auf „Oben öffnen"
links davon auch nicht. Vier Stellen bauten den Haken so: Operationsdialog,
Merkmalfenster, Druckeinstellungen (zweimal).

Dazu die Höhe, gemessen erst am 14.09.2026 auf der echten Plattform mit dem
Stylesheet der Anwendung (offscreen gibt es keines): Die Zahlenfelder des
Aushöhlen-Dialogs sind **31 Punkte** hoch, der Haken ohne Text war **12** —
ein Klick acht Punkte über oder unter seiner Mitte traf nichts, obwohl er in
der Zeile lag. Seither meldet `RowCheckBox` die Höhe eines Eingabefelds; die
Sonde (`probe_hollow_rows`, `childAt` von −14 bis +14 Punkten) trifft an
jeder Stelle den Haken.

Dazu kam die stillere Hälfte: Zwischen Klick und neuem Bild liegen 300 ms
Entprellung plus die Rechnung — an einem großen Netz Sekunden —, und solange
stand das alte Bild unter dem alten Band. Ein Haken, dessen Wirkung nach drei
Sekunden kommt, sieht aus wie einer, der nicht reagiert. Und an
`generated_figure.stl` (Weg 3, 3372 Dreiecke) scheitert die Boolesche Kette
des Aushöhlens in beiden Qualitäten — dort kam nie ein Bild, in keiner
Stellung des Hakens.

### §1.3 Vorgaben, die den Körper verfehlen

*Teilen* öffnete mit `position = 0`. Ein importierter Körper steht auf dem
Bett (gemessen: Quader 0 bis 20 mm), die Ebene lag also auf seiner Unterseite
und teilte nichts. Wer teilen will, will fast immer die Mitte.

Vorderseiten: Das Register hält die Grenze von acht Feldern
(`tests/test_interface_limits.py`), und *Grundform hochziehen* nutzte sie ganz — vier der acht
(Löcher, Spalten, Zeilen, Loch-Ø) gelten nur für Lochkreis und Lochraster und
standen bei einem Rechteck ausgegraut da. Das war eine dokumentierte
Entscheidung (`_couple_dependent_fields`: „wer sie verschwinden sähe, suchte
sie") und kein Versehen — aber für einen Kunden, der ein Rechteck hochzieht,
waren es vier Zeilen, die nichts bedeuten. Seit dem 14.09.2026 verschwinden
sie, bis die Grundform sie braucht (§4, RM-171).

## §2 Was die einfachen Werkzeuge anders machen

Gelesen am 13.09.2026; die Quellen stehen unten.

**Tinkercad.** Kein Dialog für die Grundhandlung: Formen werden auf die Fläche
gezogen, Maße stehen als Griffe am Körper, und die Boolesche Differenz ist
kein Befehl, sondern eine Eigenschaft — jede Form ist *Solid* oder *Hole*,
Gruppieren verrechnet sie. Die Lernkurve ist die kürzeste am Markt: die
meisten Nutzer haben ihr erstes Modell in unter einer Stunde.

**Shapr3D.** Direktmodellierung mit Push/Pull statt Skizze-Extrusion-Verlauf;
Gesten und Stift; Vorschau folgt der Hand. Dort werden drei bis fünf Tage
Einarbeitung gegen Hunderte Stunden bei Fusion 360 gestellt — der Unterschied
ist nicht Funktionsumfang, sondern **wie viel man wissen muss, bevor die erste
Handlung gelingt**.

**Onshape** wird in den Foren genau dafür kritisiert, was Solidon heute noch
hat: zu viele Dialoge, zu wenig Griff am Körper. **Plasticity** hält die
Erzeugerleiste fest und wechselt nur die Kontextleiste zur Aufgabe.

Vier Sätze, die daraus über Solidon gelten — und alle vier passen in „den
aktuellen Stand, optimiert":

1. **Was man tut, sieht man sofort — und wenn nicht, steht da, warum.** Ein
   leeres Bild ohne Satz ist die schlechteste Rückmeldung: es sieht aus wie
   „nichts ändert sich".
2. **Die Vorgabe trifft den Körper, nicht den Ursprung.** Mitte, oberste
   Fläche, gemessener Durchmesser — die Anwendung kennt die Zahl und sagt sie
   (§2.4: „Eine gute Vorgabe ist mehr wert als eine gute
   Einstellmöglichkeit").
3. **Kein Angebot, das nur scheitern kann.** *Offene Fläche schließen* an
   einem geschlossenen Körper ist kein Menüeintrag, sondern eine Sackgasse
   mit Dialog davor. Menü und Palette kennen `_reason_locked` — die Frage
   gehört dorthin, bevor der Dialog aufgeht.
4. **Vorn nur, was gerade wirkt.** Ein Feld, das bei dieser Grundform nichts
   tut, gehört nicht ausgegraut auf die Vorderseite.

## §3 Gebaut am 13.09.2026

| Was | Wo | Nachweis |
|---|---|---|
| Der Haken antwortet auf seiner ganzen Zeile, die Beschriftung schaltet mit | `labels.RowCheckBox`, `caption_toggles`; vier Bauorte | `test_a_checkbox_row_answers_on_its_whole_width`, `test_every_bool_row_in_the_register_is_a_row_checkbox` |
| Das Band nennt den Grund, wenn es keine Vorschau gibt | `Session.preview_async(explained=…)`, `_PreviewWorker.explained`, `MainWindow._preview_explained` | `test_a_preview_that_cannot_be_says_why`, `test_the_banner_names_the_reason_and_the_empty_difference` |
| Das Band sagt „am Volumen ändert sich nichts", wenn die Differenz leer ist | `MainWindow._show_preview` | dito |
| Das Band sagt nach 0,2 s „wird gerechnet …" (§2.8) | `MainWindow._preview_busy` | `test_a_slow_preview_says_it_is_computing` |
| *Teilen* beginnt in der Körpermitte | `MainWindow._plane_through` | `test_splitting_starts_in_the_middle_of_the_body` |
| Ein langer Grund bricht im Band um statt hinauszulaufen | `PreviewBanner.place` | Sonde: Satz von 190 Zeichen bei 1400 px |

Nach dem Umbau, dieselbe Sonde: Elf Dialoge sagen jetzt, warum kein Bild
kommt; siebzehn sagen, dass sich am Volumen nichts ändert; der Haken schaltet
bei einem Klick in die Zeilenmitte und auf die Beschriftung
(`probe_hollow_toggle`: Klickfläche vorher 14 × 14, nachher 241 × 14 plus
264 × 14 Beschriftung).

## §4 Gebaut am 14.09.2026

Robert am 14.09.2026: „dann leg los, das grundlegende konzept sollte aber
nicht geändert werden". Drei der vier Punkte waren Optimierung am Bestand;
der vierte war eine Entscheidung, und Robert traf sie am selben Tag
(„Ausblenden"). Alle vier sind gebaut.

| Was | Wo | Nachweis |
|---|---|---|
| **RM-168** Sackgassen sperren: `requires_body` im Register, `body_requirement` im Menü — derselbe Satz wie beim Rechnen, unbekannt sperrt nie | `registry.py`, `labels.body_facts`, `main_window._body_facts_of_selection` | `test_the_register_says_what_a_body_must_bring`, `test_a_dead_end_is_greyed_out_with_the_sentence_the_operation_would_say`, Gegenprobe und Zählung der Rechnungen daneben |
| **RM-169** Vorschau für Farbe und Netz: `Difference.recoloured` und `retriangulated`, der Körper danach liegt über dem davor | `difference.py`, `Viewport._cover_body` | `test_a_recolouring_is_a_preview_without_volume`, `test_a_recoloured_preview_covers_the_body_in_its_new_colours`, `test_a_reshaped_preview_shows_the_new_triangles_as_edges` |
| **RM-170** Aushöhlen an der generierten Figur: nicht die Kette, die offene Hülle ist der Grund — `NotManifoldError` mit „Reparieren und erneut versuchen" | `hollow.py` | `test_hollowing_an_open_hull_names_the_hull_and_offers_repair` |

*Deckel erzeugen* ohne Öffnung bleibt beim Band: Ob eine Öffnung nach oben
zeigt, entscheidet sich an der gewählten Fläche und nicht am Körper — das
Menü kann es vor dem Dialog nicht wissen.

- **RM-171** — Abhängige Felder vorn: Robert hat entschieden („Ausblenden",
  14.09.2026). Eine Zeile, deren Bedingung nicht gilt, verschwindet und kommt
  mit ihr wieder; ein Rechteck zeigt vorn vier Felder statt acht. Nachweis
  `test_a_rectangle_shows_only_the_rows_a_rectangle_has`.

## Quellen

- Shapr3D, „Shapr3D vs Fusion 360" — Lernkurve 3–5 Tage gegen 400–1 200 Stunden,
  Direktmodellierung: <https://www.shapr3d.com/comparison/shapr3d-vs-fusion-360>,
  <https://www.shapr3d.com/content-library/shapr3d-vs-fusion-360>
- Tinkercad, „22 Tips for Designing Faster" und Grundlagen (Solid/Hole,
  Gruppieren, erstes Modell unter einer Stunde):
  <https://www.tinkercad.com/blog/22-tips-for-working-faster-in-tinkercad>,
  <https://nibble-app.com/blog/tinkercad>,
  <https://www.coohom.com/article/explore-free-cad-with-tinkercad>
- Onshape-Forum, Diskussion über Dialoge statt Direktmanipulation:
  <https://forum.onshape.com/discussion/2531/a-discussion-about-onshape-as-a-tool-for-makers-artists-and-educators>
- Plasticity, feste Erzeugerleiste und Kontextleiste:
  <https://news.ycombinator.com/item?id=39639944>
