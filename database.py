import sqlite3
import json
import random
import string
from datetime import datetime, timedelta

class Database:
    def __init__(self, db_file="bot_database.db"):
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY, 
                      username TEXT,
                      balance INTEGER DEFAULT 0,
                      is_admin INTEGER DEFAULT 0,
                      is_seller INTEGER DEFAULT 0,
                      is_active INTEGER DEFAULT 1,
                      total_attacks INTEGER DEFAULT 0,
                      joined_date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        # Admins table
        c.execute('''CREATE TABLE IF NOT EXISTS admins
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      added_by INTEGER,
                      added_date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        # Sellers table
        c.execute('''CREATE TABLE IF NOT EXISTS sellers
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      added_by INTEGER,
                      added_date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        # Keys table
        c.execute('''CREATE TABLE IF NOT EXISTS keys
                     (key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      key_code TEXT UNIQUE,
                      duration TEXT,
                      generated_by INTEGER,
                      used_by INTEGER,
                      status TEXT DEFAULT 'active',
                      generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                      expiry_date DATETIME,
                      used_date DATETIME)''')
        
        # Attacks table
        c.execute('''CREATE TABLE IF NOT EXISTS attacks
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      ip TEXT,
                      port INTEGER,
                      duration INTEGER,
                      attack_id TEXT,
                      status TEXT,
                      start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                      end_time DATETIME)''')
        
        # Transactions table
        c.execute('''CREATE TABLE IF NOT EXISTS transactions
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      amount INTEGER,
                      type TEXT,
                      description TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        conn.commit()
        conn.close()
    
    # ============ USER FUNCTIONS ============
    
    def add_user(self, user_id, username):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
        conn.close()
    
    def get_user(self, user_id):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result
    
    def get_all_users(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT user_id, username, balance, is_admin, is_seller, is_active, total_attacks FROM users ORDER BY joined_date DESC")
        users = [{'user_id': row[0], 'username': row[1], 'balance': row[2], 'is_admin': row[3], 'is_seller': row[4], 'is_active': row[5], 'total_attacks': row[6]} for row in c.fetchall()]
        conn.close()
        return users
    
    def get_balance(self, user_id):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    
    def add_balance(self, user_id, amount):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone():
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        else:
            c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, amount if amount > 0 else 0))
        
        c.execute("INSERT INTO transactions (user_id, amount, type) VALUES (?, ?, ?)", 
                 (user_id, amount, 'add' if amount > 0 else 'deduct'))
        
        conn.commit()
        conn.close()
    
    def set_balance(self, user_id, amount):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone():
            c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
        else:
            c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, amount))
        
        conn.commit()
        conn.close()
    
    def remove_user(self, user_id):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def increment_attacks(self, user_id):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("UPDATE users SET total_attacks = total_attacks + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    # ============ ADMIN FUNCTIONS ============
    
    def add_admin(self, user_id, username, added_by):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO admins (user_id, username, added_by) VALUES (?, ?, ?)",
                 (user_id, username, added_by))
        c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def remove_admin(self, user_id):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        c.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def get_all_admins(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT user_id, username FROM admins")
        admins = [{'user_id': row[0], 'username': row[1]} for row in c.fetchall()]
        conn.close()
        return admins
    
    def is_admin(self, user_id):
        from config import OWNER_ID
        if user_id == OWNER_ID:
            return True
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result is not None
    
    # ============ SELLER FUNCTIONS ============
    
    def add_seller(self, user_id, username, added_by):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone():
            c.execute("UPDATE users SET is_seller = 1, is_active = 1 WHERE user_id = ?", (user_id,))
        else:
            c.execute("INSERT INTO users (user_id, username, is_seller, is_active) VALUES (?, ?, ?, ?)", 
                     (user_id, username, 1, 1))
        
        c.execute("INSERT OR REPLACE INTO sellers (user_id, username, added_by) VALUES (?, ?, ?)",
                 (user_id, username, added_by))
        
        conn.commit()
        conn.close()
    
    def remove_seller(self, user_id):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute("UPDATE users SET is_seller = 0 WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM sellers WHERE user_id = ?", (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_all_sellers(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT user_id, username FROM sellers ORDER BY added_date DESC")
        sellers = [{'user_id': row[0], 'username': row[1]} for row in c.fetchall()]
        conn.close()
        return sellers
    
    def is_seller(self, user_id):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT user_id FROM sellers WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result is not None
    
    def get_seller_stats(self, user_id):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = c.fetchone()
        balance = balance[0] if balance else 0
        
        c.execute("SELECT COUNT(*) FROM keys WHERE generated_by = ? AND status = 'active'", (user_id,))
        active_keys = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM keys WHERE generated_by = ?", (user_id,))
        total_keys = c.fetchone()[0]
        
        conn.close()
        return {
            'balance': balance,
            'active_keys': active_keys,
            'total_keys': total_keys
        }
    
    # ============ KEY FUNCTIONS ============
    
    def generate_key(self, duration, generated_by):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        while True:
            key_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            c.execute("SELECT key_code FROM keys WHERE key_code = ?", (key_code,))
            if not c.fetchone():
                break
        
        if duration == "12hr":
            expiry = datetime.now() + timedelta(hours=12)
        elif duration == "1day":
            expiry = datetime.now() + timedelta(days=1)
        elif duration == "1week":
            expiry = datetime.now() + timedelta(days=7)
        elif duration == "15days":
            expiry = datetime.now() + timedelta(days=15)
        elif duration == "1month":
            expiry = datetime.now() + timedelta(days=30)
        else:
            expiry = None
        
        c.execute("INSERT INTO keys (key_code, duration, generated_by, expiry_date) VALUES (?, ?, ?, ?)",
                 (key_code, duration, generated_by, expiry))
        
        conn.commit()
        conn.close()
        return key_code
    
    def redeem_key(self, key_code, user_id):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute("SELECT * FROM keys WHERE key_code = ? AND status = 'active'", (key_code,))
        key = c.fetchone()
        
        if not key:
            conn.close()
            return None, "Invalid or already used key!"
        
        if key[6]:
            expiry_date = datetime.strptime(key[6], '%Y-%m-%d %H:%M:%S.%f')
            if datetime.now() > expiry_date:
                c.execute("UPDATE keys SET status = 'expired' WHERE key_code = ?", (key_code,))
                conn.commit()
                conn.close()
                return None, "Key has expired!"
        
        c.execute("UPDATE keys SET status = 'used', used_by = ?, used_date = CURRENT_TIMESTAMP WHERE key_code = ?",
                 (user_id, key_code))
        
        duration = key[2]
        
        conn.commit()
        conn.close()
        return duration, f"Key redeemed successfully! Duration: {duration}"
    
    def get_keys(self, generated_by=None, used_by=None):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        if generated_by:
            c.execute("SELECT * FROM keys WHERE generated_by = ? ORDER BY generated_date DESC", (generated_by,))
        elif used_by:
            c.execute("SELECT * FROM keys WHERE used_by = ? ORDER BY generated_date DESC", (used_by,))
        else:
            c.execute("SELECT * FROM keys ORDER BY generated_date DESC")
        keys = c.fetchall()
        conn.close()
        return keys
    
    def get_user_active_key_count(self, user_id):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM keys WHERE used_by = ? AND status = 'active'", (user_id,))
        count = c.fetchone()[0]
        conn.close()
        return count
    
    # ============ ATTACK FUNCTIONS ============
    
    def log_attack(self, user_id, ip, port, duration, attack_id, status):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("INSERT INTO attacks (user_id, ip, port, duration, attack_id, status) VALUES (?, ?, ?, ?, ?, ?)",
                 (user_id, ip, port, duration, attack_id, status))
        conn.commit()
        conn.close()
        self.increment_attacks(user_id)
    
    def get_attack_history(self, user_id=None):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        if user_id:
            c.execute("SELECT * FROM attacks WHERE user_id = ? ORDER BY start_time DESC LIMIT 50", (user_id,))
        else:
            c.execute("SELECT * FROM attacks ORDER BY start_time DESC LIMIT 50")
        attacks = c.fetchall()
        conn.close()
        return attacks
    
    def get_active_attacks(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT * FROM attacks WHERE status = 'running' ORDER BY start_time DESC")
        attacks = c.fetchall()
        conn.close()
        return attacks
    
    def update_attack_status(self, attack_id, status):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("UPDATE attacks SET status = ?, end_time = CURRENT_TIMESTAMP WHERE attack_id = ?", (status, attack_id))
        conn.commit()
        conn.close()
    
    # ============ LOG FUNCTIONS ============
    
    def get_logs(self, limit=100):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT ?", (limit,))
        logs = c.fetchall()
        conn.close()
        return logs
    
    def clear_logs(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("DELETE FROM transactions")
        c.execute("DELETE FROM attacks WHERE status = 'finished'")
        conn.commit()
        conn.close()
    
    # ============ STATS FUNCTIONS ============
    
    def get_stats(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM admins")
        total_admins = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM sellers")
        total_sellers = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM attacks")
        total_attacks = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM attacks WHERE status = 'running'")
        running_attacks = c.fetchone()[0]
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE type = 'add'")
        total_balance = c.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_users': total_users,
            'total_admins': total_admins,
            'total_sellers': total_sellers,
            'total_attacks': total_attacks,
            'running_attacks': running_attacks,
            'total_balance': total_balance
        }
