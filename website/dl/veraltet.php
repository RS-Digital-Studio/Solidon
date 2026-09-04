<?php
/**
 * Leitet die Anfrage nach einem alten Paket auf die aktuelle Fassung weiter.
 *
 * Warum es diese Datei gibt: Beim Veröffentlichen werden die alten Pakete vom
 * Server geräumt, und damit stirbt jeder Link, der je verschickt wurde — in
 * Support-Mails, in Foren, in Lesezeichen. Am 03.09.2026 hat das einen
 * Interessenten getroffen: Er bekam am 2. September einen Link auf
 * `Solidon3D-Setup-0.2.2.exe`, und einen Tag später antwortete der Server mit
 * 404. Ein toter Download ist die schlechteste Auskunft, die eine Seite geben
 * kann — der Leser hält das Produkt für verschwunden, nicht die Datei.
 *
 * Weitergeleitet wird auf **dieselbe Plattform**, nicht pauschal auf die
 * Startseite: Wer eine `.pkg` angefragt hat, sitzt an einem Mac und ist mit
 * einer `.exe` nicht bedient.
 *
 * Das Ziel kommt aus `version.json` und nicht aus dieser Datei. Eine
 * eingetragene Versionsnummer wäre beim nächsten Release still falsch, und
 * genau solche Stellen findet niemand wieder — das Manifest wird bei jeder
 * Veröffentlichung ohnehin geschrieben.
 *
 * Einrichtung: Datei nach `httpdocs/dl/veraltet.php` legen. Die Umleitung
 * dorthin steht in `.htaccess`; ohne sie antwortet der Server weiter mit 404.
 * Kein Composer, keine Bibliothek.
 */

declare(strict_types=1);

/** Wohin die Anfrage geht, wenn sich keine Plattform bestimmen lässt. */
const FALLBACK = 'https://solidon3d.de/#download';

/**
 * Welche Plattform aus `version.json` zu einem angefragten Dateinamen gehört.
 *
 * Gelesen wird nur das Muster, nie der Name selbst: Was hier hereinkommt,
 * stammt aus der Adresszeile und wird weder in einen Pfad noch in eine
 * Ausgabe gesetzt.
 */
function plattform_zu(string $name): ?string
{
    if (preg_match('/^Solidon3D-Setup-[0-9]+(\.[0-9]+)*\.exe$/', $name) === 1) {
        return 'windows';
    }
    if (preg_match('/^Solidon3D-[0-9]+(\.[0-9]+)*-x86_64\.flatpak$/', $name) === 1) {
        return 'linux';
    }
    if (preg_match('/^Solidon3D-[0-9]+(\.[0-9]+)*-macos-arm64\.pkg$/', $name) === 1) {
        return 'macos-arm64';
    }
    if (preg_match('/^Solidon3D-[0-9]+(\.[0-9]+)*-macos-x86_64\.pkg$/', $name) === 1) {
        return 'macos-x86_64';
    }

    // Die Linux-Direktstartdatei wird gebaut und ausgeliefert, steht aber in
    // keinem Manifest: `version.json` führt die Pakete der Update-Automatik,
    // und Linux ist dort das Flatpak. Hier stand deshalb, sie werde „seit
    // 0.2.0 nicht mehr gebaut" — falsch seit dem Tag, an dem sie zurückkam,
    // und niemandem aufgefallen, weil ein Fehlschlag dieser Datei wie ein
    // Erfolg aussieht: Der Kunde landet auf der Downloadauswahl und nicht im
    // Nichts. Gemessen am 04.09.2026 gegen den Server: Windows und beide Macs
    // fanden ihre neue Datei, diese eine nicht.
    if (preg_match('/^Solidon3D-[0-9]+(\.[0-9]+)*-x86_64\.AppImage$/', $name) === 1) {
        return 'appimage';
    }

    // tar.gz und zip standen früher im Angebot und werden nicht mehr
    // ausgeliefert (das Archiv setzt ein Terminal voraus, die Zips sind
    // Bauartefakte des Signierwegs). Für sie gibt es keine Entsprechung,
    // also führt der Weg auf die Downloadauswahl.
    return null;
}

/**
 * Der Name der aktuellen Linux-Direktstartdatei, aus der Fassung im Manifest.
 *
 * Dieselbe Regel wie bei den vier Paketen: Die Nummer kommt aus
 * `version.json` und steht nicht in dieser Datei. Weitergeleitet wird nur,
 * wenn die Datei auch wirklich hier liegt — eine Umleitung auf ein 404 wäre
 * kein Fortschritt gegenüber dem 404.
 */
function appimage_ziel(array $manifest): ?string
{
    $fassung = $manifest['version'] ?? null;
    if (!is_string($fassung) || preg_match('/^[0-9]+(\.[0-9]+)*$/', $fassung) !== 1) {
        return null;
    }
    $name = 'Solidon3D-' . $fassung . '-x86_64.AppImage';
    if (!is_file(__DIR__ . '/' . $name)) {
        return null;
    }
    return 'https://solidon3d.de/dl/' . $name;
}

$angefragt = (string) ($_GET['datei'] ?? '');
$plattform = plattform_zu($angefragt);

$ziel = FALLBACK;
if ($plattform !== null) {
    $roh = @file_get_contents(__DIR__ . '/../version.json');
    if ($roh !== false) {
        $manifest = json_decode($roh, true);
        $url = is_array($manifest)
            ? ($plattform === 'appimage'
                ? appimage_ziel($manifest)
                : ($manifest['packages'][$plattform]['url'] ?? null))
            : null;
        // **Nur eine eigene Adresse.** Das Manifest liegt auf demselben Server
        // und ist damit so vertrauenswürdig wie diese Datei — aber eine
        // Weiterleitung ist ein Werkzeug, mit dem sich Vertrauen ausleihen
        // lässt, und eine offene Weiterleitung wäre genau das.
        if (is_string($url) && str_starts_with($url, 'https://solidon3d.de/')) {
            $ziel = $url;
        }
    }
}

// 302 und nicht 301: Die aktuelle Fassung wechselt, und eine dauerhafte
// Umleitung bliebe im Browser stehen, bis jemand seinen Verlauf leert.
header('Location: ' . $ziel, true, 302);
header('Cache-Control: no-store');
header('Content-Type: text/html; charset=utf-8');

// Für den seltenen Fall, dass jemand die Weiterleitung nicht ausführt — und
// weil eine leere Seite auch eine Auskunft ist, nur keine gute.
$sicher = htmlspecialchars($ziel, ENT_QUOTES, 'UTF-8');
echo "<!doctype html><html lang=\"de\"><meta charset=\"utf-8\">";
echo "<title>Diese Fassung ist nicht mehr da</title>";
echo "<p>Diese Fassung von Solidon3D steht nicht mehr zum Herunterladen bereit. ";
echo "Die aktuelle liegt hier: <a href=\"{$sicher}\">{$sicher}</a></p>";
