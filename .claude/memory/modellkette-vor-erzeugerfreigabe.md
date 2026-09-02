# Modellkette vor Erzeugerfreigabe

Eine Lizenzdatei an der Wurzel eines Modell-Repositories belegt nicht die
gesamte Kette. Vor einer Einrichtung oder Bewerbung müssen mindestens die
feste Quelltextfassung, jedes geladene Gewicht, eingebundene Modelle,
Laufzeitabhängigkeiten, deren Lizenzen und die Weitergaberechte des
resultierenden Pakets einzeln feststehen.

Bei TripoSG war die frühere Kurzfassung „MIT für Quelltext und Gewichte“
zu kurz: Quelltext und Modellkarte weisen MIT aus, das offizielle `NOTICE`
nennt daneben weitere Modell- und Community-Lizenzen (HunyuanDiT, FlashVDM),
und mindestens eine davon begrenzt das Nutzungsgebiet. Ein Verstoß ist nicht
festgestellt.

**Entscheidung Robert (02.09.2026): TripoSG ist nicht gesperrt und wird
benutzt, solange die Rechtsprüfung nichts anderes ergibt.** Der Setupweg,
der Menüeintrag, der Changelog-Punkt und die Handbuchseite bleiben aktiv;
sichtbare Lizenzaussagen sagen nur, was belegt ist („Quelltext und
Modellkarte MIT; die vollständige Kette der Gewichte wird geprüft“). Die
Gegenposition „fail-closed sperren“ (Codex, 02.09. 01:11) ist damit
zurückgenommen; der Code war ihr nie gefolgt. Offen bleibt die Kanzleifrage
zur Kette (Register P9).

Alte Ausgaben lassen sich nicht nachträglich freigeben, wenn Prompt oder
Eingabe, Startwert, Backend-Revision und Gewichtsrevision fehlen. Eine
Reparatur, ein Bildschnitt oder das Speichern als Projekt ändert diese
Herkunft nicht. Aussage, HTML-Verweis, Generatorweg und Datei müssen dann aus
dem Auslieferungspfad verschwinden; Ersatz entsteht nur in einem neuen,
vollständig dokumentierten Lauf.

Eine öffentliche Produktzusage wird erst wieder formuliert, wenn derselbe
Stand technisch installiert, rechtlich freigegeben und live gemessen wurde.
Bis dahin bleibt der ehrliche Weg: GLB oder STL aus einem Generator eigener
Wahl importieren und in Solidon reparieren, auf Maß bringen, prüfen, teilen
und verstiften.

Primärbelege der damaligen Korrektur:

- `https://github.com/VAST-AI-Research/TripoSG/blob/main/NOTICE`
- `https://github.com/Tencent-Hunyuan/FlashVDM/blob/main/LICENSE`

## Geprüfte Ersatzkandidaten am 31.08.2026

Keiner der drei naheliegenden Ersatzwege trägt derzeit alle Produktauflagen:

- **Shap-E** veröffentlicht Code und Modelle gemeinsam unter MIT. Die eigene
  Modellkarte rät jedoch von kommerzieller Nutzung ab, nennt deutlich
  niedrigere Güte als professionelle 3D-Assets sowie häufig raue Kanten,
  Löcher und unscharfe Texturen. Damit ist es kein Ersatz für die zugesagte
  Qualität eines Verkaufsprodukts.
- **Stable Fast 3D** erlaubt über die Stability-AI-Community-Lizenz nur
  begrenzte kommerzielle Nutzung, ist beim Gewichtsabruf zustimmungspflichtig
  und hängt für den offiziellen Lauf an `nvdiffrast`. Dessen NVIDIA Source
  Code License begrenzt die Nutzung auf Forschung und Auswertung. Ohne eigene
  kommerzielle NVIDIA-Lizenz ist die Kette nicht freigegeben.
- **TRELLIS.2** bezeichnet Modell und Hauptcode als MIT. Der offizielle Lauf
  verwendet ebenfalls `nvdiffrast` und `nvdiffrec`; außerdem ist die
  plattformübergreifende Einrichtung für Windows und macOS kein belegter
  Produktweg. MIT am Modell hebt diese Grenzen nicht auf.

Primärbelege der Ersatzprüfung:

- `https://github.com/openai/shap-e/blob/main/model-card.md`
- `https://github.com/openai/shap-e/blob/main/LICENSE`
- `https://huggingface.co/stabilityai/stable-fast-3d`
- `https://github.com/Stability-AI/stable-fast-3d`
- `https://github.com/microsoft/TRELLIS.2`
- `https://huggingface.co/microsoft/TRELLIS.2-4B`
- `https://github.com/NVlabs/nvdiffrast/blob/main/LICENSE.txt`
- `https://github.com/NVlabs/nvdiffrec`
