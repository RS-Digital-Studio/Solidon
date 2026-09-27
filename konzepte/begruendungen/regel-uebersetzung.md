# Begründungen zu `.claude/rules/uebersetzung.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

## Glossare je Sprache — verbindlich

Die Genusregel ist bei der Verdichtung aus den Erinnerungen dazugekommen.
Entschieden wurde das Wort je Sprache am 25.08.2026 (Kataloge in `e1e4bde3`,
Website und Handbuch in `024108cb`): Der Begriff „Baustein“ war in vier Sprachen
gespalten — Menü und Katalog sagten `bloque`/`bloc`/`blocco`/`bloco`, die
neueren Texte des Rezeptgebiets `pieza`/`brique`/`componente`/`peça`; der
Bestandsbegriff gewann, weil er Menüeinträge, Handbuch und Website verankert.
Am 30.08.2026 an einem einzigen Satz gemessen, zogen mit:

| | vorher | nachher |
|---|---|---|
| es | Esta pieza … la rechazaría | **Este** bloque … **lo** rechazaría |
| fr | Cette pièce … partagée telle quelle … la refuserait | **Ce** bloc … **partagé tel quel** … **le** refuserait |
| pt | Esta peça … partilhada … recusá-la-ia | **Este** bloco … **partilhado** … **recusá-lo-ia** |

Am selben Tag entstanden fünf Sätze in fünf Sprachen, ohne dass jemand die
Notiz zum Genus aufschlug — sie stand als letzte Zeile unter „Verwandt“. Eine
Warnung am Ende eines Dokuments wirkt wie eine Fußnote; deshalb steht die
Genusregel in der Regel **vor** den Glossaren.

## Übersetzen heißt neu schreiben, nicht flicken

Robert, 23.08.2026, als ein ergänzter Handbuchabsatz an fünf alte
Übersetzungen angehängt werden sollte: „neu übersetzen wenn es sauberer ist
merken.“ Bei „Wenn etwas nicht geht“ waren es elf Absätze in beiden Sprachen und
ein guter Ton — dort war Anhängen richtig, und der neue Absatz wurde frisch
übersetzt. Eine schlechte Übersetzung fortzuschreiben verlängert ihren Fehler.

Die Regel zu mehrsprachigen Bildschirmvideos kam ebenfalls aus den Erinnerungen:
Seitenrahmen und Navigation kommen aus dem Katalog, aber die App übersetzt keine
Benutzereingaben — ein englischer Film braucht englische Maßnamen und passende
`@`-Verweise.

## Neue Schlüssel nachtragen

Die vier Kataloge `es`, `fr`, `it` und `pt` sind am 13.08.2026 in einem Zug
entstanden: acht Hintergrund-Agenten, je zwei pro Sprache, gegen eine
eingefrorene Basis, weil der lebende Katalog mitten im Lauf um fünfzehn
Schlüssel wuchs und jede Indexangabe darüber verschob. Wer so etwas noch
einmal braucht — eine siebte Sprache am Stück —, findet Werkzeuge und
Ablaufbeschreibung in der Historie unter `.claude/i18n-wip/`, bis
Commit `93f0989`. Für alles Kleinere ist der Ordner nicht nötig, und deshalb
liegt er nicht mehr im Baum.
