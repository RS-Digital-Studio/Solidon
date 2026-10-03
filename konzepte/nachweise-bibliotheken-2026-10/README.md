# Nachweise zum Bibliothekslauf vom 02./03.10.2026 (RM-467, RM-471)

| Datei | Belegt |
|---|---|
| [schriftvergleich.md](schriftvergleich.md) | RM-471: jeder Schriftzug alt (matplotlib) gegen neu (HarfBuzz) — Fläche, Hausdorff, Punkte; dazu die Volumen der exakten Schriftkörper |
| [schrift-exakt.md](schrift-exakt.md) | RM-471: beide Wege gegen die exakte Glyphenfläche aus der Schriftdatei |

Ergebnis: Der neue Weg liegt bei jeder Schrifthöhe höchstens 0,07 % neben der
exakten Fläche, der alte bei 10 mm bis 1,46 % und bei 3 mm bis 2,41 % darunter.
Die Ränder weichen bis 0,27 mm voneinander ab; das ist der Sehnenfehler von
`to_polygons`, nicht der neue Weg. Dafür trägt der neue Weg rund doppelt so
viele Punkte, weil auch die Sehnen fast gerader Kurvenstrecken kurz bleiben
(`glyphs.chord_for`) — sonst las die Merkmalserkennung sie als Ebene. Die Lage der Glyphen unterscheidet sich am
Ende einer 50-mm-Zeile um bis 0,04 mm, weil matplotlib jede Glyphenbreite auf
1/64 Pixel rundete. Die exakten Schriftkörper ändern ihr Volumen um höchstens
0,044 %. Die DejaVu-Dateien sind bitgleich zur Veröffentlichung 2.35.
