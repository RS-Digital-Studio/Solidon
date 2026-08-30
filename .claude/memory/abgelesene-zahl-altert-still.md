---
name: abgelesene-zahl-altert-still
description: "Eine einmal aus der Geometrie abgelesene und fest eingetragene Zahl stimmt nur in der Lage, in der sie entstand — und ihr Versagen sieht aus wie eine Gestaltungsentscheidung."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cc0c50ad-6ea5-4d75-b0d4-2e514a473ea3
  modified: 2026-08-30T21:45:37.850Z
---

Am 30.08.2026 trug das Galerie-Rezept der Schraubdose
`wrap_diameter: 65.3, width: 205.1` — einmal bei ⌀60 aus der fertigen
Geometrie abgelesen. Als der Durchmesser auf 75 ging, wickelte die Rändelung
weiter um den Zylinder von gestern: Der Deckel bestand aus **553
Komponenten**, die Rändelung lag als Hunderte loser Stücke daneben.

**Why:** Wasserdicht, plausibles Volumen, keine Befunde, und auf dem Bild ein
glatter Deckel. Das ist der teure Teil: **Was fehlte, sah aus wie eine
Gestaltungsentscheidung.** Ich habe das Bild angesehen und nichts bemerkt —
ein Deckel ohne Rändelung ist ein plausibler Deckel. Ein zerbrochener wäre
aufgefallen, ein unvollständiger nicht.

Derselbe Abend brachte zwei Geschwister, und erst zu dritt sind sie ein
Muster: der Lochwandhaken (Vorgabe *Achse = Z*, die nur auf einer waagerechten
Fläche stimmt) und die Klappbox (`insert_living_hinge` auf getippten
Koordinaten, Deckel senkrecht durch den Kasten). **Jedes Mal eine feste Zahl
oder eine Vorgabe, die nur in der Lage stimmte, in der sie entstand.**

**Und die Reparatur hatte denselben Fehler in besserer Tarnung.** Drei
Stunden später zerfiel derselbe Deckel in 542 Stücke — die Formel
`=@durchmesser + 2 * @wand + 0.5` sah hergeleitet aus, und die 0,5 waren
zweimal `clearance` aus dem **Materialprofil**: 0,25 bei PETG, 0,20 bei PLA.
Gemessen hatte ich mit PETG, der Wächter fährt den Standard.

Eine Zahl aus dem Profil ist schlimmer als eine aus der Geometrie, weil sie
wie Bauart aussieht. Der Ausweg war, sie ganz wegzulassen: Die Rändelung
wickelt jetzt eine Winzigkeit **zu eng**, und das ist die sichere Richtung —
bei `mode="raised"` verschmilzt ein Muster im Material, ein Muster daneben
fällt ab. **Wo eine Toleranz nicht in die Formel gehört, gehört sie auf die
Seite, die verzeiht.**

**How to apply:**

* **Eine Zahl, die aus einer Messung stammt, gehört als Formel zurück** —
  `=@durchmesser + 2 * @wand` statt `65.3`. Der Auswerter kann Klammern,
  Multiplikation und Parameterbezüge; das ist geprüft.
* **Die Formel aus der Bauart holen, nicht aus einer Kurvenanpassung** — und
  **nichts hineinnehmen, was aus dem Profil kommt.** Eine angepasste Kurve
  stimmt an den Messpunkten und sonst nach Glück; eine Profilzahl stimmt für
  ein Material.
* **Über beide Materialien messen, nicht nur über den Parameterbereich.**
  `make_profile()` ohne Argumente gibt PLA, gearbeitet wird oft mit PETG —
  und ein Teil, das nur unter einem Material hält, ist genauso unsichtbar wie
  eines, das nur bei einem Durchmesser hält.
* **Über den Parameterbereich messen, nicht an einem Punkt.** 50, 60, 75, 90,
  120 kosten einen Lauf und trennen „stimmt" von „stimmt hier".
* **Die Teilezahl ist der billigste Wächter.** `component_count` verrät einen
  zerfallenen Körper sofort, wo Volumen und Wasserdichtheit schweigen —
  `_hanging_loose` fährt genau das für Bausteine, den Texturen fehlt es.
* Und wer einen fremden Baustein über ein fertiges Rezept misst, **misst das
  Rezept mit**: 3as „stille Untergrenze bei 66,8" war meine Rändelung, nicht
  `screw_lid`.

Verwandt: [[zwei-schwellen-eine-frage]] (ein Wert, der nur im Normalfall
stimmt), [[sollwert-aus-dem-pruefling]] (die Zahl stammt aus dem, was sie
prüfen soll) und [[was-die-suite-nicht-findet]] — auch hier fand es kein Test,
sondern ein Blick auf das fertige Bild.
