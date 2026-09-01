# Bausteinbereich ist ein Produktionsvertrag

Ein Bereichstest erfüllt Bauplan §24.3 nur, wenn er das vollständige
kartesische Produkt aller numerischen Min-/Max-Grenzen, Enum-Werte und
Bool-Stellungen fährt. Die Vorgabe ist keine Grenze; sie gehört in den
Reproduzierbarkeitstest.

Wandstärke und bedingte Merkmale sind Eigenschaften des registrierten
Bausteins. Sie gehören als explizite Metadaten an `PartSpec` und in jeden
Anwendungsweg des Bereichstests. Tabellen nach Bausteinname im Test oder
Sonderfälle im Prüfkern sind kein Produktionsvertrag. Eine nicht anwendbare
Wandprüfung nennt einen fachlichen Grund und gegebenenfalls die genaue
Parameterstellung, in der nur ein abtragender Werkzeugkörper entsteht.

Lokale Wandstärke wird an allen Flächen gegen die erste gegenläufige
Austrittsfläche gemessen. Selbstdurchdringung wird vollständig im nativen
Geometriekern geprüft: Eine rekursive disjunkte Flächenpartition ordnet jedes
Dreieckspaar genau einem Kreuzsatz zu. AABB-Ausschlüsse dürfen nur geometrisch
unmögliche Kreuzsätze entfernen; Stichproben und stilles Pruning sind nicht
zulässig.

Der Lauf meldet monotonen Fortschritt über Bau, Wand, Durchdringung und
Merkmale. Zwischen Kombinationen und in jeder langen Geometriephase bleibt er
abbrechbar. Ein Fehler nennt die vollständige Parameterkombination und bei
Maßfehlern Messwert und Grenze.
