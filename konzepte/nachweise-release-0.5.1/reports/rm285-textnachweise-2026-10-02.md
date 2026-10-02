# RM-285: Dauerhafte Textnachweise, Stand 02.10.2026

Der Stand trennt drei auf `origin/main` integrierte Textgruppen und die verbleibenden
Modelltexte. Die folgende Tabelle nennt die vollständigen Commitkennungen und das
jeweilige tatsächlich bestandene zentrale Entwicklungstor des ausgewählten Baums.
Suite, Ruff, Format und mypy endeten jeweils mit Exit 0; keine Quelldrift im Tor.

| Gruppe | Commit | Entwicklungstor |
|---|---|---|
| Oberfläche | `b1d5381ce6dec1a2c445a7bfbe18b906866c85b3` | 18.850 bestanden, 62 übersprungen |
| CLI und übriger Kern | `cb20e107b3b4f81cad6cda95c7aa61ca774ba43e` | 18.867 bestanden, 62 übersprungen |
| Bereichsprüfer zusammen mit freigegebener Schnittgrundlage | `eae249d2d7142fdfec3c51a3bcffcefcc7d79af9` | 18.908 bestanden, 62 übersprungen |

## Oberfläche

79 Textausdrücke in 18 UI-Dateien verwenden vollständige Übersetzungsrahmen, darunter
dynamische Titel und zugängliche Beschriftungen. Alle fünf Kataloge erhielten dieselben
50 neuen Schlüssel; 24 global unbenutzte Schlüssel entfielen. Zahlenformat, Einheiten,
Dateinamen und technische Kennungen blieben an ihren bisherigen Quellen.

`tests/test_translations.py::test_translated_surface_labels_do_not_append_a_fixed_colon`
liest die tatsächlichen UI-Quellen. Derselbe Wächter scheiterte am gesicherten
Ausgangsstand mit festen Doppelpunkten, tatsächlicher Exit 1. Die neuen AST-Gegenfälle
prüfen f-Strings, Addition, Formatierung, Platzhalter und technische Syntax;
`test_the_colon_guard_distinguishes_labels_from_internal_syntax` hält diese Grenze.
31 neue reine Fälle bestanden, 155 wurden abgewählt, Exit 0. Sie decken sechs Sprachen,
Verlauf, Maße, Warnungen und teilbezogene Druckvorschläge ab. Der unabhängige Quellreview
fand noch Sicherheitskontakt und dynamisches Maßpräfix; beide wurden vorwärts behoben.
Der erste Lauf mit drei falsch erwarteten Nachkommastellen war ein Testaufbaufehler;
die Erwartungen wurden an die unveränderte zweistellige Millimeteranzeige angepasst.
Dieser rote Lauf ist kein negativer Produktnachweis.

## CLI und übriger Kern

29 vollständige Rahmen in `app/cli/main.py`, `app/core/install.py`, `app/core/log.py`
und `app/core/support.py`; je Katalog 22 neue und 18 entfernte globale Schlüssel.
Rohwerte, Befehle, Zeilenumbrüche, Eingabeschlussleerzeichen und Betreffkürzung blieben
unverändert. 17 neue reine Fälle bestanden, 393 wurden abgewählt, Exit 0.
Der erweiterte tatsächliche Wächter
`test_non_model_surface_labels_do_not_append_a_fixed_colon` scheiterte an denselben
vier alten Quellen mit 25 tatsächlichen Fundstellen: ein erwarteter Fehler, Exit 1.
Eigenreview, unabhängiger Quellreview und zentraler Selektionsreview waren ohne offene
Befunde abgeschlossen. Der Commitbaum dieser Gruppe ist
`2b796336f562805e8dceb201ce60ab2ba86bcc1e`.

## Bereichsprüfer

`app/core/knowledge/parts/range_check.py::check` enthält den vollständigen übersetzten
Rahmen der zu kleinen Wandstärke. Ein Schlüssel kam je Katalog hinzu, einer entfiel.
`tests/test_parts.py::test_range_wall_failure_translates_its_complete_numeric_frame`
prüft sechs tatsächlich installierte Sprachen; die sechs Fälle bestanden.
Die alte Quellzeile scheiterte an derselben Sprachgegenprobe, Exit 1.
Nach der endgültigen gemeinsamen Geometriegrundlage wurden die 35 Baustein-
Bereichsnachweise tatsächlich neu erzeugt, kontrolliert und im oben genannten Commit
integriert. Die frühere Aussage „Bereichsprüferzeile offen“ beschreibt den Stand vor
dieser Integration und gilt nicht mehr.

## Verbleibende Abnahmegrenze

43 feste Doppelpunkte in 42 Ausdrücken aus sieben Agenten-/Steckbriefdateien haben
Modellkontakt. Die selbsttragende Fundstellenliste mit Quellenhashes und Abnahmeweg
steht in [rm285-modelltexte-2026-10-02.md](rm285-modelltexte-2026-10-02.md).
Diese Quellen wurden in den drei Textgruppen nicht geändert. Die vorgeschriebene
Modellsuite ist nicht gelaufen; lokale Textfälle ersetzen sie nicht. RM-285 bleibt
deshalb insgesamt offen. Fenster-, Renderer-, Leistungs- und neue Paketabnahme gehören
zum Release und sind durch die genannten Entwicklungstore nicht belegt.
