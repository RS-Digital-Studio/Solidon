# Prüfbericht zeigt Fehler, die nicht mehr oder noch nicht gelten

Kundenrückmeldung 0.5.3 (S-20261006-5be329): „manchmal wird im Prüfbericht auch
Fehler angezeigt und kurz darauf ist die Berechnung erst fertig“.

Gemessen am HEAD `3a5d607f3`. Damit die fremden ungesicherten Änderungen im
Arbeitsbaum nicht mitgemessen werden, lag ein `git archive HEAD app` im
Scratchpad (`head/`). Jede Ausgabedatei nennt den geladenen Baum. Die Sonde
`sonde_bericht.py` lief am echten `MainWindow(Session(), UiSettings())`,
offscreen, mit APPDATA und LOCALAPPDATA in einem Temp-Ordner. Alle 50 ms
schrieb sie `busy`, `result_current`, die laufende Güte, Kopf und Grund des
Berichts, jede Zeile mit ihrer Schwere, die Statuszeile und die
`check_states`. Dazu kam ein Kernvergleich Entwurf gegen fein
(`kern_entwurf_fein.py`).

Der Stand von 13:45:45 ist aus dem Verlauf der Kundendatei nachgebaut
(`stand_op6.p3d`: Ops 1–5 und `remove_feature pin_7`, entnommen aus den
`before`-Einträgen der Transaktionen t7, t9 und t10).

## Ergebnis je Kandidat

### (a) Alte Fehler bleiben während der Rechnung ohne Kennzeichnung stehen: belegt

Das ist der Weg aus der Rückmeldung. Der Kunde stellte den Radius von 2,0 auf
1,0 (t20 → t21). Nachgestellt mit der Kundendatei (`radius.txt`):

```
== change_params(18, radius=1.0) ==
    0ms busy=0 Kopf='Übergabe nicht empfohlen' Grund='' Status='Die Kette hält an — siehe Prüfbericht.'
         E:op.fillet_edges.GeometryError: Der Radius ist für diese Kanten zu groß …
   13ms >> busyChanged(True)
   75ms busy=1 current=0 lauf=draft  Kopf='Übergabe nicht empfohlen' Grund=''  Status='Die Kette hält an …'  checks={}
         E:op.fillet_edges.GeometryError: Der Radius ist für diese Kanten zu groß …
  262ms busy=1 … Status='Merkmale zuordnen · 91 % · Verstrichen: 0 s'
         E:op.fillet_edges.GeometryError: …            (unverändert)
  670ms >> sceneChanged stopped_at=None
  674ms busy=0 current=1 Kopf='Bewertung unvollständig'   (Fehlerzeile weg)
```

Die alte Fehlerzeile bleibt also mit voller Schwere stehen, dazu
„Übergabe nicht empfohlen“ und das Fehlersymbol. Die Statuszeile meldet
weiter „Die Kette hält an“, bis das Ergebnis da ist. Der Hinweis
„Die Bewertung läuft; der vorige Stand bleibt sichtbar.“ ist
**nur ohne Fehler** zu sehen. Der Gegenlauf zeigt es: Beim Wechsel 1,0 → 2,0
stand er 3,7 s lang da (`Grund='Die Bewertung läuft …'`). Liegt ein Fehler
vor, wird er unterdrückt. 0,6 s gelten für den Radius 1,0 aus dem Cache. Ein
frisch gerechneter Radius brauchte 3,7 s, und genau so lange stand beim
Kunden der widerrufene Fehler da (1,0 war vorher nie gerechnet).

Verantwortlich (Zeilen am HEAD):

- `app/ui/panels.py:6467-6508` `ReportPanel.show_result`: Die Zeilen
  ändern sich nur mit einem Ergebnis, das Panel kennt keinen Zustand „rechnet“.
- `app/ui/panels.py:6971`: `reason = … if self._review_missing and not counts["error"] else ""`
  schluckt den Hinweis, dass gerechnet wird, sobald ein alter Fehler dasteht.
- `app/ui/print_contract.py:167-176` `handoff_state`: Fehler gehen vor
  „unvollständig“. Ein laufender Lauf ist kein eigener Zustand.
- `app/ui/main_window.py:23403-23429` `_update_review_status` hängt den
  Hinweis zum laufenden Lauf (23407-23408) **hinter** `target.missing`, und
  der Kopf zeigt nur den ersten Grund. `23807-23808` `_on_busy` ruft sonst
  nichts am Bericht.
- `app/ui/main_window.py:23149-23163`: `_halted` und die Ansage
  „Die Kette hält an“ fallen erst mit dem nächsten Ergebnis ohne Halt.
- `app/ui/session.py:5219-5222` `evaluate_async`: Hier wird
  `result_current=False` gesetzt und `check_states` geleert. Der Bericht
  erfährt davon nur über den Grundsatz.
- Nicht gemessen, aber am Code: Auch die Fehlermarke am Reiter
  (`main_window.py:25977-26006`, `alertsChanged`) zählt den alten Fehler
  weiter.

### (b) Ein Entwurfsfehler wird von der feinen Rechnung widerrufen: im Mechanismus belegt, über den Druckdialog widerlegt, dazu ein eigener Fehler

1. **Kundenfall op 6** (`kern_op6.txt`, `voll_op6.txt`): Der Entwurf meldet
   „In der schnellen Vorschau blieb von dem Körper nichts übrig … sagt erst
   die vollständige“. Die feine Rechnung (32 s im Kern, 17 s im Fenster)
   **bestätigt** den Fehler, mit einem anderen Text: „Von dem Körper bleibt
   nichts übrig — das Werkzeug deckt ihn vollständig ab. Prüfen Sie Maß und
   Lage.“ `remove_feature pin_7` am Stiftkörper räumt ihn wirklich ab. Ein
   Widerruf war es hier nicht. Der Kunde las zweimal (op 6 und nach
   *Reparieren* op 8) den Entwurfssatz, der die Antwort offenlässt. Eine
   Reparatur kann dort nicht helfen.
2. **`request_fine` tut an einem Entwurfshalt nichts** (`fein_op6_2.txt`, `erzwungen.txt`):
   ```
   == request_fine() — wie beim Öffnen des Druckdialogs ==
      fine_current=True last_quality=draft reads_quality=False stopped_at=6
      (kein busyChanged, die Entwurfszeile bleibt)
   ```
   Ursache: `app/core/scene/evaluate.py:1055-1062` bricht beim Halt ab, bevor
   `reads_quality` in 1117-1119 gesetzt wird. `session.py:5392-5395`
   `fine_current` hält das Entwurfsergebnis deshalb für fein. Druckdialog
   (`main_window.py:8737`) und Export (`main_window.py:9286-9299`) bestellen
   die vollständige Kette also nie, obwohl der Satz im Bericht genau sie
   ankündigt. Nur *Voxelstufe erzwingen* rechnet sie
   (`main_window.py:24463` → `session.py:5365-5376`).
3. **Widerruf und Rückkehr, erzwungen** (`erzwungen_voll_2.txt`: Stufen
   `direct` und `welded` liefern per Patch nichts). Der Entwurf hält an op 11
   mit `E:op.pattern_feature.BooleanFailedError`. `recompute_fully` rechnet
   op 11 fein (`W:boolean.jittered`), **der Fehler an op 11 verschwindet**.
   Der nächste Entwurfslauf bringt ihn zurück:
   ```
   == danach: nächste Auswertung wieder im Entwurf ==
      fine_current=True last_quality=fine stopped_at=14
    519ms sceneChanged stopped_at=11 quality=draft
          E:op.pattern_feature.BooleanFailedError … (wieder da)
   ```
   Dasselbe ohne Patch im Kern (`kern_op6.txt`): erst Entwurf, dann fein,
   dann wieder Entwurf. Der dritte Lauf bringt den Satz der schnellen
   Vorschau zurück, obwohl die vollständige schon entschieden hat. Während des
   feinen Laufs (17 s) bleibt die Entwurfszeile als Fehler stehen, wie unter (a).
   Den Halt an op 14 im erzwungenen Lauf löst die Störung der Ecken aus
   (Merkmal verloren). Er ist ein Artefakt des Patches und kein Befund.

Verantwortlich: `app/core/geom/boolean.py:323-351` (Entwurfssatz),
`app/core/errors.py:727-731` (Titel),
`app/core/scene/evaluate.py:6127-6136` (jeder Halt wird `severity="error"`,
auch wenn nur die kurze Kette gelaufen ist), `evaluate.py:1055-1062` gegen
1117-1119 (`reads_quality` beim Halt), `app/ui/session.py:5378-5411`
(`fine_current`, `request_fine`).

### (c) Zwischenstände aus `check_states` oder dem Bild zuerst erscheinen als Fehler: widerlegt

Die Kundendatei hat 59 740 Dreiecke und liegt damit über
`PICTURE_FIRST_TRIANGLES` (50 000). Beim Öffnen kam das Bild zuerst
(`radius.txt`, `dialog.txt`):

```
153200ms >> pictureChanged stopped_at=None
153249ms busy=1 bild=1 Kopf='Bewertung unvollständig' Grund='Die Bewertung läuft; der vorige Stand bleibt sichtbar.'
         W:pattern_feature.overlap … I:arrange.below_bed … I:perceive.pending …
166793ms >> sceneChanged  → dieselben Zeilen, perceive.pending ersetzt durch 2× perceive.orphaned
```

Kein Fehler, keine Warnung kam und ging wieder. Ein Halt erzeugt kein Bild
(`session.py:292-293`). `check_states` (`running`, `not_started`, `failed`)
gehen nur in Prüfumfang und Grund (`main_window.py:23413-23426`), nie in die
Liste. Was nach dem Ergebnis nachkommt, ist die Schichtanalyse:
`W:settings.wall_below_nozzle` traf 2,4 s danach ein, `W:slice.island_needs_support`
nach dem feinen Lauf. Der Kopf wechselt dabei von „Bewertung unvollständig“
zu „Entscheidung erforderlich“. Das sind Warnungen, keine Fehler, und sie
treffen nur den aktuellen Stand (`print_findings_flow.py:147-150`).

### (d) Die Vorschau eines offenen Dialogs schreibt ihren Fehler in den Bericht: widerlegt

Die Kontrolle griff (`dialog.txt`): Fase-Dialog an `obj_3:face_2`,
Kantenwahl der Reihe nach durchgeschaltet.

```
 7907ms >> Kantenwahl -> vertical (Senkrecht)
11912ms >>   Dialog-Absage='Zu dieser Auswahl gehört keine Kante.'
         Bericht: unverändert, keine E-Zeile (8 Zeilen wie vorher)
```

Die Zeilen 13:51:33–40 im Kundenprotokoll stammen von solchen Vorschauen. Der
Kern schreibt dort `evaluation stopped at op 13` für die Vorschau wie für
eine Auswertung (`evaluate.py:1607-1610`), und t15 trägt die Fase mit
`edges="horizontal"` ohne spätere Änderung. Im Bericht standen sie nicht:
`preview_async` (`session.py:4307-4488`) liefert Absagen nur an den Dialog
(`main_window.py:21412-21414` → `_preview_refused` 21828 → `show_refusal`).

Ein Nebenweg ohne Messung: Die Vorschau eines **Agentenvorschlags** schreibt
ihre Befunde in den Bericht (`main_window.py:16778-16783`), bevor übernommen
wurde. Ein Halt im Vorschlag stünde dann als Fehler im Bericht, bis die
nächste Auswertung ihn ersetzt.

## Fix-Vorschlag aus Kundensicht

1. **Rechnet es, sagt der Bericht das, auch neben einem alten Fehler.**
   Ab 200 ms Laufzeit (§2.8, dieselbe Schwelle wie der Balken; ein Lauf aus dem
   Cache von 0,6 s bliebe ruhig) wechselt der Kopf auf „Wird neu berechnet …“
   mit Uhrsymbol statt Fehlersymbol. Die alten Zeilen bleiben sichtbar
   (§15.3, `wartezeit.md`), aber gedämpft und mit dem Vorsatz
   „Voriger Stand:“ als zweiter Kodierung neben der Farbe (Regel 18). Ihre
   Handlungsknöpfe sind gesperrt, mit dem Grund „Erst nach der Berechnung“.
   Die Reitermarke zeigt keine neue Fehlerzahl. Die Ansage „Die Kette hält
   an“ weicht beim Start des Laufs dem Fortschritt.
   Umsetzung: ein `ReportPanel.set_running(bool)` aus `MainWindow._on_busy`,
   dazu `_count_up` mit eigenem Zweig für „läuft“ und `_halted` beim Start
   zurücksetzen. `handoff_state` bekommt den Laufzustand als eigenes Argument
   statt einer Umdeutung von „Fehler“.
2. **Ein Entwurfsfehler, den die vollständige Rechnung klären würde, ist eine
   offene Prüfung, kein Fehler.** Hält die kurze Kette mit
   `BooleanFailedError` an, ohne dass `voxel` gelaufen ist, startet die
   Sitzung die vollständige Kette einmal selbst (`recompute_fully`, einmal je
   Dokumentstand). Die Zeile lautet so lange „Wird vollständig gerechnet –
   die schnelle Rechnung kam hier nicht weiter“, mit Uhrsymbol. Erst das
   feine Urteil wird Fehler, mit dem Satz, der dem Kunden weiterhilft
   („Das Werkzeug deckt den Körper vollständig ab“), oder es verschwindet.
   *Voxelstufe erzwingen* bleibt als Handlung bestehen.
3. **Ein Halt im Entwurf ist nie `fine_current`.** Der Halt muss
   `reads_quality` mitnehmen (`evaluate.py:1055-1062`), sonst überspringen
   Druckdialog und Export die vollständige Kette.
4. **Das feine Urteil gilt für die folgenden Entwurfsläufe**, solange sich
   Schritt und Eingang nicht ändern: den Schritt beim nächsten Entwurf mit der
   vollen Kette rechnen oder das Urteil im Cache halten. Sonst springt der
   Fehler bei jeder Änderung weiter hinten wieder auf.

## Tests, die das Verhalten heute zusichern

- `tests/test_print_contract.py:118-134`
  `test_handoff_state_requires_completed_scope_even_without_findings`:
  `("error", True) → "Übergabe nicht empfohlen"`. Der Laufzustand muss
  deshalb ein neuer Eingang sein.
- `tests/test_print_contract_ui.py:66-80`
  `test_empty_findings_do_not_claim_print_readiness`: Fehler neben fehlender
  Grundlage ergibt „Übergabe nicht empfohlen“ (ohne Lauf, verträglich).
- `tests/test_print_contract_ui.py:972-1017`
  `test_the_head_is_one_line_and_counts_leave_out_zeros`: Grund
  „Schichtanalyse: läuft“ ohne Fehler, kein Grund bei vollständiger
  Bewertung.
- `tests/test_boolean.py:1906-1931`
  `test_an_empty_result_in_draft_quality_points_at_the_stages_left`:
  Entwurfssatz mit „Rechenstufen“, Titel „schnellen Rechnung“, Handlung
  `use_voxel_stage`. Ein Fix in der Auswertung oder der Oberfläche lässt die
  Ausnahme selbst unberührt.
- `tests/test_ui.py:9849-9870`
  `test_a_boolean_that_failed_in_draft_can_go_the_full_chain`: Der Handler
  `use_voxel_stage` startet einen feinen Lauf und muss bleiben.
- `tests/test_evaluation.py:6490-6585` (RM-494): `reads_quality` an
  vollständigen Läufen. Ein Halt ist nicht abgedeckt, der neue Test gehört
  dorthin.
- `tests/test_ui.py:17645` `test_the_halt_message_goes_when_the_chain_runs_again`:
  prüft erst nach dem Lauf und verträgt das frühere Räumen.
- `tests/test_analysis_ui.py:7667` `test_a_stale_result_does_not_add_its_findings`
  und `tests/test_evaluation.py:5564-5696` (Bild zuerst) sind nicht betroffen.
- Eine Zusicherung, dass alte Fehler während eines Laufs ohne Kennzeichnung
  bleiben, gibt es nicht: Weder „Die Bewertung läuft“ noch ein Laufzustand
  des Berichts kommt in `tests/` vor.

## Was nicht geprüft ist

- Wie es aussieht (Dämpfung, Symbol, Schrift): nur offscreen gemessen, am
  echten Fenster offen.
- Gefahren wurden keine Tests der Suite. Die Untersuchung ändert keinen Code;
  geschriebene oder zurückgestellte Fenstertests gibt es nicht.
- Die Zeiten stammen von einer stark belasteten Maschine (pytest `-n 8` und
  weitere Läufe anderer Sitzungen) und gelten als Größenordnung.

## Nebenbefund an der Sonde

`QTest.qWait` hielt beim Warten die GIL. Der Auswertungsarbeiter bekam in 20 s
0,2 s Rechenzeit, der Stapel stand in der Merkmalserkennung, das Öffnen kam
nach 600 s nicht zur Ruhe. Mit `processEvents()` und `time.sleep(0.01)` dauerte
dasselbe Öffnen 24–166 s. Das betrifft die Bauart von Sonden und Tests, die mit
`QTest.qWait` auf Arbeiter warten, nicht das Produkt.
