# Liste an „Koordination 0.6.0 Übergabe“ — Stand welle4 vor dem Schnitt 09:00

Sitzung „Welle4 Einstellungen nach Modell“, abgeschlossen 11.10.2026 07:20. **Von mir kommt
nichts mehr nach welle4.**

## Gelandet auf welle4 (für 0.6.0)

| Punkt | Merge | Inhalt |
|---|---|---|
| RM-586 | `2c7fa2b91` | Feine Schichten an flachen Kuppen und Schrägen, Höhenkurve je Teil, Turmsperre auch Prusa |
| RM-706 | `1e4dec783` | Verbrauchsabdruck aus den gespeicherten Eingängen, RM-705 als Vorabdruck |
| RM-584-Nachtrag | `3d782213e` | Cura fragt Kontakt mit der Stützart der Platte; Feld fasst gleiche Werte zusammen |
| Baumleser-Fix | `c0a554949` | welle4 an test_toolchain/test_finding_ways wieder grün |
| RM-588 | `bc8595595` | Naht hinten, Bügeln als Wahl, **Projektformat 52**, Beispiele neu |
| Tunnel-Fix | `a99f848c0` | Gitterstütze nicht mehr in gesperrten Kanalmündungen (`snug`), Behebung seit v0.5.1 |
| RM-629 | `b3505824d` | Schräger Schacht Schicht für Schicht, Bauplan §9 `SliceResult.overhang_angle` (Ansage) |
| M1 Stufe 1 | `86a8fb3fa` | 0.5.3-Buchungen nach E: Rückfrage statt stillem Doppelabzug; G1 |
| M1 Stufe 2 | `81b6ac793` | Rückfrage nur für 0.5-Buchungen („si1-“ ab RM-706), 0.6-Variante bucht selbst |
| Register | `c86a04eb8` | RM-700, 702, 703, 708–720 im Register |
| RM-585 | `8992d0810` | Bögen und gefasste Kragarme ohne Stütze (Eiffelturm 216 m → 0 m); RM-721 im Register |
| Integrationsreview T2 | `8e13b452e` | 0.5-Rückfrage nur bis zur ersten 0.6-Buchung mit denselben Filamenten; RM-701 im Register; Bügel-Tabelle eine Quelle |

Dazu für die andere Sitzung: CI-Fix `fix/export-einmal-lesen` (main), Nachprüfung F Teil 1 und 2.

## Bleibt auf dem Zweig (0.6.1)

Nichts.

## Neue Punkte (im Register von welle4)

RM-700, RM-702, RM-703, RM-708 bis RM-721 — Titel und Abnahme stehen im Register. Zwei davon
sind Probedrucke für Robert: RM-703 (Cura Baum gegen normale Stütze unter flachem Hut) und
RM-717 (flache Decken, die nach RM-585 ohne Stütze bleiben).

Weitergegeben an die andere Sitzung (ihr Gebiet, inzwischen auf welle4 behoben): *Weich
verschmelzen* dreht einen geschlossenen Hohlraum nach außen; F T2-1 (Band-Vorzeichen).

## Abbau nach main

Worktrees und Zweige: `F:/sl-schichten`, `F:/sl-rm706`, `F:/sl-stil2`, `F:/sl-w4fix`, `F:/sl-naht`,
`F:/sl-tunnel`, `F:/sl-schacht`, `F:/sl-altbuchung`, `F:/sl-boegen`, `F:/sl-akten`, Zweig
`fix/altbuchung-stufe1`, dazu die alten aus KOORDINATION.md „Nächste Schritte“ Punkt 4 — je vorher
`git merge-base --is-ancestor <zweig> origin/main`. Scratch-Ordner `b00d64ab…` und `78c2d72e…`
nach `F:\claude-scratch-archiv\F--3D-Druck\` verschieben; `F:\tmp-agenten\*` meiner Kürzel,
`F:\rv585n2-scratch`, `F:\sl-naht-mess` aufräumen. Prüfberichte der Nacht nach dem Release mit
einem Aktenzweig versionieren (unversionierte Kopien im Hauptbaum vorher entfernen).
