import time
import pytchat
import database
import sheets_sync
import admin_manager
import points_manager
import command_manager
import terminal_controller
from chat_sender import YouTubeChatSender

# Configuration
# VIDEO_ID = youtube.com/*********** (string of characters at the end of the live stream URL)
# VIDEO_ID = "YOUTUBE_STREAM_VIDEO_ID"
# STREAM_URL = f"https://youtube.com{VIDEO_ID}" # Opens just the chat window

def run_bot():
    # Init SQLite tables
    database.init_db()

    # 0a. Prompt for Video ID dynamically via stdin
    print("=" * 30)
    video_id = input("👉 Enter YouTube Stream Video ID: ").strip()
    print("=" * 30)

    if not video_id:
        print("❌ Error: Video ID cannot be empty.")
        return

    # 0b. Generate clean standalone live chat pop-out URL
    stream_url = f"https://youtube.com{video_id}"

    # 1. Init chat writer
    sender = YouTubeChatSender(STREAM_URL)
    sender.start()

    # Give the user a moment to verify their login state in the browser window
    input("\n👉 Press ENTER here in the VS Code terminal ONCE the browser has loaded your stream chat...")

    # 2. Init chat scraper
    print("🔍 Connecting to YouTube Live Chat reader...")
    try:
        chat = pytchat.create(video_id=VIDEO_ID)
    except Exception as e:
        print(f"❌ Failed to connect to stream: {e}")
        return

    print("🚀 Gamba Bot is running natively on Windows! Monitoring chat logs...")
    sender.send_message("🤖 Gamba Bot is online and listening for commands!")

    # Init silent keyboard controller
    terminal_controller.start_terminal_controller()

    last_passive_tick = time.time()
    while chat.is_alive():
        try:
            current_time = time.time() # 1. Check if 5 min passed to award passive points
            if current_time - last_passive_tick >= 300: # 300 secs = 5 mins
                points_manager.DistributePassivePoints()
                sheets_sync.sync_to_google_sheets() # Run Google Sheets updater code after points shift
                last_passive_tick = current_time

            if admin_manager.IS_BETTING_OPEN and not admin_manager.HAS_ANNOUNCED_LOCK:
                elapsed_bet_time = current_time - admin_manager.BET_OPEN_TIMESTAMP
                if elapsed_bet_time >= admin_manager.BET_DURATION_SECONDS:
                    admin_manager.HAS_ANNOUNCED_LOCK = True
                    # Announce Bet Lock
                    lock_msg = "🔒 Betting is now officialy LOCKED! 🔒"
                    sender.send_message(lock_msg)
                    print("🔒 [CHANNEL RELAY] Sent pool closure alert to Live Chat.")

            # 2. Get latest batch of chat messages
            for c in chat.get().sync_items():
                username = c.author.name
                channel_id = c.author.channelId
                message_text = c.message

                # NEW!: Determine if the user has an active channel membership
                is_member = getattr(c.author, "isChatSponsor", False)
                # Pass membership flag into points engine
                points_manager.process_incoming_message(
                    username,
                    message_text,
                    "textMessageEvent",
                    is_member=is_member
                )

                # NEW: Publicly celebrate Super Chats and Member Milestones in chat!
                if message_type == "superChatEvent":
                    donation_amount = details.get("amount", 0)
                    sender.send_message(f"🌟 THANK YOU @{username}! Your ${donation_amount} donation earned you bonus points! 👑")

                elif message_type == "membershipGIFTEvent" or message_type == "newSponsorEvent":
                    sender.send_message(f"👑 HYPE! @{username} just supported the channel and received a massive point drop! 🚀")

                # Catch once-a-month Free Member Milestone Announcement
                elif message_type == "memberMilestoneChatEvent":
                    # Fallback to 1 month if pytchat doesn't read the metadata object (for whatever reason)
                    months = 1

                    # Attempt to pull raw API dictionary block out of pytchat object struct
                    try:
                        if hasattr(c, 'rawdata') and 'memberMilestoneChatDetails' in c.rawdata:
                            months = c.rawdata['memberMilestoneChatDetails'].get('memberMonth', 1)
                    except Exception:
                        pass

                    # Calculate bonus using dynamic formula
                    dynamic_payout = 1000 + (months * 250)

                    # Pass the event info to the points manager
                    points_manager.process_incoming_message(
                        username,
                        message_text,
                        "memberMilestoneChatEvent",
                        details={"months": months}
                    )

                    # Send message into chat
                    sender.send_message(
                        f"🏆 MILESTONE! @{username} claimed their Month {months} Milestone Chat "
                        f"and earned 🎁 {dynamic_payout} points!"
                    )

                print(f"🏆 Milestone! @{username} used their Member Milestone Chat and was awarded {POINTS_MEMBER_MILESTONE} points!")

                # Format a clean console log for you to read while streaming
                print(f"💬 [{c.datetime}] {username}: {message_text}")

                # 3. Handle User Commands (!balance, !gamba, )
                bot_reply = command_manager.process_user_command(username, message_text)
                if bot_reply:
                    sender.send_message(bot_reply) # Relay response to YouTube Chat
                    print(f"🤖 BOT RESPONSE: {bot_reply}")
                    continue

                # 4. Handle Admin Commands (!give, !gamba_open, )
                admin_reply = admin_manager.process_admin_command(channel_id, username, message_text)
                if admin_reply:
                    sender.send_message(admin_reply) # Relay action to YouTube Chat
                    print(f"👑 ADMIN ACTION: {admin_reply}")
                    continue

                # 5. Handle Gamba betting execution
                if message_text.startswith("!gamba"):
                    if not admin_manager.is_betting_period_active():
                    if not admin_manager.IS_BETTING_OPEN:
                        print(f"🔒 GAMBA LCOKED: @{username} tried to bet, but 5m window closed")
                    else:
                        print(f"🎲 GAMBA CLOSED: @{username} tried to bet, but no pool is open.")
                        continue
                        
                    parts = message_text.split()
                    if len(parts) >= 3:
                        try:
                            amount = int(parts[1])
                            vote = parts[2].lower()

                            if vote not in admin_manager.VALID_OPTIONS or amount <= 0:
                                continue

                            success, gamba_msg = database.place_bet(username, amount, vote)
                            print(f"🎲 GAMBA: @{username} -> {gamba_msg}")
                        except ValueError:
                            pass

            # Sleep slightly to prevent CPU spinning, pytchat handles its own polling rates internally
            time.sleep(1)

        except KeyboardInterrupt:
            print("\nShutting down bot safely.")
            break
        except Exception as e:
            print(f"⚠️ Loop encountered an error: {e}")
            time.sleep(5)

    print("🛑 Stream connection lost or closed.")

if __name__ == "__main__":
    run_bot()