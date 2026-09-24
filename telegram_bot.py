# -*- coding: utf-8 -*-
"""
v38 - обход apipoint carPhoto 500: берем фото напрямую с vin.drom.ru/report/{VIN}
Там те же фото что и nomerogram, но без токена и без 500.
"""
import asyncio, os, re, json, base64
from datetime import datetime
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN") or ""
APIPOINT_KEY = APIPOINT_KEY.strip()
APIPOINT_URL = "https://apipoint.ru/api/call"

print(f"BOOT v38 DROM BYPASS carPhoto 500 -> vin.drom.ru")

def parse_date_sort(s):
    try:
        for fmt in ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"]:
            try:
                return datetime.strptime(str(s).strip()[:19], fmt)
            except:
                pass
        m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', str(s))
        if m:
            return datetime.strptime(f"{m.group(1)}.{m.group(2)}.{m.group(3)}", "%d.%m.%Y")
    except:
        pass
    return datetime.min

async def apipoint_call(payload):
    headers = {"Authorization": f"Bearer {APIPOINT_KEY}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(APIPOINT_URL, json=payload, headers=headers, timeout=45) as resp:
                txt = await resp.text()
                print(f"[APIPOINT] {payload.get('sources')} -> {resp.status}")
                try:
                    data = json.loads(txt)
                except:
                    data = {"raw": txt[:1000]}
                return resp.status, data
        except Exception as e:
            return 0, {"error": str(e)}

async def download_image_as_base64_simple(url):
    """Простая скачка без токенов - для drom.ru cdn"""
    if not url or len(url) < 10:
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://vin.drom.ru/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=20, allow_redirects=True) as resp:
                if resp.status == 200 and "image" in resp.headers.get("Content-Type","").lower():
                    content = await resp.read()
                    if len(content) > 5000:
                        b64 = base64.b64encode(content).decode('utf-8')
                        mime = "image/jpeg"
                        if "png" in resp.headers.get("Content-Type","").lower():
                            mime = "image/png"
                        return f"data:{mime};base64,{b64}"
    except Exception as e:
        print(f"[DL DROM EXC] {url[:60]} {e}")
    return None

async def fetch_drom_report_photos(vin):
    """Парсим vin.drom.ru/report/{VIN} и вытаскиваем фото без apipoint carPhoto"""
    url = f"https://vin.drom.ru/report/{vin}"
    photos = []
    html_text = ""
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.9"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=25, allow_redirects=True) as resp:
                print(f"[DROM] GET {url} -> {resp.status}")
                if resp.status == 200:
                    html_text = await resp.text()
                    # Ищем все картинки - drom хранит в cs.drom.ru, cdn.drom.ru, etc
                    # Паттерны: https://cs.drom.ru/...jpg , https://cdn.drom.ru/...jpg , data-src, src
                    patterns = [
                        r'https?://[^"\']+drom\.ru[^"\']+\.(?:jpg|jpeg|png)',
                        r'https?://[^"\']+cs\d*\.drom\.ru[^"\']+\.(?:jpg|jpeg|png)',
                        r'https?://cdn\.drom\.ru[^"\']+\.(?:jpg|jpeg|png)',
                    ]
                    found = set()
                    for pat in patterns:
                        for m in re.findall(pat, html_text, re.IGNORECASE):
                            # Чистим от параметров
                            clean = m.split('?')[0]
                            if len(clean) > 20:
                                found.add(clean)

                    # Также ищем в JSON внутри страницы: "img": ["https://..."]
                    for m in re.findall(r'"(https://[^"]+\.(?:jpg|jpeg|png))"', html_text):
                        if "drom" in m or "avito" in m or "auto" in m:
                            found.add(m)

                    photos = list(found)[:40]  # берем до 40
                    print(f"[DROM] Found {len(photos)} photos")
                    for p in photos[:5]:
                        print(f"[DROM PHOTO] {p[:100]}")
    except Exception as e:
        print(f"[DROM EXC] {e}")

    return photos, html_text[:2000]

async def check_full_v38(vin):
    combined = {"result": {}, "meta": {}, "b64_images": [], "offers": [], "nomerogram_fresh": [], "drom_photos": [], "logs": []}
    logs = combined["logs"]

    year = 2007
    try:
        codes = {'A':2010,'B':2011,'C':2012,'D':2013,'E':2014,'F':2015,'G':2016,'H':2017,'J':2018,'K':2019,'L':2020,'M':2021,'N':2022,'P':2023,'R':2024,'1':2001,'2':2002,'3':2003,'4':2004,'5':2005,'6':2006,'7':2007,'8':2008,'9':2009}
        year = codes.get(vin[9].upper(), 2007)
    except:
        pass
    combined["meta"]["detected_year"] = year

    # Сухие факты из apipoint (без фото)
    calls = [
        {"sources": "offerbyvin", "vin": vin},
        {"sources": "probeg2", "vin": vin},
        {"sources": "vindecode", "vin": vin},
        {"sources": "nomerogram", "regNum": "Р671ЕТ152"},
        {"sources": "zalog", "vin": vin},
        {"sources": "dtp", "vin": vin},
    ]
    for payload in calls:
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            res = data.get("result") or {}
            src = payload["sources"]
            combined["result"][src] = res.get(src) or res

    # 1. Пробуем drom напрямую (обход carPhoto 500)
    drom_urls, html_preview = await fetch_drom_report_photos(vin)
    combined["drom_photos"] = drom_urls
    logs.append(f"DROM found {len(drom_urls)} urls")

    # Качаем drom фото как base64
    b64_images = []
    for url in drom_urls[:20]:
        b64 = await download_image_as_base64_simple(url)
        if b64:
            b64_images.append(b64)
            logs.append(f"DROM DL OK {url[:60]}")
        else:
            logs.append(f"DROM DL FAIL {url[:60]}")

    combined["b64_images"] = b64_images

    # 2. Номерам свежие - оставляем инфу но не качаем carPhoto (500)
    nom_fresh = []
    try:
        nom = combined["result"].get("nomerogram",{})
        rez = []
        if isinstance(nom.get("result"), dict):
            rez = nom["result"].get("rez",[])
        elif isinstance(nom.get("rez"), list):
            rez = nom.get("rez",[])

        for r in rez[:6]:
            if isinstance(r, dict):
                img_urls = r.get("img",[]) or []
                nom_fresh.append({
                    "date": r.get("date") or "",
                    "url": r.get("url") or "",
                    "img_urls": img_urls,
                    "b64_images": [],  # не качаем carPhoto 500
                    "source": "nomerogram (apipoint carPhoto сейчас 500, берем с drom)"
                })
    except Exception as e:
        logs.append(f"nomerogram err {e}")
    combined["nomerogram_fresh"] = nom_fresh

    # 3. Старые объявления
    offers = []
    try:
        oc = combined["result"].get("offerbyvin",{})
        olist = oc.get("result",{}).get("offerList") or oc.get("offerList") or []
        for item in olist[:2]:
            if isinstance(item, dict):
                img_urls = [u.strip() for u in item.get("Images","").split(",") if u.strip()] if isinstance(item.get("Images"), str) else []
                offers.append({
                    "date": item.get("Credate",""),
                    "price": item.get("Price",""),
                    "url": item.get("Url",""),
                    "descr": item.get("Descr","")[:400],
                    "img_urls": img_urls,
                    "b64_images": [],
                    "source": "offerbyvin 2018 - Avito удалил фото, apipoint carPhoto 500"
                })
    except:
        pass
    combined["offers"] = offers

    return combined

def generate_html_v38(target, data):
    b64_images = data.get("b64_images",[])
    drom_photos = data.get("drom_photos",[])
    logs = data.get("logs",[])
    nom_fresh = data.get("nomerogram_fresh",[])
    offers = data.get("offers",[])
    meta = data.get("meta",{})
    year = meta.get("detected_year")

    logs_html = "<br>".join([f"<div class='text-[10px] font-mono'>{l}</div>" for l in logs[-30:]])

    drom_gallery = "".join([f'<img src="{b64}" class="w-full h-40 object-cover rounded-xl border" loading="lazy" />' for b64 in b64_images]) or f"<div class='text-xs'>DROM: найдено {len(drom_photos)} ссылок, скачано 0 — возможно drom блокирует. Ссылки ниже.</div>"

    drom_links = "".join([f"<a href='{u}' target='_blank' class='text-[10px] text-blue-600 block break-all'>{u[:100]}</a>" for u in drom_photos[:10]])

    probeg_html = ""
    try:
        pc = data["result"].get("probeg2",{})
        lst = pc.get("result") if isinstance(pc, dict) and isinstance(pc.get("result"), list) else []
        if isinstance(data["result"].get("probeg2"), dict) and isinstance(data["result"]["probeg2"].get("result"), list):
            lst = data["result"]["probeg2"]["result"]
        from datetime import datetime
        def parse_date_sort(s):
            try:
                for fmt in ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"]:
                    try:
                        return datetime.strptime(str(s).strip()[:19], fmt)
                    except:
                        pass
                m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', str(s))
                if m:
                    return datetime.strptime(f"{m.group(1)}.{m.group(2)}.{m.group(3)}", "%d.%m.%Y")
            except:
                pass
            return datetime.min
        probeg_sorted = sorted([(it.get("DateString",""), it.get("Probeg",0)) for it in lst if isinstance(it, dict)], key=lambda x: parse_date_sort(x[0]))
        for d,p in probeg_sorted:
            probeg_html += f'<div class="flex gap-3 p-2 bg-gray-50 rounded-xl"><div class="text-xs w-24">{d[:10]}</div><div class="font-bold">{p} км</div></div>'
    except:
        probeg_html = "Нет данных"

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>v38 {target}</title></head>
<body class="bg-[#f5f5f7]"><div class="max-w-5xl mx-auto p-4">
  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm">
    <div class="text-xs text-gray-400">v38 DROM BYPASS • VIN {target} • Год {year} • Обход carPhoto 500 через vin.drom.ru • Найдено {len(drom_photos)} фото, скачано {len(b64_images)}</div>
    <h1 class="text-2xl font-bold mt-2">Фото — обход apipoint 500 через drom.ru</h1>
    <div class="text-xs text-gray-500 mt-2">apipoint /pac/api/carPhoto сейчас отдает 500 (твои скрины). Поэтому фото берем напрямую с vin.drom.ru/report/{target} без токена.</div>
  </div>

  <div class="bg-green-50 border border-green-200 rounded-[20px] p-6 mb-6">
    <h2 class="font-bold text-lg">📸 Свежие фото с vin.drom.ru (обход 500)</h2>
    <div class="text-xs text-gray-600 mt-1">Найдено {len(drom_photos)} фото на drom.ru • Скачано и вшито {len(b64_images)} как base64</div>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4">{drom_gallery}</div>
    <div class="mt-4 text-xs"><b>Ссылки с drom.ru:</b><br>{drom_links or "Не найдено"}</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📋 Логи</h2>
    <div class="max-h-64 overflow-y-auto bg-gray-50 border rounded-xl p-2">{logs_html}</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📏 Пробеги (сухие факты)</h2>
    <div class="space-y-2">{probeg_html or "Нет данных"}</div>
  </div>

  <div class="bg-yellow-50 border border-yellow-200 rounded-[20px] p-4">
    <div class="text-xs">Если drom тоже не отдал фото (0) — возможно они грузят фото JS-ом. Тогда нужен парсер через Selenium или брать фото из кэша Telegram. Но apipoint carPhoto сейчас точно 500 — это их проблема.</div>
  </div>
</div></body></html>"""
    return html

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📄 Проверить v38 DROM BYPASS")],[KeyboardButton(text="🔄 Сброс")]], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"Бот v38 DROM BYPASS ✅\n\napipoint carPhoto сейчас 500 (твои скрины). Обхожу через vin.drom.ru/report/{{VIN}} напрямую без токена.\n\nПришли VIN W0L0AHL3582033491", reply_markup=main_kb())

@dp.message()
async def handle(m: types.Message):
    text = (m.text or "").upper().replace(" ", "")
    mm = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text)
    if mm:
        vin = mm.group(0)
        await m.answer(f"🔍 {vin} — беру фото с vin.drom.ru/report/{vin} (обход carPhoto 500)...")
        data = await check_full_v38(vin)
        html = generate_html_v38(vin, data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{vin}_v38_DROM_BYPASS.html")
        await m.answer_document(file, caption=f"📄 v38: drom нашел {len(data.get('drom_photos',[]))} фото, скачал {len(data.get('b64_images',[]))} • обход 500", reply_markup=main_kb())
        return
    await m.answer("Пришли VIN", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())