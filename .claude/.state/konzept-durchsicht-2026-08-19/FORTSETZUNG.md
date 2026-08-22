# Konzeptdurchsicht 19.08.2026 — abgeschlossen

Auftrag: alle Konzepte ansehen, online nachrecherchieren, auf einen aktuellen
und vollständigen Stand bringen. **Erledigt und committet** (`8bb2454`,
19 Dateien, +2352/−112).

## Ergebnis

| Stufe | Stand |
|---|---|
| Sondierung | 18/18 — 300 externe, 265 interne Behauptungen |
| Online-Recherche | 13 Themenfelder, 469 belegte Faktenkarten |
| Interner Code-Abgleich | 18/18 — 102 stimmen, 168 überholt, 26 falsch, 15 unprüfbar |
| Redaktion | 18/18 |
| ROADMAP | Abschnitt „Die Konzepte nachrecherchiert (19.08.2026)", 8 offene Punkte, Register nachgezogen |

Geprüft: `ruff check` und `ruff format --check` grün (428 Dateien), `mypy` grün
(209 Dateien), `tests/test_roadmap.py` grün (5), dazu 656 dokumentnahe Tests
(Sprache, Handbuch, Übersetzungen, Website). **Die vollständige `pytest`-Suite
wurde nicht gefahren**: Im Arbeitsbaum liegen 31 Dateien einer parallelen
Sitzung (`app/ui/`, `app/core/`, Sprachkataloge, Tests), und sie gehören nicht
zu dieser Durchsicht. Nebenbei belegt die Recherche, warum ein Lauf am Stück
ohnehin nichts mehr sagt: 22 Minuten, dann ein nativer Abriss bei über 3 GB.

## Was hier liegt

- `befunde/` — je Datei die prüfbaren Behauptungen (Sondierung)
- `abgleich/` — je Datei das Urteil gegen den Code, mit Belegen
- `faktenkarten/` — je Datei die zugeschnittenen Rechercheergebnisse
- `cluster.json` — alle 13 Themenfelder mit 469 Faktenkarten, roh
- `KORREKTUR-claude-code.md` — warum der Claude-Code-Cluster in drei Punkten
  falsch war: er schloss von „nicht dokumentiert" auf „existiert nicht"
- `HALBFERTIG.md` — historisch, betraf die einmal unterbrochene Redaktion
- `*-roh.json`, `*-teilergebnisse.json`, `workflow-skripte/` — Rohdaten

## Was offen blieb, und warum

Acht Funde außerhalb der Konzeptdateien stehen als offene Punkte in der
ROADMAP — zwei davon in `CLAUDE.md`, das jede Sitzung liest.

An neunzehn Stellen wurde ausdrücklich **nichts** eingetragen: Messwerte, die
einen bestimmten Aufbau brauchen (Qt-Fahrgerüst im Vollbild, ComfyUI, Ollama,
Browsermessungen), Zahlen, die ein Anbieter nicht herausgibt (SindriCADs
Downloadzahlen, Patreon-Stände, Alibre- und nTop-Preise), und die Frage, ob ein
erzeugtes 3D-Modell unter die Kennzeichnungspflicht des AI Act fällt. Diese
Lücken sind das Ergebnis, nicht sein Fehlen.
