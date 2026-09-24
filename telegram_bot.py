# -*- coding: utf-8 -*-
"""
v37 - фикс 401 carPhoto: пробуем 7 вариантов авторизации + логи в HTML
"""
import asyncio, os, re, json, base64
from datetime import datetime
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN") or ""
APIPOINT_KEY = APIPOINT_KEY.strip()
APIPOINT_URL = "https://apipoint.ru/api/call"

print(f"BOOT v37 - key len {len(APIPOINT_KEY)} first8 {APIPOINT_KEY[:8]}")

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

async def download_carphoto_7ways(url, logs):
    """7 способов скачать apipoint carPhoto + логи для HTML"""
    if not url or "apipoint.ru/pac" not in url:
        return None

    url = url.strip()
    attempts = [
        {"name": "Bearer header", "url": url, "headers": {"Authorization": f"Bearer {APIPOINT_KEY}", "User-Agent": "Mozilla/5.0"}},
        {"name": "Token header", "url": url, "headers": {"Authorization": f"Token {APIPOINT_KEY}", "User-Agent": "Mozilla/5.0"}},
        {"name": "Raw key header", "url": url, "headers": {"Authorization": APIPOINT_KEY, "User-Agent": "Mozilla/5.0"}},
        {"name": "X-API-KEY header", "url": url, "headers": {"X-API-KEY": APIPOINT_KEY, "User-Agent": "Mozilla/5.0"}},
        {"name": "?token= param", "url": f"{url}{'&' if '?' in url else '?'}token={APIPOINT_KEY}", "headers": {"User-Agent": "Mozilla/5.0"}},
        {"name": "?apikey= param", "url": f"{url}{'&' if '?' in url else '?'}apikey={APIPOINT_KEY}", "headers": {"User-Agent": "Mozilla/5.0"}},
        {"name": "?api_key= param + Bearer", "url": f"{url}{'&' if '?' in url else '?'}api_key={APIPOINT_KEY}", "headers": {"Authorization": f"Bearer {APIPOINT_KEY}", "User-Agent": "Mozilla/5.0"}},
    ]

    try:
        async with aiohttp.ClientSession() as session:
            for att in attempts:
                try:
                    async with session.get(att["url"], headers=att["headers"], timeout=20, allow_redirects=True) as resp:
                        body_preview = ""
                        try:
                            if resp.headers.get("Content-Type","").lower().find("json") != -1 or resp.status in [401,403]:
                                body_preview = (await resp.text())[:300]
                            else:
                                # для картинки не читаем текст
                                pass
                        except:
                            body_preview = ""

                        log_line = f"[{att['name']}] {resp.status} CT:{resp.headers.get('Content-Type','')} Len:{resp.headers.get('Content-Length','?')} Body:{body_preview[:100]}"
                        print(log_line)
                        logs.append(log_line)

                        if resp.status == 200:
                            ct = resp.headers.get("Content-Type","").lower()
                            if "json" in ct:
                                # ошибка в json
                                txt = await resp.text()
                                print(f"[JSON ERR] {txt[:200]}")
                                continue
                            content = await resp.read()
                            if len(content) > 5000:
                                b64 = base64.b64encode(content).decode('utf-8')
                                mime = "image/png" if "png" in ct else "image/jpeg"
                                logs.append(f"✅ SUCCESS {att['name']} {len(content)} bytes")
                                return f"data:{mime};base64,{b64}"
                            else:
                                logs.append(f"⚠️ Small body {len(content)} bytes")
                        else:
                            # 401/403 - логируем тело
                            if body_preview:
                                logs.append(f"Body: {body_preview[:150]}")
                except Exception as e:
                    err = f"[EXC {att['name']}] {e}"
                    print(err)
                    logs.append(err)
                    continue
    except Exception as e:
        logs.append(f"[TOTAL EXC] {e}")

    logs.append(f"[FAIL ALL] {url[:80]}")
    return None

async def check_full(vin):
    combined = {"result": {}, "meta": {}, "b64_images": [], "offers": [], "nomerogram_fresh": [], "logs": [], "stats": {}}
    logs = combined["logs"]

    year = 2007
    try:
        codes = {'A':2010,'B':2011,'C':2012,'D':2013,'E':2014,'F':2015,'G':2016,'H':2017,'J':2018,'K':2019,'L':2020,'M':2021,'N':2022,'P':2023,'R':2024,'1':2001,'2':2002,'3':2003,'4':2004,'5':2005,'6':2006,'7':2007,'8':2008,'9':2009}
        year = codes.get(vin[9].upper(), 2007)
    except:
        pass
    combined["meta"]["detected_year"] = year

    calls = [
        {"sources": "offerbyvin", "vin": vin},
        {"sources": "pic", "vin": vin},
        {"sources": "nomerogram", "regNum": "Р671ЕТ152"},
        {"sources": "probeg2", "vin": vin},
        {"sources": "vindecode", "vin": vin},
    ]

    for payload in calls:
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            res = data.get("result") or {}
            src = payload["sources"]
            combined["result"][src] = res.get(src) or res

    # Номерам
    nom_fresh = []
    try:
        nom = combined["result"].get("nomerogram",{})
        rez = []
        if isinstance(nom.get("result"), dict):
            rez = nom["result"].get("rez",[])
        elif isinstance(nom.get("rez"), list):
            rez = nom.get("rez",[])

        for r in rez[:4]:  # берем только 4 свежих для теста
            if isinstance(r, dict):
                img_urls = r.get("img",[]) or []
                b64_list = []
                for url in img_urls[:8]:  # только 8 фото для теста
                    b64 = await download_carphoto_7ways(url, logs)
                    if b64:
                        b64_list.append(b64)
                nom_fresh.append({
                    "date": r.get("date") or "",
                    "url": r.get("url") or "",
                    "img_urls": img_urls,
                    "b64_images": b64_list,
                    "source": "nomerogram (свежие фото из инета)"
                })
    except Exception as e:
        logs.append(f"nomerogram err {e}")

    combined["nomerogram_fresh"] = nom_fresh
    combined["b64_images"] = [b64 for nf in nom_fresh for b64 in nf.get("b64_images",[])]

    # Старые - не качаем, помечаем
    offers = []
    try:
        oc = combined["result"].get("offerbyvin",{})
        olist = oc.get("result",{}).get("offerList") or oc.get("offerList") or []
        for item in olist[:1]:
            if isinstance(item, dict):
                img_urls = [u.strip() for u in item.get("Images","").split(",") if u.strip()] if isinstance(item.get("Images"), str) else []
                offers.append({
                    "date": item.get("Credate",""),
                    "price": item.get("Price",""),
                    "url": item.get("Url",""),
                    "descr": item.get("Descr","")[:300],
                    "img_urls": img_urls,
                    "b64_images": [],
                    "source": "offerbyvin 2018 - удалены Avito"
                })
    except:
        pass
    combined["offers"] = offers
    combined["stats"] = {"downloaded": len(combined["b64_images"]), "logs_count": len(logs)}

    return combined

def generate_html(target, data):
    nom_fresh = data.get("nomerogram_fresh",[])
    offers = data.get("offers",[])
    logs = data.get("logs",[])
    b64_images = data.get("b64_images",[])

    logs_html = "<br>".join([f"<div class='text-[10px] font-mono bg-gray-100 p-1 mb-1 rounded'>{l}</div>" for l in logs[-40:]])

    ads_html = ""
    for ad in offers + nom_fresh:
        b64_list = ad.get("b64_images",[])
        if b64_list:
            photos_html = "".join([f'<img src="{b64}" class="w-full h-40 object-cover rounded-xl border" />' for b64 in b64_list[:8]])
        else:
            # Если не скачалось - показываем прямые ссылки с токеном для ручной проверки
            links = ""
            for u in ad.get("img_urls",[])[:4]:
                # делаем ссылку с токеном
                link_with_token = f"{u}?token={APIPOINT_KEY}"
                links += f"<a href='{u}' target='_blank' class='text-[10px] text-blue-600 block break-all'>{u[:90]}</a>"
                links += f"<a href='{link_with_token}' target='_blank' class='text-[10px] text-green-600 block break-all'>+token: {link_with_token[:100]}</a><br>"
            photos_html = f"<div class='text-xs bg-red-50 border border-red-200 p-3 rounded-xl'>❌ Не скачалось {len(ad.get('img_urls',[]))} фото. Логи ниже.<br>{links}</div>"

        ads_html += f"""
        <div class="border rounded-2xl p-4 mb-4 bg-white">
            <div class="font-bold text-sm">{ad.get('date','')[:16]} • {ad.get('source')}</div>
            <div class="text-xs mt-1">{ad.get('descr','')[:200]}</div>
            <div class="grid grid-cols-2 gap-2 mt-3">{photos_html}</div>
            <div class="text-[10px] mt-1">Скачано {len(b64_list)} / {len(ad.get('img_urls',[]))}</div>
        </div>"""

    archive_html = "".join([f'<img src="{b64}" class="w-full h-40 object-cover rounded-xl" />' for b64 in b64_images]) or "<div class='text-xs'>Нет фото - все 401. См логи.</div>"

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>v37 {target}</title></head>
<body class="bg-[#f5f5f7]"><div class="max-w-5xl mx-auto p-4">
  <div class="bg-white rounded-[24px] p-6 mb-6">
    <div class="text-xs text-gray-400">v37 CARPHOTO 401 FIX • VIN {target} • Ключ {len(APIPOINT_KEY)} символов • Скачано {len(b64_images)} фото</div>
    <h1 class="text-xl font-bold mt-2">Фото в отчете — фикс 401 (7 способов)</h1>
    <div class="text-xs text-gray-500 mt-2">Если видишь везде 401 — твой ключ apipoint не дает доступ к /pac/api/carPhoto. Нужно писать в поддержку apipoint или включать в тарифе фото.</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📋 Логи скачивания (последние 40 строк)</h2>
    <div class="max-h-96 overflow-y-auto border rounded-xl p-2 bg-gray-50">{logs_html or "Нет логов"}</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📢 Объявления</h2>
    {ads_html}
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📸 Архив ({len(b64_images)} фото)</h2>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-3">{archive_html}</div>
  </div>

  <div class="bg-yellow-50 border border-yellow-200 rounded-[20px] p-4">
    <div class="text-xs font-bold">Что делать если везде 401:</div>
    <div class="text-xs mt-1">
    1. Напиши в apipoint.ru поддержку: "Ключ {APIPOINT_KEY[:8]}... не дает скачать /pac/api/carPhoto, возвращает 401"<br>
    2. Альтернатива: не использовать carPhoto, а парсить vin.drom.ru/report/{target} напрямую — там фото без токена<br>
    3. Временный костыль: в отчет вшиваем прямые ссылки с ?token= — открой их в браузере, если откроется — проблема в сервере бота (нет интернета к apipoint.ru/pac)
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
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📄 Проверить v37 (логи 401)")],[KeyboardButton(text="🔄 Сброс")]], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"Бот v37 401 FIX ✅\nКлюч {len(APIPOINT_KEY)} символов\nПробую 7 способов скачать carPhoto + логи в отчете.\nПришли VIN.", reply_markup=main_kb())

@dp.message()
async def handle(m: types.Message):
    text = (m.text or "").upper().replace(" ", "")
    mm = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text)
    if mm:
        vin = mm.group(0)
        await m.answer(f"🔍 {vin} — качаю фото 7 способами + логи...")
        data = await check_full(vin)
        html = generate_html(vin, data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{vin}_v37_401_LOGS.html")
        await m.answer_document(file, caption=f"📄 v37: скачано {len(data.get('b64_images',[]))} фото • логи внутри", reply_markup=main_kb())
        return
    await m.answer("Пришли VIN", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())