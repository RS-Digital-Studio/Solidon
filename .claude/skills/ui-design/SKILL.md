---
name: ui-design
description: >
  Entwirft und prüft die visuelle Gestaltung von Solidon und seiner Website:
  Hierarchie, Typografie, Abstände, Informationsdichte, Zustände und Anpassung
  an Fenstergröße und Skalierung. Benutzen bei Gestaltungsaufträgen und
  visuellen Reviews; Bedienabläufe über ux-review, reine Fehlerdiagnose am Code.
---

# Oberfläche gestalten

## Ausgangspunkt

Bestimme die konkrete Ansicht und das Nutzerziel. Lies `/bauplan` für den
betroffenen Bereich und die vorhandenen Gestaltungsvorgaben. Untersuche die
wirkliche Ansicht, wenn sie zugänglich ist; ohne sie kennzeichne Aussagen als
Codebefund oder Entwurf. Ein Mockup ist kein Screenshot der Anwendung.

Für die App: passende `CLAUDE.md`-Karten, `.claude/rules/oberflaeche.md` und
`app/ui/theme.py`, `style.py`, `palette.py`. Für die Website:
`website/CLAUDE.md`, `website/README.md`, `style.css` und betroffene Seiten.
Verwende bestehende Komponenten und Gestaltungswerte, bevor du neue anlegst.
Die Umsetzungshinweise von `.claude/agents/solidon3d-oberflaeche.md` bleiben
maßgeblich für Qt; ihre Lektüre ist kein Auftrag zur Delegation.

## Gestaltungsentscheidung

Beginne mit dem größten konkreten Problem: unklare Hauptaktion, fehlende
Gruppierung, abgeschnittener Inhalt oder ein schwer lesbarer Zustand.
Begründe die Änderung am Nutzerziel und an der sichtbaren Wirkung. Ein
Gestaltungsauftrag allein rechtfertigt keine neue Produktfunktion oder einen
Wechsel des UI-Frameworks.

| Bereich | Prüffragen |
|---|---|
| Hierarchie | Was fällt zuerst auf, was gehört zusammen, welche Handlung ist jetzt wichtig? |
| Typografie | Sind Beschriftungen, Werte, Einheiten und längere übersetzte Texte lesbar und sauber ausgerichtet? |
| Raum | Bleibt genug Platz für Modell beziehungsweise Inhalt? Sind Gruppen und Abstände konsistent? |
| Zustände | Sind Auswahl, Fokus, Hover, deaktiviert, leer, beschäftigt und Fehler unterscheidbar, soweit vorhanden? |
| Skalierung | Was passiert bei kleinem Fenster, HiDPI, größerer Schrift und langen Sprachfassungen? |
| Zugänglichkeit | Tragen Farbe und Symbole eindeutige zweite Hinweise? Sind Fokus, Kontrast und Bedienflächen tatsächlich erkennbar? |

Für Web-Zugänglichkeit ist [WCAG 2.2](https://www.w3.org/TR/WCAG22/) eine
technische Referenz; prüfe das vereinbarte Zielniveau und die aktuelle Fassung.
Übertrage CSS-Pixelwerte nicht ungeprüft auf Qt-Gerätepixel. Eine visuelle
Prüfung bestätigt keine vollständige Norm- oder Rechtskonformität.

Bei einer ausdrücklich gewünschten Konzeption liefere konkrete Ansichten
oder ein genaues Layout mit den vorhandenen Komponenten. Zeige Alternativen
nur bei einer echten Abwägung. Wenn Umsetzung beauftragt ist, setze den
begründeten Entwurf um; verlange keine zusätzliche Freigabe für bereits
autorisierte, rücknehmbare Änderungen. Größere Änderungen des Bedienwegs
werden zusätzlich mit `/ux-review` geprüft.

## Umsetzung und Sichtprüfung

Ändere an der zuständigen Quelle. Sichtbare App-Texte über `tr()` und alle
Sprachkataloge; Website-Strukturänderungen über alle betroffenen Sprachseiten.
Geometrie bleibt im Kern und wird über Ops geändert. Inhaltliche Werbeaussagen
müssen zum nachgewiesenen Produktverhalten passen.

Vergleiche vorher und nachher bei gleicher Fenstergröße und gleichem Zustand.
Prüfe die geänderten Komponenten in hell/dunkel, den betroffenen Interaktions-
zuständen und mindestens einer langen Sprachfassung. Bei abgeschnittenen
Inhalten prüfe alle betroffenen Fassungen. Notiere die tatsächlich verwendete
Skalierung, statt aus einem normalen Screenshot HiDPI-Tauglichkeit abzuleiten.

Website-Abnahme über `/website-review`; App-Sichtprüfung am echten Fenster
mit realen Schriften. Offscreen-Tests belegen Logik und Bindungen, nicht den
sichtbaren Renderzustand. Ist der Zugang zum Fenster nicht möglich, bleiben
die entsprechenden visuellen Nachweise offen. Release-Bilder nur im Auftrag
über `/erzeugen` neu erzeugen; Review-Belege außerhalb des Auslieferungspfads.

Bei Codeänderungen betroffene Tests über `/pruefen` mit Dateipfaden ausführen.
Melde die konkrete Verbesserung, geänderte Ansichten, Belege, geprüfte
Zustände, Testzahlen und offene Punkte. Geschmack als Gestaltungsentscheidung
kennzeichnen, nicht als objektiv bewiesenen Fehler.
