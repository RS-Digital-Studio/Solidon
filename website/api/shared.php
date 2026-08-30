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
        throw new SharedFailure(shared_text('upload_no_file'));
    }
    $file = $_FILES['recipe'];
    if (($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
        // `post_max_size` schlägt zu, bevor PHP die Felder füllt — dann steht
        // hier ein Fehlercode und kein Hinweis auf die Ursache.
        throw new SharedFailure(
            shared_text('upload_incomplete')
        );
    }
    if (($file['size'] ?? 0) > $rules['max_upload_bytes']) {
        throw new SharedFailure(
            shared_text('upload_too_large', [
                'size' => (int) $file['size'],
                'limit' => (int) $rules['max_upload_bytes'],
            ]),
            413,
            'too_large'
        );
    }
    $bytes = @file_get_contents($file['tmp_name']);
    if ($bytes === false) {
        throw new SharedFailure(shared_text('upload_unreadable'));
    }
    return $bytes;
}

/** Eine Mailadresse, die wenigstens die Form hat. */
function shared_contact(): string
{
    $address = trim((string) ($_POST['contact'] ?? ''));
    if ($address === '' || filter_var($address, FILTER_VALIDATE_EMAIL) === false) {
        throw new SharedFailure(
            shared_text('upload_needs_address')
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
            shared_text('upload_not_a_recipe'),
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
            shared_text('upload_too_many_today'),
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
            throw new SharedFailure(shared_text('upload_store_failed'), 500, 'storage');
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
        'message' => shared_text('upload_accepted'),
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
    // **Beide Links in einer Mail, und der zweite ohne Ablauf.** Wer
    // zurückziehen will, soll das nicht bei uns beantragen müssen; die Zusage
    // steht in datenschutz.html und lautet „jederzeit selbst".
    $body = shared_mail_body('mail_upload_body', [
        'title' => $title,
        'link' => $link,
        'hours' => SHARED_CONFIRM_HOURS,
        'withdraw' => $back,
    ]);
    $headers = 'From: ' . SHARED_SENDER . "\r\n"
        . "Content-Type: text/plain; charset=utf-8\r\n"
        . 'Content-Transfer-Encoding: 8bit';
    if (!@mail($address, '=?UTF-8?B?' . base64_encode(shared_text('mail_upload_subject')) . '?=', $body, $headers)) {
        throw new SharedFailure(
            shared_text('upload_mail_failed'),
            500,
            'mail_failed'
        );
    }
}

/**
 * Ein Mailtext aus der Satzliste, mit Zeilenenden nach RFC 5322.
 *
 * **Die Satzliste trägt einfache Umbrüche, eine Mail braucht `CRLF`.** Der
 * Unterschied ist unsichtbar und folgenreich: Ein Text mit reinen `\n` kommt
 * bei manchen Empfängern als eine einzige lange Zeile an, bei anderen gar
 * nicht. Er wird deshalb hier umgesetzt, an einer Stelle — im Quellmodul
 * stünde `\r\n` im übersetzten Satz und jeder Übersetzer müsste daran denken.
 */
function shared_mail_body(string $key, array $values = []): string
{
    return str_replace("\n", "\r\n", shared_text($key, $values));
}

/** Der Klick aus der Mail: ab jetzt ist der Baustein öffentlich. */
function shared_confirm(): void
{
    $token = (string) ($_GET['token'] ?? '');
    if ($token === '' || preg_match('/^[0-9a-f]{32}$/D', $token) !== 1) {
        throw new SharedFailure(shared_text('confirm_incomplete'), 400, 'bad_token');
    }
    $database = shared_database();
    $row = $database->prepare('SELECT part_id, expires FROM pending WHERE token = ?');
    $row->execute([$token]);
    $found = $row->fetch();
    if (!$found) {
        throw new SharedFailure(
            shared_text('confirm_unknown'),
            404,
            'unknown_token'
        );
    }
    if ((int) $found['expires'] < time()) {
        throw new SharedFailure(
            shared_text('confirm_expired'),
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
        'message' => shared_text('confirm_done'),
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
            shared_text('withdraw_incomplete'),
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
            'message' => shared_text('withdraw_part_done'),
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
            'message' => shared_text('withdraw_comment_done'),
        ]);
    }

    throw new SharedFailure(
        shared_text('withdraw_unknown'),
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

/**
 * Die Kennung eines Baustein-Datensatzes zu seinem Kurznamen.
 *
 * Veröffentlicht und nicht verborgen — wer einen zurückgezogenen oder noch
 * unbestätigten Baustein liked oder kommentiert, liked ins Leere. Die Prüfung
 * steht hier und nicht in jedem Aufrufer: Sie ist dieselbe Frage, und eine
 * zweite Formulierung wäre eine zweite Gelegenheit, auseinanderzulaufen.
 */
function shared_part_id(string $slug): int
{
    if ($slug === '' || preg_match('/^[a-z0-9-]{1,80}$/D', $slug) !== 1) {
        throw new SharedFailure(shared_text('part_unknown'), 404, 'unknown');
    }
    $row = shared_database()->prepare(
        'SELECT id FROM parts WHERE slug = ? AND published IS NOT NULL AND hidden = 0'
    );
    $row->execute([$slug]);
    $id = $row->fetchColumn();
    if ($id === false) {
        throw new SharedFailure(shared_text('part_unknown'), 404, 'unknown');
    }
    return (int) $id;
}

/**
 * Die Browser-Kennung aus dem Formular.
 *
 * Der Datenschutztext beschreibt genau, was sie ist: „eine zufällige Kennung
 * im lokalen Speicher Ihres Browsers", die „keine Angaben über Sie enthält".
 * Der Server prüft deshalb nur die **Gestalt** und nie den Inhalt — er darf
 * gar nicht wissen, was darin steht, und eine Kennung, die er nicht versteht,
 * ist ihm so recht wie eine, die er versteht.
 *
 * Die Untergrenze ist kein Schönheitsmaß: Wer acht Zeichen schickt, teilt
 * sich seine Kennung mit anderen, und dann zählt ein Like fremde Klicks mit.
 */
function shared_browser_mark(): string
{
    $mark = trim((string) ($_POST['browser'] ?? ''));
    if (preg_match('/^[A-Za-z0-9_-]{16,64}$/D', $mark) !== 1) {
        throw new SharedFailure(
            shared_text('like_bad_browser_key'),
            400,
            'bad_browser'
        );
    }
    return $mark;
}

/**
 * Ein Like: ein Klick je Browser-Kennung und Baustein.
 *
 * **Die Eindeutigkeit steht im Index, nicht in einer Abfrage davor** — zwei
 * gleichzeitige Klicks gewinnen sonst beide. `INSERT OR IGNORE` lässt den
 * zweiten stillschweigend fallen, und genau das ist die Zusage aus
 * `datenschutz.html`: „ein Like je Browser und Baustein".
 *
 * Zurück kommt die **Zahl danach** und nicht ein bloßes ok. Wer nur „ok"
 * bekommt, muss die Liste neu laden, um zu sehen, was sein Klick bewirkt hat —
 * und im häufigsten Fall (der zweite Klick derselben Kennung) bewirkt er
 * nichts, was die Seite ohne die Zahl nicht sagen könnte.
 */
function shared_like(): void
{
    $id = shared_part_id((string) ($_POST['slug'] ?? ''));
    $mark = shared_browser_mark();
    $database = shared_database();
    $database->prepare(
        'INSERT OR IGNORE INTO likes (part_id, browser, created) VALUES (?, ?, ?)'
    )->execute([$id, $mark, time()]);

    $count = $database->prepare('SELECT COUNT(*) FROM likes WHERE part_id = ?');
    $count->execute([$id]);
    shared_answer(['ok' => true, 'likes' => (int) $count->fetchColumn()]);
}

/**
 * Die Kommentare eines Bausteins — was öffentlich steht und sonst nichts.
 *
 * Die Spaltenliste ist **aufgezählt und nicht `*`**, und das ist hier keine
 * Stilfrage: `comments` trägt `contact_hash`, `withdraw_key` und
 * `confirm_token`. Ein `SELECT *` reichte alle drei an die Seite durch —
 * den Rückziehschlüssel eines fremden Kommentars an jeden Leser.
 */
function shared_comments(): void
{
    $id = shared_part_id((string) ($_GET['slug'] ?? ''));
    $rows = shared_database()->prepare(
        'SELECT id, body, author, published FROM comments
          WHERE part_id = ? AND published IS NOT NULL AND hidden = 0
          ORDER BY published ASC'
    );
    $rows->execute([$id]);
    shared_answer(['ok' => true, 'comments' => $rows->fetchAll()]);
}

/**
 * Ein Kommentar wird eingereicht — sichtbar wird er erst nach dem Mailklick.
 *
 * Dieselbe Hürde wie beim Baustein und aus demselben Grund: Ohne sie kostet
 * ein Kommentar nichts, und was nichts kostet, kommt in Mengen. Die Adresse
 * wird **nicht** im Klartext abgelegt (`shared_contact_hash`), sie ist der
 * Weg für die Bestätigung und danach nur noch ein Merkmal, an dem sich
 * Doppeleinreichungen zählen lassen.
 *
 * Der Rückziehschlüssel entsteht **hier** und nicht beim Bestätigen: Er steht
 * in derselben Mail wie der Bestätigungslink, und wer den Kommentar doch
 * nicht will, soll ihn wegwerfen können, ohne ihn vorher veröffentlicht zu
 * haben.
 */
function shared_comment(): void
{
    $id = shared_part_id((string) ($_POST['slug'] ?? ''));
    $contact = shared_contact();
    $rules = shared_rules();

    $body = trim((string) ($_POST['body'] ?? ''));
    $author = trim((string) ($_POST['author'] ?? ''));
    $findings = [];
    if ($body === '') {
        $findings[] = shared_text('comment_empty');
    }
    if (mb_strlen($body) > $rules['max_doc_chars']) {
        $findings[] = shared_text('comment_too_long', ['limit' => $rules['max_doc_chars']]);
    }
    if (preg_match(FORBIDDEN_TEXT, $body) === 1) {
        $findings[] = shared_text('comment_has_markup');
    }
    if (mb_strlen($author) > $rules['max_title_chars']) {
        $findings[] = shared_text(
            'comment_name_too_long',
            ['limit' => $rules['max_title_chars']]
        );
    }
    // Ein Name darf nennen, wo man jemanden findet — eine Auszeichnung darf er
    // nicht einschleusen. Dieselbe Trennung wie im Kern (FORBIDDEN_MARKUP).
    if (preg_match(FORBIDDEN_MARKUP, $author) === 1) {
        $findings[] = shared_text('comment_name_has_markup');
    }
    if ($findings !== []) {
        throw new SharedFailure(implode(' ', $findings), 400, 'rejected');
    }

    $now = time();
    $token = shared_token();
    $withdraw = shared_token(32);
    shared_database()->prepare(
        'INSERT INTO comments (part_id, body, author, contact_hash, withdraw_key,
                               confirm_token, confirm_expires, created)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    )->execute([
        $id,
        $body,
        $author,
        shared_contact_hash($contact),
        $withdraw,
        $token,
        $now + SHARED_CONFIRM_HOURS * 3600,
        $now,
    ]);

    shared_send_comment_confirmation($contact, $token, $withdraw);
    shared_answer(['ok' => true, 'pending' => true]);
}

/** Die Mail zum Kommentar: der Bestätigungslink und der Rückzieh-Link. */
function shared_send_comment_confirmation(
    string $address,
    string $token,
    string $withdraw
): void {
    $host = $_SERVER['HTTP_HOST'] ?? 'solidon3d.de';
    $link = 'https://' . $host . '/api/shared.php?do=confirm_comment&token=' . urlencode($token);
    $back = 'https://' . $host . '/api/shared.php?do=withdraw&key=' . urlencode($withdraw);
    $body = shared_mail_body('mail_comment_body', [
        'link' => $link,
        'hours' => SHARED_CONFIRM_HOURS,
        'withdraw' => $back,
    ]);
    $headers = 'From: ' . SHARED_SENDER . "
" . 'Content-Type: text/plain; charset=utf-8';
    if (!@mail($address, shared_text('mail_comment_subject'), $body, $headers)) {
        throw new SharedFailure(
            shared_text('comment_mail_failed'),
            500,
            'mail_failed'
        );
    }
}

/**
 * Der Klick aus der Mail: ab jetzt steht der Kommentar da.
 *
 * **Verglichen wird in konstanter Zeit.** Die Zeile wird über den Schlüssel
 * geholt und der gefundene Wert danach mit `hash_equals` geprüft — ein `=`
 * allein antwortet unterschiedlich schnell, je nachdem, wie viele Zeichen
 * stimmen. Dieselbe Bauart wie beim Rückziehweg.
 *
 * Die Marke bleibt nach dem Klick stehen und wird nicht geleert: Wer denselben
 * Link zweimal anklickt, soll dieselbe Antwort bekommen und nicht „kennt die
 * Börse nicht" — der zweite Klick ist der häufigste Fall überhaupt, wenn
 * jemand die Mail wiederfindet.
 */
function shared_confirm_comment(): void
{
    $token = (string) ($_GET['token'] ?? '');
    if ($token === '' || preg_match('/^[0-9a-f]{32}$/D', $token) !== 1) {
        throw new SharedFailure(shared_text('confirm_incomplete'), 400, 'bad_token');
    }
    $database = shared_database();
    $row = $database->prepare(
        'SELECT id, confirm_token, confirm_expires, published FROM comments WHERE confirm_token = ?'
    );
    $row->execute([$token]);
    $found = $row->fetch();
    if (!$found || !hash_equals((string) $found['confirm_token'], $token)) {
        throw new SharedFailure(
            shared_text('comment_confirm_unknown'),
            404,
            'unknown_token'
        );
    }
    if ($found['published'] !== null) {
        shared_answer(['ok' => true, 'already' => true]);
    }
    if ((int) $found['confirm_expires'] < time()) {
        throw new SharedFailure(
            shared_text('comment_confirm_expired'),
            410,
            'expired'
        );
    }
    $database->prepare('UPDATE comments SET published = ? WHERE id = ?')
        ->execute([time(), (int) $found['id']]);
    shared_answer(['ok' => true]);
}

/** Die Rezeptdatei selbst — das Einzige, was nicht JSON antwortet. */
function shared_download(): void
{
    $slug = (string) ($_GET['slug'] ?? '');
    if ($slug === '' || preg_match('/^[a-z0-9-]{1,80}$/D', $slug) !== 1) {
        throw new SharedFailure(shared_text('part_unknown'), 404, 'unknown');
    }
    $database = shared_database();
    $row = $database->prepare(
        'SELECT id FROM parts WHERE slug = ? AND published IS NOT NULL AND hidden = 0'
    );
    $row->execute([$slug]);
    $id = $row->fetchColumn();
    if ($id === false) {
        throw new SharedFailure(shared_text('part_unknown'), 404, 'unknown');
    }

    $path = shared_file_for((int) $id);
    $bytes = @file_get_contents($path);
    if ($bytes === false) {
        throw new SharedFailure(shared_text('part_file_missing'), 500, 'storage');
    }
    $database->prepare('UPDATE parts SET downloads = downloads + 1 WHERE id = ?')->execute([$id]);

    header('Content-Type: application/json; charset=utf-8');
    header('Content-Disposition: attachment; filename="' . $slug . '.json"');
    header('Content-Length: ' . strlen($bytes));
    echo $bytes;
    exit;
}

try {
    // Jeder Aufruf räumt zuerst weg, was seine Frist überschritten hat
    // (siehe shared_sweep_unconfirmed) — es gibt keinen Zeitgeber, der es täte.
    shared_sweep_unconfirmed(shared_database());
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
    } elseif ($action === 'like' && $post) {
        shared_like();
    } elseif ($action === 'comments') {
        shared_comments();
    } elseif ($action === 'comment' && $post) {
        shared_comment();
    } elseif ($action === 'confirm_comment') {
        shared_confirm_comment();
    } else {
        throw new SharedFailure(
            shared_text('unknown_action'),
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
        ['ok' => false, 'code' => 'server_error', 'error' => shared_text('server_error')],
        500
    );
}
