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
 * Aufruf: https://solidon3d.de/api/stats.php — das Anmeldefenster verlangt
 * einen Benutzernamen, geprüft wird aber nur das Passwort. Was im Namensfeld
 * steht, ist gleichgültig.
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

// --- Anmeldung -------------------------------------------------------------

/**
 * Die Seite bleibt zu, bis sich jemand ausweist.
 *
 * Fehlt die Zugangsdatei, gibt es kein Ersatzpasswort und keinen offenen
 * Zustand: Eine Statistikseite, die im Zweifel offen ist, ist schlimmer als
 * keine.
 */
function require_login(): void
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

    // **Der Benutzername zählt nicht.** Ein Anmeldefenster verlangt beide
    // Felder, aber hier gibt es nur einen Leser — ein zweites Geheimnis, das
    // niemand vergeben hat, wäre keine Sicherheit, sondern eine Stelle, an der
    // man sich selbst aussperrt. Was im Namensfeld steht, ist gleichgültig;
    // geprüft wird das Passwort.
    $password = (string) ($_SERVER['PHP_AUTH_PW'] ?? '');

    // Manche Server reichen den Authorization-Kopf nicht an PHP durch, sondern
    // legen ihn in eine Umgebungsvariable. Ohne diese Zeilen käme dort nie
    // ein Passwort an, und die Seite bliebe auch mit richtigem Passwort zu.
    if ($password === '') {
        $header = (string) ($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '');
        if (stripos($header, 'basic ') === 0) {
            $pair = explode(':', (string) base64_decode(substr($header, 6)), 2);
            $password = $pair[1] ?? '';
        }
    }

    if ($password === '' || !password_verify($password, $hash)) {
        header('WWW-Authenticate: Basic realm="Solidon3D"');
        http_response_code(401);
        header('Content-Type: text/plain; charset=utf-8');
        echo "Nicht angemeldet.\n";
        exit;
    }
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
  h2 { font-size: 1.1rem; margin: 2.5rem 0 .75rem; }
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

<h1>Zugriffe auf solidon3d.de</h1>
<p class="sub">Monat <?= e($month) ?>, Zeiten in <?= e(DISPLAY_ZONE) ?>. Ohne Cookies,
ohne gespeicherte IP-Adressen — Besucher sind je Tag gezählt und lassen sich
über den Tag hinaus nicht zusammenführen.</p>

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
  <div class="zahl"><b><?= number_format((float) array_sum($visitors), 0, ',', '.') ?></b><span>Besuche (Summe der Tage)</span></div>
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

<h2>Downloads</h2>
<?php $files = tally($rows, 'value', 'd'); ?>
<?php if (!$files): ?>
  <p class="leer">Noch keiner.</p>
<?php else: ?>
<table>
  <tr><th>Datei</th><th class="n">Downloads</th></tr>
  <?php foreach ($files as $name => $count): ?>
    <tr><td><?= e($name) ?></td><td class="n"><?= (int) $count ?></td></tr>
  <?php endforeach; ?>
</table>
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
<?php endif; ?>

<h2>Woher</h2>
<?php $sources = tally($rows, 'from'); ?>
<?php if (!$sources): ?>
  <p class="leer">Keine Verweise — alle kamen direkt oder über eine Seite, die
  ihre Herkunft nicht mitschickt (Suchmaschinen tun das oft nicht mehr).</p>
<?php else: ?>
<table>
  <tr><th>Verweisende Seite</th><th class="n">Aufrufe</th></tr>
  <?php foreach (array_slice($sources, 0, TOP, true) as $host => $count): ?>
    <tr><td><?= e($host) ?></td><td class="n"><?= (int) $count ?></td></tr>
  <?php endforeach; ?>
</table>
<?php endif; ?>

<?php endif; ?>

</body>
</html>
