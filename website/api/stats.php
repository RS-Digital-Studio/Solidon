<?php
/**
 * Zeigt, was website/api/count.php gezählt hat — Aufrufe, Besuche, Downloads.
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
 * **Einrichtung — ohne diesen Schritt bleibt die Seite zu.** Neben dieser
 * Datei muss `.stats-zugang.php` liegen und den Hash eines Passworts
 * enthalten. Sie ist eine PHP-Datei und keine Textdatei, damit der Webserver
 * sie ausführt statt sie herzugeben, falls eine .htaccess einmal nicht greift.
 * Angelegt wird sie von
 *
 *     .venv\Scripts\python.exe tools/make_stats_access.py
 *
 * und hochgeladen mit
 *
 *     .venv\Scripts\python.exe tools/upload_website.py website/api/.stats-zugang.php
 *
 * Von Hand über `php -r` geht es auch, aber dabei lauert eine Falle, die
 * still zuschlägt: Ein bcrypt-Hash enthält `$`-Zeichen, und wer ihn in einer
 * Zeichenkette mit doppelten Anführungszeichen ablegt, bekommt eine Datei mit
 * einem verstümmelten Hash — die Anmeldung scheitert dann mit richtigem
 * Passwort. Unten steht deshalb eine Prüfung, die genau das meldet, statt es
 * als falsches Passwort auszugeben.
 *
 * Die Datei steht in .gitignore. Ein Passwort-Hash im Repository ist zwar
 * kein Klartext, aber auch kein Geheimnis mehr — und dieses hier schützt die
 * einzige nicht-öffentliche Seite der Domain.
 *
 * Braucht PHP 7.4 oder neuer.
 */

declare(strict_types=1);

// --- Einstellungen ---------------------------------------------------------

/** Woher die Anmeldung ihren Vergleichswert nimmt. */
const ACCESS_FILE = __DIR__ . '/.stats-zugang.php';

/** In welcher Zeitzone die Tage gezählt werden. Gespeichert wird UTC; wer
 *  die Zahlen liest, denkt in seiner eigenen Zeit. */
const DISPLAY_ZONE = 'Europe/Berlin';

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
    $access = @include ACCESS_FILE;
    $hash = is_array($access) ? (string) ($access['hash'] ?? '') : '';

    if ($hash === '') {
        http_response_code(503);
        header('Content-Type: text/plain; charset=utf-8');
        echo "Diese Seite ist noch nicht eingerichtet.\n\n"
            . "Es fehlt .stats-zugang.php neben stats.php. Anlegen mit\n"
            . "  tools/make_stats_access.py\n"
            . "und einzeln hochladen.\n";
        exit;
    }

    // Ein Hash, den `password_verify` nicht deuten kann, sagt sonst zu jedem
    // Passwort Nein — und der Grund sähe von außen aus wie ein Tippfehler.
    // Der häufigste Fall ist ein Hash, dem beim Anlegen die `$`-Zeichen
    // ausgetrieben wurden; er ist dann zu kurz und trägt keinen Algorithmus.
    if ((password_get_info($hash)['algo'] ?? null) === null) {
        http_response_code(503);
        header('Content-Type: text/plain; charset=utf-8');
        echo "Der hinterlegte Passwort-Hash ist unbrauchbar.\n\n"
            . "In .stats-zugang.php steht keine gültige bcrypt-Zeichenkette —\n"
            . "meist, weil die \$-Zeichen beim Anlegen verschluckt wurden.\n"
            . "Neu anlegen mit tools/make_stats_access.py und hochladen.\n";
        exit;
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
    if (!ctype_digit($until) || (int) $until < time()) {
        return false;
    }
    return hash_equals(hash_hmac('sha256', $until, signing_key($hash)), $signature);
}

/** Wo die Fehlversuche gezählt werden — beim Zähler, nicht im Dokumentenstamm. */
function tries_file(): string
{
    return store_dir() . '/anmeldeversuche.json';
}

/** Wie viele Fehlversuche in der letzten Viertelstunde stehen. */
function recent_tries(): int
{
    $stamps = @json_decode((string) @file_get_contents(tries_file()), true);
    if (!is_array($stamps)) {
        return 0;
    }
    $since = time() - 900;
    return count(array_filter($stamps, static fn ($t): bool => is_int($t) && $t > $since));
}

/** Einen Fehlversuch vermerken; ältere fallen dabei heraus. */
function note_try(): void
{
    $stamps = @json_decode((string) @file_get_contents(tries_file()), true);
    $since = time() - 900;
    $kept = is_array($stamps)
        ? array_values(array_filter($stamps, static fn ($t): bool => is_int($t) && $t > $since))
        : [];
    $kept[] = time();
    @file_put_contents(tries_file(), json_encode($kept), LOCK_EX);
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
        header('Location: ' . strtok((string) ($_SERVER['REQUEST_URI'] ?? ''), '?'), true, 303);
        exit;
    }

    if (token_ok((string) ($_COOKIE[COOKIE] ?? ''), $hash)) {
        return;
    }

    $message = '';
    if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
        if (recent_tries() >= MAX_TRIES) {
            $message = 'Zu viele Versuche. Eine Viertelstunde warten.';
        } elseif (password_verify((string) ($_POST['password'] ?? ''), $hash)) {
            set_cookie(make_token($hash), time() + COOKIE_DAYS * 86400);
            header('Location: ' . strtok((string) ($_SERVER['REQUEST_URI'] ?? ''), '?'), true, 303);
            exit;
        } else {
            note_try();
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
    $outside = dirname(__DIR__, 2) . '/solidon-stats';
    if (@is_dir($outside)) {
        return $outside;
    }
    return __DIR__ . '/.stats';
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
function entries(string $dir, string $month): array
{
    $path = $dir . '/' . $month . '.jsonl';
    if (!is_file($path)) {
        return [];
    }
    $zone = new DateTimeZone(DISPLAY_ZONE);
    $rows = [];
    foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
        $row = json_decode($line, true);
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
            'kind' => (string) ($row['k'] ?? ''),
            'value' => (string) ($row['v'] ?? ''),
            'from' => (string) ($row['r'] ?? ''),
            'mark' => (string) ($row['u'] ?? ''),
        ];
    }
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

/** Wie viele verschiedene Besucher an einem Tag — je Tag gezählt, nie darüber
 *  hinaus: Das Kennzeichen wechselt um Mitternacht, eine Summe über Tage wäre
 *  keine Besucherzahl, sondern eine Erfindung. */
function visitors_per_day(array $rows): array
{
    $marks = [];
    foreach ($rows as $row) {
        if ($row['mark'] !== '') {
            $marks[$row['day']][$row['mark']] = true;
        }
    }
    $counts = [];
    foreach ($marks as $day => $set) {
        $counts[$day] = count($set);
    }
    ksort($counts);
    return $counts;
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
 * Die Muster folgen den vier ausgelieferten Paketarten aus
 * `tools/make_download.py`; was keines trifft, bleibt unter seinem Namen
 * stehen, statt in einem „Sonstige"-Topf zu verschwinden.
 */
function platform_of(string $file): string
{
    if (stripos($file, 'Setup') !== false || stripos($file, '.exe') !== false) {
        return 'Windows';
    }
    if (stripos($file, '.flatpak') !== false || stripos($file, '.AppImage') !== false) {
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

/**
 * Die Besuche eines Monats: je Tag und Kennzeichen die Seitenaufrufe, in der
 * Reihenfolge der Datei.
 *
 * Grundlage für Einstiegsseiten und Besuchstiefe. Beides bleibt innerhalb
 * eines Tages — dieselbe Grenze wie bei den Besucherzahlen, aus demselben
 * Grund: Um Mitternacht endet, was sich zusammenfassen lässt.
 */
function visits(array $rows): array
{
    $found = [];
    foreach ($rows as $row) {
        if ($row['kind'] !== 'p' || $row['mark'] === '') {
            continue;
        }
        $found[$row['day'] . '|' . $row['mark']][] = $row['value'];
    }
    return $found;
}

/** Die Kopfzeile eines Monats: Aufrufe, Besuche, Downloads — für den Vergleich
 *  über die Monate, ohne die ganze Seite je Monat aufzubauen. */
function month_totals(string $dir, string $month): array
{
    $rows = entries($dir, $month);
    $pages = 0;
    $downloads = 0;
    foreach ($rows as $row) {
        if ($row['kind'] === 'p') {
            $pages++;
        } elseif ($row['kind'] === 'd') {
            $downloads++;
        }
    }
    return [
        'pages' => $pages,
        'visitors' => array_sum(visitors_per_day($rows)),
        'downloads' => $downloads,
    ];
}

$dir = store_dir();
$available = months($dir);
$zone = new DateTimeZone(DISPLAY_ZONE);
$current = (new DateTimeImmutable('now', $zone))->format('Y-m');
$month = (string) ($_GET['m'] ?? ($available[0] ?? $current));
if (!preg_match('/^\d{4}-\d{2}$/', $month)) {
    $month = $current;
}

$rows = entries($dir, $month);
$pages = array_filter($rows, static fn (array $row): bool => $row['kind'] === 'p');
$downloads = array_filter($rows, static fn (array $row): bool => $row['kind'] === 'd');

$per_day = [];
foreach ($rows as $row) {
    $per_day[$row['day']][$row['kind']] = ($per_day[$row['day']][$row['kind']] ?? 0) + 1;
}
ksort($per_day);
$visitors = visitors_per_day($rows);
$peak = max(1, max(array_map(static fn (array $d): int => ($d['p'] ?? 0) + ($d['d'] ?? 0), $per_day ?: [[]]) ?: [1]));

$today = (new DateTimeImmutable('now', $zone))->format('Y-m-d');
$today_pages = $per_day[$today]['p'] ?? 0;
$today_downloads = $per_day[$today]['d'] ?? 0;

// Seiten je Besuch — die eine Zahl, die „viele Aufrufe" von „viele Leute"
// unterscheidet. Ohne Besuche bleibt sie leer statt durch null zu teilen.
$visit_sum = array_sum($visitors);
$pages_per_visit = $visit_sum > 0
    ? number_format(count($pages) / $visit_sum, 1, ',', '.')
    : '—';

// Nach Stunde und Wochentag, nur Seitenaufrufe: wann gelesen wird.
$by_hour = array_fill(0, 24, 0);
$by_weekday = array_fill(1, 7, 0);
foreach ($pages as $row) {
    $by_hour[$row['hour']]++;
    $by_weekday[$row['weekday']]++;
}
$hour_peak = max(1, max($by_hour));
$weekday_peak = max(1, max($by_weekday));
$weekday_names = [1 => 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag',
    'Freitag', 'Samstag', 'Sonntag'];

// Sprachfassungen der Aufrufe.
$by_language = [];
foreach ($pages as $row) {
    $code = language_of($row['value']);
    $by_language[$code] = ($by_language[$code] ?? 0) + 1;
}
arsort($by_language);
$language_names = ['de' => 'Deutsch', 'en' => 'Englisch', 'es' => 'Spanisch',
    'fr' => 'Französisch', 'it' => 'Italienisch', 'pt' => 'Portugiesisch'];

// Zielsysteme der Downloads.
$by_platform = [];
foreach ($downloads as $row) {
    $name = platform_of($row['value']);
    $by_platform[$name] = ($by_platform[$name] ?? 0) + 1;
}
arsort($by_platform);

// Einstiegsseiten und Besuchstiefe — beides je Besuch, beides je Tag.
$visit_paths = visits($rows);
$entry_pages = [];
$depth_bands = ['1 Seite' => 0, '2 bis 3' => 0, '4 bis 9' => 0, '10 und mehr' => 0];
foreach ($visit_paths as $paths) {
    $entry_pages[$paths[0]] = ($entry_pages[$paths[0]] ?? 0) + 1;
    $n = count($paths);
    if ($n === 1) {
        $depth_bands['1 Seite']++;
    } elseif ($n <= 3) {
        $depth_bands['2 bis 3']++;
    } elseif ($n <= 9) {
        $depth_bands['4 bis 9']++;
    } else {
        $depth_bands['10 und mehr']++;
    }
}
arsort($entry_pages);

// Wie viele Aufrufe ohne verweisende Seite kamen — die Zeile, die in der
// „Woher"-Tabelle sonst unsichtbar fehlt.
$without_referrer = count(array_filter($rows, static fn (array $row): bool => $row['from'] === ''));

// Alle Monate nebeneinander — erst ab dem zweiten lohnt die Tabelle.
$month_rows = [];
if (count($available) > 1) {
    foreach ($available as $option) {
        $month_rows[$option] = $option === $month
            ? ['pages' => count($pages), 'visitors' => $visit_sum, 'downloads' => count($downloads)]
            : month_totals($dir, $option);
    }
    ksort($month_rows);
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

function e(string $text): string
{
    return htmlspecialchars($text, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

?><!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Zugriffe — Solidon3D</title>
<style>
  :root { color-scheme: light dark; --line: #d8d8d4; --dim: #6b6b66; --bar: #3a6ea5; }
  @media (prefers-color-scheme: dark) { :root { --line: #3a3a38; --dim: #9a9a94; --bar: #6fa3d8; } }
  body { font: 16px/1.5 system-ui, sans-serif; margin: 0 auto; padding: 2rem 1.5rem 4rem; max-width: 60rem; }
  h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
  h1 .abmelden { font-size: .8rem; font-weight: normal; margin-left: .75rem; vertical-align: middle; }
  h2 { font-size: 1.1rem; margin: 2.5rem 0 .75rem; }
  h3 { font-size: .95rem; margin: 1.75rem 0 .5rem; }
  .sub { color: var(--dim); margin: 0 0 2rem; }
  .zahlen { display: flex; flex-wrap: wrap; gap: 1.5rem; margin: 0 0 1rem; }
  .zahl { border: 1px solid var(--line); border-radius: .5rem; padding: .75rem 1.25rem; min-width: 8rem; }
  .zahl b { display: block; font-size: 1.75rem; line-height: 1.2; }
  .zahl span { color: var(--dim); font-size: .85rem; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: .35rem .5rem; border-bottom: 1px solid var(--line); vertical-align: baseline; }
  th { font-weight: 600; color: var(--dim); font-weight: normal; font-size: .85rem; }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .balken { display: block; height: .55rem; background: var(--bar); border-radius: 2px; min-width: 1px; }
  .leer { color: var(--dim); font-style: italic; }
  nav { margin: 0 0 2rem; }
  nav a { margin-right: .75rem; }
  code { font-size: .9em; }
</style>
</head>
<body>

<h1>Zugriffe auf solidon3d.de <a class="abmelden" href="?abmelden=1">abmelden</a></h1>
<p class="sub">Monat <?= e($month) ?>, Zeiten in <?= e(DISPLAY_ZONE) ?>. Die Besucher
kommen ohne Cookie und ohne gespeicherte IP-Adresse zustande, je Tag gezählt und
über den Tag hinaus nicht zusammenführbar. (Ein Cookie gibt es hier doch: dieses
Fenster. Es merkt sich die Anmeldung, gilt nur unterhalb von <code>/api/</code>
und geht keinen Besucher etwas an.)</p>

<?php if (count($available) > 1): ?>
<nav>Monat:
  <?php foreach ($available as $option): ?>
    <?php if ($option === $month): ?><b><?= e($option) ?></b>
    <?php else: ?><a href="?m=<?= e($option) ?>"><?= e($option) ?></a><?php endif; ?>
  <?php endforeach; ?>
</nav>
<?php endif; ?>

<?php if (!$rows): ?>
  <p class="leer">Für diesen Monat liegt nichts vor. Entweder hat noch niemand
  die Seite geöffnet, oder <code>count.php</code> kommt nicht an seinen
  Ablageordner (<code><?= e($dir) ?></code>).</p>
<?php else: ?>

<div class="zahlen">
  <div class="zahl"><b><?= number_format((float) count($pages), 0, ',', '.') ?></b><span>Seitenaufrufe im Monat</span></div>
  <div class="zahl"><b><?= number_format((float) $visit_sum, 0, ',', '.') ?></b><span>Besuche (Summe der Tage)</span></div>
  <div class="zahl"><b><?= e($pages_per_visit) ?></b><span>Seiten je Besuch</span></div>
  <div class="zahl"><b><?= number_format((float) count($downloads), 0, ',', '.') ?></b><span>Downloads im Monat</span></div>
  <div class="zahl"><b><?= $today_pages ?> · <?= $today_downloads ?></b><span>heute: Aufrufe · Downloads</span></div>
</div>

<h2>Tag für Tag</h2>
<table>
  <tr><th>Tag</th><th class="n">Aufrufe</th><th class="n">Besuche</th><th class="n">Downloads</th><th style="width:40%"></th></tr>
  <?php foreach (array_reverse($per_day, true) as $day => $counts): ?>
    <?php $sum = ($counts['p'] ?? 0) + ($counts['d'] ?? 0); ?>
    <tr>
      <td><?= e($day) ?></td>
      <td class="n"><?= (int) ($counts['p'] ?? 0) ?></td>
      <td class="n"><?= (int) ($visitors[$day] ?? 0) ?></td>
      <td class="n"><?= (int) ($counts['d'] ?? 0) ?></td>
      <td><span class="balken" style="width: <?= max(1, (int) round($sum / $peak * 100)) ?>%"></span></td>
    </tr>
  <?php endforeach; ?>
</table>

<?php if ($month_rows): ?>
<h2>Monate im Vergleich</h2>
<?php $month_peak = max(1, max(array_map(static fn (array $t): int => $t['pages'], $month_rows))); ?>
<table>
  <tr><th>Monat</th><th class="n">Aufrufe</th><th class="n">Besuche</th><th class="n">Downloads</th><th style="width:40%"></th></tr>
  <?php foreach ($month_rows as $option => $totals): ?>
    <tr>
      <td><?php if ($option === $month): ?><b><?= e($option) ?></b><?php else: ?><a href="?m=<?= e($option) ?>"><?= e($option) ?></a><?php endif; ?></td>
      <td class="n"><?= number_format((float) $totals['pages'], 0, ',', '.') ?></td>
      <td class="n"><?= number_format((float) $totals['visitors'], 0, ',', '.') ?></td>
      <td class="n"><?= number_format((float) $totals['downloads'], 0, ',', '.') ?></td>
      <td><span class="balken" style="width: <?= max(1, (int) round($totals['pages'] / $month_peak * 100)) ?>%"></span></td>
    </tr>
  <?php endforeach; ?>
</table>
<?php endif; ?>

<h2>Nach Uhrzeit</h2>
<p class="sub">Seitenaufrufe je Stunde, über den ganzen Monat aufsummiert.</p>
<table>
  <tr><th>Stunde</th><th class="n">Aufrufe</th><th style="width:55%"></th></tr>
  <?php foreach ($by_hour as $hour => $count): ?>
    <?php if ($count === 0) { continue; } ?>
    <tr>
      <td><?= $hour ?>–<?= $hour + 1 ?> Uhr</td>
      <td class="n"><?= $count ?></td>
      <td><span class="balken" style="width: <?= max(1, (int) round($count / $hour_peak * 100)) ?>%"></span></td>
    </tr>
  <?php endforeach; ?>
</table>

<h2>Nach Wochentag</h2>
<table>
  <tr><th>Tag</th><th class="n">Aufrufe</th><th style="width:55%"></th></tr>
  <?php foreach ($by_weekday as $weekday => $count): ?>
    <tr>
      <td><?= e($weekday_names[$weekday]) ?></td>
      <td class="n"><?= $count ?></td>
      <td><span class="balken" style="width: <?= max(1, (int) round($count / $weekday_peak * 100)) ?>%"></span></td>
    </tr>
  <?php endforeach; ?>
</table>

<h2>Downloads</h2>
<?php
$files = tally($rows, 'value', 'd');
$present = available_files();
// Erst die gezählten in ihrer Reihenfolge, dann was sonst im Ordner liegt.
// `+` behält die linken Schlüssel, ergänzt also nur die Versionen ohne Abruf.
$listed = $files + array_map(static fn (int $size): int => 0, $present);
?>
<?php if (!$listed): ?>
  <p class="leer">Der Ordner ist leer, und geladen wurde auch nichts.</p>
<?php else: ?>
<table>
  <tr><th>Datei</th><th class="n">Größe</th><th class="n">Downloads</th></tr>
  <?php foreach ($listed as $name => $count): ?>
    <tr>
      <td>
        <?php if (isset($present[$name])): ?>
          <?php /* Der Link zeigt auf die Datei, nicht auf `count.php?f=`:
                   Wer hier klickt, prüft die eigene Seite — und das darf die
                   Zahl daneben nicht bewegen. */ ?>
          <a href="/dl/<?= e(rawurlencode($name)) ?>"><?= e($name) ?></a>
        <?php else: ?>
          <?= e($name) ?> <span class="leer">nicht mehr im Ordner</span>
        <?php endif; ?>
      </td>
      <td class="n"><?= isset($present[$name]) ? e(megabytes($present[$name])) : '—' ?></td>
      <td class="n"><?= (int) $count ?></td>
    </tr>
  <?php endforeach; ?>
</table>

<?php if ($by_platform): ?>
<h3>Nach Zielsystem</h3>
<?php $platform_peak = max(1, max($by_platform)); ?>
<table>
  <tr><th>Zielsystem</th><th class="n">Downloads</th><th style="width:55%"></th></tr>
  <?php foreach ($by_platform as $name => $count): ?>
    <tr>
      <td><?= e($name) ?></td>
      <td class="n"><?= (int) $count ?></td>
      <td><span class="balken" style="width: <?= max(1, (int) round($count / $platform_peak * 100)) ?>%"></span></td>
    </tr>
  <?php endforeach; ?>
</table>
<?php endif; ?>
<?php endif; ?>

<h2>Seiten</h2>
<?php $paths = tally($rows, 'value', 'p'); ?>
<?php if (!$paths): ?>
  <p class="leer">Noch keine.</p>
<?php else: ?>
<table>
  <tr><th>Pfad</th><th class="n">Aufrufe</th></tr>
  <?php foreach (array_slice($paths, 0, TOP, true) as $path => $count): ?>
    <tr><td><?= e($path) ?></td><td class="n"><?= (int) $count ?></td></tr>
  <?php endforeach; ?>
</table>

<?php if ($by_language): ?>
<h3>Nach Sprachfassung</h3>
<?php $language_peak = max(1, max($by_language)); ?>
<table>
  <tr><th>Fassung</th><th class="n">Aufrufe</th><th style="width:55%"></th></tr>
  <?php foreach ($by_language as $code => $count): ?>
    <tr>
      <td><?= e($language_names[$code] ?? $code) ?></td>
      <td class="n"><?= (int) $count ?></td>
      <td><span class="balken" style="width: <?= max(1, (int) round($count / $language_peak * 100)) ?>%"></span></td>
    </tr>
  <?php endforeach; ?>
</table>
<?php endif; ?>

<?php if ($entry_pages): ?>
<h3>Einstiegsseiten</h3>
<p class="sub">Die erste Seite jedes Besuchs — wo Leser ankommen, nicht wohin
sie weiterklicken. Je Tag gezählt, wie die Besuche selbst.</p>
<table>
  <tr><th>Pfad</th><th class="n">Besuche</th></tr>
  <?php foreach (array_slice($entry_pages, 0, TOP, true) as $path => $count): ?>
    <tr><td><?= e($path) ?></td><td class="n"><?= (int) $count ?></td></tr>
  <?php endforeach; ?>
</table>

<h3>Besuchstiefe</h3>
<p class="sub">Wie viele Seiten ein Besuch umfasst. Viele Ein-Seiten-Besuche
heißen: Leser kommen an und bleiben nicht — oder die eine Seite beantwortet
schon alles.</p>
<?php $depth_peak = max(1, max($depth_bands)); ?>
<table>
  <tr><th>Seiten je Besuch</th><th class="n">Besuche</th><th style="width:55%"></th></tr>
  <?php foreach ($depth_bands as $band => $count): ?>
    <tr>
      <td><?= e($band) ?></td>
      <td class="n"><?= (int) $count ?></td>
      <td><span class="balken" style="width: <?= max(1, (int) round($count / $depth_peak * 100)) ?>%"></span></td>
    </tr>
  <?php endforeach; ?>
</table>
<?php endif; ?>
<?php endif; ?>

<h2>Woher</h2>
<?php $sources = tally($rows, 'from'); ?>
<?php if (!$sources): ?>
  <p class="leer">Keine Verweise — alle kamen direkt oder über eine Seite, die
  ihre Herkunft nicht mitschickt (Suchmaschinen tun das oft nicht mehr).</p>
<?php else: ?>
<table>
  <tr><th>Verweisende Seite</th><th class="n">Aufrufe</th></tr>
  <tr><td class="leer">direkt oder ohne mitgeschickte Herkunft</td><td class="n"><?= (int) $without_referrer ?></td></tr>
  <?php foreach (array_slice($sources, 0, TOP, true) as $host => $count): ?>
    <tr><td><?= e($host) ?></td><td class="n"><?= (int) $count ?></td></tr>
  <?php endforeach; ?>
</table>
<?php endif; ?>

<?php endif; ?>

</body>
</html>
