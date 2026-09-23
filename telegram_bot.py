
import asyncio, os, base64, re, json
from datetime import datetime
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OR_KEY = os.getenv("OPENAI_API_KEY")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN") or os.getenv("APIPOINT_API_KEY")
APIPOINT_BASE = os.getenv("APIPOINT_BASE", "https://apipoint.ru/api")

print(f"OPENAI KEY: {bool(OR_KEY)} | APIPOINT KEY: {bool(APIPOINT_KEY)} | BASE: {APIPOINT_BASE}")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

# state
user_data = {}

# Keyboards
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Дистанционка по номеру/VIN")],
            [KeyboardButton(text="🚗 Я у капота (фото+видео)")],
            [KeyboardButton(text="🔄 Сбросить")],
        ],
        resize_keyboard=True
    )

def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔄 Сбросить")]],
        resize_keyboard=True
    )

HOOD_STEPS = [
    "1/8 — Спереди (весь перед, фары, бампер)",
    "2/8 — Сзади (багажник, фонари)",
    "3/8 — Левый бок целиком",
    "4/8 — Правый бок целиком",
    "5/8 — VIN под лобовым + на стойке (2 фото)",
    "6/8 — Приборка с пробегом (заведи, чтобы ошибки видно)",
    "7/8 — Под капотом",
    "8/8 — Видео запуска: 5 сек до запуска, запуск, 10 сек холостые + прогазовка",
]

def is_vin(s: str):
    return bool(re.match(r'^[A-HJ-NPR-Z0-9]{17}$', s.upper().strip()))

def is_gosnum(s: str):
    s = s.upper().replace(" ", "")
    # Х423КО550, А123АА777 etc
    return bool(re.match(r'^[АВЕКМНОРСТУХABEKMHOPCTYX]\d{3}[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\d{2,3}$', s)) or bool(re.match(r'^\d{4}[АВЕКМНОРСТУХ]{2}\d{2,3}$', s))

async def apipoint_call(point: str, params: dict):
    """Универсальный вызов apipoint. Пробует несколько форматов авторизации."""
    if not APIPOINT_KEY:
        return {"error": "no_key", "message": "APIPOINT_KEY не задан в Railway"}
    
    # нормализуем имя поинта
    p = point.lower()
    # варианты урлов которые встречаются у apipoint
    urls = [
        f"{APIPOINT_BASE}/{p}",
        f"{APIPOINT_BASE}/{point}",
        f"https://apipoint.ru/api/{p}",
        f"https://apipoint.ru/api/{point}",
    ]
    
    headers = {
        "Authorization": f"Bearer {APIPOINT_KEY}",
        "X-API-KEY": APIPOINT_KEY,
        "Accept": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    text = await resp.text()
                    # попробуем json
                    try:
                        j = json.loads(text)
                    except:
                        j = {"raw": text[:2000], "status": resp.status}
                    
                    if resp.status == 404:
                        continue # пробуем следующий url
                    return {"url": url, "status": resp.status, "data": j, "params": params}
            except Exception as e:
                last_err = str(e)
                continue
        return {"error": "all_urls_failed", "last_error": last_err if 'last_err' in locals() else "unknown"}

async def build_remote_report(gosnum_or_vin: str):
    """Делаем комбо-запросы по апипоинт: gibdd + nomerogram + offers"""
    gos = gosnum_or_vin.upper().replace(" ", "")
    is_v = is_vin(gos)
    
    results = {}
    
    # 1. Если госномер -> пробуем получить VIN
    if not is_v:
        r = await apipoint_call("Number2vin", {"gosnum": gos, "gosnumber": gos, "number": gos})
        results["number2vin"] = r
        # иногда vin внутри
        # 2. Основной отчет - пробуем Reportjson / Fullapi / Check
        for main_point in ["Reportjson", "Fullapi", "Check", "Reportnewcheck"]:
            r = await apipoint_call(main_point, {"gosnum": gos, "gosnumber": gos, "number": gos})
            results[main_point.lower()] = r
            # если успешно и есть данные - можно стоп, но соберем все
            if r.get("status") == 200 and r.get("data"):
                # не прерываем, соберем еще парочку
                pass
    else:
        # по VIN
        for main_point in ["Reportjson", "Fullapi", "Check", "Zalogvin", "Offerbyvin"]:
            r = await apipoint_call(main_point, {"vin": gos, "VIN": gos})
            results[main_point.lower()] = r

    # 3. Точечно добираем самое важное (даже если Reportjson уже все дал)
    extra_points = ["Dtp", "Gibddhistory", "Gai", "Zalog", "Fsspdata", "Probeg", "Regperiods", "Nomerogram", "Offerbygosnum", "Offerbyvin", "Autophoto", "Leasing", "Carshering", "Customs"]
    for ep in extra_points:
        # чтобы не спамить платно, берем только если нет ключа - пропустим, а если есть - берем только первые 6 самых ценных
        # в проде можно все
        if ep in ["Nomerogram", "Offerbygosnum", "Dtp", "Zalog", "Probeg", "Fsspdata"]:
            params = {"vin": gos} if is_v else {"gosnum": gos, "gosnumber": gos}
            r = await apipoint_call(ep, params)
            results[ep.lower()] = r

    return results

def make_b64_from_telegram_file(file_bytes: bytes):
    return base64.b64encode(file_bytes).decode()

@dp.message(Command("start"))
async def start(m: types.Message):
    user_data[m.from_user.id] = {"stage": "idle", "photos_remote": [], "photos_hood": [], "hood_step": 0, "desc": "", "last_gos": ""}
    await m.answer(
        f"Бот перезапущен!\nOpenAI: {bool(OR_KEY)} ✅\nApiPoint: {bool(APIPOINT_KEY)} {'✅' if APIPOINT_KEY else '⏳ ждем ключ'}\n\n"
        "Выбери режим:\n"
        "🔍 Дистанционка — кидаешь номер, я делаю отчет по ГИБДД + Номерограм + ИИ анализ\n"
        "🚗 Я у капота — веду за руку: фото кузова, VIN, приборка, видео мотора и сразу вердикт",
        reply_markup=main_kb()
    )

@dp.message(F.text == "🔄 Сбросить")
async def reset(m: types.Message):
    user_data[m.from_user.id] = {"stage": "idle", "photos_remote": [], "photos_hood": [], "hood_step": 0, "desc": "", "last_gos": ""}
    await m.answer("Сбросил. Выбери режим:", reply_markup=main_kb())

@dp.message(F.text.contains("Дистанционка"))
async def mode_remote(m: types.Message):
    user_data[m.from_user.id] = {"stage": "await_gos", "photos_hood": [], "hood_step": 0, "desc": "", "last_gos": ""}
    await m.answer(
        "🔍 Режим ДИСТАНЦИОНКА\n\n"
        "Кидай госномер (Х423КО550) или VIN (17 символов).\n"
        "Я пробью по апиПоинт: ГИБДД, залог, пробег, ФССП + Номерограм фото со старых объвлений и дам ИИ-вердикт стоит ли ехать.",
        reply_markup=cancel_kb()
    )

@dp.message(F.text.contains("у капота"))
async def mode_hood(m: types.Message):
    uid = m.from_user.id
    user_data[uid] = {"stage": "hood", "photos_hood": [], "hood_step": 0, "desc": "", "last_gos": user_data.get(uid, {}).get("last_gos", ""), "hood_reports": []}
    await m.answer(
        "🚗 Режим У КАПОТА\n\n"
        f"Буду вести по шагам. Всего {len(HOOD_STEPS)} шагов.\n"
        f"Шаг {HOOD_STEPS[0]}\n\nКидай фото, я сразу скажу что вижу.",
        reply_markup=cancel_kb()
    )

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(m: types.Message):
    uid = m.from_user.id
    txt = m.text.strip()
    
    # игнор кнопок
    if txt in ["🔍 Дистанционка по номеру/VIN", "🚗 Я у капота (фото+видео)", "🔄 Сбросить", "🚗 Оценить авто"]:
        return

    # если ждем госномер
    state = user_data.get(uid, {}).get("stage")
    if state == "await_gos":
        gos = txt.upper().replace(" ", "")
        if not (is_vin(gos) or is_gosnum(gos) or len(gos) >= 6):
            await m.answer("Не похоже на госномер или VIN. Пример: Х423КО550 или XW8ZZZ61ZKG... Кидай еще раз:")
            return
        
        user_data[uid]["last_gos"] = gos
        user_data[uid]["stage"] = "idle"
        
        await m.answer(f"Принял {gos} ✅\nДергаю апиПоинт (Gibdd, Zalog, Probeg, Nomerogram, Offerbygosnum)... ⏳")
        
        if not APIPOINT_KEY:
            await m.answer(
                "⚠️ APIPOINT_KEY еще не подключен в Railway (ждем апрува).\n"
                "Пока покажу как будет выглядеть отчет, как только дадут ключ — заработает по-настоящему.\n\n"
                f"Демо для {gos}: пока нет данных, но ИИ уже готов анализировать."
            )
            # все равно делаем ИИ заглушку
            raw_results = {"demo": True, "gos": gos}
        else:
            raw_results = await build_remote_report(gos)
        
        # ИИ анализ отчета
        if not client:
            await m.answer(f"Сырые данные от апиПоинт:\n```{json.dumps(raw_results, ensure_ascii=False, indent=2)[:3500]}```", parse_mode="Markdown")
            return

        try:
            # сжимаем данные для промпта
            trimmed = json.dumps(raw_results, ensure_ascii=False)[:12000]
            prompt = f"""
Ты жесткий автоподборщик, 20 лет опыта. Клиент прислал номер {gos}.
Вот сырые данные от ApiPoint (Gibdd, Nomerogram, Drom/Avito offers, залоги, пробеги):

{trimmed}

Сделай отчет СТРОГО в формате:

🚗 АВТО: что за тачка по базам

📜 ИСТОРИЯ ГИБДД: ДТП, владельцы, ограничения

🔢 ПРОБЕГ: есть ли скрутка, сравни Probeg и объявления

📸 НОМЕРОГРАМ / ОБЪЯВЛЕНИЯ: были ли фото на Дроме/Авито, менялась ли цена, был ли перекрас по старым фото

⚠️ РИСКИ: топ-3 риска (залог, ФССП, такси, утилизация и тд)

💰 ЦЕНА: рыночная и за сколько брать, на что давить

✅ ВЕРДИКТ: ЕХАТЬ СМОТРЕТЬ / НЕ ЕХАТЬ / ЕХАТЬ ЕСЛИ...

Пиши как свой, коротко, без воды. Если данных нет - так и пиши что база не вернула.
"""
            resp = await client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1200
            )
            answer = resp.choices[0].message.content
            await m.answer(f"📋 ДИСТАНЦИОНКА ГОТОВА по {gos}:\n\n{answer}", reply_markup=main_kb())
            await m.answer("Хочешь теперь проверить ее вживую? Жми 🚗 Я у капота и кидай фото с места.", reply_markup=main_kb())
        except Exception as e:
            await m.answer(f"Ошибка ИИ анализа: {e}\nСырые данные: {json.dumps(raw_results, ensure_ascii=False)[:3000]}")
        return
    
    # иначе просто копим описание для режима капота
    if uid not in user_data:
        user_data[uid] = {"stage": "idle", "photos_hood": [], "hood_step": 0, "desc": ""}
    user_data[uid]["desc"] = user_data[uid].get("desc", "") + " " + txt

@dp.message(F.photo)
async def handle_photo(m: types.Message):
    uid = m.from_user.id
    state = user_data.get(uid, {}).get("stage", "idle")
    
    # старый режим "оценить авто" - если stage idle и нет hood
    if state not in ["hood"]:
        # fallback к старому поведению
        if uid not in user_data:
            user_data[uid] = {"stage": "idle", "photos_hood": [], "hood_step": 0, "desc": ""}
        if "photos_remote" not in user_data[uid]:
            user_data[uid]["photos_remote"] = []
        user_data[uid]["photos_remote"].append(m.photo[-1].file_id)
        await m.answer(f"Фото принял ✅ {len(user_data[uid]['photos_remote'])}/12 (если хочешь старый отчет - жми 🚗 Оценить авто, но лучше выбери режим выше)", reply_markup=main_kb())
        return

    # режим У КАПОТА
    if state == "hood":
        step = user_data[uid].get("hood_step", 0)
        user_data[uid]["photos_hood"].append({"fid": m.photo[-1].file_id, "step": step})
        
        # быстрый ИИ анализ этого конкретного фото
        if client:
            try:
                file = await bot.get_file(m.photo[-1].file_id)
                fb = await bot.download_file(file.file_path)
                b64 = make_b64_from_telegram_file(fb.read())
                
                step_desc = HOOD_STEPS[step] if step < len(HOOD_STEPS) else f"Шаг {step+1}"
                prompt = f"""
Ты автоподборщик у капота. Клиент на шаге: {step_desc}.
Проанализируй ТОЛЬКО это фото, очень коротко, 2-3 предложения:

- Что видишь? Перекрас, зазоры, ржавчина, вмятины, состояние.
- Оценка 1-10
- На что обратить внимание вживую на этом элементе

Пиши как перекуп в гараже, без воды.
"""
                resp = await client.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]}],
                    max_tokens=300
                )
                ai_comment = resp.choices[0].message.content
                await m.answer(f"✅ Принял {step_desc}\n{ai_comment}")
            except Exception as e:
                await m.answer(f"✅ Принял {step_desc} (ИИ сейчас не ответил: {e})")
        else:
            await m.answer(f"✅ Принял {HOOD_STEPS[step] if step < len(HOOD_STEPS) else 'фото'}")

        # переход к следующему шагу
        user_data[uid]["hood_step"] += 1
        next_step = user_data[uid]["hood_step"]
        if next_step < len(HOOD_STEPS):
            await m.answer(f"Дальше: {HOOD_STEPS[next_step]}\nКидай фото.")
        else:
            await m.answer(
                "🔥 Все фото собрал! Теперь кинь ВИДЕО запуска мотора (15 сек: до запуска, запуск, холостые, прогазовка)\n"
                "Или жми 🔄 Сбросить для итогового отчета по всем фото."
            )
        return

@dp.message(F.video | F.video_note | F.voice)
async def handle_video(m: types.Message):
    uid = m.from_user.id
    if user_data.get(uid, {}).get("stage") != "hood":
        await m.answer("Видео принимаю только в режиме 🚗 Я у капота. Выбери его сначала.", reply_markup=main_kb())
        return
    
    await m.answer("Видео/звук принял ✅ Анализирую мотор... ⏳")
    
    # скачиваем видео, берем первый кадр как фото + аудио описание через GPT
    try:
        if m.video:
            fid = m.video.file_id
        elif m.video_note:
            fid = m.video_note.file_id
        else:
            fid = m.voice.file_id if m.voice else None
        
        if not fid:
            await m.answer("Не смог скачать файл")
            return

        file = await bot.get_file(fid)
        fb = await bot.download_file(file.file_path)
        data = fb.read()
        
        # для демо - анализ только как видео, без Whisper (Whisper через OpenAI тоже можно, но пока через vision первого кадра)
        # Если это голосовое - транскрибируем через whisper
        if client and m.voice:
            # whisper
            # OpenRouter не поддерживает audio, поэтому делаем заглушку - в проде надо прямой OpenAI ключ
            await m.answer("🎧 Слышу звук мотора: (демо) — ровный холостой, без стуков. В проде тут будет Whisper + анализ стуков.")
        else:
            # видео - берем как есть, GPT-4o-mini video не ест, поэтому просим юзера описать словами что слышит, а мы даем чек-лист
            await m.answer(
                "📹 Видео принял. Что слушать при запуске:\n"
                "1. Стук при холодном запуске (цепь/гидрокомпенсаторы)\n"
                "2. Синий дым при запуске (масложор)\n"
                "3. Троение, вибрация\n\n"
                "Опиши текстом что слышишь — я дам вердикт.\n"
                "Или скинь голосовое с капотом открытым."
            )
        
        # итоговый отчет по всем фото капота
        photos = user_data[uid].get("photos_hood", [])
        if len(photos) >= 3 and client:
            await m.answer(f"Делаю итоговый отчет по {len(photos)} фото с капота... ⏳")
            imgs = []
            for p in photos[-6:]: # берем последние 6 для итога
                try:
                    f = await bot.get_file(p["fid"])
                    fb2 = await bot.download_file(f.file_path)
                    b64 = make_b64_from_telegram_file(fb2.read())
                    imgs.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
                except:
                    pass
            
            prompt = f"""
Ты автоподборщик, клиент прислал {len(photos)} фото с осмотра у капота + видео мотора.
Авто: {user_data[uid].get('last_gos','неизвестно')} {user_data[uid].get('desc','')}

Дай итоговый отчет по формату:

🔍 КУЗОВ У КАПОТА: перекрасы, зазоры, ржавчина по присланным фото

🛋️ САЛОН И ПОДКАПОТКА: износ, течи, колхоз

⚠️ КРИТИЧНЫЕ КОСЯКИ: что нашел на фото

💰 ТОРГ У КАПОТА: на что давить на 20-50к скидки

✅ ВЕРДИКТ У КАПОТА: БРАТЬ / НЕ БРАТЬ / ТОРГОВАТЬСЯ

Коротко, как свой.
"""
            try:
                resp = await client.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=[{"role": "user", "content": [{"type": "text", "text": prompt}] + imgs}],
                    max_tokens=1000
                )
                await m.answer(f"📋 ИТОГ У КАПОТА:\n\n{resp.choices[0].message.content}", reply_markup=main_kb())
                user_data[uid]["stage"] = "idle"
            except Exception as e:
                await m.answer(f"Ошибка итогового отчета: {e}")
        
    except Exception as e:
        await m.answer(f"Ошибка обработки видео: {e}")

@dp.message(F.text.contains("Оценить"))
async def old_report(m: types.Message):
    # совместимость со старым ботом
    uid = m.from_user.id
    data = user_data.get(uid, {})
    photos = data.get("photos_remote", []) or data.get("photos_hood", [])
    if not photos:
        await m.answer("Кинь фото сначала!", reply_markup=main_kb())
        return
    # делегируем в hood итоговый
    await m.answer("Делаю отчет по старому формату...")
    # вызовем логику hood
    user_data[uid]["stage"] = "hood"
    user_data[uid]["hood_step"] = len(HOOD_STEPS)
    # фейк вызов видео хендлера для итога
    await handle_video(m)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())