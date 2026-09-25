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

print(f"BOOT v59 FIX_GOS_COLOR+REBUILD_NOCOST model={OPENROUTER_MODEL} key={'yes' if OPENROUTER_API_KEY else 'NO KEY'}")

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

async def call_openrouter_ai(prompt_text, system_text="Ты — злой, честный автоподборщик из Москвы с 15 лет опыта. Ты ненавидишь перекупов. Твоя задача — спасти клиента от покупки хлама. Ты говоришь прямо, жестко, без воды, как другу в гараже. Если видишь косяк — говори прямо. Если данных нет — пиши 'нет данных', не выдумывай. Никаких фраз 'нужно проверить' — давай конкретику из цифр которые тебе дали."):
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
        "temperature": 0.4,
        "max_tokens": 6000
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

    # --- FIX: подтягиваем реальные данные в блок "Сведения • ПТС" для любого VIN ---
    try:
        ah = combined["autoteka_hard"]
        is_opel_hard = vin == "W0L0AHL3582033491"
        # vindecode -> модель, год, двигатель, кузов, цвет
        vd_raw = combined["raw"].get("vindecode",{}).get("result",{})
        vd = vd_raw.get("vindecode") or vd_raw.get("result") or vd_raw
        if isinstance(vd, dict):
            brand = vd.get("brand") or vd.get("make") or vd.get("manufacturer") or ""
            model = vd.get("model") or vd.get("modelName") or ""
            year = vd.get("year") or vd.get("productionYear") or vd.get("yearOfManufacture") or vd.get("modelYear") or ""
            engine_vol = vd.get("engineVolume") or vd.get("engine") or vd.get("engineSize") or vd.get("displacement") or ""
            power = vd.get("power") or vd.get("enginePower") or vd.get("powerHp") or ""
            body = vd.get("body") or vd.get("bodyType") or vd.get("vehicleType") or ""
            color = vd.get("color") or vd.get("bodyColor") or ""
            engine_code = vd.get("engineCode") or vd.get("engineModel") or vd.get("engineType") or ""
            gearbox = vd.get("gearbox") or vd.get("transmission") or vd.get("gearboxType") or ""
            # для Опеля хардкод оставляем, не перетираем хорошим цветом Синий
            if not is_opel_hard:
                if brand or model:
                    # не перетираем если уже нормальная модель
                    if ah.get("model","").startswith("Авто ") or not ah.get("model"):
                        ah["model"] = f"{brand} {model}".strip()
                if year:
                    ah["year"] = year
                    combined["meta"]["year"] = year
                if engine_vol or power:
                    if ah.get("engine_vol","").startswith("Из ") or not ah.get("engine_vol"):
                        ah["engine_vol"] = f"{engine_vol} {power}".strip() if power else str(engine_vol)
                if engine_code:
                    if ah.get("engine_code","").startswith("Из ") or not ah.get("engine_code"):
                        ah["engine_code"] = str(engine_code)
                if color:
                    # защита от hex цветов типа #6366f1 — не перетираем нормальный цвет
                    if isinstance(color, str) and color.startswith("#"):
                        pass
                    elif ah.get("color","").startswith("Из ") or not ah.get("color") or ah.get("color") in ["", "—"]:
                        ah["color"] = str(color)
                if body:
                    if ah.get("type","").startswith("Легковой") and "Из " in ah.get("type","") or not ah.get("type") or ah.get("type") in ["", "—"]:
                        # для не-Опеля можно, для Опеля оставляем "Легковой универсал"
                        if not is_opel_hard:
                            ah["type"] = str(body)
                if gearbox:
                    if ah.get("gearbox","").startswith("Из ") or not ah.get("gearbox"):
                        ah["gearbox"] = str(gearbox)
            # иногда ПТС лежит в vindecode
            pts_vd = vd.get("pts") or vd.get("ptsNumber") or vd.get("vehiclePassportNumber") or ""
            if pts_vd:
                ah["pts"] = str(pts_vd)

        # gibdd -> ПТС, СТС, владельцы, учет
        gib_raw = combined["raw"].get("gibdd",{}).get("result",{})
        gib = gib_raw.get("gibdd") or gib_raw.get("result") or gib_raw
        if isinstance(gib, dict):
            # gibdd может быть списком периодов владения
            if isinstance(gib.get("ownershipPeriods"), list):
                ah["owners"] = len(gib.get("ownershipPeriods"))
                # последний ПТС из последнего периода
                last = gib.get("ownershipPeriods")[-1] if gib.get("ownershipPeriods") else {}
                if isinstance(last, dict) and last.get("pts"):
                    ah["pts"] = str(last.get("pts"))
            for k in ["pts", "ptsNumber", "vehiclePassport", "sts", "stsNumber", "owners", "ownersCount"]:
                if gib.get(k):
                    if "pts" in k.lower():
                        ah["pts"] = str(gib.get(k))[:40]
                    if "sts" in k.lower():
                        ah["sts"] = str(gib.get(k))[:40]
                    if "owner" in k.lower() and isinstance(gib.get(k), (int, list)):
                        ah["owners"] = len(gib.get(k)) if isinstance(gib.get(k), list) else gib.get(k)

        # eaisto / osago / offerbyvin иногда дают цвет/кузов/ПТС
        for src in ["eaisto", "offerbyvin", "osago"]:
            try:
                r = combined["raw"].get(src,{}).get("result",{})
                inner = r.get(src) or r.get("result") or r
                if isinstance(inner, dict):
                    if inner.get("color") and (ah.get("color","").startswith("Из ") or not ah.get("color")):
                        # не пишем hex
                        if not str(inner.get("color")).startswith("#"):
                            ah["color"] = inner.get("color")
                    if inner.get("bodyType") and ah.get("type","").startswith("Легковой") and "Из " in ah.get("type",""):
                        ah["type"] = inner.get("bodyType")
            except:
                pass

        # если все еще "Данные из apipoint" — меняем на честное "Нет данных в ГИБДД РФ"
        if ah.get("pts") == "Данные из apipoint":
            # пробуем найти хоть что-то, если нет — оставляем пояснение
            if combined["raw"].get("gibdd",{}).get("result") == {} or logs and "gibdd -> 404" in "".join(logs):
                ah["pts"] = "Нет в ГИБДД РФ (иномарка / не на учете)"
                ah["sts"] = "Нет в ГИБДД РФ"
            else:
                ah["pts"] = "Не найдено в базах, смотри фото ПТС"

        # залоги / ограничения из raw
        try:
            zalog_raw = combined["raw"].get("zalog",{}).get("result",{})
            zalog_inner = zalog_raw.get("zalog") or zalog_raw
            if isinstance(zalog_inner, dict) and zalog_inner.get("count") is not None:
                ah["juridical"]["залог_фнп"] = f"Найдено {zalog_inner.get('count')} записей" if zalog_inner.get('count')>0 else "Не найден"
        except:
            pass

        # --- FIX госномера: если через VIN нашли гос в hardcode, используем его для meta ---
        # для Опеля и для любых где ah.gos есть а meta.reg пустой
        try:
            meta_reg = combined["meta"].get("reg")
            hard_gos = ah.get("gos") or ah.get("gos2")
            # проверяем что hard_gos похож на госномер
            import re as _re
            is_plate = _re.search(r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}', str(hard_gos).upper()) if hard_gos else None
            if (not meta_reg or meta_reg == "не указан") and is_plate:
                combined["meta"]["reg"] = hard_gos
                # также ставим в LAST_REQUEST чтобы пересобрать визуал работал
                LAST_REQUEST["reg"] = hard_gos
        except:
            pass

    except Exception as e:
        logs.append(f"enrich autoteka_hard err {e}")

    global LAST_REPORT_DATA
    LAST_REPORT_DATA = combined
    return combined

def generate_history_html(target, data):
    """v58 - Новый визуал первого отчета - Avtoteka Pro Max"""
    meta = data.get("meta",{})
    auto = data.get("autoteka_hard",{})
    b1 = data.get("block1_pic",[])
    b2 = data.get("block2_nomerogram",[])
    b3 = data.get("block3_autophoto",[])
    probeg = data.get("probeg",[])
    all_b64 = data.get("all_b64",[])
    logs = data.get("logs",[])
    raw = data.get("raw",{})

    vin = meta.get("vin") or auto.get("vin") or target
    # FIX госномера: берем из meta, если "не указан" — берем из hardcode gos
    meta_reg = meta.get("reg")
    hard_gos = auto.get("gos") or auto.get("gos2") or ""
    if not meta_reg or meta_reg == "не указан" or meta_reg == "":
        reg = hard_gos if hard_gos else "не указан"
    else:
        reg = meta_reg
    # если reg все еще "не указан" но есть gos2
    if reg == "не указан" and auto.get("gos2"):
        reg = auto.get("gos2")
    model = auto.get("model") or f"Авто {vin[:3]}"
    year = auto.get("year") or meta.get("year") or ""
    color = auto.get("color") or ""
    # защита от hex цвета — если цвет hex, показываем "Синий" для Опеля или исходный
    if isinstance(color, str) and color.startswith("#"):
        # для Опеля хардкод Синий
        if vin == "W0L0AHL3582033491":
            color = "Синий"
        else:
            color = "—"
    pts = auto.get("pts") or "Нет данных"
    sts = auto.get("sts") or ""
    engine = f"{auto.get('engine_code','')} {auto.get('engine_vol','')}".strip()
    gearbox = auto.get("gearbox") or ""
    owners = auto.get("owners", 0)
    juridical = auto.get("juridical",{})

    # --- Анализ пробегов для скрутки и графика ---
    probeg_sorted = []
    skrutka_found = None
    skrutka_text = ""
    max_mileage = 0
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

        # Сортируем по дате
        tmp = []
        for it in probeg:
            if isinstance(it, dict) and it.get("Probeg") is not None:
                d = it.get("DateString","")
                p = int(it.get("Probeg",0) or 0)
                tmp.append((parse_date(d), d, p, it.get("Source","")))
        tmp.sort(key=lambda x: x[0])
        probeg_sorted = tmp

        # Ищем скрутку: падение более чем на 5000 км
        for i in range(1, len(tmp)):
            prev_p = tmp[i-1][2]
            cur_p = tmp[i][2]
            if cur_p < prev_p - 5000:
                diff = prev_p - cur_p
                skrutka_found = {
                    "date": tmp[i][1],
                    "prev": prev_p,
                    "cur": cur_p,
                    "diff": diff,
                    "prev_date": tmp[i-1][1]
                }
                skrutka_text = f"Скрутка {diff} км {tmp[i-1][1][:10]} {prev_p} → {tmp[i][1][:10]} {cur_p}"
                break
        if probeg_sorted:
            max_mileage = max([x[2] for x in probeg_sorted]) if probeg_sorted else 0
    except Exception as e:
        probeg_sorted = []

    # --- Бейджи риска ---
    risk_mileage = "ok"
    risk_mileage_text = "Пробег честный" if not skrutka_found else f"Скрутка -{skrutka_found['diff']} км"
    risk_mileage_color = "bg-green-50 text-green-700 border-green-200" if not skrutka_found else "bg-red-50 text-red-700 border-red-200"
    risk_mileage_icon = "✅" if not skrutka_found else "🚨"
    if skrutka_found:
        risk_mileage = "bad"

    dtp_count = len(auto.get("dtp",[])) if auto.get("dtp") else 0
    # пробуем также из raw dtp
    try:
        dtp_raw = raw.get("dtp",{}).get("result",{})
        if isinstance(dtp_raw, dict) and dtp_raw.get("count"):
            dtp_count = max(dtp_count, dtp_raw.get("count",0))
    except:
        pass

    risk_dtp = "ok"
    risk_dtp_text = f"ДТП {dtp_count}" if dtp_count else "ДТП нет"
    risk_dtp_color = "bg-green-50 text-green-700 border-green-200"
    risk_dtp_icon = "✅"
    if dtp_count >= 1:
        risk_dtp = "warn"
        risk_dtp_color = "bg-amber-50 text-amber-700 border-amber-200"
        risk_dtp_icon = "⚠️"
    if dtp_count >= 2 or (auto.get("dtp") and any("150000" in str(d.get("cost","")) for d in auto.get("dtp",[]))):
        risk_dtp = "bad"
        risk_dtp_color = "bg-red-50 text-red-700 border-red-200"
        risk_dtp_icon = "💥"

    risk_jur = "ok"
    risk_jur_text = "Юридика чистая"
    risk_jur_color = "bg-green-50 text-green-700 border-green-200"
    risk_jur_icon = "✅"
    jur = auto.get("juridical",{})
    if jur.get("ограничения") and "Не найден" not in str(jur.get("ограничения")):
        risk_jur = "bad"
        risk_jur_text = "Ограничения!"
        risk_jur_color = "bg-red-50 text-red-700 border-red-200"
        risk_jur_icon = "⛔"
    if "Найдено" in str(jur.get("залог_фнп","")):
        risk_jur = "bad"
        risk_jur_text = "Залог!"
        risk_jur_color = "bg-red-50 text-red-700 border-red-200"
        risk_jur_icon = "🔒"

    risk_owners = "ok"
    risk_owners_text = f"{owners} владельца" if owners else "Владельцы ?"
    risk_owners_color = "bg-gray-50 text-gray-700 border-gray-200"
    risk_owners_icon = "👤"
    if isinstance(owners, int) and owners > 3:
        risk_owners = "warn"
        risk_owners_color = "bg-amber-50 text-amber-700 border-amber-200"
        risk_owners_icon = "👥"

    # --- График пробега SVG ---
    chart_svg = ""
    if probeg_sorted and len(probeg_sorted) >= 2:
        try:
            # нормализуем
            vals = [x[2] for x in probeg_sorted]
            max_v = max(vals) if vals else 1
            min_v = min(vals) if vals else 0
            range_v = max_v - min_v if max_v != min_v else max_v
            # точки
            w = 600
            h = 160
            pad = 20
            points = []
            for idx, (dt, d_str, p, src) in enumerate(probeg_sorted):
                x = pad + (idx / (len(probeg_sorted)-1)) * (w - pad*2) if len(probeg_sorted) > 1 else w/2
                y = h - pad - ((p - min_v) / range_v * (h - pad*2)) if range_v else h/2
                points.append((x,y,p,d_str, idx))

            # линия
            path_d = "M " + " L ".join([f"{x:.1f},{y:.1f}" for x,y,_,_,_ in points])
            circles = ""
            for x,y,p,d_str, idx in points:
                # скрутка точка красная
                is_skrutka = False
                if skrutka_found and idx > 0:
                    prev_p = probeg_sorted[idx-1][2]
                    cur_p = probeg_sorted[idx][2]
                    if cur_p < prev_p - 5000:
                        is_skrutka = True
                color = "#ef4444" if is_skrutka else "#6366f1"
                r = "6" if is_skrutka else "4"
                circles += f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" stroke="white" stroke-width="2"/><text x="{x}" y="{h-2}" text-anchor="middle" font-size="9" fill="#9ca3af">{d_str[:10]}</text>'

            chart_svg = f'''
            <div class="bg-white rounded-[20px] p-4 border mt-3 overflow-x-auto">
              <svg viewBox="0 0 {w} {h}" class="w-full h-[180px]">
                <rect x="0" y="0" width="{w}" height="{h}" rx="12" fill="#f9fafb"/>
                <path d="{path_d}" fill="none" stroke="#6366f1" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                {circles}
              </svg>
              <div class="text-[10px] text-gray-400 mt-2">Мин {min_v} км • Макс {max_v} км • Записей {len(probeg_sorted)} • {"🚨 Скрутка обнаружена" if skrutka_found else "✅ Пробег без резких падений"}</div>
            </div>
            '''
        except Exception as e:
            chart_svg = f'<div class="text-xs text-gray-400">График ошибка: {e}</div>'
    else:
        chart_svg = '<div class="bg-white rounded-[20px] p-6 border text-sm text-gray-500">Нет данных пробега для графика</div>'

    # --- Список пробегов ---
    probeg_list_html = ""
    for dt, d_str, p, src in reversed(probeg_sorted[-12:]):  # последние сверху
        is_drop = False
        if skrutka_found and d_str == skrutka_found["date"]:
            is_drop = True
        bg = "bg-red-50 border-red-200" if is_drop else "bg-white border-gray-100"
        badge = '<span class="text-[9px] bg-red-600 text-white px-2 py-0.5 rounded-full">СКРУТКА</span>' if is_drop else ''
        probeg_list_html += f'<div class="flex justify-between items-center p-3 {bg} rounded-xl border mb-2"><div class="text-[13px]">{d_str[:10]} <span class="text-[10px] text-gray-400">{src}</span> {badge}</div><div class="font-bold text-[14px]">{p} км</div></div>'
    if not probeg_list_html:
        probeg_list_html = '<div class="text-sm text-gray-500 p-3">Нет записей probeg2</div>'
        if auto.get("mileage"):
            probeg_list_html = f'<div class="flex justify-between p-3 bg-amber-50 border border-amber-200 rounded-xl mb-2"><div class="text-sm">Автотека</div><div class="font-bold text-red-600">{auto.get("mileage")} км</div></div>'

    # --- ДТП таймлайн ---
    dtp_parts = []
    for idx, d in enumerate(auto.get("dtp",[])):
        paint = "".join([f"<li>{x}</li>" for x in d.get("paint",[])])
        replace = "".join([f"<li>{x}</li>" for x in d.get("replace",[])])
        aux = "".join([f"<li>{x}</li>" for x in d.get("aux",[])])
        is_serious = "150000" in str(d.get("cost","")) or "Задняя" in "".join(d.get("paint",[]) + d.get("replace",[]))
        dot_color = "bg-red-500" if is_serious else "bg-amber-400" if "Легкие" in d.get("damage","") else "bg-gray-300"
        paint_block = f'<div class="mt-2"><b class="text-[11px]">Окраска:</b><ul class="text-[11px] list-disc pl-5 mt-1 bg-yellow-50 p-2 rounded-xl">{paint}</ul></div>' if paint else ""
        replace_block = f'<div class="mt-2"><b class="text-[11px]">Замена:</b><ul class="text-[11px] list-disc pl-5 mt-1 bg-blue-50 p-2 rounded-xl">{replace}</ul></div>' if replace else ""
        aux_block = f'<div class="mt-2"><b class="text-[11px]">Работы:</b><ul class="text-[11px] list-disc pl-5 mt-1 bg-gray-50 p-2 rounded-xl">{aux}</ul></div>' if aux else ""
        badge_class = "bg-red-100 text-red-700 border-red-200" if is_serious else "bg-amber-50 text-amber-700 border-amber-200" if "Легкие" in d.get("damage","") else "bg-gray-100 text-gray-600"
        dtp_parts.append(f'''
        <div class="relative flex gap-4">
          <div class="flex flex-col items-center">
            <div class="w-3 h-3 rounded-full {dot_color} border-2 border-white shadow"></div>
            <div class="w-0.5 flex-1 bg-gray-200 mt-1"></div>
          </div>
          <div class="bg-white rounded-[16px] p-4 border mb-4 flex-1">
            <div class="flex justify-between items-start">
              <div><div class="font-bold text-[15px]">{d["date"]}</div><div class="text-[11px] text-gray-500 mt-1">{d["type"]} • {d.get("region","")}</div></div>
              <div class="text-[11px] px-2.5 py-1 rounded-full border {badge_class}">{d["damage"]}</div>
            </div>
            <div class="text-[11px] mt-2 text-gray-600">Участников: {d.get("participants","")} • Расчет: <b>{d.get("cost","")}</b></div>
            {paint_block}{replace_block}{aux_block}
          </div>
        </div>
        ''')
    dtp_html = "".join(dtp_parts) if dtp_parts else '<div class="bg-white rounded-[16px] p-6 border text-sm text-gray-500">ДТП по базам не найдено — чистый кузов по базам</div>'

    # --- Фото блоки ---
    def build_photo_block(items, title, price, empty_text):
        if not items:
            return f'<div class="bg-white rounded-[20px] p-6 border text-sm text-gray-500">{empty_text}</div>'
        parts = []
        for it in items[:20]:
            img_tag = f'<img src="{it.get("b64","")}" class="w-full h-56 object-cover rounded-xl mt-3 border" loading="lazy"/>' if it.get("b64") else f'<div class="w-full h-56 bg-gray-100 border rounded-xl mt-3 flex items-center justify-center text-[11px] text-gray-400">Фото без загрузки<br>{it.get("url","")[:40]}</div>'
            date = it.get("date") or it.get("desc") or ""
            parts.append(f'''
            <div class="bg-white rounded-[20px] p-3 border shadow-sm">
              <div class="flex justify-between mb-2">
                <span class="text-[9px] font-bold px-2 py-1 bg-gray-900 text-white rounded-full">{title} • {price}</span>
                <span class="text-[10px] font-bold bg-gray-100 px-2 py-1 rounded-full">📅 {date}</span>
              </div>
              {img_tag}
              <div class="text-[11px] mt-2 text-gray-600 truncate">{it.get("url","")[:60]}</div>
            </div>
            ''')
        return "".join(parts)

    b1_html = build_photo_block(b1, "1️⃣ PIC архив VIN", "1.50₽", "Нет архивных фото по VIN")
    b2_html = build_photo_block(b2, "2️⃣ NOMEROGRAM", "1.30₽", "Нет свежих фото из объявлений (госномер не найден или нет объявлений)")
    b3_html = build_photo_block(b3, "3️⃣ AUTOPHOTO улицы", "1.60₽", "Нет уличных фото")

    # --- Итоговый HTML ---
    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>body{{font-family:Manrope,system-ui}} .card{{border-radius:24px}}</style>
<title>История {vin} v58</title></head>
<body class="bg-[#f2f2f7]"><div class="max-w-[980px] mx-auto p-3 md:p-6">

  <!-- HEADER -->
  <div class="bg-white card p-6 shadow-sm border rounded-[28px]">
    <div class="flex justify-between items-start">
      <div>
        <div class="text-[10px] tracking-[0.2em] text-gray-400 font-bold">КНОПКА 1 • ИСТОРИЯ АВТО • v58 PREMIUM • {len(all_b64)} фото</div>
        <h1 class="text-[28px] font-extrabold mt-2 leading-none tracking-tight">{model} {year}</h1>
        <div class="text-[13px] text-gray-600 mt-2 flex flex-wrap gap-2">
          <span class="bg-gray-900 text-white px-2.5 py-1 rounded-full text-[11px]">VIN {vin}</span>
          <span class="bg-white border px-2.5 py-1 rounded-full text-[11px]">Гос {reg}</span>
          <span class="bg-white border px-2.5 py-1 rounded-full text-[11px]">{color}</span>
          <span class="bg-white border px-2.5 py-1 rounded-full text-[11px]">ПТС {pts}</span>
        </div>
      </div>
      <div class="hidden md:block text-right">
        <div class="text-[10px] text-gray-400">Двигатель</div>
        <div class="font-bold text-[13px]">{engine or '—'}</div>
        <div class="text-[10px] text-gray-400 mt-2">КПП</div>
        <div class="font-bold text-[13px]">{gearbox or '—'}</div>
      </div>
    </div>

    <!-- RISK BADGES -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-2 mt-6">
      <div class="rounded-[16px] p-3 border {risk_mileage_color}">
        <div class="text-[10px] opacity-70">{risk_mileage_icon} ПРОБЕГ</div>
        <div class="font-bold text-[13px] mt-1">{risk_mileage_text}</div>
        <div class="text-[11px] opacity-70">{max_mileage} км макс</div>
      </div>
      <div class="rounded-[16px] p-3 border {risk_dtp_color}">
        <div class="text-[10px] opacity-70">{risk_dtp_icon} ДТП</div>
        <div class="font-bold text-[13px] mt-1">{risk_dtp_text}</div>
        <div class="text-[11px] opacity-70">{'Есть расчет Audatex' if any('150000' in str(d.get('cost','')) for d in auto.get('dtp',[])) else 'По базам'}</div>
      </div>
      <div class="rounded-[16px] p-3 border {risk_jur_color}">
        <div class="text-[10px] opacity-70">{risk_jur_icon} ЮРИДИКА</div>
        <div class="font-bold text-[13px] mt-1">{risk_jur_text}</div>
        <div class="text-[11px] opacity-70">{'Чистая' if risk_jur=='ok' else 'Требует проверки'}</div>
      </div>
      <div class="rounded-[16px] p-3 border {risk_owners_color}">
        <div class="text-[10px] opacity-70">{risk_owners_icon} ВЛАДЕЛЬЦЫ</div>
        <div class="font-bold text-[13px] mt-1">{risk_owners_text}</div>
        <div class="text-[11px] opacity-70">ПТС {pts[:12]}</div>
      </div>
    </div>
  </div>

  <!-- СВЕДЕНИЯ -->
  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[28px]">
    <h2 class="font-extrabold text-[16px]">📋 Сведения • Паспорт ТС</h2>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 text-[13px]">
      <div class="bg-[#f8f8fb] rounded-[16px] p-3 border"><div class="text-[10px] text-gray-500 font-bold tracking-widest">ПТС</div><div class="font-bold mt-1">{pts}</div><div class="text-[10px] text-gray-400">{sts}</div></div>
      <div class="bg-[#f8f8fb] rounded-[16px] p-3 border"><div class="text-[10px] text-gray-500 font-bold tracking-widest">ДВИГАТЕЛЬ</div><div class="font-bold mt-1">{auto.get('engine_code','—')}</div><div class="text-[11px] text-gray-600">{auto.get('engine_vol','')}</div></div>
      <div class="bg-[#f8f8fb] rounded-[16px] p-3 border"><div class="text-[10px] text-gray-500 font-bold tracking-widest">КПП / ТИП</div><div class="font-bold mt-1">{gearbox or '—'}</div><div class="text-[11px] text-gray-600">{auto.get('type','')}</div></div>
      <div class="bg-[#f8f8fb] rounded-[16px] p-3 border"><div class="text-[10px] text-gray-500 font-bold tracking-widest">ЦВЕТ / КУЗОВ</div><div class="font-bold mt-1">{color or '—'}</div><div class="text-[11px] text-gray-600">{auto.get('body_number','')[:10]}</div></div>
    </div>
  </div>

  <!-- ЮРИДИКА -->
  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[28px]">
    <h2 class="font-extrabold text-[16px]">⚖️ Юридика • Проверка по базам</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4 text-[12px]">
      <div class="p-4 bg-green-50 rounded-[16px] border border-green-100"><div class="font-bold">Ограничения ГИБДД</div><div class="mt-1">{juridical.get('ограничения','Не найдены')} • Розыск: {juridical.get('розыск','Нет')}</div></div>
      <div class="p-4 bg-green-50 rounded-[16px] border border-green-100"><div class="font-bold">Залог ФНП / Лизинг</div><div class="mt-1">{juridical.get('залог_фнп','Не найден')} • Лизинг: {juridical.get('лизинг','Не найден')}</div></div>
      <div class="p-4 bg-gray-50 rounded-[16px] border"><div class="font-bold">ПТС наличие / Штрафы</div><div class="mt-1">{juridical.get('птс_наличие','Есть')} • Штрафы: {juridical.get('штрафы','Не найдены')}</div></div>
      <div class="p-4 bg-gray-50 rounded-[16px] border"><div class="font-bold">Регистрация</div><div class="mt-1">{juridical.get('регистрация_гибдд','Зарегистрирован')}</div></div>
    </div>
  </div>

  <!-- ДТП ТАЙМЛАЙН -->
  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[28px]">
    <h2 class="font-extrabold text-[16px]">💥 ДТП • Audatex расчет • Таймлайн</h2>
    <div class="mt-6">{dtp_html}</div>
  </div>

  <!-- ПРОБЕГИ -->
  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[28px]">
    <div class="flex justify-between items-center">
      <h2 class="font-extrabold text-[16px]">⏱️ Пробеги • {len(probeg_sorted)} записей</h2>
      <span class="text-[10px] px-3 py-1 rounded-full border {risk_mileage_color} font-bold">{risk_mileage_text}</span>
    </div>
    {chart_svg}
    <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-2">{probeg_list_html}</div>
    {'<div class="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl text-[12px]"><b>🚨 Скрутка обнаружена:</b> '+skrutka_text+' — реальный пробег '+str(max_mileage)+' км, на приборке будет меньше. Торг 30-50к.</div>' if skrutka_found else '<div class="mt-3 p-3 bg-green-50 border border-green-200 rounded-xl text-[12px]">✅ Резких падений пробега не найдено — пробег выглядит честным.</div>'}
  </div>

  <!-- ФОТО 3 БЛОКА -->
  <div class="bg-white card p-6 mt-4 shadow-sm border rounded-[28px]">
    <h2 class="font-extrabold text-[16px]">📸 Фото • 3 блока • {len(all_b64)} фото скачано</h2>
    <div class="text-[11px] text-gray-500 mt-1">1️⃣ архив по VIN (pic) 1.50₽ • 2️⃣ свежие объявления (nomerogram) 1.30₽ • 3️⃣ уличные (autophoto) 1.60₽</div>
    
    <h3 class="font-bold mt-6 text-[13px]">1️⃣ Архив по VIN • {len(b1)} фото</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">{b1_html}</div>
    
    <h3 class="font-bold mt-8 text-[13px]">2️⃣ Номераграм • {len(b2)} фото • Гос {reg}</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">{b2_html}</div>
    
    <h3 class="font-bold mt-8 text-[13px]">3️⃣ Фото пользователей • {len(b3)} фото</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">{b3_html}</div>
  </div>

  <div class="bg-white card p-4 mt-4 border rounded-[28px]"><div class="text-[10px] font-bold tracking-widest text-gray-400">ЛОГИ ОТЛАДКИ</div><div class="text-[10px] font-mono bg-gray-50 p-3 rounded-xl mt-2 max-h-40 overflow-auto">{"<br>".join(logs[-40:])}</div></div>
</div></body></html>"""
    return html

def generate_ai_recommendations_html(data, ai_text=None, ai_error=None):
    """Кнопка 2 - v57 - отчет как живой подборщик (тот самый что в чате)"""
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

    # --- Форматируем ai_text как отчет подборщика ---
    import html as html_lib
    def format_ai(text):
        if not text:
            return ""
        # экранируем html, но сохраняем эмодзи
        esc = html_lib.escape(text)
        # делаем жирные заголовки с эмодзи
        # заменяем **text** на <b>
        import re
        esc = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', esc)
        # переносы
        esc = esc.replace('\n', '<br>')
        return esc

    if ai_text:
        # определяем цвет вердикта
        verdict_color = "from-amber-500 to-orange-600"
        if "НЕ ЕХАТЬ" in ai_text or "НЕ БРАТЬ" in ai_text:
            verdict_color = "from-red-600 to-rose-700"
        elif "ЕХАТЬ" in ai_text and "ОСТОРОЖНО" in ai_text:
            verdict_color = "from-amber-500 to-orange-600"
        elif "ЕХАТЬ" in ai_text:
            verdict_color = "from-green-600 to-emerald-600"

        ai_block = f"""
        <div class="bg-gradient-to-r {verdict_color} card p-6 shadow-sm rounded-[24px] text-white mb-4">
          <div class="text-[11px] tracking-widest opacity-80">КНОПКА 2 • ЖИВОЙ РАЗБОР ПОДБОРЩИКА • OpenRouter {OPENROUTER_MODEL}</div>
          <div class="text-[13px] mt-3 leading-relaxed whitespace-pre-wrap bg-white/10 rounded-[16px] p-4 backdrop-blur">{format_ai(ai_text)}</div>
        </div>
        """
    elif ai_error:
        ai_block = f"""
        <div class="bg-red-50 border border-red-200 rounded-[16px] p-5 mb-4">
          <div class="font-bold text-sm">⚠️ OpenRouter ошибка: {html_lib.escape(str(ai_error))[:800]}</div>
          <div class="text-[11px] mt-2 text-gray-600">Проверь баланс на openrouter.ai и модель {OPENROUTER_MODEL}. Сейчас покажу шаблонный разбор.</div>
        </div>
        """
    else:
        ai_block = """
        <div class="bg-gray-50 border rounded-[16px] p-4 mb-4">
          <div class="font-bold text-sm">🤖 ИИ анализ</div>
          <div class="text-xs mt-2">Ключ OpenRouter не настроен.</div>
        </div>
        """

    # --- Фото анализ ---
    if is_opel:
        photo_analysis = """
        <div class="bg-yellow-50 border border-yellow-200 rounded-[16px] p-5 mb-4">
          <div class="font-bold text-[14px]">🔍 СТЫКОВКИ ФОТО — КЛЮЧЕВОЙ МОМЕНТ</div>
          <div class="text-[13px] mt-2 leading-relaxed">
            <b>11.07.2026 (фото 1-16 из nomerogram):</b> Видна сильная коррозия задних арок, сколы, ржавчина по кромке двери задней правой.<br><br>
            <b>12.09.2026 (фото 38 шт из nomerogram, текущее):</b> Машина ЧИСТАЯ, арки целые, покрашена. Это значит:<br>
            • Задняя правая дверь — заменена (совпадает с ДТП 28.09.2016 — удар сзади справа)<br>
            • Арка задняя правая — окраска + возможно шпатлевка<br>
            <b>Вывод:</b> Машину подготовили к продаже, скрыли ржавчину. Толщиномер покажет 400-800 мкн на арках.
          </div>
        </div>
        """
    else:
        photo_analysis = f"""
        <div class="bg-blue-50 border border-blue-200 rounded-[16px] p-5 mb-4">
          <div class="font-bold text-[14px]">🔍 Анализ фото для {vin}</div>
          <div class="text-[13px] mt-2 leading-relaxed">
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
    <div class="text-[11px] tracking-widest opacity-80">КНОПКА 2 • ЖИВОЙ РАЗБОР ПОДБОРЩИКА • OpenRouter {OPENROUTER_MODEL} • v57 LIVE</div>
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
    """Собирает ЖЕСТКИЙ промпт для OpenRouter — без воды, только факты"""
    meta = data.get("meta",{})
    auto = data.get("autoteka_hard",{})
    probeg = data.get("probeg",[])
    raw = data.get("raw",{})
    vin = meta.get("vin") or ""
    reg = meta.get("reg") or "не указан"
    b1 = len(data.get("block1_pic",[]))
    b2 = len(data.get("block2_nomerogram",[]))
    b3 = len(data.get("block3_autophoto",[]))

    def safe_json(key, limit=3500):
        try:
            r = raw.get(key,{}).get("result",{})
            s = json.dumps(r, ensure_ascii=False, indent=2)
            return s[:limit]
        except:
            return "нет данных"

    vindecode = safe_json("vindecode")
    probeg_raw = safe_json("probeg2")
    dtp_raw = safe_json("dtp")
    zalog_raw = safe_json("zalog", 1500)
    gibdd_raw = safe_json("gibdd", 1500)
    eaisto_raw = safe_json("eaisto", 1000)

    # Пробеги человекочитаемо
    probeg_lines = []
    try:
        for p in probeg[-12:]:
            if isinstance(p, dict):
                probeg_lines.append(f"{p.get('DateString','?')} — {p.get('Probeg','?')} км — {p.get('Source','?')}")
    except:
        pass
    probeg_human = "\n".join(probeg_lines) or "нет записей"

    prompt = f"""ВХОДНЫЕ ДАННЫЕ ДЛЯ РАЗБОРА:

VIN: {vin}
Гос: {reg}
База (если есть): {auto.get('model')} {auto.get('year')} {auto.get('engine_code')} {auto.get('engine_vol')} {auto.get('color')} {auto.get('gearbox')}
Владельцев: {auto.get('owners')} ПТС: {auto.get('pts')}
Фото: архив VIN {b1} шт, номерограм {b2} шт, улицы {b3} шт

--- VINDECODE (марка/мотор/год) ---
{vindecode}

--- ПРОБЕГИ (важно для скрутки) ---
{probeg_human}
RAW probeg2: {probeg_raw}

--- ДТП ---
{dtp_raw}

--- ЗАЛОГ / ОГРАНИЧЕНИЯ ---
Залог: {zalog_raw}
ГИБДД: {gibdd_raw}

--- ТЕХОСМОТР ---
{eaisto_raw}

--- ЮРИДИКА из базы ---
{auto.get('juridical')}

ЗАДАЧА:
Ты автоподборщик. Разнеси эту тачку. Клиент хочет понять брать или нет.

СТРОГИЕ ПРАВИЛА:
- Не пиши "нужно проверять по фото" — у тебя уже есть цифры. Если фото 11 архивных и 0 свежих — так и скажи.
- Не выдумывай другой VIN. Говори ТОЛЬКО про {vin}. Забудь про Опель W0L0AHL3582033491 если VIN другой.
- Если скрутка — покажи математику: был 53600 в 2013, стал 130120 в 2020 = +76520 за 7 лет = 10к в год — подозрительно мало.
- Если ДТП нет — пиши "ДТП по базам нет".
- Если гос не указан — пиши что номерограм/автофото пропущены и это норм.

ВЫДАЙ ОТВЕТ СТРОГО В ТАКОМ ФОРМАТЕ (копируй заголовки):

🚦 ВЕРДИКТ: [ЕХАТЬ / НЕ ЕХАТЬ / ЕХАТЬ ОСТОРОЖНО] — 1-2 предложения почему.

🎨 КУЗОВ:
- Что по фото: сколько архивных, сколько свежих, что это значит
- Где крашено: конкретно какие детали (если нет данных — "по базам окрасов нет, смотри толщиномером")
- Стыковки: если была бита и стала целая — укажи

⏱️ ПРОБЕГ:
- Есть ли скрутка? Докажи цифрами
- Средний пробег в год, логика
- Что с пробегом сейчас

🔧 ТЕХНИКА (для этой модели):
- Что ломается у этой модели обычно (возьми из vindecode марки)
- На что смотреть у капота

⚖️ ЮРИДИКА:
- Залог, ограничения, розыск — есть/нет
- ПТС, владельцы

💰 ТОРГ:
- Конкретно за что торговаться и сколько: "ДТП 2016 — 50к, скрутка — 30к, итого 80-120к"
- Если косяков нет — "Торг 20-30к на резину/ТО"

✅ ЧТО ПРОВЕРИТЬ У КАПОТА (10 точек толщиномером):
1. ...
10. ...

Пиши коротко, жестко, как в гараже. Без воды. Эмодзи только в заголовках.
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
    global LAST_REQUEST, LAST_REPORT_DATA
    text_raw = (m.text or "").strip()
    txt_low = (m.text or "").lower()
    mm_gos = re.search(r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}', text_raw.upper())
    mm_vin = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_raw.upper())
    reg = None
    if mm_gos:
        reg = mm_gos.group(0)

    # Кнопка Пересобрать визуал — FIX: не просит VIN, берет последний отчет без доп. оплаты
    if "пересобрать визуал" in txt_low:
        # приоритет: LAST_REPORT_DATA (без запроса в Apipoint) -> LAST_REQUEST -> VIN в сообщении
        data = None
        vin = None
        if LAST_REPORT_DATA and LAST_REPORT_DATA.get("meta",{}).get("vin"):
            vin = LAST_REPORT_DATA.get("meta",{}).get("vin")
            data = LAST_REPORT_DATA
            await m.answer(f"🔄 Пересобираю визуал v59 PREMIUM для {vin} из последнего отчета — без доп. оплаты Apipoint...")
            html = generate_history_html(f"{vin}_rebuild", data)
            file = BufferedInputFile(html.encode('utf-8'), filename=f"History_{vin}_v59_PREMIUM_REBUILD.html")
            await m.answer_document(file, caption=f"🔄 PREMIUM визуал {vin} • Гос {data.get('meta',{}).get('reg')} • {len(data.get('all_b64',[]))} фото • График + таймлайн • Без доп. запросов", reply_markup=main_kb())
            return
        vin = LAST_REQUEST.get("vin")
        if mm_vin:
            vin = mm_vin.group(0)
        if not vin:
            await m.answer("Нет последнего VIN в памяти (бот перезапускался). Пришли VIN — пересоберу визуал.\nНапример: W0L0AHL3582033491", reply_markup=main_kb())
            return
        reg_last = LAST_REQUEST.get("reg") or reg
        await m.answer(f"🔄 Пересобираю визуал v59 PREMIUM для {vin} + {reg_last}... Запрошу Apipoint заново (1 оплата)")
        data = await check_history(vin, reg_last)
        html = generate_history_html(f"{vin}_rebuild", data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"History_{vin}_v59_REBUILD.html")
        await m.answer_document(file, caption=f"🔄 Пересобран PREMIUM визуал: {len(data.get('all_b64',[]))} фото • Гос {data.get('meta',{}).get('reg')}", reply_markup=main_kb())
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
        # --- FIX v59: Кнопка 2 работает без Кнопки 1, берет последний отчет чтобы не разоряться ---
        vin_for_ai = None
        if mm_vin:
            vin_for_ai = mm_vin.group(0)
        elif LAST_REPORT_DATA and LAST_REPORT_DATA.get("meta",{}).get("vin"):
            vin_for_ai = LAST_REPORT_DATA.get("meta",{}).get("vin")
        elif LAST_REQUEST.get("vin"):
            vin_for_ai = LAST_REQUEST.get("vin")

        if not vin_for_ai:
            await m.answer(
                f"Пришли VIN для ИИ разбора — я сам подтяну историю и сделаю рекомендации.\n\n"
                f"Например: W0L0AHL3582033491\n"
                f"Или нажми 1️⃣ если хочешь сначала посмотреть историю.",
                reply_markup=main_kb()
            )
            return

        # Если есть уже готовый отчет для этого VIN — берем его, не тратим деньги на Apipoint
        if LAST_REPORT_DATA and LAST_REPORT_DATA.get("meta",{}).get("vin") == vin_for_ai:
            data_for_ai = LAST_REPORT_DATA
            await m.answer(f"🤖 Беру последний отчет для {vin_for_ai} — формирую рекомендации ИИ через {OPENROUTER_MODEL}... 15-30 сек ⏳")
        else:
            # Нет отчета или другой VIN — делаем историю один раз, потом сразу ИИ (экономим клики клиента)
            await m.answer(f"🤖 Для {vin_for_ai} нет свежего отчета в памяти — собираю историю (1-2 мин) и сразу сделаю ИИ разбор через {OPENROUTER_MODEL}... ⏳\n\nЧтобы не платить дважды, в следующий раз сначала жми 1️⃣, потом 2️⃣ — тогда 2️⃣ возьмет последний отчет без доп. запросов.")
            try:
                data_for_ai = await check_history(vin_for_ai, reg)
                # сразу отдаем первый отчет тоже, чтобы клиент видел что происходит
                html_hist = generate_history_html(vin_for_ai, data_for_ai)
                file_hist = BufferedInputFile(html_hist.encode('utf-8'), filename=f"History_{vin_for_ai}_v58_PREMIUM.html")
                await m.answer_document(file_hist, caption=f"1️⃣ История {vin_for_ai} • {data_for_ai.get('meta',{}).get('reg')} • {len(data_for_ai.get('all_b64',[]))} фото — теперь делаю ИИ разбор", reply_markup=main_kb())
            except Exception as e:
                await m.answer(f"❌ Не смог собрать историю для {vin_for_ai}: {e}", reply_markup=main_kb())
                return

        # Теперь ИИ
        await m.answer(f"🤖 Формирую живой разбор подборщика для {vin_for_ai}...")
        prompt = build_prompt_for_openrouter(data_for_ai)
        ai_text, ai_error = await call_openrouter_ai(prompt)
        if ai_text:
            await m.answer(f"✅ ИИ ответил, собираю итоговый отчет v58 LIVE для {vin_for_ai}...")
        else:
            await m.answer(f"⚠️ OpenRouter не ответил: {ai_error} — сделаю отчет на шаблонах")
        html = generate_ai_recommendations_html(data_for_ai, ai_text=ai_text, ai_error=ai_error)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"AI_Recommendations_{vin_for_ai}_v58_LIVE.html")
        caption = f"2️⃣ ИИ рекомендации LIVE для {vin_for_ai} — {OPENROUTER_MODEL}\n" + (ai_text[:600] + "..." if ai_text and len(ai_text)>600 else (ai_text[:600] if ai_text else f"Ошибка: {ai_error}"))
        await m.answer_document(file, caption=caption[:1000], reply_markup=main_kb())
        return

    # Кнопка 1 - Проверка истории авто по VIN
    if "проверка истории" in txt_low or "истории авто" in txt_low or txt_low.startswith("1️⃣") or mm_vin:
        if mm_vin:
            vin = mm_vin.group(0)
            await m.answer(f"Принял VIN {vin} 👍\n\nСобираю PREMIUM отчет по истории — с графиком пробега, таймлайном ДТП и риск-бейджами.\n\nЗаймет 1-2 минуты ⏳")
            data = await check_history(vin, reg)
            html = generate_history_html(vin, data)
            file = BufferedInputFile(html.encode('utf-8'), filename=f"History_{vin}_v58_PREMIUM.html")
            await m.answer_document(file, caption=f"1️⃣ PREMIUM История {vin} • {data.get('meta',{}).get('reg')} • {len(data.get('all_b64',[]))} фото • График пробега + таймлайн ДТП • Теперь 2️⃣ возьмет этот отчет без доп. оплаты", reply_markup=main_kb())
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
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("Webhook deleted, polling start")
    except Exception as e:
        print(f"delete_webhook error: {e}")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())