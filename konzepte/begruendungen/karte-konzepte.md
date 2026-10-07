# Begründungen zu `konzepte/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie ihre Datumsangabe abgab.
> Die Karte steht dort; hier steht der Beleg der Regel „Die Statustabellen
> altern“ in seiner früheren Fassung — wörtlich. *Früher unter …* nennt die
> Stelle der alten Karte.

## Die Statustabellen altern

*Früher unter „Die Statustabellen altern“.*

Die Konzepte tragen eigene Statusspalten, und die stimmen nicht dauerhaft: Von
zwölf Punkten, die sie am 22.08.2026 als offen führten, waren **sieben längst
behoben**.

## Wenn ein Konzept erledigt oder abgelöst ist

*Früher unter „Wenn ein Konzept umgesetzt ist“; der Umzug nach `archiv/` ist neu.*

Bis zum 06.10.2026 blieb jedes Konzept an seinem Ort. Der Index begründete
das mit den stabilen Dateinamen („es wandert nicht und heißt nicht anders“)
und lehnte Unterordner ab, weil ein Umzug die Verweise aus Code, Roadmap und
Archiv bräche. Die Durchsicht vor der Demo 0.3.0 zählte am 02.09.2026 daneben
21 abgearbeitete Dokumente mit 13 066 Zeilen im selben flachen Ordner wie die
geltenden; wer dort suchte, musste jedem die Statuszeile glauben oder sie am
Code nachprüfen (RM-099).

Robert hat am 06.10.2026 entschieden: „umräumen — erledigte und abgelöste
Konzepte in einen Unterordner, alle Verweise nachziehen, den Index aktuell
halten.“ Beim ersten Umzug gingen 30 Dokumente nach `archiv/`; 27 blieben,
weil ein offener Registerpunkt, eine Regel, eine Karte, der Bauplan oder eine
noch geltende Entscheidung auf sie zeigt, oder im Zweifel. Die beiden
Bedienkonzepte unter `.claude/` werden noch fortgeschrieben und blieben dort. Der alte Grund gegen Unterordner
gilt weiter für Themenordner: Der Umzug ins Archiv ist einmalig je Dokument,
der Name bleibt, und jeder Verweis wird im selben Commit nachgezogen.
