---
name: paketfix-ist-kein-anwendungsfix
description: "Ein Fehler, der im Manifest eines Paketformats behoben wurde, reist in den anderen Formaten weiter — die Regel gehört in die Anwendung, nicht in die Hülle."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 979875fd-bfa8-4b06-9f26-64e50bc5303e
  modified: 2026-09-02T16:15:54.081Z
---

Der Wayland-Absturz (Martin Donecker, 28.08.2026) wurde am 28.08. im
Flatpak-Manifest behoben (`--socket=x11`), und das Register führte ihn als
„Korrektur gebaut". Fünf Tage später stand 0.3.0 vor dem Tag — mit AppImage
und Archiv, die erstmals ausgeliefert werden und **kein Manifest haben**. Qt 6
wählt in jeder Wayland-Sitzung von sich aus Wayland, VTKs Qt-Anbindung kennt
nur X11: derselbe Fehler, auf jedem KDE- und GNOME-Desktop, am ersten Tag.
Gefunden nur, weil eine Kundenfrage („ist das die Version?") zur Nachprüfung
zwang.

**Why:** Ein Manifest, ein Wrapper, eine CI-Umgebungsvariable beheben den Fall
nur für die Hülle, in der sie stehen. Drei Paketformate sind drei Hüllen; die
Anwendung ist eine. Und „Korrektur gebaut" im Register las sich wie „behoben",
obwohl es nur für eines von dreien galt.

**How to apply:** Wenn ein Fix in ein Manifest, einen Wrapper oder eine
Umgebung wandert, sofort fragen: Wo läuft dieselbe Anwendung noch, und wer
setzt es dort? Fehlt die Antwort, gehört die Regel in den Startpfad der
Anwendung (`app/ui/qt_platform.py` ist das Muster: reine Funktion mit der
Plattform als Parameter, das Manifest trägt sie zusätzlich). Im Register die
Reichweite dazuschreiben — „im Flatpak", nicht „gebaut". Verwandt:
[[regel-gilt-weiter-als-gemeint]], [[schutz-verliert-ein-geschwister]],
[[reparierter-fehler-hat-zwillinge]].
