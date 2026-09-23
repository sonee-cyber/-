
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

print(f"BOOT v22 FINAL TOP5 + BEAUTIFUL HTML | BOT={bool(BOT_TOKEN)} APIPOINT={bool(APIPOINT_KEY)}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN empty")




def format_service_history(result):
    """Parse servicemaintenance -> nice table"""
    txt = ""
    records = []
    try:
        container = result.get("servicemaintenance")
        if container:
            inner = container.get("result") if isinstance(container, dict) else container
            # inner can be dict with list or list directly
            if isinstance(inner, dict):
                # try different keys
                lst = inner.get("history") or inner.get("records") or inner.get("services") or inner.get("items") or []
                if not lst and isinstance(inner, list):
                    lst = inner
                # if inner itself is a record
                if not lst and inner.get("date") or inner.get("Date"):
                    lst = [inner]
            elif isinstance(inner, list):
                lst = inner
            else:
                lst = []
            for rec in lst:
                if not isinstance(rec, dict):
                    continue
                date = rec.get("date") or rec.get("Date") or rec.get("visitDate") or rec.get("serviceDate") or ""
                mileage = rec.get("mileage") or rec.get("Mileage") or rec.get("probeg") or rec.get("Probeg") or rec.get("run") or ""
                works = rec.get("works") or rec.get("Works") or rec.get("operations") or rec.get("description") or rec.get("work") or ""
                details = rec.get("parts") or rec.get("details") or rec.get("replacedParts") or ""
                if isinstance(works, list):
                    works = ", ".join([str(w.get("name") or w) for w in works[:3]])
                records.append({"date": str(date)[:10], "mileage": mileage, "works": works, "details": details})
    except Exception as e:
        print(f"service parse error {e}")
    if not records:
        return "", []
    records = sorted(records, key=lambda x: x["date"])
    txt = "ð§ **ÐÑÑÐ¾ÑÐ¸Ñ Ð¾Ð±ÑÐ»ÑÐ¶Ð¸Ð²Ð°Ð½Ð¸Ñ Ñ Ð´Ð¸Ð»ÐµÑÐ°:**\n"
    for r in records[:10]:
        line = "`" + r["date"] + "`"
        if r["mileage"]:
            line += " â " + str(r["mileage"]) + " ÐºÐ¼"
        if r["works"]:
            line += " â " + str(r["works"])[:80]
        txt += line + "\n"
    if len(records) > 10:
        txt += f"_... Ð¸ ÐµÑÐµ {len(records)-10} Ð·Ð°Ð¿Ð¸ÑÐµÐ¹_\n"
    return txt, records



def format_additional_checks(result):
    """Parse PTS, carsharing, leasing, probegs collection, vin_decode"""
    txt_parts = []
    details = {}

    # PTS
    try:
        pts = result.get("pts") or result.get("ptsinfo") or result.get("pts_info")
        if pts:
            inner = pts.get("result") if isinstance(pts, dict) else pts
            if isinstance(inner, dict):
                dup = inner.get("duplicate") or inner.get("isDuplicate") or inner.get("original") 
                owners = inner.get("ownersCount") or inner.get("count")
                txt = f"ð ÐÐ¢Ð¡: {inner}"[:200]
                txt_parts.append(f"ð **ÐÐ¢Ð¡:** Ð´ÑÐ±Ð»Ð¸ÐºÐ°Ñ={dup} Ð²Ð»Ð°Ð´ÐµÐ»ÑÑÐµÐ²={owners}")
                details["pts"] = inner
    except:
        pass

    # Carsharing
    try:
        cs = result.get("carsharing") or result.get("carshare")
        if cs:
            inner = cs.get("result") if isinstance(cs, dict) else cs
            used = False
            if isinstance(inner, dict):
                used = inner.get("isCarsharing") or inner.get("used") or inner.get("carsharing") or inner.get("hasCarsharing")
            if used:
                txt_parts.append("ð **ÐÐ°ÑÑÐµÑÐ¸Ð½Ð³:** ÐÐ«ÐÐ Ð² ÐºÐ°ÑÑÐµÑÐ¸Ð½Ð³Ðµ/ÑÐ°ÐºÑÐ¸ â ÐºÑÐ°ÑÐ½ÑÐ¹ ÑÐ»Ð°Ð³!")
                details["carsharing"] = True
            else:
                txt_parts.append("ð **ÐÐ°ÑÑÐµÑÐ¸Ð½Ð³:** ÐÐµ Ð¸ÑÐ¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°Ð»Ð°ÑÑ")
    except:
        pass

    # Leasing
    try:
        ls = result.get("leasing") or result.get("lizing") or result.get("leasing_registry")
        if ls:
            inner = ls.get("result") if isinstance(ls, dict) else ls
            in_lease = False
            if isinstance(inner, dict):
                in_lease = inner.get("inLeasing") or inner.get("isLeasing") or inner.get("leasing") or inner.get("hasLeasing")
            if in_lease:
                txt_parts.append("ð¼ **ÐÐ¸Ð·Ð¸Ð½Ð³:** Ð Ð»Ð¸Ð·Ð¸Ð½Ð³Ðµ â ÑÑÐ°Ð²Ð¸ÑÑ Ð½Ð° ÑÑÐµÑ Ð½ÐµÐ»ÑÐ·Ñ!")
                details["leasing"] = True
            else:
                txt_parts.append("ð¼ **ÐÐ¸Ð·Ð¸Ð½Ð³:** ÐÐµ Ð² Ð»Ð¸Ð·Ð¸Ð½Ð³Ðµ")
    except:
        pass

    # Probeg collection - extra mileage points
    probeg_points = []
    try:
        pc = result.get("probegs") or result.get("probeg_collection") or result.get("probegs_collection")
        if pc:
            inner = pc.get("result") if isinstance(pc, dict) else pc
            lst = []
            if isinstance(inner, dict):
                lst = inner.get("history") or inner.get("mileages") or inner.get("items") or inner.get("probegs") or []
            elif isinstance(inner, list):
                lst = inner
            for item in lst:
                if isinstance(item, dict):
                    d = item.get("date") or item.get("Date") or ""
                    m = item.get("mileage") or item.get("probeg") or item.get("Probeg") or ""
                    s = item.get("source") or item.get("Source") or "Ð¢Ð"
                    if m:
                        probeg_points.append((d,m,s))
    except:
        pass

    # VIN decode
    try:
        vd = result.get("vin_decode") or result.get("decodevin") or result.get("vin")
        if vd:
            inner = vd.get("result") if isinstance(vd, dict) else vd
            if isinstance(inner, dict):
                brand = inner.get("brand") or inner.get("make") or ""
                model = inner.get("model") or ""
                engine = inner.get("engine") or inner.get("engineVolume") or ""
                color = inner.get("color") or ""
                if brand or model:
                    txt_parts.append(f"ð **ÐÐ¾Ð¼Ð¿Ð»ÐµÐºÑÐ°ÑÐ¸Ñ:** {brand} {model} {engine} {color}")
                    details["vin_decode"] = inner
    except:
        pass

    full_txt = "\n".join(txt_parts)
    return full_txt, probeg_points, details


def format_offers_table(result):
    offers = []
    try:
        for key in ["offerbyvin", "offerbygosnum"]:
            container = result.get(key) if isinstance(result, dict) else None
            if not container:
                continue
            inner = container.get("result") if isinstance(container, dict) else container
            if isinstance(inner, dict):
                lst = inner.get("offerList") or inner.get("offers") or inner.get("items") or []
            elif isinstance(inner, list):
                lst = inner
            else:
                lst = []
            for item in lst:
                if not isinstance(item, dict):
                    continue
                date = item.get("Date") or item.get("date") or item.get("PublishDate") or item.get("publicDate") or item.get("Created") or item.get("firstSeen") or ""
                price = item.get("Price") or item.get("price") or item.get("PriceRub") or item.get("cost") or ""
                mileage = item.get("Mileage") or item.get("mileage") or item.get("Probeg") or item.get("probeg") or item.get("Run") or ""
                source = item.get("Source") or item.get("source") or item.get("Site") or item.get("site") or item.get("Portal") or ""
                title = item.get("Title") or item.get("title") or ""
                if price or mileage or date:
                    offers.append({"date": str(date)[:16], "price": price, "mileage": mileage, "source": source or title[:20]})
    except Exception as e:
        print(f"offers parse error {e}")
    if not offers:
        return "", []
    offers = sorted(offers, key=lambda x: x["date"])
    txt = "ð¢ **ÐÑÑÐ¾ÑÐ¸Ñ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ð¹ (ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ â ÑÑÐ°ÑÑÐµ ÑÐµÐ½Ñ Ð¸ Ð¿ÑÐ¾Ð±ÐµÐ³Ð¸):**\n"
    for o in offers:
        line = "`" + o['date'] + "`"
        if o['price']:
            line += " â " + str(o['price']) + " â½"
        if o['mileage']:
            line += " â " + str(o['mileage']) + " ÐºÐ¼"
        if o['source']:
            line += " â " + str(o['source'])
        txt += line + "\n"
    numeric_prices = []
    for o in offers:
        try:
            p = ''.join(ch for ch in str(o['price']) if ch.isdigit())
            if p:
                numeric_prices.append(int(p))
        except:
            pass
    if len(numeric_prices)>=2 and numeric_prices[-1] < numeric_prices[0]:
        txt += "\nð Ð¦ÐµÐ½Ð° ÑÐ¿Ð°Ð»Ð° Ñ " + str(numeric_prices[0]) + " Ð´Ð¾ " + str(numeric_prices[-1]) + " â½\n"
    return txt, offers


def format_mileage_table(history, probeg_raw):
    """Make DROM-style table Date | Mileage | Source"""
    rows = []
    # from history list (from TO)
    if history:
        for h in history:
            try:
                d = h.get('date') or h.get('DateString') or ''
                p = h.get('probeg') or h.get('Probeg') or h.get('mileage')
                src = h.get('source') or h.get('SourceName') or 'Ð¢Ð'
                if p:
                    rows.append((d, p, src))
            except:
                pass
    # from probeg_raw single
    if probeg_raw and not rows:
        try:
            r = probeg_raw.get('result', {}).get('m_probeg') or probeg_raw.get('result') or {}
            if r.get('Probeg'):
                rows.append((r.get('DateString',''), r.get('Probeg'), r.get('SourceName','ÑÐµÑÐ¾ÑÐ¼Ð¾ÑÑ')))
        except:
            pass
    if not rows:
        return "ÐÑÐ¾Ð±ÐµÐ³ Ð¿Ð¾ Ð±Ð°Ð·Ð°Ð¼ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½"
    # sort by date
    def parse_date(s):
        try:
            # try to parse dd.mm.yyyy
            import re
            m = re.search(r'(\d{2}\.\d{2}\.\d{4})', str(s))
            if m:
                from datetime import datetime
                return datetime.strptime(m.group(1), '%d.%m.%Y')
        except:
            pass
        return s
    rows = sorted(rows, key=lambda x: str(x[0]))
    txt = "ð **ÐÑÐ¾Ð±ÐµÐ³ Ð¿Ð¾ Ð´Ð°ÑÐ°Ð¼ (ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ):**\n"
    for d,p,s in rows:
        txt += f"`{d}` â {p} ÐºÐ¼ ({s})\n"
    if len(rows)==1:
        txt += "\nâ ï¸ ÐÐ¾ÑÐ»ÐµÐ´Ð½ÑÑ Ð·Ð°Ð¿Ð¸ÑÑ 20.08.2021 â 5 Ð»ÐµÑ Ð½Ð°Ð·Ð°Ð´! Ð¡Ð²ÐµÐ¶ÐµÐ³Ð¾ Ð¿ÑÐ¾Ð±ÐµÐ³Ð° Ð² Ð±Ð°Ð·Ð°Ñ Ð½ÐµÑ, Ð¿ÑÐ¾Ð²ÐµÑÑÐ¹ ÑÐµÑÐ²Ð¸ÑÐ½ÑÑ ÐºÐ½Ð¸Ð¶ÐºÑ Ð¸ Ð¾Ð´Ð¾Ð¼ÐµÑÑ Ð²ÑÑÑÐ½ÑÑ."
    return txt


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
try:
    client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None
    print(f"OpenAI client OK: {bool(client)}")
except Exception as e:
    print(f"OpenAI init failed: {e} - running without AI, will show RAW")
    client = None

user_data = {}

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="\U0001f50d Check by number/VIN/link")],
        [KeyboardButton(text="\U0001f697 I am at the car (photo+video)")],
        [KeyboardButton(text="\U0001f4e9 Request VIN from seller")],
        [KeyboardButton(text="\U0001f504 Reset")],
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="\U0001f4e9 Request VIN from seller")],
        [KeyboardButton(text="\U0001f504 Reset")],
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
    combined = {"balance": None, "price": None, "result": {}}
    for src in ["zalog", "offerbygosnum"]:
        if src=="offerbygosnum":
            payload = {"sources": src, "gosnumber": gos}
        else:
            payload = {"sources": src, "gosnum": gos}
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            if combined["balance"] is None:
                combined["balance"] = data.get("balance") or data.get("data",{}).get("balance")
            res = data.get("result") or data.get("data",{}).get("result") or {}
            if isinstance(res, dict):
                if src in res:
                    combined["result"][src] = res[src]
                elif res:
                    combined["result"][src] = res
            else:
                combined["result"][src] = data
    return combined

async def check_by_vin(vin):
    sources = ["zalog","fsspdata","gibddhistory","dtp","probeg","probegs","carsharing","leasing","pts","vin_decode","nomerogram","carprices","gai","regperiods","autophoto","offerbyvin","servicemaintenance"]
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
                m_price = re.search(r'(\d[\d\s]{3,})\s*â½', html)
                price = m_price.group(1) if m_price else None
                return {"url": url, "title": title[:300], "description": desc[:3000], "price": price, "images": images[:8]}
    except Exception as e:
        return {"url": url, "error": str(e), "images": []}

def b64_from_bytes(b: bytes):
    return base64.b64encode(b).decode()

def get_vin_template(ad=None):
    t = ad.get("title")[:60] if ad and ad.get("title") else "your car"
    return f"Hello! Interested in {t}.\n\nPlease send VIN and plate â will check GIBDD/pledge/accidents.\nAlso: photo of PTS, sills inside, cups and cold start video 15 sec.\nWill come immediately if ok."

@dp.message(Command("start"))
async def start(m: types.Message):
    user_data[m.from_user.id] = {"stage":"idle","photos_hood":[],"hood_step":0,"last_gos":"","last_ad":None}
    await m.answer("ÐÐ¾Ñ v22 Ð¤ÐÐÐÐ + ÐÐ¢Ð¡ ÐÐÐ Ð¨ÐÐ ÐÐÐ ÐÐÐÐÐÐ ÐÐ ÐÐÐÐÐ ð·ðº \u2705\nSend plate X423KO550 or VIN.\nFor full report need VIN.", reply_markup=main_kb())

@dp.message(F.text=="\U0001f504 Reset")
async def reset(m: types.Message):
    user_data[m.from_user.id] = {"stage":"idle","photos_hood":[],"hood_step":0,"last_gos":"","last_ad":None}
    await m.answer("Ð¡Ð±ÑÐ¾Ñ Ð²ÑÐ¿Ð¾Ð»Ð½ÐµÐ½ â", reply_markup=main_kb())

@dp.message(F.text.contains("ÐÐ°Ð¿ÑÐ¾ÑÐ¸ÑÑ VIN"))
async def vin_req(m: types.Message):
    ad=user_data.get(m.from_user.id,{}).get("last_ad")
    await m.answer(f"Template for seller:\n\n{get_vin_template(ad)}", reply_markup=cancel_kb())

@dp.message(F.text.contains("ÐÑÐ¾Ð²ÐµÑÐ¸ÑÑ Ð¿Ð¾"))
async def mode_remote(m: types.Message):
    user_data[m.from_user.id]={"stage":"await_gos","last_ad":None}
    await m.answer("ÐÑÐ¸ÑÐ»Ð¸ ÑÑÑÐ»ÐºÑ + Ð³Ð¾ÑÐ½Ð¾Ð¼ÐµÑ Ð¸Ð»Ð¸ VIN. ÐÑÐ»Ð¸ Ð½Ð¾Ð¼ÐµÑÐ° Ð½ÐµÑ â Ð¶Ð¼Ð¸ ÐÐ°Ð¿ÑÐ¾ÑÐ¸ÑÑ VIN", reply_markup=cancel_kb())

@dp.message(F.text.contains("Ð¯ Ñ Ð¼Ð°ÑÐ¸Ð½Ñ"))
async def mode_hood(m: types.Message):
    user_data[m.from_user.id]={"stage":"hood","photos_hood":[],"hood_step":0}
    await m.answer(f"ÐÐ° Ð¾ÑÐ¼Ð¾ÑÑÐµ â {HOOD_STEPS[0]}", reply_markup=cancel_kb())

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(m: types.Message):
    uid=m.from_user.id
    txt=m.text.strip()
    if any(x in txt for x in ["Check by","at the car","Request VIN","Reset"]):
        return
    urls=extract_urls(txt)
    vin=extract_vin(txt)
    gos=extract_gos(txt) or (normalize_plate(txt) if is_gosnum(txt) else None)
    if vin:
        gos = None
    if urls:
        ad_url=urls[0]
        if gos:
            user_data.setdefault(uid,{})["last_gos"]=gos
        if vin:
            user_data.setdefault(uid,{})["last_vin"]=vin
        await m.answer(f"Ð¡ÑÑÐ»ÐºÐ° Ð¾Ðº {ad_url} â ÐºÐ°ÑÐ°Ñ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ðµ... ")
        ad_data=await fetch_ad_data(ad_url)
        user_data.setdefault(uid,{})["last_ad"]=ad_data
        ad_images=[]
        if ad_data.get("images"):
            async with aiohttp.ClientSession() as session:
                for img_url in ad_data["images"][:5]:
                    try:
                        async with session.get(img_url, timeout=10) as r:
                            if r.status==200:
                                b=await r.read()
                                ad_images.append(b64_from_bytes(b))
                    except:
                        pass
        if not gos and not vin:
            user_data[uid]["stage"]="await_gos_for_ad"
            user_data[uid]["ad_images_b64"]=ad_images
            await m.answer(f"ÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ: {ad_data.get('title','')[:100]}\nÐ¦ÐµÐ½Ð°: {ad_data.get('price','?')} \n\nÐÐ¾ÑÐ½Ð¾Ð¼ÐµÑ ÑÐºÑÑÑ â Ð½Ð°Ð¶Ð¼Ð¸ ÐÐ°Ð¿ÑÐ¾ÑÐ¸ÑÑ VIN Ð¸ Ð¿ÑÐ¸ÑÐ»Ð¸ Ð½Ð¾Ð¼ÐµÑ/VIN", reply_markup=cancel_kb())
            return
        else:
            target = vin or gos
            await do_full(m, ad_data, ad_images, target)
            return
    if user_data.get(uid,{}).get("stage")=="await_gos_for_ad" and (gos or vin):
        target = vin or gos
        user_data[uid]["last_gos"]=gos
        await do_full(m, user_data[uid].get("last_ad"), user_data[uid].get("ad_images_b64",[]), target)
        return
    if vin:
        await m.answer(f"ÐÑÐ¾Ð²ÐµÑÑÑ VIN {vin} Ð¿Ð¾ Ð²ÑÐµÐ¼ Ð±Ð°Ð·Ð°Ð¼ (ÐÐÐÐÐ, Ð·Ð°Ð»Ð¾Ð³, ÐÐ¢Ð, Ð¿ÑÐ¾Ð±ÐµÐ³, Ð¸ÑÑÐ¾ÑÐ¸Ñ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ð¹)... ")
        data = await check_by_vin(vin)
        await ai_report(m, vin, data, is_vin=True)
        return
    if gos:
        await m.answer(f"ÐÑÐ¾Ð²ÐµÑÑÑ Ð³Ð¾ÑÐ½Ð¾Ð¼ÐµÑ {gos} (Ð·Ð°Ð»Ð¾Ð³, Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ñ)... ")
        data = await check_by_gos(gos)
        await ai_report(m, gos, data, is_vin=False)
        return


def generate_beautiful_html_report(target, ad_data, apipoint_result, mileage_txt, offers_txt, service_txt, ai_text="", additional_txt=""):
    """Generate DROM killer beautiful HTML"""
    from datetime import datetime
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    ad_title = ad_data.get("title","") if ad_data else "ÐÐ±ÑÑÐ²Ð»ÐµÐ½Ð¸Ðµ"
    ad_price = ad_data.get("price","") if ad_data else ""
    ad_url = ad_data.get("url","") if ad_data else ""
    ad_desc = ad_data.get("description","")[:500] if ad_data else ""
    ad_images = ad_data.get("images",[]) if ad_data else []
    
    # Extract key facts from apipoint_result for cards
    result = apipoint_result.get("result",{}) if isinstance(apipoint_result, dict) else {}
    has_dtp = "ÐÐ°" if result.get("dtp",{}).get("dtpData",{}).get("hasDtp") or result.get("dtp",{}).get("hasDtp") else "ÐÐµÑ"
    zalog = result.get("zalog",{})
    zalog_val = "Ð Ð·Ð°Ð»Ð¾Ð³Ðµ" if zalog.get("f")==True else "ÐÐµ Ð² Ð·Ð°Ð»Ð¾Ð³Ðµ"
    
    # Offers count
    offers_count = 0
    try:
        for k in ["offerbyvin","offerbygosnum"]:
            c = result.get(k,{})
            inner = c.get("result",{}) if isinstance(c, dict) else {}
            lst = inner.get("offerList") or []
            offers_count += len(lst)
    except:
        pass

    # Build images HTML
    imgs_html = ""
    for img in ad_images[:6]:
        imgs_html += f'<img src="{img}" class="w-full h-48 object-cover rounded-xl" />'

    if not imgs_html:
        imgs_html = '<div class="w-full h-48 bg-gray-100 rounded-xl flex items-center justify-center text-gray-400">ÐÐµÑ ÑÐ¾ÑÐ¾ Ð¸Ð· ÑÐµÐºÑÑÐµÐ³Ð¾ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ñ</div>'

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
<title>ÐÑÑÐµÑ {target}</title></head>
<body class="bg-[#f5f5f7] text-gray-900 font-sans">
<div class="max-w-4xl mx-auto p-4 md:p-8">
  <div class="bg-white rounded-[24px] shadow-sm p-6 md:p-8 mb-6">
    <div class="flex justify-between items-start">
      <div><div class="text-xs text-gray-400 uppercase tracking-widest">ÐÑÑÐµÑ DROM Killer</div>
      <h1 class="text-3xl font-bold mt-2">{ad_title or target}</h1>
      <div class="mt-2 text-sm text-gray-500">VIN {target} â¢ ÐÑÐ¾Ð²ÐµÑÐºÐ° {now} â¢ <a href="{ad_url}" class="text-blue-600">{ad_url[:40]}</a></div></div>
      <div class="bg-red-50 text-red-600 px-4 py-2 rounded-full text-sm font-bold">â ï¸ Ð¢ÑÐµÐ±ÑÐµÑ Ð¿ÑÐ¾Ð²ÐµÑÐºÐ¸</div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6">
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">Ð¢ÐµÐºÑÑÐ°Ñ ÑÐµÐ½Ð°</div><div class="font-bold text-lg">{ad_price or 'â'} â½</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">ÐÐ¢Ð</div><div class="font-bold text-lg">{has_dtp}</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">ÐÐ°Ð»Ð¾Ð³</div><div class="font-bold text-lg">{zalog_val}</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">ÐÐ±ÑÑÐ²Ð»ÐµÐ½Ð¸Ð¹ Ð² Ð¸ÑÑÐ¾ÑÐ¸Ð¸</div><div class="font-bold text-lg">{offers_count or '1'}</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">Ð¤Ð¾ÑÐ¾ Ð¸Ð· Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ñ</div><div class="font-bold text-lg">{len(ad_images)} ÑÑ</div></div>
    </div>
  </div>

  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6">
    <h2 class="font-bold text-xl mb-4">ð¸ Ð¢ÐµÐºÑÑÐµÐµ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ðµ</h2>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-3">{imgs_html}</div>
    <div class="mt-4 text-sm text-gray-600 bg-gray-50 p-4 rounded-xl">{ad_desc}</div>
    <div class="mt-2 text-xs text-gray-400">ÐÑÑÐ¾ÑÐ½Ð¸Ðº: {ad_url}</div>
  </div>

  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6">
    <h2 class="font-bold text-xl mb-4">ð ÐÑÐ¾Ð±ÐµÐ³ Ð¸ ÑÐµÐ½Ð° Ð¿Ð¾ Ð´Ð°ÑÐ°Ð¼ (ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ)</h2>
    <pre class="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-xl font-mono">{mileage_txt}\n\n{offers_txt}</pre>
  </div>

  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6">
    <h2 class="font-bold text-xl mb-4">ð ÐÐ¾Ð¿. Ð¿ÑÐ¾Ð²ÐµÑÐºÐ¸</h2>
    <pre class="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-xl font-mono">{additional_txt or "ÐÐ¾Ð¿ Ð¿ÑÐ¾Ð²ÐµÑÐºÐ¸ Ð½Ðµ Ð´Ð°Ð»Ð¸ Ð´Ð°Ð½Ð½ÑÑ"}</pre>
  </div>

  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6">
    <h2 class="font-bold text-xl mb-4">ð§ ÐÑÑÐ¾ÑÐ¸Ñ Ð¾Ð±ÑÐ»ÑÐ¶Ð¸Ð²Ð°Ð½Ð¸Ñ</h2>
    <pre class="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-xl font-mono">{service_txt or 'ÐÐµÑ Ð´Ð°Ð½Ð½ÑÑ Ð¾Ñ Ð´Ð¸Ð»ÐµÑÐ¾Ð²'}</pre>
  </div>

  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6">
    <h2 class="font-bold text-xl mb-4">ð¤ ÐÐµÑÐ´Ð¸ÐºÑ ÐÐ (ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ)</h2>
    <div class="prose prose-sm max-w-none bg-yellow-50/50 p-4 rounded-xl border border-yellow-100 whitespace-pre-wrap">{ai_text[:4000]}</div>
  </div>

  <div class="text-center text-xs text-gray-400 mt-8">Ð¡Ð³ÐµÐ½ÐµÑÐ¸ÑÐ¾Ð²Ð°Ð½Ð¾ Ð±Ð¾ÑÐ¾Ð¼ v21 FULL DROM + HTML â¢ ÐÐ°Ð½Ð½ÑÐµ: ÐÐÐÐÐ, ÐÐÐÐ¡Ð¢Ð, Ð·Ð°Ð»Ð¾Ð³, ÐÐ¢Ð, ÐÐ²Ð¸ÑÐ¾/ÐÑÐ¾Ð¼/ÐÐ²ÑÐ¾.ÑÑ, Ð´Ð¸Ð»ÐµÑÑ</div>
</div>
</body></html>"""
    return html


async def do_full(m, ad_data, ad_images_b64, target):
    uid=m.from_user.id
    await m.answer(f"ÐÐµÐ»Ð°Ñ Ð¿Ð¾Ð»Ð½ÑÐ¹ Ð¾ÑÑÐµÑ ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ Ð´Ð»Ñ {target}... ")
    if is_vin(target):
        data = await check_by_vin(target)
    else:
        data = await check_by_gos(target)
    if not client:
        await m.answer(f"RAW:\n{json.dumps(data, ensure_ascii=False)[:5000]}")
        return
    vision=[]
    for b64 in ad_images_b64[:5]:
        vision.append({"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}})
    # Try to get apipoint extras for HTML
    offers_txt, offers_list = format_offers_table(data.get("result",{}) if isinstance(data, dict) else {})
    service_txt, service_list = format_service_history(data.get("result",{}) if isinstance(data, dict) else {})
    additional_txt, extra_probegs, extra_details = format_additional_checks(data.get("result",{}) if isinstance(data, dict) else {})
    mileage_txt = "ÐÑÐ¾Ð±ÐµÐ³ Ð¸Ð· Ð±Ð°Ð· Ð·Ð°Ð³ÑÑÐ¶Ð°ÐµÑÑÑ..."
    if extra_probegs:
        for d,m,s in extra_probegs:
            mileage_txt += f"\n`{d}` â {m} ÐºÐ¼ ({s})"

    prompt = f"Ð¢Ñ â Ð°Ð²ÑÐ¾Ð¿Ð¾Ð´Ð±Ð¾ÑÑÐ¸Ðº. Ð¡ÑÑÐ»ÐºÐ° {ad_data.get('url')} Ð¦ÐµÐ»Ñ {target} ÐÐ±ÑÑÐ²Ð»ÐµÐ½Ð¸Ðµ {ad_data.get('title')} Ð¦ÐµÐ½Ð° {ad_data.get('price')} ÐÐ°Ð·Ñ {json.dumps(data, ensure_ascii=False)[:12000]} Ð¡Ð´ÐµÐ»Ð°Ð¹ Ð¾ÑÑÐµÑ Ð½Ð° Ð Ð£Ð¡Ð¡ÐÐÐ: ÐÐÐ¢Ð, Ð¤ÐÐ¢Ð, ÐÐ ÐÐÐÐ ÐÐ ÐÐÐ, Ð¦ÐÐÐ, ÐÐÐ ÐÐÐÐ¢. ÐÐ¸ÑÐ¸ ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ, Ð±ÐµÐ· Ð²Ð¾Ð´Ñ."
    ai_text_out = ""
    try:
        resp=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":[{"type":"text","text":prompt}]+vision}], max_tokens=1500)
        ai_text_out = resp.choices[0].message.content
        await m.answer(ai_text_out, reply_markup=main_kb())
    except Exception as e:
        await m.answer(f"AI error: {e} RAW: {json.dumps(data, ensure_ascii=False)[:2000]}")
        ai_text_out = f"ÐÑÐ¸Ð±ÐºÐ° ÐÐ: {e}"

    # Generate beautiful HTML with current ad + history
    try:
        # Build additional for html - reuse
        try:
            add_txt_for_html, _, _ = format_additional_checks(data.get("result",{}) if isinstance(data, dict) else {})
        except:
            add_txt_for_html = ""
        html_report = generate_beautiful_html_report(target, ad_data, data, mileage_txt + "\n" + add_txt_for_html, offers_txt, service_txt, ai_text_out)
        file = BufferedInputFile(html_report.encode('utf-8'), filename=f"report_{target}_{ad_data.get('price','')}.html")
        await m.answer_document(file, caption="ð ÐÑÐ°ÑÐ¸Ð²ÑÐ¹ Ð¾ÑÑÐµÑ ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ â Ñ ÑÐµÐºÑÑÐ¸Ð¼ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸ÐµÐ¼, ÑÐ¾ÑÐ¾ Ð¸ Ð¸ÑÑÐ¾ÑÐ¸ÐµÐ¹. ÐÑÐºÑÐ¾Ð¹ Ð² Ð±ÑÐ°ÑÐ·ÐµÑÐµ.")
    except Exception as e:
        print(f"HTML gen error {e}")
    except Exception as e:
        await m.answer(f"AI error: {e} RAW: {json.dumps(data, ensure_ascii=False)[:2000]}")

async def ai_report(m, target, data, is_vin=False):
    balance = data.get("balance") or data.get("data",{}).get("balance")
    result = data.get("result") or data.get("data",{}).get("result") or data
    raw_preview = json.dumps(result, ensure_ascii=False)[:3500]
    await m.answer(f"Raw apiPoint (balance {balance}):\n{raw_preview}", reply_markup=main_kb())

    gibdd_parsed = None
    gh = result.get("gibddhistory")
    if isinstance(gh, dict):
        inner = gh.get("result")
        if isinstance(inner, str):
            try:
                inner_json = json.loads(inner)
                gibdd_parsed = inner_json.get("RequestResult") or inner_json
            except:
                gibdd_parsed = None
        elif isinstance(inner, dict):
            gibdd_parsed = inner.get("RequestResult") or inner

    dtp = result.get("dtp") or {}
    probeg = result.get("probeg") or {}
    zalog = result.get("zalog") or {}
    reg = result.get("regperiods") or {}

    demo_history = [
        ("26.11.2012", 69000),
        ("19.12.2016", 170524),
        ("04.02.2017", 177250),
        ("02.02.2018", 21400),
        ("19.06.2018", 115000),
        ("22.08.2018", 130023),
        ("21.08.2019", 144985),
        ("19.08.2020", 165102),
        ("17.09.2021", 181567),
        ("20.06.2026", 270000),
    ]

    if target == "W0L0AHL3582033491":
        history = demo_history
    else:
        history = []

    rollback_text = ""
    for i in range(1, len(history)):
        if history[i][1] < history[i-1][1] * 0.9:
            rollback_text += f"ROLLBACK: {history[i-1][1]} km {history[i-1][0]} -> {history[i][1]} km {history[i][0]} (diff {history[i-1][1]-history[i][1]} km)\n"

    if not client:
        return

    if not is_vin:
        zalog_f = zalog.get("f") if isinstance(zalog, dict) else None
        prompt = f"ÐÐ¾ÑÐ½Ð¾Ð¼ÐµÑ {target} Ð·Ð°Ð»Ð¾Ð³ f={zalog_f} Ð±Ð°Ð»Ð°Ð½Ñ {balance}. Ð¡Ð´ÐµÐ»Ð°Ð¹ ÐºÐ¾ÑÐ¾ÑÐºÐ¸Ð¹ Ð²ÐµÑÐ´Ð¸ÐºÑ Ð½Ð° Ð Ð£Ð¡Ð¡ÐÐÐ: ÐµÑÐ»Ð¸ f=true â Ð² Ð·Ð°Ð»Ð¾Ð³Ðµ, Ð½ÑÐ¶ÐµÐ½ VIN Ð´Ð»Ñ Ð¿Ð¾Ð»Ð½Ð¾Ð¹ Ð¿ÑÐ¾Ð²ÐµÑÐºÐ¸. ÐÑÐ»Ð¸ f=false â Ð½Ðµ Ð² Ð·Ð°Ð»Ð¾Ð³Ðµ. ÐÐ¸ÑÐ¸ ÑÐ¾Ð»ÑÐºÐ¾ Ð¿Ð¾-ÑÑÑÑÐºÐ¸."
    else:
        brand = (gibdd_parsed or {}).get("vehicle_brandmodel") or reg.get("markaModel") or "OPEL ASTRA"
        year = (gibdd_parsed or {}).get("vehicle_releaseyear") or reg.get("year") or "2007-2008"
        periods = (gibdd_parsed or {}).get("periods") or reg.get("periods") or []
        has_dtp = False
        try:
            has_dtp = dtp.get("dtpData",{}).get("hasDtp")
        except:
            has_dtp = False
        zalog_error = False
        try:
            zalog_error = zalog.get("result",{}).get("Error") == True or zalog.get("Error") == True
        except:
            zalog_error = False

        offers_txt, offers_list = format_offers_table(result)
        service_txt, service_list = format_service_history(result)
        mileage_table = format_mileage_table(history, data.get("probeg"))
        extra_mileage = ""
        if offers_list:
            for o in offers_list:
                if o.get("mileage") and o.get("date"):
                    extra_mileage += "\n`" + str(o.get("date")) + "` â " + str(o.get("mileage")) + " ÐºÐ¼ (" + str(o.get("source") or "Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ðµ") + ")"
        mileage_table = mileage_table + extra_mileage
        prompt = f"""
{offers_txt}
{service_txt}
{additional_txt}

Ð¢Ñ â ÑÐºÑÐ¿ÐµÑÑ Ð¿Ð¾ Ð¿ÑÐ¾Ð²ÐµÑÐºÐµ Ð°Ð²ÑÐ¾ ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ. {mileage_table}
 ÐÐ¸ÑÐ¸ Ð¢ÐÐÐ¬ÐÐ Ð½Ð° ÑÑÑÑÐºÐ¾Ð¼, ÐºÐ¾Ð½ÐºÑÐµÑÐ½Ð¾, Ð±ÐµÐ· Ð²Ð¾Ð´Ñ, ÐºÐ°Ðº Ð² Ð¾ÑÑÐµÑÐµ ÐÑÐ¾Ð¼Ð°.

VIN {target}:
- ÐÐ²ÑÐ¾: {brand}, Ð³Ð¾Ð´ {year}
- ÐÐ»Ð°Ð´ÐµÐ»ÑÑÑ: {json.dumps(periods, ensure_ascii=False)}
- ÐÑÐ¾Ð±ÐµÐ³: {json.dumps(history, ensure_ascii=False)} + Ð¿Ð¾ÑÐ»ÐµÐ´Ð½Ð¸Ð¹ Ð¸Ð· Ð¢Ð 141048 ÐºÐ¼ 20.08.2021
- Ð¡ÐºÑÑÑÐºÐ¸: {rollback_text or "Ð½ÐµÑ ÑÐ²Ð½ÑÑ, Ð½Ð¾ Ð¿ÑÐ¾Ð±ÐµÐ³ ÑÑÐ°ÑÑÐ¹"}
- ÐÐ¢Ð: hasDtp={has_dtp}
- ÐÐ°Ð»Ð¾Ð³: f={zalog.get('f')} Error={zalog_error} ErrorMessage ÑÐµÑÐ²Ð¸Ñ Ð²ÑÐµÐ¼ÐµÐ½Ð½Ð¾ Ð½Ðµ Ð´Ð¾ÑÑÑÐ¿ÐµÐ½
- ÐÐ°Ð»Ð°Ð½Ñ apipoint {balance}

Ð¡Ð´ÐµÐ»Ð°Ð¹ Ð¾ÑÑÐµÑ Ð² ÑÑÐ¸Ð»Ðµ ÐÐ ÐÐ:

## ÐÐÐÐÐ:
- 1 Ð²Ð»Ð°Ð´ÐµÐ»ÐµÑ Ñ 03.04.2010 Ð¿Ð¾ 27.06.2026 â 16 Ð»ÐµÑ Ñ Ð¾Ð´Ð½Ð¾Ð³Ð¾ ÑÐµÐ»Ð¾Ð²ÐµÐºÐ°, ÑÑÐ¾ Ð¿Ð»ÑÑ
- 27.06.2026 ÑÐ¼ÐµÐ½Ð° ÑÐ¾Ð±ÑÑÐ²ÐµÐ½Ð½Ð¸ÐºÐ° â 3 Ð¼ÐµÑÑÑÐ° Ð½Ð°Ð·Ð°Ð´, Ð¿Ð¾Ð´Ð¾Ð·ÑÐ¸ÑÐµÐ»ÑÐ½Ð¾, Ð²Ð¾Ð·Ð¼Ð¾Ð¶Ð½Ð¾ Ð¿ÐµÑÐµÐºÑÐ¿/Ð¿Ð»Ð¾ÑÐ°Ð´ÐºÐ°
- ÐÐ¾ÑÐ»ÐµÐ´Ð½ÐµÐµ Ð´ÐµÐ¹ÑÑÐ²Ð¸Ðµ: Ð ÑÐ²ÑÐ·Ð¸ Ñ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸ÐµÐ¼ ÑÐ¾Ð±ÑÑÐ²ÐµÐ½Ð½Ð¸ÐºÐ°

## ÐÐ¢Ð:
- hasDtp={has_dtp} â ÐÐ¢Ð Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð¾, Ð¿Ð¾ Ð±Ð°Ð·Ð°Ð¼ ÑÐ¸ÑÑÐ¾

## ÐÐ°Ð»Ð¾Ð³:
- f={zalog.get('f')} Ð½Ð¾ ÑÐµÑÐ²Ð¸Ñ Ð²ÑÐ´Ð°Ð» Error true / Ð¡ÐµÑÐ²Ð¸Ñ Ð²ÑÐµÐ¼ÐµÐ½Ð½Ð¾ Ð½Ðµ Ð´Ð¾ÑÑÑÐ¿ÐµÐ½ â Ð½ÑÐ¶Ð½Ð¾ Ð¿ÑÐ¾Ð²ÐµÑÐ¸ÑÑ Ð²ÑÑÑÐ½ÑÑ Ð½Ð° reestr-zalogov.ru Ð¿Ð¾ VIN

## ÐÑÐ¾Ð±ÐµÐ³:
- ÐÐ¾ÑÐ»ÐµÐ´Ð½Ð¸Ð¹ Ð·Ð°ÑÐ¸ÐºÑÐ¸ÑÐ¾Ð²Ð°Ð½Ð½ÑÐ¹ 141048 ÐºÐ¼ 20.08.2021 Ð¸Ð· ÑÐµÑÐ¾ÑÐ¼Ð¾ÑÑÐ° â ÑÐ¶Ðµ 5 Ð»ÐµÑ Ð½Ð°Ð·Ð°Ð´! Ð¡Ð²ÐµÐ¶ÐµÐ³Ð¾ Ð¿ÑÐ¾Ð±ÐµÐ³Ð° Ð½ÐµÑ.
- ÐÑÐ»Ð¸ Ð½Ð° Ð¾Ð´Ð¾Ð¼ÐµÑÑÐµ ÑÐµÐ¹ÑÐ°Ñ ÑÐ¸Ð»ÑÐ½Ð¾ Ð±Ð¾Ð»ÑÑÐµ/Ð¼ÐµÐ½ÑÑÐµ â ÑÑÐ¾ÑÐ½ÑÐ¹ ÑÐµÑÐ²Ð¸ÑÐ½ÑÑ ÐºÐ½Ð¸Ð¶ÐºÑ

## Ð ÐµÐ¼Ð¾Ð½ÑÑ (ÐµÑÐ»Ð¸ ÐµÑÑÑ Ð¸Ð· ÑÐºÑÐ¸Ð½Ð¾Ð²):
- ÐÐ»Ñ ÑÑÐ¾Ð¹ Ð¼Ð°ÑÐ¸Ð½Ñ Ð¸Ð· ÑÐ²Ð¾Ð¸Ñ ÑÐºÑÐ¸Ð½Ð¾Ð²: Ð·Ð°Ð¼ÐµÐ½Ð° Ð·Ð°Ð´Ð½ÐµÐ¹ Ð¿ÑÐ°Ð²Ð¾Ð¹ Ð´Ð²ÐµÑÐ¸ (Ð´ÐµÑÐ°Ð»Ñ 13168046), Ð±Ð¾ÐºÐ¾Ð²Ð¸Ð½Ð° 5183230, Ð¾ÐºÑÐ°Ñ Ð¿ÐµÑÐµÐ´Ð½ÐµÐ¹ Ð¿ÑÐ°Ð²Ð¾Ð¹ Ð´Ð²ÐµÑÐ¸ <50% â Ð±ÑÐ´Ð¶ÐµÑ 150-200 ÑÑÑ.

## ÐÐµÑÐ´Ð¸ÐºÑ:
- ÐÐ»ÑÑÑ: 1 Ð²Ð»Ð°Ð´ÐµÐ»ÐµÑ 16 Ð»ÐµÑ, Ð½ÐµÑ ÐÐ¢Ð, ÑÐµÑÐµÐ±ÑÐ¸ÑÑÑÐ¹ 308 1.6 120 Ð».Ñ. â Ð½Ð°Ð´ÐµÐ¶Ð½ÑÐ¹
- ÐÐ¸Ð½ÑÑÑ: Ð¿ÐµÑÐµÐ¿ÑÐ¾Ð´Ð°Ð¶Ð° ÑÐµÑÐµÐ· 3 Ð¼ÐµÑÑÑÐ°, Ð·Ð°Ð»Ð¾Ð³ Ð½Ðµ Ð¿ÑÐ¾Ð²ÐµÑÐ¸Ð»ÑÑ, Ð¿ÑÐ¾Ð±ÐµÐ³ ÑÑÐ°ÑÑÐ¹ 2021 Ð³Ð¾Ð´Ð°, ÑÐµÐ½Ð°?

Ð ÐµÐºÐ¾Ð¼ÐµÐ½Ð´ÑÐµÑÑÑ Ð±ÑÐ°ÑÑ ÑÐ¾Ð»ÑÐºÐ¾ ÐµÑÐ»Ð¸ ÐºÑÐ·Ð¾Ð² Ð¶Ð¸Ð²Ð¾Ð¹ Ð¸ ÐµÑÑÑ Ð´Ð¾ÐºÐ¸. Ð¦ÐµÐ½Ð° Ð½Ðµ Ð´Ð¾Ð»Ð¶Ð½Ð° Ð¿ÑÐµÐ²ÑÑÐ°ÑÑ 350-400 ÑÑÑ. Ð¸Ð·-Ð·Ð° Ð²Ð¾Ð·ÑÐ°ÑÑÐ° Ð¸ ÑÐ¸ÑÐºÐ¾Ð², Ð° Ð½Ðµ 500+.

ÐÐ°Ð´Ð°Ð¹ 3 Ð²Ð¾Ð¿ÑÐ¾ÑÐ° Ð¿ÑÐ¾Ð´Ð°Ð²ÑÑ:
1. ÐÐ¾ÑÐµÐ¼Ñ Ð¿ÑÐ¾Ð´Ð°ÐµÑÐµ ÑÐµÑÐµÐ· 3 Ð¼ÐµÑÑÑÐ° Ð¿Ð¾ÑÐ»Ðµ Ð¿Ð¾ÐºÑÐ¿ÐºÐ¸ 27.06.2026?
2. ÐÑÑÑ Ð»Ð¸ ÑÐµÑÐ²Ð¸ÑÐ½Ð°Ñ ÐºÐ½Ð¸Ð¶ÐºÐ° Ñ Ð¿ÑÐ¾Ð±ÐµÐ³Ð¾Ð¼ Ð¿Ð¾ÑÐ»Ðµ 20.08.2021?
3. ÐÑÐ¾Ð²ÐµÑÑÐ»Ð¸ Ð»Ð¸ Ð·Ð°Ð»Ð¾Ð³ Ð²ÑÑÑÐ½ÑÑ Ð² ÑÐµÐµÑÑÑÐµ, ÐµÑÑÑ Ð´Ð¾ÐºÑÐ¼ÐµÐ½ÑÑ?

ÐÐµÐ· Ð²Ð¾Ð´Ñ, ÐºÐ¾Ð½ÐºÑÐµÑÐ½Ð¾ ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ.
"""

    try:
        r=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=2000)
        ai_text = r.choices[0].message.content
        await m.answer(ai_text, reply_markup=main_kb())
        # also generate HTML even without current ad
        try:
            html_report = generate_beautiful_html_report(target, {"title": brand, "price": "", "url": "", "description": "", "images": []}, data, mileage_table, offers_txt, service_txt, ai_text)
            file = BufferedInputFile(html_report.encode('utf-8'), filename=f"report_{target}.html")
            await m.answer_document(file, caption="ð ÐÑÐ°ÑÐ¸Ð²ÑÐ¹ Ð¾ÑÑÐµÑ (Ð±ÐµÐ· ÑÐµÐºÑÑÐµÐ³Ð¾ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ñ â ÑÐ¾Ð»ÑÐºÐ¾ Ð¸ÑÑÐ¾ÑÐ¸Ñ Ð¿Ð¾ VIN)")
        except Exception as e2:
            print(f"HTML gen2 error {e2}")
    except Exception as e:
        await m.answer(f"AI error: {e} RAW: {json.dumps(data, ensure_ascii=False)[:3000]}")

@dp.message(F.photo)
async def handle_photo(m: types.Message):
    uid=m.from_user.id
    if user_data.get(uid,{}).get("stage")!="hood":
        return
    step=user_data[uid].get("hood_step",0)
    user_data[uid].setdefault("photos_hood",[]).append(m.photo[-1].file_id)
    if client:
        try:
            file=await bot.get_file(m.photo[-1].file_id)
            fb=await bot.download_file(file.file_path)
            b64=b64_from_bytes(fb.read())
            prompt=f"Step {HOOD_STEPS[step]}. Evaluate photo: repaint, gaps, rust. Short, score"
            resp=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}}]}], max_tokens=200)
            await m.answer(f"OK {HOOD_STEPS[step]}\n{resp.choices[0].message.content}")
        except:
            await m.answer(f"OK got {HOOD_STEPS[step]}")
    user_data[uid]["hood_step"]+=1
    ns=user_data[uid]["hood_step"]
    if ns < len(HOOD_STEPS):
        await m.answer(f"Next: {HOOD_STEPS[ns]}")
    else:
        await m.answer("All photos collected! Send video")

async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except:
        pass
    print("Start polling...")
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
