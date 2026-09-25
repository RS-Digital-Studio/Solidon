# Dreiecksnetz, Reparatur und Formenerkennung

Stand: 24.09.2026. Arbeitsbaum in `F:\3D Druck`, Ausgangscommit
`8ed5d6299ce425de90366fd9c4128ccb2147fcf6`. Mehrere Aufgaben arbeiten im selben
Arbeitsbaum. Die nachfolgenden Änderungen gehören zur Dreiecks-/Reparaturdurchsicht;
Erkennungsgrenzen, Langlochbearbeitung und Testlaufoptimierung sind getrennte Aufgaben.

## Behobene Fehler

- Normalenkorrekturen erkennen geänderte Dreieckswindungen auch bei unverändertem
  Volumen. Die Quelle wird nicht verändert.
- Vernähte und geschlossene Stellen übernehmen Farben und Filamentzuweisungen
  von ihren Ausgangsflächen. Neue Lochdreiecke folgen auch neu entstandenen Diagonalen.
- Überlappende geschlossene Außenschalen werden als getrennte Operanden vereinigt.
  Zwei Würfel mit 20 mm Kantenlänge und je 8 mm Versatz ergeben analytisch
  **14.272 mm³**, auch weit vom Ursprung. Der vorherige Weg ergab **12.544 mm³**.
  Innenschalen werden nicht als zusätzliches Material behandelt.
- Erfolg bei Durchdringungen wird erst nach vollständiger Nachprüfung gemeldet.
  Gescheiterte oder unvollständige Versuche erhalten den Ausgangskörper. Abbruch
  bleibt Abbruch; Restfehler nennen eine ausführbare Handlung.
- Eine unvollständige Defektkarte zeigt ungeprüfte Bereiche als unbekannt.
  Bereits belegte Fehler bleiben sichtbar.
- Der ausdrückliche Reparaturschritt meldet erkannte Durchdringungen auch bei
  ausgeschalteter Auflösung. Die automatische Lochfüllung beim Import startet
  diese zusätzliche Suche nicht und verweist nicht auf unpassende Ladeeinstellungen.
- Nach verändernder Reparatur werden Merkmale am Ergebnis neu zugeordnet.
  Ein entfernter Stift bleibt nicht als bearbeitbare Form im Objektbaum erhalten.
  Das ist mit Entwurf/Feinqualität, Cache, Speichern/Öffnen und Undo/Redo geprüft.
- Die lokale Erkennung erhält die konkrete Fehlerursache bis zum Dialog:
  falsche oder mehrdeutige Stelle bietet „Andere Stelle wählen“, Bereichsprobleme
  führen zum Suchradius. Eine neue Auswahl verändert noch kein Dokument.
- Großmodellhinweise führen direkt zur lokalen Erkennung der betroffenen Körper.
  Sammelhinweise binden die Auswahl an ihre noch vorhandenen Netz-Körper.
- Im vorhandenen Auswahlzustand bewegt die Tastatur ein sichtbares Fadenkreuz.
  Enter benutzt denselben Originaltreffer wie die Maus; Umschalt bewegt fein.
  Fremde Tastenkürzel bleiben frei. Neue Texte sind in allen fünf Sprachkatalogen ergänzt.

## Nachweise

Interpreter: `.venv/Scripts/python.exe`, Python 3.14.7.
Kern- und statische Läufe verwenden `not windowed and not performance`.
Die Zahlen verschiedener Läufe werden wegen überschneidender Testmengen nicht addiert.

| Lauf | Ergebnis | Nachweis |
|---|---|---|
| Reparatur und Merkmals-Lebenszyklus vor Importanschluss | 63 bestanden, 2 Leistungstests zurückgestellt; Exit 0 | `repair-final.txt` |
| Reparatur einschließlich Importanschluss | 160 bestanden, 8 zurückgestellt; Exit 0 | `python tools/affected_tests.py tests/test_repair.py tests/test_ingest.py --run`; direktes Tool-Ergebnis, kein gesondert gespeicherter Log |
| Defektkarten und Dreiecksschnittsuche | 84 bestanden; Exit 0 | abgeschlossener Direktlauf `pytest -q tests/test_maps.py tests/test_self_intersections.py -m 'not windowed and not performance'` |
| Vollständige Fehlerprüfung nach festen lokalen Kennungen | 325 bestanden; Exit 0 | `affected_tests.py tests/test_errors.py --run` |
| Lokale Fehlerursachen und Weitergabe | 13 bestanden, 22 zurückgestellt; Exit 0 | gezielter Agentenlauf |
| Tastaturkoordinaten, DPI, Grenzen und freie Tastenkürzel | 4 bestanden, 11 zurückgestellt; Exit 0 | gezielter Lauf in `test_local_recognition_flow.py` |
| Lokale Erkennung mit Bericht, Zielbindung und Tastatur am finalen Stand | 46 bestanden, 29 Fensterfälle zurückgestellt; Exit 0 | `local-final.txt` |
| Bestehende fensterlose Berichtshandlungen | 13 bestanden, 593 nicht ausgewählt; Exit 0 | gezielter Agentenlauf in `test_ui.py` |
| Übersetzungen, Sprachregeln und Verzeichniskarten | 529 bestanden, 1 Fensterfall zurückgestellt; Exit 0 | `static-final.txt`; Testoptimierung bündelt inzwischen frühere Einzelparametrisierungen |
| Ruff und Formatierung im gesamten Arbeitsbaum | beide Exit 0; 1.285 Python-Dateien formatiert | abgeschlossene Direktläufe |
| Typprüfung im gesamten Anwendungsbereich | 320 Quelldateien, Exit 0 | `mypy-final.txt` |

Der erste gemeinsame vollständige Kernlauf hatte 17.310 bestandene Tests,
25 übersprungene, 1 erwarteten Fehlschlag und 4 Fehler. Der dynamische lokale
Fehlercode wurde hier behoben; die übrigen Befunde betreffen parallele Aufgaben.
Dieser rote Lauf wird nicht nachträglich als bestanden bezeichnet.
Ein gemeinsamer abschließender Entwicklungslauf wird von der Aufgabe zur
Testlaufoptimierung seit 17:37 Uhr nach Quellruhe durchgeführt; Ergebnis noch offen.
Protokolle: `C:/Users/rober/AppData/Local/Temp/solidon-ci-gemeinsames-tor-20260924/`.

## Grenzen der Abnahme

Keine Fenster- oder Leistungsprüfungen, keine nativen Bildschirmfotos und kein
Release in diesem Auftrag. Die Projektregeln sehen diese Prüfungen ausschließlich
beim Release vor. Neue Fensterfälle für Wiederwahl und Tastatureinstieg sind ergänzt,
aber noch nicht ausgeführt. RM-238 hält die native Abnahme von Fokus, Sichtbarkeit,
DPI, Abbruch, Änderung und Undo offen.

Eine nicht sicher auflösbare Einzelschale bleibt erhalten und wird als Restproblem
gemeldet. Die Reparatur behauptet nicht, jedes beschädigte Netz rekonstruieren zu können.

Kein Commit oder Push. Nach `CLAUDE.md` erfolgt ein Commit nur auf ausdrücklichen
Auftrag. `staged.patch` und `review.index` dokumentieren die eigenen Änderungen in
einem separaten Index; der normale Git-Index bleibt unberührt.
