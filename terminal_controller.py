import sys
import threading
import database
import admin_manager
import sheets_sync

def terminal_input_loop():
    """ Continuously listens for keyboard inputs inside the TERMINAL window """
    print("⌨️ Terminal Controller Active: You can type admin commands here anytime!")
    print("👉 Available: !give [user] [amt] | !give_all [amt] | !gamba_open [opt1,opt2] [Q] | !gamba_win [opt] | !gamba_cancel")

    while True:
        try:
            # Read line from stdin (waits until ENTER is pressed)
            line = sys.stdin.readline().strip()
            if not line:
                continue
            
            parts = line.split()
            command = parts[0].lower()

            # Pass text to existing admin manager logic
            # We user '00000' and 'ConsoleAdmin' to signify it came from this TERMINAL, not the Live Chat
            reply = admin_manager.process_admin_command("00000", "ConsoleAdmin", line)

            if reply:
                print(f"🖥️ [CONSOLE EXECUTE] {reply}")

                # Force immediate spreadsheet update after any console action is taken
                sheets_sync.sync_to_google_sheets()
            
            else:
                print("❌ Unknown console command or invalid formatting!")

        except Exception as e:
            print(f"⚠️ Console Error: {e}!")

def start_terminal_controller():
    """ Init Terminal Listener on a backgroud thread so it doesn't interrupt the main loop """
    console_thread = threading.Thread(target=terminal_input_loop, daemon=True)
    console_thread.start()