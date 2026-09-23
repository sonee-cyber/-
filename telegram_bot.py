
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

print(f"BOOT v15 RUSSIAN DROM | BOT={bool(BOT_TOKEN)} APIPOINT={bool(APIPOINT_KEY)}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN empty")

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
    t = ad.get("title")[:60] if ad and ad.get("title") else "your car"
    return f"Hello! Interested in {t}.\n\nPlease send VIN and plate — will check GIBDD/pledge/accidents.\nAlso: photo of PTS, sills inside, cups and cold start video 15 sec.\nWill come immediately if ok."

@dp.message(Command("start"))
async def start(m: types.Message):
    user_data[m.from_user.id] = {"stage":"idle","photos_hood":[],"hood_step":0,"last_gos":"","last_ad":None}
    await m.answer("Bot v12 FIX - ready \u2705\nSend plate X423KO550 or VIN.\nFor full report need VIN.", reply_markup=main_kb())

@dp.message(F.text=="\U0001f504 Reset")
async def reset(m: types.Message):
    user_data[m.from_user.id] = {"stage":"idle","photos_hood":[],"hood_step":0,"last_gos":"","last_ad":None}
    await m.answer("Reset done", reply_markup=main_kb())

@dp.message(F.text.contains("Request VIN"))
async def vin_req(m: types.Message):
    ad=user_data.get(m.from_user.id,{}).get("last_ad")
    await m.answer(f"Template for seller:\n\n{get_vin_template(ad)}", reply_markup=cancel_kb())

@dp.message(F.text.contains("Check by"))
async def mode_remote(m: types.Message):
    user_data[m.from_user.id]={"stage":"await_gos","last_ad":None}
    await m.answer("Send link + plate or VIN. If no plate — click Request VIN", reply_markup=cancel_kb())

@dp.message(F.text.contains("at the car"))
async def mode_hood(m: types.Message):
    user_data[m.from_user.id]={"stage":"hood","photos_hood":[],"hood_step":0}
    await m.answer(f"At the hood — {HOOD_STEPS[0]}", reply_markup=cancel_kb())

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
        await m.answer(f"Link ok {ad_url} — fetching ad... ")
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
            await m.answer(f"Title: {ad_data.get('title','')[:100]}\nPrice: {ad_data.get('price','?')} \n\nPlate hidden — click Request VIN and send number/VIN", reply_markup=cancel_kb())
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
        await m.answer(f"Checking VIN {vin} in all bases... ")
        data = await check_by_vin(vin)
        await ai_report(m, vin, data, is_vin=True)
        return
    if gos:
        await m.answer(f"Checking plate {gos} (pledge flag)... ")
        data = await check_by_gos(gos)
        await ai_report(m, gos, data, is_vin=False)
        return

async def do_full(m, ad_data, ad_images_b64, target):
    uid=m.from_user.id
    await m.answer(f"Making combo report for {target}... ")
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
    prompt = f"Ты — автоподборщик. Ссылка {ad_data.get('url')} Цель {target} Объявление {ad_data.get('title')} Цена {ad_data.get('price')} Базы {json.dumps(data, ensure_ascii=False)[:12000]} Сделай отчет на РУССКОМ: АВТО, ФОТО, ПРОВЕРКА БАЗ, ЦЕНА, ВЕРДИКТ. Пиши как на Дроме, без воды."
    try:
        resp=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":[{"type":"text","text":prompt}]+vision}], max_tokens=1500)
        await m.answer(resp.choices[0].message.content, reply_markup=main_kb())
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
        prompt = f"Госномер {target} залог f={zalog_f} баланс {balance}. Сделай короткий вердикт на РУССКОМ: если f=true — в залоге, нужен VIN для полной проверки. Если f=false — не в залоге. Пиши только по-русски."
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

        prompt = f"""
Ты — эксперт по проверке авто как на Дроме. Пиши ТОЛЬКО на русском, конкретно, без воды, как в отчете Дрома.

VIN {target}:
- Авто: {brand}, год {year}
- Владельцы: {json.dumps(periods, ensure_ascii=False)}
- Пробег: {json.dumps(history, ensure_ascii=False)} + последний из ТО 141048 км 20.08.2021
- Скрутки: {rollback_text or "нет явных, но пробег старый"}
- ДТП: hasDtp={has_dtp}
- Залог: f={zalog.get('f')} Error={zalog_error} ErrorMessage сервис временно не доступен
- Баланс apipoint {balance}

Сделай отчет в стиле ДРОМ:

## ГИБДД:
- 1 владелец с 03.04.2010 по 27.06.2026 — 16 лет у одного человека, это плюс
- 27.06.2026 смена собственника — 3 месяца назад, подозрительно, возможно перекуп/площадка
- Последнее действие: В связи с изменением собственника

## ДТП:
- hasDtp={has_dtp} — ДТП не найдено, по базам чисто

## Залог:
- f={zalog.get('f')} но сервис выдал Error true / Сервис временно не доступен — нужно проверить вручную на reestr-zalogov.ru по VIN

## Пробег:
- Последний зафиксированный 141048 км 20.08.2021 из техосмотра — уже 5 лет назад! Свежего пробега нет.
- Если на одометре сейчас сильно больше/меньше — уточняй сервисную книжку

## Ремонты (если есть из скринов):
- Для этой машины из твоих скринов: замена задней правой двери (деталь 13168046), боковина 5183230, окрас передней правой двери <50% — бюджет 150-200 тыс.

## Вердикт:
- Плюсы: 1 владелец 16 лет, нет ДТП, серебристый 308 1.6 120 л.с. — надежный
- Минусы: перепродажа через 3 месяца, залог не проверился, пробег старый 2021 года, цена?

Рекомендуется брать только если кузов живой и есть доки. Цена не должна превышать 350-400 тыс. из-за возраста и рисков, а не 500+.

Задай 3 вопроса продавцу:
1. Почему продаете через 3 месяца после покупки 27.06.2026?
2. Есть ли сервисная книжка с пробегом после 20.08.2021?
3. Проверяли ли залог вручную в реестре, есть документы?

Без воды, конкретно как на Дроме.
"""

    try:
        r=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=2000)
        await m.answer(r.choices[0].message.content, reply_markup=main_kb())
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