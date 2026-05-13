<?php

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';

header('Content-Type: text/html; charset=utf-8');

function e($value) {
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

try {
    db_install_schema();
    $pdo = db();
    $tables = $pdo->query("SHOW TABLES")->fetchAll(PDO::FETCH_COLUMN);
    $ok = true;
    $message = 'База данных подключена, таблицы созданы.';
} catch (Throwable $error) {
    $ok = false;
    $tables = [];
    $message = $error->getMessage();
}
?>
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>IDO SKILLS News installer</title>
    <style>
        body { margin: 0; font-family: Arial, sans-serif; background: #0b0c0f; color: #eef6f8; }
        main { max-width: 760px; margin: 8vh auto; padding: 32px; }
        .card { border: 1px solid #263238; border-radius: 24px; padding: 28px; background: #11151a; }
        h1 { margin-top: 0; }
        code { color: #9eeaf4; }
        .ok { color: #91f0b7; }
        .bad { color: #ffb3b8; }
        li { margin: 8px 0; }
    </style>
</head>
<body>
<main>
    <section class="card">
        <h1>IDO SKILLS News: установка БД</h1>
        <p class="<?= $ok ? 'ok' : 'bad' ?>"><?= e($message) ?></p>

        <?php if ($ok): ?>
            <p>Созданные/доступные таблицы:</p>
            <ul>
                <?php foreach ($tables as $table): ?>
                    <li><code><?= e($table) ?></code></li>
                <?php endforeach; ?>
            </ul>
            <p>Теперь открой <code>/api/health</code>. Если там <code>"database":"ok"</code>, можно тестировать сайт.</p>
            <p><strong>Важно:</strong> после проверки удали файл <code>api/install.php</code> с хостинга.</p>
        <?php else: ?>
            <p>Проверь в <code>api/config.php</code>:</p>
            <ul>
                <li><code>db_host</code> = hostname из InfinityFree</li>
                <li><code>db_name</code> = полное имя базы, например <code>if0_41867565_idoskillsnews</code></li>
                <li><code>db_user</code> = <code>if0_41867565</code></li>
                <li><code>db_password</code> = пароль MySQL из панели</li>
            </ul>
        <?php endif; ?>
    </section>
</main>
</body>
</html>
