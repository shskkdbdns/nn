# Bot Configuration
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Get from @BotFather
OWNER_ID = 123456789  # Replace with your Telegram ID

# Attack Settings
MAX_ATTACK_TIME = 300  # Max seconds per attack
MIN_ATTACK_TIME = 10   # Min seconds per attack
MAX_CONCURRENT_ATTACKS = 4  # Total attack slots

# Key Generation Costs (Deducted from Seller Balance)
KEY_12HOUR_COST = 50
KEY_1DAY_COST = 100
KEY_1WEEK_COST = 400
KEY_15DAYS_COST = 750
KEY_1MONTH_COST = 1000

# Seller Initial Balance
SELLER_INITIAL_BALANCE = 100

# ============ API CONFIGURATION ============
API_ENABLED = True  # True = API mode, False = Local mode
API_URL = "http://your-api-server.com/api/attack"  # Your API endpoint
API_KEY = "your-api-key-here"  # API authentication key
API_TIMEOUT = 30  # API response timeout in seconds
