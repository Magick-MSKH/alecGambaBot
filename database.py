# Alec Gamba Bot
# SQLite3 Database
# Stores User Data for GABMA functions

import sqlite3

DB_NAME = "gamba_bot.db"

def init_db():
    """ Creates the database and tables with advanced stat tracking columns """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()

    # Updated USERS table (w/ stat counters!)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            points INTEGER DEFAULT 1000,
            bets_placed INTEGER DEFAULT 0,
            bets_won INTEGER DEFAULT 0,
            bets_lost INTEGER DEFAULT 0,
            highest_peak INTEGER DEFAULT 1000,
            discord_username TEXT DEFAULT NULL,
            prestige_level INTEGER DEFAULT 0
        )
    ''')

    # If the table already existed, ensure the new columns get injected safely
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN bets_placed INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE users ADD COLUMN bets_won INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE users ADD COLUMN bets_lost INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE users ADD COLUMN highest_peak INTEGER DEFAULT 1000")

    except sqlite3.OperationalError:
        pass # Columns already exist, skip safety injection
    
    # Create BETS table
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS bets (
                username TEXT PRIMARY KEY,
                amount INTEGER,
                vote_type TEXT,
                FOREIGN KEY(username) REFERENCES users(username)
            )
        ''')

    # Create CLAIMS table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_claims (
            username TEXT PRIMARY KEY
        )
    ''')
    
    # Create GOALS table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_goals (
            goal_name TEXT PRIMARY KEY,
            points_needed INTEGER,
            points_contributed INTEGER
        )
    ''')

    # Init default goal if table is completely fresh
    cursor.execute("SELECT COUNT(*) FROM global_goals")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO gobal_goals (goal_name, points_needed, points_contributed) VALUES (?, ?, ?)",
            ("no ref WHERE GOAL global_goal FROM VALUE", 9999999, 0)
        )

    # Create PIT table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS money_pit (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            jackpot_total INTEGER DEFAULT 0
        )
    ''')
    
    # Init default pit with 0 points if none exists
    cursor.execute("INSERT OR IGNORE INTO money_pit (id, jackpot_total) VALUES (1, 0)")

    # Tracks master state of gamba config
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gamba_session_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            status TEXT DEFAULT 'CLOSED', -- CLOSED, OPEN, LOCKED
            description TEXT DEFAULT '',
            options_csv TEXT DEFAULT '',   -- e.g. "win,lose" or "yes,no"
            total_pool INTEGER DEFAULT 0
        )
    ''')

    # Tracks individual live wagers locked in pool
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gamba_active_bets (
            username TEXT PRIMARY KEY,
            chosen_option TEXT NOT NULL,
            wager_amount INTEGER NOT NULL
        )
    ''')
    
    # Guarantee that default row 1 exists for the state checker tracker
    cursor.execute("SELECT COUNT(*) FROM gamba_session_state")
    if cursor.fetchone() == 0:
        cursor.execute("INSERT INTO gamba_session_state (id) VALUES (1)")
    
    conn.commit()
    conn.close()

def get_balance(username):
    """ Gets a user's current balance. Registers them with full stat tracking columns if new """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()

    cursor.execute("SELECT points FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()

    if row is None:
        cursor.execute('''
            INSERT INTO users (username, points, bets_placed, bets_won, bets_lost, highest_peak)
            VALUES (?, 1000, 0, 0, 0, 1000)
        ''', (username,))
        conn.commit()
        balance = 1000
    else:
        balance = row[0]

    conn.close()
    return balance

def place_bet(username, amount, vote_type):
    """ Deduces points and logs a bet if the user has enough currency """
    balance = get_balance(username)

    if balance < amount:
        return False, f"❌ You only have {balance} points!"
    
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()

    try:
        # Check if they already have an active bet
        cursor.execute("SELECT amount FROM bets WHERE username =?", (username,))
        if cursor.fetchone():
            return False, "❌ You already have an active bet!"
        
        # Deduct points from user
        cursor.execute("UPDATE users SET points = points - ? WHERE username = ?", (amount, username))
        # Insert into BETS table
        cursor.execute("INSERT INTO bets (username, amount, vote_type) VALUES (?, ?, ?)", (username, amount, vote_type))
        # Hook Statistics into the Gamba Loop
        cursor.execute("UPDATE users SET bets_placed = bets_placed + 1 WHERE username = ?", (username,))
        conn.commit()

        return True, f"[💎] Bet placed! {amount} points on '{vote_type}'."

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO gamba_active_bets (username, chosen_option, wager_amount)
                VALUES (?, ?, ?)
            ''', (username, vote, amount))
            cursor.execute("UPDATE gamba_session_state SET total_pool = total_pool + ? WHERE id = 1", (amount,))
        except Exception as e:
            print(f"⚠️ Crash recorder sync warning: {e}")
    
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def resolve_bets(winning_type):
    """Pays out winners, logs win/loss stats, updates peaks, and clears pool cleanly."""
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    
    try:
        # 1. Update Losers first (everyone whose vote_type DOES NOT match)
        cursor.execute(
            "UPDATE users SET bets_lost = bets_lost + 1 WHERE username IN (SELECT username FROM bets WHERE vote_type != ?)", 
            (winning_type,)
        )
        
        # 2. Get and Process Winners
        cursor.execute("SELECT username, amount FROM bets WHERE vote_type = ?", (winning_type,))
        winners = cursor.fetchall()
        
        # 3. Pay back double the bet amount to winners and update win counts
        for username, amount in winners:
            payout = amount * 2
            cursor.execute("UPDATE users SET points = points + ?, bets_won = bets_won + 1 WHERE username = ?", (payout, username))
            
            # instead of calling a separate function that opens a new connection!
            cursor.execute("UPDATE users SET highest_peak = points WHERE username = ? AND points > highest_peak", (username,))
            
        # 4. Clear the active bets pool table clean
        cursor.execute("DELETE FROM bets")
        
        # Commit ALL updates together in one single transaction block
        conn.commit()
        return len(winners)
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Database resolve error: {e}")
        return 0
    finally:
        # Safely shut down the connection so main.py can read chat again
        conn.close()


def add_points(username, amount):
    """ Adds (or subtracts) points for a specific user """
    # Calling get_balance ensures they exist in the DB (Database) first
    get_balance(username)

    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = points + ? WHERE username = ?", (amount, username))
    conn.commit()
    conn.close()

    # Check if the free/admin points created a new historical peak record
    update_peak_balance(username)

def add_points_to_multiple(usernames, amount):
    """ Efficiently gives passive points to a list of active users at once """
    if not usernames:
        return
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()

    # Safely format (?, ?, ?) for SQL mass update
    format_strings = ','.join('?' for _ in usernames)
    cursor.execute(f"UPDATE users SET points = points + ? WHERE username IN ({format_strings})", [amount] + list(usernames))
    conn.commit()
    conn.close()

def cancel_and_refund_bets():
    """ Cancels the current betting round and returns all points to the users """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()

    try:
        # 1. Fetch everyone currently locked into a bet
        cursor.execute("SELECT username, amount FROM bets")
        active_bets = cursor.fetchall()

        if not active_bets:
            return 0, "❗ No active bets to refund!"
        
        # 2. Return points back to each user
        for username, amount in active_bets:
            cursor.execute("UPDATE users SET points = points + ? WHERE username = ?", (amount, username))

        # 3. Wipe the BETS table clean
        cursor.execute("DELETE FROM bets")

        conn.commit()
        return len(active_bets), f"[&] Bet cancelled! Refunded points to {len(active_bets)} users."
    
    except Exception as e:
        conn.rollback()
        return 0, f"Error during refund: {str(e)}"
    finally:
        conn.close()

def get_top_users(limit=5):
    """ Fetches the top X richets players from the database """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()

    cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT ?", (limit,))
    top_users = cursor.fetchall()

    conn.close()
    return top_users

def add_points_to_all_registered(amount):
    """ Adds an arbitrary amount of points to every user stored in the db """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()

    # Update every single row in the users table simultaneously
    cursor.execute("UPDATE users SET points = points + ?", (amount,))

    conn.commit()
    conn.close()

def update_peak_balance(username):
    """ Checks if current points beat the user's previous high score """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET highest_peak = points WHERE username = ? AND points > highest_peak", (username,))
    conn.commit()
    conn.close()

def get_player_stats(username):
    """ Fetches full stat card details for a sepcific viewer """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()

    cursor.execute("SELECT points, bets_placed, bets_won, bets_lost, highest_peak FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        get_balance(username)
        return (1000, 0, 0, 0, 1000)

    return row

def get_all_time_peak_record():
    """ Finds the absolute highest points record ever held in the database and who achieved it """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT username, highest_peak FROM users ORDER BY highest_peak DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row

def check_daily_claimed(username):
    """ Checks if user already claimed their daily points """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM daily_claims WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def record_daily_claim(username):
    """ Log user's daily claim into session table """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO daily_claims (username) VALUES (?)", (username,))
    conn.commit()
    conn.close()

def clear_daily_claims():
    """ Wipe session table on bot start """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM daily_claims")
    conn.commit()
    conn.close()

def get_active_goal():
    """ Fetches current goal data """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT goal_name, points_needed, points_contributed FROM global_goals LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row

def contribute_to_goal(amount):
    """ INC current active goal """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE global_goals SET points_contributed = points_contributed + ?", (amount,))
    conn.commit()
    conn.close()

def set_new_global_goal(new_name, points_needed):
    """ Wipes the old goal and inserts a fresh community challenge line """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    # Wipe the existing active row
    cursor.execute("DELETE FROM global_goals")
    # Insert the new challenge configuration
    cursor.execute(
        "INSERT INTO global_goals (goal_name, points_needed, points_contributed) VALUES (?, ?, 0)",
        (new_name, points_needed)
    )
    conn.commit()
    conn.close()

def get_pit_total():
    """ Fetches the current point balance inside the money pit """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT jackpot_total FROM money_pit WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def add_to_pit(amount):
    """ Increments the global money pit pool """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE money_pit SET jackpot_total = jackpot_total + ? WHERE id = 1", (amount,))
    conn.commit()
    conn.close()

def reset_pit():
    """ Wipes the money pit to an empty slate """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE money_pit SET jackpot_total = 0 WHERE id = 1")
    conn.commit()
    conn.close()

def save_gamba_session(status, description, options_list):
    """ Mirrors top-level active gambling phase straight into SQLite RAM backup """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    options_csv = ",".join(options_list)
    cursor.execute('''
        UPDATE gamba_session_state 
        SET status = ?, description = ?, options_csv = ?, total_pool = 0 
        WHERE id = 1
    ''', (status, description, options_csv))
    # Clear leftover legacy bets from previous pool
    cursor.execute("DELETE FROM gamba_active_bets")
    conn.commit()
    conn.close()

def record_live_bet(username, option, amount):
    """ Locks individual user's point stake into persistent backup """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO gamba_active_bets (username, chosen_option, wager_amount)
        VALUES (?, ?, ?)
    ''', (username, option, amount))
    cursor.execute("UPDATE gamba_session_state SET total_pool = total_pool + ? WHERE id = 1", (amount,))
    conn.commit()
    conn.close()

def clear_persistent_gamba():
    """ Wipes recovery ledger once gamba payout loop finishes """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE gamba_session_state SET status = 'CLOSED', total_pool = 0 WHERE id = 1")
    cursor.execute("DELETE FROM gamba_active_bets")
    conn.commit()
    conn.close()

def recover_gamba_session_from_crash():
    """ Queries database to rebuild global dictionary state & player pools instantly upon unexpected bot boot script reload """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute("SELECT status, description, options_csv FROM gamba_session_state WHERE id = 1")
    state_row = cursor.fetchone()
    
    if not state_row or state_row[0] == 'CLOSED':
        conn.close()
        return None
        
    status, description, options_csv = state_row
    options_list = options_csv.split(",") if options_csv else []
    
    # Fetch all live bets that were recorded before the crash
    cursor.execute("SELECT username, chosen_option, wager_amount FROM gamba_active_bets")
    bet_rows = cursor.fetchall()
    conn.close()
    
    return {
        "status": status,
        "description": description,
        "options": options_list,
        "bets": bet_rows
    }

def mirror_gamba_session_state(status, description, options_list):
    """ Saves top-level active gambling phase into SQLite backup table.
        Clears leftover legacy wagers from previous round automatically """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    options_csv = ",".join(options_list) if options_list else ""
    cursor.execute('''
        UPDATE gamba_session_state 
        SET status = ?, description = ?, options_csv = ?, total_pool = 0 
        WHERE id = 1
    ''', (status, description, options_csv))
    cursor.execute("DELETE FROM gamba_active_bets")
    conn.commit()
    conn.close()

def link_discord_username(youtube_handle, discord_name):
    """ Binds Discord username to YT Username """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    yt = youtube_handle.strip()
    ds = discord_name.strip().lower

    cursor.execute("UPDATE users SET discord_username = ? WHERE LOWER(username) = LOWER(?)", (ds,yt))
    changes = conn.total_changes
    conn.commit()
    conn.close()
    return changes > 0

def get_youtube_handle_from_discord(discord_name):
    """ Lookup table to determine YT & DC handles. Returns YT username string if found, else None """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    ds = discord_name.strip().lower()

    cursor.execute("SELECT username FROM users WHERE LOWER(discord_username) = ?", (ds,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

PRESTIGE_LOOKUP_TABLE = {
    0: {"cost": 100000,  "multiplier": 2}, # Level 0 -> 1: Cost = 100k, Rewards * 2;
    1: {"cost": 500000,  "multiplier": 3}, # Level 1 -> 2: Cost = 500k, Rewards * 3;
    2: {"cost": 1000000, "multiplier": 4}, # Level 2 -> 3: Cost = 1Mil, Rewards * 4;
    3: {"cost": 2000000, "multiplier": 5}, # Level 3 -> 4: Cost = 2Mil, Rewards * 5;
    4: {"cost": 5000000, "multiplier": 6}  # Level 4 -> 5: Cost = 5Mil, Rewards * 6;
}

def execute_user_prestige(username):
    """ Validate user points, wipe active balance, increment Prestige Rank, return new level """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()

    cursor.execute("SELECT points, prestige_level FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"status": "NOT_FOUND"}
    
    current_points, current_level = row
    if current_level >= 5:
        conn.close()
        return {"status": "MAX_CAP"}
    
    target_tier = PRESTIGE_LOOKUP_TABLE[current_level]
    required_points = target_tier["cost"]

    if current_points < required_points:
        conn.close()
        return {"status": "LOW_POINTS", "needed": required_points}

    new_level = current_level + 1

    cursor.execute('''
        UPDATE users
        SET points = 0, prestige_level = ?
        WHERE LOWER(username) = LOWER(?)
    ''', (new_level, username.strip()))

    conn.commit()
    conn.close()

    return {"status": "SUCCESS", "new_level": new_level, "multiplier": target_tier["multiplier"]}

def get_prestige_level(username):
    """ Get player prestige level to apply point multiplier inquiries """
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT prestige_level FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),))
    row = cursor.fetchone()
    conn.close()
    return row[0] if now and row[0] else 0

def get_user_prestige_level(username):
    """ Used for point multiplier calculations """
    current_level = get_prestige_level(username)
    if current_level == 0:
        return 1
    
    return PRESTIGE_LOOKUP_TABLE[current_level - 1]["multiplier"]