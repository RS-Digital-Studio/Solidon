---
name: sonde-ueber-alle-operationen
description: "Alle 110 Operationen durch das echte Fenster fahren: Umgebung wie conftest, ein Prozess je Kategorie (nach ~60 Fenstern reißt es nativ), Modal-Wächter, Zeilen sofort schreiben — so kam am 13.09.2026 heraus, dass 28 Dialoge ein lügendes Band trugen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1ca7314c-d749-4b85-aac6-9da0d8f5da54
  modified: 2026-09-13T20:58:17.563Z
---

Am 13.09.2026 hieß der Auftrag „bei vielen Operationen fehlt die Vorschau".
Gemessen wurde nicht am Register, sondern am **Fenster**: `MainWindow(Session(),
UiSettings())`, je Op eine passende Szene (`cube_clean.stl`, `plate_holes.stl`
für Bohrungsmerkmale, `create_brep_box` für den exakten Kern), Auswahl über
`object_tree.select_object/select_feature`, dann `window.run_operation(spec)`
wie das Menü, `wait_for_idle`, und abgelesen: `_op_dialog`,
`viewport.difference`, `viewport.banner.note.text()`.

Vier Dinge, ohne die die Sonde nichts liefert:

- **Umgebung wie `tests/conftest.py`**: `QT_QPA_PLATFORM=offscreen` und
  APPDATA/LOCALAPPDATA/HOME/XDG_* in einen Temp-Ordner — sonst trifft sie
  Roberts echte Profile.
- **Ein Prozess je Kategorie.** Ein Prozess über alle 110 riss nach rund
  sechzig Fenstern mit Segfault (Exit 139) — dieselbe Grenze wie in der
  Suite. `PROBE_CATEGORY=<kategorie>` und eine Schleife in der Shell.
- **Modal-Wächter.** Ein `QMessageBox.information` („Die Szene ist leer",
  „braucht n Objekte") wartet offscreen ewig; ein `QTimer` alle 200 ms, der
  `QApplication.activeModalWidget()` schließt und den Titel vermerkt, hält
  den Lauf am Leben — 3 s CPU in fünf Minuten war das Zeichen des Hängers.
- **Jede Zeile sofort schreiben** (`print(..., flush=True)`), nicht am Ende
  drucken: Der erste Lauf verlor 60 Ergebnisse im Abriss.

Ergebnis damals: 62 Dialoge mit Bild, 17 mit leerer Differenz, 11 ohne — und
über allen dreien stand „Vorschau — noch nicht übernommen". Der Befund war
kein fehlendes Bild, sondern ein Band, das drei Lagen gleich nannte.

**Why:** Die Vorschau-Mechanik ist eine Stelle (`_wire_preview`), und wer sie
liest, sieht „jeder Dialog bekommt eine". Was der Kunde sieht, entscheidet
sich in der Rechnung dahinter — und die kennt man nur, wenn man sie für jede
Op einmal fährt.

**How to apply:** Bei „bei vielen X fehlt Y" nicht die eine Stelle lesen,
sondern alle X durch den Kundenweg fahren und den Zustand je X in eine Tabelle
schreiben. Die Sonde stand im Scratchpad (`probe_previews.py`); sie ist kein
Test, sondern eine Messung — siehe [[sondenbau]] für die pytest-Bauart und
[[zweite-sitzung-im-selben-baum]], bevor man Prozesse beendet.
