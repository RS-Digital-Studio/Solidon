# RM-285: Modelltext-Restliste, Stand 02.10.2026

43 feste Doppelpunkte in 42 Ausdrücken aus sieben Dateien stehen nach einem
Übersetzungsaufruf. Diese Liste wurde am aktuellen Quellstand erneut mit dem tatsächlichen
AST-Wächter `_fixed_translated_colons` aus `tests/test_translations.py` erhoben und die
Nachbarschaft des Übersetzungsaufrufs geprüft. Sie ist die Arbeitsgrundlage für einen
später beauftragten Modelltextnachgang; diese Quellen bleiben unverändert.

Der breite AST-Wächter meldet zusätzlich `analysis._orientation` an Zeile 268:
`object_id:` steht dort vor dem übersetzten Text. Das ist eine technische Objektkennung,
kein Doppelpunkt hinter einem übersetzten Teil, und gehört nicht zu den 43 Texttrennern.
Auch `backend:model`, `obj_1:hole_2`, `auto:` und Pfadprüfungen werden nicht pauschal
umgeschrieben. Weitere feste Trenner vor dynamisch übersetzten Werten, etwa
`checks.as_lines` und `find_part_text`, benötigen bei einem Nachgang ebenfalls Prüfung.

## Fundstellen

Alle Pfade sind relativ zum Repository. Die Zeilenzahlen gelten für die darunter
gehashten Dateien; `session._unknown_objects` enthält zwei betroffene Trenner.

| Datei | Zeile | Funktion | Texttrenner |
|---|---:|---|---:|
| `app/core/agent/analysis.py` | 114 | `analysis_text` | 1 |
| `app/core/agent/analysis.py` | 155 | `_printability` | 1 |
| `app/core/agent/apply.py` | 326 | `_title` | 1 |
| `app/core/agent/context.py` | 168 | `world_text` | 1 |
| `app/core/agent/context.py` | 179 | `report_text` | 1 |
| `app/core/agent/offer.py` | 125 | `for_request` | 1 |
| `app/core/agent/tools.py` | 406 | `operation_tools` | 1 |
| `app/core/agent/tools.py` | 515 | `operation_tools` | 1 |
| `app/core/agent/session.py` | 336 | `_unknown_objects` | 2 |
| `app/core/agent/session.py` | 605 | `_run` | 1 |
| `app/core/agent/session.py` | 697 | `_ask_user` | 1 |
| `app/core/agent/session.py` | 723 | `_undo` | 1 |
| `app/core/agent/session.py` | 727 | `_undo` | 1 |
| `app/core/agent/session.py` | 748 | `_undo` | 1 |
| `app/core/agent/session.py` | 756 | `_undo` | 1 |
| `app/core/agent/session.py` | 768 | `_parameter` | 1 |
| `app/core/agent/session.py` | 791 | `_parameter` | 1 |
| `app/core/agent/session.py` | 802 | `_analysis` | 1 |
| `app/core/agent/session.py` | 842 | `_print_target` | 1 |
| `app/core/agent/session.py` | 857 | `_standard` | 1 |
| `app/core/agent/session.py` | 869 | `_fit` | 1 |
| `app/core/agent/session.py` | 886 | `_operation` | 1 |
| `app/core/agent/session.py` | 896 | `_operation` | 1 |
| `app/core/agent/session.py` | 927 | `_operation` | 1 |
| `app/core/agent/session.py` | 945 | `_operation` | 1 |
| `app/core/agent/session.py` | 964 | `_operation` | 1 |
| `app/core/agent/session.py` | 973 | `_operation` | 1 |
| `app/core/agent/session.py` | 1099 | `parse_number` | 1 |
| `app/core/agent/session.py` | 1101 | `parse_number` | 1 |
| `app/core/agent/session.py` | 1137 | `build_fit` | 1 |
| `app/core/agent/session.py` | 1176 | `standard_text` | 1 |
| `app/core/agent/session.py` | 1178 | `standard_text` | 1 |
| `app/core/perceive/digest.py` | 150 | `digest` | 1 |
| `app/core/perceive/digest.py` | 154 | `digest` | 1 |
| `app/core/perceive/digest.py` | 289 | `_fit_lines` | 1 |
| `app/core/perceive/digest.py` | 308 | `_print_settings_line` | 1 |
| `app/core/perceive/digest.py` | 328 | `_source_lines` | 1 |
| `app/core/perceive/digest.py` | 351 | `_scene_line` | 1 |
| `app/core/perceive/digest.py` | 541 | `_extent_line` | 1 |
| `app/core/perceive/digest.py` | 1028 | `_stack_lines` | 1 |
| `app/core/perceive/digest.py` | 1098 | `new_feature_lines` | 1 |
| `app/core/perceive/digest.py` | 1101 | `new_feature_lines` | 1 |

## Wirkung und verbindliche Abnahme

- `analysis_text` und `_printability` liefern Antworten von `read_analysis`.
- `apply._title` wird als `transaction.title` gespeichert: `_title` → `accept`/
  `history.apply` → `transaction.title` → `digest._stack_lines` →
  `context.build_messages` im folgenden Modellzug. Auch dieser Grenzfall erreicht das Modell.
- `world_text` und `report_text` bauen Modellkontext; `ToolOffer.for_request` beschreibt
  ein lokales Werkzeugangebot; `operation_tools` liefert Werkzeugbeschreibungen auch über MCP.
- `session` liefert Werkzeugantworten und `digest` Kontext/Antworten zu Parametern,
  Auswahl, Passungen, Druckeinstellungen, Quellen, Szene, Lage, Verlauf und neuen Merkmalen.

`app/core/agent/CLAUDE.md` verlangt bei Systemprompt, Regelsammlung oder
Werkzeugbeschreibung die 39 Referenzanfragen vorher und nachher. Beschreibungen in
`operation_tools` und `ToolOffer.for_request` sind ausdrücklich erfasst; es gibt
keine Interpunktionsausnahme. `.claude/rules/agentenschicht.md` verlangt bei jeder
Textänderung die Anpassung der `PROMPT_VERSION`; am erhobenen Stand ist ihr Wert 8.
Die eng formulierte Suitevorgabe nennt dynamischen Kontext und Werkzeugantworten
nicht zusätzlich ausdrücklich. Daraus ist keine geprüfte Ausnahme ableitbar.

Die Modellsuite läuft laut Agentkarte auf Ansage und kostet Geld. Die Karte schließt
Ollama für diese Abnahme ausdrücklich aus. Eine neue kostenpflichtige Modellabnahme
ist nicht durchgeführt; reine Textprüfungen ersetzen sie nicht. Das ist die aktuelle
Abnahmegrenze, keine Behauptung über das Verhalten eines künftig geänderten Prompts.
Die noch beauftragbare Arbeit wird ausschließlich als offener RM-285 in `ROADMAP.md` geführt.

## Quellenfingerabdrücke (SHA-256)

| Datei | SHA-256 |
|---|---|
| `app/core/agent/analysis.py` | `97b35f4f6fd26090974608b3d4807afb2e297777219bbc3dfb3de22c0e11b006` |
| `app/core/agent/apply.py` | `4bd504d18724e54124841606a665615a8b51a666f86e2156d2abde9dbacfebfa` |
| `app/core/agent/context.py` | `effd0424873378669b456794f536b0eabcf116c331792bb6dfabe2641c9c7c39` |
| `app/core/agent/offer.py` | `b39b001fa1be320a971636b1b57ab2d4f8c7046cd32c85d530e30811e6024329` |
| `app/core/agent/tools.py` | `ad7b45ca821df0b209c67f6d5a6ddada4545d7e46100cca03d49a322b5654397` |
| `app/core/agent/session.py` | `d6daf90054e3e072a6c3d7c31a6fef4321c56749267e79e2e39a2aae9935b68c` |
| `app/core/perceive/digest.py` | `b9ef67b60875588666edcb4828a0fa8f0d713c77b65920d4cfc3d02b565755b4` |
