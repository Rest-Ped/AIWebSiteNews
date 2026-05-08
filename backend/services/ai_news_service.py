"""AI News Service — получает свежие новости, обрабатывает Gemini 2.0 и сохраняет в БД."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import quote, urlparse

import requests

from config import config


HTTP_TIMEOUT = 15

# Допустимые категории — Gemini выбирает одну из них
ALLOWED_CATEGORIES = {
    "технологии", "политика", "бизнес", "спорт", "наука",
    "здоровье", "развлечения", "мир", "образование",
    "безопасность", "стартапы", "экономика", "общество",
}

NEWS_SYSTEM_PROMPT = (
    "Ты агрегатор новостей. Тебе дают сырые заголовки и ссылки из RSS-лент "
    "и поисковых систем.\n\n"
    "ЗАДАЧА: верни ТОЛЬКО валидный JSON-массив обработанных новостей. "
    "Никакого markdown, никаких пояснений — только JSON.\n\n"
    "Для каждой статьи выдай объект с полями:\n"
    "  title        — заголовок на русском (оригинальный или переведённый)\n"
    "  summary      — краткое изложение 2-3 предложения на русском\n"
    "  url          — ссылка на оригинал (не меняй)\n"
    "  source       — название источника\n"
    "  category     — одна категория из списка: "
    "технологии, политика, бизнес, спорт, наука, здоровье, "
    "развлечения, мир, образование, безопасность, стартапы, экономика, общество\n"
    "  importance_score — целое число от 1 до 10\n"
    "  published_at — дата ISO 8601 или пустая строка\n\n"
    "ПРАВИЛА:\n"
    "- Если у статьи нет url — не включай её\n"
    "- Не выдумывай факты, опирайся только на предоставленные данные\n"
    "- Максимум 10 статей\n"
    "- Ответ: только JSON-массив, без каких-либо обёрток\n\n"
    'Пример ответа: [{"title":"...","summary":"...","url":"...","source":"...",'
    '"category":"технологии","importance_score":8,"published_at":"2026-04-04T10:00:00+00:00"}]'
)

SOURCE_CATALOG = {
    "google-news": {"label": "Google News", "domain": "", "weight": 0.4},
    "tass": {"label": "ТАСС", "domain": "tass.ru", "weight": 1.5},
    "rbc": {"label": "РБК", "domain": "rbc.ru", "weight": 1.4},
    "kommersant": {"label": "Коммерсантъ", "domain": "kommersant.ru", "weight": 1.3},
    "interfax": {"label": "Интерфакс", "domain": "interfax.ru", "weight": 1.5},
    "ria": {"label": "РИА Новости", "domain": "ria.ru", "weight": 1.2},
    "vedomosti": {"label": "Ведомости", "domain": "vedomosti.ru", "weight": 1.2},
    "habr": {"label": "Habr", "domain": "habr.com", "weight": 0.9},
    "vc": {"label": "VC", "domain": "vc.ru", "weight": 0.7},
    "techcrunch": {"label": "TechCrunch", "domain": "techcrunch.com", "weight": 1.0},
}

HIGH_IMPACT_TERMS = {
    "срочно", "важно", "экстренно", "впервые", "крупный", "массовый",
    "закон", "санкции", "запрет", "суд", "угроза", "кризис", "утечка",
    "уязвимость", "атака", "авария", "взрыв", "пожар", "погибли",
    "рост", "падение", "инвестиции", "сделка", "запуск", "релиз",
    "breakthrough", "security", "attack", "crisis", "ban", "launch",
}

LOW_IMPACT_TERMS = {
    "мнение", "колонка", "слухи", "подборка", "дайджест", "интервью",
    "обзор", "как", "why", "opinion", "rumor", "review",
}

GENERIC_TOPIC_TERMS = {
    "новости", "новость", "последние", "свежие", "сегодня", "главное",
    "лента", "дня", "news", "latest", "today",
}


@dataclass
class RawArticle:
    title: str
    url: str
    source_name: str
    source_url: str = ""
    published_at: str = ""
    snippet: str = ""


def _parse_pub_date(pub_date: str) -> str:
    if not pub_date:
        return ""
    try:
        parsed = parsedate_to_datetime(pub_date)
        return parsed.isoformat()
    except Exception:
        return pub_date


def _normalize_source_keys(raw_sources: Any) -> list[str]:
    if isinstance(raw_sources, str):
        values = [item.strip() for item in raw_sources.split(",")]
    elif isinstance(raw_sources, (list, tuple, set)):
        values = [str(item).strip() for item in raw_sources]
    else:
        values = []

    selected: list[str] = []
    for value in values:
        key = value.lower()
        if key in SOURCE_CATALOG and key not in selected:
            selected.append(key)

    return selected or ["google-news"]


def _source_domain(source_key: str) -> str:
    return str(SOURCE_CATALOG.get(source_key, {}).get("domain") or "")


def _dedupe_articles(articles: list[RawArticle], limit: int = 12) -> list[RawArticle]:
    seen: set[str] = set()
    unique: list[RawArticle] = []
    for article in articles:
        key = article.url.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(article)
        if len(unique) >= limit:
            break
    return unique


def _fetch_google_news(topic: str, source_key: str = "google-news", limit: int = 8) -> list[RawArticle]:
    """Запрашивает Google News RSS по теме, возвращает до 8 статей."""
    clean = topic.strip() or "новости"
    domain = _source_domain(source_key)
    query = f"{clean} site:{domain} when:2d" if domain else f"{clean} when:2d"
    try:
        response = requests.get(
            f"https://news.google.com/rss/search?q={quote(query)}&hl=ru&gl=RU&ceid=RU:ru",
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NewsAggBot/2.0)"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        articles: list[RawArticle] = []
        for item in root.findall(".//item")[:limit]:
            src_el = item.find("source")
            source_name = (src_el.text or "Google News").strip() if src_el is not None else "Google News"
            source_url = (src_el.get("url") or "") if src_el is not None else ""
            title = unescape((item.findtext("title") or "").strip())
            # Google News добавляет " - SourceName" в конец заголовка
            if source_name and title.endswith(f" - {source_name}"):
                title = title[: -len(f" - {source_name}")].strip()
            url = (item.findtext("link") or "").strip() or source_url
            if not url:
                continue
            articles.append(
                RawArticle(
                    title=title or "Без заголовка",
                    url=url,
                    source_name=source_name,
                    source_url=source_url,
                    published_at=_parse_pub_date(item.findtext("pubDate") or ""),
                )
            )
        return articles
    except Exception:
        return []


def _fetch_tavily_news(topic: str, source_keys: list[str] | None = None) -> list[RawArticle]:
    """Запрашивает Tavily Search API как запасной вариант."""
    api_key = getattr(config, "TAVILY_API_KEY", "")
    if not api_key:
        return []
    try:
        domains = [_source_domain(key) for key in (source_keys or []) if _source_domain(key)]
        domain_filter = " OR ".join(f"site:{domain}" for domain in domains[:6])
        query = topic.strip() or "latest news"
        if domain_filter:
            query = f"{query} ({domain_filter})"
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 10,
                "include_answer": False,
                "include_raw_content": False,
                "topic": "news",
            },
            timeout=HTTP_TIMEOUT,
        )
        if response.status_code != 200:
            return []
        articles: list[RawArticle] = []
        for item in response.json().get("results") or []:
            url = (item.get("url") or "").strip()
            if not url:
                continue
            domain = url.split("/")[2] if url.count("/") >= 2 else url
            articles.append(
                RawArticle(
                    title=(item.get("title") or url),
                    url=url,
                    source_name=domain,
                    snippet=str(item.get("content") or "")[:400],
                    published_at=str(item.get("published_date") or "").replace("T", " ")[:16],
                )
            )
        return articles
    except Exception:
        return []


def _build_raw_context(articles: list[RawArticle]) -> str:
    lines: list[str] = []
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. Заголовок: {a.title}")
        lines.append(f"   URL: {a.url}")
        lines.append(f"   Источник: {a.source_name}")
        if a.published_at:
            lines.append(f"   Дата: {a.published_at}")
        if a.snippet:
            lines.append(f"   Фрагмент: {a.snippet}")
    return "\n".join(lines)


def _call_gemini(raw_context: str, topic: str) -> list[dict[str, Any]]:
    """Отправляет сырые данные в Gemini 2.0 через OpenRouter, получает JSON-массив новостей."""
    if not config.OPENROUTER_API_KEY:
        return []
    try:
        response = requests.post(
            f"{config.OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": config.APP_SITE_URL,
                "X-Title": config.APP_HTTP_TITLE,
            },
            json={
                "model": config.OPENROUTER_MODEL,  # google/gemini-2.0-flash-001
                "messages": [
                    {"role": "system", "content": NEWS_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Тема запроса: {topic}\n"
                            "Выбери только новости, которые явно относятся к этой теме. "
                            "Если статья не по теме, не включай ее в JSON.\n\n"
                            f"Обработай эти статьи:\n\n{raw_context}"
                        ),
                    },
                ],
                "max_tokens": 2500,
                "temperature": 0.15,
            },
            timeout=50,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()

        # Gemini иногда оборачивает в ```json ... ```
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                stripped = part.strip()
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                if stripped.startswith("["):
                    content = stripped
                    break

        # Если Gemini вернул объект, а не массив — ищем массив внутри
        parsed: Any = json.loads(content)
        if isinstance(parsed, list):
            return parsed
        for key in ("articles", "news", "results", "items", "data"):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
        return []
    except Exception:
        return []


def _safe_int(value: Any, default: int, lo: int = 1, hi: int = 10) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def _normalize_category(raw: Any) -> str:
    """Приводит категорию к одному из допустимых значений."""
    candidate = str(raw or "").strip().lower()
    if candidate in ALLOWED_CATEGORIES:
        return candidate
    # Нечёткое сопоставление по подстроке
    for cat in ALLOWED_CATEGORIES:
        if cat in candidate or candidate in cat:
            return cat
    return "общество"


def _parse_article_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None


def _topic_terms(topic: str) -> list[str]:
    return [term for term in re.split(r"[\s,.;:!?()\[\]{}\"']+", topic.lower()) if len(term) > 1]


def _relevance_terms(topic: str) -> list[str]:
    return [term for term in _topic_terms(topic) if term not in GENERIC_TOPIC_TERMS]


def _matches_topic_text(text: str, topic: str) -> bool:
    terms = _relevance_terms(topic)
    if not terms:
        return True
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _filter_raw_articles_by_topic(articles: list[RawArticle], topic: str) -> list[RawArticle]:
    terms = _relevance_terms(topic)
    if not terms:
        return articles
    return [
        article
        for article in articles
        if _matches_topic_text(
            f"{article.title} {article.snippet} {article.source_name} {article.source_url}",
            topic,
        )
    ]


def _filter_processed_by_topic(items: list[dict[str, Any]], topic: str) -> list[dict[str, Any]]:
    terms = _relevance_terms(topic)
    if not terms:
        return items
    return [
        item
        for item in items
        if _matches_topic_text(
            f"{item.get('title', '')} {item.get('summary', '')} {item.get('source', '')} {item.get('url', '')}",
            topic,
        )
    ]


def _source_weight(source: str, url: str) -> float:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    source_text = source.lower()
    best = 0.0
    for meta in SOURCE_CATALOG.values():
        domain = str(meta.get("domain") or "").lower()
        label = str(meta.get("label") or "").lower()
        if domain and (host.endswith(domain) or domain in source_text):
            best = max(best, float(meta.get("weight") or 0))
        elif label and label in source_text:
            best = max(best, float(meta.get("weight") or 0))
    return best


def _calculate_importance(item: dict[str, Any], topic: str) -> int:
    """Финальная 10-балльная оценка важности, не зависящая только от LLM."""
    title = str(item.get("title") or "")
    summary = str(item.get("summary") or "")
    source = str(item.get("source") or "")
    url = str(item.get("url") or "")
    text = f"{title} {summary}".lower()

    score = 4.0
    model_score = _safe_int(item.get("importance_score"), 6)
    score += (model_score - 5) * 0.22
    score += _source_weight(source, url)

    published = _parse_article_datetime(item.get("published_at"))
    if published:
        hours = max(0.0, (datetime.now(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() / 3600)
        if hours <= 2:
            score += 2.0
        elif hours <= 8:
            score += 1.5
        elif hours <= 24:
            score += 1.0
        elif hours <= 48:
            score += 0.45
        else:
            score -= 0.4

    title_lower = title.lower()
    score += min(2.0, sum(0.45 for term in HIGH_IMPACT_TERMS if term in title_lower))
    score += min(1.2, sum(0.22 for term in HIGH_IMPACT_TERMS if term in text))
    score -= min(1.1, sum(0.35 for term in LOW_IMPACT_TERMS if term in title_lower))

    topic_hits = sum(1 for term in _topic_terms(topic) if term in text)
    if topic_hits:
        score += min(1.4, 0.45 * topic_hits)

    if len(summary) > 180:
        score += 0.25
    if not summary or summary == "Нет описания.":
        score -= 0.55

    return max(1, min(10, round(score)))


class AiNewsService:
    """
    Получает новости из Google News / Tavily, обрабатывает через Gemini 2.0,
    автоматически классифицирует по категориям и сохраняет в БД для всех пользователей.
    """

    def fetch_and_process(self, topic: str = "новости", sources: Any = None) -> tuple[list[dict[str, Any]], str]:
        """
        Возвращает (список_статей, сообщение_об_ошибке).
        При успехе сообщение_об_ошибке — пустая строка.
        """
        source_keys = _normalize_source_keys(sources)

        # 1. Забираем сырые данные с учетом выбранных источников
        articles: list[RawArticle] = []
        for source_key in source_keys:
            articles.extend(_fetch_google_news(topic, source_key=source_key, limit=5 if source_key != "google-news" else 8))
        articles = _dedupe_articles(articles)
        articles = _filter_raw_articles_by_topic(articles, topic)
        if not articles:
            articles = _filter_raw_articles_by_topic(_fetch_tavily_news(topic, source_keys), topic)

        if not articles:
            return [], "Не удалось найти релевантные новости по этой теме в выбранных источниках. Попробуйте расширить источники или изменить запрос."

        # 2. Готовим контекст для Gemini
        raw_context = _build_raw_context(articles)

        # 3. Обрабатываем через Gemini 2.0
        processed = _call_gemini(raw_context, topic)
        processed = _filter_processed_by_topic(processed, topic)

        # 4. Если Gemini недоступен — собираем результат из сырых данных
        if not processed:
            processed = [
                {
                    "title": a.title,
                    "summary": a.snippet or "Нет описания.",
                    "url": a.url,
                    "source": a.source_name,
                    "category": "общество",
                    "importance_score": _calculate_importance(
                        {
                            "title": a.title,
                            "summary": a.snippet,
                            "source": a.source_name,
                            "url": a.url,
                            "published_at": a.published_at,
                        },
                        topic,
                    ),
                    "published_at": a.published_at,
                }
                for a in articles[:8]
            ]

        # 5. Нормализуем категории и пересчитываем важность единым алгоритмом
        for item in processed:
            item["category"] = _normalize_category(item.get("category"))
            item["importance_score"] = _calculate_importance(item, topic)

        processed = sorted(
            processed,
            key=lambda item: (
                _safe_int(item.get("importance_score"), 1),
                str(item.get("published_at") or ""),
            ),
            reverse=True,
        )[:10]

        return processed, ""

    def save_to_db(self, articles: list[dict[str, Any]], db_session: Any, NewsModel: Any) -> int:
        """
        Сохраняет новые статьи в таблицу News.
        Дубликаты (по URL) пропускает.
        Возвращает количество новых записей.
        """
        saved = 0
        for item in articles:
            url = str(item.get("url") or "").strip()
            if not url:
                continue

            existing = NewsModel.query.filter_by(url=url).one_or_none()
            if existing is not None:
                # Дополняем summary, если был пустым
                if item.get("summary") and not existing.summary:
                    existing.summary = str(item["summary"])[:2000]
                continue

            news = NewsModel(url=url)
            news.title = str(item.get("title") or "Без заголовка")[:500]
            news.source = str(item.get("source") or "Источник")[:200]
            news.category = str(item.get("category") or "общество")[:80]
            summary = str(item.get("summary") or "")[:2000]
            news.summary = summary
            news.content = summary  # content совпадает с summary
            news.importance_score = _safe_int(item.get("importance_score"), 6)
            news.is_processed = True

            pub_raw = str(item.get("published_at") or "").strip()
            if pub_raw:
                try:
                    news.published_at = datetime.fromisoformat(
                        pub_raw.replace("Z", "+00:00")
                    )
                except ValueError:
                    news.published_at = datetime.now(timezone.utc)
            else:
                news.published_at = datetime.now(timezone.utc)

            db_session.add(news)
            saved += 1

        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            return 0

        return saved
