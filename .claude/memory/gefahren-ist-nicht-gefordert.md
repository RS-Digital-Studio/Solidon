---
name: gefahren-ist-nicht-gefordert
description: "Wer eine Testauflage nach dem Dateinamen erfüllt, erfüllt sie vielleicht nicht — die Tests zu einem Thema findet man über ihre Zusicherung, nicht über den Dateinamen."
metadata:
  type: feedback
---

**Eine Auflage nennt ein Thema, kein Dateiname.** Am 28.08.2026 lautete die
Freigabebedingung: „`test_manual` und die **Agenten-Werkzeugbeschreibungs-Tests**
gehören in deinen Torlauf." Ich fuhr `tests/test_agent.py` und meldete
„Bedingung erfüllt, 1813 grün". Der Test hieß
`tests/test_agent_suite.py::test_tool_descriptions_carry_the_menu_place` und war
rot — er hielt vier Menüwege als Zeichenketten fest, und zwei davon hatte ich
gekürzt.

Die Zusage in meiner Meldung war also falsch, und sie war **plausibel falsch**:
`test_agent.py` ist der naheliegende Name, er existiert, er lief grün, und
1813 grüne Tests lesen sich wie Sorgfalt.

**Why:** Ein Dateiname ist eine Vermutung über den Inhalt. Bei zwei Dateien mit
gemeinsamem Wortstamm (`test_agent.py` / `test_agent_suite.py`,
`test_registry.py` / `test_registry_consistency.py`) ist die Vermutung
fifty-fifty, und niemand merkt es, weil der gefahrene Lauf grün ist. Verwandt
mit [[gemessene-frage-ist-nicht-die-gestellte]], aber eigenständig: Dort
antwortet eine Suche auf ihre eigene Frage; hier antwortet ein **richtiger**
Lauf auf eine andere Auflage.

Dazu kam der zweite Teil, und der ist der teurere: Der Test war **schon auf
HEAD rot**, seit meinem eigenen Commit zwei Stände vorher — ich hatte ihn
gebrochen und rot nach origin gepusht, weil ich ihn beim ersten Mal genauso
nicht gefahren hatte. Ein Lauf, der eine Datei nicht anfasst, kann sie nicht
retten, und zwei Torläufe hintereinander mit derselben Lücke sind eine Lücke
und nicht zwei Belege ([[vier-torlaeufe-ein-stand]]).

**How to apply:** Nennt eine Auflage ein *Thema*, wird über die **Zusicherung**
gesucht, nicht über den Dateinamen — `grep -rn "operation_tools\|menu_path" tests/`
findet jeden, der die Sache prüft, in einer Sekunde. Bei mehreren Dateien mit
gemeinsamem Stamm gehören **alle** in den Lauf; sie sind billiger als die
Rückfrage.

Und wenn ein Torlauf mit ausgewählten Dateien gefahren wird, gehört die Liste
in die Meldung — nicht „Bedingung erfüllt", sondern die Namen. Beim ersten Mal
hätte ein Blick auf die eigene Liste die Lücke gezeigt; ich habe sie geschrieben
und nicht gelesen ([[beleg-stand-im-eigenen-kontext]]).
