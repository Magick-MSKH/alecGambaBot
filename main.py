import time
import pytchat
import database
import sheets_sync
import admin_manager
import points_manager
import command_manager
import terminal_controller
from pytchat import CompatibleProcessor     # NEW!: Advanced metadata event parser
from chat_sender import YouTubeChatSender

def run_bot():
    # Init SQLite tables
    database.init_db()

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
    sender.start()

    input("\n👉 Press ENTER here in the VS Code terminal ONCE the browser has loaded your stream chat...")

    ###################################################
    # 2. Init chat scraper
    ###################################################

    print("🔍 Connecting to YouTube Live Chat reader via CompatLayer")
    try:
        # CompatLayer: pass advanced processing flags here to reveal Superchats and Milestones
        chat = pytchat.create(video_id=VIDEO_ID, processor=CompatibleProcessor())
    except Exception as e:
        print(f"❌ Failed to connect to stream: {e}")
        sender.stop()
        return

    print("🚀 Gamba Bot is running natively on Windows! Monitoring chat logs...")
    sender.send_message("🤖 Gamba Bot is online and listening for commands!")

    ###################################################
    # Init silent keyboard controller
    ###################################################

    terminal_controller.start_terminal_controller()

    last_passive_tick = time.time()
    while chat.is_alive():
        try:
            current_time = time.time() # 
            if current_time - last_passive_tick >= 300:
                points_manager.DistributePassivePoints()
                sheets_sync.sync_to_google_sheets()
                last_passive_tick = current_time

            for c in chat.get().sync_items():
                # Read structural tags from the advanced API object layout
                author = c.get("author", {})
                username = author.get("name", "")
                channel_id = author.get("channelId", "")
                message_text = c.get("message", "")
                
                # BAN MAGICKBOT0!!!: Pull raw channel flags from metadata to detect
                if "magickbot0" in username.lower():
                    continue

                ### Read Event Flags directly from CompatLayer
                message_type = c.get("type", "textMessageEvent")
                details = {}

                ### PARSE: Super Chat
                if message_type == "superChatEvent":
                    details["amount"] = float(c.get("amountValue", 0.0))

                ### PARSE: Milestone
                elif message_type == "memberMilestoneChatEvent":
                    details["months"] = int(c.get("memberMonth", 1))

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
                    print(f"💬 {username}: {message_text}")

                    bot_reply = command_manager.process_user_command(username, message_text)
                    if bot_reply:
                        sender.send_message(bot_reply)
                        continue

                    admin_reply = admin_manager.process_admin_command(channel_id, username, message_text)
                    if admin_reply:
                        sender.send_message(admin_reply)
                        continue

                elif message_type == "memberMilestoneChatEvent":
                    months = details.get("months", 1)
                    dynamic_payout = 1000 + (months * 250)
                    print(f"🏆 MILESTONE TRACKED: {username} for Month {months}")
                    sender.send_message(f"🏆 {username} claimed thier {months}-month member chat for {dynamic_payout:,} points! 🎁")
                    sheets_sync.sync_to_google_sheets()
                    continue

                elif message_type == "superChatEvent":
                    donation_amount = details.get("amount", 0.0)
                    print(f"🌟 {username} donated {donation_amount}")
                    sender.send_message(f"🌟 {username}'s Super Chat earned channel points!")
                    sheets_sync.sync_to_google_sheets()
                    continue

                elif message_type in ["newSponsorEvent", "membershipGIFTEvent"]:
                    print(f"👑 MEMBERSHIP EVENT: {username}")
                    sender.send_message(f"👑 {username} earned bonus points for Membership!")
                    sheets_sync.sync_to_google_sheets()
                    continue

                # Format a clean console log to read while streaming
                print(f"💬 [{c.datetime}] {username}: {message_text}")

                ###########################################
                # COMMAND HANDLER #
                ###########################################

                bot_reply = command_manager.process_user_command(username, message_text)
                if bot_reply:
                    sender.send_message(bot_reply)
                    print(f"🤖 BOT RESPONSE: {bot_reply}")
                    continue

                # 4. Handle Admin Commands (!give, !gamba_open, )
                admin_reply = admin_manager.process_admin_command(channel_id, username, message_text)
                if admin_reply:
                    sender.send_message(admin_reply)
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
                            amount = int(parts[1])
                            vote = parts[2].lower()
                            
                            # Validate choice against active variables
                            if vote not in admin_manager.VALID_OPTIONS or amount <= 0:
                                continue

                            success, gamba_msg = database.place_bet(username, amount, vote)
                            print(f"🎲 GAMBA REGISTERED: {username} -> {gamba_msg}")
                        except ValueError:
                            pass

            time.sleep(1)

        except KeyboardInterrupt:
            print("\nShutting down bot safely.")
            break
        except Exception as e:
            print(f"⚠️ Error in subroutine: {e}")
            time.sleep(5)
    
    sender.stop()

    print("🛑 Stream connection lost or closed.")

if __name__ == "__main__":
    run_bot()