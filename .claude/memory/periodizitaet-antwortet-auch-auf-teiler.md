---
name: periodizitaet-antwortet-auch-auf-teiler
description: "Ein Maß für eine Periode konzentriert genauso bei p/2, p/3, p/4 — und manchmal stärker. Der höchste Gipfel ist nicht die Periode, der größte ist es."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 880d8f7a-c07e-4b8f-b374-5bef80997d00
  modified: 2026-09-04T14:52:07.868Z
---

Am 04.09.2026 beim Bau der Gewindeerkennung: Die Steigung einer Wendel findet
man, indem man `z − p·θ/2π` modulo `p` aufträgt und schaut, bei welchem `p` die
Punkte zusammenfallen. Das funktioniert — und es funktioniert **auch bei p/2,
p/3 und p/4**, denn nach einer vollen Windung wächst `z` um genau `p`, also ist
der Rest modulo jedes Teilers wieder derselbe.

An einem M8-Innengewinde stand der Gipfel bei der halben Steigung **höher** als
bei der richtigen: 0,166 gegen 0,132. Wer `argmax` nimmt, meldet 0,62 mm statt
1,25 — und scheitert danach an einer Folgeprüfung, die gegen die falsche
Steigung gemessen das Doppelte ergibt. Der Fehler sieht dann aus, als läge er
in der Folgeprüfung.

**Vielfache sind dabei unschädlich**: Bei 2p liegen aufeinanderfolgende
Windungen um eine halbe Periode versetzt und heben sich im Mittel auf. Die
Oberwellen gehen also nur nach unten, und daraus folgt die Regel.

**Why:** Jede Messung, die eine Periode über „wie gut passt dieser Kandidat"
sucht — Fourier, Autokorrelation, Phasenkonzentration, Histogramm über den Rest
—, hat diese Familie. Die Stärke des Gipfels sagt, *ob* etwas periodisch ist,
nicht *mit welcher* Periode. Welcher Teiler zufällig am höchsten steht, hängt
an der Abtastung und an der Form des Profils; hier war es bei außen liegenden
Gewinden der Grundton, bei innen liegenden die halbe Steigung, und derselbe
Code entschied beide Male anders.

**How to apply:** Nicht `argmax`, sondern: alle lokalen Gipfel sammeln, die
einen Anteil des höchsten erreichen (gemessen lag der Grundton bei 0,80 bis
1,00 des höchsten, gewählt wurde 0,70), und davon den **mit der größten
Periode** nehmen. Und die Gegenprobe, die den Fall überhaupt sichtbar macht:
Den abgesuchten Bereich **weiten** und schauen, ob der Gipfel wandert. Ein
Gipfel, der beim Weiten wandert, war ein abgeschnittener Hang am Rand — so fiel
hier ein Fehlalarm auf, der bei Bereichsende 3,0 mit 2,97 mm antwortete und bei
Bereichsende 6,0 mit 5,37. Verwandt: [[am-eingang-drehen]],
[[schranke-aus-einem-messwert-ist-geraten]].
