# Faktenkarten für `konzept-erzeugen-agent-oberflaeche-2026-08.md`

Recherchiert am 19.08.2026. Jede Karte trägt ihre Quelle. Was nicht gefunden
wurde, steht unter „Nicht belegbar“ — das ist kein Freibrief, es plausibel
zu ergänzen, sondern der Grund, es im Konzept offen zu lassen.

## lokale-3d-modelle

_Lokal laufende Bild-zu-3D- und Text-zu-3D-Modelle und ihre Lizenzen (Stand 19.08.2026)_

- **ComfyUI** — Aktuelle Fassung ist v0.33.1, veroeffentlicht am 13.08.2026; davor v0.32.0 (11.08.), v0.31.0 (07.08.), v0.30.2 (05.08.) — die Freigaben kommen derzeit im Abstand von wenigen Tagen.
  · Stand: Changelog abgerufen 19.08.2026, letzter Eintrag 13.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Zwei unabhaengige Anbieterquellen (Doku und GitHub-Releases) nennen dieselbe Fassung und denselben Tag. Ob zwischen dem 13. und dem 19.08. noch eine Fassung erschien, konnte ich nicht pruefen — die GitHub-API war zum Schluss ratenbegrenzt (403).
  · https://docs.comfy.org/changelog
  · https://github.com/comfyanonymous/ComfyUI/releases
- **ComfyUI** — ComfyUI steht unter der GNU General Public License Version 3 vom 29. Juni 2007.
  · Stand: LICENSE im master-Zweig, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Fuer Solidon einschlaegig wegen AGENTS.md Regel 15 (keine GPL-Abhaengigkeit). Der Aufruf ueber HTTP aus einem eigenen Prozess ist derselbe Fall wie OpenSCAD und Slicer — mitliefern oder linken waere er nicht.
  · https://raw.githubusercontent.com/comfyanonymous/ComfyUI/master/LICENSE
- **ComfyUI** — Das Repositorium liegt heute unter der Organisation Comfy-Org: github.com/comfyanonymous/ComfyUI leitet auf Comfy-Org/ComfyUI um (full_name in der API ist Comfy-Org/ComfyUI, 128.423 Sterne, letzter Push 19.08.2026 06:59 UTC).
  · Stand: GitHub-API abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Fest verdrahtete Klon-URLs in Solidons Unterlagen funktionieren weiter, zeigen aber auf den alten Namen.
  · https://api.github.com/repos/comfyanonymous/ComfyUI
- **ComfyUI** — Mit v0.32.0 (11.08.2026) ist PyTorch 2.7 die unterste unterstuetzte Fassung.
  · Stand: 11.08.2026 · Sicherheit: belegt
  · Anmerkung: Aeltere Nutzerinstallationen mit PyTorch < 2.7 fallen damit heraus. Das trifft Solidon nicht selbst, aber die Anleitung fuer Nutzer, die ComfyUI danebenstellen.
  · https://docs.comfy.org/changelog
  · https://github.com/comfyanonymous/ComfyUI/releases/tag/v0.32.0
- **ComfyUI HTTP-API** — Die Anbieterdoku listet rund 25 Routen, darunter POST/GET /prompt, /queue, /history, /interrupt, /object_info, /upload/image, /upload/mask, /view sowie den WebSocket /ws mit den Nachrichtentypen status, execution_start, executing, progress, executed, execution_cached.
  · Stand: Doku abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Genau die Routen, an denen Solidons Anbindung haengt. Es gibt eine versionierte Route /v2/userdata — ein Hinweis darauf, dass Versionierung punktuell und nicht global gemacht wird.
  · https://docs.comfy.org/development/comfyui-server/comms_routes
- **ComfyUI HTTP-API** — Die Anbieterdoku gibt keine ausdrueckliche Stabilitaets- oder Versionszusage fuer die HTTP-API und nennt keine Verfallsfristen fuer Routen.
  · Stand: Doku abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Fuer Solidon heisst das: die API ist faktisch stabil, aber nicht zugesagt. Eine Fassungspruefung beim Verbinden ist billiger als ein Fehlerbild beim Nutzer.
  · https://docs.comfy.org/development/comfyui-server/comms_routes
- **ComfyUI / Hunyuan3D 2.0** — ComfyUI unterstuetzt Hunyuan3D-2 und Hunyuan3D-2mv nativ, aber nur die Geometrie: „ComfyUI now natively supports Hunyuan3D-2mv, but does not yet support texture and material generation." Dateien hunyuan3d-dit-v2.safetensors und hunyuan3d-dit-v2-mv.safetensors, 6 GB VRAM nur fuer die Form.
  · Stand: Doku-Seite, juengstes genanntes Modell 18.03.2025 · Sicherheit: belegt
  · Anmerkung: Knoten sind Hunyuan3Dv2Conditioning und Hunyuan3Dv2ConditioningMultiView. Ohne Textur ist das fuer Solidon brauchbar — ein Druckteil braucht die Form, nicht die PBR-Karten.
  · https://docs.comfy.org/tutorials/3d/hunyuan3D-2
- **ComfyUI / Hunyuan3D 2.1** — ComfyUI bringt eine eingebaute Vorlage „Hunyuan 3D 2.1" mit; das Modell ist ein Sammel-Checkpoint hunyuan_3d_v2.1.safetensors, der Diffusionsmodell, Textkodierer und VAE buendelt.
  · Stand: comfy.org-Modellseite und AMD-ROCm-Doku Fassung docs-26.04, datiert 28.04.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Wichtig fuer Solidon: fuer Hunyuan3D 2.1 ist keine Knotensammlung mehr noetig. Eine eigene Doku-Seite unter docs.comfy.org/tutorials/3d/hunyuan3d-2-1 gibt es nicht (404) — die Anbieterbelege sind die Modellseite und die ROCm-Doku.
  · https://comfy.org/p/supported-models/hunyuan-3d-v2-1/
  · https://rocm.docs.amd.com/projects/comfyui/en/docs-26.04/how-to/hunyuan3d-workflow.html
- **Hunyuan3D 2.1 (tencent/Hunyuan3D-2.1)** — Die Lizenz heisst „TENCENT HUNYUAN 3D 2.1 COMMUNITY LICENSE AGREEMENT"; „Territory" ist definiert als „worldwide territory, excluding the territory of the European Union, United Kingdom and South Korea", und die Datei traegt in Grossbuchstaben den Satz „THIS LICENSE AGREEMENT DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA".
  · Stand: LICENSE im main-Zweig, Vertragsdatum 13.06.2025, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Der Gebietsausschluss besteht also unveraendert fort. Solidon wird in Deutschland entwickelt und in der EU vertrieben — es gibt keine Lesart, in der die Community License hier eine Nutzungserlaubnis erteilt.
  · https://raw.githubusercontent.com/Tencent-Hunyuan/Hunyuan3D-2.1/main/LICENSE
  · https://huggingface.co/tencent/Hunyuan3D-2.1/blob/main/LICENSE
- **Hunyuan3D 2.1** — Kommerzielle Nutzung ist innerhalb des Territoriums grundsaetzlich erlaubt, endet aber an einer Schwelle: uebersteigen die monatlich aktiven Nutzer aller Produkte im Vormonat 1 Million, ist eine schriftliche Genehmigung von Tencent noetig; ohne sie bestehen keine Rechte aus dem Vertrag.
  · Stand: LICENSE, Vertragsdatum 13.06.2025 · Sicherheit: belegt
  · Anmerkung: Die 1-Million-Schwelle ist fuer Solidon praktisch bedeutungslos; der Gebietsausschluss ist der harte Punkt.
  · https://raw.githubusercontent.com/Tencent-Hunyuan/Hunyuan3D-2.1/main/LICENSE
- **Hunyuan3D 2.0 (tencent/Hunyuan3D-2)** — Auch die Vorgaengerlizenz „TENCENT HUNYUAN 3D 2.0 COMMUNITY LICENSE AGREEMENT" (Datum 21.01.2025) definiert Territory als „worldwide territory, excluding the territory of the European Union, United Kingdom and South Korea" und traegt denselben Grossbuchstaben-Satz sowie dieselbe 1-Million-MAU-Schwelle.
  · Stand: LICENSE im main-Zweig, Vertragsdatum 21.01.2025, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Damit hilft der Rueckgriff auf 2.0 nicht: es ist derselbe Ausschluss, nur ein halbes Jahr aelter.
  · https://raw.githubusercontent.com/Tencent-Hunyuan/Hunyuan3D-2/main/LICENSE
- **Hunyuan3D-Part (P3-SAM, X-Part)** — Die „TENCENT HUNYUAN 3D-PART COMMUNITY LICENSE AGREEMENT" mit Freigabedatum 23.09.2025 fuehrt denselben Gebietsausschluss: Territory ist „Worldwide territory, excluding the territory of the European Union, United Kingdom and South Korea", dazu derselbe Grossbuchstaben-Satz und dieselbe 1-Million-MAU-Schwelle.
  · Stand: LICENSE im main-Zweig, Vertragsdatum 23.09.2025, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Belegt, dass Tencent den Ausschluss auch bei neueren 3D-Veroeffentlichungen fortschreibt — er ist kein Ueberbleibsel aus 2.0. Enthaelt P3-SAM (08.09.2025) und X-Part (10.09.2025); die veroeffentlichte X-Part-Fassung ist laut Modellkarte eine leichte Variante, die volle liegt in Hunyuan3D-Studio.
  · https://raw.githubusercontent.com/Tencent-Hunyuan/Hunyuan3D-Part/main/LICENSE
- **Hunyuan3D 2.1 auf Hugging Face** — Die Modellkarte tencent/Hunyuan3D-2.1 traegt im YAML-Kopf `license: other`, `license_name: tencent-hunyuan-community` und `extra_gated_eu_disallowed: true`.
  · Stand: README.md im main-Zweig, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Das ist kein blosser Hinweis, sondern eine wirksame Sperre — siehe die naechste Karte.
  · https://huggingface.co/tencent/Hunyuan3D-2.1/raw/main/README.md
- **Hugging Face extra_gated_eu_disallowed** — Die Hub-Doku beschreibt das Feld woertlich: „For gated models, you can add an additional layer of access control to specifically restrict users from European Union countries. This is useful if your model's license or terms of use prohibit its distribution in the EU." und ergaenzt: „The system identifies a user's location based on their IP address."
  · Stand: Hub-Doku abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Fuer Solidon der praktisch entscheidende Befund: ein Nutzer in Deutschland kann die Hunyuan3D-Gewichte ueber Hugging Face gar nicht erst herunterladen. Ein Solidon-Graph, der sie voraussetzt, scheitert beim EU-Nutzer schon an der Beschaffung — nicht erst an der Lizenz. Die Doku vermerkt zugleich, dass die Sperre nur greift, wenn das Modell ueberhaupt gated ist.
  · https://huggingface.co/docs/hub/models-gated
- **Hunyuan3D 2.1** — Der Anbieter nennt als Bedarf 10 GB VRAM allein fuer die Formerzeugung, 21 GB allein fuer die Textur und 29 GB fuer beides zusammen. Die Modelle sind Hunyuan3D-Shape-v2-1 (3,3 Mrd. Parameter) und Hunyuan3D-Paint-v2-1 (2 Mrd.), beide vom 14.06.2025.
  · Stand: README des Repositoriums, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die 29 GB fuer den vollen Weg sind mit ueblicher Endkundenhardware (12–16 GB) nicht zu machen. Nur-Form mit 10 GB ist realistisch — und genau das, was ein Druckteil braucht.
  · https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- **Hunyuan3D 2.1 (Repositorium)** — Tencent-Hunyuan/Hunyuan3D-2.1 wurde zuletzt am 17.10.2025 bespielt (pushed_at), ist nicht archiviert, hat 3.865 Sterne und 153 offene Vorgaenge.
  · Stand: GitHub-API abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Zehn Monate ohne Push. Die juengste Meldung im README ist HunyuanWorld-1.0 vom 26.07.2025. Der offene Hunyuan3D-Zweig bei Tencent ist faktisch eingefroren, die Entwicklung ist in den gehosteten Dienst gewandert.
  · https://api.github.com/repos/Tencent-Hunyuan/Hunyuan3D-2.1
- **Hunyuan3D-Omni** — Modellkarte mit `license: other`, `license_name: tencent-hunyuan-community`, `extra_gated_eu_disallowed: true`; 3,3 Mrd. Parameter, Freigabe 25.09.2025, und woertlich „It takes 10 GB VRAM for generation".
  · Stand: README.md im main-Zweig, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Steuerbare Erzeugung aus Punktwolken, Voxeln, Huellquadern und Skelettposen — inhaltlich fuer Solidon interessant, lizenzrechtlich derselbe Ausschluss wie 2.1.
  · https://huggingface.co/tencent/Hunyuan3D-Omni/raw/main/README.md
- **Hunyuan3D 3.0** — Hunyuan3D 3.0 ist ein gehosteter Dienst, keine offenen Gewichte: Tencent kuendigte am 26.11.2025 den globalen Start der Hunyuan-3D-Engine an, mit Weboberflaeche (20 freie Erzeugungen taeglich) und Hunyuan-3D-Model-API ueber Tencent Cloud (200 freie Guthaben).
  · Stand: Tencent-Pressemitteilung vom 26.11.2025, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Wichtige Abgrenzung: die neueste Hunyuan3D-Stufe laesst sich nicht lokal fahren. Fuer Solidon, das ohne Netz und ohne Konto benutzbar bleiben soll, faellt sie damit ohnehin aus. Ein Repositorium Tencent-Hunyuan/Hunyuan3D-3.0 war nicht auffindbar.
  · http://www.tencent.com/tencent-announces-global-launch-of-hunyuan-3d-engine-to-empower-creators-with-advanced-creation-tools/
- **Microsoft TRELLIS (erste Fassung)** — MIT-Lizenz (`license: mit` im YAML-Kopf von microsoft/TRELLIS-image-large, keine extra_gated-Felder). Anbieter nennt „An NVIDIA GPU with at least 16GB of memory is necessary"; Varianten: TRELLIS-image-large (1,2 Mrd.) sowie die Text-zu-3D-Modelle TRELLIS-text-base (342 Mio.), -large (1,1 Mrd.) und -xlarge (2,0 Mrd.).
  · Stand: Modellkarte und Repositoriums-README, juengster Eintrag 25.03.2025, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Einzelne Untermodule (diffoctreerast, modifiziertes Flexicubes) behalten eigene Lizenzen — bei einer Lizenzliste nach AGENTS.md-Checkliste einzeln pruefen. Der Anbieter empfiehlt ausdruecklich die bildkonditionierte Fassung; die Text-Modelle seien wegen der Datenlage schwaecher. Dies ist die einzige belegte offene Text-zu-3D-Reihe im Themenfeld.
  · https://huggingface.co/microsoft/TRELLIS-image-large/raw/main/README.md
  · https://github.com/microsoft/TRELLIS
- **Microsoft TRELLIS.2-4B** — MIT-Lizenz (`license: mit`; im README „This model and code are released under the MIT License"). 4 Mrd. Parameter, O-Voxel-Darstellung, texturierte Netze bis 1536³, volle PBR-Materialien einschliesslich Transparenz; rund 3 s bei 512³ bis 60 s bei Hoechstaufloesung.
  · Stand: Modellkarte abgerufen 19.08.2026; Repositorium angelegt 26.11.2025 · Sicherheit: belegt
  · Anmerkung: Der wichtigste Neuzugang seit Solidons letztem Stand: MIT, keinerlei Gebietsausschluss, keine Umsatzschwelle. Damit fuer die EU das, was Hunyuan3D nicht sein kann.
  · https://huggingface.co/microsoft/TRELLIS.2-4B/raw/main/README.md
  · https://api.github.com/repos/microsoft/TRELLIS.2
- **Microsoft TRELLIS.2** — Anbieter nennt „An NVIDIA GPU with at least 24GB of memory is necessary", getestet auf A100 und H100, und „The code is currently tested only on Linux". Das Repositorium microsoft/TRELLIS.2 ist MIT, angelegt 26.11.2025, zuletzt bespielt 10.07.2026, nicht archiviert, 10.701 Sterne.
  · Stand: Modellkarte, Repositoriums-README und GitHub-API, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Kehrseite: 24 GB und Linux-only im Original, Windows wird nicht als unterstuetzt genannt. Der Weg unter Windows fuehrt ueber die Knotensammlung ComfyUI-Trellis2, die Windows-Raeder und fp8 mitbringt. Lebendiges Projekt im Gegensatz zu Hunyuan3D-2.1.
  · https://huggingface.co/microsoft/TRELLIS.2-4B/raw/main/README.md
  · https://github.com/microsoft/TRELLIS.2
  · https://api.github.com/repos/microsoft/TRELLIS.2
- **TencentARC Pixal3D** — MIT-Lizenz: die LICENSE-Datei traegt „MIT License / Copyright (c) 2026 Tencent", die Modellkarte `license: mit` und „This project is released under the MIT License." SIGGRAPH 2026; Papier im April 2026 angenommen, Quelltext im Mai 2026 veroeffentlicht.
  · Stand: LICENSE und Modellkarte abgerufen 19.08.2026; Repositorium angelegt 10.05.2026, zuletzt bespielt 23.06.2026, 2.128 Sterne · Sicherheit: belegt
  · Anmerkung: Bemerkenswert: ein Tencent-Labor (ARC) gibt hier MIT heraus, nicht die Community License mit Gebietsausschluss. Das ist ein anderes Haus als Tencent-Hunyuan — die Lizenzpraxis der beiden ist nicht dieselbe.
  · https://raw.githubusercontent.com/TencentARC/Pixal3D/master/LICENSE
  · https://huggingface.co/TencentARC/Pixal3D/raw/main/README.md
  · https://api.github.com/repos/TencentARC/Pixal3D
- **TencentARC Pixal3D** — Bild-zu-3D mit direkter Pixel-zu-3D-Zuordnung durch Rueckprojektion, erzeugt Geometrie und PBR-Texturen; der main-Zweig baut auf dem Trellis.2-Rueckgrat auf, der paper-Zweig entspricht der SIGGRAPH-Fassung. Die Modellkarte nennt einen „Low-VRAM mode", der Modelle bei Bedarf laedt.
  · Stand: Modellkarte abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Modellkarte nennt keine VRAM-Zahl. Der Pipeline-Tag ist ausschliesslich image-to-3d; Text-zu-3D wird nicht beschrieben.
  · https://huggingface.co/TencentARC/Pixal3D/raw/main/README.md
- **TencentARC Pixal3D** — Die Modellkarte traegt trotz MIT-Lizenz das Feld `extra_gated_eu_disallowed: true`.
  · Stand: README.md im main-Zweig, abgerufen 19.08.2026 · Sicherheit: unsicher
  · Anmerkung: Widerspruch, den ich nicht aufloesen konnte: MIT erlaubt die Weitergabe weltweit, das Feld sperrt EU-Nutzer per IP. Die Hub-Doku sagt, die Sperre greift nur bei `gated: true`; im abgerufenen YAML-Kopf stand kein `gated`-Feld. Ob der Download aus der EU tatsaechlich blockiert wird, habe ich nicht praktisch geprueft — vor einer Entscheidung in Solidon nachmessen.
  · https://huggingface.co/TencentARC/Pixal3D/raw/main/README.md
  · https://huggingface.co/docs/hub/models-gated
- **Comfy-Org/Pixal3D** — Es gibt ein von Comfy-Org umgepacktes Modellablagefach fuer Pixal3D (pixal3d_bf16.safetensors, pixal3d_int8_convrot.safetensors, dino_v3_L_naf_fp32.safetensors, trellis_2_shape_vae_bf16.safetensors, trellis_2_texture_vae_bf16.safetensors), Lizenz mit, ausdruecklich „Repackaged model files for ComfyUI" und als „work in progress" bezeichnet.
  · Stand: Hugging-Face-Seite abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Starkes Anzeichen, dass native Pixal3D-Unterstuetzung in ComfyUI in Arbeit ist. Im Anbieter-Changelog bis v0.33.1 ist Pixal3D noch nicht als Kernunterstuetzung genannt.
  · https://huggingface.co/Comfy-Org/Pixal3D
- **Step1X-3D (stepfun-ai)** — Apache License 2.0 — die LICENSE-Datei ist der volle Apache-2.0-Text („Apache License Version 2.0, January 2004"), die Modellkarte fuehrt `apache-2.0`, GitHub meldet spdx_id Apache-2.0. Keine Gebietsausschluesse, keine Umsatzschwelle.
  · Stand: LICENSE, Modellkarte und GitHub-API abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Vermutung aus der Aufgabenstellung bestaetigt sich. Auch der 800K-Datensatz steht unter Apache-2.0.
  · https://raw.githubusercontent.com/stepfun-ai/Step1X-3D/main/LICENSE
  · https://huggingface.co/stepfun-ai/Step1X-3D
  · https://api.github.com/repos/stepfun-ai/Step1X-3D
- **Step1X-3D (stepfun-ai)** — Anbieter nennt fuer Step1X-3D-Geometry-1300m plus Step1X-3D-Texture 27 GB GPU-Speicher (152 s bei 50 Schritten), fuer die Label-Variante 29 GB. Modelle: Geometry 1,3 Mrd., Geometry-Label 1,3 Mrd., Texture 3,5 Mrd. Parameter.
  · Stand: Repositoriums-README, juengster Eintrag 26.06.2025, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: 27–29 GB ist fuer Endkundenhardware ausser Reichweite. Lizenzrechtlich sauber, praktisch schwer. Repositorium zuletzt bespielt 08.09.2025, 884 Sterne — keine Eintraege aus 2026.
  · https://github.com/stepfun-ai/Step1X-3D
- **TripoSG (VAST-AI-Research)** — MIT — die LICENSE-Datei traegt „MIT License / Copyright (c) 2025 VAST-AI-Research and contributors.", die Modellkarte VAST-AI/TripoSG fuehrt `license: mit`, GitHub meldet spdx_id MIT. Keine Gebiets- oder Umsatzbeschraenkung.
  · Stand: LICENSE, Modellkarte und GitHub-API abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Vermutung aus der Aufgabenstellung bestaetigt sich, und zwar fuer Quelltext und Gewichte getrennt belegt. Repositorium zuletzt bespielt 18.04.2025, 1.748 Sterne — seit ueber einem Jahr ruhend.
  · https://raw.githubusercontent.com/VAST-AI-Research/TripoSG/main/LICENSE
  · https://huggingface.co/VAST-AI/TripoSG/raw/main/README.md
  · https://api.github.com/repos/VAST-AI-Research/TripoSG
- **Stable Fast 3D / SF3D (Stability AI)** — „STABILITY AI COMMUNITY LICENSE AGREEMENT", Stand „Last Updated: July 5, 2024"; Modellkarte fuehrt `license: other`, `license_name: stabilityai-ai-community`. Kommerzielle Nutzung ist frei bis zu 1.000.000 USD Jahresumsatz; darueber erlischt die Lizenz und es braucht eine Unternehmenslizenz von Stability AI.
  · Stand: LICENSE.md im main-Zweig und Anbieter-Lizenzseite, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Keine Gebietsausschluesse; die Lizenz raeumt weltweite Rechte ein, verlangt aber die Einhaltung von Aussenhandelsrecht. Die Anbieterseite nennt keinen abweichenden Stand — die Fassung vom 05.07.2024 scheint fortzugelten.
  · https://raw.githubusercontent.com/Stability-AI/stable-fast-3d/main/LICENSE.md
  · https://stability.ai/license
- **Stable Fast 3D / SF3D** — Anbieter nennt „The default options takes about 6GB VRAM for a single image input." Repositorium zuletzt bespielt am 22.01.2025, nicht archiviert, 1.788 Sterne.
  · Stand: Repositoriums-README und GitHub-API, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Mit 6 GB das genuegsamste der geprueften Modelle — aber auch das aelteste und seit 19 Monaten unangetastete. Die Umsatzschwelle ist fuer Solidon derzeit unkritisch, bindet den Nutzer aber ebenfalls, wenn er selbst darueber liegt.
  · https://github.com/Stability-AI/stable-fast-3d
  · https://api.github.com/repos/Stability-AI/stable-fast-3d
- **Hi3DGen** — MIT — die LICENSE-Datei traegt „MIT License / Copyright (c) 2025 Bytedance Inc." Keine Gebiets- oder Umsatzbeschraenkung. github.com/Stable-X/Hi3DGen leitet heute auf Stable-X/Stable3DGen um („A Modular Framework for 3D Generation and Beyond [WIP]"), angelegt 26.03.2025, zuletzt bespielt 02.07.2025, 1.275 Sterne.
  · Stand: LICENSE und GitHub-API abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Der Rechteinhaber ist Bytedance, nicht die sichtbare Organisation Stable-X — bei einem Eintrag in Solidons Lizenzliste so fuehren. Umbenannt und seit ueber einem Jahr ruhend; die Knotensammlung Stable-X/ComfyUI-Hi3DGen existiert, ihren Stand habe ich nicht geprueft.
  · https://raw.githubusercontent.com/Stable-X/Hi3DGen/main/LICENSE
  · https://api.github.com/repos/Stable-X/Hi3DGen
- **PartCrafter** — MIT — die LICENSE-Datei traegt „MIT License", Rechteinhaber Yuchen Lin, 2025; GitHub meldet spdx_id MIT. NeurIPS 2025. Repositorium zuletzt bespielt 16.04.2026, 2.470 Sterne, nicht archiviert.
  · Stand: LICENSE und GitHub-API abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Gewichte auf Objektebene (wgsxm/PartCrafter) und Szenenebene (wgsxm/PartCrafter-Scene). Erzeugt mehrere Teile aus einem Bild in einem Durchgang — fuer Solidon interessant, weil das Ergebnis schon zerlegt ankommt. VRAM-Angabe habe ich nicht gefunden.
  · https://raw.githubusercontent.com/wgsxm/PartCrafter/main/LICENSE
  · https://api.github.com/repos/wgsxm/PartCrafter
- **RMBG-2.0 (BRIA AI)** — CC BY-NC 4.0 — nicht-kommerziell. Die Modellkarte sagt: „The model is released under a CC BY-NC 4.0 license for non-commercial use" und „Commercial use is subject to a commercial agreement with BRIA."
  · Stand: Modellkarte abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Vermutung aus der Aufgabenstellung bestaetigt sich. Fuer Solidon disqualifizierend, wenn die Anwendung verkauft wird — und Solidon hat eine Freischaltung mit Schluessel, ist also kommerziell. Ein mitgelieferter Graph, der RMBG-2.0 voraussetzt, verlagert das Problem nur auf den Nutzer.
  · https://huggingface.co/briaai/RMBG-2.0
- **RMBG-2.0 (BRIA AI)** — Das Ablagefach ist gated: der Abruf von huggingface.co/briaai/RMBG-2.0/raw/main/README.md ohne Anmeldung liefert HTTP 401, die Seite verlangt „Log in or Sign Up to review the conditions and access this model content."
  · Stand: Abruf am 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Praktische Folge: ein Solidon-Graph kann die Gewichte nicht unbeaufsichtigt nachladen — der Nutzer braucht ein Hugging-Face-Konto und ein Zugriffsmerkmal. Das widerspricht dem Anspruch, ohne Konto benutzbar zu bleiben.
  · https://huggingface.co/briaai/RMBG-2.0
- **InSPyReNet / transparent-background** — MIT — die LICENSE-Datei traegt „MIT License / Copyright (c) 2022 Taehun Kim"; GitHub meldet spdx_id MIT. Kommerzielle Nutzung erlaubt, keine Gebietsausschluesse.
  · Stand: LICENSE und GitHub-API abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Vermutung aus der Aufgabenstellung bestaetigt sich. Repositorium zuletzt bespielt 08.07.2026, 1.278 Sterne — im Gegensatz zu vielen 3D-Projekten weiter gepflegt. Fuer Solidon der lizenzrechtlich saubere Weg zum Freistellen.
  · https://raw.githubusercontent.com/plemeri/transparent-background/main/LICENSE
  · https://api.github.com/repos/plemeri/transparent-background
- **ComfyUI-RMBG (1038lab)** — Die Knotensammlung existiert weiter; aktuelle Fassung ist V3.1.0 vom 21.07.2026 (Lucida-Modell im BiRefNet-Knoten). Davor V3.0.0 am 01.01.2026. Repositorium zuletzt bespielt 28.07.2026, 2.077 Sterne, nicht archiviert.
  · Stand: update.md und GitHub-API abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Aktiv gepflegt. Umfasst RMBG-2.0, INSPYRENET, BEN, BEN2, BiRefNet, SDMatte, SAM, SAM2, SAM3 und GroundingDINO.
  · https://raw.githubusercontent.com/1038lab/ComfyUI-RMBG/main/update.md
  · https://api.github.com/repos/1038lab/ComfyUI-RMBG
- **ComfyUI-RMBG (1038lab)** — Die Knotensammlung selbst steht unter GPL-3.0 (GitHub meldet „GNU General Public License v3.0"). Das README nennt in den Danksagungen nur die Herkunfts-Ablagefaecher der Modelle, ohne deren Lizenzen zu benennen, und trifft keine Aussage zur kommerziellen Nutzung von RMBG-2.0.
  · Stand: GitHub-API und README abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Zwei Punkte fuer Solidon: GPL-3.0 (wie ComfyUI selbst — nur externer Aufruf, nie mitliefern) und dass die Sammlung die nicht-kommerzielle Bindung von RMBG-2.0 nicht sichtbar macht. Wer sie ueber diese Knoten benutzt, stolpert nicht darueber — er merkt es nur nicht.
  · https://api.github.com/repos/1038lab/ComfyUI-RMBG
  · https://raw.githubusercontent.com/1038lab/ComfyUI-RMBG/main/README.md
- **ComfyUI-Hunyuan3d-2-1 (visualbruno)** — Die Knotensammlung gibt es noch: visualbruno/ComfyUI-Hunyuan3d-2-1, nicht archiviert, 363 Sterne, zuletzt bespielt 30.07.2026. GitHub meldet als Lizenz NOASSERTION — also keine von GitHub erkannte Standardlizenz.
  · Stand: GitHub-API abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: NOASSERTION ist fuer Solidons Lizenzliste ein eigener Befund: der Lizenzstand der Sammlung ist unklar. Getestet laut README unter Windows 11 mit Python 3.12 und Torch >= 2.6.0 + cu126; sie braucht zwei C++-Erweiterungen (custom rasterizer, differentiable renderer), fuer die vorkompilierte Raeder bereitliegen. Ein zweiter Wrapper (niknah/ComfyUI-Hunyuan-3D-2) besteht ebenfalls.
  · https://api.github.com/repos/visualbruno/ComfyUI-Hunyuan3d-2-1
  · https://github.com/visualbruno/ComfyUI-Hunyuan3d-2-1
- **ComfyUI-Trellis2 (visualbruno)** — MIT, angelegt 17.12.2025, zuletzt bespielt 03.08.2026, 796 Sterne. Getestet unter Windows 11, Raeder fuer Windows und Linux, Python 3.11, PyTorch 2.7.0+ (Raeder fuer Torch 2.7, 2.8, 2.10). fp8-Modelle seit 26.02.2026, Pixal3D-T-Unterstuetzung seit 13.05.2026.
  · Stand: GitHub-API und README abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Das ist der Weg, auf dem TRELLIS.2 unter Windows laeuft, obwohl das Original Linux-only ist. Achtung: die Sammlung bringt Knoten zur Netzglaettung mit PyMeshlab mit — PyMeshlab ist GPL und in AGENTS.md Regel 15 ausdruecklich ausgeschlossen. Im ComfyUI-Prozess ist das ein fremdes Programm, in Solidon waere es ein Verstoss. Sie laedt ausserdem facebook/dinov3-vitl16-pretrain-lvd1689m nach.
  · https://api.github.com/repos/visualbruno/ComfyUI-Trellis2
  · https://github.com/visualbruno/ComfyUI-Trellis2
- **Pixal3D-ComfyUI (Saganaki22)** — MIT, angelegt 14.05.2026, zuletzt bespielt 12.06.2026, 201 Sterne, Windows ausdruecklich unterstuetzt, CPU-Betrieb nicht. Laedt Pixal3D (TencentARC), DINOv3 (camenduru-Spiegel), MoGe (Comfy-Org), RMBG-2.0 (briaai, gated) und den NAF-Hochskalierer (valeoai).
  · Stand: GitHub-API und README abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Der Weg zieht RMBG-2.0 mit hinein und damit dessen nicht-kommerzielle Bindung und die Kontopflicht. Wer Pixal3D in Solidon benutzen will, sollte das Freistellen auf InSPyReNet umbiegen. VRAM-Zahlen nennt das README nicht, nur Betriebsarten (dynamic_vram, hybrid_low_vram, native_low_vram) und einen Hinweis auf 12 GB in der Fehlersuche.
  · https://api.github.com/repos/Saganaki22/Pixal3D-ComfyUI
  · https://github.com/Saganaki22/Pixal3D-ComfyUI

**Nicht belegbar:**
- Ob nach v0.33.1 (13.08.2026) bis zum 19.08.2026 eine weitere ComfyUI-Fassung erschien. Gesucht ueber docs.comfy.org/changelog und die GitHub-Releases-Seite; die GitHub-API (releases/latest, tags) antwortete zum Schluss mit HTTP 403 wegen Ratenbegrenzung, und das WebSearch-Kontingent der Sitzung war aufgebraucht.
- Die Lizenzdatei von Direct3D-S2 (DreamTechAI, NeurIPS 2025, Gewichte unter wushuang98/Direct3D-S2). raw.githubusercontent.com/DreamTechAI/Direct3D-S2/main/LICENSE liefert 404; die GitHub-API war nicht mehr abrufbar (403, Ratenbegrenzung). Die Angabe 'MIT' stammt ausschliesslich aus einer Suchergebnis-Zusammenfassung und ist damit nicht belegt — bewusst nicht als Faktenkarte gefuehrt.
- Ob das Hugging-Face-Ablagefach TencentARC/Pixal3D tatsaechlich gated ist. Das Feld extra_gated_eu_disallowed: true steht im YAML-Kopf, ein gated: true habe ich dort nicht gesehen, und die Hub-Doku sagt, die EU-Sperre greift nur bei gated: true. Ein Abruf aus einer EU-IP wurde nicht durchgefuehrt.
- Konkrete VRAM-Zahlen fuer Pixal3D. Weder Modellkarte (nur 'Low-VRAM mode') noch die Knotensammlung Pixal3D-ComfyUI nennen eine Mindestangabe; in der Fehlersuche der Sammlung taucht '12 GB' auf, ohne dass daraus eine Anforderung wird.
- VRAM-Bedarf von TripoSG, PartCrafter und Hunyuan3D-Part. In den jeweiligen READMEs und Modellkarten nicht gefunden.
- Die Lizenz von facebook/dinov3-vitl16-pretrain-lvd1689m, das sowohl ComfyUI-Trellis2 als auch Pixal3D-ComfyUI zwingend nachladen. Nicht abgerufen — und Trainingswissen dazu ist hier wertlos. Vor einer Entscheidung selbst nachsehen, denn dieses Modell haengt an beiden EU-tauglichen Wegen.
- Ob es eine RMBG-Nachfolgefassung fuer Standbilder ueber 2.0 hinaus gibt. Gefunden wurde nur briaai/VRMBG-3.0, und das ist nach den Suchtreffern ein Videomodell mit eigener, nicht-quelloffener BRIA-Lizenz; die Modellkarte selbst habe ich nicht abgerufen.
- Ob Hunyuan3D 2.5 jemals als offene Gewichte erschienen ist. Zu 2.5 gibt es nach den Repositoriums-Meldungen einen Systembericht vom 23.06.2025, aber kein auffindbares Ablagefach mit Gewichten.
- Der Stand der Knotensammlung Stable-X/ComfyUI-Hi3DGen (letzte Fassung, Lizenz, Pflegezustand). Nicht abgerufen.
- Ob die vier ComfyUI-Fassungen vom August 2026 an den HTTP-Routen /prompt, /history, /view oder am WebSocket-Protokoll etwas geaendert haben. Der Anbieter-Changelog nennt keine solchen Aenderungen, sagt aber auch nirgends, dass die API stabil bleibt — die Abwesenheit eines Vermerks ist kein Beleg fuer die Abwesenheit einer Aenderung.
- Was 2026 sonst noch an offenen Text-zu-3D-Modellen dazugekommen ist. Belegt ist nur die TRELLIS-text-Reihe vom 25.03.2025; die abschliessende Suche dazu konnte nicht mehr ausgefuehrt werden, weil das WebSearch-Kontingent der Sitzung (200 Aufrufe) erschoepft war. Das Themenfeld Text-zu-3D ist in dieser Recherche damit unterbelichtet.
- Der genaue Tag, an dem die TRELLIS.2-Gewichte veroeffentlicht wurden. Belegt ist nur das Anlegedatum des Repositoriums (26.11.2025) und die Arxiv-Nummer 2512.14692; das README nennt kein Freigabedatum.
- Ob die Knotensammlung visualbruno/ComfyUI-Hunyuan3d-2-1 ueberhaupt eine Lizenzdatei fuehrt. GitHub meldet NOASSERTION; die LICENSE-Datei selbst habe ich nicht abgerufen.

**Neu seit Anfang August:**
- ComfyUI hat allein zwischen dem 3. und 13. August 2026 fuenf Fassungen herausgegeben (v0.30.0 bis v0.33.1). Wer eine Fassung fest annimmt, liegt binnen zwei Wochen daneben — Solidon sollte die Fassung beim Verbinden abfragen und nicht voraussetzen.
- Mit v0.32.0 vom 11.08.2026 ist PyTorch 2.7 die unterste unterstuetzte Fassung. Das ist die einzige Aenderung des Augustfensters, die einem Nutzer die bestehende Installation zerlegen kann, und sie gehoert in Solidons Handbuch.
- Das Repositorium heisst jetzt Comfy-Org/ComfyUI; die alte Adresse comfyanonymous/ComfyUI leitet nur noch um. Verweise in Solidons Unterlagen zeigen auf den alten Namen.
- Kein einziges der geprueften 3D-Modelle hat im August 2026 eine neue Fassung oder Lizenzaenderung bekommen. Die Bewegung im Themenfeld liegt vollstaendig bei ComfyUI und bei den Knotensammlungen (ComfyUI-Trellis2 zuletzt am 03.08., ComfyUI-Hunyuan3d-2-1 am 30.07., ComfyUI-RMBG am 28.07.2026).
- Der eigentliche Umbruch liegt vor dem Augustfenster, war Solidon aber offenbar noch nicht gegenwaertig: TRELLIS.2-4B (MIT, seit 26.11.2025) und TencentARC Pixal3D (MIT, Copyright 2026 Tencent, seit 10.05.2026) sind zwei quelloffene Bild-zu-3D-Modelle ohne jeden Gebietsausschluss. Damit gibt es erstmals einen EU-tauglichen Ersatz fuer Hunyuan3D — der Grund, warum Solidon an der Community License haengt, ist entfallen.
- Hunyuan3D-2.1 ist bei Tencent seit dem 17.10.2025 nicht mehr bespielt worden, waehrend Hunyuan3D 3.0 seit 26.11.2025 als gehosteter Dienst laeuft (20 freie Erzeugungen taeglich, Tencent-Cloud-API). Der offene Zweig ist eingefroren; auf ihn zu setzen heisst, auf ein stehendes Modell zu setzen.
- Die EU-Sperre bei Hunyuan3D ist nicht nur Vertragstext: die Modellkarten tragen extra_gated_eu_disallowed: true, und Hugging Face sperrt danach nach IP-Adresse. Ein Solidon-Graph, der Hunyuan3D-Gewichte voraussetzt, scheitert beim deutschen Nutzer schon am Herunterladen — nicht erst an einer Rechtsfrage. Das ist ein Fehlerbild, kein Lizenzhinweis.
- Beide naheliegenden Pixal3D-Wege in ComfyUI ziehen stillschweigend RMBG-2.0 zum Freistellen mit hinein — CC BY-NC und dazu ein gated Ablagefach mit Kontopflicht. Wer den mitgelieferten Graphen uebernimmt, uebernimmt die nicht-kommerzielle Bindung mit, ohne dass irgendeine Oberflaeche darauf hinweist. InSPyReNet (MIT, weiter gepflegt, zuletzt 08.07.2026) leistet dasselbe ohne diese Bindung.
- ComfyUI-Trellis2 bringt Knoten zur Netzglaettung mit PyMeshlab mit. PyMeshlab ist GPL und in AGENTS.md Regel 15 namentlich ausgeschlossen. Im ComfyUI-Prozess ist das unbedenklich, in einem Solidon-Graphen, der solche Knoten voraussetzt, wird die Grenze zwischen 'extern aufgerufen' und 'vorausgesetzt' duenn.
- Comfy-Org pflegt bereits ein umgepacktes Pixal3D-Ablagefach (bf16 und int8) und bezeichnet es als 'work in progress' — native Pixal3D-Unterstuetzung in ComfyUI zeichnet sich ab. Wer jetzt eine Knotensammlung fest verdrahtet, baut moeglicherweise etwas, das in wenigen Fassungen im Kern steht.

## ki-3d-generatoren

_gehostete KI-3D-Generatoren_

- **Meshy** — Meshy 7 ging am 10. August 2026 live, ein Bild-zu-3D-Grundlagenmodell, das auf Ausrichtung zwischen Eingabebild und Ergebnis zielt; offen für alle Abostufen, Herunterladen erst ab Pro.
  · Stand: Pressemitteilung 12.08.2026, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Selbst gemessene Kennzahlen gegen ein zurückgehaltenes Referenzset: 81,0 % Gesamtproportion, 79,7 % räumliche Verteilung, 59,8 % Oberflächendetails; Vorsprung 5,3 Punkte bei Oberflächendetails. Herstellerangabe, keine unabhängige Messung.
  · https://www.prnewswire.com/news-releases/meshy-releases-meshy-7-a-new-foundation-model-that-sets-a-new-bar-for-image-3d-alignment-302849368.html
- **Meshy** — Meshy 6 erschien am 18. Januar 2026 mit Low-Poly-Modus und ausdrücklichem Mehrfarb-3D-Druck: Texturen werden zu sauberen Farbblöcken für FDM zusammengefasst und als 3MF ausgegeben.
  · Stand: Herstellerblog, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Für Solidon der Kern: Meshy behandelt Druckvorbereitung seit Anfang 2026 als Produktmerkmal, nicht als Nebensache.
  · https://www.meshy.ai/blog/meshy-6-launch
- **Meshy** — Abostufen heute: Free 0 $ (100 Guthaben/Monat), Pro 20 $/Monat bzw. 240 $/Jahr (1.000 Guthaben), Premium 40 $/Monat, Ultra 100 $/Monat, Studio 70 $/Monat mit einem Mitglied und 10 $ je weiterem, Enterprise nach Absprache.
  · Stand: meshy.ai/pricing, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Guthabenmengen für Premium, Ultra und Studio standen auf der abgerufenen Seite nicht im Text — siehe not_verifiable. Freie Guthaben setzen sich am 1. des Monats 00:00 UTC zurück und werden nicht angespart.
  · https://www.meshy.ai/pricing
- **Meshy** — Pro (20 $/Monat) bringt API-Zugang, 60 % schnellere Erzeugung, private Eigentümerschaft an den Ergebnissen und 10 gleichzeitige Aufträge.
  · Stand: meshy.ai/pricing, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: API-Zugang beginnt also bei 20 $/Monat — die Einstiegshürde für einen Mitbewerber-Vergleich in Solidon.
  · https://www.meshy.ai/pricing
- **Meshy API** — Die API rechnet in vorab gekauften Guthaben: Text-zu-3D-Netz 20 Guthaben (Meshy-6/7, Meshy-7 Ultra +5), Textur 10 (2K/4K) bzw. 15 (8K), Bild-zu-3D 20 ohne / 30 mit Textur / 35 bei 8K, Remesh 5, Konvertieren 1, Skalieren 1, Auto-Rigging 5, Animation 3.
  · Stand: docs.meshy.ai/en/api/pricing, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Smart Topology (T2) ist mit 5 Guthaben je Vorschau deutlich billiger als die Grundmodelle. Für Mengenpreise verweist die Seite auf den Vertrieb.
  · https://docs.meshy.ai/en/api/pricing
- **Meshy API** — Es gibt eigene 3D-Druck-Endpunkte: Mehrfarbdruck 10 Guthaben, Druckbarkeit prüfen kostenlos, Druckbarkeit reparieren 10 Guthaben, dazu ein Endpunkt „Balance".
  · Stand: docs.meshy.ai/en/api/pricing, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Das ist die Stelle, an der Meshy Solidon am nächsten kommt: Netzprüfung und -reparatur als bezahlbarer Dienst, die Prüfung sogar gratis.
  · https://docs.meshy.ai/en/api/pricing
  · https://docs.meshy.ai/en/api/repair-printability
- **Meshy** — „Analyze Printability" meldet Wasserdichtheit, Anzahl nicht-mannigfaltiger Kanten, Löcher (Randschleifen) und entartete Flächen — und prüft ausdrücklich NICHT Überhänge, dünne Wände oder den Maßstab des Modells.
  · Stand: help.meshy.ai, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Der Hersteller verweist für Überhänge, Wandstärke und Maßstab auf den Slicer. Genau diese drei sind die Lücke, in der Solidon steht — belegt, nicht vermutet.
  · https://help.meshy.ai/en/articles/15813389-how-to-check-and-fix-your-model-s-printability
- **Meshy** — „Repair Printability" behebt nicht-mannigfaltige Kanten, entartete Flächen und Löcher zu einem wasserdichten Netz; Eingabe bis 100 MB als .glb/.gltf/.obj/.fbx/.stl, Ausgabeformat gleich Eingabeformat, 10 Guthaben, Fehlschlag wird erstattet.
  · Stand: docs.meshy.ai/en/api/repair-printability, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Vorhandene Texturen gehen bei der Reparatur verloren, weil sich die Geometrie ändert; die Retexture-API kann sie danach wiederherstellen. Es gibt keine Parameter für Hohlkörper, Wandstärke oder Maßstab.
  · https://docs.meshy.ai/en/api/repair-printability
- **Meshy API** — Ausgabeformate sind GLB, FBX, USDZ, OBJ, MTL, STL und 3MF; BLEND wird nicht unterstützt. Topologie wahlweise quad-dominant oder dezimiertes Dreiecksnetz.
  · Stand: docs.meshy.ai/en/api/text-to-3d, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Nicht erzeugte Formate fehlen im Antwortobjekt, statt als leere Zeichenkette zurückzukommen. Smart Topology liefert ausschließlich Dreiecke.
  · https://docs.meshy.ai/en/api/text-to-3d
- **Meshy API** — Polygonzahl beim regulären Remesh 100 bis 300.000 Flächen (Vorgabe 30.000), bei Smart Topology 100 bis 15.000 (Vorgabe 4.000); PBR-Karten sind Basisfarbe, Metallic, Normal, Roughness und Emission.
  · Stand: docs.meshy.ai/en/api/text-to-3d, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Emissionskarte gibt es nur bei meshy-6 (nicht bei 8K-Textur) und nicht mehr bei Meshy 7 — ein Rückschritt im Funktionsumfang der neuen Generation.
  · https://docs.meshy.ai/en/api/text-to-3d
- **Meshy** — Rechte je Stufe: Ergebnisse der kostenlosen Stufe stehen unter CC BY 4.0 und verlangen bei kommerzieller Nutzung eine Namensnennung; auf bezahlten Stufen gehören die erzeugten Objekte dem Nutzer.
  · Stand: help.meshy.ai, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Vorschlag zur Namensnennung laut Hersteller: „Model created with Meshy – CC BY 4.0 License". Verantwortung für Rechte am Eingabematerial bleibt beim Nutzer.
  · https://help.meshy.ai/en/articles/9992001-can-i-use-my-generated-assets-for-commercial-projects
  · https://www.meshy.ai/pricing
- **Meshy** — Seit dem 8. April 2026 gibt es eine Anbindung an Formlabs: „Print with Form Now" schickt ein erzeugtes Modell direkt in den Fertigungsdienst, mit automatischer Netzreparatur und Wandstärkenprüfung (FDM mindestens 1,2 mm, Harz mindestens 0,3 mm).
  · Stand: Pressemitteilung 14.04.2026 zur RAPID+TCT 2026, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Genannte Kennzahl: 97 % Slicer-Durchlaufquote bei Figuren. Widerspricht scheinbar der Hilfeseite, die Wandstärke ausdrücklich ausklammert — die Wandstärkenprüfung hängt offenbar am Formlabs-Weg, nicht am allgemeinen Prüf-Endpunkt. Für Solidon der wichtigste Widerspruch zum Nachfassen.
  · https://www.prnewswire.com/news-releases/meshy-ai-announces-integration-with-formlabs-to-bridge-the-gap-between-generative-ai-and-professional-3d-manufacturing-debuts-at-rapid--tct-2026-302742030.html
- **Meshy Creative Lab** — Creative Lab (Beta) macht aus einem Foto ein 3D-druckbares Konsumprodukt — über 15 Vorlagen wie Figur, Schlüsselanhänger, Kühlschrankmagnet, Lampe, Tastenkappe, Blumentopf — und lädt in 3MF und STL herunter, „bereit für jeden 3D-Drucker oder Slicer".
  · Stand: meshy.ai/creative-lab, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Entwerfen kostet nur die üblichen Guthaben; Meshy druckt und versendet auf Wunsch selbst in neun Länder (darunter Deutschland), meist in 2 bis 3 Wochen, Versand im Produktpreis enthalten.
  · https://www.meshy.ai/creative-lab
- **Meshy Creative Lab API** — Die Creative-Lab-Endpunkte erschienen am 1. Juni 2026 als produktgebundene Schnittstellen, die aus einem Foto ein 3D-druckbares Produkt machen; seit 12. Juni kostet der Bau-Schritt 30 Guthaben, der Prototyp-Schritt bleibt bei 6.
  · Stand: docs.meshy.ai/en/api/changelog, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Nachgeschoben wurden Vinyl-Figur (20.07.), Tastenkappe (22.07.) und Brick-Figur (27.07.2026) — ein sehr schneller Takt in genau dem Bereich, den Solidon adressiert.
  · https://docs.meshy.ai/en/api/changelog
- **Meshy Creative Lab API** — Der Schlüsselanhänger-Endpunkt gibt die Kantenlänge des umschließenden Quadrats in Millimetern an (Bereich größer 0 bis 400), der Tastenkappen-Endpunkt exportiert in realem Millimetermaßstab und stützt derzeit die Cherry-MX-1u-Basis.
  · Stand: docs.meshy.ai, Stand der Suche 19.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Die Millimeter-Angaben stammen aus der Suchzusammenfassung der Meshy-Dokumentation; die Einzelseite creative-lab-keychain habe ich nicht selbst geholt. Maßhaltigkeit gibt es hier also nur produktgebunden, nicht allgemein.
  · https://docs.meshy.ai/en/api/creative-lab-keychain
  · https://docs.meshy.ai/en/api/changelog
- **Meshy API** — Weitere Änderungen 2026: UV-Unwrap-API am 15. Juni (bis 40.000 Flächen, 5 Guthaben), 8K-Basisfarbtexturen am 21. Juli (15 Guthaben), Smart Topology für Bild-zu-3D am 13. Juli.
  · Stand: docs.meshy.ai/en/api/changelog, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Zeigt den Takt: etwa eine spürbare API-Erweiterung pro Woche.
  · https://docs.meshy.ai/en/api/changelog
- **Hyper3D Rodin** — Preisstufen heute: Free 0 $ (Erkundung, 10 private Objekte, eingeschränkte kommerzielle Nutzung), Creator 30 $/Monat bzw. 288 $/Jahr (entspricht 24 $/Monat, rund 60 Modelle im Monat), Business 120 $/Monat bzw. 1.152 $/Jahr (rund 416 Modelle), Enterprise nach Absprache, dazu eine Bildungsstufe.
  · Stand: hyper3d.ai/pricing, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Einzeln gekaufte Guthaben kosten laut derselben Seite 1,5 $ je Guthaben. Wiederholungen sind gedeckelt: Creator 20× Geometrie / 6× Material, Business 50× / 15×.
  · https://hyper3d.ai/pricing
- **Hyper3D Rodin** — API-Zugang gibt es erst ab Business (120 $/Monat), dort als „Full API access" mit 120 bis 240 Anfragen je Minute; Free und Creator haben keinen API-Zugang.
  · Stand: hyper3d.ai/pricing, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Deutlicher Unterschied zu Meshy, wo die API schon ab 20 $/Monat offensteht — der für Solidon greifbarste Preisunterschied zwischen den beiden Vergleichskandidaten.
  · https://hyper3d.ai/pricing
- **Hyper3D Rodin** — Kommerzielle Nutzung ist bei Free ausdrücklich eingeschränkt; Creator erlaubt unbegrenzten Export und jede Nutzung, Business schließt zusätzlich eine kommerzielle ChatAvatar-Lizenz ein.
  · Stand: hyper3d.ai/pricing, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Worin die Einschränkung der Free-Stufe genau besteht, sagt die Preisseite nicht.
  · https://hyper3d.ai/pricing
- **Hyper3D Rodin API** — Gen-2.5 rechnet additiv in Guthaben: Grunderzeugung 0,5 Guthaben, die Stufe Extreme-High +0,5, der Texturmodus extreme-high nochmals +2,0; das Zusatzpaket HighPack hebt Pack-Texturen von 2K auf 4K, ohne neue Geometrie zu erzeugen.
  · Stand: docs.hyper3d.ai/en/api-specification/rodin-gen2-5, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Mit 1,5 $ je Guthaben liegt eine einfache Erzeugung damit bei etwa 0,75 $. Die Stufe Extreme-High liefert zusätzlich ein Netz mit bis zu 10 Mio. Flächen. Texturauflösung 2K bis 12K je nach Stufe und uhd_texture.
  · https://docs.hyper3d.ai/en/api-specification/rodin-gen2-5
- **Hyper3D Rodin API** — Verfügbare Modellfamilien laut Dokumentation sind Gen-2.5, Gen-2 sowie Gen-1/1.5 mit den Stufen Sketch, Regular, Detail und Smooth; Basis-URL ist https://api.hyper3d.com/api/v2, Authentifizierung per Bearer-Token.
  · Stand: docs.hyper3d.ai, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Doku ist umgezogen: developer.hyper3d.ai leitet per 301 auf docs.hyper3d.ai, und die alten Pfade (/api-specification/rodin-gen2.5, /api-specification/rodin-generation-gen2) sind tot — neu ist /en/api-specification/rodin-gen2-5. Wer alte Links in Solidon führt, sollte sie nachziehen.
  · https://docs.hyper3d.ai/
  · https://docs.hyper3d.ai/en/get-started/features
- **Hyper3D Rodin** — Exportformate laut Herstellerseite: GLB, FBX, OBJ, STL, USDZ, glTF, 3MF und DXF; PBR-Karten für Albedo, Roughness und Metalness gehören zu jeder Erzeugung, Zielpolygonzahl bis 10 Millionen, optionale LOD-Erzeugung.
  · Stand: hyper3d.ai/features/image-to-3d, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: DXF ist bemerkenswert — das einzige gefundene Anbieterversprechen mit einem CAD-nahen Format in dieser Runde.
  · https://hyper3d.ai/features/image-to-3d
- **Hyper3D Rodin** — Der Hersteller wirbt ausdrücklich mit Druckbarkeit: „solide, mannigfaltige Geometrie", die sauber nach STL oder 3MF exportiere und ohne Löcher oder nicht-mannigfaltige Fehler slice.
  · Stand: hyper3d.ai/features/image-to-3d, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Reines Werbeversprechen auf einer Funktionsseite — ohne Prüfbericht, ohne Wandstärken-, Überhang- oder Hohlkörperfunktion. Anders als Meshy gibt es keinen Endpunkt, der Druckbarkeit misst.
  · https://hyper3d.ai/features/image-to-3d
- **Hyper3D Rodin** — Über den Drittanbieter fal.ai kostet eine Rodin-v2.5-Erzeugung 0,40 $, mit dem Zusatz HighPack 0,80 $ mehr; ausgegeben werden GLB-Netze in den Varianten basic_pbr und basic_shaded.
  · Stand: fal.ai, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Dritter Anbieter, nicht Hyper3D selbst — aber der einzige Weg zu Rodin ohne das 120-$-Business-Abo. Die dortige Oberfläche zeigt nur die Stufe Gen-2.5-High.
  · https://fal.ai/models/fal-ai/hyper3d/rodin/v2.5/text-to-3d
- **Hyper3D Rodin** — Rodin Gen-2.5 wurde Ende Mai 2026 vorgestellt, mit fünf Aufwandstufen von etwa 4 Sekunden (Extreme-Low) über 9 Sekunden (Low) bis zu höheren Stufen, Ausgaben mit über 10 Mio. Polygonen und Stapelerzeugung von bis zu 10 Varianten.
  · Stand: 80.lv-Artikel vom 03.06.2026, abgerufen 19.08.2026 · Sicherheit: unsicher
  · Anmerkung: Das genaue Erscheinungsdatum steht in dem von mir geholten Artikel NICHT; Suchtreffer nennen den 26.05.2026 über eine Pressemitteilung, die ich nicht laden konnte (Verbindungsabbruch). Datum daher als unsicher geführt.
  · https://80.lv/articles/how-hyper3d-rodin-gen-2-5-is-bringing-production-level-control-to-ai-3d-generation
- **Hyper3D Rodin** — „Smart Low-Poly" erzeugt artist-artige Dreiecks- und Quad-Geometrie für Echtzeitanwendungen, befindet sich aber noch in der Beta.
  · Stand: 80.lv-Artikel vom 03.06.2026, abgerufen 19.08.2026 · Sicherheit: unsicher
  · Anmerkung: Quad-Topologie ist bei Rodin damit weniger klar zugesichert, als Marketingtexte („high-poly quad meshes") nahelegen. Die API-Doku nennt nur mesh_mode=Raw und erklärt die übrigen Werte nicht.
  · https://80.lv/articles/how-hyper3d-rodin-gen-2-5-is-bringing-production-level-control-to-ai-3d-generation
- **Tripo AI (Tripo3D)** — Studio-Abos: Free 0 $ mit 200 Guthaben (rund 13 Modelle), ausdrücklich nur nicht-kommerziell und 15 Exporte (nur H2.5); Pro 19,90 $/Monat bzw. 238,80 $/Jahr mit 3.000 Guthaben; Max 89,90 $/Monat bzw. 1.078,80 $/Jahr mit 25.000 Guthaben; Team 54,95 $ je Platz mit 90.000 Guthaben.
  · Stand: tripo3d.ai/pricing, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Kommerzielle Nutzung erst ab Pro — strenger als Meshy, wo die freie Stufe unter CC BY 4.0 kommerziell nutzbar ist. Gleichzeitige Aufträge steigen von 10 auf 200.
  · https://www.tripo3d.ai/pricing
- **Tripo AI API** — Die API rechnet mit 1 Guthaben = 0,01 $: Text-zu-3D 10 (ohne Textur) bzw. 20, Bild-zu-3D 20 bzw. 30, Multiview 20 bzw. 30, Textur 10 (Standard) / 20 (HD) / 30 (8K Ultra), Quad-Netz 5 als Zusatz, Retopologie v2.0 Smart 30, Auto-Rig 25, Rig-Prüfung kostenlos.
  · Stand: developers.tripo3d.ai/en/pricing, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Damit kostet ein texturiertes Bild-zu-3D 0,30 $ — der günstigste belegte API-Preis dieser Runde. Modellfamilien heißen dort H Series, P Series und Splat Series.
  · https://developers.tripo3d.ai/en/pricing
- **Tripo AI** — Tripo P2.0 Preview wurde am 19. August 2026 angekündigt: „Production-Ready Native Quad Mesh", native Quad-Topologie und erweiterte Netzbudgets für Spiele- und Echtzeitpipelines.
  · Stand: tripo3d.ai/blog, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Datum und Titel stammen von der Blog-Übersicht des Herstellers; die Einzelseite war unter den geratenen URLs nicht erreichbar. Suchtreffer eines Tripo-Beitrags auf X nennen zusätzlich bis zu 50K Dreiecke / 25K Quads und 2 Freierzeugungen für alle — diese Zahlen habe ich nicht selbst am Beleg gesehen.
  · https://www.tripo3d.ai/blog
- **Tripo AI** — Tripos eigener FDM-Druckleitfaden verweist für Modellreparatur auf Blender mit dem 3D-Print-Toolbox-Plugin und für Slicing und Mehrfarbdruck auf Bambu Studio; in der Anwendung selbst gibt es Retopologie (Dreieck, 100k–150k Flächen), Vertexfarben-Export, Teilezerlegung und einen Exportmodus „3D Print".
  · Stand: tripo3d.ai/blog/tripo-fdm-3d-printing-guide, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Wichtige Einordnung: Hohlkörper, Wandstärke und Millimetermaßstab kommen in dem Leitfaden NICHT als eigene Funktion vor, und die Teilezerlegung ist laut Text „noch nicht direkt zum Drucken brauchbar".
  · https://www.tripo3d.ai/blog/tripo-fdm-3d-printing-guide
- **Tripo AI** — Die Marketingseiten zum 3D-Druck versprechen mehr als der eigene Leitfaden hält: dort ist von „intelligenter Lochreparatur", Wandstärkenanpassung und vorgehöhlten Modellen die Rede, Export nach STL, OBJ und 3MF.
  · Stand: tripo3d.ai/3d-print, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Widerspruch innerhalb desselben Anbieters: Die SEO-Seite behauptet Funktionen, die der technische Leitfaden an externe Werkzeuge abgibt. Die Skalierung findet laut Anbieterseite ohnehin erst im Slicer statt.
  · https://www.tripo3d.ai/3d-print
  · https://www.tripo3d.ai/blog/tripo-fdm-3d-printing-guide
- **Sloyd** — Preise heute: Guest kostenlos mit einer KI-Erzeugung pro Tag, Export nur GLB und OBJ, Lizenz ausdrücklich nur für den privaten Gebrauch; Plus 15 $/Monat (12,50 $ bei Jahreszahlung, 150 $/Jahr) mit 12 KI-Guthaben im Monat und 2 gleichzeitigen Erzeugungen; Pro 50 $/Monat (41,67 $ jährlich, 500 $/Jahr) mit 60 Guthaben und 5 gleichzeitigen Erzeugungen.
  · Stand: sloyd.ai/pricing, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Wichtiger Widerspruch: Dritte und Sloyds eigener älterer Blogbeitrag werben mit „unbegrenzten Erzeugungen ohne Token" auf den Bezahlstufen. Die heute abgerufene Preisseite nennt harte Guthabengrenzen (12 bzw. 60). Ich folge der Anbieterseite.
  · https://www.sloyd.ai/pricing
- **Sloyd** — Kommerzielle Rechte gibt es ab Plus; Pro schließt zusätzlich eine Weiterverkaufslizenz und 4K-Texturen ein.
  · Stand: sloyd.ai/pricing, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Sloyds öffentlicher Preisvergleich gegen Meshy, Tripo, CSM und Hyper3D stammt vom 4. September 2025 und ist damit unbrauchbar veraltet — er nennt Meshy noch mit 0,40 $ je Modell.
  · https://www.sloyd.ai/pricing
- **CSM (Common Sense Machines)** — Alphabet hat Common Sense Machines übernommen; der Abschluss erfolgte am 24. Januar 2026, das Unternehmen aus Cambridge, Massachusetts hatte rund 12 Beschäftigte, die Konditionen wurden nicht offengelegt.
  · Stand: 3D Printing Industry, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Der Artikel sagt ausdrücklich, dass weder Alphabet noch Google mitgeteilt haben, was mit Personal, Produkt oder Kunden geschieht. Suchtreffer berichten, die Mannschaft sei zu DeepMind gegangen — von mir nicht am Beleg geprüft.
  · https://3dprintingindustry.com/news/google-parent-acquires-3d-ai-company-common-sense-machines-248585/
- **CSM (Common Sense Machines)** — Die Domänen csm.ai, www.csm.ai und 3d.csm.ai lösen am 19. August 2026 nicht mehr auf (DNS-Fehler ENOTFOUND) — die Plattform ist über ihre bekannten Adressen nicht erreichbar.
  · Stand: eigener Abrufversuch am 19.08.2026 · Sicherheit: unsicher
  · Anmerkung: Das ist eine eigene Werkzeugbeobachtung, KEINE veröffentlichte Quelle; die angegebene URL belegt nur die Übernahme. Eine offizielle Abschaltmeldung habe ich nicht gefunden. Für Solidon heißt das: CSM als Vergleichsgröße vorerst streichen, nicht als „eingestellt" behaupten.
  · https://3dprintingindustry.com/news/google-parent-acquires-3d-ai-company-common-sense-machines-248585/
- **Luma AI Genie** — Genie ist eingestellt. Luma schreibt in der eigenen App-Store-Beschreibung: „We've officially Sunset Genie since January 1, 2026" — Inhalte lassen sich weiterhin exportieren.
  · Stand: Apple App Store, Eintrag Luma 3D Capture, Version 1.3.14, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Damit fällt Genie als Mitbewerber vollständig weg. Zitat wörtlich aus der Herstellerangabe.
  · https://apps.apple.com/us/app/luma-3d-capture/id1615849914
- **Luma AI** — Die Startseite von Luma Labs führt heute Ray 3.2 und Uni-1 als Modelle; Genie kommt dort nicht mehr vor.
  · Stand: lumalabs.ai, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Der frühere Genie-Pfad zeigt die allgemeine Startseite — bestätigt die Abschaltung von der Produktseite her.
  · https://lumalabs.ai/genie
- **Kaedim** — Tarife laut Anbieterseite: Trial 50 $ für 7 Tage (herabgesetzt von 100 $) mit 5 Guthaben für bis zu 5 Geometrien, danach automatischer Übergang auf Indie; Indie 400 $/Monat mit 20 Guthaben; Pro 1.200 $/Monat mit 60 Guthaben.
  · Stand: kaedim3d.com/plans, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Deutlicher Widerspruch zu Vergleichsportalen, die noch Starter 150 $ / Indie 300 $ / Studio 1.000 $ nennen — ich folge der Anbieterseite. Die früher übliche URL kaedim3d.com/pricing liefert heute 404. 20 Guthaben entsprechen laut Seite „1 vollständigem Asset" mit Retopologie, UVs und Texturen.
  · https://www.kaedim3d.com/plans
- **Kaedim** — Kaedim positioniert sich heute nicht mehr als Generator, sondern als Produktionsplattform mit menschlicher Durchsicht: Skizzen, Referenzpakete, Produktfotos und Briefings gehen hinein, das Ergebnis kommt „in Stunden" zurück und wird im Werkzeug markiert und überarbeitet.
  · Stand: kaedim3d.com, abgerufen 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Ausdrücklich genanntes Zielfeld ist unter anderem Produktgestaltung — frühe Entwürfe in 3D, „bevor man sich im CAD festlegt". Das ist der einzige Anbieter dieser Runde, der CAD überhaupt als Nachbarschaft benennt, aber er ersetzt CAD nicht.
  · https://www.kaedim3d.com/

**Nicht belegbar:**
- Meshy: die monatlichen Guthabenmengen für Premium, Ultra und Studio. Die Suchzusammenfassung nennt 3.000 (Premium), 8.000 (Ultra) und 5.500 (Studio, geteilter Vorrat), aber auf der von mir zweimal geholten Seite meshy.ai/pricing standen im Text nur Free (100) und Pro (1.000). Nicht als belegt geführt.
- Meshy: ob Auto-Rigging und Animation in der Weboberfläche tatsächlich 0 Guthaben kosten (in Suchtreffern behauptet). Die API-Preisliste nennt 5 bzw. 3 Guthaben — das widerspricht sich, und eine Anbieterseite zur Weboberfläche habe ich dazu nicht gefunden.
- Meshy: welche Abostufen die 3D-Druck-Endpunkte und die Formlabs-Anbindung nutzen dürfen. Die Pressemitteilung sagt „available to all Meshy users", die Hilfeseite nennt keine Stufe.
- Hyper3D Rodin: das genaue Erscheinungsdatum von Gen-2.5. Suchtreffer nennen den 26. Mai 2026 (Pressemitteilung über pressadvantage.com), der Abruf brach mit ECONNRESET ab; der stattdessen geholte 80.lv-Artikel vom 3. Juni 2026 nennt kein Datum. Ein weiterer Treffer nennt Juni 2026.
- Hyper3D Rodin: das Erscheinungsdatum von Gen-2 (Suchtreffer: 1. Oktober 2025) und von Gen-2 Edit (Suchtreffer: Januar 2026) — keine Anbieterseite mit Datum gefunden; der Herstellerblog hyper3d.ai/blog/rodin-gen-2 trägt das Datum 9. Februar 2026 und nennt keinen Erscheinungstermin.
- Hyper3D Rodin: welche Werte mesh_mode annehmen kann und ob es eine zugesicherte Quad-Ausgabe über die API gibt. Die Dokumentation zeigt nur mesh_mode=Raw in Beispielen und erklärt die Alternativen nicht.
- Hyper3D Rodin: wie viele Freierzeugungen die kostenlose Stufe genau umfasst, worin die „eingeschränkte" kommerzielle Nutzung besteht, und was die Gen-2-Endpunkte (nicht Gen-2.5) an Guthaben kosten — die früheren Doku-Pfade zu Gen-2 liefern heute 404.
- Tripo P2.0 Preview: die Netzbudgets (Suchtreffer aus einem X-Beitrag: bis 50K Dreiecke / 25K Quads, 2 Freierzeugungen für alle). Der X-Beitrag war nicht abrufbar (HTTP 402), die Blog-Einzelseite unter den geratenen URLs 404. Nur Titel und Datum sind über die Blog-Übersicht belegt.
- Tripo: welche Modellfassung heute die Vorgabe ist. Die Preisseite nennt „H2.5" für die freie Stufe, die API-Preisliste spricht von H Series, P Series und Splat Series, Suchtreffer nennen Tripo 3.0 (September 2025), H3.1 und Smart Mesh P1.0 (März/April 2026). Keine Anbieterseite fasst das zusammen.
- Sloyd: ob es eine öffentliche API mit Preisliste gibt. Die Preisseite nennt keine, Dritte sagen, API gebe es nur über Studio- und Enterprise-Absprachen. Keine Entwicklerdokumentation gefunden.
- Sloyd: die Ausgabeformate der Bezahlstufen über GLB und OBJ hinaus (Dritte nennen zusätzlich FBX) und ob PBR- oder Quad-Ausgabe unterstützt wird.
- CSM (Common Sense Machines): jeder heutige Preis, jede Modellfassung und jede offizielle Aussage zum Weiterbetrieb oder zur Abschaltung. Die Domänen csm.ai, www.csm.ai und 3d.csm.ai lösen nicht mehr auf; eine Abschaltmeldung habe ich trotz mehrerer Suchen (deutsch und englisch) nicht gefunden. Der in einem Suchtreffer genannte Satz „Cube shutting down January 5th, 2026" ließ sich keiner CSM-Quelle zuordnen und könnte ein anderes Produkt namens Cube meinen — bewusst nicht übernommen.
- Alpha3D: sämtliche Preise. www.alpha3d.io und www.alpha3d.io/pricing liefern beim Abruf nur die Überschrift „Alpha3D - The full AI 3D pipeline, in one place", der Rest wird per JavaScript nachgeladen. Suchtreffer nennen Tester 5 €, Basic 16 €, Creator 100 €, Creator Pro 150 € im Monat, 20 % Rabatt bei Jahreszahlung, Tester mit 90 3D-Guthaben plus 1.000 Token — nichts davon habe ich an einer geholten Seite gesehen, deshalb keine Faktenkarte.
- Alpha3D: API, Ausgabeformate, Rechte an den Ergebnissen und aktuelle Modellfassung — aus demselben Grund nicht prüfbar. Auch pricingpagehub.com lieferte nur einen Platzhalter.
- Kaedim: API-Zugang, Ausgabeformate (Dritte nennen FBX, OBJ, GLTF), Quad-Topologie und Rechte an den Ergebnissen. Auf den geholten Seiten kaedim3d.com und kaedim3d.com/plans steht dazu nichts; die Seite verweist auf docs.kaedim3d.com, die ich nicht geholt habe. Zudem fehlt für alle Anbieter eine unabhängige, nachrechenbare Messung der Maßhaltigkeit in Millimetern — gefunden habe ich nur Herstellerangaben (Meshy: 97 % Slicer-Durchlaufquote; Hyper3D: „mannigfaltig, sliced ohne Fehler").

**Neu seit Anfang August:**
- Meshy 7 erschien am 10. August 2026 — mitten im fraglichen Zeitraum. Die API-Unterstützung folgte am 12. und 13. August. Jede Aussage in Solidon, die sich auf Meshy 6 als aktuellen Stand stützt, ist seit gut einer Woche veraltet.
- Meshy 7 verliert eine Fähigkeit von Meshy 6: Die Emissionskarte wird laut API-Doku bei Meshy 7 nicht mehr erzeugt. Wer vergleicht, sollte nicht annehmen, die neue Generation sei in jeder Hinsicht die reichere.
- Tripo hat P2.0 Preview mit nativer Quad-Topologie genau heute (19. August 2026) angekündigt. Quad-Ausgabe ist damit bei Meshy, Tripo und (als Beta) Hyper3D vorhanden — sie taugt als Alleinstellungsmerkmal nicht mehr.
- Meshy baut den 3D-Druck systematisch aus, nicht nebenbei: Creative-Lab-API seit 1. Juni 2026, Tastenkappen mit echtem Millimetermaßstab seit 22. Juli, und am 4. August wurde die Druckbarkeitsprüfung auf .gltf, .fbx und .stl erweitert. Der Takt liegt bei etwa einer Erweiterung pro Woche.
- Meshy druckt und versendet inzwischen selbst — Creative Lab liefert fertige Objekte in neun Länder, darunter Deutschland. Das ist ein Schritt vom Softwareanbieter zum Fertigungsdienst und trifft Solidons Endnutzer unmittelbar.
- Die Meshy-Formlabs-Anbindung (seit 8. April 2026) prüft Wandstärken (FDM mindestens 1,2 mm, Harz mindestens 0,3 mm), während Meshys eigener Prüf-Endpunkt Wandstärke, Überhänge und Maßstab ausdrücklich NICHT prüft. Die Lücke, auf die sich Solidon beruft, ist also kleiner geworden, aber sie besteht noch — allerdings nur außerhalb des Formlabs-Wegs.
- CSM ist als Vergleichsgröße praktisch verschwunden: Alphabet hat das Unternehmen am 24. Januar 2026 übernommen, und die Domänen lösen heute nicht mehr auf. Wo Solidon CSM als Mitbewerber führt, sollte das geprüft und wahrscheinlich gestrichen werden.
- Luma Genie ist seit dem 1. Januar 2026 offiziell eingestellt — Lumas eigene Angabe. Auch dieser Vergleichspunkt ist entfallen.
- Die Hyper3D-Dokumentation ist umgezogen (developer.hyper3d.ai leitet auf docs.hyper3d.ai) und hat die Pfade geändert; alte Verweise auf die Gen-2-Spezifikation laufen heute in einen 404. Gespeicherte Links in Solidon-Unterlagen sind vermutlich tot.
- Der Preisabstand beim API-Zugang ist groß und für einen Vergleich in Solidon entscheidend: Meshy ab 20 $/Monat, Tripo ab 0,30 $ je texturiertem Modell ohne Abo, Hyper3D erst ab 120 $/Monat (oder 0,40 $ je Erzeugung über fal.ai). Kaedim liegt mit 400 $/Monat für 20 Guthaben in einer anderen Größenordnung.

## llm-backends

_LLM-Backends für die Agentenschicht (Ollama, lokale Modelle, OpenAI-kompatible Server, gehostete Preise) — Stand 19. August 2026_

- **Anthropic — claude-sonnet-4-5** — claude-sonnet-4-5-20250929 ist heute weiterhin ein gültiger, aktiver Modellname; die Tabelle nennt als Rückzugsdatum "Not sooner than September 29, 2026", eine Abkündigung ist bisher nicht ausgesprochen (Spalte "Deprecated": N/A).
  · Stand: Abruf 19.08.2026, Seite ohne eigenes Datum · Sicherheit: belegt
  · Anmerkung: Entscheidungsrelevant für Solidon: das Datum liegt rund sechs Wochen vor uns. Anthropic sagt zu, mindestens 60 Tage vor einem Rückzug zu benachrichtigen — eine Abkündigung müsste also spätestens jetzt kommen, sonst verschiebt sich das Datum. Im Modellüberblick steht Sonnet 4.5 bereits unter "Legacy models", nicht mehr in der Haupttabelle.
  · https://platform.claude.com/docs/en/about-claude/model-deprecations
- **Anthropic — claude-sonnet-4-5 (Alias)** — Der kurze Name claude-sonnet-4-5 ist ein Bequemlichkeits-Alias auf den datierten Schnappschuss claude-sonnet-4-5-20250929; ab der 4.6-Generation gibt es keine Aliase mehr, dort ist die datumslose ID selbst der feste Schnappschuss.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Wer in Solidon claude-sonnet-4-5 fest einträgt, trägt einen Alias ein, kein gepinntes Modell.
  · https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions
- **Anthropic — Nachfolger von Sonnet 4.5** — Aktiv sind heute claude-sonnet-5 (2 USD Eingabe / 10 USD Ausgabe je Mio. Token, 1 Mio. Kontext) und claude-sonnet-4-6 (3/15 USD); Sonnet 4.5 kostet 3/15 USD bei 200k Kontext.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Der Nachfolger ist billiger als das Modell, das er ersetzt. Ein Wechsel von 4.5 auf claude-sonnet-5 senkt die Kosten und verlängert das Kontextfenster.
  · https://platform.claude.com/docs/en/about-claude/models/overview
- **Anthropic — API-Parameter** — temperature, top_p und top_k sind ab Claude Opus 4.7 abgekündigt: ein Nicht-Standardwert liefert einen 400-Fehler.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Trifft Solidon direkt, falls die Agentenschicht temperature fest mitsendet. Bei Sonnet 4.5/4.6 noch erlaubt, bei den neuen Modellen nicht.
  · https://platform.claude.com/docs/en/about-claude/model-deprecations
- **Ollama** — Aktuelle Fassung ist v0.32.14; der Atom-Feed datiert sie auf den 16.08.2026, die Releases-Übersicht auf den 15.08.2026.
  · Stand: Abruf 19.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Datumsabweichung zwischen Feed und Übersichtsseite um einen Tag; die Fassungsnummer stimmt in beiden.
  · https://github.com/ollama/ollama/releases.atom
  · https://github.com/ollama/ollama/releases
- **Ollama — Kontextfenster** — Die Standard-Kontextlänge ist seit 2026 nicht mehr fest 4096, sondern nach VRAM gestaffelt: "< 24 GiB VRAM: 4k context, 24-48 GiB VRAM: 32k context, >= 48 GiB VRAM: 256k context".
  · Stand: Abruf 19.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Widerspruch in Ollamas eigener Doku: die FAQ-Seite (https://docs.ollama.com/faq) behauptet weiterhin "By default, Ollama uses a context window size of 4096 tokens". Der Quelltext gibt der context-length-Seite recht: OLLAMA_CONTEXT_LENGTH hat den Vorgabewert 0 mit dem Kommentar "(default: 4k/32k/256k based on VRAM)". Für Solidon heißt das: auf einer 16-GB-Karte bekommt der Nutzer stillschweigend 4k, ohne dass irgendwo eine Fehlermeldung erscheint.
  · https://docs.ollama.com/context-length
  · https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go
- **Ollama — Kontextfenster setzen** — num_ctx wird über das options-Objekt von /api/chat und /api/generate gesetzt; serverweit über OLLAMA_CONTEXT_LENGTH beim Start; dauerhaft je Modell über PARAMETER num_ctx in einem Modelfile plus ollama create.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Desktop-App hat zusätzlich einen Schieberegler in den Einstellungen.
  · https://docs.ollama.com/api/chat
  · https://docs.ollama.com/context-length
- **Ollama — OpenAI-Endpunkt** — Über /v1/chat/completions lässt sich die Kontextlänge nicht setzen: die OpenAI-Spezifikation kennt keinen solchen Parameter, Ollama verweist auf den Umweg über ein eigenes Modelfile mit PARAMETER num_ctx und ollama create.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Wenn Solidon Ollama über den OpenAI-kompatiblen Weg anspricht, ist das Kontextfenster nicht steuerbar — der native /api/chat-Weg ist der einzige, der num_ctx durchreicht.
  · https://docs.ollama.com/openai
- **Ollama — OpenAI-Endpunkt** — /v1/chat/completions unterstützt tools, aber tool_choice, logprobs, logit_bias und n werden nicht unterstützt.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Erzwungener Werkzeugaufruf (tool_choice: "required") ist über Ollama also nicht möglich. Wer das braucht, muss über den Systemprompt gehen oder LM Studio nehmen (dort seit 0.3.15 unterstützt).
  · https://docs.ollama.com/openai
- **Ollama — Endpunkte** — Unterstützt werden /v1/chat/completions, /v1/completions, /v1/embeddings, /v1/models und /v1/responses (die OpenAI Responses API, nur nicht-zustandsbehaftet, eingeführt in v0.13.3).
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Seit v0.32.11 kann die Responses-API zusätzlich Websuche.
  · https://docs.ollama.com/openai
- **Ollama — /api/chat** — Der Parameter think akzeptiert true/false oder die Stufen "low", "medium", "high", "max"; tools nimmt Funktionsdefinitionen entgegen; stream steht standardmäßig auf true.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Denkstufen sind neu gegenüber dem Stand Mai 2026 und für Solidons Agentenschicht ein Stellhebel gegen lange Latenz.
  · https://docs.ollama.com/api/chat
- **Ollama — Empfehlung Kontext** — Ollama empfiehlt für Websuche, Agenten und Coding-Werkzeuge mindestens 64.000 Token Kontext; die belegte Länge lässt sich mit ollama ps prüfen.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Steht in direktem Widerspruch zum Vorgabewert von 4k auf einer 16-GB-Karte.
  · https://docs.ollama.com/context-length
- **Ollama — Werkzeugaufrufe** — Werkzeuge werden als JSON-Schemata übergeben; bei gestreamten Antworten müssen thinking, content und tool_calls aus allen Teilstücken eingesammelt und gemeinsam mit den Werkzeugergebnissen in die Folgeanfrage zurückgegeben werden.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Seite nennt keine ausdrückliche Liste werkzeugfähiger Modelle, sie zeigt nur qwen3 in den Beispielen.
  · https://docs.ollama.com/capabilities/tool-calling
- **Ollama — Modellkatalog mit Werkzeugfähigkeit** — Die Filterung auf die Fähigkeit "tools" liefert heute vorne: glm-5.2, deepseek-v4-flash, kimi-k3, qwen3.8 (27B), muse-glimmer (30B), nemotron-3.5-lightning (30B MoE), gemma4 (12B/26B/31B), qwen3.6 (27B/35B), glm-5.1, minimax-m2.7, nemotron-3-super, ornith (9B/35B), minimax-m3, nemotron3 (33B), lfm2 (24B), kimi-k2.7-code, granite4.1 (3B/8B/30B), mistral-medium-3.5 (128B), kimi-k2.6, deepseek-v4-pro.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Bemerkenswert: llama3.x, mistral, devstral und gpt-oss stehen nicht mehr vorne in dieser Liste. Das Feld hat sich seit Mai 2026 vollständig umgeschlagen.
  · https://ollama.com/search?c=tools
- **Qwen3.8-27B** — Am 14.08.2026 veröffentlicht, 27,8 Mrd. Parameter, Apache 2.0, nativ 262.144 Token Kontext (bis 1 Mio. mit RoPE-Skalierung), Text/Bild/Video, Denkmodus standardmäßig an und je Anfrage abschaltbar.
  · Stand: Modellkarte, Abruf 19.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Der Ollama-Tag qwen3.8:27b ist 18 GB groß und trägt die Fähigkeiten vision, tools und thinking — läuft damit auf einer 24-GB-Karte, nicht auf 16 GB.
  · https://huggingface.co/Qwen/Qwen3.8-27B
  · https://ollama.com/library/qwen3.8
- **Muse Glimmer 30B (Meta)** — Meta hat am 10.08.2026 Muse Glimmer veröffentlicht: ~30 Mrd. Parameter, Apache 2.0, ausdrücklich "tuned for tool use" mit "reliable tool-calling", gedacht für eine einzelne GPU; Meta nennt MCP Atlas 75,5, GAIA2 43,3 und τ³-Banking 23,5.
  · Stand: Meta-Modellseite, Abruf 19.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Selbstauskunft des Herstellers, keine unabhängige Messung. Der Ollama-Tag muse-glimmer:30b ist 18 GB groß bei 128K Kontext, Fähigkeiten vision/tools/thinking — der derzeit stärkste Kandidat für Solidons lokalen Weg auf 24 GB VRAM.
  · https://developer.meta.com/ai/models/muse-glimmer/
  · https://ollama.com/library/muse-glimmer
  · https://ollama.com/blog
- **NVIDIA Nemotron 3.5 Lightning** — Am 11.08.2026 bei Ollama erschienen: 30 Mrd. Parameter als Mixture-of-Experts mit 3 Mrd. aktiven Parametern, bis 1 Mio. Token Kontext, ausdrücklich für dauerlaufende Agenten mit Werkzeugaufrufen gebaut.
  · Stand: 11.08.2026 · Sicherheit: belegt
  · Anmerkung: Der Tag nemotron-3.5-lightning:30b ist 25 GB groß und passt damit nicht auf eine 24-GB-Karte; die MLX-Variante ist 23 GB bei 256K Kontext. Ollama nennt keine VRAM-Zahl.
  · https://ollama.com/blog/nemotron-3-5-lightning
  · https://ollama.com/library/nemotron-3.5-lightning
- **Gemma 4 (Google)** — Werkzeugfähig, in den Größen 12B (7,6 GB Tag, 256K Kontext), 26B (18 GB) und 31B (20 GB) sowie E2B/E4B (6,5–9,6 GB, 128K, zusätzlich Audio).
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: gemma4:12b mit 7,6 GB ist der praktikable Kandidat für 16 GB VRAM. LM Studio 0.4.10 (April 2026) verbesserte ausdrücklich die Zuverlässigkeit der Gemma-4-Werkzeugaufrufe — ein Hinweis darauf, dass sie vorher nicht zuverlässig waren.
  · https://ollama.com/library/gemma4
  · https://ollama.com/search?c=tools
- **Qwen3.6** — 27B-Tag 17 GB, 35B-Tag 24 GB, jeweils 256K Kontext, mit vision/tools/thinking; vor rund drei bis vier Monaten aktualisiert.
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: qwen3.6:27b (17 GB) ist der bequemste Treffer für 24 GB VRAM mit Reserve fürs Kontextfenster; 5,9 Mio. Pulls, also die breiteste Erprobung im Feld.
  · https://ollama.com/library/qwen3.6
- **IBM Granite 4.1** — Werkzeugfähig in 3B (2,1 GB), 8B (5,3 GB) und 30B (17 GB), je 128K Kontext, ausdrücklich für "function-calling tasks" beworben.
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: granite4.1:8b mit 5,3 GB ist der kleinste ernsthafte Werkzeugaufrufer und passt zusammen mit einem großen Kontextfenster auf 16 GB.
  · https://ollama.com/library/granite4.1
  · https://ollama.com/search?c=tools
- **gpt-oss (OpenAI)** — Unverändert seit rund zehn Monaten: gpt-oss:20b 14 GB, gpt-oss:120b 65 GB, je 128K Kontext, mit Funktionsaufrufen und strukturierter Ausgabe. Eine neuere Fassung gibt es nicht.
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: gpt-oss:20b passt mit 14 GB auf 16 GB VRAM, ist aber gemessen am August-2026-Feld ein alter Stand und steht nicht mehr in der vorderen tools-Liste.
  · https://ollama.com/library/gpt-oss
- **Devstral (Mistral)** — devstral:24b ist 14 GB groß bei 128K Kontext und seit rund einem Jahr nicht aktualisiert; ein Devstral 2 ist auf der Ollama-Seite nicht zu finden.
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: unsicher
  · Anmerkung: Sekundärquellen sprechen von einem "Devstral-2 22B"; auf Mistrals oder Ollamas eigenen Seiten habe ich das nicht bestätigt gefunden. Nicht als belegt behandeln.
  · https://ollama.com/library/devstral
- **Llama 3.3 / Mistral Small** — llama3.3:70b ist 43 GB groß (128K, tools) und seit einem Jahr unverändert; mistral-small3.2 (24B) ist ebenfalls rund ein Jahr alt und wird für "enhanced function calling" beworben.
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Llama 3.3 70B passt weder auf 16 noch auf 24 GB. Die Llama-Linie hat 2026 keinen Nachfolger bekommen — Meta ist stattdessen mit Muse Glimmer zurückgekommen.
  · https://ollama.com/library/llama3.3
  · https://ollama.com/search?q=mistral
- **llama.cpp** — Neuester Nightly-Bau ist b10499 vom 18.08.2026; seit dem 17.08.2026 gibt es zusätzlich semantische Fassungen v0.1.0, v0.1.1 und v0.1.2, wobei die Anmerkung lautet: "Semantic versioning is still work in progress".
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Für Solidon relevant, falls eine Mindestfassung dokumentiert werden soll: bis vor drei Tagen gab es nur Baunummern, jetzt kommt ein zweites Schema dazu.
  · https://github.com/ggml-org/llama.cpp/releases.atom
  · https://github.com/ggml-org/llama.cpp/releases
- **llama.cpp — Werkzeugaufrufe** — Funktionsaufrufe im OpenAI-Stil werden mit dem Flag --jinja aktiviert. Native Handler nennt die Doku für "Llama 3.1 / 3.3 (including builtin tools support), Llama 3.2, Functionary v3.1 / v3.2, Hermes 2/3, Qwen 2.5, Qwen 2.5 Coder, Mistral Nemo, Firefunction v2, Command R7B, DeepSeek R1"; alles andere fällt auf ein generisches Format zurück.
  · Stand: Abruf 19.08.2026 (Doku im master-Zweig) · Sicherheit: belegt
  · Anmerkung: Die Modellliste ist erkennbar veraltet (Qwen 2.5, Llama 3.x) und deckt keines der August-2026-Modelle ab. Parallele Werkzeugaufrufe sind standardmäßig aus und müssen mit "parallel_tool_calls": true angefordert werden. Starke KV-Quantisierung (-ctk q4_0) verschlechtert die Werkzeugaufrufe deutlich.
  · https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md
- **llama.cpp — Anthropic-kompatibler Endpunkt** — Seit dem 19.01.2026 stellt llama-server POST /v1/messages im Anthropic-Format bereit, samt tool_use- und tool_result-Blöcken, Streaming mit Anthropic-SSE-Ereignissen und /v1/messages/count_tokens; intern wird nach OpenAI umgesetzt.
  · Stand: 19.01.2026 · Sicherheit: belegt
  · Anmerkung: Für Solidon architektonisch interessant: derselbe Anthropic-Client könnte auf ein lokales llama-server zeigen, statt einen zweiten Adapter zu brauchen. Der Beitrag warnt, dass Werkzeugnutzung Modelle mit eingebauter Werkzeugfähigkeit voraussetzt.
  · https://huggingface.co/blog/ggml-org/anthropic-messages-api-in-llamacpp
- **LM Studio** — Neueste Fassung ist 0.4.21 vom 12.08.2026.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · https://lmstudio.ai/changelog/lmstudio
- **LM Studio — Werkzeugaufrufe** — Werkzeuge laufen über /v1/chat/completions und /v1/responses. Native Vorlagen nennt die Doku für Qwen2.5, Llama-3.1/3.2 und Mistral/Ministral (GGUF wie MLX, in der App mit Hammer-Symbol markiert); alle übrigen Modelle bekommen einen Systemprompt mit dem Ersatzformat [TOOL_REQUEST]{...}[END_TOOL_REQUEST].
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Auch diese Liste ist veraltet und nennt kein Modell aus 2026. Das Ersatzformat funktioniert laut Doku überall, aber "results vary based on training".
  · https://lmstudio.ai/docs/developer/openai-compat/tools
- **LM Studio — API-Verlauf** — tool_choice ("auto"/"none"/"required") seit 0.3.15 (24.04.2025); Streaming der Werkzeugargumente seit 0.3.17; /v1/responses seit 0.3.29 (06.10.2025) mit previous_response_id und eigenen Werkzeugen; Anthropic-kompatibles POST /v1/messages seit 0.4.1, Systemnachrichten dort seit 0.4.15.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: LM Studio ist damit derzeit der einzige der drei lokalen Server, der tool_choice, Responses-API und Anthropic-Format zugleich anbietet.
  · https://lmstudio.ai/docs/developer/api-changelog
  · https://lmstudio.ai/changelog/lmstudio
- **vLLM** — Neueste Fassung ist v0.27.1 vom 11.08.2026, aufgesetzt auf v0.27.0 vom 10.08.2026 (561 Commits, 242 Beitragende, u. a. Kimi-K3-Unterstützung, PyTorch 2.13.0, FlashAttention 4).
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · https://github.com/vllm-project/vllm/releases.atom
  · https://github.com/vllm-project/vllm/releases
- **vLLM — Werkzeugaufrufe** — Werkzeugaufrufe brauchen zwei Flags: --enable-auto-tool-choice und --tool-call-parser. Parser gibt es für Hermes, Mistral, Llama 3.1/3.2/4, Qwen, DeepSeek, Granite, die OSS-Modelle von OpenAI sowie InternLM, Jamba, xLAM, Kimi, Hunyuan, Cohere Command, LongCat, GLM, FunctionGemma, Qwen3-Coder, Olmo 3, Gigachat 3 und Apertus; eigene Parser lassen sich über ToolParserManager registrieren.
  · Stand: Doku-Zeitstempel 23.06.2026, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: vLLM hat die mit Abstand breiteste Parser-Abdeckung, verlangt aber die ausdrückliche Wahl des Parsers je Modell — für eine Desktop-Anwendung ein Konfigurationsaufwand, den Ollama und LM Studio nicht haben.
  · https://docs.vllm.ai/en/latest/features/tool_calling.html
- **OpenAI — API-Preise** — Je Mio. Token (Eingabe / zwischengespeicherte Eingabe / Ausgabe, USD): gpt-5.6-sol 5,00 / 0,50 / 30,00; gpt-5.6-terra 2,00 / 0,20 / 12,00; gpt-5.6-luna 0,20 / 0,02 / 1,20; gpt-5.5 5,00 / 0,50 / 30,00; gpt-5.4 2,50 / 0,25 / 15,00; gpt-5.4-mini 0,75 / 0,075 / 4,50; gpt-5.4-nano 0,20 / 0,02 / 1,25; gpt-5-mini 0,25 / 0,025 / 2,00; gpt-5-nano 0,05 / 0,005 / 0,40; gpt-5.3-codex 1,75 / 0,175 / 14,00.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: openai.com/api/pricing antwortet mit 403; die Preisliste liegt jetzt unter developers.openai.com. Sekundärquellen behaupten eine Preissenkung am 30.07.2026 für terra und luna — auf OpenAIs eigener Seite steht dazu nichts, die Behauptung ist unbestätigt.
  · https://developers.openai.com/api/docs/pricing
- **Google — Gemini-Preise** — Je Mio. Token (Eingabe / Ausgabe, USD, bezahlte Stufe): Gemini 3.7 Flash 0,75 / 3,75 bis 31.12.2026, danach 1,50 / 7,50; Gemini 3.6 Flash ebenso; Gemini 3.5 Flash 1,50 / 9,00; Gemini 3.5 Flash-Lite 0,30 / 2,50; Gemini 3.1 Pro Preview 2,00 / 12,00 bis 200k Prompt, darüber 4,00 / 18,00.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Der Einführungspreis von Gemini 3.7 Flash halbiert sich zum 01.01.2027 nicht, sondern verdoppelt sich — wer heute damit kalkuliert, kalkuliert mit einem Ablaufdatum.
  · https://ai.google.dev/gemini-api/docs/pricing
- **Google — Gemini-Modellkennungen** — Aktuelles Spitzenmodell ist gemini-3.7-flash, beworben für "complex coding, agentic workflows, and reliable multi-step execution"; daneben stabil: gemini-3.6-flash, gemini-3.5-flash, gemini-3.5-flash-lite, gemini-3.1-flash-lite, gemini-2.5-flash, gemini-2.5-pro.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Seite nennt weder Kontextfenster je Modell noch eine Liste, welche Modelle Funktionsaufrufe können — Funktionsaufrufe werden nur allgemein als API-Fähigkeit geführt.
  · https://ai.google.dev/gemini-api/docs/models
- **Mistral — API-Preise** — Je Mio. Token (Eingabe / Ausgabe, USD): Mistral Medium 3.5 1,50 / 7,50; Mistral Small 4 0,15 / 0,60; Mistral Large 3 0,50 / 1,50; Codestral 0,30 / 0,90; Ministral 3 (3B) 0,10 / 0,10, (8B) 0,15 / 0,15, (14B) 0,20 / 0,20; GLM 5.2 über Mistral 1,40 / 4,40.
  · Stand: Abruf 19.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Die Übersichtsseite nennt für Mistral Large denselben Preis (0,50 / 1,50), beide Mistral-Seiten stimmen überein. Auffällig: Mistral Large 3 ist billiger als Medium 3.5.
  · https://mistral.ai/pricing/api
  · https://mistral.ai/pricing
- **DeepSeek — API-Preise** — Je Mio. Token in USD: DeepSeek-V4-Flash Eingabe bei Cache-Treffer 0,007 (Nebenzeit) / 0,014, Cache-Fehltreffer 0,22 / 0,44, Ausgabe 0,66 / 1,32. DeepSeek-V4-Pro: 0,022 / 0,044, 0,66 / 1,32, Ausgabe 1,98 / 3,96. Beide bis 1 Mio. Token Kontext und bis 384k Ausgabe.
  · Stand: Abruf 19.08.2026 · Sicherheit: unsicher
  · Anmerkung: Die Zeitangabe der Seite las sich beim Abruf widersprüchlich ("Peak hours are 01:00-04:00 and 06:00-10:00 UTC (all other hours are off-peak)" bei gleichzeitig "Off-peak rates are half of the peak rates") — die Zuordnung Haupt-/Nebenzeit vor einer Kalkulation nachprüfen. Die Preishöhe selbst ist von der Anbieterseite.
  · https://api-docs.deepseek.com/quick_start/pricing
- **xAI — Grok-Preise** — Je Mio. Token (Eingabe / zwischengespeichert / Ausgabe, USD): grok-4.6 2,00 / 0,50 / 6,00 unter 200k Prompt, darüber 4,00 / 1,00 / 12,00, 500k Kontext; grok-4.5 2,00 / 0,30 / 6,00; grok-4.3 1,25 / 0,20 / 2,50 bei 1 Mio. Kontext; grok-build-0.1 1,00 / 0,20 / 2,00 bei 256k.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Seite sagt nicht, welche Modelle Funktionsaufrufe unterstützen. Achtung bei der Staffel: ab 200k Token wird die ganze Anfrage zum höheren Satz abgerechnet.
  · https://docs.x.ai/docs/models
- **OpenRouter** — OpenRouter nimmt 5,5 % (mindestens 0,80 USD) auf Guthabenkäufe per Stripe, 5 % bei Kryptozahlung; bei eigenen Anbieterschlüsseln (BYOK) 5 % auf die Nutzung oberhalb eines Freibetrags von 25.000 USD Listenpreis-Inferenz im Monat (Enterprise: 200.000 USD).
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Für eine Desktop-Anwendung mit Schlüssel des Nutzers ein realistischer vierter Weg: ein Schlüssel, viele Modelle. Der Aufschlag trifft den Nutzer beim Aufladen, nicht je Anfrage.
  · https://openrouter.ai/docs/faq
- **MCP Atlas (Scale) — Werkzeugaufruf-Benchmark** — Bestenliste zum Abruf: Muse Spark 1.1 88,10 %, Claude Opus-5 (xhigh) 85,80 %, Gemini-3.5-Flash (high) 83,60 %, Claude Fable 5 83,30 %, Kimi-K3 (max) 82,30 %, GPT-5.6 (sol) 81,80 %, bis hinunter zu Claude Haiku-4-5 mit 40,20 % bei 26 Einträgen.
  · Stand: Seite nennt 08.04.2026 als letzte Aktualisierung · Sicherheit: unsicher
  · Anmerkung: Kein offen gewichtetes, lokal lauffähiges Modell ist in der Liste ausgewiesen — der Vergleich hilft also nur für die gehosteten Wege. Sekundärquellen nennen Juni 2026 als Stand, die Seite selbst April 2026; Widerspruch nicht auflösbar.
  · https://labs.scale.com/leaderboard/mcp_atlas
- **Ollama v0.32.10 — Standardwerte** — Mit v0.32.10 (12./13.08.2026) wurde der Vorgabewert von repeat_penalty von 1,1 auf 1,0 geändert; außerdem wurde eine Umgehung der Blob-Prüfung bei OCI-Manifesten mit geteilten Digests behoben.
  · Stand: 12.–13.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Änderung von repeat_penalty verändert reproduzierbare Ausgaben still — relevant, wenn Solidon Determinismus gegen Ollama prüft. Der Blob-Fix ist eine Sicherheitskorrektur beim Modellbezug.
  · https://github.com/ollama/ollama/releases.atom

**Nicht belegbar:**
- Zuverlässigkeit der Werkzeugaufrufe je lokalem Modell unter 35B: gesucht auf der Berkeley Function Calling Leaderboard (https://gorilla.cs.berkeley.edu/leaderboard.html — Tabelle wurde nicht mitgeliefert, nur Rahmentext; Stand angeblich BFCL V4 vom 12.04.2026) und auf MCP Atlas (dort kein offen gewichtetes Modell ausgewiesen). Es gibt derzeit keine von mir geprüfte, neutrale Rangliste, die sagt, welches lokale Modell Werkzeuge zuverlässig aufruft. Alles, was dazu kursiert, sind Herstellerangaben oder Blogs.
- VRAM-Bedarf der neuen Modelle: weder Meta (https://developer.meta.com/ai/models/muse-glimmer/) noch NVIDIA/Ollama (https://ollama.com/blog/nemotron-3-5-lightning) nennen eine VRAM-Zahl. Die hier angegebenen GB-Werte sind Dateigrößen der Ollama-Tags, nicht der Speicherbedarf im Betrieb — dazu kommt der KV-Cache, der beim empfohlenen 64k-Kontext erheblich ist.
- Offizielles Kontextfenster und offizielles Erscheinungsdatum von Muse Glimmer: Metas eigene Modellseite nennt beides nicht. Der Ollama-Tag zeigt 128K, Sekundärquellen nennen 131.072 und den 10.08.2026 — von Meta selbst nicht bestätigt.
- Existenz eines "Devstral 2" bzw. "Devstral-2 22B": auf https://ollama.com/library/devstral steht nur devstral:24b, seit rund einem Jahr unverändert. Nur Blogs behaupten eine zweite Fassung. Nicht als vorhanden annehmen.
- Eine neuere gpt-oss-Fassung: https://ollama.com/library/gpt-oss zeigt seit rund zehn Monaten dieselben Tags. Ein gpt-oss 2 ist nicht auffindbar.
- Ollamas Standard-Kontextlänge in der eigenen FAQ: https://docs.ollama.com/faq behauptet weiterhin fest 4096 Token und widerspricht damit https://docs.ollama.com/context-length und dem Quelltext. Welche Seite gepflegt wird, ist nicht feststellbar — der Quelltext gibt der context-length-Seite recht.
- Ob Ollamas OpenAI-Endpunkt inzwischen tool_choice unterstützt: https://docs.ollama.com/openai führt es ausdrücklich unter den nicht unterstützten Parametern. Ein Änderungseintrag, der das aufhebt, war in den Fassungsanmerkungen nicht zu finden — die Doku könnte aber hinterherhinken.
- Behauptete OpenAI-Preissenkung am 30.07.2026 (terra minus 20 %, luna minus 80 %): nur in Sekundärquellen gefunden, auf https://developers.openai.com/api/docs/pricing steht kein Änderungsdatum. Die dort abgerufenen Preise gelten, die Vorgeschichte ist unbelegt.
- Welche Grok-Modelle Funktionsaufrufe können: https://docs.x.ai/docs/models nennt Preise und Kontext, aber keine Fähigkeitenspalte.
- Preise weiterer gehosteter Anbieter, die für einen Desktop-Schlüssel in Frage kämen (Groq, Together AI, Fireworks AI, Cerebras): nicht recherchiert, keine Zahl dazu vorhanden.
- Genaue VRAM-Schwellen im Ollama-Quelltext für die Kontextstaffelung: die Dokumentation nennt "< 24 GiB / 24-48 GiB / >= 48 GiB", Sekundärquellen nennen abweichend 23 GiB und 47 GiB als tatsächliche Schwellen. Die Stelle im Quelltext, die das entscheidet, habe ich nicht gefunden (server/sched.go enthält nur die Rückstufung bei Speichermangel: 32768 → 4096 → 0).
- Ob claude-sonnet-4-5 ein formelles Abkündigungsschreiben erhalten hat: in der Deprecation-Historie auf https://platform.claude.com/docs/en/about-claude/model-deprecations gibt es keinen Eintrag dazu. Der Zustand ist "Active" mit vorläufigem Rückzugsdatum, nicht "Deprecated".

**Neu seit Anfang August:**
- Meta ist am 10.08.2026 mit Muse Glimmer zurück auf offene Gewichte gegangen: 30 Mrd. Parameter, Apache 2.0, ausdrücklich auf zuverlässige Werkzeugaufrufe getrimmt, 18 GB als Ollama-Tag — damit läuft zum ersten Mal ein für Agenten gebautes Modell auf einer einzelnen 24-GB-Karte. Für Solidons lokalen Weg ist das der wichtigste Fund der letzten drei Wochen.
- Qwen3.8-27B kam am 14.08.2026 (Apache 2.0, 262k Kontext, 18 GB Tag) und Ollama hat innerhalb von Stunden nachgezogen — v0.32.12 bis v0.32.14 drehen sich fast ausschließlich um dieses Modell. Wer eine Modellliste in Solidon fest einträgt, veraltet derzeit im Wochentakt.
- NVIDIA Nemotron 3.5 Lightning (11.08.2026, 30B MoE mit 3B aktiv, 1 Mio. Kontext) ist ausdrücklich für dauerlaufende Agenten mit Werkzeugaufrufen gebaut — mit 25 GB Tag aber knapp jenseits einer 24-GB-Karte.
- llama.cpp hat am 17.08.2026 angefangen, semantische Fassungen zu vergeben (v0.1.0 bis v0.1.2, parallel zu den Baunummern b104xx). Eine dokumentierte Mindestfassung in Solidon müsste sich jetzt entscheiden, welches Schema sie nennt.
- Ollamas Standard-Kontextlänge hängt inzwischen vom VRAM ab (4k unter 24 GiB, 32k bis 48 GiB, 256k darüber). Auf einer 16-GB-Karte bekommt ein Solidon-Nutzer also still 4096 Token, während Ollama selbst für Agenten mindestens 64.000 empfiehlt. Wenn Solidon num_ctx nicht ausdrücklich setzt, bricht die Agentensitzung auf kleiner Hardware ohne erkennbaren Grund ab.
- Ollama v0.32.10 (12.08.2026) hat den Vorgabewert von repeat_penalty von 1,1 auf 1,0 geändert — eine stille Änderung an der Ausgabe, die Determinismusprüfungen gegen ältere Ollama-Fassungen auseinanderlaufen lässt.
- Ollama v0.32.10 hat außerdem eine Umgehung der Blob-Verifikation bei OCI-Manifesten mit geteilten Digests geschlossen. Wer Ollama als Bezugsweg für Modelle beschreibt, sollte die Mindestfassung entsprechend hochsetzen.
- xAI hat am 12.08.2026 Grok 4.6 veröffentlicht (2 / 6 USD je Mio. Token unter 200k, 500k Kontext), vLLM 0.27.0/0.27.1 kamen am 10./11.08.2026, LM Studio 0.4.21 am 12.08.2026 — das gesamte Feld hat sich in der ersten Augusthälfte bewegt.
- claude-sonnet-4-5-20250929 ist noch aktiv, aber sein vorläufiges Rückzugsdatum (29.09.2026) liegt rund sechs Wochen vor uns. Der Nachfolger claude-sonnet-5 kostet mit 2/10 USD weniger als Sonnet 4.5 mit 3/15 USD und hat 1 Mio. statt 200k Kontext — der Wechsel ist billiger und besser, nicht bloß nötig.
- temperature, top_p und top_k liefern ab Claude Opus 4.7 einen 400-Fehler, wenn sie auf einen Nicht-Standardwert gesetzt werden. Wenn Solidons Agentenschicht temperature pauschal mitsendet, funktioniert sie mit Sonnet 4.5 und scheitert mit jedem neueren Modell.
