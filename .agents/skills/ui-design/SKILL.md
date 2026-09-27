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

Die konkrete Ansicht und das Nutzerziel bestimmen; den Bereich über `.agents/skills/bauplan/SKILL.md`
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
Ändert sich dabei der Bedienweg, zusätzlich `.agents/skills/ux-review/SKILL.md`.

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
Nachweis offen. Website-Abnahme über `.agents/skills/website-review/SKILL.md`. Release-Bilder nur auf
Auftrag über `.agents/skills/erzeugen/SKILL.md`; Prüfbelege außerhalb des Auslieferungspfads.

Bei Codeänderungen die betroffenen Tests über `.agents/skills/pruefen/SKILL.md` mit Dateipfaden.
Melden: die Verbesserung, geänderte Ansichten, Belege, geprüfte Zustände,
Testzahlen und offene Punkte. Geschmack als Gestaltungsentscheidung
kennzeichnen, nicht als bewiesenen Fehler.
