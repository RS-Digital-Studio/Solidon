# Fremder Code — nicht bearbeiten

Die ComfyUI-Knoten für TripoSG. Sie sind **nicht Teil der Anwendung**,
sie werden in eine fremde ComfyUI-Installation kopiert
(`app/core/backends/comfy_setup.py`).

| Datei | Rolle |
|---|---|
| `nodes.py` | Die Knoten (`TripoSGLoader`, `TripoSGImageToMesh`, `TripoSGPostprocess`, `TripoSGExportMesh`) |
| `__init__.py` | Meldet sie ComfyUI an (`NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS`) |

## Warum das hier liegt und nicht in `tools/`

Weil `tools/` im gebauten Paket nicht mitreist. Der Nutzer soll ComfyUI aus
der laufenden Anwendung heraus einrichten können — also muss der Inhalt im
Kern liegen.

## Regeln für dieses Verzeichnis

- **Nicht umformatieren, nicht umbenennen, nicht „aufräumen".** Was hier
  steht, muss gegen die fremde Gegenstelle passen, nicht gegen unseren Stil.
- **Die Sprachregel gilt hier nicht.** Englische Kommentare bleiben englisch.
- Ändert sich hier etwas, ist der Grund eine Änderung an ComfyUI oder TripoSG
  — nicht eine an Solidon.
- **Lizenzhinweise bleiben, wo sie sind.** TripoSG nennt im Wurzel-`LICENSE`
  MIT, Teile des Quelltexts stehen unter Tencent-Lizenzen ohne EU (RM-003).
