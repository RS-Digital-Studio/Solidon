# Anschreiben international — Demo-Start Solidon3D

Englische Fassung der Mail, die am 20.08.2026 an 3Druck.com ging. Für
All3DP, Fabbaloo, 3D Printing Industry, 3DPrint.com, VoxelMatters,
Hackaday und die englischsprachigen Kanäle.

**Regieanweisung, nicht zum Mitschicken.** Alles unterhalb der
Trennlinie geht hinaus, dieser Block nicht.

* **Der Link zeigt auf `/en/`**, nicht auf die deutsche Startseite.
* **Die Angabe zu den Paketen prüfen.** Der Text unten sagt Windows,
  macOS und Linux. Solange nur der Windows-Installer steht, ist der Satz
  falsch — dann die Zeile in Klammern nehmen, die nur Windows nennt.
* **Hackaday will einen anderen Text.** Dort zieht nicht die
  Produktvorstellung, sondern der technische Kern: Passung über ein
  gedrucktes Prüfstück kalibrieren, non-destruktiver Op-Stack, das
  Sprachmodell darf keine Geometrie rechnen. Zwei Absätze, kein
  Faktenblock.
* **Anhänge:** höchstens drei Bilder unter je 1 MB, alles Weitere
  verlinken.

---

## Subject

Solidon3D: free demo of a desktop app that makes downloaded STL files fit

## The mail

Dear Editors,

Over the past months I have developed a desktop application for 3D
printing: Solidon3D. It closes the gap between "model downloaded" and
"part fits" — without having to learn a CAD program first.

Four routes lead to a finished part:

* **Adapt** — import someone else's model, repair defects
  automatically, place a hole, widen a cutout
* **Construct** — rebuild from named dimensions and tested building
  blocks: nut traps, heat-set inserts, threads, hinges, cable grommets
* **Generate** — create a model from text or an image and run it
  through the repair chain
* **Sculpt** — model organic shapes freely

Nothing about this is final: every step stays in the history as an
operation and can be changed at any time. Change one dimension and the
model recomputes — even twenty steps later. On top of that: layer
analysis with overhangs, islands and support requirements, tolerances
taken from material profiles, and export to STL, 3MF and STEP.

The AI sits on top and is optional: you can describe what you want in
the chat instead of clicking through menus. On request it runs entirely
locally on your own graphics card — that needs additional software, but
no data goes to the cloud. Without AI, without an account and without an
internet connection, everything else remains fully usable. Geometry is
always computed by code, never by the language model.

You can take a look here: https://solidon3d.de/en/

The current release is a complete demo (available since 20 August) meant
to shake out bugs — free, no account, usable until the end of October.
Windows, macOS and Linux; around 255 MB download.

[Ersatzzeile, solange nur Windows steht: Windows 10/11, 173 MB
download; macOS and Linux packages are following.]

Kind regards,
Robert Schneider

## Kurzfassung für eine Meldung

Solidon3D is a desktop application that sits between a downloaded model
and a part that actually fits. It repairs defective meshes, adapts them
through a non-destructive stack of operations — change a dimension and
everything recomputes — and checks printability before slicing:
overhangs, islands, support volume. Tolerances come from material
profiles the user calibrates once with a printed test piece. An optional
chat lets you describe changes in plain language; it can only trigger
the same operations the menus offer, and it never computes geometry
itself. Runs offline, no account required. The demo is free and complete
through 30 October 2026.

## Faktenblock

* Desktop application, Windows / macOS / Linux
* Free demo through 30 October 2026, no account, no watermark, no
  export lock
* Import: STL, OBJ, 3MF (as an assembly), STEP
* Export: STL, 3MF, STEP, plus handover to an installed slicer
* Optional AI, local or hosted; the application is fully usable without
  it
* Website: https://solidon3d.de/en/
* Contact: support@solidon3d.de
