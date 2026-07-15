import sys
import msvcrt
import asyncio
import admin_manager
import sheets_sync

SENDER_OBJECT = None

async def check_terminal_input():
    global SENDER_OBJECT
    
    print("⌨️  Terminal Controller Active: You can type admin commands here anytime!")
    print("👉 Available: !give [user] [amt] | !give_all [amt] | !gamba_open [opt1,opt2] [Q] | !gamba_lock | !gamba_win [opt] | !gamba_cancel")
    print("-" * 75)

    input_buffer = ""

    while True:
        try:
            if msvcrt.kbhit():
                char_byte = msvcrt.getche()
                char = char_byte.decode(errors='ignore')

                if char_byte == b'\x08':
                    if len(input_buffer) > 0:
                        input_buffer = input_buffer[:-1]
                        sys.stdout.write(" \b")
                        sys.stdout.flush()
                    continue

                elif char_byte == b'\r' or char_byte == b'\n':
                    command_line = input_buffer.strip()
                    input_buffer = "" 
                    print("") 

                    if not command_line:
                        continue

                    if command_line.lower() in ["!quit", "!exit", "!shutdown"]:
                        print("🛑 SHUTTING DOWN ENGINE: Closing local tasks and closing Chrome window context...")
                        import main
                        main.IS_BOT_RUNNING = False
                        sys.exit(0)

                    print(f"🖥️  [CONSOLE EXECUTE] Processing: {command_line}")
                    reply = admin_manager.process_admin_command("00000", "ConsoleAdmin", command_line)
                    
                    if reply:
                        print(f"🖥️  [CONSOLE RESPONSE] {reply}")
                        
                        # NEW: If the command is an announcement that viewers NEED to see,
                        # relay that text string straight to the YouTube live stream!
                        # We skip plain '!give' command spam so chat stays bloat-free.
                        if command_line.startswith("!gamba_") or command_line.startswith("!give_all"):
                            if SENDER_OBJECT:
                                # We 'await' the message delivery securely
                                await SENDER_OBJECT.send_message(reply)
                        
                        # Instantly update the Google Sheet leaderboard
                        sheets_sync.sync_to_google_sheets()
                    else:
                        print("❌ Console Warning: Command ignored or invalid formatting layout.")
                
                else:
                    input_buffer += char

        except Exception as e:
            print(f"\n⚠️ Console key error: {e}")
            input_buffer = ""

        await asyncio.sleep(0.05)