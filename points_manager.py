import time
import database

# Config constants
POINTS_PER_CHAT = 10
POINTS_PASSIVE = 50
POINTS_SUPER_CHAT_MULTIPLIER = 250 # Example: ($5 Super Chat) * 250 = 1250 points
POINTS_MEMBER_GIFT = 2000
POINTS_MEMBER_MILESTONE = 5000

# Tracks {username: last_seen_timestamp} to handle passive points
active_viewers = {}
# Tracks {username: last_chat_timestamp} to prevent spam-farming points
chat_cooldowns = {}

def process_incoming_message(username, message_text, message_type, details=None, is_member=False):
    """ Processes a single chat event. Call this every time the bot reads a message 
        Members receive a 1.2x multiplier!
    """
    current_time = time.time()

    # Mark user as active for passive point loops (lasts 15 minutes)
    active_viewers[username] = current_time

    # 1. Handle Regular Chat Messages
    if message_type == "textMessageEvent":
        
        # 30-second cooldown so they can't spam characters for points
        last_chat = chat_cooldowns.get(username, 0)
        
        if current_time - last_chat > 30:
            
            # Calculate base points
            reward = POINTS_PER_CHAT
            
            # Apply the 1.2x multiplier if they're a channel member
            if is_member:
                reward = int(POINTS_PER_CHAT * 1.2)

            database.add_points(username, POINTS_PER_CHAT)
            chat_cooldowns[username] = current_time

            # Custom terminal merker to see who is a member
            member_tag = "👑 [MEMBER]" if is_member else "👤"
            print(f"💰 {username} earned {POINTS_PER_CHAT} points for chatting")

    # 2. Handle Super Chats
    elif message_type == "superChatEvent":
        # 'details' will contain the dollar amount from the YouTube API
        donation_amount = details.get("amount", 0)
        bonus = int(donation_amount * POINTS_SUPER_CHAT_MULTIPLIER)
        database.add_points(username, bonus)
        print(f"🌟 SUPER CHAT! {username} donated ${donation_amount} and got {bonus} points!")

    # 3. Handle Membership Gifts / New Members
    elif message_type == "membershipGIFTEvent" or message_type == "new SponsorEvent":
        database.add_points(username, POINTS_MEMBER_GIFT)
        print(f"👑 MEMBER EVENT! {username} supported the channel and earned {POINTS_MEMBER_GIFT} points!")

    # 4. Handle Member Milestone Events
    if message_type == "memberMilestoneChatEvent":
        database.add_points(username, POINTS_MEMBER_MILESTONE)
        print(f"🏆 MILESTONE CLAIMED: {username} cashed in their monthly milestone points!")
    
def DistributePassivePoints():
    """ Call this function on a timer loop (Example: Once every 5 min).
        Gives points to anyone who interacted in the last 15 minutes. 
        Gives Members 1.2x passive points. """
    current_time = time.time()
    still_active = []

    # 1. Filter out users who haven't typed in over 15 minutes
    for username, last_seen in list(active_viewers.items()):
        if current_time - last_seen < 900: # in seconds
            still_active.append(username)
        else:
            del active_viewers[username] # remove inactive users

    # 2. Iterate & check db profiles to reward balances individually
    for username in still_active:
        reward = POINTS_PASSIVE
        database.add_points(username, reward)

    if still_active:
        print(f"⏰ Passive Payout complete for {len(still_active)} active viewers.")