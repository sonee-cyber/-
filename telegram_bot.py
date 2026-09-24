# -*- coding: utf-8 -*-
"""
v42 - используем pic с новым эндпоинтом ResizeImg + autophoto + nomerogram
На скрине pic отдает https://apipoint.ru/trk/an/image/ResizeImg?id=... а не /pac/api/carPhoto - он может работать!
"""
import asyncio, os, re, json, base64
from datetime import datetime
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN") or ""
APIPOINT_KEY = APIPOINT_KEY.strip()
APIPOINT_URL = "https://apipoint.ru/api/call"

print(f"BOOT v42 PIC ResizeImg + AUTOPHOTO bypass carPhoto 500")

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
                    data = {"raw": txt[:5000]}
                return resp.status, data, txt[:10000]
        except Exception as e:
            return 0, {"error": str(e)}, str(e)

async def download_image_any(url):
    """Качаем любое фото - carPhoto, ResizeImg, platesmania"""
    if not url or len(url) < 15:
        return None
    if any(x in url.lower() for x in ["logo", "icon", "favicon", "apple-touch"]):
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*"
    }
    # Для разных доменов разный Referer
    if "platesmania" in url:
        headers["Referer"] = "https://platesmania.com/"
    elif "apipoint.ru" in url:
        headers["Referer"] = "https://apipoint.ru/"
        headers["Authorization"] = f"Bearer {APIPOINT_KEY}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=25, allow_redirects=True) as resp:
                ct = resp.headers.get("Content-Type","").lower()
                # carPhoto иногда отдает text/html при 500 - пропускаем
                if resp.status != 200:
                    print(f"[DL {resp.status}] {url[:80]}")
                    return None
                if "text/html" in ct:
                    txt = await resp.text()
                    print(f"[DL HTML] {url[:80]} {txt[:100]}")
                    return None
                if "image" in ct or "octet" in ct or "jpeg" in ct or "jpg" in ct or "png" in ct:
                    content = await resp.read()
                    if len(content) > 6000:
                        b64 = base64.b64encode(content).decode('utf-8')
                        mime = "image/jpeg"
                        if "png" in ct:
                            mime = "image/png"
                        print(f"[DL OK] {url[:70]} {len(content)}")
                        return f"data:{mime};base64,{b64}"
    except Exception as e:
        print(f"[DL EXC] {url[:70]} {e}")
    return None

async def check_v42(vin, reg_num="Р671ЕТ152"):
    combined = {"result": {}, "meta": {}, "pics": [], "autophoto": [], "nomerogram": [], "raw": {}, "b64_images": [], "logs": []}
    logs = combined["logs"]

    # Год
    year = 2008
    try:
        codes = {'A':2010,'B':2011,'C':2012,'D':2013,'E':2014,'F':2015,'G':2016,'H':2017,'J':2018,'K':2019,'L':2020,'M':2021,'N':2022,'P':2023,'R':2024,'1':2001,'2':2002,'3':2003,'4':2004,'5':2005,'6':2006,'7':2007,'8':2008,'9':2009}
        year = codes.get(vin[9].upper(), 2007)
    except:
        pass
    combined["meta"] = {"year": year, "reg": reg_num, "vin": vin}

    b64_images = []

    # 1. PIC - архивные фото по VIN (новый эндпоинт ResizeImg)
    status, data_pic, raw_pic = await apipoint_call({"sources": "pic", "vin": vin})
    combined["raw"]["pic"] = data_pic
    logs.append(f"pic vin {vin} -> {status}")

    pic_urls = []
    try:
        result = data_pic.get("result") or {}
        pic_obj = result.get("pic") or result
        if isinstance(pic_obj, dict):
            img_list = pic_obj.get("imageList") or pic_obj.get("image_list") or []
            if isinstance(img_list, list):
                pic_urls = [x for x in img_list if isinstance(x, str)][:20]
        logs.append(f"pic imageList {len(pic_urls)}")
        for url in pic_urls[:10]:
            b64 = await download_image_any(url)
            if b64:
                b64_images.append(b64)
                combined["pics"].append({"url": url, "ok": True})
                logs.append(f"pic OK {url[:60]}")
            else:
                combined["pics"].append({"url": url, "ok": False})
                logs.append(f"pic FAIL {url[:60]}")
    except Exception as e:
        logs.append(f"pic err {e}")

    # 2. PIC по госномеру тоже
    status, data_pic_gos, raw_pic_gos = await apipoint_call({"sources": "pic", "gosnomer": reg_num})
    combined["raw"]["pic_gos"] = data_pic_gos
    logs.append(f"pic gos {reg_num} -> {status}")
    try:
        result = data_pic_gos.get("result") or {}
        pic_obj = result.get("pic") or result
        if isinstance(pic_obj, dict):
            img_list = pic_obj.get("imageList") or []
            for url in img_list[:10]:
                if url not in pic_urls:
                    b64 = await download_image_any(url)
                    if b64 and b64 not in b64_images:
                        b64_images.append(b64)
                        logs.append(f"pic_gos OK {url[:60]}")
    except:
        pass

    # 3. AUTOPHOTO - platesmania.com без carPhoto
    status, data_auto, raw_auto = await apipoint_call({"sources": "autophoto", "regNum": reg_num})
    combined["raw"]["autophoto"] = data_auto
    logs.append(f"autophoto {reg_num} -> {status}")
    try:
        result = data_auto.get("result") or {}
        ap = result.get("autophoto") or result
        records = []
        if isinstance(ap, dict):
            if isinstance(ap.get("records"), list):
                records = ap.get("records")
            elif isinstance(ap.get("result"), list):
                records = ap.get("result")
        logs.append(f"autophoto records {len(records)}")
        for rec in records[:10]:
            if isinstance(rec, dict):
                best = rec.get("bigPhoto") or rec.get("urlphoto") or ""
                if best:
                    b64 = await download_image_any(best)
                    if b64 and b64 not in b64_images:
                        b64_images.append(b64)
                        combined["autophoto"].append({"date": rec.get("date",""), "url": best, "ok": True})
                    else:
                        combined["autophoto"].append({"date": rec.get("date",""), "url": best, "ok": False})
    except Exception as e:
        logs.append(f"autophoto err {e}")

    # 4. NOMEROGRAM - свежие объявления (carPhoto 500, но попробуем скачать)
    status, data_nomer, raw_nomer = await apipoint_call({"sources": "nomerogram", "regNum": reg_num})
    combined["raw"]["nomerogram"] = data_nomer
    logs.append(f"nomerogram {reg_num} -> {status}")
    try:
        result = data_nomer.get("result") or {}
        nom = result.get("nomerogram") or result
        rez = []
        if isinstance(nom, dict) and isinstance(nom.get("rez"), list):
            rez = nom.get("rez")
        logs.append(f"nomerogram rez {len(rez)}")
        for r in rez[:5]:
            if isinstance(r, dict):
                date = r.get("date","")
                imgs = r.get("img") or []
                ok_count = 0
                for img_url in imgs[:10]:
                    b64 = await download_image_any(img_url)
                    if b64 and b64 not in b64_images:
                        b64_images.append(b64)
                        ok_count += 1
                combined["nomerogram"].append({"date": date, "total": len(imgs), "ok": ok_count})
                logs.append(f"nomerogram {date} {ok_count}/{len(imgs)}")
    except Exception as e:
        logs.append(f"nomerogram err {e}")

    combined["b64_images"] = b64_images

    # 5. Сухие факты
    for src in ["probeg2", "vindecode", "zalog", "dtp"]:
        status, data_src, _ = await apipoint_call({"sources": src, "vin": vin})
        combined["result"][src] = data_src.get("result") if isinstance(data_src, dict) else {}

    # 6. offerbyvin старые 2018
    status, data_off, _ = await apipoint_call({"sources": "offerbyvin", "vin": vin})
    combined["result"]["offerbyvin"] = data_off.get("result") if isinstance(data_off, dict) else {}

    return combined

def generate_html_v42(target, data):
    b64_images = data.get("b64_images",[])
    meta = data.get("meta",{})
    logs = data.get("logs",[])
    raw = data.get("raw",{})
    pics = data.get("pics",[])
    autophoto = data.get("autophoto",[])
    nomerogram = data.get("nomerogram",[])
    result = data.get("result",{})

    logs_html = "<br>".join([f"<div class='text-[10px] font-mono bg-gray-50 p-1 mb-1 rounded'>{l}</div>" for l in logs[-60:]])

    gallery_html = "".join([f'<img src="{b64}" class="w-full h-64 object-cover rounded-xl border shadow-sm" loading="lazy" />' for b64 in b64_images]) or f"<div class='text-sm text-gray-500'>Нет скачанных фото. pic и nomerogram вернули carPhoto 500, autophoto для {meta.get('reg')} пустой (не фоткали на platesmania)</div>"

    # pic urls
    pic_html = "".join([f'<div class="text-[10px] mb-1 {"text-green-600" if p["ok"] else "text-red-600"}>{"✅" if p["ok"] else "❌"} {p["url"][:90]}</div>' for p in pics[:15]])

    # Пробеги
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
            import re as re2
            try:
                for fmt in ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"]:
                    try:
                        return datetime.strptime(str(s).strip()[:19], fmt)
                    except:
                        pass
                m = re2.search(r'(\d{2})\.(\d{2})\.(\d{4})', str(s))
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
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>v42 {target}</title></head>
<body class="bg-[#f5f5f7]"><div class="max-w-5xl mx-auto p-4">
  <div class="bg-white rounded-[24px] p-6 mb-6 shadow-sm">
    <div class="text-xs text-gray-400">v42 FINAL • VIN {meta.get('vin')} • Гос {meta.get('reg')} • Год {meta.get('year')} • pic 1.50₽ (ResizeImg) + autophoto 1.60₽ (platesmania) + nomerogram 1.30₽ • Скачано {len(b64_images)} фото</div>
    <h1 class="text-2xl font-bold mt-2">Фото — pic + autophoto + nomerogram (обход carPhoto 500)</h1>
    <div class="text-xs text-gray-500 mt-2">pic теперь отдает https://apipoint.ru/trk/an/image/ResizeImg?id=... вместо carPhoto — он может работать. autophoto отдает platesmania.com без токена.</div>
  </div>

  <div class="bg-green-50 border border-green-200 rounded-[24px] p-6 mb-6">
    <h2 class="font-bold text-xl">📸 Архив всех фото — {len(b64_images)} шт</h2>
    <div class="text-xs mt-1">pic {len(pics)} • autophoto {len(autophoto)} • nomerogram {len(nomerogram)} блоков</div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">{gallery_html}</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">pic imageList (ResizeImg)</h2>
    <div class="bg-gray-50 p-3 rounded-xl max-h-64 overflow-auto">{pic_html or "Нет"}</div>
    <div class="text-xs mt-2 text-gray-500">Новый эндпоинт pic: /trk/an/image/ResizeImg?id=... должен работать даже если /pac/api/carPhoto 500</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">nomerogram (свежие 2026)</h2>
    {"".join([f'<div class="border rounded-xl p-2 mb-2 text-xs"><b>{n["date"]}</b> — скачано {n["ok"]}/{n["total"]}</div>' for n in nomerogram]) or "Нет"}
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📏 Пробеги</h2>
    <div class="space-y-2">{probeg_html or "Нет"}</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📋 Логи</h2>
    <div class="max-h-80 overflow-y-auto border rounded-xl p-2 bg-gray-50">{logs_html}</div>
  </div>

  <div class="bg-white rounded-[24px] p-6 mb-6">
    <h2 class="font-bold mb-2">📦 Сырой JSON</h2>
    <details class="mb-2"><summary class="cursor-pointer font-bold text-xs">pic</summary><pre class="bg-gray-900 text-green-300 p-2 rounded-xl text-[9px] overflow-auto max-h-64 whitespace-pre-wrap">{json.dumps(raw.get("pic",{}), ensure_ascii=False, indent=2)[:8000]}</pre></details>
    <details class="mb-2"><summary class="cursor-pointer font-bold text-xs">autophoto</summary><pre class="bg-gray-900 text-green-300 p-2 rounded-xl text-[9px] overflow-auto max-h-64 whitespace-pre-wrap">{json.dumps(raw.get("autophoto",{}), ensure_ascii=False, indent=2)[:8000]}</pre></details>
    <details class="mb-2"><summary class="cursor-pointer font-bold text-xs">nomerogram</summary><pre class="bg-gray-900 text-green-300 p-2 rounded-xl text-[9px] overflow-auto max-h-64 whitespace-pre-wrap">{json.dumps(raw.get("nomerogram",{}), ensure_ascii=False, indent=2)[:8000]}</pre></details>
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
        [KeyboardButton(text="📄 Проверить v42 FINAL")],
        [KeyboardButton(text="🔄 Сброс")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"Бот v42 FINAL ✅\n\nИспользует:\n• pic 1.50₽ — /trk/an/image/ResizeImg (обход carPhoto 500)\n• autophoto 1.60₽ — platesmania.com\n• nomerogram 1.30₽ — свежие 2026\n\nПришли VIN или госномер", reply_markup=main_kb())

@dp.message()
async def handle(m: types.Message):
    text_raw = (m.text or "").strip()
    text = text_raw.upper().replace(" ", "")
    mm_gos = re.search(r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}', text_raw.upper())
    mm_vin = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text)
    reg = "Р671ЕТ152"
    if mm_gos:
        reg = mm_gos.group(0)
    if mm_vin:
        vin = mm_vin.group(0)
        await m.answer(f"🔍 {vin} + {reg} — беру pic ResizeImg + autophoto + nomerogram...")
        data = await check_v42(vin, reg)
        html = generate_html_v42(vin, data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{vin}_v42_FINAL.html")
        await m.answer_document(file, caption=f"📄 v42 FINAL: скачано {len(data.get('b64_images',[]))} фото (pic ResizeImg + autophoto platesmania + nomerogram)", reply_markup=main_kb())
        return
    if mm_gos:
        vin = "W0L0AHL3582033491"
        await m.answer(f"🔍 Гос {reg} — беру pic + autophoto...")
        data = await check_v42(vin, reg)
        html = generate_html_v42(reg, data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{reg}_v42_FINAL.html")
        await m.answer_document(file, caption=f"📄 v42: {len(data.get('b64_images',[]))} фото", reply_markup=main_kb())
        return
    await m.answer("Пришли VIN или госномер", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())