"""Database models for IDO SKILLS News."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


def normalize_interests(value):
    if value is None:
        return []

    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, (tuple, set)):
        raw_items = list(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            decoded = json.loads(stripped)
            raw_items = decoded if isinstance(decoded, list) else [decoded]
        except json.JSONDecodeError:
            raw_items = [item.strip() for item in stripped.split(",")]
    else:
        raw_items = [value]

    normalized = []
    seen = set()
    for item in raw_items:
        text = str(item).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            normalized.append(text)
    return normalized


def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    interests = db.Column(db.JSON, nullable=False, default=list)
    news_threshold = db.Column(db.Integer, default=6, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    last_digest = db.Column(db.DateTime(timezone=True), nullable=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def set_interests(self, interests):
        self.interests = normalize_interests(interests)

    @property
    def interests_list(self):
        return normalize_interests(self.interests)

    def to_dict(self):
        interests = self.interests_list
        return {
            "id": self.id,
            "login": self.login,
            "username": self.login,
            "email": self.email,
            "interests": interests,
            "news_threshold": self.news_threshold,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_digest": self.last_digest.isoformat() if self.last_digest else None,
        }


class News(db.Model):
    __tablename__ = "news"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(1000), nullable=False, unique=True, index=True)
    source = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(80), nullable=True)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    content = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    importance_score = db.Column(db.Integer, default=0, nullable=False)
    is_processed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "category": self.category,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "summary": self.summary,
            "importance_score": self.importance_score,
            "is_processed": self.is_processed,
        }


class UserNews(db.Model):
    __tablename__ = "user_news"
    __table_args__ = (
        db.UniqueConstraint("user_id", "news_id", name="uq_user_news"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    news_id = db.Column(db.Integer, db.ForeignKey("news.id"), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    is_bookmarked = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
