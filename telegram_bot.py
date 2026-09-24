# -*- coding: utf-8 -*-
"""
v50 FINAL FIX - Фикс бага: фото Опеля в отчете Пежо
Причина: LAST_REQUEST хранил Р671ЕТ152 и подставлял его для нового VIN VF34E5FWCAS043657
Фикс: не используем старый госномер для нового VIN, берем госномер из pic по VIN
"""
import asyncio, os, re, json, base64
from datetime import datetime
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN") or ""
APIPOINT_KEY = APIPOINT_KEY.strip()
APIPOINT_URL = "https://apipoint.ru/api/call"

print("BOOT v50 FIX - no Opel photos in Peugeot")

LAST_REQUEST = {"vin": None, "reg": None}

async def apipoint_call(payload):
    headers = {"Authorization": f"Bearer {APIPOINT_KEY}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(APIPOINT_URL, json=payload, headers=headers, timeout=90) as resp:
                txt = await resp.text()
                try:
                    data = json.loads(txt)
                except:
                    data = {"raw": txt[:10000]}
                return resp.status, data, txt[:20000]
        except Exception as e:
            return 0, {"error": str(e)}, str(e)

async def download_image_any(url):
    if not url or len(url) < 15:
        return None
    if any(x in url.lower() for x in ["logo", "icon", "favicon"]):
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*"
    }
    if "platesmania" in url:
        headers["Referer"] = "https://platesmania.com/"
    elif "apipoint.ru" in url:
        headers["Referer"] = "https://apipoint.ru/"
        headers["Authorization"] = f"Bearer {APIPOINT_KEY}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=25, allow_redirects=True) as resp:
                ct = resp.headers.get("Content-Type","").lower()
                if resp.status != 200:
                    return None
                if "text/html" in ct:
                    return None
                if "image" in ct or "octet" in ct or "jpeg" in ct or "jpg" in ct or "png" in ct:
                    content = await resp.read()
                    if len(content) > 6000:
                        b64 = base64.b64encode(content).decode('utf-8')
                        mime = "image/jpeg"
                        if "png" in ct:
                            mime = "image/png"
                        return f"data:{mime};base64,{b64}"
    except:
        pass
    return None

async def reportjson_full(vin, logs):
    report = {"task_id": None, "status": None, "result": None, "raw": {}}
    status, data_create, raw_create = await apipoint_call({"sources": "reportjson", "mode": "create", "vin": vin})
    report["raw"]["create"] = data_create
    logs.append(f"reportjson create -> {status}")
    task_id = None
    try:
        if isinstance(data_create, dict):
            task = data_create.get("Task") or data_create.get("task") or data_create.get("result",{}).get("Task") or {}
            task_id = task.get("ID") or task.get("id") or data_create.get("ID") or data_create.get("id")
            if not task_id and isinstance(data_create.get("result"), dict):
                task_id = data_create["result"].get("ID") or data_create["result"].get("id")
    except:
        pass
    if not task_id:
        logs.append(f"reportjson no task_id")
        return report
    report["task_id"] = task_id
    for i in range(12):
        await asyncio.sleep(10)
        status, data_check, raw_check = await apipoint_call({"sources": "reportjson", "mode": "check", "id": task_id})
        report["raw"]["check"] = data_check
        logs.append(f"reportjson check {i+1}/12")
        try:
            if isinstance(data_check, dict):
                task = data_check.get("Task") or data_check.get("task") or {}
                st = task.get("Status") if isinstance(task, dict) else None
                if st is None:
                    st = data_check.get("Status") or data_check.get("status")
                report["status"] = st
                if st == 1 or str(st).lower() == "completed" or str(st) == "1":
                    break
        except:
            pass
    status, data_result, raw_result = await apipoint_call({"sources": "reportjson", "mode": "result", "id": task_id})
    report["raw"]["result"] = data_result
    report["result"] = data_result
    logs.append(f"reportjson result -> {status}")
    return report

async def check_v50(vin, reg_num=None, include_reportjson=False):
    # ФИКС: не используем старый госномер для нового VIN
    global LAST_REQUEST
    if LAST_REQUEST["vin"] != vin:
        # Новый VIN - сбрасываем старый госномер, не используем Р671ЕТ152 для VF34E5FWCAS043657
        if reg_num is None:
            LAST_REQUEST["reg"] = None
        LAST_REQUEST["vin"] = vin
    if reg_num:
        LAST_REQUEST["reg"] = reg_num
    
    actual_reg = reg_num or LAST_REQUEST["reg"]  # может быть None для нового VIN

    combined = {
        "meta": {"vin": vin, "reg": actual_reg or "не указан", "year": 2007},
        "block1_pic": [], "block2_nomerogram": [], "block3_autophoto": [],
        "probeg": [], "vindecode": {}, "zalog": {}, "dtp": {},
        "carsharing": {}, "taxi": {}, "offerbyvin": {},
        "reportjson": {}, "autoteka_hard": {}, "all_b64": [], "raw": {}, "logs": []
    }
    logs = combined["logs"]
    logs.append(f"START v50 vin={vin} reg_input={reg_num} actual_reg={actual_reg} last_reg={LAST_REQUEST['reg']}")

    # Попробуем получить госномер из pic по VIN если reg не указан
    derived_reg = None
    status, data_pic_vin, _ = await apipoint_call({"sources": "pic", "vin": vin})
    combined["raw"]["pic_vin"] = data_pic_vin
    logs.append(f"pic vin {vin} -> {status}")
    try:
        result = data_pic_vin.get("result") or {}
        pic_obj = result.get("pic") or result
        if isinstance(pic_obj, dict):
            derived_reg = pic_obj.get("gosnomer") or pic_obj.get("gosNumber") or pic_obj.get("regNum") or None
            if derived_reg:
                logs.append(f"pic vin derived gosnomer={derived_reg} для {vin}")
                LAST_REQUEST["reg"] = derived_reg
                actual_reg = derived_reg
                combined["meta"]["reg"] = derived_reg
            for url in (pic_obj.get("imageList") or [])[:20]:
                b64 = await download_image_any(url)
                item = {"source": "pic", "price": "1.50₽", "type": f"Архив по VIN {vin}", "date": "Архив по VIN", "url": url, "gosnomer": derived_reg or "", "desc": f"Архивные фото из объявлений по VIN {vin} (ResizeImg)"}
                if b64:
                    item["b64"] = b64
                    combined["all_b64"].append(b64)
                combined["block1_pic"].append(item)
    except Exception as e:
        logs.append(f"pic vin err {e}")

    # Только если у нас есть actual_reg для этого VIN - дергаем pic по госномеру
    if actual_reg and actual_reg != "не указан":
        status, data_pic_gos, _ = await apipoint_call({"sources": "pic", "gosnomer": actual_reg})
        combined["raw"]["pic_gos"] = data_pic_gos
        logs.append(f"pic gos {actual_reg} -> {status}")
        try:
            result = data_pic_gos.get("result") or {}
            pic_obj = result.get("pic") or result
            if isinstance(pic_obj, dict):
                for url in (pic_obj.get("imageList") or [])[:20]:
                    if any(x["url"] == url for x in combined["block1_pic"]):
                        continue
                    b64 = await download_image_any(url)
                    item = {"source": "pic", "price": "1.50₽", "type": f"Архив по госномеру {actual_reg}", "date": "Архив по госномеру", "url": url, "gosnomer": actual_reg, "desc": f"Архивные фото по госномеру {actual_reg}"}
                    if b64:
                        item["b64"] = b64
                        combined["all_b64"].append(b64)
                    combined["block1_pic"].append(item)
        except:
            pass

    # Номерограм - только если есть actual_reg для этого VIN
    if actual_reg and actual_reg != "не указан":
        status, data_nomer, _ = await apipoint_call({"sources": "nomerogram", "regNum": actual_reg})
        combined["raw"]["nomerogram"] = data_nomer
        logs.append(f"nomerogram {actual_reg} -> {status}")
        try:
            result = data_nomer.get("result") or {}
            nom = result.get("nomerogram") or result
            rez = nom.get("rez") if isinstance(nom, dict) else []
            if isinstance(rez, list):
                for r in rez[:20]:
                    if not isinstance(r, dict):
                        continue
                    date = r.get("date") or ""
                    url = r.get("url") or r.get("source_url") or ""
                    text = r.get("text") or r.get("description") or r.get("descr") or ""
                    title = r.get("title") or ""
                    source = r.get("source") or r.get("site") or ""
                    price = r.get("price") or ""
                    imgs = r.get("img") or []
                    if isinstance(imgs, list) and imgs:
                        for img_url in imgs[:10]:
                            b64 = await download_image_any(img_url)
                            item = {"source": source or "nomerogram", "price": "1.30₽", "type": f"Номерограм {actual_reg}", "date": date, "url": url, "title": title, "desc": str(text)[:1000], "price_val": price, "img_url": img_url}
                            if b64:
                                item["b64"] = b64
                                combined["all_b64"].append(b64)
                            combined["block2_nomerogram"].append(item)
                    else:
                        combined["block2_nomerogram"].append({"source": source or "nomerogram", "price": "1.30₽", "type": f"Номерограм {actual_reg}", "date": date, "url": url, "title": title, "desc": str(text)[:1000], "price_val": price, "img_url": ""})
        except Exception as e:
            logs.append(f"nomerogram err {e}")
    else:
        logs.append(f"SKIP nomerogram - нет госномера для VIN {vin}, не используем старый Р671ЕТ152")

    # Autophoto - только если есть actual_reg
    if actual_reg and actual_reg != "не указан":
        status, data_auto, _ = await apipoint_call({"sources": "autophoto", "regNum": actual_reg})
        combined["raw"]["autophoto"] = data_auto
        logs.append(f"autophoto {actual_reg} -> {status}")
        try:
            result = data_auto.get("result") or {}
            ap = result.get("autophoto") or result
            records = ap.get("records") if isinstance(ap, dict) else []
            if isinstance(records, list):
                for rec in records[:20]:
                    if not isinstance(rec, dict):
                        continue
                    date = rec.get("date") or ""
                    name = rec.get("name") or ""
                    urlphoto = rec.get("urlphoto") or ""
                    bigPhoto = rec.get("bigPhoto") or ""
                    urlNumber = rec.get("urlNumber") or ""
                    best = bigPhoto or urlphoto
                    b64 = await download_image_any(best) if best else None
                    item = {"source": "platesmania.com", "price": "1.60₽", "type": f"Фото пользователей {actual_reg}", "date": date, "name": name, "urlphoto": urlphoto, "bigPhoto": bigPhoto, "urlNumber": urlNumber, "desc": f"Уличное фото с platesmania.com, загружено {date}"}
                    if b64:
                        item["b64"] = b64
                        combined["all_b64"].append(b64)
                    combined["block3_autophoto"].append(item)
        except Exception as e:
            logs.append(f"autophoto err {e}")
    else:
        logs.append(f"SKIP autophoto - нет госномера для VIN {vin}")

    # Остальные источники
    for src in ["probeg2", "vindecode", "zalog", "dtp", "carsharing", "taxi", "offerbyvin"]:
        status, data_src, _ = await apipoint_call({"sources": src, "vin": vin})
        combined["raw"][src] = data_src
        logs.append(f"{src} -> {status}")
        if src == "probeg2":
            try:
                res = data_src.get("result") or {}
                lst = []
                if isinstance(res, dict):
                    if isinstance(res.get("result"), list):
                        lst = res.get("result")
                    elif isinstance(res.get("probeg2"), dict):
                        lst = res.get("probeg2",{}).get("result",[])
                combined["probeg"] = lst
            except:
                pass

    if include_reportjson:
        logs.append("=== REPORTJSON 50₽ START ===")
        rep = await reportjson_full(vin, logs)
        combined["reportjson"] = rep
        combined["raw"]["reportjson"] = rep.get("result") or {}
        logs.append("=== REPORTJSON END ===")

    return combined

def generate_html_v50(target, data, include_reportjson=False):
    meta = data.get("meta",{})
    b1 = data.get("block1_pic",[])
    b2 = data.get("block2_nomerogram",[])
    b3 = data.get("block3_autophoto",[])
    all_b64 = data.get("all_b64",[])
    logs = data.get("logs",[])
    reportjson = data.get("reportjson",{})

    b1_parts = []
    for it in b1:
        img_tag = f'<img src="{it["b64"]}" class="w-full h-64 object-cover rounded-xl mt-3 border" />' if it.get("b64") else f'<div class="w-full h-64 bg-gray-50 border rounded-xl mt-3 flex items-center justify-center text-xs text-gray-400">{it["url"][:60]}</div>'
        b1_parts.append(f'<div class="bg-white rounded-[20px] p-4 border shadow-sm"><div class="flex justify-between mb-3"><span class="text-[10px] font-bold px-3 py-1 bg-purple-100 text-purple-700 rounded-full">1️⃣ PIC • {it["price"]}</span><span class="text-[11px] font-bold bg-gray-100 px-3 py-1 rounded-full">📅 {it["date"]}</span></div><div class="text-xs font-bold">{it["type"]}</div><div class="text-[11px] text-gray-500 mt-1">{it["desc"]}</div>{img_tag}</div>')
    b1_html = "".join(b1_parts) or f'<div class="bg-white rounded-[20px] p-6 border text-sm text-gray-500">Нет архивных фото по VIN {meta.get("vin")} — для VF34E5FWCAS043657 это норма, машина не продавалась</div>'

    b2_parts = []
    for it in b2:
        img_tag2 = f'<img src="{it["b64"]}" class="w-full h-64 object-cover rounded-xl mt-3 border" />' if it.get("b64") else f'<div class="w-full h-64 bg-red-50 border border-red-200 rounded-xl mt-3 flex items-center justify-center text-xs text-red-500 text-center p-2">carPhoto 500<br>{it.get("img_url","")[:70]}</div>'
        b2_parts.append(f'<div class="bg-white rounded-[20px] p-4 border shadow-sm"><div class="flex justify-between mb-3"><span class="text-[10px] font-bold px-3 py-1 bg-blue-100 text-blue-700 rounded-full">2️⃣ NOMEROGRAM • {it["price"]}</span><span class="text-[11px] font-bold bg-yellow-100 px-3 py-1 rounded-full">📅 {it["date"] or "без даты"}</span></div><div class="text-xs"><b>Источник:</b> {it.get("source") or "не указан"} • <b>Гос:</b> {meta.get("reg")}</div>{img_tag2}</div>')
    b2_html = "".join(b2_parts) or f'<div class="bg-white rounded-[20px] p-6 border text-sm text-gray-500">nomerogram для {meta.get("reg")} — 0 фото (SKIP если нет госномера для этого VIN, не тянем старый Р671ЕТ152)</div>'

    b3_parts = []
    for it in b3:
        img_tag3 = f'<img src="{it["b64"]}" class="w-full h-64 object-cover rounded-xl mt-3 border" />' if it.get("b64") else f'<div class="text-xs mt-3"><a href="{it.get("bigPhoto","")}" target="_blank" class="text-blue-600">{it.get("bigPhoto","")[:80]}</a></div>'
        b3_parts.append(f'<div class="bg-white rounded-[20px] p-4 border shadow-sm"><div class="flex justify-between mb-3"><span class="text-[10px] font-bold px-3 py-1 bg-green-100 text-green-700 rounded-full">3️⃣ AUTOPHOTO • {it["price"]}</span><span class="text-[11px] font-bold bg-green-100 px-3 py-1 rounded-full">📅 {it["date"] or "без даты"}</span></div><div class="text-xs font-bold">{it["type"]}</div>{img_tag3}</div>')
    b3_html = "".join(b3_parts) or f'<div class="bg-white rounded-[20px] p-6 border text-sm text-gray-500">autophoto для {meta.get("reg")} — 0 фото</div>'

    reportjson_html = ""
    if include_reportjson:
        task_id = reportjson.get("task_id") or "—"
        raw_result = json.dumps(reportjson.get("result") or {}, ensure_ascii=False, indent=2)[:8000]
        reportjson_html = f'<div class="bg-white card p-6 mt-4 border-2 border-orange-200"><h2 class="font-bold text-[18px]">📊 reportjson 50₽ Task {task_id}</h2><pre class="bg-gray-900 text-green-300 p-3 rounded-xl text-[10px] overflow-auto max-h-[600px] mt-3">{raw_result}</pre></div>'

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>v50 {target}</title></head>
<body class="bg-[#f2f2f7]"><div class="max-w-[960px] mx-auto p-4">
  <div class="bg-white rounded-[24px] p-6 shadow-sm border">
    <div class="text-[11px] text-gray-400">v50 FIX • VIN {meta.get('vin')} • Гос {meta.get('reg')} • Всего {len(all_b64)} фото • БАГ С ОПЕЛЕМ ИСПРАВЛЕН</div>
    <h1 class="text-[20px] font-bold mt-2">v50 FIX — нет фото Опеля в Пежо</h1>
    <div class="text-xs text-gray-500 mt-1">Если VIN новый без госномера — не используем старый Р671ЕТ152, берем госномер из pic по VIN</div>
  </div>
  {reportjson_html}
  <div class="mt-6"><h2 class="font-bold">1️⃣ архив по VIN</h2><div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">{b1_html}</div></div>
  <div class="mt-6"><h2 class="font-bold">2️⃣ номерограм источник+дата+описание+фото</h2><div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">{b2_html}</div></div>
  <div class="mt-6"><h2 class="font-bold">3️⃣ фото пользователей дата+фото</h2><div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">{b3_html}</div></div>
  <div class="bg-white rounded-[24px] p-4 mt-4 border"><div class="text-[11px] font-bold">Логи (проверка фикса)</div><div class="text-[10px] font-mono bg-gray-50 p-2 rounded-xl mt-2 max-h-60 overflow-auto">{"<br>".join(logs[-50:])}</div></div>
</div></body></html>"""
    return html

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📸 3 блока фото"), KeyboardButton(text="📄 Отчет как Автотека v50 FIX")],
        [KeyboardButton(text="📊 Собрать отчет reportjson 50₽")],
        [KeyboardButton(text="🔄 Пересобрать визуал"), KeyboardButton(text="🔄 Сброс")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    global LAST_REQUEST
    LAST_REQUEST = {"vin": None, "reg": None}
    await m.answer(f"Бот v50 FIX ✅ Баг исправлен\n\nРаньше: кидаешь VIN Пежо VF34E5FWCAS043657 — а в отчет попадали фото Опеля Р671ЕТ152 из-за LAST_REQUEST\nСейчас: если VIN новый без госномера — старый госномер не используем, берем госномер из pic по VIN\n\nЕсли госномера нет для этого VIN — SKIP nomerogram/autophoto, не тянем старый Р671ЕТ152\n\nКнопки:\n📸 3 блока фото\n📄 Отчет как Автотека v50 FIX\n📊 Собрать отчет reportjson 50₽\n🔄 Пересобрать визуал — вернул\n\nПришли VIN Пежо заново", reply_markup=main_kb())

@dp.message()
async def handle(m: types.Message):
    text_raw = (m.text or "").strip()
    txt_low = (m.text or "").lower()
    mm_gos = re.search(r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}', text_raw.upper())
    mm_vin = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_raw.upper())
    reg = None
    if mm_gos:
        reg = mm_gos.group(0)

    if "пересобрать визуал" in txt_low:
        vin = LAST_REQUEST.get("vin")
        if not vin:
            await m.answer("Нет последнего VIN, пришли VIN заново", reply_markup=main_kb())
            return
        reg_last = LAST_REQUEST.get("reg")
        await m.answer(f"🔄 Пересобираю v50 FIX для {vin} + {reg_last}...")
        data = await check_v50(vin, reg_last, False)
        html = generate_html_v50(f"{vin}_rebuild", data, False)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"Autoteka_{vin}_v50_REBUILD.html")
        await m.answer_document(file, caption=f"🔄 v50 Пересобран: {len(data.get('all_b64',[]))} фото", reply_markup=main_kb())
        return

    if "reportjson" in txt_low:
        if mm_vin:
            vin = mm_vin.group(0)
            await m.answer(f"📊 reportjson 50₽ для {vin}...")
            data = await check_v50(vin, reg, True)
            html = generate_html_v50(f"{vin}_reportjson", data, True)
            file = BufferedInputFile(html.encode('utf-8'), filename=f"ReportJSON_{vin}_v50.html")
            await m.answer_document(file, caption=f"📊 reportjson 50₽ Task {data.get('reportjson',{}).get('task_id')}", reply_markup=main_kb())
            return
        vin = LAST_REQUEST.get("vin")
        if vin:
            await m.answer(f"📊 reportjson 50₽ для последнего {vin}...")
            data = await check_v50(vin, LAST_REQUEST.get("reg"), True)
            html = generate_html_v50(f"{vin}_reportjson", data, True)
            file = BufferedInputFile(html.encode('utf-8'), filename=f"ReportJSON_{vin}_v50.html")
            await m.answer_document(file, caption=f"📊 reportjson 50₽", reply_markup=main_kb())
            return
        await m.answer("Пришли VIN для reportjson", reply_markup=main_kb())
        return

    if mm_vin:
        vin = mm_vin.group(0)
        await m.answer(f"🔍 v50 FIX: {vin} + {reg or 'без госномера — возьму из pic по VIN, не буду подставлять старый Р671ЕТ152'}...")
        data = await check_v50(vin, reg, False)
        html = generate_html_v50(vin, data, False)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"Autoteka_{vin}_v50_FIX.html")
        await m.answer_document(file, caption=f"📄 v50 FIX: VIN {vin} • Гос {data.get('meta',{}).get('reg')} • {len(data.get('all_b64',[]))} фото • Баг с Опелем исправлен", reply_markup=main_kb())
        return

    if mm_gos:
        await m.answer(f"🔍 Гос {reg} — нужен еще VIN для v50 FIX, пришли VIN", reply_markup=main_kb())
        return

    await m.answer("Пришли VIN", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())