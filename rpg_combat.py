import time
import random
import sqlite3
import gspread
import database
import rpg_database

def fetch_act_1_enemies():
    """ Connects to RPGConfig to grab Act 1 enemy matrix """
    try:
        gc = gspread.service_account(filename="credentials.json")
        sh = gc.open("RPGConfig")
        worksheet = sh.get_worksheet(0)
        records = worksheet.get_all_records()
        if records:
            return records
    except Exception as e:
        print(f"⚠️ [SHEETS ERROR] Falling back to local table: {e}")
        
    # Fallback
    return [
        {"Act I": "Imp", "HP": 20, "MP": 0, "ATK": 1, "DEF": 0, "MAGIC ATTACK": 0, "MAGIC DEFENSE": 0, "XP": 1, "GOLD": "0,1", "LOOT": "None"},
        {"Act I": "Zombie", "HP": 30, "MP": 0, "ATK": 2, "DEF": 1, "MAGIC ATTACK": 0, "MAGIC DEFENSE": 1, "XP": 2, "GOLD": "0,1", "LOOT": "None"},
        {"Act I": "Skeleton", "HP": 15, "MP": 0, "ATK": 3, "DEF": 0, "MAGIC ATTACK": 0, "MAGIC DEFENSE": 0, "XP": 2, "GOLD": "0,1,2", "LOOT": "None"},
        {"Act I": "Spider", "HP": 20, "MP": 2, "ATK": 3, "DEF": 3, "MAGIC ATTACK": 2, "MAGIC DEFENSE": 3, "XP": 3, "GOLD": "0,2", "LOOT": "None"},
        {"Act I": "Wraith", "HP": 10, "MP": 0, "ATK": 2, "DEF": 1, "MAGIC ATTACK": 0, "MAGIC DEFENSE": 1, "XP": 3, "GOLD": "0", "LOOT": "None,RuneLow"},
        {"Act I": "Vampire", "HP": 25, "MP": 4, "ATK": 2, "DEF": 2, "MAGIC ATTACK": 2, "MAGIC DEFENSE": 2, "XP": 5, "GOLD": "1,2", "LOOT": "None,MagicRing"},
        {"Act I": "Yeti", "HP": 30, "MP": 0, "ATK": 2, "DEF": 3, "MAGIC ATTACK": 0, "MAGIC DEFENSE": -2, "XP": 4, "GOLD": "1,2", "LOOT": "None"},
        {"Act I": "Tainted", "HP": 25, "MP": 2, "ATK": 2, "DEF": 1, "MAGIC ATTACK": 2, "MAGIC DEFENSE": 1, "XP": 4, "GOLD": "1,2", "LOOT": "None"},
        {"Act I": "Dark Archer", "HP": 20, "MP": 0, "ATK": 3, "DEF": 0, "MAGIC ATTACK": 0, "MAGIC DEFENSE": -1, "XP": 4, "GOLD": "1,2", "LOOT": "None,UniqueBow"}
    ]

def execute_fight_encounter(username):
    """ Spends 1 user stamina to process text combat sequence locally.
        Updates local SQLite profiles, pushes clean row changes to Sheets """
    conn = sqlite3.connect(rpg_database.RPG_DB_NAME)
    cursor = conn.cursor()
    
    # 1. Get user data
    cursor.execute('''
        SELECT class_name, level, xp, gold, current_hp, max_hp, base_str, base_dex, base_vit, stamina 
        FROM characters WHERE username = ?
    ''', (username,))
    player = cursor.fetchone()
    
    if not player:
        conn.close()
        return "❌ No hero created."
        
    c_class, lvl, xp, gold, cur_hp, max_hp, b_str, b_dex, b_vit, stamina = player
    
    if stamina <= 0:
        conn.close()
        return f"❌ You have no Stamina, {username}"
        
    if cur_hp <= 0:
        conn.close()
        return f"❌ You have no health, {username}"

    # 2. Extract Act 1 trash mob fields, filtering out Unique target rows for standard battles
    enemy_pool = fetch_act_1_enemies()
    normal_enemies = [e for e in enemy_pool if e.get("Act I") not in ["The Smith", "Andariel", "None", ""]]
    monster = random.choice(normal_enemies)
    
    m_name = monster.get("Act I") or monster.get("Act I\tHP\tMP\tATK\tDEF\tMAGIC ATTACK\tMAGIC DEFENSE\tXP\tGOLD\tLOOT\tABILITY\tUNIQUE", "Monster")
    m_hp = int(monster["HP"])
    m_atk = int(monster["ATK"])
    m_def = int(monster["DEF"])
    m_xp_reward = int(monster["XP"])
    
    # 3. Process Comma-Delimited Luck Matrix Rewards
    gold_options = str(monster["GOLD"]).split(",")
    gold_reward = int(random.choice(gold_options))
    
    loot_options = str(monster["LOOT"]).split(",")
    loot_reward = random.choice(loot_options)
    if loot_reward.lower() == "none":
        loot_reward = None

    # 4. Turn-Based Internal Math Resolution Loop
    player_hp_sim = cur_hp
    enemy_hp_sim = m_hp
    turns_max = 20 # Safety net infinite loop break ceiling
    
    # Simple Diablo flavor damage calculation parameters
    player_dmg = max(1, b_str // 2) 
    enemy_dmg = max(1, m_atk - (b_dex // 4))

    for _ in range(turns_max):
        # Player swings at monster
        enemy_hp_sim -= player_dmg
        if enemy_hp_sim <= 0:
            break
            
        # Monster swings back at player
        player_hp_sim -= enemy_dmg
        if player_hp_sim <= 0:
            player_hp_sim = 0
            break

    # 5. Process Post-Fight Database Commit Operations
    new_stamina = stamina - 1
    victory = enemy_hp_sim <= 0

    if victory:
        new_xp = xp + m_xp_reward
        new_gold = gold + gold_reward
        cursor.execute('UPDATE characters SET xp = ?, gold = ?, current_hp = ?, stamina = ? WHERE username = ?', 
                       (new_xp, new_gold, player_hp_sim, new_stamina, username))
        conn.commit()
        conn.close()

        # Level-up
        level_up_alert = rpg_database.check_and_execute_level_up(username)
        
        loot_text = f" | 🎒 Found: {loot_reward}!" if loot_reward else ""
        chat_reply = f"⚔️ VICTORY! {username} defeated a {m_name}! 🪙 Earned {gold_reward} Gold % {m_xp_reward} XP"
    else:
        # Player lost the simulation run
        cursor.execute('''UPDATE characters SET current_hp = ?, stamina = ? WHERE username = ?''', (player_hp_sim, new_stamina, username))
        conn.commit()
        conn.close()
        chat_reply = f"💀 DEFEAT! {username} was struck down by a {m_name}!"

    # 6. ASYNC BACKGROUND SHEET SYNC PASS
    try:
        gc = gspread.service_account(filename="credentials.json")
        sh = gc.open("RPGConfig")
        raw_tab = sh.worksheet("RPGRawCharData")
        
        # Look up cell coordinate reference maps by user token
        cell = raw_tab.find(username)
        if cell:
            # Sync core columns: Level, XP, Gold, Current HP, Current Stamina
            row_idx = cell.row
            
            # Fetch fresh local updates to push
            conn_sync = sqlite3.connect(rpg_database.RPG_DB_NAME)
            c_sync = conn_sync.cursor()
            c_sync.execute("SELECT level, xp, gold, current_hp FROM characters WHERE username = ?", (username,))
            s_data = c_sync.fetchone()
            conn_sync.close()
            
            if s_data:
                # Unpack the active row floats
                lvl, xp, gold, cur_hp, max_hp, cur_mp, max_mp, b_str, b_dex, b_int, b_vit, b_eng = s_data
                
                raw_tab.update_cell(row_idx, 3, lvl)
                raw_tab.update_cell(row_idx, 4, xp)
                raw_tab.update_cell(row_idx, 5, gold)
                raw_tab.update_cell(row_idx, 6, int(cur_hp))
                raw_tab.update_cell(row_idx, 7, int(max_hp))
                raw_tab.update_cell(row_idx, 8, int(cur_mp))
                raw_tab.update_cell(row_idx, 9, int(max_mp))
                raw_tab.update_cell(row_idx, 10, int(b_str))
                raw_tab.update_cell(row_idx, 11, int(b_dex))
                raw_tab.update_cell(row_idx, 12, int(b_int))
                raw_tab.update_cell(row_idx, 13, int(b_vit))
                raw_tab.update_cell(row_idx, 14, int(b_eng))
    except Exception as sheets_err:
        print(f"⚠️ [SHEETS SYNC TIMEOUT] Mirror data sync missed cell index mapping: {sheets_err}")

    return chat_reply