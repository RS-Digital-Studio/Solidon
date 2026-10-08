# RM-003 — Ersatz für TripoSG und die Vorstufen des Textwegs

Recherche vom 06.10.2026, nur lesend. Lizenzangaben sind an der Quelle
abgerufen (Lizenzdatei, Modellkarte, Dateiköpfe, Hugging-Face-API mit
`?blobs=true`, GitHub-API) und mit Commit bzw. Revision belegt. Das ist eine
technische Zuordnung, kein Rechtsurteil. Lizenzklauseln stehen sinngemäß mit
Abschnittsnummer; der Wortlaut liegt unter der genannten URL. Was nicht an der
Quelle belegt werden konnte, ist als **unbelegt** gekennzeichnet.

Stand: abgeschlossen am 06.10.2026. Ergänzt `lizenzkette.md` im selben
Ordner (dort die TripoSG-Kette und die Fragen 1–16).

## Kurzfazit

**Beste Wahl Bild→3D: TRELLIS.2-4B (Microsoft) über die eingebauten
ComfyUI-Knoten.** Code und Gewichte MIT, keine Gebiets-, Umsatz- oder
Nutzerschwelle. Seit ComfyUI v0.34.0 (26.08.2026) läuft das Modell im Kern
in reinem PyTorch/SciPy — ohne nvdiffrast, nvdiffrec, CuMesh, FlexGEMM oder
flash-attn, ohne Kompilieren, ohne eigenen Knoten. Damit entfallen genau die
Gründe, aus denen TRELLIS.2 am 31.08. verworfen wurde. Es ist zugleich der
heutige Standard (nach TRELLIS v1 das meistgeladene Bild-zu-3D-Modell auf
Hugging Face, offizielle ComfyUI-Vorlage) und im TRELLIS.2-Papier vor Hunyuan3D 2.1, Step1X-3D,
Direct3D-S2, Hi3DGen und TRELLIS v1. Ein direkter Kennzahlvergleich mit
TripoSG fehlt an der Quelle. Download ≈ 8,0 GB statt heute ≈ 8,4 GB (je
mit BiRefNet).

Zwei Haken bleiben: Der Bildkodierer **DINOv3** steht unter Metas eigener
*DINOv3 License* — weltweit und gewerblich erlaubt, aber mit Handels- und
Waffenklausel, einseitigem Änderungsrecht und zugangsbeschränktem Original
(Q2). Und die Netze sind nicht von selbst geschlossen: Die O-Voxel-Darstellung
erlaubt offene Flächen, und die ComfyUI-Vorlage erzeugt beim Remesh eine
Innenhülle (K1). Solidon muss also vor der Reparatur zum Volumenkörper
schließen. 16 GB VRAM sind praktikabel, 8 und 12 GB nicht belegt.

**Zweitbeste: Pixal3D** (Tencent ARC/Tsinghua, SIGGRAPH 2026), im selben
Kern-Graphen zuschaltbar. Gleiche Laufzeitkette plus MoGe-2 (MIT); im Papier
deutlich vor TripoSG (Toys4K IoU 93,6 gegen 73,5). Code und Gewichte seit dem
20.05.2026 MIT — **davor acht Tage unter einer Lizenz „nur Forschung, nicht
in der EU“**, für dieselben Gewichtsdateien. Das ist der Grund für Platz zwei.
Fällt DINOv3 bei der Kanzlei durch, ist **TRELLIS v1** (MIT, DINOv2 unter
Apache-2.0, FlexiCubes unter Apache-2.0) der Rückfall: auf Toys4K
mindestens gleichauf mit TripoSG, aber mit eigenem Knoten und spconv/xformers.

**Kette Text→Bild→Freistellen→3D ohne Gebiets- oder NC-Haken: ja.**
FLUX.2 [klein] 4B (Black Forest Labs, Apache-2.0, Textkodierer Qwen3-4B
ebenfalls Apache-2.0; ≈ 8,3 GB als fp8/fp4) oder gleichwertig Z-Image-Turbo
(Apache-2.0) statt SDXL → Solidons eigener Weiß-Keyer (kein Modell, Rückfall
BiRefNet) → TRELLIS.2 mit DINOv3 → Solidon.
**Ganz ohne Haken: nein.** Übrig bleiben die DINOv3-Vertragsbedingungen, die
Herkunft der 3D-Trainingsdaten (Objaverse mit NC-Objekten, HSSD CC BY-NC —
betrifft jeden Kandidaten, auch TripoSG) und im Bildweg das Freistellmodell:
Alle guten Freisteller lernen aus Forschungsdatensätzen wie DIS5K; einzig
RMBG-2.0 hat eine saubere Datenkette, ist aber nur mit kostenpflichtigem
BRIA-Vertrag gewerblich nutzbar (Entscheidung Robert). Diese Punkte gehören
zur Kanzlei.

## Prüfmaßstab

Ein Kandidat taugt für Solidon, wenn

1. Code **und** Gewichte unter einer Lizenz stehen, die in der EU gilt, keine
   Gebiets-, Umsatz- oder Nutzerschwelle kennt und die gewerbliche Nutzung der
   erzeugten Netze durch Endkunden erlaubt;
2. kein Teil, der im Auftrag läuft, unter einer anderen Lizenz steht
   (Dateiköpfe, `NOTICE`, eingebettete Fremdmodelle);
3. die Laufzeitabhängigkeiten, die der Geometrieweg braucht, ebenfalls frei
   sind — insbesondere nvdiffrast/nvdiffrec (NVIDIA Source Code License, nur
   Forschung und Evaluierung), diff-gaussian-rasterization (Inria, nur
   nicht-kommerziell), kaolin, FlexiCubes, spconv, flash-attn, xformers;
4. es unter Windows ohne Kompilieren eigener CUDA-Erweiterungen läuft und mit
   der GPU-Klasse der Kunden (8 bis 16 GB) auskommt;
5. die Netze für den Druck taugen (geschlossen, Detail).

## Querschnittsbefunde

### Q1 ComfyUI hat den Standard verschoben

Seit dem 22.08.2026 (PR #14718, Autor kijai, in Release v0.34.0 vom
26.08.2026) enthält der ComfyUI-Kern TRELLIS.2 und Pixal3D als eingebaute
Knoten (`comfy/ldm/trellis2/`, `comfy_extras/nodes_trellis2.py`,
`comfy_extras/nodes_mesh_postprocess.py`). Der PR sagt, die gesamte
Nachbearbeitung (DC-Remesh, QEM-Dezimierung, UV-Abwicklung, Textur-Bake) sei in
PyTorch/SciPy neu geschrieben, mit CuMesh und xatlas als Vorlage, Ziel: keinerlei
zusätzliche Abhängigkeiten. Die dünnbesetzte Faltung (`flexgemm.py`) ist eine
Torch-Hashmap über `torch.searchsorted`, keine CUDA-Erweiterung. Am Stand
`7a5dad69` (06.10.2026) importiert keine dieser Dateien nvdiffrast, cumesh,
flex_gemm, o_voxel oder natten. Die Vorlage „Pixal3D & TRELLIS.2: Image to
Model“ ist die offizielle Arbeitsfläche. Ebenfalls im Kern: Hunyuan3D 2.0/2.1
(seit 2025), TripoSplat (seit 01.06.2026, erzeugt Gaussian Splats, kein Netz),
MoGe 2/3, SAM 3, SAM 3D Body.

Die Verbreitung bestätigt das: Laut Hugging-Face-API (06.10.2026, Monatswert)
stehen `microsoft/TRELLIS-image-large` (2,14 Mio.) und
`microsoft/TRELLIS.2-4B` (1,89 Mio.) an der Spitze der Bild-zu-3D-Downloads,
`Comfy-Org/Pixal3D` hat 677 000, `Comfy-Org/TRELLIS.2` 301 000 —
`VAST-AI/TripoSG` 5 800. Unter den „trending“ Bild-zu-3D-Modellen stehen
Stable Fast 3D, TRELLIS.2-4B, Hunyuan3D 2.1, Lyra 2.0 und Pixal3D vorn.

Folge für Solidon: Der eigene Knoten `ComfyUI-TripoSG-Solidon`, der Git-Klon
eines Fremd-Repositorys, die Quelltext-Patches und die ANTLR-/Paketnachzüge
entfallen, wenn der Ersatz ein Kernmodell ist. ComfyUI selbst steht unter
GPL-3.0; Solidon spricht es wie bisher über die HTTP-Schnittstelle an.

### Q2 DINOv3 ist die neue Lizenzfrage

TRELLIS.2 und Pixal3D konditionieren auf DINOv3 ViT-L/16
(`facebook/dinov3-vitl16-pretrain-lvd1689m`, `pipeline.json` von
TRELLIS.2-4B an `af44b45f`). Die Gewichte sind nicht austauschbar — das Modell
ist auf diese Merkmale trainiert.

*DINOv3 License* (Stand 19.08.2025, `LICENSE.md` an Commit `ffb4bb89` von
facebookresearch/dinov3):

- **Gebiet und Zweck:** weltweite, gebührenfreie, nicht ausschließliche Lizenz
  zu Nutzung, Vervielfältigung, Verbreitung, Bearbeitung (§1.a). Keine
  Beschränkung auf Forschung, keine EU-Ausnahme, keine Nutzer- oder
  Umsatzschwelle. Vertragspartner in der EU ist Meta Platforms Ireland.
- **Pflichten:** Weitergabe nur unter dieser Lizenz mit Lizenzkopie (§1.b.i);
  Einhaltung von Gesetzen inkl. Handelskontrollen und Datenschutz (§1.b.iii);
  kein Reverse Engineering (§1.b.iv); keine ITAR-Tätigkeiten und keine
  Endverwendungen für Militär, Nuklear, Spionage oder **„development or use of
  guns or illegal weapons“** (§1.b.v) — für ein Druckprogramm beachtlich.
- **Ausgaben:** keine Regel über Rechte an Ausgaben; Gewährleistungsausschluss
  erfasst ausdrücklich „output and results“ (§3).
- **Sonstiges:** Annahme durch bloße Nutzung; Kündigung bei Verstoß mit
  Löschpflicht (§6); Freistellung Metas bei Ansprüchen Dritter (§5.b); Recht
  Kaliforniens (§7); **Meta darf die Lizenz einseitig ändern, Weiternutzung gilt
  als Zustimmung (§8).**
- **Abruf:** Das Original ist auf Hugging Face zugangsbeschränkt mit
  **manueller** Freigabe (`gated: manual`, 1 212 559 808 Byte, SHA-256
  `dcb2e451…`). Die von ComfyUI verlinkte Kopie
  `Comfy-Org/TRELLIS.2/clip_vision/dino_v3_vit_l.safetensors` (Revision
  `430a9d09`, 1 212 559 776 Byte, SHA-256 `5cb785e4…`) ist frei abrufbar,
  in der Karte als `license: mit` geführt und ohne Lizenzkopie — die Datei ist
  nicht byte-gleich (32 Byte Unterschied, vermutlich neu serialisiert), stammt
  aber erkennbar von DINOv3. Pixal3Ds eigener Code lädt eine weitere
  inoffizielle Kopie (`camenduru/dinov3-vitl16-pretrain-lvd1689m`, `app.py`
  Zeile 76).

### Q3 Trainingsdaten: fast alle Kandidaten teilen dieselbe Rechtekette

Praktisch jedes 3D-Modell der Liste lernt aus Objaverse bzw. Objaverse-XL.
Objaverse steht als Ganzes unter ODC-By 1.0, die einzelnen Objekte unter
CC-BY (721 000), **CC-BY-NC (25 000), CC-BY-NC-SA (52 000)**, CC-BY-SA und CC0
(Datensatzkarte `allenai/objaverse`). Dazu kommen je nach Modell:

| Datensatz | Lizenz laut Herausgeber | Genutzt von (dokumentiert) |
|---|---|---|
| ABO (Amazon Berkeley Objects) | CC BY 4.0 | TRELLIS, TRELLIS.2 |
| HSSD | CC BY-NC 4.0 (Karte `hssd/hssd-hab`) | TRELLIS, TRELLIS.2 |
| 3D-FUTURE | nur wissenschaftliche Forschung, kein Kommerzialisieren (Alibaba-Nutzungsvertrag) | TRELLIS |
| TexVerse | ODC-By (Karte `YiboZhang2001/TexVerse`) | TRELLIS.2 |

TRELLIS.2 nennt für die Generatoren rund 800 000 Assets, erweitert um
TexVerse; die VAEs auf einem gefilterten Trellis-500K aus Objaverse-XL, ABO
und HSSD (arXiv 2512.14692). TRELLIS v1 dokumentiert TRELLIS-500K aus
Objaverse-XL (Sketchfab 168 307, GitHub 311 843), ABO (4 485), 3D-FUTURE
(9 472), HSSD (6 670) (`DATASET.md`). Pixal3D trainiert auf der
TRELLIS-500K-Teilmenge (arXiv 2605.10922). TripoSG lernte ebenfalls aus
Objaverse(-XL). Ob nicht-kommerzielle Bedingungen einzelner Trainingsobjekte
auf Gewichte oder Ausgaben durchschlagen, ist eine Rechtsfrage (Kanzlei, siehe
unten) und **trennt die Kandidaten nicht** — sie betrifft TripoSG genauso.

## Kandidaten im Einzelnen

### K1 TRELLIS.2-4B (Microsoft) — über die nativen ComfyUI-Knoten

**Quellen:** github.com/microsoft/TRELLIS.2 an `75fbf018` (05.06.2026);
huggingface.co/microsoft/TRELLIS.2-4B an `af44b45f` (27.12.2025); ComfyUI-Paket
huggingface.co/Comfy-Org/TRELLIS.2 an `430a9d09` (23.09.2026); ComfyUI an
`7a5dad69` (06.10.2026).

- **Lizenz Code:** MIT, Copyright Microsoft (`LICENSE`). Keine `NOTICE`, keine
  fremden Lizenzköpfe im Baum (Suche nach Tencent, Hunyuan, NVIDIA,
  Non-Commercial, Inria, GPL ohne Treffer). Das README nennt nvdiffrast und
  nvdiffrec ausdrücklich als Abhängigkeiten unter eigener Lizenz.
- **Lizenz Gewichte:** MIT laut Karte, nicht zugangsbeschränkt. Das
  Strukturdekoder-Gewicht kommt aus `microsoft/TRELLIS-image-large` (MIT).
- **Fremdmodelle im Originalweg:** DINOv3 ViT-L/16 (Q2) und als Freisteller
  `briaai/RMBG-2.0` — **CC BY-NC 4.0, zugangsbeschränkt** (`pipeline.json`).
  Den Freisteller wählt Solidon selbst (Abschnitt Vorstufen); im ComfyUI-Weg
  ist es BiRefNet.
- **Abhängigkeiten im Originalweg:** flash-attn, nvdiffrast v0.4.0 und
  nvdiffrec (NVIDIA, nur Forschung), CuMesh (MIT), FlexGEMM (MIT), o-voxel
  (im Repo, MIT), utils3d (MIT) — alle als CUDA-Erweiterung zu kompilieren,
  getestet nur unter Linux mit ≥ 24 GB (README). nvdiffrast wird im Code nur
  beim Textur-Bake (`o_voxel/postprocess.py`) und in Renderern importiert, der
  Formweg (`representations/mesh/base.py`) braucht cumesh.
- **Im ComfyUI-Kern:** keine dieser Erweiterungen (Q1). Formweg:
  `CLIPVisionLoader` (DINOv3) → `Trellis2Conditioning` →
  `EmptyTrellis2LatentStructure` → `KSampler` → `VaeDecodeStructureTrellis2` →
  `Trellis2ShapeStage` → `KSampler` → `Trellis2UpsampleStage` → `KSampler` →
  `VaeDecodeShapeTrellis` (gibt `MESH`) → optional `RemeshMesh`/`DecimateMesh`
  → `MeshToFile3D`/`Save3DAdvanced`. Die Texturstufe wird für Solidon nicht
  gebraucht.
- **VRAM/Laufzeit:** Original: H100, 512³ ≈ 3 s, 1024³ ≈ 17 s, 1536³ ≈ 60 s
  (Karte); mindestens 24 GB. ComfyUI: DiT als `int8_convrot` 5,25 GB statt
  10,3 GB bf16; PR #16054 senkt Spitzen-VRAM/RAM, ohne Zahlen. Ein
  Erfahrungsbericht (InstaSD, Drittquelle) nennt 16 GB als praktikabel bei
  32³-Detailgitter, 24 GB für 64³/1536. **8 und 12 GB sind nicht belegt.**
- **Plattformen:** Windows/Linux NVIDIA ohne Kompilieren (Kern-PyTorch).
  AMD/ROCm: offene Fehler bei der UV-Abwicklung (#16124), die Solidon nicht
  braucht. macOS/MPS: `Conv3d` lieferte unter macOS 26.2 eine leere Struktur
  (#16340, geschlossen — mit macOS 26.7 behoben laut Melder); `RemeshMesh` und
  `DecimateMesh` scheitern auf MPS bei 3–8 Mio. Elementen (#16017, offen; auf
  CPU korrekt). Laut #16340 dauert der Formweg auf MPS rund 12 Minuten.
- **Qualität (belegt):** TRELLIS.2-Paper Tabelle 2: höchste Werte in CLIP,
  ULIP-2, Uni3D gegen TRELLIS, Hi3DGen, Direct3D-S2, Step1X-3D, Hunyuan3D 2.1;
  66,5 % Präferenz in der Nutzerstudie. **Kein direkter Vergleich mit
  TripoSG.** Die Karte warnt: Rohnetze können kleine Löcher haben; für
  wasserdichte Geometrie (ausdrücklich 3D-Druck) braucht es Nachbearbeitung.
  Offener ComfyUI-Fehler #16147 (06.09.2026, unbestätigt): Netze aus dem
  nativen Weg hätten einen inneren Hohlraum (Doppelschale), Slicer füllten sie
  nicht. Die Vorlage führt das Netz durch `RemeshMesh` im Modus `udf`, und
  dessen eigener Tooltip nennt „the UDF inner shell“; die Optionen
  `drop_inverted_components`/`drop_enclosed_components` stehen in der Vorlage
  auf aus — das ist sehr wahrscheinlich die Ursache (nicht nachgestellt). Die
  O-Voxel-Darstellung ist ausdrücklich „field-free“ und erlaubt offene
  Flächen — anders als TripoSGs Belegungsfeld, das immer geschlossene Flächen
  liefert. **Für Solidon heißt das: Das Rohnetz muss vor der Reparatur
  zum Volumenkörper geschlossen werden** (Innenhülle entfernen, Löcher
  schließen); das ist Solidons eigene Aufgabe, keine Lizenzfrage.

### K2 Pixal3D (Tencent ARC / Tsinghua) — über dieselben ComfyUI-Knoten

**Quellen:** github.com/TencentARC/Pixal3D an `f7cf3842` (01.09.2026);
huggingface.co/TencentARC/Pixal3D an `b0cb2e1b` (31.08.2026);
huggingface.co/Comfy-Org/Pixal3D an `f37641be` (23.09.2026).

- **Lizenz Code und Gewichte:** MIT, Copyright 2026 Tencent (`LICENSE` im
  GitHub-Repo und auf Hugging Face). `NOTICE` nennt DINOv2 (Apache-2.0),
  TRELLIS.2, Direct3D-S2 und MoGe (je MIT) und eine „Responsible Use“-Passage,
  die ausdrücklich nicht in die Lizenz eingreift (seit `28efad66`,
  24.05.2026).
- **Lizenzwechsel:** Bis Commit `5098ba1f` (GitHub, 20.05.2026) bzw.
  `b648b3c5` (Hugging Face, 20.05.2026) galt die „License Term of Pixal3D“:
  nur akademische Zwecke, keine kommerzielle oder produktive Nutzung, und
  „NOT INTENDED FOR USE WITHIN THE EUROPEAN UNION“ mit Vorrangklausel. Auf
  Hugging Face: Gewichte hochgeladen am 30.04.2026 ohne Lizenzdatei, die
  restriktive Lizenz kam am 12.05.2026 (`60f4ffb2`), MIT am 20.05.2026
  (`b648b3c5`). Die heutigen Einzelbild-Gewichte (`ckpts/*` ohne `_mv`) sind
  laut Baum-API unverändert die vom 30.04.2026; nur die Mehrbild-Gewichte
  kamen am 31.08.2026 unter MIT dazu. **Dieselben Dateien standen also acht
  Tage unter der EU-Ausschlussklausel und wurden dann umlizenziert**
  (Kanzleifrage: Wirkung und Widerruflichkeit des Wechsels).
- **Fremdmodelle:** DINOv3 (Q2; Code lädt `camenduru/…`-Kopie, ComfyUI nutzt
  `dino_v3_L_naf_fp32` = DINOv3 + NAF-Upsampler, NAF laut Kopfzeile in
  `comfy/image_encoders/naf.py` aus valeoai/NAF unter Apache-2.0), MoGe-2
  (`Ruicheng/moge-2-vitl-normal` an `cb0e8bbd`, MIT, Basis DINOv2 Apache-2.0)
  für die Kameraschätzung. `NOTICE` nennt DINOv2, obwohl der Code DINOv3
  lädt — Ungereimtheit an der Quelle.
- **Abhängigkeiten Originalweg:** wie TRELLIS.2, dazu natten 0.21.0 (aus der
  Quelle zu bauen) und ein utils3d-Rad von einem privaten GitHub-Release.
  Im ComfyUI-Kern: keine (NAF in reinem PyTorch nachgebaut).
- **VRAM/Laufzeit:** Das Pixal3D-README nennt nur einen Low-VRAM-Modus
  (1024³ statt 1536³), keine Zahl. Drittquellen: ≥ 16 GB, 24 GB empfohlen,
  3–5 Minuten auf RTX 5090 (`dreamrec/ComfyUI-Pixal3D`, Stand 14.05.2026 —
  dessen Lizenzwarnung „Academic / No-EU“ ist durch den Wechsel vom
  20.05.2026 überholt); Low-VRAM-Spitze ≈ 13 GB (`hoodtronik/Pixal3D-Pinokio`).
  ComfyUI-Kern: DiT `int8_convrot` 5,58 GB. Offene Kernfehler: bf16-Gewichte
  stürzen ab (#16056), Mehrbildweg hält 3 GiB je Ansicht im RAM (#16620).
- **Qualität (belegt):** Paper Tabelle 1, Toys4K Einzelbild: IoU 93,57 gegen
  **73,54 für TripoSG**, PSNR 24,21 gegen 19,73, LPIPS 0,108 gegen 0,250; dazu
  TRELLIS, Hunyuan3D 2.1, Direct3D-S2 als Gegner; mittlerer Normalenfehler
  16,6° gegen 28,6° (TripoSG). IoU und PSNR messen die Übereinstimmung mit der
  Eingabeansicht, also genau das, worauf Pixal3D gebaut ist. Nutzerstudie
  (Tabelle 2): Qualität 4,74 gegen 2,14 (TripoSG). Diese Zahlen gelten für den
  `paper`-Zweig (Direct3D-S2-Basis), nicht für die heutige TRELLIS.2-Basis.
  Netzeigenschaften wie TRELLIS.2 (#16147 betrifft beide).
- **Bewertung:** gleiche Laufzeitkette wie K1, bessere Bildtreue, aber
  zusätzlich MoGe-2 (≈ 0,66 GB) und die Lizenzgeschichte. Als Option neben
  TRELLIS.2 im selben Knotensatz ohne Mehraufwand anbietbar.

### K1a trellis.cpp — zweite Laufzeit für TRELLIS.2 und Pixal3D

**Quelle:** github.com/pwilkin/trellis.cpp an `c0bed38c` (25.09.2026),
Release v0.8.1 (25.09.2026).

- **Lizenz:** MIT (Piotr Wilkin); Drittanteile fqms, meshoptimizer, stb, xatlas
  mit eigenen freien Lizenzdateien.
- **Was es ist:** TRELLIS.2-4B (und Pixal3D) in C++/GGML ohne Python, mit
  fertigen Programmen für Windows und Linux (CUDA, ROCm, **Vulkan**) und
  HTTP-Server. Gewichte als GGUF (`ilintar/trellis2-gguf`, Lizenzfeld
  „other“). Laut README läuft die 1024er-Kaskade auf 16-GB-Karten; Apple M5
  (Metal) bei Auflösung 512 in 9:21 Minuten mit 5,6 GB Spitzen-RSS.
  RTX 5060 Ti, Auflösung 1024: 3:16 bis 7:23 Minuten inkl. Laden.
- **Fremdmodelle:** DINOv3 aus `timm/vit_large_patch16_dinov3.lvd1689m` — eine
  **frei abrufbare Kopie mit beigelegter `LICENSE.md`** (7 503 Byte, wie das
  Original) und korrekt als `dinov3-license` ausgewiesen; BiRefNet als
  Freisteller.
- **Bewertung:** Für Solidon interessant als Weg ohne ComfyUI und für
  AMD/Intel-Karten über Vulkan. Ein Ein-Personen-Projekt; die GGUF-Gewichte
  sind Umwandlungen Dritter. Kein Ersatz für den ComfyUI-Weg, aber eine
  Rückfallebene.

### K3 TRELLIS v1 (`microsoft/TRELLIS-image-large`)

**Quellen:** github.com/microsoft/TRELLIS an `442aa1e1` (05.11.2025);
huggingface.co/microsoft/TRELLIS-image-large an `25e0d31f` (06.12.2024).

- **Lizenz:** Code MIT (Microsoft), Gewichte MIT, nicht zugangsbeschränkt.
  Das README nennt drei Untermodule mit eigener Lizenz: diffoctreerast (von
  Inria-diff-gaussian-rasterization abgeleitet), mip-splatting und die
  modifizierte FlexiCubes. FlexiCubes (Untermodul `MaxtirError/FlexiCubes`,
  Fork von `nv-tlabs/FlexiCubes`) steht laut GitHub-API unter **Apache-2.0** —
  die Formextraktion ist damit frei. kaolin bietet `setup.sh` an, im
  Python-Code des Repositorys wird es nirgends importiert.
- **Fremdmodelle:** DINOv2 ViT-L/14-reg über `torch.hub`
  (facebookresearch/dinov2, **Apache-2.0**) — saubererer Bildkodierer als
  DINOv3. Freisteller im Originalweg: rembg mit `u2net`.
- **Formweg ohne Problemabhängigkeiten:** `pipeline.run(..., formats=["mesh"])`
  dekodiert über `cube2mesh.py` → FlexiCubes; nvdiffrast, pymeshfix und
  pyvista braucht nur `postprocessing_utils.to_glb` (Textur-Bake und
  Lochfüllung über Sichtbarkeitsrendering), den Inria-Rasterisierer nur der
  Gaussian-Dekoder. **pymeshfix steht in Version 0.18.1 unter AGPL-3.0**
  (PyPI-Klassifikation) — ein weiterer Grund, `to_glb` zu meiden.
- **Laufzeit-Abhängigkeiten:** spconv (Apache-2.0, `spconv-cu121` 2.3.8 mit
  Windows-Rad) oder torchsparse; Aufmerksamkeit über xformers
  (Windows-Räder auf PyPI) oder flash-attn — der dünnbesetzte Teil kennt
  **kein** `sdpa`. utils3d (MIT). Offiziell nur Linux, ≥ 16 GB (README),
  Windows „nicht vollständig getestet“.
- **ComfyUI:** nicht im Kern. Knotenpakete: `MrForExample/ComfyUI-3D-Pack`
  (MIT, 3 881 Sterne, zuletzt 29.12.2025), `if-ai/ComfyUI-IF_Trellis` (MIT,
  zuletzt 09.03.2025), `smthemex/ComfyUI_TRELLIS` (MIT, zuletzt 17.08.2025).
  Alle brauchen spconv/xformers im ComfyUI-Python.
- **Qualität:** in TRELLIS.2-Tabelle 2 klar hinter TRELLIS.2 (Uni3D 0,414
  gegen 0,436; Nutzerpräferenz 6,4 % gegen 66,5 %). **Gegen TripoSG**
  (Pixal3D-Tabelle 1, Toys4K): IoU 79,48 gegen 73,54, LPIPS 0,204 gegen
  0,250, mittlerer Normalenfehler 25,0° gegen 28,6° — also mindestens
  gleichwertig; in der Nutzerstudie (Tabelle 2) Qualität 1,99 gegen 2,14.
  FlexiCubes liefert geschlossene Flächen aus einem SDF-artigen Feld,
  Auflösung 256³.
- **Trainingsdaten:** TRELLIS-500K inkl. 3D-FUTURE (nur Forschung) und HSSD
  (CC BY-NC) — siehe Q3.
- **Bewertung:** saubere Lizenzkette ohne DINOv3, aber eigener Knoten mit
  spconv/xformers, ältere Qualität und kein Kernweg mehr. Rückfalloption, wenn
  die Kanzlei DINOv3 ablehnt.

### K4 TripoSR (Stability AI und Tripo AI)

**Quellen:** github.com/VAST-AI-Research/TripoSR an `107cefdc` (04.06.2026,
README-Änderung); huggingface.co/stabilityai/TripoSR an `5b521936`
(09.08.2024).

- **Lizenz:** Code und Gewichte MIT (Copyright Tripo AI & Stability AI). Die
  Karte trägt Abfragefelder, ist aber nicht zugangsbeschränkt
  (`gated: false`). `model.ckpt` 1,68 GB, SHA-256 `429e2c6b…`.
- **Fremdmodelle:** `facebook/dino-vitb16` (Apache-2.0). Keine fremden
  Lizenzköpfe im Baum.
- **Trainingsdaten:** laut Karte eine kuratierte Objaverse-Teilmenge **unter
  CC-BY** — die einzige Karte der Liste, die NC-Objekte ausdrücklich
  ausschließt.
- **Abhängigkeiten:** torchmcubes (MPL-2.0, muss mit CUDA kompiliert werden,
  sonst CPU-Rückfall laut README), rembg, xatlas, moderngl. Marching Cubes
  ginge auch über scikit-image.
- **Technik:** ≈ 6 GB VRAM, < 0,5 s auf A100 (README); läuft auch auf CPU.
  ONNX-Portierungen existieren (z. B. `brodatech/triposr-onnx`, MIT).
  ComfyUI-Knoten `flowtyone/ComfyUI-Flowty-TripoSR` (**GPL-3.0**, zuletzt
  16.06.2024).
- **Qualität:** LRM-Triplane-NeRF von 2024, Marching Cubes auf einem
  Dichtegitter → geschlossene, aber glatte und detailarme Netze. Kein
  direkter Vergleich mit TripoSG an der Quelle geprüft.
- **Bewertung:** lizenzrechtlich der sauberste Kandidat, technisch für
  8-GB-Karten und CPU geeignet, aber qualitativ eine Generation zurück. Nur
  als Kleinkarten-Notweg sinnvoll.

### K5 Hi3DGen (Stable-X / ByteDance)

**Quellen:** github.com/Stable-X/Hi3DGen an `c29f668e` (02.07.2025);
huggingface.co/Stable-X/trellis-normal-v0-1 an `fdfac1d0` (26.03.2025),
huggingface.co/Stable-X/yoso-normal-v1-8-1 an `4dd7d000` (20.01.2025).

- **Lizenz:** Code MIT (Copyright 2025 Bytedance Inc.), Gewichte
  `trellis-normal-v0-1` MIT, Normalenschätzer `yoso-normal-v1-8-1`
  Apache-2.0, StableNormal-Code Apache-2.0. Das README sagt, man habe kaolin,
  nvdiffrast und FlexiCubes entfernt, damit die Fassung gewerblich nutzbar
  sei.
- **Weg:** Bild → Normalenkarte (StableNormal/YOSO, Diffusers-UNet mit
  ControlNet, ≈ 2,6 GB) → TRELLIS-artiger Normalen-zu-Geometrie-Generator
  (DINOv2, Apache-2.0) → Marching Cubes über scikit-image. Freisteller:
  BiRefNet.
- **Abhängigkeiten:** spconv + xformers (wie K3), triton, diffusers.
- **Trainingsdaten:** 170 000 Objaverse-1.0-Objekte plus **DetailVerse**:
  700 000 synthetische Objekte, erzeugt mit **FLUX.1-dev** (Bild) und
  **TRELLIS** (3D) (arXiv 2503.22236). FLUX.1-dev steht unter einer
  nicht-kommerziellen Lizenz — ob deren Bedingungen für Ausgaben, die als
  Trainingsdaten dienten, auf Hi3DGen durchschlagen, ist eine Kanzleifrage.
- **Qualität:** in TRELLIS.2-Tabelle 2 hinter TRELLIS.2 (Uni3D 0,373); im
  eigenen Papier nur Nutzerstudie und qualitative Vergleiche, keine
  3D-Kennzahlen gegen TripoSG.
- **ComfyUI:** kein Kern, kein verbreiteter Knoten gefunden.
- **Bewertung:** eigener Knoten, zusätzliche Rechtekettenfrage
  (FLUX-dev-Daten), keine 3D-Kennzahlen.

### K6 Direct3D-S2 (DreamTech)

**Quellen:** github.com/DreamTechAI/Direct3D-S2 an `a1cf235b` (26.09.2025);
huggingface.co/wushuang98/Direct3D-S2 an `8b04a8ed` (14.06.2025).

- **Lizenz:** Code MIT (DreamTechAI), Gewichte MIT, keine fremden Köpfe.
- **Fremdmodelle:** DINOv2 ViT-L/14-reg (Apache-2.0).
- **Abhängigkeiten:** torchsparse (MIT, **aus der Quelle zu bauen**),
  flash-attn, triton 3.1.0, **pymeshfix (AGPL-3.0)** für die Lochfüllung,
  utils3d, pyvista, igraph. Windows nur über Hinweise in Issues #11/#12.
- **Technik:** 512³ ≥ 10 GB, 1024³ ≈ 24 GB (README). Gewichte v1.1 ≈ 4,2 GB.
- **Qualität:** SDF-basiert, geschlossene Flächen. In TRELLIS.2-Tabelle 2
  hinter TRELLIS.2 (Uni3D 0,392), in Pixal3D-Tabelle 1 Gegner.
- **ComfyUI:** `Yuan-ManX/ComfyUI-Direct3D-S2` (MIT, 17 Sterne).
- **Bewertung:** lizenzrechtlich sauber, technisch Bauaufwand (torchsparse)
  und 24 GB für die gute Stufe; überholt durch K1/K2.

### K7 Step1X-3D (StepFun)

**Quellen:** github.com/stepfun-ai/Step1X-3D an `cb5ac944` (09.09.2025);
huggingface.co/stepfun-ai/Step1X-3D an `bf708449` (13.05.2025).

- **Lizenz laut Repo und Karte:** Apache-2.0.
- **Aber:** `step1x3d_geometry/models/autoencoders/volume_decoders.py` beginnt
  mit „Hunyuan 3D is licensed under the TENCENT HUNYUAN NON-COMMERCIAL LICENSE
  AGREEMENT“ und verweist im selben Kopf auf die Community License. Die Datei
  liefert `VanillaVolumeDecoder` und `HierarchicalVolumeDecoder`, die
  `michelangelo_autoencoder.py` in jedem Formauftrag importiert — **dasselbe
  Muster wie bei TripoSG.** Inhaltlich eine Gitterauswertung (dichte
  Abfragepunkte → Logits), also ersetzbar; der DiT
  (`flux_transformer_1d.py`) stammt aus Diffusers (Apache-2.0).
- **Weitere Punkte:** Freisteller-Voreinstellung rembg mit Modell `bria`
  (RMBG, nicht-kommerziell); Textur-Teil mit Hunyuan3D-2-Rasterisierer
  (Tencent-Köpfe) und nvdiffrast — für Solidon nicht nötig.
- **Technik:** Formgewichte 7,3 GB; Form + Textur 27 GB VRAM, 152 s für
  50 Schritte (README); Form allein nicht belegt.
- **Trainingsdaten:** 2 Mio. Objekte, davon 320 000 Objaverse, 480 000
  Objaverse-XL, Rest selbst gesammelt (README).
- **ComfyUI:** `Yuan-ManX/ComfyUI-Step1X-3D` (MIT, 14 Sterne).
- **Bewertung:** ausgeschlossen in dieser Form — Tencent-NC-Kopf im Formweg.

### K8 Auf TripoSG aufgebaute Modelle — gleiche Kette

PartCrafter (`wgsxm/PartCrafter` an `3d773bf0`, Repo-Lizenz MIT, aber
`src/models/transformers/partcrafter_transformer.py` trägt den vollständigen
Tencent-Hunyuan-Community-Lizenzkopf), DetailGen3D und HoloPart
(VAST-AI-Research, je `triposg_transformer.py` mit Hunyuan-Kopf und
TripoSG-`NOTICE`), MIDI-3D (`midi/models/transformers/triposg_transformer.py`
laut GitHub-Codesuche). **Ausgeschlossen aus demselben Grund wie TripoSG.**

### K9 Geprüft und ausgeschlossen

| Modell | Ausschlussgrund (Beleg) |
|---|---|
| Hunyuan3D 2.0 / 2mini / 2mv / 2.1 / Omni / Part (Tencent) | Tencent Hunyuan 3D Community License: „DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA“ (`LICENSE` von Hunyuan3D-2.1 und Omni); alle HF-Repos zuletzt am 17.10.2025 geändert, **keine Lizenzänderung**. Auch die ComfyUI-Kernknoten ändern daran nichts (`Comfy-Org/hunyuan3D_2.1_repackaged` führt dieselbe Lizenz). |
| Hunyuan3D 2.5 / 3.0 / LATTICE (Tencent Hunyuan, CUHK) | Keine offenen Gewichte belegt. LATTICE ist laut Projektseite „the foundation model behind Hunyuan3D 2.5 and 3.0“; `github.com/zeqiang-lai/lattice` liefert 404. |
| UltraShape 1.0 (PKU-Yuan-Group) | Karte `infinith/UltraShape` sagt Apache-2.0, das Repository `PKU-YuanGroup/UltraShape-1.0` an `5e8dcef0` trägt aber als `LICENSE` die **Tencent Hunyuan 3D 2.1 Community License** (EU ausgenommen) und braucht Hunyuan3D-2.1 für das Grobnetz (README, Basis `tencent/Hunyuan3D-2.1`). |
| Sparc3D / Hitem3D | Kein Code und keine Gewichte: `lizhihao6/Sparc3D` an `dbcf176e` enthält nur README und Bilder; Hitem3D ist ein Bezahldienst. `ben-kaye/Sparc3Dsdf` (BSD-3) ist eine Nachbildung der SDF-Darstellung, kein Generator. |
| SAM 3D Objects (Meta) | SAM License vom 19.11.2025 (Vorlage wie DINOv3, zusätzlich Patentlizenz) wäre tragbar, aber: Gewichte `gated: manual`, Einrichtung laut `doc/setup.md` nur Linux mit **≥ 32 GB VRAM**, Abhängigkeiten kaolin, pytorch3d, gsplat, spconv, **bpy (GPL)**, **pymeshfix (AGPL)**; Ziel ist Rekonstruktion von Objekten in Szenenfotos (Gaussians/Netz), nicht Druckteile. |
| Cube 3D v0.1/v0.5 und CubePart (Roblox) | `LICENSE` an `3c6d06dd`: „CUBE3D RESEARCH-ONLY RAIL-MS LICENSE“, Zweck nur akademisch/Forschung; CubePart-README verweist auf dieselbe Lizenz (HF-Karte „openrail“ ist irreführend). |
| Arbor (Stability AI, 2026, Text→3D mit Formvorgaben) | Stability-Community-Lizenz: ab 1 Mio. US-$ Jahresumsatz Unternehmenslizenz nötig (Karte `StabilityLabs/arbor`) — Umsatzschwelle für Kunden. Baut auf TRELLIS-Text-Modellen auf. |
| SPAR3D, Stable Fast 3D (Stability AI) | Stability AI Community License (Umsatzschwelle 1 Mio. US-$), `gated: auto`; SF3D am 31.08.2026 schon verworfen, keine neue Faktenlage. |
| InstantMesh (Tencent ARC) | Code und eigene Gewichte Apache-2.0, aber die Mehransichtsstufe Zero123++ v1.2 hat Gewichte unter **CC-BY-NC 4.0** (README von SUDO-AI-3D/zero123plus), und `lrm_mesh.py` importiert nvdiffrast auf Modulebene. |
| CRM (Tsinghua) | MIT, aber nvdiffrast im Inferenzweg (`inference.py`, `model/crm/model.py`), pymeshlab (GPL-3.0). |
| LGM (3DTopia) | MIT, aber erzeugt Gaussians; braucht diff-gaussian-rasterization (Inria, nicht-kommerziell) und für Netze nvdiffrast; Mehransichten über ImageDream/MVDream (OpenRAIL). |
| CraftsMan3D (HKUST) | Kein Lizenztext im Repository (`wyysf-98/CraftsMan` an `f87d6a54`, GitHub-API: keine Lizenz); Code laut README „heavily build on“ Michelangelo (GPL-3.0); HF-Gewichte CreativeML OpenRAIL-M. |
| Michelangelo (2023) | Code GPL-3.0, Gewichte LGPL-3.0, Stand Anfang 2024; qualitativ überholt. |
| TripoSF (VAST) | MIT, aber nur der Rekonstruktions-VAE (README: „Pretrained VAE model weights (1024³ reconstruction)“), kein Bild-zu-3D-Generator. |
| TripoSplat (Tripo, 2026, im ComfyUI-Kern) | MIT, erzeugt aber Gaussian Splats, kein Netz. |
| Large Sparse Reconstruction Model (Meta, 2026) | CC-BY-NC-4.0, `gated: manual`. |
| CLAY / Rodin Gen-1 (Deemos/Hyper3D), Seed3D 1.0 (ByteDance) | Keine offenen Generatorgewichte auf Hugging Face gefunden (Suche nach Rodin, Deemos, Hyper3D, CLAY, Seed3D); von Seed3D gibt es nur Dora-VAE (Apache-2.0) und Rigging-Modelle. **Unbelegt, dass es offene Gewichte gibt.** |
| Shap-E (OpenAI) | am 31.08.2026 verworfen, keine neue Faktenlage. |

Gesichtet, aber nicht einschlägig (Szenen, Bewegung, Topologie, Bearbeitung
oder Quantisierungen anderer Modelle): Lyra 2.0 und asset-harvester (NVIDIA),
HY-World 2.0 (Tencent), Fire3D (Szenen, 67 GB), AniGen (VAST, animierbare
Assets auf TRELLIS-Basis, MIT), TriFlow (eigene Lizenz „adpncl-1.0“),
Alchemy3D (Bearbeitung), UniMate (Bewegung), VoxelModel-v1 (Klein-Voxel),
LocalMeshEngine (Quantisierung von Pixal3D).

## Vorstufen des Textwegs

### V1 Bildmodell (heute SDXL Base 1.0)

SDXL bleibt zulässig: CreativeML Open RAIL++-M erlaubt gewerbliche Nutzung
weltweit, verlangt aber die Weitergabe der Nutzungsbeschränkungen aus Anhang A,
und die Karte nennt als vorgesehene Verwendung allein die Forschung
(`lizenzkette.md`, 2.6). Kandidaten mit klarerer Lizenz, alle mit
ComfyUI-Kernunterstützung:

| Modell | Lizenz (Beleg) | Textkodierer | VRAM laut Quelle | Dateien (Comfy-Org) | Bewertung |
|---|---|---|---|---|---|
| **FLUX.2 [klein] 4B** (Black Forest Labs, Freiburg, 14.01.2026) | Apache-2.0 (`LICENSE.md` im Repo an `e7b7dc27`, nicht zugangsbeschränkt); Karte: „Open weights available for commercial use“, die Ausschlussliste ändert die Lizenz ausdrücklich nicht; dokumentierte Filterung von CSAM/NCII in Vor- und Nachtraining | Qwen3-4B (Apache-2.0) | „~13GB VRAM“, RTX 3090/4070 (Karte, bf16); 4 Schritte | offizielle fp8-Fassung `black-forest-labs/FLUX.2-klein-4b-fp8` (4,07 GB, Apache-2.0); `Comfy-Org/vae-text-encorder-for-flux-klein-4b` an `5f526678`: `qwen_3_4b_fp4_flux2` 3,85 GB, `flux2-vae` 0,34 GB | **Empfehlung.** Kleinster Gesamtbedarf (≈ 8,3 GB), Hersteller mit Sitz in der EU, fp8 direkt vom Hersteller statt aus einer Umpackung. **Achtung:** Die 9B-Fassung und FLUX.2 [dev] stehen unter der FLUX-Non-Commercial-Lizenz. |
| **Z-Image-Turbo** (Alibaba Tongyi, 25.11.2025) | Apache-2.0 (Karte `Tongyi-MAI/Z-Image-Turbo` an `f332072a`, nicht zugangsbeschränkt) | Qwen3-4B (Apache-2.0) | „fits comfortably within 16G VRAM“ (Karte); 8 Schritte | `Comfy-Org/z_image_turbo` an `6fc90a3b`: DiT `z_image_turbo_int8_convrot` 6,20 GB (bf16 12,31 GB), `qwen_3_4b_fp8_mixed` 5,63 GB (fp4 3,48 GB), VAE `ae.safetensors` 0,34 GB | Gleichwertige Alternative. Die VAE ist byte-gleich mit der von FLUX.1 [schnell] (SHA-256 `afc8e282…` bzw. `f5b59a26…` in Diffusers-Form), dort Apache-2.0. |
| FLUX.1 [schnell] | Apache-2.0, aber `gated: auto` | T5-XXL + CLIP-L | 12B, schwer | — | überholt durch FLUX.2 [klein] 4B |
| Qwen-Image / -2512 | Apache-2.0 | Qwen2.5-VL-7B | 20B | 57,7 GB | zu schwer; **Qwen-Image-2.1 steht unter „qwen-research“** |
| ERNIE-Image (Baidu, 04/2026) | Apache-2.0 | eigener | 24 GB (Karte) | 31,6 GB | zu schwer |
| HiDream-O1-Image | MIT (Comfy-Org) | nicht geprüft | fp8 8,1 GB | — | Textkodierer-Lizenz offen |
| Lumina-Image 2.0, Sana | Apache-2.0 | Gemma 2 (Gemma-Nutzungsbedingungen) | — | — | eigene Gemma-Bedingungen |
| Mage-Flow (Microsoft, 07/2026) | MIT laut Spiegeln | Qwen3-VL-4B | — | — | Original `microsoft/Mage-Flow` nicht mehr abrufbar (HF 401, GitHub 404) — **unbelegt** |
| SD 3.5, Krea 2, MiniMax-H3 | Stability Community (Umsatzschwelle), Krea-2-Community-, MiniMax-H3-Community-Lizenz | — | — | — | Schwellen bzw. Sonderlizenz |
| Ideogram 4, PixelDiT, FLUX.1 [dev] | nicht-kommerziell (Ideogram NC, NVIDIA NSCL, FLUX NC) | — | — | — | ausgeschlossen |
| HunyuanImage 2.1/3.0 | Tencent Community (EU ausgenommen) | — | — | — | ausgeschlossen |
| Kolors | Karte Apache-2.0, Gewichte aber unter eigener chinesischer `MODEL_LICENSE` | — | — | — | widersprüchlich, ausgeschlossen |

Qualitätsvergleich für den Zweck „ein freigestelltes Objekt auf weißem Grund“:
**nicht gemessen**; die Karten enthalten nur Herstellerangaben.

### V2 Freistellen (heute BiRefNet über `Comfy-Org/BiRefNet`)

Kernbefund: **Es gibt kein gutes Freistellmodell, dessen Trainingsdaten
ausdrücklich gewerblich freigegeben sind und dessen Gewichte zugleich frei
sind.** Die gängigen Datensätze (DIS5K, DUTS, HRSOD, UHRSD, P3M, COD10K) sind
Forschungsdatensätze; die DIS5K-Bedingungen verbieten die kommerzielle Nutzung
ausdrücklich (`lizenzkette.md`, 2.5). Der ComfyUI-Kern lädt nur
BiRefNet-Architektur (`comfy/bg_removal_model.py`), austauschbar sind also nur
Gewichte dieser Bauart.

| Modell | Gewichte | Trainingsdaten (dokumentiert) | Kern | Bewertung |
|---|---|---|---|---|
| BiRefNet (heute) | MIT | DIS5K-TR u. a. Forschungsdatensätze | ja | Status quo, Kanzleifrage DIS5K |
| lucida (`egeorcun/lucida` an `6cbedc97`, von Comfy-Org mitgeliefert) | MIT | Feinabstimmung von BiRefNet_HR; Karte nennt P3M-10k, COD10K, DIS5K „for research purposes“ und ToonOut (CC-BY 4.0) | ja | gleiche Frage wie BiRefNet |
| ToonOut | MIT | BiRefNet-Feinabstimmung auf 1 228 Bildern CC-BY 4.0 (Anime) | ja (Bauart) | Basis bleibt BiRefNet |
| **RMBG-2.0 (BRIA)** | **CC BY-NC 4.0**, `gated: auto` mit Formular | laut BRIA über 15 000 manuell maskierte, **vollständig lizenzierte** Bilder | Bauart BiRefNet, Ladbarkeit im Kern **nicht geprüft** | einziger Kandidat mit sauberer Datenkette, **gewerblich nur mit kostenpflichtigem Vertrag** — Entscheidung Robert (Geld) |
| RMBG-1.4 | bria-rmbg-1.4, nicht-kommerziell | — | nein | ausgeschlossen |
| BEN2 (Prama) | MIT (Basismodell) | DIS5K + 22 000 eigene Bilder (Karte) | nein | gleiche DIS5K-Frage |
| InSPyReNet / transparent-background | MIT | je Prüfpunkt DUTS-TR, HRSOD, UHRSD oder DIS5K (Model Zoo) | nein | DUTS-Bedingungen nicht belegt |
| withoutBG Open Weights 10.8.0 | Apache-2.0 + **DINOv3 License** + MIT (BiRefNet-Zweig) | eigener Matting-Zweig „trained and maintained by withoutBG“ | nein (ONNX) | mischt dieselben Fragen |
| SAM 2.1 | Apache-2.0 | SA-1B/SA-V (Bedingungen nicht geprüft) | nein | braucht Klick- oder Kastenvorgabe |
| SAM 3 / 3.1 | SAM License (Vorlage wie DINOv3), Original `gated: manual` | eigene Daten-Engine (SA-Co) | **ja** (`nodes_sam3.py`, `Comfy-Org/sam3.1`) | Segmentierung per Text („the object“); gleiche Lizenzfamilie wie DINOv3 |

**Empfehlung für den Textweg:** Solidon erzeugt das Bild selbst und
verlangt im Prompt schon heute einen schlichten weißen Hintergrund
(`text_to_mesh.json`, Knoten 2). Dann reicht ein eigener, deterministischer
Freisteller ohne Modell (Flutfüllung vom Rand mit Farbtoleranz,
morphologisches Schließen, größte Komponente) — keine Lizenz, keine Gewichte.
Grenze laut trellis.cpp-README: Ein reiner Weiß-Keyer schneidet Glanzlichter
aus, und der Generator erzeugt dort Löcher; deshalb Rückfall auf BiRefNet,
wenn die Maske unplausibel ist (z. B. Objekt berührt den Rand, Fläche < 5 %).
Das ist ein Vorschlag, **nicht gemessen**.

Generatoren, die gleich ein Bild mit Alphakanal liefern, wären die andere
Lösung: LayerDiffuse (Code Apache-2.0, Gewichte `LayerDiffusion/layerdiffusion-v1`
CreativeML OpenRAIL-M, Knoten `huchenlei/ComfyUI-layerdiffuse` Apache-2.0,
zuletzt 25.02.2025) funktioniert nur mit SDXL/SD 1.5; Qwen-Image-Layered
(Apache-2.0, 57,7 GB) und Ming-Image-0.1-Design-Layer (MIT, 65 GB) sind für
Kundenkarten zu groß.

**Für den Bildweg** (Foto des Kunden) bleibt ein Modell nötig. Wahl
zwischen BiRefNet (MIT, Datenfrage, Status quo) und RMBG-2.0 mit
BRIA-Vertrag (saubere Daten, Kosten unbelegt).

## Übersicht aller Kandidaten

Abkürzungen: W/M/L = Windows/macOS/Linux; „Kern“ = eingebauter
ComfyUI-Knoten; Qualität nur, wo an der Quelle belegt.

| Modell | Code-Lizenz | Gewichte-Lizenz | EU / Ausgaben gewerblich | Problematische Abhängigkeiten | VRAM (Quelle) | W/M/L | ComfyUI-Knoten | Qualität (belegt) | Quelle |
|---|---|---|---|---|---|---|---|---|---|
| TripoSG (Ist) | MIT + Tencent-Hunyuan-Kopf in `triposg_transformer.py`, FlashVDM-`LICENSE` | MIT (Karte) | **nein** (EU aus Territory, §5.c) | — | — | W/L | eigener Knoten | Toys4K IoU 73,54 | `lizenzkette.md` |
| **TRELLIS.2-4B** | MIT | MIT | ja; DINOv3 License (weltweit, gewerblich, Waffen-/Handelsklausel) | Original: nvdiffrast/nvdiffrec, CuMesh, FlexGEMM, o-voxel, flash-attn, RMBG-2.0 (NC) — **im Kern keine** | Original ≥ 24 GB; Kern int8 ≈ 16 GB praktikabel (Drittquelle), 8/12 GB unbelegt | W/L ja; M mit Fehlern (#16017) | **Kern** seit v0.34.0 | Paper Tab. 2: bester Wert gegen 5 Gegner, 66,5 % Präferenz | microsoft/TRELLIS.2@75fbf018, HF @af44b45f, Comfy-Org/TRELLIS.2@430a9d09 |
| **Pixal3D** | MIT (seit 20.05.2026; vorher nur Forschung, ohne EU) | MIT (dto.) | ja (nach Umlizenzierung); DINOv3 wie oben | wie TRELLIS.2, dazu natten, MoGe-2 (MIT) — **im Kern keine** | ≥ 16 GB, 24 empfohlen (Drittquellen); Kern int8 5,6 GB DiT | W/L; M wie oben | **Kern** seit v0.34.0 | Toys4K IoU 93,57 / TripoSG 73,54 (Paper-Zweig) | TencentARC/Pixal3D@f7cf3842, HF @b0cb2e1b |
| trellis.cpp (Laufzeit) | MIT | GGUF von Dritten (Lizenzfeld „other“) | wie TRELLIS.2 | — | 1024er-Kaskade auf 16 GB; M5 5,6 GB bei 512 | W/L fertig, M (Metal) belegt | nein (eigener HTTP-Server) | — | pwilkin/trellis.cpp@c0bed38c |
| TRELLIS v1 | MIT | MIT | ja; DINOv2 Apache-2.0 | spconv, xformers/flash-attn; nvdiffrast/pymeshfix (AGPL) nur in `to_glb` | ≥ 16 GB | L (W ungetestet) | Pakete (3D-Pack u. a., MIT) | Toys4K IoU 79,48 (> TripoSG) | microsoft/TRELLIS@442aa1e1 |
| TripoSR | MIT | MIT | ja; Training nur CC-BY-Objaverse | torchmcubes (MPL-2.0, kompilieren) | ≈ 6 GB | W/L; CPU-Rückfall (README), ONNX-Fassungen | Flowty (GPL-3.0), 3D-Pack | schwächer, 2024 | VAST-AI-Research/TripoSR@107cefdc |
| Hi3DGen | MIT | MIT / Apache-2.0 | ja; Trainingsdaten teils aus FLUX.1-dev | spconv, xformers | unbelegt | L | keiner verbreitet | nur Nutzerstudie | Stable-X/Hi3DGen@c29f668e |
| Direct3D-S2 | MIT | MIT | ja | torchsparse (bauen), flash-attn, pymeshfix (AGPL) | 10 GB (512³) / 24 GB (1024³) | L (W über Issues) | Yuan-ManX (MIT) | Toys4K IoU 74,23 | DreamTechAI/Direct3D-S2@a1cf235b |
| Step1X-3D | Apache-2.0 + **Tencent-NC-Kopf** im Volumendekoder | Apache-2.0 | **nein** in dieser Form (NC-Kopf im Formweg) | rembg „bria“ (NC); Textur: nvdiffrast | 27 GB mit Textur | L | Yuan-ManX (MIT) | TRELLIS.2-Tab. 2 Gegner | stepfun-ai/Step1X-3D@cb5ac944 |
| PartCrafter, DetailGen3D, HoloPart, MIDI-3D | MIT + Hunyuan-Kopf | MIT / Apache-2.0 | **nein** (wie TripoSG) | — | — | — | — | — | Repos s. K8 |
| Hunyuan3D 2.x / Omni / Part | Tencent Community | dto. | **nein** | — | — | — | Kern (2.0/2.1) | Toys4K IoU 83,33 (2.1) | Tencent-Hunyuan/Hunyuan3D-2.1@82920d64 |
| UltraShape 1.0 | Tencent Hunyuan 3D 2.1 (`LICENSE`) | Karte Apache-2.0 | **nein** | braucht Hunyuan3D-2.1 | — | — | jtydhr88 | — | PKU-YuanGroup/UltraShape-1.0@5e8dcef0 |
| LATTICE / Hunyuan3D 2.5/3.0 | — | keine offenen Gewichte belegt | — | — | — | — | — | — | lattice3d.github.io |
| Sparc3D / Hitem3D | kein Code | keine Gewichte | — | — | — | — | — | — | lizhihao6/Sparc3D@dbcf176e |
| SAM 3D Objects | SAM License | SAM License, `gated: manual` | Lizenz tragbar, technisch ausgeschlossen | kaolin, pytorch3d, gsplat, bpy (GPL), pymeshfix (AGPL) | ≥ 32 GB | L | Pozzetti (Lizenz offen) | — | facebookresearch/sam-3d-objects@f91db411 |
| Cube 3D / CubePart | Research-Only RAIL-MS | dto. | **nein** | — | — | — | — | — | Roblox/cube@3c6d06dd |
| Arbor | Stability Community | dto. | Umsatzschwelle 1 Mio. US-$ | — | — | — | — | — | StabilityLabs/arbor |
| SPAR3D, SF3D | Stability Community | dto., `gated: auto` | Umsatzschwelle | — | — | — | — | — | HF stabilityai |
| InstantMesh | Apache-2.0 | Apache-2.0; Zero123++ **CC-BY-NC** | **nein** | nvdiffrast | — | — | 3D-Pack | — | TencentARC/InstantMesh@08822c52 |
| CRM | MIT | MIT | — | nvdiffrast, pymeshlab (GPL) | — | — | 3D-Pack | — | thu-ml/CRM@4964e36a |
| LGM | MIT | MIT | — | diff-gaussian-rasterization (Inria NC), nvdiffrast | ≈ 10 GB | — | 3D-Pack | — | 3DTopia/LGM@fe8d12cf |
| CraftsMan3D | keine Lizenzdatei | CreativeML OpenRAIL-M | unklar | Michelangelo-Erbe (GPL-3.0) | — | — | Wrapper | — | wyysf-98/CraftsMan@f87d6a54 |
| Michelangelo | GPL-3.0 | LGPL-3.0 | — | nvdiffrast, pymeshlab | — | — | — | veraltet | NeuralCarver/Michelangelo@6d83b0ba |
| TripoSF | MIT | MIT | — | spconv, flash-attn | — | — | — | nur VAE | VAST-AI-Research/TripoSF@b97b749a |
| TripoSplat | MIT | MIT | ja | — | — | — | Kern | Gaussians, kein Netz | HF VAST-AI/TripoSplat |
| Shap-E | MIT | MIT | Karte rät ab | — | — | — | — | schwach | verworfen 31.08. |

## Was in Solidons Einrichtung zu ändern wäre

### Für K1 TRELLIS.2 (empfohlen)

1. **Eigenen Knoten und Quelltextabruf streichen:** `ComfyUI-TripoSG-Solidon`
   (`app/core/backends/data/comfyui/`), `fetch_triposg` (Git-Klon von
   `VAST-AI-Research/TripoSG@fc5c4099`), die Quelltext-Patches, die
   Paketnachzüge (ANTLR, jaxtyping, scikit-image) und den
   `snapshot_download` von `VAST-AI/TripoSG@2c1c516d` (7,5 GB).
2. **ComfyUI-Mindestversion v0.35.0** (09.09.2026) prüfen — sie enthält die
   Kernknoten (v0.34.0), die Speichersenkung #16054 und die
   Attention-Korrektur #16029 (per `git compare` als Vorfahren belegt). Getestet
   werden sollte gegen v0.39.0 (05.10.2026). Die Knoten-IDs blieben bei der
   Umbenennung vom 17.09.2026 (#16274) stabil, nur Anzeigenamen und
   Kategorien änderten sich. `mesh.py::missing_nodes` meldet zu alte
   Installationen schon heute über fehlende Knotennamen.
3. **Gewichte als Einzeldateien mit Revision und SHA-256** wie heute bei
   BiRefNet und SDXL (`hf_hub_download`):

   | Datei | Repo @ Revision | Byte | SHA-256 | Zielordner |
   |---|---|---|---|---|
   | `diffusion_models/trellis_2_int8_convrot.safetensors` | `Comfy-Org/TRELLIS.2` @ `430a9d09b2416687018c8fe8edced2ad4858a439` | 5 253 048 192 | `d01952ad137213f6a868f86b6b877026276f84af5eec23069217475a0bad3a31` | `models/diffusion_models/` |
   | `vae/trellis_2_shape_vae_bf16.safetensors` | dto. | 1 095 844 024 | `de0cb4949a76c59ee5c091a995a69bcc8c51d5aeda939f0c641a50d2a72341f4` | `models/vae/` |
   | `clip_vision/dino_v3_vit_l.safetensors` | dto. | 1 212 559 776 | `5cb785e458de7c460579082418af81f5c62380c181599344bdc60898c63468ee` | `models/clip_vision/` |
   | `background_removal/birefnet.safetensors` | `Comfy-Org/BiRefNet` @ `5a1bd8ae…` (wie heute) | 444 473 596 | `9ab37426…` | `models/background_removal/` |

   Summe ≈ 8,0 GB (heute 7,95 GB TripoSG + 0,44 GB BiRefNet ≈ 8,4 GB). Für
   Karten ab 24 GB optional
   `trellis_2_bf16.safetensors` (10 338 297 616 Byte, `bf8ebe29…`). Die
   Textur-VAE (0,95 GB) entfällt, weil Solidon keine Textur braucht.
   **Alternative DINOv3-Quelle:** das zugangsbeschränkte Original
   `facebook/dinov3-vitl16-pretrain-lvd1689m` @ `ea8dc286` (manuelle Freigabe,
   Kunde braucht eigenes HF-Konto) — Entscheidung nach Kanzleiantwort.
4. **`image_to_mesh.json` neu** aus Kernknoten, Werte aus der offiziellen
   Vorlage `templates/3d_pixal3d_trellis2_image_to_model.json`
   (Comfy-Org/workflow_templates @ `0e5c5efb`, 02.10.2026): `LoadImage` →
   `LoadBackgroundRemovalModel`/`RemoveBackground` → `ImageCropToMask`
   (1024, Rand 1,1) → `CLIPVisionLoader` → `Trellis2Conditioning` →
   `UNETLoader` → `EmptyTrellis2LatentStructure` → `KSampler` (12 Schritte,
   CFG 7,5, mit `CFGOverride`/`RescaleCFG` wie Vorlage) → `VAELoader` →
   `VaeDecodeStructureTrellis2` → `Trellis2ShapeStage` → `KSampler` →
   `Trellis2UpsampleStage` (1024 statt 1536 für 16-GB-Karten) → `KSampler` →
   `VaeDecodeShapeTrellis` → `RemeshMesh` → `DecimateMesh` → `MeshToFile3D`
   (GLB oder STL). **`RemeshMesh` nicht mit den Vorlagenwerten:** Im
   `udf`-Modus entsteht laut Tooltip eine Innenhülle („the UDF inner shell“);
   entweder `drop_inverted_components` und `drop_enclosed_components` setzen
   oder `sign_mode=sdf` — oder Remesh weglassen und in Solidon zum
   Volumenkörper schließen. Das erklärt vermutlich #16147.
5. **Solidons Reparatur** muss Innenhüllen, kleine Löcher und
   Doppelflächen behandeln; TripoSGs Belegungsfeld lieferte das bisher
   geschlossen. Abnahme über Solidons Druckprüfung an echten Läufen.
6. **Lizenzunterlagen:** `licences.toml` — TripoSG raus; TRELLIS.2 (MIT,
   Microsoft), **DINOv3 License** (neu, keine OSI-Lizenz; Lizenztext vor dem
   Abruf zeigen, Zustimmung einholen, §1.b.v in Solidons eigene Bedingungen
   übernehmen — Kanzlei), BiRefNet (MIT). Handbuch, Website und
   Einrichtungstexte nennen TRELLIS.2 statt TripoSG; die Kommentare in
   `comfy_setup.py:91-94` und die Kopfzeilen des alten Knotens verschwinden
   mit ihm.
7. **Plattformen:** NVIDIA unter Windows/Linux ohne Kompilieren; AMD unter
   ROCm mit offenem Fehler nur in der UV-Abwicklung (von Solidon nicht
   gebraucht); macOS ab 26.7 lauffähig, `RemeshMesh`/`DecimateMesh` auf MPS
   bei großen Netzen fehlerhaft (#16017) — dort ohne Remesh arbeiten oder
   kleiner auflösen. Ein Lauf je Plattform gehört in RM-004.

### Für K2 Pixal3D (zuschaltbar im selben Graphen)

Zusätzlich zu 3.: `Comfy-Org/Pixal3D` @ `f37641be376725d324c56626007cc477f1249a69`:
`diffusion_models/pixal3d_int8_convrot.safetensors` (5 584 555 824 Byte,
`4621eac3b715484f79303c7152af641fe0b2b14f4d0e3d394fd6922d00f955ec`),
`clip_vision/dino_v3_L_naf_fp32.safetensors` (1 215 214 176 Byte,
`4ad2ec4e0879a5b5b04cd97325cc37da954a7b6edca5170b86510f17f2b2290f`);
`Comfy-Org/MoGe` @ `1484985258ba7ef45c314144fcf0e90924ffbf44`:
`geometry_estimation/moge_2_vitl_normal_fp16.safetensors` (661 859 924 Byte,
`cb1a692d03235671e959e81360d7b4d9f44aefadb1f852d6ca6aa17799d5e31f`). Knoten
zusätzlich `LoadMoGeModel`, `MoGeInference`, `MoGeGeometryToFOV`,
`Pixal3DConditioning` statt `Trellis2Conditioning`. Pixal3D allein mit
Form-VAE und BiRefNet ≈ 9,0 GB; beide Modelle zusammen ≈ 14,3 GB, wenn nur
`dino_v3_L_naf_fp32` geladen wird (die ComfyUI-Doku nennt sie für TRELLIS.2
gleichwertig zu `dino_v3_vit_l`).

### Für den Textweg

`text_to_mesh.json`: `CheckpointLoaderSimple` (SDXL, 6,9 GB) ersetzen durch
die Kernknoten der Vorlage `templates/image_flux2_klein_text_to_image.json`,
Teilgraph „Flux.2 Klein 4B Distilled“ (workflow_templates @ `0e5c5efb`):
`UNETLoader`, `CLIPLoader` (Typ `flux2`), `VAELoader`,
`EmptyFlux2LatentImage` (1024²), `CLIPTextEncode`, `ConditioningZeroOut` als
Negativ, `CFGGuider` (1), `Flux2Scheduler` (4 Schritte), `KSamplerSelect`
(`euler`), `RandomNoise`, `SamplerCustomAdvanced`, `VAEDecode`. Dateien:

| Datei | Repo @ Revision | Byte | SHA-256 | Zielordner |
|---|---|---|---|---|
| `flux-2-klein-4b-fp8.safetensors` | `black-forest-labs/FLUX.2-klein-4b-fp8` @ `5b4408e59397a4a37ccb46afe426d8ed86379441` | 4 070 624 520 | `97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6` | `models/diffusion_models/` |
| `split_files/text_encoders/qwen_3_4b_fp4_flux2.safetensors` | `Comfy-Org/vae-text-encorder-for-flux-klein-4b` @ `5f526678002e43af5551dadb73ce2e8c91b43afe` | 3 848 213 998 | `3eab03a77adb0ee5304a4e677d5c10ac22f9049c1d7c894adca4f8bb39206ca8` | `models/text_encoders/` |
| `split_files/vae/flux2-vae.safetensors` | dto. | 336 211 292 | `868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3` | `models/vae/` |

Summe ≈ 8,3 GB statt 6,9 GB für SDXL. Ob die fp8-Fassung mit dem
fp4-Textkodierer auf 8-GB-Karten läuft, ist **nicht belegt**; die Karte nennt
≈ 13 GB für bf16. Ob der Vorlagen-`UNETLoader` die BFL-fp8-Datei ohne
Umwandlung annimmt, ist **nicht nachgestellt** — sonst die bf16-Datei
`split_files/diffusion_models/flux-2-klein-4b.safetensors` (7,75 GB) aus dem
Comfy-Org-Paket. Danach Solidons eigener Weiß-Keyer statt
`RemoveBackground`, mit BiRefNet als Rückfall.

Gleichwertige Alternative Z-Image-Turbo (Vorlage
`templates/image_z_image_turbo.json`: `UNETLoader`, `CLIPLoader` Typ
`lumina2`, `VAELoader`, `EmptySD3LatentImage`, `ModelSamplingAuraFlow` 3,
`KSampler` 8 Schritte, CFG 1, `res_multistep`/`simple`) aus
`Comfy-Org/z_image_turbo` @ `6fc90a3b1b653e935a0d175e260736de25b84df5`:
`z_image_turbo_int8_convrot.safetensors` (6 201 001 296 Byte,
`be517ebd47c912a5626a588e1aeea43e6be4a43c0cdcd2b48a2a780d9f358635`),
`qwen_3_4b_fp8_mixed.safetensors` (5 631 994 051 Byte,
`72450b19758172c5a7273cf7de729d1c17e7f434a104a00167624cba94f68f15`),
`ae.safetensors` (335 304 388 Byte,
`afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38`) —
zusammen ≈ 12,2 GB.

## Fragen an eine Kanzlei

Ergänzend zu den Fragen 7–16 in `lizenzkette.md`:

1. **DINOv3 License:** Wird ein Solidon-Kunde in der EU durch bloße Nutzung
   Vertragspartner von Meta Platforms Ireland (Präambel, §6)? Muss Solidon den
   Text vor dem Abruf anzeigen und eine Zustimmung einholen, und genügt das
   für die Einbeziehung? Wie wirkt §8 (einseitige Änderung, Weiternutzung als
   Zustimmung) nach deutschem AGB-Recht?
2. Darf Solidon DINOv3 aus der freien Kopie `Comfy-Org/TRELLIS.2` (als MIT
   ausgewiesen, ohne Lizenzkopie) oder aus `timm/…dinov3…` (mit Lizenzkopie)
   laden lassen, statt aus dem zugangsbeschränkten Original? Wer verstößt ggf.
   gegen §1.b.i?
3. Muss Solidon die Endverwendungsverbote aus §1.b.v (u. a. Entwicklung oder
   Nutzung von Waffen) in die eigenen Bedingungen übernehmen, und was folgt
   daraus für ein Programm, mit dem Kunden beliebige Teile drucken?
4. **Pixal3D:** Wirkt die Umstellung auf MIT (20.05.2026) auch für die
   Gewichte, die am 30.04.2026 hochgeladen wurden und vom 12. bis 20.05.2026
   unter einer Lizenz ohne EU standen? Kann Tencent den Wechsel widerrufen?
5. **Trainingsdaten 3D:** Schlagen CC-BY-NC/NC-SA-Objekte aus Objaverse, HSSD
   (CC BY-NC 4.0) und 3D-FUTURE (nur Forschung) auf die MIT-Gewichte von
   TRELLIS.2 oder auf die erzeugten Netze durch? Welche Rolle spielen
   § 44b UrhG und Art. 4 DSM-Richtlinie, wenn das Training in den USA
   stattfand?
6. **Hi3DGen:** Gilt dasselbe für Trainingsdaten, die mit FLUX.1-dev
   (nicht-kommerzielle Lizenz) erzeugt wurden?
7. **Freistellen:** Wie Frage 12 in `lizenzkette.md` (DIS5K), erweitert auf
   DUTS/HRSOD/UHRSD/P3M; und: Deckt ein BRIA-Vertrag für RMBG-2.0 die
   Ausführung auf Kundenrechnern, die Solidons Einrichtung anstößt?
8. **Apache-2.0-Modelle** (FLUX.2 [klein] 4B, Z-Image-Turbo, Qwen3-4B): Muss
   Solidon NOTICE-/Lizenztexte zeigen, wenn es die Dateien nicht selbst
   verbreitet, sondern der Kunde sie über Solidons Einrichtung lädt?
9. **ComfyUI (GPL-3.0):** Bestätigung, dass Solidon als getrenntes Programm
   über HTTP kein abgeleitetes Werk ist, auch wenn Solidons Einrichtung
   ComfyUI-Arbeitsflüsse mitliefert und Modelle in dessen Ordner legt.

## Beifunde (nicht geändert, der Auftrag war nur lesend)

- `konzepte/konzept-erzeugen-agent-oberflaeche-2026-08.md:173-182` führt
  Step1X-3D als „Apache-2.0, kommerziell ja, EU ja“ und InSPyReNet als MIT
  ohne Vorbehalt. Laut dieser Prüfung trägt Step1X-3Ds Volumendekoder einen
  Tencent-Hunyuan-Non-Commercial-Kopf (K7), und InSPyReNets Prüfpunkte sind
  auf DUTS/HRSOD/UHRSD/DIS5K trainiert (V2).
- Die am 31.08.2026 verworfene TRELLIS.2-Bewertung (nvdiffrast/nvdiffrec,
  kein Produktweg unter Windows/macOS) ist durch Q1 überholt: Die
  Kern-Umsetzung kam fünf Tage davor mit v0.34.0 (26.08.2026).
- Die Hugging-Face-Karte von UltraShape (Apache-2.0) widerspricht der
  Lizenzdatei des Repositorys (Tencent, EU ausgenommen); die Karte von
  CubePart („openrail“) widerspricht der Research-Only-Lizenz; die
  Comfy-Org-Pakete führen DINOv3-Gewichte als MIT.

## Quellen

Alle abgerufen am 06.10.2026. GitHub-Stände über `git clone --depth 1` und
die REST-API, Hugging-Face-Stände über `/api/models/<repo>?blobs=true`
(Revision, Größe, SHA-256) und `/raw/<revision>/…`.

**ComfyUI-Kern und Vorlagen**
- https://github.com/Comfy-Org/ComfyUI/pull/14718 (TRELLIS.2/Pixal3D im Kern, gemergt 22.08.2026)
- https://github.com/Comfy-Org/ComfyUI/tree/7a5dad695fe1cae25efcb2550530fb20ef68da3d/comfy/ldm/trellis2
- https://github.com/Comfy-Org/ComfyUI/blob/7a5dad695fe1cae25efcb2550530fb20ef68da3d/comfy_extras/nodes_trellis2.py
- https://github.com/Comfy-Org/ComfyUI/blob/7a5dad695fe1cae25efcb2550530fb20ef68da3d/comfy_extras/nodes_mesh_postprocess.py
- https://github.com/Comfy-Org/ComfyUI/blob/7a5dad695fe1cae25efcb2550530fb20ef68da3d/comfy/image_encoders/naf.py
- https://github.com/Comfy-Org/ComfyUI/blob/7a5dad695fe1cae25efcb2550530fb20ef68da3d/comfy/clip_vision.py
- https://github.com/Comfy-Org/ComfyUI/blob/7a5dad695fe1cae25efcb2550530fb20ef68da3d/comfy/bg_removal_model.py
- https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.34.0, …/v0.35.0, …/v0.39.0
- https://github.com/Comfy-Org/ComfyUI/pull/16054, https://github.com/Comfy-Org/ComfyUI/pull/16029, https://github.com/Comfy-Org/ComfyUI/pull/16274
- https://github.com/Comfy-Org/ComfyUI/issues/16147, …/16340, …/16017, …/16124, …/16056, …/16620
- https://github.com/Comfy-Org/docs/blob/main/tutorials/3d/trellis2.mdx, …/pixal3d.mdx, …/triposplat.mdx, https://github.com/Comfy-Org/docs/blob/main/changelog/index.mdx
- https://github.com/Comfy-Org/workflow_templates/blob/0e5c5efb32ba6f3365d6da07da64aaf668157042/templates/3d_pixal3d_trellis2_image_to_model.json
- https://github.com/Comfy-Org/workflow_templates/blob/0e5c5efb32ba6f3365d6da07da64aaf668157042/templates/image_z_image_turbo.json
- https://huggingface.co/Comfy-Org/TRELLIS.2/tree/430a9d09b2416687018c8fe8edced2ad4858a439
- https://huggingface.co/Comfy-Org/Pixal3D/tree/f37641be376725d324c56626007cc477f1249a69
- https://huggingface.co/Comfy-Org/MoGe/tree/1484985258ba7ef45c314144fcf0e90924ffbf44
- https://huggingface.co/Comfy-Org/BiRefNet/tree/25511f8787e51912e1480706b4e47b8f467fbf72
- https://huggingface.co/Comfy-Org/z_image_turbo/tree/6fc90a3b1b653e935a0d175e260736de25b84df5
- https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-4b/tree/5f526678002e43af5551dadb73ce2e8c91b43afe
- https://huggingface.co/api/models?pipeline_tag=image-to-3d&sort=downloads&direction=-1 (und `sort=trendingScore`)
- Drittquelle, nur für Erfahrungswerte: https://www.instasd.com/post/trellis-2-pixal3d-native-comfyui-guide

**TRELLIS.2, DINOv3, Pixal3D, trellis.cpp**
- https://github.com/microsoft/TRELLIS.2/tree/75fbf0183001ed9876c8dbb35de6b68552ee08bd (README, `setup.sh`, `LICENSE`)
- https://huggingface.co/microsoft/TRELLIS.2-4B/tree/af44b45f2e35a493886929c6d786e563ec68364d (`README.md`, `pipeline.json`)
- https://arxiv.org/abs/2512.14692
- https://github.com/JeffreyXiang/CuMesh, https://github.com/JeffreyXiang/FlexGEMM, https://github.com/NVlabs/nvdiffrast
- https://github.com/facebookresearch/dinov3/blob/ffb4bb89c6558ca3244655c25a3955d01788b732/LICENSE.md
- https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m (Revision `ea8dc2863c51be0a264bab82070e3e8836b02d51`, `gated: manual`)
- https://huggingface.co/timm/vit_large_patch16_dinov3.lvd1689m (Revision `30c1109559f65dea34316b0d4842d35c5771fe11`)
- https://github.com/TencentARC/Pixal3D/tree/f7cf38429b0bd264f1995f0f8743a88b1c728b94 (`LICENSE`, `NOTICE`, `README.md`, `app.py`)
- https://github.com/TencentARC/Pixal3D/commit/5098ba1f8c528f2c3e71a3ae88545e2826740d2b (Lizenzwechsel)
- https://github.com/TencentARC/Pixal3D/commit/28efad66fdcbd8174a8538d9baf71fe34fe4b6d2 (Responsible Use)
- https://huggingface.co/TencentARC/Pixal3D/tree/b0cb2e1b794cab9aa0ac38a95d794a4d9337437f
- https://huggingface.co/TencentARC/Pixal3D/blob/60f4ffb275f49427ba73e0445de9de2a719b1216/LICENSE (alte Lizenz)
- https://huggingface.co/TencentARC/Pixal3D/commit/b648b3c5a83fcee3628c8c608a64e26d73cdfce4 (MIT)
- https://arxiv.org/abs/2605.10922 (Tabellen 1 und 2)
- https://huggingface.co/Ruicheng/moge-2-vitl-normal (Revision `cb0e8bbd6b1e243589717c78e750b1ba4c093acf`)
- https://github.com/valeoai/NAF
- https://github.com/pwilkin/trellis.cpp/tree/c0bed38c1578f7e36e3e50c8ff1e38fa0d47583f, https://github.com/pwilkin/trellis.cpp/releases/tag/v0.8.1, https://huggingface.co/ilintar/trellis2-gguf

**Übrige 3D-Kandidaten**
- https://github.com/microsoft/TRELLIS/tree/442aa1e1afb9014e80681d3bf604e8d728a86ee7 (README, `DATASET.md`, `trellis/utils/postprocessing_utils.py`)
- https://huggingface.co/microsoft/TRELLIS-image-large/tree/25e0d31ffbebe4b5a97464dd851910efc3002d96
- https://github.com/MaxtirError/FlexiCubes, https://github.com/nv-tlabs/FlexiCubes
- https://pypi.org/project/pymeshfix/0.18.1/, https://pypi.org/project/spconv-cu121/, https://pypi.org/project/xformers/
- https://github.com/MrForExample/ComfyUI-3D-Pack, https://github.com/if-ai/ComfyUI-IF_Trellis, https://github.com/smthemex/ComfyUI_TRELLIS
- https://github.com/VAST-AI-Research/TripoSR/tree/107cefdc244c39106fa830359024f6a2f1c78871
- https://huggingface.co/stabilityai/TripoSR/tree/5b521936b01fbe1890f6f9baed0254ab6351c04a
- https://github.com/tatsy/torchmcubes, https://github.com/flowtyone/ComfyUI-Flowty-TripoSR, https://huggingface.co/facebook/dino-vitb16
- https://github.com/Stable-X/Hi3DGen/tree/c29f668ecec44b197275e9bf77f823c0c8a21076
- https://huggingface.co/Stable-X/trellis-normal-v0-1/tree/fdfac1d0e0cb3f86adcac69239c1abdd82228e17
- https://huggingface.co/Stable-X/yoso-normal-v1-8-1/tree/4dd7d000d76febb68254ebe27251c2cb79dc1c2a
- https://github.com/hugoycj/StableNormal, https://arxiv.org/html/2503.22236
- https://github.com/DreamTechAI/Direct3D-S2/tree/a1cf235b2881cff04a91900060a9546b40e7ee5d
- https://huggingface.co/wushuang98/Direct3D-S2/tree/8b04a8eddb7a56a0f4e89fe5f5b840c7d5610c00
- https://github.com/Yuan-ManX/ComfyUI-Direct3D-S2, https://github.com/Yuan-ManX/ComfyUI-Step1X-3D
- https://github.com/stepfun-ai/Step1X-3D/blob/cb5ac944709c6c913109070c7b90c3447f57f3d4/step1x3d_geometry/models/autoencoders/volume_decoders.py
- https://huggingface.co/stepfun-ai/Step1X-3D/tree/bf7084495b3a72222f36549b7942948aa4d9daa7
- https://github.com/wgsxm/PartCrafter/blob/3d773bf02fad51c7ab31a5615573fec93b287b30/src/models/transformers/partcrafter_transformer.py
- https://github.com/VAST-AI-Research/DetailGen3D/tree/acdf05e1677c9aa7e656efddf4973e6b02ef1c24
- https://github.com/VAST-AI-Research/HoloPart/tree/48dd632c9a7412e6688573bb4f153e0ade7e7325
- https://github.com/VAST-AI-Research/MIDI-3D (Codesuche „Hunyuan“)
- https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/82920d643c0dc2f7bfd7255f45f62d386edfe60c/LICENSE
- https://github.com/Tencent-Hunyuan/Hunyuan3D-Omni/tree/4d47c0cc2bd0c4281963a7314ab330a5af36bfa8
- https://huggingface.co/tencent/Hunyuan3D-2.1, https://huggingface.co/Comfy-Org/hunyuan3D_2.1_repackaged
- https://github.com/PKU-YuanGroup/UltraShape-1.0/blob/5e8dcef05df101ab00ab6cd5fdd0ed0c74fbca66/LICENSE
- https://huggingface.co/infinith/UltraShape/tree/5aeb21a7185d39f042d02b2695802f125a6f5159
- https://arxiv.org/abs/2512.03052, https://lattice3d.github.io
- https://github.com/lizhihao6/Sparc3D/tree/dbcf176e3031fd0de4300ee46b6db42842e73550, https://github.com/ben-kaye/Sparc3Dsdf
- https://github.com/facebookresearch/sam-3d-objects/blob/f91db411c50efee93d8db7aeb323885650f6f722/LICENSE, …/doc/setup.md
- https://huggingface.co/facebook/sam-3d-objects (Revision `2e73555018d2741ccd486e56c24fac41155a1dc6`)
- https://github.com/Roblox/cube/blob/3c6d06ddbef3160a1e1950cb13ab63dd12a61e50/LICENSE, https://huggingface.co/Roblox/cubepart
- https://huggingface.co/StabilityLabs/arbor/tree/9b8a23dcc3b8d0045668d289827c354c3ac184b0
- https://huggingface.co/stabilityai/stable-point-aware-3d, https://huggingface.co/stabilityai/stable-fast-3d
- https://github.com/TencentARC/InstantMesh/tree/08822c52fdc399b93ea00e4fa9e596344ed52ccc, https://github.com/SUDO-AI-3D/zero123plus
- https://github.com/thu-ml/CRM/tree/4964e36a593070a3045eb0f300935a771ff5c172
- https://github.com/3DTopia/LGM/tree/fe8d12cff8c827df7bb77a3c8e8b37408cb6fe4c
- https://github.com/wyysf-98/CraftsMan/tree/f87d6a54ef7e818581b1c97a2aa962dc731306a0, https://huggingface.co/craftsman3d/craftsman
- https://github.com/NeuralCarver/Michelangelo/tree/6d83b0bacef92715dd5179d45647ed9a3d39bc95, https://huggingface.co/Maikou/Michelangelo
- https://github.com/VAST-AI-Research/TripoSF/tree/b97b749aa5726fb64ceec359a4ef8e61e79279c7
- https://huggingface.co/VAST-AI/TripoSplat, https://huggingface.co/facebook/Large-Sparse-Reconstruction-Model
- https://arxiv.org/html/2502.06608 (TripoSG: keine Kennzahlvergleiche gegen andere Modelle)

**Trainingsdaten**
- https://huggingface.co/datasets/allenai/objaverse, https://huggingface.co/datasets/allenai/objaverse-xl
- https://huggingface.co/datasets/hssd/hssd-hab
- https://amazon-berkeley-objects.s3.amazonaws.com/index.html
- https://terms.aliyun.com/legal-agreement/terms/suit_bu1_ali_cloud/suit_bu1_ali_cloud202004171628_60052.html (3D-FUTURE)
- https://huggingface.co/datasets/YiboZhang2001/TexVerse
- https://github.com/xuebinqin/DIS/blob/main/DIS5K-Dataset-Terms-of-Use.pdf

**Bildmodelle**
- https://huggingface.co/Tongyi-MAI/Z-Image-Turbo/tree/f332072aa78be7aecdf3ee76d5c247082da564a6
- https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/tree/e7b7dc27f91deacad38e78976d1f2b499d76a294 (`LICENSE.md`, `README.md`)
- https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/tree/5b4408e59397a4a37ccb46afe426d8ed86379441
- https://github.com/Comfy-Org/workflow_templates/blob/0e5c5efb32ba6f3365d6da07da64aaf668157042/templates/image_flux2_klein_text_to_image.json
- https://huggingface.co/black-forest-labs/FLUX.1-schnell/tree/741f7c3ce8b383c54771c7003378a50191e9efe9 (VAE-Abgleich)
- https://huggingface.co/black-forest-labs/FLUX.2-klein-9B, https://huggingface.co/black-forest-labs/FLUX.2-dev (FLUX-Non-Commercial)
- https://huggingface.co/Qwen/Qwen3-4B, https://huggingface.co/Qwen/Qwen-Image, https://huggingface.co/Comfy-Org/Qwen-Image-2.1
- https://huggingface.co/baidu/ERNIE-Image, https://huggingface.co/Comfy-Org/HiDream-O1-Image
- https://huggingface.co/Alpha-VLLM/Lumina-Image-2.0, https://huggingface.co/Efficient-Large-Model/Sana_1600M_1024px_BF16_diffusers
- https://huggingface.co/Comfy-Org/Mage-Flow (Original `microsoft/Mage-Flow` nicht abrufbar)
- https://huggingface.co/Comfy-Org/Krea-2, https://huggingface.co/Comfy-Org/Ideogram-4, https://huggingface.co/Comfy-Org/MiniMax-H3, https://huggingface.co/Comfy-Org/PixelDiT
- https://huggingface.co/stabilityai/stable-diffusion-3.5-medium, https://huggingface.co/tencent/HunyuanImage-2.1
- https://huggingface.co/Kwai-Kolors/Kolors/blob/main/MODEL_LICENSE
- https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 (siehe `lizenzkette.md`)

**Freistellen**
- https://huggingface.co/ZhengPeng7/BiRefNet, https://huggingface.co/egeorcun/lucida/tree/6cbedc9722652dc9a3df91dd871f0c4f3334e922, https://huggingface.co/joelseytre/toonout
- https://huggingface.co/briaai/RMBG-2.0 (Revision `5df4c9c76d8170882c34f6986e848ee07fd0ba43`), https://bria.ai/introducing-the-rmbg-v2-0-model-the-next-generation-in-background-removal-from-images, https://huggingface.co/briaai/RMBG-1.4
- https://huggingface.co/PramaLLC/BEN2/tree/e48a20765fb421d19dcdb0bf3cc61e802ca5ec8f
- https://github.com/plemeri/InSPyReNet/blob/main/docs/model_zoo.md, https://github.com/plemeri/transparent-background
- https://github.com/withoutbg/withoutbg, https://huggingface.co/withoutbg/snap
- https://huggingface.co/facebook/sam2.1-hiera-large, https://huggingface.co/facebook/sam3, https://huggingface.co/Comfy-Org/sam3.1
- https://huggingface.co/LayerDiffusion/layerdiffusion-v1, https://github.com/huchenlei/ComfyUI-layerdiffuse
- https://huggingface.co/Qwen/Qwen-Image-Layered, https://huggingface.co/inclusionAI/Ming-Image-0.1-Design-Layer
