# Telegram Bot for Video Downloading

Это Telegram-бот, который позволяет скачивать видео с YouTube, Instagram и TikTok. Бот разработан для деплоя на Vercel.

## Функциональность

- Поддержка видео с YouTube, Instagram и TikTok
- Автоматическое определение платформы по ссылке
- Загрузка видео и отправка в чат

## Технологии

- Python
- python-telegram-bot
- Flask
- yt-dlp
- Vercel Serverless Functions

## Установка и запуск

### Локальный запуск

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Установите переменную окружения с токеном бота:
```bash
export BOT_TOKEN="ваш_токен_бота"
```

3. Запустите локальный сервер:
```bash
python test_bot.py
```

### Деплой на Vercel

1. Установите Vercel CLI:
```bash
npm install -g vercel
```

2. Авторизуйтесь в Vercel:
```bash
vercel login
```

3. Сделайте деплой:
```bash
vercel --prod
```

4. В настройках проекта в Vercel добавьте переменную окружения:
   - Ключ: `BOT_TOKEN`
   - Значение: ваш_токен_бота

5. После деплоя настройте вебхук Telegram:
```
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://<YOUR_VERCEL_DOMAIN>/api/webhook
```

## Конфигурация

Файл `vercel.json` содержит конфигурацию для серверлесс-функций Vercel:
- Функция запускается по пути `/api/webhook`
- Максимальное время выполнения: 30 секунд
- Выделенная память: 1024MB

## API эндпоинты

- `GET /` - проверка статуса бота
- `POST /api/webhook` - получение обновлений от Telegram
- `GET /api/health` - проверка работоспособности сервиса

## Переменные окружения

- `BOT_TOKEN` - токен вашего Telegram-бота (обязательно)

## Поддерживаемые платформы

- YouTube
- Instagram
- TikTok