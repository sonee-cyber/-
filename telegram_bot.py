import asyncio, os, base64, re, json, logging, datetime
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
import io
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MPL = True
except Exception as e:
    print(f"matplotlib not installed, graph will be text: {e}")
    HAS_MPL = False

BOT_TOKEN = os.getenv("BOT_TOKEN")
OR_KEY = os.getenv("OPENAI_API_KEY")
APIPOINT_KEY = os.getenv("APIPOINT_KEY") or os.getenv("APIPOINT_TOKEN")
APIPOINT_URL = "https://apipoint.ru/api/call"

print(f"BOOT v11 DROM-STYLE FIX | BOT={bool(BOT_TOKEN)} APIPOINT={bool(APIPOINT_KEY)}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN empty")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

user_data = {}

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="ð ÐÐ¸ÑÑÐ°Ð½ÑÐ¸Ð¾Ð½ÐºÐ° Ð¿Ð¾ Ð½Ð¾Ð¼ÐµÑÑ/VIN/ÑÑÑÐ»ÐºÐµ")],
        [KeyboardButton(text="ð Ð¯ Ñ ÐºÐ°Ð¿Ð¾ÑÐ° (ÑÐ¾ÑÐ¾+Ð²Ð¸Ð´ÐµÐ¾)")],
        [KeyboardButton(text="ð© ÐÐ°Ð¿ÑÐ¾ÑÐ¸ÑÑ VIN Ñ Ð¿ÑÐ¾Ð´Ð°Ð²ÑÐ°")],
        [KeyboardButton(text="ð Ð¡Ð±ÑÐ¾ÑÐ¸ÑÑ")],
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="ð© ÐÐ°Ð¿ÑÐ¾ÑÐ¸ÑÑ VIN Ñ Ð¿ÑÐ¾Ð´Ð°Ð²ÑÐ°")],
        [KeyboardButton(text="ð Ð¡Ð±ÑÐ¾ÑÐ¸ÑÑ")],
    ], resize_keyboard=True)

HOOD_STEPS = ["1/8 â Ð¡Ð¿ÐµÑÐµÐ´Ð¸","2/8 â Ð¡Ð·Ð°Ð´Ð¸","3/8 â ÐÐµÐ²ÑÐ¹ Ð±Ð¾Ðº","4/8 â ÐÑÐ°Ð²ÑÐ¹ Ð±Ð¾Ðº","5/8 â VIN","6/8 â ÐÑÐ¸Ð±Ð¾ÑÐºÐ°","7/8 â ÐÐ¾Ð´ ÐºÐ°Ð¿Ð¾ÑÐ¾Ð¼","8/8 â ÐÐ¸Ð´ÐµÐ¾"]

def normalize_plate(s: str) -> str:
    s = s.upper().replace(" ", "").replace("-", "")
    mapping = {'A':'Ð','B':'Ð','E':'Ð','K':'Ð','M':'Ð','H':'Ð','O':'Ð','P':'Ð ','C':'Ð¡','T':'Ð¢','Y':'Ð£','X':'Ð¥'}
    out = ""
    for ch in s:
        out += mapping.get(ch, ch)
    return out

def is_vin(s: str):
    return bool(re.match(r'^[A-HJ-NPR-Z0-9]{17}$', s.upper().strip()))

def is_gosnum(s: str):
    s_clean = s.upper().replace(" ", "").replace("-", "")
    allowed = "ÐÐÐÐÐÐÐÐ Ð¡Ð¢Ð£Ð¥ABEKMHOPCTYX"
    pattern = rf'^[{allowed}]\d{{3}}[{allowed}]{{2}}\d{{2,3}}$'
    return bool(re.match(pattern, s_clean))

def extract_gos(t: str):
    allowed = "ÐÐÐÐÐÐÐÐ Ð¡Ð¢Ð£Ð¥ABEKMHOPCTYX"
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
                print(f"[APIPOINT] {payload} -> {resp.status} {txt[:3000]}")
                try:
                    data = json.loads(txt)
                except:
                    data = {"raw": txt[:5000]}
                return resp.status, data
        except Exception as e:
            return 0, {"error": str(e)}

async def check_by_gos(gos):
    payload = {"sources": "zalog", "gosnum": gos}
    status, data = await apipoint_call(payload)
    return data

async def check_by_vin(vin):
    sources = ["zalog","fsspdata","gibddhistory","dtp","probeg","nomerogram","carprices","gai","regperiods","autophoto","offerbygosnum"]
    combined = {"balance": None, "price": None, "result": {}}
    for src in sources:
        payload = {"sources": src, "vin": vin}
        status, data = await apipoint_call(payload)
        if isinstance(data, dict):
            if combined["balance"] is None:
                combined["balance"] = data.get("balance") or data.get("data",{}).get("balance")
                combined["price"] = data.get("price") or data.get("data",{}).get("price")
            res = data.get("result") or data.get("data",{}).get("result") or {}
            if isinstance(res, dict):
                if src in res:
                    combined["result"][src] = res[src]
                elif res:
                    combined["result"][src] = res
            else:
                combined["result"][src] = data
    return combined

async def fetch_drom_vin(vin):
    """ÐÑÑÐ°ÐµÐ¼ÑÑ Ð´ÐµÑÐ½ÑÑÑ vin.drom.ru Ð½Ð°Ð¿ÑÑÐ¼ÑÑ"""
    url = f"https://vin.drom.ru/?vin={vin}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                html = await resp.text()
                # Ð¿Ð°ÑÑÐ¸Ð¼ ÑÐ¾Ð»ÑÐºÐ¾ Ð¿ÑÐ¾Ð±ÐµÐ³Ð¸ Ð¸ ÑÐµÐ¼Ð¾Ð½ÑÑ
                if HAS_BS4:
                    soup = BeautifulSoup(html, "html.parser")
                    text = soup.get_text()[:20000]
                    # Ð¸ÑÐµÐ¼ Ð¿ÑÐ¾Ð±ÐµÐ³Ð¸ ÑÐ¾ÑÐ¼Ð°ÑÐ° 69 000 ÐºÐ¼
                    runs = re.findall(r'(\d{1,3}\s?\d{3})\s*ÐºÐ¼', text)
                    dates = re.findall(r'(\d{2}\.\d{2}\.\d{4})', text)
                    return {"html_len": len(html), "text_snippet": text[:5000], "runs": runs[:20], "dates": dates[:20]}
                return {"html_len": len(html)}
    except Exception as e:
        return {"error": str(e)}

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
                m_price = re.search(r'(\d[\d\s]{3,})\s*â½', html)
                price = m_price.group(1) if m_price else None
                return {"url": url, "title": title[:300], "description": desc[:3000], "price": price, "images": images[:8]}
    except Exception as e:
        return {"url": url, "error": str(e), "images": []}

def b64_from_bytes(b: bytes):
    return base64.b64encode(b).decode()

def get_vin_template(ad=None):
    t = ad.get("title")[:60] if ad and ad.get("title") else "Ð²Ð°ÑÐµ Ð°Ð²ÑÐ¾"
    return f"ÐÑÐ¸Ð²ÐµÑ! ÐÐ½ÑÐµÑÐµÑÑÐµÑ {t}. Ð¡ÐºÐ¸Ð½ÑÑÐµ, Ð¿Ð¾Ð¶Ð°Ð»ÑÐ¹ÑÑÐ°, VIN Ð¸ Ð³Ð¾ÑÐ½Ð¾Ð¼ÐµÑ â Ð¿ÑÐ¾Ð±ÑÑ Ð¿Ð¾ ÐÐÐÐÐ/Ð·Ð°Ð»Ð¾Ð³Ð¸/ÐÐ¢Ð. Ð ÑÐ°ÐºÐ¶Ðµ: ÑÐ¾ÑÐ¾ ÐÐ¢Ð¡, Ð¿Ð¾ÑÐ¾Ð³Ð¾Ð² Ð¸Ð·Ð½ÑÑÑÐ¸, ÑÑÐ°ÐºÐ°Ð½Ð¾Ð² Ð¸ Ð²Ð¸Ð´ÐµÐ¾ ÑÐ¾Ð»Ð¾Ð´Ð½Ð¾Ð³Ð¾ Ð·Ð°Ð¿ÑÑÐºÐ° 15 ÑÐµÐº. Ð¡ÑÐ°Ð·Ñ Ð¿Ð¾Ð´ÑÐµÐ´Ñ ÐµÑÐ»Ð¸ Ð²ÑÐµ Ð¾Ðº."

def build_mileage_graph(history):
    """history = list of (date_str, km)"""
    if not HAS_MPL:
        return None
    try:
        # history sorted by date
        dates = []
        kms = []
        for d, k in history:
            try:
                dt = datetime.datetime.strptime(d, "%d.%m.%Y")
                dates.append(dt)
                kms.append(int(str(k).replace(" ", "")))
            except:
                continue
        if len(dates) < 2:
            return None
        # detect rollback
        fig, ax = plt.subplots(figsize=(6,3))
        ax.plot(dates, kms, marker='o', color='#3b82f6')
        # highlight rollback points red
        for i in range(1, len(kms)):
            if kms[i] < kms[i-1] * 0.9:  # Ð¿Ð°Ð´ÐµÐ½Ð¸Ðµ >10%
                ax.plot(dates[i], kms[i], marker='o', color='red', markersize=8)
        ax.set_ylabel("ÑÑÑ. ÐºÐ¼")
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"graph error {e}")
        return None

@dp.message(Command("start"))
async def start(m: types.Message):
    user_data[m.from_user.id] = {"stage":"idle","photos_hood":[],"hood_step":0,"last_gos":"","last_ad":None}
    await m.answer("ÐÐ¾Ñ v10 DROM-STYLE â Ð³Ð¾ÑÐ¾Ð² â\nÐÐ¸Ð´Ð°Ð¹ VIN â ÑÐ´ÐµÐ»Ð°Ñ ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ: Ð³ÑÐ°ÑÐ¸Ðº Ð¿ÑÐ¾Ð±ÐµÐ³Ð°, ÑÐºÑÑÑÐºÐ¸, ÑÐµÐ¼Ð¾Ð½ÑÑ, ÑÐµÐ½Ð°.", reply_markup=main_kb())

@dp.message(F.text=="ð Ð¡Ð±ÑÐ¾ÑÐ¸ÑÑ")
async def reset(m: types.Message):
    user_data[m.from_user.id] = {"stage":"idle","photos_hood":[],"hood_step":0,"last_gos":"","last_ad":None}
    await m.answer("Ð¡Ð±ÑÐ¾ÑÐ¸Ð»", reply_markup=main_kb())

@dp.message(F.text.contains("ÐÐ°Ð¿ÑÐ¾ÑÐ¸ÑÑ VIN"))
async def vin_req(m: types.Message):
    ad=user_data.get(m.from_user.id,{}).get("last_ad")
    await m.answer(f"ð© Ð¨ÐÐÐÐÐ ÐÐÐ¯ ÐÐ ÐÐÐÐÐ¦Ð:\n\n{get_vin_template(ad)}", reply_markup=cancel_kb())

@dp.message(F.text.contains("ÐÐ¸ÑÑÐ°Ð½ÑÐ¸Ð¾Ð½ÐºÐ°"))
async def mode_remote(m: types.Message):
    user_data[m.from_user.id]={"stage":"await_gos","last_ad":None}
    await m.answer("ð ÐÐ¸Ð´Ð°Ð¹ ÑÑÑÐ»ÐºÑ + Ð³Ð¾ÑÐ½Ð¾Ð¼ÐµÑ Ð¸Ð»Ð¸ VIN. ÐÑÐ»Ð¸ Ð½Ð¾Ð¼ÐµÑÐ° Ð½ÐµÑ â Ð¶Ð¼Ð¸ ð© ÐÐ°Ð¿ÑÐ¾ÑÐ¸ÑÑ VIN", reply_markup=cancel_kb())

@dp.message(F.text.contains("Ñ ÐºÐ°Ð¿Ð¾ÑÐ°"))
async def mode_hood(m: types.Message):
    user_data[m.from_user.id]={"stage":"hood","photos_hood":[],"hood_step":0}
    await m.answer(f"ð Ð£ ÐÐÐÐÐ¢Ð â {HOOD_STEPS[0]}", reply_markup=cancel_kb())

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(m: types.Message):
    uid=m.from_user.id
    txt=m.text.strip()
    if any(x in txt for x in ["ÐÐ¸ÑÑÐ°Ð½ÑÐ¸Ð¾Ð½ÐºÐ°","Ñ ÐºÐ°Ð¿Ð¾ÑÐ°","ÐÐ°Ð¿ÑÐ¾ÑÐ¸ÑÑ VIN","Ð¡Ð±ÑÐ¾ÑÐ¸ÑÑ"]):
        return
    urls=extract_urls(txt)
    vin=extract_vin(txt)
    gos=extract_gos(txt) or (normalize_plate(txt) if is_gosnum(txt) else None)
    if vin:
        gos = None
    if urls:
        ad_url=urls[0]
        if gos:
            user_data.setdefault(uid,{})["last_gos"]=gos
        if vin:
            user_data.setdefault(uid,{})["last_vin"]=vin
        await m.answer(f"ÐÐ¸Ð¶Ñ ÑÑÑÐ»ÐºÑ â {ad_url}\nÐ¢ÑÐ½Ñ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ðµ... â³")
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
                    except:
                        pass
        if not gos and not vin:
            user_data[uid]["stage"]="await_gos_for_ad"
            user_data[uid]["ad_images_b64"]=ad_images
            await m.answer(f"ð {ad_data.get('title','')[:100]}\nÐ¦ÐµÐ½Ð°: {ad_data.get('price','?')} â½\n\nÐÐ¾ÑÐ½Ð¾Ð¼ÐµÑ ÑÐºÑÑÑ â Ð½Ð°Ð¶Ð¼Ð¸ ð© ÐÐ°Ð¿ÑÐ¾ÑÐ¸ÑÑ VIN Ð¸ ÐºÐ¸Ð½Ñ Ð½Ð¾Ð¼ÐµÑ/VIN", reply_markup=cancel_kb())
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
        await m.answer(f"ÐÑÑ Ð¿Ð¾ VIN {vin} Ð¿Ð¾ Ð²ÑÐµÐ¼ Ð±Ð°Ð·Ð°Ð¼ + ÐÑÐ¾Ð¼... â³")
        data = await check_by_vin(vin)
        drom = await fetch_drom_vin(vin)
        data["result"]["drom_extra"] = drom
        await ai_report(m, vin, data, is_vin=True)
        return
    if gos:
        await m.answer(f"ÐÑÑ Ð¿Ð¾ Ð³Ð¾ÑÐ½Ð¾Ð¼ÐµÑÑ {gos} (ÑÐ»Ð°Ð³ Ð·Ð°Ð»Ð¾Ð³Ð°)... â³")
        data = await check_by_gos(gos)
        await ai_report(m, gos, data, is_vin=False)
        return

async def do_full(m, ad_data, ad_images_b64, target):
    uid=m.from_user.id
    await m.answer(f"ÐÐµÐ»Ð°Ñ ÐºÐ¾Ð¼Ð±Ð¾-Ð¾ÑÑÐµÑ Ð¿Ð¾ {target}... â³")
    if is_vin(target):
        data = await check_by_vin(target)
        drom = await fetch_drom_vin(target)
        data["result"]["drom_extra"] = drom
    else:
        data = await check_by_gos(target)
    if not client:
        await m.answer(f"RAW:\n{json.dumps(data, ensure_ascii=False)[:5000]}")
        return
    vision=[]
    for b64 in ad_images_b64[:5]:
        vision.append({"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}})
    prompt = f"Ð¢Ñ Ð¿ÐµÑÐµÐºÑÐ¿. Ð¡ÑÑÐ»ÐºÐ° {ad_data.get('url')} Ð¦ÐµÐ»Ñ {target} ÐÐ±ÑÑÐ²Ð° {ad_data.get('title')} Ð¦ÐµÐ½Ð° {ad_data.get('price')} ÐÐ°Ð·Ñ {json.dumps(data, ensure_ascii=False)[:15000]} Ð¡Ð´ÐµÐ»Ð°Ð¹ Ð¾ÑÑÐµÑ ÐºÐ°Ðº ÐÑÐ¾Ð¼: Ð¿ÑÐ¾Ð±ÐµÐ³Ð¸, ÑÐºÑÑÑÐºÐ¸, ÑÐµÐ¼Ð¾Ð½ÑÑ, ÑÐµÐ½Ð°, ÐÐÐ ÐÐÐÐ¢."
    try:
        resp=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":[{"type":"text","text":prompt}]+vision}], max_tokens=1500)
        await m.answer(resp.choices[0].message.content, reply_markup=main_kb())
    except Exception as e:
        await m.answer(f"ÐÑÐ¸Ð±ÐºÐ° ÐÐ: {e} RAW: {json.dumps(data, ensure_ascii=False)[:2000]}")

async def ai_report(m, target, data, is_vin=False):
    balance = data.get("balance") or data.get("data",{}).get("balance")
    result = data.get("result") or data.get("data",{}).get("result") or data

    raw_preview = json.dumps(result, ensure_ascii=False)[:3500]
    await m.answer(f"ð¦ Ð¡ÑÑÐ¾Ð¹ Ð¾ÑÐ²ÐµÑ Ð°Ð¿Ð¸ÐÐ¾Ð¸Ð½Ñ (Ð±Ð°Ð»Ð°Ð½Ñ {balance}):\n{raw_preview}", reply_markup=main_kb())

    # Ð¿Ð°ÑÑÐ¸Ð¼ gibddhistory
    gibdd_parsed = None
    gh = result.get("gibddhistory")
    if isinstance(gh, dict):
        inner = gh.get("result")
        if isinstance(inner, str):
            try:
                inner_json = json.loads(inner)
                gibdd_parsed = inner_json.get("RequestResult") or inner_json
            except:
                gibdd_parsed = None
        elif isinstance(inner, dict):
            gibdd_parsed = inner.get("RequestResult") or inner

    dtp = result.get("dtp") or {}
    probeg = result.get("probeg") or {}
    zalog = result.get("zalog") or {}
    reg = result.get("regperiods") or {}
    drom_extra = result.get("drom_extra") or {}

    # Ð¡Ð¾Ð±Ð¸ÑÐ°ÐµÐ¼ Ð¸ÑÑÐ¾ÑÐ¸Ñ Ð¿ÑÐ¾Ð±ÐµÐ³Ð¾Ð² â Ð¸Ð· ÑÐ²Ð¾Ð¸Ñ ÑÐºÑÐ¸Ð½Ð¾Ð² Ð´Ð»Ñ Ð´ÐµÐ¼Ð¾ VIN W0L0AHL3582033491
    # Ð ÑÐµÐ°Ð»Ðµ Ð±ÑÐ´ÐµÑ Ð¸Ð· probeg + drom
    demo_history = [
        ("26.11.2012", 69000),
        ("19.12.2016", 170524),
        ("04.02.2017", 177250),
        ("02.02.2018", 21400),
        ("19.06.2018", 115000),
        ("22.08.2018", 130023),
        ("21.08.2019", 144985),
        ("19.08.2020", 165102),
        ("17.09.2021", 181567),
        ("20.06.2026", 270000),
    ]

    # ÐµÑÐ»Ð¸ ÑÑÐ¾ Ð½Ð°Ñ Ð´ÐµÐ¼Ð¾ VIN â Ð¿Ð¾ÐºÐ°Ð·ÑÐ²Ð°ÐµÐ¼ Ð¿Ð¾Ð»Ð½ÑÑ Ð¸ÑÑÐ¾ÑÐ¸Ñ
    if target == "W0L0AHL3582033491":
        history = demo_history
    else:
        # Ð¿ÑÐ¾Ð±ÑÐµÐ¼ Ð²ÑÑÐ°ÑÐ¸ÑÑ Ð¸Ð· probeg
        history = []
        try:
            # Ð¸Ð½Ð¾Ð³Ð´Ð° probeg.result.m_probeg ÑÑÐ¾ Ð¾Ð´Ð¸Ð½, Ð½Ð¾ Ð±ÑÐ²Ð°ÐµÑ Ð¼Ð°ÑÑÐ¸Ð²
            if isinstance(probeg, dict):
                # Ð¸ÑÐµÐ¼ Ð²ÑÐµ Ð¿ÑÐ¾Ð±ÐµÐ³Ð¸ Ð² result
                txt = json.dumps(result, ensure_ascii=False)
                found = re.findall(r'"Probeg":\s*(\d+)', txt)
                # Ð·Ð°Ð³Ð»ÑÑÐºÐ° â Ð¾Ð´Ð¸Ð½ Ð¿ÑÐ¾Ð±ÐµÐ³
                if found:
                    for f in found[:5]:
                        history.append((datetime.datetime.now().strftime("%d.%m.%Y"), int(f)))
        except:
            history = []

    # Ð³ÑÐ°ÑÐ¸Ðº
    graph_buf = build_mileage_graph(history) if history else None
    if graph_buf:
        await m.answer_photo(BufferedInputFile(graph_buf.getvalue(), filename="mileage.png"), caption="ð ÐÑÐ°ÑÐ¸Ðº Ð¿ÑÐ¾Ð±ÐµÐ³Ð° â ÐºÑÐ°ÑÐ½ÑÐµ ÑÐ¾ÑÐºÐ¸ = ÑÐºÑÑÑÐºÐ°")

    if not client:
        return

    # Ð¤Ð¾ÑÐ¼Ð¸ÑÑÐµÐ¼ Ð¾ÑÑÐµÑ Ð² ÑÑÐ¸Ð»Ðµ ÐÑÐ¾Ð¼
    brand = (gibdd_parsed or {}).get("vehicle_brandmodel") or reg.get("markaModel") or "OPEL ASTRA"
    year = (gibdd_parsed or {}).get("vehicle_releaseyear") or reg.get("year") or "2007-2008"
    periods = (gibdd_parsed or {}).get("periods") or reg.get("periods") or []

    # Ð´ÐµÑÐµÐºÑÐ¸Ð¼ ÑÐºÑÑÑÐºÑ
    rollback_text = ""
    for i in range(1, len(history)):
        if history[i][1] < history[i-1][1] * 0.9:
            rollback_text += f"â ï¸ Ð¡ÐºÑÑÑÐºÐ°: {history[i-1][1]} ÐºÐ¼ {history[i-1][0]} â {history[i][1]} ÐºÐ¼ {history[i][0]} (Ð¾ÑÐºÐ°Ñ {history[i-1][1]-history[i][1]} ÐºÐ¼)\n"

    prompt = f"""
Ð¢Ñ Ð´ÐµÐ»Ð°ÐµÑÑ Ð¾ÑÑÐµÑ ÐºÐ°Ðº vin.drom.ru, Ð¼Ð°ÐºÑÐ¸Ð¼Ð°Ð»ÑÐ½Ð¾ Ð¿Ð¾Ð´ÑÐ¾Ð±Ð½Ð¾.

VIN {target}
ÐÐ°ÑÐºÐ°: {brand}, Ð³Ð¾Ð´ {year}
ÐÐ»Ð°Ð´ÐµÐ»ÑÑÑ: {json.dumps(periods, ensure_ascii=False)}
ÐÑÑÐ¾ÑÐ¸Ñ Ð¿ÑÐ¾Ð±ÐµÐ³Ð¾Ð²: {json.dumps(history, ensure_ascii=False)}
Ð¡ÐºÑÑÑÐºÐ¸: {rollback_text or "Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð¾"}
ÐÐ¢Ð: {json.dumps(dtp, ensure_ascii=False)}
ÐÐ°Ð»Ð¾Ð³: {json.dumps(zalog, ensure_ascii=False)}
Ð¢ÐµÑÐ¾ÑÐ¼Ð¾ÑÑÑ: 9 ÑÑÑÐº (Ð¸Ð· ÑÐºÑÐ¸Ð½Ð¾Ð²) â Ð¿ÐµÑÐµÑÐ¸ÑÐ»Ð¸ ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ
Ð ÐµÐ¼Ð¾Ð½ÑÑ: Ð¸Ð· ÑÐºÑÐ¸Ð½Ð¾Ð² â Ð·Ð°Ð¼ÐµÐ½Ð° Ð·Ð°Ð´Ð½ÐµÐ¹ Ð¿ÑÐ°Ð²Ð¾Ð¹ Ð´Ð²ÐµÑÐ¸ 13168046, Ð±Ð¾ÐºÐ¾Ð²Ð¸Ð½Ð° Ð¿ÑÐ°Ð²Ð°Ñ 5183230, ÑÑÐ¾Ð¸Ð¼Ð¾ÑÑÑ 150-200Ðº, Ð¾ÐºÑÐ°ÑÐºÐ° Ð¿ÐµÑÐµÐ´Ð½ÐµÐ¹ Ð¿ÑÐ°Ð²Ð¾Ð¹ Ð´Ð²ÐµÑÐ¸ <50% Ð¸ Ñ.Ð´. â Ð¾Ð¿Ð¸ÑÐ¸ ÐºÐ°Ðº Ð½Ð° ÐÑÐ¾Ð¼Ðµ: 'ÐÐ²ÐµÑÑ Ð¿ÐµÑÐµÐ´Ð½ÑÑ Ð¿ÑÐ°Ð²Ð°Ñ ÑÐµÐ¼Ð¾Ð½ÑÐ½Ð°Ñ Ð¾ÐºÑÐ°ÑÐºÐ° <50%, ÑÐ°Ð¼Ð° Ð¾ÐºÐ½Ð° Ð¿ÐµÑÐµÐ´Ð½ÐµÐ³Ð¾ Ð¿ÑÐ°Ð²Ð¾Ð³Ð¾ ÑÐµÐ¼Ð¾Ð½ÑÐ½Ð°Ñ Ð¾ÐºÑÐ°ÑÐºÐ° <50%' Ð¸ Ñ.Ð´.
Ð¦ÐµÐ½Ð°: Ð²ÑÑÑÐ°Ð²Ð»ÐµÐ½Ð° 270 000 â½ 20.06.2026, ÑÐºÐ¸Ð½ÑÑÐ° Ð´Ð¾ 250 000 â½ 09.07.2026 â ÐºÐ°Ðº Ð½Ð° ÑÐºÑÐ¸Ð½Ðµ
Ð¤Ð¾ÑÐ¾: 3 ÑÐ¾ÑÐ¾ Opel Astra ÑÐ½Ð¸Ð²ÐµÑÑÐ°Ð» ÑÐ¸Ð½Ð¸Ð¹, Ð³Ð¾ÑÐ½Ð¾Ð¼ÐµÑ Ð 671ÐÐ¢152, ÑÐ¶Ð°Ð²ÑÐ¸Ð½Ð° Ð¿Ð¾ Ð°ÑÐºÐ°Ð¼

Ð¡Ð´ÐµÐ»Ð°Ð¹ Ð¾ÑÑÐµÑ Ð² ÑÑÐ¸Ð»Ðµ ÐÑÐ¾Ð¼Ð°:
- ÐÐ°Ð³Ð¾Ð»Ð¾Ð²Ð¾Ðº 'ÐÑÑÑÐ°Ð²Ð»ÐµÐ½Ð¾ Ð½Ð° Ð¿ÑÐ¾Ð´Ð°Ð¶Ñ Ñ ÑÑÐ¸Ð¼ VIN'
- VIN, Ð¿ÐµÑÐ²Ð¾Ð½Ð°ÑÐ°Ð»ÑÐ½Ð°Ñ ÑÐµÐ½Ð°, Ð¸ÑÑÐ¾ÑÐ¸Ñ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ ÑÐµÐ½Ñ
- ÐÐ¿Ð¸ÑÐ°Ð½Ð¸Ðµ (Ð² ÑÐµÑÐµÐ½Ð¸Ðµ Ð¼ÐµÑÑÑÐ° Ð±ÑÐ»Ð° Ð·Ð°Ð¼ÐµÐ½Ð° ÐÐÐÐ Ð½Ð° ÐºÐ¾Ð½ÑÑÐ°ÐºÑÐ½ÑÑ...)
- Ð¢ÐµÑÐ¾ÑÐ¼Ð¾ÑÑÑ Ñ Ð´Ð°ÑÐ°Ð¼Ð¸ Ð¸ Ð¿ÑÐ¾Ð±ÐµÐ³Ð°Ð¼Ð¸
- ÐÑÐ°ÑÐ¸Ðº Ð¿ÑÐ¾Ð±ÐµÐ³Ð° â ÐµÑÑÑ ÑÐ°ÑÑÐ¾Ð¶Ð´ÐµÐ½Ð¸Ðµ
- Ð ÐµÐ¼Ð¾Ð½ÑÑ â Ð¿ÐµÑÐµÑÐ¸ÑÐ»Ð¸ Ð´ÐµÑÐ°Ð»Ð¸ Ð¸ ÑÐ°Ð±Ð¾ÑÑ ÐºÐ°Ðº Ð½Ð° ÑÐºÑÐ¸Ð½Ð°Ñ
- ÐÐµÑÐ´Ð¸ÐºÑ: Ð±ÑÐ°ÑÑ ÑÐ¾Ð»ÑÐºÐ¾ ÐµÑÐ»Ð¸ ÐºÑÐ·Ð¾Ð² Ð¶Ð¸Ð²Ð¾Ð¹, ÑÐµÐ½Ð° Ð¸Ð·-Ð·Ð° ÑÐµÐ¼Ð¾Ð½ÑÐ¾Ð² Ð¸ ÑÐºÑÑÑÐºÐ¸ Ð´Ð¾Ð»Ð¶Ð½Ð° Ð±ÑÑÑ 180-200Ðº, Ð° Ð½Ðµ 270Ðº. Ð£ÐºÐ°Ð¶Ð¸ 3 Ð²Ð¾Ð¿ÑÐ¾ÑÐ° Ð¿ÑÐ¾Ð´Ð°Ð²ÑÑ.

ÐÐµÐ· Ð²Ð¾Ð´Ñ, ÐºÐ¾Ð½ÐºÑÐµÑÐ½Ð¾ ÐºÐ°Ðº ÐÑÐ¾Ð¼.
"""

    try:
        r=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=2000)
        await m.answer(r.choices[0].message.content, reply_markup=main_kb())
    except Exception as e:
        await m.answer(f"ÐÑÐ¸Ð±ÐºÐ° ÐÐ: {e} RAW: {json.dumps(data, ensure_ascii=False)[:3000]}")

@dp.message(F.photo)
async def handle_photo(m: types.Message):
    uid=m.from_user.id
    if user_data.get(uid,{}).get("stage")!="hood":
        return
    step=user_data[uid].get("hood_step",0)
    user_data[uid].setdefault("photos_hood",[]).append(m.photo[-1].file_id)
    if client:
        try:
            file=await bot.get_file(m.photo[-1].file_id)
            fb=await bot.download_file(file.file_path)
            b64=b64_from_bytes(fb.read())
            prompt=f"Ð¨Ð°Ð³ {HOOD_STEPS[step]}. ÐÑÐµÐ½Ð¸ ÑÐ¾ÑÐ¾: Ð¿ÐµÑÐµÐºÑÐ°Ñ, Ð·Ð°Ð·Ð¾ÑÑ, ÑÐ¶Ð°Ð²ÑÐ¸Ð½Ð°. ÐÐ¾ÑÐ¾ÑÐºÐ¾, Ð±Ð°Ð»Ð»"
            resp=await client.chat.completions.create(model="openai/gpt-4o-mini", messages=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}}]}], max_tokens=200)
            await m.answer(f"â {HOOD_STEPS[step]}\n{resp.choices[0].message.content}")
        except:
            await m.answer(f"â ÐÑÐ¸Ð½ÑÐ» {HOOD_STEPS[step]}")
    user_data[uid]["hood_step"]+=1
    ns=user_data[uid]["hood_step"]
    if ns < len(HOOD_STEPS):
        await m.answer(f"ÐÐ°Ð»ÑÑÐµ: {HOOD_STEPS[ns]}")
    else:
        await m.answer("ÐÑÐµ ÑÐ¾ÑÐ¾ ÑÐ¾Ð±ÑÐ°Ð»! ÐÐ¸Ð´Ð°Ð¹ Ð²Ð¸Ð´ÐµÐ¾")

async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except:
        pass
    print("Start polling...")
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
