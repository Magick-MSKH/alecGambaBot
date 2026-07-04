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

async def run_bot_async():
    # Init SQLite tables
    database.init_db()
    rpg_database.init_rpg_db()
    clear_db = input("💽 Clear Daily Claims? (Y/N): ")
    if not clear_db:
        print("❌ Error: Input cannot be empty.")
    elif clear_db == "Y":
        database.clear_daily_claims()
        print("🧹 Reset daily claims table for fresh session.")
    else:
        print("📋 Daily Claim flags unchanged")

    admin_manager.check_and_execute_boot_recovery()

    ###########################################
    # Prompt for Video ID dynamically via stdin
    ###########################################

    print("=" * 30)
    VIDEO_ID = input("👉 Enter YouTube Stream ID: ").strip()
    print("=" * 30)

    if not VIDEO_ID:
        print("❌ Error: Video ID cannot be empty.")
        return

    STREAM_URL = f"https://youtube.com/live_chat?v={VIDEO_ID}"

    sender = YouTubeChatSender(STREAM_URL)
    await sender.start()

    input("\n👉 Press ENTER when browser has loaded...")
    print("⏳ Settling secure authentication parameters...")
    await asyncio.sleep(3)

    browser_cookies = await sender.get_formatted_cookies()

    terminal_controller.SENDER_OBJECT = sender
    asyncio.create_task(terminal_controller.check_terminal_input())

    print("🚀 Gamba Bot is running natively on Windows! Monitoring chat logs...")
    await sender.send_message("🤖 Gamba Bot is online and listening for commands!")

    last_passive_tick = time.time()
    global IS_BOT_RUNNING
    IS_BOT_RUNNING = True

    # --- MASTER BROWSER STREAM ENGINE LOOP ---
    while IS_BOT_RUNNING:
        try:
            current_time = time.time()
            
            # 5-Minute Passive updates
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

                if message_text.startswith("!gamba"):
                    if not admin_manager.IS_BETTING_OPEN or admin_manager.IS_BETTING_LOCKED:
                        continue
                    parts = message_text.split()
                    if len(parts) >= 3:
                        try:
                            amount_str = parts[1].lower()
                            vote = parts[2].lower()
                            if vote not in admin_manager.VALID_OPTIONS: continue

                            if amount_str in ["all", "allin", "all-in"]:
                                amount = database.get_balance(username)
                            elif amount_str == "half":
                                current_wealth = database.get_balance(username)
                                amount = int(current_wealth / 2)
                            else:
                                amount = int(amount_str)
                            
                            if amount <= 0:
                                continue

                            success, gamba_msg = database.place_bet(username, amount, vote)
                            if not gamba_msg:
                                gamba_msg = "Bet rejected."
                            print(f"🎲 GAMBA REGISTERED: {username} -> {gamba_msg}")
                            
                            if amount_str in ["all", "allin", "all-in"] and success:
                                if amount < 1000:
                                    await sender.send_message(f"💤 {username} is going all-in with a measly {amount:,} points on '{vote}'")
                                else:
                                    await sender.send_message(f"🐦‍🔥 ALL-IN! {username} just risked all {amount:,} points on '{vote}'! 🐦‍🔥")
                            elif amount_str == "half":
                                await sender.send_message(f"🔥 {username} just wagered HALF of their points ({amount:,}) on '{vote}'! 🔥")
                        except ValueError:
                            pass

            await asyncio.sleep(1)

        except asyncio.CancelledError:
            IS_BOT_RUNNING = False
            break
        except Exception as e:
            print(f"⚠️ Core loop warning: {e}")
            await asyncio.sleep(2)

    await sender.stop()

def run_bot():
    """Root execution gate to handle manual system exits explicitly on Windows."""
    try:
        asyncio.run(run_bot_async())
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 System Shutdown Hook Activated. Closing bot down completely!")
        import sys
        sys.exit(0)

if __name__ == "__main__":
    run_bot()