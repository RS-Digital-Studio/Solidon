# Faktenkarten für `konzept-organische-modellierung-2026-08.md`

Recherchiert am 19.08.2026. Jede Karte trägt ihre Quelle. Was nicht gefunden
wurde, steht unter „Nicht belegbar“ — das ist kein Freibrief, es plausibel
zu ergänzen, sondern der Grund, es im Konzept offen zu lassen.

## organische-modellierung

_Organische Modellierung, Sculpting und Skelett-Posing — Stand 19. August 2026_

- **Blender** — Blender 5.2 LTS ist die aktuelle Fassung, veröffentlicht am 14. Juli 2026, mit zwei Jahren LTS-Pflege. Lizenz: GPL-2.0-or-later (Binärpakete GPLv3 or later wegen eingebundener Apache-Bibliotheken).
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: blender.org antwortet dem Abrufwerkzeug mit 403; die Seite war nur per curl mit Browser-Kennung lesbar. GPL heißt für Solidon: nur externer Aufruf, kein Einbinden (Regel 15).
  · https://www.blender.org/download/releases/5-2/
  · https://en.wikipedia.org/wiki/Blender_(software)
- **Blender Sculpt-Mode 5.2** — Neu in 5.2: „Add Primitive" setzt Würfel, Kegel, Zylinder, UV- und Ico-Kugeln direkt im Sculpt-Mode ein; der neue „Scene Project"-Pinsel legt Flächen auf benachbarte Geometrie; der Voxel-Remesher interpoliert jetzt Vertex- und Corner-Attribute statt den Wert des nächstgelegenen Punkts zu übernehmen; die Rückfrage vor dem Einschalten von Dyntopo entfällt.
  · Stand: 2026-07-14 · Sicherheit: belegt
  · Anmerkung: Wörtlich: „The voxel remesher now interpolates vertex and corner attributes, instead of taking the value of the nearest point in the original mesh." — genau der Fehler, den ein selbstgebauter VDB-Remesh beim ersten Anlauf ebenfalls macht.
  · https://www.blender.org/download/releases/5-2/
- **Blender 3D Print Toolbox** — Fassung 1.4.1 vom 5. August 2026, Lizenz „GNU General Public License v3.0 or later", 595.081 Downloads. Funktionsumfang laut Eintrag: Volumen und Oberfläche berechnen, fehlerhafte Geometrie prüfen und mit „Make Manifold" reparieren, „Hollow"-Werkzeug für gleichmäßige Wandstärke bei komplexen Formen, Ausrichten, Skalieren, Export nach STL/PLY/OBJ.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Der Eintrag nennt KEINE Wandstärkenprüfung mehr — die im Netz kursierenden Beschreibungen einer „wall thickness analysis" decken sich nicht mit der offiziellen Beschreibung. GPL: nicht kopierbar, nur als Vorbild lesbar.
  · https://extensions.blender.org/add-ons/print3d-toolbox/
- **ZBrush (Maxon)** — Aktuelle Fassung ist ZBrush 2026.2, erschienen am 15. April 2026; neu sind native Unterstützung für Qualcomm Snapdragon (ARM/Windows), direkte Übergabe an Substance 3D Painter, ein Intensitätsregler für Polypaint und Tastenkürzel-Austausch zwischen Desktop und iPad.
  · Stand: 2026-04-15 · Sicherheit: unsicher
  · Anmerkung: Nur Fachpresse. maxon.net liefert Preise und Fassungsnummern per JavaScript nach und war nicht auslesbar.
  · https://www.cgchannel.com/2026/04/maxon-releases-zbrush-2026-2-and-zbrush-for-ipad-2026-2/
- **ZBrush Preis** — ZBrush-Abonnement kostet 49 USD im Monat oder 399 USD im Jahr und schließt ZBrush für iPad ein; der autorisierte Händler Novedge führt „ZBrush – 1-Year Subscription" mit 399 USD. ZBrush für iPad allein: Grundfassung kostenlos, voller Umfang 9,99 USD im Monat oder 89,99 USD im Jahr.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: Wörtlich CG Channel: „ZBrush subscriptions cost $49/month or $399/year, and include ZBrush for iPad."
  · https://www.cgchannel.com/2026/04/maxon-releases-zbrush-2026-2-and-zbrush-for-ipad-2026-2/
  · https://novedge.com/products/buy-zbrush-subscription
- **ZBrush Lizenzmodell** — Maxon selbst schreibt: „Perpetual licenses for ZBrush were discontinued in December 2023." ZBrush ist nur noch als ZBrush-Abonnement oder als Teil von Maxon One zu haben, beides monatlich oder jährlich, beides inklusive ZBrush für iPad.
  · Stand: 2026-03-02 · Sicherheit: belegt
  · Anmerkung: Der Artikel trägt das Änderungsdatum 2. März 2026.
  · https://support.maxon.net/hc/en-us/articles/4716058124444-How-do-I-subscribe-to-ZBrush
- **Nomad Sculpt (Desktop)** — Die Desktop-Fassung steht auf nomadsculpt.com als 2.9.27 für Windows und macOS bereit (plus Web ohne offiziellen Rückhalt), kostenlos zum Ausprobieren. Kauf: einmalig etwa 35 USD, ein Lizenzschlüssel für zwei Geräte; Offline-Kulanz 15 Tage. Steam ist angekündigt („Working on it.").
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Es gibt außerdem eine Erweiterung „Nomad Blender Link" über ein eigenes Blender-Repository (https://nomadsculpt.com/blender/index.json).
  · https://nomadsculpt.com/
- **Nomad Sculpt (iOS)** — Im App Store kostet Nomad Sculpt 19,99 USD; der „Quad Remesher" ist ein In-App-Kauf für 15,99 USD („Remesh your object automatically with a quad dominant mesh"). Die dort angezeigte Fassung ist 2.8 vom 23.12.2025.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Die App-Store-Angabe 2.8 widerspricht der Desktop-Fassung 2.9.27; welche mobile Fassung heute aktuell ist, ließ sich nicht klären.
  · https://apps.apple.com/us/app/nomad-sculpt/id1519508653
- **Plasticity** — Plasticity 2026.1 erschien am 17. April 2026. Lizenzen sind unbefristet und geräteseitig gebunden: Indie 175 USD, Studio 299 USD, jeweils mit 12 Monaten freien Aktualisierungen. Plattformen: Windows 10+, Ubuntu 22.04+, macOS 12.0+.
  · Stand: 2026-04-17 · Sicherheit: unsicher
  · Anmerkung: plasticity.xyz antwortet mit 403. Plasticity ist NURBS-/CAD-nah („CAD for artists"), kein Sculpting-Programm — Studio bringt mit „PolySplines" die Rückrichtung: Polygonnetz zu editierbarer NURBS-Fläche mit G2-Stetigkeit.
  · https://www.cgchannel.com/2026/04/plasticity-2026-1-is-out/
- **3DCoat** — 3DCoat 2026 (Fassung 2026.11 am 23. Juli 2026 als produktionsreif erklärt) kostet als persönliche Dauerlizenz 379 Euro, im Abonnement 20,80 Euro monatlich oder 169,85 Euro jährlich; 3DCoatTextura 2026 kostet 159 Euro (vorher 119 Euro). Kern der Fassung ist ein GPU-beschleunigtes, knotenbasiertes Textursystem.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: Dauerlizenz mit 12 Monaten freien Aktualisierungen, danach 45 Euro (ab Monat 13) bzw. 90 Euro (ab Monat 25). Für den Druck einschlägig: volumetrische Texturen erzeugen laut CG Channel Voxel-Gitter im Modellinneren als Stützstruktur, dazu ein „Splitter"-Werkzeug zum Zerlegen.
  · https://3dcoat.com/buy/
  · https://www.cgchannel.com/2026/07/pilgway-releases-3dcoat-2026-and-3dcoattextura-2026/
- **3DCoatPrint** — Pilgway gibt eine kostenlose Fassung „3DCoatPrint" heraus: Voxel-Modellierung und Rendering vollständig, Beschränkung nur beim Export — die Modelle werden auf höchstens 40.000 Dreiecke reduziert und das Netz wird eigens für den 3D-Druck geglättet.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://3dcoat.com/buy/
- **Womp** — Womp ist Browser-Modellierung mit „Goop"-Geometrie plus angeschlossenem Druckdienst. Preise: Starter kostenlos, Pro 9,99 USD im Monat (jährlich 119,88 USD), Team 19,99 USD je Platz im Monat (jährlich 239,88 USD), Enterprise ab 119,99 USD je Platz. Pro enthält ausdrücklich „Hollow printing for lighter, cheaper prints", „Optimised 3D meshes + clean topology" und 10 Prozent Nachlass auf Druckaufträge.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: AI-Guthaben: 300 pro Tag (Starter), 12.000 pro Monat (Pro); als Modelle genannt sind GPT Image 1, Nano Banana 2, Hunyuan 3.0.
  · https://womp.com/pricing/
- **OpenVDB** — OpenVDB 13.0.0 erschien am 4. November 2025. Die Lizenzdatei im Projekt ist wörtlich die „Apache License / Version 2.0, January 2004" — für ein kommerzielles Produkt ohne GPL uneingeschränkt brauchbar.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://raw.githubusercontent.com/AcademySoftwareFoundation/openvdb/master/LICENSE
  · https://github.com/AcademySoftwareFoundation/openvdb
- **OpenVDB Python** — Python-Anbindungen liegen im Quellbaum (openvdb/openvdb/python, pyOpenVDBModule.cc u. a.), müssen aber selbst übersetzt werden. Auf PyPI gibt es kein Paket „openvdb"; „pyopenvdb" auf PyPI ist Fassung 0.1.4 vom 12. März 2020 von Dritten (docker_pyopenvdb), Lizenzangabe „MPL version 2.0".
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Für Solidon heißt das: VDB-Remesh in Python bedeutet eine eigene C++-Übersetzung, nicht ein pip install.
  · https://pypi.org/project/pyopenvdb/
  · https://github.com/AcademySoftwareFoundation/openvdb
- **libigl** — Das Projekt schreibt selbst: „libigl is primarily MPL2 licensed" und ergänzt „Some files contain third-party code under other licenses." Im Repository liegen zwei Lizenzdateien nebeneinander: LICENSE.MPL2 (Mozilla Public License Version 2.0) und LICENSE.GPL (GNU GPL Version 3). Das PyPI-Paket libigl 2.6.2 vom 5. März 2026 trägt den Klassifikator „Mozilla Public License 2.0 (MPL 2.0)".
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: GitHubs Lizenzerkennung meldet für das Repository „GPL-3.0", weil sie LICENSE.GPL findet. Wer libigl benutzt, muss pro verwendeter Datei prüfen — die Pauschalaussage trägt nicht.
  · https://libigl.github.io/
  · https://github.com/libigl/libigl
  · https://pypi.org/project/libigl/
- **PyMeshLab** — PyMeshLab steht unter GNU General Public License v3.0; das PyPI-Paket 2025.7.post1 vom 30. Januar 2026 trägt die Lizenzangabe „GPL3".
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: Damit für Solidon nach Regel 15 ausgeschlossen — die Regel nennt pymeshlab bereits namentlich, der Befund bestätigt sie 2026 unverändert.
  · https://github.com/cnr-isti-vclab/PyMeshLab
  · https://pypi.org/project/pymeshlab/
- **Instant Meshes** — Die Lizenzdatei ist ein BSD-3-Clause-Text (Copyright 2015 Wenzel Jakob, Daniele Panozzo, Marco Tarini, Olga Sorkine-Hornung) mit dem Zusatz „You are under no obligation whatsoever to provide any bug fixes, patches, or upgrades". Kommerziell ohne GPL benutzbar. Letzter Commit: 3. Januar 2022.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Die Abhängigkeiten unter ext/ wurden nicht einzeln geprüft.
  · https://raw.githubusercontent.com/wjakob/instant-meshes/master/LICENSE.txt
  · https://github.com/wjakob/instant-meshes
- **QuadriFlow** — Die Lizenzdatei ist derselbe BSD-3-Clause-Text (Copyright 2018 Jingwei Huang, Yichao Zhou, Matthias Niessner, Jonathan Shewchuk, Leonidas Guibas). Kommerziell ohne GPL benutzbar. Letzter Commit: 7. Dezember 2019.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Der Ordner 3rd/ mit den mitgelieferten Fremdbibliotheken wurde nicht auf Lizenzen geprüft.
  · https://raw.githubusercontent.com/hjwdzh/QuadriFlow/master/LICENSE.txt
  · https://github.com/hjwdzh/QuadriFlow
- **geogram** — geogram 1.10.0 (27. Mai 2026) steht unter „BSD 3-Clause License, Copyright (c) 2000-2022 Inria". Kommerziell ohne GPL benutzbar; die Entwicklung ist aktiv (Commits am 19. August 2026).
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://raw.githubusercontent.com/BrunoLevy/geogram/main/LICENSE
  · https://github.com/BrunoLevy/geogram
- **CGAL** — CGAL 6.2 erschien am 11. Juni 2026. Die Lizenzdatei sagt wörtlich: „The CGAL software consists of several parts, each of which is licensed under an open source license. It is also possible to obtain commercial licenses from GeometryFactory (www.geometryfactory.com) for all or parts of CGAL." und weiter: „This is either the GNU General Public License or the GNU Lesser General Public License … either version 3 of the License or (at your option) any later version."
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Es gibt keine pauschale LGPL-Antwort: die Lizenz steht in jeder einzelnen Datei.
  · https://raw.githubusercontent.com/CGAL/cgal/master/Installation/LICENSE
  · https://github.com/CGAL/cgal/releases
- **CGAL — die für Sculpting einschlägigen Pakete** — Die drei Kopfdateien, die Solidon interessieren würden, tragen alle dieselbe SPDX-Zeile „GPL-3.0-or-later OR LicenseRef-Commercial": PMP_Remeshing/…/Polygon_mesh_processing/remesh.h (isotropes Remeshing), Surface_mesh_deformation/…/Surface_mesh_deformation.h (ARAP-Verformung, also Posing) und Surface_mesh_skeletonization/…/extract_mean_curvature_flow_skeleton.h (Skelettextraktion).
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Ohne gekaufte Lizenz von GeometryFactory ist genau der Teil von CGAL, den man für Remesh, Posing und Skelett bräuchte, für Solidon gesperrt.
  · https://raw.githubusercontent.com/CGAL/cgal/master/PMP_Remeshing/include/CGAL/Polygon_mesh_processing/remesh.h
  · https://raw.githubusercontent.com/CGAL/cgal/master/Surface_mesh_deformation/include/CGAL/Surface_mesh_deformation.h
  · https://raw.githubusercontent.com/CGAL/cgal/master/Surface_mesh_skeletonization/include/CGAL/extract_mean_curvature_flow_skeleton.h
- **OpenSubdiv** — Die aktuelle Marke ist v3_7_0. Die Lizenzdatei ist NICHT schlicht Apache 2.0, sondern die „TOMORROW OPEN SOURCE TECHNOLOGY LICENSE 1.0" mit vorangestelltem Hinweis: „The Tomorrow Open Source Technology License 1.0 differs from the original Apache License 2.0 in the following manner. Section 6 ("Trademarks") is different."
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Permissiv, kein Copyleft — aber der Eintrag in Solidons Lizenzliste darf nicht „Apache-2.0" heißen.
  · https://raw.githubusercontent.com/PixarAnimationStudios/OpenSubdiv/release/LICENSE.txt
  · https://github.com/PixarAnimationStudios/OpenSubdiv/tags
- **trimesh** — trimesh 5.0.0 wurde am 1. August 2026 auf PyPI veröffentlicht, Lizenz MIT.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Betrifft Solidon unmittelbar: die Grenze `trimesh<5` in pyproject.toml ist ab jetzt eine datierte, nicht mehr bloß angekündigte Migration.
  · https://pypi.org/project/trimesh/
- **manifold3d** — manifold3d 3.5.2 erschien am 27. Juni 2026 (GitHub-Marke v3.5.2 am selben Tag), Lizenz Apache 2.0.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · https://pypi.org/project/manifold3d/
  · https://github.com/elalish/manifold/releases
- **pyacvd** — pyacvd 0.4.0 vom 8. Mai 2026, Lizenz MIT, Zweck laut Paket: „Uniformly remeshes surface meshes". Damit gibt es einen permissiven, gepflegten Weg zu gleichmäßigem Remesh in Python — clusterbasiert (ACVD), nicht VDM/Voxel.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · https://pypi.org/project/pyacvd/
  · https://github.com/pyvista/pyacvd
- **Permissive Python-Bausteine für Sculpting** — fast-simplification 0.2.0 vom 12. August 2026, MIT (Hülle um Fast-Quadric-Mesh-Simplification, ebenfalls MIT) für Dezimierung; potpourri3d 1.4.0 und robust-laplacian 1.1.0, beide vom 25. März 2026, beide MIT, für robuste Laplace-Matrizen, Geodäten und Vektor-Wärmefluss — die Grundlage für Pinsel-Abklingfunktionen entlang der Oberfläche und für Glättung.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · https://pypi.org/project/fast-simplification/
  · https://github.com/pyvista/fast-simplification
  · https://pypi.org/project/potpourri3d/
- **skeletor (Python)** — skeletor 1.7.1 vom 27. Juli 2026 — „Python 3 library to extract skeletons from 3D meshes" — steht unter „GNU General Public License v3 or later". Für Solidon nach Regel 15 ausgeschlossen.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://pypi.org/project/skeletor/
- **Mixamo (Adobe)** — Adobe beschreibt Mixamo weiterhin als kostenlos: „Mixamo online animation services are currently in a limited duration technology preview, and during that preview they are available for free, with no licensing or royalty fees, for unlimited commercial or non commercial use." Auto-Rigger und Animationsbibliothek gelten ausdrücklich nur für zweibeinige, menschenähnliche Figuren („bipedal humanoids only").
  · Stand: 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Die Adobe-Seiten waren nur über Suchauszüge greifbar — der direkte Abruf lief in eine Zeitüberschreitung. Der Betriebszustand im August 2026 ist damit nicht aus erster Hand belegt.
  · https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html
  · https://helpx.adobe.com/creative-cloud/help/mixamo-rigging-animation.html
- **UniRig** — UniRig (SIGGRAPH 2025, Tsinghua/Tripo, VAST-AI-Research) steht unter MIT License, „Copyright (c) 2025 VAST-AI-Research and contributors". Es sagt eine topologisch gültige Skeletthierarchie und Skinning-Gewichte je Vertex voraus; für die Erzeugung nennt die Anleitung „CUDA-enabled GPU with at least 8GB VRAM". Die vollständigen Modellgewichte stehen im README noch unter „Planned Future Releases".
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://raw.githubusercontent.com/VAST-AI-Research/UniRig/main/LICENSE
  · https://github.com/VAST-AI-Research/UniRig
  · https://arxiv.org/abs/2504.12451
- **SkinTokens (Nachfolger von UniRig)** — SkinTokens ist der erklärte Nachfolger von UniRig. Aufsatz „Skin Tokens: A Learned Compact Representation for Unified Autoregressive Rigging" (arXiv 2602.04805, eingereicht 4. Februar 2026, Zhang, Pu, Guo, Cao, Hu). Repository seit 8. Februar 2026, Lizenz MIT; die Gewichte auf Hugging Face tragen ebenfalls „license:mit", zuletzt geändert am 20. April 2026. Berichtet werden „98%-133% percents improvement in skinning accuracy" und 17–22 Prozent bessere Knochenvorhersage.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: Skelett und Skinning entstehen in einer einzigen autoregressiven Folge (TokenRig, Qwen3-0.6B-Architektur, GRPO-verfeinert).
  · https://github.com/VAST-AI-Research/SkinTokens
  · https://arxiv.org/abs/2602.04805
  · https://huggingface.co/VAST-AI/SkinTokens
- **RigNet** — RigNet steht unter GNU General Public License v3.0; der letzte Commit stammt vom 4. November 2024. Für Solidon nach Regel 15 ausgeschlossen — und ohnehin überholt.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://github.com/zhan-xu/RigNet
- **Anything World** — Vier Stufen: Individual kostenlos (1 Platz), Micro 50 USD im Monat (5 Plätze), Pro 250 USD im Monat (10 Plätze), Enterprise nach Absprache — alle mit „Unlimited 3D models" und „Unlimited animation". Die REST-Schnittstelle teilt sich in eine Bibliotheks-API und eine Verarbeitungs-API, die eigene Netze automatisch riggt und animiert.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: anything.world leitet dauerhaft (301) auf everythinguniver.se um.
  · https://everythinguniver.se/pricing
  · https://anything-world.gitbook.io/anything-world/api/rest-api-references
- **KI-Sculpting — Rodin Gen-2 Edit (Hyper3D/Deemos)** — Rodin Gen-2 Edit ist das einzige gefundene ausgelieferte Werkzeug, das eine bestehende Form per Textanweisung geometrisch ändert statt neu zu erzeugen: „3D Inpainting" erlaubt gezielte Änderungen in einem ausgewählten Bereich des Modells über einen maskierten Diffusionsvorgang. Beispiel im Text: Bereich eines erzeugten Stuhls markieren, „add a floral pattern to the carvings" eingeben, „within seconds, the model was updated".
  · Stand: 2026-02-09 · Sicherheit: unsicher
  · Anmerkung: Herstellereigener Blogbeitrag vom 9. Februar 2026, ohne Erscheinungsdatum und ohne Preis. Keine unabhängige Bestätigung gefunden.
  · https://hyper3d.ai/blog/rodin-gen-2
- **KI-Sculpting — Forschungsstand 2026** — Das gezielte Ändern bestehender Formen ist 2026 überwiegend Forschung. Prox-E (arXiv 2604.23774, 26. April 2026) zerlegt eine Form erst in Primitive, lässt ein Vision-Sprach-Modell diese Abstraktion bearbeiten und führt damit ein 3D-Generativmodell — „enabling fine-grained, localized modifications while preserving unchanged regions". EditVerse3D (arXiv 2607.07187, ECCV 2026) arbeitet nicht per Text, sondern mit „a coarse 3D bounding box indicating the target region, and a reference 2D image describing the desired modification". Rigel3D (arXiv 2605.13129, 13. Mai 2026) erzeugt Geometrie, Skeletttopologie, Gelenke und Skinning-Gewichte gemeinsam statt nachträglich zu riggen.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://arxiv.org/abs/2604.23774
  · https://arxiv.org/abs/2607.07187
  · https://arxiv.org/abs/2605.13129
- **KI-Sculpting — Displacement aus Text** — Text2VDM („Text to Vector Displacement Maps for Expressive and Interactive 3D Sculpting", arXiv 2502.20045, eingereicht 27. Februar 2025, überarbeitet 7. August 2025) erzeugt Sculpting-Pinsel als Vektor-Displacement-Maps aus einer Textbeschreibung, über die Verformung eines dichten ebenen Netzes mit Score Distillation Sampling. Auf der arXiv-Seite ist kein Quelltext verlinkt.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Für Solidons Displacement-Op der interessanteste Ansatz: er erzeugt einen Parameterwert (die VDM), nicht eine fertige Geometrieänderung — das passt zu Regel 2.
  · https://arxiv.org/abs/2502.20045
- **Meshy** — Meshy-6 erschien am 18. Januar 2026 und wirbt mit „smoother, more anatomically correct geometry for characters and organic models", einem Low-Poly-Modus, mehrfarbigem 3D-Druck und „Auto-rig and animate any 3D character in seconds". Ein geometrisches Bearbeiten bereits vorhandener Modelle ist auf der Ankündigungsseite nicht genannt; das ausgelieferte Bearbeitungswerkzeug „Texture Edit" ändert nur Texturen.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://www.meshy.ai/blog/meshy-6-launch
  · https://help.meshy.ai/en/articles/11936711-how-to-use-texture-edit
- **3D-Druck — Wandstärke und Entleerungslöcher (Formlabs, SLA)** — Formlabs nennt als Auslegungsgrenzen (Clear Resin, 100 µm, Form 2): getragene Wand mindestens 0,4 mm, ungetragene Wand mindestens 0,4 mm, größter ungestützter Überhang 3,0 mm, kleinster ungestützter Überhangwinkel 19° zur Waagerechten, größte waagerechte Stützspanne 21 mm (bei 5 mm breit, 3 mm dick), senkrechter Draht 0,4 mm bei 7 mm Höhe bzw. 1,5 mm bei 30 mm Höhe, kleinster Durchmesser eines Entleerungslochs 3,5 mm.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Wörtlich zum Loch: „Without drain holes of at least 3.5 mm in diameter, the part may trap resin or air and lead to a cupping blowout failure." Das sind Herstellerwerte für ein Verfahren, keine allgemeinen Regeln.
  · https://support.formlabs.com/s/article/Design-Specs
- **3D-Druck — Hohlkörper (Formlabs PreForm)** — PreForm hat ein eingebautes Aushöhlen mit einstellbarer Wandstärke. Die Regel dazu lautet wörtlich: „Model regions thinner than twice the selected Wall Thickness will not be hollowed." Und: „When hollowing a model, add drainage holes to prevent suction cups (SLA) and to prevent material from becoming trapped inside the part (SLA and SLS)."
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Die Zwei-mal-Wandstärke-Schwelle ist genau die Stelle, an der ein Aushöhlen bei organischen Formen (dünne Finger, Ohren, Hörner) still nichts tut — für Solidon ein Befund, den eine Op melden müsste.
  · https://formlabs.com/support/Hollowing-models-in-PreForm/
- **3D-Druck — organische Stützstrukturen (PrusaSlicer)** — PrusaSlicer nennt sein Baumstützverfahren „Organic supports" und beschreibt es als „our significantly improved implementation of tree supports"; eingeführt in PrusaSlicer 2.4. Einstellbar sind Maximum Branch Angle, Preferred Branch Angle, Branch Diameter, Branch Diameter Angle, Tip Diameter, Branch Distance und Branch Density.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Wörtlich: „Organic supports are easily removable, do not scar the surface, and are fast and cheap to print."
  · https://help.prusa3d.com/article/organic-supports_480131
- **Slicer-Fassungen (Stand heute)** — PrusaSlicer 2.9.6 vom 25. Juni 2026, OrcaSlicer 2.4.2 vom 7. Juli 2026, UltiMaker Cura 5.13.0 vom 28. Mai 2026.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Relevant für Solidons Slicer-Übergabe (handover.py, slicer_keys.py).
  · https://github.com/prusa3d/PrusaSlicer/releases
  · https://github.com/SoftFever/OrcaSlicer/releases
  · https://github.com/Ultimaker/Cura/releases

**Nicht belegbar:**
- Maxons eigene Preisseiten (https://www.maxon.net/en/buy und https://www.maxon.net/en/zbrush-plan-options) laden ihre Preise per JavaScript nach; aus Maxon-Quelle war kein einziger ZBrush-Preis zu lesen. Die 49 USD/Monat und 399 USD/Jahr stammen aus CG Channel und dem autorisierten Händler Novedge, nicht vom Hersteller.
- Der Betriebszustand von Mixamo im August 2026 ist nicht aus erster Hand belegt. https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html lief mehrfach in eine Zeitüberschreitung, https://www.mixamo.com/ liefert nur „Loading Mixamo". Ob Adobe den Dienst noch betreibt, weiterentwickelt oder eingestellt hat, ist damit offen.
- Welche mobile Fassung von Nomad Sculpt heute aktuell ist, blieb offen: der App Store zeigte 2.8 vom 23.12.2025, die Herstellerseite bietet Desktop 2.9.27 an. Ein Datum für die aktuelle iOS-Fassung wurde nicht gefunden.
- Für Rodin Gen-2 / Gen-2 Edit wurde weder ein Erscheinungsdatum noch ein Preis gefunden; die einzige Quelle ist ein herstellereigener Blogbeitrag. Ob „3D Inpainting" wirklich Geometrie und nicht nur Oberfläche ändert, ist damit nicht unabhängig bestätigt.
- Der Zustand von Adobe Substance 3D Modeler (eingestellt oder weiter gepflegt?) ließ sich nicht aus einer Adobe-Quelle klären. Es gibt widersprechende Aussagen aus Foren und Fachpresse; die letzte gefundene Fassungsangabe (1.22) stammt aus dem April 2025.
- Ob die Academy Software Foundation offizielle OpenVDB-Räder für PyPI herausgibt, wurde nicht geklärt. Ein Paket namens „openvdb" existiert auf PyPI nicht; „pyopenvdb" ist von Dritten und seit März 2020 unverändert.
- Die Lizenzen der mitgelieferten Fremdbibliotheken in Instant Meshes (ext/) und QuadriFlow (3rd/) wurden nicht einzeln geprüft. Die BSD-Aussage gilt nur für den jeweils eigenen Quelltext.
- Welche libigl-Dateien konkret unter GPL statt MPL2 stehen, sagt das Projekt selbst nicht: „Some files contain third-party code under other licenses. We're currently in the processes of identifying these and marking appropriately." Eine Liste gibt es nicht.
- Ob das Blender 3D Print Toolbox in Fassung 1.4.1 noch eine Wandstärkenprüfung enthält, ist offen: der offizielle Eintrag auf extensions.blender.org nennt sie nicht, mehrere Sekundärseiten behaupten sie. Das Handbuch wurde nicht geprüft.
- Für 3DCoat 2026 wurde kein Erscheinungsdatum aus Herstellerquelle bestätigt — nur die Angabe von CG Channel, 2026.11 sei am 23. Juli 2026 produktionsreif erklärt worden. Ebenso stammt die Aussage über Voxel-Gitter als Druckstützen nur von dort.
- Es wurde kein ausgeliefertes Werkzeug gefunden, das eine organische Form per Text ändert UND die Änderung als nachvollziehbaren, wiederholbaren Parametersatz herausgibt — also in einer Form, die in einen Operationsstapel passt. Alle gefundenen Verfahren geben ein neues Netz zurück.
- Zu Wandstärkenempfehlungen für organische Formen im FDM-Druck (im Unterschied zu SLA) wurde keine Primärquelle mit Zahlen gefunden. Die kursierenden 1–2 mm bzw. 2–4 mm stammen aus Blogbeiträgen, nicht aus einer Hersteller- oder Normquelle.
- Ob Anything Worlds kostenlose Stufe kommerzielle Nutzung erlaubt und welche Guthabengrenzen für das Riggen gelten, geht aus der Preisseite nicht hervor.
- Ein Preis oder Erscheinungsdatum für die Steam-Fassung von Nomad Sculpt war nicht zu ermitteln; der Hersteller schreibt zu „When steam?" nur „Working on it."
- Zu Autodesk Meshmixer und Netfabb wurde keine Aussage aus einer Autodesk-Quelle gefunden; alle Fundstellen zum Zustand 2026 sind Drittseiten.

**Neu seit Anfang August:**
- trimesh 5.0.0 ist seit dem 1. August 2026 draußen. Solidons Grenze `trimesh<5` in pyproject.toml ist damit keine vorsorgliche Klammer mehr, sondern eine datierte, offene Migration — und `check_env.py --outdated` wird sie ab sofort anzeigen.
- Die Skelett-Ecke ist in Python lizenzrechtlich zugemauert: skeletor (die naheliegende Bibliothek, 1.7.1 vom 27. Juli 2026) ist GPL-3.0-or-later, und CGALs mean-curvature-flow-Skelettierung trägt ebenfalls GPL-3.0-or-later. Für automatische Skelettierung gibt es derzeit keine gepflegte permissive Python-Bibliothek — Solidon müsste sie selbst bauen oder extern aufrufen.
- Genau die drei CGAL-Pakete, die Solidon bräuchte — isotropes Remeshing, ARAP-Verformung (Posing) und Skelettierung — tragen alle „GPL-3.0-or-later OR LicenseRef-Commercial". CGAL ist nicht pauschal LGPL; der Ausweg ist eine gekaufte Lizenz von GeometryFactory, kein anderer Paketname.
- libigl sieht auf GitHub wie GPL-3.0 aus (die Erkennung findet LICENSE.GPL), das Projekt selbst sagt „primarily MPL2", und das PyPI-Rad 2.6.2 ist als MPL-2.0 klassifiziert. Wer die Lizenzprüfung nur gegen GitHub-Metadaten fährt, bekommt hier einen falschen Alarm — oder ein falsches Entwarnen.
- OpenSubdiv ist nicht Apache-2.0, sondern die „Tomorrow Open Source Technology License 1.0" — Apache 2.0 mit geändertem Abschnitt 6 (Marken). Permissiv, aber der Eintrag in der Lizenzliste muss den echten Namen tragen.
- Die beiden Standardwerkzeuge für Quad-Remesh unter BSD sind praktisch eingefroren: Instant Meshes seit dem 3. Januar 2022, QuadriFlow seit dem 7. Dezember 2019. Wer sie benutzt, übernimmt sie.
- ZBrush hat seit Dezember 2023 keine Dauerlizenz mehr — Maxon sagt das selbst. Das Zugpferd der Branche ist reine Miete; Plasticity (175/299 USD unbefristet) und 3DCoat (379 Euro unbefristet) sind die Gegenbewegung.
- Blenders eigenes Druckwerkzeug, das 3D Print Toolbox, steht unter GPL-3.0-or-later. Selbst die Referenzumsetzung von „Aushöhlen plus Netzprüfung" ist für Solidon nur lesbar, nicht übernehmbar — und laut offiziellem Eintrag enthält sie gar keine Wandstärkenprüfung mehr.
- 3DCoat baut mit volumetrischen Texturen bereits Voxel-Gitter im Modellinneren als Druckstützen und gibt mit 3DCoatPrint eine kostenlose Voxel-Fassung heraus (Export auf 40.000 Dreiecke gedeckelt). Der Teil von Solidons Plan, der Sculpting und Druckvorbereitung verbindet, existiert dort schon.
- Die KI-Seite 2026 kann erzeugen und riggen, aber kaum ändern. Automatisches Riggen ist gelöst und permissiv verfügbar (UniRig und SkinTokens, beide MIT, Gewichte MIT); das gezielte Ändern einer vorhandenen organischen Form ist bis auf Rodin Gen-2 Edit weiterhin Forschung — und EditVerse3D arbeitet nicht einmal mit Text, sondern mit Kasten plus Referenzbild.

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
