import feedparser
import telegram
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import os
import requests

TELEGRAM_TOKEN = "8024765560:AAGFsVT9bTzGHGD-aSzkUo_y-vXRLZpSi4s"
CHANNEL_ID = "@AccountingNewsDaily"
GROK_API_KEY = "xai-jPR19o8oYyJLDoxQIb0SuOlfpuAAF8tNSUxKWHAgjRp00qxYgGzEG1XtjoIf4yL2J9pCL1LEX0J2YqKA"

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

def get_persian_with_grok(title_en, summary_en):
    prompt = f"""این خبر حسابداری را کاملاً به فارسی روان و مفصل (حداقل ۶–۱۰ جمله) ترجمه کن:
عنوان: {title_en}
متن: {summary_en[:3500]}

شروع کن با عنوان فارسی جذاب، بعد توضیح کامل بده.
فقط فارسی بنویس، نام‌های خاص مثل PwC، IFRS، SEC را همان‌طور نگه دار."""

    try:
        url = "https://api.x.ai/v1/chat/completions"
        payload = {
            "model": "grok-beta",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1500
        }
        headers = {"Authorization": f"Bearer {GROK_API_KEY}"}
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()[:3800]
    except:
        pass

    return "جدیدترین خبر حسابداری (ترجمه در حال آماده‌سازی)"

async def post_one_news():
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                link = entry.link.strip()
                if link in posted_links:
                    continue

                title_en = entry.title
                summary_en = entry.summary if hasattr(entry, "summary") else ""

                persian = get_persian_with_grok(title_en, summary_en)

                message = f"#اخبار_روز\n━━━━━━━━━━━━━━\n{persian}\n\nلینک خبر:\n{link}"

                await bot.send_message(chat_id=CHANNEL_ID, text=message, disable_web_page_preview=True)
                print("خبر فارسی با Grok ارسال شد!")

                posted_links.add(link)
                with open(posted_links_file, "a") as f:
                    f.write(link + "\n")
                return
        except:
            continue

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
scheduler = AsyncIOScheduler(event_loop=loop)
scheduler.add_job(post_one_news, 'interval', minutes=10)  # برای تست
scheduler.start()
print("ربات با Grok فعال شد – هر ۱۰ دقیقه یک خبر کامل فارسی می‌فرسته!")
loop.run_forever()
