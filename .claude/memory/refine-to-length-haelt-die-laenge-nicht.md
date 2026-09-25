---
name: refine-to-length-haelt-die-laenge-nicht
description: manifold3d refine_to_length teilt die Kanten des Eingangs, nicht die, die es im Dreieck neu zieht — nach einem Durchgang bis zum 3,9-Fachen; face_id trägt die Herkunft.
metadata:
  type: reference
---

`Manifold.refine_to_length(e)` teilt jede **vorhandene** Kante in
`ceil(l / e)` Stücke. Im Inneren eines geteilten Dreiecks zieht es neue
Kanten, und die können länger sein: gemessen am 25.09.2026 an elf Modellen
aus `F:\3D Dateien` bei 1 mm längste Kante 1,76 bis 3,96 mm nach einem
Durchgang, an Quadern die Zellendiagonale bis zum 1,8-Fachen. Ein zweiter
und dritter Durchgang bringen es auf ≤ e (je 1–3 s bei einer Million
Dreiecken); `mesh_ops._split_conforming` wiederholt deshalb bis zur Zusage.

Zwei weitere Eigenschaften, die man sonst nachmessen muss:

- **`face_id` reist durch.** Gibt man `Mesh64(..., face_id=np.arange(F))`
  mit, trägt jedes Ausgabedreieck die Nummer des Eingangsdreiecks, aus dem es
  stammt (geprüft: jedes liegt in der Ebene seines Ursprungs). Ohne eigene
  Nummern vergibt der Kern je **koplanarer Gruppe** eine — zwei Filamente auf
  einer ebenen Fläche wären dann eines.
- **Die Dreieckszahl schätzt die Fläche allein nicht.** Ein Durchgang ergibt
  `Fläche/(√3/4·e²) + 2·Σ ceil(l/e) − 2F` (je Dreieck `T = 2I + R − 2`);
  die Fläche allein lag an Nadelnetzen um das Sechzehnfache zu tief
  (Besenhalter: 58 931 gegen 966 870).

**How to apply:** Wer „jede Kante höchstens e" braucht, nimmt
`mesh_ops.remesh`, nicht `refined` (ein Durchgang, fürs Biegen genug). Wer
Attribute durch den Kern tragen will, gibt `face_id` mit, statt hinterher
über `attributes.transfer` die nächste Oberfläche zu suchen. Verwandt:
[[index-messen-und-pruefen]].
