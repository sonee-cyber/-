# -*- coding: utf-8 -*-
import asyncio, os, base64, re, json, logging, datetime
import aiohttp
logging.basicConfig(level=logging.INFO)
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except:
    HAS_BS4 = False

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OR_KEY = os.getenv("OPENAI_API_KEY")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN")
APIPOINT_URL = "https://apipoint.ru/api/call"

print(f"BOOT v12 FIX ENCODING | BOT={bool(BOT_TOKEN)} APIPOINT={bool(APIPOINT_KEY)}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN empty")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

user_data = {}

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔍 Check by number/VIN/link")],
        [KeyboardButton(text="🚗 I am at the car (photo+video)")],
        [KeyboardButton(text="📩 Request VIN from seller")],
        [KeyboardButton(text="🔄 Reset")],
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📩 Request VIN from seller")],
        [KeyboardButton(text="🔄 Reset")],
    ], resize_keyboard=True)

HOOD_STEPS = ["1/8 Front","2/8 Back","3/8 Left side","4/8 Right side","5/8 VIN","6/8 Dashboard","7/8 Under hood","8/8 Video"]

def normalize_plate(s: str) -> str:
    s = s.upper().replace(" ", "").replace("-", "")
    mapping = {'A':'\u0410','B':'\u0412','E':'\u0415','K':'\u041a','M':'\u041c','H':'\u041d','O':'\u041e','P':'\u0420','C':'\u0421','T':'\u0422','Y':'\u0423','X':'\u0425'}
    out = ""
    for ch in s:
        out += mapping.get(ch, ch)
    return out

def is_vin(s: str):
    return bool(re.match(r'^[A-HJ-NPR-Z0-9]{17}$', s.upper().strip()))

def is_gosnum(s: str):
    s_clean = s.upper().replace(" ", "").replace("-", "")
    allowed = "\u0410\u0412\u0415\u041a\u041c\u041d\u041e\u0420\u0421\u0422\u0423\u0425ABEKMHOPCTYX"
    pattern = rf'^[{allowed}]\d{{3}}[{allowed}]{{2}}\d{{2,3}}$'
    return bool(re.match(pattern, s_clean))

def extract_gos(t: str):
    allowed = "\u0410\u0412\u0415\u041a\u041c\u041d\u041e\u0420\u0421\u0422\u0423\u0425ABEKMHOPCTYX"
    m = re.search(rf'[{allowed}]\d{{3}}[{allowed}]{{2}}\s*\d{{2,3}}', t.upper())
    if m:
        return normalize_plate(m.group(0))
    return None

def extract_vin(t: str):
    m = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', t.upper())
    return m.group(0) if m else None

def extract_urls(t):
    return re.findall(r'https?://[^\s]+', t)

async def apipoint_call(payload):
    headers = {"Authorization": f"Bearer {APIPOINT_KEY}", "Content-Type": "application/json", "Accept": "application/json"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(APIPOINT_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=40)) as resp:
                txt = await resp.text()
                print(f"[APIPOINT] {payload} -> {resp.status} {txt[:3000]}")
                try:
                    data = json.loads(txt)
                except:
                    data = {"raw": txt[:5000]}
                return resp.status, data
        except Exception as e:
            return 0, {"error": str(e)}

async def check_by_gos(gos):
    payload = {"sources": "zalog", "gosnum": gos}
    status, data = await apipoint_call(payload)
    return data

async def check_by_vin(vin):
    sources = ["zalog","fsspdata","gibddhistory","dtp","probeg","nomerogram","carprices","gai","regperiods","autophoto","offerbygosnum"]
    combined = {"balance": None, "price": None, "result": {}}
    for src in sources:
        payload = {"sources": src, "vin": vin}
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            if combined["balance"] is None:
                combined["balance"] = data.get("balance") or data.get("data",{}).get("balance")
                combined["price"] = data.get("price") or data.get("data",{}).get("price")
            res = data.get("result") or data.get("data",{}).get("result") or {}
            if isinstance(res, dict):
                if src in res:
                    combined["result"][src] = res[src]
                elif res:
                    combined["result"][src] = res
            else:
                combined["result"][src] = data
    return combined

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
                    desc = og_desc["content"] if og_desc and og_desc.has_attr("content") else soup.get_text()[:3000]
                    images = [m.get("content") for m in soup.find_all("meta", property="og:image") if m.get("content")]
                else:
                    m_title = re.search(r'<title>(.*?)</title>', html, re.I|re.S)
                    title = m_title.group(1) if m_title else ""
                    desc = html[:3000]
                    images = re.findall(r'property="og:image" content="([^"]+)"', html)
                m_price = re.search(r'(\d[\d\s]{3,})\s*₽', html)
                price = m_price.group(1) if m_price else None
                return {"url": url, "title": title[:300], "description": desc[:3000], "price": price, "images": images[:8]}
    except Exception as e:
        return {"url": url, "error": str(e), "images": []}

def b64_from_bytes(b: bytes):
    return base64.b64encode(b).decode()

def get_vin_template(ad=None):
    t = ad.get("title")