"""Assistant service for personalized website and Telegram AI replies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from config import config


@dataclass(slots=True)
class AssistantSource:
    title: str
    url: str


class AssistantService:
    def __init__(self):
        self.api_key = config.OPENROUTER_API_KEY
        self.base_url = config.OPENROUTER_BASE_URL
        self.model = config.OPENROUTER_MODEL
        self.timeout = config.TELEGRAM_BOT_TIMEOUT

    def chat(self, *, message: str, user: Any | None = None, news_items: list[Any] | None = None) -> dict[str, Any]:
        news_items = news_items or []
        sources = self._build_sources(news_items)
        source_payload = [{"title": source.title, "url": source.url} for source in sources]

        if not self.api_key:
            return {
                "reply": self._fallback_reply(message=message, user=user, news_items=news_items),
                "sources": source_payload,
                "provider": "fallback",
            }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": config.APP_SITE_URL,
                    "X-Title": config.APP_HTTP_TITLE,
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self._system_prompt(user=user, news_items=news_items)},
                        {"role": "user", "content": message.strip()},
                    ],
                    "max_tokens": 650,
                    "temperature": 0.45,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"].strip()
            return {
                "reply": content or self._fallback_reply(message=message, user=user, news_items=news_items),
                "sources": source_payload,
                "provider": "openrouter",
            }
        except Exception:
            return {
                "reply": self._fallback_reply(message=message, user=user, news_items=news_items),
                "sources": source_payload,
                "provider": "fallback",
            }

    def _system_prompt(self, *, user: Any | None, news_items: list[Any]) -> str:
        user_block = self._user_block(user)
        news_block = self._news_block(news_items)
        return (
            "Ты ИИ-ассистент сервиса IDO SKILLS News и Telegram-бота. "
            "Отвечай только на русском языке, кратко, понятно и без выдуманных фактов. "
            "Если вопрос касается профиля, интересов, новостей или сводки пользователя, опирайся только на переданный контекст. "
            "Если данных недостаточно, честно скажи об этом. "
            "Если в контексте есть новости, можешь рекомендовать, что читать первым.\n\n"
            f"{user_block}\n\n{news_block}"
        )

    def _user_block(self, user: Any | None) -> str:
        if not user:
            return "Пользователь не авторизован."

        interests = ", ".join(user.interests_list) if getattr(user, "interests_list", None) else "не заданы"
        return (
            "Профиль пользователя:\n"
            f"- login: {getattr(user, 'login', '') or '—'}\n"
            f"- email: {getattr(user, 'email', '') or 'не указан'}\n"
            f"- interests: {interests}\n"
            f"- news_threshold: {getattr(user, 'news_threshold', '—')}\n"
            f"- telegram_username: {getattr(user, 'telegram_username', '') or 'не привязан'}"
        )

    def _news_block(self, news_items: list[Any]) -> str:
        if not news_items:
            return "Персональных новостей пока нет."

        lines = ["Актуальные персональные новости пользователя:"]
        for index, item in enumerate(news_items[:6], start=1):
            title = self._item_value(item, "title", f"Новость {index}")
            source = self._item_value(item, "source", "Источник")
            category = self._item_value(item, "category", "без категории")
            summary = self._item_value(item, "summary", "")
            importance = self._item_value(item, "importance_score", "—")
            lines.append(
                f"{index}. {title} | {source} | {category} | важность {importance}"
            )
            if summary:
                lines.append(f"   {str(summary).strip()[:260]}")
        return "\n".join(lines)

    def _build_sources(self, news_items: list[Any]) -> list[AssistantSource]:
        sources: list[AssistantSource] = []
        seen: set[str] = set()
        for item in news_items[:6]:
            url = self._item_value(item, "url", "")
            title = self._item_value(item, "title", url or "Источник")
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(AssistantSource(title=title, url=url))
        return sources

    @staticmethod
    def _item_value(item: Any, field: str, default: Any = "") -> Any:
        if isinstance(item, dict):
            value = item.get(field, default)
        else:
            value = getattr(item, field, default)
        if value in (None, ""):
            return default
        return value

    def _fallback_reply(self, *, message: str, user: Any | None, news_items: list[Any]) -> str:
        if user is None:
            return (
                "Я могу общаться по данным сервиса, но сначала нужно войти или зарегистрироваться. "
                "После этого станут доступны профиль, интересы, персональные новости и сводка."
            )

        lowered = message.lower()
        interests = ", ".join(user.interests_list) if getattr(user, "interests_list", None) else "не заданы"

        if any(word in lowered for word in ("профиль", "аккаунт", "кто я", "мои данные")):
            return (
                f"Ваш профиль: логин {user.login}, email {user.email or 'не указан'}, "
                f"интересы: {interests}, порог важности: {user.news_threshold}."
            )

        if any(word in lowered for word in ("сводк", "дайджест")):
            if not news_items:
                return "По вашим интересам пока нет новостей для сводки."
            top_titles = ", ".join((getattr(item, "title", None) or item.get("title") or "") for item in news_items[:3])
            return (
                f"Краткая сводка по вашим интересам ({interests}): сейчас в приоритете {top_titles}. "
                "Откройте раздел новостей, чтобы получить полную подборку."
            )

        if any(word in lowered for word in ("новости", "что почитать", "что нового")):
            if not news_items:
                return "По вашим интересам пока нет актуальных новостей."
            first = news_items[0]
            title = getattr(first, "title", None) or first.get("title") or "новость"
            return (
                f"По вашим интересам сейчас самая заметная тема: {title}. "
                "Если хотите, могу ещё подсказать персональную сводку или помочь обновить интересы."
            )

        return (
            f"Я вижу ваш профиль и интересы ({interests}) и могу помочь с новостями, сводкой, профилем и настройками. "
            "Спросите, например: мои новости, моя сводка, мой профиль, обнови интересы."
        )
