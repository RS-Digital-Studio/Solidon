---
name: live-durchsicht-solidon3d-2026-08
description: Zwei Live-Durchsichten von Formwerk im August 2026 — Bedienung (04.08.) und Vergleich gegen Fusion und ElegooSlicer (05.08.); Befunde in konzept-bedienung.md und .claude/konzept-live-durchsicht-2026-08.md.
metadata: 
  node_type: memory
  type: project
  originSessionId: 04b5a4bb-f8b4-48b1-8e60-384aa7e64159
  modified: 2026-08-05T14:20:53.461Z
---

Am **4. August 2026** wurde Formwerk vollständig von Hand durchgespielt (Maus
und Tastatur): Erstinbetriebnahme, alle Menüs, Viewport, alle sieben
Beispielprojekte mit Touren, Handbuch, Skizzeneditor, Druckvorbereitung,
Export, beide Themen. Ergebnis: **`konzept-bedienung.md`** im
Projektwurzelverzeichnis.

Am **5. August 2026** folgte der Vergleich gegen die installierten Programme —
**Autodesk Fusion 2704.1.36** und **ElegooSlicer 1.5.3.4**. Ergebnis:
**`.claude/konzept-live-durchsicht-2026-08.md`**, fünfzehn gemessene Funde,
Zusammenfassung am Ende der `ROADMAP.md`.

**Die vier Funde, aus denen die Arbeit folgt:**

1. `Solid.bounds` kommt aus der Tessellation — konstant 0,025 mm zu klein
   (halbe `DEFLECTION`), bei Ø 6 wie bei Ø 120. Fusion misst denselben Körper
   exakt. Daran hängen Maßanzeige, Anordnung, Haftungsrand und jede Passung.
2. Formwerks Plattenanordnung erreicht den Slicer nicht: er ordnet selbst an,
   egal in welchen Koordinaten das 3MF kommt. Mit `--arrange 0` **und**
   Bettkoordinaten stimmt es auf ein Zehntel.
3. Bei `drill` und den sieben Bausteinen darauf ist die angeklickte Fläche die
   **Mitte** des Werkzeugs — Sacklöcher werden halb so tief, „bohrt durch"
   bohrt nicht durch, und eine Magnettasche auf der Oberfläche trägt gar nichts
   ab, ohne etwas zu melden.
4. Der Viewport nimmt weiter keine Klicks entgegen; die Ursache ist diesmal
   belegt: gepickt wird mit `vtkPointPicker`, und der trifft nur Eckpunkte.
   Rad und Rechtsziehen bewegen die Kamera, die Maus kommt also an.

**Was besser trägt als das Repository es darstellt:** STEP stimmt in beide
Richtungen auf fünfzehn Stellen mit Fusion überein; die Slicer-Übergabe meldet
gegen die neuere Slicer-Fassung null übergangene Einstellungen.

**Wie gemessen wurde** (wiederverwendbar): Slicer über `handover.slice_model`
mit dem echten Programm, Positionen aus dem G-Code über die
`; printing object`-Marken und die Extrusionen dazwischen. Fusion über ein
Add-In unter `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`, das beim
Start läuft, misst und eine JSON schreibt — nach der Messung wieder entfernt;
Fusion startet über `FusionLauncher.exe`, und ein abgestürztes Add-In wird beim
nächsten Start übersprungen (dann über Shift+S neu einschalten). Die Oberfläche
über synthetische Eingaben auf Fensterebene (`SetCursorPos` + `mouse_event`);
VTK braucht eine Zeigerbewegung **vor** dem Klick, sonst kommt er nicht an.

Siehe auch [[zeichnen-an-fusion-orientieren]].
