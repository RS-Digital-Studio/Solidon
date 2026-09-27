---
name: website-review
description: >
  Prüft die Solidon-Website mit den vorhandenen Tests und im echten Browser:
  Sprachfassungen, schmale und breite Ansicht, Bedienung, Farbschema und
  reduzierte Bewegung; behebt auf Auftrag an der Quelle. Benutzen bei
  Website-Abnahme, sichtbaren Website-Fehlern oder einer gewünschten Prüfung
  vor der Veröffentlichung. Gestaltung über /ui-design, Abläufe über
  /ux-review, Erzeugen und Upload über /erzeugen.
argument-hint: "[optional: Seite, Sprache, Adresse oder Fehlbild]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Website-Abnahme

Eine Abnahme liefert reproduzierbare Befunde und nennt die tatsächlich
geprüften Seiten und Zustände. Ein bestandener Quelltexttest ersetzt keine
Browserprüfung; eine lokale Vorschau belegt keinen funktionierenden Server.

## Prüfziel und Bestand

- Adresse, Seiten und Umfang aus der Anfrage übernehmen; ohne Angabe den
  lokalen Stand prüfen. Ein einzelner Fehler beginnt mit seiner Reproduktion
  und wird dadurch keine vollständige Abnahme.
- `website/CLAUDE.md` und die passenden Abschnitte in `website/README.md`
  lesen; `git status` und den Diff prüfen, damit der Bericht den Arbeitsstand
  samt uncommitteter Änderungen bezeichnet.
- Sprachfassungen aus den vorhandenen Seiten und ihren Sprachlinks
  ermitteln, Unterseiten nicht aus deutschen Dateinamen ableiten.
- Erzeugte Seiten werden über ihre Quelle geändert (Zuordnung in
  `website/CLAUDE.md`). Eine reine Abnahme ändert weder Produktdateien noch
  Release-Artefakte.

## Vorhandene Tests

Für eine vollständige Abnahme mindestens:

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_website.py tests/test_website_accessibility.py
```

Bei einem eingegrenzten Fehler die betroffenen Tests; gehören Changelog,
Handbuch oder Aktivierung zum Auftrag, deren Tests dazu. Die Aussagen der Tests
lesen, bevor daraus geprüfte Eigenschaften werden. Aufruf, Exit-Code und
Ergebniszahlen festhalten; ein abgebrochener Lauf ist kein bestandenes
Ergebnis. Reparaturen und das Tor vor dem Commit laufen nach `.agents/skills/pruefen/SKILL.md`.

## Browser und Vorschau

Zuerst die verfügbare Browsersteuerung, nach ihrer aktuellen Anleitung. Einen
passenden Vorschau-Server nutzen oder einen lokalen HTTP-Server nur für
`website/` starten, gebunden an `127.0.0.1`; vorher den Port prüfen, danach
nur den eigenen Server beenden. `file://` bildet Navigation und
Serververhalten nicht ab.

Die statische Vorschau führt kein PHP aus und bildet `.htaccess`, die
Download-Konfiguration der Produktion und die Aktivierungs-Endpunkte nicht
nach — diese Grenze ausweisen, statt lokale 404-Antworten als
Produktionsfehler zu melden. Lokaler und ausgelieferter Stand bleiben im
Bericht getrennt. Aktivierung, Support-Sendung oder Zahlung nur, wenn genau
diese externe Handlung beauftragt ist.

Fehlt die Browsersteuerung, liefert QtWebEngine aus der Projektumgebung
sichtbare Seiten und Bildschirmfotos — auf der echten Qt-Plattform mit
Schriften, nicht offscreen. Zwei Handgriffe tun dort still das Falsche:
`--blink-settings=preferredColorScheme=0` ist dunkel und `=1` hell (`=2` fällt
still auf hell zurück), und `runJavaScript` gibt ein JS-Objekt als leeren
String zurück — Werte als `JSON.stringify(…)` holen. Reduzierte Bewegung über
`--force-prefers-reduced-motion`. Den Zustand jeweils über `matchMedia`
gegenprüfen. Ohne brauchbaren Browserzugriff die möglichen Tests fahren und
die visuelle Abnahme als offen markieren.

## Sichtbare Prüfung

Bei einer vollständigen Abnahme zuerst eine kleine Abdeckungsmatrix: Seite,
Sprache, Fenstergröße, Farbschema, Bewegung, Ergebnis, Beleg. Jede
Sprachfassung mindestens schmal und breit auf der Startseite und den
Unterseiten des Auftrags — Ausgangsgrößen 390 × 844 und 1440 × 900
CSS-Pixel, andere Breiten bei einem Befund. Hell, dunkel und reduzierte
Bewegung an den betroffenen Komponenten. Gemeinsame Komponenten dürfen
repräsentativ geprüft werden; die Auswahl vermerken und sprachabhängige Fehler
auf alle Fassungen ausdehnen.

| Bereich | Tatsächlich ausführen und ansehen |
|---|---|
| Navigation | Sprachwechsel, Kopf- und Fußnavigation, Sprunglinks und Zurückweg; Zielseite und Sprache kontrollieren. |
| Bedienung | Menüs und Auswahllisten öffnen; Tab, Umschalt+Tab, Enter, Escape; Fokus und verdeckte Bedienelemente. |
| Darstellung | Kopf, Mitte und Ende; Umbrüche, Überlagerungen, abgeschnittene Texte, Bilder, Download-Kasten. |
| Farbschema und Bewegung | Medienzustand im Browser verifizieren, dann Text, Zeichnungen, Fokus und Kontrast; bei reduzierter Bewegung auf übereinanderliegende Zustände achten. |
| Download und Inhalt | Plattform, Version, sichtbarer Link und Ziel; Paketinhalt oder Prüfsumme nur als geprüft melden, wenn tatsächlich kontrolliert. |
| Ressourcen | Soweit möglich fehlende Ressourcen, Konsolenfehler und unerwartete externe Anforderungen beim Laden. |

Nach einer CSS-Änderung sicherstellen, dass wirklich der neue Stand geladen
ist. Nach dem Scrollen warten, bis Übergänge beendet sind; Ausschnitte zeigen
den Eindruck besser als ein Gesamtbild. Ein großer `scrollWidth` beweist
keinen sichtbaren Überlauf — die Website schneidet dekorative
Pseudoelemente absichtlich ab; das konkrete Element, seinen Elternbereich und
den sichtbaren Ausschnitt prüfen.

Belege außerhalb von `website/` speichern, damit Prüfbilder nicht in den
Upload geraten; dafür genügt die Bildschirmfotofunktion des Browserwerkzeugs.

## Ergebnis und Reparatur

Zuerst die wesentlichen Befunde, je Befund Seite, Sprache, Fenstergröße,
Reproduktionsschritte, erwartetes und beobachtetes Verhalten, Beleg.
Produktfehler von Grenzen der Vorschau und des Werkzeugs trennen. Eine
Sichtprüfung bestätigt keine vollständige Barrierefreiheit, eine
Quelltextsuche keine gemessene Browserleistung.

Beauftragte Reparaturen an der zuständigen Quelle, mit ihren Sprachvarianten,
danach dieselben Tests und derselbe Browserablauf erneut; für erzeugte
Artefakte gilt `.agents/skills/erzeugen/SKILL.md`. Was nicht sofort behoben wird und eine
Entscheidung braucht, gehört ins Register von `ROADMAP.md`, ohne vorhandene
Befunde zu doppeln. Schluss: Testzahlen, Browser und Version, geprüfte Matrix,
offene Punkte, Git-Stand und Reparaturen. Veröffentlichung und Commit nur auf
Auftrag.
