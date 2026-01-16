import json
import os
import logging
import requests
import re
from urllib.parse import unquote
from http.server import BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import yt_dlp

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение токена из переменных окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

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

# Функция для скачивания видео с YouTube
def download_video_yt(url: str) -> str:
    ydl_opts = {
        'outtmpl': 'temp_video.%(ext)s',
        'format': 'best[height<=720]',
        'noplaylist': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
    except yt_dlp.DownloadError as e:
        raise Exception(f"Ошибка загрузки: {str(e)}")

# Функция для скачивания видео с TikTok
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

# Функция для скачивания видео с TikTok (резервный вариант)
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

# Функция для скачивания видео с TikTok (еще один резервный вариант)
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

# Основная функция для Instagram
def download_video_instagram(url: str) -> str:
    return download_with_cobalt(url)

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот для скачивания видео.\n"
        "Отправь мне ссылку на видео из YouTube, Instagram (посты/рилсы) или TikTok, и я скачаю его для тебя.\n"
        "Поддерживаются только публичные видео. Размер файла не должен превышать 50 МБ."
    )

# Обработчик текстовых сообщений (ссылок)
@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        return
        
    url = message.text.strip()
    platform = get_platform(url)
    if not platform:
        await message.answer("Неподдерживаемая ссылка. Поддерживаются YouTube, Instagram и TikTok.")
        return

    await message.answer("Начинаю скачивание... Пожалуйста, подождите.")

    try:
        if platform == 'youtube':
            file_path = download_video_yt(url)
            if file_path and os.path.exists(file_path):
                await message.answer_video(video=types.FSInputFile(file_path))
                os.remove(file_path)
            else:
                await message.answer("Не удалось скачать видео.")
        elif platform == 'tiktok':
            video_link = download_video_tiktok_ssstik(url)
            if video_link:
                await message.answer_video(video=video_link)
            else:
                await message.answer("Не удалось скачать видео с TikTok. Попробуйте другую ссылку.")
        elif platform == 'instagram':
            video_link = download_video_instagram(url)
            if video_link:
                await message.answer_video(video=video_link)
            else:
                await message.answer("⚠️ Instagram временно не поддерживается из-за ограничений Meta.\nПопробуйте TikTok или YouTube!")
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await message.answer(f"Ошибка: {str(e)}")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/webhook':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "webhook is ready"}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/webhook':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                # Декодируем полученные данные
                update_data = json.loads(post_data.decode('utf-8'))
                
                # Создаем объект Update из aiogram
                update = types.Update(**update_data)
                
                # Запускаем обработку обновления
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(dp.feed_update(bot, update))
                loop.close()
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'OK')
            except Exception as e:
                logger.error(f"Error processing webhook: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.info(f"{format % args}")