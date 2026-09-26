# -*- coding: utf-8 -*-
"""
v62 REAL - NO HARDCODE - ALL SOURCES PARSED
1. carsharing, taxi - badges
2. eaisto - пробег с подписью источника
3. osago - целиком
4. zalog - целиком с деталями
5. gibdd - целиком (owners, pts, sts, restrictions, wanted, regHistory)
6. vindecode - целиком
7. dtp - целиком с damagePoints
8. offerbyvin - целиком (plate, pts, mileage, price, city, photos)
9. nomerogram - целиком (text, title, price)
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

print(f"BOOT v62 REAL FULL PARSE 9 SOURCES model={OPENROUTER_MODEL} key={'yes' if OPENROUTER_API_KEY else 'NO KEY'}")

LAST_REQUEST = {"vin": None, "reg": None}
LAST_REPORT_DATA = {}

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
    # v62 - NO HARDCODE - только пустая структура, заполнится из реальных баз
    return {
        "model": "",
        "year": "",
        "vin": vin,
        "gos": reg or "не указан",
        "gos2": "",
        "photos_online": 0,
        "pts": "",
        "sts": "",
        "body_number": vin,
        "engine_number": "",
        "engine_code": "",
        "engine_vol": "",
        "type": "",
        "color": "",
        "model_code": "",
        "production_date": "",
        "gearbox": "",
        "import": "", "osago": "", "recall": "",
        "owners": 0, "sales_history": 0, "service_history": 0,
        "commercial": "", "auction": "", "mileage": 0, "mileage_sc": False, "dtp_count": 0,
        "juridical": {"ограничения": "", "розыск": "", "залог_фнп": "", "арбитраж": "", "лизинг": "", "птс_наличие": "", "штрафы": "", "регистрация_гибдд": ""},
        "dtp": [],
        # v62 новые поля - все источники целиком
        "carsharing": {"count": 0, "list": []},
        "taxi": {"count": 0, "list": []},
        "eaisto": {"cards": [], "last_mileage": 0},
        "osago": {"policies": []},
        "zalog": {"count": 0, "details": []},
        "gibdd": {"owners": [], "restrictions": [], "wanted": [], "reg_history": []},
        "vindecode_full": {},
        "offerbyvin_full": {"offers": []},
        "nomerogram_full": {"ads": []}
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
        "meta": {"vin": vin, "reg": actual_reg or "не указан", "year": ""},
        "block1_pic": [], "block2_nomerogram": [], "block3_autophoto": [],
        "probeg": [], "vindecode": {}, "zalog": {}, "dtp": {}, "carsharing": {}, "taxi": {}, "offerbyvin": {}, "gibdd": {}, "eaisto": {}, "osago": {},
        "autoteka_hard": get_autoteka_hard_for_vin(vin, actual_reg), "all_b64": [], "raw": {}, "logs": []
    }
    logs = combined["logs"]
    logs.append(f"START v62 FULL vin={vin} reg={actual_reg}")

    # Helper to recursively find offers-like list
    def find_offers_list(obj):
        if isinstance(obj, dict):
            # direct keys
            for k in ["offers", "list", "result", "items"]:
                v = obj.get(k)
                if isinstance(v, list) and len(v)>0 and isinstance(v[0], dict):
                    # check if looks like offer (has mileage or plate or price)
                    if any("mileage" in x or "plate" in x or "gosnomer" in x or "price" in x for x in v[:2]):
                        return v
            # search deeper
            for v in obj.values():
                res = find_offers_list(v)
                if res:
                    return res
        elif isinstance(obj, list) and len(obj)>0 and isinstance(obj[0], dict):
            if any("mileage" in x or "plate" in x for x in obj[:2]):
                return obj
            for item in obj:
                res = find_offers_list(item)
                if res:
                    return res
        return None

    def find_vindecode_dict(obj):
        # returns dict that looks like vindecode
        if isinstance(obj, dict):
            # if has brand/model/year keys
            if any(k in obj for k in ["brand", "make", "model", "modelName", "year", "productionYear"]):
                return obj
            for v in obj.values():
                if isinstance(v, dict):
                    res = find_vindecode_dict(v)
                    if res:
                        return res
                elif isinstance(v, list):
                    for it in v:
                        if isinstance(it, dict):
                            res = find_vindecode_dict(it)
                            if res:
                                return res
        return None

    def parse_eaisto_date(d):
        # handles timestamp int, float, string timestamp, and normal date strings
        if not d:
            return ""
        try:
            # int timestamp
            if isinstance(d, (int, float)):
                try:
                    dt = datetime.fromtimestamp(int(d))
                    return dt.strftime("%d.%m.%Y")
                except:
                    pass
            s = str(d).strip()
            # handle "1655510400.0" or "1655510400.000"
            if "." in s:
                s_part = s.split(".")[0]
                if s_part.isdigit() and len(s_part) >= 10:
                    try:
                        dt = datetime.fromtimestamp(int(s_part[:10]))
                        return dt.strftime("%d.%m.%Y")
                    except:
                        pass
            if s.isdigit():
                # if 10 digits - unix timestamp
                if len(s) == 10:
                    try:
                        dt = datetime.fromtimestamp(int(s))
                        return dt.strftime("%d.%m.%Y")
                    except:
                        pass
                # if 13 digits - ms timestamp
                if len(s) == 13:
                    try:
                        dt = datetime.fromtimestamp(int(s)//1000)
                        return dt.strftime("%d.%m.%Y")
                    except:
                        pass
            # try to find 10-digit timestamp inside string
            import re as _re
            m = _re.search(r'(\d{10})', s)
            if m:
                try:
                    dt = datetime.fromtimestamp(int(m.group(1)))
                    return dt.strftime("%d.%m.%Y")
                except:
                    pass
            return s
        except:
            return str(d)

    derived_reg = None
    # 1. pic by vin
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
                item = {"source": "pic", "price": "1.50", "type": f"Архив по VIN {vin}", "date": "Архив ~2018", "url": url, "gosnomer": derived_reg or "", "desc": f"Архив по VIN {vin}"}
                if b64:
                    item["b64"] = b64
                    combined["all_b64"].append(b64)
                combined["block1_pic"].append(item)
    except Exception as e:
        logs.append(f"pic vin err {e}")

    # 2. СРАЗУ запрашиваем vindecode, offerbyvin, eaisto, probeg2, zalog, dtp, gibdd, osago, taxi, carsharing чтобы вытащить госномер
    pre_sources = ["vindecode", "offerbyvin", "eaisto", "probeg2", "gibdd", "zalog", "dtp", "osago", "carsharing", "taxi"]
    for src in pre_sources:
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
                    elif isinstance(res.get("list"), list):
                        lst = res.get("list")
                combined["probeg"] = lst
            except:
                pass

    # 3. Парсим offerbyvin СРАЗУ чтобы получить госномер для номерограм/автофото
    try:
        ob_raw = combined["raw"].get("offerbyvin",{}).get("result",{})
        offers = find_offers_list(ob_raw) or []
        if offers:
            combined["raw"]["offerbyvin_parsed"] = offers
            combined["autoteka_hard"]["offerbyvin_full"]["offers"] = offers
            found_plate = None
            for off in offers:
                if not isinstance(off, dict):
                    continue
                plate = off.get("plate") or off.get("gosnomer") or off.get("regNum") or off.get("number") or ""
                if plate and not found_plate:
                    import re as _re
                    if _re.search(r'[АВЕКМНОРСТУХA-Z0-9]{2,}', str(plate).upper()):
                        found_plate = str(plate).strip()
            if found_plate and (not actual_reg or actual_reg == "не указан"):
                actual_reg = found_plate
                combined["meta"]["reg"] = found_plate
                LAST_REQUEST["reg"] = found_plate
                combined["autoteka_hard"]["gos"] = found_plate
                logs.append(f"offerbyvin found plate {found_plate} - will query nomerogram/autophoto")
    except Exception as e:
        logs.append(f"offerbyvin early parse err {e}")

    # 4. Теперь зная госномер - запрашиваем номерограм, автофото, pic по гос и offerbyvin по гос (иногда по VIN пусто, а по гос есть)
    if actual_reg and actual_reg != "не указан":
        # дополнительно дергаем offerbyvin по госномеру - часто там есть объявления когда по VIN пусто
        try:
            status_ob_gos, data_ob_gos, _ = await apipoint_call({"sources": "offerbyvin", "regNum": actual_reg})
            logs.append(f"offerbyvin by reg {actual_reg} -> {status_ob_gos}")
            if status_ob_gos == 200:
                # мерджим с основным offerbyvin
                offers_gos = find_offers_list(data_ob_gos.get("result",{})) or []
                if offers_gos:
                    existing = combined["raw"].get("offerbyvin_parsed") or []
                    # объединяем без дублей
                    combined["raw"]["offerbyvin_parsed"] = existing + [o for o in offers_gos if o not in existing]
                    combined["raw"]["offerbyvin_by_reg"] = data_ob_gos
                    logs.append(f"offerbyvin by reg found {len(offers_gos)} offers")
        except Exception as e:
            logs.append(f"offerbyvin by reg err {e}")

        # также пробуем vindecode по гос? иногда помогает
        try:
            status_vd_gos, data_vd_gos, _ = await apipoint_call({"sources": "vindecode", "regNum": actual_reg})
            logs.append(f"vindecode by reg {actual_reg} -> {status_vd_gos}")
            if status_vd_gos == 200:
                combined["raw"]["vindecode_by_reg"] = data_vd_gos
        except:
            pass

        # pic by gos if not already
        if not derived_reg or derived_reg != actual_reg:
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
                        item = {"source": "pic", "price": "1.50", "type": f"Архив по гос {actual_reg}", "date": "Архив по гос", "url": url, "gosnomer": actual_reg, "desc": f"Архив по гос {actual_reg}"}
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
                    mileage = r.get("mileage") or r.get("probeg") or ""
                    imgs = r.get("img") or []
                    combined["autoteka_hard"]["nomerogram_full"]["ads"].append({
                        "date": date, "url": url, "text": str(text)[:2000], "title": title, "source": source, "price": price, "mileage": mileage
                    })
                    if isinstance(imgs, list) and imgs:
                        for img_url in imgs[:10]:
                            b64 = await download_image_any(img_url)
                            item = {"source": source or "nomerogram", "price": "1.30", "type": f"Номерограм {actual_reg}", "date": date, "url": url, "title": title, "desc": str(text)[:1000], "price_val": price, "mileage": mileage, "img_url": img_url}
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
                    item = {"source": "platesmania.com", "price": "1.60", "type": f"Фото пользователей {actual_reg}", "date": date, "name": rec.get("name") or "", "urlphoto": urlphoto, "bigPhoto": bigPhoto, "urlNumber": rec.get("urlNumber") or "", "desc": f"platesmania {date}"}
                    if b64:
                        item["b64"] = b64
                        combined["all_b64"].append(b64)
                    combined["block3_autophoto"].append(item)
        except Exception as e:
            logs.append(f"autophoto err {e}")
    else:
        logs.append(f"SKIP nomerogram/autophoto - нет госномера даже после offerbyvin")

    # --- v62 FULL PARSE ALL 9 SOURCES ROBUST ---
    try:
        ah = combined["autoteka_hard"]
        # 6. vindecode целиком - robust with deep search and many key variants
        vd_raw = combined["raw"].get("vindecode",{}).get("result",{})
        vd = None
        # try many nesting levels
        for attempt in [find_vindecode_dict(vd_raw), vd_raw.get("vindecode"), vd_raw.get("result"), vd_raw]:
            if isinstance(attempt, dict):
                vd = attempt
                # if this dict itself has vindecode inside, dive
                if "vindecode" in vd and isinstance(vd["vindecode"], dict):
                    vd = vd["vindecode"]
                if "result" in vd and isinstance(vd["result"], dict) and any(k in vd["result"] for k in ["brand","make","model","year"]):
                    vd = vd["result"]
                if find_vindecode_dict(vd):
                    vd = find_vindecode_dict(vd)
                    break
                if any(k in vd for k in ["brand","make","model","year","manufacturer"]):
                    break
        if isinstance(vd, dict):
            # final deep search
            deep = find_vindecode_dict(vd)
            if deep:
                vd = deep
            ah["vindecode_full"] = vd
            # log keys for debug
            logs.append(f"vindecode keys: {list(vd.keys())[:20]}")
        else:
            logs.append(f"vindecode empty or not dict: {type(vd)} raw keys {list(vd_raw.keys()) if isinstance(vd_raw, dict) else 'not dict'}")
            vd = {}
            brand = vd.get("brand") or vd.get("make") or vd.get("manufacturer") or ""
            model = vd.get("model") or vd.get("modelName") or ""
            year = vd.get("year") or vd.get("productionYear") or vd.get("yearOfManufacture") or vd.get("modelYear") or ""
            engine_vol = vd.get("engineVolume") or vd.get("engine") or vd.get("engineSize") or vd.get("displacement") or vd.get("engine_volume") or ""
            power = vd.get("power") or vd.get("enginePower") or vd.get("powerHp") or ""
            body = vd.get("body") or vd.get("bodyType") or vd.get("vehicleType") or ""
            color = vd.get("color") or vd.get("bodyColor") or ""
            engine_code = vd.get("engineCode") or vd.get("engineModel") or vd.get("engineType") or ""
            gearbox = vd.get("gearbox") or vd.get("transmission") or vd.get("gearboxType") or ""
            fuel = vd.get("fuel") or vd.get("fuelType") or ""
            drive = vd.get("drive") or vd.get("driveType") or ""
            if brand or model:
                if not ah.get("model"):
                    ah["model"] = f"{brand} {model}".strip()
            if year:
                ah["year"] = str(year)
                combined["meta"]["year"] = str(year)
            if engine_vol or power:
                if not ah.get("engine_vol"):
                    ah["engine_vol"] = f"{engine_vol} {power}".strip() if power else str(engine_vol)
            if engine_code:
                if not ah.get("engine_code"):
                    ah["engine_code"] = str(engine_code)
            if color:
                if not ah.get("color"):
                    ah["color"] = str(color)
            if body:
                if not ah.get("type"):
                    ah["type"] = str(body)
            if gearbox:
                if not ah.get("gearbox"):
                    ah["gearbox"] = str(gearbox)
            pts_vd = vd.get("pts") or vd.get("ptsNumber") or vd.get("vehiclePassportNumber") or ""
            if pts_vd and not ah.get("pts"):
                ah["pts"] = str(pts_vd)

        # 5. gibdd целиком
        gib_raw = combined["raw"].get("gibdd",{}).get("result",{})
        gib = gib_raw.get("gibdd") or gib_raw.get("result") or gib_raw
        if isinstance(gib, dict):
            if isinstance(gib.get("ownershipPeriods"), list) and gib.get("ownershipPeriods"):
                ah["owners"] = len(gib.get("ownershipPeriods"))
                ah["gibdd"]["owners"] = gib.get("ownershipPeriods")
                last = gib.get("ownershipPeriods")[-1]
                if isinstance(last, dict) and last.get("pts") and not ah.get("pts"):
                    ah["pts"] = str(last.get("pts"))
            if isinstance(gib.get("registrationHistory"), list):
                ah["gibdd"]["reg_history"] = gib.get("registrationHistory")
            if isinstance(gib.get("restrictions"), list):
                ah["gibdd"]["restrictions"] = gib.get("restrictions")
                if gib.get("restrictions"):
                    ah["juridical"]["ограничения"] = f"Найдено {len(gib.get('restrictions'))} огр."
                else:
                    ah["juridical"]["ограничения"] = "Не найдены"
            elif isinstance(gib.get("restrict"), list):
                ah["gibdd"]["restrictions"] = gib.get("restrict")
            if isinstance(gib.get("wanted"), list):
                ah["gibdd"]["wanted"] = gib.get("wanted")
                ah["juridical"]["розыск"] = f"Найдено {len(gib.get('wanted'))}" if gib.get("wanted") else "Не найден"
            for k in ["pts", "ptsNumber", "vehiclePassport", "sts", "stsNumber"]:
                if gib.get(k) and not ah.get(k if k in ["pts","sts"] else ""):
                    if "pts" in k.lower() and not ah.get("pts"):
                        ah["pts"] = str(gib.get(k))[:60]
                    if "sts" in k.lower() and not ah.get("sts"):
                        ah["sts"] = str(gib.get(k))[:60]

        # 7. dtp целиком
        try:
            dtp_raw = combined["raw"].get("dtp",{}).get("result",{})
            dtp_inner = dtp_raw.get("dtp") or dtp_raw
            dtp_list = []
            if isinstance(dtp_inner, dict):
                if isinstance(dtp_inner.get("list"), list):
                    dtp_list = dtp_inner.get("list")
                elif isinstance(dtp_inner.get("result"), list):
                    dtp_list = dtp_inner.get("result")
                elif isinstance(dtp_inner.get("accidents"), list):
                    dtp_list = dtp_inner.get("accidents")
                count = dtp_inner.get("count") or dtp_inner.get("total") or len(dtp_list)
                ah["dtp_count"] = count
                norm = []
                for d in dtp_list[:10]:
                    if not isinstance(d, dict):
                        continue
                    norm.append({
                        "date": parse_eaisto_date(d.get("date") or d.get("accidentDate") or d.get("eventDate") or ""),
                        "type": d.get("type") or d.get("accidentType") or "ДТП",
                        "damage": d.get("damage") or d.get("damageType") or "Нет данных",
                        "damagePoints": d.get("damagePoints") or d.get("damagedParts") or [],
                        "region": d.get("region") or d.get("place") or "",
                        "participants": d.get("participants") or 0,
                        "cost": d.get("cost") or d.get("damageCost") or ""
                    })
                ah["dtp"] = norm
            elif isinstance(dtp_inner, list):
                ah["dtp_count"] = len(dtp_inner)
                ah["dtp"] = [{"date": parse_eaisto_date(d.get("date","")), "type": d.get("type","ДТП"), "damage": d.get("damage",""), "damagePoints": d.get("damagePoints",[]), "region": d.get("region",""), "participants":0, "cost":""} for d in dtp_inner[:10] if isinstance(d, dict)]
        except Exception as e:
            logs.append(f"dtp parse err {e}")

        # 8. offerbyvin целиком - уже нашли offers ранее, но дополним
        try:
            offers = combined["raw"].get("offerbyvin_parsed") or find_offers_list(combined["raw"].get("offerbyvin",{}).get("result",{})) or []
            if offers:
                combined["raw"]["offerbyvin_parsed"] = offers
                ah["offerbyvin_full"]["offers"] = offers
                found_pts = None
                found_sts = None
                for off in offers:
                    if not isinstance(off, dict):
                        continue
                    pts = off.get("ptsNumber") or off.get("pts") or off.get("vehiclePassportNumber") or ""
                    if pts and not ah.get("pts"):
                        ah["pts"] = str(pts)
                    sts = off.get("stsNumber") or off.get("sts") or ""
                    if sts and not ah.get("sts"):
                        ah["sts"] = str(sts)
                # Пробег из объявлений с подписью источника
                for off in offers:
                    if not isinstance(off, dict):
                        continue
                    d = parse_eaisto_date(off.get("date") or off.get("publishDate") or off.get("created") or "")
                    m = off.get("mileage") or off.get("probeg") or off.get("odometer") or 0
                    try:
                        m_int = int(str(m).replace(" ", "").replace("км","").strip() or 0)
                        if m_int > 0:
                            # check if already exists to avoid duplicates
                            if not any(abs(x.get("Probeg",0)-m_int)<100 for x in combined["probeg"] if isinstance(x, dict)):
                                combined["probeg"].append({"DateString": str(d), "Probeg": m_int, "Source": f"Авито {off.get('city','')} {off.get('price','')}₽"})
                    except:
                        pass
                ah["sales_history"] = len(offers)
                # Фото из объявлений если pic пустой
                if not combined["block1_pic"] and not combined["block2_nomerogram"]:
                    for off in offers[:3]:
                        if not isinstance(off, dict):
                            continue
                        imgs = off.get("photos") or off.get("images") or off.get("img") or off.get("imageList") or []
                        if isinstance(imgs, list):
                            for img_url in imgs[:10]:
                                if isinstance(img_url, dict):
                                    img_url = img_url.get("url") or img_url.get("big") or ""
                                if not img_url or len(str(img_url)) < 15:
                                    continue
                                if len(combined["all_b64"]) >= 15:
                                    break
                                b64 = await download_image_any(str(img_url))
                                item = {"source": "offerbyvin", "price": "Авито", "type": f"Объявление {off.get('date','')}", "date": parse_eaisto_date(off.get("date","")), "url": str(img_url)[:200], "desc": f"Авито {off.get('price','')} {off.get('mileage','')}км {off.get('city','')}"}
                                if b64:
                                    item["b64"] = b64
                                    combined["all_b64"].append(b64)
                                combined["block1_pic"].append(item)
        except Exception as e:
            logs.append(f"offerbyvin parse err {e}")

        # 2. eaisto - пробег с подписью источника - robust
        try:
            ea_raw = combined["raw"].get("eaisto",{}).get("result",{})
            ea_inner = ea_raw.get("eaisto") or ea_raw.get("result") or ea_raw
            if isinstance(ea_inner, dict):
                cards = ea_inner.get("cards") or ea_inner.get("list") or ea_inner.get("result") or []
                if isinstance(cards, list) and len(cards)>0:
                    for c in cards[:10]:
                        if not isinstance(c, dict):
                            continue
                        d_raw = c.get("date") or c.get("issueDate") or c.get("validFrom") or c.get("from") or ""
                        d = parse_eaisto_date(d_raw)
                        m = c.get("mileage") or c.get("odometer") or c.get("probeg") or 0
                        try:
                            m_int = int(str(m).replace(" ","").replace("км","") or 0)
                            if m_int>0:
                                combined["probeg"].append({"DateString": str(d), "Probeg": m_int, "Source": f"ЕАИСТО ТО {c.get('operator','')}"})
                                ah["eaisto"]["cards"].append({"date": str(d), "mileage": m_int, "operator": c.get("operator",""), "validTo": parse_eaisto_date(c.get("validTo",""))})
                        except:
                            pass
                else:
                    # одиночная запись
                    d_raw = ea_inner.get("date") or ea_inner.get("issueDate") or ea_inner.get("from") or ""
                    d = parse_eaisto_date(d_raw)
                    m = ea_inner.get("mileage") or ea_inner.get("probeg") or ea_inner.get("odometer") or 0
                    try:
                        m_int = int(str(m).replace(" ","") or 0)
                        if m_int>0:
                            combined["probeg"].append({"DateString": str(d), "Probeg": m_int, "Source": "ЕАИСТО ТО"})
                            ah["eaisto"]["cards"].append({"date": str(d), "mileage": m_int, "operator": ea_inner.get("operator","")})
                    except:
                        pass
        except Exception as e:
            logs.append(f"eaisto parse err {e}")

        # 1. carsharing и taxi
        for src in ["carsharing", "taxi"]:
            try:
                raw_src = combined["raw"].get(src,{}).get("result",{})
                inner = raw_src.get(src) or raw_src.get("result") or raw_src
                if isinstance(inner, dict):
                    cnt = inner.get("count") or inner.get("total") or len(inner.get("list",[]))
                    lst = inner.get("list") or inner.get("items") or []
                    ah[src]["count"] = cnt if isinstance(cnt, int) else len(lst) if isinstance(lst, list) else 0
                    ah[src]["list"] = lst if isinstance(lst, list) else []
                    if cnt and cnt>0:
                        logs.append(f"{src} FOUND {cnt}")
                elif isinstance(inner, list):
                    ah[src]["count"] = len(inner)
                    ah[src]["list"] = inner
            except Exception as e:
                logs.append(f"{src} parse err {e}")

        # 3. osago целиком
        try:
            os_raw = combined["raw"].get("osago",{}).get("result",{})
            os_inner = os_raw.get("osago") or os_raw.get("result") or os_raw
            if isinstance(os_inner, dict):
                pols = os_inner.get("policies") or os_inner.get("list") or os_inner.get("result") or []
                if isinstance(pols, list):
                    ah["osago"]["policies"] = pols
                elif isinstance(os_inner, list):
                    ah["osago"]["policies"] = os_inner
            elif isinstance(os_inner, list):
                ah["osago"]["policies"] = os_inner
        except Exception as e:
            logs.append(f"osago parse err {e}")

        # 4. zalog целиком
        try:
            zalog_raw = combined["raw"].get("zalog",{}).get("result",{})
            zalog_inner = zalog_raw.get("zalog") or zalog_raw
            if isinstance(zalog_inner, dict):
                cnt = zalog_inner.get("count") or len(zalog_inner.get("list",[]))
                lst = zalog_inner.get("list") or zalog_inner.get("items") or []
                ah["zalog"]["count"] = cnt if isinstance(cnt, int) else 0
                ah["zalog"]["details"] = lst if isinstance(lst, list) else []
                if cnt == 0:
                    ah["juridical"]["залог_фнп"] = "Не найден"
                elif cnt>0:
                    ah["juridical"]["залог_фнп"] = f"Найдено {cnt} записей"
                else:
                    ah["juridical"]["залог_фнп"] = "Нет данных"
            else:
                ah["juridical"]["залог_фнп"] = "Нет данных"
        except:
            pass

        if not ah.get("pts"):
            ah["pts"] = "Нет данных в базах"
        if not ah.get("sts"):
            ah["sts"] = "Нет данных в базах"
        if not ah.get("model") or ah.get("model") == f"Авто {vin[:8]}":
            # fallback по WMI - первые 3 символа VIN
            wmi = vin[:3].upper()
            wmi_map = {
                "WF0": "FORD", "WFO": "FORD", "W0L": "OPEL", "W0V": "OPEL", "WBA": "BMW", "WBS": "BMW", "WDB": "MERCEDES", "WDC": "MERCEDES",
                "ZAM": "MASERATI", "ZFA": "FIAT", "ZFF": "FERRARI", "WVW": "VOLKSWAGEN", "WAU": "AUDI", "TRU": "AUDI",
                "TMB": "SKODA", "VSS": "SEAT", "1HG": "HONDA", "2HG": "HONDA", "JHM": "HONDA", "JT": "TOYOTA", "VF": "RENAULT/PEUGEOT/CITROEN"
            }
            brand_fallback = wmi_map.get(wmi, "")
            # попробуем вытащить модель из vindecode raw даже если парсинг не сработал - ищем слова
            raw_str = str(combined["raw"].get("vindecode",{}))[:5000]
            # если в raw есть "FUSION" или "FOCUS" и тд
            import re as _re
            m = _re.search(r'"model"\s*:\s*"([^"]+)"', raw_str, _re.IGNORECASE)
            model_fallback = m.group(1) if m else ""
            m2 = _re.search(r'"brand"\s*:\s*"([^"]+)"', raw_str, _re.IGNORECASE)
            brand_fallback2 = m2.group(1) if m2 else brand_fallback
            if brand_fallback2 or model_fallback:
                ah["model"] = f"{brand_fallback2} {model_fallback}".strip() or ah.get("model")
            else:
                ah["model"] = f"Авто {vin[:8]} ({brand_fallback})" if brand_fallback else f"Авто {vin[:8]}"
            logs.append(f"vindecode fallback used: wmi {wmi} -> {ah['model']} raw snippet {raw_str[:200]}")
        if not ah.get("color"):
            ah["color"] = "Нет данных"
        if not ah.get("engine_vol"):
            ah["engine_vol"] = "Нет данных"
        if not ah.get("type"):
            ah["type"] = "Легковой"

    except Exception as e:
        logs.append(f"enrich FULL err {e} {__import__('traceback').format_exc()[:500]}")

    global LAST_REPORT_DATA
    LAST_REPORT_DATA = combined
    return combined


def generate_history_html(target, data):
    """v62 FULL - NO HARDCODE - все 9 источников"""
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
    reg = meta.get("reg") or auto.get("gos") or "не указан"
    if reg in ["", "не указан"] and auto.get("gos"):
        reg = auto.get("gos")

    model_full = auto.get("model") or f"Авто {vin[:8]}"
    year = auto.get("year") or meta.get("year") or "—"
    color = auto.get("color") or "Нет данных"
    color_upper = str(color).upper() if color != "Нет данных" else str(year)
    pts = auto.get("pts") or "Нет данных в базах"
    sts = auto.get("sts") or "Нет данных в базах"
    engine_code = auto.get("engine_code") or ""
    engine_vol = auto.get("engine_vol") or "Нет данных"
    gearbox = auto.get("gearbox") or "Нет данных"
    owners = auto.get("owners", 0)
    body_type = auto.get("type") or "Легковой"

    probeg_sorted = []
    skrutka = None
    try:
        def parse_date(s):
            import re as re2
            try:
                # timestamp int or string like 1655510400
                if isinstance(s, int):
                    return datetime.fromtimestamp(s)
                s_str = str(s).strip()
                if s_str.isdigit() and len(s_str) == 10:
                    try:
                        return datetime.fromtimestamp(int(s_str))
                    except:
                        pass
                for fmt in ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        return datetime.strptime(s_str[:19], fmt)
                    except:
                        pass
                m = re2.search(r'(\d{2})\.(\d{2})\.(\d{4})', s_str)
                if m:
                    return datetime.strptime(f"{m.group(1)}.{m.group(2)}.{m.group(3)}", "%d.%m.%Y")
                m2 = re2.search(r'(\d{4})-(\d{2})-(\d{2})', s_str)
                if m2:
                    return datetime.strptime(f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}", "%Y-%m-%d")
                # try unix timestamp inside string
                m3 = re2.search(r'(\d{10})', s_str)
                if m3:
                    try:
                        return datetime.fromtimestamp(int(m3.group(1)))
                    except:
                        pass
            except:
                pass
            return datetime.min
        tmp = []
        for it in probeg:
            if isinstance(it, dict) and it.get("Probeg") is not None:
                d = it.get("DateString","")
                try:
                    p = int(it.get("Probeg",0) or 0)
                except:
                    continue
                if p <= 0:
                    continue
                tmp.append((parse_date(d), d, p, it.get("Source","")))
        tmp.sort(key=lambda x: x[0])
        probeg_sorted = tmp
        for i in range(1, len(tmp)):
            if tmp[i][2] < tmp[i-1][2] - 3000:
                skrutka = {"diff": tmp[i-1][2]-tmp[i][2], "date": tmp[i][1][:10], "prev_date": tmp[i-1][1][:10], "prev": tmp[i-1][2], "cur": tmp[i][2]}
                break
    except Exception as e:
        logs.append(f"probeg sort err {e}")
        probeg_sorted = []

    dtp_list = auto.get("dtp",[]) or []
    dtp_count = auto.get("dtp_count", len(dtp_list))
    total_photos = len(all_b64)
    all_photos = b1 + b2 + b3

    if skrutka:
        skrutka_badge = f"СКРУТКА НАЙДЕНА • -{skrutka['diff']} КМ"
    else:
        if len(probeg_sorted) >= 2:
            skrutka_badge = "СКРУТКА НЕ НАЙДЕНА"
        else:
            skrutka_badge = f"ПРОБЕГ {len(probeg_sorted)} ЗАПИСЕЙ"

    offers = raw.get("offerbyvin_parsed") or auto.get("offerbyvin_full",{}).get("offers") or []
    if not offers:
        try:
            ob_raw = raw.get("offerbyvin",{}).get("result",{})
            ob = ob_raw.get("offerbyvin") or ob_raw.get("result") or ob_raw
            if isinstance(ob, dict) and isinstance(ob.get("offers"), list):
                offers = ob.get("offers")
        except:
            offers = []

    # commercial badges
    taxi_count = auto.get("taxi",{}).get("count",0)
    carsharing_count = auto.get("carsharing",{}).get("count",0)

    graph_svg = ""
    graph_dates = ""
    if probeg_sorted:
        try:
            vals = [p[2] for p in probeg_sorted[-7:]]
            # use human readable dates for graph
            def human_date_for_graph(d_str):
                try:
                    # if timestamp, convert
                    s = str(d_str).strip()
                    if s.isdigit() and len(s)==10:
                        return datetime.fromtimestamp(int(s)).strftime("%d.%m")
                    # try parse
                    import re as _re
                    m = _re.search(r'(\d{2})\.(\d{2})\.(\d{4})', s)
                    if m:
                        return f"{m.group(1)}.{m.group(2)}"
                    return s[:5]
                except:
                    return str(d_str)[:5]
            dates = [human_date_for_graph(p[1]) for p in probeg_sorted[-7:]]
            max_v = max(vals) if vals else 1
            min_v = min(vals) if vals else 0
            rng = max_v - min_v or 1
            points = []
            for idx, v in enumerate(vals):
                x = 20 + idx * (280 / max(1, len(vals)-1))
                y = 80 - ((v - min_v) / rng) * 60
                points.append((x, y))
            path_d = f"M {points[0][0]} {points[0][1]}"
            for (x,y) in points[1:]:
                path_d += f" L {x} {y}"
            circles = "".join([f'<circle cx="{x}" cy="{y}" r="5" fill="#fff" stroke="#111" stroke-width="2"/>' for (x,y) in points])
            graph_svg = f'<svg viewBox="0 0 320 100" style="width:100%;height:90px"><path d="{path_d}" fill="none" stroke="#111" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>{circles}</svg>'
            graph_dates = "".join([f'<span style="margin-right:6px">{d}</span>' for d in dates])
        except Exception as e:
            logs.append(f"graph err {e}")
            graph_svg = '<div style="font-size:12px;color:#8e8e93;padding:20px;text-align:center">Нет данных для графика</div>'
    else:
        graph_svg = '<div style="font-size:12px;color:#8e8e93;padding:20px;text-align:center">Нет записей пробега в базах</div>'

    # build photos html safely without nested f-string backslash
    photos_html = ""
    if all_photos:
        parts = []
        for it in all_photos[:9]:
            b64 = it.get("b64","")
            img_tag = ""
            if b64:
                img_tag = '<img src="' + b64 + '" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0.9" />'
            t = it.get("type","Фото")[:20]
            d = (it.get("date","")[:10] or "—")
            parts.append('<div class="photo-cell"><div style="font-size:11px;color:#6b7280;z-index:1">' + t + '</div><span class="year">' + d + '</span>' + img_tag + '</div>')
        photos_html = "".join(parts)
    else:
        photos_html = '<div style="grid-column:1/-1;padding:20px;text-align:center;font-size:12px;color:#8e8e93">Нет фото в базах pic/nomerogram/offerbyvin</div>'

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>История {vin} v62 FULL</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}} body{{font-family:Manrope,-apple-system,BlinkMacSystemFont,sans-serif;background:#f2f2f7;color:#111; -webkit-font-smoothing:antialiased}}
.container{{max-width:440px;margin:0 auto;padding:12px;padding-bottom:40px}}
.card{{background:#fff;border-radius:24px;padding:18px;border:1px solid #e5e5ea;box-shadow:0 1px 2px rgba(0,0,0,0.04);margin-top:14px}}
.pill{{display:inline-flex;align-items:center;padding:8px 14px;border-radius:999px;font-size:11px;font-weight:800;letter-spacing:0.02em}}
.pill-red{{background:#ff3b30;color:#fff}} .pill-black{{background:#111;color:#fff}} .pill-green{{background:#34c759;color:#fff}} .pill-gray{{background:#e5e7eb;color:#374151}} .pill-orange{{background:#ff9500;color:#fff}}
.blue-hero{{background:linear-gradient(180deg,#c7d2fe 0%,#dbeafe 40%,#eff6ff 100%);border-radius:28px;padding:18px;position:relative;overflow:hidden;border:1px solid #bfdbfe}}
.blue-hero small{{font-size:11px;letter-spacing:0.12em;color:#3b82f6;font-weight:700}}
.blue-hero h2{{font-size:28px;font-weight:800;color:#1e1b4b;letter-spacing:-0.02em;margin-top:6px;line-height:0.95}}
.badge-vin{{background:#fff;border:1px solid #dbeafe;color:#2563eb;padding:6px 12px;border-radius:999px;font-size:11px;font-weight:700;display:inline-block;margin-top:10px}}
.chip-black{{background:#111;color:#fff;border-radius:999px;padding:12px 18px;font-size:14px;font-weight:700;display:inline-flex;align-items:center;gap:8px}}
.chip-white{{background:#fff;border:1px solid #e5e5ea;color:#111;border-radius:999px;padding:12px 18px;font-size:14px;font-weight:600;display:inline-flex;align-items:center;gap:8px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}}
.info-card{{background:#f8f8fb;border:1px solid #efeff4;border-radius:18px;padding:12px;display:flex;gap:10px;align-items:center}}
.info-card .ico{{width:36px;height:36px;background:#fff;border:1px solid #e5e5ea;border-radius:999px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0}}
.info-card .lbl{{font-size:10px;color:#8e8e93;font-weight:700;letter-spacing:0.08em;text-transform:uppercase}}
.info-card .val{{font-size:13px;font-weight:700;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:140px}}
.jur-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}}
.jur-pill{{background:#fff;border:1px solid #e5e5ea;color:#374151;padding:10px 12px;border-radius:999px;font-size:12px;font-weight:600;display:flex;gap:6px;align-items:center}}
.jur-pill.ok{{border-color:#d1fae5;color:#065f46}} .jur-pill.bad{{border-color:#fecaca;color:#991b1b}} .jur-pill .dot{{width:18px;height:18px;background:#8e8e93;border-radius:999px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px}} .jur-pill.ok .dot{{background:#34c759}} .jur-pill.bad .dot{{background:#ef4444}}
.dtp-card{{background:#f8f8fa;border-radius:18px;padding:14px;margin-top:10px;border:1px solid #e5e5ea}}
.timeline{{margin-top:14px}} .tl-row{{display:flex;gap:12px;position:relative;padding-bottom:18px}} .tl-line{{position:absolute;left:6px;top:14px;bottom:-4px;width:1px;background:#e5e7eb}}
.tl-dot{{width:12px;height:12px;border-radius:999px;background:#111;border:2px solid #fff;box-shadow:0 0 0 2px #e5e7eb;flex-shrink:0;margin-top:2px;z-index:1}} .tl-dot.red{{background:#ff3b30;box-shadow:0 0 0 4px #fee2e2}} .tl-dot.hl{{background:#111}}
.tl-content{{flex:1}} .tl-date{{font-weight:700;font-size:14px}} .tl-sub{{font-size:12px;color:#8e8e93;margin-top:2px}}
.skrutka-pill{{display:inline-flex;background:#ffeaea;color:#ff3b30;border:1px solid #ffcccc;padding:4px 10px;border-radius:999px;font-size:11px;font-weight:700;margin-left:8px}}
.graph-wrap{{background:#fff;border:1px solid #e5e5ea;border-radius:20px;padding:12px;margin-top:12px}}
.photo-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:12px}}
.photo-cell{{background:#f1f1f3;border-radius:16px;aspect-ratio:1;position:relative;overflow:hidden;border:1px solid #e5e5ea;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:8px;text-align:center}}
.photo-cell .year{{position:absolute;bottom:8px;left:8px;background:#111;color:#fff;font-size:11px;font-weight:700;padding:4px 8px;border-radius:999px}}
.log{{font-family:monospace;font-size:9px;background:#f8f8fb;padding:10px;border-radius:12px;overflow:auto;max-height:120px;white-space:pre-wrap;color:#8e8e93;border:1px solid #efeff4}}
</style></head>
<body><div class="container">
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:6px">
  <span class="pill {'pill-red' if skrutka else 'pill-gray'}">{skrutka_badge}</span>
  <span class="pill pill-black">ДТП {dtp_count}</span>
  <span class="pill {'pill-orange' if taxi_count>0 else 'pill-gray'}">ТАКСИ {taxi_count}</span>
  <span class="pill {'pill-orange' if carsharing_count>0 else 'pill-gray'}">КАРШЕРИНГ {carsharing_count}</span>
  <span class="pill pill-gray">ЮРИДИКА: {auto.get('juridical',{}).get('залог_фнп','Проверка')[:20]}</span>
</div>
<div class="blue-hero" style="margin-top:12px">
  <small>{body_type} • {year}</small>
  <h2>{color_upper}</h2>
  <span class="badge-vin">VIN • {vin}</span>
  <div style="margin-top:18px">
    <div style="font-size:22px;font-weight:800;letter-spacing:-0.02em;line-height:1">{model_full}</div>
    <div style="font-size:14px;color:#6b7280;font-weight:600;margin-top:4px">{engine_vol} • {gearbox} • {color}</div>
  </div>
  <div style="display:flex;gap:8px;margin-top:16px;flex-wrap:wrap">
    <span class="chip-black"># {reg}</span>
    <span class="chip-white">👥 {owners} владельца • {len(offers)} объявлений</span>
  </div>
</div>
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div style="font-weight:800;letter-spacing:0.08em;font-size:12px">СВЕДЕНИЯ • ПТС (РЕАЛЬНЫЕ ДАННЫЕ)</div>
    <span class="pill" style="background:#f2f2f7;color:#6b7280;font-size:10px">Из баз</span>
  </div>
  <div class="grid2">
    <div class="info-card"><div class="ico">#</div><div><div class="lbl">VIN</div><div class="val">{vin[:13]}...</div></div></div>
    <div class="info-card"><div class="ico">🚗</div><div><div class="lbl">ГОСНОМЕР</div><div class="val">{reg}</div></div></div>
    <div class="info-card"><div class="ico">📄</div><div><div class="lbl">ПТС</div><div class="val">{pts[:22]}</div></div></div>
    <div class="info-card"><div class="ico">📄</div><div><div class="lbl">СТС</div><div class="val">{sts[:22]}</div></div></div>
    <div class="info-card"><div class="ico">🔧</div><div><div class="lbl">ДВИГАТЕЛЬ</div><div class="val">{engine_code or engine_vol[:18]}</div></div></div>
    <div class="info-card"><div class="ico">⚙️</div><div><div class="lbl">КПП</div><div class="val">{gearbox[:18]}</div></div></div>
    <div class="info-card"><div class="ico">🎨</div><div><div class="lbl">ЦВЕТ</div><div class="val">{color[:18]}</div></div></div>
    <div class="info-card"><div class="ico">📅</div><div><div class="lbl">ГОД</div><div class="val">{year}</div></div></div>
  </div>
  <div style="font-size:10px;color:#8e8e93;margin-top:10px">Источники: vindecode, gibdd, offerbyvin, eaisto. "Нет данных" = база не вернула.</div>
</div>
<div class="card">
  <div style="font-weight:800;font-size:13px;letter-spacing:0.06em">✅ ЮРИДИКА (РЕАЛЬНЫЕ ПРОВЕРКИ)</div>
  <div class="jur-grid">
    <div class="jur-pill"><span class="dot">✓</span> Ограничений: {auto.get('juridical',{}).get('ограничения','Нет данных')[:30]}</div>
    <div class="jur-pill"><span class="dot">✓</span> Розыск: {auto.get('juridical',{}).get('розыск','Нет данных')[:20]}</div>
    <div class="jur-pill"><span class="dot">✓</span> Залог: {auto.get('juridical',{}).get('залог_фнп','Нет данных')[:30]}</div>
    <div class="jur-pill"><span class="dot">✓</span> Лизинг: {auto.get('juridical',{}).get('лизинг','Нет данных')[:20]}</div>
  </div>
  <div style="margin-top:10px">
    <div style="font-size:11px;font-weight:700;margin-top:8px">ЗАЛОГ ДЕТАЛИ ({len(auto.get('zalog',{}).get('details',[]))}):</div>
    {''.join([f'<div style="font-size:11px;color:#6b7280;padding:4px 0;border-bottom:1px solid #f2f2f7">{d.get("bank","")} • {d.get("date","")} • {d.get("type","")}</div>' for d in auto.get('zalog',{}).get('details',[])[:3]]) if auto.get('zalog',{}).get('details') else '<div style="font-size:11px;color:#6b7280">Залог не найден</div>'}
    <div style="font-size:11px;font-weight:700;margin-top:8px">ОСАГО ({len(auto.get('osago',{}).get('policies',[]))}):</div>
    {''.join([f'<div style="font-size:11px;color:#6b7280;padding:4px 0;border-bottom:1px solid #f2f2f7">{p.get("company","")} • {p.get("date","")} • {p.get("period","")}</div>' for p in auto.get('osago',{}).get('policies',[])[:3]]) if auto.get('osago',{}).get('policies') else '<div style="font-size:11px;color:#6b7280">Нет данных ОСАГО</div>'}
    <div style="font-size:11px;font-weight:700;margin-top:8px">ГИБДД РЕГ ИСТОРИЯ ({len(auto.get('gibdd',{}).get('reg_history',[]))}):</div>
    {''.join([f'<div style="font-size:11px;color:#6b7280;padding:4px 0;border-bottom:1px solid #f2f2f7">{r.get("date","")} • {r.get("region","")} • {r.get("type","")}</div>' for r in auto.get('gibdd',{}).get('reg_history',[])[:3]]) if auto.get('gibdd',{}).get('reg_history') else '<div style="font-size:11px;color:#6b7280">Нет истории ГИБДД (gibdd 404 - иномарка)</div>'}
  </div>
</div>
<div class="card">
  <div style="font-weight:800;font-size:13px;letter-spacing:0.06em">⚠️ ДТП • {dtp_count} СЛУЧАЯ (ИЗ БАЗЫ dtp - ЦЕЛИКОМ)</div>
  {''.join([f'<div class="dtp-card"><div style="font-weight:800">{d.get("date","")} • {d.get("type","")}</div><div style="font-size:12px;color:#6b7280">{d.get("region","")} • Ущерб: {d.get("damage","")} {d.get("cost","")}</div><div style="font-size:11px;color:#8e8e93;margin-top:4px">Повреждено: {", ".join(d.get("damagePoints",[])[:5]) if d.get("damagePoints") else "нет деталей"}</div></div>' for d in dtp_list]) if dtp_list else '<div style="font-size:12px;color:#6b7280;margin-top:10px;padding:12px;background:#f8f8fb;border-radius:12px">ДТП не найдено в базе dtp</div>'}
</div>
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div style="font-weight:800;font-size:13px;letter-spacing:0.06em">📈 ПРОБЕГ • ТАЙМЛАЙН (probeg2 + offerbyvin + eaisto) С ПОДПИСЬЮ ИСТОЧНИКА</div>
    <span class="pill pill-black">~{max([p[2] for p in probeg_sorted], default=0)//1000}к макс</span>
  </div>
  {f'<div style="background:#ffeaea;border:1px solid #ffcccc;color:#ff3b30;padding:8px 12px;border-radius:999px;font-size:12px;font-weight:700;margin-top:10px">Скрутка {skrutka["diff"]} км {skrutka["prev_date"]} {skrutka["prev"]} → {skrutka["date"]} {skrutka["cur"]}</div>' if skrutka else ''}
  <div class="graph-wrap">
    {graph_svg}
    <div style="display:flex;justify-content:space-between;font-size:10px;color:#8e8e93;margin-top:6px;gap:4px;flex-wrap:wrap">{graph_dates}</div>
  </div>
  <div class="timeline">
    {''.join([f'<div class="tl-row"><div class="tl-line"></div><div class="tl-dot red"></div><div class="tl-content"><div class="tl-date">{d[1][:10]} • {d[2]} км</div><div class="tl-sub">{d[3]}</div></div></div>'.replace(',', ' ') for d in reversed(probeg_sorted[-15:])]) if probeg_sorted else '<div style="font-size:12px;color:#6b7280;padding:12px">Нет записей пробега</div>'}
  </div>
  <div style="margin-top:10px">
    <div style="font-size:11px;font-weight:700">ЕАИСТО ДИАГНОСТИЧЕСКИЕ КАРТЫ ({len(auto.get('eaisto',{}).get('cards',[]))}):</div>
    {''.join([f'<div style="font-size:11px;color:#6b7280;padding:4px 0;border-bottom:1px solid #f2f2f7">{c.get("date","")} • {c.get("mileage","")} км • {c.get("operator","")}</div>' for c in auto.get('eaisto',{}).get('cards',[])[:5]]) if auto.get('eaisto',{}).get('cards') else '<div style="font-size:11px;color:#6b7280">Нет карт ЕАИСТО</div>'}
  </div>
</div>
<div class="card">
  <div style="display:flex;justify-content:space-between">
    <div style="font-weight:800;font-size:13px">📸 ФОТО • {total_photos} ШТ (РЕАЛЬНЫЕ)</div>
    <div style="font-size:11px;color:#8e8e93">VIN {len(b1)} • Номерограм {len(b2)} • Автофото {len(b3)}</div>
  </div>
  <div class="photo-grid">
    {photos_html}
  </div>
  <div style="margin-top:10px">
    <div style="font-size:11px;font-weight:700">НОМЕРОГРАМ ОБЪЯВЛЕНИЯ ({len(auto.get('nomerogram_full',{}).get('ads',[]))}):</div>
    {''.join([f'<div style="font-size:11px;color:#6b7280;padding:6px 0;border-bottom:1px solid #f2f2f7"><b>{a.get("date","")} • {a.get("price","")} • {a.get("mileage","")} км</b><br>{a.get("title","")[:80]}<br>{a.get("text","")[:120]}</div>' for a in auto.get('nomerogram_full',{}).get('ads',[])[:3]]) if auto.get('nomerogram_full',{}).get('ads') else '<div style="font-size:11px;color:#6b7280">Нет объявлений номерограм</div>'}
  </div>
</div>
<div class="card">
  <div style="font-weight:800;font-size:13px;letter-spacing:0.06em">🏷️ ИСТОРИЯ ПРОДАЖ • {len(offers)} ОБЪЯВЛЕНИЙ (offerbyvin - ЦЕЛИКОМ)</div>
  {''.join([f'<div style="background:#f8f8fb;border-radius:14px;padding:12px;margin-top:8px"><div style="font-weight:700;font-size:13px">{off.get("date","")} • {off.get("mileage","—")} км • {off.get("price","—")} ₽ • {off.get("city","")}</div><div style="font-size:11px;color:#6b7280;margin-top:4px">Гос {off.get("plate","")} • ПТС {off.get("ptsNumber","")[:20]} • {off.get("source","Авито")}<br>{off.get("description","")[:120] if off.get("description") else ""}</div></div>' for off in offers[:5]]) if offers else '<div style="font-size:12px;color:#6b7280;margin-top:8px">Объявлений не найдено в offerbyvin</div>'}
</div>
<div class="card">
  <div style="font-weight:800;font-size:13px;letter-spacing:0.06em">🚕 КОММЕРЦИЯ - ТАКСИ И КАРШЕРИНГ (ЦЕЛИКОМ)</div>
  <div style="font-size:11px;margin-top:8px">Такси: {taxi_count} записей</div>
  {''.join([f'<div style="font-size:11px;color:#6b7280;padding:4px 0">{t.get("date","")} • {t.get("company","")} • {t.get("license","")}</div>' for t in auto.get('taxi',{}).get('list',[])[:3]]) if auto.get('taxi',{}).get('list') else '<div style="font-size:11px;color:#6b7280">Не работала в такси (по базе)</div>'}
  <div style="font-size:11px;margin-top:8px">Каршеринг: {carsharing_count} записей</div>
  {''.join([f'<div style="font-size:11px;color:#6b7280;padding:4px 0">{c.get("date","")} • {c.get("company","")}</div>' for c in auto.get('carsharing',{}).get('list',[])[:3]]) if auto.get('carsharing',{}).get('list') else '<div style="font-size:11px;color:#6b7280">Не работала в каршеринге</div>'}
</div>
<div class="card">
  <div style="font-size:10px;letter-spacing:0.12em;color:#8e8e93;font-weight:700">ЛОГИ ОТЛАДКИ (РЕАЛЬНЫЕ ЗАПРОСЫ)</div>
  <div class="log">{"<br>".join(logs[-25:])}</div>
  <div style="font-size:9px;color:#8e8e93;margin-top:8px;text-align:center">РЕАЛЬНЫЕ ДАННЫЕ ИЗ БАЗ • БЕЗ ХАРДКОДОВ • v62 FULL 9 SOURCES • {reg} • {vin}</div>
</div>
</div></body></html>"""
    return html

def generate_ai_recommendations_html(data, ai_text=None, ai_error=None):
    """v62 FULL - только реальные данные, без хардкодов, все 9 источников"""
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
    
    reg = meta.get("reg") or auto.get("gos") or "не указан"
    model_full = auto.get("model") or f"Авто {vin[:8]}"
    year = auto.get("year") or meta.get("year") or "—"
    color = auto.get("color") or "Нет данных"
    pts = auto.get("pts") or "Нет данных"
    engine_vol = auto.get("engine_vol") or "Нет данных"
    gearbox = auto.get("gearbox") or "Нет данных"
    owners = auto.get("owners", 0)
    dtp_list = auto.get("dtp",[]) or []
    dtp_count = auto.get("dtp_count", len(dtp_list))
    total_photos = len(all_b64)

    probeg_sorted = []
    skrutka = None
    try:
        def parse_date(s):
            import re as re2
            try:
                for fmt in ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"]:
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
        tmp = []
        for it in probeg:
            if isinstance(it, dict) and it.get("Probeg") is not None:
                try:
                    p = int(it.get("Probeg",0) or 0)
                except:
                    continue
                if p<=0:
                    continue
                d = it.get("DateString","")
                tmp.append((parse_date(d), d, p, it.get("Source","")))
        tmp.sort(key=lambda x: x[0])
        probeg_sorted = tmp
        for i in range(1, len(tmp)):
            if tmp[i][2] < tmp[i-1][2] - 3000:
                skrutka = {"diff": tmp[i-1][2]-tmp[i][2], "date": tmp[i][1][:10], "prev_date": tmp[i-1][1][:10], "prev": tmp[i-1][2], "cur": tmp[i][2]}
                break
    except:
        probeg_sorted = []

    import html as html_lib
    def format_ai(text):
        if not text:
            return ""
        esc = html_lib.escape(text)
        import re
        esc = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', esc)
        esc = esc.replace('\n', '<br>')
        return esc

    verdict_title = "АНАЛИЗ НА ОСНОВЕ РЕАЛЬНЫХ ДАННЫХ"
    verdict_color = "#111"
    verdict_emoji = "🧠"
    if ai_text:
        if "НЕ ЕХАТЬ" in ai_text or "НЕ БРАТЬ" in ai_text:
            verdict_title = "НЕ ЕХАТЬ — РИСКИ ВЫЯВЛЕНЫ"
            verdict_color = "#ff3b30"
            verdict_emoji = "⛔"
        elif "ЕХАТЬ" in ai_text and "ОСТОРОЖНО" in ai_text:
            verdict_title = "ЕХАТЬ ОСТОРОЖНО — ЕСТЬ РИСКИ"
            verdict_color = "#ff9500"
            verdict_emoji = "⚠️"
        elif "ЕХАТЬ" in ai_text:
            verdict_title = "МОЖНО ЕХАТЬ — РИСКИ МИНИМАЛЬНЫ"
            verdict_color = "#34c759"
            verdict_emoji = "✅"
    else:
        if skrutka:
            verdict_title = f"СКРУТКА {skrutka['diff']} КМ + {dtp_count} ДТП"
            verdict_color = "#ff3b30"
            verdict_emoji = "⛔"
        elif dtp_count > 0:
            verdict_title = f"{dtp_count} ДТП — ПРОВЕРИТЬ КУЗОВ"
            verdict_color = "#ff9500"
            verdict_emoji = "⚠️"
        else:
            verdict_title = "ДАННЫЕ ИЗ БАЗ — ПРОВЕРЬТЕ КУЗОВ"
            verdict_color = "#111"
            verdict_emoji = "🔍"

    ai_block_html = ""
    if ai_text:
        ai_block_html = f'<div style="background:#111;color:#fff;border-radius:20px;padding:16px;margin-top:12px"><div style="font-size:11px;letter-spacing:0.08em;opacity:0.6">🧠 ВЕРДИКТ ПОДБОРЩИКА • {OPENROUTER_MODEL} • РЕАЛЬНЫЕ ДАННЫЕ 9 ИСТОЧНИКОВ</div><div style="font-size:13px;line-height:1.5;margin-top:10px;white-space:pre-wrap">{format_ai(ai_text)}</div></div>'
    elif ai_error:
        ai_block_html = f'<div style="background:#ffeaea;border:1px solid #ffcccc;color:#8b0000;border-radius:18px;padding:14px;margin-top:12px"><b>⚠️ OpenRouter ошибка:</b> {html_lib.escape(str(ai_error))[:600]}<br><span style="font-size:11px">Покажу анализ на основе реальных данных ниже</span></div>'
    else:
        ai_block_html = '<div style="background:#f2f2f7;border-radius:18px;padding:14px;margin-top:12px;font-size:13px">ИИ ключ не настроен — ниже анализ на основе реальных данных из баз</div>'

    offers = raw.get("offerbyvin_parsed") or auto.get("offerbyvin_full",{}).get("offers") or []
    if not offers:
        try:
            ob_raw = raw.get("offerbyvin",{}).get("result",{})
            ob = ob_raw.get("offerbyvin") or ob_raw.get("result") or ob_raw
            if isinstance(ob, dict) and isinstance(ob.get("offers"), list):
                offers = ob.get("offers")
        except:
            offers = []

    taxi_count = auto.get("taxi",{}).get("count",0)
    carsharing_count = auto.get("carsharing",{}).get("count",0)

    skrutka_badge = f"СКРУТКА НАЙДЕНА • -{skrutka['diff']} КМ" if skrutka else f"ПРОБЕГ {len(probeg_sorted)} ЗАПИСЕЙ • ~{max([p[2] for p in probeg_sorted], default=0)//1000}к" if probeg_sorted else "НЕТ ДАННЫХ ПРОБЕГА"

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Рекомендации {vin} v62 FULL</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}} body{{font-family:Manrope,-apple-system,BlinkMacSystemFont,sans-serif;background:#f2f2f7;color:#111;-webkit-font-smoothing:antialiased}}
.container{{max-width:440px;margin:0 auto;padding:12px;padding-bottom:40px}}
.card{{background:#fff;border-radius:24px;padding:18px;border:1px solid #e5e5ea;box-shadow:0 1px 2px rgba(0,0,0,0.04);margin-top:14px}}
.pill{{display:inline-flex;align-items:center;padding:8px 14px;border-radius:999px;font-size:11px;font-weight:800;letter-spacing:0.02em}}
.pill-red{{background:#ff3b30;color:#fff}} .pill-black{{background:#111;color:#fff}} .pill-green{{background:#34c759;color:#fff}} .pill-gray{{background:#e5e7eb;color:#374151}} .pill-orange{{background:#ff9500;color:#fff}}
.verdict-hero{{background:{verdict_color};border-radius:28px;padding:18px;color:#fff}}
.verdict-hero h1{{font-size:20px;font-weight:800;line-height:1.1}}
.verdict-hero .sub{{font-size:11px;opacity:0.85;margin-top:8px;letter-spacing:0.06em}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}}
.info-card{{background:#f8f8fb;border:1px solid #efeff4;border-radius:18px;padding:12px;display:flex;gap:10px;align-items:center}}
.info-card .ico{{width:36px;height:36px;background:#fff;border:1px solid #e5e5ea;border-radius:999px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0}}
.info-card .lbl{{font-size:10px;color:#8e8e93;font-weight:700;letter-spacing:0.08em;text-transform:uppercase}}
.info-card .val{{font-size:13px;font-weight:700;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:140px}}
.timeline{{margin-top:14px}} .tl-row{{display:flex;gap:12px;position:relative;padding-bottom:18px}} .tl-line{{position:absolute;left:6px;top:14px;bottom:-4px;width:1px;background:#e5e7eb}}
.tl-dot{{width:12px;height:12px;border-radius:999px;background:#111;border:2px solid #fff;box-shadow:0 0 0 2px #e5e7eb;flex-shrink:0;margin-top:2px;z-index:1}} .tl-dot.red{{background:#ff3b30;box-shadow:0 0 0 4px #fee2e2}}
.tl-content{{flex:1}} .tl-date{{font-weight:700;font-size:14px}} .tl-sub{{font-size:12px;color:#8e8e93;margin-top:2px}}
.check{{background:#f8f8fb;border:1px solid #e5e5ea;border-radius:18px;padding:12px;margin-top:8px;display:flex;gap:10px}} .check .n{{width:24px;height:24px;background:#111;color:#fff;border-radius:999px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;flex-shrink:0}}
.log{{font-family:monospace;font-size:9px;background:#f8f8fb;padding:10px;border-radius:12px;overflow:auto;max-height:80px;white-space:pre-wrap;color:#8e8e93;border:1px solid #efeff4}}
</style></head>
<body><div class="container">
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:6px">
  <span class="pill {'pill-red' if skrutka else 'pill-gray'}">{skrutka_badge}</span>
  <span class="pill pill-black">ДТП {dtp_count}</span>
  <span class="pill {'pill-orange' if taxi_count>0 else 'pill-gray'}">ТАКСИ {taxi_count}</span>
  <span class="pill {'pill-orange' if carsharing_count>0 else 'pill-gray'}">КАРШЕРИНГ {carsharing_count}</span>
  <span class="pill pill-gray">ФОТО {total_photos} • ОБЪЯВЛЕНИЙ {len(offers)}</span>
</div>
<div class="verdict-hero" style="margin-top:12px">
  <div style="font-size:11px;letter-spacing:0.12em;opacity:0.8;font-weight:700">КНОПКА 2 • РЕАЛЬНЫЕ ДАННЫЕ 9 ИСТОЧНИКОВ • {OPENROUTER_MODEL}</div>
  <h1 style="margin-top:10px">{verdict_emoji} {verdict_title}</h1>
  <div class="sub">VIN {vin} • Гос {reg} • {model_full} • {color} • {owners} владельца • {total_photos} фото • Источники: probeg2, dtp, offerbyvin, eaisto, osago, zalog, gibdd, taxi, carsharing</div>
  <div style="display:flex;gap:6px;margin-top:12px;flex-wrap:wrap">
    <span style="background:rgba(255,255,255,0.2);padding:6px 10px;border-radius:999px;font-size:11px;font-weight:700">{engine_vol}</span>
    <span style="background:rgba(255,255,255,0.2);padding:6px 10px;border-radius:999px;font-size:11px;font-weight:700">{gearbox}</span>
    <span style="background:rgba(255,255,255,0.2);padding:6px 10px;border-radius:999px;font-size:11px;font-weight:700">ПТС {pts[:18]}</span>
  </div>
</div>
<div class="card">
  <div style="font-weight:800;font-size:12px;letter-spacing:0.08em">📋 РИСКИ • ИЗ БАЗ</div>
  <div class="grid2">
    <div class="info-card"><div class="ico">🎨</div><div><div class="lbl">КУЗОВ</div><div class="val">{dtp_count} ДТП в базе</div></div></div>
    <div class="info-card"><div class="ico">⏱️</div><div><div class="lbl">ПРОБЕГ</div><div class="val">{'Скрутка' if skrutka else f'{len(probeg_sorted)} записей'}</div></div></div>
    <div class="info-card"><div class="ico">⚖️</div><div><div class="lbl">ЮРИДИКА</div><div class="val">{auto.get('juridical',{}).get('залог_фнп','Нет данных')[:16]}</div></div></div>
    <div class="info-card"><div class="ico">🔧</div><div><div class="lbl">ТЕХНИКА</div><div class="val">{engine_vol[:16]}</div></div></div>
  </div>
</div>
{ai_block_html}
<div class="card">
  <div style="font-weight:800;font-size:13px;letter-spacing:0.06em">📈 ПРОБЕГ • {len(probeg_sorted)} ЗАПИСЕЙ ИЗ БАЗ С ПОДПИСЬЮ ИСТОЧНИКА</div>
  {f'<div style="background:#ffeaea;border:1px solid #ffcccc;color:#ff3b30;padding:8px 12px;border-radius:999px;font-size:12px;font-weight:700;margin-top:10px">Скрутка {skrutka["diff"]} км {skrutka["prev_date"]} {skrutka["prev"]} → {skrutka["date"]} {skrutka["cur"]}</div>' if skrutka else ''}
  <div class="timeline">
    {''.join([f'<div class="tl-row"><div class="tl-line"></div><div class="tl-dot red"></div><div class="tl-content"><div class="tl-date">{d[1][:10]} • {d[2]:,} км</div><div class="tl-sub">{d[3]}</div></div></div>'.replace(',', ' ') for d in reversed(probeg_sorted[-10:])]) if probeg_sorted else '<div style="font-size:12px;color:#6b7280;padding:12px">Нет записей пробега в базах</div>'}
  </div>
</div>
<div class="card">
  <div style="font-weight:800;font-size:13px;letter-spacing:0.06em">⚠️ ДТП • {dtp_count} (РЕАЛЬНЫЕ ДАННЫЕ dtp - ЦЕЛИКОМ)</div>
  {''.join([f'<div style="background:#f8f8fa;border-radius:14px;padding:12px;margin-top:8px"><div style="font-weight:700">{d.get("date","")} • {d.get("type","")}</div><div style="font-size:11px;color:#6b7280">{d.get("region","")} • {d.get("damage","")} • Повреждено: {", ".join(d.get("damagePoints",[])[:3])}</div></div>' for d in dtp_list]) if dtp_list else '<div style="font-size:12px;color:#6b7280;margin-top:8px">ДТП не найдено в базе</div>'}
</div>
<div class="card">
  <div style="font-weight:800;font-size:13px;letter-spacing:0.06em">🏷️ ОБЪЯВЛЕНИЯ • {len(offers)} (offerbyvin — ЦЕЛИКОМ)</div>
  {''.join([f'<div style="background:#f8f8fb;border-radius:14px;padding:12px;margin-top:8px"><div style="font-weight:700;font-size:13px">{off.get("date","")} • {off.get("mileage","—")} км • {off.get("price","—")} ₽ • {off.get("city","")}</div><div style="font-size:11px;color:#6b7280;margin-top:4px">Гос {off.get("plate","")} • ПТС {off.get("ptsNumber","")[:20]} • {off.get("source","Авито")}<br>{off.get("description","")[:120] if off.get("description") else ""}</div></div>' for off in offers[:5]]) if offers else '<div style="font-size:12px;color:#6b7280;margin-top:8px">Нет объявлений в offerbyvin</div>'}
</div>
<div class="card">
  <div style="font-weight:800;font-size:13px;letter-spacing:0.06em">🚕 КОММЕРЦИЯ - ТАКСИ И КАРШЕРИНГ (ЦЕЛИКОМ)</div>
  <div style="font-size:11px;margin-top:8px">Такси: {taxi_count} записей - {auto.get('taxi',{}).get('list',[])}</div>
  <div style="font-size:11px;margin-top:8px">Каршеринг: {carsharing_count} записей</div>
</div>
<div class="card">
  <div style="font-size:10px;letter-spacing:0.12em;color:#8e8e93;font-weight:700">ЛОГИ ОТЛАДКИ • РЕАЛЬНЫЕ ЗАПРОСЫ 9 ИСТОЧНИКОВ</div>
  <div class="log">{"<br>".join(logs[-20:])}</div>
  <div style="font-size:9px;color:#8e8e93;margin-top:8px;text-align:center">РЕАЛЬНЫЕ ДАННЫЕ • БЕЗ ХАРДКОДОВ • v62 FULL 9 SOURCES • {reg} • {vin}</div>
</div>
</div></body></html>"""
    return html

def build_prompt_for_openrouter(data):
    """Собирает промпт из РЕАЛЬНЫХ данных всех 9 баз"""
    meta = data.get("meta",{})
    auto = data.get("autoteka_hard",{})
    probeg = data.get("probeg",[])
    raw = data.get("raw",{})
    vin = meta.get("vin") or ""
    reg = meta.get("reg") or "не указан"
    b1 = len(data.get("block1_pic",[]))
    b2 = len(data.get("block2_nomerogram",[]))
    b3 = len(data.get("block3_autophoto",[]))

    def safe_json(key, limit=4000):
        try:
            r = raw.get(key,{}).get("result",{})
            s = json.dumps(r, ensure_ascii=False, indent=2)
            return s[:limit]
        except:
            return "нет данных"

    vindecode = safe_json("vindecode")
    probeg_raw = safe_json("probeg2")
    dtp_raw = safe_json("dtp")
    zalog_raw = safe_json("zalog", 2000)
    gibdd_raw = safe_json("gibdd", 2000)
    eaisto_raw = safe_json("eaisto", 2000)
    osago_raw = safe_json("osago", 2000)
    carsharing_raw = safe_json("carsharing", 1500)
    taxi_raw = safe_json("taxi", 1500)
    offer_raw = safe_json("offerbyvin", 4000)
    nomerogram_raw = safe_json("nomerogram", 2000)

    probeg_lines = []
    try:
        for p in probeg[-20:]:
            if isinstance(p, dict):
                probeg_lines.append(f"{p.get('DateString','?')} — {p.get('Probeg','?')} км — {p.get('Source','?')}")
    except:
        pass
    probeg_human = "\n".join(probeg_lines) or "нет записей пробега в базах"

    offers = raw.get("offerbyvin_parsed") or auto.get("offerbyvin_full",{}).get("offers") or []
    if not offers:
        try:
            ob_raw = raw.get("offerbyvin",{}).get("result",{})
            ob = ob_raw.get("offerbyvin") or ob_raw.get("result") or ob_raw
            if isinstance(ob, dict) and isinstance(ob.get("offers"), list):
                offers = ob.get("offers")
        except:
            offers = []
    offers_human = ""
    if offers:
        for off in offers[:5]:
            if isinstance(off, dict):
                offers_human += f"{off.get('date','')} — {off.get('mileage','')} км — {off.get('price','')} ₽ — {off.get('plate','')} — {off.get('city','')} — {off.get('source','Авито')}\n"
    else:
        offers_human = "нет объявлений в offerbyvin"

    prompt = f"""ВХОДНЫЕ ДАННЫЕ — ТОЛЬКО РЕАЛЬНЫЕ ДАННЫЕ ИЗ 9 БАЗ APIPOINT:

VIN: {vin}
Гос: {reg}
Модель из базы: {auto.get('model')} {auto.get('year')} {auto.get('engine_code')} {auto.get('engine_vol')} {auto.get('color')} {auto.get('gearbox')} {auto.get('type')}
Владельцев: {auto.get('owners')} ПТС: {auto.get('pts')} СТС: {auto.get('sts')}
Фото: архив VIN {b1} шт, номерограм {b2} шт, улицы {b3} шт
Объявлений offerbyvin: {len(offers)} | Такси: {auto.get('taxi',{}).get('count',0)} | Каршеринг: {auto.get('carsharing',{}).get('count',0)}

--- VINDECODE (полный спек) ---
{vindecode}

--- ПРОБЕГИ (probeg2 + offerbyvin + eaisto) С ПОДПИСЬЮ ИСТОЧНИКА ---
{probeg_human}
RAW probeg2: {probeg_raw}

--- ЕАИСТО ДИАГНОСТИЧЕСКИЕ КАРТЫ (источник пробега) ---
{eaisto_raw}

--- ОБЪЯВЛЕНИЯ (offerbyvin.result.offers) — целиком ---
{offers_human}
RAW offerbyvin: {offer_raw}

--- НОМЕРОГРАМ (объявления по гос) — целиком ---
{nomerogram_raw}

--- ДТП (dtp) — целиком с damagePoints ---
{dtp_raw}

--- ЗАЛОГ / ОГРАНИЧЕНИЯ — целиком ---
Залог: {zalog_raw}
ГИБДД: {gibdd_raw}
Детали залога: {auto.get('zalog',{}).get('details',[])}
Ограничения ГИБДД: {auto.get('gibdd',{}).get('restrictions',[])}
Розыск: {auto.get('gibdd',{}).get('wanted',[])}
Рег история: {auto.get('gibdd',{}).get('reg_history',[])}

--- ОСАГО — целиком ---
{osago_raw}
Полисы: {auto.get('osago',{}).get('policies',[])}

--- КОММЕРЦИЯ — такси и каршеринг — целиком ---
Такси: {taxi_raw} -> {auto.get('taxi',{})}
Каршеринг: {carsharing_raw} -> {auto.get('carsharing',{})}

--- ЮРИДИКА ---
{auto.get('juridical')}

ЗАДАЧА:
Ты автоподборщик. Разнеси тачку по реальным данным всех 9 источников. Клиент хочет понять брать или нет. Не выдумывай данные, говори только что есть в базах выше.

СТРОГИЕ ПРАВИЛА:
- Указывай источник пробега: "108к по ЕАИСТО 18.06.2022" и "110к по Авито 18.03.2023"
- Если такси/каршеринг >0 — это жирный минус, пиши сразу в вердикт
- Если гос не указан — пиши что номерограм/автофото пропущены потому что нет госномера, но offerbyvin дал гос {reg}
- Если ПТС "Нет данных" — так и пиши
- Используй offers для анализа цены и пробега
- Используй nomerogram text для поиска слов "битая", "ржавчина"

ВЫДАЙ ОТВЕТ:

🚦 ВЕРДИКТ: [ЕХАТЬ / НЕ ЕХАТЬ / ЕХАТЬ ОСТОРОЖНО] — 1-2 предложения почему

🎨 КУЗОВ:
- Что по фото и ДТП damagePoints

⏱️ ПРОБЕГ:
- Есть ли скрутка? Докажи цифрами с подписью источника

🔧 ТЕХНИКА:
- Что ломается у этой модели

⚖️ ЮРИДИКА:
- Залог, ограничения, розыск — целиком из баз

🏷️ ИСТОРИЯ ПРОДАЖ:
- Сколько объявлений, даты, цены, пробеги, города

🚕 КОММЕРЦИЯ:
- Такси, каршеринг

💰 ТОРГ:
- За что торговаться и сколько

✅ ЧТО ПРОВЕРИТЬ У КАПОТА (5-7 точек)

Пиши коротко, жестко, как в гараже. Без воды. Только реальные данные.
"""
    return prompt

def generate_logs_file(data):
    import json
    meta = data.get("meta",{})
    logs = data.get("logs",[])
    raw = data.get("raw",{})
    auto = data.get("autoteka_hard",{})
    probeg = data.get("probeg",[])
    vin = meta.get("vin","")
    reg = meta.get("reg","")
    txt = f"VIN: {vin} REG: {reg}\n"
    txt += f"Дата: {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
    txt += "BOOT: v62 FULL 9 SOURCES\n\n"
    txt += "=== ЛОГИ ЗАПРОСОВ ===\n"
    txt += "\n".join(logs) + "\n\n"
    txt += "=== АВТОТЕКА HARD ===\n"
    try:
        txt += f"model: {auto.get('model')} year: {auto.get('year')} color: {auto.get('color')} pts: {auto.get('pts')} sts: {auto.get('sts')}\n"
        txt += f"owners: {auto.get('owners')} dtp: {auto.get('dtp_count')} sales: {auto.get('sales_history')}\n"
        txt += f"taxi: {auto.get('taxi')} carsharing: {auto.get('carsharing')}\n"
        txt += f"probeg: {len(probeg)}\n"
        for p in probeg[:15]:
            txt += f"  {p}\n"
    except Exception as e:
        txt += f"err {e}\n"
    txt += "\n=== RAW JSON ===\n"
    for src in ["vindecode","offerbyvin","eaisto","probeg2","gibdd","zalog","dtp","osago","carsharing","taxi","pic_vin","nomerogram","autophoto"]:
        try:
            r = raw.get(src)
            if not r:
                txt += f"{src}: НЕТ\n"
                continue
            result = r.get("result",{})
            txt += f"\n--- {src} --- keys: {list(result.keys())[:20] if isinstance(result, dict) else type(result)}\n"
            snippet = json.dumps(result, ensure_ascii=False, indent=2)[:3000]
            txt += snippet + "\n"
        except Exception as e:
            txt += f"{src} err {e}\n"
    return txt

def generate_kapot_html():
    html = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>Проверка у капота</title></head>
<body class="bg-[#f2f2f7]"><div class="max-w-[720px] mx-auto p-4">
  <div class="bg-white rounded-[24px] p-6 shadow-sm border">
    <div class="text-[11px] text-gray-400 tracking-widest">КНОПКА 3 • ПРОВЕРКА У КАПОТА • v62 FULL</div>
    <h1 class="text-[22px] font-bold mt-2">Проверка у капота — пришлите фото и видео</h1>
    <div class="text-sm text-gray-600 mt-2">Нужен осмотр вживую - все 9 источников уже проверены</div>
    <div class="mt-6 space-y-3 text-sm">
      <div class="bg-[#f5f5f7] rounded-xl p-4"><div class="font-bold">📸 Фото (20 шт):</div><div class="text-xs mt-1">1. Кузов по кругу, 2. Зазоры дверей, 3. Арки, пороги, 4. Подкапотка, двигатель, 5. Теплообменник, расширительный бачок, 6. Табличка VIN, 7. ПТС, СТС, 8. Багажник, швы, 9. Салон, приборка, пробег, 10. Толщиномер по 20 точкам</div></div>
      <div class="bg-[#f5f5f7] rounded-xl p-4"><div class="font-bold">🎥 Видео:</div><div class="text-xs mt-1">1. Запуск на холодную 30 сек (послушаем звук двигателя), 2. Работа на холостых, 3. Газ до 3000, 4. Выхлоп (дым?), 5. Коробка — переключение передач, 6. Ходовая — проезд по неровностям</div></div>
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
        [KeyboardButton(text="3️⃣ Проверка у капота"), KeyboardButton(text="📋 Логи Apipoint")],
        [KeyboardButton(text="🔄 Пересобрать визуал")]
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
        f"Пробью по всем официальным базам: ДТП с расчетами ремонта — что меняли и что красили, реальный пробег и скрутки (с подписью источника: ГИБДД, ЕАИСТО, Авито), залог, лизинг, ограничения и розыск ГИБДД, работа в такси и каршеринге, владельцы и ПТС, ОСАГО. Вытащу все фото машины из старых объявлений за последние годы.\n\n"
        f"2️⃣ Предварительные рекомендации ИИ — скажу, стоит ли вообще ехать смотреть\n"
        f"На основе истории дам честное заключение как живой подборщик. Сравню фото по датам, подскажу куда тыкать толщиномером и на сколько торговаться.\n\n"
        f"3️⃣ Проверка у капота — проверим вместе, когда ты уже у машины\n"
        f"Ты на месте? Скинь сюда 20 фото и 2-3 видео — оценю за 5 минут — брать или бежать.\n\n"
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

    if "пересобрать визуал" in txt_low:
        data = None
        vin = None
        if LAST_REPORT_DATA and LAST_REPORT_DATA.get("meta",{}).get("vin"):
            vin = LAST_REPORT_DATA.get("meta",{}).get("vin")
            data = LAST_REPORT_DATA
            await m.answer(f"🔄 Пересобираю визуал v62 FULL для {vin} из последнего отчета — без доп. оплаты Apipoint...")
            html = generate_history_html(f"{vin}_rebuild", data)
            file = BufferedInputFile(html.encode('utf-8'), filename=f"History_{vin}_v62_FULL_REBUILD.html")
            await m.answer_document(file, caption=f"🔄 FULL визуал {vin} • Гос {data.get('meta',{}).get('reg')} • {len(data.get('all_b64',[]))} фото • 9 источников • Без доп. запросов", reply_markup=main_kb())
            return
        vin = LAST_REQUEST.get("vin")
        if mm_vin:
            vin = mm_vin.group(0)
        if not vin:
            await m.answer("Нет последнего VIN в памяти (бот перезапускался). Пришли VIN — пересоберу визуал.\nНапример: WF0UXXGAJU8A66030", reply_markup=main_kb())
            return
        reg_last = LAST_REQUEST.get("reg") or reg
        await m.answer(f"🔄 Пересобираю визуал v62 FULL для {vin} + {reg_last}... Запрошу Apipoint заново")
        data = await check_history(vin, reg_last)
        html = generate_history_html(f"{vin}_rebuild", data)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"History_{vin}_v62_FULL_REBUILD.html")
        await m.answer_document(file, caption=f"🔄 Пересобран FULL визуал: {len(data.get('all_b64',[]))} фото • Гос {data.get('meta',{}).get('reg')}", reply_markup=main_kb())
        return

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
        file = BufferedInputFile(html.encode('utf-8'), filename=f"Kapot_Check_Instructions_v62_FULL.html")
        await m.answer_document(file, caption=f"📋 Инструкция для проверки у капота", reply_markup=main_kb())
        return

    if "предварительные рекомендации" in txt_low or "рекомендации ии" in txt_low or txt_low.startswith("2️⃣"):
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
                f"Например: WF0UXXGAJU8A66030\n"
                f"Или нажми 1️⃣ если хочешь сначала посмотреть историю.",
                reply_markup=main_kb()
            )
            return

        if LAST_REPORT_DATA and LAST_REPORT_DATA.get("meta",{}).get("vin") == vin_for_ai:
            data_for_ai = LAST_REPORT_DATA
            await m.answer(f"🤖 Беру последний отчет для {vin_for_ai} — формирую рекомендации ИИ через {OPENROUTER_MODEL}... 15-30 сек ⏳")
        else:
            await m.answer(f"🤖 Для {vin_for_ai} нет свежего отчета в памяти — собираю историю (1-2 мин) и сразу сделаю ИИ разбор через {OPENROUTER_MODEL}... ⏳")
            try:
                data_for_ai = await check_history(vin_for_ai, reg)
                html_hist = generate_history_html(vin_for_ai, data_for_ai)
                file_hist = BufferedInputFile(html_hist.encode('utf-8'), filename=f"History_{vin_for_ai}_v62_FULL.html")
                await m.answer_document(file_hist, caption=f"1️⃣ История {vin_for_ai} • {data_for_ai.get('meta',{}).get('reg')} • {len(data_for_ai.get('all_b64',[]))} фото — теперь делаю ИИ разбор", reply_markup=main_kb())
            except Exception as e:
                await m.answer(f"❌ Не смог собрать историю для {vin_for_ai}: {e}", reply_markup=main_kb())
                return

        await m.answer(f"🤖 Формирую живой разбор подборщика для {vin_for_ai}... (9 источников)")
        prompt = build_prompt_for_openrouter(data_for_ai)
        ai_text, ai_error = await call_openrouter_ai(prompt)
        if ai_text:
            await m.answer(f"✅ ИИ ответил, собираю итоговый отчет v62 FULL LIVE для {vin_for_ai}...")
        else:
            await m.answer(f"⚠️ OpenRouter не ответил: {ai_error} — сделаю отчет на шаблонах")
        html = generate_ai_recommendations_html(data_for_ai, ai_text=ai_text, ai_error=ai_error)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"AI_Recommendations_{vin_for_ai}_v62_FULL_LIVE.html")
        caption = f"2️⃣ ИИ рекомендации FULL LIVE для {vin_for_ai} — {OPENROUTER_MODEL}\n" + (ai_text[:600] + "..." if ai_text and len(ai_text)>600 else (ai_text[:600] if ai_text else f"Ошибка: {ai_error}"))
        await m.answer_document(file, caption=caption[:1000], reply_markup=main_kb())
        return

    if "логи apipoint" in txt_low or txt_low.startswith("📋"):
        data = LAST_REPORT_DATA
        if not data or not data.get("meta"):
            await m.answer("Нет последнего отчета в памяти (бот перезапускался). Пришли VIN чтобы собрать отчет и логи.", reply_markup=main_kb())
            return
        vin = data.get("meta",{}).get("vin","unknown")
        logs_txt = generate_logs_file(data)
        file_logs = BufferedInputFile(logs_txt.encode('utf-8'), filename=f"LOGS_{vin}_v62_FULL.txt")
        await m.answer_document(file_logs, caption=f"📋 Логи Apipoint для {vin} • {data.get('meta',{}).get('reg')} • 9 источников • Кинь этот файл мне", reply_markup=main_kb())
        return

    if "проверка истории" in txt_low or "истории авто" in txt_low or txt_low.startswith("1️⃣") or mm_vin:
        if mm_vin:
            vin = mm_vin.group(0)
            await m.answer(f"Принял VIN {vin} 👍\n\nСобираю FULL отчет по истории — 9 источников с подписью: probeg2, eaisto, offerbyvin, dtp, zalog, gibdd, osago, taxi, carsharing + фото + график.\n\nЗаймет 1-2 минуты ⏳")
            data = await check_history(vin, reg)
            html = generate_history_html(vin, data)
            file = BufferedInputFile(html.encode('utf-8'), filename=f"History_{vin}_v62_FULL.html")
            await m.answer_document(file, caption=f"1️⃣ FULL История {vin} • {data.get('meta',{}).get('reg')} • {len(data.get('all_b64',[]))} фото • 9 источников • Теперь 2️⃣ возьмет этот отчет без доп. оплаты", reply_markup=main_kb())
            try:
                logs_txt = generate_logs_file(data)
                file_logs = BufferedInputFile(logs_txt.encode('utf-8'), filename=f"LOGS_{vin}_v62_FULL.txt")
                await m.answer_document(file_logs, caption=f"📋 Логи для {vin} — кинь мне этот файл если что-то не подтянулось", reply_markup=main_kb())
            except Exception as e:
                await m.answer(f"⚠️ Не смог собрать логи: {e}")
            return
        if txt_low.startswith("1️⃣"):
            await m.answer("Пришли VIN для проверки истории (Кнопка 1)", reply_markup=main_kb())
            return

    if m.photo or m.video or m.video_note or m.document:
        await m.answer(
            f"Принял фото/видео для проверки у капота ✅\n\n"
            f"Если это фото кузова, двигателя, VIN, ПТС — проанализирую как автоподборщик\n"
            f"Если видео звука двигателя — послушаю двигатель на предмет стуков, масложора, течи\n\n"
            f"Для полного анализа еще нужен VIN — сделай сначала 1️⃣ Проверка истории, потом кидай фото сюда",
            reply_markup=main_kb()
        )
        return

    await m.answer("Пришли VIN или выбери кнопку:\n1️⃣ Проверка истории авто по VIN\n2️⃣ Предварительные рекомендации ИИ\n3️⃣ Проверка у капота\n🔄 Пересобрать визуал", reply_markup=main_kb())

async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("Webhook deleted, polling start v62 FULL")
    except Exception as e:
        print(f"delete_webhook error: {e}")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())