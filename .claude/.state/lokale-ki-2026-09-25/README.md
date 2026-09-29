# Lokale KI — Messungen der Agenten-Suite (25.–26.09.2026)

Werkzeuge und Rohdaten zu RM-251 (Schrittgrenze und Werkzeugangebot des
lokalen Modells) und RM-016 (gehosteter Vorgabeweg). Stand und Deutung stehen
bei den Punkten in `ROADMAP.md`; hier liegt nur, womit gemessen wurde.

| Datei | Wofür |
|---|---|
| `suite_timed.py` | Agenten-Suite mit Zeit- und Tokenzahlen je Fall gegen einen wählbaren Baum; hält die Belegung der Grafikkarte vor jedem Fall fest |
| `suite_kette.sh` | Mehrere Suiteläufe nacheinander, jeder erst auf freier Karte |
| `fit_probe.sh` | Je Modell Grundlast zählen, mit Fenster laden, Lage lesen, entladen |
| `offer_probe.py`, `rank_probe.py` | Werkzeugangebot und Rangfolge für eine Anfrage ohne Modelllauf |
| `summarize.py`, `rescore.py` | Gespeicherte Läufe zusammenfassen und mit der Bewertung vom 26.09.2026 nachrechnen (Wo-Fälle „Handlungen“, Zwilling = dieselbe Handlung) |
| `catalogs.py` | Katalogeinträge der lokalen KI in allen fünf Sprachen setzen (einmalig) |
| `messung/` | Rohdaten der Läufe je Modell (`suite_*.json`), Werkzeugproben und Zählungen |

**Aufruf:** aus der Wurzel des Repositorys mit
`.venv\Scripts\python.exe .claude\.state\lokale-ki-2026-09-25\suite_timed.py <baum> <modell> <ausgabe.json>`.
Die Suite kostet mit einem lokalen Modell kein Geld, belegt aber die
Grafikkarte; die Shell-Skripte nennen einen Scratchpad-Pfad der Sitzung vom
25.09.2026 und müssen vor einem neuen Lauf angepasst werden. Ein gehosteter
Lauf kostet Geld und läuft nur mit Roberts Freigabe.
