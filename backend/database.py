"""Модуль работы с базой данных"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

# Создаём объект БД ПЕРЕД использованием в моделях
db = SQLAlchemy()

def init_db(app):
    """Инициализация базы данных"""
    db.init_app(app)
    with app.app_context():
        db.create_all()

class User(db.Model):
    """Модель пользователя"""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=False, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    interests = db.Column(db.Text, nullable=True)
    news_threshold = db.Column(db.Integer, default=6)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_digest = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'interests': self.interests,
            'news_threshold': self.news_threshold,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_digest': self.last_digest.isoformat() if self.last_digest else None
        }

class News(db.Model):
    """Модель новости"""
    __tablename__ = 'news'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(1000), nullable=False)
    source = db.Column(db.String(200), nullable=True)
    published_at = db.Column(db.DateTime, nullable=True)
    content = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    importance_score = db.Column(db.Integer, default=0)
    is_processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'summary': self.summary,
            'importance_score': self.importance_score,
            'is_processed': self.is_processed
        }

class UserNews(db.Model):
    """Связь пользователь-новости"""
    __tablename__ = 'user_news'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    news_id = db.Column(db.Integer, db.ForeignKey('news.id'), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))