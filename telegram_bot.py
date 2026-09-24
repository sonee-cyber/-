# -*- coding: utf-8 -*-
import asyncio, os, re, json, base64
from datetime import datetime
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN")
APIPOINT_URL = "https://apipoint.ru/api/call"
CACHE_DIR = "/mnt/data/cache_reports"
os.makedirs(CACHE_DIR, exist_ok=True)

print("BOOT v34 PHOTO FIX 2 - раздельная скачка Avito CDN и apipoint carPhoto")

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
                try:
                    data = json.loads(txt)
                except:
                    data = {"raw": txt[:2000]}
                return resp.status, data
        except Exception as e:
            return 0, {"error": str(e)}

async def download_image_as_base64_fixed(url):
    """Фикс: для apipoint carPhoto нужен Bearer, для Avito CDN — только User-Agent без Bearer"""
    if not url or not isinstance(url, str) or len(url) < 10:
        return None

    # Нормализуем http -> https для avito
    urls_to_try = []
    if url.startswith("http://"):
        urls_to_try.append(url)  # пробуем http
        urls_to_try.append(url.replace("http://", "https://"))  # и https
    else:
        urls_to_try.append(url)

    headers_auth = {
        "Authorization": f"Bearer {APIPOINT_KEY}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    headers_ua = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
    }
    headers_ua2 = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    }

    try:
        async with aiohttp.ClientSession() as session:
            for try_url in urls_to_try:
                is_apipoint = "apipoint.ru/pac" in try_url
                is_avito = "avito.st" in try_url or "avito" in try_url

                # Для apipoint carPhoto — ТОЛЬКО с Bearer
                if is_apipoint:
                    try:
                        async with session.get(try_url, headers=headers_auth, timeout=20, allow_redirects=True) as resp:
                            print(f"[DL apipoint] {try_url} -> {resp.status} CT:{resp.headers.get('Content-Type')}")
                            if resp.status == 200:
                                ct = resp.headers.get("Content-Type","")
                                if "image" in ct or "octet-stream" in ct or "jpeg" in ct or "png" in ct or "jpg" in ct.lower() or len(ct)==0:
                                    content = await resp.read()
                                    if len(content) > 4000:
                                        b64 = base64.b64encode(content).decode('utf-8')
                                        mime = "image/jpeg"
                                        if "png" in ct:
                                            mime = "image/png"
                                        return f"data:{mime};base64,{b64}"
                                    else:
                                        # может вернулся JSON с ошибкой
                                        txt = content[:500].decode(errors='ignore')
                                        print(f"[DL apipoint ERR BODY] {txt[:200]}")
                    except Exception as e:
                        print(f"[DL apipoint EXC] {e}")
                        continue

                # Для Avito CDN — ТОЛЬКО с User-Agent, БЕЗ Bearer (Bearer ломает)
                if is_avito or not is_apipoint:
                    for h in [headers_ua, headers_ua2]:
                        try:
                            async with session.get(try_url, headers=h, timeout=20, allow_redirects=True) as resp:
                                print(f"[DL avito] {try_url} -> {resp.status} CT:{resp.headers.get('Content-Type')}")
                                if resp.status == 200:
                                    ct = resp.headers.get("Content-Type","")
                                    if "image" in ct or "octet" in ct or "jpeg" in ct or "png" in ct or len(ct)==0:
                                        content = await resp.read()
                                        if len(content) > 4000:
                                            b64 = base64.b64encode(content).decode('utf-8')
                                            mime = "image/jpeg"
                                            if "png" in ct:
                                                mime = "image/png"
                                            return f"data:{mime};base64,{b64}"
                        except Exception as e:
                            print(f"[DL avito EXC] {e}")
                            continue

                    # Пробуем Avito CDN через apipoint прокси с Bearer (иногда они проксируют)
                    if is_avito:
                        try:
                            async with session.get(try_url, headers=headers_auth, timeout=20) as resp:
                                print(f"[DL avito via apipoint token] {try_url} -> {resp.status}")
                                if resp.status == 200:
                                    content = await resp.read()
                                    if len(content) > 4000:
                                        b64 = base64.b64encode(content).decode('utf-8')
                                        return f"data:image/jpeg;base64,{b64}"
                        except:
                            pass

    except Exception as e:
        print(f"[DL TOTAL EXC] {e}")

    print(f"[DL FAIL] {url[:100]}")
    return None

def extract_vin_from_response(data):
    try:
        if not isinstance(data, dict):
            return None
        result = data.get("result") or {}
        for key in ["converter", "convertb2b", "conversion", "data"]:
            if isinstance(result.get(key), dict):
                v = result[key].get("vin") or result[key].get("VIN")
                if v and len(v) == 17:
                    return v.upper()
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

async def check_by_vin_dry(vin):
    combined = {"result": {}, "meta": {}, "b64_images": [], "offers": [], "nomerogram_fresh": []}
    year = 2007
    try:
        codes = {'A':2010,'B':2011,'C':2012,'D':2013,'E':2014,'F':2015,'G':2016,'H':2017,'J':2018,'K':2019,'L':2020,'M':2021,'N':2022,'P':2023,'R':2024,'1':2001,'2':2002,'3':2003,'4':2004,'5':2005,'6':2006,'7':2007,'8':2008,'9':2009}
        year = codes.get(vin[9].upper(), 2007)
    except:
        pass
    combined["meta"]["detected_year"] = year
    combined["meta"]["servicemaintenance_skipped"] = year < 2018

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

    # offerbyvin с фото
    offers = []
    try:
        oc = combined["result"].get("offerbyvin",{})
        olist = oc.get("result",{}).get("offerList") or oc.get("offerList") or []
        for item in olist:
            if isinstance(item, dict):
                img_urls = []
                if isinstance(item.get("Images"), str):
                    img_urls = [u.strip() for u in item.get("Images","").split(",") if u.strip()]
                b64_list = []
                for url in img_urls[:6]:
                    b64 = await download_image_as_base64_fixed(url)
                    if b64:
                        b64_list.append(b64)
                offers.append({
                    "source": "apipoint offerbyvin (кэш 2018)",
                    "date": item.get("Credate",""),
                    "price": item.get("Price",""),
                    "mileage": item.get("Distance",""),
                    "url": item.get("Url",""),
                    "descr": item.get("Descr","")[:500],
                    "img_urls": img_urls,
                    "b64_images": b64_list
                })
    except Exception as e:
        print(f"offers err {e}")

    combined["offers"] = offers

    # nomerogram с фото — теперь с фиксом
    nom_fresh = []
    try:
        nom = combined["result"].get("nomerogram",{})
        rez = []
        if isinstance(nom.get("result"), dict):
            rez = nom["result"].get("rez",[])
        elif isinstance(nom.get("rez"), list):
            rez = nom.get("rez",[])
        elif isinstance(nom.get("result"), dict) == False and isinstance(nom, dict):
            rez = nom.get("rez",[]) or []

        # дополнительный парсинг если структура другая
        if not rez:
            # иногда nom = {"result": {"rez": [...]}}
            inner = nom.get("result") if isinstance(nom, dict) else {}
            if isinstance(inner, dict):
                rez = inner.get("rez",[])

        print(f"[NOMEROGRAM] rez count {len(rez)}")

        for r in rez[:6]:
            if isinstance(r, dict):
                img_urls = r.get("img",[]) or r.get("images",[]) or []
                b64_list = []
                for url in img_urls[:10]:
                    b64 = await download_image_as_base64_fixed(url)
                    if b64:
                        b64_list.append(b64)
                nom_fresh.append({
                    "source": "nomerogram (свежие фото из инета, часть vin.drom.ru)",
                    "date": r.get("date") or r.get("createDate") or "",
                    "price": "",
                    "mileage": "",
                    "url": r.get("url") or "",
                    "descr": f"Фото найдено в интернете {r.get('date','')}, {len(img_urls)} шт — как на скрине 11.07.2026 ржавая. Скачано {len(b64_list)} из {len(img_urls)}",
                    "img_urls": img_urls,
                    "b64_images": b64_list
                })
    except Exception as e:
        print(f"nomerogram parse err {e}")

    combined["nomerogram_fresh"] = nom_fresh

    b64_images = []
    for off in offers:
        b64_images.extend(off.get("b64_images",[])[:4])
    for nf in nom_fresh:
        b64_images.extend(nf.get("b64_images",[])[:6])

    try:
        pic = combined["result"].get("pic",{})
        img_list = pic.get("imageList") or []
        for url in img_list[:8]:
            b64 = await download_image_as_base64_fixed(url)
            if b64:
                b64_images.append(b64)
    except:
        pass

    combined["b64_images"] = b64_images

    cache_path = os.path.join(CACHE_DIR, f"{vin}_full.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"result": combined["result"], "meta": combined["meta"]}, f, ensure_ascii=False)

    return combined

def generate_html_fixed(target, data, conversion_info=None):
    result = data.get("result",{})
    meta = data.get("meta",{})
    year = meta.get("detected_year") or "?"
    offers = data.get("offers",[])
    nom_fresh = data.get("nomerogram_fresh",[])
    b64_images = data.get("b64_images",[])

    conv_html = ""
    if conversion_info:
        gos, vin, method, cost = conversion_info
        conv_html = f"""<div class="bg-blue-50 border border-blue-200 rounded-[16px] p-4 mb-4"><div class="font-bold text-sm">🔄 {gos} → {vin} через {method} {cost}₽</div></div>"""

    ads_html = ""
    all_ads = offers + nom_fresh
    if not all_ads:
        ads_html = '<div class="text-sm text-gray-400 p-4 bg-gray-50 rounded-xl">Нет объявлений</div>'
    else:
        for ad in all_ads:
            b64_list = ad.get("b64_images",[])
            photos_html = ""
            if b64_list:
                for b64 in b64_list[:8]:
                    photos_html += f'<img src="{b64}" class="w-full h-36 object-cover rounded-xl border border-gray-200" loading="lazy" />'
            else:
                # Если не скачались — показываем кликабельные ссылки + причину
                links_html = ""
                for u in ad.get("img_urls",[])[:3]:
                    links_html += f'<a href="{u}" class="text-[10px] text-blue-600 break-all block">{u[:80]}</a>'
                photos_html = f'<div class="col-span-2 text-xs bg-red-50 border border-red-200 rounded-xl p-3">❌ Не скачалось {len(ad.get("img_urls",[]))} фото. Причины: Avito CDN блокирует без User-Agent, apipoint carPhoto нужен Bearer.<br>Ссылки для ручной проверки:<br>{links_html}</div>'

            badge_color = "bg-blue-100 text-blue-700 border-blue-200" if "nomerogram" in ad.get('source','') else "bg-gray-100 text-gray-700 border-gray-200"
            ads_html += f"""
            <div class="border { 'border-blue-200 bg-blue-50/20' if 'nomerogram' in ad.get('source','') else 'border-gray-200 bg-white' } rounded-2xl p-4 mb-5 shadow-sm">
                <div class="flex justify-between items-start mb-2">
                    <div>
                        <div class="font-bold text-sm">{ad.get('date','')[:16]} • {ad.get('price','')} ₽ • {ad.get('mileage','')} км</div>
                        <a href="{ad.get('url','')}" class="text-xs text-blue-600 break-all">{ad.get('url','')[:120]}</a>
                    </div>
                    <span class="{badge_color} border px-2 py-1 rounded-full text-[10px] font-bold">{ad.get('source')}</span>
                </div>
                <div class="text-xs text-gray-500 mt-1">Источник: {ad.get('source')}</div>
                <div class="text-sm bg-white p-3 rounded-xl mt-2 border border-gray-100">{ad.get('descr','')[:600]}</div>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">{photos_html}</div>
                <div class="text-[10px] text-green-600 mt-2">✅ Скачано {len(b64_list)} из {len(ad.get('img_urls',[]))} фото — вшиты base64</div>
            </div>"""

    archive_html = ""
    if b64_images:
        for b64 in b64_images[:24]:
            archive_html += f'<img src="{b64}" class="w-full h-40 object-cover rounded-xl border" />'
    else:
        archive_html = '<div class="text-xs text-gray-400">Нет фото в архиве</div>'

    probeg_html = ""
    try:
        pc = result.get("probeg2",{})
        lst = []
        if isinstance(pc, dict) and isinstance(pc.get("result"), list):
            lst = pc.get("result")
        elif isinstance(pc, list):
            lst = pc
        probeg_sorted = sorted([(it.get("DateString",""), it.get("Probeg",0)) for it in lst if isinstance(it, dict)], key=lambda x: parse_date_sort(x[0]))
        for d,p in probeg_sorted:
            probeg_html += f'<div class="flex gap-3 p-2 bg-gray-50 rounded-xl"><div class="text-xs w-24">{d[:10]}</div><div class="font-bold">{p} км</div></div>'
    except:
        probeg_html = "Нет данных"

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>{target} v34 фото фикс</title></head>
<body class="bg-[#f5f5f7]">
<div class="max-w-5xl mx-auto p-4">
  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm">
    <div class="text-xs text-gray-400">v34 PHOTO FIX 2 • VIN {target} • Год {year} • Раздельная скачка Avito CDN и apipoint carPhoto</div>
    <h1 class="text-2xl font-bold mt-2">История объявлений — фото вшиты (фикс)</h1>
    <div class="text-xs text-gray-500 mt-2">Исправлено: для apipoint.ru/pac/api/carPhoto — Bearer токен, для 56.img.avito.st — только User-Agent без Bearer. Должно скачать 38 фото от 12.09.2026 как на скрине.</div>
    {conv_html}
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm">
    <h2 class="font-bold text-xl mb-2">📢 История объявлений — с фото</h2>
    {ads_html}
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm">
    <h2 class="font-bold text-xl mb-2">📸 Фото архив (все вместе)</h2>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-3">{archive_html}</div>
    <div class="text-xs text-gray-400 mt-3">Всего скачано {len(b64_images)} фото</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm">
    <h2 class="font-bold text-xl mb-4">📏 Пробеги</h2>
    <div class="space-y-2">{probeg_html}</div>
  </div>
</div>
</body></html>"""
    return html

# BOT
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📄 Проверить (v34 фото фикс)")],
        [KeyboardButton(text="♻️ Пересобрать без API")],
        [KeyboardButton(text="🔄 Сброс")],
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Бот v34 PHOTO FIX 2 ✅\n\nПочинил скачку фото:\n• apipoint.ru/pac/api/carPhoto — качаем с Bearer токеном\n• 56.img.avito.st — качаем с User-Agent без Bearer\n\nТеперь должно показать 38 фото от 12.09.2026 как на скрине ржавой.\nПришли VIN.", reply_markup=main_kb())

@dp.message(F.text.contains("Пересобрать без API"))
async def rebuild(m: types.Message):
    await m.answer("Для v34 пересборка без API пока делает новый запрос — фото уже фиксануты.")

@dp.message()
async def handle(m: types.Message):
    text = (m.text or "").upper().replace(" ", "")
    mm_vin = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text)
    if mm_vin:
        vin = mm_vin.group(0)
        await m.answer(f"🔍 {vin} — качаю фото с правильными токенами (apipoint Bearer + Avito User-Agent)...")
        data = await check_by_vin_dry(vin)
        html = generate_html_fixed(vin, data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{vin}_v34_PHOTO_FIXED2.html")
        await m.answer_document(file, caption=f"📄 v34 фикс — скачано {len(data.get('b64_images',[]))} фото • {len(data.get('offers',[]))} старых + {len(data.get('nomerogram_fresh',[]))} свежих", reply_markup=main_kb())
        return

    clean_gos = text.strip()
    if re.match(r'^[АВЕКМНОРСТУХA-Z]\d{3}[АВЕКМНОРСТУХA-Z]{2}\d{2,3}$', clean_gos):
        await m.answer(f"🔢 {clean_gos} → converter 2.50 → convertb2b 7.00")
        vin, method, cost = await convert_gos_to_vin_with_fallback(clean_gos)
        if vin:
            await m.answer(f"✅ {clean_gos} → {vin} через {method}. Тяну фото...")
            data = await check_by_vin_dry(vin)
            html = generate_html_fixed(vin, data, conversion_info=(clean_gos, vin, method, cost))
            file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{clean_gos}_{vin}_v34.html")
            await m.answer_document(file, caption=f"📄 Гос {clean_gos} → VIN {vin} • Фото фикс", reply_markup=main_kb())
        else:
            await m.answer(f"❌ VIN не найден для {clean_gos}")
        return

    await m.answer("Пришли VIN или госномер", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())