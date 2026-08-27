# Fremder Code — nicht bearbeiten

Die ComfyUI-Knoten für TripoSG (MIT). Sie sind **nicht Teil der Anwendung**,
sie werden in eine fremde ComfyUI-Installation kopiert
(`app/core/backends/comfy_setup.py`).

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
- **MIT-Lizenz beachten:** Der Lizenzhinweis bleibt, wo er ist.
