# bot_live_demo.py - Fixed for Render (web service) compatibility
import time
import subprocess
import asyncio
import json
import os
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import RetryAfter, NetworkError
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import threading
from aiohttp import web

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "BOT_TOKEN": "7810330489:AAEyFvyXZuxAwLAubhLEnY6QTg-shHJbx-0",
    "YOUR_USER_ID": "5747051433",
    "CHANNEL_ID": "-1002803181805",
    "SOURCE_URL": "http://g.rosexz.xyz/at/sh/805768?token=SxAKVEBaQ14XUwYBBVYCD1VdBQRSB1cABAAEUVoFBw4JC1ADBQZUAVQTHBNGEEFcBQhpWAASCFcBAABTFUQTR0NXEGpaVkNeFwUHBgxVBAxGSRRFDV1XQA8ABlQKUFcFCAdXGRFCCAAXC15EWQgfGwEdQlQWXlMOalVUElAFAxQKXBdZXx5DC1tuVFRYBV1dRl8UAEYcEAtGQRNeVxMKWhwQAFxHQAAQUBMKX0AIXxVGBllECkRAGxcLEy1oREoUVUoWUF1BCAtbEwoTQRcRFUYMRW4WVUEWR1RQCVwURAwSAkAZEV8AHGpSX19bAVBNDQpYQkYKEFMXHRMJVggPQl9APUVaVkNeW0RcXUg",
    "CLIP_SECONDS": 12,
    "SLEEP_BETWEEN": 0,
    "VIDEO_BITRATE": "3000k",
    "AUDIO_BITRATE": "128k",
    "CRF": "22",
    "WATERMARK_TEXT": "@xl9rr",
    "WATERMARK_MODE": "static",
    "WATERMARK_POSITION": "top-left",
    "ADD_TIMESTAMP": True,
    "BUFFER_SIZE": 3
}

class ConfigManager:
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = self.load_config()
        self.lock = threading.Lock()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    return {**DEFAULT_CONFIG, **loaded}
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        with self.lock:
            self.config[key] = value

    def reload(self):
        self.config = self.load_config()
        return self.config

config = ConfigManager(CONFIG_FILE)

bot: Bot | None = None
clip_queue = Queue(maxsize=config.get("BUFFER_SIZE", 3))
stats = {"clips_sent": 0, "clips_failed": 0, "uptime_start": time.time()}
broadcast_running = False
active_users = [config.get("YOUR_USER_ID")]

print(f"📋 عدد المستخدمين: {len(active_users)}")
print(f"👥 المستخدمين: {active_users}")
print(f"📺 القناة: {config.get('CHANNEL_ID')}")

PORT = int(os.environ.get("PORT", 5000))

# ---------------- Web Server ----------------
async def handle_health(request):
    return web.Response(text="OK", content_type="text/plain")

async def handle_root(request):
    return web.Response(text="", content_type="text/html")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_get('/health', handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"🌐 Web server running on http://0.0.0.0:{PORT}")

# ---------------- Command Handlers ----------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "مجهول"
    if user_id not in active_users:
        active_users.append(user_id)
        print(f"✅ مستخدم جديد: {username} ({user_id})")
    broadcast_status = "🟢 يعمل" if broadcast_running else "🔴 متوقف"
    await update.message.reply_text(
        f"🎬 مرحباً بك!\n✅ تم تسجيلك\n📺 حالة البث: {broadcast_status}\n👤 عدد المشتركين: {len(active_users)}\n📖 اكتب /help لعرض الأوامر"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎬 **دليل استخدام البوت**

📌 **الأوامر العامة:**
• /start - بدء استخدام البوت والتسجيل
• /help - عرض هذه القائمة

📊 **أوامر المالك فقط:**
• /startLIVE - 🟢 بدء البث المباشر
• /stopLIVE - 🔴 إيقاف البث المباشر
• /watermark النص - تغيير النص
• /wmode النمط - static/scroll/bounce/fade/pulse
• /wpos الموقع - مواقع مسبقة أو إحداثيات
• /wspeed الرقم - سرعة الحركة
• /wstyle الخاصية القيمة - التنسيق
• /stats - عرض الإحصائيات
• /reload - إعادة تحميل الإعدادات
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def startlive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global broadcast_running
    if str(update.effective_user.id) != config.get("YOUR_USER_ID"):
        await update.message.reply_text("❌ هذا الأمر للمالك فقط")
        return
    if broadcast_running:
        await update.message.reply_text("⚠️ البث يعمل بالفعل!")
        return
    broadcast_running = True
    await update.message.reply_text("🎬 جاري بدء البث المباشر...")
    asyncio.create_task(broadcast_loop())
    await asyncio.sleep(2)
    await update.message.reply_text(f"✅ تم بدء البث بنجاح!\n📺 المشتركين: {len(active_users)}")

async def stoplive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global broadcast_running
    if str(update.effective_user.id) != config.get("YOUR_USER_ID"):
        await update.message.reply_text("❌ هذا الأمر للمالك فقط")
        return
    if not broadcast_running:
        await update.message.reply_text("⚠️ البث متوقف بالفعل!")
        return
    broadcast_running = False
    await update.message.reply_text("🛑 تم إيقاف البث")

async def any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "مجهول"
    if user_id not in active_users:
        active_users.append(user_id)
        print(f"✅ مستخدم جديد عبر رسالة: {username} ({user_id})")
        await update.message.reply_text("✅ تم تسجيلك تلقائيًا!\n📺 ستستقبل البث")
    else:
        await update.message.reply_text("👍 أنت مسجل بالفعل!")

# ---------------- Helper Functions ----------------
def parse_custom_position(position):
    presets = {
        "top-left": "x=10:y=10",
        "top-right": "x=w-tw-10:y=10",
        "bottom-left": "x=10:y=h-th-10",
        "bottom-right": "x=w-tw-10:y=h-th-10",
        "bottom-center": "x=(w-tw)/2:y=h-th-10",
        "center": "x=(w-tw)/2:y=(h-th)/2",
        "top-center": "x=(w-tw)/2:y=10",
        "center-left": "x=10:y=(h-th)/2",
        "center-right": "x=w-tw-10:y=(h-th)/2"
    }
    return presets.get(position, "x=10:y=10")

def build_ffmpeg_cmd_with_watermark(src, out, duration, v_bitrate, a_bitrate, crf_value, watermark_text="", watermark_mode="static", watermark_position="top-left", add_timestamp=False):
    cmd = ["ffmpeg","-y","-hide_banner","-loglevel","error","-i",src,"-t",str(duration)]
    filters = []
    if watermark_text:
        pos = parse_custom_position(watermark_position)
        filters.append(f"drawtext=text='{watermark_text}':{pos}:fontsize=28:fontcolor=white:borderw=2:bordercolor=black")
    if add_timestamp:
        filters.append("drawtext=text='%{localtime\\:%H\\\\\\:%M\\\\\\:%S}':x=w-tw-10:y=h-th-10:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.5")
    if filters:
        cmd += ["-vf", ",".join(filters)]
    cmd += ["-c:v","libx264","-preset","ultrafast","-crf",str(crf_value),"-c:a","aac","-b:a",a_bitrate,"-movflags","+faststart",out]
    return cmd

def fetch_and_encode_clip(output_path):
    if os.path.exists(output_path):
        os.remove(output_path)
    cmd = build_ffmpeg_cmd_with_watermark(
        config.get("SOURCE_URL"),
        output_path,
        config.get("CLIP_SECONDS"),
        config.get("VIDEO_BITRATE"),
        config.get("AUDIO_BITRATE"),
        config.get("CRF"),
        config.get("WATERMARK_TEXT"),
        config.get("WATERMARK_MODE"),
        config.get("WATERMARK_POSITION"),
        config.get("ADD_TIMESTAMP")
    )
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        return True
    except:
        return False

async def send_clip_to_users(clip_path):
    global stats
    if not os.path.exists(clip_path):
        return False
    try:
        with open(clip_path, "rb") as f:
            await bot.send_video(chat_id=config.get("CHANNEL_ID"), video=f, supports_streaming=True)
    except:
        pass
    for user_id in active_users:
        try:
            with open(clip_path, "rb") as f:
                await bot.send_video(chat_id=user_id, video=f, supports_streaming=True)
        except:
            pass
    stats["clips_sent"] += 1
    try: os.remove(clip_path)
    except: pass
    return True

def clip_producer():
    clip_counter = 0
    while broadcast_running:
        clip_counter += 1
        output_path = f"/tmp/clip_{clip_counter}.mp4"
        if fetch_and_encode_clip(output_path):
            clip_queue.put(output_path)
        else:
            time.sleep(3)

async def clip_consumer():
    while broadcast_running:
        if not clip_queue.empty():
            clip_path = clip_queue.get()
            await send_clip_to_users(clip_path)
        else:
            await asyncio.sleep(0.5)

async def broadcast_loop():
    executor = ThreadPoolExecutor(max_workers=2)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, clip_producer)
    await clip_consumer()

# ---------------- MAIN ----------------
async def main():
    global bot
    asyncio.create_task(start_web_server())
    application = Application.builder().token(config.get("BOT_TOKEN")).build()
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("startLIVE", startlive_command))
    application.add_handler(CommandHandler("stopLIVE", stoplive_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_message))
    bot = application.bot
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, application.run_polling)
    print("✅ البوت يعمل الآن ويستقبل الرسائل...")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
