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
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OR_KEY = os.getenv("OPENAI_API_KEY")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN")
APIPOINT_URL = "https://apipoint.ru/api/call"

print(f"BOOT v6.3 | BOT_TOKEN={bool(BOT_TOKEN)} APIPOINT_KEY={bool(APIPOINT_KEY)} OPENAI={bool(OR_KEY)}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN env is empty! Set it in Railway Variables")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

user_data = {}

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔍 Дистанционка по номеру/VIN/ссылке")],
        [KeyboardButton(text="🚗 Я у капота (фото+видео)")],
        [KeyboardButton(text="📩 Запросить VIN у продавца")],
        [KeyboardButton(text="🔄 Сбросить")],
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📩 Запросить VIN у продавца")],
        [KeyboardButton(text="🔄 Сбросить")],
    ], resize_keyboard=True)

HOOD_STEPS = ["1/8 — Спереди","2/8 — Сзади","3/8 — Левый бок","4/8 — Правый бок","5/8 — VIN","6/8 — Приборка","7/8 — Под капотом","8/8 — Видео"]

def normalize_plate(s: str) -> str:
    """Латиницу -> кириллицу для API"""
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

def extract_urls(t): return re.findall(r'https?://[^\s]+', t)

async def apipoint_full_report(gos_or_vin: str):
    if not APIPOINT_KEY:
        return {"error": "no APIPOINT_KEY"}
    orig = gos_or_vin.upper().replace(" ", "")
    clean = normalize_plate(gos_or_vin)
    is_v = is_vin(orig)
    sources = "gibdd,dtp,zalog,probeg,fsspdata,nomerogram,offerbygosnum,carprices,regperiods,gibddhistory,autophoto,gai,fines,osago"
    payload = {"sources": sources}
    if is_v:
        payload["vin"] = orig
    else:
        payload["gosnum"] = clean
        payload["vin"] = ""
    headers = {
        "Authorization": f"Bearer {APIPOINT_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(APIPOINT_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=40)) as resp:
                txt = await resp.text()
                print(f"[APIPOINT] status={resp.status} payload={payload} resp[:2000]={txt[:2000]}")
                try:
                    data = json.loads(txt)
                except:
                    data = {"raw": txt}
                if resp.status!= 200:
                    return {"status": resp.status, "error": txt[:2000], "payload": payload, "data": data}
                return data
        except Exception as e:
            return {"error": f"exception {e}", "payload": payload}

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
                    desc = og_desc["content"] if og_desc and og_desc.has_attr("content") else soup.get_text()[:2000]
                    images = [m.get("content") for m in soup.find_all("meta", property="og:image") if m.get("content")]
                else:
                    m_title = re.search(r'<title>(.*?)</title>', html, re.I|re.S)
                    title = m_title.group(1) if m_title else ""
                    desc = html[:2000]
                    images = re.findall(r'property="og:image" content="([^"]+)"', html)
                m_price = re.search(r'(\d[\d\s]{3,})\s*₽', html)
                price = m_price.group(1) if m_price else None
                return {"url": url, "title": title[:300], "description": desc[:2000], "price": price, "images": images[:8]}
    except Exception as e:
        return {"url": url, "error": str(e), "images": []}

def b64_from_bytes(b: bytes): return base64.b64encode(b).decode()
def get_vin_template(ad=None):
    t = ad.get("title")[:60] if ad and ad.get("title") else "ваше авто"
    return f"Привет! Интересует {t}.\n\nМожете скинуть, пожалуйста:\n1. Госномер и VIN для проверки по базам ГИБДД/залоги\n2. Фото ПТС\n3. Фото порогов изнутри, стаканов\n4. Видео холодного запуска 15 сек\n\nСразу подъеду если все ок."

@dp.message(Command("start"))
async def start(m: types.Message):
    print(f"/start from {m.from_user.id}")
    user_data[m.from_user.id] = {"stage":"idle","photos_hood":[],"hood_step":0,"last_gos":"","last_ad":None}
    await m.answer("Бот v6.3 — принимает и латиницу и кириллицу ✅\nКидай Х423КО550 или X423KO550", reply_markup=main_kb())

@dp.message(F.text=="🔄 Сбросить")
async def reset(m: types.Message):
    user_data[m.from_user.id] = {"stage":"idle","photos_hood":[],"hood_step":0,"last_gos":"","last_ad":None}
    await m.answer("Сбросил", reply_markup=main_kb())

@dp.message(F.text.contains("Запросить VIN"))
async def vin_req(m: types.Message):
    ad=user_data.get(m.from_user.id,{}).get("last_ad")
    await m.answer(f"📩 ШАБЛОН ДЛЯ ПРОДАВЦА:\n\n{get_vin_template(ad)}", reply_markup=cancel_kb())

@dp.message(F.text.contains("Дистанционка"))
async def mode_remote(m: types.Message):
    user_data[m.from_user.id]={"stage":"await_gos","last_ad":None}
    await m.answer("🔍 Кидай ссылку + госномер. Если номера нет — жми 📩 Запросить VIN", reply_markup=cancel_kb())

@dp.message(F.text.contains("у капота"))
async def mode_hood(m: types.Message):
    user_data[m.from_user.id]={"stage":"hood","photos_hood":[],"hood_step":0}
    await m.answer(f"🚗 У КАПОТА — {HOOD_STEPS[0]}", reply_markup=cancel_kb())

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(m: types.Message):
    uid=m.from_user.id
    txt=m.text.strip()
    print(f"text from {uid}: {txt[:100]} stage={user_data.get(uid,{}).get('stage')}")
    if any(x in txt for x in ["Дистанционка","у капота","Запросить VIN","Сбросить"]): return
    urls=extract_urls(txt)
    gos=extract_gos(txt) or (normalize_plate(txt) if is_gosnum(txt) or is_vin(txt) else None)

    if urls:
        ad_url=urls[0]
        if gos: user_data.setdefault(uid,{})["last_gos"]=gos
        await m.answer(f"Вижу ссылку ✅ {ad_url}\nТяну объявление... ⏳")
        ad_data=await fetch_ad_data(ad_url)
        user_data.setdefault(uid,{})["last_ad"]=ad_data
        ad_images=[]
        if ad_data.get("images"):
            async with aiohttp.ClientSession() as session:
                for img_url in ad_data["images"][:5]:
                    try:
                        async with session.get(img_url, timeout=10) as r:
                            if r.status==200:
                                b=await r.read()
                                ad_images.append(b64_from_bytes(b))
                    except: pass
        if not user_data.get(uid,{}).get("last_gos"):
            user_data[uid]["stage"]="await_gos_for_ad"
            user_data[uid]["ad_images_b64"]=ad_images
            await m.answer(f"📄 {ad_data.get('title','')[:100]}\nЦена: {ad_data.get('price','?')} ₽\n\nГосномер скрыт — нажми 📩 Запросить VIN", reply_markup=cancel_kb())
            return
        else:
            await do_full(m, ad_data, ad_images, user_data[uid]["last_gos"])
            return

    if user_data.get(uid,{}).get("stage")=="await_gos_for_ad" and gos:
        user_data[uid]["last_gos"]=gos
        await do_full(m, user_data[uid].get("last_ad"), user_data[uid].get("ad_images_b64",[]), gos)
        return

    if gos:
        user_data.setdefault(uid, {})["last_gos"]=gos
        await m.answer(f"Бью по апиПоинт {gos} одним запросом по всем базам... ⏳")
        raw=await apipoint_full_report(gos)
        await ai_remote(m, gos, raw)
        return
    else:
        if txt and len(txt) < 20 and not urls and txt not in ["🔍 Дистанционка по номеру/VIN/ссылке", "🚗 Я у капота (фото+видео)"]:
            if not is_gosnum(txt) and not is_vin(txt):
                await m.answer(f"Не понял номер: {txt}\nПришли госномер типа Х423КО550 / X423KO550 или VIN, или ссылку на Авито", reply_markup=main_kb())

async def do_full(m, ad_data, ad_images_b64, gos):
    uid=m.from_user.id
    await m.answer(f"Делаю комбо-отчет по {gos}... ⏳")
    raw=await apipoint_full_report(gos)
    if not client:
        await m.answer(f"RAW:\n{json.dumps(raw, ensure_ascii=False)[:4000]}")
        return
    vision=[]
    for b64 in ad_images_b64[:5]:
        vision.append({"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}})
    prompt = f"Ты перекуп. Ссылка {ad_data.get('url')} Гос {gos} Объява {ad_data.get('title')} Цена {ad_data.get('price')} Базы {json.dumps(raw, ensure_ascii=False)[:12000]} Сделай: ТАЧКА, ФОТО, СВЕРКА С БАЗАМИ, ЦЕНА, ВЕРДИКТ."
    try:
        resp=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":[{"type":"text","text":prompt}]+vision}], max_tokens=1500)
        await m.answer(resp.choices[0].message.content, reply_markup=main_kb())
        user_data[uid]["stage"]="idle"
    except Exception as e:
        await m.answer(f"Ошибка ИИ: {e} RAW: {json.dumps(raw, ensure_ascii=False)[:2000]}")

async def ai_remote(m, gos, raw):
    if "error" in raw and "data" not in raw and "result" not in raw:
        await m.answer(f"❌ АпиПоинт ошибка: {json.dumps(raw, ensure_ascii=False)[:2000]}", reply_markup=main_kb())
        return
    if not client:
        await m.answer(f"RAW апиПоинт:\n{json.dumps(raw, ensure_ascii=False)[:5000]}", reply_markup=main_kb())
        return
    balance = raw.get("balance")
    price = raw.get("price")
    result = raw.get("result", raw)
    prompt = f"Авто {gos} Баланс {balance} Цена {price} Данные {json.dumps(result, ensure_ascii=False)[:15000]} Сделай отчет: ГИБДД, ДТП, залог, ФССП, пробег, Номерограм, цена, ВЕРДИКТ."
    try:
        r=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=1500)
        await m.answer(r.choices[0].message.content, reply_markup=main_kb())
    except Exception as e:
        await m.answer(f"Ошибка ИИ: {e} RAW: {json.dumps(raw, ensure_ascii=False)[:3000]}")

@dp.message(F.photo)
async def handle_photo(m: types.Message):
    uid=m.from_user.id
    if user_data.get(uid,{}).get("stage")!="hood": return
    step=user_data[uid].get("hood_step",0)
    user_data[uid].setdefault("photos_hood",[]).append(m.photo[-1].file_id)
    if client:
        try:
            file=await bot.get_file(m.photo[-1].file_id)
            fb=await bot.download_file(file.file_path)
            b64=b64_from_bytes(fb.read())
            prompt=f"Шаг {HOOD_STEPS[step]}. Оцени фото: перекрас, зазоры, ржавчина. Коротко, балл"
            resp=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}}]}], max_tokens=200)
            await m.answer(f"✅ {HOOD_STEPS[step]}\n{resp.choices[0].message.content}")
        except: await m.answer(f"✅ Принял {HOOD_STEPS[step]}")
    user_data[uid]["hood_step"]+=1
    ns=user_data[uid]["hood_step"]
    if ns < len(HOOD_STEPS):
        await m.answer(f"Дальше: {HOOD_STEPS[ns]}")
    else:
        await m.answer("Все фото собрал! Кидай видео")

async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("Webhook deleted")
    except Exception as e:
        print(f"delete_webhook error: {e}")
    print("Start polling...")
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())