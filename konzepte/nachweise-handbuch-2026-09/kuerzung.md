# Kürzung der Erklärseiten (HB-9)

Gehört zu [`konzept-handbuch-2026-09.md`](../konzept-handbuch-2026-09.md),
Paket HB-9. Gekürzt sind alle Seiten aus `manual.INTRODUCTION` außer `start`
und `glossary`, in vier Teilen und einer Nachkürzung auf dem Zweig
`handbuch-texte` (Commits `14f862070`, `1363c4f90`, `fb61a5ef7` und der
Abschlusscommit mit diesem Nachweis).

## Wie gezählt wurde

Wie in Konzept §1.1: Kurzfassung und Text einer Seite (`Page.text()`), Token
mit mindestens einem Buchstaben oder einer Ziffer, ohne Bildverweise. Von
einem Seitenverweis `[Titel](manual:schlüssel)` zählt der Titel, wie ihn der
Leser sieht. „Vorher“ ist der Stand `8fa13081f`, von dem der Zweig abgeht;
die Zahlen stimmen bis auf `print` (seither ergänzt) mit dem Anhang von
`findbarkeit.md` überein.

## Wörter je Seite

| Seite | vorher | nachher | Änderung |
|---|---:|---:|---:|
| `what` | 180 | 156 | −13 % |
| `window` | 830 | 533 | −36 % |
| `looking` | 505 | 308 | −39 % |
| `features` | 2 029 | 1 221 | −40 % |
| `moving` | 834 | 515 | −38 % |
| `sketch` | 1 427 | 892 | −37 % |
| `ways` | 212 | 170 | −20 % |
| `sculpting` | 368 | 259 | −30 % |
| `history` | 386 | 299 | −23 % |
| `parameters` | 388 | 269 | −31 % |
| `tolerances` | 299 | 222 | −26 % |
| `parts` | 752 | 565 | −25 % |
| `own-parts` | 592 | 374 | −37 % |
| `exchange` | 391 | 259 | −34 % |
| `print` | 546 | 436 | −20 % |
| `resin` | 193 | 151 | −22 % |
| `export` | 420 | 283 | −33 % |
| `splitting` | 553 | 364 | −34 % |
| `variants` | 215 | 186 | −13 % |
| `chat` | 298 | 182 | −39 % |
| `generating` | 299 | 187 | −37 % |
| `extras` | 1 038 | 591 | −43 % |
| `surfaces` | 339 | 245 | −28 % |
| `labels` | 351 | 242 | −31 % |
| `remote` | 210 | 146 | −30 % |
| `activation` | 282 | 207 | −27 % |
| `trouble` | 890 | 555 | −38 % |
| **zusammen** | **14 827** | **9 817** | **−33,8 %** |

Die Schwelle „ein Drittel weniger“ liegt bei 9 884 Wörtern. Kleine Seiten wie
`what` und `variants` sinken weniger, weil dort wenig zu streichen war;
`variants` hat zudem die Prüfkörper aus `tolerances` aufgenommen.

## Was wohin wanderte

Nicht aufgeführt ist, was nur zusammengezogen oder kürzer gesagt wurde.
Verweise führen nur auf Schlüssel, die es im Zweig gibt: die fünf
Anleitungen aus HB-4 und HB-8 und geschriebene oder erzeugte Seiten.

| Seite | Weggefallen oder verschoben | Wohin |
|---|---|---|
| `what` | „Fassung“ | „Version“ |
| `window` | Wo die Bereiche liegen (Werkzeugleiste, Spalten, Statusleiste), die Menünamen der Leiste, *Senken* und *Bohrung verschließen* an einer Bohrung, das Abziehen des Auswahlfensters, Pos1 als eigener Absatz | Lage: Anleitung *Das Fenster auf einen Blick* (`window-overview`); Merkmalshandlungen und Abziehen: `features`; Pos1 im Mausabsatz. **Berichtigt:** Ohne Auswahl leert sich das Auswahlfenster nicht, es zeigt die Handlungen für alle Körper |
| `looking` | Begründungen („eine Karte ohne Maßstab ist ein hübsches Bild“, „Brille, kein Werkzeug“) | Die Aussage bleibt: Keines der Werkzeuge ändert das Modell |
| `features` | Versionsgeschichte („Bis zur Fassung 0.3.5 …“), die Messzahl „296 von 1130 Einträgen“, der wörtlich zitierte Ring-Satz (steht im Fenster), die Liste der Mustertypen | Mustertypen: `surfaces`. **Berichtigt:** Der Abstand zweier Merkmale steht im Fenster als Zeilen *Abstand*, *in X*, *in Y*, *in Z*, nicht als eine Zeichenkette |
| `moving` | Der Schlussabsatz, der den Verlauf wiederholte | erster Absatz |
| `sketch` | Entwicklerbegründungen zum Raster, „ein Menü mit festen Maßen gibt es nicht mehr“ (Versionsgeschichte), Kameradetails | Kamera: `window` |
| `ways` | Die Werkzeugleiste zu Weg 2, TripoSG und ComfyUI zu Weg 3 | Anleitungen `print-a-model`, `drill-a-hole`, `first-part`; Seiten `sketch`, `generating`, `sculpting` |
| `history` | Klickweg zum Ändern eines Schritts | Anleitung *Ein Loch bohren* (`drill-a-hole`) |
| `tolerances` | Toleranz-Testkörper, Wandstärkenleiter, Überhangfächer und der Winkel aus dem Herstellerprofil (standen auf `tolerances` und `variants`) | nur noch `variants`, `tolerances` verweist darauf |
| `parts` | „eine Bibliothek, die man nicht sieht, gibt es nicht“, „ausdrücklich ein halbes Scharnier“, der Klickweg Fläche → Baustein → Größe | Anleitung *Das erste eigene Teil* (`first-part`) |
| `own-parts` | – (Reihenfolge umgestellt: erst Parameter, dann Auswahl, weil der Knopf sonst gesperrt bleibt) | – |
| `exchange` | Das Zitat „Eingelesen. Der Baustein steht im Katalog.“ (kein Text der Oberfläche) | umschrieben |
| `print` | Klickweg vom Modell zur Druckdatei | Anleitung *Ein Modell prüfen und drucken* (`print-a-model`). **Berichtigt:** Der Knopf heißt *Filament abziehen …* |
| `export` | *Trennen* und *Automatisch teilen* samt Bild `split`, das zweite Bild `layers` | `splitting` (mit Bild), `looking` (mit Bild) |
| `splitting` | Die Explosionsansicht | `looking` |
| `chat` | Bauplan-Verweis „(§26.4)“, „Systemprompt“, die Modellgröße | Modellgröße: `extras`; „Anweisungen“ statt Systemprompt |
| `generating` | Bauplan-Verweis „Der dritte Weg (§2.2)“, „das ist der wichtigste Satz“ | Weg 3: `ways` |
| `extras` | Messung „knapp acht Token je Sekunde auf Intel-Arc-Grafik“, die fünf Einzelschritte der ComfyUI-Einrichtung, der Start aus den Quellen | Modellwahl und Messungen: *Welche Modelle Solidon benutzt* (`models`) |
| `remote` | **Widerspruch aufgelöst:** „Eine eigene Schnittstellenliste gibt es deshalb nicht“ stand gegen die erzeugte Seite *Die Werkzeuge der Fernsteuerung* | Verweis auf `remote-tools`, das bleibt, wo es ist; MCP und Claude Code in einem Satz erklärt |
| `activation` | „Es muss kein langer Code abgetippt werden“, „Fassung“ | „Version“ |
| `trouble` | Der Einleitungssatz (wiederholte die Kurzfassung), das Beispiel „Wählen Sie links in der Liste einen Baustein“, Einzelheiten zu Kalibrierung und Teilen | Verweise auf `splitting`, `variants`, `chat` |
| `resin`, `surfaces`, `labels`, `sculpting`, `parameters`, `variants` | nur gestrafft | – |

## Was die Suite dazu sagt

- **Suche:** Gemessen an den 50 Kundensuchen aus `test_manual_search`, am
  Ausgangsstand und danach (Rang der richtigen Seite): ganz oben vorher 42,
  nachher 42; unter den ersten drei vorher 49, nachher 50 („Strg+Z“ stieg von
  Rang 4 auf 3). Die erste Fassung der Kürzung hatte fünf Suchen einen Rang
  gekostet („verschieben“, „Slicer“, „Wandstärke“, „Überhang“, „Stütze“):
  Die Kurzfassungen von `extras` und `variants` nannten die Suchwörter und
  zogen die Treffer an sich, `moving` und `export` hatten Wörter verloren.
  Die Kurzfassungen sagen es jetzt anders, und die beiden Seiten tragen ihr
  Wort wieder im Text. `CUSTOMER_WORDS` blieb unverändert.
- Die Aussagen, die Tests an den Seiten festhalten (Demo-Stichtag,
  Schichtvorschau, Bausteinnamen, Austausch ohne Übertragung, TripoSG und
  ComfyUI, die Grafikkarten-Regeln, die Flächennamen), stehen weiter da, in
  allen sechs Sprachen. Kein Test wurde gelockert; in `test_wording` fiel
  eine Ausnahme weg, weil die englische Seite `trouble` „normal“ nicht mehr
  sagt.
- Jeder Weg *A → B* auf den gekürzten Seiten besteht HB-11
  (`test_a_way_in_a_written_page_is_the_one_the_interface_shows`).
