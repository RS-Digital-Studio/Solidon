---
name: fenstermaske-ueber-vulkan-verliert-das-geraet
description: "Ein Qt-Widget mit komplexer QRegion-Maske über der wgpu-Renderfläche lässt den Vulkan-Treiber das Gerät verlieren — ab rund 1400 Rechtecken, ohne Fehler davor; Tinte über dem Bild gehört in den Renderer, nicht in ein maskiertes Widget"
metadata:
  type: project
  originSessionId: 7708995f-8153-4da1-9385-1fa5f014d252
---

Am 21.09.2026 riss die Anwendung beim Klick auf eine Bohrung an Weg 1 mit
„Parent device is lost" im nächsten `submit` (wgpu-native `lib.rs:605`), ohne
Warnung im Logger davor. Bisektiert auf `ebba075e`: Die Maßfelder standen neu
neben dem Körper, und die Verbindungslinien dorthin liefen **schräg** — die
`QRegion`-Maske des Maßwidgets hatte damit je Linie ein Rechteck je Bildzeile,
1682 Rechtecke statt einiger Dutzend. Gemessen: 1380 liefen, 1682 rissen; unter
`WGPU_BACKEND_TYPE=D3D12` lief alles. Vulkan ist auf der RTX 4080 der Standard.

**Why:** Qt setzt eine Fenstermaske als Region auf das native Fenster, und
das native wgpu-Fenster darunter (rendercanvas, Vulkan-Swapchain) wird bei
jeder Maskenänderung mit einer Clip-Region neu komponiert. Irgendwo in Treiber
oder Compositor gibt es dafür eine Grenze, und sie meldet sich nicht als
Fehler, sondern als verlorenes Gerät beim nächsten Frame. Ein Deckel über die
Rechteckzahl (Linien in Treppen bündeln) hielt das Gerät, zeichnete aber graue
Treppen an weißen Kanten und kostete je Aufbau eine Rasterung — Robert: „warum
haben wir jetzt so graue linien", „performancetechnisch auch ganz schlecht".

**How to apply:**

- **Tinte über dem Bild gehört in den Renderer** (`add_lines`, `add_surface`
  mit `keep_in_front`, wie die Merkmalslinien). Ein maskiertes Widget über der
  Renderfläche ist nur für runde Ecken mit wenigen Rechtecken tragbar
  (Overlaykarten). Schräge Linien in einer Maske sind der Fall, der reißt.
- **Ein Riss ohne Fehler davor ist eine Treiber- oder Ressourcengrenze**, keine
  Logikfrage. Bisect über Commits mit einer Sonde, die den echten Startweg
  fährt (`probe_main.py`: `app.ui.app.main`, Bohrung über den Baum wählen,
  „LEBT" nach fünf Sekunden), und die Grenze halbieren — ein Wert statt einer
  Vermutung.
- **Das Backend ist eine Variable der Messung.** `WGPU_BACKEND_TYPE=D3D12`
  als Gegenprobe; dass Solidon auf Windows D3D12 wählen könnte, ist RM-198 und
  offen — die Wurzel ist mit der Tinte im Renderer behoben.
- Zusammenhang: [[viewport-zwei-renderer-messen]], [[qt-luegt-vor-dem-anzeigen]].
