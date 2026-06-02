import time
import asyncio
import pytchat
import database
import sheets_sync
import admin_manager
import points_manager
import command_manager
import terminal_controller
from pytchat import CompatibleProcessor
from chat_sender import YouTubeChatSender

IS_BOT_RUNNING = True

async def run_bot_async():
    # Init SQLite tables
    database.init_db()
    clear_db = input("💽 Clear Daily Claims? (Y/N): ")
    if not clear_db:
        print("❌ Error: Input cannot be empty.")
    elif clear_db == "Y":
        database.clear_daily_claims()
        print("🧹 Reset daily claims table for fresh session.")
    else:
        print("📋 Daily Claim flags unchanged")

    ###################################################
    # 0a. Prompt for Video ID dynamically via stdin
    ###################################################
    print("=" * 30)
    VIDEO_ID = input("👉 Enter YouTube Stream Video ID: ").strip()
    print("=" * 30)

    if not VIDEO_ID:
        print("❌ Error: Video ID cannot be empty.")
        return

    STREAM_URL = f"https://youtube.com/live_chat?v={VIDEO_ID}"

    ###################################################
    # 1. Init chat writer
    ###################################################

    sender = YouTubeChatSender(STREAM_URL)
    await sender.start()

    input("\n👉 Press ENTER when browser has loaded...")

    ###################################################
    # 2. Init chat scraper
    ###################################################

    print("🔍 Connecting to YouTube Live Chat reader via CompatLayer")
    try:
        chat = pytchat.create(video_id=VIDEO_ID, processor=CompatibleProcessor())
    except Exception as e:
        print(f"❌ Failed to connect to stream: {e}")
        await sender.stop()# AWAIT_ADD
        return

    terminal_controller.SENDER_OBJECT = sender ### NEW -- Links sender hook to terminal controller sub
    asyncio.create_task(terminal_controller.check_terminal_input())
    print("🚀 Gamba Bot is running natively on Windows! Monitoring chat logs...")
    await sender.send_message("🤖 Gamba Bot is online and listening for commands!")

    last_passive_tick = time.time()

    global IS_BOT_RUNNING
    IS_BOT_RUNNING = True

    ##############################
    ### MASTER CONNECTION LOOP ###
    ##############################
    while IS_BOT_RUNNING:
        print("🔍 Initializing YT Live Chat connection token...")
        try:
            chat = pytchat.create(video_id=VIDEO_ID, processor=CompatibleProcessor())
            print("🛜 Connection Established.")
        except Exception as e:
            print(f"❌ Failed to connect reader: {e}. Retrying in 10 seconds...")
            await asyncio.sleep(10)
            continue

        while chat.is_alive() and IS_BOT_RUNNING:
            try:
                current_time = time.time()

                # 5-Minute passive payout and gspread sync
                if current_time - last_passive_tick >= 300:
                    points_manager.DistributePassivePoints()
                    sheets_sync.sync_to_google_sheets()

                    # Playwright connection verification ping
                    if sender and sender.page:
                        try:
                            await sender.page.title()
                        except Exception:
                            try:
                                await sender.page.goto(STREAM_URL)
                            except Exception:
                                    pass
                    last_passive_tick = current_time

                data = chat.get()

                if data is None or not isinstance(data, dict) or 'items' not in data or data['items'] is None:
                        # Instead of crashing, break this inner loop so the parent container 
                        # can instantly request a brand new chat token from YouTube!
                        print("🔄 [CONNECTION REFRESH] YouTube token expired or recycled. Re-authenticating...")
                        break

                #########################################
                ####### MAIN GAMBA BOT SUBROUTINE #######
                #########################################
                for c in data['items']:
                    if c is None or not isinstance(c, dict):
                        print(f"🐞 [DEBUG] Skipped an invalid message item dict object layout: {c}")
                        continue
                    
                    # YouTube API layout mappings:
                    snippet = c.get("snippet") ## ("snippet", {})
                    author = c.get("authorDetails") ## ("authorDetails", {})

                    if snippet is None or author is None:
                        print(f"🐞 [DEBUG] Found empty interior object component layout!")
                        print(f"📋 [DEBUG] Raw Component Dump: {c}")
                        snippet = snippet if snippet is not None else {}
                        author = author if author is not None else {}
                    
                    username = author.get("displayName", "")
                    channel_id = author.get("channelId", "")
                    message_text = snippet.get("displayMessage", "")
                    
                    if not username:
                        print(f"🐞 [DEBUG] Username returned FALSE! {username}")
                        continue

                    if "magickbot0" in username.lower():
                        continue


                    ########################################################
                    ###   Dynamic Event Type Resolution (Checking keys)  ###
                    ########################################################
                    message_type = "textMessageEvent"
                    details = {}

                    raw_type = c.get("type") if isinstance(c, dict) else ""
                    if raw_type is None:
                        raw_type = ""

                    if "superChatDetails" in snippet:
                        message_type = "superChatEvent"
                        sc_info = snippet.get("superChatDetails")
                        if isinstance(sc_info, dict):
                            details["amount"] = float(sc_info.get("amountMicros", 0)) / 1000000.0
                        else:
                            details["amount"] = 0.0

                    elif "memberMilestoneChatDetails" in snippet:
                        message_type = "memberMilestoneChatEvent"
                        milestone_info = snippet.get("memberMilestoneChatDetails")
                        if isinstance(milestone_info, dict):
                            details["months"] = int(milestone_info.get("memberMonth", 1))
                        else:
                            details["months"] = 1

                    elif "newSponsorEvent" in raw_type or "membershipGIFTEvent" in raw_type:
                        message_type = "membershipGIFTEvent"

                    ### PARSE --Silent: Point Balances
                    is_member = author.get("isChatSponsor", False)
                    points_manager.process_incoming_message(
                        username,
                        message_text,
                        message_type,
                        details=details,
                        is_member=is_member
                    )

                    ### Re-route based on flags from CompatLayer
                    if message_type == "textMessageEvent":
                        published_at = snippet.get("publishedAt", "LIVE")
                        print(f"💬 [{published_at}] {username}: {message_text}")

                        bot_reply = command_manager.process_user_command(username, message_text)

                        if bot_reply and isinstance(bot_reply, str):
                            await sender.send_message(bot_reply)
                            continue
                        
                        admin_reply = admin_manager.process_admin_command(channel_id, username, message_text)
                        if admin_reply and isinstance(admin_reply, str):
                            await sender.send_message(admin_reply)
                            continue

                    elif message_type == "memberMilestoneChatEvent":
                        months = details.get("months", 1)
                        dynamic_payout = 1000 + (months * 250)

                        ### Terminal print confirmation
                        print(f"🖲️ [MILESTONE TRACKED] {username} for Month {months}!")
                        database.add_points(username, dynamic_payout)

                        await sender.send_message(f"🏆 {username} claimed thier {months}-month member chat for {dynamic_payout:,} points! 🎁")# AWAIT_ADD
                        sheets_sync.sync_to_google_sheets()
                        continue

                    elif message_type == "superChatEvent":
                        donation_amount = details.get("amount", 0.0)
                        print(f"🖲️ [SUPER CHAT DETECTED] {username} donated {donation_amount:.2f}")

                        await sender.send_message(f"🌟 {username}'s Super Chat earned channel points!")# AWAIT_ADD
                        sheets_sync.sync_to_google_sheets()
                        continue

                    elif message_type == "membershipGIFTEvent":
                        MEMBERSHIP_GIFT = 1500

                        print(f"🖲️ [MEMBERSHIP DETECTED] {username} supported the channel")
                        database.add_points(username, MEMBERSHIP_GIFT)

                        await sender.send_message(f"👑 {username} earned bonus points for Membership!")# AWAIT_ADD
                        sheets_sync.sync_to_google_sheets()
                        continue

                    ### Console chat debugging moved to textMessageEvent sub ###
                    # published_at = snippet.get("publishedAt", "LIVE")
                    # print(f"🖲️ [{published_at}] {username}: {message_text}")

                    ###########################################
                    # COMMAND HANDLER #
                    ###########################################

                    bot_reply = command_manager.process_user_command(username, message_text)
                    if bot_reply:
                        await sender.send_message(bot_reply)# AWAIT_ADD
                        print(f"🤖 BOT RESPONSE: {bot_reply}")
                        continue

                    # 4. Handle Admin Commands (!give, !gamba_open, )
                    admin_reply = admin_manager.process_admin_command(channel_id, username, message_text)
                    if admin_reply:
                        await sender.send_message(admin_reply)# AWAIT_ADD
                        print(f"👑 ADMIN ACTION: {admin_reply}")
                        continue

                    # 5. Handle Gamba betting execution
                    if message_text.startswith("!gamba"):
                        if not admin_manager.IS_BETTING_OPEN:
                            print(f"🎲 GAMBA CLOSED: {username} tried to bet, but no pool is open.")
                            continue
                            
                        if admin_manager.IS_BETTING_LOCKED:
                            print(f"🔒 GAMBA LOCKED: {username} tried to bet, but the pool is locked.")
                            continue

                        parts = message_text.split()
                        if len(parts) >= 3:
                            try:
                                vote = parts[2].lower()
                                    
                                # Validate choice against active variables
                                if vote not in admin_manager.VALID_OPTIONS: # or amount <= 0
                                    continue

                                amount_str = parts[1].lower()

                                if amount_str in ["all", "allin", "all-in", "max", "maxbet"]:
                                    amount = database.get_balance(username)
                                else:
                                    amount = int(amount_str)
                                    
                                if amount <= 0:
                                    print(f"🖲️ {username} tried to bet 0 or an invalid amount ({amount})")
                                    continue

                                success, gamba_msg = database.place_bet(username, amount, vote)
                                if not gamba_msg:
                                    gamba_msg = "❌ Bet rejected by sytem settings or insufficient balance."
                                print(f"💎 GAMBA REGISTERED {username} -> {gamba_msg}")

                                if amount_str in ["all", "allin", "all-in", "max", "maxbet"] and success:
                                    await sender.send_message(f"🔥 {username} just risked their life savings of {amount:,} on '{vote}'! 🔥")# AWAIT_ADD

                            except ValueError:
                                print(f"🖲️ {username} entered an invalid amount string - must be int or positive balance")
                                pass

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                IS_BOT_RUNNING = False
                break
            except Exception as e:
                print(f"⚠️ Error in subroutine: {e}")
                await asyncio.sleep(2)

        if not IS_BOT_RUNNING:
            break
        # If the loop is broken, force a 2-second pause before recycling the token connection
        print("🔄️ Re-establishing connection...")
        await asyncio.sleep(2)
    
    await sender.stop()

def run_bot():
    """Root execution gate to boot the asynchronous main function on Windows."""
    try:
        asyncio.run(run_bot_async())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")

if __name__ == "__main__":
    run_bot()
