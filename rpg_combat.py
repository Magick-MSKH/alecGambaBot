import time
import random
import sqlite3
import gspread
import database
import rpg_database

def calculate_derived_stats(class_name, base_stats):
    """ Applies class-specific attribute scaling matrices to base stats.
        Returns max_hp, max_mp, attack_power, defense, magic_attack, extra_attack_chance """
    c_type = class_name.lower().strip()
    
    # 1. Unpack raw integer attributes from SQLite player profile row
    hp_base = int(base_stats["max_hp"])
    mp_base = int(base_stats["max_mp"])
    s = int(base_stats["str"])
    d = int(base_stats["dex"])
    i = int(base_stats["int"])
    v = int(base_stats["vit"])
    e = int(base_stats["eng"])

    # 2. Set default baseline profiles
    attack_power = max(1, s // 2)    # Default baseline physical damage
    defense = d // 4                 # Default baseline armor reduction
    magic_attack = i                 # Default baseline magic damage
    extra_attack_chance = 0.0        # Default baseline double strike probability

    # ===================================
    # CLASS BONUS SCALING MATRIX MATRICES
    # ===================================
    if c_type == "warrior":
        # +1 Attack Power per 6 STR | +1 Defense per 5 DEX | +1 Max HP per 4 VIT
        attack_power += (s // 6)
        defense += (d // 5)
        hp_base += (v // 4)

    elif c_type == "wizard":
        # +1 Magic Attack per 5 INT | +1 Max MP per 5 ENG
        magic_attack += (i // 5)
        mp_base += (e // 5)

    elif c_type == "archer":
        # +1 Attack Power/Rating per 5 DEX | +1 Max HP per 6 VIT | +2% Double Strike per 10 ENG
        attack_power += (d // 5) # Archer scales physical damage on Agility/Dexterity!
        hp_base += (v // 6)
        extra_attack_chance += (e // 10) * 0.02

    elif c_type == "valkyrie":
        # +1 to every derived stat per 10 points
        attack_power += (s // 10)
        defense += (d // 10)
        magic_attack += (i // 10)
        hp_base += (v // 10)
        mp_base += (e // 10)

    return hp_base, mp_base, attack_power, defense, magic_attack, extra_attack_chance

def fetch_current_world_parameters():
    """ Connects to RPGWorldState to read live environmental control cells.
        Returns current_act, current_group """
    try:
        gc = gspread.service_account(filename="sheets_credentials.json")
        sh = gc.open("RPGConfig")
        world_tab = sh.worksheet("RPGWorldState")
        
        # Read the live administrative zone switches directly from fixed cells
        act_string = str(world_tab.acell("B2").value).strip()   # e.g., "Act I"
        group_string = str(world_tab.acell("B3").value).strip() # e.g., "Group 1"
        
        return act_string, group_string
    except Exception as e:
        print(f"⚠️ [WORLD STATE ERROR] Failed to read cells: {e}")
        return "Act I", "Group 1" # Safety net rock-solid fallback defaults

def fetch_filtered_area_enemies():
    """ Fetches the full monster ledger from RPGConfig and returns exactly 
        the 3 progressive enemies matching the spreadsheet's active location """
    # Grab administrative cell parameters
    active_act, active_group = fetch_current_world_parameters()
    
    # Hardcoded structural fallback matrix
    act_1_matrix = {
        "group 1": [
            {"Name": "Imp", "HP": 20, "MP": 0, "ATK": 1, "DEF": 0, "MAGIC ATTACK": 0, "MAGIC DEFENSE": 0, "XP": 1, "GOLD": "0,1", "LOOT": "None"},
            {"Name": "Zombie", "HP": 30, "MP": 0, "ATK": 2, "DEF": 1, "MAGIC ATTACK": 0, "MAGIC DEFENSE": 1, "XP": 2, "GOLD": "0,1", "LOOT": "None"},
            {"Name": "Skeleton", "HP": 15, "MP": 0, "ATK": 3, "DEF": 0, "MAGIC ATTACK": 0, "MAGIC DEFENSE": 0, "XP": 2, "GOLD": "0,1,2", "LOOT": "None"}
        ],
        "group 2": [
            {"Name": "Spider", "HP": 20, "MP": 2, "ATK": 3, "DEF": 3, "MAGIC ATTACK": 2, "MAGIC DEFENSE": 3, "XP": 3, "GOLD": "0,2", "LOOT": "None"},
            {"Name": "Wraith", "HP": 10, "MP": 0, "ATK": 2, "DEF": 1, "MAGIC ATTACK": 0, "MAGIC DEFENSE": 1, "XP": 3, "GOLD": "0", "LOOT": "None,RuneLow"},
            {"Name": "Vampire", "HP": 25, "MP": 4, "ATK": 2, "DEF": 2, "MAGIC ATTACK": 2, "MAGIC DEFENSE": 2, "XP": 5, "GOLD": "1,2", "LOOT": "None,MagicRing"}
        ],
        "group 3": [
            {"Name": "Yeti", "HP": 30, "MP": 0, "ATK": 2, "DEF": 3, "MAGIC ATTACK": 0, "MAGIC DEFENSE": -2, "XP": 4, "GOLD": "1,2", "LOOT": "None"},
            {"Name": "Tainted", "HP": 25, "MP": 2, "ATK": 2, "DEF": 1, "MAGIC ATTACK": 2, "MAGIC DEFENSE": 1, "XP": 4, "GOLD": "1,2", "LOOT": "None"},
            {"Name": "Dark Archer", "HP": 20, "MP": 0, "ATK": 3, "DEF": 0, "MAGIC ATTACK": 0, "MAGIC DEFENSE": -1, "XP": 4, "GOLD": "1,2", "LOOT": "None,UniqueBow"}
        ]
    }
    
    # Check live sheets table rows first (allowing dynamic edits), otherwise route to fallback groups
    try:
        gc = gspread.service_account(filename="sheets_credentials.json")
        sh = gc.open("RPGConfig")
        worksheet = sh.get_worksheet(0)
        records = worksheet.get_all_records()
        
        if records:
            # Map master sheet rows into the 3-tier filtration groups dynamically & Strips area bosses from standard fights
            filtered_list = []
            for row in records:
                m_name = row.get("Act I", "").strip()
                if m_name and m_name not in ["The Smith", "Andariel", "None", ""]:
                    filtered_list.append(row)
            
            # Segment the live array list into clean sequential subsets of 3
            if active_group.lower() == "group 1" and len(filtered_list) >= 3:
                return [{"Name": filtered_list[j]["Act I"], **filtered_list[j]} for j in range(3)]
            elif active_group.lower() == "group 2" and len(filtered_list) >= 6:
                return [{"Name": filtered_list[j]["Act I"], **filtered_list[j]} for j in range(3, 6)]
            elif active_group.lower() == "group 3" and len(filtered_list) >= 9:
                return [{"Name": filtered_list[j]["Act I"], **filtered_list[j]} for j in range(6, 9)]
    except Exception as sheets_err:
        print(f"⚠️ [CONFIG SHEETS FILTER ERROR] Routing directly to grouped code tables: {sheets_err}")

    # Fall back to the bulletproof dictionary subsets if sheets connection drops
    return act_1_matrix.get(active_group.lower(), act_1_matrix["group 1"])

def execute_fight_encounter(username):
    """ Spends stamina, refolds dynamic attribute scaling values, runs pre-battle 
        MP auto-refills, and executes the combat turn simulator engine """
    conn = sqlite3.connect(rpg_database.RPG_DB_NAME)
    cursor = conn.cursor()
    
    # Get user data
    cursor.execute('''
        SELECT class_name, level, xp, gold, current_hp, max_hp, current_mp, max_mp, 
               base_str, base_dex, base_int, base_vit, base_eng, stamina 
        FROM characters WHERE username = ?
    ''', (username,))
    player = cursor.fetchone()
    
    if not player:
        conn.close()
        return "❌ No hero created."
        
    c_class, lvl, xp, gold, cur_hp, max_hp, cur_mp, max_mp, b_str, b_dex, b_int, b_vit, b_eng, stamina = player

    if stamina <= 0:
        conn.close()
        return f"❌ You have no Stamina, {username}"
    if cur_hp <= 0:
        conn.close()
        return f"❌ You have no health, {username}"

    # Pack raw inputs into dictionary container for calculator
    base_stats = {
        "max_hp": max_hp, "max_mp": max_mp, "str": b_str, 
        "dex": b_dex, "int": b_int, "vit": b_vit, "eng": b_eng
    }

    # Run dynamic unified stat calc
    scaled_max_hp, scaled_max_mp, p_atk, p_def, p_matk, double_strike_prob = calculate_derived_stats(c_class, base_stats)

    # Apply auto mana regeneration rule
    player_mp_sim = scaled_max_mp

    # Fetch enemy datasets from sheet configs
    active_enemies = fetch_filtered_area_enemies()
    monster = random.choice(active_enemies)
    
    m_name = monster.get("Name") or monster.get("Act I") or "Monster"
    m_hp = int(monster["HP"])
    m_atk = int(monster["ATK"])
    m_mdef = int(monster["MAGIC DEFENSE"])
    m_xp_reward = int(monster["XP"])
    
    gold_reward = int(random.choice(str(monster["GOLD"]).split(",")))
    loot_reward = random.choice(str(monster["LOOT"]).split(","))
    if loot_reward.lower() == "none": loot_reward = None

    # Combat sim loop
    player_hp_sim = cur_hp
    enemy_hp_sim = m_hp
    turns_max = 20

    chosen_spell = spell_choice.lower().strip() if spell_choice else None
    is_archer_sight = (chosen_spell in ["innersight", "innersight+"]) and (c_class.lower() == "archer")
    valid_bolts = ["firebolt", "chargedbolt", "icebolt"]
    
#   player_dmg = max(1, b_str // 2) 
#   enemy_dmg = max(1, m_atk - (b_dex // 4))
#   is_archer_sight = (chosen_spell in ["innersight", "innersight+"]) and (c_class.lower() == "archer")

    for turn in range(1, turns_max + 1):
        # PLAYER'S TURN PASS
        # Calculate num of player actions (Archer Multi-Attack logic, etc)
        total_strikes = 1
        if c_class.lower() == "archer" and random.random() < double_strike_prob:
            total_strikes = 2

        for strike in range(total_strikes):
            if is_archer_sight and turn == 1:
                # Inner Sight: Sunder 50% of physical enemy defense
                m_def = max(0, int(monster["DEF"]) // 2)
                break
                
            elif chosen_spell in valid_bolts and player_mp_sim >= 1 and c_class.lower() == "wizard":
                # Wizard Bolt Cast Pass: Spend 1 MP to hit with Magic Attack power bypassing physical armor
                player_mp_sim -= 1
                player_magic_dmg = max(1, p_matk - m_mdef)
                enemy_hp_sim -= player_magic_dmg
            else:
                # Default Standard Physical Strike Pass: Modified by player scaled ATK and monster DEF
                enemy_phys_dmg = max(1, p_atk - int(monster["DEF"]))
                enemy_hp_sim -= enemy_phys_dmg

            if enemy_hp_sim <= 0: break
        if enemy_hp_sim <= 0: break
            
        # ENEMY'S TURN PASS
        enemy_final_dmg = max(1, m_atk - p_def)
        player_hp_sim -= enemy_final_dmg
        if player_hp_sim <= 0:
            player_hp_sim = 0
            break

    # DB commits and background updates
    new_stamina = stamina - 1
    victory = enemy_hp_sim <= 0

    if victory:
        new_xp = xp + m_xp_reward
        new_gold = gold + gold_reward
        cursor.execute('UPDATE characters SET xp = ?, gold = ?, current_hp = ?, current_mp = ?, stamina = ? WHERE username = ?', 
                       (new_xp, new_gold, player_hp_sim, player_mp_sim, new_stamina, username))
        conn.commit()
        conn.close()
        
        level_up_alert = rpg_database.check_and_execute_level_up(username)
        loot_text = f" | 🎒 Found: {loot_reward}!" if loot_reward else ""
        chat_reply = f"⚔️ VICTORY! {username} defeated a {m_name} & earned: {gold_reward} Gold, {m_xp_reward} XP, {loot_text}. {level_up_alert}"
    else:
        cursor.execute('UPDATE characters SET current_hp = ?, current_mp = ?, stamina = ? WHERE username = ?', 
                       (player_hp_sim, player_mp_sim, new_stamina, username))
        conn.commit()
        conn.close()
        chat_reply = f"💀 DEFEAT! {username} was struck down by a {m_name}!"

    return chat_reply