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

## Aufteilung

| Teil | Wer |
|---|---|
| Kern: Merkmal-Füllung, Pinsel-Ausbau, Migration, Filamentkatalog, Farbmodell (Grau/Orange-Exklusiv in `theme`) | 3d-druck-30 |
| Oberfläche: Filamentwähler mit Farbpalette + Katalog, Kontextmenü, Werkzeugzeile/`paint_bar`-Ausbau, Blau-Vorschau | offen (27/d1/de angefragt) |
| Handbuch, Tour, Übersetzungen | offen (angefragt) |
