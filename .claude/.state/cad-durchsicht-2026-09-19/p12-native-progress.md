# P1.2 — laufender nativer Anschluss

Ausgangscommit ist `0094eea20b12180f90f58ff51140a210bc74eba4`, gepusht.
Der vorherige vollständige Entwicklungsnachweis (12.063 bestanden,
26 übersprungen, Ruff/Format/mypy/Suite und Elternprozess jeweils 0) gehört
zu diesem Ausgangsstand, nicht zu den folgenden uncommitteten Änderungen.

Root besitzt `app/core/brep/canonical.py`, `features.py`, `CLAUDE.md`
und `tests/test_brep_surfaces.py`.

- Der bestehende gemeinsame Helfer heißt jetzt `canonical.surface_sample`.
  Er liefert einen wirklich innerhalb der Trimmung liegenden Punkt samt
  orientierter Normaler; kein zweiter Probensucher entstand.
- Kugeln erhalten den echten Trägerursprung, Radien werden nicht im Kern
  gerundet. Die Materialseite kommt aus orientierter Normaler gegen
  Kugelradiale. Kugelige Eckverrundungen behalten ihren Anzeige-Schwerpunkt.
- Native Basismerkmale, geschlossene Langlöcher und Innenräume tragen die
  neue Maßquelle `native`. Ganze native Restflächen überschreiben nur
  `area` und `centre`; andere Angaben behalten die eingehende Quelle.
  Offene Langlöcher bekommen ihre Fitquellen durch den Meshagenten.
- 24 analytische Fälle (Halbkugel/Kalotte, Kuppel/Pfanne, Verschiebung,
  Drehung, Spiegelung und zwei Tessellierungen) zuerst tatsächlich rot,
  dann grün. Präzises R8,123456789 deckt auch die alte Kernrundung auf.
  Originalbytes, native Gültigkeit, unabhängiges Volumen und exakte Auswahl
  sind geprüft. Das reale Kugelwerkzeug aus `prepare_ops._feature_solid`
  erhält ebenfalls den korrekten Mittelpunkt und Radius.
- Zwei weitere echte STEP-Fälle in draft/fine prüfen Import, Translation,
  wiederholten warmen Cache, Speicherung/Wiederöffnung und Undo/Redo.
  Kennung, Werte, Maßquellen und ursprüngliche STEP-Bytes bleiben erhalten.
  **26 bestanden, 21 abgewählt, 4,27 s, Exit 0** in
  `p12-native-sphere-history.txt`.
- Ruff und mypy der beiden Produktmodule sind grün. Betroffener nativer
  Verbraucherstand: **354 bestanden, 310,42 s, Prozess-Exit 0**;
  Ergebnis steht in `p12-native-consumers.txt`. Dieser Lauf startete vor den zwei zusätzlichen
  Historyfällen, deren eigener Nachweis oben steht.

Parallel besitzt `exact_transform_kernel` Mesh-P1.2 in perceive/features.py
und den Maßtests. `policy_review` baut die gemeinsame Maßquellen-API,
Übernahme, Speicher-/UI- und Erzeugeranschlüsse. Cacheversion und nächste
Commitgrenzen koordiniert Root, keine einzelnen Agentencommits.

P1.2 ist damit noch nicht abgeschlossen. Die neue vollständige Kernprüfung
und gemeinsame Commits/Pushe fehlen. Fensterdateien und Leistung bleiben
ausschließlich beim Release; keine aktuelle native Fensterabnahme behaupten.

## Nativer Anschluss einschließlich rationaler Kugeln

- `SphereSurface` ergänzt die gemeinsame kanonische Auskunft. Der lokale
  private OCCT-Kandidat braucht den vollständigen homogenen Kugelnachweis
  über sämtlichen Bézier-Koeffizienten; originale Trimmung, Materialseite und
  Auswahl bleiben erhalten. Offset-Kugeln sind ohne zusätzlichen Nachweis
  weiterhin unklassifiziert.
- Die bisherigen 24 Kugelabschnittsfälle laufen jetzt auch mit wirklicher
  NURBS-Umwandlung: zuerst 24 neue Fälle rot (keine Kugelerkennung), danach
  48 grün. Die unabhängige Auswahl benutzt die echte ModifiedShape-Zuordnung
  der Konvertierung, keine angenommene Besuchsreihenfolge und keine erneute
  Produktklassifizierung als Sollwert. Der erste Auswahltest hielt irrtümlich
  jede BSpline für eine Kugelhaut; OCCT wandelt auch Ebenen um. Dieser
  Testaufbau ist korrigiert und sein rotes Protokoll erhalten.
- Enge örtliche Ausbeulung mit absichtlich falschem Kugelkandidaten,
  ausgeschöpftes Koeffizientenbudget und Abbruch während der Rechnung
  veröffentlichen keine Kugel. Ein falscher Gegenpunkt lag zunächst exakt
  am Ende der Ausbeulungsstütze; korrigierte echte Innenprobe belegt den Fehler.
- Große Weltkoordinaten deckten einen echten Fehler der NURBS-Flächenintegrale
  auf: die Quadratur verlor Stellen bereits in rationalen Ableitungen.
  `properties._uv_moments` verschiebt deshalb eine private Arbeitsfläche vor
  der Auswertung in den gemeinsamen lokalen Rahmen. Keine Fehlerschranke
  wurde gelockert. Fläche, Volumen und Schwerpunkt einer schrägen Halbkugel
  sind gegen unabhängige Formeln und unveränderte Originalbytes geprüft.
- Vollständiger betroffener nativer Verbraucherlauf nach der Umsetzung:
  **425 bestanden, 400,86 s, Exit 0**, `p23-native-consumers.txt`.
  Enthält `test_brep_surfaces`, `test_brep_canonical_surfaces`, `test_brep`,
  `test_brep_import_workflow`, `test_brep_voids`, `test_solid_ownership`.
- Danach sechs zusätzliche echte Zwillinge geprüft: Kegel/Kugel/Torus,
  je zwei Tessellierungen, schräg gestellt. Sowohl native Erkennung als auch
  der tatsächliche `detect`-Netzweg treffen dieselben unabhängig vorgegebenen
  ungerundeten Maße, Mitten, Materialseiten und vollständigen Originalflächen.
  **6 bestanden, 1,57 s, Exit 0**, `p12-real-round-twins.txt`.
- Ruff der Rootdateien grün. Mypy importierte zwischenzeitlich neun noch
  laufende Mesh-Agentenfehler; dieser meldete sie anschließend behoben.
  Endstatik und gemeinsames Entwicklungstor stehen weiterhin aus.

Root besitzt zusätzlich `brep/properties.py` und die eine Anpassung des
Recognizer-Testdoubles in `test_brep_canonical_surfaces.py`. Keine fremden
Produktdateien und keine Website-Dateien wurden von Root verändert.

## Ergänzter kompletter Rundflächenverlauf

- Bestehenden STEP-Kalottenverlauf auf Kegel, Kugel und Torus erweitert,
  jeweils draft/fine und Qualitätswechsel im selben Ergebnis-Cache. Echte
  Verschiebungsoperation, wiederholter Warmcache, Speichern/Wiederöffnen und
  Undo/Redo prüfen die ursprünglichen unabhängigen Maße und native Maßquellen.
- Die zusätzliche Original-Shape-Prüfung fand im STEP-Schreiber einen echten
  Eigentumsfehler: Bei Kugel und Torus veränderte writer.Transfer Prüfkennzeichen
  der übergebenen Form. Erster Lauf **4 rot, 2 grün**, Exit 1,
  p12-native-round-history.txt. Das ist kein veränderter Sollwert.
- step.write übergibt nun die bereits vorhandene copy_shape-Arbeitskopie.
  Der Test prüft unmittelbar nach dem Transfer und nach jedem Folgeschritt
  sämtliche ursprünglichen Shape-Bytes sowie die unveränderten Projektquellen.
  **17 STEP-/Verlaufsfälle grün**, Exit 0, 3,41 s,
  p12-native-round-history-after.txt; Ruff und mypy für den Anschluss grün.
- Root besitzt damit zusätzlich brep/step.py. Die zugehörige Eigentumsregel
  steht in der bestehenden Brep-Karte. Der gesamte neue Entwicklungsnachweis
  folgt erst nach dem Freeze von Mesh-Verläufen und Export-Lebensdauer.
