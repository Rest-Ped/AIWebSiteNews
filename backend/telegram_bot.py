"""
Telegram-бот для IDO SKILLS News
PRODUCTION VERSION — полностью рабочий для конкурса
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
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8730236171:AAFy_65gvPbjYkMvnxpGyZ5bOirrxUC6rJQ")
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000/api")
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    BOT_TIMEOUT = int(os.getenv("BOT_TIMEOUT", "30"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/telegram_bot.log")

config = Config()

# ==================== ЛОГИРОВАНИЕ ====================
def setup_logging():
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

# ==================== ИНИЦИАЛИЗАЦИЯ БОТА ====================
def create_bot():
    logger.info("=" * 60)
    logger.info("🤖 Запуск Telegram-бота IDO SKILLS News")
    logger.info("=" * 60)
    logger.info(f"📡 Backend: {config.BACKEND_URL}")
    logger.info(f"🔑 Token: {config.BOT_TOKEN[:20]}...")
    logger.info(f"⏱️ Timeout: {config.REQUEST_TIMEOUT}s")
    logger.info(f"📝 Log file: {config.LOG_FILE}")
    logger.info("=" * 60)
    
    try:
        # Пробуем без прокси (VPN должен быть включен)
        logger.info("🔑 Попытка подключения без прокси...")
        apihelper.proxy = None
        apihelper.REQUEST_TIMEOUT = config.BOT_TIMEOUT
        
        bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="Markdown")
        me = bot.get_me()
        
        logger.info(f"✅ Подключение успешно!")
        logger.info(f"🤖 Bot username: @{me.username}")
        logger.info(f"👤 Bot name: {me.first_name}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info("=" * 60)
        
        return bot
        
    except Exception as e:
        logger.error(f"❌ Ошибка подключения: {e}")
        logger.error("💡 Проверьте:\n"
                    "  1. Токен бота (@BotFather)\n"
                    "  2. VPN включен\n"
                    "  3. Интернет работает")
        raise

bot = create_bot()

# ==================== ХЕЛПЕРЫ ====================

def get_user_by_telegram_id(telegram_id: int):
    """Получить пользователя из БД по Telegram ID"""
    logger.debug(f"🔍 Поиск пользователя: telegram_id={telegram_id}")
    
    try:
        url = f"{config.BACKEND_URL}/users/telegram/{telegram_id}"
        logger.debug(f"📡 GET {url}")
        
        response = requests.get(url, timeout=config.REQUEST_TIMEOUT)
        
        logger.debug(f"📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            user_data = response.json()
            logger.info(f"✅ Пользователь найден: {user_data.get('username', 'Unknown')} (ID: {user_data.get('id')})")
            return user_data
        elif response.status_code == 404:
            logger.info(f"ℹ️ Пользователь не найден (404)")
            return None
        else:
            logger.warning(f"⚠️ Неожиданный статус: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения пользователя: {e}")
        return None

def create_user_in_backend(telegram_id: int, username: str):
    """Создать пользователя в бэкенде"""
    logger.debug(f"➕ Создание пользователя: telegram_id={telegram_id}, username={username}")
    
    email = f"telegram_{telegram_id}@idoskills.local"
    logger.debug(f"📧 Email: {email}")
    
    try:
        url = f"{config.BACKEND_URL}/users"
        payload = {
            "username": username,
            "email": email,
            "interests": ["технологии", "новости"]
        }
        
        logger.debug(f"📡 POST {url}")
        logger.debug(f"📤 Payload: {json.dumps(payload, ensure_ascii=False)}")
        
        response = requests.post(
            url,
            json=payload,
            timeout=config.REQUEST_TIMEOUT
        )
        
        logger.debug(f"📥 Response status: {response.status_code}")
        
        if response.status_code == 201:
            user_data = response.json()
            logger.info(f"✅ Пользователь создан: {user_data.get('username')} (ID: {user_data.get('id')})")
            return user_data
        elif response.status_code == 200:
            # Пользователь уже существует
            user_data = response.json()
            logger.info(f"ℹ️ Пользователь уже существует: {user_data.get('username')} (ID: {user_data.get('id')})")
            return user_data
        else:
            logger.error(f"❌ Ошибка {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка создания пользователя: {e}")
        return None

def fetch_news_from_backend(user_id: int):
    """Получить новости из бэкенда"""
    logger.debug(f"📰 Получение новостей для user_id={user_id}")
    
    try:
        url = f"{config.BACKEND_URL}/news/fetch"
        payload = {"user_id": user_id}
        
        logger.debug(f"📡 POST {url}")
        
        response = requests.post(
            url,
            json=payload,
            timeout=config.REQUEST_TIMEOUT
        )
        
        logger.debug(f"📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Получено новостей: {data.get('count', 0)}")
            return data
        else:
            logger.warning(f"⚠️ Статус: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения новостей: {e}")
        return None

def get_digest_from_backend(user_id: int):
    """Получить сводку из бэкенда"""
    logger.debug(f"📋 Получение сводки для user_id={user_id}")
    
    try:
        url = f"{config.BACKEND_URL}/users/{user_id}/digest"
        logger.debug(f"📡 GET {url}")
        
        response = requests.get(url, timeout=config.REQUEST_TIMEOUT)
        
        logger.debug(f"📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Сводка получена: {len(data.get('digest', ''))} символов")
            return data
        else:
            logger.warning(f"⚠️ Статус: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения сводки: {e}")
        return None

def update_user_interests(user_id: int, interests: list, threshold: int = 6):
    """Обновить интересы пользователя"""
    logger.debug(f"⚙️ Обновление интересов: user_id={user_id}, interests={interests}")
    
    try:
        url = f"{config.BACKEND_URL}/users/{user_id}/interests"
        payload = {"interests": interests, "threshold": threshold}
        
        logger.debug(f"📡 PUT {url}")
        
        response = requests.put(
            url,
            json=payload,
            timeout=config.REQUEST_TIMEOUT
        )
        
        logger.debug(f"📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"✅ Интересы обновлены")
            return response.json()
        else:
            logger.warning(f"⚠️ Статус: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка обновления интересов: {e}")
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

@bot.message_handler(commands=['start'])
def cmd_start(message):
    logger.info("=" * 60)
    logger.info(f"📨 Команда /start")
    logger.info(f"👤 Telegram ID: {message.from_user.id}")
    logger.info(f"👤 Username: {message.from_user.username}")
    logger.info("=" * 60)
    
    telegram_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or "User"
    
    # Пробуем найти пользователя
    logger.info("🔍 Поиск пользователя в базе...")
    user = get_user_by_telegram_id(telegram_id)
    
    if not user:
        logger.info("➕ Пользователь не найден, создаём нового...")
        user = create_user_in_backend(telegram_id, username)
        
        if user:
            logger.info(f"✅ Пользователь успешно создан/найден: ID={user.get('id')}")
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
        else:
            logger.error("❌ Не удалось создать пользователя")
            bot.reply_to(
                message,
                "⚠️ Ошибка создания аккаунта.\n\n"
                f"🔍 Проверьте:\n"
                f"• Бэкенд запущен: `{config.BACKEND_URL}`\n"
                f"• VPN включен\n"
                f"• Токен бота верный",
                reply_markup=main_keyboard()
            )
    else:
        logger.info(f"✅ Пользователь найден: ID={user.get('id')}")
        bot.reply_to(
            message,
            f"👋 *С возвращением, {username}!*\n\n"
            f"Ваш ID: `{user['id']}`\n\n"
            f"Выберите действие:",
            reply_markup=main_keyboard()
        )

@bot.message_handler(commands=['help'])
def cmd_help(message):
    logger.info(f"📨 Команда /help от {message.from_user.id}")
    
    bot.reply_to(
        message,
        f"📰 *IDO SKILLS News — Справка*\n\n"
        f"*Команды:*\n"
        f"/start — Запустить бота\n"
        f"/help — Эта справка\n"
        f"/news — Получить новости\n"
        f"/digest — Получить сводку\n"
        f"/settings — Настройки\n\n"
        f"🔗 *Веб-версия:* http://localhost:5000\n"
        f"🏆 *IDO SKILLS 2026*",
        reply_markup=main_keyboard()
    )

@bot.message_handler(commands=['news'])
def cmd_news(message):
    logger.info(f"📨 Команда /news от {message.from_user.id}")
    
    telegram_id = message.from_user.id
    user = get_user_by_telegram_id(telegram_id)
    
    if not user:
        bot.reply_to(message, "❌ Сначала нажмите /start")
        logger.warning(f"❌ Пользователь {telegram_id} не найден")
        return
    
    logger.info(f"📰 Получение новостей для пользователя {user.get('id')}")
    
    # Отправляем сообщение "Загружаю..."
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
        
        news_text += f"_Всего новостей: {data['count']}_"
        
        # ИСПРАВЛЕНО: используем reply_to вместо edit_message_text
        bot.reply_to(message, news_text, parse_mode="Markdown", reply_markup=main_keyboard())
        logger.info(f"✅ Новости отправлены")
    else:
        bot.reply_to(message, "⚠️ Новости временно недоступны.\nПроверьте бэкенд.", reply_markup=main_keyboard())
        logger.warning("⚠️ Новости не получены")

@bot.message_handler(commands=['digest'])
def cmd_digest(message):
    logger.info(f"📨 Команда /digest от {message.from_user.id}")
    
    telegram_id = message.from_user.id
    user = get_user_by_telegram_id(telegram_id)
    
    if not user:
        bot.reply_to(message, "❌ Сначала нажмите /start")
        return
    
    logger.info(f"📋 Получение сводки для пользователя {user.get('id')}")
    
    # Отправляем сообщение "Генерирую..."
    loading_msg = bot.reply_to(message, "🤖 _Генерирую сводку..._")
    
    data = get_digest_from_backend(user['id'])
    
    if data and data.get('digest'):
        digest_text = f"📋 *СВОДКА IDO SKILLS*\n\n{data['digest']}\n\n"
        digest_text += f"_Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}_"
        
        # ИСПРАВЛЕНО: используем reply_to вместо edit_message_text
        bot.reply_to(message, digest_text, parse_mode="Markdown", reply_markup=main_keyboard())
        logger.info(f"✅ Сводка отправлена")
    else:
        bot.reply_to(message, "⚠️ Сводка временно недоступна.\nПопробуйте позже.", reply_markup=main_keyboard())
        logger.warning("⚠️ Сводка не получена")

@bot.message_handler(commands=['settings'])
def cmd_settings(message):
    logger.info(f"📨 Команда /settings от {message.from_user.id}")
    
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

@bot.message_handler(func=lambda message: message.text == "📰 Новости")
def btn_news(message):
    logger.info(f"🔘 Кнопка 'Новости' от {message.from_user.id}")
    cmd_news(message)

@bot.message_handler(func=lambda message: message.text == "📋 Сводка")
def btn_digest(message):
    logger.info(f"🔘 Кнопка 'Сводка' от {message.from_user.id}")
    cmd_digest(message)

@bot.message_handler(func=lambda message: message.text == "⚙️ Настройки")
def btn_settings(message):
    logger.info(f"🔘 Кнопка 'Настройки' от {message.from_user.id}")
    cmd_settings(message)

@bot.message_handler(func=lambda message: message.text == "❓ Помощь")
def btn_help(message):
    logger.info(f"🔘 Кнопка 'Помощь' от {message.from_user.id}")
    cmd_help(message)

@bot.message_handler(func=lambda message: message.text == "🔙 В меню")
def btn_back(message):
    logger.info(f"🔘 Кнопка 'В меню' от {message.from_user.id}")
    bot.reply_to(message, "📰 *Главное меню*", reply_markup=main_keyboard())

# ==================== ОБРАБОТКА ТЕКСТА ====================

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    logger.info(f"📨 Текст от {message.from_user.id}: '{message.text}'")
    
    telegram_id = message.from_user.id
    user = get_user_by_telegram_id(telegram_id)
    
    if not user:
        bot.reply_to(message, "❌ Сначала нажмите /start")
        return
    
    if "," in message.text or len(message.text.split()) >= 2:
        topics = [t.strip() for t in message.text.split(",") if t.strip()]
        
        if len(topics) >= 1:
            logger.info(f"⚙️ Обновление тем: {topics}")
            result = update_user_interests(user['id'], topics, user.get('news_threshold', 6))
            
            if result:
                bot.reply_to(
                    message,
                    f"✅ *Темы обновлены!*\n\n"
                    f"🎯 Ваши темы: _{', '.join(topics)}_\n\n"
                    f"Теперь я буду искать новости по этим темам.",
                    reply_markup=main_keyboard()
                )
                logger.info(f"✅ Темы обновлены успешно")
            else:
                bot.reply_to(
                    message,
                    "❌ Ошибка обновления тем.\n"
                    f"Проверьте бэкенд: `{config.BACKEND_URL}`",
                    reply_markup=main_keyboard()
                )
                logger.error("❌ Ошибка обновления тем")

# ==================== ЗАПУСК ====================

def main():
    logger.info("🚀 Запуск polling...")
    
    try:
        bot.infinity_polling(timeout=config.BOT_TIMEOUT)
    except KeyboardInterrupt:
        logger.info("\n👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()