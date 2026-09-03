---
name: erzeugtes-laeuft-nicht-in-der-ci
description: "Tests, die gegen eine eingecheckte erzeugte Datei vergleichen, tragen den Marker rendered und laufen nicht in der CI — neue kommen nicht ohne Eintrag dazu (Robert, 03.09.2026)."
metadata:
  node_type: memory
  type: feedback
---

Zwölf Tests vergleichen den Code gegen eine **eingecheckte, erzeugte** Datei:
die Handbuchseiten der Website (`website/handbuch.html`,
`website/<sprache>/manual.html`), die Referenz darin, die Abbildungsstempel aus
`tools/stamp_assets.py`. Sie tragen seit dem 03.09.2026 den Marker `rendered`,
und die CI wählt ihn ab (`-m "not performance and not rendered"`, vier Aufrufe
in `.github/workflows/build.yml`).

**Why:** Sie werden rot, sobald eine Operation dazukommt oder die Version
steigt — und was sie dann verlangen, ist kein Codefehler, sondern ein Lauf von
`tools/make_manual.py` und `tools/stamp_assets.py`. Am 03.09.2026 kostete das
achtzehn rote Läufe und zwei Erzeugerläufe für vier neue Operationen, die mit
dem Handbuch nichts zu tun hatten. `AGENTS.md` sagt ohnehin „Bilder und
Handbuch nur beim Release"; die Tests haben das nicht eingehalten. Ein Wächter,
der bei jeder Änderung schreit, warnt vor nichts mehr.

**How to apply:** Ein neuer Test, dessen Grün an einem Erzeugerlauf hängt,
bekommt `@pytest.mark.rendered` **und** einen Eintrag in `RENDERED_TESTS` in
`tests/test_toolchain.py`. `test_no_generated_comparison_runs_in_the_ci` hält
beide Hälften: Es meldet einen Marker ohne Eintrag, einen Eintrag ohne Marker
und jede Markerwahl in `build.yml`, die `rendered` nicht abwählt.

Die Liste ist **kuratiert und nicht erkannt** — aus demselben Grund wie
`GERMAN_STEMS` (siehe [[waechter-zaehlt-das-falsche]]). Ein Muster über den
Quelltext trennt „liest die erzeugte Seite" nicht von „benutzt den Stempler zum
Vergleichen": Gemessen hätte es
`test_the_page_loads_nothing_from_outside` mitmarkiert und damit eine
**Sicherheitsprüfung** aus der CI genommen. Und der Wächter sucht `-m "not `
statt `python -m pytest`, weil der Suitelauf in einer Shell-Funktion steckt,
die ihre Argumente nur weiterreicht, und weil zitierte Aufrufe in Kommentaren
sonst als echte gelten ([[waechter-lesen-kommentare-mit]]).

**Lokal laufen sie weiter**, und dort sind sie richtig: Wer vor einem Release
`/pruefen` fährt, soll erfahren, dass die Seiten hinterherhängen. `-m rendered`
fährt sie allein.
