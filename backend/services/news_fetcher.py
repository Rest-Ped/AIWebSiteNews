"""Сервис получения новостей - демо версия"""
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from config import config

class NewsFetcher:
    def __init__(self):
        self.sources = config.SOURCES
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (IdoSkillsNews/1.0)'
        }
    
    def fetch_web(self, url: str) -> list:
        """Получение новостей с веб-страницы"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            news = []
            for item in soup.find_all(['h1', 'h2', 'h3'], limit=10):
                text = item.get_text(strip=True)
                if text:
                    news.append({
                        'title': text,
                        'url': url,
                        'source': url,
                        'published_at': datetime.now(timezone.utc),
                        'content': text
                    })
            return news
        except Exception as e:
            print(f"Error fetching web {url}: {e}")
            return []
    
    def fetch_all(self) -> list:
        """Получение новостей из всех источников"""
        all_news = []
        for source in self.sources:
            all_news.extend(self.fetch_web(source))
        return all_news