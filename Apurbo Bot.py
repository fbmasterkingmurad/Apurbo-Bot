import logging
import asyncio
import requests
import io
import os
import re  
import json
import phonenumbers
import cloudscraper 
import pyotp  # 2FA কোড জেনারেট করার জন্য
from phonenumbers import geocoder
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.error import BadRequest, Forbidden

# --- [ কনফিগারেশন ] ---
BOT_TOKEN = "8591825314:AAGMJgtVv5BOvs-HGKBGRMeMR2cUgwRNdA8"

# মাল্টি-অ্যাকাউন্ট সেটআপ
ACCOUNTS = [
    {"email": "debnathapurbo67@gmail.com", "pass": "Ami123ami@@"},
    {"email": "debnathapurbo67@gmail.com", "pass": "Ami123ami@@"}
]

RANGE_BOT_TOKEN = "8737601081:AAGrcsWQMkdIKE_wyrdsOb9-mpByVi5Uva0"
RANGE_CHAT_ID = -1003772424822 
RANGE_GROUP_ID = -1003772424822 

ADMIN_ID = 7076702690
GROUP_CHAT_ID = -1003866534122 
OTP_GROUP_ID = -1003866534122 
# নতুন গ্রুপ যেখানে ফুল নাম্বার এবং ডিটেইলস যাবে
NEW_OTP_GROUP_ID = -1003389693084

GROUP_LINK = "https://t.me/adotprcv"
RANGE_GROUP_LINK = "https://t.me/otprangegroup"
DB_FILE = "MASTER_MURAD_USERS.txt"
CONFIG_FILE = "config.json"
BAN_FILE = "All_Users_Deails.txt"

# বট প্যানেল লিঙ্ক
BOT_PANEL_LINK = "https://t.me/adapurbov1bot"

# --- [ Force Join Configuration ] ---
MUST_JOIN_CHANNELS = ["@adotprcv", "@methodgrupbd"]

# API Endpoints
LOGIN_API = "https://x.mnitnetwork.com/mapi/v1/mauth/login"
BUY_API = "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number"
STATUS_API = "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info"
CONSOLE_API = "https://x.mnitnetwork.com/mapi/v1/mdashboard/console/info"

scraper = cloudscraper.create_scraper()
range_bot = Bot(token=RANGE_BOT_TOKEN)

# সেশন ম্যানেজমেন্ট (২টি অ্যাকাউন্টের জন্য আলাদা স্টোরেজ)
sessions = [
    {"token": None, "cookie": "cf_clearance=KUpNlWYQ7qXJv3ObbfN.GetYsLiJBR3FZoPXv0Hq.24-1772209316-1.2.1.1-p0y0rJVPEi_Cv.lTrK3akyeI1iKJecKmZaa1TQ54qFybekPDW223yf6NhxAdktnrHqMruIFNKNEmzltG0Aa0k3IRebw27AEBZYGhLjP.RQSSTjeGg4iAdG8f54_iXY_unORmShktfXSuNJJk1M_HKUOeE32D5Vcp9DvS.qh8VZJA7_nzeV4voT1W4OBEPA62kjgo73XAgBhas_WCG4IapEjcWTWZr0mtjvdUeCCJBdk"},
    {"token": None, "cookie": "cf_clearance=KUpNlWYQ7qXJv3ObbfN.GetYsLiJBR3FZoPXv0Hq.24-1772209316-1.2.1.1-p0y0rJVPEi_Cv.lTrK3akyeI1iKJecKmZaa1TQ54qFybekPDW223yf6NhxAdktnrHqMruIFNKNEmzltG0Aa0k3IRebw27AEBZYGhLjP.RQSSTjeGg4iAdG8f54_iXY_unORmShktfXSuNJJk1M_HKUOeE32D5Vcp9DvS.qh8VZJA7_nzeV4voT1W4OBEPA62kjgo73XAgBhas_WCG4IapEjcWTWZr0mtjvdUeCCJBdk"}
]
current_account_index = 0

def get_next_account_index():
    global current_account_index
    idx = current_account_index
    current_account_index = (current_account_index + 1) % len(ACCOUNTS)
    return idx

# --- [ লোড কনফিগারেশন ] ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"otp_rate": 0.003}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

current_config = load_config()
OTP_RATE = current_config["otp_rate"]

user_state = {}
last_range = {}
processed_console_ids = set()

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- [ Ban Helpers ] ---
def is_banned(user_id):
    if not os.path.exists(BAN_FILE): return False
    with open(BAN_FILE, "r") as f:
        return str(user_id) in [line.strip() for line in f]

def ban_user(user_id):
    with open(BAN_FILE, "a") as f:
        f.write(f"{user_id}\n")

# --- [ SMS Parsing Helper ] ---
def parse_otp_info(sms_text):
    otp = re.search(r'\b\d{4,8}\b', sms_text)
    otp_code = otp.group(0) if otp else "N/A"
    
    app_name = "Service"
    apps = ['Facebook', 'WhatsApp', 'Telegram', 'Google', 'IMO', 'TikTok', 'Instagram', 'Netflix', 'Twitter', 'Viber']
    for app in apps:
        if app.lower() in sms_text.lower():
            app_name = app
            break
    return otp_code, app_name

# --- [ Basic Helpers ] ---
def save_user(user_id):
    if not os.path.exists(DB_FILE):
        open(DB_FILE, "w").close()
    with open(DB_FILE, "r") as f:
        users = [line.strip() for line in f]
    if str(user_id) not in users:
        with open(DB_FILE, "a") as f:
            f.write(f"{user_id}\n")

def get_all_users():
    if not os.path.exists(DB_FILE): return []
    with open(DB_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def get_country_info(phone_number):
    try:
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        parsed_num = phonenumbers.parse(phone_number)
        country = geocoder.description_for_number(parsed_num, "en")
        country_code = phonenumbers.region_code_for_number(parsed_num)
        flag = "".join(chr(127397 + ord(c)) for c in country_code.upper())
        return f"{flag} {country}"
    except:
        return "🌍 Unknown Country"

def mask_phone_number(number):
    num_str = str(number)
    if not num_str.startswith('+'):
        num_str = '+' + num_str
    if len(num_str) > 10:
        return f"{num_str[:-6]}**{num_str[-4:]}"
    return num_str

def do_login(index=0):
    headers = {
        "Content-Type": "application/json",
        "Cookie": sessions[index]["cookie"],
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    try:
        payload = {"email": ACCOUNTS[index]["email"], "password": ACCOUNTS[index]["pass"]}
        response = scraper.post(LOGIN_API, json=payload, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            if data.get("meta", {}).get("status") == "success":
                sessions[index]["token"] = data['data']['token']
                return True
    except: pass
    return False

def get_auth_headers(index=0):
    if not sessions[index]["token"]: do_login(index)
    return {
        "mauthtoken": str(sessions[index]["token"]), 
        "Cookie": f"{sessions[index]['cookie']}; mauthtoken={sessions[index]['token']}", 
        "Content-Type": "application/json"
    }

# --- [ Check Membership Helper ] ---
async def check_membership(user_id, context: ContextTypes.DEFAULT_TYPE):
    for channel in MUST_JOIN_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            # Bot might not be admin or user has never interacted
            return False
    return True

# --- [ Handlers ] ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("❌ You are banned from using this bot.")
        return

    # --- Force Join Check ---
    is_member = await check_membership(user_id, context)
    if not is_member:
        keyboard = [
            [InlineKeyboardButton("💬 OTP Group", url="https://t.me/adotprcv")],
            [InlineKeyboardButton("💬 Method Group", url="https://t.me/methodgrupbd")],
            [InlineKeyboardButton("✅ Verify", callback_data="verify_join")]
        ]
        await update.message.reply_text(
            "🚦 *Access Denied*\n\n"
            "To use This BOT, you must Join ALL Channels:\n\n"
            "💬 [OTP Group](https://t.me/adotprcv)\n"
            "💬 [Method Group](https://t.me/methodgrupbd)\n\n"
            "After Joining, Press ✅ Verify",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return
    # ------------------------

    save_user(user_id)
    user_state[user_id] = None 
    keyboard = [
        [InlineKeyboardButton("📱 GET NUMBER 📱", callback_data='ask_single')],
        [InlineKeyboardButton("🚀 GET 5 NUMBER 🚀", callback_data='ask_bulk')],
        [InlineKeyboardButton("🔐 FB 2FA CODE", callback_data='ask_2fa')],
        [InlineKeyboardButton("🔗 View Range", url=RANGE_GROUP_LINK)]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ ADMIN PANEL ⚙️", callback_data='admin_main')])
    
    await update.message.reply_text(
        "🔥 **VIP AND FAST NUMBER BOT** 🔥\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Select Your Service Number Button\n", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="Markdown"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    global OTP_RATE

    if is_banned(user_id):
        await query.answer("❌ You are banned!", show_alert=True)
        return

    # --- Force Join Verify Button Handler ---
    if data == 'verify_join':
        is_member = await check_membership(user_id, context)
        if is_member:
            await query.answer("✅ Verification Successful!", show_alert=False)
            await query.message.delete()
            
            save_user(user_id)
            user_state[user_id] = None 
            keyboard = [
                [InlineKeyboardButton("📱 GET NUMBER 📱", callback_data='ask_single')],
                [InlineKeyboardButton("🚀 GET 5 NUMBER 🚀", callback_data='ask_bulk')],
                [InlineKeyboardButton("🔐 FB 2FA CODE", callback_data='ask_2fa')],
                [InlineKeyboardButton("🔗 View Range", url=RANGE_GROUP_LINK)]
            ]
            if user_id == ADMIN_ID:
                keyboard.append([InlineKeyboardButton("⚙️ ADMIN PANEL ⚙️", callback_data='admin_main')])
            
            await context.bot.send_message(
                chat_id=user_id, 
                text="🔥 **VIP AND FAST NUMBER BOT** 🔥\n━━━━━━━━━━━━━━━━━━\nSelect Your Service Number Button\n", 
                reply_markup=InlineKeyboardMarkup(keyboard), 
                parse_mode="Markdown"
            )
        else:
            await query.answer("❌ Please join ALL channels first!", show_alert=True)
        return

    # Verify membership for all other button clicks to be strictly secure
    is_member = await check_membership(user_id, context)
    if not is_member:
        await query.answer("❌ You must join our channels first! Send /start again.", show_alert=True)
        return
    # ----------------------------------------

    await query.answer()

    if data == 'admin_main' and user_id == ADMIN_ID:
        kb = [[InlineKeyboardButton("🔄 Change OTP Rate", callback_data='set_rate_input')],
            [InlineKeyboardButton("📢 Send Notification", callback_data='admin_broadcast')],
            [InlineKeyboardButton("📊 User Stats & List", callback_data='admin_stats')],
            [InlineKeyboardButton("🚫 Ban User", callback_data='ask_ban_id')],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_to_start')]]
        await query.message.edit_text(f"🛠 **Admin Control Panel**\n\nCurrent OTP Rate: `{OTP_RATE}$`", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == 'set_rate_input' and user_id == ADMIN_ID:
        user_state[user_id] = "WAITING_FOR_RATE"
        await query.message.reply_text("⌨️ **Enter New OTP Rate (e.g., 0.005):**", parse_mode="Markdown")

    elif data == 'admin_broadcast' and user_id == ADMIN_ID:
        user_state[user_id] = "WAITING_FOR_BROADCAST"
        await query.message.reply_text("✉️ **Send any message (Text, Photo, Video) to broadcast to ALL users:**", parse_mode="Markdown")

    elif data == 'ask_ban_id' and user_id == ADMIN_ID:
        user_state[user_id] = "WAITING_FOR_BAN_ID"
        await query.message.reply_text("🚫 **Enter User ID to Ban:**", parse_mode="Markdown")

    elif data == 'admin_stats' and user_id == ADMIN_ID:
        users = get_all_users()
        report = "📊 **USER STATISTICS & LIST**\n━━━━━━━━━━━━━━━━━━\n"
        for u in users:
            report += f"👤 ID: `{u}`\n\n"
        report += f"👥 **Total Active Users: {len(users)}**"
        if len(report) > 4000:
            file_obj = io.BytesIO(report.encode('utf-8'))
            file_obj.name = "user_stats.txt"
            await query.message.reply_document(document=file_obj, caption="📊 Full User Stats List")
        else:
            await query.message.reply_text(report, parse_mode="Markdown")

    elif data == 'back_to_start':
        keyboard = [[InlineKeyboardButton("📱 GET NUMBER 📱", callback_data='ask_single')],
            [InlineKeyboardButton("🚀 GET 5 NUMBER 🚀", callback_data='ask_bulk')],
            [InlineKeyboardButton("🔐 FB 2FA CODE", callback_data='ask_2fa')],
            [InlineKeyboardButton("🔗 View Range", url=RANGE_GROUP_LINK)],
            [InlineKeyboardButton("⚙️ ADMIN PANEL ⚙️", callback_data='admin_main')]]
        await query.message.edit_text("🔥 **OTP MASTER MURAD NUMBER PANEL** 🔥", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == 'ask_single':
        user_state[user_id] = "WAITING_FOR_SINGLE_RANGE"
        await query.message.reply_text("⌨️ **Enter Range ID (1 Number):**", parse_mode="Markdown")
        
    elif data.startswith('change_num_'):
        range_id = data.split('_')[2]
        try: await query.message.edit_reply_markup(reply_markup=None)
        except: pass
        await generate_single_number(query.message, range_id, user_id, context, is_edit=False)

    elif data == 'ask_bulk':
        user_state[user_id] = "WAITING_FOR_BULK_RANGE"
        await query.message.reply_text("⌨️ **Enter Range ID (5 Number):**", parse_mode="Markdown")

    elif data == 'ask_2fa':
        user_state[user_id] = "WAITING_FOR_2FA_KEY"
        await query.message.reply_text("🔐 **Please enter your Facebook 2FA Key:**", parse_mode="Markdown")


# --- [ SMS Checker ] --- (মাল্টিপল ওটিপি সাপোর্ট সহ)
async def single_otp_checker(context, msg_obj, num, target_id, range_id, keyboard, user_data=None):
    received_otps = set() 
    # --- [ এখানে Bot Developer বাটনটি অ্যাড করা হয়েছে ] ---
    panel_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("💥 NUMBER PANEL 💥", url=BOT_PANEL_LINK)],
        [InlineKeyboardButton("🤖 Bot Developer", url="https://t.me/otpmastermuradbd")]
    ])
    for _ in range(60): 
        await asyncio.sleep(10)
        for i in range(len(ACCOUNTS)):
            try:
                r = scraper.get(STATUS_API, headers=get_auth_headers(i), params={"date": datetime.now().strftime("%Y-%m-%d")}, timeout=10).json()
                if r.get("meta", {}).get("status") == "success":
                    match = next((x for x in r['data']['numbers'] if str(x['number']).replace('+', '') == str(num)), None)
                    if match and match.get('otp'):
                        full_sms = match['otp']
                        if full_sms not in received_otps:
                            received_otps.add(full_sms) 
                            otp_code, app_name = parse_otp_info(full_sms)
                            country_info = get_country_info(num)
                            display_name = f"@{user_data.username}" if user_data and user_data.username else (f"{user_data.first_name}" if user_data else f"`{target_id}`")
                            clean_name = re.sub(r'[_*`\[\]]', '', display_name)

                            private_msg = (f"✅ OTP Received Successfully ✅\n\n🌍 Country: {country_info}\n\n📱 Service: {app_name}\n📞 Number: `+{num}`\n🔑 OTP: `{otp_code}`\n\n📩 Full SMS: `{full_sms}`")
                            group_msg = (f"✅ OTP Received Successfully ✅\n\n🌍 Country: {country_info}\n\n📱 Service: {app_name}\n📞 Number: `{mask_phone_number(num)}`\n🔑 OTP: `{otp_code}`\n\n📩 Full SMS: `{full_sms}`")
                            
                            try: await context.bot.send_message(chat_id=target_id, text=private_msg, parse_mode="Markdown", reply_markup=panel_button)
                            except: await context.bot.send_message(chat_id=target_id, text=private_msg, reply_markup=panel_button)
                            try: await context.bot.send_message(chat_id=OTP_GROUP_ID, text=group_msg, parse_mode="Markdown", reply_markup=panel_button)
                            except: await context.bot.send_message(chat_id=OTP_GROUP_ID, text=group_msg, reply_markup=panel_button)
            except: continue

async def bulk_otp_checker(context, target_id, numbers, range_val, user_data=None):
    known_otps = {} 
    # --- [ এখানেও Bot Developer বাটনটি অ্যাড করা হয়েছে ] ---
    panel_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("💥 NUMBER PANEL 💥", url=BOT_PANEL_LINK)],
        [InlineKeyboardButton("🤖 Bot Developer", url="https://t.me/otpmastermuradbd")]
    ])
    for _ in range(120): 
        await asyncio.sleep(15)
        for i in range(len(ACCOUNTS)):
            try:
                r = scraper.get(STATUS_API, headers=get_auth_headers(i), params={"date": datetime.now().strftime("%Y-%m-%d")}, timeout=10).json()
                if r.get("meta", {}).get("status") == "success":
                    for n in numbers:
                        match = next((x for x in r['data']['numbers'] if str(x['number']).replace('+', '') == str(n)), None)
                        if match and match.get('otp'):
                            full_sms = match['otp']
                            if n not in known_otps or known_otps[n] != full_sms:
                                known_otps[n] = full_sms
                                otp_code, app_name = parse_otp_info(full_sms)
                                country_info = get_country_info(n)
                                display_name = f"@{user_data.username}" if user_data and user_data.username else (f"{user_data.first_name}" if user_data else f"`{target_id}`")
                                clean_name = re.sub(r'[_*`\[\]]', '', display_name)
                                
                                private_msg = (f"✅ OTP Received Successfully ✅\n\n🌍 Country: {country_info}\n\n📱 Service: {app_name}\n📞 Number: `+{n}`\n🔑 OTP: `{otp_code}`\n\n📩 Full SMS: `{full_sms}`")
                                group_msg = (f"✅ OTP Received Successfully ✅\n\n🌍 Country: {country_info}\n\n📱 Service: {app_name}\n📞 Number: `{mask_phone_number(n)}`\n🔑 OTP: `{otp_code}`\n\n📩 Full SMS: `{full_sms}`")
                                try: await context.bot.send_message(chat_id=target_id, text=private_msg, parse_mode="Markdown", reply_markup=panel_button)
                                except: await context.bot.send_message(chat_id=target_id, text=private_msg, reply_markup=panel_button)
                                try: await context.bot.send_message(chat_id=OTP_GROUP_ID, text=group_msg, parse_mode="Markdown", reply_markup=panel_button)
                                except: await context.bot.send_message(chat_id=OTP_GROUP_ID, text=group_msg, reply_markup=panel_button)
            except: continue

# --- [ Background Broadcast Task ] ---
async def broadcast_task(context, message_obj, user_list):
    text = f"📢 **ADMIN NOTICE**\n\n{message_obj.text or message_obj.caption or ''}"
    photo = message_obj.photo[-1].file_id if message_obj.photo else None
    video = message_obj.video.file_id if message_obj.video else None
    document = message_obj.document.file_id if message_obj.document else None
    for uid in user_list:
        try:
            if photo: await context.bot.send_photo(chat_id=uid, photo=photo, caption=text, parse_mode="Markdown")
            elif video: await context.bot.send_video(chat_id=uid, video=video, caption=text, parse_mode="Markdown")
            elif document: await context.bot.send_document(chat_id=uid, document=document, caption=text, parse_mode="Markdown")
            else: await context.bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
            await asyncio.sleep(0.05)
        except: continue

# --- [ Rest of the Logic ] ---
async def generate_bulk_numbers_task(context, user_id, range_id, user_obj):
    status_msg = await context.bot.send_message(chat_id=user_id, text=f"⏳ **Collecting 5 Numbers... Please wait.**\n[░░░░░░░░░░] 0%", parse_mode="Markdown")
    numbers = []
    attempts = 0
    max_attempts = 150 
    country_name = "Unknown Country"
    
    while len(numbers) < 5 and attempts < max_attempts:
        attempts += 1
        idx = get_next_account_index()
        try:
            r = scraper.post(BUY_API, headers=get_auth_headers(idx), json={"range": range_id}, timeout=15).json()
            if r.get("meta", {}).get("status") == "success":
                num = str(r['data']['number']).replace('+', '')
                if not numbers: country_name = get_country_info(num)
                if num not in numbers: 
                    numbers.append(num)
                    percent = int((len(numbers) / 5) * 100)
                    filled = int(percent / 10)
                    bar = "█" * filled + "░" * (10 - filled)
                    try: await status_msg.edit_text(f"⏳ **Collecting 5 Numbers...**\n`[{bar}]` {percent}% ({len(numbers)}/5)", parse_mode="Markdown")
                    except: pass
            else: await asyncio.sleep(1)
            await asyncio.sleep(0.3) 
        except: 
            await asyncio.sleep(1)
            continue
    
    if numbers:
        file_obj = io.BytesIO("\n".join(numbers).encode('utf-8'))
        file_obj.name = f"5_Numbers_{range_id}.txt"
        caption_text = (f"✅ **Done! Numbers Collected**\n\n📶 Range Name: `{range_id}`\n🌍 Country Name: {country_name}\n🔢 Total Number: `{len(numbers)}`")
        await status_msg.delete()
        await context.bot.send_document(chat_id=user_id, document=file_obj, caption=caption_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📩 View OTP", url=GROUP_LINK)]]), parse_mode="Markdown")
        asyncio.create_task(bulk_otp_checker(context, user_id, numbers, range_id, user_obj))
    else:
        await status_msg.edit_text(f"❌ Could not collect numbers.")

async def handle_range_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_banned(user_id): return

    # --- Force Join Check for Text Input ---
    is_member = await check_membership(user_id, context)
    if not is_member:
        return # Ignore text input if not joined
    # --------------------------------------

    text = update.message.text.strip() if update.message.text else ""
    global OTP_RATE
    if user_id not in user_state or user_state[user_id] is None: return
    state = user_state[user_id]
    
    if state == "WAITING_FOR_RATE" and user_id == ADMIN_ID:
        user_state[user_id] = None
        try:
            OTP_RATE = float(text)
            current_config["otp_rate"] = OTP_RATE
            save_config(current_config)
            await update.message.reply_text(f"✅ OTP Rate: `{OTP_RATE}$`")
        except: pass
    elif state == "WAITING_FOR_BROADCAST" and user_id == ADMIN_ID:
        user_state[user_id] = None
        users = get_all_users()
        asyncio.create_task(broadcast_task(context, update.message, users))
        await update.message.reply_text(f"✅ Broadcast initiated to {len(users)} users.")
    elif state == "WAITING_FOR_BAN_ID" and user_id == ADMIN_ID:
        user_state[user_id] = None
        ban_user(text)
        await update.message.reply_text(f"✅ User `{text}` has been banned.")
    elif state == "WAITING_FOR_SINGLE_RANGE":
        user_state[user_id] = None
        await generate_single_number(update.message, text, user_id, context)
    elif state == "WAITING_FOR_BULK_RANGE":
        user_state[user_id] = None
        asyncio.create_task(generate_bulk_numbers_task(context, user_id, text, update.effective_user))
    # --- [ FB 2FA Logic ] ---
    elif state == "WAITING_FOR_2FA_KEY":
        user_state[user_id] = None
        try:
            # key থেকে স্পেস থাকলে রিমুভ করা
            clean_key = text.replace(" ", "")
            totp = pyotp.TOTP(clean_key)
            current_otp = totp.now()
            await update.message.reply_text(f"✅ **Facebook 2FA OTP**\n\n🔑 Key: `{text}`\n🔢 Code: `{current_otp}`\n\n🕒 Expire: After 30s", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Invalid 2FA Key! Please provide a correct secret key.")

async def generate_single_number(message_obj, range_id, user_id, context, is_edit=False):
    status_msg = await message_obj.reply_text("📡 Searching...") 
    idx = get_next_account_index()
    try:
        res = scraper.post(BUY_API, headers=get_auth_headers(idx), json={"range": range_id}, timeout=15).json()
        if res.get("meta", {}).get("status") == "success":
            num = str(res['data']['number']).replace('+', '')
            country_info = get_country_info(num)
            
            # --- [ এখানে 2FA বাটনটি View OTP এর নিচে যোগ করা হয়েছে ] ---
            keyboard = [
                [InlineKeyboardButton("🔄 Change Number", callback_data=f'change_num_{range_id}')],
                [InlineKeyboardButton("📩 View OTP", url=GROUP_LINK)],
                [InlineKeyboardButton("🔐 FB 2FA CODE", callback_data='ask_2fa')]
            ]
            
            msg = (f"✅ **YOUR NUMBER**\n📶 Range: `{range_id}`\n🌍 Country: `{country_info}`\n📞 Number: `+{num}`\n📩 SMS Status: `Waiting...` ")
            await status_msg.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            u_obj = message_obj.from_user if not is_edit else None
            asyncio.create_task(single_otp_checker(context, status_msg, num, user_id, range_id, keyboard, u_obj))
        else: await status_msg.edit_text("❌ Range empty.")
    except: await status_msg.edit_text("❌ Error.")

async def consol_sms_logger():
    while True:
        idx = get_next_account_index()
        try:
            response = scraper.get(CONSOLE_API, headers=get_auth_headers(idx), timeout=10).json()
            if response.get("meta", {}).get("status") == "success":
                logs = response.get('data', {}).get('logs', [])
                for entry in reversed(logs):
                    msg_id = entry.get('id')
                    if msg_id not in processed_console_ids:
                        range_val, country, app_name, sms_text = entry.get('range'), entry.get('country'), entry.get('app_name'), entry.get('sms')
                        country_display = country
                        try:
                            parsed_range = phonenumbers.parse("+" + str(range_val))
                            c_code = phonenumbers.region_code_for_number(parsed_range)
                            flag = "".join(chr(127397 + ord(c)) for c in c_code.upper())
                            country_display = f"{flag} {country}"
                        except: pass
                        msg = (f"✅ New Active Range ✅\n\n🌍 Country: {country_display}\n📶 Range `{range_val}XXX`\n\n🔵 Service: {app_name}\n\n📩 Full SMS: {sms_text}")
                        try:
                            await range_bot.send_message(chat_id=RANGE_CHAT_ID, text=msg, parse_mode="Markdown")
                            processed_console_ids.add(msg_id)
                        except: pass
        except: pass
        await asyncio.sleep(10)

async def post_init(application):
    asyncio.create_task(consol_sms_logger())

if __name__ == '__main__':
    for i in range(len(ACCOUNTS)): do_login(i)
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_range_input))
    print("🚀 Bot LIVE with 2 Accounts!")
    application.run_polling(drop_pending_updates=True)
