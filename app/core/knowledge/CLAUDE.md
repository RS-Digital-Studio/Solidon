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
| `filaments.py` | Benannte Filamente mit Farbe, als Vorwahl (§20) |
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
