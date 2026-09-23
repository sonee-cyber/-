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

print(f"BOOT v7 FINAL | BOT={bool(BOT_TOKEN)} APIPOINT={bool(APIPOINT_KEY)}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN empty")

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

def extract_urls(t): return re.findall(r'https?://[^\s]+', t)

VALID_SOURCES_VIN = ["zalog","fsspdata","gibddhistory","dtp","probeg","nomerogram","carprices","gai","regperiods","autophoto","offerbygosnum"]
VALID_SOURCES_GOS = ["zalog"]

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
                    data = {"raw": txt}
                return resp.status, data
        except Exception as e:
            return 0, {"error": str(e)}

async def check_by_gos(gos):
    payload = {"sources": "zalog", "gosnum": gos}
    status, data = await apipoint_call(payload)
    return data

async def check_by_vin(vin):
    payload = {"sources": ",".join(VALID_SOURCES_VIN), "vin": vin}
    status, data = await apipoint_call(payload)
    return data

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
    return f"Привет! Интересует {t}.\n\nСкиньте, пожалуйста, VIN и госномер — пробью по ГИБДД/залоги/ДТП.\nА также: фото ПТС, порогов изнутри, стаканов и видео холодного запуска 15 сек.\n\nСразу подъеду если все ок."

@dp.message(Command("start"))
async def start(m: types.Message):
    user_data[m.from_user.id] = {"stage":"idle","photos_hood":[],"hood_step":0,"last_gos":"","last_ad":None}
    await m.answer("Бот v7 — готов ✅\nКидай госномер (Х423КО550 / X423KO550) или VIN.\nПо госномеру покажу флаг залога, для полного отчета нужен VIN.", reply_markup=main_kb())

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
    await m.answer("🔍 Кидай ссылку + госномер или VIN. Если номера нет — жми 📩 Запросить VIN", reply_markup=cancel_kb())

@dp.message(F.text.contains("у капота"))
async def mode_hood(m: types.Message):
    user_data[m.from_user.id]={"stage":"hood","photos_hood":[],"hood_step":0}
    await m.answer(f"🚗 У КАПОТА — {HOOD_STEPS[0]}", reply_markup=cancel_kb())

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(m: types.Message):
    uid=m.from_user.id
    txt=m.text.strip()
    if any(x in txt for x in ["Дистанционка","у капота","Запросить VIN","Сбросить"]): return
    urls=extract_urls(txt)
    vin=extract_vin(txt)
    gos=extract_gos(txt) or (normalize_plate(txt) if is_gosnum(txt) else None)
    if vin: gos = None

    if urls:
        ad_url=urls[0]
        if gos: user_data.setdefault(uid,{})["last_gos"]=gos
        if vin: user_data.setdefault(uid,{})["last_vin"]=vin
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
        if not gos and not vin:
            user_data[uid]["stage"]="await_gos_for_ad"
            user_data[uid]["ad_images_b64"]=ad_images
            await m.answer(f"📄 {ad_data.get('title','')[:100]}\nЦена: {ad_data.get('price','?')} ₽\n\nГосномер скрыт — нажми 📩 Запросить VIN и кинь номер/VIN", reply_markup=cancel_kb())
            return
        else:
            target = vin or gos
            await do_full(m, ad_data, ad_images, target)
            return

    if user_data.get(uid,{}).get("stage")=="await_gos_for_ad" and (gos or vin):
        target = vin or gos
        user_data[uid]["last_gos"]=gos
        await do_full(m, user_data[uid].get("last_ad"), user_data[uid].get("ad_images_b64",[]), target)
        return

    if vin:
        await m.answer(f"Бью по VIN {vin} по всем базам... ⏳")
        data = await check_by_vin(vin)
        await ai_report(m, vin, data, is_vin=True)
        return
    if gos:
        await m.answer(f"Бью по госномеру {gos} (флаг залога)... ⏳")
        data = await check_by_gos(gos)
        await ai_report(m, gos, data, is_vin=False)
        return

async def do_full(m, ad_data, ad_images_b64, target):
    uid=m.from_user.id
    await m.answer(f"Делаю комбо-отчет по {target}... ⏳")
    if is_vin(target):
        data = await check_by_vin(target)
    else:
        data = await check_by_gos(target)
    if not client:
        await m.answer(f"RAW:\n{json.dumps(data, ensure_ascii=False)[:5000]}")
        return
    vision=[]
    for b64 in ad_images_b64[:5]:
        vision.append({"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}})
    prompt = f"Ты перекуп. Ссылка {ad_data.get('url')} Цель {target} Объява {ad_data.get('title')} Цена {ad_data.get('price')} Базы {json.dumps(data, ensure_ascii=False)[:15000]} Сделай отчет: ТАЧКА, ФОТО, СВЕРКА С БАЗАМИ, ЦЕНА, ВЕРДИКТ. Если только госномер и ошибка 112 про VIN — скажи что нужен VIN."
    try:
        resp=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":[{"type":"text","text":prompt}]+vision}], max_tokens=1500)
        await m.answer(resp.choices[0].message.content, reply_markup=main_kb())
    except Exception as e:
        await m.answer(f"Ошибка ИИ: {e} RAW: {json.dumps(data, ensure_ascii=False)[:2000]}")

async def ai_report(m, target, data, is_vin=False):
    balance = data.get("balance") or data.get("data",{}).get("balance")
    price = data.get("price") or data.get("data",{}).get("price")
    result = data.get("result") or data.get("data",{}).get("result") or data
    zalog = result.get("zalog") if isinstance(result, dict) else None
    zalog_flag = False
    need_vin_msg = ""
    if isinstance(zalog, dict):
        zalog_flag = zalog.get("f") == True
        if zalog.get("error_code") == 112:
            need_vin_msg = zalog.get("error_msg") or "Должен быть указан VIN"
    if not client:
        await m.answer(f"RAW:\n{json.dumps(data, ensure_ascii=False)[:5000]}", reply_markup=main_kb())
        return
    if not is_vin:
        if zalog_flag:
            txt = f"### Отчет по {target}\nБаланс: {balance} Цена: {price}\n\n**Залог:** Да, флаг f=true (авто возможно в залоге)\n**Но:** {need_vin_msg}\n\nДля полного отчета (ГИБДД, ДТП, ФССП, пробег, номерограмма) нужен VIN. Нажми 📩 Запросить VIN у продавца и скинь VIN."
            await m.answer(txt, reply_markup=cancel_kb())
        else:
            await m.answer(f"По госномеру {target} залог не найден, но без VIN полный отчет невозможен. Баланс {balance}. Скинь VIN.", reply_markup=cancel_kb())
        prompt = f"Авто госномер {target} Результат залога {json.dumps(zalog, ensure_ascii=False)} Баланс {balance} Сделай краткий вердикт: залог флаг, почему нужен VIN, что запросить у продавца."
        try:
            r=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=1000)
            await m.answer(r.choices[0].message.content, reply_markup=main_kb())
        except Exception as e:
            await m.answer(f"Ошибка ИИ: {e}")
        return
    prompt = f"Авто VIN {target} Баланс {balance} Цена {price} Данные {json.dumps(result, ensure_ascii=False)[:15000]} Сделай полный отчет: 1.ГИБДД 2.ДТП 3.Залог 4.ФССП 5.Пробег 6.Номерограмма 7.Цена 8.ВЕРДИКТ — брать или нет и почему."
    try:
        r=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=1500)
        await m.answer(r.choices[0].message.content, reply_markup=main_kb())
    except Exception as e:
        await m.answer(f"Ошибка ИИ: {e} RAW: {json.dumps(data, ensure_ascii=False)[:3000]}")

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
    except: pass
    print("Start polling...")
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())