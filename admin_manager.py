import time
import database
import sheets_sync

# Ensure your actual YouTube channel ID or username strings are in here
ADMIN_IDS = ["UCHpI9dGQrVLLCMv-raEoJ7w", "UCa1X6pPmo2pFomK9T308BKg", "UCbs1mvFRAd_D7ATvWIFPG0g", "UCkYwhjg79txij8wDA-Jiv5Q", "UCncmqSbJ6bm6EekhTvwf-nw"] # @magicmskh, @barelyalec, @notalecprobably, @larrryft, @xddkai

# Live in-memory tracking of the current betting state
IS_BETTING_OPEN = False
IS_BETTING_LOCKED = False  # NEW: Simple boolean flag to stop entries
HAS_ANNOUNCED_LOCK = False
VALID_OPTIONS = []
CURRENT_QUESTION = ""

def process_admin_command(sender_id, sender_name, message_text):
    """
    Parses chat messages from stream admins to manage betting states manually.
    """
    global IS_BETTING_OPEN, IS_BETTING_LOCKED, VALID_OPTIONS, CURRENT_QUESTION, HAS_ANNOUNCED_LOCK

    if not message_text.startswith("!"):
        return None

    # Security Check: Block non-admins instantly
    if sender_id not in ADMIN_IDS and sender_name not in [
        "magickmskh",
        "ConsoleAdmin",
        "BarelyAlec",
        "NotAlecprobably",
        "larrryft",
        "xddkai"
        ]:
        return None

    parts = message_text.split()
    command = parts[0].lower()

    # ==========================================
    # COMMAND 1: !gamba_open [option1,option2] [Question text...]
    # ==========================================
    if command == "!gamba_open":
        if len(parts) < 3:
            return "⚠️ Usage: !gamba_open [option1,option2] [Question text...]"
        
        if IS_BETTING_OPEN:
            return f"⚠️ A betting round is already active: '{CURRENT_QUESTION}'"

        VALID_OPTIONS = [opt.strip().lower() for opt in parts[1].split(",")]
        CURRENT_QUESTION = " ".join(parts[2:])
        
        IS_BETTING_OPEN = True
        IS_BETTING_LOCKED = False  # Reset lock for the new round
        
        return f"🎰 BETTING OPENED! 🎰 | ❓ Question: {CURRENT_QUESTION} | 📋 Valid Options: {', '.join(VALID_OPTIONS)} | 👉 Type !gamba [amount] [option] to enter!"

    # ==========================================
    # COMMAND 2: !gamba_lock (NEW MANUAL LOCK)
    # ==========================================
    elif command == "!gamba_lock":
        if not IS_BETTING_OPEN:
            return "⚠️ There is no active betting pool open to lock."
        if IS_BETTING_LOCKED:
            return "⚠️ Betting is already locked!"

        IS_BETTING_LOCKED = True
        return "🔒 TIME IS UP! Betting is now officially LOCKED. No more entries will be accepted! 🔒"

    # ==========================================
    # COMMAND 3: !gamba_win [winning_option]
    # ==========================================
    elif command == "!gamba_win":
        if not IS_BETTING_OPEN:
            return "⚠️ There is no active betting pool to resolve right now."
        
        if len(parts) < 2:
            return f"⚠️ Usage: !gamba_win [option] (Valid options are: {', '.join(VALID_OPTIONS)})"
            
        winning_choice = parts[1].lower()
        if winning_choice not in VALID_OPTIONS:
            return f"❌ Invalid option. Choose from: {', '.join(VALID_OPTIONS)}"

        winners_paid = database.resolve_bets(winning_choice)
        
        # Reset everything back to default clean slate
        IS_BETTING_OPEN = False
        IS_BETTING_LOCKED = False
        VALID_OPTIONS = []
        CURRENT_QUESTION = ""
        
        return f"🏆 BET RESOLVED! The winning choice was '{winning_choice}'. Paid out 2x to {winners_paid} winners! 💰"

    # ==========================================
    # COMMAND 4: !gamba_cancel
    # ==========================================
    elif command == "!gamba_cancel":
        if not IS_BETTING_OPEN:
            return "⚠️ There is no active betting pool to cancel."

        count, refund_msg = database.cancel_and_refund_bets()
        
        IS_BETTING_OPEN = False
        IS_BETTING_LOCKED = False
        VALID_OPTIONS = []
        CURRENT_QUESTION = ""
        
        return f"🔄 BET CANCELLED: All points have been safely returned to players."

    # ==========================================
    # COMMAND 5: !give [username] [amount]
    # ==========================================
    elif command == "!give":
        if len(parts) < 3:
            return "⚠️ Usage: !give [username] [amount]"
            
        target_username = parts[1]
        try:
            amount = int(parts[2])
            database.add_points(target_username, amount)
            new_balance = database.get_balance(target_username)
            return f"🎁 Awarded {amount} points to {target_username}! New balance: {new_balance}"
        except ValueError:
            return "❌ Error: Amount must be a whole number."
            
    # ==========================================
    # COMMAND 6: !reset_user [username]
    # ==========================================
    
    elif command == "!reset_user":
        if len(parts) < 2:
            return "⚠️ Usage: !reset_user [username]"
            
        target_username = parts[1]
        
        try:
            database.add_points(target_username, 0) # Ensures user exists in DB first
            conn = database.sqlite3.connect(database.DB_NAME)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET points = 1000 WHERE username = ?", (target_username,))
            conn.commit()
            conn.close()
        
            return f"🔄 Reset points for {target_username}."

        except Exception as e:
            return f"❌ Reset error: {str(e)}"
    

    # ==========================================
    # COMMAND 7: !give_all [amount]
    # ==========================================

    elif command == "!give_all":
        if len(parts) < 2:
            return "⚠️ Usage: !give_all [amount]"

        amount_str = parts[1]
        try:
            amount = int(amount_str)

            # Execute the mass update in the database
            database.add_points_to_all_registered(amount)

            # Trigger immediate Google Sheets sync so the leaderboard updates
            import sheets_sync
            sheets_sync.sync_to_google_sheets()

            return f"🎉 Giving {amount} points to ALL users! 🎁"

        except ValueError:
            return "❌ Error: Amount must be an integer."
        except Exception as e:
            return f"❌ Database error: {str(e)}"

    return None

def get_current_pool_info():
    """ Returns a formatted string of the active betting pool for public checks """
    if not IS_BETTING_OPEN:
        return "🎲 No active betting pool is open right now."

    # Checks to see if the pool has been locked manually by a mod/admin
    status_label = "🔒 LOCKED!" if IS_BETTING_LOCKED else "🟢 OPEN!"

    return (f"🎰 ACTIVE POOL {status_label}: {CURRENT_QUESTION} | 📋 CHOICES: {', '.join(VALID_OPTIONS)} | 👉 Type !gamba [amount] [option] to play!")