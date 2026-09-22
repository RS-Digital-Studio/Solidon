# Nächster Anschluss P0.3

Noch kein Produktcode dieses Abschnitts geändert. Erst den laufenden P2.3-/P0.7-Block mit Entwicklungstor und getrennten Commits abschließen.

## Erster Kundenweg

Körper und vorhandene Bohrung im Modell wählen. Die Maße erscheinen auch bei geschlossenem Panel. Reine Maßanzeige ist noch kein begonnener Entwurf. Erst Feld oder Griff aktiviert die Bindung an Handlung, Dokument, Ergebnis, Körper, Merkmal und Umfang. Bei erkannter Bohrung trägt `resize_hole` Durchmesser und Lage, aber keine Tiefe; Tiefe bleibt dort gemessene Auskunft. Ein eindeutig zugeordneter ursprünglicher Bohrungsschritt kann dagegen einschließlich seiner tatsächlichen Tiefe geändert werden. Seine vollständigen Folgeschritte gehören zur Vorschau.

`QuietHost` hält den Entwurf; `PlacementFlow` verwendet die vorhandenen Maßfelder und die Kollisionsbehandlung. Die fachlichen Felder und ihre Umrechnung kommen aus einem gemeinsam herausgelösten Erzeuger-/Lesepaar von `FeaturePanel._build_field()` und `_values()`. Die aktive Feldgruppe gehört dem Flow, ihre Panel-Gegenstücke sind währenddessen nicht editierbar. Feldleihen wäre wegen `clear()`, Ereignisfiltern und gespeicherten Rückrufen hier aufwendiger. Werte, Merkmal, Originalschritt und Gruppenumfang müssen im Entwurf gebunden sein statt weiterhin aus dem lebenden Panel gelesen zu werden.

Ein gemeinsames ✓/× steht bei der aktiven Feldgruppe, darunter der vorhandene fachlich belegte Gruppenumfang. Enter interpretiert zunächst alle aktiven Zahlentexte, bereitet denselben vollständigen Auftrag vor und verlangt dessen dargestellte aktuelle Vorschau. Frühes Enter wird nicht nachgeholt. Fokusverlust, Tab, Loslassen und Kamera schreiben nichts. Der Callback muss Erfolg melden, bevor `QuietHost` den Entwurf verbraucht und `finished` sendet. `PlacementFlow` darf vorher nicht `_stop()` aufrufen. Der bestehende `finished`→`dispose`-Weg kann den erfolgreichen Abschluss tragen; eine Änderung der QDialog-`accept()`-Signatur ist dafür nicht nötig.

`requires_displayed_preview` ist ein neues Eingabemerkmal, getrennt vom abgeleiteten `preview_required`. Bei `change_op` bleibt `required=None` bis zur historischen Eingangsrechnung. Danach setzt `_finish_preview_prefix` die Pflicht aus Maßeditorpflicht ODER exakten Eingängen. `_set_preview_order` muss dieselbe Pflicht berücksichtigen. Keine neue Vorschauverwaltung.

`Session.apply/change_params` melden innerhalb ihres erfolgreichen Aufrufs synchron `projectChanged`. Ein enger Übernahme-Abschnitt in `QuietHost` muss deshalb die eigene Änderung bis zur Rückgabe des Callbacks halten; sonst räumt `PlacementFlow._document_changed()` trotz entferntem vorzeitigem `_stop()` erneut zu früh ab. Fremde Dokumentänderungen bleiben sofort entwertend. Der vorhandene `_commit_preview_order()` liefert bereits den passenden booleschen Erfolg.

## Auswahl und Lebensdauer

Recherche §4.2 Punkt 6 ersetzt für einen begonnenen Entwurf den bisherigen Außenklick-Abbruch: Außenklick erhält Werte und Ziel; eine andere Operation ersetzt erst nach ✓/×. Kein zusätzlicher Bestätigungsdialog und kein nachgeholter fremder Befehl. Unberührte Maßanzeige bleibt abwählbar. Programmatische Dokument-/Ergebniswechsel entwerten den Entwurf weiterhin sicher.

Ein Guard nur in `MainWindow._on_object_picked` genügt nicht: `Viewport._select_at` ändert nach dem Objektsignal selbst noch die sichtbare Merkmalsauswahl. Ein enger Auswahlguard muss davor liegen und auch den Objektbaum erreichen. Kamera bleibt frei. Gemeinsame Befehlseinstiege beachten denselben Entwurfszustand.

## Dateien und Abnahme

Anschlüsse: `placement_flow.py` (Host, Maße, Abschluss), `panels.py` (Felder, Gruppen, Anzeige), `main_window.py` (Einstieg, Auftrag, Vorschaufreigabe, Session-Erfolg), `viewport.py` und Objektbaum (Auswahlguard). Bauplan §18.11 und die betroffenen Gebietskarten/Regeln vor dem Umstellen nachführen. Übersetzungen vollständig.

Fensterregressionen schreiben, gemäß dauerhafter Prüfregel erst beim Release ausführen: geschlossenes Panel, Mesh/BRep, reale Feldtastatur, früher/zweiter Enter, Callback-Ablehnung, Tab/Kamera/Außenklick, anderer Befehl, Escape während Rechnung, verspätete Antwort, Gruppenfehler ohne Teilübernahme, historische Tiefe mit Folgeschritten, gemeinsames Undo/Redo, DPI/Ränder/lange Übersetzungen.
