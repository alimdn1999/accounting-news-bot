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
# در Railway باید این مقادیر را در بخش Variables وارد کنید
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# بررسی اینکه کلیدها ست شده باشند
if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    print("Error: Environment variables are not set. Please set TELEGRAM_TOKEN and GEMINI_API_KEY in Railway.")

# فایل ذخیره موقت (توجه: در Railway این فایل با هر دیپلوی جدید ریست می‌شود)
# اما نگران نباشید، چون ما چک می‌کنیم خبر قدیمی نباشد.
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
        print(f"Warning: Could not save link to file: {e}")

def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

def is_article_new(entry):
    """
    بررسی می‌کند که خبر مربوط به ۲۴ ساعت گذشته باشد.
    این کار باعث می‌شود اگر فایل لینک‌ها پاک شد، خبرهای قدیمی دوباره ارسال نشوند.
    """
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            now = datetime.now()
            # اگر خبر قدیمی‌تر از 24 ساعت است، False برگردان
            if now - published_time > timedelta(hours=24):
                return False
        return True
    except:
        # اگر تاریخ نداشت، فرض می‌کنیم جدید است (ریسک کم)
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
        response = requests.post(url, json=payload, timeout=20)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram Error: {e}")
        return False

def translate_with_gemini(title_en, summary_en):
    clean_summary = clean_html(summary_en)[:3500]
    
    prompt = f"""You are a professional financial journalist.
Task: Translate and summarize into fluent Persian (Farsi).

1. **Headline:** Catchy Persian headline.
2. **Body:** 6-10 sentences summary in formal/journalistic Persian.
3. **Keywords:** Keep 'IFRS', 'GAAP', 'Big4', 'SEC' in English.
4. **Output:** ONLY the translated text. No intros.

Title: {title_en}
Context: {clean_summary}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except:
        pass
    return None

# ==========================================
# پردازش اصلی
# ==========================================

def job_check_feed():
    print("--- Starting Feed Check ---")
    posted_links = load_posted_links()
    
    for feed_url in RSS_FEEDS:
        try:
            print(f"Checking: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:5]: 
                link = entry.link.strip()
                
                # 1. چک کردن تکراری بودن
                if link in posted_links:
                    continue

                # 2. چک کردن قدیمی بودن (برای جلوگیری از ارسال مجدد بعد از ریستارت)
                if not is_article_new(entry):
                    print(f"Skipping old article: {entry.title}")
                    # لینک قدیمی را هم ذخیره می‌کنیم که دفعه بعد چک نکنیم
                    posted_links.add(link)
                    save_posted_link(link)
                    continue
                
                # ترجمه و ارسال
                print(f"New Article Found: {entry.title}")
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
                        print(">> Sent to Telegram")
                        save_posted_link(link)
                        posted_links.add(link)
                        return # توقف برای این دور (ارسال یکی یکی)
                    else:
                        print(">> Failed to send")
        except Exception as e:
            print(f"Error on feed: {e}")

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    # چک کردن هر 5 دقیقه
    scheduler.add_job(job_check_feed, 'interval', minutes=5)
    
    print("Bot is running on Railway...")
    
    # اجرا بلافاصله پس از شروع
    job_check_feed()
    
    scheduler.start()
