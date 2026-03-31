# IDO SKILLS News

Новостной сервис с backend на Flask и хранением пользователей в PostgreSQL.

## Что уже реализовано

- регистрация пользователя с сохранением `login`, `password_hash`, `email`, `interests`
- вход по логину и паролю
- выдача auth token для сайта и ПК-клиента
- обновление интересов и настроек через API
- подбор новостей по интересам пользователя
- Railway-ready конфиг для PostgreSQL

## Railway PostgreSQL

1. Добавь в проект Railway новый сервис `PostgreSQL`.
2. Открой Variables у web-сервиса с сайтом.
3. Создай reference variable:

```env
DATABASE_URL=${{PostgreSQL.DATABASE_URL}}
```

4. Добавь секреты:

```env
SECRET_KEY=replace-with-long-random-secret
AUTH_TOKEN_SALT=ido-skills-auth
AUTH_TOKEN_MAX_AGE=604800
DEBUG=false
```

5. Перезапусти deploy.

Railway docs:
- [PostgreSQL](https://docs.railway.com/guides/postgresql)
- [Using Variables](https://docs.railway.com/variables)

## Основные API

### Регистрация

`POST /api/auth/register`

```json
{
  "login": "demo_user",
  "email": "demo@example.com",
  "password": "secret123",
  "interests": ["технологии", "безопасность"],
  "threshold": 7
}
```

### Вход

`POST /api/auth/login`

```json
{
  "login": "demo_user",
  "password": "secret123"
}
```

### Получить профиль

`GET /api/auth/me`

Header:

```text
Authorization: Bearer <token>
```

### Обновить интересы

`PUT /api/users/me/interests`

```json
{
  "interests": ["технологии", "программирование"],
  "threshold": 8
}
```

### Получить новости

`POST /api/news/fetch`

Header:

```text
Authorization: Bearer <token>
```

### Получить сводку

`GET /api/users/me/digest`

Header:

```text
Authorization: Bearer <token>
```

## Для ПК-приложения

ПК-приложение может работать так:

1. Отправить `POST /api/auth/login`
2. Получить `token` и данные пользователя
3. Вызвать `GET /api/auth/me` или `POST /api/news/fetch`
4. Сравнивать интересы пользователя из ответа API с локальной логикой приложения

## Локальный запуск

```bash
bash ./setup.sh build
bash ./setup.sh start
```

Или напрямую:

```bash
cd backend
pip install -r requirements.txt
python app.py
```
