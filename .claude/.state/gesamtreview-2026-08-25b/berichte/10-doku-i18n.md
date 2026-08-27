# Gebietsbericht: Handbuch, Abbildungen, Zeichnen, Markup, i18n, Changelog

Stand b1766c28. Skripte unter `review-doku\`. Nichts geändert.

## Mittel
- **1** Handbuch schickt für „Varianten erzeugen" ins falsche Menü (`manual.py:880`, sagt *Ändern → Varianten*, Eintrag steht im Menü *Bearbeiten*, `main_window.py:1680`). VERIFIZIERT. Fix: `*Bearbeiten →*`, fünf Übersetzungen.
- **2** Nach Sprachwechsel bleiben alle Zeichnungen deutsch (`figures.py:1253,1287`; `_CACHE` auf `(key, theme)`, `forget()` hat in `app/` keinen Aufrufer; `rebuild_for_language` überlebt der Modul-Cache). Gemessen: en-Text, deutsche Bilder (13 Zeichnungen). Test ruft `forget()` selbst („durchgereicht ist nicht gerufen"). Fix: `figures.forget()` in `rebuild_for_language`, Anschlusstest.
- **3** Alt-Text „ways" nennt drei Wege, das Bild zeigt vier (`figures.py:1017-1026`, vierter Weg „Organisch formen" fehlt in allen fünf Übersetzungen); Bildschirmleser hört Weg 4 nicht. VERIFIZIERT. Fix: ergänzen, `extract`, übersetzen.
- **4** „die Naht muss mindestens 5,4 mm hergeben" ist die widerlegte Größe (`manual.py:816`; Bedingung misst die Tiefe hinter der Naht, `SNAP_MIN_REACH=8.0`, nicht den Durchmesser 5,4). `_too_shallow_for_snap` hat genau das behoben. Fix: Satz auf die Tiefe umstellen, 8 mm aus der Konstante.
- **5** „Kurve" fehlt in allen fünf Katalogen (`sketch_editor.py:209-220`, `_ELEMENT_NAMES` nackte Zeichenketten, Einsammler sieht sie nicht). In jeder Fremdsprache steht „Kurve 1" in der Bedingungsliste. Dritter Fall der Sorte (nach `labels.py:1009`, `sculpt_bar.py:54`). Fix: `_("Kurve").msgid` wie in `palette.py:188`; Wortwahl mit Knopf „Spline" abgleichen.
- **6** „nichts, was den Rechner von allein verlässt" stimmt nicht mehr (`manual.py:113-114`; Startprüfung mit `User-Agent: Solidon/<version>`, Vorgabe an). Handbuch erwähnt die Aktualisierung nirgends, obwohl Hilfe-Menü und Startfenster sie führen. Fix: Halbsatz auf *Was Solidon ist*, kurzer Abschnitt zum Update.
- **7** Das Fernsteuerungs-Kapitel gibt einen Grund an, der für die Hälfte falsch ist (`manual.py:1521-1538`; `ask_user` ist keine Operation und aus anderem Grund gesperrt, `refusal_for` hat genau das behoben). Zweite Hälfte: `remote_tools` sperrt zusätzlich über `runs_foreign_source` (Rezepte mit SCAD-Schritt), das Handbuch listet nur `sorted(DENIED)`. Fix: zwei Sätze, Liste um die Wirkungssperre ergänzen.

## Gering
- **8** Beschriftungen laufen in fr/it/pt aus der Abbildung `sketch-editor` (`figures.py:638,690`; „Suppr retire celle qui est sélectionnée." ~180 px in 156 px). PLAUSIBEL. Fix: `canvas.wrapped(...)`. Zusammen mit Registerpunkt „Schemabild Skizzeneditor".
- **9** „Vier Regeln hat er mitbekommen" widerspricht dem Kapitel (`manual.py:905`; Systemprompt „Vier Gewohnheiten", Sammlung elf Regeln). Fix: „Gewohnheiten".
- **10** Fensterzeichnung zeigt fünf der acht Werkzeuge, der Text acht (`figures.py:139` vs `manual.py:192`; Trennen fehlt im Bild). Fix: alle acht.
- **11** Exportformate unvollständig genannt (`manual.py:777-784`, STL/3MF/STEP+GLB; Dialog bietet auch OBJ, PLY). Aufnehmen.
- **12** Eine Lizenzaussage verliert im pt-Katalog ihre Hervorhebung (`pt.json`, „**nicht**"→„não" ohne `**`; einziger Fall unter 5×3225). `uebersetzung.md` verlangt Markdown byte-gleich. Fix: `**não**`.
- **13** Ein Changelog-Punkt sagt auf Englisch mehr (`changelog/en.md:45`, „and in height" fehlt in de/es/fr/it/pt). Angleichen.
- **14** Die Bausteinseite liest sich abschließend und lässt vier Einträge aus (`manual.py:687`; Schnappverbindung, Passstift/Passbohrung, Deckel/Drehdeckel fehlen). Ergänzen.
- **15** `manual.find()` hat zwei kollidierende Schlüssel und in `app/` keinen Aufrufer (`manual.py:1692`); Anker im HTML in Ordnung, unerfüllte Docstring-Zusage. Binden oder Satz streichen.
- **16** (außerhalb Gebiet, deckt sich mit Infra-Befund 4) „kein Kennzeichen" gegen den gesendeten User-Agent (`datenschutz.html:96` vs `updates.py:261`).

## Geprüft und in Ordnung
`markup.py` gegen zwölf Angriffsmuster (Script/onerror/onload/iframe/javascript:/Event-Handler alles maskiert; Changelog läuft nicht durch markup, sondern `QLabel` PlainText, signaturgeprüft); Kataloge alle fünf Sprachen (3225 Einträge, keine leeren, Platzhalter/figure:/Umbrüche/Backticks/Fettmarken deckungsgleich bis auf Befund 12; 126 Handbuch-IDs vollständig); erzeugtes Handbuch (42 Seiten, 27 Bildverweise, kein toter Schlüssel, keine ungefüllten Platzhalter, alle 91 Ops mit Titel, 14 Kürzel); Abbildungen (19 SVG in beiden Themen wohlgeformt, 8×6 Bildschirmfotos je Sprache aufgenommen); Zahlen im Handbuch gegen den Code (Analysekarten, Muster, Bedingungen, Kürzel, Ports, Grammatik); Changelog (sechs Dateien, gleiche Struktur); Handbucherzeugung ohne OpenCASCADE (24 Meldungen je mit Vorschlag); `drawing.py` (Texte über `saxutils.escape`, kein Weg für Fremdwerte ins SVG).

**Kann das so rein: nein** — Befunde 1 (falsches Menü), 2 (deutsche Bilder nach Sprachwechsel), 5 (unübersetztes „Kurve") sind je ein Einzeiler plus Übersetzung und treffen den Kunden unmittelbar; der Rest kann geplant nachziehen.
