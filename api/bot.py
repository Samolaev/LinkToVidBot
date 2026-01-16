import os
import logging
import requests
import re
from urllib.parse import unquote
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('BOT_TOKEN')

if not TOKEN:
    raise ValueError("Необходимо указать токен бота в переменной окружения BOT_TOKEN")

# Создание Flask-приложения
app = Flask(__name__)

def download_with_cobalt(url):
    """
    Скачивает видео/фото с Instagram, TikTok, YouTube через cobalt.tools
    Возвращает прямую ссылку или None
    """
    try:
        api_url = "https://cobalt.tools/api/json"
        payload = {
            "url": url.strip(),
            "download_mode": "audio"  # не нужно, но иногда помогает обойти лимиты
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }

        resp = requests.post(api_url, json=payload, headers=headers, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success" and "url" in data:
                return data["url"]
        return None

    except Exception as e:
        print(f"Cobalt error: {e}")
        return None

def create_application():
    """Create a new instance of the Telegram bot application"""
    return Application.builder().token(TOKEN).build()

# Глобальная переменная для хранения приложения
application = create_application()

@app.route('/api/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        try:
            import asyncio
            update_data = request.get_json()
            update = Update.de_json(update_data)
            
            # Run the async process_update in an event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(application.process_update(update))
            loop.close()
            
            return 'ok'
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return 'error', 500
    else:
        # Ответ на GET-запрос (для проверки)
        return jsonify({'status': 'webhook is ready'}), 200

@app.route('/')
def home():
    return jsonify({'status': 'Bot is running!'}), 200

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'telegram-bot'}), 200

# Функция для определения платформы по URL
def get_platform(url: str) -> str:
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    elif 'instagram.com' in url:
        return 'instagram'
    elif 'tiktok.com' in url:
        return 'tiktok'
    else:
        return None

# Функция для скачивания видео с YouTube или TikTok с помощью yt-dlp
def download_video_yt(url: str) -> str:
    ydl_opts = {
        'outtmpl': 'temp_video.%(ext)s',
        'format': 'best[height<=720]',  # Высокое качество, но ограничено для избежания слишком больших файлов
        'noplaylist': True,  # Скачивать только одно видео
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
    except yt_dlp.DownloadError as e:
        raise Exception(f"Ошибка загрузки: {str(e)}")

# Функция для скачивания видео с Instagram через igram.io
def download_instagram_igram(url: str) -> str:
    """Скачивает видео/фото с Instagram через igram.io"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://igram.io/"
    })

    try:
        # Заменяем www на m для лучшей совместимости
        url = url.replace("www.instagram.com", "m.instagram.com")

        # Шаг 1: Получаем страницу загрузки
        resp = session.get("https://igram.io/")
        if resp.status_code != 200:
            return None

        # Шаг 2: Отправляем ссылку
        data = {"url": url.strip()}
        resp = session.post("https://igram.io/api/", data=data, timeout=15)

        if resp.status_code != 200:
            return None

        # Шаг 3: Извлекаем прямую ссылку
        # igram.io возвращает JSON вида: {"data": [{"url": "...", "type": "video"}]}
        json_data = resp.json()
        if "data" in json_data and len(json_data["data"]) > 0:
            item = json_data["data"][0]
            if item.get("type") == "video":
                return unquote(item["url"])
            elif item.get("type") == "image":
                return unquote(item["url"])
        return None

    except Exception as e:
        print(f"igram.io error: {e}")
        return None

# Функция для скачивания видео с Instagram через saveig.org
def download_instagram_saveig(url: str) -> str:
    """Запасной вариант: saveig.org"""
    try:
        # Заменяем www на m для лучшей совместимости
        url = url.replace("www.instagram.com", "m.instagram.com")

        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})

        # Простой GET-запрос — saveig часто работает без токена
        api_url = "https://saveig.org/api/ajaxSearch"
        data = {"q": url.strip()}
        resp = session.post(api_url, data=data, timeout=15)

        if resp.status_code == 200:
            html = resp.json().get("data", "")
            # Ищем ссылку на видео
            match = re.search(r'href="([^"]+\.mp4[^"]*)"', html)
            if match:
                return unquote(match.group(1))
        return None
    except Exception as e:
        print(f"saveig.org error: {e}")
        return None

# Основная функция для Instagram
def download_video_instagram(url: str) -> str:
    return download_with_cobalt(url)

# Функция для скачивания видео с TikTok с помощью ssstik.io
def download_tiktok_ssstik(url: str) -> str:
    """
    Скачивает видео с TikTok через ssstik.io
    Возвращает прямую ссылку на видео без водяного знака или None
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    try:
        # 1. Получаем главную страницу, чтобы извлечь токен и cookies
        resp = session.get("https://ssstik.io/")
        if resp.status_code != 200:
            return None

        # Ищем токен в HTML (часто в скрытом input)
        token_match = re.search(r'name="_token"\s+value="([^"]+)"', resp.text)
        if not token_match:
            return None
        token = token_match.group(1)

        # 2. Отправляем ссылку на видео
        post_data = {
            "_token": token,
            "url": url.strip(),
            "locale": "en"
        }

        resp = session.post("https://ssstik.io/abc?url=dl", data=post_data, timeout=15)
        if resp.status_code != 200:
            return None

        # 3. Извлекаем ссылку на видео без водяного знака
        # Новые версии ssstik возвращают JSON или HTML с <a> тегами
        if 'application/json' in resp.headers.get('Content-Type', ''):
            json_data = resp.json()
            # Иногда ссылка в base64 или закодирована
            if "link" in json_data:
                return json_data["link"]
        else:
            # Парсим HTML
            match = re.search(r'href="(https://[^"]+\.mp4[^"]*)"[^>]*>Without watermark', resp.text)
            if match:
                return unquote(match.group(1))  # раскодируем URL

        return None

    except Exception as e:
        print(f"SSSTik error: {e}")
        return None

# Функция для скачивания видео с TikTok с помощью snaptik.app
def download_tiktok_snaptik(url: str) -> str:
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        resp = session.get("https://snaptik.app/")
        if resp.status_code != 200:
            return None

        token_match = re.search(r'name="token"\s+value="([^"]+)"', resp.text)
        if not token_match:
            return None
        token = token_match.group(1)

        post_data = {
            "token": token,
            "url": url.strip()
        }

        resp = session.post("https://snaptik.app/abc2.php", data=post_data, timeout=15)
        if resp.status_code != 200:
            return None

        match = re.search(r'href="(https://[^"]+\.mp4[^"]*)"', resp.text)
        if match:
            return unquote(match.group(1))

        return None

    except Exception as e:
        print(f"Snaptik error: {e}")
        return None

# Функция для скачивания видео с TikTok с помощью tikwm.com
def download_tiktok_tikwm(url: str) -> str:
    try:
        api_url = "https://tikwm.com/api/"
        data = {"url": url.strip(), "hd": 1}

        resp = requests.post(api_url, data=data, timeout=15)
        if resp.status_code != 200:
            return None

        json_data = resp.json()
        if json_data.get("code") == 0 and "data" in json_data:
            return json_data["data"]["play"]

        return None

    except Exception as e:
        print(f"Tikwm error: {e}")
        return None

# Основная функция для TikTok
def download_video_tiktok_ssstik(url: str) -> str:
    downloaders = [download_tiktok_ssstik, download_tiktok_snaptik, download_tiktok_tikwm]
    for downloader in downloaders:
        link = downloader(url)
        if link:
            return link
    return None

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для скачивания видео.\n"
        "Отправь мне ссылку на видео из YouTube, Instagram (посты/рилсы) или TikTok, и я скачаю его для тебя.\n"
        "Поддерживаются только публичные видео. Размер файла не должен превышать 50 МБ."
    )

# Обработчик текстовых сообщений (ссылок)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    platform = get_platform(url)
    if not platform:
        await update.message.reply_text("Неподдерживаемая ссылка. Поддерживаются YouTube, Instagram и TikTok.")
        return

    await update.message.reply_text("Начинаю скачивание... Пожалуйста, подождите.")

    try:
        if platform == 'youtube':
            file_path = download_video_yt(url)
            if file_path and os.path.exists(file_path):
                await update.message.reply_video(video=open(file_path, 'rb'))
                os.remove(file_path)
            else:
                await update.message.reply_text("Не удалось скачать видео.")
        elif platform == 'tiktok':
            video_link = download_video_tiktok_ssstik(url)
            if video_link:
                await update.message.reply_video(video=video_link)
            else:
                await update.message.reply_text("Не удалось скачать видео с TikTok. Попробуйте другую ссылку.")
        elif platform == 'instagram':
            video_link = download_video_instagram(url)
            if video_link:
                await update.message.reply_video(video=video_link)
            else:
                await update.message.reply_text("⚠️ Instagram временно не поддерживается из-за ограничений Meta.\nПопробуйте TikTok или YouTube!")
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await update.message.reply_text(f"Ошибка: {str(e)}")

# Регистрация обработчиков команд
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Для Vercel экспорт handler как default
handler = app