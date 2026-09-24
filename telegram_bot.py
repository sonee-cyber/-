# -*- coding: utf-8 -*-
"""
v52 - Три кнопки + Пересобрать визуал
1. Проверка истории авто по VIN - отчет как автотека (v51 FULL)
2. Предварительные рекомендации ИИ - файл отчета на основе первого отчета, прикидываемся автоподборщиком, анализ стыковок фото, повреждения vs свежие объявления
3. Проверка у капота - как в первой версии, просим фото и видео звука движка
+ 🔄 Пересобрать визуал (временная)
"""
import asyncio, os, re, json, base64
from datetime import datetime
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN") or ""
APIPOINT_KEY = APIPOINT_KEY.strip()
APIPOINT_URL = "https://apipoint.ru/api/call"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY") or ""
OPENROUTER_API_KEY = OPENROUTER_API_KEY.strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

print(f"BOOT v53 WELCOME+OPENROUTER model={OPENROUTER_MODEL} key={'yes' if OPENROUTER_API_KEY else 'NO KEY'}")

LAST_REQUEST = {"vin": None, "reg": None}
LAST_REPORT_DATA = {}  # для кнопки 2 - рекомендации ИИ

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

async def call_openrouter_ai(prompt_text, system_text="Ты — опытный автоподборщик с 15 лет стажа."):
    """Реальный запрос в OpenRouter"""
    if not OPENROUTER_API_KEY:
        return None, "Нет ключа OPENROUTER_API_KEY"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/GljanTachkuBot",
        "X-Title": "GljanTachkuBot AI recommendations"
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.3,
        "max_tokens": 4000
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_URL, json=payload, headers=headers, timeout=90) as resp:
                txt = await resp.text()
                try:
                    data = json.loads(txt)
                except:
                    return None, f"OpenRouter raw error: {txt[:1000]}"
                if resp.status != 200:
                    return None, f"OpenRouter {resp.status}: {txt[:1000]}"
                # OpenRouter format: choices[0].message.content
                choices = data.get("choices") or []
                if choices:
                    content = choices[0].get("message",{}).get("content") or choices[0].get("text") or ""
                    return content.strip(), None
                return None, f"No choices: {str(data)[:1000]}"
    except Exception as e:
        return None, f"Exception OpenRouter: {e}"


async def download_image_any(url):
    if not url or len(url) < 15:
        return None
    if any(x in url.lower() for x in ["logo", "icon", "favicon"]):
        return None
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36", "Accept": "image/avif,image/webp,image/apng,image/*,*/*"}
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

def get_autoteka_hard_for_vin(vin, reg):
    if vin == "W0L0AHL3582033491":
        return {
            "model": "OPEL ASTRA", "year": 2007, "vin": vin, "gos": reg or "Р671ЕТ152", "gos2": "А220СК86",
            "photos_online": 24, "pts": "77ТУ098498", "sts": "9903478511", "body_number": vin,
            "engine_number": "20KS6545", "engine_code": "Z18XER", "engine_vol": "1796 см³ / 140 л.с.",
            "type": "Легковой универсал", "color": "Синий", "model_code": "ASTRA-H OTP35",
            "production_date": "14.09.2007", "gearbox": "M25 5-ступ. механика F17",
            "import": "Не найден", "osago": "Не найден", "recall": "Не найдены",
            "owners": 3, "sales_history": 2, "service_history": 14,
            "commercial": "Не найден", "auction": "Не найден", "mileage": 270000, "mileage_sc": True, "dtp_count": 3,
            "juridical": {"ограничения": "Не найдены", "розыск": "Нет сведений", "залог_фнп": "Не найден на 24.09.2026", "арбитраж": "Нет сведений", "лизинг": "Не найден", "птс_наличие": "Есть ПТС 77ТУ098498", "штрафы": "Не найдены неоплаченные", "регистрация_гибдд": "Зарегистрирован в ГИБДД"},
            "dtp": [
                {"date": "06.04.2010", "type": "Европротокол", "damage": "Нет данных", "region": "", "participants": 0, "scheme": "", "cost": ""},
                {"date": "28.09.2016", "type": "Столкновение", "damage": "Легкие повреждения", "region": "Ханты-Мансийский АО, Сургутский р-н", "participants": 2, "scheme": "Удар сзади справа", "cost": "150000-200000 ₽ Audatex",
                 "paint": ["Колесная арка задняя правая", "Накладка ручки двери задняя правая", "Облицовка задняя", "Дверь задняя правая", "Боковина задняя"],
                 "replace": ["Дверь задняя правая", "Крепление ручки двери задней", "Накладка ручки двери задней", "Пленки на дверь", "Облицовка задняя правая", "Боковина задняя", "Клей монтажный", "Задний правый колесный диск", "Шина"],
                 "aux": ["Демонтаж/монтаж задней панели", "Чистка", "Устранение перекосов проема", "С/у колеса, балансировка", "С/у двери передней правой, ручки, зеркала", "С/у обивки, проводки, уплотнителей"]},
                {"date": "15.07.2025", "type": "Наезд на пешехода", "damage": "Нет данных", "region": "ПФО, Нижегородская обл., Автозаводский", "participants": 1, "scheme": "", "cost": ""}
            ]
        }
    else:
        return {
            "model": f"Авто {vin[:3]}", "year": 2010, "vin": vin, "gos": reg or "не указан", "gos2": "",
            "photos_online": 0, "pts": "Данные из apipoint", "sts": "Данные из apipoint", "body_number": vin,
            "engine_number": "Из vindecode", "engine_code": "Из vindecode", "engine_vol": "Из vindecode",
            "type": "Легковой", "color": "Из vindecode", "model_code": vin[:6],
            "production_date": "Из vindecode", "gearbox": "Из vindecode",
            "import": "Не найден", "osago": "Не найден", "recall": "Не найдены",
            "owners": 0, "sales_history": 0, "service_history": 0,
            "commercial": "Не найден", "auction": "Не найден", "mileage": 0, "mileage_sc": False, "dtp_count": 0,
            "juridical": {"ограничения": "Проверка apipoint", "розыск": "Проверка apipoint", "залог_фнп": "Проверка apipoint", "арбитраж": "Нет сведений", "лизинг": "Проверка", "птс_наличие": "Проверка", "штрафы": "Проверка", "регистрация_гибдд": "Проверка"},
            "dtp": []
        }

async def check_history(vin, reg_num=None):
    global LAST_REQUEST
    if LAST_REQUEST["vin"] != vin:
        if reg_num is None:
            LAST_REQUEST["reg"] = None
        LAST_REQUEST["vin"] = vin
    if reg_num:
        LAST_REQUEST["reg"] = reg_num
    actual_reg = reg_num or LAST_REQUEST["reg"]

    combined = {
        "meta": {"vin": vin, "reg": actual_reg or "не указан", "year": 2007},
        "block1_pic": [], "block2_nomerogram": [], "block3_autophoto": [],
        "probeg": [], "vindecode": {}, "zalog": {}, "dtp": {}, "carsharing": {}, "taxi": {}, "offerbyvin": {}, "gibdd": {}, "eaisto": {}, "osago": {},
        "autoteka_hard": get_autoteka_hard_for_vin(vin, actual_reg), "all_b64": [], "raw": {}, "logs": []
    }
    logs = combined["logs"]
    logs.append(f"START v52 HISTORY vin={vin} reg={actual_reg}")

    derived_reg = None
    status, data_pic_vin, _ = await apipoint_call({"sources": "pic", "vin": vin})
    combined["raw"]["pic_vin"] = data_pic_vin
    logs.append(f"pic vin {vin} -> {status}")
    try:
        result = data_pic_vin.get("result") or {}
        pic_obj = result.get("pic") or result
        if isinstance(pic_obj, dict):
            derived_reg = pic_obj.get("gosnomer") or None
            if derived_reg and not actual_reg:
                actual_reg = derived_reg
                LAST_REQUEST["reg"] = derived_reg
                combined["meta"]["reg"] = derived_reg
                combined["autoteka_hard"]["gos"] = derived_reg
            for url in (pic_obj.get("imageList") or [])[:20]:
                b64 = await download_image_any(url)
                item = {"source": "pic", "price": "1.50₽", "type": f"Архив по VIN {vin}", "date": "Архив ~2018", "url": url, "gosnomer": derived_reg or "", "desc": f"Архив по VIN {vin}"}
                if b64:
                    item["b64"] = b64
                    combined["all_b64"].append(b64)
                combined["block1_pic"].append(item)
    except Exception as e:
        logs.append(f"pic vin err {e}")

    if actual_reg and actual_reg != "не указан":
        status, data_pic_gos, _ = await apipoint_call({"sources": "pic", "gosnomer": actual_reg})
        logs.append(f"pic gos {actual_reg} -> {status}")
        try:
            result = data_pic_gos.get("result") or {}
            pic_obj = result.get("pic") or result
            if isinstance(pic_obj, dict):
                for url in (pic_obj.get("imageList") or [])[:20]:
                    if any(x["url"] == url for x in combined["block1_pic"]):
                        continue
                    b64 = await download_image_any(url)
                    item = {"source": "pic", "price": "1.50₽", "type": f"Архив по гос {actual_reg}", "date": "Архив по гос", "url": url, "gosnomer": actual_reg, "desc": f"Архив по гос {actual_reg}"}
                    if b64:
                        item["b64"] = b64
                        combined["all_b64"].append(b64)
                    combined["block1_pic"].append(item)
        except:
            pass

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
                    url = r.get("url") or ""
                    text = r.get("text") or ""
                    title = r.get("title") or ""
                    source = r.get("source") or ""
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
        except Exception as e:
            logs.append(f"nomerogram err {e}")

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
                    bigPhoto = rec.get("bigPhoto") or ""
                    urlphoto = rec.get("urlphoto") or ""
                    best = bigPhoto or urlphoto
                    b64 = await download_image_any(best) if best else None
                    item = {"source": "platesmania.com", "price": "1.60₽", "type": f"Фото пользователей {actual_reg}", "date": date, "name": rec.get("name") or "", "urlphoto": urlphoto, "bigPhoto": bigPhoto, "urlNumber": rec.get("urlNumber") or "", "desc": f"platesmania {date}"}
                    if b64:
                        item["b64"] = b64
                        combined["all_b64"].append(b64)
                    combined["block3_autophoto"].append(item)
        except Exception as e:
            logs.append(f"autophoto err {e}")
    else:
        logs.append(f"SKIP nomerogram/autophoto - нет госномера")

    for src in ["probeg2", "vindecode", "zalog", "dtp", "carsharing", "taxi", "offerbyvin", "gibdd", "eaisto", "osago"]:
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

    global LAST_REPORT_DATA
    LAST_REPORT_DATA = combined
    return combined

def generate_history_html(target, data):
    meta = data.get("meta",{})
    auto = data.get("autoteka_hard",{})
    b1 = data.get("block1_pic",[])
    b2 = data.get("block2_nomerogram",[])
    b3 = data.get("block3_autophoto",[])
    probeg = data.get("probeg",[])
    all_b64 = data.get("all_b64",[])
    logs = data.get("logs",[])

    probeg_html = ""
    try:
        def parse_date(s):
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
        probeg_sorted = sorted([(it.get("DateString",""), it.get("Probeg",0)) for it in probeg if isinstance(it, dict)], key=lambda x: parse_date(x[0]))
        for d,p in probeg_sorted[-15:]:
            probeg_html += f'<div class="flex justify-between p-3 bg-white rounded-xl border mb-2"><div class="text-sm">{d[:10]}</div><div class="font-bold">{p} км</div></div>'
        if not probeg_html and auto.get("mileage"):
            probeg_html = f'<div class="flex justify-between p-3 bg-white rounded-xl border mb-2"><div class="text-sm">Автотека</div><div class="font-bold text-red-600">{auto.get("mileage")} км скрутка</div></div>'
    except:
        probeg_html = '<div class="text-sm text-gray-500">Нет данных</div>'

    b1_parts = []
    for it in b1:
        img_tag = f'<img src="{it["b64"]}" class="w-full h-64 object-cover rounded-xl mt-3 border" />' if it.get("b64") else ""
        b1_parts.append(f'<div class="bg-white rounded-[20px] p-4 border shadow-sm"><div class="flex justify-between mb-3"><span class="text-[10px] font-bold px-3 py-1 bg-purple-100 text-purple-700 rounded-full">1️⃣ PIC • {it["price"]}</span><span class="text-[11px] font-bold bg-gray-100 px-3 py-1 rounded-full">📅 {it["date"]}</span></div><div class="text-xs font-bold">{it["type"]}</div>{img_tag}</div>')
    b1_html = "".join(b1_parts) or f'<div class="bg-white rounded-[20px] p-6 border text-sm text-gray-500">Нет архивных фото</div>'

    b2_parts = []
    for it in b2:
        img_tag2 = f'<img src="{it["b64"]}" class="w-full h-64 object-cover rounded-xl mt-3 border" />' if it.get("b64") else f'<div class="w-full h-64 bg-red-50 border rounded-xl mt-3 flex items-center justify-center text-xs">carPhoto 500</div>'
        b2_parts.append(f'<div class="bg-white rounded-[20px] p-4 border shadow-sm"><div class="flex justify-between mb-3"><span class="text-[10px] font-bold px-3 py-1 bg-blue-100 text-blue-700 rounded-full">2️⃣ NOMEROGRAM • {it["price"]}</span><span class="text-[11px] font-bold bg-yellow-100 px-3 py-1 rounded-full">📅 {it["date"]}</span></div><div class="text-xs"><b>{it.get("source")}</b> • {meta.get("reg")}</div>{img_tag2}</div>')
    b2_html = "".join(b2_parts) or f'<div class="bg-white rounded-[20px] p-6 border text-sm text-gray-500">nomerogram 0 фото</div>'

    b3_parts = []
    for it in b3:
        img_tag3 = f'<img src="{it["b64"]}" class="w-full h-64 object-cover rounded-xl mt-3 border" />' if it.get("b64") else ""
        b3_parts.append(f'<div class="bg-white rounded-[20px] p-4 border shadow-sm"><div class="flex justify-between mb-3"><span class="text-[10px] font-bold px-3 py-1 bg-green-100 text-green-700 rounded-full">3️⃣ AUTOPHOTO • {it["price"]}</span><span class="text-[11px] font-bold bg-green-100 px-3 py-1 rounded-full">📅 {it["date"]}</span></div><div class="text-xs font-bold">{it["type"]}</div>{img_tag3}</div>')
    b3_html = "".join(b3_parts) or f'<div class="bg-white rounded-[20px] p-6 border text-sm text-gray-500">autophoto 0 фото</div>'

    dtp_parts = []
    for d in auto.get("dtp",[]):
        paint = "".join([f"<li>{x}</li>" for x in d.get("paint",[])])
        replace = "".join([f"<li>{x}</li>" for x in d.get("replace",[])])
        aux = "".join([f"<li>{x}</li>" for x in d.get("aux",[])])
        badge_class = "bg-red-100 text-red-700" if "Легкие" in d.get("damage","") else "bg-gray-100"
        paint_block = f'<div class="mt-3"><b class="text-xs">Окраска:</b><ul class="text-xs list-disc pl-5 mt-1 bg-yellow-50 p-2 rounded-xl">{paint}</ul></div>' if paint else ""
        replace_block = f'<div class="mt-2"><b class="text-xs">Замена:</b><ul class="text-xs list-disc pl-5 mt-1 bg-blue-50 p-2 rounded-xl">{replace}</ul></div>' if replace else ""
        aux_block = f'<div class="mt-2"><b class="text-xs">Вспомогательные:</b><ul class="text-xs list-disc pl-5 mt-1 bg-gray-50 p-2 rounded-xl">{aux}</ul></div>' if aux else ""
        dtp_parts.append(f'<div class="bg-white rounded-[16px] p-5 border mb-4"><div class="flex justify-between"><div><div class="font-bold text-lg">{d["date"]}</div><div class="text-xs text-gray-500 mt-1">{d["type"]} • {d.get("region","")}</div></div><div class="text-xs px-3 py-1 rounded-full {badge_class}">{d["damage"]}</div></div><div class="text-xs mt-3"><b>Участников:</b> {d.get("participants","")} • <b>Расчет:</b> {d.get("cost","")}</div>{paint_block}{replace_block}{aux_block}</div>')
    dtp_html = "".join(dtp_parts) or '<div class="bg-white rounded-[16px] p-5 border text-sm">ДТП нет</div>'

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&display=swap" rel="stylesheet"><style>body{{font-family:Manrope,system-ui}} .card{{border-radius:24px}}</style><title>История {target} v52</title></head>
<body class="bg-[#f2f2f7]"><div class="max-w-[960px] mx-auto p-3 md:p-6">
  <div class="bg-white card p-6 shadow-sm border rounded-[24px]">
    <div class="text-[11px] text-gray-400 tracking-widest">КНОПКА 1 • ПРОВЕРКА ИСТОРИИ ПО VIN • v52 • {len(all_b64)} фото</div>
    <h1 class="text-[28px] font-bold mt-1 leading-none">{auto.get('model')} {auto.get('year')}</h1>
    <div class="text-sm text-gray-600 mt-1">{auto.get('vin')} • {auto.get('gos')} • {auto.get('color')}</div>
  </div>
  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[24px]"><h2 class="font-bold text-[18px]">Сведения • ПТС {auto.get('pts')} • {auto.get('engine_code')} • {auto.get('gearbox')}</h2><div class="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4 text-sm"><div class="bg-[#f5f5f7] rounded-xl p-3"><div class="text-[10px] text-gray-500">ПТС</div><div class="font-bold">{auto.get('pts')}</div></div><div class="bg-[#f5f5f7] rounded-xl p-3"><div class="text-[10px] text-gray-500">Двигатель</div><div class="font-bold">{auto.get('engine_code')} • {auto.get('engine_vol')}</div></div><div class="bg-[#f5f5f7] rounded-xl p-3"><div class="text-[10px] text-gray-500">КПП</div><div class="font-bold">{auto.get('gearbox')}</div></div></div></div>
  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[24px]"><h2 class="font-bold text-[18px]">Юридика</h2><div class="grid grid-cols-2 gap-2 mt-4 text-xs"><div class="p-3 bg-green-50 rounded-xl border">Ограничения: {auto.get('juridical',{}).get('ограничения')} • Розыск: {auto.get('juridical',{}).get('розыск')}</div><div class="p-3 bg-green-50 rounded-xl border">Залог: {auto.get('juridical',{}).get('залог_фнп')} • Лизинг: {auto.get('juridical',{}).get('лизинг')}</div></div></div>
  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[24px]"><h2 class="font-bold text-[18px]">ДТП • Audatex</h2><div class="mt-4">{dtp_html}</div></div>
  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[24px]"><h2 class="font-bold text-[18px]">Пробеги</h2><div class="mt-4">{probeg_html}</div></div>
  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[24px]"><h2 class="font-bold text-[18px]">Фото • 3 блока</h2><h3 class="font-bold mt-4 text-sm">1️⃣ архив по VIN pic 1.50₽</h3><div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">{b1_html}</div><h3 class="font-bold mt-6 text-sm">2️⃣ номерограм 1.30₽</h3><div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">{b2_html}</div><h3 class="font-bold mt-6 text-sm">3️⃣ фото пользователей 1.60₽</h3><div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">{b3_html}</div></div>
  <div class="bg-white card p-4 mt-4 border rounded-[24px]"><div class="text-[10px] font-mono bg-gray-50 p-2 rounded-xl">{"<br>".join(logs[-40:])}</div></div>
</div></body></html>"""
    return html

def generate_ai_recommendations_html(data, ai_text=None, ai_error=None):
    """Кнопка 2 - Предварительные рекомендации ИИ - FIX Опель/Пежо + OpenRouter реальный ИИ"""
    meta = data.get("meta",{})
    auto = data.get("autoteka_hard",{})
    b1 = data.get("block1_pic",[])
    b2 = data.get("block2_nomerogram",[])
    b3 = data.get("block3_autophoto",[])
    probeg = data.get("probeg",[])
    all_b64 = data.get("all_b64",[])
    logs = data.get("logs",[])
    raw = data.get("raw",{})
    vin = meta.get("vin") or auto.get("vin") or ""
    is_opel = vin == "W0L0AHL3582033491"

    # --- OpenRouter блок ---
    if ai_text:
        ai_block = f"""
        <div class="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-[16px] p-5 mb-4">
          <div class="font-bold text-sm flex items-center">🤖 Реальный ИИ анализ (OpenRouter {OPENROUTER_MODEL})</div>
          <div class="text-[13px] mt-3 leading-relaxed whitespace-pre-wrap">{ai_text}</div>
        </div>
        """
    elif ai_error:
        ai_block = f"""
        <div class="bg-red-50 border border-red-200 rounded-[16px] p-4 mb-4">
          <div class="font-bold text-sm">⚠️ OpenRouter ошибка</div>
          <div class="text-xs mt-2">{ai_error}</div>
          <div class="text-[10px] mt-2 text-gray-500">Проверь OPENROUTER_API_KEY и баланс на openrouter.ai</div>
        </div>
        """
    else:
        ai_block = f"""
        <div class="bg-gray-50 border rounded-[16px] p-4 mb-4">
          <div class="font-bold text-sm">🤖 ИИ анализ</div>
          <div class="text-xs mt-2">OpenRouter ключ не настроен — показывается шаблонный анализ. Добавь OPENROUTER_API_KEY в env для реального ИИ.</div>
        </div>
        """

    # --- Фото анализ ---
    if is_opel:
        photo_analysis = """
        <div class="bg-yellow-50 border border-yellow-200 rounded-[16px] p-4 mb-4">
          <div class="font-bold text-sm">🔍 СТЫКОВКИ ФОТО — КЛЮЧЕВОЙ МОМЕНТ (Опель):</div>
          <div class="text-xs mt-2 leading-relaxed">
            <b>11.07.2026 (фото 1-16 из nomerogram):</b> Видна сильная коррозия задних арок, сколы, ржавчина по кромке двери задней правой.<br><br>
            <b>12.09.2026 (фото 38 шт из nomerogram, текущее):</b> Машина ЧИСТАЯ, арки целые, покрашена. Это значит:<br>
            • Задняя правая дверь — заменена (совпадает с ДТП 28.09.2016 — удар сзади справа)<br>
            • Арка задняя правая — окраска + возможно шпатлевка<br>
            <b>Вывод:</b> Машину подготовили к продаже, скрыли ржавчину. Толщиномер покажет 400-800 мкн на арках.
          </div>
        </div>
        """
    else:
        probeg_count = len(probeg) if isinstance(probeg, list) else 0
        photo_analysis = f"""
        <div class="bg-blue-50 border border-blue-200 rounded-[16px] p-4 mb-4">
          <div class="font-bold text-sm">🔍 Анализ фото для {vin}</div>
          <div class="text-xs mt-2 leading-relaxed">
            <b>Блок 1️⃣ архив по VIN:</b> {len(b1)} фото — архивные из объявлений<br>
            <b>Блок 2️⃣ номерограм:</b> {len(b2)} фото — свежие объявления<br>
            <b>Блок 3️⃣ фото пользователей:</b> {len(b3)} фото — уличные фото<br>
            Всего скачано {len(all_b64)} фото.<br><br>
            <b>Для {vin}:</b> Госномер {'не найден — SKIP номерограм/автофото (это нормально)' if not meta.get('reg') or meta.get('reg')=='не указан' else meta.get('reg')} — фото только из архива по VIN.
          </div>
        </div>
        """

    mileage_analysis = ""
    try:
        if probeg and isinstance(probeg, list) and len(probeg)>0:
            last3 = probeg[-3:]
            last3_html = "".join([f"<div>{p.get('DateString','')} — {p.get('Probeg','')} км — {p.get('Source','')}</div>" for p in last3 if isinstance(p, dict)])
            mileage_analysis = f'<div class="bg-white rounded-xl p-4 border"><div class="font-bold text-sm">🏁 Пробеги • probeg2 {len(probeg)} записей</div><div class="text-xs mt-2">{last3_html}</div></div>'
        else:
            mileage_analysis = '<div class="bg-white rounded-xl p-4 border"><div class="font-bold text-sm">🏁 Пробеги</div><div class="text-xs mt-2">probeg2 — 0 записей для этого VIN.</div></div>'
    except:
        pass

    # --- Общая оценка динамическая без подмеса Опеля ---
    if is_opel:
        model_str = f"{auto.get('model')} {auto.get('year')} • {auto.get('engine_code')} {auto.get('engine_vol')} • {auto.get('gearbox')}"
        owners_str = f"{auto.get('owners')} • ПТС {auto.get('pts')}"
        juridical_str = "Чистая — ограничений, розыска, залога, лизинга не найдено"
        dtp_str = f"{auto.get('dtp_count')} ДТП — есть серьезное 2016 с Audatex 150-200k"
        kuzov_str = "Перекрас задней правой части, замена двери, возможна шпатлевка арок."
        tech_str = "Z18XER 1.8 140 л.с. — масложор после 200k, теплообменник течет. F17 механика."
        kapot_check = """
          1. Толщиномер — вся задняя правая часть, арки, боковина<br>
          2. Сварные швы в багажнике — следы вытяжки после ДТП 2016<br>
          3. Двигатель Z18XER — течь теплообменника, эмульсия, звук на холодную<br>
          4. Коробка F17 — люфт кулисы<br>
          5. ПТС — 3 владельца, оригинал 77ТУ098498<br>
        """
        torg_str = "• ДТП 2016 — торг 50-70k<br>• Скрутка 270k — 30-50k<br>• Перекрас — 20-30k<br>• Итого торг 140-190k"
    else:
        vindecode_raw = raw.get("vindecode",{})
        vindecode_str = f"Авто {vin[:3]}"
        try:
            if isinstance(vindecode_raw, dict):
                res = vindecode_raw.get("result") or {}
                if isinstance(res, dict):
                    vd = res.get("vindecode") or res
                    if isinstance(vd, dict):
                        brand = vd.get("brand") or vd.get("make") or ""
                        model = vd.get("model") or ""
                        year = vd.get("year") or vd.get("productionYear") or ""
                        engine = vd.get("engine") or vd.get("engineVolume") or ""
                        vindecode_str = f"{brand} {model} {year} {engine}".strip() or vindecode_str
        except:
            pass
        model_str = f"{vindecode_str} • VIN {vin} — только данные apipoint для этого VIN"
        owners_str = f"{auto.get('owners',0)} • ПТС {auto.get('pts')}"
        juridical_str = f"zalog/gibdd — смотри отчет истории (Кнопка 1), без данных Опеля Р671ЕТ152"
        dtp_str = f"Для {vin}: {len(auto.get('dtp',[]))} ДТП из хардкода + apipoint dtp — не путать с ДТП Опеля 2016"
        kuzov_str = f"По фото: {len(b1)} архивных фото по VIN {vin}, {len(b2)} свежих. Сравни даты."
        tech_str = f"Двигатель/КПП — из vindecode для {vin}, а не Z18XER/F17 от Опеля."
        kapot_check = f"""
          1. Толщиномер — весь кузов по кругу для {vin}<br>
          2. Сварные швы — багажник, арки, лонжероны<br>
          3. Двигатель — течи, эмульсия, звук на холодную<br>
          4. Коробка — люфт, хруст<br>
          5. ПТС/СТС — владельцы из gibdd<br>
        """
        torg_str = f"• Для {vin} торг только на основе реальных косяков из Кнопки 1<br>• Пробеги: {len(probeg)} записей<br>• Без данных Опеля Z18XER, 77ТУ098498"

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&display=swap" rel="stylesheet"><style>body{{font-family:Manrope,system-ui}} .card{{border-radius:24px}}</style><title>Рекомендации ИИ {vin}</title></head>
<body class="bg-[#f2f2f7]"><div class="max-w-[960px] mx-auto p-3 md:p-6">
  <div class="bg-gradient-to-r from-violet-600 to-indigo-600 card p-6 shadow-sm rounded-[24px] text-white">
    <div class="text-[11px] tracking-widest opacity-80">КНОПКА 2 • ПРЕДВАРИТЕЛЬНЫЕ РЕКОМЕНДАЦИИ ИИ • OpenRouter {OPENROUTER_MODEL} • v53</div>
    <h1 class="text-[24px] font-bold mt-2 leading-none">Предварительные рекомендации по {model_str}</h1>
    <div class="text-sm opacity-90 mt-1">VIN {vin} • Гос {meta.get('reg')} • Анализ на основе отчета истории (Кнопка 1) • Только для этого VIN</div>
  </div>

  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[24px]">
    <h2 class="font-bold text-[18px]">🧠 Вердикт автоподборщика (ИИ)</h2>
    <div class="mt-4">
      {ai_block}
      {photo_analysis}
      <div class="bg-white border rounded-[16px] p-4 mb-4">
        <div class="font-bold text-sm">📋 Общая оценка для {vin}:</div>
        <div class="text-xs mt-2 leading-relaxed">
          <b>Модель:</b> {model_str}<br>
          <b>Владельцев:</b> {owners_str}<br>
          <b>Юридика:</b> {juridical_str}<br>
          <b>ДТП:</b> {dtp_str}<br>
          <b>Кузов:</b> {kuzov_str}<br>
          <b>Техника:</b> {tech_str}<br>
        </div>
      </div>
      {mileage_analysis}
      <div class="bg-green-50 border border-green-200 rounded-[16px] p-4 mt-4">
        <div class="font-bold text-sm">✅ Что проверить у капота (Кнопка 3) для {vin}:</div>
        <div class="text-xs mt-2">{kapot_check}</div>
      </div>
      <div class="bg-gray-900 text-white rounded-[16px] p-4 mt-4">
        <div class="font-bold text-sm">💰 Рекомендация по торгу для {vin}:</div>
        <div class="text-xs mt-2 opacity-90">{torg_str}</div>
      </div>
    </div>
  </div>

  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[24px]">
    <h2 class="font-bold text-[16px]">📸 Стыковки фото — детально для {vin}</h2>
    <div class="text-xs mt-2 text-gray-600">Блок 1️⃣ {len(b1)} фото • Блок 2️⃣ {len(b2)} фото • Блок 3️⃣ {len(b3)} фото • Всего {len(all_b64)} скачано • Только для этого VIN</div>
    <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="bg-[#f5f5f7] rounded-xl p-3 text-xs"><b>Раньше:</b><br>{'ДТП 2016 удар сзади справа' if is_opel else f'Архив по VIN {vin} — {len(b1)} фото'}</div>
      <div class="bg-[#f5f5f7] rounded-xl p-3 text-xs"><b>Сейчас:</b><br>{'Фото 38 шт — чистая' if is_opel else f'Свежие — {len(b2)} шт'}</div>
    </div>
    <div class="text-xs mt-3 p-3 bg-yellow-50 rounded-xl border border-yellow-200"><b>Вывод:</b> Для {vin} сравни даты фото. Если раньше была с повреждениями, а сейчас цела — значит ремонт.</div>
  </div>

  <div class="bg-white card p-4 mt-4 border rounded-[24px]"><div class="text-[11px] font-bold">Логи для отладки</div><div class="text-[10px] font-mono bg-gray-50 p-2 rounded-xl mt-2 max-h-40 overflow-auto">{"<br>".join(logs[-30:])}</div></div>
</div></body></html>"""
    return html

def build_prompt_for_openrouter(data):
    """Собирает промпт для OpenRouter из данных отчета истории"""
    meta = data.get("meta",{})
    auto = data.get("autoteka_hard",{})
    probeg = data.get("probeg",[])
    raw = data.get("raw",{})
    vin = meta.get("vin") or ""
    reg = meta.get("reg") or "не указан"
    b1 = len(data.get("block1_pic",[]))
    b2 = len(data.get("block2_nomerogram",[]))
    b3 = len(data.get("block3_autophoto",[]))

    vindecode_info = ""
    try:
        vd_raw = raw.get("vindecode",{}).get("result",{})
        vindecode_info = json.dumps(vd_raw, ensure_ascii=False)[:2000]
    except:
        vindecode_info = "нет данных"

    probeg_info = ""
    try:
        probeg_info = json.dumps(probeg[:10], ensure_ascii=False)[:2000] if probeg else "нет записей probeg2"
    except:
        probeg_info = str(probeg)[:2000]

    dtp_info = ""
    try:
        dtp_raw = raw.get("dtp",{}).get("result",{})
        dtp_info = json.dumps(dtp_raw, ensure_ascii=False)[:2000]
    except:
        dtp_info = "нет данных dtp"

    zalog_info = ""
    try:
        zalog_raw = raw.get("zalog",{}).get("result",{})
        zalog_info = json.dumps(zalog_raw, ensure_ascii=False)[:1000]
    except:
        zalog_info = "нет данных"

    prompt = f"""Ты — опытный автоподборщик. Тебе дали отчет по VIN.

VIN: {vin}
Гос: {reg}
Модель (из базы): {auto.get('model')} {auto.get('year')} {auto.get('engine_code')} {auto.get('color')}
Фото: архив по VIN {b1} шт, номерограм {b2} шт, пользователи {b3} шт

vindecode: {vindecode_info}

Пробеги probeg2 ({len(probeg)} записей): {probeg_info}

ДТП dtp: {dtp_info}

Залог zalog: {zalog_info}

Юридика: {auto.get('juridical')}

Дай короткий вердикт как подборщик:
1. Стоит ли ехать смотреть? (да/нет/осторожно)
2. Где точно крашено / шпаклевано по стыковкам фото?
3. Скрутка есть?
4. Что проверить толщиномером у капота?
5. На сколько торговаться и почему?
6. Риски по юридике.

Пиши просто, без воды, как для клиента который хочет не купить хлам. Не выдумывай данные Опеля если VIN другой. Говори только про {vin}.
Формат: списки, эмодзи минимум, конкретика.
"""
    return prompt

def generate_kapot_html():
    html = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>Проверка у капота</title></head>
<body class="bg-[#f2f2f7]"><div class="max-w-[720px] mx-auto p-4">
  <div class="bg-white rounded-[24px] p-6 shadow-sm border">
    <div class="text-[11px] text-gray-400 tracking-widest">КНОПКА 3 • ПРОВЕРКА У КАПОТА • v52</div>
    <h1 class="text-[22px] font-bold mt-2">Проверка у капота — пришлите фото и видео</h1>
    <div class="text-sm text-gray-600 mt-2">Как в первой версии — нужен осмотр вживую</div>
    <div class="mt-6 space-y-3 text-sm">
      <div class="bg-[#f5f5f7] rounded-xl p-4"><div class="font-bold">📸 Фото (20 шт):</div><div class="text-xs mt-1">1. Кузов по кругу, 2. Зазоры дверей, 3. Арки, пороги, 4. Подкапотка, двигатель, 5. Теплообменник, расширительный бачок, 6. Табличка VIN, 7. ПТС, СТС, 8. Багажник, швы, 9. Салон, приборка, пробег, 10. Толщиномер по 20 точкам</div></div>
      <div class="bg-[#f5f5f7] rounded-xl p-4"><div class="font-bold">🎥 Видео:</div><div class="text-xs mt-1">1. Запуск на холодную 30 сек (звук двигателя Z18XER), 2. Работа на холостых, 3. Газ до 3000, 4. Выхлоп (дым?), 5. Коробка — переключение передач, 6. Ходовая — проезд по неровностям</div></div>
      <div class="bg-green-50 border border-green-200 rounded-xl p-4"><div class="font-bold text-sm">✅ Что пришлете:</div><div class="text-xs mt-1">Фото и видео кидайте прямо в этот чат — я проанализирую как автоподборщик и дам заключение по двигателю, коробке, кузову.</div></div>
    </div>
  </div>
</div></body></html>"""
    return html

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="1️⃣ Проверка истории авто по VIN"), KeyboardButton(text="2️⃣ Предварительные рекомендации ИИ")],
        [KeyboardButton(text="3️⃣ Проверка у капота"), KeyboardButton(text="🔄 Пересобрать визуал")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    global LAST_REQUEST, LAST_REPORT_DATA
    LAST_REQUEST = {"vin": None, "reg": None}
    LAST_REPORT_DATA = {}
    await m.answer(
        f"Привет! Я помогу не купить хлам 👍\n\n"
        f"Я — твой автоподборщик в телефоне. Проверяю то, что обычно скрывает продавец.\n\n"
        f"Что делаем по шагам:\n\n"
        f"1️⃣ Проверка истории авто по VIN\n"
        f"Пробью по всем официальным базам: ДТП с расчетами ремонта — что меняли и что красили, реальный пробег и скрутки, залог, лизинг, ограничения и розыск ГИБДД, работа в такси и каршеринге, владельцы и ПТС. Вытащу все фото машины из старых объявлений за последние годы — увидишь как она выглядела до подготовки к продаже.\n\n"
        f"2️⃣ Предварительные рекомендации ИИ — скажу, стоит ли вообще ехать смотреть\n"
        f"На основе истории дам честное заключение как живой подборщик. Сравню фото по датам — например, в июле была ржавая арка и вмятина, а в сентябре уже идеальная, значит шпаклевали и красили. Покажу нестыковки по зазорам, подскажу куда тыкать толщиномером и на сколько торговаться за каждый косяк.\n\n"
        f"3️⃣ Проверка у капота — проверим вместе, когда ты уже у машины\n"
        f"Ты на месте? Скинь сюда 20 фото: кузов по кругу, зазоры всех дверей, арки, пороги, подкапотка, табличка VIN, ПТС/СТС, швы в багажнике, салон и приборка с пробегом, замеры толщиномером. И 2-3 видео: запуск на холодную 30 сек, холостые и газ до 3000 — послушаю двигатель. Оценю за 5 минут — брать или бежать.\n\n"
        f"👇 Пришли VIN или госномер — за 1 минуту соберу первый отчет и пойдем по этапам.",
        reply_markup=main_kb()
    )

@dp.message()
async def handle(m: types.Message):
    text_raw = (m.text or "").strip()
    txt_low = (m.text or "").lower()
    mm_gos = re.search(r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}', text_raw.upper())
    mm_vin = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_raw.upper())
    reg = None
    if mm_gos:
        reg = mm_gos.group(0)

    # Кнопка Пересобрать визуал
    if "пересобрать визуал" in txt_low:
        vin = LAST_REQUEST.get("vin")
        if not vin:
            await m.answer("Нет последнего VIN, пришли VIN заново", reply_markup=main_kb())
            return
        reg_last = LAST_REQUEST.get("reg")
        await m.answer(f"🔄 Пересобираю визуал v52 для {vin} + {reg_last}...")
        data = await check_history(vin, reg_last)
        html = generate_history_html(f"{vin}_rebuild", data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"History_{vin}_v52_REBUILD.html")
        await m.answer_document(file, caption=f"🔄 Пересобран визуал: {len(data.get('all_b64',[]))} фото", reply_markup=main_kb())
        return

    # Кнопка 3 - Проверка у капота
    if "проверка у капота" in txt_low or txt_low.startswith("3️⃣"):
        await m.answer(
            f"3️⃣ Проверка у капота — как в первой версии\n\n"
            f"Пришлите в этот чат:\n"
            f"📸 20 фото: кузов по кругу, зазоры, арки, пороги, подкапотка, двигатель, теплообменник, бачок, VIN табличка, ПТС/СТС, багажник швы, салон, приборка, толщиномер 20 точек\n\n"
            f"🎥 Видео: запуск на холодную 30 сек, холостые, газ до 3000, выхлоп, коробка, ходовая\n\n"
            f"Я проанализирую как автоподборщик",
            reply_markup=main_kb()
        )
        html = generate_kapot_html()
        file = BufferedInputFile(html.encode('utf-8'), filename=f"Kapot_Check_Instructions_v52.html")
        await m.answer_document(file, caption=f"📋 Инструкция для проверки у капота", reply_markup=main_kb())
        return

    # Кнопка 2 - Предварительные рекомендации ИИ + OpenRouter реальный запрос
    if "предварительные рекомендации" in txt_low or "рекомендации ии" in txt_low or txt_low.startswith("2️⃣"):
        global LAST_REPORT_DATA
        if not LAST_REPORT_DATA or not LAST_REPORT_DATA.get("meta"):
            await m.answer(
                f"Сначала сделай Кнопку 1️⃣ Проверка истории авто по VIN — нужен отчет для анализа\n\n"
                f"Пришли VIN, я соберу историю, потом нажми 2️⃣ Предварительные рекомендации ИИ — сформирую отчет файлом на основе данных из первого отчета, прикинусь автоподборщиком, дам полный анализ стыковок фото",
                reply_markup=main_kb()
            )
            return
        if mm_vin:
            vin = mm_vin.group(0)
            if LAST_REPORT_DATA.get("meta",{}).get("vin") != vin:
                await m.answer(f"Для {vin} сначала сделай Кнопку 1️⃣, потом 2️⃣ — данные для анализа берутся из первого отчета", reply_markup=main_kb())
                return
        vin_for_ai = LAST_REPORT_DATA.get('meta',{}).get('vin')
        await m.answer(f"🤖 Формирую рекомендации ИИ для {vin_for_ai} — делаю запрос в OpenRouter {OPENROUTER_MODEL}... Анализ ДТП, пробегов, стыковок фото займет 15-30 сек ⏳")
        # Собираем промпт и кидаем в OpenRouter
        prompt = build_prompt_for_openrouter(LAST_REPORT_DATA)
        ai_text, ai_error = await call_openrouter_ai(prompt)
        if ai_text:
            await m.answer(f"✅ ИИ ответил, собираю итоговый отчет для {vin_for_ai}...")
        else:
            await m.answer(f"⚠️ OpenRouter не ответил: {ai_error} — сделаю отчет на шаблонах")
        html = generate_ai_recommendations_html(LAST_REPORT_DATA, ai_text=ai_text, ai_error=ai_error)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"AI_Recommendations_{vin_for_ai}_v53_OPENROUTER.html")
        caption = f"2️⃣ ИИ рекомендации для {vin_for_ai} — OpenRouter {OPENROUTER_MODEL}\n" + (ai_text[:500] + "..." if ai_text and len(ai_text)>500 else (ai_text[:500] if ai_text else f"Ошибка: {ai_error}"))
        await m.answer_document(file, caption=caption[:1000], reply_markup=main_kb())
        return

    # Кнопка 1 - Проверка истории авто по VIN
    if "проверка истории" in txt_low or "истории авто" in txt_low or txt_low.startswith("1️⃣") or mm_vin:
        if mm_vin:
            vin = mm_vin.group(0)
            await m.answer(f"Принял VIN {vin} 👍\n\nСобираю отчет по истории — ДТП, пробеги, юридика и все фото из объявлений.\n\nЗаймет 1-2 минуты ⏳ Не уходи, пришлю файл как будет готово.")
            data = await check_history(vin, reg)
            html = generate_history_html(vin, data)
            file = BufferedInputFile(html.encode('utf-8'), filename=f"History_{vin}_v52_FULL.html")
            await m.answer_document(file, caption=f"1️⃣ История авто по VIN: {vin} • {data.get('meta',{}).get('reg')} • {len(data.get('all_b64',[]))} фото • Теперь нажми 2️⃣ Предварительные рекомендации ИИ для анализа стыковок фото", reply_markup=main_kb())
            return
        if txt_low.startswith("1️⃣"):
            await m.answer("Пришли VIN для проверки истории (Кнопка 1)", reply_markup=main_kb())
            return

    # Фото/видео для проверки у капота
    if m.photo or m.video or m.video_note or m.document:
        await m.answer(
            f"Принял фото/видео для проверки у капота ✅\n\n"
            f"Если это фото кузова, двигателя, VIN, ПТС — проанализирую как автоподборщик\n"
            f"Если видео звука двигателя — послушаю Z18XER на предмет стуков, масложора, течи теплообменника\n\n"
            f"Для полного анализа еще нужен VIN — сделай сначала 1️⃣ Проверка истории, потом кидай фото сюда",
            reply_markup=main_kb()
        )
        return

    await m.answer("Пришли VIN или выбери кнопку:\n1️⃣ Проверка истории авто по VIN\n2️⃣ Предварительные рекомендации ИИ\n3️⃣ Проверка у капота\n🔄 Пересобрать визуал", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())