---
name: zeichnen-an-fusion-orientieren
description: Der Skizzeneditor von Formwerk soll sich an Autodesk Fusion orientieren; Fusion ist lokal installiert und darf zum Vergleich gestartet werden.
metadata: 
  node_type: memory
  type: project
  originSessionId: 04b5a4bb-f8b4-48b1-8e60-384aa7e64159
  modified: 2026-08-04T07:53:52.330Z
---

Robert will den Skizzeneditor an **Autodesk Fusion** ausrichten — Kürzel,
Werkzeugumfang und Orientierungshilfen. Fusion 360 ist auf diesem Rechner
installiert (`%LOCALAPPDATA%\Autodesk\webdeploy\production\...\Fusion360.exe`)
und darf für einen direkten Vergleich gestartet werden.

**Warum:** Die Zielnutzer kommen aus Fusion. Der Commit „Wer aus Fusion kommt,
hat E und F in den Fingern" (0ee7132) hat dafür bereits eine zweite
Tastenbelegung eingeführt — sie deckt aber nur Modellieren ab, nicht das
Zeichnen.

**Wie anwenden:** Bei Arbeiten an `app/ui/sketch_editor.py` und
`app/ui/shortcut_schemes.py` gegen Fusion prüfen: Zeichenkürzel L/R/C/A/D/T/O/X
kontextabhängig im Skizzenmodus (in Fusion sind R und C *Rechteck* und *Kreis*,
nicht Drehen und Fasen), Ursprung mit Achsen und Maßstab, die Ändern-Gruppe
(Trimmen, Verlängern, Versetzen, Spiegeln), Projizieren und
Konstruktionsgeometrie, Maßeingabe beim Zeichnen. Einzelheiten in
`konzept-bedienung.md`, Teil 4. Siehe auch [[live-durchsicht-formwerk-2026-08]].
