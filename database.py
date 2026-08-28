import sqlite3

def init_db():
    conn = sqlite3.connect("bot_chat_lgbt.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            gender TEXT,
            target_gender TEXT,
            age INTEGER,
            status TEXT DEFAULT 'setup_gender',
            partner_id INTEGER DEFAULT NULL,
            reports INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect("bot_chat_lgbt.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, status) VALUES (?, ?, 'setup_gender')", (user_id, username))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("bot_chat_lgbt.db")
    cursor = conn.cursor()
    cursor.execute("SELECT gender, target_gender, age, status, partner_id, reports, is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_user_field(user_id, field, value):
    conn = sqlite3.connect("bot_chat_lgbt.db")
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def set_user_status(user_id, status, partner_id=None):
    conn = sqlite3.connect("bot_chat_lgbt.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ?, partner_id = ? WHERE user_id = ?", (status, partner_id, user_id))
    conn.commit()
    conn.close()

def increment_reports(user_id):
    conn = sqlite3.connect("bot_chat_lgbt.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET reports = reports + 1 WHERE user_id = ?", (user_id,))
    cursor.execute("SELECT reports FROM users WHERE user_id = ?", (user_id,))
    reports = cursor.fetchone()[0]
    if reports >= 5:
        cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return reports >= 5

def find_partner(current_user_id):
    conn = sqlite3.connect("bot_chat_lgbt.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT gender, target_gender FROM users WHERE user_id = ?", (current_user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return None
    
    my_gender, my_target = user
    
    cursor.execute("""
        SELECT user_id, gender, target_gender FROM users 
        WHERE status = 'searching' AND user_id != ? AND is_banned = 0
    """, (current_user_id,))
    candidates = cursor.fetchall()
    conn.close()
    
    for cand_id, cand_gender, cand_target in candidates:
        target_match = (cand_target == 'any' or cand_target == my_gender)
        my_match = (my_target == 'any' or my_target == cand_gender)
        
        if target_match and my_match:
            return cand_id
            
    return None
