import feedparser
import time
import os
import requests
import re
from datetime import datetime, timedelta
from time import mktime
from apscheduler.schedulers.blocking import BlockingScheduler

# ==========================================
# تنظیمات و دریافت کلیدها از متغیرهای محیطی
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    print("FATAL ERROR: Environment variables are missing.")

POSTED_LINKS_FILE = "posted_links.txt"

RSS_FEEDS = [
    "https://www.accountingtoday.com/feed",
    "https://www.goingconcern.com/feed/",
    "https://cpatrendlines.com/feed/",
    "https://www.journalofaccountancy.com/.rss/full/",
    "https://news.google.com/rss/search?q=accounting+OR+IFRS+OR+GAAP+OR+audit+OR+Big4+when:1d&hl=en&gl=US&ceid=US:en",
]

# ==========================================
# توابع کمکی
# ==========================================

def load_posted_links():
    if os.path.exists(POSTED_LINKS_FILE):
        try:
            with open(POSTED_LINKS_FILE, "r", encoding="utf-8") as f:
                return set(f.read().splitlines())
        except:
            return set()
    return set()

def save_posted_link(link):
    try:
        with open(POSTED_LINKS_FILE, "a", encoding="utf-8") as f:
            f.write(link + "\n")
    except Exception as e:
        print(f"Warning: Could not save link: {e}")

def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

def is_article_new(entry):
    """
    بررسی می‌کند که خبر مربوط به ۳ روز گذشته باشد.
    """
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            now = datetime.now()
            # لاگ کردن تاریخ خبر برای دیباگ
            # print(f"DEBUG: Article Date: {published_time} | Now: {now}")
            
            # تغییر به 72 ساعت (3 روز) برای اطمینان از پیدا شدن خبر
            if now - published_time > timedelta(hours=72):
                return False
        return True
    except:
        return True

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        print(f"Attempting to send message to {CHANNEL_ID}...")
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            print("✅ Telegram Message Sent Successfully!")
            return True
        else:
            print(f"❌ Telegram Error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False

def translate_with_gemini(title_en, summary_en):
    clean_summary = clean_html(summary_en)[:3500]
    prompt = f"""You are a professional financial journalist.
Task: Translate and summarize into fluent Persian (Farsi).

1. **Headline:** Catchy Persian headline.
2. **Body:** 6-10 sentences summary in formal/journalistic Persian.
3. **Keywords:** Keep 'IFRS', 'GAAP', 'Big4', 'SEC' in English.
4. **Output:** ONLY the translated text.

Title: {title_en}
Context: {clean_summary}
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            print(f"Gemini Error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Gemini Connection failed: {e}")
    return None

# ==========================================
# پردازش اصلی
# ==========================================

def job_check_feed():
    print("\n--- 🔄 Starting Feed Check Cycle ---")
    posted_links = load_posted_links()
    
    for feed_url in RSS_FEEDS:
        try:
            print(f"📡 Reading Feed: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                print("   ⚠️ No entries found in this feed.")
                continue

            for entry in feed.entries[:5]: 
                link = entry.link.strip()
                
                # 1. چک تکراری
                if link in posted_links:
                    continue

                # 2. چک تاریخ (با لاگ دقیق‌تر)
                if not is_article_new(entry):
                    # print(f"   ⏳ Skipping old article: {entry.title[:30]}...")
                    posted_links.add(link)
                    save_posted_link(link)
                    continue
                
                # ترجمه و ارسال
                print(f"   ✨ New Article Found: {entry.title}")
                print("   ... Translating ...")
                
                summary = entry.summary if hasattr(entry, "summary") else entry.title
                persian_text = translate_with_gemini(entry.title, summary)
                
                if persian_text:
                    msg = (
                        f"<b>{clean_html(entry.title)}</b>\n\n"
                        f"{persian_text}\n\n"
                        f"🔗 <a href='{link}'>لینک خبر اصلی</a>\n"
                        f"🆔 {CHANNEL_ID}"
                    )
                    
                    if send_telegram_message(msg):
                        save_posted_link(link)
                        posted_links.add(link)
                        print("   ✅ Cycle paused. Waiting for next schedule.")
                        return # توقف برای این دور
                    else:
                        print("   ❌ Failed to send to Telegram (Check Admin rights/Token).")
                else:
                    print("   ❌ Translation returned empty.")
                    
        except Exception as e:
            print(f"❌ Error processing feed: {e}")

if __name__ == "__main__":
    # --- تست اتصال اولیه ---
    print("🚀 Bot is starting...")
    startup_msg = f"🟢 ربات اخبار حسابداری با موفقیت روشن شد.\nساعت سرور: {datetime.now().strftime('%H:%M:%S')}\nدر حال جستجوی خبرهای ۳ روز گذشته..."
    
    # تلاش برای ارسال پیام تست
    success = send_telegram_message(startup_msg)
    
    if not success:
        print("\n⛔⛔⛔ هشدار جدی: ربات نتوانست پیام شروع را بفرستد.")
        print("لطفاً چک کنید: 1. توکن درست است؟ 2. آیدی کانال @ دارد؟ 3. ربات در کانال ادمین است؟\n")
    else:
        print("✅ Startup message sent! Connection is good.")

    # شروع اسکژولر
    scheduler = BlockingScheduler()
    scheduler.add_job(job_check_feed, 'interval', minutes=5)
    
    # اجرای اولین چک بلافاصله
    job_check_feed()
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
