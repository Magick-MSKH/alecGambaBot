import time
import database
import sheets_sync

POINTS_PER_CHAT = 10
POINTS_PASSIVE = 50
POINTS_SUPER_CHAT_MULTIPLIER = 250
POINTS_MEMBER_GIFT = 1500

active_viewers = {}
chat_cooldowns = {}

def process_incoming_message(username, message_text, message_type, details=None, is_member=False):
    if "magickbot0" in username.lower():
        return
    
    current_time = time.time()
    active_viewers[username] = current_time

    if message_type == "textMessageEvent":
        
        last_chat = chat_cooldowns.get(username, 0)
        
        if current_time - last_chat > 30:
            prestige_mult = database.get_user_prestige_multiplier(username)
            reward = POINTS_PER_CHAT * prestige_mult
            if is_member:
                reward = int(POINTS_PER_CHAT * 2)
            else:
                reward = POINTS_PER_CHAT

            database.add_points(username, reward)
            chat_cooldowns[username] = current_time

            member_tag = "👑 [MEMBER]" if is_member else "👤"
            print(f"{member_tag} {username} earned {POINTS_PER_CHAT} points for chatting")

    if message_type == "superChatEvent":
        is_usd = details.get("is_usd", True)
        if is_usd:
            donation_amount = details.get("amount", 5.0)
            points_to_add = int(donation_amount * 250)
        else:
            points_to_add = 1000

        prestige_mult = database.get_user_prestige_multiplier(username)
        points_to_add *= prestige_mult
        database.add_points(username, points_to_add)
        print(f"🌟 [SUPER CHAT DETECTED] {username} donated ${donation_amount} and got {points_to_add} points!")
        sheets_sync.sync_to_google_sheets()

    if message_type == "membershipGIFTEvent" or message_type == "newSponsorEvent":
        database.add_points(username, POINTS_MEMBER_GIFT)
        print(f"👑 MEMBER EVENT! {username} supported the channel and earned bonus points!")
        sheets_sync.sync_to_google_sheets()

    if message_type == "memberMilestoneChatEvent":

        if details is None:
            details = {}

        months = details.get("months", 1)
        dynamic_payout = 1000 + (months *  250)

        database.add_points(username, dynamic_payout)
        print(f"🏆 MILESTONE TIER: {username} cashed in Month {months} card for {dynamic_payout} points!")
        sheets_sync.sync_to_google_sheets()
    
def DistributePassivePoints():
    current_time = time.time()
    still_active = []

    for username, last_seen in list(active_viewers.items()):
        if current_time - last_seen < 900:
            still_active.append(username)
        else:
            del active_viewers[username]

    for username in still_active:
        prestige_mult = database.get_user_prestige_multiplier(username)
        reward = POINTS_PASSIVE * prestige_mult
        database.add_points(username, reward)

    if still_active:
        print(f"⏰ Passive Payout complete for {len(still_active)} active viewers.")