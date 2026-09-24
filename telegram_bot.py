# -*- coding: utf-8 -*-
"""
v39 - обход carPhoto 500 через оригинальные URL из nomerogram.rez[].url
Каждая запись nomerogram имеет поле url - это ссылка на объявление где фото нашли.
Парсим эту страницу напрямую, а не apipoint carPhoto.
"""
import asyncio, os, re, json, base64
from datetime import datetime
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN") or ""
APIPOINT_KEY = APIPOINT_KEY.strip()
APIPOINT_URL = "https://apipoint.ru/api/call"

print(f"BOOT v39 BYPASS via nomerogram.url source pages")

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

async def download_image_simple(url):
    if not url or len(url) < 15:
        return None
    # Пропускаем логотипы
    if any(x in url.lower() for x in ["logo", "icon", "og/", "apple-touch", "favicon", "banner", "gibddlogo"]):
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://auto.ru/"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=20, allow_redirects=True) as resp:
                ct = resp.headers.get("Content-Type","").lower()
                if resp.status == 200 and ("image" in ct or "octet" in ct):
                    content = await resp.read()
                    if len(content) > 8000:  # больше 8кб - точно фото машины, не иконка
                        b64 = base64.b64encode(content).decode('utf-8')
                        mime = "image/jpeg"
                        if "png" in ct:
                            mime = "image/png"
                        return f"data:{mime};base64,{b64}"
    except Exception as e:
        print(f"[DL FAIL] {url[:70]} {e}")
    return None

async def fetch_photos_from_source_page(source_url):
    """Берем оригинальное объявление (auto.ru, drom.ru, avito) и вытаскиваем фото"""
    if not source_url or len(source_url) < 10:
        return []

    print(f"[SOURCE PAGE] Fetch {source_url[:80]}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
        "Referer": "https://www.google.com/"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(source_url, headers=headers, timeout=25, allow_redirects=True) as resp:
                print(f"[SOURCE PAGE] {source_url[:60]} -> {resp.status}")
                if resp.status != 200:
                    return []
                html = await resp.text()

                found = set()

                # Паттерны для фото на разных площадках
                patterns = [
                    r'https?://[^"\']*auto\.ru[^"\']*\.(?:jpg|jpeg|png)',  # auto.ru
                    r'https?://[^"\']*avito\.ru[^"\']*\.(?:jpg|jpeg|png)',  # avito (хотя 2018 удалены)
                    r'https?://[^"\']*drom\.ru[^"\']*\.(?:jpg|jpeg|png)',
                    r'https?://[^"\']*youla\.ru[^"\']*\.(?:jpg|jpeg|png)',
                    r'https?://[^"\']*cs\d*\.drom\.ru[^"\']*\.(?:jpg|jpeg|png)',
                    r'https?://[^"\']*autoru\.[^"\']*\.(?:jpg|jpeg|png)',
                    r'https?://[^"\']*img\.auto\.ru[^"\']*\.(?:jpg|jpeg|png)',
                    # JSON с фото
                    r'"url"\s*:\s*"(https://[^"]+\.(?:jpg|jpeg|png))"',
                    r'"src"\s*:\s*"(https://[^"]+\.(?:jpg|jpeg|png))"',
                    r'https://[^\s"\']+\.jpg',
                ]

                for pat in patterns:
                    for m in re.findall(pat, html, re.IGNORECASE):
                        # m может быть кортежем
                        if isinstance(m, tuple):
                            m = m[0]
                        url = m.split('?')[0].split('#')[0]
                        # Фильтруем мусор
                        if len(url) < 20:
                            continue
                        if any(bad in url.lower() for bad in ["logo", "icon", "favicon", "banner", "gibdd", "og/drom", "apple-touch", "static", "sprite", "1x1", "pixel", "tracker"]):
                            continue
                        # Должно быть похоже на фото авто (содержит цифры, размеры)
                        if ".jpg" in url.lower() or ".jpeg" in url.lower() or ".png" in url.lower():
                            found.add(url)

                # Убираем дубли и берем первые 20
                photos = list(found)[:20]
                print(f"[SOURCE PAGE] Found {len(photos)} photos in {source_url[:50]}")
                for p in photos[:3]:
                    print(f"  - {p[:100]}")

                return photos
    except Exception as e:
        print(f"[SOURCE PAGE EXC] {source_url[:60]} {e}")
        return []

async def check_v39(vin):
    combined = {"result": {}, "meta": {}, "b64_images": [], "offers": [], "nomerogram_fresh": [], "logs": []}
    logs = combined["logs"]

    year = 2007
    try:
        codes = {'A':2010,'B':2011,'C':2012,'D':2013,'E':2014,'F':2015,'G':2016,'H':2017,'J':2018,'K':2019,'L':2020,'M':2021,'N':2022,'P':2023,'R':2024,'1':2001,'2':2002,'3':2003,'4':2004,'5':2005,'6':2006,'7':2007,'8':2008,'9':2009}
        year = codes.get(vin[9].upper(), 2007)
    except:
        pass
    combined["meta"]["detected_year"] = year

    calls = [
        {"sources": "nomerogram", "regNum": "Р671ЕТ152"},
        {"sources": "offerbyvin", "vin": vin},
        {"sources": "probeg2", "vin": vin},
        {"sources": "vindecode", "vin": vin},
    ]
    for payload in calls:
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            res = data.get("result") or {}
            src = payload["sources"]
            combined["result"][src] = res.get(src) or res

    # Разбираем nomerogram
    nom_fresh = []
    try:
        nom = combined["result"].get("nomerogram",{})
        rez = []
        if isinstance(nom.get("result"), dict):
            rez = nom["result"].get("rez",[])
        elif isinstance(nom.get("rez"), list):
            rez = nom.get("rez",[])

        print(f"[NOMEROGRAM] rez count {len(rez)}")

        for r in rez[:5]:  # берем 5 свежих
            if isinstance(r, dict):
                source_url = r.get("url") or ""
                date = r.get("date") or ""
                carphoto_urls = r.get("img",[]) or []  # эти 500 - не качаем

                logs.append(f"Обрабатываю {date} source_url={source_url[:60]} carPhoto={len(carphoto_urls)} шт (500)")

                # Пробуем вытащить фото с оригинальной страницы
                real_photos = []
                if source_url:
                    real_photos = await fetch_photos_from_source_page(source_url)

                # Качаем реальные фото как base64
                b64_list = []
                for photo_url in real_photos[:10]:
                    b64 = await download_image_simple(photo_url)
                    if b64:
                        b64_list.append(b64)
                        logs.append(f"OK {photo_url[:60]}")
                    else:
                        logs.append(f"FAIL {photo_url[:60]}")

                nom_fresh.append({
                    "date": date,
                    "source_url": source_url,
                    "carphoto_urls": carphoto_urls,  # эти 500
                    "real_photos": real_photos,
                    "b64_images": b64_list,
                    "source": f"nomerogram {date} - оригинал {source_url[:50]}",
                    "descr": f"Фото с оригинального объявления {source_url[:80]} — {len(real_photos)} найдено, {len(b64_list)} скачано. carPhoto {len(carphoto_urls)} шт сейчас 500."
                })

    except Exception as e:
        logs.append(f"nomerogram err {e}")
        import traceback
        traceback.print_exc()

    combined["nomerogram_fresh"] = nom_fresh
    combined["b64_images"] = [b64 for nf in nom_fresh for b64 in nf.get("b64_images",[])]

    # Старые
    offers = []
    try:
        oc = combined["result"].get("offerbyvin",{})
        olist = oc.get("result",{}).get("offerList") or oc.get("offerList") or []
        for item in olist[:2]:
            if isinstance(item, dict):
                offers.append({
                    "date": item.get("Credate",""),
                    "price": item.get("Price",""),
                    "url": item.get("Url",""),
                    "descr": item.get("Descr","")[:400],
                    "source": "offerbyvin 2018"
                })
    except:
        pass
    combined["offers"] = offers

    return combined

def generate_html_v39(target, data):
    nom_fresh = data.get("nomerogram_fresh",[])
    b64_images = data.get("b64_images",[])
    logs = data.get("logs",[])
    meta = data.get("meta",{})
    year = meta.get("detected_year")

    logs_html = "<br>".join([f"<div class='text-[10px] font-mono bg-gray-50 p-1 mb-1 rounded'>{l}</div>" for l in logs[-50:]])

    ads_html = ""
    for ad in nom_fresh:
        b64_list = ad.get("b64_images",[])
        real_photos = ad.get("real_photos",[])
        carphoto_urls = ad.get("carphoto_urls",[])

        if b64_list:
            photos_html = "".join([f'<img src="{b64}" class="w-full h-40 object-cover rounded-xl border" loading="lazy" />' for b64 in b64_list[:12]])
        else:
            # Показываем что нашли в оригинале
            links = "".join([f"<a href='{u}' target='_blank' class='text-[10px] text-blue-600 block break-all'>{u[:100]}</a>" for u in real_photos[:5]])
            photos_html = f"<div class='text-xs bg-yellow-50 border border-yellow-200 p-3 rounded-xl'>На оригинальной странице {ad.get('source_url')[:60]} найдено {len(real_photos)} фото, но скачать не удалось (блокировка).<br>Ссылки:<br>{links or 'Не найдено'}<br><br>carPhoto {len(carphoto_urls)} шт сейчас 500 — это apipoint лежит.</div>"

        ads_html += f"""
        <div class="border rounded-2xl p-4 mb-5 bg-white shadow-sm">
            <div class="font-bold text-sm">{ad.get('date','')[:16]} • {ad.get('source')}</div>
            <a href="{ad.get('source_url','')}" class="text-xs text-blue-600 break-all">{ad.get('source_url','')[:120]}</a>
            <div class="text-xs bg-gray-50 p-2 rounded-xl mt-2 border">{ad.get('descr','')[:400]}</div>
            <div class="grid grid-cols-2 md:grid-cols-3 gap-2 mt-3">{photos_html}</div>
            <div class="text-[10px] mt-2 text-green-600">✅ Скачано {len(b64_list)} / найдено {len(real_photos)} с оригинала | carPhoto {len(carphoto_urls)} шт — 500</div>
        </div>"""

    archive_html = "".join([f'<img src="{b64}" class="w-full h-48 object-cover rounded-xl border" />' for b64 in b64_images]) or "<div class='text-xs text-gray-400'>Нет фото — оригинальные страницы тоже блокируют или требуют JS. Попробуй открыть source_url в браузере вручную.</div>"

    probeg_html = ""
    try:
        pc = data["result"].get("probeg2",{})
        lst = pc.get("result") if isinstance(pc, dict) and isinstance(pc.get("result"), list) else []
        if isinstance(data["result"].get("probeg2"), dict) and isinstance(data["result"]["probeg2"].get("result"), list):
            lst = data["result"]["probeg2"]["result"]
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
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>v39 {target}</title></head>
<body class="bg-[#f5f5f7]"><div class="max-w-5xl mx-auto p-4">
  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm">
    <div class="text-xs text-gray-400">v39 BYPASS via source_url • VIN {target} • Год {year} • Скачано {len(b64_images)} фото с оригинальных страниц</div>
    <h1 class="text-2xl font-bold mt-2">Фото — обход carPhoto 500 через оригинальные объявления</h1>
    <div class="text-xs text-gray-500 mt-2">apipoint carPhoto отдает 500. Поэтому берем поле url из nomerogram.rez[] — это ссылка на auto.ru/drom/avito где фото нашли, и парсим фото оттуда напрямую.</div>
  </div>

  <div class="bg-green-50 border border-green-200 rounded-[24px] p-6 mb-6">
    <h2 class="font-bold text-xl">📸 Свежие фото с оригинальных страниц (обход 500)</h2>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4">{archive_html}</div>
    <div class="text-xs text-gray-500 mt-3">Всего скачано {len(b64_images)} фото с оригинальных страниц (ржавая 11.07.2026 должна быть тут)</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold text-xl mb-4">📢 История объявлений — откуда фото</h2>
    {ads_html or "<div class='text-sm'>Нет данных</div>"}
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📋 Логи</h2>
    <div class="max-h-80 overflow-y-auto border rounded-xl p-2 bg-gray-50">{logs_html}</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📏 Пробеги</h2>
    <div class="space-y-2">{probeg_html or "Нет данных"}</div>
  </div>
</div></body></html>"""
    return html

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📄 Проверить v39 BYPASS source_url")],[KeyboardButton(text="🔄 Сброс")]], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"Бот v39 BYPASS ✅\n\napipoint carPhoto 500 — обхожу через оригинальные url из nomerogram.rez[].url (auto.ru / drom / avito) и парсю фото напрямую без токена.\n\nПришли VIN", reply_markup=main_kb())

@dp.message()
async def handle(m: types.Message):
    text = (m.text or "").upper().replace(" ", "")
    mm = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text)
    if mm:
        vin = mm.group(0)
        await m.answer(f"🔍 {vin} — беру фото с оригинальных страниц объявлений (обход carPhoto 500)...")
        data = await check_v39(vin)
        html = generate_html_v39(vin, data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{vin}_v39_SOURCE_URL_BYPASS.html")
        await m.answer_document(file, caption=f"📄 v39: {len(data.get('b64_images',[]))} фото с оригинальных страниц (обход 500)", reply_markup=main_kb())
        return
    await m.answer("Пришли VIN", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())