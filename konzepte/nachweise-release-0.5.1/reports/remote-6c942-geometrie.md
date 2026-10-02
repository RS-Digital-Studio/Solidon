# Remote-Geometriereview 6e1c4896 → 6c9420b1

Fest geprüft: `6e1c4896fc77cf972260068f0635816f39c96238` → `6c9420b1fc78da491a9d7eff89279648b1b68d9e`. Ausschließlich `app/core/geom/prepare_ops.py`, `tests/test_prepare.py`, `tests/test_exact_body_parity.py`; sämtliche geänderten Zeilen (+245/−3) und erforderliche Anschlüsse gelesen. Grundlage sind gespeicherte Gitblobs unter `remote-6c942-geometrie-quellen/`, mit SHA256 in `manifest.json`. Livebaum und QA wurden nicht verändert.

## P2 G-CUT-01 — Mehrdeutige Restfläche wird als sichere Fortführung bestätigt

**Stelle:** `app/core/geom/prepare_ops.py:17740–17748` im neuen `_cut_faces_continued`.

Der Helfer nimmt alle neuen ebenen Flächen mit gleicher Normale und Ebene. Er wählt allein den größten Flächeninhalt; bei Gleichstand bleibt der zuerst durchlaufene Dictionary-Eintrag. Diesen benennt er auf die alte Kennung um und meldet `(name, name)` als bestätigte Fortführung. Auch die räumliche Zugehörigkeit zur alten Fläche fehlt. Sein eigener Docstring behauptet den Vertrag von `evaluate._divided_partners`, den er damit nicht vollständig einlöst.

Der vorhandene R4-Weg prüft in `evaluate._pieces_in_place:2213–2238` zusätzlich die Lage innerhalb der alten Fläche. `_divided_partners:2369–2375` hält gleich große Reste ausdrücklich als mehrdeutig fest. Das ist im neuen Zweig keine bloße Reihenfolgefrage der Darstellung: `_with_features:3691–3698` nimmt eine bestätigte Fortführung aus `unproven` heraus; die Bestätigung geht anschließend in `_continued_match_result` ein (Zeile 3725). Die vorangehende strukturelle Prüfung von Fortführungen prüft keine geometrische Eindeutigkeit. Ein abhängiger Bezug kann daher ohne die erforderliche Rückfrage am willkürlich ausgewählten Rest weiterlaufen.

**Konkreter quellenbasierter Gegenfall, nicht ausgeführt:** Ein vereinheitlichter, 10 mm hoher U-Körper hat Arme `x=[0,30], y=[10,20]` und `x=[0,30], y=[−20,−10]` sowie die Brücke `x=[20,30], y=[−10,10]`. Seine gemeinsame Oberseite trägt einen Namen, auf den eine Folgeoperation verweist. `cut_away(axis="x", position=10, keep="below")` entfernt die Brücke. Zwei gleich große Oberseiten von jeweils 100 mm² bleiben. Wenn die allgemeine Zuordnung diese stark verkleinerte alte Fläche nicht mehr verbindet, erfüllen beide neuen Oberseiten exakt die Kandidatenbedingungen. Der Helfer bestätigt die zuerst gelistete. Der alte gemeinsame Name ist damit ohne fachliche Entscheidung nur noch einem Arm zugeordnet. Umkehr der Kandidatenordnung kehrt diese Entscheidung um.

**Erwartung:** Gleichwertige Reste bleiben mehrdeutig und werden beim tatsächlich benötigten Flächenbezug geklärt. Nur eine belegte eindeutige Fortführung darf die Nachfrage unterdrücken. Regel 21 und der Merkmalsvertrag aus Bauplan §21.2 gelten auch am exakten Kern.

**Korrekturrichtung:** Vorhandene R4-Entscheidung einschließlich räumlicher Herkunft und Gleichstandsbehandlung gemeinsam nutzen oder die eindeutige Herkunft aus der nativen Builderhistorie belegen. Eine Regression muss das registrierte Abschneiden mit einem realen nachfolgenden Flächenbezug prüfen; Kandidatenreihenfolge, gleich große Reste und fremde koplanare Fläche gehören dazu. Kein zentraler Produktfix vorgenommen.

## Übrige geprüfte Anschlüsse

- Die bisherige Ebenenberechnung und Parameterbedeutung bleiben erhalten. Der neue native Zweig verwendet dieselbe Ebene und `keep`-Umkehr. Der Werkzeugrahmen stellt die Unterseite des auf Z=0 beginnenden Kastens auf die Schnittebene. Seine positive Normalenseite wird entfernt. Der aus der Körperdiagonale abgeleitete Kasten deckt bei einer tatsächlich schneidenden Ebene den notwendigen Körperbereich ab. Leere beziehungsweise wirkungslose Ergebnisse werden per vorhandener fachlicher Fehlermeldung abgewiesen.
- Der BRep-Zweig nutzt `brep_input`, die native Differenz, Vereinheitlichung und `_exact_body_checked`; er gibt einen `Solid` zurück. Es wird keine Netzdatenstruktur lediglich als BRep etikettiert. Ein native Fehler wird nach dem bestehenden BRep-Vertrag weitergegeben, kein stiller Netzrückfall eingeführt. Die Zwillingstabelle wurde von `MESH` auf `KEEP` geändert; deren bestehender End-to-End-Test prüft an Zeile 1580 auch den echten Datentyp.
- `result_kind="mesh"` entfällt zutreffend. `cut_away.cache_version` steigt von 3 auf 4. Die vorhandene Cachegeneration erhält dadurch einen neuen Operationsschlüssel. Parameter-, Projektformat- und Historyschema werden nicht geändert; ein eigener Speicher-/Undo-Lauf fand nicht statt.
- Bestehende native Filamentslot-Historie wird verwendet; neue Schnittflächen fallen wie im bestehenden Netzvertrag auf den Vorgabeslot zurück. Vor/nach den nativen Schritten sowie in Merkmalserkennung und Zuordnung sind die vorhandenen Abbruchanschlüsse vorhanden. Native Build-/Unify-Aufrufe bleiben im Aufruf selbst ununterbrechbar; eine neue gemessene Laufzeitbehauptung lässt sich aus diesem Quellenreview nicht ableiten.
- Die neuen acht Quaderfälle prüfen beide Körperarten mit gerader, schräger und flächenbezogener Ebene über `History` und `evaluate`, dazu Volumen, Wasserdichtheit und Körperart. Der zusätzliche Mehrkomponentenfall ist ausdrücklich ein Netz. Keiner dieser neuen Tests prüft eine mehrdeutige oder räumlich fremde Flächenfortführung.

## Grenzen

Keine Tests, Produktimporte, Geometrieberechnungen, Fenster-, Render- oder Leistungsläufe durchgeführt. Die genannten Testaussagen beschreiben gelesenen Testcode, kein eigenes grünes Ausführungsergebnis. Insbesondere ist der U-Körper ein aus dem Quellvertrag abgeleiteter Gegenfall und keine gelaufene OCP-Sonde.

Der native Schnitt umgeht den bisherigen Netz-Kontaktwächter `check_cut_contact`. Die bisherigen Tangentialfälle in `test_tangent_cuts.py` gelten für Netze; in diesem Diff fehlt ein entsprechender nativer Kontaktfall. Ohne Ausführung wird daraus kein tatsächlich ungültiger BRep-Körper und kein zweiter bestätigter P2 behauptet. Diese Grenze gehört zur nachfolgenden fachlichen Abnahme.

**Kann diese Einheit unverändert rein? Nein — G-CUT-01 muss geklärt werden.**
