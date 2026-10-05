# Sollliste Solidon 0.5.0 — was wir versprechen und wo die App es einlöst

Stand: 22.09.2026, HEAD `9307a844` (main), `app/branding.py` APP_VERSION 0.5.0,
`website/version.json` noch 0.4.4. Nur gelesen: kein Test, kein Fenster, keine
Netzverbindung, keine Datei im Repository geändert. Sonden liegen im Scratchpad
der Sitzung (`count_ops.py`, `ops_site.py`, `E/cmp*.py`).

Maßstab (Robert): Die Website ist die Sollliste; was dort steht, muss die App
für einen Kunden ohne CAD-Kenntnisse, der vom Slicer kommt, einlösen.

## Aufbau und Urteilsschlüssel

Jedes Versprechen hat eine **Prüf-ID**. Gezählt wird je Prüf-ID, nicht je
Fundstelle — dasselbe Versprechen steht oft auf Website, im Changelog und in der
Presse zugleich; die Seitentabellen unten verweisen deshalb auf die Prüf-ID.

| Präfix | Gebiet | Wo geprüft |
|---|---|---|
| A1–A23 | Merkmale, Muster, exakter Körper, Maße im Bild | Teilbericht `sollliste-A-merkmale.md` |
| B1–B34 | Zeichnen, Parametrik, Bausteine, Konstruieren | Teilbericht `sollliste-B-konstruieren.md` |
| C1–C20 | Prüfbericht, Schichtanalyse, Slicer, Dateien, Filamentlager | Teilbericht `sollliste-C-drucken.md` |
| D1–D31 | System, Netz, KI, Demo, Sprachen, Plattform | hier, Abschnitt 4 |
| R1–R10 | Rechtstexte, Aktivierung, Sicherheit | hier, Abschnitt 5 |
| M1–M12 | README | hier, Abschnitt 6 |
| Bp1–Bp10 | Bauplan §2.2 (vier Hauptwege) und §31 | hier, Abschnitt 7 |
| L1–L5 | Sprachfassungen der Website | hier, Abschnitt 8 |
| P, K, CL | nur in Presse, KI-Seite oder Changelog stehende Versprechen | hier, Abschnitte 9–11 |

Urteile: **eingelöst** (mit Beleg) · **teilweise** (was fehlt, steht dabei) ·
**nicht eingelöst** · **nicht prüfbar** ohne Fenster, Hardware, Plattform oder
Referenzmaschine (dann: welcher Code/Test es trägt).

## 1. Zählung je Urteil

| Gebiet | eingelöst | teilweise | nicht eingelöst | nicht prüfbar | Summe |
|---|---:|---:|---:|---:|---:|
| A Merkmale/exakt | 11 | 8 | 2 | 2 | 23 |
| B Konstruieren | 18 | 10 | 2 | 4 | 34 |
| C Drucken/Dateien | 8 | 10 | 2 | 0 | 20 |
| D System/Netz/KI | 25 | 3 | 1 | 2 | 31 |
| R Rechtstexte | 5 | 3 | 2 | 0 | 10 |
| M README | 7 | 3 | 1 | 1 | 12 |
| Bp Bauplan §2.2/§31 | 0 | 2 | 0 | 8 | 10 |
| L Sprachfassungen | 4 | 1 | 0 | 0 | 5 |
| P Presse (nur dort) | 0 | 1 | 1 | 1 | 3 |
| K KI-Seite (nur dort) | 1 | 0 | 0 | 0 | 1 |
| CL Changelog (nur dort) | 8 | 1 | 0 | 2 | 11 |
| **Gesamt** | **87** | **42** | **11** | **20** | **160** |

Einordnung der Zuordnung: A11 (Maße im Bild, Fensterabnahme offen) und A23
(Leistungszahlen) zählen als „nicht prüfbar“; B2, B4, B25 (Kern eingelöst,
Fenster offen) und B31 (braucht ein Sprachmodell) ebenso. C4, C10, C12 und C20
(„überwiegend“) zählen als „teilweise“, C14 („weitgehend nicht“) als „nicht
eingelöst“.

## 2. Die zehn wichtigsten Lücken

1. **Kernversprechen der Presse ist nicht gebaut (A16).** Alle 25 Entwürfe
   unter `marketing/presse-0.5.0/` tragen „aus dem Netz wird ein exakter
   Körper“ — konkret `01-3druck-com.eml:23-28`: STL hineinziehen, bearbeiten,
   „Bisher kam dabei hinten wieder ein Dreiecksnetz heraus. Jetzt nicht mehr“,
   Ergebnis als STEP ins CAD; ebenso 07, 09, 13, 16, README:32-33. Es gibt
   keine Umwandlung Netz → exakter Körper; ROADMAP RM-188 **P4.0 ist offen**,
   der Exportdialog bietet STEP nur für exakte Körper (`main_window.py:6807-6815`,
   `writer.py:665-668`), `README.md:399-400` sagt selbst „der Rückweg nicht“.
   Nach der eigenen Sperre in `marketing/presse-0.5.0/README.md:17-22`
   (RM-188 abgeschlossen) dürfen die Mails mit 0.5.0 nicht hinaus.
2. **„Der Prüfbericht nennt den Grund: welche Insel in welcher Lage
   Stützmaterial kostet und wie weit man drehen müsste“ (C2)** — in fünf Mails
   (01, 04, 08, 17, 19) der zweite Hauptpunkt; es gibt keinen Inselbefund,
   kein Stützvolumen je Insel, keinen Drehwinkel. Dazu C3: Brückenweiten werden
   gemessen, aber nie gezeigt (`advise.warnings_for` hat keinen Aufrufer).
3. **Weg 1 beginnt mit „den Verweis von MakerWorld, Printables oder
   Thingiverse aus dem Browser ziehen“ (C14, `index.html:460-462`)** — ein
   Modellseiten-Link wird beim Ziehen stumm abgewiesen (Verbotszeiger, kein
   Satz); nur direkte Datei-Links gehen. Die erste Geste des Weg-1-Films
   scheitert ohne Erklärung.
4. **„Jeder Befund trägt einen Handlungsvorschlag“ (C1; `funktionen.html:426-427`,
   `index.html:386-388, 640-642`; Bauplan §2.7, Regel 17)** — 276 von 324
   Befundstellen haben weder `suggestions` noch einen Eintrag in
   `FINDING_ACTIONS`, darunter die Fehler `gcode.spool_left_out`
   (`export/handover.py:2710`) und `join.blocked` (`geom/prepare.py:2751`) und
   die Warnung `fit.violated` (`scene/fits.py:373`). Das Handbuch schreibt
   selbst nur „die häufigsten Befunde tragen eine Schaltfläche“.
5. **„Jeder Baustein ist über seinen ganzen Parameterbereich getestet“ (B15;
   `funktionen.html:339-341`, `index.html:646-648`)** — der Lauf fiel am
   03.09.2026 (`4bcb0272`), acht neue Bausteine wurden nie gefahren, und
   `catalog.py:923-949` unterdrückt die Warnung für mitgelieferte Bausteine mit
   der falschen Begründung, die Suite fahre sie.
6. **„misst 5,19 mm — das Durchgangsloch für M5“ in einer fremden STL (A4;
   `funktionen.html:124-126`)** — an einer Netzbohrung sagt die App
   „geschätzt … Schraubengröße nicht sicher bestimmt“; der Test
   `test_matching.py::test_bore_advice_distinguishes_a_measurement_from_a_known_screw`
   schreibt das fest. Der Aufmacher der Funktionsseite ist an einer STL nicht
   erlebbar.
7. **Muster in einem heruntergeladenen Modell neu setzen (A13)** — die
   Presse-Testanleitung („Download any model with a knurl, click the pattern …
   set a different pitch“, `07-all3dp.eml`) klappt nur bei den acht
   Solidon-eigenen Stilen im Solidon-Gitter; fremde Muster sind `other` und nur
   entfernbar; Muster um Zylinder sind nur an `apply_texture`-Ausgaben geprüft.
8. **Generator-Einrichtung: Startseite sagt Nein, App sagt Ja (D28).**
   `index.html:492-495, 719-721, 841-843` (alle sechs Sprachen): Solidon
   richte „derzeit bewusst kein bestimmtes 3D-Modell ein“, lade keines herunter,
   bis die Lizenzkette belegt ist. Die App richtet TripoSG und seit dem
   21.09.2026 auch SDXL auf Wunsch ein (`comfy_dialog.py`, `install_dialog.py:712-714`,
   `comfy_setup.py:78-109`, Changelog 0.5.0 Z. 131); `ki-modelle.html:137-142`
   und das Handbuch sagen das auch. RM-003 (Lizenzkette) ist offen — eine der
   beiden Aussagen muss fallen, und das ist eine Lizenzentscheidung.
9. **Passungen folgen dem Material nicht immer, und „nicht geschätzt“ stimmt
   nicht (C5).** Presse 02/03/18/25: „Wechselt man auf PLA, ändert sich das
   Spiel mit“. Passungen aus *Automatisch teilen* und *Deckel* speichern das
   Anlagematerial (`split.py:576`, `lid_flow.py:90`), ein Materialwechsel
   schreibt sie nicht um (`ui/session.py:1650-1677`) — Sonde: PETG geteilt,
   TPU ausgewertet → zweimal `fit.violated` ohne Knopf. Alle Materialprofile
   sind unkalibriert (`materials.toml`), der Hinweis darauf liegt in totem Code;
   `index.html:432-433` sagt „nicht geschätzt“.
10. **Bausteine im Kontextmenü einer Fläche (B13/B12)** — `funktionen.html:328-332`,
    `index.html:632-635` bewerben Wandhalter, Rippe, Nutfeder usw. „im Menü einer
    Fläche“; seit 11.09.2026 zeigt der Rechtsklick keine Operationen mehr
    (`panels.py:2375-2403`, Bauplan §2.6, Changelog 0.4.1 Z. 337). Auch „Menü,
    Kontextmenü, Kommandozeile und Chat sehen dieselbe Deklaration“
    (`funktionen.html:597-599`) stimmt beim Kontextmenü nicht mehr.

## 3. Alle Lücken nach Schwere

**Kritisch — so darf es nicht veröffentlicht oder versandt werden**

- A16 Presse „STL wird exakter Körper, STEP heraus“; Presse-README-Sperre
  (RM-188 offen) — Entwürfe vor Versand kürzen oder zurückhalten.

**Hoch — Kunde folgt dem Versprechen und scheitert, oder Rechts-/Lizenzaussage falsch**

- C2 Insel/Lage/Stützmenge/Drehwinkel im Prüfbericht (Presse, fünf Mails).
- C14 Modellseiten-Link wird stumm abgewiesen (Weg 1, Startseite, Film).
- C1 Befunde ohne Handlung, darunter zwei Fehler und `fit.violated`.
- B15 Bereichsprüfung der Bausteine läuft nirgends; Katalog verschweigt es.
- A4 „Durchgangsloch für M5“ an fremder STL.
- A13 Muster neu setzen nur an Solidon-eigenen Mustern.
- D28 Generator-Einrichtung: Startseite gegen App, KI-Seite, Handbuch (RM-003).
- C5 Passungen bleiben am Anlagematerial; „nicht geschätzt“.
- B13/B12 Kontextmenü einer Fläche ohne Bausteine/Operationen.

**Mittel — Versprechen zu weit, veraltet oder nur halb**

- D12 Lokales Modell: „16 GB genügen, Median 17 s, vollständig im
  Grafikspeicher, 106 Werkzeuge“ (`ki-modelle.html:145-151`, `index.html:747-750`,
  Handbuch) — heute 144 Werkzeuge, 36 731 Token Schema, `num_ctx` 40 960
  (`llm.py:1171`) → 11 % des Modells auf der CPU, 11 statt 41 Token/s, 18 s je
  Zug (RM-185, striktes xfail).
- D11 „28 von 39, 98 %“ (Stand 08.08.) — letzte Messungen 20/39 → 24/39
  (15.09., RM-081/RM-173), RM-016 offen.
- C3/C16 Brückenweiten, schmalste Stelle, Überhang „je Schicht“ nicht sichtbar;
  `advise.warnings_for` tot.
- C8 *Teilen* aus dem Operationsdialog legt keine Passung an.
- B11 Formelbeispiel `schraube_m4 + spiel` wird abgewiesen (`@` nötig);
  60 von 136 Operationen zeigen vorn 4–8 Felder statt „zwei bis drei“.
- B10 Verlaufsschritte gemeinsam „verschieben“ gibt es nicht (P7.2 offen).
- B5 Vieleck und Langloch ohne Satz „was der nächste Klick bewirkt“.
- A17 Importiertes Gewinde am Netz: Gangzahl fehlt, Händigkeit geraten;
  Gegenstück nur an Solidon-Gewinden geprüft.
- A18 Maßherkunft: App zeigt „geschätzt/Vorgabemaß/nicht bestimmt“, Changelog
  und Presse versprechen „gemessen/eingepasst/aus dem Schritt“.
- A19/CL4 Merkmalsnamen und -zahl hängen von Lage und Rundungen ab
  (RM-210: 16 von 39 Modellen gedreht anders; RM-211; RM-189; RM-186 Ubuntu) —
  gegen „bleibt unter seinem Namen“ und „auf jedem Rechner gleich erkannt“.
- A7 „Kehlen … ausgenommen“ (Website) gegen „Wulst und Kehle … fünf
  Handlungen“ (Changelog 0.5.0).
- C15 Weg 3 „teilt oder verstiftet bei Bedarf“, „Filamentzahl, die wirklich in
  der Maschine steckt“ — Eingabe, nicht aus Drucker/AMS.
- C4/C20 Cura bekommt bei „Im Slicer öffnen“ eine STL ohne Einstellungen;
  Bambu-Mehrfarbauftrag halb (RM-163), Creality-Konsole ungeprüft (RM-164),
  Prusa ein Drittel mehr Material (RM-191).
- P7 Presse „Einmalkauf in drei Stufen / three tiers“ (05, 12, 22) — EULA/AGB
  kennen zwei Lizenzarten, Preise sind unveröffentlicht.
- P9 Presse „KI-Funktionen abschaltbar“ — es gibt keinen Schalter, nur
  Schlüssel entfernen; lokal gefundenes Ollama wird angesprochen.
- R8 EULA §9 „Verbindungen entstehen nur auf den folgenden Wegen“ — URL-Import,
  Zusatzprogramm- und Gewichts-Downloads fehlen in der Liste (Datenschutz nennt sie).
- Bp7/Bp8 §31: Erkennung organisch 3,83 s statt < 1 s (RM-193/RM-132),
  Schichtanalyse hohl 1,5 s statt < 300 ms (RM-201).
- A11, B2, B25, A15 u. a.: umgesetzt, Fensterabnahme offen (RM-183, RM-184,
  RM-197, RM-199, P5.3).

**Niedrig — Benennung, Zahl, Kleinabweichung**

- A2 Tiefenfeld im Website-Bild, an STL nur Auskunft · A22 Auflösungsgrenze
  profilunabhängig (Presse 16 sagt „des Verfahrens“) · A15 „Kuppe“/„Kuppel“.
- B1 „gleiche Länge“/„Gleich groß“ · B3 „kein Vieleck“ gilt nicht für STL/3MF ·
  B16 „fragt nach“ → Vorschau auf Oberseite · B24 Profilklemme nur M4 · B32
  Gehäuse 13 statt „zwölf“ Schritte · B34 README-Weg zum Prüfstück · B23/M12
  Namen („verdicken“, „Dezimieren … Neu vernetzen“).
- C9 Abschneiden an offenem Netz ohne Deckel und ohne Meldung · C10 FAQ
  „Schichthöhe“ ist kein Feld beim eigenen Drucker · C12 Slicer-Übernahme ohne
  Cura, Kopfzeile nennt kein Filament mehr · C13 GLB fehlt in `index.html:804-805`
  und im Export-Tooltip · C18 Slicer-Übergabe fragt vorher nicht.
- D21 „keine Einrichtung“ — Ersteinrichtung vorhanden (überspringbar).
- R1 Datenschutz „Hilfe → Installation“ statt „Hilfe → Zusätzliche Programme …“ ·
  R2 „Fragebogen bis zu dreimal“ statt einmal je Version · R3 „Solidon
  unterstützen …“ statt „Solidon3D unterstützen …“ · R10 Sicherheitsseite
  „Solidon 1 ist eine kostenpflichtige Kauflizenz“ gegen Startseite „noch kein
  Angebot“ · L3 dasselbe auf der KI-Seite („Ab 1.0 einmal kaufen“).
- M1 README nennt 0.4.2 als letzte Fassung · M3 README zum exakten Kern
  unvollständig · M9 README „TripoSG MIT, Quelltext wie Gewichte“ (RM-003 offen).

**Beim Release ohnehin fällig (kein Befund, aber Pflicht):** Download-Kasten
(`index.html:292-309`: 0.4.4, 171/287/203/215/238 MB, 19.09.2026),
Speicherbedarf „rund 750 MB“, „Download zwischen 171 und 287 MB“
(`index.html:829-830`), `version.json`, Handbuchreferenz — über
`tools/make_download.py` und `/erzeugen`. Die Zahlen 136/35/51/18/11 stimmen
mit dem heutigen Register überein (Abschnitt 4, D-Belege).

## 4. System, Netz, KI, Demo, Sprachen, Plattform (eigene Prüfung)

| ID | Versprechen (Fundstelle) | Einlösung | Urteil | Risiko |
|---|---|---|---|---|
| D1 | Demo vollständig, ohne Schlüssel/Konto, keine Wasserzeichen/Exportsperre, bis 30.10.2026; danach startet sie nicht (`index.html:313-316, 856-858`; `eula.html:59`) | `activation/store.py:96` `DEMO_UNTIL = 2026-10-30`; `activation/__init__.py:297-312` `over`; `dialogs.py:2536-2547` Abschiedsdialog mit „Website öffnen“ und Satz zu den Projekten | eingelöst | Ein gebrochenes Integritätsmanifest (Virenscanner) sperrt auch in der Demo die Schreibseite (`activation/__init__.py:352-367`) — „keine gesperrten Funktionen“ gilt nur für intakte Installationen. |
| D2 | „in der Statuszeile steht jeden Tag, wie lange sie noch läuft“, auch im Über-Dialog (`index.html:856-858`; `eula.html:59`) | `main_window.py:5125` dauerhafte Zeile; `labels.py:2548-2558` „Demo — noch {days} Tage, bis zum {date}“; `dialogs.py:3265` | eingelöst | — |
| D3 | „Läuft offline“, „ohne Konto und ohne Netz“ (`index.html:245, 874-875`) | Demo ohne Aktivierung: `activation/__init__.py:380` `Activation(days_left, deadline)` ohne Schlüssel | eingelöst | — |
| D4 | „Keine Telemetrie“, Netz nur nach Handlung (`index.html:253, 944`; `datenschutz.html:51-54`) | Netzmodule: `backends/keys.py`, `backends/llm.py`, `backends/mesh.py`, `discover.py` (nur lokale Dienstprobe), `ingest/fetch.py`, `licence_service.py`, `support.py`, `updates.py`, `ui/support_dialog.py`; keiner sendet ohne Handlung außer der Update-Prüfung | eingelöst | — |
| D5 | Update beim Start, Laden erst nach Bestätigung, abschaltbar; Anfrage nennt nur Name und Version (`index.html:331`; `datenschutz.html:52`) | `settings.py:143` `check_for_updates=True`; `updates.py:639-660` User-Agent `Solidon/<Version>`; Ed25519-Signatur `updates.py:623-636`; Menü „Einstellungen …“ `main_window.py:3394` | eingelöst | — |
| D6 | Ohne Schlüssel/Ollama alles außer Chat, auch CLI und 136 Operationen (`index.html:920-922`) | `count_ops.py`: Register 136 = veröffentlichte Referenz 136; Chat nur über `backends/llm.py` | eingelöst | — |
| D7 | Vor dem ersten Modellkontakt zeigt Solidon das Ziel (`index.html:797-800, 943`) | `ui/ai_disclosure.py:1-6`; `settings.py` `ai_disclosure_*`; `tests/test_ai_disclosure.py` | eingelöst | — |
| D8 | Chat sendet Nachricht, bis zu zwölf frühere Beiträge, Steckbrief, Prüfbericht, ggf. Bilder; keine Projektdatei (`index.html:942`; `datenschutz.html:52`) | `agent/context.py:42` `HISTORY_LIMIT = 12` | eingelöst | — |
| D9 | Agent bedient dieselben Operationen, ein Vorschlag = eine Transaktion, ein Undo, Rückfrage statt Vermutung (`funktionen.html:615-622`; `index.html:926-929`) | `registry/surfaces.py` `tool_schemas` 136; Regel 16; Rücknahme bei angehaltenem Zug (Commit `e08953fb`, `_DocumentState`) | eingelöst | — |
| D10 | „Suite aus 39 Referenzanfragen“ vor und nach jeder Regeländerung (`index.html:627-631`; `funktionen.html:623-625`) | `tests/agent_cases.py` `ALL_CASES` = 39; `test_website.py:236-248` | eingelöst (Zahl) | — |
| D11 | „Stand 08.08.2026 … 28 von 39 gut beantwortet, 98 % … gültig“ (`funktionen.html:626-629`) | ROADMAP RM-081/RM-173: 15.09. 20/39 → 24/39 mit Kürzung; RM-016 offen | teilweise (veraltet) | Redaktion misst schlechter als die Seite verspricht. |
| D12 | „qwen3:14b mit 106 Werkzeugen … 16 GB … Median 17 s … vollständig im Grafikspeicher“ (`ki-modelle.html:145-151`); „braucht eine Grafikkarte mit 16 GB“ (`index.html:747-750, 837-840`) | `llm.py:1171` `OLLAMA_CONTEXT_TOKENS = 40960`; RM-185: 143–144 Werkzeuge, 36 731 Token, 11 % CPU, 11 Token/s, 18 s je Zug, 3,8× langsamer; xfail `test_the_local_backend_opens_a_window_big_enough_for_the_tools` | teilweise | Wer lokal chattet, bekommt einen deutlich langsameren Chat als beschrieben; bei 32 768 kommt die Kürzungsmeldung. |
| D13 | „Die Anwendung weist aus, ob Ollama die GPU tatsächlich benutzt“ (`ki-modelle.html:152`) | `llm.py:1443-1463` `_ran_on_gpu`; `dialogs.py:1598-1608` „Die Grafikkarte wird genutzt.“ | eingelöst (nur im Einrichtungsdialog) | — |
| D14 | MCP-Server: aus, Schalter und Port in Einstellungen, nur 127.0.0.1 (Bindung und jede Anfrage), kein Dateipfad/Quelltext, Transaktion mit Herkunft, Strg+Z, `http://127.0.0.1:8787/mcp`, jede Operation ein Werkzeug (`funktionen.html:679-697`; `index.html:933-938`) | `agent/remote.py:1-25, 52-55, 109-120` (Bindung, Absender, `Origin`); `settings.py:170-176`; `manual.py:1978`; Handbuch `#remote`, `#ref-remote-tools`; `tests/test_remote.py`, `tests/test_remote_server.py` | eingelöst | — |
| D15 | Offline-Aktivierung „Hilfe → Solidon freischalten → Offline aktivieren“, `.solidon-request`, Antwort einlesen; Deaktivieren; Über zeigt Lizenzart (`offline-aktivierung.html:47-49`; `eula.html:37, 43, 48`) | `main_window.py:3922`; `dialogs.py:1708-1773` („1 · Anfrage speichern …“, „3 · Antwort einlesen …“), `:1937`, `:2191`; `dialogs.py:3070-3140` | eingelöst (Verkaufsversion; die Demo braucht es nicht) | — |
| D16 | „Hilfe → Rückmeldung senden“ und Knopf auf der Startfläche; Vorschau; nur angehakte Anhänge; lokal als Ordner; Absturzprotokoll liegt bei (`datenschutz.html:52-54`; Changelog 0.5.0 Z. 130) | `main_window.py:3893`; `start_screen.py:877-884`; `support_dialog.py:484-487`; `report.py:325-370` | eingelöst | — |
| D17 | Unterstützen: erst lokaler Dialog, dann PayPal/GoFundMe im Browser (`index.html:337-356`; `datenschutz.html:34-39`) | `main_window.py:3929`; `dialogs.py:2956` `DonationDialog` | eingelöst | — |
| D18 | Sechs Sprachen, Handbuch „in derselben Sprache wie die Oberfläche“ (`index.html:42`; `funktionen.html:716-717`; Presse 21, 25) | `app/i18n/locales/{en,es,fr,it,pt}.json` + deutsche Quelle; `website/handbuch/<6 Sprachen>`; `manual.py` liest die Kataloge | eingelöst (Vollständigkeit prüft `test_translations.py`, Fensterdatei, nur beim Release) | — |
| D19 | Handbuch „Die ersten fünfzehn Minuten“ (`index.html:333`), F1, Referenz aus dem Register, `solidon3d docs --manual` (`README.md:127`) | `manual.py:87, 196-198`; `main_window.py:3856`; `cli/main.py:220-226, 580` | eingelöst | — |
| D20 | Elf Beispielprojekte, vier je Weg sichtbar, sieben hinter „Was kann das noch?“, „Neues Projekt“, „Projekt öffnen“ (`index.html:382-384, 398-400`; `funktionen.html:711-715`) | `app/examples/*.p3d` = 11; `start_screen.py:835, 844, 959` | eingelöst | — |
| D21 | „Kein Konto, kein Schlüssel, keine Einrichtung — installieren und loslegen“ (`index.html:382-383`) | `first_run.py:1-6` Ersteinrichtung (Sprache, Slicer, Drucker, Chat), überspringbar („Später einstellen“ `:550`) | teilweise | harmlos; Satz zu absolut. |
| D22 | Navigation: links verschiebt, rechts dreht, Rad kippt, W/A/S/D; Schemata Cura, Bambu/Prusa, CAD, Blender (`funktionen.html:843-847`) | `ui/render/navigator.py:30` `solidon/slicer/orbit/cad/blender`, `:66` „Wie in Cura …“ | eingelöst | — |
| D23 | Fensteraufbau: links vier zuklappbare Abschnitte, Mitte Ansicht mit Werkzeugzeile, rechts Prüfbericht/Chat, außen Merkmalsfenster (`index.html:584-589`) | Code in `main_window.py`/`panels.py`; Bauplan §2.5 | nicht prüfbar ohne Fenster (Welle 2 „kundenwege“) | — |
| D24 | Windows 10 ab 1809/11 x64, macOS 13+ (arm64 und x86_64 getrennt, notarisiert ab 0.4.1), Linux x64 X11/Xwayland, 8 GB, D3D12/Vulkan/Metal, ab 1920 × 1080 (`index.html:824-836`) | `packaging/solidon3d.iss:36` `MinVersion=10.0.17763`, `:71-72` x64; `packaging/solidon3d.spec:372` `LSMinimumSystemVersion 13.0`; Windows unsigniert (RM-001, Website sagt es) | nicht prüfbar ohne Plattform (RM-011, RM-051, RM-055, RM-104 offen) | Mac/Linux-Berichte stehen aus. |
| D25 | Ohne passende Grafik startet Solidon ohne 3D-Ansicht (`README.md:230-233`) | `viewport.py:1858-1895` Hinweis; `SOLIDON3D_NO_VIEWPORT` | eingelöst | — |
| D26 | Projektdatei ZIP mit JSON, ohne Solidon lesbar, „die nächste Version liest sie unverändert“ (`index.html:862-865`; `eula.html:61`) | `scene/migrations.py:29` `FORMAT_VERSION = 29`; `tests/data/projects/example_v1…v29.p3d` | eingelöst | — |
| D27 | Sicherheitsupdates bis mindestens 31.10.2031 (`index.html:811-812`; `security.html:45`; `eula.html:69`) | `branding.py` `SECURITY_SUPPORT_UNTIL = 2031-10-31`; Über-Dialog „Aktualisierungen und Sicherheit“ | eingelöst (als Zusage) | — |
| D28 | „Solidon3D richtet derzeit bewusst kein bestimmtes 3D-Modell ein“ / lädt keines herunter, bis die Lizenzkette belegt ist (`index.html:492-495, 719-721, 841-843`, alle Sprachen, seit `df8fae68`) | App richtet TripoSG und SDXL auf Wunsch ein: `comfy_dialog.py:11`, `install_dialog.py:712-714`, `main_window.py:6020`, `generate_dialog.py:639` „Knoten und Modell einrichten …“, `comfy_setup.py:78-109`; `backends/mesh.py:25-29` („in Betrieb, solange die Prüfung nichts anderes ergibt“) | nicht eingelöst (Widerspruch) | Lizenz-/Rechtsaussage; RM-003 offen. |
| D29 | „Jede Handlung quittiert ihr Ergebnis kurz dort, wo Sie geklickt haben“ (Changelog 0.5.0 Z. 129) | `main_window.py:17236` `announce` (Commit `e08953fb`) | eingelöst | — |
| D30 | Bausteinrezepte nur als Datei lokal, nichts zu RS Digital (`datenschutz.html:55`) | `branding.PART_FILE_SUFFIX = .solidon-part`; im Netzinventar (D4) kein Hochladeweg | eingelöst | — |
| D31 | Flatpak `de.rsdigital.solidon3d`, Befehle, gleiche Netzfähigkeit (`index.html:155, 328`; `README.md:204-208`) | `packaging/de.rsdigital.solidon3d.yml:8-18` (`--share=network`, `--device=dri`) | eingelöst | — |

## 5. Rechtstexte, Aktivierung, Sicherheit (eigene Prüfung)

Quellen der erzeugten Seiten: `DATENSCHUTZ.md`, `EULA.md` im Projektwurzelordner
(`tools/make_legal.py:48-51`) — Korrekturen dort, nicht in `website/`.

| ID | Versprechen (Fundstelle) | Einlösung | Urteil | Risiko |
|---|---|---|---|---|
| R1 | „Wer über *Hilfe → Installation* ein Zusatzprogramm einrichten lässt …“ (`datenschutz.html:52`, Quelle `DATENSCHUTZ.md:68`) | App: „Hilfe → Zusätzliche Programme …“ `main_window.py:3872`; Handbuch Kapitel „Zusätzliche Programme einrichten“ | nicht eingelöst (Menüname falsch) | niedrig; Rechtstext nennt einen Weg, den es nicht gibt. |
| R2 | Fragebogen „während der Demo bis zu dreimal“ (`datenschutz.html:52`, `DATENSCHUTZ.md:70`; `eula.html:84`, `EULA.md:317`) | `core/feedback.py:48-51` `MAX_INVITATIONS = 1` **je Version** nach 15 min; Changelog 0.4.1 Z. 346 und Handbuch sagen „einmal je Version“; seit 23.08. neun Demo-Fassungen | nicht eingelöst (Text unterschätzt die Zahl) | niedrig–mittel (Datenschutzaussage). |
| R3 | „die Aktion *Solidon unterstützen …*“ (`datenschutz.html:34`, `DATENSCHUTZ.md:26`) | App „Solidon3D unterstützen …“ `main_window.py:3929` | teilweise (Benennung) | niedrig |
| R4 | Demo nennt ihren Stichtag in Statuszeile, Über-Dialog und Website (`eula.html:59`) | D2 | eingelöst | — |
| R5 | Verkaufsversion ohne Freischaltung: Lesendes offen, Ändern/Export/Slicer/Chat gesperrt (`eula.html:66`) | `activation/__init__.py:202, 264-272` `unlocked`, `sale_without_trial` | eingelöst (betrifft 1.0) | — |
| R6 | Lizenzart unter „Hilfe → Über Solidon“ (`eula.html:37`) | `main_window.py:3936`; `dialogs.py:3070-3140` `_licence_line` | eingelöst | — |
| R7 | THIRD-PARTY-NOTICES im Über-Dialog (`eula.html:78`) | `dialogs.py:3071` „Drittanbieter-Lizenzen“ | eingelöst | — |
| R8 | „Verbindungen entstehen nur auf den folgenden, sichtbaren Wegen“: Update, Chat, Support, Aktivierung (`eula.html:83-84`, EULA §9) | Zusätzlich im Code: Modell-URL laden (`ingest/fetch.py`), Zusatzprogramme/Pakete/Gewichte laden (`install_dialog.py`, `comfy_setup.py`), entfernter ComfyUI-/Ollama-Dienst; Datenschutz nennt sie, EULA nicht | teilweise (Liste unvollständig) | mittel (Vertragstext abschließend formuliert). |
| R9 | Offline-Aktivierung: „Einmal verbinden, danach offline“; keine regelmäßige Lizenzabfrage (`offline-aktivierung.html:41-49`; `eula.html:47`) | D15; `activation/certificate.py` lokale Prüfung | eingelöst | — |
| R10 | „Solidon 1 ist eine kostenpflichtige Kauflizenz“ (`security.html:44-45`) gegen „Version 1.0 … noch kein Angebot“ (`index.html:317-319, 771-773`) | organisatorisch | teilweise (Widerspruch im Ton) | niedrig |

## 6. README (eigene Prüfung)

| ID | Versprechen (Fundstelle) | Einlösung | Urteil |
|---|---|---|---|
| M1 | „nach der Veröffentlichung von **0.4.2 am 15. September** … noch nicht Teil dieses Downloads“ (`README.md:37-54`) | 0.4.3 und 0.4.4 sind draußen und enthalten die Punkte | nicht eingelöst (veraltet) |
| M2 | „In ein Netz umwandeln geht jederzeit, der Rückweg nicht“ (`README.md:399-401`) | `brep/ops.py:862` `brep_to_mesh`; keine Gegenrichtung | eingelöst — und Beleg gegen A16 |
| M3 | Exakter Kern „kommt ins Spiel, wenn eine STEP-Datei geladen oder ein exakter Körper angelegt wird“ (`README.md:389-393`) | 0.5.0: Grundkörper immer exakt (P2.8) | teilweise (unvollständig) |
| M4 | „Datei → Modell erzeugen“, ausgegraut ohne ComfyUI (`README.md:275-280`) | `main_window.py:3273-3276` | eingelöst |
| M5 | „Hilfe → Zusätzliche Programme“ (`README.md:214, 290`) | `main_window.py:3872` | eingelöst |
| M6 | „Bearbeiten → Chat einrichten“ (`README.md:239`) | `main_window.py:3408`; `dialogs.py:899` | eingelöst |
| M7 | „Bearbeiten → Automatisch teilen“ (`README.md:430`) | `main_window.py:3597-3605` (Gruppe „Vorbereiten“ ohne Menü → Bearbeiten; `registry.py:115-142`) | eingelöst |
| M8 | `solidon3d docs --manual` (`README.md:127`) | `cli/main.py:220-226, 580` | eingelöst |
| M9 | TripoSG „steht unter der MIT-Lizenz — Quelltext wie Gewichte“ (`README.md:320-322`) | `backends/mesh.py:25-29` „Lizenzkette … wird geprüft“; RM-003 offen | teilweise (README sagt mehr als belegt) |
| M10 | RTX 4080: 13 s je Körper, 300 000–600 000 Dreiecke (`README.md:324-328`) | Messung | nicht prüfbar ohne Hardware |
| M11 | höchstens acht Filamente je Objekt (`README.md:449-451`) | `core/types.py:534` `MAX_SLOTS = 8` | eingelöst |
| M12 | „Teil wählen → rechts Dezimieren, Glätten, Neu vernetzen“ (`README.md:344`) | App: „Dreiecke verringern“, „Glätten“, „Dreiecke angleichen“ (Teilbericht B, Punkt 9) | teilweise (Namen) |

## 7. Bauplan §2.2 und §31 (eigene Prüfung)

| ID | Soll | Einlösung | Urteil |
|---|---|---|---|
| Bp1 | Weg 1: ablegen → Einheitenfrage → Prüfbericht → anklicken → Chat oder Kontextmenü → Vorher/Nachher → übernehmen → exportieren | `tests/test_way_one.py` (Kern, ohne Chat-Teil laut Docstring); URL-Ablegen siehe C14; Kontextmenü siehe B13 | nicht prüfbar ohne Fenster (Welle 2) |
| Bp2 | Weg 2: Grundformen/Bausteine/Skizzen oder Agent → Parameter → Parameterleiste → Maße ändern → exportieren | `tests/test_way_two.py`; Agent B31 | nicht prüfbar ohne Fenster/Sprachmodell |
| Bp3 | Weg 3: Text/Bild → Mesh → Reparatur automatisch → Bericht → teilen/verstiften → exportieren | `tests/test_way_three.py` mit geskriptetem Generator; RM-004 realer Lauf offen | nicht prüfbar ohne GPU/ComfyUI |
| Bp4 | Weg 4: verschmelzen → vernetzen → formen, Skelett → Bericht → exportieren | `tests/test_way_four.py`; B26 | nicht prüfbar ohne Fenster |
| Bp5 | §31 Navigation flüssig bei 1 Mio., Anzeigeaufbau < 4 s, Dezimierung ab 500 000 | `tests/test_performance.py:1366` u. a.; RM-070, RM-203 offen | nicht prüfbar ohne Fenster/Referenzmaschine |
| Bp6 | §31 Boolesch 200 000 < 2 s, Wandstärkenkarte < 3 s, Projekt öffnen < 1 s, Solver < 100 ms, Orientierung < 20 s | `test_performance.py:1322, 897, 1021, 750, 914` (nur `-m performance`, nur Release) | nicht prüfbar ohne Referenzmaschine |
| Bp7 | §31 Merkmalserkennung 200 000 Dreiecke < 1 s (mechanisch **und** organisch) | Lochplatte 0,99 s (RM-208), RM-132 Freiform 1,004 s, RM-193 Drache 3,83 s | teilweise |
| Bp8 | §31 Schichtanalyse 200 000 Dreiecke < 300 ms | `test_performance.py:775, 814`; hohler Körper 1,5 s (RM-201) | teilweise |
| Bp9 | §31 Parameteränderung → sichtbar < 2 s | RM-208: 0,04 s ab der zweiten Zahl, erste 0,5 s (Einzelmessung) | nicht prüfbar ohne Fenster |
| Bp10 | §31 Start bis bedienbar < 3 s kalt und warm | Commit `e08953fb`: 2,85 → 1,42 s (Entwicklerrechner, warm); kalt nicht gemessen | nicht prüfbar ohne Referenzmaschine |

## 8. Sprachfassungen der Website (eigene Prüfung)

Verglichen: `index`, `features`, `ai-models`, `security` je Sprache gegen die
deutsche Quelle, Abschnitt für Abschnitt in Ankerreihenfolge (Sonde `E/cmp2.py`,
`E/cmp3.py`), dazu die FAQ-Antworten aus dem JSON-LD.

| ID | Prüfung | Ergebnis | Urteil |
|---|---|---|---|
| L1 | Zahlen je Abschnitt (136, 35, 51, 18, 11, 39, Daten, MB, Port, Mrd.) | keine Abweichung; Unterschiede nur Schreibweise (Monatsnamen, „Achtzigerabstand“ → 80, „14 000 millones“) | eingelöst |
| L2 | Struktur (Absätze, Listen, `details`, Abbildungen, Überschriften, FAQ-Fragen) | je Abschnitt identisch in allen fünf Sprachen; nur Fußzeilenlinks weichen ab | eingelöst |
| L3 | Kaufzeile `ai-models.html:80/82` in allen Sprachen „ab 1.0 Einmalkauf, kein Abo“ | gleiche Spannung zu `index.html:317-319` „noch kein Angebot“ | teilweise |
| L4 | Changelog-Seiten je Sprache | aus `changelog/<sprache>.md`, gleiche Gliederung (`tests/test_changelog.py`) | eingelöst |
| L5 | Rechtstexte nur deutsch, fremdsprachige Seiten verlinken sie | `/impressum.html`, `/datenschutz.html`; EULA erklärt Deutsch als Vertragssprache | eingelöst |

**Wichtig:** Jede inhaltliche Lücke der deutschen Seite steht in allen sechs
Sprachen gleich da (Generator-Satz, Kontextmenü, „jeder Befund“, M5-Satz,
Bereichstest, Link-Ziehen). Eine Korrektur muss über alle sechs Fassungen
gezählt werden (`website/CLAUDE.md`, „Eine Falle bei den sechs Sprachfassungen“).

## 9. Presseentwürfe `marketing/presse-0.5.0/` (25 Mails, nicht versandt)

Versandsperre laut `README.md:10-28`: 0.5.0 veröffentlicht, **RM-188
abgeschlossen**, Adressen neu geprüft. RM-188 ist nicht abgeschlossen (P3.3–P3.5,
P4.0–P4.3, P5.1–P5.3, P6.x, P7.x offen, `ROADMAP.md:1754-1766`).

| Versprechen (Beispielfundstelle) | Prüf-ID | Urteil |
|---|---|---|
| STL hinein, exakter Körper, STEP hinaus (01:23-28; 07; 09; 13; 16) | A16 | nicht eingelöst |
| Muster in heruntergeladenem Modell anklicken, neue Teilung setzen (01:52-54; 07; 13; 19; 20) | A13 | teilweise |
| Gewinde-Gegenstück im Tabellenmaß; 6,4 × 1,1 wird nicht M6; importiertes Gewinde mit Gangzahl und Händigkeit (18:6-10; 13; 15) | A17 | teilweise |
| Prüfbericht nennt Insel, Lage, Stützmaterial, Drehwinkel (01:44-47; 04:35-38; 08; 17; 19) | C2 | nicht eingelöst |
| „Spiel für PETG“, Materialwechsel → Passung folgt (02:36-41; 03; 18:16-24; 25) | C5 | teilweise |
| Maßherkunft „gemessen, eingepasst, aus dem Schritt“ (04:23-25; 09; 15) | A18 | teilweise |
| Identität: schließen + neu bohren = neues Merkmal, verschieben behält Bezug (04:26-29; 15) | A19 | teilweise |
| Keine Kernwahl mehr, Solidon sagt, wo exakt nicht geht (01:26-28; 04; 22) | A15 | eingelöst |
| Maße im Bild mit Vorschau beim Tippen, Rechtsklick wechselt Bezug (01:17-21; 06; 23) | A11 | nicht prüfbar (Fensterabnahme) |
| Resin-Drucker, keine Düsen-/Brim-/Brückenratschläge (06; 17; 23) | C10 | teilweise |
| Offene Stellen beim Einlesen geschlossen (06; 22; 23) | C15 | teilweise |
| „bounded recognition“ nach Auflösung des Verfahrens (16) | A22 | teilweise |
| Nach einmaliger Freischaltung offline, Offline-Aktivierung über Datei (04; 05; 22) | D15 | eingelöst |
| Sechs Sprachen, Oberfläche und vollständiges Handbuch (21; 25) | D18 | eingelöst |
| Demo kostenlos und vollständig bis Ende Oktober (alle) | D1 | eingelöst |
| **P1** „Einmalkauf in drei Stufen“ / „three tiers“ (05:34-35; 12; 22:49) | P1 | nicht eingelöst — EULA/AGB: zwei Lizenzarten (privat, gewerblich); Preise unveröffentlicht |
| **P2** „KI-Funktionen sind abschaltbar“, „wahlweise lokal auf der eigenen Grafikkarte“ (04:42; 05:13-14; 16; 20; 24) | P2 | teilweise — kein Schalter, nur Schlüssel entfernen (`dialogs.py:949`); lokal siehe D12 |
| **P3** „Fusion kostet gewerblich rund 700 Euro im Jahr … zehn aktive Dokumente“ (05:37-39) | P3 | nicht prüfbar (Fremdangabe, vor Versand belegen) |

## 10. Seite `ki-modelle.html` (nur dort stehende Versprechen)

| Versprechen (Fundstelle) | Prüf-ID | Urteil |
|---|---|---|
| GLB/STL texturiert, Farben überleben, Reparaturkette, Farben auf Filamente „auf die Zahl, die wirklich in der Maschine steckt“, teilen/verstiften, 3MF mit Materialgruppen (`:90-99`) | C15 | teilweise |
| Vergleichstabelle: Wandstärke gegen Düse, Überhang je Schicht, Inseln, Brückenweiten/schmalste Stelle, Stützbedarf/beste Lage, Bett, Passungen (`:112-121`) | C16 | teilweise (Brücken, schmalste Stelle nur im Chat) |
| Bohrung im Netz wiedererkannt, gemessen, versetzbar (`:128-130`) | A1/A3 | teilweise/eingelöst |
| **K1** TripoSG, MIT laut Quelltext/Modellkarte, Kette wird geprüft; Einrichtung nur auf Wunsch, nichts ungefragt (`:137-142`) | K1 | eingelöst (`comfy_dialog.py`, `backends/mesh.py:25-29`) — widerspricht aber `index.html` (D28) |
| qwen3:14b, 106 Werkzeuge, 16 GB, 17 s (`:145-151`) | D12 | teilweise |
| GPU-Nutzung ausgewiesen (`:152`) | D13 | eingelöst |
| „Ab 1.0 einmal kaufen — kein Abo“ (`:80`) | L3 | teilweise |

## 11. Changelog `changelog/de.md` — 0.5.0 (74 Punkte) und 0.4.0–0.4.4 (247 Punkte)

Die Punkte sind über ihre Prüf-ID erfasst; nur dort stehende Punkte tragen eine
CL-ID. Das Update-Fenster zeigt die letzten drei Fassungen (`core/changes.py:20`),
in 0.5.0 also 0.5.0, 0.4.4 und 0.4.3.

| Gruppe (Zeilen) | Prüf-IDs | Urteil zusammengefasst |
|---|---|---|
| 0.5.0 Erkennen (47-60) | A1, A17, A18, A19, A23 | teilweise; Leistungszahlen meist Einzelmessungen (A23) |
| 0.5.0 Muster (64-66) | A13, A14 | teilweise (nur eigene Muster neu setzbar) |
| 0.5.0 Bearbeiten am exakten Modell (70-84) | A15, A17, A12 | am exakten Körper eingelöst; STL-Nutzer hat davon nichts (A16) |
| 0.5.0 Bohren und Maße im Bild (88-99) | A11, A12 | umgesetzt, Fensterabnahme offen (RM-197, RM-199) |
| 0.5.0 Prüfen und Drucken (103-116) | C10, C18, CL1, CL3 | überwiegend eingelöst |
| 0.5.0 Einlesen (120-125) | C11, C15, B20, CL2 | teilweise (C15) |
| 0.5.0 Bedienung und System (129-138) | D29, D16, D28, CL5, CL6, CL10, CL11 | eingelöst; „Vorschau ein Achtel“ nicht belegt (A23) |
| 0.4.4 (142-174) | A20, B26, C12, C20, C3, C1 | überwiegend eingelöst; RM-163 (Bambu halb) |
| 0.4.3 (178-204) | A21, B24, B25, B28, B29, B30, CL4 | eingelöst bis auf CL4 und Fensterabnahmen (RM-184) |
| 0.4.2 (208-272) | B1, B5, A3, A7 | überwiegend eingelöst |
| 0.4.1 (276-403) | A20, C4, C12, C20, D15, CL7, CL9 | überwiegend eingelöst; RM-164 Creality-Konsole ungeprüft |
| 0.4.0 (407-494) | B18, C11, C12, CL8 | eingelöst |

| ID | Versprechen (Fundstelle) | Einlösung | Urteil |
|---|---|---|---|
| CL1 | Keilförmige Wand → rät Außenwand zuerst (0.5.0 Z. 109) | `slice/advise.py:62, 933` in `advise()` (Druckdialog) | eingelöst |
| CL2 | Dreiecke verringern zerreißt nicht, Bericht nennt Teilezahl (0.5.0 Z. 124-125) | `geom/mesh_ops.py:1433-1454` `mesh.components_split`; `tests/test_missing_ops.py:98` | eingelöst |
| CL3 | Formabweichung als Karte, schnell, an Rundungen genau (0.5.0 Z. 108, 112, 116) | RM-188 P1.6 „implementiert, Release-Abnahme offen“ | nicht prüfbar ohne Fenster |
| CL4 | „Ein Projekt wird auf jedem Rechner gleich erkannt und gleich bearbeitet“ (0.4.3 Z. 185) | RM-186 (Ubuntu fehlt eine Fläche), RM-187 (Änderungsweg offen), RM-210 (lageabhängig) | teilweise |
| CL5 | „Die Einrichtung für ‚Modell aus Text‘ holt das fehlende Bildmodell selbst“ (0.5.0 Z. 131) | `comfy_setup.py:78-109` SDXL; RM-003 | eingelöst (widerspricht D28) |
| CL6 | „Solidon startet in der Hälfte der Zeit“ (0.5.0 Z. 132) | Commit `e08953fb` 2,85 → 1,42 s | eingelöst (Entwicklerrechner) |
| CL7 | Rückmeldebogen nach 15 min einmal je Version (0.4.1 Z. 346) | `core/feedback.py:48-51` | eingelöst — Rechtstexte sagen anderes (R2) |
| CL8 | Jeden Baustein als OpenSCAD-Quelltext ausgeben, Katalog und CLI (0.4.0 Z. 415) | `ui/catalog.py:155, 326` „Als OpenSCAD-Datei schreiben …“ | eingelöst (Schreiben, kein Ausführen — Regel 11 gewahrt) |
| CL9 | Mac-Pakete signiert und notarisiert (0.4.1 Z. 401) | RM-001: Mac mit 0.4.1/0.4.3 belegt | nicht prüfbar für das 0.5.0-Paket |
| CL10 | Hält ein Assistentenschritt an, nimmt der Vorschlag ihn ganz zurück (0.5.0 Z. 134) | Commit `e08953fb` `_DocumentState`, `proposal.stopped = "halted"` | eingelöst |
| CL11 | Rückgängig sofort statt 2,5 s; Verschieben 200 000 Dreiecke 0,5 s statt 8 (0.5.0 Z. 135-136) | RM-208 Tabelle (Undo 2,6 → 0,2 s; Verschieben 8,6 → 0,5 s), kein Test | eingelöst (Einzelmessung) |

Summe CL: 8 eingelöst (CL1, CL2, CL5, CL6, CL7, CL8, CL10, CL11), 1 teilweise
(CL4), 2 nicht prüfbar (CL3, CL9).

## 12. Seitentabellen: Startseite und Funktionsseite → Prüf-ID

### `website/index.html`

| Zeile | Versprechen (kurz) | Prüf-ID | Urteil |
|---|---|---|---|
| 7, 26, 43 | lokal, ohne Konto, ohne Abo, ohne Telemetrie | D3, D4 | eingelöst |
| 40 | Windows 10/11, macOS, Linux | D24 | nicht prüfbar |
| 221-225 | hineinziehen, Maß ändern, Bohrung setzen, Passung wählen, Druckbarkeit vor dem Slicen | A2, A3, C5, C1, C3 | teilweise |
| 236 | bis 1.0 nur kostenlose 0.x-Demos | D1 | eingelöst |
| 241-261 | offline, kein Konto, keine Telemetrie, Dateien bleiben deine, drei Systeme | D3, D4, D24 | eingelöst / nicht prüfbar |
| 272-278 | Rollenhalter in 20 Schritten, Regler 55–90 mm | B32 | teilweise |
| 292-309, 829-830 | Download 0.4.4, Größen | — | beim Release zu erzeugen |
| 313-316 | vollständig, ohne Schlüssel, keine Sperren, bis 30.10. | D1 | eingelöst |
| 322-328 | Windows-Hinweis, macOS notarisiert, Linux-Pakete | D24, CL9 | nicht prüfbar |
| 331 | Update-Prüfung, Laden nach Bestätigung, abschaltbar | D5 | eingelöst |
| 333 | Handbuch „Die ersten fünfzehn Minuten“ | D19 | eingelöst |
| 365-370 | 136 / 35 / 51 / 18 / 11 / 0 | D6, B14, C10, D20 | eingelöst |
| 382-384 | kein Konto, keine Einrichtung, elf Beispiele | D20, D21 | teilweise |
| 385-388 | Prüfbericht sofort, jeder Befund mit Vorschlag | C1 | teilweise |
| 389-391 | anklicken, Zahl ändern, Passung, Export oder Slicer | A2, C5, C19 | teilweise |
| 398-400 | vier sichtbar, sieben hinter „Was kann das noch?“ | D20 | eingelöst |
| 416-421 | Bohrung in fremder STL ändern, versetzen, kippen, verdoppeln, entfernen; Wandstärke gemessen | A1, A3, A7 | teilweise |
| 425-427 | Schichtanalyse zeigt Inseln, Überhänge, dünne Wände, Stützbedarf vorher | C3 | teilweise |
| 431-433 | Passungen aus Kalibrierleiter, „nicht geschätzt“ | C5, C6 | teilweise |
| 437-439 | Auto-Split mit Stiften, Bohrungen, Passungen | C7 | eingelöst |
| 448-449 | vier Wege, eine Szene | Bp1–Bp4 | nicht prüfbar |
| 460-465 | Weg 1: Verweis von MakerWorld/Printables/Thingiverse ziehen, Chat oder Kontextmenü | C14, B13 | nicht eingelöst |
| 476-478 | Weg 2: Agent legt Parameter an, setzt Bausteine | B31 | nicht prüfbar |
| 489-495 | Weg 3: aufbereiten; Einrichtung eines Modells „erst wieder verfügbar“ | C15, D28 | teilweise / nicht eingelöst |
| 506-512 | Weg 4: sechs Pinsel, ein Schritt, Wandstärke läuft mit | B26 | eingelöst |
| 521-557 | Galerie: dieselben Menüs; Gehäuse zwölf Schritte, 79 134 Dreiecke | B32 | teilweise (13 Schritte) |
| 562-580 | Aufbereiten in zwei Klicks, sagt vorher, was es ändert | C15 | teilweise |
| 584-589 | Fensteraufbau | D23 | nicht prüfbar |
| 613-622 | Prüfbericht mit Zählung; Bausteine in sechs Gruppen, Normteiltabelle | C1, B14 | teilweise / eingelöst |
| 627-631 | KI-Agent, ein Undo, 39 Referenzanfragen | D9, D10 | eingelöst |
| 632-635 | angeklickte Fläche zählt; Bohrung+Senkung in einem Schritt; Menü einer Fläche mit Bausteinen | B21, B13 | teilweise / nicht eingelöst |
| 636-639 | Merkmal anfassen, Kennung bleibt, Passung behält Bezug | A3, A8, A19 | teilweise |
| 640-642 | Befund springt an die Stelle, Handlungsvorschlag | C1 | teilweise |
| 643-645 | Wandstärke 2,40 → 3,60 rechnet neu | B7 | eingelöst |
| 646-648 | Normteiltabelle, jeder Baustein über ganzen Bereich durchgerechnet | B14, B15 | nicht eingelöst (Bereich) |
| 649-652 | eigene Bausteine als Rezept | B18 | eingelöst |
| 653-655 | Schichtanalyse, Orientierungssuche | C3 | teilweise |
| 656-659 | Zeichnen mit Bedingungen, exakte Kurve | B1, B3 | teilweise |
| 660-663 | Reliefs, Gitter, Formschrägen, Deckel, mehrfarbige Beschriftung | B20, A20, B23, B27 | eingelöst |
| 672-706 | Bohrung+Senkung, Organizer, Lochfelder, Filamentlager, MCP | A12, B28, B29, C12, D14 | eingelöst / teilweise (C12) |
| 716-721 | Generator-Aufbereitung; lädt derzeit kein Modell | C15, D28 | nicht eingelöst (D28) |
| 732-736 | kein Slicer, Übergabe, G-Code-Gegenprobe; kein Cloud-CAD | C4, D4 | teilweise / eingelöst |
| 742-750 | keine Maßgarantie aus Generatornetzen; Ollama 14 Mrd., 16 GB | D12 | teilweise |
| 760-800 | Demo kostenlos, nicht beschnitten, KI optional, Ziel vor Modellkontakt | D1, D6, D7 | eingelöst |
| 804-805 | ZIP/JSON; Export STL, 3MF, OBJ, PLY, STEP (GLB fehlt) | C13, D26 | eingelöst |
| 809-812 | Sicherheitskontakt, Updates bis 31.10.2031 | D27 | eingelöst |
| 824-846 | Systemvoraussetzungen | D24 | nicht prüfbar |
| 856-865 (FAQ) | 30. Oktober, Statuszeile, Dateien unberührt | D1, D2, D26 | eingelöst |
| 873-878 (FAQ) | ohne Konto und Netz; Export STL, 3MF, STEP, OBJ „die jedes CAD kennt“ | D3, A16 | teilweise (STEP nur exakte Körper) |
| 890-893 (FAQ) | jedes Werkzeug sagt den nächsten Klick | B5 | teilweise |
| 897-905 (FAQ) | eigene Bausteine | B18 | eingelöst |
| 909-916 (FAQ) | Bohrung in STL verschieben, Handlungsmatrix, „Kehlen ausgenommen“ | A7 | teilweise |
| 920-938 (FAQ) | ohne KI alles; KI rechnet nicht; MCP | D6, D9, D14 | eingelöst |
| 942-944 (FAQ) | Datenwege | D4, D8 | eingelöst |
| 948-955 (FAQ) | Formate lesen/schreiben | C13 | eingelöst |
| 959-971 (FAQ) | Mac, Flatpak | D24, D31 | nicht prüfbar / eingelöst |
| 975-981 (FAQ) | 18 Profile; eigene mit Bauraum und Schichthöhe | C10 | teilweise |
| 985-999 | nach der Demo; „es antwortet ein Mensch“ | — | organisatorisch |

### `website/funktionen.html`

| Zeile | Versprechen (kurz) | Prüf-ID | Urteil |
|---|---|---|---|
| 105-137 | Merkmale in fremder STL, Felder, Handlungen, „Durchgangsloch für M5“, sechs Bohrungen in einem Zug, Abstand zweier Merkmale, Matrix | A1–A7 | teilweise; A4 nicht eingelöst |
| 191-207 | Griff am angeklickten Merkmal, Geist, Schatten, Bewegen-Leiste mit Grund | A8–A10 | eingelöst |
| 248-274 | Zeichnen, Bedingungen, Freiheitsgrade, fünf Körperwege, exakter Kreis, Raster, Hilfslinie | B1–B6 | teilweise |
| 278-291 | non-destruktiv, Projektparameter, Grenzen änderbar, mehrere Schritte verschieben | B7–B10 | teilweise (B10) |
| 324-348 | Bausteine an angeklickter Fläche, Kontextmenü, sechs Gruppen, über ganzen Bereich getestet, fragt nach, Katalog ohne Modell, Baum | B13–B17 | nicht eingelöst (B13, B15) |
| 359-386 | eigener Baustein, Eckenrechnung, Rezept | B18 | eingelöst |
| 388-415 | acht Muster, Abweisung zu feiner Stege, Relief, Gitter | B19, B20 | eingelöst |
| 417-436 | Prüfbericht, Sprung, jeder Befund mit Vorschlag; Bild passt nicht zum Text | C1 | teilweise |
| 438-483 | Schichtanalyse, Herkunft Analyse/G-Code | C3, C4 | teilweise |
| 485-553 | Linie ziehen, vier Stiftformen, Passung bleibt; Abschneiden; Automatisch teilen; 18 Profile | C7–C10 | teilweise (C8) |
| 556-586 | Filamentlager | C12 | teilweise |
| 588-609 | fx, `schraube_m4 + spiel`, zwei bis drei Werte vorn, 136 Operationen, Kontextmenü | B11, B12 | teilweise |
| 611-673 | KI-Agent, 39 Anfragen, 28/39 und 98 % | D9, D10, D11 | eingelöst / teilweise |
| 675-705 | MCP | D14 | eingelöst |
| 707-727 | elf Beispiele, Handbuch in derselben Sprache | D18, D20 | eingelöst |
| 735-743 | Grundkörper exakt, Boolesch, Bohrung mit Senkung in einem Schritt | B21 | eingelöst |
| 745-749 | Anordnen, Zielmaß, Muster, Ausrichten | B22 | eingelöst |
| 751-756 | Verrunden, Fase, Wulst, Fläche versetzen, Formschräge an STL und exakt; „STEP bleibt für exakte Körper“ | A20 | eingelöst |
| 758-764 | Aushöhlen, verdicken, Deckel, Drehdeckel | B23 | eingelöst |
| 766-776 | Profilklemmen „zur gewählten Normgröße“ | B24 | teilweise (nur M4) |
| 778-790 | Dichtnut und Dichtung | B25 | nicht prüfbar (Fenster, RM-184) |
| 792-796 | Formen, Skelett | B26 | eingelöst |
| 798-805 | Beschriften, Filamente, Texturfarben, farbige 3MF | B27 | eingelöst |
| 807-813 | Bett, Baugruppe, Ausrichten, Kollision, Übergabe mit Einstellungen, G-Code | C11, C4 | eingelöst / teilweise |
| 815-820 | Kalibrieren, Prüfstück, Elefantenfuß, Fügeweg | C6 | eingelöst |
| 822-827 | Netzpflege | CL2 | eingelöst |
| 829-834 | Formate, Projektinhalt | C13 | eingelöst |
| 837-839 | Messen, Schneiden, Explosion | B33 | eingelöst |
| 843-847 | Navigation und Schemata | D22 | eingelöst |
| 851-861 | KI lokal oder Schlüssel; MCP | D6, D14 | eingelöst |
| 864-867 | Referenz aus dem Register | D19 | eingelöst |
| 875-909 | Bohrung samt Senkung ändern, Modi, ein Undo | A12 | eingelöst |
| 912-923 | Organizer, Lochfelder | B28, B29 | eingelöst |
| 925-930 | Textur weiterbearbeiten, „Gesamte Fläche“ | A14 | eingelöst |
| 934-942 | Konturauswahl, lokale Erkennung | B30, A21 | eingelöst |

Die `data-operations` der Funktionsseite decken das Register vollständig und
ohne Überschuss ab (136 = 136, Sonde `ops_site.py`).

## 13. Teilberichte

- `F:\3D Druck.review-050\reports\sollliste-A-merkmale.md` — A1–A23 mit
  Belegen, Leistungszahlen (A23), acht Textwidersprüche, zwei Nebenbefunde
  (`FEATURE_TITLES` ohne „torus“, `bore_advice(ask=True)` bietet M4/M6 statt M5).
- `F:\3D Druck.review-050\reports\sollliste-B-konstruieren.md` — B1–B34,
  zwölf Widersprüche Text ↔ App, Lücken nach Schwere.
- `F:\3D Druck.review-050\reports\sollliste-C-drucken.md` — C1–C20, AST-Zählung
  der Befunde ohne Handlung, dreizehn Widersprüche, tote Funktion
  `advise.warnings_for`.

## 14. Für die Welle 2 („texte“, „kundenwege“) und das Register

- **Texte (RM-084):** Startseite 460-462 (Link-Ziehen), 492-495/719-721/841-843
  (Generator, D28), 632-635/`funktionen.html:328-332` (Kontextmenü),
  `funktionen.html:124-126` (M5), 339-341/646-648 (Bereichstest), 426-427
  (jeder Befund), 593 (Formelbeispiel), 595 (zwei bis drei Werte), 290
  (Verschieben), 626-629 (Suite-Quote), `ki-modelle.html:145-151` (lokales
  Modell), `DATENSCHUTZ.md:26, 68, 70`, `EULA.md:317` und §9-Liste, `README.md:37-54`
  — jeweils in allen sechs Sprachen.
- **Kundenwege am Fenster:** Weg 1 mit einem Printables-Seitenlink (C14), eine
  Rändel-STL aus dem Netz (A13), eine M5-Durchgangsbohrung in einer fremden
  STL (A4), PETG-Teilung mit anschließendem Materialwechsel (C5), Befunde ohne
  Knopf an einem Mehrfarbauftrag (C1, `gcode.spool_left_out`).
- **Presse:** vor Versand A16 und C2 aus allen 25 Mails streichen oder als
  Ausblick kennzeichnen; P1 („drei Stufen“) und P3 (Fusion-Preis) belegen oder
  streichen; die README-Sperre (RM-188) ehrlich anwenden.
- **Registersatz-Vorschlag:** „Sollliste 0.5.0 (22.09.2026): 160 Versprechen,
  87 eingelöst, 42 teilweise, 11 nicht eingelöst, 20 nur am Fenster/an der
  Hardware prüfbar; zehn Lücken hoch oder kritisch, Bericht
  `review-050/reports/sollliste.md`.“
