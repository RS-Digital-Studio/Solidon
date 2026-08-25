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

Verwandt: [[uebersetzung-neu-statt-flicken]] — bei Genuswechsel
(pieza→bloque) reicht kein Wörtertausch, die Angleichung läuft durch den
ganzen Satz (Artikel, Partizipien, Pronomen: „la suya" → „el suyo").
