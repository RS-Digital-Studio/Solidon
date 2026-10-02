<?php
/**
 * Zeigt, was website/api/count.php gezählt hat — vorneweg als Sätze, danach
 * in vier Blöcken, die dem Weg eines Kunden folgen:
 *
 *   Auf einen Blick  Befunde aus den Zahlen darunter: Warnungen (Zähler
 *                    schweigt, Paket fehlt), Trends, Konversion, Herkunft,
 *                    Sprache, Systeme, Versionen, Seiten
 *   Jetzt        rollend bis heute, 7 und 30 Tage, mit der Veränderung zum
 *                gleich langen Zeitraum davor — unabhängig vom Monat
 *   Reichweite   Aufrufe, Besuche, Herkunft, Sprache, Seiten mit Einstieg,
 *                Ausstieg und Ausstiegsquote, Tiefe und Dauer, Uhrzeit und
 *                Wochentag
 *   Konversion   Downloads je Besuch, Version mal Zielsystem, die Seite vor
 *                dem Download, die Dateien im Ordner
 *   Versionen    Update-Prüfungen aller gespeicherten Tage: jede Version je
 *                Tag, je Version ihr Verlauf — wie schnell eine neue
 *                Version die alte ablöst
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
    $releases = release_dates();
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
            // Prüfungen vor einer belegten Veröffentlichung stammen aus
            // Vorabfassungen. Die Rohdaten bleiben erhalten; alle Ansichten
            // rechnen auf derselben bereinigten Menge.
            $published = $releases[(string) ($row['v'] ?? '')] ?? null;
            if (($row['k'] ?? '') === 'u' && $published !== null
                && $when->format('Y-m-d') < $published) {
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

/** Belegte Veröffentlichungstage, unabhängig von Build und erster Prüfung.
 *  Fehlende oder ungültige Angaben werden nicht aus Zähldaten erraten. */
function release_dates(): array
{
    static $dates = null;
    if ($dates !== null) {
        return $dates;
    }
    $dates = [];
    $raw = @file_get_contents(__DIR__ . '/../release-dates.json');
    $data = is_string($raw) ? json_decode($raw, true) : null;
    foreach (is_array($data) ? $data : [] as $version => $day) {
        if (preg_match('/^[0-9]+(?:\.[0-9]+){0,3}$/D', (string) $version) !== 1
            || !is_string($day) || preg_match('/^\d{4}-\d{2}-\d{2}$/D', $day) !== 1) {
            continue;
        }
        $date = DateTimeImmutable::createFromFormat('!Y-m-d', $day);
        if ($date instanceof DateTimeImmutable && $date->format('Y-m-d') === $day) {
            $dates[(string) $version] = $day;
        }
    }
    return $dates;
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

// --- Formate und Kalender --------------------------------------------------
//
// Stehen vor der Auswertung, weil die Befunde fertige Sätze sind und dieselben
// Zahlen- und Datumsformate brauchen wie die Tabellen darunter.

/** Eine Zahl mit Tausenderpunkt und Dezimalkomma. */
function n(int|float|null $value, int $decimals = 0): string
{
    return $value === null ? '—' : number_format((float) $value, $decimals, ',', '.');
}

/** Eine Anzahl mit dem passenden Wort: „1 Besuch", „3 Besuche". */
function plural(int $count, string $one, string $many): string
{
    return n($count) . ' ' . ($count === 1 ? $one : $many);
}

/** Ein Anteil in Prozent auf eine Stelle — oder null, wenn die Grundmenge fehlt. */
function percent(int|float $part, int|float $whole): ?float
{
    return $whole > 0 ? round($part / $whole * 100, 1) : null;
}

/** Ein Tag als „15.09." für Beschriftungen. */
function short_day(string $day): string
{
    return substr($day, 8, 2) . '.' . substr($day, 5, 2) . '.';
}

/** Ein Tag mit Wochentag: „Sa 12.09." — für Befunde und Tooltips. */
function day_label(string $day): string
{
    $date = DateTimeImmutable::createFromFormat('!Y-m-d', $day, new DateTimeZone('UTC'));
    if (!$date instanceof DateTimeImmutable) {
        return short_day($day);
    }
    return ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'][(int) $date->format('N') - 1] . ' ' . short_day($day);
}

/**
 * Ein Tag um so viele Tage verschoben.
 *
 * Gerechnet wird in UTC und nur mit Kalenderdaten: Die Tage selbst sind schon
 * in der Anzeigezone gebildet, und eine Zeitzone mit Sommerzeit verschöbe um
 * Mitternacht eine Stunde, die hier keiner meint.
 */
function shift_day(string $day, int $days): string
{
    $date = DateTimeImmutable::createFromFormat('!Y-m-d', $day, new DateTimeZone('UTC'));
    return $date instanceof DateTimeImmutable
        ? $date->modify(sprintf('%+d days', $days))->format('Y-m-d')
        : $day;
}

/** Wie viele Tage von einem Tag zum anderen vergehen. */
function days_between(string $from, string $to): int
{
    $zone = new DateTimeZone('UTC');
    $start = DateTimeImmutable::createFromFormat('!Y-m-d', $from, $zone);
    $end = DateTimeImmutable::createFromFormat('!Y-m-d', $to, $zone);
    if (!$start instanceof DateTimeImmutable || !$end instanceof DateTimeImmutable) {
        return 0;
    }
    return intdiv($end->getTimestamp() - $start->getTimestamp(), 86400);
}

/**
 * Alle Kalendertage zwischen zwei Tagen, beide einschließlich.
 *
 * Die Zählzeilen kennen nur Tage, an denen etwas geschah; ein stiller Tag
 * fehlte sonst in jedem Diagramm, und die Säulen daneben rückten zusammen.
 * Höchstens 400 Tage — die Löschfrist lässt 62 übrig, und eine verirrte
 * Zeile aus einem fernen Jahr soll keine Schleife über Jahrzehnte auslösen.
 */
function calendar_days(string $from, string $to): array
{
    $day = DateTimeImmutable::createFromFormat('!Y-m-d', $from, new DateTimeZone('UTC'));
    if (!$day instanceof DateTimeImmutable || $from > $to) {
        return [];
    }
    $days = [];
    while (count($days) < 400) {
        $label = $day->format('Y-m-d');
        if ($label > $to) {
            break;
        }
        $days[] = $label;
        $day = $day->modify('+1 day');
    }
    return $days;
}

/**
 * Die Update-Prüfungen aller gespeicherten Tage — je Tag jede Version, je
 * Version ihr Verlauf.
 *
 * **Über alle Monatsdateien, nicht über den gewählten Monat.** Wie schnell
 * eine neue Version die alte ablöst, ist eine Zeitreihe; eine Veröffentlichung
 * am 28. hätte ihre erste Woche sonst auf zwei Seiten. Nach der Löschfrist
 * sind es höchstens 62 Tage.
 *
 * **Jede Version bekommt ihre Spalte.** Bis zum 24.09.2026 standen die fünf
 * meistgesehenen einzeln und der Rest als „andere" — und gerade eine frisch
 * veröffentlichte Version mit wenigen Prüfungen verschwand darin.
 *
 * Veröffentlichung und erste Prüfung sind getrennte Angaben. Mehrheit und
 * erste Woche beginnen am belegten Veröffentlichungstag; fehlt er oder
 * reicht er vor den Datenbeginn, bleiben diese Kennzahlen leer.
 */
function version_timeline(array $rows, string $today, string $release, array $releases): array
{
    $first = null;
    $last = $today;
    $counts = [];
    $totals = [];
    foreach ($rows as $row) {
        if ($first === null || $row['day'] < $first) {
            $first = $row['day'];
        }
        if ($row['kind'] !== 'u' || $row['value'] === '') {
            continue;
        }
        $counts[$row['day']][$row['value']] = ($counts[$row['day']][$row['value']] ?? 0) + 1;
        $totals[$row['value']] = ($totals[$row['value']] ?? 0) + 1;
        $last = max($last, $row['day']);
    }
    $weekFrom = shift_day($today, -6);
    $timeline = [
        'from' => $first,
        'to' => $last,
        'week_from' => $weekFrom,
        'total' => array_sum($totals),
        'week_total' => 0,
        'columns' => [],
        'days' => [],
        'versions' => [],
    ];
    if ($first === null || $totals === []) {
        return $timeline;
    }

    // Kennzahlen je Version erst, wenn die Tage stehen — alles daran ist ein
    // Blick auf dieselbe Tabelle.
    $columns = array_map('strval', array_keys($totals));
    usort($columns, static fn (string $a, string $b): int => newest_first($a, $b));
    $seen = [];
    foreach (calendar_days($first, $last) as $day) {
        $cells = [];
        foreach ($columns as $column) {
            $cells[$column] = (int) ($counts[$day][$column] ?? 0);
        }
        $dayTotal = array_sum($cells);
        $new = [];
        foreach ($cells as $column => $count) {
            if ($count > 0 && !isset($seen[(string) $column])) {
                $seen[(string) $column] = $day;
            }
            if (($releases[(string) $column] ?? null) === $day) {
                $new[] = (string) $column;
            }
        }
        $timeline['days'][] = [
            'day' => $day,
            'cells' => $cells,
            'total' => $dayTotal,
            'new' => $new,
            'release_share_percent' => $release !== '' && isset($cells[$release])
                ? percent($cells[$release], $dayTotal)
                : null,
        ];
        if ($day >= $weekFrom && $day <= $today) {
            $timeline['week_total'] += $dayTotal;
        }
    }

    // Seiten wurden schon vor dem Updatezähler erfasst. Ihre älteren Zeilen
    // belegen keine Abdeckung für die erste Woche einer Version.
    $updateStart = min(array_keys($counts));
    foreach ($columns as $column) {
        $firstSeen = $seen[$column];
        $sinceStart = $firstSeen === $first;
        // „unbekannt" ist keine Version, die veröffentlicht wurde — sie hat
        // keinen ersten Tag, von dem aus eine Ablösung zu zählen wäre.
        $numbered = preg_match('/^\d+(\.\d+)*$/D', $column) === 1;
        $published = $releases[$column] ?? null;
        $fromRelease = $numbered && $published !== null && $published >= $updateStart;
        $lastSeen = $firstSeen;
        $activeDays = 0;
        $peakDay = $firstSeen;
        $peak = 0;
        $week = 0;
        $majority = null;
        $firstWeekEnd = $published === null ? null : shift_day($published, 6);
        $firstWeek = 0;
        $firstWeekAll = 0;
        foreach ($timeline['days'] as $line) {
            $count = $line['cells'][$column];
            if ($count > 0) {
                $activeDays++;
                $lastSeen = $line['day'];
                if ($count > $peak) {
                    [$peak, $peakDay] = [$count, $line['day']];
                }
            }
            if ($line['day'] >= $weekFrom && $line['day'] <= $today) {
                $week += $count;
            }
            if ($fromRelease && $majority === null && $line['day'] >= $published
                && $count * 2 > $line['total']) {
                $majority = $line['day'];
            }
            if ($fromRelease && $line['day'] >= $published && $line['day'] <= $firstWeekEnd) {
                $firstWeek += $count;
                $firstWeekAll += $line['total'];
            }
        }
        $timeline['versions'][] = [
            'version' => $column,
            'current' => $column === $release,
            'published_on' => $published,
            'release_covered' => $fromRelease,
            'first_seen' => $firstSeen,
            'numbered' => $numbered,
            'since_data_start' => $sinceStart,
            'last_seen' => $lastSeen,
            'active_days' => $activeDays,
            'checks' => (int) $totals[$column],
            'share_percent' => percent((int) $totals[$column], $timeline['total']),
            'last_7_days' => $week,
            'last_7_days_share_percent' => percent($week, $timeline['week_total']),
            'peak_day' => $peakDay,
            'peak' => $peak,
            'majority_from' => $majority,
            'days_to_majority' => $majority === null ? null : days_between($published, $majority),
            // Erst, wenn die sieben Tage vorbei sind — ein halber Zeitraum
            // sähe nach einer langsamen Ablösung aus.
            'first_week_share_percent' => $fromRelease && $firstWeekEnd <= $today
                ? percent($firstWeek, $firstWeekAll)
                : null,
        ];
    }
    $timeline['columns'] = $columns;
    return $timeline;
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

// -- Versionen: alle gespeicherten Tage -----------------------------------------

// Updateabrufe tragen keine Besucherkennung. Wiederholte Abrufe bleiben
// einzelne Prüfungen; eine Zahl von Rechnern lässt sich daraus nicht ableiten.
// Gelesen werden alle Monatsdateien statt des gewählten Monats — warum, steht
// bei `version_timeline()`.
$allRows = [];
$allComplete = true;
foreach ($available as $option) {
    $allRows = array_merge($allRows, month_rows($dir, $option, $done));
    $allComplete = $allComplete && $done;
}
$timeline = version_timeline($allRows, $today, $release, release_dates());
$versions = tally($allRows, 'value', 'u');
$updateCount = $timeline['total'];
$releaseShare = $release !== '' && isset($versions[$release])
    ? percent($versions[$release], $updateCount)
    : null;
// Ø je Tag über die Kalendertage des Zeitraums — nicht über die Tage mit
// Einträgen, sonst zählte ein stiller Sonntag nicht als Tag.
$updatesPerDay = $timeline['days'] !== [] ? round($updateCount / count($timeline['days']), 1) : null;
$releaseLife = null;
foreach ($timeline['versions'] as $life) {
    if ($life['current']) {
        $releaseLife = $life;
    }
}

// Die Tage des gewählten Monats lückenlos, für die Säulen: bis heute im
// laufenden Monat, sonst bis zum Monatsende.
$monthStart = DateTimeImmutable::createFromFormat('!Y-m-d', $month . '-01', $zone);
$monthDays = $monthStart instanceof DateTimeImmutable && $month <= $current
    ? calendar_days($monthStart->format('Y-m-d'), $month === $current ? $today : $monthStart->format('Y-m-t'))
    : [];

// -- Befunde: dieselben Zahlen als Sätze ------------------------------------------
//
// Jeder Befund ist eine Regel über Zahlen, die weiter unten ohnehin stehen —
// die Seite erfindet nichts dazu, sie liest sich nur selbst vor. Wo eine Zahl
// zu klein ist, um etwas zu sagen, schweigt der Befund, statt aus drei
// Besuchen einen Trend zu machen. Der Ton steht als Wort vor dem Satz und
// zusätzlich als Farbe am Rand, nie als Farbe allein.
$findings = [];
$say = static function (string $tone, string $text) use (&$findings): void {
    $findings[] = ['tone' => $tone, 'text' => $text];
};

// Ein Zähler, der nicht mehr schreibt, sieht von außen aus wie eine Seite
// ohne Besucher — zweimal geschehen (Rechte am 03.09.2026, open_basedir nach
// dem PHP-Wechsel am 02.09.2026). Achtundvierzig Stunden ohne eine einzige
// Zeile, auch ohne Update-Prüfung, sind bei laufender Software kein Zufall.
$lastStamp = 0;
foreach ($allRows as $row) {
    $lastStamp = max($lastStamp, $row['stamp']);
}
$silentHours = $lastStamp > 0 ? intdiv($now->getTimestamp() - $lastStamp, 3600) : null;
if ($silentHours !== null && $silentHours >= 48) {
    $lastSeen = (new DateTimeImmutable('@' . $lastStamp))->setTimezone($zone);
    $say('warnung', 'Seit ' . n($silentHours) . ' Stunden keine gezählte Zeile mehr (zuletzt '
        . day_label($lastSeen->format('Y-m-d')) . ' um ' . $lastSeen->format('H:i')
        . ' Uhr). Waren Besucher da, kommt count.php nicht an seinen Ablageordner: PHP-Fehlerprotokoll, '
        . 'open_basedir und die Rechte der Monatsdatei prüfen.');
}

// Die angebotene Version muss im Download-Ordner liegen, und zwar für jedes
// Zielsystem. Fehlt ein Paket, zeigt der Download-Kasten ins Leere.
if ($release !== '') {
    $releasePlatforms = [];
    foreach (array_keys($present) as $name) {
        if (version_of((string) $name) === $release) {
            $releasePlatforms[platform_of((string) $name)] = true;
        }
    }
    if ($releasePlatforms === []) {
        $say('warnung', 'version.json bietet ' . $release
            . ' an, im Download-Ordner liegt aber kein Paket dieser Version.');
    } else {
        $missing = array_values(array_filter(
            $platformOrder,
            static fn (string $platform): bool => !isset($releasePlatforms[$platform])
        ));
        if ($missing !== []) {
            $say('warnung', 'Für ' . $release . ' fehlt im Download-Ordner ein Paket für '
                . implode(', ', $missing) . '.');
        }
    }
}

// Trends: nur mit vollständigem Vergleichszeitraum und genug Masse davor.
$week = $windows[0];
if ($week['before'] !== null) {
    foreach (['visits' => ['Besuche', 5], 'd' => ['Downloads', 3]] as $key => [$label, $floor]) {
        $was = (int) $week['before'][$key];
        $is = (int) $week['now'][$key];
        if ($was < $floor) {
            continue;
        }
        $delta = ($is - $was) / $was * 100;
        $tone = $delta >= 10 ? 'plus' : ($delta <= -10 ? 'minus' : 'info');
        $comparison = abs($delta) < 0.5
            ? 'genauso viele wie'
            : n(abs($delta)) . ' % ' . ($delta > 0 ? 'mehr' : 'weniger') . ' als';
        $say($tone, $label . ' der letzten 7 Tage: ' . n($is) . ' — ' . $comparison
            . ' in den 7 Tagen davor (' . n($was) . ').');
    }
}

if ($visitCount > 0) {
    $bestDay = null;
    foreach ($days as $day => $counts) {
        if ($bestDay === null || $counts['visits'] > $days[$bestDay]['visits']) {
            $bestDay = (string) $day;
        }
    }
    if ($bestDay !== null && count($days) > 1) {
        $say('info', 'Stärkster Tag im Monat: ' . day_label($bestDay) . ' mit '
            . plural($days[$bestDay]['visits'], 'Besuch', 'Besuchen') . ' und '
            . plural($days[$bestDay]['d'], 'Download', 'Downloads') . '.');
    }
    $say('info', n($conversion, 1) . ' % der Besuche im Monat haben etwas geladen ('
        . n($visitsWithDownload) . ' von ' . n($visitCount) . ').');
}

if ($sources !== [] && $visitCount > 0) {
    $topHost = (string) array_key_first($sources);
    $top = $sources[$topHost];
    $say('info', 'Wichtigste Herkunft: ' . $topHost . ' mit ' . plural($top['visits'], 'Besuch', 'Besuchen')
        . ' (' . n(percent($top['visits'], $visitCount), 1) . ' % aller Besuche), davon '
        . n($top['downloaded']) . ' mit Download.');
    // Die beste Konversion erst ab fünf Besuchen: Einer von einem ist 100 %.
    $bestHost = null;
    $bestRate = 0.0;
    foreach ($sources as $host => $counts) {
        $rate = $counts['downloaded'] / max(1, $counts['visits']);
        if ($counts['visits'] >= 5 && $rate > $bestRate) {
            [$bestHost, $bestRate] = [(string) $host, $rate];
        }
    }
    if ($bestHost !== null && $bestHost !== $topHost) {
        $best = $sources[$bestHost];
        $say('plus', 'Beste Konversion unter den Herkünften mit mindestens 5 Besuchen: ' . $bestHost . ' — '
            . n($best['downloaded']) . ' von ' . n($best['visits']) . ' Besuchen laden ('
            . n(percent($best['downloaded'], $best['visits']), 0) . ' %).');
    }
}

$languageVisits = array_sum(array_column($languages, 'visits'));
if ($languageVisits > 0) {
    $foreign = $languageVisits - (int) ($languages['de']['visits'] ?? 0);
    $leading = null;
    foreach ($languages as $code => $counts) {
        if ((string) $code !== 'de') {
            $leading = (string) $code;
            break;
        }
    }
    if ($foreign > 0 && $leading !== null) {
        $say('info', n(percent($foreign, $languageVisits), 0) . ' % der Besuche beginnen auf einer der '
            . 'anderen Sprachfassungen, am häufigsten ' . ($languageNames[$leading] ?? $leading) . ' ('
            . n(percent($languages[$leading]['visits'], $languageVisits), 0) . ' %).');
    } else {
        $say('info', 'Alle Besuche im Monat beginnen auf der deutschen Fassung.');
    }
}

if ($monthSum['d'] > 0) {
    $shares = array_filter($platformTotals, static fn (int $count): bool => $count > 0);
    arsort($shares);
    $parts = [];
    foreach ($shares as $platform => $count) {
        $parts[] = $platform . ' ' . n(percent($count, $monthSum['d']), 0) . ' %';
    }
    $say('info', 'Downloads im Monat nach System: ' . implode(', ', $parts) . '.');
    if ($monthSum['d'] >= 5 && $downloadsWithoutPage / $monthSum['d'] >= 0.2) {
        $say('info', n(percent($downloadsWithoutPage, $monthSum['d']), 0)
            . ' % der Downloads kamen ohne Seitenaufruf am selben Tag — Direktlinks oder Skripte.');
    }
}

if ($updateCount > 0 && $release !== '') {
    if ($releaseLife === null) {
        $say('info', 'Die aktuelle Version ' . $release . ' hat noch keine Update-Prüfung gemeldet.');
    } else {
        $text = $release . ($releaseLife['published_on'] !== null
            ? ' veröffentlicht am ' . day_label($releaseLife['published_on'])
            : ($releaseLife['since_data_start']
            ? ' meldet sich seit Beginn der Daten'
            : ' zuerst am ' . day_label($releaseLife['first_seen']) . ' geprüft (Veröffentlichung nicht belegt)'));
        $text .= $timeline['week_total'] > 0
            ? '; in den letzten 7 Tagen ' . n($releaseLife['last_7_days_share_percent'], 0)
                . ' % der Update-Prüfungen'
            : '; in den letzten 7 Tagen keine Update-Prüfung';
        if ($releaseLife['release_covered']) {
            $daysTo = $releaseLife['days_to_majority'];
            $text .= $releaseLife['majority_from'] === null
                ? ', die Mehrheit an einem Tag hatte sie noch nicht'
                : ', die Mehrheit seit ' . day_label($releaseLife['majority_from'])
                    . ($daysTo === 0 ? ' (am selben Tag)' : ' (nach ' . plural((int) $daysTo, 'Tag', 'Tagen') . ')');
        }
        $say(($releaseLife['last_7_days_share_percent'] ?? 0) >= 50 ? 'plus' : 'info', $text . '.');
    }
    // Die älteste Version, die sich noch meldet: Bis dahin reicht, was ein
    // Supportfall voraussetzen kann.
    $oldest = null;
    foreach ($timeline['versions'] as $life) {
        if ($life['last_7_days'] > 0 && preg_match('/^\d+(\.\d+)*$/D', $life['version']) === 1) {
            $oldest = $life;
        }
    }
    if ($oldest !== null && $oldest['version'] !== $release) {
        $say('info', 'Älteste Version, die sich in den letzten 7 Tagen noch meldet: ' . $oldest['version']
            . ' (' . plural($oldest['last_7_days'], 'Prüfung', 'Prüfungen') . ').');
    }
}

$sitemap = sitemap_paths();
if ($unread !== [] && $rows !== []) {
    $say('info', n(count($unread)) . ' von ' . n(count($sitemap))
        . ' Seiten aus der Sitemap hatten im Monat keinen Aufruf.');
}

// Die Ausstiegsquote erst ab zehn Aufrufen je Seite, aus demselben Grund wie
// die Konversion oben.
$exitRates = [];
foreach ($exitPages as $path => $exits) {
    $views = (int) ($paths[$path] ?? 0);
    if ($views >= 10) {
        $exitRates[(string) $path] = $exits / $views;
    }
}
arsort($exitRates);
$worstExit = array_key_first($exitRates);
if ($worstExit !== null && $exitRates[$worstExit] >= 0.5) {
    $say('info', 'Höchste Ausstiegsquote: ' . $worstExit . ' — ' . n($exitRates[$worstExit] * 100, 0)
        . ' % der Aufrufe beenden dort den Besuch (' . n($exitPages[$worstExit]) . ' von '
        . n($paths[$worstExit]) . ').');
}

// Warnungen zuerst, sonst bleibt die Reihenfolge der Regeln.
$toneOrder = ['warnung' => 0, 'minus' => 1, 'plus' => 2, 'info' => 3];
$order = array_keys($findings);
usort($order, static fn (int $a, int $b): int => [$toneOrder[$findings[$a]['tone']], $a]
    <=> [$toneOrder[$findings[$b]['tone']], $b]);
$findings = array_map(static fn (int $index): array => $findings[$index], $order);

// -- Der Bericht: eine Struktur, zwei Ausgaben --------------------------------

$report = [
    'month' => $month,
    'zone' => DISPLAY_ZONE,
    'today' => $today,
    'complete' => $month_complete,
    'months_available' => $available,
    'findings' => $findings,
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
        'from' => $timeline['from'],
        'to' => $timeline['to'],
        'complete' => $allComplete,
        'updates' => $updateCount,
        'updates_per_day' => $updatesPerDay,
        'release' => $release,
        'release_share_percent' => $releaseShare,
        'release_share_last_7_days_percent' => $releaseLife['last_7_days_share_percent'] ?? null,
        'versions' => listed($versions),
        'version_columns' => $timeline['columns'],
        'versions_per_day' => $timeline['days'],
        'lifecycle' => $timeline['versions'],
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

/**
 * Die Achsenbeschriftung eines Tages: der Monatstag, am Ersten mit Monat.
 * Auf schmalen Schirmen bleiben nur der Erste und jeder fünfte Tag stehen
 * (`neben`) — mehr passt unter sechzig Säulen nicht, ohne zu überlappen.
 */
function day_axis(string $day): array
{
    $date = (int) substr($day, 8, 2);
    $calendar = DateTimeImmutable::createFromFormat('!Y-m-d', $day, new DateTimeZone('UTC'));
    $monthLength = $calendar instanceof DateTimeImmutable ? (int) $calendar->format('t') : 31;
    return [
        'label' => $date === 1 ? $date . '.' . (int) substr($day, 5, 2) . '.' : (string) $date,
        // Die letzten zwei Tage eines Monats stehen direkt vor dem nächsten
        // Ersten und würden mit ihm zusammenlaufen („301.9.").
        'minor' => $date !== 1 && ($date % 5 !== 0 || $date > $monthLength - 2),
    ];
}

/**
 * Die Klasse eines Säulendiagramms. Ab 36 Säulen stehen nur noch die
 * Hauptmarken (der Erste und jeder fünfte Tag) — sonst laufen die Zahlen bei
 * zwei Monaten schon auf einem breiten Schirm ineinander. Darunter entscheidet
 * die Breite des Diagramms selbst (Container-Abfrage im Stil oben).
 */
function chart_class(string $base, int $count): string
{
    return $base . ($count > 35 ? ' dicht' : '');
}

/**
 * Säulen für eine Reihe — ein Tag, eine Stunde oder ein Wochentag je Säule.
 *
 * **HTML und CSS, kein SVG und kein Skript.** Die Seite lädt keine Skripte
 * (die Inhaltsrichtlinie oben verbietet sie), und ein SVG, das mit der Breite
 * gestreckt wird, verzerrt seine Schrift. Den genauen Wert trägt `title` als
 * Tooltip, die Höchstmarke steht darüber, und jede Zahl steht zusätzlich in
 * der Tabelle daneben — das Diagramm zeigt die Form, nicht die Ziffern.
 *
 * @param list<array{label: string, title: string, value: int, minor?: bool}> $points
 */
function columns(array $points, string $label): string
{
    $peak = max(1, ...array_map(static fn (array $point): int => $point['value'], $points ?: [['value' => 0]]));
    $html = '<div class="' . chart_class('saeulen', count($points)) . '" role="img" aria-label="'
        . e($label . ', höchstens ' . n($peak)) . '">'
        . '<span class="gipfel">' . n($peak) . '</span><div class="reihe">';
    foreach ($points as $point) {
        $height = $point['value'] > 0 ? max(2.0, round($point['value'] / $peak * 100, 1)) : 0.0;
        $html .= '<div class="spalte" title="' . e($point['title']) . '"><div class="flaeche">'
            . ($height > 0 ? '<span class="saeule" style="height:' . $height . '%"></span>' : '')
            . '</div><small' . (!empty($point['minor']) ? ' class="neben"' : '') . '>' . e($point['label'])
            . '</small></div>';
    }
    return $html . '</div></div>';
}

/**
 * Die Anteile der Versionen je Tag als gestapelte Säule, alle gleich hoch.
 *
 * Die neueste Version liegt unten an der Grundlinie, damit ihr Wachsen von
 * dort aus zu lesen ist. Die Farben folgen der Reihenfolge der Legende und
 * stehen nie allein: Legende, Tooltip und die Tabelle darunter nennen jede
 * Version beim Namen. Ab der achten fasst ein grauer Abschnitt „weitere"
 * zusammen — die Tabelle führt auch diese einzeln.
 *
 * @param list<array{name: string, slot: string, versions: list<string>}> $series
 */
function share_chart(array $days, array $series): string
{
    $html = '<div class="' . chart_class('saeulen anteile', count($days)) . '" role="img" aria-label="Anteile der Versionen an den '
        . 'Update-Prüfungen je Tag"><div class="reihe">';
    foreach ($days as $line) {
        $axis = day_axis($line['day']);
        $html .= '<div class="spalte"><div class="flaeche">';
        if ($line['total'] === 0) {
            $html .= '<span class="ohne" title="' . e(day_label($line['day']) . ': keine Prüfung') . '"></span>';
        }
        foreach ($series as $item) {
            $count = 0;
            foreach ($item['versions'] as $version) {
                $count += (int) ($line['cells'][$version] ?? 0);
            }
            if ($count === 0) {
                continue;
            }
            $html .= '<span class="seg ' . $item['slot'] . '" style="flex-grow:' . $count . '" title="'
                . e(day_label($line['day']) . ': ' . $item['name'] . ' ' . n($count) . ' von '
                    . n($line['total']) . ' (' . n(percent($count, $line['total']), 0) . ' %)')
                . '"></span>';
        }
        $html .= '</div><small' . ($axis['minor'] ? ' class="neben"' : '') . '>' . e($axis['label'])
            . '</small></div>';
    }
    return $html . '</div></div>';
}

// Farben je Version: die ersten sieben in der festen Reihenfolge der Palette,
// die neueste zuerst, alles danach grau unter „weitere".
$versionSeries = [];
foreach (array_slice($timeline['columns'], 0, 7) as $index => $version) {
    $versionSeries[] = ['name' => $version, 'slot' => 'v' . ($index + 1), 'versions' => [$version]];
}
if (count($timeline['columns']) > 7) {
    $versionSeries[] = ['name' => 'weitere', 'slot' => 'vx', 'versions' => array_slice($timeline['columns'], 7)];
}
$slotOf = [];
foreach ($versionSeries as $item) {
    foreach ($item['versions'] as $version) {
        $slotOf[$version] = $item['slot'];
    }
}

$toneLabels = ['warnung' => 'Achtung', 'plus' => 'Gut', 'minus' => 'Rückgang', 'info' => ''];
$metrics = ['visits' => 'Besuche', 'p' => 'Seitenaufrufe', 'd' => 'Downloads', 'u' => 'Update-Prüfungen'];

?><!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Zugriffe — Solidon3D</title>
<style>
  /* Ein Armaturenbrett für einen Leser: oben die Sätze, darunter die Zahlen,
     die sie belegen. Kacheln füllen die Breite, die Sprungleiste bleibt oben,
     lange Tabellen klappen auf, statt die Seite zu verlängern. Die Farben der
     Reihen kommen aus einer geprüften Palette (hell und dunkel getrennt
     gewählt); Text trägt nie die Farbe einer Reihe. */
  :root {
    color-scheme: light dark;
    --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --dim: #52514e; --muted: #898781;
    --line: #e1e0d9; --axis: #c3c2b7; --band: #f0efec;
    --bar: #2a78d6; --bar-hover: #1c5cab;
    --v1: #2a78d6; --v2: #eb6834; --v3: #1baf7a; --v4: #eda100; --v5: #e87ba4; --v6: #008300; --v7: #4a3aa7; --vx: #b4b2a9;
    --warn: #fab219; --good: #0ca30c; --bad: #d03b3b;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --dim: #c3c2b7; --muted: #898781;
      --line: #2c2c2a; --axis: #383835; --band: #232321;
      --bar: #3987e5; --bar-hover: #5598e7;
      --v1: #3987e5; --v2: #d95926; --v3: #199e70; --v4: #c98500; --v5: #d55181; --v6: #008300; --v7: #9085e9; --vx: #5f5e59;
    }
  }
  * { box-sizing: border-box; }
  body { font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; margin: 0; padding: 1.25rem 2rem 4rem;
         background: var(--page); color: var(--ink); }
  a { color: var(--bar); }
  h1 { font-size: 1.4rem; margin: 0 0 .25rem; }
  h1 .abmelden { font-size: .8rem; font-weight: normal; margin-left: .75rem; vertical-align: middle; }
  h2 { font-size: 1.15rem; margin: 2.25rem 0 .75rem; display: flex; flex-wrap: wrap; align-items: baseline; gap: .25rem 1rem; }
  h2 .sub { margin: 0; font-size: .88rem; font-weight: normal; }
  .sub { color: var(--dim); margin: 0 0 1rem; }
  nav.sprung { position: sticky; top: 0; z-index: 1; margin: .75rem -2rem 1rem; padding: .5rem 2rem;
               background: var(--band); border-bottom: 1px solid var(--line); display: flex; flex-wrap: wrap; gap: .25rem 1.5rem; }
  nav.sprung .monate { margin-left: auto; color: var(--dim); }
  nav.sprung .monate a { margin: 0 0 0 .75rem; }
  .zahlen { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(10.5rem, 100%), 1fr)); gap: .75rem; margin: 0 0 1rem; }
  .zahl { background: var(--surface); border: 1px solid var(--line); border-radius: .5rem; padding: .6rem 1rem; }
  .zahl b { display: block; font-size: 1.55rem; font-weight: 600; line-height: 1.2; }
  .zahl span { color: var(--dim); font-size: .8rem; }
  .zahl .titel { display: block; color: var(--ink); font-size: .85rem; font-weight: 600; }
  .zahl dl { display: grid; grid-template-columns: auto 1fr; gap: .1rem .6rem; margin: .5rem 0 0; font-size: .82rem; }
  .zahl dt { color: var(--dim); }
  .zahl dd { margin: 0; font-variant-numeric: tabular-nums; }
  .kacheln { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; align-items: start; }
  .stapel { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }
  @media (max-width: 69rem) {
    .kacheln { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .stapel { grid-column: 1 / -1; flex-direction: row; align-items: flex-start; }
    .stapel > * { flex: 1 1 0; min-width: 0; }
  }
  .kachel { background: var(--surface); border: 1px solid var(--line); border-radius: .5rem; padding: .75rem 1rem 1rem; min-width: 0; overflow-x: auto; }
  .kachel h3 { margin: 0 0 .35rem; font-size: .95rem; }
  .kachel h4 { margin: .75rem 0 .1rem; font-size: .82rem; font-weight: 600; color: var(--dim); }
  .kachel .sub { font-size: .82rem; margin: 0 0 .6rem; }
  .breit { grid-column: span 2; }
  .ganz { grid-column: 1 / -1; }
  .drei { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(16rem, 100%), 1fr)); gap: 0 1.5rem; }
  @media (max-width: 48rem) {
    .kacheln { grid-template-columns: minmax(0, 1fr); }
    .breit { grid-column: auto; }
    .stapel { flex-direction: column; align-items: stretch; }
    .stapel > * { flex: none; }
    body { padding: 1rem; }
    nav.sprung { margin: .75rem -1rem 1rem; padding: .5rem 1rem; }
    nav.sprung .monate { margin-left: 0; }
  }
  table { border-collapse: collapse; width: 100%; font-size: .88rem; }
  th, td { text-align: left; padding: .22rem .45rem; border-bottom: 1px solid var(--line); vertical-align: baseline; }
  th { color: var(--dim); font-weight: normal; font-size: .78rem; white-space: nowrap; }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  td.null { color: var(--muted); }
  table.ohne-umbruch td, td.tag { white-space: nowrap; }
  tr.summe td { font-weight: 600; border-top: 2px solid var(--line); }
  .balken { display: block; height: .5rem; background: var(--bar); border-radius: 2px; min-width: 1px; }
  .leer { color: var(--dim); font-style: italic; }
  .hinweis { color: var(--dim); max-width: 75ch; font-size: .88rem; }
  .delta { display: inline-block; font-size: .78rem; color: var(--dim); font-style: normal; margin-left: .35rem; }
  .zahl b .delta { font-size: .8rem; font-weight: normal; vertical-align: .2rem; margin-left: .5rem; }
  ul.pfade { columns: 2; column-gap: 2rem; margin: 0; padding-left: 1.25rem; font-size: .88rem; }
  code { font-size: .9em; }
  .warnung-block { border: 1px solid var(--warn); border-left-width: 4px; background: var(--surface); padding: .75rem 1rem; border-radius: .4rem; }
  details { margin-top: .6rem; }
  summary { cursor: pointer; color: var(--dim); font-size: .85rem; }
  details[open] summary { margin-bottom: .4rem; }
  .marke { display: inline-block; font-size: .72rem; line-height: 1.3; padding: 0 .35rem; border: 1px solid var(--axis);
           border-radius: .6rem; color: var(--dim); white-space: nowrap; margin-left: .3rem; }
  .farbe { display: inline-block; width: .7rem; height: .7rem; border-radius: 2px; margin-right: .4rem; vertical-align: -1px; }

  /* Befunde: das Wort sagt den Ton, der Rand wiederholt ihn. */
  ul.befunde { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(22rem, 100%), 1fr)); gap: .5rem .75rem; }
  .befund { background: var(--surface); border: 1px solid var(--line); border-left: 4px solid var(--axis); border-radius: .4rem; padding: .5rem .8rem; }
  .befund.warnung { border-left-color: var(--warn); }
  .befund.plus { border-left-color: var(--good); }
  .befund.minus { border-left-color: var(--bad); }
  .befund .ton { display: inline-block; font-size: .7rem; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; margin-right: .4rem; }

  /* Säulen: eine Grundlinie, dünne Säulen mit gerundetem Kopf, die Höchstmarke
     oben links; den genauen Wert trägt der Tooltip. */
  .saeulen { margin: .25rem 0 .25rem; container-type: inline-size; }
  .saeulen.dicht small.neben { visibility: hidden; }
  @container (max-width: 34rem) { .spalte small.neben { visibility: hidden; } }
  .saeulen .gipfel { display: block; font-size: .72rem; color: var(--muted); font-variant-numeric: tabular-nums; }
  .reihe { display: flex; gap: 2px; }
  .spalte { flex: 1 1 0; min-width: 0; }
  .flaeche { height: 6.5rem; display: flex; flex-direction: column; justify-content: flex-end; align-items: center;
             border-bottom: 1px solid var(--axis); }
  .saeule { display: block; width: 100%; max-width: 24px; background: var(--bar); border-radius: 3px 3px 0 0; }
  .spalte:hover .saeule { background: var(--bar-hover); }
  .spalte small { display: block; text-align: center; font-size: .68rem; line-height: 1.7; color: var(--muted);
                  white-space: nowrap; font-variant-numeric: tabular-nums; }
  .anteile .flaeche { flex-direction: column-reverse; justify-content: flex-start; align-items: stretch; gap: 1px;
                      width: 100%; max-width: 24px; margin: 0 auto; border-bottom: 0; }
  .anteile .reihe { border-bottom: 1px solid var(--axis); }
  .anteile .seg { flex-basis: 0; min-height: 1px; }
  .anteile .flaeche > .seg:last-child { border-radius: 3px 3px 0 0; }
  .anteile .ohne { flex: 1 1 auto; }
  .anteile .spalte:hover .seg { opacity: .85; }
  .v1 { background: var(--v1); } .v2 { background: var(--v2); } .v3 { background: var(--v3); } .v4 { background: var(--v4); }
  .v5 { background: var(--v5); } .v6 { background: var(--v6); } .v7 { background: var(--v7); } .vx { background: var(--vx); }
  ul.legende { display: flex; flex-wrap: wrap; gap: .2rem 1.1rem; list-style: none; padding: 0; margin: 0 0 .5rem; font-size: .85rem; }
  @media (max-width: 40rem) { ul.pfade { columns: 1; } }
</style>
</head>
<body>

<h1>Zugriffe auf solidon3d.de <a class="abmelden" href="?abmelden=1">abmelden</a></h1>
<p class="sub">Monat <?= e($month) ?>, Zeiten in <?= e(DISPLAY_ZONE) ?>.
Dieselben Zahlen <a href="?m=<?= e($month) ?>&amp;format=json">als JSON</a>.
Was hier gezählt wird und was nicht, steht <a href="#methode">unten</a>.</p>

<nav class="sprung"><a href="#befunde">Auf einen Blick</a><a href="#jetzt">Jetzt</a><a href="#reichweite">Reichweite</a><a href="#konversion">Konversion</a><a href="#nutzung">Versionen</a><a href="#methode">Methode</a><?php if (count($available) > 1): ?><span class="monate">Monat:
  <?php foreach ($available as $option): ?>
    <?php if ($option === $month): ?><b><?= e($option) ?></b>
    <?php else: ?><a href="?m=<?= e($option) ?>"><?= e($option) ?></a><?php endif; ?>
  <?php endforeach; ?></span><?php endif; ?></nav>

<?php if (!$month_complete): ?>
<p class="warnung-block"><b>Unvollständige Auswertung:</b> Die Monatsdatei überschreitet
die sichere Grenze von 16 MiB oder 16.384 gültigen Zeilen. Die angezeigten Zahlen
sind nicht vollständig; bitte die Datei archivieren und den Zähler prüfen.</p>
<?php endif; ?>

<h2 id="befunde">Auf einen Blick <span class="sub">aus den Zahlen weiter unten gelesen — Monat <?= e($month) ?>,
rollende Fenster und alle gespeicherten Tage</span></h2>
<?php if (!$findings): ?>
  <p class="leer">Noch zu wenig gezählt, um etwas daraus zu lesen.</p>
<?php else: ?>
<ul class="befunde">
  <?php foreach ($findings as $finding): ?>
  <li class="befund <?= e($finding['tone']) ?>"><?php if ($toneLabels[$finding['tone']] !== ''): ?><span class="ton"><?= e($toneLabels[$finding['tone']]) ?></span><?php endif; ?><?= e($finding['text']) ?></li>
  <?php endforeach; ?>
</ul>
<?php endif; ?>

<h2 id="jetzt">Jetzt <span class="sub">rollend bis heute, unabhängig vom gewählten Monat — die kleine
Zahl ist die Veränderung zum gleich langen Zeitraum davor<?php if (!$recentComplete): ?>;
<b>eine Monatsdatei ist unvollständig gelesen, die Werte sind Untergrenzen</b><?php endif; ?></span></h2>
<?php if ($recentDays === []): ?>
  <p class="leer">Noch nichts gezählt.</p>
<?php else: ?>
<?php [$week, $month30] = $windows; ?>
<div class="zahlen">
  <?php foreach ($metrics as $key => $label): ?>
  <div class="zahl">
    <span class="titel"><?= e($label) ?></span>
    <b><?= n($week['now'][$key]) ?><?= change($week['before'], $week['now'], $key) ?></b>
    <span>letzte 7 Tage, <?= e(short_day($week['from'])) ?>–<?= e(short_day($week['to'])) ?></span>
    <dl>
      <dt>Heute</dt><dd><?= n($todayCounts[$key]) ?></dd>
      <dt>30 Tage</dt><dd><?= n($month30['now'][$key]) ?><?= change($month30['before'], $month30['now'], $key) ?></dd>
    </dl>
  </div>
  <?php endforeach; ?>
</div>
<?php endif; ?>

<?php if (!$rows): ?>
<h2 id="reichweite">Reichweite</h2>
  <p class="leer">Für den Monat <?= e($month) ?> liegt nichts vor. Entweder hat
  noch niemand die Seite geöffnet, oder <code>count.php</code> kommt nicht an
  seinen privaten Ablageordner.</p>
<h2 id="konversion">Konversion</h2>
  <p class="leer">Ohne Zeilen keine Downloads.</p>
<?php else: ?>

<h2 id="reichweite">Reichweite <span class="sub">wer kommt, woher, und was gelesen wird — im Monat <?= e($month) ?></span></h2>

<div class="zahlen">
  <div class="zahl"><b><?= n($monthSum['p']) ?></b><span>Seitenaufrufe</span></div>
  <div class="zahl"><b><?= n($visitCount) ?></b><span>Besuche (Summe der Tage)</span></div>
  <div class="zahl"><b><?= n($pagesPerVisit, 1) ?></b><span>Seiten je Besuch</span></div>
  <div class="zahl"><b><?= e(duration_text(median($durations))) ?></b><span>Besuchsdauer, Median aus <?= n(count($durations)) ?> Besuchen mit mehr als einem Schritt</span></div>
</div>

<div class="kacheln">

<article class="kachel ganz">
<h3>Tag für Tag</h3>
<div class="drei">
  <?php foreach (['visits' => ['Besuche', 'Besuch', 'Besuche'], 'p' => ['Seitenaufrufe', 'Aufruf', 'Aufrufe'], 'd' => ['Downloads', 'Download', 'Downloads']] as $key => [$label, $one, $many]): ?>
  <div>
    <h4><?= e($label) ?> je Tag</h4>
    <?= columns(array_map(static function (string $day) use ($days, $key, $one, $many): array {
        $value = (int) ($days[$day][$key] ?? 0);
        return day_axis($day) + ['value' => $value, 'title' => day_label($day) . ': ' . plural($value, $one, $many)];
    }, $monthDays), $label . ' je Tag im Monat ' . $month) ?>
  </div>
  <?php endforeach; ?>
</div>
<details>
<summary>Alle Tage als Tabelle</summary>
<?php $dayPeak = max(1, max(array_map(static fn (array $d): int => $d['visits'], $days))); ?>
<table>
  <tr><th>Tag</th><th class="n">Besuche</th><th class="n">Aufrufe</th><th class="n">Downloads</th><th class="n">Update-Prüfungen</th><th style="width:34%"></th></tr>
  <?php foreach (array_reverse($days, true) as $day => $counts): ?>
    <tr>
      <td><?= e(day_label((string) $day)) ?></td>
      <td class="n"><?= n($counts['visits']) ?></td>
      <td class="n"><?= n($counts['p']) ?></td>
      <td class="n"><?= n($counts['d']) ?></td>
      <td class="n"><?= n($counts['u']) ?></td>
      <td><?= bar($counts['visits'], $dayPeak) ?></td>
    </tr>
  <?php endforeach; ?>
</table>
</details>
<?php if ($monthRows): ?>
<h4>Monate im Vergleich</h4>
<?php $monthPeak = max(1, max(array_column($monthRows, 'visitors'))); ?>
<table>
  <tr><th>Monat</th><th class="n">Besuche</th><th class="n">Aufrufe</th><th class="n">Downloads</th><th class="n">Update-Prüfungen</th><th style="width:25%"></th></tr>
  <?php foreach ($monthRows as $totals): ?>
    <tr>
      <td><?php if ($totals['month'] === $month): ?><b><?= e($totals['month']) ?></b><?php else: ?><a href="?m=<?= e($totals['month']) ?>"><?= e($totals['month']) ?></a><?php endif; ?><?php if (empty($totals['complete'])): ?> <abbr title="Unvollständig: Die Monatsdatei überschreitet die sichere Grenze, die Zahlen sind Untergrenzen.">≥</abbr><?php endif; ?></td>
      <td class="n"><?= n($totals['visitors']) ?></td>
      <td class="n"><?= n($totals['pages']) ?></td>
      <td class="n"><?= n($totals['downloads']) ?></td>
      <td class="n"><?= n($totals['updates']) ?></td>
      <td><?= bar($totals['visitors'], $monthPeak) ?></td>
    </tr>
  <?php endforeach; ?>
</table>
<?php endif; ?>
</article>

<article class="kachel breit">
<h3>Woher</h3>
<p class="sub">Je Besuch die verweisende Seite des ersten Aufrufs — und wie
viele dieser Besuche etwas geladen haben. Suchmaschinen schicken ihre Herkunft
oft nicht mehr mit; die stehen in der ersten Zeile.</p>
<table>
  <tr><th>Verweisende Seite</th><th class="n">Besuche</th><th class="n">Anteil</th><th class="n">Aufrufe</th><th class="n">mit Download</th><th class="n">Konversion</th></tr>
  <tr>
    <td class="leer">direkt oder ohne Herkunft</td>
    <td class="n"><?= n($direct['visits']) ?></td>
    <td class="n"><?= n(percent($direct['visits'], $visitCount), 1) ?> %</td>
    <td class="n"><?= n($direct['pages']) ?></td>
    <td class="n"><?= n($direct['downloaded']) ?></td>
    <td class="n"><?= n(percent($direct['downloaded'], $direct['visits']), 1) ?> %</td>
  </tr>
  <?php foreach (array_slice($sources, 0, TOP, true) as $host => $counts): ?>
    <tr>
      <td><?= e($host) ?></td>
      <td class="n"><?= n($counts['visits']) ?></td>
      <td class="n"><?= n(percent($counts['visits'], $visitCount), 1) ?> %</td>
      <td class="n"><?= n($counts['pages']) ?></td>
      <td class="n"><?= n($counts['downloaded']) ?></td>
      <td class="n"><?= n(percent($counts['downloaded'], $counts['visits']), 1) ?> %</td>
    </tr>
  <?php endforeach; ?>
</table>
</article>


<div class="stapel">
<?php if ($languages || $withoutPage): ?>
<article class="kachel">
<h3>Nach Sprache</h3>
<p class="sub">Die Sprachfassung der ersten Seite eines Besuchs. Direktdownloads
ohne Seite haben keine Sprache und stehen in der letzten Zeile.</p>
<table>
  <tr><th>Sprache</th><th class="n">Besuche</th><th class="n">Anteil</th><th class="n">mit Download</th><th class="n">Downloads</th></tr>
  <?php foreach ($languages as $code => $counts): ?>
    <tr>
      <td><?= e($languageNames[$code] ?? $code) ?></td>
      <td class="n"><?= n($counts['visits']) ?></td>
      <td class="n"><?= n(percent($counts['visits'], $visitCount), 1) ?> %</td>
      <td class="n"><?= n($counts['downloaded']) ?></td>
      <td class="n"><?= n($counts['downloads']) ?></td>
    </tr>
  <?php endforeach; ?>
  <?php if ($withoutPage): ?>
    <tr>
      <td class="leer">ohne Seitenaufruf</td>
      <td class="n"><?= n($withoutPage['visits']) ?></td>
      <td class="n"><?= n(percent($withoutPage['visits'], $visitCount), 1) ?> %</td>
      <td class="n"><?= n($withoutPage['downloaded']) ?></td>
      <td class="n"><?= n($withoutPage['downloads']) ?></td>
    </tr>
  <?php endif; ?>
</table>
</article>
<?php endif; ?>

<?php if ($unread): ?>
<article class="kachel">
<h3>Ungelesene Seiten</h3>
<p class="sub"><?= n(count($unread)) ?> der <?= n(count($sitemap)) ?> Seiten
aus der Sitemap ohne einen einzigen Aufruf in diesem Monat.</p>
<details>
<summary>Liste zeigen</summary>
<ul class="pfade">
  <?php foreach ($unread as $path): ?>
    <li><?= e($path) ?></li>
  <?php endforeach; ?>
</ul>
</details>
</article>
<?php endif; ?>
</div>

<article class="kachel breit">
<h3>Seiten</h3>
<p class="sub">Aufrufe je Seite, dazu wie oft ein Besuch dort begann und endete.
Die Ausstiegsquote ist der Anteil der Aufrufe, nach denen der Besuch vorbei war.</p>
<?php if (!$paths): ?>
  <p class="leer">Noch keine.</p>
<?php else: ?>
<?php $pathPeak = max(1, max($paths)); ?>
<table>
  <tr><th>Pfad</th><th class="n">Aufrufe</th><th class="n">Anteil</th><th class="n">Einstiege</th><th class="n">Ausstiege</th><th class="n">Ausstiegsquote</th><th style="width:22%"></th></tr>
  <?php foreach (array_slice($paths, 0, TOP, true) as $path => $count): ?>
    <tr>
      <td><?= e($path) ?></td>
      <td class="n"><?= n($count) ?></td>
      <td class="n"><?= n(percent($count, $monthSum['p']), 1) ?> %</td>
      <td class="n"><?= n($entryPages[$path] ?? 0) ?></td>
      <td class="n"><?= n($exitPages[$path] ?? 0) ?></td>
      <td class="n"><?= n(percent($exitPages[$path] ?? 0, $count), 0) ?> %</td>
      <td><?= bar($count, $pathPeak) ?></td>
    </tr>
  <?php endforeach; ?>
</table>
<?php endif; ?>
</article>



<div class="stapel">
<?php if ($visits): ?>
<article class="kachel">
<h3>Besuchstiefe</h3>
<p class="sub">Wie viele Seiten ein Besuch umfasst.</p>
<?php $depthPeak = max(1, max($depth)); ?>
<table>
  <tr><th>Seiten je Besuch</th><th class="n">Besuche</th><th class="n">Anteil</th><th style="width:40%"></th></tr>
  <?php foreach ($depth as $label => $count): ?>
    <tr><td><?= e($label) ?></td><td class="n"><?= n($count) ?></td><td class="n"><?= n(percent($count, array_sum($depth)), 0) ?> %</td><td><?= bar($count, $depthPeak) ?></td></tr>
  <?php endforeach; ?>
</table>
</article>

<article class="kachel">
<h3>Besuchsdauer</h3>
<p class="sub">Vom ersten zum letzten Schritt, nur bei Besuchen mit mehr als einem.</p>
<?php $durationPeak = max(1, max($duration)); ?>
<table>
  <tr><th>Dauer</th><th class="n">Besuche</th><th class="n">Anteil</th><th style="width:40%"></th></tr>
  <?php foreach ($duration as $label => $count): ?>
    <tr><td><?= e($label) ?></td><td class="n"><?= n($count) ?></td><td class="n"><?= n(percent($count, array_sum($duration)), 0) ?> %</td><td><?= bar($count, $durationPeak) ?></td></tr>
  <?php endforeach; ?>
</table>
</article>
<?php endif; ?>
</div>

<article class="kachel breit">
<h3>Nach Uhrzeit</h3>
<p class="sub">Seitenaufrufe je Stunde, über den Monat aufsummiert.</p>
<?= columns(array_map(static fn (int $hour): array => [
    'label' => (string) $hour,
    'minor' => $hour % 3 !== 0,
    'value' => $byHour[$hour],
    'title' => $hour . '–' . ($hour + 1) . ' Uhr: ' . plural($byHour[$hour], 'Aufruf', 'Aufrufe'),
], range(0, 23)), 'Seitenaufrufe je Stunde') ?>
</article>

<article class="kachel">
<h3>Nach Wochentag</h3>
<p class="sub">Seitenaufrufe je Wochentag.</p>
<?= columns(array_map(static fn (int $weekday): array => [
    'label' => substr($weekdayNames[$weekday], 0, 2),
    'value' => $byWeekday[$weekday],
    'title' => $weekdayNames[$weekday] . ': ' . plural($byWeekday[$weekday], 'Aufruf', 'Aufrufe'),
], range(1, 7)), 'Seitenaufrufe je Wochentag') ?>
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
  <?php if ($monthSum['d'] > 0): ?>
  <tr>
    <td class="leer">Anteil</td>
    <?php foreach ($platforms as $platform): ?><td class="n"><?= n(percent($platformTotals[$platform], $monthSum['d']), 0) ?> %</td><?php endforeach; ?>
    <td class="n"></td>
  </tr>
  <?php endif; ?>
</table>
</article>
<?php endif; ?>


<div class="stapel">
<?php if ($beforeDownload): ?>
<article class="kachel">
<h3>Seite vor dem Download</h3>
<p class="sub">Die zuletzt geöffnete Seite, als der Download begann — welcher
Knopf benutzt wird.</p>
<?php foreach ([array_slice($beforeDownload, 0, 10, true), array_slice($beforeDownload, 10, TOP - 10, true)] as $part => $entries): ?>
<?php if ($entries === []) { continue; } ?>
<?php if ($part === 1): ?><details><summary><?= plural(count($entries), 'weitere Seite', 'weitere Seiten') ?></summary><?php endif; ?>
<table>
  <?php if ($part === 0): ?><tr><th>Pfad</th><th class="n">Downloads</th><th class="n">Anteil</th></tr><?php endif; ?>
  <?php foreach ($entries as $path => $count): ?>
    <tr><td><?php if ((string) $path === ''): ?><span class="leer">ohne Seitenaufruf</span><?php else: ?><?= e($path) ?><?php endif; ?></td><td class="n"><?= n($count) ?></td><td class="n"><?= n(percent($count, $monthSum['d']), 0) ?> %</td></tr>
  <?php endforeach; ?>
</table>
<?php if ($part === 1): ?></details><?php endif; ?>
<?php endforeach; ?>
</article>
<?php endif; ?>

<article class="kachel">
<h3>Dateien</h3>
<?php if (!$files): ?>
  <p class="leer">Der Ordner ist leer, und geladen wurde auch nichts.</p>
<?php else: ?>
<p class="sub"><?= plural(count($present), 'Datei', 'Dateien') ?> im Download-Ordner; geladen im Monat: <?= n($monthSum['d']) ?>.</p>
<details>
<summary>Alle Dateien mit Größe und Downloads</summary>
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
</details>
<?php endif; ?>
</article>
</div>

</div>

<?php endif; ?>

<h2 id="nutzung">Versionen <span class="sub">Update-Prüfungen aller gespeicherten Tage<?php if ($timeline['from'] !== null): ?>,
<?= e(short_day($timeline['from'])) ?>–<?= e(short_day($timeline['to'])) ?><?php endif; ?> — unabhängig vom gewählten Monat<?php if (!$allComplete): ?>;
<b>eine Monatsdatei ist unvollständig gelesen, die Werte sind Untergrenzen</b><?php endif; ?></span></h2>
<p class="hinweis">Die Anwendung nennt bei jedem Start ihre Version, wenn die
Update-Prüfung eingeschaltet ist. Gezählt werden Abrufe, auch wiederholte: Drei
Prüfungen derselben Anwendung stehen dreimal in der Zahl. Es werden keine
Besucherkennzeichen für diese Auswertung gebildet; wie viele Rechner oder
Personen dahinterstehen, lässt sich daraus nicht bestimmen. Die Anteile zeigen,
wie schnell eine neue Version die alte ablöst, nicht wie viele sie benutzen.</p>

<?php if (!$versions): ?>
  <p class="leer">Noch keine Update-Prüfung gezählt. Entweder läuft die
  Umschreibung in <code>.htaccess</code> nicht, oder es hat seit dem Einbau
  niemand die Anwendung gestartet.</p>
<?php else: ?>
<div class="zahlen">
  <div class="zahl"><b><?= n($updateCount) ?></b><span>Update-Prüfungen im Zeitraum</span></div>
  <div class="zahl"><b><?= n($updatesPerDay, 1) ?></b><span>je Kalendertag</span></div>
  <div class="zahl"><b><?= ($releaseLife['last_7_days_share_percent'] ?? null) === null ? '—' : n($releaseLife['last_7_days_share_percent'], 1) . ' %' ?></b><span>der Prüfungen der letzten 7 Tage aus der aktuellen Version<?= $release !== '' ? ' ' . e($release) : '' ?></span></div>
  <div class="zahl"><b><?= n(count($versions)) ?></b><span>Versionen gesehen</span></div>
</div>

<div class="kacheln">

<article class="kachel ganz">
<h3 id="versionen">Je Version</h3>
<p class="sub">Veröffentlicht nennt den belegten Release-Tag, zuerst geprüft den ersten
gespeicherten Aufruf ab diesem Tag. Prüfungen vor belegten Release-Tagen und künftig
als Test gekennzeichnete Aufrufe zählen nicht mit. „Mehrheit ab“ ist der erste Tag mit
mehr als der Hälfte aller Prüfungen; „erste Woche“ ihr Anteil in den sieben Tagen ab
Veröffentlichung. Fehlt der Release-Tag oder reichen die Daten nicht bis dorthin,
bleiben beide Kennzahlen leer. Frühere Tests ab dem Release-Tag sind nicht erkennbar.</p>
<?php $lifePeak = max(1, ...array_column($timeline['versions'], 'checks')); ?>
<table class="ohne-umbruch">
  <tr><th>Version</th><th>veröffentlicht</th><th>zuerst geprüft</th><th>zuletzt</th><th class="n">Tage</th><th class="n">Prüfungen</th><th class="n">Anteil</th><th style="width:9%"></th><th class="n">letzte 7 Tage</th><th class="n">erste Woche</th><th>Mehrheit ab</th><th>stärkster Tag</th></tr>
  <?php foreach ($timeline['versions'] as $life): ?>
  <tr>
    <td><span class="farbe <?= e($slotOf[$life['version']] ?? 'vx') ?>"></span><?= e($life['version']) ?><?php if ($life['current']): ?><span class="marke">aktuell</span><?php endif; ?></td>
    <td><?= $life['published_on'] === null ? '<span class="leer">nicht belegt</span>' : e(day_label($life['published_on'])) ?></td>
    <td><?= $life['since_data_start'] ? '<span class="leer">seit Datenbeginn</span>' : e(day_label($life['first_seen'])) ?></td>
    <td><?= $life['last_seen'] === $today ? 'heute' : e(day_label($life['last_seen'])) ?></td>
    <td class="n"><?= n($life['active_days']) ?></td>
    <td class="n"><?= n($life['checks']) ?></td>
    <td class="n"><?= n($life['share_percent'], 1) ?> %</td>
    <td><?= bar($life['checks'], $lifePeak) ?></td>
    <td class="n"><?= n($life['last_7_days']) ?><?php if ($life['last_7_days_share_percent'] !== null): ?> · <?= n($life['last_7_days_share_percent'], 0) ?> %<?php endif; ?></td>
    <td class="n"><?= $life['first_week_share_percent'] === null ? '—' : n($life['first_week_share_percent'], 0) . ' %' ?></td>
    <td><?php if ($life['majority_from'] !== null): ?><?= e(day_label($life['majority_from'])) ?> <span class="leer">nach <?= e(plural((int) $life['days_to_majority'], 'Tag', 'Tagen')) ?></span><?php elseif (!$life['release_covered']): ?>—<?php else: ?><span class="leer">noch nicht</span><?php endif; ?></td>
    <td><?= e(day_label($life['peak_day'])) ?> <span class="leer">(<?= n($life['peak']) ?>)</span></td>
  </tr>
  <?php endforeach; ?>
</table>
</article>

<article class="kachel ganz">
<h3>Anteile Tag für Tag</h3>
<p class="sub">Jede Säule ist ein Tag und zusammen hundert Prozent seiner Prüfungen;
die neueste Version liegt unten. Den genauen Wert zeigt der Tooltip, alle Zahlen
stehen in der Tabelle darunter.</p>
<ul class="legende">
  <?php foreach ($versionSeries as $item): ?>
  <li><span class="farbe <?= e($item['slot']) ?>"></span><?= e($item['name']) ?></li>
  <?php endforeach; ?>
</ul>
<?= share_chart($timeline['days'], $versionSeries) ?>
<h4>Update-Prüfungen je Tag</h4>
<?= columns(array_map(static fn (array $line): array => day_axis($line['day']) + [
    'value' => $line['total'],
    'title' => day_label($line['day']) . ': ' . plural($line['total'], 'Prüfung', 'Prüfungen'),
], $timeline['days']), 'Update-Prüfungen je Tag') ?>
</article>

<article class="kachel ganz">
<h3>Versionen Tag für Tag</h3>
<p class="sub">Jede Version in ihrer Spalte, der neueste Tag oben. „neu“ markiert den
belegten Veröffentlichungstag.</p>
<details open>
<summary><?= plural(count($timeline['days']), 'Tag', 'Tage') ?>, <?= plural(count($timeline['columns']), 'Version', 'Versionen') ?></summary>
<table>
  <tr><th>Tag</th><?php foreach ($timeline['columns'] as $column): ?><th class="n"><span class="farbe <?= e($slotOf[$column] ?? 'vx') ?>"></span><?= e($column) ?></th><?php endforeach; ?><th class="n">Summe</th><?php if ($release !== '' && in_array($release, $timeline['columns'], true)): ?><th class="n">Anteil <?= e($release) ?></th><?php endif; ?></tr>
  <?php foreach (array_reverse($timeline['days']) as $line): ?>
    <tr>
      <td class="tag"><?= e(day_label($line['day'])) ?><?php foreach ($line['new'] as $version): ?><span class="marke">neu: <?= e($version) ?></span><?php endforeach; ?></td>
      <?php foreach ($timeline['columns'] as $column): ?><td class="n<?= $line['cells'][$column] === 0 ? ' null' : '' ?>"><?= n($line['cells'][$column]) ?></td><?php endforeach; ?>
      <td class="n<?= $line['total'] === 0 ? ' null' : '' ?>"><?= n($line['total']) ?></td>
      <?php if ($release !== '' && in_array($release, $timeline['columns'], true)): ?><td class="n"><?= $line['release_share_percent'] === null || $line['day'] < ($releaseLife['published_on'] ?? $releaseLife['first_seen'] ?? '') ? '—' : n($line['release_share_percent'], 0) . ' %' ?></td><?php endif; ?>
    </tr>
  <?php endforeach; ?>
</table>
</details>
</article>

</div>
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
Vergleich der letzten 30 Tage mit den 30 davor fehlen, und der Block
<em>Versionen</em> reicht höchstens so weit zurück. Die Sätze unter
<em>Auf einen Blick</em> sind Regeln über die Zahlen dieser Seite; wo eine Zahl
zu klein ist, um etwas zu sagen, fehlt der Satz. (Ein Cookie gibt es
hier doch: dieses Fenster. Es merkt sich die Anmeldung, gilt nur unterhalb von
<code>/api/</code> und geht keinen Besucher etwas an.)</p>

</body>
</html>
