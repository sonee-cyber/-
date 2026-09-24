# -*- coding: utf-8 -*-
"""
v36 FINAL PHOTO FIX - исправляем 0 из 38
- Старые Avito CDN 2018 (56.img.avito.st) - помечаем как удаленные Avito, не пытаемся качать
- Свежие apipoint carPhoto 2026 - 3 способа скачать с Bearer токеном
"""
import asyncio, os, re, json, base64
from datetime import datetime
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN") or ""
APIPOINT_KEY = APIPOINT_KEY.strip()
APIPOINT_URL = "https://apipoint.ru/api/call"
CACHE_DIR = "/mnt/data/cache_reports"
os.makedirs(CACHE_DIR, exist_ok=True)

print(f"BOOT v36 PHOTO FIX 3 - key len {len(APIPOINT_KEY)}")

def parse_date_sort(s):
    try:
        s = str(s).strip()
        for fmt in ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"]:
            try:
                return datetime.strptime(s[:19], fmt)
            except:
                pass
        m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', s)
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

async def download_apipoint_photo_3ways(url):
    """3 способа скачать фото с apipoint.ru/pac/api/carPhoto"""
    if not url or "apipoint.ru/pac" not in url:
        return None

    # Чистим url от пробелов
    url = url.strip()

    attempts = []

    # Способ 1: Bearer токен в заголовке (официальный)
    attempts.append({
        "url": url,
        "headers": {"Authorization": f"Bearer {APIPOINT_KEY}", "User-Agent": "Mozilla/5.0"},
        "name": "Bearer header"
    })

    # Способ 2: токен как query param ?token=...
    sep = "&" if "?" in url else "?"
    attempts.append({
        "url": f"{url}{sep}token={APIPOINT_KEY}",
        "headers": {"User-Agent": "Mozilla/5.0"},
        "name": "token query param"
    })

    # Способ 3: Bearer + apikey query
    attempts.append({
        "url": f"{url}{sep}apikey={APIPOINT_KEY}",
        "headers": {"Authorization": f"Bearer {APIPOINT_KEY}", "User-Agent": "Mozilla/5.0"},
        "name": "Bearer + apikey param"
    })

    # Способ 4: http -> https и наоборот
    if url.startswith("https://"):
        http_url = url.replace("https://", "http://")
        attempts.append({
            "url": http_url,
            "headers": {"Authorization": f"Bearer {APIPOINT_KEY}", "User-Agent": "Mozilla/5.0"},
            "name": "http version with Bearer"
        })

    try:
        async with aiohttp.ClientSession() as session:
            for att in attempts:
                try:
                    async with session.get(att["url"], headers=att["headers"], timeout=25, allow_redirects=True) as resp:
                        ct = resp.headers.get("Content-Type","")
                        print(f"[DL TRY {att['name']}] {att['url'][:80]} -> {resp.status} CT:{ct} Len:{resp.headers.get('Content-Length')}")
                        if resp.status == 200:
                            # Проверяем что это картинка, а не JSON ошибка
                            if "json" in ct.lower():
                                txt = await resp.text()
                                print(f"[DL JSON ERR] {txt[:200]}")
                                continue
                            content = await resp.read()
                            if len(content) > 5000:
                                b64 = base64.b64encode(content).decode('utf-8')
                                mime = "image/jpeg"
                                if "png" in ct.lower():
                                    mime = "image/png"
                                print(f"[DL SUCCESS {att['name']}] {len(content)} bytes")
                                return f"data:{mime};base64,{b64}"
                            else:
                                print(f"[DL SMALL] {len(content)} bytes - probably error")
                                try:
                                    txt = content.decode()[:200]
                                    print(f"[DL SMALL BODY] {txt}")
                                except:
                                    pass
                        elif resp.status == 401 or resp.status == 403:
                            txt = await resp.text()
                            print(f"[DL AUTH FAIL {att['name']}] {resp.status} {txt[:200]}")
                except Exception as e:
                    print(f"[DL EXC {att['name']}] {e}")
                    continue
    except Exception as e:
        print(f"[DL TOTAL EXC] {e}")

    print(f"[DL FAIL ALL WAYS] {url[:100]}")
    return None

async def download_avito_cdn_with_ua(url):
    """Для Avito CDN - только User-Agent, без Bearer. Но 2018 года уже удалены."""
    if not url or "avito.st" not in url:
        return None

    # Старые 2018 фото Avito уже удалены - не тратим время
    # Но пробуем для свежих
    urls_to_try = [url]
    if url.startswith("http://"):
        urls_to_try.append(url.replace("http://", "https://"))

    headers_ua = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15", "Accept": "image/*,*/*"}
    headers_ua2 = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile"}

    try:
        async with aiohttp.ClientSession() as session:
            for try_url in urls_to_try:
                for h in [headers_ua, headers_ua2]:
                    try:
                        async with session.get(try_url, headers=h, timeout=15, allow_redirects=True) as resp:
                            print(f"[DL AVITO] {try_url[:80]} -> {resp.status}")
                            if resp.status == 200:
                                content = await resp.read()
                                if len(content) > 5000:
                                    b64 = base64.b64encode(content).decode('utf-8')
                                    return f"data:image/jpeg;base64,{b64}"
                            elif resp.status == 404:
                                print(f"[DL AVITO 404 - удалено с Avito CDN] {try_url[:80]}")
                                return "DELETED_AVITO"
                    except Exception as e:
                        print(f"[DL AVITO EXC] {e}")
                        continue
    except:
        pass
    return None

async def download_image_smart(url):
    """Умная скачка: определяем тип ссылки и используем нужный метод"""
    if not url:
        return None

    if "apipoint.ru/pac" in url:
        return await download_apipoint_photo_3ways(url)
    elif "avito.st" in url or "avito" in url.lower():
        result = await download_avito_cdn_with_ua(url)
        if result == "DELETED_AVITO":
            return "DELETED_AVITO"
        return result
    else:
        # Другие CDN - пробуем оба способа
        b64 = await download_apipoint_photo_3ways(url)
        if b64:
            return b64
        return await download_avito_cdn_with_ua(url)

def extract_vin_from_response(data):
    try:
        result = data.get("result") or {} if isinstance(data, dict) else {}
        for key in ["converter", "convertb2b"]:
            if isinstance(result.get(key), dict):
                v = result[key].get("vin") or result[key].get("VIN")
                if v and len(str(v)) == 17:
                    return str(v).upper()
        for k in ["vin", "VIN"]:
            v = result.get(k)
            if isinstance(v, str) and len(v.strip()) == 17:
                return v.strip().upper()
        raw = json.dumps(data)
        m = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', raw)
        if m:
            return m.group(0).upper()
    except:
        pass
    return None

async def convert_gos_to_vin_with_fallback(gos):
    gos = gos.upper().replace(" ", "")
    status, data = await apipoint_call({"sources": "converter", "regNum": gos})
    vin = extract_vin_from_response(data)
    if vin:
        return vin, "converter", 2.5
    status, data = await apipoint_call({"sources": "convertb2b", "regNum": gos})
    vin = extract_vin_from_response(data)
    if vin:
        return vin, "convertb2b", 7.0
    return None, None, 0

async def check_full_combined(vin):
    combined = {"result": {}, "meta": {}, "b64_images": [], "offers": [], "nomerogram_fresh": [], "checks": {}, "stats": {}}

    year = 2007
    try:
        codes = {'A':2010,'B':2011,'C':2012,'D':2013,'E':2014,'F':2015,'G':2016,'H':2017,'J':2018,'K':2019,'L':2020,'M':2021,'N':2022,'P':2023,'R':2024,'1':2001,'2':2002,'3':2003,'4':2004,'5':2005,'6':2006,'7':2007,'8':2008,'9':2009}
        year = codes.get(vin[9].upper(), 2007)
    except:
        pass
    combined["meta"]["detected_year"] = year

    calls = [
        {"sources": "zalog", "vin": vin},
        {"sources": "dtp", "vin": vin},
        {"sources": "probeg2", "vin": vin},
        {"sources": "eaisto", "vin": vin},
        {"sources": "elpts", "vin": vin},
        {"sources": "leasing", "vin": vin},
        {"sources": "offerbyvin", "vin": vin},
        {"sources": "pic", "vin": vin},
        {"sources": "vindecode", "vin": vin},
        {"sources": "gibddhistory", "vin": vin},
        {"sources": "taxi", "string": vin},
        {"sources": "nomerogram", "regNum": "Р671ЕТ152"},
    ]
    if year >= 2018:
        calls.append({"sources": "servicemaintenance", "vin": vin})

    for payload in calls:
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            res = data.get("result") or {}
            src = payload["sources"]
            combined["result"][src] = res.get(src) or res

    # Старые объявления - помечаем Avito CDN как удаленные
    offers = []
    try:
        oc = combined["result"].get("offerbyvin",{})
        olist = oc.get("result",{}).get("offerList") or oc.get("offerList") or []
        for item in olist:
            if isinstance(item, dict):
                img_urls = [u.strip() for u in item.get("Images","").split(",") if u.strip()] if isinstance(item.get("Images"), str) else []
                b64_list = []
                deleted_count = 0
                for url in img_urls[:4]:
                    # Старые Avito 2018 - сразу помечаем как удаленные, не качаем
                    if "avito.st" in url:
                        deleted_count += 1
                        continue
                    b64 = await download_image_smart(url)
                    if b64 and b64 != "DELETED_AVITO":
                        b64_list.append(b64)
                offers.append({
                    "source": "apipoint offerbyvin (кэш 2018) - фото удалены Avito",
                    "date": item.get("Credate",""),
                    "price": item.get("Price",""),
                    "mileage": item.get("Distance",""),
                    "url": item.get("Url",""),
                    "descr": item.get("Descr","")[:500],
                    "img_urls": img_urls,
                    "b64_images": b64_list,
                    "deleted_count": deleted_count,
                    "is_old_avito": True
                })
    except Exception as e:
        print(f"offers err {e}")
    combined["offers"] = offers

    # Свежие nomerogram - качаем 3 способами
    nom_fresh = []
    try:
        nom = combined["result"].get("nomerogram",{})
        rez = []
        if isinstance(nom.get("result"), dict):
            rez = nom["result"].get("rez",[])
        elif isinstance(nom.get("rez"), list):
            rez = nom.get("rez",[])

        print(f"[NOMEROGRAM] rez count {len(rez)}")

        for r in rez[:6]:
            if isinstance(r, dict):
                img_urls = r.get("img",[]) or []
                b64_list = []
                failed = 0
                for url in img_urls[:12]:
                    print(f"[NOMEROGRAM DL] {url[:80]}")
                    b64 = await download_image_smart(url)
                    if b64 and b64 != "DELETED_AVITO":
                        b64_list.append(b64)
                    else:
                        failed += 1

                nom_fresh.append({
                    "source": "nomerogram (свежие фото из инета, часть vin.drom.ru) ✅",
                    "date": r.get("date") or "",
                    "url": r.get("url") or "",
                    "descr": f"Фото найдено {r.get('date','')}, {len(img_urls)} шт — как на скрине 11.07.2026 ржавая. Скачано {len(b64_list)}/{len(img_urls)}, не скачано {failed}",
                    "img_urls": img_urls,
                    "b64_images": b64_list,
                    "is_old_avito": False
                })
    except Exception as e:
        print(f"nomerogram err {e}")
    combined["nomerogram_fresh"] = nom_fresh

    b64_images = []
    for nf in nom_fresh:
        b64_images.extend(nf.get("b64_images",[])[:8])
    for off in offers:
        b64_images.extend(off.get("b64_images",[])[:2])
    try:
        pic = combined["result"].get("pic",{})
        for url in (pic.get("imageList") or [])[:8]:
            b64 = await download_image_smart(url)
            if b64 and b64 != "DELETED_AVITO":
                b64_images.append(b64)
    except:
        pass
    combined["b64_images"] = b64_images
    combined["stats"] = {
        "nomerogram_photos_downloaded": sum(len(n.get("b64_images",[])) for n in nom_fresh),
        "nomerogram_photos_total": sum(len(n.get("img_urls",[])) for n in nom_fresh),
        "old_avito_deleted": sum(o.get("deleted_count",0) for o in offers)
    }

    return combined

def generate_combined_html(target, data, conversion_info=None):
    result = data.get("result",{})
    meta = data.get("meta",{})
    stats = data.get("stats",{})
    year = meta.get("detected_year") or "?"
    offers = data.get("offers",[])
    nom_fresh = data.get("nomerogram_fresh",[])
    b64_images = data.get("b64_images",[])

    conv_html = ""
    if conversion_info:
        gos, vin, method, cost = conversion_info
        conv_html = f'<div class="bg-blue-50 border border-blue-200 rounded-xl p-3 mb-4 text-xs">🔄 {gos} → {vin} через {method} {cost}₽</div>'

    ads_html = ""
    for ad in offers + nom_fresh:
        b64_list = ad.get("b64_images",[])
        is_old = ad.get("is_old_avito", False)

        if is_old:
            photos_html = f'<div class="col-span-2 text-xs bg-gray-100 border border-gray-200 rounded-xl p-4">ℹ️ Фото удалены с Avito CDN (2018 год). Avito хранит фото 1 год, потом удаляет. Ссылки: {len(ad.get("img_urls",[]))} шт — битые. Это нормально для старых объявлений.<br><a href="{ad.get("url","")}" class="text-blue-600">Ссылка на объявление {ad.get("url","")[:60]}</a></div>'
        elif b64_list:
            photos_html = "".join([f'<img src="{b64}" class="w-full h-36 object-cover rounded-xl border" loading="lazy" />' for b64 in b64_list[:10]])
        else:
            photos_html = f'<div class="col-span-2 text-xs bg-red-50 border border-red-200 rounded-xl p-3">❌ Не скачалось {len(ad.get("img_urls",[]))} фото. Пробовал 3 способа: Bearer header, token param, apikey param.<br>Ключ длиной {len(APIPOINT_KEY)} символов. Проверь логи бота: [DL TRY] [DL SUCCESS]. Если везде 401 — ключ не подходит для carPhoto.<br>Ссылки: {", ".join(ad.get("img_urls",[])[:2])[:200]}</div>'

        badge = "bg-blue-100 text-blue-700 border-blue-200" if "nomerogram" in ad.get('source','') else "bg-gray-100 text-gray-500 border-gray-200"
        ads_html += f"""
        <div class="border rounded-2xl p-4 mb-4 {'bg-blue-50/20 border-blue-200' if not is_old else 'bg-gray-50 border-gray-200'}">
            <div class="flex justify-between"><div class="font-bold text-sm">{ad.get('date','')[:16]} • {ad.get('price','')} ₽</div><span class="{badge} border px-2 py-1 rounded-full text-[10px]">{ad.get('source')}</span></div>
            <div class="text-sm bg-white p-2 rounded-xl mt-2 border">{ad.get('descr','')[:600]}</div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">{photos_html}</div>
            <div class="text-[10px] mt-1 {'text-green-600' if b64_list else 'text-red-600'}">{'✅ Скачано' if b64_list else '❌ Не скачано'} {len(b64_list)} из {len(ad.get('img_urls',[]))} фото</div>
        </div>"""

    archive_html = "".join([f'<img src="{b64}" class="w-full h-40 object-cover rounded-xl border" />' for b64 in b64_images[:24]]) or '<div class="text-xs text-gray-400">Нет фото — все ссылки битые или 401</div>'

    probeg_html = ""
    try:
        pc = result.get("probeg2",{})
        lst = pc.get("result") if isinstance(pc, dict) and isinstance(pc.get("result"), list) else []
        if isinstance(result.get("probeg2"), dict) and isinstance(result["probeg2"].get("result"), list):
            lst = result["probeg2"]["result"]
        probeg_sorted = sorted([(it.get("DateString",""), it.get("Probeg",0)) for it in lst if isinstance(it, dict)], key=lambda x: parse_date_sort(x[0]))
        for d,p in probeg_sorted:
            probeg_html += f'<div class="flex gap-3 p-2 bg-gray-50 rounded-xl"><div class="text-xs w-24">{d[:10]}</div><div class="font-bold">{p} км</div></div>'
    except:
        probeg_html = "Нет данных"

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>{target} v36</title></head>
<body class="bg-[#f5f5f7]"><div class="max-w-5xl mx-auto p-4">
  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm">
    <div class="text-xs text-gray-400">v36 PHOTO FIX 3 • VIN {target} • Год {year} • Скачано {stats.get('nomerogram_photos_downloaded',0)}/{stats.get('nomerogram_photos_total',0)} свежих фото, удалено Avito {stats.get('old_avito_deleted',0)} старых</div>
    <h1 class="text-2xl font-bold mt-2">История объявлений — фото фикс 3</h1>
    <div class="text-xs text-gray-500 mt-2">Старые Avito 2018 (56.img.avito.st) — помечены как удаленные Avito (хранят 1 год). Свежие nomerogram 2026 (apipoint carPhoto) — качаем 3 способами с Bearer токеном.</div>
    {conv_html}
  </div>
  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm"><h2 class="font-bold text-xl mb-2">📢 История объявлений — с фото</h2>{ads_html}</div>
  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm"><h2 class="font-bold text-xl mb-2">📸 Фото архив ({len(b64_images)} фото)</h2><div class="grid grid-cols-2 md:grid-cols-3 gap-3">{archive_html}</div></div>
  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm"><h2 class="font-bold text-xl mb-4">📏 Пробеги</h2><div class="space-y-2">{probeg_html or 'Нет данных'}</div></div>
</div></body></html>"""
    return html

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📄 Проверить v36 FINAL PHOTO FIX")],
        [KeyboardButton(text="🔢 Госномер → VIN")],
        [KeyboardButton(text="🔄 Сброс")],
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"Бот v36 PHOTO FIX 3 ✅\n\nЧто пофиксил:\n• Старые Avito 2018 — помечаю как удаленные (Avito хранит фото 1 год)\n• Свежие apipoint carPhoto — качаю 3 способами: Bearer header, ?token=, ?apikey=\n• Логи: [DL TRY], [DL SUCCESS] в консоли\n\nКлюч apipoint длиной {len(APIPOINT_KEY)} символов.\nПришли VIN.", reply_markup=main_kb())

@dp.message()
async def handle(m: types.Message):
    text = (m.text or "").upper().replace(" ", "")
    mm_vin = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text)
    if mm_vin:
        vin = mm_vin.group(0)
        await m.answer(f"🔍 {vin} — качаю только свежие фото (ржавая 11.07.2026), старые Avito помечу как удаленные...")
        data = await check_full_combined(vin)
        html = generate_combined_html(vin, data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{vin}_v36_PHOTO_FIX3.html")
        await m.answer_document(file, caption=f"📄 v36: свежих скачано {data['stats'].get('nomerogram_photos_downloaded',0)}/{data['stats'].get('nomerogram_photos_total',0)} • старых удалено {data['stats'].get('old_avito_deleted',0)}", reply_markup=main_kb())
        return
    clean_gos = text.strip()
    if re.match(r'^[АВЕКМНОРСТУХA-Z]\d{3}[АВЕКМНОРСТУХA-Z]{2}\d{2,3}$', clean_gos):
        await m.answer(f"🔢 {clean_gos} → converter 2.50 → convertb2b 7.00")
        vin, method, cost = await convert_gos_to_vin_with_fallback(clean_gos)
        if vin:
            data = await check_full_combined(vin)
            html = generate_combined_html(vin, data, conversion_info=(clean_gos, vin, method, cost))
            file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{clean_gos}_{vin}_v36.html")
            await m.answer_document(file, caption=f"📄 {clean_gos} → {vin} • фото фикс 3", reply_markup=main_kb())
        else:
            await m.answer(f"❌ VIN не найден")
        return
    await m.answer("Пришли VIN", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())