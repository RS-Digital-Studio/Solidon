# Auftrag: „Stift für Bohrung“ baut das passende Gegenstück

Kundenwunsch (Fragebogen S-20261006-5be329, Solidon 0.5.3): „Stift aus Bohrung erzeugen, wäre noch gut,
wenn man ein Gewinde bei der Bohrung oder Senkung hat, dass man dafür auch das passende Gegenstück mit der
Funktion erzeugen könnte.“

Heute (`app/core/geom/lid_hinge.py`, `pin_for_bore`): ein glatter Zylinder, Ø = Bohrung − Spiel aus dem
Materialprofil, so lang wie die Bohrung (`span`/`depth`), Merkmal `BORE_PIN_FEATURE`. Eine Senkung, eine
Ansenkung (Stufenbohrung) oder ein Innengewinde an derselben Bohrung bleiben unbeachtet.

Soll:
- Trägt die Bohrung eine **Senkung** (Kegel an der Mündung, Kette über
  `perceive.relations.cavity_chain_state_at`), bekommt der Stift dort einen **Senkkopf**, der bündig in der
  Senkung sitzt: Kegelstumpf mit dem Winkel der Senkung, Außendurchmesser = Senkung − Spiel.
- Trägt sie eine **Ansenkung** (Stufe: größere Bohrung an der Mündung, ebenfalls Kette), bekommt er einen
  **Zylinderkopf** in deren Maß − Spiel.
- Trägt sie ein **Innengewinde** (Merkmal `thread`, `internal`, auf derselben Achse), wird der Schaft im
  Gewindebereich ein **Außengewinde** derselben Größe und Steigung mit Spiel aus dem Profil — derselbe
  Weg wie `counterpart.thread_counterpart_draft` / `thread_values_for` und der Gewindebaustein in
  `knowledge/parts/fasteners.py` (Tabellenmaß, sonst `CUSTOM_SIZE` mit Durchmesser und Steigung; Absagen
  für links-/mehrgängig/kegelig wie dort). Senkung + Gewinde = Senkkopfschraube.
- Neuer Parameter hinter der Klappe: Form „passend zur Bohrung“ (Vorgabe) oder „glatter Stift“.
  Bestehende Projekte behalten ihr Ergebnis: Formatversion erhöhen, Migration setzt bei vorhandenen
  `pin_for_bore`-Schritten „glatter Stift“ (Checkliste „Dateiformat ändern“ in AGENTS.md, Beispieldatei der
  alten Version, Test). Ein Befund nennt, was gebaut wurde („Senkkopf 90°, M6 × 1“), Regel 17 für Absagen.
- Beide Kerne (Netz und exakt, `shapes.building`), Zusage `leaves_inputs_unchanged=True` bleibt:
  `outputs[0]` ist der unveränderte Träger. `cache_version` erhöhen.
- Tests gegen den Korpus (`tests/data/meshes/plate_countersunk.stl`, `plate_countersunk_blind.stl`, eine
  Bohrung mit gedrucktem Innengewinde aus `insert_printed_thread`), Sollwerte mit Herkunft; Gegenprobe;
  Texte in allen Katalogen.
