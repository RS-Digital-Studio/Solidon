# RM-017: Nutfedern für zwei benannte Herstellerprofile

Robert hat keine Aluminiumprofile zum Nachmessen und hat die Recherche beauftragt.
Die Maße stammen deshalb aus Herstellerzeichnungen und wurden gegen die zugehörigen
STEP-Querschnitte geprüft. Eine gedruckte Passungsprobe wurde nicht durchgeführt.

## Quellen und Maße

Quelle: [Motedis, Nutenübersicht](https://www.motedis.com/daten/PDF/Nuten.pdf),
Zeichnungen für B-Typ Nut 6 und B-Typ Nut 8. Die Stegdicke ist die Differenz
zwischen Gesamttiefe und freier Kammertiefe. Die Kopfbreite ist die nutzbare
Breite zwischen den oberen Eckradien des Herstellerquerschnitts.

| Profil | Nutöffnung | Kopfbreite | Stegdicke | Kammertiefe |
|---|---:|---:|---:|---:|
| Motedis 20×20 B-Typ Nut 6 | 6 mm | 11 mm | 5,5 − 4 = 1,5 mm | 4 mm |
| Motedis 30×30 B-Typ Nut 8 | 8 mm | 15,5 mm | 9 − 6,8 = 2,2 mm | 6,8 mm |

Produkt- und CAD-Quellen:

- [20×20 B-Typ Nut 6](https://www.motedis.com/de/Aluprofil-20x20-B-Typ-Nut-6),
  [Hersteller-CAD](https://www.motedis.com/shop/products_files/motedis-profile-20x20-b-type-slot-6.zip).
- [30×30 B-Typ Nut 8](https://www.motedis.com/de/Aluprofil-30x30-B-Typ-Nut-8),
  [Hersteller-CAD](https://www.motedis.com/shop/products_files/30x30%20B-Type%20Slot%208.zip).

Die Zeichnung für **40×40 I-Typ Nut 8** nennt eine Gesamttiefe von 12,3 mm und
eine Kammer von 7,8 mm: Der Steg ist hier **4,5 mm** dick. Die alte Aussage
„Nut 8 wie 3030“ wurde entfernt. Aus der Nutöffnung allein ergibt sich kein
passender Kopfquerschnitt.

## Umsetzung und Folgen für bestehende Projekte

Die Normteiltabelle führt die zwei Herstellerprofile unter eigenen Kennungen.
Neue Nutfedern beginnen mit `motedis-2020-b6`. Die drei bisherigen Größen bleiben
mit ihren bisherigen Maßen erhalten und sind als ältere Maße gekennzeichnet.
Die Migration 42→43 trägt bei älteren Schritten ohne Größenangabe `2020` ein,
auch in beiden gespeicherten Seiten einer Verlaufsänderung. Ein vorhandener Wert
wird beibehalten.

Die Herstellerkammern verengen sich zur Profilmitte. Der neue Kopf folgt dieser
Kontur. Das Spiel wird an beiden Seiten und beiden Enden der Kammer berücksichtigt.
Auch ein manuell kürzerer Kopf ist ein Ausschnitt dieser Kontur. Ein zu hoher Kopf
wird mit Handlungsvorschlag abgelehnt. Das neue Tabellenfeld `taper_to_slot`
verlangt einen booleschen Wert; etwa die Zeichenkette `"false"` darf die Kontur
nicht versehentlich einschalten.

Bibliotheksversion 23 und der Änderungshinweis am Baustein machen die neue
Geometrie nachvollziehbar. Die Beispiele wurden mit dem regulären Generator
erneuert. Die sechs Webseiten zählen jetzt 61 hinterlegte Normteilmaße.

## Geometrische Nachweise

Die Regressionen lesen `tests/data/profile_slot_motedis.json`. Diese Datei enthält
Maße, Querschnittsbreiten und Quellen, keine eingebettete Herstellergeometrie.
Die Prüfungen verwenden ausdrücklich **mesh und brep** sowie beide Güten.

- 53 gezielte Fälle für Herstellerquerschnitt, Spiel, kurze Köpfe, zu hohe Köpfe
  und unveränderte ältere Geometrie bestanden.
- Der produktive Bausteinerzeuger wurde gegen beide Hersteller-STEP-Körper
  eingeschoben: 2 Profile × 2 Kerne × 3 Längen (5/20/80 mm) × 3 Spiele
  (0,1/0,25/1 mm) × 2 Kopfhöhen (automatisch/1 mm) × 5 Einschubstände.
  **360 Fälle, größtes Überschneidungsvolumen 0,0 mm³**; jeder Einsatz geschlossen
  und zusammenhängend. Die Einschubstände enthalten den vollständig äußeren,
  teilweise eingeschobenen und vollständig eingeschobenen Zustand.
- Zum Vergleich kollidierte die bisherige rechteckige 2020-Kontur bei 0,25 mm
  Spiel mit 115,371761 mm³, die bisherige 3030-Kontur mit 0,508483 mm³.
- Der Bereichsnachweis der Nutfeder umfasst 80 geprüfte Ecken und 16 begründet
  ausgeschlossene Kombinationen.
- Drei neue ungültige Tabellenfälle waren zunächst rot und nach der Typprüfung
  grün. Der gemeinsame Lauf mit den Normteilfällen bestand mit 15 Fällen.

Ausführliche lokale Messdateien stehen in
`F:\solidon-review-reports\codex-2026-10-03\geometrie\rm017-assembly.json` (einschließlich SHA256 der Quellen),
`rm017-tongue-both-tests.txt`, `rm017-table-red.txt` und `rm017-table-green.txt`.

## Native Bedienprüfung

Der sichtbare Weg wurde ohne Befehlspalette bedient: Neues Projekt → Bausteine →
angebotenen Quader anlegen → Bausteine → Suche „Profil“ → Nutfeder für Aluprofil
→ Einfügen. Die leere Szene sperrt das Einfügen und bietet einen passenden
Grundkörper an. Die Vorgabe nennt Motedis 20×20 B-Typ Nut 6. Alle fünf Profile
sind im geöffneten Auswahlfeld lesbar; die drei bisherigen Größen tragen den
Hinweis auf ältere Maße.

Auf dem Quader 40×30×20 mm entsteht mit dem 2020-Profil ein geschlossener Körper
mit 25,29 mm Gesamthöhe. Der Wechsel im Verlaufsdialog auf das 3030-Profil zeigt
eine größere Vorschau und ergibt 28,79 mm. Strg+Z stellt die kleine Nutfeder
wieder her; Bearbeiten → Wiederholen stellt die größere wieder her. In der
isometrischen Ansicht sind Hals, Kopf und Einführschrägen sichtbar. Der
Prüfbericht nennt den Überhang. Speichern erzeugt
`F:\solidon-review-reports\codex-2026-10-03\geometrie\rm017-native-3030.p3d` (1 415 Byte); der Fenstertitel
und die Statusmeldung bestätigen das Speichern. Wiederöffnen steht noch aus.

## Noch laufende gemeinsame Abnahme

Der vollständige Bereichslauf nach den gemeinsamen Formkorrekturen ist beendet:
alle 41 Bausteine nachgewiesen, anschließendes `--check` meldet 41/41 aktuell,
und `test_every_shipped_part_carries_a_current_range_proof` besteht. Das
Laufprotokoll liegt unter `F:\solidon-review-reports\codex-2026-10-03\geometrie\part-ranges-final.log`.

Die verbleibenden nativen Folgefälle und das Entwicklungstor gehören zur
laufenden Gesamtarbeit. Dieser Bericht erklärt diese Prüfungen noch nicht
für bestanden.
