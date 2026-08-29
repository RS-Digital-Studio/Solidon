# Konzept — ein Befehlsband, das die Auswahl versteht

> **Stand 29.08.2026 · entschieden.** Dieses Dokument hält die Entscheidung
> über die obere Bedienzone fest. Die verbindliche Fenstergrenze bleibt
> Bauplan §2.5; den Umsetzungsstand führt ausschließlich `ROADMAP.md`.

## Anlass

Die Oberfläche bot dieselbe Anwendung in drei waagerechten Schichten an:
Menüleiste, obere Werkzeugleiste und schwebende Werkzeugzeile. Das ist nicht
nur unruhig. Ein Kunde ohne CAD-Erfahrung muss zuerst entscheiden, **in
welcher Leiste** eine Handlung wohnen könnte, und erst danach nach der
Handlung suchen.

Der Vergleich vom 27.08.2026 hat die Größe des Problems gemessen: 47 der 91
Operationen lagen drei Klicks tief. Die bereits umgesetzte Abflachung verkürzt
22 davon auf zwei Klicks. Sie ändert aber nichts an den drei konkurrierenden
Orten.

Roberts Auftrag vom 29.08.2026 — für Kunden ohne CAD-Kenntnisse einfach,
schön und modern zu werden und die Befunde sauber zu beheben — entscheidet
deshalb die in `ROADMAP.md` beschriebenen Wege B und C gemeinsam.

## Die Entscheidung

Solidon bekommt **ein benanntes Befehlsband**. Es ersetzt die sichtbare
Menüleiste, die bisherige obere Werkzeugleiste und die schwebende
Werkzeugzeile. Es trägt keine Arbeitsbereichs-Reiter und schaltet nicht
zwischen „Bearbeiten“ und „Konstruieren“ um: Es gibt weiterhin genau den
Zustand der Szene, wie Bauplan §2.5 verlangt.

Das Band hat drei Teile, die ihre Plätze nie tauschen:

1. **Hauptwege links.** Menü, neues Projekt, öffnen, speichern, Modell
   einfügen, zeichnen und formen. Symbol und Wort stehen zusammen.
2. **Passend zur Auswahl in der Mitte.** Höchstens vier direkt ausführbare
   Operationen aus `applies_to`. Die Überschrift nennt den Bezug, etwa
   „Passend zu: Bohrung“. Der Platz bleibt derselbe; nur sein Inhalt folgt der
   Auswahl. Ein fester Knopf „Alle Befehle“ öffnet die bereits vorhandene
   Befehlspalette, in der die übrigen passenden Operationen vorn stehen.
3. **Projektzustand rechts.** Projektname, Außenmaß, Drucker, Material und
   gegebenenfalls Druckplatte. Diese Angaben erklären, wofür Passungen und
   Größen gerade gerechnet werden.

Die Ansichtswerkzeuge — Schnitt, Messen, Bewegen, Analyse, Schichten,
Explosion und Trennen — bilden die zweite Zeile **desselben** Bandes. Öffnet
eines davon seine Werte, erscheinen diese darunter im Band und nicht als neue
schwebende Karte über dem Modell. Skizze, Formen und Skelett benutzen denselben
Platz während ihrer laufenden Geste. Das ist ein Zustandsangebot, kein neuer
Arbeitsbereich.

## Was vollständig erreichbar bleibt

Die alte Menühierarchie verschwindet nicht aus dem Programm. Ein beschrifteter
Knopf „Menü“ öffnet sie vollständig; ihre Tastenkürzel gelten weiter. Die
Befehlspalette bleibt der universelle Suchweg. Bausteine bleiben im Katalog
mit Bildern, weil eine Textzeile für ein räumliches Teil die schlechtere
Darstellung ist. Ansichtsentscheidungen bleiben an der Ansicht.

Damit gibt es drei Tiefen, aber nur einen sichtbaren Ausgangspunkt:

- häufig und eindeutig: direkt im festen Teil des Bandes;
- gerade passend: direkt in der Kontextgruppe;
- selten oder unbekannt: Menü oder Befehlspalette.

## Warum die Kontextgruppe nicht springt

Ein vollständig dynamisches Band wäre am ersten Tag kurz und am zweiten Tag
unauffindbar. Darum ändern sich weder die Hauptwege noch die Lage der
Kontextgruppe. Wenn keine verwertbare Auswahl besteht, erklärt der Abschnitt
in einem Satz, wie er gefüllt wird. Bei einer Auswahl ändern sich nur seine
bis zu vier Knöpfe. Bedeutung entsteht durch Überschrift, Wort und
Bedienzustand, nie allein durch Farbe.

Die Auswahlreihenfolge wird nicht in der Oberfläche erfunden. Operationen
kommen aus dem Register, Eignung aus `applies_to`, Verfügbarkeit aus derselben
`QAction`, die Menü und Befehlspalette bereits pflegen. Baustein-Operationen
werden nicht als vier zufällige Namen herausgegriffen; sie führen in den
Bildkatalog.

## Breite und Verkleinerung

Bei 1280 Bildpunkten stehen die Hauptwege mit Wort und Symbol im Band. Reicht
die Breite nicht, wandern zuerst Kontextoperationen hinter „Alle Befehle“,
danach seltenere Hauptwege in den beschrifteten Menüknopf. Der Projektzustand
kürzt erklärenden Nebentext, nie den Projektnamen. Es entstehen keine
unbeschrifteten Symbolknöpfe und keine waagerechte Bildlaufleiste.

## Abnahmesätze

Das Ergebnis ist nur dann dieses Konzept, wenn alle folgenden Aussagen
zugleich stimmen:

- Über der Drei-Zonen-Fläche steht genau ein sichtbares Befehlsband.
- Neu, Öffnen, Speichern, Einfügen, Zeichnen und Formen behalten feste Plätze.
- Eine Bohrungs-, Flächen- oder Körperauswahl aktualisiert nur die benannte
  Kontextgruppe.
- Jede Operation bleibt über Menü oder Befehlspalette erreichbar.
- Ausgegraute Kontextaktionen nennen denselben Grund wie Menü und Palette.
- Startbildschirm, Skizze und laufende Gesteneditoren erzeugen kein zweites
  konkurrierendes Band.
- Die Darstellung bleibt mit Tastatur, hellem und dunklem Thema sowie bei
  1280 Bildpunkten vollständig verständlich.

## Zwei Sätze, die über diesen Umbau hinaus gelten

**Dynamik braucht einen festen Rahmen.** Eine Oberfläche darf auf die Auswahl
reagieren, wenn Ort, Überschrift und Rückweg unverändert bleiben.

**Ein seltener Befehl braucht Suche, kein dauerhaftes Möbelstück.** Sichtbare
Fläche gehört den häufigen Handlungen; Vollständigkeit leisten Menü und
Befehlspalette.
