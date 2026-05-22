import time
import database

# Ensure your actual YouTube channel ID or username strings are in here
ADMIN_IDS = ["UCHpI9dGQrVLLCMv-raEoJ7w", "UCa1X6pPmo2pFomK9T308BKg", "UCbs1mvFRAd_D7ATvWIFPG0g", "UCkYwhjg79txij8wDA-Jiv5Q"] # @magicmskh, @barelyalec, @notalecprobably, @larrryft

# Live in-memory tracking of the current betting state
IS_BETTING_OPEN = False
VALID_OPTIONS = []
CURRENT_QUESTION = ""
BET_OPEN_TIMESTAMP = 0
BET_DURATION_SECONDS = 300
HAS_ANNOUNCED_LOCK = False

def process_admin_command(sender_id, sender_name, message_text):
    """
    Parses chat messages from stream admins to open, close, and manage betting states.
    """
    global IS_BETTING_OPEN, VALID_OPTIONS, CURRENT_QUESTION

    # Ignore messages that aren't admin commands
    if not message_text.startswith("!"):
        return None

    # Security Check: Block non-admins instantly
    if sender_id not in ADMIN_IDS and sender_name not in [
        "magickmskh",
        "ConsoleAdmin",
        "BarelyAlec",
        "NotAlecprobably",
        "larrryft"
        ]:
        return None  # Return None quietly so non-admins don't trigger error spam

    parts = message_text.split()
    command = parts[0].lower()

    # ==========================================
    # COMMAND 1: !gamba_open [option1,option2] [Question text...]
    # Example: !gamba_open yes,no Will Alec clutch this level?
    # ==========================================

    if command == "!gamba_open":
        if len(parts) < 3:
            return "⚠️ Usage: !gamba_open [option1,option2] [Question text...]"
        
        if IS_BETTING_OPEN:
            return f"⚠️ A betting round is already active: '{CURRENT_QUESTION}'"

        VALID_OPTIONS = [opt.strip().lower() for opt in parts[1].split(",")]
        CURRENT_QUESTION = " ".join(parts[2:])
        IS_BETTING_OPEN = True
        BET_OPEN_TIMESTAMP = time.time()
        HAS_ANNOUNCED_LOCK = False # Reset flag for new round

        return f"🎰 BETTING OPENED! 🎰\n❓ Question: {CURRENT_QUESTION}\n📋 Valid Options: {', '.join(VALID_OPTIONS)}\n👉 Type !gamba [amount] [option] to play!"

    # ==========================================
    # COMMAND 2: !gamba_win [winning_option]
    # Example: !gamba_win yes
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
        sheets_sync.sync_to_google_sheets()
        
        # Reset state for the next round
        IS_BETTING_OPEN = False
        VALID_OPTIONS = []
        CURRENT_QUESTION = ""
        BET_OPEN_TIMESTAMP = 0
        HAS_ANNOUNCED_LOCK = False
        
        return f"🏆 BET RESOLVED! The winning choice was '{winning_choice}'. Paid out 2x to {winners_paid} winners! 💰"

    # ==========================================
    # COMMAND 3: !gamba_cancel
    # ==========================================

    elif command == "!gamba_cancel":
        if not IS_BETTING_OPEN:
            return "⚠️ There is no active betting pool to cancel."

        count, refund_msg = database.cancel_and_refund_bets()
        sheets_sync.sync_to_google_sheets()
        
        IS_BETTING_OPEN = False
        VALID_OPTIONS = []
        CURRENT_QUESTION = ""
        BET_OPEN_TIMESTAMP = 0
        HAS_ANNOUNCED_LOCK = False
        
        return f"🔄 BET CANCELLED: All points have been safely returned to players."

    # ==========================================
    # COMMAND 4: !give [username] [amount]
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
        except Exception as e:
            return f"❌ Database error: {str(e)}"
    
    # ==========================================
    # COMMAND 5: !reset_user [username]
    # ==========================================
    
    elif command == "!reset_user":
        if len(parts) < 2:
            return "⚠️ Usage: !reset_user [username]"
            
        target_username = parts
        
        # Manually adjust their balance back to the default 1000
        database.add_points(target_username, 0) # Ensures user exists in DB
        conn = database.sqlite3.connect(database.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET points = 1000 WHERE username = ?", (target_username,))
        conn.commit()
        conn.close()
        
        return f"🔄 Reset points for {target_username} back to 1000."

    # ==========================================
    # COMMAND 6: !give_all [amount]
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

def is_betting_period_active():
    if not IS_BETTING_OPEN or BET_OPEN_TIMESTAMP == 0:
        return False

    elapsed_time = time.time() - BET_OPEN_TIMESTAMP
    if elapsed_time < BET_DURATION_SECONDS:
        return True
    else:
        return False