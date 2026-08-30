<?php
/**
 * Der Endpunkt der Tauschbörse: hochladen, bestätigen, suchen, herunterladen.
 *
 * Gegenstück zur App-Seite (`app/core/knowledge/parts/shared.py`). Die
 * Formatprüfung steht in `shared_common.php` und ist nach Roberts Entscheidung
 * gegen die Vorab-Sichtung die **einzige Instanz vor der Veröffentlichung**
 * (Konzept §7). Die Ablage steht in `shared_store.php`.
 *
 *   POST ?do=upload    Felder `recipe` (Datei), `contact` (Mailadresse)
 *   GET  ?do=confirm   Feld `token` — der Link aus der Bestätigungsmail
 *   GET  ?do=list      Felder `q` (Suchtext), `licence`, `page`
 *   GET  ?do=download  Feld `slug`
 *   GET  ?do=withdraw  Feld `key` — der zweite Link aus derselben Mail
 *
 * Antwortet immer JSON, außer beim Herunterladen — dort kommt die Rezeptdatei
 * selbst. Ein Fehler nennt seinen Grund und, wo es Befunde gibt, alle davon:
 * Wer zweimal hochladen muss, um beide Gründe zu erfahren, hat die schlechtere
 * Prüfung.
 *
 * Einrichtung: Datei nach httpdocs/api/ legen, dazu `shared_common.php`,
 * `shared_store.php` und `shared-rules.json`. `SOLIDON_SHARED_SEED` muss
 * gesetzt sein — ohne ihn verweigert die Börse den Dienst, statt Adressen mit
 * wechselndem Startwert zu hashen.
 *
 * Braucht PHP 7.4 oder neuer, PDO_SQLITE und mbstring.
 */

declare(strict_types=1);

require_once __DIR__ . '/shared_store.php';

/** Absender der Bestätigung. Muss eine Adresse dieser Domain sein (SPF). */
const SHARED_SENDER = 'noreply@solidon3d.de';

/** Wie viele Einträge eine Seite der Liste trägt. */
const SHARED_PAGE_SIZE = 24;

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');

/** Antwortet und beendet. */
function shared_answer(array $payload, int $status = 200): void
{
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

/** Ein Fehler mit Grund — und mit allen Befunden, wo es welche gibt. */
function shared_answer_error(SharedFailure $problem): void
{
    $payload = ['ok' => false, 'code' => $problem->errorCode, 'error' => $problem->reason];
    if ($problem->findings) {
        $payload['findings'] = $problem->findings;
    }
    shared_answer($payload, $problem->status);
}

/**
 * Die hochgeladene Datei als Bytes.
 *
 * **Die Größe wird vor dem Lesen geprüft**, nicht danach: Eine Datei über der
 * Grenze wird nicht erst in den Speicher geholt, um dann abgelehnt zu werden.
 */
function shared_uploaded_bytes(array $rules): string
{
    if (!isset($_FILES['recipe']) || !is_array($_FILES['recipe'])) {
        throw new SharedFailure('Es kam keine Datei an. Wählen Sie ein Rezept aus und senden Sie erneut.');
    }
    $file = $_FILES['recipe'];
    if (($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
        // `post_max_size` schlägt zu, bevor PHP die Felder füllt — dann steht
        // hier ein Fehlercode und kein Hinweis auf die Ursache.
        throw new SharedFailure(
            'Die Datei kam nicht vollständig an. Prüfen Sie ihre Größe und senden Sie erneut.'
        );
    }
    if (($file['size'] ?? 0) > $rules['max_upload_bytes']) {
        throw new SharedFailure(
            sprintf(
                'Die Datei ist %d Byte groß, erlaubt sind %d.',
                (int) $file['size'],
                (int) $rules['max_upload_bytes']
            ),
            413,
            'too_large'
        );
    }
    $bytes = @file_get_contents($file['tmp_name']);
    if ($bytes === false) {
        throw new SharedFailure('Die hochgeladene Datei ließ sich nicht lesen.');
    }
    return $bytes;
}

/** Eine Mailadresse, die wenigstens die Form hat. */
function shared_contact(): string
{
    $address = trim((string) ($_POST['contact'] ?? ''));
    if ($address === '' || filter_var($address, FILTER_VALIDATE_EMAIL) === false) {
        throw new SharedFailure(
            'Für eine Einreichung braucht die Börse eine Mailadresse — sie wird nicht '
            . 'angezeigt und dient nur der Bestätigung. Tragen Sie eine gültige Adresse ein.'
        );
    }
    return $address;
}

/** Nimmt ein Rezept an, legt es unbestätigt ab und schickt den Link. */
function shared_upload(): void
{
    $rules = shared_rules();
    $bytes = shared_uploaded_bytes($rules);
    $contact = shared_contact();

    $findings = shared_inspect($bytes, $rules);
    if ($findings) {
        throw new SharedFailure(
            'Die Datei ist kein Rezept, das die Börse annehmen kann.',
            422,
            'rejected',
            $findings
        );
    }

    $data = json_decode($bytes, true);
    $database = shared_database();
    $hash = shared_contact_hash($contact);
    $now = time();

    $today = $database->prepare(
        'SELECT COUNT(*) FROM parts WHERE contact_hash = ? AND created > ?'
    );
    $today->execute([$hash, $now - 86400]);
    if ((int) $today->fetchColumn() >= SHARED_MAX_PER_DAY) {
        throw new SharedFailure(
            'Von dieser Adresse sind heute schon genug Einreichungen gekommen. '
            . 'Versuchen Sie es morgen wieder.',
            429,
            'too_many'
        );
    }

    $database->beginTransaction();
    try {
        $insert = $database->prepare(
            'INSERT INTO parts (slug, title, doc, author, licence, size, has_geometry,
                                contact_hash, withdraw_key, created)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
        );
        $title = (string) ($data['title'] ?? $data['name'] ?? 'Baustein');
        // Der Schlüssel, mit dem der Kunde seinen Beitrag jederzeit selbst
        // zurückzieht (`datenschutz.html`). Er entsteht **hier** und nicht auf
        // Anforderung: Wer ihn später bräuchte, müsste sich ausweisen, und
        // genau das soll die Börse nicht verlangen.
        $withdraw = shared_token(32);
        $insert->execute([
            // Der endgültige Kurzname braucht die Nummer, die es erst nach dem
            // Einfügen gibt; bis dahin steht die Marke selbst darin, damit die
            // Spalte eindeutig bleibt.
            'pending-' . shared_token(),
            $title,
            (string) ($data['doc'] ?? ''),
            (string) ($data['author'] ?? ''),
            (string) ($data['license'] ?? ''),
            strlen($bytes),
            empty($data['payloads']) ? 0 : 1,
            $hash,
            $withdraw,
            $now,
        ]);
        $id = (int) $database->lastInsertId();
        $database->prepare('UPDATE parts SET slug = ? WHERE id = ?')
            ->execute([shared_slug($title, $id), $id]);

        $token = shared_token();
        $database->prepare('INSERT INTO pending (token, part_id, expires) VALUES (?, ?, ?)')
            ->execute([$token, $id, $now + SHARED_CONFIRM_HOURS * 3600]);

        if (@file_put_contents(shared_file_for($id), $bytes) === false) {
            throw new SharedFailure('Die Datei ließ sich auf dem Server nicht ablegen.', 500, 'storage');
        }
        $database->commit();
    } catch (Throwable $error) {
        $database->rollBack();
        throw $error;
    }

    shared_send_confirmation($contact, $token, $withdraw, $title);
    shared_answer([
        'ok' => true,
        'pending' => true,
        'message' => 'Angenommen. In Ihrem Postfach liegt ein Link — erst nach dem Klick '
            . 'darauf ist der Baustein öffentlich sichtbar.',
    ]);
}

/**
 * Schickt den Bestätigungslink.
 *
 * **Ein Fehlschlag beim Versand ist kein Fehlschlag der Einreichung.** Die
 * Datei liegt bereits; wer hier abbräche, hätte einen Eintrag ohne Weg zur
 * Bestätigung. Gemeldet wird er trotzdem, sonst wartet der Kunde auf eine Mail,
 * die nie kommt.
 */
function shared_send_confirmation(
    string $address,
    string $token,
    string $withdraw,
    string $title
): void {
    $host = $_SERVER['HTTP_HOST'] ?? 'solidon3d.de';
    $link = 'https://' . $host . '/api/shared.php?do=confirm&token=' . urlencode($token);
    $back = 'https://' . $host . '/api/shared.php?do=withdraw&key=' . urlencode($withdraw);
    $body = "Hallo,\r\n\r\n"
        . "Sie haben „" . $title . "\" in der Solidon-Tauschbörse eingereicht.\r\n\r\n"
        . "Mit diesem Link wird er öffentlich sichtbar:\r\n\r\n"
        . $link . "\r\n\r\n"
        . "Der Link gilt " . SHARED_CONFIRM_HOURS . " Stunden. Wenn Sie nichts eingereicht "
        . "haben, ignorieren Sie diese Nachricht — ohne Klick wird nichts veröffentlicht.\r\n"
        . "\r\n"
        // **Beide Links in einer Mail, und der zweite ohne Ablauf.** Wer
        // zurückziehen will, soll das nicht bei uns beantragen müssen; die
        // Zusage steht in datenschutz.html und lautet „jederzeit selbst".
        . "Heben Sie diese Nachricht auf: Mit dem folgenden Link ziehen Sie "
        . "Ihren Baustein jederzeit selbst zurück. Er wird dann gelöscht, und "
        . "die Verknüpfung zu Ihrer Adresse geht mit.\r\n\r\n"
        . $back . "\r\n";
    $headers = 'From: ' . SHARED_SENDER . "\r\n"
        . "Content-Type: text/plain; charset=utf-8\r\n"
        . 'Content-Transfer-Encoding: 8bit';
    if (!@mail($address, '=?UTF-8?B?' . base64_encode('Ihre Einreichung bestätigen') . '?=', $body, $headers)) {
        throw new SharedFailure(
            'Der Baustein liegt auf dem Server, aber die Bestätigungsmail ging nicht '
            . 'hinaus. Melden Sie sich beim Support, dann schalten wir ihn von Hand frei.',
            500,
            'mail_failed'
        );
    }
}

/** Der Klick aus der Mail: ab jetzt ist der Baustein öffentlich. */
function shared_confirm(): void
{
    $token = (string) ($_GET['token'] ?? '');
    if ($token === '' || preg_match('/^[0-9a-f]{32}$/D', $token) !== 1) {
        throw new SharedFailure('Dieser Bestätigungslink ist unvollständig.', 400, 'bad_token');
    }
    $database = shared_database();
    $row = $database->prepare('SELECT part_id, expires FROM pending WHERE token = ?');
    $row->execute([$token]);
    $found = $row->fetch();
    if (!$found) {
        throw new SharedFailure(
            'Diesen Bestätigungslink kennt die Börse nicht — vielleicht wurde er schon '
            . 'benutzt. Sehen Sie in der Börse nach, ob Ihr Baustein bereits dasteht.',
            404,
            'unknown_token'
        );
    }
    if ((int) $found['expires'] < time()) {
        throw new SharedFailure(
            'Dieser Bestätigungslink ist abgelaufen. Laden Sie den Baustein erneut hoch.',
            410,
            'expired'
        );
    }
    $database->prepare('UPDATE parts SET published = ? WHERE id = ?')
        ->execute([time(), (int) $found['part_id']]);
    $database->prepare('DELETE FROM pending WHERE token = ?')->execute([$token]);

    $slug = $database->prepare('SELECT slug FROM parts WHERE id = ?');
    $slug->execute([(int) $found['part_id']]);
    shared_answer([
        'ok' => true,
        'slug' => (string) $slug->fetchColumn(),
        'message' => 'Bestätigt. Der Baustein steht jetzt in der Börse.',
    ]);
}

/**
 * Zurückziehen — ein Endpunkt für Bausteine und Kommentare.
 *
 * **Der Schlüssel ist der ganze Ausweis.** Wer ihn hat, hat die Mail bekommen,
 * und mehr verlangt die Börse nicht: Ein Konto entsteht hier nicht, und wer
 * sich zum Löschen erst ausweisen müsste, könnte es nicht ohne eines.
 *
 * Gelöscht wird wirklich, nicht verborgen. `datenschutz.html` sagt „damit geht
 * die Adresse mit" zu, und ein `hidden = 1` ließe den Hash stehen — er ist ein
 * Personenbezug, solange der Startwert existiert.
 *
 * Der Vergleich läuft über `hash_equals`: Ein `=` in SQL antwortet
 * unterschiedlich schnell, je nachdem, wie viele Zeichen stimmen, und ein
 * Schlüssel, den man zeichenweise erraten kann, ist keiner. Deshalb wird die
 * Zeile über den Schlüssel geholt **und** der gefundene Wert danach in
 * konstanter Zeit verglichen.
 */
function shared_withdraw(): void
{
    $key = (string) ($_GET['key'] ?? $_POST['key'] ?? '');
    if ($key === '' || preg_match('/^[0-9a-f]{64}$/D', $key) !== 1) {
        throw new SharedFailure(
            'Dieser Rückziehlink ist unvollständig. Nehmen Sie den vollständigen Link aus '
            . 'der Mail, die Sie beim Einreichen bekommen haben.',
            400,
            'bad_key'
        );
    }
    $database = shared_database();

    $part = $database->prepare('SELECT id, withdraw_key FROM parts WHERE withdraw_key = ?');
    $part->execute([$key]);
    $found = $part->fetch();
    if ($found && hash_equals((string) $found['withdraw_key'], $key)) {
        $id = (int) $found['id'];
        $database->beginTransaction();
        try {
            $database->prepare('DELETE FROM likes WHERE part_id = ?')->execute([$id]);
            $database->prepare('DELETE FROM flags WHERE part_id = ?')->execute([$id]);
            $database->prepare('DELETE FROM comments WHERE part_id = ?')->execute([$id]);
            $database->prepare('DELETE FROM pending WHERE part_id = ?')->execute([$id]);
            $database->prepare('DELETE FROM parts WHERE id = ?')->execute([$id]);
            $database->commit();
        } catch (Throwable $error) {
            $database->rollBack();
            throw $error;
        }
        // Die Datei erst nach dem Commit: Ein zurückgerollter Datensatz mit
        // gelöschter Datei wäre ein Eintrag, der auf nichts zeigt.
        @unlink(shared_file_for($id));
        shared_answer([
            'ok' => true,
            'kind' => 'part',
            'message' => 'Zurückgezogen. Der Baustein ist gelöscht, und die Verknüpfung zu '
                . 'Ihrer Adresse mit ihm.',
        ]);
    }

    $comment = $database->prepare('SELECT id, withdraw_key FROM comments WHERE withdraw_key = ?');
    $comment->execute([$key]);
    $found = $comment->fetch();
    if ($found && hash_equals((string) $found['withdraw_key'], $key)) {
        $database->prepare('DELETE FROM comments WHERE id = ?')->execute([(int) $found['id']]);
        shared_answer([
            'ok' => true,
            'kind' => 'comment',
            'message' => 'Zurückgezogen. Der Kommentar ist gelöscht.',
        ]);
    }

    throw new SharedFailure(
        'Zu diesem Schlüssel gibt es nichts mehr — vielleicht haben Sie den Beitrag '
        . 'bereits zurückgezogen. Sehen Sie in der Börse nach, ob er noch dasteht.',
        404,
        'unknown_key'
    );
}

/** Die Liste: veröffentlicht, nicht verborgen, neueste zuerst. */
function shared_list(): void
{
    $database = shared_database();
    $search = trim((string) ($_GET['q'] ?? ''));
    $licence = trim((string) ($_GET['licence'] ?? ''));
    $page = max(0, (int) ($_GET['page'] ?? 0));

    $where = ['published IS NOT NULL', 'hidden = 0'];
    $values = [];
    if ($search !== '') {
        // Titel **und** Erklärtext: Wer nach „Lochwand" sucht, meint nicht nur
        // die, die es in den Titel geschrieben haben.
        $where[] = '(title LIKE ? OR doc LIKE ?)';
        $values[] = '%' . $search . '%';
        $values[] = '%' . $search . '%';
    }
    if ($licence !== '') {
        $where[] = 'licence = ?';
        $values[] = $licence;
    }

    $sql = 'SELECT p.slug, p.title, p.doc, p.author, p.licence, p.size, p.has_geometry,
                   p.published, p.downloads,
                   (SELECT COUNT(*) FROM likes WHERE part_id = p.id) AS likes,
                   (SELECT COUNT(*) FROM comments
                     WHERE part_id = p.id AND published IS NOT NULL AND hidden = 0) AS comments
              FROM parts p
             WHERE ' . implode(' AND ', $where) . '
             ORDER BY p.published DESC
             LIMIT ? OFFSET ?';
    $rows = $database->prepare($sql);
    $rows->execute([...$values, SHARED_PAGE_SIZE, $page * SHARED_PAGE_SIZE]);

    $total = $database->prepare(
        'SELECT COUNT(*) FROM parts p WHERE ' . implode(' AND ', $where)
    );
    $total->execute($values);

    shared_answer([
        'ok' => true,
        'total' => (int) $total->fetchColumn(),
        'page' => $page,
        'page_size' => SHARED_PAGE_SIZE,
        'parts' => $rows->fetchAll(),
    ]);
}

/** Die Rezeptdatei selbst — das Einzige, was nicht JSON antwortet. */
function shared_download(): void
{
    $slug = (string) ($_GET['slug'] ?? '');
    if ($slug === '' || preg_match('/^[a-z0-9-]{1,80}$/D', $slug) !== 1) {
        throw new SharedFailure('Diesen Baustein kennt die Börse nicht.', 404, 'unknown');
    }
    $database = shared_database();
    $row = $database->prepare(
        'SELECT id FROM parts WHERE slug = ? AND published IS NOT NULL AND hidden = 0'
    );
    $row->execute([$slug]);
    $id = $row->fetchColumn();
    if ($id === false) {
        throw new SharedFailure('Diesen Baustein kennt die Börse nicht.', 404, 'unknown');
    }

    $path = shared_file_for((int) $id);
    $bytes = @file_get_contents($path);
    if ($bytes === false) {
        throw new SharedFailure('Die Datei zu diesem Baustein fehlt auf dem Server.', 500, 'storage');
    }
    $database->prepare('UPDATE parts SET downloads = downloads + 1 WHERE id = ?')->execute([$id]);

    header('Content-Type: application/json; charset=utf-8');
    header('Content-Disposition: attachment; filename="' . $slug . '.json"');
    header('Content-Length: ' . strlen($bytes));
    echo $bytes;
    exit;
}

try {
    $action = (string) ($_GET['do'] ?? '');
    $post = ($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST';
    if ($action === 'upload' && $post) {
        shared_upload();
    } elseif ($action === 'confirm') {
        shared_confirm();
    } elseif ($action === 'list') {
        shared_list();
    } elseif ($action === 'download') {
        shared_download();
    } elseif ($action === 'withdraw') {
        shared_withdraw();
    } else {
        throw new SharedFailure(
            'Diese Anfrage kennt die Börse nicht. Möglich sind upload, confirm, list, '
            . 'download und withdraw.',
            404,
            'unknown_action'
        );
    }
} catch (SharedFailure $problem) {
    shared_answer_error($problem);
} catch (Throwable $error) {
    // Der Text einer unerwarteten Ausnahme geht nicht hinaus: Er nennt Pfade
    // und Zeilennummern des Servers.
    shared_answer(
        ['ok' => false, 'code' => 'server_error', 'error' => 'Die Börse hat einen Fehler auf dem Server.'],
        500
    );
}
