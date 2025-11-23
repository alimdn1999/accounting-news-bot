import feedparser
import telegram
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import pytz
import os
import requests
from datetime import datetime

# اطلاعات تو
TELEGRAM_TOKEN = "8024765560:AAGFsVT9bTzGHGD-aSzkUo_y-vXRLZpSi4s"
CHANNEL_ID = "@AccountingNewsDaily"
GEMINI_API_KEY = "AIzaSyDwwU0YXFbI1c_lqgq1MCTlRHltNz5LpU0"

posted_links_file = "posted_links.txt"
if os.path.exists(posted_links_file):
    with open(posted_links_file, "r") as f:
        posted_links = set(f.read().splitlines())
else:
    posted_links = set()

bot = telegram.Bot(token=TELEGRAM_TOKEN)

# ۱۵ تا منبع معتبر
RSS_FEEDS = [
    "https://www.accountingtoday.com/feed",
    "https://www.goingconcern.com/feed/",
    "https://cpatrendlines.com/feed/",
    "https://www.journalofaccountancy.com/.rss/full/",
    "https://news.google.com/rss/search?q=accounting+OR+IFRS+OR+GAAP+OR+audit+OR+Big4+when:1d&hl=en&gl=US&ceid=US:en",
    "https://www.internationalaccountingbulletin.com/feed/",
    "https://www.accountancyage.com/type/news/feed/",
    "https://insightfulaccountant.com/api/rss/content.rss",
    "https://www.accountingweb.co.uk/tax/news/feed",
    "https://www.icaew.com/rss/insights",
    "https://www.theaccountant-online.com/feed/",
    "https://www.accountantsdaily.com.au/columns?format=feed&type=rss",
    "https://www.cpapracticeadvisor.com/rss/news.xml",
    "https://www.taxandaccountingblog.com/feed/",
    "https://www.bdo.com/rss/news",
]

def get_persian_news(title_en, summary_en, link):
    if not GEMINI_API_KEY:
        return title_en, summary_en[:180] + "...", link

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        prompt = f"""این خبر حسابداری را به فارسی خیلی کوتاه و جذاب ترجمه کن (حداکثر ۱۵۰ حرف کل خروجی):
عنوان: {title_en}
خلاصه انگلیسی: {summary_en[:800]}

خروجی فقط شامل:
۱. عنوان فارسی کوتاه
۲. یک جمله خلاصه فارسی
(بدون شماره، بدون نقطه اضافه)"""
        
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            title_fa = lines[0] if lines else title_en
            body_fa = " ".join(lines[1:]) if len(lines) > 1 else text
            return title_fa, body_fa[:120], link
    except:
        pass
    return title_en, summary_en[:120] + "...", link

async def post_one_important_news():
    best_entry = None
    best_score = 0

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                link = entry.link.strip()
                if link in posted_links:
                    continue

                # امتیازدهی ساده: جدیدتر = مهم‌تر
                try:
                    pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
                    if pub_date:
                        score = datetime(*pub_date[:6]).timestamp()
                    else:
                        score = 0
                except:
                    score = 0

                if score > best_score:
                    best_score = score
                    best_entry = entry
                    best_link = link

            if best_entry:
                break  # اولین خبر با بالاترین امتیاز رو بگیر
        except:
            continue

    if best_entry and best_link not in posted_links:
        title_en = best_entry.title
        summary_en = best_entry.summary if hasattr(best_entry, "summary") else ""
        title_fa, body_fa, link = get_persian_news(title_en, summary_en, best_link)

        message = f"#اخبار_روز\n━━━━━━━━━━━━━━\n• {title_fa}\n{body_fa}\n{link}"

        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=message, disable_web_page_preview=True)
            print(f"مهم‌ترین خبر ارسال شد: {title_fa[:50]}...")
            
            # ذخیره لینک برای جلوگیری از تکرار
            posted_links.add(best_link)
            with open(posted_links_file, "a") as f:
                f.write(best_link + "\n")
        except Exception as e:
            print(f"خطا در ارسال: {e}")

# فیکس event loop برای Railway
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
scheduler = AsyncIOScheduler(event_loop=loop)
scheduler.add_job(post_one_important_news, 'interval', minutes=30)  # هر ۳۰ دقیقه یک خبر مهم
scheduler.start()

print("ربات فعال شد – هر ۳۰ دقیقه فقط یک خبر مهم و کوتاه می‌فرسته!")
loop.run_forever()
