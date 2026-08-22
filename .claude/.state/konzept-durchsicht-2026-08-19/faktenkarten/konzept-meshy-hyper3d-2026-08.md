# Faktenkarten für `konzept-meshy-hyper3d-2026-08.md`

Recherchiert am 19.08.2026. Jede Karte trägt ihre Quelle. Was nicht gefunden
wurde, steht unter „Nicht belegbar“ — das ist kein Freibrief, es plausibel
zu ergänzen, sondern der Grund, es im Konzept offen zu lassen.

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

## mcp-cad

_MCP als Fernsteuerung für CAD- und 3D-Programme (Stand 19. August 2026)_

- **Model Context Protocol — Spezifikation** — Die aktuelle Fassung der Spezifikation ist 2026-07-28, veröffentlicht am 28. Juli 2026. Sie löst 2025-11-25 ab und ist laut Projektblog die größte Überarbeitung seit dem Start.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: Der Blogeintrag nennt sie „the largest revision of the protocol since launch".
  · https://blog.modelcontextprotocol.io/posts/2026-07-28/
  · https://modelcontextprotocol.io/specification/2026-07-28/changelog
- **MCP 2026-07-28 — zustandsloser Kern** — Der Handshake initialize/notifications/initialized entfällt; jede Anfrage trägt Protokollfassung und Client-Fähigkeiten in _meta (io.modelcontextprotocol/protocolVersion, .../clientCapabilities). Fassungskonflikte antworten mit UnsupportedProtocolVersionError (SEP-2575).
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Bruch gegenüber allen älteren Clients.
  · https://modelcontextprotocol.io/specification/2026-07-28/changelog
- **MCP 2026-07-28 — Transport (Sitzungen)** — Protokollebene-Sitzungen und der Header Mcp-Session-Id fallen aus Streamable HTTP weg. tools/list, resources/list und prompts/list dürfen nicht mehr je Verbindung variieren; verbindungsübergreifender Zustand läuft über servergenerierte Handles als gewöhnliche Werkzeugargumente (SEP-2567).
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://modelcontextprotocol.io/specification/2026-07-28/changelog
- **MCP 2026-07-28 — Transport (Wiederaufnahme)** — SSE-Wiederaufnahme und Nachrichtennachlieferung (Last-Event-ID, SSE-Event-IDs) sind aus Streamable HTTP entfernt. Ein abgerissener Antwortstrom verliert die laufende Anfrage; der Client MUSS sie mit neuer Anfrage-ID neu stellen.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Für Solidon relevant: lange Operationen brauchen eigene Wiederaufnahme, der Transport hilft nicht mehr.
  · https://modelcontextprotocol.io/specification/2026-07-28/changelog
- **MCP 2026-07-28 — server/discover** — Neuer Pflicht-RPC server/discover: Server MÜSSEN ihn umsetzen und darüber unterstützte Protokollfassungen, Fähigkeiten und Identität ausweisen. Clients DÜRFEN ihn vor jeder anderen Anfrage aufrufen.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://modelcontextprotocol.io/specification/2026-07-28/changelog
- **MCP 2026-07-28 — Benachrichtigungen** — HTTP-GET-Endpunkt und resources/subscribe bzw. /unsubscribe sind durch subscriptions/listen ersetzt: ein langlebiger POST-Antwortstrom, in den sich der Client für einzelne Typen einträgt (toolsListChanged, promptsListChanged, resourcesListChanged, resourceSubscriptions). ping, logging/setLevel und notifications/roots/list_changed sind entfernt.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://modelcontextprotocol.io/specification/2026-07-28/changelog
- **MCP 2026-07-28 — Elicitation und Sampling** — Servergestartete Anfragen (roots/list, sampling/createMessage, elicitation/create) sind durch das Muster Multi Round-Trip Requests ersetzt: Der Server antwortet mit InputRequiredResult (resultType "input_required") und einem Feld inputRequests, der Client wiederholt die ursprüngliche Anfrage mit inputResponses. notifications/elicitation/complete und das Feld elicitationId sind entfernt.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Direkt einschlägig für ctx.ask — Rückfragen laufen jetzt über Wiederholung der Anfrage, nicht über einen Rückkanal.
  · https://modelcontextprotocol.io/specification/2026-07-28/changelog
- **MCP 2026-07-28 — Abkündigungen** — Roots, Sampling und Logging sind als deprecated markiert (SEP-2577); neue Umsetzungen sollen sie nicht mehr aufnehmen. Empfohlene Wege: Verzeichnisse über Werkzeugparameter statt Roots, direkte Anbindung an die LLM-API statt Sampling, stderr oder OpenTelemetry statt Logging. Es gilt eine Abkündigungsfrist von mindestens zwölf Monaten.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://modelcontextprotocol.io/specification/2026-07-28/changelog
- **MCP 2026-07-28 — Autorisierung** — Autorisierungsserver SOLLEN den iss-Parameter nach RFC 9207 mitgeben, Clients MÜSSEN ihn prüfen; Clients MÜSSEN application_type bei Dynamic Client Registration angeben und Zugangsdaten je Aussteller getrennt halten. OAuth 2.0 Dynamic Client Registration (RFC 7591) ist zugunsten von Client ID Metadata Documents abgekündigt.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://modelcontextprotocol.io/specification/2026-07-28/changelog
- **MCP 2026-07-28 — Zwischenspeicher und Header** — tools/list, prompts/list, resources/list, resources/read und resources/templates/list MÜSSEN ttlMs und cacheScope ("public"/"private") zurückgeben (CacheableResult, SEP-2549). Streamable-HTTP-POSTs brauchen die Header Mcp-Method und Mcp-Name; Werkzeuge dürfen über x-mcp-header eigene Header setzen (SEP-2243). Werkzeuglisten SOLLEN in fester Reihenfolge kommen.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://modelcontextprotocol.io/specification/2026-07-28/changelog
- **MCP — Werkzeug-Suche** — Eine Werkzeug-Suche ist bis heute nicht Teil der Spezifikation. SEP-1821 „Dynamic Tool Discovery" (tools/list mit optionalem query-Parameter, ServerCapabilities.tools.filtering) steht seit 17. November 2025 auf Status „Draft", ohne Sponsor. Daneben liegen SEP-1300 (Filter nach Gruppen/Tags) und SEP-1881 (rechtebasierte Sichtbarkeit) als Vorschläge vor.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Der Änderungsbericht von 2026-07-28 nennt keine Werkzeug-Suche. Wer viele Werkzeuge anbietet, löst das heute clientseitig.
  · https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1821
  · https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1300
  · https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1881
- **MCP — Erweiterungen (Extensions)** — 2026-07-28 führt ein formales Erweiterungsrahmenwerk ein; ClientCapabilities und ServerCapabilities bekommen ein Feld extensions. Tasks wurde aus dem Kern in die offizielle Erweiterung io.modelcontextprotocol/tasks verschoben: tasks/result entfällt zugunsten von Abfrage über tasks/get, neu ist tasks/update, tasks/list fällt weg.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://modelcontextprotocol.io/specification/2026-07-28/changelog
  · https://blog.modelcontextprotocol.io/posts/2026-07-28/
- **MCP Apps (io.modelcontextprotocol/ui)** — Am 26. Januar 2026 als erste offizielle MCP-Erweiterung veröffentlicht: Werkzeuge liefern interaktive HTML-Oberflächen, die der Host in einem abgeschotteten iframe darstellt; UI-Ressourcen werden vorab unter dem Schema ui:// angemeldet. Unterstützt von Claude (Web und Desktop), ChatGPT, Goose und VS Code Insiders.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/
  · https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx
- **MCP — Verbreitung** — Die TypeScript- und die Python-SDK haben je die Marke von einer Milliarde Gesamt-Downloads überschritten; die Tier-1-SDKs zusammen kommen auf nahezu eine halbe Milliarde Downloads pro Monat. SDKs für TypeScript, Python, Go und C# unterstützen 2026-07-28 sofort, die Rust-SDK ist in Beta.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://blog.modelcontextprotocol.io/posts/2026-07-28/
- **MCP — Trägerschaft** — Anthropic hat MCP im Dezember 2025 an die Agentic AI Foundation übergeben, einen gerichteten Fonds unter der Linux Foundation, mitgegründet von Anthropic, Block und OpenAI. OpenAI hatte MCP im März 2025 übernommen (unter anderem in der ChatGPT-Desktop-App), Google DeepMind im April 2025.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Wikipedia als Beleg; die Mitgliederliste über die drei Gründer hinaus habe ich nicht aus erster Quelle geprüft.
  · https://en.wikipedia.org/wiki/Model_Context_Protocol
- **blender-mcp (ahujasid/blender-mcp)** — 26.041 Sterne, 2.480 Forks, MIT-Lizenz, letzter Push 16. August 2026, angelegt am 7. März 2025, 13 offene Meldungen. Beschreibung: „Community plugin to control Blender 3D with any LLM of your choice."
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Die Behauptung 17.800 Sterne ist überholt — der tatsächliche Stand liegt rund 46 % darüber.
  · https://api.github.com/repos/ahujasid/blender-mcp
  · https://github.com/ahujasid/blender-mcp
- **blender-mcp — Funktionsumfang** — Szene auslesen und Objekte bearbeiten, Materialien setzen, beliebigen Python-Code in Blender ausführen, Assets beziehen. Angebunden sind Poly Haven (Modelle, Texturen, HDRI), Sketchfab, Hyper3D Rodin und Hunyuan3D. Installation über uv, MCP-Client-Konfiguration und Blender-Addon. Telemetrie ist standardmäßig an und über Umgebungsvariable oder Addon-Einstellungen abschaltbar.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Das Projekt warnt selbst: execute_blender_code führt beliebigen Python-Code aus („powerful but potentially dangerous").
  · https://github.com/ahujasid/blender-mcp
- **FreeCAD-MCP (neka-nat/freecad-mcp)** — Die verbreitetste FreeCAD-Umsetzung: 1.848 Sterne, 250 Forks, MIT-Lizenz, letzter Push 19. August 2026, 31 offene Meldungen. Wird also 2026 aktiv gepflegt.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://api.github.com/repos/neka-nat/freecad-mcp
  · https://github.com/neka-nat/freecad-mcp
- **FreeCAD-MCP (neka-nat) — Funktionsumfang** — Zwölf Werkzeuge, nicht 165: create_document, create_object, edit_object, delete_object, execute_code, insert_part_from_library, get_view, get_objects, get_object, get_parts_list, get_rpc_status, run_fem_analysis. Installation durch Kopieren des Ordners FreeCADMCP in das Addon-Verzeichnis plus uvx im Client; FreeCAD 1.0 und 1.1.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Grenzen: GUI-Operationen laufen in eine Zeitschranke und melden dann GUI_DISPATCH_STUCK; Bildschirmfotos kosten Token und sind abschaltbar; RPC hört nur auf localhost, entfernte Verbindungen brauchen ausdrückliche IP-Freigabe.
  · https://raw.githubusercontent.com/neka-nat/freecad-mcp/main/README.md
- **FreeCAD-MCP — Behauptung „165 Werkzeuge über 15 Module"** — Diese Zahl stammt aus sergiudanstan/freecad-mcp (TypeScript, MIT). Das Repositorium hat 6 Sterne, 1 Fork, wurde am 7. März 2026 angelegt und zuletzt am 8. März 2026 bewegt — drei Commits, keine offenen Meldungen oder Pull Requests. Es ist damit keine tragfähige Vergleichsgröße.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Modulaufteilung laut README: Document 7, Primitives 11, Operations 17, Sketcher 12, Part Design 10, Import/Export 16 und weitere, dazu Mesh, FEM, BIM. GUI-Modus über Socket auf localhost:12345, Rückfall auf freecadcmd headless; braucht FreeCAD 0.21+.
  · https://api.github.com/repos/sergiudanstan/freecad-mcp
  · https://github.com/sergiudanstan/freecad-mcp
- **FreeCAD-MCP (spkane/freecad-addon-robust-mcp-server)** — Zweitgrößte FreeCAD-Umsetzung nach Sternen: 188 Sterne, 45 Forks, MIT-Lizenz, angelegt 3. Januar 2026, letzter Push 11. Mai 2026. Liefert Server plus „MCP Bridge"-Workbench als FreeCAD-Addon.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Seit Mai 2026 ohne Push — Pflegezustand offen.
  · https://api.github.com/repos/spkane/freecad-addon-robust-mcp-server
- **FreeCAD-MCP (contextform/freecad-mcp)** — 112 Sterne, 24 Forks, keine Lizenz angegeben, angelegt 8. August 2025, letzter Push 15. August 2025 — seit einem Jahr unbewegt und ohne Lizenz.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://api.github.com/repos/contextform/freecad-mcp
- **RhinoMCP (jingcheng-chen/rhinomcp)** — 995 Sterne, 91 Forks, MIT-Lizenz, angelegt 22. März 2025, letzter Push 26. Juli 2026 — 2026 gepflegt.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://api.github.com/repos/jingcheng-chen/rhinomcp
- **Rhino MCP Platform (McNeel)** — McNeel, der Hersteller von Rhino und Grasshopper, betreibt selbst eine kostenlose MCP-Plattform. Sie kann Rhino- und Grasshopper-Dateien auslesen, Geometrie erzeugen und ändern, Rhino-Befehle ausführen, Skripte schreiben, Grasshopper-Definitionen bauen, Modelle aus Bildern erzeugen und Ebenen ordnen. Clients: Claude, GitHub Copilot, OpenAI Codex, Gemini CLI und lokale LLMs.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Lizenz und geforderte Rhino-Fassung gehen aus der Startseite nicht hervor.
  · https://mcneel.github.io/RhinoMCP/
- **Autodesk Fusion MCP** — Autodesk hat im April 2026 zwei öffentliche MCP-Server angekündigt: Autodesk Fusion MCP (lokal, setzt laufendes Fusion voraus, führt Modellierung und Fusion-Befehle aus; arbeitet mit Claude Desktop, Cursor oder jedem MCP-fähigen HTTP-Client) und Autodesk Fusion Data MCP (entfernt, ohne laufendes Fusion, fragt und verwaltet Fusion-Daten über Autodesk-Clouddienste; Claude Desktop und VS Code). Beide sind allgemein verfügbar, nicht Vorschau.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Weitere Server für Revit und die Autodesk-Dokumentation sind angekündigt. Die Autodesk-Seiten selbst antworten auf automatisierte Abrufe mit HTTP 403, daher Fachpresse als Beleg.
  · https://www.engineering.com/autodesk-announces-fusion-mcp-servers-and-more-ai-updates/
- **Onshape FeatureScript MCP Server (PTC)** — PTC hat am 13. August 2026 den FeatureScript MCP Server für Onshape veröffentlicht, verfügbar über die Initiative Onshape Labs. Er verbindet programmierende LLMs — genannt sind Claude, ChatGPT und Gemini — mit FeatureScript, damit eigene CAD-Features per natürlicher Sprache gebaut, getestet, entfehlert und nachgeschärft werden.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: Preismodell und Tarifzuordnung nennt die Mitteilung nicht. Der Server erzeugt FeatureScript-Code, er fernsteuert nicht die Modellierung im Dokument.
  · https://www.prnewswire.com/news-releases/ptc-advances-leadership-in-ai-driven-design-with-launch-of-onshape-featurescript-mcp-server-302850833.html
  · https://investor.ptc.com/resources/news/news-details/2026/PTC-Advances-Leadership-in-AI-Driven-Design-with-Launch-of-Onshape-FeatureScript-MCP-Server/default.aspx
- **OpenSCAD-MCP** — Es gibt keinen führenden OpenSCAD-MCP-Server, sondern ein Feld von mindestens neun kleinen, unabhängigen Umsetzungen (rahulgarg123, petrijr, jhacksman, sergiudanstan, format37, quellant, fboldo, karolkaczmarek1, jkoets). Der Funktionsumfang ist überall ähnlich schmal: OpenSCAD-Quelltext prüfen, als PNG rendern, nach STL exportieren.
  · Stand: 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Sternezahlen einzeln habe ich nicht erhoben; keine der Umsetzungen tritt in den Suchergebnissen als verbreitet hervor.
  · https://github.com/petrijr/openscad-mcp
  · https://github.com/quellant/openscad-mcp
  · https://github.com/fboldo/openscad-mcp-server
- **OrcaSlicer-MCP (MaxEllis/orcaslicer-mcp)** — 31 Sterne, 4 Forks, AGPL-3.0, angelegt 18. Juli 2026, letzter Push 18. August 2026 — der aktivste Slicer-MCP. Kann Modelle laden und Platten belegen, rund 800 Einstellungen mit Plausibilitätsprüfung setzen, schneiden und je Merkmal Zeit, Filament und Flussraten zurückgeben, mehrere Varianten in einem Aufruf vergleichen und Plattenansichten als PNG rendern.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Braucht einen eigenen „OrcaSlicer 2.3.2 MCP build" von der Releases-Seite (nicht über den eingebauten Updater), uv und ein API-Token aus den Remote-API-Einstellungen. Läuft als lokaler stdio-Prozess. Daneben existiert jeff-roche/orca-mcp als dünne Hülle um die OrcaSlicer-Kommandozeile: 0 Sterne, MIT, angelegt 23. Juli 2026, letzter Push 24. Juli 2026.
  · https://api.github.com/repos/MaxEllis/orcaslicer-mcp
  · https://github.com/MaxEllis/orcaslicer-mcp
- **OrcaSlicer — eingebauter MCP-Server** — OrcaSlicer selbst hat keinen MCP-Server. Es liegt ein offener Wunsch als Meldung #13763 vom 21. Mai 2026 vor, einen nativen MCP-Server einzubauen.
  · Stand: 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Aus den Suchergebnissen entnommen; die Meldung selbst habe ich nicht geöffnet.
  · https://github.com/OrcaSlicer/OrcaSlicer/issues/13763
- **Cura-MCP (AuraFriday/cura_mcp)** — 7 Sterne, 1 Fork, Lizenz unbestimmt (NOASSERTION), angelegt und zuletzt bewegt am 14. November 2025 — seither unverändert. Getestet mit Cura 5.11+.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Ein Freigabewunsch für ein CuraMCP-Plugin liegt im UltiMaker-Forum, ohne dass ein offizieller Server daraus wurde.
  · https://api.github.com/repos/AuraFriday/cura_mcp
  · https://github.com/AuraFriday/cura_mcp
- **mcp-3D-printer-server (DMontgomery40)** — 229 Sterne, 45 Forks, GPL-2.0, angelegt 26. Februar 2025, letzter Push 30. Juli 2026. Bindet OctoPrint, Klipper, Duet, Repetier, Prusa, Creality sowie Orca und Bambu an, steuert Drucke, überwacht Zustände und bearbeitet STL (skalieren, drehen, schneiden), inklusive Slicing und Darstellung.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: GPL-2.0 — für Solidon nach AGENTS.md Regel 15 als Abhängigkeit ausgeschlossen, als externer Vergleichsfall aber einschlägig. Zum Vergleich: OctoEverywhere/mcp (Apache-2.0) hat 35 Sterne, letzter Push 3. Juli 2025.
  · https://api.github.com/repos/DMontgomery40/mcp-3D-printer-server
- **Bambu-MCP (schwarztim/bambu-mcp)** — 19 Sterne, 7 Forks, MIT-Lizenz, angelegt 6. Februar 2026, letzter Push 12. August 2026. Steuert Bambu-Drucker (P1P, P1S, X1C, A1, A1 Mini) über lokales MQTT, mit FTPS-Upload und X.509-Signatur; laut Beschreibung 25 Werkzeuge für Druckkontrolle, Zustand, Kamera, AMS, Temperatur und LED.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: Die Zahl 25 Werkzeuge und die Fassung 2.1.0 stammen aus der Suchzusammenfassung, nicht aus einer geholten Repositoriumsseite.
  · https://api.github.com/repos/schwarztim/bambu-mcp
  · https://github.com/schwarztim/bambu-mcp
- **Meshy MCP-Server (meshy-dev/meshy-mcp-server)** — 36 Sterne, MIT-Lizenz, 13 Commits auf main. Offizieller Server von Meshy. Installation über npx add-mcp @meshy-ai/meshy-mcp-server --env MESHY_API_KEY=..., Schlüssel aus den Kontoeinstellungen.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: Ein genaues Datum des letzten Commits war auf der Repositoriumsseite nicht abzulesen.
  · https://github.com/meshy-dev/meshy-mcp-server
  · https://docs.meshy.ai/en/api/ai
- **Meshy MCP — Werkzeuge** — Der Server bildet die REST-API ab: meshy_text_to_3d, meshy_image_to_3d, meshy_multi_image_to_3d, meshy_text_to_3d_refine; meshy_remesh, meshy_retexture, meshy_rig, meshy_animate; meshy_text_to_image, meshy_image_to_image; meshy_get_task_status, meshy_list_tasks, meshy_cancel_task, meshy_download_model; meshy_list_models, meshy_send_to_slicer, meshy_analyze_printability, meshy_process_multicolor, meshy_check_balance.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Das Repositorium spricht von 24 Werkzeugen insgesamt, einschließlich sieben „Creative Lab"-Produkten.
  · https://docs.meshy.ai/en/api/ai
- **Meshy — Anfragegrenzen** — Nach Tarif: Pro 20 Anfragen/s und 10 Aufgaben in der Warteschlange, Studio 20/20, Premium 20/30, Ultra 20/100, Enterprise 100/50 (verhandelbar). Zur Warteschlange zählen Text to 3D, Image to 3D, Text to Texture und Remesh; Upload und Balance nicht. Überschreitung liefert 429 mit RateLimitExceeded bzw. NoMoreConcurrentTasks.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Die Behauptung „20 Anfragen/s" gilt für alle Tarife außer Enterprise (dort 100). „10–100 gleichzeitige Aufgaben je Tarif" trifft die Spanne, unterschlägt aber Studio 20 und Enterprise 50.
  · https://docs.meshy.ai/en/api/rate-limits
- **Meshy — Guthaben je Aufruf** — Text to 3D 5–25 (Mesh) und 10–15 (Textur), Image to 3D und Multi Image to 3D 5–35, Retexture 10–15, Remesh 5, Convert 1, Resize 1, Auto-Rigging 5, Animation 3, Text to Image 3–9, Image to Image 3–12, Multi-Color-Druck 10, Repair Printability 10, Analyze Printability 0, Creative Lab 6–50. Jeder MCP-Werkzeugaufruf entspricht genau einem REST-Aufruf und kostet dasselbe.
  · Stand: 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: Die Behauptung „1–50 Guthaben je Aufruf" stimmt an der Obergrenze; die Untergrenze ist 0, weil Analyze Printability nichts kostet.
  · https://docs.meshy.ai/en/api/pricing
  · https://docs.meshy.ai/en/api/ai
- **Meshy — Verkettung über input_task_id** — Retexture nimmt input_task_id: die ID einer erfolgreich abgeschlossenen Aufgabe aus Text to 3D Preview, Text to 3D Refine, Image to 3D oder Remesh mit Status SUCCEEDED. Nur eines von input_task_id oder model_url ist nötig; sind beide gesetzt, gewinnt input_task_id. Remesh nutzt input_task_id ebenso als Eingang.
  · Stand: 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Aus der Suchzusammenfassung der beiden Dokuseiten; die Seiten selbst habe ich nicht einzeln geholt. Die MCP-Dokumentation erwähnt input_task_id nicht ausdrücklich.
  · https://docs.meshy.ai/en/api/retexture
  · https://docs.meshy.ai/en/api/remesh
- **Tripo MCP (VAST-AI-Research/tripo-mcp)** — Der als offiziell bezeichnete Tripo-MCP-Server hat 191 Sterne, 28 Forks, MIT-Lizenz, angelegt 21. März 2025 — letzter Push 14. April 2025. Seit über sechzehn Monaten unbewegt, also 2026 nicht gepflegt.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · https://api.github.com/repos/VAST-AI-Research/tripo-mcp
- **Hyper3D Rodin — MCP** — Rodin ist vor allem als Anbindung in blender-mcp präsent. Deemos (DeemosTech) betreibt daneben eigene Repositorien, darunter eine blender-mcp-Rodin-Integration und ein „Rodin3D Skills"-Paket für die Gen-2-API (Bild-zu-3D und Text-zu-3D).
  · Stand: 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Ein eigenständiges Repositorium rodin-api-mcp konnte ich nicht bestätigen; Sterne, Lizenz und Pflegestand liegen nicht belegt vor.
  · https://github.com/DeemosTech
  · https://github.com/ahujasid/blender-mcp
- **CAD-MCP-Landschaft — Überblicksartikel** — Snyk führte am 23. Juli 2025 neun CAD-MCP-Server auf: CAD-MCP (daobataotie, 98 Sterne, AutoCAD/GstarCAD/ZWCAD, 12 Werkzeuge), Easy-MCP-AutoCad (64, 16 Werkzeuge), autocad-mcp (puran-water, 59, 35+ Werkzeuge für R&I-Fließbilder), autodesk-fusion-mcp-python (6), fusion360-mcp-server (ArchimedesCrypto, 26, 11 Werkzeuge), freecad-mcp (neka-nat, damals 165 Sterne, 10 Werkzeuge), freecad_mcp (bonninr, 68, 2 Werkzeuge), mcp-server-solidworks (eyfel, 14), onshape-mcp (BLamy, 3, 18 Werkzeuge).
  · Stand: 2025-07-23 · Sicherheit: belegt
  · Anmerkung: Über ein Jahr alt; die Sternezahlen sind Stand Juli 2025 und heute überholt. Als Momentaufnahme der Streuung dennoch brauchbar.
  · https://snyk.io/articles/9-mcp-servers-for-computer-aided-drafting-cad-with-ai/

**Nicht belegbar:**
- Die genaue Zahl der heute im offiziellen MCP-Registry geführten Server: die kursierenden Zahlen (10.000+ im Dezember 2025, 17.468 laut einer Zählung im ersten Quartal 2026, 9.652 Datensätze am 24. Mai 2026) stammen aus Sekundärquellen, die ich nicht geöffnet habe.
- Lizenz und geforderte Rhino-Fassung der Rhino MCP Platform von McNeel — die Startseite nennt beides nicht.
- Preis, Tarifzuordnung und Lizenzbedingungen des Onshape FeatureScript MCP Servers; die Pressemitteilung schweigt dazu.
- Die Originalseiten von Autodesk (autodesk.com/solutions/autodesk-ai/autodesk-mcp-servers und der Fusion-Blogeintrag) antworten auf automatisierte Abrufe mit HTTP 403; die Angaben zu Fusion MCP stammen daher aus der Fachpresse, nicht von Autodesk selbst.
- Ob der Autodesk Fusion MCP quelloffen ist, unter welcher Lizenz er steht und wie viele Werkzeuge er anbietet.
- Ein eigenständiges MCP-Repositorium von Deemos für Hyper3D Rodin (rodin-api-mcp) — Existenz, Sterne, Lizenz und Pflegestand konnte ich nicht bestätigen.
- Sternezahlen der einzelnen OpenSCAD-MCP-Umsetzungen; ich habe keine davon einzeln erhoben.
- Ob das Meshy-MCP-Repositorium 2026 noch gepflegt wird — ein Datum des letzten Commits war nicht abzulesen.
- Ob PrusaSlicer einen eigenen oder einen verbreiteten MCP-Server hat; die Suche fand nur Sammelserver, die Prusa-Drucker über OctoPrint/PrusaLink ansprechen.
- Der genaue Wortlaut und Stand der OrcaSlicer-Meldung #13763 (nativer MCP-Server) — nur über die Suchzusammenfassung erfasst.
- Die vollständige Mitgliederliste der Agentic AI Foundation über Anthropic, Block und OpenAI hinaus.
- Ob es einen offiziellen MCP-Server von Bambu Lab selbst gibt — gefunden habe ich nur Gemeinschaftsprojekte.

**Neu seit Anfang August:**
- Die Behauptung „FreeCAD-MCP: 165 Werkzeuge über 15 Module" beschreibt nicht das führende Projekt, sondern sergiudanstan/freecad-mcp mit 6 Sternen, drei Commits und Stillstand seit dem 8. März 2026. Das eigentliche FreeCAD-MCP (neka-nat, 1.848 Sterne, Push von heute) hat zwölf Werkzeuge. Pikant: Snyk führte neka-nat im Juli 2025 mit genau „165★" und 10 Werkzeugen — die Zahl 165 könnte auf einer Verwechslung von Sternen und Werkzeugen beruhen.
- blender-mcp steht bei 26.041 Sternen, nicht 17.800 — rund 46 % über dem angenommenen Stand.
- Werkzeug-Suche ist kein Bestandteil von MCP. SEP-1821 steht seit November 2025 auf „Draft" und sucht noch einen Sponsor; SEP-1300 und SEP-1881 ebenso. Wer viele Werkzeuge anbietet, hat protokollseitig weiterhin nichts in der Hand.
- Sampling und Roots sind seit 2026-07-28 abgekündigt, und Elicitation läuft nicht mehr über einen servergestarteten Aufruf, sondern über Multi Round-Trip Requests: Der Server antwortet mit „input_required", der Client wiederholt die Anfrage. Für ctx.ask heißt das eine andere Architektur — Rückfragen sind kein Rückkanal mehr, sondern ein Wiederholungsmuster.
- MCP ist zustandslos geworden: kein initialize-Handshake, keine Mcp-Session-Id, keine SSE-Wiederaufnahme. Werkzeuglisten dürfen nicht mehr je Verbindung variieren — eine Fernsteuerung, deren Werkzeugangebot vom geöffneten Dokument abhängt, wäre mit der neuen Fassung nicht mehr vereinbar.
- Die beiden großen CAD-Hersteller haben 2026 nachgezogen: Autodesk mit zwei allgemein verfügbaren Fusion-MCP-Servern (April 2026), PTC mit dem Onshape FeatureScript MCP Server (13. August 2026, sechs Tage alt). McNeel betreibt eine eigene kostenlose Rhino-MCP-Plattform. Der Vergleich „Solidon gegen Bastelprojekte" trägt nicht mehr.
- Der aktivste Slicer-MCP (MaxEllis/orcaslicer-mcp, Push von gestern) verlangt einen eigenen OrcaSlicer-Sonderbau 2.3.2 und steht unter AGPL-3.0 — als Abhängigkeit für Solidon nach Regel 15 ausgeschlossen, als Vorbild für die Slicer-Übergabe trotzdem lehrreich: rund 800 Einstellungen mit Plausibilitätsprüfung, Variantenvergleich in einem Aufruf, Kennzahlen je Merkmal.
- Der offizielle Tripo-MCP-Server (191 Sterne) hat seit dem 14. April 2025 keinen Commit mehr gesehen — „offiziell" ist keine Zusage auf Pflege.
- Meshys MCP bietet mit meshy_send_to_slicer, meshy_analyze_printability und meshy_process_multicolor Druckvorbereitung an — ein KI-3D-Dienst greift damit in genau das Feld, das Solidon zwischen Modell und Slicer besetzt.
- Analyze Printability kostet bei Meshy 0 Guthaben, nicht 1 — die Untergrenze der Behauptung „1–50 Guthaben je Aufruf" stimmt nicht.

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
