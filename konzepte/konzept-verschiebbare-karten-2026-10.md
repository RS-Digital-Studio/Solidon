# Konzept: verschiebbare Karten (06.10.2026)

> **Stand 06.10.2026: umgesetzt** in `app/ui/overlay.py` (`CardPlace`,
> `CardGrip`, `card_rect`, `dropped_place`, `settled_places`, `free_span`),
> verdrahtet in `app/ui/main_window.py`, Regel in `.claude/rules/fenster.md`,
> Bauplan §2.5. Anlass: Fragebogen S-20261006-5c132b („Bewegliche Menüs?“),
> Entscheidung Robert „Karten verschiebbar“. Nach der Durchsicht
> (`output/review/punkte-0.5.3-2026-10-06/review-rm533-rm538.md`) entspricht
> der Zug dem Soll §3 und §7: Umriss und Satz zeigen das Ergebnis, ein zweiter
> Umriss die wandernde andere Karte, beim Überdecken bekommt die gezogene den
> Platz; der Griff steht zuerst in der Tabfolge seiner Karte (er entsteht vor
> ihrem Inhalt); eine schwebende Karte hält ihre Oberkante, auch wenn sie
> wächst — dann endet sie an der Unterkante und rollt. Abnahme 1 bis 7, 9 bis 12 sind Tests
> (`tests/test_overlay.py`), 13 offscreen für die Reiterleiste ohne Zeichen.
>
> **Abweichungen vom Entwurf unten:**
>
> - Die Ortswörter („rechts unter *Auswahl*“) bleiben in Handbuch, Tour und
>   Texten — sie beschreiben die Stammlage, wie die Bildanleitungen auch, und
>   ein Anfänger findet „unter *Auswahl*“ ohne Seite schlechter. Wer eine
>   Karte verschiebt, weiß, wohin. Der Wächter aus Abnahme 10 entfällt damit.
> - Der Reiter *Prüfbericht* trägt in vier Sprachen einen kurzen Namen
>   (Kontext „Reiter“: Informe, Rapport, Rapporto, Relatório); Handbuch und
>   Menü behalten den vollen.
> - Überdecken sich die Karten nach einer Größenänderung, stehen beide
>   vorübergehend an der Stammlage. „Die zuletzt gelegte behält den Platz“
>   (§3, Kanten) ist nicht gebaut; die Einstellungen merken keine Reihenfolge.
>
> **Offen:**
>
> - Abnahme 8 (Pos1 rahmt in die Lücke, Verschieben ruft `reset_camera` nicht)
>   hat keinen Test; sie braucht die Kamera und gehört zum Renderertest.
> - Abnahme 13 am echten Fenster beim Release: Reiterleiste ohne Rollpfeile in
>   sechs Sprachen (offscreen bei 1280 und 1024 grün), 3-s-Zug ohne
>   Malereignisse der Karte vor dem Loslassen, Zahl nativer Widgets gleich.
>   Mit dem Reiter *Bedingungen* (Zeichnen) oder *Tour* ist die Leiste nicht
>   gemessen.
> - Die zuletzt gelegte Karte behält beim Überdecken nicht ihren Platz (siehe
>   oben).

Der folgende Entwurf stammt vom Agenten `bedienlogik` (nur gelesen, am
Fenster nicht gefahren) und ist unverändert übernommen.

Anlass: Fragebogen S-20261006-5c132b („Bewegliche Menüs?“), Entscheidung Robert
vom 06.10.2026: „Karten verschiebbar“. Nur gelesen, am Fenster nicht gefahren.

## Empfehlung

Die Karten werden innerhalb des Hauptfensters verschoben und rasten an den
Rändern ein. Abdocken als eigenes Fenster wird nicht gebaut. Verschiebbar sind
die linke Karte (Objekte, Parameter, Verlauf, Filamente) und die rechte Karte
(Auswahl, Prüfbericht, Chat). Die untere Werkzeugleiste bleibt, wo sie ist.

## 1. Ist-Ablauf (aus dem Code abgeleitet)

- Feste Plätze: `overlay.py:21-22` („keine Ziehleiste“), links
  `QRect(EDGE, EDGE, …)` (`overlay.py:1258`), rechts `width - card - EDGE`
  (`1264-1267`), unten mittig (`1274-1278`), Seite fest in `set_zones`
  (`1027-1029`).
- Heute: Abschnitte links zuklappen; F9 blendet rechts ganz aus
  (`main_window.py:8236-8241`); Pos1 rahmt in den freien Streifen
  (`viewport.py:16444-16458`, `camera_in_free_area` 483-542).
- Gespeichert wird nur `right_panel_visible` (`settings.py:72`).
- Ränder für die Ansicht aus den Kartenbreiten (`overlay.py:1343-1347`).
- Bestandsfehler (gelesen): Die Ansichtsleiste weicht nur der unteren Karte aus
  (`viewport.py:3431-3435`); eine hohe rechte Karte bis zur Unterkante des
  Platzes (`overlay.py:1252`) liegt über ihr.

## 2. Abdocken oder Verschieben — nur im Hauptfenster verschieben

- Kürzel gelten nur im aktiven Hauptfenster; §19.2 „Undo und Redo überall,
  auch im Chat“ ginge in einem abgedockten Fenster verloren.
- Umhängen nativer Widgets macht Vorfahren nativ (`ansicht.md`; RM-232: 140 von
  854 Widgets, Bohrungsklick 346 statt 146 ms, `overlay.py:239-252`).
- Fehlerbericht, Kartenstilblatt (`main_window.py:19643`), Tourziele,
  Einladungen, `isVisibleTo(self)` (`main_window.py:26029`) hängen am Fenster.
- Kein Vergleichs-Slicer dockt ab (nicht nachgeprüft).
- Auch beim Verschieben: native Fenster malen bei jeder Bewegung — darum zieht
  ein **Umriss** (Linien, keine Maske), die Karte gleitet erst beim Loslassen.

## 3. Soll-Ablauf

**Griff:** oben rechts an jeder Seitenkarte, sechs Punkte; rechts als Eckwidget
neben den Reitern, links in der Kopfzeile *Objekte*. Zeiger Verschiebekreuz,
Tooltip „Karte verschieben. Doppelklick legt sie zurück.“ Menü *Ansicht →
Karten an ihren Platz* (Ansichtsmenü 7 → 8 Zeilen). Reiter und Klappen ziehen
nicht. Start in der Stammlage; Erzeuger mit `UiSettings()` unverändert.

| Ausgang | sieht | tut | passiert | Rückweg |
|---|---|---|---|---|
| Stammlage | Griff | drückt auf den Griff | Umriss in Kartengröße am Zeiger | Escape |
| Ziehen | Umriss bleibt im Fenster | bis 32 Punkte an linken/rechten Rand | Umriss bündig, eckig; Statuszeile „Loslassen legt die Karte an den rechten Rand.“ | Escape |
| Ziehen | Umriss frei | in die Fläche | MARGIN Abstand; „Loslassen lässt die Karte hier schweben.“ | Escape |
| Rand der anderen Karte | zweiter Umriss gegenüber | loslassen | beide tauschen die Seiten (MOVE_MS); ein Rand, eine Karte | Doppelklick |
| über schwebender anderer | zweiter Umriss zeigt Ausweichen | loslassen | gezogene bekommt den Platz, andere rückt waagrecht | Doppelklick |
| Loslassen | – | – | gleitet, speichert, Kamera bleibt; Quittung „Karte liegt jetzt rechts. Doppelklick auf den Griff legt sie zurück.“ | Doppelklick / Menü |

Escape oder Fokusverlust bricht ab. Schwebende Karte: Höhe nach Inhalt
(`natural_height`, `_share_room`), nie unter die Unterkante des Platzes
(`overlay.py:1252`), wächst an ihrem relativen Platz, Breite nach den
bisherigen Regeln, keine Größenkante.

**Rückweg:** Strg+Z nimmt Kartenlage nicht zurück (Darstellung, §2.1).
Doppelklick auf den Griff: diese Karte zurück. Menü: beide zurück, Quittung,
wenn schon dort. Keine Rückfrage (Regel 19).

**Speichern:** beim Loslassen und Zurücklegen über `_store_settings()`; je
Karte Lage (links, rechts, schwebend), bei schwebend zwei Anteile 0–1 am freien
Spielraum (`x = fx·(B − b)`), dazu welche zuletzt gelegt wurde. Nicht je
Bildschirmgröße; Kaputtes gilt als Stammlage.

**Kanten:** Überdeckung nach Größenänderung → zuletzt gelegte behält den
Platz, die andere rückt daneben; geht das nicht, vorübergehend Stammlage,
gespeicherte Anordnung bleibt (`NARROW_CARD_SHARE` 42 %, `overlay.py:205`).
Bildschirmwechsel, Skalierung, Vollbild über `resizeEvent` → `_place`. F9
blendet am jetzigen Platz aus. Tourziele folgen (`guide_targets.py:338-378`),
`_open_view` (`guide_targets.py:468-474`) braucht die Lückenrechnung.
Zeichenmodus: Karten bleiben, `_bottom_room` wie heute.

## 4. Einpassen und Kamera

Jede sichtbare Seitenkarte sperrt ihren waagrechten Bereich über die volle
Höhe; gemeldet wird die breiteste freie Spanne als `(links, rechts, unten)` an
`set_zone_margins` (`viewport.py:16821`), bei Gleichstand die linke. Stammlage
ergibt dieselben Zahlen. Gerechnet mit Zielrechtecken. Verschieben rahmt nicht
neu (`test_viewport_decisions.py:5254`). Ansichtsleiste weicht jeder Karte aus,
die sie schneidet (`viewport.py:3407-3436`).

## 5. Zählung

| Aufgabe | Heute | Soll |
|---|---|---|
| Rechte Karte vom Modell weg, ohne Bericht/Auswahl zu verlieren | geht nicht (F9 nimmt alles) | 1 Zug am Griff |
| Seiten tauschen | geht nicht | 1 Zug an den linken Rand |
| Zurück zur Stammlage | – | Doppelklick oder Menü (2 Klicks) |
| Nur Tastatur | geht nicht | Tab zum Griff, Enter, ↓, Enter |
| Teil unter einer Karte | Pos1 | Pos1, rahmt in die tatsächliche Lücke |

## 6. Tastatur und Barrierefreiheit

Griff ist ein Knopf mit `StrongFocus`, erstes Element der Karte in der
Tabfolge. Pfeile schieben 24 Punkte, Umschalt 96, am Rand rastet es ein. Enter,
Leertaste, Menütaste, Umschalt+F10: Menü *An den linken Rand*, *An den rechten
Rand*, *An ihren Platz*. Zweite Kodierung: Symbol + Tooltip, Umrissform
(bündig/eckig gegen schwebend/abgesetzt), Statuszeilensatz. `accessibleName`
„Karte Auswahl verschieben“, `accessibleDescription` nennt die Lage.

## 7. Fehlerfälle

Loslassen über der anderen Karte: Ausweichen, vorher sichtbar. Kein Platz:
Karte bleibt, Satz „Hier ist neben der anderen Karte kein Platz.“ Außerhalb des
Fensters: Umriss war begrenzt. Fenster zu klein: vorübergehend Stammlage. Karte
über Gizmo: Qt nimmt den Klick, Pos1 hilft. Ansichtsleiste weicht aus.
Werkzeugleiste: kann nicht passieren. Maßgruppe: `PlacementFlow` beobachtet
Zonen als Rechtecke (`placement_flow.py:1568-1575`). Einladungen:
`ViewNotice` (`survey.py:395-404`). Kaputte Einstellung: Stammlage.

## 8. Entscheidungen

1. Kein Abdocken. 2. Nur die beiden Seitenkarten. 3. Ein Griff, keine
Kopfzeile. 4. Umriss statt Live-Bewegung. 5. Keine Größenänderung. 6. Ein Rand,
eine Karte, Tausch beim Einrasten; `dock` „left“/„right“ gibt es schon
(`overlay.py:379-393`, `_round_corners` 397-436), schwebend heißt leer;
`_dock` (`503-511`) lernt Leeren. 7. Streifenmodell fürs Einpassen. 8.
Ortswörter („rechts“, „links“) in Kundentexten fallen weg, Texte nennen den
Namen der Stelle: `surfaces.py:688-694`, `shortcuts_window.py:115`,
`main_window.py:14638, 14667, 14730`, F9-Eintrag (`main_window.py:4658`),
`print_settings_dialog.py:2896`, `core/tour.py:320, 354, 460, 707`,
`core/guides.py:530`, `core/manual.py:278, 521, 623, 812, 892, 1282, 1456,
1499, 1880`, alle Kataloge. 9. Bauplan §2.5 bekommt einen Satz (mit Ansage),
`fenster.md` „Drei Zonen“, Register in `ROADMAP.md`.

## 9. Abnahmekriterien

1. Stammlage mit `UiSettings()` pixelgleich; `test_overlay.py:260-291,
   311-332` unverändert grün.
2. Loslassen unter 32 Punkten zum rechten Rand: bündig (`right() == width − 1`,
   `dock` „right“); bei 33 Punkten schwebend mit MARGIN, vier runde Ecken.
3. Tausch: keine zwei Karten am selben Rand.
4. Bei 640, 800, 1200, 1920, 2560, 3840 und jeder gespeicherten Lage: keine
   Überschneidung, ganz im Fenster, Unterkante über `_bottom_room`.
5. Rückfall: Stammlage im Bild, Einstellung unverändert.
6. Escape: Geometrie und Einstellung unverändert.
7. Doppelklick und Menü stellen die Stammlage her und speichern; Strg+Z ändert
   die Kartenlage nicht.
8. Pos1: rechte Karte links → linker Rand ihre Breite + EDGE + MARGIN, alle
   acht Hüllquaderecken in der Lücke (Muster `test_viewport_decisions.py:5227`);
   Verschieben ruft `reset_camera` nicht.
9. Tastatur: Griff per Tab, Pfeil rechts 24 Punkte, Enter öffnet drei Einträge.
10. Zugänglichkeit: Namen nicht leer, eindeutig, Beschreibung nennt Lage; kein
    Kundentext nennt eine Karte über „links“/„rechts“ (Wächter `test_wording.py`).
11. Ansichtsleiste schneidet kein sichtbares Kartenrechteck.
12. Tour: `_open_view` liefert bei getauschten Karten die Lücke dazwischen.
13. Release am echten Fenster: Reiterleiste mit Griff ohne Rollpfeile in sechs
    Sprachen; 3-s-Zug ohne Malereignisse der Karte vor dem Loslassen; Zahl
    nativer Widgets gleich (Maß aus RM-232).

## 10. Dateien

`app/ui/overlay.py` (Docstring 1-23, `MARGIN`/`EDGE`/`DOCK_PROPERTY` 208-219,
`_dock` 503-511, `set_zones` 1012-1044, `_lay_out` 1236-1280,
`_tell_the_view_about_the_zones` 1300-1347, neu: Griff, Umriss, Rechnung als
reine Funktionen); `app/ui/main_window.py` (linke Karte 3018-3032, rechte
Reiter/Spalte 3595-3672, `set_zones` 3679-3680, Ansichtsmenü 4656-4666,
`action_toggle_right` 8236-8241, Palette 11115, Quittungen 14638/14667/14730,
Einstellungen 3813, 26725-26759); `app/ui/settings.py` (`UiSettings` 34-135);
`app/ui/viewport.py` (`ViewBar.place` 3407-3436, `set_zone_margins`
16821-16838); `app/ui/guide_targets.py` (`_open_view` 453-478);
`app/ui/cursors.py`, `app/ui/icons.py`; `app/core/registry/surfaces.py`
688-694; `shortcuts_window.py` 115; `print_settings_dialog.py` 2896;
`core/tour.py`, `core/guides.py`, `core/manual.py`, Kataloge; Bauplan §2.5,
`fenster.md`, `app/ui/CLAUDE.md`, `ROADMAP.md`.

Tests mit festen Kartenorten (gelten gegen die Stammlage weiter):
`test_overlay.py` 144-194, 260-291, 294-308, 311-332, 335-347, 836-872;
`test_ui.py` 2808, 2942-2949, 7948-8079, 8083, 8172-8220, 14171-14200,
14599-14638, 15872-15885, 16187-16224, 22162-22167;
`test_viewport_decisions.py` 450, 1908, 1936, 5227, 5254-5262;
`test_feature_label_layout.py` 49, 128-164; `test_placement_dimensions.py`
966, 1623; `test_interface_limits.py` 169-188; `test_filament_assignment.py` 523.

Neue Tests: Rechnung als reine Funktionen in `test_overlay.py` (Einrasten,
Tausch, Ausweichen, Rückfall, Anteile, Lücke); Fensterwege in `test_ui.py`;
`test_cursors.py` für die Zeigerrolle; Wortlisten-Wächter in `test_wording.py`.
