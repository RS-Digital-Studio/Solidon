---
name: website-review
description: >
  Prüft die Solidon-Website mit den vorhandenen Tests und im echten Browser:
  Sprachfassungen, mobile und breite Ansicht, Bedienung, Farbschema und
  reduzierte Bewegung. Benutzen bei Website-Abnahme, sichtbaren Website-Fehlern
  oder einer ausdrücklich gewünschten Prüfung vor der Veröffentlichung.
---

# Website-Abnahme

Eine Abnahme liefert reproduzierbare Befunde und nennt die tatsächlich
geprüften Seiten und Zustände. Ein bestandener Quelltexttest ersetzt keine
Browserprüfung; eine lokale Vorschau belegt keinen funktionierenden Server.

## Prüfziel und Bestand

- Übernimm Adresse, Seiten und Umfang aus der Anfrage. Ohne genauere Angabe
  prüfe den aktuellen lokalen Website-Stand. Bei einem einzelnen Fehler
  beginne mit seiner Reproduktion; daraus wird keine vollständige Abnahme.
- Lies `website/CLAUDE.md` und die passenden Abschnitte in `website/README.md`.
  Prüfe `git status`, den Diff und neue Dateien, damit der Bericht den
  Arbeitsstand einschließlich uncommittierter Änderungen bezeichnet.
- Ermittle Sprachfassungen aus den vorhandenen Seiten und ihren Sprachlinks;
  heute sind es Deutsch, Englisch, Spanisch, Französisch, Italienisch und
  Portugiesisch. Unterseiten nicht aus deutschen Dateinamen ableiten.
- Nutze bei Reparaturen die Zuordnung von Quellen und erzeugten Dateien in
  `website/CLAUDE.md`. Erzeugte Seiten werden über ihre Quelle geändert.
  Eine reine Abnahme ändert weder Produktdateien noch Release-Artefakte.

## Vorhandene Tests

Für eine vollständige Website-Abnahme laufen mindestens:

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_website.py tests/test_website_accessibility.py
```

Bei einem eingegrenzten Fehler wähle die betroffenen Tests. Ergänze weitere
vorhandene Tests, wenn etwa Changelog, Handbuch oder Aktivierung zum Auftrag
gehören. Lies ihre Aussagen, bevor du daraus geprüfte Eigenschaften ableitest.
Protokolliere Aufruf, Exit-Code und Ergebniszahlen; ein abgebrochener Lauf ist
kein bestandenes Ergebnis. Der Ablauf für Reparaturen und das Tor vor einem
beauftragten Commit stehen in `.agents/skills/pruefen/SKILL.md`.

## Browser und Vorschau

Nutze zuerst die verfügbare Browsersteuerung. Lies deren aktuelle Anleitung,
bevor du ihre APIs aufrufst. Wähle einen vorhandenen passenden Vorschau-Server
oder starte einen lokalen HTTP-Server ausschließlich für `website/`, gebunden
an `127.0.0.1`. Prüfe zuerst den Port; beende danach nur den eigenen Server.
Ein Dateiaufruf über `file://` bildet Navigation und Serververhalten nicht ab.

Die statische Vorschau führt kein PHP aus und bildet `.htaccess`,
Produktions-Downloadkonfiguration und Aktivierungs-Endpunkte nicht vollständig
nach. Weise diese
Grenze aus, statt lokale 404-Antworten als Produktionsfehler zu melden. Bei
einer Prüfung der veröffentlichten Seite bleiben lokaler und ausgelieferter
Stand im Bericht getrennt. Eine Aktivierung, Support-Sendung oder Zahlung
wird nur ausgeführt, wenn die konkrete externe Handlung beauftragt ist.
Eine bereits erteilte Freigabe gilt weiter; keine zusätzliche Bestätigung
allein wegen dieses Prüfablaufs verlangen.

Falls die Browsersteuerung fehlt, prüfe, ob QtWebEngine in der Projektumgebung
verfügbar ist. Es kann sichtbare Seiten und Bildschirmfotos liefern, ersetzt
aber keine nicht durchgeführte Interaktionsprüfung. Verwende die echte
Qt-Plattform mit geladenen Schriften. Fehlt ein brauchbarer Browserzugriff,
führe die möglichen Tests aus und markiere die visuelle Abnahme als offen.

## Sichtbare Prüfung

Lege bei einer vollständigen Abnahme zuerst eine kleine Abdeckungsmatrix an:
Seite, Sprache, Fenstergröße, Farbschema, Bewegung, Ergebnis und Beleg.
Prüfe jede Sprachfassung mindestens auf schmaler und breiter Startseite sowie
auf den zum Auftrag gehörenden Unterseiten. Geeignete Ausgangsgrößen sind
390 × 844 und 1440 × 900 CSS-Pixel; ergänze andere Breiten bei einem Befund.
Prüfe hell und dunkel sowie reduzierte Bewegung an den betroffenen
Komponenten. Gemeinsame Komponenten dürfen repräsentativ geprüft werden;
vermerke die Auswahl und dehne sprachabhängige Fehler auf alle Fassungen aus.

| Bereich | Tatsächlich ausführen und ansehen |
|---|---|
| Navigation | Sprachwechsel, Kopf- und Fußnavigation, Sprunglinks und Zurückweg; Zielseite und Sprache kontrollieren. |
| Bedienung | Sichtbare Menüs und Auswahllisten öffnen; Tab, Umschalt+Tab, Enter und gegebenenfalls Escape benutzen; Fokus und verdeckte Bedienelemente prüfen. |
| Darstellung | Kopf, Mittelteil und Seitenende ansehen; Umbrüche, Überlagerungen, abgeschnittene Texte, Bilder und Download-Kasten prüfen. |
| Farbschema und Bewegung | Medienzustand im Browser verifizieren, dann Text, Zeichnungen, Fokus und Kontrast betrachten; bei reduzierter Bewegung auf übereinanderliegende Zustände achten. |
| Download und Inhalt | Plattform, Version, sichtbaren Link und Zielzuordnung prüfen; Paketinhalt oder Prüfsumme nur als geprüft melden, wenn tatsächlich kontrolliert. |
| Ressourcen | Soweit das Werkzeug es erlaubt: fehlende Ressourcen, Konsolenfehler und unerwartete externe Anforderungen beim Laden untersuchen. |

Nach einer CSS-Änderung den Browsercache berücksichtigen. Kontrolliere, dass
wirklich der geänderte Stand geladen ist. Farbschema und reduzierte Bewegung
über `matchMedia` prüfen, nicht allein aus gesetzten Optionen schließen.
Nach dem Scrollen warten, bis Übergänge beendet sind. Einzelne Ausschnitte
zeigen den tatsächlichen Eindruck besser als ausschließlich ein Gesamtbild.
Ein großer `scrollWidth` allein beweist keinen sichtbaren Überlauf: Die
Website schneidet dekorative Pseudoelemente absichtlich ab. Prüfe das konkrete
Element, seinen Elternbereich und den sichtbaren Ausschnitt.

Speichere Belege außerhalb von `website/`, damit Prüfbilder nicht in den
Upload geraten. Verwende die Screenshot-Funktion des Browserwerkzeugs;
die Release-Bilderzeugung aus `.agents/skills/erzeugen/SKILL.md` ist dafür nicht erforderlich.

## Ergebnis und gegebenenfalls Reparatur

Nenne zuerst die wesentlichen Befunde. Jeder Befund trägt Seite, Sprache,
Fenstergröße, Reproduktionsschritte, erwartetes und beobachtetes Verhalten
sowie einen Beleg, soweit verfügbar. Trenne Produktfehler von Grenzen der
Vorschau und des Prüfwerkzeugs. Eine Sichtprüfung bestätigt keine vollständige
Barrierefreiheit, eine Quelltextsuche keine gemessene Browserleistung.

Wenn Reparaturen beauftragt sind, behebe den Befund an der zuständigen Quelle,
prüfe seine Sprachvarianten und wiederhole die betroffenen Tests und denselben
Browserablauf. Für veränderte erzeugte Artefakte gilt `.agents/skills/erzeugen/SKILL.md`. Offen
bleibende bestätigte Produktfehler gehören nach den Projektregeln in das
Register von `ROADMAP.md`, ohne dort bereits vorhandene Befunde zu duplizieren.

Schließe mit Testzahlen, Browser und Version soweit ermittelbar, tatsächlich
geprüfter Matrix sowie ausdrücklich offenen Punkten. Berichte den Git-Stand
und etwaige Reparaturen. Eine Veröffentlichung oder ein Commit gehört nur
dazu, wenn der Nutzer dies beauftragt hat.
