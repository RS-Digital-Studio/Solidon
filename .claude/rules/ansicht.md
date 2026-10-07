---
description: "Der Viewport — Auswahl und Picks, Messen, Färbung, Schatten, Druckplatten, Bildpunkte, Mauszeiger, wann gemalt wird, Aufbau und Leistung, Renderstart, Bildprüfung; Griffe und Kamera stehen in eigenen Dateien"
paths:
  - "app/ui/viewport.py"
  - "app/ui/render/**/*.py"
  - "app/ui/qt_platform.py"
  - "app/ui/placement_flow.py"
  - "app/ui/overlay.py"
  - "app/ui/cursors.py"
  - "app/ui/analysis_bar.py"
  - "app/ui/section_bar.py"
  - "app/ui/split_bar.py"
  - "app/ui/transform_bar.py"
  - "app/ui/explode_bar.py"
  - "app/ui/scale_widget.py"
  - "app/ui/snapshots.py"
---

# Regeln für die Ansicht

Was im Viewport geschieht; `oberflaeche.md` lädt zusätzlich. Griffe:
`griffe.md`. Kamera, 3D-Maus, Einpassen und Kameravorgaben („Eine
Kameravorgabe dreht um den Blickpunkt, sie passt nicht ein“): `kamera.md`.
Skizzenstücke von `viewport.py`: `zeichenflaeche.md`. Messwerte und Anlässe:
`konzepte/begruendungen/regel-ansicht.md`.

## Die Auswahl hat eine Tiefe, und der Klick wandert durch sie

Stufen: nichts, Körper, Merkmal oder Kante (`Viewport.selection_depth`).
**Links wandert, rechts fragt.**

* **Links geht eine Stufe**: erst der Körper, dann das Merkmal — sonst ist ein
  Körper mit Bohrungen per Klick nicht wählbar. Nur der Klick wandert, nicht der
  Zug (`kamera.md`).
* **Rechts meint immer das Genaueste** (`_select_at(..., direct=True)`): Wer
  auf die störende Stelle zeigt, hängt an keiner Vorbedingung (§18.5). Die
  Operationen von Weg 1 stehen im Auswahlfenster; das Menü trägt davon nur
  *Entfernen* und *Vereinigen* (`grenzen.md`).
* **Außer er trifft eine Mehrfachauswahl**: Liegt der Zeiger auf einem von
  mehreren gewählten Körpern, bleibt die Auswahl, und das Menü gilt allen
  (`_on_right_click`, Entscheidung Robert) — im Objektbaum ebenso, wenn die
  Zeile schon markiert ist (`ObjectTree._on_context_menu`).
* **Ein offener Operationsdialog schaltet die Stufen ab**
  (`set_direct_picking`) — dort ist ein Klick eine Antwort.
* **Escape geht eine Stufe je Druck zurück**, in `MainWindow._escape` nach dem
  offenen Werkzeug — sonst ist die Tiefe eine Einbahnstraße.
* **Die Stufe wird aus der Auswahl gelesen, nie nebenher geführt** (sie kommt
  auch aus dem Objektbaum), und **vor** dem Senden: `objectPicked` setzt
  `_selected` synchron.
* **Ein Merkmalsklick am allein gewählten Körper meldet den Körper nicht noch
  einmal** (sonst eine Auswahlrunde je Klick): Die Ansicht wählt das Merkmal erst
  nach `featurePicked` und nur, wenn der Baum es nicht tat; mit Umschalt oder
  Strg bleibt die alte Folge.
* **Der Zeiger rechnet wie der Klick** (`_look_under_pointer` →
  `_click_target`, Auskunft `_would_pick_feature`), sonst verspricht er, was
  nicht eintritt.

### Und eine Kante gehört auf dieselbe Stufe

Erst der Körper, dann das Untergeordnete (Entscheidung Robert); `_goes_deeper`
beantwortet die Stufe für Merkmal und Kante.

* **Gemessen im Bild** (`EDGE_REACH_PIXELS`), gegen die **Strecken**, nicht die
  Punkte (Bögen aus `brep.edit.edge_points`); **bei gleichem Abstand gewinnt die
  nähere** (`render.edges.nearest_polyline`). Ein **Vorfilter misst gegen den
  Hüllquader der Kante**, nie gegen ihre Stützpunkte — zu viel durchlassen, nie
  zu wenig.
* **Der Körper gibt die Auswahlfarbe ab** (`highlighted_object()` ist `None`),
  sonst ist die Linie unsichtbar.
* **Eine neue Auswahlart fällt überall, wo eine andere entsteht** (`_drop_edge()`
  in `select`, `select_feature`, `_refresh_feature_selection`), **zählt in
  `selection_depth`** und **verschluckt keinen fremden Klick**
  (`_means_a_feature()`: Messen, Teilen, Skelett, Formen gehen vor). Umschalt
  und Strg meinen den Körper; eine Kante wird einzeln gewählt.
* **Der Zeiger fragt `_edge_under`**, die Bedingungen von `_edge_click`; die
  Rolle bleibt `feature`.
* **Rechts ohne Vorbedingung** (`_edge_click(direct=…)`); der Körper wird
  **vor** der Kante angesagt (ihre Handlungen lesen den Objektbaum); gesucht mit
  dem **Bildpunkt**, nicht über `_from_view`.
* **Die Lage einer Kante in Worten fragt der Kern** (`edges.edge_lie_of`): Die
  Mündung einer Querbohrung heißt „Senkrecht“.

### An der gewählten Kante stehen die Seiten der Fase

Die Marken legt der Kern (`edge_ops.chamfer_marks`) mit den Normalen der
Operation; ein Klick meldet nur (`chamferSidesSwapRequested`), das Fenster
schaltet den Haken im Merkmalfenster. Zweite Kodierung ist eine Ziffer („1 · …“,
„2 · …“, dazu die breitere Linie; Regel 18), die Statuszeile nennt beide
Flächen in Worten. Die Marke nimmt den Klick vor Kante und Fläche, **nur ihre
äußere Hälfte**; der Zeiger zeigt die Kantenrolle (`_set_hover_edge`).

### Ein Merkmal hat eine Reichweite

`_feature_at` misst gegen die **Dreiecke** des Merkmals
(`geom.mesh.distance_to_triangles`), nie gegen Mittel- oder Eckpunkte; die
Reichweite wächst mit der Diagonale (`FEATURE_REACH_SHARE`), weil im
dezimierten Netz gepickt wird (§18.9). Tests zielen auf die Bohrungswand
(`on_the_bore_wall`), nie auf die Achse; ein Merkmal ohne Dreiecke bleibt über
seinen Mittelpunkt erreichbar. Vorbereitet je Körper und Auswertung
(`_feature_geometry`), geleert in `show_scene`. **Jeder Klickpfad rechnet über
`_from_view` in die Szene zurück** (§25).

### Ein Klick ist eine Blickrichtung, kein Punkt

Senkrecht in eine Durchgangsbohrung trifft der Strahl nichts, daneben gewinnt
die Deckfläche. Gefragt wird der **Sichtstrahl** (`_pick_ray` → `_bore_aim`,
`bore_span`): Welche Öffnung durchquert er vor dem Auftreffpunkt (`until` —
sonst wählt die Vorderansicht Bohrungen hinter der Stirnfläche)?

* **Achsbereich aus den Dreiecken des Merkmals**, nicht aus `depth`; zurück kommt
  **ein Punkt auf der Achse**, an dem `_feature_inside` die Bohrung findet — nicht
  die Mitte des Durchtritts, die läge der Deckfläche näher.
* **Parallel zur Achse** hat die quadratische Gleichung keinen
  Leitkoeffizienten — nicht durch null teilen, sonst fehlt die Draufsicht.
* **Jede Öffnung rechnet gegen ihren Umriss**, nie gegen den Kreis ihres
  Durchmessers (Langloch: `_stadium_span`, Abstand zur Mittellinie).
* **Derselbe Aufruf** (`_aim_at`) für Links-, Rechtsklick und Zeiger; **nicht**
  beim Messen, Bemalen und Ziehen — dort ist die Oberfläche gemeint. Die
  Reichweite ist hier Zielhilfe, keine Grenze.

### Und wo kein Merkmal ist, ist trotzdem ein Körper

Trifft der Strahl in einer Öffnung gar nichts, wählt `_through_aim` den Körper
über seine **konvexe Hülle** (`geom.mesh.hull_planes`, `ray_span_in_hull`; in
`app/ui` gibt es kein `trimesh`). Hülle, nicht Hüllquader — ein Klick daneben
muss die Auswahl aufheben können (§18.5); die Kerbe eines L-Profils zählt mit.
Nur wenn sonst nichts traf, je Körper einmal (`_object_hulls`), als Stichprobe
(4096 Punkte plus die äußersten je Achsenrichtung), über Halbräume statt
Hüllnetz.

## Die Leertaste gehört dem, der sie braucht

Der Vergleich der Vorschau (`HoldToCompare`) hängt an der Anwendung und
nimmt die Taste nur, wo der Fokus kein Bedienelement trifft, das sie selbst
braucht (`answers_space`: Text, Haken, Knopf, Auswahlliste, Liste) — sonst
schaltete während jeder Vorschau in keinem Fenster ein Haken (RM-448).

## Messen

### Stellenwahl mit der Tastatur

Das Fadenkreuz der Oberflächenauswahl zeichnet der Renderer in festen
Bildmaßen: vier Arme, schwarze Unterlage und weiße Innenfläche, freie Mitte.
Die beiden Elemente bleiben bestehen und erhalten bei Bewegung oder
Kamerawechsel neue Punkte. Sie sind nicht pickbar. Ein einzelnes QWidget
von einem Bildpunkt am oberen Arm trägt Tastaturfokus und zugänglichen Namen;
beim Beenden kehrt sein Fokus in die Ansicht zurück.

Eine große Fachkarte darf bei Platzmangel den Rand des Körpers überdecken.
Dieser Ausweg gilt nur für diese Karte: Setzpunkt und Bewegungsgriff bleiben
frei, die kurzen Maßfelder behalten ihre Plätze außerhalb des Körpers.
Ein Platzmangel der Fachkarte schiebt nicht sämtliche Maße in eine Notreihe.

**Messen ist orthografisch, und zwar von selbst** (§18.1 — perspektivisch zielt
der Nutzer falsch): `MainWindow._on_measure_mode` schaltet beim Betreten um und
beim Verlassen zurück, nicht beim Wechsel der Messart; `settings.projection`
bleibt, das Häkchen folgt dem, was gilt; eine Wahl im Menü gewinnt und wird
Rückkehrziel (`action_projection`).

**Der Zeiger zeigt vor dem Klick, wohin der Kern fängt**
(`geom.measure.snap`):

* **Die Fangweite gehört in Bildpunkte** (`MEASURE_SNAP_PIXELS`):
  `_snap_radius_at` rechnet sie über `_pixels_per_mm_at` in Millimeter; ohne
  Bild `None`, dann gilt die Weite des Kerns.
* **Gefangen wird nur, was man sieht** (`visible_edges`, `corner_points`).
* **Die Marke rechnet wie der Klick** (`_preview_snap` → `_snap_for_measure`):
  ein Kreuz in der Bildebene (`_screen_axes`), feste Bildgröße
  (`SNAP_MARK_PIXELS`, `SNAP_DOT_PIXELS`); Winkelmessen bleibt bei der
  Merkmalssuche.
* **Die Fangart sagen Größe und `snap_sentence`** — nicht die Farbe (Regel 18),
  nicht die Statuszeile, kein Text in der Szene (`griffe.md`, „Was am Griff
  steht, ist ASCII“).
* **Die Marke geht** mit dem Zeiger, dem Werkzeug und jedem Szenenaufbau; Maße
  überleben die Auswertung.

## Was gefärbt wird

* **Die Auswahlfarbe gehört dem Genauesten**: Bei gewähltem Merkmal ist
  `highlighted_object()` `None`; `highlighted_faces()` nennt seine Dreiecke,
  auch unter Analysekarten (§19.1). Beide Auskünfte sind offscreen prüfbar.
  Baum und Statusleiste zeigen den Körper, die Beschriftung das Merkmal (Regel 18).
* **Marken nennen nur warnende Herkunft**: `compact=True` an `feature_label`
  und `measure_qualifier`; „gemessen“ an jeder Marke verdrängt Beschriftungen.
* **Befundmarken tragen `FINDING_COLOUR`, nie Auswahlfarbe**: *Stelle zeigen*
  wählt den Körper; gleichfarbige Ringe verschwinden. Flächenbefunde
  (`Finding.outline`, etwa Öffnungen) bekommen Umrandung und Textgrund für
  `FINDING_OUTLINE_MS`. Der Rand reist in `loader.moved_findings` und
  `cache._finding_to_cache`, nie in der Projektdatei.
* **Schweben halbtransparent, Auswahl deckend**: Schweben kündigt an.
  Über gewählten Merkmalen ändern sich nur Zeiger und Hinweis; Fläche und
  Beschriftung bleiben, auch bei Hover nach dem Klick.
* **Bohrungsmarken lassen Öffnungen frei**: Innenwände beidseitig durchscheinend,
  andere Merkmalsflächen beidseitig deckend.
* **Änderungsvorschauen besitzen die Modellfarben**: Orange nur entfernt,
  Blau nur hinzugekommen. Auswahl-/Schwebeflächen weichen bis Vorher oder
  Vorschauende; Baum, Statusleiste und Beschriftung halten die Auswahl.
* **Nur Sichtbares markieren**: Nach Auswertung bleibt der Körper gewählt,
  verschwundene Merkmale fallen auf ihn zurück; eindeutig zugeordnete
  Bausteinmerkmale übernehmen aktuelle `face_indices`.
* **Gegen das Szenennetz rechnen**, nie das Anzeigenetz;
  `FEATURE_PATCH_LIFT` hebt entlang der Normalen.
* **Analysekarten verdrängen Umgebungsverdeckung und Kontaktschatten** über
  `ambient_occlusion`/`contact_shadows`, offscreen prüfbar ohne Renderer.
* **Eine Karte behält ihre Farben am gewählten Körper** (`shows_face_colours`);
  nur Filamentfarben weichen der Auswahl.

## Schatten und Licht

* **Der Kontaktschatten ist selbst projiziert**, nie Schattenwurf des
  Renderers, und fällt schräg.
* **Er folgt der Kamera, weil das Frontlicht es tut** (`shadow_direction`);
  `_redraw_shadows` zieht nach am Zugende (`on_end`), je Schritt der 3D-Maus und
  je Kameravorgabe — nie an einem Renderer-Ereignis.
* **Er fällt auf die Fläche, auf der sein Körper steht** (`_shadow_catchers`:
  Platte und jeder Körper, dessen Oberkante nicht über seiner Unterkante liegt),
  geschnitten an deren Umriss (`clip_polygon`) und an der Platte **des Körpers**
  (`_bed_outline_for`, Kante aus `_bed_extent`; ohne gezeigten Bauraum wird
  nicht geschnitten).
* **Gerechnet je Körper, nicht je Auffangfläche**: der Umriss je Stück einmal auf
  seiner Unterkante (ebene Hülle über GEOS, als `base` an
  `shadow_outline_of`), dann nur verschoben — `ground` fällt in
  `shadow_points` als Summand heraus, die Klammer `maximum(…, 0)` greift dort
  nie. Die konvexe Hülle je Körper einmal (`_shadow_hull_of`), über
  `SHADOW_HULL_POINTS` als Stichprobe plus Extrempunkte in vierzehn Richtungen.
* **Ein Aktor je Körper**, fester Kapazität, nur neue Punkte
  (`_show_shadow_soups`), gemerkt in `_shadow_owners`; **jeder Zug zieht den
  Schatten mit** — am Griff `_drag_shadow`, frei `continue_body_drag_at`, beide
  über `set_position` am Aktor. Geworfen in einem Aufruf (`planar_outlines`,
  `shadow_soups` rein), über `SHADOW_PROJECTION_ABOVE` im `_ShadowWorker` — bis
  dahin bleibt der alte. Hüllen in Körperkoordinaten, Versatz beim Wurf.

### Zwei Werte hängen am Thema, und beide aus demselben Grund

Licht und Deckkraft wirken auf hellem und dunklem Grund verschieden; eine Zahl
stimmt nur für ein Thema. `HEADLIGHT`: Nur das Frontlicht (von fünf,
`LIGHT_KIT`) trifft die zugewandten Wände; auf dem dunkleren Körper des hellen
Themas hilft nur mehr Licht (0,45 statt 0,25). `SHADOW_OPACITY`: im hellen
Thema 0,03, so laut wie im dunklen (Entscheidung Robert). Ambient- und
Glanzanteil sind gemessen verworfen. **Falle:** Liest die Zeichenstelle die Konstante statt des gemerkten
Werts, ist das Paar wirkungslos, und ein Methodentest bleibt grün —
`test_viewport_decisions.py` hält je Paar Richtung, Setzen in `set_theme` und
Lesen beim Zeichnen.

## Was die Ansicht sich merkt

Darstellung, Schattierung und Projektion sind **Einstellungen** (drei
`QActionGroup`s mit Häkchen, `action_`-Methoden setzen, merken, speichern;
`_apply_settings` beim Start). Wer sie vorübergehend umstellt — Skizzenmodus,
Tiefenstufe der Platzierung — **leiht und gibt zurück**, auch bei Escape;
gespeichert wird das nicht.

**Durchsichtige Körper werden von hinten nach vorn gezeichnet**
(`_order_by_depth`, fernster Mittelpunkt zuerst — richtig für getrennte Körper),
obwohl pygfx reihenfolgeunabhängig mischt (`weighted_blend`). Die Ordnung hängt
an `_draw`, nicht an den Anlässen; sie merkt sich Kameralage und Körperliste;
sie geht über `set_draw_order`, ohne ein Element aufzugeben, und pygfx legt keine
eigene Reihenfolge darüber, weil die gemessen die Sortierung aufhöbe.
**`_scene_bounds` zählt nicht mit, was vorn liegt** (`GfxItem.in_front` aus
`keep_in_front`) — sonst rahmt *Alles zeigen* die Maßtinte statt des Modells.

**Die Druckplatte scheint durch, wenn etwas darunter liegt** — und nur dann
(`sunken_body`, gefragt an der Szene; Entscheidung Robert): Rückseite weg
(`culling = "back"`), `BED_SUNKEN_OPACITY` (0,45 wie *Transparent*) auf der
gefüllten Ebene (`_bed_surfaces`), neu gefragt je
Auswertung (`_apply_bed_transparency`), mitgezählt in der Tiefenordnung
(`sees_through`). Ganz aus: *Druckplatte zeigen* (Strg+Umschalt+D), gemerkt.

## Mehrere Druckplatten

Jede Platte hat ihren Nullpunkt (`arrange_bed`); `show_build_volume` zeichnet
ein Bett je Platte nach +X (`PLATE_GAP`, `plate_shift`), die erste bleibt, wo
sie ist. Die Elemente tragen die Plattennummer im Namen — die Adresse für
`item_of` und das Aufräumen.

* **Ein Klick wird zurückgerechnet** (`plate_at`, `_from_view` ganz oben in
  `_on_picked`), sonst setzt er auf Platte 2 eine Bettbreite daneben — stumm.
* **Ein Zug auf ein anderes Bett wechselt die Platte** (`across_plates`,
  `Viewport.dropped_on_plate`, `MainWindow._drag_params` → `plate` an
  *Verschieben*): Der Weg im Bild enthält die Strecke zwischen den Betten, die
  es in der Szene nicht gibt; ohne Umrechnung holt *Auf dem Bett halten* den
  Körper auf seine alte Platte zurück, und er springt.
* **Plattenversatz und Auseinanderziehen liegen zusammen in `_view_offset`**
  (§18.8): jede Zeichenstelle bekommt beides oder keines. Maße, Fangmarke und
  Schichtkonturen gehen mit (`set_layer` nimmt den Körper der Schicht).
* **Die Schnittebene geht nicht mit — eine Entscheidung**: Sie ist eine
  Szenenebene, schneidet bei zwei Platten beide Teile an ihrer Stelle, und genau
  das fragt ein Schnitt; ihr Weg kommt aus `section_ranges`. Wer das ändert,
  ändert Schnitt und Bedienung zusammen.
* **Zugeordnet wird im Bild, beim Klick**: `_object_at_view` (Hüllquader plus
  Versatz), denn in der Szene liegen die Platten übereinander. Ein Maß merkt es
  je Punkt (`Measurement.object_ids`), die Vorschau in `_snap_owner`; ohne
  Kennung bleibt ein Punkt, wo er ist.

## Eine Zahl in Bildpunkten ist ein Logikpunkt

Bildpunktzahlen stehen in **Logikpunkten**; verglichen werden sie mit
**Gerätepixeln** (Zeiger, `world_to_display`, Pickpuffer). Bei 100 Prozent fällt
der Fehler nicht auf.

* **Umgerechnet wird an der Vergleichsstelle** mit dem Faktor der Ansicht
  (`Renderer.device_ratio()`, `Viewport._device_ratio()`,
  `Viewport._device_pixels`), nie jedes Ereignis in Logikpunkte (dieselbe
  Rechnung an zehnmal so vielen Stellen, quer zum Vertrag). Betroffen u. a.
  `CLICK_SLACK`, `CURSOR_PIXELS`, `SNAP_MARK_PIXELS`, `PULL_HANDLE_PIXELS`,
  `PULL_HIT_PIXELS`, `AXIS_LABEL_PIXELS`, `MEASURE_SNAP_PIXELS`,
  `EDGE_REACH_PIXELS`, `PICK_SLACK_PIXELS`, `SNAP_PIXELS` (auch
  `_pick_reference`), `GIZMO_LEAST_PIXELS`. **Eine neue Zahl: jede Verwendung
  absuchen.**
* **Punktgrößen und Linienbreiten nie** (`SNAP_DOT_PIXELS`,
  `SKETCH_POINT_PIXELS`, jedes `width=`/`size=` am Vertrag) — pygfx rechnet sie
  selbst um (`l2p`).
* **`is_click` bleibt reine Rechnung** (`kamera.md`); der Langlochgriff rechnet
  genauso um.
* **Geprüft durch die Entscheidung des Prüflings** bei 1,0, 1,5 und 2,0
  (`test_navigator.py`, `test_viewport_decisions.py`, `test_slot_handle.py`,
  `test_surface_placement_ui.py`) — eine Sonde, die die Vergleichszeile
  nachbaut, misst sich selbst.

## Der Mauszeiger

* **Zeiger kommen aus `app/ui/cursors.py`**, nie als `Qt.CursorShape` an der
  Aufrufstelle; `cursor(rolle, widget)` wählt eigene Zeichnung oder Systemform.
  `CursorWatcher` setzt den Solidon-Pfeil bei `Show` und `CursorChange` und lässt
  Text-, Hand-, Warte- und Größenzeiger stehen; ein Wiedereintrittsschutz
  verhindert Schleifen beim Systempfeil als Rückfall.
* **Eine neue Rolle**: Silhouette vor Bildidee, angesehen auf vier Untergründen
  (Viewport dunkel, Akzent, Körpergrau, helles Thema), mit dunklem Saum (sonst
  verschwindet der Akzent auf einem gewählten Körper) — und mit Setzstelle:
  `tests/test_cursors.py` prüft, dass jedes gesetzte Literal bekannt ist und
  jede gezeichnete Rolle gesetzt wird.
* **Wo das System eine Form hat, gewinnt sie** (`SYSTEM`): Sie folgt der
  eingestellten Zeigergröße und dem Hochkontrastmodus, unsere täte das nicht.
* **Ein Maß in Millimetern gehört nicht an den Zeiger**, sondern als Ring in die
  Szene.
* **Gesetzt wird nur in `Viewport._update_cursor`**; die Auslöser melden Zustand
  (`set_measure_mode`, `set_sculpting`, `set_splitting`, `set_boning`,
  `set_sketching`, `set_drag_cursor`, `eventFilter`). Die
  Rangfolge in `_resting_role` ist die von `_on_picked` — laufen sie
  auseinander, verspricht der Zeiger etwas anderes, als der Klick tut.
* **`setMouseTracking(True)`** am Widget des Renderers.
* **Der Vertrag zählt Bildpunkte wie Qt** (oben links, Gerätepixel); die
  Umrechnung aus pygfx' Logikpunkten liegt einmal im Renderer. Wer die
  Umrechnung an einer Zeichenstelle wiederholt, rechnet doppelt.
* **Gesucht wird erst, wenn die Maus steht** (`HOVER_DELAY_MS`); ein Kamerazug
  stoppt die Suche.
* **Offscreen gibt es keinen Renderer**, jeder Setzpfad steigt aus — geprüft
  wird mit einer Attrappe, die genau die benutzte Methode hat
  (`tests/test_cursors.py`).

## Wann gemalt wird

### Die Ansicht bestellt ihr Bild — und nichts über ihr malt vorzeitig

* **`render()` bestellt, `render_now()` zeichnet sofort** (`force_draw` ist
  `repaint()` des ganzen Fensters, auch über offene Layouts). Sofort nur, wer
  das Bild in derselben Runde braucht: das erste Bild einer Vorschau
  (`differenceApplied`). Picks hängen nicht am angezeigten Bild.
* **`show`, `hide`, `setVisible`, `raise_` über der Grafikfläche malen sofort** —
  vorher steht alles fürs selbe Bild: Merkmalfenster auf „Messen“ vor der
  Maßgruppe (`MainWindow._place_from_feature_panel`), Layouts gelegt
  (`_lay_out_now`, `LAYOUT_HOPS`); eine Karte ohne fertigen Platz bleibt samt
  `raise_` verborgen (`PlacementFlow._seat_waits`).
* **Ein `QScrollArea` fragt seinen Inhalt nur einmal** — wechselnder Inhalt
  braucht einen Rollbereich, der neu fragt und Umbauten meldet
  (`selection_operations._ListScroller`).
* **Gemessen an `Paint`-Ereignissen, nicht an Bildschirmfotos** — eine Aufnahme
  verschiebt die Folge, die sie aufnehmen soll.

### Nur was über der Grafikfläche liegt, hat ein eigenes Fenster

* **`overlay.keep_widgets_alien` vor der Fläche** (`Viewport.__init__`,
  `AA_DontCreateNativeWidgetSiblings`); nativ werden nur direkte Kinder von
  `Viewport` und `OverlayHost` (`overlay.hold_above_the_view`). Jedes native
  Fenster malt beim Zeigen sofort.
* **Ein Widget entsteht in seinem endgültigen Elternteil** — umgehängt behält es
  sein Fenster und macht die Vorfahren nativ (`PlacementFlow._build_floating`,
  `FeaturePanel.measure_fields(op, None)`).
* **Schwebendes überlebt den Fluss**: `_park_floating` legt es verborgen und
  ungebunden ab, `_take_parked_floating`/`_wire_floating` übernehmen; ein Satz je
  Ansicht unter ihrer Kennung, nicht im schwachen Wörterbuch, geräumt über
  `destroyed`.
* **Der Bildtakt bremst nicht** (`max_fps=30`) — wer dort ansetzt, misst
  vorher.

### Ein Zug zeichnet leichter, sein letztes Bild voll

In Bewegung (`note_camera_motion`: Zug, Rad, 3D-Maus, Flugtaste) zeichnet die
Umgebungsverdeckung leicht. Das Loslassen endet **vor** der Geste, damit deren
Bild voll ist; sonst kommt genau eines nach (`frame_was_reduced`). Rad, 3D-Maus
und stehender Zug enden nach `INTERACTION_SETTLE_MS`, `settle_camera` sofort.
**`set_camera_pose` allein ist keine Bewegung** (Bildschirmfotos).

## Aufbau und Leistung

**Jeder Ansichts-Setter prüft auf Änderung** — ein unnötiger Aufbau kostet an
großen Modellen Sekunden und nimmt dem Actor die Vorschau-Matrix.

| Setter | verglichen wird |
|---|---|
| `set_hidden` | die Menge |
| `set_plate` | die Plattennummer |
| `set_explosion` | der **normalisierte** Wert |
| `set_display_mode` / `set_shading` | Modus / Schattierung |
| `set_section` | Ebene **und** Dicke |
| `set_analysis_map` | Identität der Karte, Gleichheit der Kennung |
| `set_theme` | das Thema; `_theme` beginnt bei `None`, geprüft ganz vorn |

`set_theme` steigt offscreen früh aus und wird an den gesetzten Farben geprüft,
die übrigen am Aufbau-Zähler; Mutationen einzeln ausbauen.

* **Die Kulisse wird nur gebaut, wenn sie sich ändert**: `_bed_built` merkt
  Renderer, Bauraum, Plattenzahl und Bettfarben; Sichtbarkeit, Zeichenebene
  (`_apply_bed_visibility`) und Deckkraft (`_apply_bed_transparency`) werden bei
  jedem Aufruf gesetzt, in beide Richtungen.
* **Die Kantensuche läuft einmal je Netz**, nicht je `show_scene` (jede
  Auswahl, jedes Thema, jeder Schieberschritt): `_edge_meshes` (wie
  `_shadow_splits`) vergleicht die **Identität** des Netzes; den
  Schnittschieber trifft der Cache absichtlich nicht. `feature_edges` zählt
  Kanten als `int64`-Schlüssel `klein·n + groß` mit `argsort`, nicht als Zeilen
  (`test_feature_edges_match_a_row_wise_reference_on_a_dense_mesh`); die
  `face_components` bleiben Sache des Kerns.
* **Was ein neues Netz mitbringt, rechnet der Arbeiter**: über
  `SCENE_PREPARATION_ABOVE` der `_SceneMeshWorker` (Kanten, Hüllen, Normalen),
  bis dahin bleibt die letzte gültige Ansicht. `_MeshMemo` hält zwei Netze je
  Körper (`MESH_MEMO_KEPT`).
* **Ein Aufbau zeichnet ein Bild** (`draw=False` in `_apply_scene`,
  `test_a_scene_build_draws_exactly_one_frame`).
* **Markierungen bauen neu, wenn sich ihr Inhalt ändert**
  (`_feature_patch_state`, `_hover_patch_drawn`), verglichen über `_Same` nach
  Identität, nie über `id()`; gebaut mit geteilten Ecken (`_lifted_patch`,
  `_lifted_and_rim`), Umriss nach Ort (`edges.outline_edges`), unbeleuchtet
  ohne Normalen. Große rechnet `_MarkingWorker` (`MARKING_IN_WORKER_FROM`,
  gemerkt `MARKING_MEMORY`); die Hohlraumfläche nie an der geteilten
  Arbeiterkopie, unter deren Schloss das Merkmalfenster wartete — ab
  `CAVITY_IN_WORKER_FROM` an einer eigenen aus `features.copy_with_answers`,
  die die Flächenfits des Originals liest.

### Die Maßtinte hält ihre Elemente und tauscht nur Punkte

`placement_flow._Dimensions` zeichnet im Renderer, nicht als maskiertes Widget
(die Fenstermaske riss über Vulkan das Gerät): vor dem Material
(`keep_in_front`), unter Griff und Knöpfen (`DRAW_ORDER = -1`). **Acht
dauerhafte Elemente mit fester Kapazität** (fünf Linien, drei Flächen); jeder
Aufbau schreibt nur Punkte (`Item.update_points`) — pygfx baut je neuem Element
eine Pipeline. Die
Kapazität ist der Vertrag (`add_lines`/`add_surface(capacity=…)`, Rest auf NaN,
unbeleuchtet, ohne Zellfarben); reißt sie, entstehen **alle acht** neu, auf das
Doppelte, in ihrer Reihenfolge.

**Was die Ansicht abräumt, kommt im Renderer wieder** (Grenzen in
`app/ui/render/CLAUDE.md`): **Ein abgeräumtes Element wird nie mehr
angefasst**, und wer eines umfärbt, umdeckt oder anders pickbar stellt, nimmt es
aus dem Vorrat (`restyled`).

### Der erste Pick kostet eine halbe Sekunde — und niemand soll ihn bezahlen

`_warm_the_picker` zieht ihn vor: über einen Timer, am **Anfang** von
`_apply_scene` vor dessen frühen Rückkehrpunkten (der leere Startaufbau kostet
niemanden), einmal je Renderer (`_picker_warm`);
`_warm_again_for_new_geometry` am **Ende** armiert neu, nur bei neuer
Geometrie. Geprüft wird der Anschluss, nicht die Zeit
(`test_the_picker_is_warmed_up_before_the_first_gesture`,
`test_new_geometry_warms_the_picker_again`). Schriftzeichen ebenso
(`_warm_the_glyphs`): **Neue Zeichen in Beschriftungen gehören in
`LABEL_GLYPHS`.**

### Der Adapter wird einmal gefragt, und nicht im Hauptthread

Ohne wgpu-Adapter stirbt der Renderer mit dem Prozess; die erste Frage kostet
rund eine Sekunde, jede weitere 0,3 s, bei drei Sekunden Startbudget (§31). In
`app/ui/render/factory.py`: **Die Antwort bleibt liegen** (sie gilt für die
Maschine); **gefragt wird nebenan** (`_AdapterProbe` aus `app.ui.app.main` an
der Leine, bevor das Register lädt); **mit Frist** (`ADAPTER_TIMEOUT_SECONDS`,
danach der Satz für einen fehlenden Adapter, §27; ohne Vorarbeit wird
gewartet); **nie zwei Fragen zugleich** (wgpu legt die Instanz ohne Sperre an;
`probe()` und `available()` teilen eine Bedingungsvariable). Nachweis:
`tests/test_render_factory.py`, der Anschluss in `app/ui/app.py` am Quelltext
geprüft.

## Die Skizze ist Vordergrund, der Körper Zusammenhang

* **Beim Zeichnen tritt der Körper zurück** (`SKETCH_CONTEXT_OPACITY`,
  Kontaktschatten und Körperauswahl weichen); der Darstellungsmodus kehrt beim
  Verlassen zurück.
* **Verdeckung**: `OverlayHost` meldet linke, rechte und untere über
  `set_zone_margins`; nur die Skizzenkamera liest die untere
  (`occluded_view_shift`, Regel in `kamera.md`).
* **Fangmarke und unfertige Kurve haben eigene Actors**, die `show_sketch`
  zwischen zwei Gesten nicht abräumt; gleiche Topologie tauscht nur Punkte.
  Maßkarten, Achsenbuchstaben und Ziehgriff-Beschriftungen sind
  `pickable=False`.
* **Schaft, Kreuz und *Abtragen* nur bei genau einem bearbeitbaren Körper**;
  ohne ihn erzeugt ein Zug nach innen keine Operation.

`sketch_grid`, `show_sketch_cursor`, `_sketch_hit`, `set_sketch_pull`,
`MEASURE_GAP`, `view_on_plane` und `place_sketch_cards`
regelt `zeichenflaeche.md`.

## Renderstart: Plattform und Wayland

* **Die wirksame Qt-Plattform entscheidet**, fest seit dem Aufbau der
  `QGuiApplication`: `viewport._available()` fragt `platformName()`, die
  Umgebungsvariable nur vorher, dann `factory.available()`.
* **Auf Wayland wird die Ansicht nicht gebaut** (der wgpu-Fensterweg ist nur
  unter X11/Xwayland geprüft). `app/ui/qt_platform.py` wählt vor der Anwendung
  xcb, sobald ein X11-Display da ist (Qt 6 nähme sonst Wayland), in einer
  Wayland-Sitzung `xcb;wayland` — fehlt eine Bibliothek des X11-Plugins
  (`libxcb-cursor0`), startet Solidon ohne 3D-Ansicht statt gar nicht;
  `unavailable_hint()` nennt, was fehlt (mit `DISPLAY` die Bibliothek, ohne
  Xwayland). Wer die Plattform vor dem Aufbau liest oder setzt, auch ein
  Werkzeug in `tools/`, geht über diese Funktion.
* **Das Eingabemodul muss im mitgelieferten Qt liegen** (RM-062): PySide6
  bringt `compose`, `ibus` und `qtvirtualkeyboard`, kein Fcitx-Modul. Nennt
  die Umgebung Fcitx (`QT_IM_MODULE`, `QT_IM_MODULES`, `XMODIFIERS`), setzt
  `qt_platform.prefer_an_input_method_qt_has` vor der Anwendung `ibus`,
  außerhalb des Flatpak mit `IBUS_USE_PORTAL=1`, wo Fcitx5 das Portal trägt
  (Herleitung: `input_method_environment`). Der Starttest des Pakets verlangt
  unter Linux das IBus-Modul.

## Was nur das Bild zeigt

Ein Dialog ist erst nach gerenderter Sichtprüfung geprüft (§35).

- Echte Plattform verwenden: Offscreen fehlen hier Schrift und gültige
  Breitenmetriken (`/erzeugen`). Für reine Widgets ohne Bildschirmfenster:
  `apply_style(app, "dark")`, `show`, `processEvents`, `grab().save`.
- Sprachen über `install_catalog(sprache, read_catalog(sprache))` laden;
  `set_language` setzt nur die Variable. Für Qt-Knöpfe zusätzlich
  `install_qt_translations(app, sprache)`, sonst ist „Cancel“ kein Produktfund.
  Gleich große Bilder auf tatsächlich verschiedene Sprachinhalte prüfen.
- Viewport nur am gezeigten Fenster per `grabWindow`; `widget.grab` liefert
  schwarze Mitte. Echte Prüfstände laden zuerst `bootstrap.load_operations`,
  setzen kein `QT_QPA_PLATFORM`, verwenden `QTimer.singleShot`-Ketten und
  `faulthandler.dump_traceback_later`. Kein `window.start` mit modalem Erstlauf;
  vor jedem Bild `processEvents`, sonst können zwei Zustände erscheinen.
- Nicht umbrechende Zeilen: `sizeHint().width()` gegen `width()` je Sprache.
  Mindestgröße und Vollbild ansehen, Bildermaße tatsächlich betrachten.
  Kachelmodus nach Änderungen mit `doItemsLayout` neu anordnen.
- Rendererattrappen erben den abstrakten Vertrag (`tests/render_fakes.py`);
  keine zusätzlichen Methoden, die echte Abstürze verdecken.
- Bei Enge auf Symbole reduzierte Leisten melden weiterhin die im breiten
  Zustand gemerkte volle `sizeHint`-Breite, sonst wachsen sie nie zurück
  (Höhenentsprechung in `fenster.md`). `SizePolicy.Fixed` lähmt,
  `Ignored` meldet null; `setSizeConstraint(SetNoConstraint)` verwenden.
- Unverändert glatte Messwerte trotz anderer Sprache, Schrift oder Inhalt
  sind selbst ein Befund: möglicherweise wurde der Messweg abgeschnitten.
