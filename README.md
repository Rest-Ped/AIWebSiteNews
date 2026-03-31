# IDO SKILLS News

Сайт, backend API, PostgreSQL и Telegram-бот для персональной новостной ленты.

## Что теперь есть

- регистрация и вход по `login/password`
- хранение `email`, `interests`, `news_threshold`
- привязка Telegram к пользователю через БД
- Telegram-бот с кнопками и свободным AI-чатом
- API для сайта, ПК-приложения и бота
- Railway-ready запуск для web и отдельного bot service

## Важные переменные

Основной файл: `.env`

```env
DATABASE_URL=
SECRET_KEY=
AUTH_TOKEN_SALT=ido-skills-auth
AUTH_TOKEN_MAX_AGE=604800
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemini-2.0-flash-001
TELEGRAM_BOT_TOKEN=
BACKEND_PUBLIC_URL=https://your-app.up.railway.app
DEBUG=false
```

Для бота можно использовать `backend/.env.bot`:

```env
TELEGRAM_BOT_TOKEN=
BACKEND_API_URL=https://your-app.up.railway.app
REQUEST_TIMEOUT=30
LOG_LEVEL=INFO
```

## Railway

Web service:

```bash
bash ./setup.sh build
bash ./setup.sh start
```

Bot service:

```bash
bash ./setup.sh build
bash ./setup.sh start-bot
```

Для PostgreSQL в Variables добавь:

```env
DATABASE_URL=${{PostgreSQL.DATABASE_URL}}
```

И отдельно:

```env
SECRET_KEY=replace-with-long-random-secret
AUTH_TOKEN_SALT=ido-skills-auth
AUTH_TOKEN_MAX_AGE=604800
OPENROUTER_API_KEY=...
TELEGRAM_BOT_TOKEN=...
DEBUG=false
```

## Основные API

### Обычная авторизация

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `PUT /api/users/me`
- `PUT /api/users/me/interests`

### Telegram-авторизация

- `POST /api/auth/telegram/register`
- `POST /api/auth/telegram/login`
- `POST /api/auth/telegram/link`
- `POST /api/auth/telegram/unlink`
- `GET /api/users/telegram/<telegram_id>`
- `PUT /api/users/telegram/<telegram_id>/interests`
- `GET /api/users/telegram/<telegram_id>/stats`
- `GET /api/users/telegram/<telegram_id>/digest`

### Новости и ИИ

- `POST /api/news/fetch`
  - работает по `Authorization: Bearer <token>` или по `telegram_id` в JSON
- `GET /api/news`
- `POST /api/news/<news_id>/read`
- `POST /api/news/<news_id>/bookmark`
- `POST /api/assistant/chat`
  - принимает `message` и `token` или `user_id` или `telegram_id`

Пример `POST /api/assistant/chat`:

```json
{
  "telegram_id": 123456789,
  "message": "Что у меня сейчас самое важное и какие интересы?"
}
```

## Локальный запуск

Backend:

```bash
bash ./setup.sh build
bash ./setup.sh start
```

Telegram bot:

```bash
cd backend
python telegram_bot.py
```

В Windows можно просто запустить:

```bat
backend\start_bot.bat
```
