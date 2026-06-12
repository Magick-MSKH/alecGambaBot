import time
import random
import database

PIT_COOLDOWN_TRACKER = {}

def process_user_command(username, message_text):
    """ Parse public user chat commands.
        Return STR message if command is triggered, otherwise Return None
    """

    parts = message_text.strip().split()
    if not parts:
        return None
    
    command = parts[0].lower()

    # ==========================================
    # COMMAND 1: !balance
    # ==========================================
    if command in ["!balance", "!points", "!cash"]:
        try:
            balance = database.get_balance(username)
            return f"💰 {username}, you currently have {balance} points!"
        except Exception as e:
            return f"❌ ERROR Checking balance: {str(e)}"

    # ==========================================
    # COMMAND 2: !leaderboard
    # ==========================================
    elif command in ["!leaderboard", "!richest", "!top"]:
        try:
            top_players = database.get_top_users(5)
            if not top_players:
                return "📋 The leaderboard is currently empty!"
                
            response = "🏆 TOP 5 RICHEST PLAYERS: "
            rank_strings = []
            for i, (username, points) in enumerate(top_players, 1):
                rank_strings.append(f"#{i} {username} ({points} pts)")
                
            return response + " | ".join(rank_strings)
        except Exception as e:
            return f"❌ Error loading leaderboard: {str(e)}"

    # ==========================================
    # COMMAND 3: !current_gamba
    # ==========================================

    elif command in ["!current_gamba", "!current_bet", "!gamba_info", "!pool"]:
        try:
            import admin_manager
            pool_info = admin_manager.get_current_pool_info()
            return pool_info
        except Exception as e:
            return f"❌ Error fetching pool data: {str(e)}"

    # ==========================================
    # COMMAND 4: !stats
    # ==========================================
    elif command in ["!stats", "!profile", "!gamba_stats"]:
        stats = database.get_player_stats(username)
        if not stats:
            return f"📋 Username {username}, no stats found yet! Type in chat to register."
        else:
            points, placed, won, lost, peak = stats
            return f"📊 {username}: {points} pts | Bets: {placed} (🏆{won}W /❌{lost}L) | Personal Peak: {peak} pts"

    # ==========================================
    # COMMAND 5: !record
    # ==========================================
    elif command in ["!record", "!peak", "!halloffame"]:
        record = database.get_all_time_peak_record()
        if not record or record[1] == 1000:
            return "👑 No historical peak record has broken past the starting line yet!"
        record_holder, record_points = record
        return f"👑 ALL-TIME RECORD: {record_holder} achieved a peak of {record_points} points! 🔥"

    # ==========================================
    # COMMAND 6: !help
    # ==========================================
    elif command in ["!help", "!commands"]:
        return "🤖 How to gamba: !gamba [amount] [vote], For more info check the Discord!"

    # ==========================================
    # COMMAND 7: !daily
    # ==========================================
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

    # ==========================================
    # COMMAND 7: !goal
    # ==========================================
    elif command in ["!goal", "!current_goal", "!pointgoal"]:
        goal_data = database.get_active_goal()
        if not goal_data:
            return "🎯 No active community point goal is currently active."
        
        goal_name, needed, current = goal_data
        percent = min(100, int((current / needed) * 100))

        # Build text-based progress bar for chat
        bar_length = 10
        filled_length = int(bar_length * current // needed)
        bar = "🟩" * filled_length + "⬜" * (bar_length - filled_length)

        return f"🎯 CURRENT GOAL: {goal_name} | {bar} ({percent}%) | 📊 Progress: {current:,} / {needed:,} points redeemed!"

    # ==========================================
    # COMMAND 7: !redeem
    # ==========================================
    elif command == "!redeem":
        if len(parts) < 2:
            return "🤖 Usage: !redeem [item] (amount)"
        
        sub_command = parts[1].lower()

        ### DRAW BENNY ###
        if sub_command == "benny":
            cost = 10000
            if len(parts) < 3:
                return "🎨 Specify what to add! Example: !redeem benny Top-hat and Monocle"

            details = " ".join(parts[2:])
            balance = database.get_balance(username)
            if balance < cost:
                return f"❌ {username}, you need {cost:,} points to draw Benny! (Balance: {balance:,})"
            
            database.add_points(username, -cost)
            print(f"🎨[BENNY REDEEM] {username} spend {cost} to draw Benny: {details}")
            return f"🎨[BENNY REDEEM] {username} spend {cost} to draw Benny: {details}"

        ### ADD TO STREAM GOAL ###
        elif sub_command == "goal":
            if len(parts) < 3:
                return "🤖 Specify an amount! Example: !redeem goal 100"
            try:
                amount = int(parts[2])
                if amount <= 0:
                    return None
                
                balance = database.get_balance(username)
                if balance < amount:
                    return f"❌ Insufficient Points! You only have {balance:,} points."

                goal_data = database.get_active_goal()
                if not goal_data:
                    return "🎯 No active goal set."

                goal_name, needed, previous_total = goal_data

                if previous_total >= needed:
                    return f"🎉 [GOAL] '{goal_name}' has already been met!"
                
                database.add_points(username, -amount)
                database.contribute_to_goal(amount)

                _, needed, fresh_current = database.get_active_goal()

                if fresh_current >= needed:
                    return f"🚨 GOAL '{goal_name}' REACHED! {username} added the final {amount:,} points for COMPLETION!"

                return f"🎯 [GOAL] {username} contributed {amount:,} points to the goal! Total: {fresh_current:,}/{needed:,} 🚀"
                
            except ValueError:
                return "❌ Error: Specify a valid whole number of points to redeem."

    # ==========================================
    # COMMAND 8: !battle
    # ==========================================

    elif command == "!battle"
        try:
            import battle_manager
            battle_reply = battle_manager.process_battle_command(username, parts)
            return battle_reply
        except Exception as e:
            return f"❌ Error in Battle Engine: {str(e)}"

    # ==========================================
    # COMMAND 9: !pit
    # ==========================================

    elif command in ["!pit", "!throw", "!void"]:
        current_time = time.time()
        # Check PIT amount with the base command
        if len(parts) < 2:
            current_jackpot = database.get_pit_total()
            return f"[MONEY PIT]: There are currently {current_jackpot:,} points inside the pit!"

        if username in PIT_COOLDOWN_TRACKER:
            if current_time < PIT_COOLDOWN_TRACKER[username]:
                remaining_seconds = int(PIT_COOLDOWN_TRACKER[username] - current_time)
                minutes = remaining_seconds // 60
                seconds = remaining_seconds % 60
                return f"🤖⏳ {username}, You have a {minutes}m {seconds}s cooldown on this command."

        try:
            # FIXED (INDEXING): Target index 1 to parse wager string safely
            amount_str = parts[1].strip()
            
            if amount_str in ["all", "max"]:
                amount = database.get_balance(username)
            elif amount_str == "half":
                amount = int(database.get_balance(username) / 2)
            else:
                amount = int(amount_str)

            # Minimum of 100 points
            if amount < 100:
                return "❌ A Minimum of 100 points must be thrown into the pit."

            balance = database.get_balance(username)
            if balance < amount:
                return f"❌ Insufficient wealth! You only have {balance:,} points."

            database.add_points(username, -amount)
            database.add_to_pit(amount)

            PIT_COOLDOWN_TRACKER[username] = current_time + 300
            
            # Get updated total pool for lottery calculation
            fresh_jackpot = database.get_pit_total()
            roll = random.randint(1, 1000)
            
            if roll == 777:
                database.add_points(username, fresh_jackpot)
                database.reset_pit()
                return f"🎰 JACKPOT! {username} rolled 7️⃣7️⃣7️⃣ and secured the entire pool of {fresh_jackpot:,} points!"
            else:
                return f"🕳️ {username} threw {amount:,} points into the money pit! The roll was {roll} . Current Pit Value: {fresh_jackpot:,} points!"

        except ValueError:
            return "❌ Error: Specify an Integer, 'half', or 'all' to throw into the pit."

    
    return None