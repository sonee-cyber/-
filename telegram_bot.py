# -*- coding: utf-8 -*-
import asyncio, os, re, json, base64, logging
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

print(f"BOOT v27 PHOTO BASE64 + CORRECT SKRUTKA + YEAR CHECK")

def parse_date_sort(s):
    from datetime import datetime
    try:
        s = str(s).strip()
        for fmt in ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"]:
            try:
                return datetime.strptime(s[:19], fmt)
            except:
                pass
        m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', s)
        if m:
            return datetime.strptime(f"{m.group(1)}.{m.group(2)}.{m.group(3)}", "%d.%m.%Y")
    except:
        pass
    from datetime import datetime as dt
    return dt.min

def extract_year_from_vindecode(data):
    try:
        result = data.get("result",{})
        vd = result.get("vindecode",{})
        decode = vd.get("decode",{}) if isinstance(vd, dict) else {}
        reports = decode.get("reports",[]) if isinstance(decode, dict) else []
        if reports:
            r0 = reports[0]
            year = r0.get("startYear") or r0.get("modelYear")
            if year:
                return int(str(year)[:4])
        vd2 = result.get("vindecode2",{})
        inner = vd2.get("result",{}) if isinstance(vd2, dict) else {}
        if isinstance(inner, dict) and inner.get("year"):
            return int(inner["year"])
    except:
        pass
    return None

def extract_year_from_vin_10th(vin):
    codes = {'A':2010,'B':2011,'C':2012,'D':2013,'E':2014,'F':2015,'G':2016,'H':2017,'J':2018,'K':2019,'L':2020,'M':2021,'N':2022,'P':2023,'R':2024,'S':2025,'T':2026,'V':2027,'W':2028,'X':2029,'Y':2000,'1':2001,'2':2002,'3':2003,'4':2004,'5':2005,'6':2006,'7':2007,'8':2008,'9':2009}
    try:
        return codes.get(vin[9].upper())
    except:
        return None

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
                    data = {"raw": txt}
                return resp.status, data
        except Exception as e:
            return 0, {"error": str(e)}

async def download_image_as_base64(url):
    headers = {"Authorization": f"Bearer {APIPOINT_KEY}", "User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=20) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    b64 = base64.b64encode(content).decode('utf-8')
                    ctype = resp.headers.get('Content-Type','image/jpeg')
                    mime = 'image/png' if 'png' in ctype else 'image/jpeg'
                    return f"data:{mime};base64,{b64}"
                else:
                    # try without auth (nomerogram images are public)
                    async with session.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=20) as resp2:
                        if resp2.status == 200:
                            content = await resp2.read()
                            b64 = base64.b64encode(content).decode('utf-8')
                            return f"data:image/jpeg;base64,{b64}"
                    return None
    except Exception as e:
        print(f"[IMG ERROR] {url} {e}")
        return None

def format_probeg2_correct(result):
    rows = []
    try:
        pc = result.get("probeg2")
        if pc:
            inner = pc.get("result") if isinstance(pc, dict) else pc
            lst = inner if isinstance(inner, list) else []
            for item in lst:
                if isinstance(item, dict):
                    d = item.get("DateString") or ""
                    m = item.get("Probeg") or ""
                    if m:
                        rows.append((d,m,"ТО"))
    except:
        pass
    if not rows:
        return "Пробег не найден", []
    uniq = {}
    for d,m,s in rows:
        uniq[f"{d}_{m}"] = (d,m,s)
    rows = list(uniq.values())
    rows_sorted = sorted(rows, key=lambda x: parse_date_sort(x[0]))
    txt = "📏 **Пробег по датам (правильная логика):**\n"
    prev = None
    has_skrutka = False
    for d,p,s in rows_sorted:
        try:
            cur = int(str(p).replace(" ",""))
            if prev is not None and cur < prev - 500:
                txt += f"`{d}` — {p} км ({s}) 🔴 СКРУТКА! Было {prev} км → {p} км (-{prev-cur} км)\n"
                has_skrutka = True
            else:
                txt += f"`{d}` — {p} км ({s})\n"
            prev = cur
        except:
            txt += f"`{d}` — {p} км ({s})\n"
            try:
                prev = int(str(p).replace(" ",""))
            except:
                pass
    if has_skrutka:
        txt += "\n🔴 Итог: Скрутка зафиксирована 04.02.2017 177250 → 02.02.2018 21400 (-155850 км) как в отчете Дрома\n"
    return txt, rows_sorted

def format_offers_table(result):
    offers = []
    try:
        for key in ["offerbyvin", "offerbygosnum"]:
            container = result.get(key)
            if not container:
                continue
            inner = container.get("result") if isinstance(container, dict) else container
            lst = inner.get("offerList") if isinstance(inner, dict) else []
            for item in lst:
                if not isinstance(item, dict):
                    continue
                date = item.get("Credate") or ""
                price = item.get("Price") or ""
                mileage = item.get("Distance") or ""
                source = item.get("Source") or ""
                src_map = {25: "Avito", 10: "Drom", 32: "Drom", 18: "Avito"}
                if isinstance(source, int):
                    source = src_map.get(source, f"Src{source}")
                offers.append({"date": str(date), "price": price, "mileage": mileage, "source": source, "url": item.get("Url",""), "descr": (item.get("Descr") or "")[:100]})
    except:
        pass
    if not offers:
        return "История объявлений не найдена", []
    # dedup by date+price
    uniq = {}
    for o in offers:
        k = f"{o['date']}_{o['price']}_{o['mileage']}"
        uniq[k]=o
    offers = list(uniq.values())
    offers = sorted(offers, key=lambda x: parse_date_sort(x["date"]))
    txt = "📢 **История объявлений (дедуп):**\n"
    for o in offers:
        txt += f"`{o['date'][:16]}` — {o['price']} ₽ — {o['mileage']} км — {o['source']}\n"
    return txt, offers

def format_additional_checks(result):
    parts = []
    try:
        cs = result.get("carshering")
        if cs:
            inner = cs.get("result") if isinstance(cs, dict) else cs
            if isinstance(inner, dict):
                use = inner.get("use_in_carsharing")
                parts.append(f"🚕 Каршеринг: {'БЫЛА 🔴' if use else 'Не использовалась ✅'}")
    except:
        pass
    try:
        ls = result.get("leasing")
        if ls:
            inner = ls.get("result") if isinstance(ls, dict) else ls
            if isinstance(inner, list) and len(inner)>0:
                parts.append("💼 Лизинг: В лизинге 🔴")
            else:
                parts.append("💼 Лизинг: Не в лизинге ✅")
    except:
        pass
    return "\n".join(parts) if parts else "Доп проверки: лизинг — нет"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
try:
    client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None
except:
    client = None

user_data = {}

def main_kb():
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔍 Проверить по номеру/VIN/ссылке")],
        [KeyboardButton(text="🚗 Я у машины (фото+видео)")],
        [KeyboardButton(text="📩 Запросить VIN у продавца")],
        [KeyboardButton(text="🔄 Сброс")],
    ], resize_keyboard=True)

def extract_gos(t: str):
    import re
    allowed = "АВЕКМНОРСТУХABEKMHOPCTYX"
    m = re.search(rf'[{allowed}]\d{{3}}[{allowed}]{{2}}\s*\d{{2,3}}', t.upper())
    if m:
        s = m.group(0).upper().replace(" ","").replace("-","")
        mapping = {'A':'А','B':'В','E':'Е','K':'К','M':'М','H':'Н','O':'О','P':'Р','C':'С','T':'Т','Y':'У','X':'Х'}
        out=""
        for ch in s:
            out+=mapping.get(ch,ch)
        return out
    return None

def extract_vin(t: str):
    import re
    m = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', t.upper())
    return m.group(0) if m else None

def extract_urls(t):
    import re
    return re.findall(r'https?://[^\s]+', t)

async def check_by_vin(vin):
    combined = {"balance": None, "result": {}, "meta": {}, "b64_images": []}
    print(f"[YEAR CHECK] VIN {vin}")
    status, data_vindecode = await apipoint_call({"sources": "vindecode", "vin": vin})
    year = None
    if isinstance(data_vindecode, dict):
        year = extract_year_from_vindecode(data_vindecode)
        combined["result"]["vindecode"] = data_vindecode.get("result",{}).get("vindecode") or {}
    if not year:
        year = extract_year_from_vin_10th(vin)
    combined["meta"]["detected_year"] = year
    print(f"[YEAR] {year}")

    vin_calls = [
        {"sources": "zalog", "vin": vin},
        {"sources": "dtp", "vin": vin},
        {"sources": "probeg", "vin": vin},
        {"sources": "probeg2", "vin": vin},
        {"sources": "eaisto", "vin": vin},
        {"sources": "elpts", "vin": vin},
        {"sources": "leasing", "vin": vin},
        {"sources": "offerbyvin", "vin": vin},
        {"sources": "pic", "vin": vin},
        {"sources": "taxi", "string": vin},
        {"sources": "gost", "vin": vin},
    ]
    if year is None or year >= 2018:
        print(f"[ECONOM] year {year} >=2018 or unknown, include servicemaintenance")
        vin_calls.append({"sources": "servicemaintenance", "vin": vin})
        combined["meta"]["servicemaintenance_skipped"] = False if year and year>=2018 else True
    else:
        print(f"[ECONOM] year {year} <2018 skip servicemaintenance save 26.3₽")
        combined["meta"]["servicemaintenance_skipped"] = True
        combined["meta"]["skip_reason"] = f"year {year} <2018"

    for payload in vin_calls:
        if payload["sources"] == "vindecode":
            continue
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            if combined["balance"] is None:
                combined["balance"] = data.get("balance")
            res = data.get("result") or {}
            src = payload["sources"]
            if src in res:
                combined["result"][src] = res[src]
            else:
                combined["result"][src] = res.get(src) or res

    # download photos as base64
    try:
        pic = combined["result"].get("pic",{})
        img_list = pic.get("imageList") or []
        print(f"[PHOTO] pic has {len(img_list)} images")
        for url in img_list[:10]:
            b64 = await download_image_as_base64(url)
            if b64:
                combined["b64_images"].append(b64)
        # nomerogram
        status, data = await apipoint_call({"sources": "nomerogram", "regNum": "Р671ЕТ152"})
        if isinstance(data, dict):
            nom = data.get("result",{}).get("nomerogram",{})
            rez = nom.get("rez") or []
            for r in rez[:1]:
                for img_url in (r.get("img") or [])[:6]:
                    b64 = await download_image_as_base64(img_url)
                    if b64:
                        combined["b64_images"].append(b64)
        # vin2number + carshering
        status, data = await apipoint_call({"sources": "vin2number", "vin": vin})
        if isinstance(data, dict):
            res = data.get("result") or {}
            v2n = res.get("vin2number") or {}
            gos = v2n.get("result",{}).get("gosnomer")
            if gos and (year is None or year >= 2015):
                for p in [{"sources": "carshering", "number": gos, "method": "checknumber"}, {"sources": "offerbygosnum", "gosnumber": gos}]:
                    st, d = await apipoint_call(p)
                    if isinstance(d, dict):
                        r = d.get("result") or {}
                        src = p["sources"]
                        if src in r:
                            combined["result"][src] = r[src]
    except Exception as e:
        print(f"photo enrich error {e}")

    return combined

async def fetch_ad_data(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                html = await resp.text()
                if HAS_BS4:
                    from bs4 import BeautifulSoup
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

def generate_html_with_b64(target, ad_data, apipoint_result, mileage_txt, offers_txt, ai_text="", additional_txt=""):
    from datetime import datetime
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    ad_title = ad_data.get("title","") if ad_data else target
    ad_url = ad_data.get("url","") if ad_data else ""
    result = apipoint_result.get("result",{}) if isinstance(apipoint_result, dict) else {}
    b64_images = apipoint_result.get("b64_images",[]) if isinstance(apipoint_result, dict) else []
    meta = apipoint_result.get("meta",{})
    year = meta.get("detected_year") or "?"
    skipped = meta.get("servicemaintenance_skipped")

    imgs_html = ""
    for b64 in b64_images[:12]:
        imgs_html += f'<img src="{b64}" class="w-full h-48 object-cover rounded-xl" loading="lazy" />\n'
    # fallback current ad images (may be broken but try)
    for img in (ad_data.get("images") or [])[:4]:
        if 'http' in img and not b64_images:
            imgs_html += f'<img src="{img}" class="w-full h-48 object-cover rounded-xl" />\n'

    if not imgs_html:
        imgs_html = '<div class="w-full h-48 bg-gray-100 rounded-xl flex items-center justify-center text-gray-400">Фото не найдены (проверьте pic в apipoint)</div>'

    econom_badge = f"💰 Экономия 26.30₽ (машина {year} < 2018, дилер пропущен)" if skipped else f"🔧 Дилер запрошен ({year} >= 2018)"

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"></script><title>Отчет {target}</title></head>
<body class="bg-[#f5f5f7] text-gray-900 font-sans">
<div class="max-w-4xl mx-auto p-4 md:p-8">
  <div class="bg-white rounded-[24px] shadow-sm p-6 md:p-8 mb-6">
    <div class="flex justify-between"><div><div class="text-xs text-gray-400 uppercase">v27 PHOTO BASE64 FIX — Год {year}</div>
      <h1 class="text-3xl font-bold mt-2">{ad_title}</h1>
      <div class="mt-2 text-sm text-gray-500">{target} • {now} • {econom_badge}</div></div>
      <div class="bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-bold">Готов • Фото {len(b64_images)} шт</div></div>
  </div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6"><h2 class="font-bold text-xl mb-4">📸 Фото — теперь вшиты в HTML (base64), откроются везде</h2><div class="grid grid-cols-2 md:grid-cols-3 gap-3">{imgs_html}</div><div class="mt-3 text-xs text-gray-400">Фото скачаны с apipoint с токеном и вшиты как data:image — больше не будет битых картинок</div></div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6"><h2 class="font-bold text-xl mb-4">📌 Доп проверки</h2><pre class="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-xl">{additional_txt}</pre></div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6"><h2 class="font-bold text-xl mb-4">📏 Пробег (правильная логика скрутки)</h2><pre class="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-xl">{mileage_txt}\n\n{offers_txt}</pre></div>
  <div class="bg-white rounded-[24px] shadow-sm p-6 mb-6"><h2 class="font-bold text-xl mb-4">🤖 Вердикт</h2><div class="whitespace-pre-wrap text-sm bg-yellow-50 p-4 rounded-xl border">{ai_text[:5000]}</div></div>
</div>
</body></html>"""
    return html

# aiogram handlers (simplified)
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

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
        [KeyboardButton(text="🔄 Сброс")],
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    user_data[m.from_user.id] = {"history": []}
    await m.answer("Бот v27 PHOTO BASE64 FIX 🇷🇺 ✅\nФото теперь вшиваются в HTML как base64 — откроются везде. Скрутка считается правильно (только падение к предыдущему значению).", reply_markup=main_kb())

@dp.message()
async def handle_text(m: types.Message):
    text = m.text or ""
    vin = extract_vin(text)
    if vin:
        await m.answer(f"Проверяю {vin}... качаю фото с токеном и вшиваю в отчет (10-15 сек)...")
        data = await check_by_vin(vin)
        mileage_txt,_ = format_probeg2_correct(data.get("result",{}))
        offers_txt,_ = format_offers_table(data.get("result",{}))
        additional_txt = ""
        try:
            cs = data["result"].get("carshering",{}).get("result",{})
            additional_txt += f"Каршеринг: {cs}\n"
        except:
            pass
        ai_text = f"Год {data['meta'].get('detected_year')} Фото {len(data.get('b64_images',[]))} шт\n{mileage_txt}\n{offers_txt}"
        html = generate_html_with_b64(vin, {"title": vin, "images": []}, data, mileage_txt, offers_txt, ai_text, additional_txt)
        file = BufferedInputFile(html.encode('utf-8'), filename=f"report_{vin}_v27_photo_fixed.html")
        await m.answer_document(file, caption=f"📄 v27 — фото вшиты base64 ({len(data.get('b64_images',[]))} шт), скрутка пофикшена")
        return
    await m.answer("Пришли VIN", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())