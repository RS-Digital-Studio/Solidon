# Sondierung: konzept-erzeugen-agent-oberflaeche-2026-08.md

**Titel:** Konzept — Erzeugen, Agent, Oberfläche
**Stand laut Dokument:** 12.08.2026
**Zweck:** Bestandsaufnahme in drei Bereichen, die das Wettbewerbspapier nur streift: Bild-zu-3D über ComfyUI samt Lizenzlage der Modelle, der lokale Agent gegen Ollama, und die Oberfläche im Vergleich zu Meshy, Hyper3D, Fusion und Shapr3D — mit Messwerten und den Vorschlägen D1, L1, B1, A1/A2, M1, H1.

**Alterung:** 5/5 — Die Kernempfehlungen stehen auf zwei schnell alternden Sockeln: Preise und Funktionsumfang fremder KI-Dienste (Meshy-Credits, Rodin-Stufen, fal.ai je Lauf) und die Lizenzlage generativer 3D-Modelle. Gerade die EU-Ausnahme bei Hunyuan3D ist der Punkt, an dem eine Nachbesserung des Anbieters den Vorschlag L1 hinfällig machen würde. Dazu kommen interne Zählwerte, die schon beim Schreiben veraltet waren (88 → 96 Werkzeuge, 104 → 110 KB), sechs Vorschläge, die inzwischen umgesetzt sein können, und ein Viewport-Befund, dessen Nachweis das Dokument selbst als unvollständig markiert. Länger halten die Urteile in Teil 6.2, 7 und 8.

## Gliederung

- Teil 1 — Der Befund, der alles andere überholt
- Teil 2 — Bild zu 3D: es klappt, und dann hört es auf
- Teil 3 — Der Blocker unter dem Erzeugen: die Lizenzen
- Teil 4 — Brauchen wir ComfyUI?
- Teil 5 — Der lokale Agent: gemessen, nicht vermutet
- Teil 6 — Meshy und Hyper3D: halten wir mit?
- Teil 7 — Oberfläche und Design gegen die anderen
- Teil 8 — Handbuch gegen Meshys Doku
- Teil 9 — Was daraus zu tun ist

## Extern prüfbare Behauptungen (20)

- **[hoch/recht] Tencent Hunyuan3D 2.0/2.1/Omni (Tencent Community License)** — Die Lizenz beider Hunyuan3D-Fassungen trägt die Kopfzeile „THIS LICENSE AGREEMENT DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA"; Territory schließt die EU ausdrücklich aus  
  _Ort:_ Teil 3.1
- **[mittel/recht] Hunyuan3D GitHub-Issue** — Eine Bitte, die EU in die Lizenz aufzunehmen, liegt seit Monaten unbeantwortet als Issue im Projekt  
  _Ort:_ Teil 3.1
- **[hoch/recht] BRIA RMBG-2.0** — RMBG-2.0 steht unter CC BY-NC 4.0, also nicht kommerziell nutzbar  
  _Ort:_ Teil 3.2 / Tabelle 3.3
- **[hoch/recht] Step1X-3D (StepFun)** — Step1X-3D steht unter Apache-2.0, kommerziell und in der EU nutzbar  
  _Ort:_ Tabelle 3.3
- **[hoch/recht] TripoSG / TripoSR (Tripo AI / VAST)** — TripoSG und TripoSR stehen unter MIT, kommerziell und EU-tauglich  
  _Ort:_ Tabelle 3.3
- **[hoch/recht] Microsoft TRELLIS, NVIDIA nvdiffrast, diffoctreerast** — TRELLIS ist MIT, die Pipeline zieht aber nvdiffrast und diffoctreerast, beide ausdrücklich nicht-kommerziell  
  _Ort:_ Tabelle 3.3
- **[mittel/recht] BiRefNet / InSPyReNet** — BiRefNet und InSPyReNet (Freistellen) stehen unter MIT  
  _Ort:_ Tabelle 3.3
- **[mittel/funktionsumfang] hy3dgen / PyTorch / CUDA** — Modell direkt in Python würde PyTorch + CUDA in die Auslieferung zwingen; Gewichte 10–29 GB  
  _Ort:_ Teil 4, Tabelle
- **[hoch/preis] fal.ai** — Gehostete API fal.ai: 0,16 $ je Lauf ohne Textur  
  _Ort:_ Teil 4, Tabelle
- **[hoch/preis] Meshy AI** — Meshy Einstieg 0 $ mit 100 Credits pro Monat unter CC BY 4.0  
  _Ort:_ Teil 6.1
- **[hoch/preis] Meshy AI** — Meshy Pro 20 $/Monat mit 1000 Credits  
  _Ort:_ Teil 6.1
- **[hoch/preis] Meshy AI** — Meshy Bild→3D kostet 20 Credits ohne Textur, 30 mit Textur, 35 bei 8K  
  _Ort:_ Teil 6.1
- **[hoch/preis] Meshy AI** — Meshy: Remesh 5, Rigging 5, Animation 3, 3D-Print-Reparatur 10 Credits, Analyse gratis; Mehrfarbe 10  
  _Ort:_ Teil 6.1 / 6.2
- **[mittel/funktionsumfang] Meshy AI API** — Meshy-API erst ab Pro verfügbar  
  _Ort:_ Teil 6.1
- **[hoch/preis] Hyper3D Rodin** — Hyper3D/Rodin: 7-Tage-Test, Creator 30 $, Business 120 $; API ab Business  
  _Ort:_ Teil 6.1
- **[mittel/funktionsumfang] Hyper3D Rodin** — Hyper3D/Rodin: ~4–5 s je Modell, bis 10 Mio. Polygone; PBR, UVs, ControlNet, Teilbearbeitung, Plugins für Blender/Unity/Unreal/Maya  
  _Ort:_ Teil 6.1
- **[niedrig/funktionsumfang] Meshy AI / Hyper3D Rodin** — Beide bieten die Formate GLB/FBX/OBJ/STL/USDZ  
  _Ort:_ Teil 6.1
- **[hoch/marktlage] Meshy AI 3D-Print** — Meshy hat seit kurzem 3D-Print-Funktionen (Analyse gratis, Reparatur, Mehrfarbe) — im Papier als Warnsignal gewertet  
  _Ort:_ Teil 6.2
- **[mittel/api] Meshy AI API-Dokumentation** — Meshys API-Doku hat vier Bereiche, 17 Endpunkte, dazu Fehlercodes, Ratengrenzen, Webhooks und eine Preisseite mit Credit-Kosten je Aufruf  
  _Ort:_ Teil 8
- **[mittel/funktionsumfang] Autodesk Fusion, Shapr3D, Plasticity** — Fusion und Plasticity leben von Vorschau am Zeiger und Werten am Objekt; Fusion/Shapr3D haben Betriebsarten, Multifunktionsleiste und Anmeldezwang  
  _Ort:_ Teil 7

## Intern prüfbare Behauptungen (15)

- **[hoch]** Viewport blieb nach dem Laden leer; Fix `_render_now` in `show_scene` steht, der Nachweis fehlt — Fehler tritt sporadisch auf, vier grüne Läufe danach  
  _Prüfen:_ app/ui-Viewport auf `_render_now` lesen, Anwendung starten (`.venv\Scripts\python.exe -m app.ui.app`) und Modell laden; ROADMAP auf den Befund prüfen. Nächste Spur laut Papier: `WA_NoSystemBackground=False` und Stylesheet am `OverlayHost`  
  _Ort:_ Teil 1, Teil 9 Punkt 1
- **[mittel]** Bild→3D über den Dialog gemessen: 42,5 s / 1.588.016 Dreiecke, zweiter Lauf 44,9 s / 1.088.166 Dreiecke (ComfyUI lokal, RTX 4080)  
  _Prüfen:_ Erzeugen-Dialog mit laufendem ComfyUI erneut fahren und Dauer/Dreieckszahl vergleichen  
  _Ort:_ Teil 2.1
- **[hoch]** Die Erzeugen-Kette hat drei Transaktionen (Modell erzeugen → Auf Arbeitsgröße bringen → Reparaturkette); Dezimieren fehlt — Vorschlag D1 offen  
  _Prüfen:_ Erzeugen-Ablauf im UI-Dialog bzw. app/core/backends/mesh.py auf die Transaktionsfolge lesen; ROADMAP nach D1 durchsuchen  
  _Ort:_ Teil 2.2, Teil 9 Punkt 3
- **[hoch]** Am erzeugten Objekt werden 0 Merkmale erkannt; `perceive` winkt oberhalb einer im Code stehenden Größengrenze ab  
  _Prüfen:_ Grenzwert in app/core/perceive/ suchen und gegen die gemessenen Dreieckszahlen halten  
  _Ort:_ Teil 2.1, 2.2
- **[hoch]** `app/core/backends/data/image_to_mesh.json` setzt `"model": "RMBG-2.0"`; der mitgelieferte Graph nennt Hunyuan3D, das Handbuch ebenfalls — Vorschlag L1 offen  
  _Prüfen:_ Datei lesen, nach RMBG-2.0 und `Hy3D*`-Knotennamen greppen, Handbuchseiten durchsuchen; ROADMAP nach L1  
  _Ort:_ Teil 3.1, 3.2, Teil 9 Punkt 2
- **[mittel]** `MODEL_ROLES` in `backends/mesh.py` erlaubt den Rollentausch ohne Python-Änderung (Graph nennt die Rolle, nicht die Datei)  
  _Prüfen:_ app/core/backends/mesh.py auf MODEL_ROLES lesen  
  _Ort:_ Vorschlag L1
- **[mittel]** Ein zweiter Backend gegen fal.ai passt ohne Umbau in das `MeshBackend`-Protokoll; entspricht P11 aus dem Bauplan — B1 nicht gebaut  
  _Prüfen:_ MeshBackend-Protokoll in app/core/backends/mesh.py prüfen; Bauplan P11 nachschlagen  
  _Ort:_ Vorschlag B1
- **[hoch]** Der Agent sieht 96 Werkzeuge (85 Operationen + 11 eigene), Schema 110 KB, ein Zug endet nach höchstens acht Schritten  
  _Prüfen:_ Operationen im Register zählen (app/core/registry), Werkzeugschema aus app/core/agent erzeugen und dessen Größe messen; Schrittgrenze im Sitzungscode  
  _Ort:_ Teil 5
- **[hoch]** Gemessen wurde bei 88 Werkzeugen und 104 KB Schema — schon beim Schreiben überholt, das Register wächst weiter  
  _Prüfen:_ Aktuelle Werkzeugzahl gegen 88 und 96 halten  
  _Ort:_ Teil 5, Teil 8
- **[mittel]** qwen3:14b: 4/5 strukturiert, 3/5 richtig; `read_report` 121 s, `add_parameter` Zeitüberschreitung, `undo_transaction` rief `ask_user`. Urteil: „Brauchbar: keines."  
  _Prüfen:_ `check_local_model` erneut gegen die installierten Ollama-Modelle fahren  
  _Ort:_ Teil 5
- **[mittel]** A1 (nur passende Werkzeuge mitschicken) und A2 (`check_local_model`-Zahlen im Chat zeigen) sind offen  
  _Prüfen:_ grep check_local_model und applies_to-Filterung in app/core/agent bzw. app/ui; ROADMAP nach A1/A2  
  _Ort:_ Vorschläge A1/A2
- **[mittel]** Solidon liest GLB seit jeher und schreibt es „seit heute"  
  _Prüfen:_ app/core/export/ und app/core/ingest/ auf GLB-Schreiben und den zugehörigen Test prüfen  
  _Ort:_ Vorschlag M1
- **[niedrig]** Oberflächenzählungen: acht Beispielkacheln, neun Menüs, sechs Werkzeuge in der Zeile, links drei einklappbare Abschnitte, Dialog vorn sechs Werte; Musterdialog-Zweisprachigkeit samt 24 weiteren Auswahlwerten behoben  
  _Prüfen:_ Anwendung starten und zählen; tests/test_translations.py laufen lassen  
  _Ort:_ Teil 7
- **[mittel]** Bei 3413 px zerfällt das Verhältnis — linke Spalte auf 160 px gedrängt, Spalten sind für 1920 gebaut und wachsen nicht mit  
  _Prüfen:_ Hauptfenster auf breitem Bildschirm starten; Layout-/Splitter-Code in app/ui prüfen  
  _Ort:_ Teil 7, Teil 9 Punkt 6
- **[mittel]** Handbuch: 35 Seiten, 19.578 Wörter, zwanzig geschrieben; Fernsteuerungsseite und Operationsreferenz sind unverbunden (H1 offen)  
  _Prüfen:_ tools/make_manual.py laufen lassen und Seiten/Wörter zählen; Fernsteuerungsseite in app/core/manual.py lesen  
  _Ort:_ Teil 8