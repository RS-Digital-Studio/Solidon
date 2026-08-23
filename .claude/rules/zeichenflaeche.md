---
paths:
  - "app/ui/sketch_editor.py"
---

# Regeln für die Zeichenfläche

Der Skizzenmodus. Die übrigen Oberflächenregeln — Texte, Wartezeit,
Barrierefreiheit, der Mauszeiger, die Ansicht — stehen in `oberflaeche.md`
und gelten hier unverändert mit.

Der Skizzeneditor (`app/ui/sketch_editor.py`) ist die zweite Ansicht, in der
gezeigt werden muss, was gleich passiert. Vier Zusagen, alle vier hatten
gefehlt:

**Was entsteht, hängt am Zeiger.** Linie, Kreis und Bogen zeigen ihre Vorschau,
bis der Klick sie festmacht. Ohne sie setzt ein Klick einen gestrichelten
Kreis, dann geschieht nichts, und beim zweiten steht plötzlich eine Linie da.

**Gefangen wird auf das Raster, ein vorhandener Punkt schlägt es.** Sonst risse
der Fang die Deckung auf, für die er da ist. Der Haken steht an der
Ebenenzeile, an ist die Vorgabe, ein Millimeter die Weite; ein Kreuz am Zeiger
zeigt, wohin ein Klick fiele — gefangen wird feiner, als das Raster gezeichnet
ist. Derselbe Fang gilt beim Ziehen eines Punktes, sonst wäre er eine Zusage
bis zum ersten Nachbessern.

**Raster und Beschriftung folgen dem Maßstab** (`grid_step`, Folge 1, 2, 5),
und das Rad zoomt auf den Zeiger. Eine feste Weite ist herausgezoomt eine
Fläche aus Linien und hineingezoomt ein Blatt mit vier Linien darauf.

**Die Ebene ist eine Ansicht, und sie steht im Bild.** Benannt wird sie danach,
was man sieht (Draufsicht, Vorderansicht, Seitenansicht), die Ebene steht in
Klammern daneben — sie ist die Angabe, die in der Projektdatei landet. Die
Achsenbuchstaben kommen aus `PLANE_AXES` und folgen ihr; auf einer angeklickten
Fläche des Körpers bleiben sie weg, denn die kann beliebig geneigt sein. Die
Ziffern 1, 2 und 3 wechseln direkt und gehen dabei über `choose_plane`, also
über das Auswahlfeld — an ihm vorbei behaupteten zwei Stellen zweierlei.

Und jedes Zeichenwerkzeug sagt in der Statuszeile, was der nächste Klick tut
(`drawing_hint`). Der Linienzug ist der Fall, an dem es fehlte: er läuft
weiter, bis Esc ihn beendet, und das stand nirgends.

**Wo der Zeiger steht, steht in der Zeile** (`pointer_target`,
`SketchPanel._show_pointer`). Genannt wird nicht die rohe Lage, sondern der
Ort, an dem ein Klick landet — bei aktivem Fang also die Rasterweite. Eine
Anzeige, die 29,75 zeigt, wo 30 entsteht, wäre schlechter als keine. Ohne sie
ist ein gezogener Punkt eine ungefähre Lage, und „genau" geht nur über den
Umweg Nachmessen; wo es auf den Zehntel ankommt, führt das Kontextmenü am
Punkt zu Zahlen (`edit_point`) — mit eigenem `_remember()`, denn den
Undo-Punkt setzt beim Ziehen der Mausdruck.

**Der Zeiger sagt, was ein Klick tut — auch auf der Zeichenfläche.** Sie
setzte ihn nie: der Pfeil stand da, gleich ob ein Zeichenwerkzeug lief oder
nicht. Wer drei Punkte gesetzt hatte und den mittleren anklickte, um ihn zu
ziehen, setzte einen vierten genau darauf — deckungsgleich, unsichtbar, mit
Bedingung. Gesetzt wird in `SketchCanvas.set_tool`, aus derselben Quelle wie
überall (`cursors.cursor`); die Rolle `draw` ist eine **Systemform**
(`CrossCursor`), weil das Fadenkreuz die bekannteste Form für „hier entsteht
etwas" ist und der Zeigergröße des Systems folgt. Dass der Viewport seinen
Zeiger an genau einer Stelle setzt, gilt dort und aus seinem eigenen Grund —
die Zeichenfläche hat nur einen Auslöser, das Werkzeug.

**Ein Klick auf einen Punkt greift ihn** (`grab_point`) — beim Auswählen und
beim Punktwerkzeug, und er hängt sofort am Zeiger. Vorher entstand dort ein
zweiter genau auf dem ersten, deckungsgleich und unsichtbar, und um den
ersten zu bewegen, musste man erst das Werkzeug wechseln. Die Regel steht in
`place` und nicht bloß im Mausereignis: **was ein Klick tut, entscheidet die
Methode, die auch ein Test ruft** — die Ereignisse übersetzen nur. Bei Linie,
Kreis und Bogen bleibt der Fang, wie er war: dort ist der vorhandene Punkt der
Anfang des neuen Elements, und die Deckung ist die Verbindung, für die der
Fang da ist.

**Was ein Klick greifen würde, leuchtet auf** (`_note_hover`). Der Fangradius
ist acht Bildpunkte; wo er greift, gehört ein Zeichen hin — sonst klickt man,
sieht keinen Unterschied und klickt wieder. Und die Auswahl selbst muss man
sehen: 5,0 gegen 3,5 Bildpunkte Radius waren drei Bildpunkte Unterschied im
Durchmesser, die Aussage hing damit praktisch allein an der Farbe (Regel 18).

**Ein Knopf, der nicht kann, sagt was ihm fehlt.** Die zehn Bedingungsknöpfe
folgen der Auswahl (`constraint_offers`); wer sie nur sperrt, lässt raten. Der
Hinweis am Knopf und die Meldung nach einem Kürzel nennen dieselbe Auskunft
aus derselben Quelle (`_needs_phrase`) — stumm zurückzukehren ist die
schlechtere Hälfte von „fehlgeschlagen": es sagt nicht einmal, dass etwas
nicht ging. Dass **Strg** das Zweite dazunimmt, steht in der Zeile, sobald
eines ausgewählt ist (`selection_hint`) — ohne das kommt niemand auf ein Maß
zwischen zwei Punkten.

**Das Maß beim Zeichnen steht am Zeiger, nicht in der Werkzeugzeile.** Wer
eine Linie zieht, sieht auf ihre Spitze; eine Zahl am Fensterrand liest dort
niemand. Fusion legt sie an den Zeiger, und darum ist das Eintippen dort der
Normalweg — hier war es eine Funktion, die man kennen musste. Die
Zeichenfläche besitzt `measure_field` und legt es mit `MEASURE_GAP`
Bildpunkten Abstand neben die Spitze:

* **Nicht darunter** — es finge die Mausbewegungen ab, und die Linie bliebe
  beim Ziehen stehen.
* **An Rand und Ecke kippt es** auf die andere Seite des Zeigers. Die untere
  rechte Ecke ist kein Sonderfall: dorthin zieht man die letzte Linie eines
  Umrisses.
* **Die erste Ziffer beginnt die Eingabe**, ohne Klick und ohne Tabulator.
  Ein Feld, das man erst anklicken muss, verlangt genau die Handbewegung, die
  das Zeichnen unterbricht — und der Zeiger steht danach woanders, also auch
  das Maß, das er gerade zeigte. Gesendet wird an `lineEdit()`; ein `event()`
  auf dem Drehfeld landet in der Pfeiltastenbehandlung.

Nebenbei löst das den breitesten Posten der Werkzeugzeile auf. Ein erster
Schritt hatte ihn nur ausgeblendet, solange nichts gezeichnet wird — gemessen
gegen den Stand davor sprang die Zeile beim ersten Klick von 881 auf 1007
Bildpunkte zurück, also genau dann, wenn man sie am wenigsten braucht.

**Was im Konstruktor gesetzt wird, kommt vor den Verbindungen.** `SketchPanel`
setzt die Skizze, bevor `sketchChanged` verbunden ist: die Bedingungsliste
blieb bei einer geöffneten Skizze leer, bis irgendetwas geändert wurde, und
die Knöpfe standen alle bedienbar da. Ein Signal ersetzt nicht den ersten
Aufruf — beide Auffrischungen laufen am Ende des Konstruktors von Hand.

**Der Drehpunkt ist die Mitte der Körper, nicht die des Sichtbaren.**
`ComputeVisiblePropBounds` nimmt Druckplatte und Bauraumrahmen mit; bei 250 mm
Rahmen und 40 mm Teil liegt die Mitte hundert Millimeter über dem Modell, und
die Kamera rückt bei jedem Szenenaufbau dorthin. `rotation_centre()` rechnet
deshalb aus `_object_bounds()` — derselben Quelle wie `reset_camera`. Ohne
Körper wird gar nichts verschoben.

**Die Zeile beantwortet zwei Fragen, und die erste ist „ist es zu?".** Ob eine
Kontur geschlossen ist, war bis zum Bestätigen der Operation nicht zu
erfahren: Wer vier Linien zog und den letzten Klick knapp neben den ersten
Punkt setzte, sah dasselbe Bild wie einer, der getroffen hatte — die Auskunft
kam danach, als Absage. `_outline_state()` fragt `regions_of`, also denselben
Kern, der später rechnet; die Antwort ist damit dieselbe und nicht bloß eine
ähnliche. Übernommen wird aber nur das **Ja oder Nein**, nicht sein Satz: „Der
Umriss ist nicht geschlossen" ist die Absage auf eine Handlung und stünde hier
vom ersten Strich an als Warnung vor einem Zustand, den man gerade
beabsichtigt. In der Zeile steht „Noch offen" oder „Geschlossen", und dahinter
die Freiheitsgrade — keine der beiden Fragen beantwortet die andere: ein
bestimmtes Rechteck kann offen sein, ein geschlossenes darf wackeln.

**Verschieben ist ein eigener Griff, kein Punkt-für-Punkt.** `edit.move`
schiebt die Auswahl an Ort und Stelle — verschoben, nicht kopiert wie
`offset` und `mirror` daneben, also behalten die Elemente ihren Platz in der
Liste und jede Bedingung zeigt weiter auf dieselbe Stelle. Vorher gab es nur
`move_point`: bei einem Rechteck vier Züge, von denen die ersten drei die Form
verziehen. In der Zeichenfläche hängt die Auswahl nach dem Klick an der Hand,
aber erst **ab Qts `startDragDistance`** (`_shift_selection`) — ohne die
Schwelle säße die Form nach jedem Auswahlklick ein Zehntelmillimeter daneben.
Der Undo-Punkt entsteht beim ersten wirklichen Zug und nur einmal; `move_selected`
merkt nicht, sonst stünden im Rückgängig so viele Schritte, wie die Maus
Meldungen geschickt hat.

**Was auf einer Taste liegt, steht auch im Kontextmenü.** Löschen lag allein
auf Entf, und in der Werkzeugleiste steht es nicht — wer die Taste nicht rät,
wird ein Element nicht los. Der Eintrag nennt das Kürzel daneben, so lernt man
es nebenbei. `_context_menu` ist dafür in **Bauen** (`context_menu_at`) und
Zeigen getrennt: ein Menü, das sich selbst öffnet, hält eine Suite an —
`QMenu.exec` blockiert wie ein modaler Dialog, und `QMenu.exec` zu patchen ist
kein Ersatz, sondern der nächste Hänger.
