"""Сервис обработки и суммаризации новостей"""
from .llm_service import LLMService
from config import config

class Summarizer:
    def __init__(self):
        self.llm = LLMService()
        self.threshold = config.NEWS_THRESHOLD
    
    def filter_and_summarize(self, news_list: list, user_interests: str) -> list:
        """Фильтрация и суммаризация новостей"""
        filtered = []
        for news in news_list:
            score = self.llm.evaluate_news_importance(
                news['title'],
                news.get('content', ''),
                user_interests
            )
            if score >= self.threshold:
                news['importance_score'] = score
                filtered.append(news)
        
        filtered.sort(key=lambda x: x['importance_score'], reverse=True)
        return filtered[:config.MAX_NEWS_PER_USER]
    
    def generate_digest(self, news_list: list, user_interests: str) -> str:
        """Генерация итоговой сводки"""
        return self.llm.summarize_news(news_list, user_interests)