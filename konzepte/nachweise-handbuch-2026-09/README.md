# Nachweise zum Handbuchumbau (RM-283)

Stand `228a05572`, 27.09.2026. Gehört zu
[`konzept-handbuch-2026-09.md`](../konzept-handbuch-2026-09.md). Zeilenangaben
altern mit dem Code; wer eine Zahl braucht, misst sie am heutigen Stand nach.

| Datei | Frage | Wie entstanden |
|---|---|---|
| [`leserblick.md`](leserblick.md) | Wie liest ein Kunde ohne CAD-Kenntnisse die dreißig geschriebenen Seiten? | Durchsicht aller Seiten aus `manual.py`, Wort- und Satzzählung per Skript |
| [`findbarkeit.md`](findbarkeit.md) | Findet die Suche, was ein Kunde sucht? Wie kommt man ins Handbuch, und wie wird es ausgeliefert? | Nachgebildete Suche des Handbuchfensters über typische Kundensuchen, Lektüre der Einstiege und Ausgabewege |
| [`aufnahmetechnik.md`](aufnahmetechnik.md) | Worauf können die Bildanleitungen bauen: Aufnahmewerkzeuge, benannte Bereiche, Dialoge, Sprachen, Einbindung ins Handbuch? | Aus dem Code gelesen, nichts ausgeführt |
| [`suche.md`](suche.md) | Findet die neue Suche die richtige Seite? Vorher und nachher an denselben 50 Kundensuchen, und warum jede Gewichtung so ist | Messung am Zweig nach `3d2af85fd`; die Suchen stehen ausführbar in `tests/test_manual_search.py` |
