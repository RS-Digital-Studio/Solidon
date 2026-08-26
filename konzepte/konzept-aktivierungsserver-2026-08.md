# Konzept: Aktivierungsserver

> **Stand: ENTWURF, 26.08.2026 — in Ausarbeitung durch alle vier Sitzungen.**
> Entschieden von Robert ist das *Ob* und die Reihenfolge; offen ist das *Wie*.
> Dieses Dokument sammelt die Ausarbeitung; verbindlich wird davon nichts,
> bevor es Robert abgenommen und der Bauplan (§8/§36) nachgezogen ist.
> Gebaut wird **nicht vor 0.2.0**.

## Die Entscheidungen, von denen dieses Konzept ausgeht

Beide von Robert am 26.08.2026:

1. **Die Testphase ist eine harte Grenze.** Nach den 14 Tagen läuft nichts
   mehr, was einen weiterbringt; Testphase und Kauf laufen über Lizenzen.
   Die lokale Härtung dafür ist gebaut (signierter Marker an zwei Orten,
   `3ef11e6e`) und bleibt auch mit Server die Verteidigung in der Tiefe.
2. **Es kommt ein echter Aktivierungsserver** — auf dem eigenen Webserver
   (netcup, solidon3d.de). Zuerst dieses Konzept, gemeinsam ausgearbeitet.

## Was ein Server kann, was lokal nicht geht

| Fähigkeit | lokal (heute) | mit Server |
|---|---|---|
| Marker editieren erkennen | ja (Unterschrift) | ja |
| Einen Marker-Ort löschen | ja (zweiter Ort heilt) | ja |
| Beide Orte löschen → neue 14 Tage | **nein** (Restgrenze) | ja — Server erinnert die Maschine |
| Geteilten/geleakten Schlüssel begrenzen | nein | ja — Aktivierungen je Schlüssel zählen |
| Erstatteten Schlüssel widerrufen | nein | ja |

## Die Zusage, an der alles hängt: §2

„Ohne Netz, ohne Konto und ohne KI bleibt alles außer dem Chat benutzbar"
steht in `AGENTS.md`, auf der Website und sinngemäß in der EULA. Ein
Aktivierungsserver muss daran vorbeikommen, ohne sie zu brechen. Der Rahmen,
der auszuarbeiten ist:

- **Aktivierung braucht einmal Kontakt, Betrieb nie.** Nach der Aktivierung
  läuft alles offline weiter; keine wiederkehrende Prüfpflicht, kein
  Heartbeat, kein stilles Nach-Hause-Telefonieren (die Telemetrie-Grenze aus
  `kern.md` gilt unverändert: einen Netzzugriff löst der Kunde aus, oder es
  gibt ihn nicht — die bestehende Update-Prüfung beim Start ist deklariert
  und abschaltbar, sie ist die einzige Ausnahme und bleibt es).
- **Ein Offline-Weg existiert** für Kunden ohne Netz am Arbeitsrechner:
  Challenge-Response über einen zweiten Rechner oder E-Mail (Code hin,
  signierte Antwort zurück). Ohne diesen Weg bräche §2 wirklich.
- **Fällt der Server aus, verliert kein Kunde etwas.** Eine einmal erteilte
  Aktivierung gilt lokal weiter; der Server wird nur für *neue* Aktivierungen
  gebraucht. Was passiert, wenn es die Firma nicht mehr gibt, gehört
  beantwortet (Notfall-Freischaltung als signierte Datei auf der Website?).

## Teil A — Kern-Integration (3d-druck-46, ausgearbeitet)

**Zustandsmodell.** `Activation` kennt heute `licence`, `days_left`,
`damaged`, `deadline`. Dazu käme ein maschinengebundenes **Aktivierungs-
zertifikat**: eine vom Server signierte Aussage „Schlüssel K ist auf Maschine
M aktiviert, ausgestellt am T". Die App prüft es offline gegen einen
eingebauten öffentlichen Schlüssel — derselbe ed25519-Weg wie beim
Lizenzschlüssel selbst. `unlocked` verlangte dann Lizenz **und** Zertifikat
(mit Übergangsregel für Bestandsschlüssel, siehe unten).

**Schlüsselkette — der private Hauptschlüssel bleibt offline.** Der Server
darf **nie** den Schlüssel halten, der Lizenzen signiert: Ein gehacktes
Shared Hosting dürfte sonst Lizenzen ausstellen. Stattdessen ein eigenes
Server-Schlüsselpaar nur für Aktivierungszertifikate; sein öffentlicher Teil
reist in der App neben dem bestehenden. Kompromittierung des Servers
erlaubt dann schlimmstenfalls das Ausstellen von Aktivierungen für gültige
Schlüssel — nicht das Erfinden von Lizenzen. Widerruf des Serverschlüssels
über ein App-Update.

**Maschinen-ID.** Nötig für „Aktivierungen je Schlüssel zählen", heikel für
den Datenschutz. Vorschlag: kein Hardware-Fingerabdruck, sondern eine beim
ersten Start **zufällig erzeugte** ID im Profil (UUID). Sie identifiziert
keine Hardware und keinen Menschen; wer das Profil neu aufsetzt, ist eine
neue Maschine — und verbraucht eine Aktivierung, was das Limit trägt.
DSGVO-seitig das mildeste Modell (Pseudonym ohne Personenbezug beim
Aktivieren eines anonymen Schlüssels; Personenbezug entsteht erst über die
Bestellnummer — Teil B).

**Trial über den Server?** Vorschlag: **nein, vorerst nicht.** Die
Testphase serverseitig zu registrieren hieße, dass Testen Netz braucht —
der härteste §2-Konflikt für den geringsten Gewinn (die lokale Härtung
deckt den einfachen Fall; wer Profile neu aufsetzt, um alle zwei Wochen 14
Tage zu schummeln, kauft auch mit Server nicht). Offen für die Runde.

**Bestandskunden-Migration.** Bereits verkaufte Schlüssel funktionieren
offline weiter (die App kann `purchased_on`/`major` lesen): Schlüssel mit
Kaufdatum vor dem Stichtag der Server-Einführung brauchen kein Zertifikat.
Kein Bestandskunde wird nachträglich zur Aktivierung gezwungen.

**Vier Grenzdateien bleiben vier.** Die Zertifikatsprüfung gehört in
`activation/` (im Cython-Prüfmodul), nicht in neue Grenzstellen.

## Teil B — Server, Kauffluss, Recht (3d-druck-a2, offen)

Fragen: Was kann das netcup-Hosting (PHP-Version, sodium/ed25519, MySQL/
SQLite, TLS, Rate-Limits)? Wie kommt heute der Schlüssel zum Kunden
(Kauffluss/Paddle → E-Mail?), und wo klinkt sich die Aktivierung ein?
DSGVO: welche Daten liegen beim Aktivieren an (Schlüssel-Hash, Zufalls-ID,
Zeitstempel, IP im Log?), Datenschutzerklärung/EULA-Erweiterung, AVV mit
netcup? Betrieb: Backup der Aktivierungsdatenbank, Monitoring, Verhalten
bei Ausfall, wer spielt Updates ein?

## Teil C — Sicherheitsarchitektur (3d-druck-ce, offen)

Fragen: Bedrohungsmodell (wer ist der Gegner, was ist er wert)?
Endpunkt-Design (activate/deactivate/status — so wenig wie möglich)?
Was darf ein gehackter Server schlimmstenfalls (und wie hält man das
klein)? Replay/Abuse (Rate-Limit je Schlüssel, Aktivierungslimit — wie
viele Maschinen je Lizenz?)? Offline-Challenge-Response-Verfahren im
Detail? Verifikation: Wie testet die Suite das, ohne Netz zu brauchen
(Testart „Anschluss" — die Isolation deckt das Netz heute nicht)?

## Teil D — Bedienung (3d-druck-43, offen)

Fragen: Der Aktivierungsfluss im Freischaltdialog (Schlüssel eintippen →
was genau passiert, was sieht der Kunde bei Erfolg/Fehler/kein Netz)?
Jeder Fehlerpfad mit Handlungsvorschlag (Regel 17) — besonders „Limit
erreicht" (Deaktivieren-anbieten statt Sackgasse) und „kein Netz"
(Offline-Weg anbieten)? Umzug auf einen neuen Rechner (Deaktivieren am
alten / Verwalten über die Website?)? Wie erklärt sich das im Handbuch, und
welche Sätze auf der Website altern damit (§2-Formulierungen!)?

## Offene Entscheidungen für Robert (nach der Ausarbeitung)

1. Aktivierungslimit je Schlüssel (Vorschlag: 3 Maschinen, Deaktivieren
   möglich).
2. Trial lokal lassen oder serverseitig registrieren (Vorschlag: lokal).
3. Bestandsschlüssel-Stichtag.
4. Notfallplan „Firma weg" (signierte Dauer-Freischaltung hinterlegen?).
