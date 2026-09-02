---
name: installer-probe-nicht-mit-fenster
description: "Ein Setup-Fenster auf Roberts Rechner wird durchgeklickt, und {app} zeigt auf eine alte HKCU-Testinstallation in %TEMP% — Integrität des Installers ohne Fenster prüfen."
metadata:
  type: feedback
---

Am 02.09.2026 habe ich `Solidon3D-Setup-0.2.2.exe` ohne Schalter gestartet,
um Innos CRC-Prüfung zu sehen (Fenster oder Fehlermeldung, dann beenden).
Zwölf Sekunden später stand das Fenster auf „Installiere …" und entpackte
nach `C:\Users\rober\AppData\Local\Temp\SolidonInstallTest\` — dorthin, weil
unter HKCU noch eine Testinstallation 0.1.1 vom 20.08.2026 eingetragen ist
und Inno den alten Pfad vorbelegt. Ich habe den Prozess bei 66 MB beendet;
der Ordner trägt seither eine halbe 0.2.2 neben `unins000.exe` von 0.1.1.
Program Files (0.2.2 vom 30.08.) blieb unberührt.

**Why:** Robert sitzt am Rechner. Ein Fenster, das ich öffne, ist für ihn ein
Fenster, und er klickt es durch — ich kann nicht annehmen, dass es steht,
bis ich es schließe. Und `{app}` ist nicht Program Files, sondern was die
Registrierung des jeweiligen Rechtekontexts hergibt.

**How to apply:** Die Integrität eines Setups misst die Prüfsumme gegen
`version.json` (Server: HTTP-HEAD plus Download über `count.php`, beides am
02.09.2026 byteidentisch). Muss Inno selbst laufen, dann still und in einen
eigenen Ordner: `/VERYSILENT /CURRENTUSER /DIR=<scratch> /NOICONS
/SUPPRESSMSGBOXES /LOG=<datei>`, danach `unins000.exe /VERYSILENT` — und
vorher den HKCU-Schlüssel `de.rsdigital.solidon3d_is1` lesen, der entscheidet,
wohin es geht. Siehe [[sonde-im-geteilten-baum]] und
[[messung-traegt-nur-am-ort-ihrer-messung]].
