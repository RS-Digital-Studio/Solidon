# Auftrag für die parallele Aufgabe

Arbeite in `F:\3D Druck` an der technischen Vorbereitung von **RM-188 / P2.7: sämtliche Bausteine auf dem exakten Kern**. Liefere gründliche, ausführbare Machbarkeitsnachweise und eine belastbare Übergabe für die spätere Produktintegration. Dies ist ein begrenztes Teilpaket des bereits genehmigten CAD-Ausbaus.

Lies zuerst die geltenden `AGENTS.md`, `CLAUDE.md`-Karten, passenden `.claude/rules/` und einschlägigen Projekterfahrungen. Danach:

- `konzepte/konzept-vollwertiges-cad-2026-09.md`, insbesondere P2.7, §§13.6, 13.8.1 und 13.10;
- `konzepte/recherche-cad-paritaet-2026-09.md`;
- `konzepte/durchsicht-cad-konzepte-2026-09.md`;
- `konzepte/konzept-bedienung.md`;
- den aktuellen Stand von RM-188 in `ROADMAP.md`.

Die Hauptaufgabe verantwortet die Produktintegration einschließlich Kernverträgen, Wahrnehmung, Cache, Transformationen, Oberfläche und Sprachkatalogen. P1.3/P1.6 sind inzwischen eingecheckt; weitere CAD-Pakete folgen im selben Baum. Fremde Änderungen niemals zurücksetzen oder mitcommitten. Kein Worktree. **`website/` bleibt vollständig unangetastet.** Erstelle keine weitere Aufgabe.

**Dein alleiniger Schreibbereich ist `konzepte/nachweise-cad-p2-7/`.** Lege dort Bericht, reproduzierbare Prüfkörperbeschreibungen und ausführbare Python-Sonden ab. Produktionscode, bestehende Tests, Bauplan, ROADMAP, bestehende Konzepte, gemeinsame Regeln und Sprachkataloge liest du nur. Damit kannst du sofort unabhängig arbeiten. Der Produktionsanschluss und die gemeinsame Statuspflege bleiben bei der Hauptaufgabe; die Voraussetzungen der Konzeptreihenfolge werden dadurch nicht übersprungen.

Arbeite diese Punkte vollständig ab:

1. Lade die tatsächlichen Bausteinregister über den vorhandenen Bootstrap. Ermittle die aktuelle vollständige Bausteinliste und jeden noch konvertierenden Pfad. Prüfe die Konzeptangabe „35 Bausteine / 31 konvertierende Pfade“ am Code; Abweichungen belegen, nicht passend rechnen.
2. Ordne jeden Pfad seiner Bausteingruppe zu und dokumentiere Eingaben, Maße, Normteilbezüge, benannte Merkmale, Material-/Filamentanschlüsse und den heutigen Konvertierungspunkt. Suche gemeinsame Geometriehelfer und fachliche Zwillinge vor jedem neuen Prototyp.
3. Erarbeite mit dem bereits installierten und festgeschriebenen OCP-/OCCT-Satz einen exakten Bauweg pro benötigter Konstruktion. Vorhandene APIs und Helfer zuerst verwenden. Eine Bibliothekslücke anhand eines konkreten Gegenfalls belegen; keine neuen Abhängigkeiten installieren und keine Lizenzen pauschal freigeben.
4. Baue eigenständig ausführbare Sonden mit `.venv/Scripts/python.exe`. Prüfe tatsächliche native Gültigkeit, Körperzahl, unabhängig hergeleitete Maße und Volumina, Auswahlflächen und Merkmalsrollen. Bei Bohrungen, Senkungen, Gewinden und Klemmungen zählen die echten Funktionsmaße und die Richtung, nicht bloß ein plausibles Gesamtvolumen. Je Bausteingruppe charakteristische Fälle, relevante Parametergrenzen und bewusste Gegenfälle verwenden. STEP-Rundreise und unveränderte Eingabeformen mitprüfen.
5. Vergleiche den vorhandenen Netzweg und den vorgeschlagenen exakten Weg anhand derselben fachlichen Anforderungen. Dokumentiere erlaubte Facettierungsunterschiede getrennt von echten Form- oder Maßabweichungen. Keine toleranzgelockerten Tests und kein erneutes Nachbauen der Anwendung im Sondenordner.
6. Liefere eine vollständige Übergabematrix: Baustein/Pfad, verwendete vorhandene API beziehungsweise nötige Eigenentwicklung, geprüfte Fälle und direkte Exitcodes, verbleibende Lücken, genaue spätere Integrationsdateien und Abnahmekriterien. Halte den Kundenweg und seine bestehenden Bezeichnungen mit fest; ein weiterer Kernwahl-Haken ist keine Lösung.

**Prüfregel dauerhaft:** Fensterdateien und Leistungsprüfungen ausschließlich beim Release, auch keine gefilterten Fensterfälle oder verdeckten Laufzeitmessungen. Hier nur funktionale Kernsonden und statische Prüfungen. Keine Screenshots, Handbücher, Paketbauten, Versionserhöhung oder Veröffentlichung. Zurückgestellte Prüfungen niemals als bestanden ausweisen.

Arbeite selbständig bis zur fertigen Übergabe. Halte den Ausgangscommit und die tatsächlich gelesenen Dateistände fest, weil parallel weiterentwickelt wird. Keine Gesamtfertigmeldung für P2.7: Sonden beweisen die geprüften Bauwege, noch keinen integrierten Kundenweg. Eigene abgeschlossene Einheiten nur mit explizitem Pathspec committen und pushen, wenn das vorgeschriebene Entwicklungstor tatsächlich für den vorgesehenen Commitstand grün ist. Bei laufendem fremdem Zwischenstand nichts reparieren oder ein grünes Tor behaupten; die fertige Übergabe mit genauer Dateiliste für den gemeinsamen Commit bereitstellen.
