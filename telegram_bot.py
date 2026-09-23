# -*- coding: utf-8 -*-
import asyncio, os, base64, re, json, logging
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

print(f"BOOT v23 FIXED RUSSIAN + BEAUTIFUL | BOT={bool(BOT_TOKEN)} APIPOINT={bool(APIPOINT_KEY)}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN empty")

def format_offers_table(result):
    offers = []
    try:
        for key in ["offerbyvin", "offerbygosnum"]:
            container = result.get(key) if isinstance(result, dict) else None
            if not container:
                continue
            inner = container.get("result") if isinstance(container, dict) else container
            if isinstance(inner, dict):
                lst = inner.get("offerList") or inner.get("offers") or inner.get("items") or []
            elif isinstance(inner, list):
                lst = inner
            else:
                lst = []
            for item in lst:
                if not isinstance(item, dict):
                    continue
                date = item.get("Date") or item.get("date") or item.get("PublishDate") or item.get("publicDate") or ""
                price = item.get("Price") or item.get("price") or item.get("PriceRub") or ""
                mileage = item.get("Mileage") or item.get("mileage") or item.get("Probeg") or ""
                source = item.get("Source") or item.get("source") or item.get("Site") or ""
                title = item.get("Title") or item.get("title") or ""
                if price or mileage or date:
                    offers.append({"date": str(date)[:16], "price": price, "mileage": mileage, "source": source or title[:20]})
    except Exception as e:
        print(f"offers parse error {e}")
    if not offers:
        return "", []
    offers = sorted(offers, key=lambda x: x["date"])
    txt = "📢 **История объявлений:**\n"
    for o in offers:
        line = f"`{o['date']}`"
        if o['price']:
            line += f" — {o['price']} ₽"
        if o['mileage']:
            line += f" — {o['mileage']} км"
        if o['source']:
            line += f" — {o['source']}"
        txt += line + "\n"
    return txt, offers

def format_mileage_table(history, probeg_raw):
    rows = []
    if history:
        for h in history:
            try:
                d = h.get('date') or h.get('DateString') or ''
                p = h.get('probeg') or h.get('Probeg') or h.get('mileage')
                src = h.get('source') or h.get('SourceName') or 'ТО'
                if p:
                    rows.append((d, p, src))
            except:
                pass
    if probeg_raw and not rows:
        try:
            r = probeg_raw.get('result', {}).get('m_probeg') or probeg_raw.get('result') or {}
            if r.get('Probeg'):
                rows.append((r.get('DateString',''), r.get('Probeg'), r.get('SourceName','техосмотр')))
        except:
            pass
    if not rows:
        return "Пробег по базам не найден"
    rows = sorted(rows, key=lambda x: str(x[0]))
    txt = "📏 **Пробег по датам:**\n"
    for d,p,s in rows:
        txt += f"`{d}` — {p} км ({s})\n"
    if len(rows)==1:
        txt += "\n⚠️ Свежего пробега в базах нет, проверяй сервисную книжку."
    return txt

def format_service_history(result):
    txt = ""
    records = []
    try:
        container = result.get("servicemaintenance")
        if container:
            inner = container.get("result") if isinstance(container, dict) else container
            lst = []
            if isinstance(inner, dict):
                lst = inner.get("history") or inner.get("records") or inner.get("services") or inner.get("items") or []
                if not lst and inner.get("date"):
                    lst = [inner]
            elif isinstance(inner, list):
                lst = inner
            for rec in lst:
                if not isinstance(rec, dict):
                    continue
                date = rec.get("date") or rec.get("Date") or rec.get("visitDate") or ""
                mileage = rec.get("mileage") or rec.get("Mileage") or rec.get("probeg") or ""
                works = rec.get("works") or rec.get("Works") or rec.get("description") or ""
                if isinstance(works, list):
                    works = ", ".join([str(w.get("name") or w) for w in works[:3]])
                records.append({"date": str(date)[:10], "mileage": mileage, "works": works})
    except Exception as e:
        print(f"service parse error {e}")
    if not records:
        return "", []
    records = sorted(records, key=lambda x: x["date"])
    txt = "🔧 **История обслуживания у дилера:**\n"
    for r in records[:10]:
        line = f"`{r['date']}`"
        if r["mileage"]:
            line += f" — {r['mileage']} км"
        if r["works"]:
            line += f" — {str(r['works'])[:80]}"
        txt += line + "\n"
    if len(records) > 10:
        txt += f"_... и еще {len(records)-10} записей_\n"
    return txt, records

def format_additional_checks(result):
    txt_parts = []
    probeg_points = []
    try:
        cs = result.get("carsharing") or result.get("carshare")
        if cs:
            inner = cs.get("result") if isinstance(cs, dict) else cs
            used = False
            if isinstance(inner, dict):
                used = inner.get("isCarsharing") or inner.get("used") or inner.get("carsharing") or inner.get("hasCarsharing")
            if used:
                txt_parts.append("🚕 **Каршеринг:** БЫЛА в каршеринге/такси — красный флаг!")
            else:
                txt_parts.append("🚕 **Каршеринг:** Не использовалась")
    except:
        pass
    try:
        ls = result.get("leasing") or result.get("lizing")
        if ls:
            inner = ls.get("result") if isinstance(ls, dict) else ls
            in_lease = False
            if isinstance(inner, dict):
                in_lease = inner.get("inLeasing") or inner.get("isLeasing") or inner.get("leasing")
            if in_lease:
                txt_parts.append("💼 **Лизинг:** В лизинге — на учет не поставить!")
            else:
                txt_parts.append("💼 **Лизинг:** Не в лизинге")
    except:
        pass
    try:
        pc = result.get("probegs") or result.get("probeg_collection")
        if pc:
            inner = pc.get("result") if isinstance(pc, dict) else pc
            lst = []
            if isinstance(inner, dict):
                lst = inner.get("history") or inner.get("mileages") or inner.get("items") or []
            elif isinstance(inner, list):
                lst = inner
            for item in lst:
                if isinstance(item, dict):
                    d = item.get("date") or item.get("Date") or ""
                    m = item.get("mileage") or item.get("probeg") or ""
                    s = item.get("source") or "ТО"
                    if m:
                        probeg_points.append((d,m,s))
    except:
        pass
    try:
        vd = result.get("vin_decode") or result.get("decodevin")
        if vd:
            inner = vd.get("result") if isinstance(vd, dict) else vd
            if isinstance(inner, dict):
                brand = inner.get("brand") or inner.get("make") or ""
                model = inner.get("model") or ""
                engine = inner.get("engine") or inner.get("engineVolume") or ""
                if brand or model:
                    txt_parts.append(f"🔍 **Комплектация:** {brand} {model} {engine}")
    except:
        pass
    try:
        pts = result.get("pts") or result.get("ptsinfo")
        if pts:
            inner = pts.get("result") if isinstance(pts, dict) else pts
            if isinstance(inner, dict):
                dup = inner.get("duplicate") or inner.get("isDuplicate")
                if dup:
                    txt_parts.append("📄 **ПТС:** Дубликат!")
                else:
                    txt_parts.append("📄 **ПТС:** Оригинал")
    except:
        pass
    full_txt = "\n".join(txt_parts)
    return full_txt, probeg_points, {}

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

HOOD_STEPS = ["1/8 Перед", "2/8 Зад", "3/8 Левая сторона", "4/8 Правая сторона", "5/8 VIN", "6/8 Приборка", "7/8 Под капотом", "8/8 Видео"]

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
            async with session.post(APIPOINT_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=40)) as resp:
                txt = await resp.text()
                print(f"[APIPOINT] {payload} -> {resp.status} {txt[:2000]}")
                try:
                    data = json.loads(txt)
                except:
                    data = {"raw": txt[:5000]}
                return resp.status, data
        except Exception as e:
            return 0, {"error": str(e)}

async def check_by_gos(gos):
    combined = {"balance": None, "price": None, "result": {}}
    for src in ["zalog", "offerbygosnum"]:
        if src=="offerbygosnum":
            payload = {"sources": src, "gosnumber": gos}
        else:
            payload = {"sources": src, "gosnum": gos}
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            if combined["balance"] is None:
                combined["balance"] = data.get("balance") or data.get("data",{}).get("balance")
            res = data.get("result") or data.get("data",{}).get("result") or {}
            if isinstance(res, dict):
                if src in res:
                    combined["result"][src] = res[src]
                elif res:
                    combined["result"][src] = res
            else:
                combined["result"][src] = data
    return combined

async def check_by_vin(vin):
    combined = {"balance": None, "price": None, "result": {}}
    sources = ["zalog","fsspdata","gibddhistory","dtp","probeg","probegs","carsharing","leasing","pts","vin_decode","nomerogram","carprices","gai","regperiods","autophoto","offerbyvin","servicemaintenance"]
    for src in sources:
        payload = {"sources": src, "vin": vin}
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            if combined["balance"] is None:
                combined["balance"] = data.get("balance") or data.get("data",{}).get("balance")
            res = data.get("result") or data.get("data",{}).get("result") or {}
            if isinstance(res, dict):
                if src in res:
                    combined["result"][src] = res[src]
                elif res:
                    combined["result"][src] = res
            else:
                combined["result"][src] = data
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
    has_dtp = "Да" if result.get("dtp",{}).get("dtpData",{}).get("hasDtp") or result.get("dtp",{}).get("hasDtp") else "Нет"
    zalog = result.get("zalog",{})
    zalog_val = "В залоге" if zalog.get("f")==True else "Не в залоге"
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
    for img in ad_images[:6]:
        imgs_html += f'<img src="{img}" class="w-full h-48 object-cover rounded-xl" />'
    if not imgs_html:
        imgs_html = '<div class="w-full h-48 bg-gray-100 rounded-xl flex items-center justify-center text-gray-400">Нет фото из текущего объявления</div>'
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
<title>Отчет {target}</title></head>
<body class="bg-[#f5f5f7] text-gray-900 font-sans">
<div class="max-w-4xl mx-auto p-4 md:p-8">
  <div class="bg-white rounded-[24px] shadow-sm p-6 md:p-8 mb-6">
    <div class="flex justify-between items-start">
      <div><div class="text-xs text-gray-400 uppercase tracking-widest">Отчет DROM Killer v23</div>
      <h1 class="text-3xl font-bold mt-2">{ad_title or target}</h1>
      <div class="mt-2 text-sm text-gray-500">VIN {target} • Проверка {now} • <a href="{ad_url}" class="text-blue-600">{ad_url[:40]}</a></div></div>
      <div class="bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-bold">Готов</div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6">
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">Текущая цена</div><div class="font-bold text-lg">{ad_price or '—'} ₽</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">ДТП</div><div class="font-bold text-lg">{has_dtp}</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">Залог</div><div class="font-bold text-lg">{zalog_val}</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">Объявлений</div><div class="font-bold text-lg">{offers_count or '1'}</div></div>
      <div class="bg-gray-50 rounded-2xl p-4"><div class="text-xs text-gray-400">Фото</div><div class="font-bold text-lg">{len(ad_images)} шт</div></div>
    </div>
  </div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6">
    <h2 class="font-bold text-xl mb-4">📸 Текущее объявление</h2>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-3">{imgs_html}</div>
    <div class="mt-4 text-sm text-gray-600 bg-gray-50 p-4 rounded-xl">{ad_desc}</div>
  </div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6">
    <h2 class="font-bold text-xl mb-4">📌 Доп. проверки (ПТС, каршеринг, лизинг)</h2>
    <pre class="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-xl font-mono">{additional_txt or 'Доп проверки не дали данных'}</pre>
  </div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6">
    <h2 class="font-bold text-xl mb-4">📏 Пробег и история объявлений</h2>
    <pre class="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-xl font-mono">{mileage_txt}\n\n{offers_txt}</pre>
  </div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6">
    <h2 class="font-bold text-xl mb-4">🔧 История обслуживания</h2>
    <pre class="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-xl font-mono">{service_txt or 'Нет данных от дилеров'}</pre>
  </div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6">
    <h2 class="font-bold text-xl mb-4">🤖 Вердикт</h2>
    <div class="prose prose-sm max-w-none bg-yellow-50/50 p-4 rounded-xl border border-yellow-100 whitespace-pre-wrap">{ai_text[:4000]}</div>
  </div>
  <div class="text-center text-xs text-gray-400 mt-8">Сгенерировано ботом v23 • ГИБДД, ЕАИСТО, залог, лизинг, каршеринг, Авито/Дром, дилеры</div>
</div>
</body></html>"""
    return html

async def do_full(m, ad_data, ad_images_b64, target):
    await m.answer(f"Делаю полный отчет для {target} — качаю базы...", reply_markup=main_kb())
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
    additional_txt, extra_probegs, _ = format_additional_checks(data.get("result",{}) if isinstance(data, dict) else {})
    mileage_txt = format_mileage_table([], {})
    if extra_probegs:
        for d,m_1,s in extra_probegs:
            mileage_txt += f"\n`{d}` — {m_1} км ({s})"
    vision = []
    if ad_images_b64:
        for b64 in ad_images_b64[:4]:
            vision.append({"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}})
    prompt = f"Ты — автоподборщик. Ссылка {ad_data.get('url')} Цель {target} Объявление {ad_data.get('title')} Цена {ad_data.get('price')} Базы {json.dumps(data, ensure_ascii=False)[:12000]} Доп {additional_txt} Сделай отчет на РУССКОМ: АВТО, ФОТО, ПРОВЕРКА БАЗ, ЦЕНА, ВЕРДИКТ. Пиши как на Дроме, без воды."
    ai_text_out = ""
    try:
        if client:
            resp=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":[{"type":"text","text":prompt}]+vision}], max_tokens=1500)
            ai_text_out = resp.choices[0].message.content
            await m.answer(ai_text_out, reply_markup=main_kb())
        else:
            await m.answer(f"ИИ выкл. Сырые данные: {json.dumps(data, ensure_ascii=False)[:3000]}", reply_markup=main_kb())
    except Exception as e:
        await m.answer(f"Ошибка ИИ: {e}", reply_markup=main_kb())
        ai_text_out = f"Ошибка ИИ: {e}"
    try:
        html_report = generate_beautiful_html_report(target, ad_data, data, mileage_txt, offers_txt, service_txt, ai_text_out, additional_txt)
        file = BufferedInputFile(html_report.encode('utf-8'), filename=f"report_{target}.html")
        await m.answer_document(file, caption="📄 Красивый отчет — с текущим объявлением, фото и историей. Открой в браузере.")
    except Exception as e:
        print(f"HTML gen error {e}")

async def ai_report(m, target, history, ad_url):
    await m.answer(f"Проверяю VIN {target} по всем базам (ГИБДД, залог, лизинг, каршеринг, ДТП, пробег, история объявлений)...", reply_markup=main_kb())
    data = await check_by_vin(target)
    offers_txt, offers_list = format_offers_table(data.get("result",{}) if isinstance(data, dict) else {})
    service_txt, service_list = format_service_history(data.get("result",{}) if isinstance(data, dict) else {})
    additional_txt, extra_probegs, _ = format_additional_checks(data.get("result",{}) if isinstance(data, dict) else {})
    mileage_table = format_mileage_table(history, data.get("result",{}).get("probeg") if isinstance(data.get("result"), dict) else None)
    if extra_probegs:
        for d,m_1,s in extra_probegs:
            mileage_table += f"\n`{d}` — {m_1} км ({s})"
    brand = ""
    try:
        brand = data.get("result",{}).get("gibddhistory",{}).get("result",{}).get("brandModel") or target
    except:
        brand = target
    prompt = f"Ты — автоподборщик. VIN {target} Марка {brand} Ссылка {ad_url} Базы {json.dumps(data, ensure_ascii=False)[:15000]}\n{offers_txt}\n{service_txt}\n{additional_txt}\nПробег:\n{mileage_table}\nСделай полный отчет на РУССКОМ как на Дроме: 1) АВТО 2) ПРОВЕРКА БАЗ (залог, лизинг, каршеринг, ДТП, ПТС) 3) ПРОБЕГ ПО ДАТАМ 4) ИСТОРИЯ ОБЪЯВЛЕНИЙ 5) ЦЕНА 6) ВЕРДИКТ. Отметь скрутку если есть."
    try:
        if client:
            r=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=2000)
            ai_text = r.choices[0].message.content
            await m.answer(ai_text, reply_markup=main_kb())
            try:
                html_report = generate_beautiful_html_report(target, {"title": brand, "price": "", "url": ad_url, "description": "", "images": []}, data, mileage_table, offers_txt, service_txt, ai_text, additional_txt)
                file = BufferedInputFile(html_report.encode('utf-8'), filename=f"report_{target}.html")
                await m.answer_document(file, caption="📄 Красивый отчет (только история по VIN)")
            except Exception as e2:
                print(f"HTML gen2 error {e2}")
        else:
            await m.answer(f"Сырые данные: {json.dumps(data, ensure_ascii=False)[:4000]}", reply_markup=main_kb())
    except Exception as e:
        await m.answer(f"Ошибка ИИ: {e}", reply_markup=main_kb())

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    user_data[m.from_user.id] = {"history": [], "ad_url": None, "ad_data": None, "ad_images_b64": []}
    await m.answer("Бот v23 ГОТОВ К ПРОВЕРКЕ 🇷🇺 ✅\nОтправь госномер X423KO550 или VIN.\nДля полного отчета нужен VIN (как на Дроме).", reply_markup=main_kb())

@dp.message(F.text=="🔄 Сброс")
async def reset(m: types.Message):
    user_data[m.from_user.id] = {"history": [], "ad_url": None, "ad_data": None, "ad_images_b64": []}
    await m.answer("Сброс выполнен ✅", reply_markup=main_kb())

@dp.message(F.text.contains("Запросить VIN"))
async def request_vin(m: types.Message):
    await m.answer("📩 Отправь продавцу:\n\nПривет! Пришлите VIN для проверки истории (ГИБДД, залог, ДТП, пробег). Пример: X423KO550 или VF3... \n\nЕсли не хочет — пришлите хотя бы госномер, проверю залог и объявления.", reply_markup=cancel_kb())

@dp.message(F.text.contains("Проверить по"))
async def check_prompt(m: types.Message):
    await m.answer("Пришли ссылку на Авито/Дром/Авто.ру + госномер или VIN. Если номера нет — жми Запросить VIN", reply_markup=main_kb())

@dp.message(F.text.contains("Я у машины"))
async def at_car(m: types.Message):
    await m.answer(f"На осмотре — {HOOD_STEPS[0]}. Пришли фото и видео сюда, я оценю кузов.", reply_markup=cancel_kb())

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
        await m.answer(f"Название: {ad_data.get('title','')[:100]}\nЦена: {ad_data.get('price','?')} \n\nФото: {len(ad_data.get('images',[]))} шт\n\nПришли VIN или госномер для полного отчета, или жми Проверить по номеру", reply_markup=main_kb())
        if vin or gos:
            await do_full(m, ad_data, [], vin or gos)
        return
    if vin:
        await ai_report(m, vin, [], user_data[uid].get("ad_url") or "")
        return
    if gos:
        await m.answer(f"Проверяю госномер {gos} (залог, объявления)...", reply_markup=main_kb())
        data = await check_by_gos(gos)
        offers_txt, _ = format_offers_table(data.get("result",{}))
        await m.answer(f"Результат по {gos}:\n{offers_txt}\n\nДля полного отчета нужен VIN.", reply_markup=main_kb())
        return
    await m.answer("Пришли госномер X423KO550, VIN или ссылку на объявление. Для полного отчета нужен VIN.", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())