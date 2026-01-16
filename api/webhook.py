import os
import json
import logging
import asyncio
from http.server import BaseHTTPRequestHandler
from urllib.parse import unquote
import requests
import re
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

application = Application.builder().token(TOKEN).build()

def download_with_cobalt(url):
    try:
        resp = requests.post("https://cobalt.tools/api/json", json={"url": url.strip()}, headers={"Accept": "application/json"}, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success" and "url" in data:
                return data["url"]
        return None
    except Exception as e:
        print(f"Cobalt error: {e}")
        return None

def get_platform(url: str) -> str:
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    elif 'instagram.com' in url:
        return 'instagram'
    elif 'tiktok.com' in url:
        return 'tiktok'
    return None

def download_video_yt(url: str) -> str:
    ydl_opts = {'outtmpl': '/tmp/temp_video.%(ext)s', 'format': 'best[height<=720]', 'noplaylist': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        raise Exception(f"Ошибка загрузки: {str(e)}")

def download_video_instagram(url: str) -> str:
    return download_with_cobalt(url)

def download_tiktok_ssstik(url: str) -> str:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    try:
        resp = session.get("https://ssstik.io/")
        token_match = re.search(r'name="_token"\s+value="([^"]+)"', resp.text)
        if not token_match: return None
        token = token_match.group(1)
        resp = session.post("https://ssstik.io/abc?url=dl", data={"_token": token, "url": url.strip()}, timeout=15)
        match = re.search(r'href="(https://[^"]+\.mp4[^"]*)"[^>]*>Without watermark', resp.text)
        return unquote(match.group(1)) if match else None
    except Exception as e:
        print(f"SSSTik error: {e}")
        return None

def download_tiktok_snaptik(url: str) -> str:
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        resp = session.get("https://snaptik.app/")
        token_match = re.search(r'name="token"\s+value="([^"]+)"', resp.text)
        if not token_match: return None
        token = token_match.group(1)
        resp = session.post("https://snaptik.app/abc2.php", data={"token": token, "url": url.strip()}, timeout=15)
        match = re.search(r'href="(https://[^"]+\.mp4[^"]*)"', resp.text)
        return unquote(match.group(1)) if match else None
    except Exception as e:
        print(f"Snaptik error: {e}")
        return None

def download_tiktok_tikwm(url: str) -> str:
    try:
        resp = requests.post("https://tikwm.com/api/", data={"url": url.strip()}, timeout=15)
        if resp.status_code == 200:
            json_data = resp.json()
            if json_data.get("code") == 0:
                return json_data["data"]["play"]
        return None
    except Exception as e:
        print(f"Tikwm error: {e}")
        return None

def download_video_tiktok_ssstik(url: str) -> str:
    for downloader in [download_tiktok_ssstik, download_tiktok_snaptik, download_tiktok_tikwm]:
        link = downloader(url)
        if link:
            return link
    return None

async def send_video(update: Update, file_path: str):
    file_size = os.path.getsize(file_path)
    if file_size > 50 * 1024 * 1024:
        await update.message.reply_document(document=open(file_path, 'rb'))
    else:
        await update.message.reply_video(video=open(file_path, 'rb'))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь ссылку на видео из YouTube, Instagram или TikTok.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    platform = get_platform(url)
    if not platform:
        await update.message.reply_text("Неподдерживаемая ссылка.")
        return

    await update.message.reply_text("Скачиваю...")

    try:
        if platform == 'youtube':
            file_path = download_video_yt(url)
            if file_path and os.path.exists(file_path):
                await send_video(update, file_path)
                os.remove(file_path)
            else:
                await update.message.reply_text("Не удалось скачать.")
        elif platform == 'tiktok':
            video_link = download_video_tiktok_ssstik(url)
            if video_link:
                await update.message.reply_video(video=video_link)
            else:
                await update.message.reply_text("Ошибка TikTok.")
        elif platform == 'instagram':
            video_link = download_video_instagram(url)
            if video_link:
                await update.message.reply_video(video=video_link)
            else:
                await update.message.reply_text("Instagram временно недоступен.")
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await update.message.reply_text(f"Ошибка: {str(e)}")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/webhook":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"webhook ready"}')
        else:
            self.send_response(404)
            self.end_headers()

def do_POST(self):
    if self.path == "/api/webhook":
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        try:
            update = Update.de_json(json.loads(post_data), application.bot)
            asyncio.run(application.process_update(update))
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except Exception as e:
            print("Error:", e)
            self.send_response(500)
            self.end_headers()
    else:
        self.send_response(404)
        self.end_headers()
