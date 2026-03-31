"""Конфигурация приложения IDO SKILLS News"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///database.db')
    LLM_MODEL = os.getenv('LLM_MODEL', 'llama3.2')
    LLM_API_URL = os.getenv('LLM_API_URL', 'http://localhost:11434')
    NEWS_THRESHOLD = int(os.getenv('NEWS_THRESHOLD', '6'))
    DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
    BACKEND_PORT = int(os.getenv('BACKEND_PORT', '5000'))
    
    MAX_NEWS_PER_USER = 20
    SOURCES = [
        'https://rss.lenta.ru/rss',
        'https://feeds.bbci.co.uk/news/rss.xml',
    ]

config = Config()