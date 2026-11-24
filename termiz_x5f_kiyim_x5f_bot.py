
# TERMIZ KIYIM BOTI - Do'konchilar o'z mollarini qo'yib sotadigan bot
# requirements.txt: python-telegram-bot==22.2 + Flask
import os, json
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

app = Flask(__name__)
@app.route('/')
def home(): return "Termiz Kiyim Boti ishlayapti!"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)
Thread(target=run_flask, daemon=True).start()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPER_ADMIN = 6738827993  # <-- O'Z ID INGNI YOZ
COMMISSION_PER_ORDER = 2000
DB_FILE = "db.json"
CATEGORIES = ["👨 Erkaklar", "👩 Ayollar", "🧒 Bolalar", "👟 Oyoq kiyim", "👜 Sumka / Aksessuar"]

def load():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except:
        return {"users": {}, "shops": {}, "orders": {}, "counter": 1}
def save():
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(DB, f, ensure_ascii=False, indent=2)
DB = load()

def main_kb(role, locked=None):
    if role == "shop":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🏪 Mening do'konim", callback_data="shop_panel")],
            [InlineKeyboardButton("➕ Mol qo'shish", callback_data="add_product")],
            [InlineKeyboardButton("👕 Mollarim", callback_data="my_products")],
            [InlineKeyboardButton("📦 Yangi buyurtmalar", callback_data="shop_orders")],
            [InlineKeyboardButton("📊 Statistika", callback_data="shop_stats")],
        ])
    if role == "courier":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🚴 Kuryer panel", callback_data="courier_panel")],
            [InlineKeyboardButton("🟢 ONLINE / 🔴 OFFLINE", callback_data="courier_toggle")],
            [InlineKeyboardButton("📦 Bo'sh buyurtmalar", callback_data="courier_list")],
            [InlineKeyboardButton("💰 Hisobim", callback_data="courier_balance")],
        ])
    if role == "admin":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🏪 Do'konlar", callback_data="admin_shops")],
            [InlineKeyboardButton("📦 Barcha buyurtmalar", callback_data="admin_orders")],
            [InlineKeyboardButton("📊 Do'konlar qarzi (komissiya)", callback_data="admin_debt")],
            [InlineKeyboardButton("👥 Mijozlar", callback_data="admin_users")],
            [InlineKeyboardButton("🚴 Kuryerlar", callback_data="admin_couriers")],
        ])
    if locked == "client":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍️ Do'konlar", callback_data="client_shops")],
            [InlineKeyboardButton("🛒 Savatim", callback_data="client_cart")],
            [InlineKeyboardButton("📦 Buyurtmalarim", callback_data="client_my")],
            [InlineKeyboardButton("💰 Hisobim", callback_data="client_balance")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ Do'konlar", callback_data="client_shops")],
        [InlineKeyboardButton("🛒 Savatim", callback_data="client_cart")],
        [InlineKeyboardButton("📦 Buyurtmalarim", callback_data="client_my")],
        [InlineKeyboardButton("💰 Hisobim", callback_data="client_balance")],
        [InlineKeyboardButton("🏪 Do'konchi bo'lib ro'yxatdan o'tish", callback_data="register_shop")],
        [InlineKeyboardButton("🚴 Kuryer bo'lib ro'yxatdan o'tish", callback_data="register_courier")],
    ])

async def show_main(update, uid, text="Asosiy menyu:"):
    u = DB["users"].get(str(uid), {})
    kb = main_kb(u.get("role", "client"), u.get("locked_role"))
    try:
        if update.callback_query:
            try: await update.callback_query.message.delete()
            except: pass
            await update.callback_query.message.reply_text(text, reply_markup=kb)
        else:
            await update.message.reply_text(text, reply_markup=kb)
    except: pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in DB["users"]:
        DB["users"][uid] = {"name": update.effective_user.first_name, "role": "client", "phone": "", "online": False, "balance": 0, "delivered": 0, "cart": []}
        save()
    if update.effective_user.id == SUPER_ADMIN:
        await update.message.reply_text("👑 Salom Boss!\nQaysi rolni ko'rmoqchisan?", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 Admin panel", callback_data="setrole_admin")],
            [InlineKeyboardButton("🛍️ Mijoz sifatida", callback_data="setrole_client")],
            [InlineKeyboardButton("🏪 Do'konchi sifatida", callback_data="setrole_shop")],
            [InlineKeyboardButton("🚴 Kuryer sifatida", callback_data="setrole_courier")],
        ])); return
    await show_main(update, update.effective_user.id, f"Salom {DB['users'][uid]['name']}! 👋\n\n🛍️ TERMIZ KIYIM BOTI ga xush kelibsiz!\nBu yerda Termiz do'konlarining mollari bor.\nRoldingiz: {DB['users'][uid]['role']}")

# --- DO'KONCHI RO'YXATI ---
async def register_shop(update, context):
    q = update.callback_query; await q.answer()
    u = DB["users"].get(str(q.from_user.id), {})
    if u.get("locked_role") and u["locked_role"] != "shop":
        await q.message.reply_text("🔒 Siz boshqa rolga qulflangansiz."); return
    if any(v.get("admin") == q.from_user.id for v in DB["shops"].values()):
        await q.message.reply_text("✅ Sizda allaqachon do'kon bor."); return
    context.user_data["step"] = "reg_shop_name"; context.user_data["reg"] = {}
    await q.message.reply_text("🏪 Do'kon ochish — 1/3\n\nDo'kon nomini yozing:\nMasalan: Zara Termiz")

async def register_courier(update, context):
    q = update.callback_query; await q.answer()
    uid = str(q.from_user.id)
    DB["users"][uid]["courier_registered"] = True; DB["users"][uid]["locked_role"] = "courier"; DB["users"][uid]["role"] = "courier"; save()
    await show_main(update, q.from_user.id, "🚴 Kuryer sifatida ro'yxatdan o'tdingiz! ✅\nEndi ONLINE bo'lib buyurtma olishingiz mumkin.")

# --- MATN BILAN ISHLASH (step mashinasi) ---
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id); txt = update.message.text.strip()
    step = context.user_data.get("step")
    if not step:
        await show_main(update, update.effective_user.id, "Asosiy menyu:"); return
    # Do'kon ro'yxati: nom -> telefon -> manzil
    if step == "reg_shop_name":
        context.user_data["reg"]["name"] = txt; context.user_data["step"] = "reg_shop_phone"
        await update.message.reply_text("🏪 2/3\nTelefon raqamingizni yozing:\nMasalan: +998 90 123 45 67"); return
    if step == "reg_shop_phone":
        context.user_data["reg"]["phone"] = txt; context.user_data["step"] = "reg_shop_addr"
        await update.message.reply_text("🏪 3/3\nDo'kon manzilini yozing:\nMasalan: Termiz, Alisher Navoiy ko'chasi 12"); return
    if step == "reg_shop_addr":
        reg = context.user_data["reg"]; reg["address"] = txt
        import re
        slug = re.sub(r"[^a-z0-9_]+", "_", reg["name"].lower()).strip("_")[:20] or "shop"
        if slug in DB["shops"]: slug = slug + "_" + uid[-4:]
        DB["shops"][slug] = {"name": reg["name"], "admin": update.effective_user.id, "phone": reg["phone"], "address": reg["address"], "delivery": 15000, "active": True, "products": {}, "debt": 0}
        DB["users"][uid]["locked_role"] = "shop"; DB["users"][uid]["role"] = "shop"; save()
        context.user_data["step"] = None
        await show_main(update, update.effective_user.id, f"🎉 Do'koningiz ochildi: {reg['name']} ✅\nEndi '➕ Mol qo'shish' ni bosib mollaringizni qo'ying."); return
    # Mol qo'shish: nom -> narx -> kategoriya tugma orqali -> razmer -> rang -> rasm -> saqlash
    if step == "add_p_name":
        context.user_data["prod"] = {"name": txt}; context.user_data["step"] = "add_p_price"
        await update.message.reply_text("💰 Narxini yozing (faqat raqam):\nMasalan: 120000"); return
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
        await update.message.reply_text("📦 Nechta bor? Soni yozing:\nMasalan: 10"); return
    if step == "add_p_stock":
        try: context.user_data["prod"]["stock"] = int(txt)
        except: await update.message.reply_text("❌ Faqat raqam: 10"); return
        context.user_data["step"] = "add_p_photo"
        await update.message.reply_text("📸 Endi molning RASMINI yuboring (1 ta rasm)"); return
    # Buyurtma: manzil
    if step == "order_addr":
        context.user_data["order_addr"] = txt; context.user_data["step"] = "order_phone"
        await update.message.reply_text("📞 Telefon raqamingizni yozing:"); return
    if step == "order_phone":
        uid2 = str(update.effective_user.id)
        cart = DB["users"][uid2].get("cart", [])
        if not cart: await update.message.reply_text("Savat bo'sh"); return
        total = sum(DB["shops"][i["shop"]]["products"][i["pid"]]["price"] * i["qty"] for i in cart)
        oid = str(DB["counter"]); DB["counter"] += 1
        DB["orders"][oid] = {"user_id": update.effective_user.id, "items": cart, "total": total, "delivery": 15000, "address": context.user_data["order_addr"], "phone": txt, "status": "new", "courier": None}
        # Do'konchiga xabar
        for item in cart:
            shop = DB["shops"][item["shop"]]
            shop["debt"] = shop.get("debt", 0) + COMMISSION_PER_ORDER
        DB["users"][uid2]["cart"] = []; save()
        context.user_data["step"] = None
        # Har bir do'konga alohida xabar
        for shop_id in set(i["shop"] for i in cart):
            shop = DB["shops"][shop_id]
            try: await context.bot.send_message(shop["admin"], f"🔔 YANGI BUYURTMA #{oid}\nDo'kon: {shop['name']}\nMijoz: {txt}\nManzil: {context.user_data['order_addr']}\nSumma: {total+15000:,} so'm\n\nBotda '📦 Yangi buyurtmalar' ni bosing.")
            except: pass
        await show_main(update, update.effective_user.id, f"✅ Buyurtmangiz qabul qilindi! #{oid}\nJami: {total+15000:,} so'm (yetkazish bilan)\nDo'konchi tasdiqlashi bilan kuryer yo'lga chiqadi."); return

async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "add_p_photo": return
    uid = update.effective_user.id
    my_shop = [k for k, v in DB["shops"].items() if v.get("admin") == uid]
    if not my_shop: return
    prod = context.user_data.get("prod", {})
    prod["photo"] = update.message.photo[-1].file_id
    pid = f"p{len(DB['shops'][my_shop[0]]['products'])+1}_{uid%1000}"
    DB["shops"][my_shop[0]]["products"][pid] = prod; save()
    context.user_data["step"] = None
    await show_main(update, uid, f"✅ Mol qo'shildi: {prod['name']} — {prod['price']:,} so'm\nRazmer: {', '.join(prod['sizes'])} | Rang: {', '.join(prod['colors'])}")

# --- CALLBACKLAR ---
async def on_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); data = q.data; uid = q.from_user.id; u = DB["users"].get(str(uid), {})
    if data.startswith("setrole_"):
        role = data.replace("setrole_", "")
        if uid != SUPER_ADMIN and role == "admin": return
        DB["users"][str(uid)]["role"] = role; save(); await show_main(update, uid, f"Rol: {role} ✅"); return
    if data == "back_main": await show_main(update, uid, "Asosiy menyu:"); return
    if data == "register_shop": await register_shop(update, context); return
    if data == "register_courier": await register_courier(update, context); return
    # MIJOZ: do'konlar
    if data == "client_shops":
        if not DB["shops"]: await q.message.reply_text("Hozircha do'kon yo'q."); return
        kb = [[InlineKeyboardButton(f"🏪 {v['name']} — {v['address']}", callback_data=f"shop_{k}")] for k, v in DB["shops"].items() if v.get("active")]
        kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")])
        try: await q.message.delete()
        except: pass
        await q.message.reply_text("🛍️ Do'konni tanlang:", reply_markup=InlineKeyboardMarkup(kb)); return
    if data.startswith("shop_") and not data.startswith("shop_orders") and not data.startswith("shop_panel") and not data.startswith("shop_stats"):
        sid = data.replace("shop_", "")
        shop = DB["shops"].get(sid)
        if not shop: return
        if not shop["products"]:
            await q.message.reply_text(f"🏪 {shop['name']}\n📍 {shop['address']}\n📞 {shop['phone']}\n\nHozircha mol yo'q."); return
        kb = [[InlineKeyboardButton(f"{p['name']} — {p['price']:,} so'm", callback_data=f"prod_{sid}_{pid}")] for pid, p in shop["products"].items()]
        kb.append([InlineKeyboardButton("⬅️ Do'konlar", callback_data="client_shops")])
        try: await q.message.delete()
        except: pass
        await q.message.reply_text(f"🏪 {shop['name']}\n📍 {shop['address']}\n📞 {shop['phone']}\n\nMolni tanlang:", reply_markup=InlineKeyboardMarkup(kb)); return
    if data.startswith("prod_"):
        _, sid, pid = data.split("_", 2)
        p = DB["shops"][sid]["products"][pid]
        kb = [[InlineKeyboardButton(f"📏 {s}", callback_data=f"size_{sid}_{pid}_{s}")] for s in p.get("sizes", ["M"])]
        kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data=f"shop_{sid}")])
        try:
            await context.bot.send_photo(uid, p.get("photo", ""), caption=f"👕 {p['name']}\n💰 {p['price']:,} so'm\n📂 {p.get('category','')}\n🎨 Rang: {', '.join(p.get('colors', []))}\n📦 Qoldiq: {p.get('stock', 0)} ta\n\nRazmer tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        except: await q.message.reply_text(f"👕 {p['name']}\n💰 {p['price']:,} so'm\nRazmer tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        return
    if data.startswith("size_"):
        _, sid, pid, size = data.split("_", 3)
        p = DB["shops"][sid]["products"][pid]
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
        txt += f"\nJami: {total:,} so'm + yetkazish 15 000 = {total+15000:,} so'm"
        await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Buyurtma berish", callback_data="checkout")],[InlineKeyboardButton("🗑️ Savatni tozalash", callback_data="clear_cart")],[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]])); return
    if data == "clear_cart": DB["users"][str(uid)]["cart"] = []; save(); await q.message.reply_text("Savat tozalandi."); return
    if data == "checkout":
        context.user_data["step"] = "order_addr"; await q.message.reply_text("📍 Yetkazish manzilini yozing:\nMasalan: Termiz, 5-mikrorayon, 12-uy"); return
    if data == "client_my":
        my = [ (k, v) for k, v in DB["orders"].items() if v["user_id"] == uid]
        if not my: await q.message.reply_text("Buyurtmangiz yo'q."); return
        txt = "📦 Buyurtmalarim:\n\n" + "\n".join([f"#{k} — {v['total']+v['delivery']:,} so'm — {v['status']}" for k, v in my])
        await q.message.reply_text(txt); return
    if data == "client_balance": await q.message.reply_text(f"💰 Hisobingiz: {u.get('balance',0):,} so'm"); return
    # DO'KONCHI
    if data == "shop_panel":
        my = [v for v in DB["shops"].values() if v.get("admin") == uid]
        if not my: await q.message.reply_text("Do'koningiz yo'q."); return
        s = my[0]; await q.message.reply_text(f"🏪 {s['name']}\n📍 {s['address']}\n📞 {s['phone']}\n📦 Mol soni: {len(s['products'])}\n💸 Komissiya qarzi: {s.get('debt',0):,} so'm", reply_markup=main_kb("shop")); return
    if data == "add_product":
        context.user_data["step"] = "add_p_name"; await q.message.reply_text("➕ Mol qo'shish — 1/6\n\nMol nomini yozing:\nMasalan: Oversize Futbolka"); return
    if data.startswith("p_cat_"):
        cat = CATEGORIES[int(data.replace("p_cat_", ""))]
        context.user_data["prod"]["category"] = cat; context.user_data["step"] = "add_p_sizes"
        await q.message.reply_text(f"Kategoriya: {cat}\n\n📏 Razmerlarni vergul bilan yozing:\nMasalan: S, M, L, XL"); return
    if data == "my_products":
        my = [v for v in DB["shops"].values() if v.get("admin") == uid]
        if not my or not my[0]["products"]: await q.message.reply_text("Hozircha mol yo'q."); return
        txt = "👕 Mollarim:\n\n" + "\n".join([f"{p['name']} — {p['price']:,} so'm — {p.get('stock',0)} ta" for p in my[0]["products"].values()])
        await q.message.reply_text(txt); return
    if data == "shop_orders":
        my_shop = [k for k, v in DB["shops"].items() if v.get("admin") == uid]
        orders = [(k, v) for k, v in DB["orders"].items() if any(i["shop"] in my_shop for i in v["items"]) and v["status"] == "new"]
        if not orders: await q.message.reply_text("Yangi buyurtma yo'q."); return
        for k, v in orders:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Qabul qilish", callback_data=f"accept_{k}")]])
            await q.message.reply_text(f"📦 Buyurtma #{k}\nManzil: {v['address']}\nTel: {v['phone']}\nSumma: {v['total']+v['delivery']:,} so'm", reply_markup=kb)
        return
    if data.startswith("accept_"):
        oid = data.replace("accept_", ""); DB["orders"][oid]["status"] = "accepted"; save()
        await q.message.reply_text(f"✅ Buyurtma #{oid} qabul qilindi. Kuryer olishi kutilmoqda.")
        try: await context.bot.send_message(DB["orders"][oid]["user_id"], f"✅ Buyurtmangiz #{oid} do'kon tomonidan qabul qilindi!")
        except: pass
        return
    if data == "shop_stats":
        my = [v for v in DB["shops"].values() if v.get("admin") == uid]
        if not my: return
        cnt = sum(1 for o in DB["orders"].values() if any(i["shop"] in [k for k, v in DB["shops"].items() if v.get("admin")==uid] for i in o["items"]))
        await q.message.reply_text(f"📊 Statistika\nJami buyurtma: {cnt} ta\nKomissiya qarzi: {my[0].get('debt',0):,} so'm"); return
    # KURYER
    if data == "courier_panel": await q.message.reply_text(f"🚴 Kuryer panel\nOnline: {u.get('online')}\nYetkazgan: {u.get('delivered',0)} ta", reply_markup=main_kb("courier")); return
    if data == "courier_toggle":
        u["online"] = not u.get("online", False); save(); await q.message.reply_text(f"{'🟢 ONLINE' if u['online'] else '🔴 OFFLINE'}"); return
    if data == "courier_list":
        free = [(k, v) for k, v in DB["orders"].items() if v["status"] == "accepted" and not v.get("courier")]
        if not free: await q.message.reply_text("Bo'sh buyurtma yo'q."); return
        for k, v in free:
            await q.message.reply_text(f"📦 #{k} — {v['address']}\nSumma: {v['total']+v['delivery']:,} so'm", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚴 Olish", callback_data=f"take_{k}")]]))
        return
    if data.startswith("take_"):
        oid = data.replace("take_", ""); DB["orders"][oid]["courier"] = uid; DB["orders"][oid]["status"] = "onway"; save()
        await q.message.reply_text(f"🚴 Buyurtma #{oid} ni oldingiz. Do'kondan olib, mijozga olib boring."); return
    if data == "courier_balance": await q.message.reply_text(f"💰 Yetkazgan: {u.get('delivered',0)} ta"); return
    # ADMIN
    if data == "admin_shops":
        txt = "🏪 Do'konlar:\n\n" + "\n".join([f"{v['name']} — {v['phone']} — Qarz: {v.get('debt',0):,} so'm" for v in DB["shops"].values()]) or "Do'kon yo'q"
        await q.message.reply_text(txt); return
    if data == "admin_orders":
        txt = "📦 Buyurtmalar:\n\n" + "\n".join([f"#{k} — {v['total']+v['delivery']:,} — {v['status']}" for k, v in DB["orders"].items()]) or "Buyurtma yo'q"
        await q.message.reply_text(txt); return
    if data == "admin_debt":
        total = sum(v.get("debt", 0) for v in DB["shops"].values())
        txt = f"💸 Jami komissiya qarzi: {total:,} so'm\n\n" + "\n".join([f"{v['name']}: {v.get('debt',0):,} so'm" for v in DB["shops"].values()])
        await q.message.reply_text(txt); return
    if data == "admin_users": await q.message.reply_text(f"👥 Mijozlar: {len(DB['users'])} ta"); return
    if data == "admin_couriers":
        cs = [v for v in DB["users"].values() if v.get("courier_registered")]
        await q.message.reply_text(f"🚴 Kuryerlar: {len(cs)} ta"); return

async def main():
    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(on_cb))
    app_bot.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print("Bot ishga tushdi...")
    await app_bot.initialize(); await app_bot.start(); await app_bot.updater.start_polling()
    import asyncio; await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio; asyncio.run(main())
