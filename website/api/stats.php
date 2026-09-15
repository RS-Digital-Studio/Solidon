<?php
/**
 * Zeigt, was website/api/count.php gezählt hat — in vier Blöcken, die dem
 * Weg eines Kunden folgen:
 *
 *   Jetzt        rollend bis heute, 7 und 30 Tage, mit der Veränderung zum
 *                gleich langen Zeitraum davor — unabhängig vom Monat
 *   Reichweite   Aufrufe, Besuche, Herkunft, Sprache, Seiten, Einstieg und
 *                Ausstieg, Tiefe und Dauer, Uhrzeit und Wochentag
 *   Konversion   Downloads je Besuch, Version mal Zielsystem, die Seite vor
 *                dem Download, die Dateien im Ordner
 *   Nutzung      Update-Prüfungen je Version und je Tag — wie schnell eine
 *                neue Version die alte ablöst
 *
 * Alles daraus entsteht aus den fünf Feldern einer Zählzeile (Zeitpunkt,
 * Art, Wert, Verweis-Host, Tageskennzeichen); gespeichert wird für keine
 * dieser Zahlen ein Feld mehr. `?format=json` liefert dieselbe Auswertung
 * als JSON, für eine Tabelle oder ein Skript.
 *
 * Eine Seite für einen Leser. Sie liegt hinter einer Anmeldung, weil die
 * Zahlen niemanden außer dem Betreiber etwas angehen, und sie zeigt nur, was
 * der Zähler aufgeschrieben hat: keine IP-Adressen, keine User-Agents, keine
 * einzelnen Besucher über den Tag hinaus. Was hier nicht steht, steht auch in
 * den Daten nicht.
 *
 * Aufruf: https://solidon3d.de/api/stats.php — ein Feld, ein Passwort, und
 * danach dreißig Tage Ruhe.
 *
 * **Warum kein Basic-Auth.** Das war der erste Versuch, und er hatte zwei
 * Fehler. Das Anmeldefenster des Browsers verlangt einen Benutzernamen, den
 * hier niemand vergeben hat — wer davorsteht, muss raten, was dort hingehört.
 * Und es kam bei jedem Aufruf wieder: Läuft PHP als CGI oder FastCGI, was auf
 * Plesk die Regel ist, reicht der Webserver den `Authorization`-Kopf gar nicht
 * an PHP durch. Das richtige Passwort kommt dann nie an, die Seite antwortet
 * mit 401, und der Browser fragt erneut — von außen sieht das aus, als wäre
 * das Passwort falsch.
 *
 * Stattdessen ein eigenes Formular und ein signiertes Cookie. Das Cookie
 * trägt einen Ablaufzeitpunkt und dessen HMAC, abgeleitet aus dem
 * Passwort-Hash; auf dem Server liegt dafür nichts, es gibt keine
 * Sitzungsdateien und keinen Zustand, der volllaufen könnte. Wer das Cookie
 * fälschen will, braucht den Hash — und der liegt in einer Datei, die der
 * Webserver nicht herausgibt.
 *
 * **Einrichtung — ohne diesen Schritt bleibt die Seite zu.** Der Hash liegt
 * standardmäßig in `appdata/stats-access.php` neben dem Dokumentenstamm; ein
 * anderer absoluter, ebenfalls privater Pfad kommt aus
 * `SOLIDON_STATS_ACCESS_FILE`. Die Datei gehört dem Webserverkonto und trägt
 * auf POSIX höchstens Rechte 0600. Eine Lage im Dokumentenstamm wird auch dann
 * abgelehnt, wenn der Webserver PHP-Dateien normalerweise ausführt.
 *
 * Die Datei gibt ein Array der Form `['hash' => '<password_hash>']` zurück.
 * Ein Passwort-Hash im Repository oder Dokumentenstamm ist kein Geheimnis
 * mehr — und dieses hier schützt die einzige nicht-öffentliche Seite der
 * Domain.
 *
 * Braucht PHP 8.1 oder neuer.
 */

declare(strict_types=1);

require_once __DIR__ . '/day_zone.php';

if (PHP_VERSION_ID < 80100) {
    http_response_code(503);
    exit;
}

// --- Einstellungen ---------------------------------------------------------

/** Höchstgröße des einzigen Formularfelds samt Kodierung. */
const STATS_MAX_BODY = 2048;
const STATS_MAX_MONTH_BYTES = 16 * 1024 * 1024;
const STATS_MAX_LINE_BYTES = 1024;
const STATS_MAX_ROWS = 16384;

/** In welcher Zeitzone die Tage gezählt werden — dieselbe wie in count.php
 *  (day_zone.php). Gespeichert wird UTC; wer die Zahlen liest, denkt in
 *  seiner eigenen Zeit. */
const DISPLAY_ZONE = DAY_ZONE;

/** Wie viele Zeilen die Ranglisten zeigen. */
const TOP = 25;

/** Wie das Cookie heißt, das die Anmeldung merkt. */
const COOKIE = 'solidon_stats';

/** Wie lange es gilt. Lang genug, dass man es vergisst; kurz genug, dass ein
 *  liegengelassener Rechner nicht ewig offensteht. */
const COOKIE_DAYS = 30;

/** Wie viele Fehlversuche in einer Viertelstunde erlaubt sind. bcrypt bremst
 *  Rateversuche schon von sich aus auf wenige je Sekunde; das hier ist die
 *  zweite Wand dahinter. */
const MAX_TRIES = 10;
const MAX_GLOBAL_TRIES = 50;
/** Im Anmeldezähler bleiben bei jedem Zugriff höchstens 15 Minuten. */
const STATS_RATE_RETENTION_SECONDS = 900;

/** Schutzköpfe gelten auch für Anmelde- und Einrichtungsfehler. */
function stats_security_headers(): void
{
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: no-referrer');
    header('X-Frame-Options: DENY');
    header('Permissions-Policy: camera=(), microphone=(), geolocation=()');
    header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; "
        . "form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
    header('Cache-Control: no-store');
}

/** Die Zugangsakte liegt standardmäßig neben, nie unter dem Dokumentenstamm. */
function access_file(): string
{
    $configured = getenv('SOLIDON_STATS_ACCESS_FILE');
    $path = $configured === false || $configured === ''
        ? dirname(__DIR__, 2) . '/appdata/stats-access.php'
        : $configured;
    if (substr($path, 0, 1) !== DIRECTORY_SEPARATOR
        && preg_match('#^[A-Za-z]:[\\\\/]#', $path) !== 1) {
        return '';
    }
    $candidate = rtrim(str_replace('\\', '/', strtolower($path)), '/');
    if (preg_match('#(^|/)\.\.(/|$)#', $candidate) === 1) {
        return '';
    }
    $probe = $path;
    while (true) {
        if (is_link($probe)) {
            return '';
        }
        if (file_exists($probe)) {
            break;
        }
        $parent = dirname($probe);
        if ($parent === $probe) {
            return '';
        }
        $probe = $parent;
    }
    $resolved = realpath($probe);
    if ($resolved === false) {
        return '';
    }
    $candidate = rtrim(str_replace('\\', '/', strtolower($resolved)), '/');
    $root = realpath((string) ($_SERVER['DOCUMENT_ROOT'] ?? dirname(__DIR__)))
        ?: realpath(dirname(__DIR__));
    if ($root !== false) {
        $root = rtrim(str_replace('\\', '/', strtolower($root)), '/');
        if ($candidate === $root || strpos($candidate, $root . '/') === 0) {
            return '';
        }
    }
    return $path;
}

stats_security_headers();
$statsMethod = (string) ($_SERVER['REQUEST_METHOD'] ?? '');
// HEAD ist ein GET ohne Rumpf — RFC 9110 verlangt es, wo es GET gibt, und PHP
// verwirft den Rumpf von selbst. Ein 405 darauf stört jeden Wächter, der nur
// wissen will, ob die Seite noch steht (dieselbe Entscheidung wie count.php).
if ($statsMethod === 'HEAD') {
    $statsMethod = 'GET';
}
if (!in_array($statsMethod, ['GET', 'POST'], true)) {
    header('Allow: GET, HEAD, POST');
    http_response_code(405);
    exit;
}
if ($statsMethod === 'POST') {
    $origin = trim((string) ($_SERVER['HTTP_ORIGIN'] ?? ''));
    if (!in_array(strtolower($origin), ['https://solidon3d.de', 'https://www.solidon3d.de'], true)) {
        http_response_code(403);
        exit;
    }
    $type = strtolower(trim(explode(';', (string) ($_SERVER['CONTENT_TYPE'] ?? ''), 2)[0]));
    if ($type !== 'application/x-www-form-urlencoded') {
        http_response_code(415);
        exit;
    }
    $declared = (string) ($_SERVER['CONTENT_LENGTH'] ?? '');
    if ($declared !== '' && (!ctype_digit($declared) || (int) $declared > STATS_MAX_BODY)) {
        http_response_code(413);
        exit;
    }
    $rawBody = file_get_contents('php://input', false, null, 0, STATS_MAX_BODY + 1);
    if ($rawBody === false || strlen($rawBody) > STATS_MAX_BODY) {
        http_response_code(413);
        exit;
    }
}

// --- Anmeldung -------------------------------------------------------------

/**
 * Der Passwort-Hash — oder eine Seite, die sagt, was ihm fehlt.
 *
 * Fehlt die Zugangsdatei, gibt es kein Ersatzpasswort und keinen offenen
 * Zustand: Eine Statistikseite, die im Zweifel offen ist, ist schlimmer als
 * keine.
 */
function stored_hash(): string
{
    $path = access_file();
    $present = $path !== '' && is_file($path);

    // Die Rechte werden geprüft, **bevor** die Datei geladen wird: Eine zu
    // offene Zugangsdatei ist PHP, und wer sie erst ausführt und dann
    // abweist, hat den fremden Code schon laufen lassen.
    $exposed = $present
        && DIRECTORY_SEPARATOR === '/'
        && ((((int) fileperms($path) & 0077) !== 0)
            || (((int) fileperms(dirname($path)) & 0077) !== 0));
    if (!$present) {
        stats_unavailable($path === '' ? 'access_path_rejected' : 'access_file_missing');
    }
    if ($exposed) {
        stats_unavailable('access_permissions');
    }
    if (!is_readable($path)) {
        stats_unavailable('access_unreadable');
    }
    $access = @include $path;
    $hash = is_array($access) ? (string) ($access['hash'] ?? '') : '';
    if ($hash === '') {
        stats_unavailable('access_hash_missing');
    }

    // Ein beschädigter Hash, etwa durch verlorene Dollarzeichen, ist kein falsches Passwort.
    if ((password_get_info($hash)['algo'] ?? null) === null) {
        stats_unavailable('access_hash_invalid');
    }

    return $hash;
}

/**
 * Der Schlüssel, mit dem das Cookie unterschrieben wird.
 *
 * Abgeleitet aus dem Passwort-Hash und nicht aus dem Passwort: Der Hash liegt
 * ohnehin auf dem Server, es kommt also kein neues Geheimnis dazu, das
 * irgendwo hinterlegt werden müsste. Und wer das Passwort ändert, macht damit
 * jedes ausgestellte Cookie ungültig — genau das, was man von einem
 * Passwortwechsel erwartet.
 */
function signing_key(string $hash): string
{
    return hash('sha256', 'solidon-stats|' . $hash);
}

/** Ein frisches Cookie: bis wann es gilt, und die Unterschrift darüber. */
function make_token(string $hash): string
{
    $until = time() + COOKIE_DAYS * 86400;
    return $until . '.' . hash_hmac('sha256', (string) $until, signing_key($hash));
}

/**
 * Ob ein mitgebrachtes Cookie gilt.
 *
 * ``hash_equals`` und nicht ``===``: Ein gewöhnlicher Vergleich bricht beim
 * ersten ungleichen Zeichen ab, und aus der Zeit, die er dafür braucht, lässt
 * sich die richtige Unterschrift Zeichen für Zeichen erraten.
 */
function token_ok(string $token, string $hash): bool
{
    $parts = explode('.', $token, 2);
    if (count($parts) !== 2) {
        return false;
    }
    [$until, $signature] = $parts;
    $now = time();
    if (!ctype_digit($until) || strlen($signature) !== 64
        || !ctype_xdigit($signature) || (int) $until < $now
        || (int) $until > $now + COOKIE_DAYS * 86400) {
        return false;
    }
    return hash_equals(hash_hmac('sha256', $until, signing_key($hash)), $signature);
}

/** Wo die Fehlversuche gezählt werden — beim Zähler, nicht im Dokumentenstamm. */
function tries_file(): string
{
    return store_dir() . '/anmeldeversuche.json';
}

/** Zwei ohne den privaten Zugangshash nicht verknüpfbare Viertelstundenkennzeichen. */
function stats_rate_client_keys(string $hash, int $now): array
{
    $root = hash_hmac('sha256', 'solidon|stats-rate', signing_key($hash), true);
    $address = (string) ($_SERVER['REMOTE_ADDR'] ?? '-');
    $bucket = intdiv($now, STATS_RATE_RETENTION_SECONDS);
    $keys = [];
    foreach ([$bucket, $bucket - 1] as $number) {
        $windowSecret = hash_hmac('sha256', (string) $number, $root, true);
        $keys[] = 'ip:v2:' . hash_hmac('sha256', $address, $windowSecret);
    }
    return array_values(array_unique($keys));
}

/** Wie viele Fehlversuche in der letzten Viertelstunde stehen. */
function recent_tries(string $hash): int
{
    $counts = stats_update_tries(false, $hash);
    return count($counts['ip']) >= MAX_TRIES || count($counts['global']) >= MAX_GLOBAL_TRIES
        ? MAX_TRIES
        : count($counts['ip']);
}

/** Einen Fehlversuch vermerken; ältere fallen dabei heraus. */
function note_try(string $hash): void
{
    stats_update_tries(true, $hash);
}

/** Öffnet den Anmeldezähler ohne Links oder Mehrfachverweise. */
function stats_open_rate_state(string $path)
{
    if (is_link($path)) {
        return null;
    }
    $previousMask = umask(0077);
    try {
        $stream = @fopen($path, 'x+b');
    } finally {
        umask($previousMask);
    }
    $created = is_resource($stream);
    if (!$created) {
        if (is_link($path)) {
            return null;
        }
        $stream = @fopen($path, 'r+b');
    }
    if (!is_resource($stream) || !flock($stream, LOCK_EX)) {
        if (is_resource($stream)) {
            fclose($stream);
        }
        return null;
    }
    if ($created && DIRECTORY_SEPARATOR === '/' && !@chmod($path, 0600)) {
        flock($stream, LOCK_UN);
        fclose($stream);
        return null;
    }
    clearstatcache(true, $path);
    $opened = fstat($stream);
    $named = @lstat($path);
    if (!is_array($opened) || !is_array($named) || is_link($path) || !is_file($path)
        || (int) ($opened['dev'] ?? -1) !== (int) ($named['dev'] ?? -2)
        || (int) ($opened['ino'] ?? -1) !== (int) ($named['ino'] ?? -2)
        || (int) ($opened['nlink'] ?? 0) !== 1 || (int) ($named['nlink'] ?? 0) !== 1
        || (DIRECTORY_SEPARATOR === '/' && ((int) $opened['mode'] & 0077) !== 0)) {
        flock($stream, LOCK_UN);
        fclose($stream);
        return null;
    }
    return $stream;
}

/** Schreibt jeden angeforderten Byte auf den bereits geöffneten Stream. */
function stats_write_all($stream, string $data): bool
{
    $offset = 0;
    while ($offset < strlen($data)) {
        $written = fwrite($stream, substr($data, $offset));
        if ($written === false || $written === 0) {
            return false;
        }
        $offset += $written;
    }
    return true;
}

/** Erzwingt die Persistenz; Solidon verlangt dafür PHP 8.1 oder neuer. */
function stats_flush_and_sync($stream): bool
{
    return fflush($stream) && fsync($stream);
}

/** Stellt nach einem fehlgeschlagenen Ersatz den zuvor gelesenen Inhalt wieder her. */
function stats_restore_stream($stream, string $original): bool
{
    $positioned = fseek($stream, 0, SEEK_SET) === 0;
    $truncated = $positioned && ftruncate($stream, 0);
    $written = $truncated && stats_write_all($stream, $original);
    $synced = stats_flush_and_sync($stream);
    return $positioned && $truncated && $written && $synced;
}

/** Ersetzt einen Stream transaktional und gibt bei jedem Persistenzfehler false zurück. */
function stats_replace_stream($stream, string $data): bool
{
    if (fseek($stream, 0, SEEK_SET) !== 0) {
        return false;
    }
    $original = stream_get_contents($stream);
    if (!is_string($original) || fseek($stream, 0, SEEK_SET) !== 0
        || !ftruncate($stream, 0)) {
        return false;
    }
    if (stats_write_all($stream, $data) && stats_flush_and_sync($stream)) {
        return true;
    }
    if (!stats_restore_stream($stream, $original)) {
        error_log('Solidon: Wiederherstellung des Statistik-Zählers fehlgeschlagen.');
    }
    return false;
}

/** Schreibt den vollständigen Zähler auf denselben geprüften Handle. */
function stats_write_rate_state(string $path, $stream, string $data): bool
{
    clearstatcache(true, $path);
    $opened = fstat($stream);
    $named = @lstat($path);
    if (!is_array($opened) || !is_array($named) || is_link($path)
        || (int) ($opened['dev'] ?? -1) !== (int) ($named['dev'] ?? -2)
        || (int) ($opened['ino'] ?? -1) !== (int) ($named['ino'] ?? -2)
        || (int) ($opened['nlink'] ?? 0) !== 1 || (int) ($named['nlink'] ?? 0) !== 1
        || !stats_replace_stream($stream, $data)) {
        return false;
    }
    clearstatcache(true, $path);
    $named = @lstat($path);
    return is_array($named) && !is_link($path)
        && (int) ($opened['dev'] ?? -1) === (int) ($named['dev'] ?? -2)
        && (int) ($opened['ino'] ?? -1) === (int) ($named['ino'] ?? -2)
        && (int) ($named['nlink'] ?? 0) === 1;
}

/** Antwortet 503, wenn der Anmeldezähler nicht sicher zu öffnen ist — dieselbe
 *  Antwort wie bei einer unbrauchbaren Zugangsdatei. Vorher stand hier ein
 *  vorgetäuschter Sperrzustand, und die Anmeldung sagte „Zu viele Versuche“,
 *  obwohl niemand es versucht hatte; fail-closed bleibt, der Satz stimmt jetzt. */
function stats_unavailable(string $diagnostic): never
{
    $diagnostic = preg_match('/^[a-z_]{1,64}$/D', $diagnostic) === 1
        ? $diagnostic : 'unexpected_failure';
    error_log('Solidon Statistik: ' . $diagnostic
        . '. Private Zugangsdatei, Passwort-Hash und Zählerspeicher prüfen.');
    http_response_code(503);
    header('Content-Type: text/plain; charset=utf-8');
    echo "Diese Seite ist vorübergehend nicht verfügbar.
";
    exit;
}

/** Liest und ändert den IP-bezogenen Fehlversuchszähler unter einer Sperre. */
function stats_update_tries(bool $add, string $hash): array
{
    $path = tries_file();
    $stream = stats_open_rate_state($path);
    if (!is_resource($stream)) {
        stats_unavailable('rate_open_or_permissions');  // Speicherfehler: ehrlich 503 statt „Zu viele Versuche“.
    }
    try {
        $raw = stream_get_contents($stream);
        $state = $raw === '' ? [] : json_decode($raw === false ? '' : $raw, true);
        if ($raw === false || !is_array($state)) {
            stats_unavailable('rate_state_invalid');  // Speicherfehler: ehrlich 503 statt „Zu viele Versuche“.
        }
        $now = time();
        $clientKeys = stats_rate_client_keys($hash, $now);
        $key = $clientKeys[0];
        $globalKey = 'global';
        $since = $now - STATS_RATE_RETENTION_SECONDS;
        foreach ($state as $name => $stamps) {
            $recent = array_values(array_filter(
                (array) $stamps,
                static fn($stamp): bool => is_int($stamp) && $stamp > $since && $stamp <= $now
            ));
            if ($recent === [] || ($name !== $globalKey
                && preg_match('/^ip:v2:[0-9a-f]{64}$/D', (string) $name) !== 1)) {
                unset($state[$name]);
            } else {
                $state[$name] = $recent;
            }
        }
        $kept = [];
        foreach ($clientKeys as $clientKey) {
            $kept = array_merge($kept, (array) ($state[$clientKey] ?? []));
            unset($state[$clientKey]);
        }
        $global = array_values(array_filter(
            (array) ($state[$globalKey] ?? []),
            static fn($stamp): bool => is_int($stamp) && $stamp > $since && $stamp <= $now
        ));
        if ($add) {
            $kept[] = $now;
            $global[] = $now;
        }
        $state[$key] = $kept;
        $state[$globalKey] = $global;
        $encoded = json_encode($state, JSON_UNESCAPED_SLASHES);
        if (!is_string($encoded) || !stats_write_rate_state($path, $stream, $encoded)) {
            stats_unavailable('rate_state_write');  // Speicherfehler: ehrlich 503 statt „Zu viele Versuche“.
        }
        return ['ip' => $kept, 'global' => $global];
    } finally {
        flock($stream, LOCK_UN);
        fclose($stream);
    }
}

/** Das Cookie setzen oder löschen, mit allem, was dazugehört. */
function set_cookie(string $value, int $expires): void
{
    setcookie(COOKIE, $value, [
        'expires' => $expires,
        // Nur unterhalb von /api/ — die öffentlichen Seiten sehen es nie und
        // bleiben damit die cookiefreien Seiten, die sie versprechen.
        'path' => '/api/',
        'secure' => true,
        'httponly' => true,
        'samesite' => 'Strict',
    ]);
}

/**
 * Die Seite bleibt zu, bis sich jemand ausweist.
 *
 * Nach erfolgreicher Anmeldung wird umgeleitet statt gleich angezeigt: Sonst
 * steht das Passwort im letzten Formular, und ein Neuladen schickt es erneut.
 */
function require_login(): void
{
    $hash = stored_hash();

    if (isset($_GET['abmelden'])) {
        set_cookie('', time() - 3600);
        header('Location: /api/stats.php', true, 303);
        exit;
    }

    if (token_ok((string) ($_COOKIE[COOKIE] ?? ''), $hash)) {
        return;
    }

    $message = '';
    if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
        if (recent_tries($hash) >= MAX_TRIES) {
            $message = 'Zu viele Versuche. Eine Viertelstunde warten.';
        } elseif (is_string($_POST['password'] ?? null)
            && password_verify((string) $_POST['password'], $hash)) {
            set_cookie(make_token($hash), time() + COOKIE_DAYS * 86400);
            header('Location: /api/stats.php', true, 303);
            exit;
        } else {
            note_try($hash);
            $message = 'Das war es nicht.';
        }
    }

    login_page($message);
    exit;
}

/** Das Anmeldeformular. Ein Feld, sonst nichts. */
function login_page(string $message): void
{
    http_response_code($message === '' ? 401 : 403);
    header('Content-Type: text/html; charset=utf-8');
    $note = $message === ''
        ? ''
        : '<p class="fehler" role="alert">' . htmlspecialchars($message, ENT_QUOTES, 'UTF-8') . '</p>';
    echo <<<HTML
        <!doctype html>
        <html lang="de">
        <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="robots" content="noindex, nofollow">
        <title>Zugriffe — Solidon3D</title>
        <style>
          :root { color-scheme: light dark; --line: #d8d8d4; --dim: #6b6b66; }
          @media (prefers-color-scheme: dark) { :root { --line: #3a3a38; --dim: #9a9a94; } }
          body { font: 16px/1.5 system-ui, sans-serif; margin: 0; min-height: 100vh;
                 display: grid; place-items: center; padding: 2rem; }
          form { width: min(22rem, 100%); }
          h1 { font-size: 1.25rem; margin: 0 0 .25rem; }
          p { color: var(--dim); margin: 0 0 1.5rem; }
          p.fehler { color: inherit; font-weight: 600; margin: 0 0 1rem; }
          label { display: block; font-size: .85rem; color: var(--dim); margin: 0 0 .35rem; }
          input { width: 100%; box-sizing: border-box; font: inherit; padding: .6rem .75rem;
                  border: 1px solid var(--line); border-radius: .4rem; background: transparent;
                  color: inherit; }
          button { margin-top: .75rem; font: inherit; padding: .6rem 1.25rem;
                   border: 1px solid var(--line); border-radius: .4rem; background: transparent;
                   color: inherit; cursor: pointer; }
        </style>
        </head>
        <body>
        <form method="post" autocomplete="on">
          <h1>Zugriffe auf solidon3d.de</h1>
          <p>Nicht öffentlich. Ein Passwort, kein Benutzername.</p>
          {$note}
          <label for="password">Passwort</label>
          <input id="password" name="password" type="password" autocomplete="current-password"
                 autofocus required>
          <button type="submit">Ansehen</button>
        </form>
        </body>
        </html>
        HTML;
}

require_login();

// --- Daten lesen -----------------------------------------------------------

/** Derselbe Ordner wie in count.php — dieselbe Suche, damit beide auch dann
 *  zusammenfinden, wenn der Weg nach außen versperrt ist. */
function store_dir(): string
{
    $configured = getenv('SOLIDON_STATS_DIR');
    $outside = $configured === false || $configured === ''
        ? dirname(__DIR__, 2) . '/solidon-stats'
        : $configured;
    if (substr($outside, 0, 1) !== DIRECTORY_SEPARATOR
        && preg_match('#^[A-Za-z]:[\\\\/]#', $outside) !== 1) {
        return dirname(__DIR__, 2) . '/solidon-stats-unavailable';
    }
    $candidate = rtrim(str_replace('\\', '/', strtolower($outside)), '/');
    $root = realpath((string) ($_SERVER['DOCUMENT_ROOT'] ?? dirname(__DIR__)))
        ?: realpath(dirname(__DIR__));
    if (preg_match('#(^|/)\.\.(/|$)#', $candidate) === 1) {
        return dirname(__DIR__, 2) . '/solidon-stats-unavailable';
    }
    $probe = $outside;
    while (true) {
        if (is_link($probe)) {
            return dirname(__DIR__, 2) . '/solidon-stats-unavailable';
        }
        if (file_exists($probe)) {
            break;
        }
        $parent = dirname($probe);
        if ($parent === $probe) {
            return dirname(__DIR__, 2) . '/solidon-stats-unavailable';
        }
        $probe = $parent;
    }
    $resolved = realpath($probe);
    if ($resolved === false) {
        return dirname(__DIR__, 2) . '/solidon-stats-unavailable';
    }
    $candidate = rtrim(str_replace('\\', '/', strtolower($resolved)), '/');
    if ($root !== false) {
        $root = rtrim(str_replace('\\', '/', strtolower($root)), '/');
        if ($candidate === $root || strpos($candidate, $root . '/') === 0) {
            return dirname(__DIR__, 2) . '/solidon-stats-unavailable';
        }
    }
    if (!is_dir($outside)
        || (DIRECTORY_SEPARATOR === '/' && ((int) fileperms($outside) & 0077) !== 0)) {
        return dirname(__DIR__, 2) . '/solidon-stats-unavailable';
    }
    return $outside;
}

/** Welche Monate es gibt, neueste zuerst. */
function months(string $dir): array
{
    $found = [];
    foreach (glob($dir . '/*.jsonl') ?: [] as $path) {
        $found[] = basename($path, '.jsonl');
    }
    rsort($found);
    return $found;
}

/**
 * Die Zeilen eines Monats, jede in ihre Bestandteile zerlegt.
 *
 * Zeilen, die sich nicht lesen lassen, werden übergangen statt gemeldet:
 * Eine halb geschriebene letzte Zeile ist im laufenden Betrieb normal, und
 * sie ist kein Grund, den Rest des Monats nicht zu zeigen.
 */
function entries(string $dir, string $month, ?bool &$complete = null): array
{
    $complete = true;
    $path = $dir . '/' . $month . '.jsonl';
    $size = is_file($path) ? filesize($path) : false;
    if ($size === false) {
        return [];
    }
    if ($size > STATS_MAX_MONTH_BYTES) {
        $complete = false;
        return [];
    }
    $zone = new DateTimeZone(DISPLAY_ZONE);
    $rows = [];
    $stream = @fopen($path, 'rb');
    if ($stream === false) {
        return [];
    }
    try {
        while (count($rows) < STATS_MAX_ROWS
            && ($line = fgets($stream, STATS_MAX_LINE_BYTES + 1)) !== false) {
            if (strlen($line) > STATS_MAX_LINE_BYTES
                || (substr($line, -1) !== "\n" && !feof($stream))) {
                while (!feof($stream) && ($tail = fgets($stream, STATS_MAX_LINE_BYTES + 1)) !== false) {
                    if (substr($tail, -1) === "\n") {
                        break;
                    }
                }
                continue;
            }
            $row = json_decode(trim($line), true);
            if (!is_array($row) || empty($row['t'])) {
                continue;
            }
            try {
                $when = (new DateTimeImmutable((string) $row['t']))->setTimezone($zone);
            } catch (Exception $error) {
                continue;
            }
            $rows[] = [
                'day' => $when->format('Y-m-d'),
                'hour' => (int) $when->format('G'),
                'weekday' => (int) $when->format('N'),
                'stamp' => $when->getTimestamp(),
                'kind' => (string) ($row['k'] ?? ''),
                'value' => (string) ($row['v'] ?? ''),
                'from' => (string) ($row['r'] ?? ''),
                'mark' => (string) ($row['u'] ?? ''),
            ];
        }
        if (count($rows) >= STATS_MAX_ROWS && fgetc($stream) !== false) {
            $complete = false;
        }
    } finally {
        fclose($stream);
    }
    return $rows;
}

/** Ein Monat wird je Seitenaufbau höchstens einmal gelesen: Der gewählte
 *  Monat, der Monatsvergleich und das rollende Fenster fragen nach denselben
 *  Dateien. */
function month_rows(string $dir, string $month, ?bool &$complete = null): array
{
    static $cache = [];
    if (!array_key_exists($month, $cache)) {
        $cache[$month] = [entries($dir, $month, $done), $done];
    }
    [$rows, $complete] = $cache[$month];
    return $rows;
}

/** Zählen, wie oft jeder Wert vorkommt — absteigend. */
function tally(array $rows, string $field, ?string $kind = null): array
{
    $counts = [];
    foreach ($rows as $row) {
        if ($kind !== null && $row['kind'] !== $kind) {
            continue;
        }
        $value = $row[$field];
        if ($value === '') {
            continue;
        }
        $counts[$value] = ($counts[$value] ?? 0) + 1;
    }
    arsort($counts);
    return $counts;
}

/** Eine Zählung als Zeilenliste — Name als Text, nie als Array-Schlüssel.
 *  PHP macht aus „2026" als Schlüssel einen `int`; in der JSON-Ausgabe würde
 *  eine Liste daraus, sobald die Schlüssel zufällig bei null beginnen. */
function listed(array $counts, int $limit = 0): array
{
    $rows = [];
    foreach ($counts as $name => $count) {
        $rows[] = ['name' => (string) $name, 'count' => (int) $count];
        if ($limit > 0 && count($rows) >= $limit) {
            break;
        }
    }
    return $rows;
}

// --- Besuche ---------------------------------------------------------------

/**
 * Die Besuche eines Zeitraums: je Tag und Kennzeichen alles, was dieses
 * Kennzeichen an dem Tag getan hat — Seiten in Reihenfolge, Downloads, die
 * Seite unmittelbar vor jedem Download, die verweisende Seite des ersten
 * Aufrufs und die Zeitspanne vom ersten bis zum letzten Eintrag.
 *
 * Alles bleibt innerhalb eines Tages, aus demselben Grund wie die
 * Besucherzahl: Um Mitternacht wechselt das Kennzeichen, und was sich danach
 * noch zusammenfassen ließe, wäre eine Erfindung. **Update-Prüfungen sind
 * keine Besuche.** Sie kommen von einem laufenden Programm und tragen
 * absichtlich kein Kennzeichen; mitgezählt hätten sie die Besucherzahl um
 * jede Installation erhöht, die morgens startet. Downloads bleiben drin —
 * wer über einen Direktlink lädt, war da, auch ohne eine Seite zu öffnen.
 */
function visits_of(array $rows): array
{
    $found = [];
    foreach ($rows as $row) {
        if ($row['kind'] === 'u' || $row['mark'] === '') {
            continue;
        }
        $key = $row['day'] . '|' . $row['mark'];
        if (!isset($found[$key])) {
            $found[$key] = [
                'day' => $row['day'],
                'pages' => [],
                'downloads' => [],
                'before' => [],
                'from' => '',
                'start' => $row['stamp'],
                'end' => $row['stamp'],
            ];
        }
        $visit = &$found[$key];
        $visit['start'] = min($visit['start'], $row['stamp']);
        $visit['end'] = max($visit['end'], $row['stamp']);
        if ($visit['from'] === '' && $row['from'] !== '') {
            $visit['from'] = $row['from'];
        }
        if ($row['kind'] === 'p') {
            $visit['pages'][] = $row['value'];
        } elseif ($row['kind'] === 'd') {
            $visit['downloads'][] = $row['value'];
            $visit['before'][] = $visit['pages'] === [] ? '' : $visit['pages'][count($visit['pages']) - 1];
        }
        unset($visit);
    }
    return $found;
}

/** Je Tag: Aufrufe, Downloads, Update-Prüfungen und Besuche — aufsteigend. */
function per_day(array $rows, array $visits): array
{
    $days = [];
    foreach ($rows as $row) {
        $days[$row['day']][$row['kind']] = ($days[$row['day']][$row['kind']] ?? 0) + 1;
    }
    foreach ($visits as $visit) {
        $days[$visit['day']]['visits'] = ($days[$visit['day']]['visits'] ?? 0) + 1;
    }
    foreach ($days as &$counts) {
        $counts = [
            'p' => (int) ($counts['p'] ?? 0),
            'd' => (int) ($counts['d'] ?? 0),
            'u' => (int) ($counts['u'] ?? 0),
            'visits' => (int) ($counts['visits'] ?? 0),
        ];
    }
    unset($counts);
    ksort($days);
    return $days;
}

/** Die Summe der Tageswerte zwischen zwei Tagen, beide einschließlich. */
function window_sum(array $days, string $from, string $to): array
{
    $sum = ['p' => 0, 'd' => 0, 'u' => 0, 'visits' => 0];
    foreach ($days as $day => $counts) {
        if ($day < $from || $day > $to) {
            continue;
        }
        foreach ($sum as $key => $_) {
            $sum[$key] += $counts[$key];
        }
    }
    return $sum;
}

/** In welche Stufe eine Zahl fällt: Die Stufen nennen je ihre Obergrenze,
 *  die letzte ist offen. */
function band(int $value, array $bands): string
{
    foreach ($bands as $label => $upper) {
        if ($value <= $upper) {
            return (string) $label;
        }
    }
    return (string) array_key_last($bands);
}

/** Der Median einer Liste ganzer Zahlen — oder null, wenn sie leer ist. */
function median(array $values): ?int
{
    if ($values === []) {
        return null;
    }
    sort($values);
    $middle = intdiv(count($values), 2);
    return count($values) % 2 === 1
        ? (int) $values[$middle]
        : (int) round(($values[$middle - 1] + $values[$middle]) / 2);
}

/**
 * Zu welcher Sprachfassung ein Pfad gehört.
 *
 * Die Fassungen liegen als Unterordner (`/en/…`), die deutsche Quelle im
 * Wurzelverzeichnis — dieselbe Ordnung, die `available_languages()` in der
 * Anwendung liest. Hier reicht die feste Liste: Ein neuer Ordner auf dem
 * Server entsteht nicht ohne eine neue Sprachdatei im Repository.
 */
function language_of(string $path): string
{
    foreach (['en', 'es', 'fr', 'it', 'pt'] as $code) {
        if (strpos($path, '/' . $code . '/') === 0 || $path === '/' . $code) {
            return $code;
        }
    }
    return 'de';
}

/**
 * Zu welchem Zielsystem ein Paketname gehört.
 *
 * Die Muster folgen den fünf ausgelieferten Paketarten aus
 * `tools/make_download.py`; was keines trifft, bleibt unter seinem Namen
 * stehen, statt in einem „Sonstige"-Topf zu verschwinden.
 */
function platform_of(string $file): string
{
    if (stripos($file, 'Setup') !== false || stripos($file, '.exe') !== false) {
        return 'Windows';
    }
    if (stripos($file, '.flatpak') !== false || stripos($file, '.AppImage') !== false
        || stripos($file, 'linux') !== false || stripos($file, '.tar.') !== false) {
        return 'Linux';
    }
    if (stripos($file, 'arm64') !== false) {
        return 'macOS (Apple Silicon)';
    }
    if (stripos($file, 'macos') !== false) {
        return 'macOS (Intel)';
    }
    return $file;
}

/** Die Version im Paketnamen — „0.4.1" aus „Solidon3D-Setup-0.4.1.exe". */
function version_of(string $file): string
{
    return preg_match('/(\d+\.\d+\.\d+)/', $file, $found) === 1 ? $found[1] : 'ohne Version';
}

/** Versionen absteigend, alles ohne Versionsnummer dahinter. */
function newest_first(string $a, string $b): int
{
    $numericA = preg_match('/^\d+(\.\d+)*$/D', $a) === 1;
    $numericB = preg_match('/^\d+(\.\d+)*$/D', $b) === 1;
    if ($numericA && $numericB) {
        return version_compare($b, $a);
    }
    if ($numericA !== $numericB) {
        return $numericA ? -1 : 1;
    }
    return strcmp($a, $b);
}

/**
 * Was im Download-Ordner liegt, mit Größe — Dateiname als Schlüssel.
 *
 * Die zweite Hälfte der Antwort auf „welche Versionen sind draußen": Der
 * Zähler kennt nur, was schon einmal geladen wurde. Ein Paket, das seit einer
 * Stunde online ist und noch keinen Abruf hat, stünde sonst nirgends — und
 * genau danach sieht man nach einer Veröffentlichung als Erstes.
 */
function available_files(): array
{
    $found = [];
    foreach (glob(__DIR__ . '/../dl/*') ?: [] as $path) {
        if (is_file($path)) {
            $found[basename($path)] = (int) filesize($path);
        }
    }
    ksort($found);

    return $found;
}

/**
 * Die Pfade aus `sitemap.xml` — die Seiten, die es geben soll.
 *
 * Gegen die Aufrufe gehalten ergibt das die Seiten, die niemand liest: Der
 * Zähler kennt nur, was geöffnet wurde, und eine Seite ohne einen einzigen
 * Aufruf fehlt in jeder Liste, die er füllt. Gelesen wird mit einem
 * regulären Ausdruck statt eines XML-Parsers: Die Datei stammt aus
 * `tools/make_seo.py`, und gebraucht wird nur der Pfad hinter der Domain.
 */
function sitemap_paths(): array
{
    $xml = @file_get_contents(__DIR__ . '/../sitemap.xml');
    if (!is_string($xml) || $xml === '') {
        return [];
    }
    preg_match_all('#<loc>\s*https?://(?:www\.)?solidon3d\.de(/[^<\s]*)\s*</loc>#', $xml, $found);
    $paths = array_values(array_unique($found[1]));
    sort($paths);
    return $paths;
}

/** Die Version, die `version.json` gerade anbietet — leer, wenn sie fehlt. */
function current_release(): string
{
    $raw = @file_get_contents(__DIR__ . '/../version.json');
    $data = is_string($raw) ? json_decode($raw, true) : null;
    $version = is_array($data) ? (string) ($data['version'] ?? '') : '';
    return preg_match('/^[0-9]+(?:\.[0-9]+){0,3}$/D', $version) === 1 ? $version : '';
}

/** Die Kopfzeile eines Monats: Aufrufe, Besuche, Downloads, Update-Prüfungen
 *  — für den Vergleich über die Monate, ohne die ganze Seite je Monat
 *  aufzubauen. */
function month_totals(string $dir, string $month): array
{
    // `entries()` kennt seine Grenze und sagt sie über `$complete`; bis zum
    // 05.09.2026 warf diese Summe das weg, und ein Monat über 16.384 Zeilen
    // stand im Vergleich als vollständige Zahl (Gesamtreview, R30).
    $rows = month_rows($dir, $month, $complete);
    $sum = window_sum(per_day($rows, visits_of($rows)), '0000-00-00', '9999-99-99');
    return [
        'month' => $month,
        'pages' => $sum['p'],
        'visitors' => $sum['visits'],
        'downloads' => $sum['d'],
        'updates' => $sum['u'],
        'complete' => $complete,
    ];
}

// --- Auswertung ------------------------------------------------------------

$dir = store_dir();
$available = months($dir);
$zone = new DateTimeZone(DISPLAY_ZONE);
$now = new DateTimeImmutable('now', $zone);
$current = $now->format('Y-m');
$today = $now->format('Y-m-d');
$month = (string) ($_GET['m'] ?? ($available[0] ?? $current));
if (!preg_match('/^\d{4}-\d{2}$/D', $month)) {
    $month = $current;
}

// -- Jetzt: rollend bis heute, unabhängig vom gewählten Monat ---------------
//
// Die Monatsgrenze ist eine Eigenschaft der Ablage, nicht der Frage. Am
// Zweiten eines Monats zeigt der Monat zwei Tage, und ob die Woche gut lief,
// steht in der Datei davor. Geladen werden nur die Monate, die das längste
// Fenster berühren — nach der Löschfrist sind das höchstens drei.
$spans = [7, 30];
$longest = max($spans) * 2;
$earliestWanted = $now->modify('-' . ($longest + 1) . ' days')->format('Y-m');
$recentMonths = array_values(array_filter(
    $available,
    static fn (string $option): bool => $option >= $earliestWanted && $option <= $current
));
$recentRows = [];
$recentComplete = true;
foreach ($recentMonths as $option) {
    $recentRows = array_merge($recentRows, month_rows($dir, $option, $done));
    $recentComplete = $recentComplete && $done;
}
$recentDays = per_day($recentRows, visits_of($recentRows));
// Ab wann die Daten reichen: der erste gezählte Tag — oder weiter zurück,
// wenn es noch ältere Monatsdateien gibt, die das Fenster nicht braucht.
$coverage = $recentDays === [] ? null : (string) array_key_first($recentDays);
if ($recentMonths !== [] && count($available) > count($recentMonths)) {
    $coverage = '0000-00-00';
}
$windows = [];
foreach ($spans as $span) {
    $from = $now->modify('-' . ($span - 1) . ' days')->format('Y-m-d');
    $beforeFrom = $now->modify('-' . (2 * $span - 1) . ' days')->format('Y-m-d');
    $beforeTo = $now->modify('-' . $span . ' days')->format('Y-m-d');
    $comparable = $coverage !== null && $coverage <= $beforeFrom;
    $windows[] = [
        'days' => $span,
        'from' => $from,
        'to' => $today,
        'now' => window_sum($recentDays, $from, $today),
        'before' => $comparable ? window_sum($recentDays, $beforeFrom, $beforeTo) : null,
    ];
}
$todayCounts = $recentDays[$today] ?? ['p' => 0, 'd' => 0, 'u' => 0, 'visits' => 0];

// -- Der gewählte Monat -------------------------------------------------------

$rows = month_rows($dir, $month, $month_complete);
$visits = visits_of($rows);
$days = per_day($rows, $visits);
$pages = array_values(array_filter($rows, static fn (array $row): bool => $row['kind'] === 'p'));
$downloads = array_values(array_filter($rows, static fn (array $row): bool => $row['kind'] === 'd'));
$monthSum = window_sum($days, '0000-00-00', '9999-99-99');
$visitCount = count($visits);

// Seiten je Besuch — die eine Zahl, die „viele Aufrufe" von „viele Leute"
// unterscheidet. Ohne Besuche bleibt sie leer statt durch null zu teilen.
$pagesPerVisit = $visitCount > 0 ? round(count($pages) / $visitCount, 1) : null;

// Besuchsdauer: vom ersten zum letzten Eintrag, nur wo es zwei gibt. Ein
// Besuch mit einer Seite hat keine messbare Dauer — der Zähler sieht das
// Öffnen, nicht das Schließen. Der Median statt des Mittelwerts, weil ein
// offen gelassener Tab sonst den Monat prägt.
$durations = [];
$durationBands = ['unter 1 Minute' => 59, '1 bis 5 Minuten' => 300,
    '5 bis 15 Minuten' => 900, 'über 15 Minuten' => PHP_INT_MAX];
$duration = array_fill_keys(array_keys($durationBands), 0);
$depthBands = ['1 Seite' => 1, '2 bis 3' => 3, '4 bis 9' => 9, '10 und mehr' => PHP_INT_MAX];
$depth = array_fill_keys(array_keys($depthBands), 0);
$entryPages = [];
$exitPages = [];
$sources = [];
$languages = [];
$visitsWithDownload = 0;
$downloadsWithoutPage = 0;
$beforeDownload = [];
foreach ($visits as $visit) {
    $steps = count($visit['pages']) + count($visit['downloads']);
    if ($steps >= 2) {
        $seconds = $visit['end'] - $visit['start'];
        $durations[] = $seconds;
        $duration[band($seconds, $durationBands)]++;
    }
    $downloaded = $visit['downloads'] !== [];
    if ($downloaded) {
        $visitsWithDownload++;
    }
    if ($visit['pages'] === []) {
        $downloadsWithoutPage += count($visit['downloads']);
    } else {
        $depth[band(count($visit['pages']), $depthBands)]++;
        $first = $visit['pages'][0];
        $last = $visit['pages'][count($visit['pages']) - 1];
        $entryPages[$first] = ($entryPages[$first] ?? 0) + 1;
        $exitPages[$last] = ($exitPages[$last] ?? 0) + 1;
    }
    foreach ($visit['before'] as $page) {
        $beforeDownload[$page] = ($beforeDownload[$page] ?? 0) + 1;
    }

    // Herkunft und Sprache je Besuch, nicht je Aufruf: Die Frage ist „wie
    // viele Leute kamen über 3druck.com, und wie viele davon haben geladen" —
    // nicht, wie viele Seiten sie dabei geöffnet haben.
    $source = $visit['from'];
    $sources[$source] = $sources[$source] ?? ['visits' => 0, 'pages' => 0, 'downloaded' => 0, 'downloads' => 0];
    $sources[$source]['visits']++;
    $sources[$source]['pages'] += count($visit['pages']);
    $sources[$source]['downloaded'] += $downloaded ? 1 : 0;
    $sources[$source]['downloads'] += count($visit['downloads']);

    $code = $visit['pages'] === [] ? '' : language_of($visit['pages'][0]);
    $languages[$code] = $languages[$code] ?? ['visits' => 0, 'pages' => 0, 'downloaded' => 0, 'downloads' => 0];
    $languages[$code]['visits']++;
    $languages[$code]['pages'] += count($visit['pages']);
    $languages[$code]['downloaded'] += $downloaded ? 1 : 0;
    $languages[$code]['downloads'] += count($visit['downloads']);
}
$direct = $sources[''] ?? ['visits' => 0, 'pages' => 0, 'downloaded' => 0, 'downloads' => 0];
unset($sources['']);
uasort($sources, static fn (array $a, array $b): int => $b['visits'] <=> $a['visits']);
$withoutPage = $languages[''] ?? null;
unset($languages['']);
uasort($languages, static fn (array $a, array $b): int => $b['visits'] <=> $a['visits']);
arsort($entryPages);
arsort($exitPages);
arsort($beforeDownload);
$languageNames = ['de' => 'Deutsch', 'en' => 'Englisch', 'es' => 'Spanisch',
    'fr' => 'Französisch', 'it' => 'Italienisch', 'pt' => 'Portugiesisch'];

// Seiten mit Anteil — und die Seiten aus der Sitemap, die niemand geöffnet hat.
$paths = tally($rows, 'value', 'p');
$unread = array_values(array_filter(
    sitemap_paths(),
    static fn (string $path): bool => !isset($paths[$path])
));

// Nach Stunde und Wochentag, nur Seitenaufrufe: wann gelesen wird.
$byHour = array_fill(0, 24, 0);
$byWeekday = array_fill(1, 7, 0);
foreach ($pages as $row) {
    $byHour[$row['hour']]++;
    $byWeekday[$row['weekday']]++;
}
$weekdayNames = [1 => 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag',
    'Freitag', 'Samstag', 'Sonntag'];

// Alle Monate nebeneinander — erst ab dem zweiten lohnt die Tabelle.
$monthRows = [];
if (count($available) > 1) {
    foreach ($available as $option) {
        $monthRows[] = month_totals($dir, $option);
    }
    usort($monthRows, static fn (array $a, array $b): int => strcmp($a['month'], $b['month']));
}

// -- Konversion ---------------------------------------------------------------

// Version mal Zielsystem: Fünf Pakete je Version als flache Dateiliste
// beantworten nicht, welche Version gerade läuft und auf welchem System —
// die Matrix tut es. Die aktuelle Version aus `version.json` steht auch ohne
// einen einzigen Abruf mit null drin, sonst fehlte gerade das, was man nach
// einer Veröffentlichung als Erstes sucht. Ältere Pakete im Ordner bekommen
// keine Nullzeile — sechzehn Versionen mal vier Spalten Nullen sagen nichts.
$release = current_release();
$platformOrder = ['Windows', 'Linux', 'macOS (Apple Silicon)', 'macOS (Intel)'];
$matrix = $release !== '' ? [$release => []] : [];
$platforms = $platformOrder;
foreach ($downloads as $row) {
    $version = version_of($row['value']);
    $platform = platform_of($row['value']);
    $matrix[$version][$platform] = ($matrix[$version][$platform] ?? 0) + 1;
    if (!in_array($platform, $platforms, true)) {
        $platforms[] = $platform;
    }
}
$present = available_files();
uksort($matrix, static fn ($a, $b): int => newest_first((string) $a, (string) $b));
$matrixRows = [];
foreach ($matrix as $version => $cells) {
    $line = ['version' => (string) $version, 'cells' => [], 'total' => 0];
    foreach ($platforms as $platform) {
        $line['cells'][$platform] = (int) ($cells[$platform] ?? 0);
        $line['total'] += (int) ($cells[$platform] ?? 0);
    }
    $matrixRows[] = $line;
}
$platformTotals = [];
foreach ($platforms as $platform) {
    $platformTotals[$platform] = array_sum(array_column(array_column($matrixRows, 'cells'), $platform));
}

// Dateien: erst die gezählten in ihrer Reihenfolge, dann was sonst im Ordner
// liegt. `+` behält die linken Schlüssel, ergänzt also nur die ohne Abruf.
$fileCounts = tally($rows, 'value', 'd') + array_map(static fn (int $size): int => 0, $present);
$files = [];
foreach ($fileCounts as $name => $count) {
    $files[] = [
        'name' => (string) $name,
        'count' => (int) $count,
        'bytes' => isset($present[$name]) ? (int) $present[$name] : null,
    ];
}

$conversion = $visitCount > 0 ? round($visitsWithDownload / $visitCount * 100, 1) : null;

// -- Nutzung --------------------------------------------------------------------

// Updateabrufe tragen keine Besucherkennung. Wiederholte Abrufe bleiben
// einzelne Prüfungen; eine Zahl von Rechnern lässt sich daraus nicht ableiten.
$versions = tally($rows, 'value', 'u');
$updateCount = $monthSum['u'];
$releaseShare = $updateCount > 0 && $release !== '' && isset($versions[$release])
    ? round($versions[$release] / $updateCount * 100, 1)
    : null;
// Ø je Tag über die Kalendertage, die der Monat bis heute hat — nicht über
// die Tage mit Einträgen, sonst zählte ein stiller Sonntag nicht als Tag.
$monthStart = DateTimeImmutable::createFromFormat('!Y-m-d', $month . '-01', $zone);
$daysElapsed = 0;
if ($monthStart instanceof DateTimeImmutable) {
    $daysElapsed = $month === $current
        ? (int) $now->format('j')
        : ($month < $current ? (int) $monthStart->format('t') : 0);
}
$updatesPerDay = $daysElapsed > 0 ? round($updateCount / $daysElapsed, 1) : null;

// Versionen Tag für Tag: die meistgesehenen einzeln, der Rest als „andere".
// Daran liest man, wie schnell eine neue Version die alte ablöst.
$versionColumns = array_slice(array_keys($versions), 0, 5);
usort($versionColumns, static fn ($a, $b): int => newest_first((string) $a, (string) $b));
$versionColumns = array_map('strval', $versionColumns);
$versionsPerDay = [];
foreach ($rows as $row) {
    if ($row['kind'] !== 'u') {
        continue;
    }
    $column = in_array($row['value'], $versionColumns, true) ? $row['value'] : 'andere';
    $versionsPerDay[$row['day']][$column] = ($versionsPerDay[$row['day']][$column] ?? 0) + 1;
}
ksort($versionsPerDay);
$versionDayRows = [];
foreach ($versionsPerDay as $day => $cells) {
    $line = ['day' => (string) $day, 'cells' => [], 'other' => (int) ($cells['andere'] ?? 0), 'total' => 0];
    foreach ($versionColumns as $column) {
        $line['cells'][$column] = (int) ($cells[$column] ?? 0);
    }
    $line['total'] = array_sum($line['cells']) + $line['other'];
    $versionDayRows[] = $line;
}

// -- Der Bericht: eine Struktur, zwei Ausgaben --------------------------------

$report = [
    'month' => $month,
    'zone' => DISPLAY_ZONE,
    'today' => $today,
    'complete' => $month_complete,
    'months_available' => $available,
    'now' => [
        'complete' => $recentComplete,
        'coverage_from' => $coverage === '0000-00-00' ? null : $coverage,
        'today' => $todayCounts,
        'windows' => $windows,
    ],
    'reach' => [
        'pages' => $monthSum['p'],
        'visits' => $visitCount,
        'pages_per_visit' => $pagesPerVisit,
        'median_duration_seconds' => median($durations),
        'per_day' => $days,
        'months' => $monthRows,
        'direct' => $direct,
        'sources' => array_slice($sources, 0, TOP, true),
        'languages' => $languages,
        'without_page' => $withoutPage,
        'paths' => listed($paths, TOP),
        'unread' => $unread,
        'entry_pages' => listed($entryPages, TOP),
        'exit_pages' => listed($exitPages, TOP),
        'depth' => $depth,
        'duration' => $duration,
        'by_hour' => $byHour,
        'by_weekday' => $byWeekday,
    ],
    'conversion' => [
        'downloads' => $monthSum['d'],
        'visits_with_download' => $visitsWithDownload,
        'visits_with_download_percent' => $conversion,
        'downloads_without_page' => $downloadsWithoutPage,
        'platforms' => $platforms,
        'matrix' => $matrixRows,
        'platform_totals' => $platformTotals,
        'page_before_download' => listed($beforeDownload, TOP),
        'files' => $files,
    ],
    'usage' => [
        'updates' => $updateCount,
        'updates_per_day' => $updatesPerDay,
        'release' => $release,
        'release_share_percent' => $releaseShare,
        'versions' => listed($versions),
        'version_columns' => $versionColumns,
        'versions_per_day' => $versionDayRows,
    ],
];

// Dieselben Zahlen als JSON — für eine Tabelle, ein Skript, einen Vergleich
// von Hand. Gerechnet wird nichts anderes: Wer beide Ausgaben nebeneinander
// legt, sieht dieselben Werte.
if ((string) ($_GET['format'] ?? '') === 'json') {
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    echo "\n";
    exit;
}

// --- Darstellung -------------------------------------------------------------

/**
 * Maskiert einen Text für die Ausgabe.
 *
 * Nimmt auch eine Ganzzahl, und das ist kein Komfort: Mehrere Aufrufstellen
 * übergeben einen **Array-Schlüssel**, und PHP wandelt einen kanonischen
 * Dezimaltext beim Eintragen still in einen `int`. Ein Referrer-Host, der nur
 * aus Ziffern besteht, kam so als `int` hier an und ließ die Seite unter
 * `declare(strict_types=1)` mit einem `TypeError` mitten im Rendern
 * abbrechen — die Statistik brach ab der Herkunftstabelle ab, mit Status 200
 * (Sicherheitsdurchsicht 04.09.2026). `count.php` lässt einen rein
 * numerischen Host inzwischen nicht mehr durch; diese Signatur ist die
 * Gegenprobe an der Stelle, an der es darauf ankommt, und deckt auch andere
 * numerische Tabellenschlüssel ab. Vor einer URL-Kodierung muss der Name
 * ebenfalls als Text vorliegen.
 */
function e(string|int $text): string
{
    return htmlspecialchars((string) $text, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/** Eine Zahl mit Tausenderpunkt und Dezimalkomma. */
function n(int|float|null $value, int $decimals = 0): string
{
    return $value === null ? '—' : number_format((float) $value, $decimals, ',', '.');
}

/** Ein Balken, dessen Breite am Höchstwert der Tabelle hängt — nie unter
 *  einem Prozent, damit auch ein einzelner Abruf sichtbar bleibt. */
function bar(int $value, int $peak): string
{
    return '<span class="balken" style="width: ' . max(1, (int) round($value / max(1, $peak) * 100)) . '%"></span>';
}

/**
 * Eine Dateigröße in ganzen Megabyte — dezimal gerechnet.
 *
 * Durch 1 000 000 und nicht durch 1 048 576, weil `tools/make_download.py`
 * es so rechnet und der Download-Kasten die Zahl trägt. Beide Wege sind
 * vertretbar; zwei verschiedene Zahlen für dieselbe Datei auf derselben
 * Domain sind es nicht (165 gegen 173 MB, gemessen am 20.08.2026).
 */
function megabytes(int $bytes): string
{
    return number_format($bytes / 1000000, 0, ',', '.') . ' MB';
}

/** Eine Dauer in Sekunden als „4 Min 12 s" — Sekunden allein unter einer Minute. */
function duration_text(?int $seconds): string
{
    if ($seconds === null) {
        return '—';
    }
    if ($seconds < 60) {
        return $seconds . ' s';
    }
    return intdiv($seconds, 60) . ' Min ' . ($seconds % 60) . ' s';
}

/** Ein Tag als „15.09." für die Fensterbeschriftung. */
function short_day(string $day): string
{
    return substr($day, 8, 2) . '.' . substr($day, 5, 2) . '.';
}

/**
 * Die Veränderung zum Zeitraum davor: „+12 %", „−8 %", „±0 %". Ohne
 * Vergleichszeitraum ein Strich mit dem Grund im Tooltip — die Daten reichen
 * nach der Löschfrist von zwei Monaten nicht immer sechzig Tage zurück, und
 * eine Veränderung gegen einen halb vorhandenen Zeitraum wäre eine Zahl, die
 * lügt. Vorzeichen als Text, nicht als Farbe.
 */
function change(?array $before, array $now, string $key): string
{
    if ($before === null) {
        return '<span class="delta leer" title="Kein Vergleich: Die Daten reichen nicht bis zum Zeitraum davor zurück.">—</span>';
    }
    $was = (int) $before[$key];
    $is = (int) $now[$key];
    if ($was === 0) {
        return '<span class="delta">' . ($is === 0 ? '±0' : 'vorher 0') . '</span>';
    }
    $percent = ($is - $was) / $was * 100;
    $sign = $percent > 0.5 ? '+' : ($percent < -0.5 ? '−' : '±');
    return '<span class="delta">' . $sign . n(abs($percent)) . ' %</span>';
}

?><!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Zugriffe — Solidon3D</title>
<style>
  /* Ein Armaturenbrett für einen Leser an einem breiten Bildschirm: die
     Kacheln füllen die Breite, die Sprungleiste bleibt oben stehen, und die
     Tabellen sind dicht genug, dass ein Monat auf einen Blick passt. */
  :root { color-scheme: light dark; --line: #d8d8d4; --dim: #6b6b66; --bar: #3a6ea5; --band: #f4f4f1; --page: #fbfbfa; }
  @media (prefers-color-scheme: dark) { :root { --line: #3a3a38; --dim: #9a9a94; --bar: #6fa3d8; --band: #232321; --page: #171716; } }
  body { font: 15px/1.45 system-ui, sans-serif; margin: 0; padding: 1.25rem 2rem 4rem; background: var(--page); }
  h1 { font-size: 1.4rem; margin: 0 0 .25rem; }
  h1 .abmelden { font-size: .8rem; font-weight: normal; margin-left: .75rem; vertical-align: middle; }
  h2 { font-size: 1.15rem; margin: 2.25rem 0 .75rem; display: flex; align-items: baseline; gap: 1rem; }
  h2 .sub { margin: 0; font-size: .9rem; font-weight: normal; }
  .sub { color: var(--dim); margin: 0 0 1rem; }
  nav.sprung { position: sticky; top: 0; z-index: 1; margin: .75rem -2rem 1rem; padding: .5rem 2rem; background: var(--band); border-bottom: 1px solid var(--line); }
  nav.sprung a { margin-right: 1.5rem; }
  nav.sprung .monate { float: right; color: var(--dim); }
  nav.sprung .monate a { margin: 0 0 0 .75rem; }
  .zahlen { display: flex; flex-wrap: wrap; gap: .75rem; margin: 0 0 1rem; }
  .zahl { border: 1px solid var(--line); border-radius: .5rem; padding: .6rem 1rem; min-width: 9rem; flex: 0 1 auto; }
  .zahl b { display: block; font-size: 1.5rem; line-height: 1.2; }
  .zahl span { color: var(--dim); font-size: .8rem; }
  .kacheln { display: grid; grid-template-columns: repeat(auto-fit, minmax(21rem, 1fr)); gap: 1rem; grid-auto-flow: dense; align-items: start; }
  .kachel { border: 1px solid var(--line); border-radius: .5rem; padding: .75rem 1rem 1rem; min-width: 0; overflow-x: auto; }
  .kachel h3 { margin: 0 0 .35rem; font-size: .95rem; }
  .kachel .sub { font-size: .82rem; margin: 0 0 .6rem; }
  .breit { grid-column: span 2; }
  @media (max-width: 48rem) { .breit { grid-column: auto; } body { padding: 1rem; } nav.sprung { margin: .75rem -1rem 1rem; padding: .5rem 1rem; } }
  table { border-collapse: collapse; width: 100%; font-size: .9rem; }
  th, td { text-align: left; padding: .22rem .45rem; border-bottom: 1px solid var(--line); vertical-align: baseline; }
  th { color: var(--dim); font-weight: normal; font-size: .8rem; white-space: nowrap; }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  tr.summe td { font-weight: 600; border-top: 2px solid var(--line); }
  .balken { display: block; height: .5rem; background: var(--bar); border-radius: 2px; min-width: 1px; }
  .leer { color: var(--dim); font-style: italic; }
  .hinweis { color: var(--dim); max-width: 70ch; font-size: .9rem; }
  .delta { display: block; font-size: .78rem; color: var(--dim); font-style: normal; }
  .fenster { max-width: 64rem; }
  .fenster td:first-child { white-space: nowrap; }
  .fenster small { color: var(--dim); }
  ul.pfade { columns: 2; column-gap: 2rem; margin: 0; padding-left: 1.25rem; font-size: .9rem; }
  code { font-size: .9em; }
  .warnung { border: 1px solid #b45309; padding: .75rem 1rem; }
</style>
</head>
<body>

<h1>Zugriffe auf solidon3d.de <a class="abmelden" href="?abmelden=1">abmelden</a></h1>
<p class="sub">Monat <?= e($month) ?>, Zeiten in <?= e(DISPLAY_ZONE) ?>.
Dieselben Zahlen <a href="?m=<?= e($month) ?>&amp;format=json">als JSON</a>.
Was hier gezählt wird und was nicht, steht <a href="#methode">unten</a>.</p>

<nav class="sprung"><a href="#jetzt">Jetzt</a><a href="#reichweite">Reichweite</a><a href="#konversion">Konversion</a><a href="#nutzung">Nutzung</a><a href="#methode">Methode</a><?php if (count($available) > 1): ?><span class="monate">Monat:
  <?php foreach ($available as $option): ?>
    <?php if ($option === $month): ?><b><?= e($option) ?></b>
    <?php else: ?><a href="?m=<?= e($option) ?>"><?= e($option) ?></a><?php endif; ?>
  <?php endforeach; ?></span><?php endif; ?></nav>

<?php if (!$month_complete): ?>
<p class="warnung"><b>Unvollständige Auswertung:</b> Die Monatsdatei überschreitet
die sichere Grenze von 16 MiB oder 16.384 gültigen Zeilen. Die angezeigten Zahlen
sind nicht vollständig; bitte die Datei archivieren und den Zähler prüfen.</p>
<?php endif; ?>

<h2 id="jetzt">Jetzt <span class="sub">rollend bis heute, unabhängig vom gewählten Monat — die kleine
Zahl ist die Veränderung zum gleich langen Zeitraum davor<?php if (!$recentComplete): ?>;
<b>eine Monatsdatei ist unvollständig gelesen, die Werte sind Untergrenzen</b><?php endif; ?></span></h2>
<?php if ($recentDays === []): ?>
  <p class="leer">Noch nichts gezählt.</p>
<?php else: ?>
<table class="fenster">
  <tr><th></th><th class="n">Besuche</th><th class="n">Aufrufe</th><th class="n">Downloads</th><th class="n">Update-Prüfungen</th></tr>
  <tr>
    <td>Heute <small><?= e(short_day($today)) ?></small></td>
    <td class="n"><?= n($todayCounts['visits']) ?></td>
    <td class="n"><?= n($todayCounts['p']) ?></td>
    <td class="n"><?= n($todayCounts['d']) ?></td>
    <td class="n"><?= n($todayCounts['u']) ?></td>
  </tr>
  <?php foreach ($windows as $window): ?>
  <tr>
    <td>Letzte <?= (int) $window['days'] ?> Tage <small><?= e(short_day($window['from'])) ?>–<?= e(short_day($window['to'])) ?></small></td>
    <td class="n"><?= n($window['now']['visits']) ?><?= change($window['before'], $window['now'], 'visits') ?></td>
    <td class="n"><?= n($window['now']['p']) ?><?= change($window['before'], $window['now'], 'p') ?></td>
    <td class="n"><?= n($window['now']['d']) ?><?= change($window['before'], $window['now'], 'd') ?></td>
    <td class="n"><?= n($window['now']['u']) ?><?= change($window['before'], $window['now'], 'u') ?></td>
  </tr>
  <?php endforeach; ?>
</table>
<?php endif; ?>

<?php if (!$rows): ?>
<h2 id="reichweite">Reichweite</h2>
  <p class="leer">Für den Monat <?= e($month) ?> liegt nichts vor. Entweder hat
  noch niemand die Seite geöffnet, oder <code>count.php</code> kommt nicht an
  seinen privaten Ablageordner.</p>
<h2 id="konversion">Konversion</h2>
  <p class="leer">Ohne Zeilen keine Downloads.</p>
<h2 id="nutzung">Nutzung</h2>
  <p class="leer">Ohne Zeilen keine Update-Prüfungen.</p>
<?php else: ?>

<h2 id="reichweite">Reichweite <span class="sub">wer kommt, woher, und was gelesen wird — im Monat <?= e($month) ?></span></h2>

<div class="zahlen">
  <div class="zahl"><b><?= n($monthSum['p']) ?></b><span>Seitenaufrufe</span></div>
  <div class="zahl"><b><?= n($visitCount) ?></b><span>Besuche (Summe der Tage)</span></div>
  <div class="zahl"><b><?= n($pagesPerVisit, 1) ?></b><span>Seiten je Besuch</span></div>
  <div class="zahl"><b><?= e(duration_text(median($durations))) ?></b><span>Besuchsdauer, Median aus <?= n(count($durations)) ?> Besuchen mit mehr als einem Schritt</span></div>
</div>

<div class="kacheln">

<article class="kachel breit">
<h3>Tag für Tag</h3>
<?php $dayPeak = max(1, max(array_map(static fn (array $d): int => $d['p'] + $d['d'], $days))); ?>
<table>
  <tr><th>Tag</th><th class="n">Aufrufe</th><th class="n">Besuche</th><th class="n">Downloads</th><th class="n">Update-Prüfungen</th><th style="width:34%"></th></tr>
  <?php foreach (array_reverse($days, true) as $day => $counts): ?>
    <tr>
      <td><?= e($day) ?></td>
      <td class="n"><?= n($counts['p']) ?></td>
      <td class="n"><?= n($counts['visits']) ?></td>
      <td class="n"><?= n($counts['d']) ?></td>
      <td class="n"><?= n($counts['u']) ?></td>
      <td><?= bar($counts['p'] + $counts['d'], $dayPeak) ?></td>
    </tr>
  <?php endforeach; ?>
</table>
</article>

<?php if ($monthRows): ?>
<article class="kachel breit">
<h3>Monate im Vergleich</h3>
<?php $monthPeak = max(1, max(array_column($monthRows, 'pages'))); ?>
<table>
  <tr><th>Monat</th><th class="n">Aufrufe</th><th class="n">Besuche</th><th class="n">Downloads</th><th class="n">Updates</th><th style="width:25%"></th></tr>
  <?php foreach ($monthRows as $totals): ?>
    <tr>
      <td><?php if ($totals['month'] === $month): ?><b><?= e($totals['month']) ?></b><?php else: ?><a href="?m=<?= e($totals['month']) ?>"><?= e($totals['month']) ?></a><?php endif; ?><?php if (empty($totals['complete'])): ?> <abbr title="Unvollständig: Die Monatsdatei überschreitet die sichere Grenze, die Zahlen sind Untergrenzen.">≥</abbr><?php endif; ?></td>
      <td class="n"><?= n($totals['pages']) ?></td>
      <td class="n"><?= n($totals['visitors']) ?></td>
      <td class="n"><?= n($totals['downloads']) ?></td>
      <td class="n"><?= n($totals['updates']) ?></td>
      <td><?= bar($totals['pages'], $monthPeak) ?></td>
    </tr>
  <?php endforeach; ?>
</table>
</article>
<?php endif; ?>

<article class="kachel breit">
<h3>Woher</h3>
<p class="sub">Je Besuch die verweisende Seite des ersten Aufrufs — und wie
viele dieser Besuche etwas geladen haben. Suchmaschinen schicken ihre Herkunft
oft nicht mehr mit; die stehen in der ersten Zeile.</p>
<table>
  <tr><th>Verweisende Seite</th><th class="n">Besuche</th><th class="n">Aufrufe</th><th class="n">mit Download</th><th class="n">Downloads</th></tr>
  <tr>
    <td class="leer">direkt oder ohne Herkunft</td>
    <td class="n"><?= n($direct['visits']) ?></td>
    <td class="n"><?= n($direct['pages']) ?></td>
    <td class="n"><?= n($direct['downloaded']) ?></td>
    <td class="n"><?= n($direct['downloads']) ?></td>
  </tr>
  <?php foreach (array_slice($sources, 0, TOP, true) as $host => $counts): ?>
    <tr>
      <td><?= e($host) ?></td>
      <td class="n"><?= n($counts['visits']) ?></td>
      <td class="n"><?= n($counts['pages']) ?></td>
      <td class="n"><?= n($counts['downloaded']) ?></td>
      <td class="n"><?= n($counts['downloads']) ?></td>
    </tr>
  <?php endforeach; ?>
</table>
</article>

<?php if ($languages || $withoutPage): ?>
<article class="kachel breit">
<h3>Nach Sprache</h3>
<p class="sub">Die Sprachfassung der ersten Seite eines Besuchs. Direktdownloads
ohne Seite haben keine Sprache und stehen in der letzten Zeile.</p>
<table>
  <tr><th>Sprache</th><th class="n">Besuche</th><th class="n">Aufrufe</th><th class="n">mit Download</th><th class="n">Downloads</th></tr>
  <?php foreach ($languages as $code => $counts): ?>
    <tr>
      <td><?= e($languageNames[$code] ?? $code) ?></td>
      <td class="n"><?= n($counts['visits']) ?></td>
      <td class="n"><?= n($counts['pages']) ?></td>
      <td class="n"><?= n($counts['downloaded']) ?></td>
      <td class="n"><?= n($counts['downloads']) ?></td>
    </tr>
  <?php endforeach; ?>
  <?php if ($withoutPage): ?>
    <tr>
      <td class="leer">ohne Seitenaufruf</td>
      <td class="n"><?= n($withoutPage['visits']) ?></td>
      <td class="n">—</td>
      <td class="n"><?= n($withoutPage['downloaded']) ?></td>
      <td class="n"><?= n($withoutPage['downloads']) ?></td>
    </tr>
  <?php endif; ?>
</table>
</article>
<?php endif; ?>

<article class="kachel">
<h3>Seiten</h3>
<?php if (!$paths): ?>
  <p class="leer">Noch keine.</p>
<?php else: ?>
<?php $pathPeak = max(1, max($paths)); ?>
<table>
  <tr><th>Pfad</th><th class="n">Aufrufe</th><th class="n">Anteil</th><th style="width:30%"></th></tr>
  <?php foreach (array_slice($paths, 0, TOP, true) as $path => $count): ?>
    <tr>
      <td><?= e($path) ?></td>
      <td class="n"><?= n($count) ?></td>
      <td class="n"><?= n($count / max(1, $monthSum['p']) * 100, 1) ?> %</td>
      <td><?= bar($count, $pathPeak) ?></td>
    </tr>
  <?php endforeach; ?>
</table>
<?php endif; ?>
</article>

<?php if ($unread): ?>
<article class="kachel">
<h3>Ungelesene Seiten</h3>
<p class="sub"><?= n(count($unread)) ?> der <?= n(count(sitemap_paths())) ?> Seiten
aus der Sitemap ohne einen einzigen Aufruf in diesem Monat.</p>
<ul class="pfade">
  <?php foreach ($unread as $path): ?>
    <li><?= e($path) ?></li>
  <?php endforeach; ?>
</ul>
</article>
<?php endif; ?>

<?php if ($entryPages): ?>
<article class="kachel">
<h3>Einstiegsseiten</h3>
<p class="sub">Die erste Seite jedes Besuchs — wo Leser ankommen.</p>
<table>
  <tr><th>Pfad</th><th class="n">Besuche</th></tr>
  <?php foreach (array_slice($entryPages, 0, TOP, true) as $path => $count): ?>
    <tr><td><?= e($path) ?></td><td class="n"><?= n($count) ?></td></tr>
  <?php endforeach; ?>
</table>
</article>

<article class="kachel">
<h3>Ausstiegsseiten</h3>
<p class="sub">Die letzte Seite jedes Besuchs — wo Leser aufhören.</p>
<table>
  <tr><th>Pfad</th><th class="n">Besuche</th></tr>
  <?php foreach (array_slice($exitPages, 0, TOP, true) as $path => $count): ?>
    <tr><td><?= e($path) ?></td><td class="n"><?= n($count) ?></td></tr>
  <?php endforeach; ?>
</table>
</article>

<article class="kachel">
<h3>Besuchstiefe</h3>
<p class="sub">Wie viele Seiten ein Besuch umfasst.</p>
<?php $depthPeak = max(1, max($depth)); ?>
<table>
  <tr><th>Seiten je Besuch</th><th class="n">Besuche</th><th style="width:40%"></th></tr>
  <?php foreach ($depth as $label => $count): ?>
    <tr><td><?= e($label) ?></td><td class="n"><?= n($count) ?></td><td><?= bar($count, $depthPeak) ?></td></tr>
  <?php endforeach; ?>
</table>
</article>

<article class="kachel">
<h3>Besuchsdauer</h3>
<p class="sub">Vom ersten zum letzten Schritt, nur bei Besuchen mit mehr als einem.</p>
<?php $durationPeak = max(1, max($duration)); ?>
<table>
  <tr><th>Dauer</th><th class="n">Besuche</th><th style="width:40%"></th></tr>
  <?php foreach ($duration as $label => $count): ?>
    <tr><td><?= e($label) ?></td><td class="n"><?= n($count) ?></td><td><?= bar($count, $durationPeak) ?></td></tr>
  <?php endforeach; ?>
</table>
</article>
<?php endif; ?>

<article class="kachel">
<h3>Nach Uhrzeit</h3>
<p class="sub">Seitenaufrufe je Stunde, über den Monat aufsummiert.</p>
<?php $hourPeak = max(1, max($byHour)); ?>
<table>
  <tr><th>Stunde</th><th class="n">Aufrufe</th><th style="width:45%"></th></tr>
  <?php foreach ($byHour as $hour => $count): ?>
    <?php if ($count === 0) { continue; } ?>
    <tr><td><?= $hour ?>–<?= $hour + 1 ?> Uhr</td><td class="n"><?= n($count) ?></td><td><?= bar($count, $hourPeak) ?></td></tr>
  <?php endforeach; ?>
</table>
</article>

<article class="kachel">
<h3>Nach Wochentag</h3>
<p class="sub">Seitenaufrufe je Wochentag.</p>
<?php $weekdayPeak = max(1, max($byWeekday)); ?>
<table>
  <tr><th>Tag</th><th class="n">Aufrufe</th><th style="width:45%"></th></tr>
  <?php foreach ($byWeekday as $weekday => $count): ?>
    <tr><td><?= e($weekdayNames[$weekday]) ?></td><td class="n"><?= n($count) ?></td><td><?= bar($count, $weekdayPeak) ?></td></tr>
  <?php endforeach; ?>
</table>
</article>

</div>

<h2 id="konversion">Konversion <span class="sub">ob aus Besuchen Downloads werden — ein Besuch zählt einmal,
auch wenn er dreimal auf den Knopf drückt</span></h2>

<div class="zahlen">
  <div class="zahl"><b><?= n($monthSum['d']) ?></b><span>Downloads</span></div>
  <div class="zahl"><b><?= n($visitsWithDownload) ?></b><span>Besuche mit Download</span></div>
  <div class="zahl"><b><?= $conversion === null ? '—' : n($conversion, 1) . ' %' ?></b><span>der Besuche laden</span></div>
  <div class="zahl"><b><?= n($downloadsWithoutPage) ?></b><span>Downloads ohne Seitenaufruf am selben Tag (Direktlinks, Skripte)</span></div>
</div>

<div class="kacheln">

<?php if ($matrixRows): ?>
<article class="kachel breit">
<h3>Version und Zielsystem</h3>
<table>
  <tr><th>Version</th><?php foreach ($platforms as $platform): ?><th class="n"><?= e($platform) ?></th><?php endforeach; ?><th class="n">Summe</th></tr>
  <?php foreach ($matrixRows as $line): ?>
    <tr>
      <td><?= e($line['version']) ?></td>
      <?php foreach ($platforms as $platform): ?><td class="n"><?= n($line['cells'][$platform]) ?></td><?php endforeach; ?>
      <td class="n"><?= n($line['total']) ?></td>
    </tr>
  <?php endforeach; ?>
  <tr class="summe">
    <td>Summe</td>
    <?php foreach ($platforms as $platform): ?><td class="n"><?= n($platformTotals[$platform]) ?></td><?php endforeach; ?>
    <td class="n"><?= n($monthSum['d']) ?></td>
  </tr>
</table>
</article>
<?php endif; ?>

<?php if ($beforeDownload): ?>
<article class="kachel">
<h3>Seite vor dem Download</h3>
<p class="sub">Die zuletzt geöffnete Seite, als der Download begann — welcher
Knopf benutzt wird.</p>
<table>
  <tr><th>Pfad</th><th class="n">Downloads</th></tr>
  <?php foreach (array_slice($beforeDownload, 0, TOP, true) as $path => $count): ?>
    <tr><td><?php if ((string) $path === ''): ?><span class="leer">ohne Seitenaufruf</span><?php else: ?><?= e($path) ?><?php endif; ?></td><td class="n"><?= n($count) ?></td></tr>
  <?php endforeach; ?>
</table>
</article>
<?php endif; ?>

<article class="kachel breit">
<h3>Dateien</h3>
<?php if (!$files): ?>
  <p class="leer">Der Ordner ist leer, und geladen wurde auch nichts.</p>
<?php else: ?>
<table>
  <tr><th>Datei</th><th class="n">Größe</th><th class="n">Downloads</th></tr>
  <?php foreach ($files as $file): ?>
    <tr>
      <td>
        <?php if ($file['bytes'] !== null): ?>
          <?php /* Der Link zeigt auf die Datei, nicht auf `count.php?f=`:
                   Wer hier klickt, prüft die eigene Seite — und das darf die
                   Zahl daneben nicht bewegen. */ ?>
          <a href="/dl/<?= e(rawurlencode($file['name'])) ?>"><?= e($file['name']) ?></a>
        <?php else: ?>
          <?= e($file['name']) ?> <span class="leer">nicht mehr im Ordner</span>
        <?php endif; ?>
      </td>
      <td class="n"><?= $file['bytes'] !== null ? e(megabytes($file['bytes'])) : '—' ?></td>
      <td class="n"><?= n($file['count']) ?></td>
    </tr>
  <?php endforeach; ?>
</table>
<?php endif; ?>
</article>

</div>

<h2 id="nutzung">Nutzung <span class="sub">Update-Prüfungen — die Anwendung nennt bei jedem Start ihre Version, wenn
die Prüfung eingeschaltet ist</span></h2>
<p class="hinweis">Gezählt werden Abrufe, auch wiederholte: Drei Prüfungen
derselben Anwendung stehen dreimal in der Zahl. Es werden keine
Besucherkennzeichen für diese Auswertung gebildet; wie viele Rechner oder
Personen dahinterstehen, lässt sich daraus nicht bestimmen. Die Kurve folgt
dem Rhythmus der Nutzung, nicht ihrer Größe.</p>

<?php if (!$versions): ?>
  <p class="leer">Noch keine Update-Prüfung gezählt. Entweder läuft die
  Umschreibung in <code>.htaccess</code> nicht, oder es hat seit dem Einbau
  niemand die Anwendung gestartet.</p>
<?php else: ?>
<div class="zahlen">
  <div class="zahl"><b><?= n($updateCount) ?></b><span>Update-Prüfungen</span></div>
  <div class="zahl"><b><?= n($updatesPerDay, 1) ?></b><span>je Kalendertag</span></div>
  <div class="zahl"><b><?= $releaseShare === null ? '—' : n($releaseShare, 1) . ' %' ?></b><span>aus der aktuellen Version<?= $release !== '' ? ' ' . e($release) : '' ?></span></div>
  <div class="zahl"><b><?= n(count($versions)) ?></b><span>Versionen gesehen</span></div>
</div>

<div class="kacheln">

<article class="kachel">
<h3 id="versionen">Versionen</h3>
<?php $updatePeak = max(1, max($versions)); ?>
<table>
  <tr><th>Version</th><th class="n">Prüfungen</th><th class="n">Anteil</th><th style="width:40%"></th></tr>
  <?php foreach ($versions as $name => $count): ?>
  <tr>
    <td><?= e((string) $name) ?></td>
    <td class="n"><?= n($count) ?></td>
    <td class="n"><?= n($count / max(1, $updateCount) * 100, 1) ?> %</td>
    <td><?= bar($count, $updatePeak) ?></td>
  </tr>
  <?php endforeach; ?>
</table>
</article>

<?php if (count($versionDayRows) > 1 && count($versions) > 1): ?>
<article class="kachel breit">
<h3>Versionen Tag für Tag</h3>
<p class="sub">Wie schnell eine neue Version die alte ablöst.<?php if (count($versions) > count($versionColumns)): ?>
Die <?= count($versionColumns) ?> meistgesehenen einzeln, der Rest als „andere“.<?php endif; ?></p>
<table>
  <tr><th>Tag</th><?php foreach ($versionColumns as $column): ?><th class="n"><?= e($column) ?></th><?php endforeach; ?><?php if (count($versions) > count($versionColumns)): ?><th class="n">andere</th><?php endif; ?><th class="n">Summe</th></tr>
  <?php foreach (array_reverse($versionDayRows) as $line): ?>
    <tr>
      <td><?= e($line['day']) ?></td>
      <?php foreach ($versionColumns as $column): ?><td class="n"><?= n($line['cells'][$column]) ?></td><?php endforeach; ?>
      <?php if (count($versions) > count($versionColumns)): ?><td class="n"><?= n($line['other']) ?></td><?php endif; ?>
      <td class="n"><?= n($line['total']) ?></td>
    </tr>
  <?php endforeach; ?>
</table>
</article>
<?php endif; ?>

</div>
<?php endif; ?>

<?php endif; ?>

<h2 id="methode">Zur Methode</h2>
<p class="hinweis">Die Besucher kommen ohne Cookie und ohne gespeicherte
IP-Adresse zustande: Ein Tageskennzeichen aus IP-Adresse und Browserkennung
unter einem Tageswert, der um Mitternacht wechselt. Besuche, Einstieg,
Ausstieg, Dauer und Konversion gelten deshalb je Tag und sind über den Tag
hinaus nicht zusammenführbar — die Monatssumme der Besuche ist eine Summe
von Tageswerten. Wer <em>Do Not Track</em> oder <em>Global Privacy Control</em>
sendet, wird nicht gezählt, auch nicht bei Downloads. Update-Prüfungen tragen
kein Kennzeichen. Es bleiben der laufende und der vorige Monat; darum kann der
Vergleich der letzten 30 Tage mit den 30 davor fehlen. (Ein Cookie gibt es
hier doch: dieses Fenster. Es merkt sich die Anmeldung, gilt nur unterhalb von
<code>/api/</code> und geht keinen Besucher etwas an.)</p>

</body>
</html>
