# RM-079 — Website bei 320 Punkt Breite (14.09.2026)

Drei Sonden in QtWebEngine (`QT_QPA_PLATFORM=offscreen`, Fenster 320 × 640):

| Sonde | Frage |
|---|---|
| `website_320.py` | Ist eine Seite breiter als ihr Fenster, und welches Element ragt am weitesten hinaus? |
| `website_320_wer.py` | Welche Texte laufen über ihren Kasten hinaus, welche Elemente liegen außerhalb? |
| `website_langs.py` | Wo liegt die Sprachliste bei sieben Breiten, vorher und mit einer eingespritzten Regel? |

Aufruf aus dem Projektstamm: `.venv\Scripts\python.exe .claude/.state/rm-079-website-320-2026-09-14/website_320.py website`.

## Befund vorher

`body { overflow: clip }` verhindert das waagerechte Rollen der Seite, und
verschluckt damit stumm, was nicht passt:

- Überschriften mit einem Wort breiter als der Schirm, abgeschnitten: `agb.html`
  h1 „Allgemeine Geschäftsbedingungen" 79 Punkt über dem Rahmen,
  `datenschutz.html` h1 59, `widerruf.html` h1 23, `index.html` h2
  „Systemvoraussetzungen" 23. Nur deutsch — die anderen Sprachen haben keine
  so langen Wörter.
- Die Sprachliste (`nav.lang details.langs ul`, `right: 0`) begann bei
  320 bis 479 Punkt bei −21 Punkt: Die Navigation steht dort am linken Rand,
  der Griff „DE" bei 78 bis 131, und die 9.5rem breite Liste hing an seiner
  rechten Kante.
- 21 Seiten mit `body.scrollWidth` über dem Fenster; davon 18 nur durch die
  dekorativen Pseudoelemente des Heros (`div.hero::before` 386 Punkt breit,
  `::after` 342) und `div.stage` (overflow hidden) — unsichtbar, kein Befund.

## Behebung (`website/style.css`)

- `:is(h1, h2, h3) { hyphens: auto; }` und unter 40rem `overflow-wrap: anywhere`.
- Unter 30rem: `nav.lang details.langs ul { left: 0; right: auto; }`.

## Nachher

42 Seiten gemessen: keine Überschrift läuft über ihren Kasten, die Sprachliste
liegt bei 320 Punkt zwischen 78 und 230, `documentElement.scrollWidth` gleich
`clientWidth` auf jeder Seite. Die 18 Seiten mit Hero-Pseudoelementen bleiben
in `body.scrollWidth` breiter, ohne dass etwas sichtbar hinausragt.
