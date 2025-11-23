import feedparser
import telegram
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import pytz
import os
import requests

# اطلاعات تو (همه پر شدن)
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
tehran_tz = pytz.timezone("Asia/Tehran")

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

def get_full_persian_news(title_en, summary_en):
    if not GEMINI_API_KEY:
        return title_en, summary_en[:250] + "..."
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        prompt = f"""این خبر حسابداری را به فارسی روان و حرفه‌ای ترجمه و خلاصه کن:
عنوان انگلیسی: {title_en}
متن انگلیسی: {summary_en[:1500]}

خروجی فقط شامل:
۱. عنوان فارسی کوتاه و جذاب
۲. خلاصه فارسی حداکثر ۲-۳ جمله"""
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=25)
        if response.status_code == 200:
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            persian_title = lines[0] if lines else title_en
            persian_body = '\n'.join(lines[1:]) if len(lines) > 1 else text
            return persian_title, persian_body or "جزئیات در لینک"
    except:
        pass
    return title_en, summary_en[:250] + "..."

async def post_news():
    new_links = []
    messages = ["#اخبار_روز\n━━━━━━━━━━━━━━"]

    found_new = False
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                link = entry.link.strip()
                if link in posted_links:
                    continue

                title_en = entry.title
                summary_en = entry.summary if hasattr(entry, "summary") else ""
                persian_title, persian_body = get_full_persian_news(title_en, summary_en)

                messages.append(f"• {persian_title}\n{persian_body}\n{link}\n")
                posted_links.add(link)
                new_links.append(link)
                found_new = True

                if len(messages) > 15:
                    break
        except:
            continue

    if found_new:
        final_message = "\n".join(messages)
        await bot.send_message(chat_id=CHANNEL_ID, text=final_message, disable_web_page_preview=True)
        with open(posted_links_file, "a") as f:
            for link in new_links:
                f.write(link + "\n")

# فیکس event loop برای Railway
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
scheduler = AsyncIOScheduler(event_loop=loop)
scheduler.add_job(post_news, 'interval', minutes=30)
scheduler.start()

print("ربات #اخبار_روز فعال شد – هر ۳۰ دقیقه پست می‌کنه!")
loop.run_forever()
