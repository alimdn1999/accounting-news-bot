import feedparser
import telegram
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import pytz
import os
import requests

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

RSS_FEEDS = [
    "https://www.accountingtoday.com/feed",
    "https://www.goingconcern.com/feed/",
    "https://cpatrendlines.com/feed/",
    "https://www.journalofaccountancy.com/.rss/full/",
    "https://news.google.com/rss/search?q=accounting+OR+IFRS+OR+GAAP+OR+audit+OR+Big4+when:1d&hl=en&gl=US&ceid=US:en",
]

def get_full_persian_news(title_en, summary_en):
    prompt = f"""این خبر حسابداری را کاملاً به فارسی روان و حرفه‌ای ترجمه کن (۶ تا ۱۲ جمله):
عنوان انگلیسی: {title_en}
متن انگلیسی: {summary_en[:3000]}

خروجی فقط شامل:
- عنوان فارسی جذاب و کوتاه
- متن کامل فارسی مفصل
- هیچ کلمه انگلیسی، عدد، علامت یا ایموجی اضافه ننویس
- فقط فارسی خالص"""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=40)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text[:3800]
    except Exception as e:
        print(f"خطای جمینی: {e}")

    return "در حال حاضر خلاصه فارسی آماده نیست. خبر به‌زودی ارسال می‌شود."

async def post_one_persian_news():
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                link = entry.link.strip()
                if link in posted_links:
                    continue

                title_en = entry.title
                summary_en = entry.summary if hasattr(entry, "summary") else ""

                persian_content = get_full_persian_news(title_en, summary_en)

                message = f"#اخبار_روز\n━━━━━━━━━━━━━━\n{persian_content}\n\nلینک خبر:\n{link}"

                await bot.send_message(chat_id=CHANNEL_ID, text=message, disable_web_page_preview=True)
                print("خبر کامل فارسی با لینک فارسی ارسال شد!")

                posted_links.add(link)
                with open(posted_links_file, "a") as f:
                    f.write(link + "\n")
                return

        except Exception as e:
            print(f"خطا در منبع: {e}")
            continue

# فیکس event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
scheduler = AsyncIOScheduler(event_loop=loop)
scheduler.add_job(post_one_persian_news, 'interval', minutes=10)  # برای تست
scheduler.start()

print("ربات نهایی فارسی فعال شد – هر ۱۰ دقیقه یک خبر کامل فارسی می‌فرسته!")
loop.run_forever()
