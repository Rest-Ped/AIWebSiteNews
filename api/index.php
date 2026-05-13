<?php

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
header('Access-Control-Allow-Methods: GET, POST, PUT, OPTIONS');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

$SOURCE_CATALOG = [
    'google-news' => ['label' => 'Google News', 'domain' => '', 'weight' => 0.4],
    'tass' => ['label' => 'ТАСС', 'domain' => 'tass.ru', 'weight' => 1.5],
    'rbc' => ['label' => 'РБК', 'domain' => 'rbc.ru', 'weight' => 1.4],
    'kommersant' => ['label' => 'Коммерсантъ', 'domain' => 'kommersant.ru', 'weight' => 1.3],
    'interfax' => ['label' => 'Интерфакс', 'domain' => 'interfax.ru', 'weight' => 1.5],
    'ria' => ['label' => 'РИА Новости', 'domain' => 'ria.ru', 'weight' => 1.2],
    'vedomosti' => ['label' => 'Ведомости', 'domain' => 'vedomosti.ru', 'weight' => 1.2],
    'habr' => ['label' => 'Habr', 'domain' => 'habr.com', 'weight' => 0.9],
    'vc' => ['label' => 'VC', 'domain' => 'vc.ru', 'weight' => 0.7],
    'techcrunch' => ['label' => 'TechCrunch', 'domain' => 'techcrunch.com', 'weight' => 1.0],
];

$HIGH_IMPACT_TERMS = ['срочно', 'важно', 'экстренно', 'закон', 'санкции', 'запрет', 'суд', 'угроза', 'кризис', 'утечка', 'уязвимость', 'атака', 'авария', 'взрыв', 'пожар', 'погибли', 'рост', 'падение', 'инвестиции', 'сделка', 'запуск', 'релиз', 'security', 'attack', 'crisis', 'ban', 'launch'];
$LOW_IMPACT_TERMS = ['мнение', 'колонка', 'слухи', 'подборка', 'дайджест', 'интервью', 'обзор', 'opinion', 'rumor', 'review'];
$GENERIC_TOPIC_TERMS = ['новости', 'новость', 'последние', 'свежие', 'сегодня', 'главное', 'лента', 'дня', 'news', 'latest', 'today'];

function respond_json($payload, $status = 200) {
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function request_json() {
    $data = json_decode(file_get_contents('php://input') ?: '{}', true);
    return is_array($data) ? $data : [];
}

function lower_text($value) {
    $value = (string)$value;
    return function_exists('mb_strtolower') ? mb_strtolower($value, 'UTF-8') : strtolower($value);
}

function clamp_int($value, $default = 6, $min = 1, $max = 10) {
    $number = filter_var($value, FILTER_VALIDATE_INT);
    if ($number === false) {
        $number = $default;
    }
    return max($min, min($max, (int)$number));
}

function threshold_from_user_or_data($user = null, $data = []) {
    if (is_array($data) && array_key_exists('threshold', $data)) {
        return clamp_int($data['threshold'], 6);
    }
    if (is_array($data) && array_key_exists('news_threshold', $data)) {
        return clamp_int($data['news_threshold'], 6);
    }
    if (isset($_GET['threshold'])) {
        return clamp_int($_GET['threshold'], 6);
    }
    if (is_array($user) && array_key_exists('news_threshold', $user)) {
        return clamp_int($user['news_threshold'], 6);
    }
    return 6;
}

function json_decode_list($value) {
    $decoded = json_decode((string)$value, true);
    return is_array($decoded) ? $decoded : [];
}

function user_public($user) {
    unset($user['password_hash']);
    $user['id'] = (int)$user['id'];
    $user['interests'] = json_decode_list($user['interests'] ?? '[]');
    $user['news_threshold'] = clamp_int($user['news_threshold'] ?? 6, 6);
    return $user;
}

function base64url_encode_value($value) {
    return rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
}

function base64url_decode_value($value) {
    $padding = strlen($value) % 4;
    if ($padding) {
        $value .= str_repeat('=', 4 - $padding);
    }
    return base64_decode(strtr($value, '-_', '+/'));
}

function make_token($user) {
    global $APP_CONFIG;
    $body = base64url_encode_value(json_encode(['id' => (int)$user['id'], 'time' => time()], JSON_UNESCAPED_UNICODE));
    return $body . '.' . hash_hmac('sha256', $body, $APP_CONFIG['secret']);
}

function bearer_token() {
    $header = $_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '';
    if (!$header && function_exists('getallheaders')) {
        $headers = getallheaders();
        $header = $headers['Authorization'] ?? $headers['authorization'] ?? '';
    }
    return stripos($header, 'Bearer ') === 0 ? trim(substr($header, 7)) : '';
}

function current_user($required = true) {
    global $APP_CONFIG;
    $token = bearer_token();
    if (!$token || strpos($token, '.') === false) {
        if ($required) respond_json(['error' => 'Нужен вход в аккаунт.'], 401);
        return null;
    }
    [$body, $signature] = explode('.', $token, 2);
    if (!hash_equals(hash_hmac('sha256', $body, $APP_CONFIG['secret']), $signature)) {
        if ($required) respond_json(['error' => 'Сессия недействительна.'], 401);
        return null;
    }
    $payload = json_decode(base64url_decode_value($body), true);
    $id = isset($payload['id']) ? (int)$payload['id'] : 0;
    $stmt = db()->prepare('SELECT * FROM users WHERE id = ?');
    $stmt->execute([$id]);
    $user = $stmt->fetch();
    if (!$user && $required) respond_json(['error' => 'Пользователь не найден.'], 401);
    return $user ?: null;
}

function normalize_interests($value) {
    $items = is_array($value) ? $value : preg_split('/\s*,\s*/u', (string)$value);
    $result = [];
    foreach ($items as $item) {
        $text = trim((string)$item);
        if ($text !== '' && !in_array($text, $result, true)) {
            $result[] = $text;
        }
    }
    return $result;
}

function route_path() {
    $route = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
    $base = str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME']));
    if ($base !== '/' && strpos($route, $base) === 0) {
        $route = substr($route, strlen($base));
    }
    $route = '/' . trim($route, '/');
    return ($route === '/' || $route === '/index.php') ? '/health' : $route;
}

function http_get_text($url, $headers = []) {
    $headers[] = 'User-Agent: Mozilla/5.0 (compatible; IDOSkillsNews/1.0)';
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_FOLLOWLOCATION => true, CURLOPT_TIMEOUT => 25, CURLOPT_HTTPHEADER => $headers]);
        $body = curl_exec($ch);
        curl_close($ch);
        return is_string($body) ? $body : '';
    }
    $context = stream_context_create(['http' => ['method' => 'GET', 'header' => implode("\r\n", $headers), 'timeout' => 25, 'ignore_errors' => true]]);
    $body = @file_get_contents($url, false, $context);
    return is_string($body) ? $body : '';
}

function http_post_json($url, $payload, $headers = []) {
    $body = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    $headers[] = 'Content-Type: application/json';
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 55, CURLOPT_POST => true, CURLOPT_POSTFIELDS => $body, CURLOPT_HTTPHEADER => $headers]);
        $response = curl_exec($ch);
        curl_close($ch);
        return is_string($response) ? $response : '';
    }
    $context = stream_context_create(['http' => ['method' => 'POST', 'header' => implode("\r\n", $headers), 'content' => $body, 'timeout' => 55, 'ignore_errors' => true]]);
    $response = @file_get_contents($url, false, $context);
    return is_string($response) ? $response : '';
}

function source_keys($sources) {
    global $SOURCE_CATALOG;
    $selected = [];
    foreach ((array)$sources as $value) {
        $key = lower_text(trim((string)$value));
        if (isset($SOURCE_CATALOG[$key]) && !in_array($key, $selected, true)) {
            $selected[] = $key;
        }
    }
    return $selected ?: ['google-news'];
}

function topic_terms($topic) {
    $parts = preg_split('/[\s,.;:!?()\[\]{}"\']+/u', lower_text($topic));
    return array_values(array_filter($parts, function ($part) {
        return (function_exists('mb_strlen') ? mb_strlen($part, 'UTF-8') : strlen($part)) > 1;
    }));
}

function relevance_terms($topic) {
    global $GENERIC_TOPIC_TERMS;
    return array_values(array_filter(topic_terms($topic), fn($term) => !in_array($term, $GENERIC_TOPIC_TERMS, true)));
}

function text_matches_topic($text, $topic) {
    $terms = relevance_terms($topic);
    if (!$terms) return true;
    $text = lower_text($text);
    foreach ($terms as $term) {
        if (strpos($text, $term) !== false) return true;
    }
    return false;
}

function global_query_for_topic($topic) {
    $lower = lower_text($topic);
    $extra = [];
    $map = [
        'искусственный интеллект' => 'artificial intelligence AI machine learning',
        'ии' => 'artificial intelligence AI',
        'технологии' => 'technology tech software hardware',
        'стартапы' => 'startups venture capital funding',
        'бизнес' => 'business companies markets',
        'экономика' => 'economy markets finance',
        'безопасность' => 'cybersecurity security data breach',
        'наука' => 'science research discovery',
        'образование' => 'education universities learning',
        'здоровье' => 'health medicine biotech',
        'мир' => 'world international global',
        'культура' => 'culture entertainment',
    ];

    foreach ($map as $ru => $en) {
        if (strpos($lower, $ru) !== false) {
            $extra[] = $en;
        }
    }

    return trim($topic . ' ' . implode(' ', $extra));
}

function fetch_google_news($topic, $sourceKey, $scope = 'mixed') {
    global $SOURCE_CATALOG;
    $domain = $SOURCE_CATALOG[$sourceKey]['domain'] ?? '';
    $query = $scope === 'global' ? global_query_for_topic(trim($topic) ?: 'news') : (trim($topic) ?: 'новости');
    $query .= $domain ? ' site:' . $domain . ' when:7d' : ' when:7d';

    $feeds = $scope === 'global'
        ? [
            ['hl' => 'en', 'gl' => 'US', 'ceid' => 'US:en'],
            ['hl' => 'en', 'gl' => 'GB', 'ceid' => 'GB:en'],
            ['hl' => 'ru', 'gl' => 'RU', 'ceid' => 'RU:ru'],
        ]
        : [
            ['hl' => 'ru', 'gl' => 'RU', 'ceid' => 'RU:ru'],
            ['hl' => 'en', 'gl' => 'US', 'ceid' => 'US:en'],
        ];

    $articles = [];
    foreach ($feeds as $feed) {
        $url = 'https://news.google.com/rss/search?q=' . rawurlencode($query)
            . '&hl=' . rawurlencode($feed['hl'])
            . '&gl=' . rawurlencode($feed['gl'])
            . '&ceid=' . rawurlencode($feed['ceid']);
        $xmlText = http_get_text($url);
        $xml = $xmlText ? @simplexml_load_string($xmlText) : null;
        if (!$xml || !isset($xml->channel->item)) continue;

        foreach ($xml->channel->item as $item) {
            $sourceName = isset($item->source) ? trim((string)$item->source) : 'Google News';
            $sourceUrl = isset($item->source) ? trim((string)$item->source['url']) : '';
            $title = html_entity_decode(trim((string)$item->title), ENT_QUOTES | ENT_HTML5, 'UTF-8');
            if ($sourceName && substr($title, -strlen(' - ' . $sourceName)) === ' - ' . $sourceName) {
                $title = trim(substr($title, 0, -strlen(' - ' . $sourceName)));
            }
            $article = ['title' => $title ?: 'Без заголовка', 'url' => trim((string)$item->link), 'source' => $sourceName, 'source_url' => $sourceUrl, 'summary' => '', 'published_at' => trim((string)$item->pubDate)];
            if ($article['url'] && ($scope === 'global' || text_matches_topic($article['title'] . ' ' . $article['source'] . ' ' . $article['source_url'], $topic))) {
                $articles[] = $article;
            }
        }
        if (count($articles) >= 12) break;
    }

    return unique_articles($articles, 12);
}

function unique_articles($articles, $limit = 12) {
    $seen = [];
    $result = [];
    foreach ($articles as $article) {
        $url = lower_text($article['url'] ?? '');
        if (!$url || isset($seen[$url])) continue;
        $seen[$url] = true;
        $result[] = $article;
        if (count($result) >= $limit) break;
    }
    return $result;
}

function build_raw_context($articles) {
    $lines = [];
    foreach ($articles as $index => $article) {
        $lines[] = ($index + 1) . '. Заголовок: ' . $article['title'];
        $lines[] = '   URL: ' . $article['url'];
        $lines[] = '   Источник: ' . $article['source'];
        $lines[] = '   Дата: ' . ($article['published_at'] ?? '');
    }
    return implode("\n", $lines);
}

function call_gemini($topic, $rawContext) {
    global $APP_CONFIG;
    $payload = [
        'model' => $APP_CONFIG['openrouter_model'],
        'messages' => [
            ['role' => 'system', 'content' => 'Ты редактор международной новостной ленты. Верни только валидный JSON-массив без markdown. Все title, summary и category обязательно на русском языке, даже если источник английский. Поля: title, summary, url, source, category, importance_score, published_at. importance_score оценивай строго по 10-балльной шкале: 10 = критически важно для большинства людей/рынка/безопасности, 7-9 = сильное влияние, 4-6 = обычная новость, 1-3 = низкая значимость. Не выдумывай факты, используй только предоставленные ссылки. Максимум 10 статей.'],
            ['role' => 'user', 'content' => "Тема запроса или интересы пользователя: {$topic}\nВыбери только явно релевантные новости со всего мира. Переведи заголовки и краткие описания на русский язык.\n\n{$rawContext}"],
        ],
        'temperature' => 0.15,
        'max_tokens' => 2400,
    ];
    $response = http_post_json(rtrim($APP_CONFIG['openrouter_base_url'], '/') . '/chat/completions', $payload, ['Authorization: Bearer ' . $APP_CONFIG['openrouter_api_key'], 'HTTP-Referer: ' . $APP_CONFIG['app_site_url'], 'X-Title: ' . $APP_CONFIG['app_title']]);
    $decoded = json_decode($response, true);
    $content = $decoded['choices'][0]['message']['content'] ?? '';
    if (!$content) return [];
    if (strpos($content, '```') !== false) {
        $content = preg_replace('/^```json\s*|\s*```$/iu', '', trim($content));
    }
    $start = strpos($content, '[');
    $end = strrpos($content, ']');
    if ($start !== false && $end !== false && $end > $start) {
        $content = substr($content, $start, $end - $start + 1);
    }
    $items = json_decode($content, true);
    return is_array($items) ? $items : [];
}

function source_weight($source, $url) {
    global $SOURCE_CATALOG;
    $host = lower_text(parse_url((string)$url, PHP_URL_HOST) ?: '');
    $sourceText = lower_text($source);
    $best = 0.0;
    foreach ($SOURCE_CATALOG as $meta) {
        $domain = lower_text($meta['domain'] ?? '');
        $label = lower_text($meta['label'] ?? '');
        if ($domain && (substr($host, -strlen($domain)) === $domain || strpos($sourceText, $domain) !== false)) $best = max($best, (float)$meta['weight']);
        if ($label && strpos($sourceText, $label) !== false) $best = max($best, (float)$meta['weight']);
    }
    return $best;
}

function calculate_importance($item, $topic) {
    global $HIGH_IMPACT_TERMS, $LOW_IMPACT_TERMS;
    $title = (string)($item['title'] ?? '');
    $summary = (string)($item['summary'] ?? '');
    $text = lower_text($title . ' ' . $summary);
    $modelScore = clamp_int($item['importance_score'] ?? 6, 6);
    $score = 1.6 + ($modelScore * 0.55) + (source_weight($item['source'] ?? '', $item['url'] ?? '') * 0.9);

    $published = strtotime((string)($item['published_at'] ?? ''));
    if ($published) {
        $hours = max(0, (time() - $published) / 3600);
        $score += $hours <= 2 ? 1.7 : ($hours <= 8 ? 1.35 : ($hours <= 24 ? 0.95 : ($hours <= 72 ? 0.45 : -0.35)));
    }

    $impactHits = 0;
    foreach ($HIGH_IMPACT_TERMS as $term) {
        if (strpos($text, $term) !== false) {
            $impactHits++;
        }
    }
    $score += min(1.8, $impactHits * 0.35);

    foreach ($LOW_IMPACT_TERMS as $term) if (strpos($text, $term) !== false) $score -= 0.35;

    $topicHits = 0;
    foreach (relevance_terms($topic) as $term) {
        if (strpos($text, $term) !== false) {
            $topicHits++;
        }
    }
    $score += min(1.4, $topicHits * 0.45);

    if ($modelScore >= 9 && $topicHits > 0) {
        $score += 0.8;
    }
    if (strlen($summary) > 180) $score += 0.25;

    return max(1, min(10, (int)round($score)));
}

function normalize_news_item($item, $topic, $strictTopic = true) {
    $url = trim((string)($item['url'] ?? ''));
    if (!$url) return null;
    $normalized = [
        'title' => trim((string)($item['title'] ?? 'Без заголовка')) ?: 'Без заголовка',
        'summary' => trim((string)($item['summary'] ?? '')),
        'url' => $url,
        'source' => trim((string)($item['source'] ?? 'Источник')),
        'category' => trim((string)($item['category'] ?? 'общество')),
        'published_at' => trim((string)($item['published_at'] ?? date(DATE_ATOM))),
        'importance_score' => 6,
    ];
    $normalized['importance_score'] = calculate_importance($item + $normalized, $topic);
    return (!$strictTopic || text_matches_topic($normalized['title'] . ' ' . $normalized['summary'] . ' ' . $normalized['source'] . ' ' . $normalized['url'], $topic)) ? $normalized : null;
}

function filter_items_by_threshold($items, $threshold) {
    return array_values(array_filter($items, fn($item) => (int)($item['importance_score'] ?? 0) >= $threshold));
}

function collect_global_news_for_interests($interests) {
    $interests = array_values(array_filter($interests, fn($item) => trim((string)$item) !== ''));
    if (!$interests) {
        $interests = ['искусственный интеллект', 'технологии', 'мировая экономика'];
    }

    $raw = [];
    foreach (array_slice($interests, 0, 4) as $interest) {
        foreach (fetch_google_news($interest, 'google-news', 'global') as $article) {
            $raw[] = $article;
        }
    }

    return unique_articles($raw, 18);
}

function refresh_personal_news($user) {
    $interests = json_decode_list($user['interests'] ?? '[]');
    $raw = collect_global_news_for_interests($interests);
    if (!$raw) {
        return 0;
    }

    $topic = implode(', ', $interests ?: ['мировые новости']);
    $processed = call_gemini($topic, build_raw_context($raw));
    $items = [];

    foreach ($processed as $item) {
        $normalized = normalize_news_item(is_array($item) ? $item : [], $topic, false);
        if ($normalized) {
            $items[] = $normalized;
        }
    }

    if (!$items) {
        foreach ($raw as $article) {
            $article['summary'] = 'Краткое описание недоступно, откройте источник для подробностей.';
            $normalized = normalize_news_item($article, $topic, false);
            if ($normalized) {
                $items[] = $normalized;
            }
        }
    }

    return $items ? save_news_items($items) : 0;
}

function db_datetime($value) {
    $ts = strtotime((string)$value);
    return $ts ? date('Y-m-d H:i:s', $ts) : date('Y-m-d H:i:s');
}

function save_news_items($items) {
    $pdo = db();
    $stmt = $pdo->prepare(
        'INSERT INTO news (title, summary, url, source, category, importance_score, published_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)
         ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            summary = CASE WHEN VALUES(summary) <> \'\' THEN VALUES(summary) ELSE summary END,
            source = VALUES(source),
            category = VALUES(category),
            importance_score = GREATEST(importance_score, VALUES(importance_score)),
            published_at = VALUES(published_at)'
    );
    $saved = 0;
    foreach ($items as $item) {
        $stmt->execute([$item['title'], $item['summary'], $item['url'], $item['source'], $item['category'], $item['importance_score'], db_datetime($item['published_at'])]);
        $saved += $stmt->rowCount() > 0 ? 1 : 0;
    }
    return $saved;
}

function serialize_news($row) {
    $row['id'] = (int)$row['id'];
    $row['importance_score'] = (int)$row['importance_score'];
    return $row;
}

function filtered_news_for_user($user, $autoRefresh = false, $thresholdOverride = null) {
    if ($autoRefresh) {
        refresh_personal_news($user);
    }

    $threshold = $thresholdOverride ? clamp_int($thresholdOverride, 6) : threshold_from_user_or_data($user);
    $stmt = db()->prepare('SELECT * FROM news WHERE importance_score >= ? ORDER BY importance_score DESC, published_at DESC LIMIT 100');
    $stmt->execute([$threshold]);
    $items = $stmt->fetchAll();
    $interests = json_decode_list($user['interests'] ?? '[]');
    if (!$interests) return array_map('serialize_news', array_slice($items, 0, 20));
    $filtered = [];
    foreach ($items as $item) {
        $haystack = ($item['title'] ?? '') . ' ' . ($item['summary'] ?? '') . ' ' . ($item['category'] ?? '');
        foreach ($interests as $interest) {
            if (text_matches_topic($haystack, $interest)) {
                $filtered[] = $item;
                break;
            }
        }
    }
    return array_map('serialize_news', array_slice($filtered, 0, 20));
}

function build_digest_text($user, $news) {
    global $APP_CONFIG;
    $interests = json_decode_list($user['interests'] ?? '[]');
    if (!$news) {
        return 'По вашим интересам и текущему порогу важности пока нет достаточно важных новостей. Попробуйте снизить важность или расширить интересы.';
    }

    $context = [];
    foreach (array_slice($news, 0, 8) as $index => $item) {
        $context[] = ($index + 1) . '. ' . ($item['title'] ?? 'Без заголовка')
            . ' | важность ' . ($item['importance_score'] ?? 6) . '/10'
            . ' | источник: ' . ($item['source'] ?? '-')
            . ' | ' . ($item['summary'] ?? '')
            . ' | URL: ' . ($item['url'] ?? '');
    }

    $payload = [
        'model' => $APP_CONFIG['openrouter_model'],
        'messages' => [
            ['role' => 'system', 'content' => 'Ты редактор персональной новостной сводки. Пиши только на русском. Сделай короткую, понятную сводку по интересам пользователя: сначала 3-5 главных пунктов, затем короткий вывод почему это важно. Не выдумывай факты.'],
            ['role' => 'user', 'content' => 'Интересы пользователя: ' . implode(', ', $interests) . "\nПорог важности: " . threshold_from_user_or_data($user) . "/10\nНовости:\n" . implode("\n", $context)],
        ],
        'temperature' => 0.2,
        'max_tokens' => 1200,
    ];

    $response = http_post_json(rtrim($APP_CONFIG['openrouter_base_url'], '/') . '/chat/completions', $payload, ['Authorization: Bearer ' . $APP_CONFIG['openrouter_api_key'], 'HTTP-Referer: ' . $APP_CONFIG['app_site_url'], 'X-Title: ' . $APP_CONFIG['app_title']]);
    $decoded = json_decode($response, true);
    $content = trim((string)($decoded['choices'][0]['message']['content'] ?? ''));
    if ($content !== '') {
        return $content;
    }

    $lines = ['IDO SKILLS NEWS DIGEST', 'Интересы: ' . implode(', ', $interests), ''];
    foreach (array_slice($news, 0, 5) as $index => $item) {
        $lines[] = ($index + 1) . '. ' . ($item['title'] ?? 'Без заголовка') . ' — важность ' . ($item['importance_score'] ?? 6) . '/10';
        if (!empty($item['summary'])) $lines[] = '   ' . $item['summary'];
    }
    return implode("\n", $lines);
}

function handle_register($data) {
    $login = trim((string)($data['login'] ?? $data['username'] ?? ''));
    $email = trim((string)($data['email'] ?? '')) ?: null;
    $password = (string)($data['password'] ?? '');
    if ($login === '') respond_json(['error' => 'Укажите логин.'], 400);
    if (strlen($password) < 6) respond_json(['error' => 'Пароль должен быть от 6 символов.'], 400);
    $stmt = db()->prepare('INSERT INTO users (login, email, password_hash, interests, news_threshold) VALUES (?, ?, ?, ?, ?)');
    try {
        $stmt->execute([$login, $email, password_hash($password, PASSWORD_DEFAULT), json_encode(normalize_interests($data['interests'] ?? []), JSON_UNESCAPED_UNICODE), clamp_int($data['threshold'] ?? 6, 6)]);
    } catch (Throwable $error) {
        respond_json(['error' => 'Такой логин или email уже есть.'], 409);
    }
    $user = db()->query('SELECT * FROM users WHERE id = LAST_INSERT_ID()')->fetch();
    respond_json(['message' => 'Аккаунт создан.', 'token' => make_token($user), 'user' => user_public($user)], 201);
}

function handle_login($data) {
    $identifier = trim((string)($data['login'] ?? $data['email'] ?? $data['username'] ?? ''));
    $stmt = db()->prepare('SELECT * FROM users WHERE LOWER(login) = LOWER(?) OR LOWER(email) = LOWER(?) LIMIT 1');
    $stmt->execute([$identifier, $identifier]);
    $user = $stmt->fetch();
    if ($user && password_verify((string)($data['password'] ?? ''), $user['password_hash'])) {
        respond_json(['message' => 'Вход выполнен.', 'token' => make_token($user), 'user' => user_public($user)]);
    }
    respond_json(['error' => 'Неверный логин или пароль.'], 401);
}

function handle_ai_news($data) {
    global $APP_CONFIG;
    $topic = trim((string)($data['topic'] ?? 'новости')) ?: 'новости';
    $threshold = threshold_from_user_or_data(null, $data);
    $raw = [];
    $sources = source_keys($data['sources'] ?? []);
    foreach ($sources as $source) {
        foreach (fetch_google_news($topic, $source, 'global') as $article) $raw[] = $article;
    }
    $raw = unique_articles($raw, 12);
    if (!$raw) respond_json(['error' => 'Не удалось найти релевантные новости в выбранных источниках.'], 503);
    $processed = call_gemini($topic, build_raw_context($raw));
    $items = [];
    foreach ($processed as $item) {
        $normalized = normalize_news_item(is_array($item) ? $item : [], $topic);
        if ($normalized) $items[] = $normalized;
    }
    if (!$items) {
        foreach ($raw as $article) {
            $article['summary'] = 'Краткое описание недоступно, откройте источник для подробностей.';
            $normalized = normalize_news_item($article, $topic);
            if ($normalized) $items[] = $normalized;
        }
    }
    usort($items, fn($a, $b) => (int)$b['importance_score'] <=> (int)$a['importance_score']);
    $saved = save_news_items($items);
    $allCount = count($items);
    $items = array_slice(filter_items_by_threshold($items, $threshold), 0, 10);
    respond_json(['news' => $items, 'saved' => $saved, 'total' => count($items), 'found_total' => $allCount, 'threshold' => $threshold, 'topic' => $topic, 'sources' => $sources, 'model' => $APP_CONFIG['openrouter_model']]);
}

$method = $_SERVER['REQUEST_METHOD'];
$route = route_path();
$data = request_json();

try {
    if ($method === 'GET' && $route === '/health') {
        $dbStatus = 'not_configured';
        if (db_config_is_ready()) {
            db()->query('SELECT 1');
            $dbStatus = 'ok';
        }
        respond_json(['status' => 'ok', 'backend' => 'php-infinityfree', 'database' => $dbStatus, 'model' => $APP_CONFIG['openrouter_model']]);
    }

    if ($method === 'POST' && ($route === '/auth/register' || $route === '/users')) handle_register($data);
    if ($method === 'POST' && $route === '/auth/login') handle_login($data);
    if ($method === 'GET' && $route === '/auth/me') respond_json(['user' => user_public(current_user(true))]);
    if ($method === 'POST' && $route === '/auth/logout') respond_json(['message' => 'Выход выполнен.']);

    if ($method === 'PUT' && $route === '/users/me/interests') {
        $user = current_user(true);
        $stmt = db()->prepare('UPDATE users SET interests = ?, news_threshold = ? WHERE id = ?');
        $stmt->execute([json_encode(normalize_interests($data['interests'] ?? []), JSON_UNESCAPED_UNICODE), clamp_int($data['threshold'] ?? 6, 6), (int)$user['id']]);
        $stmt = db()->prepare('SELECT * FROM users WHERE id = ?');
        $stmt->execute([(int)$user['id']]);
        respond_json(['message' => 'Интересы сохранены.', 'user' => user_public($stmt->fetch())]);
    }

    if ($method === 'POST' && $route === '/news/fetch') {
        $user = current_user(true);
        $threshold = threshold_from_user_or_data($user, $data);
        $news = filtered_news_for_user($user, true, $threshold);
        respond_json(['count' => count($news), 'news' => $news, 'threshold' => $threshold, 'user' => user_public($user)]);
    }

    if ($method === 'GET' && $route === '/users/me/digest') {
        $user = current_user(true);
        $threshold = threshold_from_user_or_data($user);
        $news = filtered_news_for_user($user, true, $threshold);
        respond_json(['digest' => build_digest_text($user, $news), 'news_count' => count($news), 'threshold' => $threshold]);
    }

    if ($method === 'GET' && $route === '/news') {
        $items = db()->query('SELECT * FROM news ORDER BY importance_score DESC, published_at DESC LIMIT 20')->fetchAll();
        respond_json(['items' => array_map('serialize_news', $items), 'total' => count($items), 'pages' => 1]);
    }

    if ($method === 'POST' && $route === '/ai-news') handle_ai_news($data);

    respond_json(['error' => 'Маршрут не найден: ' . $route], 404);
} catch (Throwable $error) {
    respond_json(['error' => $error->getMessage()], 500);
}
