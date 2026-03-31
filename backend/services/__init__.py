"""Сервисы приложения"""
from .llm_service import LLMService
from .news_fetcher import NewsFetcher
from .summarizer import Summarizer

__all__ = ['LLMService', 'NewsFetcher', 'Summarizer']