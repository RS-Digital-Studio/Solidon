# Entwurf HB-4: die nächsten Bildanleitungen

Stand 27.09.2026. Arbeitsvorlage für HB-4, damit eine neue Sitzung ohne den
Kontext dieser Sitzung weitermachen kann. **Noch nicht am Fenster geprüft** —
was unter „Zu prüfen" steht, entscheidet sich erst im Probelauf von
`tools/make_guides.py`. Ist eine Anleitung gebaut und angesehen, wandert sie
nach `app/core/guides.py` und `tools/make_guides.py`, und ihr Abschnitt hier
wird gelöscht. *Ein Modell prüfen und drucken* ist gebaut und steht deshalb
nicht mehr hier.

**Was der erste Probelauf gelehrt hat:** Ein Satz des Entwurfs, der eine
Bedienung beschreibt, ist eine Vermutung, bis das Bild dazu vorliegt. Beim
Prüfbericht stand „der Knopf darunter behebt ihn" — am Fenster standen
*Stelle zeigen* und *Offen lassen*, weil Solidon beim Einlesen schon repariert
hat. Deshalb: erst aufnehmen und ansehen, dann Sätze und Übersetzungen
festschreiben.

## Anleitung `drill-a-hole` — Ein Loch bohren

Teil `start`, in `manual.OUTLINE` hinter `print-a-model`. Kurzfassung: „Eine
Bohrung in ein vorhandenes Modell setzen und später verschieben."

| Nr. | Satz (deutsche Quelle) | Ziele |
|---|---|---|
| 1 | Klicken Sie auf das Teil. Es ist jetzt gewählt. | `viewport` (Punkt auf dem Teil) |
| 2 | Klicken Sie noch einmal, genau auf die Fläche für das Loch. | `viewport` (Punkt auf der Fläche), `selection` |
| 3 | Rechts unter *Auswahl*: Klicken Sie auf *Bohrung setzen*. | `operation:drill_hole` |
| 4 | Tragen Sie den Durchmesser ein. Die Vorschau zeigt das Loch sofort. | `field:diameter` |
| 5 | Klicken Sie auf *Bohrung setzen*. Das Loch ist gebohrt. | `dialog.accept` |
| 6 | Sitzt es falsch? Ein Doppelklick auf den Schritt im *Verlauf* öffnet ihn wieder. | `history.last` |

Geschichte, mit den Helfern, die `tools/make_guides.py` schon hat (`_import`,
`web.select_body`, `guide_targets.widget_for`):

1. `tests/data/meshes/plate_holes.stl` über `_import` einlesen; Körper wählen
   mit `web.select_body(window, 0)`. Der Klickpunkt für das Bild ist die Mitte
   der Oberseite, projiziert mit `make_video._world_to_window` und über
   `window.mapToGlobal` global gemacht; `capture(1, points={"viewport": …})`.
2. Die größte nach oben zeigende Fläche suchen: Merkmale der Art `face` mit
   `params["normal"][2] > 0.99`, die größte nach `params["area"]`; wählen mit
   `window.object_tree.select_feature(körper, kennung)`; Punkt neben
   `params["centre"]`, damit er nicht in einem vorhandenen Loch liegt; Bild 2.
3. Bild 3, dann `widget_for(window, "operation:drill_hole").click()`; der
   Dialog steht nicht modal in `window._op_dialog`.
4. `dialog._editors["diameter"].setValue(5.0)`, Vorschau abwarten; Bild 4
   und 5 (derselbe Zustand, zwei Ziele).
5. `widget_for(window, "dialog.accept").click()`, abwarten; Bild 6.

Zu prüfen: ob der Knopf *Bohrung setzen* bei gewählter Fläche im
Auswahlfenster steht (`selection_operations._buttons["drill_hole"]`); ob der
Dialog Ort und Richtung aus der Fläche übernimmt; ob der Punkt aus
`_world_to_window` im Bild auf der Fläche liegt; ob die Ansicht nach dem
Einlesen die Platte groß genug zeigt.

## Übersetzungen

Für die acht Sätze von *Ein Loch bohren*, nach den Glossaren aus
`.claude/rules/uebersetzung.md` und mit den Knopftexten, die die Kataloge
schon führen („Drill a bore", „Hacer un taladro", „Percer un trou",
„Pratica un foro", „Abrir furo"). Eintragen erst, wenn die Sätze nach dem
Probelauf feststehen: `python -m app.i18n.extract` im Arbeitsbaum, dann die
Werte setzen.

```json
{
  "en": {
    "Ein Loch bohren": "Drill a hole",
    "Eine Bohrung in ein vorhandenes Modell setzen und später verschieben.": "Put a bore into an existing model and move it later.",
    "Klicken Sie auf das Teil. Es ist jetzt gewählt.": "Click the part. It is now selected.",
    "Klicken Sie noch einmal, genau auf die Fläche für das Loch.": "Click once more, right on the face where the hole should go.",
    "Rechts unter *Auswahl*: Klicken Sie auf *Bohrung setzen*.": "On the right under *Selection*: click *Drill a bore*.",
    "Tragen Sie den Durchmesser ein. Die Vorschau zeigt das Loch sofort.": "Enter the diameter. The preview shows the hole straight away.",
    "Klicken Sie auf *Bohrung setzen*. Das Loch ist gebohrt.": "Click *Drill a bore*. The hole is drilled.",
    "Sitzt es falsch? Ein Doppelklick auf den Schritt im *Verlauf* öffnet ihn wieder.": "In the wrong place? Double-click the step in the *History* to open it again."
  },
  "es": {
    "Ein Loch bohren": "Taladrar un agujero",
    "Eine Bohrung in ein vorhandenes Modell setzen und später verschieben.": "Hacer un taladro en un modelo existente y moverlo después.",
    "Klicken Sie auf das Teil. Es ist jetzt gewählt.": "Haga clic en la pieza. Ahora está seleccionada.",
    "Klicken Sie noch einmal, genau auf die Fläche für das Loch.": "Haga clic otra vez, justo en la cara donde irá el agujero.",
    "Rechts unter *Auswahl*: Klicken Sie auf *Bohrung setzen*.": "A la derecha, en *Selección*: haga clic en *Hacer un taladro*.",
    "Tragen Sie den Durchmesser ein. Die Vorschau zeigt das Loch sofort.": "Introduzca el diámetro. La vista previa muestra el agujero al instante.",
    "Klicken Sie auf *Bohrung setzen*. Das Loch ist gebohrt.": "Haga clic en *Hacer un taladro*. El agujero está hecho.",
    "Sitzt es falsch? Ein Doppelklick auf den Schritt im *Verlauf* öffnet ihn wieder.": "¿Está mal colocado? Un doble clic en el paso del *Historial* lo vuelve a abrir."
  },
  "fr": {
    "Ein Loch bohren": "Percer un trou",
    "Eine Bohrung in ein vorhandenes Modell setzen und später verschieben.": "Percer un trou dans un modèle existant et le déplacer plus tard.",
    "Klicken Sie auf das Teil. Es ist jetzt gewählt.": "Cliquez sur la pièce. Elle est maintenant sélectionnée.",
    "Klicken Sie noch einmal, genau auf die Fläche für das Loch.": "Cliquez encore une fois, exactement sur la face où doit aller le trou.",
    "Rechts unter *Auswahl*: Klicken Sie auf *Bohrung setzen*.": "À droite, sous *Sélection* : cliquez sur *Percer un trou*.",
    "Tragen Sie den Durchmesser ein. Die Vorschau zeigt das Loch sofort.": "Saisissez le diamètre. L'aperçu montre le trou aussitôt.",
    "Klicken Sie auf *Bohrung setzen*. Das Loch ist gebohrt.": "Cliquez sur *Percer un trou*. Le trou est percé.",
    "Sitzt es falsch? Ein Doppelklick auf den Schritt im *Verlauf* öffnet ihn wieder.": "Mal placé ? Un double-clic sur l'étape dans l'*Historique* la rouvre."
  },
  "it": {
    "Ein Loch bohren": "Praticare un foro",
    "Eine Bohrung in ein vorhandenes Modell setzen und später verschieben.": "Praticare un foro in un modello esistente e spostarlo in seguito.",
    "Klicken Sie auf das Teil. Es ist jetzt gewählt.": "Fai clic sul pezzo. Ora è selezionato.",
    "Klicken Sie noch einmal, genau auf die Fläche für das Loch.": "Fai clic ancora una volta, proprio sulla faccia dove andrà il foro.",
    "Rechts unter *Auswahl*: Klicken Sie auf *Bohrung setzen*.": "A destra, sotto *Selezione*: fai clic su *Pratica un foro*.",
    "Tragen Sie den Durchmesser ein. Die Vorschau zeigt das Loch sofort.": "Inserisci il diametro. L'anteprima mostra subito il foro.",
    "Klicken Sie auf *Bohrung setzen*. Das Loch ist gebohrt.": "Fai clic su *Pratica un foro*. Il foro è fatto.",
    "Sitzt es falsch? Ein Doppelklick auf den Schritt im *Verlauf* öffnet ihn wieder.": "È nel posto sbagliato? Un doppio clic sul passo nella *Cronologia* lo riapre."
  },
  "pt": {
    "Ein Loch bohren": "Abrir um furo",
    "Eine Bohrung in ein vorhandenes Modell setzen und später verschieben.": "Abrir um furo num modelo existente e movê-lo mais tarde.",
    "Klicken Sie auf das Teil. Es ist jetzt gewählt.": "Clique na peça. Agora está selecionada.",
    "Klicken Sie noch einmal, genau auf die Fläche für das Loch.": "Clique mais uma vez, exatamente na face onde vai ficar o furo.",
    "Rechts unter *Auswahl*: Klicken Sie auf *Bohrung setzen*.": "À direita, em *Seleção*: clique em *Abrir furo*.",
    "Tragen Sie den Durchmesser ein. Die Vorschau zeigt das Loch sofort.": "Introduza o diâmetro. A pré-visualização mostra o furo de imediato.",
    "Klicken Sie auf *Bohrung setzen*. Das Loch ist gebohrt.": "Clique em *Abrir furo*. O furo está feito.",
    "Sitzt es falsch? Ein Doppelklick auf den Schritt im *Verlauf* öffnet ihn wieder.": "Ficou no sítio errado? Um duplo clique no passo do *Histórico* volta a abri-lo."
  }
}
```
