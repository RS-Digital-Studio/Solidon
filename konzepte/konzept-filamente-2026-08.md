# Konzept: Filamente statt nummerierter Slots

> **Stand: ENTSCHIEDEN von Robert am 26.08.2026, Umsetzung beginnt.**
> Entstanden aus der Einfachheits-Kontrolle des Bemalens: „Welche Farbe hat
> Slot 1?" konnte die Oberfläche nicht beantworten, und das Punkt-Radius-Malen
> passt nicht zu einer Anwendung, die ihre Flächen beim Namen kennt.
> Zwei Auslegungsannahmen sind unten als solche markiert.

## Roberts Entscheidung, ausformuliert

Wörtlich entschieden: Dreiklang komplett, das Punkt-Radius-Bemalen komplett
raus, Handbuch anpassen. Orange bleibt — aber **nur für die Auswahl**. Farben
kommen von **Filamenten**: Farbpalette bei der Filamentauswahl, beliebig viele
Filamente anlegbar, speicherbar als **Filamentkatalog** (Vorwahl). Ohne
zugewiesene Farbe ist die Filamentfarbe **Grau**. Eine Auswahl **blendet die
Filamentfarbe aus** (Orange überdeckt sie), sie ersetzt sie nicht.

## Das Modell

1. **Ein Filament ist benannt und trägt eine Farbe.** Das Dokumentmodell kann
   das heute schon (`MaterialSlot` hat `name` und `colour`); was fehlt, ist
   die Bedienung: ein Farbwähler bei der Filamentauswahl statt eines nackten
   Zahlen-Spinners 0–7.
2. **Der Filamentkatalog** ist ein Nutzerkatalog (projektübergreifend, im
   Profil): beliebig viele Einträge Name+Farbe, als Vorwahl beim Zuweisen.
   Die Grenze **je Objekt** bleibt `MAX_SLOTS = 8` — das ist die
   Druckerrealität des 3MF-Farbwechsels, keine Katalogsgrenze.
3. **Färben hat zwei Gesten, nicht drei:**
   - **Teil färben** — `assign_slot` (existiert): das ganze Objekt bekommt
     ein Filament.
   - **Fläche färben** — `paint_slot` wird zur **Merkmal-Füllung**: Rechtsklick
     auf eine Fläche (oder Auswahl im Baum) färbt **genau deren Dreiecke**,
     über `at_feature` wie bei Bausteinen und Bohrungen. Kein Radius, kein
     Klickpunkt. Merkmalsstabil: Ändert ein früherer Schritt die Maße, wandert
     die Färbung mit (§21) — ein gespeicherter Punkt läge daneben.
   - **Der Punkt-Radius-Pinsel entfällt komplett**: das Werkzeug „Bemalen" in
     der Werkzeugzeile (dann 7 von 8 Plätzen belegt), die Pinselleiste
     (`paint_bar`), der Strichpfad (`stroke_at`) und die Radius-Parameter.
4. **Anzeige:** Die echte Filamentfarbe im Viewport; **Grau als Standard** für
   ein Filament ohne zugewiesene Farbe. Die Okabe/Ito-Ersatzpalette
   (`SLOT_COLOURS`) verschwindet aus der Ansicht — sie war der Grund, aus dem
   Slot 1 (Orange `#e69f00`) von der Auswahlfarbe (`#f0a54a`, Kontrast 1,09)
   nicht zu unterscheiden war. **Orange gehört exklusiv der Auswahl**; solange
   etwas gewählt ist, überdeckt Orange die Filamentfarbe, danach kommt sie
   wieder.
5. **Annahme A — „blau vorschau":** Die Färbe-**Vorschau** (welche Fläche
   gleich gefärbt wird, beim Überfahren/vor dem Übernehmen) zeigt sich
   **Blau** — passend zur bestehenden Blau/Orange-Konvention der
   Differenzansicht. Falls anders gemeint: sagen, es ist ein kleiner Baustein.
6. **Annahme B — „beliebig viele":** Beliebig viele **im Katalog**; je Objekt
   begrenzt weiter `MAX_SLOTS` (Drucker/3MF). Falls die Objektgrenze selbst
   fallen soll, ist das eine eigene Export-Frage.
7. **Migration:** `paint_slot`-Schritte alter Bauart (x/y/z/radius) lassen
   sich nicht in eine Merkmal-Füllung umrechnen (der Punkt kennt kein
   Merkmal). Kein Beispielprojekt nutzt sie; für Kundendateien der Demo gilt
   die Format-Checkliste mit dem frischen Präzedenzfall: `format_version`
   hoch, der Schritt degradiert ehrlich (Befund mit „Werte ansehen", Rest der
   Szene rechnet weiter) statt still etwas anderes zu tun.
8. **Handbuch, Tour, Kataloge ×5** ziehen nach; die Sätze, die den Pinsel
   beschreiben, altern mit ihm (Verneinungssuche nach dem Ausbau).

## Zulieferungen für den Kern (26.08.2026, weitergereicht von 27, Quelle de/d1)

Beide gehören bedacht, **bevor** Katalog und Merkmal-Füllung gebaut sind —
sie lösen sich im neuen Modell auf, wenn man sie mitdenkt, und zementieren
sich, wenn nicht:

- **Die Extruder-Zuordnung ist heute je Platte, nicht je Auftrag** (de,
  belegt): `merge_slots` nummeriert nach dem ersten Auftreten, und
  `write_assembly` ruft es **je Platte** — dieselbe Farbe landet in einem
  Auftrag an verschiedenen Extrudern („Platte 1: Rot = E1; Platte 2:
  Weiß = E1, Rot = E2"), bei vier Filamenten hieße das Umstecken mitten im
  Auftrag. Mit benannten Katalog-Filamenten (Punkt 2) wird
  „Filament → Extruder" eine Eigenschaft des **Auftrags**. Nachstellen:
  zwei Platten, eine davon zweifarbig.
- **`settings.slot_profiles` schlüsselt die Filamentwahl per Position**
  (d1): Sobald Filamente Namen tragen, gehört der Schlüssel auf den Namen
  (oder Name+Farbe) — sonst erbt ein Kunde nach dem Update stumm falsche
  Zuordnungen.
- **Einstellungen je Filament sind von Robert freigegeben, und de baut das
  Modell** (26.08.2026): ein `SlotOverride` je Materialslot, das die vier
  Spulengruppen (`temperatures`, `cooling`, `retraction`, `filament`)
  optional übersteuert, plus `PrintSettings.slot_overrides` und die
  Anwendung in der Slicer-Übergabe. Die Architektur folgt Bauplan §29:
  **Der Filamentkatalog liefert die Vorgabe, der Slot im Projekt
  übersteuert sie** — dieselben drei Ebenen wie überall (Profil → Material
  → Projekt). Für den Katalog heißt das: Er *darf* Spulenwerte tragen
  (dann sind sie die Vorgabe), er *muss* nicht — ohne sie greift schlicht
  das Projekt; vorzubauen ist nichts. Der Anschlusspunkt ist eine
  Funktion Katalogeintrag + `SlotOverride` → Slotwerte, und de richtet
  sie nach 30s Katalogmodell, wenn das anders geschnitten wird — früh
  sagen. Die Bedienung (wo der Kunde die Werte je Slot einstellt) liegt
  beim Filamentwähler, also bei 27. **Gelandet als `1261935f`:** Der
  Anschlusspunkt heißt `handover.settings_for_slot(settings, override)`,
  reist additiv durch die Projektdatei, alte Projekte öffnen unverändert.
- **Korrektur vor dem Kern-Schritt 2, an der Verwendung geprüft (27):**
  `stroke_at` fällt **nicht** — es lebt in `app/core/geom/sculpt.py`, sein
  einziger Aufrufer ist `_on_sculpt` mit den Werten der **Formen**-Leiste
  (Weg 4). Der Satz in Punkt 3 („der Strichpfad (`stroke_at`)") meinte den
  Mal-Klickpfad, und der heißt `_on_paint` → `paint_slot(x/y/z/radius)`.
  Dasselbe gilt für des Doku-Zeile „`strokes` → Striche fällt mit dem
  Pinsel": `strokes` ist der Sammelparameter des Formens und bleibt. Zur
  Weg-4-Sperrliste gehören damit: `stroke_at`, `apply_strokes`,
  `strokes_to_text`, `sculpt_bar`, `set_brush_radius` und der Pinselring
  im Viewport (`_draw_brush` — die Formen-Leiste speist ihn).
- **Ausbau-Ansage (27, von Robert freigegeben):** Der UI-Zug läuft jetzt —
  Werkzeug „Bemalen" (Zeile wird 7 von 8), `paint_bar` samt Overlay und
  Verdrahtung, `_on_paint`-Klickpfad, `set_painting`/`paint`-Zeigerrolle
  und `paintRequested` im Viewport, in **einem** Commit; danach erreicht
  kein Kunde den Punktpfad mehr, der Kern bleibt kompatibel. 30 zieht als
  Schritt 2 die Kernseite nach (`radius`/`x`/`y`/`z` an `paint_slot`,
  Migration, `format_version`) — **nicht `stroke_at`**, siehe Korrektur.
  `kind="feature"` an — daran hängen Dialog-Combo, Klick-Vorbelegung
  (`values_for`) und der Träger-Hash im Cache-Schlüssel, und
  `test_a_feature_parameter_is_declared_as_one` stand rot auf origin.
  Von 27 mit einer Zeile gefixt (`11bfc2ca`, 782 Tests grün) — gehört
  inhaltlich zu deiner Einheit, war nur dringend, weil das Tor aller
  Sitzungen daran hing.

## Bestandsaufnahme Doku-Block (ce, 26.08.2026)

Gemessen über die **Katalogschlüssel**, nicht über den Quelltext: Ein
„radius" in `blend.py` ist eine Verrundung und kein Pinsel — die Rohsuche
meldete allein in `app/ui` 285 Treffer, von denen fast nichts einschlägig ist.

| Ort | Umfang | Anmerkung |
|---|---|---|
| Oberflächentexte „Pinsel" | 26 Quelltexte | verschwinden mit dem Werkzeug |
| Oberflächentexte „Slot" | 22 Quelltexte | werden umformuliert, nicht gelöscht |
| **Kataloge zusammen** | **48 × 5 = 240 Einträge** | |
| Handbuch (`manual.py`) | 14 Stellen | darunter ein ganzer Abschnitt |
| Website erzeugt | 6 Seiten | zieht aus `manual.py` nach, kein Handbetrieb |
| Website von Hand | `index.html` (2), `en/features.html` (1) | |
| Changelog | 5 Stellen | **bleiben** — Geschichte wird nicht umgeschrieben |
| Tour | 0 Stellen | nichts zu tun |
| Abbildungen | `figures.py:139` | muss **neu gerendert** werden |

**Drei Stellen, die man leicht übersieht:**

1. `manual.py:290` heißt **„Bewegen und Bemalen"** — der Abschnitt braucht
   einen neuen Titel, nicht nur neue Sätze.
2. `manual.py:201` schreibt die Werkzeugzahl aus („von links nach rechts auf
   Alt+1 bis Alt+8"). Fällt *Bemalen* aus der Leiste, altert der Satz mit.
3. `figures.py:139` beschriftet die Werkzeugleiste mit „Schnitt · Messen ·
   Bewegen · Analyse · Bemalen". Das ist ein **Bild**, kein Text — es wird
   gerendert und nicht übersetzt.

### Nachtrag: Was die Textsuche verpasst — und was sie zu viel findet

Die Zählung oben sucht im **Text** der Katalogschlüssel. Die Werte-Labels in
`app/ui/labels.py` entziehen sich dem, weil dort der *Schlüssel* englisch ist
und der Text die Sache anders benennt. Am Schlüssel nachgesucht, mit beiden
Fehlerrichtungen:

| `labels.py` | Text | |
|---|---|---|
| `slot` (Z. 844) | „Platz" | **verpasst** — muss mit |
| `slots` (Z. 845) | „Plätze" | **verpasst** — muss mit |
| `strokes` (Z. 852) | „Striche" | ~~verpasst~~ **Falschtreffer — nicht anfassen** |
| `brush` (Z. 717) | „Pinsel" | gefunden |
| `slot` (Z. 510, 630) | „Langloch" | **Falschtreffer — nicht anfassen** |
| `radius` (Z. 819) | „Radius" | **Falschtreffer — nicht anfassen** |

Die beiden Falschtreffer sind der lehrreichere Teil: `slot` heißt an zwei
Stellen **Langloch** — ein Schlitz für Schrauben, die Spiel brauchen —, und
`radius` gehört zu Bohrungen und Verrundungen (`brep/features.py`,
`perceive/features.py`). Wer den Umbau am Schlüsselnamen entlangfährt,
benennt sie mit um und macht aus einer Bohrungsangabe eine Filamentangabe.

**Berichtigt am 26.08.2026, eine Stunde später:** `strokes` stand hier
zuerst als vierter Pinsel-Kandidat — falsch. Es ist der Sammelparameter des
**Formens**: `stroke_at` lebt in `app/core/geom/sculpt.py`, die Leiste dazu ist
`sculpt_bar.py`, und `values={"strokes": …}` kommt aus drei Stellen in
`sculpt.py`. Wer es mit dem Pinsel ausbaut, reißt das Formen mit. Gefunden hat
es 27 beim Vorbereiten ihres Ausbau-Zuges.

Der Fehler ist derselbe, vor dem der Absatz darunter warnt — begangen im
Absatz darüber, im selben Nachtrag: Ich habe `strokes` am Namen zugeordnet
und die Verwendung nicht nachgesehen. Die Regel taugt nur, wenn man sie auf
den eigenen Treffer anwendet.

**Die Regel daraus:** Weder Text- noch Schlüsselsuche allein trägt. Die
Textsuche verpasst, was anders heißt; die Schlüsselsuche findet, was zufällig
gleich heißt. Jeder Treffer wird an seiner Verwendung geprüft, nicht am Namen.

### Was schon gemessen ist — und warum trotzdem noch nichts geschrieben wird

Der Färbeweg über das Kontextmenü ist am echten Fenster durchgeklickt (27,
26.08.2026, Prüfstand mit Bild): Quader → Fläche im Baum → Rechtsklick →
Dialog öffnet mit einer Merkmal-Combo, vorbelegt auf die angeklickte Fläche.

**Zwei Fundstücke, die den Handbuchsatz verändert hätten:**

1. „Bemalen" steht **nicht** direkt im Rechtsklick-Menü, sondern unter
   **„Vorbereiten → Bemalen"** — die Kategorie wird am Flächenklick gefaltet.
   Ein Satz ohne das Untermenü schickte den Kunden auf die Suche.
2. Der Weg trug **erst seit** dem Fix an `paint_slot` (`kind="feature"`,
   `11bfc2ca`). Davor war die Vorbelegung tot, und derselbe Satz wäre wörtlich
   richtig und in der Sache falsch gewesen.

**Geschrieben wird trotzdem noch nicht**, und das ist der Punkt: Das Feld
daneben heißt heute „Slot" mit Nummer 0–7, und Radius samt Punktpfad stehen
noch im Dialog. Beides fällt mit den nächsten Schritten. Ein Handbuch, das
einen **Übergangszustand** beschreibt, ist falsch, sobald der Übergang durch
ist — und niemand merkt es, weil kein Test einen Satz prüft.

Daraus die Arbeitsregel für diesen Block: **Sätze über einen Bedienweg
entstehen, wenn der Weg gemessen läuft *und* der Zielzustand erreicht ist** —
nicht wenn er gebaut ist, und nicht solange daneben noch etwas steht, das
verschwinden soll.

**Reihenfolge beim Scharfschalten:** `manual.py` zuerst (die Website folgt aus
ihm), dann die Kataloge, dann die Abbildung. Die Fundstellen liegen
zeilengenau vor.

## Aufteilung

| Teil | Wer |
|---|---|
| Kern: Merkmal-Füllung, Pinsel-Ausbau, Migration, Filamentkatalog, Farbmodell (Grau/Orange-Exklusiv in `theme`) | 3d-druck-30 |
| Oberfläche: Filamentwähler mit Farbpalette + Katalog, Kontextmenü, Werkzeugzeile/`paint_bar`-Ausbau, Blau-Vorschau | **3d-druck-27** (Board-Claim steht) |
| Handbuch, Tour, Übersetzungen | **de** (Board-Claim steht) |

## Die Verträge, die die Oberfläche vom Kern braucht (27, Regel 5)

Die Oberfläche ist gesichtet (Bestand: `paint_bar` 180 Zeilen, das Overlay
und der `stroke_at`-Pfad im Fenster, Pinselring und `_slot_colours` im
Viewport). Gebaut wird gegen diese vier Verträge — 30 legt sie fest, hier
stehen die Wünsche der Gegenseite:

1. **Filamentkatalog:** Modulpfad und Signaturen — erwartet wird etwas wie
   `filaments() -> list[Filament]`, `save_filament(...)`,
   `remove_filament(...)` mit `Filament = (name, colour)`, Ablage im Profil
   (§38-Umbiegung greift dann in der Suite von selbst).
2. **Farbmodell in `theme`:** der Ersatz für `slot_colour(index)` — eine
   Funktion, die aus einem `MaterialSlot` die Anzeigefarbe macht, mit
   **Grau** als Fallback statt Okabe/Ito, dazu die Grau-Konstante und das
   Vorschau-Blau als benannte Werte. Die Orange-überdeckt-Regel setzt der
   Viewport um (`_slot_colours` ist bei 27), aber die Farben kommen aus
   `theme`.
3. **Die Ops:** Bleibt der Registername `paint_slot` (dann mit
   `at_feature` statt x/y/z/radius), oder kommt ein neuer? `assign_slot`
   unverändert? Die Antwort entscheidet Kontextmenü-Verdrahtung und
   Draft-Bau im Fenster.
4. **Reihenfolge beim Landen:** Der Ausbau von Werkzeug „Bemalen",
   `paint_bar` und Pinselring geht zusammen mit dem Kern-Ausbau von
   `stroke_at` in **einem** abgestimmten Zug — je ein halber Stand wäre
   ein Fenster mit Knopf ohne Rückgrat oder Rückgrat ohne Knopf.
