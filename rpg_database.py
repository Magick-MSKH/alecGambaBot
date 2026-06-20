import sqlite3
import gspread
import database

RPG_DB_NAME = "rpg_engine.db"

def init_rpg_db():
    """ Initializes the structural table schemas for the modular RPG engine """
    conn = sqlite3.connect(RPG_DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS characters (
            username TEXT PRIMARY KEY,
            class_name TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            gold INTEGER DEFAULT 0,
            current_hp REAL,
            max_hp REAL,      
            current_mp REAL,
            max_mp REAL,      
            stamina INTEGER DEFAULT 3,
            base_str REAL,
            base_dex REAL,
            base_int REAL,
            base_vit REAL,
            base_eng REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            username TEXT PRIMARY KEY,
            main_hand TEXT DEFAULT 'None',
            off_hand TEXT DEFAULT 'None',
            body_armor TEXT DEFAULT 'None',
            headgear TEXT DEFAULT 'None',
            gloves TEXT DEFAULT 'None',
            boots TEXT DEFAULT 'None',
            belt TEXT DEFAULT 'None',
            ring_1 TEXT DEFAULT 'None',
            ring_2 TEXT DEFAULT 'None',
            amulet TEXT DEFAULT 'None',
            charm TEXT DEFAULT 'None',
            FOREIGN KEY(username) REFERENCES characters(username)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_world_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            normal_kills_count INTEGER DEFAULT 0,
            boss_status TEXT DEFAULT 'DEAD',
            boss_name TEXT DEFAULT 'None',
            boss_current_hp INTEGER DEFAULT 0,
            boss_max_hp INTEGER DEFAULT 0,
            boss_is_unique INTEGER DEFAULT 0
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM global_world_state")
    if cursor.fetchone() == 0:
        cursor.execute("INSERT INTO global_world_state (id) VALUES (1)")

    conn.commit()
    conn.close()
    print("⚔️ RPG Core Engine database initialized.")

def fetch_class_base_stats(class_name):
    try:
        gc = gspread.service_account(filename="credentials.json")
        sh = gc.open("RPGConfig")
        worksheet = sh.get_worksheet(0)
        records = worksheet.get_all_records()
        
        for row in records:
            if row["Class"].strip().lower() == class_name.strip().lower():
                return {
                    "hp": int(row["HP"]),
                    "mp": int(row["MP"]),
                    "str": int(row["STR"]),
                    "dex": int(row["DEX"]),
                    "int": int(row["INT"]),
                    "vit": int(row["VIT"]),
                    "eng": int(row["ENG"])
                }
    except Exception as e:
        print(f"🕹️⚠️ [SHEETS ERROR] Failed to fetch stats: {e}.")
    
    fallback_stats = {
        "warrior": {"hp": 10, "mp": 0, "str": 7, "dex": 4, "int": 2, "vit": 5, "eng": 2},
        "wizard":  {"hp": 8, "mp": 5, "str": 1, "dex": 3, "int": 7, "vit": 3, "eng": 6},
        "archer":  {"hp": 8, "mp": 4, "str": 3, "dex": 8, "int": 2, "vit": 3, "eng": 4},
        "valkyrie":{"hp": 6, "mp": 6, "str": 4, "dex": 4, "int": 4, "vit": 4, "eng": 4}
    }
    return fallback_stats.get(class_name.lower(), fallback_stats["Class"])

def register_new_character(username, chosen_class):
    valid_classes = ["warrior", "wizard", "archer", "valkyrie"]
    if chosen_class.lower() not in valid_classes:
        return f"🕹️❌ Unknown class! Available classes: Warrior, Wizard, Archer, Valkyrie."

    conn = sqlite3.connect(RPG_DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT class_name FROM characters WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return f"🕹️❌ You already have a character profile."

    creation_cost = 5000
    user_balance = database.get_balance(username)
    if user_balance < creation_cost:
        conn.close()
        return f"🕹️❌ Character creation costs {creation_cost:,} points! Current balance: {user_balance:,}"

    # Read independent flat HP/MP and attributes directly from the sheet
    stats = fetch_class_base_stats(chosen_class)

    database.add_points(username, -creation_cost)
    
    # Store explicit Max/Current stats
    cursor.execute('''
        INSERT INTO characters (
            username, class_name, current_hp, max_hp, current_mp, max_mp, 
            base_str, base_dex, base_int, base_vit, base_eng
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        username, chosen_class.capitalize(), stats["hp"], stats["hp"], stats["mp"], stats["mp"], 
        stats["str"], stats["dex"], stats["int"], stats["vit"], stats["eng"]
    ))
    
    cursor.execute('INSERT INTO inventory (username) VALUES (?)', (username,))
    conn.commit()
    conn.close()

    try:
        gc = gspread.service_account(filename="credentials.json")
        sh = gc.open("RPGConfig")
        worksheet = sh.worksheet("RPGRawCharData")
        
        # Row format mapping: Username, Class, Level, XP, Gold, HP, Max_HP, MP, Max_MP, STR, DEX, INT, VIT, ENG
        new_row = [
            username, chosen_class.capitalize(), 1, 0, 0, 
            stats["hp"], stats["hp"], stats["mp"], stats["mp"],
            stats["str"], stats["dex"], stats["int"], stats["vit"], stats["eng"]
        ]
        worksheet.append_row(new_row)
    except Exception as e:
        print(f"⚠️ [SPREADSHEET SYNC ERROR] Failed to push new character to sheet: {e}")
    
    return f"🕹️📃 CLASS REGISTERED! {username} paid {creation_cost:,} points and rose as a Level 1 {chosen_class.capitalize()}!"

def deposit_to_gheed(username, amount_str):
    """ Converts channel points into Gold via Gheed """
    conn = sqlite3.connect(RPG_DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT gold FROM characters WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return f"🕹️❌ You don't have a character. Type !create [class] first."

    try:
        if amount_str == "all":
            amount = database.get_balance(username)
        else:
            amount = int(amount_str)

        if amount <= 0:
            conn.close()
            return "🕹️❌ Gheed doesn't deal in empty promises."

        stream_bal = database.get_balance(username)
        if stream_bal < amount:
            conn.close()
            return f"🕹️❌ You don't have enough channel points! Point Balance: {stream_bal:,}"

        database.add_points(username, -amount)
        cursor.execute("UPDATE characters SET gold = gold + ? WHERE username = ?", (amount, username))
        conn.commit()
        
        cursor.execute("SELECT gold FROM characters WHERE username = ?", (username,))
        new_gold = cursor.fetchone()[0]
        conn.close()
        
        return f"🕹️💰 [GHEED TRANSACTION] {username} handed Gheed {amount:,} channel points. 🪙 Gheed gives {amount:,} gold pieces! Total Gold: {new_gold:,}"

    except ValueError:
        conn.close()
        return "🕹️❌ Usage: !bank deposit [amount] or !bank deposit all"


def fetch_class_stat_growth(class_name):
    """
    Connects to RPGConfig to extract level-up metrics.
    Falls back to your precise decimal growth blueprint matrix.
    """
    try:
        gc = gspread.service_account(filename="credentials.json")
        sh = gc.open("RPGConfig")
        worksheet = sh.worksheet("RPGConfig")
        records = worksheet.get_all_records()
        
        for row in records:
            if row.get("Class", "").strip().lower() == f"{class_name.lower()}_growth":
                return {
                    "hp": float(row["HP"]), "mp": float(row["MP"]),
                    "str": float(row["STR"]), "dex": float(row["DEX"]),
                    "int": float(row["INT"]), "vit": float(row["VIT"]), "eng": float(row["ENG"])
                }
    except Exception as e:
        print(f"⚠️ [GROWTH SHEET ERROR] Falling back to precise blueprint matrix: {e}")

    # Your exact blueprint data preserved with fractional parameters
    fallbacks = {
        "warrior":  {"hp": 1.0, "mp": 0.2, "str": 2.0,  "dex": 1.0,  "int": 0.2,  "vit": 1.0, "eng": 0.0},
        "wizard":   {"hp": 0.5, "mp": 1.0, "str": 0.2,  "dex": 0.25, "int": 2.0,  "vit": 1.0, "eng": 2.0},
        "archer":   {"hp": 0.5, "mp": 0.5, "str": 0.25, "dex": 2.0,  "int": 0.5,  "vit": 1.0, "eng": 1.0},
        "valkyrie": {"hp": 0.5, "mp": 0.5, "str": 0.5,  "dex": 0.5,  "int": 0.5,  "vit": 0.5, "eng": 0.5}
    }
    return fallbacks.get(class_name.lower(), fallbacks["warrior"])

def check_and_execute_level_up(username):
    """
    Checks XP boundaries, applies growth decimals, completely restores resources,
    and returns a clean whole-integer summary announcement for stream chat.
    """
    conn = sqlite3.connect(RPG_DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT class_name, level, xp, max_hp, max_mp, base_str, base_dex, base_int, base_vit, base_eng 
        FROM characters WHERE username = ?
    ''', (username,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return ""

    c_class, lvl, xp, max_hp, max_mp, b_str, b_dex, b_int, b_vit, b_eng = row
    xp_needed = lvl * 5
    
    if xp >= xp_needed:
        new_lvl = lvl + 1
        remaining_xp = xp - xp_needed
        
        growth = fetch_class_stat_growth(c_class)
        
        # Accumulate the fractional growth numbers cleanly in memory
        new_max_hp = max_hp + growth["hp"]
        new_max_mp = max_mp + growth["mp"]
        new_str = b_str + growth["str"]
        new_dex = b_dex + growth["dex"]
        new_int = b_int + growth["int"]
        new_vit = b_vit + growth["vit"]
        new_eng = b_eng + growth["eng"]

        # Save the full floats to the database, fully restoring current resources to the new ceiling
        cursor.execute('''
            UPDATE characters 
            SET level = ?, xp = ?, max_hp = ?, current_hp = ?, max_mp = ?, current_mp = ?,
                base_str = ?, base_dex = ?, base_int = ?, base_vit = ?, base_eng = ?
            WHERE username = ?
        ''', (new_lvl, remaining_xp, new_max_hp, new_max_hp, new_max_mp, new_max_mp,
              new_str, new_dex, new_int, new_vit, new_eng, username))
        conn.commit()
        conn.close()
        
        # TRUNCATION: Use int() to display clean, whole integers to the chat box!
        return (
            f" ✨ LEVEL UP! {username} reached Level {new_lvl}! "
            f"❤️ HP: {int(new_max_hp)} | 🔮 MP: {int(new_max_mp)} | "
            f"💪 STR: {int(new_str)} | 🎯 DEX: {int(new_dex)} ✨"
        )
        
    conn.close()
    return ""
