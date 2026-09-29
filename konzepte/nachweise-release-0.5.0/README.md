# Nachweise der Durchsicht 0.5.0 (23. und 24.09.2026)

Was offene Registerpunkte, Kommentare und Begründungen aus der Durchsicht 0.5.0
noch belegen. Die Durchsicht liegt vollständig nur auf der Entwicklungsmaschine
(`Releases/0.5.0/Nachweise/`, nicht versioniert); geholt mit
[RM-294](../../ROADMAP-ARCHIV.md#rm-294). **Unverändert abgelegt**, von ruff
ausgenommen wie `nachweise-release-0.5.1/`. Nicht hier liegen die Netze der
Vorschausonde (`kugel_*.stl`, `plate_holes_x*.stl`) — `probe_preview.py` und
`probe_sphere_table.py` nennen, wie sie entstanden.

Eine Sonde fährt wie in
[`nachweise-release-0.5.1`](../nachweise-release-0.5.1/README.md#eine-sonde-fahren)
beschrieben; der Baum steht in diesen Sonden als Pfad im Kopf
(`F:\3D Druck.review-050\wt-…`) und ist vorher auf einen Arbeitsbaum am Stand
des Berichts zu setzen.

## Inhalt

| Datei | Wofür | Punkt |
|---|---|---|
| [`reports/codex-ci-35952849083-unix-packages.md`](reports/codex-ci-35952849083-unix-packages.md) | CI-Lauf `35952849083`: Belege und Grenzen der Unix-Pakete | RM-234 |
| [`reports/codex-ci-notices-fix.md`](reports/codex-ci-notices-fix.md) | Lizenzbeilage nach dem VTK-Ausbau (67 Lizenztests) | RM-050 |
| [`reports/p7step.md`](reports/p7step.md) | Paket p7step: STEP-Baugruppen über XCAF | RM-188 P7.4 |
| [`reports/texte.md`](reports/texte.md) | Paket texte vom 23.09.2026 | RM-084 |
| [`reports/zeichnen-bedienung.md`](reports/zeichnen-bedienung.md) | Bedienabnahme Zeichnen, Abschnitt 7 (Paket Z1) | Begründung `regel-zeichenflaeche` |
| [`sonden/exakt/s30.out`](sonden/exakt/s30.out) | Parallele Boolesche des exakten Kerns (`s30`) und ihr Determinismus (`s31`) | `app/core/brep/kernel.py` |
| [`sonden/exakt/s30_bop_parallel.py`](sonden/exakt/s30_bop_parallel.py) | Parallele Boolesche des exakten Kerns (`s30`) und ihr Determinismus (`s31`) | `app/core/brep/kernel.py` |
| [`sonden/exakt/s31.out`](sonden/exakt/s31.out) | Parallele Boolesche des exakten Kerns (`s30`) und ihr Determinismus (`s31`) | `app/core/brep/kernel.py` |
| [`sonden/exakt/s31_bop_determinism.py`](sonden/exakt/s31_bop_determinism.py) | Parallele Boolesche des exakten Kerns (`s30`) und ihr Determinismus (`s31`) | `app/core/brep/kernel.py` |
| [`sonden/p66/sonde_ellipse_boolean.py`](sonden/p66/sonde_ellipse_boolean.py) | Schnitt einer Ebene mit einer extrudierten Ellipse | `app/core/brep/edit.py` |
| [`sonden/p66/sonde_ellipse_boolean.txt`](sonden/p66/sonde_ellipse_boolean.txt) | Schnitt einer Ebene mit einer extrudierten Ellipse | `app/core/brep/edit.py` |
| [`sonden/vorschau/out_after_models.txt`](sonden/vorschau/out_after_models.txt) | Grobe Vorschau: Kugeltabelle und Lochplatten vorher und nachher | Begründung `regel-wartezeit` |
| [`sonden/vorschau/out_after_plates.txt`](sonden/vorschau/out_after_plates.txt) | Grobe Vorschau: Kugeltabelle und Lochplatten vorher und nachher | Begründung `regel-wartezeit` |
| [`sonden/vorschau/out_before_models.txt`](sonden/vorschau/out_before_models.txt) | Grobe Vorschau: Kugeltabelle und Lochplatten vorher und nachher | Begründung `regel-wartezeit` |
| [`sonden/vorschau/out_before_plates.txt`](sonden/vorschau/out_before_plates.txt) | Grobe Vorschau: Kugeltabelle und Lochplatten vorher und nachher | Begründung `regel-wartezeit` |
| [`sonden/vorschau/out_sphere_table.txt`](sonden/vorschau/out_sphere_table.txt) | Grobe Vorschau: Kugeltabelle und Lochplatten vorher und nachher | Begründung `regel-wartezeit` |
| [`sonden/vorschau/probe_preview.py`](sonden/vorschau/probe_preview.py) | Grobe Vorschau: Kugeltabelle und Lochplatten vorher und nachher | Begründung `regel-wartezeit` |
| [`sonden/vorschau/probe_sphere_table.py`](sonden/vorschau/probe_sphere_table.py) | Grobe Vorschau: Kugeltabelle und Lochplatten vorher und nachher | Begründung `regel-wartezeit` |
