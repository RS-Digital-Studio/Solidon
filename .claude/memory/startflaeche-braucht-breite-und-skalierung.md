---
name: startflaeche-braucht-breite-und-skalierung
description: "Eine responsive Qt-Startfläche wird gegen Fensterbreite und Schriftskalierung getrennt geprüft; QScrollArea braucht dafür einen schrumpfbaren Inhalt."
metadata:
  node_type: memory
  type: project
  modified: 2026-08-31
---

# Breite und Skalierung sind zwei verschiedene Achsen

Eine Startfläche kann bei 1920 × 1080 sauber aussehen und bei 640 Punkten
trotz einer einzigen Kachelspalte waagerecht überlaufen. Der Grund lag nicht
im Raster, sondern eine Ebene darüber: `QScrollArea.setWidgetResizable(True)`
zwingt ein Kind mit bevorzugter Wunschbreite nicht zuverlässig auf die Breite
des Sichtfelds. In diesem Fall war das Kind 126 Punkte breiter als sein
Viewport, obwohl sein `minimumSizeHint()` hineingepasst hätte.

Der tragende Vertrag besteht aus vier Teilen:

- Der zentrierte Inhalt verwendet waagerecht `QSizePolicy.Ignored`; seine
  Wunschbreite darf den Rollbereich nicht aufziehen.
- Der Rollbereich schaltet die waagerechte Achse ausdrücklich ab. Auf engem
  Raum wird das Raster zu einer Spalte und wächst nur nach unten.
- Erklärende Überschriften sind umbrechbar. Ein einziges nicht umbrechendes
  `QLabel` kann sonst die Mindestbreite des gesamten Bildschirms bestimmen.
- Fensterbreite und Schriftgröße werden getrennt geprüft: 640, 800, 1200,
  1536, 1920, 2560 und 3072 Punkte für das Raster; 100, 125, 150 und 200
  Prozent für die Systemschrift. Nur eine der beiden Reihen zu prüfen lässt
  den anderen Fehlerweg offen.

Breite nutzen heißt nicht, jeden Zwischenraum zu füllen. Der Sprung auf eine
1360 Punkte breite Spalte lag zunächst schon bei drei rechnerischen
Mindestkacheln und griff dadurch im 1536er Fenster, obwohl die vier sichtbaren
Einstiege weiterhin als 2×2-Raster standen. Das machte Bilder, Abstände und
Ablagefläche gemeinsam übergroß. Der breite Zustand hat deshalb eine eigene
gemessene Schwelle; Vorschaugröße, Trefferfläche und Inhaltsdichte bleiben
getrennte Verträge.

Auch eine in Python gesetzte Mindesthöhe ist unter Qt noch kein Vertrag: Das
globale Stylesheet poliert den Knopf später und kann sie dabei überschreiben.
Große Einstiegsknöpfe werden deshalb ausdrücklich über
`make_large_target()` markiert; der zentrale Selektor leitet seine Inhaltsbox
aus 44 Punkten Gesamtziel, Padding und Rahmen ab. Gewöhnliche Desktopknöpfe
bleiben kompakt, und große Systemschrift darf über das Mindestmaß wachsen.

Die Rastergrenze folgt der **wirklichen Kachelbreite**, nicht nur der
Fensterbreite: Außenränder, Fuge und die Dehnungsfaktoren des zentrierenden
Layouts zählen mit. Leere Seitenfedern bekommen erst Raum, nachdem die
Inhaltsspalte ihr Maximum erreicht hat. Sonst kann die Rechnung zwei Spalten
melden, während jede sichtbare Kachel deutlich unter ihrer Mindestbreite
bleibt.

Eine fokussierbare Kachel mit selbst behandeltem Maus- und Tastaturereignis
bleibt für Hilfsmittel ein Rahmen. Eine Handlungskachel ist deshalb ein echter
`QPushButton`: Name und Beschreibung ergänzen seine native Schaltflächenrolle,
und Maus, Eingabetaste sowie Leertaste laufen durch genau ein Signal. Texte in
der Ablagefläche tragen immer `wordWrap`; große Systemschrift darf die Fläche
und die Seite nach unten verlängern, aber keine Zeile seitlich abschneiden.

Schwebende Seitenkarten folgen derselben Sichtfeldregel. Ihr Grundmaß gilt auf
Full HD, auf großen Fenstern wachsen sie gedeckelt, auf schmalen Fenstern darf
jede höchstens einen festen Anteil belegen. Die Gegenprobe prüft nicht nur die
Breitenfunktion, sondern die tatsächlichen Geometrien von linker Karte,
rechter Karte, Werkzeugleiste und vollständigem Viewport.

Ein Offscreen-Test belegt diese Verträge, aber nicht die Darstellung. Die
native Gegenprobe braucht mindestens hell und dunkel, die Quellsprache und
die längste Übersetzung sowie ein echtes VTK-Projekt. Am 31.08.2026 wurden
640 × 900, 1920 × 1080 und 2560 × 1440 bei 150 Prozent unter Windows geprüft;
die Rollachsen, Texte, Karten und gerenderten Viewports blieben sichtbar.
macOS und Linux brauchen denselben nativen Paket-/Feldtest, weil diese
Maschine deren Fenster- und Grafiksystem nicht ausführen kann.
