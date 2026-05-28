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

async def run_bot_async():
    # Init SQLite tables
    database.init_db()
    database.clear_daily_claims()
    print("🧹 Reset daily claims table for fresh session.")

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

    input("\n👉 Press ENTER here in the VS Code terminal ONCE the browser has loaded your stream chat...")

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

    while chat.is_alive():
        try:
            current_time = time.time() # 
            if current_time - last_passive_tick >= 300:
                points_manager.DistributePassivePoints()
                sheets_sync.sync_to_google_sheets()
                last_passive_tick = current_time

            data = chat.get()
            if not data or 'items' not in data:
                await asyncio.sleep(1)
                continue

            #########################################
            ####### MAIN GAMBA BOT SUBROUTINE #######
            #########################################
            for c in data['items']:
                
                # YouTube API layout mappings:
                snippet = c.get("snippet", {})
                author = c.get("authorDetails", {})

                username = author.get("displayName", "")
                channel_id = author.get("channelId", "")
                message_text = snippet.get("displayMessage", "")
                
                if "magickbot0" in username.lower():
                    continue

                ### Read Event Flags directly from CompatLayer
                # FIX: Inspect interior Event Type resolution
                message_type = "textMessageEvent"
                details = {}

                ### PARSE: Super Chat
                # FIX: Look inside snippet data wrapper for specific event flags
                if "superChatDetails" in snippet:
                    message_type = "superChatEvent"
                    sc_info = snippet.get("superChatDetails", {})
                    details["amount"] = float(sc_info.get("amountMicros", 0)) / 1000000.0

                ### PARSE: Milestone
                elif "memberMilestoneChatDetails" in snippet:
                    message_type = "memberMilestoneChatEvent"
                    milestone_info = snippet.get("memberMilestoneChatDetails", {})
                    details["months"] = int(milestone_info.get("memberMonth", 1))

                elif "newSponsorEvent" in c.get("type", "") or "membershipGIFTEvent" in c.get("type", ""):
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
                    if bot_reply:
                        await sender.send_message(bot_reply)# AWAIT_ADD
                        continue
                    
                    admin_reply = admin_manager.process_admin_command(channel_id, username, message_text)
                    if admin_reply:
                        await sender.send_message(admin_reply)# AWAIT_ADD
                        continue

                elif message_type == "memberMilestoneChatEvent":
                    months = details.get("months", 1)
                    dynamic_payout = 1000 + (months * 250)

                    ### Terminal print confirmation
                    print(f"🖲️ [MILESTONE TRACKED] {username} for Month {months}!")

                    await sender.send_message(f"🏆 {username} claimed thier {months}-month member chat for {dynamic_payout:,} points! 🎁")# AWAIT_ADD
                    sheets_sync.sync_to_google_sheets()
                    continue

                elif message_type == "superChatEvent":
                    donation_amount = details.get("amount", 0.0)

                    ### Terminal print confirmation
                    print(f"🖲️ [SUPER CHAT DETECTED] {username} donated {donation_amount:.2f}")

                    await sender.send_message(f"🌟 {username}'s Super Chat earned channel points!")# AWAIT_ADD
                    sheets_sync.sync_to_google_sheets()
                    continue

                elif message_type == "membershipGIFTEvent":
                    print(f"🖲️ [MEMBERSHIP DETECTED] {username} supported the channel")
                    await sender.send_message(f"👑 {username} earned bonus points for Membership!")# AWAIT_ADD
                    sheets_sync.sync_to_google_sheets()
                    continue

                # Format a clean console log to read while streaming
                published_at = snippet.get("publishedAt", "LIVE")
                print(f"🖲️ [{published_at}] {username}: {message_text}")

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
                        amount = int(parts[1])
                        vote = parts[2].lower()
                            
                        # Validate choice against active variables
                        if vote not in admin_manager.VALID_OPTIONS or amount <= 0:
                            continue

                        try: # !gamba [amount] [vote_choice]
                            if amount_str in ["all", "allin", "all-in", "max", "maxbet"]:
                                amount = database.get_balance(username)
                            else:
                                amount = int(amount_str)
                            
                            if amount <= 0:
                                print(f"🖲️ {username} tried to bet 0 or an invalid amount ({amount})")
                                continue

                            success, gamba_msg = database.place_bet(username, amount, vote)
                            print(f"🖲️ GAMBA REGISTERED {username} -> {gamba_msg} 💎")

                            if amount_str in ["all", "allin", "all-in", "max", "maxbet"] and success:
                                await sender.send_message(f"🔥 {username} just risked their life savings of {amount:,} on '{vote}'! 🔥")# AWAIT_ADD

                        except ValueError:
                            print(f"🖲️ {username} entered an invalid amount string - must be int or positive balance")
                            pass

            await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("\nShutting down bot safely.")
            break
        except Exception as e:
            print(f"⚠️ Error in subroutine: {e}")
            time.sleep(5)
    
    await sender.stop()

def run_bot():
    """Root execution gate to boot the asynchronous main function on Windows."""
    try:
        asyncio.run(run_bot_async())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")

if __name__ == "__main__":
    run_bot()