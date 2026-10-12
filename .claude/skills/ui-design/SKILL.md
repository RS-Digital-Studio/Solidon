---
name: ui-design
description: >
  Entwirft und prüft die visuelle Gestaltung von Solidon und seiner Website:
  Hierarchie, Typografie, Abstände, Informationsdichte, Zustände und Anpassung
  an Fenstergröße, Skalierung und lange Sprachfassungen; setzt auf Auftrag um.
  Benutzen bei Gestaltungsaufträgen und visuellen Reviews. Bedienabläufe über
  /ux-review, Qt-Umsetzung größerer Ansichten über den Agenten
  solidon3d-oberflaeche.
argument-hint: "[Ansicht, Seite oder Gestaltungsfrage]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Oberfläche gestalten

## Ausgangspunkt

Die konkrete Ansicht und das Nutzerziel bestimmen; den Bereich über `/bauplan`
nachlesen (§2, §18, §19). Die wirkliche Ansicht untersuchen, wenn sie
zugänglich ist; ohne sie Aussagen als Codebefund oder Entwurf kennzeichnen. Ein
Mockup ist kein Bildschirmfoto der Anwendung.

Für die App gelten `.claude/rules/oberflaeche.md` und, wo berührt,
`fenster.md` und `grenzen.md`; die Gestaltungswerte stehen in `app/ui/theme.py`,
`style.py` und `palette.py`. Für die Website `website/CLAUDE.md`,
`website/README.md`, `style.css` und die betroffenen Seiten. Bestehende
Komponenten und Werte vor neuen.

## Gestaltungsentscheidung

Mit dem größten konkreten Problem beginnen: unklare Hauptaktion, fehlende
Gruppierung, abgeschnittener Inhalt, schwer lesbarer Zustand. Die Änderung am
Nutzerziel und an der sichtbaren Wirkung begründen. Ein Gestaltungsauftrag
rechtfertigt keine neue Produktfunktion und keinen Wechsel des UI-Frameworks.

| Bereich | Prüffragen |
|---|---|
| Hierarchie | Was fällt zuerst auf, was gehört zusammen, welche Handlung ist jetzt wichtig? |
| Typografie | Sind Beschriftungen, Werte, Einheiten und längere übersetzte Texte lesbar und sauber ausgerichtet? |
| Raum | Bleibt genug Platz für Modell beziehungsweise Inhalt? Sind Gruppen und Abstände konsistent? |
| Zustände | Sind Auswahl, Fokus, Hover, deaktiviert, leer, beschäftigt und Fehler unterscheidbar? |
| Skalierung | Was passiert bei kleinem Fenster, HiDPI, größerer Schrift und langen Sprachfassungen? |
| Zugänglichkeit | Tragen Farbe und Symbole eine zweite Kodierung? Sind Fokus, Kontrast und Bedienflächen erkennbar? |

Für die Website ist [WCAG 2.2](https://www.w3.org/TR/WCAG22/) eine technische
Referenz; das vereinbarte Zielniveau prüfen. CSS-Pixelwerte nicht ungeprüft auf
Qt-Gerätepixel übertragen. Eine Sichtprüfung bestätigt keine Norm- oder
Rechtskonformität.

Eine Konzeption liefert konkrete Ansichten oder ein genaues Layout mit den
vorhandenen Komponenten; eine Gestaltungsfrage entscheidest du begründet
selbst, statt Varianten zur Wahl zu stellen. Ist Umsetzung beauftragt, wird
der Entwurf umgesetzt, ohne zusätzliche Freigabe für rücknehmbare Änderungen.
Ändert sich dabei der Bedienweg, zusätzlich `/ux-review`.

## Kriterien des Funktionsdurchgangs

Die eine Quelle für Gestaltung (G), zeitgemäß (Z) und innovativ (I) im
Funktionsdurchgang (`konzepte/konzept-funktionsdurchgang-2026-10.md` §4); Stufe
A misst der Prüfstand, B urteilt am Bild, C von Hand. Die Zahlen hält
`tools/function_checks.py`, ein Test hält beide gleich. Ein Fix aus Z oder I
zählt nur, wenn E und V an derselben Zeile nicht schlechter werden und er im
gewöhnlichen Weg sichtbar ist. G9 ist höchstens *leicht*; I1, I5 und der
Chatweg zu I6 sagt der Bauplan zu, ihr Fehlen ist ein Fund; den Chatweg führt
Prüfpunkt 17, Vorschlag ist bei I6 nur die Suche mit Frageformen.

| Kennung | Zählgröße | Schwelle | Stufe | Messung |
|---|---|---|---|---|
| G1 | Hauptknöpfe und Akzentflächen im Ruhezustand | ≤ 1 Hauptaktion je Dialog oder Karte (ohne Handlung keine), ≤ 1 Akzent je Fenster | A | `layout` |
| G2 | Abstände | Vielfaches von `SPACE` (4), je Gruppe einheitlich | A | `layout` |
| G3 | Ausrichtung | Beschriftungen, Felder, Einheiten bündig; Werte rechtsbündig mit Einheit | A | `layout` |
| G4 | Schrift | nur die vier Stufen aus `LEVELS`; keine feste Größe oder Farbe außerhalb der Gestaltungswerte | A | `fonts` |
| G5 | Zustände: Hover, Fokus, gedrückt, deaktiviert, beschäftigt, Fehler | je sichtbar unterscheidbar, zweite Kodierung, Fokus immer sichtbar | A misst, B urteilt | `state_images` |
| G6 | Kontrast von Text und Symbolen | ≥ 4,5 : 1, große Schrift und Symbole ≥ 3 : 1, hell und dunkel | A | `contrast` |
| G7 | Symbole | Symbol aus `icons`, Tooltip mit Name und Kürzel, ein Stil | A | `icons` |
| G8 | Bewegung | Übergang aus `motion`, 110–220 ms, abschaltbar, kein Sprung ohne Übergang | A | `animations` |
| G9 | Direkt statt Formular | Gestaltungsurteil, höchstens leicht | B | Bild |
| Z1 | Ziehen: Griff, Geist und Zahl am Zeiger | ≤ 33 ms bis zum nächsten Bild, umgerechnet auf den Referenzrechner | A | `frames` |
| Z2 | Nicht-modal | `activeModalWidget()` leer, außer den Ausnahmen aus Konzept §4 | A | `modals` |
| Z3 | Am Objekt: Handlung ohne Menü und Suche nach dem Klick auf die Stelle | ja je Zeile mit Merkmals- oder Körperbezug | A misst, B urteilt | `steps` |
| Z4 | Leere Zustände führen weiter | Knopf zur nächsten Handlung | B, A listet | `empty_states` |
| Z5 | Rohe Qt-Fenster im Kundenweg | 0, außer `QFileDialog` und den Ausnahmen aus Z2 | A | `raw_windows` |
| Z6 | Größen und Skalierungen | 1920 × 1080 logisch (maximiert, Taskleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100, 150, 200 %, solange ≥ 1920 × 1080 logisch; hell und dunkel gleiche Flächen und Akzente | A | `scrollbars`, `icons` |
| Z7 | Die ersten fünf Minuten | Schritte und Fehlklicks, jeder Fehlklick ein Fund | C | Protokoll der Stufe C |
| I1 | Merkmal statt Dreieck: Name und Maß beim Überfahren | ja an jeder erkannten Art | A misst, B urteilt | `hover_labels` |
| I2 | Druckfolge im Vorschauband | ja an jeder Zeile mit gerechneter Vorschau | A misst, B urteilt | `preview.banner_text` |
| I3 | Vorschlag statt Suche | ≥ 80 % der häufigsten Kundenziele | A | `steps` gegen `tests/data/common_goals.toml` |
| I4 | Befund mit Lösung | Zahl genannt; jede Art ohne Handlung ist ein Vorschlag | A | Befundarten und ihre Handlungen |
| I5 | Vorher und nachher mit einem Klick | ja an der Zeile Vorher/Nachher | A misst, B urteilt | `steps` |
| I6 | Sagen statt suchen: Suchproben als Frage | Treffer unter den ersten drei | A | `search` |

## Umsetzung und Sichtprüfung

An der zuständigen Quelle ändern: sichtbare App-Texte über `tr()` und alle
Kataloge, Website-Strukturänderungen über alle Sprachseiten. Werbeaussagen
müssen zum nachgewiesenen Produktverhalten passen.

Vorher und nachher bei gleicher Fenstergröße und gleichem Zustand vergleichen;
hell und dunkel, die betroffenen Interaktionszustände und mindestens eine lange
Sprachfassung prüfen, bei abgeschnittenen Inhalten alle Fassungen. Die
tatsächliche Skalierung notieren, statt HiDPI-Tauglichkeit aus einem
Bildschirmfoto abzuleiten.

App-Sichtprüfung am echten Fenster mit realen Schriften — offscreen belegt
Logik und Bindungen, nicht das Bild; ohne Fensterzugang bleibt der visuelle
Nachweis offen. Website-Abnahme über `/website-review`. Release-Bilder nur auf
Auftrag über `/erzeugen`; Prüfbelege außerhalb des Auslieferungspfads.

Bei Codeänderungen die betroffenen Tests über `/pruefen` mit Dateipfaden.
Melden: die Verbesserung, geänderte Ansichten, Belege, geprüfte Zustände,
Testzahlen und offene Punkte. Geschmack als Gestaltungsentscheidung
kennzeichnen, nicht als bewiesenen Fehler.
