import time
import random
import database

ACTIVE_BATTLE = {
    "status": "IDLE",
    "instigator": "",
    "opponent": "",
    "amount": 0,
    "target_number": 0,
    "instigator_guess": None,
    "opponent_guess": None,
    "last_update_time": 0
}

GLOBAL_BATTLE_COOLDOWN = 0

def abort_battle():
    """ Forcefully resets the entire battle function """
    global ACTIVE_BATTLE
    ACTIVE_BATTLE = {
        "status": "IDLE",
        "instigator": "",
        "opponent": "",
        "amount": 0,
        "target_number": 0,
        "instigator_guess": None,
        "opponent_guess": None,
        "last_update_time": 0
    }

def process_battle_command(username, parts):
    """ Manages multi-step battle sequence """
    
    global ACTIVE_BATTLE, GLOBAL_BATTLE_COOLDOWN
    current_time = time.time()

    if ACTIVE_BATTLE["status"] != "IDLE":
        if current_time - ACTIVE_BATTLE["last_update_time"] > 60:
            print("⌛ [BATTLE TIMEOUT]")
            abort_battle()
            GLOBAL_BATTLE_COOLDOWN = current_time + 60
            return "⌛ BATTLE TIMEOUT: 60 second time limit expired!"

    if len(parts) < 2:
        return "⚔️ Usage: !battle [@opponent] [amount] | !battle [accept/refuse]"

    sub_cmd = parts[1].strip().lower()
    username_clean = username.strip()

    # ====================================== #
    # =========== INIT CHALLENGE =========== #
    # ====================================== #

    if ACTIVE_BATTLE["status"] == "IDLE":
        if current_time < GLOBAL_BATTLE_COOLDOWN:
            remaining_seconds = int(GLOBAL_BATTLE_COOLDOWN - current_time)
            minutes = remaining_seconds // 60
            seconds = remaining_seconds % 60
            return f"⏳ The arena is cooling down! Next battle available in {minutes}m {seconds}s."

        if len(parts) < 3:
            return "⚔️ Usage: !battle [@opponent] [amount]"

        target_opponent = parts[1].strip()
        amount_str = parts[2].strip()

        if target_opponent.lower() == username_clean.lower():
            return f"❌ {username_clean} , you cannot battle yourself!"

        try:
            amount = int(amount_str)
            if amount <= 0:
                return "❌ Wager must be greater than Zero!"
        except ValueError:
            return "❌ Wager amount must be an Integer!"
        
        inst_bal = database.get_balance(username_clean)
        oppo_bal = database.get_balance(target_opponent)

        if inst_bal < amount:
            return f"❌ {username_clean} , you don't have enough points! Balance: {inst_bal:,}"
        if oppo_bal < amount:
            return f"❌ @{target_opponent} doesn't have enough points to wager!"

        # Init global state dict data
        ACTIVE_BATTLE = {
            "status": "CHALLENGED",
            "instigator": username_clean,
            "opponent": target_opponent,
            "amount": amount,
            "target_number": 0,
            "instigator_guess": None,
            "opponent_guess": None,
            "last_update_time": current_time
        }
        return f"⚔️ {target_opponent}, you have been challenged by {username_clean} to battle for {amount:,} points!"

    # ====================================== #
    # ======= ACCEPT / REFUSAL PHASE ======= #
    # ====================================== #

    if ACTIVE_BATTLE["status"] == "CHALLENGED":
        if username_clean.lower() != ACTIVE_BATTLE["opponent"].lower():
            return None # Ignore inputs from non-involved parties

        if sub_cmd in ["decline", "refuse"]:
            instigator = ACTIVE_BATTLE["instigator"]
            abort_battle()
            GLOBAL_BATTLE_COOLDOWN = current_time + 30
            return f"❌ {instigator}'s challenge was declined by {username_clean}"

        elif sub_cmd == "accept":
            instigator = ACTIVE_BATTLE["instigator"]
            amount = ACTIVE_BATTLE["amount"]
            if database.get_balance(ACTIVE_BATTLE["instigator"]) < amount or database.get_balance(ACTIVE_BATTLE["opponent"]) < amount:
                ACTIVE_BATTLE["status"] = "IDLE"
                return "❌ Battle Cancelled: One or more players no longer have enough points!"
            
            ACTIVE_BATTLE["target_number"] = random.randint(1, 25)
            ACTIVE_BATTLE["status"] = "WAITING_INST"
            ACTIVE_BATTLE["last_update_time"] = current_time 

            return f"⚔️ Challenge Accepted! Target # has been set! {instigator} , please select your number (1 - 25)"

    # ====================================== #
    # ========= INSTIGATOR # ENTRY ========= #
    # ====================================== #

    if ACTIVE_BATTLE["status"] == "WAITING_INST":
        if username_clean.lower() != ACTIVE_BATTLE["instigator"].lower():
            return None ### Forces turn-order (Instigator always goes first)

        try:
            guess = int(sub_cmd)
            if guess < 1 or guess > 25:
                return "❌ Number must be between 1 and 25!"
        except ValueError:
            return "❌ Number must be an Integer!"
        
        ACTIVE_BATTLE["instigator_guess"] = guess
        ACTIVE_BATTLE["status"] = "WAITING_OPPO"
        ACTIVE_BATTLE["last_update_time"] = current_time
        return f"🔐 {ACTIVE_BATTLE['instigator']} locked in {ACTIVE_BATTLE['instigator_guess']}! {ACTIVE_BATTLE['opponent']} , choose your number!"

    # ====================================== #
    # ============= RESOLUTION ============= #
    # ====================================== #

    if ACTIVE_BATTLE["status"] == "WAITING_OPPO":
        if username_clean.lower() != ACTIVE_BATTLE["opponent"].lower():
            return None
        
        try:
            guess = int(sub_cmd)
            if guess < 1 or guess > 25:
                return "❌ Number must be between 1 and 25!"
        except ValueError:
            return "❌ Number must be an Integer!"

        if guess == ACTIVE_BATTLE["instigator_guess"]:
            return f"❌ {ACTIVE_BATTLE['opponent']} , you cannot choose the same number as your opponent!"
        
        ACTIVE_BATTLE["opponent_guess"] = guess

        target = ACTIVE_BATTLE["target_number"]
        p1 = ACTIVE_BATTLE["instigator"]
        p2 = ACTIVE_BATTLE["opponent"]
        p1_guess = ACTIVE_BATTLE["instigator_guess"]
        p2_guess = ACTIVE_BATTLE["opponent_guess"]
        wager = ACTIVE_BATTLE["amount"]

        diff_p1 = abs(target - p1_guess)
        diff_p2 = abs(target - p2_guess)

        ACTIVE_BATTLE["status"] = "IDLE"

        # TIE
        if diff_p1 == diff_p2:
            return f"🎲 TIE GAME! The target number was {target}; Both players were exactly {diff_p1} away! Points returned."

        # P1 WIN
        elif diff_p1 < diff_p2:
            database.add_points(p1, wager)
            database.add_points(p2, -wager)
            return f"⚔️ DUEL RESOLVED! The target number was {target}! {p1} guessed {p1_guess} (Diff: {diff_p1}) | {p2} guessed {p2_guess} (Diff: {diff_p2}). {p1} WINS the wager! ({wager:,}) 💰"
        
        # P2 WIN
        else:
            database.add_points(p2, wager)
            database.add_points(p1, -wager)
            return f"🏆 DUEL RESOLVED! The target number was {target}! {p1} guessed {p1_guess} (Diff: {diff_p1}) | {p2} guessed {p2_guess} (Diff: {diff_p2}). {p2} WINS the wager! ({wager:,}) 💰"

    return None