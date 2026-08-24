<?php
/**
 * Zählt, was auf solidon3d.de abgerufen wird — Seiten und Downloads.
 *
 * Warum es diese Datei gibt: Ohne eine Zahl weiß niemand, ob eine
 * Pressemitteilung etwas gebracht hat oder ob die Demo überhaupt geladen
 * wird. Die üblichen Antworten darauf heißen Google Analytics oder Matomo;
 * beide setzen Cookies, beide erkennen denselben Besucher über Wochen
 * wieder, und die Website verspricht ausdrücklich das Gegenteil. Hier steht
 * die kleinste Sache, die die Frage beantwortet: ein Zähler ohne Cookie,
 * ohne fremden Server und ohne gespeicherte IP-Adresse.
 *
 * Zwei Eingänge, ein Zweck:
 *
 *   POST /api/count.php   mit Feld `p` (Pfad)   → Seitenaufruf, Antwort 204
 *   GET  /api/count.php?f=<Datei>               → Download, Antwort 302 auf /dl/
 *
 * Der Download läuft deshalb über eine Weiterleitung und nicht über
 * ``readfile``: Die Setup-Datei wiegt 170 MB, und wer sie durch PHP schiebt,
 * verliert die Wiederaufnahme abgebrochener Downloads und handelt sich ein
 * Zeitlimit ein. Nach der Weiterleitung liefert der Webserver die Datei
 * selbst aus, wie vorher auch.
 *
 * **Was gespeichert wird und was nicht.** Gespeichert werden Zeitpunkt, der
 * abgerufene Pfad, der Host der verweisenden Seite und ein Tageskennzeichen.
 * Nicht gespeichert werden IP-Adresse und User-Agent. Das Tageskennzeichen
 * ist ein gekürzter Hash aus IP, User-Agent und einem Zufallswert, der jede
 * Nacht neu entsteht und nirgends aufgehoben wird — damit lassen sich
 * Aufrufe innerhalb eines Tages zu Besuchen zusammenfassen, und am nächsten
 * Tag ist die Verbindung zur Person nicht wiederherstellbar, auch nicht von
 * uns. Dieselbe Bauart benutzt Plausible; sie gilt als einwilligungsfrei
 * nach § 25 Abs. 2 TDDDG, weil auf dem Gerät des Besuchers nichts abgelegt
 * und nichts ausgelesen wird.
 *
 * Gegenstück: website/api/stats.php zeigt, was hier zusammenkommt.
 *
 * Einrichtung: Datei nach httpdocs/api/count.php legen. Sonst nichts — kein
 * Composer, keine Datenbank. Der Ablageordner legt sich selbst an.
 *
 * Braucht PHP 7.4 oder neuer.
 */

declare(strict_types=1);

// --- Einstellungen ---------------------------------------------------------

/** Wo die Downloads liegen, vom Dokumentenstamm aus gesehen. */
const DOWNLOAD_URL = '/dl/';

/** Und wo im Dateisystem — zum Nachsehen, ob es die Datei überhaupt gibt.
 *  Ohne diese Prüfung wäre die Weiterleitung ein offenes Tor: Wer `f`
 *  frei wählen darf, schickt Besucher über unsere Domain irgendwohin. */
const DOWNLOAD_DIR = __DIR__ . '/../dl';

/** Wie lang das Tageskennzeichen ist. Acht Hex-Zeichen reichen, um
 *  Aufrufe eines Tages zu gruppieren, und sind kurz genug, dass die Datei
 *  lesbar bleibt. */
const MARK_LENGTH = 8;

/** Wie viele Zeichen eines Pfads aufgezeichnet werden. Alles darüber ist
 *  entweder ein Angriffsversuch oder ein Kennzeichen, das jemand angehängt
 *  hat — beides gehört nicht in die Auswertung. */
const MAX_PATH = 120;

// --- Ablage ----------------------------------------------------------------

/**
 * Der Ordner, in dem die Zähldaten liegen.
 *
 * Erste Wahl ist ein Ordner **neben** dem Dokumentenstamm: Was dort liegt,
 * ist über keine Adresse abrufbar, egal wie der Webserver eingestellt ist.
 * Verbietet ``open_basedir`` den Weg dorthin — bei manchen Paketen endet er
 * an httpdocs —, bleibt ein versteckter Ordner hier, gesichert durch eine
 * .htaccess, die das Skript selbst schreibt.
 */
function store_dir(): string
{
    $outside = dirname(__DIR__, 2) . '/solidon-stats';
    if (@is_dir($outside) || @mkdir($outside, 0750, true) || @is_dir($outside)) {
        return $outside;
    }

    $inside = __DIR__ . '/.stats';
    if (!@is_dir($inside)) {
        @mkdir($inside, 0750, true);
    }
    $guard = $inside . '/.htaccess';
    if (@is_dir($inside) && !@is_file($guard)) {
        @file_put_contents(
            $guard,
            "# Diese Daten gehören niemandem außer dem Betreiber.\n"
            . "Require all denied\n"
            . "<IfModule !mod_authz_core.c>\n  Deny from all\n</IfModule>\n"
        );
    }
    return $inside;
}

/**
 * Der Zufallswert des Tages, aus dem das Besucherkennzeichen entsteht.
 *
 * Er liegt in einer Datei, weil mehrere Aufrufe denselben brauchen, und er
 * wird überschrieben, sobald das Datum wechselt. Der Wert von gestern ist
 * damit weg — und mit ihm jede Möglichkeit, das Kennzeichen von gestern
 * einer IP-Adresse zuzuordnen.
 */
function day_salt(string $dir, string $day): string
{
    $file = $dir . '/salt.json';
    $current = @json_decode((string) @file_get_contents($file), true);
    if (is_array($current) && ($current['day'] ?? '') === $day && !empty($current['salt'])) {
        return (string) $current['salt'];
    }

    $salt = bin2hex(random_bytes(16));
    @file_put_contents(
        $file,
        json_encode(['day' => $day, 'salt' => $salt], JSON_UNESCAPED_SLASHES),
        LOCK_EX
    );
    return $salt;
}

/**
 * Das Kennzeichen dieses Besuchers für heute.
 *
 * IP und User-Agent gehen hinein, gespeichert wird nur das Ergebnis. Fehlt
 * eines von beidem, ist das Kennzeichen entsprechend gröber — das ist
 * hinnehmbar, denn es dient dem Zählen, nicht dem Wiedererkennen.
 */
function visitor_mark(string $salt): string
{
    $address = (string) ($_SERVER['REMOTE_ADDR'] ?? '');
    $agent = (string) ($_SERVER['HTTP_USER_AGENT'] ?? '');
    return substr(hash('sha256', $salt . '|' . $address . '|' . $agent), 0, MARK_LENGTH);
}

/**
 * Eine Zeile anhängen. Eine Datei je Monat, damit die Auswertung nicht
 * irgendwann eine Datei über hundert Megabyte einlesen muss.
 *
 * ``FILE_APPEND | LOCK_EX`` ist hier genug: Die Zeilen sind kurz, und zwei
 * gleichzeitige Aufrufe schreiben nacheinander statt ineinander.
 */
function record(string $kind, string $value): void
{
    $dir = store_dir();
    if (!@is_dir($dir)) {
        return;  // Kein Ablageort — dann eben keine Zahl. Ein Zähler hält nie den Betrieb an.
    }

    $now = new DateTimeImmutable('now', new DateTimeZone('UTC'));
    $day = $now->format('Y-m-d');
    $line = json_encode(
        [
            't' => $now->format('c'),
            'k' => $kind,
            'v' => $value,
            'r' => referrer_host(),
            'u' => visitor_mark(day_salt($dir, $day)),
        ],
        JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE
    );
    @file_put_contents($dir . '/' . $now->format('Y-m') . '.jsonl', $line . "\n", FILE_APPEND | LOCK_EX);
}

/**
 * Woher der Besucher kam — nur der Host, nicht die volle Adresse.
 *
 * Die volle Adresse einer verweisenden Seite kann einen Suchbegriff oder
 * eine Kennung enthalten; der Host beantwortet die Frage, die hier gestellt
 * wird („kam das über 3druck.com?"), und sonst nichts. Verweise von der
 * eigenen Domain fallen weg: Sie sind Navigation, keine Herkunft.
 */
function referrer_host(): string
{
    // **Der mitgeschickte Verweis gewinnt über den Header, und ohne ihn gibt
    // es überhaupt keinen.** Der Seitenaufruf kommt als Beacon aus `site.js`,
    // und dessen `Referer` ist die Seite, von der aus gerufen wird — also
    // immer solidon3d.de selbst. Die Prüfung unten erkennt sie als eigen und
    // verwirft sie, völlig zu Recht: Ein Sprung von Seite zu Seite ist kein
    // Verweis von außen. Nur stand damit in „Woher" nie etwas, und es sah aus
    // wie „niemand schickt seine Herkunft mit". Woher der Besucher wirklich
    // kam, weiß allein `document.referrer` im Browser; `site.js` reicht ihn
    // als `r` herein.
    //
    // Der Header bleibt der Weg für Downloads: Die laufen über `?f=` direkt
    // gegen diese Datei, ohne Skript, und dort ist er das Einzige, was es gibt.
    $referrer = (string) ($_POST['r'] ?? $_SERVER['HTTP_REFERER'] ?? '');
    if ($referrer === '') {
        return '';
    }
    $host = strtolower((string) parse_url($referrer, PHP_URL_HOST));

    // Der eigene Name ohne Port. ``HTTP_HOST`` trägt ihn mit, sobald der
    // Server nicht auf 80 oder 443 hört — beim Ausprobieren auf dem eigenen
    // Rechner ist das die Regel, und ohne diese Zeile zählte dort jeder
    // Sprung von Seite zu Seite als Verweis von außen.
    $own = strtolower((string) ($_SERVER['HTTP_HOST'] ?? ''));
    $own = (string) preg_replace('/:\d+$/', '', $own);

    $bare = static fn (string $name): string => preg_replace('/^www\./', '', $name) ?? $name;
    if ($host === '' || $own !== '' && $bare($host) === $bare($own)) {
        return '';
    }
    return substr($host, 0, 80);
}

// --- Eingänge --------------------------------------------------------------

/**
 * Einen Pfad auf das kürzen, was gezählt werden soll.
 *
 * Alles außer dem Pfad selbst fliegt weg: Abfrageteil, Sprungmarke,
 * Steuerzeichen. Was bleibt, ist die Seite — und die ist die Frage.
 */
function clean_path(string $raw): string
{
    $path = (string) parse_url(trim($raw), PHP_URL_PATH);
    if ($path === '' || $path[0] !== '/') {
        $path = '/' . ltrim($path, '/');
    }
    $path = preg_replace('/[^\x20-\x7e]/', '', $path) ?? '/';
    return substr($path, 0, MAX_PATH);
}

header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

$file = (string) ($_GET['f'] ?? '');
if ($file !== '') {
    // Download: nur ein Dateiname, kein Pfad, und die Datei muss es geben.
    $name = basename($file);
    if ($name === '' || $name !== $file || !is_file(DOWNLOAD_DIR . '/' . $name)) {
        http_response_code(404);
        header('Content-Type: text/plain; charset=utf-8');
        echo "Diese Datei gibt es hier nicht.\n";
        exit;
    }
    record('d', $name);
    header('Location: ' . DOWNLOAD_URL . rawurlencode($name), true, 302);
    exit;
}

$page = (string) ($_POST['p'] ?? $_GET['p'] ?? '');
if ($page !== '') {
    record('p', clean_path($page));
    http_response_code(204);
    exit;
}

// Ohne beides: Die Datei sagt, wofür sie da ist. Kein Fehler — wer sie von
// Hand aufruft, hat nichts falsch gemacht.
http_response_code(400);
header('Content-Type: text/plain; charset=utf-8');
echo "Zählpunkt von solidon3d.de. Erwartet ?f=<Datei> oder das Feld p.\n";
