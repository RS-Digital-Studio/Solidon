<?php
/**
 * Ausschließlich vom lokalen Support-Werkzeug gerufene Lizenzverwaltung.
 *
 * Der zufällige Betreiber-Token liegt neben der Aktivierungsdatenbank außerhalb
 * von httpdocs. Die Oberfläche sendet nur eine Lizenzkennung, nie das private
 * Schlüsselarchiv. Jede Änderung bekommt einen festen Anlass und einen
 * Audit-Eintrag ohne Namen, E-Mail-Adresse oder Freitext.
 */

declare(strict_types=1);

require_once __DIR__ . '/activation_common.php';

header('Content-Type: application/json; charset=utf-8');
activation_security_headers();

const OPERATOR_ACTIONS = ['lookup', 'block', 'unblock', 'release', 'reset_attempts'];
const OPERATOR_REASONS = [
    'support_device_change',
    'refund',
    'suspected_abuse',
    'correction',
    'data_request',
    'other',
];

/** Liest den Betreiber-Token, ohne seinen Wert in eine Antwort zu übernehmen. */
function operator_expected_token(): string
{
    $path = activation_data_path(
        'SOLIDON_ACTIVATION_OPERATOR_TOKEN_FILE',
        'operator.token'
    );
    activation_require_private_file($path);
    $text = file_get_contents($path);
    $token = $text === false ? '' : trim($text);
    if (preg_match('/^[0-9a-f]{64}$/D', $token) !== 1) {
        throw new ActivationFailure(
            'Die private Support-Verwaltung ist noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    return $token;
}

/** Nimmt den Header auf Apache/FastCGI und im lokalen PHP-Prüfstand an. */
function operator_given_token(): string
{
    $authorization = (string) (
        $_SERVER['HTTP_AUTHORIZATION']
        ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION']
        ?? ''
    );
    if (preg_match('/^Bearer ([0-9a-f]{64})$/D', trim($authorization), $match) === 1) {
        return $match[1];
    }
    return trim((string) ($_SERVER['HTTP_X_SOLIDON_OPERATOR_TOKEN'] ?? ''));
}

/** Hält jeden Lese- und Schreibweg hinter demselben 256-Bit-Geheimnis. */
function operator_authenticate(): void
{
    $expected = operator_expected_token();
    $given = operator_given_token();
    if (preg_match('/^[0-9a-f]{64}$/D', $given) !== 1 || !hash_equals($expected, $given)) {
        throw new ActivationFailure(
            'Der Zugang zur privaten Support-Verwaltung wurde abgelehnt.',
            403,
            'operator_forbidden'
        );
    }
}

/** Liest eine kleine JSON-Anforderung mit fester Obergrenze. */
function operator_request_body(): string
{
    return activation_read_json_body(16384);
}

/** Prüft die kleine JSON-Anforderung nach erfolgreicher Anmeldung. */
function operator_request(string $raw): array
{
    try {
        $request = json_decode($raw, true, 16, JSON_THROW_ON_ERROR);
    } catch (JsonException $problem) {
        throw new ActivationFailure('Die Support-Anforderung ist kein vollständiges JSON.');
    }
    if (!is_array($request)) {
        throw new ActivationFailure('Die Support-Anforderung hat den falschen Aufbau.');
    }
    $action = (string) ($request['action'] ?? '');
    $digest = strtolower(trim((string) ($request['digest'] ?? '')));
    $reason = (string) ($request['reason'] ?? '');
    if (!in_array($action, OPERATOR_ACTIONS, true)) {
        throw new ActivationFailure('Die angeforderte Support-Handlung ist unbekannt.');
    }
    $expectedKeys = $action === 'lookup'
        ? ['action', 'digest']
        : ['action', 'digest', 'reason'];
    if (!activation_has_exact_keys($request, $expectedKeys)) {
        throw new ActivationFailure('Die Support-Anforderung enthält unerwartete Felder.');
    }
    if (preg_match('/^[0-9a-f]{64}$/D', $digest) !== 1) {
        throw new ActivationFailure('Die Lizenzkennung ist nicht verwendbar.');
    }
    if ($action !== 'lookup' && !in_array($reason, OPERATOR_REASONS, true)) {
        throw new ActivationFailure('Für die Änderung fehlt ein benannter Support-Anlass.');
    }
    return ['action' => $action, 'digest' => $digest, 'reason' => $reason];
}

/** Der vollständige Support-Blick auf genau eine pseudonyme Lizenzkennung. */
function operator_state(PDO $database, string $digest): array
{
    $licence = $database->prepare(
        'SELECT status, created_at FROM licences WHERE digest = ?'
    );
    $licence->execute([$digest]);
    $licenceRow = $licence->fetch();

    $activations = $database->prepare(
        'SELECT id, device_name, activated_on, deactivated_at FROM activations '
        . 'WHERE licence_digest = ? ORDER BY activated_on DESC, id DESC'
    );
    $activations->execute([$digest]);
    $activationRows = [];
    foreach ($activations->fetchAll() as $row) {
        $activationRows[] = [
            'id' => (string) $row['id'],
            'device_name' => (string) $row['device_name'],
            'activated_on' => (string) $row['activated_on'],
            'deactivated_at' => $row['deactivated_at'] === null
                ? null
                : (string) $row['deactivated_at'],
            'active' => $row['deactivated_at'] === null,
        ];
    }

    $attempts = $database->prepare(
        'SELECT day, attempts FROM activation_attempts '
        . 'WHERE licence_digest = ? ORDER BY day DESC LIMIT 31'
    );
    $attempts->execute([$digest]);

    $events = $database->prepare(
        'SELECT occurred_at, action, reason, changed FROM operator_events '
        . 'WHERE licence_digest = ? ORDER BY id DESC LIMIT 100'
    );
    $events->execute([$digest]);
    $eventRows = [];
    foreach ($events->fetchAll() as $row) {
        $eventRows[] = [
            'occurred_at' => (string) $row['occurred_at'],
            'action' => (string) $row['action'],
            'reason' => (string) $row['reason'],
            'changed' => (bool) $row['changed'],
        ];
    }

    return [
        'ok' => true,
        'licence' => [
            'digest' => $digest,
            'status' => $licenceRow === false ? 'unknown' : (string) $licenceRow['status'],
            'created_at' => $licenceRow === false ? null : (string) $licenceRow['created_at'],
        ],
        'activations' => $activationRows,
        'attempts' => array_map(
            static fn(array $row): array => [
                'day' => (string) $row['day'],
                'attempts' => (int) $row['attempts'],
            ],
            $attempts->fetchAll()
        ),
        'events' => $eventRows,
    ];
}

/** Führt eine Änderung und ihren Audit-Eintrag in derselben Transaktion aus. */
function operator_change(PDO $database, array $request): bool
{
    $action = $request['action'];
    $digest = $request['digest'];
    $changed = false;
    $database->exec('BEGIN IMMEDIATE');
    try {
        if ($action === 'block' || $action === 'unblock') {
            $wanted = $action === 'block' ? 'blocked' : 'active';
            $insert = $database->prepare(
                'INSERT OR IGNORE INTO licences(digest, status, created_at) VALUES(?, ?, ?)'
            );
            $insert->execute([$digest, $wanted, gmdate('c')]);
            $update = $database->prepare(
                'UPDATE licences SET status = ? WHERE digest = ? AND status <> ?'
            );
            $update->execute([$wanted, $digest, $wanted]);
            $changed = $insert->rowCount() > 0 || $update->rowCount() > 0;
        } elseif ($action === 'release') {
            $update = $database->prepare(
                'UPDATE activations SET deactivated_at = ? '
                . 'WHERE licence_digest = ? AND deactivated_at IS NULL'
            );
            $update->execute([gmdate('c'), $digest]);
            $changed = $update->rowCount() > 0;
        } elseif ($action === 'reset_attempts') {
            $delete = $database->prepare(
                'DELETE FROM activation_attempts WHERE licence_digest = ?'
            );
            $delete->execute([$digest]);
            $changed = $delete->rowCount() > 0;
        }
        $event = $database->prepare(
            'INSERT INTO operator_events('
            . 'occurred_at, licence_digest, action, reason, changed) VALUES(?, ?, ?, ?, ?)'
        );
        $event->execute([
            gmdate('c'),
            $digest,
            $action,
            $request['reason'],
            $changed ? 1 : 0,
        ]);
        activation_commit($database);
    } catch (Throwable $problem) {
        activation_rollback($database);
        throw $problem;
    }
    return $changed;
}

try {
    activation_require_method('POST');
    activation_require_trusted_origin();
    activation_require_json_headers(16384);
    activation_consume_client_rate('operator', 30, 900);
    operator_authenticate();
    $request = operator_request(operator_request_body());
    $database = activation_database();
    $changed = null;
    if ($request['action'] !== 'lookup') {
        $changed = operator_change($database, $request);
    }
    $answer = operator_state($database, $request['digest']);
    if ($changed !== null) {
        $answer['changed'] = $changed;
    }
    echo json_encode($answer, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
} catch (ActivationFailure $problem) {
    activation_answer_error($problem);
} catch (Throwable $problem) {
    activation_answer_error(new ActivationFailure(
        'Die private Support-Verwaltung konnte die Handlung nicht abschließen. '
        . 'Datenbank und Serverprotokoll prüfen.',
        503,
        'service_unavailable'
    ));
}
