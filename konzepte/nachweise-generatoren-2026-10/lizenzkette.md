# RM-003 — Lizenzkette der gepinnten Generator-Bestandteile

Abgerufen am 06.10.2026, jeweils an der gepinnten Revision: GitHub über
`raw.githubusercontent.com/<repo>/<commit>/…` und die REST-API, Hugging Face
über `/raw/<revision>/…` und `/api/models/<repo>/revision/<revision>?blobs=true`.
Das ist eine Zuordnung, kein Rechtsurteil. Lizenzklauseln stehen hier
sinngemäß mit Abschnittsnummer; der Wortlaut liegt unter der genannten URL.
Kein Abruf schlug fehl; „404“ heißt, dass die Datei an dieser Revision nicht
existiert.

Alle vier Pins stimmen mit `app/core/backends/comfy_setup.py` überein. Die
SHA-256-Werte von BiRefNet und SDXL laut Hugging-Face-API entsprechen
`BACKGROUND_SHA256` und `IMAGE_MODEL_SHA256`.

## 1 Übersicht

| Bestandteil | Quelle | Revision | Lizenz laut Datei | Fundstelle (URL) |
|---|---|---|---|---|
| TripoSG-Quelltext, Wurzel | github.com/VAST-AI-Research/TripoSG | `fc5c4099…` (18.04.2025; am 06.10.2026 zugleich `main`) | MIT (`LICENSE`); `NOTICE` nennt daneben RMBG-1.4, Diffusers, HunyuanDiT, FlashVDM | https://raw.githubusercontent.com/VAST-AI-Research/TripoSG/fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c/LICENSE und …/NOTICE |
| darin `triposg/models/transformers/triposg_transformer.py` | dto. | dto. | Tencent Hunyuan Community License Agreement (HunyuanDiT, Release 14.05.2024), vollständig im Dateikopf | https://raw.githubusercontent.com/VAST-AI-Research/TripoSG/fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c/triposg/models/transformers/triposg_transformer.py |
| darin `triposg/LICENSE` | dto. | dto. | Tencent Hunyuan FlashVDM Community License Agreement (Release 19.03.2025) | https://raw.githubusercontent.com/VAST-AI-Research/TripoSG/fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c/triposg/LICENSE |
| darin `scripts/briarmbg.py` (übernimmt Solidon nicht) | dto. | dto. | laut `NOTICE` Lizenzkennung `bria-rmbg-1.4` (BRIA AI) | https://raw.githubusercontent.com/VAST-AI-Research/TripoSG/fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c/scripts/briarmbg.py |
| TripoSG-Gewichte | huggingface.co/VAST-AI/TripoSG | `2c1c516d…` (28.03.2025; zugleich `main`) | nur Modellkarte: `license: mit`; keine `LICENSE`, keine `NOTICE` (404) | https://huggingface.co/VAST-AI/TripoSG/raw/2c1c516d22d58db486a058d98d31bb6177344e06/README.md |
| darin `image_encoder_dinov2/model.safetensors` | byte-gleich mit `facebook/dinov2-large`, `model.safetensors` (SHA-256 `399fba97…`, 1 217 522 888 Byte) | — | Apache-2.0 laut Karte von `facebook/dinov2-large` | https://huggingface.co/facebook/dinov2-large |
| Freistellmodell | huggingface.co/Comfy-Org/BiRefNet, `background_removal/birefnet.safetensors` | `5a1bd8ae…` (17.08.2026; `main` steht inzwischen auf `25511f87…`) | nur Modellkarte: `license: mit`, `base_model: ZhengPeng7/BiRefNet`; keine `LICENSE` (404) | https://huggingface.co/Comfy-Org/BiRefNet/raw/5a1bd8ae750548f8cd42e3c8afa854fd3eba0fb1/README.md |
| Original von BiRefNet | huggingface.co/ZhengPeng7/BiRefNet, `model.safetensors`; github.com/ZhengPeng7/BiRefNet | HF `main` = `e2bf8e44…`; SHA-256 `9ab37426…`, dieselbe wie bei Comfy-Org: die Datei ist byte-gleich | MIT (Karte; GitHub-`LICENSE` mit Copyright 2024 ZhengPeng) | https://huggingface.co/ZhengPeng7/BiRefNet und https://github.com/ZhengPeng7/BiRefNet/blob/main/LICENSE |
| Trainingsdaten von BiRefNet (u. a. DIS5K) | github.com/xuebinqin/DIS | `main` | DIS5K Terms of Use: nur nicht-kommerzielle Forschung und Lehre | https://github.com/xuebinqin/DIS/blob/main/DIS5K-Dataset-Terms-of-Use.pdf |
| Bildmodell für den Textweg | huggingface.co/stabilityai/stable-diffusion-xl-base-1.0, `sd_xl_base_1.0.safetensors` | `46216598…` (30.10.2023; zugleich `main`) | CreativeML Open RAIL++-M vom 26.07.2023 (`LICENSE.md`); Karte `license: openrail++` | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/raw/462165984030d82259a11f4367a4eed129e94a7b/LICENSE.md |

Vorbilder der Fremdlizenzen (aktueller Stand, nicht gepinnt):

- **HunyuanDiT:** https://raw.githubusercontent.com/Tencent/HunyuanDiT/main/LICENSE.txt,
  zuletzt geändert am 17.12.2024 (`368280ec`). Der Text im Kopf von
  `triposg_transformer.py` ist nach Normalisierung der Leerzeichen wortgleich.
- **FlashVDM:** https://raw.githubusercontent.com/Tencent/FlashVDM/main/LICENSE
  (das Repository heißt jetzt `Tencent-Hunyuan/FlashVDM`), zuletzt geändert am
  30.07.2025 (`c0c0ceac`). Unterschied zur Kopie in `triposg/LICENSE`: Die
  Neufassung definiert Tencent als Unternehmensgruppe und erklärt die bisher
  genannte THL A29 Limited für gelöscht. Sonst wortgleich.

## 2 Bedingungen je Bestandteil

### 2.1 TripoSG-Quelltext, MIT-Anteil (`LICENSE`)

- **Nutzung:** frei, ohne Gewähr.
- **Weitergabe:** Copyright- und Erlaubnisvermerk in jeder Kopie oder jedem
  wesentlichen Teil.
- **Ausgaben:** keine Regel.
- **Gebiet:** keine Beschränkung.
- `LICENSE` sagt nicht, welche Dateien sie deckt. `NOTICE` und zwei Dateien im
  Baum nennen andere Lizenzen (Abschnitt 3).

### 2.2 HunyuanDiT-Anteil: Tencent Hunyuan Community License Agreement (14.05.2024)

Gilt laut Dateikopf für `triposg_transformer.py` und laut `NOTICE` für den aus
HunyuanDiT abgeleiteten Code.

- **Gebiet:** Territory ist die ganze Welt ohne die EU (§1.l). Die Lizenz wird
  nur für das Territory erteilt (§2). Nutzung, Vervielfältigung, Änderung,
  Verbreitung oder Anzeige der Works, ihres Outputs oder ihrer Ergebnisse
  außerhalb ist ausdrücklich unlizenziert (§5.c). Die Acceptable Use Policy
  verbietet als Nr. 1 die Nutzung außerhalb.
- **Nutzung:** Die Lizenz gilt schon durch bloße Nutzung als angenommen
  (Präambel). Pflicht zur Einhaltung der Gesetze einschließlich Handelsrecht
  und der Acceptable Use Policy (Anhang A, 20 Verbote, u. a. Nr. 14
  automatisierte Entscheidungen mit hohem Risiko einschließlich
  Sicherheitsbauteilen von Produkten, Nr. 19 militärische Zwecke). Tencent darf
  die Policy einseitig ändern; ihr Änderungsdatum ist im Text ein Platzhalter.
  **Nutzerschwelle:** Hatten die Produkte des Lizenznehmers am
  Veröffentlichungsdatum der Version im Vormonat mehr als 100 Mio. monatlich
  aktive Nutzer, braucht er eine eigene Lizenz von Tencent (§4). Eine
  Schutzrechtsklage gegen Tencent beendet die Lizenz; Freistellung Tencents von
  Ansprüchen Dritter (§6.c). Kündigung bei Verstoß mit Löschpflicht (§8.b).
  Recht und Gerichtsstand Hongkong (§9).
- **Weitergabe (§3):** nur im Territory. Jeder Empfänger der Works oder der
  Produkte und Dienste, die sie nutzen, bekommt eine Kopie der Lizenz (§3.a).
  Geänderte Dateien tragen einen deutlichen Änderungsvermerk (§3.b). Außer bei
  einem Hosted Service liegt eine Notice-Textdatei mit vorgegebenem Satz bei
  (§3.d); dieser Satz steht wörtlich im TripoSG-`NOTICE`. Eigene Bedingungen für
  eigene Änderungen sind erlaubt, solange der Rest der Lizenz samt Gebiet
  eingehalten wird. Die Beschränkungen aus §5.a und §5.b müssen als
  durchsetzbare Bestimmung in jede Vereinbarung über Nutzung oder Verbreitung,
  und Folgenutzer sind darauf hinzuweisen (§5.a). Empfohlen, nicht Pflicht:
  ein Erfahrungsbericht und die Kennzeichnung Powered by Tencent Hunyuan
  (§3.c). Wer die Works als Teil eines integrierten Endprodukts von einem
  Lizenznehmer erhält, für den gilt §3 nicht (letzter Satz von §3). Keine
  Markenlizenz außer für §3.c (§6.b).
- **Ausgaben:** Tencent beansprucht keine Rechte an Outputs; Nutzer sind allein
  verantwortlich (§6.d). Outputs dürfen kein anderes großes Sprachmodell
  verbessern (§5.b). Outputs dürfen außerhalb des Territory weder genutzt noch
  verbreitet noch angezeigt werden (§5.c). Policy Nr. 12: maschinell erzeugte
  Inhalte nur mit ausdrücklicher, deutlicher Kennzeichnung öffentlich machen;
  Nr. 4: Output nicht zum Schaden weiterverbreiten. Outputs allein sind keine
  Model Derivatives (§1.g).
- **Reichweite der Definitionen:** Tencent Hunyuan umfasst Gewichte, Modell-,
  Inferenz-, Trainings- und Feintuning-Code (§1.j). Model Derivatives umfassen
  Änderungen, darauf beruhende Werke sowie Modelle, die durch Übertragung von
  Gewichten, Operationen oder Output entstehen (§1.g).

### 2.3 FlashVDM-Anteil: Tencent Hunyuan FlashVDM Community License Agreement (19.03.2025), `triposg/LICENSE`

Aufbau wie 2.2, mit diesen Abweichungen:

- **Gebiet:** Schon der Kopf nimmt EU, Vereinigtes Königreich und Südkorea aus
  (dort mit Tippfehler beim Ländernamen). §1.l definiert das Territory als
  weltweit, "excluding the territory of the European Union, United Kingdom and
  South Korea". §2, §3, §5.c und Policy Nr. 1 wie in 2.2.
- **Nutzerschwelle:** mehr als 1 Mio. monatlich aktive Nutzer am
  Veröffentlichungsdatum der Version (§4). Anfrage an hunyuan3d@tencent.com mit
  Firmenname, Branche und Einsatzzweck.
- **Ausgaben:** Works und Output dürfen kein anderes KI-Modell verbessern
  (§5.b) — weiter als bei HunyuanDiT, das nur große Sprachmodelle nennt. §6.d,
  Policy Nr. 4 und Nr. 12 wie in 2.2. Stand der Policy laut Text: 05.11.2024.
- **Weitergabe:** wie 2.2, mit dem Notice-Satz für FlashVDM; auch er steht
  wörtlich im TripoSG-`NOTICE`.
- **Ungereimtheit an der Quelle:** Im FlashVDM-Repository nennt der Kopf von
  `flashvdm_decoder/volume_decoders.py` eine Tencent Hunyuan Non-Commercial
  License, das `LICENSE` des Repositorys dagegen die Community License.

### 2.4 TripoSG-Gewichte (`VAST-AI/TripoSG` @ `2c1c516d`)

- Die Lizenz steht nur als `license: mit` im Kopf der Modellkarte. Das
  Repository hat weder Lizenztext noch Copyright-Vermerk noch `NOTICE`. Die
  Karte erwähnt weder HunyuanDiT noch FlashVDM.
- Inhalt: `transformer/` (5,76 GB), `vae/` (0,97 GB), `image_encoder_dinov2/`
  (1,22 GB) und Konfigurationen. Solidon holt das ganze Repository
  (`snapshot_download` im Gewichtsabruf, `comfy_setup.py` um Zeile 1028).
- **DINOv2-Anteil:** byte-gleich mit `facebook/dinov2-large` (Apache-2.0).
  Apache-2.0 verlangt bei Weitergabe eine Lizenzkopie, den Erhalt der Vermerke
  und Hinweise auf Änderungen; für Ausgaben und Gebiet gilt nichts. Das
  TripoSG-Repository legt den Apache-Text nicht bei.
- **Nutzung, Ausgaben, Gebiet** laut MIT: frei, keine Regel. Ob die Gewichte des
  Transformers Model Derivatives im Sinne von 2.2 oder 2.3 sind, sagt keine
  Datei (offene Fragen 4 und 8).

### 2.5 BiRefNet (`Comfy-Org/BiRefNet` @ `5a1bd8ae`, Original `ZhengPeng7/BiRefNet`)

- Die geladene Datei ist byte-gleich mit `model.safetensors` von
  `ZhengPeng7/BiRefNet` (SHA-256 `9ab37426…`, 444 473 596 Byte). Comfy-Org
  bezeichnet sie als neu verpackt und gibt MIT an, legt aber keinen Lizenztext
  bei.
- **Nutzung:** frei (MIT). **Weitergabe:** Copyright-Vermerk (2024 ZhengPeng)
  und Erlaubnisvermerk beilegen. **Ausgaben, Gebiet:** keine Regel.
- **Trainingsdaten:** Die Modellkarte nennt für das DIS-Modell DIS-TR. Die
  Modelltabelle auf GitHub nennt für die Modelle zum allgemeinen Gebrauch
  zusätzlich DUTS, HRSOD, UHRSD, HRS10K, P3M-10k und einen Personendatensatz.
  Welcher Tabelleneintrag dieser Datei entspricht, sagt die Karte nicht. Die
  DIS5K Terms of Use erlauben nur nicht-kommerzielle Forschung und Lehre,
  verbieten die kommerzielle Nutzung auch nach Bearbeitung und jede Weitergabe
  der Daten.
- Nicht geladen: `background_removal/lucida.safetensors` (das zweite
  `base_model` der Karte, `egeorcun/lucida`).

### 2.6 SDXL Base 1.0 (`stabilityai/stable-diffusion-xl-base-1.0` @ `46216598`)

- **Gebiet:** weltweite Urheber- und Patentlizenz (Abschnitt II), keine
  Gebietsbeschränkung.
- **Nutzung:** nur rechtmäßig und nicht für die elf Verwendungen aus Anhang A
  (u. a. Schaden für Minderjährige, Verleumdung, schädliche Falschinformation,
  medizinische Beratung, Justiz-, Polizei- und Migrationszwecke,
  vollautomatische Entscheidungen mit Rechtswirkung). Wer Nutzer hat, muss sie
  auf Absatz 5 verpflichten. Der Lizenzgeber behält sich vor, eine
  lizenzwidrige Nutzung auch aus der Ferne einzuschränken (Abschnitt IV).
- **Weitergabe (Abschnitt III):** Anhang A als durchsetzbare Bestimmung in jede
  Vereinbarung über Nutzung oder Verbreitung, Hinweis an Folgenutzer,
  Lizenzkopie, Änderungsvermerk an geänderten Dateien, Erhalt der Vermerke.
  Gilt nicht für das Begleitmaterial (Complementary Material).
- **Ausgaben:** Der Lizenzgeber beansprucht keine Rechte am Output; der Nutzer
  ist verantwortlich, und keine Verwendung des Outputs darf der Lizenz
  widersprechen (Abschnitt III, Absatz zum Output).
- **Modellkarte:** nennt als vorgesehene Verwendung allein die Forschung. Die
  Präambel sagt, die Lizenz richte sich nach der Modellkarte. Trainingsdaten
  sind ausdrücklich nicht mitlizenziert (Definition Data).
- An dieser Revision ist das Repository nicht zugangsbeschränkt (`gated: false`).

## 3 Was `NOTICE` über HunyuanDiT und FlashVDM sagt, und welche Dateien betroffen sind

`NOTICE` am Commit nennt vier Fremdanteile: RMBG-1.4 (BRIA AI, Lizenzkennung
`bria-rmbg-1.4`), Code aus Diffusers (Apache-2.0), aus HunyuanDiT abgeleiteten
Code mit dem vorgeschriebenen Hunyuan-Notice-Satz und aus FlashVDM abgeleiteten
Code mit dem vorgeschriebenen FlashVDM-Notice-Satz. Weder `NOTICE` noch
`LICENSE` sagen, welche Dateien betroffen sind und ob MIT für diese Anteile
zurücktritt. Der FlashVDM-Satz, die Datei `triposg/LICENSE` und die Übersetzung
der chinesischen Kommentare in `extract_near_surface_volume_fn` kamen mit
Commit `2039b464` (08.04.2025, Meldung zur Aktualisierung des Lizenzhinweises);
davor nannte `NOTICE` nur HunyuanDiT.

| Datei | Kennzeichnung im Repository | Zeilenabgleich* | Im Solidon-Weg |
|---|---|---|---|
| `triposg/models/transformers/triposg_transformer.py` | Kopf: beruht auf Tencent HunyuanDiT, Teile kopiert oder angepasst; vollständiger Lizenztext; Docstrings nennen `HunyuanDiT2DModel` | 197 von 352 Zeilen gleich mit Diffusers `v0.30.3`, `models/transformers/hunyuan_transformer_2d.py` (Apache-2.0, Copyright der HunyuanDiT-Autoren, von Qixun Wang und dem Hugging-Face-Team); 7 von 352 gleich mit Tencents `hydit/modules/models.py` | **läuft in jedem Auftrag**: `TripoSGDiTModel` ist der Transformer der Pipeline |
| `triposg/inference_utils.py` | kein Dateikopf; nur über `NOTICE` und `triposg/LICENSE` | `flash_extract_geometry` 77/100, `extract_near_surface_volume_fn` 34/49, `generate_dense_grid_points_2` 9/10 gleich mit FlashVDM `flashvdm_decoder/volume_decoders.py`; `hierarchical_extract_geometry` 3/36 (nur Behandlung der Grenzen) | Modul wird geladen; Solidon ruft mit `use_flash_decoder=False` (`nodes.py:261`) den hierarchischen Pfad, nicht `flash_extract_geometry`. **Solidon ändert die Datei** (`patch_sources`, `_fix_devices`) |
| `triposg/models/attention_processor.py` | Kommentar zum FlashVDM-Top-k; ein Docstring nennt HunyuanDiT | `FlashTripoSGAttnProcessor2_0`: 10 Zeilen gleich mit FlashVDM `attention_processors.py` (Top-k-Auswahl) | nur im Flash-Pfad, im Solidon-Weg nicht aktiv |
| `triposg/models/autoencoders/autoencoder_kl_triposg.py` | keine; `set_flash_decoder` bindet den Flash-Prozessor ein | — | **Solidon ändert die Datei** (Typumwandlung, Gerät) |
| `triposg/LICENSE` | FlashVDM-Lizenztext im Paketordner | — | wird mitkopiert, weil Solidon den ganzen Ordner übernimmt |
| `scripts/briarmbg.py` | Kopf: Code aus briaai/RMBG-1.4, Copyright briaai | — | **nicht** übernommen; die RMBG-Gewichte lädt Solidon auch nicht |

\* Mechanisch: Zeilen über 25 Zeichen ohne Einrückung, Gleichheit als
Zeichenkette, gegen FlashVDM `main` und das Diffusers-Tag `v0.30.3` (die
Version, die `model_index.json` der Gewichte nennt). Ein Indiz für die
Herkunft, kein Nachweis.

Was Solidon übernimmt (`comfy_setup.fetch_triposg`, ab Zeile 659): den ganzen
Ordner `triposg/` (damit `triposg_transformer.py` mit Lizenzkopf und
`triposg/LICENSE`) sowie `LICENSE` und `NOTICE` als `LICENSE-TripoSG` und
`NOTICE-TripoSG`. Die Änderungen an `inference_utils.py` und
`autoencoder_kl_triposg.py` tragen Kommentare an der geänderten Stelle; einen
Vermerk im Dateikopf gibt es nicht.

## 4 Offene Fragen

An VAST-AI-Research:

1. Woher stammt der HunyuanDiT-Anteil in `triposg_transformer.py`: aus Tencents
   Repository oder aus dem Diffusers-Port unter Apache-2.0? Gilt die
   Hunyuan-Lizenz nach VASTs Verständnis für die ganze Datei oder für bestimmte
   Teile?
2. Gilt `triposg/LICENSE` (FlashVDM) für den ganzen Ordner `triposg/` oder nur
   für die FlashVDM-Anteile, und welche Funktionen und Klassen sind das?
3. Ist der hierarchische Pfad (`hierarchical_extract_geometry`,
   `TripoSGAttnProcessor2_0`) frei von FlashVDM-Code?
4. Sieht VAST die Gewichte unter `VAST-AI/TripoSG` als Model Derivatives von
   HunyuanDiT oder FlashVDM, oder gilt für sie allein MIT? Gilt die
   Gebietsbeschränkung damit für Gewichte und erzeugte Netze?
5. Dürfen Nutzer in EU, Vereinigtem Königreich und Südkorea diesen Commit mit
   `use_flash_decoder=False` ausführen und die Netze gewerblich verwenden? Gibt
   es sonst eine Lizenz von VAST oder Tripo für diese Gebiete?
6. Legt VAST dem Gewichts-Repository eine Lizenzdatei bei, die den
   DINOv2-Anteil (Apache-2.0) ausweist?

An eine Kanzlei:

7. Ist die Ausführung von `triposg_transformer.py` durch Kunden in der EU
   unlizenziert im Sinne von §5.c der Hunyuan-Lizenz, und was folgt daraus für
   Solidon als Anbieter der Einrichtung?
8. Fällt das Anzeigen, Bearbeiten, Drucken oder Verkaufen erzeugter Netze in der
   EU unter das Output-Verbot außerhalb des Territory (§5.c), wenn die Netze aus
   einem Hunyuan-lizenzierten Transformer stammen?
9. Ist Solidon ein Produkt, das Tencent Hunyuan Works nutzt (§3.a), obwohl der
   Quelltext beim Kunden direkt von GitHub kommt — mit der Pflicht zur
   Lizenzkopie und zur Aufnahme von §5.a und §5.b in Solidons eigene
   Bedingungen? Greift für Solidons Kunden die Ausnahme für integrierte
   Endprodukte (§3, letzter Satz)?
10. Sind die Änderungen, die Solidons Einrichtung beim Kunden vornimmt,
    geänderte Dateien im Sinne von §3.b? Wer ist der Ändernde, und genügt ein
    Kommentar an der geänderten Stelle als deutlicher Vermerk?
11. Welcher Text bindet, wenn ein Anteil, den VAST unter die Hunyuan-Lizenz
    stellt, laut Zeilenabgleich überwiegend aus einer Apache-2.0-Quelle stammt
    (Frage 1)?
12. Wirken die DIS5K-Bedingungen (nur nicht-kommerziell) auf die als MIT
    gekennzeichneten BiRefNet-Gewichte, wenn Solidon-Kunden sie gewerblich
    nutzen?
13. Muss Solidon den MIT-Vermerk von BiRefNet und den Apache-Text von DINOv2 dem
    Kunden zeigen, obwohl es die Gewichte nicht selbst verbreitet, sondern der
    Kunde sie über Solidons Einrichtung lädt?
14. SDXL: Welches Gewicht hat die Modellkarte (Verwendung allein für
    Forschung) neben einer Lizenz ohne diese Beschränkung? Muss Solidon Anhang A
    in die eigenen Bedingungen aufnehmen, obwohl es das Modell nicht weitergibt?
15. Genügt Solidons KI-Hinweis der Kennzeichnung aus Policy Nr. 12 (Hunyuan und
    FlashVDM), wenn Kunden erzeugte Modelle öffentlich teilen?
16. Welche Fassung der FlashVDM-Lizenz gilt für den TripoSG-Commit (Kopie mit
    THL A29 Limited oder Neufassung vom 30.07.2025), und was bedeutet der Kopf
    von `volume_decoders.py`, der eine Non-Commercial-Lizenz nennt? (Notfalls an
    Tencent, hunyuan3d@tencent.com.)

## 5 Entwurf einer Anfrage an VAST-AI-Research (nicht gesendet)

> **Subject:** License scope of HunyuanDiT/FlashVDM-derived parts in TripoSG
> (commit fc5c409, weights 2c1c516)
>
> Hello VAST-AI-Research team,
>
> we develop Solidon, a desktop application for designing 3D-printable parts.
> On the user's request it installs TripoSG locally into ComfyUI, pinned to
> commit fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c and to VAST-AI/TripoSG at
> revision 2c1c516d22d58db486a058d98d31bb6177344e06. We call the pipeline with
> use_flash_decoder=False. We are based in the European Union, and so are many
> of our users.
>
> The repository LICENSE is MIT, while NOTICE, triposg/LICENSE and the header
> of triposg_transformer.py refer to the Tencent Hunyuan Community License and
> the Tencent Hunyuan FlashVDM Community License, both of which exclude the EU
> from their territory. Could you clarify the following?
>
> 1. Was triposg_transformer.py derived from Tencent's HunyuanDiT repository or
>    from the Apache-2.0 implementation in diffusers (hunyuan_transformer_2d.py)?
>    Does the Hunyuan license cover the whole file or only specific parts?
> 2. Does triposg/LICENSE apply to the whole triposg package, or only to the
>    FlashVDM-derived code (for example flash_extract_geometry,
>    extract_near_surface_volume_fn, FlashTripoSGAttnProcessor2_0)?
> 3. Is the hierarchical path (hierarchical_extract_geometry with
>    TripoSGAttnProcessor2_0) free of FlashVDM-derived code?
> 4. Do you consider the weights on Hugging Face (model card: MIT) to be Model
>    Derivatives under either Tencent license, or are they licensed under MIT
>    alone?
> 5. May users in the EU, the UK and South Korea run this commit with
>    use_flash_decoder=False and use the resulting meshes, including
>    commercially? If not, is there a license from VAST or Tripo that covers
>    these territories?
> 6. The weights repository contains facebook/dinov2-large unchanged
>    (Apache-2.0) but no license file. Could you add one or confirm how that
>    part is licensed?
>
> A short written answer or a pointer to existing documentation would let us
> describe the licensing correctly to our users.
>
> Best regards,
> Robert Schneider, RS Digital

## Beifunde im Repository (nicht geändert, der Auftrag war nur lesend)

- `app/core/backends/data/comfyui/ComfyUI-TripoSG-Solidon/nodes.py:1-6` und
  `__init__.py:3`: TripoSG stehe unter MIT, Code wie Gewichte, der Knoten sei
  ohne Lizenzhaken. Derselbe Knoten importiert `TripoSGPipeline` und damit
  `triposg_transformer.py`, dessen Kopf die Hunyuan-Lizenz trägt.
- `app/core/knowledge/data/licences.toml:53`: TripoSG als MIT für Quelltext und
  Gewichte, ohne Vorbehalt (im Register bei RM-003 schon vermerkt).
- `app/core/backends/comfy_setup.py:91-92`: Der Kommentar zum Bildmodell
  grenzt SDXL gegen Hunyuan ab, dessen Lizenz die EU ausnehme. Der Quelltext,
  den dieselbe Einrichtung holt, enthält eine Datei unter genau dieser Lizenz.
- README und Handbuch sagen, die Kette werde geprüft, und widersprechen dem
  Befund nicht.
