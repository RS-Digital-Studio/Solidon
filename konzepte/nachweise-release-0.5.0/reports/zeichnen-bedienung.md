# Bedienabnahme „Zeichnen" — Klick für Klick, als Grundlage für den Umbau

Auftrag: Robert, 23.09.2026 — „das zeichnen musst du nochmal gründlich
kontrollieren auch mit verschieben, drehen, was wegschneiden, bearbeiten,
Ansicht, das ist überhaupt nicht benutzerfreundlich und einfach"; ergänzt um
„Auch erstellen, alles in zeichnen eben" und um die Vorgabe „nur einen Körper
beim Zeichnen — den ausgewählten; ist keiner ausgewählt, ist man beim neu
Zeichnen".

Stand: Arbeitsbaum `F:\3D Druck.review-050\wt-zeichnen`, Commit `3c373348`.
Sonden unter `F:\3D Druck.review-050\sonden\zeichnen\`.

**Stand: vollständig** (fortlaufend geschrieben; alle Abschnitte 0–11 stehen).

## Messweg und seine Grenzen

- Gelesen: `AGENTS.md`, `CLAUDE.md`, `app/ui/CLAUDE.md`,
  `app/core/sketch/CLAUDE.md`, Regeln `zeichenflaeche.md` (vollständig),
  Bauplan §2, §18.11, §30.1, Konzepte `konzept-bedienung.md` Teil 4 und
  Nachträge, `konzept-einfache-bedienung-2026-09.md`,
  `durchsicht-zeichenmodus-2026-09.md`, Bericht `reports/skizze.md`; Code
  `app/ui/main_window.py` (Skizzenmodus 8841–10050, Einstiege, Bearbeiten
  15653–15790), `app/ui/sketch_editor.py` (Werkzeuge, Panel, Klickweg),
  `app/ui/viewport.py` (Mausweg im Skizzenmodus), `app/core/sketch/ops.py`
  (Parameter der Erzeugungsarten).
- **Autodesk Fusion ist auf diesem Rechner nicht startbar.** Unter
  `%LOCALAPPDATA%\Autodesk\Autodesk Fusion 360` liegen nur Reste
  (`Electron`, `CER_AutoPop`, eine SQLite-Datei); der Ordner
  `webdeploy\production` mit `Fusion360.exe` fehlt, und ohne Konto startet
  Fusion ohnehin nicht. **Alle Fusion-Zahlen in diesem Bericht sind aus
  meinem Wissen über Fusion (Stand 2025/26), nicht gemessen**, und stehen
  als „Fusion (Wissen)" gekennzeichnet. Dasselbe gilt für Onshape, SolidWorks,
  Tinkercad und Shapr3D.
- Gezählt wird: **K** = Mausklick (auch Doppelklick als einer), **T** =
  Tastendruck (Ziffern einzeln, Tab und Enter je einer), **W** =
  Kontextwechsel (der Blick muss an eine andere Stelle des Fensters: Leiste
  unten, rechter Reiter, Dialog, Menü), **?** = Stelle, an der ein Kunde ohne
  Vorwissen nicht weiß, was als Nächstes zu tun ist.
- Die Sonden fahren das echte Hauptfenster über `build_application` auf der
  echten Windows-Plattform; Klicks in die 3D-Ansicht gehen über den Handler,
  den der Viewport nach dem Strahlschnitt ruft
  (`MainWindow._on_sketch_point` → `SketchCanvas.place_on_plane`), Knöpfe
  über `click()`, Menüeinträge über `trigger()`. Das ist eine Schicht unter
  dem Mausereignis der Ansicht (Erinnerung „Prüfstand geht den Weg der
  Oberfläche", vierte Richtung); wo das Ergebnis davon abhängen könnte, steht
  es dabei.

## Die drei schwersten Befunde vorab (gemessen, am heutigen Stand rot)

Diese drei stehen oben, weil sie keine Bedienfrage sind, sondern falsche
Ergebnisse auf dem Hauptweg. Jeder ist mit einer Sonde belegt.

### F1 — Sackgasse: Auf einer gewählten Fläche hochziehen scheitert immer

Sonde `b5_aufbau.py build_tray_v3.step 4`, Protokoll `b5_build_tray_v34.txt`,
Bild `b5_dialog_hochziehen_flaeche.png`.

Weg: Oberseite eines Teils anklicken → *Zeichnen* → Kreis Ø 8 → *Hochziehen*
→ Höhe 10 → *Grundform hochziehen*. Ergebnis: **kein Körper**, der Verlauf
hält an mit „Diese Fläche liegt hinter der Skizze — von dort aus geht es
nicht vorwärts."

Ursache: Der Dialog belegt „Bis zur Fläche" mit **genau der Fläche, auf der
gezeichnet wird** — sie ist ja gewählt — und schiebt das Feld nach vorn
(`MainWindow.run_operation` → `_from_selection`, `app/ui/main_window.py:17255–17259`
→ `values_for(spec, feature)`; Feld `up_to`, `app/core/sketch/ops.py:432`).
„Bis zur Fläche" schlägt die getippte Höhe, und von der eigenen Fläche aus
gibt es kein Vorwärts. Der Weg „Fläche anklicken, darauf zeichnen" ist der
einzige, den das Kontextmenü und der Knopf *Zeichnen* bei gewählter Fläche
anbieten — er führt also bei jedem Aufbau auf ein vorhandenes Teil in die
Absage.

Umbau: Die Zeichenebene ist nie Ziel von „Bis zur Fläche"; ein Skizzen-Dialog
übernimmt aus der Auswahl überhaupt keine Orts- oder Zielfelder, wenn die
Zeichnung schon eine Ebene trägt. Abnahme: derselbe Weg an
`build_tray_v3.step` Fläche 236 und an `broomholdervcd_d35mm.stl` Fläche 3
ergibt einen Zylinder Ø 8 × 10 mm (Volumen π·16·10 ± 0,5 %), keinen Befund
der Stufe Fehler.

### F2 — Falsches Ergebnis: Eine Tasche auf einer außermittigen Fläche schneidet ins Leere

Sonden `b3_aussparung.py`, `b4_tasche_netz.py` (Protokolle
`b3_broomholdervcd_d35mm.txt`, `b4_broomholdervcd_d35mm.txt`,
`b4_build_tray_v34.txt`).

Weg (Kundenaufgabe B): Oberseite anklicken → *Zeichnen* → Rechteck 20 × 10
um die Flächenmitte → *Abtragen* → Tiefe 3 → *Tasche schneiden*. Ergebnis am
Besenhalter (Netz, 59 740 Dreiecke) und an der Fläche 236 der Druckschale
(exakt): **Volumen unverändert**, Prüfbericht „Der Schnitt hat nichts
abgetragen — das Werkzeug liegt neben dem Körper. Position prüfen oder an
einer Fläche ausrichten." Nur wo die Flächenmitte zufällig im
Weltursprung liegt (Fläche 137 der Druckschale), stimmt das Ergebnis
(−600 mm³) — deshalb hat es kein Test gesehen.

Ursache: doppelte Verschiebung. Die Zeichnung liegt schon im Rahmen der
Fläche (Ursprung = Flächenmitte, `app/core/sketch/planes.py:346–351`); der
Dialog trägt aus der gewählten Fläche zusätzlich ihre **Weltkoordinaten** in
die Felder X/Y/Oberkante ein (`_from_selection`, wie F1; bei nur gewähltem
Körper nimmt `values_for_object` dessen oberste Fläche), und
`sketch_pocket` verschiebt auch eine gezeichnete Kontur um X/Y
(`app/core/sketch/ops.py:765–768`, `shifted(one, params.x, params.y)`).
Beim Besenhalter liegt das Werkzeug damit bei y ≈ 41 statt 20,5 — neben dem
Teil. X, Y und Oberkante stehen hinter „Weitere Einstellungen"; der Kunde
sieht sie nicht und hat keinen Anhaltspunkt.

Umbau: Mit einer gezeichneten Kontur verschiebt `sketch_pocket` nicht (die
Felder gelten nur der Grundform aus dem Dialog), und der Dialog übernimmt sie
aus der Auswahl nur ohne Zeichnung. Abnahme: Kundenaufgabe B an Besenhalter
Fläche 3 und Druckschale Fläche 236 nimmt genau 20 · 10 · 3 = 600 mm³ ab
(± 0,5 %), ohne Warnung.

### F3 — Falsches Ergebnis: Eine Ecke verrunden streckt das bemaßte Rechteck

Sonde `b1_verrunden.py`, Protokoll `b1_verrunden.txt`; im Fenster
`a2_platte.py` → Körper 80 × **55** × 4 statt 80 × 50 × 4.

Weg (Kundenaufgabe A): Rechteck mit getipptem 80 × 50, dann *Verrunden*
(F) an einer Ecke, R 5. Ergebnis: Die Platte wird **55 mm** breit und wandert
um 3,2 mm nach unten; mit Fase 5 sind es 52,8 mm, mit dem Klick (Vorgabe R 2)
52 mm. Nur ein **unbemaßtes** Rechteck bleibt 80 × 50. Der Operationsdialog
zeigt danach „Breite 55,00 mm" — wer nicht nachrechnet, druckt es.

Ursache: `edit.fillet` und `edit.chamfer` kürzen beide Linien bis zum
Berührpunkt, lassen aber die Längenbedingung der gekürzten Seite stehen
(`_without_corner_joint`, `app/core/sketch/edit.py:1257–1266` und
`1316–1324`). Aus „Seite = 50" wird „Reststück = 50", und der Löser zieht die
Seite auf 55. Trimmen und Verlängern haben genau diesen Fehler schon gehabt
und behoben (Bericht `skizze.md`, B4) — Verrunden und Fase nicht.

Umbau: Die Längenbedingung einer gekürzten Seite wird zu einem Maß zwischen
dem unberührten Ende und der verlängerten Nachbarseite (virtuelle Ecke, wie
Fusion es tut). Das braucht „Punkt auf Linie" aus P6.6b; bis dahin fällt die
Längenbedingung wie bei B4 weg, und die Zeile sagt ehrlich „noch ein Maß
fehlt". Abnahme: Rechteck 80 × 50 getippt, R 5 an einer Ecke → Hülle der
Zeichnung (0 | 0)–(80 | 50) auf 10⁻⁶, Körper 80 × 50 × 4.

## Die vier Kundenaufgaben, gemessen gegen Fusion

Solidon gemessen im echten Fenster (Protokolle `a2_platte.txt`,
`b3_broomholdervcd_d35mm.txt`, `c1_dreh_l.txt`); Fusion aus Wissen, so wie
ein geübter Nutzer es ohne Menüsuche tut. „Zeit" ist geschätzt für einen
Kunden ohne Vorwissen (je Klick 1,5 s, je Taste 0,4 s, je „?" 20 s Suchen),
dazu gemessene Rechenzeit.

| Aufgabe | Solidon Ist | Ergebnis Solidon | Fusion (Wissen) | Solidon Soll |
|---|---|---|---|---|
| **A** Platte 80 × 50 × 4, 4 × Ø 4, Langloch, Ecke R 5 | 15 K, 17 T, 1 ?, 6,9 s Rechnen → ≈ 55 s | **falsch**: 80 × 55 (F3); Löcher und Langloch nur über das Raster bemaßt, Abstand zum Rand nicht bemaßbar | ≈ 20 K, 35 T (Rechteck, 4 Kreise, 4 Maße, Muster, Langloch, Extrusion, 3D-Verrundung) → ≈ 45 s | 13 K, 16 T, 0 ?; richtiges Maß; Lochabstand als Zahl |
| **B** Aussparung 20 × 10 × 3 mittig auf Besenhalter (STL), dann 25 lang | 7 K, 9 T, 1 ?, 5,2 s → ≈ 35 s; ändern 3 K, 2 T, 1 W | **falsch**: schneidet ins Leere (F2); „Länge 25" streckt auch die Breite auf 12,5 | Mesh muss erst in einen Körper umgewandelt werden (bei 60 000 Dreiecken nicht sinnvoll) — **Fusion kann die Aufgabe am STL praktisch nicht**; am exakten Teil ≈ 9 K, 11 T, Ändern 3 K, 3 T | 6 K, 8 T, 0 ?; Ändern 3 K, 3 T (Maßkarte im Bild) |
| **C** Profil drehen, dann 5 mm verschieben | 7 K, 10 T, 1 ?; verschieben 9 K, 1 W, 1 ? | richtig, aber nur um die feste senkrechte Achse durch den Ursprung; Verschieben nur per Ziehen am Raster | 8 K, 10 T (Achse frei wählbar); verschieben 3 K, 3 T (Maß zur Achse ändern) | 7 K, 10 T, Achse sichtbar und wählbar; verschieben 3 K, 2 T |
| **D** L-Profil 40 hoch, dann 60, dann eine Seite halbieren | 13 K, 6 T; 60: 3 K, 2 T, 1 W; halbieren 5 K, 1 W, 1 ? | richtig (Raster 2 mm vorher gesetzt) | ≈ 9 K, 14 T; 60: 2 K, 2 T; halbieren 3 K, 3 T | 11 K, 6 T; 60: 2 K, 2 T; halbieren 3 K, 3 T |

**Was Solidon dabei besser kann als Fusion** — und was im Umbau bleiben muss:
das Raster macht runde Zahlen ohne ein einziges Maß (Aufgabe A und D sind
mit Klicks auf das 2-mm-Raster schneller als in Fusion), die Tasche geht
**direkt ins STL** (Fusion verlangt dort eine Umwandlung), und das Hochziehen
mit dem Pfeil in der Querschau zeigt die Höhe am Zeiger. Der Umbau darf diese
drei nicht verlieren.

**Was Solidon schlechter kann:** alles, was eine Zahl **relativ zu etwas
anderem** braucht — Abstand eines Lochs zur Kante, Mitte einer Fläche,
Abstand eines Drehprofils zur Achse, eine Seite eines schon gezeichneten
Umrisses. Dafür fehlen Werkzeuge (siehe 1.4) und Anzeigen (Maße am
gezeichneten Element).

## 0 Erstellen — aus der Zeichnung wird ein Körper

### 0.1 Ist, Klick für Klick (freie Zeichnung, leere Szene)

| # | Kunde sieht | Kunde tut | Folge |
|---|---|---|---|
| 1 | geschlossener Umriss; unten *Hochziehen*, *Abtragen* (grau), *Fertig* mit kleinem Pfeil, *Verwerfen*; oben im Bild die Karte „Zum Ziehen mit der Maus: Vorder- oder Seitenansicht wählen. Abtragen braucht zusätzlich einen bearbeitbaren Körper." | *Fertig* (1 K) **oder** *Hochziehen* (1 K) | Skizzenmodus endet, Dialog „Grundform hochziehen" öffnet |
| 2 | Dialog (Bild `a2_dialog_hochziehen.png`): „Grundform: Rechteck" (grau), **Länge 80** (Fokus!), Breite, Höhe 10, „Skizze 13 Elemente · 10 Freiheitsgrade frei", „Art: Grundform hochziehen", *Weitere Einstellungen* | ins Höhenfeld klicken (1 K), Zahl tippen (1–2 T) | Vorschau im Bild |
| 3 | Knopf „Grundform hochziehen" | 1 K | Körper steht, ein Schritt im Verlauf; 6,9 s bis still (Platte mit 4 Löchern, exakter Kern) |

**Summe:** 3 K + 2 T vom geschlossenen Umriss bis zum Körper; mit dem
Ziehgriff (Querschau wählen, am Umriss ziehen, Dialog bestätigen) ebenso
viele — die Regel `zeichenflaeche.md` hält das selbst fest („Der Zug kostet
dabei keinen Klick weniger").

**Fusion (Wissen):** *Sketch beenden* (1 K) oder direkt `E` (1 T) → Profil
anklicken (1 K; bei nur einem Profil vorgewählt) → Maß am Pfeil tippen
(2 T), Enter. 1–2 K, 3 T — kein zweites Fenster: die Werte stehen als kleine
Palette **und** als Zahl am Pfeil im Bild.

### 0.2 Befunde Erstellen

| Nr. | Schwere | Befund | Ursache (Datei:Zeile) | Umbau | Abnahme |
|---|---|---|---|---|---|
| E1 | **Sackgasse** | F1 oben: Hochziehen auf einer gewählten Fläche scheitert immer | `main_window.py:17255`, `ops.py:432` | siehe F1 | siehe F1 |
| E2 | **unverständlich** | *Fertig* verspricht eine Liste der Arten (Pfeil am Knopf; Regel `zeichenflaeche.md` „Fertig klappt die Arten direkt auf"), **zeigt sie aber nicht**: Ein Klick öffnet sofort den Dialog der Vorgabe. Gemessen am sichtbaren Fenster zweimal (`v1_bilder.txt`, `v2_fertig.txt`: Popup keines, danach Dialog „Grundform hochziehen", auch mit 120 ms zwischen Drücken und Loslassen). Ein isolierter `QPushButton` mit Menü klappt unter denselben Bedingungen auf (`v3_qtmenu.py`) — der Fehler sitzt im Aufbau des Fensters, die genaue Ursache ist nicht isoliert. Dort sendet Qt `clicked` außerdem **auch nach** dem Schließen des Menüs; weil `clicked` an `finish_sketch` hängt, öffnete selbst ein Esc im Menü den Dialog. | `main_window.py:2721–2741` (`done.clicked` und `setMenu` am selben Knopf), `_update_sketch_actions` 9615 | Ein Knopf, eine Bedeutung: *Fertig* schließt mit der Vorgabe (so tut er es heute schon), die Arten stehen als eigene Knöpfe daneben (Soll 0.4). Kein `setMenu` am Hauptknopf. | Ein Klick auf *Fertig* löst genau eine Handlung aus; geprüft mit `QTest.mousePress`/`mouseRelease` am sichtbaren Knopf. |
| E3 | **unverständlich** | Der Dialog nach einer **Zeichnung** spricht von einer Grundform: „Grundform: Rechteck" bei einem Kreis, einem L oder einer Platte mit Löchern (`b5_dialog_hochziehen_flaeche.png`, `c1_dialog_L.png`); „Länge"/„Breite" strecken die ganze Zeichnung **proportional** (Aufgabe B: Länge 25 macht die Breite 12,5), der Fokus steht auf **Länge** statt auf Höhe, „1 Elemente · 2 Freiheitsgrade frei". Der Beschreibungssatz sagt „geht als exakte Kurve in den Kern". | `SketchExtrudeParams` `ops.py:353–447` (Grundform/Länge/Breite vorn, `sketch` hinten), `op_dialog.follow_sketch` | Mit Zeichnung zeigt der Dialog nur **Höhe** (Fokus, markiert), Richtung (nach oben · nach unten · beidseitig) und Ergebnis (neuer Körper · anfügen · abziehen). Grundform/Länge/Breite verschwinden (`depends_on` „keine Zeichnung"). Titel „Hochziehen". Zusammenfassung „4 Linien, geschlossen" statt Freiheitsgraden. | Dialog mit Zeichnung: vorn ≤ 3 Felder, Fokus im Höhenfeld; das Wort „Grundform" steht nicht darin. |
| E4 | **umständlich** | Kein „anfügen": `sketch_extrude` erzeugt **immer** einen neuen Körper (`consumes=0, produces=1`, `ops.py:458–460`). Ein Zapfen auf einer Platte ist danach ein zweiter, überlappender Körper; wer einen Körper will, muss *Vereinigen* finden. Fusion bietet „Verbinden / Ausschneiden / Neuer Körper" im selben Dialog und wählt vor, was die Lage nahelegt. | `ops.py:452–487` | Ergebnis-Feld wie E3; Vorgabe: berührt oder überlappt das Profil den Zielkörper (Abschnitt 7) → anfügen, sonst neuer Körper. Ein Schritt mit Eingang (wie `sketch_pocket`), ein Undo. | Zylinder auf die Oberseite einer Platte: danach **ein** Körper im Objektbaum, ein Schritt im Verlauf. |
| E5 | **umständlich** | Keine Richtung, kein beidseitig beim Hochziehen; „Durchgehend" der Tasche steht hinter *Weitere Einstellungen* (`ops.py:584`, `placement="advanced"`), obwohl es für Löcher der häufigste Fall ist. „Bis zur Fläche" gibt es nur beim Hochziehen, nicht bei der Tasche. | `ops.py:353–447`, `494–615` | Höhe/Tiefe als **eine** Zeile mit Umschalter „Maß · bis Fläche · durch alles"; beidseitig als Richtungswahl. | Loch durch eine 4-mm-Platte: 1 K (durch alles) statt 3 K (Klappe, Haken, zurück). |
| E6 | **Sackgasse** | Eine Zeichnung speist genau **eine** Operation. Wer die Außenkontur hochziehen **und** eine innere Kontur als Tasche will (Fusion: eine Skizze, zwei Features), zeichnet zweimal. „Aus Skizze erzeugen …" im Menü *Erzeugen* nimmt **keine** vorhandene Zeichnung, sondern öffnet einen Grundform-Dialog (Rechteck 40 × 20). „Zeichnung hochziehen" im selben Menü liest SVG/DXF ein — wer „Zeichnen" sucht, landet dort; einen Eintrag *Zeichnen* hat das Menü nicht (`e1_menue.txt`). | `registry.py:465` (`VariantGroup`), §30.1 („Die Skizze lebt als Parameterwert der Operation") | Bauplanfrage an Robert (Entscheidungen, Nr. 2). Sofort: „Aus Skizze erzeugen …" heißt „Grundform hochziehen oder drehen …", „Zeichnung hochziehen" heißt „SVG oder DXF hochziehen …", und *Erzeugen → Zeichnen* kommt dazu. | Außen- und Innenkontur aus einer Zeichnung in 2 Schritten ohne Neuzeichnen; „Zeichnen" in Menü und Befehlspalette führt in den Zeichenmodus. |
| E7 | **unverständlich** | Mehrere Umrisse: Vorgabe „alle werden ein Körper" (`region=0`); eine einzelne Insel wählt man als **Nummer** hinter *Weitere Einstellungen* („Region 0–64", `ops.py:421–430`). Welche Nummer welcher Umriss ist, zeigt nichts. | ebd. | Umrisse im Bild anklickbar (Fusion: Profil anklicken, Strg für mehrere); das Nummernfeld verschwindet aus der Oberfläche. | Zwei getrennte Rechtecke, eines hochziehen: 1 K auf den Umriss. |
| E8 | **unverständlich** | Drehkörper: Die Achse ist immer die senkrechte durch den Ursprung (`ops.py:973–1001`), im Bild nirgends gezeigt; „Abstand zur Achse" steht mit Zeichnung vorn und **wirkt nicht** (Feld-Doku: „der Abstand oben gilt dann nicht"). Eine gezeichnete Linie als Achse geht nicht, eine waagerechte Achse auch nicht. | `SketchRevolveParams` `ops.py:886–970` | Achse als Hilfslinie in der Zeichnung wählbar (Vorgabe Z-Achse, im Bild gestrichelt mit dem Wort „Drehachse"); „Abstand zur Achse" nur ohne Zeichnung. Hängt an P6.5 (Schnitt durch Drehen braucht dieselbe Achse). | Profil + Achse gezeichnet → Drehkörper um diese Achse; kein Feld „Abstand" mit Zeichnung. |
| E9 | **kosmetisch** | Die Karte oben sagt „… Abtragen braucht zusätzlich einen bearbeitbaren Körper." auch in einem **leeren Projekt**. | `_update_sketch_hint` `main_window.py:9807–9816` | Satzteil nur, wenn ein Körper in der Szene liegt. | Leeres Projekt: Karte ohne „Abtragen". |

### 0.3 Grundkörper als Vergleich

`Erzeugen → Grundformen → Quader anlegen` (3 K) → Dialog mit Breite 40,
Tiefe 30, Höhe 10 (je Feld 1 K + 2 T) → *Quader anlegen* (1 K). Für
80 × 50 × 4: **7 K, 6 T**, ohne Zeichenmodus. Ungefähr so lang wie der
Zeichenweg (Zeichnen, Karte, R, Klick, 80 Tab 50 Enter, Hochziehen, Höhe, OK
= 6 K, 9 T); am Quader lassen sich aber keine Löcher im selben Schritt
anlegen. Kein Befund, aber das Maß für das Soll: **Der Zeichenweg für eine
Platte darf nicht länger sein als der Grundkörper-Dialog.**

### 0.4 Soll-Ablauf Erstellen

1. Umriss geschlossen → unten stehen **drei Knöpfe mit Wort und Zeichen**:
   *Hochziehen* · *Abziehen* (nur mit Zielkörper, sonst ausgeblendet) ·
   *Drehen*; daneben *Mehr …* (Führen, Überblenden, Lochfeld) und *Fertig*.
2. *Hochziehen* **bleibt im Bild**: Pfeil am Umriss, Zahl am Zeiger, Fokus im
   Zahlenfeld (für die Querschau schon gebaut: `DragValueBar.anchor`,
   `continue_sketch_pull`), kleine Palette daneben mit Richtung und Ergebnis.
   Enter übernimmt als **ein** Schritt, Esc bricht ab (dieselben
   Entwurfsregeln wie §18.11). Die Kamera kippt dafür von selbst schräg,
   damit der Pfeil zu sehen ist (Fusion tut das beim Extrudieren).
3. Kein zweites Fenster; der Dialog bleibt nur für *Mehr …*.

Soll-Zählung: Umriss → Körper **1 K + 2 T** (heute 3 K + 2 T); Tasche 1 K +
2 T; Drehen 2 K (Knopf, Achse bestätigen).

## 1 Zeichnen beginnen

### 1.1 Einstiege, Ist gezählt

| Ausgangslage | Ist (Klicks bis zum ersten Werkzeug) | Fusion (Wissen) | Beobachtet |
|---|---|---|---|
| Startbildschirm | *Neues Projekt* → *Zeichnen* (Werkzeugleiste oben) → Ebenenkarte: **3 K** | *Neues Design* ist schon offen → *Skizze erstellen* → Ebene: 2 K | Der Startbildschirm nennt „Zeichnen" nirgends; Weg 2 steht dort nur als geführte Tour (`start_screen.py:855–980`). |
| Leeres Projekt | *Zeichnen* → Karte: **2 K** (oder *Zeichnen* + Taste 1) | 2 K | Bild `v1_01_zeichnen_leer.png`: vier Karten mitten über dem Raster, Satz „Worauf gezeichnet wird. Die Ziffern 1, 2 und 3 wechseln direkt." — gut. |
| Fläche eines Körpers (Netz oder exakt) | Fläche anklicken → *Zeichnen*: **2 K**; oder Rechtsklick → „Auf dieser Fläche zeichnen": 2 K | Fläche anklicken → *Skizze erstellen*: 2 K | Das **Auswahlfenster** der Fläche bietet nur „Baustein einsetzen …" (`b3_broomholdervcd_d35mm.txt`), kein Zeichnen — obwohl §2.6 dort „den kürzesten Weg vom Sehen zum Tun" verspricht. Im Zeichenmodus bleibt die Meldung der Flächenauswahl stehen: „Der Griff versetzt die gewählte Fläche entlang ihrer Normalen." — einen solchen Griff gibt es dort nicht. |
| Körper gewählt, kein Merkmal | *Zeichnen* → Karten wie im leeren Projekt | Fusion fragt die Ebene ebenso | Der gewählte Körper spielt keine Rolle (Abschnitt 7). |
| *Neue Ebene* | Karte *Neue Ebene …* oder letzter Eintrag im Ebenenfeld → Dialog (Art, Basis, Abstand) → *Übernehmen*: **4 K + 2 T** | *Konstruieren → Versatzebene* → Fläche → Zahl am Pfeil: 3 K + 2 T | Im Bild steht die Ebene schon beim Einstellen — gut. |

**Befunde Einstieg**

| Nr. | Schwere | Befund | Ursache | Umbau | Abnahme |
|---|---|---|---|---|---|
| B1 | umständlich | Startbildschirm ohne „Neu zeichnen" | `start_screen.py:855–870` | Dritter großer Knopf „Neu zeichnen" (leeres Projekt **und** Zeichenmodus auf der Draufsicht) | Startbildschirm → erstes Werkzeug in 1 K |
| B2 | unverständlich | Auswahlfenster der Fläche ohne *Hier zeichnen* und ohne *Aussparung* | `panels.py:5285` ff., Handlungen aus `perceive/actions.actions_for` | Zwei Zeilen an jeder ebenen Fläche: *Hier zeichnen* und *Loch oder Aussparung zeichnen …* (Zeichenmodus mit Ziel „abziehen") | „Ich will hier ein Loch in dieser Form": Fläche anklicken, 1 K im Auswahlfenster |
| B3 | kosmetisch | Veraltete Meldung zum Flächengriff bleibt im Zeichenmodus stehen | `start_sketch` räumt die Meldung nicht (`main_window.py:9258–9281`) | Beim Betreten die Meldung leeren | Meldung leer nach dem Betreten |
| B4 | umständlich | Ebenenfeld mit **allen** ebenen Flächen **aller** Körper: 41 Einträge am Besenhalter, 98 bei drei Teilen, 234 an der Druckschale (`b2_modelle.txt`, `d1_quer.txt`) | `_drawable_faces` `main_window.py:8841–8881` | Nur Flächen des Zielkörpers (Abschnitt 7), höchstens die acht größten, dazu „Fläche im Bild anklicken" | ≤ 12 Einträge in jedem Fall |

### 1.2 Werkzeuge, Maßeingabe, Fang — Ist

Gemessen in `a1_start.txt`, `a2_platte.txt`, `v1_bilder.txt`:

- **Rechteck** (R): zwei Ecken, oder erste Ecke und „80 Tab 50 Enter" —
  7 Tasten, gut. **Es gibt kein Rechteck von der Mitte aus** und kein
  Dreipunkt-Rechteck. Fusion: 2-Punkt, 3-Punkt, Mittelpunkt.
- **Kreis** (C): Mitte und Rand, oder Mitte und „8 Enter". Kein 2- oder
  3-Punkt-Kreis.
- **Bogen** (A): nur Anfang, Ende, Wölbung. Kein Mittelpunkt-Bogen, **kein
  tangentialer Bogen** am Ende einer Linie — der häufigste Bogen beim
  Zeichnen eines Profils.
- **Linie/Linienzug** (L): läuft weiter bis Esc; Maß tippbar, Richtung aus
  der Hand, bis 5 Grad auf die Achse gezogen. Gut.
- **Langloch** (G): Mitte–Mitte, Breite aus der Leiste. **Vieleck** (V):
  Mitte und Ecke. **Lochkreis**, **Lochraster**: gut, aber ohne Kürzel.
- **Ziehen statt klicken** (Gewohnheit aus Paint und Tinkercad): Ein Zug
  mit dem Rechteckwerkzeug zeichnet **nichts und verschiebt die Ansicht**
  (`v1_bilder.txt`: der Ursprung wandert von Bildpunkt 1706/570 nach
  1788/488, kein Element, kein ausstehender Klick). Links-Ziehen heißt in
  der Solidon-Navigation „verschieben" (§2.9) — im Zeichenmodus die falsche
  Vorgabe.
- **Raster beim Betreten**: 20 mm (Fenster 1600 × 1000) bzw. 10 mm
  (maximiert, 3413 Bildpunkte breit). Ein Loch 6 mm vom Rand ist so nicht
  anklickbar; die Klicks bei 6/6 und 74/44 landeten auf den
  **Plattenecken**, das Langloch von 30/25 nach 50/25 wurde abgelehnt
  („Die beiden Klicks liegen aufeinander"), weil beide Klicks auf denselben
  Rasterpunkt fielen (`a1_start.txt`). Der Kunde muss zoomen oder die
  Rasterweite tippen; nichts sagt ihm das, und die Kamera passt sich der
  Zeichnung nie an („Die Kamera wird hier nicht bewegt",
  `main_window.py:9862–9865`).
- **Fang**: nur Raster und vorhandene Punkte (`_placement_target`,
  `sketch_editor.py:1155–1170`). **Kein Fang auf den Ursprung** (er ist kein
  Punkt der Zeichnung) — deshalb meldet ein am Ursprung begonnenes, voll
  getipptes Rechteck „noch 2 Maße fehlen". Kein Fang auf Linienmitten, auf
  eine Linie, auf Tangenten, keine Ausrichtungslinien zu anderen Punkten
  (Fusion zeigt gestrichelte Hilfslinien, sobald man waagerecht zu einem
  vorhandenen Punkt steht).
- **Bemaßen**: `D` verlangt **zwei vorher gewählte Punkte** und öffnet
  einen modalen Dialog (`request_constraint`, `sketch_editor.py:7065–7110`).
  Eine **Linie** anklicken und `D` drücken sagt nur „Dazu erst zwei Punkte
  auswählen." Es gibt **kein waagerechtes oder senkrechtes Maß** (nur die
  schräge Punkt-Punkt-Strecke, `_NEEDS`, `sketch_editor.py:5112`), **kein
  Maß Punkt–Linie** und **keinen Durchmesser an einem schon gezeichneten
  Kreis** („Ein Knopf, der sie nachträglich an einen bestehenden Kreis
  hängt, wäre ein eigener Bedienentwurf", `sketch_editor.py:5114–5121`).
  „Loch 6 mm vom Rand" ist damit **nicht bemaßbar** — nur über das Raster
  erreichbar.
- **Wie fest ist die Zeichnung**: rechts unten „Geschlossen · noch 10 Maße
  fehlen". Welche fehlen, zeigt nichts; Fusion färbt bestimmte Linien
  schwarz und freie blau.
- **Maße am gezeichneten Element**: nur getippte Maße stehen als Karte im
  Bild; ein gezeichnetes Rechteck zeigt keine Länge
  (`v1_03_rechteck_fertig.png`). Das Ebenenfeld heißt nach dem ersten Strich
  „Ansicht:" statt „Zeichenebene:" — dasselbe Feld wechselt still seine
  Bedeutung (`_refresh_plane_role`).

**Befunde Werkzeuge**

| Nr. | Schwere | Befund | Ursache | Umbau | Abnahme |
|---|---|---|---|---|---|
| W1 | **Sackgasse** | Abstand zu einer Kante, waagerechtes/senkrechtes Maß und Durchmesser eines vorhandenen Kreises sind nicht bemaßbar | Bedingungsarten in `solver._CONSTRAINT_TARGETS`, `_NEEDS` `sketch_editor.py:5112–5150` | **Bemaßen als Werkzeug** (D): ein oder zwei Elemente anklicken → Maß hängt am Zeiger → Klick legt es ab → Zahl tippen. Punkt–Linie, waagerecht/senkrecht nach Zugrichtung, Kreis → Durchmesser. Braucht neue Bedingungsarten (P6.6b „Punkt auf Linie", dazu waagerechter/senkrechter Abstand und Abstand Punkt–Linie). | Loch 6 mm von zwei Kanten: je Maß D, Klick Loch, Klick Kante, Klick ablegen, „6 Enter" = 3 K + 2 T; Durchmesser eines gezeichneten Kreises ändern: D, Klick Kreis, Klick, Zahl |
| W2 | umständlich | Kein Mittelpunkt-Rechteck, kein tangentialer Bogen, kein 3-Punkt-Kreis | Werkzeuggruppen `sketch_editor.py:5596–5620`, `place` 3079–3110 | Rechteck mit Umschalter „2 Ecken · Mitte" (R zweimal drücken), Bogen mit „3 Punkte · tangential"; tangentialer Bogen zusätzlich wie in Fusion durch Ziehen am Linienende | Aufgabe B: Rechteck mittig um die Flächenmitte mit 1 K + 5 T |
| W3 | unverständlich | Links-Ziehen verschiebt die Ansicht, statt zu zeichnen | Navigation §2.9 im Zeichenmodus unverändert; Weiche `on_body_drag` `viewport.py:16520–16590` | Mit Zeichenwerkzeug zeichnet Ziehen (Rechteck, Kreis, Linie von Druck bis Loslassen); verschoben wird mit Mitteltaste oder Leertaste+Ziehen; mit Auswählen heißt Ziehen Auswahl verschieben bzw. Rahmen aufziehen (M1) | Zug mit R über 30 × 30 mm erzeugt ein Rechteck 30 × 30 |
| W4 | umständlich | Raster und Zoom passen beim Betreten nicht zur Aufgabe; keine Einpassung nach dem ersten Element | `start_sketch` 9236–9247, `_redraw_sketch` 9862 | Nach dem ersten geschlossenen Umriss einmal auf die Zeichnung einpassen (danach nie wieder von selbst); im Statusfeld „Raster 10 mm · Rad zoomt feiner" | Aufgabe A ohne Rasterfeld: die Löcher bei 6 mm treffen nach dem Einpassen |
| W5 | unverständlich | Ursprung ist kein Fangpunkt; ein getipptes Rechteck am Ursprung meldet „noch 2 Maße fehlen" | `_placement_target` 1155 | Ursprung (auf einer Fläche: Flächenmitte) als fester Fangpunkt mit Deckung, im Bild als Punkt mit Wort „Mitte" auf Flächen | Rechteck am Ursprung, 80 Tab 50: „Bestimmt" |
| W6 | unverständlich | Welche Maße fehlen, zeigt nichts | `_status` 1989 ff. | Freie Elemente gestrichelt oder heller, bestimmte kräftig (Form **und** Farbe, Regel 18) | Rechteck ohne Maß: vier Linien als frei erkennbar |
| W7 | kosmetisch | Gezeichnete Längen stehen nicht am Element; das Ebenenfeld wechselt still zu „Ansicht:" | `measure_annotations`, `_refresh_plane_role` | Beim Überfahren Länge/Durchmesser als leise Karte; Ansicht und Zeichenebene als zwei getrennte Anzeigen | Zeiger über einer Linie zeigt ihre Länge |
| W8 | kosmetisch | Fünfzehn Werkzeuge nur als Zeichen (`v1_01_zeichnen_leer.png`), Lochkreis/Lochraster ohne Kürzel | Entscheidungen 14./16.09. | Wort unter den fünf häufigsten (Linie, Rechteck, Kreis, Bemaßen, Trimmen) | — |

## 2 Verschieben und Drehen

### 2.1 In der Skizze — Ist

Gemessen in `c1_dreh_l.txt` (Profil 5 mm verschieben):

| # | Kunde tut | Zählung | Beobachtet |
|---|---|---|---|
| 1 | Linie 1 anklicken, dann Linie 2, 3, 4 mit Strg | 4 K | **Keine Rahmenauswahl, kein Strg+A** (im Canvas gibt es keines von beiden). Ein Rechteck sind vier Klicks, eine Platte mit vier Löchern und Langloch zehn. |
| 2 | Auswahl greifen und 5 mm ziehen | 1 K (Zug) | Geht, auf das Raster gefangen. **Keine Zahl**: „um 5 mm nach rechts" ist nur über das Raster oder über den Trick *Rechtsklick auf eine Ecke → Koordinaten …* erreichbar (der Löser zieht die bemaßte Form mit). |
| 3 | Drehen | — | **Gibt es nicht.** Kein Drehen einer Auswahl, keine Winkelangabe. |
| 4 | Spiegeln | 1 K + Menü | Nur an der X- oder Y-Achse der Skizze und immer als Kopie (`edit.mirror`, `edit.py:378–394`); an einer gewählten Linie nicht. |
| 5 | Kopieren | — | Kein Kopieren/Einfügen, kein Muster außer Lochkreis/Lochraster; *Versetzen* macht eine versetzte Kopie. |
| 6 | Skalieren | — | Nur im Operationsdialog über „Länge"/„Breite", und dort proportional (E3). |

Fusion (Wissen): Rahmen aufziehen (1 Zug) → `M` (1 T) → Griff ziehen oder
„5" tippen (2 T) → OK (1 K): 2 K + 3 T, Drehen im selben Werkzeug.

### 2.2 Nach *Fertig* — Körper verschieben und drehen (aus dem Code, nicht gefahren)

Körper anklicken → unten *Bewegen* → Griff im Bild oder X/Y/Z tippen →
Enter: 2 K + 2–3 T, ein eigener Schritt `translate_object`
(`transform_bar.py:534–545`); Drehen um eine Hauptachse mit Winkel,
Skalieren als Faktor oder auf Maß. Das entspricht Fusions *Verschieben/
Kopieren* und ist in Ordnung. Zwei Punkte fallen auf: Der Körper aus einer
Zeichnung bekommt so **zwei** Stellen, an denen seine Lage steht (Zeichnung
und Verschiebeschritt), und wer die Zeichnung später öffnet, sieht sie am
alten Ort; und ein *Drehen* um eine beliebige Achse (Kante) gibt es nicht.

### 2.3 Die Skizze selbst verschieben oder auf eine andere Ebene legen

- Nach dem ersten Strich wählt das Ebenenfeld nur noch den **Blick**, nicht
  mehr die Ebene (`reflect_camera_view`, `sketch_editor.py:6730–6766`; das
  Wort davor wechselt von „Zeichenebene:" zu „Ansicht:"). Eine fertige
  Zeichnung von der Draufsicht auf eine Fläche zu legen, geht nicht; nur
  *Neue Ebene …* nimmt die Zeichnung mit — und nur auf eine Ebene, die von
  der jetzigen abgeleitet ist (`change_drawing_plane`).
- Die ganze Zeichnung verschieben = alles einzeln wählen (2.1) und ziehen.

**Befunde Verschieben/Drehen**

| Nr. | Schwere | Befund | Ursache | Umbau | Abnahme |
|---|---|---|---|---|---|
| M1 | umständlich | Keine Rahmenauswahl, kein Alles-Wählen | `mousePressEvent`/`_select_at` `sketch_editor.py:2767–2929` | Ziehen auf leerer Fläche mit *Auswählen* zieht einen Rahmen (links nach rechts: ganz drin, rechts nach links: berührt — wie Fusion und jedes CAD); Strg+A wählt alles | Platte mit 4 Löchern ganz wählen: 1 Zug statt 10 K |
| M2 | **Sackgasse** | Kein Drehen in der Skizze, kein Verschieben um eine Zahl | fehlt | Werkzeug *Verschieben/Drehen* (M) auf der Auswahl: Griff mit Pfeilen und Drehring (dieselbe Gestalt wie `render/gizmo.py`), Zahl am Zeiger, Enter übernimmt; mit Strg eine Kopie | Profil um 5 mm: Rahmen, M, „5 Enter" = 1 Zug + 3 T; um 30° drehen: Rahmen, M, Ring, „30 Enter" |
| M3 | umständlich | Spiegeln nur an den Achsen | `edit.mirror` 378 | Spiegeln an einer gewählten Linie (die zuletzt gewählte Linie ist die Achse); Achsen bleiben Vorgabe ohne Linie | Bohrungsbild an einer Mittellinie spiegeln: Auswahl + Linie + 1 K |
| M4 | unverständlich | Ebene einer vorhandenen Zeichnung nicht wechselbar | `reflect_camera_view`, `_plane_picked` 6696–6766 | Rechtsklick auf die Zeichnung → *Auf andere Ebene legen …* → Ebene oder Fläche anklicken; die Zeichnung behält ihre Maße | Zeichnung von der Draufsicht auf eine Deckfläche: 3 K |

## 3 Wegschneiden

### 3.1 In der Skizze

Trimmen (T) nimmt das angeklickte Stück bis zur nächsten Kreuzung weg,
Verlängern wächst bis zur nächsten Kante; Löschen über Entf, den Knopf
*Löschen* (erscheint erst mit Auswahl) oder das Kontextmenü **mit**
Auswahl. Gemessen (`d1_quer.txt`): Nach dem ersten Trimmschnitt wächst „noch
7 Maße fehlen" auf 9 und 11 — Trimmen gibt Bedingungen frei, ohne es zu
sagen. Fusion (Wissen) trimmt zusätzlich mit einem **Zug über mehrere
Stücke**; hier ist jeder Schnitt ein Klick. Ein Rechtsklick auf eine **nicht
gewählte** Linie bietet kein *Löschen*, nur vierzehn graue Bedingungen.

### 3.2 Am Körper — „ich will hier ein Loch in dieser Form rausschneiden"

Wie findet der Kunde den Weg? Heute: Fläche anklicken → im Auswahlfenster
steht **nichts** dazu (nur „Baustein einsetzen …") → er muss wissen, dass
*Zeichnen* oben links in der Werkzeugleiste auf der gewählten Fläche beginnt
(oder Rechtsklick → „Auf dieser Fläche zeichnen") → zeichnen → *Abtragen* →
Tiefe → *Tasche schneiden*: 5 K + Zeichnen + 2 T — und auf jeder Fläche,
deren Mitte nicht im Weltursprung liegt, **schneidet es ins Leere** (F2).

- *Durchgehend* steht hinter *Weitere Einstellungen* (E5); „bis Fläche"
  fehlt der Tasche ganz.
- Einen gezeichneten Körper abziehen: *Hochziehen* (neuer Körper) → beide
  wählen → *Abziehen* aus dem Menü: 2 Schritte, und die Tasche wäre
  dieselbe Handlung in einem.
- Der Tooltip von *Abtragen* sagt „Schneidet den Umriss aus dem
  **ausgewählten** Körper", genommen wird aber auch der Körper unter der
  Zeichnung (`_body_under_the_outline`) — zwei Regeln, eine davon verschwiegen.

**Befunde Wegschneiden**

| Nr. | Schwere | Befund | Ursache | Umbau | Abnahme |
|---|---|---|---|---|---|
| S1 | **falsches Ergebnis** | F2 | `ops.py:765–768`, `main_window.py:17255–17259` | siehe F2 | siehe F2 |
| S2 | unverständlich | Das Auswahlfenster einer Fläche bietet keinen Schnitt-Weg | wie B2 | wie B2 | wie B2 |
| S3 | umständlich | Trimmen nur Stück für Stück; Rechtsklick auf ungewählte Linie ohne *Löschen* | `cut_or_grow` 2850, `context_menu_at` 4090 | Trimmen auch als Zug über mehrere Stücke; Rechtsklick wählt das Element und bietet *Löschen*, *Trimmen*, *Hilfslinie* | Drei Überstände in einem Zug weg; Löschen per Rechtsklick in 2 K |
| S4 | unverständlich | Trimmen gibt Maße frei, ohne es zu sagen | `_rebuilt_line` `edit.py:425` (B4 der Skizzendurchsicht) | Zeile nach dem Trimmen: „Ein Maß fiel mit weg — die Linie ist jetzt kürzer." | Satz erscheint, wenn eine Längenbedingung fällt |

## 4 Bearbeiten

### 4.1 Ist, gezählt (`b3_…txt`, `c1_dreh_l.txt`)

| Vorhaben | Solidon Ist | Fusion (Wissen) |
|---|---|---|
| Höhe einer Extrusion ändern | Verlauf links (1 W) → Doppelklick (1 K) → Höhenfeld (1 K) → 2 T → OK (1 K): **3 K, 2 T, 1 W** | Doppelklick auf das Feature in der Zeitleiste oder am Körper → Pfeil ziehen oder Zahl → OK: 2 K, 2 T |
| Skizze wieder öffnen | Verlauf → Doppelklick → Dialog → *Zeichnen …* → Modus; nach dem Ändern *Fertig* → **derselbe Dialog noch einmal** → OK: **4 K + Änderung, 1 W** | Doppelklick auf die Skizze in der Zeitleiste → ändern → *Skizze beenden*: 2 K + Änderung |
| Ein getipptes Maß ändern | im Modus Doppelklick auf die Maßkarte → modaler Dialog → Zahl → OK: 2 K, 2 T | Doppelklick auf das Maß → Zahl direkt im Bild → Enter: 1 K, 3 T |
| Ein **gezeichnetes** (nicht getipptes) Maß ändern | geht nicht direkt — es gibt keins; erst zwei Punkte wählen, `D`, Zahl (W1) | wie oben, das Maß steht schon da oder ist in 3 K gesetzt |
| Vom Körper zum Schritt | Rechtsklick im Objektbaum → „Diesen Schritt ändern" (2 K) | Rechtsklick am Körper → *Feature bearbeiten* |
| Länge 20 → 25 im Dialog | „Länge 25" streckt die ganze Zeichnung proportional, **die Breite wird 12,5** (`b3_…txt`: Maße danach 25 und 12,5) | — |

Rückgängig im Modus: Strg+Z und der Knopf nehmen Zeichenschritte zurück, der
Eintrag im Menü *Bearbeiten* ist grau (gut, eine Taste, eine Bedeutung).
Nach *Fertig* und OK nimmt ein Strg+Z den ganzen Schritt samt Zeichnung;
Strg+Y bringt ihn wieder. Drei Mal Esc im Modus **verwirft** die Zeichnung
(„Zeichnung verworfen — Strg+Z holt sie zurück.", `d1_quer.txt`) — der
Rückweg ist da, aber nur, solange nichts anderes geschieht
(`restore_discarded_sketch`, `main_window.py:10397–10415`). Fusion verwirft
mit Esc nie eine Skizze.

Folgeschritte: Eine geänderte Zeichnung rechnet alles danach neu (§15). Wo
eine spätere Operation an einer Fläche hängt, die sich dabei teilt, ist die
Zuordnung offen (RM-188 P3.2, Registersatz im Bericht `skizze.md`) — in
dieser Abnahme nicht gesondert gefahren.

**Befunde Bearbeiten**

| Nr. | Schwere | Befund | Ursache | Umbau | Abnahme |
|---|---|---|---|---|---|
| R1 | umständlich | Wiederöffnen einer Skizze kostet einen Dialog hin **und** zurück | `edit_operation` → `SketchField.space_button` → `_draw_sketch_in_space` 15653; `finish_sketch` öffnet den Dialog erneut 10040 | Doppelklick auf einen Skizzenschritt im Verlauf (und auf die Maßkarte am Körper) öffnet **direkt** den Zeichenmodus; *Fertig* rechnet den Schritt ohne Dialog neu, wenn sich nur die Zeichnung geändert hat | Skizze öffnen, Maß ändern, fertig: 3 K + 2 T statt 6 K + 2 T |
| R2 | unverständlich | „Länge"/„Breite" im Dialog skalieren die Zeichnung proportional | `op_dialog.follow_sketch`, `edit.scaled` | Mit Zeichnung keine Längenfelder (E3); getippte Maße der Zeichnung stehen stattdessen als eigene Felder im Dialog („Rechteck-Länge 20") | Aufgabe B: 20 → 25 ändert nur die Länge |
| R3 | unverständlich | Maß ändern im Bild öffnet einen modalen Kasten | `change_constraint_value` 7351, `ExpressionDialog` | Zahl direkt in der Karte bearbeiten (Feld an Ort und Stelle, Enter/Esc) | Doppelklick, Zahl, Enter: 1 K + 3 T |
| R4 | umständlich | Kein Griff am fertigen Körper für die Höhe; der Flächengriff an der Deckfläche legt einen **neuen** Schritt an statt die Extrusion zu ändern — zwei Wege, die gleich aussehen und Verschiedenes tun | Flächengriff (`viewport` Versetzen der Fläche) gegen `edit_operation` | Klick auf die Deckfläche eines Skizzenkörpers bietet zuerst „Höhe ändern" (ändert den Schritt), erst danach „Fläche versetzen" | Deckfläche anklicken, ziehen: der Schritt `sketch_extrude` ändert seine Höhe, kein neuer Schritt |
| R5 | umständlich | Dreimal Esc verwirft die Zeichnung | `_escape` `main_window.py:8901–8909` | Esc legt nur Werkzeug und Auswahl ab; Verlassen nur über *Fertig* (behält) oder *Verwerfen* | Esc × 5 im Modus: Zeichnung bleibt |

## 5 Ansicht während des Zeichnens

| Frage | Ist | Beleg |
|---|---|---|
| Blick beim Start | senkrecht auf die Ebene, orthografisch, alle Körper durchscheinend | `start_sketch` 9219–9240, Bild `v1_01…png` |
| Drehen / Schwenken / Zoomen | wie außerhalb: rechts dreht, **links schiebt**, Rad zoomt auf den Zeiger; Einrasten innerhalb 10 Grad an Hauptansichten | §2.9, `_settle_sketch_view` |
| Zurück zur Draufsicht | Taste 1/2/3 oder Ebenenfeld; auf einer **Fläche** gibt es keine Taste — nur den Eintrag im Ebenenfeld; kein Knopf „senkrecht auf die Zeichnung" (Fusion: *Ausrichten auf*) | `PLANE_KEYS` 5476 |
| Schnitt / Durchsicht | Die Werkzeugleiste mit *Schnitt* ist im Modus ausgeblendet (`tools.setVisible(False)`, 9264); ein Körper vor der Zeichenebene verdeckt nur durchscheinend. Fusion hat dafür „Aufschneiden" in der Skizzenpalette. | `main_window.py:9260–9266` |
| Störende Körper ausblenden | nur über den Objektbaum (Rechtsklick → Ausblenden); alle Körper bleiben durchscheinend im Bild und in Ebenenfeld, Projizieren und Fang | Abschnitt 7 |
| Rasterweite | folgt dem Zoom (Auto), tippbar; 20 bzw. 10 mm beim Betreten | W4 |
| Lesbarkeit | Bedingungen rechts als „Deckung — Linie 1 Ende, Linie 2 Anfang"; Maßkarten nur für getippte Maße; auf dem 3413 Bildpunkte breiten Schirm nimmt die Zeichenleiste rund 885 × 150 Bildpunkte ein (ein Viertel der Breite), die Karte mit dem Hinweis steht **oben** in der Mitte, weit weg vom Zeiger (`v1_03_rechteck_fertig.png`) | Bild |
| 3D-Maus | nicht prüfbar (fremde Hardware) | — |

**Befunde Ansicht**

| Nr. | Schwere | Befund | Ursache | Umbau | Abnahme |
|---|---|---|---|---|---|
| V1 | umständlich | Kein Schnitt beim Zeichnen; ein Körper vor der Ebene verdeckt die Zeichnung | `main_window.py:9264` | Schalter „Aufschneiden" in der Zeichenleiste (Schnitt an der Zeichenebene, dieselbe Schnittebene wie §18.2) | Zeichnen auf einer inneren Bodenfläche eines Kastens: Wände davor aufgeschnitten mit 1 K |
| V2 | umständlich | Kein „senkrecht auf die Zeichnung" für Flächen und abgeleitete Ebenen | `PLANE_KEYS` nur für drei Grundebenen | Knopf und Taste (Pos1 zweimal oder eigene Taste) „Draufsicht auf die Zeichnung" für jede Ebene | Nach Drehen: 1 T zurück, auch auf einer Fläche |
| V3 | unverständlich | Hinweiskarte oben mittig, weit vom Geschehen; vier Textorte gleichzeitig (Karte oben, Kapsel über der Leiste, Zeile in der Leiste, Statusleiste ganz unten) | `show_sketch_action`, `show_sketch_selection`, `panel.status`, `statusBar` | **Ein** Ort für „was tut der nächste Klick" (am Zeiger oder direkt über der Leiste), einer für den Zustand; die Statusleiste schweigt im Modus | Im Modus höchstens zwei sichtbare Textzeilen |
| V4 | kosmetisch | Ansichtstasten 4–6 (Transparent, Perspektivisch, Orthografisch) wirken auch im Modus; 5 schaltet perspektivisch, obwohl die Zeichenebene orthografisch sein muss (aus dem Code, nicht gefahren) | Menü *Ansicht → Darstellung* | Im Modus Perspektive sperren oder 5/6 dort nicht binden | Taste 5 im Modus lässt die Projektion orthografisch |

## 6 Querschnitt: Rückmeldung, Esc/Enter, Kürzel, Fehler, Texte

### 6.1 Rechtsklick (`d1_quer.txt`)

| Wo | Menü heute |
|---|---|
| leere Stelle | vierzehn **graue** Bedingungen (Abstand … Konzentrisch), sonst nichts |
| Ecke eines Rechtecks | *Koordinaten …*, *Bedingung entfernen ▸ Deckung, Waagerecht*, dann die vierzehn grauen |
| Linie (nicht gewählt) | nur die vierzehn grauen — **kein Löschen** |

Fusion (Wissen): Rechtsklick öffnet ein Markierungsmenü mit *Wiederholen*,
*Löschen*, *Skizze beenden*, Linie, Rechteck, Kreis, Bemaßen, Trimmen —
das, was man gerade braucht, am Zeiger. Hier ist der Rechtsklick die
Bedingungsleiste noch einmal, und zwar ausgegraut: Das Konzept
`konzept-bedienung.md` Teil 4 hat genau das am 04.08. schon notiert, es
steht noch.

### 6.2 Esc und Enter

Esc: 1. beendet den Linienzug, 2. legt das Werkzeug ab, 3. **verwirft die
Zeichnung** (R5). Enter beendet nur eine Kurve oder bestätigt ein Maß; es
gibt kein „Enter = Fertig" und kein „Enter = Werkzeug wiederholen".

### 6.3 Kürzel gegen Fusion (Fusion aus Wissen)

| Taste | Fusion (Skizze) | Solidon (Skizze) | Urteil |
|---|---|---|---|
| L | Linie | Linie | gleich |
| R | Rechteck (2 Punkte) | Rechteck | gleich |
| C | Kreis (Mitte, Ø) | Kreis | gleich |
| A | Darstellung (kein Bogen) | Bogen | abweichend, harmlos |
| D | Bemaßen (Werkzeug) | Abstand — **nur mit zwei vorgewählten Punkten** | gleiche Taste, andere Bedienung (W1) |
| T | Trimmen | Trimmen | gleich |
| O | Versetzen (Werkzeug mit Zahl im Bild) | Versetzen der Auswahl um die Zahl aus einem Feld | ähnlich |
| X | Hilfsgeometrie umschalten | dasselbe | gleich |
| P | **Projizieren** | **Punkt** | **Widerspruch** — wer projizieren will, setzt einen Punkt |
| M | Verschieben/Kopieren | — (kein Werkzeug) | fehlt (M2) |
| S | Befehlssuche | Kurve (Spline) | abweichend; die Suche ist hier Strg+Umschalt+P |
| E | Extrudieren (auch aus der Skizze heraus) | — im Modus | fehlt (0.4) |
| F | Verrunden | Verrunden (Skizze) | gleich — aber F3 |
| Esc | Werkzeug ablegen, Skizze bleibt | dritte Stufe verwirft | abweichend (R5) |

### 6.4 Fehler als Vorschlag — was tatsächlich dasteht

| Lage | Satz | Urteil |
|---|---|---|
| Zwei Klicks landen auf demselben Rasterpunkt (Raster zu grob) | „Die beiden Klicks liegen aufeinander — der zweite bestimmt die Größe." | Der Kunde hat an zwei **verschiedenen** Stellen geklickt; der Satz nennt weder das Raster noch den Ausweg (zoomen oder Rasterweite). |
| Tasche ins Leere (F2) | „Der Schnitt hat nichts abgetragen — das Werkzeug liegt neben dem Körper. Position prüfen oder an einer Fläche ausrichten." | Ursache ist ein Fehler der Anwendung; „Position prüfen" führt zu Feldern hinter *Weitere Einstellungen*; kein Knopf. |
| Hochziehen auf der Fläche (F1) | „Diese Fläche liegt hinter der Skizze — von dort aus geht es nicht vorwärts." | Der Kunde hat keine Fläche gewählt, die „hinter" liegt — er hat auf ihr gezeichnet. |
| `D` ohne Auswahl | „Abstand: hält zwei Punkte auf einem festen Abstand. Dazu erst zwei Punkte auswählen." | verständlich, aber der Weg (Strg-Klick) fehlt im Satz; beim Rechteck will der Kunde eine **Linie** bemaßen. |

### 6.5 Texte, die ein Kunde ohne CAD nicht liest

„Freiheitsgrade" (Dialogzusammenfassung, Zeile), „Deckung — Linie 1 Ende,
Linie 2 Anfang" (Bedingungsliste), „Grundform" für eine Zeichnung,
„geht als exakte Kurve in den Kern", „Region", „Rotationskörper aufziehen",
„Zwischen zwei Umrissen aufspannen", „Lochfeld schneiden", „1 Elemente".
Nach der Erinnerung „kurze Texte" gehören sie in den Umbau, nicht in einen
eigenen Textgang.

**Befunde Querschnitt**

| Nr. | Schwere | Befund | Ursache | Umbau | Abnahme |
|---|---|---|---|---|---|
| Q1 | umständlich | Rechtsklick = graue Bedingungsliste | `context_menu_at` `sketch_editor.py:4090–4190` | Menü nach Lage: an einem Element *Löschen*, *Trimmen*, *Hilfslinie*, *Bemaßen*, passende Bedingungen (nur die möglichen); auf leerer Fläche *Werkzeug wiederholen*, *Rechteck*, *Kreis*, *Linie*, *Einpassen*, *Fertig* | kein grauer Eintrag im Rechtsklickmenü |
| Q2 | unverständlich | P ist Punkt statt Projizieren | `TOOL_KEYS` 5258 | P = Projizieren (wie Fusion), Punkt ohne Kürzel oder `.` | — |
| Q3 | unverständlich | Rastersatz beim Doppelklick-Fang | `_shape_refusal` | „Beide Klicks fielen auf denselben Rasterpunkt (Raster 20 mm) — hineinzoomen oder die Rasterweite kleiner stellen." | Satz nennt Raster und Ausweg |
| Q4 | kosmetisch | Fachwörter (6.5) | Texte in `sketch_editor.py`, `ops.py` | „Maße fehlen" statt Freiheitsgrade, „liegt auf" statt Deckung, „Hochziehen/Drehen/Führen/Überblenden" als Titel | Suchwort „Freiheitsgrad" kommt in sichtbaren Texten des Modus nicht mehr vor |

## 7 Robert-Vorgabe: Zeichnen gilt genau einem Körper

„Beim Zeichnen wäre es auch gut, wenn man nur einen Körper hat und nicht
alle — am besten den ausgewählten; wenn keiner ausgewählt ist, ist man beim
neu Zeichnen."

### 7.1 Ist, Klick für Klick (`d1_quer.txt`, drei Teile: Teppichclip exakt, Keil-Oberteil STL, Stift STL)

| # | Kunde tut | Was passiert | Stelle |
|---|---|---|---|
| 1 | Clip im Baum anklicken, *Zeichnen* | Ebenenkarten wie im leeren Projekt — der gewählte Körper ändert nichts; mit einer gewählten **Fläche** beginnt die Zeichnung dort | `start_sketch` `main_window.py:9118–9124` (`_selected_face_plane`) |
| 2 | Blick ins Bild | **alle drei** Körper durchscheinend, keiner ausgeblendet | `set_display_mode("transparent")` 9219–9220 gilt der ganzen Szene |
| 3 | Ebenenfeld aufklappen | **98 Einträge**: Grundebenen und jede ebene Fläche aller drei Körper | `_drawable_faces` 8841–8881, `_sketch_surroundings` 9014–9022 |
| 4 | *Projizieren* | **242** Elemente aus den Schnitten aller Körper, die die Ebene trifft | `project_bodies` `sketch_editor.py:1490–1532` läuft über `self._bodies` = alle Netze |
| 5 | *Abtragen* / *Fertig* über zwei Körpern | Ziel ist der gewählte Körper, sonst „der einzige unter dem Umriss" per Hüllquader; liegen zwei darunter: Absage „Unter der Zeichnung liegt kein bearbeitbarer Körper — einen auswählen." | `_body_under_the_outline` 9470–9519, `_pocket_target_problem` 9551–9574, Vorgabe bei *Fertig* 10044–10049 |
| 6 | Fertig ohne Körper darunter | neuer Körper — gut, das ist schon Roberts „neu zeichnen" | `finish_sketch` 10046 |

### 7.2 Soll-Ablauf

**Ein Körper gewählt (oder eine seiner Flächen/Merkmale):**

1. *Zeichnen* → der Zeichenmodus nennt den Körper in der Leiste („Zeichnen
   an: Clip") und bietet als Ebene seine größte obere Fläche vor, die drei
   Grundebenen daneben; eine gewählte Fläche gilt sofort.
2. Die **anderen** Körper treten zurück: 15 % Deckkraft, ohne Kanten, **nicht
   anklickbar**, nicht im Ebenenfeld, nicht im Fang, nicht in *Projizieren*.
   Ein Schalter in der Leiste „Andere ausblenden" blendet sie ganz aus; die
   Wahl wird gemerkt.
3. *Projizieren*, *Flächenkontur*, Fang auf Körperkanten, *Abziehen* und
   *Anfügen* (E4) gelten nur diesem Körper. *Abziehen* braucht keine zweite
   Auswahl und keine Hüllquader-Suche mehr.
4. *Fertig* stellt die vorige Darstellung wieder her.

**Nichts gewählt:** Karten mit Draufsicht/Vorder-/Seitenansicht; alle Körper
treten zurück (wie oben, nicht anklickbar), *Fertig* und *Hochziehen* legen
einen **neuen** Körper an; *Abziehen* ist ausgeblendet. Wer doch an einen
Körper will, klickt ihn im Modus an → Rückfrage in der Leiste „An Clip
zeichnen?" mit *Ja* (einmal gesagt, gilt für diese Zeichnung).

**Warum durchscheinend statt ausgeblendet als Vorgabe** (Fusion und Onshape
aus Wissen): Fusion blendet beim Skizzieren nichts aus; wer isolieren will,
wählt am Körper *Isolieren* (Rechtsklick), und die Skizzenpalette bietet
„Aufschneiden". Onshape zeigt alle Teile und lässt sie per Rechtsklick
ausblenden. Beide lassen die Nachbarn sichtbar, weil man an ihnen ausrichtet
(Deckel auf Dose, Halter an Wand). Solidons Kunden drucken oft mehrteilig
(Passungen §14, Bauplatten): ein ganz verschwundener Nachbar macht eine
Passung blind. Durchscheinend und nicht wählbar erfüllt Roberts Satz — „man
hat nur einen Körper" im Sinne von Auswahl, Fang, Ebenen und Ziel — ohne den
Zusammenhang zu verlieren; ganz ausblenden bleibt ein Klick. **Diese Wahl ist
eine Produktfrage** und steht deshalb unter „Entscheidungen" mit beiden
Varianten.

### 7.3 Randfälle

| Lage | Soll |
|---|---|
| Mehrere Körper gewählt | Keine stille Wahl (Regel 21): Die Leiste fragt „An welchem zeichnen?" mit den gewählten Namen als Knöpfen und „neu" |
| Merkmal (Bohrung, Kante) gewählt | dessen Körper; Ebene wie „Körper gewählt" (eine Bohrung hat keine Ebene) |
| Körper auf einer anderen Platte | Die Ansicht wechselt auf seine Platte (wie beim Anklicken im Baum), danach wie oben |
| Explosionsansicht aktiv | Die Explosion wird für den Modus aufgehoben und danach wiederhergestellt — Ebenen und Flächen liegen in Dokumentkoordinaten, gezeichnet auf einem verschobenen Bild landete die Zeichnung woanders |
| Rückkehr aus dem Verlauf („Skizze bearbeiten") | Zielkörper ist der des Schritts: bei *Tasche* `inputs[0]`, bei *Hochziehen* auf einer Fläche der Körper der Fläche, bei *Hochziehen* frei der erzeugte Körper selbst — der dann nicht als Nachbar zurücktritt |
| Zielkörper wird im Modus gelöscht (Agent, Fernsteuerung) | Leiste sagt es, Zeichnung bleibt, *Fertig* legt einen neuen Körper an |

### 7.4 Betroffene Stellen

`start_sketch` (Betreten, `main_window.py:9072–9281`), `finish_sketch`
(Verlassen, 9936–10049), `_drawable_faces` 8841, `_sketch_surroundings`
9000–9022, `_body_under_the_outline` 9470, `_pocket_target_problem` 9551,
`_update_sketch_actions`/`needed_inputs` 9605–9647, `_finish_sketch_as`
9649–9670, `SketchCanvas.project_bodies`/`take_face_outline`
(`sketch_editor.py:1490–1566`), Viewport: Anzeige je Körper statt
`set_display_mode` für alle (`viewport.py:7791`) und Auswahlsperre im Modus.

**Abnahme:** (1) Drei Teile, Clip gewählt, *Zeichnen*: Ebenenfeld ≤ 12
Einträge, alle vom Clip; *Projizieren* bringt nur Kanten des Clips;
Klick auf das Keil-Oberteil wählt nichts. (2) Nichts gewählt, Rechteck,
*Fertig*: vierter Körper, die drei alten unverändert. (3) Aus dem Verlauf
eine Tasche am Clip öffnen: Clip ist Ziel, die anderen treten zurück.

## 8 Priorisierte Umbauliste

Reihenfolge nach Schaden für den Kunden; jedes Paket ist für sich abnehmbar.
„Hängt an" nennt die laufenden Aufträge.

| Paket | Inhalt (Befunde) | Umfang | Hängt an / stößt an | Abnahme des Pakets |
|---|---|---|---|---|
| **Z0 — Falsche Ergebnisse, sofort** | F1 (Hochziehen auf Fläche), F2 (Tasche ins Leere), F3 Zwischenlösung (Längenmaß der gekürzten Seite fällt, Zeile sagt es), E2 (*Fertig* ohne Menü, eine Bedeutung), B3, E9 | S | F3 vollständig braucht „Punkt auf Linie" aus **P6.6b** (Agent `wt-p66` baut gerade Bedingungen im Skizzeneditor — dort anmelden, nicht parallel bauen). F1/F2 ändern die Vorbelegung in `run_operation`/`_from_selection`, die auch das Paket Dialoge berührt. | Die Sonden `b1_verrunden.py`, `b4_tasche_netz.py … 4`, `b5_aufbau.py … 4` als Fenstertests: Platte 80 × 50; −600 mm³ an Fläche 236; Zylinder Ø 8 × 10 an Fläche 236 |
| **Z1 — Ein Körper, ein Ziel** (Robert) | Abschnitt 7, B4, E4 (anfügen), B2/S2 (Auswahlfenster: *Hier zeichnen*, *Aussparung zeichnen*) | M | Z0 (die Zielkörper-Regel ersetzt die Vorbelegung aus der Auswahl). B2 fasst `FeaturePanel` an — dort baut **P6.2** (Fasen-Oberfläche) die Kantenzeile; Zeilen gemeinsam planen. | Abnahme 7.4 (1)–(3); Kundenaufgabe B in 5 K + 7 T |
| **Z2 — Erstellen im Bild** | Soll 0.4 (Hochziehen/Abziehen/Drehen als Knöpfe, Zahl am Pfeil, kein zweites Fenster), E3 (Dialog mit Zeichnung: 3 Felder), E5 (Richtung, beidseitig, durch alles/bis Fläche), E7 (Umriss anklicken statt Region-Nummer), E8 (Drehachse wählbar), R1 (Skizze direkt öffnen, *Fertig* ohne zweiten Dialog), R4 (Höhe am Körper ändert den Schritt) | L | **P6.5** (Schnitt durch Drehen/Pfad/Überblenden, `wt-p6c`) bringt drei neue Skizzen-Ops unter *Fertig/Mehr* und braucht dieselbe Achswahl wie E8 — Achse **einmal** bauen. Z1 (anfügen/abziehen braucht den Zielkörper). | Umriss → Körper 1 K + 2 T; Aufgabe D in 11 K + 6 T, 2 K + 2 T, 3 K + 3 T |
| **Z3 — Bemaßen und Fang** | W1 (Bemaßen-Werkzeug), W5 (Ursprung/Flächenmitte als Fangpunkt), W6, W7, R3 (Maß im Bild bearbeiten), Q3 | L | **P6.6b** liefert zuerst oder im selben Zug die Bedingungsarten (Punkt auf Linie, waagerechter/senkrechter Abstand, Abstand Punkt–Linie); keine neue `format_version` nötig (RM-175, Satz 5). | Aufgabe A mit Lochabständen **als Maß**: 6 mm von den Kanten, danach 6 → 8 ändern verschiebt alle vier |
| **Z4 — Auswählen, Verschieben, Drehen** | M1 (Rahmen, Strg+A), M2 (Verschieben/Drehen mit Zahl, Kopie mit Strg), M3 (Spiegeln an Linie), M4 (Zeichnung auf andere Ebene), S3, Q1, W3 (Ziehen zeichnet) | M | W3 weicht im Modus von §2.9 ab — Entscheidung Nr. 3. Die Werkzeugzeile darf 900 Bildpunkte nicht überschreiten (`test_the_sketch_area_fits_a_laptop_screen`); **P6.6a** (Ellipse, Splines) will dort ebenfalls Platz — Werkzeuggruppen mit Umschaltern gemeinsam entwerfen. | Aufgabe C „Profil 5 mm verschieben" in 1 Zug + 3 T; Rechtsklick ohne graue Einträge |
| **Z5 — Werkzeuge** | W2 (Mittelpunkt-Rechteck, tangentialer Bogen, 3-Punkt-Kreis), Q2 (P = Projizieren), W8 | M | P6.6a (gleiche Leiste) | Aufgabe B Rechteck mittig in 1 K + 5 T |
| **Z6 — Ansicht und Texte** | W4 (Einpassen nach dem ersten Umriss), V1 (Aufschneiden), V2, V3 (ein Textort), V4, Q4, B1 (Startbildschirm „Neu zeichnen"), E6-Umbenennungen und *Erzeugen → Zeichnen*, R5 (Esc verwirft nicht) | M | Handbuchseite „Zeichnen" ist **ein** Katalogschlüssel (Bericht `skizze.md`): nach Z2–Z6 einmal neu schreiben und übersetzen. Bild `sketch-mode.png` erst zum Release (`/erzeugen`). | Im Modus höchstens zwei Textzeilen; „Freiheitsgrad" in keinem sichtbaren Text |

**Was bleiben muss:** Rasterfang ohne Maß für runde Zahlen; getippt heißt
bemaßt; Tasche direkt ins Netz; Pfeil und Zahl am Zeiger in der Querschau;
Einladung der leeren Skizze mit Verweis; „Zeichnung verworfen — Strg+Z holt
sie zurück" als Rückweg für *Verwerfen*; Lochkreis und Lochraster.

## 9 Entscheidungen für Robert

1. **Nachbarkörper beim Zeichnen** (Abschnitt 7): (a) durchscheinend und
   nicht wählbar, Ausblenden als ein Klick — **Empfehlung**, weil Passungen
   und Ausrichten am Nachbarn sichtbar bleiben; (b) ganz ausgeblendet wie
   Fusions *Isolieren* — ruhiger, aber blind für den Nachbarn.
2. **Eine Zeichnung für mehrere Schritte** (E6): (a) „Zeichnung
   weiterverwenden" am Verlaufsschritt kopiert den Text in einen neuen
   Schritt — ohne Bauplanänderung, **Empfehlung für jetzt**; (b) Skizze als
   eigener Verlaufsschritt, auf den mehrere Operationen verweisen, wie in
   Fusion — braucht eine Änderung von §30.1 („Die Skizze lebt als
   Parameterwert") und eine Formatmigration.
3. **Links-Ziehen im Zeichenmodus** (W3): Mit einem Zeichenwerkzeug zeichnet
   Ziehen, verschoben wird mit Mitteltaste oder Leertaste — Abweichung von
   §2.9 nur im Modus. **Empfehlung ja**: die Zielgruppe kommt aus Slicern
   und Tinkercad, dort zieht man Formen auf.
4. **Esc verwirft nicht mehr** (R5): **Empfehlung ja**; *Verwerfen* bleibt
   der eine Weg, sein Rückweg über Strg+Z bleibt.
5. **Hochziehen ohne Dialog, mit Palette am Umriss** (0.4): Ihre Vorgabe vom
   02.09.2026 („bei Bestätigung sollen alle drei Werte noch änderbar sein",
   „unten im Feld wollen wir es nicht") bleibt erfüllt, wenn die Palette
   **am Umriss** steht und Höhe, Richtung und Ergebnis dort änderbar sind.
   Bitte bestätigen, dass die Palette den Dialog ersetzt.
6. **P = Projizieren** wie in Fusion statt Punkt (Q2).

## 10 Nicht geprüft

- 3D-Maus (fremde Hardware); HiDPI 150/200 % und ein 1366er Laptopschirm
  (hier nur 3413 × 1369 bei Skalierung 1 und ein verstecktes Fenster
  1600 × 1000); macOS und Linux.
- Fusion selbst (nicht startbar, siehe Messweg); alle Fusion-Zahlen aus
  Wissen.
- Folgeschritte nach Änderung einer Zeichnung, an deren Fläche eine spätere
  Operation hängt (RM-188 P3.2, bekannt offen).
- Wartezeiten nur nebenbei: STL-Import 6,9 s, STEP 16–17 s, Platte mit vier
  Löchern hochziehen 6,9 s bis still, Tasche im Netz 5,2 s — alle über 2 s;
  ob dabei Fortschritt mit *Abbrechen* steht (§2.8), gehört der Abnahme
  „Wartezeit".
- Körper verschieben/drehen nach *Fertig* (2.2) und Taste 5 im Modus (V4)
  nur aus dem Code gelesen.

## 11 Bildbelege und Sonden

Alle unter `F:\3D Druck.review-050\sonden\zeichnen\`:

| Datei | Zeigt |
|---|---|
| `v1_01_zeichnen_leer.png` | Zeichenmodus im leeren Projekt: vier Ebenenkarten mitten im Bild, Leiste unten mit fünfzehn Zeichen |
| `v1_02_rechteck_zweiter_klick_ausstehend.png`, `v1_03_rechteck_fertig.png` | Rechteck aus zwei echten Klicks; keine Längen am Rechteck, Hinweiskarte oben, rechts „Deckung — Linie 1 Ende …", das Feld heißt jetzt „Ansicht:" |
| `v1_04_nach_ziehen.png` | Nach einem Zug mit dem Rechteckwerkzeug: kein Rechteck, Ansicht verschoben (W3) |
| `a2_dialog_hochziehen.png` | Dialog nach *Fertig*: Grundform Rechteck, Fokus auf Länge, **Breite 55** (F3) |
| `b5_dialog_hochziehen_flaeche.png` | Hochziehen auf gewählter Fläche: „Bis zur Fläche" ist die eigene Fläche (F1), „Grundform Rechteck" bei einem Kreis |
| `b3_dialog_tasche.png`, `b3_dialog_aendern.png` | Taschendialog beim Anlegen und Ändern (X/Y/Oberkante hinter der Klappe, F2) |
| `c1_dialog_dreh.png`, `c1_dialog_L.png` | Drehkörper mit wirkungslosem „Abstand zur Achse"; L-Profil als „Rechteck" |

Sonden: `gerust.py` (Aufbau wie `build_application`, APPDATA isoliert,
Zeitgeber, eigenes Protokoll), `a1_start.py`, `a2_platte.py`,
`b1_verrunden.py`, `b2_modelle.py`, `b3_aussparung.py`, `b4_tasche_netz.py`,
`b5_aufbau.py`, `c1_dreh_l.py`, `d1_quer.py`, `e1_menue.py`, `v1_bilder.py`,
`v2_fertig.py`, `v3_qtmenu.py` — je ein Protokoll gleichen Namens. Alle Läufe
mit Exit 0 außer den ersten beiden Fassungen von `a1`/`a2` (Exit 9 durch
den eigenen Zeitgeber, Sonde endete ohne `os._exit`; danach berichtigt).
Kein Code der Anwendung wurde geändert.

**Registersätze (Vorschlag):**

- *„RM-neu (Zeichnen, Robert 23.09.2026): Drei falsche Ergebnisse auf dem
  Hauptweg — Hochziehen auf gewählter Fläche hält immer an (Bis zur Fläche
  = eigene Fläche), Tasche auf außermittiger Fläche schneidet ins Leere
  (doppelte Verschiebung X/Y), Verrunden/Fase strecken ein bemaßtes
  Rechteck (Längenmaß bleibt an der gekürzten Seite). Umbau Z0; Tests aus
  den Sonden b1, b4, b5."*
- *„RM-neu: Bedienumbau Zeichnen in sechs Paketen Z1–Z6 (Bericht
  zeichnen-bedienung.md); Z1/Z3 abgestimmt mit P6.6b, Z2 mit P6.5, Z4/Z5 mit
  P6.6a (Leistenbreite), B2 mit P6.2 (Auswahlfenster)."*
