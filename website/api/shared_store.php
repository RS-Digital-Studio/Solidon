<?php
/**
 * Die Ablage der Tauschbörse — Datenbank, Dateien und die Wege dorthin.
 *
 * Nicht direkt aufgerufen; `shared.php` ist der Endpunkt. Getrennt, weil die
 * Aktivierung es genauso macht (`activation_common.php`): Was Zustand hält,
 * liegt neben dem, was Anfragen beantwortet, und nicht darin.
 *
 * **Der Zustand liegt außerhalb von httpdocs.** Rezepte, Datenbank und
 * Bestätigungsmarken landen in `appdata/` neben dem Dokumentenstamm — dieselbe
 * Stelle, an der die Aktivierung ihren privaten Startwert hält. Was ein Kunde
 * hochlädt, darf nicht über eine geratene URL abrufbar sein, bevor es
 * bestätigt ist.
 *
 * **Was hier nicht passiert: ausführen.** Ein Rezept ist eine Liste
 * registrierter Operationen mit Werten (Regel 13). Es wird geprüft
 * (`shared_common.php`), abgelegt und wieder herausgegeben — nie gelesen, um
 * daraus etwas zu tun.
 *
 * Braucht PHP 7.4 oder neuer, PDO_SQLITE und mbstring.
 */

declare(strict_types=1);

require_once __DIR__ . '/shared_common.php';

/** Wie lange eine unbestätigte Einreichung wartet, bevor sie verfällt. */
const SHARED_CONFIRM_HOURS = 48;

/** Wie viele Einreichungen eine Adresse am Tag schafft. */
const SHARED_MAX_PER_DAY = 20;

//: Wie lange ein unbestätigter Beitrag liegen bleibt, bevor er samt dem
//: Prüfwert seiner Adresse verschwindet — die Frist steht so in
//: `datenschutz.html` und ist deshalb keine frei wählbare Zahl.
const SHARED_KEEP_UNCONFIRMED_DAYS = 7;

/**
 * Ein Fehler mit Grund, Status und stabiler Kennung.
 *
 * Dieselbe Bauart wie `ActivationFailure`: Der Client zeigt den Grund, und
 * „abgelehnt" allein hilft niemandem weiter (Regel 17).
 */
final class SharedFailure extends RuntimeException
{
    public string $reason;
    public int $status;
    public string $errorCode;
    /** @var string[] */
    public array $findings;

    /** @param string[] $findings */
    public function __construct(
        string $reason,
        int $status = 400,
        string $errorCode = 'invalid_request',
        array $findings = []
    ) {
        $this->reason = $reason;
        $this->status = $status;
        $this->errorCode = $errorCode;
        $this->findings = $findings;
        parent::__construct($reason);
    }
}

/**
 * Wo der Zustand liegt: `appdata` neben dem Dokumentenstamm.
 *
 * Ein relativer Pfad wird abgewiesen und nicht stillschweigend zu einem
 * Verzeichnis unter httpdocs — das ist der Unterschied zwischen „noch nicht
 * eingerichtet" und „öffentlich lesbar".
 */
function shared_data_path(string $variable, string $filename): string
{
    $configured = getenv($variable);
    $path = ($configured === false || $configured === '')
        ? dirname(__DIR__, 2) . DIRECTORY_SEPARATOR . 'appdata' . DIRECTORY_SEPARATOR . $filename
        : $configured;
    if (
        substr($path, 0, 1) !== DIRECTORY_SEPARATOR
        && preg_match('/^[A-Za-z]:[\\\\\/]/', $path) !== 1
    ) {
        throw new SharedFailure(
            'Die Tauschbörse ist auf diesem Server noch nicht eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    return $path;
}

/** Legt die Struktur idempotent an — dieselbe Datei trägt beide Aufrufe. */
function shared_create_schema(PDO $database): void
{
    $database->exec(
        'CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            doc TEXT NOT NULL DEFAULT "",
            author TEXT NOT NULL DEFAULT "",
            licence TEXT NOT NULL DEFAULT "",
            size INTEGER NOT NULL,
            has_geometry INTEGER NOT NULL DEFAULT 0,
            contact_hash TEXT NOT NULL,
            withdraw_key TEXT NOT NULL DEFAULT "",
            created INTEGER NOT NULL,
            published INTEGER,
            hidden INTEGER NOT NULL DEFAULT 0,
            downloads INTEGER NOT NULL DEFAULT 0
        )'
    );
    $database->exec(
        'CREATE TABLE IF NOT EXISTS pending (
            token TEXT PRIMARY KEY,
            part_id INTEGER NOT NULL,
            expires INTEGER NOT NULL
        )'
    );
    // Ein Like je Browser-Kennung und Baustein — die Eindeutigkeit steht im
    // Index und nicht in einer Abfrage davor: Zwei gleichzeitige Klicks
    // gewinnen sonst beide.
    $database->exec(
        'CREATE TABLE IF NOT EXISTS likes (
            part_id INTEGER NOT NULL,
            browser TEXT NOT NULL,
            created INTEGER NOT NULL,
            PRIMARY KEY (part_id, browser)
        )'
    );
    $database->exec(
        'CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            author TEXT NOT NULL DEFAULT "",
            contact_hash TEXT NOT NULL,
            withdraw_key TEXT NOT NULL DEFAULT "",
            confirm_token TEXT NOT NULL DEFAULT "",
            confirm_expires INTEGER NOT NULL DEFAULT 0,
            created INTEGER NOT NULL,
            published INTEGER,
            hidden INTEGER NOT NULL DEFAULT 0
        )'
    );
    // Gemeldet wird ohne Identität: Wer eine Hürde davorsetzt, bekommt keine
    // Meldungen (Konzept §3.2). Doppelmeldungen fängt die Browser-Kennung.
    $database->exec(
        'CREATE TABLE IF NOT EXISTS flags (
            part_id INTEGER NOT NULL,
            browser TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT "",
            created INTEGER NOT NULL,
            PRIMARY KEY (part_id, browser)
        )'
    );
    // Was nach dem ersten Auslieferungsstand dazugekommen ist, erreicht eine
    // vorhandene Datenbank nur hierüber — siehe shared_add_column.
    shared_add_column($database, 'parts', 'withdraw_key', 'TEXT NOT NULL DEFAULT ""');
    shared_add_column($database, 'comments', 'withdraw_key', 'TEXT NOT NULL DEFAULT ""');
    shared_add_column($database, 'comments', 'confirm_token', 'TEXT NOT NULL DEFAULT ""');
    shared_add_column($database, 'comments', 'confirm_expires', 'INTEGER NOT NULL DEFAULT 0');
    $database->exec('CREATE INDEX IF NOT EXISTS parts_published ON parts (published, hidden)');
}

/**
 * Ergänzt eine Spalte, die es in einer älteren Datenbank noch nicht gibt.
 *
 * **`CREATE TABLE IF NOT EXISTS` ändert eine vorhandene Tabelle nicht.** Das
 * ist der ganze Grund für diese Funktion, und der Fehler war nicht zu sehen:
 * Der Prüfstand legt seine Datenbank je Lauf neu an (`SOLIDON_SHARED_DB` in
 * einem Temp-Ordner), dort entsteht das Schema immer vollständig. Im Betrieb
 * ist die Datenbank per Definition alt — `withdraw_key` wäre dort nie
 * entstanden, und `?do=withdraw` hätte an einer Spalte gescheitert, die es
 * nach jedem Testlauf gibt.
 *
 * Eine nachgezogene `NOT NULL`-Spalte **braucht** ein `DEFAULT`; ohne eines
 * weigert sich SQLite, weil die vorhandenen Zeilen sonst keinen Wert hätten.
 *
 * Protokolliert wird, was wirklich ergänzt wurde: Eine Migration, die
 * stillschweigend läuft, ist von einer, die gar nicht läuft, im Betrieb nicht
 * zu unterscheiden.
 */
function shared_add_column(PDO $database, string $table, string $column, string $type): void
{
    $vorhanden = $database->query('PRAGMA table_info(' . $table . ')')->fetchAll();
    foreach ($vorhanden as $spalte) {
        if (($spalte['name'] ?? '') === $column) {
            return;
        }
    }
    $database->exec('ALTER TABLE ' . $table . ' ADD COLUMN ' . $column . ' ' . $type);
    error_log('Solidon-Börse: Spalte ' . $table . '.' . $column . ' nachgezogen.');
}

/**
 * Räumt weg, was nach sieben Tagen unbestätigt liegengeblieben ist.
 *
 * **Eine Löschzusage ist eine Zusage, keine Beschreibung.** `datenschutz.html`
 * verspricht öffentlich: „Eine unbestätigte Adresse wird nach sieben Tagen
 * gelöscht." Die Spalten `pending.expires` und `comments.confirm_expires`
 * standen dafür da, und gelöscht hat sie niemand — es gab kein einziges
 * `DELETE` darauf.
 *
 * **Zwei Fristen, und sie sind nicht dasselbe.** Der Bestätigungs*link* gilt
 * SHARED_CONFIRM_HOURS (48 Stunden); danach ist er wertlos, aber der Datensatz
 * steht noch, damit ein später Klick eine ehrliche Auskunft bekommt („dieser
 * Link ist abgelaufen") statt „kennt die Börse nicht". Der *Datensatz* fällt
 * nach sieben Tagen, und das ist die Frist aus der Datenschutzerklärung.
 *
 * **Aufgeräumt wird beim Zugriff, nicht von einem Zeitgeber.** Die Börse liegt
 * auf einem gewöhnlichen Webhosting ohne Cron; ein Wartungs-Endpunkt bräuchte
 * einen Rufer, und ein Rufer, den niemand baut, ist die Zusage von vorhin noch
 * einmal. Jeder Aufruf räumt, und weil die Abfrage über einen Zeitstempel
 * läuft, kostet sie im Regelfall nichts.
 */
function shared_sweep_unconfirmed(PDO $database): void
{
    $grenze = time() - SHARED_KEEP_UNCONFIRMED_DAYS * 86400;

    // Erst die Bausteine: Ihre Datei liegt neben der Datenbank und geht mit.
    $alt = $database->prepare(
        'SELECT id FROM parts WHERE published IS NULL AND created < ?'
    );
    $alt->execute([$grenze]);
    foreach ($alt->fetchAll() as $zeile) {
        $id = (int) $zeile['id'];
        @unlink(shared_file_for($id));
        $database->prepare('DELETE FROM pending WHERE part_id = ?')->execute([$id]);
        $database->prepare('DELETE FROM likes WHERE part_id = ?')->execute([$id]);
        $database->prepare('DELETE FROM flags WHERE part_id = ?')->execute([$id]);
        $database->prepare('DELETE FROM comments WHERE part_id = ?')->execute([$id]);
        $database->prepare('DELETE FROM parts WHERE id = ?')->execute([$id]);
    }

    // Und die Kommentare, die nie bestätigt wurden — mit ihnen der Prüfwert
    // der Adresse, denn genau der ist der Gegenstand der Zusage.
    $database->prepare('DELETE FROM comments WHERE published IS NULL AND created < ?')
        ->execute([$grenze]);

    // Eine Marke ohne ihren Datensatz wäre ein Link, der ins Leere zeigt.
    $database->exec('DELETE FROM pending WHERE part_id NOT IN (SELECT id FROM parts)');
}

/** Die Datenbank, angelegt beim ersten Zugriff. */
function shared_database(): PDO
{
    static $database = null;
    if ($database instanceof PDO) {
        return $database;
    }
    $path = shared_data_path('SOLIDON_SHARED_DB', 'shared.sqlite');
    $folder = dirname($path);
    if (!is_dir($folder) && !@mkdir($folder, 0770, true) && !is_dir($folder)) {
        throw new SharedFailure(
            'Die Tauschbörse kann ihren Ablageordner nicht anlegen.',
            503,
            'service_unavailable'
        );
    }
    try {
        $database = new PDO('sqlite:' . $path, null, null, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]);
    } catch (PDOException $error) {
        throw new SharedFailure(
            'Die Tauschbörse erreicht ihre Datenbank nicht.',
            503,
            'service_unavailable'
        );
    }
    // Ohne das wartet ein zweiter Schreiber nicht, sondern scheitert sofort.
    $database->exec('PRAGMA busy_timeout = 5000');
    $database->exec('PRAGMA journal_mode = WAL');
    shared_create_schema($database);
    return $database;
}

/** Wo die Rezeptdateien liegen — außerhalb von httpdocs, wie die Datenbank. */
function shared_files_folder(): string
{
    $folder = shared_data_path('SOLIDON_SHARED_FILES', 'shared-files');
    if (!is_dir($folder) && !@mkdir($folder, 0770, true) && !is_dir($folder)) {
        throw new SharedFailure(
            'Die Tauschbörse kann ihren Dateiordner nicht anlegen.',
            503,
            'service_unavailable'
        );
    }
    return $folder;
}

/**
 * Ein Dateiname, der nur aus dem stammt, was wir selbst vergeben.
 *
 * **Nicht aus dem Titel abgeleitet.** Ein Kunde bestimmt den Titel, und ein
 * Dateiname aus fremder Eingabe ist der klassische Weg aus einem Ordner heraus
 * — auch wenn drei Filter davorstehen. Die laufende Nummer der Datenbank
 * kennt diese Frage gar nicht erst.
 */
function shared_file_for(int $id): string
{
    return shared_files_folder() . DIRECTORY_SEPARATOR . sprintf('%08d.json', $id);
}

/**
 * Die Kennung, unter der ein Baustein öffentlich auftritt.
 *
 * Aus Titel **und** Nummer: Der Titel macht die Adresse lesbar, die Nummer
 * macht sie eindeutig. Zwei Kunden dürfen ihren Halter „Werkbankhalter"
 * nennen, ohne dass einer von beiden umbenennen muss.
 */
function shared_slug(string $title, int $id): string
{
    $ascii = @iconv('UTF-8', 'ASCII//TRANSLIT', $title);
    $lower = strtolower($ascii === false ? '' : $ascii);
    $clean = trim(preg_replace('~[^a-z0-9]+~', '-', $lower) ?? '', '-');
    if ($clean === '') {
        $clean = 'baustein';
    }
    return substr($clean, 0, 60) . '-' . $id;
}

/**
 * Eine Mailadresse als Hash, nie im Klartext.
 *
 * Die Börse braucht sie, um Doppeleinreichungen zu zählen und eine Bestätigung
 * zu schicken — sie braucht sie nicht, um sie aufzubewahren. Was im Datensatz
 * steht, ist ein Hash mit dem Startwert des Servers; wer die Datenbank liest,
 * findet keine Adressen (Konzept §3.4, Datenschutz).
 */
function shared_contact_hash(string $address): string
{
    $seed = getenv('SOLIDON_SHARED_SEED');
    if ($seed === false || $seed === '') {
        // Kein zufälliger Rückfall: Ein Hash mit wechselndem Startwert zählt
        // keine Doppeleinreichungen und meldet trotzdem Erfolg.
        throw new SharedFailure(
            'Die Tauschbörse ist auf diesem Server noch nicht eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    return hash('sha256', $seed . '|' . strtolower(trim($address)));
}

/**
 * Eine Marke aus dem Zufallsgenerator, als Hex.
 *
 * 16 Byte für den Bestätigungslink, der Stunden gilt; 32 für den
 * Rückziehschlüssel, den der Kunde behält. `datenschutz.html` sagt „ein Link
 * mit einem langen Schlüssel" zu, und das ist keine Floskel: Der eine verfällt,
 * der andere liegt Jahre in einem Postfach.
 */
function shared_token(int $bytes = 16): string
{
    return bin2hex(random_bytes($bytes));
}
