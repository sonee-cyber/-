import asyncio, os, base64, re, json
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OR_KEY = os.getenv("OPENAI_API_KEY")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN")
APIPOINT_BASE = os.getenv("APIPOINT_BASE", "https://apipoint.ru/api")

print(f"OPENAI: {bool(OR_KEY)} | APIPOINT: {bool(APIPOINT_KEY)}")

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

HOOD_STEPS = [
    "1/8 — Спереди", "2/8 — Сзади", "3/8 — Левый бок", "4/8 — Правый бок",
    "5/8 — VIN под лобовым + стойка", "6/8 — Приборка с пробегом", "7/8 — Под капотом",
    "8/8 — Видео запуска 15 сек"
]

def is_vin(s: str):
    return bool(re.match(r'^[A-HJ-NPR-Z0-9]{17}$', s.upper().strip()))

def is_gosnum(s: str):
    s = s.upper().replace(" ", "")
    return bool(re.match(r'^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$', s))

def extract_urls(text: str):
    return re.findall(r'https?://[^\s]+', text)

def extract_gos_from_text(text: str):
    m = re.search(r'[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\s*\d{2,3}', text.upper())
    return m.group(0).replace(" ", "") if m else None

async def apipoint_call(point: str, params: dict):
    if not APIPOINT_KEY:
        return {"error": "no_key"}
    p = point.lower()
    urls = [f"{APIPOINT_BASE}/{p}", f"{APIPOINT_BASE}/{point}"]
    headers = {"Authorization": f"Bearer {APIPOINT_KEY}", "X-API-KEY": APIPOINT_KEY}
    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    txt = await resp.text()
                    try: j = json.loads(txt)
                    except: j = {"raw": txt[:2000]}
                    if resp.status == 404: continue
                    return {"status": resp.status, "data": j}
            except: continue
        return {"error": "failed"}

async def build_remote_report(gos_or_vin: str):
    gos = gos_or_vin.upper().replace(" ", "")
    is_v = is_vin(gos)
    results = {}
    for main_point in ["Reportjson", "Fullapi", "Check"]:
        params = {"vin": gos} if is_v else {"gosnum": gos}
        results[main_point.lower()] = await apipoint_call(main_point, params)
    for ep in ["Dtp", "Zalog", "Probeg", "Fsspdata", "Nomerogram", "Offerbygosnum", "Carprices"]:
        params = {"vin": gos} if is_v else {"gosnum": gos}
        results[ep.lower()] = await apipoint_call(ep, params)
    return results

async def fetch_ad_data(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                title = soup.title.string if soup.title else ""
                og_desc = soup.find("meta", property="og:description")
                desc = og_desc["content"] if og_desc and og_desc.has_attr("content") else soup.get_text()[:2000]
                price = None
                m_price = re.search(r'(\d[\d\s]{3,})\s*₽', html)
                if m_price: price = m_price.group(1)
                images = []
                for meta in soup.find_all("meta", property="og:image"):
                    if meta.has_attr("content"): images.append(meta["content"])
                return {"url": url, "title": title[:300], "description": desc[:2000], "price": price, "images": images[:8], "html_len": len(html)}
    except Exception as e:
        return {"url": url, "error": str(e), "images": []}

def b64_from_bytes(b: bytes):
    return base64.b64encode(b).decode()

def get_vin_request_text(ad_data=None):
    title = ad_data.get("title")[:60] if ad_data and ad_data.get("title") else "ваше авто"
    return (
        f"Привет! Интересует {title}.\n\n"
        "Можете скинуть, пожалуйста:\n"
        "1. Госномер и VIN для проверки по базам ГИБДД/залоги\n"
        "2. Фото ПТС (можно замазать серию)\n"
        "3. Фото порогов изнутри, стаканов, пола под водителем\n"
        "4. Видео холодного запуска 15 сек + прогазовка\n\n"
        "Сразу подъеду смотреть если все ок. Спасибо!"
    )

def get_torg_text(ad_data=None, issues=None):
    return (
        "Привет! Посмотрел машину вживую, есть нюансы:\n"
        "- Перекрас / ржавчина по порогам\n"
        "- По базам есть вопросы\n"
        "- Резина лысая, нужно вложиться\n\n"
        "Готов забрать сегодня за [ВАША ЦЕНА] с учетом вложений. Что скажете?"
    )

@dp.message(Command("start"))
async def start(m: types.Message):
    user_data[m.from_user.id] = {"stage": "idle", "photos_hood": [], "hood_step": 0, "last_gos": "", "last_ad": None}
    await m.answer("Бот v4 — с кнопкой запроса VIN ✅\nКидай ссылку + номер или просто ссылку", reply_markup=main_kb())

@dp.message(F.text == "🔄 Сбросить")
async def reset(m: types.Message):
    user_data[m.from_user.id] = {"stage": "idle", "photos_hood": [], "hood_step": 0, "last_gos": "", "last_ad": None}
    await m.answer("Сбросил", reply_markup=main_kb())

@dp.message(F.text.contains("Запросить VIN"))
async def vin_request(m: types.Message):
    uid = m.from_user.id
    ad = user_data.get(uid, {}).get("last_ad")
    txt = get_vin_request_text(ad)
    torg = get_torg_text(ad)
    await m.answer(f"📩 ШАБЛОН ДЛЯ ПРОДАВЦА (скопируй):\n\n{txt}\n\n---\n\n💰 ШАБЛОН ДЛЯ ТОРГА У КАПОТА:\n\n{torg}", reply_markup=cancel_kb())

@dp.message(F.text.contains("Дистанционка"))
async def mode_remote(m: types.Message):
    user_data[m.from_user.id] = {"stage": "await_gos", "last_ad": None}
    await m.answer("🔍 Кидай ссылку на Авито/Дром/Авто.ру + госномер если есть. Если номера нет — нажми 📩 Запросить VIN", reply_markup=cancel_kb())

@dp.message(F.text.contains("у капота"))
async def mode_hood(m: types.Message):
    user_data[m.from_user.id] = {"stage": "hood", "photos_hood": [], "hood_step": 0}
    await m.answer(f"🚗 У КАПОТА — {HOOD_STEPS[0]}", reply_markup=cancel_kb())

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(m: types.Message):
    uid = m.from_user.id
    txt = m.text.strip()
    if any(x in txt for x in ["Дистанционка", "у капота", "Запросить VIN", "Сбросить"]): return

    urls = extract_urls(txt)
    gos = extract_gos_from_text(txt) or (txt.upper().replace(" ", "") if is_gosnum(txt) or is_vin(txt) else None)

    if urls:
        ad_url = urls[0]
        if gos: user_data.setdefault(uid, {})["last_gos"] = gos
        await m.answer(f"Вижу ссылку ✅ {ad_url}\nТяну объявление... ⏳")
        ad_data = await fetch_ad_data(ad_url)
        user_data.setdefault(uid, {})["last_ad"] = ad_data

        ad_images_b64 = []
        if ad_data.get("images"):
            async with aiohttp.ClientSession() as session:
                for img_url in ad_data["images"][:5]:
                    try:
                        async with session.get(img_url, timeout=10) as r:
                            if r.status == 200:
                                b = await r.read()
                                ad_images_b64.append(b64_from_bytes(b))
                    except: pass

        if not user_data.get(uid, {}).get("last_gos"):
            user_data[uid]["stage"] = "await_gos_for_ad"
            user_data[uid]["ad_images_b64"] = ad_images_b64
            await m.answer(
                f"📄 Объява: {ad_data.get('title','')[:100]}\nЦена: {ad_data.get('price','?')} ₽\n\n"
                "Госномер скрыт — нажми 📩 Запросить VIN у продавца и скинь ему шаблон. Как только даст номер — кидай сюда и я пробью базы + сравню с объявой.",
                reply_markup=cancel_kb()
            )
            return
        else:
            await do_full_ad_report(m, ad_data, ad_images_b64, user_data[uid]["last_gos"])
            return

    if user_data.get(uid, {}).get("stage") == "await_gos_for_ad" and gos:
        user_data[uid]["last_gos"] = gos
        await do_full_ad_report(m, user_data[uid].get("last_ad"), user_data[uid].get("ad_images_b64", []), gos)
        return

    if user_data.get(uid, {}).get("stage") == "await_gos" and gos:
        user_data[uid]["last_gos"] = gos
        raw = await build_remote_report(gos) if APIPOINT_KEY else {"demo": True}
        await ai_remote_only(m, gos, raw)
        return

async def do_full_ad_report(m, ad_data, ad_images_b64, gos):
    uid = m.from_user.id
    await m.answer(f"Делаю комбо-отчет объява + базы по {gos}... ⏳")
    raw = await build_remote_report(gos) if APIPOINT_KEY else {"demo": True}
    if not client:
        await m.answer(str(raw)[:3000]); return
    vision_parts = []
    for b64 in ad_images_b64[:5]:
        vision_parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    prompt = f"""
Ты перекуп. Ссылка {ad_data.get('url')} Гос {gos}
Объява: {ad_data.get('title')} Цена {ad_data.get('price')} Описание {ad_data.get('description')[:1000]}
Базы: {json.dumps(raw, ensure_ascii=False)[:8000]}

Сделай: ТАЧКА, ФОТО ИЗ ОБЪЯВЫ, СВЕРКА С БАЗАМИ (пробег, владельцы, ДТП, залог), ЦЕНА, КРАСНЫЕ ФЛАГИ, ВЕРДИКТ ЕХАТЬ/НЕ ЕХАТЬ.
Коротко.
"""
    try:
        resp = await client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}] + vision_parts}],
            max_tokens=1200
        )
        await m.answer(resp.choices[0].message.content, reply_markup=main_kb())
        user_data[uid]["stage"] = "idle"
    except Exception as e:
        await m.answer(f"Ошибка ИИ: {e}")

async def ai_remote_only(m, gos, raw):
    if not client:
        await m.answer(str(raw)[:3000]); return
    prompt = f"Авто {gos} данные {json.dumps(raw, ensure_ascii=False)[:8000]} Сделай отчет ГИБДД, залог, пробег, Номерограм, цена, вердикт."
    r = await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=800)
    await m.answer(r.choices[0].message.content, reply_markup=main_kb())

@dp.message(F.photo)
async def handle_photo(m: types.Message):
    uid = m.from_user.id
    if user_data.get(uid, {}).get("stage")!= "hood": return
    step = user_data[uid].get("hood_step", 0)
    user_data[uid].setdefault("photos_hood", []).append(m.photo[-1].file_id)
    if client:
        try:
            file = await bot.get_file(m.photo[-1].file_id)
            fb = await bot.download_file(file.file_path)
            b64 = b64_from_bytes(fb.read())
            prompt = f"Шаг {HOOD_STEPS[step]}. Оцени фото: перекрас, зазоры, ржавчина. Коротко 2 предл, балл"
            resp = await client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}],
                max_tokens=200
            )
            await m.answer(f"✅ {HOOD_STEPS[step]}\n{resp.choices[0].message.content}")
        except: await m.answer(f"✅ Принял {HOOD_STEPS[step]}")
    user_data[uid]["hood_step"] += 1
    ns = user_data[uid]["hood_step"]
    if ns < len(HOOD_STEPS):
        await m.answer(f"Дальше: {HOOD_STEPS[ns]}")
    else:
        await m.answer("Все фото собрал! Кидай видео запуска")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())