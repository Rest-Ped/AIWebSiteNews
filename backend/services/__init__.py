"""Сервисы приложения"""
from .assistant_service import AssistantService
from .llm_service import LLMService
from .news_fetcher import NewsFetcher
from .summarizer import Summarizer

__all__ = ['AssistantService', 'LLMService', 'NewsFetcher', 'Summarizer']
