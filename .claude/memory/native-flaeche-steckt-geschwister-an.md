---
name: native-flaeche-steckt-geschwister-an
description: "Die native wgpu-Fläche machte über Qt 140 von 854 Widgets zu Windows-Fenstern (Vorfahren samt Geschwistern, Umzug steckt das neue Elternteil an); AA_DontCreateNativeWidgetSiblings und nur die Überlagerungen nativ; ein Widget entsteht in seinem endgültigen Elternteil"
metadata:
  node_type: memory
  type: project
  originSessionId: 726f8b37-9708-4940-a4ba-a97ab4a2dcda
  modified: 2026-09-25T15:59:44.850Z
---

Am 25.09.2026 (RM-232) war der größte Posten eines Bohrungsklicks am echten
Fenster nicht Rechnung, sondern Windows-Fenster: Ohne
`AA_DontCreateNativeWidgetSiblings` macht Qt jede Ebene über einem nativen
Widget nativ **samt allen Geschwistern**, und `setParent` eines nativen
Widgets zwingt das neue Elternteil, jedes spätere Kind nativ zu bauen. Das
Merkmalfenster entstand als Kind des Hauptfensters, wurde dort nativ und
steckte beim Umzug die ganze Andockleiste an. Je Klick 30 neue Fenster;
`setVisible` 1,3 ms mit sofortigem Malen, `move` 1 ms, neun Fenster anlegen
und zeigen 19 ms, löschen 13.

**Why:** Offscreen gibt es das nicht — die Suite und jede Offscreen-Sonde
sehen nichts davon. Gefunden hat es nur ein Zähler am echten Fenster
(`testAttribute(WA_NativeWindow)` über `QApplication.allWidgets()`) und
`WinIdChange` als anwendungsweiter Ereignisfilter, der sagt, wer wann ein
Fenster bekam.

**How to apply:**

- Die Regel steht in `.claude/rules/ansicht.md` („Nur was über der
  Grafikfläche liegt, hat ein eigenes Fenster") und im Code als
  `overlay.keep_widgets_alien` / `hold_above_the_view`.
- **Ein Widget entsteht in seinem endgültigen Elternteil.** Als Kind der
  Ansicht gebaut und dort poliert behält es sein Fenster und macht beim
  Umzug seine neuen Vorfahren nativ.
- Wer etwas über der Fläche anlegt, prüft danach mit `scenario_verdeckt.py`
  (`.claude/.state/rm-232-erster-klick-2026-09-25/`), dass nichts unter ihr
  verschwindet.
- Gemessen wird abwechselnd unter derselben Last (`ab.sh` dort), nie einzeln
  — die Maschine teilt sich mit Torläufen anderer Sitzungen
  ([[leistungstests-fremdlast]], [[sonde-ohne-exec-loescht-nichts]]).
