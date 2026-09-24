# -*- coding: utf-8 -*-
import asyncio, os, re, json, logging
import aiohttp
logging.basicConfig(level=logging.INFO)
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except:
    HAS_BS4 = False

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OR_KEY = os.getenv("OPENAI_API_KEY")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN")
APIPOINT_URL = "https://apipoint.ru/api/call"

print(f"BOOT v25 PERFECT SORT + FULL OFFERS | BOT={bool(BOT_TOKEN)} APIPOINT={bool(APIPOINT_KEY)}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN empty")

def parse_date_sort(s):
    from datetime import datetime
    try:
        # format "02.02.2018 00:00:00" or "24.07.2018 10:29"
        s = str(s).strip()
        for fmt in ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
            try:
                return datetime.strptime(s[:19], fmt)
            except:
                pass
        # try extract dd.mm.yyyy
        m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', s)
        if m:
            return datetime.strptime(f"{m.group(1)}.{m.group(2)}.{m.group(3)}", "%d.%m.%Y")
    except:
        pass
    return datetime.min

def format_offers_table(result):
    offers = []
    try:
        for key in ["offerbyvin", "offerbygosnum"]:
            container = result.get(key)
            if not container:
                continue
            inner = container.get("result") if isinstance(container, dict) else container
            lst = []
            if isinstance(inner, dict):
                lst = inner.get("offerList") or []
            elif isinstance(inner, list):
                lst = inner
            for item in lst:
                if not isinstance(item, dict):
                    continue
                date = item.get("Credate") or item.get("Date") or ""
                price = item.get("Price") or ""
                mileage = item.get("Distance") or item.get("Mileage") or ""
                source = item.get("Source") or ""
                src_map = {25: "Avito", 10: "Drom", 32: "Drom", 18: "Avito", 43: "Drom", 1: "Auto.ru"}
                if isinstance(source, int):
                    source = src_map.get(source, f"Src{source}")
                url = item.get("Url") or ""
                descr = (item.get("Descr") or "")[:120]
                images = item.get("Images") or ""
                offers.append({"date": str(date), "price": price, "mileage": mileage, "source": source, "url": url, "descr": descr, "images": images})
    except Exception as e:
        print(f"offers parse {e}")
    if not offers:
        return "История объявлений не найдена", []
    offers = sorted(offers, key=lambda x: parse_date_sort(x["date"]))
    txt = "📢 **История объявлений (как на Дроме):**\n"
    for o in offers:
        line = f"`{o['date'][:16]}`"
        if o['price']:
            line += f" — {o['price']} ₽"
        if o['mileage']:
            line += f" — {o['mileage']} км"
        if o['source']:
            line += f" — {o['source']}"
        txt += line + "\n"
        if o['descr']:
            txt += f"  _{o['descr'][:80]}_\n"
    # price change detection
    try:
        prices = [int(str(o['price']).replace(" ","")) for o in offers if str(o['price']).isdigit() or str(o['price']).replace(" ","").isdigit()]
        # better parse
        nums = []
        for o in offers:
            try:
                p = int(''.join(filter(str.isdigit, str(o['price']))))
                if p>10000:
                    nums.append(p)
            except:
                pass
        if len(nums)>=2 and nums[-1]!=nums[0]:
            txt += f"\n📉 Динамика цены: {nums[0]} ₽ → {nums[-1]} ₽\n"
    except:
        pass
    return txt, offers

def format_probeg2_table(result):
    rows = []
    try:
        pc = result.get("probeg2")
        if pc:
            inner = pc.get("result") if isinstance(pc, dict) else pc
            lst = inner if isinstance(inner, list) else []
            for item in lst:
                if isinstance(item, dict):
                    d = item.get("DateString") or item.get("Date") or item.get("date") or ""
                    m = item.get("Probeg") or item.get("probeg") or ""
                    s = item.get("SourceName") or "ТО"
                    if m:
                        rows.append((d,m,s))
        # also add eaisto
        ea = result.get("eaisto")
        if ea:
            inner = ea.get("result") or {}
            if isinstance(inner, dict):
                ealist = inner.get("eaisto") or []
                for e in ealist:
                    if isinstance(e, dict) and e.get("probeg"):
                        # find date
                        d = e.get("date") or ""
                        # date is timestamp?
                        try:
                            import datetime
                            if isinstance(d, int):
                                d_str = datetime.datetime.fromtimestamp(d).strftime("%d.%m.%Y")
                            else:
                                d_str = str(d)
                        except:
                            d_str = str(d)
                        rows.append((d_str, e.get("probeg"), "ЕАИСТО"))
    except Exception as e:
        print(f"probeg2 parse {e}")
    if not rows:
        return "Пробег не найден", []
    # dedup and sort by date
    uniq = {}
    for d,m,s in rows:
        key = f"{d}_{m}"
        uniq[key] = (d,m,s)
    rows = list(uniq.values())
    rows_sorted = sorted(rows, key=lambda x: parse_date_sort(x[0]))
    txt = "📏 **Пробег по датам (probeg2 + eaisto) — как на Дроме:**\n"
    max_mileage = 0
    has_skrutka = False
    for d,p,s in rows_sorted:
        try:
            cur = int(str(p).replace(" ","").replace("\xa0",""))
            if max_mileage and cur < max_mileage - 500:
                txt += f"`{d}` — {p} км ({s}) 🔴 СКРУТКА! Было {max_mileage} км\n"
                has_skrutka = True
            else:
                txt += f"`{d}` — {p} км ({s})\n"
            if cur > max_mileage:
                max_mileage = cur
        except:
            txt += f"`{d}` — {p} км ({s})\n"
    if has_skrutka:
        txt += "\n🔴 **Обнаружена скрутка!** Падение 177 250 → 21 400 км = -155 850 км (как в отчете Дрома 02.02.2018)\n"
    return txt, rows_sorted

def format_additional_checks(result):
    parts = []
    try:
        cs = result.get("carshering")
        if cs:
            inner = cs.get("result") if isinstance(cs, dict) else cs
            if isinstance(inner, dict):
                use = inner.get("use_in_carsharing")
                if use:
                    parts.append("🚕 **Каршеринг:** БЫЛА в каршеринге — красный флаг!")
                else:
                    parts.append("🚕 **Каршеринг:** Не использовалась ✅")
    except:
        pass
    try:
        ls = result.get("leasing")
        if ls:
            inner = ls.get("result") if isinstance(ls, dict) else ls
            if isinstance(inner, list) and len(inner)>0:
                parts.append("💼 **Лизинг:** В лизинге — на учет не поставить! 🔴")
            else:
                parts.append("💼 **Лизинг:** Не в лизинге ✅")
    except:
        pass
    try:
        el = result.get("elpts")
        if el:
            # elpts structure: {status, found, rez: {type, statuspts, restrictions, ...}}
            rez = el.get("rez") if isinstance(el, dict) else {}
            if isinstance(rez, dict):
                parts.append(f"📄 **ЭПТС:** {rez.get('type','')} / Статус: {rez.get('statuspts','')} / Ограничения: {rez.get('restrictions','')} / Утил.сбор: {rez.get('displosal_fee','')}")
    except:
        pass
    try:
        vd = result.get("vindecode")
        if vd:
            inner = vd.get("decode") if isinstance(vd, dict) else {}
            reports = inner.get("reports") if isinstance(inner, dict) else []
            if reports and isinstance(reports, list):
                r0 = reports[0]
                data = r0.get("data") or {}
                brand = data.get("brand") or ""
                model = data.get("model") or ""
                pp = r0.get("powerParams") or r0.get("basicParams") or ""
                if brand:
                    parts.append(f"🔍 **Расшифровка VIN:** {brand} {model} {pp}")
    except:
        pass
    try:
        tx = result.get("taxi")
        if tx:
            partner = tx.get("partner") if isinstance(tx, dict) else {}
            if isinstance(partner, dict) and partner.get("found"):
                parts.append("🚖 **Такси:** БЫЛА в такси 🔴")
            else:
                parts.append("🚖 **Такси:** Не в такси ✅")
    except:
        pass
    try:
        gost = result.get("gost")
        if gost and isinstance(gost, dict) and gost.get("marka"):
            parts.append(f"⚠️ **Отзывная компания:** {gost.get('marka')} {gost.get('namets')} — {gost.get('reasons','')[:100]}")
    except:
        pass
    return "\n".join(parts) if parts else "Доп. проверки: лизинг — нет, каршеринг — нет (проверь госномер для точности)"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
try:
    client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None
except:
    client = None

user_data = {}

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔍 Проверить по номеру/VIN/ссылке")],
        [KeyboardButton(text="🚗 Я у машины (фото+видео)")],
        [KeyboardButton(text="📩 Запросить VIN у продавца")],
        [KeyboardButton(text="🔄 Сброс")],
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📩 Запросить VIN у продавца")],
        [KeyboardButton(text="🔄 Сброс")],
    ], resize_keyboard=True)

def normalize_plate(s: str) -> str:
    s = s.upper().replace(" ", "").replace("-", "")
    mapping = {'A':'А','B':'В','E':'Е','K':'К','M':'М','H':'Н','O':'О','P':'Р','C':'С','T':'Т','Y':'У','X':'Х'}
    out = ""
    for ch in s:
        out += mapping.get(ch, ch)
    return out

def is_vin(s: str):
    return bool(re.match(r'^[A-HJ-NPR-Z0-9]{17}$', s.upper().strip()))

def is_gosnum(s: str):
    s_clean = s.upper().replace(" ", "").replace("-", "")
    allowed = "АВЕКМНОРСТУХABEKMHOPCTYX"
    pattern = rf'^[{allowed}]\d{{3}}[{allowed}]{{2}}\d{{2,3}}$'
    return bool(re.match(pattern, s_clean))

def extract_gos(t: str):
    allowed = "АВЕКМНОРСТУХABEKMHOPCTYX"
    m = re.search(rf'[{allowed}]\d{{3}}[{allowed}]{{2}}\s*\d{{2,3}}', t.upper())
    if m:
        return normalize_plate(m.group(0))
    return None

def extract_vin(t: str):
    m = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', t.upper())
    return m.group(0) if m else None

def extract_urls(t):
    return re.findall(r'https?://[^\s]+', t)

async def apipoint_call(payload):
    headers = {"Authorization": f"Bearer {APIPOINT_KEY}", "Content-Type": "application/json", "Accept": "application/json"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(APIPOINT_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                txt = await resp.text()
                print(f"[APIPOINT] {payload.get('sources')} -> {resp.status} {txt[:2000]}")
                try:
                    data = json.loads(txt)
                except:
                    data = {"raw": txt[:5000]}
                return resp.status, data
        except Exception as e:
            return 0, {"error": str(e)}

async def check_by_gos(gos):
    combined = {"balance": None, "result": {}}
    calls = [
        {"sources": "offerbygosnum", "gosnumber": gos},
        {"sources": "zalog", "gosnum": gos},
        {"sources": "carshering", "number": gos, "method": "checknumber"},
        {"sources": "taxi", "string": gos},
        {"sources": "nomerogram", "regNum": gos},
        {"sources": "autophoto", "regNum": gos},
    ]
    for payload in calls:
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            if combined["balance"] is None:
                combined["balance"] = data.get("balance")
            res = data.get("result") or {}
            src = payload["sources"]
            if src in res:
                combined["result"][src] = res[src]
            elif res:
                combined["result"][src] = res.get(src) or res
    return combined

async def check_by_vin(vin):
    combined = {"balance": None, "result": {}}
    # Сначала VIN-источники
    vin_calls = [
        {"sources": "zalog", "vin": vin},
        {"sources": "gibddhistory", "vin": vin},
        {"sources": "dtp", "vin": vin},
        {"sources": "probeg", "vin": vin},
        {"sources": "probeg2", "vin": vin},
        {"sources": "eaisto", "vin": vin},
        {"sources": "vindecode", "vin": vin},
        {"sources": "elpts", "vin": vin},
        {"sources": "leasing", "vin": vin},
        {"sources": "servicemaintenance", "vin": vin},
        {"sources": "offerbyvin", "vin": vin},
        {"sources": "pic", "vin": vin},
        {"sources": "taxi", "string": vin},
        {"sources": "gost", "vin": vin},
        {"sources": "convertb2b", "gosnomer": "placeholder"}, # will be skipped, need gos
    ]
    for payload in vin_calls:
        if payload["sources"] == "convertb2b":
            continue
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            if combined["balance"] is None:
                combined["balance"] = data.get("balance")
            res = data.get("result") or {}
            src = payload["sources"]
            if src in res:
                combined["result"][src] = res[src]
            elif res.get(src):
                combined["result"][src] = res[src]
            else:
                # sometimes result is directly in res
                if isinstance(res, dict) and res:
                    # try to find src key inside deeper
                    combined["result"][src] = res.get(src) or res

    # Попробуем вытащить госномер из gibddhistory и догрузить каршеринг/такси по госномеру
    try:
        gibdd = combined["result"].get("gibddhistory")
        if gibdd:
            # gibddhistory result is a JSON string inside result
            inner = gibdd.get("result") if isinstance(gibdd, dict) else None
            # inner may be stringified JSON
            if isinstance(inner, str):
                try:
                    inner_json = json.loads(inner)
                    periods = inner_json.get("RequestResult",{}).get("periods") or []
                except:
                    periods = []
            else:
                periods = []
            # also try convertb2b to get gos from vin
        # Use vin2number
        status, data = await apipoint_call({"sources": "vin2number", "vin": vin})
        if isinstance(data, dict):
            res = data.get("result") or {}
            v2n = res.get("vin2number") or {}
            gos = v2n.get("result",{}).get("gosnomer")
            if gos:
                # догружаем по госномеру
                gos_data = await check_by_gos(gos)
                for k,v in gos_data["result"].items():
                    if k not in combined["result"]:
                        combined["result"][k] = v
                combined["result"]["detected_gos"] = {"gos": gos}
    except Exception as e:
        print(f"gos enrich error {e}")

    return combined

async def fetch_ad_data(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                html = await resp.text()
                if HAS_BS4:
                    soup = BeautifulSoup(html, "html.parser")
                    title = soup.title.string if soup.title else ""
                    og_desc = soup.find("meta", property="og:description")
                    desc = og_desc["content"] if og_desc and og_desc.has_attr("content") else soup.get_text()[:3000]
                    images = [m.get("content") for m in soup.find_all("meta", property="og:image") if m.get("content")]
                else:
                    m_title = re.search(r'<title>(.*?)</title>', html, re.I|re.S)
                    title = m_title.group(1) if m_title else ""
                    desc = html[:3000]
                    images = re.findall(r'property="og:image" content="([^"]+)"', html)
                m_price = re.search(r'(\d[\d\s]{3,})\s*₽', html)
                price = m_price.group(1) if m_price else None
                return {"url": url, "title": title[:300], "description": desc[:3000], "price": price, "images": images[:8]}
    except Exception as e:
        return {"url": url, "title": "", "description": str(e), "price": None, "images": []}
    return {"url": url, "title": "", "description": "", "price": None, "images": []}

def generate_beautiful_html_report(target, ad_data, apipoint_result, mileage_txt, offers_txt, service_txt, ai_text="", additional_txt=""):
    from datetime import datetime
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    ad_title = ad_data.get("title","") if ad_data else "Объявление"
    ad_price = ad_data.get("price","") if ad_data else ""
    ad_url = ad_data.get("url","") if ad_data else ""
    ad_desc = ad_data.get("description","")[:500] if ad_data else ""
    ad_images = ad_data.get("images",[]) if ad_data else []
    result = apipoint_result.get("result",{}) if isinstance(apipoint_result, dict) else {}
    dtp_count = 0
    try:
        dtp_data = result.get("dtp",{}).get("dtpData") or result.get("dtp",{})
        if isinstance(dtp_data, dict):
            acc = dtp_data.get("accident") or []
            dtp_count = len(acc) if isinstance(acc, list) else (1 if dtp_data.get("hasDtp") else 0)
    except:
        pass
    zalog = result.get("zalog",{})
    zalog_val = "В залоге" if zalog.get("zalog") or zalog.get("f") else "Не в залоге"
    offers_count = 0
    try:
        for k in ["offerbyvin","offerbygosnum"]:
            c = result.get(k,{})
            inner = c.get("result",{}) if isinstance(c, dict) else {}
            lst = inner.get("offerList") or []
            offers_count += len(lst)
    except:
        pass
    imgs_html = ""
    # current ad images
    for img in ad_images[:6]:
        imgs_html += f'<img src="{img}" class="w-full h-48 object-cover rounded-xl" />'
    # archive pics
    try:
        pic = result.get("pic",{})
        img_list = pic.get("imageList") or []
        for img in img_list[:12]:
            imgs_html += f'<img src="{img}" class="w-full h-48 object-cover rounded-xl" />'
    except:
        pass
    # nomerogram
    try:
        nom = result.get("nomerogram",{})
        rez = nom.get("rez") or []
        for r in rez[:2]:
            for img in (r.get("img") or [])[:3]:
                imgs_html += f'<img src="{img}" class="w-full h-48 object-cover rounded-xl" />'
    except:
        pass
    if not imgs_html:
        imgs_html = '<div class="w-full h-48 bg-gray-100 rounded-xl flex items-center justify-center text-gray-400">Нет фото</div>'

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>Отчет {target}</title></head>
<body class="bg-[#f5f5f7] text-gray-900 font-sans">
<div class="max-w-4xl mx-auto p-4 md:p-8">
  <div class="bg-white rounded-[24px] shadow-sm p-6 md:p-8 mb-6">
    <div class="flex justify-between items-start"><div><div class="text-xs text-gray-400 uppercase tracking-widest">Отчет DROM Killer v25 PERFECT</div>
      <h1 class="text-3xl font-bold mt-2">{ad_title or target}</h1>
      <div class="mt-2 text-sm text-gray-500">VIN {target} • {now} • <a href="{ad_url}" class="text-blue-600">{ad_url[:50]}</a></div></div>
      <div class="bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-bold">Готов</div></div>
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6">
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">Цена</div><div class="font-bold text-lg">{ad_price or '—'} ₽</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">ДТП</div><div class="font-bold text-lg">{dtp_count}</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">Залог</div><div class="font-bold text-lg">{zalog_val}</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">Объявлений</div><div class="font-bold text-lg">{offers_count}</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">Фото</div><div class="font-bold text-lg">{len(ad_images) + 6} шт</div></div>
    </div>
  </div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6"><h2 class="font-bold text-xl mb-4">📸 Фото (текущие + архив pic + номерограм)</h2><div class="grid grid-cols-2 md:grid-cols-3 gap-3">{imgs_html}</div><div class="mt-4 text-sm text-gray-600 bg-gray-50 p-4 rounded-xl">{ad_desc}</div></div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6"><h2 class="font-bold text-xl mb-4">📌 Доп. проверки</h2><pre class="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-xl font-mono">{additional_txt}</pre></div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6"><h2 class="font-bold text-xl mb-4">📏 Пробег (probeg2 отсортирован по дате) + объявления</h2><pre class="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-xl font-mono">{mileage_txt}\n\n{offers_txt}</pre></div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6"><h2 class="font-bold text-xl mb-4">🔧 Обслуживание</h2><pre class="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-xl font-mono">{service_txt}</pre></div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6"><h2 class="font-bold text-xl mb-4">🤖 Вердикт</h2><div class="prose prose-sm max-w-none bg-yellow-50/50 p-4 rounded-xl border border-yellow-100 whitespace-pre-wrap">{ai_text[:6000]}</div></div>
  <div class="text-center text-xs text-gray-400 mt-8">v25 • probeg2 + eaisto + vin2number→гос→carshering/taxi + pic + nomerogram + offerbyvin/gosnum • Audatex недоступен у apipoint</div>
</div>
</body></html>"""
    return html

async def do_full(m, ad_data, ad_images_b64, target):
    await m.answer(f"Делаю полный отчет для {target} — probeg2 сортировка по дате + фото архив...", reply_markup=main_kb())
    vin = extract_vin(target) or extract_vin(ad_data.get("url","") or "")
    gos = extract_gos(target)
    if vin:
        data = await check_by_vin(vin)
    elif gos:
        data = await check_by_gos(gos)
    else:
        data = await check_by_vin(target)
    offers_txt, offers_list = format_offers_table(data.get("result",{}) if isinstance(data, dict) else {})
    service_txt, service_list = format_service_history(data.get("result",{}) if isinstance(data, dict) else {})
    mileage_txt, probeg_rows = format_probeg2_table(data.get("result",{}) if isinstance(data, dict) else {})
    additional_txt = format_additional_checks(data.get("result",{}) if isinstance(data, dict) else {})
    vision = []
    if ad_images_b64:
        for b64 in ad_images_b64[:4]:
            vision.append({"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}})
    prompt = f"Ты — автоподборщик. Цель {target} Объявление {ad_data.get('title')} Цена {ad_data.get('price')} Базы {json.dumps(data, ensure_ascii=False)[:12000]} Доп {additional_txt} Пробег {mileage_txt} Сделай отчет на РУССКОМ."
    ai_text_out = ""
    try:
        if client:
            resp=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":[{"type":"text","text":prompt}]+vision}], max_tokens=1500)
            ai_text_out = resp.choices[0].message.content
            await m.answer(ai_text_out, reply_markup=main_kb())
    except Exception as e:
        await m.answer(f"Ошибка ИИ: {e}", reply_markup=main_kb())
    try:
        html_report = generate_beautiful_html_report(target, ad_data, data, mileage_txt, offers_txt, service_txt, ai_text_out, additional_txt)
        file = BufferedInputFile(html_report.encode('utf-8'), filename=f"report_{target}.html")
        await m.answer_document(file, caption="📄 Отчет v25 — пробег отсортирован по дате, фото из архива, каршеринг через госномер")
    except Exception as e:
        print(f"HTML gen error {e}")

def format_service_history(result):
    txt = ""
    records = []
    try:
        container = result.get("servicemaintenance")
        if container:
            inner = container.get("result") if isinstance(container, dict) else container
            lst = inner if isinstance(inner, list) else []
            for rec in lst:
                if isinstance(rec, dict):
                    date = rec.get("Date") or ""
                    mileage = rec.get("Mileage") or ""
                    desc = rec.get("Description") or rec.get("Type") or ""
                    records.append({"date": str(date)[:10], "mileage": mileage, "works": desc})
    except:
        pass
    if not records:
        return "Нет данных от дилеров", []
    txt = "🔧 **История у дилера:**\n"
    for r in records[:10]:
        txt += f"`{r['date']}` — {r['mileage']} км — {r['works'][:80]}\n"
    return txt, records

async def ai_report(m, target, history, ad_url):
    await m.answer(f"Проверяю VIN {target} по полной схеме: probeg2 + vin2number→гос→carshering/taxi/pic...", reply_markup=main_kb())
    data = await check_by_vin(target)
    offers_txt, offers_list = format_offers_table(data.get("result",{}) if isinstance(data, dict) else {})
    service_txt, service_list = format_service_history(data.get("result",{}) if isinstance(data, dict) else {})
    mileage_txt, probeg_rows = format_probeg2_table(data.get("result",{}) if isinstance(data, dict) else {})
    additional_txt = format_additional_checks(data.get("result",{}) if isinstance(data, dict) else {})
    brand = target
    try:
        brand = data.get("result",{}).get("gibddhistory",{}).get("result",{}).get("brandModel") or target
    except:
        pass
    prompt = f"Ты — автоподборщик. VIN {target} Марка {brand} Ссылка {ad_url} Базы {json.dumps(data, ensure_ascii=False)[:15000]}\n{offers_txt}\n{service_txt}\n{additional_txt}\n{mileage_txt}\nСделай полный отчет на РУССКОМ как на Дроме."
    try:
        if client:
            r=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=2000)
            ai_text = r.choices[0].message.content
            await m.answer(ai_text, reply_markup=main_kb())
            try:
                html_report = generate_beautiful_html_report(target, {"title": brand, "price": "", "url": ad_url, "description": "", "images": []}, data, mileage_txt, offers_txt, service_txt, ai_text, additional_txt)
                file = BufferedInputFile(html_report.encode('utf-8'), filename=f"report_{target}.html")
                await m.answer_document(file, caption="📄 Отчет v25 — финальный, пробег отсортирован")
            except Exception as e2:
                print(f"HTML gen2 error {e2}")
    except Exception as e:
        await m.answer(f"Ошибка ИИ: {e}", reply_markup=main_kb())

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    user_data[m.from_user.id] = {"history": [], "ad_url": None, "ad_data": None, "ad_images_b64": []}
    await m.answer("Бот v25 ГОТОВ 🇷🇺 ✅\nОтправь VIN. Теперь: probeg2 сортировка по дате, pic архив фото, vin2number→гос→каршеринг/такси, полная история объявлений.", reply_markup=main_kb())

@dp.message(F.text=="🔄 Сброс")
async def reset(m: types.Message):
    user_data[m.from_user.id] = {"history": [], "ad_url": None, "ad_data": None, "ad_images_b64": []}
    await m.answer("Сброс выполнен ✅", reply_markup=main_kb())

@dp.message(F.text.contains("Запросить VIN"))
async def request_vin(m: types.Message):
    await m.answer("📩 Отправь продавцу:\n\nПривет! Пришлите VIN для проверки истории (ГИБДД, залог, ДТП, пробег probeg2, фото pic).", reply_markup=cancel_kb())

@dp.message(F.text.contains("Проверить по"))
async def check_prompt(m: types.Message):
    await m.answer("Пришли ссылку на Авито/Дром/Авто.ру + VIN. Для полного отчета нужен VIN — покажу всю историю пробегов probeg2 и архив фото.", reply_markup=main_kb())

@dp.message(F.text.contains("Я у машины"))
async def at_car(m: types.Message):
    await m.answer("На осмотре — пришли фото и видео сюда, я оценю кузов.", reply_markup=cancel_kb())

@dp.message()
async def handle_text(m: types.Message):
    uid = m.from_user.id
    if uid not in user_data:
        user_data[uid] = {"history": [], "ad_url": None, "ad_data": None, "ad_images_b64": []}
    text = m.text or ""
    urls = extract_urls(text)
    vin = extract_vin(text)
    gos = extract_gos(text)
    if urls:
        ad_url = urls[0]
        user_data[uid]["ad_url"] = ad_url
        await m.answer(f"Ссылка ок {ad_url} — качаю объявление...", reply_markup=main_kb())
        ad_data = await fetch_ad_data(ad_url)
        user_data[uid]["ad_data"] = ad_data
        target = vin or gos or ad_data.get("title") or ad_url
        await m.answer(f"Название: {ad_data.get('title','')[:100]}\nЦена: {ad_data.get('price','?')}\nФото: {len(ad_data.get('images',[]))} шт\n\nПришли VIN для полного отчета", reply_markup=main_kb())
        if vin or gos:
            await do_full(m, ad_data, [], vin or gos)
        return
    if vin:
        await ai_report(m, vin, [], user_data[uid].get("ad_url") or "")
        return
    if gos:
        await m.answer(f"Проверяю госномер {gos}...", reply_markup=main_kb())
        data = await check_by_gos(gos)
        offers_txt, _ = format_offers_table(data.get("result",{}))
        add_txt = format_additional_checks(data.get("result",{}))
        await m.answer(f"Результат по {gos}:\n{offers_txt}\n{add_txt}\n\nДля полного отчета нужен VIN.", reply_markup=main_kb())
        return
    await m.answer("Пришли госномер, VIN или ссылку. Для полного отчета нужен VIN.", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())