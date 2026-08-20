# Anschreiben 3Druck.com — Demo-Start Solidon3D

Ziel: 3Druck.com (Wien), deutschsprachiges Fachportal für additive
Fertigung. Weg: Kontaktformular mit Thema „Pressemitteilung" oder die im
Impressum genannte Redaktionsadresse. Ein Weg genügt — nicht beides.

**Regieanweisung, nicht zum Mitschicken.** Alles unterhalb der Trennlinie
geht hinaus, dieser Block nicht.

* **Erst schicken, wenn der Download steht.** Eine Redaktion klickt beim
  Lesen. Steht dort noch „Bescheid geben, wenn sie da ist", war das der
  erste und letzte Kontakt. Also: Datei live, Prüfsumme daneben,
  `version.json` aktuell — dann die Mail.
* **Nicht vor 18 Uhr.** Der Text sagt „seit dem 20. August". Vor 18 Uhr
  ist das falsch.
* **Antwortadresse muss empfangen.** Wenn die Mail von einer privaten
  Adresse ausgeht und `support@solidon3d.de` als Rückkanal nennt, muss
  dieses Postfach Post annehmen. Sonst lieber die Adresse als
  Antwortadresse eintragen, von der tatsächlich gesendet wurde.
* **Absender offen.** Der Beitrag ist in der dritten Person geschrieben,
  wie ein Redakteur ihn schreiben würde — das ist üblich und erwünscht,
  es spart der Redaktion Arbeit. Die Mail selbst sagt aber, wer schreibt.
  3Druck.com prüft Impressum und Domain in zwei Minuten; ein verdeckter
  Absender kostet den Kontakt dauerhaft, und zwar für alles Spätere mit.
* **Das Zitat ist ein Vorschlag.** Es steht als Zitat im Beitrag und ist
  bisher von niemandem gesagt worden. Entweder freigeben — dann gilt es
  als gesagt — oder streichen.
* **Zahlen.** Der Faktenblock ist aus den Quellen ausgelesen und wird von
  `tests/test_press_release.py` gehalten. Vor dem Versand einmal die
  Suite laufen lassen.
* **Anhänge:** höchstens drei Bilder (je unter 1 MB) direkt an die Mail,
  alles Weitere verlinken. Große Anhänge landen im Spam-Ordner.

---

## Betreff

Solidon3D: kostenlose Demo einer Desktop-Software, die fremde STLs passend macht (Beitrag im Anhang)

## Die Mail

Sehr geehrte Redaktion,

seit heute steht die Demo von Solidon3D bereit — einer Desktop-Anwendung,
die dort ansetzt, wo Meshmixer aufgehört hat: heruntergeladene Modelle
reparieren, anpassen und vor dem Slicen prüfen, ob sie sich überhaupt
drucken lassen. Sie läuft lokal, ohne Konto und ohne Cloud; die Demo ist
vollständig, kostenlos und bis zum 30. Oktober 2026 nutzbar.

Zwei Dinge dürften Ihre Leser besonders interessieren: Die Anwendung
misst das Spiel einer Passung nicht ab Tabelle, sondern über ein kleines
Prüfstück, das der Nutzer einmal ausdruckt — danach rechnen alle Teile
mit diesem Wert. Und der eingebaute KI-Chat berechnet keine Geometrie:
Er darf nur dieselben Arbeitsschritte auslösen, die auch in den Menüs
stehen. Gerechnet wird von Code.

Unten finden Sie einen fertigen Beitrag, den Sie kürzen, umschreiben oder
verwerfen können, dazu eine Kurzfassung für eine Meldung und einen
Faktenblock. Bildschirmfotos in Druckqualität und ein knapp einminütiger
Film vom Ablauf „heruntergeladenes Teil wird passend" stelle ich Ihnen
gern zur Verfügung — den Film auf Wunsch ohne Sprecherstimme und ohne
Beschriftung, wenn Sie ihn selbst vertonen möchten. Für einen Test
schicke ich Ihnen ebenso gern einen Lizenzschlüssel der Vollversion.

Für Rückfragen stehe ich jederzeit zur Verfügung.

Mit freundlichen Grüßen
Robert Schneider
RS Digital, Amberg
support@solidon3d.de · https://solidon3d.de

---

# Beitrag (Langfassung, rund 600 Wörter)

## Solidon3D will die Lücke füllen, die Meshmixer hinterlassen hat

**Eine deutsche Desktop-Anwendung nimmt sich des häufigsten Problems im
3D-Druck-Alltag an: Das heruntergeladene Modell ist fast richtig. Seit
dem 20. August steht eine kostenlose Demo bereit.**

Wer regelmäßig druckt, kennt den Ablauf: Auf Printables oder MakerWorld
liegt ein Halter, der beinahe passt. Zwei Millimeter zu kurz, das
Schraubenloch am falschen Fleck, und das Netz hat Löcher. Für diese
Aufgabe gab es einmal Werkzeuge — Autodesks Meshmixer wird seit Jahren
nicht mehr weiterentwickelt, Microsofts 3D Builder ist abgekündigt. Wer
heute ein fremdes STL anpassen will, landet entweder in einem
Vollwert-CAD, in dem ein Mesh ein Fremdkörper ist, oder in Blender, das
für alles gebaut wurde, nur nicht für Maßhaltigkeit.

Genau in diese Lücke zielt Solidon3D, eine Anwendung des Amberger
Entwicklers RS Digital. Sie läuft unter Windows, macOS und Linux, arbeitet
vollständig lokal und verlangt weder Konto noch Registrierung.

### Druckbarkeit, bevor der Slicer die Datei sieht

Der auffälligste Unterschied zu einem klassischen Mesh-Editor ist die
eingebaute Schichtanalyse. Solidon3D zerlegt das Modell in Schichten,
bevor ein Slicer es zu sehen bekommt, und prüft, woran Drucke
üblicherweise scheitern: Überhänge gegen den Winkel, den das eingestellte
Material verträgt, Inseln ohne Verbindung nach unten, Brückenweiten, und
die dünnste Wand gegen die Düse des ausgewählten Druckers. Aus der
Geometrie leitet die Anwendung Druckeinstellungen ab und nennt zu jedem
Wert den Grund.

Der Unterschied zur Prüfung im Slicer ist der Zeitpunkt. Ein Slicer sagt,
ob eine Datei kaputt ist. Solidon3D sagt, ob sich das Teil drucken lässt —
solange es noch änderbar ist. Ein eigener Slicer ist ausdrücklich nicht
vorgesehen; die Druckdatei kommt weiter aus PrusaSlicer, OrcaSlicer oder
Cura, an die Solidon3D mit fertigem Profil übergibt und deren Ergebnis es
zur Gegenprobe zurückliest.

### Das Spiel einer Passung wird gemessen

Am eigenwilligsten löst die Anwendung ein Problem, an dem sich jeder
schon einmal die Finger verbrannt hat: Wie viel Luft muss zwischen Zapfen
und Loch bleiben, damit beides zusammengeht? Die Antwort hängt am Drucker
und am Material, und in den meisten Programmen steht an dieser Stelle
eine geratene Zahl im Modell.

In Solidon3D steht dort stattdessen ein Verweis auf das Materialprofil.
Gemessen wird einmal: Die Anwendung erzeugt ein kleines Prüfstück mit
abgestuften Spielmaßen, der Nutzer druckt es und probiert durch, welche
Stufe saugend sitzt — und trägt diesen einen Wert ein. Von da an rechnen
alle Teile damit, auch die, die vorher entstanden sind. Ein Deckel, der
zu stramm sitzt, wird nicht neu konstruiert; eine Zahl ändert sich, und
er passt.

### Eine KI, die nicht rechnen darf

Ein Chat gehört dazu, aber mit einer ungewöhnlichen Einschränkung: Das
Sprachmodell führt keine Geometrie aus. Es darf ausschließlich dieselben
Arbeitsschritte auslösen, die auch in den Menüs stehen — gerechnet wird
von Code. Maße erfinden kann es damit nicht. Jeder Vorschlag kommt
außerdem als ein einziger Schritt an, den ein einzelnes Rückgängig
vollständig zurücknimmt.

Nachprüfbar ist das Verhalten ebenfalls: 39 typische Anfragen laufen als
feste Prüfstrecke gegen jede Programmänderung. Mit einem mittelgroßen
Modell, das auf dem eigenen Rechner läuft, wurden zuletzt 28 der 39
Aufgaben gut gelöst; 98 Prozent der Befehle, die das Modell an die
Anwendung schickte, waren auf Anhieb gültig. Wer keinen Schlüssel
hinterlegt und kein lokales Modell betreibt, verliert nur den Chat — die
85 Arbeitsschritte bleiben über Menüs und Kommandozeile erreichbar.

### Was es nicht ist

Ein CAD-Ersatz will Solidon3D nicht sein. Es gibt Skizzen mit
Zwangsbedingungen und einen exakten Kern für Verrundungen, Fasen und
STEP-Export, aber keine Feature-Historie wie in Fusion oder SolidWorks
und keine Baugruppenverwaltung. Auch die macOS-Fassung ist noch nicht bei
Apple signiert — sie startet beim ersten Mal nur über den Umweg im
Kontextmenü. Und die Demo ist bewusst hart befristet: Sie ist vollständig,
ohne Wasserzeichen und ohne Exportsperre, lässt sich aber ab dem
31. Oktober nicht mehr starten. Projektdateien bleiben davon unberührt;
sie sind ZIP-Archive mit JSON darin.

Nach der Demo soll Solidon3D 49 Euro als Einmalkauf kosten, später 79
Euro. Kein Abo, kein Konto, alle 1.x-Aktualisierungen inbegriffen. Die
Demo steht unter https://solidon3d.de bereit.

---

# Kurzfassung (rund 150 Wörter, für eine Meldung)

## Solidon3D: kostenlose Demo für das Anpassen fremder Druckdateien

Der Amberger Entwickler RS Digital hat am 20. August die Demo von
Solidon3D veröffentlicht, einer Desktop-Anwendung zum Reparieren,
Anpassen und Prüfen von 3D-Modellen. Sie zielt auf die Lücke, die
Autodesks eingestelltes Meshmixer und Microsofts abgekündigter 3D
Builder hinterlassen haben.

Kern der Anwendung ist eine Schichtanalyse, die vor dem Slicen auf
Überhänge, Inseln, Brückenweiten und zu dünne Wände prüft und daraus
Druckeinstellungen mit Begründung ableitet. Passungen bezieht Solidon3D
nicht aus Tabellenwerten, sondern aus einem Prüfstück, das der Nutzer
einmal ausdruckt. Ein KI-Chat ist eingebaut, berechnet aber keine
Geometrie: Er darf nur dieselben Arbeitsschritte auslösen wie die Menüs.

Die Anwendung läuft lokal unter Windows, macOS und Linux, ohne Konto und
ohne Cloud. Die Demo ist vollständig und bis zum 30. Oktober 2026
kostenlos; danach kostet Solidon3D 49 Euro als Einmalkauf.
https://solidon3d.de

---

# Faktenblock

| | |
|---|---|
| Demo | 20.08.–30.10.2026, kostenlos, vollständig, ohne Konto |
| Plattformen | Windows 10/11, macOS, Linux |
| Sprachen | Deutsch, Englisch, Spanisch, Französisch, Italienisch, Portugiesisch |
| Umfang | 85 Arbeitsschritte, 17 geprüfte Bausteine, 40 Normteilmaße, 16 Druckerprofile, 9 Beispielprojekte |
| Formate | liest STL, 3MF, OBJ, GLB/GLTF, PLY, OFF, STEP, SVG, DXF — schreibt STL, 3MF, OBJ, PLY, GLB, STEP |
| Slicer-Übergabe | PrusaSlicer, OrcaSlicer, Cura — mit fertigem Profil, Druckdatei wird zur Gegenprobe zurückgelesen |
| KI | auf dem eigenen Rechner oder über einen selbst hinterlegten Zugang; von außen ansteuerbar, standardmäßig abgeschaltet |
| Preis nach der Demo | 49 € Einmalkauf zur Einführung, später 79 €; kein Konto, kein Abo |
| Hersteller | RS Digital, Amberg (Deutschland) |
| Website | https://solidon3d.de (deutsch), https://solidon3d.de/en/ (englisch) |
| Kontakt | support@solidon3d.de |

# Bildmaterial

Bildschirmfotos in Druckqualität unter https://solidon3d.de/handbuch.html —
es sind die Abbildungen des Handbuchs, alle aus der laufenden Anwendung
aufgenommen; auf Anfrage auch als Paket. Dazu ein Film vom Ablauf
„heruntergeladenes Teil wird passend", knapp unter einer Minute, in Deutsch
und Englisch, im Querformat (1080p) und im Hochformat.

# Zitatvorschlag (freigeben oder streichen)

„Ein Slicer sagt dir, ob deine Datei kaputt ist. Er sagt dir nicht, ob
das Teil sich drucken lässt — und wenn du es merkst, ist die Datei schon
geschnitten. Solidon3D sagt es dir, solange du noch etwas ändern kannst."
— Robert Schneider, Entwickler von Solidon3D
