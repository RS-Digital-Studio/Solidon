# Prüfbericht `bedienlogik` zum Konzept Funktionsdurchgang (11.10., Entwurf)

Urteil: in dieser Fassung nicht tragfähig; aus Code und Regeln abgeleitet, nicht am Fenster.

## Schwer
- **S1 §3** Kennungen instabil: `window_commands` (Palettengerüst, `main_window.py:12121-12127`)
  nummeriert Menüzeilen nach Lage (`key = f"menu.{len(found) - overridden}"`, `:12247`), zählt 15
  `settings.*` (`:12165-12174`), fällt evtl. mit RM-735. Vorschlag: Kennung = Registername (Ops),
  Menüpfad aus unübersetzten Quelltexten (Fensterbefehle), fester Name aus Anleitungswortschatz
  (Bedienflächen); Einstellungen eine Zeile je Dialogabschnitt.
- **S2 §5** `guide_targets` erreicht die meisten Bedienorte nicht: ~30 feste Namen + `operation:`,
  `field:` (nur offener Operationsdialog, `guide_targets.py:312-317`), `history.last` (`:288`),
  Menüeinträge nur bei offenem Menü (`:328-329`). Fehlen: Merkmalfensterzeilen/-felder, Maßgruppe im
  Bild, Griffe, Kontextmenüs, Baum-/Verlaufszeilen, Bildschirmlage eines Merkmals — genau Weg 1
  (`griffe.md:232-288`). Vorschlag D0: `feature:<art>`, `panel.action:<op>`,
  `panel.field:<op>.<feld>`, `measure.field:<feld>`, `grip:<…>`, `context:<eintrag>`,
  `history.row:<n>`, `tree.row:<objekt>`; `test_guides.py` hält sie. D0-Aufwand reicht kaum.
- **S3 §4** Fehlende Prüfpunkte: 12 nachträglich ändern (§2.1, `grenzen.md:295-305`, `kern.md`),
  13 Auswahlstufen-Matrix (`grenzen.md:120-134`, `:157-162`), 14 Abbruch während der Rechnung (§15.6,
  `wartezeit.md:272-277`, `:287-295`), 15 Halt und Einfügemarke (`fenster.md:155-187`), 16
  Projektwechsel (`wartezeit.md:141-153`, `fenster.md:25-30`), 17 Agentenweg (`tool_schemas()`,
  Regel 16, §2.6), 18 Lizenzzustand (Demo/abgelaufen, `kern.md` „Die Lizenzgrenze“). Prüfpunkt 5:
  Escape/Dialog-Abbrechen (§18.11) ≠ Rechnung abbrechen; Redo je Plattform (`grenzen.md:348-353`).
  Prüfpunkt 9: Zoll (§19.3, `oberflaeche.md:375-399`).
- **S4 §4/§5** Einfachheit/Verständlichkeit Geschmack → Kriterien E1–E7, V1–V6 (siehe unten);
  Abnahme: 10 % Stichprobe je Paket durch zweiten Agenten, < 90 % Übereinstimmung je Prüfpunkt →
  Kriterium schärfen.

## Kriterien
- E1 Klicks ≤ 3 (am Merkmal ≤ 2 nach Auswahl); E2 Pflichteingaben ≤ 1 bei 90 %; E3 Entscheidungen
  ohne Vorwissen ≤ 1; E4 Blickwechsel zwischen Zonen ≤ 2, Dialog verdeckt nicht die Stelle; E5 ≤ 3
  Felder vorn (höchstens 4), ≤ 25 Wörter über dem ersten Feld, übersetzt ≤ 35 (`grenzen.md:32-33`);
  E6 Nachfragen außerhalb Regel 19 = 0; E7 Sackgassen = 0.
- V1 Negativliste (`oberflaeche.md:99-107`) = 0, Positivliste Slicer-Wortschatz, beide versioniert
  neben `tests/data/text_patterns.json`; V2 Satzlängen nach `test_text_length`
  (`oberflaeche.md:131-136`); V3 Felder mit eigenem Satz 100 %, ≤ halbe Wortüberschneidung mit Titel;
  V4 Vorhersageprobe; V5 Meldungen „was, warum, was jetzt“, Handlungen geklickt und wirksam; V6 ≤ 1
  Kurzhilfe, nie Handbuch.

## Mittel
- M1 §6 Pakete über Kategorieschlüssel; fehlen `colour`, `label`, `fits`, `variants`, `parameters`
  (`registry.py:42-86`); Weg 4 (Formen/Skelett in `mesh`, `sculpt.py:2064`, `pose.py:942`) eigenes
  Paket; Wächter: jede Kategorie genau einem Paket.
- M2 §3 Bedienflächenliste unvollständig (Startseite, Generierung/ComfyUI, Zusätzliche Programme,
  Varianten, Nachbauen, örtliche Erkennung, STEP-/Konturauswahl, Organizer, Gegenstücke, Als Baustein
  speichern, Zahlen binden, Dichtweg, Vorher/Nachher-Regler, Karten verschieben/Reiter, Wiederherstellung,
  Speicherfrage, KI-/Druckhinweis, Rückmeldung/Fehlerbericht, Einladungen, Statusleiste, Über-Dialog;
  Prüfberichtshandlungen `FINDING_ACTIONS`, Merkmalfenster-Handlungen ohne Op, Verlaufskontextmenü) →
  erzeugen aus `app/ui/*dialog*.py`, `guide_targets`, `FINDING_ACTIONS`; Wächter je Dialogklasse.
- M3 Szenenkatalog in `tests/data/` aus Ops gebaut (je Merkmalsart, Kante, Kantenzug; exakt und Netz;
  zwei Körper; offen, mehrteilig, Hohlraum; langsame Szenen > 2 s und > 10 s; über Erkennungsgrenze;
  über `COARSE_PREVIEW_ABOVE`); externe Vorbedingungen je Zeile als Zustand (KI/ComfyUI/Slicer
  vorhanden/fehlt, Lizenz Demo/gekauft/abgelaufen über vorbereitetes APPDATA, Filament/Resin; 3D-Maus,
  zweiter Monitor nur Stufe C).
- M4 Grobe Vorschau ab `COARSE_PREVIEW_ABOVE` gewollt anders (`wartezeit.md:219-251`).
- M5 Szenenabdruck definieren (Ops, Parameter, Projektparameter, Passungen, Auswertungshash; Auswahl und
  Kamera getrennt); „bedienbar“ = größte Hauptthread-Lücke ≤ 100 ms (`wartezeit.md:432-436`); ohne
  §31-Budget „kein Budget“.
- M6 Schwere der Funde (schwer/mittel/leicht); Abnahme null schwere und null mittlere; geschlossene
  Liste der Gründe für *entfällt*.
- M7 RM-735 nicht im Register; Bauplan §2.6/§19.2 nennen Palette noch (`3d-agent-bauplan.md:230-231`,
  `:1512-1513`).
- M8 §8 Importgraph wählt alles; stattdessen Registerabdruck der Spec, Katalogschlüssel der Zeile,
  Klassen ihrer Wortschatzziele.

## Leicht
- L1 Suchproben aus externer Liste, Treffer unter den ersten drei. L2 Schwellen Zugänglichkeit
  (`oberflaeche.md:275-319`), „Bildschirmleser ungeprüft“. L3 Bilder nur Deutsch + längste
  Übersetzung, beide Themen; Textlänge automatisch. L4 Website aller Sprachen und `manual.help_for`.
  L5 Hauptwege durch Experten = kein Usability-Test; Schritte und Fehlversuche zählen.
