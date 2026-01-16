# Telegram Bot for Video Downloading

Это Telegram-бот, который позволяет скачивать видео с YouTube, Instagram и TikTok. Бот разработан для деплоя на Vercel.

## Функциональность

- Поддержка видео с YouTube, Instagram и TikTok
- Автоматическое определение платформы по ссылке
- Загрузка видео и отправка в чат

## Технологии

- Python
- aiogram 3.x
- yt-dlp
- Vercel Serverless Functions

## Установка и запуск

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
   - Key: TELEGRAM_BOT_TOKEN
   - Value: ваш_токен_бота
   - Установите галочку "Encrypted" для шифрования

5. После деплоя настройте вебхук Telegram:
```
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<YOUR_VERCEL_DOMAIN>/api/webhook
```

## Конфигурация

Файл `vercel.json` содержит конфигурацию для серверлесс-функций Vercel:
- Функция запускается по пути `/api/webhook`
- Максимальное время выполнения: 30 секунд
- Выделенная память: 1024MB

## API эндпоинты

- `GET /api/webhook` - проверка статуса бота
- `POST /api/webhook` - получение обновлений от Telegram

## Переменные окружения

- `TELEGRAM_BOT_TOKEN` - токен вашего Telegram-бота (обязательно)

## Поддерживаемые платформы

- YouTube
- Instagram
- TikTok