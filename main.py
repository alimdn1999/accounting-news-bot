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
    try:
        prompt = f"""این خبر حسابداری را کاملاً به فارسی روان و حرفه‌ای ترجمه کن:
عنوان انگلیسی: {title_en}
متن انگلیسی: {summary_en[:3500]}

خروجی فقط شامل:
• عنوان فارسی جذاب و کوتاه
• خلاصه فارسی کامل و مفصل (۵ تا ۱۰ جمله)
• هیچ کلمه انگلیسی، شماره، یا علامت اضافه‌ای ننویس
• از ایموجی فقط در صورت لزوم استفاده کن"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=35)

        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text[:3800]
    except Exception as e:
        print(f"Gemini خطا: {e}")

    return "در حال حاضر خلاصه فارسی در دسترس نیست. خبر به‌زودی ترجمه و ارسال می‌شود."

async def post_one_persian_news():
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:8]:
                link = entry
