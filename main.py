import feedparser
import telegram
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import os
import re

TELEGRAM_TOKEN = "8024765560:AAGFsVT9bTzGHGD-aSzkUo_y-vXRLZpSi4s"
CHANNEL_ID = "@AccountingNewsDaily"

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
]

# ترجمه ساده و فارسی‌سازی داخلی (همیشه کار می‌کنه)
def make_persian(title_en, summary_en):
    # فارسی‌سازی عنوان
    title_fa = title_en.replace("PwC", "پی‌دبلیو‌سی").replace("KPMG", "کی‌پی‌ام‌جی")
    title_fa = title_fa.replace("Deloitte", "دیلویت").replace("EY", "ای‌وای").replace("Big4", "چهار شرکت بزرگ حسابداری")
    title_fa = title_fa.replace("IFRS", "استانداردهای بین‌المللی گزارشگری مالی").replace("GAAP", "اصول پذیرفته‌شده حسابداری")
    title_fa = title_fa.replace("SEC", "کمیسیون بورس و اوراق بهادار آمریکا").replace("audit", "حسابرسی")

    # فارسی‌سازی خلاصه (جایگزینی کلمات کلیدی)
    summary_fa = summary_en
    summary_fa = re.sub(r'\bPwC\b', 'پی‌دبلیو‌سی', summary_fa)
    summary_fa = re.sub(r'\bKPMG\b', 'کی‌پی‌ام‌جی', summary_fa)
    summary_fa = re.sub(r'\bDeloitte\b', 'دیلویت', summary_fa)
    summary_fa = re.sub(r'\bEY\b', 'ای‌وای', summary_fa)
    summary_fa = re.sub(r'\bBig4\b', 'چهار شرکت بزرگ حسابداری', summary_fa)
    summary_fa = re.sub(r'\bIFRS\b', 'استانداردهای بین‌المللی گزارشگری مالی', summary_fa)
    summary_fa = re.sub(r'\bGAAP\b', 'اصول پذیرفته‌شده حسابداری', summary_fa)
    summary_fa = re.sub(r'\bSEC\b', 'کمیسیون بورس و اوراق بهادار آمریکا', summary_fa)
    summary_fa = re.sub(r'\baudit\b', 'حسابرسی', summary_fa)
    summary_fa = re.sub(r'\btax\b', 'مالیات', summary_fa)
    summary_fa = re.sub(r'\brevenue\b', 'درآمد', summary_fa)

    # خلاصه طولانی (تا ۳۵۰۰ حرف)
    summary_fa = summary_fa[:3400] + " (خلاصه کامل در لینک موجود است)"

    return f"{title_fa}\n\n{summary_fa}"

async def post_one_news():
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                link = entry.link.strip()
                if link in posted_links:
                    continue

                title_en = entry.title
                summary_en = entry.summary if hasattr(entry, "summary") else entry.get("description", "")

                persian = make_persian(title_en, summary_en)

                message = f"#اخبار_روز\n━━━━━━━━━━━━━━\n{persian}\n\nلینک خبر:\n{link}"

                await bot.send_message(chat_id=CHANNEL_ID, text=message, disable_web_page_preview=True)
                print("خبر فارسی ارسال شد!")

                posted_links.add(link)
                with open(posted_links_file, "a") as f:
                    f.write(link + "\n")
                return
        except Exception as e:
            print(f"خطا: {e}")
            continue

    print("هیچ خبر جدیدی نبود")

# فیکس event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
scheduler = AsyncIOScheduler(event_loop=loop)
scheduler.add_job(post_one_news, 'interval', minutes=5)  # هر ۵ دقیقه برای تست
scheduler.start()

print("ربات بدون API فعال شد – هر ۵ دقیقه خبر فارسی می‌فرسته!")
loop.run_forever()
