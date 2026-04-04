"""AI News Service — получает свежие новости, обрабатывает Gemini 2.0 и сохраняет в БД."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import quote

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


def _fetch_google_news(topic: str) -> list[RawArticle]:
    """Запрашивает Google News RSS по теме, возвращает до 8 статей."""
    clean = topic.strip() or "новости"
    query = f"{clean} when:2d"
    try:
        response = requests.get(
            f"https://news.google.com/rss/search?q={quote(query)}&hl=ru&gl=RU&ceid=RU:ru",
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NewsAggBot/2.0)"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        articles: list[RawArticle] = []
        for item in root.findall(".//item")[:8]:
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


def _fetch_tavily_news(topic: str) -> list[RawArticle]:
    """Запрашивает Tavily Search API как запасной вариант."""
    api_key = getattr(config, "TAVILY_API_KEY", "")
    if not api_key:
        return []
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": topic.strip() or "latest news",
                "search_depth": "advanced",
                "max_results": 7,
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


def _call_gemini(raw_context: str) -> list[dict[str, Any]]:
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
                        "content": f"Обработай эти статьи:\n\n{raw_context}",
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


class AiNewsService:
    """
    Получает новости из Google News / Tavily, обрабатывает через Gemini 2.0,
    автоматически классифицирует по категориям и сохраняет в БД для всех пользователей.
    """

    def fetch_and_process(self, topic: str = "новости") -> tuple[list[dict[str, Any]], str]:
        """
        Возвращает (список_статей, сообщение_об_ошибке).
        При успехе сообщение_об_ошибке — пустая строка.
        """
        # 1. Забираем сырые данные
        articles = _fetch_google_news(topic)
        if not articles:
            articles = _fetch_tavily_news(topic)

        if not articles:
            return [], "Не удалось получить новости из внешних источников. Попробуйте позже."

        # 2. Готовим контекст для Gemini
        raw_context = _build_raw_context(articles)

        # 3. Обрабатываем через Gemini 2.0
        processed = _call_gemini(raw_context)

        # 4. Если Gemini недоступен — собираем результат из сырых данных
        if not processed:
            processed = [
                {
                    "title": a.title,
                    "summary": a.snippet or "Нет описания.",
                    "url": a.url,
                    "source": a.source_name,
                    "category": "общество",
                    "importance_score": 6,
                    "published_at": a.published_at,
                }
                for a in articles[:8]
            ]

        # 5. Нормализуем категории
        for item in processed:
            item["category"] = _normalize_category(item.get("category"))

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
