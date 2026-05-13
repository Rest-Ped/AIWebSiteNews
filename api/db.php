<?php

function db_config_is_ready() {
    global $APP_CONFIG;
    return !empty($APP_CONFIG['db_host'])
        && !empty($APP_CONFIG['db_name'])
        && !empty($APP_CONFIG['db_user'])
        && !empty($APP_CONFIG['db_password'])
        && strpos($APP_CONFIG['db_name'], 'XXX') === false
        && strpos($APP_CONFIG['db_password'], 'PASTE_') === false;
}

function db_config_problem() {
    global $APP_CONFIG;

    if (empty($APP_CONFIG['db_host'])) {
        return 'Не указан db_host в api/config.php.';
    }
    if (empty($APP_CONFIG['db_name']) || strpos($APP_CONFIG['db_name'], 'XXX') !== false) {
        return 'Не указано реальное имя базы db_name. Нужно имя из списка MySQL Databases, например if0_41867565_base.';
    }
    if (empty($APP_CONFIG['db_user'])) {
        return 'Не указан db_user в api/config.php.';
    }
    if (empty($APP_CONFIG['db_password']) || strpos($APP_CONFIG['db_password'], 'PASTE_') !== false) {
        return 'Не указан db_password в api/config.php.';
    }
    return '';
}

function db() {
    static $pdo = null;
    global $APP_CONFIG;

    if ($pdo instanceof PDO) {
        return $pdo;
    }

    if (!db_config_is_ready()) {
        $problem = db_config_problem();
        throw new RuntimeException($problem ?: 'База данных не настроена. Заполните api/config.php.');
    }

    $dsn = sprintf(
        'mysql:host=%s;port=%s;dbname=%s;charset=utf8mb4',
        $APP_CONFIG['db_host'],
        $APP_CONFIG['db_port'] ?? 3306,
        $APP_CONFIG['db_name']
    );

    $pdo = new PDO($dsn, $APP_CONFIG['db_user'], $APP_CONFIG['db_password'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);

    return $pdo;
}

function db_install_schema() {
    $pdo = db();

    $pdo->exec("
        CREATE TABLE IF NOT EXISTS users (
            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            login VARCHAR(80) NOT NULL UNIQUE,
            email VARCHAR(160) NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            interests TEXT NULL,
            news_threshold TINYINT UNSIGNED NOT NULL DEFAULT 6,
            telegram_id BIGINT NULL UNIQUE,
            telegram_username VARCHAR(120) NULL,
            telegram_chat_id BIGINT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    ");

    $pdo->exec("
        CREATE TABLE IF NOT EXISTS news (
            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            summary TEXT NULL,
            url VARCHAR(900) NOT NULL UNIQUE,
            source VARCHAR(200) NULL,
            category VARCHAR(80) NULL,
            importance_score TINYINT UNSIGNED NOT NULL DEFAULT 6,
            published_at DATETIME NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_news_score (importance_score),
            INDEX idx_news_published (published_at)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    ");

    $pdo->exec("
        CREATE TABLE IF NOT EXISTS user_news (
            user_id INT UNSIGNED NOT NULL,
            news_id INT UNSIGNED NOT NULL,
            is_read TINYINT(1) NOT NULL DEFAULT 0,
            is_bookmarked TINYINT(1) NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, news_id),
            CONSTRAINT fk_user_news_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT fk_user_news_news FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    ");

    return true;
}
