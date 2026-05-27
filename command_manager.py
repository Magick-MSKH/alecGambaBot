import database

def process_user_command(username, message_text):
    """ Parse public user chat commands.
        Return STR message if command is triggered, otherwise Return None
    """

    # Clean up Input STR
    parts = message_text.strip().split()
    if not parts:
        return None
    
    command = parts[0].lower()

    ########################################
    # 1. Handle Balance Check Command
    ########################################
    if command in ["!balance", "!points", "!cash"]:
        try:
            balance = database.get_balance(username)
            return f"💰 {username}, you currently have {balance} points!"
        except Exception as e:
            return f"❌ ERROR Checking balance: {str(e)}"

    ########################################
    # 2. Handle Leaderboard commands 
    ########################################
    elif command in ["!leaderboard", "!richest", "!top"]:
        try:
            top_players = database.get_top_users(5)
            if not top_players:
                return "📋 The leaderboard is currently empty!"
                
            response = "🏆 TOP 5 RICHEST PLAYERS: "
            # Format players nicely into a single chat string line
            rank_strings = []
            for i, (username, points) in enumerate(top_players, 1):
                rank_strings.append(f"#{i} {username} ({points} pts)")
                
            return response + " | ".join(rank_strings)
        except Exception as e:
            return f"❌ Error loading leaderboard: {str(e)}"

    elif command in ["!current_gamba", "!current_bet", "!gamba_info", "!pool"]:
        try:
            ## I think this import needs to be LOCAL to this script, as to prevent out-of-scope errors (maybe) (idk)
            import admin_manager

            # Fetch structured text from def get_current_pool_info() in admin_manager
            pool_info = admin_manager.get_current_pool_info()
            return pool_info
        except Exception as e:
            return f"❌ Error fetching pool data: {str(e)}"

    ########################################
    # 3. Handle Statistics commands
    ########################################
    elif command in ["!stats", "!profile", "!gamba_stats"]:
        stats = database.get_player_stats(username)
        if not stats:
            return f"📋 Username {username}, no stats found yet! Type in chat to register."
        else:
            points, placed, won, lost, peak = stats
            return f"📊 {username}: {points} pts | Bets: {placed} (🏆{won}W /❌{lost}L) | Personal Peak: {peak} pts"

    ########################################
    # 4. Handle Peak commands
    ########################################
    elif command in ["!record", "!peak", "!halloffame"]:
        record = database.get_all_time_peak_record()
        if not record or record[1] == 1000:
            return "👑 No historical peak record has broken past the starting line yet!"
        record_holder, record_points = record
        return f"👑 ALL-TIME RECORD: {record_holder} achieved a peak of {record_points} points! 🔥"

    ########################################
    # 5. Handle Help Command
    ########################################
    elif command in ["!help", "!commands"]:
        return "🤖 Available commands: !balance, !gamba [amount] [vote]"

    ########################################
    # 6. Handle Daily Points Command
    ########################################
    elif command in ["!daily", "!bonus", "!check_in"]:
        DAILY_REWARD = 500
        try:
            if database.check_daily_claimed(username):
                return f"⚠️ {username}, you have already claimed your bonus points for this stream."
            
            database.add_points(username, DAILY_REWARD)
            database.record_daily_claim(username)

            new_balance = database.get_balance(username)
            return f"🎁 {username} claimed their bonus {DAILY_REWARD} points for this stream."

        except Exception as e:
            return f"❌ Error claiming daily points: {str(e)}"
    
    return None