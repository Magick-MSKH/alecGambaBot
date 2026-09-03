import time
import random
import database
import rpg_database
import admin_manager

PIT_COOLDOWN_TRACKER = {}
PIT_CURSE_STATUS = False
PIT_COST_MODIFIER = 0

def process_user_command(username, message_text, is_member=False):
    global PIT_CURSE_STATUS
    global PIT_COST_MODIFIER
    parts = message_text.strip().split()
    if not parts:
        return None
    
    command = parts[0].lower()

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # COMMAND: !balance
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    if command == "!balance":
        try:
            if len(parts) < 2:
                balance = database.get_balance(username)
                return f"💰 {username} , you currently have {balance} points!"
            else:
                target_user = parts[1].lower()
                balance = database.get_balance(target_user)
                return f"💰 {target_user} currently has {balance} points!"
        except Exception as e:
            return f"❌ ERROR Checking balance: {str(e)}"

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # COMMAND: !leaderboard
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    elif command in ["!leaderboard", "!top"]:
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

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # COMMAND: !current_gamba
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    elif command == "!current_gamba":
        try:
            pool_info = admin_manager.get_current_pool_info()
            return pool_info
        except Exception as e:
            return f"❌ Error fetching pool data: {str(e)}"

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # COMMAND: !stats
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    elif command == "!stats":
        stats = database.get_player_stats(username)
        if not stats:
            return f"📋 Username {username} , no stats found yet! Type in chat to register."
        else:
            points, placed, won, lost, peak = stats
            return f"📊 {username}: {points} pts | Bets: {placed} (🏆{won}W /❌{lost}L) | Personal Peak: {peak} pts"

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # COMMAND: !record
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    elif command == "!record":
        record = database.get_all_time_peak_record()
        if not record or record[1] == 1000:
            return "👑 No historical peak record has broken past the starting line yet!"
        record_holder, record_points = record
        return f"👑 ALL-TIME RECORD: {record_holder} achieved a peak of {record_points} points! 🔥"

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # COMMAND: !help
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    elif command == "!help":
        return "🤖 For a full list of commands, check the Discord channel or Github page"

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # COMMAND: !daily
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    elif command in ["!daily", "!bonus", "!flarg"]:
        try:
            if database.check_daily_claimed(username):
                return f"⚠️ {username} , you have already claimed your bonus points for this stream."

            current_streak = database.get_user_daily_streak(username)
            prestige_mult = database.get_user_prestige_multiplier(username)

            BASE_REWARD = 1000 if is_member else 500
            streak_bonus = current_streak * 500
            FINAL_PAYOUT = (BASE_REWARD + streak_bonus) * prestige_mult

            database.add_points(username, FINAL_PAYOUT)
            database.record_daily_claim(username)
            database.increment_user_daily_streak(username)
#           new_balance = database.get_balance(username)

            if is_member:
                return f"🎁 {username} claimed their member bonus {FINAL_PAYOUT:,} points."
            else:
                return f"🎁 {username} claimed their bonus {FINAL_PAYOUT:,} points."

        except Exception as e:
            return f"❌ Error claiming !daily: {str(e)}"

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # COMMAND: !current_goal
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
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

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # COMMAND: !redeem
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
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
                return f"❌ {username} , you need {cost:,} points to draw Benny! (Balance: {balance:,})"
            
            database.add_points(username, -cost)
            print(f"🎨[BENNY REDEEM] {username} spend {cost} to draw Benny: {details}")
            return f"🎨[BENNY REDEEM] {username} spend {cost} to draw Benny: {details}"

        ### ADD TO STREAM GOAL ###
        elif sub_command == "goal":
            if len(parts) < 3:
                return "🤖 Specify an amount! Example: !redeem goal 100"
            if "barelyalec" in username.lower():
                return f"Sorry, {username} You can't contribute to your own stream goal!"
            if "notalecprobably" in username.lower():
                return f"Sorry, {username} You can't contribute to your own stream goal!"
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

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # COMMAND: !pit
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    elif command == "!pit":
        current_time = time.time()
        if len(parts) < 2:
            current_jackpot = database.get_pit_total()
            return f"🕳️ PIT TOTAL: {current_jackpot:,} channel points"
        
        sub_command = parts[1].lower()
        if sub_command == "cleanse":
            try:
                if PIT_CURSE_STATUS == False:
                    return f"✝️ There is no Curse on the Pit"
                else:
                    cleanse_fee = 10000
                    balance = database.get_balance(username)
                    if balance < cleanse_fee:
                        return f"{username} you do not have the required points to cleanse the pit."
                    else:
                        database.add_points(username, -cleanse_fee)
                        PIT_CURSE_STATUS = False
                        return f"✝️🪽 Masekah cleansed The Pit."
            except Exception as e:
                return f"❌ Error cleansing the pit: {str(e)}"


        if PIT_CURSE_STATUS == True:
            return f"💀 The Pit is CURSED and cannot be used!"

        if username in PIT_COOLDOWN_TRACKER:
            if current_time < PIT_COOLDOWN_TRACKER[username]:
                remaining_seconds = int(PIT_COOLDOWN_TRACKER[username] - current_time)
                minutes = remaining_seconds // 60
                seconds = remaining_seconds % 60
                return f"🤖⏳ {username} , You have a {minutes}m {seconds}s cooldown on this command."

        try:
            amount_str = parts[1].strip()
            
            if amount_str == "all":
                amount = database.get_balance(username)
            elif amount_str == "half":
                amount = int(database.get_balance(username) / 2)
            elif amount_str == "min":
                amount = database.get_user_prestige_multiplier(username) * 100
            else:
                amount = int(amount_str)

            pit_cost = database.get_user_prestige_multiplier(username) * 100
            pit_cost += PIT_COST_MODIFIER

            if amount < pit_cost:
                return f"❌ A Minimum of {pit_cost} points must be thrown into the pit."

            balance = database.get_balance(username)
            if balance < amount:
                return f"❌ Insufficient wealth! You only have {balance:,} points."

            database.add_points(username, -amount)
            database.add_to_pit(amount)
            PIT_COOLDOWN_TRACKER[username] = current_time + 300
            
            # Init PIT total
            fresh_jackpot = database.get_pit_total()
            
            if amount > 9999:
                roll = random.randint(111, 999)
            else:
                roll = random.randint(1, 999)

            if roll == amount:
                database.add_points(username, 10000)
                sender.send_message(f"🎰 {username} 's amount and roll matched! Bonus 10k points!")
            
            match roll:
                case 1:
                    PIT_CURSE_STATUS = True
                    return f"👻 Blooky has cursed the pit! 💀 It cannot be used again unless cleansed!"
                case 111:
                    PIT_COST_MODIFIER += 100
                    return f"🕳️ Pit Cost temporarily increased by 100 for the rest of the stream!"
#               case 222:
                    # Do something
                case 333:
                    database.add_to_pit(fresh_jackpot)
                    fresh_jackpot = database.get_pit_total()
                    return f"🪽 Masekah descends to bless the pit.🪽 The pool is doubled to {fresh_jackpot:,} points!"
#               case 420:
                    # Do something
                    # Bunny suggestion
                case 444:
                    return rpg_database.deposit_to_gheed(username, 44000)
#               case 555:
                    # Do something
                case 666:
                    database.add_to_pit(-amount)
                    fresh_jackpot = database.get_pit_total() # Renew pit total
                    return f"🔥 Lily grabs {username} 's points and sets them ablaze!🔥 The pit total remains unchanged at {fresh_jackpot}!"
                case 777:
                    database.add_points(username, fresh_jackpot)
                    database.reset_pit()
                    return f"🎰 JACKPOT! {username} rolled 7️⃣7️⃣7️⃣ and won all {fresh_jackpot:,} points!"
#               case 888:
                    # Do something
#               case 999:
                    # Do something
                case _:
                    return f"🕳️ {username} threw {amount:,} points into the money pit! The roll was {roll}. Current Pit Value: {fresh_jackpot:,} points!"

        except ValueError:
            return "❌ Error: Specify an Integer, 'half', or 'all' to throw into the pit."

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # COMMAND: !prestige
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

    elif command == "!prestige":
        if len(parts) < 2:
            res = database.execute_user_prestige(username)
            
            if res["status"] == "NOT_FOUND":
                return f"[ERROR] {username} USERNAME NOT FOUND."
                
            elif res["status"] == "MAX_CAP":
                return f"[ERROR] {username} IS AT THE MAXIMUM LEVEL."
                
            elif res["status"] == "LOW_POINTS":
                return f"[ERROR] {username} NOT ENOUGH POINTS"
                
            return f"⬆️ {username} PRESTIGE LEVEL INCREASED TO {res['new_level']}! NEW MULTIPLIER: {res['multiplier']}x"

        elif len(parts) == 2:
            user_query = parts[1].lower()
            user_prestige = database.get_prestige_level(user_query)
            user_multiplier = database.get_user_prestige_multiplier(user_query)
            return f"User {user_query} is Prestige Level {user_prestige} ({user_multiplier}x Multi)"
            


    return None