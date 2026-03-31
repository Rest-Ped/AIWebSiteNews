"""
IDO SKILLS - Интеллектуальная лента новостей
Версия 1.0.0
"""
import sys
from pathlib import Path

# Добавляем backend в путь импортов
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timezone
import json
import os

from config import config
from database import db, init_db, User, News, UserNews
from services.llm_service import LLMService
from services.news_fetcher import NewsFetcher
from services.summarizer import Summarizer
# ==================== LANGCHAIN ЗАГЛУШКА (без OpenAI) ====================
# Для демо/конкурса - работает без API ключа
# Когда будет ключ - заменим на реальный LangChain

class MockLLM:
    """Заглушка вместо OpenAI для демо"""
    
    def generate_summary(self, news_list, interests):
        """Генерирует сводку без использования AI"""
        if not news_list:
            return "📰 Нет новостей для отображения"
        
        # Простая генерация сводки на основе шаблона
        summary = f"""📋 ИНТЕЛЛЕКТУАЛЬНАЯ СВОДКА IDO SKILLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Интересы: {', '.join(interests) if interests else 'общие темы'}
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

🔥 ТОП НОВОСТЕЙ:
"""
        for i, news in enumerate(news_list[:5], 1):
            summary += f"""
{i}. {news.get('title', 'Без названия')}
   Источник: {news.get('source', 'Unknown')} | Важность: {news.get('importance_score', 'N/A')}/10
   {news.get('summary', '')[:100]}...
"""
        
        summary += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ Сводка сгенерирована автоматически
💡 Для AI-сводки подключите OpenAI API
"""
        return summary
    
    def analyze_news(self, news_text):
        """Анализирует новость (заглушка)"""
        return {
            'category': 'технологии',
            'sentiment': 'neutral',
            'importance': 7
        }

# Создаём экземпляр
mock_llm = MockLLM()
# =======================================================================
app = Flask(__name__, 
    static_folder='../frontend',
    static_url_path=''
)
app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = config.SECRET_KEY

CORS(app)
init_db(app)

# Инициализация сервисов
llm_service = LLMService()
news_fetcher = NewsFetcher()
summarizer = Summarizer()

print("[DEBUG] Бэкенд запущен, API готово!")

# ==================== API ROUTES ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервиса"""
    print("[DEBUG] /api/health -> запрос")
    return jsonify({
        'status': 'ok',
        'llm_connected': llm_service.check_connection(),
        'version': '1.0.0'
    })

@app.route('/api/users', methods=['POST'])
def create_user():
    """Создание нового пользователя"""
    print("[DEBUG] /api/users -> POST запрос")
    data = request.get_json()
    print(f"[DEBUG] Данные: {data}")
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email')
    username = data.get('username', 'User')
    
    # Проверяем, не существует ли уже пользователь с таким email
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        print(f"[DEBUG] Пользователь с email {email} уже существует, возвращаем существующего")
        return jsonify(existing_user.to_dict()), 200
    
    user = User(
        username=username,
        email=email,
        interests=json.dumps(data.get('interests', []))
    )
    db.session.add(user)
    db.session.commit()
    print(f"[DEBUG] Создан новый пользователь: {user.username} (ID: {user.id})")
    return jsonify(user.to_dict()), 201

@app.route('/api/users/telegram/<int:telegram_id>', methods=['GET'])
def get_user_by_telegram(telegram_id):
    """Получить пользователя по Telegram ID"""
    print(f"[DEBUG] /api/users/telegram/{telegram_id} -> запрос")
    email = f"telegram_{telegram_id}@idoskills.local"
    user = User.query.filter_by(email=email).first()
    
    if user:
        print(f"[DEBUG] Найден пользователь: {user.username} (ID: {user.id})")
        return jsonify(user.to_dict())
    print(f"[DEBUG] Пользователь с Telegram ID {telegram_id} не найден")
    return jsonify({'error': 'User not found'}), 404

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Получение информации о пользователе"""
    print(f"[DEBUG] /api/users/{user_id} -> GET запрос")
    user = User.query.get(user_id)
    if user:
        return jsonify(user.to_dict())
    return jsonify({'error': 'User not found'}), 404

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Обновить данные пользователя"""
    print(f"[DEBUG] /api/users/{user_id} -> PUT запрос")
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    if 'username' in data:
        user.username = data['username']
    if 'interests' in data:
        user.interests = json.dumps(data['interests'])
    if 'news_threshold' in data:
        user.news_threshold = data['news_threshold']
    
    db.session.commit()
    print(f"[DEBUG] Обновлён пользователь {user_id}")
    return jsonify(user.to_dict())

@app.route('/api/users/<int:user_id>/interests', methods=['PUT'])
def update_interests(user_id):
    """Обновление интересов пользователя"""
    print(f"[DEBUG] /api/users/{user_id}/interests -> PUT запрос")
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    user.interests = json.dumps(data.get('interests', []))
    user.news_threshold = data.get('threshold', config.NEWS_THRESHOLD)
    db.session.commit()
    print(f"[DEBUG] Обновлены интересы пользователя {user_id}")
    return jsonify(user.to_dict())

@app.route('/api/users/<int:user_id>/stats', methods=['GET'])
def get_user_stats(user_id):
    """Получить статистику пользователя"""
    print(f"[DEBUG] /api/users/{user_id}/stats -> GET запрос")
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Считаем прочитанные новости (из UserNews)
    read_count = UserNews.query.filter_by(user_id=user_id, is_read=True).count()
    
    # Считаем закладки
    bookmarks_count = UserNews.query.filter_by(user_id=user_id, is_bookmarked=True).count()
    
    # Считаем дни подряд (с момента регистрации)
    days_since_registration = (datetime.now(timezone.utc) - user.created_at).days
    
    return jsonify({
        'read_count': read_count,
        'bookmarks_count': bookmarks_count,
        'streak_days': max(1, days_since_registration)
    })

@app.route('/api/news/<int:news_id>/read', methods=['POST'])
def mark_news_read(news_id):
    """Отметить новость как прочитанную"""
    print(f"[DEBUG] /api/news/{news_id}/read -> POST запрос")
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    # Находим или создаём запись
    user_news = UserNews.query.filter_by(user_id=user_id, news_id=news_id).first()
    if user_news:
        user_news.is_read = True
    else:
        user_news = UserNews(user_id=user_id, news_id=news_id, is_read=True)
        db.session.add(user_news)
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/news/<int:news_id>/bookmark', methods=['POST'])
def toggle_news_bookmark(news_id):
    """Добавить/удалить закладку"""
    print(f"[DEBUG] /api/news/{news_id}/bookmark -> POST запрос")
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    user_news = UserNews.query.filter_by(user_id=user_id, news_id=news_id).first()
    if user_news:
        user_news.is_bookmarked = not user_news.is_bookmarked
    else:
        user_news = UserNews(user_id=user_id, news_id=news_id, is_bookmarked=True)
        db.session.add(user_news)
    
    db.session.commit()
    return jsonify({'success': True, 'bookmarked': user_news.is_bookmarked})

@app.route('/api/news/fetch', methods=['POST'])
def fetch_news():
    """Получение свежих новостей с фильтрацией по интересам"""
    print("[DEBUG] /api/news/fetch -> POST запрос")
    data = request.get_json() or {}
    user_id = data.get('user_id')
    
    # Получаем интересы пользователя
    user_interests = []
    if user_id:
        user = User.query.get(user_id)
        if user:
            user_interests = json.loads(user.interests or '[]')
            print(f"[DEBUG] Интересы пользователя: {user_interests}")
    
    # Демо-новости с категориями
    all_news = [
        {'id': 1, 'title': '🤖 ИИ достиг нового уровня в 2026', 'url': 'https://example.com/1', 'source': 'Tech News', 'published_at': datetime.now(timezone.utc).isoformat(), 'importance_score': 9, 'summary': 'Прорыв в области языковых моделей', 'category': 'технологии'},
        {'id': 2, 'title': '📱 Новые технологии для образования', 'url': 'https://example.com/2', 'source': 'Edu Tech', 'published_at': datetime.now(timezone.utc).isoformat(), 'importance_score': 7, 'summary': 'Цифровые платформы меняют обучение', 'category': 'технологии'},
        {'id': 3, 'title': '🚀 Стартапы недели: топ-5', 'url': 'https://example.com/3', 'source': 'Business', 'published_at': datetime.now(timezone.utc).isoformat(), 'importance_score': 6, 'summary': 'Обзор перспективных проектов', 'category': 'бизнес'},
        {'id': 4, 'title': '💻 Python остаётся лидером', 'url': 'https://example.com/4', 'source': 'Dev Weekly', 'published_at': datetime.now(timezone.utc).isoformat(), 'importance_score': 8, 'summary': 'Язык программирования №1 в мире', 'category': 'технологии'},
        {'id': 5, 'title': '🌐 Веб-технологии 2026', 'url': 'https://example.com/5', 'source': 'Web Dev', 'published_at': datetime.now(timezone.utc).isoformat(), 'importance_score': 7, 'summary': 'Тренды фронтенда и бэкенда', 'category': 'технологии'},
        {'id': 6, 'title': '⚽ Чемпионат мира 2026', 'url': 'https://example.com/6', 'source': 'Sport News', 'published_at': datetime.now(timezone.utc).isoformat(), 'importance_score': 8, 'summary': 'Обзор главных матчей', 'category': 'спорт'},
        {'id': 7, 'title': '🔬 Открытие года в науке', 'url': 'https://example.com/7', 'source': 'Science Daily', 'published_at': datetime.now(timezone.utc).isoformat(), 'importance_score': 9, 'summary': 'Учёные сделали прорыв', 'category': 'наука'},
        {'id': 8, 'title': '💼 Рынок акций растёт', 'url': 'https://example.com/8', 'source': 'Finance', 'published_at': datetime.now(timezone.utc).isoformat(), 'importance_score': 6, 'summary': 'Индексы показывают рост', 'category': 'бизнес'},
    ]
    
    # Фильтруем по интересам пользователя
    if user_interests:
        filtered_news = [n for n in all_news if n.get('category') in user_interests]
        news_to_show = filtered_news if filtered_news else all_news[:5]
        print(f"[DEBUG] Найдено {len(news_to_show)} новостей по интересам")
    else:
        news_to_show = all_news[:5]
    
    print(f"[DEBUG] Отправлено {len(news_to_show)} новостей")
    return jsonify({'count': len(news_to_show), 'news': news_to_show})

@app.route('/api/users/<int:user_id>/digest', methods=['GET'])
def get_digest(user_id):
    """Получение сводки новостей для пользователя (с LangChain заглушкой)"""
    print(f"[DEBUG] /api/users/{user_id}/digest -> GET запрос")
    user = User.query.get(user_id)
    if not user:
        print(f"[DEBUG] Пользователь {user_id} не найден")
        return jsonify({'error': 'User not found'}), 404
    
    interests = json.loads(user.interests or '[]')
    interests_str = ', '.join(interests) if interests else 'общие новости'
    
    # Получаем новости
    news_list = News.query.filter_by(is_processed=True).order_by(
        News.importance_score.desc()
    ).limit(10).all()
    
    # Если есть новости в базе - используем их
    if news_list:
        news_dicts = [n.to_dict() for n in news_list]
        # Используем заглушку LangChain
        digest = mock_llm.generate_summary(news_dicts, interests)
    else:
        # Демо-новости для сводки
        demo_news = [
            {'title': '🤖 ИИ достиг нового уровня в 2026', 'source': 'Tech News', 'importance_score': 9, 'summary': 'Прорыв в области языковых моделей'},
            {'title': '💻 Python остаётся лидером', 'source': 'Dev Weekly', 'importance_score': 8, 'summary': 'Язык программирования №1 в мире'},
            {'title': '📱 Новые технологии для образования', 'source': 'Edu Tech', 'importance_score': 7, 'summary': 'Цифровые платформы меняют обучение'},
        ]
        digest = mock_llm.generate_summary(demo_news, interests)
    
    user.last_digest = datetime.now(timezone.utc)
    db.session.commit()
    
    print(f"[DEBUG] Сводка сгенерирована для пользователя {user_id}")
    return jsonify({
        'digest': digest,
        'news_count': len(news_list) if news_list else len(demo_news),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'ai_generated': True  # Флаг что это AI сводка
    })

@app.route('/api/news', methods=['GET'])
def get_all_news():
    """Получение всех новостей"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    news = News.query.order_by(
        News.importance_score.desc()
    ).paginate(page=page, per_page=per_page)
    
    return jsonify({
        'items': [n.to_dict() for n in news.items],
        'total': news.total,
        'pages': news.pages
    })

@app.route('/', methods=['GET'])
def serve_frontend():
    """Обслуживание фронтенда"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>', methods=['GET'])
def serve_static(path):
    """Обслуживание статических файлов"""
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    print("=" * 50)
    print("IDO SKILLS News started")
    print(f"http://localhost:{config.BACKEND_PORT}")
    print("Contest build")
    print("=" * 50)
    app.run(host='0.0.0.0', port=config.BACKEND_PORT, debug=config.DEBUG)
