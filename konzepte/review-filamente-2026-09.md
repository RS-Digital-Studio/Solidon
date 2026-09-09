# Filamente — Gestaltung und Gesamtreview

Stand: 08.09.2026. Auftrag: das Filamentlager schöner gestalten, sämtliche
Filamentwege nach `engineering:code-review` prüfen und bestätigte Befunde
einschließlich ihrer Anschlüsse beheben. Maßstab sind Bauplan §2, §19, §20,
§22, §25 und §29 sowie die präzisierten Verträge im
[Filamentlagerkonzept](konzept-filamentlager-2026-09.md#14-review-und-präzisierte-verträge).

## Umfang und sichtbares Ergebnis

Geprüft wurden Lager, Spulendialog, Importvorschläge, Schnellwahl, ganze Körper
und einzelne Flächen, Projektübersicht, Speichern und Undo, Herstellerprofile,
Auswahl- und Plattenexport, G-Code-Mengen, Buchungsangebote, manuelle Aufteilung,
Korrektur, Rücknahme und die atomare Lagerdatei. Dazu gehören unbekannte Daten,
gleichnamige Spulen und Änderungen zwischen Auswahl und Bestätigung.

Das Regal verwendet ruhigere Karten mit erkennbarer Spulengeometrie und
hervorgehobenen Restmengen. Suche und Hauptaktionen stehen zusammen; Details
und Journal haben eine klare Lesereihenfolge. Der Spulendialog zeigt Lagerort
und Nennfüllung direkt. Die Verbrauchsanzeige gliedert je Filament Name, Menge,
Herkunft, gegebenenfalls Preis und die zugehörigen Handlungen. Helle und dunkle
Darstellung sowie große Schrift und schmale Auswahlkarten wurden nativ geprüft.

## Bestätigte Befunde und Behebung

| Priorität | Auslöser und frühere Folge | Behebung und Regression |
|---|---|---|
| P1 | Ein älterer Dialog bestätigte nach einer neueren Korrektur seine veraltete Verbrauchsaufteilung. | `book` prüft `expected_booking_updated_at`; gleiche Zustellungen bleiben idempotent. UI übergibt den gelesenen Vorgangsstand. |
| P1 | Eine einzelne Fläche teilte Slot 0 mit anderen Flächen; eine vermeintliche Abwahl hätte deren gemeinsame Definition geändert. | Registrierte `clear_filament`-Operation mit neutralem Slot und sicherem Umlegen der übrigen Flächen. Geometrie-, Auswahl- und Workflowtests prüfen Nachbarflächen, Achtergrenze und Undo. |
| P1 | Nach Abwahl oder Umordnung änderte sich die Slotreihenfolge; positionsgebundene Herstellerprofile konnten beim anderen Filament landen. | `slot_profile_bindings` speichert vollständige Filamentidentitäten. Alte Wahlen werden an der ursprünglichen vollständigen Szene gebunden. Formatmigration, Export, Qualitätswechsel und Undo sind angeschlossen. |
| P2 | Export nur des zweiten Körpers las durch dessen neue Werkzeugnummer das erste Herstellerprofil: 5 statt 21 mm³/s. | Auswahl-Export bildet Profile über die Filamentidentität ab. Regression liest die echte 3MF und vergleicht den Verbrauchsfingerabdruck. |
| P2 | Eine angezeigte Spule wurde vor Bestätigung umbenannt, archiviert oder in Typ/Farbe/Profil geändert. | Beide Wähler prüfen die angezeigte Identität erneut und aktualisieren ihre Angebote mit bleibendem Hinweis. Reine Restmengenänderungen bleiben zulässig. Manuell geänderte Projektwerte verlieren die vorgemerkte Lagerbindung. |
| P2 | Verwaiste Slotdefinitionen erschienen als benutzte Filamente; gemischte Auswahl verschwieg Teile ihres Wirkungsbereichs. | Übersicht und Schnellwahl lesen tatsächlich verwendete Mesh-Slots. Gleiche Druckidentität zählt je Körper einmal; der Text nennt Körper und Flächen getrennt. |
| P2 | Eine Vorbelegung für den ganzen Körper konnte eine geometrisch gefundene Fläche als ausdrücklich ausgewählt übernehmen. | `values_for_object` entfernt ihre abgeleiteten Einzel- und Mehrfachverweise. Eine tatsächliche Flächenwahl und ausdrücklich übergebene Werte bleiben erhalten. Der allgemeine Registertest prüft beide Feldarten. |
| P2 | RM-135: Lange Hinweise wurden abgeschnitten, während versteckte Abstände und überzählige Mindestzeilen Platz beanspruchten. | Qt misst den tatsächlichen Zeilenumbruch und sichtbare Bedienelemente. Acht Regressionen prüfen knappen/freien Platz, leere/volle Listen und große Schrift; der Mac-xfail entfällt. Native Windows-Abnahme ist grün, der native Mac-Lauf bleibt gesondert nachzuweisen. |
| P2 | Zusätzliches Stützfilament des Slicers fehlte in der Verbrauchsliste; eine Gesamtlänge konnte beim einzigen Modellfilament landen. | Zusätzliche Werkzeuge erhalten ungebundene Bedarfzeilen. Tatsächliche Werkzeugwechsel verhindern falsche Gesamtzuordnung. Unbelegte Einzelmengen bleiben unbekannt. |
| P2 | Die Ergebnisanzeige rechnete Längen mit 1,75 mm um, die Lagerbuchung bereits mit dem tatsächlichen Durchmesser. Später geänderte Dialogwerte konnten die Anzeige erneut verfälschen. | Ergebnis und Buchungsangebot verwenden dieselben eingefrorenen Einzelmengen. Tests vergleichen 2,85 mm, verschiedene Materialien und fehlende Kennwerte. Direkte Grammwerte einschließlich null haben Vorrang. |
| P2 | Ein später eintreffendes Ergebnis änderte den Buchungsstatus einer anderen gerade ausgewählten Ausgabe. | Anzeige und bevorzugtes Angebot folgen dem jeweiligen Fingerabdruck; neuere G-Code-Aufteilungen bleiben bei älteren Schätzungen erhalten. |
| P2 | Ein bewusst geändertes Herstellerprofil verlor die Bindung zur bereits gewählten physischen Spule. Ein fehlendes Profil erschien zudem als anderes verfügbares Profil. | Die Spulenbindung folgt dem ursprünglichen Slot, die Druckwerte und der Fingerabdruck dem gewählten Profil. Fehlende Profile bleiben ausdrücklich mit Originalnamen ungelöst sichtbar. |
| P2 | Ein gültiger Herstellername wie `Generic Support for PLA/PETG @System` wurde als Dateipfad abgewiesen. | Interne Schrägstriche bleiben Namenszeichen; absolute Pfade, Backslash und Traversierungssegmente werden weiterhin abgewiesen. Der Name wird nicht als Dateipfad geöffnet. |
| P2 | Beschädigte historische Positionen, Revisionen oder Zeitwerte blieben lesbar und konnten beim nächsten Schreiben übernommen werden. | Die vollständige Korrektur- und Rücknahmekette wird vor jeder Änderung geprüft; beschädigte Dateien werden nicht überschrieben. |
| P2 | Sehr große Zahlen erzeugten nackte Überlaufausnahmen; ein binärer Rest bei `3,3 − 1,1 − 2,2 g` galt als Unterdeckung. | Zahlenüberläufe werden atomar mit Handlungsvorschlag abgewiesen. Ausschließlich Maschinenrundungsreste werden normalisiert; tatsächliche Unterdeckung bleibt unbekannt. |

Die Zuständigkeiten bleiben getrennt: Geometrieoperationen tragen keine lokalen
Spulenkennungen, die Projektbindung bezeichnet eine physische Spule, das
Herstellerprofil bezeichnet Druckwerte. Die Lageränderung läuft vollständig
unter einer Dateisperre. Eine ausgegebene Datei beweist keinen erfolgten Druck.

## Möglichkeiten zur Weiterentwicklung

Diese Punkte sind Produktvorschläge, keine verbliebenen Fehler des beauftragten
Vertrags und keine verdeckten Umsetzungszusagen:

1. **Lager sichern und wiederherstellen.** Ein sichtbarer Export-/Importweg
   könnte die Lagerdatei samt Journal sichern. Beim Wiederherstellen wären
   Lageridentität und bestehende Projektbindungen ausdrücklich zu behandeln.
2. **Wiegeereignisse mit Verlauf.** Der heutige Bestandsschutz bewahrt jüngere
   Feststellungen. Ein eigener rücknehmbarer Wiegeverlauf könnte zusätzlich
   Tara und den Grund einer Korrektur sichtbar machen.
3. **Historische Kosten.** Preis und Währung je Buchungsposition würden spätere
   Kostenberichte ermöglichen, ohne vergangene Drucke mit dem heutigen
   Spulenpreis neu zu bewerten.

Die Reihenfolge bewertet den unmittelbaren Kundennutzen: zuerst eine bedienbare
Sicherung, danach nachvollziehbares Wiegen, zuletzt historische Auswertungen.
Eine Umsetzung braucht einen eigenen abgegrenzten Produktvertrag in der Roadmap.

## Prüfbelege

Die gezielten Regressionen liegen in den bestehenden Filament-, Paint-, G-Code-,
Druckeinstellungs- und Projekttests. Die nativen Bedienbilder der Durchsicht waren lokale
Prüfbilder und keine neuen Veröffentlichungsbilder. Endgültige Torwerte werden nach dem abschließenden
Lauf im Roadmap-Archiv festgehalten.

Das unabhängige Gegenreview hat die behobenen Befunde und anschließend die
abgegrenzte Commit-Einheit geprüft. Serialisierung, Format 22, Exportbasis,
Featurelisten und Lager sind vollständig angeschlossen; weitere bestätigte
Commit-Lücken wurden dabei nicht gefunden. Die Erweiterungen des G-Code-Lesers
werden als gemeinsame Voraussetzung vor der Filamenteinheit eingecheckt.
