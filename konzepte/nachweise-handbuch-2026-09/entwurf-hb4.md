# Entwurf HB-4: die nächsten Bildanleitungen

Stand 27.09.2026. Arbeitsvorlage für HB-4, damit eine neue Sitzung ohne den
Kontext dieser Sitzung weitermachen kann. **Noch nicht am Fenster geprüft** —
was unter „Zu prüfen" steht, entscheidet sich erst im Probelauf von
`tools/make_guides.py`. Ist eine Anleitung gebaut und angesehen, wandert sie
nach `app/core/guides.py` und `tools/make_guides.py`, und ihr Abschnitt hier
wird gelöscht.

## Wortschatz, der dazukommt

In `guides.TARGETS` und `app/ui/guide_targets.py` (`_FINDERS` oder eine neue
Tabelle für den Druckdialog):

| Name | Widget | Wie finden |
|---|---|---|
| `report.slicer` | `window.report.to_slicer` („An den Slicer übergeben …") | Attribut des Prüfberichts; sichtbar nur ohne Fehler und mit Körper |
| `print.printer` | `PrintSettingsDialog.printer_choice` | `QApplication.activeModalWidget()` ist der Druckdialog (er läuft über `exec()`) |
| `print.slice` | `PrintSettingsDialog.slice_button` („Slicen") | dito |
| `print.save` | `PrintSettingsDialog.save_button` („Druckdatei speichern …", vor dem Slicen gesperrt) | dito |

## Anleitung `print-a-model` — Ein Modell prüfen und drucken

Teil `start`. Kurzfassung: „Von der heruntergeladenen Datei bis zur
Druckdatei."

| Nr. | Satz (deutsche Quelle) | Ziele |
|---|---|---|
| 1 | Ziehen Sie die Datei auf das Fenster oder klicken Sie auf *Modell öffnen …*. | `start.drop`, `start.model` |
| 2 | Rechts im *Prüfbericht* steht, was am Modell nicht stimmt. | `report` |
| 3 | Klicken Sie einen Befund an. Der Knopf darunter behebt ihn. | `report.action` |
| 4 | Passt alles, klicken Sie auf *An den Slicer übergeben …*. | `report.slicer` |
| 5 | Prüfen Sie oben Drucker und Filament. | `print.printer` |
| 6 | *Slicen* rechnet die Druckdatei, *Druckdatei speichern …* legt sie ab. | `print.slice`, `print.save` |

Geschichte:

1. Zurück auf den Startbildschirm: `session.forget_changes()`,
   `session.start_new()`, `window._show_start_screen(True)`; Bild 1.
2. `tests/data/meshes/broken_open.stl` einlesen wie `make_web_images`:
   `session.start_new()`, `session.import_model(pfad, raise_on_error=True)`,
   `window._show_start_screen(False)`, `web.until_quiet(...)`, Kamera
   einpassen, Reiter Prüfbericht nach vorn; Bild 2.
3. `window.report.list.setCurrentRow(0)`; Bild 3 (der Prüfbericht wählt beim
   Beispiel „Dose mit Deckel" den ersten Befund schon selbst — hier prüfen).
4. `guide_targets.widget_for(window, "report.action").click()`, abwarten,
   Bild 4.
5. Druckdialog über `web.while_open(PrintSettingsDialog, knopf.click, handeln)`;
   in `handeln` erst `dialog.wait_for_slicers()` und `_profiles_pending`
   abwarten (Muster `make_web_images`, Motiv „schritt-druck"); Bild 5 und 6.

Einrichtung im Kindprozess wie in `make_web_images._screens_child`:
`discover.remember_path("slicer", <PrusaSlicer>)` und
`print_disclosure.remember_disclosure(settings)`, sonst steht vor dem Dialog
ein Hinweis, und ohne gemerkten Slicer sucht der Dialog.

Zu prüfen: ob `broken_open.stl` einen Befund mit Handlung bringt (sonst
`partially_open.stl`); ob nach der Reparatur `report.to_slicer` sichtbar ist
(bei der „Dose" stand er mit drei Warnungen da); wo der Druckdialog steht
(`make_web_images` prüft, dass er im Fenster liegt).

## Anleitung `drill-a-hole` — Ein Loch bohren

Teil `start`. Kurzfassung: „Eine Bohrung in ein vorhandenes Modell setzen und
später verschieben."

| Nr. | Satz (deutsche Quelle) | Ziele |
|---|---|---|
| 1 | Klicken Sie auf das Teil. Es ist jetzt gewählt. | `viewport` (Punkt auf dem Teil) |
| 2 | Klicken Sie noch einmal, genau auf die Fläche für das Loch. | `viewport` (Punkt auf der Fläche), `selection` |
| 3 | Rechts unter *Auswahl*: Klicken Sie auf *Bohrung setzen*. | `operation:drill_hole` |
| 4 | Tragen Sie den Durchmesser ein. Die Vorschau zeigt das Loch sofort. | `field:diameter` |
| 5 | Klicken Sie auf *Bohrung setzen*. Das Loch ist gebohrt. | `dialog.accept` |
| 6 | Sitzt es falsch? Ein Doppelklick auf den Schritt im *Verlauf* öffnet ihn wieder. | `history.last` |

Geschichte:

1. `tests/data/meshes/plate_holes.stl` einlesen (wie oben); Körper wählen mit
   `web.select_body(window, 0)`. Der Klickpunkt für das Bild ist die Mitte der
   Oberseite, projiziert mit `make_video._world_to_window` und über
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
`_world_to_window` im Bild auf der Fläche liegt.

## Übersetzungen

Fertig für alle sechzehn Sätze beider Anleitungen, nach den Glossaren aus
`.claude/rules/uebersetzung.md` und mit den Knopftexten, die die Kataloge
schon führen („Open model …", „Hand over to the slicer …", „Slice",
„Save print file …", „Drill a bore" und ihre Entsprechungen). Eintragen:
erst `python -m app.i18n.extract` im Arbeitsbaum, dann die Werte setzen.

```json
{
  "en": {
    "Ein Modell prüfen und drucken": "Check and print a model",
    "Von der heruntergeladenen Datei bis zur Druckdatei.": "From the downloaded file to the print file.",
    "Ziehen Sie die Datei auf das Fenster oder klicken Sie auf *Modell öffnen …*.": "Drag the file onto the window or click *Open model …*.",
    "Rechts im *Prüfbericht* steht, was am Modell nicht stimmt.": "The *Report* on the right says what is wrong with the model.",
    "Klicken Sie einen Befund an. Der Knopf darunter behebt ihn.": "Click a finding. The button below it fixes it.",
    "Passt alles, klicken Sie auf *An den Slicer übergeben …*.": "When everything is fine, click *Hand over to the slicer …*.",
    "Prüfen Sie oben Drucker und Filament.": "Check the printer and filament at the top.",
    "*Slicen* rechnet die Druckdatei, *Druckdatei speichern …* legt sie ab.": "*Slice* calculates the print file, *Save print file …* stores it.",
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
    "Ein Modell prüfen und drucken": "Comprobar e imprimir un modelo",
    "Von der heruntergeladenen Datei bis zur Druckdatei.": "Del archivo descargado al archivo de impresión.",
    "Ziehen Sie die Datei auf das Fenster oder klicken Sie auf *Modell öffnen …*.": "Arrastre el archivo a la ventana o haga clic en *Abrir modelo …*.",
    "Rechts im *Prüfbericht* steht, was am Modell nicht stimmt.": "A la derecha, el *Informe de comprobación* dice qué no está bien en el modelo.",
    "Klicken Sie einen Befund an. Der Knopf darunter behebt ihn.": "Haga clic en un hallazgo. El botón de debajo lo corrige.",
    "Passt alles, klicken Sie auf *An den Slicer übergeben …*.": "Si todo está bien, haga clic en *Entregar al slicer …*.",
    "Prüfen Sie oben Drucker und Filament.": "Compruebe arriba la impresora y el filamento.",
    "*Slicen* rechnet die Druckdatei, *Druckdatei speichern …* legt sie ab.": "*Laminar* calcula el archivo de impresión, *Guardar archivo de impresión …* lo guarda.",
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
    "Ein Modell prüfen und drucken": "Vérifier et imprimer un modèle",
    "Von der heruntergeladenen Datei bis zur Druckdatei.": "Du fichier téléchargé au fichier d'impression.",
    "Ziehen Sie die Datei auf das Fenster oder klicken Sie auf *Modell öffnen …*.": "Faites glisser le fichier sur la fenêtre ou cliquez sur *Ouvrir un modèle …*.",
    "Rechts im *Prüfbericht* steht, was am Modell nicht stimmt.": "À droite, le *Rapport de contrôle* indique ce qui ne va pas dans le modèle.",
    "Klicken Sie einen Befund an. Der Knopf darunter behebt ihn.": "Cliquez sur un constat. Le bouton en dessous le corrige.",
    "Passt alles, klicken Sie auf *An den Slicer übergeben …*.": "Si tout va bien, cliquez sur *Transmettre au slicer …*.",
    "Prüfen Sie oben Drucker und Filament.": "Vérifiez en haut l'imprimante et le filament.",
    "*Slicen* rechnet die Druckdatei, *Druckdatei speichern …* legt sie ab.": "*Trancher* calcule le fichier d'impression, *Enregistrer le fichier d'impression …* l'enregistre.",
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
    "Ein Modell prüfen und drucken": "Verificare e stampare un modello",
    "Von der heruntergeladenen Datei bis zur Druckdatei.": "Dal file scaricato al file di stampa.",
    "Ziehen Sie die Datei auf das Fenster oder klicken Sie auf *Modell öffnen …*.": "Trascina il file sulla finestra oppure fai clic su *Apri modello …*.",
    "Rechts im *Prüfbericht* steht, was am Modell nicht stimmt.": "A destra, il *Rapporto di verifica* dice che cosa non va nel modello.",
    "Klicken Sie einen Befund an. Der Knopf darunter behebt ihn.": "Fai clic su un rilievo. Il pulsante sotto lo corregge.",
    "Passt alles, klicken Sie auf *An den Slicer übergeben …*.": "Se va tutto bene, fai clic su *Passa allo slicer …*.",
    "Prüfen Sie oben Drucker und Filament.": "Controlla in alto stampante e filamento.",
    "*Slicen* rechnet die Druckdatei, *Druckdatei speichern …* legt sie ab.": "*Affetta* calcola il file di stampa, *Salva file di stampa …* lo salva.",
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
    "Ein Modell prüfen und drucken": "Verificar e imprimir um modelo",
    "Von der heruntergeladenen Datei bis zur Druckdatei.": "Do ficheiro transferido ao ficheiro de impressão.",
    "Ziehen Sie die Datei auf das Fenster oder klicken Sie auf *Modell öffnen …*.": "Arraste o ficheiro para a janela ou clique em *Abrir modelo …*.",
    "Rechts im *Prüfbericht* steht, was am Modell nicht stimmt.": "À direita, o *Relatório de verificação* diz o que não está bem no modelo.",
    "Klicken Sie einen Befund an. Der Knopf darunter behebt ihn.": "Clique numa constatação. O botão por baixo corrige-a.",
    "Passt alles, klicken Sie auf *An den Slicer übergeben …*.": "Se estiver tudo bem, clique em *Entregar ao slicer …*.",
    "Prüfen Sie oben Drucker und Filament.": "Verifique em cima a impressora e o filamento.",
    "*Slicen* rechnet die Druckdatei, *Druckdatei speichern …* legt sie ab.": "*Fatiar* calcula o ficheiro de impressão, *Guardar o ficheiro de impressão …* guarda-o.",
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
