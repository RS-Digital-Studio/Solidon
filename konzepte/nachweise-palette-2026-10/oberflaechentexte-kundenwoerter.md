# Bericht oberflaechentexte: Kundenwörter Boolesch und Hinweissatz (11.10.2026)

Gemessen mit echten Palettenzeilen aus einem MainWindow offscreen (Operationen
und Fensterbefehle) und den Gruppentiteln des Panels, Wörter im Speicher
eingesetzt, Stand von rank(): genau gesagtes Kundenwort (Rang 1) vor Titelwort
am Wortanfang (Rang 2).

## Kundenwörter

| Operation | de | en | es | fr | it | pt |
|---|---|---|---|---|---|---|
| union_objects | zusammensetzen; boolesch; Boolesche Operation; Boolean; kombinieren; union | join; join together; merge; combine; boolean; Boolean operation; union | unir; juntar; combinar; fusionar; booleano; operación booleana; unión | fusionner; unir; assembler; combiner; booléen; opération booléenne; union | unire; fondere; combinare; unificare; booleano; operazione booleana; unione | juntar; unir; combinar; fundir; booleano; operação booleana; união |
| subtract_objects | herausschneiden; Form ausschneiden; boolesch; Boolesche Operation; Boolean; kombinieren; subtrahieren; Differenz; difference | cut out; subtract; carve out; remove shape; boolean; Boolean operation; combine; difference | restar; sustraer; recortar forma; vaciar forma; booleano; operación booleana; combinar; diferencia | découper; soustraire; retirer la forme; booléen; opération booléenne; combiner; différence; soustraction | sottrarre; ritagliare; scavare; booleano; operazione booleana; combinare; differenza; sottrazione | subtrair; recortar forma; escavar; booleano; operação booleana; combinar; diferença; subtração |
| intersect_objects | boolesch; Boolesche Operation; Boolean; kombinieren | boolean; Boolean operation; combine; common | booleano; operación booleana; combinar; común | booléen; opération booléenne; combiner; commun | booleano; operazione booleana; combinare; comune; interseca | booleano; operação booleana; combinar; comum |

Zusätze gegenüber der Vorgabe: „difference“ in der deutschen Quelle von
Abziehen (in Roberts Liste der gescheiterten Wörter; ohne ihn zeigt die deutsche
Oberfläche zuerst die Differenzansicht), „union“ in der deutschen Quelle von
Vereinigen (OpenSCAD-Wort; vorher gleichauf mit blend_union, in it/pt stand
„Fondi dolcemente“/„Fundir suavemente“ vorn).

Bewusst weggelassen: „parte común/partie commune/…“ (schiebt „parte“/„partie“
auf Schnittmenge), „Überschneidung“ (trifft Überschneidungen prüfen), die
Fusion-Wörter cut/couper/taglia/recortar/cortar (treffen sechs bis zwölf
Schnittoperationen), fr „joindre“ (trifft Joindre au corps).

## Kollisionen

1. Differenz/difference gegen Einstellungen: Differenzansicht (Katalog 2989) —
   unter dem jetzigen rank() steht Abziehen überall auf Platz 1.
2. en „combine“ gegen Combine into a pattern (group_pattern): die drei Rang 1,
   das Muster Rang 2.
3. es „unión“ gegen Unión de canal, Unión de encaje: Unir Rang 1.
4. „Boolesche Operation“ enthält „Operation“: die bloße Suche „Operation“ zeigt
   die drei zuerst (Rang 4) vor Parameter anlegen, Handbuch (Rang 7) —
   hingenommen.
5. Gruppentitel im Panel: en „combine“ trifft „Combine and subtract“, fr
   „combiner“ „Combiner et soustraire“ — ganze Gruppe; galt schon vorher für
   subtract/restar/unir/…
6. Kein Konflikt: boolesch, booleano/booléen, kombinieren, subtrahieren,
   soustraction, sottrazione, subtração, unione, união, interseca;
   common/común/… stehen sonst nur in Beschreibungen.
7. Bestand: es/pt „unir“ gegen Unir al cuerpo/Unir ao corpo, it „unisci“
   gleichauf mit Unisci al corpo, en „join“ gegen Join to body.

Wirkung: alle Fachwörter in sechs Sprachen zeigen genau die drei auf Rang 1;
Differenz/difference/diferencia/… zeigen Abziehen zuerst. Handbuchquote bei
HEAD, Zwischenstand und Vorschlag gleich: Auftrag 37/38 (31 oben), alle 49/50
(40 oben), einziger Fehltreffer „Stütze“ (Rang 6) schon an HEAD.

## Hinweissatz (Vorbild „Für eine Passung ein Gegenstück mit {key} und Klick im Objektbaum hinzuwählen.“)

- de: Für „Vereinigen“, „Abziehen“ und „Schnittmenge“ ein zweites Objekt mit Umschalt oder {key} und Klick hinzuwählen.
- en: For “Unite”, “Subtract” and “Intersection”, Shift-click or {key}-click to add a second object.
- es: Para «Unir», «Sustraer» e «Intersección», añadir un segundo objeto con Mayús o {key} y clic.
- fr: Pour « Réunir », « Soustraire » et « Intersection », ajoutez un second objet avec Maj ou {key} et un clic.
- it: Per «Unisci», «Sottrai» e «Intersezione», aggiungi un secondo oggetto con Maiusc o {key} e clic.
- pt: Para «Unir», «Subtrair» e «Interseção», adicionar um segundo objeto com Shift ou {key} e um clique.

„Objekt“ statt „Körper“, weil Zusammenfassung („1 Objekt gewählt“) und
Sperrgrund („braucht zwei Objekte“) es so sagen.
