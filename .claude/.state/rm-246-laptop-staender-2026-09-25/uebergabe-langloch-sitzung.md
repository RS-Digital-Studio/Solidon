# Stand beim Anhalten (25.09.2026, abends)

Alles committet und gepusht, kein eigener offener Stand, keine Worktrees mehr:
- a199d43b7 RM-220 (Kippen kappt an alten Randebenen, starres Versetzen am exakten Kern,
  Nachmessen am Netz, mouth_covered, Kantenprüfung am ersten Durchstoß, Absage ab halbem
  Öffnungswinkel, Senkung ohne Bohrung) — RM-220 im Archiv.
- 7bf78e19f Nachbarwand beim Versetzen/Verdoppeln, over_the_edge fällt neben neighbour_opened.
- c133f96b0 gekrümmte Mündung: Fächerdeckel im Stopfen (curved_rims, CURVED_RIM), Versetzen
  einer Kette ohne Flächenkörper über _cavity_plug + _chain_copy_tool.
- 0c86d6266 spitze Senkung (ein Randring) wird gekappt.
- 94cd80d90 Quaderkappung (_boxed_in) wo der ebene Schnitt scheitert, Prüfsäule im
  Innenkreis (_inscribed_radius), zugedeckt = ≥ Hälfte der Proben (COVERED_SHARE);
  Erinnerung pruefsonde-liegt-im-vieleck.
- 5fd0d0a7c RM-245 im Register (Robert: ja, eigener Punkt).

## Weiter mit

**RM-245** — Bohrung mit Erweiterung an beiden Enden (Pegboard-STEPs: Zylindersenkung
Ø 10 hinten, Ø 6 auf 1 mm, Fase Ø 7 vorn; `cavity_chain_state_at` → ambiguous_cavity_chain →
NO_OWN_BODY bei Kippen, Versetzen, Verdoppeln). Eintrag in ROADMAP.md mit Weg und Abnahme.
Erst lesen: relations.cavity_chain_state_at / cavity_chains, prepare_ops.bore_entrance,
_BoreEntrance, _chain_tool, _cavity_plug, _old_rim_caps, _exact_chain_*.
Probe dafür: rm220/probe_peg.py <datei> (PROBE_TREE=<baum>), rm220/probe_real.py.

## Übergeben / bewusst so
- Laptop-Ständer (offen nach Reparatur, Voxelstufe +31 %): andere Sitzung
  („Dreieckserkennung und Reparatur überprüfen") hat es übernommen, eigener Registerpunkt
  (vermutlich RM-246).
- Verdoppeln in die Vorlage: exakter Kern zusätzlich feature_lost (erkennt neu), Netz nicht.
- Rinne/gekrümmte Mündung: Rest 1–4 mm³ Durchhang des Fächerdeckels (kein LAPACK-Hub, RM-187).
- Bohrerhalter −4,7 mm³ = parts_united (RM-221); Teppichclip „nicht sicher einzeln" (P1.5);
  Besenhalter-Klemme +Volumen beim Versetzen = offen, geometrisch richtig.

## Werkzeug
- scratchpad/commit_merge.sh <erwarteter HEAD> <baum> <meldung>: eigener Index,
  eigene Dateien im Hauptbaum dreiseitig nachgeführt (fremde Arbeit bleibt),
  Override-Verzeichnis scratchpad/merge-override/<pfad mit _> für vorab aufgelöste Dateien.
- Tor im Worktree: SUITE_PYTHON="F:/3D Druck/.venv/Scripts/python.exe" bash
  .claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh > datei; Exit lesen.
