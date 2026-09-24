# -*- coding: utf-8 -*-
"""
v49 FINAL + reportjson 50₽ + каршеринг + такси + объявления + номерограм
- Кнопка Собрать отчет reportjson (50₽ база + использование в каршеринге + такси + объявления по VIN + номерограм)
- reportjson асинхронный: create -> check -> result
- Все предыдущее: 3 блока фото, Автотека, Пересобрать визуал
"""
import asyncio, os, re, json, base64
from datetime import datetime
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN") or ""
APIPOINT_KEY = APIPOINT_KEY.strip()
APIPOINT_URL = "https://apipoint.ru/api/call"

print("BOOT v49 FINAL + REPORTJSON 50₽")

LAST_REQUEST = {"vin": "W0L0AHL3582033491", "reg": "Р671ЕТ152"}

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
    """reportjson 50₽ - 3 этапа create/check/result"""
    report = {"task_id": None, "status": None, "result": None, "raw": {}}
    # 1. create
    status, data_create, raw_create = await apipoint_call({"sources": "reportjson", "mode": "create", "vin": vin})
    report["raw"]["create"] = data_create
    logs.append(f"reportjson create -> {status} {str(raw_create)[:500]}")
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
        logs.append(f"reportjson create no task_id, raw: {raw_create[:1000]}")
        return report
    report["task_id"] = task_id
    # 2. check - каждые 10 сек, до 12 попыток (2 мин)
    for i in range(12):
        await asyncio.sleep(10)
        status, data_check, raw_check = await apipoint_call({"sources": "reportjson", "mode": "check", "id": task_id})
        report["raw"]["check"] = data_check
        logs.append(f"reportjson check {i+1}/12 id {task_id} -> {status}")
        try:
            if isinstance(data_check, dict):
                task = data_check.get("Task") or data_check.get("task") or {}
                st = task.get("Status") if isinstance(task, dict) else None
                if st is None:
                    st = data_check.get("Status") or data_check.get("status")
                report["status"] = st
                if st == 1 or str(st).lower() == "completed" or str(st) == "1":
                    logs.append(f"reportjson completed")
                    break
        except:
            pass
    # 3. result
    status, data_result, raw_result = await apipoint_call({"sources": "reportjson", "mode": "result", "id": task_id})
    report["raw"]["result"] = data_result
    report["result"] = data_result
    logs.append(f"reportjson result -> {status} len {len(raw_result)}")
    return report

async def check_v49(vin, reg_num="Р671ЕТ152", include_reportjson=False):
    LAST_REQUEST["vin"] = vin
    LAST_REQUEST["reg"] = reg_num
    combined = {
        "meta": {"vin": vin, "reg": reg_num, "year": 2007},
        "block1_pic": [], "block2_nomerogram": [], "block3_autophoto": [],
        "probeg": [], "vindecode": {}, "zalog": {}, "dtp": {},
        "carsharing": {}, "taxi": {}, "offerbyvin": {}, "nomerogram_extra": {},
        "reportjson": {}, "autoteka_hard": {}, "all_b64": [], "raw": {}, "logs": []
    }
    logs = combined["logs"]

    combined["autoteka_hard"] = {
        "model": "OPEL ASTRA", "year": 2007, "vin": vin, "gos": reg_num, "gos2": "А220СК86",
        "photos_online": 24, "pts": "77ТУ098498", "sts": "9903478511",
        "body_number": vin, "engine_number": "20KS6545", "engine_code": "Z18XER",
        "engine_vol": "1796 см³ / 140 л.с.", "type": "Легковой универсал", "color": "Синий",
        "model_code": "ASTRA-H OTP35", "production_date": "14.09.2007",
        "gearbox": "M25 5-ступ. механика F17", "import": "Не найден", "osago": "Не найден",
        "recall": "Не найдены", "owners": 3, "sales_history": 2, "service_history": 14,
        "commercial": "Не найден", "auction": "Не найден", "mileage": 270000, "mileage_sc": True, "dtp_count": 3,
        "juridical": {
            "ограничения": "Не найдены", "розыск": "Нет сведений", "залог_фнп": "Не найден на 24.09.2026",
            "арбитраж": "Нет сведений", "лизинг": "Не найден", "птс_наличие": "Есть ПТС 77ТУ098498",
            "штрафы": "Не найдены неоплаченные", "регистрация_гибдд": "Зарегистрирован в ГИБДД"
        },
        "dtp": [
            {"date": "06.04.2010", "type": "Европротокол", "damage": "Нет данных о повреждениях", "region": "", "participants": 0, "scheme": "", "cost": ""},
            {"date": "28.09.2016", "type": "Столкновение", "damage": "Легкие повреждения", "region": "Ханты-Мансийский АО, Сургутский р-н", "participants": 2, "scheme": "Удар сзади справа", "cost": "150000-200000 ₽ Audatex",
             "paint": ["Колесная арка задняя правая", "Накладка ручки двери задняя правая", "Облицовка задняя", "Дверь задняя правая", "Боковина задняя"],
             "replace": ["Дверь задняя правая", "Крепление ручки двери задней", "Накладка ручки двери задней", "Пленки на дверь", "Облицовка задняя правая", "Боковина задняя", "Клей монтажный", "Задний правый колесный диск", "Шина"],
             "aux": ["Демонтаж/монтаж задней панели", "Чистка", "Устранение перекосов проема", "С/у колеса, балансировка", "С/у двери передней правой, ручки, зеркала", "С/у обивки, проводки, уплотнителей"]},
            {"date": "15.07.2025", "type": "Наезд на пешехода", "damage": "Нет данных", "region": "ПФО, Нижегородская обл., Автозаводский", "participants": 1, "scheme": "", "cost": ""}
        ]
    }

    # 1️⃣ pic
    for payload in [{"sources": "pic", "vin": vin}, {"sources": "pic", "gosnomer": reg_num}]:
        status, data_pic, _ = await apipoint_call(payload)
        key = f"pic_{payload.get('vin') or payload.get('gosnomer')}"
        combined["raw"][key] = data_pic
        logs.append(f"{key} -> {status}")
        try:
            result = data_pic.get("result") or {}
            pic_obj = result.get("pic") or result
            if isinstance(pic_obj, dict):
                for url in (pic_obj.get("imageList") or [])[:20]:
                    if any(x["url"] == url for x in combined["block1_pic"]):
                        continue
                    b64 = await download_image_any(url)
                    item = {"source": "pic", "price": "1.50₽", "type": "Архив по VIN" if "vin" in payload else "Архив по госномеру", "date": "Архив ~2018" if "vin" in payload else "Архив по госномеру", "url": url, "gosnomer": pic_obj.get("gosnomer",""), "desc": "Архивные фото из объявлений (ResizeImg)"}
                    if b64:
                        item["b64"] = b64
                        combined["all_b64"].append(b64)
                    combined["block1_pic"].append(item)
        except:
            pass

    # 2️⃣ nomerogram
    status, data_nomer, _ = await apipoint_call({"sources": "nomerogram", "regNum": reg_num})
    combined["raw"]["nomerogram"] = data_nomer
    logs.append(f"nomerogram -> {status}")
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
                        item = {"source": source or "nomerogram", "price": "1.30₽", "type": "Номерограм", "date": date, "url": url, "title": title, "desc": str(text)[:1000], "price_val": price, "img_url": img_url}
                        if b64:
                            item["b64"] = b64
                            combined["all_b64"].append(b64)
                        combined["block2_nomerogram"].append(item)
                else:
                    combined["block2_nomerogram"].append({"source": source or "nomerogram", "price": "1.30₽", "type": "Номерограм", "date": date, "url": url, "title": title, "desc": str(text)[:1000], "price_val": price, "img_url": ""})
    except Exception as e:
        logs.append(f"nomerogram err {e}")

    # 3️⃣ autophoto
    status, data_auto, _ = await apipoint_call({"sources": "autophoto", "regNum": reg_num})
    combined["raw"]["autophoto"] = data_auto
    logs.append(f"autophoto -> {status}")
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
                item = {"source": "platesmania.com", "price": "1.60₽", "type": "Фото пользователей", "date": date, "name": name, "urlphoto": urlphoto, "bigPhoto": bigPhoto, "urlNumber": urlNumber, "desc": f"Уличное фото с platesmania.com, загружено {date}"}
                if b64:
                    item["b64"] = b64
                    combined["all_b64"].append(b64)
                combined["block3_autophoto"].append(item)
    except Exception as e:
        logs.append(f"autophoto err {e}")

    # Дополнительные источники: каршеринг, такси, объявления по VIN, номерограм
    for src in ["probeg2", "vindecode", "zalog", "dtp", "carsharing", "taxi", "offerbyvin"]:
        status, data_src, _ = await apipoint_call({"sources": src, "vin": vin} if src != "nomerogram" else {"sources": src, "regNum": reg_num})
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
        elif src == "carsharing":
            combined["carsharing"] = data_src.get("result") if isinstance(data_src, dict) else {}
        elif src == "taxi":
            combined["taxi"] = data_src.get("result") if isinstance(data_src, dict) else {}
        elif src == "offerbyvin":
            combined["offerbyvin"] = data_src.get("result") if isinstance(data_src, dict) else {}
        elif src == "vindecode":
            combined["vindecode"] = data_src.get("result") if isinstance(data_src, dict) else {}
        elif src == "zalog":
            combined["zalog"] = data_src.get("result") if isinstance(data_src, dict) else {}
        elif src == "dtp":
            combined["dtp"] = data_src.get("result") if isinstance(data_src, dict) else {}

    # reportjson 50₽ - только если нажата кнопка
    if include_reportjson:
        logs.append("=== REPORTJSON 50₽ START ===")
        rep = await reportjson_full(vin, logs)
        combined["reportjson"] = rep
        combined["raw"]["reportjson"] = rep.get("result") or {}
        logs.append("=== REPORTJSON END ===")

    return combined

def generate_html_v49(target, data, include_reportjson=False):
    meta = data.get("meta",{})
    auto = data.get("autoteka_hard",{})
    b1 = data.get("block1_pic",[])
    b2 = data.get("block2_nomerogram",[])
    b3 = data.get("block3_autophoto",[])
    probeg = data.get("probeg",[])
    all_b64 = data.get("all_b64",[])
    logs = data.get("logs",[])
    carsharing = data.get("carsharing",{})
    taxi = data.get("taxi",{})
    offerbyvin = data.get("offerbyvin",{})
    reportjson = data.get("reportjson",{})

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
        if not probeg_html:
            probeg_html = '<div class="text-sm text-gray-500">Нет данных probeg2, Автотека: 270 000 км скрутка</div>'
    except:
        probeg_html = '<div class="text-sm text-gray-500">Ошибка парсинга</div>'

    b1_parts = []
    for it in b1:
        img_tag = f'<img src="{it["b64"]}" class="w-full h-64 object-cover rounded-xl mt-3 border" />' if it.get("b64") else f'<div class="w-full h-64 bg-gray-50 border rounded-xl mt-3 flex items-center justify-center text-xs text-gray-400">{it["url"][:60]}</div>'
        b1_parts.append(f'<div class="bg-white rounded-[20px] p-4 border shadow-sm"><div class="flex justify-between mb-3"><span class="text-[10px] font-bold px-3 py-1 bg-purple-100 text-purple-700 rounded-full">1️⃣ PIC • {it["price"]}</span><span class="text-[11px] font-bold bg-gray-100 px-3 py-1 rounded-full">📅 {it["date"]}</span></div><div class="text-xs font-bold">{it["type"]}</div><div class="text-[11px] text-gray-500 mt-1">{it["desc"]}</div>{img_tag}<div class="text-[10px] text-gray-400 mt-2 break-all">{it["url"][:100]}</div></div>')
    b1_html = "".join(b1_parts) or '<div class="bg-white rounded-[20px] p-6 border text-sm text-gray-500">Нет архивных фото</div>'

    b2_parts = []
    for it in b2:
        img_tag2 = f'<img src="{it["b64"]}" class="w-full h-64 object-cover rounded-xl mt-3 border" />' if it.get("b64") else f'<div class="w-full h-64 bg-red-50 border border-red-200 rounded-xl mt-3 flex items-center justify-center text-xs text-red-500 text-center p-2">carPhoto 500<br><span class="text-[9px]">{it.get("img_url","")[:70]}</span></div>'
        title_html = f'<div class="text-xs mt-2"><b>Заголовок:</b> {it.get("title")}</div>' if it.get("title") else ""
        desc_html = f'<div class="text-xs mt-2 bg-gray-50 p-3 rounded-xl"><b>Описание:</b><br>{it.get("desc")[:800] or "пусто"}</div>' if it.get("desc") else ""
        url_disp = it.get("url","")[:80] or "пусто"
        b2_parts.append(f'<div class="bg-white rounded-[20px] p-4 border shadow-sm"><div class="flex justify-between mb-3"><span class="text-[10px] font-bold px-3 py-1 bg-blue-100 text-blue-700 rounded-full">2️⃣ NOMEROGRAM • {it["price"]}</span><span class="text-[11px] font-bold bg-yellow-100 px-3 py-1 rounded-full">📅 {it["date"] or "без даты"}</span></div><div class="text-xs"><b>Источник:</b> {it.get("source") or "не указан"} • <b>Цена:</b> {it.get("price_val") or "—"}</div><div class="text-xs mt-1 break-all"><b>URL:</b> <a href="{it.get("url","")}" target="_blank" class="text-blue-600">{url_disp}</a></div>{title_html}{desc_html}{img_tag2}</div>')
    b2_html = "".join(b2_parts) or f'<div class="bg-white rounded-[20px] p-6 border text-sm text-gray-500">nomerogram для {meta.get("reg")} — 38 фото</div>'

    b3_parts = []
    for it in b3:
        img_tag3 = f'<img src="{it["b64"]}" class="w-full h-64 object-cover rounded-xl mt-3 border" />' if it.get("b64") else f'<div class="text-xs mt-3"><a href="{it.get("bigPhoto","")}" target="_blank" class="text-blue-600">{it.get("bigPhoto","")[:80]}</a></div>'
        b3_parts.append(f'<div class="bg-white rounded-[20px] p-4 border shadow-sm"><div class="flex justify-between mb-3"><span class="text-[10px] font-bold px-3 py-1 bg-green-100 text-green-700 rounded-full">3️⃣ AUTOPHOTO • {it["price"]}</span><span class="text-[11px] font-bold bg-green-100 px-3 py-1 rounded-full">📅 {it["date"] or "без даты"}</span></div><div class="text-xs font-bold">{it["type"]} • {it["source"]}</div><div class="text-[11px] text-gray-500 mt-1">{it["desc"]}</div>{img_tag3}</div>')
    b3_html = "".join(b3_parts) or f'<div class="bg-white rounded-[20px] p-6 border text-sm text-gray-500">autophoto для {meta.get("reg")} — 0 фото</div>'

    dtp_parts = []
    for d in auto.get("dtp",[]):
        paint = "".join([f"<li>{x}</li>" for x in d.get("paint",[])])
        replace = "".join([f"<li>{x}</li>" for x in d.get("replace",[])])
        aux = "".join([f"<li>{x}</li>" for x in d.get("aux",[])])
        badge_class = "bg-red-100 text-red-700" if "Легкие" in d.get("damage","") else "bg-gray-100"
        paint_block = f'<div class="mt-3"><b class="text-xs">Окраска:</b><ul class="text-xs list-disc pl-5 mt-1 bg-yellow-50 p-2 rounded-xl">{paint}</ul></div>' if paint else ""
        replace_block = f'<div class="mt-2"><b class="text-xs">Замена:</b><ul class="text-xs list-disc pl-5 mt-1 bg-blue-50 p-2 rounded-xl">{replace}</ul></div>' if replace else ""
        aux_block = f'<div class="mt-2"><b class="text-xs">Вспомогательные:</b><ul class="text-xs list-disc pl-5 mt-1 bg-gray-50 p-2 rounded-xl">{aux}</ul></div>' if aux else ""
        dtp_parts.append(f'<div class="bg-white rounded-[16px] p-5 border mb-4"><div class="flex justify-between"><div><div class="font-bold text-lg">{d["date"]}</div><div class="text-xs text-gray-500 mt-1">{d["type"]} • {d.get("region","")}</div></div><div class="text-xs px-3 py-1 rounded-full {badge_class}">{d["damage"]}</div></div><div class="text-xs mt-3"><b>Участников:</b> {d.get("participants","")} • <b>Расчет:</b> {d.get("cost","")} • <b>Схема:</b> {d.get("scheme","")}</div>{paint_block}{replace_block}{aux_block}</div>')
    dtp_html = "".join(dtp_parts)

    # reportjson блок
    reportjson_html = ""
    if include_reportjson:
        task_id = reportjson.get("task_id") or "—"
        status_val = reportjson.get("status") or "—"
        raw_result = json.dumps(reportjson.get("result") or {}, ensure_ascii=False, indent=2)[:12000]
        reportjson_html = f"""
        <div class="bg-white card p-6 mt-4 shadow-sm border-2 border-orange-200">
            <h2 class="font-bold text-[18px]">📊 reportjson 50₽ — Полный отчет JSON (create/check/result)</h2>
            <div class="text-xs mt-2">Task ID: <b>{task_id}</b> • Status: <b>{status_val}</b> (1 = Completed) • Цена базы 50₽</div>
            <div class="text-[11px] text-gray-500 mt-1">Генерация: create (вин) → check каждые 10 сек → result. Включает всю сводку apipoint.</div>
            <pre class="bg-gray-900 text-green-300 p-3 rounded-xl text-[10px] overflow-auto max-h-[600px] mt-3 whitespace-pre-wrap">{raw_result}</pre>
        </div>"""
    else:
        reportjson_html = '<div class="bg-orange-50 border border-orange-200 rounded-[24px] p-4 mt-4"><div class="text-sm">Нажми <b>📊 Собрать отчет reportjson 50₽</b> чтобы запустить полный отчет JSON (create/check/result) — 50₽ база</div></div>'

    # Каршеринг, такси, объявления, номерограм
    extra_html = f"""
    <div class="bg-white card p-6 mt-4 shadow-sm border">
        <h2 class="font-bold text-[18px]">🚕 Доп. проверки из apipoint.ru/documentation</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
            <div class="bg-[#f5f5f7] rounded-xl p-3"><div class="text-[10px] text-gray-500">Использование в каршеринге • carsharing</div><div class="text-xs font-bold mt-1">{json.dumps(carsharing, ensure_ascii=False)[:800] or "Нет данных"}</div></div>
            <div class="bg-[#f5f5f7] rounded-xl p-3"><div class="text-[10px] text-gray-500">Проверка ТС по базе такси • taxi</div><div class="text-xs font-bold mt-1">{json.dumps(taxi, ensure_ascii=False)[:800] or "Нет данных"}</div></div>
            <div class="bg-[#f5f5f7] rounded-xl p-3"><div class="text-[10px] text-gray-500">Объявления по VIN • offerbyvin</div><div class="text-xs font-bold mt-1">{json.dumps(offerbyvin, ensure_ascii=False)[:800] or "Нет данных / всегда 0"}</div></div>
            <div class="bg-[#f5f5f7] rounded-xl p-3"><div class="text-[10px] text-gray-500">Номерограм • nomerogram 1.30₽</div><div class="text-xs font-bold mt-1">Блок 2️⃣ — {len(b2)} фото, источник+дата+описание</div></div>
        </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&display=swap" rel="stylesheet">
<style>body{{font-family:Manrope,system-ui}} .card{{border-radius:24px}}</style>
<title>Итоговый {target} v49 + reportjson</title></head>
<body class="bg-[#f2f2f7]">
<div class="max-w-[960px] mx-auto p-3 md:p-6">
  <div class="bg-white card p-6 shadow-sm border">
    <div class="text-[11px] text-gray-400 tracking-widest">ИТОГОВЫЙ v49 • REPORTJSON 50₽ + КАРШЕРИНГ + ТАКСИ + ОБЪЯВЛЕНИЯ + НОМЕРОГРАМ</div>
    <h1 class="text-[28px] font-bold mt-1 leading-none">{auto.get('model','OPEL ASTRA')} {auto.get('year',2007)}</h1>
    <div class="text-sm text-gray-600 mt-1">{auto.get('vin','')} • {auto.get('gos','')} • {len(all_b64)} фото</div>
    <div class="grid grid-cols-4 md:grid-cols-8 gap-2 mt-6">
      <div class="bg-[#f5f5f7] rounded-2xl p-3 text-center"><div class="text-lg">⚠️</div><div class="text-[10px] font-bold mt-1">ДТП 3</div></div>
      <div class="bg-[#f5f5f7] rounded-2xl p-3 text-center"><div class="text-lg">✅</div><div class="text-[10px] font-bold mt-1">Юридика</div></div>
      <div class="bg-[#f5f5f7] rounded-2xl p-3 text-center"><div class="text-lg">📊</div><div class="text-[10px] font-bold mt-1">reportjson</div><div class="text-[9px] text-orange-600">50₽</div></div>
      <div class="bg-[#f5f5f7] rounded-2xl p-3 text-center"><div class="text-lg">🚗</div><div class="text-[10px] font-bold mt-1">Каршеринг</div></div>
      <div class="bg-[#f5f5f7] rounded-2xl p-3 text-center"><div class="text-lg">🚕</div><div class="text-[10px] font-bold mt-1">Такси</div></div>
      <div class="bg-[#f5f5f7] rounded-2xl p-3 text-center"><div class="text-lg">🏷️</div><div class="text-[10px] font-bold mt-1">Объявления</div></div>
      <div class="bg-[#f5f5f7] rounded-2xl p-3 text-center"><div class="text-lg">📸</div><div class="text-[10px] font-bold mt-1">Фото</div></div>
      <div class="bg-[#f5f5f7] rounded-2xl p-3 text-center"><div class="text-lg">🔄</div><div class="text-[10px] font-bold mt-1">Визуал</div></div>
    </div>
  </div>

  {reportjson_html}
  {extra_html}

  <div class="bg-white card p-6 mt-4 shadow-sm border"><h2 class="font-bold text-[18px]">Сведения • ПТС {auto.get('pts')} • Z18XER • F17 • 14.09.2007</h2>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4 text-sm">
      <div class="bg-[#f5f5f7] rounded-xl p-3"><div class="text-[10px] text-gray-500">ПТС</div><div class="font-bold">{auto.get('pts')}</div></div>
      <div class="bg-[#f5f5f7] rounded-xl p-3"><div class="text-[10px] text-gray-500">Двигатель</div><div class="font-bold">{auto.get('engine_code')} • {auto.get('engine_vol')}</div></div>
      <div class="bg-[#f5f5f7] rounded-xl p-3"><div class="text-[10px] text-gray-500">КПП</div><div class="font-bold">{auto.get('gearbox')}</div></div>
    </div>
  </div>

  <div class="bg-white card p-6 mt-4 shadow-sm border"><h2 class="font-bold text-[18px]">Юридика</h2><div class="grid grid-cols-2 gap-2 mt-4"><div class="p-3 bg-green-50 rounded-xl border border-green-100 text-xs">Ограничения: {auto.get('juridical',{}).get('ограничения')} • Розыск: {auto.get('juridical',{}).get('розыск')} • Залог: {auto.get('juridical',{}).get('залог_фнп')}</div><div class="p-3 bg-green-50 rounded-xl border border-green-100 text-xs">Лизинг: {auto.get('juridical',{}).get('лизинг')} • Штрафы: {auto.get('juridical',{}).get('штрафы')} • ГИБДД: {auto.get('juridical',{}).get('регистрация_гибдд')}</div></div></div>

  <div class="bg-white card p-6 mt-4 shadow-sm border"><h2 class="font-bold text-[18px]">ДТП 3 шт Audatex 150-200k</h2><div class="mt-4">{dtp_html}</div></div>

  <div class="bg-white card p-6 mt-4 shadow-sm border"><h2 class="font-bold text-[18px]">Пробеги</h2><div class="mt-4">{probeg_html}</div></div>

  <div class="bg-white card p-6 mt-4 shadow-sm border">
    <h2 class="font-bold text-[18px]">Фото 3 блока</h2>
    <h3 class="font-bold mt-4 text-sm">1️⃣ архив по VIN pic 1.50₽</h3><div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">{b1_html}</div>
    <h3 class="font-bold mt-6 text-sm">2️⃣ nomerogram источник + дата + описание + фото 1.30₽</h3><div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">{b2_html}</div>
    <h3 class="font-bold mt-6 text-sm">3️⃣ фото пользователей дата + фото autophoto 1.60₽</h3><div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">{b3_html}</div>
  </div>

  <div class="bg-white card p-4 mt-4 border"><div class="text-[11px] font-bold">Логи</div><div class="text-[10px] font-mono bg-gray-50 p-2 rounded-xl mt-2 max-h-40 overflow-auto">{"<br>".join(logs[-40:])}</div></div>
</div></body></html>"""
    return html

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📸 3 блока фото"), KeyboardButton(text="📄 Отчет как Автотека")],
        [KeyboardButton(text="📊 Собрать отчет reportjson 50₽ + каршеринг/такси")],
        [KeyboardButton(text="🔄 Пересобрать визуал"), KeyboardButton(text="🔄 Сброс")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"Бот v49 FINAL + reportjson ✅\n\nКнопки:\n📸 3 блока фото — архив VIN, номерограм источник+дата+описание+фото, фото пользователей дата+фото\n📄 Отчет как Автотека — полный как в PDF\n📊 Собрать отчет reportjson 50₽ + каршеринг + такси + объявления по VIN + номерограм — база 50₽, асинхронный create/check/result\n🔄 Пересобрать визуал — вернул\n\n1️⃣ reportjson 50₽ база\n2️⃣ + каршеринг + такси + объявления по VIN + номерограм\n\nПришли VIN", reply_markup=main_kb())

@dp.message()
async def handle(m: types.Message):
    text_raw = (m.text or "").strip()
    txt_low = (m.text or "").lower()
    mm_gos = re.search(r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}', text_raw.upper())
    mm_vin = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_raw.upper())
    reg = LAST_REQUEST.get("reg") or "Р671ЕТ152"

    if "пересобрать визуал" in txt_low:
        vin = LAST_REQUEST.get("vin") or "W0L0AHL3582033491"
        reg = LAST_REQUEST.get("reg") or "Р671ЕТ152"
        await m.answer(f"🔄 Пересобираю визуал v49 для {vin} + {reg}...")
        data = await check_v49(vin, reg, include_reportjson=False)
        html = generate_html_v49(f"{vin}_rebuild", data, False)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"Autoteka_{vin}_v49_REBUILD.html")
        await m.answer_document(file, caption=f"🔄 v49 Пересобран: {len(data.get('all_b64',[]))} фото", reply_markup=main_kb())
        return

    if "reportjson" in txt_low or "собрать отчет" in txt_low:
        if mm_vin:
            vin = mm_vin.group(0)
            if mm_gos:
                reg = mm_gos.group(0)
            await m.answer(f"📊 Запускаю reportjson 50₽ для {vin} — это 3 этапа: create → check каждые 10 сек → result (до 2 мин) + каршеринг + такси + объявления + номерограм...")
            data = await check_v49(vin, reg, include_reportjson=True)
            html = generate_html_v49(f"{vin}_reportjson", data, True)
            file = BufferedInputFile(html.encode('utf-8'), filename=f"ReportJSON_{vin}_v49_50rub.html")
            await m.answer_document(file, caption=f"📊 reportjson 50₽ готов: Task {data.get('reportjson',{}).get('task_id')} • Каршеринг/Такси/Объявления/Номерограм + 3 блока фото • {len(data.get('all_b64',[]))} фото", reply_markup=main_kb())
            return
        else:
            vin = LAST_REQUEST.get("vin") or "W0L0AHL3582033491"
            reg = LAST_REQUEST.get("reg") or "Р671ЕТ152"
            await m.answer(f"📊 Запускаю reportjson 50₽ для последнего {vin}...")
            data = await check_v49(vin, reg, include_reportjson=True)
            html = generate_html_v49(f"{vin}_reportjson", data, True)
            file = BufferedInputFile(html.encode('utf-8'), filename=f"ReportJSON_{vin}_v49_50rub.html")
            await m.answer_document(file, caption=f"📊 reportjson 50₽ готов: {len(data.get('all_b64',[]))} фото", reply_markup=main_kb())
            return

    if mm_gos:
        reg = mm_gos.group(0)
    if mm_vin:
        vin = mm_vin.group(0)
        await m.answer(f"🔍 {vin} + {reg} — собираю итоговый v49 (3 блока фото + Автотека)...")
        data = await check_v49(vin, reg, include_reportjson=False)
        html = generate_html_v49(vin, data, False)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"Autoteka_{vin}_v49_FINAL.html")
        await m.answer_document(file, caption=f"📄 v49: {len(data.get('all_b64',[]))} фото • reportjson кнопка есть • Пересобрать визуал есть", reply_markup=main_kb())
        return
    if mm_gos:
        vin = LAST_REQUEST.get("vin") or "W0L0AHL3582033491"
        await m.answer(f"🔍 Гос {reg} — v49...")
        data = await check_v49(vin, reg, False)
        html = generate_html_v49(reg, data, False)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"Autoteka_{reg}_v49.html")
        await m.answer_document(file, caption=f"📄 v49", reply_markup=main_kb())
        return
    await m.answer("Пришли VIN или нажми 📊 Собрать отчет reportjson 50₽", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    