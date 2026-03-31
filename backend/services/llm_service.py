"""Сервис работы с LLM (Ollama/LLaMa) - демо режим"""
import random
from config import config

class LLMService:
    def __init__(self):
        self.api_url = config.LLM_API_URL
        self.model = config.LLM_MODEL
    
    def check_connection(self):
        """Проверка подключения к LLM (в демо всегда False)"""
        return False
    
    def evaluate_news_importance(self, title: str, content: str, user_interests: str) -> int:
        """Оценка важности новости по 10-балльной шкале (демо)"""
        return random.randint(6, 9)
    
    def summarize_news(self, articles: list, user_interests: str) -> str:
        """Формирование сводки новостей (демо)"""
        if not articles:
            return "Нет новостей для отображения"
        
        summary = "📰 СВОДКА НОВОСТЕЙ\n\n"
        for i, article in enumerate(articles[:5], 1):
            summary += f"{i}. {article.get('title', 'Без названия')}\n"
            summary += f"   Источник: {article.get('source', 'Неизвестно')}\n"
            summary += f"   Важность: {article.get('importance_score', 5)}/10\n\n"
        
        return summary