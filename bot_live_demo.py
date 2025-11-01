
# bot_live_demo.py - Enhanced Version with Dynamic Watermark
import time
import subprocess
import asyncio
import json
import os
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import threading

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "BOT_TOKEN": "7810330489:AAEyFvyXZuxAwLAubhLEnY6QTg-shHJbx-0",
    "YOUR_USER_ID": "5747051433",
    "CHANNEL_ID": "-1002803181805",
    "SOURCE_URL": "https://hamada-tv.site/alwan1/index.m3u8",
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
            except:
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
bot = Bot(token=config.get("BOT_TOKEN"))

clip_queue = Queue(maxsize=config.get("BUFFER_SIZE", 3))
stats = {"clips_sent": 0, "clips_failed": 0, "uptime_start": time.time()}

# قائمة المستخدمين في الذاكرة فقط - بدون حفظ
active_users = [config.get("YOUR_USER_ID")]
print(f"📋 عدد المستخدمين: {len(active_users)}")
print(f"👥 المستخدمين: {active_users}")
print(f"📺 القناة: {config.get('CHANNEL_ID')}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "مجهول"
    
    if user_id not in active_users:
        active_users.append(user_id)
        print(f"✅ مستخدم جديد: {username} ({user_id})")
    
    await update.message.reply_text(
        "🎬 مرحباً بك في بوت البث المباشر!\n\n"
        "✅ تم تسجيلك بنجاح\n"
        "📺 سوف تستقبل البث المباشر تلقائياً\n\n"
        f"👤 عدد المشتركين: {len(active_users)}\n\n"
        "📖 اكتب /help لعرض جميع الأوامر المتاحة"
    )

async def any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "مجهول"
    
    if user_id not in active_users:
        active_users.append(user_id)
        print(f"✅ مستخدم جديد عبر رسالة: {username} ({user_id})")
        await update.message.reply_text(
            "✅ تم تسجيلك تلقائياً!\n"
            "📺 سوف تستقبل البث المباشر"
        )
    else:
        await update.message.reply_text("👍 أنت مسجل بالفعل!")

async def watermark_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != config.get("YOUR_USER_ID"):
        await update.message.reply_text("❌ هذا الأمر للمالك فقط")
        return
    
    if not context.args:
        await update.message.reply_text(
            f"📝 النص الحالي: {config.get('WATERMARK_TEXT')}\n\n"
            "استخدم: /watermark النص الجديد"
        )
        return
    
    new_text = " ".join(context.args)
    config.set("WATERMARK_TEXT", new_text)
    
    await update.message.reply_text(f"✅ تم تغيير العلامة المائية إلى:\n{new_text}")

async def wmode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != config.get("YOUR_USER_ID"):
        await update.message.reply_text("❌ هذا الأمر للمالك فقط")
        return
    
    if not context.args:
        current = config.get('WATERMARK_MODE')
        await update.message.reply_text(
            f"🎬 النمط الحالي: {current}\n\n"
            "🎨 الأنماط المتاحة:\n\n"
            "١️⃣ `/wmode static` - ثابت 📌\n"
            "٢️⃣ `/wmode scroll` - يتحرك ← 🏃\n"
            "٣️⃣ `/wmode bounce` - يرتد ↔️ 🎾\n\n"
            "💡 اضغط على الأمر مباشرة!"
        )
        return
    
    mode = context.args[0].lower().lstrip('/')
    
    # اختصارات
    shortcuts = {
        "s": "static",
        "sc": "scroll", 
        "b": "bounce"
    }
    
    if mode in shortcuts:
        mode = shortcuts[mode]
    
    if mode not in ["static", "scroll", "bounce"]:
        await update.message.reply_text(
            "❌ نمط غير صحيح!\n\n"
            "استخدم: static, scroll, bounce\n"
            "أو: s, sc, b"
        )
        return
    
    config.set("WATERMARK_MODE", mode)
    
    icons = {"static": "📌", "scroll": "🏃", "bounce": "🎾"}
    await update.message.reply_text(
        f"✅ تم تغيير نمط الحركة!\n\n"
        f"{icons.get(mode, '')} النمط الجديد: {mode}"
    )

async def wpos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != config.get("YOUR_USER_ID"):
        await update.message.reply_text("❌ هذا الأمر للمالك فقط")
        return
    
    if not context.args:
        current = config.get('WATERMARK_POSITION')
        await update.message.reply_text(
            f"📍 الموقع الحالي: {current}\n\n"
            "🎯 المواقع المتاحة:\n\n"
            "١️⃣ `/wpos top-left` - أعلى اليسار ↖️\n"
            "٢️⃣ `/wpos top-right` - أعلى اليمين ↗️\n"
            "٣️⃣ `/wpos bottom-left` - أسفل اليسار ↙️\n"
            "٤️⃣ `/wpos bottom-right` - أسفل اليمين ↘️\n"
            "٥️⃣ `/wpos bottom-center` - أسفل المنتصف ⬇️\n"
            "٦️⃣ `/wpos center` - المنتصف 🎯\n\n"
            "💡 يمكنك أيضاً الضغط على الأمر مباشرة!"
        )
        return
    
    # تنظيف الإدخال - إزالة / إذا كتبها المستخدم
    position = context.args[0].lower().lstrip('/')
    
    valid_positions = ["top-left", "top-right", "bottom-left", "bottom-right", "bottom-center", "center"]
    
    # إذا كتب المستخدم اختصار
    shortcuts = {
        "tl": "top-left",
        "tr": "top-right", 
        "bl": "bottom-left",
        "br": "bottom-right",
        "bc": "bottom-center",
        "c": "center"
    }
    
    if position in shortcuts:
        position = shortcuts[position]
    
    if position not in valid_positions:
        await update.message.reply_text(
            f"❌ موقع غير صحيح!\n\n"
            f"استخدم أحد المواقع:\n{', '.join(valid_positions)}\n\n"
            f"أو الاختصارات:\ntl, tr, bl, br, bc, c"
        )
        return
    
    config.set("WATERMARK_POSITION", position)
    
    # أيقونة حسب الموقع
    icons = {
        "top-left": "↖️",
        "top-right": "↗️",
        "bottom-left": "↙️",
        "bottom-right": "↘️",
        "bottom-center": "⬇️",
        "center": "🎯"
    }
    
    await update.message.reply_text(
        f"✅ تم تغيير موقع العلامة المائية!\n\n"
        f"{icons.get(position, '')} الموقع الجديد: {position}"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != config.get("YOUR_USER_ID"):
        return
    
    uptime = time.time() - stats["uptime_start"]
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    
    msg = f"📊 إحصائيات البوت:\n\n"
    msg += f"👥 عدد المشتركين: {len(active_users)}\n"
    msg += f"✅ مقاطع مرسلة: {stats['clips_sent']}\n"
    msg += f"❌ مقاطع فشلت: {stats['clips_failed']}\n"
    msg += f"⏱️ وقت التشغيل: {hours}س {minutes}د\n"
    msg += f"🎬 المصدر: {config.get('SOURCE_URL')[:50]}...\n"
    msg += f"⚙️ مدة المقطع: {config.get('CLIP_SECONDS')}ث\n\n"
    msg += f"🎨 العلامة المائية:\n"
    msg += f"   النص: {config.get('WATERMARK_TEXT')}\n"
    msg += f"   النمط: {config.get('WATERMARK_MODE')}\n"
    msg += f"   الموقع: {config.get('WATERMARK_POSITION')}"
    
    await update.message.reply_text(msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎬 **دليل استخدام البوت**

📌 **الأوامر العامة:**
• `/start` - بدء استخدام البوت والتسجيل
• `/help` - عرض هذه القائمة

📊 **أوامر المالك فقط:**

**إدارة العلامة المائية:**
• `/watermark النص` - تغيير نص العلامة المائية
  مثال: `/watermark @channel_name`

• `/wmode النمط` - تغيير نمط الحركة
  الأنماط المتاحة:
  - `static` (ثابت)
  - `scroll` (يتحرك من اليمين لليسار)
  - `bounce` (يرتد يميناً ويساراً)
  مثال: `/wmode scroll`

• `/wpos الموقع` - تغيير موقع العلامة
  المواقع المتاحة:
  - `top-left` (أعلى اليسار)
  - `top-right` (أعلى اليمين)
  - `bottom-left` (أسفل اليسار)
  - `bottom-right` (أسفل اليمين)
  - `bottom-center` (أسفل المنتصف) 🆕
  - `center` (المنتصف)
  مثال: `/wpos bottom-center`

**أوامر أخرى:**
• `/stats` - عرض إحصائيات البوت
• `/reload` - إعادة تحميل الإعدادات

💡 **نصائح:**
- النص يدعم الرموز والإيموجي: @username 🔴
- يمكنك تغيير الإعدادات أثناء البث بدون توقف
- كل مقطع يبدأ من نهاية المقطع السابق - لن تفوتك أي لحظة!

✨ **التحسينات الجديدة:**
- خط محسّن مع حدود وظل للوضوح
- موقع جديد: أسفل المنتصف
- دعم كامل للغة العربية
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def reload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != config.get("YOUR_USER_ID"):
        return
    
    config.reload()
    await update.message.reply_text("✅ تم إعادة تحميل الإعدادات من config.json")

def get_watermark_position(position):
    """Returns x and y coordinates based on position name"""
    positions = {
        "top-left": "x=10:y=10",
        "top-right": "x=w-tw-10:y=10",
        "bottom-left": "x=10:y=h-th-10",
        "bottom-right": "x=w-tw-10:y=h-th-10",
        "bottom-center": "x=(w-tw)/2:y=h-th-10",
        "center": "x=(w-tw)/2:y=(h-th)/2"
    }
    return positions.get(position, "x=10:y=10")

def build_ffmpeg_cmd_with_watermark(src, out, duration, v_bitrate, a_bitrate, crf_value, watermark_text="", watermark_mode="static", watermark_position="top-left", add_timestamp=False):
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-reconnect", "1",  # إعادة الاتصال عند القطع
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-timeout", "10000000",  # 10 ثانية timeout للشبكة
        "-i", src,
        "-t", str(duration)
    ]
    
    filters = []
    
    if watermark_text:
        escaped_text = watermark_text.replace(":", "\\:").replace("'", "\\'")
        pos = get_watermark_position(watermark_position)
        
        # إعدادات الخط المحسّنة مع shadow
        font_settings = "fontsize=28:fontcolor=white:borderw=2:bordercolor=black:shadowcolor=black@0.7:shadowx=2:shadowy=2"
        
        if watermark_mode == "static":
            filters.append(f"drawtext=text='{escaped_text}':{pos}:{font_settings}")
        
        elif watermark_mode == "scroll":
            filters.append(f"drawtext=text='{escaped_text}':x='w-mod(t*50,w+tw)':y=10:{font_settings}")
        
        elif watermark_mode == "bounce":
            filters.append(f"drawtext=text='{escaped_text}':x='if(lt(mod(t,4),2),10+mod(t*100,w-tw-20),w-tw-10-mod(t*100,w-tw-20))':y=10:{font_settings}")
    
    if add_timestamp:
        filters.append("drawtext=text='%{localtime\\:%H\\\\\\:%M\\\\\\:%S}':x=w-tw-10:y=h-th-10:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.5")
    
    if filters:
        filter_str = ",".join(filters)
        cmd += ["-vf", filter_str]
    
    if crf_value:
        cmd += [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", str(crf_value),
            "-c:a", "aac",
            "-b:a", a_bitrate,
            "-movflags", "+faststart",
            out
        ]
    else:
        cmd += [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-b:v", v_bitrate,
            "-maxrate", v_bitrate,
            "-bufsize", "2M",
            "-c:a", "aac",
            "-b:a", a_bitrate,
            "-movflags", "+faststart",
            out
        ]
    return cmd

def fetch_and_encode_clip(output_path):
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except:
            pass
    
    cmd = build_ffmpeg_cmd_with_watermark(
        config.get("SOURCE_URL"),
        output_path,
        config.get("CLIP_SECONDS"),
        config.get("VIDEO_BITRATE"),
        config.get("AUDIO_BITRATE"),
        config.get("CRF"),
        config.get("WATERMARK_TEXT", ""),
        config.get("WATERMARK_MODE", "static"),
        config.get("WATERMARK_POSITION", "top-left"),
        config.get("ADD_TIMESTAMP", True)
    )
    
    try:
        # timeout أطول لضمان اكتمال التحميل
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        return True
    except subprocess.TimeoutExpired:
        print(f"⏱️ انتهى الوقت - يُعاد المحاولة...")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ خطأ ffmpeg:", e.stderr.decode(errors="ignore") if e.stderr else str(e))
        return False
    except Exception as e:
        print(f"❌ خطأ غير متوقع:", str(e))
        return False

async def send_clip_to_users(clip_path):
    if not os.path.exists(clip_path):
        print("No output file to send.")
        return False
    
    success_count = 0
    
    try:
        with open(clip_path, "rb") as f:
            await bot.send_video(
                chat_id=config.get("CHANNEL_ID"),
                video=f,
                supports_streaming=True,
                read_timeout=300,
                write_timeout=300
            )
        success_count += 1
        print(f"✅ تم الإرسال للقناة")
    except Exception as e:
        print(f"❌ خطأ في القناة: {e}")
    
    tasks = []
    for user_id in active_users:
        tasks.append(send_to_user(user_id, clip_path))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    success_count += sum(1 for r in results if r is True)
    
    try:
        os.remove(clip_path)
    except:
        pass
    
    stats["clips_sent"] += 1
    
    print(f"📊 نتيجة الإرسال: {success_count}/{len(active_users) + 1}")
    return success_count > 0

async def send_to_user(user_id, clip_path):
    try:
        with open(clip_path, "rb") as f:
            await bot.send_video(
                chat_id=user_id,
                video=f,
                supports_streaming=True,
                read_timeout=300,
                write_timeout=300
            )
        print(f"✅ إرسال: {user_id}")
        return True
    except Exception as e:
        print(f"❌ خطأ: {user_id}")
        return False

async def send_start_broadcast_message():
    print("📢 إرسال إشعار بدء البث...")
    
    try:
        await bot.send_message(
            chat_id=config.get("CHANNEL_ID"),
            text="🎬 بدأ البث المباشر الآن!\n📺 كل مقطع يبدأ من نهاية المقطع السابق - لن تفوتك أي لحظة!"
        )
        print(f"✅ إشعار للقناة")
    except Exception as e:
        print(f"❌ خطأ إشعار القناة: {e}")
    
    for user_id in active_users:
        try:
            await bot.send_message(
                chat_id=user_id,
                text="🎬 بدأ البث المباشر الآن!\n📺 كل مقطع يبدأ من نهاية المقطع السابق - لن تفوتك أي لحظة!"
            )
        except:
            pass
        await asyncio.sleep(0.3)

def clip_producer():
    clip_counter = 0
    clip_duration = config.get("CLIP_SECONDS")
    
    print(f"⚙️ إعدادات التسجيل:")
    print(f"   مدة المقطع: {clip_duration}ث")
    print(f"   بدون تداخل - كل مقطع يبدأ من نهاية السابق")
    print(f"   إعادة محاولة تلقائية عند الفشل")
    print(f"🎬 التسجيل المتتالي نشط - لن تفوت أي لحظة!\n")
    
    while True:
        clip_counter += 1
        output_path = f"/tmp/clip_{clip_counter}.mp4"
        
        # نظام إعادة المحاولة (3 محاولات)
        max_retries = 3
        retry_count = 0
        success = False
        
        while retry_count < max_retries and not success:
            if retry_count > 0:
                print(f"🔄 محاولة {retry_count + 1}/{max_retries} للمقطع #{clip_counter}...")
            else:
                print(f"🎬 تسجيل مقطع #{clip_counter}...")
            
            success = fetch_and_encode_clip(output_path)
            
            if not success:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 3 * retry_count  # انتظار تصاعدي
                    print(f"⏳ انتظار {wait_time}ث قبل المحاولة التالية...")
                    time.sleep(wait_time)
        
        if success and os.path.exists(output_path):
            clip_queue.put(output_path)
            print(f"✅ مقطع #{clip_counter} جاهز في الطابور")
        else:
            stats["clips_failed"] += 1
            print(f"❌ فشل المقطع #{clip_counter} بعد {max_retries} محاولات")
            time.sleep(10)  # انتظار أطول قبل المقطع التالي

async def clip_consumer():
    while True:
        if not clip_queue.empty():
            clip_path = clip_queue.get()
            await send_clip_to_users(clip_path)
            
            sleep_time = config.get("SLEEP_BETWEEN", 0)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        else:
            await asyncio.sleep(0.5)

async def broadcast_loop():
    print("🎬 بدء البث المباشر المحسّن مع نظام العلامة المائية الديناميكي...")
    
    await send_start_broadcast_message()
    await asyncio.sleep(2)
    
    executor = ThreadPoolExecutor(max_workers=2)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, clip_producer)
    
    await clip_consumer()

async def main():
    application = Application.builder().token(config.get("BOT_TOKEN")).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("reload", reload_command))
    application.add_handler(CommandHandler("watermark", watermark_command))
    application.add_handler(CommandHandler("wmode", wmode_command))
    application.add_handler(CommandHandler("wpos", wpos_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_message))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("✅ البوت يعمل الآن ويستقبل الرسائل...")
    
    await broadcast_loop()

if __name__ == "__main__":
    asyncio.run(main())
