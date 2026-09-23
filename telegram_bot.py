import asyncio, os, base64, re, json, logging
import aiohttp
logging.basicConfig(level=logging.INFO)
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except:
    HAS_BS4 = False

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OR_KEY = os.getenv("OPENAI_API_KEY")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN")
APIPOINT_URL = "https://apipoint.ru/api/call"

print(f"BOOT v6.1 | BOT_TOKEN={bool(BOT_TOKEN)} APIPOINT_KEY={bool(APIPOINT_KEY)} OPENAI={bool(OR_KEY)}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN env is empty! Set it in Railway Variables")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

user_data = {}

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔍 Дистанционка по номеру/VIN/ссылке")],
        [KeyboardButton(text="🚗 Я у капота (фото+видео)")],
        [KeyboardButton(text="📩 Запросить VIN у продавца")],
        [KeyboardButton(text="🔄 Сбросить")],
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📩 Запросить VIN у продавца")],
        [KeyboardButton(text="🔄 Сбросить")],
    ], resize_keyboard=True)

HOOD_STEPS = ["1/8 — Спереди","2/8 — Сзади","3/8 — Левый бок","4/8 — Правый бок","5/8 — VIN","6/8 — Приборка","7/8 — Под капотом","8/8 — Видео"]

def is_vin(s): return bool(re.match(r'^[A-HJ-NPR-Z0-9]{17}$', s.upper().strip()))
def is_gosnum(s): 
    s=s.upper().replace(" ","")
    return bool(re.match(r'^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$', s))
def extract_urls(t): return re.findall(r'https?://[^\s]+', t)
def extract_gos(t):
    m=re.search(r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\s*\d{2,3}', t.upper())
    return m.group(0).replace(" ","") if m else None

async def apipoint_full_report(gos_or_vin: str):
    if not APIPOINT_KEY:
        return {"error": "no APIPOINT_KEY"}
    clean = gos_or_vin.upper().replace(" ","")
    sources = "gibdd,dtp,zalog,probeg,fsspdata,nomerogram,offerbygosnum,carprices,regperiods,gibddhistory,autophoto,gai,fines,osago"
    payload = {"sources": sources}
    if is_vin(clean):
        payload["vin"] = clean
    else:
        payload["gosnum"] = clean
        payload["vin"] = ""
    headers = {
        "Authorization": f"Bearer {APIPOINT_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(APIPOINT_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=40)) as resp:
                txt = await resp.text()
                print(f"[APIPOINT] status={resp.status} resp[:2000]={txt[:2000]}")
                try:
                    data = json.loads(txt)
                except:
                    data = {"raw": txt}
                if resp.status != 200:
                    return {"status": resp.status, "error": txt[:2000], "payload": payload, "data": data}
                return data
        except Exception as e:
            return {"error": f"exception {e}", "payload": payload}

async def fetch_ad_data(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                html = await resp.text()
                if HAS_BS4:
                    soup = BeautifulSoup(html, "html.parser")
                    title = soup.title.string if soup.title else ""
                    og_desc = soup.find("meta", property="og:description")
                    desc = og_desc["content"] if og_desc and og_desc.has_attr("content") else soup.get_text()[:2000]
                    images = [m["content"] for m