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
