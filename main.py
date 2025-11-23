import feedparser
import telegram
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
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
    prompt = f"""این خبر را به فارسی کامل و مفصل (حداقل ۶ جمله) ترجمه کن:

عنوان: {title_en}
خلاصه: {summary_en[:3200]}

شروع کن با یک عنوان فارسی جذاب.
از کلمات فارسی استفاده کن، فقط نام‌های خاص مثل PwC، IFRS، SEC را همان‌طور نگه دار.
هیچ کلمه انگلیسی غیرضروری ننویس."""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=40)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text[:3800]
    except:
        pass

    return f"جدیدترین خبر حسابداری:\n{title_en}\n\nخلاصه به‌زودی با ترجمه فارسی کامل ارسال می‌شود."

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

                persian = get_full_persian_news(title_en, summary_en)

                message = f"#اخبار_روز\n━━━━━━━━━━━━━━\n{persian}\n\nلینک خبر:\n{link}"

                await bot.send_message(chat_id=CHANNEL_ID, text=message, disable_web_page_preview=True)
                print("خبر فارسی کامل ارسال شد!")

                posted_links.add(link)
                with open(posted_links_file, "a") as f:
                    f.write(link + "\n")
                return

        except Exception as e:
            print(f"خطا: {e}")
            continue

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
scheduler = AsyncIOScheduler(event_loop=loop)
scheduler.add_job(post_one_persian_news, 'interval', minutes=5)  # هر ۵ دقیقه
scheduler.start()

print("ربات تست ۵ دقیقه‌ای فعال شد – هر ۵ دقیقه یک خبر فارسی کامل می‌فرسته!")
loop.run_forever()
