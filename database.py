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
            
            # FIX THE LOCK: Run the peak balance check directly on THIS active cursor
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

def get_current_pool_info():
    """ Returns a formatted string of the active betting pool for public checks """
    if not IS_BETTING_OPEN:
        return "🎲 No active betting pool is open right now."

    # Checks to see if the pool has been locked manually by a mod/admin
    status_label = "🔒 LOCKED!" if IS_BETTING_LOCKED else "🔓 OPEN!"

    return (f"🎰 ACTIVE POOL [{status_label}]: {CURRENT_QUESTION} | 📋 CHOICES: {', '.join(VALID_OPTIONS)} | 👉 Type !gamba [amount] [option] to play!")
