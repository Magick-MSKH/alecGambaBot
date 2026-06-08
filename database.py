# Alec Gamba Bot
# SQLite3 Database
# Stores User Data for GABMA functions

import sqlite3

DB_NAME = "gamba_bot.db"

def init_db():
    """ Creates the database and tables with advanced stat tracking columns """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Updated USERS table (w/ stat counters!)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            points INTEGER DEFAULT 1000,
            bets_placed INTEGER DEFAULT 0,
            bets_won INTEGER DEFAULT 0,
            bets_lost INTEGER DEFAULT 0,
            highest_peak INTEGER DEFAULT 1000
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
    cursor.execute("SELECET COUNT(*) FROM global_goals")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO gobal_goals (goal_name, points_needed, points_contributed) VALUES (?, ?, ?)",
            ("NO REF WHERE GOAL global_goals VALUE", 9999999, 0)
        )

    conn.commit()
    conn.close()

def get_balance(username):
    """ Gets a user's current balance. Registers them with full stat tracking columns if new """
    conn = sqlite3.connect(DB_NAME)
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
    
    conn = sqlite3.connect(DB_NAME)
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
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def resolve_bets(winning_type):
    """Pays out winners, logs win/loss stats, updates peaks, and clears pool cleanly."""
    conn = sqlite3.connect(DB_NAME)
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

    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Safely format (?, ?, ?) for SQL mass update
    format_strings = ','.join('?' for _ in usernames)
    cursor.execute(f"UPDATE users SET points = points + ? WHERE username IN ({format_strings})", [amount] + list(usernames))
    conn.commit()
    conn.close()

def cancel_and_refund_bets():
    """ Cancels the current betting round and returns all points to the users """
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT ?", (limit,))
    top_users = cursor.fetchall()

    conn.close()
    return top_users

def add_points_to_all_registered(amount):
    """ Adds an arbitrary amount of points to every user stored in the db """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Update every single row in the users table simultaneously
    cursor.execute("UPDATE users SET points = points + ?", (amount,))

    conn.commit()
    conn.close()

def update_peak_balance(username):
    """ Checks if current points beat the user's previous high score """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET highest_peak = points WHERE username = ? AND points > highest_peak", (username,))
    conn.commit()
    conn.close()

def get_player_stats(username):
    """ Fetches full stat card details for a sepcific viewer """
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, highest_peak FROM users ORDER BY highest_peak DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row

def check_daily_claimed(username):
    """ Checks if user already claimed their daily points """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM daily_claims WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def record_daily_claim(username):
    """ Log user's daily claim into session table """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO daily_claims (username) VALUES (?)", (username,))
    conn.commit()
    conn.close()

def clear_daily_claims():
    """ Wipe session table on bot start """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM daily_claims")
    conn.commit()
    conn.close()

def get_active_goal():
    """ Fetches current goal data """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT goal_name, points_needed, points_contributed FROM global_goals LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row

def contribute_to_goal(amount):
    """ INC current active goal """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE global_goals SET points_contributed = points_contributed + ?", (amount,))
    conn.commit()
    conn.close()

def set_new_global_goal(new_name, points_needed):
    """ Wipes the old goal and inserts a fresh community challenge line """
    conn = sqlite3.connect(DB_NAME)
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