import sys
import msvcrt
import asyncio
import admin_manager
import sheets_sync

async def check_terminal_input():
    """
    Natively monitors the Windows VS Code terminal for admin commands.
    Bypasses all asyncio ProactorPipe/WinError 6 handle bugs using msvcrt.
    """
    print("⌨️  Terminal Controller Active: ")
    print("-" * 75)

    input_buffer = ""

    while True:
        try:
            # Check if a keyboard key has been pressed in the terminal window
            if msvcrt.kbhit():
                # 1. Read the character byte natively from the console
                char_byte = msvcrt.getche()
                
                # FIX: Decode the text character instantly right here so 'char' ALWAYS has a value!
                char = char_byte.decode(errors='ignore')

                # 2. Handle Backspace key presses safely
                if char_byte == b'\x08':
                    if len(input_buffer) > 0:
                        input_buffer = input_buffer[:-1]
                        # Clean up the visual terminal display for backspaces on Windows
                        sys.stdout.write(" \b")
                        sys.stdout.flush()
                    continue

                # 3. Handle Enter key press (Submit the command string!)
                elif char_byte == b'\r' or char_byte == b'\n':
                    command_line = input_buffer.strip()
                    input_buffer = "" # Reset the buffer instantly
                    print("") # Move terminal display down to a fresh line

                    if not command_line:
                        continue

                    print(f"🖥️  [CONSOLE EXECUTE] Processing: {command_line}")
                    
                    # Route the command to your existing admin manager logic
                    reply = admin_manager.process_admin_command("00000", "ConsoleAdmin", command_line)
                    
                    if reply:
                        print(f"🖥️  [CONSOLE RESPONSE] {reply}")
                        sheets_sync.sync_to_google_sheets()
                    else:
                        print("❌ Console Warning: Command ignored or invalid formatting layout.")
                
                # 4. Handle regular text characters
                else:
                    input_buffer += char

        except Exception as e:
            print(f"\n⚠️ Console key error: {e}")
            input_buffer = ""

        # Yield control for a microsecond to keep the CPU usage at 0%
        await asyncio.sleep(0.05)
