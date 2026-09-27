# -*- coding: utf-8 -*-
"""
v66.1 - ТЕКУЩИЙ ГОС В КАРТОЧКУ + ВСЕ ГОС ДЛЯ ОБЪЯВЛЕНИЙ
- Карточка = строго по VIN (vindecode по VIN), но текущий госномер = самый свежий из всех источников
- Объявления = по ВСЕМ гос что находим (ТО eaisto, pic, offerbyvin, servicemaintenance, vin2number)
- servicemaintenance 26.3₽, gai 21₽, gibddhistory 2.1₽, autophoto 1.6₽
- vindecode 1.1 + vindecode2 3.2 фолбек, offerbyvin+offerbygosnum по каждому гос, vin2number 6₽
"""
import asyncio, os, re, json, base64, html as html_lib, logging, time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

try:
    from PIL import Image
    from io import BytesIO
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot_v65")

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
APIPOINT_KEY = (os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN") or "").strip()
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY") or "").strip()
OPENROUTER_MODEL = (os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini").strip()
APIPOINT_URL = "https://apipoint.ru/api/call"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

if not BOT_TOKEN:
    raise RuntimeError("Нет BOT_TOKEN")
if not APIPOINT_KEY:
    raise RuntimeError("Нет APIPOINT_KEY")

print(f"BOOT v66.1 CURRENT GOS IN CARD + ALL GOS FOR ADS model={OPENROUTER_MODEL} pil={HAS_PIL}")

USER_DATA: Dict[int, Dict[str, Any]] = {}
CACHE: Dict[str, Tuple[float, Any]] = {}
CACHE_TTL = 86400
COOLDOWN: Dict[int, float] = {}
MAX_B64_IMAGES = 6
MAX_IMAGE_BYTES = 2_500_000
_session: Optional[aiohttp.ClientSession] = None

async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=90, connect=15)
        _session = aiohttp.ClientSession(timeout=timeout)
    return _session

async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()

def get_user_data(uid: int) -> Dict[str, Any]:
    if uid not in USER_DATA:
        USER_DATA[uid] = {"last_request": {"vin": None, "reg": None, "ts": 0}, "last_report": {}}
    return USER_DATA[uid]

def cache_get(k: str):
    if k in CACHE:
        exp, val = CACHE[k]
        if time.time() < exp:
            return val
        del CACHE[k]
    return None

def cache_set(k: str, v: Any, ttl: int = CACHE_TTL):
    CACHE[k] = (time.time() + ttl, v)

def is_valid_vin(v: str) -> bool:
    if not v: return False
    v = v.upper().strip()
    return len(v) == 17 and bool(re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", v))

JAPANESE_BRANDS = {"TOYOTA","LEXUS","NISSAN","INFINITI","HONDA","ACURA","MAZDA","SUBARU","SUZUKI","DAIHATSU","MITSUBISHI","MITSUOKA","ISUZU"}

def is_frame_format(s: str) -> bool:
    """Фрейм-код японца: 7-15 символов [A-Z0-9-], обязательно дефис, пример NCP51-0012345, по доке апиПоинт /^[a-zA-Z0-9-]{7,15}$/"""
    if not s: return False
    s = s.strip().upper()
    if not (7 <= len(s) <= 15): return False
    if not re.fullmatch(r"[A-Z0-9-]{7,15}", s): return False
    if "-" not in s: return False
    if is_valid_vin(s): return False
    # типичные японские фреймы: буквы+цифры-дефис-цифры, напр. NCP51-0012345, DBA-ZVW30-123456
    # хотя бы одна буква и цифры
    if not re.search(r"[A-Z]", s): return False
    if not re.search(r"[0-9]", s): return False
    return True

def is_japanese_by_brand_or_vin(vin: str, brand: str) -> bool:
    if vin and vin.upper().startswith("J"): return True
    if brand:
        b = brand.upper().strip()
        for jb in JAPANESE_BRANDS:
            if jb in b or b in jb:
                return True
    return False

def should_call_frameapi(input_text: str, vin: str, body_number: str, brand: str, vindecode_empty: bool) -> Tuple[bool, Optional[str]]:
    """
    Решает, нужно ли бить frameapi 10.50₽.
    Возвращает (нужно?, frame_значение)
    Логика:
    1) Если пользователь ввел фрейм напрямую (NCP51-0012345) — обязательно бьем
    2) Если нашли body_number фрейм-формата и бренд японец и vindecode пустой/неполный — бьем
    3) Если body_number фрейм-формата и бренд японец, но vindecode полный — НЕ бьем (экономим), т.к. инфа уже есть
    """
    inp = (input_text or "").strip().upper()
    # случай 1: юзер ввел фрейм
    if is_frame_format(inp):
        return True, inp

    # случай 2: body_number из vindecode
    if body_number and is_frame_format(body_number):
        if is_japanese_by_brand_or_vin(vin, brand):
            # если vindecode пустой — точно нужен frameapi
            if vindecode_empty:
                return True, body_number.upper()
            # если есть модель/год — можно не бить, но для прулей лучше добить историю регистрации
            # экономим: бьем только если body_number отличается от VIN и содержит дефис
            return True, body_number.upper()
    
    return False, None

def parse_eaisto_date(d) -> str:
    if not d: return ""
    try:
        if isinstance(d, (int, float)):
            return datetime.fromtimestamp(int(d)).strftime("%d.%m.%Y")
        s = str(d).strip()
        if "." in s:
            sp = s.split(".")[0]
            if sp.isdigit() and len(sp) >= 10:
                try:
                    return datetime.fromtimestamp(int(sp[:10])).strftime("%d.%m.%Y")
                except: pass
        if s.isdigit():
            if len(s) == 10:
                try: return datetime.fromtimestamp(int(s)).strftime("%d.%m.%Y")
                except: pass
            if len(s) == 13:
                try: return datetime.fromtimestamp(int(s)//1000).strftime("%d.%m.%Y")
                except: pass
        m = re.search(r'(\d{10})', s)
        if m:
            try: return datetime.fromtimestamp(int(m.group(1))).strftime("%d.%m.%Y")
            except: pass
        for fmt in ["%d.%m.%Y", "%Y-%m-%d"]:
            try: return datetime.strptime(s[:10], fmt).strftime("%d.%m.%Y")
            except: pass
        return s[:10]
    except:
        return str(d)[:10]

def parse_date_for_sort(d) -> datetime:
    try:
        if not d: return datetime.min
        if isinstance(d, (int, float)):
            return datetime.fromtimestamp(int(d))
        s = str(d).strip()
        if s.isdigit() and len(s) == 10:
            return datetime.fromtimestamp(int(s))
        if s.isdigit() and len(s) == 13:
            return datetime.fromtimestamp(int(s)//1000)
        # try  DD.MM.YYYY
        for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d.%m.%Y %H:%M:%S"]:
            try:
                return datetime.strptime(s[:10], fmt)
            except: pass
        m = re.search(r'(\d{10})', s)
        if m:
            return datetime.fromtimestamp(int(m.group(1)))
    except:
        pass
    return datetime.min

async def apipoint_call(payload: Dict[str, Any], use_cache: bool = True) -> Tuple[int, Dict, str]:
    cache_key = f"{payload.get('sources')}:{payload.get('vin') or payload.get('regNum') or payload.get('gosnumber') or payload.get('gosnomer') or payload.get('frame') or ''}"
    if use_cache:
        c = cache_get(cache_key)
        if c:
            return 200, c, "CACHED"
    headers = {"Authorization": f"Bearer {APIPOINT_KEY}", "Content-Type": "application/json"}
    session = await get_session()
    for attempt in range(2):
        try:
            async with session.post(APIPOINT_URL, json=payload, headers=headers) as resp:
                txt = await resp.text()
                try: data = json.loads(txt)
                except: data = {"raw": txt[:10000]}
                if resp.status == 429 and attempt == 0:
                    await asyncio.sleep(2)
                    continue
                if resp.status == 200 and use_cache:
                    cache_set(cache_key, data)
                return resp.status, data, txt[:20000]
        except asyncio.TimeoutError:
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            return 0, {"error": "timeout"}, "timeout"
        except Exception as e:
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            return 0, {"error": str(e)}, str(e)
    return 0, {"error": "retry"}, "retry"

async def call_openrouter_ai(prompt_text: str, system_text: str = None):
    if not OPENROUTER_API_KEY:
        return None, "Нет ключа OPENROUTER"
    if not system_text:
        system_text = "Ты — злой, честный автоподборщик из Москвы с 15 лет опыта. Ненавидишь перекупов. Говори прямо, жестко, без воды, как другу в гараже. Если данных нет — пиши 'нет данных', не выдумывай."
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://t.me/GljanTachkuBot", "X-Title": "GljanTachkuBot v65"}
    payload = {"model": OPENROUTER_MODEL, "messages": [{"role": "system", "content": system_text}, {"role": "user", "content": prompt_text}], "temperature": 0.35, "max_tokens": 4000}
    try:
        session = await get_session()
        async with session.post(OPENROUTER_URL, json=payload, headers=headers) as resp:
            txt = await resp.text()
            try: data = json.loads(txt)
            except: return None, f"OpenRouter raw: {txt[:1000]}"
            if resp.status != 200:
                return None, f"OpenRouter {resp.status}: {txt[:1000]}"
            choices = data.get("choices") or []
            if choices:
                return (choices[0].get("message",{}).get("content") or "").strip(), None
            return None, f"No choices {str(data)[:800]}"
    except Exception as e:
        return None, f"Exception {e}"

async def download_image_any(url: str) -> Optional[str]:
    if not url or len(url) < 15: return None
    low = url.lower()
    if any(x in low for x in ["logo","icon","favicon","svg"]): return None
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "image/*,*/*"}
    if "platesmania" in low: headers["Referer"] = "https://platesmania.com/"
    if "avto-nomer" in low: headers["Referer"] = "https://avto-nomer.ru/"
    try:
        session = await get_session()
        async with session.get(url, headers=headers, allow_redirects=True) as resp:
            if resp.status != 200: return None
            ct = resp.headers.get("Content-Type","").lower()
            if "text/html" in ct: return None
            content = await resp.read()
            if len(content) < 6000 or len(content) > MAX_IMAGE_BYTES: return None
            if HAS_PIL:
                try:
                    img = Image.open(BytesIO(content)).convert("RGB")
                    img.thumbnail((800,800))
                    buf = BytesIO()
                    img.save(buf, format="JPEG", quality=80, optimize=True)
                    content = buf.getvalue()
                    mime = "image/jpeg"
                except:
                    mime = "image/jpeg"
            else:
                mime = "image/jpeg" if "jpeg" in ct or "jpg" in ct else "image/png"
            b64 = base64.b64encode(content).decode('utf-8')
            return f"data:{mime};base64,{b64}"
    except:
        return None

def get_autoteka_hard_for_vin(vin: str, reg: Optional[str]):
    return {
        "model": "", "year": "", "vin": vin, "gos": reg or "не указан", "pts": "", "sts": "", "engine_code": "", "engine_vol": "", "type": "", "color": "", "gearbox": "", "owners": 0, "sales_history": 0, "dtp_count": 0,
        "juridical": {"ограничения": "", "розыск": "", "залог_фнп": "", "арбитраж": "", "лизинг": ""},
        "dtp": [], "carsharing": {"count": 0, "list": []}, "taxi": {"count": 0, "list": []},
        "eaisto": {"cards": [], "last_mileage": 0}, "osago": {"policies": []}, "zalog": {"count": 0, "details": []},
        "gibdd": {"owners": [], "restrictions": [], "wanted": [], "reg_history": []},
        "vindecode_full": {}, "offerbyvin_full": {"offers": []}, "nomerogram_full": {"ads": []},
        "service": {"count": 0, "records": []},
        "gai": {"owners": [], "restrictions": [], "wanted": [], "reg_history": [], "count_owners": 0},
        "gibddhistory": {"count": 0, "records": []},
        "vin2number": {"gos": "", "list": [], "current": ""}
    }

def find_offers_list(obj):
    if isinstance(obj, dict):
        for k in ["offers","list","result","items"]:
            v = obj.get(k)
            if isinstance(v, list) and len(v)>0 and isinstance(v[0], dict):
                if any("mileage" in x or "plate" in x or "gosnomer" in x or "price" in x or "Title" in x for x in v[:2]):
                    return v
        for v in obj.values():
            r = find_offers_list(v)
            if r: return r
    elif isinstance(obj, list) and len(obj)>0 and isinstance(obj[0], dict):
        if any("mileage" in x or "plate" in x or "Title" in x for x in obj[:2]):
            return obj
        for item in obj:
            r = find_offers_list(item)
            if r: return r
    return None

def find_vindecode_dict(obj):
    if isinstance(obj, dict):
        if any(k.lower() in ["brand","make","model","modelname","year","productionyear"] for k in obj.keys()):
            return obj
        for v in obj.values():
            if isinstance(v, dict):
                r = find_vindecode_dict(v)
                if r: return r
            elif isinstance(v, list):
                for it in v:
                    if isinstance(it, dict):
                        r = find_vindecode_dict(it)
                        if r: return r
    return None

def get_nested_vindecode_data(raw):
    try:
        if isinstance(raw, dict):
            if "vindecode2" in raw and isinstance(raw["vindecode2"], dict):
                inner2 = raw["vindecode2"]
                for key in ["Data","result","decode","info"]:
                    if key in inner2 and isinstance(inner2[key], dict):
                        cand = inner2[key]
                        if isinstance(cand.get("Data"), dict):
                            return cand.get("Data")
                        if find_vindecode_dict(cand):
                            return find_vindecode_dict(cand) or cand
                if any(k.lower() in ["brand","make","model","complectation"] for k in inner2.keys()):
                    return inner2
                r = find_vindecode_dict(inner2)
                if r: return r
            if "vindecode" in raw and isinstance(raw["vindecode"], dict):
                inner = raw["vindecode"]
                if "decode" in inner and isinstance(inner["decode"], dict):
                    dec = inner["decode"]
                    if "Reports" in dec and isinstance(dec["Reports"], list) and dec["Reports"]:
                        data = dec["Reports"][0].get("Data")
                        if isinstance(data, dict): return data
                    if "Data" in dec and isinstance(dec["Data"], dict): return dec["Data"]
                r = find_vindecode_dict(inner)
                if r: return r
            if "decode" in raw and isinstance(raw["decode"], dict):
                dec = raw["decode"]
                if "Reports" in dec and isinstance(dec["Reports"], list) and dec["Reports"]:
                    data = dec["Reports"][0].get("Data")
                    if isinstance(data, dict): return data
            r = find_vindecode_dict(raw)
            if r: return r
    except: pass
    return None

def parse_gos_from_vin2number(raw) -> Optional[str]:
    try:
        if not isinstance(raw, dict): return None
        result = raw.get("result") or raw
        for key in ["gosnumber","gosnomer","regNum","number","plate","gos"]:
            v = result.get(key)
            if v and isinstance(v, str) and len(v) >= 6:
                if re.search(r'[АВЕКМНОРСТУХA-Z0-9]{2,}', v.upper()):
                    return v.strip().upper()
        inner = result.get("vin2number") or result.get("vin2Number") or {}
        if isinstance(inner, dict):
            for key in ["gosnumber","gosnomer","regNum","number","plate"]:
                v = inner.get(key)
                if v and isinstance(v, str) and len(v) >= 6:
                    return v.strip().upper()
            lst = inner.get("list") or inner.get("numbers") or inner.get("result") or []
            if isinstance(lst, list) and lst:
                first = lst[0]
                if isinstance(first, str):
                    return first.strip().upper()
                if isinstance(first, dict):
                    for k in ["gosnumber","gosnomer","number"]:
                        vv = first.get(k)
                        if vv: return str(vv).strip().upper()
        if isinstance(result.get("list"), list) and result["list"]:
            first = result["list"][0]
            if isinstance(first, dict):
                for k in ["gosnumber","gosnomer","number"]:
                    vv = first.get(k)
                    if vv: return str(vv).strip().upper()
    except:
        pass
    return None

def parse_all_gos_from_vin2number(raw) -> list:
    res = []
    try:
        result = raw.get("result") or raw
        # list variants
        for key in ["list","numbers","gosnumbers"]:
            lst = result.get(key)
            if isinstance(lst, list):
                for item in lst:
                    if isinstance(item, str) and len(item) >= 6:
                        res.append(item.strip().upper())
                    elif isinstance(item, dict):
                        for k in ["gosnumber","gosnomer","number","plate"]:
                            if item.get(k):
                                res.append(str(item[k]).strip().upper())
        inner = result.get("vin2number") or result.get("vin2Number") or {}
        if isinstance(inner, dict):
            for key in ["list","numbers"]:
                lst = inner.get(key)
                if isinstance(lst, list):
                    for item in lst:
                        if isinstance(item, str):
                            res.append(item.strip().upper())
                        elif isinstance(item, dict):
                            for k in ["gosnumber","gosnomer","number"]:
                                if item.get(k):
                                    res.append(str(item[k]).strip().upper())
            for k in ["gosnumber","gosnomer","number"]:
                if inner.get(k):
                    res.append(str(inner[k]).strip().upper())
    except:
        pass
    return list(set([r for r in res if len(r)>=6]))

async def check_history(vin: str, reg_num: Optional[str] = None, user_id: Optional[int] = None, original_input: Optional[str] = None) -> Dict[str, Any]:
    original_input = (original_input or vin or "").strip().upper()
    vin = vin.upper().strip()
    # если ввели фрейм вместо VIN - сразу идем в ветку frameapi
    is_input_frame = is_frame_format(original_input)
    if is_input_frame and not is_valid_vin(vin):
        # пользователь ввел фрейм NCP51-0012345, а не VIN
        vin = ""  # VIN неизвестен, будем добывать из frameapi
    combined = {
        "meta": {"vin": vin or original_input, "reg": reg_num or "не указан", "year": "", "all_gos_found": [], "input_is_frame": is_input_frame},
        "block1_pic": [], "block2_nomerogram": [], "block3_autophoto": [],
        "probeg": [], "all_b64": [], "raw": {}, "logs": [],
        "autoteka_hard": get_autoteka_hard_for_vin(vin or original_input, reg_num)
    }
    logs = combined["logs"]
    logs.append(f"START v66.1 uid={user_id} vin={vin} reg={reg_num} input={original_input} is_frame={is_input_frame}")

    # --- Для сбора всех гос и определения текущего ---
    all_gos_found = set()
    gos_candidates_with_date = []  # list of (date, gos) для определения текущего

    if reg_num and reg_num != "не указан":
        g = reg_num.upper().strip()
        all_gos_found.add(g)
        gos_candidates_with_date.append((datetime.now(), g))

    def add_gos_with_date(g, date_obj=None, source=""):
        if not g: return None
        gg = str(g).strip().upper()
        if len(gg) < 6: return None
        if not re.search(r'[АВЕКМНОРСТУХA-Z0-9]{2,}', gg): return None
        all_gos_found.add(gg)
        dt = date_obj if isinstance(date_obj, datetime) else parse_date_for_sort(date_obj) if date_obj else datetime.min
        gos_candidates_with_date.append((dt, gg, source))
        return gg

    actual_reg = reg_num  # будет перезаписан на текущий в конце

    async def fetch_one(name: str, payload: dict):
        st, data, _ = await apipoint_call(payload)
        return name, st, data

    # Если ввели фрейм напрямую (японец) — сразу бьем frameapi 10.50₽, это обязательно
    frame_api_data = None
    if is_input_frame:
        logs.append(f"Введен фрейм-код {original_input} -> бью frameapi 10.50₽ ОБЯЗАТЕЛЬНО")
        try:
            st_f, data_f, _ = await apipoint_call({"sources": "frameapi", "frame": original_input}, use_cache=False)
            combined["raw"]["frameapi"] = data_f
            frame_api_data = data_f
            logs.append(f"frameapi {original_input} -> {st_f}")
            # пробуем вытащить VIN и body из ответа
            try:
                res_f = data_f.get("result") or {}
                inner_f = res_f.get("frameapi") or res_f.get("result") or res_f
                if isinstance(inner_f, dict):
                    # иногда возвращает vin
                    maybe_vin = inner_f.get("vin") or inner_f.get("VIN") or ""
                    if maybe_vin and is_valid_vin(maybe_vin):
                        vin = maybe_vin.upper()
                        combined["meta"]["vin"] = vin
                        combined["autoteka_hard"]["vin"] = vin
                        logs.append(f"frameapi вернул VIN {vin}")
                    # body тоже
                    maybe_body = inner_f.get("frame") or inner_f.get("bodyNumber") or original_input
                    if maybe_body:
                        combined["meta"]["body_number"] = str(maybe_body).upper()
                        combined["autoteka_hard"]["body_number"] = str(maybe_body).upper()
            except Exception as e:
                logs.append(f"frameapi parse err {e}")
        except Exception as e:
            logs.append(f"frameapi exc {e}")

    first_sources = ["vindecode","offerbyvin","eaisto","probeg","probeg2","gibdd","zalog","dtp","osago","carsharing","taxi","servicemaintenance","gai","gibddhistory","elpts"]
    tasks = []
    if vin:
        tasks.append(fetch_one("pic_vin", {"sources": "pic", "vin": vin}))
        for src in first_sources:
            tasks.append(fetch_one(src, {"sources": src, "vin": vin}))
    else:
        # если VIN так и не получили из frameapi — бьем что можем по гос/фрейму, vindecode пропустим
        tasks.append(fetch_one("offerbyvin", {"sources": "offerbyvin", "vin": original_input}))  # вдруг найдет по фрейму как по VIN
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    pic_vin_data = None
    for r in results:
        if isinstance(r, Exception):
            logs.append(f"first batch exc {r}")
            continue
        name, st, data = r
        combined["raw"][name] = data
        logs.append(f"{name} -> {st}")
        if name == "pic_vin": pic_vin_data = data
        if name == "probeg2":
            try:
                res = data.get("result") or {}
                lst = []
                if isinstance(res, dict):
                    if isinstance(res.get("result"), list): lst = res.get("result")
                    elif isinstance(res.get("probeg2"), dict): lst = res.get("probeg2",{}).get("result",[])
                    elif isinstance(res.get("list"), list): lst = res.get("list")
                if lst:
                    combined["probeg"] = lst
            except: pass
        if name == "probeg":
            try:
                res = data.get("result") or {}
                inner = res.get("probeg") or res.get("result") or res
                if isinstance(inner, dict):
                    if inner.get("mileage") or inner.get("probeg") or inner.get("Probeg"):
                        mileage = inner.get("mileage") or inner.get("probeg") or inner.get("Probeg") or inner.get("value") or 0
                        date_str = inner.get("date") or inner.get("Date") or inner.get("dateString") or ""
                        try:
                            m_int = int(str(mileage).replace(" ","").replace("км",""))
                        except:
                            m_int = 0
                        if m_int>0:
                            if not combined["probeg"]:
                                combined["probeg"] = []
                            combined["probeg"].append({"DateString": str(date_str), "Probeg": m_int, "Source": "probeg 1.10₽ последняя запись"})
                            logs.append(f"probeg -> {m_int} км {date_str}")
                    elif isinstance(inner.get("result"), dict):
                        sub = inner.get("result")
                        mileage = sub.get("mileage") or sub.get("probeg") or 0
                        date_str = sub.get("date") or ""
                        try:
                            m_int = int(str(mileage).replace(" ",""))
                        except:
                            m_int = 0
                        if m_int>0:
                            if not combined["probeg"]:
                                combined["probeg"] = []
                            combined["probeg"].append({"DateString": str(date_str), "Probeg": m_int, "Source": "probeg 1.10₽ последняя запись"})
                elif isinstance(inner, list) and inner:
                    for item in inner:
                        if isinstance(item, dict):
                            mileage = item.get("mileage") or item.get("probeg") or 0
                            date_str = item.get("date") or ""
                            try:
                                m_int = int(str(mileage).replace(" ",""))
                            except:
                                continue
                            if m_int>0:
                                if not combined["probeg"]:
                                    combined["probeg"] = []
                                combined["probeg"].append({"DateString": str(date_str), "Probeg": m_int, "Source": "probeg 1.10₽"})
            except Exception as e:
                logs.append(f"probeg parse err {e}")

    # 1) pic по VIN
    try:
        if pic_vin_data:
            result = pic_vin_data.get("result") or {}
            pic_obj = result.get("pic") or result
            if isinstance(pic_obj, dict):
                gn = pic_obj.get("gosnomer") or pic_obj.get("gosnumber")
                if gn:
                    add_gos_with_date(gn, datetime.now(), "pic_vin")
    except Exception as e:
        logs.append(f"pic vin parse err {e}")

    # 2) offerbyvin - все plates
    try:
        ob_raw = combined["raw"].get("offerbyvin",{}).get("result",{})
        offers = find_offers_list(ob_raw) or []
        if offers:
            combined["raw"]["offerbyvin_parsed"] = offers
            combined["autoteka_hard"]["offerbyvin_full"]["offers"] = offers
            for off in offers[:15]:
                if not isinstance(off, dict): continue
                plate = off.get("plate") or off.get("gosnomer") or off.get("regNum") or off.get("gosnumber") or ""
                d = off.get("date") or off.get("publishDate") or off.get("created")
                if plate:
                    add_gos_with_date(plate, d, "offerbyvin")
    except Exception as e:
        logs.append(f"offerbyvin early err {e}")

    # helper для единого блока пробега
    def add_probeg_entry(date_obj_or_str, mileage, source_str):
        try:
            if not mileage: return
            m_int = int(str(mileage).replace(" ","").replace("км","").replace(",",""))
            if m_int <= 0: return
            date_str = ""
            if isinstance(date_obj_or_str, (int,float)):
                try:
                    date_str = datetime.fromtimestamp(int(date_obj_or_str)).strftime("%d.%m.%Y")
                except:
                    date_str = str(date_obj_or_str)
            else:
                date_str = str(date_obj_or_str or "")[:19]
            # дедупликация по дате+пробегу
            for existing in combined["probeg"]:
                if existing.get("Probeg")==m_int and existing.get("DateString")==date_str:
                    return
            combined["probeg"].append({"DateString": date_str, "Probeg": m_int, "Source": source_str})
        except Exception as e:
            logs.append(f"add_probeg_entry err {e} {mileage}")

    # 3) eaisto - ТО, берем все гос с датами + ПРОБЕГ в общий раздел
    try:
        ea_raw = combined["raw"].get("eaisto",{}).get("result",{})
        ea_inner = ea_raw.get("eaisto") or ea_raw.get("result") or ea_raw
        if isinstance(ea_inner, dict):
            cards = ea_inner.get("result") or ea_inner.get("list") or ea_inner.get("cards") or []
            if isinstance(cards, list):
                for c in cards[:20]:
                    if not isinstance(c, dict): continue
                    gos = c.get("gosnumber") or c.get("gosnomer") or c.get("regNum") or c.get("number") or ""
                    d = c.get("date") or c.get("issueDate") or c.get("createDate") or c.get("datestring") or ""
                    if gos:
                        add_gos_with_date(gos, d, "eaisto ТО")
                    # пробег из ЕАИСТО
                    prob = c.get("probeg") or c.get("mileage") or 0
                    if prob:
                        ds = c.get("datestring") or c.get("dateString") or d or ""
                        add_probeg_entry(ds, prob, f"ЕАИСТО {c.get('docname','диаг.карта')[:20]} {str(gos)[:12]}".strip())
    except Exception as e:
        logs.append(f"eaisto plate/probeg err {e}")

    # 4) servicemaintenance + пробег из дилерского ТО
    try:
        sm_raw = combined["raw"].get("servicemaintenance",{}).get("result",{})
        sm_inner = sm_raw.get("servicemaintenance") or sm_raw.get("result") or sm_raw
        if isinstance(sm_inner, dict):
            lst = sm_inner.get("list") or sm_inner.get("records") or sm_inner.get("result") or []
            if isinstance(lst, list):
                for rec in lst[:20]:
                    if not isinstance(rec, dict): continue
                    gos = rec.get("gosnumber") or rec.get("gosnomer") or rec.get("regNum") or ""
                    d = rec.get("date") or rec.get("serviceDate") or rec.get("dateString") or ""
                    if gos:
                        add_gos_with_date(gos, d, "servicemaintenance")
                    # пробег из ТО
                    prob = rec.get("mileage") or rec.get("probeg") or rec.get("odometer") or 0
                    if prob:
                        add_probeg_entry(d, prob, f"ТО дилера {rec.get('dealer','')[:20]} {str(gos)[:12]}".strip())
    except Exception as e:
        logs.append(f"servicemaintenance plate/probeg err {e}")

    # 4b) offerbyvin пробеги из объявлений
    try:
        offers_for_probeg = combined["raw"].get("offerbyvin_parsed") or []
        for off in offers_for_probeg[:20]:
            if not isinstance(off, dict): continue
            prob = off.get("mileage") or off.get("probeg") or off.get("odometer") or off.get("km") or 0
            d = off.get("date") or off.get("publishDate") or off.get("created") or ""
            if prob:
                add_probeg_entry(d, prob, f"Объявление {off.get('source','')[:15]} {off.get('plate','')[:12]}".strip())
    except Exception as e:
        logs.append(f"offer probeg err {e}")

    # 5) vin2number 6₽ - коммерческие базы, самый авторитетный для текущего гос
    current_from_v2n = None
    try:
        logs.append(f"собрано {len(all_gos_found)} гос до vin2number, добиваю vin2number 6₽")
        st_v2n, data_v2n, _ = await apipoint_call({"sources": "vin2number", "vin": vin}, use_cache=False)
        combined["raw"]["vin2number"] = data_v2n
        logs.append(f"vin2number -> {st_v2n}")
        all_from_v2n = parse_all_gos_from_vin2number(data_v2n)
        for g in all_from_v2n:
            add_gos_with_date(g, datetime.now(), "vin2number комм.база")
        gos_from_v2n = parse_gos_from_vin2number(data_v2n)
        if gos_from_v2n:
            current_from_v2n = gos_from_v2n
            add_gos_with_date(gos_from_v2n, datetime.now(), "vin2number CURRENT")
            logs.append(f"vin2number текущий гос {gos_from_v2n}, всего {len(all_gos_found)}")
    except Exception as e:
        logs.append(f"vin2number err {e}")

    # --- Определяем ТЕКУЩИЙ госномер для карточки ---
    # Приоритет: vin2number (коммерческие базы = самый свежий) > последний по дате из ТО/сервиски/объявлений > первый найденный
    current_gos = None
    if current_from_v2n:
        current_gos = current_from_v2n
        logs.append(f"текущий гос из vin2number: {current_gos}")
    else:
        # ищем самый свежий по дате среди кандидатов
        if gos_candidates_with_date:
            # сортируем по дате desc, у кого дата = min ставим в конец
            dated = [(d if isinstance(d, datetime) else parse_date_for_sort(d), g, src) for d,g,src in [x if len(x)==3 else (x[0], x[1], "") for x in gos_candidates_with_date]]
            dated_sorted = sorted(dated, key=lambda x: x[0], reverse=True)
            # берем первый у кого дата не min
            for dt, g, src in dated_sorted:
                if dt != datetime.min and g:
                    current_gos = g
                    logs.append(f"текущий гос из {src} по дате {dt}: {g}")
                    break
            if not current_gos:
                # если все даты пустые - берем последний добавленный
                current_gos = dated_sorted[0][1] if dated_sorted else None
                logs.append(f"текущий гос из последнего кандидата: {current_gos}")

    if not current_gos and all_gos_found:
        current_gos = list(all_gos_found)[0]
        logs.append(f"текущий гос fallback из all_gos_found: {current_gos}")

    # Ставим текущий в карточку
    if current_gos:
        actual_reg = current_gos
        combined["meta"]["reg"] = current_gos
        combined["meta"]["current_gos"] = current_gos
        combined["autoteka_hard"]["gos"] = current_gos
        combined["autoteka_hard"]["vin2number"]["current"] = current_gos
        combined["autoteka_hard"]["vin2number"]["gos"] = current_gos
        logs.append(f"✅ ТЕКУЩИЙ ГОС В КАРТОЧКУ: {current_gos}")

    combined["meta"]["all_gos_found"] = list(all_gos_found)
    combined["autoteka_hard"]["vin2number"]["list"] = list(all_gos_found)
    logs.append(f"ИТОГО госномеров для объявлений: {list(all_gos_found)} | текущий в карточку: {current_gos}")

    # Этап 2: по госномеру - объявления по ВСЕМ гос, остальное по текущему + ПТС/СТС
    second_tasks = []
    if all_gos_found:
        for idx, gos in enumerate(list(all_gos_found)[:5]):
            second_tasks.append(fetch_one(f"offerbygosnum_{idx}_{gos}", {"sources": "offerbygosnum", "gosnumber": gos}))
            second_tasks.append(fetch_one(f"offerbyvin_by_reg_{idx}_{gos}", {"sources": "offerbyvin", "regNum": gos}))
        if actual_reg and actual_reg != "не указан":
            second_tasks.append(fetch_one("vindecode_by_reg", {"sources": "vindecode", "regNum": actual_reg}))
            second_tasks.append(fetch_one("gibdd_by_reg", {"sources": "gibdd", "regNum": actual_reg}))
            second_tasks.append(fetch_one("dtp_by_reg", {"sources": "dtp", "regNum": actual_reg}))
            second_tasks.append(fetch_one("osago_by_reg", {"sources": "osago", "regNum": actual_reg}))
            second_tasks.append(fetch_one("pic_gos", {"sources": "pic", "gosnomer": actual_reg}))
            second_tasks.append(fetch_one("nomerogram", {"sources": "nomerogram", "regNum": actual_reg}))
            second_tasks.append(fetch_one("autophoto", {"sources": "autophoto", "regNum": actual_reg}))
            second_tasks.append(fetch_one("number2sts", {"sources": "number2sts", "number": actual_reg, "mode": "single"}))
    elif actual_reg and actual_reg != "не указан":
        second_tasks.append(fetch_one("offerbyvin_by_reg", {"sources": "offerbyvin", "regNum": actual_reg}))
        second_tasks.append(fetch_one("offerbygosnum", {"sources": "offerbygosnum", "gosnumber": actual_reg}))
        second_tasks.append(fetch_one("vindecode_by_reg", {"sources": "vindecode", "regNum": actual_reg}))
        second_tasks.append(fetch_one("gibdd_by_reg", {"sources": "gibdd", "regNum": actual_reg}))
        second_tasks.append(fetch_one("dtp_by_reg", {"sources": "dtp", "regNum": actual_reg}))
        second_tasks.append(fetch_one("osago_by_reg", {"sources": "osago", "regNum": actual_reg}))
        second_tasks.append(fetch_one("pic_gos", {"sources": "pic", "gosnomer": actual_reg}))
        second_tasks.append(fetch_one("nomerogram", {"sources": "nomerogram", "regNum": actual_reg}))
        second_tasks.append(fetch_one("autophoto", {"sources": "autophoto", "regNum": actual_reg}))
        second_tasks.append(fetch_one("number2sts", {"sources": "number2sts", "number": actual_reg, "mode": "single"}))

    if second_tasks:
        second_results = await asyncio.gather(*second_tasks, return_exceptions=True)
        for r in second_results:
            if isinstance(r, Exception):
                logs.append(f"second exc {r}")
                continue
            name, st, data = r
            combined["raw"][name] = data
            gos_log = name.split("_")[-1] if "_" in name else actual_reg
            logs.append(f"{name} {gos_log} -> {st}")
            if name.startswith("offerby") and st == 200:
                offers_gos = find_offers_list(data.get("result",{})) or []
                if not offers_gos:
                    inner = data.get("result",{}).get("offerbygosnum") or data.get("result",{}).get("offerbyvin") or data.get("result",{})
                    if isinstance(inner, dict):
                        offers_gos = inner.get("list") or inner.get("offers") or inner.get("result") or []
                        if not isinstance(offers_gos, list): offers_gos = []
                if offers_gos:
                    existing = combined["raw"].get("offerbyvin_parsed") or []
                    merged = existing[:]
                    for new_off in offers_gos:
                        if new_off not in merged:
                            merged.append(new_off)
                    combined["raw"]["offerbyvin_parsed"] = merged
                    logs.append(f"{name} +{len(offers_gos)} объяв (гос {gos_log}), всего {len(merged)}")
            if name.startswith("gibdd_by_reg") or name.startswith("dtp_by_reg") or name.startswith("osago_by_reg"):
                base = name.split("_by_reg")[0]
                if not combined["raw"].get(base) or not combined["raw"].get(base,{}).get("result"):
                    combined["raw"][base] = data

    # Этап 2б: если получили СТС из number2sts — добиваем getpts 5.30₽ для ПТС
    try:
        n2s_data = combined["raw"].get("number2sts",{}).get("result",{})
        sts_number = None
        if isinstance(n2s_data, dict):
            inner = n2s_data.get("number2sts") or n2s_data.get("result") or n2s_data
            if isinstance(inner, dict):
                sts_number = inner.get("sts") or inner.get("stsNumber") or inner.get("number") or inner.get("ctc") or inner.get("stc")
            elif isinstance(inner, list) and inner:
                first = inner[0] if isinstance(inner[0], dict) else {}
                sts_number = first.get("sts") or first.get("number")
        if sts_number and actual_reg:
            import re
            sts_clean = re.sub(r"\D", "", str(sts_number))
            if len(sts_clean)>=10:
                logs.append(f"number2sts дал СТС {sts_clean[:4]}...{sts_clean[-4:]} — бью getpts 5.30₽")
                st_g, data_g, _ = await apipoint_call({"sources": "getpts", "gosnumber": actual_reg, "sts": sts_clean}, use_cache=False)
                combined["raw"]["getpts"] = data_g
                logs.append(f"getpts -> {st_g}")
    except Exception as e:
        logs.append(f"getpts err {e}")

    # Фото
    photo_urls = []
    try:
        if pic_vin_data:
            result = pic_vin_data.get("result") or {}
            pic_obj = result.get("pic") or result
            if isinstance(pic_obj, dict):
                for url in (pic_obj.get("imageList") or [])[:10]:
                    photo_urls.append(("pic", url, f"Архив VIN {vin}"))
        pic_gos_data = combined["raw"].get("pic_gos",{}).get("result",{})
        if pic_gos_data:
            pic_obj = pic_gos_data.get("pic") or pic_gos_data
            if isinstance(pic_obj, dict):
                for url in (pic_obj.get("imageList") or [])[:10]:
                    photo_urls.append(("pic_gos", url, f"Архив гос {actual_reg}"))
        auto_raw = combined["raw"].get("autophoto",{}).get("result",{})
        auto_inner = auto_raw.get("autophoto") or auto_raw.get("result") or auto_raw
        if isinstance(auto_inner, dict):
            records = auto_inner.get("records") or auto_inner.get("list") or auto_inner.get("result") or []
            for rec in records[:15]:
                if not isinstance(rec, dict): continue
                best = rec.get("bigPhoto") or rec.get("urlphoto") or rec.get("urlPhoto") or ""
                if best:
                    if best.startswith("/"):
                        if "avto" in best or "ru31" in best:
                            best = "https://avto-nomer.ru" + best
                        else:
                            best = "https://platesmania.com" + best
                    photo_urls.append(("autophoto", best, f"Улица {rec.get('date','')[:10]}"))
        nom_raw = combined["raw"].get("nomerogram",{}).get("result",{})
        nom_inner = nom_raw.get("nomerogram") or nom_raw.get("result") or nom_raw
        if isinstance(nom_inner, dict):
            rez = nom_inner.get("rez") or nom_inner.get("list") or nom_inner.get("result") or []
            for r in rez[:10]:
                if not isinstance(r, dict): continue
                imgs = r.get("img") or []
                for img_url in imgs[:3]:
                    if img_url and len(str(img_url)) > 15:
                        photo_urls.append(("nomerogram", img_url, f"Номерограм {r.get('date','')[:10]}"))
    except Exception as e:
        logs.append(f"photo urls parse err {e}")

    photo_urls = photo_urls[:20]
    if photo_urls:
        async def dl_one(item):
            src, url, typ = item
            b64 = await download_image_any(url)
            return src, url, typ, b64
        dl_results = await asyncio.gather(*[dl_one(u) for u in photo_urls], return_exceptions=True)
        for r in dl_results:
            if isinstance(r, Exception): continue
            src, url, typ, b64 = r
            item_dict = {"source": src, "type": typ, "url": url, "gosnomer": actual_reg or "", "desc": typ}
            if b64 and len(combined["all_b64"]) < MAX_B64_IMAGES:
                item_dict["b64"] = b64
                combined["all_b64"].append(b64)
            combined["block1_pic"].append(item_dict)

    # --- Парсинг в autoteka_hard ---
    try:
        ah = combined["autoteka_hard"]
        vd_raw = combined["raw"].get("vindecode",{}).get("result",{})
        vd = get_nested_vindecode_data(vd_raw)
        if not vd:
            vd_raw_reg = combined["raw"].get("vindecode_by_reg",{}).get("result",{})
            vd = get_nested_vindecode_data(vd_raw_reg)
        if not vd or len(vd) < 2:
            logs.append("vindecode пустой -> пробую vindecode2 3.20₽")
            try:
                st2, data2, _ = await apipoint_call({"sources": "vindecode2", "vin": vin}, use_cache=False)
                combined["raw"]["vindecode2"] = data2
                logs.append(f"vindecode2 -> {st2}")
                vd2_raw = data2.get("result",{})
                vd2 = get_nested_vindecode_data(vd2_raw)
                if not vd2 and isinstance(vd2_raw, dict):
                    if isinstance(vd2_raw.get("vindecode2"), dict):
                        vd2 = get_nested_vindecode_data({"vindecode2": vd2_raw.get("vindecode2")})
                    else:
                        if any(k.lower() in ["brand","make","complectation","engine"] for k in vd2_raw.keys()):
                            vd2 = vd2_raw
                if isinstance(vd2, dict) and vd2:
                    vd = vd2
            except Exception as e:
                logs.append(f"vindecode2 err {e}")

        if isinstance(vd, dict) and vd:
            ah["vindecode_full"] = vd
            def get_ci(d,*keys):
                if not isinstance(d, dict): return ""
                lm = {k.lower(): v for k,v in d.items()}
                for k in keys:
                    if k.lower() in lm: return lm[k.lower()]
                return ""
            brand = get_ci(vd,"brand","make","BrandName") or ""
            model = get_ci(vd,"model","modelName") or ""
            year = get_ci(vd,"year","productionYear","modelYear","Year") or ""
            ev_raw = get_ci(vd,"engineVolume","EngineVolume")
            engine_vol = str(ev_raw.get("L") or ev_raw.get("Ccm") or ev_raw) if isinstance(ev_raw, dict) else str(ev_raw or "")
            pow_raw = get_ci(vd,"enginePower","power")
            power = str(pow_raw.get("Hp") or pow_raw.get("PS") or pow_raw) if isinstance(pow_raw, dict) else str(pow_raw or "")
            color = get_ci(vd,"color","bodyColor") or ""
            body = get_ci(vd,"body","BodyName","bodyType") or ""
            gearbox = get_ci(vd,"gearbox","transmission") or ""
            body_num = get_ci(vd,"bodyNumber","BodyNumber","bodyNo","chassisNumber","ChassisNumber","frameNumber","FrameNumber","frame","chassis","bodyNum","chassisNo","frameNo","numberBody") or ""
            chassis_num = get_ci(vd,"chassisNumber","ChassisNumber","chassis") or ""
            frame_num = get_ci(vd,"frameNumber","FrameNumber","frame") or ""
            if brand or model: ah["model"] = f"{brand} {model}".strip()
            if year:
                ah["year"] = str(year)
                combined["meta"]["year"] = str(year)
            if engine_vol or power:
                ah["engine_vol"] = f"{engine_vol} {power} л.с.".strip() if engine_vol and power else (engine_vol or power)
            if color: ah["color"] = str(color)
            if body: ah["type"] = str(body)
            if gearbox: ah["gearbox"] = str(gearbox)
            if body_num:
                ah["body_number"] = str(body_num).strip()
                combined["meta"]["body_number"] = str(body_num).strip()
                logs.append(f"body_number from vindecode: {body_num}")
            if chassis_num: ah["chassis_number"] = str(chassis_num).strip()
            if frame_num: ah["frame_number"] = str(frame_num).strip()
            # Умный вызов frameapi 10.50₽ только для японцев
            if not is_input_frame and not combined["raw"].get("frameapi"):
                vindecode_empty = not (brand or model or year)
                should_call, frame_val = should_call_frameapi(original_input, vin, body_num or chassis_num or frame_num, brand, vindecode_empty)
                if should_call and frame_val:
                    logs.append(f"Японец обнаружен: brand={brand} body={frame_val} -> бью frameapi 10.50₽ по необходимости")
                    try:
                        st_f, data_f, _ = await apipoint_call({"sources": "frameapi", "frame": frame_val}, use_cache=False)
                        combined["raw"]["frameapi"] = data_f
                        logs.append(f"frameapi {frame_val} -> {st_f}")
                        # парсим ответ frameapi для обогащения карточки
                        try:
                            res_f = data_f.get("result") or {}
                            inner_f = res_f.get("frameapi") or res_f.get("result") or res_f
                            if isinstance(inner_f, dict):
                                # модель/год могут прийти из frameapi
                                if not ah["model"]:
                                    b = inner_f.get("brand") or inner_f.get("make") or ""
                                    m = inner_f.get("model") or ""
                                    if b or m:
                                        ah["model"] = f"{b} {m}".strip()
                                if not ah["year"]:
                                    y = inner_f.get("year") or inner_f.get("productionYear") or ""
                                    if y:
                                        ah["year"] = str(y)
                                        combined["meta"]["year"] = str(y)
                                # пробеги из frameapi тоже могут быть
                                for key in ["mileage","probeg","odometer"]:
                                    if inner_f.get(key):
                                        try:
                                            m_int = int(str(inner_f.get(key)).replace(" ",""))
                                            if m_int>0:
                                                combined["probeg"].append({"DateString": "", "Probeg": m_int, "Source": f"frameapi {frame_val}"})
                                        except: pass
                        except Exception as e:
                            logs.append(f"frameapi enrich err {e}")
                    except Exception as e:
                        logs.append(f"frameapi conditional err {e}")
                else:
                    logs.append(f"frameapi НЕ вызываем: input={original_input} body={body_num} brand={brand} empty={vindecode_empty} -> экономим 10.50₽")

        gib_raw = combined["raw"].get("gibdd",{}).get("result",{})
        gib = gib_raw.get("gibdd") or gib_raw.get("result") or gib_raw
        if isinstance(gib, dict):
            if isinstance(gib.get("ownershipPeriods"), list) and gib.get("ownershipPeriods"):
                ah["owners"] = len(gib.get("ownershipPeriods"))
                ah["gibdd"]["owners"] = gib.get("ownershipPeriods")
            if isinstance(gib.get("registrationHistory"), list):
                ah["gibdd"]["reg_history"] = gib.get("registrationHistory")
            if isinstance(gib.get("restrictions"), list):
                ah["gibdd"]["restrictions"] = gib.get("restrictions")
                ah["juridical"]["ограничения"] = f"Найдено {len(gib.get('restrictions'))}" if gib.get("restrictions") else "Не найдены"
            if isinstance(gib.get("wanted"), list):
                ah["gibdd"]["wanted"] = gib.get("wanted")
                ah["juridical"]["розыск"] = f"Найдено {len(gib.get('wanted'))}" if gib.get("wanted") else "Не найден"

        try:
            gai_raw = combined["raw"].get("gai",{}).get("result",{})
            gai_inner = gai_raw.get("gai") or gai_raw.get("result") or gai_raw
            data_block = None
            if isinstance(gai_inner, dict):
                data_block = gai_inner.get("data") if isinstance(gai_inner.get("data"), dict) else None
                owners_list = None
                if isinstance(gai_inner.get("ownershipPeriods"), list):
                    owners_list = gai_inner.get("ownershipPeriods")
                elif isinstance(gai_inner.get("History"), list):
                    owners_list = gai_inner.get("History")
                elif data_block and isinstance(data_block.get("History"), list):
                    owners_list = data_block.get("History")
                if owners_list:
                    ah["gai"]["owners"] = owners_list
                    ah["gai"]["count_owners"] = len(owners_list)
                    if not ah["owners"]:
                        ah["owners"] = len(owners_list)
                    if data_block and data_block.get("Color"):
                        ah["color"] = data_block.get("Color")
                        combined["meta"]["color"] = data_block.get("Color")
                    if data_block and data_block.get("Marka"):
                        if not ah["model"]:
                            ah["model"] = f"{data_block.get('Marka')} {data_block.get('MarkaModel','')}".strip()
                if isinstance(gai_inner.get("restrictions"), list):
                    ah["gai"]["restrictions"] = gai_inner.get("restrictions")
                    if gai_inner.get("restrictions"):
                        ah["juridical"]["ограничения"] = f"GAI: {len(gai_inner.get('restrictions'))} огр."
                    elif not ah["juridical"]["ограничения"]:
                        ah["juridical"]["ограничения"] = "Не найдены (gai)"
                if isinstance(gai_inner.get("wanted"), list):
                    ah["gai"]["wanted"] = gai_inner.get("wanted")
                    if gai_inner.get("wanted"):
                        ah["juridical"]["розыск"] = f"GAI: в розыске {len(gai_inner.get('wanted'))}"
                if isinstance(gai_inner.get("registrationHistory"), list):
                    ah["gai"]["reg_history"] = gai_inner.get("registrationHistory")
                if data_block and isinstance(data_block.get("History"), list):
                    ah["gai"]["reg_history"] = data_block.get("History")
        except Exception as e:
            logs.append(f"gai parse err {e}")

        try:
            gh_raw = combined["raw"].get("gibddhistory",{}).get("result",{})
            gh_inner = gh_raw.get("gibddhistory") or gh_raw.get("result") or gh_raw
            records = []
            if isinstance(gh_inner, str):
                try:
                    import json as _json
                    parsed = _json.loads(gh_inner)
                    gh_inner = parsed
                except: pass
            if isinstance(gh_inner, dict):
                if isinstance(gh_inner.get("result"), str):
                    try:
                        import json as _json2
                        parsed2 = _json2.loads(gh_inner.get("result"))
                        if isinstance(parsed2, dict):
                            req = parsed2.get("RequestResult") or {}
                            if isinstance(req.get("periods"), list):
                                records = req.get("periods")
                            elif isinstance(parsed2.get("periods"), list):
                                records = parsed2.get("periods")
                    except: pass
                if not records:
                    if isinstance(gh_inner.get("list"), list): records = gh_inner.get("list")
                    elif isinstance(gh_inner.get("history"), list): records = gh_inner.get("history")
                    elif isinstance(gh_inner.get("result"), list): records = gh_inner.get("result")
                    elif isinstance(gh_inner.get("ownershipPeriods"), list): records = gh_inner.get("ownershipPeriods")
                    elif isinstance(gh_inner.get("periods"), list): records = gh_inner.get("periods")
                    else:
                        rr = gh_inner.get("RequestResult") or {}
                        if isinstance(rr.get("periods"), list):
                            records = rr.get("periods")
            elif isinstance(gh_inner, list):
                records = gh_inner
            ah["gibddhistory"]["records"] = records[:30]
            ah["gibddhistory"]["count"] = len(records)
            if records and not ah["owners"]:
                ah["owners"] = len(records)
        except Exception as e:
            logs.append(f"gibddhistory parse err {e}")

        try:
            dtp_raw = combined["raw"].get("dtp",{}).get("result",{})
            dtp_inner = dtp_raw.get("dtp") or dtp_raw
            dtp_list = []
            if isinstance(dtp_inner, dict):
                if isinstance(dtp_inner.get("list"), list): dtp_list = dtp_inner.get("list")
                elif isinstance(dtp_inner.get("result"), list): dtp_list = dtp_inner.get("result")
                count = dtp_inner.get("count") or len(dtp_list)
                ah["dtp_count"] = count
            elif isinstance(dtp_inner, list):
                dtp_list = dtp_inner
                ah["dtp_count"] = len(dtp_inner)
            norm = []
            for d in dtp_list[:10]:
                if not isinstance(d, dict): continue
                norm.append({"date": parse_eaisto_date(d.get("date") or d.get("accidentDate") or ""), "type": d.get("type") or "ДТП", "damage": d.get("damage") or "Нет данных", "damagePoints": d.get("damagePoints") or [], "region": d.get("region") or ""})
            ah["dtp"] = norm
        except Exception as e:
            logs.append(f"dtp parse err {e}")

        try:
            offers = combined["raw"].get("offerbyvin_parsed") or []
            if offers:
                ah["offerbyvin_full"]["offers"] = offers
                ah["sales_history"] = len(offers)
                for off in offers:
                    if not isinstance(off, dict): continue
                    d = parse_eaisto_date(off.get("date") or "")
                    m = off.get("mileage") or 0
                    try:
                        m_int = int(str(m).replace(" ","").replace("км","").strip() or 0)
                        if m_int>0 and not any(abs(x.get("Probeg",0)-m_int)<100 for x in combined["probeg"] if isinstance(x, dict)):
                            combined["probeg"].append({"DateString": str(d), "Probeg": m_int, "Source": f"Авито {off.get('city','')} {off.get('price','')}₽ {off.get('plate','') or off.get('gosnumber','')}"})
                    except: pass
        except Exception as e:
            logs.append(f"offerbyvin parse err {e}")

        try:
            ea_raw = combined["raw"].get("eaisto",{}).get("result",{})
            ea_inner = ea_raw.get("eaisto") or ea_raw.get("result") or ea_raw
            if isinstance(ea_inner, dict):
                cards = ea_inner.get("cards") or ea_inner.get("list") or ea_inner.get("result") or []
                if isinstance(cards, list):
                    for c in cards[:10]:
                        if not isinstance(c, dict): continue
                        d = parse_eaisto_date(c.get("date") or c.get("issueDate") or "")
                        m = c.get("mileage") or 0
                        try:
                            m_int = int(str(m).replace(" ","") or 0)
                            if m_int>0:
                                combined["probeg"].append({"DateString": str(d), "Probeg": m_int, "Source": f"ЕАИСТО ТО {c.get('operator','')} {c.get('gosnumber','')}"})
                                ah["eaisto"]["cards"].append({"date": str(d), "mileage": m_int, "operator": c.get("operator","")})
                        except: pass
        except Exception as e:
            logs.append(f"eaisto parse err {e}")

        try:
            sm_raw = combined["raw"].get("servicemaintenance",{}).get("result",{})
            sm_inner = sm_raw.get("servicemaintenance") or sm_raw.get("result") or sm_raw
            records = []
            if isinstance(sm_inner, dict):
                if isinstance(sm_inner.get("list"), list): records = sm_inner.get("list")
                elif isinstance(sm_inner.get("records"), list): records = sm_inner.get("records")
                elif isinstance(sm_inner.get("result"), list): records = sm_inner.get("result")
            elif isinstance(sm_inner, list):
                records = sm_inner
            norm_sm = []
            for rec in records[:30]:
                if not isinstance(rec, dict): continue
                d = parse_eaisto_date(rec.get("date") or rec.get("serviceDate") or "")
                m = rec.get("mileage") or rec.get("odometer") or 0
                try: m_int = int(str(m).replace(" ","") or 0)
                except: m_int = 0
                works = rec.get("works") or rec.get("workList") or []
                if isinstance(works, list):
                    works_str = ", ".join([str(w.get("name") or w)[:80] for w in works[:5]])
                else:
                    works_str = str(works)[:200]
                dealer = rec.get("dealer") or rec.get("service") or ""
                if m_int>0:
                    combined["probeg"].append({"DateString": str(d), "Probeg": m_int, "Source": f"Дилер ТО {dealer} {rec.get('gosnumber','')}"})
                norm_sm.append({"date": str(d), "mileage": m_int, "dealer": str(dealer)[:60], "works": works_str})
            ah["service"]["records"] = norm_sm
            ah["service"]["count"] = len(norm_sm)
        except Exception as e:
            logs.append(f"servicemaintenance parse err {e}")

        for src in ["carsharing","taxi"]:
            try:
                raw_src = combined["raw"].get(src,{}).get("result",{})
                inner = raw_src.get(src) or raw_src.get("result") or raw_src
                if isinstance(inner, dict):
                    lst = inner.get("list") or inner.get("items") or []
                    cnt = inner.get("count") or (len(lst) if isinstance(lst, list) else 0)
                    ah[src]["count"] = cnt if isinstance(cnt, int) else 0
                    ah[src]["list"] = lst if isinstance(lst, list) else []
                elif isinstance(inner, list):
                    ah[src]["count"] = len(inner)
                    ah[src]["list"] = inner
            except Exception as e:
                logs.append(f"{src} parse err {e}")

        try:
            os_raw = combined["raw"].get("osago",{}).get("result",{})
            os_inner = os_raw.get("osago") or os_raw.get("result") or os_raw
            if isinstance(os_inner, dict):
                pols = os_inner.get("policies") or os_inner.get("list") or []
                if isinstance(pols, list): ah["osago"]["policies"] = pols
            elif isinstance(os_inner, list):
                ah["osago"]["policies"] = os_inner
        except: pass

        try:
            zalog_raw = combined["raw"].get("zalog",{}).get("result",{})
            zalog_inner = zalog_raw.get("zalog") or zalog_raw
            if isinstance(zalog_inner, dict):
                lst = zalog_inner.get("list") or []
                cnt = zalog_inner.get("count") or len(lst)
                ah["zalog"]["count"] = cnt if isinstance(cnt, int) else 0
                ah["zalog"]["details"] = lst if isinstance(lst, list) else []
                ah["juridical"]["залог_фнп"] = f"Найдено {cnt}" if cnt and cnt>0 else "Не найден"
        except: pass

    except Exception as e:
        logs.append(f"enrich err {e}")

    return combined

def generate_history_html(target, data):
    meta = data.get("meta",{})
    auto = data.get("autoteka_hard",{})
    b1 = data.get("block1_pic",[])
    probeg = data.get("probeg",[])
    all_b64 = data.get("all_b64",[])
    logs = data.get("logs",[])
    raw = data.get("raw",{})

    vin = meta.get("vin") or auto.get("vin") or target
    reg = meta.get("reg") or auto.get("gos") or "не указан"
    current_gos = meta.get("current_gos") or reg
    all_gos = meta.get("all_gos_found",[])
    model_full = html_lib.escape(auto.get("model") or f"Авто {vin[:8]}")
    year = html_lib.escape(str(auto.get("year") or meta.get("year") or "—"))
    color = html_lib.escape(str(auto.get("color") or "Нет данных"))
    engine_vol = html_lib.escape(str(auto.get("engine_vol") or "Нет данных"))
    gearbox = html_lib.escape(str(auto.get("gearbox") or "Нет данных"))
    owners = auto.get("owners", 0)
    dtp_list = auto.get("dtp",[]) or []
    dtp_count = auto.get("dtp_count", len(dtp_list))
    total_photos = len(all_b64)

    probeg_sorted = []
    skrutka = None
    try:
        def parse_sort(s):
            if not s: return datetime.min
            s = str(s).strip()[:19]
            for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M"):
                try:
                    return datetime.strptime(s, fmt)
                except: 
                    pass
                try:
                    # пробуем обрезать до длины формата без % (костыль)
                    return datetime.strptime(s[:10], "%d.%m.%Y")
                except:
                    pass
            try:
                if str(s).isdigit() and len(str(s))>=10:
                    return datetime.fromtimestamp(int(str(s)[:10]))
            except: pass
            return datetime.min

        tmp = []
        seen = set()
        for it in probeg:
            if not isinstance(it, dict): continue
            # пробег может быть в разных ключах
            p_raw = it.get("Probeg") or it.get("probeg") or it.get("mileage") or it.get("Mileage") or 0
            try:
                p = int(str(p_raw).replace(" ","").replace("км","").replace(",","").strip() or 0)
            except: continue
            if p<=0: continue
            d_raw = it.get("DateString") or it.get("date") or it.get("Date") or it.get("datestring") or it.get("dateString") or ""
            src = it.get("Source") or it.get("SourceName") or it.get("source") or it.get("sourceName") or "—"
            # дедуп по дате+пробегу+источнику (чтобы не дублировать ЕАИСТО и probeg2 одну и ту же запись)
            key = (str(d_raw)[:10], p)
            if key in seen: 
                # если уже есть, но источник другой и более информативный — обновим
                # пропускаем дубли
                continue
            seen.add(key)
            tmp.append((parse_sort(d_raw), str(d_raw)[:19], p, str(src)[:80]))
        # сортируем по дате
        tmp.sort(key=lambda x: x[0])
        probeg_sorted = tmp
        # поиск скрутки
        for i in range(1, len(tmp)):
            if tmp[i][2] < tmp[i-1][2] - 500:
                skrutka = {"diff": tmp[i-1][2]-tmp[i][2], "date": tmp[i][1][:10], "prev_date": tmp[i-1][1][:10], "prev": tmp[i-1][2], "cur": tmp[i][2]}
                break
    except Exception as e:
        logs.append(f"probeg sort err {e}")
        probeg_sorted = []

    skrutka_badge = f"СКРУТКА -{skrutka['diff']} КМ" if skrutka else f"ПРОБЕГ {len(probeg_sorted)} ЗАПИСЕЙ"
    offers = raw.get("offerbyvin_parsed") or auto.get("offerbyvin_full",{}).get("offers") or []
    taxi_count = auto.get("taxi",{}).get("count",0)
    carsharing_count = auto.get("carsharing",{}).get("count",0)
    service_count = auto.get("service",{}).get("count",0)
    gai_rest = len(auto.get("gai",{}).get("restrictions",[]))
    gh_count = auto.get("gibddhistory",{}).get("count",0)

    photos_html = ""
    if b1:
        parts = []
        for it in b1[:MAX_B64_IMAGES]:
            b64 = it.get("b64","")
            img_tag = f'<img src="{b64}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover" />' if b64 else ""
            t = html_lib.escape(it.get("type","Фото")[:20])
            d = html_lib.escape(it.get("date","")[:10] or "—")
            parts.append(f'<div class="photo-cell"><div style="font-size:11px;color:#6b7280;z-index:1">{t}</div><span class="year">{d}</span>{img_tag}</div>')
        photos_html = "".join(parts)
    else:
        photos_html = '<div style="grid-column:1/-1;padding:20px;text-align:center;font-size:12px;color:#8e8e93">Нет фото</div>'

    safe_logs = "<br>".join([html_lib.escape(str(x)) for x in logs[-35:]])

    service_recs = auto.get("service",{}).get("records",[])[:5]
    if service_recs:
        service_html = "".join([f'<div style="font-size:11px;padding:6px 0;border-bottom:1px solid #f2f2f7"><b>{html_lib.escape(s.get("date",""))} • {s.get("mileage","")} км • {html_lib.escape(s.get("dealer","")[:40])}</b><br>{html_lib.escape(s.get("works","")[:120])}</div>' for s in service_recs])
    else:
        service_html = '<div style="font-size:11px;color:#6b7280">Нет данных дилерского ТО</div>'

    # Владельцы из gai / gibddhistory — с расшифровкой периода владения
    def parse_owner_date(s):
        if not s: return None
        s = str(s).strip()[:10]
        if s.lower() in ("н.в.", "н.в", "now", "наст.вр.", "текущий"): return datetime.now()
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(s[:10], fmt)
            except: pass
        # timestamp
        try:
            if s.isdigit() and len(s)>=8:
                return datetime.fromtimestamp(int(s[:10]))
        except: pass
        return None

    def format_duration(from_dt, to_dt):
        if not from_dt or not to_dt: return ""
        try:
            # пробуем точный расчет через relativedelta
            try:
                from dateutil.relativedelta import relativedelta
                rd = relativedelta(to_dt, from_dt)
                y = rd.years
                m = rd.months
                d = rd.days
                delta_days = (to_dt - from_dt).days
                if delta_days < 0: delta_days = 0
                txt = ""
                if y>0:
                    if y%10==1 and y%100!=11: txt+=f"{y} год "
                    elif 2<=y%10<=4 and not 12<=y%100<=14: txt+=f"{y} года "
                    else: txt+=f"{y} лет "
                if m>0:
                    txt+=f"{m} мес "
                if d>0 and y==0:
                    txt+=f"{d} дн "
                if not txt:
                    txt = f"{delta_days} дн "
                return txt.strip()
            except:
                # fallback простой
                delta_days = (to_dt - from_dt).days
                if delta_days < 0: delta_days = 0
                years = delta_days // 365
                rem = delta_days % 365
                months = rem // 30
                txt = ""
                if years>0:
                    if years%10==1 and years%100!=11: txt+=f"{years} год "
                    elif 2<=years%10<=4 and not 12<=years%100<=14: txt+=f"{years} года "
                    else: txt+=f"{years} лет "
                if months>0:
                    txt+=f"{months} мес "
                if not txt:
                    txt = f"{delta_days} дн "
                return txt.strip()
        except Exception as e:
            return ""

    owners_list = auto.get("gai",{}).get("owners") or auto.get("gibddhistory",{}).get("records") or auto.get("gibdd",{}).get("owners") or []
    owners_html = ""
    if owners_list:
        parts = []
        for idx, own in enumerate(owners_list[:10]):
            if not isinstance(own, dict): continue
            from_raw = own.get("From") or own.get("from") or own.get("startDate") or own.get("StartDate") or own.get("simpleDateFrom") or ""
            to_raw = own.get("To") or own.get("to") or own.get("endDate") or own.get("EndDate") or own.get("simpleDateTo") or "н.в."
            ptype = own.get("PersonType") or own.get("ownerType") or own.get("personType") or own.get("lastOwnerType") or "физлицо"
            # gai иногда хранит From/To внутри, а также From/To как строки
            if not from_raw:
                from_raw = own.get("from") or ""
            from_dt = parse_owner_date(from_raw)
            to_dt = parse_owner_date(to_raw)
            if to_raw and str(to_raw).lower().startswith("н.в"): to_dt = datetime.now()
            duration_txt = format_duration(from_dt, to_dt) if from_dt and to_dt else ""
            # красиво форматируем даты
            from_show = html_lib.escape(str(from_raw)[:10]) if from_raw else "?"
            to_show = html_lib.escape(str(to_raw)[:10]) if str(to_raw).lower() not in ("н.в.", "н.в") else "н.в."
            # если to_raw н.в. — показываем н.в.
            if str(to_raw).lower().startswith("н.в"):
                to_show = "н.в."
            parts.append(f'<div style="font-size:11px;padding:8px 0;border-bottom:1px solid #f2f2f7"><b>{idx+1}-й владелец:</b> {from_show} — {to_show}<br><span style="color:#6b7280">⏱ {html_lib.escape(duration_txt)} • {html_lib.escape(str(ptype)[:30])}</span></div>')
        owners_html = "".join(parts) if parts else '<div style="font-size:11px;color:#6b7280">Нет данных</div>'
    else:
        owners_html = '<div style="font-size:11px;color:#6b7280">Нет данных о владельцах (gai/gibddhistory 500 в этом прогоне, но в v65.6 было 3 владельца — см. Авито)</div>'

    # ЕАИСТО блок
    eaisto_raw = raw.get("eaisto",{}).get("result",{})
    eaisto_inner = eaisto_raw.get("eaisto") or eaisto_raw.get("result") or eaisto_raw
    eaisto_cards = []
    if isinstance(eaisto_inner, dict):
        eaisto_cards = eaisto_inner.get("result") or eaisto_inner.get("list") or eaisto_inner.get("cards") or []
    elif isinstance(eaisto_inner, list):
        eaisto_cards = eaisto_inner
    eaisto_html = ""
    if eaisto_cards:
        parts = []
        for c in eaisto_cards[:10]:
            if not isinstance(c, dict): continue
            ds = c.get("datestring") or c.get("dateString") or c.get("date") or ""
            prob = c.get("probeg") or c.get("mileage") or ""
            gos = c.get("gosnumber") or c.get("gosnomer") or ""
            doc = c.get("docname") or "Диаг.карта"
            parts.append(f'<div style="font-size:11px;padding:6px 0;border-bottom:1px solid #f2f2f7"><b>{html_lib.escape(str(ds)[:10])}</b> • {prob} км • {html_lib.escape(str(gos)[:12])} • {html_lib.escape(str(doc)[:20])}</div>')
        eaisto_html = "".join(parts)
    else:
        eaisto_html = '<div style="font-size:11px;color:#6b7280">Нет карт ТО</div>'

    # ПТС / СТС / ЭПТС блок — из number2sts + getpts + elpts
    pts_html = ""
    try:
        n2s_raw = raw.get("number2sts",{}).get("result",{})
        n2s_inner = n2s_raw.get("number2sts") or n2s_raw.get("result") or n2s_raw
        getpts_raw = raw.get("getpts",{}).get("result",{})
        getpts_inner = getpts_raw.get("getpts") or getpts_raw.get("result") or getpts_raw
        elpts_raw = raw.get("elpts",{}).get("result",{})
        elpts_inner = elpts_raw.get("elpts") or elpts_raw.get("result") or elpts_raw

        parts_pts = []
        if isinstance(n2s_inner, dict) and (n2s_inner.get("sts") or n2s_inner.get("number")):
            sts_val = n2s_inner.get("sts") or n2s_inner.get("number") or n2s_inner.get("ctc") or ""
            gos_val = n2s_inner.get("gosnumber") or n2s_inner.get("number") or current_gos
            parts_pts.append(f'<div style="font-size:11px;padding:6px 0;border-bottom:1px solid #f2f2f7"><b>СТС по гос {html_lib.escape(str(gos_val)[:12])}:</b> {html_lib.escape(str(sts_val)[:20])} (number2sts 2.00₽)</div>')
        elif isinstance(n2s_inner, list) and n2s_inner:
            for it in n2s_inner[:3]:
                if isinstance(it, dict):
                    sts_val = it.get("sts") or it.get("number") or ""
                    parts_pts.append(f'<div style="font-size:11px;padding:6px 0;border-bottom:1px solid #f2f2f7"><b>СТС:</b> {html_lib.escape(str(sts_val)[:20])}</div>')

        if isinstance(getpts_inner, dict) and (getpts_inner.get("pts") or getpts_inner.get("series") or getpts_inner.get("number")):
            ser = getpts_inner.get("series") or getpts_inner.get("seria") or ""
            num = getpts_inner.get("number") or getpts_inner.get("pts") or ""
            date = getpts_inner.get("date") or getpts_inner.get("issueDate") or ""
            sts_cur = getpts_inner.get("sts") or getpts_inner.get("currentSts") or ""
            parts_pts.append(f'<div style="font-size:11px;padding:6px 0;border-bottom:1px solid #f2f2f7"><b>ПТС (getpts 5.30₽):</b> {html_lib.escape(str(ser))} {html_lib.escape(str(num))} от {html_lib.escape(str(date)[:10])}<br>Текущий СТС: {html_lib.escape(str(sts_cur)[:20])}</div>')
        elif isinstance(getpts_inner, dict) and getpts_inner:
            # выводим сырые поля если структура другая
            dump = ", ".join([f"{k}={str(v)[:20]}" for k,v in list(getpts_inner.items())[:6]])
            if dump:
                parts_pts.append(f'<div style="font-size:11px;padding:6px 0;border-bottom:1px solid #f2f2f7"><b>getpts:</b> {html_lib.escape(dump)}</div>')

        if isinstance(elpts_inner, dict) and elpts_inner:
            status = elpts_inner.get("status") or elpts_inner.get("state") or ""
            util = elpts_inner.get("utilizationFee") or elpts_inner.get("uFee") or ""
            last_reg = elpts_inner.get("lastRegistration") or elpts_inner.get("lastAction") or ""
            parts_pts.append(f'<div style="font-size:11px;padding:6px 0;border-bottom:1px solid #f2f2f7"><b>ЭПТС (elpts 1.20₽):</b> статус {html_lib.escape(str(status)[:20])} • утил.сбор {html_lib.escape(str(util)[:20])}<br>Посл.рег: {html_lib.escape(str(last_reg)[:40])}</div>')
            if not parts_pts:
                # если elpts пустой, но есть данные
                dump2 = ", ".join([f"{k}={str(v)[:20]}" for k,v in list(elpts_inner.items())[:6]])
                parts_pts.append(f'<div style="font-size:11px;padding:6px 0">{html_lib.escape(dump2)}</div>')

        if parts_pts:
            pts_html = "".join(parts_pts)
        else:
            pts_html = '<div style="font-size:11px;color:#6b7280">Нет данных ПТС/СТС (number2sts 2₽ вернул пусто, getpts 5.3₽ требует СТС, elpts 1.2₽ — для ЭПТС, для 2008 авто ЭПТС может не быть). После добавления источников будут тут.</div>'
    except Exception as e:
        pts_html = f'<div style="font-size:11px;color:#ff3b30">Ошибка ПТС/СТС блока {html_lib.escape(str(e)[:80])}</div>'

    all_gos_html = "".join([f'<span style="background:#111;color:#fff;border-radius:999px;padding:6px 10px;font-size:10px;margin-right:4px">{html_lib.escape(g)}</span>' for g in all_gos[:6]])

    return f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>История {html_lib.escape(vin)} v66.1</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}} body{{font-family:Manrope,sans-serif;background:#f2f2f7;color:#111}} .container{{max-width:440px;margin:0 auto;padding:12px;padding-bottom:40px}} .card{{background:#fff;border-radius:24px;padding:18px;border:1px solid #e5e5ea;margin-top:14px}} .pill{{display:inline-flex;padding:8px 14px;border-radius:999px;font-size:11px;font-weight:800}} .pill-red{{background:#ff3b30;color:#fff}} .pill-black{{background:#111;color:#fff}} .pill-gray{{background:#e5e7eb;color:#374151}} .pill-orange{{background:#ff9500;color:#fff}} .pill-green{{background:#34c759;color:#fff}} .blue-hero{{background:linear-gradient(180deg,#c7d2fe 0%,#dbeafe 40%,#eff6ff 100%);border-radius:28px;padding:18px;border:1px solid #bfdbfe}} .photo-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:12px}} .photo-cell{{background:#f1f1f3;border-radius:16px;aspect-ratio:1;position:relative;overflow:hidden;border:1px solid #e5e5ea;display:flex;align-items:center;justify-content:center;padding:8px;text-align:center}} .photo-cell .year{{position:absolute;bottom:8px;left:8px;background:#111;color:#fff;font-size:11px;font-weight:700;padding:4px 8px;border-radius:999px}} .log{{font-family:monospace;font-size:9px;background:#f8f8fb;padding:10px;border-radius:12px;overflow:auto;max-height:140px;white-space:pre-wrap;color:#8e8e93;border:1px solid #efeff4}}</style></head><body><div class="container">
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:6px">
<span class="pill {'pill-red' if skrutka else 'pill-gray'}">{html_lib.escape(skrutka_badge)}</span>
<span class="pill pill-black">ДТП {dtp_count}</span>
<span class="pill {'pill-orange' if taxi_count>0 else 'pill-gray'}">ТАКСИ {taxi_count}</span>
<span class="pill {'pill-orange' if carsharing_count>0 else 'pill-gray'}">КАРШЕРИНГ {carsharing_count}</span>
<span class="pill {'pill-green' if service_count>0 else 'pill-gray'}">ТО ДИЛЕР {service_count}</span>
<span class="pill {'pill-orange' if gai_rest>0 else 'pill-gray'}">GAI {gai_rest} огр.</span>
<span class="pill pill-gray">КЭШ ГИБДД {gh_count}</span>
<span class="pill pill-black">ТЕКУЩИЙ {html_lib.escape(current_gos[:12])}</span>
</div>
<div class="blue-hero" style="margin-top:12px">
<h2 style="font-size:24px;font-weight:800">{model_full}</h2>
<div style="font-size:13px;color:#6b7280;margin-top:4px">{engine_vol} • {gearbox} • {color} • {year}</div>
<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
<span style="background:#111;color:#fff;border-radius:999px;padding:12px 18px;font-size:14px;font-weight:800"># ТЕКУЩИЙ {html_lib.escape(current_gos)}</span>
<span style="background:#fff;border:1px solid #e5e5ea;border-radius:999px;padding:10px 16px;font-size:12px">👥 {owners} • {len(offers)} объяв • {service_count} ТО</span>
</div>
<div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:4px">{all_gos_html}<span style="font-size:10px;color:#6b7280;margin-left:6px">все гос для объявлений ({len(all_gos)})</span></div>
</div>

<div class="card"><div style="font-weight:800;font-size:12px">👥 ВЛАДЕЛЬЦЫ • {owners} (из GAI/GIBDDHISTORY — есть в логах v65.6, в v66.1 GAI 500)</div><div style="margin-top:8px">{owners_html}</div></div>

<div class="card"><div style="font-weight:800;font-size:12px">📋 ЕАИСТО • диаг.карты {len(eaisto_cards)} (есть в логах, раньше не выводили)</div><div style="margin-top:8px">{eaisto_html}</div></div>

<div class="card"><div style="font-weight:800;font-size:12px">🔧 ДИЛЕРСКАЯ ИСТОРИЯ • {service_count} записей</div><div style="margin-top:8px">{service_html}</div></div>

<div class="card"><div style="font-weight:800;font-size:12px">📸 ФОТО {total_photos}</div><div class="photo-grid">{photos_html}</div></div>

<div class="card"><div style="font-weight:800;font-size:12px">📈 ПРОБЕГ {len(probeg_sorted)} записей — ЕДИНЫЙ РАЗДЕЛ (ЕАИСТО+probeg+probeg2+ТО+объявления+frameapi), сортировка РАННЯЯ → ПОЗДНЯЯ</div>
{''.join([f'<div style="font-size:12px;padding:8px 0;border-bottom:1px solid #f2f2f7;display:flex;justify-content:space-between;align-items:center;gap:8px"><div><b>{html_lib.escape(str(d[1][:10]))}</b> • {d[2]} км</div><span style="font-size:10px;background:#f2f2f7;border-radius:999px;padding:4px 8px;color:#6b7280;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{html_lib.escape(str(d[3])[:60])}</span></div>' for d in probeg_sorted]) if probeg_sorted else '<div style="font-size:12px;color:#6b7280">Нет записей</div>'}
</div>

<div class="card"><div style="font-weight:800;font-size:12px">📄 ПТС / СТС / ЭПТС — новые источники (помогут закрыть gap с Авито)</div><div style="margin-top:8px">{pts_html}</div></div>

<div class="card"><div class="log">{safe_logs}</div><div style="font-size:9px;color:#8e8e93;margin-top:8px;text-align:center">v66.1 CURRENT GOS={html_lib.escape(current_gos)} ALL={html_lib.escape(",".join(all_gos[:3]))} • {html_lib.escape(vin)}</div></div>
</div></body></html>"""

def build_prompt_for_openrouter(data: Dict[str, Any]) -> str:
    meta = data.get("meta",{})
    auto = data.get("autoteka_hard",{})
    probeg = data.get("probeg",[])[:25]
    raw = data.get("raw",{})
    vin = meta.get("vin") or ""
    reg = meta.get("reg") or "не указан"
    current_gos = meta.get("current_gos") or reg
    all_gos = meta.get("all_gos_found",[])
    offers = (raw.get("offerbyvin_parsed") or [])[:7]
    probeg_lines = []
    for p in probeg[-20:]:
        if isinstance(p, dict):
            probeg_lines.append(f"{p.get('DateString','?')} {p.get('Probeg','?')}км {p.get('Source','')}")
    probeg_human = "\n".join(probeg_lines) or "нет данных"
    offers_human = "\n".join([f"{off.get('date','')} {off.get('mileage','')}км {off.get('price','')}₽ {off.get('city','')} {off.get('plate','') or off.get('gosnumber','')}" for off in offers if isinstance(off, dict)]) or "нет объявлений"
    dtp = auto.get("dtp",[])[:5]
    dtp_human = "\n".join([f"{d.get('date','')} {d.get('type','')} {d.get('damage','')}" for d in dtp]) or "нет ДТП"
    service = auto.get("service",{}).get("records",[])[:7]
    service_human = "\n".join([f"{s.get('date','')} {s.get('mileage','')}км {s.get('dealer','')} {s.get('works','')[:80]}" for s in service]) or "нет дилер ТО"
    prompt = f"""VIN:{vin} ТЕКУЩИЙ ГОС:{current_gos} ВСЕ ГОС:{",".join(all_gos[:5])} Модель:{auto.get('model')} {auto.get('year')} {auto.get('engine_vol')} {auto.get('color')}
Владельцев:{auto.get('owners')} ДТП:{auto.get('dtp_count')} Объявлений:{len(offers)} Дилер ТО:{auto.get('service',{}).get('count',0)}

ПРОБЕГИ:
{probeg_human}

ДТП:
{dtp_human}

ДИЛЕР ТО:
{service_human}

ОБЪЯВЛЕНИЯ ПО ВСЕМ ГОС:
{offers_human}

Задача: вердикт ЕХАТЬ/НЕ ЕХАТЬ/ЕХАТЬ ОСТОРОЖНО + кузов, пробег (скрутка?), техника, юридика, торг. Текущий гос {current_gos} ставь в заголовок. Пиши жестко, коротко, по цифрам."""
    return prompt[:9000]

def generate_ai_recommendations_html(data, ai_text=None, ai_error=None):
    meta = data.get("meta",{})
    auto = data.get("autoteka_hard",{})
    vin = html_lib.escape(meta.get("vin") or "")
    reg = html_lib.escape(meta.get("current_gos") or meta.get("reg") or "не указан")
    model_full = html_lib.escape(auto.get("model") or f"Авто {vin[:8]}")
    verdict_title = "АНАЛИЗ 15 ИСТОЧНИКОВ"; verdict_color = "#111"; verdict_emoji = "🧠"
    if ai_text:
        up = ai_text.upper()
        if "НЕ ЕХАТЬ" in up or "НЕ БРАТЬ" in up: verdict_title = "НЕ ЕХАТЬ"; verdict_color = "#ff3b30"; verdict_emoji = "⛔"
        elif "ЕХАТЬ" in up and "ОСТОРОЖНО" in up: verdict_title = "ЕХАТЬ ОСТОРОЖНО"; verdict_color = "#ff9500"; verdict_emoji = "⚠️"
        elif "ЕХАТЬ" in up: verdict_title = "МОЖНО ЕХАТЬ"; verdict_color = "#34c759"; verdict_emoji = "✅"
    def format_ai(t):
        if not t: return ""
        esc = html_lib.escape(t)
        esc = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', esc)
        return esc.replace('\n','<br>')
    ai_block = f'<div style="background:#111;color:#fff;border-radius:20px;padding:16px;margin-top:12px"><div style="font-size:11px;opacity:0.6">🧠 {OPENROUTER_MODEL} • ТЕКУЩИЙ ГОС {reg}</div><div style="font-size:13px;line-height:1.5;margin-top:10px">{format_ai(ai_text)}</div></div>' if ai_text else f'<div style="background:#ffeaea;padding:14px;border-radius:18px;margin-top:12px"><b>Ошибка ИИ:</b> {html_lib.escape(str(ai_error))[:600]}</div>' if ai_error else '<div style="background:#f2f2f7;padding:14px;border-radius:18px;margin-top:12px">Нет ключа ИИ</div>'
    return f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ИИ {vin} {reg} v66.1</title><style>body{{font-family:Manrope,sans-serif;background:#f2f2f7;color:#111}} .container{{max-width:440px;margin:0 auto;padding:12px}} .card{{background:#fff;border-radius:24px;padding:18px;margin-top:14px;border:1px solid #e5e5ea}} .verdict{{background:{verdict_color};border-radius:28px;padding:18px;color:#fff}}</style></head><body><div class="container"><div class="verdict"><h1>{verdict_emoji} {verdict_title}</h1><div style="font-size:12px;opacity:0.85;margin-top:8px">{model_full} • ТЕКУЩИЙ {reg} • {vin}</div></div>{ai_block}</div></body></html>"""

def generate_kapot_html():
    return """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>Капот v66.1</title></head><body class="bg-[#f2f2f7]"><div class="max-w-[720px] mx-auto p-4"><div class="bg-white rounded-[24px] p-6 border"><div class="text-[11px] text-gray-400 tracking-widest">v66.1 CURRENT GOS</div><h1 class="text-[22px] font-bold mt-2">Проверка у капота</h1><div class="mt-6 space-y-3 text-sm"><div class="bg-green-50 border border-green-200 rounded-xl p-4"><div class="font-bold">✅ Текущий гос в карточку:</div><div class="text-xs mt-1">Теперь в карточке всегда текущий госномер (из vin2number комм.баз или последний по дате из ТО). А объявления ищем по всем гос что нашли.</div></div></div></div></div></body></html>"""

def generate_logs_file(data):
    meta = data.get("meta",{}); logs = data.get("logs",[]); raw = data.get("raw",{}); auto = data.get("autoteka_hard",{})
    vin = meta.get("vin",""); reg = meta.get("reg",""); current = meta.get("current_gos","")
    all_gos = meta.get("all_gos_found",[])
    txt = f"VIN: {vin} CURRENT: {current} REG: {reg}\nALL GOS: {all_gos}\nДата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\nBOOT: v66.1 CURRENT GOS\n\n=== ЛОГИ ===\n" + "\n".join(logs) + "\n\n"
    txt += f"model: {auto.get('model')} year: {auto.get('year')} owners: {auto.get('owners')} dtp: {auto.get('dtp_count')} current: {current} all_gos: {all_gos}\n"
    for src in ["vindecode","vindecode2","offerbyvin","eaisto","probeg2","gibdd","gai","gibddhistory","vin2number","servicemaintenance","zalog","dtp","osago","carsharing","taxi","pic_vin","pic_gos","autophoto","nomerogram"]:
        try:
            r = raw.get(src)
            if not r: continue
            result = r.get("result",{})
            snippet = json.dumps(result, ensure_ascii=False, indent=2)[:2500]
            txt += f"\n--- {src} ---\n{snippet}\n"
        except Exception as e:
            txt += f"{src} err {e}\n"
    for key in raw.keys():
        if key.startswith("offerbygosnum_") or key.startswith("offerbyvin_by_reg_"):
            try:
                r = raw.get(key)
                result = r.get("result",{})
                snippet = json.dumps(result, ensure_ascii=False, indent=2)[:2500]
                txt += f"\n--- {key} ---\n{snippet}\n"
            except Exception as e:
                txt += f"{key} err {e}\n"
    return txt

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="1️⃣ Проверка истории авто по VIN"), KeyboardButton(text="2️⃣ Предварительные рекомендации ИИ")],[KeyboardButton(text="3️⃣ Проверка у капота"), KeyboardButton(text="📋 Логи Apipoint")],[KeyboardButton(text="🔄 Пересобрать визуал")]], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    ud = get_user_data(m.from_user.id)
    ud["last_request"] = {"vin": None, "reg": None, "ts": 0}
    ud["last_report"] = {}
    await m.answer("Привет! v66.1 • ТЕКУЩИЙ ГОС В КАРТОЧКУ 👇\n\n✅ Карточка по VIN, но текущий госномер = самый свежий:\n   1) vin2number 6₽ комм.базы (приоритет)\n   2) последний по дате из ТО eaisto\n   3) из объявлений / дилер ТО\n\n✅ Объявления = по ВСЕМ гос что находим (до 5 номеров)\n\nПришли VIN.", reply_markup=main_kb())

@dp.message()
async def handle(m: types.Message):
    user_id = m.from_user.id
    now = time.time()
    if user_id in COOLDOWN and now - COOLDOWN[user_id] < 3:
        await m.answer("⏳ Чуть помедленнее...")
        return
    COOLDOWN[user_id] = now
    ud = get_user_data(user_id)
    text_raw = (m.text or "").strip()
    txt_low = (m.text or "").lower()
    mm_gos = re.search(r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}', text_raw.upper())
    mm_vin = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_raw.upper())
    # ищем фрейм NCP51-0012345 формат 7-15 с дефисом
    mm_frame = re.search(r'\b[A-Z0-9]{2,10}-[A-Z0-9]{4,10}\b', text_raw.upper())
    # более широкий поиск для frameapi: 7-15 [A-Z0-9-]
    if not mm_frame:
        # пробуем найти любой токен 7-15 с дефисом
        for token in re.findall(r'[A-Z0-9-]{7,15}', text_raw.upper()):
            if is_frame_format(token):
                mm_frame = re.match(r'.*', token)  # заглушка
                mm_frame = type('obj', (object,), {'group': lambda self, x=token: x})()
                break
    reg = mm_gos.group(0) if mm_gos else None
    vin_candidate = mm_vin.group(0) if mm_vin else None
    frame_candidate = None
    if mm_frame:
        try:
            # если это наш объект-заглушка
            fc = mm_frame.group(0) if callable(getattr(mm_frame, 'group', None)) else str(mm_frame)
            # mm_frame.group(0) для реального match
            if hasattr(mm_frame, 'group'):
                try:
                    fc_raw = mm_frame.group(0)
                except:
                    fc_raw = text_raw.upper()
            else:
                fc_raw = str(mm_frame)
            # вытаскиваем из текста токен который is_frame_format
            for tok in re.findall(r'[A-Z0-9-]{7,15}', text_raw.upper()):
                if is_frame_format(tok):
                    frame_candidate = tok
                    break
            if not frame_candidate and is_frame_format(fc_raw):
                frame_candidate = fc_raw
        except:
            pass
    # если нашли и VIN и фрейм — приоритет у VIN, но фрейм тоже запомним
    if not vin_candidate and frame_candidate:
        vin_candidate = None  # будет обработан как фрейм

    if "пересобрать визуал" in txt_low:
        data = ud.get("last_report")
        if data and data.get("meta",{}).get("vin"):
            vin = data.get("meta",{}).get("vin")
            await m.answer(f"🔄 Пересобираю v66.1 для {vin} из памяти...")
            html_out = generate_history_html(f"{vin}_rebuild", data)
            file = BufferedInputFile(html_out.encode('utf-8'), filename=f"History_{vin}_v66.1_REBUILD.html")
            await m.answer_document(file, caption=f"🔄 v66.1 REBUILD {vin} • ТЕКУЩИЙ {data.get('meta',{}).get('current_gos','')} • {len(data.get('all_b64',[]))} фото", reply_markup=main_kb())
            return
        if vin_candidate:
            await m.answer(f"🔄 Пересобираю v66.1 для {vin_candidate}...")
            data = await check_history(vin_candidate, reg, user_id)
            ud["last_report"] = data
            ud["last_request"] = {"vin": vin_candidate, "reg": reg, "ts": now}
            html_out = generate_history_html(vin_candidate, data)
            file = BufferedInputFile(html_out.encode('utf-8'), filename=f"History_{vin_candidate}_v66.1.html")
            await m.answer_document(file, caption=f"🔄 v66.1 {vin_candidate}", reply_markup=main_kb())
            return
        await m.answer("Нет VIN в памяти.", reply_markup=main_kb())
        return

    if "проверка у капота" in txt_low or txt_low.startswith("3️⃣"):
        await m.answer("3️⃣ Пришли 20 фото + видео. Сначала 1️⃣ чтобы я знал VIN.", reply_markup=main_kb())
        html_out = generate_kapot_html()
        file = BufferedInputFile(html_out.encode('utf-8'), filename=f"Kapot_v66.1.html")
        await m.answer_document(file, caption="📋 Инструкция v66.1 CURRENT GOS", reply_markup=main_kb())
        return

    if "предварительные рекомендации" in txt_low or "рекомендации ии" in txt_low or txt_low.startswith("2️⃣"):
        vin_for_ai = vin_candidate or ud.get("last_request",{}).get("vin") or ud.get("last_report",{}).get("meta",{}).get("vin")
        if not vin_for_ai:
            await m.answer("Пришли VIN для ИИ.", reply_markup=main_kb())
            return
        if not is_valid_vin(vin_for_ai):
            await m.answer(f"VIN {vin_for_ai} невалидный.", reply_markup=main_kb())
            return
        data_for_ai = None
        if ud.get("last_report") and ud["last_report"].get("meta",{}).get("vin") == vin_for_ai:
            data_for_ai = ud["last_report"]
            await m.answer(f"🤖 Беру из памяти {vin_for_ai} — ИИ разбор {OPENROUTER_MODEL}...")
        else:
            await m.answer(f"🤖 Собираю 15 источников для {vin_for_ai} и сразу ИИ...")
            try:
                await bot.send_chat_action(m.chat.id, "typing")
                data_for_ai = await check_history(vin_for_ai, reg, user_id)
                ud["last_report"] = data_for_ai
                ud["last_request"] = {"vin": vin_for_ai, "reg": reg, "ts": now}
                html_hist = generate_history_html(vin_for_ai, data_for_ai)
                file_hist = BufferedInputFile(html_hist.encode('utf-8'), filename=f"History_{vin_for_ai}_v66.1.html")
                await m.answer_document(file_hist, caption=f"1️⃣ История {vin_for_ai} • ТЕКУЩИЙ {data_for_ai.get('meta',{}).get('current_gos','')} • {len(data_for_ai.get('all_b64',[]))} фото", reply_markup=main_kb())
            except Exception as e:
                log.exception("check_history failed")
                await m.answer(f"❌ Ошибка: {e}", reply_markup=main_kb())
                return
        await bot.send_chat_action(m.chat.id, "typing")
        prompt = build_prompt_for_openrouter(data_for_ai)
        ai_text, ai_error = await call_openrouter_ai(prompt)
        html_out = generate_ai_recommendations_html(data_for_ai, ai_text=ai_text, ai_error=ai_error)
        file = BufferedInputFile(html_out.encode('utf-8'), filename=f"AI_{vin_for_ai}_v66.1.html")
        caption = (ai_text[:800] + "..." if ai_text and len(ai_text)>800 else ai_text or f"Ошибка: {ai_error}")[:1000]
        await m.answer_document(file, caption=caption, reply_markup=main_kb())
        return

    if "логи apipoint" in txt_low or txt_low.startswith("📋"):
        data = ud.get("last_report")
        if not data or not data.get("meta"):
            await m.answer("Нет отчета.", reply_markup=main_kb())
            return
        vin = data.get("meta",{}).get("vin","unknown")
        logs_txt = generate_logs_file(data)
        file_logs = BufferedInputFile(logs_txt.encode('utf-8'), filename=f"LOGS_{vin}_v66.1.txt")
        await m.answer_document(file_logs, caption=f"📋 Логи v66.1 {vin} ТЕКУЩИЙ {data.get('meta',{}).get('current_gos','')}", reply_markup=main_kb())
        return

    if "проверка истории" in txt_low or txt_low.startswith("1️⃣") or vin_candidate:
        if vin_candidate:
            if not is_valid_vin(vin_candidate):
                await m.answer(f"VIN {vin_candidate} невалидный.", reply_markup=main_kb())
                return
            await m.answer(f"Принял VIN {vin_candidate} 👍 v66.1 ТЕКУЩИЙ ГОС В КАРТОЧКУ + объявления по всем гос ⏳")
            await bot.send_chat_action(m.chat.id, "typing")
            try:
                data = await check_history(vin_candidate, reg, user_id)
                ud["last_report"] = data
                ud["last_request"] = {"vin": vin_candidate, "reg": reg, "ts": now}
                html_out = generate_history_html(vin_candidate, data)
                file = BufferedInputFile(html_out.encode('utf-8'), filename=f"History_{vin_candidate}_v66.1.html")
                await m.answer_document(file, caption=f"1️⃣ v66.1 {vin_candidate} • ТЕКУЩИЙ {data.get('meta',{}).get('current_gos','')} • ВСЕ ГОС: {','.join(data.get('meta',{}).get('all_gos_found',[])[:3])} • {len(data.get('all_b64',[]))} фото", reply_markup=main_kb())
                try:
                    logs_txt = generate_logs_file(data)
                    file_logs = BufferedInputFile(logs_txt.encode('utf-8'), filename=f"LOGS_{vin_candidate}_v66.1.txt")
                    await m.answer_document(file_logs, caption=f"📋 Логи {vin_candidate}", reply_markup=main_kb())
                except Exception as e:
                    await m.answer(f"⚠️ Логи: {e}")
            except Exception as e:
                log.exception("history failed")
                await m.answer(f"❌ Ошибка: {e}", reply_markup=main_kb())
            return
        if txt_low.startswith("1️⃣"):
            await m.answer("Пришли VIN 17 символов.", reply_markup=main_kb())
            return

    if m.photo or m.video or m.video_note or m.document:
        await m.answer("Принял фото/видео ✅ Сначала 1️⃣ чтобы я знал VIN.", reply_markup=main_kb())
        return

    await m.answer("Пришли VIN или выбери кнопку:\n1️⃣ История 15 источников\n2️⃣ ИИ\n3️⃣ У капота", reply_markup=main_kb())

async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        log.info("Webhook deleted, polling v66.1")
    except Exception as e:
        log.warning(f"delete_webhook {e}")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await close_session()

if __name__ == "__main__":
    asyncio.run(main())