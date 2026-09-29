# Paket 3mf — Schluss

Zweig `rm-258-3mf` (von `aa82afdff`), Endcommit `5a6f0bfa3`, gepusht, nicht
nach `main` gemerged. Einzelheiten und Sonden: `reports\3mf.md`,
`sonden\3mf\`.

## 1. RM-258

**Ursache** (`py-spy dump --native`, `out\p01_a1_dumps\`): Der Hauptfaden
wartet in `PyGILState_Ensure` unter jedem Python-Einstieg eines Neuzeichnens
(Anwendungsfilter, Überschreibungen, Slots). Jeder dieser Griffe wartete neben
dem Lesefaden bis zum Ablauf des Umschaltintervalls, und das endet unter
Windows am Takt des Systemzeitgebers: 15,6 ms je Griff (`p03_umschalten.py`).
Verstärkt durch C-Strecken des Lesers bis 160 ms, einen Sekundentakt der
Ladeanzeige, der das ganze Fenster neu malte (rund 45 Widgets), und die Suche
nach der 3D-Maus im Hauptfaden.

**Gebaut:**

| Commit | Was |
|---|---|
| `4d071c887` | `XML_CHUNK` 32 KB, `NUMBER_BLOCK` 4 096, `_outside_meshes` statt `findall(".//…")` (höchstens 2,3 ms je C-Strecke) |
| `fe2f74e95` | Schleier `WA_OpaquePaintEvent`, Takt und Fortschritt malen nur `_block_rect()` |
| `578d1eb71` | `hid.enumerate()` im Daemon-Faden (`SpaceMouseController._search`), geöffnet im Hauptthread |
| `5a6f0bfa3` | `GIL_SWITCH_S = 0.001` beim Start; `Worker.run` verlangt unter Windows für die Dauer von `work` `timeBeginPeriod(1)` |

**Messung** (Drache, echte Ereignisschleife, gebunden `FFFFF0FF`, je Lauf ein
Prozess, im Wechsel, Last 90 bis 100 %), längste Lücke im Qt-Takt:

| Takt der Sonde | vorher | nachher |
|---|---|---|
| grob 25 ms (hebt die Zeitgeberauflösung nicht, Reihe `abt`) | 2,58 · 2,73 · 2,52 s | 0,27 · 0,16 · 0,31 s |
| 5 ms (wie die Durchsicht, Reihen `abc1`, `abz1`) | 2,04 · 1,46 · 1,61 · 1,26 · 1,31 · 1,20 s | 0,18 · 0,17 · 0,23 · 0,20 · 0,22 · 0,23 s |

Lücken über 200 ms je Import: vorher 8 bis 20, nachher 0 oder 1. Gesamtdauer
unverändert (von der Last bestimmt). Gegenprobe ohne `_prompt_handover`
(grober Takt): 0,40 bis 0,62 s, 7 bis 16 Lücken über 200 ms.

**Abnahme „längste Lücke unter 200 ms“: teilweise.** Während des Lesens
selbst (bis eine Sekunde vor der Rückfrage) 0,15 bis 0,20 s, einmal 0,31 s.
Zweimal je Import liegt die Lücke darüber, beide einmalig und kurz:

- der erste Aufbau der Arbeitsfläche beim Wechsel von der Startfläche
  (bei 6 bis 7,5 s): 0,15 bis 0,31 s;
- das Modellbild und der Aufbau der Rückfrage zur Vollerkennung (`_on_ask`),
  während der Arbeiter die Rechnerprobe `recognition_time.probe_work`
  rechnet: 0,14 bis 0,27 s, zweimal 0,39 und 0,55 s. Vorher lag diese Stelle
  bei 0,15 bis 0,27 s, sie ist also nicht schlechter geworden.

Unter Last von 90 bis 100 % auf allen Kernen gemessen. Ohne Last sind kürzere
Werte zu erwarten, belegt ist das nicht.

## 2. Kundensicht

Vorher: Beim Öffnen einer großen 3MF (Mausoleum-Drache, 2,3 Mio. Dreiecke)
steht das Fenster immer wieder 1 bis 2,7 s still, jede Sekunde neu, solange
gelesen wird: Die Uhr springt, Mauszeiger und Knöpfe reagieren nicht. Mit
3D-Maus-Suche kommen weitere Stockungen dazu. Nachher läuft das Fenster
während des Lesens flüssig. Zwei kurze Stockungen um 0,2 bis 0,5 s bleiben,
beim ersten Bild und bevor die Frage nach der Vollerkennung erscheint.

## 3. Dateien und Tests

| Datei | Tests |
|---|---|
| `app/core/ingest/threemf.py` | `test_threemf_assembly.py::test_objects_and_materials_are_found_without_entering_a_mesh`, `::test_no_search_over_the_whole_model_holds_the_interpreter`, bestehend `::test_the_model_xml_is_read_in_pieces_and_nothing_stays_frozen`, `::test_numbers_in_blocks_give_the_same_arrays` |
| `app/ui/leash.py`, `app/ui/app.py` | `test_leash.py::test_a_worker_asks_for_millisecond_timers_only_while_it_works`, `::test_the_start_hands_the_interpreter_over_every_millisecond` |
| `app/ui/spacemouse.py` | `test_spacemouse.py::test_an_offered_search_is_opened_without_searching_again`; Fenstertest `::test_the_controller_searches_off_the_main_thread` |
| `app/ui/loading.py` | Fenstertest `test_loading.py::test_the_clock_repaints_the_block_not_the_whole_window` |
| `.claude/rules/wartezeit.md`, `dateiformat.md`, `kamera.md`, `app/ui/CLAUDE.md` | Unterlagen |

Die beiden Fenstertests sind geschrieben und zurückgestellt. Offscreen
außerhalb der Suite einmal gefahren, grün (`sonden\3mf\p07_fenstertests.py`,
`laeufe\3mf-p07.txt`).

**Tor:** `F:\3D Druck.review-051\laeufe\3mf-tor.txt`: 17 908 passed,
59 skipped, Läufe mit Fehler 0, ruff/format/mypy EXIT 0.

Der Betroffenen-Lauf (`laeufe\3mf-betroffen1.txt`) umfasste 360 von 372
Dateien in einem Prozess. Er hing im `gc.collect()` von `conftest.py:432` und
wurde von der Release-Sitzung beendet. Das liegt nicht an dieser Änderung;
`wt-texte` hing an derselben Stelle.

Am echten Fenster ist nichts geprüft. Offscreen belegt keine Darstellung. Ob
der Schleier mit `WA_OpaquePaintEvent` und den Teilrechtecken sichtbar sauber
malt (keine Reste an den Rändern des Blocks, auch bei laufender Animation und
bei Themenwechsel), ist deshalb **offen** und muss am echten Fenster
angesehen werden.

## 4. Oberflächentexte

Keine neuen oder geänderten.

## 5. Changelog

„Beim Öffnen großer 3MF-Dateien bleibt das Fenster bedienbar, auch während
das Modell gelesen wird.“

## 6. Registertext

RM-258 kann schließen, wenn die Release-Sitzung die Ausnahme so annimmt: Die
Ursache ist behoben, das Lesen liegt unter 200 ms. Offen bleiben die zwei
einmaligen Stellen aus Abschnitt 1, und zwar genau so, wie sie dort stehen.
Sonst bleibt ein Rest: „Erstes Bild der Arbeitsfläche und Aufbau der
Rückfrage zur Vollerkennung stehen neben dem Arbeiter einmal je Import 0,15
bis 0,55 s (Messung `sonden/3mf`, Reihen `abt`, `ab4`).“ Der Hebel dafür ist
die Zahl der Griffe des Hauptfadens je Bild, vor allem der Anwendungsfilter
`ApplicationEvents`, der für jedes Ereignis in Python läuft.

## 7. Nicht behoben

- Die zwei einmaligen Lücken aus Abschnitt 1. Sie brauchen weniger
  Python-Einstiege im ersten Aufbau und in `_on_ask`, also einen Eingriff in
  den Anwendungsfilter bzw. den Bildaufbau. Das geht über den Leser hinaus.
  Gemessen: `out\p01_d7_dumps\01_*`, `p01_d10.txt`, `p01_d11.txt`.
- Kürzer als 1 ms schalten ist verworfen: Unter Windows dreht sich dann jeder
  Wartende im Kreis, und zwei Rechenfäden reichen den GIL nach jedem Befehl
  weiter (Durchsatz 0,80 bis 0,93).
- Werkzeug: `py-spy record --native` hielt den Zielprozess zweimal
  angehalten („Failed to resume process: Zugriff verweigert“). Benutzt wurde
  nur `dump`. py-spy war nach der Messung deinstalliert; die Release-Sitzung
  hat es für ihre Diagnose wieder installiert und entfernt es selbst.
