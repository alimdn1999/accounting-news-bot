import feedparser
import time
import os
import requests
import re
from apscheduler.schedulers.blocking import BlockingScheduler

# ==========================================
# تنظیمات و کلیدها
# ==========================================
# نکته امنیتی: هیچوقت کلیدهای خود را در جاهای عمومی منتشر نکنید.
TELEGRAM_TOKEN = "8024765560:AAGFsVT9bTzGHGD-aSzkUo_y-vXRLZpSi4s"
CHANNEL_ID = "@AccountingNewsDaily"
GEMINI_API_KEY = "AIzaSyDCJZ71zv_u4DiA93nn_CtRv2BmSnyCtFw"

# فایل ذخیره لینک‌های ارسال شده برای جلوگیری از تکرار
POSTED_LINKS_FILE = "posted_links.txt"

# لیست منابع خبری
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
    """لینک‌های قبلاً ارسال شده را از فایل می‌خواند."""
    if os.path.exists(POSTED_LINKS_FILE):
        with open(POSTED_LINKS_FILE, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    return set()

def save_posted_link(link):
    """لینک جدید را به فایل اضافه می‌کند."""
    with open(POSTED_LINKS_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

def clean_html(raw_html):
    """تگ‌های HTML مزاحم را از متن خبر حذف می‌کند."""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

def send_telegram_message(text):
    """پیام را مستقیماً با استفاده از API تلگرام ارسال می‌کند (بدون نیاز به کتابخانه خاص)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML", # برای خوشگل‌تر شدن متن (بولد کردن و ...)
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            return True
        else:
            print(f"Error sending to Telegram: {response.text}")
            return False
    except Exception as e:
        print(f"Telegram Connection Error: {e}")
        return False

def translate_with_gemini(title_en, summary_en):
    """استفاده از هوش مصنوعی برای ترجمه و خلاصه‌سازی خبری."""
    
    # تمیز کردن متن ورودی
    clean_summary = clean_html(summary_en)[:4000] # محدودیت کاراکتر
    
    prompt = f"""You are a professional financial journalist and translator.
Task: Translate and summarize the following accounting news into fluent, professional Persian (Farsi).

Instructions:
1. **Headline:** Create a catchy, bold Persian headline based on the English title.
2. **Body:** Write a comprehensive summary (6-10 sentences). Use formal, journalistic Persian language suitable for accountants and auditors.
3. **Terminology:** Keep specific English acronyms like IFRS, GAAP, SEC, Big4, PwC, Deloitte, etc., in English characters. Do not translate them literally.
4. **Formatting:** Do NOT use Markdown symbols like ** or ## inside the text provided for the body, unless it helps readability. 
5. **Output:** Provide ONLY the translated content without any introductory phrases like "Here is the translation".

English Title: {title_en}
English Text: {clean_summary}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if "candidates" in data and data["candidates"]:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            print(f"Gemini API Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Gemini Connection Error: {e}")
        
    return None

# ==========================================
# تابع اصلی پردازش
# ==========================================

def job_check_feed():
    print("Checking feeds for new articles...")
    posted_links = load_posted_links()
    
    for feed_url in RSS_FEEDS:
        try:
            print(f"Reading: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            # فقط ۱۰ خبر اول هر فید را چک می‌کنیم
            for entry in feed.entries[:5]: 
                link = entry.link.strip()
                
                if link in posted_links:
                    continue # اگر قبلا پست شده، برو بعدی
                
                # استخراج اطلاعات
                title = entry.title
                summary = entry.summary if hasattr(entry, "summary") else entry.title
                
                print(f"Found new article: {title}")
                print("Translating...")
                
                persian_text = translate_with_gemini(title, summary)
                
                if persian_text:
                    # آماده‌سازی پیام نهایی
                    final_message = (
                        f"<b>{clean_html(title)}</b>\n\n" # عنوان انگلیسی برای رفرنس
                        f"{persian_text}\n\n"
                        f"🔗 <a href='{link}'>لینک خبر اصلی</a>\n"
                        f"🆔 {CHANNEL_ID}"
                    )
                    
                    if send_telegram_message(final_message):
                        print("Message sent successfully!")
                        save_posted_link(link)
                        posted_links.add(link)
                        
                        # توقف کوتاه برای جلوگیری از اسپم و عبور از محدودیت‌های API
                        return # در هر دور اجرا فقط ۱ خبر می‌فرستیم (Drip feeding)
                    else:
                        print("Failed to send message.")
                else:
                    print("Translation failed.")
                    
        except Exception as e:
            print(f"Error parsing feed {feed_url}: {e}")
            continue

# ==========================================
# اجرا
# ==========================================

if __name__ == "__main__":
    # ایجاد اسکژولر (زمان‌بند)
    scheduler = BlockingScheduler()
    
    # اجرا هر ۵ دقیقه
    # تذکر: تابع job_check_feed طوری نوشته شده که در هر بار اجرا فقط ۱ خبر جدید می‌فرستد
    # تا کانال شما اسپم نشود.
    scheduler.add_job(job_check_feed, 'interval', minutes=5)
    
    print("Bot started successfully...")
    print("Press Ctrl+C to stop.")
    
    # اجرای اولیه محض اطمینان
    job_check_feed()
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
