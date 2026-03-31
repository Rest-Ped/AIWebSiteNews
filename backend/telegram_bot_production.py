"""
Telegram-бот для IDO SKILLS News
PRODUCTION VERSION — с управлением прокси, логированием и обработкой ошибок
"""
import logging
import requests
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import telebot
from telebot import types
from telebot import apihelper

# ==================== КОНФИГУРАЦИЯ ====================
class Config:
    """Конфигурация бота"""
    # Токен бота (из переменной окружения или файла)
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8730236171:AAFy_65gvPbjYkMvnxpGyZ5bOirrxUC6rJQ")
    
    # Бэкенд
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000/api")
    
    # Таймауты
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
    BOT_TIMEOUT = int(os.getenv("BOT_TIMEOUT", "30"))
    
    # Прокси (список для перебора)
    PROXY_LIST = [
        p.strip() for p in os.getenv(
            "TELEGRAM_PROXIES", 
            "http://47.88.62.42:80,http://51.159.115.233:3128,http://185.217.137.244:3128"
        ).split(",")
        if p.strip()
    ]
    
    # Логирование
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/telegram_bot.log")
    
    # База данных
    DB_PATH = os.getenv("DB_PATH", "backend/database.db")

config = Config()

# ==================== ЛОГИРОВАНИЕ ====================
def setup_logging():
    """Настройка логирования"""
    log_dir = Path(config.LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ==================== МЕНЕДЖЕР ПРОКСИ ====================
class ProxyManager:
    """Менеджер прокси с авто-перебором и кэшированием"""
    
    def __init__(self, proxy_list: list, timeout: int = 10):
        self.proxy_list = proxy_list
        self.timeout = timeout
        self.current_proxy = None
        self.failed_proxies = set()
        self.successful_proxy = None
        logger.info(f"ProxyManager инициализирован: {len(proxy_list)} прокси")
    
    def test_proxy(self, proxy_url: str) -> bool:
        """Тестирование прокси"""
        try:
            test_url = "https://api.telegram.org"
            proxies = {'http': proxy_url, 'https': proxy_url}
            response = requests.get(
                test_url, 
                proxies=proxies, 
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Прокси {proxy_url} не работает: {e}")
            return False
    
    def get_working_proxy(self) -> str:
        """Получить рабочий прокси"""
        # Если есть успешный прокси, пробуем его сначала
        if self.successful_proxy and self.successful_proxy not in self.failed_proxies:
            if self.test_proxy(self.successful_proxy):
                logger.info(f"Используем проверенный прокси: {self.successful_proxy}")
                return self.successful_proxy
        
        # Перебираем список
        for proxy in self.proxy_list:
            if proxy in self.failed_proxies:
                continue
            
            logger.info(f"Тестируем прокси: {proxy}")
            if self.test_proxy(proxy):
                self.successful_proxy = proxy
                logger.info(f"✅ Рабочий прокси найден: {proxy}")
                return proxy
            
            self.failed_proxies.add(proxy)
        
        return None
    
    def mark_failed(self, proxy_url: str):
        """Отметить прокси как нерабочий"""
        self.failed_proxies.add(proxy_url)
        if self.successful_proxy == proxy_url:
            self.successful_proxy = None
        logger.warning(f"Прокси отмечен как нерабочий: {proxy_url}")
    
    def reset_failed(self):
        """Сбросить список неудачных прокси"""
        self.failed_proxies.clear()
        logger.info("Список неудачных прокси сброшен")

# ==================== ИНИЦИАЛИЗАЦИЯ БОТА ====================
def create_bot_with_retry(max_attempts: int = 3) -> telebot.TeleBot:
    """Создание бота с повторными попытками"""
    proxy_manager = ProxyManager(config.PROXY_LIST, config.REQUEST_TIMEOUT)
    
    for attempt in range(1, max_attempts + 1):
        try:
            # Пробуем без прокси (если VPN включен)
            logger.info(f"Попытка {attempt}/{max_attempts}: подключение без прокси...")
            apihelper.proxy = None
            apihelper.REQUEST_TIMEOUT = config.BOT_TIMEOUT
            
            bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="Markdown")
            bot.get_me()  # Тест подключения
            
            logger.info("✅ Подключение без прокси успешно!")
            return bot, proxy_manager
            
        except Exception as e:
            logger.warning(f"Без прокси не работает: {e}")
        
        # Пробуем с прокси
        working_proxy = proxy_manager.get_working_proxy()
        
        if working_proxy:
            try:
                logger.info(f"Попытка {attempt}/{max_attempts}: подключение через прокси {working_proxy}...")
                apihelper.proxy = {
                    'http': working_proxy,
                    'https': working_proxy
                }
                apihelper.REQUEST_TIMEOUT = config.BOT_TIMEOUT
                
                bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="Markdown")
                bot.get_me()  # Тест подключения
                
                logger.info(f"✅ Подключение через прокси успешно!")
                return bot, proxy_manager
                
            except Exception as e:
                logger.warning(f"Прокси {working_proxy} не работает: {e}")
                proxy_manager.mark_failed(working_proxy)
        else:
            logger.error("Нет рабочих прокси в списке")
        
        if attempt < max_attempts:
            logger.info(f"Ждём 5 секунд перед следующей попыткой...")
            import time
            time.sleep(5)
    
    raise Exception("Не удалось подключиться к Telegram API после всех попыток")

# ==================== ХЕЛПЕРЫ ====================
def get_user_by_telegram_id(telegram_id: int):
    """Получить пользователя из БД по Telegram ID"""
    try:
        response = requests.get(
            f"{config.BACKEND_URL}/users/{telegram_id}", 
            timeout=config.REQUEST_TIMEOUT
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"Backend unavailable: {e}")
    return None

def create_user_in_backend(telegram_id: int, username: str):
    """Создать пользователя в бэкенде"""
    try:
        response = requests.post(
            f"{config.BACKEND_URL}/users",
            json={
                "username": username,
                "email": f"telegram_{telegram_id}@idoskills.local",
                "interests": ["технологии", "новости"]
            },
            timeout=config.REQUEST_TIMEOUT
        )
        if response.status_code == 201:
            return response.json()
    except Exception as e:
        logger.warning(f"Failed to create user: {e}")
    return None

def fetch_news_from_backend(user_id: int):
    """Получить новости из бэкенда"""
    try:
        response = requests.post(
            f"{config.BACKEND_URL}/news/fetch",
            json={"user_id": user_id},
            timeout=config.REQUEST_TIMEOUT
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"Failed to fetch news: {e}")
    return None

def get_digest_from_backend(user_id: int):
    """Получить сводку из бэкенда"""
    try:
        response = requests.get(
            f"{config.BACKEND_URL}/users/{user_id}/digest",
            timeout=config.REQUEST_TIMEOUT
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"Failed to get digest: {e}")
    return None

def update_user_interests(user_id: int, interests: list, threshold: int = 6):
    """Обновить интересы пользователя"""
    try:
        response = requests.put(
            f"{config.BACKEND_URL}/users/{user_id}/interests",
            json={"interests": interests, "threshold": threshold},
            timeout=config.REQUEST_TIMEOUT
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"Failed to update interests: {e}")
    return None

# ==================== КЛАВИАТУРЫ ====================
def main_keyboard():
    """Главное меню бота"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_news = types.KeyboardButton("📰 Новости")
    btn_digest = types.KeyboardButton("📋 Сводка")
    btn_settings = types.KeyboardButton("⚙️ Настройки")
    btn_help = types.KeyboardButton("❓ Помощь")
    markup.add(btn_news, btn_digest)
    markup.add(btn_settings, btn_help)
    return markup

def settings_keyboard():
    """Клавиатура настроек"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    btn_back = types.KeyboardButton("🔙 В меню")
    markup.add(btn_back)
    return markup

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

def cmd_start(message, bot):
    """Приветствие при старте бота"""
    telegram_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    user = get_user_by_telegram_id(telegram_id)
    
    if not user:
        user = create_user_in_backend(telegram_id, username)
        if user:
            bot.reply_to(
                message,
                f"👋 *Добро пожаловать, {username}!*\n\n"
                f"🤖 Я — бот *IDO SKILLS News*\n\n"
                f"✅ Ваш аккаунт создан (ID: `{user['id']}`)\n\n"
                f"📌 *Что я умею:*\n"
                f"• Искать новости по вашим темам\n"
                f"• Оценивать важность через AI\n"
                f"• Формировать краткие сводки\n\n"
                f"Нажмите ⚙️ *Настройки* чтобы начать!",
                reply_markup=main_keyboard()
            )
            logger.info(f"Новый пользователь: {username} (ID: {telegram_id})")
        else:
            bot.reply_to(
                message,
                "⚠️ Ошибка создания аккаунта. Проверьте, запущен ли бэкенд.",
                reply_markup=main_keyboard()
            )
            logger.error(f"Не удалось создать пользователя: {telegram_id}")
    else:
        bot.reply_to(
            message,
            f"👋 *С возвращением, {username}!*\n\nВыберите действие:",
            reply_markup=main_keyboard()
        )
        logger.info(f"Пользователь вернулся: {username} (ID: {telegram_id})")

def cmd_help(message, bot):
    """Справка по боту"""
    bot.reply_to(
        message,
        f"📰 *IDO SKILLS News — Справка*\n\n"
        f"*Команды:*\n"
        f"/start — Запустить бота\n"
        f"/help — Эта справка\n"
        f"/news — Получить новости\n"
        f"/digest — Получить сводку\n"
        f"/settings — Настройки\n\n"
        f"*Как это работает:*\n"
        f"1️⃣ Настройте интересные темы\n"
        f"2️⃣ Бот ищет новости по темам\n"
        f"3️⃣ AI оценивает важность (1-10)\n"
        f"4️⃣ Вы получаете краткую сводку\n\n"
        f"🔗 *Веб-версия:* http://localhost:5000\n"
        f"🏆 *IDO SKILLS 2026*",
        reply_markup=main_keyboard()
    )

def cmd_news(message, bot):
    """Получить новости"""
    telegram_id = message.from_user.id
    user = get_user_by_telegram_id(telegram_id)
    
    if not user:
        bot.reply_to(message, "❌ Сначала нажмите /start")
        return
    
    loading_msg = bot.reply_to(message, "🔄 _Загружаю новости..._")
    
    data = fetch_news_from_backend(user['id'])
    
    if data and data.get('news'):
        news_text = "📰 *НОВОСТИ IDO SKILLS*\n\n"
        for i, news in enumerate(data['news'][:5], 1):
            emoji = "🔥" if news.get('importance_score', 0) >= 8 else "📌"
            news_text += f"{emoji} *{news['title']}*\n"
            news_text += f"   📁 {news.get('source', 'Неизвестно')}\n"
            news_text += f"   ⭐ Важность: {news.get('importance_score', 5)}/10\n"
            news_text += f"   🔗 [Читать]({news['url']})\n\n"
        
        news_text += f"_Всего новостей: {data['count']}_\n"
        news_text += f"_Время: {datetime.now().strftime('%H:%M')}_"
        
        bot.edit_message_text(news_text, loading_msg.chat.id, loading_msg.message_id, reply_markup=main_keyboard())
        logger.info(f"Новости отправлены пользователю {telegram_id}")
    else:
        bot.edit_message_text(
            "⚠️ Новости временно недоступны.\n"
            f"Проверьте бэкенд: `{config.BACKEND_URL}`",
            loading_msg.chat.id,
            loading_msg.message_id,
            reply_markup=main_keyboard()
        )
        logger.warning(f"Не удалось получить новости для {telegram_id}")

def cmd_digest(message, bot):
    """Получить сводку"""
    telegram_id = message.from_user.id
    user = get_user_by_telegram_id(telegram_id)
    
    if not user:
        bot.reply_to(message, "❌ Сначала нажмите /start")
        return
    
    loading_msg = bot.reply_to(message, "🤖 _Генерирую сводку..._")
    
    data = get_digest_from_backend(user['id'])
    
    if data and data.get('digest'):
        digest_text = f"📋 *СВОДКА IDO SKILLS*\n\n{data['digest']}\n\n"
        digest_text += f"_Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}_"
        
        bot.edit_message_text(digest_text, loading_msg.chat.id, loading_msg.message_id, reply_markup=main_keyboard())
        logger.info(f"Сводка отправлена пользователю {telegram_id}")
    else:
        bot.edit_message_text(
            "⚠️ Сводка временно недоступна.\n"
            "Попробуйте позже или получите новости сначала.",
            loading_msg.chat.id,
            loading_msg.message_id,
            reply_markup=main_keyboard()
        )
        logger.warning(f"Не удалось получить сводку для {telegram_id}")

def cmd_settings(message, bot):
    """Настройки пользователя"""
    telegram_id = message.from_user.id
    user = get_user_by_telegram_id(telegram_id)
    
    if not user:
        bot.reply_to(message, "❌ Сначала нажмите /start")
        return
    
    interests = user.get('interests', '[]')
    if interests:
        try:
            interests_list = json.loads(interests)
            interests_str = ", ".join(interests_list) if interests_list else "Не настроены"
        except:
            interests_str = interests
    else:
        interests_str = "Не настроены"
    
    bot.reply_to(
        message,
        f"⚙️ *НАСТРОЙКИ*\n\n"
        f"👤 Пользователь: `{user.get('username', 'Неизвестно')}`\n"
        f"🎯 Темы: _{interests_str}_\n"
        f"⭐ Порог важности: {user.get('news_threshold', 6)}/10\n\n"
        f"📝 *Чтобы изменить темы:*\n"
        f"Отправьте их через запятую:\n"
        f"_Пример: технологии, AI, стартапы_",
        reply_markup=settings_keyboard()
    )

# ==================== ОБРАБОТКА КНОПОК ====================

def btn_news(message, bot):
    cmd_news(message, bot)

def btn_digest(message, bot):
    cmd_digest(message, bot)

def btn_settings(message, bot):
    cmd_settings(message, bot)

def btn_help(message, bot):
    cmd_help(message, bot)

def btn_back(message, bot):
    bot.reply_to(message, "📰 *Главное меню*", reply_markup=main_keyboard())

# ==================== ОБРАБОТКА ТЕКСТА ====================

def handle_text(message, bot):
    """Обработка текстовых сообщений (для настройки тем)"""
    telegram_id = message.from_user.id
    user = get_user_by_telegram_id(telegram_id)
    
    if not user:
        bot.reply_to(message, "❌ Сначала нажмите /start")
        return
    
    if "," in message.text or len(message.text.split()) >= 2:
        topics = [t.strip() for t in message.text.split(",") if t.strip()]
        
        if len(topics) >= 1:
            result = update_user_interests(user['id'], topics, user.get('news_threshold', 6))
            
            if result:
                bot.reply_to(
                    message,
                    f"✅ *Темы обновлены!*\n\n"
                    f"🎯 Ваши темы: _{', '.join(topics)}_\n\n"
                    f"Теперь я буду искать новости по этим темам.",
                    reply_markup=main_keyboard()
                )
                logger.info(f"Темы обновлены для {telegram_id}: {topics}")
            else:
                bot.reply_to(
                    message,
                    "❌ Ошибка обновления тем.\n"
                    f"Проверьте бэкенд: `{config.BACKEND_URL}`",
                    reply_markup=main_keyboard()
                )
                logger.error(f"Не удалось обновить темы для {telegram_id}")

# ==================== ЗАПУСК ====================

def register_handlers(bot):
    """Регистрация обработчиков"""
    
    @bot.message_handler(commands=['start'])
    def start_handler(message):
        cmd_start(message, bot)
    
    @bot.message_handler(commands=['help'])
    def help_handler(message):
        cmd_help(message, bot)
    
    @bot.message_handler(commands=['news'])
    def news_handler(message):
        cmd_news(message, bot)
    
    @bot.message_handler(commands=['digest'])
    def digest_handler(message):
        cmd_digest(message, bot)
    
    @bot.message_handler(commands=['settings'])
    def settings_handler(message):
        cmd_settings(message, bot)
    
    @bot.message_handler(func=lambda message: message.text == "📰 Новости")
    def news_btn_handler(message):
        btn_news(message, bot)
    
    @bot.message_handler(func=lambda message: message.text == "📋 Сводка")
    def digest_btn_handler(message):
        btn_digest(message, bot)
    
    @bot.message_handler(func=lambda message: message.text == "⚙️ Настройки")
    def settings_btn_handler(message):
        btn_settings(message, bot)
    
    @bot.message_handler(func=lambda message: message.text == "❓ Помощь")
    def help_btn_handler(message):
        btn_help(message, bot)
    
    @bot.message_handler(func=lambda message: message.text == "🔙 В меню")
    def back_btn_handler(message):
        btn_back(message, bot)
    
    @bot.message_handler(func=lambda message: True)
    def text_handler(message):
        handle_text(message, bot)

def main():
    """Запуск бота"""
    logger.info("=" * 60)
    logger.info("🤖 Запуск Telegram-бота IDO SKILLS News (PRODUCTION)")
    logger.info("=" * 60)
    logger.info(f"📡 Backend: {config.BACKEND_URL}")
    logger.info(f"🔑 Token: {config.BOT_TOKEN[:20]}...")
    logger.info(f"🌐 Proxies: {len(config.PROXY_LIST)} configured")
    logger.info(f"📝 Log file: {config.LOG_FILE}")
    logger.info("=" * 60)
    
    try:
        # Создаём бота с повторными попытками
        bot, proxy_manager = create_bot_with_retry(max_attempts=5)
        
        # Регистрируем обработчики
        register_handlers(bot)
        
        logger.info("✅ Бот запущен! Ожидание сообщений...")
        logger.info("=" * 60)
        
        # Запускаем polling с обработкой ошибок
        while True:
            try:
                bot.infinity_polling(timeout=config.BOT_TIMEOUT)
            except Exception as e:
                logger.error(f"Ошибка polling: {e}")
                logger.info("Переподключение через 10 секунд...")
                
                # Пробуем пересоздать бота
                import time
                time.sleep(10)
                
                try:
                    bot, proxy_manager = create_bot_with_retry(max_attempts=3)
                    register_handlers(bot)
                    logger.info("✅ Переподключение успешно!")
                except Exception as reconnect_error:
                    logger.error(f"Не удалось переподключиться: {reconnect_error}")
                    logger.info("Ждём 30 секунд перед следующей попыткой...")
                    time.sleep(30)
                    
    except KeyboardInterrupt:
        logger.info("\n👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.error("💡 Проверьте:\n"
                    "  1. Токен бота (@BotFather)\n"
                    "  2. Доступ к Telegram API (VPN/прокси)\n"
                    "  3. Бэкенд запущен и доступен")
        sys.exit(1)

if __name__ == "__main__":
    main()