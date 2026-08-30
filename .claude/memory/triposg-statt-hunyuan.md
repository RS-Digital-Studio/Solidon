---
name: triposg-statt-hunyuan
description: "Solidons Mesh-Erzeugung läuft seit 20.08.2026 auf TripoSG (MIT) statt Hunyuan3D — mit drei Fallen, die den ersten Lauf kosten."
metadata: 
  node_type: memory
  type: project
  originSessionId: cb9b39e7-6deb-4fb2-a5ba-c8e29524d1b0
  modified: 2026-08-30T08:19:15.415Z
---

Der mitgelieferte Erzeuger-Ablauf benutzt **TripoSG** (VAST-AI-Research, MIT
für Quelltext *und* Gewichte), nicht mehr Hunyuan3D. Grund ist allein die
Lizenz: Die Tencent Community License nimmt die EU ausdrücklich aus, und
Solidon wird hier verkauft. Die Hunyuan-Sammlung bleibt in ComfyUI installiert
und die Muster dafür stehen weiter in `MODEL_ROLES` — siehe
[[comfyui-installation-d-ai]].

Die Knoten liegen im Repository unter `tools/comfyui/ComfyUI-TripoSG-Solidon`
und werden mit `python tools/setup_comfyui.py` eingerichtet (kopiert, klont
TripoSG, patcht, installiert, lädt 7,5 GB Gewichte nach `models/triposg`).

**Drei Fallen**, jede hat einen Lauf gekostet:

1. **Der Fourier-Embedder gibt float32 zurück**, auch wenn er float16
   bekommt. Die nächste Linearschicht trägt halbe Gewichte → „mat1 and mat2
   must have the same dtype". Nur im Marching-Cubes-Pfad; mit Flash-Decoder
   fällt es nicht auf, deshalb ist es upstream nicht gefixt.
2. **`diso` hat kein Windows-Wheel** und wird oben in `inference_utils.py`
   hart importiert, obwohl es nur der Flash-Decoder braucht. Import lazy
   machen und `use_flash_decoder=False` fahren.
3. **`requirements.txt` von TripoSG nagelt `numpy==1.22.3`** fest und zieht
   `pymeshlab` (GPL). Niemals ungefiltert installieren — das zerlegt ComfyUI.
   Nur `jaxtyping typeguard fast-simplification` mit `--no-deps`.

**Gemessene Vorgaben** (RTX 4080, vier Testkörper): `octree_depth=8` — 9
bringt keinen sichtbaren Unterschied bei vierfacher Dreieckszahl und
doppelter Zeit. `steps=50` — bei 25 fransen dünne Flächen sichtbar aus. So
rund 13 s je Körper, 300–600 k Dreiecke, wasserdicht und aus einem Stück.

**Dezimieren macht es kaputt**, nicht besser: `simplify_quadric_decimation`
erzeugt eine Handvoll non-manifold Kanten, und `is_watertight` kippt auf
False bei null offenen Kanten. Die Auflösung gehört an der Quelle gesteuert
(`octree_depth`), nicht hinterher.

Der größte Qualitätshebel im Knoten ist **der Zuschnitt vor dem Modell**:
DINOv2 rechnet auf 518 Pixel herunter, ein kleines Objekt im Bild kommt dort
klein an. Auf die Silhouette plus 10 % Rand zuschneiden, quadratisch fassen,
auf Weiß komponieren — Alpha wird von DINOv2 verworfen.

**Der teuerste Fehler war keiner von TripoSG.** Beim Aufräumen wählte
`max(parts, key=lambda p: abs(p.volume) or len(p.faces))` die größte
Komponente — und `abs(volume)` ist bei einem offenen Fragment `0.0`, also
falsch im Sinne von Python. Der Ausdruck fiel auf die Dreieckszahl zurück und
verglich sie mit dem *Volumen* der anderen: zwei Dreiecke schlugen einen
Körper von 1,57. Das sah aus wie ein sporadischer Generator-Ausfall (Startwert
11 leer, 42 gut) und führte auf eine falsche Spur zur halben Rechengenauigkeit.
**Was den Fall aufklärte, war ein Lauf ohne den Aufräum-Knoten** — dort lagen
567 590 Dreiecke in zwanzig Teilen. Wer so ein Bild sieht, prüft zuerst die
Stufe *hinter* dem Verdächtigen.

~~**Grenzen, die nicht zusammenpassen** (Stand 20.08.2026): `FEATURE_LIMIT_TRIANGLES`
in `scene/evaluate.py` ist 200 000, die Automatik in `generate.py` dezimiert
aber erst ab 500 000.~~

**Erledigt, nachgemessen am 30.08.2026.** `generate.GENERATED_TRIANGLE_LIMIT`
ist heute wörtlich `FEATURE_LIMIT_TRIANGLES` (200 000), und
`GENERATED_TRIANGLE_TARGET` sind drei Viertel davon (150 000) — als Anteil und
nicht als eigene Zahl, damit der Abstand mitwandert. Ein echter Textweg-Lauf
bestätigt es: 614 820 Dreiecke aus TripoSG, vierter Stapelschritt
`decimate_mesh`, Ergebnis 150 000 und damit unter der Erkennungsgrenze.

**Was an der Stelle geblieben ist, ist ein anderer Fall:** Der Prüfbericht
zeigt danach `ingest.very_large` — „Analysekarten und Merkmalserkennung lehnen
ab; ‚Dreiecke verringern‘ hilft". Der Befund entsteht in `ingest/loader.py`
beim **Laden** (614 820) und gilt für diesen Zeitpunkt; erledigt hat ihn der
vierte Schritt derselben Kette. Der Kunde liest einen Rat, den die Anwendung
im selben Zug schon befolgt hat — und der Reiter schickt ihn hin
(„Prüfbericht · 1").

**`decimate` zerlegt glatte Körper**: Vase 607 k → 200 k ergab 60 Teile und
`is_watertight=False`; das kantige Gehäuse überstand dieselbe Stufe unversehrt.
Solidons Reparaturkette holt die Teilzahl zurück auf 1, die Wasserdichtheit
nicht. Das ist älter als der TripoSG-Wechsel.
