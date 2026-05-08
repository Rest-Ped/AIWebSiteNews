"""IDO SKILLS News backend with PostgreSQL-ready auth API."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, or_, text

sys.path.insert(0, str(Path(__file__).parent))

from config import config
from database import News, User, UserNews, db, init_db, normalize_interests
from services.ai_news_service import AiNewsService
from services.assistant_service import AssistantService
from services.llm_service import LLMService
from services.news_fetcher import NewsFetcher
from services.summarizer import Summarizer


class MockLLM:
    """Fallback summary generator for demo mode."""

    def generate_summary(self, news_list, interests):
        if not news_list:
            return "Нет новостей для отображения."

        interest_text = ", ".join(interests) if interests else "общая лента"
        lines = [
            "IDO SKILLS NEWS DIGEST",
            f"Интересы: {interest_text}",
            f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            "",
            "Топ новостей:",
        ]

        for index, news in enumerate(news_list[:5], start=1):
            lines.append(
                f"{index}. {news.get('title', 'Без названия')} "
                f"({news.get('source', 'Источник не указан')}, "
                f"важность {news.get('importance_score', 'N/A')}/10)"
            )
            summary = (news.get("summary") or "").strip()
            if summary:
                lines.append(f"   {summary[:160]}")

        lines.append("")
        lines.append("Сводка сгенерирована встроенным демо-режимом.")
        return "\n".join(lines)


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = config.SECRET_KEY

CORS(app, resources={r"/api/*": {"origins": config.CORS_ORIGINS}})
init_db(app)

llm_service = LLMService()
news_fetcher = NewsFetcher()
summarizer = Summarizer()
assistant_service = AssistantService()
ai_news_service = AiNewsService()
mock_llm = MockLLM()
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt=config.AUTH_TOKEN_SALT)


def parse_json():
    return request.get_json(silent=True) or {}


def json_error(message, status_code=400):
    return jsonify({"error": message}), status_code


def parse_threshold(data):
    raw_value = data.get("threshold") or data.get("news_threshold") or config.NEWS_THRESHOLD
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = config.NEWS_THRESHOLD
    return max(1, min(10, value))


def create_auth_token(user: User) -> str:
    return serializer.dumps({"user_id": user.id, "login": user.login})


def find_user_by_identifier(identifier: str):
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    return User.query.filter(
        or_(
            func.lower(User.login) == identifier.lower(),
            func.lower(User.email) == identifier.lower(),
        )
    ).first()


def get_user_by_telegram_id_value(telegram_id):
    try:
        parsed_id = int(telegram_id)
    except (TypeError, ValueError):
        return None
    return User.query.filter_by(telegram_id=parsed_id).first()


def link_telegram_account(user: User, data):
    telegram_id = data.get("telegram_id")
    if not telegram_id:
        return user, None

    try:
        parsed_id = int(telegram_id)
    except (TypeError, ValueError):
        return None, json_error("Telegram ID is invalid.")

    existing = get_user_by_telegram_id_value(parsed_id)
    if existing and existing.id != user.id:
        return None, json_error("Telegram account is already linked to another user.", 409)

    user.link_telegram(
        parsed_id,
        username=(data.get("telegram_username") or "").strip() or None,
        chat_id=data.get("telegram_chat_id"),
    )
    return user, None


def extract_token():
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()

    fallback = request.headers.get("X-Auth-Token", "").strip()
    if fallback:
        return fallback

    token = request.args.get("token", "").strip()
    if token:
        return token

    payload = parse_json()
    return str(payload.get("token", "")).strip()


def get_current_user(required=True):
    token = extract_token()
    if not token:
        if required:
            return None, json_error("Authentication token is required.", 401)
        return None, None

    try:
        payload = serializer.loads(token, max_age=config.AUTH_TOKEN_MAX_AGE)
    except SignatureExpired:
        return None, json_error("Authentication token expired.", 401)
    except BadSignature:
        return None, json_error("Authentication token is invalid.", 401)

    user = db.session.get(User, payload.get("user_id"))
    if not user:
        return None, json_error("User not found.", 401)

    return user, None


def get_user_from_request_or_token(required=True):
    user, _ = get_current_user(required=False)
    if user:
        return user, None

    data = parse_json()
    user_id = data.get("user_id") or request.args.get("user_id")
    if user_id:
        try:
            user = db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            user = None
        if user:
            return user, None

    telegram_id = data.get("telegram_id") or request.args.get("telegram_id")
    if telegram_id:
        user = get_user_by_telegram_id_value(telegram_id)
        if user:
            return user, None

    if required:
        return None, json_error("Authentication is required.", 401)

    return None, None


def build_demo_news():
    now = datetime.now(timezone.utc)
    return [
        {
            "title": "ИИ помогает редакциям быстрее собирать новости",
            "url": "https://example.com/news/ai-newsroom",
            "source": "Tech News",
            "category": "технологии",
            "summary": "Редакции используют ИИ для поиска тем, расстановки приоритетов и черновых сводок.",
            "content": "Новые инструменты помогают новостным командам ускорять подготовку материалов и подбор тем.",
            "importance_score": 9,
            "published_at": now - timedelta(minutes=15),
        },
        {
            "title": "Стартапы в области ИИ привлекли новые инвестиции",
            "url": "https://example.com/news/ai-startups",
            "source": "Startup Weekly",
            "category": "стартапы",
            "summary": "Инвесторы продолжают вкладываться в команды, которые автоматизируют аналитику и клиентский сервис.",
            "content": "Раунд финансирования получили компании, работающие с корпоративными AI-продуктами.",
            "importance_score": 8,
            "published_at": now - timedelta(hours=1),
        },
        {
            "title": "Python остается основным языком для ML и автоматизации",
            "url": "https://example.com/news/python-ml",
            "source": "Dev Weekly",
            "category": "программирование",
            "summary": "Экосистема Python продолжает расти благодаря data science и backend-разработке.",
            "content": "Сообщество продолжает выпускать библиотеки для анализа данных, API и автоматизации процессов.",
            "importance_score": 8,
            "published_at": now - timedelta(hours=2),
        },
        {
            "title": "Новый инструмент аналитики собирает новости по интересам пользователя",
            "url": "https://example.com/news/personal-digest",
            "source": "Product Radar",
            "category": "аналитика",
            "summary": "Продукт объединяет фильтрацию, оценку важности и генерацию персональных дайджестов.",
            "content": "Сервисы персонализации становятся ядром для приложений, работающих с потоками новостей.",
            "importance_score": 7,
            "published_at": now - timedelta(hours=3),
        },
        {
            "title": "Команды внедряют безопасную авторизацию для рабочих приложений",
            "url": "https://example.com/news/auth-security",
            "source": "Security Daily",
            "category": "безопасность",
            "summary": "Хранение паролей в виде хеша и токены доступа стали обязательным стандартом.",
            "content": "Компании переходят на более надежные схемы хранения учетных данных и контроля доступа.",
            "importance_score": 7,
            "published_at": now - timedelta(hours=4),
        },
        {
            "title": "Рынок EdTech делает ставку на персональные рекомендации",
            "url": "https://example.com/news/edtech-personalization",
            "source": "Edu Tech",
            "category": "образование",
            "summary": "Платформы обучения адаптируют контент под интересы и поведение пользователей.",
            "content": "Персонализация стала главным трендом платформ дистанционного обучения и корпоративного апскиллинга.",
            "importance_score": 6,
            "published_at": now - timedelta(hours=5),
        },
    ]


def sync_demo_news():
    stored_items = []
    for item in build_demo_news():
        news = News.query.filter_by(url=item["url"]).one_or_none()
        if news is None:
            news = News(url=item["url"])
            db.session.add(news)

        news.title = item["title"]
        news.source = item["source"]
        news.category = item["category"]
        news.summary = item["summary"]
        news.content = item["content"]
        news.importance_score = item["importance_score"]
        news.published_at = item["published_at"]
        news.is_processed = True
        stored_items.append(news)

    db.session.commit()
    return stored_items


def filter_news_for_user(news_items, interests):
    ordered_items = sorted(
        news_items,
        key=lambda item: (
            item.importance_score or 0,
            item.published_at or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    normalized = [value.lower() for value in normalize_interests(interests)]
    if not normalized:
        return ordered_items[: config.MAX_NEWS_PER_USER]

    matched = []
    for item in ordered_items:
        haystack = " ".join(
            [
                item.title or "",
                item.summary or "",
                item.content or "",
                item.source or "",
                item.category or "",
            ]
        ).lower()
        if any(term in haystack for term in normalized):
            matched.append(item)

    return matched if matched else ordered_items[: config.MAX_NEWS_PER_USER]


def serialize_news_list(news_items):
    return [item.to_dict() for item in news_items]


def ensure_owner_or_current(user_id: int):
    current_user, error_response = get_current_user(required=True)
    if error_response:
        return None, error_response

    if current_user.id != user_id:
        return None, json_error("Access denied.", 403)

    return current_user, None


def build_digest_response(user: User):
    stored_news = sync_demo_news()
    filtered_news = filter_news_for_user(stored_news, user.interests_list)
    digest = mock_llm.generate_summary(serialize_news_list(filtered_news), user.interests_list)

    user.last_digest = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify(
        {
            "digest": digest,
            "news_count": len(filtered_news),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ai_generated": True,
        }
    )


def build_stats_payload(user: User):
    read_count = UserNews.query.filter_by(user_id=user.id, is_read=True).count()
    bookmarks_count = UserNews.query.filter_by(user_id=user.id, is_bookmarked=True).count()
    created_at = user.created_at or datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    days_since_registration = (datetime.now(timezone.utc) - created_at).days
    return {
        "read_count": read_count,
        "bookmarks_count": bookmarks_count,
        "streak_days": max(1, days_since_registration),
    }


@app.route("/api/health", methods=["GET"])
def health_check():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        return (
            jsonify(
                {
                    "status": "error",
                    "database": "unavailable",
                    "message": str(exc),
                    "version": "2.0.0",
                }
            ),
            500,
        )

    return jsonify(
        {
            "status": "ok",
            "database": "ok",
            "llm_connected": llm_service.check_connection(),
            "version": "2.0.0",
        }
    )


@app.route("/api/auth/register", methods=["POST"])
@app.route("/api/users", methods=["POST"])
def register_user():
    data = parse_json()
    login = (data.get("login") or data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower() or None
    password = str(data.get("password") or "").strip()
    interests = normalize_interests(data.get("interests"))
    threshold = parse_threshold(data)

    if not login:
        return json_error("Login is required.")
    if not password or len(password) < 6:
        return json_error("Password must contain at least 6 characters.")

    if User.query.filter(func.lower(User.login) == login.lower()).first():
        return json_error("User with this login already exists.", 409)

    if email and User.query.filter(func.lower(User.email) == email.lower()).first():
        return json_error("User with this email already exists.", 409)

    user = User(login=login, email=email, news_threshold=threshold)
    user.set_password(password)
    user.set_interests(interests)
    linked_user, error_response = link_telegram_account(user, data)
    if error_response:
        return error_response
    user = linked_user

    db.session.add(user)
    db.session.commit()

    token = create_auth_token(user)
    return (
        jsonify(
            {
                "message": "User created successfully.",
                "token": token,
                "user": user.to_dict(),
            }
        ),
        201,
    )


@app.route("/api/auth/login", methods=["POST"])
def login_user():
    data = parse_json()
    identifier = (data.get("login") or data.get("email") or data.get("username") or "").strip()
    password = str(data.get("password") or "").strip()

    if not identifier or not password:
        return json_error("Login and password are required.")

    user = find_user_by_identifier(identifier)

    if not user or not user.check_password(password):
        return json_error("Invalid login or password.", 401)

    linked_user, error_response = link_telegram_account(user, data)
    if error_response:
        return error_response
    user = linked_user

    if data.get("telegram_id"):
        db.session.commit()

    token = create_auth_token(user)
    return jsonify(
        {
            "message": "Login successful.",
            "token": token,
            "user": user.to_dict(),
        }
    )


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user, error_response = get_current_user(required=True)
    if error_response:
        return error_response
    return jsonify({"user": user.to_dict()})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    return jsonify({"message": "Logout successful."})


@app.route("/api/auth/telegram/login", methods=["POST"])
def telegram_login():
    data = parse_json()
    identifier = (data.get("login") or data.get("email") or data.get("username") or "").strip()
    password = str(data.get("password") or "").strip()

    if not identifier or not password:
        return json_error("Login and password are required.")

    user = find_user_by_identifier(identifier)
    if not user or not user.check_password(password):
        return json_error("Invalid login or password.", 401)

    linked_user, error_response = link_telegram_account(user, data)
    if error_response:
        return error_response
    db.session.commit()

    token = create_auth_token(linked_user)
    return jsonify(
        {
            "message": "Telegram login successful.",
            "token": token,
            "user": linked_user.to_dict(),
        }
    )


@app.route("/api/auth/telegram/register", methods=["POST"])
def telegram_register():
    data = parse_json()
    login = (data.get("login") or data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower() or None
    password = str(data.get("password") or "").strip()
    interests = normalize_interests(data.get("interests"))
    threshold = parse_threshold(data)

    if not login:
        return json_error("Login is required.")
    if not password or len(password) < 6:
        return json_error("Password must contain at least 6 characters.")

    if User.query.filter(func.lower(User.login) == login.lower()).first():
        return json_error("User with this login already exists.", 409)
    if email and User.query.filter(func.lower(User.email) == email.lower()).first():
        return json_error("User with this email already exists.", 409)

    user = User(login=login, email=email, news_threshold=threshold)
    user.set_password(password)
    user.set_interests(interests)

    linked_user, error_response = link_telegram_account(user, data)
    if error_response:
        return error_response

    db.session.add(linked_user)
    db.session.commit()

    token = create_auth_token(linked_user)
    return (
        jsonify(
            {
                "message": "Telegram user created successfully.",
                "token": token,
                "user": linked_user.to_dict(),
            }
        ),
        201,
    )


@app.route("/api/auth/telegram/link", methods=["POST"])
def telegram_link():
    user, error_response = get_current_user(required=True)
    if error_response:
        return error_response

    data = parse_json()
    linked_user, link_error = link_telegram_account(user, data)
    if link_error:
        return link_error

    db.session.commit()
    return jsonify({"message": "Telegram account linked.", "user": linked_user.to_dict()})


@app.route("/api/auth/telegram/unlink", methods=["POST"])
def telegram_unlink():
    user, error_response = get_current_user(required=True)
    if error_response:
        return error_response

    user.unlink_telegram()
    db.session.commit()
    return jsonify({"message": "Telegram account unlinked.", "user": user.to_dict()})


@app.route("/api/users/telegram/<int:telegram_id>", methods=["GET"])
def get_user_by_telegram(telegram_id):
    user = get_user_by_telegram_id_value(telegram_id)
    if not user:
        return json_error("User not found.", 404)
    return jsonify(user.to_dict())


@app.route("/api/users/telegram/<int:telegram_id>/interests", methods=["PUT"])
def update_telegram_interests(telegram_id):
    user = get_user_by_telegram_id_value(telegram_id)
    if not user:
        return json_error("User not found.", 404)

    data = parse_json()
    user.set_interests(data.get("interests"))
    user.news_threshold = parse_threshold(data)
    db.session.commit()

    return jsonify({"message": "Telegram interests saved.", "user": user.to_dict()})


@app.route("/api/users/me", methods=["GET"])
def get_current_profile():
    user, error_response = get_current_user(required=True)
    if error_response:
        return error_response
    return jsonify(user.to_dict())


@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    user, error_response = ensure_owner_or_current(user_id)
    if error_response:
        return error_response
    return jsonify(user.to_dict())


@app.route("/api/users/me", methods=["PUT"])
def update_current_user():
    user, error_response = get_current_user(required=True)
    if error_response:
        return error_response

    data = parse_json()
    new_login = (data.get("login") or data.get("username") or "").strip()
    new_email = (data.get("email") or "").strip().lower() or None
    new_password = str(data.get("password") or "").strip()

    if new_login and new_login.lower() != user.login.lower():
        if User.query.filter(func.lower(User.login) == new_login.lower(), User.id != user.id).first():
            return json_error("User with this login already exists.", 409)
        user.login = new_login

    if new_email != user.email:
        if new_email and User.query.filter(func.lower(User.email) == new_email.lower(), User.id != user.id).first():
            return json_error("User with this email already exists.", 409)
        user.email = new_email

    if "interests" in data:
        user.set_interests(data.get("interests"))

    if "threshold" in data or "news_threshold" in data:
        user.news_threshold = int(data.get("threshold") or data.get("news_threshold") or config.NEWS_THRESHOLD)

    if new_password:
        if len(new_password) < 6:
            return json_error("Password must contain at least 6 characters.")
        user.set_password(new_password)

    db.session.commit()
    return jsonify({"message": "Profile updated.", "user": user.to_dict()})


@app.route("/api/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    user, error_response = ensure_owner_or_current(user_id)
    if error_response:
        return error_response

    data = parse_json()
    new_login = (data.get("login") or data.get("username") or "").strip()
    new_email = (data.get("email") or "").strip().lower() or None
    new_password = str(data.get("password") or "").strip()

    if new_login and new_login.lower() != user.login.lower():
        if User.query.filter(func.lower(User.login) == new_login.lower(), User.id != user.id).first():
            return json_error("User with this login already exists.", 409)
        user.login = new_login

    if new_email != user.email:
        if new_email and User.query.filter(func.lower(User.email) == new_email.lower(), User.id != user.id).first():
            return json_error("User with this email already exists.", 409)
        user.email = new_email

    if "interests" in data:
        user.set_interests(data.get("interests"))

    if "threshold" in data or "news_threshold" in data:
        user.news_threshold = int(data.get("threshold") or data.get("news_threshold") or config.NEWS_THRESHOLD)

    if new_password:
        if len(new_password) < 6:
            return json_error("Password must contain at least 6 characters.")
        user.set_password(new_password)

    db.session.commit()
    return jsonify({"message": "Profile updated.", "user": user.to_dict()})


@app.route("/api/users/me/interests", methods=["PUT"])
def update_current_interests():
    user, error_response = get_current_user(required=True)
    if error_response:
        return error_response

    data = parse_json()
    user.set_interests(data.get("interests"))
    user.news_threshold = int(data.get("threshold") or config.NEWS_THRESHOLD)
    db.session.commit()

    return jsonify({"message": "Interests saved.", "user": user.to_dict()})


@app.route("/api/users/<int:user_id>/interests", methods=["PUT"])
def update_interests(user_id):
    user, error_response = ensure_owner_or_current(user_id)
    if error_response:
        return error_response

    data = parse_json()
    user.set_interests(data.get("interests"))
    user.news_threshold = int(data.get("threshold") or config.NEWS_THRESHOLD)
    db.session.commit()

    return jsonify({"message": "Interests saved.", "user": user.to_dict()})


@app.route("/api/users/<int:user_id>/stats", methods=["GET"])
def get_user_stats(user_id):
    user, error_response = ensure_owner_or_current(user_id)
    if error_response:
        return error_response
    return jsonify(build_stats_payload(user))


@app.route("/api/users/telegram/<int:telegram_id>/stats", methods=["GET"])
def get_telegram_user_stats(telegram_id):
    user = get_user_by_telegram_id_value(telegram_id)
    if not user:
        return json_error("User not found.", 404)
    return jsonify(build_stats_payload(user))


@app.route("/api/news/<int:news_id>/read", methods=["POST"])
def mark_news_read(news_id):
    user, error_response = get_user_from_request_or_token(required=True)
    if error_response:
        return error_response

    news = db.session.get(News, news_id)
    if not news:
        return json_error("News not found.", 404)

    user_news = UserNews.query.filter_by(user_id=user.id, news_id=news_id).first()
    if user_news is None:
        user_news = UserNews(user_id=user.id, news_id=news_id)
        db.session.add(user_news)

    user_news.is_read = True
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/news/<int:news_id>/bookmark", methods=["POST"])
def toggle_news_bookmark(news_id):
    user, error_response = get_user_from_request_or_token(required=True)
    if error_response:
        return error_response

    news = db.session.get(News, news_id)
    if not news:
        return json_error("News not found.", 404)

    user_news = UserNews.query.filter_by(user_id=user.id, news_id=news_id).first()
    if user_news is None:
        user_news = UserNews(user_id=user.id, news_id=news_id)
        db.session.add(user_news)

    user_news.is_bookmarked = not user_news.is_bookmarked
    db.session.commit()
    return jsonify({"success": True, "bookmarked": user_news.is_bookmarked})


@app.route("/api/news/fetch", methods=["POST"])
def fetch_news():
    user, error_response = get_user_from_request_or_token(required=True)
    if error_response:
        return error_response

    stored_news = sync_demo_news()
    filtered_news = filter_news_for_user(stored_news, user.interests_list)

    return jsonify(
        {
            "count": len(filtered_news),
            "news": serialize_news_list(filtered_news),
            "user": user.to_dict(),
        }
    )


@app.route("/api/users/me/digest", methods=["GET"])
def get_current_digest():
    user, error_response = get_current_user(required=True)
    if error_response:
        return error_response
    return build_digest_response(user)


@app.route("/api/users/<int:user_id>/digest", methods=["GET"])
def get_digest(user_id):
    user, error_response = ensure_owner_or_current(user_id)
    if error_response:
        return error_response
    return build_digest_response(user)


@app.route("/api/users/telegram/<int:telegram_id>/digest", methods=["GET"])
def get_telegram_digest(telegram_id):
    user = get_user_by_telegram_id_value(telegram_id)
    if not user:
        return json_error("User not found.", 404)
    return build_digest_response(user)


@app.route("/api/assistant/chat", methods=["POST"])
def assistant_chat():
    data = parse_json()
    message = str(data.get("message") or "").strip()
    if not message:
        return json_error("Message is required.")

    user, error_response = get_user_from_request_or_token(required=False)
    if error_response:
        return error_response

    stored_news = sync_demo_news()
    personal_news = filter_news_for_user(stored_news, user.interests_list if user else []) if user else stored_news[:5]
    result = assistant_service.chat(message=message, user=user, news_items=personal_news)

    return jsonify(
        {
            "reply": result.get("reply") or "",
            "sources": result.get("sources") or [],
            "provider": result.get("provider") or "fallback",
            "user": user.to_dict() if user else None,
        }
    )


@app.route("/api/news", methods=["GET"])
def get_all_news():
    sync_demo_news()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    pagination = News.query.order_by(News.importance_score.desc(), News.published_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    return jsonify(
        {
            "items": serialize_news_list(pagination.items),
            "total": pagination.total,
            "pages": pagination.pages,
        }
    )


@app.route("/api/ai-news", methods=["POST"])
def ai_news_chat():
    """
    Вкладка «AI Новости»: Gemini 2.0 ищет свежие новости по теме,
    автоматически присваивает категории и сохраняет в общую БД.

    Body (JSON, все поля опциональны):
        topic  — тема поиска (str, default "новости")
        sources — список источников: google-news, tass, rbc, kommersant,
                  interfax, ria, vedomosti, habr, vc, techcrunch

    Response:
        news   — список статей [{title, summary, url, source, category,
                  importance_score, published_at}]
        saved  — сколько новых записей добавлено в БД
        total  — общее количество статей в ответе
        topic  — тема запроса
        model  — модель, которая обрабатывала
    """
    data = parse_json()
    topic = str(data.get("topic") or "новости").strip() or "новости"
    sources = data.get("sources") or []

    articles, error_msg = ai_news_service.fetch_and_process(topic, sources=sources)

    if error_msg and not articles:
        return json_error(error_msg, 503)

    saved_count = ai_news_service.save_to_db(articles, db.session, News)

    return jsonify(
        {
            "news": articles,
            "saved": saved_count,
            "total": len(articles),
            "topic": topic,
            "sources": sources,
            "model": config.OPENROUTER_MODEL,
        }
    )


@app.route("/", methods=["GET"])
def serve_frontend():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:path>", methods=["GET"])
def serve_static(path):
    return send_from_directory(app.static_folder, path)


if __name__ == "__main__":
    print("=" * 50)
    print("IDO SKILLS News started")
    print(f"http://localhost:{config.BACKEND_PORT}")
    print("Railway/PostgreSQL ready build")
    print("=" * 50)
    app.run(host="0.0.0.0", port=config.BACKEND_PORT, debug=config.DEBUG)
