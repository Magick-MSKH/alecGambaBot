import sys
import time
import httpx
import asyncio
import pytchat
import database
import sheets_sync
import rpg_database
import admin_manager
import points_manager
import command_manager
import terminal_controller
from pytchat import CompatibleProcessor
from chat_sender import YouTubeChatSender

IS_BOT_RUNNING = True
PIT_COST_MODIFIER = 0

async def run_bot_async():

    database.init_db()

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # Clear Daily Claims
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    clear_db = input("💽 Clear Daily Claims? (Y/N): ")
    if not clear_db:
        print("❌ Error: Input cannot be empty.")
    elif clear_db == "Y":
        database.clear_daily_claims()
    else:
        print("📋 Daily Claim flags unchanged")

    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # Stream Select
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    print("🖥️ STREAM PROFILE INIT 🖥️")
    stream_choice = input("Select Stream Profile: ").strip().upper()
    if stream_choice == "A":
        PROFILE_SUFFIX = "alec"
        channel_name = "Alec"
    elif stream_choice == "S":
        PROFILE_SUFFIX = "sample"
        channel_name = "Sample"
    elif stream_choice == "C":
        PROFILE_SUFFIX = "chicken"
        channel_name = "Chickeninja42"
    else:
        print("❌ Invalid selection! Defaulting to Alec profile...")
        PROFILE_SUFFIX = "alec"
        channel_name = "Alec"

    admin_manager.check_and_execute_boot_recovery()

    print("=" * 30)
    VIDEO_ID = input("👉 Enter YouTube Stream ID: ").strip()
    print("=" * 30)

    if not VIDEO_ID:
        print("❌ Error: Video ID cannot be empty.")
        return

    STREAM_URL = f"https://youtube.com/live_chat?v={VIDEO_ID}"

    sender = YouTubeChatSender(STREAM_URL, profile_name=PROFILE_SUFFIX)
    await sender.start()

    input("\n👉 Press ENTER when browser has loaded...")
    print("⏳ Settling secure authentication parameters...")
    await asyncio.sleep(3)

    browser_cookies = await sender.get_formatted_cookies()

    terminal_controller.SENDER_OBJECT = sender
    asyncio.create_task(terminal_controller.check_terminal_input())
    await sender.send_message("🤖 MagickBot is online, running version 1.7")

    last_passive_tick = time.time()
    global IS_BOT_RUNNING
    IS_BOT_RUNNING = True

    while IS_BOT_RUNNING:
        try:
            current_time = time.time()
            
            if current_time - last_passive_tick >= 300:
                points_manager.DistributePassivePoints()
                sheets_sync.sync_to_google_sheets()
                last_passive_tick = current_time

            items = await sender.get_new_messages()

            for c in items:
                username = c["username"]
                message_text = c["message_text"]
                message_type = c["message_type"]
                details = c["details"]
                is_member = c["is_member"]
                
                if "magickbot0" in username.lower():
                    continue

                points_manager.process_incoming_message(
                    username, message_text, message_type, details=details, is_member=is_member
                )

                if message_type == "textMessageEvent":
                    print(f"💬 [LIVE_WINDOW] {username}: {message_text}")
                    
                    bot_reply = command_manager.process_user_command(username, message_text, is_member)
                    if bot_reply and isinstance(bot_reply, str):
                        await sender.send_message(bot_reply)
                        continue

                    admin_reply = admin_manager.process_admin_command("", username, message_text)
                    if admin_reply and isinstance(admin_reply, str):
                        await sender.send_message(admin_reply)
                        continue

                elif message_type == "memberMilestoneChatEvent":
                    months = details.get("months", 1)
                    dynamic_payout = 1000 + (months * 250)

                    print(f"🏆 [MILESTONE DETECTED] {username} cashed in Month {months}!")
                    database.add_points(username, dynamic_payout)
                    await sender.send_message(f"🏆🎁 MILESTONE! {username} claimed their Month {months} membership message and earned {dynamic_payout:,} points!")

                    sheets_sync.sync_to_google_sheets()
                    continue

                elif message_type == "superChatEvent":
                    donation_amount = details.get("amount", 5.0)
                    print(f"🌟 [SUPER CHAT] {username} donated ${donation_amount}")
                    await sender.send_message(f"🌟 THANK YOU {username}! Your ${donation_amount:.2f} SuperChat earned you a massive points bonus! 👑")
                    sheets_sync.sync_to_google_sheets()
                    continue

                elif message_type == "membershipGIFTEvent":
                    NEW_MEMBER_BONUS = 2500
                    print(f"👑 [MEMBERSHIP UPGRADE] {username} supported the channel!")
                    database.add_points(username, NEW_MEMBER_BONUS)
                    sheets_sync.sync_to_google_sheets()
                    continue

            await asyncio.sleep(1)

        except asyncio.CancelledError: 
            IS_BOT_RUNNING = False
            break
        except Exception as e:
            print(f"⚠️ Core loop warning: {e}")
            await asyncio.sleep(2)

    await sender.stop()

def run_bot():
    try:
        asyncio.run(run_bot_async())
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 System Shutdown Hook Activated. Closing bot down completely!")
        import sys
        sys.exit(0)

if __name__ == "__main__":
    run_bot()