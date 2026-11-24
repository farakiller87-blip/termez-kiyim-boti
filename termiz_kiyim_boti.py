
# TERMIZ KIYIM BOTI - login + parol bilan kiriladi
# requirements: python-telegram-bot==22.2 + Flask
# FUNKSIYALAR: login/parol, ro'yxatdan o'tish, do'kon, mijoz, kuryer, admin,
# qadoqlash yo'riqnomasi, tayyor rasm, lokatsiya, kuryer yo'lga chiqdi,
# yetkazdim, 1-5 reyting (do'kon + kuryer, admin panelida hammaniki)
import os, json, time, hashlib
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

app = Flask(__name__)
@app.route('/')
def home(): return "Termiz Kiyim Boti ishlayapti!"
@app.route('/ping')
def ping(): return "pong", 200
@app.route('/health')
def health():
    return {"status": "ok", "bot": "Termiz Kiyim Boti", "users": len(DB.get("users", {})), "shops": len(DB.get("shops", {})), "orders": len(DB.get("orders", {}))}, 200
@app.route('/uptime')
def uptime(): return "OK - bot uxlamayapti", 200
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), use_reloader=False)
Thread(target=run_flask, daemon=True).start()
# --- UXLAMASLIK: o'z-o'zini uyg'otish (tashqi ping bilan birga ishlaydi) ---
# Render dagi sayting manzilini Env ga yoz: KEEP_ALIVE_URL=https://termiz-kiyim-boti.onrender.com
# Bu thread har 4 daqiqada o'sha manzilga o'zi ping yuboradi.
def _keep_alive_loop():
    import urllib.request
    url = (os.environ.get("KEEP_ALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").strip()
    if not url: return
    if not url.startswith("http"): url = "https://" + url
    url = url.rstrip("/") + "/ping"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=15) as r: r.read(10)
        except Exception: pass
        time.sleep(240)
Thread(target=_keep_alive_loop, daemon=True).start()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPER_ADMIN = 6738827993  # <-- O'Z ID INGNI YOZ
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")  # <-- Render da o'zgartir! Admin paroli
COMMISSION_PER_ORDER = 2000
# --- KURYER XIZMAT HAQI: shahar ichi / tashqaris / uzoq ---
DELIVERY_CITY = 15000      # 🏙️ Shahar ichi (Termiz shahar)
DELIVERY_OUTSIDE = 30000   # 🏡 Shahar tashqaris (Termiz tumani, yaqin qishloqlar)
DELIVERY_FAR = 50000       # 🛣️ Uzoq tumanlar
DELIVERY_ZONES = {"1": ("🏙️ Shahar ichi", DELIVERY_CITY), "2": ("🏡 Shahar tashqaris", DELIVERY_OUTSIDE), "3": ("🛣️ Uzoq tuman", DELIVERY_FAR)}
# --- CLICK / PAYME: pul ADMINGA emas, DO'KONCHIGA tushadi ---
PAYMENT_NOTE = "Termiz Kiyim Boti"
def shop_card(shop, method):
    if method == "click": return shop.get("click_card"), shop.get("click_name")
    return shop.get("payme_card"), shop.get("payme_name")
def pay_kb(oid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ To'lovni tasdiqlash", callback_data=f"confirm_pay_{oid}")],[InlineKeyboardButton("❌ To'lov kelmadi", callback_data=f"reject_pay_{oid}")]])
DB_FILE = "db.json"
CATEGORIES = ["👨 Erkaklar", "👩 Ayollar", "🧒 Bolalar", "👟 Oyoq kiyim", "👜 Sumka / Aksessuar"]

def load():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {"users": {}, "shops": {}, "orders": {}, "counter": 1}
def save():
    try: _sync_archive_all()
    except Exception: pass
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(DB, f, ensure_ascii=False, indent=2)
    # --- ZAXIRA: har bir saqlashda nusxa olinadi, hech narsa yo'qolmaydi ---
    try:
        with open("db_backup.json", "w", encoding="utf-8") as f: json.dump(DB, f, ensure_ascii=False, indent=2)
        import datetime as _dt
        with open("db_backup_last.txt", "w", encoding="utf-8") as f: f.write(_dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception: pass
DB = load()
DB.setdefault("archive", {})
# --- DOIMIY ARXIV: foydalanuvchi botni o'chirsa ham ma'lumoti o'chmaydi ---
# Har bir save() da barcha foydalanuvchining surati arxivga tushadi.
# Arxiv hech qachon o'chirilmaydi - faqat admin yangi parol/login bera oladi.
def _sync_archive_all():
    DB.setdefault("archive", {})
    for uid, u in list(DB.get("users", {}).items()):
        shops = []
        for slug, s in DB.get("shops", {}).items():
            if str(s.get("admin")) == str(uid):
                shops.append({"slug": slug, "name": s.get("name"), "phone": s.get("phone"), "address": s.get("address"), "status": s.get("status"), "guvohnoma_num": s.get("guvohnoma_num"), "guvohnoma_photo": s.get("guvohnoma_photo"), "click_card": s.get("click_card"), "payme_card": s.get("payme_card"), "debt": s.get("debt", 0)})
        ocnt = sum(1 for o in DB.get("orders", {}).values() if str(o.get("user_id")) == str(uid))
        DB["archive"][str(uid)] = {"telegram_id": str(uid), "name": u.get("name"), "login": u.get("login"), "phone": u.get("phone"), "role": u.get("role"), "locked_role": u.get("locked_role"), "password_hash": u.get("password_hash"), "courier_registered": u.get("courier_registered"), "courier_status": u.get("courier_status"), "passport_num": u.get("passport_num"), "passport_photo": u.get("passport_photo"), "delivered": u.get("delivered", 0), "earned_delivery": u.get("earned_delivery", 0), "balance": u.get("balance", 0), "ratings": u.get("ratings", []), "orders_count": ocnt, "shops": shops, "updated_at": int(time.time())}
def _arch(uid):
    return DB.get("archive", {}).get(str(uid), {})
def _arch_text(a):
    shops = "\n".join([f"  🏪 {s.get('name')} ({s.get('status','?')}) — 📞 {s.get('phone','—')} — 💳 Click: {s.get('click_card') or '—'} / Payme: {s.get('payme_card') or '—'} — 📄 Guvohnoma: {s.get('guvohnoma_num') or '—'}" for s in a.get("shops", [])]) or "  — do'koni yo'q"
    return (f"🗄️ ARXIV — {a.get('name','?')}\n\n👤 Ism: {a.get('name','?')}\n🆔 Telegram ID: {a.get('telegram_id')}\n🔑 Login: {a.get('login') or '—'}\n📞 Telefon: {a.get('phone') or '—'}\n🎭 Rol: {a.get('role')} / qulflangan: {a.get('locked_role') or '—'}\n🚴 Kuryer: {'ha' if a.get('courier_registered') else 'yo‘q'} ({a.get('courier_status') or '—'}) — 🪪 Pasport: {a.get('passport_num') or '—'}\n📦 Buyurtmalari: {a.get('orders_count',0)} ta — Yetkazgan: {a.get('delivered',0)} ta — Topgani: {a.get('earned_delivery',0):,} so'm\n\nDo'konlari:\n{shops}\n\n⚠️ Parol hash ko'rinmaydi — admin faqat YANGI parol bera oladi.")
# --- SOZLAMALAR: admin paneldan o'zgartiriladi, db.json da saqlanadi (kodga tegish shart emas) ---
DEFAULT_SETTINGS = {"delivery_city": 15000, "delivery_outside": 30000, "delivery_far": 50000, "commission": 2000, "free_delivery": 0}
def get_settings():
    s = dict(DEFAULT_SETTINGS); s.update(DB.get("settings", {}) or {}); return s
def delivery_zones():
    s = get_settings()
    return {"1": ("🏙️ Shahar ichi", s["delivery_city"]), "2": ("🏡 Shahar tashqaris", s["delivery_outside"]), "3": ("🛣️ Uzoq tuman", s["delivery_far"])}
def get_commission():
    return get_settings()["commission"]
def set_setting(key, value):
    DB.setdefault("settings", {})[key] = value; save()
def hpw(p): return hashlib.sha256(str(p).encode()).hexdigest()
def avg(ratings):
    return sum(ratings)/len(ratings) if ratings else 0

PACKAGING_GUIDE = """📦 QADOQLASH YO'RIQNOMASI — yaxshilab o'qing!

1️⃣ Mahsulotni tekshiring: dog', yirtiq, nuqson yo'qmi? Razmer + rang buyurtmadagi bilan bir xilmi?
2️⃣ Toza paketga soling — kiyimni chiroyli buklang, g'ijimlamang.
3️⃣ Ichiga kichik qog'oz soling: Do'kon nomi + rahmat so'zi.
4️⃣ Paketni yopishtiring, ustiga buyurtma raqamini yozing.
5️⃣ Sumka / qopga soling, yomg'irda ho'l bo'lmasin.
6️⃣ Tayyor bo'lgach — shu yerda buyurtmaning RASMINI yuboring.
⚠️ Rasm yubormasangiz, mijozga 'Tayyor' xabari ketmaydi!
"""

# ---------- LOGIN / PAROL ----------
def auth_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Kirish (login + parol)", callback_data="auth_login")],
        [InlineKeyboardButton("📝 Ro'yxatdan o'tish", callback_data="auth_register")],
        [InlineKeyboardButton("🔐 Parolni unutdim — adminga yozish", callback_data="auth_forgot")],
    ])
def is_authed(context, uid):
    return context.user_data.get("authed") is True
async def ask_login(update, context, text="🔒 Botga kirish uchun login + parol kerak.\n\nBirinchi marta bo'lsangiz — Ro'yxatdan o'ting."):
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=auth_kb())
    else:
        await update.message.reply_text(text, reply_markup=auth_kb())
def find_by_login(login):
    login = login.strip().lower()
    for uid, u in DB["users"].items():
        if str(u.get("login","")).lower() == login: return uid, u
    return None, None

def main_kb(role, locked=None):
    if role == "shop":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🏪 Mening do'konim", callback_data="shop_panel")],
            [InlineKeyboardButton("➕ Mol qo'shish", callback_data="add_product")],
            [InlineKeyboardButton("👕 Mollarim", callback_data="my_products")],
            [InlineKeyboardButton("📦 Yangi buyurtmalar", callback_data="shop_orders")],
            [InlineKeyboardButton("💳 Kartalarim (Click / Payme)", callback_data="shop_cards")],
            [InlineKeyboardButton("⭐ Mening reytingim", callback_data="shop_my_rating")],
            [InlineKeyboardButton("📊 Statistika", callback_data="shop_stats")],
            [InlineKeyboardButton("🔐 Parolni o'zgartirish", callback_data="change_pass")],
            [InlineKeyboardButton("🚪 Chiqish", callback_data="logout")],
        ])
    if role == "courier":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🚴 Kuryer panel", callback_data="courier_panel")],
            [InlineKeyboardButton("🟢 ONLINE / 🔴 OFFLINE", callback_data="courier_toggle")],
            [InlineKeyboardButton("📦 Bo'sh buyurtmalar", callback_data="courier_list")],
            [InlineKeyboardButton("⭐ Mening reytingim", callback_data="courier_my_rating")],
            [InlineKeyboardButton("💰 Hisobim", callback_data="courier_balance")],
            [InlineKeyboardButton("🔐 Parolni o'zgartirish", callback_data="change_pass")],
            [InlineKeyboardButton("🚪 Chiqish", callback_data="logout")],
        ])
    if role == "admin":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🏪 Do'konlar", callback_data="admin_shops")],
            [InlineKeyboardButton("📄 Guvohnoma kutayotganlar", callback_data="admin_pending")],
            [InlineKeyboardButton("⭐ Reytinglar — hammaniki", callback_data="admin_ratings")],
            [InlineKeyboardButton("📦 Barcha buyurtmalar", callback_data="admin_orders")],
            [InlineKeyboardButton("📊 Do'konlar qarzi (komissiya)", callback_data="admin_debt")],
            [InlineKeyboardButton("👥 Mijozlar", callback_data="admin_users")],
            [InlineKeyboardButton("🚴 Kuryerlar", callback_data="admin_couriers")],
            [InlineKeyboardButton("⚙️ Narxlar — yetkazish + komissiya", callback_data="admin_settings")],
            [InlineKeyboardButton("🗄️ Arxiv / Parol tiklash", callback_data="admin_archive")],
            [InlineKeyboardButton("💾 Zaxira / Export — bazani yuklab olish", callback_data="admin_backup")],
            [InlineKeyboardButton("📥 Tiklash — zaxira faylni yuborish", callback_data="admin_restore_help")],
            [InlineKeyboardButton("🔐 Parolni o'zgartirish", callback_data="change_pass")],
            [InlineKeyboardButton("🚪 Chiqish", callback_data="logout")],
        ])
    base = [
        [InlineKeyboardButton("🛍️ Do'konlar", callback_data="client_shops")],
        [InlineKeyboardButton("🛒 Savatim", callback_data="client_cart")],
        [InlineKeyboardButton("📦 Buyurtmalarim", callback_data="client_my")],
        [InlineKeyboardButton("💰 Hisobim", callback_data="client_balance")],
        [InlineKeyboardButton("🔐 Parolni o'zgartirish", callback_data="change_pass")],
        [InlineKeyboardButton("🚪 Chiqish", callback_data="logout")],
    ]
    # MIJOZ PANELIDA do'konchi / kuryer bo'lish tugmalari BO'LMAYDI.
    # Do'konchi / kuryer bo'lish faqat ro'yxatdan o'tishda tanlanadi.
    return InlineKeyboardMarkup(base)

async def show_main(update, uid, text="Asosiy menyu:"):
    u = DB["users"].get(str(uid), {})
    kb = main_kb(u.get("role", "client"), u.get("locked_role"))
    try:
        if update.callback_query:
            try: await update.callback_query.message.delete()
            except: pass
            await update.callback_query.message.reply_text(text, reply_markup=kb)
        else: await update.message.reply_text(text, reply_markup=kb)
    except: pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    # Admin ham parol bilan kiradi
    if update.effective_user.id == SUPER_ADMIN:
        if context.user_data.get("authed") and context.user_data.get("auth_role") == "admin":
            await update.message.reply_text("👑 Salom Boss!\nQaysi rolni ko'rmoqchisan?", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin panel", callback_data="setrole_admin")],
                [InlineKeyboardButton("🛍️ Mijoz sifatida", callback_data="setrole_client")],
                [InlineKeyboardButton("🏪 Do'konchi sifatida", callback_data="setrole_shop")],
                [InlineKeyboardButton("🚴 Kuryer sifatida", callback_data="setrole_courier")],
            ])); return
        context.user_data["step"] = "admin_pass"
        await update.message.reply_text("🔒 ADMIN PANEL\n\nAdmin parolini yozing:"); return
    # Botni o'chirib qaytgan bo'lsa - arxivdan eski login/rolni tiklaymiz
    _a = _arch(uid)
    if _a and uid in DB["users"]:
        for _k in ("login", "password_hash", "phone", "role", "locked_role", "courier_registered", "courier_status", "passport_num", "passport_photo"):
            if not DB["users"][uid].get(_k) and _a.get(_k) is not None: DB["users"][uid][_k] = _a[_k]
        save()
    if context.user_data.get("authed"):
        await show_main(update, update.effective_user.id, f"Salom {DB['users'].get(uid, {}).get('name','')}! 👋\n\n🛍️ TERMIZ KIYIM BOTI ga xush kelibsiz!")
        return
    await ask_login(update, context, "👋 TERMIZ KIYIM BOTI ga xush kelibsiz!\n\n🔒 Botga kirish uchun login + parol kerak.\n\nBirinchi marta bo'lsangiz — Ro'yxatdan o'ting, bo'lmasa — Kirish ni bosing.")

async def register_shop(update, context):
    q = update.callback_query; await q.answer()
    u = DB["users"].get(str(q.from_user.id), {})
    if u.get("locked_role") and u["locked_role"] != "shop":
        await q.message.reply_text("🔒 Siz boshqa rolga qulflangansiz."); return
    if any(v.get("admin") == q.from_user.id for v in DB["shops"].values()):
        await q.message.reply_text("✅ Sizda allaqachon do'kon bor."); return
    context.user_data["step"] = "reg_shop_name"; context.user_data["reg"] = {}
    await q.message.reply_text("🏪 Do'kon ochish — 1/5\n\nDo'kon nomini yozing:\n\n⚠️ Do'kon ochish uchun GUVOHNOMA shart!\nGuvohnomangiz bo'lmasa, arizangiz tasdiqlanmaydi.")

async def register_courier(update, context):
    q = update.callback_query; await q.answer()
    uid = str(q.from_user.id)
    DB["users"][uid]["courier_registered"] = True; DB["users"][uid]["courier_status"] = "pending"; DB["users"][uid]["locked_role"] = "courier"; DB["users"][uid]["role"] = "courier"; save()
    context.user_data["step"] = "courier_phone"
    await q.message.reply_text("🚴 Kuryer bo'lish — 1/3\n\n📞 Telefon raqamingizni yozing:\n\n⚠️ Kuryer bo'lish uchun PASPORT / GUVOHNOMA shart!\nHujjatingiz bo'lmasa, arizangiz tasdiqlanmaydi.")

AUTH_STEPS = {"auth_login_login", "auth_login_pass", "auth_reg_role", "auth_reg_name", "auth_reg_login", "auth_reg_pass", "admin_pass", "change_pass_old", "change_pass_new"}

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id); txt = update.message.text.strip()
    step = context.user_data.get("step")
    # --- ADMIN PAROLI ---
    if step == "admin_pass":
        if txt == ADMIN_PASSWORD:
            context.user_data["authed"] = True; context.user_data["auth_role"] = "admin"; context.user_data["step"] = None
            if uid not in DB["users"]:
                DB["users"][uid] = {"name": "Admin", "role": "admin", "phone": "", "online": False, "balance": 0, "delivered": 0, "cart": [], "ratings": [], "login": "admin"}
                save()
            await update.message.reply_text("✅ Admin sifatida kirdingiz!", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin panel", callback_data="setrole_admin")],
                [InlineKeyboardButton("🛍️ Mijoz sifatida", callback_data="setrole_client")],
                [InlineKeyboardButton("🏪 Do'konchi sifatida", callback_data="setrole_shop")],
                [InlineKeyboardButton("🚴 Kuryer sifatida", callback_data="setrole_courier")],
            ])); return
        await update.message.reply_text("❌ Parol noto'g'ri. Qaytadan yozing:"); return
    # --- KIRISH ---
    if step == "auth_login_login":
        _, u = find_by_login(txt)
        if not u: await update.message.reply_text("❌ Bunday login topilmadi. Loginni qaytadan yozing yoki Ro'yxatdan o'ting:"); return
        context.user_data["login_try"] = txt.lower(); context.user_data["step"] = "auth_login_pass"
        await update.message.reply_text("🔐 Parolni yozing:"); return
    if step == "auth_login_pass":
        _, u = find_by_login(context.user_data.get("login_try", ""))
        if not u or u.get("password_hash") != hpw(txt):
            await update.message.reply_text("❌ Parol noto'g'ri. Qaytadan yozing:"); return
        # Shu Telegram hisobiga bog'lash (boshqa telefondan kirsa ham ishlaydi)
        old_uid, _ = find_by_login(context.user_data.get("login_try", ""))
        if old_uid != uid:
            DB["users"][uid] = DB["users"][old_uid]
            # eski yozuvni o'chirmaymiz - u ham shu odam, lekin asosiy uid yangisi bo'ladi
        context.user_data["authed"] = True; context.user_data["auth_role"] = u.get("role", "client"); context.user_data["step"] = None
        await show_main(update, update.effective_user.id, f"✅ Xush kelibsiz, {u.get('name','')}!\nLogin: {u.get('login')}\nRol: {u.get('role')}"); return
    # --- RO'YXATDAN O'TISH ---
    if step == "auth_reg_role":
        if txt not in ("1", "2", "3"):
            await update.message.reply_text("❌ 1, 2 yoki 3 deb yozing:\n1 — Mijoz\n2 — Do'konchi\n3 — Kuryer"); return
        context.user_data["reg_role"] = {"1": "client", "2": "shop", "3": "courier"}[txt]
        context.user_data["step"] = "auth_reg_name"
        await update.message.reply_text("👤 Ismingizni yozing:"); return
    if step == "auth_reg_name":
        context.user_data["reg_name"] = txt; context.user_data["step"] = "auth_reg_login"
        await update.message.reply_text("🔑 Login o'ylab toping (lotin harflari, bo'sh joysiz):\nMasalan: farrux123"); return
    if step == "auth_reg_login":
        if " " in txt or len(txt) < 3: await update.message.reply_text("❌ Login kamida 3 ta belgi, bo'sh joysiz bo'lsin. Qaytadan yozing:"); return
        _, ex = find_by_login(txt)
        if ex: await update.message.reply_text("❌ Bu login band. Boshqa login yozing:"); return
        context.user_data["reg_login"] = txt.lower(); context.user_data["step"] = "auth_reg_pass"
        await update.message.reply_text("🔐 Parol o'ylab toping (kamida 4 ta belgi):\nUni hech kimga bermang!"); return
    if step == "auth_reg_pass":
        if len(txt) < 4: await update.message.reply_text("❌ Parol kamida 4 ta belgi bo'lsin:"); return
        role = context.user_data.get("reg_role", "client")
        DB["users"][uid] = {"name": context.user_data.get("reg_name", "Foydalanuvchi"), "role": role, "locked_role": role if role != "client" else None, "phone": "", "online": False, "balance": 0, "delivered": 0, "cart": [], "ratings": [], "login": context.user_data["reg_login"], "password_hash": hpw(txt), "courier_registered": role == "courier"}
        save()
        context.user_data["authed"] = True; context.user_data["auth_role"] = role; context.user_data["step"] = None
        if role == "shop":
            await update.message.reply_text(f"✅ Ro'yxatdan o'tdingiz!\nLogin: {context.user_data.get('reg_login')}\nRol: Do'konchi\n\nEndi do'kon oching:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏪 Do'kon ochish", callback_data="register_shop")]])); return
        if role == "courier":
            DB["users"][uid]["courier_status"] = "pending"
            save()
            context.user_data["step"] = "courier_phone"
            await update.message.reply_text(f"✅ Ro'yxatdan o'tdingiz!\nLogin: {context.user_data.get('reg_login')}\nRol: Kuryer\n\n🚴 Kuryer bo'lish — 1/3\n📞 Telefon raqamingizni yozing:\n\n⚠️ Pasport / guvohnoma shart!"); return
        await show_main(update, update.effective_user.id, f"✅ Ro'yxatdan o'tdingiz!\nLogin: {context.user_data.get('reg_login')}\nRol: Mijoz\n\nEndi do'konlardan xarid qilishingiz mumkin."); return
    # --- PAROLNI O'ZGARTIRISH ---
    if step == "change_pass_old":
        u = DB["users"].get(uid, {})
        if u.get("password_hash") != hpw(txt):
            await update.message.reply_text("❌ Eski parol noto'g'ri. Qaytadan yozing:"); return
        context.user_data["step"] = "change_pass_new"
        await update.message.reply_text("🔐 Yangi parolni yozing (kamida 4 ta belgi):"); return
    if step == "change_pass_new":
        if len(txt) < 4: await update.message.reply_text("❌ Kamida 4 ta belgi:"); return
        DB["users"][uid]["password_hash"] = hpw(txt); save(); context.user_data["step"] = None
        await update.message.reply_text("✅ Parol o'zgartirildi! Endi yangi parol bilan kirasiz."); return
    # --- KIRISH QILMAGANLARGA RUXSAT YO'Q ---
    if not is_authed(context, uid):
        await ask_login(update, context); return
    if not step:
        await show_main(update, update.effective_user.id, "Asosiy menyu:"); return
    if step == "courier_phone":
        DB["users"][uid]["phone"] = txt; save(); context.user_data["step"] = "courier_passport_num"
        await update.message.reply_text("🚴 Kuryer bo'lish — 2/3 — 🪪 PASPORT\n\nPasport seriya + raqamini yozing:\nMasalan: AA1234567\n\nPasportsiz ariza qabul qilinmaydi!"); return
    if step == "courier_passport_num":
        if len(txt) < 5:
            await update.message.reply_text("❌ Pasport raqami juda qisqa. To'liq yozing, masalan: AA1234567"); return
        DB["users"][uid]["passport_num"] = txt; DB["users"][uid]["courier_status"] = "pending"; save(); context.user_data["step"] = "courier_passport_photo"
        await update.message.reply_text("🚴 Kuryer bo'lish — 3/3 — 🪪 PASPORT RASMI\n\nEndi pasportingizning RASMINI yuboring — rasm tiniq, hamma yozuvi o'qiladigan bo'lsin!\n\n⚠️ Rasm yubormasangiz, kuryer bo'la olmaysiz."); return
    if step == "reg_shop_name":
        context.user_data["reg"] = context.user_data.get("reg", {}); context.user_data["reg"]["name"] = txt; context.user_data["step"] = "reg_shop_phone"
        await update.message.reply_text("🏪 2/5\nTelefon raqamingizni yozing:"); return
    if step == "reg_shop_phone":
        context.user_data["reg"]["phone"] = txt; context.user_data["step"] = "reg_shop_addr"
        await update.message.reply_text("🏪 3/5\nDo'kon manzilini yozing:"); return
    if step == "reg_shop_addr":
        context.user_data["reg"]["address"] = txt; context.user_data["step"] = "reg_shop_guv_num"
        await update.message.reply_text("🏪 4/5 — 📄 GUVOHNOMA\n\nGuvohnoma RAQAMINI yozing:\nMasalan: 123456789\n\nGuvohnoma raqamisiz ariza qabul qilinmaydi!"); return
    if step == "reg_shop_guv_num":
        if len(txt) < 4:
            await update.message.reply_text("❌ Guvohnoma raqami juda qisqa. To'liq raqamni yozing:"); return
        context.user_data["reg"]["guvohnoma_num"] = txt; context.user_data["step"] = "reg_shop_guv_photo"
        await update.message.reply_text("🏪 5/5 — 📄 GUVOHNOMA RASMI\n\nEndi guvohnomangizning RASMINI yuboring — rasm tiniq, hamma yozuvi o'qiladigan bo'lsin!\n\n⚠️ Rasm yubormasangiz, do'koningiz ochilmaydi."); return
    if step == "reg_shop_click":
        slug = context.user_data.get("reg", {}).get("shop_slug")
        shop = DB["shops"].get(slug)
        if shop:
            shop["click_card"] = "" if txt.strip() == "-" else txt.strip(); shop["click_name"] = DB["users"].get(uid, {}).get("name",""); save()
        context.user_data["step"] = "reg_shop_payme"
        await update.message.reply_text("💳 Endi PAYME kartangizni yozing:\nMasalan: 8600 1234 5678 9012\nPayme ingiz yo'q bo'lsa, '-' yozing."); return
    if step == "reg_shop_payme":
        slug = context.user_data.get("reg", {}).get("shop_slug")
        shop = DB["shops"].get(slug)
        if shop:
            shop["payme_card"] = "" if txt.strip() == "-" else txt.strip(); shop["payme_name"] = DB["users"].get(uid, {}).get("name",""); save()
        context.user_data["step"] = None; context.user_data["reg"] = {}
        await show_main(update, update.effective_user.id, f"✅ Arizangiz qabul qilindi!\n\n🏪 Do'kon: {shop['name'] if shop else ''}\n💳 Click: {shop.get('click_card') or 'yo‘q'} | Payme: {shop.get('payme_card') or 'yo‘q'}\n\n⏳ Hozir admin guvohnomangizni tekshiryapti. Tasdiqlansa, sizga xabar keladi."); return
    if step == "shop_cards_click":
        my = [v for v in DB["shops"].values() if v.get("admin") == update.effective_user.id]
        if not my: return
        my[0]["click_card"] = "" if txt.strip() == "-" else txt.strip(); my[0]["click_name"] = DB["users"].get(uid, {}).get("name",""); save()
        context.user_data["step"] = "shop_cards_payme"
        await update.message.reply_text(f"✅ Click karta saqlandi: {my[0]['click_card'] or 'o‘chirildi'}\n\nEndi Payme kartangizni yozing (yo'q bo'lsa '-' yozing):"); return
    if step == "shop_cards_payme":
        my = [v for v in DB["shops"].values() if v.get("admin") == update.effective_user.id]
        if not my: return
        my[0]["payme_card"] = "" if txt.strip() == "-" else txt.strip(); my[0]["payme_name"] = DB["users"].get(uid, {}).get("name",""); save()
        context.user_data["step"] = None
        await show_main(update, update.effective_user.id, f"✅ Kartalar saqlandi!\n💳 Click: {my[0].get('click_card') or 'yo‘q'}\n💳 Payme: {my[0].get('payme_card') or 'yo‘q'}\nEndi mijozlar shu kartalaringizga to'laydi."); return
    if isinstance(step, str) and step.startswith("admin_setpass_"):
        _uid = step.replace("admin_setpass_", "")
        if len(txt) < 4:
            await update.message.reply_text("❌ Parol kamida 4 ta belgi bo'lsin. Qaytadan yozing:"); return
        _a = _arch(_uid)
        if _uid not in DB["users"]:
            if not _a: await update.message.reply_text("❌ Bu odam arxivda topilmadi."); return
            DB["users"][_uid] = {"name": _a.get("name",""), "role": _a.get("role","client"), "phone": _a.get("phone",""), "login": _a.get("login"), "online": False, "balance": 0, "delivered": 0, "cart": []}
            for _k in ("locked_role", "courier_registered", "courier_status", "passport_num", "passport_photo"):
                if _a.get(_k) is not None: DB["users"][_uid][_k] = _a[_k]
        DB["users"][_uid]["password_hash"] = hpw(txt); save()
        context.user_data["step"] = None
        await update.message.reply_text(f"✅ Yangi parol berildi!\n\n👤 {_a.get('name','?')} (login: {_a.get('login') or DB['users'][_uid].get('login')})\n🔑 Yangi parol: {txt}\n\n⚠️ Shu parolni odamga o'zingiz yetkazib qo'ying (telefon orqali). U botda '🔑 Kirish' ni bosib, eski logini + shu yangi parol bilan kiradi."); return
    if isinstance(step, str) and step.startswith("admin_setlogin_"):
        _uid = step.replace("admin_setlogin_", "")
        _lg = txt.strip().lower()
        if len(_lg) < 3:
            await update.message.reply_text("❌ Login kamida 3 ta belgi bo'lsin. Qaytadan yozing:"); return
        _ex, _u = find_by_login(_lg)
        if _ex and str(_ex) != str(_uid):
            await update.message.reply_text(f"❌ Bu login band — {_u.get('name')} da. Boshqa login yozing:"); return
        if _uid not in DB["users"]:
            if not _arch(_uid): await update.message.reply_text("❌ Bu odam arxivda topilmadi."); return
            DB["users"][_uid] = {"name": _arch(_uid).get("name",""), "role": "client", "phone": "", "online": False, "balance": 0, "delivered": 0, "cart": []}
        DB["users"][_uid]["login"] = _lg; save()
        context.user_data["step"] = None
        await update.message.reply_text(f"✅ Yangi login berildi: {_lg}\n\nOdamga ayting: botda '🔑 Kirish' → login: {_lg} + o'z paroli bilan kirsin. Parolini ham unutgan bo'lsa, avval unga yangi parol bering."); return
    if isinstance(step, str) and step == "admin_archive_search":
        _q = txt.strip().lower(); _found = []
        for _uid, _a in DB.get("archive", {}).items():
            if _q in str(_a.get("login","")).lower() or _q in str(_a.get("phone","")).lower() or _q in str(_a.get("name","")).lower():
                _found.append((_uid, _a))
        if not _found: await update.message.reply_text("❌ Topilmadi. Telefon raqami, login yoki ism bilan qidirib ko'ring."); return
        context.user_data["step"] = None
        for _uid, _a in _found[:10]:
            await update.message.reply_text(_arch_text(_a), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔑 Yangi parol berish", callback_data=f"admin_setpass_{_uid}")],[InlineKeyboardButton("✏️ Loginni o'zgartirish", callback_data=f"admin_setlogin_{_uid}")]]))
        return
    if step in ("admin_set_city", "admin_set_outside", "admin_set_far", "admin_set_commission", "admin_set_free"):
        try: val = int(txt.replace(" ", "").replace(",", ""))
        except: await update.message.reply_text("❌ Faqat raqam yozing, masalan: 20000"); return
        _mx = 10000000 if step == "admin_set_free" else 500000
        if val < 0 or val > _mx:
            await update.message.reply_text(f"❌ Narx 0 dan {_mx:,} gacha bo'lishi kerak. Qaytadan yozing:"); return
        key_map = {"admin_set_city": "delivery_city", "admin_set_outside": "delivery_outside", "admin_set_far": "delivery_far", "admin_set_commission": "commission", "admin_set_free": "free_delivery"}
        set_setting(key_map[step], val); context.user_data["step"] = None
        await update.message.reply_text(f"✅ Saqlandi: {val:,} so'm\n\nEndi mijozlarga ham, kuryerlarga ham shu yangi narx chiqadi.")
        # Sozlamalar ekranini qayta ko'rsatish uchun admin_settings ni chaqirish o'rniga matn bilan:
        s = get_settings()
        _fr = s.get('free_delivery', 0)
        await update.message.reply_text(f"⚙️ HOZIRGI NARXLAR\n\n🏙️ Shahar ichi: {s['delivery_city']:,} so'm\n🏡 Shahar tashqaris: {s['delivery_outside']:,} so'm\n🎁 Bepul yetkazish: {'o‘chirilgan' if not _fr else f'{_fr:,} so‘mdan oshsa BEPUL'}\n🛣️ Uzoq tuman: {s['delivery_far']:,} so'm\n💸 Komissiya (har bir buyurtmadan): {s['commission']:,} so'm", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏙️ Shahar ichi narxini o'zgartirish", callback_data="admin_set_city")],[InlineKeyboardButton("🏡 Shahar tashqaris narxini o'zgartirish", callback_data="admin_set_outside")],[InlineKeyboardButton("🛣️ Uzoq tuman narxini o'zgartirish", callback_data="admin_set_far")],[InlineKeyboardButton("💸 Komissiyani o'zgartirish", callback_data="admin_set_commission")],[InlineKeyboardButton("🎁 Bepul yetkazish chegarasi", callback_data="admin_set_free")]])); return
    if step == "add_p_name":
        context.user_data["prod"] = {"name": txt}; context.user_data["step"] = "add_p_price"
        await update.message.reply_text("💰 Narxini yozing (faqat raqam):"); return
    if step == "add_p_price":
        try: price = int(txt.replace(" ", ""))
        except: await update.message.reply_text("❌ Faqat raqam yozing: 120000"); return
        context.user_data["prod"]["price"] = price; context.user_data["step"] = None
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(c, callback_data=f"p_cat_{i}")] for i, c in enumerate(CATEGORIES)])
        await update.message.reply_text("📂 Kategoriyani tanlang:", reply_markup=kb); return
    if step == "add_p_sizes":
        context.user_data["prod"]["sizes"] = [s.strip().upper() for s in txt.split(",") if s.strip()]
        context.user_data["step"] = "add_p_colors"
        await update.message.reply_text("🎨 Ranglarini vergul bilan yozing:\nMasalan: Qora, Oq, Bej"); return
    if step == "add_p_colors":
        context.user_data["prod"]["colors"] = [s.strip() for s in txt.split(",") if s.strip()]
        context.user_data["step"] = "add_p_stock"
        await update.message.reply_text("📦 Nechta bor? Soni yozing:"); return
    if step == "add_p_stock":
        try: context.user_data["prod"]["stock"] = int(txt)
        except: await update.message.reply_text("❌ Faqat raqam: 10"); return
        context.user_data["step"] = "add_p_photo"
        await update.message.reply_text("📸 Endi molning RASMINI yuboring (1 ta rasm)"); return
    if step == "order_addr":
        context.user_data["order_addr"] = txt; context.user_data["step"] = "order_location"
        kb = ReplyKeyboardMarkup([[KeyboardButton("📍 Lokatsiyamni yuborish", request_location=True)]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("📍 Endi LOKATSIYANGIZNI yuboring — kuryer adashmasdan topsin.\n\nPastdagi tugmani bosing, yoki 'O'tkazib yuborish' deb yozing:", reply_markup=kb); return
    if step == "order_location":
        if txt.lower() in ("o'tkazib yuborish", "o'tkazib", "skip", "yo'q"):
            context.user_data["order_location"] = None; context.user_data["step"] = "order_phone"
            await update.message.reply_text("📞 Telefon raqamingizni yozing:", reply_markup=ReplyKeyboardRemove()); return
        await update.message.reply_text("📍 Iltimos pastdagi tugma bilan lokatsiya yuboring yoki 'O'tkazib yuborish' deb yozing:"); return
    if step == "order_phone":
        context.user_data["order_phone"] = txt; context.user_data["step"] = "order_zone"
        _s = get_settings()
        _free_note = f"\n\n🎁 {_s.get('free_delivery',0):,} so'mdan oshsa yetkazish BEPUL!" if _s.get('free_delivery',0) else ""
        await update.message.reply_text(f"🚴 YETKAZISH HUDUDINI TANLANG\n\nManzilingiz qayerda?\n\n1 — 🏙️ Shahar ichi — {_s['delivery_city']:,} so'm\n2 — 🏡 Shahar tashqaris — {_s['delivery_outside']:,} so'm\n3 — 🛣️ Uzoq tuman — {_s['delivery_far']:,} so'm{_free_note}\n\nRaqam yozing: 1 / 2 / 3"); return
    if step == "order_zone":
        if txt not in ("1","2","3"):
            await update.message.reply_text("❌ Faqat 1, 2 yoki 3 yozing:\n1 — Shahar ichi\n2 — Shahar tashqaris\n3 — Uzoq tuman"); return
        zname, zfee = delivery_zones()[txt]
        cart = DB["users"][uid].get("cart", [])
        total = sum(DB["shops"][i["shop"]]["products"][i["pid"]]["price"] * i["qty"] for i in cart)
        _thr = get_settings().get('free_delivery', 0)
        _free = bool(_thr and total >= _thr)
        if _free: zfee = 0
        context.user_data["order_zone"] = zname; context.user_data["order_delivery"] = zfee; context.user_data["order_free"] = _free; context.user_data["step"] = "order_pay"
        _del_tx = "🎁 BEPUL!" if _free else f"{zfee:,} so'm"
        _pay_tx = "1 — 💵 Naqd (faqat mol pulini kuryerga berasiz — yetkazish BEPUL)\n2 — 🟣 Click (mol puli do'konchiga — yetkazish BEPUL)\n3 — 🔵 Payme (mol puli do'konchiga — yetkazish BEPUL)" if _free else "1 — 💵 Naqd (hammasini kuryerga berasiz)\n2 — 🟣 Click (mol puli do'konchiga, yetkazish haqi kuryerga naqd)\n3 — 🔵 Payme (mol puli do'konchiga, yetkazish haqi kuryerga naqd)"
        await update.message.reply_text(f"🚴 Yetkazish: {zname} — {_del_tx}\n💰 Mol: {total:,} so'm\n🧾 Jami: {total+zfee:,} so'm\n\n💳 TO'LOV USULINI TANLANG\n\n{_pay_tx}\n\nRaqam yozing: 1 / 2 / 3"); return
    if step == "order_pay":
        if txt not in ("1","2","3"):
            await update.message.reply_text("❌ Faqat 1, 2 yoki 3 yozing:\n1 — Naqd\n2 — Click\n3 — Payme"); return
        pay_map = {"1": "cash", "2": "click", "3": "payme"}; pay_method = pay_map[txt]
        cart = DB["users"][uid].get("cart", [])
        if not cart: await update.message.reply_text("Savat bo'sh"); return
        total = sum(DB["shops"][i["shop"]]["products"][i["pid"]]["price"] * i["qty"] for i in cart)
        delivery = context.user_data.get("order_delivery", get_settings()["delivery_city"]); zname = context.user_data.get("order_zone", "🏙️ Shahar ichi")
        phone = context.user_data.get("order_phone",""); addr = context.user_data.get("order_addr","")
        oid = str(DB["counter"]); DB["counter"] += 1
        if pay_method == "cash":
            DB["orders"][oid] = {"user_id": update.effective_user.id, "items": cart, "total": total, "delivery": delivery, "zone": zname, "address": addr, "location": context.user_data.get("order_location"), "phone": phone, "status": "new", "payment": "cash", "payment_status": "cash", "courier": None, "shop_rating": None, "courier_rating": None}
            for item in cart: DB["shops"][item["shop"]]["debt"] = DB["shops"][item["shop"]].get("debt", 0) + get_commission()
            DB["users"][uid]["cart"] = []; save(); context.user_data["step"] = None
            for shop_id in set(i["shop"] for i in cart):
                shop = DB["shops"][shop_id]
                try: await context.bot.send_message(shop["admin"], f"🔔 YANGI BUYURTMA #{oid}\nDo'kon: {shop['name']}\nMijoz tel: {phone}\nManzil: {addr}\nHudud: {zname}\nMol: {total:,} + Yetkazish: {delivery:,} = {total+delivery:,} so'm\n💵 To'lov: NAQD (kuryerga beriladi)\n\nBotda '📦 Yangi buyurtmalar' ni bosing.")
                except: pass
            await show_main(update, update.effective_user.id, f"✅ Buyurtmangiz qabul qilindi! #{oid}\nMol: {total:,} + Yetkazish ({zname}): {delivery:,} = Jami: {total+delivery:,} so'm\n💵 To'lov: Naqd — kuryerga berasiz."); return
        # Click / Payme - har bir do'konning o'z kartasi bormi?
        missing = []
        for shop_id in set(i["shop"] for i in cart):
            shop = DB["shops"][shop_id]; card, _ = shop_card(shop, pay_method)
            if not card: missing.append(shop["name"])
        if missing:
            DB["counter"] -= 1
            await update.message.reply_text(f"❌ Bu do'konlarda {pay_method.upper()} kartasi qo'yilmagan:\n• " + "\n• ".join(missing) + "\n\nBoshqa usulni tanlang:\n1 — Naqd\n2 — Click\n3 — Payme"); return
        DB["orders"][oid] = {"user_id": update.effective_user.id, "items": cart, "total": total, "delivery": delivery, "zone": zname, "address": addr, "location": context.user_data.get("order_location"), "phone": phone, "status": "awaiting_payment", "payment": pay_method, "payment_status": "waiting", "courier": None, "shop_rating": None, "courier_rating": None}
        DB["users"][uid]["cart"] = []; save(); context.user_data["step"] = f"pay_receipt_{oid}"
        label = "🟣 CLICK" if pay_method=="click" else "🔵 PAYME"
        lines = []
        for shop_id in set(i["shop"] for i in cart):
            shop = DB["shops"][shop_id]
            sub = sum(DB["shops"][i["shop"]]["products"][i["pid"]]["price"] * i["qty"] for i in cart if i["shop"] == shop_id)
            card, cname = shop_card(shop, pay_method)
            lines.append(f"🏪 {shop['name']}\n   💰 {sub:,} so'm\n   💳 {card}\n   👤 {cname or shop['name']}")
        await update.message.reply_text(f"{label} BILAN TO'LOV — Buyurtma #{oid}\n\n💰 Mol: {total:,} so'm\n🚴 Yetkazish ({zname}): {delivery:,} so'm — KURYERGA NAQD berasiz\n📝 Izoh: {PAYMENT_NOTE} #{oid}\n\n" + "\n\n".join(lines) + f"\n\n1️⃣ {label} da har bir do'konning kartasiga o'z summasini o'tkazing.\n2️⃣ Hamma chekni shu yerga RASM qilib yuboring.\n\n⚠️ Chek yubormasangiz, buyurtma tayyorlanmaydi! Pul ADMINGA emas — DO'KONCHIGA tushadi."); return
    if step.startswith("pay_receipt_"):
        await update.message.reply_text("📸 Chekni RASM qilib yuboring — matn emas, skrinshot / chek rasmi bo'lsin."); return

async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authed(context, update.effective_user.id): await ask_login(update, context); return
    if context.user_data.get("step") != "order_location": return
    loc = update.message.location
    context.user_data["order_location"] = {"lat": loc.latitude, "lon": loc.longitude}
    context.user_data["step"] = "order_phone"
    await update.message.reply_text("✅ Lokatsiya saqlandi! 📍\n\n📞 Endi telefon raqamingizni yozing:", reply_markup=ReplyKeyboardRemove())

async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authed(context, update.effective_user.id): await ask_login(update, context); return
    step = context.user_data.get("step", "")
    # --- PASPORT RASMI: kuryer ro'yxatdan o'tayotganda ---
    if step == "courier_passport_photo":
        uid = str(update.effective_user.id)
        DB["users"][uid]["passport_photo"] = update.message.photo[-1].file_id
        DB["users"][uid]["courier_status"] = "pending"; save()
        context.user_data["step"] = None
        u = DB["users"][uid]
        await update.message.reply_text(f"✅ Arizangiz qabul qilindi!\n\n🚴 Kuryer: {u.get('name')}\n🪪 Pasport: {u.get('passport_num')}\n📞 Tel: {u.get('phone')}\n\n⏳ Hozir admin pasportingizni tekshiryapti.\nTasdiqlansa, sizga xabar keladi va buyurtma ola boshlaysiz.\nTasdiqlanmaguncha buyurtma ola olmaysiz.")
        try:
            await context.bot.send_photo(SUPER_ADMIN, u.get("passport_photo"), caption=f"🪪 YANGI KURYER ARIZASI!\n\n🚴 Kuryer: {u.get('name')} (@{update.effective_user.username or '-'})\nLogin: {u.get('login')}\n📞 Tel: {u.get('phone')}\n🪪 Pasport: {u.get('passport_num')}\n\nAdmin panelda tasdiqlang.")
            await context.bot.send_message(SUPER_ADMIN, "Yuqoridagi kuryerni tasdiqlash uchun: /start → Admin panel → 📄 Guvohnoma kutayotganlar")
        except: pass
        return
    # --- CLICK / PAYME CHEK RASMI ---
    if isinstance(step, str) and step.startswith("pay_receipt_"):
        oid = step.replace("pay_receipt_", ""); order = DB["orders"].get(oid)
        if not order: await update.message.reply_text("❌ Buyurtma topilmadi."); return
        photo_id = update.message.photo[-1].file_id
        order["payment_receipt"] = photo_id; order["payment_status"] = "receipt_sent"; save()
        context.user_data["step"] = None
        label = "🟣 CLICK" if order.get("payment")=="click" else "🔵 PAYME"
        await update.message.reply_text(f"✅ Chek qabul qilindi! #{oid}\n\n{label} to'lovingiz tekshirilmoqda. Do'konchi tasdiqlashi bilan buyurtmangiz tayyorlanishga o'tadi.\n🚴 Yetkazish haqi ({order.get('zone','')}): {order.get('delivery',0):,} so'm — kuryerga naqd berasiz.")
        for shop_id in set(i["shop"] for i in order["items"]):
            shop = DB["shops"][shop_id]
            sub = sum(DB["shops"][i["shop"]]["products"][i["pid"]]["price"] * i["qty"] for i in order["items"] if i["shop"] == shop_id)
            try:
                await context.bot.send_photo(shop["admin"], photo_id, caption=f"💳 TO'LOV CHEKI — Buyurtma #{oid}\nDo'kon: {shop['name']}\nMijoz: {order['phone']}\nManzil: {order['address']} ({order.get('zone','')})\n💰 SIZGA TUSHISHI KERAK: {sub:,} so'm (sizning kartangizga)\nTo'lov: {label}\n\nKartangizni tekshiring — pul tushgan bo'lsa '✅ To'lovni tasdiqlash' ni bosing.")
                await context.bot.send_message(shop["admin"], f"Buyurtma #{oid} to'lovini tasdiqlaysizmi?", reply_markup=pay_kb(oid))
            except: pass
        return
    # --- GUVOHNOMA RASMI: do'konchi ro'yxatdan o'tayotganda ---
    if step == "reg_shop_guv_photo":
        uid = str(update.effective_user.id)
        reg = context.user_data.get("reg", {})
        reg["guvohnoma_photo"] = update.message.photo[-1].file_id
        import re
        slug = re.sub(r"[^a-z0-9_]+", "_", reg.get("name","shop").lower()).strip("_")[:20] or "shop"
        if slug in DB["shops"]: slug = slug + "_" + uid[-4:]
        DB["shops"][slug] = {"name": reg.get("name"), "admin": update.effective_user.id, "phone": reg.get("phone"), "address": reg.get("address"), "delivery": 15000, "active": False, "status": "pending", "guvohnoma_num": reg.get("guvohnoma_num"), "guvohnoma_photo": reg.get("guvohnoma_photo"), "products": {}, "debt": 0, "ratings": []}
        DB["users"][uid]["locked_role"] = "shop"; DB["users"][uid]["role"] = "shop"; save()
        context.user_data["step"] = "reg_shop_click"; context.user_data["reg"] = {"shop_slug": slug}
        await update.message.reply_text(f"✅ Guvohnoma qabul qilindi!\n\n💳 Endi CLICK kartangizni yozing — pul aynan SIZGA tushishi uchun:\nMasalan: 8600 1234 5678 9012\nClick ingiz yo'q bo'lsa, '-' yozing.")
        # Adminga xabar (avvalgidek) - quyida davom etadi\n\n🏪 Do'kon: {reg.get('name')}\n📄 Guvohnoma: {reg.get('guvohnoma_num')}\n\n⏳ Hozir admin guvohnomangizni tekshiryapti.\nTasdiqlansa, sizga xabar keladi va do'koningiz ochiladi.\nTasdiqlanmaguncha mol qo'sha olmaysiz.")
        # Adminga xabar + guvohnoma rasmi
        try:
            await context.bot.send_photo(SUPER_ADMIN, reg.get("guvohnoma_photo"), caption=f"📄 YANGI DO'KON ARIZASI!\n\n🏪 Do'kon: {reg.get('name')}\n👤 Do'konchi: {DB['users'][uid].get('name')} (@{update.effective_user.username or '-'})\nLogin: {DB['users'][uid].get('login')}\n📞 Tel: {reg.get('phone')}\n📍 Manzil: {reg.get('address')}\n📄 Guvohnoma №: {reg.get('guvohnoma_num')}\n\nAdmin panelda tasdiqlang.")
            await context.bot.send_message(SUPER_ADMIN, f"Yuqoridagi arizani tasdiqlash uchun: /start → Admin panel → 📄 Guvohnoma kutayotganlar")
        except: pass
        return
    if isinstance(step, str) and step.startswith("ready_photo_"):
        oid = step.replace("ready_photo_", "")
        order = DB["orders"].get(oid)
        if not order: await update.message.reply_text("❌ Buyurtma topilmadi."); return
        photo_id = update.message.photo[-1].file_id
        order["status"] = "ready"; order["ready_photo"] = photo_id; save()
        context.user_data["step"] = None
        await update.message.reply_text(f"✅ Buyurtma #{oid} tayyor deb belgilandi.\nMijozga rasmingiz bilan xabar ketdi.")
        try: await context.bot.send_photo(order["user_id"], photo_id, caption=f"🎉 BUYURTMANGIZ TAYYOR! #{oid}\n\n✅ Do'konchi buyurtmangizni qadoqlab, tayyorladi.\n📸 Yuqoridagi rasm — aynan sizning buyurtmangiz.\n🚴 Endi kuryer olib chiqishi kutilmoqda.")
        except: pass
        return
    if context.user_data.get("step") != "add_p_photo": return
    uid = update.effective_user.id
    my_shop = [k for k, v in DB["shops"].items() if v.get("admin") == uid]
    if not my_shop: return
    prod = context.user_data.get("prod", {}); prod["photo"] = update.message.photo[-1].file_id
    pid = f"p{len(DB['shops'][my_shop[0]]['products'])+1}_{uid%1000}"
    DB["shops"][my_shop[0]]["products"][pid] = prod; save()
    context.user_data["step"] = None
    await show_main(update, uid, f"✅ Mol qo'shildi: {prod['name']} — {prod['price']:,} so'm")
    await update.message.reply_text("📸 Rasm qabul qilindi, lekin hozir rasm kutilmayapti.\n\nAgar chek / pasport / guvohnoma / tayyor buyurtma rasmini yubormoqchi bo\u2018lsangiz, avval o\u2018sha bo\u2018limdagi tugmani bosing, keyin rasm yuboring.")

async def on_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); data = q.data; uid = q.from_user.id; u = DB["users"].get(str(uid), {})

    # --- ZAXIRA / TIKLASH (faqat admin) — hech kim o'chmaydi, arxivda turadi ---
    if data == "admin_backup":
        try:
            await q.message.reply_text("💾 ZAXIRA HOLATI\n\nBazani fayl qilib yuklab olish uchun botga yoz:\n/export\n\nYoki zaxira holatini ko'rish uchun:\n/backup")
        except: pass
        return
    if data == "admin_restore_help":
        await q.message.reply_text("📥 TIKLASH QANDAY BO'LADI:\n\n1. Avval /export bilan olgan zaxira faylingni top (termiz_baza_zaxira.json)\n2. Shu faylni botga yubor (fayl qilib)\n3. Bot so'raydi: ✅ HA, TIKLA ni bos\n\n⚠️ Tiklashdan oldin hozirgi baza ham db_before_restore.json ga saqlanadi — adashsang ham yo'qolmaydi.")
        return
    if data == "restore_yes":
        try:
            new_db = json.loads(context.user_data.get("restore_data", b"{}"))
            with open("db_before_restore.json", "w", encoding="utf-8") as f: json.dump(DB, f, ensure_ascii=False, indent=2)
            DB.clear(); DB.update(new_db)
            DB.setdefault("archive", {}); DB.setdefault("settings", {})
            save()
            await q.message.reply_text(f"✅ TIKLANDI!\n👥 Odamlar: {len(DB.get('users', {}))}\n🏪 Do'konlar: {len(DB.get('shops', {}))}\n📦 Buyurtmalar: {len(DB.get('orders', {}))}\n🗄️ Arxiv: {len(DB.get('archive', {}))}")
        except Exception as e:
            await q.message.reply_text(f"❌ Tiklashda xato: {e}")
        return
    if data == "restore_no":
        await q.message.reply_text("❌ Tiklash bekor qilindi."); return
    # Auth tugmalari - hamma uchun ochiq
    if data == "auth_login":
        context.user_data["step"] = "auth_login_login"
        await q.message.reply_text("🔑 KIRISH\n\nLoginingizni yozing:"); return
    if data == "auth_register":
        context.user_data["step"] = "auth_reg_role"
        await q.message.reply_text("📝 RO'YXATDAN O'TISH\n\nKim bo'lib kirasiz? Raqam yozing:\n1 — 🛍️ Mijoz\n2 — 🏪 Do'konchi\n3 — 🚴 Kuryer"); return
    if data == "logout":
        context.user_data["authed"] = False; context.user_data["auth_role"] = None; context.user_data["step"] = None
        await q.message.reply_text("🚪 Chiqdingiz. Qaytadan kirish uchun /start ni bosing.", reply_markup=auth_kb()); return
    if data == "change_pass":
        context.user_data["step"] = "change_pass_old"
        await q.message.reply_text("🔐 PAROLNI O'ZGARTIRISH\n\nEski parolni yozing:"); return
    # Qolgan hamma tugma - faqat kirganlarga
    if not is_authed(context, uid):
        await ask_login(update, context, "🔒 Avval kirishingiz kerak:"); return
    if data.startswith("setrole_"):
        role = data.replace("setrole_", "")
        if uid != SUPER_ADMIN and role == "admin":
            await q.message.reply_text("⛔ Admin panel faqat bot egasiga."); return
        DB["users"][str(uid)]["role"] = role; save(); await show_main(update, uid, f"Rol: {role} ✅"); return
    if data == "back_main": await show_main(update, uid, "Asosiy menyu:"); return
    if data == "register_shop": await register_shop(update, context); return
    if data == "register_courier": await register_courier(update, context); return
    if data == "skip_location":
        context.user_data["order_location"] = None; context.user_data["step"] = "order_phone"
        await q.message.reply_text("📞 Telefon raqamingizni yozing:", reply_markup=ReplyKeyboardRemove()); return
    if data == "client_shops":
        if not DB["shops"]: await q.message.reply_text("Hozircha do'kon yo'q."); return
        kb = []
        for k, v in DB["shops"].items():
            if not v.get("active") or v.get("status") == "pending": continue
            a = avg(v.get("ratings", []))
            kb.append([InlineKeyboardButton(f"🏪 {v['name']}{' ⭐ '+format(a,'.1f') if a else ''} — {v['address']}", callback_data=f"shop_{k}")])
        kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")])
        try: await q.message.delete()
        except: pass
        await q.message.reply_text("🛍️ Do'konni tanlang:", reply_markup=InlineKeyboardMarkup(kb)); return
    if data.startswith("shop_") and not data.startswith(("shop_orders", "shop_panel", "shop_stats", "shop_my_rating", "shop_cards")):
        sid = data.replace("shop_", ""); shop = DB["shops"].get(sid)
        if not shop:
            await q.message.reply_text("❌ Bu do'kon topilmadi — ehtimol o'chirilgan. Boshqa do'konni tanlang.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Do'konlar", callback_data="client_shops")]])); return
        a = avg(shop.get("ratings", []))
        head = f"🏪 {shop['name']}\n⭐ Reyting: {a:.1f} / 5 ({len(shop.get('ratings', []))} ta baho)\n📍 {shop['address']}\n📞 {shop['phone']}\n\n" if a else f"🏪 {shop['name']}\n📍 {shop['address']}\n📞 {shop['phone']}\n\n"
        if not shop["products"]:
            await q.message.reply_text(head + "Hozircha mol yo'q."); return
        kb = [[InlineKeyboardButton(f"{p['name']} — {p['price']:,} so'm", callback_data=f"prod_{sid}_{pid}")] for pid, p in shop["products"].items()]
        kb.append([InlineKeyboardButton("⬅️ Do'konlar", callback_data="client_shops")])
        try: await q.message.delete()
        except: pass
        await q.message.reply_text(head + "Molni tanlang:", reply_markup=InlineKeyboardMarkup(kb)); return
    if data.startswith("prod_"):
        _, sid, pid = data.split("_", 2); p = DB["shops"][sid]["products"][pid]
        kb = [[InlineKeyboardButton(f"📏 {s}", callback_data=f"size_{sid}_{pid}_{s}")] for s in p.get("sizes", ["M"])]
        kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data=f"shop_{sid}")])
        try: await context.bot.send_photo(uid, p.get("photo", ""), caption=f"👕 {p['name']}\n💰 {p['price']:,} so'm\n🎨 Rang: {', '.join(p.get('colors', []))}\n📦 Qoldiq: {p.get('stock', 0)} ta\n\nRazmer tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        except: await q.message.reply_text(f"👕 {p['name']}\n💰 {p['price']:,} so'm\nRazmer tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        return
    if data.startswith("size_"):
        _, sid, pid, size = data.split("_", 3); p = DB["shops"][sid]["products"][pid]
        kb = [[InlineKeyboardButton(f"🎨 {c}", callback_data=f"color_{sid}_{pid}_{size}_{c}")] for c in p.get("colors", ["Qora"])]
        await q.message.reply_text(f"👕 {p['name']} — Razmer: {size}\nRang tanlang:", reply_markup=InlineKeyboardMarkup(kb)); return
    if data.startswith("color_"):
        parts = data.split("_", 4); sid, pid, size, color = parts[1], parts[2], parts[3], parts[4]
        DB["users"][str(uid)].setdefault("cart", []).append({"shop": sid, "pid": pid, "size": size, "color": color, "qty": 1}); save()
        await q.message.reply_text(f"✅ Savatga qo'shildi!\n{DB['shops'][sid]['products'][pid]['name']} — {size} / {color}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Savatga o'tish", callback_data="client_cart")],[InlineKeyboardButton("🛍️ Do'konlar", callback_data="client_shops")]])); return
    if data == "client_cart":
        cart = u.get("cart", [])
        if not cart: await q.message.reply_text("🛒 Savat bo'sh."); return
        txt = "🛒 Savatingiz:\n\n"; total = 0
        for i, it in enumerate(cart):
            p = DB["shops"][it["shop"]]["products"][it["pid"]]; total += p["price"]
            txt += f"{i+1}. {p['name']} — {it['size']} / {it['color']} — {p['price']:,} so'm\n"
        txt += f"\nJami mol: {total:,} so'm\n🚴 Yetkazish haqi manzilga qarab: shahar ichi {get_settings()['delivery_city']:,} / tashqaris {get_settings()['delivery_outside']:,} / uzoq {get_settings()['delivery_far']:,} so'm — keyingi qadamda tanlaysiz"
        await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Buyurtma berish", callback_data="checkout")],[InlineKeyboardButton("🗑️ Savatni tozalash", callback_data="clear_cart")],[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]])); return
    if data == "clear_cart": DB["users"][str(uid)]["cart"] = []; save(); await q.message.reply_text("Savat tozalandi."); return
    if data == "checkout":
        context.user_data["step"] = "order_addr"; await q.message.reply_text("📍 Yetkazish manzilini yozing:\nMasalan: Termiz, 5-mikrorayon, 12-uy"); return
    if data == "client_my":
        my = [(k, v) for k, v in DB["orders"].items() if v["user_id"] == uid]
        if not my: await q.message.reply_text("Buyurtmangiz yo'q."); return
        txt = "📦 Buyurtmalarim:\n\n" + "\n".join([f"#{k} — {v['total']+v['delivery']:,} so'm — {v['status']}" for k, v in my])
        await q.message.reply_text(txt); return
    if data == "client_balance": await q.message.reply_text(f"💰 Hisobingiz: {u.get('balance',0):,} so'm"); return
    if data.startswith("rate_shop_"):
        parts = data.split("_"); oid = parts[2]; star = int(parts[3])
        o = DB["orders"].get(oid)
        if not o or o.get("shop_rating") is not None: await q.message.reply_text("Bu buyurtmaga allaqachon baho berilgan."); return
        o["shop_rating"] = star; shop_id = o["items"][0]["shop"]
        DB["shops"][shop_id].setdefault("ratings", []).append(star); save()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{'⭐'*i}", callback_data=f"rate_courier_{oid}_{i}")] for i in [5, 4, 3, 2, 1]])
        await q.message.reply_text(f"✅ Do'konga baho: {star} ⭐ — rahmat!\n\nEndi KURYERGA baho bering (1-5):", reply_markup=kb); return
    if data.startswith("rate_courier_"):
        parts = data.split("_"); oid = parts[2]; star = int(parts[3])
        o = DB["orders"].get(oid)
        if not o or o.get("courier_rating") is not None: await q.message.reply_text("Bu buyurtmaga allaqachon baho berilgan."); return
        o["courier_rating"] = star
        if o.get("courier"):
            cu = DB["users"].get(str(o["courier"]), {}); cu.setdefault("ratings", []).append(star)
        save()
        await q.message.reply_text(f"✅ Rahmat! Kuryerga baho: {star} ⭐\nBahoyingiz saqlandi."); return
    if data == "shop_panel":
        my = [v for v in DB["shops"].values() if v.get("admin") == uid]
        if not my: await q.message.reply_text("Do'koningiz yo'q."); return
        s = my[0]; a = avg(s.get("ratings", []))
        status_txt = "⏳ Tasdiqlanmoqda — admin guvohnomani tekshiryapti" if s.get("status") == "pending" else ("✅ Tasdiqlangan" if s.get("status") == "approved" else f"Holati: {s.get('status')}")
        await q.message.reply_text(f"🏪 {s['name']}\n{status_txt}\n📄 Guvohnoma №: {s.get('guvohnoma_num','—')}\n⭐ Reyting: {a:.1f} / 5 ({len(s.get('ratings', []))} ta baho)\n📍 {s['address']}\n📞 {s['phone']}\n📦 Mol soni: {len(s['products'])}\n💸 Komissiya qarzi: {s.get('debt',0):,} so'm", reply_markup=main_kb("shop")); return
    if data == "shop_my_rating":
        my = [v for v in DB["shops"].values() if v.get("admin") == uid]
        if not my: return
        s = my[0]; a = avg(s.get("ratings", []))
        txt = f"⭐ SIZNING REYTINGINGIZ\n\n🏪 {s['name']}\nO'rtacha: {a:.1f} / 5\nJami baho: {len(s.get('ratings', []))} ta\n\n" + "\n".join([f"{'⭐'*i} — {s.get('ratings', []).count(i)} ta" for i in [5, 4, 3, 2, 1]])
        await q.message.reply_text(txt); return
    if data == "shop_cards":
        my = [v for v in DB["shops"].values() if v.get("admin") == uid]
        if not my: await q.message.reply_text("Do'koningiz yo'q."); return
        s = my[0]
        await q.message.reply_text(f"💳 KARTALARIM — {s['name']}\n\n🟣 Click: {s.get('click_card') or 'qo‘yilmagan'}\n🔵 Payme: {s.get('payme_card') or 'qo‘yilmagan'}\n\nPul to'g'ridan-to'g'ri shu kartalarga tushadi. O'zgartirish uchun Click kartangizni yozing (o'chirish uchun '-' yozing):")
        context.user_data["step"] = "shop_cards_click"; return
    if data.startswith("confirm_pay_"):
        oid = data.replace("confirm_pay_", ""); o = DB["orders"].get(oid)
        if not o: return
        if o.get("payment_status") == "paid": await q.message.reply_text("Bu to'lov allaqachon tasdiqlangan."); return
        o["payment_status"] = "paid"; o["status"] = "new"; save()
        for item in o["items"]: DB["shops"][item["shop"]]["debt"] = DB["shops"][item["shop"]].get("debt", 0) + get_commission()
        save()
        await q.message.reply_text(f"✅ To'lov tasdiqlandi! Buyurtma #{oid} endi 'Yangi buyurtmalar' da. Qabul qiling.")
        try: await context.bot.send_message(o["user_id"], f"✅ TO'LOVINGIZ TASDIQLANDI! #{oid}\n\n💳 To'lov qabul qilindi, rahmat! Endi do'konchi buyurtmangizni tayyorlayapti.")
        except: pass
        return
    if data.startswith("reject_pay_"):
        oid = data.replace("reject_pay_", ""); o = DB["orders"].get(oid)
        if not o: return
        o["payment_status"] = "rejected"; save()
        await q.message.reply_text(f"❌ Buyurtma #{oid} to'lovi rad etildi. Mijozga xabar ketdi.")
        try: await context.bot.send_message(o["user_id"], f"❌ TO'LOV TOPILMADI! #{oid}\n\n💳 Chekingizdagi pul topilmadi yoki chek noto'g'ri. Iltimos, qaytadan to'lang yoki do'konchi bilan bog'laning. /start bosing.")
        except: pass
        return
    if data == "courier_balance":
        await q.message.reply_text(f"💰 HISOBIM\n\n🚴 Yetkazgan: {u.get('delivered',0)} ta\n🚴 Yetkazishdan topganingiz: {u.get('earned_delivery',0):,} so'm\n\nHar bir yetkazgan buyurtmangiz uchun yetkazish haqi sizniki."); return
    if data == "add_product":
        my = [v for v in DB["shops"].values() if v.get("admin") == uid]
        if my and my[0].get("status") == "pending":
            await q.message.reply_text("⏳ Do'koningiz hali tasdiqlanmagan!\n\nAdmin guvohnomangizni tekshiryapti. Tasdiqlangach mol qo'sha olasiz."); return
        if my and my[0].get("status") == "rejected":
            await q.message.reply_text("❌ Arizangiz rad etilgan. Admin bilan bog'laning yoki qaytadan ro'yxatdan o'ting."); return
        context.user_data["step"] = "add_p_name"; await q.message.reply_text("➕ Mol qo'shish — 1/6\n\nMol nomini yozing:"); return
    if data.startswith("p_cat_"):
        cat = CATEGORIES[int(data.replace("p_cat_", ""))]
        context.user_data["prod"]["category"] = cat; context.user_data["step"] = "add_p_sizes"
        await q.message.reply_text(f"Kategoriya: {cat}\n\n📏 Razmerlarni vergul bilan yozing:"); return
    if data == "my_products":
        my = [v for v in DB["shops"].values() if v.get("admin") == uid]
        if not my or not my[0]["products"]: await q.message.reply_text("Hozircha mol yo'q."); return
        txt = "👕 Mollarim:\n\n" + "\n".join([f"{p['name']} — {p['price']:,} so'm — {p.get('stock',0)} ta" for p in my[0]["products"].values()])
        await q.message.reply_text(txt); return
    if data == "shop_orders":
        my_shop0 = [k for k, v in DB["shops"].items() if v.get("admin") == uid]
        waiting = [(k, v) for k, v in DB["orders"].items() if any(i["shop"] in my_shop0 for i in v["items"]) and v["status"] == "awaiting_payment"]
        for k, v in waiting:
            label = "🟣 CLICK" if v.get("payment")=="click" else ("🔵 PAYME" if v.get("payment")=="payme" else "💳")
            txt_w = f"⏳ TO'LOV KUTILMOQDA — Buyurtma #{k}\nManzil: {v['address']} ({v.get('zone','')})\nTel: {v['phone']}\nMol: {v['total']:,} + Yetkazish: {v['delivery']:,} = {v['total']+v['delivery']:,} so'm\nTo'lov: {label} — {v.get('payment_status')}"
            if v.get("payment_receipt"):
                try: await context.bot.send_photo(uid, v["payment_receipt"], caption=txt_w)
                except: pass
                await q.message.reply_text(txt_w, reply_markup=pay_kb(k))
            else: await q.message.reply_text(txt_w + "\n\nMijoz hali chek yubormadi.")
        # quyida eski shop_orders davom etadi
        my_shop = [k for k, v in DB["shops"].items() if v.get("admin") == uid]
        orders = [(k, v) for k, v in DB["orders"].items() if any(i["shop"] in my_shop for i in v["items"]) and v["status"] == "new"]
        if not orders:
            if waiting: return
            await q.message.reply_text("Yangi buyurtma yo'q."); return
        for k, v in orders:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Qabul qilish", callback_data=f"accept_{k}")]])
            await q.message.reply_text(f"📦 Buyurtma #{k}\nManzil: {v['address']}\nTel: {v['phone']}\nSumma: {v['total']+v['delivery']:,} so'm", reply_markup=kb)
            if v.get("location"):
                try: await context.bot.send_location(uid, v["location"]["lat"], v["location"]["lon"])
                except: pass
        return
    if data.startswith("accept_"):
        oid = data.replace("accept_", ""); DB["orders"][oid]["status"] = "accepted"; save()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("👨‍🍳 Tayyorlayapman — boshlash", callback_data=f"preparing_{oid}")]])
        await q.message.reply_text(f"✅ Buyurtma #{oid} qabul qilindi.\n\nEndi tayyorlashni boshlash uchun tugmani bosing:", reply_markup=kb)
        try: await context.bot.send_message(DB["orders"][oid]["user_id"], f"✅ Buyurtmangiz #{oid} do'kon tomonidan qabul qilindi!")
        except: pass
        return
    if data.startswith("preparing_"):
        oid = data.replace("preparing_", ""); DB["orders"][oid]["status"] = "preparing"; save()
        await q.message.reply_text(f"👨‍🍳 Buyurtma #{oid} — TAYYORLANAYAPTI\n\n" + PACKAGING_GUIDE + f"\n\n📸 Qadoqlab bo'lgach, shu chatga buyurtmaning RASMINI yuboring.")
        context.user_data["step"] = f"ready_photo_{oid}"
        try: await context.bot.send_message(DB["orders"][oid]["user_id"], f"👨‍🍳 BUYURTMANGIZ TAYYORLANAYAPTI! #{oid}\n\nDo'konchi buyurtmangizni hozir tayyorlayapti, yaxshilab qadoqlayapti.")
        except: pass
        return
    if data == "shop_stats":
        my = [v for v in DB["shops"].values() if v.get("admin") == uid]
        if not my: return
        cnt = sum(1 for o in DB["orders"].values() if any(i["shop"] in [k for k, v in DB["shops"].items() if v.get("admin")==uid] for i in o["items"]))
        await q.message.reply_text(f"📊 Statistika\nJami buyurtma: {cnt} ta\nKomissiya qarzi: {my[0].get('debt',0):,} so'm"); return
    if data == "courier_panel":
        st = u.get("courier_status", "approved" if u.get("courier_registered") else "pending")
        st_txt = "✅ Tasdiqlangan" if st == "approved" else "⏳ Tasdiqlanmoqda — admin pasportni tekshiryapti"
        await q.message.reply_text(f"🚴 Kuryer panel\n{st_txt}\n🪪 Pasport: {u.get('passport_num','—')}\nOnline: {u.get('online')}\nYetkazgan: {u.get('delivered',0)} ta", reply_markup=main_kb("courier")); return
    if data == "courier_my_rating":
        a = avg(u.get("ratings", []))
        txt = f"⭐ SIZNING REYTINGINGIZ\n\n🚴 {u.get('name','')}\nO'rtacha: {a:.1f} / 5\nJami baho: {len(u.get('ratings', []))} ta\n\n" + "\n".join([f"{'⭐'*i} — {u.get('ratings', []).count(i)} ta" for i in [5, 4, 3, 2, 1]])
        await q.message.reply_text(txt); return
    if data == "courier_toggle":
        if u.get("courier_status") == "pending":
            await q.message.reply_text("⏳ Hali tasdiqlanmagansiz!\n\nAdmin pasportingizni tekshiryapti. Tasdiqlangach ONLINE bo'lib buyurtma ola olasiz."); return
        u["online"] = not u.get("online", False); save(); await q.message.reply_text(f"{'🟢 ONLINE' if u['online'] else '🔴 OFFLINE'}"); return
    if data == "courier_list":
        if u.get("courier_status") == "pending":
            await q.message.reply_text("⏳ Hali tasdiqlanmagansiz!\n\nAdmin pasportingizni tekshiryapti. Tasdiqlangach buyurtmalarni ko'ra olasiz."); return
        free = [(k, v) for k, v in DB["orders"].items() if v["status"] == "ready" and not v.get("courier")]
        if not free: await q.message.reply_text("Bo'sh buyurtma yo'q."); return
        for k, v in free:
            _dtx = "🎁 Yetkazish BEPUL — bu buyurtmadan xizmat haqi yo'q" if v.get('delivery',0)==0 else f"🚴 Sizning xizmat haqingiz: {v['delivery']:,} so'm"
            await q.message.reply_text(f"📦 #{k} — {v['address']} ({v.get('zone','')})\n✅ Tayyor, qadoqlangan\nMol: {v['total']:,} + {_dtx}\nJami: {v['total']+v['delivery']:,} so'm", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚴 Olish", callback_data=f"take_{k}")]]))
            if v.get("location"):
                try: await context.bot.send_location(uid, v["location"]["lat"], v["location"]["lon"])
                except: pass
        return
    if data.startswith("take_"):
        if u.get("courier_status") == "pending":
            await q.message.reply_text("⏳ Hali tasdiqlanmagansiz! Admin pasportingizni tekshiryapti."); return
        oid = data.replace("take_", ""); DB["orders"][oid]["courier"] = uid; DB["orders"][oid]["status"] = "onway"; save()
        c = DB["users"].get(str(uid), {}); c_phone = c.get("phone") or "Bot orqali bog'laning"; c_name = c.get("name") or "Kuryer"
        o = DB["orders"][oid]
        _dtx2 = "🎁 Yetkazish BEPUL — bu buyurtmadan xizmat haqi yo'q." if o.get('delivery',0)==0 else f"🚴 Sizning xizmat haqingiz: {o['delivery']:,} so'm — mijozdan naqd olasiz."
        await q.message.reply_text(f"🚴 Buyurtma #{oid} ni oldingiz!\n\n📍 Mijoz manzili: {o['address']} ({o.get('zone','')})\n{_dtx2}\n\n📞 Mijoz telefoni: {o['phone']}\n\nDo'kondan paketni olib, mijozga olib boring.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Yetkazdim", callback_data=f"delivered_{oid}")]]))
        if o.get("location"):
            try: await context.bot.send_location(uid, o["location"]["lat"], o["location"]["lon"])
            except: pass
        try: await context.bot.send_message(o["user_id"], f"🚴 KURYER YO'LGA CHIQDI! #{oid}\n\nKuryer: {c_name}\n📞 Kuryer telefoni: {c_phone}\n📦 Buyurtmangiz hozir sizga olib kelinmoqda.")
        except: pass
        return
    if data.startswith("delivered_"):
        oid = data.replace("delivered_", ""); o = DB["orders"].get(oid)
        if not o: return
        o["status"] = "delivered"; save()
        cu = DB["users"].get(str(uid), {}); cu["delivered"] = cu.get("delivered", 0) + 1; cu["earned_delivery"] = cu.get("earned_delivery", 0) + o.get("delivery", 0); save()
        await q.message.reply_text(f"✅ Buyurtma #{oid} yetkazildi deb belgilandi. Rahmat!\n🚴 Sizning xizmat haqingiz: {o.get('delivery',0):,} so'm — jami topganingiz: {cu.get('earned_delivery',0):,} so'm.")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{'⭐'*i}", callback_data=f"rate_shop_{oid}_{i}")] for i in [5, 4, 3, 2, 1]])
        try: await context.bot.send_message(o["user_id"], f"✅ BUYURTMANGIZ YETKAZILDI! #{oid}\n\n⭐ DO'KONGA BAHO BERING (1-5):", reply_markup=kb)
        except: pass
        return
    if data == "admin_settings":
        s = get_settings()
        _free = s.get('free_delivery', 0)
        _free_tx = "o'chirilgan (0)" if not _free else f"{_free:,} so'mdan oshsa yetkazish BEPUL"
        await q.message.reply_text(f"⚙️ NARXLAR — HOZIRGI HOLAT\n\n🏙️ Shahar ichi yetkazish: {s['delivery_city']:,} so'm\n🏡 Shahar tashqaris yetkazish: {s['delivery_outside']:,} so'm\n🛣️ Uzoq tuman yetkazish: {s['delivery_far']:,} so'm\n💸 Komissiya (har bir buyurtmadan do'konchidan): {s['commission']:,} so'm\n🎁 Bepul yetkazish chegarasi: {_free_tx}\n❌ Minimal buyurtma summasi: YO'Q — xohlagan summa bilan buyurtma berish mumkin.\n\nO'zgartirmoqchi bo'lgan narxni bosing, keyin yangi narxni yozing.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏙️ Shahar ichi narxini o'zgartirish", callback_data="admin_set_city")],[InlineKeyboardButton("🏡 Shahar tashqaris narxini o'zgartirish", callback_data="admin_set_outside")],[InlineKeyboardButton("🛣️ Uzoq tuman narxini o'zgartirish", callback_data="admin_set_far")],[InlineKeyboardButton("💸 Komissiyani o'zgartirish", callback_data="admin_set_commission")],[InlineKeyboardButton("🎁 Bepul yetkazish chegarasini o'zgartirish", callback_data="admin_set_free")]])); return
    if data == "admin_set_city":
        await q.message.reply_text(f"🏙️ Shahar ichi yetkazish narxi hozir: {get_settings()['delivery_city']:,} so'm\n\nYangi narxni yozing (faqat raqam, masalan: 20000):"); context.user_data["step"] = "admin_set_city"; return
    if data == "admin_set_outside":
        await q.message.reply_text(f"🏡 Shahar tashqaris yetkazish narxi hozir: {get_settings()['delivery_outside']:,} so'm\n\nYangi narxni yozing (faqat raqam, masalan: 35000):"); context.user_data["step"] = "admin_set_outside"; return
    if data == "admin_set_far":
        await q.message.reply_text(f"🛣️ Uzoq tuman yetkazish narxi hozir: {get_settings()['delivery_far']:,} so'm\n\nYangi narxni yozing (faqat raqam, masalan: 60000):"); context.user_data["step"] = "admin_set_far"; return
    if data == "admin_set_free":
        _f = get_settings().get('free_delivery', 0)
        await q.message.reply_text(f"🎁 Bepul yetkazish chegarasi hozir: {'o‘chirilgan (0)' if not _f else f'{_f:,} so‘m'}\n\nYangi chegarani yozing (faqat raqam):\nMasalan: 500000 — demak savat 500 000 so'mdan oshsa, yetkazish BEPUL bo'ladi.\nO'chirish uchun: 0 yozing."); context.user_data["step"] = "admin_set_free"; return
    if data == "admin_set_commission":
        await q.message.reply_text(f"💸 Komissiya hozir: {get_settings()['commission']:,} so'm (har bir buyurtmadan)\n\nYangi komissiyani yozing (faqat raqam, masalan: 3000):"); context.user_data["step"] = "admin_set_commission"; return
    if data == "auth_forgot":
        await q.message.reply_text("🔐 PAROLNI UNUTDINGIZMI?\n\nVahimaga tushmang — ma'lumotingiz o'chmaydi!\n\n📩 Adminga (bot egasiga) yozing va ayting:\n• Ismingiz\n• Telefon raqamingiz\n• Eski loginingiz (eslasangiz)\n\nAdmin sizni arxivdan topib, YANGI PAROL beradi.\nKeyin botda '🔑 Kirish' ni bosib, eski loginingiz + yangi parol bilan kirasiz.\n\n🗄️ Botni o'chirgan bo'lsangiz ham ma'lumotingiz admin panelda turadi — qayta ro'yxatdan o'tishingiz shart emas."); return
    if data == "admin_archive":
        _all = list(DB.get("archive", {}).items())
        if not _all: await q.message.reply_text("🗄️ Arxiv bo'sh — hali hech kim ro'yxatdan o'tmagan."); return
        await q.message.reply_text(f"🗄️ ARXIV — jami {len(_all)} kishi\n\nBu yerdagi ma'lumotlar O'CHMAYDI: odam botni o'chirsa ham, bloklasa ham shu yerda turadi.\nQidirish uchun pastdagi tugmani bosing yoki ro'yxatdan birini tanlang:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 Telefon / login / ism bilan qidirish", callback_data="admin_archive_search")]]))
        for _uid, _a in _all[-20:]:
            await q.message.reply_text(f"{'🏪' if _a.get('shops') else ('🚴' if _a.get('courier_registered') else '🛍️')} {_a.get('name','?')} — login: {_a.get('login') or '—'} — 📞 {_a.get('phone') or '—'} — buyurtma: {_a.get('orders_count',0)} ta", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📂 Ochish / Parol tiklash", callback_data=f"admin_restore_{_uid}")]]))
        return
    if data == "admin_archive_search":
        await q.message.reply_text("🔎 Qidirish: telefon raqami, login yoki ismni yozing:\nMasalan: 901234567 yoki farrux"); context.user_data["step"] = "admin_archive_search"; return
    if data.startswith("admin_restore_"):
        _uid = data.replace("admin_restore_", ""); _a = _arch(_uid)
        if not _a: await q.message.reply_text("❌ Arxivda topilmadi."); return
        await q.message.reply_text(_arch_text(_a), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔑 Yangi parol berish", callback_data=f"admin_setpass_{_uid}")],[InlineKeyboardButton("✏️ Loginni o'zgartirish", callback_data=f"admin_setlogin_{_uid}")]])); return
    if data.startswith("admin_setpass_"):
        _uid = data.replace("admin_setpass_", ""); _a = _arch(_uid)
        await q.message.reply_text(f"🔑 Yangi parol berish — {_a.get('name','?')} (login: {_a.get('login') or '—'})\n\nYangi parolni yozing (kamida 4 ta belgi):"); context.user_data["step"] = f"admin_setpass_{_uid}"; return
    if data.startswith("admin_setlogin_"):
        _uid = data.replace("admin_setlogin_", ""); _a = _arch(_uid)
        await q.message.reply_text(f"✏️ Loginni o'zgartirish — {_a.get('name','?')} (eski login: {_a.get('login') or '—'})\n\nYangi loginni yozing (kamida 3 ta belgi, lotin harflarda):"); context.user_data["step"] = f"admin_setlogin_{_uid}"; return
    if data == "admin_pending":
        pend = [(k, v) for k, v in DB["shops"].items() if v.get("status") == "pending"]
        pend_c = [(k, v) for k, v in DB["users"].items() if v.get("courier_registered") and v.get("courier_status") == "pending"]
        if not pend and not pend_c: await q.message.reply_text("✅ Kutayotgan ariza yo'q — hamma hujjat ko'rib chiqilgan."); return
        for ck, cv in pend_c:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_courier_{ck}")],[InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_courier_{ck}")]])
            await q.message.reply_text(f"🪪 KURYER ARIZASI — {cv.get('name')}\nLogin: {cv.get('login')}\n📞 {cv.get('phone')}\n🪪 Pasport: {cv.get('passport_num')}", reply_markup=kb)
            if cv.get("passport_photo"):
                try: await context.bot.send_photo(uid, cv["passport_photo"], caption=f"🪪 Pasport rasmi — {cv.get('name')} ({cv.get('passport_num')})")
                except: pass
        for k, v in pend:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_shop_{k}")],[InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_shop_{k}")]])
            await q.message.reply_text(f"📄 ARIZA — {v['name']}\n👤 {DB['users'].get(str(v.get('admin')), {}).get('name')} | Login: {DB['users'].get(str(v.get('admin')), {}).get('login')}\n📞 {v['phone']}\n📍 {v['address']}\n📄 Guvohnoma №: {v.get('guvohnoma_num')}", reply_markup=kb)
            if v.get("guvohnoma_photo"):
                try: await context.bot.send_photo(uid, v["guvohnoma_photo"], caption=f"📄 Guvohnoma rasmi — {v['name']} (№ {v.get('guvohnoma_num')})")
                except: pass
        return
    if data.startswith("approve_courier_"):
        cuid = data.replace("approve_courier_", ""); cu = DB["users"].get(cuid)
        if not cu: return
        cu["courier_status"] = "approved"; save()
        await q.message.reply_text(f"✅ Kuryer {cu.get('name')} tasdiqlandi! Endi buyurtma ola oladi.")
        try: await context.bot.send_message(int(cuid), f"🎉 TABRIKLAYMIZ!\n\n🚴 Kuryerligingiz tasdiqlandi!\n🪪 Pasport: {cu.get('passport_num')}\n\nEndi ONLINE bo'lib buyurtma ola olasiz!")
        except: pass
        return
    if data.startswith("reject_courier_"):
        cuid = data.replace("reject_courier_", ""); cu = DB["users"].get(cuid)
        if not cu: return
        cname = cu.get("name")
        cu["courier_registered"] = False; cu["courier_status"] = "rejected"; cu["role"] = "client"; cu["locked_role"] = None; save()
        await q.message.reply_text(f"❌ Kuryer {cname} rad etildi.")
        try: await context.bot.send_message(int(cuid), f"❌ Arizangiz rad etildi.\n\n🚴 Kuryerlik arizasi tasdiqlanmadi — pasport tasdiqlanmadi / rasm o'qilmadi.\nPasportingizni to'g'rilab, qaytadan ro'yxatdan o'ting — /start → Ro'yxatdan o'tish → Kuryer.")
        except: pass
        return
    if data.startswith("approve_shop_"):
        slug = data.replace("approve_shop_", ""); s = DB["shops"].get(slug)
        if not s: return
        s["status"] = "approved"; s["active"] = True; save()
        await q.message.reply_text(f"✅ {s['name']} tasdiqlandi! Endi bu do'kon mijozlarga ko'rinadi.")
        try: await context.bot.send_message(s["admin"], f"🎉 TABRIKLAYMIZ!\n\n🏪 Do'koningiz tasdiqlandi: {s['name']}\n📄 Guvohnoma №: {s.get('guvohnoma_num')}\n\nEndi mol qo'shishingiz va sotishingiz mumkin!\n'➕ Mol qo'shish' ni bosing.")
        except: pass
        return
    if data.startswith("reject_shop_"):
        slug = data.replace("reject_shop_", ""); s = DB["shops"].get(slug)
        if not s: return
        admin_id = s.get("admin"); shop_name = s["name"]
        del DB["shops"][slug]
        if str(admin_id) in DB["users"]:
            DB["users"][str(admin_id)]["role"] = "client"; DB["users"][str(admin_id)]["locked_role"] = None
        save()
        await q.message.reply_text(f"❌ {shop_name} rad etildi.")
        try: await context.bot.send_message(admin_id, f"❌ Arizangiz rad etildi.\n\n🏪 Do'kon: {shop_name}\n\nSababi: guvohnoma tasdiqlanmadi / rasm o'qilmadi.\nGuvohnomangizni to'g'rilab, qaytadan ro'yxatdan o'ting — /start → Ro'yxatdan o'tish → Do'konchi.")
        except: pass
        return
    if data == "admin_shops":
        txt = "🏪 Do'konlar:\n\n" + "\n".join([f"{v['name']} — {v['phone']} — ⭐ {avg(v.get('ratings',[])):.1f} — Qarz: {v.get('debt',0):,} so'm" for v in DB["shops"].values()]) or "Do'kon yo'q"
        await q.message.reply_text(txt); return
    if data == "admin_ratings":
        txt = "⭐ REYTINGLAR — HAMMANIKI\n\n🏪 DO'KONLAR:\n"
        if not DB["shops"]: txt += "Do'kon yo'q\n"
        for v in sorted(DB["shops"].values(), key=lambda x: avg(x.get("ratings", [])), reverse=True):
            a = avg(v.get("ratings", []))
            txt += f"{v['name']} — {'⭐'*int(round(a)) if a else '—'} {a:.1f} / 5 ({len(v.get('ratings', []))} ta baho)\n"
        txt += "\n🚴 KURYERLAR:\n"
        couriers = [v for v in DB["users"].values() if v.get("courier_registered")]
        if not couriers: txt += "Kuryer yo'q\n"
        for v in sorted(couriers, key=lambda x: avg(x.get("ratings", [])), reverse=True):
            a = avg(v.get("ratings", []))
            txt += f"{v.get('name','?')} — {'⭐'*int(round(a)) if a else '—'} {a:.1f} / 5 ({len(v.get('ratings', []))} ta baho) — Yetkazgan: {v.get('delivered',0)} ta\n"
        bad = [v for v in DB["shops"].values() if avg(v.get("ratings", [])) and avg(v.get("ratings", [])) < 3]
        if bad: txt += "\n⚠️ DIQQAT — reytingi 3 dan past:\n" + "\n".join([f"• {v['name']} — {avg(v.get('ratings',[])):.1f}" for v in bad])
        await q.message.reply_text(txt); return
    if data == "admin_orders":
        txt = "📦 Buyurtmalar:\n\n" + "\n".join([f"#{k} — {v['total']+v['delivery']:,} — {v['status']} — Do'kon ⭐ {v.get('shop_rating','—')} | Kuryer ⭐ {v.get('courier_rating','—')}" for k, v in DB["orders"].items()]) or "Buyurtma yo'q"
        await q.message.reply_text(txt); return
    if data == "admin_debt":
        total = sum(v.get("debt", 0) for v in DB["shops"].values())
        txt = f"💸 Jami komissiya qarzi: {total:,} so'm\n\n" + "\n".join([f"{v['name']}: {v.get('debt',0):,} so'm" for v in DB["shops"].values()])
        await q.message.reply_text(txt); return
    if data == "admin_users": await q.message.reply_text(f"👥 Mijozlar: {len(DB['users'])} ta"); return
    if data == "admin_couriers":
        cs = [v for v in DB["users"].values() if v.get("courier_registered")]
        txt = "🚴 Kuryerlar:\n\n" + "\n".join([f"{v.get('name','?')} — {'✅' if v.get('courier_status')=='approved' else '⏳ kutmoqda'} — ⭐ {avg(v.get('ratings',[])):.1f} ({len(v.get('ratings',[]))} ta) — Yetkazgan: {v.get('delivered',0)} ta — 🪪 {v.get('passport_num','—')}" for v in cs]) or "Kuryer yo'q"
        await q.message.reply_text(txt); return
    # FALLBACK: birorta handlerga tushmagan tugma bo'lsa ham jim qolmasin
    try: await q.message.reply_text("↩️ Asosiy menyuga qaytdik:")
    except: pass
    await show_main(update, uid, "Asosiy menyu:")


# --- ZAXIRA / TIKLASH BUYRUQLARI (faqat SUPER_ADMIN) ---
async def export_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPER_ADMIN:
        await update.message.reply_text("⛔ Faqat admin."); return
    save()
    try:
        last = open("db_backup_last.txt", encoding="utf-8").read()
    except: last = "—"
    try:
        await update.message.reply_document(document=open(DB_FILE, "rb"), filename="termiz_baza_zaxira.json", caption=f"📦 HAMMA BAZA — ZAXIRA\n\n👥 Odamlar: {len(DB.get('users', {}))}\n🏪 Do'konlar: {len(DB.get('shops', {}))}\n📦 Buyurtmalar: {len(DB.get('orders', {}))}\n🗄️ Arxiv: {len(DB.get('archive', {}))}\nOxirgi zaxira: {last}\n\n⚠️ Bu faylni hech kimga berma! Hamma login, telefon, guvohnoma, pasport, karta shu yerda.\nTelefoningga + Google Drive ga saqlab qo'y.")
    except Exception as e:
        await update.message.reply_text(f"Xato: {e}")

async def backup_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPER_ADMIN:
        await update.message.reply_text("⛔ Faqat admin."); return
    try: last = open("db_backup_last.txt", encoding="utf-8").read()
    except: last = "hali zaxira olinmagan"
    await update.message.reply_text(f"💾 ZAXIRA HOLATI\n\nOxirgi zaxira: {last}\n👥 Odamlar: {len(DB.get('users', {}))}\n🏪 Do'konlar: {len(DB.get('shops', {}))}\n📦 Buyurtmalar: {len(DB.get('orders', {}))}\n🗄️ Arxiv (hech kim o'chmaydi): {len(DB.get('archive', {}))}\n\nBuyruqlar:\n/export — bazani yuklab olish\n/backup — shu holat\n\nTiklash: zaxira faylni botga yubor → ✅ HA, TIKLA ni bos.")

async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Faqat admin yuborgan .json zaxira fayl tiklash uchun qabul qilinadi
    if update.effective_user.id != SUPER_ADMIN: return
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".json"): return
    try:
        f = await context.bot.get_file(doc.file_id)
        data = await f.download_as_bytearray()
        json.loads(bytes(data))  # zaxira ekanini tekshiramiz
    except Exception:
        await update.message.reply_text("❌ Bu zaxira faylga o'xshamaydi. /export bilan olgan faylni yubor."); return
    context.user_data["restore_data"] = bytes(data)
    await update.message.reply_text("📥 Zaxira fayl keldi. Rostan ham hammasini shu fayl bilan almashtirilsinmi?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ HA, TIKLA", callback_data="restore_yes")],[InlineKeyboardButton("❌ YO'Q", callback_data="restore_no")]]))

async def main():
    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("export", export_db))
    app_bot.add_handler(CommandHandler("backup", backup_info))
    app_bot.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app_bot.add_handler(CallbackQueryHandler(on_cb))
    app_bot.add_handler(MessageHandler(filters.LOCATION, on_location))
    app_bot.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print("Bot ishga tushdi...")
    await app_bot.initialize(); await app_bot.start(); await app_bot.updater.start_polling()
    import asyncio; await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio; asyncio.run(main())
