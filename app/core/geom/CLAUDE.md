# `app/core/geom/` — wo Geometrie entsteht

Die einzige Stelle, an der Geometrie entsteht oder sich ändert (Regel 2).
Gerechnet wird gegen `manifold3d` und `trimesh`.

Die Regeln stehen in `.claude/rules/operationen.md`.

## Die Boolesche Rückfallkette (§17.2)

Sie ist das Muster, das dieses Gebiet prägt — kein Sonderfall, sondern der
Normalweg:

| Stufe | Was sie tut | Vermerk |
|---|---|---|
| 1 | direkt durch den Kern | `direct` |
| 2 | verschweißen, aufräumen, erneut | `welded` |
| 3 | die Eingangsgeometrie minimal stören | `jittered` |
| 4 | auf Voxeln rechnen, neu vernetzen | `voxel` |
| 5 | aufgeben — mit Befund und Weg nach vorn | — |

**Die Stufe, die es geschafft hat, wird in die Operation geschrieben.** So
rechnet dieselbe Datei gleich nach (§11.3), und der Bericht kann sagen, was
die Zahlen wert sind. Stufe 4 kostet Genauigkeit und läuft **nie
stillschweigend**. In Entwurfsqualität endet die Kette nach Stufe 2, damit das
Iterieren schnell bleibt (§31).

`tests/test_boolean.py` erzwingt jede Stufe einzeln.

## Die Karte

**Grundlage**

`mesh.py` (die Mesh-Hülle um den Geometriekern, §9) · `boolean.py` (die Kette
oben) · `repair.py` (Netze reparieren) · `attributes.py` (Materialslots durch
eine Operation hindurch behalten, §20) · `enclosure.py` (Konturverschachtelung
ohne `rtree`)

**Bewegen und Ausrichten**

`transform.py` · `ops.py` (Kategorie „Transformation") · `align.py` (Merkmale
in Flucht bringen)

**Körper erzeugen und formen**

`primitive_ops.py` · `blend.py` (weiches Verschmelzen) · `displace.py`
(Höhenfeld) · `lattice.py` (Gitterfüllung) · `texture_ops.py`
(Oberflächentexturen als echte Geometrie) · `sculpt.py` · `pose.py`
(Skelett und Stellung) · `sketch_solid.py` (einen Skizzenumriss zu einem Netz
aufziehen)

`sketch_solid.py` ist das Gegenstück zu `brep/profiles.extrude` für den Fall,
dass kein exakter Körper vorliegt — und dieser Fall ist der häufigste: Wer ein
heruntergeladenes STL öffnet, hat ein Netz. Bis zum 30.08.2026 endete das
Abtragen dort an einem Satz („besteht bereits aus festen Dreiecken"); seitdem
schneidet `sketch_pocket` über die Boolesche Kette auch in ein Netz. Was dabei
entsteht, ist wieder ein Netz — der Unterschied bleibt, die Absage nicht.

`sculpt.py` und `pose.py` sind **Sammelparameter-Ops**: viele Gesten, ein
Schritt. Das Ergebnis folgt vollständig aus den Parametern, was das Fenster
währenddessen zeigt, ist Vorschau. `tests/test_gesture_ops.py` prüft das über
das ganze Register.

**Wandungen**

`hollow.py` (Aushöhlen — mit den Entlüftungen, die es druckbar machen) ·
`lid.py` (ein Deckel für eine Öffnung)

**Druckvorbereitung**

`prepare.py` und `prepare_ops.py` (Bohrungen, Teilen, Anordnen, Kollisionen,
§18.6) · `autosplit.py` (schneiden, bis es auf die Platte passt; nach einer
billigen Naht-Vorauswahl entscheidet das interne Stützvolumen der fertig
verstifteten Hälften, §22.3) ·
`pins.py` (Passstifte; Auto Split wählt die Form aus Fügefläche und
Materialtiefe und hält den Kleberhinweis als Operationsparameter fest; die
beiden Verbinder-Bausteine werden vor einer Hintergrundsuche als
unveränderlicher `ConnectorGeometrySnapshot` erfasst, nie während der
Nahtbewertung aus dem globalen Register gelesen) ·
`orient.py`

**Messen und Schneiden**

`measure.py` (§18.3) · `section.py` (Ebene durch einen Körper, §18.2) ·
`difference.py` (was eine Änderung hinzugefügt und was sie entfernt hat)

**Netz, Farbe, Text**

`mesh_ops.py` (Arbeit am Netz selbst) · `colour_ops.py` · `paint.py` (Flächen
in ein Filament färben) · `texture.py` (von einer Textur zu druckbaren Slots)
· `label_ops.py` (Text und Logos auf einer Fläche)

## Was eine Operation hier einhalten muss

1. Registereintrag in `registry/` — ohne ihn gibt es sie nicht
2. Umsetzung als `OpFn`; Boolesches über die Kette, benutzte Stufe in `solver`
3. Bei Zufall: Startwert aus `ctx.seed`, `deterministic=False`
4. **Beide Qualitätsstufen bedienen** (`ctx.quality`)
5. Befunde als `findings` zurückgeben, nicht selbst protokollieren
6. Geometrietest gegen den Korpus in `tests/data/`
7. Texte übersetzbar, alle fünf Kataloge ziehen nach

## Grenzen

- **Millimeter, doppelte Genauigkeit.** Vergleich über `units.is_close()`,
  nie mit `==`.
- **Keine Zahlenkonstante für Toleranzen** — `auto:<material>` verweist ins
  Materialprofil (Regel 7).
- **Nie eine Eingabe verändern.** `OpResult.outputs` sind neue Objekte.
- **Verrundungen auf Mesh-Kanten vor dem B-Rep-Kern** werden ausdrücklich
  nicht gebaut. Dafür ist `brep/` da.
