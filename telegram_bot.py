# -*- coding: utf-8 -*-
"""
v41 - используем autophoto вместо nomerogram/carPhoto
autophoto отдает прямые ссылки на platesmania.com без токена и без 500
Цена 1.60р, возвращает urlphoto и bigPhoto - можно качать напрямую
"""
import asyncio, os, re, json, base64
from datetime import datetime
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN") or ""
APIPOINT_KEY = APIPOINT_KEY.strip()
APIPOINT_URL = "https://apipoint.ru/api/call"

print(f"BOOT v41 AUTOPHOTO - platesmania.com bypass carPhoto 500")

async def apipoint_call(payload):
    headers = {"Authorization": f"Bearer {APIPOINT_KEY}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(APIPOINT_URL, json=payload, headers=headers, timeout=45) as resp:
                txt = await resp.text()
                print(f"[APIPOINT] {payload.get('sources')} {payload.get('regNum') or payload.get('vin','')} -> {resp.status}")
                try:
                    data = json.loads(txt)
                except:
                    data = {"raw": txt[:5000]}
                return resp.status, data, txt[:8000]
        except Exception as e:
            return 0, {"error": str(e)}, str(e)

async def download_platesmania_photo(url):
    """Качаем фото с platesmania.com напрямую без токена"""
    if not url or "platesmania.com" not in url and "img" not in url:
        # autophoto может отдать и другие домены, пробуем любой
        pass
    if not url or len(url) < 10:
        return None
    if any(x in url.lower() for x in ["logo", "icon", "favicon"]):
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://platesmania.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=20, allow_redirects=True) as resp:
                ct = resp.headers.get("Content-Type","").lower()
                if resp.status == 200 and ("image" in ct or "octet" in ct or "jpeg" in ct or "jpg" in ct):
                    content = await resp.read()
                    if len(content) > 5000:
                        b64 = base64.b64encode(content).decode('utf-8')
                        mime = "image/jpeg"
                        if "png" in ct:
                            mime = "image/png"
                        print(f"[DL OK] {url[:70]} {len(content)} bytes")
                        return f"data:{mime};base64,{b64}"
                    else:
                        print(f"[DL SMALL] {url[:70]} {len(content)}")
    except Exception as e:
        print(f"[DL EXC] {url[:70]} {e}")
    return None

async def check_v41(vin, reg_num="Р671ЕТ152"):
    combined = {"result": {}, "meta": {}, "autophoto": {}, "raw_autophoto": None, "b64_images": [], "logs": [], "offers": []}
    logs = combined["logs"]

    year = 2008
    try:
        codes = {'A':2010,'B':2011,'C':2012,'D':2013,'E':2014,'F':2015,'G':2016,'H':2017,'J':2018,'K':2019,'L':2020,'M':2021,'N':2022,'P':2023,'R':2024,'1':2001,'2':2002,'3':2003,'4':2004,'5':2005,'6':2006,'7':2007,'8':2008,'9':2009}
        year = codes.get(vin[9].upper(), 2007)
    except:
        pass
    combined["meta"]["detected_year"] = year
    combined["meta"]["regNum"] = reg_num

    # 1. autophoto - главный источник фото без carPhoto 500
    status, data, raw_txt = await apipoint_call({"sources": "autophoto", "regNum": reg_num})
    combined["raw_autophoto"] = data
    combined["raw_autophoto_text"] = raw_txt
    logs.append(f"autophoto {reg_num} -> {status}")

    # Парсим autophoto
    b64_images = []
    autophoto_records = []
    try:
        result = data.get("result") or {}
        ap = result.get("autophoto") or result
        records = []
        if isinstance(ap, dict):
            if isinstance(ap.get("records"), list):
                records = ap.get("records")
            elif isinstance(ap.get("result"), list):
                records = ap.get("result")
            elif isinstance(ap, list):
                records = ap

        print(f"[AUTOPHOTO] records {len(records)}")
        logs.append(f"autophoto records {len(records)}")

        for rec in records[:15]:
            if isinstance(rec, dict):
                urlphoto = rec.get("urlphoto") or rec.get("urlPhoto") or ""
                bigphoto = rec.get("bigPhoto") or rec.get("bigphoto") or ""
                urlnumber = rec.get("urlNumber") or ""
                date = rec.get("date") or rec.get("addDate") or rec.get("created") or ""
                name = rec.get("name") or ""

                # Берем bigPhoto если есть, иначе urlphoto
                best_url = bigphoto or urlphoto

                autophoto_records.append({
                    "date": date,
                    "name": name,
                    "urlphoto": urlphoto,
                    "bigPhoto": bigphoto,
                    "urlNumber": urlnumber,
                    "best_url": best_url
                })

                if best_url:
                    b64 = await download_platesmania_photo(best_url)
                    if b64:
                        b64_images.append(b64)
                        logs.append(f"DL OK autophoto {date} {best_url[:60]}")
                    else:
                        # пробуем второй вариант
                        if urlphoto and urlphoto != best_url:
                            b64_2 = await download_platesmania_photo(urlphoto)
                            if b64_2:
                                b64_images.append(b64_2)
                                logs.append(f"DL OK autophoto fallback {urlphoto[:60]}")
                            else:
                                logs.append(f"DL FAIL {best_url[:60]}")
                        else:
                            logs.append(f"DL FAIL {best_url[:60]}")

    except Exception as e:
        logs.append(f"autophoto parse err {e}")
        import traceback; traceback.print_exc()

    combined["autophoto"]["records"] = autophoto_records
    combined["b64_images"] = b64_images

    # 2. Сухие факты
    for src in ["probeg2", "vindecode", "zalog", "dtp"]:
        status, data_src, _ = await apipoint_call({"sources": src, "vin": vin})
        combined["result"][src] = data_src.get("result") if isinstance(data_src, dict) else {}

    # 3. offerbyvin старые
    status, data_off, _ = await apipoint_call({"sources": "offerbyvin", "vin": vin})
    combined["result"]["offerbyvin"] = data_off.get("result") if isinstance(data_off, dict) else {}
    try:
        offer = combined["result"]["offerbyvin"].get("offerbyvin") if isinstance(combined["result"]["offerbyvin"], dict) else {}
        if isinstance(offer, dict) and isinstance(offer.get("result"), dict):
            offer_list = offer["result"].get("offerList") or []
        elif isinstance(combined["result"]["offerbyvin"], dict):
            inner = combined["result"]["offerbyvin"]
            if isinstance(inner.get("result"), dict):
                offer_list = inner["result"].get("offerList") or []
            elif "offerList" in inner:
                offer_list = inner["offerList"]
            else:
                offer_list = []
        else:
            offer_list = []

        offers = []
        for item in offer_list[:3]:
            if isinstance(item, dict):
                offers.append({
                    "date": item.get("Credate",""),
                    "price": item.get("Price",""),
                    "url": item.get("Url",""),
                    "descr": item.get("Descr","")[:400],
                    "source": "offerbyvin 2018"
                })
        combined["offers"] = offers
    except:
        combined["offers"] = []

    return combined

def generate_html_v41(target, data):
    b64_images = data.get("b64_images",[])
    autophoto = data.get("autophoto",{})
    records = autophoto.get("records",[])
    raw_autophoto = data.get("raw_autophoto")
    raw_text = data.get("raw_autophoto_text","")[:8000]
    logs = data.get("logs",[])
    meta = data.get("meta",{})
    year = meta.get("detected_year")
    reg_num = meta.get("regNum")
    result = data.get("result",{})
    offers = data.get("offers",[])

    raw_pretty = json.dumps(raw_autophoto, ensure_ascii=False, indent=2)[:15000] if raw_autophoto else "Нет данных"
    logs_html = "<br>".join([f"<div class='text-[10px] font-mono bg-gray-50 p-1 mb-1 rounded'>{l}</div>" for l in logs[-50:]])

    gallery_html = "".join([f'<img src="{b64}" class="w-full h-56 object-cover rounded-xl border shadow-sm" loading="lazy" />' for b64 in b64_images]) or f"<div class='text-sm text-gray-500'>Нет фото с autophoto для {reg_num}. Возможно госномер не засветился на platesmania.com. Попробуй другой госномер этого VIN.</div>"

    records_html = ""
    for rec in records[:10]:
        records_html += f"""
        <div class="border rounded-xl p-3 mb-3 bg-white">
            <div class="text-xs font-bold">{rec.get('date','')} • {rec.get('name','')}</div>
            <div class="text-[10px] mt-1"><b>bigPhoto:</b> <a href="{rec.get('bigPhoto','')}" target="_blank" class="text-blue-600 break-all">{rec.get('bigPhoto','')[:100]}</a></div>
            <div class="text-[10px]"><b>urlphoto:</b> <a href="{rec.get('urlphoto','')}" target="_blank" class="text-blue-600 break-all">{rec.get('urlphoto','')[:100]}</a></div>
        </div>"""

    probeg_html = ""
    try:
        pc = result.get("probeg2",{})
        lst = []
        if isinstance(pc, dict):
            if isinstance(pc.get("result"), list):
                lst = pc.get("result")
            elif isinstance(pc.get("probeg2"), dict):
                lst = pc.get("probeg2",{}).get("result",[])
            elif isinstance(pc.get("result"), dict) and isinstance(pc["result"].get("result"), list):
                lst = pc["result"]["result"]

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
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>v41 {target} autophoto</title></head>
<body class="bg-[#f5f5f7]"><div class="max-w-5xl mx-auto p-4">
  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm">
    <div class="text-xs text-gray-400">v41 AUTOPHOTO BYPASS • VIN {target} • Гос {reg_num} • Год {year} • autophoto 1.60₽ вместо carPhoto 500 • Скачано {len(b64_images)} фото с platesmania.com</div>
    <h1 class="text-2xl font-bold mt-2">Фото — autophoto (platesmania.com) обход carPhoto 500</h1>
    <div class="text-xs text-gray-500 mt-2">Источник autophoto отдает прямые ссылки http://img03.platesmania.com/.../m/128929.jpg без токена и без 500. Это фото с дорог, загруженные пользователями по госномеру.</div>
  </div>

  <div class="bg-green-50 border border-green-200 rounded-[24px] p-6 mb-6">
    <h2 class="font-bold text-xl">📸 Фото с autophoto (platesmania.com) — {len(b64_images)} шт</h2>
    <div class="text-xs text-gray-600 mt-1">Госномер {reg_num} • Скачано {len(b64_images)} / найдено {len(records)} • Без carPhoto 500</div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">{gallery_html}</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold text-lg mb-2">📋 autophoto records (10 шт)</h2>
    <div class="text-xs text-gray-500 mb-2">Что вернул apipoint:</div>
    {records_html or "<div class='text-sm'>Нет записей для этого госномера на platesmania.com</div>"}
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📦 Сырой autophoto JSON</h2>
    <pre class="bg-gray-900 text-green-300 p-4 rounded-xl text-[10px] overflow-auto max-h-96 whitespace-pre-wrap">{raw_pretty}</pre>
    <div class="text-xs mt-2">Raw text:</div>
    <pre class="bg-gray-100 p-2 rounded-xl text-[10px] overflow-auto max-h-64">{raw_text}</pre>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📢 Старые объявления offerbyvin (2018)</h2>
    {"".join([f'<div class="border rounded-xl p-3 mb-2"><div class="text-xs font-bold">{o.get("date")}</div><div class="text-xs">{o.get("descr")[:300]}</div></div>' for o in offers]) or "Нет"}
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📏 Пробеги</h2>
    <div class="space-y-2">{probeg_html or "Нет данных"}</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📋 Логи</h2>
    <div class="max-h-80 overflow-y-auto border rounded-xl p-2 bg-gray-50">{logs_html}</div>
  </div>

  <div class="bg-blue-50 border border-blue-200 rounded-[20px] p-4">
    <div class="text-xs"><b>Что делать дальше:</b><br>
    1. Если autophoto для Р671ЕТ152 вернул 0 — это нормально, значит машину не фоткали на platesmania.com<br>
    2. Тогда используем autophoto + nomerogram вместе: свежие фото с авто.ру все равно пока 500, ждем фикс apipoint<br>
    3. Для Отчета №2 (ржавая 11.07 → чистая 12.09) — грузим фото вручную через бота
    </div>
  </div>
</div></body></html>"""
    return html

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📄 Проверить v41 AUTOPHOTO")],
        [KeyboardButton(text="📸 Загрузить фото для ИИ анализа")],
        [KeyboardButton(text="🔄 Сброс")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"Бот v41 AUTOPHOTO ✅\n\nТеперь использую autophoto (platesmania.com) вместо carPhoto 500.\nДает прямые ссылки без токена, цена 1.60₽\n\nПришли VIN или госномер", reply_markup=main_kb())

@dp.message()
async def handle(m: types.Message):
    text_raw = (m.text or "").strip()
    text = text_raw.upper().replace(" ", "")

    # Госномер?
    mm_gos = re.search(r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}', text_raw.upper())
    # VIN?
    mm_vin = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text)

    if mm_vin:
        vin = mm_vin.group(0)
        reg = "Р671ЕТ152"  # для теста этого авто
        if mm_gos:
            reg = mm_gos.group(0)
        await m.answer(f"🔍 VIN {vin} + гос {reg} — беру autophoto с platesmania.com (обход carPhoto 500)...")
        data = await check_v41(vin, reg)
        html = generate_html_v41(vin, data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{vin}_v41_AUTOPHOTO.html")
        await m.answer_document(file, caption=f"📄 v41: autophoto {reg} — найдено {len(data.get('autophoto',{}).get('records',[]))} фото, скачано {len(data.get('b64_images',[]))} с platesmania.com", reply_markup=main_kb())
        return

    if mm_gos:
        reg = mm_gos.group(0)
        # VIN неизвестен, берем тот же для теста
        vin = "W0L0AHL3582033491"
        await m.answer(f"🔍 Гос {reg} — беру autophoto с platesmania.com...")
        data = await check_v41(vin, reg)
        html = generate_html_v41(vin, data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{reg}_v41_AUTOPHOTO.html")
        await m.answer_document(file, caption=f"📄 v41: autophoto {reg} — {len(data.get('b64_images',[]))} фото", reply_markup=main_kb())
        return

    await m.answer("Пришли VIN или госномер (например Р671ЕТ152)", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())