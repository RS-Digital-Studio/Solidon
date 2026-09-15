# Kundenorientierte Website und Funktionsabdeckung

## Ergebnis

Die Startseite erklärt das Produkt eigenständig. Die Funktionsseite bietet
sechs Einstiege nach Kundenaufgabe, bebilderte Erläuterungen und native
Aufklapper für zusätzliche Werkzeuge. Bestehende Seitenadressen und Sprungziele
bleiben erhalten. Alle sechs Sprachfassungen tragen denselben Umfang.

Die Beschreibungen decken alle 110 Operationen des angebotenen Pakets 0.4.2 ab.
Zusammen mit den Ergänzungen für die nächste Demo sind 121 Operationsnamen
zugeordnet. Die Seite geht erst gemeinsam mit dieser Demo online; die
Funktionen werden deshalb ohne Entwicklungsvorbehalt beschrieben. Eine neue
Websiteprüfung vergleicht diese
Zuordnung zwischen den Sprachen und verlangt für jede veröffentlichte Operation
eine Beschreibung. Zählungen beziehen sich auf die beim Release
erzeugte Registerreferenz; deren Version muss zur Downloadliste passen.

Bohrung und Senkung in einem Schritt **anlegen** ist im regulären Umfang
erklärt. Bohrung samt Senkung und Stufen gemeinsam **ändern** ist ebenfalls
beschrieben. Dazu kommen Organizer, Öffnungsfelder, Konturauswahl,
örtliche Erkennung und das Weiterbearbeiten von Oberflächenmustern.

README, Handbuchquelle mit fünf Übersetzungskatalogen und die lokalen Texte
für 20 Workshopvideos wurden nachgezogen. Die öffentlichen Handbuchinhalte
bleiben passend zur Downloadversion; neue Inhalte werden beim nächsten
Paketbau daraus erzeugt. YouTube wurde nicht verändert.

## Bilder

Vier sprachneutrale WebP-Dateien mit jeweils 1200 × 800 Pixeln zeigen echte
Ergebnisse registrierter Operationen: Senkbohrung vorher/nachher, Organizer,
Oberflächenmuster und ein Öffnungsfeld. Zusammen sind sie rund 92 KB groß.
Die Bilder stehen mit Alternativtexten und festen Seitenverhältnissen im HTML.

`tools/make_feature_images.py` erzeugt jedes Motiv in einem eigenen nativen
Prozess. Alle vier Prozesse endeten mit Exit 0; die sieben dargestellten
Körper sind geschlossen, zusammenhängend und haben positives Volumen.
Parameter und Messwerte stehen unter `../feature-images-2026-09-15/`.
Die Rechtekette steht in `ASSET-RIGHTS.toml`.

## Prüfungen

| Prüfung | Ergebnis |
|---|---|
| Website, Website-Zielgrößen und Asset-Rechte | 412 bestanden, Exit 0, 35,68 s |
| Abschließende Websiteprüfung nach Anpassung der Verfügbarkeitstexte | 401 bestanden, Exit 0, 32,02 s |
| Handbuch ohne erzeugte Release-Artefakte | 83 bestanden, 60 abgewählt, Exit 0 |
| Eigene 20 übersetzte Handbuchabschnitte | Vollständig, Absatzstruktur geprüft, Exit 0 |
| Helix-Erkennung mit kurzen breiten Innen-/Außengewinden | 55 bestanden, Exit 0 |
| Neuer Helix-Gegenfall und beide betroffenen Galerien | 3 bestanden, Exit 0 |
| Ruff und Format aller sieben eigenen Python-Dateien | Exit 0 |
| Mypy des Bildgenerators und des Helixmoduls | Exit 0 |
| SEO und Inhaltsstempel | Exit 0; letzter Stempellauf ohne weitere Änderungen |
| Eigener Diff auf Whitespacefehler | Exit 0 |

Die Galerieprüfung fand eine Nullnormale aus flächenlosen Dreiecken in der
Helix-Erkennung. Drei Zeilen filtern ausschließlich solche richtungslosen
Achskandidaten. Ein analytischer Regressionstest reproduzierte den Fehler vor
dem Fix; danach rechnen auch die beiden bestehenden Galeriemodelle wieder.
Die Eingangsgeometrie bleibt unverändert.

### Browser

Codex In-app Browser, lokale HTTP-Vorschau auf Port 8765. DE, EN, ES, FR, IT
und PT: Start- und Funktionsseite jeweils bei 1440 × 900 und 390 × 844 CSS-Pixeln
geprüft. Die neuen Bildbereiche wurden in jeder Kombination sichtbar angesehen;
kein seitlicher Überlauf an Überschriften, Karten, Werkzeuggruppen oder
Aufgabenlinks. Die Screenshots stehen in den Browserausgaben der Sitzung.

Zusätzlich repräsentativ in DE: Werkzeuggruppe und Querschnitt mit Enter öffnen
und schließen, Tab und Umschalt+Tab, sichtbarer Fokus, alle neuen Bedienziele
mindestens 44 Pixel hoch. Mobiles Kopfmenü öffnet und schließt nach der Wahl;
Sprachwechsel führt auf die englische Funktionsseite. Keine Warnungen oder
Fehler in den abgefragten Konsolenmeldungen.

Der Browser meldete dunkles Farbschema und normale Bewegung. Die verfügbare
Browsersteuerung bietet keine Umschaltung dieser Medienzustände; heller Modus
und reduzierte Bewegung wurden in dieser Abnahme nicht visuell bestätigt.
Die neuen Komponenten verwenden die bestehenden Farbvariablen und keine
eigenen Animationen. Der Befund ist eine Grenze der Abnahme, kein bestätigter
Darstellungsfehler.

## Abgrenzung und Git

Im gemeinsamen Arbeitsbaum laufen weitere Änderungen an Profilklemmen,
Dichtungen und Merkmalsbearbeitung. Die projektweiten statischen Prüfungen
waren dort noch rot; auch die Katalogprüfung meldete fremde neue Texte und
Erläuterungen. Die erzeugten Handbuchreferenzen unterscheiden sich erwartbar
vom unveröffentlichten Register. Diese Dateien wurden nicht zurückgesetzt
oder für die Websitearbeit mit übernommen.

Ein vollständiges Freigabetor aus geteilter Suite und Leistungstests wurde
nicht als bestanden behauptet. Der Commitumfang umfasst ausschließlich die
Websitearbeit, ihre Begleittexte und Nachweise; die kleine Helixkorrektur bildet
einen eigenen Commit. Die Veröffentlichung der Seiten erfolgt gemeinsam mit
der nächsten Demo. Diese Websitearbeit führt selbst keinen Upload und keinen
Release aus. Die lokale Vorschau zeigt bereits die überarbeiteten Seiten.
