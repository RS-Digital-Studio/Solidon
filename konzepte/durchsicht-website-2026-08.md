# Durchsicht: die Website gegen die Begehrlichkeits-Referenzen

**Stand:** Erhebung abgeschlossen, 30.08.2026 · **Anlass:** Roberts Order —
die ganze Website moderner, innovativer, optimiert; Ziel ist das „das will
ich haben"-Gefühl · **Register:** die W-Pakete in `ROADMAP.md` (Zeile W1)

**Methode:** Referenz-Recherche über zehn Sites in drei Gruppen —
Nachbarschaft (Bambu Lab, Prusa, Elegoo, Orca), Begehrlichkeits-Vorbilder
(Linear, Raycast, Arc, Figma), 3D-Tools (Shapr3D, Plasticity; Bambu und
Plasticity live im Browser besichtigt, da per Abruf gesperrt) — plus
Bestandsaufnahme der eigenen Seiten (index/style/site.js/funktionen, sechs
Sprachfassungen strukturell, Werkzeugkette make_web_images/stamp_assets/
make_video, Außenadressen-Wächter).

Die Statustabellen dieses Dokuments altern — offene Arbeit steht im Register.

---

## Die zwölf übertragbaren Muster

| # | Muster | Vorbild | Warum es wirkt |
|---|---|---|---|
| M1 | Produkt im echten Fenster als Hero, ein Satz, ein CTA | Linear, Arc | Nichts konkurriert — die Entscheidung ist vorbereitet, bevor gelesen wird |
| M2 | Kurze Autoplay-Loops statt Standbilder, je Feature einer | Plasticity (hero.mp4 + fünf Loops, gemessen im Live-DOM) | Man sieht die Fase entstehen, nicht das Ergebnis — der stärkste Begehrlichkeits-Hebel bei 3D-Werkzeugen |
| M3 | Das Kaufmodell ist die Headline | Plasticity („no subscription" als H1) | Räumt die größte Kaufangst zuerst aus |
| M4 | Dunkle, kinoreife Produktbühne | Bambu, Plasticity | Dunkel = Kino, hell = Broschüre; das Produkt leuchtet |
| M5 | Fremde Stimmen als eigenes Band | Prusa, Bambu, Linear, Raycast | Begehrlichkeit ist sozial — „andere wollen es schon" |
| M6 | Zeigen, was Menschen damit gemacht haben | Bambu/MakerWorld, Prusa/Printables, Figma | Der Kunde kauft das fertige Teil in seiner Hand |
| M7 | Ein CTA-Ziel, rhythmisch wiederholt | Arc, Orca | Jeder Überzeugungspunkt bietet dieselbe eine Handlung |
| M8 | Feature-Tabs über einer Demo-Bühne | Plasticity, Raycast | Die Seite bleibt kurz und lädt zum Spielen ein |
| M9 | Konkrete Vorteilszahlen als Band | Prusa, Orca | Zahlen lesen sich als Beweis, nicht als Behauptung |
| M10 | Vorher/Nachher als Bild | Linear, Prusa | Transformation ist die überzeugendste Bildform für „aus kaputt wird druckbar" |
| M11 | Typografie als Markenzeichen | Plasticity, Linear, Bambu | Die Schrift trägt das Qualitätsversprechen vor dem ersten Wort; keine Referenz nutzt Systemschrift |
| M12 | Bewegung genau dosiert, nie dekorativ | Linear, Raycast | Eine beweisende Bewegung je Sektion wirkt teuer, mehr wirkt billig |

## Was schon stark ist und bleibt

Die Hero-Headline („Aus STL wird das Teil, das du brauchst") ist besser als
die meisten Referenzen; die Schmerzpunkt-Sektion mit vier Kundenzitaten ist
ein Muster, das die Referenzen nicht haben; Ehrlichkeitsblock und
Preisklarheit erfüllen M3 faktisch schon („einmal kaufen statt abonnieren"
samt Abo-Vergleichsrechnung); die dunkle Screenshot-Bühne, die testgesicherte
Zahlenleiste, FAQ mit Schema-Auszeichnung, Barrierefreiheit und die
„nichts von außen"-Haltung.

## Die Befunde

| Nr. | Fundort | Ist → Soll | Schwere |
|---|---|---|---|
| WB1 | Hero (index 206–301) | Ein Dutzend konkurrierende Botschaften, Spendenkasten mit Rechtstext direkt unterm Produktbild — die Spende bittet um Geld, bevor das Produkt begehrt wird → M1: eine Botschaft, ein Bild, ein CTA | **hoch** |
| WB2 | ganze Site | Nirgends bewegt sich das echte Produkt (SVG-Vignetten zeigen Cartoons) → M2-Loops; `make_video.py` liefert ruckelfreie Aufnahmen bereits | **hoch** |
| WB3 | ganze Site | Null fremde Stimmen, obwohl die 0.2.2-Pressekampagne läuft und `count.php` zählt → M5-Band, gefüllt aus den Rückläufen | **hoch** |
| WB4 | #generiert | Ergebnisbilder nur für Weg 3; für die Kernwege kein Foto eines real gedruckten Teils → M6/M10, Vorher/Nachher für Weg 1 | **hoch** |
| WB5 | style.css 83 | `system-ui` ohne Markenstimme, H1 zurückhaltend → M11; selbst gehostetes woff2 ist erlaubt, stamp_assets stempelt es schon | mittel |
| WB6 | CTAs | Ziele wechseln zwischen #preis und #download → M7: ein Ziel überall | mittel |
| WB7 | #wege | Das Herzstück nur als Vignetten, nie als Produkt → M8: eine Bühne mit vier Tabs oder je Weg ein Loop | mittel |
| WB8 | Screenshots | Vollfenster auf Mobil bei 23 % (Beschriftungen 3,3 px) → Ausschnitte, wo ein Detail die Aussage trägt; make_web_images kann zuschneiden | mittel |
| WB9 | Hero-Erzählung | Demo-Logistik dominiert die Begehrlichkeit → erst wollen machen, dann Konditionen | mittel |
| WB10 | Farbwelt | Hell ist Default, die App ist dunkel — Kino-Frage → M4; **Geschmacksentscheidung für Robert** | gering–mittel |
| WB11 | Zahlenband | Zahlen ohne Sprung zum Beleg → M9: jede Zahl verlinkt ihren Beweis | gering |
| WB12 | sechs Sprachen | Strukturänderungen sind Handarbeit ×6 — Randbedingung, die die Umbaugröße je Schritt begrenzt | (Randbedingung) |

**Werkzeugketten-Verträglichkeit:** Selbst gehostete Loops sind mit „nichts
von außen" vereinbar (der Wächter verbietet nur fremde Adressen). Zwei
Vorarbeiten: `stamp_assets.py` kennt mp4/webm noch nicht (SUFFIXES), und der
Upload schafft ~1,8 MB/s — Loops daher 720p, 5–15 s, 2–5 MB, mit poster-PNG
und Standbild bei `prefers-reduced-motion`.

## Der Empfehlungs-Dreiklang

1. **Das Produkt in Bewegung zeigen** (WB2/WB7): Hero-Loop „STL hineinziehen →
   Prüfbericht springt an → Bohrung anklicken → Maß ändern → druckbar", dazu
   je Weg ein kurzer Loop. Der teuerste Referenz-Effekt mit fast fertiger
   Infrastruktur — kein anderer Umbau erzeugt mehr „will ich haben".
2. **Den Hero auf eine Botschaft entrümpeln** (WB1/WB6/WB9): Kicker, H1,
   Lead, ein Download-Knopf, sechs Zusagen als eine Zeile, Produktbild/-
   video; Spende in einen eigenen Abschnitt, Demo-Logistik zur Preis-Sektion,
   alle CTAs auf ein Ziel.
3. **Beweis durch Ergebnisse und Stimmen** (WB3/WB4): Galerie real gedruckter
   Teile (Fotos, nicht Renderings), Vorher/Nachher für Weg 1, Social-Proof-
   Band aus den Presse-Rückläufen; bis dahin tragen Beispielprojekte und
   Downloadzahl.

Sekundär: Display-Schrift (WB5), verlinkte Zahlen (WB11).
