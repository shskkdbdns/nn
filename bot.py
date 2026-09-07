import logging
import asyncio
import time
import os
import sys
import aiohttp
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from config import *
from database import Database
import random
from datetime import datetime

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()

# Active attacks tracking
attack_slots = [None] * MAX_CONCURRENT_ATTACKS

# ============ API FUNCTIONS ============

async def send_attack_to_api(ip, port, time_sec, attack_id, user_id):
    """Send attack request to external API"""
    
    if not API_ENABLED:
        # Local attack mode (simulation)
        return {"success": True, "message": "Attack launched locally", "attack_id": attack_id}
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "ip": ip,
                "port": port,
                "time": time_sec,
                "attack_id": attack_id,
                "user_id": user_id,
                "api_key": API_KEY
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}"
            }
            
            async with session.post(
                API_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    error_text = await response.text()
                    return {"success": False, "error": f"API Error {response.status}: {error_text}"}
                    
    except asyncio.TimeoutError:
        return {"success": False, "error": "API timeout - Server not responding"}
    except Exception as e:
        logger.error(f"API Error: {e}")
        return {"success": False, "error": str(e)}

async def check_attack_status(attack_id):
    """Check attack status from API"""
    if not API_ENABLED:
        return {"status": "running"}
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "attack_id": attack_id,
                "api_key": API_KEY
            }
            
            async with session.post(
                f"{API_URL}/status",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {"status": "unknown"}
    except:
        return {"status": "unknown"}

# ============ PERMISSION CHECKS ============

def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    return is_owner(user_id) or db.is_admin(user_id)

def is_seller(user_id):
    return db.is_seller(user_id)

def is_authorized(user_id):
    return is_admin(user_id) or is_seller(user_id)

def get_available_slot():
    for i, slot in enumerate(attack_slots):
        if slot is None:
            return i
    return -1

def clear_finished_attacks():
    for i, slot in enumerate(attack_slots):
        if slot and slot.get('status') == 'finished':
            attack_slots[i] = None

def get_user_attack_slot(user_id):
    for slot in attack_slots:
        if slot and slot.get('user_id') == user_id and slot.get('status') == 'running':
            return slot
    return None

def has_active_key(user_id):
    keys = db.get_keys(used_by=user_id)
    for key in keys:
        if key[4] == 'active':
            if key[6]:
                try:
                    expiry_date = datetime.strptime(key[6], '%Y-%m-%d %H:%M:%S.%f')
                    if datetime.now() <= expiry_date:
                        return True
                except:
                    return True
            else:
                return True
    return False

# ============ START COMMAND ============

async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    db.add_user(user_id, update.effective_user.username or str(user_id))
    
    await update.message.reply_text(
        f"🎮 **RAGE BITE BGMI Attack Bot**\n\n"
        f"👤 Welcome {update.effective_user.first_name}!\n\n"
        f"Type `/help` to see all commands\n"
        f"Type `/plan` to view pricing\n"
        f"Type `/status` to check your status\n\n"
        f"💎 **ULTIMATE PLAN AVAILABLE**\n"
        f"→ 300 seconds attack time\n"
        f"→ Priority Support\n"
        f"→ No Waiting Time",
        parse_mode='Markdown'
    )

# ============ HELP COMMAND ============

async def help_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    is_admin_user = is_admin(user_id)
    is_seller_user = is_seller(user_id)
    
    help_text = """
💥 **Attack Commands:**
/bgmi <ip> <port> <time> - Launch attack
  • IP: Valid IP address
  • Port: 1-65535
  • Time: 10-300 seconds

🔑 **Key Commands:**
/redeem <key> - Activate access key

📊 **Info Commands:**
/status - Check your attack status
/plan - View pricing plans
/id - Your user ID
/help - This menu

"""
    
    if is_seller_user or is_admin_user:
        help_text += """
🛒 **Seller Commands:**
/genkey <duration> - Generate key (deducts balance)
  • 12hr, 1day, 1week, 15days, 1month
/mykeys - View your generated keys
/keycount - Check your key count

"""
    
    if is_admin_user:
        help_text += """
👑 **Admin Commands:**
/add <user_id> - Add user
/remove <user_id> - Remove user
/allusers - List all users
/logs - View logs
/clearlogs - Clear logs
/broadcast <msg> - Broadcast message
/stats - Bot statistics
/generate 1hr/1day - Generate key
/keyslist - Show generated keys
/addadmin <id> - Add admin
/removeadmin <id> - Remove admin
/addseller <id> - Add seller
/removeseller <id> - Remove seller
/sellers - List all sellers
/sellerbalance <id> - Check seller balance
/addbalance <id> <amount> - Add balance
/activeattacks - See all active attacks
/attackhistory - See attack history

"""
    
    help_text += """
📌 **RULES:**
• Multiple users can attack simultaneously
• 1 User = 1 Attack at a time
• Different users can attack at same time
• Admin/Seller = Unlimited attacks
• Max 300 seconds per attack

⚠️ NO BUGS - NO DELAYS
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ============ PLAN COMMAND ============

async def plan_command(update: Update, context: CallbackContext):
    plan_text = """
💎 **RAGE BITE PLANS**

💎 **ULTIMATE PLAN:**
→ Attack Time: 300 seconds
→ Priority Support
→ No Waiting Time
→ 4 Concurrent Slots
→ Unlimited Attacks

💰 **PRICES (Direct Purchase):**
• 12 Hours: 50 Rs
• Day: 100 Rs
• Week: 400 Rs
• 15 Days: 750 Rs
• Month: 1000 Rs

🔑 **Key Generation (For Resellers):**
• 12 Hours Key: 50 Coins
• 1 Day Key: 100 Coins
• 1 Week Key: 400 Coins
• 15 Days Key: 750 Coins
• 1 Month Key: 1000 Coins

📌 **RULES:**
• Unlimited attacks after key redemption
• No coin deduction for attacks
• Multiple users can attack simultaneously
• No delays or bugs

⚠️ **NO BUGS - NO DELAYS**
"""
    await update.message.reply_text(plan_text, parse_mode='Markdown')

# ============ STATUS COMMAND ============

async def status_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    active_slot = get_user_attack_slot(user_id)
    balance = db.get_balance(user_id)
    user_data = db.get_user(user_id)
    total_attacks = user_data[6] if user_data else 0
    is_seller_user = is_seller(user_id)
    has_key = has_active_key(user_id)
    
    status_text = f"""
📊 **Your Status**

👤 User ID: `{user_id}`
💰 Balance: `{balance}` coins
⚔️ Total Attacks: `{total_attacks}`
🔑 Active Key: `{'✅ Yes' if has_key else '❌ No'}`
🛒 Seller: `{'Yes' if is_seller_user else 'No'}`
👑 Admin: `{'Yes' if is_admin(user_id) else 'No'}`
"""
    
    if active_slot:
        elapsed = int(time.time() - active_slot['start_time'])
        remaining = max(0, active_slot['time'] - elapsed)
        status_text += f"""
🎯 **Active Attack:**
  IP: `{active_slot['ip']}:{active_slot['port']}`
  ⏱️ Remaining: `{remaining}` seconds
  🆔 ID: `{active_slot['attack_id']}`
"""
    else:
        status_text += "\n📌 No active attacks"
    
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def id_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 **Your User ID:** `{user_id}`", parse_mode='Markdown')

# ============ BGMI ATTACK COMMAND (UPDATED WITH API) ============

async def bgmi_attack(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    args = context.args
    
    # Check if user has active key or is admin
    if not has_active_key(user_id) and not is_admin(user_id):
        await update.message.reply_text(
            "❌ **No Active Key Found!**\n\n"
            "You need to redeem a key first.\n"
            "Use `/redeem <key>` to activate your key.\n\n"
            "Contact reseller to purchase a key.",
            parse_mode='Markdown'
        )
        return
    
    # Check if user already has active attack
    if get_user_attack_slot(user_id):
        await update.message.reply_text("❌ You already have an active attack! Wait for it to finish.")
        return
    
    # Check available slots
    clear_finished_attacks()
    slot_index = get_available_slot()
    if slot_index == -1:
        await update.message.reply_text(
            f"❌ **All Attack Slots Full!**\n\n"
            f"📊 Max: `{MAX_CONCURRENT_ATTACKS}` concurrent attacks\n"
            f"⏳ Please wait for ongoing attacks to finish.",
            parse_mode='Markdown'
        )
        return
    
    # Parse arguments
    if len(args) != 3:
        await update.message.reply_text(
            "❌ **Invalid Format!**\n\n"
            "Use: `/bgmi <IP> <PORT> <TIME>`\n"
            "Example: `/bgmi 1.1.1.1 443 60`\n\n"
            "📌 **Port Range:** `1-65535`\n"
            "⏱️ **Time Range:** `10-300` seconds",
            parse_mode='Markdown'
        )
        return
    
    ip = args[0]
    port = args[1]
    
    # Validate port
    if not port.isdigit() or int(port) < 1 or int(port) > 65535:
        await update.message.reply_text(
            f"❌ **Invalid Port!**\n\n"
            f"📌 Port `{port}` is not valid.\n"
            f"✅ **Valid Range:** `1-65535`",
            parse_mode='Markdown'
        )
        return
    
    port = int(port)
    
    # Validate time
    try:
        time_sec = int(args[2])
        if time_sec < MIN_ATTACK_TIME or time_sec > MAX_ATTACK_TIME:
            await update.message.reply_text(
                f"❌ **Invalid Time!**\n\n"
                f"⏱️ Time must be between **{MIN_ATTACK_TIME}-{MAX_ATTACK_TIME}** seconds.",
                parse_mode='Markdown'
            )
            return
    except ValueError:
        await update.message.reply_text("❌ **Invalid Time!** Must be a number.")
        return
    
    # Validate IP
    ip_parts = ip.split('.')
    if len(ip_parts) != 4:
        await update.message.reply_text("❌ **Invalid IP Address!** Example: `1.1.1.1`", parse_mode='Markdown')
        return
    
    for part in ip_parts:
        if not part.isdigit() or int(part) < 0 or int(part) > 255:
            await update.message.reply_text("❌ **Invalid IP Address!** Each octet must be 0-255.", parse_mode='Markdown')
            return
    
    # Generate attack ID
    attack_id = f"{user_id}_{int(time.time())}"
    
    # ============ SEND TO API ============
    await update.message.reply_text(
        f"🔄 **Sending attack to server...**\n\n"
        f"🎯 Target: `{ip}:{port}`\n"
        f"⏱️ Duration: `{time_sec}` seconds\n"
        f"🆔 Attack ID: `{attack_id}`",
        parse_mode='Markdown'
    )
    
    # Call API
    api_response = await send_attack_to_api(ip, port, time_sec, attack_id, user_id)
    
    if not api_response.get('success', False):
        error_msg = api_response.get('error', 'Unknown error')
        await update.message.reply_text(
            f"❌ **Attack Failed!**\n\n"
            f"Error: `{error_msg}`\n"
            f"Please try again later.",
            parse_mode='Markdown'
        )
        return
    
    # Reserve slot
    attack_slots[slot_index] = {
        'attack_id': attack_id,
        'user_id': user_id,
        'ip': ip,
        'port': port,
        'time': time_sec,
        'start_time': time.time(),
        'status': 'running',
        'api_response': api_response
    }
    
    # Send attack launched message
    attack_msg = await update.message.reply_text(
        f"⚔️ **Attack Launched!**\n\n"
        f"🎯 Target: `{ip}:{port}`\n"
        f"⏱️ Duration: `{time_sec}` seconds\n"
        f"🆔 Attack ID: `{attack_id}`\n"
        f"📌 Slot: `{slot_index + 1}/{MAX_CONCURRENT_ATTACKS}`\n"
        f"🌐 Server: `{'API' if API_ENABLED else 'Local'}`\n\n"
        f"🔄 **Status:** Processing...",
        parse_mode='Markdown'
    )
    
    db.log_attack(user_id, ip, port, time_sec, attack_id, 'running')
    
    # Simulate or monitor attack
    if API_ENABLED:
        await monitor_api_attack(attack_id, attack_msg, ip, port, time_sec, slot_index)
    else:
        await simulate_attack(attack_id, attack_msg, ip, port, time_sec, slot_index)

async def monitor_api_attack(attack_id, attack_msg, ip, port, duration, slot_index):
    """Monitor API attack status"""
    try:
        elapsed = 0
        while elapsed < duration:
            await asyncio.sleep(10)
            elapsed += 10
            remaining = duration - elapsed
            
            # Check status from API
            status_response = await check_attack_status(attack_id)
            status = status_response.get('status', 'running')
            
            if remaining > 0:
                progress = (elapsed / duration) * 100
                await attack_msg.edit_text(
                    f"⚔️ **Attack in Progress**\n\n"
                    f"🎯 Target: `{ip}:{port}`\n"
                    f"⏱️ Remaining: `{remaining}` seconds\n"
                    f"📊 Progress: `{progress:.1f}%`\n"
                    f"📌 Slot: `{slot_index + 1}/{MAX_CONCURRENT_ATTACKS}`\n"
                    f"🌐 Status: `{status}`\n\n"
                    f"🔄 **Attacking...**",
                    parse_mode='Markdown'
                )
        
        await attack_msg.edit_text(
            f"✅ **Attack Finished!**\n\n"
            f"🎯 Target: `{ip}:{port}`\n"
            f"⏱️ Total Duration: `{duration}` seconds\n"
            f"📌 Slot: `{slot_index + 1}/{MAX_CONCURRENT_ATTACKS}`\n"
            f"📊 Status: **Completed** ✅\n"
            f"🌐 Server: **API**",
            parse_mode='Markdown'
        )
        
        if slot_index < len(attack_slots) and attack_slots[slot_index]:
            attack_slots[slot_index]['status'] = 'finished'
            db.update_attack_status(attack_id, 'finished')
            
    except Exception as e:
        logger.error(f"Attack monitor error: {e}")
        attack_slots[slot_index] = None

async def simulate_attack(attack_id, attack_msg, ip, port, duration, slot_index):
    """Local attack simulation (when API is disabled)"""
    try:
        elapsed = 0
        while elapsed < duration:
            await asyncio.sleep(10)
            elapsed += 10
            remaining = duration - elapsed
            if remaining > 0:
                progress = (elapsed / duration) * 100
                await attack_msg.edit_text(
                    f"⚔️ **Attack in Progress**\n\n"
                    f"🎯 Target: `{ip}:{port}`\n"
                    f"⏱️ Remaining: `{remaining}` seconds\n"
                    f"📊 Progress: `{progress:.1f}%`\n"
                    f"📌 Slot: `{slot_index + 1}/{MAX_CONCURRENT_ATTACKS}`\n\n"
                    f"🔄 **Attacking...**",
                    parse_mode='Markdown'
                )
        
        await attack_msg.edit_text(
            f"✅ **Attack Finished!**\n\n"
            f"🎯 Target: `{ip}:{port}`\n"
            f"⏱️ Total Duration: `{duration}` seconds\n"
            f"📌 Slot: `{slot_index + 1}/{MAX_CONCURRENT_ATTACKS}`\n"
            f"📊 Status: **Completed** ✅",
            parse_mode='Markdown'
        )
        
        if slot_index < len(attack_slots) and attack_slots[slot_index]:
            attack_slots[slot_index]['status'] = 'finished'
            db.update_attack_status(attack_id, 'finished')
            
    except Exception as e:
        logger.error(f"Attack error: {e}")
        attack_slots[slot_index] = None

# ============ KEY COMMANDS ============

async def genkey(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ **Access Denied!** Only Admin/Seller can generate keys.")
        return
    
    args = context.args
    if len(args) != 1:
        await update.message.reply_text(
            "❌ **Invalid Format!**\n\n"
            "Use: `/genkey <duration>`\n\n"
            "📌 **Available Durations:**\n"
            "• `/genkey 12hr` - 12 Hours (50 coins)\n"
            "• `/genkey 1day` - 1 Day (100 coins)\n"
            "• `/genkey 1week` - 1 Week (400 coins)\n"
            "• `/genkey 15days` - 15 Days (750 coins)\n"
            "• `/genkey 1month` - 1 Month (1000 coins)",
            parse_mode='Markdown'
        )
        return
    
    duration = args[0]
    valid_durations = ['12hr', '1day', '1week', '15days', '1month']
    if duration not in valid_durations:
        await update.message.reply_text(
            "❌ **Invalid Duration!**\n\n"
            "Use: `/genkey 12hr` or `/genkey 1day` or `/genkey 1week` or `/genkey 15days` or `/genkey 1month`",
            parse_mode='Markdown'
        )
        return
    
    cost_map = {
        '12hr': KEY_12HOUR_COST,
        '1day': KEY_1DAY_COST,
        '1week': KEY_1WEEK_COST,
        '15days': KEY_15DAYS_COST,
        '1month': KEY_1MONTH_COST
    }
    cost = cost_map[duration]
    
    if is_seller(user_id) and not is_admin(user_id):
        balance = db.get_balance(user_id)
        if balance < cost:
            await update.message.reply_text(
                f"❌ **Insufficient Balance!**\n\n"
                f"💰 Your balance: `{balance}` coins\n"
                f"🔑 {duration} key cost: `{cost}` coins\n"
                f"❌ Need `{cost - balance}` more coins\n\n"
                f"Contact admin to add balance.",
                parse_mode='Markdown'
            )
            return
    
    key_code = db.generate_key(duration, user_id)
    
    if is_seller(user_id) and not is_admin(user_id):
        db.add_balance(user_id, -cost)
        balance_msg = f"\n💰 Deducted: `{cost}` coins\n📊 New Balance: `{db.get_balance(user_id)}` coins"
    else:
        balance_msg = ""
    
    duration_names = {
        '12hr': '12 Hours',
        '1day': '1 Day',
        '1week': '1 Week',
        '15days': '15 Days',
        '1month': '1 Month'
    }
    
    await update.message.reply_text(
        f"✅ **Key Generated!**\n\n"
        f"🔑 Key: `{key_code}`\n"
        f"⏱️ Duration: `{duration_names[duration]}`\n"
        f"👤 Generated by: `{user_id}`{balance_msg}\n\n"
        f"📌 Give this key to user to redeem:\n"
        f"`/redeem {key_code}`",
        parse_mode='Markdown'
    )

async def mykeys(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ **Access Denied!** Only Admin/Seller can view keys.")
        return
    
    keys = db.get_keys(generated_by=user_id)
    
    if not keys:
        await 
