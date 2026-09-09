# `app/core/knowledge/` — was die Anwendung weiß

Profile, Normteile, Regelsammlung, Kalibrierung — und in `parts/` die
Bausteinbibliothek (§24, §38, §39).

Die Regeln stehen in `.claude/rules/bausteine.md`.

## Der Grundsatz

**Der Agent setzt geprüfte Bausteine zusammen, statt Geometrie zu erfinden**
(§24). Was hier liegt, ist der Vorrat, aus dem er schöpft — und damit Teil des
Rechenwegs, nicht Beiwerk.

## Die Karte

| Datei | Rolle |
|---|---|
| `profiles.py` | Drucker- und Materialprofile (§38). **Hier stehen die Toleranzen**, auf die `auto:<material>` verweist |
| `standards.py` | Normteilmaße (§24.2) — M3, M4, Einpressbuchsen, Lager |
| `print_settings.py` | Löst Stufe + Material + Drucker zu Einstellungen auf (§29) |
| `rules.py` | Die Regelsammlung für den Agenten (§39) |
| `calibration.py` | Selbstkalibrierung (§28.3) |
| `filaments.py` | Örtliches Filamentlager: Spulen mit beständiger Kennung, optionale Mengen und Angaben, Journal ganzer Druckvorgänge (§20) |
| `licences.py` | Lizenzprüfung der Abhängigkeiten (§36) |
| `tables.py` | Der eine TOML-Leser für Dateien, die auch von Hand geschrieben sein können — ein Syntaxfehler wird ein Satz mit Dateinamen (Regel 17); Profile, Druckeinstellungen und Kalibrierung rufen ihn mit ihrem Titel |
| `parts/` | Die Bausteinbibliothek — eigene `CLAUDE.md`, **eigene Lizenz** |
| `data/` | **Wo das Wissen wirklich steht**: sechs TOML-Dateien (siehe unten) |

## Das Wissen steht in `data/`, nicht im Code

Die Module hier **laden und lösen auf**; die Werte selbst liegen daneben:

| Datei | Inhalt |
|---|---|
| `printers.toml` | Druckerprofile |
| `materials.toml` | Materialprofile — hier stehen die Toleranzen |
| `print_settings.toml` | Druckeinstellungen je Stufe |
| `standards.toml` | Normteilmaße |
| `rules.toml` | **Die Regelsammlung des Agenten** (§39) |
| `licences.toml` | Die Freigabeliste der Abhängigkeiten (§36) |

`AGENTS.md` nennt für die Regelsammlung einen Pfad `core/knowledge/rules/` —
**den gibt es nicht.** Der Eintrag gehört in `data/rules.toml`.

## Warum das keine Konstanten im Code sind

Weil sie sich ändern, ohne dass der Code sich ändert. Eine Toleranz gehört ins
Materialprofil, ein Gewindemaß in die Normteiltabelle — **eine Zahl im
Baustein ist ein Fehler** (Regel 7, Checkliste Baustein Punkt 6).

## Eine Regeländerung wird gemessen

Regelsammlung angefasst? Dann:

1. Eintrag in `data/rules.toml` mit Datum und Anlass
2. Version erhöhen
3. Agenten-Suite **vorher und nachher**, beide Ergebnisse festhalten
4. Verschlechtert sich die Quote, wird die Regel zurückgenommen — nicht
   „trotzdem behalten"

Der Suite-Lauf kostet Geld und rund anderthalb Stunden je Modell
(`tools/run_agent_suite.py`). Er ist kein Testlauf.

Kalibrierung schreibt TOML-Tabellen- und Feldkennungen als zitierte Literale.
Materialkennungen mit Leerraum, Punkten oder Anführungszeichen bleiben so
beim Aktualisieren eines anderen Profils unverändert lesbar.

## Druckproben gelten für ihren Prozess

`calibration.apply(..., process=...)` speichert gemessene Mindestwand und
Überhanggrenze zusammen mit Druckerkennung, Düse, Schichthöhe und Linienbreite.
`profiles.for_process` übernimmt dafür das tatsächliche Druckraster aus den
Projekteinstellungen. `Profile` verwendet die Messwerte nur bei passendem
Prozess; andernfalls gelten zwei Linienbreiten und die Überhang-Startregel.
Ein Wechsel des Messprozesses nimmt keine Messung des anderen Felds mit.
Nicht ausgewählte Messfelder bleiben beim Speichern unverändert.

`analysis_limits` verbindet die Anforderungen der zugeordneten Materialien:
größte Mindestwand, kleinster Überhangwinkel. Unbekannte Materialarten
übernehmen keine Kalibrierung eines anderen Materials. Analyse und ihre
Zwischenspeicher müssen die wirksamen Grenzen berücksichtigen.

## Das Filamentlager ist örtlicher Bestand

`filaments.save` speichert eine Spule nach Kennung; eine leere Kennung legt
ein neues Exemplar an. Namen dürfen mehrfach vorkommen. Bearbeitungen behalten
die gelesene `revision`, damit ein offener Dialog keinen jüngeren Verbrauch
zurückschreibt. Archivieren erhält Kennung und Verlauf. Die alten Namenswege
`remember`, `synchronise` und `forget` bearbeiten nur eindeutige Treffer;
sie raten bei zwei gleichen Etiketten keine physische Spule.

Spulen, letzte Bestandsfeststellungen und Buchungen stehen gemeinsam in der
versionierten `filaments.json`. Lesen, Prüfen und atomarer Dateitausch liegen
unter einer Betriebssystemsperre. Die Migration alter Listenkataloge speichert
Lager- und Spulenkennungen im selben Vorgang; unbekannte Mengen bleiben leer.
Die Vorwahl darf einen Lesefehler mit einer leeren Liste beantworten;
`catalogue(strict=True)` meldet ihn in der Lageransicht. Jeder Schreibweg
verweigert das Überschreiben einer beschädigten oder neueren Datei.

`book` nimmt einen ganzen Vorgang an. Seine Kennung macht Zustellungen
idempotent; ein gleicher Fingerabdruck mit neuer Vorgangskennung bedeutet
einen ausdrücklich wiederholten Druck. Jede Position bewahrt ihre Herkunft
und Druckfilamentidentität. G-Code ersetzt eine Schätzung mit dokumentierter
Differenz; `reverse_booking` nimmt sämtliche Positionen und Korrekturen zurück.
Der Bestand wird ab der letzten manuellen Feststellung gerechnet. Deren
`stock_revision` schützt jüngere Kenntnis vor alten Korrekturen und Rücknahmen.
Eine bestätigte Unterdeckung bleibt unbekannt, der volle Abzug im Journal.
Nach einem Bestandskonflikt kann eine ausdrücklich bestätigte Rücknahme
`preserve_newer_counts=True` setzen: jüngere Feststellungen bleiben erhalten,
übrige Spulen erhalten ihre Gutschrift. `preserved_counts` dokumentiert im
zurückgenommenen Vorgang, welche Bestände dabei unverändert geblieben sind.
Eine manuell eingetragene Menge oder Spulenaufteilung wird ausschließlich mit
`correct_manual_allocation=True` ausdrücklich ersetzt. Die Korrektur erhält
die Druckfilamentidentitäten und die vollständigen vorherigen Positionen;
automatische G-Code-Übernahmen dürfen diesen Schalter nicht setzen.

Eine manuelle Korrektur übergibt mit `expected_booking_updated_at` den
gelesenen Vorgangsstand. Eine inzwischen neuere Aufteilung wird abgewiesen;
die wiederholte Zustellung derselben unveränderten Positionen bleibt wirkungslos.
Zusätzliche G-Code-Werkzeuge dürfen Positionen ergänzen, ohne bestehende
Druckfilamentidentitäten zu entfernen. Auch frühere Positionen, Revisionen,
Zeitangaben und Rücknahmebelege werden beim Lesen vollständig geprüft.
Ein negativer Rest innerhalb der Maschinenrundung der verrechneten Werte
gilt als null; eine tatsächliche Unterdeckung bleibt unbekannt.
