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

    # 1. Handle Balance Check Command
    if command in ["!balance", "!points", "!cash"]:
        try:
            balance = database.get_balance(username)
            return f"💰 {username}, you currently have {balance} points!"
        except Exception as e:
            return f"❌ ERROR Checking balance: {str(e)}"

    # 2. Handle Leaderboard commands 
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

    # 3. Handle Statistics commands
    elif command in ["!stats", "!profile", "!gamba_stats"]:
        stats = database.get_player_stats(username)
        if not stats:
            return f"📋 Username {username}, no stats found yet! Type in chat to register."
        points, placed, won, lost, peak = stats
        return f"📊 {username}: {points} pts | Bets: {placed} (🏆{won}W /❌{lost}L) | Personal Peak: {peak} pts"

    # 4. Handle Peak commands
    elif command in ["!record", "!peak", "!halloffame"]:
        record = database.get_all_time_peak_record()
        if not record or record[1] == 1000:
            return "👑 No historical peak record has broken past the starting line yet!"
        record_holder, record_points = record
        return f"👑 ALL-TIME RECORD: {record_holder} achieved a peak of {record_points} points! 🔥"


    # 5. Handle Help Command
    elif command in ["!help", "!commands"]:
        return "🤖 Available commands: !balance (check points), !gamba [amount] [vote_type] (place a bet)"
    
    return None