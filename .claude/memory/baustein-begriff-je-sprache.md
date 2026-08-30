---
name: baustein-begriff-je-sprache
description: Baustein heißt je Sprache genau ein Wort — es bloque, fr bloc, it blocco, pt bloco; pieza/peça bleiben für „Teil".
metadata:
  type: project
---

# Baustein heißt je Sprache genau ein Wort

Entschieden und umgesetzt am 25.08.2026 (Kataloge in e1e4bde3, Website und
Handbuch in 024108cb), unter Roberts Vollmacht „alles am besten für den
Kunden".

**Der Befund:** Der Begriff „Baustein" war in vier Sprachen gespalten. Menü
und Katalog sagten seit je `bloque`/`bloc`/`blocco`/`bloco`; die neueren
Texte des Rezeptgebiets sagten `pieza`/`brique`/`componente`/`peça`. Der
Kunde las „Catálogo de bloques" im Menü und „Guardar la selección como
pieza" darin — und im französischen Handbuch standen „catalogue de briques"
und „Catalogue de blocs" im selben Absatz.

**Die Entscheidung:** Der Bestandsbegriff gewinnt — er verankert die
Menüeinträge, das Handbuch und die Website. Also: es **bloque**, fr
**bloc**, it **blocco**, pt **bloco**.

**Ein Genuswechsel zieht durch den ganzen Satz, und das ist keine Fußnote.**
`bloque`, `bloc` und `bloco` sind **maskulin**, `pieza`, `pièce` und `peça`
**feminin**. Wer nur das Substantiv tauscht, hinterlässt einen Satz, der in
sich nicht mehr stimmt — und das ist schlechter als der ursprüngliche Fehler,
weil es aussieht wie eine geprüfte Übersetzung. Am 30.08.2026 an einem
einzigen Börsensatz gemessen, mitgezogen sind:

| | vorher | nachher |
|---|---|---|
| es | Esta pieza … la rechazaría | **Este** bloque … **lo** rechazaría |
| fr | Cette pièce … partagée telle quelle … la refuserait | **Ce** bloc … **partagé tel quel** … **le** refuserait |
| pt | Esta peça … partilhada … recusá-la-ia | **Este** bloco … **partilhado** … **recusá-lo-ia** |

Im Italienischen fiel nichts an, weil `componente` und `blocco` beide
maskulin sind — genau der Fall, der zu dem Fehlschluss verführt, ein
Wörtertausch genüge.

**Die Grenze, und sie trägt:** Ersetzt wurde nur, wo die deutsche Quelle
„Baustein" sagt. `pieza`/`peça` sind zugleich die richtigen Wörter für
„Teil" (das Werkstück), `componenti normalizzati` für Normteile,
`pièce` für „dasselbe Teil" — die bleiben. Wer hier pauschal ersetzt,
macht Sätze wie „si levanta la pieza, la descuelga" falsch. b0 hat die
Regel an seinen Bausteintexten gegengeprüft: Sie greift beim Baustein und
lässt das Teil in Ruhe.

**Wie man es prüft:** Je Sprache über die Schlüssel, die „Baustein"
enthalten — dort darf der Minderheitsbegriff nicht mehr vorkommen. Die
Website zitiert Dialogtitel wörtlich; ändert sich ein Katalogtext, ziehen
`website/{es,fr,it,pt}/index.html` und `features.html` nach, die
Handbücher erzeugt `tools/make_manual.py` ohnehin aus den Katalogen.

**Und wo diese Notiz gelesen werden muss, ist beim Schreiben — nicht danach.**
Am 30.08.2026 hat eine Sitzung fünf Sätze in fünf Sprachen verfasst, ohne die
eine Datei aufzuschlagen, die genau diese Frage beantwortet; gefunden wurde es
erst in der Durchsicht. Der Genus-Absatz oben stand dabei schon hier — als
letzte Zeile unter „Verwandt", und dort liest ihn niemand als Anweisung. Er
ist deshalb nach oben gewandert. **Eine Warnung am Ende eines Dokuments wirkt
wie eine Fußnote, gleich was sie sagt**; wer eine schreibt, stellt sie vor die
Arbeit, die sie verhindern soll.

Verwandt: [[uebersetzung-neu-statt-flicken]] (dieselbe Angleichung, allgemein
gefasst: Artikel, Partizipien, Pronomen — „la suya" → „el suyo") und
[[katalog-schluessel-sind-woerter]], denn beide Fallen sitzen im selben Satz:
die eine im Substantiv, die andere im Schlüssel.
